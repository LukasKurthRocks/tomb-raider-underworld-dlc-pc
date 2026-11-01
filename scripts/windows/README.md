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
| `input\xbox-game\` | your Xbox 360 game (`layer1/2.000/.001`, `default.xex`) + title update (`TitleUpdate.000`, `default.xexp`); only for the pipeline |
| `input\ModLoader-v1.2.zip` | [TombRaiderModding/ModLoader](https://github.com/TombRaiderModding/ModLoader/releases) v1.2 |
| `release\<build>\` | `install_dlc.py` + `trudlcport-kit-<build>.zip` from the original's [releases](https://github.com/andrearicci93/trudlcport/releases) |
| `staging\`, `backup\`, `logs\` | unpacked ModLoader, backups (original `tru.exe`/`binkw32.dll`, replaced mod files, registry exports), run logs |

Xbox 360 content folders (title id `534307EC`, content type `00000002`):

| Folder | Files | Content |
|---|---|---|
| `9CA70CF0EDA43654D158C2E37470D301DFA850E753` | `pack10.000`, `credits_DLC1.wmv` | DLC 1 *Beneath the Ashes* (required) |
| `600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153` | `pack11.000`, `credits_DLC2.wmv` | DLC 2 *Lara's Shadow* (optional; menu images and music only) |
| `E5AF...`, `9FDD...`, `AC00...` | `pack1.000`, `pack2.000`, `pack20.000` | costume packs - not supported yet, see [docs/COSTUMES.md](../../docs/COSTUMES.md) |

## Scripts

| Script | Purpose |
|---|---|
| `Install-TruDlc.ps1` | install a release kit + ModLoader into the game folder: `-Check` (dry run, writes nothing), install, `-Restore`; finds the Steam game folder itself (`-GamePath` to override), `-Build` (default `B138`) |
| `Install-TruModFile.ps1` | replace one file in the game's `mods\` (`-Name`, `-Source`), keeping the old one as `backup\mods\<name>.<md5>`; `-Restore` puts it back |
| `Install-TruTree.ps1` | lay a whole converted tree over `mods\` (e.g. the DLC 2 test tree): `-Check` dry run; install saves every replaced file and a manifest (added files, replaced files, created folders) in `backup\tree_<time>\`; `-Restore` undoes exactly that, newest install first - installs stack, one `-Restore` per install (tested on copies of `mods\`: install + restore 275/275 files, two stacked installs + two restores 461/461, folder lists identical). `local\` and `padshock\` are excluded by default (the installed string tables carry the DLC menu text fix) |
| `Set-TruDisplay.ps1` | `-Windowed` (installs TRAWindowed's `d3d9.dll` in the game folder; in game F6 border, Shift+F6 centre) / `-Fullscreen` / `-Restore` (remove it again; a foreign `d3d9.dll` is never touched) and `-Language English\|French\|German\|Italian\|Spanish\|Dutch` (registry, exported to `backup\` first) |
| `Get-Tools.ps1` | download the portable tools into `<workspace>\bin`, SHA-256 checked before unpacking |
| `Build-TruAsi.ps1` | build the ASI plugins in `src\asi\` (today `TruShadowPower`, DLC 2 shadow-power slow motion) with the installed Visual Studio x86 toolchain -> `work\asi\` |
| `Set-TruShadowPower.ps1` | `-Install` / `-Remove` `TruShadowPower.asi` + `.ini` next to `tru.exe` (loaded by the game's ASI loader `binkw32.dll`; foreign files are never touched) |
| `Set-TruRockVein.ps1` | `-Install` / `-Remove` `TruRockVein.asi` + `.ini` (DLC 2 rock veins: markup conditions 607 / 608) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Set-TruLink.ps1` | `-Install` / `-Remove` `TruLink.asi` + `.ini` (test tool: live read / write channel on 127.0.0.1:9265, `src\asi\TruLink\README.md`) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1` |
| `Invoke-TruLink.ps1` | client for `TruLink.asi`: `-Command 'read32 cheat'`, `-Script file.txt` or `-Interactive`; prints the answers (`-PassThru` returns them) |
| `Set-TruMenu.ps1` | `-Install` / `-Remove` `TruMenu.asi` + `.ini` (in-game debug menu, L3 + R3, Dear ImGui; `src\asi\TruMenu\README.md`) next to `tru.exe`, same rules as `Set-TruShadowPower.ps1`. Build with `Build-TruAsi.ps1 -Name TruMenu` (compiles the ImGui sources from `src\asi\third_party\imgui` as well) |
| `Invoke-TruPipeline.ps1` | run the conversion pipeline one step at a time (`-Step`, `-FromTool` to resume), with progress and a summary |
| `Test-TruUploadReady.ps1` | read-only check of our commits before an upload (paths, machine name, identity, e-mails, secrets, hardware, local patterns) |
| `Invoke-TruTestRun.ps1` | one regression run of the game from a profile `tests\profiles\<name>.json`: installs exactly that state, starts the game (plain or under cdb), preloads the TruMenu TO TEST rows, waits for the end, collects logs / markers / test states into `<workspace>\runs\<time>_<profile>\` with `summary.md` + `summary.json`; `-Compare` (see [Regression runs](#regression-runs)) |

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
   `<workspace>\input\xbox-dlc\`. Python 3.9+ with `pip install bsdiff4`.
2. Close the game. Dry run: `.\scripts\windows\Install-TruDlc.ps1 -Check -Verbose` - it must end with
   *All inputs OK*.
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
part only; `uirecord`: the UI text element records of the new DLC scripts by Crystal's PC rules; last fix
`achievement`: the 11 script calls into the title update's achievement natives f16-f20, which the PC exe lacks, are
dropped - on the Xbox they only queue an Xbox Live achievement) and
`Repair` (the tested repair tree for an installed B138: shader constant fix, grapple ring shaders, UI paths, texts and
text element records of DLC 1, state charts of DLC 1, the DLC 1 achievement call, cinematics in all five languages,
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
