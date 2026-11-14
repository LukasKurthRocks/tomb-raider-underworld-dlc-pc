# TruShadowCombat.asi - DLC 2 combat of the title update (0.6.15)

2026-11-14 evening: the owner tested `ModeWithoutTarget`, `StrikeWithoutButton` and `AssistPointer` live - all three
work as expected, so they are **options** now (TruMenu 0.22.49 labels "Modus ohne Ziel", "Absprung-Schlag ohne X",
"Zielhilfe Kreis"; INI comments say "PC option"). No rebuild for the wording: the plugin's own log lines still say
`0.6.15 test switches: ...` (a string in the binary, left as it is). `DrainPercent=0` + `DrainModePercent=0` keep the
meter where it is in and out of the mode (rate x 0.0 = 0.0; TruMenu 0.22.49 "Adrenalin bleibt voll" writes both).

0.6.15 (2026-11-14, offline build; two switches, at first test switches, main workspace
`docs\Befund-Adrenalin-ohne-Ziel-1411.md`, `docs\Befund-Adrenalin-Modus-Bedingung-1411.md`, ENGINE.md row "Adrenaline
mode without a target, strike without X"): build `work\asi\tsc0615`, byte pre-checks `work\asi\tsc0615\precheck_0615.txt`
(22 checks: the 10 of `SetupM15`, 12 proof facts; 0 mismatches against `data\pc\tru.exe` and the installed tru.exe).
**PC options (tested live 14.11.), not TU translations; both default 0 = the game.**
* **`[Adrenaline] ModeWithoutTarget`** (new, live, default **0**): R3 (action 37) starts the adrenaline mode in the tick
  0x718bd0 only with the **hard lock** (CM+0x1fc bit 10, set by 0x71edf0 only with a live target of targeter 0 in
  CM+0xc). LT without an enemy gives the **soft lock** (bit 9) and R3 runs the failure branch 0x718c71 = Lara event 0x3b
  (fail sound). With 1 the lock test `shr ecx,0xa; test cl,1` at 0x718beb becomes `shr ecx,9; test cl,3` (two single
  bytes, 0x718bed 0a -> 09, 0x718bf0 01 -> 03): soft **or** hard lock. The tick ends a running mode as soon as the
  test fails (0x718cda -> 0x718ad0), so **releasing LT ends it** - the game's own end path. Not "no lock at all": R3
  without LT is also action 25 of Lara's chart, and nothing but R3 / an empty meter would end the mode. Start 0x7189c0 /
  end 0x718ad0 (HUD, time ramp, events 0x39 / 0x3a) and the other bit-27 readers (camera mode 0x34, sound word,
  meter, condition 1047) do not read the target; the readers of CM+0xc test the handle themselves. The bytes are
  written **only while the switch is 1** and only after the first combat manager exists (TruShadowPower byte-checks
  0x718be3..0x718c02 when it loads); with 0 they are the game's. Lines: `0.6.15 ModeWithoutTarget (...)` per write,
  `0.6.15 adrenaline mode without target: started with the soft lock only ...` per start, `... ended after n ms (...)`.
* **`[Adrenaline] StrikeWithoutButton`** (new, live, default **0**; 13.11. test evening, W8 "the vault-off is enough"):
  the vault-off strike's only transition (lara DTP 850 +0x720a0, into chart record 786 = state 1014) is `{500,538,1}
  {2000,2001,1} {2000,2011,1} {700,701,0} {1500,1502,0} {2300,2302,1} {150,150,46}`; the last record = action 46 held
  (pad X). Condition 150 (0x760b50, a generic "action held" test used by ~98 transitions) is wrapped in Lara's machines
  1 / 2 like 538; with 1 it answers 1 **only** when its record is `{150,150,46}` and the 6 records before it are exactly
  the strike's (the list stops at the first false, 0x785920, so it is asked only when they hold). Every other button
  test gets the game's answer; the "not full" feedback `{150,150,46} {500,538,0} {2300,2304,1}` is untouched. Together
  with `StrikeWithoutFullMeter=1`: any meter. Needs `[Conditions] Enabled=1`. Line `0.6.15 condition 150 {150,150,46}
  ... answered 1 without the button ...` (at most one per second, with the count).
* Sites: 0x718bed / 0x718bf0 (bytes, only while ModeWithoutTarget=1) - next to, not inside, TruShadowPower's tick
  sites 0x718bf3 / 0x718c5d / 0x718cda; Lara's condition tables (copies, as 538). TruMenu: not touched.

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.15 ... loaded`; `0.6.15 test switches: ModeWithoutTarget 0 (lock test 0x718beb checked; ...), StrikeWithoutButton 0 (condition 150 wrapped at Lara's registration, ...)`; no `0.6.15: ... does not match`; at the level `machine 1 conditions: ... 150 (replaced)` |
| 2 | level loaded | `0.6.15 ModeWithoutTarget: first combat manager seen - the switch acts from now on (ModeWithoutTarget 0)` |
| 3 | `ModeWithoutTarget=0`, no enemy near, hold LT, press R3 (meter > 0) | fail sound, no mode (as before); no `0.6.15 adrenaline mode without target` line |
| 4 | `ModeWithoutTarget=1` (live) | `0.6.15 switches (run time): ... ModeWithoutTarget 1 ...`, `0.6.15 ModeWithoutTarget (run time): 0x718beb = shr ecx,9; test cl,3 ...` |
| 5 | as 3 with the switch 1 | slow motion starts (`0.6.13 Q108 adrenaline mode ON ... hard lock 0`), `0.6.15 adrenaline mode without target: started with the soft lock only (CM+0x1fc bit 9 1, bit 10 0; target handle CM+0xc 0x00000000 ...)`; release LT -> mode ends, `... ended after n ms (lock released - the game's end 0x718cda ...)`; R3 again while LT held also ends it |
| 6 | as 5, then an enemy comes into view | the lock becomes hard (bit 10), the mode keeps running as in the game; camera / HUD look normal |
| 7 | `StrikeWithoutButton=1`, full meter, LT on a Viking, vault | the strike starts without X: `0.6.15 condition 150 {150,150,46} ... answered 1 without the button ...`, then `0.6.13 Q108 state 1014 enter ... STARTED`; other X uses (finisher, jumps) as before |
| 8 | `StrikeWithoutButton=1` + `StrikeWithoutFullMeter=1`, empty meter | as 7 with any meter (`0.6.14 F6 condition 538 ... answered 1` too) |
| 9 | trouble | both back to 0 (live; with 0 the tick bytes are the game's again: `0.6.15 ModeWithoutTarget (run time): ... (the game's bytes)`); send the log |

0.6.14 (2026-11-12, **offline, not yet seen in game**; group L / F6, main workspace `docs\Befund-Gruppe-L-1211.md`,
`docs\Befund-Gruppe-F-1211.md` 4.3, ENGINE.md 13.7): build `work\asi\combat0614`, byte pre-checks
`work\asi\combat0614\precheck_0614.txt`. **PC options on the game's own rules, every default = the game.**
* **Correction of 0.6.13 / group C:** the vault-off strike is chart **record 786** (state id 1014), entered only from
  the combat records 711 / 724 / 730 by `{500,538,1}` **meter full** (CM+0x1fc bit 22), `{2000,2001,1}` (activity 1002
  of record 705), `{2000,2011,1}` (hard lock + target of targeter 5 + enemy query 0x161), `{700,701,0}`,
  `{1500,1502,0}`, `{2300,2302,1}` (strike prompt: bit 28 + byte 0xfae8d8 + HUD group 1) and `{150,150,46}` = **action 46
  held = pad X** (code 1; keyboard: registry value "1"). The `{500,518,1}` transitions read by group C lead into chart
  record 1014 (state 612, a landing record) - not the strike. Without a full meter the same button gives
  `{150,150,46} {500,538,0} {2300,2304,1}` = Lara event 0x38 (feedback). So "no slow motion without a full meter"
  (11.11.) is the game's rule.
* **`[Adrenaline] FillPercent`** (new, live, default **100**): the enemy damage path posts message 0xd9 with the damage
  Lara dealt (0x63b03a -> INSTANCE_Post 0x5b3750); the plugin scales that amount (rounded) before the post. Line per post:
  `0.6.14 F6 fill: message 0xd9 (damage Lara dealt) n x FillPercent p -> m; meter a -> b / 500` (+ "skipped: bit 21" /
  "not added: bit 22").
* **`[Adrenaline] DrainPercent` / `DrainModePercent`** (new, live, default **100** = player data +0x2d4 = 20 /
  +0x2d8 = 225): the bar 0x6f2930 loads its rate at 0x6f2965 / 0x6f2972; both loads go through stubs that multiply the
  data value (factor 1.0 = the same value).
* **`[Adrenaline] StrikeWithoutFullMeter`** (new, live, default **0**, accessibility): condition 538 answers 1 in the
  main game (the plugin's registered 538 handler; doppelganger mode keeps the TU meter flag 8), so the strike starts
  without a full meter. Needs `[Conditions] Enabled=1`. Line `0.6.14 F6 condition 538 ... answered 1 without a full meter`.
* **Strike prompt log** (part of `[Adrenaline] Log`): `0.6.14 F6 strike prompt ON (CM+0x1fc bit 28 from condition 2302 ...)`
  / `OFF after n ms` - the frames in which X would start the strike.
* Sites: 0x63b03a (call), 0x6f2965 (11 B) / 0x6f2972 (12 B) - not touched or checked by TruShadowPower (0x71f500,
  0x6f28c0, 0x6f2930 head, 0x6f29b2) or TruMenu (0x6f28c0, 0x6f2930 head).

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.14 ... loaded`; `0.6.14 group L (F6): fill placed (call 0x63b03a, FillPercent 100), drain placed (...), StrikeWithoutFullMeter 0 (condition 538 registered), strike prompt log on`; no `0.6.14 F6: ... does not match` |
| 2 | empty meter, pistol hits on a Viking | per hit `0.6.14 F6 fill: message 0xd9 ... n x FillPercent 100 -> n; meter a -> a+n / 500`; n = the LP the hit took |
| 3 | `FillPercent=200`, repeat 2 | `-> 2n`, meter rises twice as fast |
| 4 | full meter (`adren.fill`), lock on (LT) near a Viking | `0.6.14 F6 strike prompt ON ...` while the conditions hold; **X** (keyboard: the key of registry value "1") -> `Q108 state 1014 enter ... STARTED` |
| 5 | `DrainPercent=0` / `DrainModePercent=50` | the meter no longer drains / drains at half speed in R3 mode |
| 6 | `StrikeWithoutFullMeter=1`, meter empty, lock + X near a Viking | `0.6.14 F6 condition 538 ... answered 1`, the strike starts (slow motion, circle) |
| 7 | trouble | all four back to 100 / 100 / 100 / 0; send the log |

0.6.13 (2026-11-12, **offline, not yet seen in game**; group C: Q108 / Q109 / Q68 / Q99, main workspace
`docs\Befund-Gruppe-C-1211.md`, ENGINE.md 13.7 / 21): build `work\asi\combat0613`, byte pre-checks
`work\asi\combat0613\precheck_0613.txt` (32 checks: the 19 of `SetupQ108`, 13 proof facts of the static findings;
0 mismatches against `data\pc\tru.exe` and the installed tru.exe). **PC options, not TU translations** (the TU changes
the adrenaline only in doppelganger mode, Q60).
* **Q108 adrenaline log** (`[Adrenaline] Log`, new, start only, default **1**, read only): a poll thread (every 10 ms,
  faults caught) writes `0.6.13 Q108 ...` lines on every change of: meter full (CM+0x1fc bit 22), adrenaline mode
  (bit 27; started by **R3** = action 37, generalbank DTP 47 binding #105 set 17 <- source 9 = pad code 9 =
  XINPUT_GAMEPAD_RIGHT_THUMB, with a hard lock and meter > 0), headshot window (bit 21, set only by the vault-off strike
  = state 1014 slot 0 0x71d3c0), circle (reticle `[CM+0]` +0x40 bit 6), pointer in / out of the zone (bit 7 = |pointer|
  < radius, 0x6f2f67), and every slow motion start / end of the world (`[0xe7f1a0]`) or player (`[0xe7f1d4]`) time
  scale with its factor (not only the first one per session). Game-thread lines: each **Vaulted Enter** of an enemy
  (in the 0.6.6 stub at 0x64fdb9, independent of `TranslateVaultedClock`), each **state 1014 enter** (STARTED / why
  not), the **0xbe record** of the strike, and each **strike shot** (RT edge in the 1014 tick 0x718d00, with pointer,
  radius and in / out of the zone). Every line carries meter / max, CM+0x1fc, reticle, pointer, radius, HUD byte
  0xfae8ae, world / player scale, the doppelganger byte and Lara's chart record.
* **Q109 pointer assist** (`[Adrenaline] AssistPointer`, new, live, default **0**, accessibility): the call 0x70d863 ->
  0x6f2f20 (runs only while the circle is up) goes through the plugin; with 1 the pointer is pulled to at most half the
  radius before the game's zone test, so bit 7 stays set and a shot succeeds (success = bit 7 when the bullet hit
  0x7198d0 runs, 0x719ce8). One line per circle: `0.6.13 Q109 assist: pointer ... pulled to ...`. A "skip the second
  condition" cheat is **not built**: the second condition of the transitions into 1014 is a timing gate (animation end,
  condition 201, or time in record >= chart parameter 354, condition 20), not a player test (Befund section 2).
* **Q68 lock-on switch input** (`[Lock] MouseSwitch` live default **1** = the game's; `[Lock] RightKey` / `LeftKey`
  live default **0**): the target switch 0x71cb10 adds the **mouse axes** (actions 0x10 / 0x11, calls 0x71cd07 /
  0x71cd20) to the right stick and switches at |v| >= 0.2 (player tuning +0x2a0) - so on the PC every mouse movement
  while locked on can jump to another target. `MouseSwitch=0` returns 0 for those two reads (the camera keeps its own
  mouse read 0x5ed4a0). RightKey / LeftKey (virtual-key codes) give one frame of +1.0 / -1.0 on the x read, so the
  game's own threshold, direction search 0x71a740, switch 0x714e80, repeat timers (+0x29c / +0x29e: 3 / 12) and sound
  run. Only while the game window has the focus. Log `0.6.13 Q68 lock: key 0x.. -> target switch to the right`.
