// TruLink.asi - live read / write channel into the running tru.exe (Steam, image base 0x400000) for our tests.
//
// A small TCP server bound to 127.0.0.1 ONLY (port from TruLink.ini, default 9265; 9264 is FMOD's profiler port)
// takes one client at a time and answers a line-based text protocol (README.md): memory reads / writes, the object
// table, the player instance, our loaded plugins, and two game functions (CAMERA_SetMode 0x5f39f0 / camera restore
// 0x5edf50, INSTANCE_Post 0x5b3750). It replaces the cdb command-file channel of the earlier debug sessions.
//
// Threads: the server thread does the socket work and the memory commands (guarded with __try / __except, ranges
// checked with VirtualQuery). Commands that call game functions are queued (one slot) and run on the game thread from
// the per-frame pad poll (tru+0x84b82, call dword ptr [0x00a02b8c] = XInputGetState), which TruShadowPower.asi and
// TruMenu.asi hook as well - the chaining rules below keep the order of the plugins irrelevant.
//
// Every game address is checked against the expected bytes at load; on a mismatch the affected command answers
// "err" and the reason is logged. Loaded by the Ultimate ASI Loader (binkw32.dll of the installed game).

#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

#pragma comment(lib, "ws2_32.lib")

namespace {

const char kVersion[] = "0.2";

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, void *);
typedef void(__cdecl *CameraSetModeFn)(int mode);
typedef void(__fastcall *ThisCallFn)(void *self, int);                 // thiscall without stack arguments
typedef void(__cdecl *InstancePostFn)(void *instance, int message, int data);

const DWORD kImageBase = 0x00400000;
const DWORD kCallSite = 0x00484b82;     // ff 15 8c 2b a0 00 = call dword ptr [0x00a02b8c]
const BYTE kCallBytes[] = {0xff, 0x15, 0x8c, 0x2b, 0xa0, 0x00};
const DWORD kPadPointer = 0x00a02b8c;   // filled by the game: LoadLibraryW(L"xinput9_1_0.dll") + "XInputGetState"
const DWORD kGameClock = 0x00e7f15c;    // ms, advances once per frame (TruShadowPower)
const DWORD kGameTracker = 0x00e7f088;  // +0xc player instance, +0xbc cheatMode (TRLAU-menu-hook Game.h)
const DWORD kPlayerPtr = 0x00e7f094;    // GameTracker +0xc
const DWORD kCheatMode = 0x00e7f144;    // GameTracker +0xbc (byte)
const DWORD kPlayerState = 0x00fadb58;  // player game-state pointer (Befund-Entwicklerkanal 4)
const DWORD kCameraManager = 0x00e804f0;
const DWORD kCurrentCamera = 0x00e80534; // [mgr+0x44]; slot table [mgr+4+4*mode], modes 0..15

// CAMERA_SetMode (cdecl, mode): only 6, 11 and 12 switch anything in retail (11 = free camera, 12 = 0x5f2ba0(1),
// 6 = 0x5eb3c0); other modes return without a change
const DWORD kCameraSetMode = 0x005f39f0;
const BYTE kCameraSetModeBytes[] = {0x56, 0x8b, 0x74, 0x24, 0x08, 0x83, 0xfe, 0x06, 0x75, 0x1e, 0x81, 0x3d, 0x34,
                                    0x05, 0xe8, 0x00, 0xe0, 0xea, 0xe8, 0x00, 0x74, 0x68, 0xa1, 0xf8, 0xf3, 0xe7,
                                    0x00, 0x50, 0xb9, 0xf0, 0x04, 0xe8, 0x00};
// camera restore (thiscall CameraManager, no stack arguments; ends in jmp [[mgr+0x44]]->vfunc+8)
const DWORD kCameraRestore = 0x005edf50;
const BYTE kCameraRestoreBytes[] = {0xd9, 0x05, 0x30, 0x11, 0x84, 0x00, 0x56, 0x8b, 0xf1, 0x33, 0xc9, 0xd9, 0x5e,
                                    0x78, 0x39, 0x4e, 0x4c};
// INSTANCE_Post (cdecl instance, message, data): instance +0x120 handler called as (instance, message, data)
const DWORD kInstancePost = 0x005b3750;
const BYTE kInstancePostBytes[] = {0x56, 0x8b, 0x74, 0x24, 0x08, 0x8d, 0x86, 0x10, 0x01, 0x00, 0x00, 0x85, 0xc0,
                                   0x74, 0x22, 0x57, 0x8b, 0xbe, 0x20, 0x01, 0x00, 0x00, 0x85, 0xff, 0x74, 0x16,
                                   0x56, 0xe8, 0x70, 0xf6, 0xff, 0xff, 0x8b, 0x4c, 0x24, 0x18, 0x8b, 0x54, 0x24,
                                   0x14, 0x51, 0x52, 0x56, 0xff, 0xd7, 0x83, 0xc4, 0x10};
// object table: 0xcc entries of 0x24 bytes, +8 object, +0xc s16 id, +0xe u16 state (2 = loaded); checked through
// the lookup tru+0x14e930 that walks it (as TruShadowPower)
const DWORD kFindObject = 0x0054e930;
const BYTE kFindObjectBytes[] = {0x8b, 0x54, 0x24, 0x04, 0x33, 0xc0, 0xb9, 0x0c, 0x74, 0xdb, 0x00};
const DWORD kFindObjectLoop = 0x0054e951;
const BYTE kFindObjectLoopBytes[] = {0x83, 0xc1, 0x24, 0x3d, 0xcc, 0x00, 0x00, 0x00};
const DWORD kObjectTable = 0x00db7400;
const int kObjectCount = 0xcc;

const DWORD kMaxRead = 4096;
const DWORD kMaxWrite = 1024;

// options (TruLink.ini)
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info + every write / game call, 2 every command, 3 debug
int g_port = 9265;
int g_allowForce = 1;                   // 0 = the "force" flag is refused
int g_timeoutMs = 5000;                 // wait for the game thread (camera / post)

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
volatile LONG g_stop = 0;
DWORD g_imageStart = 0, g_imageEnd = 0;
bool g_hookOk = false, g_cameraOk = false, g_restoreOk = false, g_postOk = false, g_tableOk = false;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[1024];
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

