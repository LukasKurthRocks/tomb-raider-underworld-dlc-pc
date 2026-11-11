# TruDlc2Player.asi

DLC 2 *Lara's Shadow*: the doppelganger as the player object, as the Xbox title update (TU) does, for the PC
`tru.exe` (Steam, image base 0x400000). The source header of `TruDlc2Player.cpp` holds the full translation with all
addresses; the findings are in docs/WINDOWS_REBUILD.md (finding 43) and the workspace notes (Befund-Felsrinne,
Befund-TU-Funktionen L4, Befund-Kostuem-Reset-DLC1).

## What it does

| Part (ini key) | TU | PC |
|---|---|---|
| type record (`TypeRecord`) | player type table 0x8275ae38 record 35 `{"doppelganger_casual", DoppelgangerInit 0x82412c48, player f2..f6}` | copy of the PC table 0x8aba28 with the record appended (index 39), the 11 code operands that address the table moved to the copy |
| costume (`Costume`) | `GAMELOOP_LevelLoadAndInit` 0x82297d30: `lara_doppelganger` -> `doppelganger_casual` before the costume load request | 6-byte detour at tru+0x1de3a3 (all costume paths meet there, esi = name) |
| DoppelgangerInit | 0x82412c48: base player init, then gameTracker+0x1244 = 1 | base init tru+0x321f80, then the flag in the plugin (export `TruDlc2PlayerDoppelganger`) |
| 0.2 flag reset (`FlagReset`) | every new game tracker = memset (constructor 0x82413878) clears +0x1244 | the only constructor call tru+0x322445 redirected: constructor, then flag = 0; export `TruDlc2PlayerTrackerGeneration` |
| 0.4 tracker flag (`TrackerFlag`) | DoppelgangerInit 0x82412c70..0x82412c84: `stb 1, 0x1244([0x829892b0])` | the same store into PC `[0xfadb58]+0x1244` (readers verified at start: larabase f36 body tru+0x377dc0, player code tru+0x3200d6); the tracker constructor's memset clears it |
| 0.3 costume reset (`CostumeReset`) | every mission start: `MainTracker_UILoadLevel` 0x8247d818 (4th argument 1) calls the new-game reset 0x821fe9a8 at 0x8247d95c: chosen costume +0x210 / +0x20e / +0x20c = 0 | the direct level change (TruMenu `level.load`) skips that reset; in the costume detour: name `lara_doppelganger` / `doppelganger_casual` and the unit's own default costume (tru+0x1de379: stream unit data +0x70 -> u16 +0x294) not `lara_doppelganger` -> the three words = 0, the unit default is loaded |

| 0.5 TU costume mapping (`[Costume] TuMapping`, default 0) | state save 0x821fef58 (0x821ff0dc..0x821ff118): current == id(`doppelganger_casual`) -> `+0x20c` = id(`lara_doppelganger`); state load 0x821ff1e0 (0x821ff518..0x821ff540): `+0x20c` == id(`lara_doppelganger`) -> current = id(`doppelganger_casual`); spawns 0x822973b0 (0x822976b0..0x822976d8) and 0x82297f10 (0x8229803c..0x82298064): record `+0x50` == id(`lara_doppelganger`) -> current and `+0x50` = id(`doppelganger_casual`) | detours tru+0x155cb1 (save, 13 bytes), tru+0x156fbd (load, 13), tru+0x1d42e9 (player spawn tru+0x1d40c0, 5), tru+0x1d4469 (costume-switch spawn tru+0x1d4340, record 0xe7f2a0, 8); name lookup tru+0x1bf770 (= TU 0x822809e0) at every call; all four or none; needs `TypeRecord=1` + `Costume=1` |

| 0.6 level start from the game (`[Mission] DialogStart`, default 1) | yes / no dialog accept `ScriptDialogYesNo::RegisterAcceptChanges` 0x8247f0c0, case 8 0x8247f2c8..0x8247f510: `sel` = 0 for `dlc_level2_start` .. `dlc_level6_start` (string table 0x820760f8), else 1; `MainTracker_UILoadLevel(name, sel, 0, 1)` | PC 0x77e790 case 8 (retail code: `UILoadLevel(name, 1, 0, 0)` inlined, always the outfit selection): the 35 bytes 0x77e8c0..0x77e8e3 jump to a stub that calls f27 0x77e170(name, sel, 0, 1); the PC's own case tail follows |

