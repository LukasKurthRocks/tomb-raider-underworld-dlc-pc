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
//
// 0.1.1 (2026-11-08, TruMenu page Fixes): the live keys are read again while the game runs - LiveTick, at most once a
// second and only when the last-write time of TruQoL.ini changed (cheap file-time check first, as TruMercLang PollIni),
// on the game thread: from ClockStub, i.e. the frame-time function 0x5da230 that every main-state handler calls once
// per frame (like TruShadowCombat's switches, read from the code they switch). A read passes the current value as its
// default (a missing key keeps it, an invalid one is logged and keeps it). One log line per change.
//   live:    [TruQoL] LogLevel; [FrameLimit] Enabled, MaxFps, AutoOff, SpinUs; [Camera] Fov, FovCutscenes, ShakeScale
//   restart: [TruQoL] Enabled (0 = nothing patched, so nothing to switch), [Startup] ThreadCap (acts once, before WinMain)
// Hooks: the two clock calls and the FOV call are patched ONCE at the start whenever TruQoL is enabled and their bytes
// match - also with [FrameLimit] Enabled=0 / Fov=0 (then a pass-through: ClockStub = the game's clock, FovHook = the
// game's value) - and gated at run time; the hook sites are the 0.1 ones. Reason: the FOV call 0x5cb0a8 is render code
// (no proof of its thread) and the clock calls sit in the function that runs the tick, so no code there is rewritten
// while the game runs. AutoOff is live because the limiter detection (DXVK / dxwrapper) runs once, read-only, whatever
// AutoOff says (d3d9.dll is loaded once per process) - AutoOff only decides whether that result gates the limiter.
// ShakeScale keeps the 0.1 rule live: TruQoL owns the two shake calls only while its ShakeScale is below 1.0. A change
// to < 1.0 points them to ShakeStub (only while both still call the game's 0x5eb460 - TruMenu's cam.shakescale below
// 100 % holds them: refused with one line, tried again at the next change of the key), a change to 1.0 puts the game's
// target back (only while both still call ShakeStub) so TruMenu's slider may take them again. These two rel32 writes
// run on the game thread, as TruMenu's own run-time patch of the same sites (M21PatchGroup from PadHook) and
// TruShadowCombat's [Damage] Translate switch do. Without the clock hook (bytes differ) there is no tick: every key
// then takes effect at the next start (logged once).
//
// 0.1.2 (2026-11-08, package 18c) [Startup] SkipIntro (restart, default 0) - skips the start-up intro movie. Static
// proof (work\skip18c_0811): the front-end script plays it with the uigamedata native f21 0x7a0cf0 (binder 0x7af0c0
// idx 0x15) -> PlayMovie 0x77bc60 (its only caller; 0x6457a0 = an empty log stub, 0x5f6420 = mov eax, 1) -> the video
// player 0x4a12b0(name, loop 0). The player is BLOCKING: it opens the Bink file (0x4a0c70; cannot open -> returns 0 at
// 0x4a12df) and runs its own frame loop until the last frame (0x4a0ae0: handle +0xc == +0x8), the stop byte 0xa039b8
// (native f22 0x4a0f10), a skip press or a lost device, then BinkClose and handle 0xa039bc = 0. The handle and the
// "finished" test are used only inside the video code 0x4a0a00..0x4a15ff, the native writes no result and PlayMovie
// drops eax: the script learns the end only by the native RETURNING - there is no "movie finished" event to fake.
// MovieHook replaces the rel32 of `call 0x4a12b0` at 0x77bc7b (patched once in DllMain) and, while the front-end state
// 0xfae8da is 0 (LegalScreens) or 1 (IntroMovie), the main state 0xe7ed60 is not 1 / 2 / 9 (level, level load, outfit
// selection) and state 2 or higher was never seen in this run, returns as the game's own "file cannot be opened" path
// (the player's entry writes 0xa039b8 = 0, 0xa039dc = loop, 0xa039dd = 0, result 0). The game's code-played movies
// (attract "intro" 0x5d5520, menu loop "medsea_loop" 0x5daf3e, state-8 "explode" 0x5db008, the queue 0xe7ece0) call
// 0x4a12b0 directly and are never touched; the state-1 handler 0x5dae86 sets state 2 by itself. The legal screens are
// no movie (no logo .bik in Movies\; state 0 is not in the code switch 0x5dae7f, i.e. script-drawn): not skipped.

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

