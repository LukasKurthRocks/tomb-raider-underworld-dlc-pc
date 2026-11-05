<#
.SYNOPSIS
    Read-only check before a test evening: game folder, stacked trees, generalbank, the ASI / INI state a run
    profile expects, cdb, disk, RAM, save folder and a few registry settings. Changes nothing.

.DESCRIPTION
    Every check adds one row to a status table (ok / warn / fail / info, shown as check mark / warning / cross /
    info sign); the table goes to the console and to the per-run log <workspace>\logs\Test-TruPreflight_<time>.log
    (the only file this script writes). Nothing in the game folder, the save folder, the backups or the registry is
    changed; no process is started or ended.

    Checks:
      * tru.exe running (a run refuses to start while it runs - this script never ends it),
      * game folder: -GamePath or the Steam libraries (Find-TruGamePath, the same way Invoke-TruTestRun.ps1 and
        Install-TruTree.ps1 find it), tru.exe + mods\,
      * <workspace>\runs\installed-state.json (the previous harness run; Invoke-TruTestRun undoes it itself) and the
        open <workspace>\backup\tree_* installs (not *.restored): stacked trees are reported, never restored; a
        foreign tree newer than the harness trees makes the next run refuse (fail),
      * mods\generalbank.drm: the old direct-start test patch 41e (md5 b57d8c48...) or 41e + script 104 fix
        (3a2b9a1d...) = warn, the profile's generalbank = ok,
      * with -RunProfile, data checks of what the profile ends up installing (2026-11-05; last tree source of every
        .drm plus the game folder's mods\ for the files no tree brings - the folder as it stands, so trees still
        installed by an earlier run count as base): tools\objdata_texlist_check.py --profile (texture group counts of
        the object data DTPs, finding 47: a raw count wipes game memory) and tools\soundplex_sequence_fix.py scan
        --profile (SoundPlex Sequence repeat word, finding 49: repeat 0 = endless sound); both read-only, run with
        the project venv from the repository; a problem = fail, a tool that cannot evaluate the profile = warn
        (-SkipDataChecks leaves them out),
      * with -RunProfile: the tree sources and their md5 lists (a mismatch makes the run abort), each profile ASI
        (source sha256 vs. profile; installed <game>\<name>.asi sha256), each INI (installed sha256, sample sha256,
        the profile's INI overrides vs. the current values), other ASIs in the game folder,
      * TruMenu 0.11 "Ablauf", only for a profile with "flowFile": the flow file (marker line, 0 parse errors with the
        parser of Invoke-TruTestRun.ps1 / TruFlowCore.h, flowSha256), every do= command an item of the profile's
        TruMenu.asi (and the build knows flow.next), TruMenu [Flow] Enabled=1 in the profile, TruTrace in the profile
        when a pattern reads TruTrace.log, a TruMenu.flow.txt in the game folder (ours / foreign),
      * -Session (a cdb command file): present, number of ba w4 / THRALLLINK breakpoints, .dump target folders,
      * cdb.exe (x86, default Windows Kits 10 path or -CdbPath),
      * free disk space on the game drive, the workspace drive and the WER crash dump drive; free RAM (+ the largest
        processes, information only),
      * TruGuard: installed asi / ini sha256 as information only (no judgement),
      * save folder (Documents\Eidos\Tomb Raider - Underworld, OneDrive or local; or -SaveFolder): number, size and
        newest date of the *.TRUSave files (listed only, never opened),
      * HKLM ...\Windows Error Reporting\LocalDumps\tru.exe (information) and the game's Fullscreen value
        (HKCU ...\Crystal Dynamics\Tomb Raider: Underworld\Graphics, information).
    -Verbose shows each step, -Debug paths and hashes, -Trace adds a PowerShell line trace.
    Exit code: 0 = no fail row, 1 = at least one fail row.

.PARAMETER RunProfile
    Test profile name (tests\profiles\<name>.json) or path; without it the profile checks are skipped.
.PARAMETER GamePath
    Game folder; default: found via the Steam libraries.
.PARAMETER CdbPath
    cdb.exe (x86); default: Windows Kits 10 Debuggers\x86\cdb.exe.
.PARAMETER Session
    cdb command file the evening run will use (e.g. the THRALLLINK session); optional.
.PARAMETER SaveFolder
    Save folder; default: Documents\Eidos\Tomb Raider - Underworld (OneDrive and local Documents are tried).
.PARAMETER MinFreeDiskGB
    Free space below this is a warning (default 10 GB; below 2 GB a fail). Full dumps are ~0.6 GB each.
.PARAMETER MinFreeRamGB
    Free RAM below this is a warning (default 4 GB; below 2 GB a fail).
.PARAMETER SkipTreeHashes
    Do not hash the profile tree files (faster; the md5 lists are then not checked).
.PARAMETER SkipDataChecks
    Do not run the two data checks of the profile's DRMs (objdata_texlist_check / soundplex_sequence_fix scan,
    together about 1-2 minutes).
.PARAMETER Trace
    PowerShell line trace (Set-PSDebug -Trace 1).

.EXAMPLE
    .\scripts\windows\Test-TruPreflight.ps1 -RunProfile regress_shadowlara_50l_radial2
.EXAMPLE
    .\scripts\windows\Test-TruPreflight.ps1 -RunProfile regress_shadowlara_50l_radial2 -Session ..\session_thrall_watch.cdb -Verbose
