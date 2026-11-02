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
2026-10-31, not yet played.** Not covered: sounds, the blur / bloom look, rock veins (TruRockVein.asi), the shadow
strike target states and the combat conditions (0.5 gaps below).

## 0.6: condition 1046 (2026-11-01)

Every loop transition of the wall run (chart DTP 20212, records 1477 / 1488 / 1492 / 1493) needs `{2000,1046,1}`.
The TU predicate 0x8246e400 answers, in doppelganger mode (gameTracker+0x1244), the meter flags bit 0 (power active;
no meter object -> 0), else the retail test (player +0x504)->+0x1fc bit 21. PC tru+0x3655c0 has only the retail test.
`Pred1046` (option `[Conditions] Cond1046`, default 1) replaces it with a 5-byte jump; doppelganger mode =
`TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi. Log: "condition 1046: title-update predicate ..." at load,
"condition 1046 (...) is now evaluated: doppelganger 1 -> ..." and at `LogLevel=2` every change. Sample ini unchanged.
Built 2026-11-01 into `work\asi\v06`, not loaded.

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

The 0.2 options `WorldScale`, `PlayerScale`, `RampSeconds`, `[Meter] Enabled`, `DrainSeconds`, `RefillSeconds`,
`RefillDelay`, `MinStart` are gone - those values now come from the data / the TU constants.

## Build, install, remove (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Verbose              # Visual Studio 2022 x86 toolchain -> work\asi\TruShadowPower.asi
.\scripts\windows\Set-TruShadowPower.ps1 -Install        # copies .asi + .ini next to tru.exe (game closed); updates our earlier builds
.\scripts\windows\Set-TruShadowPower.ps1 -Remove         # removes them again (only if they are a build of ours)
```

No external libraries; static runtime (`/MT`), imports only `KERNEL32.dll`. License: MIT, as the repository.
