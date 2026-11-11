<#
.SYNOPSIS
    Shared helpers of the trudlcport Windows scripts: run log, workspace paths, Steam game folder, MD5, installed-file
    checks of the install manifests (Install-TruTree / Install-TruDlc -Restore).

.DESCRIPTION
    Every script in scripts\windows imports this module near its top:
        Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
    and then sets its per-run log file with Set-TruLogFile before the first Write-Log.

    A script module does not see the preference variables of the calling script. The exported functions therefore
    take over the caller's VerbosePreference, DebugPreference, WarningPreference and ErrorActionPreference, so
    -Verbose, -Debug and ErrorActionPreference 'Stop' of the calling script apply as before.
#>

# path of the current run's log file, set by Set-TruLogFile
$script:LogFile = $null

function Get-TruCallerPreference {
    <#
    .SYNOPSIS
        Returns the caller's preference variables (private helper, not exported).
    .DESCRIPTION
        $Cmdlet.SessionState is the session state of the code that called the advanced function; its variables
        are looked up from the caller's current scope.
    .PARAMETER Cmdlet
        $PSCmdlet of the calling advanced function.
    #>
    param([Parameter(Mandatory)][System.Management.Automation.PSCmdlet]$Cmdlet)
    $values = @{}
    foreach ($name in 'VerbosePreference', 'DebugPreference', 'WarningPreference', 'ErrorActionPreference') {
        $value = $Cmdlet.SessionState.PSVariable.GetValue($name)
        if ($null -ne $value) { $values[$name] = $value }
    }
    return $values
}

function Set-TruLogFile {
    <#
    .SYNOPSIS
        Sets the log file that Write-Log appends to.
    .DESCRIPTION
        Call once per run after the log folder exists, before the first Write-Log. The folder is not created here.
    .PARAMETER Path
        Full path of the per-run log file, e.g. <workspace>\logs\<script>_<time>.log.
    .EXAMPLE
        Set-TruLogFile -Path $logFile
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path)
    $script:LogFile = $Path
}

function Write-Log {
    <#
    .SYNOPSIS
        Appends a time-stamped line to the run log and shows the message on the matching stream.
    .DESCRIPTION
        Log line: 'yyyy-MM-dd HH:mm:ss.fff [LEVEL] message' (UTF-8). Console: INFO -> Write-Host,
        VERBOSE -> Write-Verbose, DEBUG -> Write-Debug, WARN -> Write-Warning, ERROR -> Write-Host in red.
        VERBOSE and DEBUG lines are always written to the log, but only shown with -Verbose / -Debug of the caller.
    .PARAMETER Message
        Text to log.
    .PARAMETER Level
        INFO (default), VERBOSE, DEBUG, WARN or ERROR.
    .EXAMPLE
        Write-Log "Game folder: $GamePath" -Level VERBOSE
    #>
    [CmdletBinding()]
    param(
        [string]$Message,
        [ValidateSet('INFO', 'VERBOSE', 'DEBUG', 'WARN', 'ERROR')][string]$Level = 'INFO'
    )
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    if (!$script:LogFile) { throw 'Write-Log: no log file set; call Set-TruLogFile first.' }
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'), $Level, $Message
    # a locked log file (reader, scanner) must not abort a long tool run: warn on the console and go on
    try { Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8 -ErrorAction Stop }
    catch { Write-Host ('(log write failed: {0})' -f $_.Exception.Message) -ForegroundColor Yellow }
    switch ($Level) {
        'INFO'    { Write-Host $Message }
        'VERBOSE' { Write-Verbose $Message }
        'DEBUG'   { Write-Debug $Message }
        'WARN'    { Write-Warning $Message }
        'ERROR'   { Write-Host $Message -ForegroundColor Red }
    }
}

