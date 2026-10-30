<#
.SYNOPSIS
    Runs one stage of the trudlcport conversion pipeline (Python tools in the clone) with full logging.

.DESCRIPTION
    Each -Step runs one or more tools from the trudlcport clone root with the project venv
    (..\bin\venv\Scripts\python.exe -u -I -X utf8 tools\<tool>.py ...). Output is shown live and written to
    <workspace>\logs\Invoke-TruPipeline_<step>_<time>.log; at the end a summary with duration and exit codes is printed.
    The tools only read the game / Xbox data (via <workspace>\data junctions) and write below work\ of the repository.

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
      Prep     generic_type0 save07 (type 0/7 tables), pc_vers_build (our reconstruction), model_point_fix learn +
               selftest, dtpid_evidence (rule inputs of Convert's --extra-fixes, learned from base pairs only)
               -> type0_table.pkl, type7_table.pkl, pc_vers.json, pc_vers_content.json,
                  work\chain_aim\model_point_rules.pkl, work\generic\dtpid_evidence.pkl
      Convert  dlc_convert_all --media --write --extra-fixes -> work\generic\out\pack10|pack11\*.drm
      Names    dlc_names (file names of unnamed DLC records) -> work\generic\dlc_names.txt (can run any time after Ids)
      Media    dlc_media_build (our reconstruction: DLC 1 tree in the B138 layout), locals build, padshock build,
               compare_b138 -> work\rebuild\stage1\mods + work\rebuild\compare_stage1.json
      Audio    dlc_audio_build (our glue: wave_swap for all DRMs incl. sub folders, mul_audio_batch), compare_b138
               -> work\rebuild\stage2a\mods (replaced on every run) + compare_stage2a.json
      Assemble upstream's full stage-1 route (optional, after Media): render tables (render_tables_build build,
               rend_extract pairs/dlc, shader_map, material_rules, material_dlc, pc_shader_sections,
               terrain_validate, mesh_tables_build), dlc_assemble_build (assemble_dlc, material 'dlc', PC shader sections),
               dlc_audio_build, compare_b138, compare_sections
               -> work\render\*, work\rebuild\asm_stage1\mods, asm_stage2a\mods (+ compare_asm_stage2a.json)
      Dlc2     DLC 2 (pack11) stage 1 + 2a, after Assemble (needs its render tables): dlc_media_build pack11,
               dlc_assemble_build --pack pack11, dlc_audio_build --pack pack11, tree_check (no reference build)
               -> work\rebuild\dlc2_stage1\mods, dlc2_asm_stage1\mods, dlc2_asm_stage2a\mods (the input of Fixes)
      Fixes    stage 2b: dlc_fixes_build for DLC 1 (asm_stage2a -> asm_stage2b, compare_b138) and DLC 2
               (dlc2_asm_stage2a -> dlc2_asm_stage2b, --pack pack11); cloth / uipath / uitext were found in DLC 2,
               uipath / uitext also change 10 DLC 1 level files (since 2026-10-30)
      Repair   the repair tree for an installed B138 (finding 43, tested in game 2026-10-30): b138_snapshot (pristine
               B138 mods, verified against the kit manifest, from the game folder and the Install-TruTree backups),
               b138_fix_tree (shader constant fix, grapple ring shaders, DLC 1 UI paths / texts, cinematic languages
               of both DLCs)
               -> work\rebuild\b138_pristine\mods, work\rebuild\b138_fixes\mods (install with Install-TruTree.ps1)

    Aborting: a step can be stopped between tools without loss (each tool writes its output when it finishes);
    a tool stopped midway has to run again. -FromTool N resumes a step at its N-th tool (numbers as shown in the
    progress bar, "tool N/M").

    Progress: a progress bar (Write-Progress) shows the running tool and its time; steps with a known number of
    output files (Convert: 300 DRM files) also show percent and an estimate. Every 30 s a "still running" line is
    written to the console and the log.

    Processes: the heavy converters (dlc_convert_all, ~18 GB RAM each) run -Jobs processes, the light tools
    (audio, comparisons) -LightJobs. 0 = automatic: Jobs = (free RAM - 8 GB) / 18 GB, between 1 and 3;
    LightJobs = logical CPUs - 4, at most 24 (cores left for other work). Passed as TRUDLC_JOBS / TRUDLC_JOBS_LIGHT.

    -Verbose shows steps, -Debug the command lines, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Cache -Verbose
