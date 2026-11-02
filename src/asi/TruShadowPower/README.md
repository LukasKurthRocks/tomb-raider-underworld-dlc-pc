# TruShadowPower.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld) that brings back the **slow motion and the
meter of the DLC 2 shadow power** (*Lara's Shadow*). On the Xbox the title update (TU) gives Lara the Doppelgänger's
power: while LB or RB is held the world slows down, a meter (the yellow silhouette in the HUD) drains; when it is empty
the power ends, and it refills over time. The PC exe never received that code, but it has the engine parts the TU
drives: the time-scale ramps, the HUD bar and the same tuning data.

Since 0.3 the meter is a **function-by-function translation of the TU code** (decompiled from the TU memory image; same
formulas, order and branches) that reads its rates and scales from the **same data the Xbox reads** - no estimated
values. The translation table, the data sources and every left-out part are documented in
[docs/WINDOWS_REBUILD.md](../../../docs/WINDOWS_REBUILD.md) finding 43 ("ASI step 3.3") and the project's
`Befund-Schattenkraft.md`.

**Status: 3.1 (slow motion) played; 3.2 (meter with estimated rates) played - meter OK, HUD silhouette not shown;
3.3 (translated meter + HUD trigger) played 2026-10-30 - drain / refill 200/s as in the data, tuning from the
fallback copy; 0.4 (lookup diagnostics, Lara conditions) played 2026-10-31 (test A); 0.5 (TU states) built
2026-10-31, not yet played; 0.9 (TU tick gates, adrenaline look) built 2026-11-02, not played.** Not covered: sounds,
the shadow-strike look, rock veins (TruRockVein.asi), the shadow
strike target states and the combat conditions (0.5 gaps below).

## 0.9: the power only through the TU path, and the adrenaline look (2026-11-02)

**Tick.** On the Xbox the shadow-power tick 0x823d7a10 is called by the player update 0x824126d8 only when
gameTracker+0x1244 (the doppelganger flag) is set (0x824128a4..0x824128b8). Up to 0.8 the plugin ran it in every level
from the pad poll and without the TU's gates - so the power could start in DLC 1 / the main game and during a
cutscene (live 2026-11-02). 0.9 runs the tick only with `TruDlc2PlayerDoppelganger()` (TruDlc2Player 0.2 clears it
with every new game tracker, as the TU's new tracker does) and translates the gates of 0x823d7a10 / 0x823d7d40:

| TU | PC | effect |
|---|---|---|
| cinematic: [0x82efb590] +0xdd set and +0x2c != -1 (inline) | tru+0x53f00 (same test on [0xe7f1c0]) | active power stops; no start |
| byte 0x829ca6da (= retail 0x829ca5f1) | 0xfae8dd (setter tru+0x37bbf0, called by GAMELOOP tru+0x1de480 = retail 0x8229c530) | active power stops; no start |
| gameTracker+0x628 > 0.0 (health) | gameTracker+0x628 | no start at 0 health |
| 0x82efb514 bit 0 | 0xe7f144 bit 0 (same test in the adrenaline tick tru+0x318bd0 = TU 0x823defa8) | buttons ignored, active power stops |
| bool parameter 0x412 of Lara's current state (gameTracker+0xf10) -> meter flag 0x80 | same (tru+0x383f50 / 0x384c20) | meter blocked while set |
| refused start -> player event 0x80 | tru+0x318780 | sound / effect record of the doppelganger, if any |
| new tracker -> new meter object | TruDlc2PlayerTrackerGeneration() | meter re-initialised per tracker |

What is still not the TU: the buttons. The TU reads LB / RB from the game's input records (+0x1a70 / +0x1b30 & 4 of
[[0x8286dd90]+0x18]->[0], PC [[0xa02b68]+0x18]->[0] - the PC adrenaline tick reads +0x6f0 of the same records as the
TU). No PC code reads +0x1a70 / +0x1b30, so whether the PC fills them is open: by default the pad poll's XInput LB / RB
stays the button source and the log prints the two game records whenever LB / RB changes ("input diagnostic", 12
lines); `[ShadowPower] GameInput=1` reads the game records instead. `[ShadowPower] LegacyPadStart=1` restores the 0.8
tick (every level, no gates). The ControlFlag word [0xfada74] is not tested by the TU tick and therefore not here.

**Adrenaline look ([Look] AdrenalineMode).** The TU's lead for the soft / bright look (docs Befund-TU-Funktionen L9):
0x823d94f8 runs per tick and sets **meter flag 0x40** (0x823d9348: world request slot 3 = tuning +0x38 = 0.1, HUD
0x9000 when player +0x1fc bit 10, event 0x39) while the power is on, the meter is above tuning +0x28, 0x823df8f8(player)
answers 1 (= PC tru+0x2f2800 with the TU's doppelganger branch: only +0x1fc bits 9 / 10, 30, 24 before the shared tail),
the mode [gameTracker+0x500]+0x134 is not 3 and flag 2 is clear; 0x823d9438 clears it (slot 3 empty, HUD &= ~0x9000,
event 0x3a; also from Stop). In doppelganger mode the camera mode chooser (TU 0x822acdd0 = tru+0x1e7fe0, site
tru+0x1e80a9) picks **camera mode 0x34** by meter flag 0x40 instead of player +0x1fc bit 27, and the adrenaline start /
stop / tick (tru+0x3189c0 / tru+0x318ad0 / tru+0x318bd0) and condition 1047 (tru+0x365600) read flag 0x40 (and flag 2
for bit 21) - six naked stubs, all or none. Whether mode 0x34 is the soft / bright look is for the live test. Not
ported: the instance messages 0x82415b50(1) (PC partner unverified), 0x823d77f0 (shadow-strike look group).

**TO TEST (0.9)**

| # | test | what the owner should see |
|---|---|---|
| 1 | DLC 2: hold RB / LB | slow motion + yellow bar as in 0.8; log "doppelganger flag 0 -> 1: shadow-power tick runs" |
| 2 | DLC 2: hold RB during a cutscene / cinematic camera | no slow motion; if it was on: log "shadow power OFF (cinematic)" (LogLevel 2) |
| 3 | DLC 2 -> main menu -> DLC 1 (same session), hold RB | no slow motion, no bar; log "new game tracker ...: meter re-initialised" and "doppelganger flag 1 -> 0 ... does not run" |
| 4 | DLC 2: power on, aim at an enemy / target (meter above 15 %) | log "meter flag 0x40 ON (TU 0x823d9348, first time)" and "camera mode chooser ... mode 0x34 ... (n times)"; the screen may turn soft / bright (camera mode 0x34) - say what it looks like; release: "meter flag 0x40 OFF" |
| 5 | main game: adrenaline dodge (aim + adrenaline button) | unchanged (retail bit 27; no line "adrenaline start ... meter flag 0x40") |
| 6 | DLC 2: LB / RB a few times, then send TruShadowPower.log | "input diagnostic" lines: whether +0x1a70 / +0x1b30 have bit 4 while held - decides GameInput=1 |
| 7 | if 1 fails (no power at all in DLC 2) | set `[ShadowPower] LegacyPadStart=1`, retry, send the log |

## 0.6: condition 1046 (2026-11-01)

Every loop transition of the wall run (chart DTP 20212, records 1477 / 1488 / 1492 / 1493) needs `{2000,1046,1}`.
The TU predicate 0x8246e400 answers, in doppelganger mode (gameTracker+0x1244), the meter flags bit 0 (power active;
no meter object -> 0), else the retail test (player +0x504)->+0x1fc bit 21. PC tru+0x3655c0 has only the retail test.
`Pred1046` (option `[Conditions] Cond1046`, default 1) replaces it with a 5-byte jump; doppelganger mode =
`TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi. Log: "condition 1046: title-update predicate ..." at load,
"condition 1046 (...) is now evaluated: doppelganger 1 -> ..." and at `LogLevel=2` every change. Sample ini unchanged.
Built 2026-11-01 into `work\asi\v06`, not loaded.

## 0.8: the shadow-power look (2026-11-02)

The blurry / bright look of the power is not a post-process call in the TU code: Start 0x823d7d40 and Stop
0x823d7fb8 fire **player events by type** through 0x82418158 (walk of the player object's event list, every record of
that type -> the player's anim-event callback). Start: 0x89, 0x32, (0x83 while moving - not ported), 0x81 (meter
full), 0x87 / 0x88 (above / below tuning +0x70 = 75 % of max); Stop: 0x33, then 0x7e (ran empty) or 0x82. The effects
are data of `doppelganger_casual.drm` (object 857, event list DTP 20172): 0x32 starts instance effects (model +0x18
effect 2 at two bones, model +0x38 record 14), 0x33 stops all of them. The PC has the same walker (retail):
tru+0x318780 `cdecl(instance, type, 0xff, channel 0)`; 0.8 calls it at the TU's places, in the TU's order, after a
byte check of its entry, type compare and callback call (`[Look] Enabled`, default 1). Log: "shadow look: player event
walker tru+0x318780 verified ..." at load, "shadow look on: first start, player events 0x89 0x32 ..." once, and at
`LogLevel=2` every "shadow look on / off: player events ...". Start / Stop also send **message 0x1f4 / 0x1f5** to
every instance whose query function (+0x11c) answers 0x172 (TU 0x823d7f18 / 0x823d8080; PC instance list [0xd98d54],
wake tru+0x1b2de0 = TU 0x8226fe00; `[Look] Messages`, default 1) - the level objects that react to the power;
presumably `dlc_fx_bloom` (object 1038, an animated fx mesh with the states fx_on / fx_off, 3 shader libs, colour
curve tables) is the full-screen look. Not ported: the camera manager call (*0x82efc780)->vtbl[0xa4] (camera +0x7c
|= 2, a sticky flag; PC camera manager not mapped), event 0x83 (needs gameTracker+0x1f0 on PC). Built 2026-11-02 into
`work\asi\v08` (sha256 8e276629...04af5, ini 2cdc7d49...1ac9), not loaded. Events and messages only in doppelganger
mode (`TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi - on the Xbox Start / Stop exist only with the DLC 2 meter
object).

## 0.7: condition 1055 (2026-11-02)

1055 is in no PC table, so the default handler answered TRUE; its only chart use is `{2000,1055,1,NOT}` (second
machine), which therefore never fired on PC. TU 0x8246e488 = the condition template with predicate 0x8246e450:
doppelganger mode -> meter flag 4, else player `+0x1fc` bit 0x20000000. Flag 4 is set only by the shadow look
0x823d8a80 while flag 2 is set, and flag 2 only by 0x823d8978 = state 1014 slot 0 in doppelganger mode (the shadow
strike) - both not ported, so in DLC 2 the translation answers 0 (the TU's answer outside a shadow strike). `Cond1055`
joins the copy of Lara's condition table (option `[Conditions] Cond1055`, default 1; TruDoppelganger.asi must hold 1055
in the generic table - it does). Log: "... 1055 (TU predicate 0x8246e450 ...) added to the link array", first call
"condition 1055 predicate (TU 0x8246e450) first call: doppelganger 1 -> 0 ...", result changes at `LogLevel=2`. Built
2026-11-02 into `work\asi\v07`, not loaded.

## 0.5: title-update states, conditions and activities of Lara

Translated from the TU (project docs `Befund-Schattenkraft.md`, "TU states for Lara"), registered in copies of Lara's
condition / activity / state tables (push operands tru+0x368b82 / +0x368b8e / +0x368b9a) after byte checks of 20 PC
building blocks, the registration code, the table sizes and TruDoppelganger's generic copies (`[States] Enabled`):

| id | Xbox TU | translation (PC parts) |
|---|---|---|
| state 243 | 0x82464180 -> 0x82463eb8 | move Lara to gameTracker+0x1270 in motion mode 1 (state parameters tru+0x383f50 / 0x384c20, frame count tru+0x35f3e0, channel setters tru+0x38d70 / 0x3e400) |
| state 245 | 0x824645d8 / 0x824647d0 | move tuning +0x6c (1896.3) along -(player matrix row +0x10), steps = length / tuning +0x68 (410.87), mode 2 (player 0xe7f094, setter tru+0x38d00); step count kept in the plugin (TU gameTracker+0x1280) |
| state 1018 | 0x82465078 / 0x824651c8 | meter cost from parameters 0x410 / 0x411, refill delay 0x414, world time-scale request 0x413 (slot 5) |
| condition 1048 | 0x8246ece0 | step count x 100 <= animation time of the agent's channel |
| condition 2401 | 0x824702b0 | timed request slot 4 (tuning +0x58 player, +0x54 world) for record-value frames; always false |
| activity 1009 / 1039 | 0x82472788 / 0x82455a38 | player instance +0xc8 = record +4 / empty print stub |
| selector | 0x823d7520 | the 7-slot time-scale request list; Start / Stop use slot 0 |

Not translated (named gaps): states 244, 1017, 1019, 1020, 2102; conditions 1055, 2005, 2006, 2013. Each new handler
logs its first call (LogLevel 1) and, at LogLevel 2, further calls at most twice per second. Build into a separate
folder with `Build-TruAsi.ps1 -OutDir work\asi\v05`, install with `Set-TruShadowPower.ps1 -Install -SourceDir
work\asi\v05`.

## 0.4: the meter conditions of Lara's link array

Lara's state machine has its own condition link array (PC tru+0x368b60 registers table 0x8b2ce8; Xbox TU 0x82473b50).
The TU added 13 conditions there; seven of them only read the meter and are translated here and added to a copy of the
table (the `push` operand at tru+0x368b81 points at the copy; checked bytes of the registration, the template and the
compare function first, and that none of the ids is in the table yet):

| id | Xbox TU | translation |
|---|---|---|
| 1049 / 1050 / 1051 | 0x824703d0 (key must be 20) | meter value (TU meter +8) compared with the record value: equal / >= / <= through the PC's own compare tru+0x383bd0 (= Xbox 0x82487348) |
| 1052 / 1053 / 1054 | same | meter percentage (value / tuning +0x10 x 100, [0x8207d53c]) the same way |
| 1056 | 0x8246e528 = template 0x82487718 with predicate 0x8246e498 | PC template tru+0x382d70 (cache per agent frame, 0 / 1 / falling / rising edge) with the predicate "percentage >= tuning +0x70 x 0.01 and power active" |

The registration loop takes the node of a new id from the generic registry; an id that is in neither registry makes
it read address 0 (tru+0x385265) - so the plugin registers only if the generic builder's table (push operand
tru+0x387343) is `TruDoppelganger.asi`'s copy and holds all seven ids; otherwise it logs why and leaves Lara's table
alone. Not translated (named gaps): 1048 (gameTracker+0x1280 x 100 vs an animation value),
1055 (meter flag 4 - no TU writer found yet), 2005 / 2006 / 2013 (shadow-combat targets), 2401 (timed time-scale
request), activity 1009, the TU states. The DLC 2 chart uses 1049-1056 in the shadow-combat transitions (e.g. "meter
at least 60 %" before a shadow strike). Option `[Conditions] Enabled`.

## Translation

| Xbox TU function | plugin | PC parts used |
|---|---|---|
| `0x823d7700` meter init (value 1000) | `MeterInit` | - |
| `0x823d7a10` per-frame tick (button latch, drain / refill, stop when empty) | `MeterTick` | frame time `0xe7f190` |
| `0x823d8120` may start (after "empty" only above tuning +0x28) | `CanStart` | - |
| `0x823d7d40` start: request player = tuning +0x40, world = tuning +0x3c | `StartPower` | `SetPlayerTimeScale` / `SetWorldTimeScale`, 33 ms |
| `0x823d7fb8` stop: request cleared (both 1.0) | `StopPower` | same setters |
| `0x823d81a0` refill: tuning +0x18 per second (+0x20 while a delay runs, +0x1c in another player state), clamp to max +0x10 | `Refill` | HUD below |
| `0x823d8380` drain by frame time x 1/30 x tuning +0x14, clamp 0..max | `Drain` | HUD below |
| `0x82415518` tuning = data of the extension instance | `FindTuning` | object table `0xdb7400`, object 858 |
| HUD in refill / drain: `0x829ca6cc = value / max; 0x829ca724 \|= 2; (*0x829ca720)->vtbl[0xc]()` | `ShowMeter` | `0xfae8d4`, `tru+0x37d9d0(1)`, `tru+0x37da70` |

The HUD trigger is the same one the PC breath code uses under water (`tru+0x2f2905..0x2f292d`): fraction into
`0x00fae8d4` (read by `hudscreenmgr` native 36), display group 1 requested in the bit mask `0x00fae924`
(`tru+0x37d9d0`), then the HUD manager `*0x00fae920` is told (`tru+0x37da70`, its vtable slot 3). The HUD script
(generalbank script 37) polls the group bit (native 7) and shows the silhouette; the TU does not touch the breath-style
flag `0x00fae8af` (native 38), so neither does the plugin (0.2 set it - removed).

Tuning: the TU spawns an instance of the object `player_tru_dlc2_extension` (id 858) and reads its data (u16 type 60):
max +0x10 = 1000, drain +0x14 = 200/s, refill +0x18 = 200/s, +0x1c = 400/s, +0x20 = 75/s, restart above +0x28 = 150,
+0x2c = 300, world +0x3c = 0.3, player +0x40 = 1.2 (values of the converted file). The plugin finds the loaded object in
the PC object table (`0xdb7400`, 0xcc entries of 0x24 bytes, the same layout as the Xbox's `0x82979280`) and makes the
TU's own checks (state loaded, object +0x5c data and +0x60 set, type 60). If the object is not loaded it uses a copy of
the file values (`Fallback=1`, logged as FALLBACK) or no power at all (`Fallback=0`, as the Xbox).
In the 0.3 test (2026-10-30) the lookup failed; 0.3.1 (same behaviour) logs which check stopped it ("id 858 not in the
table", "entry state is not 2", ..., with entry / object / data addresses) and once the list of loaded table entries
(id / state), so the next test shows where the PC keeps the object - or that it is not loaded at all.

Frame time: the PC frame update stores the unscaled frame time in 30 fps units into `0x00e7f190` (us / 33333.33, the
same constants as the Xbox's `0x82efb560`); the tick runs once per advance of the game clock `0x00e7f15c`.

At load the plugin checks the image base and the bytes at all used code addresses; on a mismatch of the pad,
time-scale or frame-time code it hooks nothing, of the HUD code it runs without the bar, of the object table it uses
only the fallback; the reason is logged. The installed game ships the **Ultimate ASI Loader** as `binkw32.dll`; it loads
every `*.asi` next to `tru.exe`.

## Options (`TruShadowPower.ini` next to the `.asi`, optional)

| Section / key | Default | Meaning |
|---|---|---|
| `[ShadowPower] Enabled` | 1 | 0 = load but hook nothing |
| `[ShadowPower] LogLevel` | 1 | 0 errors, 1 info (incl. the tuning values in use), 2 every power on / off, 3 debug |
| `[ShadowPower] Buttons` | 768 | XInput mask: 256 LB, 512 RB, 768 either (Xbox) |
| `[Meter] HudBar` | 1 | feed the HUD silhouette; 0 = no HUD writes |
| `[Meter] Fallback` | 1 | 1 = file values when object 858 is not loaded; 0 = no power then |
| `[ShadowPower] LegacyPadStart` | 0 | 0.9: 1 = the 0.8 tick (every level, no doppelganger / cinematic gates) |
| `[ShadowPower] GameInput` | 0 | 0.9: 1 = LB / RB from the game's input records +0x1a70 / +0x1b30 & 4 (the TU's source; unproven on PC) |
| `[Conditions] Enabled / Cond1046 / Cond1055` | 1 | see 0.4 / 0.6 / 0.7 |
| `[States] Enabled` | 1 | see 0.5 |
| `[Look] Enabled / Messages` | 1 | see 0.8; Enabled=0 also turns AdrenalineMode off |
| `[Look] AdrenalineMode` | 1 | 0.9: TU meter flag 0x40 (0x823d94f8 group) + doppelganger branches of camera mode chooser (mode 0x34), adrenaline start / stop / tick, condition 1047 |

The 0.2 options `WorldScale`, `PlayerScale`, `RampSeconds`, `[Meter] Enabled`, `DrainSeconds`, `RefillSeconds`,
`RefillDelay`, `MinStart` are gone - those values now come from the data / the TU constants.

## Build, install, remove (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Verbose              # Visual Studio 2022 x86 toolchain -> work\asi\TruShadowPower.asi
.\scripts\windows\Set-TruShadowPower.ps1 -Install        # copies .asi + .ini next to tru.exe (game closed); updates our earlier builds
.\scripts\windows\Set-TruShadowPower.ps1 -Remove         # removes them again (only if they are a build of ours)
```

No external libraries; static runtime (`/MT`), imports only `KERNEL32.dll`. License: MIT, as the repository.