const char kVersion[] = "TruQoL 0.1.2";
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

// ---- 4. start-up intro: the script native PlayMovie and the blocking video player (0.1.2) ----
const DWORD kPlayMovie = 0x0077bc60;        // PlayMovie(&name): log stub, 0x5f6420, call 0x4a12b0(name, 0), log stub
const char *const kPlayMovieHex = "56 8b742408 8b06 85c0 741e 50 e82f9becff e8aaa7e7ff 8b06 6a00 50 e83056d2ff 83c40c 5e e9179becff 5e c3";
const DWORD kPlayMovieCall = 0x0077bc7b;    // call 0x4a12b0 - the patched rel32
const DWORD kVideoPlay = 0x004a12b0;        // entry writes, open 0x4a0c70, open failed -> return 0 (0x4a12df)
const char *const kVideoPlayHex = "8b4c2404 8a442408 83ec20 53 55 33db 51 881db839a000 a2dc39a000 881ddd39a000 33ed e898f9ffff 83c404 85c0 7506 5d 5b 83c420 c3";
const DWORD kMovieNative = 0x007a0cf0;      // uigamedata f21: push the argument pointer, call 0x77bc60, no result
const char *const kMovieNativeHex = "8b44240c 50 e866affdff 59 c3";
const DWORD kMovieBind = 0x007af1f3;        // binder 0x7af0c0: push 0x7a0cf0; push 0x15
const char *const kMovieBindHex = "68f00c7a00 6a15";
const DWORD kFrontEndGet = 0x0077bbe0;      // mov al, [0xfae8da]
const char *const kFrontEndGetHex = "a0dae8fa00 c3";
const DWORD kIntroCase = 0x005dae86;        // front-end state 1 in 0x5dae20: log stub, SetFrontEndState(2)
const char *const kIntroCaseHex = "51 e814a90600 6a02 e82d0d1a00";
const DWORD kFrontEndState = 0x00fae8da;    // byte: 0 LegalScreens, 1 IntroMovie, 2 PressStart, 3 MainMenu, ...
const DWORD kMainState = 0x00e7ed60;        // dword: 1 level, 2 level load, 9 outfit selection, 10 front end
const DWORD kMovieStop = 0x00a039b8;        // the player's stop byte (native f22 0x4a0f10 sets 1)
const DWORD kMovieLoop = 0x00a039dc;        // the player's loop byte
const DWORD kMoviePause = 0x00a039dd;       // the player's pause byte

// ---- options (TruQoL.ini) ----
int g_enabled = 1, g_logLevel = 1;
int g_limitEnabled = 1, g_maxFps = 60, g_autoOff = 1, g_spinUs = 0;
float g_fov = 0.0f;                         // factor; 0 (or 1) = game
int g_fovCutscenes = 0;
float g_shakeScale = 1.0f;                  // read by ShakeStub
int g_threadCap = 31;
int g_skipIntro = 0;                        // 0.1.2: [Startup] SkipIntro (restart)

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
        Log(0, "[%s] %s=%s is not a whole number in %d .. %d - %d used", section, key, v, lo, hi, def);
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
        Log(0, "[%s] %s=%s is not a number in %.2f .. %.2f - %.2f used", section, key, v, lo, hi, def);
        return def;
    }
    return static_cast<float>(x);
}

// ---------------------------------------------------------------------------------------------------------------
// 1. frame limiter
LONGLONG g_qpf = 0, g_period = 0, g_next = 0, g_spinTicks = 0;
HANDLE g_timer = nullptr;
bool g_hiRes = false;
// 0.1.1: the clock calls are patched once (g_limitHooked); whether a frame waits is decided per frame (LimitActive)
bool g_limitHooked = false;
bool g_otherLimiter = false;                // DetectLimiter: DXVK / dxwrapper limits the frame rate itself
char g_otherWhat[24] = "";                  // "DXVK" / "dxwrapper" (for the log lines)
bool g_detectPending = false, g_waitReady = false;
void LiveTick();                            // 0.1.1, below
// 0.1.2 SkipIntro (section 4 below): LimiterWait also runs its start-up latch once per frame
bool g_movieHooked = false;                  // the call 0x77bc7b goes to MovieHook (patched once in DllMain)
volatile LONG g_bootOver = 0;                // front-end state 2 or higher seen: no skip any more in this run
volatile LONG g_moviesSkipped = 0;
void BootCheck(BYTE frontEnd);
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