// ---- memory access ----

const DWORD kReadable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READ |
                        PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
const DWORD kWritable = PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;

// Checks [address, address + length) region by region with VirtualQuery (no IsBadReadPtr). Allowed without "force":
// the tru.exe image and private memory (heap, VirtualAlloc, stacks - MEM_PRIVATE). Other modules' images and mapped
// files need "force". Writes to read-only pages are allowed in the tru.exe image (or with force): the write then goes
// through VirtualProtect. Returns nullptr when allowed, else the reason.
const char *CheckRange(DWORD address, DWORD length, bool write, bool force) {
    if (!length) return "length 0";
    if (address + length < address) return "range wraps around";
    if (force && !g_allowForce) return "force is switched off in TruLink.ini (AllowForce=0)";
    DWORD p = address, end = address + length;
    while (p < end) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(reinterpret_cast<void *>(p), &mbi, sizeof(mbi))) return "VirtualQuery failed";
        if (mbi.State != MEM_COMMIT) return "not committed memory";
        if ((mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) || !(mbi.Protect & kReadable)) return "page not readable";
        bool inImage = p >= g_imageStart && p < g_imageEnd;
        if (!force && !inImage && mbi.Type != MEM_PRIVATE)
            return "outside the tru.exe image and private memory (add 'force' to override)";
        if (write && !(mbi.Protect & kWritable) && !inImage && !force)
            return "read-only page outside the tru.exe image (add 'force' to override)";
        DWORD next = reinterpret_cast<DWORD>(mbi.BaseAddress) + static_cast<DWORD>(mbi.RegionSize);
        if (next <= p) return "VirtualQuery loop";
        p = next;
    }
    return nullptr;
}

bool ReadBytes(DWORD address, BYTE *out, DWORD length) {
    __try {
        memcpy(out, reinterpret_cast<const void *>(address), length);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool CopyGuarded(DWORD address, const BYTE *data, DWORD length) {
    __try {
        memcpy(reinterpret_cast<void *>(address), data, length);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// writes region by region; read-only pages (code) are opened with VirtualProtect for the copy and restored, then the
// instruction cache is flushed. Returns nullptr or the reason.
const char *WriteBytes(DWORD address, const BYTE *data, DWORD length, int *protectedRegions) {
    *protectedRegions = 0;
    DWORD p = address, end = address + length;
    while (p < end) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(reinterpret_cast<void *>(p), &mbi, sizeof(mbi))) return "VirtualQuery failed";
        DWORD regionEnd = reinterpret_cast<DWORD>(mbi.BaseAddress) + static_cast<DWORD>(mbi.RegionSize);
        DWORD chunk = (regionEnd < end ? regionEnd : end) - p;
        const BYTE *src = data + (p - address);
        if (mbi.Protect & kWritable) {
            if (!CopyGuarded(p, src, chunk)) return "access fault while writing";
        } else {
            DWORD old = 0, dummy = 0;
            if (!VirtualProtect(reinterpret_cast<void *>(p), chunk, PAGE_EXECUTE_READWRITE, &old))
                return "VirtualProtect failed";
            bool ok = CopyGuarded(p, src, chunk);
            VirtualProtect(reinterpret_cast<void *>(p), chunk, old, &dummy);
            ++*protectedRegions;
            if (!ok) return "access fault while writing";
        }
        p += chunk;
    }
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), length);
    return nullptr;
}

bool Read32(DWORD address, DWORD *value) {
    if (CheckRange(address, 4, false, false)) return false;
    return ReadBytes(address, reinterpret_cast<BYTE *>(value), 4);
}

// ---- game-thread job (one slot; the server handles one command at a time) ----

enum { kJobIdle = 0, kJobQueued = 1, kJobRunning = 2, kJobDone = 3 };
enum { kKindCamera = 1, kKindCameraRestore = 2, kKindPost = 3 };
struct Job {
    volatile LONG state;
    int kind;
    DWORD a, b, c;
    bool faulted;
    DWORD frame;                        // game clock when it ran
};
Job g_job;
HANDLE g_jobDone = nullptr;

void RunJobBody() {
    switch (g_job.kind) {
    case kKindCamera:
        reinterpret_cast<CameraSetModeFn>(kCameraSetMode)(static_cast<int>(g_job.a));
        break;
    case kKindCameraRestore:
        reinterpret_cast<ThisCallFn>(kCameraRestore)(reinterpret_cast<void *>(kCameraManager), 0);
        break;
    case kKindPost:
        reinterpret_cast<InstancePostFn>(kInstancePost)(reinterpret_cast<void *>(g_job.a), static_cast<int>(g_job.b),
                                                        static_cast<int>(g_job.c));
        break;
    }
}

void RunJob() {
    if (InterlockedCompareExchange(&g_job.state, kJobRunning, kJobQueued) != kJobQueued) return;
    g_job.faulted = false;
    g_job.frame = *reinterpret_cast<volatile DWORD *>(kGameClock);
    __try {
        RunJobBody();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_job.faulted = true;
    }
    InterlockedExchange(&g_job.state, kJobDone);
    SetEvent(g_jobDone);
}

// queues a job and waits; returns nullptr when it ran, else the reason
const char *CallOnGameThread(int kind, DWORD a, DWORD b, DWORD c) {
    if (!g_hookOk) return "pad poll hook not installed (see status / TruLink.log)";
    ResetEvent(g_jobDone);
    g_job.kind = kind;
    g_job.a = a; g_job.b = b; g_job.c = c;
    InterlockedExchange(&g_job.state, kJobQueued);
    if (WaitForSingleObject(g_jobDone, static_cast<DWORD>(g_timeoutMs)) != WAIT_OBJECT_0) {
        // not picked up: take it back; if the game thread just took it, wait for the end
        if (InterlockedCompareExchange(&g_job.state, kJobIdle, kJobQueued) == kJobQueued)
            return "timeout: the game thread did not poll the pad (paused / loading / hook bypassed? see status)";
        WaitForSingleObject(g_jobDone, 30000);
    }
    bool faulted = g_job.faulted;
    InterlockedExchange(&g_job.state, kJobIdle);
    return faulted ? "access fault inside the game function (caught)" : nullptr;
}

