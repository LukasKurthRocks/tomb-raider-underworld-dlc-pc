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
//   d3d9   The game's device manager is [0x00ad75e4] (created at tru+0x1239c0), its IDirect3DDevice9 at +0x20 (out
//          parameter of the CreateDevice call tru+0x122736; +0x208 are the present parameters). A worker thread waits for that device and patches the
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

const char *const kVersion = "TruMenu 0.5 (TO TEST steps / checks / toggles + test.export; 0.4: TO TEST checklist over "
                             "TruLink, log collapse / filters / rate limit, weapon "
                             "slots, ammo fill, gear give; debug menu: Crystal's original developer menu from the exe's "
                             "tables, time / player / HUD, instances, live outfit switch, log page + overlay, videos, "
                             "status, outfits, level select, Lara position overlay, cheat / camera; items callable by id)";

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
// CreateDevice(adapter, type, [esi+0x14] window, [esi+0x248] flags, esi+0x208 present params, esi+0x20 ppDevice);
// +0x208 holds the present parameters (1920 / 1080 / format 0x15 seen live 31.10.), the device is at +0x20
const DWORD kCreateDeviceCall = 0x0052270a;
const char *const kCreateDeviceBytes = "8d6e20 55";            // lea ebp, [esi+0x20]; push ebp (ppDevice)
const DWORD kCreateDeviceCall2 = 0x00522733;
const char *const kCreateDeviceBytes2 = "8b4a40 ffd1";         // mov ecx, [edx+0x40]; call ecx (IDirect3D9 slot 16)
const DWORD kDeviceManager = 0x00ad75e4;
const DWORD kDeviceField = 0x20;
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
// costume / game data (0.2; read from the PC tru.exe with tools/pe_dis.py, README "Outfits")
const DWORD kGameDataPtr = 0x00c59264;      // pointer to the game data (re-allocated by the new-game reset 0x556940)
const DWORD kGdMode = 0x1f4;                // u16: 0 = the level load reads +0x20c, else +0x210
const DWORD kGdChosen0 = 0x20c, kGdChosen1 = 0x20e, kGdChosen2 = 0x210;   // u16 chosen costume (object id)
const DWORD kLevelLoadChoice = 0x005de2d6;  // GAMELOOP_LevelLoadAndInit tru+0x1de2b0: chosen costume by +0x1f4
const char *const kLevelLoadChoiceBytes = "a16492c500 56 33f6 6639b0f4010000 7409 0fb78010020000 eb07 0fb7800c020000";
const DWORD kResetCostume = 0x00556abe;     // new-game reset (PC partner of TU 0x821fe9a8): +0x210 / +0x20e / +0x20c = 0
const char *const kResetCostumeBytes = "66899910020000 8b156492c500 66899a0e020000 a16492c500 6689980c020000";
const DWORD kSaveCostume = 0x00555cb1;      // game state save: word [game data +0x20c] = word [0xe7f1c8]
const char *const kSaveCostumeBytes = "66a1c8f1e700 6689820c020000";
const DWORD kCostumeNow = 0x00e7f1c8;       // costume object id set by the level load (= the player object)
const DWORD kObjNames = 0x00db94d0;         // pointer: +0 count, name of object id n at +n*8 (objectlist.txt)
const DWORD kNameLookup = 0x005bf770;       // name -> object id over [0xdb94d0] (0 = none)
const char *const kNameLookupBytes = "8b0dd094db00 56 33f6 3931 57 7e27 8b7c240c 8b44f108";
const DWORD kCostumeValid = 0x005c54e0;     // bool cdecl(id): id <= count and <name>.drm exists (tail call 0x5bf7b0)
const char *const kCostumeValidBytes = "8b442404 8b0dd094db00 3b01 7e03 32c0 c3 8b04c1";
const DWORD kTypeLookup = 0x005bf121;       // cmp [type table], esi in the type-by-name lookup tru+0x1bf0e0
const DWORD kTypeTableOrig = 0x008aba28;    // player type table {name, init, f2..f6}; TruDlc2Player may move it
const DWORD kPlayerF2 = 0x007228e0;         // f2 of every player record (TruDlc2Player's record has it too)
const DWORD kUnitId = 0x00e7f148;           // GameTracker +0xc0 current stream unit id (read at tru+0x1de379)
const DWORD kUnitLookup = 0x005c1b50;       // stream unit table 0xdbab40, 0xd8 per unit, +0 id, +4 state 2, +8 data
const char *const kUnitLookupBytes = "56 8b742408 33c0 33d2 b940abdb00 8bff 80790402 7504 3931 7413 81c1d8000000 83c201"
                                     " 81f940c6db00";
const DWORD kStreamUnits = 0x00dbab40, kStreamUnitsEnd = 0x00dbc640, kStreamUnitSize = 0xd8;
const DWORD kDefaultCostume = 0x005de379;   // unit default costume: [[unit+8]+0x70]+0x294 (u16 object id)
const char *const kDefaultCostumeBytes = "8b0d48f1e700 51 e8cb37feff 8b5008 8b4270 0fb78094020000";
const DWORD kObjectTable = 0x00db7400;      // 0xcc entries of 0x24: +8 object, +0xc s16 id, +0xe u16 state (TruLink)
const int kObjectEntries = 0xcc;
typedef bool(__cdecl *CostumeValidFn)(int id);

// ---- options (TruMenu.ini) ----
// 0.3: every key with its default and comment in one table. ReadOptions takes the defaults from here, settings.reset
// writes TruMenu.ini from it (DefaultIniText), and the shipped src/asi/TruMenu/TruMenu.ini is exactly that text
// (keep both in step; a '\n' in a comment starts a new "; " line).
struct OptDef { const char *section, *key, *def, *comment; };
const OptDef kOpts[] = {
    {"Menu", "Enabled", "1", "0 = load but hook nothing"},
    {"Menu", "LogLevel", "1", "0 errors, 1 info, 2 every menu toggle / action, 3 debug - TruMenu.log next to tru.exe"},
    {"Menu", "ToggleButtons", "192", "XInput buttons that open / close the menu together: 0x0040 L3 + 0x0080 R3 = 192 (0x00C0)"},
    {"Menu", "ToggleKey", "0", "keyboard key that also opens / closes the menu (virtual key code, e.g. 119 = F8); 0 = off"},
    {"Menu", "Scale", "1.5", "size of the menu (font and spacing), 0.5 .. 4"},
    {"Menu", "Overlay", "0", "1 = show the Lara position overlay from the start"},
    {"Pad", "BlockInput", "1", "1 = the game gets a neutral pad while the menu is open; 0 = the game sees the pad as well"},
    {"Cheat", "Experimental", "1", "1 = show the experimental actions (cheat / flight, camera mode, level load, costumes, "
                                   "developer menu rows, time /\nplayer / instance / video items); 0 = read-only"},
    {"Cheat", "FlightSpeed", "20", "flight: units per 30 fps frame at full trigger (RT up, LT down) while cheat mode is on"},
    {"Levels", "List", "dlc_level1_start,dlc_level2_start", "units offered as buttons on the Level select page (comma list)"},
    {"Log", "Overlay", "0", "1 = log lines (Tru*.log tails, script prints) in the bottom-left corner from the start"},
    {"Log", "Lines", "12", "lines on the Debug / Log page and in the overlay, 1 .. 64"},
    {"Log", "Script", "0", "1 = redirect the game's 8 script print / log natives to the log page from the start (patches 5 "
                           "bytes each)"},
    {"Log", "Collapse", "1", "1 = repeated lines (same source, same text after the time stamp) become one line \"text x42 "
                             "(17:09:02-17:09:33)\""},
    {"Log", "HideLinkReads", "1", "1 = drop TruLink's echo of read / scan / watch / ping commands and of menu reads (info "
                                  "items such as status.*,\ntest.list) - the lines never enter the log page"},
    {"Log", "MinLevel", "0", "lines shown on the page / overlay: 0 all, 1 warnings and errors, 2 errors only"},
    {"Log", "MaxLinesPerSecond", "40", "at most this many new lines per source and second (more are dropped and counted); "
                                       "0 = no limit"},
    {"Favorites", "Ids", "", "item ids on the \"Quick access / Favourites\" page (comma list); empty = default list. Y on an "
                             "item in the menu\npins / unpins it and rewrites this line (TruLink: menu fav.add <id> / "
                             "fav.del <id> / fav.list)"},
};
const char *const kIniHeader = "TruMenu.asi options - put next to tru.exe together with TruMenu.asi (optional; defaults below)";

const char *OptDefault(const char *section, const char *key) {
    for (const OptDef &o : kOpts)
        if (_stricmp(o.section, section) == 0 && _stricmp(o.key, key) == 0) return o.def;
    return "";
}
int OptInt(const char *ini, const char *section, const char *key) {
    return static_cast<int>(GetPrivateProfileIntA(section, key, atoi(OptDefault(section, key)), ini));
}
void OptString(const char *ini, const char *section, const char *key, char *out, DWORD size) {
    GetPrivateProfileStringA(section, key, OptDefault(section, key), out, size, ini);
}

int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 actions, 3 debug
WORD g_toggleButtons = kPadL3 | kPadR3;
int g_toggleKey = 0;                    // virtual key (e.g. 119 = F8), 0 = off
int g_blockInput = 1;
float g_scale = 1.5f;
int g_overlayAtStart = 0;
int g_logOverlayAtStart = 0, g_logLinesAtStart = 12, g_scriptLogAtStart = 0;   // 0.3 [Log]
volatile LONG g_logCollapse = 1, g_logHideReads = 1;                         // 0.4 [Log] Collapse / HideLinkReads
int g_logMinLevel = 0, g_logRate = 40;                                       // 0.4 [Log] MinLevel / MaxLinesPerSecond
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
volatile LONG g_testFocus = 0;          // 0.4: a TO TEST row had the nav focus last frame (X / Y go to the row)
volatile LONG g_testX = 0, g_testY = 0; // 0.4: X / Y pressed while a row had the focus (edges, consumed by the page)

bool g_levelOk = false;
bool g_baseOk = false, g_padCodeOk = false, g_d3dCodeOk = false, g_playerOk = false, g_postOk = false,
     g_cameraOk = false, g_frameOk = false;
bool g_costumeOk = false;               // level-load choice, reset, name table, validator, type table checked
bool g_unitOk = false;                  // stream unit table / unit default costume checked
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
char g_reqId[64], g_reqArg[160], g_reqResult[1024];
char g_lastAction[1024] = "none";
volatile DWORD g_lastPadHookTick = 0;
bool g_flight = false;                  // our view of GameTracker.cheatMode after our own toggle
int g_cameraModeChoice = 11;
char g_levelList[1024] = "";            // [Levels] List (comma separated unit names)
char g_iniPath[MAX_PATH] = "";
char g_favs[1024] = "";                 // 0.3 [Favorites] Ids (comma separated item ids)
CRITICAL_SECTION g_favLock;
const char *const kFavDefault = "player.invincible,player.health,time.scale,time.pause,level.reload,camera.free,"
                                "overlay.position,log.overlay,costume.next";

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
void WeaponsTick();    // 0.3 costume switch: player message 35 a frame later
void InvincibleTick(); // 0.3 player.invincible: health = MaxHealth once per game frame
void LogTailTick();    // 0.3 log page: tail Tru*.log once per second (worker thread)

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
        WeaponsTick();
        InvincibleTick();
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
    // 0.4 TO TEST: while a row has the focus, X and Y belong to the row (fail / skip). ImGui would otherwise toggle its
    // menu layer on X and activate the row on Y (= OK). Held until released, also if the focus moves meanwhile.
    static WORD rowOwned = 0, rowHeld = 0;
    WORD xy = pad.wButtons & 0xC000;
    if (g_testFocus) rowOwned |= static_cast<WORD>(xy & ~rowHeld);
    WORD pressed = static_cast<WORD>(xy & ~rowHeld & rowOwned);
    if (pressed & 0x4000) InterlockedExchange(&g_testX, 1);
    if (pressed & 0x8000) InterlockedExchange(&g_testY, 1);
    rowHeld = xy;
    rowOwned &= xy;                          // released buttons go back to ImGui
    pad.wButtons &= static_cast<WORD>(~rowOwned);
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

void Status03Line();                    // 0.3 code checks line, defined with the 0.3 pages
void ValStatusUnit(char *o, size_t n);  // 0.2 helpers, defined with the items below
void ValCostume(char *o, size_t n);
void PlayerInfo(char *o, size_t n);
const char *GameState();

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
    ImGui::TextWrapped("costume %s, unit table %s", g_costumeOk ? "ok" : "NO", g_unitOk ? "ok" : "NO");
    Status03Line();
    ImGui::Separator();
    char line[1024];
    ValStatusUnit(line, sizeof(line));
    ImGui::TextWrapped("unit: %s   [status.unit]", line);
    ImGui::TextWrapped("state: %s   [status.state]", GameState());
    ValCostume(line, sizeof(line));
    ImGui::TextWrapped("costume: %s   [status.costume]", line);
    PlayerInfo(line, sizeof(line));
    ImGui::TextWrapped("player: %s   [status.player]", line);
    ImGui::Separator();
    ImGui::TextUnformatted("Our plugins   [status.plugins]");
    PluginLine("TruShadowPower");
    PluginLine("TruDoppelganger");
    PluginLine("TruDlc2Player");
    PluginLine("TruRockVein");
    PluginLine("TruLink");
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

// ---- 0.2: units, game data, costumes (read-only helpers, any thread) ----
// playable units of the PC unit list tr8/pc-w/unitlist.txt (the list the game loads; = installed mods list),
// grouped by tools/menu_unit_table.py: base game by unit prefix l1_ .. l7_ (l7_* units sit in levels\l5), DLC 1 =
// dlc\dlc_level1, DLC 2 = dlc\dlc_level2, DLC 3-6 start units. Containers / cine / costume units are not offered.
struct UnitRow { const char *group, *unit, *path; };
const UnitRow kUnits[] = {
    {"Base game l1", "l1_baldrs_hall", "levels\\l1\\l1_baldrs_hall"},
    {"Base game l1", "l1_baldrs_sideroom", "levels\\l1\\l1_baldrs_sideroom"},
    {"Base game l1", "l1_baldrs_tomb", "levels\\l1\\l1_baldrs_tomb"},
    {"Base game l1", "l1_baldrsstairs_a", "levels\\l1\\l1_baldrsstairs_a"},
    {"Base game l1", "l1_baldrsstairs_b", "levels\\l1\\l1_baldrsstairs_b"},
    {"Base game l1", "l1_cine_ship_sinking", "levels\\l1\\l1_cine_ship_sinking"},
    {"Base game l1", "l1_cineseatop", "levels\\l1\\l1_cineseatop"},
    {"Base game l1", "l1_kraken_entrance", "levels\\l1\\l1_kraken_entrance"},
    {"Base game l1", "l1_kraken_room", "levels\\l1\\l1_kraken_room"},
    {"Base game l1", "l1_krakenstairs_a", "levels\\l1\\l1_krakenstairs_a"},
    {"Base game l1", "l1_krakenstairs_b", "levels\\l1\\l1_krakenstairs_b"},
    {"Base game l1", "l1_norse_hallway_a", "levels\\l1\\l1_norse_hallway_a"},
    {"Base game l1", "l1_rutlands_ship_m1", "levels\\l1\\l1_rutlands_ship_m1"},
    {"Base game l1", "l1_seafloor", "levels\\l1\\l1_seafloor"},
    {"Base game l1", "l1_seatop", "levels\\l1\\l1_seatop"},
    {"Base game l1", "l1_ship_engine_hall", "levels\\l1\\l1_ship\\l1_ship_engine_hall"},
    {"Base game l1", "l1_ship_exterior", "levels\\l1\\l1_ship\\l1_ship_exterior"},
    {"Base game l1", "l1_ship_lower_hallway", "levels\\l1\\l1_ship\\l1_ship_lower_hallway"},
    {"Base game l1", "l1_ship_natla_room", "levels\\l1\\l1_ship\\l1_ship_natla_room"},
    {"Base game l1", "l1_ship_sinking_hall", "levels\\l1\\l1_ship\\l1_ship_sinking_hall"},
    {"Base game l1", "l1_ship_upper_hallway", "levels\\l1\\l1_ship\\l1_ship_upper_hallway"},
    {"Base game l1", "l1_ship_upper_hallway_a", "levels\\l1\\l1_ship\\l1_ship_upper_hallway_a"},
    {"Base game l1", "l1_ship_upper_hallway_b", "levels\\l1\\l1_ship\\l1_ship_upper_hallway_b"},
    {"Base game l2", "l2_cliffclimb", "levels\\l2\\l2_cliffclimb"},
    {"Base game l2", "l2_cliffhall", "levels\\l2\\l2_cliffhall"},
    {"Base game l2", "l2_cliffhall_b", "levels\\l2\\l2_cliffhall_b"},
    {"Base game l2", "l2_flushtunnel", "levels\\l2\\l2_flushtunnel"},
    {"Base game l2", "l2_hubhall", "levels\\l2\\l2_hubhall"},
    {"Base game l2", "l2_junglehub", "levels\\l2\\l2_junglehub"},
    {"Base game l2", "l2_mapconnector", "levels\\l2\\l2_mapconnector"},
    {"Base game l2", "l2_maproom", "levels\\l2\\l2_maproom"},
    {"Base game l2", "l2_norsehall", "levels\\l2\\l2_norsehall"},
    {"Base game l2", "l2_norsehub", "levels\\l2\\l2_norsehub"},
    {"Base game l2", "l2_puzzleconnector", "levels\\l2\\l2_puzzleconnector"},
    {"Base game l2", "l2_puzzleroom", "levels\\l2\\l2_puzzleroom"},
    {"Base game l2", "l2_shrineroom", "levels\\l2\\l2_shrineroom"},
    {"Base game l2", "l2_towerconnector", "levels\\l2\\l2_towerconnector"},
    {"Base game l2", "l2_towerroom", "levels\\l2\\l2_towerroom"},
    {"Base game l2", "l2_upperhallway", "levels\\l2\\l2_upperhallway"},
    {"Base game l3", "l3_bedroom_hall", "levels\\l3\\l3_bedroom_hall"},
    {"Base game l3", "l3_caverns_start", "levels\\l3\\l3_caverns_start"},
    {"Base game l3", "l3_chamberrockhall", "levels\\l3\\l3_chamberrockhall"},
    {"Base game l3", "l3_chapel", "levels\\l3\\l3_chapel"},
    {"Base game l3", "l3_main_bedroom", "levels\\l3\\l3_main_bedroom"},
    {"Base game l3", "l3_main_hall", "levels\\l3\\l3_main_hall"},
    {"Base game l3", "l3_mansion_exterior_afterburn", "levels\\l3\\l3_mansion_exterior_afterburn"},
    {"Base game l3", "l3_secretchamber", "levels\\l3\\l3_secretchamber"},
    {"Base game l3", "l3_stairhall", "levels\\l3\\l3_stairhall"},
    {"Base game l4", "l4_ballcourt", "levels\\l4\\l4_ballcourt"},
    {"Base game l4", "l4_pool", "levels\\l4\\l4_pool"},
    {"Base game l4", "l4_ragnarok_room", "levels\\l4\\l4_ragnarok_room"},
    {"Base game l4", "l4_staircase_mictlan", "levels\\l4\\l4_staircase_mictlan"},
    {"Base game l4", "l4_staircase_upper", "levels\\l4\\l4_staircase_upper"},
    {"Base game l4", "l4_staircase_xibalba", "levels\\l4\\l4_staircase_xibalba"},
    {"Base game l4", "l4_temple", "levels\\l4\\l4_temple"},
    {"Base game l4", "l4_templepath", "levels\\l4\\l4_templepath"},
    {"Base game l4", "l4_trailstart", "levels\\l4\\l4_trailstart"},
    {"Base game l4", "l4_trailtube", "levels\\l4\\l4_trailtube"},
    {"Base game l4", "l4_traprooms", "levels\\l4\\l4_traprooms"},
    {"Base game l5", "l5_startsnow", "levels\\l5\\l5_startsnow"},
    {"Base game l5", "l5_valaskjalf", "levels\\l5\\l5_valaskjalf"},
    {"Base game l5", "l5_valaskjalf_entry", "levels\\l5\\l5_valaskjalf_entry"},
    {"Base game l5", "l5_valaskjalf_entryb", "levels\\l5\\l5_valaskjalf_entryb"},
    {"Base game l5", "l5_valgrind", "levels\\l5\\l5_valgrind"},
    {"Base game l5", "l5_valgrind_tunnel", "levels\\l5\\l5_valgrind_tunnel"},
    {"Base game l6", "l6_ship_engine_hall", "levels\\l6\\l6_ship_engine_hall"},
    {"Base game l6", "l6_ship_exterior", "levels\\l6\\l6_ship_exterior"},
    {"Base game l6", "l6_ship_natla_room", "levels\\l6\\l6_ship_natla_room"},
    {"Base game l6", "l6_ship_upper_hallway", "levels\\l6\\l6_ship_upper_hallway"},
    {"Base game l6", "l6_ship_upper_hallway_a", "levels\\l6\\l6_ship_upper_hallway_a"},
    {"Base game l6", "l6_ship_upper_hallway_b", "levels\\l6\\l6_ship_upper_hallway_b"},
    {"Base game l7", "l7_arctic_sea", "levels\\l5\\l7_arctic_sea"},
    {"Base game l7", "l7_helheim01", "levels\\l5\\l7_helheim01"},
    {"Base game l7", "l7_helheim02", "levels\\l5\\l7_helheim02"},
    {"Base game l7", "l7_helheim03", "levels\\l5\\l7_helheim03"},
    {"Base game l7", "l7_helheim_hall01", "levels\\l5\\l7_helheim_hall01"},
    {"Base game l7", "l7_helheim_hall02", "levels\\l5\\l7_helheim_hall02"},
    {"Base game l7", "l7_himalaya_end", "levels\\l5\\l7_himalaya_end"},
    {"Base game l7", "l7_monastery", "levels\\l5\\l7_monastery"},
    {"Base game l7", "l7_thin_ice", "levels\\l5\\l7_thin_ice"},
    {"Base game l7", "l7_yggdrasil", "levels\\l5\\l7_yggdrasil"},
    {"Base game l7", "l7_yggdrasil_end", "levels\\l5\\l7_yggdrasil_end"},
    {"Base game l7", "l7_yggdrasil_hall01", "levels\\l5\\l7_yggdrasil_hall01"},
    {"Base game l7", "l7_yggdrasil_hall02", "levels\\l5\\l7_yggdrasil_hall02"},
    {"DLC 1", "dlc_caverns", "dlc\\dlc_level1\\dlc_caverns"},
    {"DLC 1", "dlc_caverns_hall", "dlc\\dlc_level1\\dlc_caverns_hall"},
    {"DLC 1", "dlc_dungeon", "dlc\\dlc_level1\\dlc_dungeon"},
    {"DLC 1", "dlc_dungeonhalla", "dlc\\dlc_level1\\dlc_dungeonhalla"},
    {"DLC 1", "dlc_dungeonhallb", "dlc\\dlc_level1\\dlc_dungeonhallb"},
    {"DLC 1", "dlc_level1_left", "dlc\\dlc_level1\\dlc_level1_left"},
    {"DLC 1", "dlc_level1_right", "dlc\\dlc_level1\\dlc_level1_right"},
    {"DLC 1", "dlc_level1_start", "dlc\\dlc_level1\\dlc_level1_start"},
    {"DLC 1", "dlc_pillory", "dlc\\dlc_level1\\dlc_pillory"},
    {"DLC 1", "dlc_treasureroom", "dlc\\dlc_level1\\dlc_treasureroom"},
    {"DLC 1", "dlc_water_wheel", "dlc\\dlc_level1\\dlc_water_wheel"},
    {"DLC 1", "dlc_watertunnel", "dlc\\dlc_level1\\dlc_watertunnel"},
    {"DLC 2", "dlc2_ceremony_room", "dlc\\dlc_level2\\dlc2_ceremony_room"},
    {"DLC 2", "dlc2_goo_room", "dlc\\dlc_level2\\dlc2_goo_room"},
    {"DLC 2", "dlc2_hall_ceremony_goo", "dlc\\dlc_level2\\dlc2_hall_ceremony_goo"},
    {"DLC 2", "dlc2_hall_goo_machine", "dlc\\dlc_level2\\dlc2_hall_goo_machine"},
    {"DLC 2", "dlc2_hall_machine_ceremony", "dlc\\dlc_level2\\dlc2_hall_machine_ceremony"},
    {"DLC 2", "dlc2_machine_room", "dlc\\dlc_level2\\dlc2_machine_room"},
    {"DLC 2", "dlc2_treasure_room_cine", "dlc\\dlc_level2\\dlc2_treasure_room_cine"},
    {"DLC 2", "dlc_level2_start", "dlc\\dlc_level2\\dlc_level2_start"},
    {"DLC 2", "dlc_yggdrasil_end", "dlc\\dlc_level2\\dlc_yggdrasil_end"},
    {"DLC 2", "dlc_yggdrasil_hall01", "dlc\\dlc_level2\\dlc_yggdrasil_hall01"},
    {"DLC 2", "dlc_yggdrasil_hall02", "dlc\\dlc_level2\\dlc_yggdrasil_hall02"},
    {"DLC other starts", "dlc_level3_start", "dlc\\dlc_level3\\dlc_level3_start"},
    {"DLC other starts", "dlc_level4_start", "dlc\\dlc_level4\\dlc_level4_start"},
    {"DLC other starts", "dlc_level5_start", "dlc\\dlc_level5\\dlc_level5_start"},
    {"DLC other starts", "dlc_level6_start", "dlc\\dlc_level6\\dlc_level6_start"},
};
const int kUnitCount = sizeof(kUnits) / sizeof(kUnits[0]);

