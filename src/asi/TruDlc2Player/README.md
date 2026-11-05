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

Every patched byte is compared with the expected code / data first; on a mismatch that part is left alone and the
reason is logged.

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