// game thread, every frame: the limiter waits only while [FrameLimit] Enabled=1 and no other limiter takes over
bool LimitActive() { return g_limitHooked && g_limitEnabled && !(g_autoOff && g_otherLimiter); }

// the effect of a detected limiter now (for the detection line and the live lines)
const char *OtherNote() {
    if (!g_otherLimiter) return "";
    return g_autoOff ? " - auto-off (AutoOff=1): TruQoL's limiter does not wait"
                     : " - AutoOff=0: TruQoL's limiter waits as well (the lower rate wins)";
}

// decides once, as soon as d3d9.dll is loaded, whether a known limiter already caps the game (game thread). 0.1.1: runs
// whatever AutoOff says (read only) and stores the result; AutoOff (live) decides at every frame whether it gates.
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
            g_otherLimiter = true;
            strcpy_s(g_otherWhat, sizeof(g_otherWhat), "DXVK");
            Log(1, "FrameLimit: d3d9.dll is DXVK (%s) and DXVK limits the frame rate itself (%s = %s)%s", path, source,
                value, OtherNote());
            return;
        }
        Log(1, "FrameLimit: d3d9.dll is DXVK (%s) with its limiter off (%s = %s) - TruQoL's limiter is the only one "
               "(%s, %d fps)", path, source, value, g_limitEnabled ? "on" : "Enabled=0", g_maxFps);
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
            g_otherLimiter = true;
            strcpy_s(g_otherWhat, sizeof(g_otherWhat), "dxwrapper");
            Log(1, "FrameLimit: dxwrapper is loaded (%s) and limits the frame rate (LimitPerFrameFPS = %ld in %s)%s",
                dxw ? "dxwrapper.dll" : path, v, ini, OtherNote());
            return;
        }
        Log(1, "FrameLimit: dxwrapper is loaded (%s) without LimitPerFrameFPS > 0 (%s) - TruQoL's limiter is the only "
               "one (%s, %d fps)", dxw ? "dxwrapper.dll" : path, found ? value : "key not found",
            g_limitEnabled ? "on" : "Enabled=0", g_maxFps);
        return;
    }
    char sys[MAX_PATH] = "";
    GetSystemDirectoryA(sys, MAX_PATH);
    const bool system = _strnicmp(path, sys, strlen(sys)) == 0;
    char wow[MAX_PATH] = "";
    const bool wow64 = GetSystemWow64DirectoryA(wow, MAX_PATH) > 0 && _strnicmp(path, wow, strlen(wow)) == 0;
    Log(1, "FrameLimit: d3d9.dll = %s (%s, no known limiter) - TruQoL's limiter is the only one (%s, %d fps)", path,
        system || wow64 ? "the system's" : "a wrapper, e.g. TRAWindowed", g_limitEnabled ? "on" : "Enabled=0", g_maxFps);
}

// the pause-loop share of a wait (SpinUs; 0 = automatic) - at the first wait and on a live change
int SpinUsNow() { return g_spinUs > 0 ? g_spinUs : (g_hiRes ? 600 : 2000); }

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
    const int spinUs = SpinUsNow();
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

