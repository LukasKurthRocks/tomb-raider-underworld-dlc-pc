<#
.SYNOPSIS
    Read-only report of the stacked tree installs (backup\tree_*): what each open install wrote, which install
    "owns" each changed mods file now, whether every -Restore would pass its checks, and what the mods files would
    be after undoing the open installs. Changes nothing.

.DESCRIPTION
    Reads every open <workspace>\backup\tree_* (not *.restored) manifest written by Install-TruTree.ps1 and
    <workspace>\runs\installed-state.json (the trees of the previous Invoke-TruTestRun run), then:
      * per install: time, source tree, added / replaced counts, harness run or not, whether every saved file in
        <backup>\files still has the MD5 its manifest records (Install-TruTree -Restore aborts on a mismatch),
        and the later open installs that touch the same files,
      * per mods file touched by an open install: the installed MD5 (game folder), the owner (newest open install
        that touched it), whether the installed file still equals the owner's source file (a different MD5 means
        a later single-file install, a rebuilt source or an out-of-order restore), and the chain check (the backup
        of each later install should equal the source of the install below it),
      * simulation: the MD5 of each file after undoing all open installs except the -KeepOldest oldest ones,
        newest first (= one Install-TruTree -Restore per install, or Invoke-TruTestRun -Undo for the harness
        trees), compared with reference trees (-Reference) and known generalbank builds.
    Nothing is copied, renamed or deleted; the only file written is <workspace>\logs\Get-TruTreeStack_<time>.log.
    INFO lines give the summary tables, -Verbose adds the per-file table, -Debug paths and hashes, -Trace a
    PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found via the Steam libraries.
.PARAMETER KeepOldest
    Number of the oldest open installs the simulation keeps (default 0 = undo all open installs). Installs stack:
    only the oldest ones can stay, Install-TruTree -Restore always undoes the newest open install first.
.PARAMETER Reference
    Mods trees (relative to the workspace or absolute) the simulated result is compared with.
.PARAMETER Trace
    PowerShell line trace (Set-PSDebug -Trace 1).

.EXAMPLE
    .\scripts\windows\Get-TruTreeStack.ps1
.EXAMPLE
    .\scripts\windows\Get-TruTreeStack.ps1 -KeepOldest 1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$GamePath,
    [ValidateRange(0, 1000)][int]$KeepOldest = 0,
    [string[]]$Reference = @('trudlcport\work\rebuild\b138_pristine\mods', 'trudlcport\work\rebuild\play_20261030b\mods',
                             'trudlcport\work\rebuild\b138_fixes\mods'),
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, Find-TruGamePath, Get-Md5
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$workspace = $paths.Workspace
$backupDir = Join-Path $workspace 'backup'
$stateFile = Join-Path $workspace 'runs\installed-state.json'
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
if (!(Test-Path -LiteralPath $paths.Logs)) { New-Item -ItemType Directory -Force -Path $paths.Logs | Out-Null }
$logFile = Join-Path $paths.Logs ('Get-TruTreeStack_{0}.log' -f $stamp)
Set-TruLogFile -Path $logFile

# generalbank builds with a known meaning (docs/Testabend-Werkzeuge.md, TODO.md)
$known = @{
    'b57d8c482accab7afab59ee20bd8ccad' = 'generalbank 41e direct start (test only)'
    '3a2b9a1d7b689d13d73037d3b412ea5b' = 'generalbank 41e + script 104 fix (test only)'
    '57f5226610903c8b58a1d911d53fc65a' = 'generalbank pipeline (no direct start)'
    '586c37ad378691d534f0aab2cee3c439' = 'generalbank AutoStart (profile 50l/50n)'
    '5c6c468dd16327a275b2001e6a30da4e' = 'generalbank pipeline step 22 (TU input bindings, without script 104)'
    '66efd71d19aed26ec458cbb3f8f25421' = 'generalbank pipeline step 23 (+ script 104 S104) = AutoStart + TU input bindings (dlc_test50l_input)'
    '2ff716288e69a6ba8baca595f9c6f354' = 'generalbank pipeline + HUD (dlc_test50l_hud_input)'
    '3fe0a2842dc5ad8443accd99a1151950' = 'generalbank pipeline + pause port (dlc_test50l_pause_input)'
    '219fdf16e7bdf6ee236eea6ae6397ebb' = 'generalbank pipeline + HUD + pause port (dlc_test50l_hud_pause_input)'
    'ce29c75231e4cbe3ea84ed882d3a737a' = 'generalbank DLC menu fix 27.10. (Install-TruModFile)'
}

