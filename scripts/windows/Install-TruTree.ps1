<#
.SYNOPSIS
    Lays a converted mods tree (e.g. the DLC 2 test tree) over the game's mods\ folder, with backup and exact undo.

.DESCRIPTION
    Install: every file of -Source (sub folders included, except the top folders in -Exclude) is copied to
    <game>\mods\<same path>. Files that already exist and differ are saved first under
    <workspace>\backup\tree_<time>\files\<path>; a manifest (manifest.json) lists the files added and replaced
    (old MD5 of each replaced file) and, since 2026-11-05 (manifest_version 2), "installed": path + MD5 of every
    file this install wrote. Every copied file is MD5-checked.
    -Check   dry run: lists what would be added / replaced / is already equal; changes nothing.
    -Restore undoes an install: replaced files come back from the backup, added files are removed (only those
             listed in the manifest). Uses the newest backup\tree_* that is not undone yet unless -BackupName is
             given, and renames it to *.restored afterwards - installs stack, one -Restore undoes one install.
             Simplest: -Restore before installing a newer build of the same tree.
             Before anything is changed: every backup must have its recorded MD5, and every installed file must
             still have the MD5 the install wrote. A file changed since (by hand, a single-file install, or a later
             tree install that is not undone yet - e.g. restores in the wrong order) makes -Restore refuse with
             the list of files. Manifests written before 2026-11-05 have no installed MD5s: not checked (logged).
    -Force   with -Restore: restore even when installed files were changed; the changed files are first saved
             to <backup>\overwritten_<time>\<path> (+ forced_restore.json) and the override is logged as WARN.

    -Exclude defaults to 'local','padshock': the installed string tables carry the DLC menu text fix
    (docs/DLC_MENU.md) and would be overwritten by tables without it; padshock is the same file.
    The game folder is taken from the Steam libraries (app 8140) unless -GamePath is given.
    Every run writes <workspace>\logs\Install-TruTree_<time>_<mode>.log. -Verbose shows steps, -Debug paths/hashes,
    -Trace adds a PowerShell line trace. The script never stops a running game; it aborts instead.

.EXAMPLE
    .\scripts\windows\Install-TruTree.ps1 -Source .\work\rebuild\dlc2_test\mods -Check -Verbose
.EXAMPLE
    .\scripts\windows\Install-TruTree.ps1 -Source .\work\rebuild\dlc2_test\mods -Verbose
.EXAMPLE
    .\scripts\windows\Install-TruTree.ps1 -Restore -Verbose
.EXAMPLE
    .\scripts\windows\Install-TruTree.ps1 -Restore -BackupName tree_20261105_155132 -Force -Verbose