* **Q99 option A** (`[Chunk] RemoveLastPiece`, new, live, default **0**): byte 0x696f69 `75 0f` -> `eb 0f` after the
  check of `83 e1 01 80 f9 01 75 0f 56 e8 ..` at 0x696f63; the permanent chunk piece #6 is then removed after its
  lifetime (20 s) like the others. Written back to `75` with 0 (only if the byte is still the plugin's).
* **TO TEST** (main game, e.g. `l7_helheim03` with `arena.go 1a`, **from a main-game session** - doppelganger byte 0,
  see Q100; TruMenu `adren.fill` for a full meter):

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.13 ... loaded`; `0.6.13 group C: Q108 adrenaline log on ...; Q109 pointer assist placed (AssistPointer 0 ...); Q68 lock switch input placed (MouseSwitch 1, RightKey 0x00, LeftKey 0x00 ...); Q99 RemoveLastPiece 0 (byte checked)`; no `0.6.13 ... does not match` line |
| 2 | `adren.fill`, lock on (LT), press **R3** | `Q108 meter FULL (bit 22)`, then `Q108 adrenaline mode ON (bit 27 ...)` + `Q108 slow motion START: player time scale 1.000 -> ...` (ramp to 0.5); R3 again / release lock: `mode OFF after n ms`, `slow motion END ... (lowest 0.500)`; the meter drains faster (225 instead of 20) |
| 3 | full meter, a thrall / Viking charges, jump off it (vault) | `Q108 vault: <enemy> enters Vaulted ...`; `Q108 state 1014 enter (vault-off strike 0x71d3c0): STARTED` (+ `strike 1014: message 0xbe record for <enemy>`), `headshot window ON (bit 21 ...)`, `circle ON (reticle bit 6) ... radius r`; if 1014 is entered but nothing starts, the line says why (bit 21 already set / no target ...) |
| 4 | move the pointer into the grey zone, shoot (RT) | `pointer IN the zone (bit 7) ...`, `headshot SHOT ... -> IN the zone`; the enemy dies (the 762-type hit, `[Damage] Log`); `headshot window OFF ... (reticle bit 9 0x200 = 1)`; a shot outside: `-> OUT of the zone`, window OFF with 0x200 = 0 |
| 5 | slow motions | every one has a START / END line with its factor (kill camera, scripted adrenaline moments; world 0.133 at the yggdrasil grapple scene) - not only the first of the session |
| 6 | `AssistPointer=1` (TruMenu row "Adrenalin: Zeiger im Ziel (Hilfe)"), repeat 3 / 4 | `0.6.13 switches (run time): [Adrenaline] AssistPointer 1 ...`; at the circle `Q109 assist: pointer ... pulled to ...`; the pointer sits in the grey zone and only moves within it; RT always succeeds |
| 7 | locked on (LT) with several enemies, move the mouse | `MouseSwitch=1`: the target jumps (Q68 as reported); `MouseSwitch=0`: no jump from the mouse, the right stick of the pad still switches; `RightKey=88` (X) / `LeftKey=67` (C): one switch per key press (`Q68 lock: key 0x58 -> target switch to the right`) - say whether the direction is right |
| 8 | `[Chunk] RemoveLastPiece=1`, kill a Viking (chunkdoll), wait 25 s | `0.6.13 Q99 chunk (run time): 0x00696f69 = eb 0f ...`; the last piece (torso) vanishes too; with 0 it stays; checkpoint + reload: old pieces reappear and vanish 20 s later |
| 9 | trouble | `[Adrenaline] Log=0`, `AssistPointer=0`, `MouseSwitch=1`, `RemoveLastPiece=0`; send the log |

0.6.12 (2026-11-11, **offline, not yet seen in game**; Q37 "the thrall got up again after the finisher Y", live
2026-11-10 22:12; main workspace `docs\Befund-Translate1015Exit-1111.md`, ENGINE.md 12): build `work\asi\combat0612`,
byte pre-checks `work\asi\combat0612\precheck_0612.txt` (13 checks: the 10 of `CheckState1015Blocks`, 3 proof facts of
the death-kind reading; 0 mismatches against `data\pc\tru.exe` and the installed tru.exe).
* **State 1015 exit = the kill of the finisher Y's target** (chart record 742 [1004 1015]; `[States]
  Translate1015Exit`, new, live, default **0**). PC = retail: table entry 1015 at tru.exe 0x8b1a48 = {tru+0x35e0e0, 0,
  tru+0x35e0f0, 0, 0, 0}: slot 0 keeps the targeter-6 object in CombatManager +0x48 / +0x4c (tru+0x31d8c0), slot 2 only
  clears it (tru+0x2e66d0, = retail 0x8245bd48). TU table 0x827589cc: slot 2 = **0x8245fe58** (TU-new,
  "[CombatManager::ThrallFatalityEnd] Enemy Didn't Chunk from Fatality, Chunking them explicitly on exit."): when the
  stored handle is still valid, v = Lara +0x20 - target +0x20 with z = 0, death switch 0x823258c8(target, 0, 0, 0,
  kind 0, 1, v) = tru+0x241650(target, &v, 0, 0, 0, 0, 1), then the retail clear. Ported 1:1: the plugin's copy of
  Lara's table gets a wrapper in slot 2 that does the kill (with `Translate1015Exit=1`) and then always runs the PC
  slot 2. Slot 0 stays the PC's (TU 0x8245fde8 = retail with the index remap 6 -> 7 only).
* **Death kind 0** (static, PC and TU): the switch sets LP 0 and requests EnemyState_Death with data +0x14 = 0,
  +0x19 = 0 (only kinds 5 / 7 set it), +0x1a = 0, +0x1b = 1. The Death Enter (PC tru+0x26c500, TU 0x8232c818) then
  plays the effect "death" (kind 5 would be "vehicle death") and keeps the default orientation instead of the hit
  vector (+0x19 = 0). The PC-only +0x19 call tru+0x218020 is not reached with kind 0 (and does nothing in that path
  anyway). The PC itself uses kind 0 for damage type 0xe. So kind 0 = the same death on both exes.
* **Log:** one line per 1015 exit: `state 1015 slot 2 (...) (call n): ON: target 0x... obj N name, death switch kind 0
  ..., v = x y 0 -> al r; LP a -> b, state S1 -> S2; Lara record k; then the PC clear tru+0x2e66d0` or `off (would):
  target ..., LP a, state S - the TU would switch it to Death kind 0 now ...`, or `no valid target in CM+0x48` (as the
  TU: nothing). With `[Death] Log=1` the 0.6.9 line `0.6.9 death switch: ... kind 0 ... from TruShadowCombat (...)`
  follows the ON line.
* **TO TEST** (hall02, tutorial thrall knocked down, finisher Y (the 742 [1004 1015] -> 743 [1008] chain), TruFight
  trace on; can be combined with the 0.6.11 test):

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.12 ... loaded`; `state 1015 exit (finisher Y kill, ...): building blocks verified, wrapped at Lara's registration - Translate1015Exit 0`; at the level start `machine 1 states: ... 1015 (slot 2, log only)`; no `state 1015 exit: ... does not match` / `machine 1 state 1015 is not ...` line |
| 2 | finisher Y on a downed thrall, `Translate1015Exit=0` | as 0.6.11: **the thrall gets up again** (RegenerateDeath -> Regenerate); log `state 1015 slot 2 ... off (would): target 0x<thrall> ..., LP 0.0 (or the low LP), state RegenerateDeath - the TU would switch it to Death kind 0 now` |
| 3 | the same with `Translate1015Exit=1` (live, TruMenu switch "Finisher Y kill 1015 as TU") | `0.5.1 switch: [States] Translate1015Exit 0 -> 1`; `ON: target 0x<thrall> ..., LP a -> 0.0, state RegenerateDeath -> Death`; **the thrall dies and does not get up again** (chunkdoll / death as after a normal kill; `0.6.9 death switch: ... kind 0 ... from TruShadowCombat`, then `0.6.9 chunk build` if the record has a chunkdoll) |
| 4 | compare 0 / 1 | only 1 kills at the end of 742; with 0 the 0.6.10 / 0.6.11 behaviour stays (thrall regenerates) |
| 5 | when it fires | note the `Lara record` in the line (expected 742 -> the kill comes at the change to 743, i.e. before / at the start of the 1008 move - inferred from the record contents, not measured) |
| 6 | side effects | no `access fault` line; 1015 exits without a target say `no valid target in CM+0x48`; main game finisher Y with 1: the target dies as well (the TU has no level test there) |

0.6.11 (2026-11-11, **offline, not yet seen in game**; Q19 "Lara falls out of the world after the finisher Y in
hall02", main workspace `docs\Befund-Sturz-durch-Welt-1111.md` and `docs\Befund-Translate1008-1111.md`, ENGINE.md 12):
build `work\asi\combat0611`, byte pre-checks `work\asi\combat0611\precheck_0611.txt` (23 checks: the 7 of
`CheckState1008Blocks`, the 14 building blocks it reuses, 2 proof facts; 0 mismatches against `data\pc\tru.exe` and
the installed tru.exe).
* **State 1008 = the finisher Y move** (chart record 743 [1008] under 742 [1004 1015]; `[States] Translate1008`, new,
  live, default **0**). PC = retail: table entry 1008 at tru.exe 0x8b19bc (machine-1 table 0x8b0a50, the push operand
  at tru+0x368b99, entry 141 x 28 bytes) = {0, 0, 0, 0, slot 4 tru+0x36d9a0, 0}; tru+0x36d9a0 (= retail 0x8245bb30)
  only writes gameTracker+0x1270 (facing) / +0x1260 (target +0x20) for targeter 6 - Lara is carried by the
  animation's root motion alone (PC 2026-11-10: +341 / +614 units, 112 / 324 / 346 past the target; at the hall02
  edge she left the floor). TU table 0x82758940: 1008 = {**0x8245f7b0**, 0, 0x82455a38 (`blr`), **0x8245fa40**, 0,
  0}, slot 4 removed. Translated 1:1:
  * slot 0 (enter, TU 0x8245f7b0): handle = tru+0x31c9a0(player, PC slot 6) (= TU 0x823dd138 with 7) kept by the
    plugin (TU agent +0x4f4 / +0x4f8 - its only writer in the state code; a new target list resets it as the 1019
    handle); slot 3 (tick, TU 0x8245fa40): the kept handle when its +0x44 stamp still matches.
  * both: `Busy244` -> channel mode 2 {instance +0x20, (0, 0, 0, 1), animation entry +0x28 - 1.0} (tru+0x38d00,
    stop); no target -> nothing; else face = `FaceTarget(t, 1)` (TU 0x82457b28), point = t +0x20 (player +0x20 for
    `[t+0x14] & 0x400000`), n = tru+0x35f3e0 (TU 0x82463af8 flag 0); n > 0 -> channel mode 3 {face, point, n x 100.0}
    (tru+0x38dc0), else mode 3 with the animation's frame count (tru+0x3e480). Every tick re-aims at the target's
    current position, so the move ends on the target instead of past it.
  * slot 2 = the TU's empty function + the plugin's end line; slot 4 (PC tru+0x36d9a0) runs only with
    `Translate1008=0` (the TU has none; gameTracker+0x1260 / +0x1270 are then not written by 1008, as on the TU).
  * No doppelganger test in either TU function: every level, as the TU. `[Probe] State1008=0` leaves the record as
    the PC's (start only). Not ported: the TU print stub's arguments (they would read address 0x10 for a dead handle).
* **Log:** `state 1008 slot 0 (...) (call n): ON: / off (would): handle taken, target 0x... ; Lara x y z, distance d
  -> path p (...), steering point x y z, frames n`; `state 1008 slot 3 (...) ON tick k (ms): target, path, steering
  point, Lara, distance` (path change, else every 250 ms; 8 lines per run at level 1); `state 1008 slot 2 (...):
  Translate1008 0/1, k ticks, ms; Lara x y z, d units from the enter point; target ... END DISTANCE d (horizontal h)`.
* **Not part of it (other mechanism, evidence in the Befund):** the TU-new exit of 1015 (0x8245fe58) calls the death
  switch (TU 0x823258c8 = tru+0x241650: LP 0, Death) on the 1015 target kept in CombatManager +0x48 / +0x4c, direction
  target -> Lara (z = 0), kind 0 - the kill of the finisher Y's target, not Lara's move; it shares no data with 1008.
* **TO TEST** (hall02, tutorial thrall knocked down near the arena edge at y ~ 8260, TruMenu `combo.trace` /
  TruFight trace on):

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.11 ... loaded`; `state 1008 (finisher Y move, ...): building blocks verified, wrapped at Lara's registration - Translate1008 0`; at the level start `machine 1 states: ... 1008 (slots 0 / 2 / 3 / 4, log only)`; no `state 1008: ... does not match` / `machine 1 state 1008 is not ...` line |
| 2 | finisher Y on a downed thrall, `Translate1008=0` | as 0.6.10 (Lara overshoots); log `state 1008 slot 0 ... off (would): handle taken, target 0x<thrall> ... path 3`, tick lines `off (would)`, end line with END DISTANCE ~300+ |
| 3 | the same with `Translate1008=1` (live, TruMenu switch "Finisher Y 1008 as TU") | `0.5.1 switch: [States] Translate1008 0 -> 1`; slot 0 `ON: ... path 3`; tick lines with the steering point = the thrall's position; end line **END DISTANCE <= ~50**; TruFight: the 743 rows end next to the lying thrall, no fall; at the y ~ 8260 edge Lara stays on the floor |
| 4 | finisher Y with no target / outside a fight (if reachable) | `path 2` (nothing) - root motion as the PC |
| 5 | main game (any level with a finisher Y, `Translate1008=1`) | same steering (the TU has no doppelganger test); no crash |
| 6 | side effects | the thrall still dies / regenerates as before (the kill at the end of 1015 is not ported); no `access fault` line |

0.6.10 (2026-11-10, **offline, not yet seen in game**; K-8b "4th chain punch, type 21, -80 does not knock the thrall
down", main workspace `docs\Befund-K8b-Art21-1011.md`, ENGINE.md 13): build `work\asi\combat0610`, byte pre-checks
`work\asi\combat0610\precheck_0610.txt` (6 checks: 4 the plugin does at load + 2 proof facts; 0 mismatches against
`data\pc\tru.exe` and the installed tru.exe).
* **Knockback speed of Lara's contact hit** (`[Hit] TranslateHitSpeed`, new, live, default **1**; TU
  0x823e169c..0x823e16c8): the sender tru+0x319050 builds the hit message 0x11c with tru+0x23c9b0 (= TU 0x8230afd8:
  argument 5 -> msg+0x44, 6 -> msg+0x48, 7 -> msg+0x40). Retail and the PC push 0 / 0 / 0 (tru+0x319169..+0x31916e);
  the title update passes msg+0x44 = `(int)` A+0x10 (Lara's attack force, `fctiwz f28`) and msg+0x48 = `(int)` A+0x14
  (`fctiwz f29`), A = the attack data `[CombatManager+0xc4]` (eax at that point). The knockback tru+0x220650 (= TU
  0x822f73a8) runs with speed v = msg+0x44 when > 0, else the hit record's s+0x30 (tru+0x220716..+0x22073e); records
  with s+0x30 = 0 - type 21 (the 4th chain punch, 753) and type 26 (775) - therefore never knocked back on the PC: the
  thrall stayed in Hit, the Xbox throws it. 6-byte jump at tru+0x319169 (`6a 00` x 3) -> `HitSpeedStub` + nop: pushes
  0, `cvttss2si` A+0x14, `cvttss2si` A+0x10 (truncation toward zero as `fctiwz`) and returns to tru+0x31916f; FPU
  stack, esp and the pushed count as the PC; no branch targets the overwritten bytes (`pe_dis.py` on
  tru+0x319050..+0x319400, `pe_callers.py` on the whole exe). Switch 0 = push 0 / 0 / 0 (PC). Every other receiver of
  this 0x11c gets the values too, as on the Xbox. NaN / out-of-range forces would give 0x80000000 (`fctiwz`:
  0x7fffffff) - irrelevant for Lara's forces 0..1250.
* **Hit line:** `0.6.7 hit:` (prefix unchanged) now also prints `msg+0x44 <v> msg+0x48 <v>` after `amount` and
  `TranslateHitSpeed <0/1>` at the end - the speed the knockback works with.
* **Still open (not 1:1):** the TU's type-27 substitute record `[CM+0xc8]` of the same block 0x823e160c..0x823e1674
  (the TU copies it over A for type 27 before these arguments) is not ported - the stub reads A as the PC does. Who reads
  msg+0x48 is not searched (guess: the upward share).
* **Effect (inferred):** only hits with s+0x20 = 1 **and** A+0x10 > 0 change: type 21 (753, force 250) and type 26
  (775, force 1250) now knock back; types 23 / 24 / 25 / 27 with force > 0 would take A+0x10 instead of s+0x30 (762 /
  759 / 772 have force 0 today -> unchanged). Types 18 / 19 / 20 / 22 stay Hit (s+0x20 = 0).
* **TO TEST** (hall02, tutorial thrall, `[States] Translate1004=1`, `[Hit] TranslateImpulseGate=1`, `[Hit] Log=1`):

| # | what | expected |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.10 ... loaded`; `0.6.10 hit speed on (tru+0x319169 ...)`; no `0.6.10 hit speed: ... does not match` / `0.6.10 hit speed: not placed` line |
| 2 | 4 x X, `TranslateHitSpeed=1` | `0.6.7 hit: ... type 21 ... msg+0x44 250 ...` -> right after it **`0.6.7 knockback: ... type 21 force 12.0 (companion record +0x40 (TU) ...)`**; TruFight: -80 -> **Fall -> Land -> Getup** (Xbox: 469-1 097 units in 1.1-2.0 s); types 18 / 19 / 20 stay Hit with `msg+0x44 200`, no knockback line |
| 3 | 4 x X, `TranslateHitSpeed=0` (live) | as before: `msg+0x44 0`, no knockback line for type 21, Hit |
| 4 | X X Y / big punch | types 23 / 25 unchanged (`msg+0x44 0`, force 3 or from the record) -> Fall / Splat |
| 5 | shadow pull 775 (type 26) | now a knockback line + Fall (compare Xbox X21 "electrically thrown away") |
| 6 | Xbox counter-check (TruXenia) | 4 x X on the tutorial thrall: `combo: Lara records ...>754>753 ... (-80.0) ... reaction Fall` - a recording with record 753 is still missing |
| 7 | side effects | still no `impulse 0x91` to thralls, no crash at tru+0x319169, death / chunkdoll (PC test package 1 row 5) unchanged |

0.6.9 (2026-11-10, **offline, not yet seen in game**; TODO N18 K-8 / melee kill, main workspace
`docs\Befund-K8-Kombo-1011.md` sections 5 / 6.3, ENGINE.md 13): **log points only - nothing in the game changes**.
Build `work\asi\combat069`, byte pre-checks `work\asi\combat069\precheck_069.txt` (11 checks: 9 the plugin does at
load + 2 facts of the study; 0 mismatches against `data\pc\tru.exe` and the installed tru.exe). Each part calls the
original code with the same arguments and then writes a line; a failed byte check leaves that site untouched.
* **Chunkdoll build of the Death state** (`[Death] Log`, new, live, default **1**): Death slot 8 tru+0x26c950 (TU
  0x8232cd50) builds the chunkdoll with tru+0x296f90(inst) at tru+0x26c9f9 (TU 0x8232ce28 -> 0x823766c0) when the tune
  record (tru+0x214610(brain+0x168), in edi) has +0x46 != 0. The call goes through `ChunkBuildStub`: line `0.6.9 chunk
  build: <enemy> in the Death state ... record +0x46 <n>, +0x48 <n>, +0x4c <f> -> BUILT / not built (al 0); chunkdoll
  count [0xecfc70] <a> -> <b> (limit 8 / 4), physics lock 0x<l>, LP <f>`. Answers "did it shatter" from the log.
* **Hit-list add of Lara's contact hit** (`[Hit] Log`, cap `[Hit] MaxLines`): the sender tru+0x319050 calls the add
  tru+0x2e6990 (thiscall CombatManager, target; 8 slots +0xa4..+0xc0; al = 0 if already in the list or full) at
  tru+0x3190ad; only al = 1 lets the hit message 0x11c out. Through `HitListStub`: line `0.6.9 hit list: contact ->
  <enemy> at Lara record <n>, attack type <A+0xc> damage <A+4> force <A+0x10> -> added in slot k / REFUSED: already in
  slot k / REFUSED: list full ...; list +0xa4 [T - x ...] (T = this target, x = other); <n> repeat(s) ... not logged;
  [States] Translate1004 <0/1>`. Lara's record = machine 1 `[[0xfadb58]+0xf10]`, `[machine+0x510]` as an index in
  `[[machine+4]+0xc]` (as TruMenu `combo.trace`; -1 when the machine check at 0x768c50 fails). The same target / result /
  record again within 1 s is only counted (contacts come every physics step while the fist touches). This is the K-8
  proof: with `Translate1004=0` the fist touches at 755 / 754 / 753 but the list refuses; with 1 it is added.
* **Death switch** (`[Death] Log`): entry hook of tru+0x241650 (= retail 0x82327a18, TU 0x823258c8; 6 bytes into a
  trampoline): line `0.6.9 death switch: <enemy> kind <k> (args ...) from <caller>, LP <f>, state <before> -> <after>
  (switched inside the call / not switched yet), request to brain+0x1254 accepted (al 1) / al 0`. Caller = `death check
  tru+0x220380`, another `tru+0x...`, or `TruShadowCombat (0x...)` for the plugin's own 0.6.1 / 0.6.5 / 0.6.6 calls. The
  call site tru+0x24170b is not patched (TruMenu's `ai.kill` checks those bytes).
* **Study TU 0x823258c8 (death switch) - nothing to translate, no `[Death] TranslateSwitchRequest`:** the TU body is
  retail 0x82327a18 with retail's helper 0x8230e290 inlined. Both end in the same call 0x82349468 (= retail
  0x82349b90)(brain+0x1254, inst, brain+0x11e0, Death 0x82779bf8 / retail 0x82779978, &{data, "EnemyDeathSwitchData",
  0x20}, 0); the rest differs only in stack offsets and shifted constants with equal values. The PC does the same:
  tru+0x241650 -> tru+0x23d6e0 (= 0x8230e290: `ecx = brain+0x1254`, {data, 0x8588b8 "EnemyDeathSwitchData", 0x20}) ->
  tru+0x271d30 (= 0x82349b90: file the request tru+0x271080, then unless the current state's slot +0x40 (inst, 1)
  refuses, machine+4 |= 1 and switch at once tru+0x271c10). So the "request through the behaviour control" is already
  the PC's way; death animation timing, chunkdoll and regeneration cannot change from it. The new death-switch line
  shows live whether the switch happens inside the call. Disassemblies: `work\asi\combat069\analysis`.
* **TO TEST** (hall02, tutorial thrall; `[Hit] Log=1`, `[Death] Log=1`; TruMenu `combo.trace 1` helps):

| # | what | expected log lines |
|---|---|---|
| 1 | game start | `TruShadowCombat 0.6.9 ... loaded`; `0.6.9 log points (nothing changed in the game): chunkdoll build of the Death state on ..., hit-list add of Lara's contact hit on (..., Lara's record read), death switch on ...`; no `0.6.9 ... does not match` |
| 2 | 4 x X, `[States] Translate1004=0` | 752: `0.6.9 hit list: contact -> <thrall> at Lara record 752 ... -> added in slot 0 ...: hit message 0x11c follows`; then at 755 / 754 / 753: `... at Lara record 755 ... REFUSED: already in slot 0 ... list +0xa4 [T - - - - - - -]` = K-8 proven (the fist touches, the list refuses). No hit-list line at 755 at all = the fist does not touch (contact problem, not the list) |
| 3 | 4 x X, `[States] Translate1004=1` (live) | `state 1004 slot 1 ... ON: ... list cleared` before each new record, then `... at Lara record 755 ... added in slot 0` (and 754 / 753); TruMenu `combo:` -40 / -60 like the Xbox |
| 4 | X X Y (with 1004 on and off) | `... at Lara record 760 ... added` (on) / `REFUSED: already in slot 0` (off); combo `752>755>760 ... (-100.0)` with 1004 on |
| 5 | melee kill: knock the thrall down, Y finisher | `0.6.5 death: ... RegenerateDeath hit ... death switch kind 7 and notification 38` -> `0.6.9 death switch: <thrall> kind 7 ... from TruShadowCombat (...), ..., state RegenerateDeath -> Death (switched inside the call) or (not switched yet), request ... accepted (al 1)` (which of the two is the open timing question - both are the PC's = retail's way) -> after the Death timer `0.6.9 chunk build: <thrall> in the Death state ... record +0x46 <n> -> BUILT; chunkdoll count 0 -> 1 (limit 8), physics lock 0x0` + the thrall shatters. `not built` = limit / object test failed (send the log); no chunk-build line at all = the Death state never reached its timer or the record has +0x46 = 0 |
| 6 | other kills (pistol, a punch without regeneration) | `0.6.9 death switch: ... from death check tru+0x220380` or `0.6.6 T5` + `from TruShadowCombat`; then the chunk-build line as in 5 |
| 7 | anything odd | `[Hit] Log=0` and `[Death] Log=0` stop the lines (the hooks still pass through); send `TruShadowCombat.log` |

0.6.8 (2026-11-09, **offline, not yet seen in game**; TODO N18 K-1b, main workspace
`docs\Befund-K1b-Entscheidung-0911.md`, ENGINE.md 13): build `work\asi\combat068`, byte pre-checks
`work\asi\combat068\precheck_068.txt` (7 checks, 0 mismatches against the installed tru.exe).
* **Impulse gate** (`[Hit] TranslateImpulseGate`, live, default **1**; TU 0x823e1870..0x823e1884): Lara's contact-hit
  sender tru+0x319050 (CombatManager in edi, hit instance in ebx, attack data A = `[edi+0xc4]`) sends the hit message
  0x11c and then, when A+0x10 > 0 and no special body was hit, the impulse message 0x91 (tru+0x3192da..+0x319394). The
  title update skips that impulse when `[[inst+0x10]]+4` has bit 0x400000 (enemies with a brain, the thrall too) and
  continues at 0x823e1934 (= PC tru+0x319398); retail and the PC always send it, so on the PC the impulse receiver
  tru+0x224c60 throws the thrall into Fall on every punch. Jump at tru+0x3192da (5 bytes `lea edx, [esp+0x20]; push
  edx`) -> `ImpulseGateStub`; flag set and switch on -> tru+0x319398, else the two moved instructions and back to
  tru+0x3192df (switch 0 = PC). Other impulse senders (weapons, surroundings) are not touched. Side effect: Lara's melee
  no longer reaches the 0.6.1 lethal-impulse path in tru+0x224c60; death comes through 0x11c + the death check, as in
  the TU.
* **Log** (`[Hit] Log`, same cap `[Hit] MaxLines`): per skipped impulse `0.6.8 impulse gate: <enemy> type <A+0xc> force
  A+0x10 <f>, [[inst+0x10]]+4 0x... -> impulse 0x91 not sent (TU 0x823e1870, #<n>, ...)`. Load line `0.6.8 impulse
  gate on (...)`.
* **Hit line label fixed:** `0.6.7 hit:` now prints the subtype msg+0x64 as `sub` (2 for Lara's contact hit, builder
  argument 17 at tru+0x31914b) and msg+0x54 (argument 16, fixed -1 at tru+0x31914d) as `msg+0x54`; 0.6.7 printed
  msg+0x54 under `sub`.
* **Test (hall02, tutorial thrall):** single punches during the thrall's attack with the switch 1 / 0: expected with 1
  `impulse gate` lines, Hit instead of Fall, Fall only for types 21 / 23..27 (records with s+0x20 = 1).

0.6.7 (2026-11-09, **offline, not yet seen in game**; for the combat tests of TODO N18 "Kampf wie Xbox"): K-1 hit
structures + knockback and K-7 chunkdoll limit (main workspace `docs\Befund-K1-Umfallen-0911.md`, ENGINE.md 13). Build
`work\asi\combat067`, byte pre-checks `work\asi\combat067\precheck_067.txt` (15 checks, 0 mismatches against the
installed tru.exe). Switches in `TruShadowCombat.ini` `[Hit]` (live, read again at most once per second through
`kP1dKeys`) and `[Chunk] Limit8` (start only); all default **1**; a switch at 0 runs the PC code.
* **Hit structures** (`[Hit] Translate`, TU 0x82301dc0 = retail 0x823042a8 + instance): the selector tru+0x2159a0
  (cdecl &s, hit message, D) knows damage types 0..16 only; Lara's DLC 2 melee hits are types 18..27, so the PC gives
  them no structure and the decision tru+0x223410 skips its flag tests (heavy reaction every time). The TU first
  searches the companion's hit records (extension 870 / 932 / 944: `[comp+0x2c]` count, `[comp+0x28]` base, 0xc4 bytes
  each, +0 = type == message +0x50) and takes record +0xc; the D+0x758 redirect (tru+0x213c70) and the return (bit 30
  of +0x14) stay. Placed at the selector calls tru+0x223429 (decision, instance = argument 1) and tru+0x23b157 (hit
  reaction, esi). **Not 1:1:** tru+0x24f338 (inside tru+0x24f230 = TU 0x82329810, which got the instance as a new
  argument) gets the instance only on the path from the knockback tru+0x220650 (return 0x6206e8); its callers
  tru+0x24f5ad / tru+0x25215d keep the PC selector.
* **Knockback** (`[Hit] TranslateKnockback`, TU 0x822f73a8, block 0x822f77e4..0x822f783c + fneg 0x822f7894): the force
  factor is record +0x40 of the same companion record (extension 870: 3 for 18-20 / 22 / 25, 9 for 26, 12 for 21, 18 for
  23 / 24 / 27), 3.0 without a record, instead of the PC's fixed 3.0 / -3.0 (tru+0x220940 `fmul qword [0x8415e8]`,
  tru+0x220971 `fld dword [0x845338]`). **Not translated:** the TU's sideways direction for type 25 with a companion
  (0x822f7558..0x822f75bc) and `brain+0x1254 |= 1` before the second call (0x822f788c, not compared with the PC).
