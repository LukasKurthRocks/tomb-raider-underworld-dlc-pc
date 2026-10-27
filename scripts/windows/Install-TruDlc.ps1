<#
.SYNOPSIS
    Installs the trudlcport (Xbox 360 DLC -> PC) build and ModLoader into the Steam copy of Tomb Raider: Underworld.

.DESCRIPTION
    -Check    Dry run of install_dlc.py: verifies game and DLC inputs, writes nothing.
    (default) Copies ModLoader.asi + binkw32.dll into the game folder, then runs install_dlc.py.
              install_dlc.py itself keeps tru.exe as tru.exe.steam_original and an old mods\ as mods_backup_<time>.
    -Restore  Puts back the original binkw32.dll and tru.exe from .\backup and renames mods\ to mods_disabled_<time>.

    Original files are backed up in .\backup (binkw32.dll.steam_original, tru.exe.steam_original).
    The script never stops a running game; it aborts instead.

.EXAMPLE
    .\Install-TruDlc.ps1 -Check
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Restore,
    [string]$GamePath = '<Spielordner>',
    [string]$Build = 'B138'
)

$ErrorActionPreference = 'Stop'
$root      = $PSScriptRoot
$dlcPath   = Join-Path $root 'input\xbox-dlc'
$release   = Join-Path $root "release\$Build"
$kitPath   = Join-Path $release 'kit'
$installer = Join-Path $release 'install_dlc.py'
$loaderDir = Join-Path $root 'staging\ModLoader-v1.2'
$backupDir = Join-Path $root 'backup'

$md5BinkOriginal = '2f912c88c18c4aa65b2153339482f320'
$md5ExeOriginal  = 'b36da327a320eab8b5c8464b27685840'

function Get-Md5 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm MD5).Hash.ToLower()
}

function Assert-GameClosed {
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) {
        throw 'Tomb Raider: Underworld (tru.exe) is running. Please close the game first.'
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) {
    throw "No tru.exe in game folder: $GamePath"
}

if ($Restore) {
    Assert-GameClosed
    Copy-Item -LiteralPath (Join-Path $backupDir 'binkw32.dll.steam_original') -Destination (Join-Path $GamePath 'binkw32.dll') -Force
    Copy-Item -LiteralPath (Join-Path $backupDir 'tru.exe.steam_original') -Destination (Join-Path $GamePath 'tru.exe') -Force
    $mods = Join-Path $GamePath 'mods'
    if (Test-Path -LiteralPath $mods) {
        $newName = 'mods_disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
        Rename-Item -LiteralPath $mods -NewName $newName
        Write-Host "mods\ renamed to $newName"
    }
    $asi = Join-Path $GamePath 'ModLoader.asi'
    if (Test-Path -LiteralPath $asi) {
        Rename-Item -LiteralPath $asi -NewName 'ModLoader.asi.disabled'
        Write-Host 'ModLoader.asi renamed to ModLoader.asi.disabled'
    }
    Write-Host 'Restored original binkw32.dll and tru.exe.'
    return
}

$pyArgs = @($installer, '--game', $GamePath, '--dlc', $dlcPath, '--kit', $kitPath)

if ($Check) {
    & python @pyArgs --check
    Write-Host "install_dlc.py exit code: $LASTEXITCODE"
    return
}

Assert-GameClosed

# Safety: the backups must be the untouched Steam files before anything is overwritten.
if ((Get-Md5 (Join-Path $backupDir 'binkw32.dll.steam_original')) -ne $md5BinkOriginal) { throw 'Backup binkw32.dll does not match the Steam original.' }
if ((Get-Md5 (Join-Path $backupDir 'tru.exe.steam_original')) -ne $md5ExeOriginal) { throw 'Backup tru.exe does not match the Steam original.' }

# Verify inputs first; stop before touching the game folder if anything is wrong.
& python @pyArgs --check
if ($LASTEXITCODE -ne 0) { throw "Dry run failed (exit code $LASTEXITCODE); nothing was changed." }

foreach ($name in 'ModLoader.asi', 'binkw32.dll') {
    Copy-Item -LiteralPath (Join-Path $loaderDir $name) -Destination (Join-Path $GamePath $name) -Force
    Write-Host "copied $name"
}

& python @pyArgs
Write-Host "install_dlc.py exit code: $LASTEXITCODE"
if ($LASTEXITCODE -eq 0) {
    Write-Host 'Next: Steam -> start the game, new game via "Downloadable content" -> Beneath the Ashes, lock to 60 fps.'
}
