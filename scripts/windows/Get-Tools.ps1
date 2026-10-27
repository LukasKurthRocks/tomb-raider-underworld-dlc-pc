<#
.SYNOPSIS
    Downloads the portable reverse engineering tools (Ghidra, Temurin JDK 25) into .\bin and verifies SHA-256.

.DESCRIPTION
    Zips go to .\bin\_download, are checked against the official SHA-256 and only then unpacked into .\bin.
    Existing verified zips are not downloaded again; already unpacked tools are left alone.
    Every run writes .\logs\Get-Tools_<time>.log. -Verbose shows steps, -Debug URLs/paths/hashes,
    -Trace adds a PowerShell line trace.

.EXAMPLE
    .\Get-Tools.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }

$root   = $PSScriptRoot
$binDir = Join-Path $root 'bin'
$dlDir  = Join-Path $binDir '_download'
$logDir = Join-Path $root 'logs'

$tools = @(
    @{
        Name   = 'Ghidra 12.2'
        Url    = 'https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.2_build/ghidra_12.2_PUBLIC_20261016.zip'
        File   = 'ghidra_12.2_PUBLIC_20261016.zip'
        Sha256 = '2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67'
        Folder = 'ghidra_12.2_PUBLIC'
    },
    @{
        # Ghidra 12.2 requires Java 25 (application.java.min=25)
        Name   = 'Temurin JDK 25.0.5+8'
        Url    = 'https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.5%2B8/OpenJDK25U-jdk_x64_windows_hotspot_25.0.5_8.zip'
        File   = 'OpenJDK25U-jdk_x64_windows_hotspot_25.0.5_8.zip'
        Sha256 = '636bdc13dc649ddc7d5921c5c7d23cca6e44fd19d662b45cc9c02135a6c96c42'
        Folder = 'jdk-25.0.5+8'
    }
)

New-Item -ItemType Directory -Force -Path $dlDir, $logDir | Out-Null
$logFile = Join-Path $logDir ('Get-Tools_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

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

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Get-Tools log=$logFile" -Level VERBOSE
    foreach ($tool in $tools) {
        $zip    = Join-Path $dlDir $tool.File
        $target = Join-Path $binDir $tool.Folder
        Write-Log "== $($tool.Name)" -Level VERBOSE
        Write-Log "url=$($tool.Url) zip=$zip target=$target" -Level DEBUG

        if (Test-Path -LiteralPath $target) {
            Write-Log "$($tool.Name): already unpacked in $target"
            continue
        }

        $haveValidZip = (Test-Path -LiteralPath $zip) -and ((Get-Sha256 $zip) -eq $tool.Sha256)
        if (!$haveValidZip) {
            Write-Log "Downloading $($tool.File) ..." -Level VERBOSE
            $previous = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                & curl.exe -sSL --fail -o $zip $tool.Url 2>&1 | ForEach-Object { Write-Log ('curl: ' + [string]$_) -Level WARN }
                $code = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $previous
            }
            if ($code -ne 0) { throw "Download of $($tool.File) failed (curl exit code $code)." }
        }

        $hash = Get-Sha256 $zip
        Write-Log "sha256 $hash (expected $($tool.Sha256)), size $((Get-Item -LiteralPath $zip).Length)" -Level DEBUG
        if ($hash -ne $tool.Sha256) { throw "SHA-256 mismatch for $($tool.File): $hash" }
        Write-Log "$($tool.Name): SHA-256 ok"

        Write-Log "Unpacking to $binDir ..." -Level VERBOSE
        Expand-Archive -LiteralPath $zip -DestinationPath $binDir
        if (!(Test-Path -LiteralPath $target)) { throw "Expected folder not found after unpacking: $target" }
        $count = @(Get-ChildItem -LiteralPath $target -Recurse -File).Count
        Write-Log "$($tool.Name): unpacked to $target ($count files)"
    }
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