* **Chunkdoll limit** (`[Chunk] Limit8`, start only): `cmp [0xecfc70], 4` at tru+0x296fa8 -> 8 as the TU 0x82376700
  (retail 0x823769e0: 4). The counter has no array behind it (only inc tru+0x2970b8 / dec tru+0x296e5c / this compare).
  Was held back until the lethal-impulse translation (0.6.1 `[Chunk] Translate`) was seen live - 09.11.: 5 impulses
  inside the physics step caught, no crash.
* **Log** (`[Hit] Log`, cap `[Hit] MaxLines` 3000): per hit decision `0.6.7 hit: <enemy> type <t> sub <s> amount <a> -
  structure: companion record (TU) / PC table / no structure (flags +0x14 ...) -> HEAVY (knockback) / light (MoveHit)`,
  per knockback `0.6.7 knockback: <enemy> type <t> force <f> (companion record +0x40 (TU) / 3.0 ...)`. Together with
  TruMenu 0.22.10 `combo.trace 1` this shows per hit what happened. Load line `0.6.7: hit structures on ...`.
* **Test (hall02, tutorial thrall):** with `[Hit] Translate=1` punches (type 18) should show `companion record (TU)` and
  flags 0x10000000; compare heavy / light against `Translate=0` (PC: `no structure -> HEAVY` every time).

