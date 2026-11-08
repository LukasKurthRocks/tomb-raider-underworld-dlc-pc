# TruQoL.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld 1.1, unpacked) with **comfort options for
players**: a frame limiter, a field-of-view factor, a camera-shake factor (motion sickness) and the fix for the
start-up crash on PCs with more than 31 CPU threads. TruMenu stays the debug tool; TruQoL holds only switches a player
wants, each with its own INI key (owner decision 2026-11-08). Defaults: **frame limiter on at 60 fps**, the camera
options neutral (= the game's behaviour), the thread cap on at 31 (it only acts on PCs where the game would crash).

**Status TruQoL 0.1.1: built 2026-11-08 (`work\asi\qol011`), not installed, not played.** 0.1 (`work\asi\qol01`) was
the first build; 0.1.1 reads the live keys again while the game runs (TruMenu page "Fixes", group "Komfort (TruQoL)").
Everything below is proven statically (disassembly of the installed `tru.exe`, md5 `5560abac...`, and `binkw32.dll`);
nothing is seen in game yet.

Install: `scripts\windows\Set-TruQoL.ps1 -Install -SourceDir work\asi\qol011` (check first with `-Check`, remove with
`-Remove` / `-Restore`). The Ultimate ASI Loader the game ships as `binkw32.dll` loads every `*.asi` next to `tru.exe`;
ModLoader.asi is just another plugin of that loader. Log: `TruQoL.log` next to `tru.exe`, one line per feature (on /
off / why).

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
| `[Startup]` | `ThreadCap` | 31 | 0 .. 31 | restart | the game's CPU count sees at most this many threads (only when the PC has more); 0 = off - acts once, before WinMain |

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
| `[TruQoL] Enabled`, `[Startup] ThreadCap` | **restart**: `Enabled=0` patches nothing (no tick); the CPU count runs once in WinMain |

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

Coexistence: TruQoL hooks no D3D9 function (TruMenu's Present / Reset hook, TRAWindowed / DXVK / dxwrapper as
`d3d9.dll` are not touched). TruShadowPower checks 0x5da3f4 / 0x5da40c and TruMenu 0x5da40c in the same function; TruQoL
changes only the two clock calls. With `ShakeScale` below 1.0 TruQoL owns the two shake calls and TruMenu's
`cam.shakescale` is refused (TruMenu logs "another plugin?"); with 1.0 TruQoL leaves them to the game (0.1.1: also when
the value changes live, see "Live keys"). TruMenu `camera.fov` writes camera +0xb0; TruQoL's factor applies on top.
Every redirect is made only when the call still goes to the game's function.

Not done: an INI value in degrees (the game's base FOV is camera tuning data, not a constant in the exe; read it with
TruMenu `camera.fov` in the gameplay camera to translate a degree wish into a factor), a hot-key. The TruMenu page came
with 0.1.1 (TruMenu.switches.txt, group "Komfort (TruQoL)").

## TO TEST

1. Install with `Set-TruQoL.ps1 -Install -SourceDir work\asi\qol011`; start the game (affinity work-around still in the
   launch options for the first run); `TruQoL.log`: the loaded line (`TruQoL 0.1.1`), `Startup ThreadCap: on, 31`,
   `FrameLimit: on, 60 fps`, `Camera Fov: off ... pass-through`, `Camera ShakeScale: off`, `live: TruQoL.ini is read
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

## Files

`TruQoL.cpp` (source; the comment block at the top holds the evidence in short), `TruQoL.ini` (sample with the
defaults), build: `scripts\windows\Build-TruAsi.ps1 -Name TruQoL -OutDir <repo>\work\asi\qol011`. Offline checks:
`work\qol17x_0811\check_qol01.py` (0.1: bytes, call targets, the start-up order, the loader default, the build, INI,
README, install script) with negative tests `work\qol17x_0811\make_negative_qol01.py`; for 0.1.1
`work\qol17y_0811\check_qol011.py` (the same plus the live logic: tick, gates, ShakeApply, the switches rows) with
`work\qol17y_0811\make_negative_qol011.py`.
