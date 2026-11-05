<#
.SYNOPSIS
    Raw Xbox 360 LIVE packages of the Tomb Raider: Underworld DLC: identify, verify and extract them into the
    input layout the installer and the pipeline read (input\xbox-dlc\<package name>\<files>).

.DESCRIPTION
    The purchased DLC sits on the console (hard drive / USB stick) under
    Content\<profile id or 0000000000000000>\534307EC\00000002\ as single files without extension, named
    <content id, 40 hex><2 hex> (42 characters). The content id is the SHA-1 of the package header.

    Expand-TruDlcPackage   identify (tools\stfs_extract.py identify: header, title id, content type, header SHA-1
                           against the header bytes and the file name, known-packages list) -> extract into
                           <Destination>\<Name>.tmp\ (every block checked against the package's hash tree) -> size +
                           MD5 of every file against the list -> rename to <Destination>\<Name>\. Supports -WhatIf.
                           -CheckOnly: identify + full hash-tree / block verification, writes nothing.
    Test-TruDlcInput       read-only: compares the extracted folders in input\xbox-dlc with the list (for the
                           installer and, later, the pipeline input check).
    Get-TruDlcPackageList  reads the known-packages list (scripts\windows\TruDlcPackages.json).

    Uses Write-Log of TruCommon.psm1 (import TruCommon first and set the log file with Set-TruLogFile; if no log
    file is set, Expand-TruDlcPackage starts its own in <workspace>\logs). Python: <workspace>\bin\venv python if
    present, else python from PATH; run isolated (-I), UTF-8, stdin closed.
#>

Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Verbose:$false

$script:StfsMagic = @('CON ', 'LIVE', 'PIRS')

function Get-TruDlcCallerPreference {
    # private: the caller's preference variables (same rule as in TruCommon.psm1, plus WhatIfPreference)
    param([Parameter(Mandatory)][System.Management.Automation.PSCmdlet]$Cmdlet)
    $values = @{}
    foreach ($name in 'VerbosePreference', 'DebugPreference', 'WarningPreference', 'ErrorActionPreference', 'WhatIfPreference') {
        $value = $Cmdlet.SessionState.PSVariable.GetValue($name)
        if ($null -ne $value) { $values[$name] = $value }
    }
    return $values
}

function Get-TruDlcDefaultPath {
    # private: repository / workspace paths seen from this module (scripts\windows)
    $paths = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
    return [pscustomobject]@{
        Repository = $paths.Repository
        Workspace  = $paths.Workspace
        Logs       = $paths.Logs
        List       = (Join-Path $PSScriptRoot 'TruDlcPackages.json')
        Live       = (Join-Path $paths.Workspace 'input\xbox-dlc-live')
        Dlc        = (Join-Path $paths.Workspace 'input\xbox-dlc')
        Tool       = (Join-Path $paths.Repository 'tools\stfs_extract.py')
    }
}

function Initialize-TruDlcLog {
    # private: when the caller has not set a log file (module used on its own), start one in LogDir
    param([string]$LogDir, [string]$Name)
    New-Item -ItemType Directory -Force -Path $LogDir -WhatIf:$false | Out-Null
    # the TruCommon instance whose Write-Log this module calls: has the caller set a log file?
    $trucommon = (Get-Command -Name Write-Log -CommandType Function).Module
    if (!(& $trucommon { $script:LogFile })) {
        Set-TruLogFile -Path (Join-Path $LogDir ('{0}_{1}.log' -f $Name, (Get-Date -Format 'yyyyMMdd_HHmmss')))
    }
}

function Get-TruStfsMagic {
    # private: first four bytes of a file as text ('' if shorter)
    param([string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $buffer = New-Object byte[] 4
        $read = $stream.Read($buffer, 0, 4)
        if ($read -lt 4) { return '' }
        return [System.Text.Encoding]::ASCII.GetString($buffer)
    } finally {
        $stream.Dispose()
    }
}

function Invoke-TruStfsTool {
    # private: runs tools\stfs_extract.py with the given arguments; every output line goes to the log (VERBOSE),
    # stderr lines as WARN. Returns the exit code. stdin is closed at once (the tool never reads it).
    param([string]$Python, [string]$Tool, [string[]]$Arguments)
    $all = @('-u', '-I', '-X', 'utf8', $Tool) + $Arguments
    $quoted = ($all | ForEach-Object { '"{0}"' -f ($_ -replace '"', '\"').TrimEnd('\') }) -join ' '
    Write-Log "$Python $quoted" -Level DEBUG
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Python
    $info.Arguments = $quoted
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $process.StandardInput.Close()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        while ($null -ne ($line = $process.StandardOutput.ReadLine())) {
            Write-Log "  $line" -Level VERBOSE
        }
        $process.WaitForExit()
        foreach ($line in ($stderrTask.Result -split "`r?`n")) {
            if ($line) { Write-Log "  stderr: $line" -Level WARN }
        }
        return $process.ExitCode
    } finally {
        $process.Dispose()
    }
}

function Get-TruDlcPackageList {
    <#
    .SYNOPSIS
        Reads the known-packages list (names, roles, files with size / md5 / sha1).
    .PARAMETER Path
        List file; default scripts\windows\TruDlcPackages.json next to this module.
    .EXAMPLE
        (Get-TruDlcPackageList).packages | Select-Object name, role
    #>
    [CmdletBinding()]
    param([string]$Path)
    foreach ($preference in (Get-TruDlcCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local -WhatIf:$false
    }
    if (!$Path) { $Path = (Get-TruDlcDefaultPath).List }
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Known-packages list not found: $Path" }
    $list = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if (!$list.packages) { throw "Known-packages list has no packages: $Path" }
    return $list
}

function Compare-TruDlcFolder {
    # private: one extracted folder against one list entry -> list of problems (empty = identical)
    param([string]$Folder, $Entry, [switch]$Quick)
    $problems = New-Object System.Collections.Generic.List[string]
    $seen = @{}
    foreach ($file in @($Entry.files)) {
        $path = Join-Path $Folder ($file.path -replace '/', '\')
        $seen[$file.path.ToLowerInvariant()] = $true
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { $problems.Add("missing file $($file.path)"); continue }
        $length = (Get-Item -LiteralPath $path).Length
        if ($length -ne [long]$file.size) { $problems.Add("$($file.path): size $length, expected $($file.size)"); continue }
        if (!$Quick) {
            $md5 = Get-Md5 $path
            Write-Log ('  {0,-20} {1,12}  {2}' -f $file.path, $length, $md5) -Level DEBUG
            if ($md5 -ne $file.md5) { $problems.Add("$($file.path): md5 $md5, expected $($file.md5)") }
        }
    }
    $root = (Get-Item -LiteralPath $Folder).FullName.TrimEnd('\')
    foreach ($item in @(Get-ChildItem -LiteralPath $Folder -Recurse -File)) {
        $relative = $item.FullName.Substring($root.Length + 1).Replace('\', '/')
        if (!$seen.ContainsKey($relative.ToLowerInvariant())) { $problems.Add("extra file $relative") }
    }
    return , $problems
}

function Test-TruDlcInput {
    <#
    .SYNOPSIS
        Read-only: compares the extracted DLC folders (input\xbox-dlc) with the known-packages list.
    .DESCRIPTION
        For every package of the list (or only the given roles): Status OK (every file present, size and MD5 as in
        the list, no extra files), Missing (no folder) or Different (Problems lists what differs). Folders and files
        in the input folder that the list does not know are returned with Status Unknown.
        Nothing is written; with -Quick only names and sizes are compared (no MD5).
    .PARAMETER Path
        The input folder; default <workspace>\input\xbox-dlc.
    .PARAMETER Role
        Only these roles, e.g. dlc1, dlc2.
    .PARAMETER PackageList
        Known-packages list; default scripts\windows\TruDlcPackages.json.
    .PARAMETER Quick
        Names and sizes only.
    .PARAMETER LogDir
        Log folder if the caller has not set a log file (Set-TruLogFile); default <workspace>\logs.
    .EXAMPLE
        Test-TruDlcInput -Role dlc1, dlc2 | Format-Table Name, Role, Status
    #>
    [CmdletBinding()]
    param(
        [string]$Path,
        [string[]]$Role,
        [string]$PackageList,
        [switch]$Quick,
        [string]$LogDir
    )
    foreach ($preference in (Get-TruDlcCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local -WhatIf:$false
    }
    $defaults = Get-TruDlcDefaultPath
    if (!$Path) { $Path = $defaults.Dlc }
    if (!$LogDir) { $LogDir = $defaults.Logs }
    Initialize-TruDlcLog -LogDir $LogDir -Name 'Test-TruDlcInput'
    $list = Get-TruDlcPackageList -Path $PackageList
    $known = @{}
    foreach ($entry in @($list.packages)) {
        $known[$entry.name.ToUpperInvariant()] = $true
        if ($Role -and ($Role -notcontains $entry.role)) { continue }
        $folder = Join-Path $Path $entry.name
        if (!(Test-Path -LiteralPath $folder -PathType Container)) {
            Write-Log "input $($entry.name) ($($entry.role)): missing" -Level VERBOSE
            [pscustomobject]@{ Name = $entry.name; Role = $entry.role; DisplayName = $entry.display_name; Status = 'Missing'; Problems = @() }
            continue
        }
        $problems = Compare-TruDlcFolder -Folder $folder -Entry $entry -Quick:$Quick
        $status = if ($problems.Count) { 'Different' } else { 'OK' }
        Write-Log "input $($entry.name) ($($entry.role)): $status $($problems -join '; ')" -Level VERBOSE
        [pscustomobject]@{ Name = $entry.name; Role = $entry.role; DisplayName = $entry.display_name; Status = $status; Problems = @($problems) }
    }
    if (!$Role -and (Test-Path -LiteralPath $Path -PathType Container)) {
        foreach ($item in @(Get-ChildItem -LiteralPath $Path)) {
            if ($known.ContainsKey($item.Name.ToUpperInvariant())) { continue }
            Write-Log "input $($item.Name): not in the known-packages list" -Level VERBOSE
            [pscustomobject]@{ Name = $item.Name; Role = $null; DisplayName = $null; Status = 'Unknown'; Problems = @('not in the known-packages list') }
        }
    }
}

function Expand-TruDlcPackage {
    <#
    .SYNOPSIS
        Verifies raw Xbox 360 LIVE packages of the DLC and extracts them into input\xbox-dlc\<package name>\.
    .DESCRIPTION
        For every package file (-Path, or every file in -Source = <workspace>\input\xbox-dlc-live):
          1. tools\stfs_extract.py identify: STFS magic LIVE, title id 534307EC, content type 2, header SHA-1 against
             the header bytes and the file name, truncation, file names / sizes against the known-packages list.
             Unknown, foreign or damaged packages are refused.
          2. Target <Destination>\<Name>\ already there: compared with the list (size + MD5); identical -> skipped,
             different -> error (an existing folder is never overwritten; move it away first).
          3. Extract into <Destination>\<Name>.tmp\ (every data block and the whole hash tree checked), then size +
             MD5 of every file on disk against the list, then rename to <Destination>\<Name>\. The extraction
             manifest (metadata, md5 / sha1 per file) goes to the log folder. On any error the .tmp folder is
             removed again.
        -CheckOnly runs identify + 'verify' (whole hash tree and every block) and the target comparison and writes
        nothing to the destination. -WhatIf shows what would be extracted (identify still runs; read-only).
        Returns one object per package: Package, Name, Role, DisplayName, Status (Extracted, AlreadyPresent,
        Checked, WhatIf, Skipped, Failed), TargetPresent, Target, Manifest, Message. Throws at the end if any
        package failed.
    .PARAMETER Path
        Raw package file(s).
    .PARAMETER Source
        Folder with raw package files (used when -Path is not given); default <workspace>\input\xbox-dlc-live.
        Files that are no STFS package (desktop.ini, notes, ...) are skipped with a warning.
    .PARAMETER Destination
        Folder of the extracted packages; default <workspace>\input\xbox-dlc.
    .PARAMETER PackageList
        Known-packages list; default scripts\windows\TruDlcPackages.json.
    .PARAMETER LogDir
        Folder for identify results and extraction manifests; default <workspace>\logs.
    .PARAMETER Python
        Python executable; default <workspace>\bin\venv\Scripts\python.exe if present, else python from PATH.
    .PARAMETER CheckOnly
        Identify + verify only; nothing is extracted.
    .EXAMPLE
        Expand-TruDlcPackage -WhatIf -Verbose
    .EXAMPLE
        Expand-TruDlcPackage -Path D:\Content\0000000000000000\534307EC\00000002\9CA70CF0EDA43654D158C2E37470D301DFA850E753 -CheckOnly
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [string[]]$Path,
        [string]$Source,
        [string]$Destination,
        [string]$PackageList,
        [string]$LogDir,
        [string]$Python,
        [switch]$CheckOnly
    )
    foreach ($preference in (Get-TruDlcCallerPreference -Cmdlet $PSCmdlet).GetEnumerator()) {
        Set-Variable -Name $preference.Key -Value $preference.Value -Scope Local -WhatIf:$false
    }
    $defaults = Get-TruDlcDefaultPath
    if (!$Source) { $Source = $defaults.Live }
    if (!$Destination) { $Destination = $defaults.Dlc }
    if (!$PackageList) { $PackageList = $defaults.List }
    if (!$LogDir) { $LogDir = $defaults.Logs }
    $Destination = [System.IO.Path]::GetFullPath($Destination)
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    Initialize-TruDlcLog -LogDir $LogDir -Name 'Expand-TruDlcPackage'
    if (!$Python) {
        $venv = Join-Path $defaults.Workspace 'bin\venv\Scripts\python.exe'
        $Python = if (Test-Path -LiteralPath $venv) { $venv } else { (Get-Command python -ErrorAction Stop).Source }
    }
    $list = Get-TruDlcPackageList -Path $PackageList
    Write-Log "Expand-TruDlcPackage: destination $Destination | list $PackageList | python $Python" -Level VERBOSE

    # package files
    $files = New-Object System.Collections.Generic.List[string]
    if ($Path) {
        foreach ($item in $Path) {
            if (!(Test-Path -LiteralPath $item -PathType Leaf)) { throw "Package file not found: $item" }
            $files.Add((Get-Item -LiteralPath $item).FullName)
        }
    } elseif (Test-Path -LiteralPath $Source -PathType Container) {
        foreach ($item in @(Get-ChildItem -LiteralPath $Source -File | Sort-Object Name)) {
            if ($script:StfsMagic -notcontains (Get-TruStfsMagic $item.FullName)) {
                Write-Log "skipped $($item.Name) in $Source (not an Xbox 360 package)" -Level WARN
                continue
            }
            $files.Add($item.FullName)
        }
    }
    if (!$files.Count) {
        Write-Log "No raw package files (folder $Source)." -Level VERBOSE
        return
    }

    $failed = 0
    foreach ($file in $files) {
        $leaf = Split-Path -Leaf $file
        $result = [pscustomobject]@{ Package = $file; Name = $null; Role = $null; DisplayName = $null; Status = 'Failed';
                                     TargetPresent = $false; Target = $null; Manifest = $null; Message = '' }
        $tmp = $null
        try {
            Write-Log "Package $file ($((Get-Item -LiteralPath $file).Length) bytes)"
            # 1. identify (header, name, list)
            $identifyJson = Join-Path $LogDir "Expand-TruDlcPackage_${stamp}_$leaf.identify.json"
            $code = Invoke-TruStfsTool -Python $Python -Tool $defaults.Tool -Arguments @('identify', $file, '--known', $PackageList, '--json', $identifyJson)
            $identify = if (Test-Path -LiteralPath $identifyJson) { Get-Content -LiteralPath $identifyJson -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
            if ($code -ne 0 -or !$identify -or !$identify.known) {
                $why = if ($identify) { @($identify.problems) -join '; ' } else { "identify exit code $code" }
                throw "refused ($(@{1 = 'damaged or foreign package'; 3 = 'not a known package'}[[int]$code])): $why"
            }
            $entry = @($list.packages | Where-Object { $_.name -eq $identify.name })[0]
            $result.Name = $entry.name; $result.Role = $entry.role; $result.DisplayName = $entry.display_name
            $target = Join-Path $Destination $entry.name
            $result.Target = $target
            Write-Log "identified: $($entry.name) = $($entry.display_name) ($($entry.role)), header SHA-1 $($identify.header_sha1)"

            # 2. target already there?
            if (Test-Path -LiteralPath $target) {
                $result.TargetPresent = $true
                $problems = Compare-TruDlcFolder -Folder $target -Entry $entry
                if ($problems.Count) {
                    throw "target $target exists and differs from the list ($($problems -join '; ')); it is never overwritten - move it away first"
                }
                if (!$CheckOnly) {
                    $result.Status = 'AlreadyPresent'; $result.Message = 'target identical to the list (size + MD5)'
                    Write-Log "$($entry.name): already extracted and identical (size + MD5) - skipped"
                    continue
                }
            }

            # 3a. check only: whole hash tree + every block
            if ($CheckOnly) {
                Write-Log "verify $leaf (whole hash tree and every data block) ..." -Level VERBOSE
                $code = Invoke-TruStfsTool -Python $Python -Tool $defaults.Tool -Arguments @('verify', $file)
                if ($code -ne 0) { throw "verify failed (exit code $code): hash mismatch in the package" }
                $result.Status = 'Checked'
                $result.Message = if ($result.TargetPresent) { 'package OK; target identical' } else { 'package OK; not extracted yet' }
                Write-Log "$($entry.name): package OK ($($result.Message))"
                continue
            }

            # 3b. extract
            $need = [long](@($entry.files) | Measure-Object -Property size -Sum).Sum
            if (!$PSCmdlet.ShouldProcess($target, "Extract package $leaf ($([math]::Round($need / 1MB)) MB, $(@($entry.files).Count) files)")) {
                $result.Status = 'WhatIf'; $result.Message = 'would extract'
                continue
            }
            $drive = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($Destination))
            if ($drive.AvailableFreeSpace -lt ($need + 256MB)) {
                throw "not enough free space on $($drive.Name): $([math]::Round($drive.AvailableFreeSpace / 1MB)) MB free, $([math]::Round($need / 1MB)) MB needed"
            }
            New-Item -ItemType Directory -Force -Path $Destination | Out-Null
            $tmp = Join-Path $Destination "$($entry.name).tmp"
            foreach ($leftover in @($tmp, "$tmp.manifest.json")) {
                if (Test-Path -LiteralPath $leftover) {
                    Write-Log "removing leftover $leftover of an earlier run" -Level WARN
                    Remove-Item -LiteralPath $leftover -Recurse -Force
                }
            }
            Write-Log "extracting into $tmp ..." -Level VERBOSE
            $code = Invoke-TruStfsTool -Python $Python -Tool $defaults.Tool -Arguments @('extract', $file, $tmp)
            if ($code -ne 0) { throw "extract failed (exit code $code): hash mismatch or short file" }
            $manifestPath = "$tmp.manifest.json"
            $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($manifest.meta.header_sha1 -ne $entry.content_id) { throw "manifest header SHA-1 $($manifest.meta.header_sha1) is not $($entry.content_id)" }
            $problems = Compare-TruDlcFolder -Folder $tmp -Entry $entry
            if ($problems.Count) { throw "extracted files differ from the list: $($problems -join '; ')" }
            $result.Manifest = Join-Path $LogDir "Expand-TruDlcPackage_${stamp}_$($entry.name).manifest.json"
            Move-Item -LiteralPath $manifestPath -Destination $result.Manifest -Force
            Rename-Item -LiteralPath $tmp -NewName $entry.name
            $tmp = $null
            $result.Status = 'Extracted'; $result.TargetPresent = $true
            $result.Message = "$(@($entry.files).Count) files, size + MD5 as in the list"
            Write-Log "$($entry.name): extracted into $target ($($result.Message)); manifest $($result.Manifest)"
        }
        catch {
            $failed++
            $result.Status = 'Failed'; $result.Message = $_.Exception.Message
            Write-Log "$leaf FAILED: $($_.Exception.Message)" -Level ERROR
            if ($tmp) {
                foreach ($leftover in @($tmp, "$tmp.manifest.json")) {
                    if (Test-Path -LiteralPath $leftover) {
                        Remove-Item -LiteralPath $leftover -Recurse -Force -ErrorAction Continue -WhatIf:$false
                        Write-Log "removed $leftover" -Level VERBOSE
                    }
                }
            }
        }
        finally {
            $result
        }
    }
    if ($failed) { throw "$failed of $($files.Count) package(s) failed - see the log." }
}

Export-ModuleMember -Function Expand-TruDlcPackage, Test-TruDlcInput, Get-TruDlcPackageList
