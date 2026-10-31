// TruMenu.asi - in-game debug menu for the PC tru.exe (Steam, Tomb Raider: Underworld, image base 0x400000),
// operated with the Xbox controller (L3 + R3 opens / closes it), drawn with Dear ImGui (MIT, src/asi/third_party).
//
// Hooks (every address is checked against the expected bytes first; on a mismatch that part stays off and the reason
// is logged - see README.md):
//   pad    The game loads XInput itself: tru+0x824f0 calls LoadLibraryW("xinput9_1_0.dll") and GetProcAddress through
//          the import slot 0x0083e08c and stores "XInputGetState" in 0x00a02b8c (the pointer the per-frame pad poll
//          tru+0x84b82 calls). TruMenu replaces that import slot at load time with a filter that hands out its own
//          PadHook for "XInputGetState" - so the game itself writes PadHook into 0x00a02b8c, before any other plugin
//          can wrap the pointer. TruShadowPower.asi (waits for the pointer, then wraps whatever is there) therefore
//          always wraps PadHook, whatever the load order of the two plugins. PadHook calls the real XInputGetState,
//          watches L3 + R3 and hands the game a neutral pad while the menu is open. Project chaining rule (shared
//          with TruShadowPower / TruLink): hook once, re-hook only when the slot points into xinput*.dll again,
//          thread-local re-entry guard that calls the real XInputGetState. When the game does not poll the slot
//          (front end, loading) the Present hook reads the pad itself after 250 ms.
//   d3d9   The game's device manager is [0x00ad75e4] (created at tru+0x1239c0), its IDirect3DDevice9 at +0x208 (out
//          parameter of the CreateDevice call tru+0x122736). A worker thread waits for that device and patches the
//          device's own vtable entries Reset (16) and Present (17). This works with or without a d3d9.dll proxy
//          (TRAWindowed): the vtable patched is the one of the object the game calls.
//   game   Every menu entry is an item with a stable id (kItems); items that touch the game (cheat, camera, level
//          change, debug flag) are queued and run on the game thread inside PadHook - or inside the Present hook
//          while the game does not poll the pad. Exports TruMenuList / TruMenuInvoke make them callable without the
//          controller (TruLink "menu" command).
//
// Facts about engine functions marked "TRLAU" were learned from TheIndra55/TRLAU-menu-hook (GPL v3), read as reference
// only; no code was taken from it (README.md, Credits).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <ctype.h>

#include "imgui.h"
#include "imgui_impl_dx9.h"
#include "imgui_impl_win32.h"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

namespace {

const char *const kVersion = "TruMenu 0.1 (debug menu: status, Lara position overlay, level select, experimental "
                             "cheat / camera; items callable by id)";

struct PadState {                       // XINPUT_STATE without including xinput.h
    DWORD dwPacketNumber;
    WORD wButtons;
    BYTE bLeftTrigger, bRightTrigger;
    SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY;
};

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, PadState *);
typedef FARPROC(WINAPI *GetProcAddressFn)(HMODULE, LPCSTR);
typedef HRESULT(STDMETHODCALLTYPE *PresentFn)(IDirect3DDevice9 *, const RECT *, const RECT *, HWND, const RGNDATA *);
typedef HRESULT(STDMETHODCALLTYPE *ResetFn)(IDirect3DDevice9 *, D3DPRESENT_PARAMETERS *);
typedef void(__cdecl *InstancePostFn)(void *instance, int message, int data);
typedef void(__cdecl *CameraSetModeFn)(int mode);
typedef void(__fastcall *CameraRestoreFn)(void *manager, int);   // thiscall without arguments
typedef void(__cdecl *LevelChangeFn)(char *name, void *gameTracker, int doneType);

const WORD kPadL3 = 0x0040, kPadR3 = 0x0080;

// ---- addresses (PC tru.exe, Steam) ----
const DWORD kImageBase = 0x00400000;
// pad: tru+0x824f0 loads XInput; the import slot of GetProcAddress, the pointer it fills, the per-frame poll
const DWORD kPadLoader = 0x004824f0;
const char *const kPadLoaderBytes = "68a84b8400 ff1590e08300 85c0 a3882ba000 743b 56 8b358ce08300 68984b8400 50 ffd6"
                                    " a38c2ba000";
const DWORD kGetProcSlot = 0x0083e08c;
const DWORD kPadPointer = 0x00a02b8c;
const DWORD kPadCallSite = 0x00484b82;
const char *const kPadCallBytes = "ff158c2ba000";              // call dword ptr [0x00a02b8c]
const DWORD kXInputName = 0x00844b98;                          // "XInputGetState"
// d3d9: device manager global and the device field (CreateDevice out parameter)
const DWORD kD3dCreate = 0x005239c0;
const char *const kD3dCreateBytes = "a1e475ad00 85c0 56 57 0f859c000000 6810b68400 ff15b8e08300";
const DWORD kD3dStore = 0x00523a30;
const char *const kD3dStoreBytes = "a3e475ad00";
const DWORD kCreateDeviceCall = 0x00522711;
const char *const kCreateDeviceBytes = "8d9e08020000 53";      // lea ebx, [esi+0x208]; push ebx (ppDevice)
const DWORD kCreateDeviceCall2 = 0x00522733;
const char *const kCreateDeviceBytes2 = "8b4a40 ffd1";         // mov ecx, [edx+0x40]; call ecx (IDirect3D9 slot 16)
const DWORD kDeviceManager = 0x00ad75e4;
const DWORD kDeviceField = 0x208;
// game state
const DWORD kGameTracker = 0x00e7f088;                         // TRLAU: GameTracker
const DWORD kPlayerPtr = 0x00e7f094;                           // GameTracker +0xc playerInstance
const char *const kPlayerReaderBytes = "8b0d94f0e700";         // a reader at 0x00741764 (as TruShadowPower checks)
const DWORD kPlayerReader = 0x00741764;
const DWORD kInstancePosition = 0x20;                          // TRLAU Instance.h: position (16-byte vector)
const DWORD kInstanceRotation = 0x30;                          //                  rotation (16-byte vector)
const DWORD kCheatMode = 0x00e7f144;                           // GameTracker +0xbc cheatMode (TRLAU)
const DWORD kDebugFlags2 = 0x00e7f09c;                         // GameTracker +0x14 debugFlags2 (TRLAU)
const DWORD kInstancePost = 0x005b3750;                        // TRLAU: INSTANCE_Post (cdecl, ret)
const char *const kInstancePostBytes = "56 8b742408 8d8610010000 85c0 7422 57 8bbe20010000";
const DWORD kCameraSetMode = 0x005f39f0;                       // TRLAU / Befund-Entwicklerkanal: CAMERA_SetMode
const char *const kCameraSetModeBytes = "56 8b742408 83fe06 751e 813d3405e800e0eae800";
const DWORD kCameraRestore = 0x005edf50;                       // thiscall CameraManager, no arguments
const char *const kCameraRestoreBytes = "d90530118400 56 8bf1 33c9 d95e78";
const DWORD kCameraManager = 0x00e804f0;
const DWORD kCurrentCamera = 0x00e80534;                       // [manager + 0x44]
const volatile DWORD *const kGameClock = reinterpret_cast<const volatile DWORD *>(0x00e7f15c);
const DWORD kLevelChange = 0x005df8c0;                         // TRLAU: GAMELOOP_RequestLevelChangeByName (cdecl)
const char *const kLevelChangeBytes = "56 8b742408 57 56 e8d45e0600 8b7c2414 83c404 80bfb900000000 754d 834f2c01";
const DWORD kLevelNameCopy = 0x005df8ee;                       // add edi, 0x38: name copied to GameTracker+0x38
const DWORD kUnitName = 0x00e7f0c0;                            // GameTracker +0x38 (tru+0x3744ae reloads it)
const DWORD kFrameStore = 0x005da40c;
const char *const kFrameStoreBytes = "d91590f1e700";           // fst dword [0xe7f190] (frame time, 30 fps units)
const float *const kFrameTime = reinterpret_cast<const float *>(0x00e7f190);

