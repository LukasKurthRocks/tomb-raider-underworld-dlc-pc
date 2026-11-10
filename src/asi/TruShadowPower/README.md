# TruShadowPower.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld) that brings back the **slow motion and the
meter of the DLC 2 shadow power** (*Lara's Shadow*). On the Xbox the title update (TU) gives Lara the Doppelgänger's
power: while LB or RB is held the world slows down, a meter (the yellow silhouette in the HUD) drains; when it is empty
the power ends, and it refills over time. The PC exe never received that code, but it has the engine parts the TU
drives: the time-scale ramps, the HUD bar and the same tuning data.

Since 0.3 the meter is a **function-by-function translation of the TU code** (decompiled from the TU memory image; same
formulas, order and branches) that reads its rates and scales from the **same data the Xbox reads** - no estimated
values. The translation table, the data sources and every left-out part are documented in
[docs/WINDOWS_REBUILD.md](../../../docs/WINDOWS_REBUILD.md) finding 43 ("ASI step 3.3") and the project's
`Befund-Schattenkraft.md`.

**Status: 3.1 (slow motion) played; 3.2 (meter with estimated rates) played - meter OK, HUD silhouette not shown;
3.3 (translated meter + HUD trigger) played 2026-10-30 - drain / refill 200/s as in the data, tuning from the
fallback copy; 0.4 (lookup diagnostics, Lara conditions) played 2026-10-31 (test A); 0.5 (TU states) built
2026-10-31, not yet played; 0.9 (TU tick gates, adrenaline look) played 2026-11-02 (test 50k: power OK, screen black /
white-black with the look); 0.10 (look screen-effect report / switch, with the data fix tree `dlc_test50l_look`) built
2026-11-03, not played; 0.11 (GlobalParams[7], state 2102, meter interface v2) built 2026-11-03, not played; 0.12
(meter interface v3, InstanceParams[1] in cinematics) built 2026-11-03, played in the runs of 2026-11-03 (state 2102
never registered); 0.13 (state 2102 next to TruDataGuard) built 2026-11-04, not played; 0.14 (loop sound, movement
events, camera flag, strike look - four switches, all default off) built 2026-11-04, not played; 0.15 (the TU's
player cloth time step, `[Cloth] TuTimeStep`, default off) built 2026-11-06, not played; 0.16 (crash fix: the meter
ticks only with a player in a level) built 2026-11-06, played 2026-11-06 evening (power OK; TruMenu's quick bar
LB / RB started it); 0.17 (LB / RB only as the game gets them, `[ShadowPower] MenuInput`) built 2026-11-06, played
2026-11-07 14:44 / 14:53 (bar LB / RB suppressed); 0.18 (K11: no retail adrenaline tick / bar in doppelganger mode,
`[Adrenaline] Translate`) built 2026-11-07, played 2026-11-07 from 15:02; 0.19 (TruMenu's `TruMenuPadBlock` instead
of the pad-chain re-wrap) built 2026-11-07, not played; 0.20 (`[Look] CameraFlag` default 1 = TU, the PC reader of
the camera bit found) built 2026-11-07, installed, ran in the sessions of 2026-11-09 (log; its TO TEST rows not
reported); 0.21 (time-scale request slot 6: gamebase natives 23 / 24 as the TU, `[TimeScale] TranslateSlot6`) built
2026-11-10, not installed, not played.** Not covered: the
meter's one-shot sounds of refill / drain (0x7c..0x86), rock veins (TruRockVein.asi), the shadow strike target states
and the combat conditions (0.5 gaps below; TruShadowCombat.asi).

## 0.21: time-scale request slot 6 - the gamebase natives 23 / 24 as the TU (X23, 2026-11-10)

Build `work\asi\power021`; byte pre-checks `work\asi\power021\prechecks_v21.txt` (5 checks, 0 mismatches against
`data\pc\tru.exe` and the installed `tru.exe`, both md5 `5560abac...`). Workspace docs `Befund-X23-Kraftlauf-0911.md`
(the slot writers) and `Befund-PC-Test-0911-Abend.md` rows 5 / 5b (the goo drip).

* **TU:** the request selector 0x823d7520 reads 7 slots {player, world} at meter +0x40; slot 6 (+0x70 / +0x74) is
  written only by the TU versions of the **gamebase natives 23 / 24** (generalbank script 55, f23 @0x3f8 / f24
  @0x414; binder 0x824a28c0 stores them at +0x298 / +0x2b4 = entries 23 / 24 - its retail partner is 0x8249ced0 with
  0x8249dac8 / 0x8249db18, on the PC tru+0x3b44a0 with tru+0x397cf0 / tru+0x397d10). Arguments args[0] = target,
  args[1] = seconds. **0x824a3238 (23):** player state `[0x829892b0]` != 0, tuning lookup 0x82415518 != 0,
  `gameTracker+0x1244` != 0 and meter `+0x508` != 0 -> `stfs args[0], meter+0x70` (0x824a3280), selector, return;
  else the retail body: world ramp 0x827754cc = {target, seconds x 1000, current world scale, now}. **0x824a32f0
  (24):** the same with `meter+0x74` (0x824a3338) / the player ramp 0x827754ac. The selector takes slot +0 as the
  PLAYER and +4 as the WORLD value (ramps 0x827754ac / 0x827754cc) - so in doppelganger mode **native 23 requests the
  player scale and native 24 the world scale**, crossed against their retail meaning. The duration is not used there
  (the selector ramps in 33 ms). A value <= 0 empties the slot (threshold 0.0): a script clears slot 6 by calling the
  native with 0 or a negative value. No other TU code stores to meter +0x70 / +0x74; the meter init 0x823d7700 does not
  touch the list. Neither native looks at speed, state or input.
* **Callers (data):** `tools/script_ref_find.py 55 0x3f8,0x414` over the 268 DRMs of the B270 kit: only script 205
  f1 (Lara's class, vtable slot 55, debug text "Heads up!!!": `f24(p0, p8)`, `f23(p4 x p0, p8)`, members +0x24 / +0x20
  / +0x1c) in every DLC level / player file, and DLC 1 script 3583 (dlc_caverns). No DLC script refers to the
  prototype of 205 f1 (`script_ref_find.py 205 0x123c`: 0 hits) - inside the DLC data nothing calls it. Its partners
  f2 / f3 ("You Failed" / "Success") call gamebase f2 / f1, which write the current scales directly (TU 0x824a30d0 /
  0x824a30b8, unchanged by the TU) - not slot 6.
* **PC evidence (2026-11-09 evening, TruMenu 0.22.11 counts every call of SetWorldTimeScale / SetPlayerTimeScale with
  its caller module):** 372 calls, all from TruShadowPower.asi, none from tru.exe - so no script ran gamebase 23 / 24
  in that session, the goo-drip runs 20:57:51 and 20:59:15 included. Slot 6 has therefore **probably no part in the
  goo-drip difference** (Xbox world 1.00 while running); the Xbox log of 18:06 also shows the meter standing still at
  893.5 from 02.14 to 02.70 while the world scale jumps to 1.00, and draining at ~200 / s afterwards - another
  mechanism, open. 0.21 is the translation nevertheless (the TU path exists), and its log lines settle it live.
* **Port:** `[TimeScale] TranslateSlot6=1` (default): tru+0x397cf0 / tru+0x397d10 start with a 5-byte jump to
  Native23Stub / Native24Stub. They make the TU's tests (player state `[0xfadb58]`, `FindTuning` = the tick's tuning
  lookup incl. `[Meter] Fallback`, byte `+0x1244`; the plugin's meter always exists) and write
  `request[6][0]` (23) / `request[6][1]` (24), then `Selector()`; otherwise the game's own body runs through a
  trampoline (its first 7 bytes, relocation-free, then back), so the ramp is set exactly as before (and TruMenu's
  counter still names tru.exe as the caller). A new game tracker re-initialises the meter, slot 6 included. Read
  again at run time at most once per second (only when hooked at the start); switching it off empties a set slot 6
  (plugin rule).
* **Log:** one line per slot-6 change (`0.21 slot 6: gamebase native 24 (script value ...) in doppelganger mode ->
  slot 6 WORLD (meter +0x74) -1.000 -> 1.000 (TU 0x824a3338) - selector: player ..., world ...`), the first 50
  retail-path calls per native (`-> game body, ramp set directly - not in doppelganger mode ...`), the rest at
  LogLevel 2. TruMenu's `fight.trace` request column (`TruShadowPowerMeterApi` requests) shows slot 6 as `6:<player>/<world>` (e.g. `6:-/1.00`).
* New checks (all must match, else `0.21 slot 6: <check> does not match - natives 23 / 24 left to the game`): both
  native bodies (32 bytes each, incl. the call to the setter), the binder lines tru+0x3b4548 (entries 0x17 / 0x18),
  both setters.

| # | TO TEST 0.21 (DLC 2, sample ini) | expected |
|---|---|---|
| 1 | load | `TruShadowPower 0.21 loaded (... 0.21: time-scale slot 6 1)`, `0.21 slot 6: gamebase natives 23 / 24 (tru+0x397cf0 / tru+0x397d10) -> plugin ...`, no "does not match" |
| 2 | goo drip (end level) with the power, running | world scale while running (TruMenu `fight.trace`: `time_scale`, `pc_ramp_last`, request column): if a `0.21 slot 6:` line comes, slot 6 decides it (Xbox: world 1.00); if none comes (as on 2026-11-09), slot 6 is not the mechanism - report the time of the run |
| 3 | main game / DLC 1 (a "Heads up" slow motion, if one is known) | `0.21 slot 6: gamebase native 24 / 23 ... -> game body ... not in doppelganger mode`, slow motion as before |
| 4 | `[TimeScale] TranslateSlot6=0` while running | `0.21 switch: [TimeScale] TranslateSlot6 1 -> 0 ...`; natives 23 / 24 = PC |

## 0.20: the camera flag of the start as the TU (P5b, 2026-11-07)

Build `work\asi\v20`; byte pre-checks `work\asi\v20\prechecks_v20.txt` (9 checks, 0 mismatches against the installed
`tru.exe` md5 `5560abac...`; the lists of v09..v19 still 0 mismatches). Only the default and the check list change - the
call itself is the 0.14 code.

* **TU:** the power's Start 0x823d7f00..0x823d7f14 calls `(*0x82efc780)->vtbl[0xa4]` = 0x822a9e58, camera manager
  `+0x7c |= 2`. All TU sites of bit 2 (static manager object, found with `work\p5_0711\cam_slot_static_scan.py`): set
  in Start 0x823d7f0c and in the main-game strike look 0x823e0308 (site 0x823e0514), cleared only by its off
  0x823e07e8 (site 0x823e0904) - neither runs in doppelganger mode (the TU switch 0x8240a430 sends anim events 5 / 4
  to 0x823d8a80 / 0x823d9050, which neither set nor clear it) - and tested only at **0x822a9a7c** (vtbl[0xac]) in
  0x822a9888 (= retail 0x822ac840).
* **PC reader found** (the 0.14 search looked for `call [reg+0xac]`; the PC calls `mov eax, [edx+0xac]; call eax`):
  **tru+0x1e5e8e** in tru+0x1e5bc0 - getter tru+0x1e7770, vtbl[0xac] = tru+0x1eb220 (`[+0x80] >> 1 & 1`), then the
  second curve set `+0x9c` / `+0xe8` of the camera's tuning object when the bit is set, else `+0x4` / `+0x50`, each
  through tru+0x1f20a0 - the same code as TU 0x822a9a7c..0x822a9abc (`addi r3, r30, 0x9c` / `0xe8` vs `4` / `0x50`,
  `bl 0x822b6840`). So on the PC the bit does what it does on the Xbox.
* **Lifetime:** the camera reset tru+0x1edf50 (vtable 0x855ae4 slot 0x20, tail call of the camera init tru+0x1f2440
  from tru+0x1d4318 / tru+0x1de18a / tru+0x32249c) writes `+0x80 = 0`; a second init path (store at tru+0x1f3c48) too.
  So the bit lives from the first power start until the next camera reset (level / player init; whether the TU's reset
  is the same was not diffed here) - matching the Xenia snapshots (0 before the first power, 2 after).
* **Remaining difference (not this switch):** with `[Look] StrikeLook=0` (default) a PC strike in doppelganger mode
  runs the retail look tru+0x315020 / tru+0x318ea0, which sets and **clears** the bit; the TU never clears it there.
  `StrikeLook=1` routes both to the TU translation (no camera call), as the TU.
* New checks (all must match, else `camera flag: <check> does not match - off`): vtable slot 0xac = tru+0x1eb220
  (`8b8180000000 d1e8 2401 c3`), the reader tru+0x1e5e8e (40 bytes incl. both curve offsets); the 0.14 checks stay.

| # | TO TEST 0.20 (DLC 2, sample ini) | expected |
|---|---|---|
| 1 | load | `TruShadowPower 0.20 loaded (... camera flag 1 ...)`, `camera flag: [Look] CameraFlag=1 - Start calls ... reader tru+0x1e5e8e ... checked` |
| 2 | hold RB once (power on) | `camera flag: TU 0x823d7f14 ... +0x80 0x........ -> 0x........ (bit 2 added), first time - the camera reader ... second curve set ...`; describe the camera (distance / follow speed) before and after the first power use |
| 3 | release, power again | no further line at LogLevel 1 (LogLevel 2: one per start, value stays) |
| 4 | death / reload or level change, then the power | after the reload `+0x80` starts without bit 2 again (`before` without 2 on the next start at LogLevel 2) |
| 5 | `[Look] CameraFlag=0` | no `camera flag` lines (= 0.19) |

## 0.19: TruMenuPadBlock instead of the re-wrap (2026-11-07)

Project doc `Befund-Padkette-StartView-0711.md`. Build `work\asi\v19`, no new byte check (`prechecks_v19.txt` = the
0.17 table `kPadPollChecks`, unchanged).

* The 0.17 re-wrap (taking the pad pointer over TruMenu's hook, and over TruLink's while innermost) is gone: the hook
  thread follows the project rule again (hook once, re-hook only when the slot points into xinput again); a foreign
  hook that took the slot over is left in place with one line `0.19 pad chain: pad pointer now 0x... (TruMenu.asi) -
  left in place ...`. A call back into the plugin goes to XInputGetState (as 0.16).
* `[ShadowPower] MenuInput=1`: the hook thread resolves TruMenu.asi's export **`TruMenuPadBlock(pad)`** (TruMenu 0.21.1
  or later; `0.19 menu input: TruMenu.asi's TruMenuPadBlock at 0x... - ...`). GameButtons: the game's view = the pad
  after the inner hooks minus the export's mask; the second XInputGetState read (same packet number) stays, so a button
  the pad holds but the game does not get is still ignored until released - in either order (this plugin inside or
  outside TruMenu). Without the export (older TruMenu) only the second read is left (one log line; then the quick bar's
  LB / RB count again when TruMenu sits outside this plugin).
