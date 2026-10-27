<#
.SYNOPSIS
    Checks the project and the trudlcport clone for things that must not be published (read-only).

.DESCRIPTION
    Scans before an upload:
      Project      every tracked file (HEAD) and every commit message
      Clone        only our part: lines added on branch 'windows' since 'origin/main' and the messages of those commits
      Identities   author/committer names and e-mails of the commits that would be published
    Finding groups:
      Path         absolute local paths (drive letters, /c/..., user folders, AppData, Steam library, Downloads)
      Machine      this PC's name (read at run time)
      Identity     the Windows user name, the git user name and e-mail (read at run time; the owner's own name may
                   stay, the list shows where it appears so it can be decided per place)
      Email        any e-mail address except GitHub noreply addresses
      Secret       passwords, API keys, tokens, private keys
      Hardware     CPU/GPU/RAM details
      Local        extra patterns from Test-TruUploadReady.local.txt next to this script (one regex per
                   line, '#' = comment); for words that must not appear in the repository themselves
                   (e.g. names of local software); the file is not part of the repository
    Names of other people cannot be found by a pattern; review the docs by hand.
    The script contains nothing personal itself: all personal values are read at run time.
    Nothing is changed. Every run writes .\logs\Test-TruUploadReady_<time>.log with all findings.
    -Verbose shows the scanned files, -Debug the patterns, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Test-TruUploadReady.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$UpstreamRef = 'origin/main',
    [string]$Branch = 'windows',
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
if ($Trace) { Set-PSDebug -Trace 1 }

$root    = $PSScriptRoot
$clone   = Join-Path $root 'trudlcport'
$logDir  = Join-Path $root 'logs'
$stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
$self    = Split-Path -Leaf $PSCommandPath
$binaryExt = '.png', '.jpg', '.jpeg', '.gif', '.zip', '.7z', '.exe', '.dll', '.asi', '.bin', '.drm', '.pkl', '.npz', '.ico', '.pdf'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Test-TruUploadReady_{0}.log' -f $stamp)

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

function Invoke-Git {
    param([string]$Repo, [string[]]$GitArgs)
    $out = & git -C $Repo -c core.quotepath=off @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) { throw ("git {0} failed in {1}: {2}" -f ($GitArgs -join ' '), $Repo, ($out -join ' ')) }
    return , @($out | ForEach-Object { [string]$_ })
}

# --- patterns; personal values are read at run time -------------------------------------------------------------
$gitName  = (Invoke-Git -Repo $root -GitArgs @('config', 'user.name'))[0]
$gitMail  = (Invoke-Git -Repo $root -GitArgs @('config', 'user.email'))[0]
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

# --- project: tracked files + commit messages ---------------------------------------------------------------------
Write-Log 'Project: tracked files'
foreach ($rel in (Invoke-Git -Repo $root -GitArgs @('ls-files'))) {
    if ($rel -eq $self -or $binaryExt -contains [IO.Path]::GetExtension($rel).ToLower()) { continue }
    $full = Join-Path $root $rel
    if (!(Test-Path -LiteralPath $full -PathType Leaf)) { continue }
    Write-Log ('  {0}' -f $rel) -Level VERBOSE
    $n = 0
    foreach ($line in [IO.File]::ReadAllLines($full)) { $n++; Test-Line -Scope 'project' -Where ('{0}:{1}' -f $rel, $n) -Text $line }
}
Write-Log 'Project: commit messages'
foreach ($line in (Invoke-Git -Repo $root -GitArgs @('log', '--format=%h %s%n%b'))) {
    Test-Line -Scope 'project-commits' -Where 'log' -Text $line
}

# --- clone: our added lines + our commit messages -----------------------------------------------------------------
if (Test-Path -LiteralPath $clone) {
    Write-Log ('Clone: lines added in {0}..{1}' -f $UpstreamRef, $Branch)
    $file = ''; $n = 0
    foreach ($line in (Invoke-Git -Repo $clone -GitArgs @('diff', '-U0', '--no-color', $UpstreamRef, $Branch))) {
        if ($line.StartsWith('+++ ')) { $file = $line.Substring(4) -replace '^b/', ''; continue }
        if ($line -match '^@@ -\S+ \+(\d+)') { $n = [int]$Matches[1]; continue }
        if ($line.StartsWith('+')) {
            if ($file -notmatch '\.(png|jpe?g|gif|zip|bin)$') { Test-Line -Scope 'clone' -Where ('{0}:{1}' -f $file, $n) -Text $line.Substring(1) }
            $n++
        }
    }
    Write-Log 'Clone: commit messages'
    foreach ($line in (Invoke-Git -Repo $clone -GitArgs @('log', '--format=%h %s%n%b', ('{0}..{1}' -f $UpstreamRef, $Branch)))) {
        Test-Line -Scope 'clone-commits' -Where 'log' -Text $line
    }
} else {
    Write-Log ('Clone not found: {0}' -f $clone) -Level WARN
}

# --- identities ---------------------------------------------------------------------------------------------------
Write-Log 'Identities of the commits to publish:'
$ids = @(Invoke-Git -Repo $root -GitArgs @('log', '--format=%an <%ae> / %cn <%ce>'))
if (Test-Path -LiteralPath $clone) { $ids += Invoke-Git -Repo $clone -GitArgs @('log', '--format=%an <%ae> / %cn <%ce>', ('{0}..{1}' -f $UpstreamRef, $Branch)) }
$ids | Group-Object | ForEach-Object { Write-Log ('  {0,4} x {1}' -f $_.Count, $_.Name) }

# --- report -------------------------------------------------------------------------------------------------------
Write-Log '--- findings ---'
foreach ($f in ($findings | Sort-Object Group, Scope, Where)) {
    Write-Log ('{0,-9} {1,-15} {2}  [{3}]  {4}' -f $f.Group, $f.Scope, $f.Where, $f.Match, $f.Text)
}
Write-Log '--- summary ---'
$findings | Group-Object Group, Scope | Sort-Object Name | ForEach-Object { Write-Log ('{0,-30} {1}' -f $_.Name, $_.Count) }
Write-Log ('total findings {0}' -f $findings.Count)
if ($Trace) { Set-PSDebug -Off }
Write-Host "Log: $logFile"
