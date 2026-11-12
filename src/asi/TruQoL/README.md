# TruQoL.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld 1.1, unpacked) with **comfort options for
players**: a frame limiter, a field-of-view factor, a camera-shake factor (motion sickness) and the fix for the
start-up crash on PCs with more than 31 CPU threads; 0.1.2: an optional skip of the start-up intro movie; 0.1.4: an
optional fix for the half-speed main menu after "pause -> back to the main menu". TruMenu stays the debug tool; TruQoL holds only switches a player
wants, each with its own INI key (owner decision 2026-11-08). Defaults: **frame limiter on at 60 fps**, the camera
options neutral (= the game's behaviour), the thread cap on at 8 since 0.1.3 (it only acts on PCs with more threads;
31 was the old default - live on a 36-thread PC 25 and more hang at the first load).

**Status TruQoL 0.1.6 (2026-11-11, `work\asi\qol016`): new `[Save] RetryOnLock` (restart, default 0 = nothing
patched) - the save / load file open retries when another program (security scan, backup, sync) still holds the file - built, byte
checks and the patch site checked offline against `tru.exe`, not installed, not played (see "RetryOnLock" below).**
0.1.5 (2026-11-11, `work\asi\qol015`): new diagnosis `[Diag] ExitTrace` (restart, default 0 = nothing
installed; not in the shipped INI) for the rare silent end at start-up - built, checked offline with a test exe (not
with tru.exe), not installed, not played (see "ExitTrace" below).** 0.1.4 (2026-11-11, `work\asi\qol014`): new `[Fixes]
FrontEndPauseBit` (live, default 0 = the game's behaviour) - built and checked offline, not installed, not played (see
"FrontEndPauseBit" below). 0.1.3 (2026-11-09,
`work\asi\qol013`) changed only the ThreadCap default 31 -> 8; the 0.1.2 build
was installed and played 2026-11-08 (frame limiter, thread cap with 8 / 16 / 24 in the INI). 0.1 (`work\asi\qol01`) was
the first build; 0.1.1 (`work\asi\qol011`) reads the live keys again while the game runs (TruMenu page "Fixes", group
"Komfort (TruQoL)"); 0.1.2 adds `[Startup] SkipIntro` (skip the start-up intro movie, default off - see below).
Everything below is proven statically (disassembly of the installed `tru.exe`, md5 `5560abac...`, and `binkw32.dll`);
nothing is seen in game yet.

Install: `scripts\windows\Set-TruQoL.ps1 -Install -SourceDir work\asi\qol014` (check first with `-Check`, remove with
`-Remove` / `-Restore`). The Ultimate ASI Loader the game ships as `binkw32.dll` loads every `*.asi` next to `tru.exe`;
ModLoader.asi is just another plugin of that loader. Log: `TruQoL.log` next to `tru.exe`, one line per feature (on /
off / why).

## 0.1.7: dated log lines (Q107, 2026-11-12)

Built 2026-11-12 into `work\asi\i_1211\TruQoL`, not installed, not played. Only the log format changed (shared helper
`src\asi\TruLog.h`): every line of `TruQoL.log` starts with `YYYY-MM-DD HH:MM:SS.mmm`, each game process writes one
header line `=== <date time> TruQoL 0.1.7 session start (pid n) ===` before its first line, and the two line kinds of
`TruQoL.exit.log` that had only the time (`[Diag] ExitTrace=1`) now carry the date as well. Options and patches are as
in 0.1.6 (same sample .ini). Install: `scripts\windows\Set-TruQoL.ps1 -Install -SourceDir work\asi\i_1211\TruQoL`
(dry run first: add `-Check`).

| # | TO TEST 0.1.7 | expected |
|---|---|---|
| 1 | start the game once with 0.1.7 installed, read `TruQoL.log` from its last `session start` line on | header and `loaded` line name 0.1.7; every newer line starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start |

## INI reference (`TruQoL.ini`)

| Section | Key | Default | Range | When (0.1.1) | Meaning |
|---|---|---|---|---|---|
| `[TruQoL]` | `Enabled` | 1 | 0 / 1 | restart | 0 = load but patch nothing (so there is nothing to switch live) |
| `[TruQoL]` | `LogLevel` | 1 | 0 .. 2 | live | 0 errors, 1 one line per feature, 2 also a frame-rate line every 10 s |
| `[FrameLimit]` | `Enabled` | 1 | 0 / 1 | live | cap the frame rate (physics / cubes misbehave above 60 fps; GOG ships a 60 fps cap since 2025) |
| `[FrameLimit]` | `MaxFps` | 60 | 20 .. 500 | live | frames per second (a change starts a new frame cadence) |
| `[FrameLimit]` | `AutoOff` | 1 | 0 / 1 | live | 1 = off by itself when DXVK or dxwrapper already limits (see below); 0 = keep it anyway |
| `[FrameLimit]` | `SpinUs` | 0 | 0 .. 5000 | live | advanced: microseconds before a frame waited in a pause loop (0 = 600 with a high-resolution timer, 2000 without) |
| `[Camera]` | `Fov` | 0 | 0, 0.5 .. 2.0 | live | **factor** on the game's vertical field of view; 0 or 1 = the game's, 1.15 = 15 % wider |
| `[Camera]` | `FovCutscenes` | 0 | 0 / 1 | live | 0 = only the gameplay camera, cutscenes keep their framing; 1 = every camera |
| `[Camera]` | `ShakeScale` | 1.0 | 0 .. 1.0 | live | camera shake strength: 1.0 = the game's, 0 = no camera shakes |
| `[Startup]` | `ThreadCap` | 8 | 0 .. 31 | restart | the game's CPU count sees at most this many threads (only when the PC has more); 0 = off - acts once, before WinMain. 0.1.3: default 8 (was 31) - live on a 36-thread PC 8 / 16 / 24 work, 25 and more hang at the first load (worker pool, ENGINE.md 3), more threads gave no faster loading |
| `[Startup]` | `SkipIntro` | 0 | 0 / 1 | restart | 0.1.2: 1 = skip the start-up intro movie (only before the "press start" screen, never in a level; the legal screens stay); patched once at the start |
| `[Fixes]` | `FrontEndPauseBit` | 0 | 0 / 1 | live | 0.1.4: 1 = clear the pause bit the front end keeps after "pause -> back to the main menu" (main-menu clocks, e.g. the teaser timer, then run in real time instead of half speed); only in the front end and only while no pause is open - the pause in a level is untouched. 0 = the game's behaviour (the bit stays until the next level load) |