function Get-TreeLabel([string]$Source) {
    # ...\work\rebuild\<name>\mods -> <name>; other layouts: the last two folders
    $leaf = Split-Path -Leaf $Source
    $parent = Split-Path -Leaf (Split-Path -Parent $Source)
    if ($leaf -eq 'mods') { return $parent }
    return "$parent\$leaf"
}

function Format-Time([string]$Stamp) {
    $t = [datetime]::ParseExact($Stamp, 'yyyyMMdd_HHmmss', [Globalization.CultureInfo]::InvariantCulture)
    return $t.ToString('yyyy-MM-dd HH:mm:ss')
}

$md5Cache = @{}
function Get-CachedMd5([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    if (!$md5Cache.ContainsKey($Path)) {
        $md5Cache[$Path] = Get-Md5 $Path
        Write-Log "md5 $($md5Cache[$Path]) $Path" -Level DEBUG
    }
    return $md5Cache[$Path]
}

function Get-Short([string]$Md5) { if ($Md5) { return $Md5.Substring(0, 8) } return 'absent' }

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Get-TruTreeStack keepOldest=$KeepOldest log=$logFile (read-only)" -Level VERBOSE
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'mods'))) { throw "Game folder with mods\ not found: $GamePath" }
    $mods = Join-Path $GamePath 'mods'
    Write-Log "Game folder: $GamePath" -Level VERBOSE

    $harness = @()
    if (Test-Path -LiteralPath $stateFile) {
        $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $harness = @(@($state.trees) | Where-Object { $_ })
        Write-Log "Harness state: run $($state.run) ($($state.time)), trees $($harness -join ', ')" -Level VERBOSE
    }

    $dirs = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' | Where-Object { $_.Name -notlike '*.restored' } | Sort-Object Name)
    $restoredCount = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*.restored').Count
    $trees = New-Object System.Collections.Generic.List[object]
    foreach ($d in $dirs) {
        $m = Get-Content -LiteralPath (Join-Path $d.FullName 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $added = @(@($m.added) | Where-Object { $_ })
        $replaced = @(@($m.replaced) | Where-Object { $_ })
        $bad = 0
        foreach ($r in $replaced) {
            $saved = Join-Path $d.FullName "files\$($r.path)"
            $h = Get-CachedMd5 $saved
            if ($h -ne $r.md5) { $bad++; Write-Log "backup mismatch: $($d.Name) files\$($r.path) is $(Get-Short $h), manifest $(Get-Short $r.md5)" -Level WARN }
        }
        $trees.Add([pscustomobject]@{
            Name = $d.Name; Time = (Format-Time $m.time); Source = [string]$m.source; Label = (Get-TreeLabel ([string]$m.source))
            SourceExists = (Test-Path -LiteralPath ([string]$m.source)); Added = $added; Replaced = $replaced
            Paths = @($added + @($replaced | ForEach-Object { $_.path })); Harness = ($harness -contains $d.Name); BackupBad = $bad
        })
    }
    Write-Log ('{0} open tree install(s), {1} undone (*.restored).' -f $trees.Count, $restoredCount)
    if ($KeepOldest -gt $trees.Count) { throw "-KeepOldest $KeepOldest is more than the $($trees.Count) open installs." }

    # ---- per install ----
    Write-Log ''
    Write-Log '| # | Tree (backup) | Installed | Source tree | added | replaced | harness | backups ok | later open installs on the same files |'
    Write-Log '|---|---|---|---|---|---|---|---|---|'
    for ($i = 0; $i -lt $trees.Count; $i++) {
        $t = $trees[$i]
        $over = New-Object System.Collections.Generic.List[string]
        for ($j = $i + 1; $j -lt $trees.Count; $j++) {
            $n = @($trees[$j].Paths | Where-Object { $t.Paths -contains $_ }).Count
            if ($n) { $over.Add(('{0} ({1})' -f $trees[$j].Label, $n)) }
        }
        $src = if ($t.SourceExists) { $t.Label } else { "$($t.Label) (source gone)" }
        Write-Log ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f ($i + 1), $t.Name, $t.Time, $src, $t.Added.Count,
            $t.Replaced.Count, $(if ($t.Harness) { 'yes' } else { 'no' }),
            $(if ($t.BackupBad) { "NO ($($t.BackupBad) mismatch)" } else { "yes ($($t.Replaced.Count))" }),
            $(if ($over.Count) { $over -join ', ' } else { '-' }))
    }

    # ---- per file ----
    $allPaths = @($trees | ForEach-Object { $_.Paths } | Sort-Object -Unique)
    $refs = @()
    foreach ($r in $Reference) {
        $p = if ([IO.Path]::IsPathRooted($r)) { $r } else { Join-Path $workspace $r }
        if (Test-Path -LiteralPath $p) { $refs += [pscustomobject]@{ Label = (Get-TreeLabel $p); Path = $p } }
        else { Write-Log "Reference tree not found: $p" -Level WARN }
    }
    $restoreFrom = $KeepOldest           # trees[$KeepOldest..] are undone in the simulation
    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($path in $allPaths) {
        $touch = @(for ($i = 0; $i -lt $trees.Count; $i++) { if ($trees[$i].Paths -contains $path) { $i } })
        $game = Get-CachedMd5 (Join-Path $mods $path)
        $owner = $trees[$touch[-1]]
        $ownerSrc = Get-CachedMd5 (Join-Path $owner.Source $path)
        # chain: the backup of each later install should equal the source of the install below it
        $breaks = New-Object System.Collections.Generic.List[string]
        for ($k = 1; $k -lt $touch.Count; $k++) {
            $lower = $trees[$touch[$k - 1]]; $upper = $trees[$touch[$k]]
            $rep = @($upper.Replaced | Where-Object { $_.path -eq $path })
            $was = if ($rep.Count) { $rep[0].md5 } else { $null }
            $lowerSrc = Get-CachedMd5 (Join-Path $lower.Source $path)
            if ($was -ne $lowerSrc) { $breaks.Add(('{0} saved {1}, {2} source now {3}' -f $upper.Label, (Get-Short $was), $lower.Label, (Get-Short $lowerSrc))) }
        }
        # simulation: undo trees[$restoreFrom..] newest first; the last undo that touches the file decides
        $final = $game; $finalBy = 'unchanged'
        for ($i = $trees.Count - 1; $i -ge $restoreFrom; $i--) {
            $t = $trees[$i]
            if ($t.Added -contains $path) { $final = $null; $finalBy = "removed by undo of $($t.Label)" }
            else {
                $rep = @($t.Replaced | Where-Object { $_.path -eq $path })
                if ($rep.Count) { $final = $rep[0].md5; $finalBy = "backup of $($t.Label)" }
            }
        }
        $finalLabel = if (!$final) { 'absent' } elseif ($known.ContainsKey($final)) { $known[$final] } else {
            $hit = @($refs | Where-Object { (Get-CachedMd5 (Join-Path $_.Path $path)) -eq $final } | ForEach-Object { $_.Label })
            if ($hit.Count) { '= ' + ($hit -join ' = ') } else { 'other' }
        }
        $rows.Add([pscustomobject]@{
            Path = $path; Game = $game; Owner = $owner.Label; OwnerMatches = ($game -eq $ownerSrc); Touch = @($touch | ForEach-Object { $trees[$_].Label })
            Breaks = $breaks; Final = $final; FinalBy = $finalBy; FinalLabel = $finalLabel
        })
    }

    Write-Log ''
    Write-Log ('{0} mods file(s) touched by open installs. Owner = newest open install that wrote the file:' -f $rows.Count)
    Write-Log '| Owner (newest open install) | files | installed = owner source | differs |'
    Write-Log '|---|---|---|---|'
    foreach ($g in ($rows | Group-Object Owner | Sort-Object Name)) {
        $ok = @($g.Group | Where-Object { $_.OwnerMatches }).Count
        Write-Log ('| {0} | {1} | {2} | {3} |' -f $g.Name, $g.Count, $ok, ($g.Count - $ok))
    }

    Write-Log ''
    Write-Log 'Files touched by more than one open install, or not equal to their owner source, or with a chain break:'
    Write-Log '| File | installed | owner | = owner source | touched by (old -> new) | chain | after the simulated undo |'
    Write-Log '|---|---|---|---|---|---|---|'
    foreach ($r in $rows) {
        $line = ('| {0} | {1}{2} | {3} | {4} | {5} | {6} | {7} {8} ({9}) |' -f $r.Path, (Get-Short $r.Game),
            $(if ($r.Game -and $known.ContainsKey($r.Game)) { " = $($known[$r.Game])" } else { '' }), $r.Owner,
            $(if ($r.OwnerMatches) { 'yes' } else { 'NO' }), ($r.Touch -join ' -> '),
            $(if ($r.Breaks.Count) { 'BREAK: ' + ($r.Breaks -join '; ') } else { 'ok' }), (Get-Short $r.Final), $r.FinalLabel, $r.FinalBy)
        if ($r.Touch.Count -gt 1 -or !$r.OwnerMatches -or $r.Breaks.Count) { Write-Log $line } else { Write-Log $line -Level VERBOSE }
    }

    Write-Log ''
    $undone = @($trees | Select-Object -Skip $KeepOldest | ForEach-Object { $_.Label })
    [array]::Reverse($undone)
    $kept = @($trees | Select-Object -First $KeepOldest | ForEach-Object { $_.Label })
    Write-Log ('Simulation: undo {0} install(s) newest first ({1}); kept: {2}' -f $undone.Count, ($undone -join ', '), $(if ($kept.Count) { $kept -join ', ' } else { 'none' }))
    Write-Log '| Result after the simulated undo | files |'
    Write-Log '|---|---|'
    foreach ($g in ($rows | Group-Object FinalLabel | Sort-Object Name)) { Write-Log ('| {0} | {1} |' -f $g.Name, $g.Count) }
    $gb = @($rows | Where-Object { $_.Path -eq 'generalbank.drm' })
    if ($gb.Count) {
        Write-Log ('generalbank.drm: now {0} ({1}), after the simulated undo {2} ({3}, {4})' -f (Get-Short $gb[0].Game),
            $(if ($known.ContainsKey([string]$gb[0].Game)) { $known[$gb[0].Game] } else { 'unknown build' }), (Get-Short $gb[0].Final), $gb[0].FinalLabel, $gb[0].FinalBy)
    }
    # ---- mods files outside every open install: equal to a reference tree, different, or unknown ----
    Write-Log ''
    $inManifest = @{}
    foreach ($p in $allPaths) { $inManifest[$p.ToLowerInvariant()] = $true }
    $extra = New-Object System.Collections.Generic.List[object]
    foreach ($f in (Get-ChildItem -LiteralPath $mods -Recurse -File)) {
        $rel = $f.FullName.Substring($mods.Length).TrimStart('\')
        if ($inManifest.ContainsKey($rel.ToLowerInvariant())) { continue }
        $top = ($rel -split '\\')[0]
        $withPath = @($refs | Where-Object { Test-Path -LiteralPath (Join-Path $_.Path $rel) -PathType Leaf })
        if (!$withPath.Count) { $extra.Add([pscustomobject]@{ Path = $rel; Class = 'in no open install and no reference tree'; Top = $top }); continue }
        $h = Get-CachedMd5 $f.FullName
        $hit = @($withPath | Where-Object { (Get-CachedMd5 (Join-Path $_.Path $rel)) -eq $h } | ForEach-Object { $_.Label })
        $class = if ($hit.Count) { '= ' + ($hit -join ' = ') } else { 'differs from ' + (($withPath | ForEach-Object { $_.Label }) -join ', ') }
        $extra.Add([pscustomobject]@{ Path = $rel; Class = $class; Top = $top; Md5 = $h })
    }
    Write-Log ('{0} mods file(s) outside the open installs (local\ and padshock\ are excluded from trees, set by Install-TruModFile):' -f $extra.Count)
    Write-Log '| Class | files |'
    Write-Log '|---|---|'
    foreach ($g in ($extra | Group-Object Class | Sort-Object Name)) { Write-Log ('| {0} | {1} |' -f $g.Name, $g.Count) }
    foreach ($e in ($extra | Where-Object { $_.Class -notlike '= *' })) {
        Write-Log ('outside the open installs: mods\{0} ({1}{2})' -f $e.Path, $e.Class, $(if ($e.Md5) { ', md5 ' + (Get-Short $e.Md5) } else { '' })) -Level VERBOSE
    }

    $badTrees = @($trees | Where-Object { $_.BackupBad })
    $gone = @($trees | Where-Object { !$_.SourceExists })
    Write-Log ('Restore checks: {0} of {1} open installs have all backups intact; sources missing: {2}' -f ($trees.Count - $badTrees.Count), $trees.Count,
        $(if ($gone.Count) { ($gone | ForEach-Object { $_.Label }) -join ', ' } else { 'none' }))
    Write-Log "Log: $logFile"
}
catch {
    Write-Log "FAILED: $($_.Exception.Message)" -Level ERROR
    Write-Log ($_.ScriptStackTrace) -Level DEBUG
    throw
}
finally {
    if ($Trace) { Set-PSDebug -Off }
}