function Get-TruWorkspacePath {
    <#
    .SYNOPSIS
        Derives the repository, workspace and log folder from the folder of a script in scripts\windows.
    .DESCRIPTION
        <workspace> = the folder that holds the repository (bin, data, input, logs, backup, release - never in
        the repository); the scripts live in <repository>\scripts\windows. Returns an object with
        Repository, Workspace and Logs (<workspace>\logs). Nothing is created.
    .PARAMETER ScriptRoot
        $PSScriptRoot of the calling script.
    .EXAMPLE
        $paths = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$ScriptRoot)
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    $repository = Split-Path -Parent (Split-Path -Parent $ScriptRoot)
    $workspace  = Split-Path -Parent $repository
    return [pscustomobject]@{
        Repository = $repository
        Workspace  = $workspace
        Logs       = (Join-Path $workspace 'logs')
    }
}

function Find-TruGamePath {
    <#
    .SYNOPSIS
        Finds the Steam folder of Tomb Raider: Underworld (app 8140); returns $null if not found.
    .DESCRIPTION
        Steam library folders from the registry + libraryfolders.vdf; the first library with
        steamapps\common\Tomb Raider Underworld\tru.exe wins. Each candidate is logged at DEBUG level.
    .EXAMPLE
        $GamePath = Find-TruGamePath
    #>
    [CmdletBinding()]
    param()
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    $steam = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    if (!$steam) { return $null }
    $libraries = @($steam)
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        foreach ($match in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $libraries += $match.Groups[1].Value -replace '\\\\', '\'
        }
    }
    foreach ($library in ($libraries | Select-Object -Unique)) {
        $candidate = Join-Path $library 'steamapps\common\Tomb Raider Underworld'
        Write-Log "Steam library candidate: $candidate" -Level DEBUG
        if (Test-Path -LiteralPath (Join-Path $candidate 'tru.exe')) { return $candidate }
    }
    return $null
}

function Get-Md5 {
    <#
    .SYNOPSIS
        Returns the MD5 of a file as lower-case hex.
    .PARAMETER Path
        File to hash (literal path).
    .EXAMPLE
        Get-Md5 (Join-Path $GamePath 'tru.exe')
    #>
    [CmdletBinding()]
    param([string]$Path)
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    (Get-FileHash -LiteralPath $Path -Algorithm MD5).Hash.ToLower()
}

function Get-TruPlayerGuardRules {
    <#
    .SYNOPSIS
        Loads the player-path guard rules docs\data\playerpath_guard.json (plan Spielerweg P0, gate G2).
    .DESCRIPTION
        The same rules tools\player_guard.py applies inside every Python tool process. Returns an object with
        Version, Categories (Name, Action, Ws, Repo, Name regex lists), Allow (workspace-relative paths) and the
        Repository / Workspace folders (lower case, forward slashes) the patterns are relative to.
    .PARAMETER Repository
        The repository folder (Get-TruWorkspacePath).Repository.
    .EXAMPLE
        $rules = Get-TruPlayerGuardRules -Repository $paths.Repository
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Repository)
    $file = Join-Path $Repository 'docs\data\playerpath_guard.json'
    $json = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($json.schema -ne 1) { throw "player guard rules: schema $($json.schema), expected 1 ($file)" }
    $cats = @()
    foreach ($p in $json.categories.PSObject.Properties) {
        $cats += [pscustomobject]@{
            Name = $p.Name; Action = $p.Value.action
            Ws = @($p.Value.ws | ForEach-Object { $_.ToLower() }); Repo = @($p.Value.repo | ForEach-Object { $_.ToLower() })
            NameRx = @($p.Value.name)
        }
    }
    $norm = { param($x) ([IO.Path]::GetFullPath($x) -replace '\\', '/').TrimEnd('/').ToLower() }
    return [pscustomobject]@{
        Version = $json.version; Categories = $cats
        Allow = @($json.allow | ForEach-Object { $_.ws.ToLower() })
        Repository = (& $norm $Repository); Workspace = (& $norm (Split-Path -Parent $Repository))
    }
}

