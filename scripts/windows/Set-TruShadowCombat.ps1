<#
.SYNOPSIS
    Installs or removes TruShadowCombat.asi (DLC 2 combat: the title update's target list, target conditions and
    shadow-strike gate) next to tru.exe.

.DESCRIPTION
    -Install copies TruShadowCombat.asi (built by Build-TruAsi.ps1 -Name TruShadowCombat -OutDir ...) and its sample
             .ini from -SourceDir (default <workspace>\work\asi) into the game folder; the Ultimate ASI Loader the game
             ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours: the same SHA-256 as a TruShadowCombat.asi / .ini built
             anywhere below <workspace>\work\asi (e.g. work\asi\combat01) or one of our released builds listed in
             $earlierBuilds (0.1 - 0.3, 0.5.3, 0.6 - 0.6.3, 0.6.6 - 0.6.8); a foreign file of the same name is never overwritten or removed.
             TruShadowCombat.log is left in place. Nothing installed = nothing to do (no error), so the test harness
             may call -Remove for every profile.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The plugin needs TruDlc2Player.asi (doppelganger flag) and TruDoppelganger.asi (generic registry of the new
    condition ids); without them it logs why and leaves those parts off. The game must not be running. Every run
    writes <workspace>\logs\Set-TruShadowCombat_<time>.log. -Verbose shows the steps, -Debug the hashes, -Trace adds
    a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.PARAMETER SourceDir
    Folder with the built TruShadowCombat.asi / .ini (default <workspace>\work\asi).

