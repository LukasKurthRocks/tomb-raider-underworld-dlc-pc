<#
.SYNOPSIS
    Installs or removes TruGuard.asi (exception diagnostics: fault sites, minidumps, optional resume) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruGuard.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruGuard.log and the TruGuardDumps folder are left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruGuard_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.EXAMPLE
    .\Set-TruGuard.ps1 -Install -Verbose
    .\Set-TruGuard.ps1 -Remove
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
$names   = 'TruGuard.asi', 'TruGuard.ini'
# SHA-256 of earlier builds of ours - recognised as ours for update / removal (0.1 of 2026-11-01, used in the field
# runs guard / 48i-48l; its shipped .ini)
$earlierBuilds = @{
    'TruGuard.asi' = @(
        '0886a0332228dc9f298fcc2e72433fd0ea4d188ad256d5cd845f1935b496510e'  # 0.1
        'c138012bc8e338e2703633ebc4025b8d665cd83186f4a0c441b3890267df7e19'  # 0.2
        'ae6fbcc5c4fc2319d759d25c141ef29e60d988828b7b6bab55caec92be0f36f7'  # 0.2
        'da38cd9c641fd9c91d4bd639cac03a0529e6b850af63a9f9488eafbbe1a6c2cc'  # 0.3
        'acd2a742848f3137668b2c2825352dcd0ac713c18340c1c15b8fbe438578ed8d'  # 0.4 before the review fixes
        '1ff03f56a5fc931a4fa3c8204c7ba27ae6813b3337335a361a1a17ddc47323a9'  # 0.4 review fixes, first build
        'b9f72a529ecd6c564b3df5803caf75c84fc300f898fa78f266dc940b7f105a0c'  # 0.4 review fixes, second build
        'f6c5da1338d38830ebb6408011a119153052c0f863ee9f844dbc011f780792ab'  # 0.4 review fixes, third build
        'db259e5a7b0a382e266d94dc057cda5c091da0d1d29ea6ce047448c0134c1aa1'  # 0.4 review fixes, fourth build
        '45dd58533ea157f19acbacdc05692711df98e74f4e3992966d89dc96c137c4dc'  # 0.4 review fixes
        '39fa6858a5bf5f1b5f24023828a0ac1211c43b1c24f974606553ea779e7870e4'  # 0.4.1
        '0e7224594f2ee130dcbddb64ce7b61b6a63edd83367502c3183973192ad6755d'  # 0.4.2, first build
        '39a6a471d0a91a90980280103176da340554048bc4eb1697f21fdcd3dadd0319'  # 0.4.2, outside logging
        'ade03eb7b9e9fd2384ed474e21f0e271c5d969b5f551479705fccd77e66b2837'  # 0.4.2+outside-fix, current build
    )
    'TruGuard.ini' = @(
        'fc7ae32cd19ceb7b1853a9004e84072d2415e55a055ec8aa39419a1558775c6c'  # 0.1
        '64b9a62891320bea529e1e7c40dbea6147936d2fd6c1004d6ea019da509e7b1d'  # 0.3/0.4 before the review fixes
        '55cfd7d4495f6f8cf3f9cc19cebea5fc10c040efccd259dffeb0a7cb65896c2b'  # 0.4 review fixes, second build
        'ea012508203d7577ba27ac483a458636077e160bbb9e5acc36f27e0204d341e6'  # 0.4 review fixes
        '834e07f458d64f40c0e0df403f01f67c6c3252ff5281872db5de31b60bd9e9b8'  # 0.4.1
        '1fa917927799193d93d1278f95064c96e62d646af6a683f9802b5a6185c12220'  # 0.4.2, current build
    )
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruGuard_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruGuard mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
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
