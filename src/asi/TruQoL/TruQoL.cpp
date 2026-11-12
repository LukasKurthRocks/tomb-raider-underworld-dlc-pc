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
// 3. [Startup] ThreadCap (default 8 since 0.1.3: live 2026-11-08 on a 36-thread PC 8 / 16 / 24 started and loaded DLC 2,
//    25 / 26 / 28 / 31 hung at the first load - the worker pool keeps at most 20 of 24+ workers alive, ENGINE.md 3;
//    more workers brought no load-time gain; 8 is what the `start /affinity FFFF` work-around gives)
//    - the start-up crash with > 31 logical CPUs: the CPU topology count 0x4a21d0 (called once:
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
// 0.1.3 (2026-11-09) [Startup] ThreadCap default 31 -> 8: the live bisection of 2026-11-08 (36-thread PC) showed
// 25 / 26 / 28 / 31 hang at the first load, 8 / 16 / 24 run, and more workers do not load faster (ENGINE.md 3).
// No code change besides the default.
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
//
// 0.1.4 (2026-11-11) [Fixes] FrontEndPauseBit (live, default 0 = the game's behaviour) - the stale pause bit in the
// front end (docs\Befund-Skript-Uhr-halbe-Zeit-1111.md, commit 9787ea5). The in-game pause 0x5d4780 / 0x5d4810 writes
// the pause byte 0xe7f143 = 6 and then sets [0xe7f0b4] |= 0x10000000; with that bit the frame-time function 0x5da230
// takes its paused branch 0x5da621 and stores a FIXED 0.5 to [0xe7f188] (0x5da664 fld [0x8413a8]). Only the unpause
// 0x5d4700 (0x5d4752) and the reset 0x5d3df0 at level load clear the bit; the level exit 0x5dab40 clears only bit 0x10
// (0x5dab9e) and writes the pause byte 0 (0x5dac6e, bl = 0 from 0x5dab46). After "pause -> back to the main menu" the
// front end keeps the bit: the main menu's Bink loop runs at 29.97 Hz with dt 0.5 / 30 s, every script clock there runs
// at half speed (teaser after ~81 s instead of 40 s; live 2026-11-10 via TruLink: [0xe7f0b4] = 0x50000000, [0xe7f188] =
// 0.5, main state [0xe7ed60] = 10). Same code on Xbox retail / TU. The fix uses the clock call 0x5da684 that 0.1 already
// redirects - it lies only in the paused branch, so it runs only while the bit is set: from 0.1.4 that one site goes to
// PauseClockStub (= PauseBitCheck, then exactly ClockStub). PauseBitCheck clears the bit (lock and) only while the
// switch is 1, the main state is 6 or 10 (front end, the rule of uigamedata f37 0x5d56e0) and the pause byte is not 6.
// Pause byte 6 is written only by the two pause functions, each right before it sets the bit (0x5d47a7 -> 0x5d47bb,
// 0x5d481a -> 0x5d482b); every other writer (unpause 0, level exit 0, 0x5d7538 / 0x5d756c / 0x5df883 / 0x5dfbc9 /
// 0x77c2a3 0, 0x5d757f 4, 0x5da941 0xa) ends that pause state - so "byte != 6" means no pause is open, and the pause
// menu itself decides by the same byte (0x78bb13 / 0x78bb28). In a level (main state 1) nothing is touched: the pause
// there keeps its freeze. The frame after the clear takes the running branch with the game's own "first frame after the
// pause" step ([0xe7f384] = 1 from 0x5da66a: saved values back, then 0x5da538 clears it), as after a real unpause; the
// other effects of the unpause 0x5d4700 (object manager 0x5785a0, 0x5bfdf0(0), [0xe7f094]+0x14) are NOT run - the level
// they belong to is gone. Readers of the bit: 0x5da233 (frame time) and 0x5bf861 (render step) only. One log line per
// clear at LogLevel 1 (at most one per 10 s; later ones counted in the next line).
//
// 0.1.5 (2026-11-11, Q22, workspace doc Befund-FMOD-Startabsturz-1111.md) [Diag] ExitTrace (restart, default 0 = nothing
// installed) - a diagnosis for the rare silent end at start-up (live 2026-11-10 20:45:44: logs stop, no WER dump, no
// Application event = no exception reached WER). With ExitTrace=1 TruQoL writes TruQoL.exit.log (own file, kept open
// with read sharing - TruQoL.log is opened per line with fopen_s, which refuses a second writer) with
//   (a) a session header with the full date, pid, main thread and the WER LocalDumps values for tru.exe (read only);
//   (b) first-chance exceptions with an error code (>= 0xC0000000) from a vectored handler registered first: code,
//       address (tru+offset or the allocation base of its module), thread, access kind / address for 0xC0000005 /
//       0xC0000006, esp; the first 24 in full, later ones counted. It always returns EXCEPTION_CONTINUE_SEARCH (logging
//       only). Written without heap or locks (own formatter, WriteFile, GetLocalTime, VirtualQuery) because it can run
//       inside a heap or loader fault or on the last page of an overflowed stack;
//   (c) every call of tru.exe's own ExitProcess / TerminateProcess(self) through its import slots 0x83e054 / 0x83e058
//       (chained: TruQoL calls what the slot held) with exit code, caller and the known site name: 0x478aec / 0x478a66
//       the fatal-error path 0x596cb0 -> dialog 0x47b4c0 -> 0x478a10 (main thread: shut-down, ExitProcess(0); another
//       thread: SuspendThread(main), TerminateProcess(-1)), 0x479690 the WinMain SKUType registry check, 0x59a0f1 the
//       allocator's "Unable to reserve %dMB of address space" box, 0x816a00 the CRT exit, 0x81d740 the CRT /GS failure
//       (0xc0000409), 0x81e3c7 the CRT invalid-parameter end (0xc000000d);
//   (d) DLL_PROCESS_DETACH with "process exit" = some module called ExitProcess (also one that bypasses tru.exe's IAT).
// Reading: an exit line names the path; a detach line without an exit line = ExitProcess from another module; only
// exception lines = a fault followed by an end outside these paths (fail-fast, a handler that terminates); nothing at
// all = TerminateProcess by another module or from outside. TruMenu's game.quit logs itself (TruMenu.log). The key is
// not in the shipped TruQoL.ini (every key there needs a TruMenu switches row); add "[Diag]" / "ExitTrace=1" by hand.
//
// 0.1.6 (2026-11-11, Q69, workspace doc Befund-PC-Technik-Q69-1111.md) [Save] RetryOnLock (restart, default 0 = nothing
// patched) - saving fails while security software runs (Steam guide). The save / load state machine (writer 0x6db810, loader
// 0x6db9b0, ticked by the save menu code 0x78ab60.. through 0x6dc140) opens its file in 0x6db690: write = CreateFileW(path,
// GENERIC_WRITE, share 0, -, CREATE_ALWAYS, FILE_FLAG_OVERLAPPED), read = (GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING,
// 0); both reach the one call `call [0x83e0c4]` at 0x6db6d0. On INVALID_HANDLE_VALUE it sets status +0x24 = 2 and the
// next tick takes step 2 = abort 0x6db956 (CloseHandle, DeleteFileW(path) when the status is not 0, result +0x1c = 3):
// one try, no retry, no temporary file. A scanner that still holds the file (no FILE_SHARE_WRITE) makes the open fail
// with ERROR_SHARING_VIOLATION. RetryOnLock=1: the call becomes `call SaveCreateFile; nop`; it calls what the IAT slot
// 0x83e0c4 holds (chained), and only when that fails with ERROR_SHARING_VIOLATION / ERROR_LOCK_VIOLATION /
// ERROR_ACCESS_DENIED it waits 100 ms and tries again, at most 10 times (at most about 1 s on the thread that ticks the
// save, only in that error case). One log line per retried open (file name, first error, result).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <psapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "../TruLog.h"                      // Q107: date + time in every log line, session header

