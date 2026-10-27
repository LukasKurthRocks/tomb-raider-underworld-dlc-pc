<#
.SYNOPSIS
    Runs one stage of the trudlcport conversion pipeline (Python tools in the clone) with full logging.

.DESCRIPTION
    Each -Step runs one or more tools from the trudlcport clone root with the project venv
    (..\bin\venv\Scripts\python.exe -u -I tools\<tool>.py ...). Output is shown live and written to
    .\logs\Invoke-TruPipeline_<step>_<time>.log; at the end a summary with duration and exit codes is printed.
    The tools only read the game / Xbox data (via .\data junctions) and write below trudlcport\work\.

    Steps (in order):
      Index    tools\index_all.py (3x)        which DRM sits where, with section lists
               -> work\idx_pc.json (bigfile + patch.000), idx_xbox_base.json (layers + TU), idx_dlc.json (pack10/11)
      Cache    tools\generic_cache.py        pair the base-game DRMs Xbox <-> PC  -> work\generic\pairs.pkl
               tools\generic_cache.py patch   runtime pairs (Xbox TU / PC patch.000) -> work\generic\pairs_patch.pkl
      Ids      generic_store, generic_ids, objlists_extract (our reconstruction), objlist_merge
               -> store.pkl, idmap.json, merged\ (object lists + remap)
      Learn    generic_learn save, generic_symbols seed, script_pairs, unit_ids (needs script\pairs_8.pkl)
               -> mask_table.pkl, symbols in idmap.json, script\pairs_*.pkl, unit_idmaps.json   (about 26 min)
      Tables   dlc_drms_build (our reconstruction), dlc_generic (provisional dlc_idmap.json, script_learn needs it),
               script_learn save, generic_type0 save07, script_name_match, tex_idmap (both rewrite idmap.json),
               dlc_generic again (final dlc_idmap.json on the final base id map)
      Prep     generic_type0 save07 (type 0/7 tables), pc_vers_build (our reconstruction)
               -> type0_table.pkl, type7_table.pkl, pc_vers.json, pc_vers_content.json
      Convert  dlc_convert_all --media --write   -> work\generic\out\ (first converted DLC DRMs + self checks)

    -Verbose shows steps, -Debug the command lines, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Cache -Verbose
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Index', 'Cache', 'Ids', 'Learn', 'Tables', 'Prep', 'Convert')][string]$Step,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }

$root   = $PSScriptRoot
$clone  = Join-Path $root 'trudlcport'
$python = Join-Path $root 'bin\venv\Scripts\python.exe'
$logDir = Join-Path $root 'logs'

$align = '@7ff00000'          # bigfile part size (tools/archive.py ALIGN)
$dlc   = '../data/Xenia-SteveRepack/Content/534307EC/00000002'
$steps = @{
    Index = @(
        @('tools\index_all.py', 'work/idx_pc.json', 'le', "../data/pc/bigfile.000$align", "../data/pc/patch.000$align"),
        @('tools\index_all.py', 'work/idx_xbox_base.json', 'be', "../data/TombRaiderUnderworld_Patched/layer1.000$align",
          "../data/TombRaiderUnderworld_Patched/layer2.000$align", "../data/TombRaiderUnderworld_Patched/TitleUpdate.000$align"),
        @('tools\index_all.py', 'work/idx_dlc.json', 'be', "$dlc/9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000$align",
          "$dlc/600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000$align")
    )
    Cache = @(
        @('tools\generic_cache.py'),
        @('tools\generic_cache.py', 'patch')
    )
    Ids = @(
        @('tools\generic_store.py'),
        @('tools\generic_ids.py'),
        @('tools\objlists_extract.py'),
        @('tools\objlist_merge.py')
    )
    Learn = @(
        @('tools\generic_learn.py', 'save'),
        @('tools\generic_symbols.py', 'seed'),
        @('tools\script_pairs.py'),
        @('tools\unit_ids.py')
    )
    Tables = @(
        @('tools\dlc_drms_build.py'),
        @('tools\dlc_generic.py'),
        @('tools\script_learn.py', 'save'),
        @('tools\generic_type0.py', 'save07'),
        @('tools\script_name_match.py'),
        @('tools\tex_idmap.py'),
        @('tools\dlc_generic.py')
    )
    Prep = @(
        @('tools\generic_type0.py', 'save07'),
        @('tools\pc_vers_build.py')
    )
    Convert = @(
        @('tools\dlc_convert_all.py', '--media', '--write')
    )
}
$outputDirs = @{
    Index   = @('work')
    Cache   = @('work\generic')
    Ids     = @('work\generic', 'work\generic\merged')
    Learn   = @('work\generic', 'work\script')
    Tables  = @('work\generic', 'work\script')
    Prep    = @('work\generic')
    Convert = @('work\generic\out')
}

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