0.6.6 (2026-11-08, **offline, not yet seen in game**): N4c - T5 (immediate death in the hit reaction) and P1c (the
Vaulted Enter of the title update with the chain that feeds it); `docs\Befund-P1d-Begleiter-0711.md` section 2 rows T5 /
P1c in the main workspace, disassemblies in `work\combat066_0711`. Build `work\asi\combat066`. All three switches
(`TranslateT5`, `TranslateVaulted`, `TranslateVaultedClock`) default **1**, read again at run time (`P1dReadSwitches`, key table `kP1dKeys`, at most once per second from the hooks); the
hooks are placed at the start whenever their byte checks pass, a switch at 0 runs exactly the PC code.
* **T5** (`[Death] TranslateT5`): the enemy hit reaction tru+0x23ad50 (TU 0x823038d8 = retail 0x82305d40; cdecl inst,
  hit data, a3, a4 -> float amount). The TU inserted at its start (0x8230390c..0x82303a78): with a companion, LP <=
  hit amount (+0x4c) and ShouldRegenerate (TU 0x8235ece8 = H1's companion list + the PC tune list) no -> hit direction
  `(data+0x70 ? data+0x10 : [data+0x30]+0x20) - (data+0x72 ? data+0 : inst+0x20)`, z = 0, normalised (TU 0x8213e838:
  zero unless the squared length is finite and > FLT_MIN), for type 0x19 crossed with (0, 0, -1, 0), then the death
  switch tru+0x241650 kind 7 (the same call as H7 / H8) and return the amount - no damage message, no hit animation.
  The companion is only tested for existence: T5 reads no extension field (needs no data fix). Jump at tru+0x23ad82
  (7 bytes) -> `T5Stub`, back at tru+0x23ad89 or the stub's own epilogue (= tru+0x23b312 without brain+0x2c50 = 0, as
  the TU's 0x8230443c). Log `0.6.6 T5: ... lethal hit type .. -> death switch kind 7 as the TU 0x82303a74, direction ..`.
* **P1c** (`[Death] TranslateVaulted`): the TU-only Vaulted Enter 0x8232b630 (PC tru+0x24fcf0 = retail 0x8232cb18) reads
  a new data field +0x44 = the companion step. Six links, placed together or not at all:
  F retail strike record (PC tru+0x31d5cc -> tru+0x245e40): +0x34 = 0 (TU 0x823e0294);
  E finisher 1013 record (tru+0x31d895, the 0.4 site): +0x3c = 0 in every mode (TU 0x823e0e84; 0.4 did it only in
  doppelganger mode);
  A enemy message handler case 0xbe (tru+0x23b421 -> record copy tru+0x245de0): copy +0x3c = incoming +0x34 (TU
  0x8230743c; the TU strike - `StrikeAt`, `[Strike] Translate` - writes its step there);
  B Vaulted switch from a record (tru+0x223fa2 -> tru+0x20ed80): data +0x44 = record +0x3c (TU 0x823044dc);
  D Vaulted slot 3 copier (tru+0x25a4a2 -> tru+0x24d350): copies +0x44 too (TU 0x8232300c);
  C Enter (tru+0x24fdb9, 5 bytes -> `VaultedAnimStub`): state data +0xb8 = step; companion -> brain+0x2c7c = 0x0fffffff
  (the PC never reads that field); step 0 = the PC's own (retail) animation choice; step != 0 = the companion's step
  table entry `[comp+0x20] + (step - 1) * 0x14` when step <= `[comp+0x24]`, else 0 = no animation (TU 0x8232b3f8).
  **Data guard:** the step table is read only from the FIXED extension layout (record count +0x2c <= 64, step count
  +0x24 <= 64, table set, every entry's anim pair < 0x1000). The installed converted files fail it (0x000f0000) - one
  line `0.6.6: extension data not fixed - install work\extfix_0711 / thrall_extension_fix ...`, the PC choice runs.
  Log `0.6.6 vaulted: ... message 0xbe with step n ...`, `... Vaulted Enter step n: companion step table entry 0x...
  (anim pair {a, b}) ...`.
* **K Vaulted clock** (`[Death] TranslateVaultedClock`, needs the chain): the TU lets an enemy that enters Vaulted run
  5 s without slow motion. Globals `[0x82efb458]` = PC 0xe7f088 (as TruShadowPower's dt translation): +0xd4 = 0xe7f15c
  ms counter, +0x100 = 0xe7f188 time multiplier, +0x118 = 0xe7f1a0 slow motion factor (the PC player update does the
  same at tru+0x3228e9 / +0x3229eb). Enter (TU 0x8232b698, in link C): bit 0x10 of brain+0xc clear -> set, clock = now,
  multiplier /= slow motion. Enemy update tru+0x238d40 (TU 0x822db190): after the brain the multiplier is saved (TU
  brain+0x5084); with bit 0x10: now - clock >= 5000 ms -> bit cleared, else multiplier *= 1 / slow motion; restored at
  the end of the main path (TU 0x822db4e0) - not on the brain+8 bit 0x20000 exit (TU 0x822db364, as the TU). brain+0x5080
  / +0x5084 lie in the block the TU added to the brain (TU +0x5088 = PC +0x5030), so the plugin keeps them: clock word
  per instance in a 64-entry table keyed by instance + serial (+0x44); an entry lives only while its bit runs, ends when
  the update clears the bit, when the serial differs (instance reused - unload / level change), or when the table is full
  (oldest dropped, logged); a missing entry = expired. The save is one slot {instance, value, valid} (updates do not
  nest). Sites: call tru+0x238d6f (-> `ClockStartStub`), tru+0x238e76 (11 bytes -> `ClockExitStub`), epilogue
  tru+0x238efb (7 bytes -> `ClockEndStub`); TruMenu's byte-checked ranges tru+0x238d59..0x238d6e / 0x238ed4..0x238ee2
  are not touched. Not translated: the two script commands 0x822d6844 / 0x822d6880 (set / clear). Log `0.6.6 clock: ...
  Vaulted Enter: brain+0xc bit 0x10 set ...`, `... clock ended after n ms ...`.
* **Not in 0.6.6:** Vaulted slot 10 case 0xbe (next step, TU 0x8232be54), slot 11 0x8232c068, Exit 0x8232b930,
  the strike's step queries 0x165..0x167 (TU 0x82308850), and the rest of RegenerateDeath / Regenerate slot 10 (lying
  animation from companion +0x10 on 0x15 / 0x8a - needs the TU's 2-byte RegenerateDeath state data +8 / +9, which the
  PC state lacks; the subtype-2 sound 0x82399b48 (changed against retail 0x82399e98, 4 arguments) - the PC's call of
  the same pattern in the hit reaction, tru+0x23b0cd -> tru+0x2a5dd0, passes 5; pairing not proven).
* Byte checks: 42 used by the plugin + 6 proof-only (`work\asi\combat066\prechecks_combat066.txt`, generated from the
  source by `work\combat066_0711\facts066.py`; 48, 0 mismatches); earlier lists combat01..combat065 545, 0 mismatches.
  No branch of the patched PC functions lands inside a patched range (`work\combat066_0711\branch_into.py`, 9 ranges).
  Imports unchanged (81, KERNEL32 only), exports unchanged.

New writes into game memory (for the TruGuard author):

| when | address | what |
|---|---|---|
| start, checks passed | 0x63ad82 (`.text`, 7) | `jmp rel32` -> `T5Stub` + 2 `nop` |
| start (all six or none) | 0x71d5cc / 0x63b421 / 0x623fa2 / 0x65a4a2 (`.text`, 5 each) | `call rel32` -> `StrikeRecordHook` / `RecCopyHook` / `VaultSwitchStub` / `VaultCopyStub` (were tru+0x245e40 / +0x245de0 / +0x20ed80 / +0x24d350) |
| start (with them) | 0x64fdb9 (`.text`, 5) | `jmp rel32` -> `VaultedAnimStub` |
| run time | message records (ring tru+0x1c0b10) | +0x34 = 0 (F), +0x3c = 0 (E, the 0.4 hook), +0x3c = step (A) |
| run time | Vaulted switch data / its copy | +0x44 = step (B, D) |
| start (with the chain) | 0x638d6f (`.text`, 5) / 0x638e76 (11) / 0x638efb (7) | `call rel32` -> `ClockStartStub` (was tru+0x2e7710); `jmp rel32` + 6 `nop` -> `ClockExitStub`; `jmp rel32` + 2 `nop` -> `ClockEndStub` |
| run time | Vaulted state data, brain | state data +0xb8 = step; brain+0x2c7c = 0x0fffffff (companion); brain+0xc bit 0x10 set (Vaulted Enter) / cleared (5 s later, enemy update) |
| run time | 0xe7f188 (time multiplier, `.data`) | Vaulted Enter: /= [0xe7f1a0]; enemy update: saved, *= 1 / [0xe7f1a0] while the clock runs, restored at the end (every enemy update while the clock part is on) |
| run time | - | game function calls on the game thread: death switch tru+0x241650 (T5), ShouldRegenerate tru+0x27f040, record builders tru+0x245e40 / +0x245de0, SwitchToVaulted tru+0x20ed80, copy tru+0x24d350 |

| # | TO TEST 0.6.6 (hall02 tutorial thralls; **extension test tree `work\extfix_0711\testtree\mods` installed** for P1c) | expected |
|---|---|---|
| 1 | load, read `TruShadowCombat.log` once | `TruShadowCombat 0.6.6 (`, `0.6.6: T5 on (...), P1c Vaulted chain on (...), clock on (...)`, no "does not match" |
| 2 | kill a tutorial thrall with a non-regenerating lethal hit (finisher 1013, a type outside the regenerate lists) while it stands | `0.6.6 T5: ... lethal hit type .. with companion, ShouldRegenerate no -> death switch kind 7 ...`; the thrall dies at once (no hit animation) |
| 3 | lethal hit with a regenerating type (combo 18..24, heavy) | no T5 line; `0.6.3 death: ... notification 33` / RegenerateDeath as in 0.6.5 |
| 4 | `[Strike] Translate=1`, shadow strike on a thrall | `0.6.6 vaulted: ... message 0xbe with step n`, `... Vaulted Enter step n: companion step table entry ...`; the thrall plays the step animation of its extension. With the old (unfixed) files: one `extension data not fixed` line, PC animation |
| 5 | main game finisher / strike (no companion) | no `0.6.6 vaulted` step lines (step 0 = PC choice), finishers as before |
| 6 | an enemy enters Vaulted (finisher / strike), shadow slow motion on | `0.6.6 clock: ... Vaulted Enter: brain+0xc bit 0x10 set ... time multiplier a -> b`; the enemy moves at normal speed for 5 s, then `... clock ended after ~5000 ms`; without slow motion (factor 1) nothing visible |
| 7 | trouble | `[Death] TranslateVaultedClock=0`, `TranslateT5=0` / `TranslateVaulted=0` (live); send the log |

0.6.5 (2026-11-07, **offline, not yet seen in game**): P1d - the thrall's companion instance (T4) and the title-update
code that hangs on it (`docs\Befund-P1d-Begleiter-0711.md` section 3 in the main workspace; T1 / T2 of
`Befund-Thrall-Felder-0611.md`, T-M3 of `Befund-P1b-MeleeAttack-0711.md`, notifications 34 / 38 of
`Befund-Hall02-Tutorial-Stufe2-0711.md`). Build `work\asi\combat065`. Every part default **1**, every switch read again
at run time (at most once per second, from the hooks); the hooks are placed at the start whenever their byte checks
pass, a switch at 0 runs exactly the PC code.
* **H0 companion** (`[Companion] Translate` / `Log`): the TU builds a companion instance in the enemy init (TU-only
  0x822da800): the first child of the thrall object's id list `[[inst+0x10]+0x2c]` whose object table entry (0xdb7400,
  state 2) has data `[o+0x5c]` of type 0x3d (u16 +2) and `[o+0x60]` != 0 - 870 (viking / tutorial viking), 932 (yeti),
  944 (armoured yeti); 1007 is type 0x3b (chunkdoll), not it. Its readers (0x822da918) only ask "is it there" and take
  its data (= `[o+0x5c]`, PC tru+0x1ba84c). The PC loads these objects already but makes no instance. The plugin answers
  the readers' question from the object table on every use and keeps nothing. `[o+0x60]` is the object's name pointer
  on the PC (tru+0x1bf0fb) - set for every loaded object (the open point of the finding). Log: one line per thrall
  instance the first time a hook sees it, `0.6.5 companion: 0x... obj 1004 viking_thrall_tutorial_dlc2_ serial ...
  (first seen: MeleeAttack slot 13) - companion object 870 viking_thrall_dlc2_extension, data 0x... (type 0x3d), byte
  +0x18 = 0, regeneration list count 1, entry 0 {2, 0, 0}; children: ...` or `- none: <reason>; children: <id reason,
  ..>` (max 400).
* **H6 notification 34** (`[Death] TranslateNotify34`): RegenerateDeath slot 12 (Exit, vtable 0x85b104 = tru+0x27eeb0,
  retail 0x8235ea38) = TU 0x8235e338 = the same body + `PlayNotification(34)` - every time an enemy leaves
  RegenerateDeath. No companion needed. hall02: closes the finisher hint `hint_17` (23101 f3, f4).
* **H7 / H8 finisher 38** (`[Death] TranslateNotify38`): the TU-new first block of RegenerateDeath slot 10 (vtable
  0x85b0fc = tru+0x282490, TU 0x8235e3a8) and Regenerate slot 10 (0x85b15c = tru+0x282680, TU 0x8235e998): hit message
  0x11c with data, a companion and type 16 (or type 1 subtype 1) -> death switch kind 7 (tru+0x241650 with the vector
  (0, 0, 1, 0) of TU 0x8207db00, the same switch as 0.6.1) and `PlayNotification(38)`, return 1; else the PC handler.
* **H1 regeneration list** (`[Death] TranslateRegenList`): ShouldRegenerate (TU 0x8235ece8, PC tru+0x27f040 = retail)
  asks the companion's list (+0x40 / +0x44, entries {type -1 any, subtype 0 any, flag bit 0}; the three extensions: 1
  entry {2 Heavy, 0, 0}) after the same preconditions and before the tune list. The three calls tru+0x2203e4 (death
  check), tru+0x2824b9 (RegenerateDeath slot 10), tru+0x2826d3 (Regenerate slot 10) go to the plugin; the function is
  not patched (TruMenu byte-checks its head and calls it).