function Resolve-TruLinkPath {
    <#
    .SYNOPSIS
        Full path with junctions / symbolic links resolved component by component (private helper).
    #>
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $parts = $full.Substring($root.Length).Split([char[]]@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries)
    $cur = $root
    foreach ($part in $parts) {
        $cur = Join-Path $cur $part
        $item = Get-Item -LiteralPath $cur -Force -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType -in 'Junction', 'SymbolicLink' -and $item.Target) {
            $target = @($item.Target)[0]
            if (![IO.Path]::IsPathRooted($target)) { $target = Join-Path (Split-Path -Parent $cur) $target }
            $cur = [IO.Path]::GetFullPath($target)
        }
    }
    return $cur
}

function Test-TruPlayerPath {
    <#
    .SYNOPSIS
        Classifies one path by the player-path guard rules; $null when no rule matches.
    .DESCRIPTION
        Matches the path as written and with junctions resolved (lower case, forward slashes) against each
        category's workspace / repository prefixes and file-name patterns. A trailing bigfile part size
        ('@7ff00000') is ignored. Returns Category, Action (refuse / log / allow), Rule and the resolved Path.
        Nothing is opened.
    .PARAMETER Path
        Path to classify (relative paths are taken relative to -BaseDir).
    .PARAMETER Rules
        Get-TruPlayerGuardRules result.
    .PARAMETER BaseDir
        Folder relative paths start from (the repository: the pipeline's tools run there).
    .EXAMPLE
        Test-TruPlayerPath -Path '../data/TombRaiderUnderworld_Patched/layer1.000' -Rules $rules -BaseDir $clone
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Rules, [Parameter(Mandatory)][string]$BaseDir)
    $p = $Path -replace '@[0-9a-fA-F]+$', ''
    if (![IO.Path]::IsPathRooted($p)) { $p = Join-Path $BaseDir $p }
    try { $forms = @((Resolve-TruLinkPath $p), [IO.Path]::GetFullPath($p)) } catch { return $null }
    $forms = @($forms | ForEach-Object { ($_ -replace '\\', '/').TrimEnd('/').ToLower() } | Select-Object -Unique)
    $rel = foreach ($f in $forms) {
        [pscustomobject]@{
            Full = $f
            Ws   = $(if ($f.StartsWith($Rules.Workspace + '/')) { $f.Substring($Rules.Workspace.Length + 1) } else { $null })
            Repo = $(if ($f.StartsWith($Rules.Repository + '/')) { $f.Substring($Rules.Repository.Length + 1) } else { $null })
        }
    }
    foreach ($r in $rel) {
        if ($r.Ws -and $Rules.Allow -contains $r.Ws) {
            return [pscustomobject]@{ Category = 'tu_allow'; Action = 'allow'; Rule = $r.Ws; Path = $forms[0] }
        }
    }
    $hit = {
        param($relPath, $patterns)
        if ($null -eq $relPath) { return $null }
        foreach ($pat in $patterns) {
            if ($pat.EndsWith('/')) { if ($relPath -eq $pat.TrimEnd('/') -or $relPath.StartsWith($pat)) { return $pat } }
            elseif ($relPath.StartsWith($pat)) { return $pat }
        }
        return $null
    }
    foreach ($c in $Rules.Categories) {
        foreach ($r in $rel) {
            $rule = & $hit $r.Ws $c.Ws
            if (!$rule) { $rule = & $hit $r.Repo $c.Repo }
            if (!$rule) {
                $leaf = ($r.Full -split '/')[-1]
                foreach ($rx in $c.NameRx) { if ($leaf -match $rx) { $rule = $rx; break } }
            }
            if ($rule) { return [pscustomobject]@{ Category = $c.Name; Action = $c.Action; Rule = $rule; Path = $r.Full } }
        }
    }
    return $null
}