// ---- per-frame hook (pad poll) ----
//
// Chaining: the slot 0x00a02b8c holds one pointer. Every plugin saves what it finds there, puts its own hook in and
// calls the saved pointer. TruShadowPower 0.5 re-swaps whenever the slot is not its own hook, which would close a
// loop with any other plugin doing the same (A calls B calls A ...). TruLink therefore
//   1. installs itself on top of whatever is in the slot (the real XInputGetState or another plugin's hook),
//   2. re-installs only when the slot holds the real function again (the game wrote it back), never over another
//      plugin's hook - that plugin has saved TruLink's pointer and calls it,
//   3. breaks a loop: if the plugin it calls takes the slot over (it then calls TruLink), or if TruLink is re-entered
//      on the same thread, it calls the real XInputGetState (xinput9_1_0.dll, resolved by name) from then on.
// So every hook in the chain runs once per poll, whatever the load order.

volatile XInputGetStateFn g_next = nullptr;   // what TruLink calls
volatile XInputGetStateFn g_real = nullptr;   // XInputGetState itself
DWORD g_tls = TLS_OUT_OF_INDEXES;
volatile LONG g_padCalls = 0, g_frames = 0, g_reentries = 0;
volatile DWORD g_lastClock = 0, g_lastCallTick = 0;

void ModuleName(DWORD address, char *name, size_t size) {
    name[0] = 0;
    HMODULE mod = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(address), &mod) || !mod) {
        strncpy_s(name, size, "?", _TRUNCATE);
        return;
    }
    char path[MAX_PATH];
    DWORD len = GetModuleFileNameA(mod, path, MAX_PATH);
    const char *base = path;
    for (DWORD i = 0; i < len; ++i)
        if (path[i] == '\\' || path[i] == '/') base = path + i + 1;
    strncpy_s(name, size, len ? base : "?", _TRUNCATE);
}

void ResolveReal() {
    const char *const dlls[] = {"xinput9_1_0.dll", "xinput1_4.dll", "xinput1_3.dll"};
    for (const char *dll : dlls) {
        HMODULE mod = GetModuleHandleA(dll);
        if (!mod) continue;
        FARPROC fn = GetProcAddress(mod, "XInputGetState");
        if (fn) {
            g_real = reinterpret_cast<XInputGetStateFn>(fn);
            Log(1, "XInputGetState resolved: %s 0x%08lx", dll, reinterpret_cast<DWORD>(fn));
            return;
        }
    }
}