bool ReadWord(DWORD address, WORD *out) {
    __try {
        *out = *reinterpret_cast<const volatile WORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadString(DWORD address, char *out, size_t size) {
    out[0] = 0;
    if (!address) return false;
    __try {
        size_t i = 0;
        const volatile char *p = reinterpret_cast<const volatile char *>(address);
        for (; i + 1 < size && i < 127 && p[i]; ++i) out[i] = p[i];
        out[i] = 0;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
        return false;
    }
}

// object id -> name as the game does ([0xdb94d0] + id * 8)
bool ObjectName(int id, char *out, size_t size) {
    out[0] = 0;
    DWORD table = 0, count = 0, name = 0;
    if (id <= 0 || !ReadDword(kObjNames, &table) || !table || !ReadDword(table, &count) || id > static_cast<int>(count))
        return false;
    return ReadDword(table + static_cast<DWORD>(id) * 8, &name) && ReadString(name, out, size) && out[0];
}

// name -> object id as tru+0x1bf770 does (case-insensitive, 0 = not in the object list)
int ObjectId(const char *name) {
    DWORD table = 0, count = 0;
    if (!name || !name[0] || !ReadDword(kObjNames, &table) || !table || !ReadDword(table, &count) || count > 4096) return 0;
    for (DWORD id = 1; id <= count; ++id) {
        DWORD p = 0;
        char other[128];
        if (ReadDword(table + id * 8, &p) && ReadString(p, other, sizeof(other)) && _stricmp(other, name) == 0)
            return static_cast<int>(id);
    }
    return 0;
}

// the player type table the game uses now (the operand of tru+0x1bf121; TruDlc2Player points it at its copy)
DWORD TypeTable() {
    DWORD table = 0;
    if (!ReadDword(kTypeLookup + 2, &table)) return 0;
    return table;
}

// record <index>: name, player record (f2 = the player's)? false past the end
bool TypeRecord(int index, char *name, size_t size, bool *player) {
    DWORD table = TypeTable(), namePtr = 0, f2 = 0;
    if (!table || index < 0 || index > 63) return false;
    DWORD rec = table + static_cast<DWORD>(index) * 0x1c;
    if (!ReadDword(rec, &namePtr) || !namePtr || !ReadString(namePtr, name, size)) return false;
    ReadDword(rec + 8, &f2);
    *player = f2 == kPlayerF2;
    return true;
}

// type of an object name as tru+0x1bf0e0: the first record with that name, -1 if none
int TypeIndexOf(const char *name) {
    char rec[64];
    bool player = false;
    for (int i = 0; TypeRecord(i, rec, sizeof(rec), &player); ++i)
        if (_stricmp(rec, name) == 0) return i;
    return -1;
}

DWORD GameData() {
    DWORD gd = 0;
    ReadDword(kGameDataPtr, &gd);
    return gd;
}

struct CostumeState {
    DWORD gameData;
    WORD mode, chosen0, chosen1, chosen2;  // +0x1f4, +0x20c, +0x20e, +0x210
    DWORD current;                          // [0xe7f1c8]
    int unitDefault;                        // unit data +0x70 -> +0x294, -1 = unknown
    DWORD unitId;
};

int UnitDefaultCostume(DWORD *unitId) {
    *unitId = 0;
    if (!g_unitOk || !ReadDword(kUnitId, unitId)) return -1;
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD id = 0, state = 0, data = 0, level = 0;
        if (!ReadDword(e, &id) || !ReadDword(e + 4, &state)) return -1;
        if ((state & 0xff) != 2 || id != *unitId) continue;
        WORD costume = 0;
        if (ReadDword(e + 8, &data) && data && ReadDword(data + 0x70, &level) && level &&
            ReadWord(level + 0x294, &costume))
            return costume;
        return -1;
    }
    return -1;
}

void ReadCostumeState(CostumeState *s) {
    memset(s, 0, sizeof(*s));
    s->gameData = GameData();
    if (s->gameData) {
        ReadWord(s->gameData + kGdMode, &s->mode);
        ReadWord(s->gameData + kGdChosen0, &s->chosen0);
        ReadWord(s->gameData + kGdChosen1, &s->chosen1);
        ReadWord(s->gameData + kGdChosen2, &s->chosen2);
    }
    ReadDword(kCostumeNow, &s->current);
    s->unitDefault = UnitDefaultCostume(&s->unitId);
}

// "<id> <name>" or "0 (none)"
void IdName(int id, char *out, size_t size) {
    char name[128];
    if (id <= 0) { Out(out, size, "%d (none)", id); return; }
    if (ObjectName(id, name, sizeof(name))) Out(out, size, "%d %s", id, name);
    else Out(out, size, "%d (?)", id);
}

const char *GameState() {
    DWORD busy = 0;
    ReadDword(kGameTracker + 0xb8, &busy);
    if ((busy >> 8) & 0xff) return "level change pending (GameTracker+0xb9)";
    if (InLevel()) return "in a level (player instance present)";
    return "no player instance (front end / loading)";
}

// player object: the costume id [0xe7f1c8], its entry in the object table 0xdb7400 (object +0x14 id, +0x34 type)
void PlayerInfo(char *o, size_t n) {
    DWORD player = 0, current = 0;
    ReadDword(kPlayerPtr, &player);
    ReadDword(kCostumeNow, &current);
    char idName[160];
    IdName(static_cast<int>(current), idName, sizeof(idName));
    char name[128] = "";
    ObjectName(static_cast<int>(current), name, sizeof(name));
    int type = name[0] ? TypeIndexOf(name) : -1;
    DWORD object = 0, objType = 0xffffffff, state = 0;
    for (int i = 0; i < kObjectEntries && current; ++i) {
        DWORD e = kObjectTable + static_cast<DWORD>(i) * 0x24, obj = 0, idState = 0;
        if (!ReadDword(e + 8, &obj) || !ReadDword(e + 0xc, &idState)) break;
        if (obj && static_cast<DWORD>(static_cast<SHORT>(idState & 0xffff)) == current) {
            object = obj;
            state = idState >> 16;
            ReadDword(obj + 0x34, &objType);
            break;
        }
    }
    Out(o, n, "instance 0x%08lx; object %s (type record %d by name, object 0x%08lx state %lu, object+0x34 type %ld)",
        player, idName, type, object, state, static_cast<LONG>(objType));
}

void PluginsInfo(char *o, size_t n) {
    const char *const names[] = {"TruShadowPower", "TruDoppelganger", "TruDlc2Player", "TruRockVein", "TruLink"};
    size_t used = 0;
    o[0] = 0;
    for (const char *name : names) {
        char file[64], exportName[64];
        _snprintf_s(file, sizeof(file), _TRUNCATE, "%s.asi", name);
        _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", name);
        HMODULE module = GetModuleHandleA(file);
        typedef const char *(*VersionFn)();
        VersionFn version = module ? reinterpret_cast<VersionFn>(GetProcAddress(module, exportName)) : nullptr;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s=%s", used ? "; " : "", name,
                            !module ? "no" : version ? version() : "loaded");
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    _snprintf_s(o + used, n - used, _TRUNCATE, "; ModLoader=%s", GetModuleHandleA("ModLoader.asi") ? "loaded" : "no");
}

void CostumeInfo(char *o, size_t n) {
    CostumeState s;
    ReadCostumeState(&s);
    char cur[160], c0[160], c2[160], def[160];
    IdName(static_cast<int>(s.current), cur, sizeof(cur));
    IdName(s.chosen0, c0, sizeof(c0));
    IdName(s.chosen2, c2, sizeof(c2));
    IdName(s.unitDefault, def, sizeof(def));
    Out(o, n, "current [0x%08lx] %s; game data [0x%08lx] = 0x%08lx: +0x1f4 %u (level load reads +0x%x), chosen +0x20c %s, "
        "+0x20e %u, +0x210 %s; unit %lu default %s", kCostumeNow, cur, kGameDataPtr, s.gameData, s.mode,
        s.mode ? kGdChosen2 : kGdChosen0, c0, s.chosen1, c2, s.unitId, def);
}

// value getters (any thread, read-only)
void ValStatusUnit(char *o, size_t n) {
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    DWORD id = 0;
    ReadDword(kUnitId, &id);
    Out(o, n, "%s (stream unit id %lu)", unit[0] ? unit : "-", id);
}
void ValState(char *o, size_t n) { Out(o, n, "%s", GameState()); }
void ValCostume(char *o, size_t n) {
    if (!g_costumeOk) { Out(o, n, "costume code check failed"); return; }
    CostumeInfo(o, n);
}
void ValCostumeCurrent(char *o, size_t n) {
    DWORD current = 0;
    ReadDword(kCostumeNow, &current);
    IdName(static_cast<int>(current), o, n);
}
void ValPlayerObject(char *o, size_t n) { PlayerInfo(o, n); }
void ValPlugins(char *o, size_t n) { PluginsInfo(o, n); }
// "index name id; ..." for every player record of the type table
void ValCostumeList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    char name[64];
    bool player = false;
    for (int i = 0; TypeRecord(i, name, sizeof(name), &player); ++i) {
        if (!player) continue;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d %s %d", used ? "; " : "", i, name, ObjectId(name));
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!used) Out(o, n, "no type table");
}
// "group: unit unit ...; group: ..." for every offered unit
void ValLevelList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    const char *group = nullptr;
    for (const UnitRow &u : kUnits) {
        bool head = !group || strcmp(group, u.group) != 0;
        group = u.group;
        int w = head ? _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s: %s", used ? "; " : "", u.group, u.unit)
                     : _snprintf_s(o + used, n - used, _TRUNCATE, " %s", u.unit);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

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
// costume.set <index|name> [20c|210]: the chosen costume (object id) into the game-data word the level load reads
// (+0x20c while +0x1f4 is 0, else +0x210 - tru+0x1de2d6), checked first with the game's own validator tru+0x1c54e0
// (the level load's check: id in the object list and <name>.drm present). The game writes +0x20c the same way in its
// state save tru+0x155cb1 (word = costume object id). Takes effect at the next level load.
bool SetCostume(const char *arg, char *o, size_t n) {
    if (!g_costumeOk || !g_experimental) { Out(o, n, "costume code not verified / experimental off"); return false; }
    char first[64] = "", second[16] = "";
    if (!arg || sscanf_s(arg, "%63s %15s", first, static_cast<unsigned>(sizeof(first)), second,
                         static_cast<unsigned>(sizeof(second))) < 1) {
        Out(o, n, "usage: costume.set <type record index | costume name> [20c|210]");
        return false;
    }
    char name[64] = "";
    bool player = false;
    char *end = nullptr;
    long index = strtol(first, &end, 10);
    if (end && !*end) {
        if (!TypeRecord(static_cast<int>(index), name, sizeof(name), &player)) { Out(o, n, "no type record %ld", index); return false; }
    } else {
        index = TypeIndexOf(first);
        if (index < 0 || !TypeRecord(static_cast<int>(index), name, sizeof(name), &player)) {
            Out(o, n, "'%s' is not in the player type table", first);
            return false;
        }
    }
    if (!player) { Out(o, n, "type record %ld '%s' is not a player record", index, name); return false; }
    int id = ObjectId(name);
    if (!id) { Out(o, n, "'%s' is not in the object list", name); return false; }
    if (!reinterpret_cast<CostumeValidFn>(kCostumeValid)(id)) {
        Out(o, n, "'%s' (id %d) refused by the game's check 0x%08lx (no %s.drm?) - the level load would ignore it", name,
            id, kCostumeValid, name);
        return false;
    }
    DWORD gd = GameData();
    WORD mode = 0;
    if (!gd || !ReadWord(gd + kGdMode, &mode)) { Out(o, n, "no game data at [0x%08lx]", kGameDataPtr); return false; }
    DWORD slot = mode ? kGdChosen2 : kGdChosen0;
    if (_stricmp(second, "20c") == 0) slot = kGdChosen0;
    else if (_stricmp(second, "210") == 0) slot = kGdChosen2;
    else if (second[0]) { Out(o, n, "slot must be 20c or 210"); return false; }
    __try {
        *reinterpret_cast<volatile WORD *>(gd + slot) = static_cast<WORD>(id);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Out(o, n, "write to 0x%08lx failed", gd + slot);
        return false;
    }
    Out(o, n, "costume %ld %s (object %d) written to game data 0x%08lx +0x%lx (+0x1f4 = %u); used at the next level load",
        index, name, id, gd, slot, mode);
    return true;
}
bool RunCostumeSet(const char *arg, char *o, size_t n) { return SetCostume(arg, o, n); }
bool RunCostumeSetReload(const char *arg, char *o, size_t n) {
    if (!SetCostume(arg, o, n)) return false;
    char first[400];
    strncpy_s(first, sizeof(first), o, _TRUNCATE);
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    if (!unit[0]) { Out(o, n, "%s; no current unit to reload", first); return false; }
    char text[300];
    bool ok = LoadUnit(unit, text, sizeof(text));
    Out(o, n, "%s; %s", first, text);
    return ok;
}
// costume.reset: what the new-game reset does (TU 0x821fe9a8, PC tru+0x156abe): +0x210 / +0x20e / +0x20c = 0, so the
// next level load takes the unit's default costume. Only these three words - the reset itself does far more.
bool RunCostumeReset(const char *, char *o, size_t n) {
    if (!g_costumeOk || !g_experimental) { Out(o, n, "costume code not verified / experimental off"); return false; }
    DWORD gd = GameData();
    if (!gd) { Out(o, n, "no game data at [0x%08lx]", kGameDataPtr); return false; }
    __try {
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen2) = 0;
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen1) = 0;
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen0) = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Out(o, n, "write to game data 0x%08lx failed", gd);
        return false;
    }
    Out(o, n, "game data 0x%08lx +0x210 / +0x20e / +0x20c = 0 (unit default at the next level load)", gd);
    return true;
}
bool RunTodo(const char *, char *o, size_t n) { Out(o, n, "todo - not implemented"); return false; }

// ======================================================================================================================
// 0.3: original developer debug menu, quick wins, log page, videos
// ======================================================================================================================

volatile LONG g_exceptionLines = 0;          // log lines (tails / script) that mention an exception
volatile LONG g_ownExceptions = 0;           // exceptions TruMenu caught in its own game calls (dev rows, script natives)

bool WriteBytes(DWORD address, const void *data, size_t size) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), size, PAGE_EXECUTE_READWRITE, &old)) return false;
    bool ok = true;
    __try {
        memcpy(reinterpret_cast<void *>(address), data, size);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    DWORD unused = 0;
    VirtualProtect(reinterpret_cast<void *>(address), size, old, &unused);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), size);
    return ok;
}

bool ReadByte(DWORD address, BYTE *out) {
    __try {
        *out = *reinterpret_cast<const volatile BYTE *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// ---- developer menu: Crystal's tables in .data 0x8aaa6c .. 0x8ab3f0 (tools/devmenu_dump.py; README "Developer
// menu"). Row 0x18 bytes: +0 type, +4 min / action argument, +8 max, +0xc label, +0x10 target, +0x14 mask / bool
// value / int callback. The retail exe has no driver for them any more (the root 0x8aaae8 is referenced from the
// tables only); TruMenu reads the rows at load and draws / runs them as the row types say.
const DWORD kDevFrom = 0x008aaa6c, kDevTo = 0x008ab3f0, kDevRoot = 0x008aaae8, kDevRowSize = 0x18;
const DWORD kDevRootTitle = 0x00855070;     // "This should not be the Options Title"
enum DevType { kDevFlag = 0x00, kDevBool = 0x02, kDevInt = 0x03, kDevAction = 0x09, kDevLink = 0x0a, kDevTitle = 0x0b,
               kDevEnd = 0x10, kDevHeader = 0x11 };
struct DevRow {
    DWORD addr, page;                        // row address, page (first row) it belongs to
    DWORD type, p1, p2, label, target, p5;   // the six dwords
    char text[48];                           // label string
    char id[56];                             // "dev.<slug>" for value / action rows, "" else
};
const int kDevMax = 128;
DevRow g_dev[kDevMax];
int g_devCount = 0;
DWORD g_devPages[48];
int g_devPageCount = 0;
bool g_devOk = false;
DWORD g_devPage = kDevRoot;                  // page shown in the menu
char g_devStatus[160] = "not read";

// facts per row from the static pass (tools/devmenu_dump.py, 2026-10-31): who reads the target in retail code
struct DevNote { DWORD row; const char *note; };
const DevNote kDevNotes[] = {
    {0x008aab00, "live: streamFlags 0x200000 is read by Reload Current Unit 0x5dfba0 and ~20 other sites"},
    {0x008aab30, "0x5d37b0 = jmp 0x6457a0 (empty function): compiled out"},
    {0x008aaab8, "0x5dfba0: if byte [0xe7f141] == 0 { if streamFlags & 0x200000: 0x5570f0(0); 0x5df760(4) }; "
                 "byte [0xe7f143] = 0 - reloads the unit"},
    {0x008aab78, "0x6457a0 is an empty function (ret): compiled out"},
    {0x008aab90, "0x555d40: streamFlags |= 0x200000 only"},
    {0x008aabd8, "readers with this mask: 0x5cf331, 0x5cf434, 0x5cf57b (what they draw in retail: unknown)"},
    {0x008aabf0, "no reader of 0xe7edb4 in retail code: effect unknown / dead"},
    {0x008aac38, "callback 0x5d36a0: writes the current unit's fog (unit +0x94 / +0x98 / +0xa0..0xa3) and calls "
                 "0x5bfe10 / 0x5bfe40"},
    {0x008aac50, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac68, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac80, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac98, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aacb0, "0x5d3760: the unit's fog defaults (0xe7b8a0 / 0xe7ecdc) back into the five ints, then 0x5d36a0(0)"},
    {0x008aacf8, "written once at init (0x5df56d = 1), no reader found: effect unknown"},
    {0x008aad10, "no reader of 0xa02b80 in retail code: effect unknown / dead"},
    {0x008aad28, "live: read at 0x5da2e9, written at 0x5d3cfb / 0x5da316"},
    {0x008aad40, "live: init 0x1000 at 0x5d3d44, read at 0x5da380 (fild)"},
    {0x008aad58, "byte in .rdata, no reader: dead"},
    {0x008aad70, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aad88, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aada0, "no reader with this mask found: effect unknown"},
    {0x008aadb8, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aadd0, "0x5d3510: dword [0xe7f0b4] |= 0x100 (GameTracker+0x2c) - a progress bit, TruMenu cannot undo it"},
    {0x008aae18, "0x5d7590: calls [0x8ab79c](float [0x8416b4])"},
    {0x008aae30, "no reader with this mask found: effect unknown"},
    {0x008aae48, "byte in .rdata, no reader: dead"},
    {0x008aaf38, "byte in .rdata, no reader: dead"},
};

const char *DevNoteOf(DWORD row) {
    for (const DevNote &n : kDevNotes)
        if (n.row == row) return n.note;
    return nullptr;
}

const char *DevTypeName(DWORD type) {
    switch (type) {
    case kDevFlag: return "flag";
    case kDevBool: return "bool";
    case kDevInt: return "int";
    case kDevAction: return "action";
    case kDevLink: return "page";
    case kDevTitle: return "title";
    case kDevEnd: return "end";
    case kDevHeader: return "header";
    default: return nullptr;
    }
}

void Slug(const char *in, char *out, size_t size) {
    size_t n = 0;
    bool sep = false;
    for (const char *p = in; *p && n + 1 < size; ++p) {
        unsigned char c = static_cast<unsigned char>(*p);
        if (isalnum(c)) {
            if (sep && n) out[n++] = '_';
            if (n + 1 < size) out[n++] = static_cast<char>(tolower(c));
            sep = false;
        } else {
            sep = true;
        }
    }
    out[n] = 0;
}

// a function that is only "ret" (or a jmp to one): compiled out in retail
bool IsEmptyFunction(DWORD fn) {
    BYTE b = 0;
    if (!ReadByte(fn, &b)) return false;
    if (b == 0xc3) return true;
    DWORD rel = 0;
    if (b == 0xe9 && ReadDword(fn + 1, &rel)) {
        BYTE t = 0;
        return ReadByte(fn + 5 + rel, &t) && t == 0xc3;
    }
    return false;
}

// read the tables the way tools/devmenu_dump.py walks them: pages end with a type 0x10 row, a 0x11 header page keeps
// its 0x10 rows as empty slots, a lone dword between pages (0x8aaa9c = the root pointer) is skipped
void DevRead() {
    g_devCount = g_devPageCount = 0;
    DWORD title[6] = {};
    for (int i = 0; i < 6; ++i) ReadDword(kDevRoot + 4 * i, &title[i]);
    char text[64];
    ReadString(kDevRootTitle, text, sizeof(text));
    if (title[0] != kDevTitle || title[3] != kDevRootTitle || strcmp(text, "This should not be the Options Title") != 0) {
        Out(g_devStatus, sizeof(g_devStatus), "root row 0x%08lx does not match (type %lu, label 0x%08lx)", kDevRoot,
            title[0], title[3]);
        return;
    }
    DWORD a = kDevFrom, page = kDevFrom;
    bool header = false;
    while (a + kDevRowSize <= kDevTo && g_devCount < kDevMax) {
        DWORD r[6] = {};
        for (int i = 0; i < 6; ++i) ReadDword(a + 4 * i, &r[i]);
        if (header && page != a && r[0] != kDevEnd) { header = false; page = a; }
        if (a == page) {
            if (!DevTypeName(r[0])) { a += 4; page = a; continue; }
            header = r[0] == kDevHeader;
            if (g_devPageCount < 48) g_devPages[g_devPageCount++] = page;
        }
        if (!DevTypeName(r[0])) {
            Out(g_devStatus, sizeof(g_devStatus), "unknown row type 0x%lx at 0x%08lx - stopped", r[0], a);
            return;
        }
        DevRow &d = g_dev[g_devCount++];
        d.addr = a;
        d.page = page;
        d.type = r[0]; d.p1 = r[1]; d.p2 = r[2]; d.label = r[3]; d.target = r[4]; d.p5 = r[5];
        d.text[0] = d.id[0] = 0;
        if (d.label) ReadString(d.label, d.text, sizeof(d.text));
        if ((d.type == kDevFlag || d.type == kDevBool || d.type == kDevInt || d.type == kDevAction) && d.text[0]) {
            char slug[48];
            Slug(d.text, slug, sizeof(slug));
            Out(d.id, sizeof(d.id), "dev.%s", slug);
            for (int k = 0; k + 1 < g_devCount; ++k)          // keep ids unique (none collide in retail)
                if (strcmp(g_dev[k].id, d.id) == 0) { Out(d.id, sizeof(d.id), "dev.%s_%08lx", slug, a); break; }
        }
        if (d.type == kDevEnd && !header) page = a + kDevRowSize;
        a += kDevRowSize;
    }
    g_devOk = g_devCount > 90;
    Out(g_devStatus, sizeof(g_devStatus), "%d rows in %d pages read from 0x%08lx .. 0x%08lx%s", g_devCount, g_devPageCount,
        kDevFrom, kDevTo, g_devOk ? "" : " (fewer than expected - off)");
}

const DevRow *DevFind(const char *id) {
    if (!g_devOk || !id) return nullptr;
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].id[0] && _stricmp(g_dev[i].id, id) == 0) return &g_dev[i];
    return nullptr;
}

// page name: its title row, else the label of the first link to it, else "page 0x.. (not linked)"
void DevPageName(DWORD page, char *out, size_t size) {
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].addr == page && g_dev[i].type == kDevTitle && g_dev[i].text[0]) {
            Out(out, size, "%s", page == kDevRoot ? "Main Menu (root)" : g_dev[i].text);
            return;
        }
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].type == kDevLink && g_dev[i].target == page && g_dev[i].page != page) {
            Out(out, size, "%s", g_dev[i].text);
            return;
        }
    Out(out, size, "page 0x%08lx (not linked)", page);
}

void DevValue(const DevRow &d, char *o, size_t n) {
    DWORD v = 0;
    BYTE b = 0;
    switch (d.type) {
    case kDevFlag:
        if (ReadDword(d.target, &v)) Out(o, n, "%d", (v & d.p5) ? 1 : 0); else Out(o, n, "?");
        break;
    case kDevBool:
        if (ReadByte(d.target, &b)) Out(o, n, "%d", b ? 1 : 0); else Out(o, n, "?");
        break;
    case kDevInt:
        if (ReadDword(d.target, &v)) Out(o, n, "%ld", static_cast<LONG>(v)); else Out(o, n, "?");
        break;
    case kDevAction:
        Out(o, n, "%s", IsEmptyFunction(d.target) ? "empty" : "-");
        break;
    default:
        Out(o, n, "-");
    }
}

typedef void(__cdecl *DevFn)(DWORD);

// game thread: change / run one row
bool DevRun(const DevRow &d, const char *arg, char *o, size_t n) {
    if (!g_experimental) { Out(o, n, "experimental off"); return false; }
    __try {
        if (d.type == kDevFlag) {
            volatile DWORD *p = reinterpret_cast<volatile DWORD *>(d.target);
            bool on = BoolArg(arg, (*p & d.p5) != 0);
            if (on) *p |= d.p5; else *p &= ~d.p5;
            Out(o, n, "%s %d ([0x%08lx] = 0x%08lx, mask 0x%lx)", d.id, on ? 1 : 0, d.target, *p, d.p5);
            return true;
        }
        if (d.type == kDevBool) {
            BYTE cur = 0;
            ReadByte(d.target, &cur);
            bool on = BoolArg(arg, cur != 0);
            BYTE value = on ? static_cast<BYTE>(d.p5 & 0xff) : 0;
            if (on && !value) value = 1;
            if (!WriteBytes(d.target, &value, 1)) { Out(o, n, "write to 0x%08lx failed", d.target); return false; }
            Out(o, n, "%s %d (byte [0x%08lx] = 0x%02x)", d.id, on ? 1 : 0, d.target, value);
            return true;
        }
        if (d.type == kDevInt) {
            char *end = nullptr;
            long v = strtol(arg ? arg : "", &end, 0);
            if (!arg || !arg[0] || *end) { Out(o, n, "usage: %s <%ld..%ld>", d.id, static_cast<LONG>(d.p1), static_cast<LONG>(d.p2)); return false; }
            LONG lo = static_cast<LONG>(d.p1), hi = static_cast<LONG>(d.p2);
            if (v < lo) v = lo;
            if (v > hi) v = hi;
            if (d.p5 && !IsEmptyFunction(d.p5) && !InLevel()) { Out(o, n, "needs a level (callback 0x%08lx)", d.p5); return false; }
            *reinterpret_cast<volatile LONG *>(d.target) = v;
            // callback as the game's own caller 0x5d3760 calls it: cdecl, one argument 0
            if (d.p5) reinterpret_cast<DevFn>(d.p5)(0);
            Out(o, n, "%s %ld ([0x%08lx]%s)", d.id, v, d.target, d.p5 ? ", callback called" : "");
            return true;
        }
        if (d.type == kDevAction) {
            bool empty = IsEmptyFunction(d.target);
            if (!empty && !InLevel()) { Out(o, n, "needs a level"); return false; }
            reinterpret_cast<DevFn>(d.target)(d.p1);   // cdecl; +4 is the argument (only the Chapter rows have one)
            Out(o, n, "%s: 0x%08lx(0x%lx) called%s", d.id, d.target, d.p1, empty ? " - empty function in retail" : "");
            return true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "%s: exception 0x%08lx", d.id, GetExceptionCode());
        Log(0, "dev menu: %s", o);           // reaches the log page through the TruMenu.log tail
        return false;
    }
    Out(o, n, "row type %lu has no value", d.type);
    return false;
}

void ValDevList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    if (!g_devOk) { Out(o, n, "%s", g_devStatus); return; }
    for (int i = 0; i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (!d.id[0]) continue;
        char value[32], page[64];
        DevValue(d, value, sizeof(value));
        DevPageName(d.page, page, sizeof(page));
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s %s=%s (%s; row 0x%08lx)", used ? "; " : "", d.id,
                            DevTypeName(d.type), value, page, d.addr);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

