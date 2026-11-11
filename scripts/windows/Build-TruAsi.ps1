<#
.SYNOPSIS
    Builds the ASI plugins of this fork (src\asi\<name>\<name>.cpp) with the installed Visual Studio x86 toolchain.

.DESCRIPTION
    Today: TruShadowPower.asi (DLC 2 shadow-power slow motion, src\asi\TruShadowPower\README.md) and the other
    plugins below src\asi. TruMenu also compiles Dear ImGui (src\asi\third_party\imgui, table $extra below; objects
    in <OutDir>\obj_TruMenu).
    Calls vcvarsall.bat (target x86) of the newest Visual Studio found (2022 Community by default), compiles with
    cl /LD /O2 /MT (static runtime, no extra DLLs next to the game) and writes <workspace>\work\asi\<name>.asi plus
    the sample .ini. Nothing is copied into the game folder - install with Set-TruShadowPower.ps1 -Install.
    TruShadowPower (2026-11-11, Q30): first the 0.26 doppelganger mode tables are generated from the player's own
    files (tools\tu_dg_modes_inc.py, TitleUpdate.000 + PC patch.000, read-only) into
    src\asi\TruShadowPower\TruShadowPower_dgmodes.local.inc (gitignored: converted title-update data, never committed;
    generator log <OutDir>\TruShadowPower_dgmodes.txt). Without a TitleUpdate.000 the generator is skipped and logged:
    the plugin builds without the tables (__has_include; DgModeTables reports "not built in", the stand-in keeps the
    0.25 tables) or with an include left by an earlier run (its date is logged). A failing generator stops the build.
    Every run writes <workspace>\logs\Build-TruAsi_<time>.log incl. the compiler / linker output. -Verbose shows the
    steps, -Debug the commands and dumpbin output, -Trace adds a PowerShell line trace.

.PARAMETER Name
    Plugin folder below src\asi (default TruShadowPower).

.PARAMETER VsPath
    Visual Studio installation (default: C:\Program Files\Microsoft Visual Studio\2022\Community).

.PARAMETER OutDir
    Output folder (default <repository>\work\asi). A separate folder (e.g. work\asi\v05) keeps an earlier build of the
    same plugin untouched.

.PARAMETER TitleUpdate
    TruShadowPower only: the player's Xbox title update TitleUpdate.000 for the mode-table generator (default
    <workspace>\data\TombRaiderUnderworld_Patched\TitleUpdate.000). Missing = build without generating (logged).

.EXAMPLE
    .\Build-TruAsi.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [string]$Name = 'TruShadowPower',
    [string]$VsPath = 'C:\Program Files\Microsoft Visual Studio\2022\Community',
    [string]$OutDir,
    [string]$TitleUpdate,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

