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
| `Invoke-TruPipeline.ps1` | run the conversion pipeline one step at a time (`-Step`, `-FromTool` to resume), with progress and a summary |
| `Test-TruUploadReady.ps1` | read-only check of our commits before an upload (paths, machine name, identity, e-mails, secrets, hardware, local patterns) |

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
DLC 1 and DLC 2) and `Repair` (the tested repair tree for an installed B138: shader constant fix,
grapple ring shaders, UI paths and texts of DLC 1, cinematics in all five languages -> `work\rebuild\b138_fixes\mods`, install it with
`Install-TruTree.ps1 -Source .\work\rebuild\b138_fixes\mods`). What each
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
