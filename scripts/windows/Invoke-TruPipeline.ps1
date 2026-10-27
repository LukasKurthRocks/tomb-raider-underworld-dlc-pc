<#
.SYNOPSIS
    Runs one stage of the trudlcport conversion pipeline (Python tools in the clone) with full logging.

.DESCRIPTION
    Each -Step runs one or more tools from the trudlcport clone root with the project venv
    (..\bin\venv\Scripts\python.exe -u -I tools\<tool>.py ...). Output is shown live and written to
    .\logs\Invoke-TruPipeline_<step>_<time>.log; at the end a summary with duration and exit codes is printed.
    The tools only read the game / Xbox data (via .\data junctions) and write below trudlcport\work\.

    Steps (in order):
      Cache   tools\generic_cache.py         pair the base-game DRMs Xbox <-> PC  -> work\generic\pairs.pkl
              tools\generic_cache.py patch   runtime pairs (Xbox TU / PC patch.000) -> work\generic\pairs_patch.pkl

    -Verbose shows steps, -Debug the command lines, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Cache -Verbose
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Cache')][string]$Step,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }

$root   = $PSScriptRoot
$clone  = Join-Path $root 'trudlcport'
$python = Join-Path $root 'bin\venv\Scripts\python.exe'
$logDir = Join-Path $root 'logs'

$steps = @{
    Cache = @(
        @('tools\generic_cache.py'),
        @('tools\generic_cache.py', 'patch')
    )
}
$outputDirs = @{ Cache = @('work\generic') }

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Invoke-TruPipeline_{0}_{1}.log' -f $Step, (Get-Date -Format 'yyyyMMdd_HHmmss'))

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'VERBOSE', 'DEBUG', 'WARN', 'ERROR')][string]$Level = 'INFO'
    )
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'), $Level, $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    switch ($Level) {
        'INFO'    { Write-Host $Message }
        'VERBOSE' { Write-Verbose $Message }
        'DEBUG'   { Write-Debug $Message }
        'WARN'    { Write-Warning $Message }
        'ERROR'   { Write-Host $Message -ForegroundColor Red }
    }
}

function Invoke-Tool {
    param([string[]]$ToolArgs)
    Write-Log ('python -u -I ' + ($ToolArgs -join ' ')) -Level DEBUG
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $python -u -I @ToolArgs 2>&1 | ForEach-Object {
            $text = if ($_ -is [System.Management.Automation.ErrorRecord]) { 'stderr: ' + $_.Exception.Message } else { [string]$_ }
            Write-Log $text
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $code
}

if ($Trace) { Set-PSDebug -Trace 1 }
$results = @()
$started = Get-Date
Push-Location $clone
try {
    Write-Log "Invoke-TruPipeline step=$Step log=$logFile" -Level VERBOSE
    if (!(Test-Path -LiteralPath $python)) { throw "Python venv not found: $python (see README, Entwicklungsumgebung)." }
    Write-Log "Python: $((& $python --version 2>&1) -join ' ')" -Level DEBUG
    foreach ($dir in $outputDirs[$Step]) { New-Item -ItemType Directory -Force -Path (Join-Path $clone $dir) | Out-Null }

    foreach ($toolArgs in $steps[$Step]) {
        $t0 = Get-Date
        Write-Log ('== ' + ($toolArgs -join ' ')) -Level VERBOSE
        $code = Invoke-Tool $toolArgs
        $seconds = [int]((Get-Date) - $t0).TotalSeconds
        $results += [pscustomobject]@{ Tool = ($toolArgs -join ' '); ExitCode = $code; Seconds = $seconds }
        if ($code -ne 0) { throw "Tool failed (exit code $code): $($toolArgs -join ' ')" }
    }
}
catch {
    Write-Log "FAILED: $($_.Exception.Message)" -Level ERROR
    Write-Log ($_.ScriptStackTrace) -Level DEBUG
    throw
}
finally {
    Pop-Location
    if ($Trace) { Set-PSDebug -Off }
    Write-Log '--- summary ---'
    foreach ($r in $results) { Write-Log ('{0,-40} exit {1}  {2} s' -f $r.Tool, $r.ExitCode, $r.Seconds) }
    foreach ($dir in $outputDirs[$Step]) {
        Get-ChildItem -LiteralPath (Join-Path $clone $dir) -File -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Log ('{0,-40} {1,14:N0} bytes' -f "$dir\$($_.Name)", $_.Length) }
    }
    Write-Log ('total {0:N0} s' -f ((Get-Date) - $started).TotalSeconds)
    Write-Host "Log: $logFile"
}
