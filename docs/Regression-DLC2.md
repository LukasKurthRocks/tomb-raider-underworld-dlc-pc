# Regression test: DLC 2 "Lara's Shadow" (shadow Lara / doppelganger)

Profile `tests/profiles/regress_shadowlara.json` (template; the per-build copies are `regress_shadowlara_<test>.json`),
run by `scripts/windows/Invoke-TruTestRun.ps1`. The DLC 1 counterpart is `Regression-DLC1.md`.

## Purpose

One repeatable game run that shows whether everything that worked once in DLC 2 still works: start and loading
screen, intro, the doppelganger look, hints, HUD, the shadow power, the rock channel wall run, death / respawn,
leaving DLC 2, and no crash. Things that worked before can break again after any change, so the list only grows.
Automatic checks read the plugin logs and the cdb log; the owner marks the visual checks in TruMenu (TO TEST page
today; a separate "Regression" page with DLC 1 / DLC 2 lists is planned, see the TruMenu plan). Every run gets one
verdict, and two runs can be compared.

## When to run

After any change to:

- `TruDlc2Player`, `TruDoppelganger`, `TruRockVein`, `TruShadowPower`, `TruMenu` (source, INI defaults or build),
- the DLC 2 data (`doppelganger_casual.drm`, `player_tru_dlc2_extension.drm`, `dlc_level2_start.drm`, shader /
  material fixes, state chart fixes),
- the pipeline steps that build those files.

When a new tree or new ASI builds are tested, copy the newest `regress_shadowlara_<test>.json`, update the tree
`source`, the `md5` and the `sha256` values (or run with `-AllowMd5Mismatch` once and copy the values from
`installed.json`), and keep every step / check below.

## Command line

From the repository root, game closed:

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile regress_shadowlara_<test> -Debugger -Session <path to a cdb session like session_exit.cdb>
```

The session must echo the markers `D3DFAIL`, `AV2NDCHANCE`, `FASTFAIL`, `MESSAGEBOX_A` / `MESSAGEBOX_W` on lines of
their own and end with `g` (as `session_exit.cdb` does); it should also write a full dump on a second-chance access
violation (`.dump /ma`) - copy that dump away before the next run, it is overwritten. Without `-Debugger` there is no
`cdb.log`: the four cdb checks show a warning and the verdict cannot be better than INCOMPLETE.

Offline re-evaluation of an existing run folder (no game needed; rewrites that folder's summary):

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -Evaluate <run folder> -RunProfile regress_shadowlara_<test>
.\scripts\windows\Invoke-TruTestRun.ps1 -Compare <older run folder> -CompareTo <newer run folder>
```

## Known gap: chosen-costume reset