// game thread, once per frame (ClockStub): 0.1.1 the live tick, the one-time detection, then the wait - only while the
// limiter is active; while it is not, the next active frame starts a new cadence (no wait for a slot of long ago)
extern "C" void __cdecl LimiterWait() {
    LiveTick();
    if (g_movieHooked && !g_bootOver) BootCheck(*reinterpret_cast<const volatile BYTE *>(kFrontEndState));
    if (g_detectPending) DetectLimiter();
    if (!LimitActive()) {
        g_next = 0;
        return;
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

// 0.1.1: the clock calls are patched whenever TruQoL is enabled and the bytes match - also with [FrameLimit] Enabled=0
// (then ClockStub is a pass-through until Enabled=1 is read live); they also carry the live tick
void StartFrameLimit() {
    if (!HexBytesAt(kFrameTimer, kFrameTimerHex) || !HexBytesAt(kClockCallPause, kClockCallPauseHex) ||
        !HexBytesAt(kClock, kClockHex) || !HexBytesAt(kFrameStore, kFrameStoreHex)) {
        Log(0, "FrameLimit: off - the frame-time function 0x%08lx / clock 0x%08lx do not match this tru.exe; no live "
               "tick either: every TruQoL.ini change takes effect at the next start", kFrameTimer, kClock);
        return;
    }
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    g_qpf = f.QuadPart;
    g_period = g_qpf / g_maxFps;
    const DWORD sites[2] = {kClockCallRun, kClockCallPause};
    if (!RedirectCalls(sites, 2, kClock, reinterpret_cast<DWORD>(&ClockStub), "FrameLimit")) {
        Log(0, "FrameLimit: no live tick - every TruQoL.ini change takes effect at the next start");
        return;
    }
    g_limitHooked = true;
    g_detectPending = true;                  // read only, whatever AutoOff says (AutoOff is live)
    if (!g_limitEnabled)
        Log(1, "FrameLimit: off ([FrameLimit] Enabled=0) - the game's own frame rate; the clock calls 0x%08lx / 0x%08lx "
               "of 0x%08lx go through TruQoL as a pass-through (Enabled=1 in TruQoL.ini takes effect within a second)",
            kClockCallRun, kClockCallPause, kFrameTimer);
    else
        Log(1, "FrameLimit: on, %d fps - the clock calls 0x%08lx / 0x%08lx of the frame-time function 0x%08lx wait for "
               "the next frame slot (the game measures the limited frame: dt 0xe7f190 = %.3f x 1/30 s); check for other "
               "limiters (DXVK / dxwrapper) when d3d9.dll is loaded, AutoOff=%d", g_maxFps, kClockCallRun,
            kClockCallPause, kFrameTimer, 30.0 / g_maxFps, g_autoOff);
}

// ---------------------------------------------------------------------------------------------------------------
// 2. camera
typedef float(__cdecl *FovGetterFn)();
FovGetterFn g_fovGetter = reinterpret_cast<FovGetterFn>(kFovGetter);
const float kFovMin = 0.05f, kFovMax = 2.8f;        // radians (about 3 .. 160 degrees vertical)
volatile LONG g_fovFrames = 0;

// in place of `call 0x5e78d0` at 0x5cb0a8 (cdecl, result st0)
bool g_fovHooked = false;                    // 0.1.1: the call 0x5cb0a8 goes to FovHook (patched once at the start)

float __cdecl FovHook() {
    float f = g_fovGetter();
    const float factor = g_fov;              // 0.1.1: live; 0 / 1 = the game's value (pass-through)
    if (factor == 0.0f || factor == 1.0f) return f;
    if (!g_fovCutscenes) {
        const DWORD cur = *reinterpret_cast<const volatile DWORD *>(kCamCurrent);
        const DWORD game = *reinterpret_cast<const volatile DWORD *>(kCamGameplay);
        if (!cur || cur != game) return f;
    }
    if (!(f > 0.0f)) return f;
    float g = f * factor;
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

// 0.1.1 ShakeScale ownership (the 0.1 rule, kept live): TruQoL's ShakeStub sits in the two shake calls only while
// ShakeScale < 1.0. g_shakeOk = the shake code matched at the start; g_shakeOn = both calls go to ShakeStub;
// g_shakeRefused = the last attempt met a foreign target (not tried again until the key changes - no line per second).
bool g_shakeOk = false, g_shakeOn = false, g_shakeRefused = false;
const DWORD kShakeSites[2] = {kShakeCall1, kShakeCall2};

// game thread (start: DllMain; live: LiveTick in ClockStub): both shake calls to ShakeStub (want) or back to the game's
// 0x5eb460, all or nothing, only over the expected target (the game's when patching, ours when restoring); the result in
// `note` for the caller's one log line
void ShakeApply(bool want, char *note, size_t n) {
    note[0] = 0;
    if (!g_shakeOk) { _snprintf_s(note, n, _TRUNCATE, " - the shake code did not match at the start: no effect in this run"); return; }
    if (want == g_shakeOn) return;
    const DWORD hook = reinterpret_cast<DWORD>(&ShakeStub);
    const DWORD from = want ? kShakeFn : hook, to = want ? hook : kShakeFn;
    if (want && g_shakeRefused) { _snprintf_s(note, n, _TRUNCATE, " - still refused (foreign calls), not tried again"); return; }
    for (int i = 0; i < 2; ++i) {
        const DWORD t = CallTarget(kShakeSites[i]);
        if (t == from) continue;
        if (want) {
            g_shakeRefused = true;
            _snprintf_s(note, n, _TRUNCATE, " - refused: the call at 0x%08lx goes to 0x%08lx, not the game's 0x%08lx "
                        "(TruMenu cam.shakescale below 100 %%? set it to 100); nothing patched, tried again at the next "
                        "change", kShakeSites[i], t, kShakeFn);
        } else {
            g_shakeOn = false;           // someone else holds the calls now: ShakeStub is not called any more
            _snprintf_s(note, n, _TRUNCATE, " - the call at 0x%08lx goes to 0x%08lx now (another plugin) - left as it is",
                        kShakeSites[i], t);
        }
        return;
    }
    for (int i = 0; i < 2; ++i) {
        const DWORD rel = to - (kShakeSites[i] + 5);
        if (!WriteCode(kShakeSites[i] + 1, &rel, 4)) {
            for (int j = 0; j < i; ++j) {    // put back what was already written
                const DWORD back = from - (kShakeSites[j] + 5);
                WriteCode(kShakeSites[j] + 1, &back, 4);
            }
            if (want) g_shakeRefused = true;
            _snprintf_s(note, n, _TRUNCATE, " - patch failed at 0x%08lx - nothing changed", kShakeSites[i]);
            return;
        }
    }
    g_shakeOn = want;
    _snprintf_s(note, n, _TRUNCATE, want ? " - the shake calls 0x%08lx / 0x%08lx -> TruQoL (TruMenu cam.shakescale is "
                                           "refused while ShakeScale < 1.0)"
                                         : " - the shake calls 0x%08lx / 0x%08lx back to the game's 0x5eb460 (free for "
                                           "TruMenu cam.shakescale again)",
                kShakeCall1, kShakeCall2);
}

void StartCamera() {
    // 0.1.1: the FOV call is patched whenever its code matches (Fov 0 / 1 = pass-through), so Fov / FovCutscenes are live
    if (!HexBytesAt(kFovCall, kFovCallHex) || !HexBytesAt(kFovGetter, kFovGetterHex) ||
        !HexBytesAt(kFovReader, kFovReaderHex) || !HexBytesAt(kPerspective, kPerspectiveHex)) {
        Log(0, "Camera Fov: off - the projection code 0x%08lx / 0x%08lx / 0x%08lx does not match this tru.exe", kFovCall,
            kFovReader, kPerspective);
    } else {
        const DWORD site = kFovCall;
        g_fovHooked = RedirectCalls(&site, 1, kFovGetter, reinterpret_cast<DWORD>(&FovHook), "Camera Fov");
        if (g_fovHooked && (g_fov == 0.0f || g_fov == 1.0f))
            Log(1, "Camera Fov: off (Fov=%g = the game's field of view) - render projection call 0x%08lx goes through "
                   "TruQoL as a pass-through (a factor in TruQoL.ini takes effect within a second)", g_fov, kFovCall);
        else if (g_fovHooked)
            Log(1, "Camera Fov: on, factor %.3f on the game's vertical FOV (radians; %s) - render projection call "
                   "0x%08lx -> TruQoL (getter 0x%08lx, scene FOV 0xe49700, perspective 0x%08lx)", g_fov,
                g_fovCutscenes ? "every camera incl. cutscenes" : "gameplay camera only, cutscenes unchanged", kFovCall,
                kFovGetter, kPerspective);
    }
    g_shakeOk = HexBytesAt(kShakeFn, kShakeFnHex) && HexBytesAt(kShakeCall1, kShakeCall1Hex) &&
                HexBytesAt(kShakeCall2, kShakeCall2Hex);
    if (!g_shakeOk) {
        Log(0, "Camera ShakeScale: off - the shake code 0x%08lx / 0x%08lx / 0x%08lx does not match this tru.exe "
               "(or another plugin patched it)", kShakeFn, kShakeCall1, kShakeCall2);
        return;
    }
    if (g_shakeScale == 1.0f) {
        Log(1, "Camera ShakeScale: off (1.0 = the game's own camera shakes; TruMenu cam.shakescale keeps the sites; a "
               "value below 1.0 in TruQoL.ini patches them within a second)");
        return;
    }
    char note[300];
    ShakeApply(true, note, sizeof(note));
    Log(g_shakeOn ? 1 : 0, "Camera ShakeScale: %s, factor %.2f%s%s", g_shakeOn ? "on" : "off", g_shakeScale,
        g_shakeScale == 0.0f ? " (no camera shakes)" : "", note);
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
// 4. start-up intro (0.1.2): [Startup] SkipIntro
typedef int(__cdecl *VideoPlayFn)(const char *, int);
VideoPlayFn g_videoPlay = reinterpret_cast<VideoPlayFn>(kVideoPlay);

// the movie name for the log (script data: copied under SEH, at most 63 characters)
void MovieName(const char *name, char *out, size_t n) {
    out[0] = 0;
    if (!name) { strcpy_s(out, n, "(null)"); return; }
    __try {
        size_t k = 0;
        while (k + 1 < n && name[k]) {
            const char c = name[k];
            out[k] = (c >= 0x20 && c < 0x7f) ? c : '?';
            ++k;
        }
        out[k] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        strcpy_s(out, n, "(unreadable)");
    }
}

// game thread: the latch - once the front end has reached PressStart (2) or later, the start-up is over for good
void BootCheck(BYTE frontEnd) {
    if (frontEnd >= 2 && InterlockedExchange(&g_bootOver, 1) == 0)
        Log(1, "SkipIntro: front-end state %u reached - start-up over, no more movies skipped in this run (%ld skipped)",
            frontEnd, g_moviesSkipped);
}

// in place of `call 0x4a12b0` at 0x77bc7b (PlayMovie 0x77bc60, the script native f21; cdecl, the caller drops eax)
int __cdecl MovieHook(const char *name, int loop) {
    const BYTE frontEnd = *reinterpret_cast<const volatile BYTE *>(kFrontEndState);
    const DWORD mainState = *reinterpret_cast<const volatile DWORD *>(kMainState);
    BootCheck(frontEnd);
    char movie[64];
    if (!g_skipIntro || g_bootOver || frontEnd > 1 || mainState == 1 || mainState == 2 || mainState == 9) {
        if (g_skipIntro && !g_bootOver && frontEnd <= 1) {
            MovieName(name, movie, sizeof(movie));
            Log(1, "SkipIntro: movie '%s' played - front-end state %u but main state %lu (level / load / selection)",
                movie, frontEnd, mainState);
        }
        return g_videoPlay(name, loop);
    }
    // the player's own entry writes (0x4a12c0 .. 0x4a12cb), then its "cannot open" return (0x4a12df): the native
    // returns at once, as after the last frame - the script goes on with its next line
    *reinterpret_cast<volatile BYTE *>(kMovieStop) = 0;
    *reinterpret_cast<volatile BYTE *>(kMovieLoop) = static_cast<BYTE>(loop);
    *reinterpret_cast<volatile BYTE *>(kMoviePause) = 0;
    InterlockedIncrement(&g_moviesSkipped);
    MovieName(name, movie, sizeof(movie));
    Log(1, "SkipIntro: movie '%s' skipped (front-end state %u = %s, main state %lu) - PlayMovie returns as for a file "
           "that cannot be opened", movie, frontEnd, frontEnd ? "IntroMovie" : "LegalScreens", mainState);
    return 0;
}

void StartSkipIntro() {
    if (!g_skipIntro) {
        Log(1, "Startup SkipIntro: off (SkipIntro=0) - the start-up intro movie plays (restart key)");
        return;
    }
    if (!HexBytesAt(kPlayMovie, kPlayMovieHex) || !HexBytesAt(kVideoPlay, kVideoPlayHex) ||
        !HexBytesAt(kMovieNative, kMovieNativeHex) || !HexBytesAt(kMovieBind, kMovieBindHex) ||
        !HexBytesAt(kFrontEndGet, kFrontEndGetHex) || !HexBytesAt(kIntroCase, kIntroCaseHex)) {
        Log(0, "Startup SkipIntro: off - PlayMovie 0x%08lx / video player 0x%08lx / front-end code do not match this "
               "tru.exe (or another plugin patched them)", kPlayMovie, kVideoPlay);
        return;
    }
    const DWORD site = kPlayMovieCall;
    g_movieHooked = RedirectCalls(&site, 1, kVideoPlay, reinterpret_cast<DWORD>(&MovieHook), "Startup SkipIntro");
    if (g_movieHooked)
        Log(1, "Startup SkipIntro: on - the script's PlayMovie call 0x%08lx -> TruQoL: movies skipped only while the "
               "front-end state 0x%08lx is 0 / 1 (before PressStart), never in a level; the legal screens stay",
            kPlayMovieCall, kFrontEndState);
}

// ---------------------------------------------------------------------------------------------------------------
// 0.1.1 live keys (TruMenu page Fixes / TruMenu.switches.txt "live"): game thread, from LiveTick. Every read passes the
// current value as its default (a missing key keeps it); one log line per change. Not here (restart): [TruQoL] Enabled,
// [Startup] ThreadCap.
void LiveReadOptions() {
    char note[300];
    const int logLevel = IniInt("TruQoL", "LogLevel", g_logLevel, 0, 2);
    if (logLevel != g_logLevel) {
        Log(0, "live: [TruQoL] LogLevel %d -> %d", g_logLevel, logLevel);
        g_logLevel = logLevel;
        g_statStart = 0;                     // LogLevel 2: the 10 s frame-rate lines start anew
        g_statFrames = g_statLate = 0;
        g_statWait = 0;
    }
    const char *const noHook = g_limitHooked ? "" : " - the clock calls are not hooked: no effect in this run";
    const int limit = IniInt("FrameLimit", "Enabled", g_limitEnabled, 0, 1);
    if (limit != g_limitEnabled) {
        g_limitEnabled = limit;
        Log(1, "live: [FrameLimit] Enabled %d -> %d - %s%s%s", !limit, limit,
            limit ? "the limiter waits from the next frame" : "the game's own frame rate from the next frame",
            limit ? OtherNote() : "", noHook);
    }
    const int fps = IniInt("FrameLimit", "MaxFps", g_maxFps, 20, 500);
    if (fps != g_maxFps) {
        Log(1, "live: [FrameLimit] MaxFps %d -> %d (dt 0xe7f190 = %.3f x 1/30 s; new cadence from the next frame)%s",
            g_maxFps, fps, 30.0 / fps, noHook);
        g_maxFps = fps;
        if (g_qpf) g_period = g_qpf / g_maxFps;
        g_next = 0;
    }
    const int autoOff = IniInt("FrameLimit", "AutoOff", g_autoOff, 0, 1);
    if (autoOff != g_autoOff) {
        g_autoOff = autoOff;
        Log(1, "live: [FrameLimit] AutoOff %d -> %d%s%s", !autoOff, autoOff,
            g_otherLimiter ? OtherNote() : g_detectPending ? " (d3d9.dll not loaded yet: no other limiter known)"
                                                           : " (no other limiter found: no change)", noHook);
    }
    const int spin = IniInt("FrameLimit", "SpinUs", g_spinUs, 0, 5000);
    if (spin != g_spinUs) {
        g_spinUs = spin;
        if (g_waitReady) g_spinTicks = g_qpf * SpinUsNow() / 1000000;
        Log(1, "live: [FrameLimit] SpinUs -> %d (last %d us of a wait as a pause loop)%s", spin, SpinUsNow(), noHook);
    }
    float fov = IniFloat("Camera", "Fov", g_fov, 0.0f, 2.0f);
    if (fov != 0.0f && fov < 0.5f) {
        Log(0, "live: [Camera] Fov=%g is below 0.5 - %g kept", fov, g_fov);
        fov = g_fov;
    }
    if (fov != g_fov) {
        Log(1, "live: [Camera] Fov %g -> %g%s%s", g_fov, fov,
            fov == 0.0f || fov == 1.0f ? " (the game's field of view)" : "",
            g_fovHooked ? "" : " - the FOV call is not hooked: no effect in this run");
        g_fov = fov;
    }
    const int cuts = IniInt("Camera", "FovCutscenes", g_fovCutscenes, 0, 1);
    if (cuts != g_fovCutscenes) {
        g_fovCutscenes = cuts;
        Log(1, "live: [Camera] FovCutscenes %d -> %d (%s)%s", !cuts, cuts,
            cuts ? "the factor applies to every camera" : "gameplay camera only, cutscenes unchanged",
            g_fovHooked ? "" : " - the FOV call is not hooked: no effect in this run");
    }
    const float shake = IniFloat("Camera", "ShakeScale", g_shakeScale, 0.0f, 1.0f);
    if (shake != g_shakeScale) {
        const float was = g_shakeScale;
        g_shakeRefused = false;              // a change of the key = a new attempt
        if (shake < 1.0f) {
            g_shakeScale = shake;            // first the factor, then the calls (ShakeStub reads it)
            ShakeApply(true, note, sizeof(note));
        } else {
            ShakeApply(false, note, sizeof(note));
            g_shakeScale = shake;
        }
        Log(1, "live: [Camera] ShakeScale %.2f -> %.2f%s", was, shake, note);
    }
}

// game thread, every frame (LimiterWait): at most once a second, and only when TruQoL.ini's last-write time changed,
// the live keys again. The time is kept only when it did not change during the read (a write that met the read is
// read again a second later).
DWORD g_liveTick = 0;
FILETIME g_iniTime = {0, 0};
bool g_iniTimeOk = false;

bool IniTime(FILETIME *t) {
    char ini[MAX_PATH];
    IniPath(ini, sizeof(ini));
    WIN32_FILE_ATTRIBUTE_DATA d;
    if (!GetFileAttributesExA(ini, GetFileExInfoStandard, &d)) return false;
    *t = d.ftLastWriteTime;
    return true;
}

void LiveTick() {
    const DWORD now = GetTickCount();
    if (now - g_liveTick < 1000) return;
    g_liveTick = now;
    FILETIME before, after;
    if (!IniTime(&before)) return;           // no TruQoL.ini: keep every value
    if (g_iniTimeOk && CompareFileTime(&before, &g_iniTime) == 0) return;
    LiveReadOptions();
    if (IniTime(&after) && CompareFileTime(&before, &after) == 0) {
        g_iniTime = before;
        g_iniTimeOk = true;
    }
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
    g_skipIntro = IniInt("Startup", "SkipIntro", 0, 0, 1);
}

void Start(HMODULE self) {
    ModuleDir(self, g_dir, sizeof(g_dir));
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruQoL.log", g_dir);
    ReadOptions();
    Log(1, "%s loaded (enabled %d, log level %d; FrameLimit %d / %d fps / AutoOff %d, Fov %g / cutscenes %d, ShakeScale "
           "%g, ThreadCap %d, SkipIntro %d)", kVersion, g_enabled, g_logLevel, g_limitEnabled, g_maxFps, g_autoOff, g_fov,
        g_fovCutscenes, g_shakeScale, g_threadCap, g_skipIntro);
    if (!g_enabled) { Log(1, "disabled by TruQoL.ini ([TruQoL] Enabled=0) - nothing patched"); return; }
    const DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - nothing patched", base, kImageBase); return; }
    StartThreadCap();                        // first: the CPU count runs in WinMain, soon after the plugins are loaded
    StartFrameLimit();
    StartCamera();
    StartSkipIntro();                        // 0.1.2: before WinMain, so no movie can be playing yet
    g_iniTimeOk = IniTime(&g_iniTime);       // 0.1.1: the live tick reads again only after a change of TruQoL.ini
    if (g_limitHooked)
        Log(1, "live: TruQoL.ini is read again at most once a second when it changes (LogLevel, FrameLimit Enabled / "
               "MaxFps / AutoOff / SpinUs, Camera Fov / FovCutscenes / ShakeScale; restart: Enabled, ThreadCap, "
               "SkipIntro)");
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
    return "TruQoL 0.1.2 (player options: frame limiter at the game's frame clock 0x5da230, FOV factor at the render "
           "projection 0x5cb0a8, camera shake factor 0x5eb460, CPU thread cap for the start-up count 0x4a21d0, start-up "
           "intro skip at the script's PlayMovie call 0x77bc7b; live INI re-read once a second for TruMenu page Fixes)";
}