| `[Save]` | `RetryOnLock` | 0 | 0 / 1 | restart | 0.1.6: 1 = when the save / load file cannot be opened because another program holds it (sharing / lock / access error), try again up to 10 times 100 ms apart (only then; at most about 1 s); 0 = the game's one try (a failed save write deletes the slot's file) |
| `[Diag]` | `ExitTrace` | 0 | 0 / 1 | restart | 0.1.5: 1 = write `TruQoL.exit.log` (first-chance exceptions, tru.exe's own `ExitProcess` / `TerminateProcess`, the DLL detach) - a diagnosis, see "ExitTrace" below. **Not in the shipped `TruQoL.ini`** (every key there needs a TruMenu switches row, which TruMenu's owner adds): add `[Diag]` / `ExitTrace=1` by hand |

Invalid values are logged and replaced by the default (at the start) or keep the current value (live). Every engine
address is byte-checked before it is patched; on a mismatch that feature stays off and the log says why.

## Live keys (0.1.1)

TruMenu's page "Fixes" (`TruMenu.switches.txt`, group `truqol` "Komfort (TruQoL)") writes `TruQoL.ini` with
`WritePrivateProfileString`. TruQoL reads the live keys again in `LiveTick`: on the **game thread**, from `ClockStub`
(the clock calls of the frame-time function 0x5da230, once per frame in every main state), **at most once a second**
and only when the **last-write time** of `TruQoL.ini` changed (cheap file-time check first, as TruMercLang's
`PollIni`). The time is kept only if it did not change during the read (a write that met the read is read again a
second later). Each read passes the current value as its default (a missing key keeps it, an invalid one is logged and
keeps it); **one log line per change** (`live: [Section] Key old -> new ...`).

| Key | How a live change acts (hook sites unchanged from 0.1) |
|---|---|
| `[FrameLimit] Enabled` / `MaxFps` / `SpinUs` | the clock calls 0x5da247 / 0x5da684 are patched **once at the start** whenever TruQoL is enabled and the bytes match - also with `Enabled=0` (then `ClockStub` only runs the tick and jumps to the game's clock 0x597f10). The wait is gated per frame (`LimitActive`); a switch-on or a new `MaxFps` starts a new cadence (no wait for an old slot) |
| `[FrameLimit] AutoOff` | the DXVK / dxwrapper detection now runs once whatever `AutoOff` says (read only, when `d3d9.dll` is loaded - once per process) and keeps its result; `AutoOff` decides per frame whether that result stops the wait |
| `[Camera] Fov` / `FovCutscenes` | the FOV call 0x5cb0a8 is patched **once at the start** whenever its code matches (also `Fov=0`); `FovHook` returns the game's value while the factor is 0 or 1. Not patched at run time: it is render code and its thread is not proven |
| `[Camera] ShakeScale` | the 0.1 rule kept live: TruQoL owns the shake calls 0x5eea55 / 0x5eb56d **only while ShakeScale < 1.0**. A change to < 1.0 points both to `ShakeStub` - only while both still call the game's 0x5eb460 (TruMenu's `cam.shakescale` below 100 % holds them: refused with one line, tried again at the next change of the key); a change to 1.0 puts the game's target back (only while both still call `ShakeStub`) and TruMenu's slider may take them again (move it once more: TruMenu retries only after a change). These two rel32 writes run on the game thread, as TruMenu's own run-time patch of the same two sites (`M21PatchGroup` from its pad hook) and TruShadowCombat's `[Damage] Translate` switch |
| `[TruQoL] LogLevel` | the next line uses the new level; the change line itself is always written |
| `[Fixes] FrontEndPauseBit` (0.1.4) | no code is written at run time: the paused-branch clock call 0x5da684 goes to `PauseClockStub` from the start (together with the frame-limiter hook); the key is a flag that `PauseBitCheck` reads at every paused frame |
| `[TruQoL] Enabled`, `[Startup] ThreadCap`, `[Startup] SkipIntro` (0.1.2), `[Save] RetryOnLock` (0.1.6) | **restart**: `Enabled=0` patches nothing (no tick); the CPU count runs once in WinMain; the intro plays once, right after the start, so the movie call is patched in DllMain or not at all; the save open call is patched in DllMain or not at all |