.EXAMPLE
    .\Set-TruShadowCombat.ps1 -Install -SourceDir ..\..\work\asi\combat01 -Verbose
    .\Set-TruShadowCombat.ps1 -Remove
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
$asiRoot = Join-Path $repo 'work\asi'
$built   = if ($SourceDir) { $SourceDir } else { $asiRoot }
$names   = 'TruShadowCombat.asi', 'TruShadowCombat.ini'
# released builds of ours (SHA-256), recognised even when their output folder below work\asi is gone
$earlierBuilds = @{
    'TruShadowCombat.asi' = @('05cf33c59b24047377dddc9d414b5a18cfc82d636349b03e29659982e63e8753',    # 0.1 (work\asi\combat01)
                              'f692be359d1f6f00989b5685d875c9505b8e6e641f80e525f0718a6d43db27e5',    # 0.2 (work\asi\combat02)
                              'f65fe474cf0a930400196a4e46d62a0c976f6fc01361e31782dbce5cfb69bca7',    # 0.3 (work\asi\combat03)
                              '04933c30edd488254eec22f3815fda669d4442c5e119f12f896420ca60e00ef0',    # 0.5.3 (work\asi\combat053)
                              '78aec9a1652ead192a9e41a90fd03621d4881387a7605c1a393261ee3e579bc6',    # 0.6 (work\asi\combat06)
                              'acc4aeb17988d236502e1f352f4a9475b4a0e114bf986707b07e5f4ac031a891',    # 0.6.1 (work\asi\combat061)
                              '012c9dc4adddb6b21150bb00fee9d845daab1093bc80069eb6cb0836ae23ed12',    # 0.6.2 (work\asi\combat062)
                              '45821900e1e218a19798127d8d0e8184b4a2159b141731f787c534260fb701bd',    # 0.6.3 (work\asi\combat063)
                              '4c413af861b5104bf024552177eafe63ba534028b2df51cb24f4ce27fb55ac17',    # 0.6.6 (work\asi\combat066)
                              '11f15a66f2aaeff7fda8b5d3983dae33d3c40bbc7c53d07c413295b9ed30302f',    # 0.6.7 (work\asi\combat067)
                              'b31e7e664d5c6caf0c0f0f75a79164349969e463746c01bdcfcaa5f8a0f8a55a')    # 0.6.8 (work\asi\combat068)
    'TruShadowCombat.ini' = @('d909de94f1af40861e3e3bb3e183785af75e6f0be2167bc208aa051cfcc85ce0',    # 0.1 sample .ini
                              '4141f31f35f6e3631c5895fb2a1799963a435c2d82dc9f744ca1c8f65468fdae',    # 0.2 sample .ini
                              '8c9be2daf9e926a3d0c26d559c08bf8ee77e817cedcd3b8ebfe56f22d65645f4',    # 0.3 sample .ini
                              '74e55129c6628bc7e73ebcf0bc47e7c0c7bca3831e96ffafa305e43180233fec',    # 0.5.3 sample .ini
                              '97d06bffd3a4b05c47b8085269377cf4556fa49596290a7b6ee81afd266419da',    # 0.6 sample .ini
                              'fec519abee98446a8dad48dbe27e2009ea3972c011d704992a1ad89d2010f18f',    # 0.6.1 sample .ini
                              '133d875216a7ccbfeaa1f03789e64d0dfd4afb68e550f35db884775485e64d44',    # 0.6.2 sample .ini
                              '725b4119f15a508ce7dafce7ccfff80c98a0539a8bcefebe6f258afe8db5eb6b',    # 0.6.3 sample .ini
                              '3a5db52dea26d1d08413ec8e9c48f5c265b8eda5c075bf8a1a61ae84c803a479',    # 0.6.7 sample .ini
                              '2ff9cfb641c6dd760225a23f7c878ca71fd28084dc722b812e3c8fb857cbf753')    # 0.6.8 sample .ini
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruShadowCombat_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

# SHA-256 of every build of ours: the released ones in $earlierBuilds and every build below work\asi, per file name
function Get-OwnHashes {
    param([string]$Name)
    $hashes = @($earlierBuilds[$Name])
    if (Test-Path -LiteralPath $asiRoot) {
        foreach ($f in @(Get-ChildItem -LiteralPath $asiRoot -Recurse -File -Filter $Name -ErrorAction SilentlyContinue)) {
            $hashes += Get-Sha256 $f.FullName
            Write-Log "own build $($f.FullName)" -Level DEBUG
        }
    }
    return , $hashes
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruShadowCombat mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) { throw 'Tomb Raider: Underworld is running. Please close it first.' }
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) { throw "Game folder not found (-GamePath): $GamePath" }
    Write-Log "Game folder: $GamePath" -Level VERBOSE

    foreach ($name in $names) {
        $source = Join-Path $built $name
        $target = Join-Path $GamePath $name
        $targetHash = if (Test-Path -LiteralPath $target) { Get-Sha256 $target } else { $null }
        if ($targetHash) { Write-Log "$name installed sha256 $targetHash" -Level DEBUG }
        if ($Remove) {
            if (!$targetHash) { Write-Log "$name not in the game folder." -Level VERBOSE; continue }
            $own = Get-OwnHashes $name
            if ($own -notcontains $targetHash) { Write-Log "$target is not a build of ours - left untouched." -Level WARN; continue }
            Remove-Item -LiteralPath $target
            Write-Log "$name removed from $GamePath."
            continue
        }
        if (!(Test-Path -LiteralPath $source)) { throw "$source not found (run Build-TruAsi.ps1 -Name TruShadowCombat first)." }
        $sourceHash = Get-Sha256 $source
        Write-Log "$name built sha256 $sourceHash" -Level DEBUG
        if ($targetHash -eq $sourceHash) { Write-Log "$name already installed."; continue }
        $isOwn = $targetHash -and ((Get-OwnHashes $name) -contains $targetHash)
        if ($targetHash -and !$isOwn) {
            if ($name -like '*.ini') { Write-Log "$target was edited (not a build of ours) - kept." -Level WARN; continue }
            throw "$target exists and is not a build of ours - left untouched."
        }
        Copy-Item -LiteralPath $source -Destination $target -Force
        if ($isOwn) { Write-Log "$name updated in $GamePath (earlier build replaced)." }
        else { Write-Log "$name copied to $target." }
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