DWORD WINAPI PadHook(DWORD index, void *state) {
    if (TlsGetValue(g_tls)) {
        // re-entered on the same thread: the chain loops back to TruLink - end it here with the real function and
        // let the outer call skip the loop from now on
        if (InterlockedIncrement(&g_reentries) == 1)
            Log(1, "pad hook re-entered (hook chain loops back to TruLink) - calling XInputGetState directly from now on");
        XInputGetStateFn real = g_real;
        if (real) g_next = real;
        return real ? real(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    }
    TlsSetValue(g_tls, reinterpret_cast<void *>(1));
    XInputGetStateFn next = g_next;
    if (!next) next = g_real;
    DWORD result = next ? next(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    InterlockedIncrement(&g_padCalls);
    g_lastCallTick = GetTickCount();
    DWORD clock = *reinterpret_cast<volatile DWORD *>(kGameClock);
    if (clock != g_lastClock) {
        g_lastClock = clock;
        InterlockedIncrement(&g_frames);
    }
    if (g_job.state == kJobQueued) RunJob();
    TlsSetValue(g_tls, nullptr);
    return result;
}

DWORD WINAPI HookThread(LPVOID) {
    volatile LONG *slot = reinterpret_cast<volatile LONG *>(kPadPointer);
    const LONG ours = static_cast<LONG>(reinterpret_cast<LONG_PTR>(&PadHook));
    bool installed = false;
    for (int waited = 0; !g_stop; ++waited) {
        LONG current = *slot;
        if (current && !g_real) ResolveReal();
        if (current == 0) {
            if (waited == 600) Log(1, "pad pointer still empty after 60 s - still waiting");
        } else if (current != ours) {
            char name[MAX_PATH];
            ModuleName(static_cast<DWORD>(current), name, sizeof(name));
            bool isReal = _strnicmp(name, "xinput", 6) == 0 ||
                          (g_real && current == static_cast<LONG>(reinterpret_cast<LONG_PTR>(g_real)));
            if (isReal || !installed) {
                g_next = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
                if (InterlockedCompareExchange(slot, ours, current) == current) {
                    Log(1, "pad pointer 0x%08lx %shooked, TruLink calls 0x%08lx (%s%s)", kPadPointer,
                        installed ? "re-" : "", current, name, isReal ? ", XInputGetState" : ", another plugin - chained");
                    installed = true;
                    g_hookOk = true;
                }
            } else if (g_real && reinterpret_cast<LONG>(g_next) == current) {
                // the plugin TruLink calls took the slot over and now calls TruLink: calling it back would loop
                g_next = g_real;
                Log(1, "pad pointer taken over by 0x%08lx (%s), which TruLink called - TruLink now calls XInputGetState "
                       "0x%08lx directly (loop avoided)", current, name, reinterpret_cast<DWORD>(g_real));
            } else {
                static LONG lastForeign = 0;
                if (lastForeign != current) {
                    lastForeign = current;
                    Log(1, "pad pointer now 0x%08lx (%s) - assumed to chain to TruLink, left in place", current, name);
                }
            }
        }
        Sleep(installed ? 500 : 100);
    }
    return 0;
}

// ---- parsing ----

bool ParseHex(const char *s, DWORD *value) {
    if (!s || !*s) return false;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
    if (!*s) return false;
    char *end = nullptr;
    unsigned long v = strtoul(s, &end, 16);
    if (*end) return false;
    *value = v;
    return true;
}

// "0x.." hex, otherwise decimal (signed)
bool ParseNumber(const char *s, DWORD *value) {
    if (!s || !*s) return false;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) return ParseHex(s, value);
    char *end = nullptr;
    long v = strtol(s, &end, 10);
    if (*end) {
        unsigned long u = strtoul(s, &end, 10);
        if (*end) return false;
        *value = u;
        return true;
    }
    *value = static_cast<DWORD>(v);
    return true;
}

// address: hex ("e7f144", "0xe7f144") or a name - player (the player instance [0xe7f094]), gametracker (0xe7f088),
// cheat (0xe7f144), camera (current camera [0xe80534]), cameramgr (0xe804f0), playerstate ([0xfadb58]) - with an
// optional "+hex" offset, e.g. player+0x20
bool ParseAddress(const char *s, DWORD *value, char *err, size_t errSize) {
    char base[64];
    strncpy_s(base, sizeof(base), s, _TRUNCATE);
    DWORD offset = 0;
    char *plus = strchr(base, '+');
    if (plus) {
        *plus = 0;
        if (!ParseHex(plus + 1, &offset)) { _snprintf_s(err, errSize, _TRUNCATE, "bad offset '%s'", plus + 1); return false; }
    }
    DWORD v = 0;
    struct { const char *name; DWORD address; bool pointer; } const names[] = {
        {"player", kPlayerPtr, true}, {"gametracker", kGameTracker, false}, {"cheat", kCheatMode, false},
        {"camera", kCurrentCamera, true}, {"cameramgr", kCameraManager, false}, {"playerstate", kPlayerState, true}};
    bool named = false;
    for (const auto &n : names) {
        if (_stricmp(base, n.name)) continue;
        named = true;
        v = n.address;
        if (n.pointer && !Read32(n.address, &v)) {
            _snprintf_s(err, errSize, _TRUNCATE, "cannot read the %s pointer at 0x%08lx", n.name, n.address);
            return false;
        }
        if (n.pointer && !v) { _snprintf_s(err, errSize, _TRUNCATE, "%s pointer is 0 (not in game?)", n.name); return false; }
    }
    if (!named && !ParseHex(base, &v)) { _snprintf_s(err, errSize, _TRUNCATE, "bad address '%s'", s); return false; }
    *value = v + offset;
    return true;
}

// ---- answers ----

struct Out {
    char buf[65536];
    size_t n;
    void Reset() { n = 0; buf[0] = 0; }
    void Add(const char *fmt, ...) {
        if (n >= sizeof(buf) - 1) return;
        va_list ap;
        va_start(ap, fmt);
        int w = _vsnprintf_s(buf + n, sizeof(buf) - n, _TRUNCATE, fmt, ap);
        va_end(ap);
        n = w < 0 ? strlen(buf) : n + static_cast<size_t>(w);
    }
};
Out g_out;

void AddHex(const BYTE *data, DWORD length) {
    for (DWORD i = 0; i < length; ++i) g_out.Add("%02x", data[i]);
}

int ModeOfCamera(DWORD camera) {
    for (int mode = 0; mode < 16; ++mode) {
        DWORD slot = 0;
        if (Read32(kCameraManager + 4 + 4 * mode, &slot) && slot == camera && camera) return mode;
    }
    return -1;
}

void CmdHelp() {
    g_out.Add("ok+ help\n"
              "ping                          -> pong TruLink <version>\n"
              "status                        hook / chain / code checks (block)\n"
              "read <addr> <len> [force]     hex bytes (len <= 4096)\n"
              "read32 <addr> | readf <addr>  dword (hex + signed) | float\n"
              "write <addr> <hexbytes> [force]      e.g. write cheat 01 (answer names the old bytes)\n"
              "write32 <addr> <value> [force] | writef <addr> <float> [force]\n"
              "player                        player instance + position (+0x20)\n"
              "camera                        current camera + mode | camera <mode> | camera restore (game thread)\n"
              "post <instance> <msg> <data>  INSTANCE_Post on the game thread (instance may be 'player')\n"
              "objects                       object table 0xdb7400: index id state object (block)\n"
              "modules                       loaded .asi plugins + versions (block)\n"
              "menu list | menu <id> [arg]   TruMenu items: list (block) | run one by id (ok / err line)\n"
              "log <0-3>                    TruLink.log level\n"
              "quit                          close the connection\n"
              "addr: hex or player | gametracker | cheat | camera | cameramgr | playerstate, optional +hexoffset\n"
              ".\n");
}

void CmdStatus() {
    DWORD slot = 0;
    Read32(kPadPointer, &slot);
    char slotName[MAX_PATH], nextName[MAX_PATH];
    ModuleName(slot, slotName, sizeof(slotName));
    ModuleName(reinterpret_cast<DWORD>(g_next), nextName, sizeof(nextName));
    DWORD since = g_lastCallTick ? GetTickCount() - g_lastCallTick : 0xffffffff;
    g_out.Add("ok+ status\n");
    g_out.Add("version %s port %d loglevel %d force %d timeout %d ms\n", kVersion, g_port, g_logLevel, g_allowForce,
              g_timeoutMs);
    g_out.Add("hook %s slot 0x%08lx (%s) next 0x%08lx (%s) real 0x%08lx self 0x%08lx\n", g_hookOk ? "on" : "off", slot,
              slotName, reinterpret_cast<DWORD>(g_next), nextName, reinterpret_cast<DWORD>(g_real),
              reinterpret_cast<DWORD>(&PadHook));
    g_out.Add("pad calls %ld frames %ld last call %ld ms ago reentries %ld\n", g_padCalls, g_frames,
              since == 0xffffffff ? -1L : static_cast<long>(since), g_reentries);
    g_out.Add("checks camera %d restore %d post %d objects %d image 0x%08lx-0x%08lx\n", g_cameraOk, g_restoreOk,
              g_postOk, g_tableOk, g_imageStart, g_imageEnd);
    g_out.Add(".\n");
}

void CmdRead(char **tok, int count, bool force) {
    char err[128];
    DWORD address = 0, length = 0;
    if (count < 3 || !ParseAddress(tok[1], &address, err, sizeof(err))) {
        g_out.Add("err %s\n", count < 3 ? "usage: read <addr> <len> [force]" : err);
        return;
    }
    if (!ParseNumber(tok[2], &length) || !length || length > kMaxRead) { g_out.Add("err len 1..%lu\n", kMaxRead); return; }
    const char *why = CheckRange(address, length, false, force);
    if (why) { g_out.Add("err 0x%08lx: %s\n", address, why); return; }
    static BYTE data[kMaxRead];
    if (!ReadBytes(address, data, length)) { g_out.Add("err 0x%08lx: access fault (caught)\n", address); return; }
    g_out.Add("ok 0x%08lx %lu ", address, length);
    AddHex(data, length);
    g_out.Add("\n");
}

void CmdRead32(char **tok, int count, bool force, bool asFloat) {
    char err[128];
    DWORD address = 0, value = 0;
    if (count < 2 || !ParseAddress(tok[1], &address, err, sizeof(err))) {
        g_out.Add("err %s\n", count < 2 ? "usage: read32|readf <addr> [force]" : err);
        return;
    }
    const char *why = CheckRange(address, 4, false, force);
    if (why) { g_out.Add("err 0x%08lx: %s\n", address, why); return; }
    if (!ReadBytes(address, reinterpret_cast<BYTE *>(&value), 4)) { g_out.Add("err 0x%08lx: access fault (caught)\n", address); return; }
    if (asFloat) {
        float f;
        memcpy(&f, &value, 4);
        g_out.Add("ok 0x%08lx %.9g 0x%08lx\n", address, static_cast<double>(f), value);
    } else {
        g_out.Add("ok 0x%08lx 0x%08lx %ld\n", address, value, static_cast<long>(value));
    }
}

void DoWrite(DWORD address, const BYTE *data, DWORD length, bool force) {
    const char *why = CheckRange(address, length, true, force);
    if (why) { g_out.Add("err 0x%08lx: %s\n", address, why); return; }
    static BYTE old[kMaxWrite];
    if (!ReadBytes(address, old, length)) { g_out.Add("err 0x%08lx: access fault (caught)\n", address); return; }
    int protectedRegions = 0;
    why = WriteBytes(address, data, length, &protectedRegions);
    if (why) { g_out.Add("err 0x%08lx: %s\n", address, why); Log(0, "write 0x%08lx (%lu bytes) failed: %s", address, length, why); return; }
    g_out.Add("ok wrote %lu at 0x%08lx%s was ", length, address, protectedRegions ? " (VirtualProtect)" : "");
    AddHex(old, length);
    g_out.Add("\n");
    Log(1, "write 0x%08lx %lu bytes%s%s", address, length, protectedRegions ? " (code page, VirtualProtect)" : "",
        force ? " FORCE" : "");
}

void CmdWrite(char **tok, int count, bool force) {
    char err[128];
    DWORD address = 0;
    if (count < 3 || !ParseAddress(tok[1], &address, err, sizeof(err))) {
        g_out.Add("err %s\n", count < 3 ? "usage: write <addr> <hexbytes> [force]" : err);
        return;
    }
    static BYTE data[kMaxWrite];
    DWORD length = 0;
    for (int i = 2; i < count; ++i) {
        const char *s = tok[i];
        if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
        size_t len = strlen(s);
        if (len % 2) { g_out.Add("err odd number of hex digits in '%s'\n", tok[i]); return; }
        for (size_t k = 0; k < len; k += 2) {
            char two[3] = {s[k], s[k + 1], 0};
            char *end = nullptr;
            unsigned long b = strtoul(two, &end, 16);
            if (*end) { g_out.Add("err bad hex '%s'\n", tok[i]); return; }
            if (length >= kMaxWrite) { g_out.Add("err at most %lu bytes\n", kMaxWrite); return; }
            data[length++] = static_cast<BYTE>(b);
        }
    }
    if (!length) { g_out.Add("err no bytes\n"); return; }
    DoWrite(address, data, length, force);
}

void CmdWrite32(char **tok, int count, bool force, bool asFloat) {
    char err[128];
    DWORD address = 0, value = 0;
    if (count < 3 || !ParseAddress(tok[1], &address, err, sizeof(err))) {
        g_out.Add("err %s\n", count < 3 ? "usage: write32|writef <addr> <value> [force]" : err);
        return;
    }
    if (asFloat) {
        char *end = nullptr;
        float f = static_cast<float>(strtod(tok[2], &end));
        if (*end) { g_out.Add("err bad float '%s'\n", tok[2]); return; }
        memcpy(&value, &f, 4);
    } else if (!ParseNumber(tok[2], &value)) {
        g_out.Add("err bad value '%s'\n", tok[2]);
        return;
    }
    DoWrite(address, reinterpret_cast<const BYTE *>(&value), 4, force);
}

void CmdPlayer() {
    DWORD player = 0;
    if (!Read32(kPlayerPtr, &player)) { g_out.Add("err cannot read 0x%08lx\n", kPlayerPtr); return; }
    if (!player) { g_out.Add("ok none (GameTracker +0xc is 0)\n"); return; }
    float pos[3];
    if (CheckRange(player + 0x20, 12, false, false) || !ReadBytes(player + 0x20, reinterpret_cast<BYTE *>(pos), 12)) {
        g_out.Add("err player instance 0x%08lx not readable\n", player);
        return;
    }
    g_out.Add("ok instance 0x%08lx pos %.3f %.3f %.3f\n", player, static_cast<double>(pos[0]),
              static_cast<double>(pos[1]), static_cast<double>(pos[2]));
}

void AddCurrentCamera(const char *prefix) {
    DWORD camera = 0;
    if (!Read32(kCurrentCamera, &camera)) { g_out.Add("err cannot read 0x%08lx\n", kCurrentCamera); return; }
    g_out.Add("ok %scurrent 0x%08lx mode %d\n", prefix, camera, ModeOfCamera(camera));
}

void CmdCamera(char **tok, int count) {
    if (count < 2) { AddCurrentCamera(""); return; }
    const char *why = nullptr;
    if (!_stricmp(tok[1], "restore")) {
        if (!g_restoreOk) { g_out.Add("err camera restore 0x%08lx not verified (other exe?)\n", kCameraRestore); return; }
        Log(1, "camera restore (0x%08lx on the game thread)", kCameraRestore);
        why = CallOnGameThread(kKindCameraRestore, 0, 0, 0);
    } else {
        DWORD mode = 0;
        if (!ParseNumber(tok[1], &mode) || mode > 15) { g_out.Add("err usage: camera [<mode 0..15> | restore]\n"); return; }
        if (!g_cameraOk) { g_out.Add("err CAMERA_SetMode 0x%08lx not verified (other exe?)\n", kCameraSetMode); return; }
        Log(1, "CAMERA_SetMode(%lu) on the game thread", mode);
        why = CallOnGameThread(kKindCamera, mode, 0, 0);
    }
    if (why) { g_out.Add("err %s\n", why); Log(0, "camera: %s", why); return; }
    AddCurrentCamera("done, ");
}

void CmdPost(char **tok, int count) {
    char err[128];
    DWORD instance = 0, message = 0, data = 0;
    if (count < 4) { g_out.Add("err usage: post <instance> <msg> <data>\n"); return; }
    if (!ParseAddress(tok[1], &instance, err, sizeof(err))) { g_out.Add("err %s\n", err); return; }
    if (!ParseNumber(tok[2], &message) || !ParseNumber(tok[3], &data)) { g_out.Add("err bad msg / data\n"); return; }
    if (!g_postOk) { g_out.Add("err INSTANCE_Post 0x%08lx not verified (other exe?)\n", kInstancePost); return; }
    const char *why = CheckRange(instance, 0x124, false, false);
    if (why) { g_out.Add("err instance 0x%08lx: %s\n", instance, why); return; }
    DWORD handler = 0;
    Read32(instance + 0x120, &handler);
    if (!handler) { g_out.Add("err instance 0x%08lx has no message handler (+0x120 = 0)\n", instance); return; }
    Log(1, "INSTANCE_Post(0x%08lx, %lu, 0x%08lx) on the game thread (handler 0x%08lx)", instance, message, data, handler);
    why = CallOnGameThread(kKindPost, instance, message, data);
    if (why) { g_out.Add("err %s\n", why); Log(0, "post: %s", why); return; }
    g_out.Add("ok posted %lu data 0x%08lx to 0x%08lx (handler 0x%08lx, frame %lu)\n", message, data, instance, handler,
              g_job.frame);
}

void CmdObjects() {
    if (!g_tableOk) { g_out.Add("err object table code not verified (other exe?)\n"); return; }
    static BYTE table[kObjectCount * 0x24];
    if (!ReadBytes(kObjectTable, table, sizeof(table))) { g_out.Add("err access fault (caught)\n"); return; }
    int used = 0;
    for (int i = 0; i < kObjectCount; ++i)
        if (*reinterpret_cast<const WORD *>(table + i * 0x24 + 0xe)) ++used;
    g_out.Add("ok+ objects %d of %d in use (index id state object)\n", used, kObjectCount);
    for (int i = 0; i < kObjectCount; ++i) {
        const BYTE *e = table + i * 0x24;
        WORD state = *reinterpret_cast<const WORD *>(e + 0xe);
        if (!state) continue;
        g_out.Add("%d %d %u 0x%08lx\n", i, *reinterpret_cast<const SHORT *>(e + 0xc), state,
                  *reinterpret_cast<const DWORD *>(e + 8));
    }
    g_out.Add(".\n");
}

// 0.2: TruMenu items by id - "menu list" = TruMenuList(), "menu <id> [arg]" = TruMenuInvoke(id, arg). TruMenu runs
// items that touch the game on its own game-thread hook and waits up to 3 s itself, so this runs on the server thread.
typedef const char *(__cdecl *MenuListFn)();
typedef const char *(__cdecl *MenuInvokeFn)(const char *id, const char *arg);

void CmdMenu(char **tok, int count) {
    if (count < 2) { g_out.Add("err usage: menu list | menu <id> [arg]\n"); return; }
    HMODULE menu = GetModuleHandleA("TruMenu.asi");
    if (!menu) { g_out.Add("err no TruMenu\n"); return; }
    if (!_stricmp(tok[1], "list")) {
        MenuListFn list = reinterpret_cast<MenuListFn>(GetProcAddress(menu, "TruMenuList"));
        if (!list) { g_out.Add("err TruMenu has no TruMenuList export\n"); return; }
        const char *text = list();
        g_out.Add("ok+ menu items (id type value label, tab separated)\n");
        g_out.Add("%s", text ? text : "");
        g_out.Add(".\n");
        return;
    }
    MenuInvokeFn invoke = reinterpret_cast<MenuInvokeFn>(GetProcAddress(menu, "TruMenuInvoke"));
    if (!invoke) { g_out.Add("err TruMenu has no TruMenuInvoke export\n"); return; }
    char arg[512] = "";
    for (int i = 2; i < count; ++i) {                          // the rest of the line is the argument
        if (i > 2) strncat_s(arg, sizeof(arg), " ", _TRUNCATE);
        strncat_s(arg, sizeof(arg), tok[i], _TRUNCATE);
    }
    const char *answer = invoke(tok[1], arg);
    g_out.Add("%s\n", answer ? answer : "err (null)");
    Log(2, "menu %s %s -> %s", tok[1], arg, answer ? answer : "(null)");
}

typedef const char *(*VersionFn)();

const char *CallVersion(FARPROC fn) {
    __try {
        const char *s = reinterpret_cast<VersionFn>(fn)();
        if (!s) return "(null)";
        volatile char first = *s;            // fault here -> caught
        (void)first;
        return s;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return "(fault)";
    }
}

void CmdModules() {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE) { g_out.Add("err CreateToolhelp32Snapshot failed (%lu)\n", GetLastError()); return; }
    g_out.Add("ok+ modules (.asi: name base size version)\n");
    const char *const known[] = {"TruShadowPower", "TruDlc2Player", "TruDoppelganger", "TruRockVein", "TruMenu",
                                 "TruLink"};
    bool seen[6] = {false, false, false, false, false, false};
    MODULEENTRY32 me;
    me.dwSize = sizeof(me);
    for (BOOL ok = Module32First(snap, &me); ok; ok = Module32Next(snap, &me)) {
        size_t len = strlen(me.szModule);
        if (len < 5 || _stricmp(me.szModule + len - 4, ".asi")) continue;
        char stem[MAX_PATH];
        strncpy_s(stem, sizeof(stem), me.szModule, len - 4);
        for (int k = 0; k < 6; ++k)
            if (!_stricmp(stem, known[k])) seen[k] = true;
        char exportName[MAX_PATH + 16];
        _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", stem);
        FARPROC fn = GetProcAddress(me.hModule, exportName);
        g_out.Add("%s 0x%08lx %lu %s\n", me.szModule, reinterpret_cast<DWORD>(me.modBaseAddr), me.modBaseSize,
                  fn ? CallVersion(fn) : "-");
    }
    CloseHandle(snap);
    for (int k = 0; k < 6; ++k)
        if (!seen[k]) g_out.Add("%s.asi not loaded\n", known[k]);
    g_out.Add(".\n");
}

