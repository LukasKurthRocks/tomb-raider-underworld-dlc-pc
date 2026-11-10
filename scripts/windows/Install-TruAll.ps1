<#
.SYNOPSIS
    One-click install for players (started by Install.bat): fetches what is missing from the official sources
    (pinned versions, SHA-256 checked), skips what is already there, then installs the DLC port (the original's B270
    kit), the fork's DLC 2 plugins and the display settings.

.DESCRIPTION
    The player needs only the Steam copy of the game and their own Xbox 360 DLC folders in <workspace>\input\xbox-dlc\
    (or the raw package files from the console in <workspace>\input\xbox-dlc-live\). <workspace> is the folder that
    holds the repository folder (see scripts\windows\README.md, Workspace). Steps, in this order (each one skips
    itself when its result is already there):

      1. game folder (Steam libraries) and game closed
      2. DLC inputs: folders 9CA70CF0... (pack10.000, DLC 1) and 600A1264... (pack11.000, DLC 2), or raw packages
      3. Python 3.9+ (only detected; never installed silently - without it the script stops with the python.org link)
      4. ModLoader v1.2 (TombRaiderModding release) -> input\ModLoader-v1.2.zip, unpacked to staging\ModLoader-v1.2
      5. the original's B270 release: trudlcport-kit-B270.zip, install_dlc.py, tex_convert.py, credits_convert.py
         -> release\B270\ (kit unpacked to release\B270\kit)
      6. venv bin\venv-install with bsdiff4 + numpy (pip, PyPI)
      7. RAD Video Tools: only detected (radvideo64.exe in the usual folders or RAD_VIDEO_TOOLS); without it the
         credits movies are skipped with a note. ffmpeg 9.0.2 through Get-Tools.ps1 -Name 'ffmpeg*' (only for the credits)
      8. Steamless v3.1.0.5 on tru.exe (or tru.exe.steam_original) when no Steamless-unpacked exe is there
      9. Install-TruDlc.ps1 -Build B270: raw packages first, dry run (install_dlc.py --check), and only after
         "All inputs OK" the install, with --credits when RAD Video Tools was found. Skipped when the game's install
         record already says B270 (and has the credits, or they are not wanted)
     10. fork plugins: from a pinned fork release (trudlcport-fork-plugins-<version>.zip - none yet, the entry is
         disabled until $forkPlugins.Version is set), else built with Build-TruAsi.ps1 when the Visual Studio x86
         build tools are found, else skipped with a note. DLC 2 set: TruShadowPower, TruShadowCombat, TruRockVein,
         TruDoppelganger, TruDlc2Player; TruMenu (shipped INI = quick bar only) unless -NoMenu; TruQoL with -QoL
     11. Set-TruDisplay.ps1 -FullscreenEffects On -DepthOfField On (exports the registry key to backup\ first)
     12. summary: what was skipped, the 60 fps note

    Every download goes to "<target>.part" first and is renamed only after its SHA-256 matched; a mismatch stops the
    run (the rejected file is kept as "<target>.sha256-mismatch"). An existing file with a wrong SHA-256 is never
    overwritten: the run stops and says which file it is. Items without a pinned SHA-256 are never downloaded.

    Where the SHA-256 values come from:
      B270 files    GitHub release v-B270 of andrearicci93/trudlcport, asset digests (sha256) - the same values as
                    the SHA256SUMS.txt of the owner's download of 2026-11-05
      ModLoader     computed from the owner's ModLoader.zip of release v1.2 (1 313 604 bytes = the release asset);
                    GitHub shows no digest for that 2024 release
      Steamless     not pinned yet (no digest on GitHub, no verified copy): the script does not download it and asks
                    to run Steamless by hand, or to unzip it into <workspace>\bin\steamless-3.1.0.5 (then the script
                    runs it and checks the MD5 of tru.exe.unpacked.exe) - see $steamless below
      ffmpeg        Get-Tools.ps1 (gyan.dev release 9.0.2)

    -Check lists everything it would download (URL, target, SHA-256) or do, checks the files that are already there
    and changes nothing: no download, no unpacking, no venv, no Steamless, no install_dlc.py, no plugin build, no
    registry. Every run writes <workspace>\logs\Install-TruAll_<time>.log; the scripts it calls write their own logs.
    -Verbose shows each step, -Debug adds paths, hashes and command lines, -Trace adds a PowerShell line trace.

.PARAMETER Check
    Dry run: list and check only, change nothing.
.PARAMETER NoDownload
    Download nothing (also no pip install); a missing item stops the run (or, for the credits, skips them).
.PARAMETER NoPlugins
    Do not install the fork's plugins.
.PARAMETER NoCredits
    Do not build the credits movies (a DLC then ends on a black screen after its last cutscene).
.PARAMETER NoMenu
    Leave TruMenu out (default: installed, quick bar only).
.PARAMETER QoL
    Also install TruQoL (60 fps cap, field of view, start-up fix for PCs with more than 31 CPU threads).
.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.
.EXAMPLE
    .\scripts\windows\Install-TruAll.ps1 -Check
.EXAMPLE
    .\scripts\windows\Install-TruAll.ps1 -NoPlugins -Verbose
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoDownload,
    [switch]$NoPlugins,
    [switch]$NoCredits,
    [switch]$NoMenu,
    [switch]$QoL,
    [string]$GamePath,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Find-TruGamePath, Get-Md5, Get-TruWorkspacePath