// ---- quick wins (catalog section 14; every address checked at load, Start) ----
const DWORD kTimeDilation = 0x00e7f1d0;     // GameTracker+0x148 float (TRLAU MainMenu.cpp); init 0x5d3d25, read 0x5da3a0
const DWORD kStreamFlags = 0x00e7f0b8;      // GameTracker+0x30; pause = bit 0x1000 (TRLAU, key F3)
const DWORD kPlayerControl = 0x008ab4e6;    // byte, 1 = player control on (TRLAU Input.cpp); 0x5d5f45 / 0x5d5f60
const DWORD kUiHidden = 0x00cdc9a0;         // bool (TRLAU Frontend.cpp); read at 0x5a434c
const DWORD kCameraFov = 0xb0;              // [0xe80534] + 0xb0 float (TRLAU Camera.h)
const DWORD kFirstInstance = 0x00d98d54;    // first instance, +0x08 next (TRLAU Instances.cpp); written at 0x5b2ec6
const DWORD kRemoveInstance = 0x005bc4e0;   // INSTANCE_ReallyRemoveInstance(inst, 0, 0) cdecl (TRLAU)
const char *const kRemoveInstanceBytes = "53 56 8b74240c 33db 395e60 57 0f8496000000";
const DWORD kCostumeSwitch = 0x006f0a90;    // reached from 0x778ca0 (native 0x79db50): alt id or the next of the list
const char *const kCostumeSwitchBytes = "a194f0e700 8b4810 8b5114 83ec0c 53 56 57 6aff 52";
const DWORD kCostumeSwitchAlt = 0x00778ca0; // thiscall: [0xe7f1cc] = id of entry [ecx], then jmp 0x6f0a90
const char *const kCostumeSwitchAltBytes = "8b01 50 e898dce5ff 0fb74808 83c404 890dccf1e700 e9d67df7ff";
const DWORD kAltPlayerObject = 0x00e7f1cc;  // GameTracker+0x144 altPlayerObjectID
const DWORD kGlobalInfo = 0x00e7ee50;       // [..]+4 -> {u16 count; u16 *ids at +4} (read at 0x6f0ac7)
const DWORD kMainState = 0x00e7ed60;        // TRLAU: 10 = main menu; read at 0x5d56e0
const DWORD kMoviePlay = 0x004a12b0;        // cdecl (name, bool loop) (catalog 11.1)
const char *const kMoviePlayBytes = "8b4c2404 8a442408 83ec20 53 55 33db 51 881db839a000";
const DWORD kMenuLoopPtr = 0x008abf20;      // char* "medsea_loop" 0x8552a8, read at 0x5daf35 for the menu background
const DWORD kMenuLoopOrig = 0x008552a8;
typedef void(__cdecl *VoidFn)();
typedef void(__cdecl *RemoveFn)(void *instance, int, int);
typedef void(__cdecl *MoviePlayFn)(const char *name, bool loop);

bool g_timeOk = false, g_pauseOk = false, g_controlOk = false, g_uiOk = false, g_instOk = false, g_removeOk = false,
     g_switchOk = false, g_movieOk = false, g_menuLoopOk = false, g_mainStateOk = false;
float g_mark[3];
bool g_markSet = false;
volatile LONG g_weaponsPending = 0;          // frames until INSTANCE_Post(player, 35, 0) after a costume switch
char g_menuLoopName[64];
char g_exeDir[MAX_PATH], g_asiDir[MAX_PATH];

void Post(DWORD instance, int message, int data) {
    reinterpret_cast<InstancePostFn>(kInstancePost)(reinterpret_cast<void *>(instance), message, data);
}

bool ParseFloats(const char *arg, float *v, int count) {
    if (!arg) return false;
    const char *p = arg;
    for (int i = 0; i < count; ++i) {
        char *end = nullptr;
        v[i] = static_cast<float>(strtod(p, &end));
        if (end == p) return false;
        p = end;
    }
    while (*p == ' ') ++p;
    return *p == 0;
}

void ValTimeScale(char *o, size_t n) {
    float f = 0.0f;
    if (g_timeOk && ReadFloats(kTimeDilation, &f, 1)) Out(o, n, "%.3f", f); else Out(o, n, "?");
}
bool RunTimeScale(const char *arg, char *o, size_t n) {
    if (!g_timeOk || !g_experimental) { Out(o, n, "time code not verified / experimental off"); return false; }
    float f = arg && arg[0] ? static_cast<float>(atof(arg)) : 1.0f;
    if (!(f >= 0.0f && f <= 10.0f)) { Out(o, n, "usage: time.scale <0..10> (\"\" = 1)"); return false; }
    *reinterpret_cast<volatile float *>(kTimeDilation) = f;
    Out(o, n, "time.scale %.3f (timeDilation 0x%08lx)", f, kTimeDilation);
    return true;
}
void ValPause(char *o, size_t n) {
    DWORD v = 0;
    ReadDword(kStreamFlags, &v);
    Out(o, n, "%d", (v & 0x1000) ? 1 : 0);
}
bool RunPause(const char *arg, char *o, size_t n) {
    if (!g_pauseOk || !g_experimental) { Out(o, n, "streamFlags not verified / experimental off"); return false; }
    volatile DWORD *f = reinterpret_cast<volatile DWORD *>(kStreamFlags);
    bool on = BoolArg(arg, (*f & 0x1000) != 0);
    if (on) *f |= 0x1000; else *f &= ~0x1000u;
    Out(o, n, "time.pause %d (streamFlags 0x%08lx)", on ? 1 : 0, *f);
    return true;
}
void ValControl(char *o, size_t n) {
    BYTE b = 0;
    if (ReadByte(kPlayerControl, &b)) Out(o, n, "%u", b); else Out(o, n, "?");
}
bool RunControl(const char *arg, char *o, size_t n) {
    if (!g_controlOk || !g_experimental) { Out(o, n, "player control byte not verified / experimental off"); return false; }
    volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kPlayerControl);
    bool on = BoolArg(arg, *b != 0);
    *b = on ? 1 : 0;
    Out(o, n, "player.control %d (byte 0x%08lx)", on ? 1 : 0, kPlayerControl);
    return true;
}
bool RunDie(const char *, char *o, size_t n) {
    if (!g_postOk || !g_experimental) { Out(o, n, "INSTANCE_Post not verified / experimental off"); return false; }
    DWORD player = 0;
    if (!ReadDword(kPlayerPtr, &player) || !player) { Out(o, n, "needs a level"); return false; }
    Post(player, 4, 3);                      // TRLAU MainMenu.cpp (F11): message 4, data 3 = ragdoll death
    Out(o, n, "INSTANCE_Post(player 0x%08lx, 4, 3)", player);
    return true;
}
void ValUiHide(char *o, size_t n) {
    BYTE b = 0;
    if (ReadByte(kUiHidden, &b)) Out(o, n, "%d", b ? 1 : 0); else Out(o, n, "?");
}
bool RunUiHide(const char *arg, char *o, size_t n) {
    if (!g_uiOk || !g_experimental) { Out(o, n, "UI byte not verified / experimental off"); return false; }
    volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kUiHidden);
    bool on = BoolArg(arg, *b != 0);
    *b = on ? 1 : 0;
    Out(o, n, "ui.hide %d", on ? 1 : 0);
    return true;
}
bool FovAddress(DWORD *address, float *value) {
    DWORD camera = 0;
    if (!ReadDword(kCurrentCamera, &camera) || !camera) return false;
    *address = camera + kCameraFov;
    return ReadFloats(*address, value, 1);
}
void ValFov(char *o, size_t n) {
    DWORD a = 0;
    float f = 0.0f;
    if (FovAddress(&a, &f)) Out(o, n, "%.4f", f); else Out(o, n, "-");
}
bool RunFov(const char *arg, char *o, size_t n) {
    if (!g_experimental || !InLevel()) { Out(o, n, "needs a level / experimental off"); return false; }
    DWORD a = 0;
    float cur = 0.0f;
    if (!FovAddress(&a, &cur)) { Out(o, n, "no current camera [0x%08lx]", kCurrentCamera); return false; }
    // sanity check of the catalog's offset: the field must already hold an angle in radians
    if (!(cur > 0.05f && cur < 3.1f)) { Out(o, n, "camera+0xb0 = %f does not look like a fov - not written", cur); return false; }
    float f = arg && arg[0] ? static_cast<float>(atof(arg)) : 0.7854f;
    if (!(f > 0.05f && f < 3.1f)) { Out(o, n, "usage: camera.fov <0.05..3.1 radians> (\"\" = pi/4)"); return false; }
    *reinterpret_cast<volatile float *>(a) = f;
    Out(o, n, "camera.fov %.4f (was %.4f, 0x%08lx)", f, cur, a);
    return true;
}

// ---- instances: [0xd98d54] first, +0x08 next; +0x10 object (+0x14 object id), +0x20 position, +0x30 rotation,
// +0x58 intro unique id, +0x14 iflags, +0x23c no-draw groups (catalog section 1, TRLAU Instance.h)
struct InstInfo { DWORD addr; LONG intro; int objectId; char name[64]; float pos[3]; };

bool ReadInstance(DWORD inst, InstInfo *info) {
    memset(info, 0, sizeof(*info));
    info->addr = inst;
    DWORD object = 0, oid = 0, intro = 0;
    if (!ReadDword(inst + 0x10, &object) || !ReadDword(inst + 0x58, &intro)) return false;
    info->intro = static_cast<LONG>(intro);
    if (object && ReadDword(object + 0x14, &oid)) info->objectId = static_cast<int>(oid & 0xffff);
    if (!ObjectName(info->objectId, info->name, sizeof(info->name))) Out(info->name, sizeof(info->name), "?");
    return ReadFloats(inst + kInstancePosition, info->pos, 3);
}

// walks the list; calls fn for each instance until it returns false; max 4096
template <typename F> int ForInstances(F fn) {
    DWORD inst = 0;
    if (!g_instOk || !ReadDword(kFirstInstance, &inst)) return 0;
    int count = 0;
    while (inst && count < 4096) {
        InstInfo info;
        if (!ReadInstance(inst, &info)) break;
        ++count;
        if (!fn(info)) break;
        if (!ReadDword(inst + 8, &inst)) break;
    }
    return count;
}

void ValInstCount(char *o, size_t n) {
    int count = ForInstances([](const InstInfo &) { return true; });
    Out(o, n, "%d instances", count);
}

// "<intro id>" (decimal), "0x<address>" or "#<index>" -> instance address (0 = none)
DWORD FindInstance(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "give an instance: intro id, 0x<address> or #<index> (instance.list)"); return 0; }
    DWORD found = 0;
    char *end = nullptr;
    if (arg[0] == '#') {
        long want = strtol(arg + 1, &end, 10), i = 0;
        ForInstances([&](const InstInfo &x) { if (i++ == want) { found = x.addr; return false; } return true; });
    } else if (arg[0] == '0' && (arg[1] == 'x' || arg[1] == 'X')) {
        DWORD want = strtoul(arg, &end, 16);
        ForInstances([&](const InstInfo &x) { if (x.addr == want) { found = x.addr; return false; } return true; });
    } else {
        long want = strtol(arg, &end, 10);
        ForInstances([&](const InstInfo &x) { if (x.intro == want) { found = x.addr; return false; } return true; });
    }
    if (!found) Out(o, n, "no instance '%s' in the list [0x%08lx]", arg, kFirstInstance);
    return found;
}