// ---- options (TruMenu.ini) ----
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 actions, 3 debug
WORD g_toggleButtons = kPadL3 | kPadR3;
int g_toggleKey = 0;                    // virtual key (e.g. 119 = F8), 0 = off
int g_blockInput = 1;
float g_scale = 1.5f;
int g_overlayAtStart = 0;
int g_experimental = 1;
float g_flightSpeed = 20.0f;

// ---- state ----
char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
CRITICAL_SECTION g_padLock;
volatile LONG g_stop = 0;
volatile LONG g_menuOpen = 0;
volatile LONG g_menuJustOpened = 0;
volatile LONG g_overlay = 0;

bool g_levelOk = false;
bool g_baseOk = false, g_padCodeOk = false, g_d3dCodeOk = false, g_playerOk = false, g_postOk = false,
     g_cameraOk = false, g_frameOk = false;
volatile GetProcAddressFn g_getProcOriginal = nullptr;
volatile XInputGetStateFn g_padOriginal = nullptr;   // what PadHook calls (the real XInputGetState)
volatile XInputGetStateFn g_selfPoll = nullptr;      // fallback: own reads when PadHook could not be placed
volatile XInputGetStateFn g_padReal = nullptr;        // XInputGetState inside the xinput module (re-entry guard)
const char *g_padMode = "waiting";
bool g_padSetupDone = false;
bool g_padModeIdle = false;             // the game has not polled the pad slot for 250 ms (front end?)
PadState g_pad[4];                                    // last real state per pad (before neutralising)
bool g_padConnected[4];
bool g_comboHeld[4];
bool g_swallow[4];
int g_lastPad = 0;
DWORD g_lastClock = 0;

volatile PresentFn g_presentOriginal = nullptr;
volatile ResetFn g_resetOriginal = nullptr;
IDirect3DDevice9 *volatile g_device = nullptr;
const char *g_d3dMode = "waiting for the device";
HWND g_hwnd = nullptr;
WNDPROC g_wndProcOriginal = nullptr;
bool g_imguiReady = false;
bool g_imguiFailed = false;
IDirect3DDevice9 *g_imguiDevice = nullptr;
bool g_keyHeld = false;

// game-thread request slot (one at a time): written by the menu / TruMenuInvoke, run by PadHook (or by the Present
// hook when the game has not polled the pad for 250 ms, e.g. in the front end)
CRITICAL_SECTION g_reqLock;
HANDLE g_reqDone = nullptr;
volatile LONG g_reqPending = 0;
char g_reqId[64], g_reqArg[160], g_reqResult[512];
char g_lastAction[512] = "none";
volatile DWORD g_lastPadHookTick = 0;
bool g_flight = false;                  // our view of GameTracker.cheatMode after our own toggle
int g_cameraModeChoice = 11;
char g_levelList[1024] = "";            // [Levels] List (comma separated unit names)

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[512];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        fputs(line, f);
        fputs("\n", f);
        fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[64];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char pair[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(pair, nullptr, 16));
        p += 2;
    }
    __try {
        return memcmp(reinterpret_cast<const void *>(address), buf, n) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadDword(DWORD address, DWORD *out) {
    __try {
        *out = *reinterpret_cast<const volatile DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadFloats(DWORD address, float *out, int count) {
    __try {
        for (int i = 0; i < count; ++i) out[i] = reinterpret_cast<const volatile float *>(address)[i];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// module that holds an address ("?" if none) - for the status page and the log
void ModuleOf(const void *address, char *out, size_t size) {
    HMODULE module = nullptr;
    out[0] = '?';
    out[1] = 0;
    if (!address || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                        static_cast<LPCSTR>(address), &module))
        return;
    char path[MAX_PATH];
    DWORD len = GetModuleFileNameA(module, path, MAX_PATH);
    if (!len) return;
    const char *name = path + len;
    while (name > path && name[-1] != '\\' && name[-1] != '/') --name;
    strncpy_s(out, size, name, _TRUNCATE);
}

bool WriteDword(DWORD address, DWORD value) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old)) return false;
    InterlockedExchange(reinterpret_cast<volatile LONG *>(address), static_cast<LONG>(value));
    DWORD unused = 0;
    VirtualProtect(reinterpret_cast<void *>(address), sizeof(DWORD), old, &unused);
    return true;
}

void RunPending();     // items section below
bool InLevel();

// flight: while cheat mode is on and the menu is closed, the triggers move Lara up (RT) / down (LT) - TRLAU moves
// position.z the same way with keys
void FlightTick(const PadState &pad) {
    if (!g_flight || !g_playerOk || !g_frameOk) return;
    __try {
        if (!*reinterpret_cast<volatile BYTE *>(kCheatMode)) { g_flight = false; return; }
        DWORD player = *reinterpret_cast<volatile DWORD *>(kPlayerPtr);
        if (!player) return;
        float frames = *kFrameTime;
        if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
        float up = (pad.bRightTrigger > 30 ? pad.bRightTrigger / 255.0f : 0.0f) -
                   (pad.bLeftTrigger > 30 ? pad.bLeftTrigger / 255.0f : 0.0f);
        if (up != 0.0f) *reinterpret_cast<volatile float *>(player + kInstancePosition + 8) += up * g_flightSpeed * frames;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_flight = false;
    }
}

// ---- pad ----
void ToggleMenu(const char *by) {
    LONG open = !InterlockedCompareExchange(&g_menuOpen, 0, 0);
    InterlockedExchange(&g_menuOpen, open);
    if (open) InterlockedExchange(&g_menuJustOpened, 1);
    Log(2, "menu %s (%s)", open ? "opened" : "closed", by);
}

// real pad state in, toggle detection; returns true when the game must get a neutral state
bool OnPad(DWORD index, bool connected, const PadState *state) {
    if (index > 3) return false;
    EnterCriticalSection(&g_padLock);
    g_padConnected[index] = connected;
    WORD buttons = connected ? state->wButtons : 0;
    if (connected) {
        g_pad[index] = *state;
        if (buttons) g_lastPad = static_cast<int>(index);
    }
    bool combo = (buttons & g_toggleButtons) == g_toggleButtons;
    bool toggled = false;
    if (combo && !g_comboHeld[index]) {
        g_comboHeld[index] = true;
        g_swallow[index] = true;
        toggled = true;
    } else if (!combo) {
        g_comboHeld[index] = false;
    }
    // after a toggle the pad stays neutral until both sticks are released, so the game never sees the half combo
    if (g_swallow[index] && !(buttons & g_toggleButtons)) g_swallow[index] = false;
    bool neutral = g_swallow[index];
    LeaveCriticalSection(&g_padLock);
    if (toggled) ToggleMenu("pad");
    return neutral || (g_blockInput && g_menuOpen);
}

// project chaining rule (TruShadowPower / TruLink / TruMenu share the slot 0x00a02b8c): hook once, re-hook only when
// the slot points into the real XInputGetState again, and on re-entry on the same thread call the real one directly
__declspec(thread) int t_padDepth = 0;

bool IsXInputModule(const void *address) {
    char owner[MAX_PATH];
    ModuleOf(address, owner, sizeof(owner));
    return _strnicmp(owner, "xinput", 6) == 0;
}

XInputGetStateFn RealXInput() {
    XInputGetStateFn real = g_padReal;
    if (real) return real;
    const char *const names[] = {"xinput9_1_0.dll", "xinput1_3.dll", "xinput1_4.dll"};
    for (const char *name : names) {
        HMODULE module = GetModuleHandleA(name);
        if (module && (real = reinterpret_cast<XInputGetStateFn>(GetProcAddress(module, "XInputGetState"))) != nullptr) {
            g_padReal = real;
            return real;
        }
    }
    return nullptr;
}

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    if (t_padDepth > 0) {                     // re-entered through another plugin's wrapper: no second pass
        XInputGetStateFn real = RealXInput();
        return real ? real(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    }
    ++t_padDepth;
    XInputGetStateFn original = g_padOriginal;
    DWORD result = original ? original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    --t_padDepth;
    bool connected = result == ERROR_SUCCESS && state;
    PadState copy = {};
    if (connected) copy = *state;
    if (OnPad(index, connected, &copy) && connected) {
        DWORD packet = state->dwPacketNumber;
        memset(state, 0, sizeof(*state));
        state->dwPacketNumber = packet;
    }
    g_lastPadHookTick = GetTickCount();
    if (g_reqPending) RunPending();           // game thread; the game clock may stand still (front end, pause)
    DWORD clock = *kGameClock;
    if (clock != g_lastClock) {               // once per game frame (the game polls several pads per frame)
        g_lastClock = clock;
        if (!g_menuOpen && connected) FlightTick(copy);
    }
    return result;
}

FARPROC WINAPI GetProcHook(HMODULE module, LPCSTR name) {
    GetProcAddressFn original = g_getProcOriginal;
    FARPROC result = original(module, name);
    if (result && HIWORD(reinterpret_cast<DWORD_PTR>(name)) && strcmp(name, "XInputGetState") == 0 &&
        reinterpret_cast<FARPROC>(&PadHook) != result) {
        if (IsXInputModule(reinterpret_cast<const void *>(result))) g_padReal = reinterpret_cast<XInputGetStateFn>(result);
        g_padOriginal = reinterpret_cast<XInputGetStateFn>(result);
        g_padMode = "PadHook given to the game (import filter)";
        char owner[MAX_PATH];
        ModuleOf(reinterpret_cast<const void *>(result), owner, sizeof(owner));
        Log(1, "pad: game asked for XInputGetState (0x%08lx, %s) - handed out PadHook", reinterpret_cast<DWORD>(result),
            owner);
        return reinterpret_cast<FARPROC>(&PadHook);
    }
    return result;
}

// ---- d3d9 ----
void PatchVtable(void **vtable, int index, void *hook, void *volatile *original, const char *what) {
    if (vtable[index] == hook) return;
    DWORD old = 0;
    if (!VirtualProtect(&vtable[index], sizeof(void *), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "d3d9: VirtualProtect on the vtable failed (%lu) - %s not hooked", GetLastError(), what);
        return;
    }
    *original = vtable[index];               // set before the swap: the game may call it right away
    InterlockedExchange(reinterpret_cast<volatile LONG *>(&vtable[index]),
                        static_cast<LONG>(reinterpret_cast<DWORD_PTR>(hook)));
    DWORD unused = 0;
    VirtualProtect(&vtable[index], sizeof(void *), old, &unused);
    char owner[MAX_PATH];
    ModuleOf(*original, owner, sizeof(owner));
    Log(1, "d3d9: %s hooked (vtable 0x%08lx slot %d, original 0x%08lx in %s)", what, reinterpret_cast<DWORD>(vtable),
        index, reinterpret_cast<DWORD>(*original), owner);
}

LRESULT CALLBACK WndProcHook(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    if (g_imguiReady && g_menuOpen) ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam);
    return IsWindowUnicode(hwnd) ? CallWindowProcW(g_wndProcOriginal, hwnd, msg, wParam, lParam)
                                 : CallWindowProcA(g_wndProcOriginal, hwnd, msg, wParam, lParam);
}