.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Tables -FromTool 5 -Verbose
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Index', 'Cache', 'Ids', 'Learn', 'Tables', 'Prep', 'Convert', 'Names', 'Media', 'Audio', 'Assemble', 'Dlc2', 'Fixes', 'Repair')][string]$Step,
    [ValidateRange(1, 99)][int]$FromTool = 1,
    [ValidateRange(0, 16)][int]$Jobs = 0,
    [ValidateRange(0, 64)][int]$LightJobs = 0,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths  = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root   = $paths.Workspace
$clone  = $paths.Repository
$python = Join-Path $root 'bin\venv\Scripts\python.exe'
$logDir = $paths.Logs

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
        @('tools\pc_vers_build.py'),
        @('tools\model_point_fix.py', 'learn'),
        @('tools\model_point_fix.py', 'selftest'),
        @('tools\dtpid_evidence.py')
    )
    # leading comma: a step with a single tool must stay a list of argument lists (PowerShell unrolls @(@(...)))
    Convert = @(
        , @('tools\dlc_convert_all.py', '--media', '--write', '--extra-fixes')
    )
    Names = @(
        , @('tools\dlc_names.py')
    )
    Media = @(
        @('tools\dlc_media_build.py', 'work/rebuild/stage1/mods', 'pack10'),
        @('tools\locals.py', 'build', 'work/rebuild/stage1'),
        @('tools\padshock_convert.py', 'build', 'work/rebuild/stage1/mods'),
        @('tools\compare_b138.py', 'work/rebuild/stage1/mods', 'stage1'),
        @('tools\compare_sections.py', 'work/rebuild/stage1/mods', 'stage1')
    )
    Audio = @(
        @('tools\dlc_audio_build.py', 'work/rebuild/stage1/mods', 'work/rebuild/stage2a/mods'),
        @('tools\compare_b138.py', 'work/rebuild/stage2a/mods', 'stage2a'),
        @('tools\compare_sections.py', 'work/rebuild/stage2a/mods', 'stage2a')
    )
    Assemble = @(
        @('tools\render_tables_build.py', 'build'),
        @('tools\rend_extract.py', 'pairs'),
        @('tools\render_tables_build.py', 'check'),
        @('tools\rend_extract.py', 'dlc'),
        @('tools\shader_map.py'),
        @('tools\material_rules.py'),
        @('tools\material_dlc.py'),
        @('tools\pc_shader_sections.py'),
        @('tools\terrain_validate.py'),
        @('tools\mesh_tables_build.py'),
        @('tools\dlc_assemble_build.py', 'work/rebuild/stage1/mods', 'work/rebuild/asm_stage1/mods'),
        @('tools\dlc_audio_build.py', 'work/rebuild/asm_stage1/mods', 'work/rebuild/asm_stage2a/mods'),
        @('tools\compare_b138.py', 'work/rebuild/asm_stage2a/mods', 'asm_stage2a'),
        @('tools\compare_sections.py', 'work/rebuild/asm_stage2a/mods', 'asm_stage2a')
    )
    Dlc2 = @(
        @('tools\dlc_media_build.py', 'work/rebuild/dlc2_stage1/mods', 'pack11'),
        @('tools\dlc_assemble_build.py', 'work/rebuild/dlc2_stage1/mods', 'work/rebuild/dlc2_asm_stage1/mods', '--pack', 'pack11'),
        @('tools\dlc_audio_build.py', 'work/rebuild/dlc2_asm_stage1/mods', 'work/rebuild/dlc2_asm_stage2a/mods', '--pack', 'pack11'),
        @('tools\tree_check.py', 'work/rebuild/dlc2_asm_stage2a/mods', 'dlc2_asm_stage2a')
    )
    Fixes = @(
        @('tools\dlc_fixes_build.py', 'work/rebuild/asm_stage2a/mods', 'work/rebuild/asm_stage2b/mods'),
        @('tools\compare_b138.py', 'work/rebuild/asm_stage2b/mods', 'asm_stage2b'),
        @('tools\dlc_fixes_build.py', 'work/rebuild/dlc2_asm_stage2a/mods', 'work/rebuild/dlc2_asm_stage2b/mods', '--pack', 'pack11')
    )
    Repair = @(
        @('tools\b138_snapshot.py', '../release/B138/kit/manifest.json', '../data/pc/mods', '../backup', 'work/rebuild/b138_pristine/mods', '../backup/mods', 'work/rebuild/base_b138'),
        @('tools\b138_fix_tree.py', 'work/rebuild/b138_pristine/mods', 'work/rebuild/b138_fixes/mods', '--dlc2', '--replace')
    )
}
$outputDirs = @{
    Index   = @('work')
    Cache   = @('work\generic')
    Ids     = @('work\generic', 'work\generic\merged')
    Learn   = @('work\generic', 'work\script')
    Tables  = @('work\generic', 'work\script')
    Prep    = @('work\generic', 'work\chain_aim')
    Convert = @('work\generic\out')
    Names   = @('work\generic')
    Media   = @('work\rebuild')
    Audio   = @('work\rebuild')
    Assemble = @('work\render', 'work\rebuild')
    Dlc2    = @('work\rebuild')
    Fixes   = @('work\rebuild')
    Repair  = @('work\rebuild')
}
# steps whose progress can be measured by counting output files
$progressHints = @{
    # 307 pack records, 300 distinct file names (7 duplicate records write the same file again)
    Convert = @{ Dir = 'work\generic\out'; Filter = '*.drm'; Total = 300 }
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Invoke-TruPipeline_{0}_{1}.log' -f $Step, (Get-Date -Format 'yyyyMMdd_HHmmss'))
Set-TruLogFile -Path $logFile

function Get-ProgressCount {
    # number of output files written since the tool started (older files from a previous run do not count),
    # for steps with a known total (see $progressHints)
    param([datetime]$Since)
    $hint = $progressHints[$Step]
    if (!$hint) { return $null }
    $dir = Join-Path $clone $hint.Dir
    if (!(Test-Path -LiteralPath $dir)) { return 0 }
    return @(Get-ChildItem -LiteralPath $dir -Recurse -File -Filter $hint.Filter -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $Since }).Count
}

