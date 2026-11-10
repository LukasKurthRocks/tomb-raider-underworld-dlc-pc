<#
.SYNOPSIS
    Installs or removes TruShadowPower.asi (DLC 2 shadow-power slow motion) next to tru.exe.

.DESCRIPTION
    -Install copies <workspace>\work\asi\TruShadowPower.asi (built by Build-TruAsi.ps1) and its sample .ini into the
             game folder; the Ultimate ASI Loader the game ships as binkw32.dll loads every *.asi there.
    -Remove  deletes them again - only if they are ours (same SHA-256 as the built file / the sample .ini, or one of
             our earlier released builds listed in $earlierBuilds); a foreign file of the same name is never
             overwritten or removed. TruShadowPower.log is left in place.
    -Install over an earlier build of ours replaces it (update); an .ini the owner edited is not ours and is kept
             (the plugin's built-in defaults cover options it lacks).
    The game must not be running. Every run writes <workspace>\logs\Set-TruShadowPower_<time>.log. -Verbose shows the
    steps, -Debug the hashes, -Trace adds a PowerShell line trace.

.PARAMETER GamePath
    Game folder; default: found through the Steam libraries.

.PARAMETER SourceDir
    Folder with the built .asi / .ini (default <repository>\work\asi; e.g. work\asi\v05 for a build made with
    Build-TruAsi.ps1 -OutDir).

.EXAMPLE
    .\Set-TruShadowPower.ps1 -Install -Verbose
    .\Set-TruShadowPower.ps1 -Install -SourceDir .\work\asi\v05
    .\Set-TruShadowPower.ps1 -Remove
#>
[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install', Mandatory)][switch]$Install,
    [Parameter(ParameterSetName = 'Remove', Mandatory)][switch]$Remove,
    [string]$GamePath,
    [string]$SourceDir,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
if ($PSBoundParameters.ContainsKey('Debug')) { $DebugPreference = 'Continue' }
# shared helpers: Write-Log, Set-TruLogFile, Get-TruWorkspacePath, Find-TruGamePath, ...
Import-Module (Join-Path $PSScriptRoot 'TruCommon.psm1') -Force -Verbose:$false

$paths   = Get-TruWorkspacePath -ScriptRoot $PSScriptRoot
$repo    = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$built   = if ($SourceDir) { $SourceDir } else { Join-Path $repo 'work\asi' }
$names   = 'TruShadowPower.asi', 'TruShadowPower.ini'
# SHA-256 of earlier builds of ours (0.1 = slow motion only, 0.2 = estimated meter, 0.3 = translated meter, all
# 2026-10-30; 0.4 = Lara meter conditions, 2026-10-31; 0.5 = TU states (work\asi\v05) and 0.5.1 as installed for
# test 48k, 2026-11-01; 0.6 = condition 1046 (work\asi\v06), 2026-11-01; 0.7 = condition 1055 (work\asi\v07) and the
# sample .ini of 0.5-0.7, 2026-11-02; 0.8 = look events (work\asi\v08); 0.9 = TU tick / adrenaline look (work\asi\v09),
# 2026-11-02; 0.10 = look screen effect (work\asi\v10), 0.11 = GlobalParams[7] / state 2102 / meter API v2
# (work\asi\v11), 2026-11-03; 0.12 - 0.16 (work\asi\v12 .. v16), 2026-11-03 .. 2026-11-06; 0.16 shipped the
# unchanged 0.15 sample .ini; 0.17 LB / RB only as the game gets them, [ShadowPower] MenuInput (work\asi\v17,
# 2026-11-06); 0.18 K11 adrenaline (work\asi\v18, 2026-11-07); 0.19 TruMenu's TruMenuPadBlock instead of the pad-chain
# re-wrap (work\asi\v19, 2026-11-07, new sample .ini: comment of MenuInput); 0.20 [Look] CameraFlag default 1 = TU
# (work\asi\v20, 2026-11-07, sample .ini CameraFlag=1); 0.21 X23 time-scale request slot 6 (work\asi\power021,
# 2026-11-10, sample .ini [TimeScale] TranslateSlot6=1); 0.22 K-5 combat reticle request and adrenaline refill
# (work\asi\power022, 2026-11-10, md5 10654dc22b5937f3e3ad878a4cc59557 = installed on 2026-11-10, sample .ini
# [Reticle]); 0.23 N2 [Meter] Infinite (work\asi\power023, 2026-11-10, sample .ini [Meter] Infinite=0)) - recognised
# as ours for update / removal; 0.24 N6 [Camera] TuTimeStep (work\asi\power024, 2026-11-11).
# The current build 0.25 (camera comparison: keys [Camera] CameraTuTimeStep / [Cloth] ClothTuTimeStep - the old name
# TuTimeStep is still read -, [Camera] Trace (TruCam.log) and [Camera] DoppelgangerSettings, defaults 0;
# work\asi\power025, 2026-11-11) ships a new sample .ini; its hashes are listed too (marked current) so a later build
# recognises it. Install it with -SourceDir <repo>\work\asi\power025.
$earlierBuilds = @{
    'TruShadowPower.asi' = @('5eaeeb3d33d5e53b7059ff39323907cc38d2288625c09439943efabb20093366',
                             '0e307cab2bae9e805ecd0a2c4fb645b943ec792c47ae8a32d489d5441b2e335e',
                             '5d638bae7c41c888dac8d328ec8ef5c5aaac85c0c3100f3fe071409ebc247b7c',
                             '31cea1102d986789d656c73472cd410cd560ea890c6e27f17e583b230183c9e0',
                             '6887f3dc0436e5125f5b824d5af168a7493dc9afdb4e97572380c381bbb45a31',
                             '004e190490b66872c6bc3780681ae45877d25501974a602b28c9d2a9acdedd2e',
                             '68009a611af59f980a6d80053720e791173e32ec93b6ef5a4707e2bd6f5005b9',
                             '0a536f3c1f4835640e94259f653638e5983b531d634219240980d23ad3ec5394',
                             '8e27662950b98778a882334e86fbe8be404c4fb39f12456b5969f8fefd904af5',   # 0.8 look (work\asi\v08)
                             '37b0d55016689de9896c39abe6052c84aadebf415eebd2e1c60437af39616c8a',   # 0.9 TU tick / adrenaline (work\asi\v09)
                             '9570fe9089d8b82dfc8cb6fb1033d52a49445dda11e3d5bfaa8b8224be202256',   # 0.10 look screen effect (work\asi\v10)
                             'fe42c05135581cdef87fae7b1d5e41c2a08213f2d2d38f02f36a82fc2c85f30a',   # 0.11 GlobalParams[7] / 2102 / API v2 (work\asi\v11)
                             'a3dd085da71e630a87ea220b4c7b24294421e1080c9c592f84bf173f533b0c5e',   # 0.12 (work\asi\v12)
                             'a3961fb70975d8436a032250203df6ef6577987429b1529993bdfd415493fb1b',   # 0.13 2102 check next to TruDataGuard (work\asi\v13)
                             'e8746362890d87be6139d297feb3dbb4978fc05a88698ced5969c846c0619bd6',   # 0.14 loop sound / move events / camera flag / strike look (work\asi\v14)
                             'b0432e31f71cd3ab9b4cdcfa7ab3ecc69d86155f2fea4f7c2da53f13b4ed42ab',   # 0.15 cloth TU time step (work\asi\v15)
                             '1dbf267a5f8cbe048e9e0c16990486b4f594fb28d698e614ad6606e8c6609732',   # 0.16 tick only with a player in a level (work\asi\v16, md5 9eec75eb04b71601b2d74d1468050801)
                             '0229e49c771a8f55c2e19ef8617648a1a8887c1f85554b1d52b849f3e2ce11ff',   # 0.17 LB / RB only as the game gets them (work\asi\v17, md5 f01010291dfe09ff325a6e8ab40be834)
                             'fc56e3b72d7cb2a0dcf7b9a3a512b9e3595198853304f14c2e2d11a3d57c4b0f',   # 0.18 K11 adrenaline (work\asi\v18, md5 0ee7c5fca49716f2637ade50e37a7032)
                             '06f80b26ebd103348a05eec0c79cf9f2d7b6ba16ee6eb140940190470dcb5b73',   # 0.19 TruMenuPadBlock (work\asi\v19, md5 02a8e389028c1c78e0662b412be4aeb4)
                             '21c12e8b21c2fa51ec0a89c5b64f206284f435c075ffc21030ac46129ad189b2',   # 0.20 camera flag default 1 (work\asi\v20, md5 26c253ad519a072d6b2573889aac7ab6 = installed on 2026-11-10)
                             'fc0885d0162d50880be353ae7c72a11bf37bd62b716dd10f813d478679063681',   # 0.21 X23 slot 6 (work\asi\power021, not installed)
                             'fb19e1c4fa0bc444cbf7eb3bc422989a588539b0ce72fbe8b5fc3c5b76a06a31',   # 0.22 K-5 reticle / refill (work\asi\power022, md5 10654dc22b5937f3e3ad878a4cc59557 = installed on 2026-11-10)
                             'c22dac1ce3c09f4049600f82908b9c6c84fc71e707ad930575ec4ae3d4741a58',   # 0.23 N2 [Meter] Infinite (work\asi\power023, md5 b679a97ad58c753717574e4bc5605ab0, not installed)
                             '5ca2d7adfa45aec86ec6a1b4651aa10ae099735fbba7c13afa183bde24b1efdf',   # 0.24 N6 [Camera] TuTimeStep (work\asi\power024, md5 3f1d37f5dd003d090bee745bf6121c87, not installed)
                             '89d15879f6f32b7eb8402c95668fefeb4ea999c5f571c32e3d5d2157a88c9114')   # 0.25 camera trace / doppelganger settings (work\asi\power025, md5 ea3c85aa0b6c283f358a408add8faa6b, current, not installed)
    'TruShadowPower.ini' = @('03499f85d90031c5f0140b98be23f7b5dcb11f92ff8834b3ebe6d1b6aea4a0db',
                             '7130a68b309aedd422082beea02f78c9a8d67ba10ab16209561f5dabc614d42e',
                             '3001b5730bcecd218857143df32632b82dcb6c569f34c23853535f3b806a5f2a',
                             '4924bfb8cac427467517c10c543f9c6eadc1f7503cf755ff54a5ef99671e29d9',
                             '162111a4586f70f7c19ca9e98f186998f1961a8441a8296a6b9fc34b0296c745',
                             '2cdc7d4992fdad5449c521370df9b2a786d2a3b5c34673af5f62d42489de1ac9',   # 0.8 sample .ini ([Look])
                             'c9e7fde0b34d80362fe608aa1bd8b91c2a9d376050032135efb6b47a52bfb07c',   # 0.9 sample .ini (AdrenalineMode)
                             '97dccd43228ed0942fa9fbc4f7a35b17aa17189e9fc1843d4ef4f82f0dd25f16',   # 0.10 sample .ini (ScreenEffect)
                             'dab30d022a0067b58b8d6e1c20fab323f3e71d1fb6ed358fa4cf86437b95c0cd',   # 0.11 sample .ini (GlobalParams7, State2102)
                             'd8467e122ed50150aeac292075e6ec3ee6c634295e6867a3ab91355e521bf132',   # 0.12 / 0.13 sample .ini
                             '5bf019742d81fe897bbc08fe145cccde0b45468c603852c469798f468b2d0c50',   # 0.14 sample .ini ([Sound] LoopSound, [Look] MoveEvents / CameraFlag / StrikeLook)
                             '4109ea03592cbb70cc1cf96158336d8045d8ddebbba8da87b9548a8add1cbea3',   # 0.15 / 0.16 sample .ini ([Cloth] TuTimeStep)
                             '891e2d9c554239f9a1d1202c7e90511ef15954ac09b3ac9ccfb8778604d1d9ad',   # 0.17 sample .ini ([ShadowPower] MenuInput)
                             '6acc71004ab8c0e2ef7898e0a2feec25e0b093afaf5c071a5fde4a87710a2c26',   # 0.18 sample .ini ([Adrenaline])
                             '0b056fc3baac70cf0571aa82a5933fd0bbcdd4fd17ee5b64433b2a89225726c4',   # 0.19 sample .ini (MenuInput comment)
                             'df2250c0d73f243e6f3c66456c45d31e6b390d029a43f7391ceeb72b969c8656',   # 0.20 sample .ini (CameraFlag=1)
                             '7d9f4d2b7f7a7a5176c454b961df9885209db31efc6b2606c04ca77a22cd27da',   # 0.21 sample .ini ([TimeScale] TranslateSlot6)
                             '0215ac43c100a4a613ad05959966817df45eb90c83d86b89ac3adcb3cbaaf998',   # 0.22 sample .ini ([Reticle])
                             '682949882f7777c1dcf0e9e1233ae1da9bed273a42b61f83e6c14ad46e01d3cb',   # 0.23 sample .ini ([Meter] Infinite=0)
                             '64f16eef48ea3a89fe6de96c2ce2150bbf6ce6cfbfdf6c999ae31ea810b1c6b4',   # 0.24 sample .ini ([Camera] TuTimeStep=0)
                             '12285a5977b07ffbec8d9b3a01a97e14792cd5ec0a127dc97807f9dd978e859d')   # 0.25 sample .ini ([Camera] CameraTuTimeStep / DoppelgangerSettings / Trace, [Cloth] ClothTuTimeStep, current)
}
$logDir  = $paths.Logs
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ('Set-TruShadowPower_{0}_{1}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PSCmdlet.ParameterSetName)
Set-TruLogFile -Path $logFile

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

if ($Trace) { Set-PSDebug -Trace 1 }
try {
    Write-Log "Set-TruShadowPower mode=$($PSCmdlet.ParameterSetName) log=$logFile" -Level VERBOSE
    if (Get-Process -Name 'tru' -ErrorAction SilentlyContinue) { throw 'Tomb Raider: Underworld is running. Please close it first.' }
    if (!$GamePath) { $GamePath = Find-TruGamePath }
    if (!$GamePath -or !(Test-Path -LiteralPath (Join-Path $GamePath 'tru.exe'))) { throw "Game folder not found (-GamePath): $GamePath" }
    Write-Log "Game folder: $GamePath" -Level VERBOSE

    foreach ($name in $names) {
        $source = Join-Path $built $name
        $target = Join-Path $GamePath $name
        if (!(Test-Path -LiteralPath $source)) { throw "$source not found (run Build-TruAsi.ps1 first)." }
        $sourceHash = Get-Sha256 $source
        Write-Log "$name built sha256 $sourceHash" -Level DEBUG
        $targetHash = if (Test-Path -LiteralPath $target) { Get-Sha256 $target } else { $null }
        if ($targetHash) { Write-Log "$name installed sha256 $targetHash" -Level DEBUG }
        $isEarlier = $targetHash -and ($earlierBuilds[$name] -contains $targetHash)
        if ($Install) {
            if ($targetHash -eq $sourceHash) { Write-Log "$name already installed."; continue }
            if ($targetHash -and !$isEarlier) {
                if ($name -like '*.ini') { Write-Log "$target was edited (not a build of ours) - kept." -Level WARN; continue }
                throw "$target exists and is not a build of ours - left untouched."
            }
            Copy-Item -LiteralPath $source -Destination $target -Force
            if ($isEarlier) { Write-Log "$name updated in $GamePath (earlier build replaced)." }
            else { Write-Log "$name copied to $target." }
        }
        else {
            if (!$targetHash) { Write-Log "$name not in the game folder." -Level VERBOSE; continue }
            if ($targetHash -ne $sourceHash -and !$isEarlier) { Write-Log "$target is not a build of ours - left untouched." -Level WARN; continue }
            Remove-Item -LiteralPath $target
            Write-Log "$name removed from $GamePath."
        }
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