bool RunInstanceList(const char *arg, char *o, size_t n) {
    if (!g_instOk) { Out(o, n, "instance list not verified"); return false; }
    size_t used = 0;
    o[0] = 0;
    int index = 0, shown = 0;
    int total = ForInstances([&](const InstInfo &x) {
        int i = index++;
        if (arg && arg[0] && !strstr(x.name, arg)) return true;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s#%d %ld %s 0x%08lx (%.0f %.0f %.0f)", used ? "; " : "", i,
                            x.intro, x.name, x.addr, x.pos[0], x.pos[1], x.pos[2]);
        if (w < 0) return false;
        used += static_cast<size_t>(w);
        ++shown;
        return true;
    });
    if (!total) { Out(o, n, "no instances (needs a level)"); return false; }
    if (used + 40 < n) _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d of %d shown", used ? "; " : "", shown, total);
    return true;
}
bool RunInstanceInfo(const char *arg, char *o, size_t n) {
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    InstInfo x;
    ReadInstance(inst, &x);
    float rot[3] = {};
    DWORD flags = 0, nodraw = 0, prev = 0;
    ReadFloats(inst + kInstanceRotation, rot, 3);
    ReadDword(inst + 0x14, &flags);
    ReadDword(inst + 0x23c, &nodraw);
    ReadDword(inst, &prev);
    Out(o, n, "0x%08lx intro %ld object %d %s pos %.2f %.2f %.2f rot %.4f %.4f %.4f iflags 0x%08lx noDrawGroups 0x%08lx%s",
        inst, x.intro, x.objectId, x.name, x.pos[0], x.pos[1], x.pos[2], rot[0], rot[1], rot[2], flags, nodraw,
        prev ? "" : " (node prev 0: removed)");
    return true;
}
bool SetPosition(DWORD inst, const float *p) {
    __try {
        volatile float *dst = reinterpret_cast<volatile float *>(inst + kInstancePosition);
        dst[0] = p[0]; dst[1] = p[1]; dst[2] = p[2];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}
bool NeedPlayer(DWORD *player, char *o, size_t n) {
    if (!g_experimental || !g_playerOk || !ReadDword(kPlayerPtr, player) || !*player) {
        Out(o, n, "needs a level / experimental off");
        return false;
    }
    return true;
}
bool RunTeleport(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    float p[3];
    if (!ParseFloats(arg, p, 3)) { Out(o, n, "usage: player.teleport <x> <y> <z>"); return false; }
    if (!SetPosition(player, p)) { Out(o, n, "write failed"); return false; }
    Out(o, n, "player at %.1f %.1f %.1f (tip: cheat.flight on, so Lara does not fall)", p[0], p[1], p[2]);
    return true;
}
bool RunMark(const char *, char *o, size_t n) {
    float p[3], r[3];
    DWORD instance = 0;
    if (!ReadLara(p, r, &instance)) { Out(o, n, "needs a level"); return false; }
    memcpy(g_mark, p, sizeof(g_mark));
    g_markSet = true;
    Out(o, n, "mark %.1f %.1f %.1f", p[0], p[1], p[2]);
    return true;
}
void ValMark(char *o, size_t n) {
    if (g_markSet) Out(o, n, "%.1f %.1f %.1f", g_mark[0], g_mark[1], g_mark[2]); else Out(o, n, "-");
}
bool RunRecall(const char *, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    if (!g_markSet) { Out(o, n, "no mark (player.mark first)"); return false; }
    if (!SetPosition(player, g_mark)) { Out(o, n, "write failed"); return false; }
    Out(o, n, "player back at the mark %.1f %.1f %.1f", g_mark[0], g_mark[1], g_mark[2]);
    return true;
}
bool RunGoto(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    float p[3];
    if (!ReadFloats(inst + kInstancePosition, p, 3) || !SetPosition(player, p)) { Out(o, n, "read / write failed"); return false; }
    Out(o, n, "player at instance 0x%08lx (%.1f %.1f %.1f)", inst, p[0], p[1], p[2]);
    return true;
}
bool RunBring(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    float p[3];
    if (!ReadFloats(player + kInstancePosition, p, 3) || !SetPosition(inst, p)) { Out(o, n, "read / write failed"); return false; }
    Out(o, n, "instance 0x%08lx brought to Lara (%.1f %.1f %.1f)", inst, p[0], p[1], p[2]);
    return true;
}
bool RunUnhide(const char *arg, char *o, size_t n) {
    if (!g_postOk || !g_experimental) { Out(o, n, "INSTANCE_Post not verified / experimental off"); return false; }
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    Post(inst, 7, 0);                        // TRLAU modules/Instance.cpp: message 7, data 0 = unhide
    Out(o, n, "INSTANCE_Post(0x%08lx, 7, 0)", inst);
    return true;
}
bool RunUnhideAll(const char *, char *o, size_t n) {
    if (!g_postOk || !g_experimental || !InLevel()) { Out(o, n, "needs a level / INSTANCE_Post / experimental"); return false; }
    DWORD list[4096];
    int count = 0;
    ForInstances([&](const InstInfo &x) { list[count++] = x.addr; return true; });
    for (int i = 0; i < count; ++i) Post(list[i], 7, 0);
    Out(o, n, "message 7 posted to %d instances", count);
    return true;
}
bool RunRemove(const char *arg, char *o, size_t n) {
    if (!g_removeOk || !g_experimental) { Out(o, n, "INSTANCE_ReallyRemoveInstance not verified / experimental off"); return false; }
    DWORD inst = FindInstance(arg, o, n), player = 0;
    if (!inst) return false;
    ReadDword(kPlayerPtr, &player);
    if (inst == player) { Out(o, n, "refused: that is the player"); return false; }
    reinterpret_cast<RemoveFn>(kRemoveInstance)(reinterpret_cast<void *>(inst), 0, 0);
    Out(o, n, "INSTANCE_ReallyRemoveInstance(0x%08lx, 0, 0)", inst);
    return true;
}

// ---- costume live: GlobalInfo list + the game's switch 0x6f0a90 ----
// 0x6f0a90 (reached from the costume native 0x79db50 -> 0x778ca0): if altPlayerObjectID [0xe7f1cc] != 0 it becomes
// the current costume [0xe7f1c8], else the id after the player's object id in GlobalInfo [0xe7ee50]+4 (wraps).
// TRLAU then posts message 35 to the player (re-birth the weapons) one frame later.
int GlobalCostumes(WORD *ids, int max) {
    DWORD gi = 0, list = 0, arr = 0;
    WORD count = 0;
    if (!ReadDword(kGlobalInfo, &gi) || !gi || !ReadDword(gi + 4, &list) || !list || !ReadWord(list, &count) ||
        !ReadDword(list + 4, &arr) || !arr)
        return -1;
    int c = count < max ? count : max;
    for (int i = 0; i < c; ++i)
        if (!ReadWord(arr + static_cast<DWORD>(i) * 2, &ids[i])) return i;
    return c;
}
void ValGlobalCostumes(char *o, size_t n) {
    WORD ids[128];
    int c = GlobalCostumes(ids, 128);
    if (c < 0) { Out(o, n, "no GlobalInfo [0x%08lx]", kGlobalInfo); return; }
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < c; ++i) {
        char name[64];
        if (!ObjectName(ids[i], name, sizeof(name))) Out(name, sizeof(name), "?");
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%u %s", used ? "; " : "", ids[i], name);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!c) Out(o, n, "empty list");
}
bool SwitchCostume(int id, char *o, size_t n) {
    if (!g_switchOk || !g_postOk || !g_experimental) { Out(o, n, "costume switch not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    *reinterpret_cast<volatile DWORD *>(kAltPlayerObject) = static_cast<DWORD>(id);
    reinterpret_cast<VoidFn>(kCostumeSwitch)();
    InterlockedExchange(&g_weaponsPending, 2);   // INSTANCE_Post(player, 35, 0) two game frames later
    DWORD now = 0;
    ReadDword(kCostumeNow, &now);
    char cur[96];
    IdName(static_cast<int>(now), cur, sizeof(cur));
    Out(o, n, "costume switched (0x%08lx, alt %d): current %s; weapons message 35 next frame", kCostumeSwitch, id, cur);
    return true;
}
bool RunCostumeNext(const char *, char *o, size_t n) { return SwitchCostume(0, o, n); }
bool RunCostumeLive(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: costume.set <object name | object id> (live switch)"); return false; }
    char *end = nullptr;
    long id = strtol(arg, &end, 10);
    if (*end) id = ObjectId(arg);
    if (id <= 0) { Out(o, n, "'%s' is not in the object list", arg); return false; }
    if (g_costumeOk && !reinterpret_cast<CostumeValidFn>(kCostumeValid)(static_cast<int>(id))) {
        Out(o, n, "object %ld refused by the game's check 0x%08lx (no .drm?)", id, kCostumeValid);
        return false;
    }
    return SwitchCostume(static_cast<int>(id), o, n);
}
void WeaponsTick() {
    if (!g_weaponsPending || InterlockedDecrement(&g_weaponsPending) > 0) return;
    DWORD player = 0;
    if (g_postOk && ReadDword(kPlayerPtr, &player) && player) {
        Post(player, 35, 0);
        Log(2, "costume: INSTANCE_Post(player, 35, 0)");
    }
}

// ---- log page: tail of the Tru*.log files (once per second, worker thread) + the game's script prints ----
// 0.4: text = the line without its leading time stamp; stamp = "HH:MM:SS.mmm" of the first occurrence (from the line,
// or the local time for lines without one), last = of the latest repeat, count = repeats collapsed into this entry;
// src[0] == 0 marks an entry that was moved to the head by a repeat
struct LogLine { char src[20]; char stamp[16]; char last[16]; char text[220]; int count; BYTE sev; bool hadStamp; };
const int kLogRing = 512;
LogLine g_logRing[kLogRing];
int g_logHead = 0, g_logTotal = 0;
CRITICAL_SECTION g_logRingLock;
struct TailFile { char name[24]; char path[MAX_PATH]; LONGLONG offset; bool used; };
TailFile g_tails[16];
volatile LONG g_logOverlay = 0;
int g_logLines = 12;
char g_logFilter[24] = "";                   // "" = all, else a source name (TruLink, script, ...)
volatile LONG g_scriptLog = 0;               // script print natives redirected
bool g_scriptOk = false;
char g_scriptPartial[220];
size_t g_scriptPartialLen = 0;
LONG g_scriptCount = 0;

// 0.4: per-source rate limit ([Log] MaxLinesPerSecond) and counters
struct SrcRate { char src[20]; DWORD second; int count; LONG dropped; };
SrcRate g_rates[24];
LONG g_logDropped = 0, g_logHidden = 0, g_logCollapsed = 0;
bool IsInfoItem(const char *id);             // defined after kItems

// 2 error, 1 warning, 0 info - by words in the line (the plugins write no level field)
BYTE LineSeverity(const char *t) {
    const char *const errors[] = {"fail", "FAIL", "error", "Error", "ERROR", "exception", "Exception", " NO ", "-> err ",
                                  "crash"};
    for (const char *w : errors)
        if (strstr(t, w)) return 2;
    if (strncmp(t, "err ", 4) == 0) return 2;
    const char *const warnings[] = {"warn", "Warn", "WARN", "not match", "mismatch", "busy", "refused", "unreadable",
                                    "timeout", "timed out", "missing", "skipped", "not verified"};
    for (const char *w : warnings)
        if (strstr(t, w)) return 1;
    return 0;
}

// "HH:MM:SS" or "HH:MM:SS.mmm" followed by a space at the start; returns its length (0 = none)
size_t StampLength(const char *t) {
    for (int i = 0; i < 8; ++i) {
        bool colon = i == 2 || i == 5;
        if (colon ? t[i] != ':' : !isdigit(static_cast<unsigned char>(t[i]))) return 0;
    }
    size_t len = 8;
    if (t[8] == '.' && isdigit(static_cast<unsigned char>(t[9])) && isdigit(static_cast<unsigned char>(t[10])) &&
        isdigit(static_cast<unsigned char>(t[11])))
        len = 12;
    return t[len] == ' ' ? len : 0;
}

// TruLink's echo of a read-type command ("> read32 ...", "> scan ...", "> watch ...", "> ping") and its "menu" lines
// for info items ("> menu status.state", "menu test.list  -> ok ...")
bool IsLinkRead(const char *src, const char *body) {
    if (_stricmp(src, "TruLink") != 0) return false;
    bool echo = body[0] == '>' && body[1] == ' ';
    const char *p = echo ? body + 2 : body;
    char word[24] = "", id[64] = "";
    sscanf_s(p, "%23s %63s", word, static_cast<unsigned>(sizeof(word)), id, static_cast<unsigned>(sizeof(id)));
    if (echo && (_strnicmp(word, "read", 4) == 0 || _strnicmp(word, "scan", 4) == 0 || _strnicmp(word, "watch", 5) == 0 ||
                 _stricmp(word, "ping") == 0))
        return true;
    if (_stricmp(word, "menu") != 0) return false;
    return _strnicmp(id, "status.", 7) == 0 || _stricmp(id, "list") == 0 || IsInfoItem(id);
}

// g_logRingLock held
void PutLine(const LogLine &l) {
    g_logRing[g_logHead] = l;
    g_logHead = (g_logHead + 1) % kLogRing;
    if (g_logTotal < kLogRing) ++g_logTotal;
}

// g_logRingLock held: a "(n lines dropped)" line for every source whose second is over
void FlushDropsLocked(DWORD second) {
    for (SrcRate &r : g_rates) {
        if (!r.src[0] || r.second == second || !r.dropped) continue;
        LogLine l = {};
        strncpy_s(l.src, sizeof(l.src), r.src, _TRUNCATE);
        SYSTEMTIME t;
        GetLocalTime(&t);
        _snprintf_s(l.stamp, sizeof(l.stamp), _TRUNCATE, "%02d:%02d:%02d.%03d", t.wHour, t.wMinute, t.wSecond,
                    t.wMilliseconds);
        strncpy_s(l.last, sizeof(l.last), l.stamp, _TRUNCATE);
        _snprintf_s(l.text, sizeof(l.text), _TRUNCATE, "(%ld lines dropped: more than %d per second, [Log] "
                    "MaxLinesPerSecond / log.rate)", r.dropped, g_logRate);
        l.count = 1;
        l.sev = 1;
        PutLine(l);
        r.dropped = 0;
    }
}

void PushLine(const char *src, const char *text) {
    if (strstr(text, "exception") || strstr(text, "Exception")) InterlockedIncrement(&g_exceptionLines);
    LogLine l = {};
    strncpy_s(l.src, sizeof(l.src), src, _TRUNCATE);
    const char *body = text;
    size_t stamp = StampLength(text);
    if (stamp) {
        memcpy(l.stamp, text, stamp);
        l.stamp[stamp] = 0;
        l.hadStamp = true;
        body = text + stamp;
        while (*body == ' ') ++body;
    } else {
        SYSTEMTIME t;
        GetLocalTime(&t);
        _snprintf_s(l.stamp, sizeof(l.stamp), _TRUNCATE, "%02d:%02d:%02d.%03d", t.wHour, t.wMinute, t.wSecond,
                    t.wMilliseconds);
    }
    if (g_logHideReads && IsLinkRead(l.src, body)) { InterlockedIncrement(&g_logHidden); return; }
    strncpy_s(l.text, sizeof(l.text), body, _TRUNCATE);
    strncpy_s(l.last, sizeof(l.last), l.stamp, _TRUNCATE);
    l.count = 1;
    l.sev = LineSeverity(body);
    DWORD second = GetTickCount() / 1000;
    EnterCriticalSection(&g_logRingLock);
    FlushDropsLocked(second);
    // collapse: the newest line of the same source has the same text -> count it there and move it to the head
    if (g_logCollapse) {
        for (int k = 0; k < g_logTotal && k < 64; ++k) {
            LogLine &o = g_logRing[(g_logHead - 1 - k + kLogRing) % kLogRing];
            if (!o.src[0] || _stricmp(o.src, l.src) != 0) continue;
            if (strcmp(o.text, l.text) == 0) {
                l.count = o.count + 1;
                strncpy_s(l.stamp, sizeof(l.stamp), o.stamp, _TRUNCATE);
                l.hadStamp = o.hadStamp;
                l.sev = o.sev;
                if (k == 0) {
                    o = l;
                } else {
                    o.src[0] = 0;
                    PutLine(l);
                }
                ++g_logCollapsed;
                LeaveCriticalSection(&g_logRingLock);
                return;
            }
            break;
        }
    }
    // rate limit per source
    SrcRate *rate = nullptr;
    for (SrcRate &r : g_rates)
        if (r.src[0] && _stricmp(r.src, l.src) == 0) { rate = &r; break; }
    if (!rate)
        for (SrcRate &r : g_rates)
            if (!r.src[0]) { strncpy_s(r.src, sizeof(r.src), l.src, _TRUNCATE); r.second = second; rate = &r; break; }
    if (rate) {
        if (rate->second != second) { rate->second = second; rate->count = 0; }
        if (g_logRate > 0 && rate->count >= g_logRate) {
            ++rate->dropped;
            ++g_logDropped;
            LeaveCriticalSection(&g_logRingLock);
            return;
        }
        ++rate->count;
    }
    PutLine(l);
    LeaveCriticalSection(&g_logRingLock);
}

// worker thread, once per second: the "(n lines dropped)" line also when the source stays quiet afterwards
void FlushDrops() {
    EnterCriticalSection(&g_logRingLock);
    FlushDropsLocked(GetTickCount() / 1000);
    LeaveCriticalSection(&g_logRingLock);
}

// one shown line: "[src] stamp text", collapsed: "[src] text x42 (17:09:02-17:09:33)"
void FormatLine(const LogLine &l, char *o, size_t n, size_t maxText) {
    if (l.count > 1)
        _snprintf_s(o, n, _TRUNCATE, "[%s] %.*s x%d (%.8s-%.8s)", l.src, static_cast<int>(maxText), l.text, l.count,
                    l.stamp, l.last);
    else if (l.hadStamp)
        _snprintf_s(o, n, _TRUNCATE, "[%s] %s %.*s", l.src, l.stamp, static_cast<int>(maxText), l.text);
    else
        _snprintf_s(o, n, _TRUNCATE, "[%s] %.*s", l.src, static_cast<int>(maxText), l.text);
}

// the last <max> lines matching the filter and [Log] MinLevel, oldest first; returns the count
int CopyLines(LogLine *out, int max, const char *filter) {
    int c = 0;
    EnterCriticalSection(&g_logRingLock);
    for (int k = 0; k < g_logTotal && c < max; ++k) {
        const LogLine &l = g_logRing[(g_logHead - 1 - k + kLogRing) % kLogRing];
        if (!l.src[0] || l.sev < g_logMinLevel) continue;
        if (filter && filter[0] && _stricmp(l.src, filter) != 0) continue;
        out[c++] = l;
    }
    LeaveCriticalSection(&g_logRingLock);
    for (int i = 0; i < c / 2; ++i) { LogLine t = out[i]; out[i] = out[c - 1 - i]; out[c - 1 - i] = t; }
    return c;
}

void TailOne(TailFile &t, bool first) {
    HANDLE h = CreateFileA(t.path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER size = {};
    GetFileSizeEx(h, &size);
    if (size.QuadPart < t.offset) t.offset = 0;                 // file was recreated
    LONGLONG from = t.offset;
    if (size.QuadPart - from > 6000) from = size.QuadPart - 6000;  // never more than the last ~6 KB
    if (first && size.QuadPart - from > 2000) from = size.QuadPart - 2000;
    if (size.QuadPart > from) {
        static char buf[6200];
        LARGE_INTEGER pos;
        pos.QuadPart = from;
        DWORD got = 0;
        if (SetFilePointerEx(h, pos, nullptr, FILE_BEGIN) &&
            ReadFile(h, buf, static_cast<DWORD>(size.QuadPart - from), &got, nullptr)) {
            buf[got] = 0;
            char *p = buf;
            if (from != t.offset) { char *nl = strchr(p, '\n'); p = nl ? nl + 1 : p + got; }  // skip a cut line
            DWORD consumed = got;
            char *lastNl = strrchr(p, '\n');
            if (lastNl) consumed = static_cast<DWORD>(lastNl + 1 - buf); else consumed = static_cast<DWORD>(p - buf);
            if (lastNl) *lastNl = 0;
            char *context = nullptr;
            if (lastNl)
                for (char *line = strtok_s(p, "\r\n", &context); line; line = strtok_s(nullptr, "\r\n", &context))
                    PushLine(t.name, line);
            t.offset = from + consumed;
        }
    }
    CloseHandle(h);
}

void TailDir(const char *dir) {
    char pattern[MAX_PATH];
    _snprintf_s(pattern, sizeof(pattern), _TRUNCATE, "%sTru*.log", dir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pattern, &fd);
    if (f == INVALID_HANDLE_VALUE) return;
    do {
        char path[MAX_PATH];
        _snprintf_s(path, sizeof(path), _TRUNCATE, "%s%s", dir, fd.cFileName);
        int slot = -1;
        for (int i = 0; i < 16; ++i)
            if (g_tails[i].used && _stricmp(g_tails[i].path, path) == 0) { slot = i; break; }
        bool first = false;
        if (slot < 0) {
            for (int i = 0; i < 16 && slot < 0; ++i)
                if (!g_tails[i].used) slot = i;
            if (slot < 0) continue;
            TailFile &t = g_tails[slot];
            t.used = true;
            t.offset = 0;
            strncpy_s(t.path, sizeof(t.path), path, _TRUNCATE);
            strncpy_s(t.name, sizeof(t.name), fd.cFileName, _TRUNCATE);
            char *dot = strrchr(t.name, '.');
            if (dot) *dot = 0;
            first = true;
        }
        TailOne(g_tails[slot], first);
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}

void LogTailTick() {
    static DWORD last = 0;
    DWORD now = GetTickCount();
    if (now - last < 1000) return;
    last = now;
    TailDir(g_asiDir);
    FlushDrops();
    if (_stricmp(g_asiDir, g_exeDir) != 0) TailDir(g_exeDir);
}

// script print natives of NsCoreBase (registered as natives 0..7 at 0x7b3920..0x7b399e, cdecl (instance, numArgs,
// DataValue *args), 4 bytes per argument). In retail they end in empty functions (0x574be0 / 0x7987b0: ret) or in
// sprintf into a stack buffer that is dropped (0x4a3200 .. 0x4a32c0). TruMenu replaces their first 5 bytes with a
// jmp to the handlers below while log.script is on.
struct ScriptNative { DWORD addr; const char *bytes; int kind; BYTE saved[5]; };
enum { kSnInt, kSnBool, kSnFloat, kSnString };
ScriptNative g_natives[] = {
    {0x00795d30, "8b44240c 80780800 d94004 8b10", kSnInt, {}},          // print int (value, time, newline)
    {0x00795d50, "8b44240c 80780800 d94004 0f95c1 803800", kSnBool, {}}, // print bool
    {0x00795d80, "8b44240c 80780800 d94004 0f95c1 51 8b4c2408", kSnFloat, {}},  // print float
    {0x00795db0, "8b44240c 80780800 d94004 0f95c1 51 51 8b4c240c", kSnString, {}},  // print string
    {0x00795dd0, "8b44240c 80780400 8b10 0f95c1", kSnInt, {}},          // log int (value, newline)
    {0x00795df0, "8b44240c 80780400 0f95c1 803800", kSnBool, {}},       // log bool
    {0x00795e10, "8b44240c 80780400 d900 0f95c1", kSnFloat, {}},        // log float
    {0x00795e30, "8b44240c 80780400 0f95c1 51 8b4c2408 50", kSnString, {}},  // log string
};
const int kNativeCount = sizeof(g_natives) / sizeof(g_natives[0]);

void ScriptText(const char *text, bool newline) {
    for (const char *p = text; *p; ++p) {
        if (*p == '\n' || g_scriptPartialLen + 1 >= sizeof(g_scriptPartial)) {
            g_scriptPartial[g_scriptPartialLen] = 0;
            PushLine("script", g_scriptPartial);
            g_scriptPartialLen = 0;
            if (*p == '\n') continue;
        }
        if (*p != '\r') g_scriptPartial[g_scriptPartialLen++] = *p;
    }
    if (newline) {
        g_scriptPartial[g_scriptPartialLen] = 0;
        PushLine("script", g_scriptPartial);
        g_scriptPartialLen = 0;
    }
    ++g_scriptCount;
}

// a string DataValue: a char* or a pointer to one (not verified - both are tried, read under __try)
void ScriptString(DWORD *args, char *out, size_t size) {
    DWORD v = 0, w = 0;
    out[0] = 0;
    if (!ReadDword(reinterpret_cast<DWORD>(args), &v) || !v) return;
    char a[200];
    if (ReadString(v, a, sizeof(a)) && a[0] && isprint(static_cast<unsigned char>(a[0]))) {
        strncpy_s(out, size, a, _TRUNCATE);
        return;
    }
    if (ReadDword(v, &w) && w && ReadString(w, a, sizeof(a))) strncpy_s(out, size, a, _TRUNCATE);
}

void ScriptNativeCall(int kind, int argsWithTime, DWORD *args) {
    char text[220];
    bool newline = false;
    __try {
        int nlIndex = argsWithTime ? 2 : 1;
        newline = reinterpret_cast<BYTE *>(args)[4 * nlIndex] != 0;
        switch (kind) {
        case kSnInt: Out(text, sizeof(text), "%ld", static_cast<LONG>(args[0])); break;
        case kSnBool: Out(text, sizeof(text), "%s", reinterpret_cast<BYTE *>(args)[0] ? "true" : "false"); break;
        case kSnFloat: Out(text, sizeof(text), "%g", static_cast<double>(*reinterpret_cast<float *>(&args[0]))); break;
        default: ScriptString(args, text, sizeof(text)); break;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(text, sizeof(text), "(unreadable script argument)");
    }
    ScriptText(text, newline);
}
void __cdecl SnPrintInt(void *, int, DWORD *a) { ScriptNativeCall(kSnInt, 1, a); }
void __cdecl SnPrintBool(void *, int, DWORD *a) { ScriptNativeCall(kSnBool, 1, a); }
void __cdecl SnPrintFloat(void *, int, DWORD *a) { ScriptNativeCall(kSnFloat, 1, a); }
void __cdecl SnPrintString(void *, int, DWORD *a) { ScriptNativeCall(kSnString, 1, a); }
void __cdecl SnLogInt(void *, int, DWORD *a) { ScriptNativeCall(kSnInt, 0, a); }
void __cdecl SnLogBool(void *, int, DWORD *a) { ScriptNativeCall(kSnBool, 0, a); }
void __cdecl SnLogFloat(void *, int, DWORD *a) { ScriptNativeCall(kSnFloat, 0, a); }
void __cdecl SnLogString(void *, int, DWORD *a) { ScriptNativeCall(kSnString, 0, a); }
typedef void(__cdecl *SnFn)(void *, int, DWORD *);
const SnFn kSnHandlers[] = {SnPrintInt, SnPrintBool, SnPrintFloat, SnPrintString,
                            SnLogInt, SnLogBool, SnLogFloat, SnLogString};

// game thread: patch / restore the natives (the scripts run on the game thread, so none is running now)
bool SetScriptLog(bool on, char *o, size_t n) {
    if (!g_scriptOk) { Out(o, n, "script natives did not match at load - log.script off"); return false; }
    if (on == (g_scriptLog != 0)) { Out(o, n, "log.script %d (unchanged)", on ? 1 : 0); return true; }
    for (int i = 0; i < kNativeCount; ++i) {
        ScriptNative &s = g_natives[i];
        if (on) {
            BYTE jmp[5] = {0xe9};
            DWORD rel = reinterpret_cast<DWORD>(kSnHandlers[i]) - (s.addr + 5);
            memcpy(jmp + 1, &rel, 4);
            memcpy(s.saved, reinterpret_cast<const void *>(s.addr), 5);
            if (!WriteBytes(s.addr, jmp, 5)) { Out(o, n, "patch of 0x%08lx failed", s.addr); return false; }
        } else {
            WriteBytes(s.addr, s.saved, 5);
        }
    }
    InterlockedExchange(&g_scriptLog, on ? 1 : 0);
    Out(o, n, "log.script %d (%d NsCoreBase print / log natives %s)", on ? 1 : 0, kNativeCount,
        on ? "redirected to the log page" : "restored");
    Log(1, "%s", o);
    return true;
}
bool RunScriptLog(const char *arg, char *o, size_t n) { return SetScriptLog(BoolArg(arg, g_scriptLog != 0), o, n); }
void ValScriptLog(char *o, size_t n) { Out(o, n, "%d (%ld prints)", g_scriptLog ? 1 : 0, g_scriptCount); }

void LinesText(const char *filter, int max, char *o, size_t n) {
    static LogLine lines[64];                // only called from one thread at a time in practice (menu / TruLink)
    if (max > 64) max = 64;
    int c = CopyLines(lines, max, filter);
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < c; ++i) {
        char line[300];
        FormatLine(lines[i], line, sizeof(line), 220);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " | " : "", line);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!c) Out(o, n, "no lines");
}
void ValLogPage(char *o, size_t n) { LinesText(g_logFilter, g_logLines, o, n); }
void ValScriptLines(char *o, size_t n) { LinesText("script", g_logLines, o, n); }
void ValLogOverlay(char *o, size_t n) { Out(o, n, "%d", g_logOverlay ? 1 : 0); }
bool RunLogOverlay(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logOverlay != 0);
    InterlockedExchange(&g_logOverlay, on ? 1 : 0);
    Out(o, n, "log.overlay %d", on ? 1 : 0);
    return true;
}
void ValLogLines(char *o, size_t n) { Out(o, n, "%d", g_logLines); }
bool RunLogLines(const char *arg, char *o, size_t n) {
    int v = arg ? atoi(arg) : 0;
    if (v < 1 || v > 64) { Out(o, n, "usage: log.lines <1..64>"); return false; }
    g_logLines = v;
    Out(o, n, "log.lines %d", v);
    return true;
}
void ValLogFilter(char *o, size_t n) { Out(o, n, "%s", g_logFilter[0] ? g_logFilter : "all"); }
bool RunLogFilter(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0] || _stricmp(arg, "all") == 0) g_logFilter[0] = 0;
    else strncpy_s(g_logFilter, sizeof(g_logFilter), arg, _TRUNCATE);
    Out(o, n, "log.filter %s", g_logFilter[0] ? g_logFilter : "all");
    return true;
}
void ValLogCount(char *o, size_t n) {
    Out(o, n, "%d lines, %ld exception lines, %ld caught by TruMenu; 0.4: %ld repeats collapsed, %ld TruLink reads hidden, "
        "%ld dropped by the rate limit", g_logTotal, g_exceptionLines, g_ownExceptions, g_logCollapsed, g_logHidden,
        g_logDropped);
}
// 0.4 log options (also [Log] Collapse / HideLinkReads / MinLevel / MaxLinesPerSecond)
void ValLogCollapse(char *o, size_t n) { Out(o, n, "%d", g_logCollapse ? 1 : 0); }
bool RunLogCollapse(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logCollapse != 0);
    InterlockedExchange(&g_logCollapse, on ? 1 : 0);
    Out(o, n, "log.collapse %d (new lines; %ld repeats collapsed so far)", on ? 1 : 0, g_logCollapsed);
    return true;
}
void ValLogHideReads(char *o, size_t n) { Out(o, n, "%d", g_logHideReads ? 1 : 0); }
bool RunLogHideReads(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logHideReads != 0);
    InterlockedExchange(&g_logHideReads, on ? 1 : 0);
    Out(o, n, "log.hidereads %d (new lines; %ld hidden so far)", on ? 1 : 0, g_logHidden);
    return true;
}
const char *const kLevelNames[] = {"all", "warn", "error"};
void ValLogLevel(char *o, size_t n) { Out(o, n, "%d (%s)", g_logMinLevel, kLevelNames[g_logMinLevel]); }
bool RunLogLevel(const char *arg, char *o, size_t n) {
    int v = -1;
    if (arg && (_stricmp(arg, "all") == 0 || _stricmp(arg, "info") == 0)) v = 0;
    else if (arg && _strnicmp(arg, "warn", 4) == 0) v = 1;
    else if (arg && _strnicmp(arg, "err", 3) == 0) v = 2;
    else if (arg && isdigit(static_cast<unsigned char>(arg[0]))) v = atoi(arg);
    if (v < 0 || v > 2) { Out(o, n, "usage: log.level 0|1|2 (all | warn | error)"); return false; }
    g_logMinLevel = v;
    Out(o, n, "log.level %d (%s)", v, kLevelNames[v]);
    return true;
}
void ValLogRate(char *o, size_t n) { Out(o, n, "%d (%ld dropped)", g_logRate, g_logDropped); }
bool RunLogRate(const char *arg, char *o, size_t n) {
    if (!arg || !isdigit(static_cast<unsigned char>(arg[0])) || atoi(arg) > 10000) {
        Out(o, n, "usage: log.rate <lines per source and second, 0 = no limit>");
        return false;
    }
    g_logRate = atoi(arg);
    Out(o, n, "log.rate %d", g_logRate);
    return true;
}
bool RunLogClear(const char *, char *o, size_t n) {
    EnterCriticalSection(&g_logRingLock);
    g_logTotal = 0;
    LeaveCriticalSection(&g_logRingLock);
    Out(o, n, "log cleared");
    return true;
}

// ---- videos: Movies\*.bik next to tru.exe, played with 0x4a12b0(name, loop) ----
void ValVideoList(char *o, size_t n) {
    char pattern[MAX_PATH];
    _snprintf_s(pattern, sizeof(pattern), _TRUNCATE, "%sMovies\\*.bik", g_exeDir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pattern, &fd);
    size_t used = 0;
    o[0] = 0;
    if (f == INVALID_HANDLE_VALUE) { Out(o, n, "no Movies\\*.bik next to tru.exe"); return; }
    do {
        char name[MAX_PATH];
        strncpy_s(name, sizeof(name), fd.cFileName, _TRUNCATE);
        char *dot = strrchr(name, '.');
        if (dot) *dot = 0;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " " : "", name);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}
bool VideoName(const char *arg, char *name, size_t size, char *o, size_t n) {
    if (!arg || !arg[0] || strlen(arg) > 48) { Out(o, n, "give a video name (media.video.list)"); return false; }
    strncpy_s(name, size, arg, _TRUNCATE);
    char *dot = strrchr(name, '.');
    if (dot && _stricmp(dot, ".bik") == 0) *dot = 0;
    for (const char *p = name; *p; ++p)
        if (!(isalnum(static_cast<unsigned char>(*p)) || *p == '_' || *p == '-')) { Out(o, n, "name: a-z 0-9 _ - only"); return false; }
    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sMovies\\%s.bik", g_exeDir, name);
    if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) { Out(o, n, "no Movies\\%s.bik", name); return false; }
    return true;
}
bool RunVideoPlay(const char *arg, char *o, size_t n) {
    if (!g_movieOk || !g_mainStateOk || !g_experimental) { Out(o, n, "movie player not verified / experimental off"); return false; }
    static char name[64];
    if (!VideoName(arg, name, sizeof(name), o, n)) return false;
    DWORD state = 0;
    ReadDword(kMainState, &state);
    // catalog 11.1: the player is a blocking-style one; only from the front end (TRLAU main state 10 = main menu)
    if (state != 10) { Out(o, n, "front end only (main state [0x%08lx] = %lu, needs 10)", kMainState, state); return false; }
    reinterpret_cast<MoviePlayFn>(kMoviePlay)(name, false);
    Out(o, n, "0x%08lx(\"%s\", 0) called", kMoviePlay, name);
    return true;
}
void ValMenuLoop(char *o, size_t n) {
    DWORD p = 0;
    char s[64] = "";
    if (ReadDword(kMenuLoopPtr, &p)) ReadString(p, s, sizeof(s));
    Out(o, n, "%s", s[0] ? s : "?");
}
bool RunMenuLoop(const char *arg, char *o, size_t n) {
    if (!g_menuLoopOk || !g_experimental) { Out(o, n, "menu loop pointer not verified / experimental off"); return false; }
    if (!arg || !arg[0]) {
        *reinterpret_cast<volatile DWORD *>(kMenuLoopPtr) = kMenuLoopOrig;
        Out(o, n, "menu background back to medsea_loop");
        return true;
    }
    char name[64];
    if (!VideoName(arg, name, sizeof(name), o, n)) return false;
    strncpy_s(g_menuLoopName, sizeof(g_menuLoopName), name, _TRUNCATE);
    *reinterpret_cast<volatile DWORD *>(kMenuLoopPtr) = reinterpret_cast<DWORD>(g_menuLoopName);
    Out(o, n, "menu background loop = %s (0x%08lx; used when the main menu starts its movie again)", name, kMenuLoopPtr);
    return true;
}

// ---- draw.markup / draw.ledges (experimental, read-only): the markup boxes projected like the game's
// TRANS_RotTransPersVectorf 0x49f630 and drawn into ImGui's background draw list ----
// Facts (static, tru.exe): MarkupManager [0xdb94cc] (a vtable object); 0x5c3ce0 (called with ecx = [0xdb94cc] at
// 0x5d3349) walks its boxes: box = [mgr+0x14], next = [box+4]; box +0x20 MarkUp*, +0x28 flags (bits 19 / 20 tested
// there); MarkUp +0x34 position (x y z), +0x58 poly line {int count; points at +0x10 + 16*i}. All of them are moved by
// that function's world shift, so they are world coordinates. Projection 0x49f630: view = M * p with M = 4 columns of
// 16 bytes at 0xa038f0 (column 3 = translation); x' = x / z * f + 256, y' = y / z * f + 224, f = float [0x8906d0]
// (512.0 in the file); TRLAU draws only when z > 16. The 512 x 448 screen space is a reading of those constants and is
// scaled to the back buffer here (draw.scale) - to verify live. Flag bit names are the catalog's (TRLAU Markup.h,
// 30 ledge grab, 27..25 poles, 22 ladder, 20 water, 19 rope) and are not verified for box +0x28.
const DWORD kMarkupMgr = 0x00db94cc, kViewMatrix = 0x00a038f0, kFocal = 0x008906d0;
const DWORD kCentreX = 0x00843a00, kCentreY = 0x008454c8;   // doubles 256.0 / 224.0
bool g_drawOk = false;
volatile LONG g_drawMarkup = 0, g_drawLedges = 0;
float g_drawW = 512.0f, g_drawH = 448.0f;
int g_drawnBoxes = 0;

struct View { float m[16]; float f; double cx, cy; float sx, sy; };

bool ReadView(View *v, float width, float height) {
    if (!ReadFloats(kViewMatrix, v->m, 16) || !ReadFloats(kFocal, &v->f, 1)) return false;
    __try {
        v->cx = *reinterpret_cast<const double *>(kCentreX);
        v->cy = *reinterpret_cast<const double *>(kCentreY);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    v->sx = width / g_drawW;
    v->sy = height / g_drawH;
    return v->f > 0.0f;
}

bool Project(const View &v, const float *p, ImVec2 *out) {
    const float *m = v.m;
    float x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12];
    float y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
    float z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14];
    if (!(z > 16.0f)) return false;
    out->x = static_cast<float>(x / z * v.f + v.cx) * v.sx;
    out->y = static_cast<float>(y / z * v.f + v.cy) * v.sy;
    return out->x > -4000.0f && out->x < 8000.0f && out->y > -4000.0f && out->y < 8000.0f;
}

ImU32 MarkupColour(DWORD flags) {
    if (flags & (1u << 30)) return IM_COL32(255, 220, 40, 230);    // ledge grab
    if (flags & (1u << 22)) return IM_COL32(60, 230, 90, 230);     // ladder
    if (flags & (7u << 25)) return IM_COL32(60, 220, 230, 230);    // poles
    if (flags & (1u << 20)) return IM_COL32(60, 120, 255, 230);    // water
    if (flags & (1u << 19)) return IM_COL32(230, 120, 40, 230);    // rope
    return IM_COL32(200, 200, 200, 160);
}

void DrawMarkup() {
    if (!g_drawOk || !InLevel()) return;
    ImGuiIO &io = ImGui::GetIO();
    View v;
    if (!ReadView(&v, io.DisplaySize.x, io.DisplaySize.y)) return;
    ImDrawList *dl = ImGui::GetBackgroundDrawList();
    DWORD mgr = 0, box = 0;
    if (!ReadDword(kMarkupMgr, &mgr) || !mgr || !ReadDword(mgr + 0x14, &box)) return;
    int drawn = 0;
    for (int guard = 0; box && guard < 4000; ++guard) {
        DWORD flags = 0, markup = 0, line = 0, next = 0;
        ReadDword(box + 0x28, &flags);
        ReadDword(box + 0x20, &markup);
        if (!ReadDword(box + 4, &next)) break;
        bool ledge = (flags & (1u << 30)) != 0;
        if (markup && (!g_drawLedges || ledge)) {
            ImU32 colour = MarkupColour(flags);
            float pos[3];
            DWORD count = 0;
            ImVec2 a, b;
            bool havePoly = ReadDword(markup + 0x58, &line) && line && ReadDword(line, &count) && count >= 2 && count <= 64;
            if (havePoly) {
                float p0[3], p1[3];
                bool ok0 = ReadFloats(line + 0x10, p0, 3) && Project(v, p0, &a);
                for (DWORD i = 1; i < count; ++i) {
                    bool ok1 = ReadFloats(line + 0x10 + 16 * i, p1, 3) && Project(v, p1, &b);
                    if (ok0 && ok1) dl->AddLine(a, b, colour, 2.0f);
                    a = b;
                    ok0 = ok1;
                }
                ++drawn;
            } else if (ReadFloats(markup + 0x34, pos, 3) && Project(v, pos, &a)) {
                dl->AddCircle(a, 5.0f, colour, 8, 2.0f);
                ++drawn;
            }
        }
        box = next;
    }
    g_drawnBoxes = drawn;
}

void ValDrawMarkup(char *o, size_t n) { Out(o, n, "%d (%d boxes drawn)", g_drawMarkup ? 1 : 0, g_drawnBoxes); }
void ValDrawLedges(char *o, size_t n) { Out(o, n, "%d", g_drawLedges ? 1 : 0); }
bool RunDrawMarkup(const char *arg, char *o, size_t n) {
    if (!g_drawOk) { Out(o, n, "markup / projection code not verified"); return false; }
    bool on = BoolArg(arg, g_drawMarkup != 0);
    InterlockedExchange(&g_drawMarkup, on ? 1 : 0);
    if (!on) InterlockedExchange(&g_drawLedges, 0);
    Out(o, n, "draw.markup %d", on ? 1 : 0);
    return true;
}
bool RunDrawLedges(const char *arg, char *o, size_t n) {
    if (!g_drawOk) { Out(o, n, "markup / projection code not verified"); return false; }
    bool on = BoolArg(arg, g_drawLedges != 0);
    InterlockedExchange(&g_drawLedges, on ? 1 : 0);
    if (on) InterlockedExchange(&g_drawMarkup, 1);
    Out(o, n, "draw.ledges %d (only boxes with flag bit 30)", on ? 1 : 0);
    return true;
}
void ValDrawScale(char *o, size_t n) { Out(o, n, "%.0f %.0f", g_drawW, g_drawH); }
bool RunDrawScale(const char *arg, char *o, size_t n) {
    float v[2];
    if (!ParseFloats(arg, v, 2) || !(v[0] >= 64.0f && v[0] <= 8192.0f && v[1] >= 64.0f && v[1] <= 8192.0f)) {
        Out(o, n, "usage: draw.scale <width> <height> of the game's projected space (default 512 448)");
        return false;
    }
    g_drawW = v[0];
    g_drawH = v[1];
    Out(o, n, "draw.scale %.0f %.0f", v[0], v[1]);
    return true;
}

