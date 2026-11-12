<#
.SYNOPSIS
    Installs, checks or removes TruQoL.asi (player comfort options: frame limiter, field of view, camera shake, the
    start-up fix for PCs with more than 31 CPU threads) next to tru.exe.

.DESCRIPTION
    -Install  copies TruQoL.asi (built by Build-TruAsi.ps1 -Name TruQoL -OutDir ...) and its sample .ini from
              -SourceDir (default <workspace>\work\asi) into the game folder; the Ultimate ASI Loader the game ships as
              binkw32.dll loads every *.asi there. A TruQoL.asi / .ini of ours already there (the same SHA-256 as a
              build below <workspace>\work\asi or a released build in $earlierBuilds) is replaced (update); a foreign
              TruQoL.asi is never overwritten; an .ini the owner edited is not ours and is kept (the plugin's
              built-in defaults cover options it lacks).
    -Remove   deletes TruQoL.asi / TruQoL.ini again - only if they are ours (same rule). TruQoL.log is left in place.
              Nothing installed = nothing to do (no error), so the test harness may call -Remove for every profile.
    -Restore  the same as -Remove: the game folder as before -Install (TruQoL adds files only, it changes none).
    -Check    dry run: writes nothing into the game folder. Alone it reports what is installed (ours / foreign /
              edited), the d3d9.dll in the game folder (system, TRAWindowed, DXVK, dxwrapper - the plugin's frame
              limiter switches itself off for DXVK and for dxwrapper with LimitPerFrameFPS > 0), dxvk.conf /
              dxwrapper.ini values and a TruMenu.ini [Camera] ShakeScale that would compete for the same two code
              sites. With -Install or -Remove / -Restore it lists what that run would change.
    The game must not be running for -Install / -Remove / -Restore. Every run writes
    <workspace>\logs\Set-TruQoL_<time>_<mode>.log. -Verbose shows the steps, -Debug the hashes, -Trace adds a
    PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.PARAMETER SourceDir
    Folder with the built TruQoL.asi / .ini (default <workspace>\work\asi; the 0.1 build is work\asi\qol01).

.EXAMPLE
    .\Set-TruQoL.ps1 -Check -Verbose
    .\Set-TruQoL.ps1 -Install -SourceDir ..\..\work\asi\qol01 -Check
    .\Set-TruQoL.ps1 -Install -SourceDir ..\..\work\asi\qol01 -Verbose
    .\Set-TruQoL.ps1 -Restore