#>
[CmdletBinding()]
param(
    [string]$Source,
    [string[]]$Exclude = @('local', 'padshock'),
    [switch]$Check,
    [switch]$Restore,
    [string]$BackupName,
    [string]$GamePath,
    [switch]$Force,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Find-TruGamePath, Get-Md5, Get-TruWorkspacePath
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$backupDir = Join-Path $root 'backup'
$logDir    = $paths.Logs
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
$mode      = if ($Restore) { 'Restore' } elseif ($Check) { 'Check' } else { 'Install' }

New-Item -ItemType Directory -Force -Path $logDir, $backupDir | Out-Null
$logFile = Join-Path $logDir ('Install-TruTree_{0}_{1}.log' -f $stamp, $mode)
Set-TruLogFile -Path $logFile

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Install-TruTree mode=$mode source=$Source exclude=$($Exclude -join ',') force=$([bool]$Force) log=$logFile" -Level VERBOSE
    if ($Force -and !$Restore) { Write-Log '-Force only applies to -Restore - ignored.' -Level WARN }
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) {
        throw 'Tomb Raider: Underworld (tru.exe) is running. Please close the game first.'
    }
    if (!$GamePath) {
        $GamePath = Find-TruGamePath
        if (!$GamePath) { throw 'Game folder not found in the Steam libraries; pass -GamePath.' }
        Write-Log "Game folder found via Steam: $GamePath" -Level VERBOSE
    }
    $mods = Join-Path $GamePath 'mods'
    if (!(Test-Path -LiteralPath $mods)) { throw "No mods folder in $GamePath (is the B138 kit / ModLoader installed?)" }

    if ($Restore) {
        # installs stack: each -Restore undoes the newest install that is not undone yet (done ones end in .restored)
        $candidates = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' |
            Where-Object { $_.Name -notlike '*.restored' } | Sort-Object Name)
        if ($BackupName) { $candidates = @($candidates | Where-Object { $_.Name -eq $BackupName }) }
        if (!$candidates.Count) { throw "No backup\tree_* found$(if ($BackupName) { " named $BackupName" })." }
        $bk = $candidates[-1].FullName
        $manifest = Get-Content -LiteralPath (Join-Path $bk 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Log "Restoring from $bk (installed $($manifest.time) from $($manifest.source))"
        $replacedList = @(@($manifest.replaced) | Where-Object { $_ })
        $addedList = @(@($manifest.added) | Where-Object { $_ })
        # checks first, so that a refusal leaves the game folder untouched: every backup has its recorded MD5 ...
        foreach ($r in $replacedList) {
            $saved = Join-Path $bk "files\$($r.path)"
            if (!(Test-Path -LiteralPath $saved -PathType Leaf) -or (Get-Md5 $saved) -ne $r.md5) {
                throw "Backup of $($r.path) does not match its recorded MD5 - nothing changed."
            }
        }
        # ... and (E12, 2026-11-05) every file the install wrote still has the MD5 it had after the install
        $installed = @(@($manifest.installed) | Where-Object { $_ })
        if ($installed.Count) {
            $recorded = @{}
            foreach ($i in $installed) { $recorded[[string]$i.path] = $true }
            foreach ($u in (@($replacedList | ForEach-Object { [string]$_.path }) + @($addedList | ForEach-Object { [string]$_ }))) {
                if (!$recorded.ContainsKey($u)) {
                    Write-Log "no installed MD5 recorded for mods\$u (install interrupted before its copy was verified?) - not checked" -Level WARN
                }
            }
            $deviation = @(Get-TruInstallDeviation -Root $mods -Installed $installed)
            Write-Log ('Installed files: {0} of {1} unchanged since the install, {2} changed.' -f
                ($installed.Count - $deviation.Count), $installed.Count, $deviation.Count)
            Assert-TruRestoreAllowed -Deviation $deviation -Root $mods -What (Split-Path -Leaf $bk) -Force:$Force `
                -SaveDir (Join-Path $bk ('overwritten_' + $stamp))
        }
        elseif ([int]$manifest.manifest_version -ge 2) {
            Write-Log 'Installed files not checked: the manifest lists none (install interrupted before its first copy was verified?).' -Level WARN
        }
        else {
            Write-Log 'Installed files not checked: this manifest has no installed MD5s (install made before 2026-11-05).'
        }
        foreach ($r in $replacedList) {
            $saved = Join-Path $bk "files\$($r.path)"
            $dst = Join-Path $mods $r.path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $saved -Destination $dst -Force
            if ((Get-Md5 $dst) -ne $r.md5) { throw "Restored mods\$($r.path) does not match the backup." }
            Write-Log "restored  mods\$($r.path)" -Level VERBOSE
        }
        foreach ($a in $addedList) {
            $p = Join-Path $mods $a
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force; Write-Log "removed   mods\$a" -Level VERBOSE }
        }
        # folders the install created (recorded in the manifest), deepest first, only when empty again
        foreach ($d in (@($manifest.created_dirs) | Where-Object { $_ } | Sort-Object Length -Descending)) {
            $p = Join-Path $mods $d
            if ((Test-Path -LiteralPath $p) -and !(Get-ChildItem -LiteralPath $p -Force | Select-Object -First 1)) {
                Remove-Item -LiteralPath $p -Force; Write-Log "removed   folder mods\$d" -Level DEBUG
            }
        }
        Write-Log ('Restore done: {0} files restored, {1} added files removed.' -f @($manifest.replaced).Count, @($manifest.added).Count)
        Rename-Item -LiteralPath $bk -NewName ((Split-Path -Leaf $bk) + '.restored')
        Write-Log "Backup marked as undone: $bk.restored (the next -Restore undoes the install before it, if any)" -Level VERBOSE
        return
    }

    if (!$Source) { throw 'Pass -Source (a mods tree) or -Restore.' }
    $src = (Resolve-Path -LiteralPath $Source).Path
    $files = @(Get-ChildItem -LiteralPath $src -Recurse -File)
    $added = New-Object System.Collections.Generic.List[string]
    $replaced = New-Object System.Collections.Generic.List[object]
    $same = 0; $skipped = 0; $plan = @()
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($src.Length).TrimStart('\')
        $top = ($rel -split '\\')[0]
        if ($Exclude -contains $top) { $skipped++; continue }
        $dst = Join-Path $mods $rel
        $md5 = Get-Md5 $f.FullName
        if (Test-Path -LiteralPath $dst) {
            $old = Get-Md5 $dst
            if ($old -eq $md5) { $same++; continue }
            $plan += [pscustomobject]@{ Rel = $rel; Src = $f.FullName; Md5 = $md5; Action = 'replace'; Old = $old }
        } else {
            $plan += [pscustomobject]@{ Rel = $rel; Src = $f.FullName; Md5 = $md5; Action = 'add'; Old = $null }
        }
    }
    $nAdd = @($plan | Where-Object { $_.Action -eq 'add' }).Count
    $nRep = @($plan | Where-Object { $_.Action -eq 'replace' }).Count
    Write-Log ('{0} files in the source: add {1}, replace {2}, already equal {3}, excluded {4} ({5})' -f
        $files.Count, $nAdd, $nRep, $same, $skipped, ($Exclude -join ', '))
    foreach ($p in ($plan | Where-Object { $_.Action -eq 'replace' })) { Write-Log "replace   mods\$($p.Rel)" }
    foreach ($p in ($plan | Where-Object { $_.Action -eq 'add' })) { Write-Log "add       mods\$($p.Rel)" -Level VERBOSE }
    if ($Check) { Write-Log 'Check only - nothing changed.'; return }
    if (!$plan.Count) { Write-Log 'Nothing to install.'; return }
    $open = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' | Where-Object { $_.Name -notlike '*.restored' })
    if ($open.Count) {
        Write-Log ('{0} earlier install(s) not undone yet ({1}); this one stacks on top - undo needs one -Restore per install.' -f
            $open.Count, (($open | Sort-Object Name | ForEach-Object { $_.Name }) -join ', ')) -Level WARN
    }

    $bk = Join-Path $backupDir "tree_$stamp"
    # two installs in the same second (e.g. Invoke-TruTestRun stacking small trees) would share one backup folder and
    # the second manifest would overwrite the first: wait for a free second instead (keeps the name order for -Restore)
    while ((Test-Path -LiteralPath $bk) -or (Test-Path -LiteralPath "$bk.restored")) {
        Write-Log "backup folder tree_$stamp exists already - waiting for the next second" -Level VERBOSE
        Start-Sleep -Milliseconds 250
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $bk = Join-Path $backupDir "tree_$stamp"
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $bk 'files') | Out-Null
    # folders that do not exist yet and will be created by the copies (so -Restore removes exactly these)
    $createdDirs = New-Object System.Collections.Generic.List[string]
    foreach ($p in ($plan | Where-Object { $_.Action -eq 'add' })) {
        $d = Split-Path -Parent (Join-Path $mods $p.Rel)
        while ($d.Length -gt $mods.Length -and !(Test-Path -LiteralPath $d)) {
            $r = $d.Substring($mods.Length).TrimStart('\')
            if (!$createdDirs.Contains($r)) { $createdDirs.Add($r) }
            $d = Split-Path -Parent $d
        }
    }
    # installed: path + MD5 of every file this install wrote (E12, 2026-11-05) - -Restore refuses when one of them
    # was changed afterwards; new fields only, readers of added / replaced / created_dirs see the old format
    $installedFiles = New-Object System.Collections.Generic.List[object]
    $writeManifest = {
        [pscustomobject]@{ time = $stamp; source = $src; game = $GamePath; added = $added; replaced = $replaced;
                           created_dirs = $createdDirs; manifest_version = 2; installed = $installedFiles } |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $bk 'manifest.json') -Encoding UTF8
    }
    foreach ($p in $plan) {
        $dst = Join-Path $mods $p.Rel
        if ($p.Action -eq 'replace') {
            $saved = Join-Path $bk "files\$($p.Rel)"
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
            Copy-Item -LiteralPath $dst -Destination $saved
            if ((Get-Md5 $saved) -ne $p.Old) { throw "Backup copy of mods\$($p.Rel) is not identical." }
            $replaced.Add([pscustomobject]@{ path = $p.Rel; md5 = $p.Old })
        } else {
            $added.Add($p.Rel)
        }
        # write the manifest before each copy, so an interrupted run can still be undone
        & $writeManifest
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
        Copy-Item -LiteralPath $p.Src -Destination $dst -Force
        if ((Get-Md5 $dst) -ne $p.Md5) { throw "Copied mods\$($p.Rel) does not match the source." }
        $installedFiles.Add([pscustomobject]@{ path = $p.Rel; md5 = $p.Md5 })
        Write-Log ('{0,-9} mods\{1}  {2}' -f $p.Action, $p.Rel, $p.Md5) -Level DEBUG
    }
    & $writeManifest
    Write-Log ('Installed: {0} added, {1} replaced. Backup and manifest: {2} (undo with -Restore).' -f $added.Count, $replaced.Count, $bk)
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
