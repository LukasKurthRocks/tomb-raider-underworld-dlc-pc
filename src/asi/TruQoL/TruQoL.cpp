// TruQoL.asi - comfort options for players of the PC tru.exe (Steam, unpacked, image base 0x400000). TruMenu is the
// debug tool; this plugin only holds switches a player wants, each with its own INI key (TruQoL.ini) and one log line
// per feature in TruQoL.log (on / off / why). Owner decision 2026-11-08: frame limiter on at 60 fps by default,
// everything else neutral (= the game's own behaviour) unless the INI says otherwise. Plugin README: INI reference,
// evidence, TO TEST list. Workshop: work\qol17x_0811 (static checks, disassembly listings).
//
// 1. [FrameLimit] - the game's frame-time function 0x5da230 (called once per frame by the main-state handlers, e.g.
//    0x5e012e, 0x5dde91, 0x5daab8) reads the microsecond clock 0x597f10 (QueryPerformanceCounter 0x597e90, monotonic
//    sum 0xcdb4d8) at 0x5da247 (running) or 0x5da684 (paused branch, [0xe7f0b4] & 0x10000000), averages the last six
//    deltas (ring 0xe7ee10), clamps to 66 666 us and stores dt = us / 33 333.33 (double 0x855280) to 0xe7f190 / 0xe7f194
//    (1.0 = one 30 fps frame) and dt x time scales to 0xe7f188. The plugin points the rel32 of both clock calls to
//    ClockStub = wait until the next frame slot, then the game's clock: the game measures the limited frame itself, no
//    D3D hook (no conflict with TruMenu's Present / Reset hook or a d3d9.dll wrapper). Waiting: a high-resolution
//    waitable timer (Windows 10 1803+; else timeBeginPeriod(1) + a normal timer) until SpinUs before the slot, then a
//    short pause-loop - no busy core. Auto-off when the loaded d3d9.dll / dxgi.dll is DXVK (its tru.exe profile sets
//    d3d9.maxFrameRate = -60; dxvk.conf / DXVK_FRAME_RATE checked) or dxwrapper with LimitPerFrameFPS > 0.
// 2. [Camera] Fov - the render projection: 0x5cb0a8 `call 0x5e78d0` (the camera FOV getter: [0xe8eec0] while the
//    snapshot byte [0xe8eec8] is set, else current camera [0xe80534] vtable +0x40, base 0x5e1c90 = fld [ecx+0xb0])
//    stores the scene FOV 0xe49700; its only reader 0x5ce949 passes it to 0x5129d0(out, fov, aspect, near, far), which
//    computes tan(fov x 0.5) (0.5 = double 0x8413c0, tan 0x813870 = fptan) and m00 = 1 / (aspect x tan), m11 = 1 / tan:
//    the FOV is the VERTICAL angle in RADIANS (aspect 0xe49704 = [[0xad75e4]+0x170] / 10000). About 25 camera sites
//    write +0xb0 every frame (cinematic keys, gameplay tuning), so Fov is a FACTOR on the game's value (an absolute
//    angle would flatten cinematic zooms). Only the call 0x5cb0a8 is redirected (the other getter callers 0x6b134a,
//    0x6e4ce4 keep the game's value - nothing scaled is ever written back). FovCutscenes=0: only while the current
//    camera [0xe80534] is the gameplay camera [0xe804f0+0xb80].
// 2. [Camera] ShakeScale - the shake strength 0x5eb460 (esi = slot of the pool 0xe80020, result in st0) has two
//    callers, 0x5eea55 (camera apply) and 0x5eb56d (shake sum); both rel32 -> ShakeStub (the game's function, then
//    fmul by the factor) - the same two sites TruMenu's cam.shakescale uses (TruMenu then refuses its slider and logs
//    "another plugin?"; with ShakeScale=1.0 TruQoL patches nothing).
// 3. [Startup] ThreadCap - the start-up crash with > 31 logical CPUs: the CPU topology count 0x4a21d0 (called once:
//    WinMain 0x479c80 -> 0x47a0bb -> 0x4a28e0 -> 0x4a2904) asks GetProcessAffinityMask at 0x4a2238 and walks mask =
//    1 << i while mask <= the system mask; the step 0x4a2455 `mov eax, 1; mov ecx, edi; shl eax, cl` shifts modulo 32,
//    so with bit 31 set (>= 32 threads; a 32-bit process sees 0xffffffff) the mask never becomes 0 or exceeds the
//    system mask and 0x4a235d `mov [ebp+edi+0x284], al` writes past a 256-byte stack array (0xc0000409). An unequal
//    process / system mask returns 8 at once (0x4a2244) - why the `start /affinity FFFF` work-around helps. The plugin
//    replaces `call [0x83e0a8]` at 0x4a2238 (6 bytes) by `call CappedAffinity; nop`: both masks & ((1 << ThreadCap) - 1)
//    only when the system mask has a bit at or above ThreadCap. Early enough: the Ultimate ASI Loader (binkw32.dll)
//    loads the plugins at tru.exe's first GetStartupInfoA call (CRT 0x818255, default dontloadfromdllmain = 1, IAT hook
//    0x1001a570), before WinMain is called at 0x8183b3; this plugin patches in DllMain. After the count WinMain pins
//    the main thread to CPU 0 (0x47a0c9), so the capped mask the count restores at 0x4a2477 has no lasting effect.
// Every engine address is byte-checked before it is patched; on a mismatch that feature stays off and the log says why.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif

