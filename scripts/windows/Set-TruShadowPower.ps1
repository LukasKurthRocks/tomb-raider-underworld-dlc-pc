<#
.SYNOPSIS
    Installs or removes TruShadowPower.asi (DLC 2 shadow-power slow motion) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruShadowPower.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruShadowPower.log is left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruShadowPower_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.PARAMETER SourceDir
    Folder with the built .asi / .ini (default <repository>\work\asi; e.g. work\asi\v05 for a build made with
    Build-TruAsi.ps1 -OutDir).

.EXAMPLE
    .\Set-TruShadowPower.ps1 -Install -Verbose
    .\Set-TruShadowPower.ps1 -Install -SourceDir .\work\asi\v05
    .\Set-TruShadowPower.ps1 -Remove
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
$names   = 'TruShadowPower.asi', 'TruShadowPower.ini'
# SHA-256 of earlier builds of ours (0.1 = slow motion only, 0.2 = estimated meter, 0.3 = translated meter, all
# 2026-10-30; 0.4 = Lara meter conditions, 2026-10-31; 0.5 = TU states (work\asi\v05) and 0.5.1 as installed for
# test 48k, 2026-11-01; 0.6 = condition 1046 (work\asi\v06), 2026-11-01) - recognised as ours for update / removal
$earlierBuilds = @{
    'TruShadowPower.asi' = @('5eaeeb3d33d5e53b7059ff39323907cc38d2288625c09439943efabb20093366',
                             '0e307cab2bae9e805ecd0a2c4fb645b943ec792c47ae8a32d489d5441b2e335e',
                             '5d638bae7c41c888dac8d328ec8ef5c5aaac85c0c3100f3fe071409ebc247b7c',
                             '31cea1102d986789d656c73472cd410cd560ea890c6e27f17e583b230183c9e0',
                             '6887f3dc0436e5125f5b824d5af168a7493dc9afdb4e97572380c381bbb45a31',
                             '004e190490b66872c6bc3780681ae45877d25501974a602b28c9d2a9acdedd2e',
                             '68009a611af59f980a6d80053720e791173e32ec93b6ef5a4707e2bd6f5005b9')
    'TruShadowPower.ini' = @('03499f85d90031c5f0140b98be23f7b5dcb11f92ff8834b3ebe6d1b6aea4a0db',
                             '7130a68b309aedd422082beea02f78c9a8d67ba10ab16209561f5dabc614d42e',
                             '3001b5730bcecd218857143df32632b82dcb6c569f34c23853535f3b806a5f2a',
                             '4924bfb8cac427467517c10c543f9c6eadc1f7503cf755ff54a5ef99671e29d9')
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruShadowPower_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruShadowPower mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
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
