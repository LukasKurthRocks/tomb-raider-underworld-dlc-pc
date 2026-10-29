<#
.SYNOPSIS
    Samples the memory of running Python processes (read-only) to size parallel pipeline runs.

.DESCRIPTION
    Every -IntervalSeconds the private memory and working set of every process named -ProcessName are recorded
    together with its command line. Ends after -DurationMinutes, or with -UntilIdle as soon as no such process has
    been seen for 3 samples in a row. At the end a summary per tool (script name from the command line) lists the
    number of processes, the peak private memory of one process and the peak sum of all processes of that tool.
    Nothing is changed and no process is touched.

    Output: <workspace>\logs\Measure-TruProcessMemory_<time>.csv (all samples) and .log (summary).
    -Verbose shows every sample, -Debug the raw values, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\scripts\windows\Measure-TruProcessMemory.ps1 -DurationMinutes 120 -UntilIdle -Verbose
#>
[CmdletBinding()]
param(
    [int]$IntervalSeconds = 10,
    [int]$DurationMinutes = 120,
    [string]$ProcessName = 'python',
    [switch]$UntilIdle,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
if ($Trace) { Set-PSDebug -Trace 1 }

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$logDir  = $paths.Logs
$stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Measure-TruProcessMemory_{0}.log' -f $stamp)
$csvFile = Join-Path $logDir ('Measure-TruProcessMemory_{0}.csv' -f $stamp)
Set-TruLogFile -Path $logFile

function Get-ToolName {
    # the first argument that ends in .py (tools\x.py), else the executable name
    param([string]$CommandLine)
    if ($CommandLine -match '([\w\-]+\.py)') { return $Matches[1] }
    return '(no script)'
}

Write-Log ('sampling {0} every {1} s for up to {2} min, until idle: {3}' -f $ProcessName, $IntervalSeconds, $DurationMinutes, [bool]$UntilIdle)
'time,pid,start,tool,private_mb,workingset_mb,free_ram_mb' | Set-Content -LiteralPath $csvFile -Encoding UTF8
$end = (Get-Date).AddMinutes($DurationMinutes)
$idle = 0
$seen = $false
$peakOne = @{}; $peakSum = @{}; $pids = @{}
while ((Get-Date) -lt $end) {
    $now = Get-Date
    $free = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
    $procs = @(Get-CimInstance Win32_Process -Filter ("Name = '{0}.exe'" -f $ProcessName))
    $sum = @{}
    foreach ($p in $procs) {
        $gp = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        if (!$gp) { continue }
        $tool = Get-ToolName -CommandLine $p.CommandLine
        $priv = [int]($gp.PrivateMemorySize64 / 1MB); $ws = [int]($gp.WorkingSet64 / 1MB)
        ('{0:HH:mm:ss},{1},{2:HH:mm:ss},{3},{4},{5},{6}' -f $now, $p.ProcessId, $gp.StartTime, $tool, $priv, $ws, $free) |
            Add-Content -LiteralPath $csvFile -Encoding UTF8
        Write-Log ('{0,-28} pid {1,6} private {2,7} MB ws {3,7} MB' -f $tool, $p.ProcessId, $priv, $ws) -Level VERBOSE
        if (!$peakOne.ContainsKey($tool) -or $priv -gt $peakOne[$tool]) { $peakOne[$tool] = $priv }
        $sum[$tool] = [int]$sum[$tool] + $priv
        if (!$pids.ContainsKey($tool)) { $pids[$tool] = @{} }
        $pids[$tool][$p.ProcessId] = $true
    }
    foreach ($t in $sum.Keys) { if (!$peakSum.ContainsKey($t) -or $sum[$t] -gt $peakSum[$t]) { $peakSum[$t] = $sum[$t] } }
    Write-Log ('free RAM {0} MB, {1} processes' -f $free, $procs.Count) -Level DEBUG
    if ($procs.Count) { $seen = $true; $idle = 0 } else { $idle++ }
    if ($UntilIdle -and $seen -and $idle -ge 3) { Write-Log 'no process for 3 samples - stop'; break }
    Start-Sleep -Seconds $IntervalSeconds
}
Write-Log '--- summary (MB) ---'
Write-Log ('{0,-28} {1,9} {2,14} {3,14}' -f 'tool', 'processes', 'peak one', 'peak all')
foreach ($t in ($peakOne.Keys | Sort-Object)) {
    Write-Log ('{0,-28} {1,9} {2,14} {3,14}' -f $t, $pids[$t].Count, $peakOne[$t], $peakSum[$t])
}
if ($Trace) { Set-PSDebug -Off }
Write-Host "Log: $logFile"
Write-Host "CSV: $csvFile"