#pragma comment(lib, "advapi32.lib")   // 0.1.5 ExitTrace: the WER LocalDumps values (read only)
#pragma intrinsic(_ReturnAddress)

#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif

namespace {

const char kVersion[] = "TruQoL 0.1.7";             // 0.1.7: dated log lines (Q107)
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

// ---- 5. front end: the stale pause bit (0.1.4) - nothing patched here; the hook is the clock call kClockCallPause ----
const DWORD kGameFlags = 0x00e7f0b4;        // dword: bit 0x10000000 = paused (frame time fixed at 0.5)
const DWORD kPauseBit = 0x10000000;
const DWORD kPauseByte = 0x00e7f143;        // byte: 6 = paused (written only by the two pause functions)
const DWORD kPauseBranch = 0x005da664;      // paused branch: fld [0x8413a8] (0.5); [0xe7f384] = 1; fstp [0xe7f188]; ...
const char *const kPauseBranchHex = "d905a8138400 c70584f3e70001000000 d91d88f1e700 c70560f1e70010000000";
const DWORD kPauseHalf = 0x008413a8;        // float 0.5
const char *const kPauseHalfHex = "0000003f";
const DWORD kPauseOn1 = 0x005d47a7;         // pause 0x5d4780: byte 6, two calls, then the bit
const char *const kPauseOn1Hex = "c60543f1e70006 e83db6feff 83c404 e8f52cfbff 810db4f0e70000000010";
const DWORD kPauseOn2 = 0x005d481a;         // pause 0x5d4810: byte 6, two calls, then the bit
const char *const kPauseOn2Hex = "c60543f1e70006 e88a2cfbff e8a5eceaff 810db4f0e70000000010";
const DWORD kUnpauseClear = 0x005d4752;     // unpause 0x5d4700: clear the bit, byte 0
const char *const kUnpauseClearHex = "8125b4f0e700ffffffef 6a00 c60543f1e70000";
const DWORD kLevelExitBit = 0x005dab9e;     // level exit 0x5dab40: clears only bit 0x10
const char *const kLevelExitBitHex = "8325b4f0e700ef";
const DWORD kLevelExitByte = 0x005dac6e;    // level exit: pause byte = bl (0, xor ebx, ebx at 0x5dab46)
const char *const kLevelExitByteHex = "881d43f1e700";
const DWORD kFrontEndTest = 0x005d56e0;     // uigamedata f37: main state 6 or 10 = front end
const char *const kFrontEndTestHex = "a160ede700 83f806 7408 83f80a 7403 32c0 c3 b001 c3";
const DWORD kRenderStepRead = 0x005bf861;   // the other reader of the bit (render time step)
const char *const kRenderStepReadHex = "f705b4f0e70000000010";

// ---- 6. saves: the save / load file open 0x6db690 (0.1.6) ----
const DWORD kSaveOpenArgs = 0x006db6a9;     // write: push 0x40000000 (overlapped), 2 (CREATE_ALWAYS), 0, 0 (share),
                                            // 0x40000000 (GENERIC_WRITE), path; read: 3, 0, 1, 0x80000000, path; then
                                            // call [0x83e0c4]; cmp eax, -1; mov [esi], eax; jne; status +0x24 = 2
const char *const kSaveOpenArgsHex = "6800000040 7410 6a02 50 50 8b44241c 6800000040 50 eb10 8b4c2410 6a03 6a00 6a01 "
                                     "6800000080 51 ff15c4e08300 83f8ff 8906 750d c7462402000000";
const DWORD kSaveOpenCall = 0x006db6d0;     // call [0x83e0c4] (6 bytes) - the patched instruction
const DWORD kCreateFileWIat = 0x0083e0c4;
const DWORD kSaveAbort = 0x006db956;        // writer step 2: CloseHandle, status != 0 -> DeleteFileW(path)
const char *const kSaveAbortHex = "8b06 33ff 3bc7 7407 50 ff15b4e18300 397e24 740a 8b5628 52 ff15cce08300";
const DWORD kSaveTick = 0x006db810;         // writer tick: status 2 .. 5 -> step 2 (abort), no retry
const char *const kSaveTickHex = "56 8bf1 8b4624 83f801 0f846d010000 83c0fe 83f803 57 bf02000000 7703 897e20";
const int kSaveRetries = 10;                // at most 10 retries ...
const DWORD kSaveRetryMs = 100;             // ... 100 ms apart (about 1 s, only after a failed first open)

// ---- options (TruQoL.ini) ----
int g_enabled = 1, g_logLevel = 1;
int g_limitEnabled = 1, g_maxFps = 60, g_autoOff = 1, g_spinUs = 0;
float g_fov = 0.0f;                         // factor; 0 (or 1) = game
int g_fovCutscenes = 0;
float g_shakeScale = 1.0f;                  // read by ShakeStub
int g_threadCap = 8;   // 0.1.3: default 8 (live 2026-11-08, 36-thread PC: 8 / 16 / 24 run, 25 / 26 / 28 / 31 hang)
int g_skipIntro = 0;                        // 0.1.2: [Startup] SkipIntro (restart)
int g_frontEndPauseBit = 0;                 // 0.1.4: [Fixes] FrontEndPauseBit (live; read by PauseBitCheck)
int g_exitTrace = 0;                        // 0.1.5: [Diag] ExitTrace (restart; not in the shipped INI)
int g_saveRetry = 0;                        // 0.1.6: [Save] RetryOnLock (restart)

char g_logPath[MAX_PATH], g_dir[MAX_PATH];
CRITICAL_SECTION g_logLock;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[900];
    int n = TruLogStamp(line, sizeof(line));     // Q107: "YYYY-MM-DD HH:MM:SS.mmm "
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        TruLogSessionStart(f, "TruQoL", kVersion);
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

// a group of rel32 call sites that must all call `game` today; site i is pointed to hooks[i], all or none (0.1.4: one
// hook per site - the paused-branch clock call gets its own stub)
bool RedirectCallsTo(const DWORD *sites, const DWORD *hooks, int count, DWORD game, const char *what) {
    for (int i = 0; i < count; ++i) {
        DWORD t = CallTarget(sites[i]);
        if (t != game) {
            Log(0, "%s: the call at 0x%08lx goes to 0x%08lx, not the game's 0x%08lx (another plugin?) - left untouched, "
                   "feature off", what, sites[i], t, game);
            return false;
        }
    }
    for (int i = 0; i < count; ++i) {
        DWORD rel = hooks[i] - (sites[i] + 5);
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

// all sites to the same hook
bool RedirectCalls(const DWORD *sites, int count, DWORD game, DWORD hook, const char *what) {
    DWORD hooks[4];
    if (count < 1 || count > 4) return false;
    for (int i = 0; i < count; ++i) hooks[i] = hook;
    return RedirectCallsTo(sites, hooks, count, game, what);
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

// ---- 0.1.4 [Fixes] FrontEndPauseBit: the stale pause bit in the front end ----
bool g_pauseBitOk = false;                  // the pause / unpause / level-exit / front-end code matched at the start
LONG g_pauseBitClears = 0, g_pauseBitLogged = 0;
DWORD g_pauseBitLogTick = 0;
bool g_pauseBitHeldNoted = false;           // "pause byte 6 in the front end" logged once

// game thread, from PauseClockStub = only in the paused branch of 0x5da230 (the bit was set at 0x5da233 this frame)
extern "C" void __cdecl PauseBitCheck() {
    if (!g_frontEndPauseBit || !g_pauseBitOk) return;
    const DWORD mainState = *reinterpret_cast<const volatile DWORD *>(kMainState);
    if (mainState != 6 && mainState != 10) return;                       // a level (1) or a load: the game's pause
    const BYTE pauseByte = *reinterpret_cast<const volatile BYTE *>(kPauseByte);
    if (pauseByte == 6) {                                                 // a pause the game holds open: keep it
        if (!g_pauseBitHeldNoted) {
            g_pauseBitHeldNoted = true;
            Log(1, "Fixes FrontEndPauseBit: front end (main state %lu) with the pause byte 0x%08lx = 6 - a pause the "
                   "game holds open, the bit stays (logged once)", mainState, kPauseByte);
        }
        return;
    }
    volatile LONG *flags = reinterpret_cast<volatile LONG *>(kGameFlags);
    if (!(*flags & static_cast<LONG>(kPauseBit))) return;
    const LONG before = InterlockedAnd(flags, ~static_cast<LONG>(kPauseBit));
    const LONG n = ++g_pauseBitClears;
    const DWORD now = GetTickCount();
    if (g_pauseBitLogged == 0 || now - g_pauseBitLogTick >= 10000) {
        Log(1, "Fixes FrontEndPauseBit: stale pause bit cleared in the front end (main state %lu, pause byte %u, "
               "[0x%08lx] 0x%08lx -> 0x%08lx) - the frame time is measured again from the next frame; clear %ld (%ld not "
               "logged since the last line)", mainState, pauseByte, kGameFlags, static_cast<DWORD>(before),
            static_cast<DWORD>(before & ~static_cast<LONG>(kPauseBit)), n, n - 1 - g_pauseBitLogged);
        g_pauseBitLogged = n;
        g_pauseBitLogTick = now;
    }
}

// in place of `call 0x597f10` at 0x5da684 only (the paused branch): the front-end check, then exactly ClockStub
__declspec(naked) void PauseClockStub() {
    __asm {
        call PauseBitCheck
        call LimiterWait
        jmp dword ptr [g_clockFn]
    }
}

// the premises of PauseBitCheck (read only; the hook itself is the clock call 0x5da684 of StartFrameLimit)
void StartPauseBit() {
    g_pauseBitOk = HexBytesAt(kPauseBranch, kPauseBranchHex) && HexBytesAt(kPauseHalf, kPauseHalfHex) &&
                   HexBytesAt(kPauseOn1, kPauseOn1Hex) && HexBytesAt(kPauseOn2, kPauseOn2Hex) &&
                   HexBytesAt(kUnpauseClear, kUnpauseClearHex) && HexBytesAt(kLevelExitBit, kLevelExitBitHex) &&
                   HexBytesAt(kLevelExitByte, kLevelExitByteHex) && HexBytesAt(kFrontEndTest, kFrontEndTestHex) &&
                   HexBytesAt(kRenderStepRead, kRenderStepReadHex);
    if (!g_pauseBitOk) {
        Log(0, "Fixes FrontEndPauseBit: off - the pause / unpause / level-exit / front-end code (0x%08lx, 0x%08lx, "
               "0x%08lx, 0x%08lx) does not match this tru.exe; nothing is cleared in this run", kPauseOn1, kUnpauseClear,
            kLevelExitBit, kFrontEndTest);
        return;
    }
    Log(1, "Fixes FrontEndPauseBit: %s - the paused-branch clock call 0x%08lx -> TruQoL: %s", g_frontEndPauseBit ? "on" : "off",
        kClockCallPause, g_frontEndPauseBit ? "the stale pause bit 0x10000000 of [0xe7f0b4] is cleared while the main state "
                                              "is 6 / 10 (front end) and the pause byte is not 6; a level's pause stays"
                                            : "pass-through, the game's behaviour (1 in TruQoL.ini takes effect within a second)");
}

// 0.1.1: the clock calls are patched whenever TruQoL is enabled and the bytes match - also with [FrameLimit] Enabled=0
// (then ClockStub is a pass-through until Enabled=1 is read live); they also carry the live tick
void StartFrameLimit() {
    if (!HexBytesAt(kFrameTimer, kFrameTimerHex) || !HexBytesAt(kClockCallPause, kClockCallPauseHex) ||
        !HexBytesAt(kClock, kClockHex) || !HexBytesAt(kFrameStore, kFrameStoreHex)) {
        Log(0, "FrameLimit: off - the frame-time function 0x%08lx / clock 0x%08lx do not match this tru.exe; no live "
               "tick either: every TruQoL.ini change takes effect at the next start", kFrameTimer, kClock);
        Log(0, "Fixes FrontEndPauseBit: off - it needs the clock call 0x%08lx", kClockCallPause);
        return;
    }
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    g_qpf = f.QuadPart;
    g_period = g_qpf / g_maxFps;
    const DWORD sites[2] = {kClockCallRun, kClockCallPause};
    // 0.1.4: the paused-branch call goes to PauseClockStub (= the front-end pause-bit check, then exactly ClockStub)
    const DWORD hooks[2] = {reinterpret_cast<DWORD>(&ClockStub), reinterpret_cast<DWORD>(&PauseClockStub)};
    if (!RedirectCallsTo(sites, hooks, 2, kClock, "FrameLimit")) {
        Log(0, "FrameLimit: no live tick - every TruQoL.ini change takes effect at the next start");
        Log(0, "Fixes FrontEndPauseBit: off - it needs the clock call 0x%08lx", kClockCallPause);
        return;
    }
    g_limitHooked = true;
    StartPauseBit();
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
// 6. diagnosis (0.1.5): [Diag] ExitTrace - see the header. Nothing of this runs with ExitTrace=0 (the default).
const DWORD kIatExitProcess = 0x0083e054;       // tru.exe import slot KERNEL32!ExitProcess
const DWORD kIatTerminateProcess = 0x0083e058;  // tru.exe import slot KERNEL32!TerminateProcess
const LONG kXtFullLines = 24;                   // first-chance exceptions written in full; later ones only counted
const int kXtModMax = 256;

struct XtSite {
    DWORD ret;            // return address of `call dword ptr [slot]` (6 bytes before)
    const char *call;     // the call's bytes (checked at the start; an unchecked site is shown without a name)
    const char *what;
};
const XtSite kXtSites[] = {
    {0x00478af2, "ff1554e08300", "fatal-error path 0x596cb0 -> 0x478a10 on the main thread (dialog 0x47b4c0, then shut-down)"},
    {0x00478a6c, "ff1558e08300", "fatal-error path 0x596cb0 -> 0x478a10 on another thread (main thread suspended)"},
    {0x00479696, "ff1554e08300", "WinMain registry check SKUType (0x4791d0)"},
    {0x0059a0f7, "ff1554e08300", "allocator: 'Unable to reserve %dMB of address space' message box (0x59a0e9)"},
    {0x00816a06, "ff1554e08300", "CRT exit (__crtExitProcess: WinMain returned or exit())"},
    {0x0081d746, "ff1558e08300", "CRT /GS cookie failure (0xc0000409, after UnhandledExceptionFilter)"},
    {0x0081e3cd, "ff1558e08300", "CRT invalid parameter (0xc000000d, after UnhandledExceptionFilter)"},
};
const int kXtSiteCount = sizeof(kXtSites) / sizeof(kXtSites[0]);
bool g_xtSiteOk[kXtSiteCount];

typedef VOID(WINAPI *ExitProcessFn)(UINT);
typedef BOOL(WINAPI *TerminateProcessFn)(HANDLE, UINT);
ExitProcessFn g_xtExit = nullptr;               // what tru.exe's slot held (kernel32's or another hook)
TerminateProcessFn g_xtTerminate = nullptr;
HANDLE g_xtFile = INVALID_HANDLE_VALUE;
DWORD g_xtMainThread = 0, g_xtImageEnd = 0;
volatile LONG g_xtExceptions = 0;
volatile LONG g_xtLastTick = 0;                 // GetTickCount of the last written exception line
volatile DWORD g_xtLastCode = 0, g_xtLastAddr = 0, g_xtLastThread = 0;
volatile LONG g_xtModBusy = 0;
HMODULE g_xtSeen[kXtModMax];
int g_xtSeenCount = 0;

// line builder without heap, CRT or locks: it runs inside faults (heap / loader) and on an overflowed stack
struct XtLine {
    char s[480];
    int n;
    XtLine() : n(0) {}
    void Ch(char c) {
        if (n < static_cast<int>(sizeof(s)) - 3) s[n++] = c;
    }
    void Str(const char *t) {
        while (t && *t) Ch(*t++);
    }
    void Hex(DWORD v) {
        Str("0x");
        for (int i = 7; i >= 0; --i) Ch("0123456789abcdef"[(v >> (i * 4)) & 0xf]);
    }
    void Dec(DWORD v, int width = 1) {
        char d[12];
        int k = 0;
        do {
            d[k++] = static_cast<char>('0' + v % 10);
            v /= 10;
        } while (v && k < 11);
        while (k < width && k < 11) d[k++] = '0';
        while (k > 0) Ch(d[--k]);
    }
    void Time(bool date) {
        SYSTEMTIME t;
        GetLocalTime(&t);
        if (date) {
            Dec(t.wYear, 4); Ch('-'); Dec(t.wMonth, 2); Ch('-'); Dec(t.wDay, 2); Ch(' ');
        }
        Dec(t.wHour, 2); Ch(':'); Dec(t.wMinute, 2); Ch(':'); Dec(t.wSecond, 2); Ch('.'); Dec(t.wMilliseconds, 3); Ch(' ');
    }
    void Addr(DWORD a) {
        Hex(a);
        if (a >= kImageBase && a < g_xtImageEnd) { Str(" (tru.exe)"); return; }
        MEMORY_BASIC_INFORMATION m;
        if (VirtualQuery(reinterpret_cast<LPCVOID>(static_cast<DWORD_PTR>(a)), &m, sizeof(m)) && m.AllocationBase) {
            Str(" (allocation base ");
            Hex(static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(m.AllocationBase)));
            Str(" - see the module lines)");
        }
    }
    void Thread() {
        const DWORD id = GetCurrentThreadId();
        Str("thread ");
        Dec(id);
        if (id == g_xtMainThread) Str(" (main)");
    }
    void Write() {
        s[n++] = '\r';
        s[n++] = '\n';
        DWORD written = 0;
        if (g_xtFile != INVALID_HANDLE_VALUE) WriteFile(g_xtFile, s, static_cast<DWORD>(n), &written, nullptr);
    }
};

// module list (name, base, size) - only new modules; from the watch thread and the ExitProcess hook (normal context,
// never from the exception handler or TerminateProcess: those may run while another thread holds the loader lock)
void XtModules(const char *when) {
    if (InterlockedExchange(&g_xtModBusy, 1)) return;
    HMODULE mods[kXtModMax];
    DWORD need = 0;
    if (K32EnumProcessModules(GetCurrentProcess(), mods, sizeof(mods), &need)) {
        int count = static_cast<int>(need / sizeof(HMODULE));
        if (count > kXtModMax) count = kXtModMax;
        for (int i = 0; i < count; ++i) {
            bool seen = false;
            for (int k = 0; k < g_xtSeenCount && !seen; ++k) seen = g_xtSeen[k] == mods[i];
            if (seen || g_xtSeenCount >= kXtModMax) continue;
            g_xtSeen[g_xtSeenCount++] = mods[i];
            char path[MAX_PATH];
            DWORD len = GetModuleFileNameA(mods[i], path, MAX_PATH);
            const char *name = path;
            for (DWORD c = 0; c < len; ++c)
                if (path[c] == '\\' || path[c] == '/') name = path + c + 1;
            MODULEINFO info = {};
            K32GetModuleInformation(GetCurrentProcess(), mods[i], &info, sizeof(info));
            XtLine l;
            l.Time(true);                    // Q107: date in every line
            l.Str("module (");
            l.Str(when);
            l.Str("): ");
            l.Str(len ? name : "?");
            l.Str(" base ");
            l.Hex(static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(mods[i])));
            l.Str(" size ");
            l.Hex(info.SizeOfImage);
            l.Write();
        }
    }
    InterlockedExchange(&g_xtModBusy, 0);
}

// first-chance exceptions with an error code; logging only
LONG CALLBACK XtVeh(EXCEPTION_POINTERS *ep) {
    const EXCEPTION_RECORD *r = ep ? ep->ExceptionRecord : nullptr;
    if (!r || r->ExceptionCode < 0xc0000000u || g_xtFile == INVALID_HANDLE_VALUE) return EXCEPTION_CONTINUE_SEARCH;
    const LONG count = InterlockedIncrement(&g_xtExceptions);
    g_xtLastCode = r->ExceptionCode;             // for the exit / detach line (the probes of other plugins may use up
    g_xtLastAddr = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(r->ExceptionAddress));   // the full lines)
    g_xtLastThread = GetCurrentThreadId();
    const LONG now = static_cast<LONG>(GetTickCount());
    if (count > kXtFullLines) {                  // later ones: at most one line per second
        const LONG last = g_xtLastTick;
        if (static_cast<DWORD>(now - last) < 1000 || InterlockedCompareExchange(&g_xtLastTick, now, last) != last)
            return EXCEPTION_CONTINUE_SEARCH;
    } else {
        g_xtLastTick = now;
    }
    XtLine l;
    l.Time(true);                            // Q107: date in every line
    l.Str("first-chance exception ");
    l.Hex(r->ExceptionCode);
    l.Str(" at ");
    l.Addr(static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(r->ExceptionAddress)));
    l.Str("; ");
    l.Thread();
    if ((r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION || r->ExceptionCode == EXCEPTION_IN_PAGE_ERROR) &&
        r->NumberParameters >= 2) {
        const ULONG_PTR kind = r->ExceptionInformation[0];
        l.Str(kind == 0 ? "; read of " : kind == 1 ? "; write to " : kind == 8 ? "; execute at " : "; access to ");
        l.Hex(static_cast<DWORD>(r->ExceptionInformation[1]));
    }
    if (ep->ContextRecord) {
        l.Str("; esp ");
        l.Hex(ep->ContextRecord->Esp);
    }
    l.Str("; #");
    l.Dec(static_cast<DWORD>(count));
    if (count == kXtFullLines) l.Str(" - later ones at most one line per second (count + last one in the exit line)");
    l.Write();
    return EXCEPTION_CONTINUE_SEARCH;
}

void XtLastException(XtLine &l) {
    l.Str("; first-chance exceptions ");
    l.Dec(static_cast<DWORD>(g_xtExceptions));
    if (!g_xtExceptions) return;
    l.Str(", last ");
    l.Hex(g_xtLastCode);
    l.Str(" at ");
    l.Hex(g_xtLastAddr);
    if (g_xtLastAddr >= kImageBase && g_xtLastAddr < g_xtImageEnd) l.Str(" (tru.exe)");
    l.Str(" thread ");
    l.Dec(g_xtLastThread);
}

void XtExitLine(const char *what, UINT code, DWORD from) {
    XtLine l;
    l.Time(true);
    l.Str("exit: ");
    l.Str(what);
    l.Str("(exit code ");
    l.Hex(code);
    l.Str(") called from ");
    l.Addr(from);
    for (int i = 0; i < kXtSiteCount; ++i)
        if (g_xtSiteOk[i] && kXtSites[i].ret == from) {
            l.Str(" = ");
            l.Str(kXtSites[i].what);
        }
    l.Str("; ");
    l.Thread();
    XtLastException(l);
    l.Write();
}

VOID WINAPI XtExitProcess(UINT code) {
    XtExitLine("ExitProcess", code, static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(_ReturnAddress())));
    XtModules("at exit");                        // every thread still runs here: the normal context
    ExitProcessFn next = g_xtExit;
    if (next) next(code);
    ExitProcess(code);                           // not reached
}

