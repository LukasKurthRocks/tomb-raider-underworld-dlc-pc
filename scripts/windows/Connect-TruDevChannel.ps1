<#
.SYNOPSIS
    Read-only client for the TCP server inside tru.exe on port 9264 - the FMOD Ex profiler server (audio telemetry).

.DESCRIPTION
    tru.exe links FMOD Ex statically. Its profiler module (fmod_profile.cpp) listens on TCP port 9264 when the game
    initialises FMOD with FMOD_INIT_ENABLE_PROFILE (0x20). The retail game passes 0x200080 (without 0x20), so the
    server does not run in the normal game; see docs\Befund-Entwicklerkanal.md in the workspace for the evidence and
    the ASI design that would switch it on.

    Protocol (read from tru.exe, finding 'Entwicklerkanal' 31.10.2026):
      every packet starts with a 12-byte header  u32 size (incl. header) | u32 timestamp ms | u8 type | u8 subtype |
      u8 0 | u8 0.  Client -> game: only type 0 / subtype 0 'subscribe', payload u8 type | u8 subtype | u32
      interval ms (0 = unsubscribe), size 18. Game -> client: type 3 = CPU usage (3 floats: dsp, stream, update %),
      type 1 = DSP network (n records of 45 bytes: u32 DSP address, char name[32], u32 inputs, u8 bypass flag,
      u32 unknown). There is no command to read or write game memory.

    The script first checks (Get-NetTCPConnection) that something listens on the port. If not, it only reports
    that the channel is not active and does not connect. Otherwise it connects, subscribes to CPU (and with -Dsp
    to the DSP network), prints what arrives for -Seconds, unsubscribes and closes. It sends nothing else.

    Log: <workspace>\logs\Connect-TruDevChannel_<time>.log. -Verbose shows every packet, -Debug the raw header
    bytes, -Trace adds a PowerShell line trace.

.PARAMETER HostName
    Host of the game, default 127.0.0.1.

.PARAMETER Port
    TCP port, default 9264 (FMOD Ex default profiler port, 0x2430 in tru.exe 0x7ef6a6).

.PARAMETER Seconds
    How long to listen after subscribing (default 5).

.PARAMETER IntervalMs
    Minimum time between two packets of one type the game should send (default 500).

.PARAMETER Dsp
    Also subscribe to the DSP network packets (type 1).

.PARAMETER Force
    Connect even when Get-NetTCPConnection shows no listener (e.g. a remote host).

.EXAMPLE
    .\scripts\windows\Connect-TruDevChannel.ps1 -Verbose
.EXAMPLE
    .\scripts\windows\Connect-TruDevChannel.ps1 -Dsp -Seconds 10
