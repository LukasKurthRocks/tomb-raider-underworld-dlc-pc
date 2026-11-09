# Windows scripts

PowerShell helpers around trudlcport for Windows: install the release kit, swap single files in `mods\`, set display
mode and language, fetch the tools, run the conversion pipeline step by step, and check our commits before an upload.
They were written for one Windows PC with its own copy of the game and its own Xbox 360 files (see the notice in the
main [README](../../README.md)).

All scripts run in Windows PowerShell 5.1 and PowerShell 7, are read-only unless their help says otherwise, and
write a log per run. `-Verbose` shows the steps, `-Debug` paths, hashes and command lines, `-Trace` adds a
PowerShell line trace. Help: `Get-Help .\scripts\windows\<script>.ps1 -Full`.

Shared helpers live in `TruCommon.psm1` next to the scripts; every script imports it at the top. It holds the run
log writer (`Set-TruLogFile`, `Write-Log`), the workspace paths (`Get-TruWorkspacePath`), the Steam game folder search
(`Find-TruGamePath`) and `Get-Md5`. Its functions take over the calling script's `-Verbose`/`-Debug` and
`ErrorActionPreference`, so they behave like the former per-script copies. Keep the module in this folder.
`TruDlcPackage.psm1` (raw Xbox LIVE packages: `Expand-TruDlcPackage`, `Test-TruDlcInput`, `Get-TruDlcPackageList`)
builds on it, together with the known-packages list `TruDlcPackages.json`.

## Workspace

The repository sits inside a work folder (`<workspace>`) that also holds everything that must never be committed.
The Python tools refer to it as `..\` (e.g. `..\bin\venv`, `..\data\pc`), so the repository folder has to be a direct
sub folder of it.

| `<workspace>\...` | Content |
|---|---|
| `trudlcport\` | this repository (branch `windows`) |
| `bin\` | tools: Python venv (`bin\venv`), ffmpeg, Yura, Ghidra + JDK, Xenia Canary - `Get-Tools.ps1` |
| `data\` | junctions to the game, the Xbox files and the repository - see [Pipeline](#pipeline) |
| `input\xbox-dlc\` | your Xbox 360 DLC content (folder `534307EC\00000002\...`, see below) |
| `input\xbox-dlc-live\` | optional: raw DLC package files as copied from the console; `Install-TruDlc.ps1` verifies and extracts them into `input\xbox-dlc\` (see [Raw Xbox LIVE packages](#raw-xbox-live-packages)) |
| `input\xbox-game\` | your Xbox 360 game (`layer1/2.000/.001`, `default.xex`) + title update (`TitleUpdate.000`, `default.xexp`); only for the pipeline |
| `input\ModLoader-v1.2.zip` | [TombRaiderModding/ModLoader](https://github.com/TombRaiderModding/ModLoader/releases) v1.2 |
| `release\<build>\` | `install_dlc.py` + `trudlcport-kit-<build>.zip` from the original's [releases](https://github.com/andrearicci93/trudlcport/releases) |
| `staging\`, `backup\`, `logs\` | unpacked ModLoader, backups (original `tru.exe`/`binkw32.dll`, replaced mod files, registry exports), run logs |

Xbox 360 content folders (title id `534307EC`, content type `00000002`):

| Folder | Files | Content |
|---|---|---|
| `9CA70CF0EDA43654D158C2E37470D301DFA850E753` | `pack10.000`, `credits_DLC1.wmv` | DLC 1 *Beneath the Ashes* (required) |
| `600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153` | `pack11.000`, `credits_DLC2.wmv` | DLC 2 *Lara's Shadow* (optional; menu images and music only) |
| `E5AF...`, `9FDD...`, `AC00...` | `pack1.000`, `pack2.000`, `pack20.000` | costume packs (Wetsuit k / p, Classic a / h, Designer l / m) - pipeline step `Costumes` (converted and checked offline, not played yet), see [docs/COSTUMES.md](../../docs/COSTUMES.md) |

### Raw Xbox LIVE packages

On the console (hard drive or USB stick, copied with e.g. Horizon or Velocity) every DLC is **one file without
extension** in `Content\<profile id or 0000000000000000>\534307EC\00000002\`, named like the folders above
(42 characters: the content id = SHA-1 of the package header, plus 2 hex). Copy these files into
`<workspace>\input\xbox-dlc-live\` (or pass them with `-Package`) and run `Install-TruDlc.ps1` as usual - or only
`.\scripts\windows\Install-TruDlc.ps1 -PackageOnly -Verbose` to extract them. Per package
(`TruDlcPackage.psm1`, `Expand-TruDlcPackage`):

1. `tools\stfs_extract.py identify`: magic `LIVE`, title id `534307EC`, content type 2, header SHA-1 against the
   header bytes and the file name (a renamed copy is fine; a name that contradicts the header is refused), not
   truncated, file names and sizes against `TruDlcPackages.json`. Unknown or damaged packages are refused.
2. Folder `input\xbox-dlc\<name>\` already there: identical to the list (size + MD5) -> skipped; different -> error
   (never overwritten).
3. Extract into `input\xbox-dlc\<name>.tmp\` (every data block and the whole hash tree checked), size + MD5 of every
   file against the list, rename to `<name>\` - the same flat layout as a Xenia-extracted folder. The extraction
   manifest goes to `logs\`.

`-Check` only identifies and verifies the packages (nothing is extracted); `-WhatIf` shows what would happen.
`Test-TruDlcInput` (same module, read-only) compares the folders in `input\xbox-dlc` with the list.

`TruDlcPackages.json` holds names, roles, file sizes and hashes only (no game data). Regenerate it from extracted
folders (roles and display names are kept):
`..\bin\pyt -t 900 tools/stfs_extract.py catalog scripts/windows/TruDlcPackages.json ../input/xbox-dlc/<name> ... --base scripts/windows/TruDlcPackages.json`.
Tested on 13 prototype DLC packages (file name = header SHA-1 in all 13, every extracted file = size + MD5 of the
earlier extraction of 2026-11-02, damaged / truncated / renamed copies handled); not yet on a raw final package.

## Scripts

| Script | Purpose |
|---|---|
| `Install-TruDlc.ps1` | install a release kit + ModLoader into the game folder: `-Check` (dry run, writes nothing), install, `-Restore`; finds the Steam game folder itself (`-GamePath` to override), `-Build` (default `B138`); raw Xbox LIVE packages first (`-Package <file(s)>` or the files in `input\xbox-dlc-live\`; `-PackageOnly` stops after extracting, `-DlcPath`, `-PackageList`); `-WhatIf` changes nothing. Since 2026-11-05 an install writes the MD5 of every installed file to `backup\dlc_install_<time>\manifest.json`; `-Restore` refuses when `ModLoader.asi`, `binkw32.dll` or `tru.exe` no longer has its installed MD5 (changed `mods\` files are only reported - the folder is kept as `mods_disabled_<time>`); `-Force` restores anyway, saves the changed files first and logs the override |
| `Install-TruModFile.ps1` | replace one file in the game's `mods\` (`-Name`, `-Source`), keeping the old one as `backup\mods\<name>.<md5>`; `-Restore` puts it back |
| `Install-TruTree.ps1` | lay a whole converted tree over `mods\` (e.g. the DLC 2 test tree): `-Check` dry run; install saves every replaced file and a manifest (added files, replaced files, created folders) in `backup\tree_<time>\`; `-Restore` undoes exactly that, newest install first - installs stack, one `-Restore` per install (tested on copies of `mods\`: install + restore 275/275 files, two stacked installs + two restores 461/461, folder lists identical). `local\` and `padshock\` are excluded by default (the installed string tables carry the DLC menu text fix). Since 2026-11-05 the manifest also lists the installed MD5 of every file it wrote (`installed`, `manifest_version` 2); `-Restore` checks all backups and installed files before it changes anything and refuses when an installed file was changed since (by hand, a single-file install, or a later install not undone yet - restores in the wrong order); `-Force` restores anyway, first saving the changed files to `backup\tree_<time>\overwritten_<time>\` with `forced_restore.json`, and logs the override. Older manifests are restored unchecked (logged) |
| `Set-TruDisplay.ps1` | `-Windowed` (installs TRAWindowed's `d3d9.dll` in the game folder; in game F6 border, Shift+F6 centre) / `-Fullscreen` / `-Restore` (remove it again; a foreign `d3d9.dll` is never touched) and `-Language English\|French\|German\|Italian\|Spanish\|Dutch` (registry, exported to `backup\` first); graphics options (2026-11-08) `-DepthOfField On\|Off`, `-FullscreenEffects On\|Off`, `-AspectRatio Auto\|W:H`, `-StutterFix`, and `-Check` (dry run, writes nothing) |
| `Get-Tools.ps1` | download the portable tools into `<workspace>\bin`, SHA-256 checked before unpacking |
| `Build-TruAsi.ps1` | build the ASI plugins in `src\asi\` (`TruShadowPower`, `TruRockVein`, `TruDoppelganger`, `TruDlc2Player`, `TruLink`, `TruMenu`, `TruGuard`, `TruQoL`, ...) with the installed Visual Studio x86 toolchain -> `work\asi\` |
| `Set-TruDlc2Player.ps1` | `-Install` / `-Remove` `TruDlc2Player.asi` + `.ini` (DLC 2 player: the doppelganger as player object, type record, DoppelgangerInit) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Set-TruDoppelganger.ps1` | `-Install` / `-Remove` `TruDoppelganger.asi` + `.ini` (DLC 2 player: the title-update state-machine ids) next to `tru.exe`, same rules |
| `Set-TruGuard.ps1` | `-Install` / `-Remove` `TruGuard.asi` + `.ini` (exception diagnostics: fault sites, minidumps; `src\asi\TruGuard\README.md`) next to `tru.exe`, same rules |
| `Set-TruShadowPower.ps1` | `-Install` / `-Remove` `TruShadowPower.asi` + `.ini` next to `tru.exe` (loaded by the game's ASI loader `binkw32.dll`; foreign files are never touched) |
| `Set-TruMercLang.ps1` | `-Install` / `-Remove` `TruMercLang.asi` + `.ini` (fun option: the mercenaries' barks in another language, default off; `src\asi\TruMercLang\README.md`) next to `tru.exe`, same rules as `Set-TruShadowHud.ps1` |
| `Set-TruRockVein.ps1` | `-Install` / `-Remove` `TruRockVein.asi` + `.ini` (DLC 2 rock veins: markup conditions 607 / 608) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Set-TruLink.ps1` | `-Install` / `-Remove` `TruLink.asi` + `.ini` (test tool: live read / write channel on 127.0.0.1:9265, `src\asi\TruLink\README.md`) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Invoke-TruLink.ps1` | client for `TruLink.asi`: `-Command 'read32 cheat'`, `-Script file.txt` or `-Interactive`; prints the answers (`-PassThru` returns them) |
| `Set-TruMenu.ps1` | `-Install` / `-Remove` `TruMenu.asi` + `.ini` (in-game debug menu, L3 + R3, Dear ImGui; `src\asi\TruMenu\README.md`) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1`; also the regression lists, `TruMenu.media.txt` and (0.10) the radial menu file `TruMenu.radial.txt` (build folder, else `src\asi\TruMenu`; ours = first line `# TruMenu radial menu`). Build with `Build-TruAsi.ps1 -Name TruMenu` (compiles the ImGui sources from `src\asi\third_party\imgui` as well; copies `TruMenu.radial.txt` into the build folder) |
| `Set-TruQoL.ps1` | `-Install` / `-Remove` / `-Restore` / `-Check` `TruQoL.asi` + `.ini` (player comfort fixes for the base game: 60 fps cap at the game's own frame clock, FOV factor, camera shake scale, start-up fix for PCs with more than 31 CPU threads, optional intro skip; keys adjustable live from TruMenu page "Fixes"; `src\asi\TruQoL\README.md`) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Invoke-TruPipeline.ps1` | run the conversion pipeline one step at a time (`-Step`, `-FromTool` to resume, `-ToTool` to stop early and split a long step), with progress and a summary |
| `Test-TruUploadReady.ps1` | read-only check of our commits before an upload (paths, machine name, identity, e-mails, secrets, hardware, local patterns) |
| `Invoke-TruTestRun.ps1` | one regression run of the game from a profile `tests\profiles\<name>.json`: installs exactly that state, starts the game (plain or under cdb), preloads the TruMenu TO TEST rows, waits for the end, collects logs / markers / test states into `<workspace>\runs\<time>_<profile>\` with `summary.md` + `summary.json`; dumps written during the run are copied into `<run>\dumps\` (`-NoDumpCopy`); `-Compare` (see [Regression runs](#regression-runs)) |
| `Test-TruPreflight.ps1` | read-only check before a test evening (`-RunProfile`, `-Session`): game folder, open `backup\tree_*` installs, direct-start generalbank 41e, profile sources / ASI / INI state, Data rows on the DRMs the profile installs last (texture group counts, SoundPlex sequence repeat, script class clash, NavPower navmesh of the DLC 2 units via `tools/navgraph_raw_fix.py scan --pack pack11`; `-SkipDataChecks`), cdb, disk, RAM, save folder, LocalDumps / Fullscreen (information); status table + `<workspace>\logs\Test-TruPreflight_<time>.log`, exit 1 on a fail row |
| `Connect-TruDevChannel.ps1` | read-only client for the TCP server inside `tru.exe` on port 9264 - the FMOD Ex profiler (audio telemetry), not a developer channel |
| `Measure-TruProcessMemory.ps1` | read-only samples of the memory of running Python processes, to size parallel pipeline runs |

All `Set-Tru<Plugin>.ps1` scripts take `-SourceDir` (default `<repository>\work\asi`) for a build made with
`Build-TruAsi.ps1 -OutDir`, e.g. `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu05`.

## Regression runs

`Invoke-TruTestRun.ps1 -RunProfile <name>` (Windows PowerShell 5.1) does one game run from a **profile** in
`tests\profiles\` (paths in it relative to `<workspace>`; format in the script's help, example
`tests\profiles\dlc2_doppelganger.json`):

1. aborts while `tru.exe` runs (it never ends a process); undoes what its previous run installed
   (`<workspace>\runs\installed-state.json`: tree install, single mod files, INI backups - refused while a newer
   tree install of someone else sits on top); checks the profile's md5 / sha256 values (abort on a mismatch unless
   `-AllowMd5Mismatch`);
2. installs with `Install-TruTree.ps1` / `Install-TruModFile.ps1` / `Set-Tru<Plugin>.ps1 -Install -SourceDir`
   (our ASIs that the profile does not list are removed with `-Remove`), writes the profile's INI overrides and the
   `initial` state of INI toggles (each edited INI backed up into the run folder first), records the installed md5s;
3. starts the game: `cmd /c start "" /b /wait /affinity FFFF tru.exe`, or with `-Debugger -Session <file.cdb>`
   `cdb.exe -G -cf <file.cdb> -logo <run>\cdb.log tru.exe` started the same way (`-CdbPath`, default the x86
   debugger of the Windows 10 kit);
4. waits for TruLink, sends `menu test.clear` and the profile's rows (`test.step` / `test.add` / `test.toggle`) and
   saves `menu test.export`; then waits for the end (`-TimeoutMinutes`, default 90 - on a timeout it only stops
   waiting);
5. collects into `<workspace>\runs\<time>_<profile>\`: the part of every `Tru*.log` written during the run, `cdb.log`,
   `TruMenu.tests.txt`, our INIs before / after, the markers of the cdb log (`D3DFAIL` with the hresult, `AV2NDCHANCE`,
   `FASTFAIL`, `STACKOVERFLOW`, `EXITPROCESS`, `TERMINATEPROCESS`, `MESSAGEBOX_A/W`), dumps newer than the start
   (`%LOCALAPPDATA%\CrashDumps`, the game folder, paths named in the session file - names and sizes only), and
   writes `summary.md` / `summary.json` (status per row: ok / fail / open, the first crash marker).

```powershell
.\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile dlc2_doppelganger -Debugger -Session ..\session_exit.cdb -Verbose
.\scripts\windows\Invoke-TruTestRun.ps1 -Compare 20261031_221500_dlc2_doppelganger          # against the newest other run
.\scripts\windows\Invoke-TruTestRun.ps1 -Undo                                               # only undo the last install
```

`-Compare <run>` lists what differs between two runs (installed md5s, marker counts, the first crash marker, the exit
code, the state of every TO TEST row); after a run it compares the new run with `<run>` and saves `compare.txt`.
`-InstallOnly` installs and records without starting the game.

## Install (play DLC 1)

1. Put the kit into `<workspace>\release\B138\` and ModLoader into `<workspace>\input\`, your Xbox DLC files into
   `<workspace>\input\xbox-dlc\` - extracted folders, or the raw package files from the console into
   `<workspace>\input\xbox-dlc-live\` (see [Raw Xbox LIVE packages](#raw-xbox-live-packages)). Python 3.9+ with
   `pip install bsdiff4`.
2. Close the game. Dry run: `.\scripts\windows\Install-TruDlc.ps1 -Check -Verbose` - it must end with
   *All inputs OK* (with raw packages that are not extracted yet it only verifies the packages; extract them first
   with `-PackageOnly`, then repeat the dry run).
3. Install: `.\scripts\windows\Install-TruDlc.ps1 -Verbose`. The original `binkw32.dll` and `tru.exe` are backed up
   first; `-Restore` returns to the original game.
4. Start a new DLC game from the main menu (*Downloadable content*), lock the game to 60 fps.

The installer itself and its options are the original's: [docs/INSTALL.md](../../docs/INSTALL.md),
[docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md).

## Game notes (Steam version, `tru.exe` 1.1)

- **Crash at start-up on CPUs with more than 31 threads.** The game's CPU detection shifts an affinity mask core by
  core; with 32 bits it overflows, the loop never ends and writes past the stack (`0xc0000409` at `tru+0xa235d`,
  seen on an i9-9980XE with 36 threads). Known bug of the original game, not of the DLC port. Work-around: Steam ->
  Properties -> Launch options `cmd /c start "" /affinity FFFF %command%` (16 threads).
- **Language:** registry value `Language` under `HKCU\Software\Crystal Dynamics\Tomb Raider: Underworld`:
  0 English, 1 French, 2 German, 3 Italian, 4 Spanish, 5 Dutch (the order of the `locals.bin_001..032` language
  bits; all six checked in game) - `Set-TruDisplay.ps1 -Language`.
- **Subtitle language** (apart from the speech): registry value `SubtitleLanguage` in the same key; -1 = as the game
  language (the default). The game keeps -1, 0 .. 4, 7 and 9 .. 12 and falls back to -1 for 5, 6 and 8, so Dutch is not
  offered - `Set-TruDisplay.ps1 -SubtitleLanguage Auto|English|French|German|Italian|Spanish` (e.g. German speech with
  English subtitles; every cinematic stream carries all subtitle languages; not yet seen in game).
- **Windowed mode:** the game sets `Fullscreen` back to 1 at start-up; `LockWindowSize` and `LockedWindow*` stay but
  are not used. Still open.

## Pipeline

`Invoke-TruPipeline.ps1` runs upstream's Python tools from the repository root with
`<workspace>\bin\venv\Scripts\python.exe -u -I -X utf8` (packages from `requirements.txt`). The tools read the game
and the Xbox files through junctions in `<workspace>\data\`:

| `<workspace>\data\...` | Junction to |
|---|---|
| `pc` | the Steam game folder (read only) |
| `trudlcport` | the repository |
| `Xenia-SteveRepack\Content\534307EC\00000002` | `<workspace>\input\xbox-dlc` |
| `TombRaiderUnderworld_Patched` | `<workspace>\input\xbox-game` |

**Never delete `data\` or `bin\` recursively** (Explorer, `Remove-Item -Recurse`): through the junctions that can
delete the game files or the repository. Remove a junction on its own: `cmd /c rmdir <workspace>\data\pc`.

Steps in order: `Index`, `Cache`, `Ids`, `Learn`, `Tables`, `Prep`, `Convert`, `Names`, `Media`, `Audio`, and
optionally `Assemble` (upstream's full stage-1 route with the rebuilt render tables; better shaders and materials), then
`Dlc2` (DLC 2 through the same route, `--pack pack11`; see [docs/DLC2.md](../../docs/DLC2.md)), `Fixes` (stage 2b for
DLC 1 and DLC 2; `statechart`: state charts, record tables and id lists of the new DLC objects re-converted from the
base game's Xbox/PC pairs, the DLC 2 player chart first by its typed steps - this one needs the title-update memory
image `work\xenia_dump\tu_image_82000000.bin` or `TRUDLC_TU_IMAGE`, without it the player chart gets the base-pair
part only; then the proven structure fixes of `tools/dlc_struct_fixes.py`, one step each (2026-11-01/02): `twins`
(base-twin byte-order truth for every same-size section of the DLC 2 player files, `tools/dlc_structure_audit.py`,
~20 min), `childids` (object child id list by name), `translist` / `actlist` (state records and activity entries of
the DLC 2 player chart), `condlist` (the condition records every transition of that chart lists), `eventlist` (object
event lists), `reclist` (model record list 36 -> 40 bytes), `fadeslots`
(own fade pixel-shader libraries 2494.. of the TU-drawn DLC 2 player objects), `animfx` (anim event lists), `markup`
(object markup records), `vmliteral` (VM literals); then the converter fault families that crash dumps of tests
50d-50j uncovered (2026-11-03, `tools/converter_faults_fix.py`, each rule proven on the base pair `lara.drm`):
`objevent` (object event list words), `idword` (kind-1 sub-0x32 event payload = one u32 section id), `animlist` (anim
event list words), `fxnode` (effect node headers and type-1 section ids), `statevm` (state-program VM code words),
`chartid` (state-chart id values of types 3 / 5); the step `Fixes` first runs `converter_faults_fix.py proof` (every
rule on the base pair) and after each tree `converter_faults_fix.py check` (exit code 1 on any wrong or unexpected word,
report `<tree>\converter_faults_check.json`); `-FixesOut work\rebuild\<name>` writes `<name>\dlc1\mods` and
`<name>\dlc2\mods` instead of the usual `asm_stage2b` / `dlc2_asm_stage2b` (check runs); `uirecord`: the UI text element records of the new DLC scripts by Crystal's PC rules; last fix
`achievement`: the 11 script calls into the title update's achievement natives f16-f20, which the PC exe lacks, are
dropped - on the Xbox they only queue an Xbox Live achievement), `Costumes` (2026-11-03: the three costume packs
through the DLC 2 route, one chain per pack - `verify_ids.py extend` adds their ids to the id table first (existing
entries never change), then media, assemble, audio, `tree_check`, stage 2b, `converter_faults_fix check` ->
`work\rebuild\costumes\<pack>\...` or `-FixesOut DIR` -> `DIR\<pack>\...`; only the two `dlc_costume_<x>.drm` of each
pack are new for the game, see [docs/COSTUMES.md](../../docs/COSTUMES.md)) and
`Repair` (the tested repair tree for an installed B138: shader constant fix, grapple ring shaders, UI paths, texts and
text element records of DLC 1, state charts of DLC 1, the DLC 1 structure fixes (step `struct`: costume anim event
lists, pillar markup), the DLC 1 achievement call, cinematics in all five languages,
our `generalbank.drm` ->
`work\rebuild\b138_fixes\mods`, install it with `Install-TruTree.ps1 -Source .\work\rebuild\b138_fixes\mods`).
`Generalbank` rebuilds only our `generalbank.drm` (`tools/generalbank_build.py`, 21 steps: mission screen style, the
title update's loading screen with the DLC titles and its hint box, ~8 min, two steps need ~16 GB RAM) and checks it
against the MD5 of the file played in game -> `work\rebuild\generalbank_build\mods`; `Repair` runs it too. What each
step runs, how long it takes and how the result compares with B138:
[docs/WINDOWS_REBUILD.md](../../docs/WINDOWS_REBUILD.md); upstream's own scripts and layers:
[docs/WS_MAP.md](../../docs/WS_MAP.md).

## Tools (`Get-Tools.ps1`)

| Tool | Version | Source | Used for |
|---|---|---|---|
| ffmpeg (gyan.dev essentials) | 9.0.2 | [GyanD/codexffmpeg](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2) | XMA decoding in the audio steps |
| Yura | 1.7.2 | [TheIndra55/Yura](https://github.com/TheIndra55/Yura/releases/tag/v1.7.2) | file name lists (`ref\yura-release` in the repository, junction) |
| Ghidra | 12.2 | [NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build) | reverse engineering of `tru.exe` |
| Temurin JDK | 25.0.5+8 | [adoptium/temurin25-binaries](https://github.com/adoptium/temurin25-binaries/releases) | Java for Ghidra 12.2 (needs Java 25) |
| Xenia Canary | 02d2cb5 | [xenia-canary/xenia-canary-releases](https://github.com/xenia-canary/xenia-canary-releases/releases/tag/02d2cb5) | the Xbox 360 version as a reference |
| TRAWindowed (`d3d9.dll`, MIT) | 1.9.0 | [chreden/trawindowed](https://github.com/chreden/trawindowed/releases/tag/v1.9.0) | windowed mode for the game (`Set-TruDisplay.ps1 -Windowed`); the Steam game has none of its own |

The SHA-256 of every download is in `Get-Tools.ps1`.

### Xenia (reference only)

`<workspace>\bin\xenia-canary\` with `portable.txt`; content under `content\0000000000000000\534307EC\`
(`00000002` = junction to `input\xbox-dlc`, `000B0000\<title update>\` = copy of `default.xexp` + `TitleUpdate.000`).
Start: `xenia_canary.exe <workspace>\input\xbox-game\default.xex`. Settings used in `xenia-canary.config.toml`:
`keyboard_mode = 1` (A = Enter/Space, B = Backspace, d-pad = arrow keys, right stick = numpad 8/4/2/6),
`license_mask = -1` (DLC licensed), `render_target_path_d3d12 = "rov"` (against the graphics errors in Underworld,
xenia-canary game-compatibility #418).
