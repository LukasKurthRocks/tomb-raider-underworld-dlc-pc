<#
.SYNOPSIS
    Installs or removes TruRockVein.asi (DLC 2 rock veins: title-update markup conditions 607 / 608; since 0.10 also
    the title update's SweepAndPrune limits, since 0.11 its ledge-corner nudge, since 0.12 its jump targets on
    vertical segments, since 0.13 its edge probe) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruRockVein.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruRockVein.log is left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruRockVein_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.EXAMPLE
    .\Set-TruRockVein.ps1 -Install -Verbose
    .\Set-TruRockVein.ps1 -Remove
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
$names   = 'TruRockVein.asi', 'TruRockVein.ini'
# SHA-256 of earlier builds of ours - recognised as ours for update / removal (0.1 of 2026-10-30 23:09,
# 0.2 of 2026-10-31, 0.3 of 2026-11-01 as installed for test 48i, 0.4 of 2026-11-01 as installed for test 48j,
# 0.5 of 2026-11-01 as installed for test 48k, 0.6 of 2026-11-01 as installed for test 48l, 0.7 of 2026-11-01 for
# tests 48m / 50a)
$earlierBuilds = @{
    'TruRockVein.asi' = @('7473ddd8580a5d07d14b8c55409520a0fcff3e46e6ed657751fe8fb69ef2b230',
                          '6edc63ca49f69d44fe3fdf7e1fda73c25b53296e2cc32b65cf6b6451dd7e6cb8',
                          'f875759e392c8c3c502f03752d501688850b8e259a0751b7dc5cd6cdcf3da45f',
                          'ce7a8712f267c4d2836730edc7013301fce8413fc7186e8dd29bfbdff710b5e6',
                          '8d5c97328621be81e1f4d500e1bd2c7781b3a203e914351295eaf57ba4abd4ec',
                          'f0d3456c9a66ed27b5fc15f51db83646078f1c19b95501868065f6bb1a37b57e',
                          'c2b626dff712ee579a18ff11eb389333455b9a3a9a289173464243e221e1173b',
                          '66f80abb20e9ec6a74e2f3f6e933e8be2757ec70a870f03406197999cf55b29c',   # 0.8 jump geometry (work\asi_rv08)
                          'e7430050c8587e8d1a36f09fc8c2d7de4cb2738821e9732af00f1d6967234076',   # 0.9 skip geometry (work\asi_rv09, installed since 2026-11-02)
                          'c50d7a69ee4fe0ac15aceb9dde48315c6b5f6f2f3d646117620039b58a5ea1c8',   # 0.10 SweepAndPrune limits (work\asi\rv10)
                          'e019de803b1ebb828cb05a07d11bf159cd792f8d7bc3e83b7fca1fc8be1535b0',   # 0.11 ledge-corner nudge (work\asi\rv11)
                          '4f385dac84cb3834c9826e6c7bb3bdcc6e9a4f62cf6f0b3a7cfc0f4d12c781e3',   # 0.12 jump targets (work\asi\rv12)
                          '7c53372f65288c7c6f0881277be7f2abf27f9e6589869c1d87088f16186484df',   # 0.13 edge probe (work\asi\rv13, installed 2026-11-11)
                          '6f5e3cc9ae23ab0958b62c14cc14c43f37dba8bf32cd12626da2f9aa003097ff')   # 0.13.1 dated log lines (work\asi\i_1211\TruRockVein, current)
    'TruRockVein.ini' = @('89c0283b20a375253d38e6f53e77cfb7df10b0c036650c789564c629d3f227c1',
                          '1dbfc739c5f0646ba6a791eb1b77504927b74ab7b146d9ae8b71c0621113b19f',   # sample .ini of 0.8 (also 0.9; 0.10 adds [SweepAndPrune])
                          'a16fb9d9c5671be0a3ba44e3b719465b932ee7ab111286cac4a518dbec8b5c32',   # sample .ini of 0.10 (0.11 adds [LedgeCorner])
                          'ec223baec6277c03619d04d075701c92c01a84da544b219016a245a30d509d66',   # sample .ini of 0.11 (0.12 adds [JumpTarget])
                          '1d460eafa229946cb81a9e98dc2240d0a075483c87a60c5eb9702e25074942b6',   # sample .ini of 0.12 (0.13 adds [LedgeProbe])
                          '3b2cec98c1d760aecbcf34ea94b61b5e682293ee5faf839f67b009a21c97524a')   # sample .ini of 0.13 / 0.13.1
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruRockVein_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruRockVein mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
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