$commonModule = Join-Path $PSScriptRoot 'TruCommon.psm1'
Import-Module $commonModule -Force -Verbose:$false
# Test-TruDlcInput (read-only check of input\xbox-dlc)
Import-Module (Join-Path $PSScriptRoot 'TruDlcPackage.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths     = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$root      = $paths.Workspace
$repo      = $paths.Repository
$logDir    = $paths.Logs
$binDir    = Join-Path $root 'bin'
$dlDir     = Join-Path $binDir '_download'
$Build     = 'B270'
$release   = Join-Path $root "release\$Build"
$kitDir    = Join-Path $release 'kit'
$dlcDir    = Join-Path $root 'input\xbox-dlc'
$liveDir   = Join-Path $root 'input\xbox-dlc-live'
$loaderDir = Join-Path $root 'staging\ModLoader-v1.2'
$venvDir   = Join-Path $binDir 'venv-install'
$venvPy    = Join-Path $venvDir 'Scripts\python.exe'
$ffmpegExe = Join-Path $binDir 'ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe'
$asiOut    = Join-Path $repo 'work\asi\install'

$md5SteamExe    = 'b36da327a320eab8b5c8464b27685840'   # tru.exe v1.1 (Steam)
$md5UnpackedExe = '56d1ce2dffa62f16354063da2df44d5a'   # the same exe after Steamless (docs/INSTALL.md; kit manifest exe.source)

# ---- pinned downloads ------------------------------------------------------------------------------------------
$b270Url = 'https://github.com/andrearicci93/trudlcport/releases/download/v-B270'
$b270Source = 'GitHub release v-B270 asset digest, = SHA256SUMS.txt of the owner''s download 2026-11-05'
$modLoader = @{
    Name = 'ModLoader v1.2'; Url = 'https://github.com/TombRaiderModding/ModLoader/releases/download/v1.2/ModLoader.zip'
    Target = (Join-Path $root 'input\ModLoader-v1.2.zip')
    Sha256 = 'a97c23fb0d13ba7fcaea0c92ce9396e8d6579bce9d22f314b07dcfc55fce521b'
    Source = 'computed from the owner''s ModLoader.zip of release v1.2 (1313604 bytes = the release asset)'
}
$kitFiles = @(
    @{ Name = 'B270 kit'; File = 'trudlcport-kit-B270.zip'; Sha256 = '619b7cd0c6a4f8bddbbcd53c429e47e17e2116022d0cdd66ad3656fc337188f0' },
    @{ Name = 'B270 install_dlc.py'; File = 'install_dlc.py'; Sha256 = '8233c3afaea2aa5b951f3410c3d63fccaa172dfba9d76d275781a16b55b5dd70' },
    @{ Name = 'B270 tex_convert.py'; File = 'tex_convert.py'; Sha256 = '053338dbd5b6b1af70ab36b0597374756e766fcbfce9e123f35fe72e2aff6d53' },
    @{ Name = 'B270 credits_convert.py'; File = 'credits_convert.py'; Sha256 = '4b56ae4ec6da1f9722cc782eba97253774cfbad133b23460853eb222adc346bc' }
) | ForEach-Object { @{ Name = $_.Name; Url = "$b270Url/$($_.File)"; Target = (Join-Path $release $_.File); Sha256 = $_.Sha256; Source = $b270Source } }
# Steamless: tested with the March 2024 release v3.1.0.5 (docs/INSTALL.md). Its SHA-256 is not pinned yet - GitHub
# shows no digest for it and no verified copy was at hand on 2026-11-10. Until Sha256 is set it is never downloaded.
$steamless = @{
    Name = 'Steamless v3.1.0.5'; Url = 'https://github.com/atom0s/Steamless/releases/download/v3.1.0.5/Steamless.v3.1.0.5.-.by.atom0s.zip'
    Target = (Join-Path $dlDir 'Steamless.v3.1.0.5.-.by.atom0s.zip'); Sha256 = ''; Source = 'not pinned yet'
    Folder = (Join-Path $binDir 'steamless-3.1.0.5')
    Manual = 'Run Steamless (https://github.com/atom0s/Steamless/releases, v3.1.0.5, default options) once on {0}; it writes {0}.unpacked.exe. Or unzip that Steamless release into {1}: the installer then runs it and checks the MD5 of what it writes. Then start Install.bat again.'
}
# Prebuilt plugins from a release of this fork: none yet. Set Version, Url and Sha256 of the release asset
# trudlcport-fork-plugins-<version>.zip to enable it (flat zip: <Plugin>.asi + .ini + the TruMenu text files).
$forkPlugins = @{ Version = ''; Url = ''; Sha256 = '' }

# ---- plugins ----------------------------------------------------------------------------------------------------
$plugins = @('TruShadowPower', 'TruShadowCombat', 'TruRockVein', 'TruDoppelganger', 'TruDlc2Player')
if (!$NoMenu) { $plugins += 'TruMenu' }
if ($QoL) { $plugins += 'TruQoL' }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Install-TruAll_{0}_{1}.log' -f $stamp, $(if ($Check) { 'Check' } else { 'Install' }))
Set-TruLogFile -Path $logFile

$script:Notes = New-Object System.Collections.Generic.List[string]
$script:Problems = New-Object System.Collections.Generic.List[string]
$script:FetchCount = 0

function Stop-Install {
    # a blocking problem: the real run stops here; -Check collects it and goes on listing
    param([string]$Message)
    if ($Check) {
        $script:Problems.Add($Message)
        Write-Log "[stop]  $Message" -Level ERROR
    } else {
        throw $Message
    }
}

function Add-Note {
    # something skipped or left to the player: printed again in the summary
    param([string]$Message)
    $script:Notes.Add($Message)
    Write-Log "[note]  $Message"
}

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

function Invoke-Native {
    # runs an external program, every output line to the log (VERBOSE), returns the exit code
    param([string]$Exe, [string[]]$Arguments)
    Write-Log ('"{0}" {1}' -f $Exe, (($Arguments | ForEach-Object { '"{0}"' -f $_ }) -join ' ')) -Level DEBUG
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object {
            $text = if ($_ -is [System.Management.Automation.ErrorRecord]) { 'stderr: ' + $_.Exception.Message } else { [string]$_ }
            Write-Log $text -Level VERBOSE
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    Write-Log "exit code $code" -Level DEBUG
    return $code
}

function Invoke-TruScript {
    # runs one of the scripts next to this one in this session (its output stays visible); they set their own log
    # file and re-import TruCommon, so ours is set again afterwards
    param([string]$Name, [hashtable]$Arguments)
    $text = ($Arguments.GetEnumerator() | Sort-Object Key | ForEach-Object {
        if ($_.Value -is [switch] -or $_.Value -is [bool]) { "-$($_.Key)" } else { "-$($_.Key) '$($_.Value -join ',')'" } }) -join ' '
    Write-Log "> $Name $text" -Level VERBOSE
    try {
        & (Join-Path $PSScriptRoot $Name) @Arguments | Out-Host
    }
    finally {
        Import-Module $commonModule -Force -Verbose:$false
        Set-TruLogFile -Path $logFile
    }
}

function Get-PinnedFile {
    <#
    Present + SHA-256 ok -> skip; missing -> download (unless -Check / -NoDownload) and verify.
    Returns 'ok' (there and verified), 'planned' (-Check: would be downloaded) or 'missing'.
    #>
    param([hashtable]$Item)
    $target = $Item.Target
    Write-Log "$($Item.Name): url=$($Item.Url) target=$target sha256=$($Item.Sha256) ($($Item.Source))" -Level DEBUG
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $hash = Get-Sha256 $target
        Write-Log "$($Item.Name): sha256 now $hash" -Level DEBUG
        if (!$Item.Sha256) {
            Write-Log "[have]  $($Item.Name): $target (sha256 $hash, no pinned value to compare)" -Level WARN
            return 'ok'
        }
        if ($hash -eq $Item.Sha256) {
            Write-Log "[skip]  $($Item.Name): already there, SHA-256 ok - $target"
            return 'ok'
        }
        Stop-Install ('{0}: {1} is there but its SHA-256 is {2}, expected {3} ({4}). It is damaged or another version: move it away (or put the right file there) and start again.' -f $Item.Name, $target, $hash, $Item.Sha256, $Item.Source)
        return 'missing'
    }
    if (!$Item.Sha256) {
        Write-Log "[skip]  $($Item.Name): no SHA-256 pinned - not downloaded ($($Item.Url))" -Level WARN
        return 'missing'
    }
    if ($Check) {
        $script:FetchCount++
        Write-Log "[fetch] $($Item.Name): $($Item.Url)"
        Write-Log "          -> $target"
        Write-Log "          sha256 $($Item.Sha256) ($($Item.Source))"
        return 'planned'
    }
    if ($NoDownload) {
        Stop-Install "$($Item.Name) is missing ($target) and -NoDownload is set. Download $($Item.Url) yourself, put it there and start again."
        return 'missing'
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    $part = "$target.part"
    Write-Log "[fetch] $($Item.Name): $($Item.Url) -> $target"
    # curl.exe ships with Windows 10 1803+; the progress bar goes straight to the console
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & curl.exe -L --fail --retry 2 --progress-bar -o $part $Item.Url
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) { throw "Download of $($Item.Url) failed (curl exit code $code). Check the internet connection and start again." }
    $hash = Get-Sha256 $part
    Write-Log "$($Item.Name): downloaded $((Get-Item -LiteralPath $part).Length) bytes, sha256 $hash" -Level DEBUG
    if ($hash -ne $Item.Sha256) {
        $rejected = "$target.sha256-mismatch"
        Move-Item -LiteralPath $part -Destination $rejected -Force
        throw ('{0}: the download has SHA-256 {1}, expected {2} ({3}). Not used; kept as {4}. Stopped.' -f $Item.Name, $hash, $Item.Sha256, $Item.Source, $rejected)
    }
    Move-Item -LiteralPath $part -Destination $target
    Write-Log "[ok]    $($Item.Name): SHA-256 ok - $target"
    return 'ok'
}

function Expand-TruZip {
    <#
    Unpacks a verified zip into Destination (via Destination.tmp_<time>, renamed at the end). Inner = the top folder in
    the zip that becomes Destination ('' = the zip root). Returns $true when Destination is there afterwards.
    #>
    param([string]$Name, [string]$Zip, [string]$Destination, [string]$Inner, [string]$ZipState)
    if (Test-Path -LiteralPath $Destination -PathType Container) {
        Write-Log "[skip]  $Name already unpacked: $Destination"
        return $true
    }
    if ($Check) {
        if ($ZipState -ne 'missing') { Write-Log "[do]    unpack $Name -> $Destination" }
        return $false
    }
    if ($ZipState -ne 'ok') { return $false }
    $tmp = '{0}.tmp_{1}' -f $Destination, $stamp
    Write-Log "Unpacking $Zip -> $tmp ..." -Level VERBOSE
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($Zip, $tmp)
    $from = if ($Inner) { Join-Path $tmp $Inner } else { $tmp }
    if (!(Test-Path -LiteralPath $from -PathType Container)) { throw "$Name`: folder $Inner not found in $Zip (left in $tmp)." }
    Move-Item -LiteralPath $from -Destination $Destination
    if ($Inner -and !@(Get-ChildItem -LiteralPath $tmp -Force).Count) { Remove-Item -LiteralPath $tmp }
    $count = @(Get-ChildItem -LiteralPath $Destination -Recurse -File).Count
    Write-Log "[ok]    $Name unpacked: $Destination ($count files)"
    return $true
}

function Find-SystemPython {
    # Python 3.9+ without running anything: PEP 514 registry entries, then python.exe on PATH (not the Store alias)
    $found = New-Object System.Collections.Generic.List[object]
    foreach ($hive in 'HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore') {
        foreach ($key in @(Get-ChildItem -LiteralPath $hive -ErrorAction SilentlyContinue)) {
            if ($key.PSChildName -notmatch '^(\d+)\.(\d+)(-32|-64)?$') { continue }
            $version = [version]('{0}.{1}' -f $Matches[1], $Matches[2])
            $bits = if ($Matches[3] -eq '-32' -or $hive -like '*WOW6432Node*') { 32 } else { 64 }
            $install = Get-ItemProperty -LiteralPath (Join-Path $key.PSPath 'InstallPath') -ErrorAction SilentlyContinue
            if (!$install) { continue }
            $exe = if ($install.ExecutablePath) { $install.ExecutablePath } elseif ($install.'(default)') { Join-Path $install.'(default)' 'python.exe' } else { '' }
            if (!$exe -or !(Test-Path -LiteralPath $exe -PathType Leaf)) { continue }
            Write-Log "Python candidate (registry $($key.PSChildName)): $exe" -Level DEBUG
            $found.Add([pscustomobject]@{ Path = $exe; Version = $version; Bits = $bits })
        }
    }
    foreach ($cmd in @(Get-Command python.exe -All -CommandType Application -ErrorAction SilentlyContinue)) {
        if ($cmd.Source -like '*\WindowsApps\*') { continue }
        $product = (Get-Item -LiteralPath $cmd.Source).VersionInfo.ProductVersion
        if ($product -notmatch '^(\d+)\.(\d+)') { continue }
        Write-Log "Python candidate (PATH, $product): $($cmd.Source)" -Level DEBUG
        $found.Add([pscustomobject]@{ Path = $cmd.Source; Version = [version]('{0}.{1}' -f $Matches[1], $Matches[2]); Bits = 64 })
    }
    @($found | Where-Object { $_.Version -ge [version]'3.9' } |
        Sort-Object @{ Expression = { $_.Bits }; Descending = $true }, @{ Expression = { $_.Version }; Descending = $true }) | Select-Object -First 1
}

function Test-VenvPackage {
    # bsdiff4 and numpy in the installer venv (folder check, nothing is run)
    $site = Join-Path $venvDir 'Lib\site-packages'
    @('bsdiff4', 'numpy' | Where-Object { !(Test-Path -LiteralPath (Join-Path $site $_) -PathType Container) })
}

function Find-RadVideo {
    # the same places credits_convert.py searches
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:RAD_VIDEO_TOOLS) {
        $candidates.Add($env:RAD_VIDEO_TOOLS)
        $candidates.Add((Join-Path $env:RAD_VIDEO_TOOLS 'radvideo64.exe'))
    }
    # program folders and the per-user local folder (the scanner of Test-TruUploadReady flags the env var name)
    $localData = [Environment]::GetFolderPath('LocalApplicationData')
    foreach ($base in @(${env:ProgramFiles}, ${env:ProgramFiles(x86)}, $localData) | Where-Object { $_ }) {
        foreach ($sub in 'RADVideo', 'RAD Video Tools', 'RAD Game Tools\RAD Video Tools', 'RAD Game Tools', 'Epic Games Tools\RAD Video Tools', 'Bink') {
            $candidates.Add((Join-Path (Join-Path $base $sub) 'radvideo64.exe'))
        }
    }
    foreach ($c in $candidates) {
        Write-Log "RAD candidate: $c" -Level DEBUG
        if ((Test-Path -LiteralPath $c -PathType Leaf) -and $c -like '*.exe') { return $c }
    }
    return $null
}