* **H3 / H4 / H3b T2 Land** (`[Death] TranslateLand`): Land slot 9 (tru+0x25afe0, TU 0x82328aa0) with LP <= 0 and a
  companion whose data byte +0x18 is 0 -> notification 33 (only with `[Death] TranslateNotify33=1`) and RegenerateDeath
  with the 2-byte data {([state data+0x30] >> 1) & 1, 1} (TU 0x8230c050 = PC tru+0x23d4a0 with 0x8afa4c, the helper of
  the Getup branch beside it; the PC's RegenerateDeath copies / reads no transition data), else LandDeath as before.
  Jump at tru+0x25b181. Land slot 13 (vtable 0x858c90 = tru+0x241d30, TU-only 0x82329060): with a companion
  RegenerateDeath and Death may interrupt Land (6; PC -1 - the state machine tru+0x271080 would refuse T2's switch, so
  T2 is placed only with it). Land exception of T3 (TU 0x822f6654, in the 0.6.3 hook): a lethal regenerate hit while
  in Land sends 33 but switches nothing (return 0) - the landing decides.
* **H5 T-M3** (`[Melee] TranslateInterrupt`): MeleeAttack slot 13 (vtable 0x859160 = tru+0x242f40, TU 0x82330830):
  where the PC answers -1, Vaulted (0x8ae8bc) and - with a companion - RegenerateDeath may interrupt too, answer
  tru+0x270400(next) = `[next+4]` (read: `next ? [next+4] : 0`).
* **33 + 34 + 38 belong together**: the shipped .ini has all three at 1. 33 alone (0.6.3 / 0.6.4) opens the finisher hint
  and nothing closes it (hall02 run 1, 07.11.); with 34 it closes when the thrall stands up or dies, with 38 at once on
  the finisher. Keep `TranslateNotify33=0` in the game .ini only while 34 / 38 are off.
* **Not in this build:** T5 (TU 0x823038d8: companion + lethal + not regenerating -> death kind 7 at once), the rest of
  RegenerateDeath / Regenerate slot 10 (0x15 / 0x8a with companion: lying animation from data +0x10; the sound
  0x82399b48; Regenerate 0x15 only without data), P1c (Vaulted Enter 0x8232b630) - P1c / T5 read the extensions'
  stage table +0x20 / +0x24 and the 0xc4 records +0x28 / +0x2c, which the converter got wrong (count 0x000f0000 instead
  of 15): data fix of 870 / 932 / 944 first.
* Byte checks: 36 used by the plugin + 9 proof-only (`work\asi\combat065\prechecks_combat065.txt`, generated from the
  source by `work\combat065_0711\facts065.py`; 45, 0 mismatches); earlier lists combat01..combat064 500, 0 mismatches.
  Imports unchanged (81, KERNEL32 only), exports unchanged.

New writes into game memory (for the TruGuard author):

| when | address | what |
|---|---|---|
| start, checks passed | 0x85b104 (`.rdata`, 4 bytes) | RegenerateDeath vtable slot 12: 0x67eeb0 -> `RdExitHook` |
| start | 0x85b0fc (`.rdata`, 4) | RegenerateDeath slot 10: 0x682490 -> `RdMsgHook` |
| start | 0x85b15c (`.rdata`, 4) | Regenerate slot 10: 0x682680 -> `RgMsgHook` |
| start | 0x858c90 (`.rdata`, 4) | Land slot 13: 0x641d30 -> `LandIntHook` |
| start | 0x859160 (`.rdata`, 4) | MeleeAttack slot 13: 0x642f40 -> `MeleeIntHook` |
| start | 0x6203e4 / 0x6824b9 / 0x6826d3 (`.text`, 5 each) | `call rel32` 0x67f040 -> `RegenListHook` (all three or none) |
| start | 0x65b181 (`.text`, 6) | `jmp rel32` -> `LandStub` + `nop` (only with the Land slot 13 entry) |
| run time | - | no data writes; calls of game functions on the game thread: PlayNotification tru+0x37a540 (34 / 38 / 33), death switch tru+0x241650 (kind 7), state switch tru+0x23d4a0 (RegenerateDeath) |

All `.rdata` / `.text` writes through `VirtualProtect` (old protection restored) + `FlushInstructionCache`, once at
the start. Note for TruMenu: its ai.kill check list holds `{0x006203e4, "e857ec0500 ..."}` - it runs when TruMenu
loads (before this plugin, alphabetical), so it still passes; a later re-check would see the H1 call.

| # | TO TEST 0.6.5 (hall02 tutorial thralls, TruMenu `[Debug] EnemyStateLog=1`, game .ini `[Death]` 33 / 34 / 38 = 1) | expected |
|---|---|---|
| 1 | load, read `TruShadowCombat.log` once | `TruShadowCombat 0.6.5 (`, `0.6.5 companion: lookup ready ...`, `0.6.5: H6 notification 34 on, H7 / H8 finisher 38 on / on, H1 regeneration list on (3 of 3 calls), H4 Land slot 13 on, H3 T2 Land on, H3b Land exception on, H5 T-M3 on`, no "does not match" |
| 2 | first tutorial thrall attacks | one `0.6.5 companion: ... obj 1004 ... companion object 870 ... type 0x3d ... byte +0x18 = 0, regeneration list count 1, entry 0 {2, 0, 0}` per thrall (or `none: <reason>` - send the line) |
| 3 | knock a thrall down so that it regenerates (finisher hint appears) | `0.6.3 death: ... notification 33 sent`; `hint_17` shows |
| 4 | let it stand up | `0.6.5 death: ... leaves RegenerateDeath: notification 34 sent`; the hint closes, the punch / kick hint comes back |
| 5 | next thrall down, finisher (type 16 hit) while it lies | `0.6.5 death: ... RegenerateDeath hit type 16 ... -> death switch kind 7 and notification 38`; thrall dies, hint closes at once |
| 6 | punch + kick afterwards | `tutorial` goes to 2 (TruMenu hall02 counter), wall opens after the next kill |
| 7 | heavy attack as the last hit | `0.6.5 regen: ... companion regeneration list entry 0 -> ShouldRegenerate yes` - the thrall regenerates instead of dying |
| 8 | thrall killed in the air / on landing | `0.6.5 land: ... lands with LP <= 0, companion byte +0x18 = 0: notification 33 sent, RegenerateDeath ...` (not LandDeath); with the lethal hit in Land first `0.6.3 death: ... no switch in Land` |
| 9 | trouble | switch the part off (TruMenu Fixes page or the .ini, live): `TranslateNotify38`, `TranslateLand`, `TranslateRegenList`, `[Melee] TranslateInterrupt`, `[Companion] Translate`; send the log |

0.6.4 (2026-11-07, **offline, not yet seen in game**): P1b - the title update's three small changes to the enemy state
`MeleeAttack` (T-M1..T-M3 of `docs\Befund-Thrall-MeleeAttack-Freeze-0711.md` section 4; full proof
`docs\Befund-P1b-MeleeAttack-0711.md` in the main workspace), T-M1 and T-M2 translated. Build `work\asi\combat064`.
The thrall freeze in MeleeAttack itself was a data bug (combo link record, `tools\melee_link_record_fix.py`); this
version does not touch it.
* State object 0x8aea00 "MeleeAttack", vtable 0x85912c = retail vtable 0x8206d160 / TU 0x8206d450 (18 slots). State
  data `(brain+0x1273 + ([brain+0x18d4+4i] + 2i) * 0x19c) & ~0xf` on all three exes (TU writes it as brain+0x1254 +
  0x680 / +0x1f), record = `[data+0x50]`. Update tru+0x265f10 and the follow-up helper tru+0x25bc10 are TU = retail =
  PC; the anim callback tru+0x225c60 sends 0x15 with data 0.
* **T-M1** message slot tru+0x266350 (retail 0x82331c28, TU 0x82330d40): retail / PC set data+0xa4 = 2 (= leave the
  attack) on 0x15 / 0x8a always and on 0xbe unless its data points at the instance; the TU (0x82331164..0x8233117c)
  only when the message data pointer is 0. The plugin points jump table tru+0x26672c entries 0 (0x15 / 0x8a) and 5
  (0xbe) at a stub: data != 0 -> switch default tru+0x266721 (return 0 = TU 0x82331578), data == 0 -> tru+0x2663c7
  (PC code unchanged). The byte table is checked: index 0 = exactly 0x15 / 0x8a, index 5 = exactly 0xbe.
* **T-M2** Enter slot tru+0x25c7b0 (retail 0x82330a88, TU 0x8232fb48): the TU added after the "record+8 bit 24 ->
  brain+8 |= 0x800000" step (PC tru+0x25c9da -> tru+0x2224c0) `if (!(record+8 & 4)) brain+0xc |= 1`
  (0x8232fd6c..0x8232fd8c) - the bit message 0xcb sets (PC tru+0x26670e = TU 0x8233155c) and 0xd1 clears. The plugin
  jumps from tru+0x25c9ea (10 bytes moved) into a stub with that test, back at tru+0x25c9f4.
* **Not translated: T-M3** (interruption slot 13, TU 0x82330830 / PC tru+0x242f40): the TU also lets Vaulted (TU
  0x82779bb0 = PC 0x8ae8bc) and RegenerateDeath interrupt - the latter only with the companion instance (TU
  0x822da918 = T4, missing on the PC). Belongs to the finisher / regeneration package T1-T4.
* `[Melee] Translate=1` (default **1**, a pure TU translation with proven twins); 0 = nothing patched. Read at the start
  only. Log lines (max 300 each): `0.6.4 melee: ... MeleeAttack message 0x15 with data 0x... ignored as the TU
  0x82331164 ...` and `0.6.4 melee: ... MeleeAttack Enter, record+8 bit 2 clear -> brain+0xc |= 1 as the TU 0x8232fd8c
  (bit was 0)`.
* New byte checks: 12 used by the plugin + 6 proof-only (`work\asi\combat064\prechecks_combat064.txt`, 18, 0 mismatches
  on the Steam exe); the earlier lists (combat01..combat063, 482 checks) still 0 mismatches. Imports unchanged (81,
  KERNEL32 only).

| # | TO TEST 0.6.4 (DLC 2 `dlc_yggdrasil_end` or hall02, God Mode; TruMenu `[Debug] EnemyStateLog=1`) | expected |
|---|---|---|
| 1 | load | `0.6.4 melee: [Melee] Translate 1 - T-M1 on ..., T-M2 on ...`, no "does not match" |
| 2 | let thralls attack (MeleeWindup -> MeleeAttack) | each attack ends with `FinishAttack` as before; `0.6.4 melee: ... MeleeAttack Enter, record+8 bit 2 clear ...` lines for records without flag bit 2 |
| 3 | watch for `message 0x.. with data` lines | note count / message (which PC sender passes data is not known; the normal anim end has data 0) |
| 4 | trouble | `[Melee] Translate=0`, restart |

0.6.3 (2026-11-07, **offline, not yet seen in game**): P1a - script notification 33 of the title update's thrall
death (T3 of `docs\Befund-Thrall-Felder-0611.md` 3.2; full proof `docs\Befund-P1a-ThrallTod-0711.md` in the main
workspace) and K14 on by default. Build `work\asi\combat063`.
* The enemy death check tru+0x220380 (retail 0x822f8c88, TU 0x822f6578) runs from the damage case tru+0x237630
  (flags bit 0): LP <= 0 -> ShouldRegenerate tru+0x27f040 -> yes: EnterRegenerateDeath tru+0x282780 (= retail
  0x8235efd8, state RegenerateDeath 0x8afa4c). The TU sends `TRScriptUnitManager::PlayNotification(33)` (TU 0x8247b0f0
  with `[0x829ca684]` = PC tru+0x37a540 with `[0xfae880]`, the pair of the script event handler TU 0x82473928 / PC
  tru+0x368a20) right there, before its query 0x182 / state switch. hall02's level script 23101 f3 answers 33 with
  the finisher hint `hint_17` (once, sticky +188); the wall does not wait for 33.
* `[Death] TranslateNotify33=1` (default **1**, a pure TU translation): the call at tru+0x2203fb goes to the plugin,
  which sends 33 and then calls tru+0x282780 with the same arguments (result unchanged). 0 = only the call (PC). Read
  again at run time at most once per second when the site is reached. One log line per such hit (max 1000):
  `0.6.3 death: 0x... obj 1004 viking_thrall_tutorial_dlc2_ lethal hit, ShouldRegenerate yes (LP -17, state not Land):
  notification 33 sent (TU 0x822f6638); then RegenerateDeath tru+0x282780 (PC)`.
* **Not translated (needs T4):** the TU's Land path T2 (TU 0x82328aa0, PC tru+0x25afe0) sends 33 and switches into
  RegenerateDeath only when the thrall's companion instance (TU 0x822da918: handle brain+0x5090 / +0x5094, set up by
  TU-only 0x822da800) exists and its data byte +0x18 is 0; without it the TU switches to LandDeath, exactly as the PC.
  The PC brain is 0x5040 bytes, it has no companion. T3's "no switch in Land" exception only makes sense together with
  T2, and the TU's own switch feeds its changed RegenerateDeath state (2-byte data, Enter 0x8235dff8) - both stay PC.
  The log names the Land case (`state Land ... the TU would not switch in Land`).
* `[Damage] Translate` (K14) now defaults to **1** (code and sample .ini): pure TU translation, live 07.11. (-40 per hit,
  the tutorial thralls die, the hall02 wall breaks).
* New byte checks: 6 used by the plugin + 10 proof-only (`work\asi\combat063\prechecks_combat063.txt`, 16, 0
  mismatches on the Steam exe); the earlier lists 88 + 6 + 21 + 4 + 13 + 12 + 11 = 155 still 0 mismatches. Imports
  unchanged (81, KERNEL32 only); exports unchanged (4).

| # | TO TEST 0.6.3 (DLC 2 hall01 / hall02 tutorial thralls; TruDlc2Player `TrackerFlag=1`) | expected |
|---|---|---|
| 1 | load | `0.6.3 death: tru+0x2203fb ... -> plugin - [Death] TranslateNotify33 1`, `0.6 damage switch (start): extend`, no "does not match" |
| 2 | kill a tutorial thrall with Lara's DLC 2 attacks (type 0 / 18..24 = regenerate list) | `0.6.3 death: ... ShouldRegenerate yes ... notification 33 sent`; the thrall goes to `RegenerateDeath` (TruMenu label); the finisher hint `hint_17` appears once |
| 3 | `[Death] TranslateNotify33=0`, next thrall | `0.6.3 switch: ... 1 -> 0`, `no notification`; no hint |
| 4 | trouble | `[Death] TranslateNotify33=0` |

