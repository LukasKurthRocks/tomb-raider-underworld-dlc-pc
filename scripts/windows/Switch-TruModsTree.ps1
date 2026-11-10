<#
.SYNOPSIS
    Swaps the game's whole mods\ folder for another complete mods tree (e.g. the own tree built only from our
    pipeline, work\own_1011\mods) and back - by renaming and copying only, never deleting.

.DESCRIPTION
    Switch (default):
      1. checks: no tru.exe of this game folder running (also refused when its path cannot be read; -Check only
         warns), game folder and <game>\mods exist, the source tree matches its manifest
         (own_manifest.tsv of tools/own_tree.py assemble: every file with its MD5, no extra file), no name containing
         "TruGuard" in the source, enough free space on the game drive, no target folder name in use;
      2. copies the source tree to <game>\mods_incoming_<time> and checks the MD5 of every copied file;
      3. -CarryOver: copies the listed files (paths relative to mods) from the current mods\ into the incoming tree
         (only files the source does not have; a file of the source is never overwritten);
      4. renames <game>\mods -> <game>\mods_stack_<time> (the installed stack stays complete, byte for byte),
         then <game>\mods_incoming_<time> -> <game>\mods;
      5. writes the record <workspace>\backup\mods_switch_<time>\switch.json (game, source, folder names, file count
         and bytes of both folders) - the input of -Rollback.
      If a step fails before the first rename, the game folder still has its old mods\ (the incoming folder is left
      for inspection, never deleted). If the second rename fails, the script renames mods_stack_<time> back.

    -Rollback: undoes the newest switch that is not rolled back yet (or -SwitchName): checks that
      <game>\mods_stack_<time> still has the file count and bytes recorded at the switch, renames <game>\mods ->
      <game>\mods_own_<time> (kept, with anything installed onto it since) and <game>\mods_stack_<time> -> <game>\mods,
      checks count and bytes again and marks the record as rolled back. Nothing is deleted; remove the kept folders by
      hand when they are no longer needed.

    -Check: dry run of the chosen mode - every check above, the planned names and the differences between the source
      and the current mods\ (counts), nothing is written but the log. -WhatIf: the same steps without any change.

    The script only reads or writes <game>\mods and <game>\mods_* folders and <workspace>\backup\mods_switch_*:
    tru.exe, the plugin .asi / .ini files in the game root and any file named *TruGuard* are never touched, listed or
    opened (names containing "TruGuard" are filtered out of every listing before anything is printed).
    While the own tree is active, do not run Install-TruTree.ps1 -Restore or Invoke-TruTestRun.ps1 -Undo: the open
    backup\tree_* installs belong to the stack (now mods_stack_<time>); roll back first.

    Every run writes <workspace>\logs\Switch-TruModsTree_<time>_<mode>.log. -Verbose shows steps, -Debug paths and
    hashes, -Trace adds a PowerShell line trace.

.PARAMETER Source
    Complete mods tree to switch to; default <repository>\work\own_1011\mods.
.PARAMETER Manifest
    TSV with columns rel, size, md5 (tools/own_tree.py own_manifest.tsv); default <Source>\..\own_manifest.tsv.
    Rows whose rel starts with "../" (the exe) are not part of mods and ignored.
.PARAMETER CarryOver
    Files (relative to mods, e.g. 'local\locals.bin_001') to take over from the current mods\ into the new one.
