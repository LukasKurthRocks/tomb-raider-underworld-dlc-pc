# Regression test: DLC 1 "Beneath the Ashes"

Counterpart of `Regression-DLC2.md` (DLC 2). Profile `tests/profiles/regress_dlc1.json` (created 2026-11-02
from `regress_shadowlara_50f`: the same trees and plugins, so DLC 1 is checked in the state the DLC 2 tests leave the
game in; 18 rows, 10 automatic checks), run by `scripts/windows/Invoke-TruTestRun.ps1`.

**Note while the test generalbank 41e is installed:** it auto-starts DLC 2 after the main menu's attract timer. Open
the mission menu at once, or use TruMenu `level.load dlc_level1_start` (no intro). Do not play DLC 2 in the same
session before DLC 1: the doppelganger flag is not reset yet (known gap) and the DLC 2 plugins would act in DLC 1.

## Purpose

DLC 1 has run since the B138 kit and our pipeline rebuild, but most work since 2026-10-31 went into DLC 2. Several
changes are global and can break DLC 1 without anyone noticing: the generalbank scripts (hint script 9 is global -
test 36 once showed DLC 1 hints wrongly as a paused box), the shader / material fixes (shader libraries are global by
id), the achievement fix, and the plugins that load in every level (TruShadowPower, TruRockVein, TruDoppelganger,
TruDlc2Player, TruMenu, TruLink, TruGuard). This list holds everything that has been seen working in DLC 1.

## When to run

- After a change to the generalbank scripts, the shared shader / material fixes, the `Fixes` / `Repair` pipeline steps
  or the DLC 1 tree.
- After a change to any plugin that hooks global code (pad hook, state / condition tables, markup code, Present).
- At least once per milestone together with the DLC 2 regression.

## Command line

As for DLC 2, game closed, from the repository root:

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile regress_dlc1 -Debugger -Session <path to a cdb session like session_exit.cdb>
```

## Owner steps and checks

Ids in brackets are the check ids. References are in `references/DLC1/`.

**Start and loading**

1. Main menu: the DLC mission menu shows "Unter der Asche" / "Beneath the Ashes" (title and text in the game
   language) (`dlc1-menu`; reference `references/PC-Fix_DLC-Missionsmenue_*`).
2. Start DLC 1 from the mission menu (not with `level.load`, which skips the intro).
3. Loading screen: title "UNTER DER ASCHE" / "BENEATH THE ASHES" above the line, the description directly below the
   line, not on it (`dlc1-load-title`; reference `Xenia-TU_DLC1_01` / `_12`). Known: the text started one line too
   high before test 41e - mark what you see.
4. The intro cutscene plays to its end in the game language (voice / subtitles), the skip-cinematic bar looks as on
   the Xbox (`dlc1-cutscene`; reference `Xenia-TU_DLC1_10`).

**Level**

5. Lara is in her normal DLC 1 outfit (no doppelganger, no DLC 2 costume swap) (`dlc1-lara`).
6. Health-pack hint: text at the top right in a faint dark box, **no** "Press A" line and **no** pause
   (`dlc1-hint`; reference `Xenia-TU_DLC1_11`).
7. Grapple points: a rusty copper ring with highlights, the holder without a yellow / olive highlight; in the camera
   zoom the ring is shiny copper (`dlc1-grapple`; references `PC-Test26a-*_13/_14`, `Xenia-TU_DLC1_08/_09`).
8. The adrenaline bridge (padshock entry `dlc1_adren_bridge`): crossing it does not crash (`dlc1-bridge`).
9. Hold RB / LB: normal DLC 1 behaviour (no slow motion, no shadow meter in the HUD) - the DLC 2 plugins must stay
   inactive outside DLC 2 (`dlc1-no-shadow`).
10. Take a hit / fall: health drops; jump to death: no crash, Lara reappears at the checkpoint (`dlc1-death`).
11. Treasure room (`dlc_treasureroom`, achievement fix): entering it and its trigger do not crash (`dlc1-treasure`;
    TruMenu `level.load dlc_treasureroom` is allowed for this step if the way is long).
12. Outfit list (pause menu / outfit selection): entries with English / German descriptions as on the Xbox, four
    lines (`dlc1-outfits`; reference `PC-Test41e-*_22`, `Xenia-TU_DLC1_13`). Known: the costume packs (Legend Lara,
    Red Drysuit, ...) are not ported yet - fewer entries than on the Xbox is the known gap.
13. Mark the checks, end the game normally. Whole run: no crash, freeze or box (`no-crash`).

## Automatic checks (`regress_dlc1.json`; also `doppel-ids` - the plugins loaded)

| Id | File | Mode | What it shows |
|---|---|---|---|
| dlc1-no-swap | TruDlc2Player.log | absent | no `costume "lara_doppelganger" -> doppelganger_casual` (DLC 1 must not swap) |
| sp-no-on | TruShadowPower.log | absent | no `shadow power ON` (needs LogLevel 2; the power must stay off outside DLC 2) |
| rv-no-mismatch, sp-no-mismatch | plugin logs | absent | every patched code site found |
| guard-faults | TruGuard.log | absent | no `TRUGUARD_DETAIL` (no first-chance fault in the game code) |
| cdb-d3dfail, cdb-av, cdb-fastfail, cdb-msgbox | cdb.log | absent | the crash / box markers |

## Open

- Pipeline rebuild of DLC 1 against B138 (TODO "Pipeline-Nachbau DLC 1"); install variants "only DLC 1 / only DLC 2 /
  both" (10 files differ between the packs).
- DLC 1 has not been played end to end on PC; extend this list with every new place that is seen working.