| 0.7 rest of case 8 (`[Mission] DialogDifficulty`, default 0) | the same case 0x8247f2d8..0x8247f3a0: "Resetting player tailoring to Medium difficulty." - `0x822a2b50(name, old, 1)` + game data +0x3efa0 / a4 / ac / b0 = 1 for EnemyHP / AmmoAdj / PlayerHP / SavingGrabAdj, +0x3efb4 = 1 (= the bodies of the setters 0x824be628..0x824be788, natives f6..f10, with 1); after the case 0x8247f57c `stb 0, 0x1f94(0x829be044)` | inside the 0.6 stub, before f27: the PC setters 0x6e75a0 / 0x6e75e0 / 0x6e7620 / 0x6e7660 / 0x6e76a0 with 1 (+0x3ef98 / 9c / a4 / a8 / ac; their metric call 0x6457a0 is the PC's empty `ret`); the tail's last call 0x77e8f9 (call 0x4be5e0) -> a stub that makes it and then 0x5bfdf0(0) = `[0xdb94de] = 0`; needs `DialogStart=1` |

| 0.8 hold clear after cases 4 / 6 (`[Mission] DialogHoldClear`, default 0) | case 4 0x8247f1b4..0x8247f1dc: `[0x829ca6d9] = 1`, `[0x829ca6d3] = 3`, `bl 0x8247e000`, then `stb 0, 0x1f94(0x829be044)`; case 6 0x8247f20c..0x8247f2b4: `MainTracker_UILoadLevel(&name, sel, 1, 0)` (sel 0 for `ee_01` / `Ee_01`), then the same store | case 4 0x77e7eb (= retail case 4 + a PC-only call 0x483810): the call 0x77e7fe (call 0x77e460 = TU 0x8247e000) -> a stub that makes it and then 0x5bfdf0(0); case 6 0x77e808 (UILoadLevel inlined twice, as retail): both calls 0x77e860 / 0x77e88d (call 0x5dfb20(name, 1)) -> a cdecl stub that makes it and then 0x5bfdf0(0); independent of the 0.6 / 0.7 keys |

Every patched byte is compared with the expected code / data first; on a mismatch that part is left alone and the
reason is logged.

### 0.7: the TU's tailoring reset in the same case (Befund-DLC-Schwierigkeit-1111)

The TU's case 8 also sets the player tailoring (the difficulty values) to Medium before the start. The call
0x822a2b50 the TU makes for four of the values is `GameMetrics` *SendSettingChangedMetric* (it formats old / new with
`%d` and builds a metric "Setting" / "Prev" / "New"); the case's code is word for word the body of the TU's tailoring
setters 0x824be628 / 680 / 6d8 / 730 / 788 (script natives f6..f10; retail 0x824ba640..0x824ba7a0 moved-equal) with
the value 1. Their PC partners are the setters 0x6e75a0 / 0x6e75e0 / 0x6e7620 / 0x6e7660 / 0x6e76a0 (strings
`EnemyHP` 0x85ddf8 ... `SavingGrabAdj` 0x85de14; natives f6..f10 of the class registered by 0x7aede0), each
`v <= 2 -> 0x6457a0(name, old, v); [[0xc59264] + 0x3ef98 / 9c / a4 / a8 / ac] = v`. 0x6457a0 is the PC's folded empty
function (`ret`, 2143 callers): metrics are compiled out, so the PC partner of 0x822a2b50 is that `ret`. 1 is also the
PC's own default (0x6e7500 sets all five to 1). `DialogDifficulty=1` calls the five setters with 1 in the TU's order
inside the 0.6 stub, before f27, and logs old / new values.

After the case the TU stores `0x1f94(0x829be044) = 0` (byte 0x829bffd8; retail 0x829bfee8). Retail writes that byte
in 0x8229d6d0 (1) / 0x8229d5d0 (0), whose PC partners 0x5d4780 / 0x5d4700 (xbox_pc_map verified, the same state
+0xbb = 6 / 0 and flag masks) call 0x5bfdf0(1 / 0) = `[0xdb94de]` - the pause menu's render-clock hold (TruMenu
README, shader clock: dt 0 while set). The plugin redirects the case tail's last call 0x77e8f9 (call 0x4be5e0, the
retail `bl 0x821669e0` the TU inlined right before its store) to a stub that makes that call and then 0x5bfdf0(0).
No branch enters the tail 0x77e8e3..0x77e8fe (`tools/pe_patch_site_check.py`). Byte checks:
`work/asi/dlc2p07/prechecks_dlc2p07.txt` (16 / 16 ok against tru.exe md5 5560abac...).