function Find-VisualStudio {
    # Visual Studio / Build Tools with the x86 compiler (vcvarsall.bat + Hostx64\x86\cl.exe); the tested 2022
    # Community first (Build-TruAsi.ps1's default), then any other edition
    $found = New-Object System.Collections.Generic.List[string]
    foreach ($base in @(${env:ProgramFiles}, ${env:ProgramFiles(x86)}) | Where-Object { $_ }) {
        $vsRoot = Join-Path $base 'Microsoft Visual Studio'
        foreach ($year in @(Get-ChildItem -LiteralPath $vsRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
            foreach ($edition in @(Get-ChildItem -LiteralPath $year.FullName -Directory -ErrorAction SilentlyContinue)) {
                $vcvars = Join-Path $edition.FullName 'VC\Auxiliary\Build\vcvarsall.bat'
                $msvc = Join-Path $edition.FullName 'VC\Tools\MSVC'
                $cl = @(Get-ChildItem -LiteralPath $msvc -Directory -ErrorAction SilentlyContinue |
                    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\Hostx64\x86\cl.exe') -PathType Leaf })
                Write-Log "Visual Studio candidate: $($edition.FullName) vcvarsall=$(Test-Path -LiteralPath $vcvars) x86 cl=$($cl.Count)" -Level DEBUG
                if ((Test-Path -LiteralPath $vcvars -PathType Leaf) -and $cl.Count) { $found.Add($edition.FullName) }
            }
        }
    }
    $tested = @($found | Where-Object { $_ -like '*\2022\Community' })
    if ($tested.Count) { return $tested[0] }
    if ($found.Count) { return $found[0] }
    return $null
}

function Get-KitManifest {
    # manifest.json of the kit: from the unpacked kit, else read straight out of the verified zip (nothing written)
    $file = Join-Path $kitDir 'manifest.json'
    if (Test-Path -LiteralPath $file -PathType Leaf) { return (Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json) }
    $zip = Join-Path $release 'trudlcport-kit-B270.zip'
    if (!(Test-Path -LiteralPath $zip -PathType Leaf)) { return $null }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
    try {
        $entry = $archive.GetEntry('kit/manifest.json')
        if (!$entry) { return $null }
        $reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
    } finally {
        $archive.Dispose()
    }
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Install-TruAll build=$Build check=$([bool]$Check) noDownload=$([bool]$NoDownload) noPlugins=$([bool]$NoPlugins) noCredits=$([bool]$NoCredits) plugins=$($plugins -join ',') log=$logFile" -Level VERBOSE
    Write-Log "PowerShell $($PSVersionTable.PSVersion) on $([Environment]::OSVersion.VersionString); workspace $root" -Level DEBUG
    if ($Check) { Write-Log 'Check only: nothing is downloaded, unpacked, installed or changed.' }

    # ---- 1. game folder ------------------------------------------------------------------------------------------
    Write-Log '== 1. Game'
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe') -PathType Leaf)) {
        throw 'Tomb Raider: Underworld (Steam) not found. Install it with Steam and start it once, or pass -GamePath "<game folder>".'
    }
    Write-Log "[ok]    game folder: $GamePath"
    $running = Get-Process -Name 'tru' -ErrorAction SilentlyContinue
    if ($running) { Stop-Install "The game is running (tru.exe, PID $($running.Id -join ', ')). Close it first." }
    $exeMd5 = Get-Md5 (Join-Path $GamePath 'tru.exe')
    $exeState = if ($exeMd5 -eq $md5SteamExe) { 'the Steam v1.1 original' } else { 'not the Steam original (patched by an earlier install?)' }
    Write-Log "[ok]    tru.exe MD5 $exeMd5 - $exeState"
    $record = $null
    $recordFile = Join-Path $GamePath 'trudlcport_install.json'
    if (Test-Path -LiteralPath $recordFile -PathType Leaf) {
        try { $record = Get-Content -LiteralPath $recordFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { Write-Log "install record unreadable: $($_.Exception.Message)" -Level WARN }
    }
    if ($record) { Write-Log "[ok]    installed build (trudlcport_install.json): $($record.build), credits: $(@($record.credits).Count)" }
    else { Write-Log '[ok]    no install record of the B269+ installer in the game folder' }

    # ---- 2. the player's DLC files -------------------------------------------------------------------------------
    Write-Log '== 2. Your Xbox 360 DLC files'
    $rawCount = if (Test-Path -LiteralPath $liveDir -PathType Container) { @(Get-ChildItem -LiteralPath $liveDir -File).Count } else { 0 }
    $inputs = @(Test-TruDlcInput -Path $dlcDir -Role dlc1, dlc2 -Quick)
    foreach ($in in $inputs) {
        $label = '{0} {1}' -f $in.DisplayName, $in.Name
        switch ($in.Status) {
            'OK'        { Write-Log "[ok]    $label - $(Join-Path $dlcDir $in.Name)" }
            'Different' { Write-Log "[warn]  $label differs from the known list: $($in.Problems -join '; ') (the dry run checks the MD5s)" -Level WARN }
            default     { Write-Log "[miss]  $label - not in $dlcDir" -Level VERBOSE }
        }
    }
    $missingRoles = @($inputs | Where-Object { $_.Status -eq 'Missing' } | ForEach-Object { $_.Role })
    if ($missingRoles.Count) {
        # also accepted: the packs somewhere deeper below input\xbox-dlc (install_dlc.py searches --dlc recursively)
        $deep = @{}
        if (Test-Path -LiteralPath $dlcDir -PathType Container) {
            foreach ($pack in @(Get-ChildItem -LiteralPath $dlcDir -Recurse -File -Include 'pack10.000', 'pack11.000' -ErrorAction SilentlyContinue)) {
                $deep[$pack.Name] = $pack.FullName
            }
        }
        $absent = @()
        foreach ($role in $missingRoles) {
            $pack = if ($role -eq 'dlc1') { 'pack10.000' } else { 'pack11.000' }
            if ($deep.ContainsKey($pack)) { Write-Log "[ok]    $pack found deeper below input\xbox-dlc: $($deep[$pack])"; continue }
            if ($rawCount) { Write-Log "[ok]    $pack not extracted yet: $rawCount raw package file(s) in $liveDir - Install-TruDlc.ps1 verifies and extracts them"; continue }
            $absent += $pack
        }
        if ($absent.Count) {
            Stop-Install ("Your Xbox DLC files are missing ($($absent -join ', ')). Copy the DLC folders from your Xbox 360 " +
                "(Content\<profile>\534307EC\00000002\): 9CA70CF0EDA43654D158C2E37470D301DFA850E753 (Beneath the Ashes) and " +
                "600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153 (Lara's Shadow) into $dlcDir\ - or the raw package files " +
                "(one file each, same names) into $liveDir\ - and start Install.bat again.")
        }
    }

    # ---- 3. Python -----------------------------------------------------------------------------------------------
    Write-Log '== 3. Python'
    $venvMissing = @(Test-VenvPackage)
    $venvReady = (Test-Path -LiteralPath $venvPy -PathType Leaf) -and !$venvMissing.Count
    $systemPython = $null
    if ($venvReady) {
        Write-Log "[skip]  installer venv ready (bsdiff4 + numpy): $venvDir"
    } else {
        $systemPython = Find-SystemPython
        if ($systemPython) { Write-Log "[ok]    Python $($systemPython.Version) ($($systemPython.Bits)-bit): $($systemPython.Path)" }
        else { Stop-Install 'Python 3.9 or newer was not found. Install it from https://www.python.org/ (tick "Add python.exe to PATH"), then start Install.bat again.' }
    }

    # ---- 4. ModLoader --------------------------------------------------------------------------------------------
    Write-Log '== 4. ModLoader'
    if ((Test-Path -LiteralPath (Join-Path $loaderDir 'ModLoader.asi')) -and (Test-Path -LiteralPath (Join-Path $loaderDir 'binkw32.dll'))) {
        Write-Log "[skip]  ModLoader already unpacked: $loaderDir"
    } else {
        $state = Get-PinnedFile $modLoader
        [void](Expand-TruZip -Name 'ModLoader v1.2' -Zip $modLoader.Target -Destination $loaderDir -Inner '' -ZipState $state)
    }

    # ---- 5. the original's B270 release --------------------------------------------------------------------------
    Write-Log '== 5. The original''s B270 release (kit + installer scripts)'
    $kitState = 'ok'
    foreach ($item in $kitFiles) {
        $state = Get-PinnedFile $item
        if ($item.Name -eq 'B270 kit') { $kitState = $state }
    }
    if (Test-Path -LiteralPath (Join-Path $kitDir 'manifest.json') -PathType Leaf) {
        Write-Log "[skip]  kit already unpacked: $kitDir"
    } elseif (Test-Path -LiteralPath $kitDir) {
        Stop-Install "$kitDir exists but has no manifest.json. Move that folder away and start again."
    } else {
        [void](Expand-TruZip -Name 'B270 kit' -Zip (Join-Path $release 'trudlcport-kit-B270.zip') -Destination $kitDir -Inner 'kit' -ZipState $kitState)
    }
    $manifest = $null
    try { $manifest = Get-KitManifest } catch { Write-Log "kit manifest not readable: $($_.Exception.Message)" -Level WARN }
    $patchedMd5 = $null
    if ($manifest -and $manifest.exe) {
        $patchedMd5 = [string]$manifest.exe.md5
        if ($manifest.exe.source -and $manifest.exe.source.md5) { $md5UnpackedExe = [string]$manifest.exe.source.md5 }
        Write-Log "kit manifest: build $($manifest.build), exe source MD5 $md5UnpackedExe, patched exe MD5 $patchedMd5" -Level VERBOSE
    }

    # ---- 6. installer venv ---------------------------------------------------------------------------------------
    Write-Log '== 6. Python packages (bsdiff4, numpy)'
    if (!$venvReady) {
        if (!(Test-Path -LiteralPath $venvPy -PathType Leaf)) {
            if ($Check) { Write-Log "[do]    create the venv $venvDir with $(if ($systemPython) { $systemPython.Path } else { '<Python 3.9+>' })" }
            elseif ($systemPython) {
                Write-Log "Creating venv $venvDir ..." -Level VERBOSE
                $code = Invoke-Native $systemPython.Path @('-m', 'venv', $venvDir)
                if ($code -ne 0 -or !(Test-Path -LiteralPath $venvPy -PathType Leaf)) { throw "Creating the venv $venvDir failed (exit code $code); see $logFile." }
                Write-Log "[ok]    venv created: $venvDir"
            }
        }
        $venvMissing = @(Test-VenvPackage)
        if ($Check) {
            $script:FetchCount++
            Write-Log "[fetch] pip install $($venvMissing -join ' ') (PyPI) into $venvDir"
        } elseif ($NoDownload) {
            Stop-Install "The Python packages $($venvMissing -join ', ') are missing in $venvDir and -NoDownload is set (pip needs the internet)."
        } else {
            $code = Invoke-Native $venvPy (@('-m', 'pip', 'install', '--disable-pip-version-check') + $venvMissing)
            $still = @(Test-VenvPackage)
            if ($code -ne 0 -or $still.Count) { throw "pip install $($venvMissing -join ' ') failed (exit code $code, still missing: $($still -join ', ')); see $logFile." }
            Write-Log "[ok]    installed in the venv: $($venvMissing -join ', ')"
        }
    }

    # ---- 7. credits: RAD Video Tools + ffmpeg --------------------------------------------------------------------
    Write-Log '== 7. Credits movies (RAD Video Tools, ffmpeg)'
    $radExe = $null
    $wantCredits = $false
    if ($NoCredits) {
        Add-Note 'Credits movies skipped (-NoCredits): each DLC ends on a black screen after its last cutscene until they are built.'
    } else {
        $radExe = Find-RadVideo
        if (!$radExe) {
            Add-Note ('RAD Video Tools not found: the credits movies are not built, and each DLC ends on a black screen after its ' +
                'last cutscene. Install RAD Video Tools (free, https://www.radgametools.com/bnkdown.htm) and start Install.bat again - it then builds only the credits.')
        } else {
            Write-Log "[ok]    RAD Video Tools: $radExe"
            $wantCredits = $true
            if (Test-Path -LiteralPath $ffmpegExe -PathType Leaf) {
                Write-Log "[skip]  ffmpeg already there: $ffmpegExe"
            } elseif ($Check) {
                $script:FetchCount++
                Invoke-TruScript -Name 'Get-Tools.ps1' -Arguments @{ Name = @('ffmpeg*'); Check = $true }
            } elseif ($NoDownload) {
                $wantCredits = $false
                Add-Note "ffmpeg missing ($ffmpegExe) and -NoDownload set: credits movies not built."
            } else {
                Invoke-TruScript -Name 'Get-Tools.ps1' -Arguments @{ Name = @('ffmpeg*') }
                if (!(Test-Path -LiteralPath $ffmpegExe -PathType Leaf)) { throw "ffmpeg not found after Get-Tools.ps1: $ffmpegExe" }
            }
        }
    }

    # ---- 8. Steamless-unpacked exe -------------------------------------------------------------------------------
    Write-Log '== 8. Steamless-unpacked tru.exe'
    $alreadyInstalled = $record -and ([string]$record.build -eq $Build)
    if ($patchedMd5 -and $exeMd5 -eq $patchedMd5) {
        Write-Log '[skip]  tru.exe is already the B270 patched exe'
    } else {
        $unpacked = @('tru.exe.unpacked.exe', 'tru.exe.steam_original.unpacked.exe', 'tru.exe.steamless_original') |
            ForEach-Object { Join-Path $GamePath $_ } |
            Where-Object { (Test-Path -LiteralPath $_ -PathType Leaf) -and ((Get-Md5 $_) -eq $md5UnpackedExe) } | Select-Object -First 1
        if ($unpacked) {
            Write-Log "[skip]  Steamless-unpacked exe already there (MD5 ok): $unpacked"
        } else {
            $exeSource = @('tru.exe', 'tru.exe.steam_original') | ForEach-Object { Join-Path $GamePath $_ } |
                Where-Object { (Test-Path -LiteralPath $_ -PathType Leaf) -and ((Get-Md5 $_) -eq $md5SteamExe) } | Select-Object -First 1
            if (!$exeSource) {
                Stop-Install "No Steam v1.1 tru.exe (MD5 $md5SteamExe) in $GamePath (tru.exe or tru.exe.steam_original). Let Steam verify the game files, then start again."
            } else {
                Write-Log "[ok]    Steam original exe: $exeSource"
                $steamlessExe = $null
                $state = 'ok'
                if (Test-Path -LiteralPath $steamless.Folder -PathType Container) {
                    $steamlessExe = Get-ChildItem -LiteralPath $steamless.Folder -Recurse -File -Filter 'Steamless.CLI.exe' | Select-Object -First 1
                }
                if (!$steamlessExe) {
                    $state = Get-PinnedFile $steamless
                    if ($state -ne 'missing' -and (Expand-TruZip -Name $steamless.Name -Zip $steamless.Target -Destination $steamless.Folder -Inner '' -ZipState $state)) {
                        $steamlessExe = Get-ChildItem -LiteralPath $steamless.Folder -Recurse -File -Filter 'Steamless.CLI.exe' | Select-Object -First 1
                    }
                }
                if ($state -eq 'missing') {
                    # no pinned SHA-256 (or -NoDownload / a bad file, already reported): the player runs Steamless by hand
                    if (!$steamless.Sha256) { Stop-Install ($steamless.Manual -f $exeSource, $steamless.Folder) }
                } elseif ($Check) {
                    Write-Log "[do]    Steamless on $exeSource -> $exeSource.unpacked.exe (expected MD5 $md5UnpackedExe)"
                } elseif ($steamlessExe) {
                    Write-Log "Running Steamless on $exeSource ..." -Level VERBOSE
                    $code = Invoke-Native $steamlessExe.FullName @($exeSource)
                    $out = "$exeSource.unpacked.exe"
                    if (!(Test-Path -LiteralPath $out -PathType Leaf)) { throw "Steamless wrote no $out (exit code $code); see $logFile." }
                    $outMd5 = Get-Md5 $out
                    if ($outMd5 -ne $md5UnpackedExe) { throw "Steamless output $out has MD5 $outMd5, expected $md5UnpackedExe. Stopped (file left for inspection)." }
                    Write-Log "[ok]    Steamless: $out (MD5 ok)"
                } else {
                    throw "Steamless.CLI.exe not found in $($steamless.Folder)."
                }
            }
        }
    }

    # ---- 9. the DLC install --------------------------------------------------------------------------------------
    Write-Log '== 9. DLC install (the original''s B270 installer)'
    $creditsDone = $record -and (@($record.credits).Count -ge 2)
    $dlcArgs = @{ Build = $Build; GamePath = $GamePath; Python = $venvPy }
    if ($wantCredits) { $dlcArgs.Credits = $true; $dlcArgs.Rad = $radExe; $dlcArgs.Ffmpeg = $ffmpegExe }
    if ($alreadyInstalled -and (!$wantCredits -or $creditsDone)) {
        Write-Log "[skip]  $Build is already installed (trudlcport_install.json$(if ($creditsDone) { ', with credits' })). Check it: python install_dlc.py --game ""$GamePath"" --verify"
    } elseif ($Check) {
        $what = if ($alreadyInstalled) { 'only the credits movies (the build is installed)' } elseif ($wantCredits) { 'install with --credits' } else { 'install without credits' }
        Write-Log "[do]    Install-TruDlc.ps1 -Build $Build -Python $venvPy$(if ($wantCredits) { ' -Credits -Rad ... -Ffmpeg ...' }): raw packages first, dry run (install_dlc.py --check), then - only after ""All inputs OK"" - $what"
        Write-Log '          the install backs up binkw32.dll / tru.exe to <workspace>\backup, copies ModLoader.asi + binkw32.dll, keeps the old mods\ as mods_backup_<date>'
    } else {
        Invoke-TruScript -Name 'Install-TruDlc.ps1' -Arguments $dlcArgs
        Write-Log '[ok]    DLC installed'
    }

    # ---- 10. plugins ---------------------------------------------------------------------------------------------
    Write-Log '== 10. Fork plugins'
    if ($NoPlugins) {
        Add-Note 'Plugins skipped (-NoPlugins): Lara''s Shadow needs the title-update plugins for the shadow power and the doppelganger.'
    } else {
        $pluginDir = $null
        if ($forkPlugins.Version) {
            $forkFile = 'trudlcport-fork-plugins-{0}.zip' -f $forkPlugins.Version
            $forkItem = @{ Name = "fork plugins $($forkPlugins.Version)"; Url = $forkPlugins.Url; Sha256 = $forkPlugins.Sha256
                           Target = (Join-Path $root "release\fork-plugins\$forkFile"); Source = 'fork release notes' }
            $state = Get-PinnedFile $forkItem
            $dest = Join-Path $root "release\fork-plugins\$($forkPlugins.Version)"
            if (Expand-TruZip -Name $forkItem.Name -Zip $forkItem.Target -Destination $dest -Inner '' -ZipState $state) { $pluginDir = $dest }
            elseif ($Check) { $pluginDir = $dest }
        } else {
            Write-Log '[skip]  no fork release with prebuilt plugins yet - building them instead' -Level VERBOSE
            $vs = Find-VisualStudio
            if (!$vs) {
                Add-Note ('Plugins not installed: no prebuilt release and no Visual Studio x86 build tools found. Lara''s Shadow needs them ' +
                    'for the shadow power and the doppelganger. Install Visual Studio 2022 Community with "Desktop development with C++" and start Install.bat again.')
            } else {
                Write-Log "[ok]    Visual Studio x86 build tools: $vs"
                foreach ($name in $plugins) {
                    $built = Join-Path $asiOut "$name.asi"
                    $src = Join-Path $repo "src\asi\$name"
                    $newest = @(Get-ChildItem -LiteralPath $src -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
                    $fresh = (Test-Path -LiteralPath $built -PathType Leaf) -and $newest.Count -and ((Get-Item -LiteralPath $built).LastWriteTime -gt $newest[0].LastWriteTime)
                    if ($fresh) { Write-Log "[skip]  $name already built: $built" }
                    elseif ($Check) { Write-Log "[do]    build $name (Build-TruAsi.ps1) -> $built" }
                    else { Invoke-TruScript -Name 'Build-TruAsi.ps1' -Arguments @{ Name = $name; VsPath = $vs; OutDir = $asiOut } }
                }
                $pluginDir = $asiOut
            }
        }
        if ($pluginDir) {
            foreach ($name in $plugins) {
                $inGame = Join-Path $GamePath "$name.asi"
                $have = if (Test-Path -LiteralPath $inGame -PathType Leaf) { " (now in the game folder: sha256 $(Get-Sha256 $inGame))" } else { '' }
                if ($Check) { Write-Log "[do]    Set-$name.ps1 -Install -SourceDir $pluginDir$have" }
                else { Invoke-TruScript -Name "Set-$name.ps1" -Arguments @{ Install = $true; GamePath = $GamePath; SourceDir = $pluginDir } }
            }
            if ($plugins -contains 'TruMenu') { Write-Log '          TruMenu: shipped TruMenu.ini = quick bar only (View + Start on the controller); -NoMenu leaves it out' }
        }
    }

    # ---- 11. display settings ------------------------------------------------------------------------------------
    Write-Log '== 11. Fullscreen effects + depth of field'
    $graphicsKey = 'HKCU:\Software\Crystal Dynamics\Tomb Raider: Underworld\Graphics'
    if (!(Test-Path -LiteralPath $graphicsKey)) {
        Add-Note 'Fullscreen effects / depth of field not set: start the game once, then run .\scripts\windows\Set-TruDisplay.ps1 -FullscreenEffects On -DepthOfField On.'
    } else {
        $now = Get-ItemProperty -LiteralPath $graphicsKey
        if ($now.EnableFullscreenEffects -eq 1 -and $now.EnableDepthOfField -eq 1) {
            Write-Log '[skip]  fullscreen effects and depth of field are already on'
        } elseif ($Check) {
            Write-Log "[do]    Set-TruDisplay.ps1 -FullscreenEffects On -DepthOfField On (now $($now.EnableFullscreenEffects) / $($now.EnableDepthOfField); registry key exported to <workspace>\backup first)"
        } else {
            Invoke-TruScript -Name 'Set-TruDisplay.ps1' -Arguments @{ FullscreenEffects = 'On'; DepthOfField = 'On'; GamePath = $GamePath }
        }
    }

    # ---- 12. summary ---------------------------------------------------------------------------------------------
    Write-Log '== Summary'
    foreach ($n in $script:Notes) { Write-Log "Skipped: $n" -Level WARN }
    if ($Check) {
        Write-Log ('Check only - nothing was downloaded or changed. Would download {0} item(s); {1} problem(s) would stop the install.' -f $script:FetchCount, $script:Problems.Count)
        foreach ($p in $script:Problems) { Write-Log "  - $p" -Level ERROR }
    } else {
        Write-Log 'Done. Start the game from Steam: Downloadable Content -> Beneath the Ashes or Lara''s Shadow -> start a NEW game.'
    }
    Write-Log 'Lock the game to 60 fps (TruQoL with -QoL, or your graphics driver; docs/TROUBLESHOOTING.md) - above 60 fps the game misbehaves.'
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
if ($Check -and $script:Problems.Count) { exit 1 }