#>
[CmdletBinding()]
param(
    [string]$HostName = '127.0.0.1',
    [int]$Port = 9264,
    [int]$Seconds = 5,
    [int]$IntervalMs = 500,
    [switch]$Dsp,
    [switch]$Force,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false
if ($Trace) { Set-PSDebug -Trace 1 }

$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
New-Item -ItemType Directory -Force -Path $paths.Logs | Out-Null
$logFile = Join-Path $paths.Logs ('Connect-TruDevChannel_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Set-TruLogFile -Path $logFile

function New-SubscribePacket {
    # header (size 18, timestamp 0, type 0, subtype 0, 2 x 0) + payload (type, subtype, interval ms)
    param([byte]$Type, [byte]$SubType, [uint32]$Interval)
    $buffer = New-Object byte[] 18
    [BitConverter]::GetBytes([uint32]18).CopyTo($buffer, 0)
    $buffer[12] = $Type
    $buffer[13] = $SubType
    [BitConverter]::GetBytes($Interval).CopyTo($buffer, 14)
    return ,$buffer
}

function Read-Exact {
    # reads exactly $Count bytes or returns $null when the stream ends / the deadline passes
    param([System.Net.Sockets.NetworkStream]$Stream, [int]$Count, [datetime]$Deadline)
    $buffer = New-Object byte[] $Count
    $done = 0
    while ($done -lt $Count) {
        if ((Get-Date) -gt $Deadline) { return $null }
        if (!$Stream.DataAvailable) { Start-Sleep -Milliseconds 20; continue }
        $n = $Stream.Read($buffer, $done, $Count - $done)
        if ($n -le 0) { return $null }
        $done += $n
    }
    return ,$buffer
}

function Write-DspPacket {
    param([byte[]]$Body)
    $count = [int][Math]::Floor($Body.Length / 45)
    Write-Log ('DSP network: {0} nodes' -f $count)
    for ($i = 0; $i -lt $count; $i++) {
        $o = $i * 45
        $address = [BitConverter]::ToUInt32($Body, $o)
        $name = [Text.Encoding]::ASCII.GetString($Body, $o + 4, 32).Split([char]0)[0]
        $inputs = [BitConverter]::ToUInt32($Body, $o + 36)
        $bypass = $Body[$o + 40]
        $unknown = [BitConverter]::ToUInt32($Body, $o + 41)
        Write-Log ('  0x{0:x8} {1,-32} inputs {2,3} bypass {3} field 0x{4:x8}' -f $address, $name, $inputs, $bypass, $unknown)
    }
}

Write-Log ('FMOD profiler client: {0}:{1}, {2} s, interval {3} ms, DSP {4}' -f $HostName, $Port, $Seconds, $IntervalMs, [bool]$Dsp)

$listening = $false
try {
    # the module autoload prints a verbose line per export - keep it out of -Verbose
    $savedVerbose = $VerbosePreference
    $VerbosePreference = 'SilentlyContinue'
    $listening = [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    $VerbosePreference = $savedVerbose
} catch {
    Write-Log ('Get-NetTCPConnection failed: {0}' -f $_.Exception.Message) -Level WARN
}
if (!$listening -and !$Force) {
    Write-Log ('nothing listens on port {0} - channel not active (the retail game starts FMOD without FMOD_INIT_ENABLE_PROFILE). Not connecting.' -f $Port) -Level WARN
    if ($Trace) { Set-PSDebug -Off }
    Write-Host "Log: $logFile"
    return
}

$client = New-Object System.Net.Sockets.TcpClient
$packets = 0
try {
    $client.Connect($HostName, $Port)
    $stream = $client.GetStream()
    Write-Log 'connected'
    $types = @(3)
    if ($Dsp) { $types += 1 }
    foreach ($t in $types) {
        $p = New-SubscribePacket -Type $t -SubType 0 -Interval $IntervalMs
        $stream.Write($p, 0, $p.Length)
        Write-Log ('subscribed to type {0}' -f $t) -Level VERBOSE
    }
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $header = Read-Exact -Stream $stream -Count 12 -Deadline $deadline
        if ($null -eq $header) { break }
        Write-Log ('header {0}' -f [BitConverter]::ToString($header)) -Level DEBUG
        $size = [BitConverter]::ToUInt32($header, 0)
        $stamp = [BitConverter]::ToUInt32($header, 4)
        $type = $header[8]; $subType = $header[9]
        if ($size -lt 12 -or $size -gt 1048576) { Write-Log ('implausible packet size {0} - stop' -f $size) -Level ERROR; break }
        $body = New-Object byte[] 0
        if ($size -gt 12) {
            $body = Read-Exact -Stream $stream -Count ([int]$size - 12) -Deadline $deadline.AddSeconds(2)
            if ($null -eq $body) { Write-Log 'packet body incomplete - stop' -Level WARN; break }
        }
        $packets++
        Write-Log ('packet type {0}/{1}, {2} bytes, t={3} ms' -f $type, $subType, $size, $stamp) -Level VERBOSE
        if ($type -eq 3 -and $body.Length -ge 12) {
            Write-Log ('CPU  dsp {0:N2} %  stream {1:N2} %  update {2:N2} %' -f [BitConverter]::ToSingle($body, 0),
                [BitConverter]::ToSingle($body, 4), [BitConverter]::ToSingle($body, 8))
        } elseif ($type -eq 1) {
            Write-DspPacket -Body $body
        } else {
            Write-Log ('unknown packet type {0}/{1} ({2} bytes)' -f $type, $subType, $size)
        }
    }
    foreach ($t in $types) {
        $p = New-SubscribePacket -Type $t -SubType 0 -Interval 0
        $stream.Write($p, 0, $p.Length)
    }
    Write-Log ('done: {0} packets' -f $packets)
} catch {
    Write-Log ('connection failed: {0}' -f $_.Exception.Message) -Level ERROR
} finally {
    $client.Close()
    if ($Trace) { Set-PSDebug -Off }
}
Write-Host "Log: $logFile"