// ---- weapons / ammo / health (experimental; catalog section 17, static facts, not yet checked live) ----
// playerstate P = [0xfadb58]; weapon manager WM = [P+0x500]; WM::GiveWeaponByName 0x7161f0 thiscall (name, a, b),
// the default loadout's call with (1, 0) - it polls the stream load queue until the object is loaded (blocking, game
// thread, in a level only); reserve ammo u16 P+0x51c+2*type (6 types, HUD reader 0x6e8475); health float P+0x628
// (GetHealth 0x6e7860); MaxHealth 0x6e7990 () -> float.
const DWORD kPlayerState = 0x00fadb58, kGiveWeapon = 0x007161f0, kMaxHealth = 0x006e7990;
typedef void(__fastcall *GiveWeaponFn)(void *wm, int, const char *name, int a, int b);   // thiscall via fastcall
typedef float(__cdecl *MaxHealthFn)();
bool g_weaponOk = false, g_ammoOk = false, g_healthOk = false;
volatile LONG g_invincible = 0;
struct WeaponName { int id; const char *name; };
const WeaponName kWeapons[] = {{37, "wp_handgun"}, {38, "wp_assault_rifle"}, {40, "wp_shotgun"}, {41, "wp_speargun"},
                               {42, "wp_thorhammer"}, {43, "wp_tranq"}, {44, "wp_uzi"}, {114, "wp_akrifle"}};

DWORD PlayerState() {
    DWORD p = 0;
    ReadDword(kPlayerState, &p);
    return p;
}
void ValWeaponList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (const WeaponName &w : kWeapons) {
        char name[64];
        bool listed = ObjectName(w.id, name, sizeof(name)) && _stricmp(name, w.name) == 0;
        int r = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d %s%s", used ? "; " : "", w.id, w.name,
                            listed ? "" : " (not in the object list)");
        if (r < 0) return;
        used += static_cast<size_t>(r);
    }
}
bool RunWeaponGive(const char *arg, char *o, size_t n) {
    if (!g_weaponOk || !g_experimental) { Out(o, n, "weapon code not verified / experimental off"); return false; }
    DWORD state = 0, p = PlayerState(), wm = 0;
    ReadDword(kMainState, &state);
    if (!InLevel() || state != 1 || !p || !ReadDword(p + 0x500, &wm) || !wm) {
        Out(o, n, "in a level only (main state %lu, needs 1; playerstate 0x%08lx, weapon manager 0x%08lx)", state, p, wm);
        return false;
    }
    if (!arg || !arg[0]) { Out(o, n, "usage: weapon.give <object name> (weapon.list)"); return false; }
    static char name[64];
    strncpy_s(name, sizeof(name), arg, _TRUNCATE);
    if (!ObjectId(name)) { Out(o, n, "'%s' is not in the object list", name); return false; }
    reinterpret_cast<GiveWeaponFn>(kGiveWeapon)(reinterpret_cast<void *>(wm), 0, name, 1, 0);
    Out(o, n, "WM::GiveWeaponByName 0x%08lx(\"%s\", 1, 0) on 0x%08lx done", kGiveWeapon, name, wm);
    return true;
}
void ValAmmo(char *o, size_t n) {
    DWORD p = PlayerState();
    WORD v[6] = {};
    if (!g_ammoOk || !p) { Out(o, n, "-"); return; }
    for (int i = 0; i < 6; ++i) ReadWord(p + 0x51c + 2 * i, &v[i]);
    Out(o, n, "%u %u %u %u %u %u", v[0], v[1], v[2], v[3], v[4], v[5]);
}
bool RunAmmoSet(const char *arg, char *o, size_t n) {
    if (!g_ammoOk || !g_experimental) { Out(o, n, "ammo code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    int type = -1, value = -1;
    if (!arg || sscanf_s(arg, "%d %d", &type, &value) != 2 || type < 0 || type > 5 || value < 0 || value > 9999) {
        Out(o, n, "usage: ammo.set <type 0..5> <n 0..9999>");
        return false;
    }
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    *reinterpret_cast<volatile WORD *>(p + 0x51c + 2 * type) = static_cast<WORD>(value);
    Out(o, n, "reserve ammo type %d = %d (playerstate 0x%08lx +0x%x)", type, value, p, 0x51c + 2 * type);
    return true;
}
void ValHealth(char *o, size_t n) {
    DWORD p = PlayerState();
    float h = 0.0f;
    if (g_healthOk && p && ReadFloats(p + 0x628, &h, 1)) Out(o, n, "%.2f", h); else Out(o, n, "-");
}
bool RunHealth(const char *arg, char *o, size_t n) {
    if (!g_healthOk || !g_experimental) { Out(o, n, "health code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    float max = reinterpret_cast<MaxHealthFn>(kMaxHealth)();
    float v = arg && arg[0] ? static_cast<float>(atof(arg)) : max;
    if (!(v > 0.0f && v < 100000.0f)) { Out(o, n, "usage: player.health <n > 0> (\"\" = max %.1f)", max); return false; }
    *reinterpret_cast<volatile float *>(p + 0x628) = v;
    Out(o, n, "health %.2f (max %.2f)", v, max);
    return true;
}
void ValInvincible(char *o, size_t n) { Out(o, n, "%d", g_invincible ? 1 : 0); }
bool RunInvincible(const char *arg, char *o, size_t n) {
    if (!g_healthOk || !g_experimental) { Out(o, n, "health code not verified / experimental off"); return false; }
    bool on = BoolArg(arg, g_invincible != 0);
    InterlockedExchange(&g_invincible, on ? 1 : 0);
    Out(o, n, "player.invincible %d (health = MaxHealth every frame; state deaths such as falls still kill)", on ? 1 : 0);
    return true;
}
// game thread, once per game frame (PadHook)
void InvincibleTick() {
    if (!g_invincible || !InLevel()) return;
    DWORD p = PlayerState();
    if (!p) return;
    __try {
        float max = reinterpret_cast<MaxHealthFn>(kMaxHealth)();
        if (max > 0.0f) *reinterpret_cast<volatile float *>(p + 0x628) = max;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        InterlockedExchange(&g_invincible, 0);
    }
}

// 0.4 (catalog 17.1 / 17.2 / 17.5, static facts, not yet checked live). Weapon slots: WM+4+0x10*slot = handle
// {instance, id} of the right hand, WM+0xC+0x10*slot the left hand, 15 slots (reader 0x6e7b90); a handle is valid when
// [instance+0x44] == handle id (the game's check 0x5b39d0, done here with our own reads); the weapon's object name is
// [[instance+0x10]+0x60] (as the gear callback 0x715ea2 reads it). MaxAmmo 0x6eeae0 cdecl (s8 type) -> u16 (0xffff for
// type > 5). GiveObject 0x555f60 cdecl (owner, objectId, callback, flag) with the save-restore callback 0x715e90, flag 1
// = WM::AddGear (17.1 step 5).
const DWORD kMaxAmmo = 0x006eeae0, kGiveObject = 0x00555f60, kGearCallback = 0x00715e90;
typedef unsigned short(__cdecl *MaxAmmoFn)(int type);
typedef void(__cdecl *GiveObjectFn)(DWORD owner, int objectId, DWORD callback, int flag);
bool g_slotsOk = false, g_maxAmmoOk = false, g_gearOk = false;

DWORD HandleInstance(DWORD handle) {
    DWORD inst = 0, id = 0, check = 0;
    if (!ReadDword(handle, &inst) || !inst || !ReadDword(handle + 4, &id) || !ReadDword(inst + 0x44, &check) || check != id)
        return 0;
    return inst;
}
bool InstanceObjectName(DWORD inst, char *out, size_t size) {
    DWORD object = 0, name = 0;
    out[0] = 0;
    return ReadDword(inst + 0x10, &object) && object && ReadDword(object + 0x60, &name) && name &&
           ReadString(name, out, size);
}
DWORD WeaponManager() {
    DWORD p = PlayerState(), wm = 0;
    if (!p || !InLevel() || !ReadDword(p + 0x500, &wm)) return 0;
    return wm;
}
// fn(slot, left, name) for every filled slot / hand
template <typename F> int ForWeaponSlots(DWORD wm, F fn) {
    int c = 0;
    for (int slot = 0; slot < 15; ++slot)
        for (int left = 0; left < 2; ++left) {
            DWORD inst = HandleInstance(wm + (left ? 0xc : 0x4) + 0x10 * slot);
            if (!inst) continue;
            char name[64];
            if (!InstanceObjectName(inst, name, sizeof(name))) strncpy_s(name, sizeof(name), "?", _TRUNCATE);
            fn(slot, left != 0, name);
            ++c;
        }
    return c;
}
void ValWeaponSlots(char *o, size_t n) {
    DWORD wm = WeaponManager();
    if (!g_slotsOk || !wm) { Out(o, n, g_slotsOk ? "needs a level" : "slot code not verified"); return; }
    DWORD selected = 0;
    ReadDword(wm + 0x138, &selected);
    size_t used = 0;
    o[0] = 0;
    int c = ForWeaponSlots(wm, [&](int slot, bool left, const char *name) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d%s %s", used ? "; " : "", slot, left ? "L" : "", name);
        if (w > 0) used += static_cast<size_t>(w);
    });
    _snprintf_s(o + used, n - used, _TRUNCATE, "%s(%d filled, selected slot %ld, WM 0x%08lx)", c ? " " : "no weapon ", c,
                static_cast<LONG>(selected), wm);
}
bool RunWeaponHas(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: weapon.has <object name> (weapon.list / weapon.slots)"); return false; }
    DWORD wm = WeaponManager();
    if (!g_slotsOk || !wm) { Out(o, n, g_slotsOk ? "needs a level" : "slot code not verified"); return false; }
    int found = -1;
    bool foundLeft = false;
    ForWeaponSlots(wm, [&](int slot, bool left, const char *name) {
        if (found < 0 && _stricmp(name, arg) == 0) { found = slot; foundLeft = left; }
    });
    if (found >= 0) Out(o, n, "yes: %s in slot %d%s", arg, found, foundLeft ? " (left hand)" : "");
    else Out(o, n, "no: %s is in none of the 15 slots", arg);
    return true;
}
// game thread: every reserve = MaxAmmo(type) (the clips are not touched)
bool RunAmmoFill(const char *, char *o, size_t n) {
    if (!g_ammoOk || !g_maxAmmoOk || !g_experimental) { Out(o, n, "ammo code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    WORD v[6] = {};
    __try {
        for (int type = 0; type < 6; ++type) {
            v[type] = reinterpret_cast<MaxAmmoFn>(kMaxAmmo)(type);
            if (v[type] != 0xffff) *reinterpret_cast<volatile WORD *>(p + 0x51c + 2 * type) = v[type];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in MaxAmmo 0x%08lx", kMaxAmmo);
        return false;
    }
    Out(o, n, "reserve = MaxAmmo per type: %u %u %u %u %u %u (clips unchanged)", v[0], v[1], v[2], v[3], v[4], v[5]);
    return true;
}
// game thread, main state 1: GiveObject(player, id, 0x715e90, 1) -> WM::AddGear (an existing instance of the object
// is taken at once, else the game loads and births it first)
bool RunGearGive(const char *arg, char *o, size_t n) {
    if (!g_gearOk || !g_experimental) { Out(o, n, "gear code not verified / experimental off"); return false; }
    DWORD state = 0, player = 0;
    ReadDword(kMainState, &state);
    if (!InLevel() || state != 1 || !ReadDword(kPlayerPtr, &player) || !player) {
        Out(o, n, "in a level only (main state %lu, needs 1)", state);
        return false;
    }
    if (!arg || !arg[0]) { Out(o, n, "usage: gear.give <object name> (g_binoculars, g_grapple, g_pda, g_healthpack, ...)"); return false; }
    char name[64];
    strncpy_s(name, sizeof(name), arg, _TRUNCATE);
    int id = ObjectId(name);
    if (!id) { Out(o, n, "'%s' is not in the object list", name); return false; }
    __try {
        reinterpret_cast<GiveObjectFn>(kGiveObject)(player, id, kGearCallback, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in GiveObject 0x%08lx", kGiveObject);
        return false;
    }
    Out(o, n, "GiveObject 0x%08lx(player, %d %s, 0x%08lx, 1) done%s", kGiveObject, id, name, kGearCallback,
        _strnicmp(name, "g_", 2) == 0 ? "" : " (not a g_ gear object - check the result)");
    return true;
}

// ---- favourites: [Favorites] Ids in TruMenu.ini (comma list of item ids; empty = kFavDefault) ----
bool ItemUsable(const char *id);         // defined after kItems: id exists and is not a todo item

// calls fn(id) for every usable favourite
template <typename F> void ForFavs(F fn) {
    char copy[sizeof(g_favs)];
    EnterCriticalSection(&g_favLock);
    strncpy_s(copy, sizeof(copy), g_favs, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    char *context = nullptr;
    for (char *id = strtok_s(copy, ", ", &context); id; id = strtok_s(nullptr, ", ", &context))
        if (ItemUsable(id)) fn(id);
}
bool FavHas(const char *id) {
    bool found = false;
    ForFavs([&](const char *f) { if (_stricmp(f, id) == 0) found = true; });
    return found;
}
void FavSave() {
    if (g_iniPath[0] && !WritePrivateProfileStringA("Favorites", "Ids", g_favs, g_iniPath))
        Log(1, "favourites: writing %s failed (%lu)", g_iniPath, GetLastError());
}
bool FavSet(const char *id, bool add, char *o, size_t n) {
    if (!id || !id[0] || !ItemUsable(id)) { Out(o, n, "no such item '%s'", id ? id : ""); return false; }
    char rebuilt[sizeof(g_favs)] = "";
    size_t used = 0;
    bool had = false;
    ForFavs([&](const char *f) {
        if (_stricmp(f, id) == 0) { had = true; if (!add) return; }
        int w = _snprintf_s(rebuilt + used, sizeof(rebuilt) - used, _TRUNCATE, "%s%s", used ? "," : "", f);
        if (w > 0) used += static_cast<size_t>(w);
    });
    if (add && !had) _snprintf_s(rebuilt + used, sizeof(rebuilt) - used, _TRUNCATE, "%s%s", used ? "," : "", id);
    EnterCriticalSection(&g_favLock);
    strncpy_s(g_favs, sizeof(g_favs), rebuilt, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    FavSave();
    Out(o, n, "fav %s %s (%s)", add ? "add" : "del", id, add ? (had ? "was already in" : "added") : (had ? "removed" : "was not in"));
    return true;
}
void FavToggle(const char *id) {
    char o[160];
    FavSet(id, !FavHas(id), o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s", o);
}
void ValFavList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    ForFavs([&](const char *f) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " " : "", f);
        if (w > 0) used += static_cast<size_t>(w);
    });
    if (!used) Out(o, n, "-");
}
bool RunFavAdd(const char *arg, char *o, size_t n) { return FavSet(arg, true, o, n); }
bool RunFavDel(const char *arg, char *o, size_t n) { return FavSet(arg, false, o, n); }

bool RunFavReset(const char *, char *o, size_t n) {
    EnterCriticalSection(&g_favLock);
    strncpy_s(g_favs, sizeof(g_favs), kFavDefault, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    // empty Ids = the default list (kOpts), so later changes of the default reach this file too
    if (g_iniPath[0]) WritePrivateProfileStringA("Favorites", "Ids", "", g_iniPath);
    Out(o, n, "favourites back to the default list (%s)", kFavDefault);
    return true;
}

// ---- 0.4 TO TEST: a checklist the main session fills over TruLink (menu test.add / test.mark / test.list ...),
// marked in the menu (A ok, X fail, Y skip on the selected row); kept in TruMenu.tests.txt next to tru.exe, one row per
// line: id TAB state TAB hint TAB note TAB time [TAB kind TAB target TAB number] (lines starting with '#' are
// comments; 0.4 files without the last three columns load as checks).
// 0.5 row kinds: "check" (ok / fail / skip / open, as in 0.4), "step" (an ordered instruction, id "step<n>", state
// open / done, optional item to run: target "id" or "id:arg"), "toggle" (a switch, state on / off; target = a TruMenu
// item run with 1 / 0, or "ini:<Plugin>:<Section>:<Key>" written to <Plugin>.ini next to the .asi files) ----
struct TestRow {
    char id[64]; char state[8]; char hint[240]; char note[160]; char when[16];
    char kind[8]; char target[128]; int num;
};
const int kTestMax = 64;
TestRow g_tests[kTestMax];
int g_testCount = 0;
CRITICAL_SECTION g_testLock;
char g_testPath[MAX_PATH] = "";

bool ItemUsable(const char *id);                        // defined after kItems
bool ItemValueText(const char *id, char *o, size_t n);  // defined after kItems: the item's value text
void QueueItem(const char *id, const char *arg);        // defined after kItems: run from the menu, never waits

// tabs / line breaks would break the file and '|' / '{' / '}' the test.list answer
void TestClean(char *s) {
    for (; *s; ++s) {
        if (*s == '\t' || *s == '\r' || *s == '\n') *s = ' ';
        else if (*s == '|') *s = '/';
        else if (*s == '{') *s = '(';
        else if (*s == '}') *s = ')';
    }
}
bool TestStateOk(const char *s) {
    return !_stricmp(s, "open") || !_stricmp(s, "ok") || !_stricmp(s, "fail") || !_stricmp(s, "skip");
}
bool TestIs(const TestRow &t, const char *kind) { return _stricmp(t.kind, kind) == 0; }
// valid states per kind: check open|ok|fail|skip, step open|done, toggle on|off
bool TestStateFits(const char *kind, const char *s) {
    if (!_stricmp(kind, "step")) return !_stricmp(s, "open") || !_stricmp(s, "done");
    if (!_stricmp(kind, "toggle")) return !_stricmp(s, "on") || !_stricmp(s, "off");
    return TestStateOk(s);
}
const char *TestDefaultState(const char *kind) { return !_stricmp(kind, "toggle") ? "off" : "open"; }

// "ini:<Plugin>:<Section>:<Key>" -> path of <Plugin>.ini next to the .asi files, section, key; the plugin name must
// start with "Tru" and hold letters / digits only (no other files are written)
bool TestIniTarget(const char *target, char *path, size_t pathSize, char *section, size_t secSize, char *key,
                   size_t keySize) {
    if (_strnicmp(target, "ini:", 4) != 0) return false;
    char plugin[40] = "";
    const char *p = target + 4;
    const char *c1 = strchr(p, ':');
    const char *c2 = c1 ? strchr(c1 + 1, ':') : nullptr;
    if (!c1 || !c2 || c1 - p < 4 || static_cast<size_t>(c1 - p) >= sizeof(plugin) || c2 - c1 < 2 || !c2[1]) return false;
    memcpy(plugin, p, static_cast<size_t>(c1 - p));
    plugin[c1 - p] = 0;
    if (_strnicmp(plugin, "Tru", 3) != 0) return false;
    for (const char *q = plugin; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q))) return false;
    if (static_cast<size_t>(c2 - c1 - 1) >= secSize) return false;
    memcpy(section, c1 + 1, static_cast<size_t>(c2 - c1 - 1));
    section[c2 - c1 - 1] = 0;
    strncpy_s(key, keySize, c2 + 1, _TRUNCATE);
    for (const char *q = section; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q)) && *q != '_') return false;
    for (const char *q = key; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q)) && *q != '_') return false;
    _snprintf_s(path, pathSize, _TRUNCATE, "%s%s.ini", g_asiDir, plugin);
    return true;
}

// the current state of a toggle: INI value (1 / 0; missing file or key = off) or the item's value text
// ("1" / "on" / "true" ... = on); false when the target cannot be read (state unchanged)
bool TestToggleRead(const char *target, bool *on) {
    char path[MAX_PATH], section[64], key[64];
    if (TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) return false;
        *on = GetPrivateProfileIntA(section, key, 0, path) != 0;
        return true;
    }
    if (!_strnicmp(target, "ini:", 4)) return false;
    char value[256] = "";
    if (!ItemValueText(target, value, sizeof(value))) return false;
    const char *v = value;
    while (*v == ' ') ++v;
    if (*v == '1' || !_strnicmp(v, "on", 2) || !_strnicmp(v, "true", 4) || !_strnicmp(v, "yes", 3)) { *on = true; return true; }
    if (*v == '0' || !_strnicmp(v, "off", 3) || !_strnicmp(v, "false", 5) || !_strnicmp(v, "no", 2)) { *on = false; return true; }
    return false;
}

// g_testLock held
void TestSaveLocked() {
    if (!g_testPath[0]) return;
    FILE *f = nullptr;
    if (fopen_s(&f, g_testPath, "wb") != 0 || !f) { Log(1, "tests: cannot write %s", g_testPath); return; }
    fputs("# TruMenu.tests.txt - TO TEST list (TruMenu 0.5): id<TAB>state<TAB>hint<TAB>note<TAB>time<TAB>kind<TAB>target"
          "<TAB>number\r\n", f);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        fprintf(f, "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\r\n", t.id, t.state, t.hint, t.note, t.when, t.kind, t.target, t.num);
    }
    fclose(f);
}

void TestLoad() {
    FILE *f = nullptr;
    if (!g_testPath[0] || fopen_s(&f, g_testPath, "rb") != 0 || !f) return;
    char line[1024];
    EnterCriticalSection(&g_testLock);
    g_testCount = 0;
    while (g_testCount < kTestMax && fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
        if (!line[0] || line[0] == '#') continue;
        char *field[8] = {line, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};
        for (int k = 1; k < 8; ++k) {
            char *tab = field[k - 1] ? strchr(field[k - 1], '\t') : nullptr;
            if (!tab) break;
            *tab = 0;
            field[k] = tab + 1;
        }
        if (!field[0][0]) continue;
        TestRow &t = g_tests[g_testCount++];
        memset(&t, 0, sizeof(t));
        const char *kind = field[5] && (!_stricmp(field[5], "step") || !_stricmp(field[5], "toggle")) ? field[5] : "check";
        strncpy_s(t.kind, sizeof(t.kind), kind, _TRUNCATE);
        _strlwr_s(t.kind, sizeof(t.kind));
        strncpy_s(t.id, sizeof(t.id), field[0], _TRUNCATE);
        strncpy_s(t.state, sizeof(t.state), field[1] && TestStateFits(t.kind, field[1]) ? field[1] : TestDefaultState(t.kind),
                  _TRUNCATE);
        _strlwr_s(t.state, sizeof(t.state));
        strncpy_s(t.hint, sizeof(t.hint), field[2] ? field[2] : "", _TRUNCATE);
        strncpy_s(t.note, sizeof(t.note), field[3] ? field[3] : "", _TRUNCATE);
        strncpy_s(t.when, sizeof(t.when), field[4] ? field[4] : "", _TRUNCATE);
        strncpy_s(t.target, sizeof(t.target), field[6] ? field[6] : "", _TRUNCATE);
        t.num = field[7] ? atoi(field[7]) : 0;
    }
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    fclose(f);
    // toggles show the real state of their target (an INI may have been edited between two runs)
    for (int i = 0; i < count; ++i) {
        EnterCriticalSection(&g_testLock);
        char target[128] = "";
        if (i < g_testCount && TestIs(g_tests[i], "toggle")) strncpy_s(target, sizeof(target), g_tests[i].target, _TRUNCATE);
        LeaveCriticalSection(&g_testLock);
        bool on = false;
        if (target[0] && !_strnicmp(target, "ini:", 4) && TestToggleRead(target, &on)) {
            EnterCriticalSection(&g_testLock);
            if (i < g_testCount) strncpy_s(g_tests[i].state, sizeof(g_tests[i].state), on ? "on" : "off", _TRUNCATE);
            LeaveCriticalSection(&g_testLock);
        }
    }
    Log(1, "tests: %d rows from %s", count, g_testPath);
}

// g_testLock held
int TestFindLocked(const char *id) {
    for (int i = 0; i < g_testCount; ++i)
        if (_stricmp(g_tests[i].id, id) == 0) return i;
    return -1;
}

// open / ok / fail / skip count the checks only; total = every row
void TestCounts(int *open, int *ok, int *fail, int *skip, int *total) {
    *open = *ok = *fail = *skip = 0;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        if (!TestIs(g_tests[i], "check")) continue;
        const char *s = g_tests[i].state;
        if (!_stricmp(s, "ok")) ++*ok;
        else if (!_stricmp(s, "fail")) ++*fail;
        else if (!_stricmp(s, "skip")) ++*skip;
        else ++*open;
    }
    *total = g_testCount;
    LeaveCriticalSection(&g_testLock);
}

// splits "<word> <rest>": word (cut to size), rest = after the spaces
const char *TestWord(const char *arg, char *word, size_t size) {
    const char *rest = arg ? arg : "";
    while (*rest == ' ') ++rest;
    size_t len = 0;
    while (rest[len] && rest[len] != ' ' && len + 1 < size) { word[len] = rest[len]; ++len; }
    word[len] = 0;
    rest += len;
    while (*rest && *rest != ' ') ++rest;          // an over-long word is cut
    while (*rest == ' ') ++rest;
    return rest;
}

// g_testLock held: a new row at index at (rows behind it move down); false when the list is full
bool TestInsertLocked(int at) {
    if (g_testCount >= kTestMax) return false;
    for (int k = g_testCount; k > at; --k) g_tests[k] = g_tests[k - 1];
    ++g_testCount;
    memset(&g_tests[at], 0, sizeof(TestRow));
    return true;
}

// "<id> <hint text>": new check row (state open) or new hint for an existing row (state back to open, note cleared)
bool RunTestAdd(const char *arg, char *o, size_t n) {
    char id[64] = "";
    const char *rest = TestWord(arg, id, sizeof(id));
    if (!id[0]) { Out(o, n, "usage: test.add <id> <hint text> (id = a menu item id, id:arg, or any key)"); return false; }
    TestClean(id);
    for (char *p = id; *p; ++p) if (*p == ' ') *p = '_';
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added && !TestInsertLocked(g_testCount)) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
        return false;
    }
    if (added) i = g_testCount - 1;
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "check", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), "open", _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.add %s (%s, %d rows)", id, added ? "new" : "updated, state open again", count);
    Log(1, "tests: %s", o);
    return true;
}

// 0.5 "<n> <id|-> <text>": step n (1..999, row id "step<n>"); id = the item it runs ("id" or "id:arg", "-" = none).
// A new step goes in front of the first step with a higher number (checks / toggles between steps keep their place);
// an existing step n gets the new item / text and is open again.
bool RunTestStep(const char *arg, char *o, size_t n) {
    char num[16] = "", target[128] = "";
    const char *rest = TestWord(arg, num, sizeof(num));
    rest = TestWord(rest, target, sizeof(target));
    int number = atoi(num);
    if (number < 1 || number > 999 || !target[0]) {
        Out(o, n, "usage: test.step <n 1..999> <item id | id:arg | -> <text>");
        return false;
    }
    if (!strcmp(target, "-")) target[0] = 0;
    TestClean(target);
    char id[16];
    _snprintf_s(id, sizeof(id), _TRUNCATE, "step%d", number);
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added) {
        int at = g_testCount;
        for (int k = 0; k < g_testCount; ++k)
            if (TestIs(g_tests[k], "step") && g_tests[k].num > number) { at = k; break; }
        if (!TestInsertLocked(at)) {
            LeaveCriticalSection(&g_testLock);
            Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
            return false;
        }
        i = at;
    }
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "step", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), "open", _TRUNCATE);
    strncpy_s(t.target, sizeof(t.target), target, _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    t.num = number;
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.step %d %s (%s, %d rows)", number, target[0] ? target : "-", added ? "new" : "updated, open again",
        count);
    Log(1, "tests: %s", o);
    return true;
}

