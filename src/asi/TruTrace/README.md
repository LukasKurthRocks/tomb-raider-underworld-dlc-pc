# TruTrace.asi

A **log-only** ASI plugin for the PC `tru.exe` (Steam, image base `0x400000`). It changes nothing in the game: every
hook writes log lines and then runs the original code with all registers, the flags and the x87 / SSE state as they
were. It answers "where do we have to change it?" for open points of the DLC port. Log `TruTrace.log`, options
`TruTrace.ini` `[Trace]` (both next to `tru.exe`). Every category is on by default and rate limited.

**Status 0.3: built 2026-11-05 (`work\asi\trace03`), offline self test 17 / 17 (framework; the new hook itself only
runs in the game), byte checks 0.1 51 / 51 + 0.2 55 / 55 + 0.3 8 / 8, not played.** 0.2: built 2026-11-05
(`work\asi\trace02`), self test 17 / 17. 0.1: built 2026-11-04 (`work\asi\trace01`), self test 11 / 11.

## 0.3.1: dated log lines (Q107, 2026-11-12)

Built 2026-11-12 into `work\asi\i_1211\TruTrace`, not installed, not played (0.3 is installed since 2026-11-05).
Only the log format and the version text changed (shared helper `src\asi\TruLog.h`): every line of `TruTrace.log`
starts with `YYYY-MM-DD HH:MM:SS.mmm`, and each game process writes one header line
`=== <date time> TruTrace 0.3.1 session start (pid n) ===` (at the first buffer flush). The exported
`TruTraceVersion()` (TruLink `modules`) said 0.2 up to 0.3 - it now says 0.3.1. Hooks and options are as in 0.3 (same
sample .ini). Install: `scripts\windows\Set-TruTrace.ps1 -Install -SourceDir work\asi\i_1211\TruTrace`.

| # | TO TEST 0.3.1 | expected |
|---|---|---|
| 1 | start the game once with 0.3.1 installed, read `TruTrace.log` from its last `session start` line on | header and `loaded` line name 0.3.1; every newer line starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start; TruLink `modules` shows `TruTrace 0.3.1` |

## Categories

| INI key | Question | Source of the lines |
|---|---|---|
| `Sound` | Which sound keeps playing after the wall run (groan loop), who started it, was it ever stopped? | entry + result hook on the emitter create `tru+0x1935d0` (callers: anim event sound branch `tru+0x1b99c0`, sound by id `tru+0x1953e0`, play wrappers), emitter end = vtable `0x851240` slot 0 (`0x590920`), instance sound list release `tru+0x18d740`, fixed-slot stop `tru+0x189820(mode)`; `LONG` = emitter alive after `SoundLiveMs`, `REPEAT` = same sound started `SoundRepeat` times in 10 s |
| `Teleport` | Player state before / after a position jump (TruMenu "Zur Marke", unstuck) | poll thread: instance +0x20, chart record of `gameTracker+0xf10` with its Lara state ids, `gameTracker+0xa64` / `+0xc94`, instance +0x14, `[0xfada74]`; follow-ups after 0.25 / 0.5 / 1 / 2 / 3 s |
| `Chart` | Which call changes the player's state | transition `tru+0x387890` (old -> new record, caller), reset `tru+0x3874d0`, start `tru+0x387e00` - player machines only; level 1 inside the teleport window |
| `PowerMessages` | Who receives 0x1f4 / 0x1f5 | wake `tru+0x1b2de0` called from `TruShadowPower.asi` (it wakes every receiver right before the message); message number from `TruShadowPowerMeterApi` flags bit 0; instance +0x14 0.5 s later |
| `Spawn` | Spawn requests and why one is refused (hall02 thralls) | intro `tru+0x1bcc30`, birth `tru+0x1bd0f0` / `tru+0x1bd270` with result; objects whose name contains `SpawnFilter` (default `thrall`) |
| `Object858` | When does the object table entry of 858 change state | poll of table `0xdb7400` (state +0xe, object +8, data +0x5c type) |
| `TimeVector` | Does the shader clock stand still while the world is frozen | RenderDevice `[0xa1407c]` +0xfa4c / +0xfa48, `[0xe7f188]`, `[0xdb94de]` once per `TimeVectorMs` |

0.2 (why does a level load put the player somewhere else?):