#>
[CmdletBinding(DefaultParameterSetName = 'Check')]
param(
    [Parameter(ParameterSetName = 'Install', Mandatory)][switch]$Install,
    [Parameter(ParameterSetName = 'Remove', Mandatory)][switch]$Remove,
    [Parameter(ParameterSetName = 'Restore', Mandatory)][switch]$Restore,
    [Parameter(ParameterSetName = 'Check', Mandatory)]
    [Parameter(ParameterSetName = 'Install')]
    [Parameter(ParameterSetName = 'Remove')]
    [Parameter(ParameterSetName = 'Restore')][switch]$Check,
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
$names   = 'TruQoL.asi', 'TruQoL.ini'
$mode    = $PSCmdlet.ParameterSetName
$removing = $Remove -or $Restore
# released builds of ours (SHA-256), recognised even when their output folder below work\asi is gone; the first build
# (0.1, work\asi\qol01, 2026-11-08) is found below work\asi like every other build
$earlierBuilds = @{
    'TruQoL.asi' = @('f4cc77e825cca8831bdde49e32f56f36a70d8ed2cecdbf97ae7e1d2f3defa7bf',   # 0.1.6 [Save] RetryOnLock (work\asi\qol016, installed 2026-11-11)
                     'de2a25e4484bc76ac29817710a6a559984d356b5c3ff0232e890972ad75026b8')   # 0.1.7 dated log lines (work\asi\i_1211\TruQoL, current)
    'TruQoL.ini' = @('c02cebfa259a6564e3ebb84b32b65360c8b0b67e25b183597d7d68d76145d94c')   # sample .ini of 0.1.6 / 0.1.7
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruQoL_{0}_{1}{2}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $mode, $(if ($Check -and $mode -ne 'Check') { 'Check' } else { '' }))
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

# true when the bytes of a file contain the ASCII text (case-insensitive); read only
function Test-FileText {
    param([string]$Path, [string]$Text)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $latin = [System.Text.Encoding]::GetEncoding(28591).GetString($bytes)
    return $latin.IndexOf($Text, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

# the value of 'key = value' anywhere in a text file (last one wins, ';' and '#' start a comment); $null = not found
function Get-FileKey {
    param([string]$Path, [string]$Key)
    if (!(Test-Path -LiteralPath $Path)) { return $null }
    $value = $null
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match ('^\s*{0}\s*=\s*"?([^;#"]*)' -f [regex]::Escape($Key))) { $value = $Matches[1].Trim() }
    }
    return $value
}

# what the plugin's auto-off would see in the game folder (static: the files, not the running process)
function Write-LimiterReport {
    param([string]$Game)
    $d3d9 = Join-Path $Game 'd3d9.dll'
    if (!(Test-Path -LiteralPath $d3d9)) {
        Write-Log 'd3d9.dll: none in the game folder (the system one) - TruQoL limits the frame rate ([FrameLimit] Enabled=1).'
        return
    }
    $kind = 'unknown wrapper'
    if ((Test-FileText $d3d9 'DXVK_CONFIG_FILE') -or (Test-FileText $d3d9 'dxvk.conf')) { $kind = 'DXVK' }
    elseif ((Test-FileText $d3d9 'dxwrapper') -or (Test-Path -LiteralPath (Join-Path $Game 'dxwrapper.dll'))) { $kind = 'dxwrapper' }
    elseif (Test-FileText $d3d9 'trawindowed') { $kind = 'TRAWindowed' }
    Write-Log "d3d9.dll in the game folder: $kind (sha256 $(Get-Sha256 $d3d9))."
    if ($kind -eq 'DXVK') {
        $conf = Join-Path $Game 'dxvk.conf'
        $v = Get-FileKey $conf 'd3d9.maxFrameRate'
        if ($null -eq $v) { $v = '-60 (DXVK profile for tru.exe; no d3d9.maxFrameRate in dxvk.conf)' }
        Write-Log "DXVK d3d9.maxFrameRate = $v - TruQoL's limiter switches itself off unless it is 0 ([FrameLimit] AutoOff=1)."
    }
    elseif ($kind -eq 'dxwrapper') {
        $v = Get-FileKey (Join-Path $Game 'dxwrapper.ini') 'LimitPerFrameFPS'
        if ($null -eq $v) { $v = 'not set' }
        Write-Log "dxwrapper LimitPerFrameFPS = $v - TruQoL's limiter switches itself off when it is > 0 ([FrameLimit] AutoOff=1)."
    }
    else {
        Write-Log "$kind has no known frame limiter - TruQoL limits the frame rate ([FrameLimit] Enabled=1)."
    }
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruQoL mode=$mode check=$([bool]$Check) log=$logFile" -Level VERBOSE
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) { throw "Game folder not found (-GamePath): $GamePath" }
    Write-Log "Game folder: $GamePath" -Level VERBOSE
    $dryRun = [bool]$Check
    if (!$dryRun -and (Get-Process -Name 'tru' -ErrorAction SilentlyContinue)) {
        throw 'Tomb Raider: Underworld is running. Please close it first.'
    }

    foreach ($name in $names) {
        $source = Join-Path $built $name
        $target = Join-Path $GamePath $name
        $targetHash = if (Test-Path -LiteralPath $target) { Get-Sha256 $target } else { $null }
        if ($targetHash) { Write-Log "$name installed sha256 $targetHash" -Level DEBUG }
        $isOwn = $targetHash -and ((Get-OwnHashes $name) -contains $targetHash)
        if ($mode -eq 'Check') {
            if (!$targetHash) { Write-Log "$name not installed." }
            elseif ($isOwn) { Write-Log "$name installed (a build of ours)." }
            elseif ($name -like '*.ini') { Write-Log "$name installed (edited by the owner - -Install keeps it)." }
            else { Write-Log "$name installed but not a build of ours - -Install / -Remove leave it untouched." -Level WARN }
            continue
        }
        if ($removing) {
            if (!$targetHash) { Write-Log "$name not in the game folder." -Level VERBOSE; continue }
            if (!$isOwn) { Write-Log "$target is not a build of ours - left untouched." -Level WARN; continue }
            if ($dryRun) { Write-Log "Check: $name would be removed from $GamePath."; continue }
            Remove-Item -LiteralPath $target
            Write-Log "$name removed from $GamePath."
            continue
        }
        if (!(Test-Path -LiteralPath $source)) { throw "$source not found (run Build-TruAsi.ps1 -Name TruQoL first)." }
        $sourceHash = Get-Sha256 $source
        Write-Log "$name built sha256 $sourceHash" -Level DEBUG
        if ($targetHash -eq $sourceHash) { Write-Log "$name already installed."; continue }
        if ($targetHash -and !$isOwn) {
            if ($name -like '*.ini') { Write-Log "$target was edited (not a build of ours) - kept." -Level WARN; continue }
            throw "$target exists and is not a build of ours - left untouched."
        }
        if ($dryRun) {
            Write-Log ('Check: {0} would be {1}.' -f $name, $(if ($isOwn) { 'updated (earlier build of ours replaced)' } else { "copied to $target" }))
            continue
        }
        Copy-Item -LiteralPath $source -Destination $target -Force
        if ($isOwn) { Write-Log "$name updated in $GamePath (earlier build replaced)." }
        else { Write-Log "$name copied to $target." }
    }

    if ($mode -eq 'Check' -or ($Install -and $dryRun)) {
        Write-LimiterReport -Game $GamePath
        $menuIni = Join-Path $GamePath 'TruMenu.ini'
        $shake = Get-FileKey $menuIni 'ShakeScale'
        if ($null -ne $shake -and $shake -ne '100') {
            Write-Log ('TruMenu.ini ShakeScale = {0}: TruMenu and TruQoL [Camera] ShakeScale patch the same two calls; with TruQoL ShakeScale below 1.0 TruQoL patches them at load and TruMenu refuses its own (logged) - use one of them.' -f $shake) -Level WARN
        }
        if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) { Write-Log 'The game is running (only a check - nothing changed).' -Level WARN }
        Write-Log 'Check only - nothing changed in the game folder.'
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