The direct start loads the costume chosen in the game data (`+0x20c` / `+0x210`). If a costume was chosen in an
earlier session, the level loads e.g. `dlc_costume_f` instead of `lara_doppelganger`, the swap does not happen and
the check `dlc2-costume` fails. Until this reset is built into TruDlc2Player (as the title update's new-game reset),
run the workbench helper `Reset-TruCostumeLive.ps1` (not in the repository) in a second console **after** the harness
has preloaded the TO TEST rows (TruLink serves one client at a time) and before the DLC 2 level loads.

## State (2026-11-02)

Last full runs: test 50d family (`regress_shadowlara_50d`, `_50d_nolook`, `_50d_nojump`, `_50b`): 50c data (outfit
with all 14 title-update shaders, rock vein shader, 134 condition records), TruRockVein 0.8, TruShadowPower 0.8,
TruMenu 0.7, TruLink 0.3, TruGuard 0.4. Known failures: **crash after a wall run** (heap, the jump from the wall to the
upper edge; under analysis -> test 50e), the arm skin / gloves look, the shadow-power screen look (missing), player
event 0x87 (look on). `sp-loaded` fails on 0.8 only because 0.8 has no "loaded" line at the top of its log - fix the
pattern in the next profile.

## Owner steps and checks

Ids in brackets are the TO TEST / regression check ids. Steps without an id are actions only.

**Start and loading**

1. Wait in the main menu until it is shown completely. L3 + R3: TruMenu opens; check the switches (a change needs a
   restart).
2. Close the menu and wait for the automatic direct start into DLC 2 (or start it from the DLC mission menu). Do not
   use `level.load` here - it loads the unit directly and skips the intro.
3. Loading screen: title "LARAS SCHATTEN" / "LARA'S SHADOW" above the line, description below
   (`load-title`).
4. The intro cutscene plays to its end, picture and sound, no hang (`cutscene`).

**Look and HUD**

5. Move Lara: walk, run, turn the camera.
6. Doppelganger outfit as on the Xbox: dark red hair, black top / trousers, **black fingerless gloves**, natural face
   and **arm skin with faint veins** - no black / white blotches, no white, cyan, green, olive or red / white parts
   (`doppel-look`, `arms-gloves`; reference `references/DLC2/Xbox-TU_DLC2_05_*`).
7. No D3D error box after the load (`d3d-box`).
8. Waterfall in the first cave: luminous, translucent, moving (`waterfall`; reference `Xbox-TU_DLC2_07_*`).
9. HUD: green health silhouette and the yellow shadow silhouette next to it (`hud-meter`).

**Hints**

10. Shadow meter hint: a box at the top centre with the Lara symbol; the game pauses until A (`hint-shadow`;
    reference `Xenia-TU_DLC2_15`).
11. Rock channel hint ("Halten Sie LB oder RB gedrückt ..."): a box without symbol, the text stays after A
    (`hint-vein`; reference `Xenia-TU_DLC2_18`).

**Shadow power**

12. Hold RB for a few seconds: slow motion, the yellow silhouette drains; release RB: normal speed, the silhouette
    refills (`shadow-power`).
13. While RB is held: picture soft and over-bright (cyan-white), glow at Lara's hands; gone after release
    (`shadow-look`; reference `Xenia-TU_DLC2_24`). **Missing so far** - keep the check, mark fail until it works.

**Rock channel (Felsrinne)**

14. Rock vein strip: bright, raised stone blocks with a dark centre joint, not a dark flat strip, no black /
    flickering patches (`vein-look`; reference `Xenia-TU_DLC2_17`).
15. Without the power: jump against the rock channel - normal wall behaviour (no ledge, no fall through)
    (`wall-normal`).
16. Hold RB and press A at the wall: Lara attaches and runs up (`wall-run`).
17. Hanging in the wall run: press X to jump up to the upper edge; Lara grabs it and climbs up (`wall-to-ledge`).
    The Xbox behaviour still has to be confirmed in Xenia; the 50d-family crash happened here.
18. At the top: the yellow silhouette refills (`wall-top-refill`; reference `Xenia-TU_DLC2_25..30`).
19. Wall run until the meter is empty: Lara falls down (`wall-meter-empty`).
20. Leave the wall three ways: jump off (A + direction), release RB, run until she comes down near the floor; each
    time she lands or falls normally, no teleport (`wall-exit`).

**Damage, death, respawn**

21. Take a hit or fall from a small height: health drops (`health`).
22. After at least one wall run: jump to death - no crash; Lara reappears at the checkpoint, still as the doppelganger
    (`death-after-wall`).
23. TruMenu `time.scale 0.5`, jump to death, then `time.scale 1` - no crash (`death-timescale`).

**Leaving DLC 2**

24. Quit to the main menu and start a base-game level from there with TruMenu `level.start l1_seatop 0` (the game's
    mission start of that unit; since TruMenu 0.22.46 `level.load` is refused in the main menu - the game serves a level
    change request only inside a level) or `arena.go 1a` (Helheim hall): Lara looks normal, RB gives no slow motion, no
    shadow meter (`leave-dlc2`; the title update's reset of the doppelganger flag is not ported yet - a fail here is the
    known gap).
25. Mark the checks (A ok, X fail, Y skip), then end the game normally. Whole run: no crash, freeze or box
    (`no-crash`).

Later (blocked, add when built): combat with the power (aim at an enemy with RB, shadow strike - title-update states
244 / 1007 / 1014 / 1017-1020 and the target list), the shadow-power HUD through the real `larabase` natives.

## Automatic checks

The patterns are in the profile (`expects`); the format is described in the script header. Current set (50d):

| Id | File | Mode | What it shows |
|---|---|---|---|
| dlc2-costume | TruDlc2Player.log | present | `level load n: costume "lara_doppelganger" -> doppelganger_casual` |
| dlc2-init | TruDlc2Player.log | present | `DoppelgangerInit finished` |
| doppel-ids | TruDoppelganger.log | present | `title-update ids registered: 13 conditions, 9 activities, 8 states` |
| sp-loaded | TruShadowPower.log | present | load line of the expected version (pattern to fix for 0.8, see State) |
| sp-conditions / sp-states | TruShadowPower.log | present | Lara conditions 1049-1056 / states 243 / 245 / 1018 added |
| sp-1055-added, sp-1055-run (optional) | TruShadowPower.log | present | condition 1055 registered / asked in DLC 2 |
| sp-on / sp-off | TruShadowPower.log | present, min 1 | `shadow power ON` / `shadow power OFF` (step 12; LogLevel 2) |
| sp-look-* | TruShadowPower.log | present / absent | look code verified, on / off fired, no access fault (only with `[Look] Enabled=1`) |
| sp-no-mismatch, rv-no-mismatch | both logs | absent | no `does not match` (every patched code site found) |
| rv-loaded, rv-types, rv-slots, rv-patched, rv-action608-added, rv-jumpgeo | TruRockVein.log | present | the rock vein translations are active |
| rv-607 / rv-608 / rv-608-true / rv-action608-run / rv-geo-hit | TruRockVein.log | present, optional | the wall run was reached and used the type-22 code |
| rv-nullbox | TruRockVein.log | absent | the NullBoxGuard did not fire |
| cdb-d3dfail, cdb-av, cdb-fastfail, cdb-msgbox | cdb.log | absent | the marker lines (anchored, so the session's own command echo does not count) |

To add in the next profile: `guard-faults` (TruGuard.log absent `TRUGUARD_DETAIL` = no first-chance fault in the game
code), `chart-wall-exit` (TruRockVein chart log: a transition from the wall-run loop 1488-1494 into 1497-1505,
optional), `menu-loaded` (TruMenu version line).

## Reading the summary

`runs/<time>_<profile>/summary.md` starts with the verdict line:

- **PASS** - every non-optional automatic check ok, no crash marker, every owner check marked ok.
- **FAIL** - an automatic check failed, a crash marker (or crash exit code) was found, or an owner check is marked fail.
- **INCOMPLETE** - nothing failed, but a file is missing (e.g. no `cdb.log`), owner checks are open / skipped, or
  the run timed out.

The section "Automatic checks" lists each check with result (ok / fail / file missing), the pattern, the number of
matching lines and the first matching line. Optional targets are shown but not counted. `summary.json` holds the
same data (`expects`, `verdict`, `verdictNotes`). `-Compare` lists changed checks (`check <id>: ok (1 lines) -> fail
(0 lines)`) and a changed verdict next to md5s, markers and owner states.

## Bisecting with the switches

The INI switches listed as `toggle` rows (`dlc2-costume`, `sp-states`, `sp-conditions`) are written by the harness
before the start from their `"initial"` value; a change in the menu only acts at the next start and is overwritten by
the next harness run. To bisect, copy the profile (any path works with `-RunProfile <path>`), set one switch to
`"initial": "off"` or add an INI value to the plugin's `ini` block, run, and compare with the last good run:

- `sp-conditions` off: `sp-conditions` fails by design; if the crash / wall-run fault is gone, look at 1049-1056.
- `sp-states` off: `sp-states` fails by design; states 243 / 245 / 1018 are the suspects.
- `dlc2-costume` off: Lara keeps `lara_doppelganger`; `dlc2-costume` fails by design (`dlc2-init` presumably as
  well); isolates the costume swap from the TruShadowPower / TruRockVein side.
- `[Look] Enabled=0` (TruShadowPower 0.8): no look events / messages (= 0.7); profile `_50d_nolook`.
- `[RockVein] JumpGeometry=0` (TruRockVein 0.8): no type-22 jump-off / fall branches (= 0.7 geometry); profile
  `_50d_nojump`.

Plugins can be left out the same way: drop the ASI from `asis` in the copy (it is then removed for that run).

Bisect of 2026-11-02 (heap crash): death alone ok, death with `time.scale 0.5` ok, crash after a wall run in 50b /
50d / `_nolook` / `_nojump` - so not the 50c shaders, TruMenu 0.7, the 0.8 look or the 0.8 jump geometry.
