<#
.SYNOPSIS
    Replaces one file in the game's mods\ folder with a new build (with backup), or restores the backup.

.DESCRIPTION
    Install: copies -Source to <game>\mods\<Name>. The file it replaces is saved first as
             <workspace>\backup\mods\<Name>.<md5> (kept if it already exists). Source and result are MD5-checked.
    -Restore copies the backup given by -BackupMd5 (or the only backup for <Name>) back to <game>\mods\<Name>.

    The game folder is taken from the Steam libraries (app 8140) unless -GamePath is given.
    Every run writes <workspace>\logs\Install-TruModFile_<time>.log. -Verbose shows steps, -Debug paths/hashes,
    -Trace adds a PowerShell line trace. The script never stops a running game; it aborts instead.

.EXAMPLE
    .\scripts\windows\Install-TruModFile.ps1 -Source .\work\dlc_screen\generalbank.drm -Name generalbank.drm -Verbose
.EXAMPLE
    .\Install-TruModFile.ps1 -Name generalbank.drm -Restore -Verbose
.EXAMPLE
    .\scripts\windows\Install-TruModFile.ps1 -Source .\work\dlc_text\local\locals.bin_004 -Name local\locals.bin_004
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Name,
    [string]$Source,
    [switch]$Restore,
    [string]$BackupMd5,
    [string]$GamePath,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Find-TruGamePath, Get-Md5, Get-TruWorkspacePath
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$backupDir = Join-Path $root 'backup\mods'
$logDir    = $paths.Logs
$mode      = if ($Restore) { 'Restore' } else { 'Install' }

New-Item -ItemType Directory -Force -Path $logDir, $backupDir | Out-Null
$logFile = Join-Path $logDir ('Install-TruModFile_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $mode)
Set-TruLogFile -Path $logFile

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Install-TruModFile mode=$mode name=$Name log=$logFile" -Level VERBOSE
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) {
        throw 'Tomb Raider: Underworld (tru.exe) is running. Please close the game first.'
    }
    if (!$GamePath) {
        $GamePath = Find-TruGamePath
        if (!$GamePath) { throw 'Game folder not found in the Steam libraries; pass -GamePath.' }
        Write-Log "Game folder found via Steam: $GamePath" -Level VERBOSE
    }
    $target = Join-Path $GamePath "mods\$Name"
    if (!(Test-Path -LiteralPath $target)) { throw "Not found in the game's mods folder: $Name" }
    $current = Get-Md5 $target
    Write-Log "current mods\$Name md5 $current" -Level DEBUG
    # files in sub folders (e.g. local\locals.bin_004) keep their sub folder below backup\mods
    $leaf = Split-Path -Leaf $Name
    $parent = Split-Path -Parent $Name
    $backupSub = if ($parent) { Join-Path $backupDir $parent } else { $backupDir }
    New-Item -ItemType Directory -Force -Path $backupSub | Out-Null

    if ($Restore) {
        $pattern = if ($BackupMd5) { "$leaf.$BackupMd5" } else { "$leaf.*" }
        $backups = @(Get-ChildItem -LiteralPath $backupSub -Filter $pattern -File)
        if ($backups.Count -ne 1) { throw "Expected exactly one backup matching $pattern in $backupSub, found $($backups.Count); pass -BackupMd5." }
        $wanted = $backups[0].Name.Substring($leaf.Length + 1)
        if ((Get-Md5 $backups[0].FullName) -ne $wanted) { throw "Backup $($backups[0].Name) does not match its MD5 name." }
        Copy-Item -LiteralPath $backups[0].FullName -Destination $target -Force
        if ((Get-Md5 $target) -ne $wanted) { throw "Restored mods\$Name does not match the backup." }
        Write-Log "Restored mods\$Name from backup (md5 $wanted)."
        return
    }

    if (!$Source) { throw 'Pass -Source (the new file) or -Restore.' }
    $sourceMd5 = Get-Md5 $Source
    Write-Log "source $Source md5 $sourceMd5" -Level DEBUG
    if ($sourceMd5 -eq $current) { Write-Log "mods\$Name is already this build (md5 $current)."; return }

    $backup = Join-Path $backupSub "$leaf.$current"
    if (!(Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $target -Destination $backup
        Write-Log "backup: backup\mods\$Name.$current"
    } else {
        Write-Log "backup already present: backup\mods\$Name.$current" -Level VERBOSE
    }
    Copy-Item -LiteralPath $Source -Destination $target -Force
    if ((Get-Md5 $target) -ne $sourceMd5) { throw "Copied mods\$Name does not match the source." }
    Write-Log "Installed mods\$Name (md5 $sourceMd5); previous build md5 $current."
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