Not translated by the plugin: the TU's main-menu start (script 134 function 9, no game in progress) calls the natives
f6..f10 with 1 as well; the PC's script 104 function 9 (pipeline S104) has no such calls - a data change, since Q40
the opt-in rule `tu134_tailoring` of `tools/generalbank_pc_build.py build --tailoring`. The same TU store after cases
4 and 6: 0.8 (below).

### 0.8: the TU's render-hold clear after cases 4 and 6 (Befund-Hauptmenue-Schwierigkeit-1111)

The TU ends cases 4 and 6 of `RegisterAcceptChanges` with the same `stb 0, 0x1f94(0x829be044)` as case 8; retail and
PC have none there. Side by side (jump tables TU 0x8247f118, retail 0x82479700, PC 0x77e97c, entries 3 and 5):

| case | TU | retail | PC |
|---|---|---|---|
| 4 (script 7 f8 opens the dialog with action 4, TU and PC) | 0x8247f1b4: `[0x829ca6d9] = 1`, `[0x829ca6d3] = 3`, `bl 0x8247e000`, **`stb 0` 0x8247f1d0..0x8247f1dc** | 0x82479788: the same without the store (`bl 0x82478590`) | 0x77e7eb: `call 0x483810` (PC-only), `[0xfae8dc] = 1`, `[0xfae8da] = 3`, `call 0x77e460` (= retail 0x82478590, verified) |
| 6 (level start, `ee_01` / `Ee_01` -> no selection) | 0x8247f20c: two compares, `bl 0x8247d818(&name, sel, 1, 0)`, **`stb 0` 0x8247f2a8..0x8247f2b4** | 0x824797c4: the same with two call sites, no store | 0x77e808: UILoadLevel inlined twice (`[0xfae8d9] = sel`, game data +0x90 = 0, `call 0x5dfb20(name, 1)`) |
| 9 | 0x8247f584: `[0x829ca6d9] = 1`, `[0x829be084]` vcall +8, `[0x829be07c]` vcall +0xc | 0x824798e4: the same through the getters 0x821666c0 / 0x821669a0 | 0x77e900: `[0xfae8dc] = 1`, 0x4be560 (`[0xa13f58]` +8), 0x4bdd90 (`[0xa13f50]` +0xc) - equal, nothing to port |

`DialogHoldClear=1` redirects the call 0x77e7fe to a stub (0x77e460, then 0x5bfdf0(0)) and the two calls 0x77e860 /
0x77e88d to a cdecl stub (0x5dfb20(name, arg), then 0x5bfdf0(0)); each a whole 5-byte call followed by the PC's own
`add esp,8` / `jmp 0x77e94a`, no branch into any of them (`tools/pe_patch_site_check.py`). Byte checks:
`work/asi/dlc2p08/prechecks_dlc2p08.txt` (17 / 17 ok against tru.exe md5 5560abac...). Every clear is logged with the
byte before / after.

### 0.6: DLC 2 from the pause menu without the outfit selection (Befund-Kostuemauswahl-DLC2-1111)

Live 2026-11-10 21:12: DLC 2 started from inside DLC 1 (pause ring -> DLC -> mission screen -> "Wenn Sie ein neues
Spiel starten ..." -> yes) showed the outfit selection, Lara was loaded in the chosen outfit (no `level load`
costume line in TruDlc2Player.log, DoppelgangerInit only after a manual `costume.set 11`). Started from the main menu,
DLC 2 has no selection (script 104 as the TU, pipeline step S104). The difference is exe code: in a running game
script 104 function 9 (the same as TU script 134 function 9 in this branch) opens the yes / no dialog with action 8,
and the dialog's accept handler starts the level. Retail and PC: `UILoadLevel(name, 1, 0, 0)` (always the selection,
the chosen costume stays); TU: `UILoadLevel(name, 0 for dlc_level2..6_start else 1, 0, 1)` - the 4th argument 1 also
runs the new-game block with the costume reset, so the unit default `lara_doppelganger` (-> `doppelganger_casual`,
0.1) is loaded. `DialogStart=1` translates the rule and the call; DLC 1 keeps its selection (as on the TU).
Not ported in 0.6: the TU's tailoring reset to Medium in the same case (`EnemyHP` / `AmmoAdj` / `PlayerHP` /
`SavingGrabAdj` via 0x822a2b50) - on PC the player's tailoring stays as it was (f27 keeps it across the reset); and
the TU-only byte store `0x1f94(0x829be044) = 0` after the case. Both: 0.7 `DialogDifficulty` (above). Byte checks:
`work/asi/dlc2p06/prechecks_dlc2p06.txt` (8 / 8 ok against tru.exe md5 5560abac...); patch site:
`tools/pe_patch_site_check.py` (no branch into the 35 bytes). Log: one line per start (`dialog start N: level ...`)
and the selection byte after f27.

