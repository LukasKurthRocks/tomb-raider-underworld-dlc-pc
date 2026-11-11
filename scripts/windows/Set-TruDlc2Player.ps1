<#
.SYNOPSIS
    Installs or removes TruDlc2Player.asi (DLC 2 player: doppelganger as player object, type record, DoppelgangerInit) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruDlc2Player.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruDlc2Player.log is left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruDlc2Player_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.EXAMPLE
    .\Set-TruDlc2Player.ps1 -Install -Verbose
    .\Set-TruDlc2Player.ps1 -Remove
#>
[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install', Mandatory)][switch]$Install,
    [Parameter(ParameterSetName = 'Remove', Mandatory)][switch]$Remove,
    [string]$GamePath,
    [string]$SourceDir,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, Find-TruGamePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$repo    = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$built   = if ($SourceDir) { $SourceDir } else { Join-Path $repo 'work\asi' }
$names   = 'TruDlc2Player.asi', 'TruDlc2Player.ini'
# SHA-256 of earlier builds of ours (0.1 .. 0.8) - recognised as ours for update / removal
$earlierBuilds = @{
    'TruDlc2Player.asi' = @('c73c8c6693000e45a1ae60b0b29d69ecb02313796a2820ab65e4546a1267992b',   # 0.1 (work\asi)
                            '70fd89e77e9e205d8117babe9f9767c33dce524394e87bfcd2af58b17994ab3a',   # 0.2 flag reset (work\asi\dlc2p02)
                            'f02fafe040c03be8c348f9de2c9872338b7c179d96a15439617c9cdb572916cd',   # 0.3 costume reset (work\asi\dlc2p03)
                            '0753689bd07f731b15ea62142201020d90d27ec7cfb5293976bf535df38487c3',   # 0.4 tracker flag (work\asi\dlc2p04)
                            '9979fdc43b6f80946efc160ffe55bd6dbedfc485e58bc6ac6558afddcc422877',   # 0.5 [Costume] TuMapping (work\asi\dlc2p05)
                            '90b80293502921be34d45ff0e3f855644aef413f4379ba8373a8d4c1a403f7ac',   # 0.6 [Mission] DialogStart (work\asi\dlc2p06)
                            'cc15b9fdda2681ebe3f86b20a12fd1da35cfbb1b0c374bfe011268d9524518f7',   # 0.7 [Mission] DialogDifficulty (work\asi\dlc2p07)
                            '62a0417e7cf74d761f3ba95ffa50681a87bb765a5e9ab30bfd79e470090fd78b')   # 0.8 [Mission] DialogHoldClear (work\asi\dlc2p08)
    'TruDlc2Player.ini' = @('eeb2fd036a03e4b97c73b46d9a3ed18a17ceab727f9cb058b66cb3246637f8b5',   # 0.1 sample .ini
                            'a5af71389086eb5221f82720826c84c66995d0eee3fade3917a1a701e9d79dc7',   # 0.2 (+ FlagReset; work\asi\dlc2p02)
                            '1c9ade1b1b53ed98b0811238e99ac81fa48b5024fe913072f76fe341b0755679',   # 0.3 (+ CostumeReset; work\asi\dlc2p03)
                            '6e2d6dea68bd72e6c25700afb80982714f049f1f181d44400410fb60ffbfd012',   # 0.4 (+ TrackerFlag; work\asi\dlc2p04)
                            'ac37a91095739b77be812d6c4e5e6efc71d5e920ac7bcfcd80c241ddc471c26e',   # 0.5 (+ [Costume] TuMapping; work\asi\dlc2p05)
                            'b7c0735f2720eb53f364defcd9a30ae855a35268bfba3152d5e3345ca682892f',   # 0.6 (+ [Mission] DialogStart; work\asi\dlc2p06)
                            'b77cdca57c21e245ba4d3ea852c6b7b6ecb47c41726cfcd55c5bcb59e5b69247',   # 0.7 (+ [Mission] DialogDifficulty; work\asi\dlc2p07)
                            'bc4093e4460d22a18d845ba194336ba186a31aa848346b320fab5f21e64b7dd6')   # 0.8 (+ [Mission] DialogHoldClear; work\asi\dlc2p08)
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruDlc2Player_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruDlc2Player mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) { throw 'Tomb Raider: Underworld is running. Please close it first.' }
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) { throw "Game folder not found (-GamePath): $GamePath" }
    Write-Log "Game folder: $GamePath" -Level VERBOSE

    foreach ($name in $names) {
        $source = Join-Path $built $name
        $target = Join-Path $GamePath $name
        if (!(Test-Path -LiteralPath $source)) { throw "$source not found (run Build-TruAsi.ps1 first)." }
        $sourceHash = Get-Sha256 $source
        Write-Log "$name built sha256 $sourceHash" -Level DEBUG
        $targetHash = if (Test-Path -LiteralPath $target) { Get-Sha256 $target } else { $null }
        if ($targetHash) { Write-Log "$name installed sha256 $targetHash" -Level DEBUG }
        $isEarlier = $targetHash -and ($earlierBuilds[$name] -contains $targetHash)
        if ($Install) {
            if ($targetHash -eq $sourceHash) { Write-Log "$name already installed."; continue }
            if ($targetHash -and !$isEarlier) {
                if ($name -like '*.ini') { Write-Log "$target was edited (not a build of ours) - kept." -Level WARN; continue }
                throw "$target exists and is not a build of ours - left untouched."
            }
            Copy-Item -LiteralPath $source -Destination $target -Force
            if ($isEarlier) { Write-Log "$name updated in $GamePath (earlier build replaced)." }
            else { Write-Log "$name copied to $target." }
        }
        else {
            if (!$targetHash) { Write-Log "$name not in the game folder." -Level VERBOSE; continue }
            if ($targetHash -ne $sourceHash -and !$isEarlier) { Write-Log "$target is not a build of ours - left untouched." -Level WARN; continue }
            Remove-Item -LiteralPath $target
            Write-Log "$name removed from $GamePath."
        }
    }
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
