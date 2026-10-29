<#
.SYNOPSIS
    Shared helpers of the trudlcport Windows scripts: run log, workspace paths, Steam game folder, MD5.

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
    Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8
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

Export-ModuleMember -Function Set-TruLogFile, Write-Log, Get-TruWorkspacePath, Find-TruGamePath, Get-Md5
