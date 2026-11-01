<#
.SYNOPSIS
    Installs or removes TruMenu.asi (in-game debug menu, Dear ImGui, L3 + R3) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruMenu.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruMenu.log is left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruMenu_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.EXAMPLE
    .\Set-TruMenu.ps1 -Install -Verbose
    .\Set-TruMenu.ps1 -Remove
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
$names   = 'TruMenu.asi', 'TruMenu.ini'
# SHA-256 of earlier builds of ours (0.1.3, 0.2, 0.3, 0.4, all 2026-10-31) - recognised as ours for update / removal
$earlierBuilds = @{
    'TruMenu.asi' = @('50ebd28adcf96cef7e1db673ce293b5810bd8d64d0669617d09a1250598491a3',
                      'cd1b8796e40fccb09ab063d7e9f955b9029a230e37b21dce9bb570c1a3cb1892',
                      '9dda37273b5473d560474e7473b82978bfc77d3bd4d4af2ec0ae10e625b0b7ca',
                      'ae80725d7ad14fcf5a157e5f6b5a1d1190b1dbda17638ebdc875a2a95e0a9304',
                      '557962839d28b19e71ada3a74bb1c50a27fdc5a9f7765b72894758629fa66c51',   # 0.5 (2026-10-31)
                      '53d4cedb5523a51f2909181a5c9f249e27074ef0ebe6c41d06f2adc0de55f44b')   # 0.5 + TruGuard items (2026-11-01)
    'TruMenu.ini' = @('9a82044330189540488a98f2d53224d60e7eadb53a9b3246582eb1109912896a',
                      'dea74bda46400d0f743494d85536c1d11011d347fdea16f3fc5978491e5bd9c1',
                      '91bde312e5a0c2e5bbcaab6d217328f7d63846c2a24ef714bd839177e19393da',
                      'ae77e5d50799c4d528a5bf8339b7266c3e0c0dd05024247932cf012cdf302e83')
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruMenu_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruMenu mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
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