| INI key | Question | Source of the lines |
|---|---|---|
| `Level` | Which unit was requested, by whom, which unit was loaded, where was the player put and why | `GAMELOOP_RequestLevelChangeByName` `tru+0x1df8c0` (name, doneType, caller / module; ignored while `gameTracker+0xb9` is set), poll of `gameTracker` `0xe7f088` +0x38 / +0xb8..+0xbb, `STREAM_LevelLoadAndInit` `tru+0x1d30d0` (requested name -> unit entry; also reached from `STREAM_MoveIntoNewStreamUnit` through `[0x8aa840]`), the player placement `tru+0x1d40c0` (game data `[0xc59264]` +0x90 checkpoint id, +0x114 when +0x1f4 != 0 -> the intro with that id +0x58 in the loaded unit, else a `checkpoint` / `invis_checkpoint` intro by the unit's default index; position copy `0x698180`, spawn `0x5bd080`; no checkpoint intro -> `SAVE_SaveGame(0)`), `STREAM_MoveIntoNewStreamUnit` `tru+0x1c1bf0` |
| `Portal` | Which stream portal moved the player into another unit | `tru+0x1d2aa0` (instance, portal; record = `[[unit data]+4] + portal+0x14 * 0x100`, target unit +0x84) - the player's at level 1 |
| `StreamUnits` | Which units are loaded / unloaded when | poll of the stream unit table `0xdbab40` (32 x 0xd8: +0 id, +4 state, +0xc name) |
| `Save` | When is a checkpoint written, with which unit / checkpoint id; what does a restore bring back | `SAVE_SaveGame` `tru+0x1570f0` (callers: checkpoint message handler `0x6a1a70` - logs the checkpoint instance -, gameloop `0x5dfba0`, the placement's tail jump), `SAVE_RestoreGame` `tru+0x157130` with the result; poll of +0x10 / +0x90 / +0x114 / +0x1f4 in the active block and the checkpoint copy `[0xc59268]` |
| `Progress`, `ProgressFilter` | Which checkpoint / trigger / wall instances appear, go or change flags | poll of the active instance list `0xd98d54` (+8 next): births, removals, +0x14 / +0x18 changes of objects whose name contains a filter token |
| `Messages` | Which messages reach those instances | `INSTANCE_Post` `tru+0x1b3750` (instance, message, data) to ProgressFilter objects |
| `GameData`, `GameDataMs` | Which game data bytes change (progress flags) | diff of the active save buffer `[0xc59258]` (0x140000 bytes) every `GameDataMs`; a word changing in 8 polls in a row is muted |

0.3 (F5 follow-up: which fixed sound slot plays "sound 20212"?):

| INI key | Question | Source of the lines |
|---|---|---|
| `SoundSlots` (needs `Sound`) | Which object sound slot started / stopped an emitter, with which mode and parameter | entry + leave hook on the slot play `tru+0x193d50` (thiscall, `ecx` = the instance sound list `[inst+0x248]`: +0 owner, +4 slot count, +8 slot table of {SoundPlex node, s16 default parameter}, +0xc handles), reached only from the anim event dispatcher `tru+0x1b69c0` (type 0x60, call `0x5b6a30`): `SLOT STARTED / already playing - not restarted / stop mode 4 sent / dead handle released` with owner instance, slot, mode (1 start only when the slot has no live emitter, 0 stop), p3 (word -> emitter +0x44), p4 (0xff = the slot's default parameter), node + its section id, emitter / sound before and after, the dispatcher's caller (`0x5b9fe8` = anim event kind 2) and the payload bytes +4 / +5. The same (owner, slot, mode, result) is logged at level 1 the first 5 times and every 20th time, else at level 2. Emitters started there carry `fixed slot N of <instance>` in their START / REPEAT / LONG / END lines |

No generic "trigger fired" / script event point was proven statically; `Progress` / `Messages` / `GameData` log the
effects instead.

Every line: `time [stream unit] category: text`. A status line every 60 s counts the hook calls and any framework
fault (should stay 0).

## Safety

* Every hook site and every fact the decoding relies on is byte-checked at load (list in
  `work\asi\trace01\precheck_trace01.txt` 51 / 51, `work\asi\trace02\precheck_trace02.txt` 55 / 55 and
  `work\asi\trace03\precheck_trace03.txt` 8 / 8, offline `tools/pe_bytes_check.py`); a mismatch switches that category
  off and is logged (0.3: a slot-play fact mismatch switches only `SoundSlots` off). The plugin loads after the other
  `Tru*.asi` (alphabetical), so it sees their patches. 0.2 never hooks a site another plugin patches; it hooks entries
  that TruMenu (`0x5df8c0`, `0x5c1bf0`, `0x5b3750`), TruLink / TruShadowCombat (`0x5b3750`) only byte-check in their
  own start, and the placement `0x5d40c0` whose body TruDlc2Player patches at `0x5d42e9` (not checked by TruTrace).
* Hooks: a 5-byte `jmp` over position-independent prologue instructions (relocated into a trampoline) or a vtable slot;
  results through a per-thread shadow stack of return addresses (matched by the stack pointer).
* Lines are buffered and written by the poll thread every 100 ms - no file access on the game thread.
* Not in `tru.exe` (self test host): nothing is hooked.

## Self test

`SelfTest.cpp` (build line in its header) loads the plugin outside the game and calls `TruTraceSelfTest`: the same
framework on the plugin's own test functions (cdecl, thiscall `ret 0xc`, float in st0, recursion depth 6, vtable slot,
`GetLastError` kept, 1000 calls; 0.2: 7-byte prologue, prologue with an absolute `mov eax, [abs]`, `push esi; mov
esi,[esp+8]`, and a hooked function tail-jumping into another hooked one - both leaves on the same stack slot, as the
placement `tru+0x1d40c0` jumps into `SAVE_SaveGame`).

## Exports

`TruTraceVersion()`, `TruTraceSelfTest(buf, size)` (offline only, refuses inside `tru.exe`).
