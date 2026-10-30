// TruShadowPower.asi - DLC 2 "Lara's Shadow" shadow-power slow motion for the PC tru.exe (Steam, image base 0x400000).
//
// The Xbox title update gives Lara the Doppelgaenger's power: while LB or RB is held the world runs at 0.3 and Lara at
// 1.2 of normal speed. The PC exe never got that code, but it has the engine's time-scale system the title update
// drives (docs/WINDOWS_REBUILD.md finding 43, test 39b). This plugin does what the title update does for the slow
// motion only: on a press / release of the shadow buttons it calls the engine's own setters with the Xbox values.
//
//   tru+0x84b82  call dword ptr [0x00a02b8c]   the per-frame pad poll (XInputGetState via a stored pointer)
//   tru+0x376030 SetWorldTimeScale(float target, float seconds)   __stdcall, ret 8 (world ramp 0x8abeb4)
//   tru+0x376090 SetPlayerTimeScale(float target, float seconds)  __stdcall, ret 8 (player ramp 0x8abe94)
//
// The plugin replaces the stored XInputGetState pointer with a wrapper that calls the original and then, on the same
// (game) thread, reacts to the button edges. Every address is checked against the expected bytes first; on any
// mismatch nothing is hooked and the reason is logged. Not covered: the shadow meter, the blur / bloom look, rock
// veins, the shadow jump and combat moves. Active in every level (no DLC 2 check yet) - see README.md.
//
// Loaded by the Ultimate ASI Loader that the installed game ships as binkw32.dll (it loads every *.asi next to
// tru.exe, the same way it loads ModLoader.asi). Options: TruShadowPower.ini next to the .asi (see README.md).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

struct PadState {                       // XINPUT_STATE without including xinput.h
    DWORD dwPacketNumber;
    WORD wButtons;
    BYTE bLeftTrigger, bRightTrigger;
    SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY;
};

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, PadState *);
typedef void(__stdcall *SetTimeScaleFn)(float target, float seconds);

const DWORD kImageBase = 0x00400000;
const DWORD kCallSite = 0x00484b82;     // ff 15 8c 2b a0 00 = call dword ptr [0x00a02b8c]
const DWORD kPadPointer = 0x00a02b8c;
const DWORD kSetWorld = 0x00776030;
const DWORD kSetPlayer = 0x00776090;
const BYTE kCallBytes[] = {0xff, 0x15, 0x8c, 0x2b, 0xa0, 0x00};
// first 12 bytes of both setters: push ecx; mov eax,[0xe7f15c]; fild dword [0xe7f15c]; test eax,eax
const BYTE kSetterBytes[] = {0x51, 0xa1, 0x5c, 0xf1, 0xe7, 0x00, 0xdb, 0x05, 0x5c, 0xf1, 0xe7, 0x00};
const BYTE kWorldRamp[] = {0xb9, 0xb4, 0xbe, 0x8a, 0x00};   // mov ecx,0x8abeb4 at +0x1d
const BYTE kPlayerRamp[] = {0xb9, 0x94, 0xbe, 0x8a, 0x00};  // mov ecx,0x8abe94 at +0x1d

// options (TruShadowPower.ini, section [ShadowPower])
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 every button edge, 3 debug
WORD g_buttons = 0x0300;                // LB 0x0100 | RB 0x0200 (Xbox: either); LB also sprints on PC
float g_world = 0.3f, g_player = 1.2f, g_ramp = 0.033f;   // Xbox title update values

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
volatile XInputGetStateFn g_original = nullptr;
SetTimeScaleFn g_setWorld = reinterpret_cast<SetTimeScaleFn>(kSetWorld);
SetTimeScaleFn g_setPlayer = reinterpret_cast<SetTimeScaleFn>(kSetPlayer);
WORD g_lastButtons[4] = {0, 0, 0, 0};
bool g_active = false;
volatile LONG g_stop = 0;

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