// one line in, answer in g_out; returns false to close the connection
bool HandleLine(char *line) {
    g_out.Reset();
    char *tok[24];
    int count = 0;
    char *context = nullptr;
    for (char *t = strtok_s(line, " \t", &context); t && count < 24; t = strtok_s(nullptr, " \t", &context))
        tok[count++] = t;
    if (!count) return true;                                   // empty line: no answer
    bool force = false;
    if (count > 1 && !_stricmp(tok[count - 1], "force")) { force = true; --count; }
    const char *cmd = tok[0];
    if (cmd[0] == '#') return true;                            // comment (script files)
    if (!_stricmp(cmd, "ping")) g_out.Add("pong TruLink %s\n", kVersion);
    else if (!_stricmp(cmd, "help")) CmdHelp();
    else if (!_stricmp(cmd, "status")) CmdStatus();
    else if (!_stricmp(cmd, "read")) CmdRead(tok, count, force);
    else if (!_stricmp(cmd, "read32")) CmdRead32(tok, count, force, false);
    else if (!_stricmp(cmd, "readf")) CmdRead32(tok, count, force, true);
    else if (!_stricmp(cmd, "write")) CmdWrite(tok, count, force);
    else if (!_stricmp(cmd, "write32")) CmdWrite32(tok, count, force, false);
    else if (!_stricmp(cmd, "writef")) CmdWrite32(tok, count, force, true);
    else if (!_stricmp(cmd, "player")) CmdPlayer();
    else if (!_stricmp(cmd, "camera")) CmdCamera(tok, count);
    else if (!_stricmp(cmd, "post")) CmdPost(tok, count);
    else if (!_stricmp(cmd, "objects")) CmdObjects();
    else if (!_stricmp(cmd, "modules")) CmdModules();
    else if (!_stricmp(cmd, "menu")) CmdMenu(tok, count);
    else if (!_stricmp(cmd, "log")) {
        DWORD level = 0;
        if (count < 2 || !ParseNumber(tok[1], &level) || level > 3) g_out.Add("err usage: log <0-3>\n");
        else { g_logLevel = static_cast<int>(level); g_out.Add("ok log level %d\n", g_logLevel); }
    } else if (!_stricmp(cmd, "quit") || !_stricmp(cmd, "exit") || !_stricmp(cmd, "bye")) {
        g_out.Add("ok bye\n");
        return false;
    } else {
        g_out.Add("err unknown command '%s' (help)\n", cmd);
    }
    return true;
}

