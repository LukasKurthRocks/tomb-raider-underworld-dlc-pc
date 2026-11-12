# TruShadowHud.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld) that provides the **HUD natives of the DLC 2
shadow meter** (*Lara's Shadow*) the Xbox title update (TU) added: `larabase` f70-f73 and `dlc2data` f0. The TU HUD
script (Xbox generalbank script 38 = PC script 37) colours the meter with them: red while the power cannot start,
pulsing when the shadow strike is ready, the refill delay. The PC exe has none of them.

**Status 0.1: built 2026-11-03, not played; 0.2 (`dlc2data` f1 bound, P5d) built 2026-11-07, not played.** It belongs to the data tree `work\rebuild\dlc_test50l_hud` (the TU HUD
script and the 74-entry TU `larabase` type script in the generalbank, `tools/generalbank_hud_build.py`). That
generalbank **must not be used without this plugin**: its HUD script calls f71-f73 and `dlc2data` f0 every HUD frame,
which are null natives without it. The plugin alone (with the normal generalbank) only logs that the `larabase`
script has 70 entries and binds nothing there.

## 0.2.1: dated log lines (Q107, 2026-11-12)

Built 2026-11-12 into `work\asi\i_1211\TruShadowHud`, not installed, not played. Only the log format changed (shared
helper `src\asi\TruLog.h`): every line of `TruShadowHud.log` starts with `YYYY-MM-DD HH:MM:SS.mmm`, and each game
process writes one header line `=== <date time> TruShadowHud 0.2.1 session start (pid n) ===` before its first line.
Natives and options are as in 0.2 (same sample .ini). Install:
`scripts\windows\Set-TruShadowHud.ps1 -Install -SourceDir work\asi\i_1211\TruShadowHud`.

| # | TO TEST 0.2.1 | expected |
|---|---|---|
| 1 | start the game once with 0.2.1 installed, read `TruShadowHud.log` from its last `session start` line on | header and `loaded` line name 0.2.1; every newer line starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start |

## Translation

| TU | what it does | PC (this plugin) |
|---|---|---|
| `larabase` binder `0x824a7d28` (vtable `0x820796c8` slot 3) | binds 74 natives: entry k +0x14 = function | vtable `0x862a38` slot 3 -> hook: PC binder `tru+0x3b5490` (70 natives 0..0x45), then `tru+0x1768f0(70..73, f70..f73)` - only when the bound script has exactly 74 entries and 70..73 are unbound natives |
| f70 `0x824aa060` | meter +0x10 = tuning +0x24 (no TU caller) | `TruShadowPowerMeterApi()->delayStart()` |
| f71 `0x824aa0a0` | bool: flag 8 and value > tuning +0x70 x 0.01 x tuning +0x10 (75 % of 1000) | `->strikeReady()` |
| f72 `0x824aa120` | bool: `CanStart(meter)` `0x823d8120` (clears flag 0x200 above tuning +0x28) | `->canStart()` (TruShadowPower's own CanStart) |
| f73 `0x824aa150` | float: max(meter +0x10, 0.0) | `->delayLeft()` |
| registration `0x824d4f58`: type `dlc2data` (fields +0x10 = 1, +0x14 = +0x18 = 4, vtable `0x8207a0ac`) | a static native type | after the PC `larabase` registration (`call tru+0x17ed00` at `tru+0x3a946f`): engine allocator `[[0xcd9cac]+0x48]->vtbl[0x34](0x24, 0)`, ctor `tru+0x174b60("game/script/game/game", "dlc2data", 4, 4, 0)`, vtable = copy of the PC `globaleffect` vtable `0x86279c` (registered with the same 4 / 4 / 0; its TU twin `0x8207a148` equals the TU `dlc2data` vtable in all 13 slots except the binder), slot 3 = hook |
| `dlc2data` binder `0x824a1140`: f0 `0x824a1188`, f1 `0x824a11a0` | f0 = byte gameTracker+0x1244; f1: byte `0x829ca67c` = arg != 0 | base bind `tru+0x174bc0`, f0 = `TruDlc2PlayerDoppelganger()`; 0.2: f1 = the same store into the plugin's byte (export `TruShadowHudDlc2F1`; `0x829ca67c` has no PC reader - see 0.2) |

PC native convention (from the 70 PC `larabase` natives, e.g. `tru+0x399eb0` / `0x399f20` / `0x39a6c0`): cdecl
`(instance, ?, args, result)`; bool results are a byte at `[esp+0x10]`, floats a dword - the TU passes the same in r3..r6.

The bodies are looked up at the first native call: `TruShadowPower.asi` `TruShadowPowerMeterApi` (version >= 2 - 0.11
exports 2, 0.12 exports 3 = 2 + `gt1280` appended; only the version-2 part is used) and `TruDlc2Player.asi`
`TruDlc2PlayerDoppelganger`. Without them the natives answer as the TU does without the tuning object: f71 0, f72 0
(= red meter), f73 0.0, f70 nothing, `dlc2data` f0 0 - logged once.

Not translated: the TU binder also caches the entry addresses 70..73 next to 0..69; the PC cache (`0x105baa8..`) has
no slots for them and no PC code reads them.

Byte pre-checks: 12, checked offline against the installed exe (`work\asi\hud01\prechecks_hud01.txt`,
`tools/pe_bytes_check.py`): 0 mismatches. On a mismatch at run time the part is not patched and the log says why.

## 0.2: `dlc2data` f1 (P5d, 2026-11-07)

`dlc2data` f1 was the only TU native this plugin's types still lacked (`tools/tu_native_coverage.py`: `achievement`
f16-f20 are Xbox Live only, `larabase` f70-f73 and `dlc2data` f0 are here, `uigamedata` f93 / f94 are replaced /
unused). **f1** `0x824a11a0`: `lbz r11, 0(r5); extsb; cntlzw; rlwinm >> 5; xori 1; stb 0x829ca67c` = the bool
argument != 0 into a global byte.

* **Who calls it:** only the TU hint-box script 10 (PC script 9; `tools/script_dis.py xt 10`): f8 (the modal box
  opens: `uitext` f3, `uiscreen` f95, then `f1(1)`, `uiscreen` f86); f7 (message `paused`: `uitext` f4, `uiscreen`
  f87, `f1(0)`) and f9 (when f0 is set: `uitext` f4, `uiscreen` f87, `f1(0)`). Not the HUD script 38. On the PC the
  three calls are replaced by member writes (`tools/script_dlc2_flag_stub.py`), so with today's data f1 is not called.
* **Who reads the byte:** one load in the whole TU image (`work\p5_0711\ppc_hilo_refs.py`: 1 load, 1 store), at
  0x8248d058 in **0x8248cea8 = the Xbox system notification listener** (retail 0x824873d8; message 9 = `XN_SYS_UI`,
  0xa sign-in, 0xe profile settings; debug text "main state playgame %s  quitting %s"). When the Guide opens in main
  state playgame and not quitting, retail pauses the game (`0x8229d6d0(0)` = PC tru+0x1d4780) unless gameTrackerX+0xbb
  == 6 or +0x2c & 0x80; **the TU pauses in those two states as well when the f1 byte is set** (modal DLC 2 hint box
  open). Earlier docs called 0x8248cea8 a "debug TRUE/FALSE dump" - it prints, then acts.
* **PC:** no Guide and no twin of that listener (the PC callers of the pause tru+0x1d4780 are tru+0x1d4891,
  tru+0x1d4981 and tru+0x38bb1e; none tests +0x2c & 0x80 or reacts to a system UI). So nothing on the PC reads the
  byte; 0.2 binds f1 1:1 (store only; `TruShadowHudDlc2F1()` returns it) so that the native type is complete and a TU
  script calling f1 no longer hits a null native.
* Switch `[ShadowHud] TranslateDlc2F1` (default 1 = TU; 0 = f1 unbound as 0.1). No new game address (the same bind
  `tru+0x1768f0`); pre-checks `work\asi\hud02\prechecks_hud02.txt` = the 12 of 0.1 + the PC bool-argument convention
  (`tru+0x399f70 8b44240c 803800 0f95c1`), 13 checks, 0 mismatches. Export added: `TruShadowHudDlc2F1`.
* Side finding (data, not changed here): the stub replaced f0 at the f9 site by a read of member +0x50, which the
  replaced f1 sites also write. On the TU f9 reads f0 = gameTracker+0x1244 (1 in DLC 2), independent of f1; on the PC
  the f9 branch reads 0 after a `paused` message (f7 wrote 0). Whether the player sees a difference (the box is
  already hidden by f7) is not checked.

| # | TO TEST 0.2 | expected |
|---|---|---|
| 1 | game start (with the HUD tree as 0.1) | `TruShadowHud 0.2 loaded (... 0.2: dlc2data f1 1)`, `dlc2data bind 1: 2 functions - f0 bound ..., f1 bound (TU 0x824a11a0 ...)` |
| 2 | DLC 2 hint boxes (hall02 tutorial) with today's data | no `dlc2data f1 ... first call` line (PC script 9 does not call it); HUD as 0.1 |
| 3 | `[ShadowHud] TranslateDlc2F1=0` | `f1 left unbound ([ShadowHud] TranslateDlc2F1=0)` (= 0.1) |

## Options (`TruShadowHud.ini` next to the `.asi`, optional)

| key (`[ShadowHud]`) | default | meaning |
|---|---|---|
| `Enabled` | 1 | 0 = load but patch nothing |
| `LogLevel` | 1 | 0 errors, 1 info (first call of every native), 2 also every change of a native's result |
| `LaraNatives` | 1 | bind `larabase` f70-f73 |
| `Dlc2Data` | 1 | register `dlc2data` and bind f0 |
| `MeterApi` | 1 | 0 = always the answers without the tuning object (test of the fallback) |
| `TranslateDlc2F1` | 1 | 0.2: bind `dlc2data` f1 (TU 0x824a11a0, the hint-box byte); 0 = unbound as 0.1 |

## Build, install, remove (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Name TruShadowHud -OutDir work\asi\hud01 -Verbose
.\scripts\windows\Set-TruShadowHud.ps1 -Install -SourceDir work\asi\hud01   # game closed
.\scripts\windows\Set-TruShadowHud.ps1 -Remove
```

Build 0.1 (`work\asi\hud01`): `TruShadowHud.asi` 128 000 bytes, sha256
`8d664b7fbec2df33d67b6f9f89a0835de7e070c52469d8312b398901b2d2e1cb`; `TruShadowHud.ini` sha256
`316082b8bf6018a110cdcb8b85fc95aff46c138e6de21ac88de896202ed6eaa7`. /W4 without warnings, x86 DLL, imports only
KERNEL32, export `TruShadowHudVersion`. Static runtime (`/MT`). License: MIT, as the repository.

## Data: tree `work\rebuild\dlc_test50l_hud`

`mods\generalbank.drm` md5 `62efb0ee7fc2a21093e5e27e246dfe8b` = the clean generalbank of
`work\rebuild\test50l_look_work\autostart_gb` (md5 `586c37ad...`, no direct-start script 60) with the TU HUD script 38
(PC 37), the TU `larabase` type script 211 (PC 213, 74 entries) and the TU textures 7899 / 7036 - nothing else changed
(`drm_section_compare.py`: 1261 of 1263 sections identical, 2 added). Built by `tools/generalbank_hud_build.py`
(control chain on the retail script = Crystal's PC script 37 except the dependency order; details in the workspace
`docs\Befund-Schattenleiste-HUD.md`). `tree_check.py`: 1 DRM, readback ok, 0 reloc errors, 0 out of bounds;
`native_calls_check.py`: 0 calls without a function entry. In a profile the tree replaces the `autostart_gb` tree
(same position: last).

## TO TEST (owner)

Profile: 50l_look (`regress_shadowlara_50l_look.json`) with `work\rebuild\dlc_test50l_hud\mods` instead of
`test50l_look_work\autostart_gb\mods`, plus `TruShadowHud` from `work\asi\hud01` (`[ShadowHud] LogLevel=2`), TruShadowPower
`work\asi\v11` or `v12`, TruDlc2Player `dlc2p02`.

| # | test | expected |
|---|---|---|
| 1 | game start | TruShadowHud.log: `0.1 loaded`, `larabase: vtable 0x00862a38 slot 3 -> hook`, `dlc2data: registration hooked`, then `dlc2data: native type registered`, `larabase bind 1: 74 functions (TU type script) - f70-f73 bound`, `dlc2data bind 1: ... f0 bound` |
| 2 | main menu / main game level | no crash; HUD (health, ammo) as before; in the main game no shadow meter |
| 3 | DLC 2 start | `TruShadowPower meter interface found (version 2 / 3)`, `dlc2data f0 ... first call -> 1 (doppelganger player)`; the shadow meter (silhouette) is visible |
| 4 | hold RB until the meter is empty | f72 `-> 0 (cannot start: meter red)` in the log; **the meter turns red** and stays red until it refilled above 150 |
| 5 | let it refill | after a short delay (f73 `refill delay left` > 0, then 0) the meter fills; colour back to normal (f72 `-> 1`) |
| 6 | meter above 75 % | f71 `-> 1 (strike ready)`; **the meter pulses** |
| 7 | trouble | `[ShadowHud] MeterApi=0` (fallback: red meter, no pulse) or back to the `autostart_gb` tree; send TruShadowHud.log |

| task | status |
|---|---|
| natives f70-f73, dlc2data f0 | ⏳ built, not played |
| generalbank tree dlc_test50l_hud | ⏳ built, not played |
| TruShadowPower `[Meter] HudBar` (feeds the silhouette) | unchanged - it is the TU's own refill / drain HUD trigger; keep 1 |
