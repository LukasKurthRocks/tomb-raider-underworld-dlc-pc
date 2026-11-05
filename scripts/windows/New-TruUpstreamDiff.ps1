<#
.SYNOPSIS
    Writes docs/UPSTREAM_DIFF.md: what this branch has that upstream main does not (changed upstream files with the
    reason, converter fault families, names, new parts). Changes nothing else.

.DESCRIPTION
    Base = git merge-base of the upstream ref (default origin/main) and HEAD, so the report stays right after every
    upstream merge. Generated from git:
      * section 1: every file that exists at the base and differs at HEAD, with its kind and note from
        docs/data/upstream_diff_notes.tsv (path TAB kind TAB note) and the number of non-merge commits since the base,
      * section 4: files added since the base, grouped (plugins, Windows scripts, test profiles, tools, docs).
    Hand-written and inserted unchanged: docs/data/upstream_diff_curated.md (sections 2 and 3).
    -Check writes nothing and lists changed upstream files without a note and notes for files that are no longer
    changed (exit 1 if any). Log: <workspace>\logs\New-TruUpstreamDiff_<time>.log. -Verbose lists every file,
    -Debug the git calls, -Trace a PowerShell line trace.

.PARAMETER Upstream
    Upstream ref (default origin/main; fetch it first: git fetch origin).
.PARAMETER Check
    Only check the notes against the diff; write nothing.
.PARAMETER Trace
    PowerShell line trace (Set-PSDebug -Trace 1).

.EXAMPLE
    .\scripts\windows\New-TruUpstreamDiff.ps1 -Check
.EXAMPLE
    .\scripts\windows\New-TruUpstreamDiff.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$Upstream = 'origin/main',
    [switch]$Check,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$repo = $paths.Repository
if (!(Test-Path -LiteralPath $paths.Logs)) { New-Item -ItemType Directory -Force -Path $paths.Logs | Out-Null }
Set-TruLogFile -Path (Join-Path $paths.Logs ('New-TruUpstreamDiff_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss')))
$notesFile = Join-Path $repo 'docs\data\upstream_diff_notes.tsv'
$curatedFile = Join-Path $repo 'docs\data\upstream_diff_curated.md'
$outFile = Join-Path $repo 'docs\UPSTREAM_DIFF.md'

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    Write-Log ('git {0}' -f ($GitArgs -join ' ')) -Level DEBUG
    $out = & git -C $repo @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) { throw ('git {0} failed: {1}' -f ($GitArgs -join ' '), ($out -join ' ')) }
    # the comma keeps a one-line result an array (otherwise [0] would be its first character)
    return , @($out | ForEach-Object { [string]$_ })
}

