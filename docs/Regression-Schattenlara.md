# Regression test: shadow Lara (doppelganger)

Profile `tests/profiles/regress_shadowlara.json`, run by `scripts/windows/Invoke-TruTestRun.ps1`.

## Purpose

One repeatable game run that shows whether the DLC 2 shadow Lara still works end to end: costume swap to
`doppelganger_casual`, DoppelgangerInit, the title-update ids, shadow power (slow motion + meter), the ledge, the
rock channel wall run, and no crash. Automatic checks read the plugin logs and the cdb log; the owner marks the
visual checks in TruMenu's TO TEST page. Every run gets one verdict, and two runs can be compared.

## When to run

After any change to:

- `TruDlc2Player`, `TruDoppelganger`, `TruRockVein`, `TruShadowPower` (source, INI defaults or build),
- the `doppelganger_casual` data (`doppelganger_casual.drm`, `player_tru_dlc2_extension.drm`),
- the pipeline statechart steps that build those files.

When a new tree or new ASI builds are tested, update the tree `source`, the `md5` and the `sha256` values in the
profile (or run with `-AllowMd5Mismatch` once and copy the values from `installed.json`).

## Command line

From the repository root, game closed:

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile regress_shadowlara -Debugger -Session <path to a cdb session like session_exit.cdb>
```

The session must echo the markers `D3DFAIL`, `AV2NDCHANCE`, `FASTFAIL`, `MESSAGEBOX_A` / `MESSAGEBOX_W` on lines of
their own and end with `g` (as `session_exit.cdb` does). Without `-Debugger` there is no `cdb.log`: the four cdb
checks show a warning and the verdict cannot be better than INCOMPLETE.

Offline re-evaluation of an existing run folder (no game needed; rewrites that folder's summary):

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -Evaluate <run folder> -RunProfile regress_shadowlara
.\scripts\windows\Invoke-TruTestRun.ps1 -Compare <older run folder> -CompareTo <newer run folder>
```

## Known gap: chosen-costume reset

The direct start loads the costume chosen in the game data (`+0x20c` / `+0x210`). If a costume was chosen in an
earlier session, the level loads e.g. `dlc_costume_f` instead of `lara_doppelganger`, the swap does not happen and
the check `dlc2-costume` fails. Until this reset is built into TruDlc2Player (as the title update's new-game reset),
run the workbench helper `Reset-TruCostumeLive.ps1` (not in the repository) in a second console **after** the harness
has preloaded the TO TEST rows (TruLink serves one client at a time) and before the DLC 2 level loads.

## State

As `dlc2_48h`: tree `work/rebuild/dlc_test48h/mods`, ASIs TruDlc2Player, TruDoppelganger, TruRockVein,
TruShadowPower 0.5.1 (`work/asi/v05`), TruLink, TruMenu 0.5 (`work/asi/menu05`), the same three switches. One
difference: TruShadowPower `[ShadowPower] LogLevel=2`, because `shadow power ON` / `OFF` are logged only at level 2.

## Owner steps (TO TEST)

1. Wait in the main menu until it is shown completely.
2. L3 + R3: TruMenu opens on TO TEST; check the three switches.
3. Close the menu and wait for the automatic direct start into DLC 2 (no `level.load`).
4. Let the intro cutscene play to its end.
5. Move Lara (walk, run, camera).
6. Walk to the first ledge, jump, grab it, climb up.
7. Hold RB for a few seconds: slow motion, the yellow silhouette drains.
8. Release RB: normal speed, the silhouette refills.
9. At the rock channel (Felsrinne) wall: hold RB and press A (wall run).
10. Take a hit or fall from a small height: health drops.
11. Mark the checks (A ok, X fail, Y skip), then end the game normally.

Owner checks: `cutscene`, `doppel-look`, `d3d-box`, `ledge`, `shadow-power`, `wall-run`, `no-crash`.

## Automatic checks

| Id | File | Mode | What it shows |
|---|---|---|---|
| dlc2-costume | TruDlc2Player.log | present | `level load n: costume "lara_doppelganger" -> doppelganger_casual` |
| dlc2-init | TruDlc2Player.log | present | `DoppelgangerInit finished` |
| doppel-ids | TruDoppelganger.log | present | `title-update ids registered: 13 conditions, 9 activities, 8 states` |
| sp-loaded | TruShadowPower.log | present | `TruShadowPower 0.5.x loaded (enabled 1` |
| sp-conditions | TruShadowPower.log | present | `Lara conditions: 1049-1054 ... added` |
| sp-states | TruShadowPower.log | present | `Lara states: 243 ... added` |
| sp-on / sp-off | TruShadowPower.log | present, min 1 | `shadow power ON` / `shadow power OFF` (steps 7 / 8) |
| sp-no-mismatch | TruShadowPower.log | absent | no `does not match` (every patched code site found) |
| rv-patched | TruRockVein.log | present | `jump table patched: 607 -> ..., 608 -> ...` |
| rv-607 / rv-608 | TruRockVein.log | present, **optional** | `condition 607/608 is now evaluated` - wall-run target, may still fail |
| cdb-d3dfail, cdb-av, cdb-fastfail, cdb-msgbox | cdb.log | absent | the marker lines (anchored, so the session's own command echo does not count) |

The patterns are in the profile (`expects`); the format is described in the script header.

## Reading the summary

`runs/<time>_regress_shadowlara/summary.md` starts with the verdict line:

- **PASS** - every non-optional automatic check ok, no crash marker, every owner check marked ok.
- **FAIL** - an automatic check failed, a crash marker (or crash exit code) was found, or an owner check is marked fail.
- **INCOMPLETE** - nothing failed, but a file is missing (e.g. no `cdb.log`), owner checks are open / skipped, or
  the run timed out.

The section "Automatic checks" lists each check with result (ok / fail / file missing), the pattern, the number of
matching lines and the first matching line. Optional targets are shown but not counted. `summary.json` holds the
same data (`expects`, `verdict`, `verdictNotes`). `-Compare` lists changed checks (`check <id>: ok (1 lines) -> fail
(0 lines)`) and a changed verdict next to md5s, markers and owner states.

## Bisecting with the switches

The three INI switches (`dlc2-costume`, `sp-states`, `sp-conditions`) are written by the harness before the start
from their `"initial"` value; a change in the menu only acts at the next start and is overwritten by the next harness
run. To bisect, copy the profile (any path works with `-RunProfile <path>`), set one switch to `"initial": "off"`,
run, and compare with the last good run:

- `sp-conditions` off: `sp-conditions` fails by design; if the crash / wall-run fault is gone, look at 1049-1056.
- `sp-states` off: `sp-states` fails by design; states 243 / 245 / 1018 are the suspects.
- `dlc2-costume` off: Lara keeps `lara_doppelganger`; `dlc2-costume` fails by design (`dlc2-init` presumably as
  well); isolates the costume swap from the TruShadowPower / TruRockVein side.

Plugins can be left out the same way: drop the ASI from `asis` in the copy (it is then removed for that run).
