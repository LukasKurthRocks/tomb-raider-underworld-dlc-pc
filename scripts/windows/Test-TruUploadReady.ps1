<#
.SYNOPSIS
    Checks our commits in this repository for things that must not be published (read-only).

.DESCRIPTION
    Scans our part of the repository before an upload: every commit on branch 'windows' that is not on 'origin/main'
    (the original repository) -
      Lines        every line those commits add, in every version (not only the current state: an old file
                   version in the history is published as well)
      Messages     the commit messages
      Identities   author/committer names and e-mails
    The original author's commits are not scanned (they stay unchanged).
    Finding groups:
      Path         absolute local paths (drive letters, /c/..., user folders, AppData, Steam library, Downloads)
      Machine      this PC's name (read at run time)
      Identity     the Windows user name, the git user name and e-mail (read at run time; the owner's own name may
                   stay, the list shows where it appears so it can be decided per place)
      Email        any e-mail address except noreply addresses
      Secret       passwords, API keys, tokens, private keys
      Hardware     CPU/GPU/RAM details
      Local        extra patterns from Test-TruUploadReady.local.txt next to this script (one regex per
                   line, '#' = comment); for words that must not appear in the repository themselves
                   (e.g. names of local software); the file is not part of the repository
    Names of other people cannot be found by a pattern; review the docs by hand.
    The script contains nothing personal itself: all personal values are read at run time. Its own pattern lines
    are not scanned.

    Category GameData (own count, not part of 'total findings'): the repository must hold no copies of game data
    (players supply the PC game, the title update and the DLC packs; the repository keeps references and rules).
    Every file version (blob) that our commits of '<Branch>' and '<PushedRef>' (pushed + not yet pushed, not
    '<UpstreamRef>') add is read once with 'git cat-file' and checked:
      ext          known game / console file extensions (.drm .bik .mul .raw .tfb .wav .xma .fsb .xex, .bin under
                   a 'data' folder)
      binary       a non-text file (NUL byte in the first 8000 bytes); images under docs/ or assets/ are listed
                   separately as screenshots and not counted
      hex          a run of >= HexRunMin hex digits (one line, or consecutive lines of >= 48 characters)
      base64/zlib  a run of >= Base64RunMin base64 characters (one line or consecutive lines); 'zlib' when it
                   decodes to a zlib header
      array        >= ArrayMin comma-separated numbers in a row (JSON / Python / C array)
      hexdump      >= ArrayMin space-separated hex bytes in consecutive lines (8+ per line)
      escbytes     >= ArrayMin escaped bytes in a row (\x00\x01...)
      listing      >= ArrayMin lines 'address  instruction word  mnemonic' (Xbox code listing with its words)
    Info (not counted, bytes are listed per file): TU instruction words used as signatures ("0x82xxxxxx": "word"
    pairs whose value is not an address of the same range), PC byte patterns ("8B 45 ?? 08", \x.. strings of 4+).
    Test-TruUploadReady.gamedata.txt next to this script is the allow-list for proven non-game data:
    '<path wildcard> | <class> | <reason>' (class: synthetic / own / third-party / screenshot); allowed hits are
    listed with the reason. Paths whose name contains 'TruGuard' are skipped unread.
    Nothing is changed. Every run writes <workspace>\logs\Test-TruUploadReady_<time>.log with all findings.
    -Verbose shows the scanned commits, -Debug the patterns (and every blob of the game-data scan), -Trace adds a
    PowerShell line trace.

.PARAMETER PushedRef
    The published branch (default fork/windows); its commits and those of -Branch are scanned for game data and each
    hit is marked 'pushed' or 'unpushed'. Empty = only -Branch.
.PARAMETER IncludeUpstream
    Also checks the original repository's file versions (<UpstreamRef>) for game data; listed as 'upstream', counted
    separately.
.PARAMETER SkipGameData
    Classic scan only.
.PARAMETER GameDataOnly
    Game-data scan only.

.EXAMPLE
    .\scripts\windows\Test-TruUploadReady.ps1 -Verbose
.EXAMPLE
    .\scripts\windows\Test-TruUploadReady.ps1 -GameDataOnly -IncludeUpstream
