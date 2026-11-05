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
               -> work\idx_pc.json (bigfile + patch.000), idx_xbox_base.json (layers + TU), idx_dlc.json (pack10/11 and,
               since 2026-11-03, the costume packs pack1/2/20 after them)
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
               uipath / uitext also change 10 DLC 1 level files (since 2026-10-30); statechart (2026-10-31) re-converts
               the state charts of the new DLC objects (DLC 2 player chart: needs the title-update memory image);
               twins / childids / translist / actlist / condlist / eventlist / reclist / fadeslots / animfx / markup /
               vmliteral (2026-11-01/02) apply the structure layouts proven on the base pairs
               (tools/dlc_struct_fixes.py, tests 47 / 48 / 48c-48m; twins ~20 min);
               objtex / objrec / objid (2026-11-04, after markup, findings 47 / 48) set the object data DTP faults:
               texture group counts (F16 machine room), particle record byte classes (F3 / B24) and the player data
               breath-sound ids (doppelganger_casual 0x68f40000); dlc_struct_fixes check runs on each output tree
               (exit 1 on a word left, report <tree>\objdata_check.json);
               seqrepeat (2026-11-05, after objid, finding 49) sets the SoundPlex Sequence word +0xc (repeat byte +
               3 bytes) to the Xbox bytes (the converter u32-swapped repeat 1 to 0 = endless: DLC 2 doppelganger groan,
               DLC 1 dlc_caverns_hall / dlc_dungeonhallb); the step first proves the rule on the base pairs
               (soundplex_sequence_fix proof: exit 1 when a pair contradicts it or a count differs) and gates each
               output tree afterwards (soundplex_sequence_fix scan: exit 1 on a wrong or unexplained word, report
               <tree>\soundplex_sequence_check.json; dlc_struct_fixes check covers seqrepeat too);
               objevent / idword / animlist / fxnode / statevm / chartid (2026-11-03, finding 44) set the converter
               fault families that crash dumps of tests 50d-50j uncovered (tools/converter_faults_fix.py: event list
               words and sub-0x32 ids, anim event list words, effect node headers / type-1 ids, state-VM code words,
               state-chart id values); the step first proves every rule on the base pair (converter_faults_fix proof)
               and checks each output tree afterwards (converter_faults_fix check: exit 1 on any wrong or unexpected
               word, report <tree>\converter_faults_check.json);
               achievement (2026-10-31) drops the 11 script calls into the title update's achievement natives
               f16-f20 that the PC exe lacks (1 in DLC 1, 10 in DLC 2);
               scriptclash (2026-11-04, last, finding 46) gives DLC script classes re-authored under the id of an
               always-resident PC generalbank script with another instance layout their own PC id (rule in
               tools/script_clash_fix.py, ids in docs/data/script_clash_ids.json: DLC 2 thrall base 12433 -> 26884,
               16 DRMs; DLC 1: nothing); script_clash_fix check runs on each output tree (exit 1 on a clash left,
               report <tree>\script_clash_check.json).
               -FixesOut DIR (relative to the repository) writes DIR\dlc1\mods and DIR\dlc2\mods instead of
               work\rebuild\asm_stage2b and dlc2_asm_stage2b (check runs that must not replace the usual outputs)
      Costumes the three Xbox costume packs (2026-11-03; pack1 Wetsuit k / p, pack2 Classic a / h, pack20 Designer
               l / m), after Assemble (render tables) and Fixes' proof: verify_ids extend (adds the packs' ids to
               dlc_idmap.json, existing entries never change; second run adds nothing), converter_faults_fix proof,
               soundplex_sequence_fix proof (2026-11-05), then per pack the DLC 2 route: dlc_media_build,
               dlc_assemble_build --pack, dlc_audio_build --pack, tree_check, dlc_fixes_build --pack,
               converter_faults_fix check --pack, script_clash_fix check, dlc_struct_fixes check --pack (objtex / objrec
               / objid / seqrepeat), soundplex_sequence_fix scan --pack
               -> work\rebuild\costumes\<pack>\{stage1,asm_stage1,asm_stage2a,stage2b}\mods (-FixesOut DIR: DIR\<pack>\...)
               Only the two dlc_costume_<x>.drm of each pack are new for the game; images, names and lists are in
               the DLC 1 tree already (docs/COSTUMES.md)
               Needs the render tables WITH the costume packs (Index since 2026-11-03, then Assemble's rend_extract dlc /
               shader_map (shaderlibs.pkl moved away first) / material_dlc / pc_shader_sections); otherwise assemble
               passes the packs' materials through as Xbox bytes (media_error). Proven 2026-11-03: the extended tables
               leave DLC 1 / DLC 2 assemble byte-identical (tools/render_tables_compare.py tables / tree).
               About 75-90 min per costume DRM: their DTPs are larger than every Xbox base record (no pc_copy /
               template, route 'convert'; tools/costume_pack_check.py xids)
      Repair   the repair tree for an installed B138 (finding 43, tested in game 2026-10-30): b138_snapshot (pristine
               B138 mods, verified against the kit manifest, from the game folder and the Install-TruTree backups),
               generalbank_build (see Generalbank), b138_fix_tree (shader constant fix, grapple ring shaders, DLC 1 UI
               paths / texts, DLC 1 state charts, DLC 1 structure fixes (anim event lists of the costumes, pillar
               markup; step struct), the DLC 1 achievement call, cinematic languages of both DLCs, our generalbank.drm)
               -> work\rebuild\b138_pristine\mods, work\rebuild\b138_fixes\mods (install with Install-TruTree.ps1)
      Generalbank  our generalbank.drm alone (after Repair's snapshot): B138's + mission screen style + the title
               update's loading screen (script 6, DLC titles) and hint box (script 10 -> 9), 21 steps with the
               existing tools, two of them load the generic store (~16 GB RAM, one after the other); step 21 is
               compared with the played test 38 file (MD5); step 22 (2026-11-04) appends the title update's 6 input
               bindings of Lara's set 17 (tools/input_map_tu_fix.py: RB / X / Y / LB for the DLC 2 shadow combat)
               -> work\rebuild\generalbank_build\mods\generalbank.drm; input_map_tu_fix --verify checks the result
               (also in Repair, on b138_fixes), report <dir>\input_map_check.json; step 23 (2026-11-05, S104):
               mission screen script 104 starts DLC 2 like the title update, without costume / weapon selection
               (tools/dlc2_player_fix.py gb; result = dlc_test50l_input, md5 66efd71d...), gate
               dlc2_player_fix verify (every changed word explained), report <dir>\script104_check.json
               -FixesOut DIR (2026-11-04, check runs): Generalbank writes DIR\generalbank_build; Repair writes
               DIR\b138_pristine\mods, DIR\generalbank_build (--base = that snapshot's generalbank.drm) and
               DIR\b138_fixes\mods instead of the usual work\rebuild\b138_pristine / generalbank_build / b138_fixes

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
.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Fixes -FixesOut work/rebuild/pipeline_check_0311 -Verbose
.EXAMPLE
    .\Invoke-TruPipeline.ps1 -Step Costumes -FixesOut work/rebuild/costumes_0311 -Jobs 1 -Verbose
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Index', 'Cache', 'Ids', 'Learn', 'Tables', 'Prep', 'Convert', 'Names', 'Media', 'Audio', 'Assemble', 'Dlc2', 'Fixes', 'Costumes', 'Repair', 'Generalbank')][string]$Step,
    [ValidateRange(1, 99)][int]$FromTool = 1,
    [ValidateRange(0, 16)][int]$Jobs = 0,
    [ValidateRange(0, 64)][int]$LightJobs = 0,
    # steps Fixes / Costumes / Generalbank / Repair: output folder below the repository instead of work/rebuild/asm_stage2b + dlc2_asm_stage2b
    # (Costumes: work/rebuild/costumes; Generalbank / Repair: work/rebuild/generalbank_build, b138_pristine, b138_fixes)
    # (one folder directly below work/rebuild; never a test tree dlc_test*)
    [ValidatePattern('^work[\\/]rebuild[\\/](?!dlc_test)[\w\-\.]+[\\/]?$')][string]$FixesOut,
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
# outputs of step Fixes (-FixesOut: a separate check folder, the usual trees stay untouched)
if ($FixesOut) {
    $fixRoot = ($FixesOut -replace '\\', '/').TrimEnd('/')
    $fix1 = "$fixRoot/dlc1/mods"; $fix2 = "$fixRoot/dlc2/mods"
    $fixLabel = Split-Path -Leaf $fixRoot
    $cmp1 = "${fixLabel}_dlc1"
} else {
    $fix1 = 'work/rebuild/asm_stage2b/mods'; $fix2 = 'work/rebuild/dlc2_asm_stage2b/mods'
    $cmp1 = 'asm_stage2b'
}
$chk1 = (Split-Path -Parent $fix1) + '/converter_faults_check.json'
$chk2 = (Split-Path -Parent $fix2) + '/converter_faults_check.json'
$clash1 = (Split-Path -Parent $fix1) + '/script_clash_check.json'
$clash2 = (Split-Path -Parent $fix2) + '/script_clash_check.json'
$obj1 = (Split-Path -Parent $fix1) + '/objdata_check.json'
$obj2 = (Split-Path -Parent $fix2) + '/objdata_check.json'
$seq1 = (Split-Path -Parent $fix1) + '/soundplex_sequence_check.json'
$seq2 = (Split-Path -Parent $fix2) + '/soundplex_sequence_check.json'
$gbOut = 'work/rebuild/generalbank_build'
$repPristine = 'work/rebuild/b138_pristine/mods'
$repFixes = 'work/rebuild/b138_fixes/mods'
$gbBase = @()
if ($FixesOut) {
    # steps Generalbank / Repair as check runs: every output below -FixesOut, the usual trees stay untouched
    $gbOut = "$fixRoot/generalbank_build"
    $repPristine = "$fixRoot/b138_pristine/mods"
    $repFixes = "$fixRoot/b138_fixes/mods"
    # Repair: generalbank_build reads its base from this run's own snapshot (its default is work/rebuild/b138_pristine)
    if ($Step -eq 'Repair') { $gbBase = @('--base', "$repPristine/generalbank.drm") }
}
# step Costumes: one chain per costume pack (the DLC 2 route), below work/rebuild/costumes or -FixesOut
$costRoot = if ($FixesOut) { $fixRoot } else { 'work/rebuild/costumes' }
$costumeTools = @(
    @('tools\verify_ids.py', 'extend'),
    @('tools\converter_faults_fix.py', 'proof'),
    @('tools\soundplex_sequence_fix.py', 'proof')
)
foreach ($pk in 'pack1', 'pack2', 'pack20') {
    $o = "$costRoot/$pk"
    $costumeTools += , @('tools\dlc_media_build.py', "$o/stage1/mods", $pk)
    $costumeTools += , @('tools\dlc_assemble_build.py', "$o/stage1/mods", "$o/asm_stage1/mods", '--pack', $pk)
    $costumeTools += , @('tools\dlc_audio_build.py', "$o/asm_stage1/mods", "$o/asm_stage2a/mods", '--pack', $pk)
    $costumeTools += , @('tools\tree_check.py', "$o/asm_stage2a/mods", ('{0}_{1}' -f (Split-Path -Leaf $costRoot), $pk))
    $costumeTools += , @('tools\dlc_fixes_build.py', "$o/asm_stage2a/mods", "$o/stage2b/mods", '--pack', $pk)
    $costumeTools += , @('tools\converter_faults_fix.py', 'check', "$o/stage2b/mods", '--pack', $pk, '--report', "$o/converter_faults_check.json")
    $costumeTools += , @('tools\script_clash_fix.py', 'check', "$o/stage2b/mods", '--report', "$o/script_clash_check.json")
    $costumeTools += , @('tools\dlc_struct_fixes.py', 'check', "$o/stage2b/mods", '--pack', $pk, '--report', "$o/objdata_check.json")
    $costumeTools += , @('tools\soundplex_sequence_fix.py', 'scan', "$o/stage2b/mods", '--pack', $pk, '--report', "$o/soundplex_sequence_check.json")
}
$steps = @{
    Index = @(
        @('tools\index_all.py', 'work/idx_pc.json', 'le', "../data/pc/bigfile.000$align", "../data/pc/patch.000$align"),
        @('tools\index_all.py', 'work/idx_xbox_base.json', 'be', "../data/TombRaiderUnderworld_Patched/layer1.000$align",
          "../data/TombRaiderUnderworld_Patched/layer2.000$align", "../data/TombRaiderUnderworld_Patched/TitleUpdate.000$align"),
        # costume packs last (2026-11-03): the first record of a section id wins in the render tables, so pack10 / pack11
        # keep every entry they had (tools/render_tables_compare.py index / tables)
        @('tools\index_all.py', 'work/idx_dlc.json', 'be', "$dlc/9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000$align",
          "$dlc/600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000$align",
          "$dlc/E5AFB2B959A72C52120D73678AED11BD8752686753/pack1.000$align",
          "$dlc/9FDDD06617D1016DE468ACF53AC663E8BA2AD41853/pack2.000$align",
          "$dlc/AC0089F81B621CD0E0C156B6176EFCC6C844705D53/pack20.000$align")
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
        # shader_map reads work\render\shaderlibs.pkl as a cache when it exists: after a new rend_extract (pairs / dlc)
        # move that file away first, else the libraries / materials of the new index are missing from all DLC tables
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
        @('tools\converter_faults_fix.py', 'proof'),
        @('tools\soundplex_sequence_fix.py', 'proof'),
        @('tools\dlc_fixes_build.py', 'work/rebuild/asm_stage2a/mods', $fix1),
        @('tools\converter_faults_fix.py', 'check', $fix1, '--report', $chk1),
        @('tools\script_clash_fix.py', 'check', $fix1, '--report', $clash1),
        @('tools\dlc_struct_fixes.py', 'check', $fix1, '--report', $obj1),
        # DLC 1 = pack10 first, the same Xbox sources as dlc_fixes_build without --pack
        @('tools\soundplex_sequence_fix.py', 'scan', $fix1, '--pack', 'pack10', '--report', $seq1),
        @('tools\compare_b138.py', $fix1, $cmp1),
        @('tools\dlc_fixes_build.py', 'work/rebuild/dlc2_asm_stage2a/mods', $fix2, '--pack', 'pack11'),
        @('tools\converter_faults_fix.py', 'check', $fix2, '--pack', 'pack11', '--report', $chk2),
        @('tools\script_clash_fix.py', 'check', $fix2, '--report', $clash2),
        @('tools\dlc_struct_fixes.py', 'check', $fix2, '--pack', 'pack11', '--report', $obj2),
        @('tools\soundplex_sequence_fix.py', 'scan', $fix2, '--pack', 'pack11', '--report', $seq2)
    )
    Costumes = $costumeTools
    Repair = @(
        @('tools\b138_snapshot.py', '../release/B138/kit/manifest.json', '../data/pc/mods', '../backup', $repPristine, '../backup/mods', 'work/rebuild/base_b138'),
        (@('tools\generalbank_build.py', $gbOut) + $gbBase),
        @('tools\input_map_tu_fix.py', '--verify', "$gbOut/mods/generalbank.drm", '--report', "$gbOut/input_map_check.json"),
        @('tools\b138_fix_tree.py', $repPristine, $repFixes, '--dlc2', '--replace', '--generalbank', "$gbOut/mods/generalbank.drm"),
        @('tools\input_map_tu_fix.py', '--verify', "$repFixes/generalbank.drm", '--report', ((Split-Path -Parent $repFixes) + '/input_map_check.json'))
    )
    Generalbank = @(
        @('tools\generalbank_build.py', $gbOut),
        @('tools\input_map_tu_fix.py', '--verify', "$gbOut/mods/generalbank.drm", '--report', "$gbOut/input_map_check.json"),
        # gate S104 (2026-11-05): the result = step 22 + exactly the script 104 fix of step 23, block = TU script 134 test
        @('tools\dlc2_player_fix.py', 'verify', "$gbOut/steps/22_input.drm", "$gbOut/mods/generalbank.drm", '--tu', "$gbOut/steps/10_tu_be.drm", '--report', "$gbOut/script104_check.json")
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
    Costumes = @('work\rebuild')
    Repair  = @('work\rebuild')
    Generalbank = @('work\rebuild')
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
