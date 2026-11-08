# Documentation index

All files in `docs/`, grouped by reader. "(upstream)" marks files that come from the original project's `main`; the
others were added on branch `windows`. The repository [README](../README.md) has the short overview and the current
state.

## Players

| File | What it is |
|---|---|
| [INSTALL.md](INSTALL.md) | (upstream) How to install the DLC on the Steam PC game from your own Xbox 360 DLC files with the release kit |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | (upstream, extended) 60 fps lock, the "display driver" box, known problems of the original PC game and their workarounds |
| [SETUP.md](SETUP.md) | (upstream) The developer route: which files you need to rebuild from the raw files, and how to install the result |

## Plugins

| File | What it is |
|---|---|
| [PLUGINS.md](PLUGINS.md) | All ASI plugins of the fork: purpose, version, state, INI switches, links to their READMEs; the title-update approach |
| [DLC_MENU.md](DLC_MENU.md) | The DLC mission screen on PC (title drawn over the description) and its fix in all six languages |

## Status and history

| File | What it is |
|---|---|
| [STATUS.md](STATUS.md) | (upstream) Status of the original project's build B270: what works, what was fixed offline, open issues |
| [../CHANGELOG.md](../CHANGELOG.md) | The fork's changes by date (section "Fork branch `windows`" at the top), then the original changelog |
| [DEVLOG.md](DEVLOG.md) | Snapshots from development builds, newest first; older README pictures and states move here |
| [Regression-DLC1.md](Regression-DLC1.md) | Regression test for DLC 1 *Beneath the Ashes*: profile, checks, what must still work |
| [Regression-DLC2.md](Regression-DLC2.md) | Regression test for DLC 2 *Lara's Shadow*: profile, automatic and visual checks |
| [UPSTREAM_DIFF.md](UPSTREAM_DIFF.md) | Generated list of what branch `windows` adds to upstream `main`: changed files, fault families, new parts |
| [LINEAGE.md](LINEAGE.md) | (upstream) Build lineage of the original project: what each build step added |

## Developers

| File | What it is |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Overview of the Windows rebuild: data flow, steps, learned tables, how results are verified |
| [PIPELINE.md](PIPELINE.md) | (upstream) How the `mods/` tree is produced, stage by stage, and which script does what |
| [ENGINE.md](ENGINE.md) | Engine reference by topic: how `tru.exe` and the Xbox title update work, with addresses and proofs |
| [WINDOWS_REBUILD.md](WINDOWS_REBUILD.md) | Running log of the pipeline rebuild on Windows: comparison with B138, run log, numbered findings |
| [DEVELOPMENT.md](DEVELOPMENT.md) | (upstream) Development notes moved out of the original README: repository map, rebuilding, coding agents, release kit |
| [AGENT_GUIDE.md](AGENT_GUIDE.md) | (upstream) Guide for a coding agent helping a user with the port, with ground rules |
| [WS_MAP.md](WS_MAP.md) | Map of the original author's `work/ws/` scripts to builds and overlay layers |
| [FINDINGS.md](FINDINGS.md) | (upstream) Former list of verified technical findings; now only a pointer to ENGINE.md |
| [INVESTIGATION.md](INVESTIGATION.md) | (upstream) What still has to be investigated, with hypotheses and the tools to use |

Also outside `docs/`: [scripts/windows/README.md](../scripts/windows/README.md) (the Windows scripts: install, plugins,
pipeline, test runs, tools) and the plugin READMEs in [src/asi/](../src/asi/).

## Research

| File | What it is |
|---|---|
| [RELATED_WORK.md](RELATED_WORK.md) | Earlier attempts to bring the DLC to PC, cdcEngine tools, other porting projects, techniques worth adopting |
| [COSTUMES.md](COSTUMES.md) | Notes on the Xbox 360 costume packs: which pack is which, the port (offline), what was left out |
| [DLC2.md](DLC2.md) | Notes on DLC 2 *Lara's Shadow*: the missing shadow power, the Xbox reference, the DLC 2 trees and checklist |

## About this fork

- A copy of the original repository with its **full, unchanged history**; the fork's work sits on top of it on branch
  `windows`.
- Made for the owner's own use: running the upstream pipeline on Windows, learning how it works, rebuilding DLC 1 step
  by step and comparing it with the B138 release, then trying DLC 2 (*Lara's Shadow*) and the costume packs.
- **It does not replace the original** and is not a competing release. No support, no guarantees, no game data: like
  the original, everything needs your own files.

## What the fork adds (overview)

- [scripts/windows/](../scripts/windows/README.md) – PowerShell scripts: install the kit, swap single mod files,
  display mode and language, tools, the pipeline step by step, a pre-upload check. The installer also takes the raw
  DLC package files as copied from the console (`Install-TruDlc.ps1 -Package`, or the files in `input\xbox-dlc-live\`):
  checked against a list of the known packages, verified block by block and extracted
  ([Raw Xbox LIVE packages](../scripts/windows/README.md#raw-xbox-live-packages))
- [src/asi/](../src/asi/) – the plugins (ASI, loaded by ModLoader): the title update's shadow power and DLC 2 player
  code translated, the base-game comfort plugin `TruQoL`, test helpers `TruMenu`, `TruLink`, `TruTrace`,
  `TruDataGuard`, and TruGuard (crash guard by a contributor; see its own folder); each with its own README, installed
  with `scripts/windows/Set-Tru*.ps1`. Overview: [PLUGINS.md](PLUGINS.md)
- Test runs: `scripts/windows/Invoke-TruTestRun.ps1` with the profiles in `tests/profiles/` (which test builds and
  plugins to install, what to check, expected log lines, verdict), `Test-TruPreflight.ps1`, `Install-TruTree.ps1`
- [WINDOWS_REBUILD.md](WINDOWS_REBUILD.md) – running the pipeline on Windows: missing glue scripts rebuilt,
  stage-by-stage comparison with B138, run log and findings
- [ARCHITECTURE.md](ARCHITECTURE.md) – overview of the Windows rebuild: data flow, steps, learned tables, how results
  are verified
- [RELATED_WORK.md](RELATED_WORK.md) – what we researched and found: earlier attempts to bring the TRU DLC to PC (Tomb
  Raider Forums 2011-2026), cdcEngine tools, other porting/decomp/recomp projects, techniques worth adopting
- [WS_MAP.md](WS_MAP.md) – map of the author's `work/ws/` scripts, builds and overlay layers
- [DLC_MENU.md](DLC_MENU.md), [DLC2.md](DLC2.md), [COSTUMES.md](COSTUMES.md) – DLC menu text fix (all six languages),
  notes on DLC 2 and the costume packs
- New tools in `tools/` (e.g. `compare_b138.py`, `compare_sections.py`, `compare_audio.py`, `dlc_media_build.py`,
  `dlc_audio_build.py`, `mul_audio_nch.py` - the audio fix for non-stereo `.mul`, `dlc_assemble_build.py` (also DLC 2),
  `mesh_tables_build.py`, `tree_check.py`)
- [CHANGELOG.md](../CHANGELOG.md) – section "Fork branch `windows`" at the top: what this fork changed, by date (no
  release of the port)
- [UPSTREAM_DIFF.md](UPSTREAM_DIFF.md) – only what this fork has that the original's `main` does not: changed upstream
  files with the reason, converter fault families with their checks, names, new parts (generated by
  `scripts/windows/New-TruUpstreamDiff.ps1`)