### 0.5: the TU's costume mapping 857 <-> 11 (Befund-Kostuem-Reset-DLC1 section 7)

The TU added the same two-name test in four places (TU disassembly `work/asi/combat02/analysis/tu_all.txt`; the retail
functions have the plain store / load and no test there). `TuMapping=1` translates all four; one alone would load
`lara_doppelganger` as the player. Effect: a save written in DLC 2 holds 11 (as on the Xbox) instead of 857; loading
it maps back to 857; a spawn that sees 11 as the costume spawns 857. With the 0.1 level-load substitution and the 0.3
reset (both names) the outcome on PC is the same as with 0.4 - the difference is the save content. Not ported (not
part of the mapping, documented in the source header): the TU load's store of the old costume into
altPlayerObjectID (`0x144(r29)` = PC 0xe7f1cc) and the TU spawn's validity test + unit-default fallback
(0x82297688..0x822976ac). Every site is byte-checked with a neighbouring instruction (register roles) and the four
sites were checked offline for branches into the patched bytes (`tools/pe_patch_site_check.py`, 4 / 0 fail).
TruMenu up to 0.10.3 byte-checks the save site tru+0x155cb1 for its costume items and turns them off when the
detour is there - use TruMenu 0.10.4 (accepts the detour) with `TuMapping=1`.

### 0.4: why the TU HUD never turned the shadow meter red / pulsing (F17)

0.1-0.3 kept the doppelganger flag only in the plugin, on the assumption that the PC game tracker has no byte +0x1244.
It has (constructor tru+0x31c2d0, memset 0x1310), and the retail code reads it exactly as the TU: larabase native f36
(PC tru+0x39a290 -> tru+0x377dc0; the TU binds entry 36 to 0x824a1188, the same function as `dlc2data` f0; retail
0x824a4260) and the player code tru+0x3200df (= retail 0x8240b7b4 = TU 0x8240e5f4, identical). The TU HUD script
(generalbank 37 function 15) enters its shadow-meter block (larabase f70-f73: delay, red, pulse) only when larabase f36
answers 1 (`op69 f36; op50; op64 -> +0x180c`). With the flag only in the plugin f36 answered 0 and f70-f73 were never
called (run 20261103_213440_paket05_leiste). 0.4 makes the TU's store; `TrackerFlag=0` restores 0.3. Only HUD
script 37 calls larabase f36 in the installed mods (`tools/drm_script_refs.py <mods> 213`: one reference, +0x174c).

### 0.3: why DLC 1 after DLC 2 was the doppelganger (F12)

The game's state save (PC tru+0x155cb1; TU 0x821fef58) copies the current costume into the chosen costume
(game data `+0x20c`). After DLC 2 it holds 857 `doppelganger_casual` (the TU saves 11 `lara_doppelganger` instead -
0x821ff0dc..0x821ff118 - and turns it back into `doppelganger_casual` at the next level load, the same result). The
next level load takes the chosen costume before the unit default. On the Xbox no other unit is ever loaded with that
word: the mission menu starts every DLC through the new-game reset. The PC's direct level change does not, so
`level.load dlc_level1_start` loaded the doppelganger, ran DoppelgangerInit again (shadow power, wrong controls).

Which units are DLC 2 is read from the data, not from a name list: the unit default costume is 11 `lara_doppelganger`
in `dlc_level2_start`, `dlc_yggdrasil_hall01`, `dlc_yggdrasil_hall02`, `dlc_yggdrasil_end` and 25 in the DLC 1 units
(`tools/unit_default_costume.py <unit>.drm --sec 0`). The reset therefore keeps the doppelganger inside DLC 2 (also
for a chosen 857 on a DLC 2 unit change) and never touches a costume that is not the DLC 2 player.