0.6.2 (2026-11-07, **offline, not yet seen in game**): K9 - `CombatManager::MeleeSplashDamage` tru+0x2e68b0 as the
title update (TU 0x823e1220, retail 0x823dedc0; `docs\Befund-TU-K9-K11-0711.md` in the main workspace). Build
`work\asi\combat062`.
* The function (event dispatcher tru+0x316f30 case 75) calls the area damage tru+0x29f1e0 (TU 0x8237ae88) once per
  splash record of the current attack; argument 13 is the damage type (`[CM+0xc4]+0x0c`), which becomes +0x50 of the
  hit message 0x11c and so the type K14's switch sees. The TU added (a) in doppelganger mode (gameTracker+0x1244) the
  type remap through the extension's pair table (object 858, DTP 22497 +0xf0 +0x78 -> +0x1b0: **0x1a -> 0x10,
  0x10 -> 0x16**) and (b) always the main target (handle CM+0x48) as an 18th argument, which the area function skips
  right after its self test (TU 0x8237af64). Both are missing on the PC and in the upstream build.
* `[Splash] Translate=1` (default **1**): the call at tru+0x2e692d goes to the plugin (remap argument 13 in place, note
  the main target via the game's handle resolver tru+0x1b39d0, then jump into tru+0x29f1e0 with the original return
  address); the loop test tru+0x29f224 (`cmp esi, edi; je next`, 8 bytes) goes to a stub that also skips the noted
  target, only in calls returning to tru+0x2e6932 - the nine other callers of tru+0x29f1e0 stay unchanged (the TU's
  other callers pass 0). The remap runs only while the K14 switch is extended (`[Damage] Translate=1`): 22 is a type
  only the TU switch accepts. Without it the doppelganger records keep their type (`HELD BACK` in the log).
* The pair table comes from the loaded object 858 (PC twin of the TU's extension instance data, as the target list /
  TruShadowPower). The converted file holds three of the four words unswapped (+0x1b0 / +0x1b8 / +0x1bc read
  0x1a000000 / 0x10000000 / 0x16000000 in every PC tree); `[Splash] Fallback=1` (default) then uses the Xbox values and
  logs it (`0.6.2 splash table: ... FALLBACK`). Data fix pending (converter).
* `[Splash] Log=1`: burst lines every 2 s, e.g. `0.6.2 splash: x2 record type 26 -> 16 - doppelganger mode: REMAPPED
  as TU 0x823e1220, table Xbox values (FALLBACK ...); main target 0x... obj 1004 viking_thrall_tutorial_dlc2_; enemy
  switch as TU (0..27): damage + death check` and `... area hit(s) on the main target held back`.
* New byte checks: 11 (`work\asi\combat062\prechecks_combat062.txt`); with 88 + 6 + 21 + 4 + 13 + 12: 155, 0
  mismatches on the Steam exe. Imports unchanged (81, KERNEL32 only); exports unchanged (4).

| # | TO TEST 0.6.2 (DLC 2 hall01 / hall02 tutorial thralls; TruDlc2Player 0.4 `TrackerFlag=1`) | expected |
|---|---|---|
| 1 | load | `0.6.2 splash: tru+0x2e692d (...) and tru+0x29f224 (...) -> plugin - [Splash] Translate 1`, no "does not match" |
| 2 | `[Damage] Translate=0`: shadow moves (1018) / 1015 near several thralls | `0.6.2 splash:` lines `HELD BACK - damage switch is the PC's`, types unchanged; `held back` lines when the main target stood in the radius |
| 3 | `[Damage] Translate=1`: the same | `0.6.2 splash table: ...` once; `type 26 -> 16` / `type 16 -> 22` `REMAPPED`; K14 lines `type 22 ... switch as TU: damage + death check` for the splash victims |
| 4 | trouble | `[Splash] Translate=0` (PC splash at the next splash) |

0.6.1 (2026-11-07, **offline, not yet seen in game**): the fatal `ChunkDoll: failed to create geom` after a thrall
death with `[Damage] Translate=1` (`docs\Befund-ChunkDoll-Physikschritt-0711.md` in the main workspace). Build
`work\asi\combat061`.
* Chain (PC, code + live stack 07.11.): `PhysicsSystem::Step` tru+0xf0ab0 sets the lock `[phys+0x20f8] = 3` -> contact
  pairs tru+0x6d200 -> pair callback tru+0x92980 (geometry types 3 / 9) -> message 0x26 to Lara -> CombatManager contact
  hit tru+0x319050 sends the damage message 0x11c (with K14 the thrall's LP drops to <= 0) and then the impulse message
  **0x91** to the enemy -> enemy handler tru+0x23b330 case 0x91 -> **tru+0x224c60**: LP <= 0 and a chunk record ->
  chunkdoll create tru+0x296f90 **at once** -> rigid body tru+0x97270 -> `AllocBody` refuses inside the step (lock bit
  0) -> fatal. Live 12:12 the lock read 3, 13 of 405 bodies used.
* The TU changed exactly this branch (retail 0x82307ea8 -> TU 0x82305ba0, same size): no chunkdoll there any more;
  unless the enemy is already in a death state (TU 0x82324700: Death, LandDeath, DeferredInstantDie, DrownDeath, Fade =
  PC tru+0x240e90 on `[brain+0x125c]`) it computes the hit vector (TU 0x8230e5c0 = PC tru+0x256430, from a zero
  vector) and calls the death switch (TU 0x823258c8 = PC tru+0x241650) with (1, 0, 1, **kind 7**, 1); otherwise the
  hit-reaction path. The chunkdoll then comes from the Death state's per-frame slot 8 (tru+0x26c950 = TU 0x8232cd50,
  same record check) in the enemy update - outside the physics step.
* `[Chunk] Translate=1` (default **1**, a pure TU translation): the first instruction of the PC branch (tru+0x224caa,
  `mov eax, [edi+0x168]`, 6 bytes) jumps into the plugin, which runs the TU branch with the game's own functions and
  continues at the hit-reaction path tru+0x224ccd or the function's epilogue tru+0x224cf1. `Translate=0` (read again at
  run time at most once per second when the branch is reached) runs the moved instruction and the PC branch unchanged.
* `[Chunk] Log=1` (default, changes nothing): burst lines every 2 s from an own thread, per enemy / outcome:
  `0.6.1 chunk: 0x... obj 1004 viking_thrall_tutorial_dlc2_ x1 lethal impulse (message 0x91, tru+0x224c60) at LP -17,
  physics lock 0x3 (INSIDE the physics step), chunk record yes: TU: death switch (Death, kind 7) - chunkdoll left to
  the Death state (PC alone: chunkdoll NOW, bodies refused in the step -> fatal)`. `[Chunk] MaxLines=2000`. With
  `Translate=0` and `Log=0` nothing is patched.
* New byte checks: 12 (`work\asi\combat061\prechecks_combat061.txt`); with 88 + 6 + 21 + 4 + 13: 144, 0 mismatches on
  the Steam exe. Imports unchanged (81, KERNEL32 only); exports unchanged (4).
* Not here: the swapped piece records of `viking_thrall_chunkdoll_dlc2_` (DTP 24559 +0x130 / +0x158) and
  `yeti_thrall_armored_chunkdoll_dlc_2_` (DTP 26190 +0x150) are a converter fix.

| # | TO TEST 0.6.1 (fresh start, DLC 2 hall01 / hall02 tutorial thralls, `[Damage] Translate=1`) | expected |
|---|---|---|
| 1 | load | `0.6.1 chunk: tru+0x224caa (...) -> plugin - [Chunk] Translate 1 (...)`, no "does not match" |
| 2 | kill every tutorial thrall (combo / shadow moves) | no fatal; `0.6.1 chunk:` lines with `physics lock 0x3 (INSIDE the physics step)` and `TU: death switch`; pieces appear (TruTrace births, caller 0x00696bde) shortly after the death |
| 3 | population 0 | the hall02 wall breaks |
| 4 | trouble | `[Chunk] Translate=0` (PC branch at the next lethal impulse) |

0.6 (2026-11-06, **offline, not yet seen in game**): K14 - the damage-type switch of the enemy damage function
tru+0x237590 (TU 0x822f60e0, retail 0x822f87d8; `docs\Befund-K14-Schadensarten-0611.md` in the main workspace).
Build `work\asi\combat06`.
* The function (cdecl: instance, hit vector, float amount, bool, **type**, subtype, flags) switches over the damage
  type: PC / retail bound 16, byte table 0x6376c4 -> jump table 0x6376b8 with three case bodies (damage + death check
  0x637630, stamina 0x637685, nothing 0x6376b1). The TU bounds it at 0x1b and its 28-word table adds **17 -> nothing,
  18..27 -> damage + death check** (the same case body); 0..16 are unchanged. Lara's DLC 2 attack records
  (`doppelganger_casual` DTP 20212, activity 1005 -> CombatManager+0xc4, record +0x0c, `tools/chart_attack_damage_types.py`)
  use 17..27 for most hits (18..25 for the combo steps, 26 / 27 for the shadow moves of state 1018), so on the PC
  those hits never reach the health component nor the death / regenerate check (tru+0x220380, LP <= 0) - no damage,
  no `Hit`, no `RegenerateDeath`. The finisher's own records (types 1 / 4) and the shadow step (17) are not affected.
* `[Damage] Translate=1` (default **0**): the byte-table operand of `movzx edx, byte [esi + table]` (tru+0x237625)
  points at a 28-entry table in the plugin (TU mapping), then the bound byte tru+0x23761b becomes 0x1b - jump table
  and case bodies stay the game's. Table first, bound last (off: bound first), so every intermediate state is a valid
  switch. Read again at run time at most once per second while hits come (from the entry hook, before the original
  runs); bytes that are neither the game's nor ours freeze the switch (logged).
* `[Damage] Log=1` (default, **changes nothing**): entry hook on tru+0x237590 (5 bytes -> trampoline, the original
  runs with the same arguments). Per target / type / subtype / caller it counts the hits and writes burst lines every
  2 s while hits happen (a flush thread; no game memory read or written there):
  `0.6 damage types: 0x... obj 1004 viking_thrall_tutorial_dlc2_ type 19 sub 2 x3 via hit message 0x11c
  (tru+0x23aaa0), amount 40.0, flags 0x3, LP 500 -> 500: PC: DROPPED (above the bound) (TU: damage + death check)`.
  Callers named: hit message (tru+0x23aaa0, type = message +0x50), kill (tru+0x2376e0, amount = LP), fall
  (EnemyState_Fall tru+0x25adb0, type 8). `[Damage] MaxLines=3000`. With `Log=0` and `Translate=0` the function is not
  touched (then a later `Translate=1` needs a restart).
* New byte checks: 13 (`work\asi\combat06\prechecks_combat06.txt`); with 88 + 6 + 21 + 4: 132, 0 mismatches on the
  Steam exe. Imports: `CreateThread`, `Sleep` added (81, KERNEL32 only); exports unchanged.

| # | TO TEST 0.6 (DLC 2 hall01 / hall02 tutorial thralls, god mode, `[Debug] EnemyStateLog=1` in TruMenu) | expected |
|---|---|---|
| 1 | load | `0.6 damage: entry hook tru+0x237590 placed ...`, `0.6 damage switch (start): the game's ...` |
| 2 | `Translate=0`: punch / kick / shadow move on a thrall | `0.6 damage types:` lines; types 18..27 with `DROPPED`, LP unchanged |
| 3 | `Translate=1` (INI, no restart) | `0.6 switch: [Damage] Translate 0 -> 1`, `damage switch (run time): EXTENDED ...`; LP drops, `Hit`; lethal hit with 18..24 -> `RegenerateDeath` -> `Regenerate`, others -> `Death` |
| 4 | trouble | `Translate=0` (restored at the next hit) or `Log=0` + `Translate=0` and restart |

0.5.3 (2026-11-05, **offline, not yet seen in game; read-only - behaviour unchanged**): a data export for TruMenu
0.13's thrall labels (debug view stage S1) and one fix of the 0.5.2 diagnostics. Build `work\asi\combat053`.
* Export `DWORD __cdecl TscTargeterSnapshot(DWORD tuIndex, void *out, DWORD outSize)`: tuIndex 9 only; copies
  `TscTargeterSnapshotV1` (version 1, 604 bytes; `static_assert` in both plugins): targeter 9, its target object
  (+0x90), flags / candidates / groups / bucket counts / rejected count, up to 24 list entries {instance, where = 0x10 +
  group (bucket) or 0x20 (rejected), the last WHY result for rejected ones (0x100 = eligibility passed, low byte = filter
  groups passed; 0xffffffff = not evaluated), its tick, marker data}, the player's 8-slot hit list
  `[[0xfadb58]+0x504]+0xa4`, the last condition 2011 (calls, tick, path, result, query 0x161, target). Returns 1 = a copy
  from the game thread, 0 = none (the first 8 bytes always carry size and version). Every call marks "asked"; the copy
  is built at the end of slot 9's per-frame update (after the original) only while a reader asked within 2 s, under a
  sequence counter. No game data written, no game function called for it. `[Diag] Snapshot=1` (0 = the export answers
  "none"); needs `[Diag] Targeter9=1`.
* Fix: `WHY rejected` walked the rejected list by node +0 - that is the **prev** link (list append tru+0x2ecd40: tail +4
  -> new node, new node +0 = old tail; the select walk tru+0x3166f3 reads `mov esi, [esi+4]`), so 0.5.2 reported only the
  first rejected candidate. 0.5.3 follows +4 (next): up to 4 candidates as documented.
* New byte checks: 4 (`work\asi\combat053\prechecks_combat053.txt`: the two list-link facts in SetupDiag, the hit list
  owner / clear for the snapshot); with 88 + 6 + 21: 119, 0 mismatches. Imports unchanged (79); exports + 1.
* Log: `0.5.3 snapshot: TscTargeterSnapshot (read-only export for TruMenu's thrall labels) on - built only while a reader
  asks, hit list verified`.

0.5.2 (2026-11-05, **offline, not yet seen in game; log only - behaviour unchanged**): diagnostics for F21 (the
finisher 1013 is never entered because condition 2011 finds targeter 9 empty). Static result first: the TU fills
targeter 9 with the **same** code as every other targeter - the instance add 0x82406390 (mask 0x3f1, the 0.1 patch) and
the candidate add 0x82404650 (= PC tru+0x316860 / tru+0x3164d0); all five TU callers of the instance add have PC
partners (instance init tru+0x1ba5a3 / +0x1ba801, tru+0x2d6126, the list ctor tru+0x31dc93, player message 0x1dc
tru+0x31f93e; message ids TU = PC), and the per-frame sort / select / set / get functions are relink (TU = retail).
No TU-only filler, so nothing new is translated. The log answers which step loses the thrall (`[Diag]`, default on):
* entry hooks (log only, the original runs with the same arguments): candidate add tru+0x3164d0 (instance, marker
  data, mask vs. slot bit 0x200, return and outer caller: which of the five paths), set target tru+0x316730, select
  tru+0x316590 (bucket entries present but nothing passed = sight test / exclusion), remove tru+0x319f80 (target
  cleared), per-frame update tru+0x31a270 (target changes, bucket / rejected counts); redirected calls: target list
  array build tru+0x32263a / destroy tru+0x32219e (slots 0..9, slot 9 bit / parameters). Changes of +0x90 that none
  of these made are reported as "changed outside the hooked functions".