bool InitImGui(IDirect3DDevice9 *device) {
    D3DDEVICE_CREATION_PARAMETERS params = {};
    HWND hwnd = nullptr;
    if (SUCCEEDED(device->GetCreationParameters(&params))) hwnd = params.hFocusWindow;
    if (!hwnd) {
        IDirect3DSwapChain9 *chain = nullptr;
        if (SUCCEEDED(device->GetSwapChain(0, &chain)) && chain) {
            D3DPRESENT_PARAMETERS pp = {};
            if (SUCCEEDED(chain->GetPresentParameters(&pp))) hwnd = pp.hDeviceWindow;
            chain->Release();
        }
    }
    if (!hwnd) {
        Log(0, "imgui: no window handle from the device - menu off");
        return false;
    }
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = nullptr;                // nothing written next to the game
    io.LogFilename = nullptr;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad | ImGuiConfigFlags_NavEnableKeyboard;
    io.FontGlobalScale = g_scale;
    ImGui::StyleColorsDark();
    ImGui::GetStyle().ScaleAllSizes(g_scale);
    if (!ImGui_ImplWin32_Init(hwnd) || !ImGui_ImplDX9_Init(device)) {
        Log(0, "imgui: backend init failed - menu off");
        return false;
    }
    g_hwnd = hwnd;
    g_imguiDevice = device;
    WNDPROC previous = reinterpret_cast<WNDPROC>(
        IsWindowUnicode(hwnd) ? GetWindowLongPtrW(hwnd, GWLP_WNDPROC) : GetWindowLongPtrA(hwnd, GWLP_WNDPROC));
    g_wndProcOriginal = previous;
    LONG_PTR set = IsWindowUnicode(hwnd)
                       ? SetWindowLongPtrW(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&WndProcHook))
                       : SetWindowLongPtrA(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&WndProcHook));
    if (!set) Log(1, "imgui: window procedure not replaced (%lu) - mouse / keyboard input off", GetLastError());
    Log(1, "imgui %s ready (window 0x%08lx, device 0x%08lx, scale %.2f)", IMGUI_VERSION, reinterpret_cast<DWORD>(hwnd),
        reinterpret_cast<DWORD>(device), g_scale);
    return true;
}

void FeedGamepad(ImGuiIO &io) {
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    PadState pad = {};
    bool have = false;
    EnterCriticalSection(&g_padLock);
    if (g_padConnected[g_lastPad]) { pad = g_pad[g_lastPad]; have = true; }
    LeaveCriticalSection(&g_padLock);
    if (!g_menuOpen || !have) memset(&pad, 0, sizeof(pad));
    struct { ImGuiKey key; WORD mask; } const buttons[] = {
        {ImGuiKey_GamepadStart, 0x0010}, {ImGuiKey_GamepadBack, 0x0020}, {ImGuiKey_GamepadFaceLeft, 0x4000},
        {ImGuiKey_GamepadFaceRight, 0x2000}, {ImGuiKey_GamepadFaceUp, 0x8000}, {ImGuiKey_GamepadFaceDown, 0x1000},
        {ImGuiKey_GamepadDpadLeft, 0x0004}, {ImGuiKey_GamepadDpadRight, 0x0008}, {ImGuiKey_GamepadDpadUp, 0x0001},
        {ImGuiKey_GamepadDpadDown, 0x0002}, {ImGuiKey_GamepadL1, 0x0100}, {ImGuiKey_GamepadR1, 0x0200},
        {ImGuiKey_GamepadL3, 0x0040}, {ImGuiKey_GamepadR3, 0x0080}};
    for (const auto &b : buttons) io.AddKeyEvent(b.key, (pad.wButtons & b.mask) != 0);
    auto analog = [&io](ImGuiKey key, float value, float lo, float hi) {
        float v = (value - lo) / (hi - lo);
        if (v < 0.0f) v = 0.0f;
        if (v > 1.0f) v = 1.0f;
        io.AddKeyAnalogEvent(key, v > 0.1f, v);
    };
    analog(ImGuiKey_GamepadL2, pad.bLeftTrigger, 30.0f, 255.0f);
    analog(ImGuiKey_GamepadR2, pad.bRightTrigger, 30.0f, 255.0f);
    const float dead = 7849.0f;
    analog(ImGuiKey_GamepadLStickLeft, pad.sThumbLX, -dead, -32768.0f);
    analog(ImGuiKey_GamepadLStickRight, pad.sThumbLX, dead, 32767.0f);
    analog(ImGuiKey_GamepadLStickUp, pad.sThumbLY, dead, 32767.0f);
    analog(ImGuiKey_GamepadLStickDown, pad.sThumbLY, -dead, -32768.0f);
    analog(ImGuiKey_GamepadRStickLeft, pad.sThumbRX, -dead, -32768.0f);
    analog(ImGuiKey_GamepadRStickRight, pad.sThumbRX, dead, 32767.0f);
    analog(ImGuiKey_GamepadRStickUp, pad.sThumbRY, dead, 32767.0f);
    analog(ImGuiKey_GamepadRStickDown, pad.sThumbRY, -dead, -32768.0f);
}