BOOL WINAPI XtTerminateProcess(HANDLE process, UINT code) {
    if (process == GetCurrentProcess() || GetProcessId(process) == GetCurrentProcessId())
        XtExitLine("TerminateProcess", code, static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(_ReturnAddress())));
    TerminateProcessFn next = g_xtTerminate;
    return next ? next(process, code) : TerminateProcess(process, code);
}

// one import slot of tru.exe -> hook; the hook calls what the slot held (kernel32's function or another hook)
bool XtHookSlot(DWORD slot, const char *name, DWORD hook, DWORD *original) {
    DWORD current = 0;
    if (!ReadDword(slot, &current) || !current) {
        Log(0, "Diag ExitTrace: import slot 0x%08lx (%s) unreadable or empty - not hooked", slot, name);
        return false;
    }
    char owner[MAX_PATH] = "?";
    HMODULE mod = nullptr;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCSTR>(static_cast<DWORD_PTR>(current)), &mod) && mod)
        GetModuleFileNameA(mod, owner, MAX_PATH);
    const DWORD own = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetProcAddress(GetModuleHandleA("kernel32.dll"), name)));
    *original = current;
    if (!WriteCode(slot, &hook, sizeof(hook))) return false;
    Log(1, "Diag ExitTrace: tru.exe import slot 0x%08lx %s held 0x%08lx (%s%s) -> TruQoL, chained", slot, name, current,
        owner, current == own ? ", kernel32's own" : ", NOT kernel32's own address: another hook, called after TruQoL");
    return true;
}