* Why: the live case 2026-11-07 14:55 (View + Start opened the game's pause menu) was not caused by the re-wrap (it
  did not happen in that run) but by TruLink's re-entry breaker after an item of TruMenu polled the pad (TruMenu
  0.21.2 is the fix there). With the export this plugin no longer needs a place in the chain. Model `padblock` in
  `tools\trumenu_quick_check.py`.

| # | TO TEST 0.19 (DLC 2, with TruMenu 0.21.2) | expected |
|---|---|---|
| 1 | load | `TruShadowPower 0.19 loaded`, `0.19 menu input: TruMenu.asi's TruMenuPadBlock at 0x...`, no `0.17 pad chain: ... wrapped it once more` |
| 2 | quick bar, LB / RB page switches | no `shadow power ON`; `pad input suppressed` / `resumed` pairs |
| 3 | RB held through the bar close | nothing until RB was released once |
| 4 | RB normally | power on / off as before |

## 0.18: K11 - no retail adrenaline in doppelganger mode, as the TU (2026-11-07)

Project doc `Befund-TU-K9-K11-0711.md` (K11 in `Befund-Exe-Stellen-K8-K14-0611.md`). Build `work\asi\v18`.

* `CombatManager::Update` tru+0x3227d0 (once per frame from the player update tru+0x3228ae) = retail 0x823daa58 =
  TU 0x823dca00, same call order on all three. Its 2nd call is the **adrenaline tick** tru+0x318bd0 (TU 0x823defa8;
  R3 start / stop of the retail adrenaline mode, message 0x3b) and its tail call the **adrenaline bar** tru+0x2f2930
  (TU 0x823dfea8), which drains CM+0x3c and writes the HUD value **`[0xfae8d4]` = CM+0x3c / [0xfad764]+0x2d0 on every
  frame** plus HUD group 1. The TU calls both only while `gameTracker+0x1244 == 0` (0x823dca18 / 0x823dcae0); retail
  calls them always. The shadow meter drives the same HUD value (hudscreenmgr native 36) - on the PC the bar
  overwrote this plugin's value after every tick.
