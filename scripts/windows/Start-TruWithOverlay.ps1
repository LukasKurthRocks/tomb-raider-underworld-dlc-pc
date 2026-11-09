<#
.SYNOPSIS
    Starts Tomb Raider: Underworld through Steam and attaches the Steam overlay by hand.

.DESCRIPTION
    Work-around for the known TRU problem that the Steam overlay does not show (Steam community guides for app 8140:
    run the overlay UI with the game's process id). Observed on this fork's PC (2026-11-09): Steam injects
    gameoverlayrenderer.dll into tru.exe and starts the overlay UI, but the UI log says "The game hasn't rendered a
    frame from us in over 10 seconds" and Shift+Tab shows nothing; starting the 64-bit overlay UI by hand with
    -manuallyclearframes 0 makes it work. The real cause (D3D9 Present hook chain: d3d9.dll wrapper, TruMenu present
    hook / re-entry guard, overlay) is still open - see TODO N13.

    Steps: start steam://rungameid/8140 through steam.exe, wait for tru.exe, then run
    <Steam>\gameoverlayui64.exe -steampid <steam pid> -pid <tru pid> -gameid 8140 -manuallyclearframes 0
    (gameoverlayui.exe when the 64-bit one is missing). If tru.exe is already running, only the overlay is attached.
    Nothing is changed in Steam or in the game folder. Log: <workspace>\logs\Start-TruWithOverlay_<time>.log, with the
    tail of Steam's gameoverlay_ui.txt after the start. -Verbose shows the steps, -Debug the command lines, -Trace adds
    a PowerShell line trace.

.PARAMETER SteamPath
    Steam folder; default: from the registry (HKCU\Software\Valve\Steam SteamPath), else Steam below the 32-bit
    program files folder (env ProgramFiles(x86)).

.PARAMETER WaitSeconds
    How long to wait for tru.exe after the Steam start (default 90).

.PARAMETER SettleSeconds
    Pause after tru.exe appeared before the overlay is attached (default 5, as the community scripts).

.EXAMPLE
    .\Start-TruWithOverlay.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$SteamPath,
    [ValidateRange(5, 600)][int]$WaitSeconds = 90,
    [ValidateRange(0, 60)][int]$SettleSeconds = 5,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
if ($Trace) { Set-PSDebug -Trace 1 }

$paths = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
New-Item -ItemType Directory -Force -Path $paths.Logs | Out-Null
$logFile = Join-Path $paths.Logs ('Start-TruWithOverlay_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Set-TruLogFile -Path $logFile

try {
    if (!$SteamPath) {
        $reg = Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -Name SteamPath -ErrorAction SilentlyContinue
        $SteamPath = if ($reg -and $reg.SteamPath) { $reg.SteamPath -replace '/', '\' } else { Join-Path ${env:ProgramFiles(x86)} 'Steam' }
    }
    $steamExe = Join-Path $SteamPath 'steam.exe'
    $overlayUi = Join-Path $SteamPath 'gameoverlayui64.exe'
    if (!(Test-Path -LiteralPath $overlayUi)) { $overlayUi = Join-Path $SteamPath 'gameoverlayui.exe' }
    if (!(Test-Path -LiteralPath $steamExe)) { throw "steam.exe not found in $SteamPath" }
    if (!(Test-Path -LiteralPath $overlayUi)) { throw "no gameoverlayui64.exe / gameoverlayui.exe in $SteamPath" }
    Write-Log "Steam folder $SteamPath, overlay UI $(Split-Path -Leaf $overlayUi)." -Level VERBOSE

    $game = Get-Process -Name 'tru' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($game) {
        Write-Log "tru.exe already running (pid $($game.Id)) - only the overlay is attached."
    } else {
        Write-Log 'Starting the game through Steam (steam://rungameid/8140).'
        Write-Log "`"$steamExe`" steam://rungameid/8140" -Level DEBUG
        & $steamExe 'steam://rungameid/8140'
        $deadline = (Get-Date).AddSeconds($WaitSeconds)
        while (!$game -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
            $game = Get-Process -Name 'tru' -ErrorAction SilentlyContinue | Select-Object -First 1
        }
        if (!$game) { throw "tru.exe did not start within $WaitSeconds s" }
        Write-Log "tru.exe started (pid $($game.Id)); waiting $SettleSeconds s before attaching the overlay."
        Start-Sleep -Seconds $SettleSeconds
    }

    $steam = Get-Process -Name 'steam' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$steam) { throw 'steam.exe is not running' }
    $running = Get-Process -Name 'gameoverlayui64', 'gameoverlayui' -ErrorAction SilentlyContinue
    if ($running) { Write-Log ("overlay UI already running: pid {0} - a second one is started for tru.exe" -f (($running | ForEach-Object Id) -join ', ')) -Level VERBOSE }

    $uiLog = Join-Path $SteamPath 'logs\gameoverlay_ui.txt'
    $uiLogLines = if (Test-Path -LiteralPath $uiLog) { @(Get-Content -LiteralPath $uiLog).Count } else { 0 }

    $argList = @('-steampid', $steam.Id, '-pid', $game.Id, '-gameid', 8140, '-manuallyclearframes', 0)
    Write-Log ("`"$overlayUi`" " + ($argList -join ' ')) -Level DEBUG
    $ui = Start-Process -FilePath $overlayUi -ArgumentList $argList -PassThru
    Write-Log "Overlay UI started (pid $($ui.Id)) for tru.exe pid $($game.Id), steam pid $($steam.Id). Shift+Tab in the game."

    Start-Sleep -Seconds 3
    if (Test-Path -LiteralPath $uiLog) {
        $newLines = @(Get-Content -LiteralPath $uiLog | Select-Object -Skip $uiLogLines)
        if ($newLines.Count) {
            Write-Log "Steam gameoverlay_ui.txt ($($newLines.Count) new lines since the start):" -Level VERBOSE
            $newLines | Select-Object -Last 8 | ForEach-Object { Write-Log "  $_" -Level VERBOSE }
        } else {
            Write-Log 'Steam gameoverlay_ui.txt: no new lines yet (normal; the FPS counter in the game shows that the overlay is attached).' -Level VERBOSE
        }
    }
} catch {
    Write-Log $_.Exception.Message -Level ERROR
    exit 1
} finally {
    if ($Trace) { Set-PSDebug -Off }
    Write-Log "Log: $logFile"
}