// watch thread: the module lines (allocation bases of the exception lines -> names) every 2 s for the first 60 s
DWORD WINAPI XtWatch(LPVOID) {
    for (int i = 0; i < 30; ++i) {
        XtModules(i ? "new" : "start");
        Sleep(2000);
    }
    return 0;
}

DWORD XtImageEnd() {                             // tru.exe's SizeOfImage from its PE header
    __try {
        const BYTE *base = reinterpret_cast<const BYTE *>(static_cast<DWORD_PTR>(kImageBase));
        const IMAGE_NT_HEADERS32 *nt = reinterpret_cast<const IMAGE_NT_HEADERS32 *>(
            base + reinterpret_cast<const IMAGE_DOS_HEADER *>(base)->e_lfanew);
        return kImageBase + nt->OptionalHeader.SizeOfImage;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return kImageBase;
    }
}

void XtRegDword(HKEY key, const char *value, char *out, size_t n) {
    DWORD v = 0, size = sizeof(v), type = 0;
    if (RegQueryValueExA(key, value, nullptr, &type, reinterpret_cast<BYTE *>(&v), &size) == ERROR_SUCCESS &&
        type == REG_DWORD)
        _snprintf_s(out, n, _TRUNCATE, "%lu", v);
    else
        _snprintf_s(out, n, _TRUNCATE, "-");
}