namespace {

const char kVersion[] = "TruQoL 0.1";
const DWORD kImageBase = 0x00400000;

// ---- 1. frame limiter: the frame-time function 0x5da230 and its two clock reads ----
const DWORD kFrameTimer = 0x005da230;
const char *const kFrameTimerHex = "83ec0c f705b4f0e70000000010 53 56 57 0f85db030000 55 e8c4dcfbff 8b35c4ede700";
const DWORD kClockCallRun = 0x005da247;     // running: call 0x597f10, then the six-frame average
const DWORD kClockCallPause = 0x005da684;   // paused branch 0x5da621: call 0x597f10
const char *const kClockCallPauseHex = "e887d8fbff 8bc8 2b0d38eee700 8bf2 1b353ceee700";
const DWORD kClock = 0x00597f10;            // u64 microseconds (edx:eax), QueryPerformanceCounter 0x597e90
const char *const kClockHex = "56 e87affffff 8bc8 2b0de0b4cd00 8bf2 1b35e4b4cd00";
const DWORD kFrameStore = 0x005da47c;       // fdiv qword [0x855280] (us -> 30 fps units) ... fst dword [0xe7f190]
const char *const kFrameStoreHex = "dc3580528500 d91d88f1e700 d90588f1e700 d91594f1e700 d91590f1e700";

// ---- 2. camera: FOV at the render projection, shake strength ----
const DWORD kFovCall = 0x005cb0a8;          // call 0x5e78d0; mov eax, [0xad75e4]; fstp [0xe49700]
const char *const kFovCallHex = "e823c80100 a1e475ad00 d91d0097e400";
const DWORD kFovGetter = 0x005e78d0;
const char *const kFovGetterHex = "803dc8eee80000 7407 d905c0eee800 c3 8b0d3405e800 8b01 8b5040 ffe2";
const DWORD kFovReader = 0x005ce949;        // the only reader of 0xe49700: fov argument of the perspective 0x5129d0
const char *const kFovReaderHex = "d9050097e400 d91c24 50 e87840f4ff";
const DWORD kPerspective = 0x005129d0;      // tan(fov x 0.5): fld [ebp+0xc]; fmul qword [0x8413c0]; ...; call tan
const char *const kPerspectiveHex = "55 8bec 83e4f0 83ec10 d9450c dc0dc0138400 d95c240c d944240c e8810e3000";
const DWORD kCamCurrent = 0x00e80534;       // [camera manager 0xe804f0 + 0x44]
const DWORD kCamGameplay = 0x00e81070;      // [camera manager 0xe804f0 + 0xb80]
const DWORD kShakeFn = 0x005eb460;          // strength (esi = slot), result st0
const char *const kShakeFnHex = "55 8bec 83e4f0 83ec30 80be8400000000 0f84c1000000";
const DWORD kShakeCall1 = 0x005eea55;       // camera apply
const char *const kShakeCall1Hex = "e806caffff d95c2414";
const DWORD kShakeCall2 = 0x005eb56d;       // shake sum
const char *const kShakeCall2Hex = "e8eefeffff d84f78";

// ---- 3. start-up: the CPU topology count 0x4a21d0 ----
const DWORD kAffinityCall = 0x004a2238;     // call [0x83e0a8] GetProcessAffinityMask (the only caller in tru.exe)
const char *const kAffinityCallHex = "ff15a8e08300 8b557c 3b5578 7407 b008";
const DWORD kAffinityArgs = 0x004a2215;     // lea eax, [ebp+0x78] (system mask); ...; lea ecx, [ebp+0x7c] (process)
const char *const kAffinityArgsHex = "8d4578 894d60 50 8d4d7c 33ff 51";
const DWORD kAffinityIat = 0x0083e0a8;
const DWORD kCpuLoopStep = 0x004a2455;      // mov eax, 1; mov ecx, edi; shl eax, cl (modulo 32 = the bug)
const char *const kCpuLoopStepHex = "b801000000 8bcf d3e0 897d64 85c0 894554 0f8504feffff";
const DWORD kCpuOverflow = 0x004a235d;      // mov [ebp+edi+0x284], al (256-byte array)
const char *const kCpuOverflowHex = "88843d84020000";
const DWORD kCpuCountCall = 0x0047a0bb;     // WinMain 0x479c80 -> 0x4a28e0; then SetThreadAffinityMask(thread, 1)
const char *const kCpuCountCallHex = "e820880200 6a01 ff1584e08300 50 ff1578e08300";

// ---- options (TruQoL.ini) ----
int g_enabled = 1, g_logLevel = 1;
int g_limitEnabled = 1, g_maxFps = 60, g_autoOff = 1, g_spinUs = 0;
float g_fov = 0.0f;                         // factor; 0 (or 1) = game
int g_fovCutscenes = 0;
float g_shakeScale = 1.0f;                  // read by ShakeStub
int g_threadCap = 31;

char g_logPath[MAX_PATH], g_dir[MAX_PATH];
CRITICAL_SECTION g_logLock;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[900];
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

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[96];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

bool ReadDword(DWORD address, DWORD *value) {
    __try {
        *value = *reinterpret_cast<const DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(reinterpret_cast<void *>(address), bytes, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(address), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), length);
    return true;
}

// target of the rel32 call at site (0 when the byte there is not E8)
DWORD CallTarget(DWORD site) {
    const BYTE call = 0xe8;
    DWORD rel = 0;
    if (!BytesAt(site, &call, 1) || !ReadDword(site + 1, &rel)) return 0;
    return site + 5 + rel;
}

// a group of rel32 call sites that must all call `game` today; all are pointed to `hook`, or none
bool RedirectCalls(const DWORD *sites, int count, DWORD game, DWORD hook, const char *what) {
    for (int i = 0; i < count; ++i) {
        DWORD t = CallTarget(sites[i]);
        if (t != game) {
            Log(0, "%s: the call at 0x%08lx goes to 0x%08lx, not the game's 0x%08lx (another plugin?) - left untouched, "
                   "feature off", what, sites[i], t, game);
            return false;
        }
    }
    for (int i = 0; i < count; ++i) {
        DWORD rel = hook - (sites[i] + 5);
        if (!WriteCode(sites[i] + 1, &rel, 4)) {
            for (int j = 0; j < i; ++j) {           // put back what was already written
                DWORD back = game - (sites[j] + 5);
                WriteCode(sites[j] + 1, &back, 4);
            }
            Log(0, "%s: patch failed at 0x%08lx - nothing stays patched", what, sites[i]);
            return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// INI
void IniPath(char *out, size_t n) { _snprintf_s(out, n, _TRUNCATE, "%sTruQoL.ini", g_dir); }

int IniInt(const char *section, const char *key, int def, int lo, int hi) {
    char ini[MAX_PATH], v[64];
    IniPath(ini, sizeof(ini));
    GetPrivateProfileStringA(section, key, "", v, sizeof(v), ini);
    if (!v[0]) return def;
    char *end = nullptr;
    long x = strtol(v, &end, 10);
    while (end && (*end == ' ' || *end == '\t')) ++end;
    if (!end || end == v || *end || x < lo || x > hi) {
        Log(0, "[%s] %s=%s is not a whole number in %d .. %d - default %d used", section, key, v, lo, hi, def);
        return def;
    }
    return static_cast<int>(x);
}

float IniFloat(const char *section, const char *key, float def, float lo, float hi) {
    char ini[MAX_PATH], v[64];
    IniPath(ini, sizeof(ini));
    GetPrivateProfileStringA(section, key, "", v, sizeof(v), ini);
    if (!v[0]) return def;
    char *end = nullptr;
    double x = strtod(v, &end);
    while (end && (*end == ' ' || *end == '\t')) ++end;
    if (!end || end == v || *end || !(x >= lo && x <= hi)) {
        Log(0, "[%s] %s=%s is not a number in %.2f .. %.2f - default %.2f used", section, key, v, lo, hi, def);
        return def;
    }
    return static_cast<float>(x);
}

// ---------------------------------------------------------------------------------------------------------------
// 1. frame limiter
LONGLONG g_qpf = 0, g_period = 0, g_next = 0, g_spinTicks = 0;
HANDLE g_timer = nullptr;
bool g_hiRes = false;
volatile LONG g_limitLive = 0;              // 1 = waiting, 0 = pass-through (auto-off or not patched)
bool g_detectPending = false, g_waitReady = false;
DWORD g_clockFn = kClock;                   // ClockStub jumps here (the game's clock)
// LogLevel 2: a line every 10 s
LONGLONG g_statStart = 0, g_statWait = 0;
LONG g_statFrames = 0, g_statLate = 0;

LONGLONG Qpc() {
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    return t.QuadPart;
}

// case-insensitive search of an ASCII text in the readable pages of a loaded module's image
bool ModuleHas(HMODULE m, const char *text) {
    if (!m) return false;
    const BYTE *base = reinterpret_cast<const BYTE *>(m);
    DWORD size = 0;
    __try {
        const IMAGE_DOS_HEADER *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
        const IMAGE_NT_HEADERS *nt = reinterpret_cast<const IMAGE_NT_HEADERS *>(base + dos->e_lfanew);
        size = nt->OptionalHeader.SizeOfImage;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    const size_t len = strlen(text);
    char first = static_cast<char>(tolower(static_cast<unsigned char>(text[0])));
    for (DWORD off = 0; off < size;) {
        MEMORY_BASIC_INFORMATION mi;
        if (!VirtualQuery(base + off, &mi, sizeof(mi))) break;
        const BYTE *start = reinterpret_cast<const BYTE *>(mi.BaseAddress);
        const BYTE *stop = start + mi.RegionSize;
        if (stop > base + size) stop = base + size;
        const DWORD prot = mi.Protect & 0xff;
        const bool readable = mi.State == MEM_COMMIT && !(mi.Protect & PAGE_GUARD) && prot != PAGE_NOACCESS &&
                              prot != PAGE_EXECUTE;
        if (readable && stop - start >= static_cast<ptrdiff_t>(len)) {
            __try {
                for (const BYTE *p = start; p + len <= stop; ++p) {
                    if (static_cast<char>(tolower(*p)) != first) continue;
                    size_t k = 1;
                    while (k < len && tolower(p[k]) == tolower(static_cast<unsigned char>(text[k]))) ++k;
                    if (k == len) return true;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        off = static_cast<DWORD>(stop - base);
        if (stop <= start) break;
    }
    return false;
}

// the value of `key = value` anywhere in a text file (any section; ';' and '#' start a comment); false = not found
bool FileKey(const char *path, const char *key, char *value, size_t n) {
    FILE *f = nullptr;
    if (fopen_s(&f, path, "r") != 0 || !f) return false;
    char line[512];
    bool found = false;
    const size_t klen = strlen(key);
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') ++p;
        if (_strnicmp(p, key, klen) != 0) continue;
        char *q = p + klen;
        while (*q == ' ' || *q == '\t') ++q;
        if (*q != '=') continue;
        ++q;
        while (*q == ' ' || *q == '\t' || *q == '"') ++q;
        size_t k = 0;
        while (q[k] && q[k] != ';' && q[k] != '#' && q[k] != '"' && q[k] != '\r' && q[k] != '\n' && k + 1 < n) {
            value[k] = q[k];
            ++k;
        }
        while (k > 0 && (value[k - 1] == ' ' || value[k - 1] == '\t')) --k;
        value[k] = 0;
        found = true;                        // the last occurrence wins (as in both readers)
    }
    fclose(f);
    return found;
}

void ModuleDir(HMODULE m, char *out, size_t n) {
    DWORD len = GetModuleFileNameA(m, out, static_cast<DWORD>(n));
    while (len > 0 && out[len - 1] != '\\' && out[len - 1] != '/') --len;
    out[len] = 0;
}

// decides once, as soon as d3d9.dll is loaded, whether a known limiter already caps the game (main thread)
void DetectLimiter() {
    HMODULE d3d9 = GetModuleHandleA("d3d9.dll");
    if (!d3d9) return;                       // the game loads d3d9.dll itself (no static import); ask again next frame
    g_detectPending = false;
    char path[MAX_PATH] = "?";
    GetModuleFileNameA(d3d9, path, MAX_PATH);
    HMODULE dxgi = GetModuleHandleA("dxgi.dll");
    HMODULE dxw = GetModuleHandleA("dxwrapper.dll");
    // markers: DXVK's config reader names DXVK_CONFIG_FILE / dxvk.conf in every DXVK dll; dxwrapper names itself
    const bool dxvk = ModuleHas(d3d9, "DXVK_CONFIG_FILE") || ModuleHas(d3d9, "dxvk.conf") ||
                      (dxgi && (ModuleHas(dxgi, "DXVK_CONFIG_FILE") || ModuleHas(dxgi, "dxvk.conf")));
    const bool dxwrapper = dxw || ModuleHas(d3d9, "dxwrapper");
    if (dxvk) {
        // DXVK reads DXVK_FRAME_RATE, then d3d9.maxFrameRate of the conf file (DXVK_CONFIG_FILE or dxvk.conf in the
        // game folder), else its built-in tru.exe profile: d3d9.maxFrameRate = -60
        char value[64] = "", conf[MAX_PATH] = "", source[MAX_PATH + 40] = "";
        if (GetEnvironmentVariableA("DXVK_FRAME_RATE", value, sizeof(value)) > 0) {
            strcpy_s(source, sizeof(source), "environment DXVK_FRAME_RATE");
        } else {
            value[0] = 0;
            if (!GetEnvironmentVariableA("DXVK_CONFIG_FILE", conf, sizeof(conf)))
                _snprintf_s(conf, sizeof(conf), _TRUNCATE, "%sdxvk.conf", g_dir);
            if (FileKey(conf, "d3d9.maxFrameRate", value, sizeof(value))) {
                _snprintf_s(source, sizeof(source), _TRUNCATE, "d3d9.maxFrameRate in %s", conf);
            } else {
                strcpy_s(value, sizeof(value), "-60");
                strcpy_s(source, sizeof(source), "DXVK's tru.exe profile (no d3d9.maxFrameRate in dxvk.conf)");
            }
        }
        const long v = strtol(value, nullptr, 10);
        if (v != 0) {
            InterlockedExchange(&g_limitLive, 0);
            Log(1, "FrameLimit: auto-off - d3d9.dll is DXVK (%s) and DXVK limits the frame rate itself (%s = %s); "
                   "AutoOff=0 keeps TruQoL's limiter as well", path, source, value);
            return;
        }
        Log(1, "FrameLimit: d3d9.dll is DXVK (%s) with its limiter off (%s = %s) - TruQoL's limiter stays on (%d fps)",
            path, source, value, g_maxFps);
        return;
    }
    if (dxwrapper) {
        char dir[MAX_PATH], ini[MAX_PATH], value[64] = "";
        ModuleDir(dxw ? dxw : d3d9, dir, sizeof(dir));
        _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sdxwrapper.ini", dir);
        bool found = FileKey(ini, "LimitPerFrameFPS", value, sizeof(value));
        if (!found) {
            _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sdxwrapper.ini", g_dir);
            found = FileKey(ini, "LimitPerFrameFPS", value, sizeof(value));
        }
        const long v = found ? strtol(value, nullptr, 10) : 0;
        if (v > 0) {
            InterlockedExchange(&g_limitLive, 0);
            Log(1, "FrameLimit: auto-off - dxwrapper is loaded (%s) and limits the frame rate (LimitPerFrameFPS = %ld in "
                   "%s); AutoOff=0 keeps TruQoL's limiter as well", dxw ? "dxwrapper.dll" : path, v, ini);
            return;
        }
        Log(1, "FrameLimit: dxwrapper is loaded (%s) without LimitPerFrameFPS > 0 (%s) - TruQoL's limiter stays on (%d "
               "fps)", dxw ? "dxwrapper.dll" : path, found ? value : "key not found", g_maxFps);
        return;
    }
    char sys[MAX_PATH] = "";
    GetSystemDirectoryA(sys, MAX_PATH);
    const bool system = _strnicmp(path, sys, strlen(sys)) == 0;
    char wow[MAX_PATH] = "";
    const bool wow64 = GetSystemWow64DirectoryA(wow, MAX_PATH) > 0 && _strnicmp(path, wow, strlen(wow)) == 0;
    Log(1, "FrameLimit: d3d9.dll = %s (%s, no known limiter) - TruQoL's limiter stays on (%d fps)", path,
        system || wow64 ? "the system's" : "a wrapper, e.g. TRAWindowed", g_maxFps);
}

void PrepareWait() {
    g_waitReady = true;
    g_timer = CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
    g_hiRes = g_timer != nullptr;
    if (!g_timer) {
        g_timer = CreateWaitableTimerExW(nullptr, nullptr, 0, TIMER_ALL_ACCESS);
        HMODULE winmm = GetModuleHandleA("winmm.dll");   // tru.exe imports WINMM.dll
        typedef UINT(WINAPI * PeriodFn)(UINT);
        PeriodFn begin = winmm ? reinterpret_cast<PeriodFn>(GetProcAddress(winmm, "timeBeginPeriod")) : nullptr;
        if (begin) begin(1);
    }
    const int spinUs = g_spinUs > 0 ? g_spinUs : (g_hiRes ? 600 : 2000);
    g_spinTicks = g_qpf * spinUs / 1000000;
    Log(1, "FrameLimit: waiting with %s, last %d us as a short pause loop", g_hiRes ? "a high-resolution waitable timer"
                                                                                     : g_timer ? "timeBeginPeriod(1) + a waitable timer"
                                                                                               : "Sleep(1)",
        spinUs);
}

void SleepUntil(LONGLONG target) {
    for (;;) {
        const LONGLONG left = target - Qpc();
        if (left <= g_spinTicks) break;
        const LONGLONG ticks = left - g_spinTicks;
        LONGLONG hundredNs = ticks * 10000000 / g_qpf;
        if (hundredNs <= 0) break;
        if (hundredNs > 1000000) hundredNs = 1000000;        // never more than 100 ms in one wait
        if (g_timer) {
            LARGE_INTEGER due;
            due.QuadPart = -hundredNs;
            if (SetWaitableTimer(g_timer, &due, 0, nullptr, nullptr, FALSE))
                WaitForSingleObject(g_timer, 200);
            else
                Sleep(1);
        } else {
            Sleep(1);
        }
    }
    while (Qpc() < target) YieldProcessor();
}

extern "C" void __cdecl LimiterWait() {
    if (!g_limitLive) return;
    if (g_detectPending) {
        DetectLimiter();
        if (!g_limitLive) return;
    }
    if (!g_waitReady) PrepareWait();
    LONGLONG now = Qpc();
    LONGLONG target = g_next;
    if (target && target - now > 2 * g_period) target = now + g_period;   // clock oddity: never wait > 2 frames
    LONGLONG waited = 0;
    if (target && now < target) {
        SleepUntil(target);
        const LONGLONG after = Qpc();
        waited = after - now;
        now = after;
    }
    const bool late = !target || now - target > g_period;
    g_next = late ? now + g_period : target + g_period;   // late by more than a frame: new cadence, no catch-up burst
    if (g_logLevel >= 2) {
        if (!g_statStart) g_statStart = now;
        ++g_statFrames;
        g_statWait += waited;
        if (late && target) ++g_statLate;
        if (now - g_statStart >= 10 * g_qpf) {
            const double secs = static_cast<double>(now - g_statStart) / static_cast<double>(g_qpf);
            Log(2, "FrameLimit: %ld frames in %.1f s = %.1f fps, waited %.2f ms per frame, %ld late frame(s)", g_statFrames,
                secs, g_statFrames / secs, 1000.0 * static_cast<double>(g_statWait) / static_cast<double>(g_qpf) /
                                               (g_statFrames ? g_statFrames : 1), g_statLate);
            g_statStart = now;
            g_statFrames = g_statLate = 0;
            g_statWait = 0;
        }
    }
}

// in place of `call 0x597f10` at 0x5da247 / 0x5da684: wait, then the game's clock (its edx:eax is the result)
__declspec(naked) void ClockStub() {
    __asm {
        call LimiterWait
        jmp dword ptr [g_clockFn]
    }
}

void StartFrameLimit() {
    if (!g_limitEnabled) { Log(1, "FrameLimit: off ([FrameLimit] Enabled=0) - the game's own frame rate"); return; }
    if (!HexBytesAt(kFrameTimer, kFrameTimerHex) || !HexBytesAt(kClockCallPause, kClockCallPauseHex) ||
        !HexBytesAt(kClock, kClockHex) || !HexBytesAt(kFrameStore, kFrameStoreHex)) {
        Log(0, "FrameLimit: off - the frame-time function 0x%08lx / clock 0x%08lx do not match this tru.exe",
            kFrameTimer, kClock);
        return;
    }
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    g_qpf = f.QuadPart;
    g_period = g_qpf / g_maxFps;
    const DWORD sites[2] = {kClockCallRun, kClockCallPause};
    if (!RedirectCalls(sites, 2, kClock, reinterpret_cast<DWORD>(&ClockStub), "FrameLimit")) return;
    g_detectPending = g_autoOff != 0;
    InterlockedExchange(&g_limitLive, 1);
    Log(1, "FrameLimit: on, %d fps - the clock calls 0x%08lx / 0x%08lx of the frame-time function 0x%08lx wait for the "
           "next frame slot (the game measures the limited frame: dt 0xe7f190 = %.3f x 1/30 s); %s", g_maxFps,
        kClockCallRun, kClockCallPause, kFrameTimer, 30.0 / g_maxFps,
        g_autoOff ? "auto-off check (DXVK / dxwrapper) when d3d9.dll is loaded"
                  : "AutoOff=0: no check for other limiters");
}

// ---------------------------------------------------------------------------------------------------------------
// 2. camera
typedef float(__cdecl *FovGetterFn)();
FovGetterFn g_fovGetter = reinterpret_cast<FovGetterFn>(kFovGetter);
const float kFovMin = 0.05f, kFovMax = 2.8f;        // radians (about 3 .. 160 degrees vertical)
volatile LONG g_fovFrames = 0;

// in place of `call 0x5e78d0` at 0x5cb0a8 (cdecl, result st0)
float __cdecl FovHook() {
    float f = g_fovGetter();
    if (!g_fovCutscenes) {
        const DWORD cur = *reinterpret_cast<const volatile DWORD *>(kCamCurrent);
        const DWORD game = *reinterpret_cast<const volatile DWORD *>(kCamGameplay);
        if (!cur || cur != game) return f;
    }
    if (!(f > 0.0f)) return f;
    float g = f * g_fov;
    if (g < kFovMin) g = kFovMin;
    if (g > kFovMax) g = kFovMax;
    if (InterlockedIncrement(&g_fovFrames) == 1)
        Log(1, "Camera Fov: first scaled frame - the game's %.4f rad (%.1f deg vertical) -> %.4f rad (%.1f deg)", f,
            f * 57.29578f, g, g * 57.29578f);
    return g;
}

DWORD g_shakeFnPtr = kShakeFn;               // ShakeStub calls the game's strength through this

// in place of `call 0x5eb460` at 0x5eea55 / 0x5eb56d (esi = slot, untouched; st0 = strength x factor)
__declspec(naked) void ShakeStub() {
    __asm {
        call dword ptr [g_shakeFnPtr]
        fmul dword ptr [g_shakeScale]
        ret
    }
}

void StartCamera() {
    if (g_fov == 0.0f || g_fov == 1.0f) {
        Log(1, "Camera Fov: off (Fov=%g = the game's field of view)", g_fov);
    } else if (!HexBytesAt(kFovCall, kFovCallHex) || !HexBytesAt(kFovGetter, kFovGetterHex) ||
               !HexBytesAt(kFovReader, kFovReaderHex) || !HexBytesAt(kPerspective, kPerspectiveHex)) {
        Log(0, "Camera Fov: off - the projection code 0x%08lx / 0x%08lx / 0x%08lx does not match this tru.exe", kFovCall,
            kFovReader, kPerspective);
    } else {
        const DWORD site = kFovCall;
        if (RedirectCalls(&site, 1, kFovGetter, reinterpret_cast<DWORD>(&FovHook), "Camera Fov"))
            Log(1, "Camera Fov: on, factor %.3f on the game's vertical FOV (radians; %s) - render projection call "
                   "0x%08lx -> TruQoL (getter 0x%08lx, scene FOV 0xe49700, perspective 0x%08lx)", g_fov,
                g_fovCutscenes ? "every camera incl. cutscenes" : "gameplay camera only, cutscenes unchanged", kFovCall,
                kFovGetter, kPerspective);
    }
    if (g_shakeScale == 1.0f) {
        Log(1, "Camera ShakeScale: off (1.0 = the game's own camera shakes; TruMenu cam.shakescale keeps the sites)");
        return;
    }
    if (!HexBytesAt(kShakeFn, kShakeFnHex) || !HexBytesAt(kShakeCall1, kShakeCall1Hex) ||
        !HexBytesAt(kShakeCall2, kShakeCall2Hex)) {
        Log(0, "Camera ShakeScale: off - the shake code 0x%08lx / 0x%08lx / 0x%08lx does not match this tru.exe "
               "(or another plugin patched it)", kShakeFn, kShakeCall1, kShakeCall2);
        return;
    }
    const DWORD sites[2] = {kShakeCall1, kShakeCall2};
    if (RedirectCalls(sites, 2, kShakeFn, reinterpret_cast<DWORD>(&ShakeStub), "Camera ShakeScale"))
        Log(1, "Camera ShakeScale: on, factor %.2f%s - the callers 0x%08lx / 0x%08lx of the shake strength 0x%08lx -> "
               "TruQoL (TruMenu's cam.shakescale is refused while this is on)", g_shakeScale,
            g_shakeScale == 0.0f ? " (no camera shakes)" : "", kShakeCall1, kShakeCall2, kShakeFn);
}

// ---------------------------------------------------------------------------------------------------------------
// 3. start-up: thread cap
typedef BOOL(WINAPI *AffinityFn)(HANDLE, PDWORD_PTR, PDWORD_PTR);
volatile LONG g_affinityCalls = 0;

int Bits(DWORD_PTR v) {
    int n = 0;
    for (; v; v &= v - 1) ++n;
    return n;
}

// in place of `call [0x83e0a8]` at 0x4a2238 (stdcall, the same three arguments)
BOOL WINAPI CappedAffinity(HANDLE process, PDWORD_PTR processMask, PDWORD_PTR systemMask) {
    DWORD slot = 0;
    AffinityFn real = ReadDword(kAffinityIat, &slot) && slot ? reinterpret_cast<AffinityFn>(slot)
                                                              : &GetProcessAffinityMask;
    const BOOL ok = real(process, processMask, systemMask);
    const LONG n = InterlockedIncrement(&g_affinityCalls);
    if (!ok || !processMask || !systemMask) {
        Log(0, "Startup ThreadCap: GetProcessAffinityMask failed (%lu) - the game's own answer passed on", GetLastError());
        return ok;
    }
    const DWORD_PTR cap = (static_cast<DWORD_PTR>(1) << g_threadCap) - 1;
    const DWORD_PTR proc = *processMask, sys = *systemMask;
    if (!(sys & ~cap)) {
        Log(1, "Startup ThreadCap: CPU count %ld - system mask 0x%08lx (%d logical CPUs) is within %d - unchanged", n,
            static_cast<DWORD>(sys), Bits(sys), g_threadCap);
        return ok;
    }
    *processMask = proc & cap;
    *systemMask = sys & cap;
    Log(1, "Startup ThreadCap: CPU count %ld - process / system mask 0x%08lx / 0x%08lx (%d logical CPUs) -> 0x%08lx / "
           "0x%08lx (%d): the count loop 0x4a2270 now ends at bit %d instead of running past its stack array%s",
        n, static_cast<DWORD>(proc), static_cast<DWORD>(sys), Bits(sys), static_cast<DWORD>(*processMask),
        static_cast<DWORD>(*systemMask), Bits(*systemMask), g_threadCap,
        *processMask != *systemMask ? " (masks differ, e.g. a start /affinity: the game returns 8 at once, as before)"
                                    : "");
    return ok;
}

void StartThreadCap() {
    if (!g_threadCap) {
        Log(1, "Startup ThreadCap: off (ThreadCap=0) - the game's own CPU count (crashes with more than 31 threads; "
               "work-around: start /affinity FFFF)");
        return;
    }
    if (!HexBytesAt(kAffinityCall, kAffinityCallHex) || !HexBytesAt(kAffinityArgs, kAffinityArgsHex) ||
        !HexBytesAt(kCpuLoopStep, kCpuLoopStepHex) || !HexBytesAt(kCpuOverflow, kCpuOverflowHex) ||
        !HexBytesAt(kCpuCountCall, kCpuCountCallHex)) {
        Log(0, "Startup ThreadCap: off - the CPU count 0x%08lx / 0x%08lx does not match this tru.exe (or it already "
               "ran / another plugin patched it)", kAffinityCall, kCpuLoopStep);
        return;
    }
    BYTE call[6] = {0xe8, 0, 0, 0, 0, 0x90};
    const DWORD rel = reinterpret_cast<DWORD>(&CappedAffinity) - (kAffinityCall + 5);
    memcpy(call + 1, &rel, 4);
    if (!WriteCode(kAffinityCall, call, sizeof(call))) return;
    Log(1, "Startup ThreadCap: on, %d - GetProcessAffinityMask call 0x%08lx of the CPU count 0x4a21d0 -> TruQoL (masks "
           "capped only when the PC reports more logical CPUs; the count runs once, in WinMain, after this)",
        g_threadCap, kAffinityCall);
}

// ---------------------------------------------------------------------------------------------------------------
void ReadOptions() {
    g_enabled = IniInt("TruQoL", "Enabled", 1, 0, 1);
    g_logLevel = IniInt("TruQoL", "LogLevel", 1, 0, 2);
    g_limitEnabled = IniInt("FrameLimit", "Enabled", 1, 0, 1);
    g_maxFps = IniInt("FrameLimit", "MaxFps", 60, 20, 500);
    g_autoOff = IniInt("FrameLimit", "AutoOff", 1, 0, 1);
    g_spinUs = IniInt("FrameLimit", "SpinUs", 0, 0, 5000);
    g_fov = IniFloat("Camera", "Fov", 0.0f, 0.0f, 2.0f);
    if (g_fov != 0.0f && g_fov < 0.5f) {
        Log(0, "[Camera] Fov=%g is below 0.5 - 0 (game) used", g_fov);
        g_fov = 0.0f;
    }
    g_fovCutscenes = IniInt("Camera", "FovCutscenes", 0, 0, 1);
    g_shakeScale = IniFloat("Camera", "ShakeScale", 1.0f, 0.0f, 1.0f);
    g_threadCap = IniInt("Startup", "ThreadCap", 31, 0, 31);
}

void Start(HMODULE self) {
    ModuleDir(self, g_dir, sizeof(g_dir));
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruQoL.log", g_dir);
    ReadOptions();
    Log(1, "%s loaded (enabled %d, log level %d; FrameLimit %d / %d fps / AutoOff %d, Fov %g / cutscenes %d, ShakeScale "
           "%g, ThreadCap %d)", kVersion, g_enabled, g_logLevel, g_limitEnabled, g_maxFps, g_autoOff, g_fov,
        g_fovCutscenes, g_shakeScale, g_threadCap);
    if (!g_enabled) { Log(1, "disabled by TruQoL.ini ([TruQoL] Enabled=0) - nothing patched"); return; }
    const DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - nothing patched", base, kImageBase); return; }
    StartThreadCap();                        // first: the CPU count runs in WinMain, soon after the plugins are loaded
    StartFrameLimit();
    StartCamera();
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    }
    return TRUE;
}

extern "C" __declspec(dllexport) const char *TruQoLVersion() {
    return "TruQoL 0.1 (player options: frame limiter at the game's frame clock 0x5da230, FOV factor at the render "
           "projection 0x5cb0a8, camera shake factor 0x5eb460, CPU thread cap for the start-up count 0x4a21d0)";
}