// fallback when PadHook is not in the chain: read the pad ourselves (toggle + navigation, no blocking)
void SelfPoll(XInputGetStateFn poll) {
    static DWORD frames = 0;
    PadState state = {};
    DWORD index = static_cast<DWORD>(g_lastPad);
    bool connected = poll(index, &state) == ERROR_SUCCESS;
    OnPad(index, connected, &state);
    // no pad at that index: look at the next one twice a second (a pad that sends buttons becomes g_lastPad)
    if (!connected && ++frames % 30 == 0) {
        DWORD next = (index + 1 + (frames / 30) % 3) % 4;
        PadState other = {};
        bool found = poll(next, &other) == ERROR_SUCCESS;
        OnPad(next, found, &other);
        if (found) g_lastPad = static_cast<int>(next);
    }
}

void KeyboardToggle() {
    if (!g_toggleKey) return;
    bool down = (GetAsyncKeyState(g_toggleKey) & 0x8000) != 0 && GetForegroundWindow() == g_hwnd;
    if (down && !g_keyHeld) ToggleMenu("key");
    g_keyHeld = down;
}

// ---- pages ----
void Text(const char *fmt, ...) {
    char line[512];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(line, sizeof(line), _TRUNCATE, fmt, ap);
    va_end(ap);
    ImGui::TextUnformatted(line);
}

void PluginLine(const char *name) {
    char file[64], exportName[64];
    _snprintf_s(file, sizeof(file), _TRUNCATE, "%s.asi", name);
    _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", name);
    HMODULE module = GetModuleHandleA(file);
    if (!module) { Text("%-16s not loaded", name); return; }
    typedef const char *(*VersionFn)();
    VersionFn version = reinterpret_cast<VersionFn>(GetProcAddress(module, exportName));
    if (version) {
        ImGui::TextWrapped("%-16s %s", name, version());
    } else {
        Text("%-16s loaded (no %s export)", name, exportName);
    }
}

void PageStatus() {
    ImGui::TextWrapped("%s", kVersion);
    HMODULE exe = GetModuleHandleA(nullptr);
    const IMAGE_DOS_HEADER *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(exe);
    const IMAGE_NT_HEADERS *nt = reinterpret_cast<const IMAGE_NT_HEADERS *>(reinterpret_cast<const BYTE *>(exe) + dos->e_lfanew);
    Text("tru.exe: base 0x%08lx, PE time stamp 0x%08lx, size 0x%lx", reinterpret_cast<DWORD>(exe),
         nt->FileHeader.TimeDateStamp, nt->OptionalHeader.SizeOfImage);
    ImGui::TextWrapped("code checks: base %s, pad %s, d3d9 %s, player %s, post %s, camera %s, frame %s, level %s",
                       g_baseOk ? "ok" : "NO", g_padCodeOk ? "ok" : "NO", g_d3dCodeOk ? "ok" : "NO",
                       g_playerOk ? "ok" : "NO", g_postOk ? "ok" : "NO", g_cameraOk ? "ok" : "NO",
                       g_frameOk ? "ok" : "NO", g_levelOk ? "ok" : "NO");
    Text("in a level: %s; pad read in Present (front end): %s", InLevel() ? "yes" : "no", g_padModeIdle ? "yes" : "no");
    ImGui::Separator();
    ImGui::TextUnformatted("Our plugins");
    PluginLine("TruShadowPower");
    PluginLine("TruDoppelganger");
    PluginLine("TruDlc2Player");
    PluginLine("TruRockVein");
    Text("%-16s %s", "ModLoader", GetModuleHandleA("ModLoader.asi") ? "loaded" : "not loaded");
    ImGui::Separator();
    char owner[MAX_PATH], inner[MAX_PATH];
    DWORD pointer = 0;
    ReadDword(kPadPointer, &pointer);
    ModuleOf(reinterpret_cast<const void *>(pointer), owner, sizeof(owner));
    ModuleOf(reinterpret_cast<const void *>(g_padOriginal), inner, sizeof(inner));
    Text("pad: %s", g_padMode);
    Text("  game calls 0x%08lx (%s), PadHook calls 0x%08lx (%s)", pointer, owner,
         reinterpret_cast<DWORD>(g_padOriginal), inner);
    Text("  last pad %d, input to the game while open: %s", g_lastPad, g_blockInput ? "blocked" : "passed");
    HMODULE d3d9 = GetModuleHandleA("d3d9.dll");
    char d3dPath[MAX_PATH] = "not loaded";
    if (d3d9) GetModuleFileNameA(d3d9, d3dPath, MAX_PATH);
    Text("d3d9: %s", g_d3dMode);
    ImGui::TextWrapped("  d3d9.dll = %s", d3dPath);
    Text("  device 0x%08lx, window 0x%08lx", reinterpret_cast<DWORD>(g_device), reinterpret_cast<DWORD>(g_hwnd));
}

bool ReadLara(float *position, float *rotation, DWORD *instance) {
    DWORD player = 0;
    if (!g_playerOk || !ReadDword(kPlayerPtr, &player) || !player) return false;
    *instance = player;
    return ReadFloats(player + kInstancePosition, position, 3) && ReadFloats(player + kInstanceRotation, rotation, 3);
}

// ---- items: every menu entry has a stable id, callable from the menu and through TruMenuInvoke (TruLink "menu") ----
bool InLevel() {
    DWORD player = 0;
    return g_playerOk && ReadDword(kPlayerPtr, &player) && player != 0;
}

void Out(char *out, size_t size, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(out, size, _TRUNCATE, fmt, ap);
    va_end(ap);
}

// arg: "" toggles, "0" / "1" set; returns the new state
bool BoolArg(const char *arg, bool current) {
    if (!arg || !arg[0]) return !current;
    return atoi(arg) != 0 || _stricmp(arg, "on") == 0 || _stricmp(arg, "true") == 0;
}

void CurrentUnit(char *out, size_t size) {
    out[0] = 0;
    __try {
        const volatile char *name = reinterpret_cast<const volatile char *>(kUnitName);
        size_t i = 0;
        for (; i + 1 < size && i < 63 && name[i]; ++i) out[i] = name[i];
        out[i] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
    }
}

// value getters (any thread, read-only)
void ValMenu(char *o, size_t n) { Out(o, n, "%d", g_menuOpen ? 1 : 0); }
void ValOverlay(char *o, size_t n) { Out(o, n, "%d", g_overlay ? 1 : 0); }
void ValVersion(char *o, size_t n) { Out(o, n, "%s", kVersion); }
void ValHooks(char *o, size_t n) {
    Out(o, n, "pad=%s; d3d9=%s; frontend-pad=%d", g_padMode, g_d3dMode, g_padModeIdle ? 1 : 0);
}
void ValPlayer(char *o, size_t n) {
    float p[3], r[3];
    DWORD instance = 0;
    if (ReadLara(p, r, &instance)) Out(o, n, "%.2f %.2f %.2f rot %.4f %.4f %.4f", p[0], p[1], p[2], r[0], r[1], r[2]);
    else Out(o, n, "-");
}
void ValCamera(char *o, size_t n) {
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Out(o, n, "0x%08lx", camera);
}
void ValCheat(char *o, size_t n) {
    DWORD v = 0;
    ReadDword(kCheatMode, &v);
    Out(o, n, "%lu", v & 0xff);
}
void ValSpeed(char *o, size_t n) { Out(o, n, "%.1f", g_flightSpeed); }
void ValDebugFlag(char *o, size_t n) {
    DWORD v = 0;
    ReadDword(kDebugFlags2, &v);
    Out(o, n, "%d", (v & 0x100) ? 1 : 0);
}
void ValUnit(char *o, size_t n) { CurrentUnit(o, n); if (!o[0]) Out(o, n, "-"); }
void ValLevels(char *o, size_t n) { Out(o, n, "%s", g_levelList); }
void ValTodo(char *o, size_t n) { Out(o, n, "todo"); }