#>
[CmdletBinding()]
param(
    [string]$UpstreamRef = 'origin/main',
    [string]$Branch = 'windows',
    [string]$PushedRef = 'fork/windows',
    [int]$HexRunMin = 256,
    [int]$Base64RunMin = 512,
    [int]$ArrayMin = 128,
    [switch]$IncludeUpstream,
    [switch]$SkipGameData,
    [switch]$GameDataOnly,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
if ($Trace) { Set-PSDebug -Trace 1 }

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$repo    = $paths.Repository
$logDir  = $paths.Logs
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$self    = 'scripts/windows/' + (Split-Path -Leaf $PSCommandPath)
$range   = '{0}..{1}' -f $UpstreamRef, $Branch

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Test-TruUploadReady_{0}.log' -f $stamp)
Set-TruLogFile -Path $logFile

function Invoke-Git {
    param([string[]]$GitArgs)
    # git writes UTF-8; the console code page would turn umlauts and dashes into mojibake (and break non-ASCII patterns)
    $savedEncoding = [Console]::OutputEncoding
    # PowerShell 5.1 turns every stderr line of a native command into an error record, which 'Stop' makes fatal -
    # a harmless git warning (CRLF, rename detection) would abort the scan; the exit code decides instead
    $savedPreference = $ErrorActionPreference
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $ErrorActionPreference = 'Continue'
        $out = & git -C $repo -c core.quotepath=off @GitArgs 2>&1
    } finally {
        $ErrorActionPreference = $savedPreference
        [Console]::OutputEncoding = $savedEncoding
    }
    $stdout = @($out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { [string]$_ })
    $stderr = @($out | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { [string]$_ })
    if ($LASTEXITCODE -ne 0) { throw ("git {0} failed in {1}: {2}" -f ($GitArgs -join ' '), $repo, (($stdout + $stderr) -join ' ')) }
    foreach ($line in $stderr) { Write-Log ('git: ' + $line) -Level VERBOSE }
    return , $stdout
}

