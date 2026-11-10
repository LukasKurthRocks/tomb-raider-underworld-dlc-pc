<#
.SYNOPSIS
    Installs the trudlcport (Xbox 360 DLC -> PC) build and ModLoader into the Steam copy of Tomb Raider: Underworld.

.DESCRIPTION
    -Check    Dry run of install_dlc.py: verifies game and DLC inputs, writes nothing to the game folder.
    (default) Copies ModLoader.asi + binkw32.dll into the game folder, then runs install_dlc.py.
              install_dlc.py itself keeps tru.exe as tru.exe.steam_original and an old mods\ as mods_backup_<time>.
    -Restore  Puts back the original binkw32.dll and tru.exe from <workspace>\backup and renames mods\ to mods_disabled_<time>.

    Install manifest (since 2026-11-05, E12): after a successful install the MD5 of every installed file
    (ModLoader.asi, binkw32.dll, tru.exe and every file below mods\) is written to
    <workspace>\backup\dlc_install_<time>\manifest.json. -Restore first compares the game files with the newest
    manifest that is not undone yet: if ModLoader.asi, binkw32.dll or tru.exe (the files -Restore overwrites or
    renames) no longer have their installed MD5, it refuses and changes nothing. Changed mods\ files are only
    reported (WARN): tree installs change them on purpose, and -Restore keeps the whole folder as
    mods_disabled_<time>. An install made before 2026-11-05 has no manifest: then the installed MD5s are taken from
    the kit (release\<Build>\kit\manifest.json, tru.exe) and the ModLoader copy (staging\ModLoader-v1.2).
    -Force restores anyway: the changed files are first saved to <manifest folder>\overwritten_<time>\ (or
    backup\dlc_restore_forced_<time>\ without a manifest) with forced_restore.json, and the override is logged.

    Raw Xbox LIVE packages: the DLC files copied from the console (Content\<profile>\534307EC\00000002\<42-character
    name>, one file per package) can be given with -Package or put into <workspace>\input\xbox-dlc-live\. Before
    anything else they are identified (header SHA-1 = content id = file name, title id, content type), checked
    against scripts\windows\TruDlcPackages.json and extracted into <workspace>\input\xbox-dlc\<name>\ (every block
    of the package's hash tree checked, then size + MD5 of every file against the list); unknown or damaged packages
    are refused, an existing different folder is never overwritten (TruDlcPackage.psm1, Expand-TruDlcPackage).
    With -Check the packages are only identified and verified (nothing is extracted). -PackageOnly stops after this
    step and does not look at the game folder.

    -WhatIf shows what would be extracted / installed / restored and changes nothing.

    Every run writes a log to <workspace>\logs\Install-TruDlc_<time>.log (environment, hashes, full python output).
    -Verbose shows each step, -Debug adds paths, hashes and command lines, -Trace adds a PowerShell line trace.

    Original files are backed up in <workspace>\backup (binkw32.dll.steam_original, tru.exe.steam_original).
    The script never stops a running game; it aborts instead.

.EXAMPLE
    .\Install-TruDlc.ps1 -Check -Verbose
.EXAMPLE
    .\Install-TruDlc.ps1 -Restore -Debug
.EXAMPLE
    .\Install-TruDlc.ps1 -Package E:\Content\0000000000000000\534307EC\00000002\9CA70CF0EDA43654D158C2E37470D301DFA850E753 -PackageOnly -Verbose
.EXAMPLE
    .\Install-TruDlc.ps1 -Check -Verbose      # also checks the raw packages in <workspace>\input\xbox-dlc-live, if any
.PARAMETER Package
    Raw Xbox LIVE package file(s). Without it, the files in <workspace>\input\xbox-dlc-live\ are used (if any).
.PARAMETER PackageOnly
    Only verify / extract the raw packages; the game folder is not looked at.
.PARAMETER DlcPath
    Folder of the extracted packages (default <workspace>\input\xbox-dlc); also passed to install_dlc.py --dlc.
.PARAMETER PackageList
    Known-packages list (default scripts\windows\TruDlcPackages.json).
.PARAMETER Force
    With -Restore: restore even when installed files were changed since the install (they are saved first; logged).
.PARAMETER Python
    Python executable for install_dlc.py and the package tool (default: python from PATH). Install-TruAll.ps1 passes
    its own venv (<workspace>\bin\venv-install).
.PARAMETER Credits
    Install: also build the credits movies (install_dlc.py --credits, with -Rad / -Ffmpeg when given). The dry run
    before the install stays without --credits.
.PARAMETER Rad
    radvideo64.exe for --credits (passed as --rad).
.PARAMETER Ffmpeg
    ffmpeg.exe for --credits (passed as --ffmpeg).
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Check,
    [switch]$Restore,
    [switch]$Force,
    [switch]$Trace,
    [string]$GamePath,
    [string]$Build = 'B138',
    [string[]]$Package,
    [switch]$PackageOnly,
    [string]$DlcPath,
    [string]$PackageList,
    [string]$Python = 'python',
    [switch]$Credits,
    [string]$Rad,
    [string]$Ffmpeg
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Find-TruGamePath, Get-Md5, Get-TruWorkspacePath
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
# raw Xbox LIVE packages: Expand-TruDlcPackage (identify, verify, extract)
Import-Module (Join-Path $PSScriptRoot 'TruDlcPackage.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$dlcPath   = if ($DlcPath) { [System.IO.Path]::GetFullPath($DlcPath) } else { Join-Path $root 'input\xbox-dlc' }
$liveDir   = Join-Path $root 'input\xbox-dlc-live'
$release   = Join-Path $root "release\$Build"
$kitPath   = Join-Path $release 'kit'
$installer = Join-Path $release 'install_dlc.py'
$loaderDir = Join-Path $root 'staging\ModLoader-v1.2'
$backupDir = Join-Path $root 'backup'
$logDir    = $paths.Logs

$md5BinkOriginal = '2f912c88c18c4aa65b2153339482f320'
$md5ExeOriginal  = 'b36da327a320eab8b5c8464b27685840'

$mode = if ($Restore) { 'Restore' } elseif ($PackageOnly -and $Check) { 'PackageCheck' } elseif ($PackageOnly) { 'Package' } elseif ($Check) { 'Check' } else { 'Install' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path $logDir -WhatIf:$false | Out-Null
$logFile = Join-Path $logDir ('Install-TruDlc_{0}_{1}.log' -f $stamp, $mode)
Set-TruLogFile -Path $logFile

function Get-InstallRecordFolders {
    # open install manifests of this script (backup\dlc_install_<time>, not *.restored), oldest first
    @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'dlc_install_*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike '*.restored' } | Sort-Object Name)
}

function Write-InstallManifest {
    # E12 (2026-11-05): MD5 of every installed file -> backup\dlc_install_<time>\manifest.json
    $folder = Join-Path $backupDir ('dlc_install_' + $stamp)
    while (Test-Path -LiteralPath $folder) {
        Start-Sleep -Milliseconds 250
        $folder = Join-Path $backupDir ('dlc_install_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    }
    $rel = @('ModLoader.asi', 'binkw32.dll', 'tru.exe')
    $mods = Join-Path $GamePath 'mods'
    if (Test-Path -LiteralPath $mods) {
        $rel += @(Get-ChildItem -LiteralPath $mods -Recurse -File | ForEach-Object { $_.FullName.Substring($GamePath.TrimEnd('\').Length).TrimStart('\') })
    }
    $installed = @(Get-TruInstalledRecord -Root $GamePath -Path $rel)
    New-Item -ItemType Directory -Force -Path $folder -WhatIf:$false | Out-Null
    [pscustomobject]@{ time = (Split-Path -Leaf $folder).Substring(12); script = 'Install-TruDlc.ps1'; build = $Build;
                       game = $GamePath; kit = $kitPath; manifest_version = 2; installed = $installed } |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $folder 'manifest.json') -Encoding UTF8 -WhatIf:$false
    Write-Log ('Install manifest: {0} files with their installed MD5 -> {1}' -f $installed.Count, (Join-Path $folder 'manifest.json'))
}

function Assert-RestoreAllowed {
    # E12 (2026-11-05): refuses -Restore when a file it overwrites / renames was changed since the install
    $open = @(Get-InstallRecordFolders)
    if ($open.Count) {
        $record = $open[-1].FullName
        $manifest = Get-Content -LiteralPath (Join-Path $record 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $installed = @(@($manifest.installed) | Where-Object { $_ })
        $what = Split-Path -Leaf $record
        $saveDir = Join-Path $record ('overwritten_' + $stamp)
        Write-Log "Install manifest: $record ($($installed.Count) installed files)" -Level VERBOSE
    }
    else {
        # install made before 2026-11-05: the installed MD5s follow from the kit and the ModLoader copy
        $kitManifest = Join-Path $kitPath 'manifest.json'
        $what = "the $Build install (no install manifest; MD5s from the kit and the ModLoader copy)"
        $saveDir = Join-Path $backupDir ('dlc_restore_forced_' + $stamp)
        $sources = @((Join-Path $loaderDir 'ModLoader.asi'), (Join-Path $loaderDir 'binkw32.dll'), $kitManifest)
        $absent = @($sources | Where-Object { !(Test-Path -LiteralPath $_ -PathType Leaf) })
        if ($absent.Count) {
            Write-Log "No install manifest and the expected MD5s cannot be derived (missing: $($absent -join ', '))." -Level WARN
            if (!$Force) { throw 'Restore refused: the installed files cannot be checked (no install manifest, kit or ModLoader copy missing) - nothing changed. Pass -Force to restore anyway.' }
            Write-Log "FORCED restore of ${what}: installed files not checked." -Level WARN
            return
        }
        $exe = @((Get-Content -LiteralPath $kitManifest -Raw -Encoding UTF8 | ConvertFrom-Json).extra | Where-Object { $_.rel -eq 'tru.exe' })
        $installed = @(
            [pscustomobject]@{ path = 'ModLoader.asi'; md5 = (Get-Md5 (Join-Path $loaderDir 'ModLoader.asi')) },
            [pscustomobject]@{ path = 'binkw32.dll'; md5 = (Get-Md5 (Join-Path $loaderDir 'binkw32.dll')) }
        )
        if ($exe.Count) { $installed += [pscustomobject]@{ path = 'tru.exe'; md5 = [string]$exe[0].md5 } }
        Write-Log "No install manifest (install made before 2026-11-05): checking $($installed.Count) files against the kit / ModLoader MD5s." -Level VERBOSE
    }
    $rootFiles = @($installed | Where-Object { ([string]$_.path) -notlike 'mods\*' })
    $modsFiles = @($installed | Where-Object { ([string]$_.path) -like 'mods\*' })
    $devMods = @(Get-TruInstallDeviation -Root $GamePath -Installed $modsFiles)
    if ($modsFiles.Count) {
        Write-Log ('mods\ files: {0} of {1} unchanged since the install, {2} changed.' -f ($modsFiles.Count - $devMods.Count), $modsFiles.Count, $devMods.Count)
    }
    if ($devMods.Count) {
        Write-Log ('{0} mods\ file(s) changed since the install (tree / single-file installs) - not a reason to refuse: -Restore keeps mods\ as mods_disabled_<time>, nothing in it is overwritten.' -f $devMods.Count) -Level WARN
        foreach ($d in $devMods) { Write-Log ('  mods file changed: {0} - installed {1}, now {2}' -f $d.Path, $d.Recorded, $d.Now) -Level VERBOSE }
    }
    $devRoot = @(Get-TruInstallDeviation -Root $GamePath -Installed $rootFiles)
    Write-Log ('Installed files that -Restore overwrites / renames: {0} of {1} unchanged, {2} changed.' -f ($rootFiles.Count - $devRoot.Count), $rootFiles.Count, $devRoot.Count)
    Assert-TruRestoreAllowed -Deviation $devRoot -Root $GamePath -What $what -SaveDir $saveDir -Force:$Force
}

function Write-FileState {
    param([string]$Label)
    Write-Log "File state ($Label):" -Level VERBOSE
    foreach ($name in 'tru.exe', 'tru.exe.steam_original', 'binkw32.dll', 'ModLoader.asi', 'movies\credits_DLC1.bik') {
        $path = Join-Path $GamePath $name
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path
            Write-Log ('  {0,-26} {1,10}  {2}' -f $name, $item.Length, (Get-Md5 $path)) -Level DEBUG
        } else {
            Write-Log ('  {0,-26} (missing)' -f $name) -Level DEBUG
        }
    }
    $mods = Join-Path $GamePath 'mods'
    $count = if (Test-Path -LiteralPath $mods) { @(Get-ChildItem -LiteralPath $mods -Recurse -File).Count } else { 0 }
    Write-Log "  mods\ files: $count" -Level DEBUG
}

function Assert-GameClosed {
    $proc = Get-Process -Name 'tru' -ErrorAction SilentlyContinue
    if ($proc) {
        throw "Tomb Raider: Underworld (tru.exe, PID $($proc.Id -join ', ')) is running. Please close the game first."
    }
    Write-Log 'Game is not running.' -Level VERBOSE
}

function Invoke-Installer {
    param([string[]]$ExtraArgs)
    $pyArgs = @($installer, '--game', $GamePath, '--dlc', $dlcPath, '--kit', $kitPath) + $ExtraArgs
    Write-Log ($Python + ' ' + (($pyArgs | ForEach-Object { '"{0}"' -f $_ }) -join ' ')) -Level DEBUG
    # Native stderr must not become a terminating error under ErrorActionPreference Stop (PS 5.1).
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Python @pyArgs 2>&1 | ForEach-Object {
            $text = if ($_ -is [System.Management.Automation.ErrorRecord]) { 'stderr: ' + $_.Exception.Message } else { [string]$_ }
            Write-Log $text
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    Write-Log "install_dlc.py exit code: $code" -Level $(if ($code -eq 0) { 'INFO' } else { 'ERROR' })
    return $code
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Install-TruDlc mode=$mode build=$Build force=$([bool]$Force) log=$logFile" -Level VERBOSE
    Write-Log "PowerShell $($PSVersionTable.PSVersion) on $([Environment]::OSVersion.VersionString)" -Level DEBUG

    # Raw Xbox LIVE packages (-Package, or files in input\xbox-dlc-live): identify, verify, extract into $dlcPath.
    $pendingRoles = @()
    if (!$Restore) {
        $packageArgs = @{ Destination = $dlcPath; CheckOnly = [bool]$Check; WhatIf = [bool]$WhatIfPreference }
        if ($PackageList) { $packageArgs.PackageList = $PackageList }
        if ($PSBoundParameters.ContainsKey('Python')) { $packageArgs.Python = $Python }
        $hasPackages = $false
        if ($Package) {
            $packageArgs.Path = $Package
            $hasPackages = $true
        } elseif ((Test-Path -LiteralPath $liveDir -PathType Container) -and @(Get-ChildItem -LiteralPath $liveDir -File).Count) {
            $packageArgs.Source = $liveDir
            $hasPackages = $true
            Write-Log "Raw package files found in $liveDir" -Level VERBOSE
        }
        if ($hasPackages) {
            $packageResults = @(Expand-TruDlcPackage @packageArgs)
            foreach ($result in $packageResults) {
                Write-Log ('package {0} ({1}): {2} - {3}' -f $result.Name, $result.Role, $result.Status, $result.Message)
            }
            $pendingRoles = @($packageResults | Where-Object { !$_.TargetPresent } | ForEach-Object { $_.Role })
        } elseif ($PackageOnly) {
            throw "No raw package files: pass -Package or put them into $liveDir."
        }
        if ($PackageOnly) {
            Write-Log 'PackageOnly: done; the game folder was not looked at.' -Level VERBOSE
            return
        }
    }

    if (!$GamePath) {
        $GamePath = Find-TruGamePath
        if (!$GamePath) { throw 'Game folder not found in the Steam libraries; pass -GamePath.' }
        Write-Log "Game folder found via Steam: $GamePath" -Level VERBOSE
    }
    Write-Log "Game: $GamePath | DLC: $dlcPath | Kit: $kitPath" -Level DEBUG

    if (!(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) {
        throw "No tru.exe in game folder: $GamePath"
    }

    if ($Restore) {
        if (!$PSCmdlet.ShouldProcess($GamePath, 'Restore the original binkw32.dll and tru.exe, disable mods\ and ModLoader.asi')) { return }
        Assert-GameClosed
        Write-FileState 'before restore'
        # E12: nothing is changed when a file -Restore overwrites / renames was changed since the install (unless -Force)
        Assert-RestoreAllowed
        Copy-Item -LiteralPath (Join-Path $backupDir 'binkw32.dll.steam_original') -Destination (Join-Path $GamePath 'binkw32.dll') -Force
        Copy-Item -LiteralPath (Join-Path $backupDir 'tru.exe.steam_original') -Destination (Join-Path $GamePath 'tru.exe') -Force
        Write-Log 'Copied original binkw32.dll and tru.exe from backup.' -Level VERBOSE
        $mods = Join-Path $GamePath 'mods'
        if (Test-Path -LiteralPath $mods) {
            $newName = 'mods_disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
            Rename-Item -LiteralPath $mods -NewName $newName
            Write-Log "mods\ renamed to $newName"
        }
        $asi = Join-Path $GamePath 'ModLoader.asi'
        if (Test-Path -LiteralPath $asi) {
            Rename-Item -LiteralPath $asi -NewName 'ModLoader.asi.disabled' -Force
            Write-Log 'ModLoader.asi renamed to ModLoader.asi.disabled'
        }
        if ((Get-Md5 (Join-Path $GamePath 'tru.exe')) -ne $md5ExeOriginal) { throw 'tru.exe after restore does not match the Steam original.' }
        if ((Get-Md5 (Join-Path $GamePath 'binkw32.dll')) -ne $md5BinkOriginal) { throw 'binkw32.dll after restore does not match the Steam original.' }
        Write-FileState 'after restore'
        Write-Log 'Restored original binkw32.dll and tru.exe (MD5 verified).'
        # the restore undoes every recorded install (all of them end in the Steam originals)
        foreach ($rec in @(Get-InstallRecordFolders)) {
            Rename-Item -LiteralPath $rec.FullName -NewName ($rec.Name + '.restored')
            Write-Log "Install manifest marked as undone: $($rec.FullName).restored" -Level VERBOSE
        }
        return
    }

    $pyVersion = (& $Python --version 2>&1) -join ' '
    Write-Log "Python: $pyVersion" -Level DEBUG

    if ($Check) {
        Write-FileState 'current'
        if ($pendingRoles -contains 'dlc1') {
            Write-Log 'The DLC 1 package is verified but not extracted yet (-Check writes nothing): install_dlc.py --check skipped. Run without -Check to extract and install.' -Level WARN
            return
        }
        $code = Invoke-Installer @('--check')
        if ($code -ne 0) { throw "Dry run failed (exit code $code)." }
        return
    }

    if (!$PSCmdlet.ShouldProcess($GamePath, 'Install ModLoader and the DLC kit (install_dlc.py)')) { return }
    Assert-GameClosed
    Write-FileState 'before install'

    # First install on this PC (2026-11-10, Install-TruAll.ps1): no backups yet -> take them from the game folder,
    # but only files with the Steam MD5 (tru.exe or the tru.exe.steam_original an earlier install kept).
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    foreach ($pair in @(@('binkw32.dll.steam_original', $md5BinkOriginal, @('binkw32.dll')),
                        @('tru.exe.steam_original', $md5ExeOriginal, @('tru.exe', 'tru.exe.steam_original')))) {
        $backup = Join-Path $backupDir $pair[0]
        if (Test-Path -LiteralPath $backup -PathType Leaf) { continue }
        $from = @($pair[2] | ForEach-Object { Join-Path $GamePath $_ } |
            Where-Object { (Test-Path -LiteralPath $_ -PathType Leaf) -and ((Get-Md5 $_) -eq $pair[1]) }) | Select-Object -First 1
        if (!$from) { throw "No backup $backup and no file with the Steam MD5 $($pair[1]) in the game folder ($($pair[2] -join ', ')) - nothing changed." }
        Copy-Item -LiteralPath $from -Destination $backup
        Write-Log "Backup created: $from -> $backup"
    }

    # Safety: the backups must be the untouched Steam files before anything is overwritten.
    foreach ($pair in @(@('binkw32.dll.steam_original', $md5BinkOriginal), @('tru.exe.steam_original', $md5ExeOriginal))) {
        $hash = Get-Md5 (Join-Path $backupDir $pair[0])
        Write-Log "backup $($pair[0]): $hash (expected $($pair[1]))" -Level DEBUG
        if ($hash -ne $pair[1]) { throw "Backup $($pair[0]) does not match the Steam original." }
    }
    Write-Log 'Backups verified.' -Level VERBOSE

    # Verify inputs first; stop before touching the game folder if anything is wrong.
    Write-Log 'Dry run before install ...' -Level VERBOSE
    $code = Invoke-Installer @('--check')
    if ($code -ne 0) { throw "Dry run failed (exit code $code); nothing was changed." }

    foreach ($name in 'ModLoader.asi', 'binkw32.dll') {
        Copy-Item -LiteralPath (Join-Path $loaderDir $name) -Destination (Join-Path $GamePath $name) -Force
        Write-Log "copied $name"
    }

    $installArgs = @()
    if ($Credits) {
        $installArgs += '--credits'
        if ($Rad) { $installArgs += @('--rad', $Rad) }
        if ($Ffmpeg) { $installArgs += @('--ffmpeg', $Ffmpeg) }
    }
    Write-Log "Running install_dlc.py $($installArgs -join ' ') ..." -Level VERBOSE
    $code = Invoke-Installer $installArgs
    Write-FileState 'after install'
    if ($code -ne 0) { throw "install_dlc.py failed (exit code $code)." }
    Write-InstallManifest
    Write-Log 'Next: Steam -> start the game, new game via "Downloadable content" -> Beneath the Ashes, lock to 60 fps.'
}
catch {
    Write-Log "FAILED: $($_.Exception.Message)" -Level ERROR
    Write-Log ($_.ScriptStackTrace) -Level DEBUG
    throw
}
finally {
    if ($Trace) { Set-PSDebug -Off }
    Write-Host "Log: $logFile"
}