function Assert-TruPlayerToolArgs {
    <#
    .SYNOPSIS
        Checks the arguments of one pipeline tool call against the player-path guard rules before it starts.
    .DESCRIPTION
        Every argument (comma-separated lists are split, options starting with '-' skipped) is classified with
        Test-TruPlayerPath. Each match is logged (Write-Log). Mode Enforce throws when an argument names a path of
        a category with action refuse; mode Report only logs. Returns the matches. Nothing is opened; what a tool
        reads by itself (default paths in its code) is caught by tools\player_guard.py inside the process.
    .PARAMETER ToolArgs
        The tool and its arguments as passed to Invoke-Tool.
    .PARAMETER Rules
        Get-TruPlayerGuardRules result.
    .PARAMETER Mode
        Report or Enforce.
    .PARAMETER BaseDir
        The repository (working folder of the tools).
    .EXAMPLE
        Assert-TruPlayerToolArgs -ToolArgs $toolArgs -Rules $rules -Mode Enforce -BaseDir $clone
    #>
    [CmdletBinding()]
    param([string[]]$ToolArgs, [Parameter(Mandatory)]$Rules, [ValidateSet('Report', 'Enforce')][string]$Mode = 'Enforce',
          [Parameter(Mandatory)][string]$BaseDir)
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    $found = @()
    foreach ($a in $ToolArgs) {
        foreach ($p in ($a -split ',')) {
            if (!$p -or $p.StartsWith('-')) { continue }
            $m = Test-TruPlayerPath -Path $p -Rules $Rules -BaseDir $BaseDir
            if (!$m -or $m.Action -eq 'allow') { continue }
            $found += $m
            $verb = if ($m.Action -ne 'refuse') { 'logged' } elseif ($Mode -eq 'Enforce') { 'refused' } else { 'would-refuse' }
            Write-Log ('player guard: {0} argument {1} ({2}, rule {3}) of {4}' -f $verb, $p, $m.Category, $m.Rule, $ToolArgs[0]) -Level WARN
        }
    }
    $refused = @($found | Where-Object { $_.Action -eq 'refuse' })
    if ($Mode -eq 'Enforce' -and $refused.Count) {
        throw ('player guard: {0} refused argument(s) of {1}: {2}' -f $refused.Count, $ToolArgs[0], (($refused | ForEach-Object { $_.Path }) -join ', '))
    }
    return $found
}

function Get-TruInstalledRecord {
    <#
    .SYNOPSIS
        Returns path + MD5 of files an install just wrote (the "installed" list of an install manifest).
    .DESCRIPTION
        One object { path = <relative path>; md5 = <MD5 of Root\path> } per path. A missing file is an error: only
        files the install has written and verified are recorded. Added 2026-11-05 (E12).
    .PARAMETER Root
        Folder the relative paths are below (the game folder or its mods folder).
    .PARAMETER Path
        Relative paths.
    .EXAMPLE
        $installed = @(Get-TruInstalledRecord -Root $GamePath -Path 'tru.exe', 'binkw32.dll')
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [string[]]$Path)
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    foreach ($rel in @($Path)) {
        if (!$rel) { continue }
        $full = Join-Path $Root $rel
        if (!(Test-Path -LiteralPath $full -PathType Leaf)) { throw "Installed file missing: $full" }
        [pscustomobject]@{ path = $rel; md5 = (Get-Md5 $full) }
    }
}

function Get-TruInstallDeviation {
    <#
    .SYNOPSIS
        Compares the installed MD5s recorded in an install manifest with the files now below Root.
    .DESCRIPTION
        Returns one object { Path; Recorded; Now } per file that no longer has its recorded MD5 (Now = '(missing)'
        when the file is gone); nothing when every file is unchanged. Each comparison is logged at DEBUG level.
        Added 2026-11-05 (E12).
    .PARAMETER Root
        Folder the recorded paths are below.
    .PARAMETER Installed
        The manifest's installed list (objects with path and md5).
    .EXAMPLE
        $dev = @(Get-TruInstallDeviation -Root $mods -Installed $manifest.installed)
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [object[]]$Installed)
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    foreach ($entry in @($Installed)) {
        if (!$entry) { continue }
        $full = Join-Path $Root ([string]$entry.path)
        $now = if (Test-Path -LiteralPath $full -PathType Leaf) { Get-Md5 $full } else { '(missing)' }
        Write-Log ('installed md5 {0}: recorded {1}, now {2}' -f $entry.path, $entry.md5, $now) -Level DEBUG
        if ($now -ne [string]$entry.md5) {
            [pscustomobject]@{ Path = [string]$entry.path; Recorded = [string]$entry.md5; Now = $now }
        }
    }
}