* `[Adrenaline] Translate=1` (default **1**, a pure translation of the TU's two tests): the call at tru+0x3227da and the
  tail jump at tru+0x322865 go to two stubs that test the same byte `[[0xfadb58]+0x1244]` (written by TruDlc2Player
  0.4, `[Dlc2Player] TrackerFlag=1`, as the TU's DoppelgangerInit) and return at once when it is set, else continue into
  the game's function. Read again at run time at most once per second. `[Adrenaline] Log=1`: one line per change of the
  decision per site (`0.18 K11: adrenaline bar tru+0x2f2930 (...) SKIPPED - doppelganger mode ...`).
* 6 new byte checks (`work\asi\v18\prechecks_v18.txt`); v09-v17 lists unchanged, 0 mismatches. Imports unchanged.
* The 0.9 stubs inside the tick (adrenaline start tru+0x3189c6 - only caller the tick -, tick tru+0x318bf3 / +0x318c5d /
  +0x318cda) are then no longer reached in doppelganger mode (the TU's own doppelganger branches there are dead code
  for the same reason). They stay patched (outside doppelganger mode they answer the PC bit; with
  `[Adrenaline] Translate=0` or TruDlc2Player `TrackerFlag=0` they are needed again). Still in use: the stop stub
  tru+0x318ad6 (also called from tru+0x1d4864 / tru+0x31eff9), the camera chooser tru+0x1e80a9, condition 1047.

| # | TO TEST 0.18 (DLC 2, TruDlc2Player 0.4 with `TrackerFlag=1`) | expected |
|---|---|---|
| 1 | load, DLC 2 start | `TruShadowPower 0.18 loaded (... 0.18: adrenaline K11 1, log 1)`, `0.18 K11: tru+0x3227da ... -> plugin`, then `0.18 K11: adrenaline tick ... SKIPPED - doppelganger mode` and the same for the bar; no "does not match" |
| 2 | shadow power (RB) on / off, fights | the silhouette follows the meter only (no jumping back to the adrenaline value), drains / refills as before |
| 3 | R3 (also L3 + R3 for TruMenu) in DLC 2 | no retail adrenaline mode (no slow motion / camera of the base game) |
| 4 | main game / DLC 1 | `... runs - not in doppelganger mode`, adrenaline as before |
| 5 | trouble | `[Adrenaline] Translate=0` (PC at once) |

## 0.17: LB / RB only as the game gets them - no power from TruMenu's menus (2026-11-06)

Live 2026-11-06 22:18 (DLC 2): with TruMenu's quick bar open, every LB / RB page switch logged `shadow power ON`
(and OFF ~0.13 s later). Cause: the pad pointer 0x00a02b8c is shared by TruMenu, TruLink and this plugin, each wraps it
once, and the order depends on thread timing. TruMenu's import filter (meant to give the game TruMenu's hook first)
never did so in that day's TruMenu.log - 44 sessions, always `PadHook set on the pointer (late load)` - so TruMenu
often sits **outside** this plugin: `game -> TruMenu -> TruShadowPower -> TruLink -> XInputGetState` (22:18 session).
TruMenu clears LB / RB (quick bar) or hands out a neutral pad (menu, ring) on the way back, after this plugin has read
the real pad; the poll's state buffer lives on its stack (tru+0x84b7c), so nothing is left to read afterwards.

0.17, `[ShadowPower] MenuInput=1` (default; 0 = 0.16):

1. **Outside TruMenu**: when another hook took the slot over this plugin, the hook thread wraps it once more per hook
   generation and owner (`0.17 pad chain: TruMenu.asi (0x...) took the pad pointer over this plugin - wrapped it once
   more ...`): always TruMenu.asi; TruLink.asi only while this plugin itself calls XInputGetState (order TruLink ->
   TruMenu -> TruShadowPower) - TruLink's loop breaker (TruLink calls XInputGetState directly once the plugin it calls
   takes the slot) could otherwise drop TruMenu. The call back into this plugin from inside the chain goes on to the
   function it called before (once per poll; a second one goes to XInputGetState), so every hook still runs once per
   poll. TruMenu re-hooks only when the slot points into xinput again, TruLink leaves foreign hooks in place - no
   ping-pong. Any other owner is left in place with one log line. All six orders of the three plugins end with this
   plugin outside TruMenu:

   | Order before (outer -> inner) | 0.17 | Order after |
   |---|---|---|
   | ShadowPower, TruMenu, TruLink / ShadowPower, TruLink, TruMenu | nothing to do | unchanged |
   | TruMenu, ShadowPower, TruLink (22:18 session) | wrap TruMenu | ShadowPower, TruMenu, (ShadowPower ->) TruLink |
   | TruMenu, TruLink, ShadowPower | wrap TruMenu; TruLink's breaker switches TruLink to XInput | ShadowPower, TruMenu, TruLink |
   | TruLink, ShadowPower, TruMenu | left in place (already outside TruMenu) | unchanged |
   | TruLink, TruMenu, ShadowPower | wrap TruLink (plugin innermost) | ShadowPower, TruLink, TruMenu, (ShadowPower ->) XInput |
