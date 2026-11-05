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
    Get-TruInstalledRecord, Get-TruInstallDeviation, Assert-TruRestoreAllowed