* `Targeter9Why=1`: once per second for up to 4 rejected candidates the game's own eligibility tru+0x2ecca0 and the
  filter tru+0x312090 per group (the functions the update calls for them every frame) - which test rejects them.
* condition 2011: every evaluation in doppelganger mode on change (else every 2 s) with the record {+0, +2 id, +4
  value, +6 flags}, targeter 9 before / after the get call, excluded, the answer of query 0x161.
* lines `0.5.2 diag ...`, capped by `[Diag] MaxLines=4000`. New byte checks: 21
  (`work\asi\combat052\prechecks_combat052.txt`; with the 88 of 0.5 and the 6 of 0.5.1: 115, 0 mismatches). Imports:
  `VirtualAlloc` added (trampoline page, RW -> RX). Build `work\asi\combat052`.

| # | TO TEST 0.5.2 (hall02 / Yggdrasil end, power on, all Translate switches as in the package) | expected |
|---|---|---|
| 1 | load | `0.5.2 diag: targeter 9 (log only) - entries ...`; at the level `0.5.2 diag target list BUILT ...: slot 9: index 9, bit 0x200, parameters 0x...` |
| 2 | walk to the thralls | `0.5.2 diag targeter 9 candidate TAKEN ...` with the thrall's object name = it is offered; only `not offered (mask)` lines for it = its marker flags lack bit 0 (data) |
| 3 | knock one down, stand next to it, power on | `targeter 9 state changed ...` buckets / rejected; `WHY rejected`: eligibility 0 = the thrall's answers (queries 0x14c / 0xca / 0x185 / 0x1d), groups passed 0 = distance / cone; `SELECT ... none passed` = sight test; `SET target` = it got one |
| 4 | X / Y next to it | `0.5.2 diag condition 2011 changed ...: path 2` + `query 0x161 0` = target there, thrall says no; path 3 = 2011 true (then `state 1013` should follow) |