// 0.5 "<id> <target> <text>": a switch row; target = a TruMenu item (run with 1 / 0) or ini:<Plugin>:<Section>:<Key>
bool RunTestToggle(const char *arg, char *o, size_t n) {
    char id[64] = "", target[128] = "";
    const char *rest = TestWord(arg, id, sizeof(id));
    rest = TestWord(rest, target, sizeof(target));
    if (!id[0] || !target[0]) {
        Out(o, n, "usage: test.toggle <id> <item id | ini:<Plugin>:<Section>:<Key>> <text>");
        return false;
    }
    TestClean(id);
    TestClean(target);
    char path[MAX_PATH], section[64], key[64];
    bool isIni = !_strnicmp(target, "ini:", 4);
    if (isIni && !TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        Out(o, n, "bad ini target '%s' (ini:<TruPlugin>:<Section>:<Key>, letters / digits / _)", target);
        return false;
    }
    if (!isIni && !ItemUsable(target)) { Out(o, n, "unknown or todo item '%s'", target); return false; }
    bool on = false, known = TestToggleRead(target, &on);
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added && !TestInsertLocked(g_testCount)) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
        return false;
    }
    if (added) i = g_testCount - 1;
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "toggle", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), on ? "on" : "off", _TRUNCATE);
    strncpy_s(t.target, sizeof(t.target), target, _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    if (isIni) strncpy_s(t.note, sizeof(t.note), "INI: takes effect at the next start", _TRUNCATE);
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.toggle %s %s now %s%s (%s, %d rows)", id, target, on ? "on" : "off", known ? "" : " (not readable)",
        added ? "new" : "updated", count);
    Log(1, "tests: %s", o);
    return true;
}

// "" = every row; "done" = only the checks that are marked (steps and toggles stay)
bool RunTestClear(const char *arg, char *o, size_t n) {
    bool doneOnly = arg && _stricmp(arg, "done") == 0;
    if (arg && arg[0] && !doneOnly) { Out(o, n, "usage: test.clear [done]"); return false; }
    EnterCriticalSection(&g_testLock);
    int before = g_testCount, kept = 0;
    for (int i = 0; doneOnly && i < g_testCount; ++i)
        if (!TestIs(g_tests[i], "check") || !_stricmp(g_tests[i].state, "open")) g_tests[kept++] = g_tests[i];
    g_testCount = kept;
    TestSaveLocked();
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.clear%s: %d rows removed, %d left", doneOnly ? " done" : "", before - kept, kept);
    Log(1, "tests: %s", o);
    return true;
}

bool RunTestDel(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: test.del <id>"); return false; }
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(arg);
    if (i >= 0) {
        for (int k = i; k + 1 < g_testCount; ++k) g_tests[k] = g_tests[k + 1];
        --g_testCount;
        TestSaveLocked();
    }
    LeaveCriticalSection(&g_testLock);
    Out(o, n, i >= 0 ? "test.del %s" : "no test row '%s'", arg);
    return i >= 0;
}

// a toggle row switched: INI written at once (the plugins read it at start) or the item run with 1 / 0
bool TestToggleApply(const char *target, bool on, char *o, size_t n) {
    char path[MAX_PATH], section[64], key[64];
    if (TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) { Out(o, n, "%s not found - not created", path); return false; }
        if (!WritePrivateProfileStringA(section, key, on ? "1" : "0", path)) {
            Out(o, n, "cannot write %s (%lu)", path, GetLastError());
            return false;
        }
        Out(o, n, "[%s] %s=%d written to %s - takes effect at the next start", section, key, on ? 1 : 0, path);
        return true;
    }
    if (!ItemUsable(target)) { Out(o, n, "unknown or todo item '%s'", target); return false; }
    QueueItem(target, on ? "1" : "0");
    Out(o, n, "%s %d run (%s)", target, on ? 1 : 0, g_lastAction);
    return true;
}

bool TestMark(const char *id, const char *state, const char *note, char *o, size_t n) {
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    if (i < 0) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "no test row '%s' (test.list)", id);
        return false;
    }
    if (!TestStateFits(g_tests[i].kind, state)) {
        const char *kind = g_tests[i].kind;
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "%s is a %s row: %s", id, kind, !_stricmp(kind, "step") ? "open|done" : !_stricmp(kind, "toggle")
                                                                            ? "on|off" : "ok|fail|skip|open");
        return false;
    }
    char apply[300] = "";
    if (TestIs(g_tests[i], "toggle")) {
        char target[128];
        strncpy_s(target, sizeof(target), g_tests[i].target, _TRUNCATE);
        LeaveCriticalSection(&g_testLock);          // the INI write / item run happens without the lock
        bool ok = TestToggleApply(target, !_stricmp(state, "on"), apply, sizeof(apply));
        if (!ok) { Out(o, n, "%s", apply); Log(1, "tests: toggle %s: %s", id, apply); return false; }
        EnterCriticalSection(&g_testLock);
        i = TestFindLocked(id);
        if (i < 0) { LeaveCriticalSection(&g_testLock); Out(o, n, "%s (row removed meanwhile)", apply); return true; }
    }
    TestRow &t = g_tests[i];
    strncpy_s(t.state, sizeof(t.state), state, _TRUNCATE);
    _strlwr_s(t.state, sizeof(t.state));
    if (note) { strncpy_s(t.note, sizeof(t.note), note, _TRUNCATE); TestClean(t.note); }
    SYSTEMTIME s;
    GetLocalTime(&s);
    _snprintf_s(t.when, sizeof(t.when), _TRUNCATE, "%02d:%02d:%02d", s.wHour, s.wMinute, s.wSecond);
    TestSaveLocked();
    Out(o, n, "test.mark %s %s%s%s%s%s", t.id, t.state, t.note[0] ? " - " : "", t.note, apply[0] ? "; " : "", apply);
    LeaveCriticalSection(&g_testLock);
    Log(1, "tests: %s", o);
    return true;
}

// "<id> <state> [note]": check ok|fail|skip|open, step done|open, toggle on|off (switches the target)
bool RunTestMark(const char *arg, char *o, size_t n) {
    char id[64] = "", state[16] = "";
    int used = 0;
    if (!arg || sscanf_s(arg, "%63s %15s %n", id, static_cast<unsigned>(sizeof(id)), state,
                         static_cast<unsigned>(sizeof(state)), &used) < 2 ||
        !(TestStateOk(state) || !_stricmp(state, "done") || !_stricmp(state, "on") || !_stricmp(state, "off"))) {
        Out(o, n, "usage: test.mark <id> ok|fail|skip|open [note] (steps: done|open, toggles: on|off)");
        return false;
    }
    const char *note = used > 0 && static_cast<size_t>(used) <= strlen(arg) ? arg + used : "";
    return TestMark(id, state, note[0] ? note : nullptr, o, n);
}

// "<n> rows (o open, k ok, f fail, s skip): id [state] hint {note} | ..." - steps / toggles carry their kind:
// "step3 (step 3 -> level.load:x) [open] text", "sp-states (toggle ini:...) [on] text"
void ValTestList(char *o, size_t n) {
    int open, ok, fail, skip, total;
    TestCounts(&open, &ok, &fail, &skip, &total);
    int used = _snprintf_s(o, n, _TRUNCATE, "%d rows (%d open, %d ok, %d fail, %d skip)%s", total, open, ok, fail, skip,
                           total ? ":" : "");
    if (used < 0) return;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        char kind[180] = "";
        if (TestIs(t, "step"))
            _snprintf_s(kind, sizeof(kind), _TRUNCATE, " (step %d%s%s)", t.num, t.target[0] ? " -> " : "", t.target);
        else if (TestIs(t, "toggle"))
            _snprintf_s(kind, sizeof(kind), _TRUNCATE, " (toggle %s)", t.target);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s %s%s [%s] %s%s%s%s", i ? " |" : "", t.id, kind, t.state,
                            t.hint, t.note[0] ? " {" : "", t.note, t.note[0] ? "}" : "");
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_testLock);
}

// 0.5 test.export: the whole list as a TruLink block (InvokeItem answers it directly):
// "ok+ test.export <n> rows ..." then one line per row "kind<TAB>id<TAB>state<TAB>number<TAB>target<TAB>hint<TAB>note
// <TAB>time", then ".". As a plain value (menu list / status) only the counts.
void ValTestExport(char *o, size_t n) {
    int open, ok, fail, skip, total, steps = 0, done = 0, toggles = 0, on = 0;
    TestCounts(&open, &ok, &fail, &skip, &total);
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        if (TestIs(g_tests[i], "step")) { ++steps; if (!_stricmp(g_tests[i].state, "done")) ++done; }
        if (TestIs(g_tests[i], "toggle")) { ++toggles; if (!_stricmp(g_tests[i].state, "on")) ++on; }
    }
    LeaveCriticalSection(&g_testLock);
    _snprintf_s(o, n, _TRUNCATE, "%d rows; checks %d open %d ok %d fail %d skip; steps %d/%d done; toggles %d/%d on",
                total, open, ok, fail, skip, done, steps, on, toggles);
}

void TestExportBlock(char *o, size_t n) {
    char head[200];
    ValTestExport(head, sizeof(head));
    int used = _snprintf_s(o, n, _TRUNCATE, "ok+ test.export %s (kind id state number target hint note time, tab "
                           "separated; file %s)\n", head, g_testPath[0] ? g_testPath : "-");
    if (used < 0) used = 0;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n", t.kind, t.id, t.state,
                            t.num, t.target, t.hint, t.note, t.when);
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_testLock);
    // the block always ends with "." (TruLink adds the final line break); cut rows make room for it
    if (static_cast<size_t>(used) + 2 >= n) used = static_cast<int>(n) - 3;
    _snprintf_s(o + used, n - used, _TRUNCATE, ".");
}

// ---- settings: the kOpts table vs the file ----
void ReadOptions(const char *dir);       // with Start below

// TruMenu.ini as written from the table (= the shipped src/asi/TruMenu/TruMenu.ini)
size_t DefaultIniText(char *out, size_t size) {
    size_t used = 0;
    auto put = [&](const char *fmt, const char *a, const char *b) {
        int w = _snprintf_s(out + used, size - used, _TRUNCATE, fmt, a, b);
        if (w > 0) used += static_cast<size_t>(w);
    };
    put("; %s%s\n", kIniHeader, "");
    const char *section = nullptr;
    for (const OptDef &d : kOpts) {
        if (!section || strcmp(section, d.section) != 0) {
            put(section ? "\n[%s]%s\n" : "[%s]%s\n", d.section, "");
            section = d.section;
        }
        char comment[512];
        strncpy_s(comment, sizeof(comment), d.comment, _TRUNCATE);
        char *context = nullptr;
        for (char *line = strtok_s(comment, "\n", &context); line; line = strtok_s(nullptr, "\n", &context))
            put("; %s%s\n", line, "");
        put("%s=%s\n", d.key, d.def);
    }
    return used;
}

void ValSettings(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (const OptDef &d : kOpts) {
        char value[1024];
        GetPrivateProfileStringA(d.section, d.key, "\x01", value, sizeof(value), g_iniPath);
        bool missing = value[0] == '\x01';
        bool changed = !missing && strcmp(value, d.def) != 0;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s[%s] %s=%s%s", used ? "; " : "", changed ? "* " : "",
                            d.section, d.key, missing ? d.def : value,
                            missing ? " (missing: default)" : changed ? "" : " (default)");
        if (changed && w > 0) {
            used += static_cast<size_t>(w);
            w = _snprintf_s(o + used, n - used, _TRUNCATE, " (default %s)", d.def[0] ? d.def : "\"\"");
        }
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

bool RunSettingsReset(const char *, char *o, size_t n) {
    if (!g_iniPath[0]) { Out(o, n, "no ini path"); return false; }
    SYSTEMTIME t;
    GetLocalTime(&t);
    char backup[MAX_PATH];
    _snprintf_s(backup, sizeof(backup), _TRUNCATE, "%s.bak_%04d%02d%02d_%02d%02d%02d", g_iniPath, t.wYear, t.wMonth, t.wDay,
                t.wHour, t.wMinute, t.wSecond);
    bool hadFile = GetFileAttributesA(g_iniPath) != INVALID_FILE_ATTRIBUTES;
    if (hadFile && !CopyFileA(g_iniPath, backup, TRUE)) {
        Out(o, n, "backup to %s failed (%lu) - nothing changed", backup, GetLastError());
        return false;
    }
    static char text[8192];
    size_t len = DefaultIniText(text, sizeof(text));
    FILE *f = nullptr;
    if (fopen_s(&f, g_iniPath, "wb") != 0 || !f) { Out(o, n, "cannot write %s", g_iniPath); return false; }
    fwrite(text, 1, len, f);
    fclose(f);
    ReadOptions(g_asiDir);
    g_logOverlay = g_logOverlayAtStart ? 1 : 0;
    g_logLines = g_logLinesAtStart;
    Out(o, n, "TruMenu.ini rewritten from the defaults%s%s; options reloaded (Scale / Enabled / Script take effect at the "
        "next start)", hadFile ? ", backup " : "", hadFile ? backup : "");
    Log(1, "settings: %s", o);
    return true;
}
void ValIniPath(char *o, size_t n) { Out(o, n, "%s", g_iniPath[0] ? g_iniPath : "-"); }

// Y (gamepad face up) on the focused widget pins / unpins <id>
void FavKey(const char *id) {
    if (ImGui::IsItemFocused() && ImGui::IsKeyPressed(ImGuiKey_GamepadFaceUp, false)) FavToggle(id);
}

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
    {"status.unit", "info", "current unit (GameTracker+0x38) and stream unit id", false, ValStatusUnit, nullptr},
    {"status.state", "info", "game state (level change pending / in a level / no player)", false, ValState, nullptr},
    {"status.costume", "info", "current costume, chosen costume words, game-data base, unit default", false, ValCostume,
     nullptr},
    {"status.player", "info", "player instance, object id / name, type record", false, ValPlayerObject, nullptr},
    {"status.plugins", "info", "our ASIs (loaded? version)", false, ValPlugins, nullptr},
    {"overlay.position", "bool", "Lara position overlay", false, ValOverlay, RunOverlay},
    {"player.position", "info", "Lara position / rotation (needs a level)", false, ValPlayer, nullptr},
    {"camera.current", "info", "current camera object", false, ValCamera, nullptr},
    {"camera.mode", "action", "CAMERA_SetMode(arg 0..15), experimental, needs a level", true, ValCamera, RunCameraMode},
    {"camera.restore", "action", "restore the game camera, needs a level", true, ValCamera, RunCameraRestore},
    {"camera.free", "todo", "own free camera - todo: offsets of Camera transform / invTransform not verified", false, ValTodo,
     RunTodo},
    {"cheat.flight", "bool", "cheatMode + message 12 (flight), needs a level", true, ValCheat, RunCheat},
    {"cheat.speed", "float", "flight speed per 30 fps frame (RT up / LT down)", false, ValSpeed, RunSpeed},
    {"draw.markup", "bool", "markup boxes / poly lines projected with the game camera (experimental)", false,
     ValDrawMarkup, RunDrawMarkup},
    {"draw.ledges", "bool", "only ledge-grab markup (flag bit 30), turns draw.markup on", false, ValDrawLedges,
     RunDrawLedges},
    {"draw.scale", "action", "<w> <h> of the projected screen space (default 512 448)", false, ValDrawScale, RunDrawScale},
    {"fav.list", "info", "favourite item ids (Quick access page; [Favorites] Ids)", false, ValFavList, nullptr},
    {"fav.add", "action", "pin <id> to Quick access (also: Y on an item in the menu)", false, ValFavList, RunFavAdd},
    {"fav.del", "action", "unpin <id>", false, ValFavList, RunFavDel},
    {"fav.reset", "action", "favourites back to the default list", false, ValFavList, RunFavReset},
    {"settings.show", "info", "every TruMenu.ini key: current value vs default (* = changed)", false, ValSettings, nullptr},
    {"settings.reset", "action", "back up TruMenu.ini to TruMenu.ini.bak_<time>, rewrite it from the defaults, reload",
     false, ValIniPath, RunSettingsReset},
    {"weapon.list", "info", "weapon object ids (catalog 17.1)", false, ValWeaponList, nullptr},
    {"weapon.give", "action", "WM::GiveWeaponByName 0x7161f0(<name>, 1, 0), main state 1 only, experimental", true,
     ValWeaponList, RunWeaponGive},
    {"ammo.show", "info", "reserve ammo u16 playerstate+0x51c, types 0..5", false, ValAmmo, nullptr},
    {"ammo.set", "action", "<type 0..5> <n>: reserve ammo, experimental", true, ValAmmo, RunAmmoSet},
    {"player.health", "float", "float playerstate+0x628 (\"\" = MaxHealth 0x6e7990), experimental", true, ValHealth,
     RunHealth},
    {"player.invincible", "bool", "health = MaxHealth every game frame (variant A), experimental", false, ValInvincible,
     RunInvincible},
    {"level.current", "info", "unit name at GameTracker+0x38", false, ValUnit, nullptr},
    {"level.list", "info", "all offered units by group (PC unitlist.txt)", false, ValLevelList, nullptr},
    {"level.presets", "info", "preset units ([Levels] List)", false, ValLevels, nullptr},
    {"level.load", "action", "load unit (arg = unit name), experimental", true, ValUnit, RunLevel},
    {"level.reload", "action", "reload the current unit, experimental", true, ValUnit, RunReload},
    // 0.3: costume.list / costume.set are the live outfit cycle now; the 0.2 "chosen for the next level load" items
    // are costume.records / costume.choose* (costume.setreload / costume.reset keep their 0.2 meaning)
    {"costume.list", "info", "outfit cycle list GlobalInfo [0xe7ee50]+4: object-id name", false, ValGlobalCostumes, nullptr},
    {"costume.records", "info", "player records of the type table: index name object-id (0.2 costume.list)", false,
     ValCostumeList, nullptr},
    {"costume.current", "info", "costume object id [0xe7f1c8] of the last level load", false, ValCostumeCurrent, nullptr},
    {"costume.next", "action", "live: next outfit of the cycle list (0x6f0a90), needs a level", true, ValCostumeCurrent,
     RunCostumeNext},
    {"costume.set", "action", "live: outfit by object name / id now (altPlayerObjectID + 0x6f0a90), needs a level", true,
     ValCostumeCurrent, RunCostumeLive},
    {"costume.choose", "action", "chosen costume (arg = index or name [20c|210]) for the next level load (0.2 costume.set)",
     true, ValCostume, RunCostumeSet},
    {"costume.choosereload", "action", "costume.choose, then reload the current unit", true, ValCostume, RunCostumeSetReload},
    {"costume.choosereset", "action", "chosen costume words +0x20c/+0x20e/+0x210 = 0 (new-game reset)", true, ValCostume,
     RunCostumeReset},
    {"costume.setreload", "action", "= costume.choosereload (0.2 id)", true, ValCostume, RunCostumeSetReload},
    {"costume.reset", "action", "= costume.choosereset (0.2 id)", true, ValCostume, RunCostumeReset},
    {"dev.log", "todo", "engine channel log (stub 0x6457a0) - todo; script prints: log.script", false, ValTodo, RunTodo},
    // 0.3
    {"dev.list", "info", "original developer menu: id type=value (page; row) for every value / action row", false,
     ValDevList, nullptr},
    {"time.scale", "float", "timeDilation 0xe7f1d0 (0..10, \"\" = 1)", false, ValTimeScale, RunTimeScale},
    {"time.pause", "bool", "freeze the world: streamFlags 0xe7f0b8 bit 0x1000", true, ValPause, RunPause},
    {"player.control", "bool", "player control byte 0x8ab4e6 (1 = on)", true, ValControl, RunControl},
    {"player.die", "action", "INSTANCE_Post(player, 4, 3): ragdoll death, needs a level", true, ValPlayer, RunDie},
    {"player.teleport", "action", "Lara to <x> <y> <z>, needs a level", true, ValPlayer, RunTeleport},
    {"player.mark", "action", "remember Lara's position", false, ValMark, RunMark},
    {"player.recall", "action", "Lara back to the mark", true, ValMark, RunRecall},
    {"player.goto", "action", "Lara to an instance (intro id, 0x<address> or #<index>)", true, ValPlayer, RunGoto},
    {"ui.hide", "bool", "hide the HUD (bool 0xcdc9a0)", true, ValUiHide, RunUiHide},
    {"camera.fov", "float", "current camera +0xb0 fov in radians (\"\" = pi/4), needs a level", true, ValFov, RunFov},
    {"instance.list", "action", "instances (arg = name filter): #index intro name address (pos)", false, ValInstCount,
     RunInstanceList},
    {"instance.info", "action", "one instance (intro id, 0x<address> or #<index>)", false, ValInstCount, RunInstanceInfo},
    {"instance.bring", "action", "move an instance to Lara", true, ValInstCount, RunBring},
    {"instance.unhide", "action", "INSTANCE_Post(instance, 7, 0)", true, ValInstCount, RunUnhide},
    {"instance.unhideall", "action", "message 7 to every instance", true, ValInstCount, RunUnhideAll},
    {"instance.remove", "action", "INSTANCE_ReallyRemoveInstance(instance, 0, 0) (not the player)", true, ValInstCount, RunRemove},
    {"log.page", "info", "last log.lines lines (Tru*.log tails + script prints, log.filter)", false, ValLogPage, nullptr},
    {"log.show", "info", "last script print / log lines", false, ValScriptLines, nullptr},
    {"log.script", "bool", "redirect the 8 NsCoreBase print / log natives to the log page", true, ValScriptLog,
     RunScriptLog},
    {"log.overlay", "bool", "log lines in the bottom-left corner", false, ValLogOverlay, RunLogOverlay},
    {"log.lines", "int", "lines on the page / overlay (1..64)", false, ValLogLines, RunLogLines},
    {"log.filter", "action", "only one source (TruLink, TruMenu, script, ...; \"\" / all = every source)", false,
     ValLogFilter, RunLogFilter},
    {"log.clear", "action", "clear the collected lines", false, ValLogCount, RunLogClear},
    {"media.video.list", "info", "Movies\\*.bik next to tru.exe", false, ValVideoList, nullptr},
    {"media.video.play", "action", "0x4a12b0(<name>, 0), front end only (main state 10)", true, ValVideoList, RunVideoPlay},
    {"media.video.menuloop", "action", "main menu background loop [0x8abf20] = <name> (\"\" = medsea_loop)", false,
     ValMenuLoop, RunMenuLoop},
    // 0.4
    {"log.collapse", "bool", "collapse repeated lines (same source + text) into \"text xN (first-last)\"", false,
     ValLogCollapse, RunLogCollapse},
    {"log.hidereads", "bool", "drop TruLink's read / scan / watch / ping echo and menu info reads", false,
     ValLogHideReads, RunLogHideReads},
    {"log.level", "int", "lines shown: 0 all, 1 warnings + errors, 2 errors (also all / warn / error)", false, ValLogLevel,
     RunLogLevel},
    {"log.rate", "int", "max new lines per source and second (0 = no limit)", false, ValLogRate, RunLogRate},
    {"test.list", "info", "TO TEST rows: id [state] hint {note} | ...", false, ValTestList, nullptr},
    {"test.add", "action", "<id> <hint text>: add / update a TO TEST row (id = item id, id:arg or any key)", false,
     ValTestList, RunTestAdd},
    {"test.mark", "action", "<id> ok|fail|skip|open [note] (steps done|open, toggles on|off)", false, ValTestList,
     RunTestMark},
    {"test.del", "action", "<id>: remove one TO TEST row", false, ValTestList, RunTestDel},
    {"test.clear", "action", "remove every TO TEST row (\"done\" = only the marked checks)", false, ValTestList, RunTestClear},
    // 0.5
    {"test.step", "action", "<n> <id|id:arg|-> <text>: numbered step (in order, runs the item with a button)", false,
     ValTestList, RunTestStep},
    {"test.toggle", "action", "<id> <item id|ini:Plugin:Section:Key> <text>: switch row (checkbox)", false, ValTestList,
     RunTestToggle},
    {"test.export", "info", "the whole TO TEST list as a block (kind id state number target hint note time)", false,
     ValTestExport, nullptr},
    {"weapon.slots", "info", "the 15 weapon slots: slot[L] object name (WM+4+0x10*slot), selected slot", false,
     ValWeaponSlots, nullptr},
    {"weapon.has", "action", "<object name>: is it in a weapon slot? (read-only)", false, ValWeaponSlots, RunWeaponHas},
    {"ammo.fill", "action", "every reserve = MaxAmmo(type) 0x6eeae0 (clips unchanged), experimental", true, ValAmmo,
     RunAmmoFill},
    {"gear.give", "action", "GiveObject 0x555f60(player, <name>, 0x715e90, 1) -> AddGear, main state 1, experimental", true,
     ValWeaponSlots, RunGearGive},
};

const Item *FindItem(const char *id) {
    if (!id) return nullptr;
    for (const Item &item : kItems)
        if (_stricmp(item.id, id) == 0) return &item;
    return nullptr;
}

bool IsInfoItem(const char *id) {
    const Item *item = FindItem(id);
    return item && strcmp(item->type, "info") == 0;
}

bool ItemUsable(const char *id) {
    const Item *item = FindItem(id);
    if (item) return strcmp(item->type, "todo") != 0;
    return DevFind(id) != nullptr;
}

// 0.5 (TO TEST toggles): the value text of an item or developer-menu row; false if there is none
bool ItemValueText(const char *id, char *o, size_t n) {
    const Item *item = FindItem(id);
    if (item) { item->value(o, n); return true; }
    const DevRow *dev = DevFind(id);
    if (dev) { DevValue(*dev, o, n); return true; }
    return false;
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
    char text[1000] = "";
    bool ok = false;
    const DevRow *dev = item ? nullptr : DevFind(g_reqId);
    if (item && item->run) ok = item->run(g_reqArg, text, sizeof(text));
    else if (dev) ok = DevRun(*dev, g_reqArg, text, sizeof(text));
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
    if (!item && DevFind(id)) {                // developer-menu rows always run on the game thread
        if (!Enqueue(id, arg)) SetLastAction(id, false, "busy (another request pending)");
        else SetLastAction(id, true, "queued");
        return;
    }
    if (!item || !item->run) return;
    if (!item->gameThread) {
        char text[1000];
        bool ok = item->run(arg, text, sizeof(text));
        SetLastAction(id, ok, text);
        return;
    }
    if (!Enqueue(id, arg)) SetLastAction(id, false, "busy (another request pending)");
    else SetLastAction(id, true, "queued");
}

__declspec(thread) char t_answer[49152];
__declspec(thread) char t_value[16384];