void StartExitTrace() {
    if (!g_exitTrace) {
        Log(1, "Diag ExitTrace: off ([Diag] ExitTrace=0, restart) - no exception / exit trace");
        return;
    }
    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sTruQoL.exit.log", g_dir);
    g_xtFile = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (g_xtFile == INVALID_HANDLE_VALUE) {
        Log(0, "Diag ExitTrace: %s cannot be opened (%lu) - off", path, GetLastError());
        return;
    }
    g_xtMainThread = GetCurrentThreadId();       // DllMain: the ASI loader loads the plugins on the main thread
    g_xtImageEnd = XtImageEnd();
    int sitesOk = 0;
    for (int i = 0; i < kXtSiteCount; ++i) {
        g_xtSiteOk[i] = HexBytesAt(kXtSites[i].ret - 6, kXtSites[i].call);
        if (g_xtSiteOk[i]) ++sitesOk;
    }
    char dumpType[16] = "-", dumpCount[16] = "-", dumpFolder[MAX_PATH] = "";
    bool werKey = false;
    HKEY key = nullptr;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting\\LocalDumps\\tru.exe",
                      0, KEY_QUERY_VALUE | KEY_WOW64_64KEY, &key) == ERROR_SUCCESS) {
        werKey = true;
        XtRegDword(key, "DumpType", dumpType, sizeof(dumpType));
        XtRegDword(key, "DumpCount", dumpCount, sizeof(dumpCount));
        DWORD size = sizeof(dumpFolder) - 1, type = 0;
        if (RegQueryValueExA(key, "DumpFolder", nullptr, &type, reinterpret_cast<BYTE *>(dumpFolder), &size) !=
                ERROR_SUCCESS || (type != REG_SZ && type != REG_EXPAND_SZ))
            dumpFolder[0] = 0;
        dumpFolder[sizeof(dumpFolder) - 1] = 0;
        RegCloseKey(key);
    }
    char head[1000];
    XtLine stamp;
    stamp.Time(true);
    stamp.s[stamp.n] = 0;
    _snprintf_s(head, sizeof(head), _TRUNCATE,
                "%s=== %s ExitTrace: pid %lu, main thread %lu, tru.exe 0x%08lx..0x%08lx, %d of %d known exit sites "
                "verified; WER LocalDumps tru.exe: %s%s%s%s%s%s%s (read only). Lines: 'first-chance exception' = "
                "seen by the vectored handler (may still be caught); 'exit:' = tru.exe's own ExitProcess / "
                "TerminateProcess; 'detach: process exit' = some module's ExitProcess; no line = ended from outside "
                "these paths\r\n",
                stamp.s, kVersion, GetCurrentProcessId(), g_xtMainThread, kImageBase, g_xtImageEnd, sitesOk,
                kXtSiteCount, werKey ? "DumpType " : "key not found", werKey ? dumpType : "",
                werKey ? ", DumpCount " : "", werKey ? dumpCount : "", werKey ? ", DumpFolder '" : "",
                werKey ? dumpFolder : "", werKey ? "'" : "");
    DWORD written = 0;
    WriteFile(g_xtFile, head, static_cast<DWORD>(strlen(head)), &written, nullptr);
    PVOID veh = AddVectoredExceptionHandler(1, &XtVeh);
    DWORD exitOrig = 0, termOrig = 0;
    const bool exitHooked = XtHookSlot(kIatExitProcess, "ExitProcess",
                                       static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(&XtExitProcess)), &exitOrig);
    if (exitHooked) g_xtExit = reinterpret_cast<ExitProcessFn>(static_cast<DWORD_PTR>(exitOrig));
    const bool termHooked = XtHookSlot(kIatTerminateProcess, "TerminateProcess",
                                       static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(&XtTerminateProcess)), &termOrig);
    if (termHooked) g_xtTerminate = reinterpret_cast<TerminateProcessFn>(static_cast<DWORD_PTR>(termOrig));
    HANDLE watch = CreateThread(nullptr, 0, &XtWatch, nullptr, 0, nullptr);
    if (watch) CloseHandle(watch);
    Log(1, "Diag ExitTrace: on - %sTruQoL.exit.log: first-chance exceptions >= 0xC0000000 (vectored handler %s, first "
           "%ld in full), tru.exe's ExitProcess %s / TerminateProcess %s (%d of %d exit sites named), module lines for "
           "60 s, the DLL detach (restart key; logging only, nothing else changes)",
        g_dir, veh ? "on" : "FAILED", kXtFullLines, exitHooked ? "hooked" : "NOT hooked",
        termHooked ? "hooked" : "NOT hooked", sitesOk, kXtSiteCount);
}