Without the clock hook (bytes differ, another plugin owns the calls) there is no tick: every key takes effect at the
next start (logged once).

## How each feature works (evidence)

| Feature | Hook point (absolute VA) | What the game does there | Proof |
|---|---|---|---|
| FrameLimit | rel32 of `call 0x597f10` at **0x5da247** (running) and **0x5da684** (paused branch) in the frame-time function **0x5da230** | 0x597f10 = microsecond clock (QueryPerformanceCounter 0x597e90, monotonic sum 0xcdb4d8); 0x5da230 averages the last six frame deltas (ring 0xe7ee10, index 0xe7edc4), clamps to 66 666 us (0x5da455) and stores dt = us / 33 333.33 (double 0x855280) to 0xe7f190 / 0xe7f194 (1.0 = one 30 fps frame), x time scales to 0xe7f188 | 7 callers of 0x5da230, one per main-state handler (0x4a13f2, 0x5daab8, 0x5daceb, 0x5dae56, 0x5dde91, 0x5e003a, 0x5e012e); the clock has only these two callers in 0x5da230 (third: 0x597f70, another timer) |
| FrameLimit auto-off | at the first frame after `d3d9.dll` is loaded (the game loads it itself, no static import) | DXVK: the module image of `d3d9.dll` / `dxgi.dll` names `DXVK_CONFIG_FILE` / `dxvk.conf`; then `DXVK_FRAME_RATE`, `d3d9.maxFrameRate` in `dxvk.conf` (or `DXVK_CONFIG_FILE`), else DXVK's tru.exe profile `d3d9.maxFrameRate = -60` -> off unless the value is 0. dxwrapper: `dxwrapper.dll` loaded or `d3d9.dll` names dxwrapper; `LimitPerFrameFPS` > 0 in `dxwrapper.ini` -> off | DXVK profile: `docs\Recherche-QoL-Beschwerden-0811.md` (DXVK `config.cpp`, read 08.11.); markers not tested against real DXVK / dxwrapper files (none on this PC) - 🔶 |
| Fov | rel32 of `call 0x5e78d0` at **0x5cb0a8** (render projection only) | 0x5e78d0 = FOV getter: `[0xe8eec0]` while the snapshot byte `[0xe8eec8]` is set (0x5e7780), else the current camera `[0xe80534]` vtable +0x40 (base 0x5e1c90 = `fld [ecx+0xb0]`); 0x5cb0a8 stores the scene FOV 0xe49700, whose only reader 0x5ce949 passes it to the perspective 0x5129d0(out, fov, aspect, near, far) | 0x5129d0: `fov x 0.5` (double 0x8413c0), `call 0x813870` (= `fptan`), m00 = 1 / (aspect x tan), m11 = 1 / tan -> **vertical FOV in radians**; aspect 0xe49704 = `[[0xad75e4]+0x170]` / 10000 (the AspectRatio registry value) |
| Fov (gameplay only) | `[0xe80534]` (= manager 0xe804f0 + 0x44) == `[0xe81070]` (= manager + 0xb80) | the gameplay camera; cutscene cameras differ (TruMenu live 06.11.: gameplay 0x00e83860, prologue cutscene 0x00e80de0) | about 25 sites write camera +0xb0 every frame (cinematic keys 0x5e338b / 0x5e348d, interpolations), so a factor keeps the game's own zooms; the other getter callers 0x6b134a / 0x6e4ce4 keep the game's value |
| ShakeScale | rel32 of `call 0x5eb460` at **0x5eea55** (camera apply) and **0x5eb56d** (shake sum) | 0x5eb460 = shake strength (esi = slot of the pool 0xe80020, result st0); the stub calls it and multiplies st0 | the only two callers; the same sites as TruMenu `cam.shakescale` (ENGINE.md section 22) |
| ThreadCap | **0x4a2238** `call [0x83e0a8]` (GetProcessAffinityMask, its only use in tru.exe) -> `call CappedAffinity; nop` | CPU topology count **0x4a21d0**: unequal process / system mask -> returns 8 at once (0x4a2244, why `start /affinity FFFF` helps); else for mask = 1 << i while mask <= system mask: SetThreadAffinityMask, APIC ids into 256-byte stack arrays; step 0x4a2455 `shl eax, cl` shifts modulo 32 -> with bit 31 set (>= 32 threads; a 32-bit process sees 0xffffffff) the loop never ends and **0x4a235d** `mov [ebp+edi+0x284], al` writes past the array (0xc0000409, `tru+0xa235d` in `scripts\windows\README.md`) | both masks are capped to `(1 << ThreadCap) - 1` only when the system mask has a higher bit, so the loop ends at bit ThreadCap; after the count WinMain pins the main thread to CPU 0 (0x47a0c9), so the capped mask the count restores (0x4a2477) does not last |
| ThreadCap: early enough? | DllMain of TruQoL | the count runs once: WinMain 0x479c80 -> 0x47a0bb -> 0x4a28e0 -> 0x4a2904 -> 0x4a21d0. The CRT start 0x818241 calls GetStartupInfoA at **0x818255** before it calls WinMain at 0x8183b3 (-> 0x47a280 -> 0x479c80). `binkw32.dll` = Ultimate ASI Loader: `dontloadfromdllmain` defaults to 1 (`mov edx, 1` at 0x1001ade8 before the key), then 0x1001a570 hooks the exe's imports GetStartupInfoA/W, GetModuleHandle, GetProcAddress, ... and loads the plugins at the first such call; no loader `.ini` in the game folder | the plugins (and TruQoL's patch) are in place before WinMain - **implemented**; the launcher work-around stays documented for ThreadCap=0 |