Not a TU code path (the TU has no direct level change) - only its outcome. A doppelganger chosen on purpose outside
DLC 2 (TruMenu `costume.choose doppelganger_casual`) is reset as well; `CostumeReset=0` brings back 0.2.

## Options (`TruDlc2Player.ini`, section `[Dlc2Player]`)

| Key | Default | Meaning |
|---|---|---|
| `Enabled` | 1 | 0 = load, patch nothing |
| `LogLevel` | 1 | 0 errors, 1 info (one line per level load), 2 + every new game tracker and every kept DLC 2 costume |
| `Costume` | 1 | the TU's name substitution (needs `TypeRecord=1`) |
| `TypeRecord` | 1 | the type record `doppelganger_casual` |
| `FlagReset` | 1 | 0.2: flag = 0 with every new game tracker |
| `CostumeReset` | 1 | 0.3: chosen-costume reset outside DLC 2 (needs `Costume=1`, same detour) |
| `TrackerFlag` | 1 | 0.4: DoppelgangerInit also stores game tracker +0x1244 = 1 (TU 0x82412c84) |
| `[Costume] TuMapping` | 0 | 0.5: the TU's 857 <-> 11 mapping in state save / load / both spawns (needs `TypeRecord=1`, `Costume=1`; 0 = nothing patched, as 0.4) |
| `[Mission] DialogStart` | 1 | 0.6: a level started from the game (pause menu -> DLC, dialog accept case 8) as the TU: `dlc_level2..6_start` without the outfit selection, every level with the new-game reset (independent of the other keys; 0 = nothing patched, as 0.5) |
| `[Mission] DialogDifficulty` | 0 | 0.7: that start also sets the player tailoring to Medium (1) through the game's five setters and clears the render hold `[0xdb94de]` after the case, as the TU (needs `DialogStart=1`; 0 = nothing patched, as 0.6) |
| `[Mission] DialogHoldClear` | 0 | 0.8: the dialog's cases 4 and 6 clear the render hold `[0xdb94de]` right after their call, as the TU (0x8247f1dc / 0x8247f2b4; independent of the keys above; 0 = nothing patched, as 0.7) |

## Log lines (`TruDlc2Player.log` next to `tru.exe`)

- start: `TruDlc2Player 0.3 loaded (... costume reset 1)`, `costume reset: a level load of "lara_doppelganger" /
  "doppelganger_casual" in a unit whose default costume is not "lara_doppelganger" ...`; on a code mismatch
  `costume reset: unit default code ... does not match - reset off`.