// runners: return true on success, text in out
bool RunMenu(const char *arg, char *o, size_t n) {
    bool open = BoolArg(arg, g_menuOpen != 0);
    if (open != (g_menuOpen != 0)) ToggleMenu("item");
    Out(o, n, "menu.open %d", open ? 1 : 0);
    return true;
}
bool RunOverlay(const char *arg, char *o, size_t n) {
    if (!g_playerOk) { Out(o, n, "player pointer check failed"); return false; }
    bool on = BoolArg(arg, g_overlay != 0);
    InterlockedExchange(&g_overlay, on ? 1 : 0);
    Out(o, n, "overlay.position %d", on ? 1 : 0);
    return true;
}
bool RunCameraMode(const char *arg, char *o, size_t n) {
    if (!g_cameraOk || !g_experimental) { Out(o, n, "camera code not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    char *end = nullptr;
    long mode = strtol(arg ? arg : "", &end, 0);
    if (!arg || !arg[0] || *end || mode < 0 || mode > 15) { Out(o, n, "usage: camera.mode <0..15>"); return false; }
    reinterpret_cast<CameraSetModeFn>(kCameraSetMode)(static_cast<int>(mode));
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Out(o, n, "CAMERA_SetMode(%ld) done, current camera 0x%08lx", mode, camera);
    return true;
}
bool RunCameraRestore(const char *, char *o, size_t n) {
    if (!g_cameraOk || !g_experimental) { Out(o, n, "camera code not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    reinterpret_cast<CameraRestoreFn>(kCameraRestore)(reinterpret_cast<void *>(kCameraManager), 0);
    Out(o, n, "camera restored");
    return true;
}
bool RunCheat(const char *arg, char *o, size_t n) {
    if (!g_postOk || !g_playerOk || !g_experimental) { Out(o, n, "INSTANCE_Post / player not verified / experimental off"); return false; }
    DWORD player = 0;
    if (!ReadDword(kPlayerPtr, &player) || !player) { Out(o, n, "needs a level"); return false; }
    volatile BYTE *cheat = reinterpret_cast<volatile BYTE *>(kCheatMode);
    BYTE value = BoolArg(arg, *cheat != 0) ? 1 : 0;
    *cheat = value;
    // TRLAU Skew.cpp (TR8): message 12 to the player with the new cheatMode value
    reinterpret_cast<InstancePostFn>(kInstancePost)(reinterpret_cast<void *>(player), 12, value);
    g_flight = value != 0;
    Out(o, n, "cheat.flight %u (cheatMode 0x%08lx, message 12 to 0x%08lx)", value, kCheatMode, player);
    return true;
}
bool RunSpeed(const char *arg, char *o, size_t n) {
    float v = arg && arg[0] ? static_cast<float>(atof(arg)) : 0.0f;
    if (!(v > 0.0f && v < 1000.0f)) { Out(o, n, "usage: cheat.speed <0..1000>"); return false; }
    g_flightSpeed = v;
    Out(o, n, "cheat.speed %.1f", v);
    return true;
}
bool RunDebugFlag(const char *arg, char *o, size_t n) {
    if (!g_experimental) { Out(o, n, "experimental off"); return false; }
    volatile DWORD *flags = reinterpret_cast<volatile DWORD *>(kDebugFlags2);
    bool on = BoolArg(arg, (*flags & 0x100) != 0);
    if (on) *flags |= 0x100; else *flags &= ~0x100u;
    Out(o, n, "draw.debugflag %d (debugFlags2 0x%08lx)", on ? 1 : 0, *flags);
    return true;
}
bool LoadUnit(const char *unit, char *o, size_t n) {
    if (!g_levelOk || !g_experimental) { Out(o, n, "level change code not verified / experimental off"); return false; }
    size_t len = unit ? strlen(unit) : 0;
    if (!len || len > 63) { Out(o, n, "usage: level.load <unit name, 1..63 chars>"); return false; }
    for (size_t i = 0; i < len; ++i)
        if (!(isalnum(static_cast<unsigned char>(unit[i])) || unit[i] == '_' || unit[i] == '-')) {
            Out(o, n, "unit name may hold a-z 0-9 _ - only");
            return false;
        }
    DWORD busy = 0;
    ReadDword(kGameTracker + 0xb8, &busy);
    if ((busy >> 8) & 0xff) { Out(o, n, "a level change is already pending (GameTracker+0xb9)"); return false; }
    static char name[64];                    // the game copies it to GameTracker+0x38; keep ours alive anyway
    strncpy_s(name, sizeof(name), unit, _TRUNCATE);
    // GAMELOOP_RequestLevelChangeByName(name, gameTracker, doneType 4) - TRLAU name / signature, doneType 4 as the
    // game's own caller tru+0x1dfb6b
    reinterpret_cast<LevelChangeFn>(kLevelChange)(name, reinterpret_cast<void *>(kGameTracker), 4);
    Out(o, n, "level change to '%s' requested", name);
    if (g_menuOpen) ToggleMenu("level change");
    return true;
}
bool RunLevel(const char *arg, char *o, size_t n) { return LoadUnit(arg, o, n); }
bool RunReload(const char *, char *o, size_t n) {
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    if (!unit[0]) { Out(o, n, "no current unit name"); return false; }
    return LoadUnit(unit, o, n);
}
bool RunTodo(const char *, char *o, size_t n) { Out(o, n, "todo - not implemented in 0.1"); return false; }

struct Item {
    const char *id, *type, *label;
    bool gameThread;                         // runner must run on the game thread (queued)
    void (*value)(char *, size_t);
    bool (*run)(const char *, char *, size_t);
};
const Item kItems[] = {
    {"menu.open", "bool", "menu visible", false, ValMenu, RunMenu},
    {"status.version", "info", "TruMenu version", false, ValVersion, nullptr},
    {"status.hooks", "info", "pad / d3d9 hook state", false, ValHooks, nullptr},
    {"overlay.position", "bool", "Lara position overlay", false, ValOverlay, RunOverlay},
    {"player.position", "info", "Lara position / rotation (needs a level)", false, ValPlayer, nullptr},
    {"camera.current", "info", "current camera object", false, ValCamera, nullptr},
    {"camera.mode", "action", "CAMERA_SetMode(arg 0..15), experimental, needs a level", true, ValCamera, RunCameraMode},
    {"camera.restore", "action", "restore the game camera, needs a level", true, ValCamera, RunCameraRestore},
    {"camera.free", "todo", "own free camera", false, ValTodo, RunTodo},
    {"cheat.flight", "bool", "cheatMode + message 12 (flight), needs a level", true, ValCheat, RunCheat},
    {"cheat.speed", "float", "flight speed per 30 fps frame (RT up / LT down)", false, ValSpeed, RunSpeed},
    {"draw.debugflag", "bool", "GameTracker debugFlags2 0x100", true, ValDebugFlag, RunDebugFlag},
    {"draw.markup", "todo", "own markup / collision drawing", false, ValTodo, RunTodo},
    {"level.current", "info", "unit name at GameTracker+0x38", false, ValUnit, nullptr},
    {"level.list", "info", "preset units ([Levels] List)", false, ValLevels, nullptr},
    {"level.load", "action", "load unit (arg = unit name), experimental", true, ValUnit, RunLevel},
    {"level.reload", "action", "reload the current unit, experimental", true, ValUnit, RunReload},
    {"dev.log", "todo", "re-enabled debug log", false, ValTodo, RunTodo},
};

const Item *FindItem(const char *id) {
    if (!id) return nullptr;
    for (const Item &item : kItems)
        if (_stricmp(item.id, id) == 0) return &item;
    return nullptr;
}

void SetLastAction(const char *id, bool ok, const char *text) {
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s: %s%s", id, ok ? "" : "err ", text);
    Log(ok ? 2 : 1, "item %s", g_lastAction);
}

// game thread: run the queued request
void RunPending() {
    if (!InterlockedCompareExchange(&g_reqPending, 0, 0)) return;
    EnterCriticalSection(&g_reqLock);
    const Item *item = FindItem(g_reqId);
    char text[400] = "";
    bool ok = false;
    if (item && item->run) ok = item->run(g_reqArg, text, sizeof(text));
    else _snprintf_s(text, sizeof(text), _TRUNCATE, "unknown item");
    _snprintf_s(g_reqResult, sizeof(g_reqResult), _TRUNCATE, "%s%s", ok ? "ok " : "err ", text);
    SetLastAction(g_reqId, ok, text);
    InterlockedExchange(&g_reqPending, 0);
    LeaveCriticalSection(&g_reqLock);
    SetEvent(g_reqDone);
}

// queue for the game thread; false if another request is still pending
bool Enqueue(const char *id, const char *arg) {
    EnterCriticalSection(&g_reqLock);
    bool busy = g_reqPending != 0;
    if (!busy) {
        strncpy_s(g_reqId, sizeof(g_reqId), id, _TRUNCATE);
        strncpy_s(g_reqArg, sizeof(g_reqArg), arg ? arg : "", _TRUNCATE);
        g_reqResult[0] = 0;
        ResetEvent(g_reqDone);
        InterlockedExchange(&g_reqPending, 1);
    }
    LeaveCriticalSection(&g_reqLock);
    return !busy;
}

// from the menu (render hook): never waits
void QueueItem(const char *id, const char *arg) {
    const Item *item = FindItem(id);
    if (!item || !item->run) return;
    if (!item->gameThread) {
        char text[400];
        bool ok = item->run(arg, text, sizeof(text));
        SetLastAction(id, ok, text);
        return;
    }
    if (!Enqueue(id, arg)) SetLastAction(id, false, "busy (another request pending)");
    else SetLastAction(id, true, "queued");
}

__declspec(thread) char t_answer[4096];

const char *InvokeItem(const char *id, const char *arg) {
    const Item *item = FindItem(id);
    if (!item) { _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err unknown item '%s'", id ? id : ""); return t_answer; }
    if (!item->run) {
        char value[400];
        item->value(value, sizeof(value));
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok %s %s", item->id, value);
        return t_answer;
    }
    if (!item->gameThread) {
        char text[400];
        bool ok = item->run(arg, text, sizeof(text));
        SetLastAction(item->id, ok, text);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s%s", ok ? "ok " : "err ", text);
        return t_answer;
    }
    if (!Enqueue(item->id, arg)) {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err busy (another request pending)");
        return t_answer;
    }
    if (WaitForSingleObject(g_reqDone, 3000) == WAIT_OBJECT_0 && !g_reqPending) {
        EnterCriticalSection(&g_reqLock);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s", g_reqResult);
        LeaveCriticalSection(&g_reqLock);
    } else {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok queued %s (no game frame within 3 s - runs at the next "
                    "one)", item->id);
    }
    return t_answer;
}

const char *ListItems() {
    size_t used = 0;
    t_answer[0] = 0;
    for (const Item &item : kItems) {
        char value[400];
        item.value(value, sizeof(value));
        int w = _snprintf_s(t_answer + used, sizeof(t_answer) - used, _TRUNCATE, "%s\t%s\t%s\t%s\n", item.id, item.type,
                            value, item.label);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    return t_answer;
}

void PageLevel() {
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    Text("current unit (GameTracker+0x38): %s", unit[0] ? unit : "-");
    if (!g_levelOk || !g_experimental) {
        ImGui::TextUnformatted(g_levelOk ? "(experimental actions off in TruMenu.ini)" : "level change code check failed");
        return;
    }
    // presets from [Levels] List
    char list[sizeof(g_levelList)];
    strncpy_s(list, sizeof(list), g_levelList, _TRUNCATE);
    char *context = nullptr;
    int index = 0;
    for (char *name = strtok_s(list, ", ", &context); name; name = strtok_s(nullptr, ", ", &context), ++index) {
        char label[96];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Load %s##lvl%d", name, index);
        if (ImGui::Button(label)) QueueItem("level.load", name);
    }
    if (unit[0] && ImGui::Button("Reload current unit  [level.reload]")) QueueItem("level.reload", "");
    ImGui::TextWrapped("GAMELOOP_RequestLevelChangeByName 0x%08lx (name, GameTracker, 4). Other units: TruLink "
                       "\"menu level.load <unit>\" or [Levels] List in TruMenu.ini.", kLevelChange);
}

void PageOverlay() {
    bool overlay = g_overlay != 0;
    if (!g_playerOk) ImGui::BeginDisabled();
    if (ImGui::Checkbox("Show Lara's position (top left)", &overlay)) InterlockedExchange(&g_overlay, overlay);
    if (!g_playerOk) ImGui::EndDisabled();
    float p[3], r[3];
    DWORD instance = 0;
    if (ReadLara(p, r, &instance)) {
        Text("player instance 0x%08lx", instance);
        Text("position %.1f  %.1f  %.1f", p[0], p[1], p[2]);
        Text("rotation %.3f  %.3f  %.3f", r[0], r[1], r[2]);
    } else {
        ImGui::TextUnformatted(g_playerOk ? "no player instance (menu / loading)" : "player pointer check failed");
    }
    ImGui::TextWrapped("Source: [0x%08lx] = GameTracker+0xc, instance +0x%lx position / +0x%lx rotation (TRLAU Instance.h).",
                       kPlayerPtr, kInstancePosition, kInstanceRotation);
}

void Todo(const char *text) {
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.8f, 0.3f, 1.0f));
    ImGui::TextWrapped("TODO: %s", text);
    ImGui::PopStyleColor();
}

void PageCamera() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    Todo("own free camera (move / rotate the camera transform with the sticks) - needs the camera struct offsets.");
    ImGui::TextWrapped("Known: CameraManager 0x%08lx, current camera [0x%08lx]; CAMERA_SetMode 0x%08lx; restore 0x%08lx "
                       "(thiscall manager). Modes: 5 FreeCamera, 9 ObjectDebugCamera, 10 CheatCamera; TRLAU enters its "
                       "free camera with mode 11.", kCameraManager, kCurrentCamera, kCameraSetMode, kCameraRestore);
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Text("current camera 0x%08lx", camera);
    if (!g_experimental || !g_cameraOk) {
        ImGui::TextUnformatted(g_cameraOk ? "(experimental actions off in TruMenu.ini)" : "camera code check failed");
        return;
    }
    ImGui::TextUnformatted("Experimental (runs on the game thread when the menu is closed or next frame):");
    ImGui::SliderInt("mode", &g_cameraModeChoice, 0, 12);
    char arg[16];
    _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", g_cameraModeChoice);
    if (ImGui::Button("CAMERA_SetMode(mode)  [camera.mode]")) QueueItem("camera.mode", arg);
    if (ImGui::Button("Restore game camera  [camera.restore]")) QueueItem("camera.restore", "");
}

void PageCheat() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    BYTE cheat = 0;
    DWORD value = 0;
    if (ReadDword(kCheatMode & ~3u, &value)) cheat = static_cast<BYTE>(value >> ((kCheatMode & 3) * 8));
    Text("GameTracker.cheatMode [0x%08lx] = %u", kCheatMode, cheat);
    if (!g_experimental || !g_postOk || !g_playerOk) {
        ImGui::TextUnformatted(g_postOk && g_playerOk ? "(experimental actions off in TruMenu.ini)"
                                                      : "INSTANCE_Post / player check failed");
        return;
    }
    if (ImGui::Button(cheat ? "Cheat / flight OFF  [cheat.flight]" : "Cheat / flight ON  [cheat.flight]"))
        QueueItem("cheat.flight", "");
    ImGui::TextWrapped("Toggles cheatMode and posts message 12 to the player (TRLAU Skew.cpp). While on and the menu "
                       "is closed: RT moves Lara up, LT down (speed %.0f per 30 fps frame, [Cheat] FlightSpeed).",
                       g_flightSpeed);
    Todo("PSCCF_IsInCheatMode (bit 30 of [[0xfadb58]+0x68], player message 0x9f) is a different switch - not used yet.");
}

void PageMarkup() {
    DWORD flags = 0;
    ReadDword(kDebugFlags2, &flags);
    Text("GameTracker debugFlags2 [0x%08lx] = 0x%08lx", kDebugFlags2, flags);
    if (g_experimental && ImGui::Button("Toggle debugFlags2 0x100  [draw.debugflag]")) QueueItem("draw.debugflag", "");
    Todo("own markup / collision drawing (TRLAU draws markup itself; the retail draw paths are mostly compiled out).");
}

void DrawMenu() {
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 40.0f, vp->WorkPos.y + 40.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(vp->WorkSize.x * 0.5f, vp->WorkSize.y * 0.7f), ImGuiCond_FirstUseEver);
    if (InterlockedExchange(&g_menuJustOpened, 0)) ImGui::SetNextWindowFocus();
    bool open = true;
    if (ImGui::Begin("TruMenu  (L3 + R3 closes)", &open, ImGuiWindowFlags_NoCollapse)) {
        if (ImGui::CollapsingHeader("Status", ImGuiTreeNodeFlags_DefaultOpen)) PageStatus();
        if (ImGui::CollapsingHeader("Overlay: Lara's position")) PageOverlay();
        if (ImGui::CollapsingHeader("Free camera")) PageCamera();
        if (ImGui::CollapsingHeader("Cheat / flight")) PageCheat();
        if (ImGui::CollapsingHeader("Markup / collision draw")) PageMarkup();
        if (ImGui::CollapsingHeader("Level select")) PageLevel();
        if (ImGui::CollapsingHeader("Dev channel")) {
            ImGui::TextWrapped("tru.exe has no developer channel (TCP 9264 is FMOD's profiler).");
            Todo("re-enable the compiled-out log stub 0x6457a0 (filtered by channel id) and show it here.");
        }
        ImGui::Separator();
        Text("last action: %s", g_lastAction);
        if (ImGui::Button("Close menu")) open = false;
    }
    ImGui::End();
    if (!open && g_menuOpen) ToggleMenu("close button");
}

void DrawOverlay() {
    float p[3], r[3];
    DWORD instance = 0;
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 10.0f, vp->WorkPos.y + 10.0f), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.4f);
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruMenuOverlay", nullptr, flags)) {
        if (ReadLara(p, r, &instance))
            Text("Lara  %.0f  %.0f  %.0f   rot %.2f", p[0], p[1], p[2], r[2]);
        else
            ImGui::TextUnformatted("Lara  -");
    }
    ImGui::End();
}

