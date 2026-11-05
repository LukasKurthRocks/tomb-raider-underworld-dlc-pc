# Tests

Test runs of the game for branch `windows`: one profile = one run of `scripts/windows/Invoke-TruTestRun.ps1`, which
installs the profile's trees, plugins and INI settings, starts the game (optionally under `cdb`), preloads the checks
into the in-game menu (TruMenu, over TruLink), waits for the game to end, collects logs, dumps and screenshots, checks
the expected log lines and writes a verdict to `runs\<time>_<profile>\summary.md`. Before a run:
`scripts/windows/Test-TruPreflight.ps1 -RunProfile <profile>` (read-only; its "Data" lines check the texture group
counts and the SoundPlex sequence repeat bytes of what the profile installs).

| Folder | Content |
|---|---|
| `profiles/` | the active profiles (JSON): `trees` (mods trees in install order, every file pinned by MD5), `asis` (plugins with their INI settings), `files`, `trulink` (commands sent at the start), `tests` (the rows shown in game), `expects` (log patterns, mode present / absent, optional or not) |
| `profiles/archive_regress/` | older intermediate profiles kept for reference (see its README); not run any more |
| `flows/` | guided test flows for TruMenu 0.11 (`TruMenu.flow.txt` format, see `src/asi/TruMenu/README.md`), written from a profile by a workbench script |
| `regress/` | the regression lists TruMenu shows on its regression page (`dlc1.txt`, `dlc2.txt`), from `docs/Regression-DLC1.md` / `docs/Regression-DLC2.md`; checked by `tools/trumenu_ini_check.py` |

**Names.** `paketNN_<topic>` = test package NN ("los NN" in the owner's notes), one topic per package; a letter
(`paket15e`) is a variant of the same package, `t` a variant with the log-only plugin TruTrace, `_flow` one with a
guided flow. `regress_*` / `dlc2_*` are the regression runs and older single tests. The names stay as they are: runs,
notes and docs refer to them.

**Language.** The repository is English. The exceptions are deliberate: the rows in `tests` of many profiles and the
steps in `flows/` are **German**, because they are the instructions the tester reads in the game. Profile
descriptions, ids and expects are English. Quotes of German game text in the docs (hint boxes, loading-screen titles)
are evidence and stay as the game shows them.

**Fix trees on top.** Every active profile ends with the data-fix trees it needs (for example `dlc_test51q_dungeon`
and one `dlc_test51r_seq*` tree for the texture group counts and the sequence repeat bytes). A new profile that
installs other copies of those files needs its own fix tree: `tools/profile_fix_plan.py` computes which.
