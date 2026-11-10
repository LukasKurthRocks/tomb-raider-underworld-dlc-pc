<#
.SYNOPSIS
    Records the memory use of the running game (tru.exe) to a CSV until the game exits (read-only).

.DESCRIPTION
    Samples the process every -IntervalSeconds: virtual size (address space - the 2 GB limit of a 32-bit process
    without the large-address-aware flag, 4 GB with it), its lifetime peak, private bytes and working set. Waits up to
    -WaitSeconds for tru.exe to appear. Changes nothing in the game or the process.
    Output: <workspace>\logs\mem_tru_<time>.csv (time;pid;virtualMB;peakVirtualMB;privateMB;workingSetMB) and a
    run log <workspace>\logs\Watch-TruMemory_<time>.log with the summary (maximum values and when they occurred).

.PARAMETER IntervalSeconds
    Seconds between two samples (default 15).

.PARAMETER WaitSeconds
    How long to wait for tru.exe to start (default 300).

.PARAMETER MaxSamples
    Stop after this many samples (0 = until the game exits; for tests).

.PARAMETER ProcessName
    Process to watch (default tru; for tests another process can be named).

.PARAMETER Trace
    Also print every sample to the console.

.EXAMPLE
    .\scripts\windows\Watch-TruMemory.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [int]$IntervalSeconds = 15,
    [int]$WaitSeconds = 300,
    [int]$MaxSamples = 0,
    [string]$ProcessName = 'tru',
    [switch]$Trace
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$workspace = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$logDir = Join-Path $workspace 'logs'
if (!(Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$csv = Join-Path $logDir "mem_${ProcessName}_$stamp.csv"
$log = Join-Path $logDir "Watch-TruMemory_$stamp.log"

function Write-Log([string]$Text) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
    Write-Verbose $line
}

Write-Log "start: process '$ProcessName', every $IntervalSeconds s, csv $csv"
Set-Content -LiteralPath $csv -Value 'time;pid;virtualMB;peakVirtualMB;privateMB;workingSetMB' -Encoding UTF8

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$proc = $null
while (!$proc) {
    $proc = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc) { break }
    if ((Get-Date) -gt $deadline) { Write-Log "no process '$ProcessName' within $WaitSeconds s - stop"; exit 1 }
    Start-Sleep -Seconds 2
}
Write-Log ('process found: pid {0}, started {1}' -f $proc.Id, $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))

$n = 0
$max = @{ virtual = 0; private = 0; ws = 0; peak = 0; tVirtual = ''; tPrivate = '' }
while ($true) {
    try { $proc.Refresh() } catch { break }
    if ($proc.HasExited) { break }
    $t = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $v = [math]::Round($proc.VirtualMemorySize64 / 1MB)
    $pv = [math]::Round($proc.PeakVirtualMemorySize64 / 1MB)
    $pr = [math]::Round($proc.PrivateMemorySize64 / 1MB)
    $ws = [math]::Round($proc.WorkingSet64 / 1MB)
    $row = '{0};{1};{2};{3};{4};{5}' -f $t, $proc.Id, $v, $pv, $pr, $ws
    Add-Content -LiteralPath $csv -Value $row -Encoding UTF8
    if ($Trace) { Write-Host $row }
    if ($v -gt $max.virtual) { $max.virtual = $v; $max.tVirtual = $t }
    if ($pr -gt $max.private) { $max.private = $pr; $max.tPrivate = $t }
    if ($ws -gt $max.ws) { $max.ws = $ws }
    if ($pv -gt $max.peak) { $max.peak = $pv }
    $n++
    if ($n -eq 1) { Write-Log "first sample: $row" }
    if ($MaxSamples -gt 0 -and $n -ge $MaxSamples) { break }
    Start-Sleep -Seconds $IntervalSeconds
}
Write-Log ('end after {0} samples: max virtual {1} MB at {2}; peak virtual (process lifetime) {3} MB; max private {4} MB at {5}; max working set {6} MB' -f $n, $max.virtual, $max.tVirtual, $max.peak, $max.private, $max.tPrivate, $max.ws)
Write-Log "csv: $csv"
exit 0