# <workspace> = the folder that holds the repository (see Get-TruWorkspacePath)
$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$repo    = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$srcDir  = Join-Path $repo "src\asi\$Name"
$outDir  = if ($OutDir) { $OutDir } else { Join-Path $repo 'work\asi' }
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $outDir, $logDir | Out-Null
$logFile = Join-Path $logDir ('Build-TruAsi_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Set-TruLogFile -Path $logFile

function Invoke-Logged {
    param([string]$Exe, [string[]]$Arguments)
    Write-Log ('{0} {1}' -f $Exe, ($Arguments -join ' ')) -Level DEBUG
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object { Write-Log ([string]$_) -Level DEBUG }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $code
}

function Update-TruDgModesInclude {
    # TruShadowPower 0.26 mode tables: tools\tu_dg_modes_inc.py writes the gitignored include from the player's own
    # TitleUpdate.000 + PC patch.000; no TitleUpdate.000 = skip and log (the plugin handles a missing include itself)
    $include = Join-Path $srcDir 'TruShadowPower_dgmodes.local.inc'
    $tu = if ($TitleUpdate) { $TitleUpdate } else { Join-Path $paths.Workspace 'data\TombRaiderUnderworld_Patched\TitleUpdate.000' }
    $python = Join-Path $paths.Workspace 'bin\venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $tu -PathType Leaf)) {
        if (Test-Path -LiteralPath $include) {
            Write-Log ('dgmodes: no TitleUpdate.000 ({0}) - include not regenerated, the existing one from {1:yyyy-MM-dd HH:mm} is built in: {2}' -f $tu, (Get-Item -LiteralPath $include).LastWriteTime, $include) -Level WARN
        } else {
            Write-Log ('dgmodes: no TitleUpdate.000 ({0}) - building without the 0.26 mode tables (DgModeTables "not built in", stand-in keeps 0.25)' -f $tu) -Level WARN
        }
        return
    }
    if (!(Test-Path -LiteralPath $python)) { throw "Python venv not found: $python (needed for tools\tu_dg_modes_inc.py)" }
    $text = Join-Path $outDir 'TruShadowPower_dgmodes.txt'
    Write-Log ('dgmodes: generating {0} from {1}' -f $include, $tu) -Level VERBOSE
    # the generator's PC input (../data/pc/patch.000) is relative to the repository: run it from there
    Push-Location -LiteralPath $repo
    try {
        $code = Invoke-Logged -Exe $python -Arguments @('-u', '-I', '-X', 'utf8', 'tools\tu_dg_modes_inc.py', $text, $include, '--tu', $tu)
    } finally {
        Pop-Location
    }
    if (Test-Path -LiteralPath $text) {
        Select-String -LiteralPath $text -Pattern '^SELF-CHECK' | ForEach-Object { Write-Log ('dgmodes: ' + $_.Line) }
    }
    if ($code -ne 0 -or !(Test-Path -LiteralPath $include)) { throw "dgmodes generator failed (exit code $code), see $logFile and $text" }
    Write-Log ('dgmodes: include written ({0} bytes, md5 {1})' -f (Get-Item -LiteralPath $include).Length, (Get-FileHash -LiteralPath $include -Algorithm MD5).Hash.ToLower())
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Build-TruAsi name=$Name log=$logFile" -Level VERBOSE
    $source = Join-Path $srcDir "$Name.cpp"
    if (!(Test-Path -LiteralPath $source)) { throw "Source not found: $source" }
    $vcvars = Join-Path $VsPath 'VC\Auxiliary\Build\vcvarsall.bat'
    if (!(Test-Path -LiteralPath $vcvars)) { throw "vcvarsall.bat not found: $vcvars (-VsPath)" }
    if ($Name -eq 'TruShadowPower') { Update-TruDgModesInclude }

    $asi = Join-Path $outDir "$Name.asi"
    $obj = Join-Path $outDir "$Name.obj"
    # vcvarsall sets the environment for one cmd.exe; compile and link in the same call. amd64_x86 = x64 host, x86 target
    $cmd = 'call "{0}" amd64_x86 >nul && cl /nologo /LD /O2 /MT /W4 /EHsc /DNDEBUG "{1}" /Fo"{2}" /Fe"{3}" /link /NOLOGO /DLL kernel32.lib' -f $vcvars, $source, $obj, $asi
    # plugins with extra sources (paths below src\asi): TruMenu = Dear ImGui core + DX9 / Win32 backends
    $extra = @{
        'TruMenu' = @{
            Sources  = @('third_party\imgui\imgui.cpp', 'third_party\imgui\imgui_draw.cpp',
                         'third_party\imgui\imgui_tables.cpp', 'third_party\imgui\imgui_widgets.cpp',
                         'third_party\imgui\imgui_demo.cpp', 'third_party\imgui\backends\imgui_impl_dx9.cpp',
                         'third_party\imgui\backends\imgui_impl_win32.cpp')
            Includes = @('third_party\imgui', 'third_party\imgui\backends')
            Defines  = @('IMGUI_IMPL_WIN32_DISABLE_GAMEPAD', 'IMGUI_DISABLE_WIN32_DEFAULT_IME_FUNCTIONS',
                         'IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS', 'IMGUI_DISABLE_DEMO_WINDOWS')
            Libs     = @('user32.lib')
        }
    }
    if ($extra.ContainsKey($Name)) {
        $asiRoot = Join-Path $repo 'src\asi'
        $spec = $extra[$Name]
        $objDir = Join-Path $outDir "obj_$Name"
        New-Item -ItemType Directory -Force -Path $objDir | Out-Null
        $sources = @($source) + @($spec.Sources | ForEach-Object { Join-Path $asiRoot $_ })
        foreach ($file in $sources) { if (!(Test-Path -LiteralPath $file)) { throw "Source not found: $file" } }
        $quoted = ($sources | ForEach-Object { '"{0}"' -f $_ }) -join ' '
        $includes = ($spec.Includes | ForEach-Object { '/I"{0}"' -f (Join-Path $asiRoot $_) }) -join ' '
        $defines = ($spec.Defines | ForEach-Object { "/D$_" }) -join ' '
        # several sources: /Fo is a folder (trailing backslash doubled so it does not escape the quote)
        $cmd = 'call "{0}" amd64_x86 >nul && cl /nologo /LD /O2 /MT /W4 /EHsc /DNDEBUG {1} {2} {3} /Fo"{4}\\" /Fe"{5}" /link /NOLOGO /DLL kernel32.lib {6}' -f $vcvars, $defines, $includes, $quoted, $objDir, $asi, ($spec.Libs -join ' ')
    }
    Write-Log "Compiling $source -> $asi" -Level VERBOSE
    $code = Invoke-Logged -Exe 'cmd.exe' -Arguments @('/c', $cmd)
    if ($code -ne 0 -or !(Test-Path -LiteralPath $asi)) { throw "Build failed (exit code $code), see $logFile" }

    $ini = Join-Path $srcDir "$Name.ini"
    if (Test-Path -LiteralPath $ini) { Copy-Item -LiteralPath $ini -Destination (Join-Path $outDir "$Name.ini") -Force }
    # TruMenu 0.10: the default radial menu file goes into the build folder as well (Set-TruMenu.ps1 installs it);
    # 0.10.1: the tour file (radial level Tests / Rundgang) too
    foreach ($suffix in 'radial.txt', 'tour.txt', 'switches.txt') {   # TruMenu 0.21.5: + the switches file (page Fixes)
        $radial = Join-Path $srcDir "$Name.$suffix"
        if (Test-Path -LiteralPath $radial) { Copy-Item -LiteralPath $radial -Destination (Join-Path $outDir "$Name.$suffix") -Force }
    }

    # check: 32-bit DLL, exports, imports (dumpbin from the same toolchain)
    $dumpCmd = 'call "{0}" amd64_x86 >nul && dumpbin /nologo /headers /exports /imports "{1}"' -f $vcvars, $asi
    # vcvarsall writes harmless messages to stderr (e.g. vswhere not on PATH) - collect them without stopping
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $dump = & cmd.exe /c $dumpCmd 2>&1 | ForEach-Object { [string]$_ }
    } finally {
        $ErrorActionPreference = $previous
    }
    $dump | ForEach-Object { Write-Log $_ -Level DEBUG }
    $machine = $dump | Where-Object { $_ -match 'machine \(x86\)' } | Select-Object -First 1
    $isDll = $dump | Where-Object { $_ -match '^\s+DLL$' } | Select-Object -First 1
    if (!$machine -or !$isDll) { throw "$asi is not a 32-bit DLL (dumpbin), see $logFile" }
    $hash = (Get-FileHash -LiteralPath $asi -Algorithm SHA256).Hash.ToLower()
    Write-Log ('Built {0} ({1} bytes, x86 DLL, sha256 {2})' -f $asi, (Get-Item -LiteralPath $asi).Length, $hash)
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