function Get-ScriptSynopsis([string]$Path) {
    # first sentence of .SYNOPSIS (it may wrap over several lines) of a PowerShell script's comment-based help
    $lines = @(Get-Content -LiteralPath $Path -TotalCount 25 -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count - 1; $i++) {
        if ($lines[$i].Trim() -ne '.SYNOPSIS') { continue }
        $parts = @()
        for ($j = $i + 1; $j -lt $lines.Count; $j++) {
            $l = $lines[$j].Trim()
            if (!$l -or $l.StartsWith('.') -or $l.StartsWith('#>')) { break }
            $parts += $l
        }
        $text = $parts -join ' '
        $m = [regex]::Match($text, '^(?:e\.g\.|i\.e\.|.)*?\.(?=\s|$)')
        return $(if ($m.Success) { $m.Value } else { $text })
    }
    return ''
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    $base = (Invoke-Git merge-base $Upstream HEAD)[0].Trim()
    $baseInfo = (Invoke-Git log -1 '--format=%h %cs' $base)[0]
    $headInfo = (Invoke-Git log -1 '--format=%h %cs' HEAD)[0]
    $branch = (Invoke-Git rev-parse --abbrev-ref HEAD)[0]
    Write-Log "upstream $Upstream, merge base $baseInfo, HEAD $headInfo ($branch)"

    $changed = New-Object System.Collections.Generic.List[string]
    $added = New-Object System.Collections.Generic.List[string]
    foreach ($line in (Invoke-Git diff --no-renames --name-status $base HEAD)) {
        $parts = $line -split "`t"
        if ($parts.Count -lt 2) { continue }
        switch -Regex ($parts[0]) {
            '^M' { $changed.Add($parts[1]) }
            '^A' { $added.Add($parts[1]) }
            '^D' { $changed.Add($parts[1]) }
        }
    }
    Write-Log "changed upstream files $($changed.Count), added files $($added.Count)"

    # notes: path TAB kind TAB note
    $notes = [ordered]@{}
    foreach ($line in [IO.File]::ReadAllLines($notesFile, [Text.Encoding]::UTF8)) {
        if (!$line.Trim() -or $line.StartsWith('#')) { continue }
        $p = $line -split "`t"
        if ($p.Count -lt 3) { throw "upstream_diff_notes.tsv: bad line '$line'" }
        $notes[$p[0]] = [pscustomobject]@{ Kind = $p[1]; Note = $p[2] }
    }
    $missing = @($changed | Where-Object { !$notes.Contains($_) })
    $stale = @($notes.Keys | Where-Object { $changed -notcontains $_ })
    foreach ($m in $missing) { Write-Log "no note: $m" -Level WARN }
    foreach ($s in $stale) { Write-Log "note for a file that is not changed (any more): $s" -Level WARN }
    if ($Check) {
        Write-Log ('check: {0} changed upstream files, {1} without note, {2} stale notes' -f $changed.Count, $missing.Count, $stale.Count)
        if ($missing.Count -or $stale.Count) { exit 1 }
        return
    }

    $nl = "`n"
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('# What branch `windows` adds to upstream `main`' + $nl + $nl)
    [void]$sb.Append('<!-- Generated by scripts/windows/New-TruUpstreamDiff.ps1 - do not edit here: notes in docs/data/upstream_diff_notes.tsv, sections 2-3 in docs/data/upstream_diff_curated.md -->' + $nl + $nl)
    [void]$sb.Append(('This page lists only what this fork has that the original project''s `main` does not, for anyone who wants to pick something up. Base: upstream `main` at the merge base {0}; this branch at {1}. Dates and history: [CHANGELOG.md](../CHANGELOG.md).' -f ('`' + $baseInfo.Split(' ')[0] + '` (' + $baseInfo.Split(' ')[1] + ')'), ('`' + $headInfo.Split(' ')[0] + '` (' + $headInfo.Split(' ')[1] + ')')) + $nl + $nl)

    # section 1
    [void]$sb.Append('## 1. Upstream files changed in this fork' + $nl + $nl)
    [void]$sb.Append('Kinds: **fix** = changes a result, **extension** = adds something without changing old results, **windows** = runs on Windows (paths, tools).' + $nl + $nl)
    [void]$sb.Append('| File | Kind | Commits | Why |' + $nl + '|---|---|---|---|' + $nl)
    $order = @{ 'fix' = 0; 'extension' = 1; 'windows' = 2 }
    $rows = foreach ($f in $changed) {
        $n = $notes[$f]
        $kind = if ($n) { $n.Kind } else { '?' }
        $note = if ($n) { $n.Note } else { '(no note yet)' }
        $commits = Invoke-Git log --no-merges '--format=%h' "$base..HEAD" -- $f
        $count = @($commits | Where-Object { $_ }).Count
        Write-Log "$f : $kind, $count commit(s)" -Level VERBOSE
        [pscustomobject]@{ File = $f; Kind = $kind; Count = $count; Note = $note; Order = $(if ($order.ContainsKey($kind)) { $order[$kind] } else { 9 }) }
    }
    $rel = { param($f) if ($f.StartsWith('docs/')) { $f.Substring(5) } else { '../' + $f } }
    foreach ($r in @($rows | Sort-Object Order, File)) {
        [void]$sb.Append(('| [`{0}`]({1}) | {2} | {3} | {4} |' -f $r.File, (& $rel $r.File), $r.Kind, $r.Count, $r.Note) + $nl)
    }
    [void]$sb.Append($nl)

    # sections 2-3 (hand-written)
    $curated = [IO.File]::ReadAllText($curatedFile, [Text.Encoding]::UTF8) -replace "`r`n", "`n"
    [void]$sb.Append($curated.TrimEnd() + $nl + $nl)

    # section 4
    [void]$sb.Append('## 4. New parts' + $nl + $nl)
    $plugins = @($added | Where-Object { $_ -match '^src/asi/([^/]+)/' -and $Matches[1] -ne 'third_party' } | ForEach-Object { ($_ -split '/')[2] } | Sort-Object -Unique)
    $scripts = @($added | Where-Object { $_ -match '^scripts/windows/[^/]+\.ps1$' } | Sort-Object)
    $profiles = @($added | Where-Object { $_ -match '^tests/' })
    $tools = @($added | Where-Object { $_ -match '^tools/[^/]+\.py$' } | Sort-Object)
    $docs = @($added | Where-Object { $_ -match '^docs/[^/]+\.md$' -and $_ -ne 'docs/UPSTREAM_DIFF.md' } | Sort-Object)
    $other = @($added | Where-Object { $_ -notmatch '^(src/asi/|scripts/windows/|tests/|tools/[^/]+\.py$|docs/[^/]+\.md$)' } | Sort-Object)
    [void]$sb.Append(('- **Plugins (ASI, loaded by ModLoader)** ({0}): {1}. The title update''s exe code (shadow power, combat, rock veins, DLC 2 player) translated into small add-ons, plus test helpers; each has its own README.' -f $plugins.Count, (($plugins | ForEach-Object { '[`{0}`](../src/asi/{0}/)' -f $_ }) -join ', ')) + $nl)
    [void]$sb.Append(('- **Windows scripts** ({0}) in [scripts/windows/](../scripts/windows/README.md):' -f $scripts.Count) + $nl)
    foreach ($s in $scripts) {
        $syn = Get-ScriptSynopsis (Join-Path $repo ($s -replace '/', '\'))
        [void]$sb.Append(('  - `{0}`{1}' -f (Split-Path -Leaf $s), $(if ($syn) { ' - ' + $syn } else { '' })) + $nl)
    }
    [void]$sb.Append(('- **Test profiles** ({0} files) in `tests/`: what a test run installs and checks (`Invoke-TruTestRun.ps1`).' -f $profiles.Count) + $nl)
    [void]$sb.Append(('- **Docs** ({0}): {1}' -f $docs.Count, (($docs | ForEach-Object { '[{0}]({0})' -f (Split-Path -Leaf $_) }) -join ', ')) + $nl)
    [void]$sb.Append(('- **Tools** ({0} new Python tools in `tools/`):' -f $tools.Count) + $nl + $nl)
    [void]$sb.Append('<details><summary>List of the new tools</summary>' + $nl + $nl)
    foreach ($t in $tools) { [void]$sb.Append(('`{0}` ' -f (Split-Path -Leaf $t))) }
    [void]$sb.Append($nl + $nl + '</details>' + $nl + $nl)
    if ($other.Count) {
        [void]$sb.Append(('- **Other added files** ({0}): {1}' -f $other.Count, (($other | ForEach-Object { '`' + $_ + '`' }) -join ', ')) + $nl)
    }

    $text = $sb.ToString()
    [IO.File]::WriteAllText($outFile, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Log ('written {0} ({1} bytes): section 1 {2} files ({3} without note), plugins {4}, scripts {5}, profiles {6}, tools {7}, docs {8}, other {9}' -f $outFile, (Get-Item -LiteralPath $outFile).Length, $changed.Count, $missing.Count, $plugins.Count, $scripts.Count, $profiles.Count, $tools.Count, $docs.Count, $other.Count)
}
finally {
    if ($Trace) { Set-PSDebug -Off }
}