// ---- server ----

bool SendAll(SOCKET s, const char *data, size_t length) {
    while (length) {
        int w = send(s, data, static_cast<int>(length > 0x10000 ? 0x10000 : length), 0);
        if (w <= 0) return false;
        data += w;
        length -= static_cast<size_t>(w);
    }
    return true;
}

DWORD WINAPI ServerThread(LPVOID) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) { Log(0, "WSAStartup failed - no server"); return 0; }
    SOCKET listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listener == INVALID_SOCKET) { Log(0, "socket failed (%d) - no server", WSAGetLastError()); return 0; }
    BOOL exclusive = TRUE;                                     // no other process can bind the same port over us
    setsockopt(listener, SOL_SOCKET, SO_EXCLUSIVEADDRUSE, reinterpret_cast<const char *>(&exclusive), sizeof(exclusive));
    sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(static_cast<u_short>(g_port));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);          // 127.0.0.1 only - never INADDR_ANY
    if (bind(listener, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == SOCKET_ERROR ||
        listen(listener, 1) == SOCKET_ERROR) {
        Log(0, "bind / listen on 127.0.0.1:%d failed (%d) - port in use? no server", g_port, WSAGetLastError());
        closesocket(listener);
        return 0;
    }
    u_long nonBlocking = 1;
    ioctlsocket(listener, FIONBIO, &nonBlocking);
    Log(1, "listening on 127.0.0.1:%d (one client at a time)", g_port);
    SOCKET client = INVALID_SOCKET;
    static char buf[8192];
    int used = 0;
    while (!g_stop) {
        fd_set readable;
        FD_ZERO(&readable);
        FD_SET(listener, &readable);
        if (client != INVALID_SOCKET) FD_SET(client, &readable);
        timeval tv = {0, 250000};
        int n = select(0, &readable, nullptr, nullptr, &tv);
        if (n == SOCKET_ERROR) { Sleep(250); continue; }
        if (n == 0) continue;
        if (FD_ISSET(listener, &readable)) {
            sockaddr_in peer;
            int peerLength = sizeof(peer);
            SOCKET s = accept(listener, reinterpret_cast<sockaddr *>(&peer), &peerLength);
            if (s != INVALID_SOCKET) {
                u_long blocking = 0;
                ioctlsocket(s, FIONBIO, &blocking);
                DWORD sendTimeout = 5000;
                setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&sendTimeout), sizeof(sendTimeout));
                if ((ntohl(peer.sin_addr.s_addr) >> 24) != 127) {
                    closesocket(s);                            // cannot happen on a loopback socket - belt and braces
                } else if (client != INVALID_SOCKET) {
                    const char busy[] = "err busy: another client is connected\n";
                    SendAll(s, busy, sizeof(busy) - 1);
                    closesocket(s);
                    Log(2, "second client refused (busy)");
                } else {
                    client = s;
                    used = 0;
                    Log(1, "client connected (port %u)", ntohs(peer.sin_port));
                }
            }
        }
        if (client == INVALID_SOCKET || !FD_ISSET(client, &readable)) continue;
        int r = recv(client, buf + used, static_cast<int>(sizeof(buf)) - 1 - used, 0);
        if (r <= 0) {
            closesocket(client);
            client = INVALID_SOCKET;
            Log(1, "client disconnected");
            continue;
        }
        used += r;
        bool keep = true;
        for (;;) {
            char *newline = static_cast<char *>(memchr(buf, '\n', static_cast<size_t>(used)));
            if (!newline) break;
            *newline = 0;
            int consumed = static_cast<int>(newline - buf) + 1;
            if (newline > buf && newline[-1] == '\r') newline[-1] = 0;
            char line[sizeof(buf)];
            strcpy_s(line, sizeof(line), buf);
            memmove(buf, buf + consumed, static_cast<size_t>(used - consumed));
            used -= consumed;
            Log(2, "> %s", line);
            keep = HandleLine(line);
            if (g_out.n && !SendAll(client, g_out.buf, g_out.n)) keep = false;
            if (!keep) break;
        }
        if (keep && used >= static_cast<int>(sizeof(buf)) - 1) {
            const char tooLong[] = "err line too long\n";
            SendAll(client, tooLong, sizeof(tooLong) - 1);
            used = 0;
        }
        if (!keep) {
            closesocket(client);
            client = INVALID_SOCKET;
            Log(1, "client closed");
        }
    }
    if (client != INVALID_SOCKET) closesocket(client);
    closesocket(listener);
    return 0;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruLink.ini", dir);
    g_enabled = GetPrivateProfileIntA("TruLink", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("TruLink", "LogLevel", 1, ini);
    g_port = GetPrivateProfileIntA("TruLink", "Port", 9265, ini);
    g_allowForce = GetPrivateProfileIntA("TruLink", "AllowForce", 1, ini);
    g_timeoutMs = GetPrivateProfileIntA("TruLink", "GameThreadTimeoutMs", 5000, ini);
    if (g_timeoutMs < 500) g_timeoutMs = 500;
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruLink.log", dir);
    ReadOptions(dir);
    Log(1, "TruLink %s loaded (enabled %d, port %d, log level %d, force %d)", kVersion, g_enabled, g_port, g_logLevel,
        g_allowForce);
    if (!g_enabled) { Log(1, "disabled by TruLink.ini - no server, no hook"); return; }
    if (g_port <= 0 || g_port > 65535 || g_port == 9264) {
        Log(0, "port %d not usable (9264 is FMOD's profiler port) - no server", g_port);
        return;
    }
    HMODULE exe = GetModuleHandleA(nullptr);
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(exe));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not started", base, kImageBase); return; }
    const IMAGE_DOS_HEADER *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
    const IMAGE_NT_HEADERS *nt = reinterpret_cast<const IMAGE_NT_HEADERS *>(base + dos->e_lfanew);
    g_imageStart = base;
    g_imageEnd = base + nt->OptionalHeader.SizeOfImage;
    bool callOk = BytesAt(kCallSite, kCallBytes, sizeof(kCallBytes));
    g_cameraOk = BytesAt(kCameraSetMode, kCameraSetModeBytes, sizeof(kCameraSetModeBytes));
    g_restoreOk = BytesAt(kCameraRestore, kCameraRestoreBytes, sizeof(kCameraRestoreBytes));
    g_postOk = BytesAt(kInstancePost, kInstancePostBytes, sizeof(kInstancePostBytes));
    g_tableOk = BytesAt(kFindObject, kFindObjectBytes, sizeof(kFindObjectBytes)) &&
                BytesAt(kFindObjectLoop, kFindObjectLoopBytes, sizeof(kFindObjectLoopBytes));
    Log(1, "code checks: pad call %d, CAMERA_SetMode %d, camera restore %d, INSTANCE_Post %d, object table %d", callOk,
        g_cameraOk, g_restoreOk, g_postOk, g_tableOk);
    g_jobDone = CreateEventA(nullptr, FALSE, FALSE, nullptr);
    g_tls = TlsAlloc();
    if (callOk && g_jobDone && g_tls != TLS_OUT_OF_INDEXES) {
        HANDLE hook = CreateThread(nullptr, 0, HookThread, nullptr, 0, nullptr);
        if (hook) CloseHandle(hook);
        else Log(0, "CreateThread (hook) failed (%lu)", GetLastError());
    } else {
        Log(0, "pad poll call at 0x%08lx does not match (or no event / TLS) - no game-thread commands", kCallSite);
    }
    HANDLE server = CreateThread(nullptr, 0, ServerThread, nullptr, 0, nullptr);
    if (server) CloseHandle(server);
    else Log(0, "CreateThread (server) failed (%lu)", GetLastError());
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

// exported so TruLink's own "modules" command and other tools can identify the plugin
extern "C" __declspec(dllexport) const char *TruLinkVersion() {
    return "TruLink 0.2 (127.0.0.1 text channel: read / write / camera / post / objects / modules / menu)";
}
