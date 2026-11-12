# Q102 - Where the ~35 s of a `level.load` go (2026-11-12, read-only)

Researcher: agent (static disassembly of the PC `tru.exe`, existing logs of 2026-11-11). Nothing built, nothing
installed, the game was not started. Tools written for this: `q102_load_times.py` (phases from TruTrace.log, output
`q102_load_times_1111.md`), `q102_unit_sizes.py` (unit DRM sizes from the PC archives). Raw disassembly listings:
`dis_*.txt` in a temp folder outside the repository.

Legend: ✅ proven (code or log), 🔶 plausible / estimate, ⬜ open.

## 0. Short answer

* A base-game `level.load` from inside a level takes **22.9 - 37.8 s (median 32.2 s; 19 loads on 11.11.)**, DLC 2
  start 18.3 - 18.9 s, a death reload about 3 s (a fixed minimum of 3000 ms in the code). ✅
* The whole load runs **on the main thread in six "wait" loops of one shape** ✅:
  `fs->IsBusy / fs->Update()` (exactly **one** call per pass) -> `Sleep(5)` -> one loading-screen frame `0x5dddf0`
  (scripts, render, Present, and the frame-time function 0x5da230, i.e. TruQoL's limiter wait). No worker thread
  reads or decompresses: the file system (`MSFileSystem`, overlapped `ReadFile` + non-blocking
  `GetOverlappedResult`) issues **at most one read of <= 512 KB per `Update()` call** and processes (decompresses /
  hands to the section receiver) the previous one in the same call. ✅
* So the load speed is **(bytes or files per `Update`) x (loop passes per second)**. The passes are slow: in the
  per-second dt samples of TruTrace the loop never runs faster than **33.3 ms per pass (dt = 1.00 minimum in every
  in-game load, i.e. two 60 Hz vblanks)**, and 40 - 50 % of the seconds are even slower (dt 1.1 - 2.0 = 37 - 67 ms,
  heavy work in the pass). ✅ (log). Main units arrive at a steady **6.3 - 7.2 MiB/s** whatever their size
  (60 MB in 8.8 s, 13 MB in 2.0 s) = about 220 KiB per pass at 30 passes/s. ✅ (log + sizes)
* **The 60 fps FrameLimit is not the brake**: it waits only when a pass is shorter than 16.7 ms, and in-game loads
  never had such a pass (min dt 1.00 in 23 of 23 loads started inside a level); the live A/B of 08.11. (ENGINE.md row "Worker pool") gave
  the same load times with and without the limiter. ✅ A `SkipWhileLoading` switch would therefore change nothing today.
* Biggest lever (mechanism proven, gain not measured): **pump `fs->Update()` several times per pass** (time budget)
  instead of once - the engine itself does exactly this in its synchronous paths. Second lever (hypothesis): the
  `Sleep(5)` costs a whole 15.6 ms timer tick when the process has the default timer resolution, which would explain
  the 2-vblank floor (front-end-started loads reach 16.7 ms passes in the same loop).

## 1. Log evidence

### 1.1 Plugin state during the loads (11.11., sessions 19:09, 20:21, 21:04)

`TruQoL.log` (game folder), session cut at the `loaded` line:

```
533: 21:04:51.744 TruQoL 0.1.6 loaded (enabled 1, log level 1; FrameLimit 1 / 60 fps / AutoOff 1, ...
539: 21:04:51.805 FrameLimit: on, 60 fps - the clock calls 0x005da247 / 0x005da684 of the frame-time function 0x005da230 wait ...
546: 21:05:13.343 FrameLimit: d3d9.dll = <game folder>\d3d9.dll (a wrapper, e.g. TRAWindowed, no known limiter) - TruQoL's limiter is the only one (on, 60 fps)
547: 21:05:13.354 FrameLimit: waiting with a high-resolution waitable timer, last 600 us as a short pause loop
```

Same lines for the 19:09 (502-516) and 20:21 (518-532) sessions: **FrameLimit on, MaxFps 60, AutoOff 1 but no other
limiter found -> TruQoL's limiter active in every load below.** `TruQoL.ini`: `[FrameLimit] Enabled=1, MaxFps=60,
AutoOff=1, SpinUs=0`. Registry (HKCU ...\Tomb Raider: Underworld\Graphics, read only): `EnableVSync=1`,
`EnableTripleBuffer=1`, `PresentationIntervalTwo=0`, FullscreenModeID 0x3c438780 (1920 x 1080, 60 Hz 🔶 by the
encoding). So VSync at 60 Hz is on as well.

### 1.2 One load in detail: `level.load l7_arctic_sea` (21:10, from L3_main_bedroom)

`TruMenu.log` (game folder):

```
76561: 21:10:26.835 item level.load: level change to 'l7_arctic_sea' requested
76563: 21:10:27.042 script: FrameCount = 1
76564: 21:10:27.062 script: Sound: Muting audio during the loading screen.
76572: 21:10:27.325 script: FrameCount = 6
76574: 21:10:35.990 script: load into l7_arctic_sea, godray 0.8
76575: 21:10:36.014 unit: l7_arctic_sea (was L3_main_bedroom; stream unit id 85)
76579: 21:11:01.904 script: *** CURRENT LEVEL = l7_arctic_sea
76581: 21:11:01.905 script: *** ABOUT TO FADE OUT LOADING SCREEN
```

`TruTrace.log` (game folder; TruTrace 0.3, `[Trace] Level / StreamUnits / TimeVector = 1`):

```
1138358: 21:10:26.833 level: REQUEST level change to 'l7_arctic_sea' (doneType 4, ... caller TruMenu.asi+0x5f0d9)
1138410: 21:10:27.213 level: STREAM_LevelLoadAndInit 'l7_arctic_sea' from 0x005de02a (level load 0x5dded0)
1138423: 21:10:36.016 stream: stream unit slot 0: id 85 'l7_arctic_sea' state 2 = loaded
1138426: 21:10:36.042 level: STREAM_LevelLoadAndInit 'l7_arctic_sea' (level load 0x5dded0) -> unit entry ... state 2
1138444: 21:10:50.857 stream: stream unit slot 1: id 86 'l7_helheim_hall01' state 2 = loaded
1138446: 21:10:52.107 stream: stream unit slot 2: id 26 'l7_thin_ice' state 2 = loaded
1138464: 21:11:01.904 level: PLACEMENT done: player ... current unit [0xe7f148] 85 'l7_arctic_sea'
```

| Phase | From -> to | Time | Loop (section 2) | dt samples (1 per s) |
|---|---|---|---|---|
| request -> load entry | 26.83 -> 27.21 | 0.38 s | L1 0x5ddff0 | - |
| main unit `l7_arctic_sea.drm` (60 124 073 B, CDRM) | 27.21 -> 36.02 | **8.8 s** = 6.5 MiB/s | L0 0x5d28b0 | 1.00 - 1.08 |
| adjacent units hall01 (18.3 MB) + thin_ice (13.3 MB) + their objects | 36.04 -> 52.11 | **16.1 s** | L2 0x5de142 | **1.62 - 2.00** for 11 s, then 1.0 - 1.3 |
| remaining objects / files until the queue is empty | 52.11 -> 01.90 | **9.8 s** | L2 0x5de142 | 0.999 - 1.05 |
| total | | **35.1 s** | | estimated ~860 loop passes |

### 1.3 All loads of 11.11. (`q102_load_times_1111.md`, made by `q102_load_times.py`)

| Unit (request from a level, doneType 4) | Total s | -> main unit s | mean dt | samples at dt 1.00 | min dt |
|---|---|---|---|---|---|
| l7_helheim03 (19:35) | 32.15 | 4.05 | 1.33 | 18 / 31 | 1.00 |
| l1_seatop | 22.85 | 1.32 | 1.59 | 7 / 22 | 1.00 |
| l1_ship_engine_hall | 31.54 | 3.55 | 1.41 | 17 / 31 | 1.00 |
| l2_cliffclimb | 27.12 | 2.26 | 1.28 | 18 / 27 | 1.00 |
| l1_baldrs_hall | 36.48 | 2.10 | 1.38 | 17 / 36 | 1.00 |
| l1_baldrs_sideroom | 29.81 | 3.13 | 1.41 | 15 / 29 | 1.00 |
| l1_baldrs_tomb | 31.14 | 3.75 | 1.44 | 14 / 30 | 1.00 |
| l1_baldrsstairs_a | 37.81 | 3.50 | 1.39 | 22 / 37 | 1.00 |
| l1_cineseatop | 34.97 | 3.32 | 1.36 | 19 / 34 | 1.00 |
| l1_cine_ship_sinking | 32.20 | 0.99 | 1.47 | 16 / 32 | 1.00 |
| l1_kraken_entrance | 31.29 | 4.48 | 1.39 | 16 / 30 | 1.00 |
| l2_junglehub | 29.63 | 2.72 | 1.41 | 16 / 29 | 1.00 |
| l7_helheim03 (20:51) | 31.80 | 4.16 | 1.27 | 19 / 31 | 1.00 |
| l7_arctic_sea | 35.07 | 9.18 | 1.34 | 20 / 35 | 1.00 |
| l7_helheim_hall01 | 32.21 | 2.80 | 1.30 | 18 / 32 | 1.00 |
| l7_helheim_hall02 | 33.48 | 2.81 | 1.27 | 18 / 33 | 1.00 |
| l7_helheim02 | 33.58 | 2.36 | 1.37 | 21 / 33 | 1.00 |
| l1_ship_exterior | 34.20 | 8.38 | 1.42 | 18 / 34 | 1.00 |
| l7_helheim03 (21:19) | 31.92 | 4.02 | 1.33 | 19 / 31 | 1.00 |
| dlc_level2_start (x3, 19:12 - 19:27) | 18.49 - 18.88 | 5.07 - 5.23 | 1.02 - 1.06 | 13 - 18 / 18 - 19 | 1.00 |
| *front end:* l1_kraken_room -> baldrsstairs_a (doneType 10, 20:23) | 25.45 | 15.16 | 1.00 | 0 (12 at **0.50**) | **0.50** |
| *front end:* l7_yggdrasil (doneType 10, 21:05) | 19.03 | 1.83 | 0.97 | 1 (10 at **0.50**) | **0.50** |

(`l1_rutlands_ship_m1` 20:18 never reached a placement in the log - excluded. "Total" = request -> `PLACEMENT
done`; the loading screen fades out within 10 ms after it.)

Main-unit rate (size from `q102_unit_sizes.py`, time = `->main unit` minus `->init`):

| Unit | DRM bytes (CDRM) | s | MiB/s |
|---|---|---|---|
| l7_arctic_sea | 60 124 073 | 8.80 | 6.5 |
| l1_ship_exterior | 55 468 121 | 8.04 | 6.6 |
| l7_helheim03 | 23 965 240 | 3.63 | 6.3 |
| l7_helheim_hall01 | 18 294 055 | 2.45 | 7.1 |
| l7_helheim_hall02 | 18 411 667 | 2.45 | 7.2 |
| l7_helheim02 | 12 950 614 | 1.97 | 6.3 |

A constant rate independent of the size, at dt = 1.0 (30 passes/s) = **210 - 240 KiB per pass**. zlib alone inflates
100+ MB/s on any current CPU, so 7 MiB/s is not a decompression limit 🔶; it matches "one read (<= 512 KiB, often
less: section 2.2) per pass".

Reloads after death (doneType 10 via 0x5de480, no `level.load`): `Muting audio` -> `ABOUT TO FADE OUT` = 3.1 s
(TruMenu.log 75830 -> 75842, 76028 -> 76040, 76426 -> 76438, 77219 -> 77231, 77350 -> 77362) = the 3000 ms minimum
of loop L5 (section 2.1).

### 1.4 Earlier live A/B (08.11., ENGINE.md section 3 row "Worker pool")

"dlc2_ceremony_room 2.06 s with ThreadCap 8, 2.0 s with 24, 2.13 s with 24 and no frame limit; dlc_yggdrasil_end
7.35 / 7.3 / 7.29 s; back in play about 40 s / 28 s in all three runs - the worker count and the 60 fps limit change
neither the unit load nor the time after it". One run each, but consistent with 1.3.

## 2. Static: how the loader progresses

### 2.1 The call chain and the six wait loops ✅

`level.load` -> `GAMELOOP_RequestLevelChangeByName` 0x5df8c0 -> next frame the main-state dispatcher 0x5e0090
calls **0x5de7e0** (at 0x5e00d3): main state = 2 (0x5de896), **synchronous** `0x5de2b0` (0x5de89c) = load entry
`0x5dded0` + post-load `0x5de040` (0x5de3c0), then state 1 and a full file-system `Synchronize` (fs vf+0x20 = 0x472c20
-> 0x4741a0 `while (IsBusy) Update()` without Sleep, 0x5de8c9). From the menu: 0x5de9c0 (state 2 at 0x5de9ca ->
0x5de040). The game does not return to its main loop until the level is in: every loading-screen frame is drawn from
inside the wait loops below.

| Loop | Where | Waits for | Body per pass |
|---|---|---|---|
| L0 | 0x5d28b0..0x5d2904 in 0x5d2870 (wait for one unit, from `STREAM_LevelLoadAndInit` 0x5d30d0) | the unit's load object (0x54f050) | fs vf+0x18 IsBusy, **fs vf+0x1c Update** (0x5d28d5), `Sleep(5)` (0x5d28ec), **0x5dddf0** (0x5d28ee) |
| L1 | 0x5ddff0..0x5de009 in 0x5dded0 | fs idle (after the unit dump and the two resident objects 0x8abecc) | `Sleep(5)` (0x5ddff2), 0x5dddf0 (0x5ddff4), **0x5c1da0** (0x5ddff9) |
| L2 | 0x5de142..0x5de15b in 0x5de040 | fs idle = adjacent units, all intro objects, children | `Sleep(5)` (0x5de144), 0x5dddf0 (0x5de146), 0x5c1da0 (0x5de14b) - then placement 0x5d40c0 at 0x5de174 |
| L3 | 0x5de1e0..0x5de231 in 0x5de040 | fs idle, plus 0x5b9140 / `[[0xa1407c]+0x11600]`, at most 15 000 ms (0x5de211) | 0x5c1da0, `Sleep(5)` (0x5de22a), 0x5dddf0 (0x5de22c) |
| L4 | 0x5de430..0x5de463 in 0x5de3e0 | as L3 without time limit | 0x5c1da0, `Sleep(5)` (0x5de45c), 0x5dddf0 (0x5de45e) |
| L5 | 0x5de6c1..0x5de6f2 in 0x5de480 (death reload) | fs idle **and at least 3000 ms** (0x5de6e2 `cmp eax, 0xbb8`) | 0x5c1da0, `Sleep(5)` (0x5de6eb), 0x5dddf0 (0x5de6ed) |

`0x5c1da0` = `busy = fs->IsBusy(); fs->Update(); return busy || fs->IsBusy()` (fs = `[0x9ce278]`, MultiFS vtable
0x8440ec: +0x18 IsBusy 0x472be0, +0x1c Update 0x473680 = Update of every mounted file system, +0x20 Synchronize
0x472c20). `0x5dddf0` = the loading-screen frame: pulsing colour 0x8abf40 / 0x8abf44, begin / clear 0x474e60 /
0x474d70, script & UI update `0x47afd0([0xe7f194])`, 0x774550, 0x789220, 0x483810, **frame time `0x5da230` at
0x5dde91**, 0x52c470, 0x5cebc0(0), 0x5c5a30(1), end 0x474d70 / 0x474d50. Its only callers are the six loop sites
0x5d28ee, 0x5ddff4, 0x5de146, 0x5de22c, 0x5de45e, 0x5de6ed (`pe_callers`, no other reference) - so **"inside
0x5dddf0" means exactly "in a load wait loop"**.

### 2.2 The file system: one read per `Update` ✅

`MSFileSystem` (vtable 0x84425c; +0x18 IsBusy 0x473fd0 = request list `[this+0x1442c]` non-empty, **+0x1c Update
0x474610**, +0x20 Synchronize 0x4741a0, +0x24 0x4741d0 / +0x28 0x4742b0 = suspend / resume by the code (counter `+0x1443c`, closes the handles, `Sleep(1)` until in-flight reads end) 🔶 names). Files are opened
`CreateFileA(..., GENERIC_READ, ..., OPEN_EXISTING, 0x60000000 = FILE_FLAG_OVERLAPPED | FILE_FLAG_NO_BUFFERING)`
(0x473ab7..0x473ad3), read with `ReadFile` + OVERLAPPED (0x473b61), polled with `GetOverlappedResult(..., bWait = 0)`
(0x473bb0). `Update` 0x474610 is a state machine over the head request (`+0x134`, switch table 0x474a08):

* state 0 (0x474683): open the file, receiver start -> state 1 -> continue;
* state 1 (0x474711): chunk = `min(0x80000 - buffered, bytes left)` into the 0x80800 ring `[this+8]`; if the
  buffered part is already large (`buffered + 2 x partial >= 0x80000`, 0x4747ba..0x4747c4) -> state 3 and **return
  without a read**; else `ReadFile` -> state 2 and **return** (0x47483e..0x47484d);
* state 2 (0x47484e): `GetOverlappedResult(no wait)`: pending -> process what is buffered (0x4749f5 -> 0x474060) and
  return; done -> state 3 -> continue;
* state 3 (0x4748c3): `0x474060` hands the bytes to the request's receiver (`[req+0x120]` vf+0: the DRM / CDRM
  section reader - decompression and section handlers run here, on the main thread) -> state 1 (more bytes) or 5;
* state 5 (0x47493d): close, receiver done (vf+8 / vf+0xc: e.g. the object load end 0x54e6c0 with its child
  requests), state 6, next request.

So per `Update` call: at most one completed chunk is processed and at most one new read of <= 512 KiB is issued; a
small file costs at least one pass (open + read in pass n, completion in pass n+1). The measured ~220 KiB per pass
fits the "skip the read when the buffer is half full" rule. There is **no reader / decompression thread** (the worker
pool 0x4a1ed0 of ENGINE.md section 3 is not used by this path: no fs call there, and the reads are polled from the
main thread). No per-frame byte budget other than "one request step per call".

### 2.3 Where the pass time goes (partly open)

* `Sleep(5)` (import 0x83e104): `tru.exe` never calls `timeBeginPeriod` (not imported). On Windows 10 2004+ a
  process that did not raise the timer resolution itself is woken at the default 15.6 ms tick, so `Sleep(5)` takes
  5 - 20 ms (often ~15.6). 🔶 TruQoL calls `timeBeginPeriod(1)` only when the high-resolution waitable timer is
  missing (TruQoL.cpp `PrepareWait`, ~line 607) - here it exists (log line 547), so TruQoL does not change it. Two
  multimedia timers in the exe (`timeSetEvent` at 0x7fce34 and 0x80d129, resolution 0) may raise the process
  resolution while they run - which subsystem / when: ⬜.
* The loading frame: Present with `EnableVSync=1` at 60 Hz -> a pass ends on a vblank; with Sleep ~15.6 ms + any
  work > 1.1 ms the pass becomes 2 vblanks = 33.3 ms = dt 1.00. This is exactly the floor seen in every in-game load,
  while the **front-end-started loads ran whole phases at dt 0.50 (16.7 ms per pass) in the same loop L2** (TruTrace
  1089748.., 20:23:46 - 20:23:56, objects phase). So the loop can run at 60 passes/s; in a level something adds
  >= 16.7 ms per pass. Prime suspect: the Sleep granularity (in the front end a multimedia timer may be active); not
  proven ⬜.
* The dt 1.3 - 2.0 seconds (40 - 50 % of every in-game load, e.g. arctic_sea 36 - 47 s at 2.0 = >= 67 ms per pass)
  are passes with heavy work inside `Update` (receiver: section handlers, object load end / resolve, texture
  creation) and/or the frame. Not split further statically ⬜.

## 3. TruQoL [FrameLimit] during loads

* `StartFrameLimit` points the rel32 of both clock calls of 0x5da230 (0x5da247 running, 0x5da684 paused) to
  `ClockStub` -> `LimiterWait()` (TruQoL.cpp ~line 646): wait until the next 1/MaxFps slot with a high-resolution
  waitable timer + 600 us spin, then the game's clock. **It waits in every caller of 0x5da230, including the loading
  frame 0x5dddf0 (call 0x5dde91), once per load-loop pass.** There is no main-state or loading exemption. ✅
* `AutoOff` exists but only switches the limiter off when DXVK (d3d9.maxFrameRate) or dxwrapper (LimitPerFrameFPS)
  is detected; here d3d9.dll is TRAWindowed -> no auto-off (log line 546). ✅
* Effect: the limiter only waits when a pass is shorter than 1/60 s (`if (target && now < target)`; a pass that is
  late starts a new cadence, no catch-up). In-game loads: min dt 1.00 in 23/23 loads started inside a level -> **the limiter never waited
  during an in-game load on 11.11.** ✅ (by the dt samples; the dt is the game's own 6-frame average of the very clock
  the limiter delays). In the two front-end loads it may have bound the dt-0.50 phases - but so would VSync at 60 Hz,
  so even there `SkipWhileLoading` would gain nothing while VSync is on. 🔶
* Quantified: passes/s are 15 - 30 in-game; with the limiter at 60 the cap is 60 passes/s -> 0 % loss now. It only
  becomes a brake after a change that brings a pass below 16.7 ms **and** VSync off (or a higher refresh rate).

Side observation (not part of the question): the dt samples show **30 fps (dt 1.00) also in normal play** in these
sessions (e.g. TruTrace 1138341 `21:10:25.512 [L3_main_bedroom] ... dt 1.00368`), i.e. the game reached 60 fps
nowhere in a level; the TruQoL README test 2 expects about 60. Cause ⬜ (GPU / plugin load / vsync quantisation).

## 4. ModLoader.asi (third party)

From the docs only (`docs/WINDOWS_REBUILD.md` ~line 1349, `docs/COSTUMES.md` line 44): ModLoader v1.2 wraps the
game's file system (`HookFileSystem`); `FindFile` formats `"%s_%03d"` with the language mask and uses
`mods\<path>_NNN` when it exists, else `mods\<path>`, else the archive. Import list of `ModLoader.asi` (quick look):
no `CreateFile` / `FindFirstFile` / `GetFileAttributes` at all - it checks existence through the game's own file
system objects (the game imports the file APIs). So per opened file: up to two existence checks, **no directory
scan** ✅ (no enumeration import). Cost: a few file-system metadata calls per file (tens of microseconds each on an
NVMe with a warm cache) against >= 33 ms per pass and at most one file opened per pass -> negligible 🔶 (not measured).
`mods\` has 266 entries.

## 5. Speed-ups

| # | Change | Evidence | Expected gain | Risk |
|---|---|---|---|---|
| P1 | **Pump the file system more than once per loop pass**: before each loading frame, call `0x5c1da0` (= IsBusy + Update) repeatedly while busy, up to N ms (e.g. 8 ms) - a stub on the six `call 0x5dddf0` sites (rel32 at 0x5d28ee, 0x5ddff4, 0x5de146, 0x5de22c, 0x5de45e, 0x5de6ed; all `E8` + rel32 to 0x5dddf0) that pumps, then jumps to 0x5dddf0 | ✅ one `Update` per pass, one read per `Update` (2.1 / 2.2); ✅ the engine itself pumps `Update` in a tight loop without Sleep in `Synchronize` 0x4741a0 (used at 0x5de8c9 / 0x5dea06 right after every load) and in the synchronous file load 0x54f430 (loop 0x54f4e0..0x54f50c) - so many `Update` calls in a row are a supported pattern | 🔶 large in the dt-1.0 phases (50 - 60 % of the time, I/O-per-pass bound), small in the dt-2.0 phases (work-bound). Rough: 32 s -> 12 - 20 s; not measured | low-medium: same thread, same function, same order; the loading animation gets fewer frames (pass longer by <= N ms); a pass with many completions runs more receiver code at once (object load ends, texture creation) - same code as now, only bunched. L5's 3000 ms minimum keeps death reloads at 3 s |
| P2 | `timeBeginPeriod(1)` (process) while the main state is 2 / inside the loops, `timeEndPeriod` after | 🔶 2.3 (Sleep granularity), front-end loads reach 16.7 ms passes in the same loop | 🔶 the dt-1.0 seconds would halve -> about -25 % (e.g. arctic_sea 35 s -> ~25 s) **if** the 2-vblank floor is the Sleep; 0 if not | low (common practice; a little more power while loading) |
| P3 | `Sleep(5)` -> `Sleep(0)` in the loops (`push 5` = `6a 05` at 0x5d28ea, 0x5ddff0, 0x5de142, 0x5de228, 0x5de45a, 0x5de6e9) | same as P2 | same as P2, without a process-wide timer change | low; the loop then runs at the vblank / limiter rate (it already does in the front end) |
| P4 | TruQoL `[FrameLimit] SkipWhileLoading` | ✅ the limiter waits in 0x5dddf0 too; ✅ but never waited in an in-game load (min dt 1.00); 08.11. A/B: no change | **0 today**; only useful after P1/P3 bring passes below 16.7 ms and with VSync off | none (it only removes a wait) |
| P5 | Lower the 3000 ms minimum of the death reload (0x5de6e2 `cmp eax, 0xbb8`) | ✅ reloads measure 3.1 s = the minimum | -2 s per death | design choice (the loading screen / sound may expect it) ⬜ - owner's call |
| P6 | Prefetch / warm the OS cache | ✗ files are opened with `FILE_FLAG_NO_BUFFERING` (0x473ab7), the OS cache is bypassed; the disk is not the limit anyway | none | - |

### The one small change

**No speed-up is proven by a measurement.** `SkipWhileLoading` is the opposite of proven: the data show it would be
a no-op today (P4). The change whose **mechanism is fully proven** (static) and which is small enough for a
default-0 switch is **P1**, e.g. TruQoL `[Loading] PumpMs=0` (0 = off, 1 .. 15 = pump budget per pass):

* detection "loading": by construction - only the six `call 0x5dddf0` sites (the loading frame, called only from the
  six load wait loops; `pe_callers` 0x5dddf0) are redirected; byte-check `E8` + the rel32 to 0x5dddf0 at each site
  (TruQoL's existing pattern for rel32 patches, like `kClockCallRun`);
* stub: `t_end = Qpc() + PumpMs; while (Qpc() < t_end && ((char (*)())0x5c1da0)()) {}` then `jmp 0x5dddf0`
  (0x5c1da0 takes no arguments, returns busy in `al`, cdecl - it is what L1..L5 call themselves; L0 inlines the same two vtable calls);
* where in TruQoL.cpp: a new section next to `StartFrameLimit()` (~line 759: hook install at start-up; INI read next
  to the `[FrameLimit]` keys ~line 1612, live like `MaxFps` ~line 1522); log one line per load (passes, Update calls,
  ms pumped) at `LogLevel=2` - this also gives the missing measurement (2.3) even with `PumpMs=0`.
* the same hook gives an exact flag for a later `SkipWhileLoading` (set before / clear after the original 0x5dddf0,
  checked at the top of `LimiterWait()` ~line 650, before `if (!LimitActive())`); main state `[0xe7ed60] == 2` is the
  coarser alternative (TruMenu already reads it: "main state 2: a level start is being set up").

## 6. Open points

1. ⬜ Split of a 33 ms pass (Sleep / frame incl. Present / Update) - needs a log-only measurement (P1's log line with
   `PumpMs=0`, or cdb timing). Decides between P1 and P2/P3.
2. ⬜ Why front-end loads reach 16.7 ms passes and in-game loads do not (timer resolution via the two `timeSetEvent`
   users 0x7fce34 / 0x80d129? scripts in 0x47afd0? render content?).
3. ⬜ What the dt-2.0 passes do (36 - 47 s in arctic_sea): receiver section handlers vs. object load end vs. render.
4. ⬜ Number of files per load (object DRMs etc.) - TruTrace logs no per-file line; an `Update` state-0 counter would.
5. ⬜ 30 fps in normal play with the 60 fps limiter (section 3 side note).
6. 🔶 Sizes in 1.3 are the stored (compressed) CDRM sizes read from `bigfile.000`; the reads are of those bytes.