void Render(IDirect3DDevice9 *device) {
    // front end / loading: if the game has not polled the pad slot for 250 ms, read the pad here (toggle +
    // navigation) and run queued requests from this hook (the game's Present call)
    bool padIdle = GetTickCount() - g_lastPadHookTick > 250;
    XInputGetStateFn poll = g_selfPoll ? g_selfPoll : (padIdle ? RealXInput() : nullptr);
    if (poll) SelfPoll(poll);
    if (padIdle != g_padModeIdle) {
        g_padModeIdle = padIdle;
        Log(2, padIdle ? "pad: slot not polled - reading the pad in Present" : "pad: slot polled again");
    }
    if (padIdle && g_reqPending) RunPending();
    KeyboardToggle();
    if (!g_menuOpen && !g_overlay) return;
    if (g_imguiFailed) return;
    if (!g_imguiReady) {
        g_imguiReady = InitImGui(device);
        if (!g_imguiReady) { g_imguiFailed = true; return; }
    } else if (device != g_imguiDevice) {
        Log(1, "imgui: device changed 0x%08lx -> 0x%08lx", reinterpret_cast<DWORD>(g_imguiDevice),
            reinterpret_cast<DWORD>(device));
        ImGui_ImplDX9_Shutdown();
        ImGui_ImplDX9_Init(device);
        g_imguiDevice = device;
    }
    ImGuiIO &io = ImGui::GetIO();
    io.MouseDrawCursor = g_menuOpen != 0;
    ImGui_ImplDX9_NewFrame();
    ImGui_ImplWin32_NewFrame();
    // draw in back-buffer pixels: the window client size can differ (windowed proxies scale the back buffer)
    IDirect3DSurface9 *back = nullptr;
    if (SUCCEEDED(device->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back)) && back) {
        D3DSURFACE_DESC desc = {};
        // (mouse positions stay in client pixels - with a scaling proxy the mouse is off; the pad is unaffected)
        if (SUCCEEDED(back->GetDesc(&desc)) && desc.Width && desc.Height)
            io.DisplaySize = ImVec2(static_cast<float>(desc.Width), static_cast<float>(desc.Height));
        back->Release();
    }
    FeedGamepad(io);
    ImGui::NewFrame();
    if (g_overlay) DrawOverlay();
    if (g_menuOpen) DrawMenu();
    ImGui::EndFrame();
    if (SUCCEEDED(device->BeginScene())) {
        ImGui::Render();
        ImGui_ImplDX9_RenderDrawData(ImGui::GetDrawData());
        device->EndScene();
    }
}