2. **Withheld buttons**: after the chain the plugin reads the real pad once more; when both reads carry the same
   packet number, a button the pad holds and the game lacks is withheld until the pad releases it - also after the
   menu / bar closes, so RB held through the close starts nothing until it was released once. With the plugin inside
   TruMenu (TruMenu's filter worked) both views are equal - nothing to withhold, the masked pad already arrives.
3. **Log**: `pad input suppressed: buttons 0x0200 held on the pad but not passed to the game (TruMenu menu / ring /
   quick bar) - ...` once per burst, `pad input resumed: suppressed buttons 0x... released after T ms (N polls) - they
   count again` at its end (first 64 bursts at LogLevel 1, later at 2); `0.17 menu input: 6 code checks passed ...` at
   load.

Byte pre-checks `work\asi\v17\prechecks_v17.txt` (6, = `kPadPollChecks`): the only writer of the pointer
(tru+0x82505), the per-frame poll (stack buffer, pad index, call, packet number test tru+0x84b95, wButtons read
tru+0x84bc3) and the two other calls through the pointer (tru+0x82613 presence test, tru+0x86204). A mismatch turns
MenuInput off (0.16 behaviour). Everything else - switches, meter, tick, conditions, API v4 - is unchanged.

Limits: the re-wrap runs in the hook thread (about 1 s after the last placement), so the first second after the
pointer is filled is still 0.16; a fourth plugin on the slot is not wrapped. The order-independent fix is a small
TruMenu export (project doc `Befund-TruShadowPower-017-0611.md` section 5) - proposed for the next TruMenu build.

## 0.16: the meter ticks only with a player in a level - crash fix (2026-11-06)

The 15h live run crashed at tru+0x37bdd3 (`mov al,[ecx+0x50d]`, ecx = 0) on the first meter tick after a ring
`level.load` unload: the player state `[0xfadb58]` was already 0, the meter stood at 99.6 %, so Refill -> ShowMeter ->
HUD manager vtbl[3] -> HUD script -> uigamedata f32 (tru+0x3a0db0 -> tru+0x37bd80) read the player state without a
null test (project doc `Befund-15h-Absturz-Finisher-0611.md` section 1). On the TU the tick runs inside Lara's player
update (0x824128a4..0x824128b8): no Lara, no tick. The plugin ticks from the pad poll, and its only gate was the
doppelganger flag, which stays 1 through a teardown.

0.16 mirrors the TU: `MeterTick` returns at once - no refill, no drain, no HUD call, no flag / latch / request change,
no new-tracker re-init (that one runs at the first tick after the skip, before any refill) - while

| # | Test | PC evidence (byte pre-checks `work\asi\v16\prechecks_v16.txt`, 15 checks) | Applies |
|---|---|---|---|
| 1 | player state `[0xfadb58]` == 0 | the faulting reader tru+0x37bdb5 / 0x37bdd3; set tru+0x32247b, cleared (ebx = 0 from tru+0x321ffa) tru+0x322304 | always |
| 2 | player instance `[0xe7f094]` == 0 | GameTracker 0xe7f088 + 0xc, reader tru+0x341764 (TruMenu `InLevel()`) | always |
| 3 | main state `[0xe7ed60]` != 1 | game loop tru+0x1e01ab -> dispatcher tru+0x1e0090, state 1 -> tru+0x1e0050 (level loop); 1 after the level load tru+0x1de9f0, 2 on a mission start tru+0x1dfb83 | code verified |
| 4 | level change pending, byte GameTracker+0xb9 `[0xe7f141]` != 0 | set by the request tru+0x1df88a, tested by GAMELOOP_RequestLevelChangeByName tru+0x1df8d3, cleared by the level load tru+0x1de86c | code verified |

Tests 1 / 2 are plain reads of two globals and always apply; 3 / 4 are TruMenu's `LevelChangePending` /
`SafePauseReason` tests and apply only when their code matches (otherwise one error line; the tick keeps tests 1 / 2).
Second line of defence: **every HUD call** of the plugin (ShowMeter, flag 0x40 on / off, the new-tracker HUD clear,
the strike-look aim) is skipped while `[0xfadb58]` is 0, also when called through the meter interface
(`TruShadowPowerMeterApi` drain). Nothing else changed: all switches (`[Sound] LoopSound`, `[Look] MoveEvents` /
`CameraFlag` / `StrikeLook`, `[Cloth] TuTimeStep`, ...) and the sample .ini are as in 0.15.

**Log lines**: `0.16 tick gate: 15 code checks passed - the meter ticks only with player state [0xfadb58], ...` at load
(or `0.16 tick gate: code at 0x... does not match - main state / level change tests off ...`); per skip burst
`meter tick skipped (no player / level change): <reason> - player state 0x..., player 0x..., main state N,
GameTracker+0xb9 N; meter M, flags 0x... kept (... burst K)` and on resume `meter tick resumed: ... - N ticks skipped
over T ms game clock (last reason: ...)` (the first 64 bursts at LogLevel 1, later ones at 2; a reason change inside a
burst at 2); `HUD call skipped (<what>): no player state [0xfadb58] ...` (first time at 1, then powers of two at 2).
When the game clock advances in the main menu (the tick runs only then), the first such line is a skip with reason
`no player state` - expected.

## 0.15: the TU's player cloth time step - Lara's ponytail in slow motion (2026-11-06)

On the PC the ponytail stretches ("janky", very long) while the shadow power slows the world (world 0.3, Lara 1.2):
the cloth of every instance is stepped with the world-scaled frame time. The title update fixed that in the caller of
the cloth update, and only there (the cloth code itself, PC tru+0x5d680 / 0x5fab0 / 0x601c0, is unchanged in the TU).
`[Cloth] TuTimeStep=1` translates that change; **default 0** = 0.14 behaviour (nothing checked, nothing patched).
Project doc `Befund-F20-Zopf-0611.md` has the evidence; byte pre-checks `work\asi\v15\prechecks_v15.txt` (6 checks,
0 mismatches against the installed exe; the 0.14 list re-run: 36 checks, 0 mismatches). Build `work\asi\v15`.

| | Xbox | PC |
|---|---|---|
| function | TU 0x82278120 (retail 0x8227b220), cdecl(instance); callers 0x822995a8 / 0x82299d88 | tru+0x1bbe70; callers tru+0x1d4688 / tru+0x1dfee1 |
| cloth component | type 14 via 0x82275ab0, update 0x82102e70(component, dt) | component list +0x68 / +0x70, update tru+0x5d680 (thiscall, dt on the stack) |
| retail dt | `lfs f1,0x100(r10)`, r10 = 0x82efb358 | `fld dword [0xe7f188]` at tru+0x1bbec2 |
| TU change 0x822781dc..0x822781f8 | gt = 0x82efb458: `r10 = [gt+0xc]; f1 = [gt+0x100]; if (r26 == r10) f1 /= [gt+0x118]` | `fld [0xe7f188]; if ([esp+4] == [0xe7f094]) fdiv [0xe7f1a0]` |

Field partners (gt = PC 0xe7f088, same offsets): +0xc = 0xe7f094 the player instance, +0x100 = 0xe7f188 the frame
time multiplied by the world scale (tru+0x1da5af / 0x1da5b5), +0x118 = 0xe7f1a0 the world time scale (tru+0x1da595).
r26 is the function's **argument** (0x8227812c `mr r26,r3`), i.e. the instance, not the component; at tru+0x1bbec2
esi / edi are already restored, so the instance is `[esp+4]`. The TU has **no further test** - no gameTracker+0x1244
(doppelganger mode) and no "scale > 0": the player's cloth runs on the unscaled frame time in every level whenever the
world time is scaled (shadow power, base-game slow motion such as script 205). Cross-check only: the upstream B270 exe
patches the same site, but compares `[component+0]` instead of the instance, and adds the +0x1244 and scale > 0 tests
(and a counter) - none of that is in the TU, so the plugin does not do it.

Hook: tru+0x1bbec2, 6 bytes -> `jmp ClothDtStub; nop`, back to tru+0x1bbec8 (`push ecx; mov ecx,eax; fstp [esp];
call tru+0x5d680`); eax (the component) is kept, ecx and the flags are dead there. Checked first: function entry,
the site from tru+0x1bbeb5 to the `ret`, both callers, the world-scale code tru+0x1da595. The site holds a jump on the
upstream B270 exe -> the check fails there and the switch stays off (`site tru+0x1bbec2`).

**Log lines**: `cloth time step: [Cloth] TuTimeStep=1 - tru+0x1bbec2 runs TU 0x822781dc..0x822781f8 ...` (patched),
`cloth time step: first player cloth update with the TU division (dt ... / world scale ... = ...)`, `cloth time
step: world time scaled - player cloth dt ... / world scale 0.300 = ... (update N)` (first update with the world
scale more than 1 % away from 1.0 - a log threshold only), LogLevel 2: `cloth time step: N player cloth updates
divided` at powers of two. `cloth time step: world scale 0 at a player cloth update (N times) - the TU divides anyway`
(LogLevel 0, once). A failed check: `cloth time step: code does not match (<part>) - off`. The report runs in the
per-frame tick of the pad poll, so it needs the plugin's pad hook (as every other part).

**TO TEST (0.15)**

| # | switch | test | what the owner should see / the log |
|---|---|---|---|
| 1 | TuTimeStep=1 | DLC 2, hold RB (shadow power on), run and hit with the power, watch the ponytail | normal length / movement in slow motion; `cloth time step: [Cloth] TuTimeStep=1`, `first player cloth update`, `world time scaled ... world scale 0.300` |
| 2 | TuTimeStep=0 | the same | ponytail stretches as before (comparison); no `cloth time step` lines |

## 0.14: the remaining TU parts of the power, each behind its own switch (2026-11-04)

All four are **off by default** - with the 0.14 sample ini the plugin behaves as 0.13 (nothing checked, nothing
patched). Project doc `Befund-Schattenkraft-0411b.md` has the evidence; byte pre-checks `work\asi\v14\prechecks_v14.txt`
(36 checks, 0 mismatches; the v12 / v13 lists unchanged: 37 / 6, 0 mismatches). Build `work\asi\v14`.

| switch | TU | PC translation |
|---|---|---|
| `[Sound] LoopSound` | meter +0x0 handle (init 0x823d7700: {+0xc = tuning +0x5c, +0x10 weak node}; tick 0x823d7ae0..0x823d7b34: power on -> TU-only 0x82480440, off -> TU-only 0x824805c8) | start = tru+0x193c90 (= TU 0x8223ee58: tru+0x1935d0 on the sound manager [0x8a8100]), position = tru+0x183340 (= 0x82241918), emitter +0x2c / +0x30 / +0x34 = value / start value / value, stop = (emitter +8)->vtbl[0x10](6), weak-node free list [0xcda0c4], pool tru+0x198570; data = tuning +0x5c of object 858 (SoundPlex node -> DTP 22864). The handle is made at the first tick of a tracker generation with object 858 loaded (the PC player init is not hooked) and freed (0x823d7680) with the next tracker |
| `[Look] MoveEvents` | 0x823d77f0 per tick (events 0x84 / 0x83 by \|gameTracker+0x1f0\| against 10.0 and 3000 ms, meter +0x30 / +0x34) and Start's 0x83 when the length is > 10 | PC gameTracker+0x1f0 = the same field: the PC twin tru+0x317eb6 of retail 0x82409660 (switch tru+0x316f30 = retail 0x824077e0, map verified) builds `[0xfadb58] + 0x1f0`. Branches as the TU (unordered compares included); length with sqrtf instead of vrsqrtefp128 + one Newton step |
| `[Look] CameraFlag` | Start: (*0x82efc780)->vtbl[0xa4] = 0x822a9e58 (+0x7c \|= 2) | manager 0xe804f0, vtable 0x855ae4 slot 0xa4 = tru+0x1eb200 (+0x80 \|= 2); slots 0x8c..0xac in the same order on both; the PC retail strike look tru+0x315103 makes the same call |
| `[Look] StrikeLook` | player anim events 5 / 4 in doppelganger mode: 0x823d8a80 / 0x823d9050 instead of the retail 0x823e0308 / 0x823e07e8; Stop calls 0x823d9050 with flag 2 | call sites tru+0x316f6b / tru+0x316f86 (switch tru+0x316f30) go to the plugin: doppelganger mode -> translation, else the PC handlers tru+0x315020 / tru+0x318ea0. Look on: request slot 2 = tuning +0x50 / +0x4c, event 0x7a (tru+0x318780), target from TruShadowCombatStrikeState (handle, count), query 0x188 (tru+0x1b3720, arg = count) -> segment matrix +0x30, aim = TU 0x823e2b98 (point 0: tru+0x30db20; else its tail written out with tru+0x3020e0 / tru+0x2e6a70), second model +0x40 \|= 0x200, strike latch 0, flag 4. Look off: request 2 cleared, event 0x7b, tru+0x2e6ca0, 0x200 cleared on both models, flag 4 cleared |

**Meter interface version 4** (pure append): `void (__cdecl *strikeLookOff)()` = TU 0x823d9050 for the strike tick /
end (TU 0x823d8d18 / 0x823d9210 call it next to their 100 % drain); does nothing unless meter flag 4 is set.

**Log lines** (LogLevel 1 = first time, 2 = every time): `loop sound: handle made`, `loop sound: started (TU
0x8223ee58 ...)`, `loop sound: first stop (TU 0x824805c8 ...)`; `move events: TU 0x823d77f0 runs`, `move events:
speed fell to ... player event 0x84`, `move events: ... player event 0x83`; `camera flag: TU 0x823d7f14 ... +0x80
0x........ -> 0x........`; `strike look: player anim event 5 in doppelganger mode -> TU 0x823d8a80`, `strike look ON
(TU 0x823d8a80 ...)`, `strike look OFF (TU 0x823d9050 ...)`. A failed check: `... code does not match (<part>) - off`.

**TO TEST (0.14)**

| # | switch | test | what the owner should see / the log |
|---|---|---|---|
| 1 | LoopSound=1 | DLC 2, hold RB a few seconds, release | a loop sound while the power runs, gone after release; `loop sound: handle made`, `started`, `first stop` |
| 2 | MoveEvents=1 | power on while running, stop, run again | `move events: speed fell to ... 0x84` on every stop with the power on; 0x83 only by the TU's 3000 ms rule (statically: hardly ever) or at a start while running (`start while moving`) |
| 3 | CameraFlag=1 | power on once | `camera flag: ... +0x80 0x..0 -> 0x..2` (sticky); describe any camera change |
| 4 | StrikeLook=1 + TruShadowCombat `[Strike] Translate=1` | hall02, after the F4 fix: power on, strike at a thrall | `strike look: player anim event 5 ...`, `strike look ON`, condition 1055 -> 1 (LogLevel 2), then `strike look OFF` |

## 0.13: state 2102 next to TruDataGuard.asi (2026-11-04)

In every run of 2026-11-03 the log said `state 2102: camera code does not match - not registered`. The expected bytes
are right (`tools/pe_bytes_check.py` against the clean `tru.exe`: all 5 checks ok). The failing check is the section
lookup **tru+0x14df80** (the camera-settings lookup of TU 0x822bc198): **TruDataGuard.asi** loads first (alphabetical
order) and replaces its first 5 bytes with `E9 <stub>` (TruDataGuard.cpp `WriteJump(kLookup, &LookupStub)`); the
check ran afterwards and saw `e9 ..` instead of `8b 44 24 04 8b`. Since TruDataGuard 0.1 (run 50j) the two were never
installed without each other while TruShadowPower had state 2102 (0.11+).

0.13 accepts the original bytes **or** exactly that patch: `E9` whose target lies in a module named
`TruDataGuard.asi` and the unchanged rest of the function from +5 (`04 85 28 6f c3 00 ..`). The guard stub returns the
same entry for valid ids (State2102 is not one of TruDataGuard's "tests for 0" callers: an invalid id is logged and the
original lookup runs). A failing check now names itself in the log (`camera code does not match (<check>)`). Log on
success with TruDataGuard: `state 2102: section lookup tru+0x14df80 jumps to TruDataGuard.asi (0x........) - accepted`,
then `Lara states: ... 2102 (camera blend to its end ...) added`; in the wall run `state 2102 ... first call`.

Details: docs `Befund-2102-und-Id68f4.md` (project folder).

## 0.12: meter interface v3, the second TU block of 0x82474728 (2026-11-03)

**Meter interface version 3.** Pure append to version 2 (layout of v1 / v2 unchanged): `volatile LONG *gt1280` = the
plugin's TU-only gameTracker+0x1280 (move step count), as requested in docs Befund-Schattenkampf.md section 5 ("Version
3 request"). State 245 writes it (since 0.5), TruShadowCombat's state 244 can write the same variable through the
pointer, condition 1048 reads it (unchanged code, the variable is now `volatile LONG`).

**InstanceParams[1] of the player model (`[Look] CinematicParam`, default 1).** The second block the TU appended to
0x82474728 (0x8247498c..0x82474a24, same gate as GlobalParams[7]: game tracker and object 858's tuning): model =
(instance +0x244)->+0x10[(s8)((+0x244)->+4)->+0x234], `model->vtbl[0x50](1, cinematic ? (1, 0, 0, 0) : (0, 0, 0, 0))`
(cinematic = [0x82efb590] +0xdd and +0x2c != -1). PC layout checked: the same three fields in the PC helpers
(tru+0x1b6abd: `mov eax,[ecx+0x244]; mov edx,[eax+4]; movsx ecx,byte [edx+0x234]; mov edx,[eax+0x10]; mov ecx,
[edx+ecx*4]`); slot 0x50 of `cdc::PCRenderModelInstance` (vtable 0x849764, RTTI) = tru+0xf4f60 = set InstanceParams
[index] (allocates the 0x90-byte block, `[+0x1c + 16 x index] = *vec`); same slot on both platforms: retail 0x8248fe38
(map: verified = PC tru+0x393680) calls vtbl[0x50](0, v) / (1, +0x4a0), the PC twin `call [edx+0x50]` with push 0 /
push 1 + vector pointer. Translation in the 0.11 wrapper after GlobalParams[7]; the cinematic test is PC tru+0x53f00
(the plugin's verified copy of the same test); the model's vtable is checked at run time (else a log line, nothing set).

**Doppelganger default camera (+0x14c) - documented, not patched.** 28 PC sites inline TU 0x822bc198's fallback as
`call tru+0x1d4080; mov eax, [eax+0x144]` (`tools/camera2102.py pcdefaults`), all followed by the settings lookup
tru+0x14df80. What PC [0xe7ee50] +0x14c holds is not proven (the only +0x14c writers near the camera code,
tru+0x1ddba7 / tru+0x1ddc19, write a four-id block +0x140..+0x14c of an object not proven to be [0xe7ee50]); a wrong
id makes the lookup return 0 and some sites dereference it. Not patched; list for a
Xenia comparison in project doc Befund-Look.md section 9.

Byte pre-checks `work\asi\v12\prechecks_v12.txt`: 37 checks, 0 mismatches. Build `work\asi\v12`.

**TO TEST (0.12)**

| # | test | what the owner should see |
|---|---|---|
| 1 | DLC 2 start (intro cutscene, then play) | log "InstanceParams[1] of the player model (TU 0x8247498c) = ..." at the first frame; at LogLevel 2 a line when a cinematic starts / ends; doppelganger look in cutscenes vs gameplay as on the Xbox |
| 2 | with TruShadowCombat 0.2 | TruShadowCombat.log "meter interface found (version 3)"; shadow dash (state 244) then condition 1048 lines in TruShadowPower.log ("steps x 100 = ...") with the dash's step count |
| 3 | `[Look] CinematicParam=0` | no InstanceParams line, everything else as 0.11 |
| 4 | main game | nothing of this (object 858 not loaded) |

## 0.11: GlobalParams[7], state 2102, the meter interface (2026-11-03)

**GlobalParams[7] (`[Look] GlobalParams7`, default 1).** 19 TU pixel shaders (the look 2327, the rock vein 2392, ...)
read GlobalParams[7] (PC c147); no base shader does. Writer found: TU **0x82474728** (= retail 0x8246eff0 = PC
**tru+0x373a70**, called per frame for the player from tru+0x373bf0) sets GlobalParams[0..6] (player position, six bones)
through `(*0x829be0a4)->vtbl[0x84](index, 1, vec)`; the TU appended at 0x824748e4, when the game tracker and the tuning
(0x82415518 = object 858) exist: **GlobalParams[7] = (meter / tuning +0x10, meter / meter +0xc, flags & 1, fade)**
with 0x823d8548 / 0x823d85a8; fade = clamp((clock - meter +0x3c) x 0.03 / tuning +0x60) while the power is on, else
1 - clamp(... / tuning +0x64) (1 when the span is <= 0). PC: the same setter `[0xa1407c]->vtbl[0x84]` = tru+0x107110;
the call tru+0x373bfd goes to a wrapper (`GlobalsWrap`) that runs tru+0x373a70 and then the TU block. The meter's
start time now uses the TU's clock: TU +0x3c = [0x82efb528] = **PC 0xe7f158** (gameTrackerX has one offset between the
platforms: 0x82efb464 / 0x514 / 0x560 / 0x590 = PC 0xe7f094 / 0xf144 / 0xf190 / 0xf1c0); 0.3-0.10 stored 0xe7f15c (no
reader). Not translated: the second appended TU block 0x8247498c (player instance +0x244 -> ...->vtbl[0x50](1,
cinematic ? (1,0,0,0) : 0)).

**State 2102 (`[States] State2102`, default 1).** TU record `{2102, 0x824627b0, 0 x5}` (Lara table, 0x82758c18):
r3 = camera manager 0x82efc780, 0x822ae918: if the Lara camera (+0xb50) is current -> its vtbl[0x80] = TU-only
**0x822c2130**: `+0x1e4 = settings +0xb8 + settings +0xb4` (the camera blend jumps to its end; settings =
0x822bc198(+0x1d0), whose TU fallback uses the defaults +0x14c instead of +0x144 in doppelganger mode). The TU split
this out of the retail slot 0x6c (PC tru+0x202290, body tru+0x202298..0x2022db); the PC vtable 0x85600c has no slot
0x80, so the body is written out: manager 0xe804f0, `+0xb80`, is-current tru+0x1e7fb0, settings tru+0x14df80,
defaults [0xe7ee50]. Added to Lara's state copy only when TruDoppelganger's generic table holds 2102.

**Meter interface `TruShadowPowerMeterApi` (version 2).** `extern "C" const TruShadowPowerMeter *__cdecl
TruShadowPowerMeterApi()` - version 1 exactly as TruShadowCombat's proposal (docs Befund-Schattenkampf.md section 5:
size, version, flags, value, startValue, request[7][2], selector 0x823d7520, drain 0x823d8380 with the meter's tuning);
version 2 appends for a later HUD plugin (larabase natives, Plan-Nacht-Analysen section 2): `float *delay` (+0x10),
`delayStart()` = f70 0x824aa060 (+0x10 = tuning +0x24), `strikeReady()` = f71 0x824aa0a0 (flag 8 and value > tuning
+0x70 x 0.01 x tuning +0x10, game tracker and tuning present), `canStart()` = f72 0x824aa120 (the plugin's CanStart =
0x823d8120, clears flag 0x200 above +0x28), `delayLeft()` = f73 0x824aa150 (max(+0x10, 0)). Game thread only. The
tuning is the meter's own (TU 0x82415518; with `[Meter] Fallback=1` possibly the file copy). Not in the struct: the
meter fields +0x15 / +0x18 / +0x1c / +0x28 / +0x2c the strike would write (not in the proposal).

Byte pre-checks `work\asi\v11\prechecks_v11.txt`: 33 checks, 0 mismatches. Build `work\asi\v11`.

**TO TEST (0.11)**

| # | test | what the owner should see |
|---|---|---|
| 1 | DLC 2 start with tree `dlc_test50l_look` | log "GlobalParams[7] (TU 0x824748e4): first set (...)" and "meter interface: TruShadowPowerMeterApi version 2 exported" |
| 2 | hold RB | the look edges fade in over ~1 s (tuning +0x60 = 25 frames) and out after release; rock vein strip: note whether it changes with the power (TU shader 2392 reads the same vector) |
| 3 | wall run (RB + A at the rock channel) | log "state 2102 (TU 0x822ae918 -> 0x822c2130) first call ..."; the camera settles at once, no jump / flicker |
| 4 | with TruShadowCombat 0.1 | TruShadowCombat.log "TruShadowPower meter interface found (version 2)" |
| 5 | main game | no "GlobalParams[7]" line (object 858 not loaded -> not set), adrenaline unchanged |

## 0.10: the black / white-black screen of the look (2026-11-03)

**Cause (data, not the camera).** The bad picture of tests 50k (screenshots `_64` / `_67`) and the black screen at the
DLC 2 start follow the **power**, not camera mode 0x30 / 0x34: in all three cases the camera was mode 1 when the
picture was taken (the camera log ends in mode 1 while the power is on), and at the DLC 2 start there was no mode 0x30 /
0x34 at all. Start event **0x32** of `doppelganger_casual` fires kind 1 sub 0xb {0xe} = **record 14** of the model
record list (DTP 20134). PC `tru+0x135cc0` turns it into an instance effect of **type 0x85** (global effect list
`[0xae4d00]`); `tru+0x1469a0` draws it every frame: record word 7 = **material 20744** -> `tru+0x146340` ->
`tru+0x13ef30` = a **full-screen quad drawn with material 20744** (colour 0x80576b79, alpha x fade). On the Xbox that
material runs TU pixel shader **2327**: a 13-tap radial blur of the back buffer (s0 / s2), desaturated and tinted
(MaterialParams 0-6), blended in by its mask texture **6619** (black centre, white edges) - the soft / bright look of
`Xenia-TU_DLC2_24`. The converter gave it a **surrogate** (PC lib 2517 = copy of base 405, class D, score 0.13) that
outputs `s0 x InstanceParams.w x .y + s1 x InstanceParams.z` with alpha = MaterialOpacity, and dropped the 7
MaterialParams: the screen shows the mask texture 6619 opaque (white edges, black centre - the exact shape of
screenshot 67) or plain black. Only effects drawn after it (additive eitr, HUD) stay visible.

**Fix (data, tree `work\rebuild\dlc_test50l_look`).** `tools/look_material_fix.py`: TU 2327 translated Xenos -> ps_3_0
(upstream xenos2sm3, constants by name: ScreenExtents c51, MaterialOpacity c98, MaterialParams c100-c106,
GlobalParams[7] c147) as **ShaderLib 2943** (8 slots, slot k = Xbox slot k & 1); **VS 2944** = the material's PC VS 406
(PC twin of base Xbox 350, which TU VS 2328 extends) plus the vertex-colour pass-through of 2328 (the PS reads COLOR0.w,
the fade); material 20744 = Xbox MaterialParams (7 vec4, Xbox layout byte for byte). Applied to all five DRMs that
carry material 20744 (doppelganger_casual and the four DLC 2 thralls - the engine keeps the first loaded copy).

**Plugin 0.10.** After event 0x32 the plugin looks for the player's type-0x85 effect in `[0xae4d00]` (up to 30 frames)
and logs its material and colour ("look screen effect: ..."). `[Look] ScreenEffect=0` removes it with the engine's own
kill `tru+0x12f1c0` - for data without the fix (the rest of the look stays). Five new byte pre-checks
(`work\asi\v10\prechecks_v10.txt`, 22 checks, 0 mismatches).

**Open.** GlobalParams[7] (PC c147) is read by 19 TU shaders (2327, the vein shader 2392, ...), by no base shader; on
the PC `cdc::PCScene` uploads 16 GlobalParams from `+0x49c` (`tru+0x1150e0`, PS c140 / VS c65), zeroed in the
constructor and written by no PC code - the TU writer is not found yet, so 2327 runs with GlobalParams[7].y = 0 (the
offline preview shows the blurred / brightened edges either way). Materials 24356 / 24958 (records 10-13, events not
fired today) have the same surrogate.

**TO TEST (0.10)**

| # | test | what the owner should see |
|---|---|---|
| 1 | tree `dlc_test50l_look` + 0.10, DLC 2 start: hold RB / LB | slow motion; the picture stays visible: centre normal, edges blurred and brighter / blue-grey (like `Xenia-TU_DLC2_24`), no black screen; log "look screen effect: type 0x85 effect of the player, material 20744, colour 0x80576b79" |
| 2 | same, hall02 near thralls, RB + aim | as 1; camera modes 0x34 / 0x30 come and go without a black or white-black picture |
| 3 | old data (50k tree) + 0.10 with `[Look] ScreenEffect=0` | power and slow motion without the full-screen effect, no black screen; log "... - REMOVED ([Look] ScreenEffect=0)" |
| 4 | main game: adrenaline dodge | unchanged |

## 0.9: the power only through the TU path, and the adrenaline look (2026-11-02)

**Tick.** On the Xbox the shadow-power tick 0x823d7a10 is called by the player update 0x824126d8 only when
gameTracker+0x1244 (the doppelganger flag) is set (0x824128a4..0x824128b8). Up to 0.8 the plugin ran it in every level
from the pad poll and without the TU's gates - so the power could start in DLC 1 / the main game and during a
cutscene (live 2026-11-02). 0.9 runs the tick only with `TruDlc2PlayerDoppelganger()` (TruDlc2Player 0.2 clears it
with every new game tracker, as the TU's new tracker does) and translates the gates of 0x823d7a10 / 0x823d7d40:

| TU | PC | effect |
|---|---|---|
| cinematic: [0x82efb590] +0xdd set and +0x2c != -1 (inline) | tru+0x53f00 (same test on [0xe7f1c0]) | active power stops; no start |
| byte 0x829ca6da (= retail 0x829ca5f1) | 0xfae8dd (setter tru+0x37bbf0, called by GAMELOOP tru+0x1de480 = retail 0x8229c530) | active power stops; no start |
| gameTracker+0x628 > 0.0 (health) | gameTracker+0x628 | no start at 0 health |
| 0x82efb514 bit 0 | 0xe7f144 bit 0 (same test in the adrenaline tick tru+0x318bd0 = TU 0x823defa8) | buttons ignored, active power stops |
| bool parameter 0x412 of Lara's current state (gameTracker+0xf10) -> meter flag 0x80 | same (tru+0x383f50 / 0x384c20) | meter blocked while set |
| refused start -> player event 0x80 | tru+0x318780 | sound / effect record of the doppelganger, if any |
| new tracker -> new meter object | TruDlc2PlayerTrackerGeneration() | meter re-initialised per tracker |

What is still not the TU: the buttons. The TU reads LB / RB from the game's input records (+0x1a70 / +0x1b30 & 4 of
[[0x8286dd90]+0x18]->[0], PC [[0xa02b68]+0x18]->[0] - the PC adrenaline tick reads +0x6f0 of the same records as the
TU). No PC code reads +0x1a70 / +0x1b30, so whether the PC fills them is open: by default the pad poll's XInput LB / RB
stays the button source and the log prints the two game records whenever LB / RB changes ("input diagnostic", 12
lines); `[ShadowPower] GameInput=1` reads the game records instead. `[ShadowPower] LegacyPadStart=1` restores the 0.8
tick (every level, no gates). The ControlFlag word [0xfada74] is not tested by the TU tick and therefore not here.

**Adrenaline look ([Look] AdrenalineMode).** The TU's lead for the soft / bright look (docs Befund-TU-Funktionen L9):
0x823d94f8 runs per tick and sets **meter flag 0x40** (0x823d9348: world request slot 3 = tuning +0x38 = 0.1, HUD
0x9000 when player +0x1fc bit 10, event 0x39) while the power is on, the meter is above tuning +0x28, 0x823df8f8(player)
answers 1 (= PC tru+0x2f2800 with the TU's doppelganger branch: only +0x1fc bits 9 / 10, 30, 24 before the shared tail),
the mode [gameTracker+0x500]+0x134 is not 3 and flag 2 is clear; 0x823d9438 clears it (slot 3 empty, HUD &= ~0x9000,
event 0x3a; also from Stop). In doppelganger mode the camera mode chooser (TU 0x822acdd0 = tru+0x1e7fe0, site
tru+0x1e80a9) picks **camera mode 0x34** by meter flag 0x40 instead of player +0x1fc bit 27, and the adrenaline start /
stop / tick (tru+0x3189c0 / tru+0x318ad0 / tru+0x318bd0) and condition 1047 (tru+0x365600) read flag 0x40 (and flag 2
for bit 21) - six naked stubs, all or none. Whether mode 0x34 is the soft / bright look is for the live test. Not
ported: the instance messages 0x82415b50(1) (PC partner unverified), 0x823d77f0 (shadow-strike look group).

**TO TEST (0.9)**

| # | test | what the owner should see |
|---|---|---|
| 1 | DLC 2: hold RB / LB | slow motion + yellow bar as in 0.8; log "doppelganger flag 0 -> 1: shadow-power tick runs" |
| 2 | DLC 2: hold RB during a cutscene / cinematic camera | no slow motion; if it was on: log "shadow power OFF (cinematic)" (LogLevel 2) |
| 3 | DLC 2 -> main menu -> DLC 1 (same session), hold RB | no slow motion, no bar; log "new game tracker ...: meter re-initialised" and "doppelganger flag 1 -> 0 ... does not run" |
| 4 | DLC 2: power on, aim at an enemy / target (meter above 15 %) | log "meter flag 0x40 ON (TU 0x823d9348, first time)" and "camera mode chooser ... mode 0x34 ... (n times)"; the screen may turn soft / bright (camera mode 0x34) - say what it looks like; release: "meter flag 0x40 OFF" |
| 5 | main game: adrenaline dodge (aim + adrenaline button) | unchanged (retail bit 27; no line "adrenaline start ... meter flag 0x40") |
| 6 | DLC 2: LB / RB a few times, then send TruShadowPower.log | "input diagnostic" lines: whether +0x1a70 / +0x1b30 have bit 4 while held - decides GameInput=1 |
| 7 | if 1 fails (no power at all in DLC 2) | set `[ShadowPower] LegacyPadStart=1`, retry, send the log |

## 0.6: condition 1046 (2026-11-01)

Every loop transition of the wall run (chart DTP 20212, records 1477 / 1488 / 1492 / 1493) needs `{2000,1046,1}`.
The TU predicate 0x8246e400 answers, in doppelganger mode (gameTracker+0x1244), the meter flags bit 0 (power active;
no meter object -> 0), else the retail test (player +0x504)->+0x1fc bit 21. PC tru+0x3655c0 has only the retail test.
`Pred1046` (option `[Conditions] Cond1046`, default 1) replaces it with a 5-byte jump; doppelganger mode =
`TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi. Log: "condition 1046: title-update predicate ..." at load,
"condition 1046 (...) is now evaluated: doppelganger 1 -> ..." and at `LogLevel=2` every change. Sample ini unchanged.
Built 2026-11-01 into `work\asi\v06`, not loaded.

## 0.8: the shadow-power look (2026-11-02)

The blurry / bright look of the power is not a post-process call in the TU code: Start 0x823d7d40 and Stop
0x823d7fb8 fire **player events by type** through 0x82418158 (walk of the player object's event list, every record of
that type -> the player's anim-event callback). Start: 0x89, 0x32, (0x83 while moving - not ported), 0x81 (meter
full), 0x87 / 0x88 (above / below tuning +0x70 = 75 % of max); Stop: 0x33, then 0x7e (ran empty) or 0x82. The effects
are data of `doppelganger_casual.drm` (object 857, event list DTP 20172): 0x32 starts instance effects (model +0x18
effect 2 at two bones, model +0x38 record 14), 0x33 stops all of them. The PC has the same walker (retail):
tru+0x318780 `cdecl(instance, type, 0xff, channel 0)`; 0.8 calls it at the TU's places, in the TU's order, after a
byte check of its entry, type compare and callback call (`[Look] Enabled`, default 1). Log: "shadow look: player event
walker tru+0x318780 verified ..." at load, "shadow look on: first start, player events 0x89 0x32 ..." once, and at
`LogLevel=2` every "shadow look on / off: player events ...". Start / Stop also send **message 0x1f4 / 0x1f5** to
every instance whose query function (+0x11c) answers 0x172 (TU 0x823d7f18 / 0x823d8080; PC instance list [0xd98d54],
wake tru+0x1b2de0 = TU 0x8226fe00; `[Look] Messages`, default 1) - the level objects that react to the power;
presumably `dlc_fx_bloom` (object 1038, an animated fx mesh with the states fx_on / fx_off, 3 shader libs, colour
curve tables) is the full-screen look. Not ported: the camera manager call (*0x82efc780)->vtbl[0xa4] (camera +0x7c
|= 2, a sticky flag; PC camera manager not mapped), event 0x83 (needs gameTracker+0x1f0 on PC). Built 2026-11-02 into
`work\asi\v08` (sha256 8e276629...04af5, ini 2cdc7d49...1ac9), not loaded. Events and messages only in doppelganger
mode (`TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi - on the Xbox Start / Stop exist only with the DLC 2 meter
object).

## 0.7: condition 1055 (2026-11-02)

1055 is in no PC table, so the default handler answered TRUE; its only chart use is `{2000,1055,1,NOT}` (second
machine), which therefore never fired on PC. TU 0x8246e488 = the condition template with predicate 0x8246e450:
doppelganger mode -> meter flag 4, else player `+0x1fc` bit 0x20000000. Flag 4 is set only by the shadow look
0x823d8a80 while flag 2 is set, and flag 2 only by 0x823d8978 = state 1014 slot 0 in doppelganger mode (the shadow
strike) - both not ported, so in DLC 2 the translation answers 0 (the TU's answer outside a shadow strike). `Cond1055`
joins the copy of Lara's condition table (option `[Conditions] Cond1055`, default 1; TruDoppelganger.asi must hold 1055
in the generic table - it does). Log: "... 1055 (TU predicate 0x8246e450 ...) added to the link array", first call
"condition 1055 predicate (TU 0x8246e450) first call: doppelganger 1 -> 0 ...", result changes at `LogLevel=2`. Built
2026-11-02 into `work\asi\v07`, not loaded.

## 0.5: title-update states, conditions and activities of Lara

Translated from the TU (project docs `Befund-Schattenkraft.md`, "TU states for Lara"), registered in copies of Lara's
condition / activity / state tables (push operands tru+0x368b82 / +0x368b8e / +0x368b9a) after byte checks of 20 PC
building blocks, the registration code, the table sizes and TruDoppelganger's generic copies (`[States] Enabled`):

| id | Xbox TU | translation (PC parts) |
|---|---|---|
| state 243 | 0x82464180 -> 0x82463eb8 | move Lara to gameTracker+0x1270 in motion mode 1 (state parameters tru+0x383f50 / 0x384c20, frame count tru+0x35f3e0, channel setters tru+0x38d70 / 0x3e400) |
| state 245 | 0x824645d8 / 0x824647d0 | move tuning +0x6c (1896.3) along -(player matrix row +0x10), steps = length / tuning +0x68 (410.87), mode 2 (player 0xe7f094, setter tru+0x38d00); step count kept in the plugin (TU gameTracker+0x1280) |
| state 1018 | 0x82465078 / 0x824651c8 | meter cost from parameters 0x410 / 0x411, refill delay 0x414, world time-scale request 0x413 (slot 5) |
| condition 1048 | 0x8246ece0 | step count x 100 <= animation time of the agent's channel |
| condition 2401 | 0x824702b0 | timed request slot 4 (tuning +0x58 player, +0x54 world) for record-value frames; always false |
| activity 1009 / 1039 | 0x82472788 / 0x82455a38 | player instance +0xc8 = record +4 / empty print stub |
| selector | 0x823d7520 | the 7-slot time-scale request list; Start / Stop use slot 0 |

Not translated (named gaps): states 244, 1017, 1019, 1020, 2102; conditions 1055, 2005, 2006, 2013. Each new handler
logs its first call (LogLevel 1) and, at LogLevel 2, further calls at most twice per second. Build into a separate
folder with `Build-TruAsi.ps1 -OutDir work\asi\v05`, install with `Set-TruShadowPower.ps1 -Install -SourceDir
work\asi\v05`.

## 0.4: the meter conditions of Lara's link array

Lara's state machine has its own condition link array (PC tru+0x368b60 registers table 0x8b2ce8; Xbox TU 0x82473b50).
The TU added 13 conditions there; seven of them only read the meter and are translated here and added to a copy of the
table (the `push` operand at tru+0x368b81 points at the copy; checked bytes of the registration, the template and the
compare function first, and that none of the ids is in the table yet):

| id | Xbox TU | translation |
|---|---|---|
| 1049 / 1050 / 1051 | 0x824703d0 (key must be 20) | meter value (TU meter +8) compared with the record value: equal / >= / <= through the PC's own compare tru+0x383bd0 (= Xbox 0x82487348) |
| 1052 / 1053 / 1054 | same | meter percentage (value / tuning +0x10 x 100, [0x8207d53c]) the same way |
| 1056 | 0x8246e528 = template 0x82487718 with predicate 0x8246e498 | PC template tru+0x382d70 (cache per agent frame, 0 / 1 / falling / rising edge) with the predicate "percentage >= tuning +0x70 x 0.01 and power active" |

The registration loop takes the node of a new id from the generic registry; an id that is in neither registry makes
it read address 0 (tru+0x385265) - so the plugin registers only if the generic builder's table (push operand
tru+0x387343) is `TruDoppelganger.asi`'s copy and holds all seven ids; otherwise it logs why and leaves Lara's table
alone. Not translated (named gaps): 1048 (gameTracker+0x1280 x 100 vs an animation value),
1055 (meter flag 4 - no TU writer found yet), 2005 / 2006 / 2013 (shadow-combat targets), 2401 (timed time-scale
request), activity 1009, the TU states. The DLC 2 chart uses 1049-1056 in the shadow-combat transitions (e.g. "meter
at least 60 %" before a shadow strike). Option `[Conditions] Enabled`.

## Translation

| Xbox TU function | plugin | PC parts used |
|---|---|---|
| `0x823d7700` meter init (value 1000) | `MeterInit` | - |
| `0x823d7a10` per-frame tick (button latch, drain / refill, stop when empty) | `MeterTick` | frame time `0xe7f190` |
| `0x823d8120` may start (after "empty" only above tuning +0x28) | `CanStart` | - |
| `0x823d7d40` start: request player = tuning +0x40, world = tuning +0x3c | `StartPower` | `SetPlayerTimeScale` / `SetWorldTimeScale`, 33 ms |
| `0x823d7fb8` stop: request cleared (both 1.0) | `StopPower` | same setters |
| `0x824a3238` / `0x824a32f0` gamebase natives 23 / 24: in doppelganger mode request slot 6 (+0x70 player / +0x74 world) + selector, else the retail ramp (0.21) | `Slot6Native` | tru+0x397cf0 / tru+0x397d10 (jump + trampoline) |
| `0x823d81a0` refill: tuning +0x18 per second (+0x20 while a delay runs, +0x1c in another player state), clamp to max +0x10 | `Refill` | HUD below |
| `0x823d8380` drain by frame time x 1/30 x tuning +0x14, clamp 0..max | `Drain` | HUD below |
| `0x82415518` tuning = data of the extension instance | `FindTuning` | object table `0xdb7400`, object 858 |
| HUD in refill / drain: `0x829ca6cc = value / max; 0x829ca724 \|= 2; (*0x829ca720)->vtbl[0xc]()` | `ShowMeter` | `0xfae8d4`, `tru+0x37d9d0(1)`, `tru+0x37da70` |

The HUD trigger is the same one the PC breath code uses under water (`tru+0x2f2905..0x2f292d`): fraction into
`0x00fae8d4` (read by `hudscreenmgr` native 36), display group 1 requested in the bit mask `0x00fae924`
(`tru+0x37d9d0`), then the HUD manager `*0x00fae920` is told (`tru+0x37da70`, its vtable slot 3). The HUD script
(generalbank script 37) polls the group bit (native 7) and shows the silhouette; the TU does not touch the breath-style
flag `0x00fae8af` (native 38), so neither does the plugin (0.2 set it - removed).

Tuning: the TU spawns an instance of the object `player_tru_dlc2_extension` (id 858) and reads its data (u16 type 60):
max +0x10 = 1000, drain +0x14 = 200/s, refill +0x18 = 200/s, +0x1c = 400/s, +0x20 = 75/s, restart above +0x28 = 150,
+0x2c = 300, world +0x3c = 0.3, player +0x40 = 1.2 (values of the converted file). The plugin finds the loaded object in
the PC object table (`0xdb7400`, 0xcc entries of 0x24 bytes, the same layout as the Xbox's `0x82979280`) and makes the
TU's own checks (state loaded, object +0x5c data and +0x60 set, type 60). If the object is not loaded it uses a copy of
the file values (`Fallback=1`, logged as FALLBACK) or no power at all (`Fallback=0`, as the Xbox).
In the 0.3 test (2026-10-30) the lookup failed; 0.3.1 (same behaviour) logs which check stopped it ("id 858 not in the
table", "entry state is not 2", ..., with entry / object / data addresses) and once the list of loaded table entries
(id / state), so the next test shows where the PC keeps the object - or that it is not loaded at all.

Frame time: the PC frame update stores the unscaled frame time in 30 fps units into `0x00e7f190` (us / 33333.33, the
same constants as the Xbox's `0x82efb560`); the tick runs once per advance of the game clock `0x00e7f15c`.

At load the plugin checks the image base and the bytes at all used code addresses; on a mismatch of the pad,
time-scale or frame-time code it hooks nothing, of the HUD code it runs without the bar, of the object table it uses
only the fallback; the reason is logged. The installed game ships the **Ultimate ASI Loader** as `binkw32.dll`; it loads
every `*.asi` next to `tru.exe`.

## Options (`TruShadowPower.ini` next to the `.asi`, optional)

| Section / key | Default | Meaning |
|---|---|---|
| `[ShadowPower] Enabled` | 1 | 0 = load but hook nothing |
| `[ShadowPower] LogLevel` | 1 | 0 errors, 1 info (incl. the tuning values in use), 2 every power on / off, 3 debug |
| `[ShadowPower] Buttons` | 768 | XInput mask: 256 LB, 512 RB, 768 either (Xbox) |
| `[Meter] HudBar` | 1 | feed the HUD silhouette; 0 = no HUD writes |
| `[Meter] Fallback` | 1 | 1 = file values when object 858 is not loaded; 0 = no power then |
| `[ShadowPower] LegacyPadStart` | 0 | 0.9: 1 = the 0.8 tick (every level, no doppelganger / cinematic gates) |
| `[ShadowPower] GameInput` | 0 | 0.9: 1 = LB / RB from the game's input records +0x1a70 / +0x1b30 & 4 (the TU's source; unproven on PC) |
| `[ShadowPower] MenuInput` | 1 | 0.17: LB / RB only as the game gets them (a button TruMenu withholds is ignored until released; 0.19: from TruMenu's `TruMenuPadBlock` + a second pad read, no re-wrap of the pad chain); 0 = 0.16 |
| `[Conditions] Enabled / Cond1046 / Cond1055` | 1 | see 0.4 / 0.6 / 0.7 |
| `[States] Enabled` | 1 | see 0.5 |
| `[Look] Enabled / Messages` | 1 | see 0.8; Enabled=0 also turns AdrenalineMode off |
| `[Look] AdrenalineMode` | 1 | 0.9: TU meter flag 0x40 (0x823d94f8 group) + doppelganger branches of camera mode chooser (mode 0x34), adrenaline start / stop / tick, condition 1047 |
| `[Look] ScreenEffect / GlobalParams7 / CinematicParam` | 1 | see 0.10 / 0.11 / 0.12 |
| `[States] State2102` | 1 | see 0.11 |
| `[Sound] LoopSound` | 0 | 0.14: the TU's looping sound of the power |
| `[Look] MoveEvents / StrikeLook` | 0 | 0.14: movement events 0x83 / 0x84, the shadow-strike look |
| `[Look] CameraFlag` | 1 | 0.14: camera flag of Start (camera +0x80 \|= 2 -> second camera curve set, reader tru+0x1e5e8e); 0.20: default 1 = TU (0.14-0.19: 0) |
| `[Cloth] TuTimeStep` | 0 | 0.15: the TU's player cloth time step (TU 0x82278120): the ponytail gets the frame time / world scale, so it keeps real time in slow motion |
| `[Adrenaline] Translate` | 1 | 0.18 (K11): CombatManager::Update skips the adrenaline tick tru+0x318bd0 and bar tru+0x2f2930 while gameTracker+0x1244 is set (TU 0x823dca00); 0 = PC; read again at run time (<= 1 / s) |
| `[Adrenaline] Log` | 1 | 0.18: one line per change of the K11 decision per site |
| `[TimeScale] TranslateSlot6` | 1 | 0.21 (X23): gamebase natives 23 / 24 in doppelganger mode -> time-scale request slot 6 (23 player, 24 world, crossed as TU 0x824a3238 / 0x824a32f0), else the game's body; 0 = PC; read again at run time (<= 1 / s, only if 1 at the start) |

The 0.2 options `WorldScale`, `PlayerScale`, `RampSeconds`, `[Meter] Enabled`, `DrainSeconds`, `RefillSeconds`,
`RefillDelay`, `MinStart` are gone - those values now come from the data / the TU constants.

## Build, install, remove (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Verbose              # Visual Studio 2022 x86 toolchain -> work\asi\TruShadowPower.asi
.\scripts\windows\Set-TruShadowPower.ps1 -Install        # copies .asi + .ini next to tru.exe (game closed); updates our earlier builds
.\scripts\windows\Set-TruShadowPower.ps1 -Remove         # removes them again (only if they are a build of ours)
```

No external libraries; static runtime (`/MT`), imports only `KERNEL32.dll`. License: MIT, as the repository.
