<#
.SYNOPSIS
    One regression run of the game: installs the state of a test profile, starts the game (optionally under cdb),
    preloads the TO TEST list over TruLink, waits for the game to end and collects logs, markers and test states.

.DESCRIPTION
    A run is described by a PROFILE (tests\profiles\<name>.json in the repository, format below). The script
      1. aborts if tru.exe is running (it never ends a process),
      2. undoes what its previous run installed (state file <workspace>\runs\installed-state.json: tree installs,
         single mod files, INI backups) - only when no newer tree install of someone else sits on top,
      3. checks the md5 of every profile file that names one (abort on a mismatch unless -AllowMd5Mismatch),
      4. installs exactly that state with the existing scripts: Install-TruTree.ps1 (trees), Install-TruModFile.ps1
         (single files), Set-Tru<Plugin>.ps1 -Install -SourceDir (the profile's ASIs; our other ASIs are removed with
         -Remove unless "removeOtherAsis": false), then the INI overrides and the initial state of INI toggles
         (every INI it edits is backed up first and put back by the next run or -Undo),
      5. records the installed md5s (mods files, ASIs, INIs),
      6. starts the game: plain  cmd /c start "" /b /wait /affinity FFFF tru.exe  (game folder), or with -Debugger
         cdb.exe -G -cf <Session> -logo <run>\cdb.log tru.exe started the same way (affinity FFFF is inherited),
      7. waits for TruLink (127.0.0.1, port from the profile / TruLink.ini, default 9265) and preloads the TO TEST
         rows: menu test.clear, then menu test.step / test.add / test.toggle in profile order, then menu test.export,
      8. waits for the game to exit (-TimeoutMinutes; on a timeout it stops waiting and collects what is there),
      9. collects into <workspace>\runs\<time>_<profile>\: the new part of every Tru*.log of the game folder, the cdb
         log, TruMenu.tests.txt, our INIs after the run, markers (D3DFAIL + hresult, AV2NDCHANCE, FASTFAIL,
STACKOVERFLOW, EXITPROCESS, TERMINATEPROCESS, MESSAGEBOX_A/W), TruGuard markers (TRUGUARD_FAULT /
TRUGUARD_DETAIL / TRUGUARD_RESUME / RESUME_STOP / HANDLED / PREV / DUMP; an unhandled DETAIL counts as a crash even
without a debugger), dump file
         names / sizes newer than the start (copied into <run>\dumps\ - the session's fixed .dump path is
         overwritten by the next run; -NoDumpCopy skips the copy), the installed md5s; writes summary.md and
         summary.json (status table:
         ok / fail / open per row, first crash marker).
     10. evaluates the profile's "expects" (automatic checks: a regex counted in one collected file) and writes the
         section "Automatic checks" plus an overall verdict: PASS = every automatic check ok + no crash marker + every
         owner check (TO TEST check row) ok; FAIL = a failed automatic check, a crash marker or a failed owner check;
         INCOMPLETE = otherwise (file missing, owner checks open / skipped, timeout).
    -Compare <run folder> prints the differences (md5s, markers, test states, automatic checks, verdict) between two
    runs: after a run against the new run, without -RunProfile against -CompareTo (default: the newest other run).
    -Evaluate <run folder> only evaluates an existing run folder again (offline, the game is not needed): markers from
    its cdb.log, rows from its TruMenu.tests.txt, the expects of -RunProfile (default: the folder's profile.json);
    summary.md / summary.json of that folder are rewritten.
    -Undo only undoes the previous run's installs (ASIs stay). -InstallOnly installs and records, then stops.

    Profile (JSON, every path relative to <workspace>, i.e. the folder that holds trudlcport):
      {
        "name": "dlc2_doppelganger", "description": "...",
        "trees": [ { "source": "trudlcport/work/rebuild/x/mods", "exclude": ["local","padshock"],
                     "md5": { "file.drm": "<md5>" } } ],
        "files": [ { "name": "file.drm", "source": "trudlcport/work/x/file.drm", "md5": "<md5>" } ],
        "asis":  [ { "name": "TruShadowPower", "sourceDir": "trudlcport/work/asi/v05",
                     "ini": { "States": { "Enabled": "1" } } } ],
        "removeOtherAsis": true,
        "trulink": { "port": 9265, "waitSeconds": 300 },
        "tests": [ { "kind": "step", "n": 1, "id": "-", "text": "..." },
                   { "kind": "check", "id": "look", "text": "..." },
                   { "kind": "toggle", "id": "sp-states", "target": "ini:TruShadowPower:States:Enabled",
                     "text": "...", "initial": "on" } ]
      }
    "md5" may be null / missing (then only recorded). A toggle's "initial" ("on" / "off") is written to the INI before
    the start (INI toggles take effect at the next start); item toggles ("target": "<menu item id>") are not touched.
    Automatic checks (optional):
        "expects": [ { "id": "sp-on", "file": "TruShadowPower.log", "pattern": "shadow power ON \\(meter",
                       "mode": "present", "min": 1, "text": "...", "optional": false } ]
    "file" is relative to the run folder (TruShadowPower.log, cdb.log, TruMenu.tests.txt, ini-after\x.ini, ...);
    "pattern" is a .NET regex matched per line (case-sensitive); "present" needs at least "min" (default 1) matching
    lines, "absent" needs none. A missing file is shown as a warning. "optional": true = a target that may still fail:
    shown, but not counted in the verdict.

    Every run writes <workspace>\logs\Invoke-TruTestRun_<time>_<mode>.log. -Verbose shows the steps, -Debug paths,
    hashes, command lines and TruLink traffic, -Trace adds a PowerShell line trace.

.PARAMETER RunProfile
    Profile name (tests\profiles\<name>.json) or path of a profile file. Alias -Profile.
.PARAMETER Debugger
    Start the game under cdb.exe with the command file -Session (e.g. a session that logs 2nd-chance AVs, fast fail,
    ExitProcess, the D3D error handler and message boxes and ends with "g").
.PARAMETER Session
    cdb command file for -Debugger.
.PARAMETER CdbPath
    cdb.exe (x86); default: Windows Kits 10 Debuggers\x86\cdb.exe.
.PARAMETER TimeoutMinutes
    Longest wait for the game to exit (default 90). The game is never ended by this script.
.PARAMETER LinkWaitSeconds
    Longest wait for TruLink after the start (default 300; the profile's trulink.waitSeconds wins).
.PARAMETER Compare
    A run folder (path or name below <workspace>\runs) to compare with.
.PARAMETER CompareTo
    Second run folder for -Compare without -RunProfile (default: the newest other run).
.PARAMETER Evaluate
    A run folder (path or name below <workspace>\runs) to evaluate again offline (expects, markers, verdict); the
    expects come from -RunProfile or, without it, from the folder's profile.json.
.PARAMETER AllowMd5Mismatch
    Install even if a profile md5 does not match (the mismatch is noted in the summary).
.PARAMETER NoDumpCopy
    Do not copy the dumps written during the run into <run>\dumps\ (they can be ~600 MB each).
.PARAMETER Undo
    Only undo the installs of the previous run (state file), then stop.
.PARAMETER InstallOnly
    Install and record, do not start the game.
.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.EXAMPLE
    .\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile dlc2_doppelganger -Verbose
.EXAMPLE
    .\scripts\windows\Invoke-TruTestRun.ps1 -RunProfile dlc2_doppelganger -Debugger -Session ..\session_exit.cdb
.EXAMPLE
    .\scripts\windows\Invoke-TruTestRun.ps1 -Compare 20261031_220000_dlc2_doppelganger
.EXAMPLE
    .\scripts\windows\Invoke-TruTestRun.ps1 -Evaluate 20261031_223710_dlc2_48g -RunProfile regress_shadowlara
#>
[CmdletBinding()]
param(
    [Alias('Profile')][string]$RunProfile,
    [switch]$Debugger,
    [string]$Session,
    [string]$CdbPath,
    [ValidateRange(1, 1440)][int]$TimeoutMinutes = 90,
    [ValidateRange(10, 3600)][int]$LinkWaitSeconds = 300,
    [string]$Compare,
    [string]$CompareTo,
    [string]$Evaluate,
    [switch]$AllowMd5Mismatch,
    [switch]$NoDumpCopy,
    [switch]$Undo,
    [switch]$InstallOnly,
    [string]$GamePath,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, Find-TruGamePath, Get-Md5
$commonModule = Join-Path $PSScriptRoot 'TruCommon.psm1'
Import-Module $commonModule -Force -Verbose:$false

$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$workspace = $paths.Workspace
$repo      = $paths.Repository
$runsDir   = Join-Path $workspace 'runs'
$stateFile = Join-Path $runsDir 'installed-state.json'
$backupDir = Join-Path $workspace 'backup'
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
$mode      = if ($Undo) { 'Undo' } elseif ($Evaluate) { 'Evaluate' } elseif ($RunProfile) { if ($InstallOnly) { 'Install' } else { 'Run' } } elseif ($Compare) { 'Compare' } else { 'None' }
New-Item -ItemType Directory -Force -Path $paths.Logs, $runsDir | Out-Null
$logFile = Join-Path $paths.Logs ('Invoke-TruTestRun_{0}_{1}.log' -f $stamp, $mode)
Set-TruLogFile -Path $logFile

# our plugins: name -> install script; every one has -Install / -Remove / -SourceDir / -GamePath
$knownAsis = 'TruDlc2Player', 'TruDoppelganger', 'TruRockVein', 'TruShadowPower', 'TruLink', 'TruGuard', 'TruMenu',
              'TruDataGuard'
# cdb markers (the session file echoes them on a line of their own)
$markerNames = 'D3DFAIL', 'AV2NDCHANCE', 'FASTFAIL', 'STACKOVERFLOW', 'EXITPROCESS', 'TERMINATEPROCESS', 'MESSAGEBOX_A',
               'MESSAGEBOX_W'
$crashMarkers = 'AV2NDCHANCE', 'FASTFAIL', 'STACKOVERFLOW', 'D3DFAIL', 'MESSAGEBOX_A', 'MESSAGEBOX_W', 'TERMINATEPROCESS'
# TruMenu 0.7.2 game.quit: TerminateProcess(own process, 0x544D) by the owner
$truMenuQuitCode = 0x544D
$iconOk   = [string][char]0x2705   # check mark
$iconFail = [string][char]0x274C   # cross
$iconOpen = [string][char]0x23F3   # hourglass
$iconSkip = [string][char]0x2796   # minus
$iconWarn = [string][char]0x26A0 + [string][char]0xFE0F   # warning sign

function Resolve-WorkspacePath {
    # profile paths are relative to <workspace>; absolute paths are refused (no personal paths in profiles)
    param([string]$Relative)
    if (!$Relative) { return $null }
    if ([IO.Path]::IsPathRooted($Relative)) { throw "Profile path must be relative to the workspace: $Relative" }
    return [IO.Path]::GetFullPath((Join-Path $workspace ($Relative -replace '/', '\')))
}

function Invoke-TruScript {
    # runs one of the existing scripts in this session; they set their own log file, so ours is set again after
    param([string]$Name, [hashtable]$Arguments)
    $path = Join-Path $PSScriptRoot $Name
    $text = ($Arguments.GetEnumerator() | ForEach-Object { if ($_.Value -is [switch] -or $_.Value -is [bool]) { "-$($_.Key)" } else { "-$($_.Key) '$($_.Value -join ',')'" } }) -join ' '
    Write-Log "> $Name $text" -Level VERBOSE
    try {
        & $path @Arguments *>&1 | ForEach-Object { Write-Log ('  | {0}' -f $_) -Level DEBUG }
    }
    finally {
        Import-Module $commonModule -Force -Verbose:$false
        Set-TruLogFile -Path $logFile
    }
}

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

function Set-TruIniValue {
    # sets Key=Value in [Section] of an INI (ASCII, CRLF), adds the key / section if missing; keeps comments
    param([string]$Path, [string]$Section, [string]$Key, [string]$Value)
    $lines = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $Path) { foreach ($l in [IO.File]::ReadAllLines($Path)) { $lines.Add($l) } }
    $secStart = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match ('^\s*\[' + [regex]::Escape($Section) + '\]\s*$')) { $secStart = $i; break }
    }
    if ($secStart -lt 0) {
        $lines.Add("[$Section]")
        $lines.Add("$Key=$Value")
    }
    else {
        $secEnd = $lines.Count
        for ($i = $secStart + 1; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*\[') { $secEnd = $i; break } }
        $found = $false
        for ($i = $secStart + 1; $i -lt $secEnd; $i++) {
            if ($lines[$i] -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) { $lines[$i] = "$Key=$Value"; $found = $true; break }
        }
        if (!$found) {
            $at = $secEnd
            while ($at - 1 -gt $secStart -and !$lines[$at - 1].Trim()) { $at-- }
            $lines.Insert($at, "$Key=$Value")
        }
    }
    [IO.File]::WriteAllText($Path, (($lines -join "`r`n") + "`r`n"), (New-Object System.Text.ASCIIEncoding))
}

function Get-TruIniValue {
    param([string]$Path, [string]$Section, [string]$Key)
    if (!(Test-Path -LiteralPath $Path)) { return $null }
    $inSection = $false
    foreach ($l in [IO.File]::ReadAllLines($Path)) {
        if ($l -match '^\s*\[(.+)\]\s*$') { $inSection = $Matches[1] -eq $Section; continue }
        if ($inSection -and $l -match ('^\s*' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) { return $Matches[1].Trim() }
    }
    return $null
}

function Open-TruLink {
    # one connection attempt; returns @{Client; Reader; Writer} or $null
    param([int]$Port, [int]$TimeoutMs = 2000)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (!$pending.AsyncWaitHandle.WaitOne($TimeoutMs)) { $client.Close(); return $null }
        $client.EndConnect($pending)
    }
    catch { $client.Close(); return $null }
    $client.ReceiveTimeout = 15000
    $client.SendTimeout = 15000
    $stream = $client.GetStream()
    $encoding = New-Object System.Text.ASCIIEncoding
    $writer = New-Object System.IO.StreamWriter($stream, $encoding)
    $writer.NewLine = "`n"
    return @{ Client = $client; Reader = (New-Object System.IO.StreamReader($stream, $encoding)); Writer = $writer }
}

function Send-TruLink {
    # one command line -> answer lines (block answers "ok+ ..." up to the line ".")
    param([hashtable]$Link, [string]$Line)
    Write-Log "> $Line" -Level DEBUG
    $Link.Writer.Write($Line + "`n")
    $Link.Writer.Flush()
    $answer = New-Object System.Collections.Generic.List[string]
    $first = $Link.Reader.ReadLine()
    if ($null -eq $first) { throw 'TruLink closed the connection.' }
    $answer.Add($first)
    if ($first.StartsWith('ok+')) {
        while ($true) {
            $next = $Link.Reader.ReadLine()
            if ($null -eq $next -or $next -eq '.') { break }
            $answer.Add($next)
        }
    }
    foreach ($a in $answer) { Write-Log "< $a" -Level DEBUG }
    return ,$answer.ToArray()
}

function Get-TestCommand {
    # profile test row -> TruLink line
    param($Row)
    $text = [string]$Row.text
    switch ([string]$Row.kind) {
        'step' {
            $id = if ($Row.id) { [string]$Row.id } else { '-' }
            return ('menu test.step {0} {1} {2}' -f [int]$Row.n, ($id -replace ' ', ':'), $text)
        }
        'toggle' { return ('menu test.toggle {0} {1} {2}' -f $Row.id, $Row.target, $text) }
        default { return ('menu test.add {0} {1}' -f $Row.id, $text) }
    }
}

function Read-TestFile {
    # TruMenu.tests.txt (0.4: 5 columns, 0.5: 8) -> objects
    param([string]$Path)
    $rows = @()
    if (!$Path -or !(Test-Path -LiteralPath $Path)) { return ,$rows }
    foreach ($l in [IO.File]::ReadAllLines($Path)) {
        if (!$l -or $l.StartsWith('#')) { continue }
        $f = $l.Split("`t")
        $get = { param($i) if ($f.Count -gt $i) { $f[$i] } else { '' } }
        $kind = & $get 5
        if ($kind -ne 'step' -and $kind -ne 'toggle') { $kind = 'check' }
        $rows += [pscustomobject]@{
            id = $f[0]; state = (& $get 1); text = (& $get 2); note = (& $get 3); time = (& $get 4)
            kind = $kind; target = (& $get 6); n = [int](('0' + (& $get 7)) -replace '[^0-9]', '')
        }
    }
    return ,$rows
}

function ConvertTo-RunTests {
    # Read-TestFile rows -> summary rows (with icon); the unary comma keeps a one-row list a list
    param($Rows)
    return ,@(@($Rows) | Where-Object { $_ } | ForEach-Object {
        [ordered]@{ kind = $_.kind; id = $_.id; n = $_.n; target = $_.target; text = $_.text; state = $_.state; note = $_.note; time = $_.time; icon = (Get-RowIcon $_) }
    })
}

function Get-RowIcon {
    param($Row)
    switch ($Row.kind) {
        'step'   { if ($Row.state -eq 'done') { return $iconOk } else { return $iconOpen } }
        'toggle' { return $Row.state }
        default {
            switch ($Row.state) { 'ok' { return $iconOk } 'fail' { return $iconFail } 'skip' { return $iconSkip } default { return $iconOpen } }
        }
    }
}

function Find-Markers {
    # cdb log -> marker list in log order (name, line number, detail)
    param([string]$Path)
    $found = @()
    if (!$Path -or !(Test-Path -LiteralPath $Path)) { return ,$found }
    $lines = [IO.File]::ReadAllLines($Path)
    $pattern = '^\s*(' + ($markerNames -join '|') + ')\s*$'
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -notmatch $pattern) { continue }
        $name = $Matches[1]
        $detail = ''
        $window = ($lines[($i + 1)..([Math]::Min($i + 12, $lines.Count - 1))]) -join "`n"
        if ($name -eq 'D3DFAIL') {
            $hr = [regex]::Match($window, '\b8876[0-9a-f]{4}\b')
            $eax = [regex]::Match($window, 'eax=([0-9a-f]{8})')
            $ecx = [regex]::Match($window, 'ecx=([0-9a-f]{8})')
            $detail = 'hresult {0}; eax={1} ecx={2}' -f $(if ($hr.Success) { '0x' + $hr.Value } else { '?' }),
                $(if ($eax.Success) { $eax.Groups[1].Value } else { '?' }), $(if ($ecx.Success) { $ecx.Groups[1].Value } else { '?' })
        }
        elseif ($name -like 'MESSAGEBOX*') {
            $text = [regex]::Match($window, '"([^"]{1,200})')
            if ($text.Success) { $detail = 'text "' + $text.Groups[1].Value + '"' }
        }
        elseif ($name -eq 'AV2NDCHANCE' -or $name -eq 'FASTFAIL') {
            $eip = [regex]::Match($window, 'eip=([0-9a-f]{8})')
            if ($eip.Success) { $detail = 'eip=' + $eip.Groups[1].Value }
        }
        $found += [pscustomobject]@{ name = $name; line = $i + 1; detail = $detail }
    }
    return ,$found
}

function Find-GuardFaults {
    # TruGuard.log -> marker list in log order (kind, site, code, access, addr, hits, state, dump, line)
    param([string]$Path)
    $found = @()
    if (!$Path -or !(Test-Path -LiteralPath $Path)) { return ,$found }
    $lines = [IO.File]::ReadAllLines($Path)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $m = [regex]::Match($lines[$i], 'TRUGUARD_(FAULT|DETAIL|RESUME|HANDLED|PREV|DUMP|RESUME_STOP)\s+(.*)$')
        if (!$m.Success) { continue }
        $kind = $m.Groups[1].Value
        $rest = $m.Groups[2].Value
        $site = [regex]::Match($rest, 'site=tru\+0x([0-9a-f]+)')
        $dump = [regex]::Match($rest, '(?:^|\s)dump=(.+)$')   # a path may contain spaces, so it is the last field
        $pathField = [regex]::Match($rest, '(?:^|\s)path=(.+)$')
        $newest = [regex]::Match($rest, 'newest=([^\s]+)')
        $count = [regex]::Match($rest, 'count=([0-9]+)')
        if (!$count.Success) { $count = [regex]::Match($rest, '^([0-9]+) resumes') }
        $found += [pscustomobject][ordered]@{
            kind    = $kind
            line    = $i + 1
            site    = $(if ($site.Success) { 'tru+0x' + $site.Groups[1].Value } else { if ($newest.Success) { $newest.Groups[1].Value } else { '?' } })
            code    = (Get-GuardField $rest 'code')
            access  = (Get-GuardField $rest 'access')
            addr    = (Get-GuardField $rest 'addr')
            hits    = $(if ($kind -eq 'HANDLED') { (Get-GuardField $rest 'hits') } elseif ($kind -eq 'PREV') { $count.Groups[1].Value } else { (Get-GuardField $rest 'hits') })
            state   = (Get-GuardField $rest 'state')
            skip    = (Get-GuardField $rest 'skip')
            target  = (Get-GuardField $rest 'to')
            dump    = $(if ($pathField.Success) { $pathField.Groups[1].Value.Trim() } elseif ($dump.Success) { $dump.Groups[1].Value.Trim() } else { '' })
            count   = $(if ($count.Success) { $count.Groups[1].Value } else { '' })
            newest  = $(if ($newest.Success) { $newest.Groups[1].Value } else { '' })
        }
    }
    return ,$found
}

function Get-GuardField {
    param([string]$Text, [string]$Name)
    $m = [regex]::Match($Text, '(?:^|\s)' + [regex]::Escape($Name) + '=([^\s]+)')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Get-GuardCrash {
    # a DETAIL with state=unhandled is a fatal fault in tru.exe, with or without cdb
    param($Faults)
    $f = @($Faults) | Where-Object { $_ -and $_.kind -eq 'DETAIL' -and $_.state -eq 'unhandled' } | Select-Object -First 1
    if ($f) { return ('TRUGUARD_UNHANDLED (line {0}) {1} {2} {3}' -f $f.line, $f.site, $f.code, $f.addr) }
    return $null
}

function Resolve-RunFolder {
    param([string]$Name)
    if (!$Name) { return $null }
    if (Test-Path -LiteralPath $Name -PathType Container) { return (Resolve-Path -LiteralPath $Name).Path }
    $candidate = Join-Path $runsDir $Name
    if (Test-Path -LiteralPath $candidate -PathType Container) { return $candidate }
    throw "Run folder not found: $Name"
}

function Read-TruProfile {
    # profile name (tests\profiles\<name>.json) or path -> @{ Path; Data; Name }; checks the expects definitions
    param([string]$NameOrPath)
    $path = if ($NameOrPath -match '[\\/]' -or $NameOrPath -like '*.json') { $NameOrPath } else { Join-Path $repo "tests\profiles\$NameOrPath.json" }
    if (!(Test-Path -LiteralPath $path)) { throw "Profile not found: $path" }
    $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $name = if ($data.name) { [string]$data.name } else { [IO.Path]::GetFileNameWithoutExtension($path) }
    if ($name -notmatch '^[A-Za-z0-9_.-]+$') { throw "Profile name '$name' must be letters, digits, _ . - only." }
    Test-ExpectDefinition -Expects $data.expects -Source $path
    return @{ Path = (Resolve-Path -LiteralPath $path).Path; Data = $data; Name = $name }
}

function Test-ExpectDefinition {
    # throws on a bad "expects" list (before anything is installed): unique id, relative file, valid regex and mode
    param($Expects, [string]$Source)
    $ids = @{}
    foreach ($e in @($Expects)) {
        if (!$e) { continue }
        $id = [string]$e.id
        if (!$id) { throw "$Source : an expect without id" }
        if ($ids[$id]) { throw "$Source : expect id '$id' twice" }
        $ids[$id] = $true
        $file = [string]$e.file
        if (!$file -or [IO.Path]::IsPathRooted($file) -or $file -match '(^|[\\/])\.\.([\\/]|$)') { throw "$Source : expect '$id' needs a file relative to the run folder (got '$file')" }
        if ($e.mode -and @('present', 'absent') -notcontains [string]$e.mode) { throw "$Source : expect '$id' mode must be present or absent (got '$($e.mode)')" }
        if ($null -ne $e.min -and [int]$e.min -lt 1) { throw "$Source : expect '$id' min must be 1 or more" }
        try { $null = New-Object System.Text.RegularExpressions.Regex ([string]$e.pattern) }
        catch { throw "$Source : expect '$id' pattern is not a valid regex: $($_.Exception.Message)" }
        if (![string]$e.pattern) { throw "$Source : expect '$id' has an empty pattern" }
    }
}

function Test-TruExpects {
    # evaluates the expects against the files of a run folder -> list of results (one per expect, profile order)
    param($Expects, [string]$Folder)
    $results = @()
    $cache = @{}
    foreach ($e in @($Expects)) {
        if (!$e) { continue }
        $mode = if ($e.mode) { [string]$e.mode } else { 'present' }
        $min = if ($null -ne $e.min) { [int]$e.min } else { 1 }
        $path = Join-Path $Folder ([string]$e.file -replace '/', '\')
        $r = [ordered]@{
            id = [string]$e.id; file = [string]$e.file; pattern = [string]$e.pattern; mode = $mode; min = $min
            text = [string]$e.text; optional = [bool]$e.optional; result = 'missing'; icon = $iconWarn; hits = 0
            line = $null; evidence = ''
        }
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            if (!$cache.ContainsKey($path)) { $cache[$path] = [IO.File]::ReadAllLines($path) }
            $lines = $cache[$path]
            $rx = New-Object System.Text.RegularExpressions.Regex ([string]$e.pattern)
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if (!$rx.IsMatch($lines[$i])) { continue }
                $r['hits'] = $r['hits'] + 1
                if ($null -eq $r.line) {
                    $r.line = $i + 1
                    $t = $lines[$i].Trim()
                    $r.evidence = if ($t.Length -gt 140) { $t.Substring(0, 140) + '...' } else { $t }
                }
            }
            $ok = if ($mode -eq 'absent') { $r.hits -eq 0 } else { $r.hits -ge $min }
            $r.result = if ($ok) { 'ok' } else { 'fail' }
            $r.icon = if ($ok) { $iconOk } else { $iconFail }
        }
        Write-Log ('check {0}: {1} ({2} matching lines in {4}, wanted {3})' -f $r.id, $r.result, $r.hits, $mode, $r.file) -Level VERBOSE
        $results += $r
    }
    return ,$results
}

function Test-TruMenuQuitLog {
    # TruMenu.log of a run folder names an owner game.quit -> the cdb TERMINATEPROCESS marker is that quit, not a crash
    param([string]$Folder)
    $log = Join-Path $Folder 'TruMenu.log'
    return [bool]((Test-Path -LiteralPath $log) -and (Select-String -LiteralPath $log -SimpleMatch 'game.quit by the owner' -Quiet))
}

function Get-FirstCrash {
    # first crash marker of the cdb log, else a crash exit code; $null = none. -QuitByOwner: TERMINATEPROCESS is the
    # owner's TruMenu game.quit (under the debugger the exit code comes from cdb, so the marker is the only trace)
    param($Markers, $ExitCode, [switch]$QuitByOwner)
    $first = @($Markers) | Where-Object { $_ -and $crashMarkers -contains $_.name -and !($QuitByOwner -and $_.name -eq 'TERMINATEPROCESS') } |
        Select-Object -First 1
    if ($first) { return ('{0} (line {1}) {2}' -f $first.name, $first.line, $first.detail) }
    if ($null -ne $ExitCode -and [long]$ExitCode -ne 0) {
        $hex = '0x{0:x8}' -f ([long]$ExitCode -band 0xffffffffL)
        $named = switch ($hex) { '0xc0000005' { 'AV (exit code)' } '0xc0000409' { 'FASTFAIL (exit code)' } '0xc00000fd' { 'STACKOVERFLOW (exit code)' } default { $null } }
        if ($named) { return "$named $hex" }
    }
    return $null
}

function Test-TruMenuQuit {
    # exit code 0x544D (21581) = the owner ended the game with TruMenu game.quit (TerminateProcess) - not a crash
    param($ExitCode)
    return ($null -ne $ExitCode -and "$ExitCode" -ne '' -and ([long]$ExitCode -band 0xffffffffL) -eq $truMenuQuitCode)
}

function Set-RunVerdict {
    # automatic checks + crash marker + owner checks -> $Run.expects / verdict / verdictIcon / verdictNotes
    param([hashtable]$Run, $Expects, [string]$Folder)
    $results = @(Test-TruExpects -Expects $Expects -Folder $Folder | ForEach-Object { $_ })
    $Run.expects = $results
    $required = @($results | Where-Object { !$_.optional })
    $failed   = @($required | Where-Object { $_.result -eq 'fail' }).Count
    $missing  = @($required | Where-Object { $_.result -eq 'missing' }).Count
    $optOpen  = @($results | Where-Object { $_.optional -and $_.result -ne 'ok' }).Count
    $checks   = @(@($Run.tests) | Where-Object { $_ -and $_.kind -eq 'check' })
    $cFail    = @($checks | Where-Object { $_.state -eq 'fail' }).Count
    $cOk      = @($checks | Where-Object { $_.state -eq 'ok' }).Count
    $cOther   = $checks.Count - $cFail - $cOk
    $notes = New-Object System.Collections.Generic.List[string]
    if ($Run.firstCrash) { $notes.Add("crash marker $($Run.firstCrash)") }
    if (Test-TruMenuQuit $Run.exitCode) { $notes.Add('ended via TruMenu game.quit (exit code 0x544D, not a crash)') }
    $firstChanceSites = @($Run.guard | Where-Object { $_ -and $_.kind -eq 'DETAIL' -and $_.state -eq 'firstchance' })
    if ($firstChanceSites.Count) { $notes.Add("$($firstChanceSites.Count) first-chance fault site(s) recorded (see TruGuard faults)") }
    $notes.Add(('automatic checks {0}/{1} ok{2}{3}' -f @($required | Where-Object { $_.result -eq 'ok' }).Count, $required.Count,
        $(if ($failed) { ", $failed failed" }), $(if ($missing) { ", $missing without their file" })))
    if (!$checks.Count) { $notes.Add('no owner checks collected') }
    else { $notes.Add(('owner checks {0}/{1} ok{2}{3}' -f $cOk, $checks.Count, $(if ($cFail) { ", $cFail failed" }), $(if ($cOther) { ", $cOther open / skipped" }))) }
    if ($Run.timedOut) { $notes.Add('timeout - game still running') }
    if ($optOpen) { $notes.Add("$optOpen optional target(s) not met (not counted)") }
    if ($Run.firstCrash -or $failed -or $cFail) { $Run.verdict = 'FAIL'; $Run.verdictIcon = $iconFail }
    elseif ($missing -or !$checks.Count -or $cOther -or $Run.timedOut) { $Run.verdict = 'INCOMPLETE'; $Run.verdictIcon = $iconWarn }
    else { $Run.verdict = 'PASS'; $Run.verdictIcon = $iconOk }
    $Run.verdictNotes = $notes -join '; '
    Write-Log "Verdict: $($Run.verdict) - $($Run.verdictNotes)"
}

function Compare-TruRun {
    # prints (and returns) the differences between two runs' summary.json
    param([string]$Old, [string]$New)
    $a = Get-Content -LiteralPath (Join-Path $Old 'summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $b = Get-Content -LiteralPath (Join-Path $New 'summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $out = New-Object System.Collections.Generic.List[string]
    $out.Add(('Compare {0} ({1}, {2}) -> {3} ({4}, {5})' -f (Split-Path -Leaf $Old), $a.profile, $a.status,
        (Split-Path -Leaf $New), $b.profile, $b.status))
    $ma = @{}; foreach ($m in @($a.installed)) { if ($m) { $ma[$m.path] = $m.md5 } }
    $mb = @{}; foreach ($m in @($b.installed)) { if ($m) { $mb[$m.path] = $m.md5 } }
    foreach ($k in (@($ma.Keys) + @($mb.Keys) | Sort-Object -Unique)) {
        if ($ma[$k] -ne $mb[$k]) { $out.Add(('  md5     {0}: {1} -> {2}' -f $k, $(if ($ma[$k]) { $ma[$k] } else { '-' }), $(if ($mb[$k]) { $mb[$k] } else { '-' }))) }
    }
    $ca = @{}; foreach ($m in @($a.markers)) { if ($m) { $ca[$m.name] = 1 + [int]$ca[$m.name] } }
    $cb = @{}; foreach ($m in @($b.markers)) { if ($m) { $cb[$m.name] = 1 + [int]$cb[$m.name] } }
    foreach ($k in (@($ca.Keys) + @($cb.Keys) | Sort-Object -Unique)) {
        if ([int]$ca[$k] -ne [int]$cb[$k]) { $out.Add(('  marker  {0}: {1} -> {2}' -f $k, [int]$ca[$k], [int]$cb[$k])) }
    }
    if ($a.firstCrash -ne $b.firstCrash) { $out.Add(('  first crash marker: {0} -> {1}' -f $(if ($a.firstCrash) { $a.firstCrash } else { '-' }), $(if ($b.firstCrash) { $b.firstCrash } else { '-' }))) }
    # TruGuard sites with their state (firstchance / unhandled / resumed) - a site that switches to "unhandled"
    # is the difference that matters between a run that survived and one that crashed
    $ga = @{}; foreach ($g in @($a.guard)) { if ($g -and $g.kind -eq 'DETAIL') { $ga["$($g.site) $($g.state)"] = 1 } }
    $gb = @{}; foreach ($g in @($b.guard)) { if ($g -and $g.kind -eq 'DETAIL') { $gb["$($g.site) $($g.state)"] = 1 } }
    foreach ($k in (@($ga.Keys) + @($gb.Keys) | Sort-Object -Unique)) {
        if (!$ga[$k] -or !$gb[$k]) { $out.Add(('  guard   {0}: {1} -> {2}' -f $k, $(if ($ga[$k]) { 'yes' } else { '-' }), $(if ($gb[$k]) { 'yes' } else { '-' }))) }
    }
    if ($a.exitCode -ne $b.exitCode) { $out.Add(('  exit code: {0} -> {1}' -f $a.exitCode, $b.exitCode)) }
    $ta = @{}; foreach ($r in @($a.tests)) { if ($r) { $ta[$r.id] = $r } }
    $tb = @{}; foreach ($r in @($b.tests)) { if ($r) { $tb[$r.id] = $r } }
    foreach ($k in (@($ta.Keys) + @($tb.Keys) | Sort-Object -Unique)) {
        $sa = if ($ta[$k]) { $ta[$k].state } else { '-' }
        $sb = if ($tb[$k]) { $tb[$k].state } else { '-' }
        if ($sa -ne $sb) { $out.Add(('  test    {0}: {1} -> {2}' -f $k, $sa, $sb)) }
    }
    # automatic checks (runs before the expects feature have none: shown as '-')
    $ea = @{}; foreach ($e in @($a.expects)) { if ($e) { $ea[$e.id] = $e } }
    $eb = @{}; foreach ($e in @($b.expects)) { if ($e) { $eb[$e.id] = $e } }
    foreach ($k in (@($ea.Keys) + @($eb.Keys) | Sort-Object -Unique)) {
        $sa = if ($ea[$k]) { '{0} ({1} lines)' -f $ea[$k].result, $ea[$k].hits } else { '-' }
        $sb = if ($eb[$k]) { '{0} ({1} lines)' -f $eb[$k].result, $eb[$k].hits } else { '-' }
        if ($sa -ne $sb) { $out.Add(('  check   {0}: {1} -> {2}' -f $k, $sa, $sb)) }
    }
    if ($a.verdict -ne $b.verdict) { $out.Add(('  verdict: {0} -> {1}' -f $(if ($a.verdict) { $a.verdict } else { '-' }), $(if ($b.verdict) { $b.verdict } else { '-' }))) }
    if ($out.Count -eq 1) { $out.Add('  no differences in md5s, markers, exit code, test states, automatic checks and verdict') }
    foreach ($l in $out) { Write-Log $l }
    return ,$out.ToArray()
}

function Undo-PreviousInstall {
    # undoes what the previous run installed (state file); refuses when a newer tree install sits on top
    if (!(Test-Path -LiteralPath $stateFile)) { Write-Log 'No previous harness install to undo.' -Level VERBOSE; return }
    $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Log "Undoing the installs of run $($state.run) ($($state.time))"
    $ours = @(@($state.trees) | Where-Object { $_ })
    if ($ours.Count) {
        $open = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notlike '*.restored' } | Sort-Object Name)
        $newest = [string](@($ours | Sort-Object)[-1])      # @() - with one tree [-1] would index the last character
        $foreign = @($open | Where-Object { $_.Name -gt $newest -and $ours -notcontains $_.Name })
        if ($foreign.Count) {
            throw (("A newer tree install ({0}) sits on top of the previous harness run - undo it first " +
                    "(Install-TruTree.ps1 -Restore) or delete {1} if that state is wanted.") -f ($foreign.Name -join ', '), $stateFile)
        }
    }
    foreach ($ini in @($state.inis)) {
        if (!$ini) { continue }
        $bk = Join-Path $workspace $ini.backup
        if ($ini.existed -and (Test-Path -LiteralPath $bk)) {
            Copy-Item -LiteralPath $bk -Destination $ini.path -Force
            Write-Log "INI restored: $($ini.path)" -Level VERBOSE
        }
        elseif (!$ini.existed -and (Test-Path -LiteralPath $ini.path)) {
            Write-Log "INI $($ini.path) did not exist before the previous run - left in place (Set-Tru*.ps1 -Remove handles it)." -Level WARN
        }
    }
    foreach ($f in @($state.files)) {
        if (!$f) { continue }
        Invoke-TruScript 'Install-TruModFile.ps1' @{ Name = $f.name; Restore = $true; BackupMd5 = $f.backupMd5; GamePath = $GamePath }
    }
    [array]::Reverse($ours)
    foreach ($t in $ours) {
        if (Test-Path -LiteralPath (Join-Path $backupDir $t)) {
            Invoke-TruScript 'Install-TruTree.ps1' @{ Restore = $true; BackupName = $t; GamePath = $GamePath }
        }
        else { Write-Log "Tree backup $t is gone or already restored - skipped." -Level WARN }
    }
    Remove-Item -LiteralPath $stateFile
    Write-Log 'Previous harness install undone.'
}

function Write-RunSummary {
    param([hashtable]$Run, [string]$Folder)
    $Run | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Folder 'summary.json') -Encoding UTF8
    $md = New-Object System.Collections.Generic.List[string]
    $md.Add("# Test run $($Run.profile) - $($Run.start)")
    $md.Add('')
    if ($Run.verdict) {
        $md.Add("**Verdict: $($Run.verdictIcon) $($Run.verdict)** - $($Run.verdictNotes)")
        $md.Add('')
    }
    $md.Add('| Item | Value |')
    $md.Add('|---|---|')
    $md.Add("| Status | $($Run.statusIcon) $($Run.status) |")
    $md.Add("| First crash marker | $(if ($Run.firstCrash) { $Run.firstCrash } else { '-' }) |")
    $md.Add("| Start / end | $($Run.start) / $($Run.end) |")
    $md.Add("| Mode | $($Run.mode) |")
    $md.Add("| Exit code | $($Run.exitCode)$(if (Test-TruMenuQuit $Run.exitCode) { ' (0x544D: ended via TruMenu game.quit)' }) |")
    $md.Add("| TruLink preload | $($Run.preload) |")
    $md.Add("| md5 notes | $(if ($Run.md5Notes.Count) { $Run.md5Notes -join '; ' } else { 'all as in the profile' }) |")
    if ($Run.expectsFrom) { $md.Add("| Automatic checks from | $($Run.expectsFrom) |") }
    $md.Add('')
    if ($Run.verdict) {
        $md.Add('## Automatic checks')
        $md.Add('')
        $md.Add('| # | Result | Id | Check | File | Expected | Lines | First match |')
        $md.Add('|---|---|---|---|---|---|---|---|')
        $i = 0
        foreach ($e in @($Run.expects)) {
            if (!$e) { continue }
            $i++
            $want = if ($e.mode -eq 'absent') { 'absent' } else { "present, at least $($e.min)" }
            $res = '{0} {1}{2}' -f $e.icon, $(if ($e.result -eq 'missing') { 'file missing' } else { $e.result }), $(if ($e.optional) { ' (optional target)' } else { '' })
            $first = if ($e.line) { 'line {0}: `{1}`' -f $e.line, ($e.evidence -replace '`', "'" -replace '\|', '\|') } else { '-' }
            $md.Add(('| {0} | {1} | {2} | {3} | {4} | {5} `{6}` | {7} | {8} |' -f $i, $res, $e.id, ($e.text -replace '\|', '/'), $e.file,
                $want, ($e.pattern -replace '\|', '\|'), $e.hits, $first))
        }
        if (!$i) { $md.Add('| - | - | - | the profile has no expects | - | - | - | - |') }
        $md.Add('')
    }
    $md.Add('## TO TEST rows (after the run)')
    $md.Add('')
    $md.Add('| # | Kind | Id | Text | State | Note | Time |')
    $md.Add('|---|---|---|---|---|---|---|')
    $i = 0
    foreach ($r in @($Run.tests)) {
        if (!$r) { continue }
        $i++
        $num = if ($r.kind -eq 'step') { "step $($r.n)" } else { $r.kind }
        $target = if ($r.target) { " ($($r.target))" } else { '' }
        $md.Add(('| {0} | {1} | {2} | {3}{4} | {5} {6} | {7} | {8} |' -f $i, $num, $r.id, ($r.text -replace '\|', '/'), $target,
            $r.icon, $r.state, ($r.note -replace '\|', '/'), $r.time))
    }
    if (!$i) { $md.Add('| - | - | - | no TruMenu.tests.txt collected | - | - | - |') }
    $md.Add('')
    $md.Add('## Markers (cdb log)')
    $md.Add('')
    $md.Add('| # | Marker | Line | Detail |')
    $md.Add('|---|---|---|---|')
    $i = 0
    foreach ($m in @($Run.markers)) { if ($m) { $i++; $md.Add("| $i | $($m.name) | $($m.line) | $($m.detail) |") } }
    if (!$i) { $md.Add("| - | none | - | $(if ($Run.mode -like 'debugger*') { 'cdb log without markers' } else { 'plain start: no cdb log' }) |") }
    $md.Add('')
    if ($Run.ContainsKey('guard')) {
        $md.Add('## TruGuard faults (TruGuard.log)')
        $md.Add('')
        $md.Add('| # | Kind | Site | Code | Access | Address | Hits/Count | State | Dump |')
        $md.Add('|---|---|---|---|---|---|---|---|---|')
        $i = 0
        foreach ($g in @($Run.guard)) {
            if (!$g) { continue }
            $i++
            if ($g.kind -eq 'RESUME') {
                $md.Add(('| {0} | RESUME | {1} | - | - | skip {2} to {3} | - | - | - |' -f $i, $g.site, $g.skip, $g.target))
            }
            elseif ($g.kind -eq 'RESUME_STOP') {
                $md.Add(('| {0} | STOP | - | - | - | {1} resumes in 1 s | - | - | - |' -f $i, $g.count))
            }
            elseif ($g.kind -eq 'HANDLED') {
                $md.Add(('| {0} | HANDLED | {1} | - | - | - | {2} | - | - |' -f $i, $g.site, $g.hits))
            }
            elseif ($g.kind -eq 'PREV') {
                $md.Add(('| {0} | PREV | {1} | - | - | - | {2} | - | - |' -f $i, $g.site, $g.count))
            }
            elseif ($g.kind -eq 'DUMP') {
                $md.Add(('| {0} | DUMP | - | - | - | - | - | manual | {1} |' -f $i, $(if ($g.dump) { $g.dump } else { '-' })))
            }
            else {
                $md.Add(('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f $i, $g.kind, $g.site, $g.code,
                    $g.access, $g.addr, $g.hits, $g.state, $(if ($g.dump) { $g.dump } else { '-' })))
            }
        }
        if (!$i) { $md.Add('| - | none | - | - | - | - | - | - | no TRUGUARD_* lines |') }
        $md.Add('')
    }
    $md.Add('## Installed (md5)')
    $md.Add('')
    $md.Add('| File | md5 | Expected |')
    $md.Add('|---|---|---|')
    foreach ($f in @($Run.installed)) { if ($f) { $md.Add("| $($f.path) | $($f.md5) | $(if ($f.expected) { if ($f.expected -eq $f.md5) { $iconOk } else { $iconFail + ' ' + $f.expected } } else { '-' }) |") } }
    $md.Add('')
    $md.Add('## Dumps and collected files')
    $md.Add('')
    foreach ($d in @($Run.dumps)) { if ($d) { $md.Add("- dump $($d.path) ($($d.size) bytes, $($d.time))$(if ($d.copy) { ", copy $($d.copy)" })") } }
    if (!@($Run.dumps | Where-Object { $_ }).Count) { $md.Add('- no dump newer than the start') }
    foreach ($c in @($Run.collected)) { if ($c) { $md.Add("- $c") } }
    $md.Add('')
    Set-Content -LiteralPath (Join-Path $Folder 'summary.md') -Value $md -Encoding UTF8
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Invoke-TruTestRun mode=$mode profile=$RunProfile debugger=$Debugger log=$logFile" -Level VERBOSE

    if ($Evaluate) {
        # offline: evaluate an existing run folder again (no game, nothing installed)
        $folder = Resolve-RunFolder $Evaluate
        $p = if ($RunProfile) { Read-TruProfile $RunProfile } else {
            $pj = Join-Path $folder 'profile.json'
            if (!(Test-Path -LiteralPath $pj)) { throw "$folder has no profile.json - pass -RunProfile." }
            Read-TruProfile $pj
        }
        $run = @{}
        $sj = Join-Path $folder 'summary.json'
        if (Test-Path -LiteralPath $sj) {
            $old = Get-Content -LiteralPath $sj -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($prop in $old.PSObject.Properties) { $run[$prop.Name] = $prop.Value }
        }
        else {
            $run = @{ profile = $p.Name; start = '?'; end = '?'; status = 'unknown (no summary.json)'; statusIcon = $iconOpen; mode = 'unknown'
                      exitCode = $null; preload = 'unknown'; firstCrash = $null; markers = @(); guard = @(); tests = @(); dumps = @(); collected = @()
                      installed = @(); md5Notes = @() }
        }
        $cdb = Join-Path $folder 'cdb.log'
        if (Test-Path -LiteralPath $cdb) {
            $run.markers = @(Find-Markers $cdb | ForEach-Object { $_ })
            $run.firstCrash = Get-FirstCrash -Markers $run.markers -ExitCode $run.exitCode -QuitByOwner:(Test-TruMenuQuitLog $folder)
        }
        $run.guard = @(Find-GuardFaults (Join-Path $folder 'TruGuard.log') | ForEach-Object { $_ })
        $guardCrash = Get-GuardCrash $run.guard
        if (!$run.firstCrash -and $guardCrash) { $run.firstCrash = $guardCrash }
        $testRows = Read-TestFile (Join-Path $folder 'TruMenu.tests.txt')
        if ($testRows.Count) { $run.tests = ConvertTo-RunTests $testRows }
        $run.expectsFrom = '{0} (evaluated offline {1})' -f $p.Name, (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        Set-RunVerdict -Run $run -Expects $p.Data.expects -Folder $folder
        Write-RunSummary -Run $run -Folder $folder
        Write-Log "Run folder evaluated: $folder (summary.md, summary.json)"
        if ($Compare) {
            $diff = Compare-TruRun -Old (Resolve-RunFolder $Compare) -New $folder
            Set-Content -LiteralPath (Join-Path $folder 'compare.txt') -Value $diff -Encoding UTF8
        }
        return
    }

    if (!$RunProfile -and !$Undo) {
        if (!$Compare) { throw 'Pass -RunProfile <name> (a run), -Undo, or -Compare <run folder>.' }
        $old = Resolve-RunFolder $Compare
        $new = if ($CompareTo) { Resolve-RunFolder $CompareTo } else {
            $other = @(Get-ChildItem -LiteralPath $runsDir -Directory | Where-Object { $_.FullName -ne $old -and (Test-Path -LiteralPath (Join-Path $_.FullName 'summary.json')) } | Sort-Object Name)
            if (!$other.Count) { throw 'No other run folder with summary.json to compare with.' }
            $other[-1].FullName
        }
        Compare-TruRun -Old $old -New $new | Out-Null
        return
    }

    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) {
        throw 'Tomb Raider: Underworld (tru.exe) is running. Please close the game first - this script never ends it.'
    }
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) { throw "Game folder not found (-GamePath): $GamePath" }
    Write-Log "Game folder: $GamePath" -Level VERBOSE

    if ($Undo) { Undo-PreviousInstall; return }

    # ---- profile ----
    $profInfo = Read-TruProfile $RunProfile
    $profilePath = $profInfo.Path
    $prof = $profInfo.Data
    $profName = $profInfo.Name
    Write-Log "Profile $profName from $profilePath" -Level VERBOSE
    if ($Debugger) {
        if (!$Session -or !(Test-Path -LiteralPath $Session)) { throw "-Debugger needs -Session <cdb command file> (not found: $Session)" }
        $Session = (Resolve-Path -LiteralPath $Session).Path
        if (!$CdbPath) { $CdbPath = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Debuggers\x86\cdb.exe' }
        if (!(Test-Path -LiteralPath $CdbPath)) { throw "cdb.exe not found: $CdbPath (pass -CdbPath, x86 debugger)" }
    }

    # ---- md5 check of the profile sources (before anything is changed) ----
    $md5Notes = New-Object System.Collections.Generic.List[string]
    $treePlans = @()
    foreach ($t in @($prof.trees)) {
        if (!$t) { continue }
        $src = Resolve-WorkspacePath $t.source
        if (!(Test-Path -LiteralPath $src -PathType Container)) { throw "Tree source not found: $($t.source)" }
        $exclude = if ($null -ne $t.exclude) { @($t.exclude) } else { @('local', 'padshock') }
        $expect = @{}
        if ($t.md5) { foreach ($p in $t.md5.PSObject.Properties) { $expect[($p.Name -replace '/', '\')] = [string]$p.Value } }
        foreach ($k in $expect.Keys) {
            $f = Join-Path $src $k
            if (!(Test-Path -LiteralPath $f)) { throw "Tree $($t.source) lacks $k (named in its md5 list)" }
            $m = Get-Md5 $f
            if ($expect[$k] -and $m -ne $expect[$k]) { $md5Notes.Add("$($t.source)/$k is $m, profile says $($expect[$k])") }
        }
        $treePlans += [pscustomobject]@{ Source = $src; Relative = $t.source; Exclude = $exclude; Expect = $expect }
    }
    $filePlans = @()
    foreach ($f in @($prof.files)) {
        if (!$f) { continue }
        $src = Resolve-WorkspacePath $f.source
        if (!(Test-Path -LiteralPath $src -PathType Leaf)) { throw "File source not found: $($f.source)" }
        $m = Get-Md5 $src
        if ($f.md5 -and $m -ne [string]$f.md5) { $md5Notes.Add("$($f.source) is $m, profile says $($f.md5)") }
        $filePlans += [pscustomobject]@{ Name = ([string]$f.name -replace '/', '\'); Source = $src; Expect = [string]$f.md5 }
    }
    $asiPlans = @()
    foreach ($a in @($prof.asis)) {
        if (!$a) { continue }
        if ($knownAsis -notcontains $a.name) { throw "Unknown ASI '$($a.name)' (known: $($knownAsis -join ', '))" }
        $dir = if ($a.sourceDir) { Resolve-WorkspacePath $a.sourceDir } else { Join-Path $repo 'work\asi' }
        $asiFile = Join-Path $dir "$($a.name).asi"
        if (!(Test-Path -LiteralPath $asiFile)) { throw "$($a.name).asi not found in $dir (build it first)" }
        if ($a.sha256 -and (Get-Sha256 $asiFile) -ne [string]$a.sha256) { $md5Notes.Add("$($a.sourceDir)/$($a.name).asi sha256 is $(Get-Sha256 $asiFile), profile says $($a.sha256)") }
        $asiPlans += [pscustomobject]@{ Name = [string]$a.name; SourceDir = $dir; Ini = $a.ini; Expect = [string]$a.sha256 }
    }
    foreach ($n in $md5Notes) { Write-Log "md5 mismatch: $n" -Level WARN }
    if ($md5Notes.Count -and !$AllowMd5Mismatch) { throw "$($md5Notes.Count) md5 mismatch(es) against the profile - nothing changed (-AllowMd5Mismatch to go on)." }

    # ---- undo the previous run, then install exactly this profile ----
    Undo-PreviousInstall
    $runFolder = Join-Path $runsDir ('{0}_{1}' -f $stamp, $profName)
    New-Item -ItemType Directory -Force -Path $runFolder, (Join-Path $runFolder 'ini-before'), (Join-Path $runFolder 'ini-after') | Out-Null
    Copy-Item -LiteralPath $profilePath -Destination (Join-Path $runFolder 'profile.json')
    $runRel = $runFolder.Substring($workspace.Length).TrimStart('\')
    $state = [ordered]@{ run = $runRel; time = (Get-Date -Format 's'); trees = @(); files = @(); inis = @() }
    $saveState = { $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $stateFile -Encoding UTF8 }

    foreach ($t in $treePlans) {
        $before = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
        Invoke-TruScript 'Install-TruTree.ps1' @{ Source = $t.Source; Exclude = $t.Exclude; GamePath = $GamePath }
        $new = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' -ErrorAction SilentlyContinue |
            Where-Object { $before -notcontains $_.Name } | Sort-Object Name | ForEach-Object { $_.Name })
        if ($new.Count) { $state.trees += $new[-1]; & $saveState; Write-Log "Tree $($t.Relative) installed (backup $($new[-1]))." }
        else { Write-Log "Tree $($t.Relative): nothing to install (already equal)." }
    }
    foreach ($f in $filePlans) {
        $target = Join-Path $GamePath "mods\$($f.Name)"
        $beforeMd5 = if (Test-Path -LiteralPath $target) { Get-Md5 $target } else { $null }
        Invoke-TruScript 'Install-TruModFile.ps1' @{ Name = $f.Name; Source = $f.Source; GamePath = $GamePath }
        if ($beforeMd5 -and $beforeMd5 -ne (Get-Md5 $f.Source)) {
            $state.files += [ordered]@{ name = $f.Name; backupMd5 = $beforeMd5 }
            & $saveState
        }
    }
    foreach ($n in $knownAsis) {
        $plan = $asiPlans | Where-Object { $_.Name -eq $n }
        if ($plan) { Invoke-TruScript "Set-$n.ps1" @{ Install = $true; SourceDir = $plan.SourceDir; GamePath = $GamePath } }
        elseif ($prof.removeOtherAsis -ne $false) { Invoke-TruScript "Set-$n.ps1" @{ Remove = $true; GamePath = $GamePath } }
    }

    # INI overrides + initial toggle states; every INI that gets edited is backed up first
    $iniEdits = @{}
    foreach ($a in $asiPlans) {
        if (!$a.Ini) { continue }
        foreach ($sec in $a.Ini.PSObject.Properties) {
            foreach ($key in $sec.Value.PSObject.Properties) {
                $iniEdits["$($a.Name)|$($sec.Name)|$($key.Name)"] = [string]$key.Value
            }
        }
    }
    foreach ($r in @($prof.tests)) {
        if (!$r -or $r.kind -ne 'toggle' -or !$r.initial) { continue }
        if ([string]$r.target -notmatch '^ini:(Tru[A-Za-z0-9]+):([A-Za-z0-9_]+):([A-Za-z0-9_]+)$') { continue }
        $iniEdits["$($Matches[1])|$($Matches[2])|$($Matches[3])"] = $(if ($r.initial -eq 'on') { '1' } else { '0' })
    }
    $backedUp = @{}
    foreach ($k in ($iniEdits.Keys | Sort-Object)) {
        $plugin, $section, $key = $k.Split('|')
        $iniPath = Join-Path $GamePath "$plugin.ini"
        if (!$backedUp[$plugin]) {
            $existed = Test-Path -LiteralPath $iniPath
            $bk = Join-Path $runFolder "ini-before\$plugin.ini"
            if ($existed) { Copy-Item -LiteralPath $iniPath -Destination $bk }
            $state.inis += [ordered]@{ path = $iniPath; backup = $bk.Substring($workspace.Length).TrimStart('\'); existed = $existed }
            & $saveState
            $backedUp[$plugin] = $true
        }
        $old = Get-TruIniValue -Path $iniPath -Section $section -Key $key
        Set-TruIniValue -Path $iniPath -Section $section -Key $key -Value $iniEdits[$k]
        Write-Log ('INI {0}.ini [{1}] {2}={3} (was {4})' -f $plugin, $section, $key, $iniEdits[$k], $(if ($null -ne $old) { $old } else { 'missing' }))
    }

    # ---- record the installed state ----
    $installed = @()
    foreach ($t in $treePlans) {
        $files = Get-ChildItem -LiteralPath $t.Source -Recurse -File | Where-Object {
            $rel = $_.FullName.Substring($t.Source.Length).TrimStart('\')
            $t.Exclude -notcontains ($rel.Split('\')[0])
        }
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($t.Source.Length).TrimStart('\')
            $g = Join-Path $GamePath "mods\$rel"
            $installed += [ordered]@{ path = "mods\$rel"; md5 = $(if (Test-Path -LiteralPath $g) { Get-Md5 $g } else { 'missing' }); expected = $t.Expect[$rel] }
        }
    }
    foreach ($f in $filePlans) {
        $g = Join-Path $GamePath "mods\$($f.Name)"
        $installed += [ordered]@{ path = "mods\$($f.Name)"; md5 = (Get-Md5 $g); expected = $f.Expect }
    }
    foreach ($n in $knownAsis) {
        foreach ($ext in 'asi', 'ini') {
            $g = Join-Path $GamePath "$n.$ext"
            if (Test-Path -LiteralPath $g) { $installed += [ordered]@{ path = "$n.$ext"; md5 = (Get-Md5 $g); sha256 = (Get-Sha256 $g); expected = $null } }
        }
    }
    $installed | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runFolder 'installed.json') -Encoding UTF8
    Write-Log "Installed state recorded: $($installed.Count) files (installed.json)."

    $run = @{
        profile = $profName; start = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'); end = $null; status = 'installed'; statusIcon = $iconOpen
        mode = $(if ($Debugger) { "debugger ($([IO.Path]::GetFileName($Session)))" } else { 'plain (affinity FFFF)' })
        exitCode = $null; preload = 'not done'; firstCrash = $null; markers = @(); guard = @(); tests = @(); dumps = @(); collected = @()
        installed = $installed; md5Notes = @($md5Notes)
    }
    if ($InstallOnly) {
        $run.end = $run.start
        $run.mode = 'install only (game not started)'
        Write-RunSummary -Run $run -Folder $runFolder
        Write-Log "Install only - run folder $runFolder"
        return
    }

    # ---- start the game ----
    $logOffsets = @{}
    foreach ($l in @(Get-ChildItem -LiteralPath $GamePath -Filter 'Tru*.log' -File -ErrorAction SilentlyContinue)) { $logOffsets[$l.Name] = $l.Length }
    $testsFile = Join-Path $GamePath 'TruMenu.tests.txt'
    $startTime = Get-Date
    $cdbLog = Join-Path $runFolder 'cdb.log'
    $exe = Join-Path $GamePath 'tru.exe'
    $inner = if ($Debugger) { '"{0}" -G -cf "{1}" -logo "{2}" "{3}"' -f $CdbPath, $Session, $cdbLog, $exe } else { 'tru.exe' }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $env:SystemRoot 'System32\cmd.exe'
    $psi.Arguments = '/c start "" /b /wait /affinity FFFF ' + $inner
    $psi.WorkingDirectory = $GamePath
    $psi.UseShellExecute = $false
    Write-Log "Start: cmd $($psi.Arguments)" -Level DEBUG
    $proc = [System.Diagnostics.Process]::Start($psi)
    Write-Log "Game started ($($run.mode)) - waiting for TruLink, then for the game to end (at most $TimeoutMinutes min)."
    $deadline = $startTime.AddMinutes($TimeoutMinutes)

    # ---- TruLink: preload the TO TEST rows ----
    $port = if ($prof.trulink -and $prof.trulink.port) { [int]$prof.trulink.port } else {
        $p = Get-TruIniValue -Path (Join-Path $GamePath 'TruLink.ini') -Section 'TruLink' -Key 'Port'
        if ($p) { [int]$p } else { 9265 }
    }
    $linkWait = if ($prof.trulink -and $prof.trulink.waitSeconds) { [int]$prof.trulink.waitSeconds } else { $LinkWaitSeconds }
    $rows = @($prof.tests | Where-Object { $_ })
    if (!$rows.Count) { $run.preload = 'no rows in the profile' }
    elseif (!(Test-Path -LiteralPath (Join-Path $GamePath 'TruLink.asi')) -or !(Test-Path -LiteralPath (Join-Path $GamePath 'TruMenu.asi'))) {
        $run.preload = 'skipped (TruLink.asi / TruMenu.asi not installed)'
        Write-Log $run.preload -Level WARN
    }
    else {
        $link = $null
        $linkDeadline = (Get-Date).AddSeconds($linkWait)
        while (!$link -and (Get-Date) -lt $linkDeadline -and (!$proc.HasExited -or (Get-Process -Name 'tru' -ErrorAction SilentlyContinue))) {
            $link = Open-TruLink -Port $port
            if (!$link) { Start-Sleep -Seconds 2 }
        }
        if (!$link) {
            $run.preload = "TRULINK_TIMEOUT (no connection on port $port within $linkWait s)"
            Write-Log $run.preload -Level WARN
        }
        else {
            try {
                # TruMenu answers once it is loaded
                $menuOk = $false
                while (!$menuOk -and (Get-Date) -lt $linkDeadline) {
                    $ans = Send-TruLink -Link $link -Line 'menu status.version'
                    if ($ans[0].StartsWith('ok')) { $menuOk = $true } else { Start-Sleep -Seconds 2 }
                }
                if (!$menuOk) { throw 'TruMenu does not answer over TruLink.' }
                $errors = 0
                foreach ($line in @('menu test.clear') + @($rows | ForEach-Object { Get-TestCommand $_ })) {
                    # TruLink's tokenizer keeps at most 24 words per line - longer texts are cut
                    if (@($line -split '\s+' | Where-Object { $_ }).Count -gt 24) { Write-Log "more than 24 words, TruLink cuts the text: $line" -Level WARN }
                    $ans = Send-TruLink -Link $link -Line $line
                    if (!$ans[0].StartsWith('ok')) { $errors++; Write-Log "$line -> $($ans[0])" -Level WARN }
                }
                $export = Send-TruLink -Link $link -Line 'menu test.export'
                Set-Content -LiteralPath (Join-Path $runFolder 'tests_preloaded.txt') -Value $export -Encoding UTF8
                $run.preload = '{0} rows sent, {1} errors ({2})' -f $rows.Count, $errors, $export[0]
                Write-Log "TO TEST preloaded: $($run.preload)"
            }
            catch {
                $run.preload = "failed: $($_.Exception.Message)"
                Write-Log "TO TEST preload failed: $($_.Exception.Message)" -Level WARN
            }
            finally { $link.Client.Close() }
        }
    }

    # ---- wait for the end (never ends a process) ----
    $timedOut = $false
    $left = [int][Math]::Max(0, ($deadline - (Get-Date)).TotalMilliseconds)
    if (!$proc.WaitForExit($left)) { $timedOut = $true }
    else {
        # a start through Steam can leave tru.exe running after cmd returned: wait for that one as well
        foreach ($p in @(Get-Process -Name 'tru' -ErrorAction SilentlyContinue)) {
            $left = [int][Math]::Max(0, ($deadline - (Get-Date)).TotalMilliseconds)
            if (!$p.WaitForExit($left)) { $timedOut = $true }
        }
    }
    if ($timedOut) { Write-Log "Timeout after $TimeoutMinutes min - the game still runs; collecting what is there (nothing ended)." -Level WARN }
    else { $run.exitCode = $proc.ExitCode }
    $run.end = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    # ---- collect ----
    foreach ($l in @(Get-ChildItem -LiteralPath $GamePath -Filter 'Tru*.log' -File -ErrorAction SilentlyContinue)) {
        $dest = Join-Path $runFolder $l.Name
        $offset = [long]$logOffsets[$l.Name]
        if ($offset -gt 0 -and $l.Length -ge $offset) {
            # only the part written during this run
            $fs = [IO.File]::Open($l.FullName, 'Open', 'Read', 'ReadWrite')
            try {
                $null = $fs.Seek($offset, 'Begin')
                $out = [IO.File]::Create($dest)
                try { $fs.CopyTo($out) } finally { $out.Close() }
            }
            finally { $fs.Close() }
            $run.collected += "$($l.Name) (from byte $offset)"
        }
        else { Copy-Item -LiteralPath $l.FullName -Destination $dest; $run.collected += $l.Name }
    }
    if (Test-Path -LiteralPath $testsFile) { Copy-Item -LiteralPath $testsFile -Destination (Join-Path $runFolder 'TruMenu.tests.txt'); $run.collected += 'TruMenu.tests.txt' }
    foreach ($n in $knownAsis) {
        $g = Join-Path $GamePath "$n.ini"
        if (Test-Path -LiteralPath $g) { Copy-Item -LiteralPath $g -Destination (Join-Path $runFolder "ini-after\$n.ini") }
    }
    if (Test-Path -LiteralPath $cdbLog) { $run.collected += 'cdb.log' }

    # Find-Markers returns its list with the unary comma (one object); @() around the call nested it, so several
    # markers became ONE row with joined names and the crash-marker test below missed D3DFAIL / MESSAGEBOX
    $run.markers = @(Find-Markers $cdbLog | ForEach-Object { $_ })
    $run.firstCrash = Get-FirstCrash -Markers $run.markers -ExitCode $run.exitCode -QuitByOwner:(Test-TruMenuQuitLog $runFolder)

    # TruGuard markers are in its own log (plain runs have no cdb log); an unhandled DETAIL is a fatal fault.
    # Only the copy in the run folder is read - the game folder may still hold a log from an earlier session.
    $run.guard = @(Find-GuardFaults (Join-Path $runFolder 'TruGuard.log') | ForEach-Object { $_ })
    $guardCrash = Get-GuardCrash $run.guard
    if (!$run.firstCrash -and $guardCrash) { $run.firstCrash = $guardCrash }

    # dumps: paths named in the session file, the WER folder, the game folder, TruGuard's own folder, the run folder
    $dumpDirs = @((Join-Path $env:LOCALAPPDATA 'CrashDumps'), $GamePath, (Join-Path $GamePath 'TruGuardDumps'), $runFolder)
    if ($Debugger) {
        foreach ($m in [regex]::Matches((Get-Content -LiteralPath $Session -Raw), '([A-Za-z]:\\[^\s"'';]+\.dmp)')) {
            $dumpDirs += (Split-Path -Parent ($m.Groups[1].Value -replace '\\\\', '\'))
        }
    }
    $seen = @{}
    foreach ($d in ($dumpDirs | Select-Object -Unique)) {
        if (!(Test-Path -LiteralPath $d)) { continue }
        foreach ($f in @(Get-ChildItem -LiteralPath $d -Filter '*.dmp' -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $startTime })) {
            if ($seen[$f.FullName]) { continue }
            $seen[$f.FullName] = $true
            $entry = [ordered]@{ path = $f.FullName; size = $f.Length; time = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') }
            # keep a copy in the run folder: the session's fixed .dump path (/o) is overwritten by the next run
            $dumpCopyDir = Join-Path $runFolder 'dumps'
            if (!$NoDumpCopy -and !$f.FullName.StartsWith($runFolder, [StringComparison]::OrdinalIgnoreCase)) {
                try {
                    New-Item -ItemType Directory -Force -Path $dumpCopyDir | Out-Null
                    $copy = Join-Path $dumpCopyDir $f.Name
                    Copy-Item -LiteralPath $f.FullName -Destination $copy -Force
                    $entry.copy = $copy
                    Write-Log "dump copied: $($f.FullName) -> $copy" -Level VERBOSE
                }
                catch { Write-Log "dump copy failed: $($f.FullName): $($_.Exception.Message)" -Level WARN }
            }
            $run.dumps += $entry
        }
    }

    $testRows = Read-TestFile (Join-Path $runFolder 'TruMenu.tests.txt')
    $run.tests = ConvertTo-RunTests $testRows
    $fails = @($testRows | Where-Object { $_.kind -eq 'check' -and $_.state -eq 'fail' }).Count
    $open = @($testRows | Where-Object { ($_.kind -eq 'check' -and $_.state -eq 'open') -or ($_.kind -eq 'step' -and $_.state -ne 'done') }).Count
    if ($run.firstCrash -or $fails) { $run.status = "fail ($fails failed checks$(if ($run.firstCrash) { ', crash marker' }))"; $run.statusIcon = $iconFail }
    elseif ($timedOut -or $open -or !$testRows.Count) { $run.status = "open ($open open rows$(if ($timedOut) { ', timeout - game still running' }))"; $run.statusIcon = $iconOpen }
    else { $run.status = 'ok'; $run.statusIcon = $iconOk }
    if (Test-TruMenuQuit $run.exitCode) { $run.status += ' - ended via TruMenu game.quit (exit code 0x544D, not a crash)' }
    $run.timedOut = $timedOut
    $run.expectsFrom = $profName
    Set-RunVerdict -Run $run -Expects $prof.expects -Folder $runFolder

    Write-RunSummary -Run $run -Folder $runFolder
    Write-Log "Run $profName finished: $($run.status); verdict $($run.verdict); first crash marker: $(if ($run.firstCrash) { $run.firstCrash } else { '-' })"
    Write-Log "Run folder: $runFolder (summary.md, summary.json)"
    if ($Compare) {
        $diff = Compare-TruRun -Old (Resolve-RunFolder $Compare) -New $runFolder
        Set-Content -LiteralPath (Join-Path $runFolder 'compare.txt') -Value $diff -Encoding UTF8
    }
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