#>
[CmdletBinding()]
param(
    [Alias('Profile')][string]$RunProfile,
    [string]$GamePath,
    [string]$CdbPath,
    [string]$Session,
    [string]$SaveFolder,
    [ValidateRange(1, 10000)][int]$MinFreeDiskGB = 10,
    [ValidateRange(1, 1024)][int]$MinFreeRamGB = 4,
    [switch]$SkipTreeHashes,
    [switch]$SkipDataChecks,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, Find-TruGamePath, Get-Md5
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$workspace = $paths.Workspace
$repo      = $paths.Repository
$backupDir = Join-Path $workspace 'backup'
$stateFile = Join-Path $workspace 'runs\installed-state.json'
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path $paths.Logs | Out-Null
$logFile = Join-Path $paths.Logs ('Test-TruPreflight_{0}.log' -f $stamp)
Set-TruLogFile -Path $logFile

# our plugins (same list as Invoke-TruTestRun.ps1)
$knownAsis = 'TruDlc2Player', 'TruDoppelganger', 'TruRockVein', 'TruShadowPower', 'TruLink', 'TruGuard', 'TruMenu',
              'TruDataGuard', 'TruShadowCombat', 'TruShadowHud', 'TruTrace'
# generalbank builds with a meaning (docs\Befund-Direktstart.md, docs\Befund-Felsrinne.md, TODO.md)
$generalbankKnown = @{
    'b57d8c482accab7afab59ee20bd8ccad' = 'test patch 41e (direct start: attract timer loads dlc_level2_start) - test only, never ship'
    '3a2b9a1d7b689d13d73037d3b412ea5b' = 'test patch 41e + script 104 fix (direct start) - test only, never ship'
}
$icons = @{
    ok   = [string][char]0x2705                      # check mark
    warn = [string][char]0x26A0 + [string][char]0xFE0F   # warning sign
    fail = [string][char]0x274C                      # cross
    info = [string][char]0x2139 + [string][char]0xFE0F   # information
}
$rows = New-Object System.Collections.Generic.List[object]

# ---- TruMenu 0.11 "Ablauf": the flow file parser (the same text in Invoke-TruTestRun.ps1; the C++ side is
# src/asi/TruMenu/TruFlowCore.h - the workbench test tru-flow-test\Test-FlowRunner.ps1 checks all three against each other) ----
function ConvertTo-TruFlowAscii {
    # UTF-8 text -> ASCII as TruMenu shows it (TruFlowCore.h Ascii: umlauts spelled out, a few marks mapped, else '?')
    param([string]$Text)
    if (!$Text) { return '' }
    $sb = New-Object System.Text.StringBuilder
    $i = 0
    while ($i -lt $Text.Length) {
        $c = [int]$Text[$i]
        if ([char]::IsHighSurrogate($Text[$i]) -and $i + 1 -lt $Text.Length) { [void]$sb.Append('?'); $i += 2; continue }
        $i++
        if ($c -lt 0x80) { [void]$sb.Append([char]$c); continue }
        $map = switch ($c) {
            0xe4 { 'ae' } 0xf6 { 'oe' } 0xfc { 'ue' } 0xc4 { 'Ae' } 0xd6 { 'Oe' } 0xdc { 'Ue' } 0xdf { 'ss' } 0xb7 { '-' }
            0x2013 { '-' } 0x2014 { '-' } 0x201e { '"' } 0x201c { '"' } 0x201d { '"' } 0x2018 { "'" } 0x2019 { "'" }
            0x2026 { '...' } 0xa0 { ' ' } 0x2192 { '->' } default { '?' }
        }
        [void]$sb.Append($map)
    }
    return $sb.ToString()
}

function Test-TruFlowRegex {
    # the regex subset of TruFlowCore.h CompileRegex; $null = fine, else the reason (same rules as the C++ side)
    param([string]$Source)
    $escapable = '\.[]()*+?^$|{}-/:''"#&%!=<>,;@~`'
    $s = $Source
    $i = 0
    $atoms = 0
    if ($s.Length -and $s[0] -eq '^') { $i = 1 }
    $anchorEnd = $false
    while ($i -lt $s.Length) {
        $ch = $s[$i]
        if ($ch -eq '$' -and $i -eq $s.Length - 1) { $anchorEnd = $true; break }
        if ('()|{}'.IndexOf($ch) -ge 0) { return "'$ch' is not in the pattern subset (no groups, alternation or {n})" }
        if ('*+?'.IndexOf($ch) -ge 0) { return "quantifier '$ch' without an atom" }
        if ($ch -eq '^' -or $ch -eq '$') { return "anchor '$ch' only at the start / end" }
        if ($ch -eq '.') { $i++ }
        elseif ($ch -eq '\') {
            if ($i + 1 -ge $s.Length) { return "pattern ends with '\'" }
            $e = $s[$i + 1]
            if ('dwsDWS'.IndexOf($e) -lt 0 -and $escapable.IndexOf($e) -lt 0) { return "escape '\$e' is not in the pattern subset" }
            $i += 2
        }
        elseif ($ch -eq '[') {
            $i++
            if ($i -lt $s.Length -and $s[$i] -eq '^') { $i++ }
            $first = $true
            while ($i -lt $s.Length -and ($s[$i] -ne ']' -or $first)) {
                $lo = 0
                if ($s[$i] -eq '\') {
                    if ($i + 1 -ge $s.Length) { break }
                    $e = $s[$i + 1]
                    if ('dws'.IndexOf($e) -ge 0) {
                        $i += 2
                        $first = $false
                        if ($i + 1 -lt $s.Length -and $s[$i] -eq '-' -and $s[$i + 1] -ne ']') { return "a range cannot start at \$e" }
                        continue
                    }
                    if ($escapable.IndexOf($e) -lt 0) { return "escape '\$e' in a class is not in the subset" }
                    $lo = [int]$e
                    $i += 2
                }
                else {
                    if ($s[$i] -eq '[') { return "'[' inside a class must be escaped" }
                    $lo = [int]$s[$i]
                    $i++
                }
                $first = $false
                if ($i + 1 -lt $s.Length -and $s[$i] -eq '-' -and $s[$i + 1] -ne ']') {
                    if ($s[$i + 1] -eq '\') {
                        if ($i + 2 -ge $s.Length -or $escapable.IndexOf($s[$i + 2]) -lt 0 -or 'dws'.IndexOf($s[$i + 2]) -ge 0) { return 'bad range end in a class' }
                        $hi = [int]$s[$i + 2]
                        $i += 3
                    }
                    else { $hi = [int]$s[$i + 1]; $i += 2 }
                    if ($hi -lt $lo) { return ('range {0}-{1} is reversed' -f [char]$lo, [char]$hi) }
                }
            }
            if ($i -ge $s.Length -or $s[$i] -ne ']') { return "class without ']'" }
            $i++
        }
        elseif ($ch -eq ']') { return "']' must be escaped" }
        else { $i++ }
        $copies = 1
        if ($i -lt $s.Length -and ($s[$i] -eq '*' -or $s[$i] -eq '?')) { $i++ }
        elseif ($i -lt $s.Length -and $s[$i] -eq '+') { $copies = 2; $i++ }
        if ($i -lt $s.Length -and '*+?'.IndexOf($s[$i]) -ge 0) { return 'two quantifiers in a row' }
        $atoms += $copies
        if ($atoms -gt 63) { return 'more than 63 atoms' }
    }
    if (!$atoms -and !($Source.StartsWith('^')) -and !$anchorEnd) { return 'empty regex' }
    return $null
}

function Test-TruFlowPattern {
    # a pattern ("re:<expr>" or a substring); $null = fine, else the reason
    param([string]$Pattern)
    if ($Pattern.StartsWith('re:')) {
        if ([Text.Encoding]::UTF8.GetByteCount($Pattern.Substring(3)) -ge 128) { return 'pattern longer than 127' }
        return (Test-TruFlowRegex $Pattern.Substring(3))
    }
    if ([Text.Encoding]::UTF8.GetByteCount($Pattern) -ge 128) { return 'pattern longer than 127' }
    return $null
}

function Test-TruFlowLine {
    # does one log line match a watch (file / category / pattern)? Same rules as TruFlowCore.h WatchMatches
    param($Watch, [string]$Line)
    $text = $Line
    if ($Watch.cat) {
        $key = '] ' + $Watch.cat + ': '
        $at = $Line.IndexOf($key, [StringComparison]::Ordinal)
        if ($at -lt 0) { return $false }
        $text = $Line.Substring($at + $key.Length)
    }
    $p = [string]$Watch.pattern
    if ($p.StartsWith('re:')) { return [regex]::IsMatch($text, $p.Substring(3), [Text.RegularExpressions.RegexOptions]::CultureInvariant) }
    return (!$p -or $text.IndexOf($p, [StringComparison]::Ordinal) -ge 0)
}

function Read-TruFlowText {
    # TruMenu.flow.txt text -> flow object (same records, watches, limits and error lines as TruFlowCore.h ParseText)
    param([string]$Text, [string]$Source = '(text)')
    $traceCats = 'trace', 'sound', 'teleport', 'chart', 'power', 'spawn', 'obj', 'timevec', 'level', 'portal', 'stream',
                 'save', 'progress', 'message', 'gamedata'
    $flow = [pscustomobject]@{ source = $Source; id = ''; title = ''; titleRaw = ''; hasHeader = $false
        counters = New-Object System.Collections.Generic.List[object]; watches = New-Object System.Collections.Generic.List[object]
        steps = New-Object System.Collections.Generic.List[object]; errors = New-Object System.Collections.Generic.List[object] }
    $bytes = { param($s) [Text.Encoding]::UTF8.GetByteCount([string]$s) }
    $validId = { param($s) ([string]$s) -cmatch '^[A-Za-z0-9_.-]{1,31}$' }
    $validName = { param($s) ([string]$s) -cmatch '^[A-Za-z0-9_.:-]{1,63}$' }
    $addWatch = {
        param($file, $cat, $pattern)
        for ($w = 0; $w -lt $flow.watches.Count; $w++) {
            $x = $flow.watches[$w]
            if ($x.file -eq $file -and $x.cat -ceq $cat -and $x.pattern -ceq $pattern) { return @{ index = $w } }
        }
        if ($flow.watches.Count -ge 48) { return @{ why = 'more than 48 log patterns' } }
        $why = Test-TruFlowPattern $pattern
        if ($why) { return @{ why = $why } }
        $flow.watches.Add([pscustomobject]@{ file = $file; cat = $cat; pattern = $pattern })
        return @{ index = $flow.watches.Count - 1 }
    }
    $watchRef = {
        param([string]$t)
        $c1 = $t.IndexOf(':')
        if ($c1 -lt 0 -or $c1 -ge 8) { return @{ why = 'expected log:<file>:<pattern> or trace:<category>:<pattern>' } }
        $kind = $t.Substring(0, $c1)
        $c2 = $t.IndexOf(':', $c1 + 1)
        if ($c2 -lt 0) { return @{ why = "'$kind' needs <name>:<pattern>" } }
        $a = $t.Substring($c1 + 1, $c2 - $c1 - 1)
        if ($a.Length -ge 40) { return @{ why = 'name too long' } }
        $pat = $t.Substring($c2 + 1)
        if ($kind -ceq 'log') {
            if ($a -cnotmatch '^Tru[A-Za-z0-9]+\.[Ll][Oo][Gg]$' -or $a.Length -lt 8) { return @{ why = "log file '$a' must be Tru<Name>.log" } }
            if (!$pat) { return @{ why = 'empty log pattern' } }
            return (& $addWatch $a '' $pat)
        }
        if ($kind -ceq 'trace') {
            if ($traceCats -cnotcontains $a) { return @{ why = "unknown TruTrace category '$a'" } }
            return (& $addWatch 'TruTrace.log' $a $pat)
        }
        return @{ why = "expected log: or trace:, got '${kind}:'" }
    }
    $parseCond = {
        param([string]$t)
        foreach ($pre in 'step:', 'done:', 'counter:', 'mark:') {
            if (!$t.StartsWith($pre, [StringComparison]::Ordinal)) { continue }
            $ref = $t.Substring($pre.Length)
            $ok = if ($pre -eq 'mark:') { $ref -and (& $bytes $ref) -lt 32 } else { & $validId $ref }
            if (!$ok) { return @{ why = "bad $pre reference '$ref'" } }
            return @{ cond = [pscustomobject]@{ type = $pre.TrimEnd(':'); ref = (ConvertTo-TruFlowAscii $ref); index = -1 } }
        }
        if ($t.StartsWith('log:', [StringComparison]::Ordinal) -or $t.StartsWith('trace:', [StringComparison]::Ordinal)) {
            $w = & $watchRef $t
            if ($w.why) { return @{ why = $w.why } }
            return @{ cond = [pscustomobject]@{ type = 'watch'; ref = ''; index = $w.index } }
        }
        return @{ why = ("unknown condition '{0}' (step: done: counter: mark: log: trace:)" -f $(if ($t.Length -gt 40) { $t.Substring(0, 40) } else { $t })) }
    }
    $parseSource = {
        param([string]$t)
        $colon = $t.IndexOf(':')
        $head = if ($colon -ge 0) { $t.Substring(0, $colon) } else { $t }
        $name = if ($colon -ge 0) { $t.Substring($colon + 1) } else { '' }
        if ($name.Length -gt 79) { $name = $name.Substring(0, 79) }
        $r = @{ source = ''; arg = ''; watch = -1 }
        switch -CaseSensitive ($head) {
            { $_ -ceq 'units' -or $_ -ceq 'levels' } {
                $units = $head -eq 'units'
                $r.source = $head
                if ($colon -ge 0 -and !(& $validName $name)) { return @{ why = "bad unit name '$name'" } }
                $r.arg = $name
                $pat = if ($units) { if ($name) { "'$name' state 2 = loaded" } else { "' state 2 = loaded" } }
                       elseif ($name) { "re:STREAM_LevelLoadAndInit '" + ($name -replace '([.:-])', '\$1') + "' \(.*\) -> unit entry" }
                       else { ') -> unit entry 0x' }
                $w = & $addWatch 'TruTrace.log' $(if ($units) { 'stream' } else { 'level' }) $pat
                if ($w.why) { return @{ why = $w.why } }
                $r.watch = $w.index
                return $r
            }
            'restores' {
                if ($colon -ge 0) { return @{ why = 'restores takes no argument' } }
                $r.source = 'restores'
                $w = & $addWatch 'TruTrace.log' 'save' 're:SAVE_RestoreGame\(\d+\) -> '
                if ($w.why) { return @{ why = $w.why } }
                $r.watch = $w.index
                return $r
            }
            'deaths' {
                if ($colon -ge 0) { return @{ why = 'deaths takes no argument' } }
                $r.source = 'deaths'
                return $r
            }
            { $_ -ceq 'toggle' -or $_ -ceq 'item' } {
                $r.source = $head
                if (!(& $validName $name)) { return @{ why = "bad $head id '$name'" } }
                $r.arg = $name
                return $r
            }
            'mark' {
                $r.source = 'mark'
                if (!$name -or (& $bytes $name) -ge 32) { return @{ why = 'bad mark name' } }
                $r.arg = ConvertTo-TruFlowAscii $name
                return $r
            }
            { $_ -ceq 'log' -or $_ -ceq 'trace' } {
                $r.source = 'watch'
                $w = & $watchRef $t
                if ($w.why) { return @{ why = $w.why } }
                $r.watch = $w.index
                $r.arg = $t
                return $r
            }
        }
        return @{ why = ("unknown counter source '{0}' (units levels deaths restores toggle: item: mark: log: trace:)" -f $(if ($t.Length -gt 40) { $t.Substring(0, 40) } else { $t })) }
    }
    $parseRecord = {
        param([string]$line)
        if ($line.Length -gt 1000) { return 'line longer than 1000' }
        $fl = @($line.Split('|') | ForEach-Object { $_.Trim(' ', "`t", "`r", "`n") })
        if ($fl.Count -gt 24) { $fl = $fl[0..23] }
        $n = $fl.Count
        $watchesBefore = $flow.watches.Count
        $fail = { param($why) while ($flow.watches.Count -gt $watchesBefore) { $flow.watches.RemoveAt($flow.watches.Count - 1) }; return $why }
        if ($fl[0] -eq 'flow') {
            if ($flow.hasHeader) { return (& $fail 'a second flow record') }
            if ($n -lt 2 -or !(& $validId $fl[1])) { return (& $fail ("flow | <id> | <title>: bad id '{0}'" -f $(if ($n -gt 1) { $fl[1] } else { '' }))) }
            if ($n -gt 3) { return (& $fail 'flow record with more than 3 fields') }
            if ($n -gt 2 -and (& $bytes $fl[2]) -ge 160) { return (& $fail 'title longer than 159 bytes') }
            $flow.id = $fl[1]
            $flow.titleRaw = if ($n -gt 2) { $fl[2] } else { '' }
            $flow.title = ConvertTo-TruFlowAscii $flow.titleRaw
            $flow.hasHeader = $true
            return $null
        }
        if ($fl[0] -eq 'counter') {
            if ($n -lt 4 -or $n -gt 5) { return (& $fail 'counter | <id> | <source> | <target> | <text>') }
            if (!(& $validId $fl[1])) { return (& $fail "bad counter id '$($fl[1])'") }
            if (@($flow.counters | Where-Object { $_.id -eq $fl[1] }).Count) { return (& $fail "counter id '$($fl[1])' twice") }
            if ($flow.counters.Count -ge 16) { return (& $fail 'more than 16 counters') }
            $src = & $parseSource $fl[2]
            if ($src.why) { return (& $fail $src.why) }
            if ($fl[3] -cnotmatch '^[0-9]{1,5}$') { return (& $fail "counter target '$($fl[3])' must be 0..99999") }
            if ($n -gt 4 -and (& $bytes $fl[4]) -ge 160) { return (& $fail 'counter text longer than 159 bytes') }
            $raw = if ($n -gt 4) { $fl[4] } else { '' }
            $flow.counters.Add([pscustomobject]@{ id = $fl[1]; source = $src.source; arg = $src.arg; target = [int]$fl[3]
                watch = $src.watch; text = (ConvertTo-TruFlowAscii $raw); textRaw = $raw; spec = $fl[2] })
            return $null
        }
        if ($fl[0] -eq 'step') {
            if ($n -lt 4) { return (& $fail 'step | <id> | <kind> | <text> [| key=value ...]') }
            if (!(& $validId $fl[1])) { return (& $fail "bad step id '$($fl[1])'") }
            if (@($flow.steps | Where-Object { $_.id -eq $fl[1] }).Count) { return (& $fail "step id '$($fl[1])' twice") }
            if ($flow.steps.Count -ge 64) { return (& $fail 'more than 64 steps') }
            $kind = @('action', 'observe', 'mark') | Where-Object { $_ -eq $fl[2] } | Select-Object -First 1
            if (!$kind) { return (& $fail "step kind '$($fl[2])' must be action, observe or mark") }
            if (!$fl[3]) { return (& $fail 'step without text') }
            if ((& $bytes $fl[3]) -ge 160) { return (& $fail 'step text longer than 159 bytes') }
            $s = [pscustomobject]@{ id = $fl[1]; kind = $kind; text = (ConvertTo-TruFlowAscii $fl[3]); textRaw = $fl[3]; hint = ''; hintRaw = ''
                cmds = ''; skip = ''; skipRaw = ''; after = New-Object System.Collections.Generic.List[object]; check = New-Object System.Collections.Generic.List[object]
                fail = New-Object System.Collections.Generic.List[object]; countIds = New-Object System.Collections.Generic.List[string]
                counters = New-Object System.Collections.Generic.List[int]; line = 0; condText = @{ after = @(); check = @(); fail = @() } }
            $have = @{}
            for ($i = 4; $i -lt $n; $i++) {
                $eq = $fl[$i].IndexOf('=')
                if ($eq -lt 0) { return (& $fail ("field '{0}' is not key=value" -f $(if ($fl[$i].Length -gt 40) { $fl[$i].Substring(0, 40) } else { $fl[$i] }))) }
                $key = $fl[$i].Substring(0, $eq).Trim(' ', "`t")
                $val = $fl[$i].Substring($eq + 1).Trim(' ', "`t")
                $k = $key.ToLowerInvariant()
                switch ($k) {
                    'do' {
                        if ($have['do']) { return (& $fail 'do= twice') }
                        $have['do'] = $true
                        if ($kind -ne 'action') { return (& $fail 'do= only in an action step') }
                        if ((& $bytes $val) -gt 319) { return (& $fail 'do= longer than 319 characters') }
                        $cmds = @($val.Split(';') | ForEach-Object { $_.Trim(' ', "`t", "`r", "`n") } | Where-Object { $_ })
                        foreach ($c in $cmds) {
                            if ($c.StartsWith('#')) { return (& $fail 'do= must not hold a #title') }
                            if ($c -match '^game\.quit( |$)') { return (& $fail 'game.quit is never run by a flow') }
                        }
                        if (!$cmds.Count) { return (& $fail 'do= without a command') }
                        if ($cmds.Count -gt 12) { return (& $fail 'do= with more than 12 commands') }
                        $s.cmds = $val
                    }
                    { $_ -eq 'after' -or $_ -eq 'check' -or $_ -eq 'fail' } {
                        $list = $s.$k
                        if ($list.Count -ge 4) { return (& $fail "more than 4 $key= conditions") }
                        $c = & $parseCond $val
                        if ($c.why) { return (& $fail $c.why) }
                        $list.Add($c.cond)
                        $s.condText[$k] += $val
                    }
                    'count' {
                        if ($have['count']) { return (& $fail 'count= twice') }
                        $have['count'] = $true
                        foreach ($c in @($val.Split(',') | ForEach-Object { $_.Trim(' ', "`t", "`r", "`n") } | Where-Object { $_ })) {
                            if (!(& $validId $c)) { return (& $fail "bad counter id '$c' in count=") }
                            if ($s.countIds.Count -ge 4) { return (& $fail 'more than 4 counters in count=') }
                            $s.countIds.Add($c)
                            $s.counters.Add(-1)
                        }
                        if (!$s.countIds.Count) { return (& $fail 'count= without a counter') }
                    }
                    'skip' {
                        if ($have['skip']) { return (& $fail 'skip= twice') }
                        $have['skip'] = $true
                        if (!$val) { return (& $fail 'skip= needs a reason') }
                        if ((& $bytes $val) -ge 160) { return (& $fail 'skip reason longer than 159 bytes') }
                        $s.skip = ConvertTo-TruFlowAscii $val
                        $s.skipRaw = $val
                    }
                    'hint' {
                        if ($have['hint']) { return (& $fail 'hint= twice') }
                        $have['hint'] = $true
                        if ((& $bytes $val) -ge 160) { return (& $fail 'hint longer than 159 bytes') }
                        $s.hint = ConvertTo-TruFlowAscii $val
                        $s.hintRaw = $val
                    }
                    default { return (& $fail "unknown key '$key' (do after check fail count skip hint)") }
                }
            }
            if ($kind -eq 'action' -and !$have['do']) { return (& $fail 'an action step needs do=') }
            $flow.steps.Add($s)
            return $null
        }
        return (& $fail ("unknown record '{0}' (flow, counter, step)" -f $(if ($fl[0].Length -gt 20) { $fl[0].Substring(0, 20) } else { $fl[0] })))
    }
    if ($Text.Length -and $Text[0] -eq [char]0xFEFF) { $Text = $Text.Substring(1) }
    $lineNo = 0
    foreach ($raw in $Text.Split("`n")) {
        $lineNo++
        $line = $raw.Trim(' ', "`t", "`r", "`n")
        if (!$line -or $line.StartsWith('#')) { continue }
        if ([Text.Encoding]::UTF8.GetByteCount($raw.TrimEnd("`r")) -gt 1000) { $flow.errors.Add([pscustomobject]@{ line = $lineNo; message = 'line longer than 1000 characters' }); continue }
        $before = $flow.steps.Count
        $why = & $parseRecord $line
        if ($why) { $flow.errors.Add([pscustomobject]@{ line = $lineNo; message = $why }); continue }
        if ($flow.steps.Count -gt $before) { $flow.steps[$flow.steps.Count - 1].line = $lineNo }
    }
    # references (TruFlowCore.h Resolve): a bad step is reported and dropped, then everything is resolved again
    $again = $true
    while ($again) {
        $again = $false
        for ($i = 0; $i -lt $flow.steps.Count -and !$again; $i++) {
            $s = $flow.steps[$i]
            $why = $null
            for ($k = 0; $k -lt $s.countIds.Count -and !$why; $k++) {
                $ci = -1
                for ($j = 0; $j -lt $flow.counters.Count; $j++) { if ($flow.counters[$j].id -eq $s.countIds[$k]) { $ci = $j; break } }
                $s.counters[$k] = $ci
                if ($ci -lt 0) { $why = "count=: no counter '$($s.countIds[$k])'" }
            }
            foreach ($list in @($s.after, $s.check, $s.fail)) {
                foreach ($c in $list) {
                    if ($why) { break }
                    if ($c.type -eq 'step' -or $c.type -eq 'done') {
                        $c.index = -1
                        for ($j = 0; $j -lt $flow.steps.Count; $j++) { if ($flow.steps[$j].id -eq $c.ref) { $c.index = $j; break } }
                        if ($c.index -lt 0) { $why = "no step '$($c.ref)'" }
                        elseif ($c.index -eq $i) { $why = "step '$($c.ref)' refers to itself" }
                    }
                    elseif ($c.type -eq 'counter') {
                        $c.index = -1
                        for ($j = 0; $j -lt $flow.counters.Count; $j++) { if ($flow.counters[$j].id -eq $c.ref) { $c.index = $j; break } }
                        if ($c.index -lt 0) { $why = "no counter '$($c.ref)'" }
                        elseif ($flow.counters[$c.index].target -lt 1) { $why = "counter '$($c.ref)' has no target (0)" }
                    }
                }
            }
            if ($why) {
                $flow.errors.Add([pscustomobject]@{ line = $s.line; message = $why })
                $flow.steps.RemoveAt($i)
                $again = $true
            }
        }
    }
    return $flow
}

function Read-TruFlowFile {
    # TruMenu.flow.txt (UTF-8, BOM optional) -> flow object; $null when the file is missing
    param([string]$Path)
    if (!$Path -or !(Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $text = [IO.File]::ReadAllText($Path, (New-Object System.Text.UTF8Encoding($false)))
    return (Read-TruFlowText -Text $text -Source $Path)
}

function Add-Row {
    # one table row; State: ok / warn / fail / info
    param([string]$Area, [string]$Check, [ValidateSet('ok', 'warn', 'fail', 'info')][string]$State, [string]$Detail)
    $rows.Add([pscustomobject]@{ Area = $Area; Check = $Check; State = $State; Detail = $Detail })
    Write-Log ('{0} {1} / {2}: {3}' -f $State.ToUpper(), $Area, $Check, $Detail) -Level VERBOSE
}

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

function Get-Short {
    # first 8 hex digits of a hash for the table
    param([string]$Hash)
    if (!$Hash) { return '-' }
    return $Hash.Substring(0, [Math]::Min(8, $Hash.Length)) + '...'
}

function Get-TruIniValue {
    # same reader as Invoke-TruTestRun.ps1
    param([string]$Path, [string]$Section, [string]$Key)
    if (!$Path -or !(Test-Path -LiteralPath $Path)) { return $null }
    $inSection = $false
    foreach ($l in [IO.File]::ReadAllLines($Path)) {
        if ($l -match '^\s*\[(.+)\]\s*$') { $inSection = $Matches[1] -eq $Section; continue }
        if ($inSection -and $l -match ('^\s*' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) { return $Matches[1].Trim() }
    }
    return $null
}

function Resolve-WorkspacePath {
    # profile paths are relative to <workspace>
    param([string]$Relative)
    if (!$Relative) { return $null }
    if ([IO.Path]::IsPathRooted($Relative)) { return $Relative }
    return [IO.Path]::GetFullPath((Join-Path $workspace ($Relative -replace '/', '\')))
}

function Format-GB {
    param([double]$Bytes)
    return ('{0:N1} GB' -f ($Bytes / 1GB))
}

function Test-FreeDisk {
    param([string]$Label, [string]$Path)
    try {
        $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Path))
        $d = New-Object System.IO.DriveInfo($root)
        $free = $d.AvailableFreeSpace
        $state = if ($free -lt 2GB) { 'fail' } elseif ($free -lt ([long]$MinFreeDiskGB * 1GB)) { 'warn' } else { 'ok' }
        Add-Row 'System' "Free disk $root ($Label)" $state ('{0} free of {1}' -f (Format-GB $free), (Format-GB $d.TotalSize))
    }
    catch { Add-Row 'System' "Free disk ($Label)" 'warn' "not readable: $($_.Exception.Message)" }
}

function Invoke-TruPyCheck {
    # one read-only repository tool with the project venv (-u -I -X utf8, working folder = repository, no window);
    # every output line goes to the log (DEBUG). Returns @{ Code; Lines; Why } - Code $null = could not run / did not
    # finish (Why says why). A tool still running after the timeout is reported with its PID and NOT ended.
    param([string[]]$ToolArgs, [int]$TimeoutSeconds = 1800)
    $python = Join-Path $workspace 'bin\venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) { return @{ Code = $null; Lines = @(); Why = "no project venv ($python)" } }
    if (!(Test-Path -LiteralPath (Join-Path $repo $ToolArgs[0]))) { return @{ Code = $null; Lines = @(); Why = "tool missing: $($ToolArgs[0])" } }
    $allArgs = @('-u', '-I', '-X', 'utf8') + $ToolArgs
    $argLine = ($allArgs | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    Write-Log "python $argLine" -Level DEBUG
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = $argLine
    $psi.WorkingDirectory = $repo
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $t0 = Get-Date
    $p = [System.Diagnostics.Process]::Start($psi)
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if (!$p.WaitForExit($TimeoutSeconds * 1000)) {
        return @{ Code = $null; Lines = @(); Why = ('still running after {0} s (PID {1}, not ended - end it yourself if needed)' -f $TimeoutSeconds, $p.Id) }
    }
    $p.WaitForExit()
    $lines = @(($outTask.Result -split "`r?`n") | Where-Object { $_ -ne '' })
    $errLines = @(($errTask.Result -split "`r?`n") | Where-Object { $_ -ne '' })
    foreach ($l in $lines) { Write-Log "  $l" -Level DEBUG }
    foreach ($l in $errLines) { Write-Log "  stderr: $l" -Level DEBUG }
    Write-Log ('{0}: exit {1}, {2} lines, {3:N0} s' -f (Split-Path -Leaf $ToolArgs[0]), $p.ExitCode, $lines.Count, ((Get-Date) - $t0).TotalSeconds) -Level VERBOSE
    $why = if ($errLines.Count) { 'stderr: ' + $errLines[-1] } else { '' }
    return @{ Code = $p.ExitCode; Lines = $lines; Why = $why }
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Test-TruPreflight profile=$RunProfile session=$Session log=$logFile (read-only)" -Level VERBOSE

    # ---- running game ----
    $running = @(Get-Process -Name 'tru' -ErrorAction SilentlyContinue)
    if ($running.Count) { Add-Row 'Game' 'tru.exe running' 'fail' ('PID {0} - a run refuses to start; close the game yourself (this script never ends it)' -f (($running | ForEach-Object { $_.Id }) -join ', ')) }
    else { Add-Row 'Game' 'tru.exe running' 'ok' 'not running' }
    $dbg = @(Get-Process -Name 'cdb' -ErrorAction SilentlyContinue)
    if ($dbg.Count) { Add-Row 'Game' 'cdb.exe running' 'warn' ('PID {0} - an old debugger session is still open' -f (($dbg | ForEach-Object { $_.Id }) -join ', ')) }

    # ---- game folder ----
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    $gameOk = $GamePath -and (Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))
    if ($gameOk) {
        $modsOk = Test-Path -LiteralPath (Join-Path $GamePath 'mods')
        Add-Row 'Game' 'Game folder' $(if ($modsOk) { 'ok' } else { 'fail' }) ('{0}{1}' -f $GamePath, $(if ($modsOk) { '' } else { ' - no mods folder (B138 kit / ModLoader?)' }))
    }
    else { Add-Row 'Game' 'Game folder' 'fail' "not found ($GamePath) - pass -GamePath" }
    Write-Log "Game folder: $GamePath" -Level DEBUG

    # ---- harness state + stacked trees ----
    $harnessTrees = @()
    if (Test-Path -LiteralPath $stateFile) {
        $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $harnessTrees = @(@($state.trees) | Where-Object { $_ } | ForEach-Object { [string]$_ })
        Add-Row 'Trees' 'Previous harness run' 'info' ('{0} ({1}): {2} tree(s), {3} file(s), {4} INI backup(s) - the next Invoke-TruTestRun undoes them itself' -f
            $state.run, $state.time, $harnessTrees.Count, @(@($state.files) | Where-Object { $_ }).Count, @(@($state.inis) | Where-Object { $_ }).Count)
    }
    else { Add-Row 'Trees' 'Previous harness run' 'ok' 'no runs\installed-state.json (nothing to undo)' }

    $open = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike '*.restored' } | Sort-Object Name)
    $treesWithGb = New-Object System.Collections.Generic.List[string]
    $treeText = New-Object System.Collections.Generic.List[string]
    foreach ($t in $open) {
        $mf = Join-Path $t.FullName 'manifest.json'
        if (Test-Path -LiteralPath $mf) {
            $m = Get-Content -LiteralPath $mf -Raw -Encoding UTF8 | ConvertFrom-Json
            $src = [string]$m.source
            $short = if ($src) { (Split-Path -Leaf (Split-Path -Parent $src)) + '\' + (Split-Path -Leaf $src) } else { '?' }
            $treeText.Add(('{0} ({1}: +{2} / ~{3})' -f $t.Name, $short, @(@($m.added) | Where-Object { $_ }).Count, @(@($m.replaced) | Where-Object { $_ }).Count))
            if ((@($m.added) -contains 'generalbank.drm') -or (@(@($m.replaced) | Where-Object { $_ -and $_.path -eq 'generalbank.drm' }).Count)) { $treesWithGb.Add("$($t.Name) = $short") }
        }
        else { $treeText.Add("$($t.Name) (no manifest.json)") }
        Write-Log "open tree backup: $($treeText[-1])" -Level DEBUG
    }
    $foreignOpen = @($open | Where-Object { $harnessTrees -notcontains $_.Name })
    if (!$open.Count) { Add-Row 'Trees' 'Open tree installs (backup\tree_*)' 'ok' 'none - only *.restored' }
    elseif (!$foreignOpen.Count) {
        Add-Row 'Trees' 'Open tree installs (backup\tree_*)' 'ok' ('{0} open, all from the previous harness run: {1}' -f $open.Count, ($treeText -join '; '))
    }
    else {
        $newest = if ($harnessTrees.Count) { [string](@($harnessTrees | Sort-Object)[-1]) } else { '' }
        $onTop = @($foreignOpen | Where-Object { $newest -and $_.Name -gt $newest })
        $stateTxt = if ($onTop.Count) { 'fail' } else { 'warn' }
        $note = if ($onTop.Count) { " - $($onTop.Count) newer than the harness trees: the next run refuses to undo (Install-TruTree.ps1 -Restore first)" } else { ' - stacked below / without harness state, not restored (report only)' }
        Add-Row 'Trees' 'Open tree installs (backup\tree_*)' $stateTxt ('{0} open, {1} not from the previous harness run{2}: {3}' -f $open.Count, $foreignOpen.Count, $note, ($treeText -join '; '))
    }

    # ---- profile ----
    $prof = $null
    if ($RunProfile) {
        $pp = if ($RunProfile -match '[\\/]' -or $RunProfile -like '*.json') { $RunProfile } else { Join-Path $repo "tests\profiles\$RunProfile.json" }
        if (Test-Path -LiteralPath $pp) {
            $prof = Get-Content -LiteralPath $pp -Raw -Encoding UTF8 | ConvertFrom-Json
            Add-Row 'Profile' 'Profile file' 'ok' ('{0} ({1} trees, {2} files, {3} ASIs)' -f (Split-Path -Leaf $pp), @(@($prof.trees) | Where-Object { $_ }).Count, @(@($prof.files) | Where-Object { $_ }).Count, @(@($prof.asis) | Where-Object { $_ }).Count)
        }
        else { Add-Row 'Profile' 'Profile file' 'fail' "not found: $pp" }
    }
    else { Add-Row 'Profile' 'Profile file' 'info' 'no -RunProfile - profile checks skipped' }

    # ---- generalbank ----
    $profileGb = $null
    if ($prof) {
        foreach ($t in @($prof.trees)) { if ($t -and $t.md5 -and $t.md5.'generalbank.drm') { $profileGb = [string]$t.md5.'generalbank.drm' } }
        foreach ($f in @($prof.files)) { if ($f -and $f.name -eq 'generalbank.drm' -and $f.md5) { $profileGb = [string]$f.md5 } }
    }
    if ($gameOk) {
        $gb = Join-Path $GamePath 'mods\generalbank.drm'
        if (Test-Path -LiteralPath $gb) {
            $gbMd5 = Get-Md5 $gb
            # the newest open install that wrote generalbank.drm is where the current file came from
            $from = if ($treesWithGb.Count) {
                ' (last written by tree install {0}{1})' -f $treesWithGb[$treesWithGb.Count - 1], $(if ($treesWithGb.Count -gt 1) { "; $($treesWithGb.Count - 1) older open install(s) also wrote it" } else { '' })
            } else { '' }
            if ($generalbankKnown.ContainsKey($gbMd5)) {
                $runNote = if ($profileGb) { '; the profile brings its own generalbank for the run, the undo after the run brings this one back' } else { '' }
                Add-Row 'Game' 'generalbank.drm' 'warn' ('md5 {0} = {1}{2}{3} (TODO: Direktstart herausnehmen)' -f $gbMd5, $generalbankKnown[$gbMd5], $from, $runNote)
            }
            elseif ($profileGb -and $gbMd5 -eq $profileGb) { Add-Row 'Game' 'generalbank.drm' 'ok' ("md5 $gbMd5 = the profile's generalbank$from") }
            else { Add-Row 'Game' 'generalbank.drm' 'info' ('md5 {0} - not 41e{1}{2}' -f $gbMd5, $(if ($profileGb) { ", profile brings $profileGb" } else { '' }), $from) }
        }
        else { Add-Row 'Game' 'generalbank.drm' 'info' 'no mods\generalbank.drm (the game uses its own bigfile copy)' }
    }

    if ($prof) {
        # ---- tree sources ----
        $nTrees = 0; $missing = New-Object System.Collections.Generic.List[string]; $bad = New-Object System.Collections.Generic.List[string]; $hashed = 0
        foreach ($t in @($prof.trees)) {
            if (!$t) { continue }
            $nTrees++
            $src = Resolve-WorkspacePath $t.source
            if (!(Test-Path -LiteralPath $src -PathType Container)) { $missing.Add([string]$t.source); continue }
            if ($SkipTreeHashes -or !$t.md5) { continue }
            foreach ($p in $t.md5.PSObject.Properties) {
                $f = Join-Path $src ($p.Name -replace '/', '\')
                if (!(Test-Path -LiteralPath $f)) { $missing.Add("$($t.source)/$($p.Name)"); continue }
                $hashed++
                $m = Get-Md5 $f
                Write-Log "md5 $m $f" -Level DEBUG
                if ($p.Value -and $m -ne [string]$p.Value) { $bad.Add("$($p.Name) is $(Get-Short $m), profile $(Get-Short ([string]$p.Value))") }
            }
        }
        foreach ($f in @($prof.files)) {
            if (!$f) { continue }
            $src = Resolve-WorkspacePath $f.source
            if (!(Test-Path -LiteralPath $src -PathType Leaf)) { $missing.Add([string]$f.source); continue }
            $hashed++
            $m = Get-Md5 $src
            if ($f.md5 -and $m -ne [string]$f.md5) { $bad.Add("$($f.name) is $(Get-Short $m), profile $(Get-Short ([string]$f.md5))") }
        }
        $detail = '{0} tree(s), {1} file(s) hashed{2}' -f $nTrees, $hashed, $(if ($SkipTreeHashes) { ' (-SkipTreeHashes: md5 lists not checked)' } else { '' })
        if ($missing.Count) { $detail += '; MISSING: ' + ($missing -join ', ') }
        if ($bad.Count) { $detail += '; md5 MISMATCH (the run aborts without -AllowMd5Mismatch): ' + ($bad -join '; ') }
        Add-Row 'Profile' 'Tree / file sources' $(if ($missing.Count -or $bad.Count) { 'fail' } else { 'ok' }) $detail

        # ---- data checks of what the profile installs (read-only repository tools; findings 47 / 49) ----
        if ($SkipDataChecks) { Add-Row 'Data' 'Profile DRM checks' 'info' '-SkipDataChecks: objdata_texlist_check / soundplex_sequence_fix scan not run' }
        else {
            $ppFull = (Resolve-Path -LiteralPath $pp).Path
            $baseArgs = @()
            $baseNote = 'no base (game folder not found): only the files of the profile trees'
            if ($gameOk -and (Test-Path -LiteralPath (Join-Path $GamePath 'mods'))) {
                $baseArgs = @('--base', (Join-Path $GamePath 'mods'))
                $baseNote = 'other files from the game mods folder as it stands'
            }
            # texture group counts of the object data DTPs (finding 47: a raw count makes tru+0x12b360 AND 0x1fff
            # over millions of dwords - crash tru+0x12b4a0 / the FMOD timer thread)
            $r = Invoke-TruPyCheck -ToolArgs (@('tools\objdata_texlist_check.py', '--profile', $ppFull) + $baseArgs)
            $sum = @($r.Lines | Where-Object { $_ -like 'PROFILE *' }) | Select-Object -First 1
            if ($null -eq $r.Code -or $r.Code -gt 1 -or !$sum) {
                Add-Row 'Data' 'Object data texture groups' 'warn' ('cannot evaluate the profile with objdata_texlist_check.py: {0}' -f $(if ($r.Why) { $r.Why } else { "exit $($r.Code), no PROFILE line" }))
            }
            else {
                $sum = $sum -replace '^PROFILE [^:]+: ', ''
                $hits = @($r.Lines | ForEach-Object { if ($_ -match '^(\S+\.drm) object (\d+) -> DTP (\d+)') { '{0} (object {1}, DTP {2})' -f $Matches[1], $Matches[2], $Matches[3] } } | Select-Object -Unique)
                if ($r.Code -eq 1) {
                    Add-Row 'Data' 'Object data texture groups' 'fail' ('{0} ({1}): {2} - raw group count (finding 47); a tree with the fixed copy (dlc_test51c_objfx or dlc_test51q_dungeon) must come after the tree that brings the file' -f $sum, $baseNote, ($hits -join ', '))
                }
                else { Add-Row 'Data' 'Object data texture groups' 'ok' ('{0} ({1})' -f $sum, $baseNote) }
            }
            # SoundPlex Sequence repeat word (finding 49: the converter u32-swapped repeat 1 -> 0 = endless sound)
            $r = Invoke-TruPyCheck -ToolArgs (@('tools\soundplex_sequence_fix.py', 'scan', '--profile', $ppFull) + $baseArgs)
            $sum = @($r.Lines | Where-Object { $_ -like 'PROFILE *: *Sequence nodes*' }) | Select-Object -First 1
            if ($null -eq $r.Code -or $r.Code -gt 1 -or !$sum) {
                Add-Row 'Data' 'SoundPlex Sequence repeat' 'warn' ('cannot evaluate the profile with soundplex_sequence_fix.py scan: {0}' -f $(if ($r.Why) { $r.Why } else { "exit $($r.Code), no PROFILE line" }))
            }
            else {
                $sum = $sum -replace '^PROFILE [^:]+: ', 'scan '
                $nRepeat = if ($sum -match 'repeat byte (\d+)\)') { [int]$Matches[1] } else { -1 }
                $nUnexp = if ($sum -match 'unexpected (\d+)') { [int]$Matches[1] } else { -1 }
                if ($r.Code -eq 0) { Add-Row 'Data' 'SoundPlex Sequence repeat' 'ok' ('{0} ({1})' -f $sum, $baseNote) }
                elseif ($nRepeat -eq 0 -and $nUnexp -eq 0) {
                    # only the bytes +0xd..+0xf differ (no known reader): wrong by the proven rule, no effect on the repeat
                    Add-Row 'Data' 'SoundPlex Sequence repeat' 'warn' ('{0} ({1}) - repeat bytes right, only the 3 bytes after them differ (no known reader; the pipeline step seqrepeat sets them, the B138 repair tree not yet)' -f $sum, $baseNote)
                }
                else {
                    Add-Row 'Data' 'SoundPlex Sequence repeat' 'fail' ('{0} ({1}) - a wrong repeat byte 0 plays the sequence for ever (finding 49); a tree with the fixed copies (dlc_test51p_moan for DLC 2) must come last' -f $sum, $baseNote)
                }
            }
        }

        # ---- ASIs + INIs ----
        $profAsiNames = @()
        foreach ($a in @($prof.asis)) {
            if (!$a) { continue }
            $n = [string]$a.name
            $profAsiNames += $n
            $dir = if ($a.sourceDir) { Resolve-WorkspacePath $a.sourceDir } else { Join-Path $repo 'work\asi' }
            $srcAsi = Join-Path $dir "$n.asi"
            $want = [string]$a.sha256
            $inst = if ($gameOk) { Join-Path $GamePath "$n.asi" } else { $null }
            $instSha = if ($inst -and (Test-Path -LiteralPath $inst)) { Get-Sha256 $inst } else { $null }
            if ($n -eq 'TruGuard') {
                # information only, no judgement: only the installed files are hashed (the sources are not opened)
                $iniG = if ($gameOk) { Join-Path $GamePath 'TruGuard.ini' } else { $null }
                $iniSha = if ($iniG -and (Test-Path -LiteralPath $iniG)) { Get-Sha256 $iniG } else { $null }
                Add-Row 'TruGuard' 'TruGuard (information only)' 'info' ('installed asi {0}, ini {1}; profile names asi {2}' -f $(if ($instSha) { $instSha } else { 'none' }), $(if ($iniSha) { $iniSha } else { 'none' }), $(if ($want) { $want } else { '-' }))
                continue
            }
            $srcSha = if (Test-Path -LiteralPath $srcAsi) { Get-Sha256 $srcAsi } else { $null }
            Write-Log "$n source $srcAsi $srcSha / installed $instSha / profile $want" -Level DEBUG
            if (!$srcSha) { Add-Row 'ASI' "$n.asi" 'fail' "source missing: $srcAsi (the run aborts)"; continue }
            if ($want -and $srcSha -ne $want) { Add-Row 'ASI' "$n.asi" 'fail' ('source sha256 {0} != profile {1} (the run aborts without -AllowMd5Mismatch)' -f (Get-Short $srcSha), (Get-Short $want)); continue }
            if ($instSha -and $instSha -eq $srcSha) { Add-Row 'ASI' "$n.asi" 'ok' ('installed = profile build {0} ({1})' -f (Get-Short $srcSha), $a.sourceDir) }
            elseif ($instSha) { Add-Row 'ASI' "$n.asi" 'warn' ('installed {0} != profile {1} ({2}) - the run installs the profile build' -f (Get-Short $instSha), (Get-Short $srcSha), $a.sourceDir) }
            else { Add-Row 'ASI' "$n.asi" 'warn' ('not installed - the run installs {0} ({1})' -f (Get-Short $srcSha), $a.sourceDir) }

            # INI: installed hash, sample hash, overrides
            $iniInst = if ($gameOk) { Join-Path $GamePath "$n.ini" } else { $null }
            $iniSample = Join-Path $dir "$n.ini"
            $iniSha = if ($iniInst -and (Test-Path -LiteralPath $iniInst)) { Get-Sha256 $iniInst } else { $null }
            $sampleSha = if (Test-Path -LiteralPath $iniSample) { Get-Sha256 $iniSample } else { $null }
            $diff = New-Object System.Collections.Generic.List[string]; $same = 0
            $overrides = @{}
            if ($a.ini) { foreach ($sec in $a.ini.PSObject.Properties) { foreach ($k in $sec.Value.PSObject.Properties) { $overrides["$($sec.Name)|$($k.Name)"] = [string]$k.Value } } }
            foreach ($r in @($prof.tests)) {
                if (!$r -or $r.kind -ne 'toggle' -or !$r.initial) { continue }
                if ([string]$r.target -match ('^ini:' + [regex]::Escape($n) + ':([A-Za-z0-9_]+):([A-Za-z0-9_]+)$')) {
                    $overrides["$($Matches[1])|$($Matches[2])"] = $(if ($r.initial -eq 'on') { '1' } else { '0' })
                }
            }
            foreach ($k in ($overrides.Keys | Sort-Object)) {
                $sec, $key = $k.Split('|')
                $now = Get-TruIniValue -Path $iniInst -Section $sec -Key $key
                if ($now -eq $overrides[$k]) { $same++ } else { $diff.Add(('[{0}] {1}={2} (now {3})' -f $sec, $key, $overrides[$k], $(if ($null -ne $now) { $now } else { 'missing' }))) }
            }
            $iniDetail = 'installed {0}, sample {1}{2}; overrides {3} equal' -f $(if ($iniSha) { Get-Short $iniSha } else { 'none' }), $(if ($sampleSha) { Get-Short $sampleSha } else { 'none' }),
                $(if ($iniSha -and $sampleSha) { $(if ($iniSha -eq $sampleSha) { ' (= sample)' } else { ' (edited / other build)' }) } else { '' }), $same
            if ($diff.Count) { $iniDetail += '; the run sets: ' + ($diff -join ', ') }
            Add-Row 'INI' "$n.ini" $(if ($diff.Count) { 'info' } else { 'ok' }) $iniDetail
        }
        if ($gameOk) {
            $extra = @($knownAsis | Where-Object { $profAsiNames -notcontains $_ -and (Test-Path -LiteralPath (Join-Path $GamePath "$_.asi")) })
            if ($extra.Count) {
                $how = if ($prof.removeOtherAsis -ne $false) { 'the run removes them (removeOtherAsis)' } else { 'they stay (removeOtherAsis false)' }
                Add-Row 'ASI' 'Our ASIs not in the profile' 'info' (($extra -join ', ') + " - $how")
            }
            else { Add-Row 'ASI' 'Our ASIs not in the profile' 'ok' 'none installed' }
            $foreign = @(Get-ChildItem -LiteralPath $GamePath -Filter '*.asi' -File | Where-Object { $knownAsis -notcontains $_.BaseName })
            if ($foreign.Count) { Add-Row 'ASI' 'Other ASI files' 'info' (($foreign | ForEach-Object { '{0} {1}' -f $_.Name, (Get-Short (Get-Sha256 $_.FullName)) }) -join ', ') }
        }

        # ---- TruMenu 0.11 "Ablauf" (only for a profile with "flowFile") ----
        if ($prof.flowFile) {
            $ff = Resolve-WorkspacePath ([string]$prof.flowFile)
            $flowMarker = '# TruMenu flow'
            $menu = @($prof.asis) | Where-Object { $_ -and $_.name -eq 'TruMenu' } | Select-Object -First 1
            if (!(Test-Path -LiteralPath $ff -PathType Leaf)) { Add-Row 'Flow' 'Flow file' 'fail' "not found: $($prof.flowFile) (the run aborts; New-FlowFile.ps1 writes it)" }
            else {
                $first = [string]([IO.File]::ReadAllLines($ff, [Text.Encoding]::UTF8) | Select-Object -First 1)
                $fl = Read-TruFlowFile $ff
                $sha = Get-Sha256 $ff
                $detail = '{0}: {1} steps, {2} counters, {3} log patterns, sha256 {4}' -f $prof.flowFile, $fl.steps.Count, $fl.counters.Count, $fl.watches.Count, (Get-Short $sha)
                if (!$first.TrimStart([char]0xFEFF).StartsWith($flowMarker)) { Add-Row 'Flow' 'Flow file' 'fail' "$detail - first line is not '$flowMarker ...' (the run aborts)" }
                elseif ($fl.errors.Count) { Add-Row 'Flow' 'Flow file' 'fail' ('{0} - {1} error(s), first line {2}: {3} (the run aborts)' -f $detail, $fl.errors.Count, $fl.errors[0].line, $fl.errors[0].message) }
                elseif ($prof.flowSha256 -and $sha -ne [string]$prof.flowSha256) { Add-Row 'Flow' 'Flow file' 'fail' "$detail - profile flowSha256 $(Get-Short ([string]$prof.flowSha256)) (the run aborts without -AllowMd5Mismatch)" }
                else { Add-Row 'Flow' 'Flow file' 'ok' "$detail, parses with 0 errors" }
                # commands: the first word of every do= command must be an item of the profile's TruMenu build
                if ($menu) {
                    $mdir = if ($menu.sourceDir) { Resolve-WorkspacePath $menu.sourceDir } else { Join-Path $repo 'work\asi' }
                    $masi = Join-Path $mdir 'TruMenu.asi'
                    if (Test-Path -LiteralPath $masi) {
                        $ids = New-Object 'System.Collections.Generic.HashSet[string]'
                        foreach ($m in [regex]::Matches([Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($masi)), '[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+(?=\x00)')) { [void]$ids.Add($m.Value) }
                        $bad = New-Object System.Collections.Generic.List[string]
                        $nCmd = 0
                        foreach ($s in $fl.steps) {
                            foreach ($c in @(([string]$s.cmds).Split(';') | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
                                $nCmd++
                                $word = $c.Split(' ')[0]
                                if ($word -notlike 'dev.*' -and !$ids.Contains($word)) { $bad.Add("$($s.id): $word") }
                            }
                        }
                        if (!$ids.Contains('flow.next')) { Add-Row 'Flow' 'Flow commands' 'fail' "$($menu.sourceDir)\TruMenu.asi knows no flow.next - not TruMenu 0.11 or later" }
                        elseif ($bad.Count) { Add-Row 'Flow' 'Flow commands' 'fail' ('{0} of {1} command(s) are no item of {2}\TruMenu.asi: {3}' -f $bad.Count, $nCmd, $menu.sourceDir, ($bad -join ', ')) }
                        else { Add-Row 'Flow' 'Flow commands' 'ok' ('{0} command(s), every one an item of {1}\TruMenu.asi (flow.next present)' -f $nCmd, $menu.sourceDir) }
                    }
                    $on = if ($menu.ini -and $menu.ini.Flow) { [string]$menu.ini.Flow.Enabled } else { '' }
                    if ($on -eq '1') { Add-Row 'Flow' '[Flow] Enabled' 'ok' 'the profile sets TruMenu [Flow] Enabled=1' }
                    else { Add-Row 'Flow' '[Flow] Enabled' 'warn' "the profile does not set TruMenu [Flow] Enabled=1 (now '$on') - the flow would not load" }
                }
                else { Add-Row 'Flow' 'Flow commands' 'fail' 'flowFile without TruMenu in the profile asis (the run aborts)' }
                $needTrace = @($fl.watches | Where-Object { $_.file -eq 'TruTrace.log' }).Count
                if ($needTrace -and !@(@($prof.asis) | Where-Object { $_ -and $_.name -eq 'TruTrace' }).Count) {
                    Add-Row 'Flow' 'TruTrace for the flow' 'fail' "$needTrace pattern(s) read TruTrace.log but the profile has no TruTrace"
                }
                elseif ($needTrace) { Add-Row 'Flow' 'TruTrace for the flow' 'ok' "$needTrace pattern(s) on TruTrace.log, TruTrace in the profile" }
            }
            if ($gameOk) {
                $gfp = Join-Path $GamePath 'TruMenu.flow.txt'
                if (Test-Path -LiteralPath $gfp) {
                    $gf = [string]([IO.File]::ReadAllLines($gfp, [Text.Encoding]::UTF8) | Select-Object -First 1)
                    if ($gf.TrimStart([char]0xFEFF).StartsWith($flowMarker)) { Add-Row 'Flow' 'Game folder TruMenu.flow.txt' 'info' ('ours ({0}) - the run replaces it' -f (Get-Short (Get-Sha256 $gfp))) }
                    else { Add-Row 'Flow' 'Game folder TruMenu.flow.txt' 'fail' 'present and not ours (first line) - the run refuses to replace it' }
                }
                else { Add-Row 'Flow' 'Game folder TruMenu.flow.txt' 'ok' 'none - the run installs the profile flow' }
            }
        }
    }
    elseif ($gameOk) {
        $g = Join-Path $GamePath 'TruGuard.asi'
        if (Test-Path -LiteralPath $g) { Add-Row 'TruGuard' 'TruGuard (information only)' 'info' ('installed asi {0}' -f (Get-Sha256 $g)) }
        else { Add-Row 'TruGuard' 'TruGuard (information only)' 'info' 'not installed' }
    }

    # ---- debugger ----
    if (!$CdbPath) { $CdbPath = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Debuggers\x86\cdb.exe' }
    if (Test-Path -LiteralPath $CdbPath) {
        $ver = (Get-Item -LiteralPath $CdbPath).VersionInfo.ProductVersion
        Add-Row 'Debugger' 'cdb.exe (x86)' 'ok' "$CdbPath (version $ver)"
    }
    else { Add-Row 'Debugger' 'cdb.exe (x86)' 'fail' "not found: $CdbPath (pass -CdbPath)" }
    if ($Session) {
        if (Test-Path -LiteralPath $Session) {
            $text = [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $Session).Path)
            $ba = @($text | Where-Object { $_ -match '^\s*ba\s+[rwe]\d' })
            $thrall = @($ba | Where-Object { $_ -match 'THRALLLINK' })
            $dumpDirs = @($text | ForEach-Object { [regex]::Matches($_, '\.dump\s+/\w+\s+(?:/o\s+)?([^;"]+?\.dmp)') } | ForEach-Object { Split-Path -Parent ($_.Groups[1].Value -replace '\\\\', '\') } | Select-Object -Unique)
            $noDir = @($dumpDirs | Where-Object { $_ -and !(Test-Path -LiteralPath $_) })
            $sd = '{0}: {1} data breakpoint(s) ({2} THRALLLINK; max 4 hardware slots), .dump folder(s): {3}' -f (Split-Path -Leaf $Session), $ba.Count, $thrall.Count, $(if ($dumpDirs.Count) { ($dumpDirs -join ', ') } else { 'none' })
            $st = 'ok'
            if ($ba.Count -gt 4) { $st = 'warn'; $sd += ' - more than 4 hardware breakpoints' }
            if ($noDir.Count) { $st = 'fail'; $sd += ' - MISSING dump folder(s): ' + ($noDir -join ', ') }
            Add-Row 'Debugger' 'cdb session file' $st $sd
        }
        else { Add-Row 'Debugger' 'cdb session file' 'fail' "not found: $Session" }
    }
    else { Add-Row 'Debugger' 'cdb session file' 'info' 'no -Session given (a debugger run needs one)' }

    # ---- disk + RAM ----
    $crashDir = Join-Path $env:LOCALAPPDATA 'CrashDumps'
    $driveSeen = @{}
    foreach ($d in @(@{ L = 'game'; P = $(if ($gameOk) { $GamePath } else { $null }) }, @{ L = 'workspace, runs, cdb dumps'; P = $workspace }, @{ L = 'WER crash dumps'; P = $crashDir })) {
        if (!$d.P) { continue }
        $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($d.P))
        if ($driveSeen.ContainsKey($root)) { continue }
        $driveSeen[$root] = $true
        Test-FreeDisk -Label $d.L -Path $d.P
    }
    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem
        $freeRam = [double]$os.FreePhysicalMemory * 1KB
        $totalRam = [double]$os.TotalVisibleMemorySize * 1KB
        $st = if ($freeRam -lt 2GB) { 'fail' } elseif ($freeRam -lt ([double]$MinFreeRamGB * 1GB)) { 'warn' } else { 'ok' }
        Add-Row 'System' 'Free RAM' $st ('{0} free of {1}' -f (Format-GB $freeRam), (Format-GB $totalRam))
        $big = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 2GB } | Sort-Object WorkingSet64 -Descending | Select-Object -First 3)
        if ($big.Count) { Add-Row 'System' 'Large processes (information)' 'info' (($big | ForEach-Object { '{0} PID {1} {2}' -f $_.ProcessName, $_.Id, (Format-GB $_.WorkingSet64) }) -join ', ') }
    }
    catch { Add-Row 'System' 'Free RAM' 'warn' "not readable: $($_.Exception.Message)" }

    # ---- save folder (listed only) ----
    $saveCandidates = @()
    if ($SaveFolder) { $saveCandidates += $SaveFolder }
    else {
        foreach ($docs in @($(if ($env:OneDrive) { Join-Path $env:OneDrive 'Documents' }), $(if ($env:OneDrive) { Join-Path $env:OneDrive 'Dokumente' }), [Environment]::GetFolderPath('MyDocuments'))) {
            if ($docs) { $saveCandidates += (Join-Path $docs 'Eidos\Tomb Raider - Underworld') }
        }
    }
    $saveDir = $saveCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -First 1
    if ($saveDir) {
        $saves = @(Get-ChildItem -LiteralPath $saveDir -Filter '*.TRUSave' -File -Recurse -ErrorAction SilentlyContinue)
        if ($saves.Count) {
            $newest = $saves | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            $size = ($saves | Measure-Object -Property Length -Sum).Sum
            Add-Row 'Saves' 'Save folder' 'ok' ('{0}: {1} *.TRUSave, {2:N0} KB, newest {3} ({4})' -f $saveDir, $saves.Count, ($size / 1KB), $newest.Name, $newest.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
        }
        else { Add-Row 'Saves' 'Save folder' 'warn' "$saveDir present, but no *.TRUSave" }
    }
    else { Add-Row 'Saves' 'Save folder' 'warn' ('not found (tried: {0})' -f ($saveCandidates -join '; ')) }

    # ---- registry (information) ----
    $ld = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\tru.exe' -ErrorAction SilentlyContinue
    if ($ld) {
        $dumps = @(Get-ChildItem -LiteralPath $crashDir -Filter 'tru.exe.*.dmp' -File -ErrorAction SilentlyContinue)
        $dsize = ($dumps | Measure-Object -Property Length -Sum).Sum
        Add-Row 'Registry' 'LocalDumps\tru.exe' 'info' ('still set: DumpType={0} DumpCount={1}{2}; {3} tru.exe dump(s) in CrashDumps ({4}) - remove after the crash hunt (TODO)' -f
            $ld.DumpType, $ld.DumpCount, $(if ($ld.DumpFolder) { " DumpFolder=$($ld.DumpFolder)" } else { '' }), $dumps.Count, (Format-GB ([double]$dsize)))
    }
    else { Add-Row 'Registry' 'LocalDumps\tru.exe' 'info' 'not set' }
    $gfx = Get-ItemProperty -LiteralPath 'HKCU:\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics' -ErrorAction SilentlyContinue
    if ($gfx -and $null -ne $gfx.Fullscreen) { Add-Row 'Registry' 'Graphics\Fullscreen' 'info' ('Fullscreen={0} ({1})' -f $gfx.Fullscreen, $(if ($gfx.Fullscreen -eq 0) { 'windowed - TODO: back to 1 after the tests' } else { 'fullscreen' })) }
    else { Add-Row 'Registry' 'Graphics\Fullscreen' 'info' 'value not found' }

    # ---- table ----
    Write-Log ''
    Write-Log ('Preflight {0}{1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $(if ($RunProfile) { " - profile $RunProfile" } else { '' }))
    Write-Log ''
    Write-Log '| Status | Area | Check | Detail |'
    Write-Log '|---|---|---|---|'
    # icon + word: the Windows PowerShell 5.1 console shows the icons as '?', the UTF-8 log keeps them
    foreach ($r in $rows) { Write-Log ('| {0} {1} | {2} | {3} | {4} |' -f $icons[$r.State], $r.State.ToUpper(), $r.Area, $r.Check, ($r.Detail -replace '\|', '/')) }
    $count = @{}
    foreach ($s in 'ok', 'warn', 'fail', 'info') { $count[$s] = @($rows | Where-Object { $_.State -eq $s }).Count }
    Write-Log ''
    Write-Log ('Result: {0} ok, {1} warn, {2} fail, {3} info - {4}' -f $count.ok, $count.warn, $count.fail, $count.info, $(if ($count.fail) { 'NOT READY (fix the fail rows first)' } elseif ($count.warn) { 'ready with warnings' } else { 'ready' }))
    $script:preflightFail = $count.fail
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
if ($script:preflightFail) { exit 1 }