## SkipIntro (0.1.2): how the script learns that a movie ended

Question of package 18b: does the front-end script wait for a "movie finished" signal, so that an early return must
fake it? Answer (static, `work\skip18c_0811`): **no signal exists - the movie call is synchronous.** The script's
native returns only when the movie is over, so a native that returns at once is, for the script, a movie that ended at
once. TruQoL returns exactly as the game does for a movie file that cannot be opened.

| What | Address | Proof | St |
|---|---|---|---|
| Script native PlayMovie | uigamedata f21 **0x7a0cf0** (binder 0x7af0c0 `push 0x7a0cf0; push 0x15` at 0x7af1f3) | `mov eax, [esp+0xc]; push eax; call 0x77bc60; pop ecx; ret` - no write to the result pointer `[esp+0x10]` (natives with a result write it, e.g. f13 GetFrontEndState 0x7a0c40) | ✅ static |
| PlayMovie | **0x77bc60** (only caller 0x7a0cf5; no other reference) | name pointer != 0 -> 0x6457a0 (= `ret`, a log stub), 0x5f6420 (= `mov eax, 1; ret`), **`call 0x4a12b0` at 0x77bc7b** (name, loop 0), `add esp, 0xc`, tail jump to the log stub: the player's result is dropped | ✅ static |
| Video player | **0x4a12b0** (name, loop) | entry writes stop byte 0xa039b8 = 0, loop byte 0xa039dc, pause byte 0xa039dd = 0; open 0x4a0c70 (4:3 name variant, then the plain name via 0x4a0b00) -> **cannot open: return 0 at 0x4a12df**; else its OWN frame loop 0x4a13c0 .. 0x4a14fb (frame time 0x5da230, UI 0x5cebc0 / 0x5c5a30, BinkDoFrame / BinkNextFrame) until the last frame (0x4a0ae0: handle +0xc == +0x8, not looping), the stop byte (f22 0x4a0f10 sets 1), a skip press (ebp = 1, 0x4a1492 .. 0x4a14cf) or a lost device (0x47afd0); then BinkClose (0x83e404), handle 0xa039bc = 0, result 1 / 0 | ✅ static |
| Who else reads the movie state | 0xa039bc, 0x4a0ae0, 0xa039dc, 0xa039dd | every use lies inside the video code 0x4a0a00 .. 0x4a15ff (tools/pe_abs_uses.py): nothing outside polls "movie playing / finished" | ✅ static |
| Code-played movies (untouched) | 0x5d5554 (attract list 0x8abef4 = "intro", state 6 -> 7, then 2), 0x5daf3e (states 2 / 3: menu loop [0x8abf20] = "medsea_loop", loop 1), 0x5db008 (state 8: "explode"), 0x5d6b39 / 0x5dab0f (queue 0xe7ece0, extras / level) | they call 0x4a12b0 directly, not through 0x77bc7b | ✅ static |
| Front-end state 1 | handler 0x5dae86 in 0x5dae20 | `push ecx; call 0x6457a0; push 2; call 0x77bbc0`: the code moves IntroMovie -> PressStart by itself; state 0 is not in the code switch (0x5dae7f: index state - 1, 8 cases), i.e. the script runs the legal screens | ✅ static |
| Movies on disk | `Movies\` of the game: intro, medsea_loop, credits, credits_DLC1, explode, prevontr (.bik) | no logo / legal movie -> the legal screens are no movie and are **not** skipped (setting the state from outside does not stop the script's own screen timer - not proven safe) | ✅ (file list) |

The hook: the rel32 of `call 0x4a12b0` at **0x77bc7b** -> `MovieHook(name, loop)` (patched once in DllMain, only with
`SkipIntro=1`, after a byte check of PlayMovie, the player's entry, the native, its binder entry, the front-end getter
and the state-1 handler; the call must still go to 0x4a12b0). `MovieHook` skips only while **all** hold: front-end
state `[0xfae8da]` is 0 or 1, main state `[0xe7ed60]` is not 1 / 2 / 9 (level, level load, outfit selection) and
state 2 or higher was never seen in this run (latch, checked at each movie call and once per frame in the clock hook).
A skip writes the player's three entry bytes as the player would and returns 0 - the game's "cannot open" path. Every
other call goes to 0x4a12b0 unchanged. Log: one line per skipped movie with its name and both states, one line when the
latch closes.

Why default 0: everything above is static; the intro movie has not been skipped in the game yet (TO TEST 12). Open
points it may show: whether the script plays the intro in state 0 or 1 (both are covered), whether the main state at
that time is one of 1 / 2 / 9 (then nothing is skipped and the log says why), and whether the front end loads
something behind the intro (then "press start" comes a little later, as with a missing intro.bik).

Coexistence: TruQoL hooks no D3D9 function (TruMenu's Present / Reset hook, TRAWindowed / DXVK / dxwrapper as
`d3d9.dll` are not touched). TruShadowPower checks 0x5da3f4 / 0x5da40c and TruMenu 0x5da40c in the same function; TruQoL
changes only the two clock calls. With `ShakeScale` below 1.0 TruQoL owns the two shake calls and TruMenu's
`cam.shakescale` is refused (TruMenu logs "another plugin?"); with 1.0 TruQoL leaves them to the game (0.1.1: also when
the value changes live, see "Live keys"). TruMenu `camera.fov` writes camera +0xb0; TruQoL's factor applies on top.
Every redirect is made only when the call still goes to the game's function.

Not done: an INI value in degrees (the game's base FOV is camera tuning data, not a constant in the exe; read it with
TruMenu `camera.fov` in the gameplay camera to translate a degree wish into a factor), a hot-key. The TruMenu page came
with 0.1.1 (TruMenu.switches.txt, group "Komfort (TruQoL)").

## FrontEndPauseBit (0.1.4): the stale pause bit in the front end

The finding (`docs\Befund-Skript-Uhr-halbe-Zeit-1111.md` in the workspace, commit 9787ea5, ENGINE.md row "Script clock
time step / stale pause bit"): the in-game pause sets bit **0x10000000** of **`[0xe7f0b4]`**; while it is set the
frame-time function 0x5da230 takes its paused branch and stores a **fixed 0.5** as the frame time `[0xe7f188]`. The
level exit does not clear the bit, so after "pause -> back to the main menu" the front end keeps it and every script
clock in the main menu runs at half speed (the main menu's Bink loop runs at 29.97 Hz: 0.5 / 30 s per loop; the
teaser came after ~81 s instead of 40 s). Live 2026-11-10 (TruLink): in a level with the pause open `[0xe7f0b4]` has
0x10000000, `[0xe7f188]` = 0.5, main state 1; then in the main menu `[0xe7f0b4]` = 0x50000000, `[0xe7f188]` = 0.5,
main state `[0xe7ed60]` = 10. The same code is on the Xbox (retail and TU) - an original quirk, not our port.

| What | Address | Proof | St |
|---|---|---|---|
| Hook | rel32 of the clock call **0x5da684** (already redirected since 0.1) -> `PauseClockStub` = `PauseBitCheck`, then exactly `ClockStub` (wait + the game's clock 0x597f10). The running-branch call 0x5da247 keeps `ClockStub` | the call lies only in the paused branch: 0x5da233 `test [0xe7f0b4], 0x10000000` -> 0x5da240 `jne 0x5da621` is the only way into 0x5da621, 0x5da628 the only jump to 0x5da664, the branch has no call / jump / ret before 0x5da684, and no rel32 branch elsewhere in `.text` lands in it. So `PauseBitCheck` runs only in frames that see the bit; it is the 0.1 hook site, no new code patch | ✅ static |
| The bit | set only at **0x5d47bb** / **0x5d482b** (pause 0x5d4780 / 0x5d4810, both `or [0xe7f0b4], 0x10000000`); cleared by `and` only at **0x5d4752** (unpause 0x5d4700) and by the reset 0x5d3e74 (`mov [0xe7f0b4], ebx`, ebx = 0, level load); the level exit 0x5dab40 clears only bit 0x10 (**0x5dab9e**) | every instruction with the memory operand `[0xe7f0b4]` decoded (`work\qol_pausebit_1111\check_qol014.py` section pausebit): the register writers are 0x5d3e74 (ebx = 0 from 0x5d3df6), 0x5ddf57 (esi = 0x40000000 from 0x5ddf2f), 0x5df878 (eax = 1); no byte access to 0xe7f0b5..0xe7f0b7 | ✅ static |
| Who reads the bit | **0x5da233** (frame time) and **0x5bf861** (render time step: `[0xe7f194]` / 60 instead of `[0xe7f188]` / 30) | the only `test` with 0x10000000; the two whole-dword loads 0x5d4877 / 0x5d4a00 (pause control 0x5d4870, called only from 0x5dfc44) test 0x80, 0x40000000, 0x20000000 | ✅ static |
| The pause byte | **`[0xe7f143]`** = 6 is written only at **0x5d47a7** / **0x5d481a**, each a few instructions before the bit is set in the same function; the other 9 writers store 0 (unpause 0x5d475e, level exit **0x5dac6e** `mov [0xe7f143], bl` with bl = 0 from 0x5dab46, 0x5d7538, 0x5d756c, 0x5df883, 0x5dfbc9, 0x77c2a3), 4 (0x5d757f) or 0xa (0x5da941) | every instruction with the memory operand `[0xe7f143]` decoded; the pause menu itself decides by the same byte (0x78bb13 / 0x78bb28 `cmp [0xe7f143], 6`) | ✅ static |
| Front end | main state `[0xe7ed60]` 6 or 10 | the rule of `uigamedata` f37 **0x5d56e0** (`cmp eax, 6; je; cmp eax, 0xa; je` -> 1) | ✅ static |
| What a clear does | the next frame takes the running branch with `[0xe7f384]` = 1 (written by the paused branch at 0x5da66a): the game's own "first frame after the pause" step (0x5da4e8: saved values 0x8abea4.. back, time dilation 0xe7f1d8 -> 0xe7f1d4), then 0x5da538 clears `[0xe7f384]` - the same path as after a real unpause; the frame time is measured again | listing 0x5da230 (`work\clockhalf_1111\frametime_5da230.txt`) | ✅ static |
| Not done | the other steps of the unpause 0x5d4700 (object manager 0x5785a0, 0x5bfdf0(0), `[0xe7f094]+0x14` bit 0x100) are not run - they belong to the level that is gone; bit 0x40000000 (the pause menu's unpause request, also left in the main menu: 0x50000000) is not touched | the original leaves both as they are, too | - |

**The rule** (`PauseBitCheck`, game thread, only in the paused branch): switch on **and** the start checks matched
**and** main state 6 / 10 **and** pause byte != 6 **and** the bit set -> `lock and [0xe7f0b4], ~0x10000000`. Why the
pause byte: 6 means a pause the game holds open (written only together with the bit; every other writer ends the
pause state) - then the bit stays and one line says so (once per run). In a level (main state 1) nothing is ever
touched, so the pause menu in a level still freezes the game. Byte checks at the start (`StartPauseBit`, after the
clock hook; a mismatch = the feature stays off with one log line): the paused branch 0x5da664 (0.5 from 0x8413a8,
`[0xe7f384]` = 1, store to `[0xe7f188]`), the float 0.5 at 0x8413a8, both pause functions (0x5d47a7 / 0x5d481a ..
the bit set), the unpause 0x5d4752, the level exit 0x5dab9e / 0x5dac6e, f37 0x5d56e0 and the render-step reader
0x5bf861; the clock call 0x5da684 itself is checked by the frame limiter's checks (bytes + target 0x597f10). Log
(LogLevel 1): one line per clear with the main state, the pause byte and the flags before / after; at most one line
per 10 s (clears in between are counted in the next line). Nothing else is written; no code is patched at run time.

Why default 0: proven statically and the cause seen live, but the fix itself has not run in the game yet (TO TEST
13).

## ExitTrace (0.1.5): what ended the game?

Live 2026-11-10 20:45:39-44 the game ended about 4-10 s after the start (during the start-up intro): every plugin log
stops, no WER dump although `LocalDumps\tru.exe` is set (DumpType 2, DumpCount 3; the three dumps in the default
dump folder are from 20:01-20:04), no Application event (an unhandled exception normally leaves Application
Error 1000); the next start worked (workspace `docs\Befund-FMOD-Startabsturz-1111.md`). Without an exception that
reached WER the process ended through an exit call or from outside. `[Diag] ExitTrace=1` (restart) tells these apart
next time, in its own file `TruQoL.exit.log` (TruQoL.log is opened per line with `fopen_s`, which refuses a second
writer):

| Line | Written by | Means |
|---|---|---|
| `=== <date time> TruQoL 0.1.5 ExitTrace: pid, main thread, ... WER LocalDumps ...` | DllMain | session start (full date: the file is appended over days) |
| `first-chance exception 0xC... at <address> ...; thread ...` | vectored handler, registered first, returns `EXCEPTION_CONTINUE_SEARCH` | an exception with an error code was raised (it may still be caught - other plugins probe memory with `__try`); first 24 in full, then at most one line per second; the last one is repeated in the exit / detach line |
| `module (start / new / at exit): <name> base size` | a thread every 2 s for 60 s, and the ExitProcess hook | names for the allocation bases in the exception lines |
| `exit: ExitProcess(...)` / `exit: TerminateProcess(...) called from <address> = <site>` | tru.exe's import slots 0x83e054 / 0x83e058 (chained) | the game's own exit paths: 0x478aec / 0x478a66 fatal-error path 0x596cb0 (dialog, then exit; on another thread with the main thread suspended), 0x479690 SKUType check, 0x59a0f1 address-space message box, 0x816a00 CRT exit, 0x81d740 CRT /GS failure, 0x81e3c7 CRT invalid parameter |
| `detach: process exit` | DLL_PROCESS_DETACH | some module called ExitProcess (also one that does not go through tru.exe's import slot) |
| nothing after the last line | - | TerminateProcess by another module or from outside (TruMenu's `game.quit` writes its own line in TruMenu.log) |

The handler and the exit / detach lines use no heap, no CRT and no lock (own formatter, `WriteFile`, `GetLocalTime`,
`VirtualQuery`): they can run inside a heap or loader fault, on an overflowed stack, or while ExitProcess has already
ended the other threads. Nothing of it changes what the game does; with `ExitTrace=0` nothing is installed. Offline
check: `work\q22_fmod_1111\xt_harness.ps1` (a test exe at base 0x400000 loads the built TruQoL.asi with `ExitTrace=1`:
header, exception lines incl. the per-second limit after 24, module lines, detach line with the last exception;
tru.exe's slots are outside the test exe, so the log says "not hooked" there - the hook itself is untested).

## RetryOnLock (0.1.6): saving fails while another program holds the file

Players report that saving fails with security software running (Steam guide "Definitive Improvement Guide"; workspace doc
`docs\Befund-PC-Technik-Q69-1111.md`). Static reading of `tru.exe` (Q69):

| What | Address | Proof | St |
|---|---|---|---|
| File open of the save / load state machine | **0x6db690** (thiscall (path, write)) | write: `CreateFileW(path, GENERIC_WRITE, 0 = no sharing, -, CREATE_ALWAYS, FILE_FLAG_OVERLAPPED)`; read: `(GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, 0)`; both branches reach the one call **0x6db6d0** `call [0x83e0c4]`; failure -> status +0x24 = 2 | ✅ static |
| Writer tick | **0x6db810** (via 0x6dc140, called by the save menu code 0x78ab60 ..) | status 2 .. 5 -> step 2 = abort **0x6db956**: CloseHandle, `DeleteFileW(path)` when the status is not 0, result +0x1c = 3. Steps 3 .. 8: open, header / blocks by overlapped `WriteFile` (ERROR_IO_PENDING 0x3e5 accepted), `GetOverlappedResult` polled (0x3e4 = not yet) | ✅ static |
| Retry / temporary file | - | none: one open per save, the slot file is truncated in place (CREATE_ALWAYS) - a failed write leaves no old save | ✅ static |

The hook: `call [0x83e0c4]` (6 bytes) at 0x6db6d0 -> `call SaveCreateFile; nop` (patched once at the start, only with
`RetryOnLock=1`, after byte checks of the argument block 0x6db6a9 .. 0x6db6e3, the abort 0x6db956 and the tick 0x6db810;
`tools/pe_patch_site_check.py`: one whole instruction, the only branch to it is the `jmp` of the write branch to its
start). `SaveCreateFile` calls what the import slot 0x83e0c4 holds at that moment (chained: a loader that hooks
CreateFileW stays in the path). Only when that returns INVALID_HANDLE_VALUE with ERROR_SHARING_VIOLATION (32),
ERROR_LOCK_VIOLATION (33) or ERROR_ACCESS_DENIED (5) it sleeps 100 ms and tries again, at most 10 times; any other error
(e.g. no save file yet on a load) goes back at once. One log line per retried open: file name, read / write, the
first error, the result. The wait runs on the thread that ticks the save (the save menu), at most about 1 s, only in
that error case. Not done (plan): writing to a temporary file and renaming it over the slot (keeps the old save when a
write fails); the abort's `DeleteFileW` stays the game's.

Why default 0: proven statically; a locked save file has not been reproduced in the game yet (TO TEST 15).

## TO TEST

1. Install with `Set-TruQoL.ps1 -Install -SourceDir work\asi\qol014`; start the game (affinity work-around still in the
   launch options for the first run); `TruQoL.log`: the loaded line (`TruQoL 0.1.4`), `Startup ThreadCap: on, 8`,
   `FrameLimit: on, 60 fps`, `Fixes FrontEndPauseBit: off ... pass-through`, `Camera Fov: off ... pass-through`,
   `Camera ShakeScale: off`, `Startup SkipIntro: off`,
   `live: TruQoL.ini is read
   again ...`, then `FrameLimit: d3d9.dll = ...TRAWindowed...` (TRAWindowed installed) and `Startup ThreadCap: CPU count
   1 - ... unchanged` (fewer than 32 threads here).
2. Frame rate: `LogLevel=2`; in a level and in the main menu about 60 fps in the 10 s lines (`waited ... ms per frame`
   > 0 on a fast PC); no stutter; the game speed is normal (dt about 0.5 in 30 fps units). `MaxFps=30`: 30 fps.
3. Cubes / physics objects and the camera behave as at 60 fps with VSync; loading screens not noticeably slower than
   with `[FrameLimit] Enabled=0`.
4. CPU load of the game's main thread with the limiter (Task Manager per core): no core at 100 % from waiting.
5. Pause menu (paused branch 0x5da684) also at 60 fps; alt-tab and back: no catch-up burst.
6. `Fov=1.2`: in gameplay wider; aiming and cutscenes unchanged with `FovCutscenes=0`; with `FovCutscenes=1`
   cutscenes wider too; edges of the screen: objects do not pop in late (culling); the log line "first scaled frame"
   shows the game's base value in degrees (please note it).
7. `ShakeScale=0`: explosions / heavy landings / quake scenes without camera shake; `0.5` half; TruMenu with its own
   `[Camera] ShakeScale` 100: no conflict line in TruMenu.log as long as it is not moved.
8. Only on a PC with 32+ threads (or a VM with 32 vCPUs): start without the affinity option; the log shows the masks
   capped and the game starts. `ThreadCap=0` there: the known crash comes back (proves the cause).
9. With DXVK as `d3d9.dll` (instead of TRAWindowed): log line `auto-off - d3d9.dll is DXVK`; with `dxvk.conf`
   `d3d9.maxFrameRate = 0`: TruQoL stays on. With dxwrapper (`LimitPerFrameFPS = 60`): auto-off.

10. Live (0.1.1, TruMenu page Fixes, group "Komfort (TruQoL)", or an editor on `TruQoL.ini`), each within about a
    second, one `live:` line each in `TruQoL.log`: `MaxFps` 60 -> 30 -> 60 (LogLevel 2 lines follow); `[FrameLimit]
    Enabled` 1 -> 0 -> 1 (the frame rate free and capped again, no burst); `Fov` 0 -> 1.2 -> 0 (wider / back) and
    `FovCutscenes`; `LogLevel` 1 -> 2 (10 s lines start). `ShakeScale` 1.0 -> 0.5 -> 0 -> 1.0: the line names the shake
    calls -> TruQoL, then back to the game's; with TruMenu's shake slider at 50 % first, `ShakeScale` 0.5 is refused
    (line names the foreign target); slider back to 100 %, `ShakeScale` 0.25: patched. After `ShakeScale` 1.0 TruMenu's
    slider works again (move it once). `[TruQoL] Enabled` / `ThreadCap` in the page show "Neustart" and do nothing live.
11. With DXVK as `d3d9.dll`: `AutoOff` 1 -> 0 -> 1 live: TruQoL's limiter waits as well / stops again.
12. SkipIntro (0.1.2): first with `SkipIntro=0`: the log has `Startup SkipIntro: off`, the intro plays as before. Then
    `SkipIntro=1` (TruMenu page Fixes shows "Neustart"; restart the game): log `Startup SkipIntro: on`, then `SkipIntro:
    movie 'intro' skipped (front-end state 1 = IntroMovie, main state N)` (note N and the name) and `front-end state 2
    reached`; the legal screens still show, then "press start" without the intro, the menu background movie
    (medsea_loop) runs; music / sound normal; New Game and Load work. Back to the main menu from a level and wait for the
    attract mode: the attract "intro" plays (not skipped). If instead a line says `played - ... main state N`, the gate
    was too strict (report N).
13. FrontEndPauseBit (0.1.4): install `work\asi\qol014`; log `Fixes FrontEndPauseBit: off - ... pass-through`. TruMenu
    0.22.21 "Teaser-Uhr anzeigen" on (page Spiel-Einstellungen, group "Hauptmenü"). a) `FrontEndPauseBit=0` first:
    load a level, pause, "back to the main menu": the teaser line counts about half as fast as a watch (teaser after
    ~81 s), TruLink `read32 0xe7f0b4` has 0x10000000. b) `FrontEndPauseBit=1` (TruMenu page Fixes, group "Komfort
    (TruQoL)", live): within a second one line `stale pause bit cleared in the front end (main state 10, pause byte 0,
    [0x00e7f0b4] 0x50000000 -> 0x40000000)`; from then the teaser timer runs in real time (40 s alarm after 40 s on a
    watch, the line `Teaser-Uhr 40.0 / 40.0 s` at the same moment), `readf 0xe7f188` about 1.0 instead of 0.500; the
    menu animations, the menu music and the background movie normal. c) The same path again with the switch already
    on: one clear line right after the main menu appears. d) In-level pause with the switch on: the pause menu still
    freezes the game (Lara, enemies, water stand still; `[0xe7f188]` = 0.5 and the bit stays while it is open; no
    clear line while in the level); unpause and play on normally. e) Fresh start without a level: no clear line at
    all (the bit is never set). Note any line `pause byte ... = 6 - a pause the game holds open` (main state and when).
14. ExitTrace (0.1.5): install `work\asi\qol015`, add `[Diag]` / `ExitTrace=1` to `TruQoL.ini`, start. `TruQoL.log`:
    `Diag ExitTrace: tru.exe import slot 0x0083e054 ExitProcess held ... (...KERNEL32.DLL, kernel32's own) -> TruQoL`
    (and the same for 0x0083e058) and `Diag ExitTrace: on - ... (7 of 7 exit sites named)`. `TruQoL.exit.log`: the
    header with today's date, module lines; then quit through the game's own menu: an `exit: ExitProcess(...) called
    from ... = ...` line (note which site) and a `detach: process exit` line. Note the `first-chance exception` lines of
    a normal start (other plugins' probes) as the baseline. Start and play as usual: no slower start, nothing else
    changes. After a silent end: keep `TruQoL.exit.log` and report its last lines.
15. RetryOnLock (0.1.6): install `work\asi\qol016`. a) `RetryOnLock=0`: log `Save RetryOnLock: off`; save and load as
    usual. b) `RetryOnLock=1` (restart): log `Save RetryOnLock: on - CreateFileW call 0x006db6d0 ...`; save and load as
    usual - no extra line (no retry needed). c) Provoke a lock: in the save folder hold the slot file open without
    sharing (PowerShell: `$f = [IO.File]::Open('<slot file>', 'Open', 'ReadWrite', 'None')`), save to that slot, close
    the handle (`$f.Close()`) within about 1 s: one line `'savegameNN.sav' (write) - CreateFileW error 32 at the first
    try, opened after N retries` and the save works; keep it open longer: `... still 32 after 10 retries - the game's
    own failure path` and the game's save error as before. With `RetryOnLock=0` the same lock fails at once (baseline).