0.5.1 (2026-11-04, **offline, not yet seen in game**): two TU differences in Lara's state table of retail states
(found while porting 1019 / 1020), translated 1:1, **default off**:
* **231** (move to gameTracker+0x1260 facing +0x1270; chart records #773 [1007, 231, 1004] and #819): TU slots 0 **and
  1** = 0x82464160 = the move helper 0x82463c18 with its doppelganger branch (0.5's `MoveTo`); PC: slot 0 only,
  tru+0x35f550 -> tru+0x35f470 (retail 0x8245f930). Switches `[States] Translate231Slot0=0`, `Translate231Slot1=0`.
  Slot 0 differs from the PC only on move paths 3..6 (frames n x 100 <= animation +0x28).
* **1004** (records #741 [1004, 1013], #756, #773): TU slots 0 / 1 = 0x8245efc8 = the player's 8-slot hit list +0xa4
  (filled by the finisher 1013) is cleared only when the state's bool parameter 0x415 is **not** set, then
  0x823dfc98 (= PC tru+0x3036c0); PC slot 0 tru+0x35e020 always clears, no slot 1. Switch `[States] Translate1004=0`.
* Slot 1 = enter while the state was already active in the previous chart record (PC enter loop tru+0x385a30, getter
  tru+0x384790); a null slot is skipped, so the log-only slot 1 with the switch off is the PC behaviour.
* Off: the PC handler runs and a line `... off (would): ...` appears whenever the TU would do something else; on: `ON:`.
  Switches read again at run time (`0.5.1 switch: [States] Translate1004 0 -> 1 ...`). `[Probe] States231And1004=0`
  leaves both records untouched (= 0.5). New byte checks: 6 (`work\asi\combat051\prechecks_combat051.txt`, plus the
  88 of 0.5; 0 mismatches). Build `work\asi\combat051`.
* **Strike look off** (TU 0x823d9050) in the translated strike (`[Strike] Translate=1`), through the meter interface
  **v4** `strikeLookOff` of TruShadowPower 0.14 (used only when `version >= 4` and `size >= 60`, else skipped, logged
  once). Order as the TU: tick, input edge with model +0x40 bit 7 clear: flag 4 -> drain all, then look off
  (0x823d8dfc..0x823d8e1c); bit 7 set: look off, then the second strike (0x823d8db0); end: flag 4 -> look off, then
  drain all (0x823d92ac..0x823d92d0). 0x823d9050 itself does nothing without flag 4. The version-3 size test of
  `gt1280` is now `size >= 56` (it was `sizeof` of the interface struct, which grew to 60). Log:
  `meter interface: strike look off (TU 0x823d9050) found (version 4) ...`, per call with flag 4 `shadow strike
  tick / end: strike look off (...), meter flags 0x... -> 0x...`.

| # | TO TEST 0.5.1 (hall02, power on) | expected |
|---|---|---|
| 1 | load | `states 231 / 1004 (...): building blocks verified, wrapped ...`; `machine 1 states: ... 231 (slots 0 / 1, log only) 1004 (slots 0 / 1, log only)` |
| 2 | knock a thrall down, finisher (switches off) | `state 1004 slot 0 / 1 ...: off (would): parameter 0x415 1, hit list slots used n -> TU: list kept` = the TU keeps the list where the PC clears it |
| 3 | `Translate1004=1`, same | `0.5.1 switch: [States] Translate1004 0 -> 1`, `ON: parameter 0x415 1 ... list kept`; **do the thralls stay down?** |
| 4 | shadow step (1007, X with power) | `state 231 slot 1 ...: off (would)` (re-entry) / slot 0 lines only on paths 3..6; with `Translate231Slot0/1=1`: `ON:` |

0.5 (2026-11-04, **offline, not yet seen in game**): the last two untranslated TU states of Lara's combat, **1019**
(TU 0x8245f420 slots 0 / 1, 0x8245f540 slot 3; chart record #756 of `doppelganger_casual` DTP 20212, the combat hub)
and **1020** (TU 0x8245f398 slots 0 / 1; record #748 after the finisher #741, list index 8 = targeter 8), with their
TU-new helpers 0x8245f2a8 (point next to the target, VMX128 math), 0x82463c18 (channel move = retail 0x8245f930 / PC
tru+0x35f470 plus a TU doppelganger branch) and 0x82463eb8 (face only). The VMX128 bodies were decoded with
`tools/ppc_dis128.py` and cross-checked against the Xenia emulator's published decoder tables with the new
`tools/vmx128_xenia_check.py` (77 / 77 words of the state code the same). 1019 keeps its target handle (TU meter
+0x20 / +0x24, only 1019 uses it - `tools/ppc_ptr_field_users.py`) in the plugin. Both are registered with Lara's
state table (needs TruDoppelganger's generic registry, as 1017 / 244) and are **log only** by default:
`[States] Translate1019=0`, `Translate1020=0` (read again at run time, at most once per second); `[Probe]
States1019=0` leaves them out (= 0.4.1). New byte checks: 17 (88 in total, `work\asi\combat05\prechecks_combat05.txt`,
0 mismatches on the Steam exe). Details: `docs\Befund-Schattenkampf-0411b.md` (main workspace).

| # | TO TEST 0.5 (after F4 is confirmed; hall02, power on) | expected |
|---|---|---|
| 1 | load | `states 1019 / 1020 (...): building blocks verified, registered ...`, `machine 1 states: ... 1019 (added, log only) 1020 (added, log only)` |
| 2 | power on near thralls, aim / fight (switches off) | `state 1019 slot 0 / 1 (...) (call n): off (would) ...` with the reason / path; `state 1019 slot 3 ...: off: nothing (no valid meter target)`; after a finisher `state 1020 ...` |
| 3 | `Translate1019=1`, `Translate1020=1` (TruMenu switch or INI) | `0.5 switch: [States] Translate1019 0 -> 1`; `ON slot 0 ... step next to it ... meter handle set`; slot 3 `ON follow the meter target`; Lara steps / turns to the thrall |
| 4 | trouble | both 0 (or `[Probe] States1019=0`) |

0.4.1 (2026-11-03, **offline, not yet seen in game**): `[Strike] Translate` and `[States] Translate1013` are read
again from `TruShadowCombat.ini` at run time - at most once per second, from the code they switch (state 1014 slots
0 / 2 / 3, the 1013 target site tru+0x31d610), so TruMenu's TO TEST switches `sc-strike` / `sc-translate1013` (which
write the INI at once) count from the next strike / finisher without a restart. Nothing new is translated: the
switches only turn on / off the code 0.4 built and byte-checked at the start. To make that possible the three 1013
sites are now patched at the start whenever their byte checks pass, also with `Translate1013=0` (then every site runs
the PC path - the same code path 0.4 used outside doppelganger mode). A strike that runs keeps the translation until
its end (meter flag 2 cleared by slot 2); a missing key keeps the current value; the 1014 wrappers need `Gate=1` (the
default) or `Translate=1` at the start. Log lines: `0.4.1 switch: [Strike] Translate 0 -> 1 (read again from
TruShadowCombat.ini)`, `0.4.1 switch: [States] Translate1013 1 -> 0 ...`, at the start `state 1013 translation: off
([States] Translate1013=0) - sites ... patched but they run the PC path ...` or `... ON (...)`. Build
`work\asi\combat041` (sha256 `24fcd9331b651f8f00657da736caae1d4d90a93b7de155fced06faa7bc4554a7`, 0 compiler warnings),
pre-checks `work\asi\combat041\prechecks_combat041.txt`: 71 checks, 0 mismatches on the Steam exe (the 0.4 list; no
new engine address). Profiles: the `_radial2` variants (`regress_shadowlara_50l_radial2`, `_50n_radial2`,
`_50l_hud_radial2`); 50l / 50n / 50l_hud keep 0.4 (`combat04`).

| # | TO TEST 0.4.1 (hall02, switches in TruMenu Tests -> Schalter or the TO TEST page) | expected |
|---|---|---|
| 1 | load | `TruShadowCombat 0.4.1 ... loaded`, `state 1013 translation: off ([States] Translate1013=0) - sites ... patched`, no "does not match" |
| 2 | downed thrall, power on: switch `sc-translate1013` on, X / Y next to it; then off | `0.4.1 switch: [States] Translate1013 0 -> 1`, then the 0.4 translation lines (row 2 below); off: `1 -> 0`, probe lines only |
| 3 | same with `sc-strike` | `0.4.1 switch: [Strike] Translate 0 -> 1`, `state 1014 slot 0 ... TU strike translation`, `shadow strike start / hit / end`; off: `1 -> 0`, `[Strike] Translate=0 - strike not run` |

0.4: `[States] Translate1013=1` (default 0 - then nothing is patched) runs the finisher state 1013 (PC tru+0x31d600)
in doppelganger mode as the TU's 0x823e0a88: target of targeter 9 (if it has a handle), the target into the player's
8-slot hit list +0xa4, hit record +0x68 = attack data (player +0xc4) byte +1 instead of 0xff, message record +0x3c =
0. Three sites in the PC function are redirected (tru+0x31d610 call, tru+0x31d825 push 0xff, tru+0x31d895 call);
outside doppelganger mode they do what the PC did. Build `work\asi\combat04`, 71 pre-checks (0 mismatches).

| # | TO TEST 0.4 (tree 50l, `Translate1013=1`) | expected |
|---|---|---|
| 1 | load | `state 1013 translation: ON (...)` |
| 2 | hall02: knock a thrall down, power on, X / Y next to it | `state 1013 translation ... target of targeter 9: 0x...`, `message 0xf4 to 0x..., hit list slot n, record +0x3c = 0`; LogLevel 2: `hit record +0x68 = n (attack data +1)`; does the thrall stay down now? |
| 3 | main game finisher (any downed enemy) | unchanged (no translation lines outside DLC 2) |
| 4 | trouble | `Translate1013=0` |

0.3: probe of state 1013 (the finisher, PC tru+0x31d600 = TU 0x823e0a88) - `[Probe] State1013=1` logs the PC
target (targeter 5) next to the TU's doppelganger target (targeter 9), the PC handler runs unchanged; meter API v3
(`gt1280`, TruShadowPower 0.12) used when present. Build `work\asi\combat03`, 65 pre-checks. TO TEST 0.3: in hall02
knock a thrall down, power on, X / Y next to it -> `state 1013 slot 0 ... PC target ... TU target ...`
(Befund-Schattenkampf section 10).

Translation of the Xbox title update's (TU) **target list**, **target conditions**, the target **states 1017 / 244 /
1007** (0.2) and the **shadow strike** (state 1014, 0.2, behind `[Strike] Translate`, default off) for Lara's Shadow on
the Steam `tru.exe` (image base 0x400000). Findings and
the full Xbox -> PC map: workspace doc `docs\Befund-Schattenkampf.md`. Rule: translate, do not imitate - every value
comes from the same data / code the Xbox uses.

Needs (loaded by the Ultimate ASI Loader, alphabetical): `TruDlc2Player.asi` (doppelganger flag = TU
gameTracker+0x1244), `TruDoppelganger.asi` (generic registry of the TU condition ids). Works next to
`TruShadowPower.asi` (its copies of Lara's tables are extended, not replaced).

## What it does

| part | TU (Xbox) | PC |
|---|---|---|
| target list 7 -> 10 | 0x824062c8 ctor (`cmpwi 0xa`), 0x82406390 instance add (mask 0x71 -> 0x3f1, 2 loops), 0x82412ca0 player init (array 0x28 bytes, destroy loop), 0x824126d8 per-frame loop, 0x823ed958 / 0x823c3eb8 / 0x823c6790 / 0x822ebc58 loops | patched constants at tru+0x322631, +0x31dc7a, +0x316916, +0x316948, +0x3169a3, +0x3169d2, +0x31acab, +0x31dcd0, +0x316845, +0x3228a5 |
| targeter parameters | 0x82402208: tuning (object 858) table +0x90 / count +0x94 first, else 0..5 retail, 6 -> +0x468, 7 -> +0x478, 8 / 9 -> none | tru+0x2ecc10 (retail switch 0..6) replaced; slot 7 = TU 6, slots 8 / 9 = TU 8 / 9, slot 6 stays the retail 6 (= TU 7) |
| condition 2005 | 0x8246ea20 / predicate 0x8246e8e0 | new record (group 2000) in both machines |
| condition 2006 | 0x8246ec68 / 0x8246eb08 | new record, machine 1 |
| condition 2013 | 0x8246eaf8 / 0x8246ea30 | new record in both machines (reads state 1017's target - 1017 not ported, so 0) |
| condition 2011 | 0x8246f270 / 0x8246f140: doppelganger -> targeter 9 + query 0x161 | handler replaced; outside DLC 2 the PC predicate tru+0x365970 |
| condition 538 | 0x8246fae0 / 0x8246faa8: doppelganger -> meter flag 8 | handler replaced; outside DLC 2 tru+0x365fa0; in DLC 2 needs `TruShadowPowerMeterApi` (not in TruShadowPower 0.9 -> 0) |
| state 1014 | 0x8245fd70 / 0x8245fdc0 / 0x8245fd98: doppelganger -> 0x823d8978 / 0x823d9210 / 0x823d8d18 (meter object) | slots 0 / 2 / 3 wrapped: in DLC 2 with `[Strike] Translate=1` and `TruShadowPowerMeterApi` (TruShadowPower 0.11+) the TU strike (placement + message 0xbe 0x823d86a8, hit tru+0x1b4de0, message 0x3f at the end); else nothing (`Gate=1`); outside DLC 2 the PC handlers |
| state 1017 slot 4 (0.2) | 0x8245f5a0: target from parameter 0x40f / aim, facing (0x82457b28), gameTracker+0x1260 / +0x1270, target handle +0x1284 | new record; facing tru+0x30b8a0; the handle feeds condition 2013 and state 244 |
| state 244 (0.2) | 0x82464198 / 0x824642a8 / 0x82463fc8: dash to the 1017 target | new record; channel mode 2 tru+0x38d00; step count +0x1280 (shared with TruShadowPower only from meter API version 3) |
| state 1007 slots 4 / 5 (0.2) | 0x8245f068 (doppelganger branch) | wrapped: doppelganger -> translation, else PC slot 4 tru+0x36d930 |
| state 1008 (0.6.11) | {0x8245f7b0, 0, 0x82455a38 (empty), 0x8245fa40, 0, 0}: enter / tick steer the motion channel onto the target of targeter TU 7 (mode 3 {FaceTarget, t+0x20, n x 100}; Busy244 -> mode 2 stop) | record {0, 0, 0, 0, tru+0x36d9a0, 0} wrapped: slots 0 / 3 = translation (`Translate1008=1`) or log only, slot 2 = end line, slot 4 = PC handler only with `Translate1008=0` |
| state 1015 exit (0.6.12) | slot 2 0x8245fe58 (TU-new): target in CM+0x48 valid -> death switch kind 0 (v = Lara - target, z = 0), then the retail clear | slot 2 of record {tru+0x35e0e0, 0, tru+0x35e0f0, 0, 0, 0} wrapped: kill with `Translate1015Exit=1` (else log only), then the PC slot 2 tru+0x35e0f0 |

The tables are extended when Lara's registration runs (PC tru+0x368b60, reached through the vtable slot 0x85e1d4):
the current `push table` operand (original or TruShadowPower's copy) is copied with these records. Byte pre-checks:
40 (`work\asi\combat01\prechecks_combat01.txt`, `tools/pe_bytes_check.py`: 0 mismatches on the Steam exe). Any
mismatch switches the affected part off with a log line.

## Data

The targeters 8 / 9 take their parameters from DTP 22497 of `player_tru_dlc2_extension.drm`; 10 words of that
section were converted wrongly (count 2 -> 0x200, index byte, flags, record kinds / floats). Fixed file in tree
`work\rebuild\dlc_test50l_combat\mods` (= 50k_cut + this file), tool `tools/tuning_target_fix.py`. With the old file
the plugin logs "tuning +0x94 = ... implausible" and the targeters 8 / 9 get no parameters.

0.2: the tree also holds `doppelganger_casual.drm` with the list index parameter 0x40f (activity 1039, type 46, read
by the TU as one byte) fixed in 4 records (`tools/chart_act_u8_fix.py`) - without it state 1017 reads list index 0
instead of 6 in records #764 / #765 / #770 (#773: 5 -> 0).

## Options (TruShadowCombat.ini)

| key | default | meaning |
|---|---|---|
| `[ShadowCombat] Enabled` | 1 | 0 = load, patch nothing |
| `[ShadowCombat] LogLevel` | 1 | 0 errors, 1 info + first call of every translated condition / state, 2 + result changes, 3 + periodic |
| `[TargetList] Enabled` | 1 | 0 = PC list unchanged (2005 / 2006 / 2013 / 2011 in DLC 2 answer 0) |
| `[Conditions] Enabled` | 1 | the five conditions |
| `[States] Enabled` | 1 | 0.2: states 1017 / 244 / 1007 (slots 4 / 5) |
| `[Strike] Gate` | 1 | state 1014 in DLC 2 without the translation: 1 = nothing, 0 = PC retail strike as before |
| `[Strike] Translate` | 0 | 0.2: 1 = the TU shadow strike (needs `TruShadowPowerMeterApi`, logged "no meter interface" otherwise); 0.4.1: read again at run time (<= 1 / s) |
| `[States] Translate1013` | 0 | 0.4: 1 = the finisher 1013 in doppelganger mode as the TU; 0.4.1: read again at run time (<= 1 / s) |
| `[Probe] State1013` | 1 | 0.3: log the PC / TU target of the finisher 1013 |
| `[Diag] Targeter9` | 1 | 0.5.2: log-only hooks of targeter 9 (add / update / select / set / remove, list build / destroy); 0 = no hooks |
| `[Diag] Targeter9Why` | 1 | 0.5.2: eligibility / filter result of the rejected candidates of targeter 9 (once per second) |
| `[Diag] Condition2011` | 1 | 0.5.2: every evaluation of condition 2011 in doppelganger mode with its inputs |
| `[Diag] MaxLines` | 4000 | 0.5.2: total cap of the diagnostic lines |
| `[Diag] Snapshot` | 1 | 0.5.3: read-only export `TscTargeterSnapshot` for TruMenu's thrall labels (built only while asked) |
| `[Damage] Translate` | 1 | 0.6: 1 = the TU damage-type switch 0..27; read again at run time (<= 1 / s while hits come); default 1 since 0.6.3 (live 07.11.) |
| `[Damage] Log` | 1 | 0.6: burst lines of the incoming damage types (changes nothing) |
| `[Damage] MaxLines` | 3000 | 0.6: cap of the damage lines |
| `[Chunk] Translate` | 1 | 0.6.1: lethal impulse (message 0x91) as the TU - death switch kind 7 instead of a chunkdoll inside the physics step; 0 = PC branch; read again at run time (<= 1 / s) |
| `[Chunk] Log` | 1 | 0.6.1: burst lines of the lethal impulses with the physics lock (changes nothing) |
| `[Chunk] MaxLines` | 2000 | 0.6.1: cap of the chunk lines |
| `[Splash] Translate` | 1 | 0.6.2 (K9): MeleeSplashDamage as the TU - main target excluded from the splash; doppelganger remap 0x1a -> 0x10 / 0x10 -> 0x16 while `[Damage] Translate=1`; 0 = PC splash; read again at run time (<= 1 / s) |
| `[Splash] Fallback` | 1 | 0.6.2: the Xbox pair values when object 858's table differs from them (converted file: words unswapped); 0 = table as loaded |
| `[Splash] Log` | 1 | 0.6.2: burst lines of the splash records (type in / out, main target, enemy switch verdict; changes nothing) |
| `[Splash] MaxLines` | 2000 | 0.6.2: cap of the splash lines |
| `[Death] TranslateNotify33` | 1 | 0.6.3 (T3): script notification 33 before EnterRegenerateDeath in the death check tru+0x220380, as the TU 0x822f6578 (hall02: finisher hint `hint_17`); 0 = PC; read again at run time (<= 1 / s) |
| `[Melee] Translate` | 1 | 0.6.4 (T-M1 / T-M2): enemy MeleeAttack as the TU - messages 0x15 / 0x8a / 0xbe end the attack only without a data pointer (TU 0x82330d40), Enter sets brain+0xc bit 0 unless record+8 bit 2 (TU 0x8232fb48); 0 = nothing patched; start only |
| `[Companion] Translate` | 1 | 0.6.5 (H0): the thrall's companion (TU 0x822da800 / 0x822da918) as an object-table lookup; 0 = never a companion (TU without one = PC); live (<= 1 / s) |
| `[Companion] Log` | 1 | 0.6.5: one line per new thrall instance (companion object, type, byte +0x18, regeneration list; or the reason for none), max 400 |
| `[Death] TranslateNotify34` | 1 | 0.6.5 (H6): notification 34 at every RegenerateDeath exit (TU 0x8235e338); live |
| `[Death] TranslateNotify38` | 1 | 0.6.5 (H7 / H8): finisher block of RegenerateDeath / Regenerate slot 10 - type 16 (or 1 / 1) hit with companion -> death kind 7 + notification 38 (TU 0x8235e3a8 / 0x8235e998); live |
| `[Death] TranslateRegenList` | 1 | 0.6.5 (H1): companion regeneration list before the tune list in ShouldRegenerate (TU 0x8235ece8); live |
| `[Death] TranslateLand` | 1 | 0.6.5 (H3 / H4 / H3b): T2 Land with LP <= 0 -> 33 (with TranslateNotify33) + RegenerateDeath, Land slot 13 with companion, Land exception of T3; live |
| `[Melee] TranslateInterrupt` | 1 | 0.6.5 (H5, T-M3): Vaulted and (with companion) RegenerateDeath may interrupt MeleeAttack (TU 0x82330830); live |
| `[Death] TranslateT5` | 1 | 0.6.6 (T5): lethal, not regenerating hit on an enemy with a companion -> death kind 7 at once in the hit reaction (TU 0x823038d8); live |
| `[Death] TranslateVaulted` | 1 | 0.6.6 (P1c): Vaulted Enter as the TU 0x8232b630 with the step chain (records 0xbe / 0xf4, switch, copier); step table only from fixed extension data; live |
| `[Death] TranslateVaultedClock` | 1 | 0.6.6 (P1c K): the TU's Vaulted clock - 5 s without slow motion (Enter 0x8232b698, enemy update 0x822db190); needs the chain; live |
| `[Death] Log` | 1 | 0.6.9: one line per chunkdoll build of the Death state (tru+0x26c9f9) and per death switch (tru+0x241650), max 2000; log only; live |
| `[Hit] TranslateHitSpeed` | 1 | 0.6.10 (K-8b): Lara's contact hit gives msg+0x44 / +0x48 = (int) A+0x10 / A+0x14 as the TU 0x823e169c (tru+0x319169) - the knockback speed; 0 = 0 / 0 (PC); live |
| `[States] Translate1008` | 0 | 0.6.11 (Q19): state 1008 (finisher Y move) as the TU 0x8245f7b0 / 0x8245fa40 - steer Lara onto the target of targeter TU 7 every tick, PC slot 4 tru+0x36d9a0 not run; 0 = PC + "off (would)" lines; every level; live |
| `[Probe] State1008` | 1 | 0.6.11: wrap record 1008 (slots 0 / 2 / 3 / 4) at all; 0 = PC record untouched (start only) |
| `[States] Translate1015Exit` | 0 | 0.6.12 (Q37): exit of state 1015 as the TU 0x8245fe58 - death switch kind 0 on the finisher Y's target (CM+0x48) before the PC clear; 0 = PC + "off (would)" lines; every level; live. Slot 2 is wrapped whenever `[States] Enabled=1` and the 10 byte checks pass (no own probe key) |
| `[Adrenaline] Log` | 1 | 0.6.13 (Q108): read-only `0.6.13 Q108` lines - poll every 10 ms (meter full, adrenaline mode, headshot window, circle, pointer zone, every world / player slow motion with its factor) + Vaulted Enter / 1014 enter / 0xbe record / strike shot; start only |
| `[Adrenaline] AssistPointer` | 0 | 0.6.13 (Q109, PC option): the strike pointer is kept within half the radius before the zone test (call 0x70d863 -> 0x6f2f20), so every shot hits the zone; live |
| `[Lock] MouseSwitch` | 1 | 0.6.13 (Q68, PC option): 0 = the mouse axes no longer feed the lock-on target switch 0x71cb10 (calls 0x71cd07 / 0x71cd20); 1 = the game's; live |
| `[Lock] RightKey` / `LeftKey` | 0 | 0.6.13 (Q68): virtual-key codes that switch the locked target right / left (one frame of +-1.0 on the switch's mouse x read); 0 = off; live |
| `[Chunk] RemoveLastPiece` | 0 | 0.6.13 (Q99 option A, PC option): 0x696f69 `75` -> `eb`, the permanent chunk piece is removed after its lifetime; live |
| `[Adrenaline] FillPercent` | 100 | 0.6.14 (F6, PC option): message 0xd9 (damage Lara dealt, the game's fill) x percent at its post 0x63b03a; 0..1000; live |
| `[Adrenaline] DrainPercent` / `DrainModePercent` | 100 / 100 | 0.6.14 (F6, PC option): drain rate = player data +0x2d4 (20) / +0x2d8 (225, R3 mode) x percent (loads 0x6f2972 / 0x6f2965); 0..1000; live |
| `[Adrenaline] StrikeWithoutFullMeter` | 0 | 0.6.14 (F6, accessibility): condition 538 (meter full, first condition of the vault-off strike) answers 1 in the main game; needs `[Conditions] Enabled=1`; live |

Log: `TruShadowCombat.log` next to tru.exe.

## Build / install

```
scripts\windows\Build-TruAsi.ps1 -Name TruShadowCombat -OutDir work\asi\combat02
scripts\windows\Set-TruShadowCombat.ps1 -Install -SourceDir work\asi\combat02     (game closed; replaces 0.1)
scripts\windows\Set-TruShadowCombat.ps1 -Remove
```

Byte pre-checks 0.2: 64 (`work\asi\combat02\prechecks_combat02.txt`, 0 mismatches on the Steam exe).

## TO TEST (0.2: tree `dlc_test50l_combat`, TruShadowPower 0.11)

| # | where | what | expected log / picture |
|---|---|---|---|
| 1 | game start | load | `TruShadowCombat 0.2 ... loaded (... states 1, strike gate 1, strike translate 0)`, `target list: 7 -> 10 targeters ... 10 sites patched`, `Lara registration: vtable slot 0x0085e1d4 -> hook`, no "does not match" line |
| 2 | main game level | Lara loads, a few fights | `targeter slot 0..9` lines; `machine 1 conditions: 2005 (added) 2013 (added) 2006 (added) 2011 (replaced) 538 (replaced)`, `machine 2 ...`, `machine 1 states: 1014 (slots 0 / 2 / 3 gated) 1007 (slots 4 / 5) 1017 (added) 244 (added)`; main-game combat (aim, adrenaline dodge, headshot) as before |
| 3 | DLC 2 start | load | slots 8 / 9 `DLC 2 tuning table (object 858 +0x90)` with a non-zero parameter; no "implausible" line; `TruShadowPower meter interface found (version 2 ...)` at the first doppelganger condition |
| 4 | `dlc_yggdrasil_hall02` thralls | RB near a thrall, aim at it | `condition 2011 / 2005 / 2006` lines, `condition 538` now from meter flag 8 (switches to 1 when the meter is high); `state 1017 slot 4 ... first call` and `state 244 ...`: Lara turns to / dashes at the thrall; `condition 2013 -> 1` |
| 5 | same, `[Strike] Translate=1` | knock a thrall down, power + X next to it | `state 1014 slot 0 ... TU strike translation`, `shadow strike start: target ...`, `shadow strike hit ...`, `shadow strike end: message 0x3f sent`; does the thrall stay down? how long does the strike animation run (x100 question, Befund 9.4)? |
| 6 | any | crash / odd targeting | `[Strike] Translate=0`, `[States] Enabled=0`, `[TargetList] Enabled=0`, `[Conditions] Enabled=0` in that order; send the log |
