<#
.SYNOPSIS
    Switches Tomb Raider: Underworld between windowed and fullscreen mode (registry, current user).

.DESCRIPTION
    -Windowed   Fullscreen=0, LockWindowSize=1, LockedWindowWidth/Height = -Width/-Height (default 1600x900).
    -Fullscreen Fullscreen=1 (window values are left as they are).
    -Restore    Re-imports the first backup .reg from <workspace>\backup (state before this script ever ran).
    -Language   Additionally sets the game language (registry value Language one level up):
                English=0, French=1, German=2, Italian=3, Spanish=4, Dutch=5 (order of the locals.bin_001..032
                language bits; all six verified in game).

    Before any change the key is exported to <workspace>\backup\TRU-Graphics_<time>.reg.
    Every run writes <workspace>\logs\Set-TruDisplay_<time>.log. -Verbose shows steps, -Debug the values before/after,
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
    [Parameter(ParameterSetName = 'Windowed')][Parameter(ParameterSetName = 'Fullscreen')]
    [ValidateSet('English', 'French', 'German', 'Italian', 'Spanish', 'Dutch')][string]$Language,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$regPath   = 'HKCU:\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics'
$regNative = 'HKCU\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics'
$rootPath  = 'HKCU:\Software\Crystal Dynamics\Tomb Raider: Underworld'
$rootNative = 'HKCU\Software\Crystal Dynamics\Tomb Raider: Underworld'
$languageIds = @{ English = 0; French = 1; German = 2; Italian = 3; Spanish = 4; Dutch = 5 }
$backupDir = Join-Path $root 'backup'
$logDir    = $paths.Logs
$stamp    = Get-Date -Format 'yyyyMMdd_HHmmss'
$valueNames = 'Fullscreen', 'LockWindowSize', 'LockWindowResolution', 'LockWindowAspect', 'LockedWindowWidth', 'LockedWindowHeight', 'EnableVSync', 'AdapterID'

New-Item -ItemType Directory -Force -Path $logDir, $backupDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruDisplay_{0}_{1}.log' -f $stamp, $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Write-Values {
    param([string]$Label)
    $props = Get-ItemProperty -LiteralPath $regPath
    Write-Log "Values ($Label):" -Level VERBOSE
    foreach ($name in $valueNames) {
        Write-Log ('  {0,-22} = {1}' -f $name, $props.$name) -Level DEBUG
    }
    $rootProps = Get-ItemProperty -LiteralPath $rootPath
    Write-Log ('  {0,-22} = {1}' -f 'Language', $rootProps.Language) -Level DEBUG
    Write-Log ('  {0,-22} = {1}' -f 'SubtitleLanguage', $rootProps.SubtitleLanguage) -Level DEBUG
}

function Set-GameLanguage {
    if (!$Language) { return }
    $id = $languageIds[$Language]
    Set-ItemProperty -LiteralPath $rootPath -Name 'Language' -Value $id -Type DWord
    Write-Log "Language set to $Language ($id)."
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
    if (!(Test-Path -LiteralPath $regPath)) { throw "Registry key not found: $regNative (start the game once first)." }

    if ($Restore) {
        $first = Get-ChildItem -LiteralPath $backupDir -Filter 'TRU-Graphics_*.reg' | Sort-Object Name | Select-Object -First 1
        if (!$first) { throw "No TRU-Graphics_*.reg backup in $backupDir." }
        Write-Values 'before restore'
        $firstRoot = Get-ChildItem -LiteralPath $backupDir -Filter 'TRU-Root_*.reg' | Sort-Object Name | Select-Object -First 1
        if ($firstRoot) {
            Invoke-Reg @('import', $firstRoot.FullName)
            Write-Log "Restored language values from $($firstRoot.Name)."
        }
        Invoke-Reg @('import', $first.FullName)
        Write-Values 'after restore'
        Write-Log "Restored from $($first.Name)."
        return
    }

    Write-Values 'before'
    $backupFile = Join-Path $backupDir "TRU-Graphics_$stamp.reg"
    Invoke-Reg @('export', $regNative, $backupFile, '/y')
    Write-Log "Backup: $backupFile" -Level VERBOSE
    if ($Language) {
        $rootBackup = Join-Path $backupDir "TRU-Root_$stamp.reg"
        Invoke-Reg @('export', $rootNative, $rootBackup, '/y')
        Write-Log "Backup: $rootBackup" -Level VERBOSE
    }
    Set-GameLanguage

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