## Files

`TruQoL.cpp` (source; the comment block at the top holds the evidence in short), `TruQoL.ini` (sample with the
defaults), build: `scripts\windows\Build-TruAsi.ps1 -Name TruQoL -OutDir <repo>\work\asi\qol016` (0.1.6; the
0.1.5 build is `work\asi\qol015`, 0.1.4 `work\asi\qol014`). 0.1.5 ExitTrace: `work\q22_fmod_1111\xt_harness.ps1` (see "ExitTrace"). Offline checks:
`work\qol17x_0811\check_qol01.py` (0.1: bytes, call targets, the start-up order, the loader default, the build, INI,
README, install script) with negative tests `work\qol17x_0811\make_negative_qol01.py`; for 0.1.1
`work\qol17y_0811\check_qol011.py` (the same plus the live logic: tick, gates, ShakeApply, the switches rows) with
`work\qol17y_0811\make_negative_qol011.py`; for 0.1.2 `work\skip18c_0811\check_qol012.py` (the same plus SkipIntro:
the movie chain, the player's open-failure path, the gates, the restart row) with
`work\skip18c_0811\make_negative_qol012.py`; for 0.1.4 `work\qol_pausebit_1111\check_qol014.py` (the same plus
section pausebit: every instruction with the memory operand of the pause byte / pause flags decoded, the paused branch
reached only with the bit, the `PauseBitCheck` order, the clock-site / hook pairing) with
`work\qol_pausebit_1111\make_negative_qol014.py`.