const char *InvokeItem(const char *id, const char *arg) {
    const Item *item = FindItem(id);
    const DevRow *dev = item ? nullptr : DevFind(id);
    if (!item && !dev) { _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err unknown item '%s'", id ? id : ""); return t_answer; }
    const char *itemId = item ? item->id : dev->id;
    if (item && !_stricmp(item->id, "test.export")) {          // 0.5: a block answer ("ok+ ...", rows, ".")
        TestExportBlock(t_answer, sizeof(t_answer));
        return t_answer;
    }
    if (item && !item->run) {
        char *value = t_value;
        item->value(value, sizeof(t_value));
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok %s %s", item->id, value);
        return t_answer;
    }
    if (dev && (!arg || !arg[0]) && dev->type == kDevInt) {   // an int row without argument: its value
        char value[32];
        DevValue(*dev, value, sizeof(value));
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok %s %s (%ld..%ld)", dev->id, value,
                    static_cast<LONG>(dev->p1), static_cast<LONG>(dev->p2));
        return t_answer;
    }
    if (item && !item->gameThread) {
        char *text = t_value;                  // lists (instance.list) can be long
        bool ok = item->run(arg, text, sizeof(t_value));
        SetLastAction(item->id, ok, text);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s%s", ok ? "ok " : "err ", text);
        return t_answer;
    }
    if (!Enqueue(itemId, arg)) {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err busy (another request pending)");
        return t_answer;
    }
    if (WaitForSingleObject(g_reqDone, 3000) == WAIT_OBJECT_0 && !g_reqPending) {
        EnterCriticalSection(&g_reqLock);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s", g_reqResult);
        LeaveCriticalSection(&g_reqLock);
    } else {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok queued %s (no game frame within 3 s - runs at the next "
                    "one)", itemId);
    }
    return t_answer;
}

const char *ListItems() {
    size_t used = 0;
    t_answer[0] = 0;
    for (const Item &item : kItems) {
        char *value = t_value;
        item.value(value, sizeof(t_value));
        int w = _snprintf_s(t_answer + used, sizeof(t_answer) - used, _TRUNCATE, "%s\t%s\t%s\t%s\n", item.id, item.type,
                            value, item.label);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    // the developer menu rows (dev.<slug>), from the tables
    for (int i = 0; g_devOk && i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (!d.id[0]) continue;
        char value[32], page[64];
        DevValue(d, value, sizeof(value));
        DevPageName(d.page, page, sizeof(page));
        const char *type = d.type == kDevAction ? "action" : d.type == kDevInt ? "int" : "bool";
        int w = _snprintf_s(t_answer + used, sizeof(t_answer) - used, _TRUNCATE, "%s\t%s\t%s\toriginal dev menu: %s / %s "
                            "(row 0x%08lx)\n", d.id, type, value, page, d.text, d.addr);
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
    // every playable unit of the PC unit list, one tree node per group
    ImGui::Separator();
    Text("All units (%d, PC tr8/pc-w/unitlist.txt) - [level.load <unit>]", kUnitCount);
    for (int i = 0; i < kUnitCount;) {
        const char *group = kUnits[i].group;
        int count = 0;
        while (i + count < kUnitCount && strcmp(kUnits[i + count].group, group) == 0) ++count;
        char head[64];
        _snprintf_s(head, sizeof(head), _TRUNCATE, "%s (%d)##grp%d", group, count, i);
        if (ImGui::TreeNode(head)) {
            for (int k = i; k < i + count; ++k) {
                char label[96];
                _snprintf_s(label, sizeof(label), _TRUNCATE, "%s##unit%d", kUnits[k].unit, k);
                if (ImGui::Button(label)) QueueItem("level.load", kUnits[k].unit);
                if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s", kUnits[k].path);
            }
            ImGui::TreePop();
        }
        i += count;
    }
    ImGui::TextWrapped("GAMELOOP_RequestLevelChangeByName 0x%08lx (name, GameTracker, 4). Any other unit: TruLink "
                       "\"menu level.load <unit>\" or [Levels] List in TruMenu.ini. A unit loads with the chosen costume "
                       "(Outfits page) or the unit's default.", kLevelChange);
}

void PageOutfits() {
    if (!g_costumeOk) { ImGui::TextUnformatted("costume code check failed (see TruMenu.log)"); return; }
    CostumeState s;
    ReadCostumeState(&s);
    char cur[160], c0[160], c2[160], def[160];
    IdName(static_cast<int>(s.current), cur, sizeof(cur));
    IdName(s.chosen0, c0, sizeof(c0));
    IdName(s.chosen2, c2, sizeof(c2));
    IdName(s.unitDefault, def, sizeof(def));
    Text("current costume [0x%08lx]: %s", kCostumeNow, cur);
    Text("game data [0x%08lx] = 0x%08lx, +0x1f4 = %u -> the level load reads +0x%lx", kGameDataPtr, s.gameData, s.mode,
         s.mode ? kGdChosen2 : kGdChosen0);
    Text("chosen +0x20c: %s   +0x20e: %u   +0x210: %s", c0, s.chosen1, c2);
    Text("unit default (unit %lu, data +0x70 -> +0x294): %s", s.unitId, s.unitDefault < 0 ? "-" : def);
    if (!g_experimental) { ImGui::TextUnformatted("(experimental actions off in TruMenu.ini)"); return; }
    static bool reload = false;
    ImGui::Checkbox("reload the current unit after choosing  [costume.setreload]", &reload);
    if (ImGui::Button("Reset chosen costume (0 / 0 / 0)  [costume.reset]")) QueueItem("costume.reset", "");
    ImGui::Separator();
    ImGui::TextUnformatted("Player records of the type table (index  name  object id):");
    // object ids by record, recomputed when the object name table or the type table moves (the lookup walks ~1000 names)
    static int ids[64];
    static DWORD cachedNames = 0, cachedTypes = 0;
    DWORD names = 0;
    ReadDword(kObjNames, &names);
    bool fresh = names != cachedNames || TypeTable() != cachedTypes;
    if (fresh) { cachedNames = names; cachedTypes = TypeTable(); }
    char name[64];
    bool player = false;
    for (int i = 0; i < 64 && TypeRecord(i, name, sizeof(name), &player); ++i) {
        if (!player) continue;
        if (fresh) ids[i] = ObjectId(name);
        int id = ids[i];
        bool chosen = id && id == (s.mode ? s.chosen2 : s.chosen0);
        bool now = id && static_cast<DWORD>(id) == s.current;
        char label[128];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%2d  %s  (%d)%s%s##cos%d", i, name, id, chosen ? "  [chosen]" : "",
                    now ? "  [current]" : "", i);
        if (!id) ImGui::BeginDisabled();
        if (ImGui::Button(label)) {
            char arg[16];
            _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", i);
            QueueItem(reload ? "costume.setreload" : "costume.set", arg);
        }
        if (!id) ImGui::EndDisabled();
    }
    ImGui::TextWrapped("Choosing writes the object id (u16) to game data +0x20c (+0x210 while +0x1f4 != 0) after the "
                       "game's check 0x%08lx; the next level load (tru+0x1de2b0) uses it unless byte [0x0084216c] holds "
                       "a name, and in l1_seatop it takes lara_wetsuit_warm instead. The state save tru+0x155cb1 writes "
                       "the current costume back to +0x20c.", kCostumeValid);
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
    ImGui::TextWrapped("0.3: draw.debugflag (debugFlags2 0x100) was removed - that bit is the TR7 / TRAE debug-draw path, "
                       "not TR8 (catalog section 7). The TR8 developer flags are on the page \"Developer menu "
                       "(original)\" (e.g. Show Spline Info = debugFlags2 0x400000).");
    if (!g_drawOk) { ImGui::TextUnformatted("markup / projection code check failed"); return; }
    bool markup = g_drawMarkup != 0, ledges = g_drawLedges != 0;
    if (ImGui::Checkbox("draw markup  [draw.markup]", &markup)) { char o[96]; RunDrawMarkup(markup ? "1" : "0", o, sizeof(o)); }
    ImGui::SameLine();
    if (ImGui::Checkbox("ledges only  [draw.ledges]", &ledges)) { char o[96]; RunDrawLedges(ledges ? "1" : "0", o, sizeof(o)); }
    ImGui::SliderFloat("projected width  [draw.scale]", &g_drawW, 256.0f, 2048.0f, "%.0f");
    ImGui::SliderFloat("projected height", &g_drawH, 224.0f, 2048.0f, "%.0f");
    Text("boxes drawn last frame: %d", g_drawnBoxes);
    ImGui::TextWrapped("Experimental: boxes of MarkupManager [0xdb94cc]+0x14 (next +4), poly line of MarkUp +0x58 or a "
                       "circle at MarkUp +0x34, projected like 0x49f630 (matrix 0xa038f0, focal [0x8906d0], centre "
                       "256 / 224). Colours: yellow ledge (bit 30), green ladder (22), cyan poles (25-27), blue water "
                       "(20), orange rope (19) - catalog bit names, not verified. If lines sit off, adjust the "
                       "projected size (default 512 x 448).");
    Todo("draw.collision / portals / triggers (catalog section 7).");
}

// ---- 0.3 pages ----
void Status03Line() {
    ImGui::TextWrapped("0.3: dev menu %s, time %s, pause %s, control %s, ui %s, instances %s, remove %s, costume switch %s, "
                       "movie %s, menu loop %s, script natives %s, markup draw %s", g_devOk ? "ok" : "NO",
                       g_timeOk ? "ok" : "NO", g_pauseOk ? "ok" : "NO", g_controlOk ? "ok" : "NO", g_uiOk ? "ok" : "NO",
                       g_instOk ? "ok" : "NO", g_removeOk ? "ok" : "NO", g_switchOk ? "ok" : "NO",
                       g_movieOk && g_mainStateOk ? "ok" : "NO", g_menuLoopOk ? "ok" : "NO", g_scriptOk ? "ok" : "NO",
                       g_drawOk ? "ok" : "NO");
    ImGui::TextWrapped("     weapon.give %s, ammo %s, health %s", g_weaponOk ? "ok" : "NO", g_ammoOk ? "ok" : "NO",
                       g_healthOk ? "ok" : "NO");
    ImGui::TextWrapped("0.4: weapon slots %s, ammo.fill %s, gear.give %s; TO TEST file %s", g_slotsOk ? "ok" : "NO",
                       g_maxAmmoOk && g_ammoOk ? "ok" : "NO", g_gearOk ? "ok" : "NO", g_testPath);
}

void Note(const char *text) {
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.6f, 0.75f, 1.0f, 1.0f));
    ImGui::TextWrapped("%s", text);
    ImGui::PopStyleColor();
}

// one widget for any item id: bool -> checkbox, info -> value text, else a button that runs it with "" (its default)
void ItemWidget(const char *id) {
    const Item *item = FindItem(id);
    const DevRow *dev = item ? nullptr : DevFind(id);
    char value[256] = "";
    const char *type = "action", *label = id;
    if (item) {
        item->value(value, sizeof(value));
        type = item->type;
        label = item->label;
    } else if (dev) {
        DevValue(*dev, value, sizeof(value));
        type = dev->type == kDevAction ? "action" : dev->type == kDevInt ? "int" : "bool";
        label = dev->text;
    } else {
        return;
    }
    ImGui::PushID(id);
    char text[200];
    if (strcmp(type, "bool") == 0) {
        bool on = value[0] == '1';
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s  [%s]", label, id);
        if (ImGui::Checkbox(text, &on)) QueueItem(id, on ? "1" : "0");
    } else if (strcmp(type, "info") == 0) {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s: %.120s", id, value);
        ImGui::Selectable(text);
    } else {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s  [%s]%s%s", label, id, value[0] ? " = " : "", value);
        if (ImGui::Button(text)) QueueItem(id, "");
    }
    FavKey(id);
    ImGui::PopID();
}

void PageFavourites() {
    ImGui::TextUnformatted("Y on an item pins / unpins it ([Favorites] Ids in TruMenu.ini; fav.list / fav.add / fav.del).");
    int count = 0;
    ForFavs([&](const char *id) { ItemWidget(id); ++count; });
    if (!count) ImGui::TextUnformatted("(no favourites)");
    if (ImGui::TreeNode("Add an item (A or Y on an id)")) {
        for (const Item &item : kItems) {
            if (strcmp(item.type, "todo") == 0 || FavHas(item.id)) continue;
            if (ImGui::Selectable(item.id)) FavToggle(item.id);
            else FavKey(item.id);
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s", item.label);
        }
        ImGui::TreePop();
    }
}

// 0.4 TO TEST page: one row per test (state, hint, id, note), A on the row = OK, X = FAIL, Y = SKIP (X / Y are taken
// from ImGui in FeedGamepad while a row has the focus), buttons OK / FAIL / SKIP and Run (when the id - or the part
// before ':' - is a usable item; the part after ':' is its argument)
void TestMarkFromMenu(const char *id, const char *state) {
    char o[300];
    TestMark(id, state, nullptr, o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s", o);
}

bool ConfirmButton(const char *label, const char *key);

// "id" or "id:arg" -> item id + argument; false when it is not a usable item
bool TestRunTarget(const char *target, char *itemId, size_t idSize, const char **runArg) {
    strncpy_s(itemId, idSize, target, _TRUNCATE);
    char *colon = strchr(itemId, ':');
    *runArg = "";
    if (colon) { *colon = 0; *runArg = target + (colon - itemId) + 1; }
    return itemId[0] && ItemUsable(itemId);
}

// 0.5: switches first (toggles: a checkbox each; INI targets take effect at the next start), then steps and checks
// in list order; steps are numbered, the first open step is marked "NEXT"; A on a step runs its item and marks it
// done, "Run" only runs it, "Done" / "Open" only mark it
void PageTestToggles(const TestRow *rows, int c) {
    bool any = false;
    for (int i = 0; i < c; ++i) if (TestIs(rows[i], "toggle")) { any = true; break; }
    if (!any) return;
    ImGui::SeparatorText("Switches (on / off - to find the step or feature that crashes)");
    for (int i = 0; i < c; ++i) {
        const TestRow &t = rows[i];
        if (!TestIs(t, "toggle")) continue;
        ImGui::PushID(1000 + i);
        bool on = !_stricmp(t.state, "on");
        char label[512];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s   [%s -> %s]", t.hint[0] ? t.hint : t.id, t.id, t.target);
        if (ImGui::Checkbox(label, &on)) TestMarkFromMenu(t.id, on ? "on" : "off");
        if (t.note[0] || t.when[0]) {
            ImGui::Indent();
            ImGui::TextDisabled("%s%s%s", t.note, t.note[0] && t.when[0] ? "  " : "", t.when);
            ImGui::Unindent();
        }
        ImGui::PopID();
    }
    ImGui::Separator();
}

void PageTests() {
    ImGui::TextWrapped("TO TEST list from the main session or Invoke-TruTestRun.ps1 (TruLink: menu test.step / test.add / "
                       "test.toggle / test.mark / test.export). Checks: A = OK, X = FAIL, Y = SKIP. Steps: A = run + "
                       "done. Kept in %s.", g_testPath[0] ? g_testPath : "TruMenu.tests.txt");
    static TestRow rows[kTestMax];
    EnterCriticalSection(&g_testLock);
    int c = g_testCount;
    memcpy(rows, g_tests, sizeof(TestRow) * static_cast<size_t>(c));
    LeaveCriticalSection(&g_testLock);
    bool xPressed = InterlockedExchange(&g_testX, 0) != 0, yPressed = InterlockedExchange(&g_testY, 0) != 0;
    bool anyFocus = false;
    PageTestToggles(rows, c);
    int nextStep = -1;
    for (int i = 0; i < c && nextStep < 0; ++i)
        if (TestIs(rows[i], "step") && _stricmp(rows[i].state, "done") != 0) nextStep = i;
    for (int i = 0; i < c; ++i) {
        const TestRow &t = rows[i];
        if (TestIs(t, "toggle")) continue;
        if (TestIs(t, "step")) {
            ImGui::PushID(i);
            bool done = !_stricmp(t.state, "done");
            char itemId[64];
            const char *runArg = "";
            bool runnable = t.target[0] && TestRunTarget(t.target, itemId, sizeof(itemId), &runArg);
            char label[512];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s %2d. %s", done ? "[DONE]" : i == nextStep ? "NEXT->" : "      ",
                        t.num, t.hint[0] ? t.hint : "(no text)");
            ImVec4 colour = done ? ImVec4(0.6f, 0.6f, 0.6f, 1.0f) : i == nextStep ? ImVec4(1.0f, 0.85f, 0.3f, 1.0f)
                                                                                  : ImVec4(0.75f, 0.85f, 1.0f, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_Text, colour);
            bool activated = ImGui::Selectable(label);
            ImGui::PopStyleColor();
            if (activated) {
                if (runnable) QueueItem(itemId, runArg);
                TestMarkFromMenu(t.id, "done");
            }
            ImGui::Indent();
            if (runnable) {
                char run[160];
                _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
                if (ImGui::SmallButton(run)) QueueItem(itemId, runArg);
                ImGui::SameLine();
            } else if (t.target[0]) {
                ImGui::TextDisabled("(%s: no such item)", t.target);
                ImGui::SameLine();
            }
            if (ImGui::SmallButton(done ? "Open again" : "Done")) TestMarkFromMenu(t.id, done ? "open" : "done");
            if (t.when[0]) {
                ImGui::SameLine();
                ImGui::TextDisabled("%s", t.when);
            }
            ImGui::Unindent();
            ImGui::PopID();
            continue;
        }
        ImGui::PushID(i);
        bool ok = !_stricmp(t.state, "ok"), fail = !_stricmp(t.state, "fail"), skip = !_stricmp(t.state, "skip");
        ImVec4 colour = ok ? ImVec4(0.45f, 1.0f, 0.45f, 1.0f) : fail ? ImVec4(1.0f, 0.45f, 0.4f, 1.0f)
                      : skip ? ImVec4(0.65f, 0.65f, 0.65f, 1.0f) : ImVec4(1.0f, 1.0f, 1.0f, 1.0f);
        char label[512];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  %s   [%s]%s%s", ok ? "[OK]  " : fail ? "[FAIL]" : skip ? "[SKIP]" : "[    ]",
                    t.hint[0] ? t.hint : "(no hint)", t.id, t.note[0] ? "  - " : "", t.note);
        ImGui::PushStyleColor(ImGuiCol_Text, colour);
        bool activated = ImGui::Selectable(label);
        ImGui::PopStyleColor();
        if (ImGui::IsItemFocused()) {
            anyFocus = true;
            if (xPressed) TestMarkFromMenu(t.id, "fail");
            else if (yPressed) TestMarkFromMenu(t.id, "skip");
        }
        if (activated) TestMarkFromMenu(t.id, "ok");
        ImGui::Indent();
        if (ImGui::SmallButton("OK")) TestMarkFromMenu(t.id, "ok");
        ImGui::SameLine();
        if (ImGui::SmallButton("FAIL")) TestMarkFromMenu(t.id, "fail");
        ImGui::SameLine();
        if (ImGui::SmallButton("SKIP")) TestMarkFromMenu(t.id, "skip");
        char itemId[64];
        strncpy_s(itemId, sizeof(itemId), t.id, _TRUNCATE);
        char *colon = strchr(itemId, ':');
        const char *runArg = "";
        if (colon) { *colon = 0; runArg = t.id + (colon - itemId) + 1; }
        if (ItemUsable(itemId)) {
            ImGui::SameLine();
            char run[160];
            _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
            if (ImGui::SmallButton(run)) QueueItem(itemId, runArg);
        }
        if (t.when[0]) {
            ImGui::SameLine();
            ImGui::TextDisabled("%s", t.when);
        }
        ImGui::Unindent();
        ImGui::PopID();
    }
    InterlockedExchange(&g_testFocus, anyFocus ? 1 : 0);
    if (ImGui::Button("Remove the marked rows  [test.clear done]")) { char o[160]; RunTestClear("done", o, sizeof(o)); }
    ImGui::SameLine();
    if (ConfirmButton("Remove all rows  [test.clear]", "testclear")) { char o[160]; RunTestClear("", o, sizeof(o)); }
}

// in-menu confirmation (no dialogs): the first A arms a button for 5 s, the second A runs it
bool ConfirmButton(const char *label, const char *key) {
    static char armed[32] = "";
    static DWORD armedAt = 0;
    bool isArmed = strcmp(armed, key) == 0 && GetTickCount() - armedAt < 5000;
    char text[160];
    _snprintf_s(text, sizeof(text), _TRUNCATE, isArmed ? "%s - press A again to confirm##%s" : "%s##%s", label, key);
    if (isArmed) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
    bool pressed = ImGui::Button(text);
    if (isArmed) ImGui::PopStyleColor();
    if (!pressed) return false;
    if (isArmed) { armed[0] = 0; return true; }
    strncpy_s(armed, sizeof(armed), key, _TRUNCATE);
    armedAt = GetTickCount();
    return false;
}

void PageSettings() {
    Text("TruMenu.ini: %s", g_iniPath[0] ? g_iniPath : "-");
    static char all[8192];
    ValSettings(all, sizeof(all));
    char *context = nullptr;
    for (char *line = strtok_s(all, ";", &context); line; line = strtok_s(nullptr, ";", &context)) {
        while (*line == ' ') ++line;
        bool changed = line[0] == '*';
        if (changed) ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.8f, 0.3f, 1.0f));
        ImGui::TextUnformatted(line);
        if (changed) ImGui::PopStyleColor();
    }
    ImGui::TextUnformatted("(* = changed from the default)   [settings.show]");
    char o[512];
    if (ConfirmButton("Favourites back to the default list  [fav.reset]", "favreset")) {
        bool ok = RunFavReset("", o, sizeof(o));
        SetLastAction("fav.reset", ok, o);
    }
    if (ConfirmButton("Reset all settings (backup, rewrite TruMenu.ini)  [settings.reset]", "setreset")) {
        bool ok = RunSettingsReset("", o, sizeof(o));
        SetLastAction("settings.reset", ok, o);
    }
}

// one page of Crystal's developer menu, drawn from its rows: links switch the page, values are read live
void PageDev() {
    if (!g_devOk) { ImGui::TextWrapped("developer menu tables: %s", g_devStatus); return; }
    ImGui::TextWrapped("Crystal Dynamics' own debug menu, still in tru.exe .data (%s). The driver is gone in retail; "
                       "TruMenu draws the rows as their types say. Effects in retail are mostly unverified (notes in "
                       "blue). [dev.<label>], dev.list", g_devStatus);
    if (!g_experimental) ImGui::TextUnformatted("(experimental actions off in TruMenu.ini - read only)");
    char name[64];
    DevPageName(g_devPage, name, sizeof(name));
    ImGui::Separator();
    Text("page: %s (0x%08lx)", name, g_devPage);
    if (g_devPage != kDevRoot && ImGui::Button("<< root page##devroot")) g_devPage = kDevRoot;
    for (int i = 0; i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (d.page != g_devPage) continue;
        ImGui::PushID(static_cast<int>(d.addr));
        char value[32];
        DevValue(d, value, sizeof(value));
        const char *note = DevNoteOf(d.addr);
        switch (d.type) {
        case kDevTitle:
            Text("== %s ==", d.text[0] ? d.text : "(no title)");
            break;
        case kDevHeader:
            Text("(page header, text layout \"%s\"; its slots are empty in retail)", d.text);
            break;
        case kDevLink: {
            char label[96];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  ->", d.text);
            if (ImGui::Button(label)) g_devPage = d.target;
            break;
        }
        case kDevFlag:
        case kDevBool: {
            bool on = value[0] == '1';
            char label[120];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", d.text, d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            if (ImGui::Checkbox(label, &on)) QueueItem(d.id, on ? "1" : "0");
            FavKey(d.id);
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip(d.type == kDevFlag ? "[0x%08lx] & 0x%lx" : "byte [0x%08lx] (value 0x%lx)", d.target, d.p5);
            break;
        }
        case kDevInt: {
            int v = atoi(value), lo = static_cast<int>(d.p1), hi = static_cast<int>(d.p2);
            char label[120];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", d.text, d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            bool changed = hi - lo <= 255 ? ImGui::SliderInt(label, &v, lo, hi)
                                          : ImGui::InputInt(label, &v, hi > 1000 ? 100 : 1, 1000);
            FavKey(d.id);
            if (changed) {
                char arg[16];
                _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", v);
                QueueItem(d.id, arg);
            }
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("s32 [0x%08lx] %d..%d%s", d.target, lo, hi, d.p5 ? ", callback after a change" : "");
            break;
        }
        case kDevAction: {
            char label[120];
            bool empty = IsEmptyFunction(d.target);
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s%s  [%s]", d.text, empty ? " (empty in retail)" : "", d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            if (ImGui::Button(label)) QueueItem(d.id, "");
            FavKey(d.id);
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("cdecl 0x%08lx(0x%lx)", d.target, d.p1);
            break;
        }
        default:
            break;
        }
        if (note && d.type != kDevLink) { ImGui::Indent(); Note(note); ImGui::Unindent(); }
        ImGui::PopID();
    }
    ImGui::Separator();
    // the retail root links only "Units" and "Chapters"; the other pages are not linked from anywhere any more
    if (ImGui::TreeNode("All pages of the tables (most are not linked from the root in retail)")) {
        for (int p = 0; p < g_devPageCount; ++p) {
            int rows = 0;
            for (int i = 0; i < g_devCount; ++i)
                if (g_dev[i].page == g_devPages[p] && g_dev[i].type != kDevEnd) ++rows;
            DevPageName(g_devPages[p], name, sizeof(name));
            char label[96];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s (%d rows)##devp%d", name, rows, p);
            if (ImGui::Button(label)) g_devPage = g_devPages[p];
        }
        ImGui::TreePop();
    }
}