# --- patterns; personal values are read at run time -------------------------------------------------------------
$gitName  = (Invoke-Git -GitArgs @('config', 'user.name'))[0]
$gitMail  = (Invoke-Git -GitArgs @('config', 'user.email'))[0]
$identity = @($env:USERNAME) + @($gitName -split '\s+') + @($gitMail, ($gitMail -split '@')[-1])
$identity = @($identity | Where-Object { $_ -and $_.Length -ge 4 } | Sort-Object -Unique)
$machine  = @($env:COMPUTERNAME) + @($env:COMPUTERNAME -split '[-_.]' | Where-Object { $_.Length -ge 4 -and $identity -notcontains $_ })
$toAlternation = { param($values) '(?i)(' + (($values | Sort-Object -Unique | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')' }
# extra patterns that must not be written into the repository themselves: local file only
$localFile    = Join-Path $PSScriptRoot 'Test-TruUploadReady.local.txt'
$localPattern = '(?!)'   # matches nothing without the file
if (Test-Path -LiteralPath $localFile) {
    $localLines = @(Get-Content -LiteralPath $localFile | Where-Object { $_.Trim() -and !$_.TrimStart().StartsWith('#') })
    if ($localLines.Count) { $localPattern = '(?i)(' + ($localLines -join '|') + ')' }
}
$patterns = [ordered]@{
    Path      = '(?i)(\b[a-z]:[\\/][^\s''"`|*]|(^|[\s''"`(=])/[a-z]/(dev|users|steamlibrary|program)|[\\/]users[\\/]|appdata|steamlibrary|[\\/]downloads[\\/])'
    Machine   = & $toAlternation $machine
    Identity  = & $toAlternation $identity
    Email     = '(?i)\b(?!noreply@)[a-z0-9._%+-]+@(?!users\.noreply\.github\.com)[a-z0-9.-]+\.[a-z]{2,}\b'
    Secret    = '(?i)(passwor[dt]|kennwort|api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|bearer\s+[a-z0-9]|-----BEGIN [A-Z ]*PRIVATE KEY|\bghp_[a-z0-9]{20,}|\bsk-[a-z0-9-]{20,})'
    Hardware  = '(?i)(ryzen|threadripper|xeon|core i[3579]|\bi[3579]-\d{4,5}|\brtx ?\d{3,4}|\bgtx ?\d{3,4}|geforce|radeon|\brx ?\d{4}\b|\d+ ?gb ram)'
    Local     = $localPattern
}
foreach ($k in $patterns.Keys) { Write-Log ('pattern {0}: {1}' -f $k, $patterns[$k]) -Level DEBUG }
Write-Log ('local pattern file: {0}' -f $(if (Test-Path -LiteralPath $localFile) { 'found' } else { 'none' })) -Level VERBOSE

$findings = New-Object System.Collections.Generic.List[object]
function Test-Line {
    param([string]$Scope, [string]$Where, [string]$Text)
    foreach ($k in $patterns.Keys) {
        $m = [regex]::Match($Text, $patterns[$k])
        if ($m.Success) {
            $snippet = $Text.Trim()
            if ($snippet.Length -gt 140) { $snippet = $snippet.Substring(0, 140) + '...' }
            $findings.Add([pscustomobject]@{ Group = $k; Scope = $Scope; Where = $Where; Match = $m.Value; Text = $snippet })
        }
    }
}

if (!$GameDataOnly) {
    # --- lines added by our commits, every version --------------------------------------------------------------
    $commits = Invoke-Git -GitArgs @('rev-list', $range)
    Write-Log ('Our commits ({0}): {1}' -f $range, $commits.Count)
    $commit = ''; $file = ''; $n = 0
    foreach ($line in (Invoke-Git -GitArgs @('log', '-p', '-U0', '--no-color', '--format=commit %h', $range))) {
        if ($line -match '^commit ([0-9a-f]+)$') { $commit = $Matches[1]; Write-Log ('  {0}' -f $commit) -Level VERBOSE; continue }
        if ($line.StartsWith('+++ ')) { $file = $line.Substring(4) -replace '^b/', ''; continue }
        if ($line -match '^@@ -\S+ \+(\d+)') { $n = [int]$Matches[1]; continue }
        if ($line.StartsWith('+')) {
            if ($file -ne $self -and $file -notmatch '\.(png|jpe?g|gif|zip|bin)$') {
                Test-Line -Scope 'lines' -Where ('{0} {1}:{2}' -f $commit, $file, $n) -Text $line.Substring(1)
            }
            $n++
        }
    }

    # --- commit messages and identities ---------------------------------------------------------------------------
    foreach ($line in (Invoke-Git -GitArgs @('log', '--format=%h %s%n%b', $range))) {
        Test-Line -Scope 'messages' -Where 'log' -Text $line
    }
    Write-Log 'Identities of the commits to publish:'
    # Invoke-Git returns one wrapped array: assign it first, piping the call directly would group the whole array as one item
    $ids = Invoke-Git -GitArgs @('log', '--format=%an <%ae> / %cn <%ce>', $range)
    $ids | Group-Object | ForEach-Object { Write-Log ('  {0,4} x {1}' -f $_.Count, $_.Name) }

    # --- report ---------------------------------------------------------------------------------------------------
    Write-Log '--- findings ---'
    foreach ($f in ($findings | Sort-Object Group, Scope, Where)) {
        Write-Log ('{0,-9} {1,-9} {2}  [{3}]  {4}' -f $f.Group, $f.Scope, $f.Where, $f.Match, $f.Text)
    }
    Write-Log '--- summary ---'
    $findings | Group-Object Group, Scope | Sort-Object Name | ForEach-Object { Write-Log ('{0,-30} {1}' -f $_.Name, $_.Count) }
    Write-Log ('total findings {0}' -f $findings.Count)
}

# --- game data: every file version our commits add ----------------------------------------------------------------
if (!$SkipGameData) {
    $gameFindings = New-Object System.Collections.Generic.List[object]
    $gameAllowed  = New-Object System.Collections.Generic.List[object]
    $images       = New-Object System.Collections.Generic.List[object]
    $signatures   = New-Object System.Collections.Generic.List[object]

    # allow-list: '<path wildcard> | <class> | <reason>'
    $allowFile = Join-Path $PSScriptRoot 'Test-TruUploadReady.gamedata.txt'
    $allowList = @()
    if (Test-Path -LiteralPath $allowFile) {
        $allowList = @(Get-Content -LiteralPath $allowFile -Encoding UTF8 | Where-Object { $_.Trim() -and !$_.TrimStart().StartsWith('#') } | ForEach-Object {
            $parts = $_ -split '\|', 3
            [pscustomobject]@{ Pattern = $parts[0].Trim(); Class = $(if ($parts.Count -gt 1) { $parts[1].Trim() } else { '?' }); Reason = $(if ($parts.Count -gt 2) { $parts[2].Trim() } else { '' }) }
        })
    }
    Write-Log ('game-data allow-list: {0} entries ({1})' -f $allowList.Count, $(if (Test-Path -LiteralPath $allowFile) { 'found' } else { 'none' })) -Level VERBOSE

    $rxOpt       = [System.Text.RegularExpressions.RegexOptions]::Compiled
    $rxGameExt   = [regex]::new('(?i)\.(drm|bik|mul|raw|tfb|wav|xma|fsb|xex)$')
    $rxDataBin   = [regex]::new('(?i)(^|/)data/(.*/)?[^/]+\.bin$')
    $rxImage     = [regex]::new('(?i)\.(png|jpe?g|gif|webp|bmp|ico)$')
    $rxDocsPath  = [regex]::new('(?i)^(docs|assets)/|/screenshots/')
    $rxNameSkip  = [regex]::new('(?i)truguard')
    # one run: base64 alphabet, classified afterwards (hex digits only = hex)
    $rxRun       = [regex]::new(('[A-Za-z0-9+/]{{{0},}}={{0,2}}' -f [Math]::Min($HexRunMin, $Base64RunMin)), $rxOpt)
    # the same over consecutive lines (string concatenation, MIME line breaks)
    $rxRunLines  = [regex]::new('(?m)(?:^[ \t"''`]*[A-Za-z0-9+/]{48,}={0,2}[ \t"'',]*\r?\n){6,}', $rxOpt)
    # atomic and unambiguous: a nested '\d+\.?\d*' backtracks exponentially on long digit lists
    $num         = '(?>0[xX][0-9A-Fa-f]+|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)[uUlLfF]*'
    $rxArrayPre  = [regex]::new(('(?<![\w.])(?>{0})(?:\s*,\s*(?>{0})){{15}}' -f $num), $rxOpt)
    $rxArray     = [regex]::new(('(?<![\w.])(?>{0})(?:\s*,\s*(?>{0})){{{1},}}' -f $num, ($ArrayMin - 1)), $rxOpt)
    $rxDumpLines = [regex]::new('(?m)(?:^[^\n]*?\b(?:[0-9A-Fa-f]{2}[ \t]+){7,}[0-9A-Fa-f]{2}\b[^\n]*\n)+', $rxOpt)
    $rxDumpByte  = [regex]::new('(?<![0-9A-Za-z])[0-9A-Fa-f]{2}(?![0-9A-Za-z])')
    $rxEscBytes  = [regex]::new('(?:\\x[0-9A-Fa-f]{2}){4,}', $rxOpt)
    $rxListing   = [regex]::new('(?im)^[ \t|>]*(?:0x)?8[0-9a-f]{7}:?[ \t]+(?:0x)?[0-9a-f]{8}[ \t]+[a-z][a-z0-9.]{0,9}[ \t]', $rxOpt)
    $rxSigPair   = [regex]::new('(?i)["'']?0x(8[0-9a-f]{7})["'']?\s*:\s*["'']?0x([0-9a-f]{8})\b', $rxOpt)
    $rxSigBytes  = [regex]::new('"((?:[0-9A-Fa-f]{2}|\?\??)(?: (?:[0-9A-Fa-f]{2}|\?\??)){3,})"', $rxOpt)

    function New-Row {
        # ordered row: the common columns first, then the extra ones
        param([System.Collections.IDictionary]$Base, [System.Collections.IDictionary]$More)
        $row = [ordered]@{}
        foreach ($k in $Base.Keys) { $row[$k] = $Base[$k] }
        foreach ($k in $More.Keys) { $row[$k] = $More[$k] }
        return [pscustomobject]$row
    }
    function Test-ZlibHeader {
        param([byte[]]$Bytes)
        return ($Bytes.Count -ge 2 -and $Bytes[0] -le 0x78 -and ($Bytes[0] -band 0x0f) -eq 8 -and ((([int]$Bytes[0]) * 256 + $Bytes[1]) % 31) -eq 0)
    }
    function Get-RunKind {
        # hex digits only = hex (>= HexRunMin), else base64 (>= Base64RunMin, varied alphabet); $null = no finding
        param([string]$Run)
        $body = $Run.TrimEnd('=')
        $distinct = @($body.ToCharArray() | Select-Object -Unique).Count
        if ($body -match '^[0-9A-Fa-f]+$') {
            if ($body.Length -lt $HexRunMin -or $distinct -lt 6) { return $null }
            $head = [byte[]]@([Convert]::ToByte($body.Substring(0, 2), 16), [Convert]::ToByte($body.Substring(2, 2), 16))
            if (Test-ZlibHeader $head) { return 'hex/zlib' }
            return 'hex'
        }
        if ($body.Length -lt $Base64RunMin -or $distinct -lt 10) { return $null }
        try { $head = [Convert]::FromBase64String($body.Substring(0, 4)) } catch { $head = [byte[]]@() }
        if (Test-ZlibHeader $head) { return 'base64/zlib' }
        return 'base64'
    }
    function Get-ArrayKind {
        param([string]$Text)
        $values = @($Text -split '\s*,\s*')
        # (parentheses: ',' binds tighter than '*' in PowerShell)
        if (@($values | Where-Object { $_ -match '[.eE]' -and $_ -notmatch '^0[xX]' }).Count) { return @('float array', $values.Count, ($values.Count * 4)) }
        if (@($values | Where-Object { $_ -match '^0[xX]' }).Count -eq $values.Count) {
            $wide = @($values | Where-Object { $_.Length -gt 4 }).Count
            if ($wide) { return @('hex array', $values.Count, ($values.Count * 4)) }
            return @('byte array', $values.Count, $values.Count)
        }
        $big = @($values | Where-Object { $_ -notmatch '^\d{1,3}$' -or [int]$_ -gt 255 }).Count
        if ($big) { return @('int array', $values.Count, ($values.Count * 4)) }
        return @('byte array', $values.Count, $values.Count)
    }

    # git cat-file --batch: one reader process, raw bytes; it ends by itself when its input is closed
    function Open-BlobReader {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = 'git'
        $psi.Arguments = ('-C "{0}" cat-file --batch' -f $repo)
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.CreateNoWindow = $true
        return [System.Diagnostics.Process]::Start($psi)
    }
    function Read-Blob {
        param($Reader, [string]$Id)
        $request = [System.Text.Encoding]::ASCII.GetBytes($Id + "`n")
        $Reader.StandardInput.BaseStream.Write($request, 0, $request.Length)
        $Reader.StandardInput.BaseStream.Flush()
        $stream = $Reader.StandardOutput.BaseStream
        $header = New-Object System.Collections.Generic.List[byte]
        while ($true) {
            $b = $stream.ReadByte()
            if ($b -lt 0) { throw 'git cat-file ended unexpectedly' }
            if ($b -eq 10) { break }
            $header.Add([byte]$b)
        }
        $parts = [System.Text.Encoding]::ASCII.GetString($header.ToArray()) -split ' '
        if ($parts.Count -lt 3 -or $parts[1] -ne 'blob') { return $null }
        $size = [int]$parts[2]
        $buffer = New-Object byte[] $size
        $offset = 0
        while ($offset -lt $size) {
            $read = $stream.Read($buffer, $offset, $size - $offset)
            if ($read -le 0) { throw 'git cat-file ended inside a blob' }
            $offset += $read
        }
        [void]$stream.ReadByte()   # LF after the content
        return , $buffer
    }

    # which commits are published already
    $pushed = @{}
    $refsToScan = @($Branch)
    if ($PushedRef) {
        $known = $true
        try { [void](Invoke-Git -GitArgs @('rev-parse', '--verify', '--quiet', $PushedRef)) } catch { $known = $false }
        if ($known) {
            $refsToScan += $PushedRef
            foreach ($c in (Invoke-Git -GitArgs @('rev-list', $PushedRef, '--not', $UpstreamRef))) { $pushed[$c] = $true }
        } else { Write-Log ('pushed ref {0} not found: every commit counts as unpushed' -f $PushedRef) -Level WARN }
    }
    $upstreamBlobs = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($line in (Invoke-Git -GitArgs @('rev-list', '--objects', $UpstreamRef))) { [void]$upstreamBlobs.Add($line.Substring(0, 40)) }
    $headBlobs = @{}
    foreach ($line in (Invoke-Git -GitArgs @('ls-tree', '-r', $Branch))) {
        if ($line -match '^\d{6} blob ([0-9a-f]{40})\t(.+)$') { $headBlobs[$Matches[2]] = $Matches[1] }
    }

    # every (blob, path) once, oldest commit first; merges against each parent (-m)
    $entries = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]'
    $skippedByName = 0
    $passes = @(@{ Scope = 'ours'; GitArgs = @('log', '--raw', '--no-abbrev', '--no-renames', '-m', '--reverse', '--format=commit %H') + $refsToScan + @('--not', $UpstreamRef) })
    if ($IncludeUpstream) { $passes += @{ Scope = 'upstream'; GitArgs = @('log', '--raw', '--no-abbrev', '--no-renames', '-m', '--reverse', '--format=commit %H', $UpstreamRef) } }
    foreach ($pass in $passes) {
        $commit = ''
        foreach ($line in (Invoke-Git -GitArgs $pass.GitArgs)) {
            if ($line -match '^commit ([0-9a-f]{40})') { $commit = $Matches[1]; continue }
            if ($line -notmatch '^:\d{6} (\d{6}) [0-9a-f]{40} ([0-9a-f]{40}) ([A-Z])\d*\t(.+)$') { continue }
            $mode = $Matches[1]; $blob = $Matches[2]; $path = $Matches[4]
            if ($Matches[3] -eq 'D' -or $mode -notmatch '^100') { continue }
            if ($rxNameSkip.IsMatch($path)) { $skippedByName++; continue }
            if ($pass.Scope -eq 'ours' -and $upstreamBlobs.Contains($blob)) { continue }
            if (!$seen.Add($blob + "`t" + $path)) { continue }
            $state = if ($pass.Scope -eq 'upstream') { 'upstream' } elseif ($pushed.ContainsKey($commit)) { 'pushed' } else { 'unpushed' }
            $entries.Add([pscustomobject]@{ Blob = $blob; Path = $path; Commit = $commit.Substring(0, 7); State = $state })
        }
    }
    Write-Log ('game data: {0} file versions to check (skipped by name rule: {1})' -f $entries.Count, $skippedByName)

    $reader = Open-BlobReader
    $cache = @{}
    $textCount = 0; $binaryCount = 0; $byteCount = [int64]0
    try {
        foreach ($e in $entries) {
            $atHead = $(if ($headBlobs[$e.Path] -eq $e.Blob) { 'HEAD' } else { 'old' })
            $base = [ordered]@{ State = $e.State; Commit = $e.Commit; Path = $e.Path; Blob = $e.Blob.Substring(0, 8); AtHead = $atHead }
            $allow = $allowList | Where-Object { $e.Path -like $_.Pattern } | Select-Object -First 1
            if (!$cache.ContainsKey($e.Blob)) {
                $bytes = Read-Blob -Reader $reader -Id $e.Blob
                $hits = New-Object System.Collections.Generic.List[object]
                $sig = [ordered]@{ Words = 0; PatternBytes = 0; EscBytes = 0 }
                $binary = $bytes.Length -gt 0 -and [Array]::IndexOf($bytes, [byte]0, 0, [Math]::Min($bytes.Length, 8000)) -ge 0
                $magic = ''
                for ($i = 0; $i -lt [Math]::Min($bytes.Length, 4); $i++) { $magic += $bytes[$i].ToString('x2') }
                if (!$binary) {
                    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
                    foreach ($m in $rxRun.Matches($text)) {
                        $kind = Get-RunKind $m.Value
                        if ($kind) { $hits.Add(@($kind, $m.Value.Length, ('{0} chars at {1}' -f $m.Value.Length, $m.Index))) }
                    }
                    foreach ($m in $rxRunLines.Matches($text)) {
                        $joined = ($m.Value -replace '[\s"''`,]', '')
                        # one md5 / sha1 / sha256 per line = a hash list (checksums of our own builds), not data
                        $lineRuns = @($m.Value -split '\n' | ForEach-Object { ($_ -replace '[\s"''`,]', '') } | Where-Object { $_ })
                        if (@($lineRuns | Where-Object { $_ -notmatch '^([0-9A-Fa-f]{32}|[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$' }).Count -eq 0) { continue }
                        $kind = Get-RunKind $joined
                        if ($kind) { $hits.Add(@(($kind + ' (lines)'), $joined.Length, ('{0} chars at {1}' -f $joined.Length, $m.Index))) }
                    }
                    if ($rxArrayPre.IsMatch($text)) {
                        foreach ($m in $rxArray.Matches($text)) {
                            $ak = Get-ArrayKind $m.Value
                            $hits.Add(@($ak[0], $ak[2], ('{0} values at {1}' -f $ak[1], $m.Index)))
                        }
                    }
                    foreach ($m in $rxDumpLines.Matches($text)) {
                        $count = 0
                        foreach ($line in ($m.Value -split '\n')) {
                            if ($line -match '\b(?:[0-9A-Fa-f]{2}[ \t]+){7,}[0-9A-Fa-f]{2}\b') { $count += $rxDumpByte.Matches($line).Count }
                        }
                        if ($count -ge $ArrayMin) { $hits.Add(@('hexdump', $count, ('{0} bytes at {1}' -f $count, $m.Index))) }
                    }
                    foreach ($m in $rxEscBytes.Matches($text)) {
                        $n = [int]($m.Value.Length / 4)
                        if ($n -ge $ArrayMin) { $hits.Add(@('escbytes', $n, ('{0} bytes at {1}' -f $n, $m.Index))) } else { $sig.EscBytes += $n }
                    }
                    $listing = $rxListing.Matches($text).Count
                    if ($listing -ge $ArrayMin) { $hits.Add(@('listing', ($listing * 4), ('{0} instruction words' -f $listing))) }
                    foreach ($m in $rxSigPair.Matches($text)) {
                        # an address of the same range on both sides is a reference, not an instruction word
                        if ($m.Groups[1].Value.Substring(0, 2) -ne $m.Groups[2].Value.Substring(0, 2)) { $sig.Words++ }
                    }
                    foreach ($m in $rxSigBytes.Matches($text)) { $sig.PatternBytes += @($m.Groups[1].Value -split ' ').Count }
                    $sig.Words += $listing
                    $textCount++
                } else { $binaryCount++ }
                $byteCount += $bytes.Length
                $cache[$e.Blob] = [pscustomobject]@{ Size = $bytes.Length; Binary = $binary; Hits = $hits; Sig = $sig; Magic = $magic }
            }
            $info = $cache[$e.Blob]
            Write-Log ('  {0} {1} {2} {3} B binary={4} hits={5}' -f $e.State, $e.Commit, $e.Path, $info.Size, $info.Binary, $info.Hits.Count) -Level DEBUG

            $results = New-Object System.Collections.Generic.List[object]
            if ($rxGameExt.IsMatch($e.Path) -or $rxDataBin.IsMatch($e.Path)) { $results.Add(@('ext', $info.Size, ('game file extension, magic ' + $info.Magic))) }
            if ($info.Binary) {
                if ($rxImage.IsMatch($e.Path) -and $rxDocsPath.IsMatch($e.Path)) {
                    $images.Add((New-Row $base @{ Size = $info.Size }))
                } else {
                    $results.Add(@('binary', $info.Size, ('non-text, magic ' + $info.Magic)))
                }
            }
            foreach ($h in $info.Hits) { $results.Add($h) }
            foreach ($r in $results) {
                $item = New-Row $base ([ordered]@{ Size = $info.Size; Kind = $r[0]; Bytes = $r[1]; Detail = $r[2]; Class = ''; Reason = '' })
                if ($allow) { $item.Class = $allow.Class; $item.Reason = $allow.Reason; $gameAllowed.Add($item) } else { $gameFindings.Add($item) }
            }
            if ($info.Sig.Words -or $info.Sig.PatternBytes -or $info.Sig.EscBytes) {
                $signatures.Add((New-Row $base @{ Words = $info.Sig.Words; PatternBytes = $info.Sig.PatternBytes; EscBytes = $info.Sig.EscBytes; Bytes = $info.Sig.Words * 4 + $info.Sig.PatternBytes + $info.Sig.EscBytes }))
            }
        }
    } finally {
        $reader.StandardInput.Close()
        $reader.WaitForExit()
        $reader.Dispose()
    }

    # --- game data report -----------------------------------------------------------------------------------------
    $line2 = '{0,-8} {1,-8} {2} {3} {4} ({5} B, blob {6}, {7})  {8} B  {9}'
    Write-Log '--- game data findings (category GameData; not part of total findings) ---'
    foreach ($f in ($gameFindings | Sort-Object State, Kind, Path, Commit)) {
        Write-Log ($line2 -f 'GameData', $f.State, $f.Commit, $f.Kind, $f.Path, $f.Size, $f.Blob, $f.AtHead, $f.Bytes, $f.Detail)
    }
    Write-Log '--- game data: allowed (allow-list) ---'
    foreach ($f in ($gameAllowed | Sort-Object Path, Commit)) {
        Write-Log (($line2 -f 'allowed', $f.State, $f.Commit, $f.Kind, $f.Path, $f.Size, $f.Blob, $f.AtHead, $f.Bytes, $f.Detail) + ('  [{0}: {1}]' -f $f.Class, $f.Reason))
    }
    Write-Log '--- screenshots / docs images (not counted; check by eye) ---'
    foreach ($f in ($images | Sort-Object Path, Commit)) {
        Write-Log ('image    {0,-8} {1} {2} ({3} B, blob {4}, {5})' -f $f.State, $f.Commit, $f.Path, $f.Size, $f.Blob, $f.AtHead)
    }
    Write-Log '--- signatures: TU instruction words / PC byte patterns (info; bytes per file version) ---'
    foreach ($f in ($signatures | Sort-Object Path, Commit)) {
        Write-Log ('sig      {0,-8} {1} {2} (blob {3}, {4})  words {5} = {6} B, pattern bytes {7}, escaped bytes {8}, total {9} B' -f $f.State, $f.Commit, $f.Path, $f.Blob, $f.AtHead, $f.Words, ($f.Words * 4), $f.PatternBytes, $f.EscBytes, $f.Bytes)
    }
    Write-Log '--- game data summary ---'
    Write-Log ('file versions {0} (text {1}, binary {2}, {3} bytes read), skipped by name rule {4}' -f $entries.Count, $textCount, $binaryCount, $byteCount, $skippedByName)
    $gameFindings | Group-Object State, Kind | Sort-Object Name | ForEach-Object { Write-Log ('GameData, {0,-28} {1}' -f $_.Name, $_.Count) }
    $sigHead = @($signatures | Where-Object { $_.AtHead -eq 'HEAD' })
    Write-Log ('allowed {0}, images {1}, signature file versions {2} (at {3}: {4} files, {5} B)' -f $gameAllowed.Count, $images.Count, $signatures.Count, $Branch, $sigHead.Count, (($sigHead | Measure-Object Bytes -Sum).Sum + 0))
    Write-Log ('game data findings {0}' -f $gameFindings.Count)
}
if ($Trace) { Set-PSDebug -Off }
Write-Host "Log: $logFile"
