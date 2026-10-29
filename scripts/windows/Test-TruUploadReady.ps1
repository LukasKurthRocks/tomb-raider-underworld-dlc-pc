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
    Nothing is changed. Every run writes <workspace>\logs\Test-TruUploadReady_<time>.log with all findings.
    -Verbose shows the scanned commits, -Debug the patterns, -Trace adds a PowerShell line trace.

.EXAMPLE
    .\scripts\windows\Test-TruUploadReady.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$UpstreamRef = 'origin/main',
    [string]$Branch = 'windows',
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
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $out = & git -C $repo -c core.quotepath=off @GitArgs 2>&1
    } finally {
        [Console]::OutputEncoding = $savedEncoding
    }
    if ($LASTEXITCODE -ne 0) { throw ("git {0} failed in {1}: {2}" -f ($GitArgs -join ' '), $repo, ($out -join ' ')) }
    return , @($out | ForEach-Object { [string]$_ })
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

# --- lines added by our commits, every version ------------------------------------------------------------------
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

# --- commit messages and identities -------------------------------------------------------------------------------
foreach ($line in (Invoke-Git -GitArgs @('log', '--format=%h %s%n%b', $range))) {
    Test-Line -Scope 'messages' -Where 'log' -Text $line
}
Write-Log 'Identities of the commits to publish:'
# Invoke-Git returns one wrapped array: assign it first, piping the call directly would group the whole array as one item
$ids = Invoke-Git -GitArgs @('log', '--format=%an <%ae> / %cn <%ce>', $range)
$ids | Group-Object | ForEach-Object { Write-Log ('  {0,4} x {1}' -f $_.Count, $_.Name) }

# --- report -------------------------------------------------------------------------------------------------------
Write-Log '--- findings ---'
foreach ($f in ($findings | Sort-Object Group, Scope, Where)) {
    Write-Log ('{0,-9} {1,-9} {2}  [{3}]  {4}' -f $f.Group, $f.Scope, $f.Where, $f.Match, $f.Text)
}
Write-Log '--- summary ---'
$findings | Group-Object Group, Scope | Sort-Object Name | ForEach-Object { Write-Log ('{0,-30} {1}' -f $_.Name, $_.Count) }
Write-Log ('total findings {0}' -f $findings.Count)
if ($Trace) { Set-PSDebug -Off }
Write-Host "Log: $logFile"
