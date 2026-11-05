# TruShadowCombat.asi - DLC 2 combat of the title update (0.5.3)

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
