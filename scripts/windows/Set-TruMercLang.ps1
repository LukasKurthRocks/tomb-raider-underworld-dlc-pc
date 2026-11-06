<#
.SYNOPSIS
    Installs or removes TruMercLang.asi (fun option: the mercenaries' barks in another language, e.g. Spanish) next to
    tru.exe.

.DESCRIPTION
    -Install copies TruMercLang.asi (built by Build-TruAsi.ps1 -Name TruMercLang -OutDir ...) and its sample .ini
             from -SourceDir (default <workspace>\work\asi) into the game folder; the Ultimate ASI Loader the game ships
             as binkw32.dll loads every *.asi there. The sample .ini has Enabled=0 - the plugin hooks nothing until the
             owner sets Enabled=1 (src\asi\TruMercLang\README.md).
    -Remove  deletes them again - only if they are ours: the same SHA-256 as a TruMercLang.asi / .ini built anywhere
             below <workspace>\work\asi (e.g. work\asi\merclang01) or one of our released builds listed in
             $earlierBuilds (none yet); a foreign file of the same name is never overwritten or removed. An .ini the
             owner edited (e.g. Enabled=1) is not ours any more and is kept. TruMercLang.log is left in place. Nothing
             installed = nothing to do (no error), so the test harness may call -Remove for every profile.
    -Install over an earlier build of ours replaces it (update); an edited .ini is kept (the plugin's built-in
             defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruMercLang_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.PARAMETER SourceDir
    Folder with the built TruMercLang.asi / .ini (default <workspace>\work\asi).

.EXAMPLE
    .\Set-TruMercLang.ps1 -Install -SourceDir ..\..\work\asi\merclang01 -Verbose
    .\Set-TruMercLang.ps1 -Remove
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
$names   = 'TruMercLang.asi', 'TruMercLang.ini'
# released builds of ours (SHA-256), recognised even when their output folder below work\asi is gone
$earlierBuilds = @{
    'TruMercLang.asi' = @()   # 0.1 (work\asi\merclang01) is found below work\asi
    'TruMercLang.ini' = @()
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruMercLang_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
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
    Write-Log "Set-TruMercLang mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
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
            if ($own -notcontains $targetHash) { Write-Log "$target is not a build of ours (or was edited) - left untouched." -Level WARN; continue }
            Remove-Item -LiteralPath $target
            Write-Log "$name removed from $GamePath."
            continue
        }
        if (!(Test-Path -LiteralPath $source)) { throw "$source not found (run Build-TruAsi.ps1 -Name TruMercLang first)." }
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
