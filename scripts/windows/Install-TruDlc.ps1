<#
.SYNOPSIS
    Installs the trudlcport (Xbox 360 DLC -> PC) build and ModLoader into the Steam copy of Tomb Raider: Underworld.

.DESCRIPTION
    -Check    Dry run of install_dlc.py: verifies game and DLC inputs, writes nothing to the game folder.
    (default) Copies ModLoader.asi + binkw32.dll into the game folder, then runs install_dlc.py.
              install_dlc.py itself keeps tru.exe as tru.exe.steam_original and an old mods\ as mods_backup_<time>.
    -Restore  Puts back the original binkw32.dll and tru.exe from <workspace>\backup and renames mods\ to mods_disabled_<time>.

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
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Check,
    [switch]$Restore,
    [switch]$Trace,
    [string]$GamePath,
    [string]$Build = 'B138',
    [string[]]$Package,
    [switch]$PackageOnly,
    [string]$DlcPath,
    [string]$PackageList
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
New-Item -ItemType Directory -Force -Path $logDir -WhatIf:$false | Out-Null
$logFile = Join-Path $logDir ('Install-TruDlc_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $mode)
Set-TruLogFile -Path $logFile

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
    Write-Log ('python ' + (($pyArgs | ForEach-Object { '"{0}"' -f $_ }) -join ' ')) -Level DEBUG
    # Native stderr must not become a terminating error under ErrorActionPreference Stop (PS 5.1).
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & python @pyArgs 2>&1 | ForEach-Object {
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
    Write-Log "Install-TruDlc mode=$mode build=$Build log=$logFile" -Level VERBOSE
    Write-Log "PowerShell $($PSVersionTable.PSVersion) on $([Environment]::OSVersion.VersionString)" -Level DEBUG

    # Raw Xbox LIVE packages (-Package, or files in input\xbox-dlc-live): identify, verify, extract into $dlcPath.
    $pendingRoles = @()
    if (!$Restore) {
        $packageArgs = @{ Destination = $dlcPath; CheckOnly = [bool]$Check; WhatIf = [bool]$WhatIfPreference }
        if ($PackageList) { $packageArgs.PackageList = $PackageList }
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
        return
    }

    $pyVersion = (& python --version 2>&1) -join ' '
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

    Write-Log 'Running install_dlc.py ...' -Level VERBOSE
    $code = Invoke-Installer @()
    Write-FileState 'after install'
    if ($code -ne 0) { throw "install_dlc.py failed (exit code $code)." }
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