bool BytesAt(DWORD address, const BYTE *expected, size_t length) {
    __try {
        return memcmp(reinterpret_cast<const void *>(address), expected, length) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    DWORD result = g_original ? g_original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    if (result != ERROR_SUCCESS || !state || index > 3) return result;
    WORD held = state->wButtons & g_buttons;
    WORD before = g_lastButtons[index];
    g_lastButtons[index] = held;
    bool any = false;
    for (int i = 0; i < 4; ++i) any = any || g_lastButtons[i] != 0;
    if (any == g_active) return result;
    g_active = any;
    // the game thread is inside its pad poll here (the debugger prototype injected the same calls at this point)
    if (any) {
        g_setWorld(g_world, g_ramp);
        g_setPlayer(g_player, g_ramp);
    } else {
        g_setWorld(1.0f, g_ramp);
        g_setPlayer(1.0f, g_ramp);
    }
    Log(2, "pad %lu buttons 0x%04x (was 0x%04x): shadow power %s", index, held, before, any ? "ON" : "OFF");
    return result;
}

// The game fills the pad pointer itself (GetProcAddress) - wait for it, swap it, and re-swap if the game ever
// writes the original back (e.g. after a device change).
DWORD WINAPI HookThread(LPVOID) {
    volatile LONG *slot = reinterpret_cast<volatile LONG *>(kPadPointer);
    for (int waited = 0; !g_stop; ++waited) {
        LONG current = *slot;
        LONG ours = static_cast<LONG>(reinterpret_cast<LONG_PTR>(&PadHook));
        if (current != 0 && current != ours) {
            g_original = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            if (InterlockedCompareExchange(slot, ours, current) == current)
                Log(1, "pad pointer 0x%08lx hooked (original XInputGetState 0x%08lx)", kPadPointer, current);
        } else if (current == 0 && waited == 600) {
            Log(1, "pad pointer still empty after 60 s - still waiting");
        }
        Sleep(current == ours ? 1000 : 100);
    }
    return 0;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruShadowPower.ini", dir);
    char value[32];
    g_enabled = GetPrivateProfileIntA("ShadowPower", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowPower", "LogLevel", 1, ini);
    g_buttons = static_cast<WORD>(GetPrivateProfileIntA("ShadowPower", "Buttons", 0x0300, ini));
    GetPrivateProfileStringA("ShadowPower", "WorldScale", "0.3", value, sizeof(value), ini);
    g_world = static_cast<float>(atof(value));
    GetPrivateProfileStringA("ShadowPower", "PlayerScale", "1.2", value, sizeof(value), ini);
    g_player = static_cast<float>(atof(value));
    GetPrivateProfileStringA("ShadowPower", "RampSeconds", "0.033", value, sizeof(value), ini);
    g_ramp = static_cast<float>(atof(value));
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowPower.log", dir);
    ReadOptions(dir);
    Log(1, "TruShadowPower loaded (enabled %d, buttons 0x%04x, world %.3f, player %.3f, ramp %.3f s)", g_enabled,
        g_buttons, g_world, g_player, g_ramp);
    if (!g_enabled) { Log(1, "disabled by TruShadowPower.ini - nothing hooked"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not hooked", base, kImageBase); return; }
    if (!BytesAt(kCallSite, kCallBytes, sizeof(kCallBytes))) {
        Log(0, "pad poll call at 0x%08lx does not match (other tru.exe build?) - not hooked", kCallSite);
        return;
    }
    if (!BytesAt(kSetWorld, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetWorld + 0x1d, kWorldRamp, 5) ||
        !BytesAt(kSetPlayer, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetPlayer + 0x1d, kPlayerRamp, 5)) {
        Log(0, "time-scale setters at 0x%08lx / 0x%08lx do not match - not hooked", kSetWorld, kSetPlayer);
        return;
    }
    Log(3, "code checks passed (call site, both setters and their ramps)");
    HANDLE thread = CreateThread(nullptr, 0, HookThread, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
    else Log(0, "CreateThread failed (%lu) - not hooked", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_stop = 1;
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruShadowPowerVersion() { return "TruShadowPower 0.1 (slow motion only)"; }