function Invoke-Tool {
    param([string[]]$ToolArgs, [string]$Label)
    # -X utf8: with -I Python ignores PYTHONIOENCODING and would write cp1252 to the pipe; any character outside
    # cp1252 in a tool's output (e.g. game text, an arrow) would then raise UnicodeEncodeError
    $allArgs = @('-u', '-I', '-X', 'utf8') + $ToolArgs
    $argLine = ($allArgs | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    Write-Log "python $argLine" -Level DEBUG

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = $argLine
    $psi.WorkingDirectory = $clone
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $process = [System.Diagnostics.Process]::Start($psi)
    $script:runningProcess = $process    # for the finally block: report it if the run is aborted while it runs

    # read stdout and stderr line by line without blocking; heartbeat every 30 s
    $outTask = $process.StandardOutput.ReadLineAsync()
    $errTask = $process.StandardError.ReadLineAsync()
    $t0 = Get-Date
    $nextBeat = $t0.AddSeconds(30)
    $nextCount = $t0
    $count = $null
    $hint = $progressHints[$Step]
    while ($outTask -or $errTask) {
        $idle = $true
        if ($outTask -and $outTask.IsCompleted) {
            $line = $outTask.Result
            if ($null -eq $line) { $outTask = $null } else { Write-Log $line; $outTask = $process.StandardOutput.ReadLineAsync(); $idle = $false }
        }
        if ($errTask -and $errTask.IsCompleted) {
            $line = $errTask.Result
            if ($null -eq $line) { $errTask = $null } else { Write-Log ('stderr: ' + $line); $errTask = $process.StandardError.ReadLineAsync(); $idle = $false }
        }
        $now = Get-Date
        $elapsed = $now - $t0
        $status = '{0}  running {1:hh\:mm\:ss}' -f $Label, $elapsed
        if ($now -ge $nextCount) { $count = Get-ProgressCount -Since $t0; $nextCount = $now.AddSeconds(5) }
        if ($null -ne $count -and $hint.Total -gt 0) {
            $percent = [Math]::Min(99, [int](100 * $count / $hint.Total))
            $remaining = if ($count -gt 0) { [int]($elapsed.TotalSeconds * ($hint.Total - $count) / $count) } else { -1 }
            Write-Progress -Activity "Invoke-TruPipeline $Step" -Status ('{0}  {1}/{2} files' -f $status, $count, $hint.Total) -PercentComplete $percent -SecondsRemaining $remaining
        } else {
            Write-Progress -Activity "Invoke-TruPipeline $Step" -Status $status
        }
        if ($now -ge $nextBeat) {
            $beat = if ($null -ne $count) { '{0} / {1} files' -f $count, $hint.Total } else { 'no output yet' }
            Write-Log ('... still running: {0}, {1:hh\:mm\:ss}, {2}' -f $Label, $elapsed, $beat)
            $nextBeat = $now.AddSeconds(30)
        }
        if ($idle) { Start-Sleep -Milliseconds 250 }
    }
    $process.WaitForExit()
    $script:runningProcess = $null
    Write-Progress -Activity "Invoke-TruPipeline $Step" -Completed
    return $process.ExitCode
}

if ($Trace) { Set-PSDebug -Trace 1 }
$results = @()
$started = Get-Date
$script:runningProcess = $null
$savedEnv = @{}
Push-Location $clone
try {
    Write-Log "Invoke-TruPipeline step=$Step log=$logFile" -Level VERBOSE
    if (!(Test-Path -LiteralPath $python)) { throw "Python venv not found: $python (see README, Entwicklungsumgebung)." }
    Write-Log "Python: $((& $python --version 2>&1) -join ' ')" -Level DEBUG
    # audio conversion: prefer the ffmpeg from <workspace>\bin (Get-Tools.ps1), else the tools find one on PATH
    $ffmpeg = Join-Path $root 'bin\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe'
    if (Test-Path -LiteralPath $ffmpeg) { $env:TRUDLC_FFMPEG = $ffmpeg }
    Write-Log "ffmpeg: $(if ($env:TRUDLC_FFMPEG) { $env:TRUDLC_FFMPEG } else { 'from PATH' })" -Level DEBUG
    # process counts (docs/WINDOWS_REBUILD.md finding 36: one converter process needs ~18 GB, light tools < 20 MB)
    $freeGb = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB)
    $cpus = [int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    if ($Jobs -eq 0) { $Jobs = [Math]::Max(1, [Math]::Min(3, [int][Math]::Floor(($freeGb - 8) / 18))) }
    if ($LightJobs -eq 0) { $LightJobs = [Math]::Max(1, [Math]::Min(24, $cpus - 4)) }
    $env:TRUDLC_JOBS = $Jobs
    $env:TRUDLC_JOBS_LIGHT = $LightJobs
    # DLC selection and string id map come from the step's own arguments (--pack pack11), never from the calling
    # shell: a TRUDLC_PACK_FIRST left over from a manual DLC 2 run would switch DLC 1 to DLC-2-only fixes
    foreach ($name in 'TRUDLC_PACK_FIRST', 'TRUDLC_LOCMAP') {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ($value) {
            $savedEnv[$name] = $value
            Write-Log "ignoring $name=$value from the calling shell for this run" -Level VERBOSE
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        }
    }
    Write-Log ('processes: heavy {0}, light {1} (free RAM {2} GB, {3} logical CPUs)' -f $Jobs, $LightJobs, $freeGb, $cpus) -Level VERBOSE
    foreach ($dir in $outputDirs[$Step]) { New-Item -ItemType Directory -Force -Path (Join-Path $clone $dir) | Out-Null }

    $toolCount = @($steps[$Step]).Count
    $toolIndex = 0
    foreach ($toolArgs in $steps[$Step]) {
        $toolIndex++
        if ($toolIndex -lt $FromTool) {
            Write-Log ('== skipped (FromTool {0}): {1}' -f $FromTool, ($toolArgs -join ' ')) -Level VERBOSE
            continue
        }
        $t0 = Get-Date
        $label = 'tool {0}/{1} {2}' -f $toolIndex, $toolCount, (Split-Path -Leaf $toolArgs[0])
        Write-Log ('== ' + ($toolArgs -join ' ')) -Level VERBOSE
        $code = Invoke-Tool -ToolArgs $toolArgs -Label $label
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
    foreach ($name in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnv[$name], 'Process') }
    # aborted (Ctrl+C, error) while a tool was running: the tool and its worker processes keep running (they were
    # started without a console). Nothing is ended automatically - the PIDs are logged so the user can decide.
    if ($script:runningProcess -and !$script:runningProcess.HasExited) {
        $toolPid = $script:runningProcess.Id
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$toolPid" -ErrorAction SilentlyContinue |
            ForEach-Object { $_.ProcessId })
        Write-Log ('Tool still running after the abort: PID {0}, worker PIDs: {1}. Not ended - end them yourself if needed.' -f
            $toolPid, $(if ($children.Count) { $children -join ', ' } else { 'none' })) -Level WARN
    }
    Write-Log '--- summary ---'
    foreach ($r in $results) { Write-Log ('{0,-40} exit {1}  {2} s' -f $r.Tool, $r.ExitCode, $r.Seconds) }
    foreach ($dir in $outputDirs[$Step]) {
        Get-ChildItem -LiteralPath (Join-Path $clone $dir) -File -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Log ('{0,-40} {1,14} bytes' -f "$dir\$($_.Name)", $_.Length) }
    }
    # plain integers: N0 uses the culture's group separator ("3.097 s" on German systems)
    Write-Log ('total {0} s' -f [int]((Get-Date) - $started).TotalSeconds)
    Write-Host "Log: $logFile"
}