HRESULT STDMETHODCALLTYPE PresentHook(IDirect3DDevice9 *device, const RECT *source, const RECT *dest, HWND window,
                                      const RGNDATA *dirty) {
    Render(device);
    return g_presentOriginal(device, source, dest, window, dirty);
}

HRESULT STDMETHODCALLTYPE ResetHook(IDirect3DDevice9 *device, D3DPRESENT_PARAMETERS *params) {
    if (g_imguiReady) ImGui_ImplDX9_InvalidateDeviceObjects();
    HRESULT hr = g_resetOriginal(device, params);
    Log(hr < 0 ? 0 : 3, "d3d9: Reset 0x%08lx", static_cast<DWORD>(hr));
    return hr;                               // device objects are re-created by the next ImGui_ImplDX9_NewFrame
}

void HookDevice(IDirect3DDevice9 *device) {
    void **vtable = nullptr;
    if (!ReadDword(reinterpret_cast<DWORD>(device), reinterpret_cast<DWORD *>(&vtable)) || !vtable) return;
    PatchVtable(vtable, 16, reinterpret_cast<void *>(&ResetHook), reinterpret_cast<void *volatile *>(&g_resetOriginal),
                "Reset");
    PatchVtable(vtable, 17, reinterpret_cast<void *>(&PresentHook),
                reinterpret_cast<void *volatile *>(&g_presentOriginal), "Present");
    g_device = device;
    g_d3dMode = "Present / Reset hooked on the game's device";
}

// import slot of GetProcAddress: only when it holds a function inside a loaded module (resolved imports)
bool PatchGetProc() {
    DWORD current = 0;
    if (!ReadDword(kGetProcSlot, &current) || !current) return false;
    if (current == reinterpret_cast<DWORD>(&GetProcHook)) return true;
    char owner[MAX_PATH];
    ModuleOf(reinterpret_cast<const void *>(current), owner, sizeof(owner));
    if (owner[0] == '?') return false;
    g_getProcOriginal = reinterpret_cast<GetProcAddressFn>(current);
    if (!WriteDword(kGetProcSlot, reinterpret_cast<DWORD>(&GetProcHook))) {
        Log(0, "pad: VirtualProtect on the import slot failed (%lu) - pad filter off", GetLastError());
        g_padMode = "import slot not writable";
        return true;
    }
    g_padMode = "import filter set, waiting for the game to load XInput";
    Log(1, "pad: import slot 0x%08lx (GetProcAddress 0x%08lx in %s) filtered", kGetProcSlot, current, owner);
    return true;
}