void PageTimePlayer() {
    char v[64];
    ValTimeScale(v, sizeof(v));
    float scale = static_cast<float>(atof(v));
    if (!g_timeOk || !g_experimental) ImGui::BeginDisabled();
    if (ImGui::SliderFloat("time scale  [time.scale]", &scale, 0.0f, 10.0f, "%.2f")) {
        char arg[16];
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%.3f", scale);
        QueueItem("time.scale", arg);
    }
    if (ImGui::Button("time scale 1.0##ts1")) QueueItem("time.scale", "1");
    if (!g_timeOk || !g_experimental) ImGui::EndDisabled();
    ValPause(v, sizeof(v));
    bool paused = v[0] == '1';
    if (ImGui::Checkbox("freeze world (streamFlags 0x1000)  [time.pause]", &paused)) QueueItem("time.pause", paused ? "1" : "0");
    ValUiHide(v, sizeof(v));
    bool hidden = v[0] == '1';
    if (ImGui::Checkbox("hide HUD  [ui.hide]", &hidden)) QueueItem("ui.hide", hidden ? "1" : "0");
    if (!InLevel()) { ImGui::TextUnformatted("player items: needs a level"); return; }
    ValControl(v, sizeof(v));
    bool control = v[0] == '1';
    if (ImGui::Checkbox("player control  [player.control]", &control)) QueueItem("player.control", control ? "1" : "0");
    if (ImGui::Button("Ragdoll death  [player.die]")) QueueItem("player.die", "");
    if (ImGui::Button("Mark position  [player.mark]")) QueueItem("player.mark", "");
    ImGui::SameLine();
    if (ImGui::Button("Back to mark  [player.recall]")) QueueItem("player.recall", "");
    ValMark(v, sizeof(v));
    Text("mark: %s   (player.teleport x y z over TruLink)", v);
    ValFov(v, sizeof(v));
    float fov = static_cast<float>(atof(v));
    if (fov > 0.05f && fov < 3.1f && ImGui::SliderFloat("camera fov (rad)  [camera.fov]", &fov, 0.2f, 2.5f, "%.3f")) {
        char arg[16];
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%.4f", fov);
        QueueItem("camera.fov", arg);
    }
    ImGui::Separator();
    ImGui::TextUnformatted("Weapons / ammo / health (experimental, catalog section 17, not checked live):");
    char ammo[64];
    ValHealth(v, sizeof(v));
    ValAmmo(ammo, sizeof(ammo));
    Text("health %s   [player.health]   reserve ammo %s   [ammo.show / ammo.set <type> <n>]", v, ammo);
    if (g_healthOk && ImGui::Button("Full health  [player.health]")) QueueItem("player.health", "");
    bool inv = g_invincible != 0;
    if (g_healthOk && ImGui::Checkbox("invincible (health = max every frame)  [player.invincible]", &inv))
        QueueItem("player.invincible", inv ? "1" : "0");
    for (const WeaponName &w : kWeapons) {
        char label[64];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Give %s##wg%d", w.name, w.id);
        if (!g_weaponOk) ImGui::BeginDisabled();
        if (ImGui::Button(label)) QueueItem("weapon.give", w.name);
        if (!g_weaponOk) ImGui::EndDisabled();
        if (w.id != 41 && w.id != 114) ImGui::SameLine();
    }
}

void PageInstances() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    static char filter[32] = "";
    ImGui::InputText("name filter", filter, sizeof(filter));
    ImGui::TextWrapped("ids for TruLink: intro id, 0x<address> or #<index> - instance.info / player.goto / instance.bring "
                       "/ unhide / remove");
    int index = 0, shown = 0;
    ForInstances([&](const InstInfo &x) {
        int i = index++;
        if (filter[0] && !strstr(x.name, filter)) return true;
        if (++shown > 200) return false;
        char label[160], arg[16];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "#%d  %s  intro %ld  (%.0f %.0f %.0f)##inst%d", i, x.name, x.intro,
                    x.pos[0], x.pos[1], x.pos[2], i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "#%d", i);
        if (ImGui::TreeNode(label)) {
            if (ImGui::Button("Lara goes there  [player.goto]")) QueueItem("player.goto", arg);
            ImGui::SameLine();
            if (ImGui::Button("Bring to Lara  [instance.bring]")) QueueItem("instance.bring", arg);
            if (ImGui::Button("Unhide  [instance.unhide]")) QueueItem("instance.unhide", arg);
            ImGui::SameLine();
            if (ImGui::Button("Remove  [instance.remove]")) QueueItem("instance.remove", arg);
            ImGui::TreePop();
        }
        return true;
    });
    Text("%d instances, %d shown (max 200)", index, shown > 200 ? 200 : shown);
    if (ImGui::Button("Unhide all  [instance.unhideall]")) QueueItem("instance.unhideall", "");
}

void PageCostumeLive() {
    ImGui::TextWrapped("Live switch (the game's 0x6f0a90, as the costume native 0x79db50): altPlayerObjectID [0xe7f1cc] "
                       "= id, or 0 = next of the cycle list GlobalInfo [0xe7ee50]+4; then player message 35 (weapons).");
    if (!g_switchOk) { ImGui::TextUnformatted("costume switch code check failed"); return; }
    if (!InLevel()) { ImGui::TextUnformatted("needs a level"); return; }
    if (ImGui::Button("Next outfit  [costume.next]")) QueueItem("costume.next", "");
    WORD ids[128];
    int c = GlobalCostumes(ids, 128);
    DWORD now = 0;
    ReadDword(kCostumeNow, &now);
    for (int i = 0; i < c; ++i) {
        char name[64], label[96], arg[16];
        if (!ObjectName(ids[i], name, sizeof(name))) Out(name, sizeof(name), "?");
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%u %s%s##live%d", ids[i], name, ids[i] == now ? "  [current]" : "", i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%u", ids[i]);
        if (ImGui::Button(label)) QueueItem("costume.set", arg);
    }
    if (c < 0) ImGui::TextUnformatted("no GlobalInfo list");
}

void PageLog() {
    ImGui::TextWrapped("Tails of the Tru*.log files next to the .asi / tru.exe (once per second) and, with log.script on, "
                       "the game's script print / log natives.");
    bool overlay = g_logOverlay != 0;
    if (ImGui::Checkbox("corner overlay  [log.overlay]", &overlay)) InterlockedExchange(&g_logOverlay, overlay ? 1 : 0);
    ImGui::SameLine();
    bool script = g_scriptLog != 0;
    if (!g_scriptOk) ImGui::BeginDisabled();
    if (ImGui::Checkbox("script prints  [log.script]", &script)) QueueItem("log.script", script ? "1" : "0");
    if (!g_scriptOk) ImGui::EndDisabled();
    ImGui::SliderInt("lines  [log.lines]", &g_logLines, 1, 64);
    // sources: every tailed file + "script"
    if (ImGui::Button(g_logFilter[0] ? "all##lf" : "[all]##lf")) g_logFilter[0] = 0;
    for (int i = 0; i < 16; ++i) {
        if (!g_tails[i].used) continue;
        ImGui::SameLine();
        char label[48];
        bool active = _stricmp(g_logFilter, g_tails[i].name) == 0;
        _snprintf_s(label, sizeof(label), _TRUNCATE, active ? "[%s]##lf%d" : "%s##lf%d", g_tails[i].name, i);
        if (ImGui::Button(label)) strncpy_s(g_logFilter, sizeof(g_logFilter), g_tails[i].name, _TRUNCATE);
    }
    ImGui::SameLine();
    if (ImGui::Button(_stricmp(g_logFilter, "script") == 0 ? "[script]##lfs" : "script##lfs"))
        strncpy_s(g_logFilter, sizeof(g_logFilter), "script", _TRUNCATE);
    ImGui::SameLine();
    if (ImGui::Button("clear  [log.clear]")) { char o[64]; RunLogClear("", o, sizeof(o)); }
    // 0.4: collapse, TruLink reads, severity, rate
    bool collapse = g_logCollapse != 0, hide = g_logHideReads != 0;
    if (ImGui::Checkbox("collapse repeats  [log.collapse]", &collapse)) InterlockedExchange(&g_logCollapse, collapse ? 1 : 0);
    ImGui::SameLine();
    if (ImGui::Checkbox("hide TruLink reads  [log.hidereads]", &hide)) InterlockedExchange(&g_logHideReads, hide ? 1 : 0);
    ImGui::TextUnformatted("show  [log.level]:");
    for (int i = 0; i < 3; ++i) {
        ImGui::SameLine();
        char label[32];
        _snprintf_s(label, sizeof(label), _TRUNCATE, g_logMinLevel == i ? "[%s]##ll%d" : "%s##ll%d",
                    i == 0 ? "all" : i == 1 ? "warnings + errors" : "errors", i);
        if (ImGui::Button(label)) g_logMinLevel = i;
    }
    ImGui::SliderInt("max lines per source and second (0 = off)  [log.rate]", &g_logRate, 0, 200);
    static LogLine lines[64];
    int c = CopyLines(lines, g_logLines, g_logFilter);
    ImGui::BeginChild("##logchild", ImVec2(0.0f, ImGui::GetTextLineHeightWithSpacing() * 14.0f), true);
    for (int i = 0; i < c; ++i) {
        BYTE sev = lines[i].sev;
        if (sev) ImGui::PushStyleColor(ImGuiCol_Text, sev == 2 ? ImVec4(1.0f, 0.5f, 0.4f, 1.0f) : ImVec4(1.0f, 0.85f, 0.4f, 1.0f));
        char line[300];
        FormatLine(lines[i], line, sizeof(line), 220);
        ImGui::TextWrapped("%s", line);
        if (sev) ImGui::PopStyleColor();
    }
    ImGui::EndChild();
    Text("script prints so far: %ld; lines mentioning an exception: %ld; exceptions caught by TruMenu: %ld", g_scriptCount,
         g_exceptionLines, g_ownExceptions);
    Text("repeats collapsed: %ld; TruLink reads hidden: %ld; dropped by the rate limit: %ld", g_logCollapsed, g_logHidden,
         g_logDropped);
}

void PageMedia() {
    char list[1024];
    ValVideoList(list, sizeof(list));
    Text("Movies: %s   [media.video.list]", list);
    DWORD state = 0;
    ReadDword(kMainState, &state);
    char loop[64];
    ValMenuLoop(loop, sizeof(loop));
    Text("main state [0x%08lx] = %lu (10 = main menu); menu background loop [0x%08lx] = %s", kMainState, state,
         kMenuLoopPtr, loop);
    if (!g_experimental) return;
    char copy[1024];
    strncpy_s(copy, sizeof(copy), list, _TRUNCATE);
    char *context = nullptr;
    int i = 0;
    for (char *name = strtok_s(copy, " ", &context); name && strncmp(name, "no", 2); name = strtok_s(nullptr, " ", &context), ++i) {
        char label[96];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Play %s##vp%d", name, i);
        if (state != 10 || !g_movieOk) ImGui::BeginDisabled();
        if (ImGui::Button(label)) QueueItem("media.video.play", name);
        if (state != 10 || !g_movieOk) ImGui::EndDisabled();
        ImGui::SameLine();
        _snprintf_s(label, sizeof(label), _TRUNCATE, "as menu loop##vl%d", i);
        if (ImGui::Button(label)) QueueItem("media.video.menuloop", name);
    }
    if (ImGui::Button("menu loop back to medsea_loop")) QueueItem("media.video.menuloop", "");
    ImGui::TextWrapped("0x4a12b0(name, loop) is a blocking-style player (its callers loop while it plays): play only "
                       "from the main menu; experimental. The menu loop name is read when the main menu (re)starts "
                       "its background movie (0x5daf35).");
}

void DrawLogOverlay() {
    static LogLine lines[64];
    int c = CopyLines(lines, g_logLines, g_logFilter);
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 10.0f, vp->WorkPos.y + vp->WorkSize.y - 10.0f), ImGuiCond_Always,
                            ImVec2(0.0f, 1.0f));
    ImGui::SetNextWindowBgAlpha(0.4f);
    ImGui::SetNextWindowSizeConstraints(ImVec2(0.0f, 0.0f), ImVec2(vp->WorkSize.x * 0.6f, vp->WorkSize.y * 0.5f));
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruMenuLog", nullptr, flags)) {
        for (int i = 0; i < c; ++i) {
            char line[300];
            FormatLine(lines[i], line, sizeof(line), 160);
            BYTE sev = lines[i].sev;
            if (sev) ImGui::PushStyleColor(ImGuiCol_Text, sev == 2 ? ImVec4(1.0f, 0.5f, 0.4f, 1.0f) : ImVec4(1.0f, 0.85f, 0.4f, 1.0f));
            ImGui::TextUnformatted(line);
            if (sev) ImGui::PopStyleColor();
        }
        if (!c) ImGui::TextUnformatted("(log: no lines)");
    }
    ImGui::End();
}

void DrawMenu() {
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 40.0f, vp->WorkPos.y + 40.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(vp->WorkSize.x * 0.5f, vp->WorkSize.y * 0.7f), ImGuiCond_FirstUseEver);
    if (InterlockedExchange(&g_menuJustOpened, 0)) ImGui::SetNextWindowFocus();
    bool open = true;
    if (ImGui::Begin("TruMenu  (L3 + R3 closes)", &open, ImGuiWindowFlags_NoCollapse)) {
        // 0.4: TO TEST first, only while the list holds rows
        int open04, ok04, fail04, skip04, total04;
        TestCounts(&open04, &ok04, &fail04, &skip04, &total04);
        bool testShown = false;
        if (total04) {
            char header[96];
            _snprintf_s(header, sizeof(header), _TRUNCATE, "TO TEST (%d open, %d ok, %d fail, %d skip)###totest", open04,
                        ok04, fail04, skip04);
            ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.55f, 0.35f, 0.05f, 1.0f));
            bool show = ImGui::CollapsingHeader(header, ImGuiTreeNodeFlags_DefaultOpen);
            ImGui::PopStyleColor();
            if (show) { PageTests(); testShown = true; }
        }
        if (!testShown) InterlockedExchange(&g_testFocus, 0);
        if (ImGui::CollapsingHeader("Quick access / Favourites", ImGuiTreeNodeFlags_DefaultOpen)) PageFavourites();
        if (ImGui::CollapsingHeader("Status")) PageStatus();
        if (ImGui::CollapsingHeader("Developer menu (original)")) PageDev();
        if (ImGui::CollapsingHeader("Time / player / HUD")) PageTimePlayer();
        if (ImGui::CollapsingHeader("Instances")) PageInstances();
        if (ImGui::CollapsingHeader("Outfits (live switch)")) PageCostumeLive();
        if (ImGui::CollapsingHeader("Debug / Log")) PageLog();
        if (ImGui::CollapsingHeader("Media: videos")) PageMedia();
        if (ImGui::CollapsingHeader("Settings")) PageSettings();
        if (ImGui::CollapsingHeader("Overlay: Lara's position")) PageOverlay();
        if (ImGui::CollapsingHeader("Free camera")) PageCamera();
        if (ImGui::CollapsingHeader("Cheat / flight")) PageCheat();
        if (ImGui::CollapsingHeader("Markup / collision draw")) PageMarkup();
        if (ImGui::CollapsingHeader("Level select")) PageLevel();
        if (ImGui::CollapsingHeader("Outfits (next level load)")) PageOutfits();
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
    if (padIdle) WeaponsTick();
    KeyboardToggle();
    if (!g_menuOpen && !g_overlay && !g_logOverlay && !g_drawMarkup) return;
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
    if (g_drawMarkup) DrawMarkup();
    if (g_overlay) DrawOverlay();
    if (g_logOverlay) DrawLogOverlay();
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
    static bool seen = false;
    if (!seen) { seen = true; Log(1, "d3d9: first IDirect3DDevice9::Present call"); }
    Render(device);
    return g_presentOriginal(device, source, dest, window, dirty);
}

// the game may present through the implicit swap chain instead of the device (IDirect3DSwapChain9::Present, slot 3)
typedef HRESULT(STDMETHODCALLTYPE *SwapPresentFn)(IDirect3DSwapChain9 *, const RECT *, const RECT *, HWND,
                                                  const RGNDATA *, DWORD);
volatile SwapPresentFn g_swapPresentOriginal = nullptr;
volatile LONG g_inDevicePresent = 0;

HRESULT STDMETHODCALLTYPE SwapPresentHook(IDirect3DSwapChain9 *chain, const RECT *source, const RECT *dest,
                                          HWND window, const RGNDATA *dirty, DWORD flags) {
    static bool seen = false;
    if (!seen) { seen = true; Log(1, "d3d9: first IDirect3DSwapChain9::Present call"); }
    IDirect3DDevice9 *device = nullptr;
    if (SUCCEEDED(chain->GetDevice(&device)) && device) {
        Render(device);
        device->Release();
    }
    return g_swapPresentOriginal(chain, source, dest, window, dirty, flags);
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
    IDirect3DSwapChain9 *chain = nullptr;
    if (SUCCEEDED(device->GetSwapChain(0, &chain)) && chain) {
        void **chainVtable = nullptr;
        if (ReadDword(reinterpret_cast<DWORD>(chain), reinterpret_cast<DWORD *>(&chainVtable)) && chainVtable)
            PatchVtable(chainVtable, 3, reinterpret_cast<void *>(&SwapPresentHook),
                        reinterpret_cast<void *volatile *>(&g_swapPresentOriginal), "SwapChain Present");
        chain->Release();
    }
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
    // never placed yet (the game took XInput past our import filter and other plugins chained first): go on top once
    if (!g_padOriginal && current != reinterpret_cast<DWORD>(&PadHook)) {
        TakePointerLate(current);
        return;
    }
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
        LogTailTick();
        Sleep(g_device ? 250 : 50);
    }
    return 0;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH], text[32];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruMenu.ini", dir);
    // defaults: the kOpts table (also the source of the shipped TruMenu.ini)
    g_enabled = OptInt(ini, "Menu", "Enabled");
    g_logLevel = OptInt(ini, "Menu", "LogLevel");
    g_toggleButtons = static_cast<WORD>(OptInt(ini, "Menu", "ToggleButtons"));
    if (!g_toggleButtons) g_toggleButtons = kPadL3 | kPadR3;
    g_toggleKey = OptInt(ini, "Menu", "ToggleKey");
    OptString(ini, "Menu", "Scale", text, sizeof(text));
    g_scale = static_cast<float>(atof(text));
    if (!(g_scale >= 0.5f && g_scale <= 4.0f)) g_scale = static_cast<float>(atof(OptDefault("Menu", "Scale")));
    g_overlayAtStart = OptInt(ini, "Menu", "Overlay");
    g_blockInput = OptInt(ini, "Pad", "BlockInput");
    g_experimental = OptInt(ini, "Cheat", "Experimental");
    OptString(ini, "Cheat", "FlightSpeed", text, sizeof(text));
    g_flightSpeed = static_cast<float>(atof(text));
    if (!(g_flightSpeed > 0.0f && g_flightSpeed < 1000.0f))
        g_flightSpeed = static_cast<float>(atof(OptDefault("Cheat", "FlightSpeed")));
    OptString(ini, "Levels", "List", g_levelList, sizeof(g_levelList));
    strncpy_s(g_iniPath, sizeof(g_iniPath), ini, _TRUNCATE);
    OptString(ini, "Favorites", "Ids", g_favs, sizeof(g_favs));
    if (!g_favs[0]) strncpy_s(g_favs, sizeof(g_favs), kFavDefault, _TRUNCATE);
    g_logOverlayAtStart = OptInt(ini, "Log", "Overlay");
    g_logLinesAtStart = OptInt(ini, "Log", "Lines");
    if (g_logLinesAtStart < 1 || g_logLinesAtStart > 64) g_logLinesAtStart = atoi(OptDefault("Log", "Lines"));
    g_scriptLogAtStart = OptInt(ini, "Log", "Script");
    // 0.4: applied at once (also by settings.reset)
    InterlockedExchange(&g_logCollapse, OptInt(ini, "Log", "Collapse") ? 1 : 0);
    InterlockedExchange(&g_logHideReads, OptInt(ini, "Log", "HideLinkReads") ? 1 : 0);
    g_logMinLevel = OptInt(ini, "Log", "MinLevel");
    if (g_logMinLevel < 0 || g_logMinLevel > 2) g_logMinLevel = atoi(OptDefault("Log", "MinLevel"));
    g_logRate = OptInt(ini, "Log", "MaxLinesPerSecond");
    if (g_logRate < 0 || g_logRate > 10000) g_logRate = atoi(OptDefault("Log", "MaxLinesPerSecond"));
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruMenu.log", dir);
    strncpy_s(g_asiDir, sizeof(g_asiDir), dir, _TRUNCATE);
    DWORD exeLen = GetModuleFileNameA(nullptr, g_exeDir, MAX_PATH);
    while (exeLen > 0 && g_exeDir[exeLen - 1] != '\\' && g_exeDir[exeLen - 1] != '/') --exeLen;
    g_exeDir[exeLen] = 0;
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
    // costume: the level load's choice, the reset, the state save, name table lookup, validator, type-table operand
    // (the original table or a copy outside tru.exe, e.g. TruDlc2Player's)
    DWORD typeTable = 0;
    bool typeOk = HexBytesAt(kTypeLookup, "3935") && ReadDword(kTypeLookup + 2, &typeTable) &&
                  (typeTable == kTypeTableOrig || typeTable < kImageBase || typeTable >= 0x01000000);
    g_costumeOk = HexBytesAt(kLevelLoadChoice, kLevelLoadChoiceBytes) && HexBytesAt(kResetCostume, kResetCostumeBytes) &&
                  HexBytesAt(kSaveCostume, kSaveCostumeBytes) && HexBytesAt(kNameLookup, kNameLookupBytes) &&
                  HexBytesAt(kCostumeValid, kCostumeValidBytes) && typeOk;
    g_unitOk = HexBytesAt(kUnitLookup, kUnitLookupBytes) && HexBytesAt(kDefaultCostume, kDefaultCostumeBytes);
    // 0.3: every address used by the new items, by an instruction of the game that uses it (README "0.3 facts")
    g_timeOk = HexBytesAt(0x005d3d25, "d915d0f1e700") && HexBytesAt(0x005da3a0, "d905d0f1e700");
    g_pauseOk = HexBytesAt(0x00555d40, "810db8f0e70000002000");     // Restore Game: streamFlags |= 0x200000
    g_controlOk = HexBytesAt(0x005d5f45, "c605e6b48a0001") && HexBytesAt(0x005d5f60, "c605e6b48a0000");
    g_uiOk = HexBytesAt(0x005a434c, "803da0c9cd0000");
    // the game's own walk at 0x5d467d: esi = [0xd98d54]; ... esi = [esi+8]
    g_instOk = HexBytesAt(0x005b2ec6, "890d548dd900") && HexBytesAt(0x005d467d, "8b35548dd900 85f6 7410 56 e8e377feff 8b7608");
    g_removeOk = HexBytesAt(kRemoveInstance, kRemoveInstanceBytes) && g_instOk;
    g_switchOk = HexBytesAt(kCostumeSwitch, kCostumeSwitchBytes) && HexBytesAt(kCostumeSwitchAlt, kCostumeSwitchAltBytes) &&
                 HexBytesAt(0x006f0ac7, "8b1550eee700 8b7a04") && HexBytesAt(0x0079db50, "8b4c2404 e947b1fdff");
    g_movieOk = HexBytesAt(kMoviePlay, kMoviePlayBytes);
    g_mainStateOk = HexBytesAt(0x005d56e0, "a160ede700 83f806");
    DWORD loopPtr = 0;
    g_menuLoopOk = HexBytesAt(0x005daf35, "8b1520bf8a00 6a01 52 e86d63ecff") && ReadDword(kMenuLoopPtr, &loopPtr) &&
                   loopPtr == kMenuLoopOrig;
    // markup walk 0x5c3ce0 (box list +0x14, MarkUp +0x20 / +0x34, poly line +0x58, next +4), its caller with
    // [0xdb94cc], and the projection 0x49f630 (matrix, focal, centre constants)
    g_drawOk = HexBytesAt(0x005c3ce8, "8b5914 85db") && HexBytesAt(0x005c3d1e, "8b4320 d907 d84034") &&
               HexBytesAt(0x005c3d54, "d94034 8b4858") && HexBytesAt(0x005c3da2, "8b5b04 85db") &&
               HexBytesAt(0x005d3349, "8b0dcc94db00 e88c09ffff") && HexBytesAt(0x0049f64e, "d9050039a000") &&
               HexBytesAt(0x0049f67f, "d8052039a000") && HexBytesAt(0x0049f6f8, "d905d0068900") &&
               HexBytesAt(0x0049f702, "dc05003a8400") && HexBytesAt(0x0049f713, "dc05c8548400") && g_playerOk;
    // weapons / ammo / health (catalog 17): give-by-name, the HUD's reserve reader, GetHealth, MaxHealth
    g_weaponOk = HexBytesAt(kGiveWeapon, "8b44240c 8b542404 56 8bf1 8b4c240c 50 51 52 e86995eaff") && g_mainStateOk;
    g_ammoOk = HexBytesAt(0x006e8475, "0fb784511c050000");
    g_healthOk = HexBytesAt(0x006e7860, "a158dbfa00 85c0 7407 d98028060000 c3") &&
                 HexBytesAt(kMaxHealth, "51 a16492c500 8b80a4ef0300 8b1550eee700");
    g_scriptOk = HexBytesAt(0x007b3990, "68305e7900 6a07");            // native 7 registration (NsCoreBase)
    for (int i = 0; i < kNativeCount && g_scriptOk; ++i) g_scriptOk = HexBytesAt(g_natives[i].addr, g_natives[i].bytes);
    // 0.4: weapon slots (the game's handle check 0x5b39d0 and the slot reader 0x6e7b90: right +4 / +8, left +0xc /
    // +0x10), MaxAmmo 0x6eeae0 (6-entry jump table), GiveObject 0x555f60 and the save-restore callback 0x715e90
    g_slotsOk = HexBytesAt(0x005b39d0, "8b4c2404 85c9 740e 8b01 85c0 7408 8b5044 3b5104") &&
                HexBytesAt(0x006e7bb9, "8b543e10 8b4c3e0c") && HexBytesAt(0x006e7bde, "8b443e04 8b4c3e08") &&
                HexBytesAt(0x006e7b98, "83fe0e") && g_playerOk;
    g_maxAmmoOk = HexBytesAt(kMaxAmmo, "0fbe442404 83f805 0f8779010000 ff24856cec6e00") &&
                  HexBytesAt(0x006eec67, "660dffff c3") && g_playerOk;
    g_gearOk = HexBytesAt(kGiveObject, "56 8b74240c 56 e8e5d90500 8b54240c 83c404 85c0 7410") &&
               HexBytesAt(kGearCallback, "8b44240c 83e800 742a 83e801 754b 8b442408 8b4810 8b5160") &&
               HexBytesAt(0x00715eb2, "a158dbfa00 8b8800050000") && g_mainStateOk && g_playerOk;
    _snprintf_s(g_testPath, sizeof(g_testPath), _TRUNCATE, "%sTruMenu.tests.txt", g_exeDir);
    TestLoad();
    DevRead();
    g_logOverlay = g_logOverlayAtStart ? 1 : 0;
    g_logLines = g_logLinesAtStart;
    if (g_scriptLogAtStart && g_scriptOk && g_experimental) {   // at load no script runs yet: patch here
        char text[160];
        SetScriptLog(true, text, sizeof(text));
    }
    Log(1, "0.3 checks: time %d, pause %d, control %d, ui %d, instances %d, remove %d, costume switch %d, movie %d, "
           "main state %d, menu loop %d, script natives %d, markup draw %d; dev menu: %s", g_timeOk, g_pauseOk,
        g_controlOk, g_uiOk, g_instOk, g_removeOk, g_switchOk, g_movieOk, g_mainStateOk, g_menuLoopOk, g_scriptOk,
        g_drawOk, g_devStatus);
    Log(1, "0.3 checks: weapon.give %d, ammo %d, health %d", g_weaponOk, g_ammoOk, g_healthOk);
    Log(1, "0.4 checks: weapon slots %d, MaxAmmo %d, gear give %d; TO TEST file %s", g_slotsOk, g_maxAmmoOk, g_gearOk,
        g_testPath);
    Log(1, "code checks: pad %d, d3d9 %d, player %d, INSTANCE_Post %d, camera %d, frame time %d, level change %d, "
           "costume %d (type table 0x%08lx), unit table %d", g_padCodeOk, g_d3dCodeOk, g_playerOk, g_postOk, g_cameraOk,
        g_frameOk, g_levelOk, g_costumeOk, typeTable, g_unitOk);
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
        InitializeCriticalSection(&g_logRingLock);
        InitializeCriticalSection(&g_favLock);
        InitializeCriticalSection(&g_testLock);
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
