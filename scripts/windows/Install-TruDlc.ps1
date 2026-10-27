<#
.SYNOPSIS
    Installs the trudlcport (Xbox 360 DLC -> PC) build and ModLoader into the Steam copy of Tomb Raider: Underworld.

.DESCRIPTION
    -Check    Dry run of install_dlc.py: verifies game and DLC inputs, writes nothing to the game folder.
    (default) Copies ModLoader.asi + binkw32.dll into the game folder, then runs install_dlc.py.
              install_dlc.py itself keeps tru.exe as tru.exe.steam_original and an old mods\ as mods_backup_<time>.
    -Restore  Puts back the original binkw32.dll and tru.exe from <workspace>\backup and renames mods\ to mods_disabled_<time>.

    Every run writes a log to <workspace>\logs\Install-TruDlc_<time>.log (environment, hashes, full python output).
    -Verbose shows each step, -Debug adds paths, hashes and command lines, -Trace adds a PowerShell line trace.

    Original files are backed up in <workspace>\backup (binkw32.dll.steam_original, tru.exe.steam_original).
    The script never stops a running game; it aborts instead.

.EXAMPLE
    .\Install-TruDlc.ps1 -Check -Verbose
.EXAMPLE
    .\Install-TruDlc.ps1 -Restore -Debug
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Restore,
    [switch]$Trace,
    [string]$GamePath,
    [string]$Build = 'B138'
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }

# <workspace> = the folder that holds the repository (bin, data, input, logs, backup, release - never in
# the repository); this script lives in <repository>\scripts\windows
$repo      = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$root      = Split-Path -Parent $repo
$dlcPath   = Join-Path $root 'input\xbox-dlc'
$release   = Join-Path $root "release\$Build"
$kitPath   = Join-Path $release 'kit'
$installer = Join-Path $release 'install_dlc.py'
$loaderDir = Join-Path $root 'staging\ModLoader-v1.2'
$backupDir = Join-Path $root 'backup'
$logDir    = Join-Path $root 'logs'

$md5BinkOriginal = '2f912c88c18c4aa65b2153339482f320'
$md5ExeOriginal  = 'b36da327a320eab8b5c8464b27685840'

$mode = if ($Restore) { 'Restore' } elseif ($Check) { 'Check' } else { 'Install' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Install-TruDlc_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $mode)

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'VERBOSE', 'DEBUG', 'WARN', 'ERROR')][string]$Level = 'INFO'
    )
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'), $Level, $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    switch ($Level) {
        'INFO'    { Write-Host $Message }
        'VERBOSE' { Write-Verbose $Message }
        'DEBUG'   { Write-Debug $Message }
        'WARN'    { Write-Warning $Message }
        'ERROR'   { Write-Host $Message -ForegroundColor Red }
    }
}

function Find-TruGamePath {
    # Steam library folders from the registry + libraryfolders.vdf; Tomb Raider: Underworld is app 8140.
    $steam = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if (!$steam) { return $null }
    $libraries = @($steam)
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        foreach ($match in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $libraries += $match.Groups[1].Value -replace '\\\\', '\'
        }
    }
    foreach ($library in ($libraries | Select-Object -Unique)) {
        $candidate = Join-Path $library 'steamapps\common\Tomb Raider Underworld'
        Write-Log "Steam library candidate: $candidate" -Level DEBUG
        if (Test-Path -LiteralPath (Join-Path $candidate 'tru.exe')) { return $candidate }
    }
    return $null
}

function Get-Md5 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm MD5).Hash.ToLower()
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
        $code = Invoke-Installer @('--check')
        if ($code -ne 0) { throw "Dry run failed (exit code $code)." }
        return
    }

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