// the pointer was already filled when we came (late load): take it over only if nobody wrapped it yet
// (hook once; if another plugin wrapped it first we go on top of that wrapper - the re-entry guard in PadHook keeps a
// wrapper that re-wraps us from recursing)
bool PlacePadHook(DWORD current, const char *mode) {
    char owner[MAX_PATH];
    ModuleOf(reinterpret_cast<const void *>(current), owner, sizeof(owner));
    if (IsXInputModule(reinterpret_cast<const void *>(current))) g_padReal = reinterpret_cast<XInputGetStateFn>(current);
    g_padOriginal = reinterpret_cast<XInputGetStateFn>(current);
    if (InterlockedCompareExchange(reinterpret_cast<volatile LONG *>(kPadPointer),
                                   static_cast<LONG>(reinterpret_cast<DWORD>(&PadHook)),
                                   static_cast<LONG>(current)) != static_cast<LONG>(current))
        return false;
    g_padMode = mode;
    Log(1, "pad: pointer 0x%08lx held 0x%08lx (%s) - PadHook placed (%s)", kPadPointer, current, owner, mode);
    return true;
}

void TakePointerLate(DWORD current) {
    if (current == reinterpret_cast<DWORD>(&PadHook) || PlacePadHook(current, "PadHook set on the pointer (late load)"))
        return;
    // could not swap (the slot changed under us): read the pad ourselves - toggle and navigation work, no blocking
    g_selfPoll = RealXInput();
    g_padMode = "pointer busy - own reads, game input NOT blocked";
    Log(0, "pad: pointer 0x%08lx changed while hooking - menu reads the pad itself, input to the game is not blocked",
        kPadPointer);
}

// chaining rule: re-hook only when the slot points into the real XInputGetState again (game re-loaded XInput)
void CheckPadSlot() {
    DWORD current = 0;
    if (!ReadDword(kPadPointer, &current) || !current) return;
    if (IsXInputModule(reinterpret_cast<const void *>(current)))
        PlacePadHook(current, "PadHook re-placed (slot pointed to XInput again)");
}

// pad setup: the import filter if the pointer is still empty, else the late path; false = try again later
bool SetupPad() {
    DWORD pointer = 0;
    if (ReadDword(kPadPointer, &pointer) && pointer) {
        TakePointerLate(pointer);
        return true;
    }
    return PatchGetProc();
}

DWORD WINAPI WorkerThread(LPVOID) {
    bool padDone = !g_padCodeOk || g_padSetupDone;
    while (!g_stop) {
        if (!padDone) padDone = SetupPad();
        else if (g_padCodeOk && !g_selfPoll) CheckPadSlot();
        if (g_d3dCodeOk) {
            DWORD manager = 0, device = 0;
            if (ReadDword(kDeviceManager, &manager) && manager && ReadDword(manager + kDeviceField, &device) && device &&
                device != reinterpret_cast<DWORD>(g_device))
                HookDevice(reinterpret_cast<IDirect3DDevice9 *>(device));
        }
        Sleep(g_device ? 1000 : 50);
    }
    return 0;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH], text[32];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruMenu.ini", dir);
    g_enabled = GetPrivateProfileIntA("Menu", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Menu", "LogLevel", 1, ini);
    g_toggleButtons = static_cast<WORD>(GetPrivateProfileIntA("Menu", "ToggleButtons", kPadL3 | kPadR3, ini));
    if (!g_toggleButtons) g_toggleButtons = kPadL3 | kPadR3;
    g_toggleKey = GetPrivateProfileIntA("Menu", "ToggleKey", 0, ini);
    GetPrivateProfileStringA("Menu", "Scale", "1.5", text, sizeof(text), ini);
    g_scale = static_cast<float>(atof(text));
    if (!(g_scale >= 0.5f && g_scale <= 4.0f)) g_scale = 1.5f;
    g_overlayAtStart = GetPrivateProfileIntA("Menu", "Overlay", 0, ini);
    g_blockInput = GetPrivateProfileIntA("Pad", "BlockInput", 1, ini);
    g_experimental = GetPrivateProfileIntA("Cheat", "Experimental", 1, ini);
    GetPrivateProfileStringA("Cheat", "FlightSpeed", "20", text, sizeof(text), ini);
    g_flightSpeed = static_cast<float>(atof(text));
    if (!(g_flightSpeed > 0.0f && g_flightSpeed < 1000.0f)) g_flightSpeed = 20.0f;
    GetPrivateProfileStringA("Levels", "List", "dlc_level1_start,dlc_level2_start", g_levelList, sizeof(g_levelList), ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruMenu.log", dir);
    ReadOptions(dir);
    Log(1, "%s loaded (enabled %d, toggle 0x%04x, key %d, block %d, scale %.2f, experimental %d)", kVersion, g_enabled,
        g_toggleButtons, g_toggleKey, g_blockInput, g_scale, g_experimental);
    if (!g_enabled) { Log(1, "disabled by TruMenu.ini - nothing hooked"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    g_baseOk = base == kImageBase;
    if (!g_baseOk) { Log(0, "image base 0x%08lx, expected 0x%08lx - not hooked", base, kImageBase); return; }
    g_padCodeOk = HexBytesAt(kPadLoader, kPadLoaderBytes) && HexBytesAt(kPadCallSite, kPadCallBytes) &&
                  HexBytesAt(kXInputName, "58496e7075744765745374617465 00");
    if (!g_padCodeOk) Log(0, "pad: XInput loader 0x%08lx / poll 0x%08lx do not match - pad hook off (keyboard toggle "
                             "only)", kPadLoader, kPadCallSite);
    g_d3dCodeOk = HexBytesAt(kD3dCreate, kD3dCreateBytes) && HexBytesAt(kD3dStore, kD3dStoreBytes) &&
                  HexBytesAt(kCreateDeviceCall, kCreateDeviceBytes) && HexBytesAt(kCreateDeviceCall2, kCreateDeviceBytes2);
    if (!g_d3dCodeOk) Log(0, "d3d9: device manager code 0x%08lx does not match - no menu drawing", kD3dCreate);
    g_playerOk = HexBytesAt(kPlayerReader, kPlayerReaderBytes);
    g_postOk = HexBytesAt(kInstancePost, kInstancePostBytes);
    g_cameraOk = HexBytesAt(kCameraSetMode, kCameraSetModeBytes) && HexBytesAt(kCameraRestore, kCameraRestoreBytes);
    g_levelOk = HexBytesAt(kLevelChange, kLevelChangeBytes) && HexBytesAt(kLevelNameCopy, "83c738 8bd7 8bc6 2bd6");
    g_frameOk = HexBytesAt(kFrameStore, kFrameStoreBytes);
    Log(1, "code checks: pad %d, d3d9 %d, player %d, INSTANCE_Post %d, camera %d, frame time %d, level change %d", g_padCodeOk,
        g_d3dCodeOk, g_playerOk, g_postOk, g_cameraOk, g_frameOk, g_levelOk);
    g_overlay = g_overlayAtStart && g_playerOk;
    // set the import filter now if the imports are resolved already (normal case), else the worker retries
    if (g_padCodeOk) {
        g_padSetupDone = SetupPad();
        if (!g_padSetupDone) Log(2, "pad: import slot not resolved yet - worker retries");
    }
    HANDLE thread = CreateThread(nullptr, 0, WorkerThread, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
    else Log(0, "CreateThread failed (%lu) - no menu", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        InitializeCriticalSection(&g_padLock);
        InitializeCriticalSection(&g_reqLock);
        g_reqDone = CreateEventA(nullptr, TRUE, FALSE, nullptr);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_stop = 1;
    }
    return TRUE;
}

// exported so the loader / tools / other plugins can identify the plugin
extern "C" __declspec(dllexport) const char *TruMenuVersion() { return kVersion; }

// item interface for other plugins / tools (TruLink "menu"): one line per item "id<TAB>type<TAB>value<TAB>label\n".
// The returned text lives in a buffer of the calling thread, valid until that thread's next call.
extern "C" __declspec(dllexport) const char *__cdecl TruMenuList() { return ListItems(); }

// runs item <id> with <arg> ("" = toggle / default). Items that touch the game run on the game thread: the call
// waits up to 3 s for the next game frame and returns "ok ..." / "err ...".
extern "C" __declspec(dllexport) const char *__cdecl TruMenuInvoke(const char *id, const char *arg) {
    return InvokeItem(id, arg);
}