// DLL_PROCESS_DETACH (heap-free: during ExitProcess the other threads are already gone, maybe holding locks)
void XtDetach(bool processExit) {
    if (g_xtFile == INVALID_HANDLE_VALUE) return;
    XtLine l;
    l.Time(true);
    l.Str(processExit ? "detach: process exit (some module called ExitProcess)" : "detach: FreeLibrary");
    l.Str("; ");
    l.Thread();
    XtLastException(l);
    l.Write();
}

// ---------------------------------------------------------------------------------------------------------------
// 7. saves (0.1.6): [Save] RetryOnLock - see the header. Nothing of this runs with RetryOnLock=0 (the default).
typedef HANDLE(WINAPI *CreateFileWFn)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
bool g_saveHooked = false;
volatile LONG g_saveOpens = 0, g_saveRetried = 0;

// the file name for the log (the game's own wide path: last part only, ASCII, copied under SEH)
void SaveName(LPCWSTR path, char *out, size_t n) {
    out[0] = 0;
    if (!path) { strcpy_s(out, n, "(null)"); return; }
    __try {
        LPCWSTR name = path;
        for (LPCWSTR p = path; *p; ++p)
            if (*p == L'\\' || *p == L'/') name = p + 1;
        size_t k = 0;
        for (; k + 1 < n && name[k]; ++k)
            out[k] = (name[k] >= 0x20 && name[k] < 0x7f) ? static_cast<char>(name[k]) : '?';
        out[k] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        strcpy_s(out, n, "(unreadable)");
    }
}

