<#
.SYNOPSIS
    Switches Tomb Raider: Underworld between windowed and fullscreen mode (registry, current user).

.DESCRIPTION
    -Windowed   Fullscreen=0, LockWindowSize=1, LockedWindowWidth/Height = -Width/-Height (default 1600x900).
    -Fullscreen Fullscreen=1 (window values are left as they are).
    -Restore    Re-imports the first backup .reg from .\backup (state before this script ever ran).

    Before any change the key is exported to .\backup\TRU-Graphics_<time>.reg.
    Every run writes .\logs\Set-TruDisplay_<time>.log. -Verbose shows steps, -Debug the values before/after,
    -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Set-TruDisplay.ps1 -Windowed -Verbose
#>
[CmdletBinding(DefaultParameterSetName = 'Windowed')]
param(
    [Parameter(ParameterSetName = 'Windowed')][switch]$Windowed,
    [Parameter(ParameterSetName = 'Windowed')][int]$Width = 1600,
    [Parameter(ParameterSetName = 'Windowed')][int]$Height = 900,
    [Parameter(ParameterSetName = 'Fullscreen', Mandatory)][switch]$Fullscreen,
    [Parameter(ParameterSetName = 'Restore', Mandatory)][switch]$Restore,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }

$root      = $PSScriptRoot
$regPath   = 'HKCU:\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics'
$regNative = 'HKCU\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics'
$backupDir = Join-Path $root 'backup'
$logDir    = Join-Path $root 'logs'
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
$valueNames = 'Fullscreen', 'LockWindowSize', 'LockWindowResolution', 'LockWindowAspect', 'LockedWindowWidth', 'LockedWindowHeight', 'EnableVSync', 'AdapterID'

New-Item -ItemType Directory -Force -Path $logDir, $backupDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruDisplay_{0}_{1}.log' -f $stamp, $PSCmdlet.ParameterSetName)

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

function Write-Values {
    param([string]$Label)
    $props = Get-ItemProperty -LiteralPath $regPath
    Write-Log "Values ($Label):" -Level VERBOSE
    foreach ($name in $valueNames) {
        Write-Log ('  {0,-22} = {1}' -f $name, $props.$name) -Level DEBUG
    }
}

function Invoke-Reg {
    param([string[]]$RegArgs)
    Write-Log ('reg.exe ' + ($RegArgs -join ' ')) -Level DEBUG
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & reg.exe @RegArgs 2>&1 | ForEach-Object { Write-Log ([string]$_) -Level VERBOSE }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) { throw "reg.exe $($RegArgs[0]) failed (exit code $code)." }
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruDisplay mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) {
        throw 'Tomb Raider: Underworld is running; it would overwrite the settings on exit. Please close it first.'
    }
    if (-not (Test-Path -LiteralPath $regPath)) { throw "Registry key not found: $regNative (start the game once first)." }

    if ($Restore) {
        $first = Get-ChildItem -LiteralPath $backupDir -Filter 'TRU-Graphics_*.reg' | Sort-Object Name | Select-Object -First 1
        if (-not $first) { throw "No TRU-Graphics_*.reg backup in $backupDir." }
        Write-Values 'before restore'
        Invoke-Reg @('import', $first.FullName)
        Write-Values 'after restore'
        Write-Log "Restored from $($first.Name)."
        return
    }

    Write-Values 'before'
    $backupFile = Join-Path $backupDir "TRU-Graphics_$stamp.reg"
    Invoke-Reg @('export', $regNative, $backupFile, '/y')
    Write-Log "Backup: $backupFile" -Level VERBOSE

    if ($Fullscreen) {
        Set-ItemProperty -LiteralPath $regPath -Name 'Fullscreen' -Value 1 -Type DWord
        Write-Values 'after'
        Write-Log 'Fullscreen mode set.'
        return
    }

    Set-ItemProperty -LiteralPath $regPath -Name 'Fullscreen' -Value 0 -Type DWord
    Set-ItemProperty -LiteralPath $regPath -Name 'LockWindowSize' -Value 1 -Type DWord
    Set-ItemProperty -LiteralPath $regPath -Name 'LockedWindowWidth' -Value $Width -Type DWord
    Set-ItemProperty -LiteralPath $regPath -Name 'LockedWindowHeight' -Value $Height -Type DWord
    Write-Values 'after'
    Write-Log "Windowed mode set ($Width x $Height)."
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