- DLC 2 start: `level load 1: costume "lara_doppelganger" -> doppelganger_casual (...)`, `DoppelgangerInit finished`.
- DLC 1 after DLC 2: `level load N: costume "doppelganger_casual" (chosen +0x20c 857 / +0x210 0) in unit U whose
  default is "<name>" (25, not lara_doppelganger = no DLC 2 unit): chosen costume +0x210 / +0x20e / +0x20c = 0 as the
  TU's mission start (...), unit default loaded`, then `level load N: costume "doppelganger_casual" -> <name> (...)`
  and **no** `DoppelgangerInit finished` after it.

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruDlc2Player -OutDir work\asi\dlc2p03` (x86, `/MT`, /W4, imports
  only KERNEL32).
- Install: through a test profile (`tests\profiles\paket14_dlc1nachdlc2.json`, `Invoke-TruTestRun.ps1`) or
  `scripts\windows\Set-TruDlc2Player.ps1 -Install` (game closed). Remove: `Set-TruDlc2Player.ps1 -Remove`.

## Test (0.3)

1. DLC 2 via TruMenu AutoStart (mission start), play a little (a checkpoint / autosave writes 857 into `+0x20c`).
2. Ring -> Tests -> Rundgang -> DLC 1 (`level.load dlc_level1_start`).
3. Expected: normal Lara in DLC 1, stick forward walks, RB does nothing, camera steady; log lines as above.

## Test (0.4, build `work\asi\dlc2p04`)

With TruShadowHud 0.1 (`work\asi\hud01`), TruShadowPower 0.11+ and a generalbank with the TU HUD script (tree
`dlc_test50l_hud`, or `dlc_test50l_hud_input` which also has the TU input bindings):

1. Start: `TruDlc2Player 0.4 loaded (... tracker flag 1)`, `tracker flag: DoppelgangerInit also stores game tracker
   [0x00fadb58]+0x1244 = 1 ... verified`.
2. DLC 2 start: `DoppelgangerInit finished (instance ...) - game tracker +0x1244 = 1 (TU 0x82412c84; ...)`; then in
   TruShadowHud.log `larabase f73 ... first call`, `f72 ... first call`, `f71 ... first call`.
3. Hold RB until the meter is (nearly) empty: the meter turns **red** (f72 -> 0) until it refilled above 150;
   above 75 % it **pulses** (f71 -> 1) - compare with Xenia.
4. Anything odd in DLC 2 (player costume / weapons after a reload, see the player code tru+0x3200df): `TrackerFlag=0`.
5. DLC 1 / main game after DLC 2: the tracker is rebuilt (memset) - HUD as before, no red / pulse.

## Test (0.5, build `work\asi\dlc2p05`)

Back up the saves first (a save written with `TuMapping=1` holds 11 in the chosen costume, like an Xbox save).

1. `TuMapping=0` (default): start line `TruDlc2Player 0.5 loaded (... [Costume] TU mapping 0)`, `costume map: off
   ([Costume] TuMapping=0) - saves keep 857 ...`; everything as 0.4.
2. `TuMapping=1` (TO TEST switch `ini:TruDlc2Player:Costume:TuMapping`, read at start): `costume map: TU 857 <-> 11
   patched at state save 0x00555cb1, state load 0x00556fbd, player spawn 0x005d42e9, switch spawn 0x005d4469 ...`.
3. DLC 2, reach a checkpoint: `costume map N (state save, TU 0x821ff0dc..0x821ff118): current 857 = doppelganger_casual
   -> chosen +0x20c = 11 (lara_doppelganger)`; Lara stays the doppelganger.
4. Die / reload the checkpoint: `costume map N (state load, ...): chosen +0x20c 11 = lara_doppelganger -> current 857`,
   then the level load `level load N: costume "lara_doppelganger" -> doppelganger_casual (... chosen +0x20c 11 ...)`;
   Lara is the doppelganger again with the shadow power.
5. DLC 1 after DLC 2 (`level.load dlc_level1_start`): the 0.3 reset line with `costume "lara_doppelganger" (chosen
   +0x20c 11 ...)` and normal Lara.
6. A `costume map ... (player spawn ...)` / `(switch spawn ...)` line appears only when a spawn sees 11 - rare on PC
   (the level load already loads 857); none is expected in a normal run.

## Test (0.6, build `work\asi\dlc2p06`)

Install with `Set-TruDlc2Player.ps1 -Install -SourceDir work\asi\dlc2p06` (game closed; an edited .ini is kept - the
built-in default `DialogStart=1` applies when the key is missing).

1. Start: `TruDlc2Player 0.6 loaded (... [Mission] dialog start 1)`, `dialog start: RegisterAcceptChanges case 8 ...
   (detour at 0x0077e8c0, 35 bytes)`.
2. Main menu -> DLC -> DLC 2: no outfit screen, doppelganger (unchanged, script 104); no `dialog start` line.
3. In DLC 1: pause -> DLC -> DLC 2 -> yes: `dialog start 1: level "dlc_level2_start" ... f27 UILoadLevel(..., 0, 0, 1)
   ... without costume / weapon selection`, `selection byte [0x00fae8d9] = 0`, then `level load N: costume
   "lara_doppelganger" -> doppelganger_casual (... chosen +0x20c 0 ...)` and `DoppelgangerInit finished`; no outfit
   screen in the game.
4. In DLC 2: pause -> DLC -> DLC 1 -> yes: `dialog start N: level "dlc_level1_start" ... 1, 0, 1 ... WITH costume /
   weapon selection`; the outfit screen appears (as on the TU), Lara in the chosen outfit.
5. If the game crashes or hangs after "yes": `DialogStart=0` and send TruDlc2Player.log + TruMenu.log.

## TO TEST (0.7, build `work\asi\dlc2p07`)

Install with `Set-TruDlc2Player.ps1 -Install -SourceDir work\asi\dlc2p07` (game closed). `DialogDifficulty` is 0 by
default: set `[Mission] DialogDifficulty=1` in the installed `TruDlc2Player.ini` (an edited 0.6 .ini lacks the key -
then the built-in 0 applies). TruMenu Fixes row since TruMenu 0.22.23 (switch file limit 512): group `DLC 2 Spielerin /
Kostüm`, `Levelstart: Anpassung auf Mittel` (restart).

1. `DialogDifficulty=0`: start line `TruDlc2Player 0.7 loaded (... dialog start 1, dialog difficulty 0)`,
   `dialog difficulty: off ...`; everything as 0.6.
2. `DialogDifficulty=1`: `dialog difficulty: case 8 also resets the player tailoring to Medium (setters 0x006e75a0 ...)
   ... (call at 0x0077e8f9 redirected; TU 0x8247f57c)`.
3. In the game's options set the difficulty / tailoring values away from Medium (e.g. enemy health high, player health
   low); note them.
4. In DLC 1: pause -> DLC -> DLC 2 -> yes: `dialog difficulty 1: player tailoring reset to Medium (1) ... EnemyHP
   +0x3ef98 <old> -> 1, AmmoAdj +0x3ef9c <old> -> 1, PlayerHP +0x3efa4 <old> -> 1, SavingGrabAdj +0x3efa8 <old> -> 1,
   f10 +0x3efac <old> -> 1`, then the 0.6 `dialog start 1: ...` lines, then `dialog difficulty 1: case-8 tail - render
   hold [0x00db94de] <b> -> 0` (note `<b>`: 1 = the pause menu's hold was still set at that point - then the TU
   store matters; 0 = it was already cleared); DLC 2 starts normally.
5. In DLC 2 the options show Medium for all values (as on the Xbox TU); Lara's health / enemy health as Medium.
6. Main menu -> DLC -> DLC 2: no `dialog difficulty` line (script path; the TU resets there too - since Q40 the
   opt-in generalbank rule `tu134_tailoring`, see TO TEST 0.8 step 6; without it the values stay as set).
7. Crash / hang after "yes" or a frozen picture after the load: `DialogDifficulty=0`, send TruDlc2Player.log +
   TruMenu.log.

## TO TEST (0.8, build `work\asi\dlc2p08`)

Install with `Set-TruDlc2Player.ps1 -Install -SourceDir work\asi\dlc2p08` (game closed). `DialogHoldClear` is 0 by
default: set `[Mission] DialogHoldClear=1` in the installed `TruDlc2Player.ini` (an edited 0.7 .ini lacks the key -
then the built-in 0 applies). TruMenu Fixes row (since Q41, `TruMenu.switches.txt`): group `DLC 2 Spielerin / Kostüm`,
`Dialog 4/6: Render-Halt aus` / `Dialog 4/6: clear render hold` (restart) - next to the rows of `DialogStart` and
`DialogDifficulty`.

1. `DialogHoldClear=0`: start line `TruDlc2Player 0.8 loaded (... dialog difficulty D, dialog hold clear 0)`,
   `dialog hold: off ...`; everything as 0.7.
2. `DialogHoldClear=1`: `dialog hold: RegisterAcceptChanges cases 4 and 6 clear the render hold [0x00db94de] ... (case
   4: call at 0x0077e7fe ... case 6: calls at 0x0077e860 / 0x0077e88d ...)`.
3. Case 4 = the pause / main menu ring's dialog with action 4 (script 7 f8 +0x17460 / +0x1748c; which menu item it is
   was not traced - try the pause menu's yes / no items such as restart / load / quit and answer yes): `dialog hold N:
   case 4 (after tru+0x37e460 = TU bl 0x8247e000) - render hold [0x00db94de] <b> -> 0`; the game goes on as before
   (`<b>` 1 = the hold was still set, the TU's clear matters).
4. Case 6 (a level start that compares the name with `ee_01`; no generalbank script opens action 6 - it may never
   appear): a `dialog hold N: case 6 (level "...", after tru+0x1dfb20(name, 1) ...)` line only if it does.
5. Animated shaders (water, light shafts) after such a dialog: running (not frozen) - compare with 0.7.
6. Main menu tailoring (data, not this plugin): build the generalbank with
   `tools/generalbank_pc_build.py build work/rebuild/generalbank_pc_tailoring --tailoring` (md5 014bce24...), install
   it as `mods\generalbank.drm`; set the difficulty values away from Medium; main menu (no game running) -> DLC ->
   DLC 2: the values are Medium (1) afterwards, as on the TU. Undo: the default build (810711f1...).
7. Crash / hang after a dialog "yes": `DialogHoldClear=0`, send TruDlc2Player.log + TruMenu.log.