// the errors a scanner / indexer / backup tool that still holds the file gives; "not found" and the rest stay the game's
bool SaveLockError(DWORD e) {
    return e == ERROR_SHARING_VIOLATION || e == ERROR_LOCK_VIOLATION || e == ERROR_ACCESS_DENIED;
}

// in place of `call [0x83e0c4]` (CreateFileW) at 0x6db6d0 in the save / load file open 0x6db690 (stdcall, the same seven
// arguments, the game reads eax only: cmp eax, -1)
HANDLE WINAPI SaveCreateFile(LPCWSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disposition,
                             DWORD flags, HANDLE templ) {
    DWORD slot = 0;
    CreateFileWFn real = ReadDword(kCreateFileWIat, &slot) && slot ? reinterpret_cast<CreateFileWFn>(slot)
                                                                     : &CreateFileW;
    InterlockedIncrement(&g_saveOpens);
    HANDLE h = real(path, access, share, sa, disposition, flags, templ);
    if (h != INVALID_HANDLE_VALUE) return h;
    DWORD err = GetLastError();
    if (!SaveLockError(err)) return h;       // e.g. no save file yet on a load: the game's own answer, untouched
    const DWORD first = err;
    int tries = 0;
    while (tries < kSaveRetries && h == INVALID_HANDLE_VALUE && SaveLockError(err)) {
        Sleep(kSaveRetryMs);
        ++tries;
        h = real(path, access, share, sa, disposition, flags, templ);
        err = h == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    }
    InterlockedIncrement(&g_saveRetried);
    char name[80];
    SaveName(path, name, sizeof(name));
    const char *const what = (access & GENERIC_WRITE) ? "write" : "read";
    if (h != INVALID_HANDLE_VALUE) {
        Log(1, "Save RetryOnLock: '%s' (%s) - CreateFileW error %lu at the first try, opened after %d retr%s x %lu ms "
               "(%ld retried opens of %ld)", name, what, first, tries, tries == 1 ? "y" : "ies", kSaveRetryMs,
            g_saveRetried, g_saveOpens);
        return h;
    }
    Log(0, "Save RetryOnLock: '%s' (%s) - CreateFileW error %lu at the first try, still %lu after %d retries x %lu ms - "
           "the game's own failure path (status 2, abort 0x6db956)", name, what, first, err, tries, kSaveRetryMs);
    SetLastError(err);
    return h;
}