function Assert-TruRestoreAllowed {
    <#
    .SYNOPSIS
        Refuses a restore when installed files were changed after the install; -Force restores anyway, saves the
        changed files first and logs the override.
    .DESCRIPTION
        Without deviations nothing happens. Each deviation is logged as WARN. Without -Force the function throws
        (the caller has changed nothing yet). With -Force every deviating file that still exists is copied to
        SaveDir\<path> (MD5-checked), SaveDir\forced_restore.json lists all deviations, and a WARN line
        'FORCED restore ...' goes to the run log. Added 2026-11-05 (E12).
    .PARAMETER Deviation
        Output of Get-TruInstallDeviation.
    .PARAMETER Root
        Folder the deviation paths are below.
    .PARAMETER What
        Name of the install being undone (for the messages).
    .PARAMETER SaveDir
        Folder for the copies of the changed files (only used with -Force).
    .PARAMETER Force
        Restore anyway.
    .EXAMPLE
        Assert-TruRestoreAllowed -Deviation $dev -Root $mods -What 'tree_20261105_120000' -SaveDir $save -Force:$Force
    #>
    [CmdletBinding()]
    param(
        [object[]]$Deviation,
        [Parameter(Mandatory)][string]$Root,
        [string]$What,
        [string]$SaveDir,
        [switch]$Force
    )
    foreach ($preference in (Get-TruCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local
    }
    $dev = @($Deviation | Where-Object { $_ })
    if (!$dev.Count) { return }
    foreach ($d in $dev) {
        Write-Log ('changed since the install: {0} - installed {1}, now {2}' -f $d.Path, $d.Recorded, $d.Now) -Level WARN
    }
    if (!$Force) {
        throw (('Restore refused: {0} file(s) of {1} no longer have the MD5 the install wrote (changed after the ' +
                'install - by hand, by another tool or by a later install that is not undone yet). Nothing was ' +
                'changed. Undo the later installs first, or pass -Force to restore anyway (the changed files are ' +
                'saved before they are overwritten or removed).') -f $dev.Count, $What)
    }
    $saved = 0
    if ($SaveDir) {
        New-Item -ItemType Directory -Force -Path $SaveDir | Out-Null
        foreach ($d in $dev) {
            $src = Join-Path $Root $d.Path
            if (!(Test-Path -LiteralPath $src -PathType Leaf)) { continue }
            $dst = Join-Path $SaveDir $d.Path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $src -Destination $dst -Force
            if ((Get-Md5 $dst) -ne $d.Now) { throw "Saving the changed file $($d.Path) failed (MD5 differs) - nothing restored." }
            Write-Log "saved changed file $($d.Path) -> $dst" -Level VERBOSE
            $saved++
        }
        [pscustomobject]@{ time = (Get-Date -Format 'yyyyMMdd_HHmmss'); install = $What; root = $Root; deviations = $dev } |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $SaveDir 'forced_restore.json') -Encoding UTF8
    }
    Write-Log ('FORCED restore of {0}: -Force overrides {1} changed file(s); {2} of them saved to {3}' -f
        $What, $dev.Count, $saved, $(if ($SaveDir) { $SaveDir } else { '(not saved)' })) -Level WARN
}

Export-ModuleMember -Function Set-TruLogFile, Write-Log, Get-TruWorkspacePath, Find-TruGamePath, Get-Md5,
    Get-TruInstalledRecord, Get-TruInstallDeviation, Assert-TruRestoreAllowed,
    Get-TruPlayerGuardRules, Test-TruPlayerPath, Assert-TruPlayerToolArgs