.PARAMETER CarryOverFile
    Text file with more -CarryOver paths, one per line (empty lines and lines starting with # are ignored).
.PARAMETER Rollback
    Undo the newest open switch (or -SwitchName).
.PARAMETER SwitchName
    With -Rollback: the record folder name, e.g. mods_switch_20261111_090000.
.PARAMETER Check
    Dry run: checks and plan only.
.PARAMETER GamePath
    Game folder; default: found via the Steam libraries. For tests: a scratch folder with a mods\ sub folder.
.PARAMETER RecordDir
    Folder of the mods_switch_<time> records; default <workspace>\backup (tests on a scratch game folder: a scratch
    folder, so no test record lies next to the real ones).
.PARAMETER Trace
    PowerShell line trace (Set-PSDebug -Trace 1).

.EXAMPLE
    .\scripts\windows\Switch-TruModsTree.ps1 -Check -Verbose
.EXAMPLE
    .\scripts\windows\Switch-TruModsTree.ps1 -Verbose
.EXAMPLE
    .\scripts\windows\Switch-TruModsTree.ps1 -Rollback -Check -Verbose
.EXAMPLE
    .\scripts\windows\Switch-TruModsTree.ps1 -Rollback -Verbose
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Source,
    [string]$Manifest,
    [string[]]$CarryOver = @(),
    [string]$CarryOverFile,
    [switch]$Rollback,
    [string]$SwitchName,
    [switch]$Check,
    [string]$GamePath,
    [string]$RecordDir,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Find-TruGamePath, Get-Md5, Get-TruWorkspacePath
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$backupDir = Join-Path $root 'backup'
if (!$RecordDir) { $RecordDir = $backupDir }
$logDir    = $paths.Logs
$stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'
$mode      = if ($Rollback) { 'Rollback' } else { 'Switch' }
if ($Check) { $mode += 'Check' } elseif ($WhatIfPreference) { $mode += 'WhatIf' }

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Switch-TruModsTree_{0}_{1}.log' -f $stamp, $mode)
Set-TruLogFile -Path $logFile

function Test-Hidden {
    # names that are never listed, printed or touched
    param([string]$Name)
    return ($Name -match '(?i)truguard')
}

function Get-TreeFiles {
    # every file below $Dir as @{ rel (lower case key) -> FileInfo }, names containing TruGuard filtered out
    # (counted in $script:hiddenCount, never printed)
    param([string]$Dir)
    $map = @{}
    $script:hiddenCount = 0
    $base = (Resolve-Path -LiteralPath $Dir).Path.TrimEnd('\')
    foreach ($f in @(Get-ChildItem -LiteralPath $base -Recurse -File -Force)) {
        $rel = $f.FullName.Substring($base.Length).TrimStart('\')
        if (Test-Hidden $rel) { $script:hiddenCount++; continue }
        $map[$rel.ToLowerInvariant()] = $f
    }
    return $map
}

function Get-TreeStat {
    # file count and bytes of a folder (names containing TruGuard filtered out, as everywhere)
    param([string]$Dir)
    $base = (Resolve-Path -LiteralPath $Dir).Path.TrimEnd('\')
    $files = @(Get-ChildItem -LiteralPath $base -Recurse -File -Force |
        Where-Object { !(Test-Hidden $_.FullName.Substring($base.Length)) })
    $bytes = [long]0
    foreach ($f in $files) { $bytes += $f.Length }
    return [pscustomobject]@{ Files = $files.Count; Bytes = $bytes }
}

function Assert-ModsTarget {
    # every folder this script renames or creates must be <game>\mods or <game>\mods_<something>, never a TruGuard name
    param([string]$Path)
    $leaf = Split-Path -Leaf $Path
    $parent = (Split-Path -Parent $Path).TrimEnd('\')
    if ($parent -ne $GamePath.TrimEnd('\') -or $leaf -notmatch '^mods(_[A-Za-z]+_\d{8}_\d{6})?$' -or (Test-Hidden $leaf)) {
        throw "Refused: $Path is not a mods folder of the game folder."
    }
}

function Read-SourceManifest {
    # rel -> @{ size; md5 } from the TSV (header rel / size / md5 ...); rows of files outside mods ('../') skipped
    param([string]$Path)
    $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    $head = $lines[0] -split "`t"
    $iRel = [array]::IndexOf($head, 'rel'); $iSize = [array]::IndexOf($head, 'size'); $iMd5 = [array]::IndexOf($head, 'md5')
    if ($iRel -lt 0 -or $iSize -lt 0 -or $iMd5 -lt 0) { throw "Manifest $Path has no rel / size / md5 columns." }
    $map = @{}
    foreach ($ln in ($lines | Select-Object -Skip 1)) {
        if (!$ln) { continue }
        $c = $ln -split "`t"
        if ($c[$iRel].StartsWith('../')) { continue }
        $map[($c[$iRel] -replace '/', '\').ToLowerInvariant()] = [pscustomobject]@{ Rel = ($c[$iRel] -replace '/', '\'); Size = [long]$c[$iSize]; Md5 = $c[$iMd5] }
    }
    return $map
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Switch-TruModsTree mode=$mode log=$logFile" -Level VERBOSE
    if (!$GamePath) {
        $GamePath = Find-TruGamePath
        if (!$GamePath) { throw 'Game folder not found in the Steam libraries; pass -GamePath.' }
        Write-Log "Game folder found via Steam: $GamePath" -Level VERBOSE
    }
    $GamePath = (Resolve-Path -LiteralPath $GamePath).Path.TrimEnd('\')
    $mods = Join-Path $GamePath 'mods'
    Write-Log "Game folder: $GamePath"
    # a running tru.exe of THIS game folder (or one whose path cannot be read) blocks every change; a dry run goes on.
    # A tru.exe started from another folder does not use this mods folder (logged, e.g. tests on a scratch copy).
    foreach ($proc in @(Get-Process -Name 'tru' -ErrorAction SilentlyContinue)) {
        $exePath = $null
        try { $exePath = $proc.Path } catch { $exePath = $null }
        if ($exePath -and !$exePath.StartsWith($GamePath + '\', [StringComparison]::OrdinalIgnoreCase)) {
            Write-Log "tru.exe (PID $($proc.Id)) runs from another folder ($exePath) - it does not use $mods." -Level VERBOSE
            continue
        }
        if (!$Check) { throw "Tomb Raider: Underworld (tru.exe, PID $($proc.Id)) is running. Please close the game first - nothing changed." }
        Write-Log "tru.exe (PID $($proc.Id)) is running: a real run would refuse now (dry run goes on, nothing is changed)." -Level WARN
    }
    $openTrees = @()
    if (Test-Path -LiteralPath $backupDir) {
        $openTrees = @(Get-ChildItem -LiteralPath $backupDir -Directory -Filter 'tree_*' |
            Where-Object { $_.Name -notlike '*.restored' -and !(Test-Hidden $_.Name) })
    }

    if ($Rollback) {
        $records = @()
        if (Test-Path -LiteralPath $RecordDir) {
            $records = @(Get-ChildItem -LiteralPath $RecordDir -Directory -Filter 'mods_switch_*' | Sort-Object Name |
                Where-Object { $rec = Get-Content -LiteralPath (Join-Path $_.FullName 'switch.json') -Raw -Encoding UTF8 | ConvertFrom-Json
                               $rec.state -eq 'switched' -and $rec.game -eq $GamePath })
        }
        if ($SwitchName) { $records = @($records | Where-Object { $_.Name -eq $SwitchName }) }
        if (!$records.Count) { throw "No open switch record for $GamePath$(if ($SwitchName) { " named $SwitchName" }) in $RecordDir - nothing changed." }
        $recDir = $records[-1].FullName
        $recFile = Join-Path $recDir 'switch.json'
        $rec = Get-Content -LiteralPath $recFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $stackDir = Join-Path $GamePath $rec.stack_folder
        $ownKeep = Join-Path $GamePath ('mods_own_' + $stamp)
        Assert-ModsTarget $stackDir; Assert-ModsTarget $ownKeep; Assert-ModsTarget $mods
        Write-Log "Rollback of $(Split-Path -Leaf $recDir) (switched $($rec.time) to $($rec.source))"
        if (!(Test-Path -LiteralPath $stackDir -PathType Container)) { throw "The stack folder $stackDir is missing - nothing changed." }
        if (!(Test-Path -LiteralPath $mods -PathType Container)) { throw "No mods folder in $GamePath - nothing changed." }
        if (Test-Path -LiteralPath $ownKeep) { throw "$ownKeep exists already - nothing changed." }
        $stackStat = Get-TreeStat $stackDir
        Write-Log ('stack folder {0}: {1} files, {2} bytes (recorded at the switch: {3} files, {4} bytes)' -f
            $rec.stack_folder, $stackStat.Files, $stackStat.Bytes, $rec.stack_files, $rec.stack_bytes)
        if ($stackStat.Files -ne [int]$rec.stack_files -or $stackStat.Bytes -ne [long]$rec.stack_bytes) {
            throw "The stack folder changed since the switch (file count / bytes differ) - nothing changed; check it by hand."
        }
        $nowStat = Get-TreeStat $mods
        Write-Log ('current mods: {0} files, {1} bytes (own tree at the switch: {2} files, {3} bytes){4}' -f $nowStat.Files,
            $nowStat.Bytes, $rec.own_files, $rec.own_bytes, $(if ($nowStat.Files -ne [int]$rec.own_files -or $nowStat.Bytes -ne [long]$rec.own_bytes) { ' - changed since the switch, kept as is' } else { '' }))
        Write-Log "plan: rename mods -> $(Split-Path -Leaf $ownKeep), $($rec.stack_folder) -> mods"
        if ($Check) { Write-Log 'Check only - nothing changed.'; return }
        if (!$PSCmdlet.ShouldProcess($GamePath, "rename mods -> $(Split-Path -Leaf $ownKeep), $($rec.stack_folder) -> mods")) { return }
        Rename-Item -LiteralPath $mods -NewName (Split-Path -Leaf $ownKeep)
        try { Rename-Item -LiteralPath $stackDir -NewName 'mods' }
        catch {
            Write-Log "second rename failed ($($_.Exception.Message)) - putting the own tree back as mods" -Level ERROR
            Rename-Item -LiteralPath $ownKeep -NewName 'mods'
            throw
        }
        $after = Get-TreeStat $mods
        if ($after.Files -ne [int]$rec.stack_files -or $after.Bytes -ne [long]$rec.stack_bytes) {
            throw "mods after the rollback has $($after.Files) files / $($after.Bytes) bytes, recorded $($rec.stack_files) / $($rec.stack_bytes)."
        }
        $rec.state = 'rolledback'
        $rec | Add-Member -NotePropertyName rollback_time -NotePropertyValue $stamp -Force
        $rec | Add-Member -NotePropertyName own_kept_as -NotePropertyValue (Split-Path -Leaf $ownKeep) -Force
        $rec | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recFile -Encoding UTF8
        Write-Log ('Rollback done: mods = the stack again ({0} files, {1} bytes); the own tree is kept as {2}.' -f $after.Files, $after.Bytes, (Split-Path -Leaf $ownKeep))
        return
    }

    # ---- switch
    if (!$Source) { $Source = Join-Path $paths.Repository 'work\own_1011\mods' }
    $Source = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
    if ((Split-Path -Leaf $Source) -ne 'mods') { throw "-Source must be a ...\mods folder: $Source" }
    if (!$Manifest) { $Manifest = Join-Path (Split-Path -Parent $Source) 'own_manifest.tsv' }
    if (!(Test-Path -LiteralPath $Manifest -PathType Leaf)) { throw "Manifest not found: $Manifest" }
    if (!(Test-Path -LiteralPath $mods -PathType Container)) { throw "No mods folder in $GamePath (ModLoader / kit installed?) - nothing changed." }
    $stackDir = Join-Path $GamePath ('mods_stack_' + $stamp)
    $incoming = Join-Path $GamePath ('mods_incoming_' + $stamp)
    Assert-ModsTarget $stackDir; Assert-ModsTarget $incoming; Assert-ModsTarget $mods
    foreach ($p in $stackDir, $incoming) { if (Test-Path -LiteralPath $p) { throw "$p exists already - nothing changed." } }
    Write-Log "Source: $Source"
    Write-Log "Manifest: $Manifest" -Level VERBOSE

    # source against its manifest: same file set, sizes and MD5s
    $want = Read-SourceManifest $Manifest
    $src = Get-TreeFiles $Source
    if ($script:hiddenCount) { throw "The source holds $($script:hiddenCount) file(s) with a TruGuard name - refused, nothing changed." }
    $bad = @()
    foreach ($k in $want.Keys) {
        if (!$src.ContainsKey($k)) { $bad += "missing in the source: $($want[$k].Rel)"; continue }
        if ($src[$k].Length -ne $want[$k].Size) { $bad += "size differs: $($want[$k].Rel)"; continue }
        $m = Get-Md5 $src[$k].FullName
        Write-Log ('{0}  {1}' -f $m, $want[$k].Rel) -Level DEBUG
        if ($m -ne $want[$k].Md5) { $bad += "MD5 differs: $($want[$k].Rel)" }
    }
    foreach ($k in $src.Keys) { if (!$want.ContainsKey($k)) { $bad += "not in the manifest: $($src[$k].FullName.Substring($Source.Length + 1))" } }
    if ($bad.Count) { foreach ($b in $bad) { Write-Log $b -Level ERROR }; throw "Source tree does not match its manifest ($($bad.Count) problems) - nothing changed." }
    $srcBytes = [long]0; foreach ($f in $src.Values) { $srcBytes += $f.Length }
    Write-Log ('Source matches the manifest: {0} files, {1} bytes, every MD5 checked.' -f $src.Count, $srcBytes)

    # the current mods folder (names with TruGuard filtered out before anything is compared or printed)
    $cur = Get-TreeFiles $mods
    $curHidden = $script:hiddenCount
    $curStat = Get-TreeStat $mods
    $onlyCur = @($cur.Keys | Where-Object { !$src.ContainsKey($_) } | Sort-Object)
    $onlySrc = @($src.Keys | Where-Object { !$cur.ContainsKey($_) })
    $both = @($src.Keys | Where-Object { $cur.ContainsKey($_) })
    $sameSize = @($both | Where-Object { $src[$_].Length -eq $cur[$_].Length }).Count
    Write-Log ('current mods: {0} files, {1} bytes{2}; in both {3} ({4} of them same size), only current {5}, only source {6}' -f
        $curStat.Files, $curStat.Bytes, $(if ($curHidden) { " (incl. $curHidden filtered names)" } else { '' }), $both.Count, $sameSize, $onlyCur.Count, $onlySrc.Count)
    foreach ($k in $onlyCur) { Write-Log ('only in the current mods (stays in {0}): {1}' -f (Split-Path -Leaf $stackDir), $cur[$k].FullName.Substring($mods.Length + 1)) -Level VERBOSE }

    # -CarryOver: files of the current mods the new tree should keep
    $carry = @()
    $carryList = @($CarryOver)
    if ($CarryOverFile) {
        if (!(Test-Path -LiteralPath $CarryOverFile -PathType Leaf)) { throw "-CarryOverFile not found: $CarryOverFile - nothing changed." }
        $carryList += @(Get-Content -LiteralPath $CarryOverFile -Encoding UTF8 | ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and !$_.StartsWith('#') })
        Write-Log ('{0} carry-over path(s) from {1}' -f ($carryList.Count - @($CarryOver).Count), $CarryOverFile) -Level VERBOSE
    }
    foreach ($c in $carryList) {
        $k = ($c -replace '/', '\').TrimStart('\').ToLowerInvariant()
        if (Test-Hidden $k) { throw 'Refused: a -CarryOver name contains TruGuard.' }
        if (!$cur.ContainsKey($k)) { throw "-CarryOver: $c is not in the current mods - nothing changed." }
        if ($src.ContainsKey($k)) { throw "-CarryOver: $c is part of the source tree; it is never overwritten - nothing changed." }
        $carry += $cur[$k]
        Write-Log "carry over: $c" -Level VERBOSE
    }
    $carryBytes = [long]0; foreach ($f in $carry) { $carryBytes += $f.Length }

    # free space on the game drive: the copy + 1 GB
    $drive = (Split-Path -Qualifier $GamePath)
    $free = [long](Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='{0}'" -f $drive)).FreeSpace
    $need = $srcBytes + $carryBytes + 1GB
    Write-Log ('free space on {0}: {1:N1} GB, needed {2:N1} GB' -f $drive, ($free / 1GB), ($need / 1GB)) -Level VERBOSE
    if ($free -lt $need) { throw "Not enough free space on $drive - nothing changed." }
    if ($openTrees.Count) {
        Write-Log ('{0} open Install-TruTree install(s) belong to the current mods (they move with it to {1}); while the own tree is active do not run Install-TruTree -Restore / Invoke-TruTestRun -Undo - roll back first.' -f
            $openTrees.Count, (Split-Path -Leaf $stackDir)) -Level WARN
    }
    Write-Log "plan: copy the source to $(Split-Path -Leaf $incoming) ($($src.Count) files + $($carry.Count) carried over), rename mods -> $(Split-Path -Leaf $stackDir), $(Split-Path -Leaf $incoming) -> mods"
    if ($Check) { Write-Log 'Check only - nothing changed.'; return }
    if (!$PSCmdlet.ShouldProcess($GamePath, "switch mods to $Source (old mods -> $(Split-Path -Leaf $stackDir))")) { return }

    # copy + verify
    $i = 0
    foreach ($k in $src.Keys) {
        $i++
        $rel = $src[$k].FullName.Substring($Source.Length + 1)
        $dst = Join-Path $incoming $rel
        if (($i % 50) -eq 1) { Write-Progress -Activity 'Switch-TruModsTree' -Status "copy $i / $($src.Count)" -PercentComplete ([int](100 * $i / $src.Count)) }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
        Copy-Item -LiteralPath $src[$k].FullName -Destination $dst
        if ((Get-Md5 $dst) -ne $want[$k].Md5) { throw "Copied $rel does not match the manifest - the game's mods is unchanged; $incoming left for inspection." }
    }
    foreach ($f in $carry) {
        $rel = $f.FullName.Substring($mods.Length + 1)
        $dst = Join-Path $incoming $rel
        $m = Get-Md5 $f.FullName
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $dst
        if ((Get-Md5 $dst) -ne $m) { throw "Carried-over $rel is not identical - the game's mods is unchanged; $incoming left for inspection." }
        Write-Log "carried over $rel  $m" -Level VERBOSE
    }
    Write-Progress -Activity 'Switch-TruModsTree' -Completed
    $inStat = Get-TreeStat $incoming
    Write-Log ('copied and checked: {0} files, {1} bytes in {2}' -f $inStat.Files, $inStat.Bytes, (Split-Path -Leaf $incoming))

    # record first (state 'prepared'), then the two renames
    $recDir = Join-Path $RecordDir ('mods_switch_' + $stamp)
    New-Item -ItemType Directory -Force -Path $recDir | Out-Null
    $recFile = Join-Path $recDir 'switch.json'
    $rec = [pscustomobject]@{ time = $stamp; game = $GamePath; source = $Source; manifest = $Manifest; state = 'prepared';
                              stack_folder = (Split-Path -Leaf $stackDir); stack_files = $curStat.Files; stack_bytes = $curStat.Bytes;
                              own_files = $inStat.Files; own_bytes = $inStat.Bytes; carried_over = @($carry | ForEach-Object { $_.FullName.Substring($mods.Length + 1) });
                              open_tree_installs = @($openTrees | ForEach-Object { $_.Name }) }
    $rec | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recFile -Encoding UTF8
    Rename-Item -LiteralPath $mods -NewName (Split-Path -Leaf $stackDir)
    try { Rename-Item -LiteralPath $incoming -NewName 'mods' }
    catch {
        Write-Log "second rename failed ($($_.Exception.Message)) - putting the old mods back" -Level ERROR
        Rename-Item -LiteralPath $stackDir -NewName 'mods'
        $rec.state = 'failed'; $rec | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recFile -Encoding UTF8
        throw
    }
    $rec.state = 'switched'
    $rec | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recFile -Encoding UTF8
    Write-Log ('Switched: mods = {0} ({1} files); the old mods is {2} ({3} files, {4} bytes). Record {5}. Undo: Switch-TruModsTree.ps1 -Rollback' -f
        $Source, $inStat.Files, (Split-Path -Leaf $stackDir), $curStat.Files, $curStat.Bytes, $recDir)
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