void StartSaveRetry() {
    if (!g_saveRetry) {
        Log(1, "Save RetryOnLock: off (RetryOnLock=0) - the game's own save / load open: one CreateFileW, no retry "
               "(restart key)");
        return;
    }
    if (!HexBytesAt(kSaveOpenArgs, kSaveOpenArgsHex) || !HexBytesAt(kSaveAbort, kSaveAbortHex) ||
        !HexBytesAt(kSaveTick, kSaveTickHex)) {
        Log(0, "Save RetryOnLock: off - the save file open 0x%08lx / abort 0x%08lx / tick 0x%08lx do not match this "
               "tru.exe (or another plugin patched them)", kSaveOpenArgs, kSaveAbort, kSaveTick);
        return;
    }
    BYTE call[6] = {0xe8, 0, 0, 0, 0, 0x90};
    const DWORD rel = reinterpret_cast<DWORD>(&SaveCreateFile) - (kSaveOpenCall + 5);
    memcpy(call + 1, &rel, 4);
    if (!WriteCode(kSaveOpenCall, call, sizeof(call))) return;
    g_saveHooked = true;
    Log(1, "Save RetryOnLock: on - CreateFileW call 0x%08lx of the save / load file open 0x6db690 -> TruQoL: after a "
           "sharing / lock / access error up to %d retries %lu ms apart (only then; the first try is the game's own)",
        kSaveOpenCall, kSaveRetries, kSaveRetryMs);
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
    const int pauseBit = IniInt("Fixes", "FrontEndPauseBit", g_frontEndPauseBit, 0, 1);   // 0.1.4
    if (pauseBit != g_frontEndPauseBit) {
        g_frontEndPauseBit = pauseBit;
        Log(1, "live: [Fixes] FrontEndPauseBit %d -> %d (%s)%s", !pauseBit, pauseBit,
            pauseBit ? "a stale pause bit in the front end is cleared from the next paused frame"
                     : "the game's behaviour: a stale pause bit stays until the next level load",
            g_limitHooked && g_pauseBitOk ? "" : " - the clock call / pause code did not match: no effect in this run");
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
    g_threadCap = IniInt("Startup", "ThreadCap", 8, 0, 31);   // 0.1.3: default 8 (was 31; 25+ hang at the first load)
    g_skipIntro = IniInt("Startup", "SkipIntro", 0, 0, 1);
    g_frontEndPauseBit = IniInt("Fixes", "FrontEndPauseBit", 0, 0, 1);   // 0.1.4
    g_exitTrace = IniInt("Diag", "ExitTrace", 0, 0, 1);                   // 0.1.5 (restart; not in the shipped INI)
    g_saveRetry = IniInt("Save", "RetryOnLock", 0, 0, 1);                 // 0.1.6 (restart)
}

void Start(HMODULE self) {
    ModuleDir(self, g_dir, sizeof(g_dir));
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruQoL.log", g_dir);
    ReadOptions();
    Log(1, "%s loaded (enabled %d, log level %d; FrameLimit %d / %d fps / AutoOff %d, Fov %g / cutscenes %d, ShakeScale "
           "%g, ThreadCap %d, SkipIntro %d, FrontEndPauseBit %d, ExitTrace %d, RetryOnLock %d)", kVersion, g_enabled,
        g_logLevel, g_limitEnabled, g_maxFps, g_autoOff, g_fov, g_fovCutscenes, g_shakeScale, g_threadCap, g_skipIntro,
        g_frontEndPauseBit, g_exitTrace, g_saveRetry);
    if (!g_enabled) { Log(1, "disabled by TruQoL.ini ([TruQoL] Enabled=0) - nothing patched"); return; }
    const DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - nothing patched", base, kImageBase); return; }
    StartExitTrace();                        // 0.1.5: first, so the trace covers the rest of the start ([Diag] ExitTrace)
    StartThreadCap();                        // first: the CPU count runs in WinMain, soon after the plugins are loaded
    StartFrameLimit();
    StartCamera();
    StartSkipIntro();                        // 0.1.2: before WinMain, so no movie can be playing yet
    StartSaveRetry();                        // 0.1.6: [Save] RetryOnLock (restart)
    g_iniTimeOk = IniTime(&g_iniTime);       // 0.1.1: the live tick reads again only after a change of TruQoL.ini
    if (g_limitHooked)
        Log(1, "live: TruQoL.ini is read again at most once a second when it changes (LogLevel, FrameLimit Enabled / "
               "MaxFps / AutoOff / SpinUs, Camera Fov / FovCutscenes / ShakeScale, Fixes FrontEndPauseBit; restart: "
               "Enabled, ThreadCap, SkipIntro, Diag ExitTrace, Save RetryOnLock)");
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        XtDetach(reserved != nullptr);       // 0.1.5 ExitTrace (nothing while it is off)
    }
    return TRUE;
}

extern "C" __declspec(dllexport) const char *TruQoLVersion() {
    return "TruQoL 0.1.7 (player options: frame limiter at the game's frame clock 0x5da230, FOV factor at the render "
           "projection 0x5cb0a8, camera shake factor 0x5eb460, CPU thread cap for the start-up count 0x4a21d0, start-up "
           "intro skip at the script's PlayMovie call 0x77bc7b, stale front-end pause bit at the paused-branch clock "
           "call 0x5da684; live INI re-read once a second for TruMenu page Fixes; [Diag] ExitTrace (default off): "
           "first-chance exceptions + tru.exe's ExitProcess / TerminateProcess -> TruQoL.exit.log; [Save] RetryOnLock "
           "(default off): retry of the save / load CreateFileW 0x6db6d0 on a sharing / lock / access error; 0.1.7: "
           "dated log lines)";
}
