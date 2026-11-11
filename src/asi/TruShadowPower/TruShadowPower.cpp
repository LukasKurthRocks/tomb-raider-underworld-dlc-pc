// TruShadowPower.asi - DLC 2 "Lara's Shadow" shadow power (slow motion + meter) for the PC tru.exe (Steam, image base
// 0x400000).
//
// The Xbox title update (TU) gives Lara the Doppelgaenger's power: while LB or RB is held the world slows down, a meter
// drains, and the HUD shows it as the second silhouette. The PC exe never got that code, but it has the engine parts
// the TU drives (docs/WINDOWS_REBUILD.md finding 43). This plugin is a function-by-function TRANSLATION of the TU's
// meter code (decompiled from the TU memory image, see docs/Befund-Schattenkraft.md "ASI step 3.3"):
//
//   Xbox TU                       here                PC engine parts used
//   0x823d7700 meter init         MeterInit           -
//   0x823d7a10 per-frame tick     MeterTick           frame time 0xe7f190 (= Xbox 0x82efb560, unscaled, 30 fps units)
//   0x823d8120 may start?         CanStart            -
//   0x823d7d40 start              StartPower          SetPlayerTimeScale / SetWorldTimeScale (the TU's selector
//   0x823d7fb8 stop               StopPower             0x823d7520 writes the same ramps, 33 ms)
//   0x823d81a0 refill             Refill              HUD: 0xfae8d4 + display group 1 (tru+0x37d9d0, tru+0x37da70)
//   0x823d8380 drain              Drain               HUD as above
//   0x82415518 tuning lookup      FindTuning          object table 0xdb7400 (= Xbox 0x82979280), object 858
//
// The rates and scales come from the same data the Xbox reads: the tuning struct (u16 type 60) of the object
// player_tru_dlc2_extension (id 858), offsets +0x10 max .. +0x70 as the TU uses them. Parts of the TU functions that
// depend on systems not ported yet (sounds, the blur effect, instance messages, cinematic / zone checks) are left out
// and named at their place - see the doc for the full list.
//
// Hooks: the per-frame pad poll (tru+0x84b82, call dword ptr [0x00a02b8c] = XInputGetState) is redirected to a wrapper
// that runs the tick on the game thread, once per game frame. Every address is checked against the expected bytes
// first; on a mismatch the affected part stays off and the reason is logged. Loaded by the Ultimate ASI Loader
// (binkw32.dll of the installed game). Options: TruShadowPower.ini next to the .asi (see README.md).
//
// 0.6 (2026-11-01, docs Befund-Felsrinne "Wall run: orientation, magnet and duration"): condition 1046 holds every loop
// transition of the wall run (chart DTP 20212 records 1477 / 1488 / 1492 / 1493: `{2000,1046,1}`, exits on 0). Its TU
// predicate 0x8246e400 reads, in doppelganger mode (gameTracker+0x1244), the meter object's flags bit 0 (power active;
// meter object +0x508 null -> 0), else the retail test (player +0x504)->+0x1fc bit 21. PC tru+0x3655c0 has only the
// retail test. Pred1046 replaces it (5-byte jump at its entry): doppelganger mode = TruDlc2Player's flag
// (TruDlc2PlayerDoppelganger, the TU's +0x1244), meter = this plugin's translation of the meter object.
//
// 0.7 (2026-11-02, docs Befund-Felsrinne "Condition 528 and the missing list"): condition 1055 was answered TRUE by the
// PC default handler (the id is in no PC table). Its only chart use is `{2000,1055,1,NOT}` in a transition of the second
// player machine, so the PC could never take it. TU 0x8246e488 = the template with predicate 0x8246e450: doppelganger
// mode -> meter flags bit 4, else (player)->+0x1fc bit 0x20000000 (PC writes that bit too: tru+0x315129). Meter flag 4
// is set only by the shadow look 0x823d8a80 (player anim event 5), and only while flag 2 is set; flag 2 is set only by
// 0x823d8978, the TU branch of state 1014 slot 0 (shadow strike) - both not ported, so in DLC 2 the translation answers
// 0, which is the TU's answer outside a shadow strike. Cond1055 joins the copy of Lara's condition table (option
// [Conditions] Cond1055).
//
// 0.8 (2026-11-02, docs Befund-Schattenkraft "Shadow-power look (title update) - translation"): the look of the power.
// No TU function of the meter group calls a post-process API; Start 0x823d7d40 and Stop 0x823d7fb8 fire PLAYER EVENTS
// by type through 0x82418158 (walk of the player object's event list, records of that type -> the player's anim-event
// callback) - on: 0x89, 0x32, (0x83 moving), 0x81 (meter full), 0x87 / 0x88 (above / below tuning +0x70 % of max);
// off: 0x33, then 0x7e (ran empty) or 0x82. The records are data of doppelganger_casual (object 857, DTP 20172):
// 0x32 starts the instance effects (model +0x18 effect 2 at two bones, model +0x38 record 14 as instance effect),
// 0x33 stops all of them. The PC has the walker with the same body: tru+0x318780 cdecl(instance, type, 0xff, channel
// 0). FireEvent calls it at the TU's places, in the TU's order ([Look] Enabled). Start / Stop also send message
// 0x1f4 / 0x1f5 to every instance whose query +0x11c answers 0x172 (PC instance list [0xd98d54], wake tru+0x1b2de0)
// - the level objects that react to the power, e.g. presumably dlc_fx_bloom (object 1038, states fx_on / fx_off)
// ([Look] Messages).
//
// 0.9 (2026-11-02, docs Befund-TU-Funktionen "Plugins 0.9"): the power only through the TU path, and the TU's
// adrenaline look.
//   * Tick = TU 0x823d7a10 as the TU calls it: the player update 0x824126d8 runs it only when gameTracker+0x1244 is set
//     (0x824128a4..0x824128b8) - so the tick (and with it every start) now needs TruDlc2Player's flag, which 0.2 clears
//     with every new tracker. The TU's own gates are translated: a running cinematic (TU inline test of
//     [0x82efb590] +0xdd / +0x2c = PC tru+0x53f00 on [0xe7f1c0]) or the byte 0x829ca6da (= retail 0x829ca5f1 = PC
//     0xfae8dd, set by tru+0x37bbf0 from GAMELOOP tru+0x1de480) stop the power and refuse a start; the start also needs
//     gameTracker+0x628 (health) > 0; the buttons count only while gameTrackerX+0xbc bit 0 (TU 0x82efb514 = PC
//     0xe7f144, the same test in the adrenaline tick TU 0x823defa8 = tru+0x318bd0) is clear, and that bit also stops
//     an active power; flag 0x80 = bool parameter 0x412 of Lara's current state (state machine gameTracker+0xf10)
//     blocks the meter; a refused start fires player event 0x80. A new tracker re-initialises the meter (TU: the meter
//     object belongs to the player data built by the player init). The TU reads LB / RB from the game's input records
//     (+0x1a70 / +0x1b30 & 4 of [[0x8286dd90]+0x18]->[0] = PC [[0xa02b68]+0x18]->[0]); no PC code reads these two
//     records, so the XInput state of the pad poll stays the button source by default ([ShadowPower] GameInput=1 reads
//     the game records instead; the log shows both while LB / RB is held). [ShadowPower] LegacyPadStart=1 restores the
//     0.8 tick (no doppelganger / cinematic gates).
//   * Look = TU adrenaline camera: 0x823d94f8 per tick (power on, meter > tuning +0x28, 0x823df8f8(player) = PC
//     tru+0x2f2800 with the TU's doppelganger branch, mode [gameTracker+0x500]+0x134 != 3, not flag 2) sets meter flag
//     0x40 through 0x823d9348 (world request slot 3 = tuning +0x38, HUD 0x9000 when player +0x1fc bit 10, event 0x39)
//     and clears it through 0x823d9438 (slot 3 empty, HUD &= ~0x9000, event 0x3a; also from Stop). In doppelganger mode
//     the TU's camera mode chooser (0x822acdd0 = tru+0x1e7fe0, site tru+0x1e80a9) picks mode 0x34 by meter flag 0x40
//     instead of player +0x1fc bit 27, and the adrenaline start / stop / tick (0x823ded18 / 0x823dee58 / 0x823defa8 =
//     tru+0x3189c0 / tru+0x318ad0 / tru+0x318bd0) read flag 0x40 for "active" and meter flag 2 for +0x1fc bit 21;
//     condition 1047 (TU predicate 0x8246e538 = PC tru+0x365600) the same. [Look] AdrenalineMode.
//
// 0.10 (2026-11-03, project doc Befund-Look.md): the black / white-black screen of the look was data, not the camera
// mode: event 0x32 creates a full-screen effect (type 0x85) drawn with material 20744, whose converted pixel shader was
// a surrogate. The fix is the data tree dlc_test50l_look (TU shader translated). 0.10 reports that effect in the log and
// can remove it ([Look] ScreenEffect=0, for data without the fix).
//
// 0.11 (2026-11-03, Befund-Look.md section 7): GlobalParams[7] = the TU's shader vector of the power (TU 0x82474728
// appends it to the per-frame GlobalParams 0-6 of the player; PC tru+0x373a70 + wrapper), state 2102 (camera blend to
// its end, TU 0x822ae918 / 0x822c2130), the meter interface TruShadowPowerMeterApi (version 2: TruShadowCombat + HUD natives),
// and the meter's start time on the TU's clock (PC 0xe7f158 = Xbox 0x82efb528, read by the look fade).
//
// 0.12 (2026-11-03, Befund-Look.md section 9): meter interface version 3 (+ gt1280, the step count shared with
// TruShadowCombat's state 244 and read by condition 1048), and the second appended block of TU 0x82474728 (the player
// model's InstanceParams[1] = (1, 0, 0, 0) while a cinematic runs, else 0; [Look] CinematicParam).
//
// 0.13 (2026-11-04, docs Befund-2102-und-Id68f4.md): state 2102 is registered again next to TruDataGuard.asi. Its byte
// check of the section lookup tru+0x14df80 (the camera-settings lookup) failed in every run since TruDataGuard 0.1:
// TruDataGuard loads first (alphabetical) and writes a 5-byte jump to its guard stub there. The check now accepts
// exactly that patch (E9 into TruDataGuard.asi, the rest of the function unchanged) and names the failing check.
//
// 0.14 (2026-11-04, project doc Befund-Schattenkraft-0411b.md): the remaining TU parts of the power, four switches,
// all default 0 (= 0.13): [Sound] LoopSound (meter +0x0 looping sound, 0x823d7700 / 0x82480440 / 0x824805c8),
// [Look] MoveEvents (0x823d77f0 events 0x83 / 0x84 and Start's 0x83 by gameTracker+0x1f0, the same PC field),
// [Look] CameraFlag (Start's camera manager vtbl[0xa4]), [Look] StrikeLook (0x823d8a80 / 0x823d9050 on player anim
// events 5 / 4 in doppelganger mode; meter interface v4 strikeLookOff for TruShadowCombat).
//
// 0.15 (2026-11-06, project doc Befund-F20-Zopf-0611.md): [Cloth] TuTimeStep (default 0 = 0.14) - the TU's player
// cloth time step. TU 0x82278120 (retail 0x8227b220, PC tru+0x1bbe70) updates the cloth component (type 14, Lara's
// ponytail) of an instance; the TU divides the player's frame time by the world time scale there, so the hair keeps
// real time while the shadow power slows the world (without it the ponytail stretches). Section "0.15" below.
//
// 0.16 (2026-11-06, project doc Befund-15h-Absturz-Finisher-0611.md section 1): crash fix. The TU runs the meter tick
// inside Lara's player update (0x824128a4..0x824128b8) - no Lara, no tick. The plugin ticks from the pad poll, so
// during a level teardown (level.load, save.load, mission start, death reload) a tick ran with player state
// [0xfadb58] = 0; with the meter below max Refill -> ShowMeter -> HUD manager vtbl[3] -> HUD script -> uigamedata f32
// (tru+0x3a0db0 -> tru+0x37bd80) read [0xfadb58]+0x50d -> AV tru+0x37bdd3. MeterTick now returns at once (no refill,
// no HUD call, no state change) while the player state or the player instance [0xe7f094] is 0, the main state
// [0xe7ed60] is not 1 or a level change waits (GameTracker+0xb9); every HUD call of the plugin needs the player state.
// One log line per skip burst and one when the tick resumes. Section "0.16" below.
//
// 0.17 (2026-11-06, project doc Befund-TruShadowPower-017-0611.md): the power counts LB / RB only as the game gets
// them. Live 22:18 (DLC 2): every LB / RB page switch of TruMenu's quick bar started the power. The pad slot
// 0x00a02b8c is shared by TruMenu, TruLink and this plugin, and the chain order depends on thread timing: TruMenu's
// import filter never handed out its hook in that TruMenu.log (44 sessions, always "PadHook set on the pointer (late
// load)"), so TruMenu often sits OUTSIDE this plugin (game -> TruMenu -> TruShadowPower -> TruLink -> XInputGetState)
// and masks LB / RB (quick bar) or hands out a neutral pad (menu, ring) only after this plugin has read the real pad;
// the game's state buffer is on the poll's stack (tru+0x84b7c), so nothing of it is left to read afterwards.
// [ShadowPower] MenuInput=1 (default; 0 = 0.16): (1) once per hook generation and owner the plugin wraps the hook
// that took the slot over it (TruMenu always, TruLink only while the plugin is innermost), so it runs outside
// TruMenu's hook and its view is the game's view; a call that comes back into the plugin from inside that chain goes
// on to the function it called before (every hook still runs once per poll);
// (2) a button the real pad holds but the game does not get (read again from XInputGetState with the same packet
// number) is ignored until it is released - also after the menu / bar closes (no start with RB still held). One log
// line per suppression burst and one at the resume. Section "0.17" below.
//
// 0.18 (2026-11-07, project doc Befund-TU-K9-K11-0711.md): K11. CombatManager::Update tru+0x3227d0 (TU 0x823dca00)
// runs the retail adrenaline tick tru+0x318bd0 and, as its tail call, the adrenaline bar tru+0x2f2930, which writes the
// HUD value [0xfae8d4] every frame - over this plugin's meter. The TU calls both only while gameTracker+0x1244 is 0.
// [Adrenaline] Translate=1 (default) does the same at the PC call sites; [Adrenaline] Log=1. Section "0.18" below.
//
// 0.19 (2026-11-07, project doc Befund-Padkette-StartView-0711.md): no re-wrap any more. 0.17 took the pad pointer
// over TruMenu's hook (and over TruLink's while innermost) to see the pad as the game gets it. TruMenu 0.21.1 exports
// TruMenuPadBlock(pad) - the buttons it keeps from the game right now (menu / ring neutral pad, quick bar D-pad / LB /
// RB, a button held at the close) - so the place in the chain no longer matters: the hook thread is back to the 0.16
// rule (hook once, re-hook only when the slot points into xinput again; foreign hooks are left in place, one log line
// per owner), and GameButtons takes the export's mask (resolved by the hook thread from TruMenu.asi) in addition to the
// second XInputGetState read of 0.17 (still needed when this plugin sits outside TruMenu: a neutral pad hides which
// buttons the real pad holds). Withheld buttons stay ignored until they are released, as in 0.17. Without the export
// (TruMenu older than 0.21.1) only the second read is left (= 0.17 without the re-wrap; one log line).
//
// 0.20 (2026-11-07, P5b): [Look] CameraFlag default 1 = the TU. The reader of the camera manager's bit 2 is found on
// the PC: tru+0x1e5e8e in tru+0x1e5bc0 (= TU 0x822a9888 / retail 0x822ac840) calls the getter tru+0x1e7770, then
// `mov eax, [edx+0xac]; call eax` (= TU 0x822a9a7c vtbl[0xac], test bit 2) and picks the second camera curve set
// (+0x9c / +0xe8 instead of +0x4 / +0x50, evaluator tru+0x1f20a0 = TU 0x822b6840) - the same code as the TU's. The
// earlier search missed it (it looked for `call [reg+0xac]`). TU sites of the bit (cam_slot_static_scan.py): set in
// Start 0x823d7f0c and in the main-game strike look 0x823e0308 (site 0x823e0514), cleared only by its off 0x823e07e8
// (site 0x823e0904) - neither runs in doppelganger mode; on the PC the camera reset tru+0x1edf50 (vtable slot 0x20,
// from the camera init tru+0x1f2440 at level / player init) clears +0x80. The reader site and the bit-2 test slot are
// byte-checked too; the flag call itself is unchanged.
//
// 0.21 (2026-11-10, X23, workspace doc Befund-X23-Kraftlauf-0911.md): time-scale request slot 6. The TU's gamebase
// natives 23 / 24 (binder 0x824a28c0 entries 23 / 24 = 0x824a3238 / 0x824a32f0; retail 0x8249dac8 / 0x8249db18, binder
// 0x8249ced0; PC tru+0x397cf0 / tru+0x397d10, binder tru+0x3b44a0 at tru+0x3b4548) take args[0] = target, args[1] =
// seconds. With the player state [0x829892b0], the tuning (0x82415518), gameTracker+0x1244 and the meter +0x508 all
// set they write args[0] into meter +0x70 (native 23) / +0x74 (native 24) and call the selector 0x823d7520 - crossed
// against the retail meaning: +0x70 is slot 6 PLAYER, +0x74 slot 6 WORLD; the duration is not used. Otherwise they set
// the ramp directly as retail (23 world, 24 player). [TimeScale] TranslateSlot6=1 (default) does the same: both PC
// natives jump to Native23Stub / Native24Stub; outside doppelganger mode the game's own body runs (trampoline).
// Section "0.21" below.
//
// 0.22 (2026-11-10, K-5, workspace docs Befund-Anvisier-Kreis-0911.md section 6 and Befund-TU-Abdeckung-Teilweise-
// 1011.md): the combat reticle ("ring") request and the adrenaline refill in doppelganger mode as the TU.
// playerDrawCombatLock (TU 0x823de170, retail 0x823dc120, PC tru+0x31e710) requests the ring (HUD script 37, HUD group
// 12) when a target exists and CM+0x1fc bit 9 or 10 or a third condition holds; that third condition is CM+0x1fc
// bit 21 on retail / PC, and in doppelganger mode the TU's meter flag 2 (TU 0x823de47c..0x823de49c, PC site
// tru+0x31e979). The refill case of PlayerSM::DefaultMessageHandler (TU 0x823ee158..0x823ee22c, PC tru+0x31f500)
// gates the refill the same way (bit 21 -> meter flag 2), and the TU's "adrenaline full" helper 0x823dfd98 (= PC
// tru+0x2e6630) tests meter flag 0x40 instead of CM+0x1fc bit 27. [Reticle] TranslateRequest / TranslateRefill
// (default 1), read again at run time. TU 0x823e0308 (retail strike look, PC tru+0x315020) has a doppelganger branch
// too, but its only caller 0x8240a430 calls it only outside doppelganger mode - dead code on the Xbox, not ported
// ([Look] StrikeLook is the TU's doppelganger case). Section "0.22" below.
//
// 0.23 (2026-11-10, N2, testing / accessibility - not a TU feature): [Meter] Infinite=1 keeps the meter at max.
// Default 0; read again at run time at most once per second (InfiniteReadSwitch, game thread, from the pad poll like
// the 0.21 switch). Only the plugin's own meter path changes, nothing is written from another thread and no game code
// is patched: the tick (TU and legacy) sets the value to tuning +0x10 before its button / drain / refill block, as a
// finished refill leaves it (InfiniteHold: value = max, delay 0, flag 8 by tuning +0x2c, the HUD bar once to full),
// and Drain (0x823d8380 - the tick, state 1018, TruShadowPowerMeterApi drain of TruShadowCombat's strike) leaves the
// value at max. So the power runs exactly as with a full meter (start events 0x81 / 0x87, request slot 0 with tuning
// +0x40 / +0x3c, flags, condition 1046 = flag 1); it ends only on release / cinematic / game flag, never "meter empty"
// (no flag 0x200, no event 0x7e). Switching it off lets the meter drain / refill from max with the TU rates again.
// Section "0.23" below.
//
// 0.24 (2026-11-11, N6, project doc Befund-Kletterkamera-Kraft-1111.md): [Camera] TuTimeStep (default 0 = 0.23) - the
// TU's camera time step. Four TU camera updates (camera manager 0x822ad048, LaraCamera 0x822beeb8, LaraCameraRewrite
// 0x822c39c8, LaraCombatCamera 0x822c79d0) divide the world-scaled frame time [gt+0x100] by the world time scale
// [gt+0x118] before the 1/30 factor; retail and the PC use the scaled time, so on the PC the gameplay camera follows /
// re-centres at 0.3 x speed while the shadow power slows the world. PC sites tru+0x1f3c79 / 0x1fe30a / 0x2026ca /
// 0x2044aa (6-byte `fld [0xe7f188]` -> stub with `fdiv [0xe7f1a0]`), the same idiom as [Cloth] TuTimeStep (0.15).
// Section "0.24" below (after the 0.15 cloth section).
//
// 0.25 (2026-11-11, project doc Plan-Kamera-Vergleich-Xenia-PC-1111.md): ini keys renamed [Camera] CameraTuTimeStep /
// [Cloth] ClothTuTimeStep (the old name TuTimeStep is still read when the new key is missing). [Camera] Trace=1
// (default 0, live): TruCam.log, one TSV row per TraceInterval ms with TruXenia's --camtrace columns (camera / Lara
// yaw, recenter clock and settings, world scale, meter, pad) - read only. [Camera] DoppelgangerSettings (default 0):
// the TU's camera settings choice in doppelganger mode (0x822bc198 / 0x822c61d8: DTP 21237 / 21238 instead of the
// GlobalInfo defaults) at the 34 PC fallback blocks; 1 = 1:1 (needs the DTPs in the data - the installed generalbank
// lacks them), 2 = 1 + a stand-in for 21237 (PC DTP 20 with the TU's delay 0.25 s / ramp 5.0 s - partial). Live Xbox
// 2026-11-10 21:48: the gameplay camera uses 21237 (0.25 s / 5.0 s), the PC DTP 20 (5.0 s / 2.0 s). State 2102 no longer
// reads PC GlobalInfo +0x14c (DTP 22). Sections "0.25 [Camera] Trace" / "0.25 DoppelgangerSettings".
//
// 0.26 (2026-11-11): [Camera] Trace accepts TruDataGuard's jump at the settings lookup 0x54df80 (0.25 compared the
// original bytes and refused the trace, live 2026-11-10 22:23:31 "code at 0x0054df80 does not match"; the trace never
// calls the lookup, it reads the table 0xc36f28 itself) and names every failing check. DoppelgangerSettings=2: the
// stand-in also carries DTP 21237's per-mode tables (table A / B; the climb modes 60 / 61 / 62 and 0 / 8 / 23 / 32 /
// 33 / 34 / 58 / 59 / 63 differ from the retail default) - section "0.26 doppelganger mode tables".
//
// 0.27 (2026-11-11, Q50, project doc Befund-Zeitschritt-Q50-1111.md): the TU's remaining divisions of the frame time
// by the world time scale (Q17 ranks 7 / 11), two new switches (default 0 = 0.26; patched only when 1 at the start,
// then read again at run time at most once per second). [Camera] ShakeTuTimeStep: the camera shake pool TU 0x822af4d8
// = PC tru+0x1f3390 (site tru+0x1f339e). [Player] TuTimeStep: Lara's query case 0xe0 (TU 0x8240cf88, site
// tru+0x30a70a), message 0x190 (TU 0x8240e3a0, tru+0x320ed7), ComputeSmoothRide (TU 0x82411850, tru+0x300bda),
// RazielAdditionalCollide (TU 0x82411c30: gt+0x100 divided for its whole body, wrapper at tru+0x31bfa0) and
// PLAYER_GetAttachedToVelocity (TU 0x82419c98, tru+0x302a43). Section "0.27" below (after the 0.24 section).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <errno.h>
#include <share.h>

namespace {

struct PadState {                       // XINPUT_STATE without including xinput.h
    DWORD dwPacketNumber;
    WORD wButtons;
    BYTE bLeftTrigger, bRightTrigger;
    SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY;
};

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, PadState *);
typedef void(__stdcall *SetTimeScaleFn)(float target, float seconds);
typedef void(__cdecl *HudGroupFn)(int group);
typedef void(__cdecl *HudUpdateFn)();

const DWORD kImageBase = 0x00400000;
const DWORD kCallSite = 0x00484b82;     // ff 15 8c 2b a0 00 = call dword ptr [0x00a02b8c]
const DWORD kPadPointer = 0x00a02b8c;
const DWORD kSetWorld = 0x00776030;
const DWORD kSetPlayer = 0x00776090;
const BYTE kCallBytes[] = {0xff, 0x15, 0x8c, 0x2b, 0xa0, 0x00};
// first 12 bytes of both setters: push ecx; mov eax,[0xe7f15c]; fild dword [0xe7f15c]; test eax,eax
const BYTE kSetterBytes[] = {0x51, 0xa1, 0x5c, 0xf1, 0xe7, 0x00, 0xdb, 0x05, 0x5c, 0xf1, 0xe7, 0x00};
const BYTE kWorldRamp[] = {0xb9, 0xb4, 0xbe, 0x8a, 0x00};   // mov ecx,0x8abeb4 at +0x1d
const BYTE kPlayerRamp[] = {0xb9, 0x94, 0xbe, 0x8a, 0x00};  // mov ecx,0x8abe94 at +0x1d

// frame time: the frame update stores us / 33333.33 (1.0 = one 30 fps frame) unscaled into 0xe7f190, like the Xbox
// into 0x82efb560 (both frame updates use the constants 0x8235 / 50000 / 0x411b us); the game clock 0xe7f15c (ms,
// Xbox 0x82efb528) advances once per frame and is the setters' start time
const DWORD kFrameDivSite = 0x005da3f4;                     // fdiv qword [0x855280]
const BYTE kFrameDivBytes[] = {0xdc, 0x35, 0x80, 0x52, 0x85, 0x00};
const DWORD kFrameDivConst = 0x00855280;
const BYTE kFrameDivValue[] = {0x00, 0x00, 0x00, 0xa0, 0xaa, 0x46, 0xe0, 0x40};  // 33333.333
const DWORD kFrameStoreSite = 0x005da40c;                   // fst dword [0xe7f190]
const BYTE kFrameStoreBytes[] = {0xd9, 0x15, 0x90, 0xf1, 0xe7, 0x00};
const float *const kFrameTime = reinterpret_cast<const float *>(0x00e7f190);
const volatile DWORD *const kGameClock = reinterpret_cast<const volatile DWORD *>(0x00e7f15c);
// 0.11: the clock the TU meter keeps in +0x3c (Start / Stop: [0x82efb458 +0xd0] = 0x82efb528) and the look fade
// 0x823d85a8 reads. gameTrackerX has the same layout on both platforms (0x82efb464 / 0x82efb514 / 0x82efb560 /
// 0x82efb590 = PC 0xe7f094 / 0xe7f144 / 0xe7f190 / 0xe7f1c0, one offset), so 0x82efb528 = PC 0xe7f158 (advanced once
// per frame by `add [0xe7f158], eax` at tru+0x1da813). Up to 0.10 the meter stored 0xe7f15c (nothing read it).
const volatile DWORD *const kTuClock = reinterpret_cast<const volatile DWORD *>(0x00e7f158);
const DWORD kTuClockAdd = 0x005da813;
const char *const kTuClockAddHex = "010558f1e700";

// HUD: the second silhouette is a uimeter fed by hudscreenmgr native 36 (0xfae8d4); it is drawn while display group 1
// is requested. The TU meter does "0x829ca6cc = value / max; 0x829ca724 |= 2; (*0x829ca720)->vtbl[0xc]()", the PC
// breath code the same with tru+0x37d9d0(1) (0xfae924 |= 1 << 1) and tru+0x37da70 ((*0xfae920)->vtbl[0xc]()).
const DWORD kHudValueGetter = 0x0077a860;                   // hudscreenmgr native 36 body
const BYTE kHudValueBytes[] = {0xd9, 0x05, 0xd4, 0xe8, 0xfa, 0x00, 0xc3};   // fld dword [0xfae8d4]; ret
const DWORD kHudGroup = 0x0077d9d0;
const BYTE kHudGroupBytes[] = {0x8b, 0x4c, 0x24, 0x04, 0x8d, 0x41, 0xff, 0x83, 0xf8, 0x1e, 0x77, 0x0e, 0xba,
                               0x01, 0x00, 0x00, 0x00, 0xd3, 0xe2, 0x09, 0x15, 0x24, 0xe9, 0xfa, 0x00, 0xc3};
const DWORD kHudUpdate = 0x0077da70;
const BYTE kHudUpdateBytes[] = {0x8b, 0x0d, 0x20, 0xe9, 0xfa, 0x00, 0x8b, 0x01, 0x8b, 0x50, 0x0c, 0xff, 0xe2};
float *const kHudValue = reinterpret_cast<float *>(0x00fae8d4);
void *const *const kHudManager = reinterpret_cast<void *const *>(0x00fae920);

// object table (Xbox 0x82979280): 0xcc entries of 0x24 bytes, +8 object, +0xc s16 id, +0xe u16 state (2 = loaded);
// checked through the PC lookup tru+0x14e930 that walks it
const DWORD kFindObject = 0x0054e930;
const BYTE kFindObjectBytes[] = {0x8b, 0x54, 0x24, 0x04, 0x33, 0xc0, 0xb9, 0x0c, 0x74, 0xdb, 0x00};
const DWORD kFindObjectLoop = 0x0054e951;
const BYTE kFindObjectLoopBytes[] = {0x83, 0xc1, 0x24, 0x3d, 0xcc, 0x00, 0x00, 0x00};
const DWORD kObjectTable = 0x00db7400;
const int kObjectCount = 0xcc;
const SHORT kExtensionObject = 858;     // player_tru_dlc2_extension
const WORD kTuningType = 60;            // u16 at +2 of the object's data, checked by the TU (0x82412b74)

// 0.4: Lara's own condition link array (PC tru+0x368b60 = Xbox TU 0x82473b50 registers the conditions table
// 0x8b2ce8, activities 0x8b2280, states 0x8b0a50 of the state machine at gameTracker+0xf10). Its loop tru+0x385120
// inserts a record only when the id is also in the generic registry (tru+0x3851bc..+0x385208) - so the title-update ids
// need TruDoppelganger.asi's generic entries AND an entry here with the real handler, as on the Xbox.
const DWORD kLaraReg = 0x00768b60;
const BYTE kLaraRegBytes[] = {0xa1, 0x58, 0xdb, 0xfa, 0x00, 0x56, 0xc7, 0x05, 0x74, 0xda, 0xfa, 0x00, 0x48, 0x00,
                              0x00, 0x00, 0x8b, 0xb0, 0x10, 0x0f, 0x00, 0x00, 0x8b, 0xce, 0xe8, 0xc3, 0xa8, 0x01, 0x00,
                              0x85, 0xc0, 0x75, 0x24, 0x68, 0xe8, 0x2c, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0x93, 0xc5, 0x01,
                              0x00};
const DWORD kLaraCondPush = 0x00768b81;                     // push 0x8b2ce8 (operand at +1)
const DWORD kGenericCondPush = 0x00787343;                  // operand of the generic builder's push 0x8b57e0
const DWORD kGenericCondTable = 0x008b57e0;
const DWORD kLaraCondTable = 0x008b2ce8;
const int kLaraCondCount = 285;                             // records before the closing {0, 0, default}
const DWORD kCondDefaultFn = 0x00782140;                    // closing record's function (SCCondFunction_Default)
// condition template = Xbox 0x82487718: cache {agent, frame (+0x50c), bits}, predicate(record), value 0 now false,
// 1 now true, 2 falling edge, 3 rising edge, flag bit 0 negates
const DWORD kCondTemplate = 0x00782d70;
const BYTE kCondTemplateBytes[] = {0x51, 0x53, 0x55, 0x8b, 0x6c, 0x24, 0x18, 0x56, 0x8b, 0x74, 0x24, 0x18, 0x8b, 0x5e,
                                   0x08, 0x57, 0x8b, 0x7c, 0x24, 0x18, 0x39, 0x3e, 0xc6, 0x44, 0x24, 0x13, 0x00, 0x75,
                                   0x0b, 0x8b, 0x46, 0x04, 0x3b, 0x87, 0x0c, 0x05, 0x00, 0x00, 0x74, 0x23, 0x55, 0xff,
                                   0x54, 0x24, 0x28};
// float compare = Xbox 0x82487348: record value (s16 +4, key 1000 = variable), mode 1 value >= it, 2 value <= it,
// 0 |difference| < 1e-8 ([0x8454c4] = Xbox [0x8207dcd4]), flag bit 0 negates
const DWORD kCondCompare = 0x00783bd0;
const BYTE kCondCompareBytes[] = {0x56, 0x8b, 0x74, 0x24, 0x10, 0x66, 0x81, 0x3e, 0xe8, 0x03, 0x0f, 0xbf, 0x46, 0x04,
                                  0x89, 0x44, 0x24, 0x10, 0xdb, 0x44, 0x24, 0x10};

// TU constants (Xbox addresses in brackets)
const float kZero = 0.0f;               // [0x8207d538]
const float kOne = 1.0f;                // [0x8207d544] ramp target without a request
const float kMeterStart = 1000.0f;      // [0x8206af78] meter value at init, start value after a stop (+0xc)
const float kPerSecond = 1.0f / 30.0f;  // [0x82052c58] 0.0333333 - frame units -> seconds
const float kRampSeconds = 0.033f;      // [0x8207db70] 33.0 ms, the selector's ramp duration
const float kNoRequest = -1.0f;         // [0x82052664] empty request slot
const float kPercent = 0.01f;           // [0x820536ec]
const float kHundred = 100.0f;          // [0x8207d53c]
const float kShortMove = 200.0f;        // [0x8206af90] frames value of a move of <= 2 steps (state 245)

// tuning struct offsets (floats) as the TU reads them
enum {
    kTuneMax = 0x10, kTuneDrain = 0x14, kTuneRefill = 0x18, kTuneRefillAlt = 0x1c, kTuneRefillDelayed = 0x20,
    kTuneRestart = 0x28, kTuneHigh = 0x2c, kTuneWorld = 0x3c, kTunePlayer = 0x40, kTuneDelay1018 = 0x24,
    kTuneTimedWorld = 0x54, kTuneTimedPlayer = 0x58, kTuneMoveSpeed = 0x68, kTuneMoveDistance = 0x6c, kTuneSize = 0x78
};

// copy of the same struct from the converted file (player_tru_dlc2_extension.drm, DTP 22497 +0xf0), used only when
// the object is not found at run time and Fallback=1 - logged as such
BYTE g_fileTuning[kTuneSize];

void InitFileTuning() {
    struct { int offset; float value; } const values[] = {
        {kTuneMax, 1000.0f}, {kTuneDrain, 200.0f}, {kTuneRefill, 200.0f}, {kTuneRefillAlt, 400.0f},
        {kTuneRefillDelayed, 75.0f}, {0x24, 6.0f}, {kTuneRestart, 150.0f}, {kTuneHigh, 300.0f}, {0x30, 200.0f},
        {0x34, 500.0f}, {0x38, 0.1f}, {kTuneWorld, 0.3f}, {kTunePlayer, 1.2f}, {0x44, 0.075f}, {0x48, 1.0f},
        {0x4c, 0.075f}, {0x50, 0.075f}, {kTuneTimedWorld, 1.0f}, {kTuneTimedPlayer, 0.02f}, {0x60, 25.0f},
        {0x64, 25.0f}, {kTuneMoveSpeed, 410.87f}, {kTuneMoveDistance, 1896.3f}, {0x70, 75.0f}, {0x74, 1.0f}};
    // (+0x5c is a pointer in the file - the sound / effect handle data, not used here)
    memset(g_fileTuning, 0, sizeof(g_fileTuning));
    g_fileTuning[0] = 1;                                     // u16 1, u16 type 60 as in the file
    g_fileTuning[2] = static_cast<BYTE>(kTuningType);
    for (const auto &v : values) memcpy(g_fileTuning + v.offset, &v.value, sizeof(float));
    // exact bit patterns of the two non-round values of the file (410.87 / 1896.3 are rounded above)
    const DWORD speed = 0x43cd6fa8, distance = 0x44ed0aaf;
    memcpy(g_fileTuning + kTuneMoveSpeed, &speed, sizeof(DWORD));
    memcpy(g_fileTuning + kTuneMoveDistance, &distance, sizeof(DWORD));
}

// the TU's meter object (allocated with the player data; the fields used here, with their Xbox offsets)
struct Meter {
    DWORD flags;                        // +0x04: 1 active, 8 at or above tuning +0x2c, 0x200 ran empty (restart only
                                        //        above tuning +0x28); 0x10 / 0x80 block the meter (not set here)
    float value;                        // +0x08
    float startValue;                   // +0x0c value when the power started (1000 after a stop)
    float delay;                        // +0x10 refill delay timer (no writer found in the TU besides the refill)
    BYTE latch;                         // +0x14 buttons seen held
    float moveLength;                   // +0x30 0.14: last length of gameTracker+0x1f0 (0x823d77f0; 0.0 at init)
    LONG moveSince;                     // +0x34 0.14: game clock of the rising edge, -1 = none (0x823d77f0)
    float requestTimer;                 // +0x38 frames until request slot 4 (condition 2401) is cleared
    DWORD startTime;                    // +0x3c game clock at the last start / stop
    // +0x40..+0x77: time-scale request list of 0x823d7520, 7 slots {player, world}; a value <= 0 = no request
    // (-1.0 [0x82052664] clears a slot). Slot 0 = the power (Start / Stop), 2 = shadow look (0x823d8a80, not ported),
    // 4 = timed request of condition 2401, 5 = state 1018, 6 = the gamebase natives 23 / 24 in doppelganger mode (0.21).
    float request[7][2];
};

// options (TruShadowPower.ini)
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 every start / stop, 3 debug
WORD g_buttons = 0x0300;                // LB 0x0100 | RB 0x0200 (Xbox: either); LB also sprints on PC
int g_hudFeed = 1;                      // [Meter] HudBar
int g_fallback = 1;                     // [Meter] Fallback: file copy of the tuning when the object is not loaded
int g_legacyPadStart = 0;               // 0.9 [ShadowPower] LegacyPadStart: 1 = the 0.8 tick (no TU gates)
int g_gameInput = 0;                    // 0.9 [ShadowPower] GameInput: 1 = LB / RB from the game's input records
int g_adrenalineMode = 1;               // 0.9 [Look] AdrenalineMode: TU 0x823d94f8 group + mode chooser / adrenaline
int g_loopSound = 0;                    // 0.14 [Sound] LoopSound: TU looping sound of the power (meter +0x0)
int g_moveEvents = 0;                   // 0.14 [Look] MoveEvents: TU 0x823d77f0 + Start's event 0x83 (gameTracker+0x1f0)
int g_cameraFlag = 0;                   // 0.14 [Look] CameraFlag: TU Start's camera manager vtbl[0xa4] (+0x80 |= 2)
int g_strikeLook = 0;                   // 0.14 [Look] StrikeLook: TU 0x823d8a80 / 0x823d9050 (player anim events 5 / 4)
int g_menuInput = 1;                    // 0.17 [ShadowPower] MenuInput: buttons only as the game gets them (0 = 0.16)
int g_infinite = 0;                     // 0.23 [Meter] Infinite: the meter stays at max (read again at run time)
LONG g_infDrains = 0;                   // 0.23: drain calls held at max while Infinite is on (log only)
double g_infHeld = 0.0;                 // 0.23: their amounts (meter units not taken, log only)
LONG g_infFills = 0;                    // 0.23: tick fills to max while Infinite is on (log only)

char g_logPath[MAX_PATH];
char g_iniPath[MAX_PATH];                     // 0.18: for the run-time reads of the ini ([Adrenaline] Translate, ...)
CRITICAL_SECTION g_logLock;
volatile XInputGetStateFn g_original = nullptr;
SetTimeScaleFn g_setWorld = reinterpret_cast<SetTimeScaleFn>(kSetWorld);
SetTimeScaleFn g_setPlayer = reinterpret_cast<SetTimeScaleFn>(kSetPlayer);
HudGroupFn g_hudGroup = reinterpret_cast<HudGroupFn>(kHudGroup);
HudUpdateFn g_hudUpdate = reinterpret_cast<HudUpdateFn>(kHudUpdate);
WORD g_lastButtons[4] = {0, 0, 0, 0};
bool g_hudOk = false;                   // HUD code verified
bool g_tableOk = false;                 // object table verified
int g_tuningSource = -1;                // last logged source: 0 none, 1 game object, 2 file copy
DWORD g_lastClock = 0;
Meter g_meter;
volatile LONG g_stop = 0;
const BYTE *volatile g_tuning = nullptr;  // tuning of the last tick (Xbox 0x82415518's result), read by the conditions
int g_condEnabled = 1;                    // [Conditions] Enabled: register 1049-1054 / 1056 in Lara's link array
int g_statesEnabled = 1;                  // [States] Enabled (0.5): TU states 243 / 245 / 1018, conditions 1048 / 2401,
                                          // activities 1009 / 1039
volatile LONG g_condCalls[9];             // first-call log per handler (1049..1054, 1056, -, 1055)
volatile LONG g_condLast[9];              // last result per handler (+1, 0 = none yet) for LogLevel 2

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[512];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        fputs(line, f);
        fputs("\n", f);
        fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}

bool BytesAt(DWORD address, const BYTE *expected, size_t length) {
    __try {
        return memcmp(reinterpret_cast<const void *>(address), expected, length) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

float Tune(const BYTE *tuning, int offset) { return *reinterpret_cast<const float *>(tuning + offset); }

// Xbox 0x82415518 returns the extension instance's data (game state +0x1314 -> instance +0x50); the instance is
// spawned by TU code (0x82412ab0) from the player's object list when the object's data has type 60. The PC has no
// such instance, so the same data is taken from the loaded object itself: table entry id 858, state 2 (loaded),
// object +0x5c data and +0x60 set, u16 type 60 at data +2 - the checks of 0x82412b44..0x82412b7c.
// 0.3.1 (2026-10-31): the lookup failed in the 0.3 test without saying why; it now records which check stopped it
// (same checks, same result) so the next log names the step: 1 table not verified, 2 id 858 not in the table,
// 3 entry state not 2, 4 no object, 5 object +0x5c / +0x60 empty, 6 data type not 60, 7 read fault.
int g_lookupReason = 0;
DWORD g_lookupDetail[4];

const BYTE *ObjectTuning() {
    g_lookupReason = 1;
    if (!g_tableOk) return nullptr;
    __try {
        g_lookupReason = 2;
        for (int i = 0; i < kObjectCount; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            if (*reinterpret_cast<const SHORT *>(entry + 0xc) != kExtensionObject) continue;
            g_lookupDetail[0] = static_cast<DWORD>(i);
            g_lookupDetail[1] = *reinterpret_cast<const WORD *>(entry + 0xe);
            g_lookupDetail[2] = *reinterpret_cast<const DWORD *>(entry + 8);
            g_lookupReason = 3;
            if (*reinterpret_cast<const WORD *>(entry + 0xe) != 2) return nullptr;
            const BYTE *object = *reinterpret_cast<const BYTE *const *>(entry + 8);
            g_lookupReason = 4;
            if (!object) return nullptr;
            const BYTE *data = *reinterpret_cast<const BYTE *const *>(object + 0x5c);
            g_lookupDetail[3] = reinterpret_cast<DWORD>(data);
            g_lookupReason = 5;
            if (!data || !*reinterpret_cast<const DWORD *>(object + 0x60)) return nullptr;
            g_lookupReason = 6;
            g_lookupDetail[1] = *reinterpret_cast<const DWORD *>(data);   // first word of the data (u16 x2)
            if (*reinterpret_cast<const WORD *>(data + 2) != kTuningType) return nullptr;
            g_lookupReason = 0;
            return data;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_lookupReason = 7;
    }
    return nullptr;
}

// list of the loaded table entries (id / state) once, when the lookup fails - shows whether 858 is there at all
void LogObjectTable() {
    char line[900];
    int n = 0, count = 0;
    __try {
        for (int i = 0; i < kObjectCount && n < static_cast<int>(sizeof(line)) - 16; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            WORD state = *reinterpret_cast<const WORD *>(entry + 0xe);
            if (!state) continue;
            int w = _snprintf_s(line + n, sizeof(line) - n, _TRUNCATE, " %d/%u", *reinterpret_cast<const SHORT *>(entry + 0xc),
                                state);
            if (w <= 0) break;
            n += w; ++count;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    line[n] = 0;
    Log(1, "object table 0x%08lx: %d entries in use (id/state):%s", kObjectTable, count, line);
}

const BYTE *FindTuning() {
    const BYTE *tuning = ObjectTuning();
    int source = tuning ? 1 : (g_fallback ? 2 : 0);
    if (!tuning && g_fallback) tuning = g_fileTuning;
    static int lastReason = -1, reasonLogs = 0;
    if (source != g_tuningSource || (source != 1 && g_lookupReason != lastReason && reasonLogs < 10)) {
        if (source != 1 && g_lookupReason != lastReason) ++reasonLogs;
        lastReason = g_lookupReason;
        if (source != 1) {
            static const char *const reasons[] = {"ok", "table code not verified", "id 858 not in the table",
                                                  "entry state is not 2", "entry has no object",
                                                  "object +0x5c / +0x60 empty", "data type at +2 is not 60",
                                                  "read fault"};
            Log(1, "tuning lookup of object %d failed: %s (entry %lu, state/first data word 0x%08lx, object 0x%08lx, "
                   "data 0x%08lx)", kExtensionObject, reasons[g_lookupReason & 7], g_lookupDetail[0], g_lookupDetail[1],
                g_lookupDetail[2], g_lookupDetail[3]);
            if (g_tableOk) LogObjectTable();
        }
        g_tuningSource = source;
        if (!tuning)
            Log(1, "tuning: object %d not loaded - no shadow power (as on the Xbox without the extension)",
                kExtensionObject);
        else
            Log(1, "tuning: %s - max %.1f, drain %.1f/s, refill %.1f/s (alt %.1f, delayed %.1f), restart above %.1f, "
                   "world %.3f, player %.3f",
                source == 1 ? "game object player_tru_dlc2_extension (858)"
                            : "FALLBACK copy of the file values (object 858 not found at run time)",
                Tune(tuning, kTuneMax), Tune(tuning, kTuneDrain), Tune(tuning, kTuneRefill),
                Tune(tuning, kTuneRefillAlt), Tune(tuning, kTuneRefillDelayed), Tune(tuning, kTuneRestart),
                Tune(tuning, kTuneWorld), Tune(tuning, kTunePlayer));
    }
    return tuning;
}

// 0.16 (Befund-15h-Absturz-Finisher-0611.md section 1): the HUD update below runs the HUD script, which reads the
// current weapon name through uigamedata f32 (native 0x20, tru+0x3a0db0 -> tru+0x37bd80): `mov ecx,[0xfadb58]` at
// tru+0x37bdb5, then `mov al,[ecx+0x50d]` at tru+0x37bdd3 without a null test. The player state [0xfadb58] (TU
// 0x829892b0; kGameTrackerPtr below, TruMenu's "playerstate P") is set by tru+0x32247b and cleared (ebx = 0 from
// tru+0x321ffa) by tru+0x322304 when the player goes. So no HUD call of this plugin while it is 0. Pinned by bytes in
// the 0.16 tick gate checks (section "0.16"); the test itself is a plain read of a global and always applies.
const DWORD kPlayerStatePtr = 0x00fadb58;
volatile LONG g_hudSkips = 0;           // HUD calls skipped for a missing player state

bool PlayerStateNow() { return *reinterpret_cast<const volatile DWORD *>(kPlayerStatePtr) != 0; }

// false (and counted / logged rate-limited) when there is no player state: the caller skips its HUD call
bool HudPlayerOk(const char *what) {
    if (PlayerStateNow()) return true;
    LONG n = InterlockedIncrement(&g_hudSkips);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(n == 1 ? 1 : 2, "HUD call skipped (%s): no player state [0xfadb58] - the HUD script would read it (%ld times)",
            what, n);
    return false;
}

// HUD part of 0x823d81a0 / 0x823d8380: fraction, request display group 1, let the HUD manager react
void ShowMeter(float fraction) {
    if (!g_hudOk || !g_hudFeed) return;
    if (!HudPlayerOk("meter")) return;                  // 0.16: no fraction write, no group, no update
    *kHudValue = fraction;
    if (!*kHudManager) return;
    g_hudGroup(1);
    g_hudUpdate();
}

// 0x823d7700: flags 0, value / start value 1000, latch 0 (the HUD fraction is written once the tuning is known).
// 0.5: the request slots and the timer are not set by 0x823d7700 (the meter object is allocated elsewhere, not
// inspected); they start empty here (-1.0, the TU's "no request" value) and 0.
void MeterInit() {
    g_meter.flags = 0;
    g_meter.startValue = kMeterStart;
    g_meter.latch = 0;
    g_meter.value = kMeterStart;
    g_meter.delay = kZero;
    g_meter.moveLength = kZero;                         // 0.14: TU 0x823d7738 stfs 0.0, +0x30
    g_meter.moveSince = -1;                             // 0.14: not set by 0x823d7700 nor the allocation 0x82409c68..;
                                                        // -1 is 0x823d77f0's own idle value (set on every tick while off)
    g_meter.requestTimer = kZero;
    for (int i = 0; i < 7; ++i) g_meter.request[i][0] = g_meter.request[i][1] = kNoRequest;
}

// 0x823d7520 (request selector, argument meter +0x40): the highest slot with a player value > 0 sets the player
// ramp, the highest with a world value > 0 the world ramp; none -> 1.0. The TU writes the ramp structs directly
// (target, 33 ms, current value, clock) - the PC setters write the same ramps (0.3).
// 0.21: the pick of the selector alone (also for the slot-6 log lines)
void SelectorPick(float *playerOut, float *worldOut) {
    bool player = false, world = false;
    float playerTarget = kOne, worldTarget = kOne;
    for (int i = 6; i >= 0; --i) {
        if (!player && kZero < g_meter.request[i][0]) { player = true; playerTarget = g_meter.request[i][0]; }
        if (!world && kZero < g_meter.request[i][1]) { world = true; worldTarget = g_meter.request[i][1]; }
        if (player && world) break;
    }
    *playerOut = playerTarget;
    *worldOut = worldTarget;
}

void Selector() {
    float playerTarget = kOne, worldTarget = kOne;
    SelectorPick(&playerTarget, &worldTarget);
    g_setPlayer(playerTarget, kRampSeconds);
    g_setWorld(worldTarget, kRampSeconds);
    Log(3, "selector: player %.3f, world %.3f", playerTarget, worldTarget);
}

// ---- 0.8: player events of Start / Stop (TU 0x82418158 = PC tru+0x318780) ----
// TU 0x82418158(player 0x82efb464, type, 0xff): every record of the player object's event list (instance +0x10 ->
// object +4) with that type byte (+4), channel 0 (h & 0xc00), skip bit (h & 4) clear, anim controller +0x5c == 0,
// kind 0 / 3 only if controller +0x4c & 0x40, kind 1 only if & 0x80 -> anim-event callback (msg 7). PC tru+0x318780
// (retail, same tests) takes the channel as a 4th argument ((arg ^ h) & 0xc00 == 0) - 0 = the TU's test.
typedef void(__cdecl *PlayerEventFn)(void *instance, int type, int param, int channel);
const DWORD kPlayerEvent = 0x00718780;
const char *const kPlayerEventHex = "51 817c240cff000000 0f84f2000000 8b442408 56 8b7010 8b8080020000 8b4814";
const DWORD kPlayerEventType = 0x007187d0;      // movzx ecx, byte [esi+4]; cmp ecx, [esp+0x1c] (the type byte)
const char *const kPlayerEventTypeHex = "0fb64e04 3b4c241c";
const DWORD kPlayerEventCall = 0x00718858;      // push 7; push ebp x3; push edx; call 0x7181a0 (anim-event callback)
const char *const kPlayerEventCallHex = "6a07 55 55 55 52 e83df9ffff";
int g_lookEnabled = 1;                          // [Look] Enabled
bool g_lookOk = false;                          // walker verified
volatile LONG g_lookStarts = 0;
int Doppelganger();                             // TruDlc2Player's flag (TU gameTracker+0x1244), defined below

// fire one TU player event on the player instance (TU 0x82efb464 = PC 0xe7f094); returns false when not fired.
// On the Xbox Start / Stop exist only with the meter object (gameTracker+0x508), i.e. for the DLC 2 doppelganger
// player - the look is therefore limited to doppelganger mode (the plugin's slow motion itself stays as in 0.7).
bool FireEvent(int type) {
    if (!g_lookOk || !g_lookEnabled || !Doppelganger()) return false;
    void *player = *reinterpret_cast<void *const *>(0x00e7f094);
    if (!player) return false;
    __try {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(player, type, 0xff, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "player event 0x%02x (tru+0x318780): access fault - skipped", type);
        return false;
    }
    return true;
}

// TU 0x823d7f18..0x823d7fa0 (Start, message 0x1f4) / 0x823d8080.. (Stop, message 0x1f5): every instance of the list
// 0x828aaf18 (+4 first, +8 next - read before the calls) whose query function +0x11c answers 0x172 gets 0x8226fe00
// (wake) and then message (+0x120)(instance, msg, 0). PC: list head [0xd98d54] (the walk tru+0x1b53e0, same +8 next,
// +0x110 / +0x11c / +0x120 layout), wake tru+0x1b2de0 = 0x8226fe00 (same body). All cdecl.
typedef int(__cdecl *InstQueryFn)(void *instance, int id);
typedef int(__cdecl *InstMessageFn)(void *instance, int msg, int arg);
typedef void(__cdecl *InstWakeFn)(void *instance);
const DWORD kInstanceHead = 0x00d98d54;
const DWORD kInstWalk = 0x005b53ea;             // mov esi, [0xd98d54] in tru+0x1b53e0
const char *const kInstWalkHex = "8b35548dd900 85f6";
const DWORD kInstNext = 0x005b5563;             // mov esi, [esi+8]; test esi, esi
const char *const kInstNextHex = "8b7608 85f6";
const DWORD kInstQuery = 0x005b5425;            // mov eax, [esi+0x11c]; test; je; push 0x22; push esi; call eax
const char *const kInstQueryHex = "8b861c010000 85c0 7410 6a22 56 ffd0 83c408";
const DWORD kInstWake = 0x005b2de0;             // = TU 0x8226fe00
const char *const kInstWakeHex = "56 8b742408 8b4618 a801 744e 83e0fe 894618 8d8610010000 85c0 741c 57 8bbe20010000 "
                                 "85ff 7410 56 e8d3ffffff 6a00 6a13 56 ffd7 83c410";
int g_lookMessages = 1;                         // [Look] Messages
bool g_msgOk = false;                           // instance list / query / wake verified

// returns the number of instances that got the message, -1 when not sent
int BroadcastPowerMessage(int msg) {
    if (!g_msgOk || !g_lookEnabled || !g_lookMessages || !Doppelganger()) return -1;
    int sent = 0;
    __try {
        BYTE *inst = *reinterpret_cast<BYTE *const *>(kInstanceHead);
        for (int guard = 0; inst && guard < 4096; ++guard) {
            BYTE *next = *reinterpret_cast<BYTE *const *>(inst + 8);           // r29 = [r31+8] before the calls
            InstQueryFn query = *reinterpret_cast<InstQueryFn *>(inst + 0x11c);
            if (inst + 0x110 && query && query(inst, 0x172)) {
                InstMessageFn message = *reinterpret_cast<InstMessageFn *>(inst + 0x120);
                if (message) {
                    reinterpret_cast<InstWakeFn>(kInstWake)(inst);
                    message(inst, msg, 0);
                    ++sent;
                }
            }
            inst = next;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "message 0x%03x to the instances: access fault after %d - skipped", msg, sent);
        return -1;
    }
    return sent;
}

// 0.10 (docs Befund-Look.md): the full-screen part of the look. Event 0x32 of doppelganger_casual fires kind 1 sub 0xb
// {0xe} = record 14 of the model record list (DTP 20134); tru+0x135cc0 makes it an instance effect of type 0x85 in the
// global effect list [0xae4d00] (+0 next, +8 instance, +0x10 type, +0x30 colour, +0x4c material = record word 7).
// tru+0x1469a0 draws it each frame: material != 0 -> tru+0x146340 -> tru+0x13ef30 = a full-screen quad with MATERIAL
// 20744 (colour 0x80576b79, alpha x fade). On the converted data that material had a surrogate pixel shader (lib 2517)
// that shows its mask texture 6619 (black centre, white edges) or black - the "look draws wrong" bug. The fix is data
// (tree dlc_test50l_look: the TU pixel shader 2327 translated, lib 2943 / VS 2944, Xbox MaterialParams). This plugin
// only reports the effect ([Look] ScreenEffect=1) or removes it with the engine's own kill tru+0x12f1c0 (=0; for the
// old data). Read-only walk of the list; called from the game thread (pad poll) like the event walker.
typedef void(__cdecl *EffectKillFn)(void *effect);
const DWORD kEffectHead = 0x00ae4d00;
const DWORD kEffectWalk = 0x0054773b;           // mov esi, [0xae4d00]; xor edi, edi; cmp esi, edi (tru+0x147220)
const char *const kEffectWalkHex = "8b35004dae00 33ff 3bf7";
const DWORD kFx85Create = 0x00535d2e;           // tru+0x135cc0: callback 0x535c00, +8 instance, +0x10 = 0x85
const char *const kFx85CreateHex = "c74604005c5300 660fbe4709 66894614 8b44240c 894608 8b4844 894e0c 81481c00020000 "
                                   "83caff c6461085";
const DWORD kFx85Material = 0x00535de8;         // mov eax, [edi+0x1c]; mov [esi+0x4c], eax (record word 7)
const char *const kFx85MaterialHex = "8b471c 89464c";
const DWORD kFx85Draw = 0x00546dd2;             // tru+0x1469a0: cmp [esi+0x4c], 0 -> tru+0x146340 (material quad)
const char *const kFx85DrawHex = "837e4c00 7411 51 d91c24 6a00 56";
const DWORD kEffectKill = 0x0052f1c0;           // marks the effect dead (+0x10 |= 0x40), the list walk frees it
const char *const kEffectKillHex = "56 8b742408 85f6 743d 8a4610 a840 7536";
int g_lookScreen = 1;                           // [Look] ScreenEffect
bool g_fxOk = false;                            // effect list code verified
int g_fxPending = 0;                            // frames left to look for the effect after event 0x32
volatile LONG g_fxSeen = 0;

// returns the number of type-0x85 effects of the player found (and removed when [Look] ScreenEffect=0)
int ScreenEffectCheck() {
    void *player = *reinterpret_cast<void *const *>(0x00e7f094);
    if (!g_fxOk || !player) return 0;
    int found = 0;
    __try {
        BYTE *e = *reinterpret_cast<BYTE *const *>(kEffectHead);
        for (int guard = 0; e && guard < 8192; ++guard) {
            BYTE *next = *reinterpret_cast<BYTE *const *>(e);
            if (e[0x10] == 0x85 && *reinterpret_cast<void *const *>(e + 8) == player) {
                ++found;
                DWORD material = *reinterpret_cast<const DWORD *>(e + 0x4c);
                DWORD colour = *reinterpret_cast<const DWORD *>(e + 0x30);
                if (!g_lookScreen) reinterpret_cast<EffectKillFn>(kEffectKill)(e);
                if (InterlockedIncrement(&g_fxSeen) == 1)
                    Log(1, "look screen effect: type 0x85 effect of the player, material %lu, colour 0x%08lx (record 14 "
                           "of doppelganger_casual, drawn as a full-screen quad by tru+0x1469a0 -> tru+0x13ef30)%s",
                        material, colour, g_lookScreen ? "" : " - REMOVED ([Look] ScreenEffect=0)");
                else
                    Log(2, "look screen effect: material %lu, colour 0x%08lx%s", material, colour,
                        g_lookScreen ? "" : " - removed");
            }
            e = next;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "look screen effect: access fault in the effect list after %d - skipped", found);
        return -1;
    }
    return found;
}

// per tick after event 0x32 until the effect is found (the anim event may create it a frame later)
void ScreenEffectPoll() {
    if (g_fxPending <= 0) return;
    int n = ScreenEffectCheck();
    if (n != 0) { g_fxPending = 0; return; }
    if (--g_fxPending == 0) Log(2, "look screen effect: no type-0x85 effect of the player within 30 frames of event 0x32");
}

// 0.9, defined below: the TU's start gates (cinematic / 0x829ca6da / health) and the flag-0x40 clear 0x823d9438
bool TuStartRefused();
void Clear40();
// 0.14, defined below (section "0.14"): length of gameTracker+0x1f0, the camera call of Start, the strike look off
bool MoveLength(float *length);
void StartCameraFlag();
void StrikeLookOff();
volatile LONG g_move83Start = 0;

// 0x823d8120
bool CanStart(const BYTE *tuning) {
    if (!tuning) return false;
    if ((g_meter.flags & 0x200) && !(Tune(tuning, kTuneRestart) < g_meter.value)) return false;
    g_meter.flags &= ~0x200u;
    return true;
}

// 0x823d7d40 (the request list 0x823d7520 with only this request = both ramps to the tuning values in 33 ms)
void StartPower(const BYTE *tuning) {
    if (g_meter.flags & 1) return;
    // 0.9: no cinematic (0x82efb590 = PC [0xe7f1c0] via tru+0x53f00), 0x829ca6da (PC 0xfae8dd) clear and gameTracker
    // +0x628 > 0 (0x823d7d68..0x823d7dd4); not with LegacyPadStart=1. Not ported: the camera manager call
    // (*0x82efc780)->vtbl[0xa4] (= 0x822a9e58: camera +0x7c |= 2, selects other camera curves - docs L9)
    if (!g_legacyPadStart && TuStartRefused()) return;
    if (!tuning) return;
    g_meter.request[0][0] = Tune(tuning, kTunePlayer);          // +0x40 = tuning +0x40
    g_meter.request[0][1] = Tune(tuning, kTuneWorld);           // +0x44 = tuning +0x3c
    Selector();
    // 0.8: 0x823d7e10..0x823d7efc - the player events of the start, in the TU's order
    char fired[64] = "";
    int n = 0;
    auto fire = [&](int type) {
        if (FireEvent(type) && n < static_cast<int>(sizeof(fired)) - 6)
            n += _snprintf_s(fired + n, sizeof(fired) - n, _TRUNCATE, " 0x%02x", type);
    };
    fire(0x89);
    fire(0x32);
    if (g_fxOk && g_lookEnabled) { g_fxPending = 30; ScreenEffectPoll(); }      // 0.10: the full-screen effect
    // 0x823d7e30..0x823d7e9c: 0x83 unless the length of gameTracker+0x1f0 <= 10.0 [0x8205262c] (ble skips it). 0.14:
    // PC gameTracker+0x1f0 = the same field (twin block tru+0x317eb6 of retail 0x82409660); [Look] MoveEvents (default
    // 0 = as 0.13: not fired). Its only record in DTP 20172 is sound 0x1cd.
    if (g_moveEvents) {
        float len = 0.0f;
        if (MoveLength(&len) && !(len <= 10.0f)) {
            const int before = n;
            fire(0x83);
            const bool f = n != before;
            LONG k = InterlockedIncrement(&g_move83Start);
            if (k == 1 || g_logLevel >= 2)
                Log(k == 1 ? 1 : 2, "move events: start while moving (|gameTracker+0x1f0| = %.1f > 10) - player event 0x83 "
                    "%s (TU 0x823d7e9c)%s", len, f ? "fired" : "not fired", k == 1 ? ", first time" : "");
        }
    }
    float max = Tune(tuning, kTuneMax);
    if (g_meter.value == max) fire(0x81);                       // [r28+8] == tuning +0x10
    float high = Tune(tuning, 0x70) * kPercent * max;           // tuning +0x70 x [0x820536ec] x tuning +0x10
    if (!(g_meter.value < high)) fire(0x87);
    else fire(0x88);
    // 0x823d7f00..0x823d7f14: (*0x82efc780)->vtbl[0xa4]() = camera manager +0x7c |= 2. 0.14 [Look] CameraFlag (0.20:
    // default 1 = TU; 0 = not called as 0.13-0.19): PC manager 0xe804f0, its vtable slot 0xa4 = tru+0x1eb200 (+0x80 |= 2)
    if (g_cameraFlag) StartCameraFlag();
    g_meter.startValue = g_meter.value;
    g_meter.flags |= 1;
    int sent = BroadcastPowerMessage(0x1f4);                    // 0x823d7f18..0x823d7fa0
    g_meter.startTime = *kTuClock;                    // 0.11: TU +0x3c = [0x82efb528] = PC 0xe7f158
    Log(2, "shadow power ON (meter %.1f)", g_meter.value);
    if (g_lookOk && g_lookEnabled) {
        if (InterlockedIncrement(&g_lookStarts) == 1)
            Log(1, "shadow look on: first start, player events%s fired (TU 0x823d7d40 -> 0x82418158 = tru+0x318780), "
                   "message 0x1f4 to %d instances", n ? fired : " - none (no player or not doppelganger mode)", sent);
        else
            Log(2, "shadow look on: player events%s, message 0x1f4 to %d instances", n ? fired : " - none (no player or not doppelganger mode)",
                sent);
    }
}

// 0x823d7fb8 (request cleared: both ramps back to 1.0 in 33 ms)
void StopPower(const char *why) {
    if (!(g_meter.flags & 1)) return;
    // 0.9: flag 0x40 -> 0x823d9438 (Clear40, translated with [Look] AdrenalineMode); flag 2 -> 0x823d9050 (0.14: the
    // strike look off, [Look] StrikeLook; flag 2 is set only by the shadow strike 0x823d8978 = TruShadowCombat)
    if (g_meter.flags & 0x40) Clear40();
    if (g_strikeLook && (g_meter.flags & 2)) StrikeLookOff();
    g_meter.request[0][0] = g_meter.request[0][1] = kNoRequest;
    Selector();
    // 0.8: 0x823d7ffc..0x823d8068 - event 0x33, then 0x7e (ran empty, flag 0x200) or 0x82
    bool fired33 = FireEvent(0x33);
    bool left = kZero < g_meter.value;
    if (!left) g_meter.flags |= 0x200;
    int second = left ? 0x82 : 0x7e;
    bool fired2 = FireEvent(second);
    g_meter.flags &= ~1u;
    g_meter.startValue = kMeterStart;
    int sent = BroadcastPowerMessage(0x1f5);                    // 0x823d8080..
    g_meter.startTime = *kTuClock;                    // 0.11: TU +0x3c = [0x82efb528] = PC 0xe7f158
    Log(2, "shadow power OFF (%s, meter %.1f)", why, g_meter.value);
    if (g_lookOk && g_lookEnabled)
        Log(2, "shadow look off: player events%s%s%s, message 0x1f5 to %d instances", fired33 ? " 0x33" : "",
            fired2 ? (left ? " 0x82" : " 0x7e") : "", (fired33 || fired2) ? "" : " - none (no player or not doppelganger mode)", sent);
}

// 0x823d81a0
void Refill(const BYTE *tuning, float frames) {
    if (!tuning || (g_meter.flags & 0x90)) return;
    float before = g_meter.value;
    float dt = frames * kPerSecond;
    const bool alternate = false;       // game state +0xc94 != 0 (player state, PC offset not mapped) -> tuning +0x1c
    if (!alternate) {
        if (g_meter.delay <= kZero) {
            g_meter.value = Tune(tuning, kTuneRefill) * dt + before;
        } else {
            g_meter.delay -= dt;
            g_meter.value = Tune(tuning, kTuneRefillDelayed) * dt + before;
        }
    } else {
        g_meter.value = Tune(tuning, kTuneRefillAlt) * dt + before;
    }
    float max = Tune(tuning, kTuneMax);
    if (g_meter.value < max) {
        ShowMeter(g_meter.value / max);
    } else {
        g_meter.value = max;
        if (before < max) Log(3, "meter full");              // sound 0x7c not ported
        g_meter.delay = kZero;
    }
    // not ported: sounds 0x7f (crossing tuning +0x28), 0x85 / 0x86 (crossing +0x70 percent of max)
    if (Tune(tuning, kTuneHigh) <= g_meter.value) g_meter.flags |= 8;
}

// 0x823d8380
void Drain(const BYTE *tuning, float amount) {
    if (!tuning) return;
    float max = Tune(tuning, kTuneMax);
    float value = g_meter.value - amount;
    if (g_infinite) {                   // 0.23 [Meter] Infinite=1: the drain leaves the meter at max (amount only counted)
        value = max;
        ++g_infDrains;
        g_infHeld += amount;
    }
    if (max - value < 0.0f) value = max;
    if (value < 0.0f) value = kZero;
    g_meter.value = value;
    ShowMeter(value / max);
    if (g_meter.value < Tune(tuning, kTuneHigh)) g_meter.flags &= ~8u;
    // not ported: sounds 0x7d (crossing tuning +0x30), 0x85 / 0x86
}

// 0.23 [Meter] Infinite=1 (not a TU function): called by the tick on the game thread before its button / drain /
// refill block - the meter is set to max as a finished Refill leaves it (value = tuning +0x10, delay 0, flag 8 when
// tuning +0x2c <= value), the HUD bar once to full. Flag 0x200 ("ran empty") is left to CanStart, which clears it
// because the value is above tuning +0x28.
void InfiniteHold(const BYTE *tuning) {
    if (!g_infinite || !tuning) return;
    const float max = Tune(tuning, kTuneMax);
    if (g_meter.value == max) return;
    const float before = g_meter.value;
    g_meter.value = max;
    g_meter.delay = kZero;
    if (Tune(tuning, kTuneHigh) <= g_meter.value) g_meter.flags |= 8;
    ShowMeter(1.0f);
    const LONG n = ++g_infFills;
    Log(n == 1 ? 1 : 3, "0.23 infinite meter: filled %.1f -> %.1f (tuning +0x10; power %s, flags 0x%03lx, fill %ld)", before,
        max, (g_meter.flags & 1) ? "on" : "off", g_meter.flags, n);
}

// 0x823d7a10 as translated up to 0.8 (kept for [ShadowPower] LegacyPadStart=1): runs in every level, without the
// TU's doppelganger / cinematic gates (on the Xbox called once per frame from the player update 0x824126d8; here from
// the pad poll, once per advance of the game clock). 0.9's MeterTick (below) is the TU path.
void LegacyMeterTick(bool held) {
    const BYTE *tuning = FindTuning();
    g_tuning = tuning;
    InfiniteHold(tuning);                                   // 0.23: [Meter] Infinite=1 (nothing when 0)
    // not ported: stop on cinematic / 0x829ca6da, zone query 0x412 (flag 0x80), the looping sound, effects
    // 0x823d77f0 / 0x823d94f8 (blur), the 0x82efb514 bit, the timed request +0x38
    float frames = *kFrameTime;
    if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
    if (!(g_meter.flags & 0x90)) {
        if (held) {
            if (!g_meter.latch && CanStart(tuning)) {
                StartPower(tuning);
                g_meter.latch = 1;
            } else {
                g_meter.latch = 1;                            // sound 0x80 (refused) not ported
            }
        } else if (g_meter.latch == 1) {
            if (g_meter.flags & 1) StopPower("released");
            g_meter.latch = 0;
        }
        if (!(g_meter.flags & 1)) {
            Refill(tuning, frames);
        } else {
            if (kZero < g_meter.value && tuning) Drain(tuning, frames * kPerSecond * Tune(tuning, kTuneDrain));
            if (!(kZero < g_meter.value)) {
                g_meter.flags |= 0x200;
                StopPower("meter empty");
            }
        }
    }
    // 0x823d7cf8.. (outside the 0x90 test): the timed request of condition 2401 counts down in unscaled frames;
    // at 0 slot 4 is cleared and the selector runs
    if (kZero < g_meter.requestTimer) {
        g_meter.requestTimer = g_meter.requestTimer - frames;
        if (g_meter.requestTimer <= kZero) {
            g_meter.request[4][0] = g_meter.request[4][1] = kNoRequest;
            Selector();
            g_meter.requestTimer = kZero;
            Log(2, "timed request (2401) ended");
        }
    }
}

void MeterTick(bool padHeld);                // 0.9: the TU tick (defined below)

XInputGetStateFn g_realXInput = nullptr;    // the real XInputGetState (xinput* module), for the re-entry guard
__declspec(thread) int g_inPadHook = 0;

// ---- 0.17: the buttons as the game gets them (project doc Befund-TruShadowPower-017-0611.md) ----
// g_withheld: per pad, the buttons the real pad holds but the game did not get (TruMenu's neutral pad of menu / ring,
// the quick bar's LB / RB / D-pad) - ignored until the pad releases them.
// 0.19 (project doc Befund-Padkette-StartView-0711.md): no re-wrap over TruMenu / TruLink any more (the 0.17 g_inner
// path is gone); what TruMenu keeps from the game comes from its export TruMenuPadBlock (TruMenu 0.21.1+), resolved
// by the hook thread, whatever the order of the hooks.
typedef DWORD(__cdecl *PadBlockFn)(DWORD pad);
volatile PadBlockFn g_padBlock = nullptr;   // TruMenu.asi's TruMenuPadBlock (null = not loaded / older TruMenu)
bool g_menuInputOk = false;                 // [ShadowPower] MenuInput=1 and the pad poll code verified (CheckPadPoll)
WORD g_withheld[4] = {0, 0, 0, 0};
bool g_withheldOn = false;                  // a suppression burst is running (any pad)
WORD g_withheldMask = 0;                    // buttons of the running burst (for the log)
LONG g_withheldBursts = 0, g_withheldPolls = 0;
DWORD g_withheldTick = 0;
const LONG kWithheldBurstLog = 64;          // bursts logged at LogLevel 1, later ones at 2

// buttons of g_buttons the game got in this poll, minus the withheld ones. `state` is the pad after every hook inside
// this one (masked if TruMenu is inside, raw if TruMenu is outside); 0.19: TruMenuPadBlock names what TruMenu keeps
// from the game right now, so the game's view is `state` minus that mask in either order. The pad's own view is a
// second read of the real XInputGetState, compared only when both carry the same packet number (the same controller
// state - TruMenu keeps the packet number when it masks or neutralises); it is needed when TruMenu is inside this
// plugin (a neutral pad hides which buttons are held).
WORD GameButtons(DWORD index, DWORD result, const PadState *state) {
    if (result != ERROR_SUCCESS || !state) {
        g_withheld[index] = 0;
        return 0;
    }
    WORD seen = static_cast<WORD>(state->wButtons & g_buttons);
    if (!g_menuInputOk) return seen;
    PadBlockFn padBlock = g_padBlock;
    WORD block = padBlock ? static_cast<WORD>(padBlock(index) & g_buttons) : 0;   // 0.19: TruMenu keeps these
    WORD game = static_cast<WORD>(seen & ~block);
    XInputGetStateFn real = g_realXInput;
    PadState pad = {};
    if (real && real(index, &pad) == ERROR_SUCCESS && pad.dwPacketNumber == state->dwPacketNumber) {
        WORD held = static_cast<WORD>(pad.wButtons & g_buttons);
        g_withheld[index] = static_cast<WORD>((g_withheld[index] | (held & ~game)) & held);   // set, or released
    } else {
        g_withheld[index] = static_cast<WORD>(g_withheld[index] | (seen & block));   // other packet: only add
    }
    return static_cast<WORD>(game & ~g_withheld[index]);
}

// one line when a suppression burst starts, one when every withheld button is released (never per frame)
void WithheldLog() {
    WORD any = static_cast<WORD>(g_withheld[0] | g_withheld[1] | g_withheld[2] | g_withheld[3]);
    if (any && !g_withheldOn) {
        g_withheldOn = true;
        g_withheldMask = any;
        g_withheldPolls = 0;
        g_withheldTick = GetTickCount();
        LONG burst = ++g_withheldBursts;
        if (burst <= kWithheldBurstLog || g_logLevel >= 2)
            Log(burst <= kWithheldBurstLog ? 1 : 2,
                "pad input suppressed: buttons 0x%04x held on the pad but not passed to the game (TruMenu menu / ring / "
                "quick bar) - the power ignores them until they are released (power %s, meter %.1f; burst %ld%s)", any,
                (g_meter.flags & 1) ? "on" : "off", g_meter.value, burst,
                burst == kWithheldBurstLog ? ", later bursts at LogLevel 2" : "");
    } else if (any) {
        g_withheldMask |= any;
    } else if (g_withheldOn) {
        g_withheldOn = false;
        if (g_withheldBursts <= kWithheldBurstLog || g_logLevel >= 2)
            Log(g_withheldBursts <= kWithheldBurstLog ? 1 : 2,
                "pad input resumed: suppressed buttons 0x%04x released after %lu ms (%ld polls) - they count again",
                g_withheldMask, GetTickCount() - g_withheldTick, g_withheldPolls);
    }
    if (g_withheldOn) ++g_withheldPolls;
}

void Slot6ReadSwitch();                 // 0.21: [TimeScale] TranslateSlot6 at run time (defined below)
void InfiniteReadSwitch();              // 0.23: [Meter] Infinite at run time (defined below)
void CamTraceReadSwitch();              // 0.25: [Camera] Trace at run time (defined below)
void TimeStepReadSwitch();              // 0.27: [Camera] ShakeTuTimeStep / [Player] TuTimeStep at run time (below)
volatile SHORT g_padRx = 0, g_padRy = 0;   // 0.25 camera trace: pad 0 as the pad hook got it
volatile WORD g_padButtons = 0;

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    if (g_inPadHook)                            // another plugin's hook called back into us: break the loop
        return g_realXInput ? g_realXInput(index, state) : ERROR_DEVICE_NOT_CONNECTED;   // 0.19: as 0.16
    g_inPadHook = 1;
    DWORD result = g_original ? g_original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    g_inPadHook = 0;
    if (index > 3) return result;
    if (index == 0 && result == 0 && state) {   // 0.25 camera trace: pad 0 as this hook got it (read only)
        g_padRx = state->sThumbRX;
        g_padRy = state->sThumbRY;
        g_padButtons = state->wButtons;
    }
    WORD before = g_lastButtons[index];
    g_lastButtons[index] = GameButtons(index, result, state);     // 0.17: as the game gets them (0.16: state only)
    WithheldLog();
    if (g_lastButtons[index] != before)
        Log(3, "pad %lu buttons 0x%04x (was 0x%04x)", index, g_lastButtons[index], before);
    DWORD clock = *kGameClock;
    if (clock == g_lastClock) return result;                  // same frame (another pad) or game clock stopped
    g_lastClock = clock;
    bool held = false;
    for (int i = 0; i < 4; ++i) held = held || g_lastButtons[i] != 0;
    Slot6ReadSwitch();                          // 0.21: once per game frame, reads the ini at most once per second
    InfiniteReadSwitch();                       // 0.23: the same (game thread, before the tick that uses it)
    CamTraceReadSwitch();                       // 0.25: [Camera] Trace / TraceInterval, the same
    TimeStepReadSwitch();                       // 0.27: only when patched at the start, the same
    MeterTick(held);
    return result;
}

// true when the address lies in an xinput*.dll (the real XInputGetState, not another plugin's hook)
bool InXInputModule(LONG address) {
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(static_cast<LONG_PTR>(address)), &module))
        return false;
    char path[MAX_PATH] = {0};
    if (!GetModuleFileNameA(module, path, MAX_PATH)) return false;
    const char *name = strrchr(path, '\\');
    name = name ? name + 1 : path;
    return _strnicmp(name, "xinput", 6) == 0;
}

// 0.17: file name of the module that holds the address ("?" if none)
void ModuleBaseName(LONG address, char *name, size_t size) {
    strncpy_s(name, size, "?", _TRUNCATE);
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(static_cast<LONG_PTR>(address)), &module))
        return;
    char path[MAX_PATH] = {0};
    if (!GetModuleFileNameA(module, path, MAX_PATH)) return;
    const char *base = strrchr(path, '\\');
    strncpy_s(name, size, base ? base + 1 : path, _TRUNCATE);
}

// The game fills the pad pointer itself (GetProcAddress) - wait for it and chain in front of whatever is there
// (the real XInputGetState or another of our plugins: TruLink, TruMenu). Re-hook later only when the slot holds the
// real XInputGetState again (the game rewrote it, e.g. after a device change) - never just because it is "not ours",
// or two plugins would keep re-hooking each other.
// 0.19: the 0.17 re-wrap (over TruMenu.asi, and over TruLink.asi while innermost) is gone - the rule above holds for
// every owner again; a foreign hook that took the slot over this plugin is left in place with one log line per owner.
// [ShadowPower] MenuInput=1: the thread also resolves TruMenu.asi's export TruMenuPadBlock (GameButtons).
void ResolvePadBlock(DWORD hookedTick) {
    static bool missingLogged = false, absentLogged = false;
    if (!g_menuInputOk || g_padBlock || missingLogged) return;
    HMODULE menu = GetModuleHandleA("TruMenu.asi");
    if (!menu) {
        if (!absentLogged && hookedTick && GetTickCount() - hookedTick > 30000) {
            absentLogged = true;
            Log(1, "0.19 menu input: TruMenu.asi not loaded 30 s after the pad hook - LB / RB as the pad chain hands them "
                   "on (still looking for it)");
        }
        return;
    }
    PadBlockFn fn = reinterpret_cast<PadBlockFn>(GetProcAddress(menu, "TruMenuPadBlock"));
    if (!fn) {
        missingLogged = true;
        Log(1, "0.19 menu input: TruMenu.asi has no TruMenuPadBlock export (older than 0.21.1) - only the second pad read "
               "is left: LB / RB of TruMenu's quick bar may start the power when TruMenu sits outside this plugin");
        return;
    }
    g_padBlock = fn;
    Log(1, "0.19 menu input: TruMenu.asi's TruMenuPadBlock at 0x%08lx - LB / RB TruMenu keeps from the game are ignored "
           "until released, whatever the order of the pad hooks (no re-wrap)", reinterpret_cast<DWORD>(fn));
}

DWORD WINAPI HookThread(LPVOID) {
    volatile LONG *slot = reinterpret_cast<volatile LONG *>(kPadPointer);
    bool hookedOnce = false;
    DWORD hookedTick = 0;                       // 0.19: first hook (for the "TruMenu not loaded" note)
    LONG lastForeign = 0;                       // last foreign owner logged
    for (int waited = 0; !g_stop; ++waited) {
        ResolvePadBlock(hookedTick);            // 0.19
        if (!g_realXInput) {                    // resolve the real one for the re-entry guard
            const char *dlls[] = {"xinput1_3.dll", "xinput9_1_0.dll", "xinput1_4.dll"};
            for (int d = 0; d < 3 && !g_realXInput; ++d) {
                HMODULE xinput = GetModuleHandleA(dlls[d]);
                if (xinput)
                    g_realXInput = reinterpret_cast<XInputGetStateFn>(GetProcAddress(xinput, "XInputGetState"));
            }
        }
        LONG current = *slot;
        LONG ours = static_cast<LONG>(reinterpret_cast<LONG_PTR>(&PadHook));
        if (current != 0 && current != ours && (!hookedOnce || InXInputModule(current))) {
            if (InXInputModule(current)) g_realXInput = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            g_original = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            if (InterlockedCompareExchange(slot, ours, current) == current) {
                hookedOnce = true;
                if (!hookedTick) hookedTick = GetTickCount() | 1;
                lastForeign = 0;
                Log(1, "pad pointer 0x%08lx hooked (previous 0x%08lx%s)", kPadPointer, current,
                    g_realXInput && current == reinterpret_cast<LONG>(g_realXInput) ? ", XInputGetState" : ", another hook");
            }
        } else if (current != 0 && current != ours && current != lastForeign) {
            char owner[MAX_PATH];
            ModuleBaseName(current, owner, sizeof(owner));
            lastForeign = current;
            Log(1, "0.19 pad chain: pad pointer now 0x%08lx (%s) - left in place (it calls this plugin; no re-wrap since "
                   "0.19)", current, owner);
        } else if (current == 0 && waited == 600) {
            Log(1, "pad pointer still empty after 60 s - still waiting");
        }
        Sleep(current == ours ? 1000 : 100);
    }
    return 0;
}

// ---- 0.4: title-update conditions of Lara's link array that read the meter (translated) ----
// Called by the state machine on the game thread (cdecl, like every PC condition handler: agent, cache, record;
// result in al). The meter / tuning they read are the plugin's translation of the TU meter object (gameTracker+0x508)
// and of 0x82415518. The TU tests gameTracker+0x1244 (doppelganger player) first: these ids occur only in the DLC 2
// player's chart (doppelganger_casual.drm), whose init sets that byte on the Xbox (DoppelgangerInit) - the PC has no
// such field; the test is therefore met whenever the chart asks (named gap, docs Befund-Felsrinne).

typedef char(__cdecl *CondPredFn)(const BYTE *record);
typedef char(__cdecl *CondTemplateFn)(void *agent, void *cache, const BYTE *record, CondPredFn pred);
typedef char(__cdecl *CondCompareFn)(void *agent, void *cache, const BYTE *record, float value, int mode);

void LogCond(int slot, int id, const BYTE *record, int result) {
    if (InterlockedIncrement(&g_condCalls[slot]) == 1)
        Log(1, "condition %d is now evaluated (record value %d, flags %u) -> %d", id,
            *reinterpret_cast<const SHORT *>(record + 4), record[6], result);
    if (InterlockedExchange(&g_condLast[slot], result + 1) != result + 1)
        Log(2, "condition %d -> %d (meter %.1f, flags 0x%03lx)", id, result, g_meter.value, g_meter.flags);
}

// Xbox 0x8246e498 (predicate of 1056): meter fraction >= tuning +0x70 x 0.01 and the power active (flags bit 0)
char __cdecl Pred1056(const BYTE *) {
    const BYTE *tuning = g_tuning;                        // 0x82415518
    if (!tuning) return 0;
    double threshold = static_cast<double>(Tune(tuning, 0x70) * 0.01f);       // [0x820536ec] = 0.01
    double fraction = static_cast<double>(g_meter.value / Tune(tuning, kTuneMax));   // 0x823d8548
    if (fraction < threshold || !(g_meter.flags & 1)) return 0;
    return 1;
}

// Xbox 0x8246e528: r6 = 0x8246e498; b 0x82487718 (the template) - PC template tru+0x382d70
char __cdecl Cond1056(void *agent, void *cache, const BYTE *record) {
    char r = 0;
    __try {
        r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &Pred1056);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    LogCond(6, 1056, record, r ? 1 : 0);
    return r;
}

// Xbox 0x824703d0 (1049..1054): key must be 20; 1049-1051 compare the meter value (+8), 1052-1054 the fraction x 100
// ([0x8207d53c]); modes 0 / 1 / 2 (equal, >=, <=) through 0x82487348 = PC tru+0x383bd0; other ids: 0.0, mode 0
char __cdecl CondMeter(void *agent, void *cache, const BYTE *record) {
    int id = *reinterpret_cast<const SHORT *>(record + 2);
    int slot = (id >= 1049 && id <= 1054) ? id - 1049 : 7;
    char r = 0;
    const BYTE *tuning = g_tuning;
    if (tuning && *reinterpret_cast<const WORD *>(record) == 20) {   // TU: +0x1244, +0x508 set; record key 0x14
        unsigned idx = static_cast<unsigned>(id - 1049);
        float value = kZero;
        int mode = 0;
        if (idx <= 2) {
            value = g_meter.value;
        } else if (idx <= 5) {
            value = static_cast<float>(static_cast<double>(g_meter.value / Tune(tuning, kTuneMax)) * 100.0);
        }
        if (idx == 1 || idx == 4) mode = 1;
        else if (idx == 2 || idx == 5) mode = 2;
        __try {
            r = reinterpret_cast<CondCompareFn>(kCondCompare)(agent, cache, record, value, mode);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    LogCond(slot, id, record, r ? 1 : 0);
    return r;
}

// ---- 0.5: title-update states / conditions / activities of Lara (docs Befund-Schattenkraft "TU states for Lara") ----
// PC building blocks, each verified by its bytes at load (kTuBlocks below). thiscall functions are called through
// __fastcall pointers (ecx = this, edx unused, the rest on the stack, callee cleans - the thiscall layout).
typedef void *(__fastcall *ParamNodeFn)(void *agent, int, int id);              // 0x783f50 = TU 0x82482d28
typedef void *(__fastcall *ParamFindFn)(void *node, int, int id);               // 0x784b30 = TU 0x82488680
typedef float(__cdecl *ParamFloatFn)(const void *record);                       // 0x783680 = TU 0x82484a08
typedef char(__fastcall *ParamBoolFn)(void *node, int, int id, char *out);      // 0x784c20 = TU 0x823d7230 tail
typedef void *(__cdecl *AnimFramesFn)(int *out, void *agent);                   // 0x75f3e0 = TU 0x82463af8 (flag 0)
typedef void(__fastcall *ChanMoveFn)(void *chan, int, const float *vec, float frames);   // 0x438d70 mode 1 /
                                                                                          // 0x438d00 mode 2
typedef void(__fastcall *ChanMoveAnimFn)(void *chan, int, const float *vec);    // 0x43e400 mode 1, frames of the anim

const DWORD kParamNode = 0x00783f50, kParamFind = 0x00784b30, kParamFloat = 0x00783680, kParamBool = 0x00784c20;
const DWORD kAnimFrames = 0x0075f3e0, kChanMode1 = 0x00438d70, kChanMode1Anim = 0x0043e400, kChanMode2 = 0x00438d00;
const DWORD kGameTrackerPtr = 0x00fadb58;   // TU 0x829892b0
const DWORD kPlayerPtr = 0x00e7f094;        // TU 0x82efb464 (player instance; frame-time block + 0xc)

struct CodeCheck { DWORD address; const char *bytes; };   // hex string, spaces ignored
const CodeCheck kTuBlocks[] = {
    {0x00783f50, "56 8bf1 8b8620050000 85c0"},                          // param node, cache agent +0x520
    {0x00784b30, "0fb701 53 56 57 8b7c2410 33db"},                       // param find
    {0x00783680, "51 8b442408 d9ee 0fbf4802"},                           // float value (switch on type +2)
    {0x00783770, "8b542404 0fbf4a02 32c0 83e902"},                       // bool value (types 2 / 0x10 / 0x29)
    {0x00784c20, "8b442404 50 e806ffffff 85c0"},                         // bool param of a node
    {0x0075f3e0, "56 57 8b7c2410 681b010000 681b010000"},                // anim frame count (param 0x11b)
    {0x0075f470, "83ec08 56 57 8b7c241c 8b4704 0fb77002 8b4f08 69f620030000 8b9180020000 037214"},  // channel
    {0x00438970, "0fb681f8000000 6bc070 038180000000"},                  // anim entry: chan +0x80 + 0x70 x +0xf8
    {0x00438d70, "55 8bec 83e4f0 83ec10 d9450c 8bc1 8b4d08 0f2801 0f294010"}, {0x00438db1, "c7402401000000"},
    {0x0043e400, "55 8bec 83e4f0 83ec20 8bc1 8b8880000000"}, {0x0043e464, "c7402401000000"},
    {0x00438d00, "55 8bec 83e4f0 83ec10 f30f100534118400 d9450c"}, {0x00438d59, "c7402402000000"},
    {0x00741764, "8b0d94f0e700 0f8599010000 8b8190000000"},               // player +0x90 matrix (row +0x10)
    {0x00764e79, "8b0d58dbfa00"}, {0x00764e85, "39b11c030000"}, {0x00764e99, "80b92003000000"},  // gt +0x31c/+0x320
    {0x0075e0e0, "a158dbfa00 8b8804050000"},                             // gt +0x504 = player instance
    {0x006457a0, "c3"},                                                  // print stub (activity 1039)
};

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[200];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

bool g_tuStatesOk = false;          // all kTuBlocks verified
volatile LONG g_gt1280 = 0;         // TU-only gameTracker+0x1280 (move step count of 244 / 245, read by 1048) - the
                                    // PC uses +0x1280 for other data, so the translation keeps it here; 0.12: exported
                                    // (meter interface v3) - TruShadowCombat's state 244 writes the same variable

BYTE *GameTracker() { return *reinterpret_cast<BYTE *const *>(kGameTrackerPtr); }

// agent motion channel: (agent+8)->+0x280->+0x14 + 0x320 x (agent+4)->+2 (TU and PC tru+0x35f470)
BYTE *Channel(const BYTE *agent) {
    const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
    const BYTE *anim = *reinterpret_cast<const BYTE *const *>(instance + 0x280);
    WORD index = *reinterpret_cast<const WORD *>(*reinterpret_cast<const BYTE *const *>(agent + 4) + 2);
    return *reinterpret_cast<BYTE *const *>(anim + 0x14) + 0x320 * index;
}

// animation entry of a channel: chan->+0x80 + 0x70 x chan->+0xf8 (u8) - TU inline, PC tru+0x38970
const BYTE *AnimEntry(const BYTE *chan) {
    return *reinterpret_cast<const BYTE *const *>(chan + 0x80) + 0x70 * chan[0xf8];
}

// TU 0x82482d28 + 0x82488680 + 0x82484a08. The TU does not test the record for null before reading its type (a
// missing parameter would read guest address 2); a missing record answers 0.0 here - the getter's default value.
float ParamFloat(void *agent, int id) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    if (!node) return kZero;
    void *record = reinterpret_cast<ParamFindFn>(kParamFind)(node, 0, id);
    if (!record) {
        static volatile LONG missing = 0;
        if (InterlockedIncrement(&missing) <= 5) Log(1, "state parameter 0x%x not in the current state (0.0 used)", id);
        return kZero;
    }
    return reinterpret_cast<ParamFloatFn>(kParamFloat)(record);
}

// TU 0x823d7230(agent, id, &out) = 0x82482d28 + 0x82488680 + (record ? out = 0x82484b88(record))
void ParamBool(void *agent, int id, char *out) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, id, out);
}

// first-call / rate-limited logging of the new handlers (proves in a test that a state / condition is entered)
struct Probe { const char *name; volatile LONG calls; DWORD lastTick; LONG lastLogged; };
Probe g_probes[] = {
    {"state 243 slot 0 (move to gameTracker+0x1270)"}, {"state 245 slot 0 (move tuning +0x6c along player row)"},
    {"state 245 slot 3 (stop at the current position)"}, {"state 1018 slot 0 (meter cost / world request)"},
    {"state 1018 slot 1 (meter cost / world request)"}, {"state 1018 slot 2 (clear request 5)"},
    {"condition 1048 (step count x 100 <= animation time)"}, {"condition 2401 (timed time-scale request)"},
    {"activity 1009 (player +0xc8 = record +4)"}, {"activity 1039 (print stub)"}};
enum { kP243, kP245a, kP245d, kP1018a, kP1018b, kP1018c, kP1048, kP2401, kP1009, kP1039 };

void Hit(int probe, const char *fmt = nullptr, double a = 0.0, double b = 0.0, double c = 0.0) {
    Probe &p = g_probes[probe];
    LONG n = InterlockedIncrement(&p.calls);
    char detail[160] = "";
    if (fmt) _snprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, a, b, c);
    if (n == 1) {
        Log(1, "%s is now entered%s%s", p.name, detail[0] ? ": " : "", detail);
        p.lastTick = GetTickCount();
        p.lastLogged = 1;
        return;
    }
    DWORD now = GetTickCount();
    if (g_logLevel >= 3 || (g_logLevel >= 2 && now - p.lastTick >= 500)) {
        Log(2, "%s (call %ld, %ld since last line)%s%s", p.name, n, n - p.lastLogged, detail[0] ? ": " : "", detail);
        p.lastTick = now;
        p.lastLogged = n;
    }
}

// state 243, slot 0 = TU 0x82464180: v1 = gameTracker+0x1270; b 0x82463eb8 (TU-new). 0x82463eb8: unless the bool
// parameter 0x11d is set: n = 0x82463af8(agent, flag 0) (= PC 0x75f3e0, parameter 0x11b); n > 0 -> channel +0x10 =
// v1, +0x00 = 0 vector [0x8207db30], +0x20 = n, +0x24 = 1 (= PC 0x438d70); else the same with the animation's frame
// count (+0x80 -> +0x24: s16 +0x34 x +0x32) (= PC 0x43e400).
void __cdecl State243(BYTE *agent) {
    __try {
        float *target = reinterpret_cast<float *>(GameTracker() + 0x1270);
        BYTE *chan = Channel(agent);
        char keep = 0;
        ParamBool(agent, 0x11d, &keep);
        if (keep) { Hit(kP243, "parameter 0x11d set - nothing done"); return; }
        int n = 0;
        reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
        if (n > 0)
            reinterpret_cast<ChanMoveFn>(kChanMode1)(chan, 0, target, static_cast<float>(n));
        else
            reinterpret_cast<ChanMoveAnimFn>(kChanMode1Anim)(chan, 0, target);
        Hit(kP243, "frames %.0f, target %.1f %.1f", n, target[0], target[1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 243: access fault - skipped");
    }
}

// TU "busy" test of 245 (both slots): gameTracker+0x31c set, byte +0x320 set and (+0x31c)->u16 +0x40 == 2 or
// u16 +0x32 == 3
bool Busy245(const BYTE *gt) {
    if (!gt) return false;
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(gt + 0x31c);
    if (!p || !gt[0x320]) return false;
    return *reinterpret_cast<const WORD *>(p + 0x40) == 2 || *reinterpret_cast<const WORD *>(p + 0x32) == 3;
}

// state 245, slot 0 = TU 0x824645d8: unless busy: target = player position (+0x20) + (row +0x10 of the player's
// matrix (+0x90) x -1.0) x tuning +0x6c; length = |target - position| (vrsqrtefp + one Newton step on the Xbox, 0
// for 0); n = (int)floor(length / tuning +0x68); n > 2: gameTracker+0x1280 = n, frames = n x 100.0; else +0x1280 = 2,
// frames = 200.0; channel +0x00 = target, +0x10 = (0, 0, 0, 1), +0x20 = frames, +0x24 = 2 (= PC 0x438d00).
void __cdecl State245(BYTE *agent) {
    __try {
        BYTE *gt = GameTracker();
        if (Busy245(gt)) { Hit(kP245a, "busy (gameTracker+0x31c) - nothing done"); return; }
        BYTE *chan = Channel(agent);
        const BYTE *tuning = gt ? g_tuning : nullptr;
        if (!tuning) { Log(1, "state 245: no tuning - skipped (the Xbox would read address 0x68)"); return; }
        float speed = Tune(tuning, kTuneMoveSpeed);
        float distance = Tune(tuning, kTuneMoveDistance);
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(kPlayerPtr);
        const float *row = reinterpret_cast<const float *>(*reinterpret_cast<const BYTE *const *>(player + 0x90) + 0x10);
        const float *position = reinterpret_cast<const float *>(player + 0x20);
        __declspec(align(16)) float target[4];
        for (int i = 0; i < 4; ++i) target[i] = (row[i] * kNoRequest) * distance + position[i];   // [0x82052664]
        float d[3] = {target[0] - position[0], target[1] - position[1], target[2] - position[2]};
        float squared = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
        float length = squared == kZero ? squared : sqrtf(squared);
        int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(length / speed))));
        float frames;
        if (n > 2) {
            g_gt1280 = n;
            frames = static_cast<float>(n) * kHundred;
        } else {
            g_gt1280 = 2;
            frames = kShortMove;
        }
        reinterpret_cast<ChanMoveFn>(kChanMode2)(chan, 0, target, frames);
        // direction of the move (-row): (0, 0, +-1) = vertical (wall run), otherwise horizontal
        Hit(kP245a, "direction %.2f %.2f %.2f", -row[0], -row[1], -row[2]);
        Log(2, "state 245: steps %d, length %.1f, frames %.0f, from %.1f %.1f %.1f to %.1f %.1f %.1f", static_cast<int>(g_gt1280), length,
            frames, position[0], position[1], position[2], target[0], target[1], target[2]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 245: access fault - skipped");
    }
}

// state 245, slot 3 = TU 0x824647d0: only when busy: channel +0x00 = instance (agent+8) position +0x20, +0x10 =
// (0, 0, 0, 1), +0x20 = animation entry +0x28 - 1.0, +0x24 = 2 (= PC 0x438d00)
void __cdecl State245Slot3(BYTE *agent) {
    __try {
        if (!Busy245(GameTracker())) return;
        BYTE *chan = Channel(agent);
        const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
        float frames = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28) - kOne;
        reinterpret_cast<ChanMoveFn>(kChanMode2)(chan, 0, reinterpret_cast<const float *>(instance + 0x20), frames);
        Hit(kP245d, "frames %.2f", frames);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 245 slot 3: access fault - skipped");
    }
}

// state 1018, slots 0 and 1 = TU 0x82465078 (gameTracker+0x1244 / +0x508 taken as present, see 0.4): parameters
// 0x410 (amount), 0x411 (percent), bool 0x414; amount > 0 -> Drain(amount) (0x823d8380), else percent > 0 ->
// Drain(max x percent x 0.01) (0x823d84d0); 0x414 set -> refill delay = tuning +0x24; parameter 0x413 > 0 -> world
// request slot 5 = it, else slot 5 cleared; selector.
void State1018(BYTE *agent, int probe) {
    __try {
        float amount = ParamFloat(agent, 0x410);
        float percent = ParamFloat(agent, 0x411);
        char delay = 0;
        ParamBool(agent, 0x414, &delay);
        const BYTE *tuning = g_tuning;
        if (kZero < amount) {
            Drain(tuning, amount);
        } else if (kZero < percent) {
            if (tuning) Drain(tuning, Tune(tuning, kTuneMax) * (percent * kPercent));
        }
        if (delay && tuning) g_meter.delay = Tune(tuning, kTuneDelay1018);
        float world = ParamFloat(agent, 0x413);
        if (kZero < world) {
            g_meter.request[5][1] = world;
        } else {
            g_meter.request[5][0] = g_meter.request[5][1] = kNoRequest;
        }
        Selector();
        Hit(probe, "cost %.1f / %.1f %%, world request %.3f", amount, percent, world);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1018: access fault - skipped");
    }
}
void __cdecl State1018Slot0(BYTE *agent) { State1018(agent, kP1018a); }
void __cdecl State1018Slot1(BYTE *agent) { State1018(agent, kP1018b); }

// state 1018, slot 2 = TU 0x824651c8: slot 5 cleared, selector
void __cdecl State1018Slot2(BYTE *) {
    g_meter.request[5][0] = g_meter.request[5][1] = kNoRequest;
    Selector();
    Hit(kP1018c);
}

// condition 1048 = TU 0x8246ece0 (agent; no record test, no NOT flag): true unless gameTracker+0x1280 x 100.0 >
// animation entry +0x28 of the agent's channel
char __cdecl Cond1048(BYTE *agent, void *, const BYTE *) {
    char r = 0;
    __try {
        float steps = static_cast<float>(g_gt1280) * kHundred;
        float time = *reinterpret_cast<const float *>(AnimEntry(Channel(agent)) + 0x28);
        r = steps > time ? 0 : 1;
        Hit(kP1048, "steps x 100 = %.0f, animation %.1f -> %.0f", steps, time, r);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    return r;
}

// condition 2401 = TU 0x824702b0 (always false): with the tuning: meter +0x38 = record value (s16 -> float, frames),
// slot 4 = {tuning +0x58 player, tuning +0x54 world}, selector
char __cdecl Cond2401(void *, void *, const BYTE *record) {
    __try {
        float value = static_cast<float>(*reinterpret_cast<const SHORT *>(record + 4));
        const BYTE *tuning = g_tuning;
        if (!tuning) return 0;
        g_meter.requestTimer = value;
        g_meter.request[4][0] = Tune(tuning, kTuneTimedPlayer);
        g_meter.request[4][1] = Tune(tuning, kTuneTimedWorld);
        Selector();
        Hit(kP2401, "%.0f frames, player %.3f, world %.3f", value, g_meter.request[4][0], g_meter.request[4][1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

// activity 1009 = TU 0x82472788: (gameTracker+0x504 = player instance)->+0xc8 = record +4
void __cdecl Act1009(void *, const BYTE *record) {
    __try {
        BYTE *player = *reinterpret_cast<BYTE *const *>(GameTracker() + 0x504);
        *reinterpret_cast<DWORD *>(player + 0xc8) = *reinterpret_cast<const DWORD *>(record + 4);
        Hit(kP1009, "value %.0f", static_cast<double>(*reinterpret_cast<const DWORD *>(record + 4)));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

// activity 1039 = TU 0x82455a38 = PC 0x6457a0 (an empty print function - `ret`)
void __cdecl Act1039(void *, const BYTE *) { Hit(kP1039); }

// ---- 0.7: condition 1055 = TU 0x8246e488 (r6 = predicate 0x8246e450; b 0x82487718 = PC template tru+0x382d70) ----
int g_cond1055 = 1;                       // [Conditions] Cond1055
volatile LONG g_p1055Calls = 0;
int Doppelganger();                       // 0.6, below: TruDlc2Player's doppelganger flag (TU gameTracker+0x1244)

// TU 0x8246e450: doppelganger mode -> (gameTracker+0x508)->flags bit 4 (rlwinm 0x1e = bit value 4), else
// (gameTracker+0x504)->+0x1fc bit 0x20000000 (rlwinm 3). The TU reads the meter without a null test; the plugin's meter
// always exists. Writers of flag 4 on the TU: 0x823d8a80 (set, needs flag 2) and 0x823d9050 (clear) - 0.14 ports them
// behind [Look] StrikeLook (default 0: flag 4 stays clear, the answer in DLC 2 stays 0).
char __cdecl Pred1055(const BYTE *) {
    int dg = Doppelganger();
    char r = 0;
    if (dg) {
        r = (g_meter.flags & 4) ? 1 : 0;
    } else {
        __try {
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
            r = static_cast<char>((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 29) & 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    if (InterlockedIncrement(&g_p1055Calls) == 1)
        Log(1, "condition 1055 predicate (TU 0x8246e450) first call: doppelganger %d -> %d (meter flags 0x%03lx; flag 4 "
               "comes only from the shadow look of the shadow strike, [Look] StrikeLook %d)", dg, r, g_meter.flags, g_strikeLook);
    return r;
}

char __cdecl Cond1055(void *agent, void *cache, const BYTE *record) {
    char r = 0;
    __try {
        r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &Pred1055);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    LogCond(8, 1055, record, r ? 1 : 0);
    return r;
}

// copy of Lara's table with the TU records before the closing record; the builder's push operand points at the copy
DWORD g_laraConds[(kLaraCondCount + 16) * 3];

void RegisterLaraConditions() {
    if (!g_condEnabled) { Log(1, "Lara conditions: off ([Conditions] Enabled=0)"); return; }
    if (!BytesAt(kLaraReg, kLaraRegBytes, sizeof(kLaraRegBytes)) ||
        !BytesAt(kCondTemplate, kCondTemplateBytes, sizeof(kCondTemplateBytes)) ||
        !BytesAt(kCondCompare, kCondCompareBytes, sizeof(kCondCompareBytes))) {
        Log(0, "Lara conditions: registration / template / compare code does not match - not registered");
        return;
    }
    const DWORD *table = reinterpret_cast<const DWORD *>(kLaraCondTable);
    const DWORD *end = table + kLaraCondCount * 3;
    if (end[0] != 0 || end[1] != 0 || end[2] != kCondDefaultFn || table[0] != 10) {
        Log(0, "Lara conditions: table 0x%08lx is not the expected one (%lu records + closing) - not registered",
            kLaraCondTable, static_cast<DWORD>(kLaraCondCount));
        return;
    }
    // 0.5: + 1048 and 2401 (only when the 0.5 building blocks are verified; group 2000 / 2400 as in the TU table)
    struct AddRec { DWORD id; DWORD group; const void *fn; };
    AddRec add[10] = {
        {1049, 2000, &CondMeter}, {1050, 2000, &CondMeter}, {1051, 2000, &CondMeter}, {1052, 2000, &CondMeter},
        {1053, 2000, &CondMeter}, {1054, 2000, &CondMeter}, {1056, 2000, &Cond1056}, {0, 0, nullptr}, {0, 0, nullptr},
        {0, 0, nullptr}};
    int addCount = 7;
    if (g_tuStatesOk && g_statesEnabled) {
        add[addCount++] = {1048, 2000, &Cond1048};
        add[addCount++] = {2401, 2400, &Cond2401};
    }
    bool with1055 = false;
    if (g_cond1055) { add[addCount++] = {1055, 2000, &Cond1055}; with1055 = true; }   // 0.7 (group 2000 as the TU)
    for (int i = 0; i < kLaraCondCount; ++i)
        for (int k = 0; k < addCount; ++k)
            if (table[i * 3] == add[k].id) {
                Log(0, "Lara conditions: id %lu already in the table - not registered", add[k].id);
                return;
            }
    // Precondition: every id must be in the generic registry. For an id found neither in Lara's tree nor in the
    // generic one, the loop reads a null node (tru+0x385258 -> 0x385265 cmp di,[edx] with edx = 0) - a crash. The
    // generic table is the builder's push operand tru+0x387343 (original 0x8b57e0); TruDoppelganger.asi (loaded
    // before us, alphabetical) points it at its copy with the TU ids. Register only if that copy holds all of ours.
    __try {
        DWORD generic = *reinterpret_cast<const DWORD *>(kGenericCondPush);
        if (generic == kGenericCondTable) {
            Log(0, "Lara conditions: the generic table is the original (TruDoppelganger.asi not active) - not "
                   "registered (the game would crash on ids the generic registry lacks)");
            return;
        }
        const DWORD *g = reinterpret_cast<const DWORD *>(generic);
        int found = 0;
        for (int i = 0; i < 1000 && g[i * 3] != 0; ++i)
            for (int k = 0; k < addCount; ++k)
                if (g[i * 3] == add[k].id) ++found;
        if (found != addCount) {
            Log(0, "Lara conditions: the generic table 0x%08lx holds %d of our %d ids - not registered", generic, found,
                addCount);
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "Lara conditions: generic table not readable - not registered");
        return;
    }
    memcpy(g_laraConds, table, kLaraCondCount * 3 * sizeof(DWORD));
    int n = kLaraCondCount;
    for (int k = 0; k < addCount; ++k) {
        g_laraConds[n * 3] = add[k].id;
        g_laraConds[n * 3 + 1] = add[k].group;
        g_laraConds[n * 3 + 2] = reinterpret_cast<DWORD>(add[k].fn);
        ++n;
    }
    memcpy(g_laraConds + n * 3, end, 3 * sizeof(DWORD));   // closing {0, 0, default}
    DWORD *operand = reinterpret_cast<DWORD *>(kLaraCondPush + 1);
    DWORD old = 0;
    if (!VirtualProtect(operand, 4, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "Lara conditions: VirtualProtect failed (%lu) - not registered", GetLastError());
        return;
    }
    *operand = reinterpret_cast<DWORD>(g_laraConds);
    DWORD dummy = 0;
    VirtualProtect(operand, 4, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), operand, 4);
    Log(1, "Lara conditions: 1049-1054 (meter compare), 1056 (meter >= tuning +0x70 while active)%s%s added to the link "
           "array (copy 0x%08lx, %d records; generic registry has them via TruDoppelganger)",
        addCount > (with1055 ? 8 : 7) ? ", 1048 (move steps vs animation), 2401 (timed time-scale request)" : "",
        with1055 ? ", 1055 (TU predicate 0x8246e450: doppelganger -> meter flag 4, else player +0x1fc bit 29)" : "",
        reinterpret_cast<DWORD>(g_laraConds), n);
}

// 0.5: Lara's activity and state tables get the translated TU records the same way (push operands tru+0x368b8d /
// tru+0x368b99, loops tru+0x385390 / tru+0x385600 - the state loop has the same null-node crash path for an id the
// generic registry lacks, tru+0x3856e4 -> 0x385742). Generic tables: TruDoppelganger's copies (push operands
// tru+0x38735a / tru+0x38736a). TU slot positions kept: 243 {f, 0, 0, 0, 0, 0}, 245 {f, 0, 0, g, 0, 0}, 1018 {f, f,
// g, 0, 0, 0} (TU table 0x82757948).
const DWORD kLaraActPush = 0x00768b8d, kLaraStatePush = 0x00768b99;
const BYTE kLaraActStateBytes[] = {0x68, 0x80, 0x22, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0xf7, 0xc7, 0x01, 0x00,
                                   0x68, 0x50, 0x0a, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0x5b, 0xca, 0x01, 0x00};
const DWORD kLaraActTable = 0x008b2280, kLaraStateTable = 0x008b0a50;
const int kLaraActCount = 139, kLaraStateCount = 179;
const DWORD kActClosingFn = 0x00784cf0, kStateDefaultFn = 0x00781d10;
const DWORD kGenericActPush = 0x0078735a, kGenericStatePush = 0x0078736a;
const DWORD kGenericActTable = 0x008b6650, kGenericStateTable = 0x008b4200;
DWORD g_laraActs[(kLaraActCount + 4) * 2];
DWORD g_laraStates[(kLaraStateCount + 6) * 7];

// count of `ids` present in a generic {id, n-1 words} table that is not the original; -1 if it is the original / bad
int GenericHolds(DWORD pushOperand, DWORD original, int stride, const DWORD *ids, int count) {
    __try {
        DWORD table = *reinterpret_cast<const DWORD *>(pushOperand);
        if (table == original) return -1;
        const DWORD *t = reinterpret_cast<const DWORD *>(table);
        int found = 0;
        for (int i = 0; i < 2000 && t[i * stride] != 0; ++i)
            for (int k = 0; k < count; ++k)
                if (t[i * stride] == ids[k]) ++found;
        return found;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
}

// ---- 0.6: condition 1046 (TU predicate 0x8246e400) ----
const DWORD kPred1046 = 0x007655c0;       // mov eax,[0FADB58h]; mov ecx,[eax+504h]; mov eax,[ecx+1FCh]; shr eax,15h; and al,1
const char *const kPred1046Hex = "a158dbfa00 8b8804050000 8b81fc010000 c1e815 2401 c3";
const DWORD kCond1046Push = 0x007655ec;   // condition 1046 tru+0x3655e0: push 0x7655c0 (template tru+0x382d70)
const char *const kCond1046PushHex = "68c0557600";
int g_cond1046 = 1;                       // [Conditions] Cond1046
typedef int(__cdecl *DoppelgangerFn)();
DoppelgangerFn g_doppelganger = nullptr;
int g_doppelgangerLooked = 0;
volatile LONG g_p1046Calls = 0, g_p1046Last = -1;

int Doppelganger() {
    if (!g_doppelgangerLooked) {
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_doppelganger = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        g_doppelgangerLooked = 1;
        if (!g_doppelganger)
            Log(0, "TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - condition 1046 uses the retail test only");
    }
    return g_doppelganger ? g_doppelganger() : 0;
}

char __cdecl Pred1046(const BYTE *) {
    int dg = Doppelganger();
    char r = 0;
    if (dg) {
        r = (g_meter.flags & 1) ? 1 : 0;          // meter object +4 bit 0 (the plugin's meter always exists)
    } else {
        __try {                                   // retail: (gameTracker+0x504)->+0x1fc bit 21
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
            r = static_cast<char>((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 21) & 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    LONG n = InterlockedIncrement(&g_p1046Calls);
    LONG packed = r | (dg << 1);
    if (n == 1)
        Log(1, "condition 1046 (predicate tru+0x3655c0 = TU 0x8246e400) is now evaluated: doppelganger %d -> %d (meter flags "
               "0x%03lx)", dg, r, g_meter.flags);
    else if (InterlockedExchange(&g_p1046Last, packed) != packed)
        Log(2, "condition 1046 -> %d (doppelganger %d, meter %.1f, flags 0x%03lx, call %ld)", r, dg, g_meter.value,
            g_meter.flags, n);
    if (n == 1) g_p1046Last = packed;
    return r;
}

bool WriteJump5(DWORD at, const void *to) {
    BYTE code[5] = {0xe9, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, 5);
    VirtualProtect(reinterpret_cast<void *>(at), 5, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), 5);
    return true;
}

void Patch1046() {
    if (!HexBytesAt(kPred1046, kPred1046Hex) || !HexBytesAt(kCond1046Push, kCond1046PushHex)) {
        Log(0, "condition 1046 predicate at 0x%08lx does not match - not translated", kPred1046);
        return;
    }
    if (WriteJump5(kPred1046, &Pred1046))
        Log(1, "condition 1046: title-update predicate (doppelganger mode -> meter active, else retail; 0x%08lx)", kPred1046);
    else
        Log(0, "condition 1046 not written (VirtualProtect %lu)", GetLastError());
}

bool PatchPush(DWORD operandAddress, DWORD value) {
    DWORD *operand = reinterpret_cast<DWORD *>(operandAddress);
    DWORD old = 0;
    if (!VirtualProtect(operand, 4, PAGE_EXECUTE_READWRITE, &old)) return false;
    *operand = value;
    DWORD dummy = 0;
    VirtualProtect(operand, 4, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), operand, 4);
    return true;
}

// 0.11, defined below (section "0.11")
void __cdecl State2102(BYTE *);
bool CheckState2102();
int g_state2102Enabled = 1;                 // [States] State2102

void RegisterLaraStates() {
    if (!g_statesEnabled) { Log(1, "Lara states / activities: off ([States] Enabled=0)"); return; }
    if (!g_tuStatesOk) { Log(0, "Lara states / activities: building blocks not verified - not registered"); return; }
    // RegisterLaraConditions runs first and may already have pointed the condition push (inside kLaraRegBytes) at
    // our copy - accept the original operand or that copy, all other bytes must match
    const size_t condOff = kLaraCondPush + 1 - kLaraReg;
    const DWORD condCopy = reinterpret_cast<DWORD>(g_laraConds);
    const bool regOk = BytesAt(kLaraReg, kLaraRegBytes, condOff) &&
                       BytesAt(kLaraCondPush + 5, kLaraRegBytes + condOff + 4, sizeof(kLaraRegBytes) - condOff - 4) &&
                       (BytesAt(kLaraCondPush + 1, kLaraRegBytes + condOff, 4) ||
                        BytesAt(kLaraCondPush + 1, reinterpret_cast<const BYTE *>(&condCopy), 4));
    if (!regOk || !BytesAt(kLaraActPush, kLaraActStateBytes, sizeof(kLaraActStateBytes))) {
        Log(0, "Lara states / activities: registration code does not match - not registered");
        return;
    }
    // activities
    const DWORD *acts = reinterpret_cast<const DWORD *>(kLaraActTable);
    const DWORD *actEnd = acts + kLaraActCount * 2;
    const DWORD actIds[] = {1009, 1039};
    const DWORD actFns[] = {reinterpret_cast<DWORD>(&Act1009), reinterpret_cast<DWORD>(&Act1039)};
    bool actsOk = actEnd[0] == 0 && actEnd[1] == kActClosingFn && acts[0] == 203;
    for (int i = 0; actsOk && i < kLaraActCount; ++i)
        if (acts[i * 2] == 1009 || acts[i * 2] == 1039) actsOk = false;
    int actGeneric = GenericHolds(kGenericActPush, kGenericActTable, 2, actIds, 2);
    if (!actsOk) {
        Log(0, "Lara activities: table 0x%08lx is not the expected one - not registered", kLaraActTable);
    } else if (actGeneric != 2) {
        Log(0, "Lara activities: generic table lacks the ids (%d of 2; TruDoppelganger.asi active?) - not registered",
            actGeneric);
    } else {
        memcpy(g_laraActs, acts, kLaraActCount * 2 * sizeof(DWORD));
        int n = kLaraActCount;
        for (int k = 0; k < 2; ++k, ++n) { g_laraActs[n * 2] = actIds[k]; g_laraActs[n * 2 + 1] = actFns[k]; }
        memcpy(g_laraActs + n * 2, actEnd, 2 * sizeof(DWORD));
        if (PatchPush(kLaraActPush + 1, reinterpret_cast<DWORD>(g_laraActs)))
            Log(1, "Lara activities: 1009 (player +0xc8 = record +4), 1039 (print stub) added (copy 0x%08lx, %d "
                   "records)", reinterpret_cast<DWORD>(g_laraActs), n);
        else
            Log(0, "Lara activities: VirtualProtect failed (%lu) - not registered", GetLastError());
    }
    // states
    const DWORD *states = reinterpret_cast<const DWORD *>(kLaraStateTable);
    const DWORD *stateEnd = states + kLaraStateCount * 7;
    bool statesOk = stateEnd[0] == 0 && states[0] == 2;
    for (int k = 1; statesOk && k < 7; ++k) statesOk = stateEnd[k] == kStateDefaultFn;
    for (int i = 0; statesOk && i < kLaraStateCount; ++i)
        if (states[i * 7] == 243 || states[i * 7] == 245 || states[i * 7] == 1018) statesOk = false;
    const DWORD stateIds[] = {243, 245, 1018};
    int stateGeneric = GenericHolds(kGenericStatePush, kGenericStateTable, 7, stateIds, 3);
    if (!statesOk) {
        Log(0, "Lara states: table 0x%08lx is not the expected one - not registered", kLaraStateTable);
        return;
    }
    if (stateGeneric != 3) {
        Log(0, "Lara states: generic table lacks the ids (%d of 3; TruDoppelganger.asi active?) - not registered",
            stateGeneric);
        return;
    }
    // 0.11: state 2102 (TU Lara table record at 0x82758c18: {2102, 0x824627b0, 0, 0, 0, 0, 0}) when the generic table holds it
    // and the camera code is verified
    const DWORD id2102[] = {2102};
    bool add2102 = g_state2102Enabled && CheckState2102();
    for (int i = 0; add2102 && i < kLaraStateCount; ++i)
        if (states[i * 7] == 2102) add2102 = false;
    if (add2102 && GenericHolds(kGenericStatePush, kGenericStateTable, 7, id2102, 1) != 1) {
        Log(0, "state 2102: generic table lacks the id (TruDoppelganger.asi active?) - not registered");
        add2102 = false;
    }
    const DWORD rec[4][7] = {
        {243, reinterpret_cast<DWORD>(&State243), 0, 0, 0, 0, 0},
        {245, reinterpret_cast<DWORD>(&State245), 0, 0, reinterpret_cast<DWORD>(&State245Slot3), 0, 0},
        {1018, reinterpret_cast<DWORD>(&State1018Slot0), reinterpret_cast<DWORD>(&State1018Slot1),
         reinterpret_cast<DWORD>(&State1018Slot2), 0, 0, 0},
        {2102, reinterpret_cast<DWORD>(&State2102), 0, 0, 0, 0, 0}};
    memcpy(g_laraStates, states, kLaraStateCount * 7 * sizeof(DWORD));
    int n = kLaraStateCount;
    const int count = add2102 ? 4 : 3;
    for (int k = 0; k < count; ++k, ++n) memcpy(g_laraStates + n * 7, rec[k], 7 * sizeof(DWORD));
    memcpy(g_laraStates + n * 7, stateEnd, 7 * sizeof(DWORD));
    if (PatchPush(kLaraStatePush + 1, reinterpret_cast<DWORD>(g_laraStates)))
        Log(1, "Lara states: 243 (move to gameTracker+0x1270), 245 (move tuning +0x6c along the player), 1018 (meter "
               "cost / world request)%s added (copy 0x%08lx, %d records); not translated: 244, 1017, 1019, 1020%s",
            add2102 ? ", 2102 (camera blend to its end, TU 0x822ae918 / 0x822c2130)" : "",
            reinterpret_cast<DWORD>(g_laraStates), n, add2102 ? "" : ", 2102");
    else
        Log(0, "Lara states: VirtualProtect failed (%lu) - not registered", GetLastError());
}

// ================================================================================================================
// 0.9: the TU tick 0x823d7a10 with its gates, and the adrenaline look group (0x823d94f8 / 0x823d9348 / 0x823d9438,
// mode chooser, adrenaline start / stop / tick, condition 1047)

// ---- TU gates (PC partners, each pinned by bytes in Start) ----
typedef char(__cdecl *CinematicFn)();
const DWORD kCinematic = 0x00453f00;      // [0xe7f1c0] && +0xdd && +0x2c != -1 (TU 0x823d7a30..0x823d7a6c inline)
const char *const kCinematicHex = "a1c0f1e700 85c0 7418 80b8dd00000000 740c 83782cff 7406 b801000000 c3 33c0 c3 32c0 c3";
const DWORD kBlockByte = 0x00fae8dd;      // TU 0x829ca6da = retail 0x829ca5f1
const DWORD kBlockGetter = 0x0077bc20;    // mov al,[0FAE8DDh]; ret
const char *const kBlockGetterHex = "a0dde8fa00 c3";
const DWORD kBlockSetter = 0x0077bbf0;    // mov al,[esp+4]; mov [0FAE8DDh],al; ret
const char *const kBlockSetterHex = "8a442404 a2dde8fa00 c3";
const DWORD kBlockSetterCall = 0x005de576;   // GAMELOOP tru+0x1de480 (= retail 0x8229c530, store 0x8229c708)
const char *const kBlockSetterCallHex = "e875d61900";
const DWORD kGtxFlags = 0x00e7f144;       // TU 0x82efb514 (gameTrackerX +0xbc), bit 0
const DWORD kGtxFlagsCheck = 0x00718c1f;  // adrenaline tick tru+0x318bd0 = TU 0x823defa8: test byte [0E7F144h],1
const char *const kGtxFlagsCheckHex = "f60544f1e70001 0f85c4000000 803d43f1e70004";
const DWORD kInputPtr = 0x00a02b68;       // TU 0x8286dd90: [[p]+0x18]->[0] = the input records
const DWORD kInputCheck = 0x00718c39;     // the same chain to +0x6f0 & 0x10 in tru+0x318bd0 (TU: +0x6f0 >> 4 & 1)
const char *const kInputCheckHex = "8b0d682ba000 8b5118 8b0a 8b91f0060000 80e210";
bool g_gatesOk = false;                   // cinematic / block byte / 0xe7f144 verified
bool g_inputOk = false;                   // input chain verified (GameInput / diagnostic)

bool Cinematic() {
    if (!g_gatesOk) return false;
    char c = 0;
    __try {
        c = reinterpret_cast<CinematicFn>(kCinematic)();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        c = 0;
    }
    return c != 0;
}

bool BlockByte() { return g_gatesOk && *reinterpret_cast<const volatile BYTE *>(kBlockByte) != 0; }
bool GtxFlag() { return g_gatesOk && (*reinterpret_cast<const volatile BYTE *>(kGtxFlags) & 1) != 0; }

// TU 0x823d7d68..0x823d7dd4: refused while a cinematic runs, 0x829ca6da is set, no tracker or health <= 0.0
bool TuStartRefused() {
    if (Cinematic() || BlockByte()) return true;
    BYTE *gt = GameTracker();
    if (!gt) return true;
    float health = 0.0f;
    __try {
        health = *reinterpret_cast<const float *>(gt + 0x628);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return true;
    }
    return !(kZero < health);
}

// game input record word (TU 0x823d7b6c..0x823d7b8c reads +0x1a70 / +0x1b30); returns false when not readable
bool InputWord(DWORD offset, DWORD *value) {
    if (!g_inputOk) return false;
    __try {
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(kInputPtr);
        if (!p) return false;
        const BYTE *list = *reinterpret_cast<const BYTE *const *>(p + 0x18);
        if (!list) return false;
        const BYTE *rec = *reinterpret_cast<const BYTE *const *>(list);
        if (!rec) return false;
        *value = *reinterpret_cast<const DWORD *>(rec + offset);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// ---- adrenaline look group ----
const DWORD kTargetCheck = 0x006f2800;    // TU 0x823df8f8 (retail leaf 0x823dd7a8), thiscall(player) -> al
const char *const kTargetCheckHex =
    "53 8b1d58dbfa00 8b8300050000 56 8bb034010000 83fe0c 57 8bf9 0f8491000000 83fe07 0f8488000000 83fe03 747d "
    "83fe04 7478 e898f6ffff 84c0 756f 8b87fc010000 8bc8 c1e91e f6c101 755f 8bd0 c1ea15 f6c201 7555 c1e818 a801 754e "
    "83feff 744f d9ee d89b88050000 dfe0 f6c405 7b3a 803de6b48a0000 7437 f60544f1e70001 752e 803d43f1e70004 7425 "
    "a1682ba000 8b4818 8b11 8b8230060000 2404 33c9 3c04 0f94c1 8bc1 85c0 7406 5f 5e b001 5b c3 5f 5e 32c0 5b c3";
const DWORD kAimHelper = 0x006f1ed0;      // +0x1fc bit 9 or bit 10 (TU inline 0x823df924..0x823df948)
const char *const kAimHelperHex = "8b81fc010000 8bc8 c1e909 f6c101 750a c1e80a a801 7503 33c0 c3 b801000000 c3";
const DWORD kHudClear = 0x0077db70;       // clear bit n of the HUD group mask 0xfae924 (PC adrenaline stop)
const char *const kHudClearHex = "8b4c2404 8d41ff 83f81e 7710 ba01000000 d3e2 f7d2 211524e9fa00 c3";
typedef void(__cdecl *HudClearFn)(int bit);
bool g_lookAdrOk = false;                 // check function / HUD clear verified (LookTick, Set40, Clear40)
volatile LONG g_set40 = 0, g_clear40 = 0;

// TU 0x823df8f8 (gameTracker in r8, player in r3). The TU inserted 0x823df918..0x823df970: in doppelganger mode only
// +0x1fc bits 9 / 10, 30, 24 answer 1 before the shared tail (no mode 3 / 4, no bit 21). The rest is the PC function's
// code (tru+0x2f2800, verified byte for byte) written out: mode 0xc / 7 -> 0; tail tru+0x2f285d = TU 0x823df9d8.
bool TargetCheck(const BYTE *gt, const BYTE *player) {
    const int mode = *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134);
    if (mode == 0xc || mode == 7) return false;
    const DWORD w = *reinterpret_cast<const DWORD *>(player + 0x1fc);
    if (Doppelganger()) {
        if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
        if ((w >> 30) & 1) return true;
        if ((w >> 24) & 1) return true;
    } else {
        if (mode == 3 || mode == 4) return true;
        if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
        if (((w >> 30) & 1) || ((w >> 21) & 1) || ((w >> 24) & 1)) return true;
    }
    if (mode == -1) return false;
    if (kZero < *reinterpret_cast<const float *>(gt + 0x588)) return true;
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) == 0) return false;         // TU 0x8275422a
    if (*reinterpret_cast<const volatile BYTE *>(kGtxFlags) & 1) return false;          // TU 0x82efb514
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f143) == 4) return false;        // TU 0x82efb513
    DWORD word = 0;
    if (!InputWord(0x630, &word)) return false;
    return (word & 4) == 4;
}

// TU 0x823d9348 (meter flag 0x40 on)
void Set40(const BYTE *tuning) {
    if ((g_meter.flags & 0x40) || !(g_meter.flags & 1)) return;
    BYTE *gt = GameTracker();
    if (gt && tuning) {
        g_meter.request[3][1] = Tune(tuning, 0x38);              // +0x5c = tuning +0x38 (world 0.1)
        g_meter.request[3][0] = kNoRequest;                      // +0x58 = -1.0
        Selector();
    }
    bool hud = false;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(gt + 0x504);
        if ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) {
            if (g_hudOk && *kHudManager && HudPlayerOk("flag 0x40 on")) {   // 0x829ca724 |= 0x9000; vtbl[0xc] - as
                                                                            // tru+0x3189d7 (0.16: needs the player state)
                g_hudGroup(0xf);
                g_hudGroup(0xc);
                g_hudUpdate();
                hud = true;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    g_meter.flags |= 0x40;
    // not ported: 0x82415b50(1) (instance messages; PC partner 0x6f64c0 from the map, unverified)
    bool fired = FireEvent(0x39);
    LONG n = InterlockedIncrement(&g_set40);
    Log(n == 1 ? 1 : 2, "meter flag 0x40 ON (TU 0x823d9348%s): world request 3 = %.3f, HUD 0x9000 %s, event 0x39 %s", n == 1
        ? ", first time" : "", tuning ? Tune(tuning, 0x38) : 0.0f, hud ? "set" : "not set (player +0x1fc bit 10 clear)",
        fired ? "fired" : "not fired");
}

// TU 0x823d9438 (meter flag 0x40 off)
void Clear40() {
    if (!(g_meter.flags & 0x40)) return;
    const BYTE *tuning = g_tuning;
    if (GameTracker() && tuning) {
        g_meter.request[3][0] = g_meter.request[3][1] = kNoRequest;
        Selector();
    }
    if (g_hudOk && g_lookAdrOk && *kHudManager && HudPlayerOk("flag 0x40 off")) {   // 0x829ca724 &= 0xffff6fff;
                                                                                    // vtbl[0xc] (0.16: player state)
        reinterpret_cast<HudClearFn>(kHudClear)(0xf);
        reinterpret_cast<HudClearFn>(kHudClear)(0xc);
        g_hudUpdate();
    }
    g_meter.flags &= ~0x40u;
    bool fired = FireEvent(0x3a);
    LONG n = InterlockedIncrement(&g_clear40);
    Log(n == 1 ? 1 : 2, "meter flag 0x40 OFF (TU 0x823d9438): request 3 cleared, HUD 0x9000 cleared, event 0x3a %s",
        fired ? "fired" : "not fired");
}

// TU 0x823d94f8, once per tick
void LookTick(const BYTE *tuning) {
    if (!g_lookAdrOk || !g_adrenalineMode) return;
    bool on = false;
    __try {
        const BYTE *gt = GameTracker();
        if (gt && tuning && Tune(tuning, kTuneRestart) < g_meter.value && (g_meter.flags & 1)) {
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(gt + 0x504);
            if (player && TargetCheck(gt, player) &&
                *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134) != 3 &&
                !(g_meter.flags & 2))
                on = true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        on = false;
    }
    if (!on) {
        if (g_meter.flags & 0x40) Clear40();
    } else if (!(g_meter.flags & 0x40)) {
        Set40(tuning);
    }
}

// ---- the TU's doppelganger branches in the adrenaline code (naked stubs; no logging inside) ----
// The TU: gameTracker+0x1244 ? (meter +4 >> 6) & 1 : (player +0x1fc >> 27) & 1 (and for bit 21: meter flag 2).
// The stubs only read the cached export pointer (no lookup, no log) - Doppelganger() resolves it on the first tick.
volatile LONG g_adrHits[7];               // DG-mode answers 1: 0 chooser (mode 0x34), 1 start, 2 stop, 3 tick bit 21,
                                          // 4 tick toggle, 5 tick release, 6 condition 1047 (diagnostic counters)
LONG g_adrReported[7];
const char *const kAdrNames[7] = {
    "camera mode chooser tru+0x1e80a9 (TU 0x822acef8): mode 0x34 by meter flag 0x40 (doppelganger mode)",
    "adrenaline start tru+0x3189c6 (TU 0x823ded18): 'already active' = meter flag 0x40",
    "adrenaline stop tru+0x318ad6 (TU 0x823dee58): 'active' = meter flag 0x40",
    "adrenaline tick tru+0x318bf3 (TU 0x823defa8): +0x1fc bit 21 -> meter flag 2",
    "adrenaline tick tru+0x318c5d (TU 0x823defa8): toggle by meter flag 0x40",
    "adrenaline tick tru+0x318cda (TU 0x823defa8): release by meter flag 0x40",
    "condition 1047 (tru+0x365600 = TU 0x8246e538): meter flag 0x40"};

int __cdecl AdrBit(DWORD word, int counter) {
    if (g_adrenalineMode && g_doppelganger && g_doppelganger()) {
        int r = (g_meter.flags >> 6) & 1;
        if (r) InterlockedIncrement(&g_adrHits[counter]);
        return r;
    }
    return (word >> 27) & 1;
}

int __cdecl AdrBit21(DWORD word) {
    if (g_adrenalineMode && g_doppelganger && g_doppelganger()) {
        int r = (g_meter.flags >> 1) & 1;
        if (r) InterlockedIncrement(&g_adrHits[3]);
        return r;
    }
    return (word >> 21) & 1;
}

DWORD g_modeYes = 0x005e80b9, g_modeNo = 0x005e80c2;          // mov [esi+58h],34h | shr eax,0Ah
DWORD g_startActive = 0x00718ac0, g_startGo = 0x007189d7;
DWORD g_stopIdle = 0x00718bc1, g_stopGo = 0x00718ae7;
DWORD g_tickBit21Yes = 0x00718c71, g_tickBit21No = 0x00718bfd;
DWORD g_adrStart = 0x007189c0, g_adrStop = 0x00718ad0;
DWORD g_tickRelIdle = 0x00718cf0, g_tickRelGo = 0x00718ce8;

// tru+0x1e80a9 (6 bytes `mov eax,[ecx+1FCh]`; ecx = player): bit -> 0x5e80b9 (mode 0x34) else 0x5e80c2
__declspec(naked) void ModeStub() {
    __asm {
        push ecx
        push edx
        push 0
        push dword ptr [ecx + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        mov eax, [ecx + 1fch]
        mov ecx, eax                  // as the original: ecx = word >> 27
        jz no34
        shr ecx, 1bh
        jmp dword ptr [g_modeYes]
    no34:
        shr ecx, 1bh
        jmp dword ptr [g_modeNo]
    }
}

// tru+0x3189c6 (adrenaline start, esi = player): active -> return (0x718ac0), else go on (0x7189d7)
__declspec(naked) void StartStub() {
    __asm {
        push ecx
        push edx
        push 1
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        jnz active
        jmp dword ptr [g_startGo]
    active:
        jmp dword ptr [g_startActive]
    }
}

// tru+0x318ad6 (adrenaline stop, esi = player): not active -> return (0x718bc1), else go on (0x718ae7)
__declspec(naked) void StopStub() {
    __asm {
        push ecx
        push edx
        push 2
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        jz idle
        jmp dword ptr [g_stopGo]
    idle:
        jmp dword ptr [g_stopIdle]
    }
}

// tru+0x318bf3 (adrenaline tick, eax = player +0x1fc, kept): bit 21 (meter flag 2) -> 0x718c71, else 0x718bfd
__declspec(naked) void TickBit21Stub() {
    __asm {
        push eax
        push ecx
        push eax
        call AdrBit21
        add esp, 4
        mov edx, eax
        pop ecx
        pop eax
        test dl, 1
        jnz yes
        jmp dword ptr [g_tickBit21No]
    yes:
        jmp dword ptr [g_tickBit21Yes]
    }
}

// tru+0x318c5d (adrenaline tick, eax = player +0x1fc; then mov ecx,esi; pop esi; je start; jmp stop)
__declspec(naked) void TickToggleStub() {
    __asm {
        push ecx
        push edx
        push 4
        push eax
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        mov ecx, esi
        pop esi
        jz start
        jmp dword ptr [g_adrStop]
    start:
        jmp dword ptr [g_adrStart]
    }
}

// tru+0x318cda (6 bytes `mov ecx,[esi+1FCh]`): bit clear -> 0x718cf0 (return), else 0x718ce8 (stop)
__declspec(naked) void TickReleaseStub() {
    __asm {
        push eax
        push edx
        push 5
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        mov ecx, eax
        pop edx
        pop eax
        test cl, 1
        jz idle
        jmp dword ptr [g_tickRelGo]
    idle:
        jmp dword ptr [g_tickRelIdle]
    }
}

// condition 1047 predicate (PC tru+0x365600 = retail test; TU 0x8246e538 adds the doppelganger branch)
char __cdecl Pred1047(const BYTE *) {
    char r = 0;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
        r = static_cast<char>(AdrBit(*reinterpret_cast<const DWORD *>(player + 0x1fc), 6));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    return r;
}

bool WriteJumpN(DWORD at, const void *to, int length) {
    BYTE code[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

struct AdrSite { const char *name; DWORD check; const char *hex; DWORD at; const void *stub; int len; };
const AdrSite kAdrSites[] = {
    {"camera mode chooser", 0x005e80a9,
     "8b81fc010000 8bc8 c1e91b f6c101 7409 c7465834000000 eb17 c1e80a a801 7509 c7465830000000", 0x005e80a9, &ModeStub, 6},
    {"adrenaline start", 0x007189c0, "83ec0c 56 8bf1 8b86fc010000 c1e81b a801 0f85e9000000 6a0f e8f24f0600", 0x007189c6,
     &StartStub, 6},
    {"adrenaline stop", 0x00718ad0, "83ec0c 56 8bf1 8b86fc010000 c1e81b a801 0f84da000000 6a0f e882500600", 0x00718ad6,
     &StopStub, 6},
    {"adrenaline tick bit 21", 0x00718be3, "8b86fc010000 8bc8 c1e90a f6c101 747e 8bd0 c1ea15 f6c201 7574 8b0d58dbfa00",
     0x00718bf3, &TickBit21Stub, 5},
    {"adrenaline tick toggle", 0x00718c5d, "c1e81b a801 8bce 5e 7405 e964feffff e94ffdffff", 0x00718c5d,
     &TickToggleStub, 5},
    {"adrenaline tick release", 0x00718cda, "8b8efc010000 c1e91b f6c101 7408 8bce 5e e9e0fdffff 5e c3", 0x00718cda,
     &TickReleaseStub, 6},
    {"condition 1047 predicate", 0x00765600, "a158dbfa00 8b8804050000 8b81fc010000 c1e81b 2401 c3", 0x00765600,
     &Pred1047, 5}};
const char *const kCond1047PushHex = "8b44240c 8b4c2408 8b542404 6800567600 50 51 52 e837d70100";   // at 0x765620

// all or nothing: a partial set would let start / stop / tick disagree about "active"
void PatchAdrenalineMode() {
    if (!g_adrenalineMode) { Log(1, "adrenaline look: off ([Look] AdrenalineMode=0)"); return; }
    g_lookAdrOk = HexBytesAt(kTargetCheck, kTargetCheckHex) && HexBytesAt(kAimHelper, kAimHelperHex) &&
                  HexBytesAt(kHudClear, kHudClearHex) && g_gatesOk && g_inputOk;
    if (!g_lookAdrOk) {
        Log(0, "adrenaline look: check function 0x%08lx / helper 0x%08lx / HUD clear 0x%08lx / gates / input chain do not "
               "match - TU 0x823d94f8 group and the doppelganger branches not translated", kTargetCheck, kAimHelper,
            kHudClear);
        return;
    }
    bool sitesOk = HexBytesAt(0x00765620, kCond1047PushHex);
    for (const auto &s : kAdrSites)
        if (!HexBytesAt(s.check, s.hex)) {
            Log(0, "adrenaline look: %s at 0x%08lx does not match", s.name, s.at);
            sitesOk = false;
        }
    if (!sitesOk) {
        g_lookAdrOk = false;
        Log(0, "adrenaline look: not translated (all sites or none)");
        return;
    }
    int written = 0;
    for (const auto &s : kAdrSites) {
        if (WriteJumpN(s.at, s.stub, s.len)) ++written;
        else Log(0, "adrenaline look: %s not written (VirtualProtect %lu)", s.name, GetLastError());
    }
    Log(1, "adrenaline look: TU 0x823d94f8 / 0x823d9348 / 0x823d9438 (meter flag 0x40) per tick; doppelganger branches "
           "of the camera mode chooser (mode 0x34), adrenaline start / stop / tick and condition 1047 - %d of %d sites "
           "written", written, static_cast<int>(sizeof(kAdrSites) / sizeof(kAdrSites[0])));
}

void ReportAdrenalineHits() {
    for (int i = 0; i < 7; ++i) {
        LONG n = g_adrHits[i], last = g_adrReported[i];
        if (n == last) continue;
        g_adrReported[i] = n;
        bool pow2 = false;
        for (LONG p = 1; p > 0 && p <= n; p <<= 1)
            if (p > last) { pow2 = true; break; }
        if (last == 0 || (g_logLevel >= 2 && pow2)) Log(1, "%s (%ld times)", kAdrNames[i], n);
    }
}

// 0.14, defined below (section "0.14")
void LoopTick(BYTE *gt);
void LoopFree(const char *why);
void MoveEvents();
// 0.15, defined below (section "0.15")
void ReportClothTimeStep();
// 0.24, defined below (section "0.24")
void ReportCameraTimeStep();
// 0.27, defined below (section "0.27")
void ReportTimeStep027();
// 0.25, defined below (sections "0.25 [Camera] Trace" / "0.25 DoppelgangerSettings")
void DgSynthTick();
void ReportCamSettings();
void CamTraceTick();

// ---- new tracker -> new meter (TU player init 0x82412ca0 -> 0x82409418 -> meter init 0x823d7700) ----
typedef int(__cdecl *GenerationFn)();
GenerationFn g_generation = nullptr;
int g_generationLooked = 0, g_lastGeneration = -1;

void NewTrackerCheck() {
    if (!g_generationLooked) {
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_generation = reinterpret_cast<GenerationFn>(GetProcAddress(m, "TruDlc2PlayerTrackerGeneration"));
        g_generationLooked = 1;
        if (!g_generation)
            Log(0, "TruDlc2PlayerTrackerGeneration not found (TruDlc2Player older than 0.2?) - the meter is not "
                   "re-initialised with a new game tracker");
    }
    if (!g_generation) return;
    int gen = g_generation();
    if (gen == g_lastGeneration) return;
    if (g_lastGeneration >= 0) {
        bool requests = false;
        for (int i = 0; i < 7; ++i) requests = requests || kZero < g_meter.request[i][0] || kZero < g_meter.request[i][1];
        DWORD was = g_meter.flags;
        if ((was & 0x40) && g_hudOk && g_lookAdrOk && *kHudManager && HudPlayerOk("new tracker, flag 0x40")) {
            reinterpret_cast<HudClearFn>(kHudClear)(0xf);
            reinterpret_cast<HudClearFn>(kHudClear)(0xc);
            g_hudUpdate();
        }
        // 0.14: the player teardown 0x82412ea8..0x82412ebc frees the old meter's loop handle (0x823d7680: stop,
        // release the node, free) before the new player init builds a new meter (0x823d7700 then makes a new handle)
        if (g_loopSound) LoopFree("new game tracker");
        if (kZero < g_meter.request[6][0] || kZero < g_meter.request[6][1])     // 0.21: one line per slot-6 change
            Log(1, "0.21 slot 6: cleared with the new game tracker (was player %.3f / world %.3f; the plugin's meter is "
                   "re-initialised, all 7 slots empty)", g_meter.request[6][0], g_meter.request[6][1]);
        MeterInit();
        if (requests) Selector();       // the plugin's meter outlives the TU object: release its time-scale requests
        Log(1, "new game tracker (generation %d): meter re-initialised (was flags 0x%03lx%s)", gen, was,
            requests ? ", time-scale requests released" : "");
    }
    g_lastGeneration = gen;
}

// ================================================================================================================
// 0.16 (project doc Befund-15h-Absturz-Finisher-0611.md section 1): the tick only while Lara exists and updates.
//
// TU: the player update 0x824126d8 calls the tick 0x823d7a10 (0x824128a4..0x824128b8) - without Lara (unit unload,
// level change, front end) there is no player update and so no tick. The plugin ticks from the pad poll; up to 0.15 its
// only gate was the doppelganger flag, which stays 1 until the next tracker constructor. The 15h run crashed on the
// first tick after a level.load unload: player state 0, meter 99.6 %, Refill -> ShowMeter -> HUD script -> uigamedata
// f32 -> AV tru+0x37bdd3. MeterTick now returns at once - no refill, no drain, no HUD call, no flag / latch / request
// change, no new-tracker re-init (that runs at the first tick after the skip, before any refill) - when:
//   1 player state [0xfadb58] == 0         the HUD script's f32 dereferences it (tru+0x37bdb5 / 0x37bdd3)
//   2 player instance [0xe7f094] == 0      GameTracker 0xe7f088 + 0xc (reader tru+0x341764, TruMenu's InLevel())
//   3 main state [0xe7ed60] != 1           dispatcher tru+0x1e0090 (&mainState from the game loop tru+0x1e01ab): state
//                                          1 -> tru+0x1e00e1 -> tru+0x1e0050 = the level loop; 2 = a level start is set
//                                          up (tru+0x1dfb83, level load tru+0x1de9c0), 9 outfit selection, 10 front end
//   4 level change byte GameTracker+0xb9   [0xe7f141] set by the request tru+0x1df88a, tested by GAMELOOP_Request-
//                                          LevelChangeByName tru+0x1df8d3, cleared by the level load tru+0x1de86c
// 1 / 2 are plain reads of two globals and always apply; 3 / 4 (TruMenu's LevelChangePending / SafePauseReason tests)
// apply only when their code is verified (kTickGateChecks); 1 and 2 are pinned there too.
const volatile DWORD *const kMainStateVar = reinterpret_cast<const volatile DWORD *>(0x00e7ed60);
const volatile BYTE *const kLevelChangeByte = reinterpret_cast<const volatile BYTE *>(0x00e7f141);
const volatile DWORD *const kPlayerInstanceVar = reinterpret_cast<const volatile DWORD *>(0x00e7f094);
const CodeCheck kTickGateChecks[] = {
    // player state: the faulting reader (uigamedata f32 body tru+0x37bd80), its writers (set / clear with ebx = 0)
    {0x0077bdb5, "8b0d58dbfa00 8944240f 89442413 89442417 8944241b 8944241f 89442423 8a810d050000"},
    {0x0072247b, "893d58dbfa00"}, {0x00721ffa, "33db"}, {0x00722304, "891d58dbfa00"},
    // player instance [0xe7f094] (GameTracker + 0xc)
    {0x00741764, "8b0d94f0e700"},
    // main state: the game loop passes &mainState, the dispatcher, table entry state 1 -> the level loop handler
    {0x005e01ab, "6888f0e700 6860ede700 e8d6feffff"},
    {0x005e0096, "8b3e 8d47ff 83f809 0f87b0000000 ff24855c015e00"},
    {0x005e015c, "e1005e00"}, {0x005e00e1, "8b4c2410 51 56 e864ffffff"},
    // main state 1 after the level load, 2 on a mission start from a level / the front end
    {0x005de9f0, "c70560ede70001000000"}, {0x005dfb5c, "833d60ede70001"}, {0x005dfb83, "c70560ede70002000000"},
    // GameTracker+0xb9: request sets it, RequestLevelChangeByName tests it (edi = GameTracker), level load clears it
    {0x005df883, "c60543f1e70000 a241f1e700"}, {0x005df8d3, "80bfb900000000 754d"},
    {0x005de864, "381d41f1e700 7406 881d41f1e700"},
};
bool g_levelGateOk = false;             // kTickGateChecks verified (else only tests 1 / 2)
int g_skipReason = 0;                   // 0 ticking, else the reason of the running skip burst (1..4)
LONG g_skipTicks = 0;                   // ticks skipped in the running burst
DWORD g_skipClock = 0;                  // game clock [0xe7f15c] at the burst's first skip
LONG g_skipBursts = 0;                  // bursts so far (logged at LogLevel 1 up to kSkipBurstLog, then at 2)
const LONG kSkipBurstLog = 64;

// 0 = the tick may run, else 1 no player state, 2 no player instance, 3 main state not 1, 4 level change pending
int TickSkipReason() {
    if (!PlayerStateNow()) return 1;
    if (!*kPlayerInstanceVar) return 2;
    if (g_levelGateOk) {
        if (*kMainStateVar != 1) return 3;
        if (*kLevelChangeByte) return 4;
    }
    return 0;
}

const char *SkipReasonText(int reason) {
    static const char *const texts[] = {"none", "no player state [0xfadb58]", "no player instance [0xe7f094]",
                                        "main state [0xe7ed60] not 1", "level change pending (GameTracker+0xb9)"};
    return texts[reason >= 0 && reason <= 4 ? reason : 0];
}

// true = skip this tick (logs the start of a burst, a reason change at LogLevel 2 and the resume)
bool TickGate() {
    int reason = TickSkipReason();
    if (reason) {
        if (!g_skipReason) {
            g_skipClock = *kGameClock;
            g_skipTicks = 0;
            LONG burst = ++g_skipBursts;
            if (burst <= kSkipBurstLog || g_logLevel >= 2)
                Log(burst <= kSkipBurstLog ? 1 : 2,
                    "meter tick skipped (no player / level change): %s - player state 0x%08lx, player 0x%08lx, main "
                    "state %lu, GameTracker+0xb9 %u; meter %.1f, flags 0x%03lx kept (TU: the tick runs only in Lara's "
                    "update 0x824128a4; burst %ld%s)", SkipReasonText(reason),
                    *reinterpret_cast<const volatile DWORD *>(kPlayerStatePtr), *kPlayerInstanceVar, *kMainStateVar,
                    static_cast<unsigned>(*kLevelChangeByte), g_meter.value, g_meter.flags, burst,
                    burst == kSkipBurstLog ? ", later bursts at LogLevel 2" : "");
        } else if (reason != g_skipReason) {
            Log(2, "meter tick still skipped: %s (was: %s)", SkipReasonText(reason), SkipReasonText(g_skipReason));
        }
        g_skipReason = reason;
        ++g_skipTicks;
        return true;
    }
    if (g_skipReason) {
        DWORD ms = *kGameClock - g_skipClock;
        if (g_skipBursts <= kSkipBurstLog || g_logLevel >= 2)
            Log(g_skipBursts <= kSkipBurstLog ? 1 : 2,
                "meter tick resumed: player state 0x%08lx, player 0x%08lx, main state 1 - %ld ticks skipped over %lu ms "
                "game clock (last reason: %s)", *reinterpret_cast<const volatile DWORD *>(kPlayerStatePtr),
                *kPlayerInstanceVar, g_skipTicks, ms, SkipReasonText(g_skipReason));
        g_skipReason = 0;
        g_skipTicks = 0;
    }
    return false;
}

void CheckTickGate() {
    g_levelGateOk = true;
    for (const auto &c : kTickGateChecks)
        if (!HexBytesAt(c.address, c.bytes)) {
            Log(0, "0.16 tick gate: code at 0x%08lx does not match - main state / level change tests off (the tick "
                   "still needs the player state [0xfadb58] and the player instance [0xe7f094])", c.address);
            g_levelGateOk = false;
            break;
        }
    if (g_levelGateOk)
        Log(1, "0.16 tick gate: %u code checks passed - the meter ticks only with player state [0xfadb58], player "
               "instance [0xe7f094], main state [0xe7ed60] = 1 and no level change pending (GameTracker+0xb9) - as the "
               "TU's tick inside Lara's update; every HUD call needs the player state",
            static_cast<unsigned>(sizeof(kTickGateChecks) / sizeof(kTickGateChecks[0])));
}

// ================================================================================================================
// 0.17 (project doc Befund-TruShadowPower-017-0611.md): LB / RB only as the game gets them.
//
// Live 2026-11-06 22:18 (DLC 2): each LB / RB page switch of TruMenu's quick bar logged "shadow power ON". The pad
// pointer 0x00a02b8c is written once by the game (tru+0x82513, the GetProcAddress result) and called at three sites
// (tru+0x82619 presence test every 500 ms, tru+0x84b82 the per-frame poll, tru+0x8620a); the per-frame poll passes a
// state buffer on its own stack (lea eax,[esp+4] at tru+0x84b7c) and reads wButtons from it after the call
// (tru+0x84bc3) - what the game got is gone after the poll returns. TruMenu, TruLink and this plugin each wrap the
// pointer once; TruMenu's import filter (meant to hand the game its hook first) never did so in the TruMenu.log of
// that day, so TruMenu was placed "late" on top of whatever was there - in that session this plugin. Chain: game ->
// TruMenu -> TruShadowPower -> TruLink -> XInputGetState; TruMenu cleared LB / RB (quick bar open) only after this
// plugin had read them. 0.17: go outside TruMenu once (HookThread) and withhold what the game does not get
// (GameButtons, WithheldLog); 0.19: no re-wrap, TruMenu's export TruMenuPadBlock names what it keeps from the game. The game also compares dwPacketNumber with its last one (tru+0x84b95): TruMenu keeps it
// when it masks or neutralises, which is what GameButtons relies on for its two reads.
const CodeCheck kPadPollChecks[] = {
    // the only writer of the pointer: GetProcAddress (import slot 0x83e08c, "XInputGetState" 0x844b98) -> 0xa02b8c
    {0x00482505, "8b358ce08300 68984b8400 50 ffd6 a38c2ba000"},
    // per-frame poll: state on the stack, pad index [ebp+0x894], call through the pointer, result test
    {0x00484b70, "83ec10 55 8be9 8b8d94080000 8d442404 50 51 ff158c2ba000 85c0 7409"},
    // packet number against the last one ([ebp+0x890]), unless forced (arg byte); wButtons read from the stack buffer
    {0x00484b95, "8b442404 398590080000 7507 807c242000 74e4"},
    {0x00484bc3, "0fb74c2414"},
    // the two other calls through the pointer: presence test (pad 0, every 500 ms) and tru+0x8620a
    {0x00482613, "8d542408 52 56 ff158c2ba000 85c0 0f94c0"},
    {0x00486204, "8d4c2424 51 57 ff158c2ba000 85c0 0f8538010000"},
};

void CheckPadPoll() {
    if (!g_menuInput) {
        Log(1, "0.17 menu input: off ([ShadowPower] MenuInput=0) - LB / RB as read in the pad chain (0.16)");
        return;
    }
    for (const auto &c : kPadPollChecks)
        if (!HexBytesAt(c.address, c.bytes)) {
            Log(0, "0.17 menu input: pad poll code at 0x%08lx does not match - off (LB / RB as read in the pad chain, "
                   "0.16)", c.address);
            return;
        }
    g_menuInputOk = true;
    Log(1, "0.17 menu input: %u code checks passed - LB / RB count only as the game gets them (0.19: TruMenu's "
           "TruMenuPadBlock + a second pad read, no re-wrap; a button TruMenu withholds is ignored until released)",
        static_cast<unsigned>(sizeof(kPadPollChecks) / sizeof(kPadPollChecks[0])));
}

// ---- the TU tick 0x823d7a10 ----
int g_lastDg = -1;
bool g_lastPadHeld = false;
int g_inputDiag = 0;

void MeterTick(bool padHeld) {
    if (TickGate()) return;                      // 0.16: no player / not in a level / level change - TU: no tick
                                                 // (also for the legacy 0.8 tick below)
    ScreenEffectPoll();                          // 0.10: only while an event 0x32 is pending
    ReportClothTimeStep();                       // 0.15: log only ([Cloth] ClothTuTimeStep=1)
    ReportCameraTimeStep();                      // 0.24: log only ([Camera] CameraTuTimeStep=1)
    ReportTimeStep027();                         // 0.27: log only ([Camera] ShakeTuTimeStep / [Player] TuTimeStep)
    DgSynthTick();                              // 0.25: [Camera] DoppelgangerSettings=2 stand-in (once)
    ReportCamSettings();                         // 0.25: the gameplay camera's settings choice (log on change)
    CamTraceTick();                              // 0.25: [Camera] Trace=1 -> TruCam.log
    if (g_legacyPadStart) { LegacyMeterTick(padHeld); return; }
    NewTrackerCheck();
    // TU 0x824128a4..0x824128b8: the player update runs the tick only when gameTracker+0x1244 is set
    int dg = Doppelganger();
    if (dg != g_lastDg) {
        if (g_lastDg < 0)
            Log(1, "doppelganger flag %d at the first tick: shadow-power tick %s (TU 0x824128a8)", dg,
                dg ? "runs" : "does not run");
        else
            Log(1, "doppelganger flag %d -> %d: shadow-power tick %s (TU 0x824128a8)", g_lastDg, dg,
                dg ? "runs" : "does not run");
        g_lastDg = dg;
    }
    // diagnostic for GameInput: the game's records while the pad's LB / RB change
    if (padHeld != g_lastPadHeld) {
        g_lastPadHeld = padHeld;
        DWORD lb = 0, rb = 0, adr = 0;
        if (g_inputDiag < 12 && InputWord(0x1a70, &lb) && InputWord(0x1b30, &rb) && InputWord(0x6f0, &adr)) {
            ++g_inputDiag;
            Log(1, "input diagnostic: pad LB/RB %s - game records +0x1a70 0x%08lx, +0x1b30 0x%08lx (TU tests & 4), "
                   "+0x6f0 0x%08lx", padHeld ? "held" : "released", lb, rb, adr);
        }
    }
    ReportAdrenalineHits();
    if (!dg) return;
    const BYTE *tuning = FindTuning();
    g_tuning = tuning;
    InfiniteHold(tuning);                        // 0.23: [Meter] Infinite=1 - meter at max before the TU block
    float frames = *kFrameTime;
    if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
    // 0x823d7a30..0x823d7a9c: a running cinematic or 0x829ca6da -> print "ADRENALINE: Process(): stopping
    // adrenaline!" (0x82455a38 = empty print on PC) and Stop (no-op when not active)
    bool cine = Cinematic(), block = BlockByte();
    if ((cine || block) && (g_meter.flags & 1)) StopPower(cine ? "cinematic" : "0x829ca6da (PC 0xfae8dd) set");
    // 0x823d7aa0..0x823d7adc: flag 0x80 = bool parameter 0x412 of Lara's current state (state machine gt+0xf10)
    BYTE *gt = GameTracker();
    if (gt && g_tuStatesOk) {
        __try {
            void *machine = *reinterpret_cast<void *const *>(gt + 0xf10);
            if (machine) {
                char zone = 0;
                ParamBool(machine, 0x412, &zone);
                DWORD before = g_meter.flags;
                if (zone) g_meter.flags |= 0x80;
                else g_meter.flags &= ~0x80u;
                if ((before ^ g_meter.flags) & 0x80)
                    Log(1, "meter flag 0x80 %s (state parameter 0x412 of the current state; blocks the meter)",
                        zone ? "set" : "cleared");
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    // 0.14: 0x823d7ae0..0x823d7b34 looping sound (+0x0 handle; [Sound] LoopSound) and 0x823d77f0 (movement events
    // 0x83 / 0x84; [Look] MoveEvents) - both off by default (= 0.13)
    if (g_loopSound) LoopTick(gt);
    if (g_moveEvents) MoveEvents();                                         // 0x823d77f0
    LookTick(tuning);                                                       // 0x823d94f8
    if (!(g_meter.flags & 0x90)) {
        bool buttons = padHeld;
        if (g_gameInput) {                                                  // 0x823d7b6c..0x823d7b98
            DWORD lb = 0, rb = 0;
            buttons = (InputWord(0x1a70, &lb) && (lb & 4) == 4) || (InputWord(0x1b30, &rb) && (rb & 4) == 4);
        }
        if (buttons && !GtxFlag()) {
            if (!g_meter.latch && CanStart(tuning)) {
                StartPower(tuning);
                g_meter.latch = 1;
            } else {
                if (!g_meter.latch) {                                       // CanStart false: event 0x80 (refused)
                    FireEvent(0x80);
                    Log(2, "start refused (meter %.1f, flags 0x%03lx): event 0x80", g_meter.value, g_meter.flags);
                }
                g_meter.latch = 1;
            }
        } else if (g_meter.latch == 1) {
            if (g_meter.flags & 1) StopPower(buttons ? "game flag 0xe7f144" : "released");
            g_meter.latch = 0;
        }
        if (!(g_meter.flags & 1)) {
            Refill(tuning, frames);
        } else {
            if (kZero < g_meter.value && !(g_meter.flags & 0x90) && tuning)
                Drain(tuning, frames * kPerSecond * Tune(tuning, kTuneDrain));
            if (kZero < g_meter.value) {
                if (GtxFlag()) StopPower("game flag 0xe7f144");
            } else {
                g_meter.flags |= 0x200;
                StopPower("meter empty");
            }
        }
    }
    // 0x823d7cf8..: the timed request of condition 2401
    if (kZero < g_meter.requestTimer) {
        g_meter.requestTimer = g_meter.requestTimer - frames;
        if (g_meter.requestTimer <= kZero) {
            g_meter.request[4][0] = g_meter.request[4][1] = kNoRequest;
            Selector();
            g_meter.requestTimer = kZero;
            Log(2, "timed request (2401) ended");
        }
    }
}

// ================================================================================================================
// 0.11 (project doc Befund-Look.md section 7): GlobalParams[7], state 2102, the meter interface

// ---- GlobalParams[7] = the TU's shadow-power shader vector ----
// TU 0x82474728 (= retail 0x8246eff0 = PC tru+0x373a70, called per frame for the player instance from tru+0x373bf0)
// sets GlobalParams[0..6] (player position and six bones) through (*0x829be0a4)->vtbl[0x84](index, 1, vec); the TU
// appended (0x824748e4..0x82474988), when gameTracker [0x829892b0] and the tuning 0x82415518 exist:
//   GlobalParams[7] = { 0x823d8548(meter) = value / tuning +0x10, value / meter +0xc, (float)(flags & 1),
//                       0x823d85a8(meter) = fade: t = (clock 0x82efb528 - meter +0x3c) x 0.03 [0x8207d6fc];
//                       active: clamp(t / tuning +0x60) (1 if +0x60 <= 0), else 1 - clamp(t / tuning +0x64) }
// read by 19 TU pixel shaders (look 2327 as a lerp factor, the vein 2392, ...). PC: the same setter
// [0xa1407c]->vtbl[0x84] = tru+0x107110 (thiscall(index, count, vec) -> renderer +0xfb18 + 16 x index). Translation:
// the call tru+0x373bfd (-> tru+0x373a70) goes to a wrapper that runs the PC function and then the TU's block.
// Not translated (named): the second TU block 0x8247498c.. (player instance +0x244 -> ...->vtbl[0x50](1, cinematic ?
// (1,0,0,0) : 0) - PC layout of +0x244 not checked).
typedef void(__cdecl *GlobalsFn)(void *instance);
typedef void(__fastcall *SetGlobalFn)(void *renderer, int, int index, int count, const float *vec);
const DWORD kGlobalsCall = 0x00773bfd;              // call tru+0x373a70 in tru+0x373bf0 (only caller)
const char *const kGlobalsCallHex = "e86efeffff d9450c d9ee 83c404";
const DWORD kGlobalsFn = 0x00773a70;
const char *const kGlobalsFnHex = "55 8bec 83e4f0 83ec18 56 8b7508 85f6 57 0f8464010000";
const DWORD kGlobalsTail = 0x00773be1;              // push 6; ...; call edx = GlobalParams[6] - the TU's block follows
const char *const kGlobalsTailHex = "6a06 0f2944241c ffd2 5f 5e 8be5 5d c3";
const DWORD kRendererPtr = 0x00a1407c;
const DWORD kSetGlobalSlot = 0x00849350;            // renderer vtable 0x8492cc + 0x84
const DWORD kSetGlobal = 0x00507110;
const char *const kSetGlobalHex = "8b442404 8b542408 56 8d3410 83fe10 5e 771c c1e204";
int g_gp7Enabled = 1;                               // [Look] GlobalParams7
bool g_gp7Ok = false;
volatile LONG g_gp7Sets = 0;
float g_gp7Last[4] = {-1.0f, -1.0f, -1.0f, -1.0f};

// 0x823d85a8
float LookFade(const BYTE *tuning) {
    float t = static_cast<float>(static_cast<DWORD>(*kTuClock - g_meter.startTime)) * 0.03f;   // [0x8207d6fc]
    float span = Tune(tuning, (g_meter.flags & 1) ? 0x60 : 0x64);
    if (!(kZero < span)) return kOne;
    float x = t / span;
    float c = (kOne - x >= kZero) ? x : kOne;                  // fsel f10, 1 - x, x, 1
    c = (c >= kZero) ? c : kZero;                              // fsel f1, f10, f10, 0
    return (g_meter.flags & 1) ? c : kOne - c;
}

// ---- 0.12: the second appended TU block 0x8247498c..0x82474a24 ----
// model = (instance +0x244)->+0x10[(s8)((+0x244)->+4)->+0x234] (the instance's current render model; PC: the same
// fields, e.g. tru+0x1b6abd), model->vtbl[0x50](1, cinematic ? (1, 0, 0, 0) [0x8207dc20] : (0, 0, 0, 0) [0x8207db30])
// with the TU's inline cinematic test ([0x82efb590] +0xdd and +0x2c != -1 = PC tru+0x53f00). Slot 0x50 = set
// InstanceParams[index] (PCRenderModelInstance vtable 0x849764 -> tru+0xf4f60: lazily allocated 0x90-byte block,
// [+0x1c + 16 x index] = *vec, movaps); proven the same slot on both platforms: retail 0x8248fe38 (map: verified =
// PC tru+0x393680) calls vtbl[0x50](0, v) / (1, +0x4a0), the PC twin `call [edx+0x50]` with push 0 / push 1 + vec*.
typedef void(__fastcall *SetInstParamFn)(void *model, int, int index, const float *vec);
const DWORD kModelOfInstance = 0x005b6abd;      // mov eax,[ecx+0x244]; mov edx,[eax+4]; movsx ecx,[edx+0x234]; ...
const char *const kModelOfInstanceHex = "8b8144020000 8b5004 0fbe8a34020000 8b5010 8b0c8a";
const DWORD kModelVtable = 0x00849764;          // cdc::PCRenderModelInstance (RTTI)
const DWORD kModelSlot50 = 0x004f4f60;
const char *const kModelSlot50Hex = "55 8bec 83e4f0 83ec0c 56 8bf1 e84ff6ffff 837e1800";
const DWORD kModelSlot50Store = 0x004f4fb2;     // mov edx,[ebp+8]; mov eax,[ebp+0xc]; movaps xmm0,[eax]; shl edx,4; ...
const char *const kModelSlot50StoreHex = "8b5508 8b450c 0f2800 c1e204 03561c 5e 0f2902 8be5 5d c20800";
int g_cineParamEnabled = 1;                     // [Look] CinematicParam
bool g_cineParamOk = false;
volatile LONG g_cineParamSets = 0;
int g_cineLast = -1;
__declspec(align(16)) const float kVecX[4] = {1.0f, 0.0f, 0.0f, 0.0f};   // [0x8207dc20]
__declspec(align(16)) const float kVec0[4] = {0.0f, 0.0f, 0.0f, 0.0f};   // [0x8207db30]

void CinematicParam(BYTE *instance) {
    __try {
        BYTE *o = *reinterpret_cast<BYTE *const *>(instance + 0x244);
        if (!o) return;                                                     // TU 0x82474990 beq
        BYTE *m4 = *reinterpret_cast<BYTE *const *>(o + 4);
        void *const *arr = *reinterpret_cast<void *const *const *>(o + 0x10);
        if (!m4 || !arr) return;
        void *model = arr[*reinterpret_cast<const signed char *>(m4 + 0x234)];
        if (!model) return;                                                 // TU 0x824749b4 beq
        if (*reinterpret_cast<const DWORD *>(model) != kModelVtable) {
            if (InterlockedIncrement(&g_cineParamSets) == 1)
                Log(1, "InstanceParams[1] (TU 0x8247498c): player model 0x%08lx has vtable 0x%08lx, not "
                       "PCRenderModelInstance 0x%08lx - not set", reinterpret_cast<DWORD>(model),
                    *reinterpret_cast<const DWORD *>(model), kModelVtable);
            return;
        }
        const int cine = Cinematic() ? 1 : 0;
        reinterpret_cast<SetInstParamFn>(kModelSlot50)(model, 0, 1, cine ? kVecX : kVec0);
        if (InterlockedIncrement(&g_cineParamSets) == 1 || (cine != g_cineLast && g_logLevel >= 2))
            Log(g_cineParamSets == 1 ? 1 : 2, "InstanceParams[1] of the player model (TU 0x8247498c) = %s (cinematic %d)",
                cine ? "(1, 0, 0, 0)" : "(0, 0, 0, 0)", cine);
        g_cineLast = cine;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "InstanceParams[1] (TU 0x8247498c): access fault - off");
        g_cineParamOk = false;
    }
}

void SetGlobalParams7(const BYTE *tuning);

void __cdecl GlobalsWrap(void *instance) {
    reinterpret_cast<GlobalsFn>(kGlobalsFn)(instance);
    if (!instance || !g_gp7Ok) return;                         // TU: r31 == 0 -> end of function
    if (!GameTracker()) return;                                // TU: [0x829892b0] == 0
    const BYTE *tuning = ObjectTuning();                       // TU 0x82415518 (the game object only, no fallback)
    if (!tuning) return;
    if (g_gp7Enabled) SetGlobalParams7(tuning);
    if (g_cineParamEnabled && g_cineParamOk) CinematicParam(static_cast<BYTE *>(instance));   // 0.12, TU order
}

void SetGlobalParams7(const BYTE *tuning) {
    float v[4];
    float max = Tune(tuning, kTuneMax);
    v[0] = (max != kZero) ? g_meter.value / max : kZero;      // 0x823d8548
    v[1] = g_meter.value / g_meter.startValue;                 // [m+8] / [m+0xc]
    v[2] = static_cast<float>(g_meter.flags & 1);
    v[3] = LookFade(tuning);                                   // 0x823d85a8
    __try {
        void *renderer = *reinterpret_cast<void *const *>(kRendererPtr);
        if (!renderer) return;
        SetGlobalFn set = reinterpret_cast<SetGlobalFn>((*reinterpret_cast<DWORD *const *>(renderer))[0x84 / 4]);
        set(renderer, 0, 7, 1, v);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "GlobalParams[7]: access fault in the renderer call - off");
        g_gp7Ok = false;
        return;
    }
    if (InterlockedIncrement(&g_gp7Sets) == 1)
        Log(1, "GlobalParams[7] (TU 0x824748e4): first set (%.3f, %.3f, %.0f, %.3f) - meter / max, meter / start, "
               "active, look fade", v[0], v[1], v[2], v[3]);
    else if (g_logLevel >= 3 && (v[2] != g_gp7Last[2] || fabsf(v[3] - g_gp7Last[3]) > 0.2f))
        Log(3, "GlobalParams[7] = (%.3f, %.3f, %.0f, %.3f)", v[0], v[1], v[2], v[3]);
    memcpy(g_gp7Last, v, sizeof(v));
}

bool WriteCall5(DWORD at, const void *to) {
    BYTE code[5] = {0xe8, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, 5);
    VirtualProtect(reinterpret_cast<void *>(at), 5, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), 5);
    return true;
}

void PatchGlobalParams7() {
    // 0.12: the same wrapper also runs the second appended TU block ([Look] CinematicParam)
    g_cineParamOk = g_cineParamEnabled && g_gatesOk && HexBytesAt(kModelOfInstance, kModelOfInstanceHex) &&
                    HexBytesAt(kModelSlot50, kModelSlot50Hex) && HexBytesAt(kModelSlot50Store, kModelSlot50StoreHex) &&
                    *reinterpret_cast<const DWORD *>(kModelVtable + 0x50) == kModelSlot50;
    if (g_cineParamEnabled && !g_cineParamOk)
        Log(0, "InstanceParams[1] (TU 0x8247498c): model code at 0x%08lx / 0x%08lx or the cinematic test does not match "
               "- not set", kModelOfInstance, kModelSlot50);
    if (!g_gp7Enabled) Log(1, "GlobalParams[7]: off ([Look] GlobalParams7=0)");
    if (!g_cineParamEnabled) Log(1, "InstanceParams[1] of the player model: off ([Look] CinematicParam=0)");
    if (!g_gp7Enabled && !g_cineParamOk) return;
    g_gp7Ok = HexBytesAt(kGlobalsCall, kGlobalsCallHex) && HexBytesAt(kGlobalsFn, kGlobalsFnHex) &&
              HexBytesAt(kGlobalsTail, kGlobalsTailHex) && HexBytesAt(kSetGlobal, kSetGlobalHex) &&
              *reinterpret_cast<const DWORD *>(kSetGlobalSlot) == kSetGlobal && g_tableOk &&
              HexBytesAt(kTuClockAdd, kTuClockAddHex);
    if (!g_gp7Ok) { Log(0, "GlobalParams[7]: code at 0x%08lx / 0x%08lx does not match - not set", kGlobalsCall, kSetGlobal); return; }
    if (!WriteCall5(kGlobalsCall, reinterpret_cast<const void *>(&GlobalsWrap))) {
        g_gp7Ok = false;
        Log(0, "GlobalParams[7]: VirtualProtect failed (%lu) - not set", GetLastError());
        return;
    }
    Log(1, "GlobalParams[7] %s / InstanceParams[1] %s: TU 0x824748e4 / 0x8247498c translated - after tru+0x373a70 "
           "(GlobalParams 0-6) the wrapper sets index 7 through [0x%08lx]->vtbl[0x84] = tru+0x107110 and the player "
           "model's InstanceParams[1] (cinematic) while object 858's tuning is loaded", g_gp7Enabled ? "on" : "off",
        g_cineParamOk ? "on" : "off", kRendererPtr);
}

// ---- state 2102 (TU 0x824627b0 -> 0x822ae918 -> camera vtbl[0x80] = TU-only 0x822c2130) ----
// The TU moved the end of the Lara camera's slot 0x6c (retail 0x822c4df8 = PC tru+0x202290: after tru+0x201d30, the
// "jump the camera blend to its end" part) into a new slot 0x80 and calls it from state 2102 when that camera is the
// manager's current one. PC: no slot 0x80 (the vtable 0x85600c ends at 0x7c), so the slot's body is written out from
// its PC copy tru+0x202298..0x2022db, with the TU's doppelganger default of 0x822bc198 (settings +0x14c instead of
// +0x144 when gameTracker+0x1244 is set). Manager 0xe804f0 (+0xb80 = Xbox +0xb50), is-current tru+0x1e7fb0.
typedef char(__fastcall *CamIsCurrentFn)(void *mgr, int, void *cam);
typedef BYTE *(__cdecl *CamSettingsFn)(int id);
const DWORD kCamMgr = 0x00e804f0;
const DWORD kCamMgrVtable = 0x00855ae4;
const DWORD kCamMgrDtor = 0x0083cee0;
const char *const kCamMgrDtorHex = "b9f004e800 e9b6e1daff";
const DWORD kCamIsCurrent = 0x005e7fb0;
const char *const kCamIsCurrentHex = "8b4144 8b542404 3bc2 7419 56 8db170060000 3bc6 5e 7508 3991b0070000 7405";
const DWORD kCamSnapBody = 0x00602298;
const char *const kCamSnapBodyHex = "8b86d0010000 83f8ff 740d 50 e8d7bcf4ff 83c404 85c0 7514 e8cb1dfdff 8b8044010000 50 "
                                    "e8bfbcf4ff 83c404 83c010 7412 d980b8000000 d880b4000000 d99ee4010000";
const DWORD kCamSettings = 0x0054df80;
const char *const kCamSettingsHex = "8b442404 8b0485286fc300 85c0 740a 80780400 7504 83c010 c3 33c0 c3";
const DWORD kCamDefaults = 0x005d4080;              // mov eax, [0xe7ee50]; ret (Xbox [0x829ca200])
const char *const kCamDefaultsHex = "a150eee700 c3";
bool g_state2102Ok = false;
volatile LONG g_state2102Calls = 0;
DWORD __cdecl CamFallback(DWORD disp);              // 0.25, section "0.25 DoppelgangerSettings"

void __cdecl State2102(BYTE *) {
    if (!g_state2102Ok) return;
    LONG n = InterlockedIncrement(&g_state2102Calls);
    __try {
        BYTE *mgr = reinterpret_cast<BYTE *>(kCamMgr);
        if (*reinterpret_cast<const DWORD *>(mgr) != kCamMgrVtable) return;
        BYTE *cam = *reinterpret_cast<BYTE *const *>(mgr + 0xb80);
        if (!cam || !reinterpret_cast<CamIsCurrentFn>(kCamIsCurrent)(mgr, 0, cam)) {
            if (n == 1) Log(1, "state 2102 (TU 0x822ae918) first call: Lara camera not current - nothing");
            return;
        }
        // 0x822c2130 with 0x822bc198
        int id = *reinterpret_cast<const int *>(cam + 0x1d0);
        BYTE *e = id != -1 ? reinterpret_cast<CamSettingsFn>(kCamSettings)(id) : nullptr;
        const bool dg = Doppelganger() != 0;
        if (!e) {
            // 0.25: the TU's doppelganger default is the TU GlobalInfo +0x14c = DTP 21237; the PC GlobalInfo +0x14c is
            // DTP 22 (not camera settings), which 0.11..0.24 read here. Now the choice of the patched fallback blocks
            // (section "0.25 DoppelgangerSettings": 21237 when loaded / stand-in, else the retail +0x144)
            if (!*reinterpret_cast<BYTE *const *>(0x00e7ee50)) return;
            e = reinterpret_cast<BYTE *>(CamFallback(0x144));
        }
        if (!e) return;
        const BYTE *s = e + 0x10;
        float end = *reinterpret_cast<const float *>(s + 0xb8) + *reinterpret_cast<const float *>(s + 0xb4);
        *reinterpret_cast<float *>(cam + 0x1e4) = end;
        if (n == 1 || g_logLevel >= 2)
            Log(n == 1 ? 1 : 2, "state 2102 (TU 0x822ae918 -> 0x822c2130)%s: Lara camera 0x%08lx settings %d%s -> blend "
                "time +0x1e4 = %.2f (end)", n == 1 ? " first call" : "", reinterpret_cast<DWORD>(cam), id,
                id == -1 ? (dg ? " (doppelganger: 0.25 choice)" : " (default +0x144)") : "", end);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 2102: access fault - off");
        g_state2102Ok = false;
    }
}

// 0.13: TruDataGuard.asi replaces the first 5 bytes of the lookup (mov eax,[esp+4] + the first byte of the next
// instruction) with `jmp stub`; the stub does the same lookup plus the bound / record checks, so valid ids give the
// same result (invalid ids: logged, original lookup - this plugin is not one of its "tests for 0" callers). The tail
// from +5 stays the original code.
const char *const kCamSettingsTailHex = "0485286fc300 85c0 740a 80780400 7504 83c010 c3 33c0 c3";

bool InModuleNamed(DWORD address, const char *want) {
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(static_cast<ULONG_PTR>(address)), &module))
        return false;
    char path[MAX_PATH] = {0};
    if (!GetModuleFileNameA(module, path, MAX_PATH)) return false;
    const char *name = strrchr(path, '\\');
    name = name ? name + 1 : path;
    return _stricmp(name, want) == 0;
}

// 1 = original bytes, 2 = TruDataGuard's jump + original tail, 0 = neither
int CamSettingsState(DWORD *target) {
    *target = 0;
    if (HexBytesAt(kCamSettings, kCamSettingsHex)) return 1;
    __try {
        if (*reinterpret_cast<const BYTE *>(kCamSettings) != 0xe9) return 0;
        *target = kCamSettings + 5 + *reinterpret_cast<const DWORD *>(kCamSettings + 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return InModuleNamed(*target, "TruDataGuard.asi") && HexBytesAt(kCamSettings + 5, kCamSettingsTailHex) ? 2 : 0;
}

bool CheckState2102() {
    DWORD target = 0;
    const int lookup = CamSettingsState(&target);
    const char *bad = !HexBytesAt(kCamMgrDtor, kCamMgrDtorHex) ? "camera manager tru+0x43cee0"
                      : !HexBytesAt(kCamIsCurrent, kCamIsCurrentHex) ? "is-current tru+0x1e7fb0"
                      : !HexBytesAt(kCamSnapBody, kCamSnapBodyHex) ? "slot 0x6c body tru+0x202298"
                      : lookup == 0 ? "section lookup tru+0x14df80 (neither original nor TruDataGuard's jump)"
                      : !HexBytesAt(kCamDefaults, kCamDefaultsHex) ? "defaults getter tru+0x1d4080"
                                                                    : nullptr;
    g_state2102Ok = bad == nullptr;
    if (!g_state2102Ok) Log(0, "state 2102: camera code does not match (%s) - not registered", bad);
    else if (lookup == 2)
        Log(1, "state 2102: section lookup tru+0x14df80 jumps to TruDataGuard.asi (0x%08lx) - accepted (same result for "
               "valid ids)", target);
    return g_state2102Ok;
}

// ================================================================================================================
// 0.14 (2026-11-04, project doc Befund-Schattenkraft-0411b.md): the remaining TU parts of the power, each behind its
// own switch, all default 0 (= 0.13 behaviour): the looping sound, the movement events, the camera flag of Start, the
// strike look. Every PC part is byte-checked at load; a mismatch leaves the part off and says so.

// ---- [Sound] LoopSound: the looping sound of the power (TU meter +0x0) ----
// TU 0x823d7700 (meter init, run by the player init after the extension instance exists): gameTracker and 0x82415518
// -> handle = new 0x14-byte object {+0xc = tuning +0x5c, +0x10 = 0}; the weak-node pool is made first when
// [0x829beb60] is 0 (0x82250ed8(0x2000) = PC tru+0x198570(0x2000), [0xcda0c0]); an old handle is freed first by
// 0x823d7680 (0x824805c8, node release, free). tuning +0x5c is a SoundPlex node of player_tru_dlc2_extension (DTP
// 22497 +0x14c -> +0x190: type 1, -> id 22864 = the loop's SoundPlex tree).
// TU tick 0x823d7ae0..0x823d7b34: gameTracker, 0x82415518 and the handle set -> power on (flags & 1):
// 0x82480440(handle, value +8, start value +0xc, value, player [0x82efb464] +0x20), else 0x824805c8(handle).
// 0x82480440 (TU-only): dead node (+0 = 0) -> release; no node -> 0x8223ee58(&node, +0xc) starts the sound (= PC
// tru+0x193c90, the same body: tru+0x1935d0 on the sound manager [0x8a8100] with 0.0, then the dead-node test with the
// free list [0xcda0c4] = TU 0x829beb64); then emitter = node +0: 0x82241918(emitter, &pos) (= PC tru+0x183340:
// +0x68 |= 0x100, +0x70 = pos) and emitter +0x2c / +0x30 / +0x34 = value / start / value (emitter layout: PC
// constructor tru+0x190860 = TU inline constructor in 0x82241b68, both zero seven parameter words +0x28..+0x40).
// 0x824805c8 (TU-only): no node -> nothing; dead node -> release, +0x10 = 0; else (emitter +8)->vtbl[0x10](6) (stop of
// the SoundPlex instance tree: PC slot 0x10 = thiscall(mode) in the same classes, e.g. the forwarders tru+0x183700 /
// tru+0x1838b0 = TU 0x82242fa0 / 0x82243560); the node is kept until the emitter is dead (called every tick).
// PC difference (named): the PC player init is not hooked; the handle is made at the first tick of a tracker
// generation in which object 858's tuning (the game object, as 0x82415518 - not the file copy) exists.
typedef BYTE **(__cdecl *SoundPlayFn)(BYTE **out, const void *data);           // tru+0x193c90 = TU 0x8223ee58
typedef void(__fastcall *SoundPosFn)(BYTE *emitter, int, const float *pos);      // tru+0x183340 = TU 0x82241918
typedef void(__fastcall *SoundStopFn)(void *instance, int, int mode);            // SoundPlex vtbl slot 0x10
typedef void(__cdecl *NodePoolFn)(int count);                                    // tru+0x198570 = TU 0x82250ed8
const DWORD kSoundPlay = 0x00593c90;
const char *const kSoundPlayHex = "d9ee 8b442408 56 8b742408 51 8b0d00818a00 d91c24 50 56 e824f9ffff 8b06 85c0 7428 833800 "
                                  "751d 834004ff 750d 8b0dc4a0cd00 8908 a3c4a0cd00 c70600000000 8bc6 5e c3 8b00 836024fe "
                                  "8bc6 5e c3";
const DWORD kSoundEmit = 0x005935d0;              // TU 0x82241b68: data 0 -> out 0; alloc 0xb0; +0x24 |= 1; +0xc = data +8
const char *const kSoundEmitHex = "53 57 8b7c2410 85ff 8bd9 750f";
const DWORD kSoundEmitAlloc = 0x0059360b;
const char *const kSoundEmitAllocHex = "6a00 68b0000000 ffd0 85c0 740b 8bc8 e841d2ffff";
const DWORD kEmitterParams = 0x0059088d;          // constructor tru+0x190860: +0x28..+0x40 = 0 (parameter words)
const char *const kEmitterParamsHex = "894828 d90530118400 89482c 894830 894834 894838 89483c 894840";
const DWORD kSoundPos = 0x00583340;
const char *const kSoundPosHex = "55 8bec 83e4f0 8bc1 668148680001 83ec0c 56 8d7070 8b4508 8b08 890e";
const DWORD kSoundFwd1 = 0x00583700, kSoundFwd2 = 0x005838b0;   // slot 0x10 forwarders (TU 0x82242fa0 / 0x82243560)
const char *const kSoundFwd1Hex = "d9ee d9592c 8b4914 8b01 8b4010 ffe0";
const char *const kSoundFwd2Hex = "8b4914 8b01 8b4010 ffe0";
const DWORD kNodePool = 0x00598570;
const char *const kNodePoolHex = "833dc0a0cd0000 757e a1ac9ccd00";
const DWORD kNodePoolHead = 0x00cda0c0, kNodeFree = 0x00cda0c4;   // TU 0x829beb60 / 0x829beb64
const DWORD kSoundMgr = 0x008a8100;                               // TU [0x827741c0]

struct LoopHandle { DWORD unused[3]; const void *data; BYTE *node; };   // TU: 0x14 bytes, +0xc data, +0x10 node
LoopHandle g_loopStore;
LoopHandle *g_loop = nullptr;                   // TU meter +0x0
bool g_loopOk = false, g_loopMake = true, g_loopWasOn = false;
volatile LONG g_loopNodes = 0, g_loopStopCalls = 0, g_loopNoEmitter = 0;

// TU (inline everywhere): --node+4; at 0 the node goes to the head of the free list
void NodeRelease(BYTE *node) {
    LONG *count = reinterpret_cast<LONG *>(node + 4);
    if (--*count == 0) {
        *reinterpret_cast<DWORD *>(node) = *reinterpret_cast<const DWORD *>(kNodeFree);
        *reinterpret_cast<DWORD *>(kNodeFree) = reinterpret_cast<DWORD>(node);
    }
}

// TU 0x824805c8
void LoopStop(LoopHandle *h) {
    BYTE *node = h->node;
    if (!node) return;
    BYTE *emitter = *reinterpret_cast<BYTE **>(node);
    if (!emitter) {
        NodeRelease(node);
        h->node = nullptr;
        return;
    }
    void *instance = *reinterpret_cast<void **>(emitter + 8);
    SoundStopFn stop = (*reinterpret_cast<SoundStopFn *const *>(instance))[0x10 / 4];
    stop(instance, 0, 6);
    if (InterlockedIncrement(&g_loopStopCalls) == 1)
        Log(1, "loop sound: first stop (TU 0x824805c8: emitter 0x%08lx +8 -> vtbl[0x10](6))", reinterpret_cast<DWORD>(emitter));
}

// TU 0x82480440
void LoopPlay(LoopHandle *h, float a, float b, float c, const float *pos) {
    BYTE *node = h->node;
    if (node) {
        if (*reinterpret_cast<BYTE **>(node)) goto alive;
        NodeRelease(node);
        h->node = nullptr;
    }
    {
        BYTE *made = nullptr;
        reinterpret_cast<SoundPlayFn>(kSoundPlay)(&made, h->data);
        BYTE *old = h->node;                    // the smart-pointer assignment of 0x824804c0..0x82480508
        if (old) NodeRelease(old);
        h->node = made;
        if (made) ++*reinterpret_cast<LONG *>(made + 4);
        if (made) NodeRelease(made);            // the temporary's release 0x8248050c..0x8248053c
        if (made) {
            LONG k = InterlockedIncrement(&g_loopNodes);
            if (k == 1 || g_logLevel >= 2)
                Log(k == 1 ? 1 : 2, "loop sound: started (TU 0x8223ee58 = tru+0x193c90: data 0x%08lx, emitter 0x%08lx)%s",
                    reinterpret_cast<DWORD>(h->data), *reinterpret_cast<const DWORD *>(made), k == 1 ? ", first time" : "");
        } else if (InterlockedIncrement(&g_loopNoEmitter) <= 3) {
            Log(1, "loop sound: tru+0x193c90 made no emitter (data 0x%08lx) - nothing plays (retried every tick as the TU)",
                reinterpret_cast<DWORD>(h->data));
        }
    }
alive:
    node = h->node;
    if (!node) return;
    {
        BYTE *emitter = *reinterpret_cast<BYTE **>(node);
        if (!emitter) {
            NodeRelease(node);
            h->node = nullptr;
            return;
        }
        __declspec(align(16)) float p[4];
        memcpy(p, pos, sizeof(p));
        reinterpret_cast<SoundPosFn>(kSoundPos)(emitter, 0, p);
        emitter = *reinterpret_cast<BYTE **>(h->node);
        *reinterpret_cast<float *>(emitter + 0x2c) = a;
        *reinterpret_cast<float *>(emitter + 0x30) = b;
        *reinterpret_cast<float *>(emitter + 0x34) = c;
    }
}

// TU 0x823d7680 (stop, node release, free) - from 0x823d7700 and the player teardown 0x82412ea8
void LoopFree(const char *why) {
    g_loopMake = true;
    LoopHandle *h = g_loop;
    if (!h) return;
    __try {
        LoopStop(h);
        if (h->node) NodeRelease(h->node);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "loop sound: access fault while freeing the handle - loop sound off");
        g_loopOk = false;
    }
    h->node = nullptr;
    g_loop = nullptr;
    Log(2, "loop sound: handle freed (%s, TU 0x823d7680)", why);
}

// TU 0x823d7700's handle part
void LoopMake(const BYTE *tuning) {
    if (g_loop) LoopFree("meter init");
    LoopHandle *h = &g_loopStore;
    memset(h, 0, sizeof(*h));
    const void *data = *reinterpret_cast<const void *const *>(tuning + 0x5c);
    h->node = nullptr;
    if (*reinterpret_cast<const DWORD *>(kNodePoolHead) == 0) reinterpret_cast<NodePoolFn>(kNodePool)(0x2000);
    h->data = data;
    g_loop = h;
    g_loopMake = false;
    Log(1, "loop sound: handle made (TU 0x823d7700: tuning +0x5c = SoundPlex data 0x%08lx of object 858)",
        reinterpret_cast<DWORD>(data));
}

// TU 0x823d7ae0..0x823d7b34, once per tick
void LoopTick(BYTE *gt) {
    if (!g_loopOk) return;
    __try {
        const BYTE *tuning = ObjectTuning();                // TU 0x82415518 (the game object)
        if (g_loopMake && gt && tuning) LoopMake(tuning);
        if (!gt || !tuning || !g_loop) return;
        const bool on = (g_meter.flags & 1) != 0;
        if (on) {
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(kPlayerPtr);
            if (!player) return;
            LoopPlay(g_loop, g_meter.value, g_meter.startValue, g_meter.value,
                     reinterpret_cast<const float *>(player + 0x20));
        } else {
            LoopStop(g_loop);
        }
        if (on != g_loopWasOn) {
            Log(2, "loop sound: power %s -> %s", on ? "on" : "off",
                on ? "TU 0x82480440 (keep playing, position, parameters)" : "TU 0x824805c8 (stop 6)");
            g_loopWasOn = on;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "loop sound: access fault in the sound code - loop sound off for this run");
        g_loopOk = false;
    }
}

void CheckLoopSound() {
    if (!g_loopSound) return;
    const char *bad = !HexBytesAt(kSoundPlay, kSoundPlayHex) ? "start tru+0x193c90"
                      : !HexBytesAt(kSoundEmit, kSoundEmitHex) ? "emitter tru+0x1935d0"
                      : !HexBytesAt(kSoundEmitAlloc, kSoundEmitAllocHex) ? "emitter alloc tru+0x19360b"
                      : !HexBytesAt(kEmitterParams, kEmitterParamsHex) ? "emitter constructor tru+0x19088d"
                      : !HexBytesAt(kSoundPos, kSoundPosHex) ? "position tru+0x183340"
                      : !HexBytesAt(kSoundFwd1, kSoundFwd1Hex) || !HexBytesAt(kSoundFwd2, kSoundFwd2Hex) ? "slot 0x10 forwarders"
                      : !HexBytesAt(kNodePool, kNodePoolHex) ? "node pool tru+0x198570"
                      : !g_tableOk ? "object table (tuning lookup)"
                                   : nullptr;
    g_loopOk = bad == nullptr;
    if (!g_loopOk)
        Log(0, "loop sound: code does not match (%s) - off", bad);
    else
        Log(1, "loop sound: [Sound] LoopSound=1 - TU 0x823d7ae0..0x823d7b34 per tick (start / position / parameters "
               "0x82480440 while the power is on, stop 0x824805c8 when off), sound manager [0x%08lx], free list [0x%08lx]",
            kSoundMgr, kNodeFree);
}

// ---- [Look] MoveEvents: TU 0x823d77f0 (per tick) and Start's event 0x83 ----
// gameTracker+0x1f0 is the same field on the PC: the PC twin of retail 0x824077e0 (TU 0x8240a430, player anim-event
// switch) = tru+0x316f30 (map: verified) builds `mov eax, [0xfadb58]; add eax, 0x1f0` at tru+0x317eb6 exactly where
// retail 0x8240965c / TU 0x8240c3f0 build gameTracker+0x1f0 (same block: [0xfada74] |= 8, [0xfad754] = 10, then the
// vector to tru+0x30b7c0 = retail 0x824173d8). Length = vdot3fp128 + vrsqrtefp128 with one Newton step on the TU
// (0 when the dot product is 0); here sqrtf (same value to float precision).
const DWORD kMoveFieldSite = 0x00717e9e;
const char *const kMoveFieldHex = "a158dbfa00 830d74dafa0008 d915f0dffa00 d91df4dffa00 05f0010000";
bool g_moveOk = false;
volatile LONG g_move83 = 0, g_move84 = 0, g_moveRuns = 0;

bool MoveLength(float *length) {
    if (!g_moveOk) return false;
    const BYTE *gt = GameTracker();
    if (!gt) return false;
    const float *v = reinterpret_cast<const float *>(gt + 0x1f0);
    float d = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    *length = (d == 0.0f) ? d : sqrtf(d);
    return true;
}

// TU 0x823d77f0, branch for branch (fcmpu: an unordered compare takes neither bgt nor ble)
void MoveEvents() {
    if (!g_moveOk) return;
    __try {
        float len = 0.0f;
        if (!MoveLength(&len)) return;
        if (InterlockedIncrement(&g_moveRuns) == 1)
            Log(1, "move events: TU 0x823d77f0 runs (|gameTracker+0x1f0| = %.2f, meter +0x30 = %.2f)", len, g_meter.moveLength);
        const float limit = 10.0f;                           // [0x8205262c]
        const bool active = (g_meter.flags & 1) != 0;
        const DWORD clock = *kTuClock;                       // [0x82efb458 +0xd0] = 0x82efb528
        if (!active) goto L9b8;
        if (g_meter.moveLength > limit) goto L8b4;           // 0x823d782c bgt
        if (len <= limit) goto L8b4;                          // 0x823d7878 ble
        if (static_cast<float>(g_meter.moveSince) >= 0.0f) goto L9c0;   // 0x823d78a0 bge
        g_meter.moveSince = static_cast<LONG>(clock);         // rising edge: +0x34 = clock
        goto L9c0;
    L8b4:
        if (!active) goto L9b8;
        if (g_meter.moveLength <= limit) goto L93c;           // 0x823d78c4 ble
        if (len > limit) goto L93c;                           // 0x823d7910 bgt
        {
            bool f = FireEvent(0x84);                         // falling edge
            LONG k = InterlockedIncrement(&g_move84);
            if (k == 1 || g_logLevel >= 2)
                Log(k == 1 ? 1 : 2, "move events: speed fell to %.1f (<= 10) - player event 0x84 %s (TU 0x823d7928)%s", len,
                    f ? "fired" : "not fired", k == 1 ? ", first time" : "");
        }
        g_meter.moveSince = -1;
        goto L9c0;
    L93c:
        if (!active) goto L9b8;
        if (static_cast<float>(g_meter.moveSince) <= 0.0f) goto L9b8;   // 0x823d7968 ble
        if (static_cast<float>(static_cast<DWORD>(clock - static_cast<DWORD>(g_meter.moveSince))) <= 3000.0f)
            goto L9b8;                                         // 0x823d799c ble ([0x8207d938] = 3000.0)
        {
            bool f = FireEvent(0x83);
            LONG k = InterlockedIncrement(&g_move83);
            if (k == 1 || g_logLevel >= 2)
                Log(k == 1 ? 1 : 2, "move events: moving for > 3000 ms (%.1f) - player event 0x83 %s (TU 0x823d79ac)%s", len,
                    f ? "fired" : "not fired", k == 1 ? ", first time" : "");
        }
        goto L9c0;
    L9b8:
        g_meter.moveSince = -1;
    L9c0:
        g_meter.moveLength = len;                             // 0x823d79c0..0x823d7a04 (+0x30 = the length again)
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "move events: access fault - off");
        g_moveOk = false;
    }
}

void CheckMoveEvents() {
    if (!g_moveEvents) return;
    g_moveOk = HexBytesAt(kMoveFieldSite, kMoveFieldHex) && g_lookOk && g_lookEnabled;
    if (!g_moveOk)
        Log(0, "move events: gameTracker+0x1f0 reader tru+0x317e9e or the player event walker does not match / [Look] "
               "Enabled=0 - off");
    else
        Log(1, "move events: [Look] MoveEvents=1 - TU 0x823d77f0 per tick (events 0x84 / 0x83 by |gameTracker+0x1f0| "
               "against 10.0 and 3000 ms) and event 0x83 at the start while moving");
}

// ---- [Look] CameraFlag: Start's (*0x82efc780)->vtbl[0xa4]() ----
// TU manager 0x82efc780 (vtable 0x82068930) = PC 0xe804f0 (vtable 0x855ae4, state 2102 / docs L3). The bit helpers
// are in the same order on both: slots 0x8c..0xac = set / clear / test of bit 4, bit 1, bit 2 (TU 0x822a9df8..
// 0x822a9e78 on +0x7c, PC tru+0x1eb1a0..0x1eb220 on +0x80); slot 0xa4 = TU 0x822a9e58 = PC tru+0x1eb200 (+0x80 |= 2).
// The PC retail strike look (tru+0x315020 = retail 0x823e0308) makes the same call (`call 0x5e7770(0)` -> vtbl[0xa4]);
// the TU moved it into Start. Reader of the bit (TU 0x822a9a7c in 0x822a9888 = retail 0x822ac840: other camera curves)
// = PC tru+0x1e5e8e in tru+0x1e5bc0 (0.20): getter, vtbl[0xac] = tru+0x1eb220 (`[+0x80] >> 1 & 1`), then curve set
// +0x9c / +0xe8 (bit set) or +0x4 / +0x50 through tru+0x1f20a0 (= TU 0x822b6840) - checked below, not patched.
const DWORD kCamSlotA4 = 0x00855ae4 + 0xa4;
const DWORD kCamSet2 = 0x005eb200;
const char *const kCamSet2Hex = "83898000000002 c3";
const DWORD kCamRetailCall = 0x00715103;            // tru+0x315020: push 0; call 0x5e7770; ...; call [edx+0xa4]
const char *const kCamRetailCallHex = "6a00 e86626edff 8b10 8bc8 8b82a4000000 83c414 ffd0";
const DWORD kCamSlotAC = 0x00855ae4 + 0xac;         // 0.20: the bit-2 test the reader calls
const DWORD kCamTest2 = 0x005eb220;
const char *const kCamTest2Hex = "8b8180000000 d1e8 2401 c3";
const DWORD kCamReader = 0x005e5e8e;                // 0.20: tru+0x1e5bc0's test of the bit and the curve choice
const char *const kCamReaderHex = "e8dd180000 8b10 8bc8 8b82ac000000 83c404 ffd0 d944242c 84c0 51 d91c24 7414 "
                                  "8d8f9c000000 51 e8e6c10000 8d9fe8000000 eb0c 8d5704 52 e8d5c10000 8d5f50";
bool g_camFlagOk = false;
volatile LONG g_camFlagCalls = 0;

void StartCameraFlag() {
    if (!g_camFlagOk || !Doppelganger()) return;            // TU Start exists only with the DLC 2 meter (as FireEvent)
    __try {
        BYTE *mgr = reinterpret_cast<BYTE *>(kCamMgr);
        const DWORD *vtbl = *reinterpret_cast<const DWORD *const *>(mgr);
        LONG k = InterlockedIncrement(&g_camFlagCalls);
        if (reinterpret_cast<DWORD>(vtbl) != kCamMgrVtable || vtbl[0xa4 / 4] != kCamSet2) {
            if (k == 1) Log(1, "camera flag: manager 0x%08lx has vtable 0x%08lx - not called", kCamMgr, reinterpret_cast<DWORD>(vtbl));
            return;
        }
        DWORD before = *reinterpret_cast<const DWORD *>(mgr + 0x80);
        reinterpret_cast<void(__fastcall *)(void *, int)>(vtbl[0xa4 / 4])(mgr, 0);
        DWORD after = *reinterpret_cast<const DWORD *>(mgr + 0x80);
        if (k == 1 || g_logLevel >= 2)
            Log(k == 1 ? 1 : 2, "camera flag: TU 0x823d7f14 (*0x82efc780)->vtbl[0xa4] = tru+0x1eb200 on 0x%08lx: +0x80 0x%08lx "
                "-> 0x%08lx%s", kCamMgr, before, after, k == 1 ? ", first time - the camera reader tru+0x1e5e8e (TU "
                "0x822a9a7c) now takes the second curve set +0x9c / +0xe8 until the next camera reset" : "");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "camera flag: access fault - off");
        g_camFlagOk = false;
    }
}

void CheckCameraFlag() {
    if (!g_cameraFlag) return;
    const char *bad = nullptr;
    if (*reinterpret_cast<const DWORD *>(kCamSlotA4) != kCamSet2 || !HexBytesAt(kCamSet2, kCamSet2Hex))
        bad = "vtable 0x855ae4 slot 0xa4 / tru+0x1eb200";
    else if (!HexBytesAt(kCamRetailCall, kCamRetailCallHex)) bad = "retail strike look call tru+0x315103";
    else if (!HexBytesAt(kCamMgrDtor, kCamMgrDtorHex)) bad = "camera manager tru+0x43cee0";
    else if (*reinterpret_cast<const DWORD *>(kCamSlotAC) != kCamTest2 || !HexBytesAt(kCamTest2, kCamTest2Hex))
        bad = "vtable 0x855ae4 slot 0xac / tru+0x1eb220";                            // 0.20
    else if (!HexBytesAt(kCamReader, kCamReaderHex)) bad = "camera reader tru+0x1e5e8e";   // 0.20
    g_camFlagOk = bad == nullptr;
    if (!g_camFlagOk)
        Log(0, "camera flag: %s does not match - off", bad);
    else
        Log(1, "camera flag: [Look] CameraFlag=1 - Start calls the camera manager 0x%08lx vtbl[0xa4] (+0x80 |= 2, TU "
               "0x823d7f00); reader tru+0x1e5e8e (TU 0x822a9a7c, vtbl[0xac] = tru+0x1eb220) checked", kCamMgr);
}

// ---- [Look] StrikeLook: the shadow-strike look, TU 0x823d8a80 (anim event 5) / 0x823d9050 (anim event 4) ----
// TU switch 0x8240a430 (= PC tru+0x316f30, map verified): case 5 (0x8240a67c) / case 4 (0x8240a6c0) call, when
// gameTracker+0x1244 is set, 0x823d8a80 / 0x823d9050 with the meter, else the retail 0x823e0308 / 0x823e07e8 with
// gameTracker+0x504 (= PC tru+0x315020 / tru+0x318ea0, called at tru+0x316f6b / tru+0x316f86 with ecx = [gt+0x504]).
// The TU functions are the retail ones moved into the meter: retail player time ramp -> request slot 2 (tuning +0x50
// player / +0x4c world), events 0x32 / 0x33 -> the inline walks of type 0x7a / 0x7b (= 0x82418158 = PC tru+0x318780),
// player +0x1fc bit 29 -> meter flag 4, camera vtbl[0xa4] / [0xa8] -> not called (Start does vtbl[0xa4]).
// 0x823d8a80: flag 2 set and flag 4 clear; request 2; type 0x7a; target = handle meter +0x18 / +0x1c (valid when
// target +0x44 == +0x1c): [0x829bffa4] = +0x28, q = target->+0x11c(0x188) (= PC tru+0x1b3720(target, 0x188, +0x28),
// [0xd98f9c]), point = (target +0x90)[q] row +0x30 -> 0x823e2b98(P->+0, &point); no target -> 0x823e2b98(P->+0, 0);
// (P->+4)->+0x40 |= 0x200; +0x15 = 0; flags |= 4 (P = [gameTracker+0x504]).
// 0x823e2b98(A, point) = retail 0x823e0540 (= PC tru+0x30db20, called by tru+0x315119 with ecx = [P]) plus the point
// argument: point 0 -> the retail body; else A +0x3c == 0 -> return, the target point = *point instead of
// 0x82406690(target), then the retail tail (written out from PC tru+0x30db60..0x30dbd2: tru+0x3020e0, tru+0x2e6a70,
// A +0x20, HUD 0x802 / mask 2 / update, [0xfae8ae] = 0, A +0x44 / +0x48 = 0, A +0x40 |= 0x40).
// 0x823d9050: flag 4 set: request 2 cleared; type 0x7b; 0x823e2ca0(P->+0) (= PC tru+0x2e6ca0); (P->+0) / (P->+4)
// +0x40 &= ~0x200; flags &= ~4. Also called by Stop (flag 2) and by the strike tick / end (TruShadowCombat, through
// the meter interface v4 strikeLookOff). The strike's meter fields +0x15 / +0x18 / +0x1c / +0x28 are
// TruShadowCombat's (TruShadowCombatStrikeState).
typedef void(__fastcall *ThisFn)(void *self, int);
typedef int(__cdecl *QueryArgFn)(BYTE *instance, int id, void *arg);            // tru+0x1b3720
typedef void(__cdecl *AimProjectFn)(float *out, char *b1, char *b0, const float *point);   // tru+0x3020e0 = TU 0x82418600
typedef float *(__fastcall *AimVectorFn)(BYTE *a, int, float *out, const float *in);       // tru+0x2e6a70 = TU 0x823e20e8
const DWORD kCase5Site = 0x00716f5f, kCase5Call = 0x00716f6b, kRetail5 = 0x00715020;
const char *const kCase5Hex = "8b0d58dbfa00 8b8904050000 e8b0e0ffff 8b451c";
const DWORD kCase4Site = 0x00716f7a, kCase4Call = 0x00716f86, kRetail4 = 0x00718ea0;
const char *const kCase4Hex = "8b1558dbfa00 8b8a04050000 e8151f0000 8b451c";
const DWORD kCaseIndex = 0x0071811c;                // byte index of the switch: cases 1..5 -> 0, 1, 2, 3, 4
const char *const kCaseIndexHex = "00010203 04";
const DWORD kCaseTable = 0x00718024;
const char *const kRetail5Hex = "83ec0c 56 8bf1 8b86fc010000 8bc8 c1e915 f6c101";
const char *const kRetail4Hex = "83ec0c 56 8bf1 8b86fc010000 c1e81d a801";
const DWORD kRetail5Aim = 0x00715119;               // mov ecx,[esi]; call tru+0x30db20; mov eax,[esi+4]; or word [eax+0x40],0x200
const char *const kRetail5AimHex = "8b0e e8008affff 8b4604 668148400002";
const DWORD kRetail4Off = 0x00718f89;               // the PC's inline copy of 0x823e2ca0 and the two 0x200 clears
const char *const kRetail4OffHex = "8b3e 6a0b e8de4b0600 6a01 e8374a0600 6a01 e8a04a0600 83c40c e8c84a0600 668167403fff "
                                   "8b06 b9fffd0000 66214840 8b4604 66214840";
const DWORD kAimRetail = 0x0070db20;
const char *const kAimRetailHex =
    "55 8bec 83e4f0 83ec38 56 8bf1 57 8b7e3c 85ff 0f849d000000 57 e8925eeaff 83c404 85c0 741b f7401400004000 7512 "
    "8b4f0c 51 50 8d542418 52 e8e314ffff 83c40c 8d442410 50 8d4c2412 51 8d542417 52 8d44242c 50 e86745ffff 83c410 "
    "8d4c2420 51 8d542434 52 8bce e8e38efdff 8b08 894e20 8b5004 895624 8b4808 894e28 8b500c 6a0b 89562c e825fe0600 "
    "6a01 e81efe0600 6a01 e867fe0600 83c40c e8affe0600 d9ee c605aee8fa0000 d95648 66834e4040 d95e44 5f 5e 8be5 5d c3";
const DWORD kAimProject = 0x007020e0;
const char *const kAimProjectHex = "55 8bec 83e4f0 83ec34 8b0d94f0e700 8b450c";
const DWORD kAimVector = 0x006e6a70;
const char *const kAimVectorHex = "55 8bec 83e4f0 83ec28 56 8b7508 57 8bf9";
const DWORD kAimOff = 0x006e6ca0;
const char *const kAimOffHex = "56 6a0b 8bf1 e8c66e0900 6a01 e81f6d0900 6a01 e8886d0900 83c40c e8b06d0900 668166403fff 5e c3";
const DWORD kHudMask2Set = 0x0077da20;
const char *const kHudMask2SetHex = "8b4c2404 8d41ff 83f81e 770e ba01000000 d3e2 091528e9fa00 c3";
const DWORD kQueryArg = 0x005b3720;
const char *const kQueryArgHex = "8b4c2404 8b44240c 8d9110010000 85d2 a39c8fd900 740a 8b811c010000 85c0";
const DWORD kHudStrikeByte = 0x00fae8ae;            // TU 0x829ca67f (retail 0x829ca5be)
bool g_strikeLookOk = false;
volatile LONG g_slOn = 0, g_slOff = 0, g_slEvent5 = 0, g_slEvent4 = 0;

struct TruShadowCombatStrike { DWORD size, version; BYTE *latch; DWORD *target; LONG *count; float *frames; };
const TruShadowCombatStrike *g_strikeState = nullptr;
int g_strikeStateLooked = 0;

const TruShadowCombatStrike *StrikeState() {
    if (!g_strikeStateLooked) {
        g_strikeStateLooked = 1;
        HMODULE m = GetModuleHandleA("TruShadowCombat.asi");
        typedef const TruShadowCombatStrike *(__cdecl *StateFn)();
        StateFn fn = m ? reinterpret_cast<StateFn>(GetProcAddress(m, "TruShadowCombatStrikeState")) : nullptr;
        const TruShadowCombatStrike *s = fn ? fn() : nullptr;
        if (s && s->size >= sizeof(TruShadowCombatStrike) && s->version >= 1 && s->latch && s->target && s->count) {
            g_strikeState = s;
            Log(1, "strike look: TruShadowCombatStrikeState version %lu found (target handle / count / latch of the strike)",
                s->version);
        } else {
            Log(0, "strike look: TruShadowCombat.asi / TruShadowCombatStrikeState not found - the look runs without a target");
        }
    }
    return g_strikeState;
}

// TU 0x823e2b98
void AimAt(BYTE *a, const float *point) {
    if (!point) { reinterpret_cast<ThisFn>(kAimRetail)(a, 0); return; }
    if (!*reinterpret_cast<void *const *>(a + 0x3c)) return;
    __declspec(align(16)) float pt[4];
    __declspec(align(16)) float proj[4];
    __declspec(align(16)) float out[4];
    struct { char b0, b1; } bytes = {0, 0};
    memcpy(pt, point, sizeof(pt));
    reinterpret_cast<AimProjectFn>(kAimProject)(proj, &bytes.b1, &bytes.b0, pt);
    const float *r = reinterpret_cast<AimVectorFn>(kAimVector)(a, 0, out, proj);
    memcpy(a + 0x20, r, 16);
    if (g_hudOk && *kHudManager && HudPlayerOk("strike look aim")) {     // 0.16: the HUD script needs the player state
        g_hudGroup(0xb);
        g_hudGroup(1);
        reinterpret_cast<HudGroupFn>(kHudMask2Set)(1);
        g_hudUpdate();
    }
    *reinterpret_cast<volatile BYTE *>(kHudStrikeByte) = 0;
    *reinterpret_cast<float *>(a + 0x48) = kZero;
    *reinterpret_cast<WORD *>(a + 0x40) |= 0x40;
    *reinterpret_cast<float *>(a + 0x44) = kZero;
}

// TU 0x823d8a80
void StrikeLookOn() {
    if (!(g_meter.flags & 2) || (g_meter.flags & 4)) return;
    BYTE *gt = GameTracker();
    if (!gt) return;
    const BYTE *tuning = g_tuning;
    if (tuning) {
        g_meter.request[2][0] = Tune(tuning, 0x50);           // +0x50 = tuning +0x50 (player)
        g_meter.request[2][1] = Tune(tuning, 0x4c);           // +0x54 = tuning +0x4c (world)
        Selector();
    }
    const bool ev = FireEvent(0x7a);
    const TruShadowCombatStrike *s = StrikeState();
    BYTE *target = nullptr;
    if (s) {
        BYTE *o = reinterpret_cast<BYTE *>(s->target[0]);
        if (o && *reinterpret_cast<const DWORD *>(o + 0x44) == s->target[1]) target = o;
    }
    BYTE *p = *reinterpret_cast<BYTE **>(gt + 0x504);
    BYTE *a = *reinterpret_cast<BYTE **>(p);
    int q = -1;
    if (target) {
        q = reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x188, reinterpret_cast<void *>(static_cast<LONG_PTR>(*s->count)));
        const BYTE *mats = *reinterpret_cast<const BYTE *const *>(target + 0x90);
        __declspec(align(16)) float point[4];
        memcpy(point, mats + (static_cast<DWORD>(q) << 6) + 0x30, sizeof(point));
        AimAt(a, point);
    } else {
        AimAt(a, nullptr);
    }
    *reinterpret_cast<WORD *>(*reinterpret_cast<BYTE **>(p + 4) + 0x40) |= 0x200;
    if (s) *s->latch = 0;
    g_meter.flags |= 4;
    LONG k = InterlockedIncrement(&g_slOn);
    if (k == 1 || g_logLevel >= 2)
        Log(k == 1 ? 1 : 2, "strike look ON (TU 0x823d8a80%s): request 2 = %.3f / %.3f, event 0x7a %s, target 0x%08lx (query "
            "0x188 -> %d), second model +0x40 |= 0x200, meter flags 0x%03lx", k == 1 ? ", first time" : "",
            tuning ? Tune(tuning, 0x50) : 0.0f, tuning ? Tune(tuning, 0x4c) : 0.0f, ev ? "fired" : "not fired",
            reinterpret_cast<DWORD>(target), q, g_meter.flags);
}

// TU 0x823d9050
void StrikeLookOffBody() {
    if (!(g_meter.flags & 4)) return;
    BYTE *gt = GameTracker();
    if (!gt) return;
    if (g_tuning) {
        g_meter.request[2][0] = g_meter.request[2][1] = kNoRequest;
        Selector();
    }
    const bool ev = FireEvent(0x7b);
    BYTE *p = *reinterpret_cast<BYTE **>(gt + 0x504);
    reinterpret_cast<ThisFn>(kAimOff)(*reinterpret_cast<BYTE **>(p), 0);
    *reinterpret_cast<WORD *>(*reinterpret_cast<BYTE **>(p) + 0x40) &= 0xfdff;
    *reinterpret_cast<WORD *>(*reinterpret_cast<BYTE **>(p + 4) + 0x40) &= 0xfdff;
    g_meter.flags &= ~4u;
    LONG k = InterlockedIncrement(&g_slOff);
    if (k == 1 || g_logLevel >= 2)
        Log(k == 1 ? 1 : 2, "strike look OFF (TU 0x823d9050%s): request 2 cleared, event 0x7b %s, HUD tru+0x2e6ca0, 0x200 "
            "cleared on both models, meter flags 0x%03lx", k == 1 ? ", first time" : "", ev ? "fired" : "not fired",
            g_meter.flags);
}

void StrikeLookOff() {
    if (!g_strikeLookOk) return;
    __try {
        StrikeLookOffBody();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "strike look: access fault in 0x823d9050 - strike look off (retail handlers again)");
        g_strikeLookOk = false;
    }
}

// tru+0x316f6b / tru+0x316f86: `call tru+0x315020` / `call tru+0x318ea0` with ecx = [gameTracker+0x504]
void __fastcall AnimEvent5(BYTE *p, int) {
    if (g_strikeLookOk && Doppelganger()) {
        if (InterlockedIncrement(&g_slEvent5) == 1)
            Log(1, "strike look: player anim event 5 in doppelganger mode -> TU 0x823d8a80 (meter flags 0x%03lx)", g_meter.flags);
        __try {
            StrikeLookOn();
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            Log(0, "strike look: access fault in 0x823d8a80 - strike look off (retail handlers again)");
            g_strikeLookOk = false;
        }
        return;
    }
    reinterpret_cast<ThisFn>(kRetail5)(p, 0);
}

void __fastcall AnimEvent4(BYTE *p, int) {
    if (g_strikeLookOk && Doppelganger()) {
        if (InterlockedIncrement(&g_slEvent4) == 1)
            Log(1, "strike look: player anim event 4 in doppelganger mode -> TU 0x823d9050 (meter flags 0x%03lx)", g_meter.flags);
        StrikeLookOff();
        return;
    }
    reinterpret_cast<ThisFn>(kRetail4)(p, 0);
}

bool CallTargetIs(DWORD at, DWORD target) {
    __try {
        return *reinterpret_cast<const BYTE *>(at) == 0xe8 && at + 5 + *reinterpret_cast<const DWORD *>(at + 1) == target;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

void PatchStrikeLook() {
    if (!g_strikeLook) return;
    const DWORD *table = reinterpret_cast<const DWORD *>(kCaseTable);
    const char *bad = !HexBytesAt(kCase5Site, kCase5Hex) || !CallTargetIs(kCase5Call, kRetail5) ? "case 5 tru+0x316f5f"
                      : !HexBytesAt(kCase4Site, kCase4Hex) || !CallTargetIs(kCase4Call, kRetail4) ? "case 4 tru+0x316f7a"
                      : !HexBytesAt(kCaseIndex, kCaseIndexHex) || table[3] != kCase4Site || table[4] != kCase5Site
                          ? "switch tables tru+0x31811c / tru+0x318024"
                      : !HexBytesAt(kRetail5, kRetail5Hex) || !HexBytesAt(kRetail4, kRetail4Hex) ? "retail look tru+0x315020 / tru+0x318ea0"
                      : !HexBytesAt(kRetail5Aim, kRetail5AimHex) || !HexBytesAt(kRetail4Off, kRetail4OffHex) ? "retail look body"
                      : !HexBytesAt(kAimRetail, kAimRetailHex) ? "aim tru+0x30db20"
                      : !HexBytesAt(kAimProject, kAimProjectHex) || !HexBytesAt(kAimVector, kAimVectorHex) ? "aim helpers"
                      : !HexBytesAt(kAimOff, kAimOffHex) || !HexBytesAt(kHudMask2Set, kHudMask2SetHex) ? "HUD tru+0x2e6ca0 / tru+0x37da20"
                      : !HexBytesAt(kQueryArg, kQueryArgHex) ? "query tru+0x1b3720"
                      : !g_lookOk || !g_lookEnabled ? "player event walker / [Look] Enabled"
                                                    : nullptr;
    if (bad) { Log(0, "strike look: code does not match (%s) - off", bad); return; }
    g_strikeLookOk = true;                   // before the patch: the stubs read it
    if (!WriteCall5(kCase5Call, reinterpret_cast<const void *>(&AnimEvent5)) ||
        !WriteCall5(kCase4Call, reinterpret_cast<const void *>(&AnimEvent4))) {
        Log(0, "strike look: VirtualProtect failed (%lu)", GetLastError());
        return;
    }
    Log(1, "strike look: [Look] StrikeLook=1 - player anim events 5 / 4 (tru+0x316f6b / tru+0x316f86) run TU 0x823d8a80 / "
           "0x823d9050 in doppelganger mode, else the PC handlers tru+0x315020 / tru+0x318ea0; Stop runs 0x823d9050 "
           "with flag 2; meter interface v4 strikeLookOff for TruShadowCombat");
}

// ---- 0.15 [Cloth] TuTimeStep: the TU's player cloth time step (TU 0x82278120, retail 0x8227b220) ----
// TU 0x82278120 = PC tru+0x1bbe70, cdecl(instance) (TU callers 0x822995a8 / 0x82299d88, PC tru+0x1d4688 /
// tru+0x1dfee1): after the instance's own part it looks up component type 14 (the cloth, Lara's ponytail; TU
// 0x82275ab0) and updates it with the frame time. Retail 0x8227b2dc..0x8227b2e8 (= the PC code): dt = [0x82efb358
// +0x100]. TU 0x822781dc..0x822781f8, gt = 0x82efb458 (= PC 0xe7f088, the same field offsets):
//     r10 = [gt+0xc]        the player instance                       PC [0xe7f094]
//     f1  = [gt+0x100]      frame time * world time scale             PC [0xe7f188] (tru+0x1da5af / 0x1da5b5)
//     if (r26 == r10)       r26 = the function's ARGUMENT (the instance; 0x8227812c mr r26,r3), not the component
//         f1 /= [gt+0x118]  the world time scale                      PC [0xe7f1a0] (tru+0x1da595)
//     bl 0x82102e70         component update (component, f1)          PC tru+0x5d680
// There is no other test in the TU (no gameTracker+0x1244, no scale > 0): the player's cloth runs on the unscaled
// frame time wherever the world is slowed (shadow power 0.3, base-game slow motion). Site tru+0x1bbec2 (6 bytes
// fld dword [0xe7f188]): esi / edi are already restored, so the instance is the argument [esp+4]; eax = the component
// (kept), ecx and the flags are dead there (push ecx only makes room for the fstp).
const DWORD kClothFunc = 0x005bbe70;                           // TU 0x82278120 / retail 0x8227b220
const char *const kClothFuncHex = "56 8b742408 f6461c01 57 7409 56 e8fe23eaff 83c404 8b7e70 83c668";
const DWORD kClothSite = 0x005bbeb5;                           // component lookup end .. call tru+0x5d680 .. ret
const char *const kClothSiteHex = "3bc1 5f 5e 7418 8b4004 85c0 7411 d90588f1e700 51 8bc8 d91c24 e8ad17eaff c3";
const DWORD kClothPatch = 0x005bbec2;                          // fld dword [0xe7f188] (6 bytes)
const DWORD kClothCaller1 = 0x005d4688, kClothCaller2 = 0x005dfee1;
const DWORD kWorldScaleSite = 0x005da595;                      // world scale -> 0xe7f1a0, 0xe7f194 / 0xe7f188 *= it
const char *const kWorldScaleHex = "d91da0f1e700 d905a0f1e700 d9c0 d80d94f1e700 d91d94f1e700 d80d88f1e700 d91d88f1e700";
DWORD g_clothBack = 0x005bbec8;                                // push ecx; mov ecx,eax; fstp [esp]; call tru+0x5d680
int g_clothTimeStep = 0;                                       // [Cloth] TuTimeStep
bool g_clothOk = false;
volatile LONG g_clothHits = 0;                                 // player cloth updates divided (log only)
volatile LONG g_clothZero = 0;                                 // of them with world scale +-0.0 (the TU divides anyway)
volatile DWORD g_clothDtBits = 0, g_clothScaleBits = 0;        // last scaled dt / world scale (log only)

__declspec(naked) void ClothDtStub() {
    __asm {
        fld dword ptr ds:[0x00e7f188]           // TU 0x822781e8 lfs f1,0x100(r11)
        mov ecx, dword ptr [esp + 4]            // the instance (TU r26)
        cmp ecx, dword ptr ds:[0x00e7f094]      // TU 0x822781e4 / 0x822781ec cmplw cr6,r26,r10 (r10 = [gt+0xc])
        jne done                                // TU 0x822781f0 bne cr6,0x822781fc
        fdiv dword ptr ds:[0x00e7f1a0]          // TU 0x822781f4 lfs f0,0x118(r11) / 0x822781f8 fdivs f1,f1,f0
        inc dword ptr [g_clothHits]             // from here on: log only
        mov ecx, dword ptr ds:[0x00e7f188]
        mov dword ptr [g_clothDtBits], ecx
        mov ecx, dword ptr ds:[0x00e7f1a0]
        mov dword ptr [g_clothScaleBits], ecx
        test ecx, 7fffffffh
        jnz done
        inc dword ptr [g_clothZero]
    done:
        jmp dword ptr [g_clothBack]             // TU 0x822781fc bl 0x82102e70 = PC tru+0x5d680
    }
}

LONG g_clothReported = 0, g_clothZeroReported = 0;
bool g_clothSlowLogged = false;

// called once per game frame from MeterTick (game thread, like the cloth update)
void ReportClothTimeStep() {
    if (!g_clothOk) return;
    LONG n = g_clothHits, last = g_clothReported;
    if (n == last) return;
    g_clothReported = n;
    DWORD dtBits = g_clothDtBits, scaleBits = g_clothScaleBits;
    float dt, scale;
    memcpy(&dt, &dtBits, 4);
    memcpy(&scale, &scaleBits, 4);
    double result = scale != 0.0f ? static_cast<double>(dt) / scale : 0.0;
    if (last == 0)
        Log(1, "cloth time step: first player cloth update with the TU division (dt %.5f / world scale %.3f = %.5f, "
               "TU 0x822781f8)", dt, scale, result);
    // log threshold only (not part of the translation): the first update while the world runs slower / faster than 1 %
    if (!g_clothSlowLogged && (scale < 0.99f || scale > 1.01f)) {
        g_clothSlowLogged = true;
        Log(1, "cloth time step: world time scaled - player cloth dt %.5f / world scale %.3f = %.5f (update %ld)", dt,
            scale, result, n);
    }
    bool pow2 = false;
    for (LONG p = 1; p > 0 && p <= n; p <<= 1)
        if (p > last) { pow2 = true; break; }
    if (g_logLevel >= 2 && pow2)
        Log(2, "cloth time step: %ld player cloth updates divided (last dt %.5f / world scale %.3f)", n, dt, scale);
    LONG z = g_clothZero;
    if (z != g_clothZeroReported) {
        if (g_clothZeroReported == 0)
            Log(0, "cloth time step: world scale 0 at a player cloth update (%ld times) - the TU divides anyway", z);
        g_clothZeroReported = z;
    }
}

void PatchClothTimeStep() {
    if (!g_clothTimeStep) return;                       // default: nothing checked, nothing patched (0.14 behaviour)
    const char *bad = !HexBytesAt(kClothFunc, kClothFuncHex) ? "function entry tru+0x1bbe70"
                      : !HexBytesAt(kClothSite, kClothSiteHex) ? "site tru+0x1bbec2"
                      : !CallTargetIs(kClothCaller1, kClothFunc) || !CallTargetIs(kClothCaller2, kClothFunc)
                          ? "callers tru+0x1d4688 / tru+0x1dfee1"
                      : !HexBytesAt(kWorldScaleSite, kWorldScaleHex) ? "world scale tru+0x1da595"
                                                                     : nullptr;
    if (bad) { Log(0, "cloth time step: code does not match (%s) - off", bad); return; }
    if (!WriteJumpN(kClothPatch, reinterpret_cast<const void *>(&ClothDtStub), 6)) {
        Log(0, "cloth time step: VirtualProtect failed (%lu) - off", GetLastError());
        return;
    }
    g_clothOk = true;
    Log(1, "cloth time step: [Cloth] ClothTuTimeStep=1 - tru+0x1bbec2 runs TU 0x822781dc..0x822781f8: the player's cloth "
           "(component 14) gets dt [0xe7f188] / world scale [0xe7f1a0] when the instance is [0xe7f094]");
}

// ---- 0.24 [Camera] TuTimeStep: the TU's camera time step (N6, project doc Befund-Kletterkamera-Kraft-1111.md) ----
// Retail (= PC) starts four camera updates with dt = [gt+0x100] (frame time * world time scale) * 1/30; the TU divides
// by the world time scale [gt+0x118] first, so the cameras run on the unscaled frame time while the world is slowed
// (shadow power: world 0.3). No other test in the TU (no gameTracker+0x1244, no scale > 0). gt = TU 0x82efb458 = PC
// 0xe7f088 (+0x100 = 0xe7f188, +0x118 = 0xe7f1a0).
//   TU function (retail)                        TU instructions          PC function (vtable slot)       PC site
//   camera manager slot 0x28 0x822ad048         0x822ad06c..0x822ad084   tru+0x1f3c70 (0x855ae4 +0x28)    tru+0x1f3c79
//     (0x822affd8)
//   LaraCamera slot 4 0x822beeb8 (0x822c1678)   0x822beef8..0x822bef14   tru+0x1fe2d0 (0x855f54 +4)       tru+0x1fe30a
//   LaraCameraRewrite slot 4 0x822c39c8         0x822c3a08..0x822c3a24   tru+0x202690 (0x85600c +4)       tru+0x2026ca
//     (0x822c6720)
//   LaraCombatCamera slot 4 0x822c79d0          0x822c7a18..0x822c7a30   tru+0x204470 (0x8560c4 +4)       tru+0x2044aa
//     (0x822ca700)
// The PC keeps `fdiv qword [0x8439b8]` (30.0) after each site (the TU's fmuls by 1/30 = 0x3d088889); the stubs replace
// only `fld dword [0xe7f188]` (6 bytes) by `fld [0xe7f188]; fdiv [0xe7f1a0]` (TU lfs 0x100 / lfs 0x118 / fdivs). The
// flags are dead at all four sites (the next flag reader follows a cmp or a call). World scale 0: the TU divides
// anyway, as the PC player update tru+0x3228e9 does (dt * 1 / [0xe7f1a0], no test) - only counted for the log.
struct CamDtSite { const char *name; DWORD func; DWORD vtSlot; DWORD check; const char *hex; DWORD site; };
const CamDtSite kCamDtSites[4] = {
    {"camera manager update tru+0x1f3c70 (TU 0x822ad048)", 0x005f3c70, 0x00855ae4 + 0x28, 0x005f3c70,
     "55 8bec 83e4f0 83ec14 d90588f1e700 53 dc35b8398400 56 8bf1 807e7e00", 0x005f3c79},
    {"LaraCamera update tru+0x1fe2d0 (TU 0x822beeb8)", 0x005fe2d0, 0x00855f54 + 0x4, 0x005fe2dc,
     "8b8390010000 83f8ff 56 57 740d 50 e891fcf4ff 83c404 85c0 7514 e8855dfdff 8b8044010000 50 e879fcf4ff 83c404 "
     "d90588f1e700 0f288300010000 dc35b8398400", 0x005fe30a},
    {"LaraCameraRewrite update tru+0x202690 (TU 0x822c39c8)", 0x00602690, 0x0085600c + 0x4, 0x0060269c,
     "8b83d0010000 83f8ff 56 57 740d 50 e8d1b8f4ff 83c404 85c0 7514 e8c519fdff 8b8044010000 50 e8b9b8f4ff 83c404 "
     "d90588f1e700 0f288300010000 dc35b8398400", 0x006026ca},
    {"LaraCombatCamera update tru+0x204470 (TU 0x822c79d0)", 0x00604470, 0x008560c4 + 0x4, 0x0060447d,
     "8b8644010000 83f8ff 57 740d 50 e8f19af4ff 83c404 85c0 7514 e8e5fbfcff 8b8048010000 50 e8d99af4ff 83c404 "
     "d90588f1e700 8d7810 dc35b8398400", 0x006044aa},
};
int g_camTimeStep = 0;                                         // [Camera] TuTimeStep
bool g_camDtOk = false;
volatile LONG g_camDtHits[4] = {0, 0, 0, 0};                   // divided updates per site (log only)
DWORD g_camDtBack[4] = {0x005f3c7f, 0x005fe310, 0x006026d0, 0x006044b0};

__declspec(naked) void CamDtStub0() {           // camera manager: TU 0x822ad06c / 0x822ad070 / 0x822ad078
    __asm {
        fld dword ptr ds:[0x00e7f188]
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_camDtHits]
        jmp dword ptr [g_camDtBack]
    }
}
__declspec(naked) void CamDtStub1() {           // LaraCamera: TU 0x822beef8 / 0x822bef00 / 0x822bef08
    __asm {
        fld dword ptr ds:[0x00e7f188]
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_camDtHits + 4]
        jmp dword ptr [g_camDtBack + 4]
    }
}
__declspec(naked) void CamDtStub2() {           // LaraCameraRewrite: TU 0x822c3a08 / 0x822c3a10 / 0x822c3a18
    __asm {
        fld dword ptr ds:[0x00e7f188]
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_camDtHits + 8]
        jmp dword ptr [g_camDtBack + 8]
    }
}
__declspec(naked) void CamDtStub3() {           // LaraCombatCamera: TU 0x822c7a18 / 0x822c7a20 / 0x822c7a28
    __asm {
        fld dword ptr ds:[0x00e7f188]
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_camDtHits + 12]
        jmp dword ptr [g_camDtBack + 12]
    }
}
void (*const kCamDtStubs[4])() = {CamDtStub0, CamDtStub1, CamDtStub2, CamDtStub3};

LONG g_camDtReported[4] = {0, 0, 0, 0};
bool g_camDtSlowLogged[4] = {false, false, false, false};
LONG g_camDtZero = 0;

// called once per game frame from MeterTick (game thread, like the camera updates); log only
void ReportCameraTimeStep() {
    if (!g_camDtOk) return;
    const float scale = *reinterpret_cast<volatile const float *>(0x00e7f1a0);
    const float dt = *reinterpret_cast<volatile const float *>(0x00e7f188);
    const double result = scale != 0.0f ? static_cast<double>(dt) / scale : 0.0;
    for (int i = 0; i < 4; ++i) {
        LONG n = g_camDtHits[i], last = g_camDtReported[i];
        if (n == last) continue;
        g_camDtReported[i] = n;
        if (last == 0)
            Log(1, "camera time step: first %s with the TU division (dt %.5f / world scale %.3f = %.5f)",
                kCamDtSites[i].name, dt, scale, result);
        // log threshold only (not part of the translation): the first update while the world runs slower / faster
        if (!g_camDtSlowLogged[i] && (scale < 0.99f || scale > 1.01f)) {
            g_camDtSlowLogged[i] = true;
            Log(1, "camera time step: world time scaled - %s runs on dt %.5f / world scale %.3f = %.5f (update %ld)",
                kCamDtSites[i].name, dt, scale, result, n);
        }
        bool pow2 = false;
        for (LONG p = 1; p > 0 && p <= n; p <<= 1)
            if (p > last) { pow2 = true; break; }
        if (g_logLevel >= 2 && pow2)
            Log(2, "camera time step: %ld updates of %s divided (world scale %.3f)", n, kCamDtSites[i].name, scale);
    }
    if (scale == 0.0f && g_camDtZero++ == 0)
        Log(0, "camera time step: world scale 0 while the cameras update - the TU divides anyway");
}

void PatchCameraTimeStep() {
    if (!g_camTimeStep) {                                      // default: nothing checked, nothing patched (= 0.23)
        Log(1, "camera time step: [Camera] CameraTuTimeStep=0 - the cameras run on the world-scaled frame time (retail)");
        return;
    }
    for (int i = 0; i < 4; ++i) {
        const CamDtSite &s = kCamDtSites[i];
        bool slotOk = false;
        __try { slotOk = *reinterpret_cast<const DWORD *>(s.vtSlot) == s.func; }
        __except (EXCEPTION_EXECUTE_HANDLER) { slotOk = false; }
        if (!slotOk || !HexBytesAt(s.check, s.hex)) {
            Log(0, "camera time step: code does not match (%s, %s) - off", s.name, slotOk ? "bytes" : "vtable slot");
            return;
        }
    }
    if (!HexBytesAt(kWorldScaleSite, kWorldScaleHex)) {
        Log(0, "camera time step: code does not match (world scale tru+0x1da595) - off");
        return;
    }
    for (int i = 0; i < 4; ++i) {
        if (!WriteJumpN(kCamDtSites[i].site, reinterpret_cast<const void *>(kCamDtStubs[i]), 6)) {
            Log(0, "camera time step: VirtualProtect failed at 0x%08lx (%lu) - %d of 4 sites patched",
                kCamDtSites[i].site, GetLastError(), i);
            g_camDtOk = i > 0;
            return;
        }
    }
    g_camDtOk = true;
    Log(1, "camera time step: [Camera] CameraTuTimeStep=1 - tru+0x1f3c79 / 0x1fe30a / 0x2026ca / 0x2044aa run TU "
           "0x822ad06c / 0x822beef8 / 0x822c3a08 / 0x822c7a18: camera manager, LaraCamera, LaraCameraRewrite and "
           "LaraCombatCamera get dt [0xe7f188] / world scale [0xe7f1a0] (unscaled while the world is slowed)");
}

// ---- 0.27 [Camera] ShakeTuTimeStep / [Player] TuTimeStep: the TU's other world-time divisions (Q50, project doc
// Befund-Zeitschritt-Q50-1111.md; found by Q17, Befund-TU-Prioritaeten-Q17-1111.md ranks 7 / 11) ----
// The TU divides gameTracker+0x100 (frame time x world scale, PC 0xe7f188) by +0x118 (world scale, PC 0xe7f1a0) at six
// more places than retail (= the PC). None of them tests the doppelganger flag or the scale (as 0.24); world scale 0:
// the TU divides anyway (counted for the log only).
//   [Camera] ShakeTuTimeStep - the camera shake pool: TU 0x822af4d8 (retail 0x822b2408) = PC tru+0x1f3390 (Q17's
//     coverage partner 0x5ed860 is wrong). Both are called first by the camera update (TU 0x822aa520 bl 0x822af4d8,
//     then the manager 0x822ad048 on 0x82efc780; PC tru+0x1f3df0 call tru+0x1f3390, then tru+0x1f3c70 on 0xe804f0 =
//     pool + 0x4d0 on both). dt = 0.0 when gt+0xbb == 6, else gt+0x100 / gt+0x118 * 1/30 (TU 0x822af510..0x822af524;
//     retail / PC: gt+0x100 * 1/30), then the 8 slots of 0x90 bytes (TU 0x82efc2b0, PC 0xe80020) update with it (TU
//     0x822af2c0 / PC tru+0x1f3190). PC site tru+0x1f339e `fld [0xe7f188]`; its `fdiv qword [30.0]` stays.
//   [Player] TuTimeStep - Lara's object functions (TU table 0x8275ae3c = PC 0x8aba2c: init, process, collide, query,
//     message, additional collide):
//     P1 query case 0xe0 (TU 0x8240cf88 -> 0x8240db78; PC tru+0x309fd0 case 224 -> tru+0x30a6d5): retail / PC return
//        int(length(+0x90 row 3 - +0x94 row 3) / gt+0x100); the TU int(length * ((1.0 / gt+0x118) / gt+0x100))
//        (0x8240dbbc..0x8240dbd0, 0x8240dc00; 1.0 = TU 0x8207d544). PC site tru+0x30a70a `fdiv [0xe7f188]`, st0 = length.
//     P2 message 0x190 (TU 0x8240e3a0 -> 0x8240fa6c; PC tru+0x31ffe0 case 400 -> tru+0x320eb8): the player instance
//        position += vector * 1/30 * min(dt, 2.0) with dt = gt+0x100 (retail / PC) / gt+0x100 / gt+0x118 (TU
//        0x8240faa4..0x8240fad0). PC site tru+0x320ed7 `fld [0xe7f188]` (argument of the min helper tru+0x35170).
//     P3 ComputeSmoothRide (TU 0x82411850, retail 0x8240ea00, PC tru+0x300940, only called by P4): the smoothing block
//        uses gt+0x100 / gt+0x118 wherever retail uses gt+0x100 (TU 0x82411b50..0x82411bf4: retail f0 -> TU f6). PC site
//        tru+0x300bda, the function's only `fld [0xe7f188]` (stored to [esp+0x18], every use reads it from there).
//     P4 RazielAdditionalCollide (TU 0x82411c30, retail 0x8240edd8, PC tru+0x31bfa0): when instance+0x298 == 0 the TU
//        stores gt+0x100 / gt+0x118 into gt+0x100 for the whole body (0x82411c78..0x82411c8c, f30 = the old value) and
//        writes the old value back after the last call (0x82411f98): every callee (P3, gravity / collision steps) sees
//        the unscaled frame time. PC: the entry jumps to a wrapper that does the same around the game's body
//        (trampoline = the 6 moved prologue bytes). P3 divides again inside this window, as in the TU.
//     P5 PLAYER_GetAttachedToVelocity (TU 0x82419c98, retail 0x82416ac8, PC tru+0x3027b0; 10 callers each, e.g. TU
//        camera manager 0x822ad048 / PC tru+0x1e7ef0): the platform branch (instance+0x274 == 0) passes min(dt, 2.0)
//        with dt = gt+0x100 / gt+0x118 in the TU (0x82419ff4..0x8241a020). PC site tru+0x302a43 `fld [0xe7f188]`.
// Patched only when the switch is 1 at the start (default 0: nothing checked, nothing patched). Then read again at run
// time at most once per second (TimeStepReadSwitch, game thread): 0 sends every stub along the PC path (the jumps stay).
// The stubs keep the flags (pushfd / popfd) and the registers; the wrapper runs at a function entry (cdecl, eax free).
int g_shakeTimeStep = 0;                                       // [Camera] ShakeTuTimeStep at the start
int g_playerTimeStep = 0;                                      // [Player] TuTimeStep at the start
volatile LONG g_shakeOn = 0, g_playerOn = 0;                   // live values read by the stubs
bool g_shakePatched = false, g_playerPatched = false;
DWORD g_tsSwitchTick = 0;
const int kTsSites = 6;                                        // 0 shake, 1..5 = P1..P5
const char *const kTsNames[kTsSites] = {
    "camera shake pool tru+0x1f3390 (TU 0x822af4d8)", "player query 0xe0 tru+0x30a6d5 (TU 0x8240db78)",
    "player message 0x190 tru+0x320eb8 (TU 0x8240fa6c)", "ComputeSmoothRide tru+0x300940 (TU 0x82411850)",
    "RazielAdditionalCollide tru+0x31bfa0 (TU 0x82411c30)", "PLAYER_GetAttachedToVelocity tru+0x3027b0 (TU 0x82419c98)"};
const DWORD kTsSite[kTsSites] = {0x005f339e, 0x0070a70a, 0x00720ed7, 0x00700bda, 0x0071bfa0, 0x00702a43};
DWORD g_tsBack[kTsSites] = {0x005f33a4, 0x0070a710, 0x00720edd, 0x00700be0, 0, 0x00702a49};
volatile LONG g_tsHits[kTsSites] = {0, 0, 0, 0, 0, 0};          // divided calls per site (log only)
LONG g_tsReported[kTsSites] = {0, 0, 0, 0, 0, 0};
bool g_tsSlowLogged[kTsSites] = {false, false, false, false, false, false};
LONG g_tsZero = 0;
DWORD g_addCollideBody = 0;                                    // trampoline: moved prologue + jmp tru+0x31bfa6

__declspec(naked) void TsShakeStub() {          // tru+0x1f339e, TU 0x822af510 / 0x822af518 / 0x822af51c
    __asm {
        fld dword ptr ds:[0x00e7f188]
        pushfd
        cmp dword ptr [g_shakeOn], 0
        je plain
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_tsHits]
    plain:
        popfd
        jmp dword ptr [g_tsBack]
    }
}
__declspec(naked) void TsQueryStub() {          // tru+0x30a70a, st0 = the length (TU f11)
    __asm {
        pushfd
        cmp dword ptr [g_playerOn], 0
        je plain
        fld1                                    // TU 0x8240dbbc lfs f0 = [0x8207d544] = 1.0
        fdiv dword ptr ds:[0x00e7f1a0]          // TU 0x8240dbc0 / 0x8240dbc4 f13 = 1.0 / gt+0x118
        fdiv dword ptr ds:[0x00e7f188]          // TU 0x8240dbc8 / 0x8240dbd0 f12 = f13 / gt+0x100
        fmulp st(1), st                         // TU 0x8240dc00 f10 = f12 * length
        inc dword ptr [g_tsHits + 4]
        popfd
        jmp dword ptr [g_tsBack + 4]            // PC: ftol tru+0x414d20 = TU fctiwz
    plain:
        fdiv dword ptr ds:[0x00e7f188]          // PC / retail 0x8240adc4: length / gt+0x100
        popfd
        jmp dword ptr [g_tsBack + 4]
    }
}
__declspec(naked) void TsMessageStub() {        // tru+0x320ed7, TU 0x8240faa4 / 0x8240faac / 0x8240fab4
    __asm {
        fld dword ptr ds:[0x00e7f188]
        pushfd
        cmp dword ptr [g_playerOn], 0
        je plain
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_tsHits + 8]
    plain:
        popfd
        jmp dword ptr [g_tsBack + 8]
    }
}
__declspec(naked) void TsSmoothRideStub() {     // tru+0x300bda, TU 0x82411b50 / 0x82411b5c / 0x82411b64
    __asm {
        fld dword ptr ds:[0x00e7f188]
        pushfd
        cmp dword ptr [g_playerOn], 0
        je plain
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_tsHits + 12]
    plain:
        popfd
        jmp dword ptr [g_tsBack + 12]
    }
}
__declspec(naked) void TsAddCollideStub() {     // tru+0x31bfa0 entry, cdecl(instance)
    __asm {
        cmp dword ptr [g_playerOn], 0
        je plain
        mov eax, dword ptr [esp + 4]            // the instance (TU r31 = r3)
        cmp dword ptr [eax + 0x298], 0          // TU 0x82411c50 / 0x82411c54 / 0x82411c58 bne -> no division
        jne plain
        push dword ptr ds:[0x00e7f188]          // TU 0x82411c80 fmr f30,f0 (the old gt+0x100)
        fld dword ptr ds:[0x00e7f188]           // TU 0x82411c78 lfs f0,0x100
        fdiv dword ptr ds:[0x00e7f1a0]          // TU 0x82411c7c lfs f13,0x118 / 0x82411c84 fdiv / 0x82411c88 frsp
        fstp dword ptr ds:[0x00e7f188]          // TU 0x82411c8c stfs f0,0x100
        push dword ptr [esp + 8]                // the instance again
        call dword ptr [g_addCollideBody]       // the game's body (= TU 0x82411c90..0x82411f94)
        add esp, 4
        pop dword ptr ds:[0x00e7f188]           // TU 0x82411f98 stfs f30,0x100
        inc dword ptr [g_tsHits + 16]
        ret
    plain:
        jmp dword ptr [g_addCollideBody]
    }
}
__declspec(naked) void TsVelocityStub() {       // tru+0x302a43, TU 0x82419ff4 / 0x82419ffc / 0x8241a004
    __asm {
        fld dword ptr ds:[0x00e7f188]
        pushfd
        cmp dword ptr [g_playerOn], 0
        je plain
        fdiv dword ptr ds:[0x00e7f1a0]
        inc dword ptr [g_tsHits + 20]
    plain:
        popfd
        jmp dword ptr [g_tsBack + 20]
    }
}

// called once per game frame from MeterTick (game thread); log only: one line per site at its first divided call,
// one at its first call while the world runs slower / faster than 1 % (log threshold only, not part of the translation)
void ReportTimeStep027() {
    if (!g_shakePatched && !g_playerPatched) return;
    const float scale = *reinterpret_cast<volatile const float *>(0x00e7f1a0);
    const float dt = *reinterpret_cast<volatile const float *>(0x00e7f188);
    const double result = scale != 0.0f ? static_cast<double>(dt) / scale : 0.0;
    for (int i = 0; i < kTsSites; ++i) {
        LONG n = g_tsHits[i], last = g_tsReported[i];
        if (n == last) continue;
        g_tsReported[i] = n;
        if (last == 0)
            Log(1, "0.27 time step: first %s with the TU division (dt %.5f / world scale %.3f = %.5f)", kTsNames[i],
                dt, scale, result);
        if (!g_tsSlowLogged[i] && (scale < 0.99f || scale > 1.01f)) {
            g_tsSlowLogged[i] = true;
            Log(1, "0.27 time step: world time scaled - %s divided: dt %.5f / world scale %.3f = %.5f (call %ld)",
                kTsNames[i], dt, scale, result, n);
        }
        bool pow2 = false;
        for (LONG p = 1; p > 0 && p <= n; p <<= 1)
            if (p > last) { pow2 = true; break; }
        if (g_logLevel >= 2 && pow2)
            Log(2, "0.27 time step: %ld calls of %s divided (world scale %.3f)", n, kTsNames[i], scale);
    }
    if (scale == 0.0f && g_tsZero++ == 0)
        Log(0, "0.27 time step: world scale 0 while a divided site runs - the TU divides anyway");
}

void TimeStepReadSwitch() {
    if ((!g_shakePatched && !g_playerPatched) || !g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_tsSwitchTick < 1000) return;
    g_tsSwitchTick = now;
    if (g_shakePatched) {
        const LONG v = GetPrivateProfileIntA("Camera", "ShakeTuTimeStep", g_shakeOn, g_iniPath) ? 1 : 0;
        if (v != g_shakeOn) {
            Log(1, "0.27 switch: [Camera] ShakeTuTimeStep %ld -> %ld (read again from TruShadowPower.ini) - %s",
                g_shakeOn, v, v ? "the camera shake pool runs on dt / world scale (TU 0x822af4d8)"
                                : "the camera shake pool runs on the world-scaled dt (PC)");
            g_shakeOn = v;
        }
    }
    if (g_playerPatched) {
        const LONG v = GetPrivateProfileIntA("Player", "TuTimeStep", g_playerOn, g_iniPath) ? 1 : 0;
        if (v != g_playerOn) {
            Log(1, "0.27 switch: [Player] TuTimeStep %ld -> %ld (read again from TruShadowPower.ini) - %s",
                g_playerOn, v, v ? "the five player sites divide by the world scale (TU)"
                                 : "the five player sites use the world-scaled dt (PC)");
            g_playerOn = v;
        }
    }
}

struct TsCheck { DWORD at; const char *hex; const char *what; };
const TsCheck kShakeChecks[] = {
    {0x005f3390, "51 803d43f1e70006 7504 d9ee eb0c d90588f1e700 dc35b8398400 56 d95c2404 57 be2800e800",
     "shake update tru+0x1f3390 (gt+0xbb test, dt, pool 0xe80028)"},
    {0x005f33e2, "81c690000000 81fea804e800 7cc5", "shake pool loop (slots of 0x90 up to 0xe804a8)"},
    {0x005f3e07, "e884f5ffff b9f004e800 e85afeffff", "camera update tru+0x1f3e07: shake pool, then the manager 0xe804f0"},
};
const TsCheck kPlayerChecks[] = {
    {0x00709fdf, "3d36010000 53 56 8b7508 57 0f8785080000 0f8458080000 3df8000000 0f87b50b0000 0fb6887cac7000 "
                 "ff248dc8ab7000", "player query tru+0x309fd0 dispatch"},
    {0x0070ad5c, "2a", "query byte table: case 224 -> index 42"},
    {0x0070ac70, "d5a67000", "query jump table: index 42 -> tru+0x30a6d5"},
    {0x0070a6d5, "8b8690000000 85c0 0f84aefbffff 8bb694000000 85f6 0f84a0fbffff 0f284030 0f284e30 0f5cc1 8d4c2420 "
                 "0f29442420 e8867ad2ff d83588f1e700 e80ba61000", "query case 224 (length of +0x90 - +0x94 / dt)"},
    {0x00720e99, "8d87fafeffff 3de9000000 0f8745010000 0fb680e0117200 ff2485bc117200",
     "player message tru+0x31ffe0 dispatch (base 0x106)"},
    {0x0072126a, "03", "message byte table: 0x190 -> index 3"},
    {0x007211c8, "b80e7200", "message jump table: index 3 -> tru+0x320eb8"},
    {0x00720eb8, "d94308 83ec0c d95c2408 8d4c243c d94304 d95c2404 d903 d91c24 e84910d1ff d90588f1e700 0f284c2430 "
                 "f30f1005105f8500 83ec08 d95c2404 0fc6c000 d9059c288400 0f59c1 d91c24 0f29442438 e86542d1ff",
     "message 0x190 (position += vector * 1/30 * min(dt, 2.0))"},
    {0x00435170, "d9442408 d9442404 d8d1 dfe0 f6c441 750b ddd8 d95c2408 d9442408 c3", "min helper tru+0x35170"},
    {0x00700940, "558bec 83e4f0 8b0d58dbfa00 d9ee 83ec54", "ComputeSmoothRide tru+0x300940 entry"},
    {0x00700bbc, "807f3000 7518 8b450c d94008 d95f20 d94008 c6473001 d95f24 d9ee d95f28 d90588f1e700 a164d7fa00 "
                 "d95c2418 d9c0 d86720 d9442418 d9c0 defa d9c9 d95c241c d98018050000 dc0d20118400 dc35b8398400",
     "ComputeSmoothRide smoothing block (dt -> [esp+0x18])"},
    {0x0071bfa0, "558bec 83e4f0 83ec68 56 8b7508 83be9802000000 57 0f850b030000",
     "RazielAdditionalCollide tru+0x31bfa0 entry (instance+0x298 test)"},
    {0x0071c076, "e8c548feff", "RazielAdditionalCollide calls ComputeSmoothRide tru+0x300940"},
    {0x0071c2b6, "6a00 68a6000000 56 e88d74e9ff 83c40c 5f 5e 8be5 5d c3", "RazielAdditionalCollide end (message 0xa6)"},
    {0x007027b0, "558bec 83e4f0 83ec34 8b4508 53 8b5d0c 56", "PLAYER_GetAttachedToVelocity tru+0x3027b0 entry"},
    {0x00702a03, "8b8e74020000 85c9 7430", "GetAttachedToVelocity: instance+0x274 test"},
    {0x00702a3d, "d9059c288400 d90588f1e700 d8d1 dfe0 f6c405 7a04 ddd9 eb02 ddd8 a194f0e700 d95c242c",
     "GetAttachedToVelocity platform branch (min(dt, 2.0))"},
    {0x005e7f48, "e863a81100", "camera caller tru+0x1e7f48 -> tru+0x3027b0"},
};

void PatchTimeStep027() {
    if (!g_shakeTimeStep && !g_playerTimeStep) {       // default: nothing checked, nothing patched (= 0.26)
        Log(1, "0.27 time step: [Camera] ShakeTuTimeStep=0, [Player] TuTimeStep=0 - camera shake and the five player "
               "sites run on the world-scaled frame time (retail; a later 1 needs a restart)");
        return;
    }
    if (!HexBytesAt(kWorldScaleSite, kWorldScaleHex)) {
        Log(0, "0.27 time step: code does not match (world scale tru+0x1da595) - off");
        return;
    }
    if (g_shakeTimeStep) {
        const char *bad = nullptr;
        for (const auto &c : kShakeChecks)
            if (!HexBytesAt(c.at, c.hex)) {
                bad = c.what;
                Log(0, "0.27 time step: code at 0x%08lx does not match (%s)", c.at, c.what);
            }
        if (bad) {
            Log(0, "0.27 time step: [Camera] ShakeTuTimeStep=1 - checks failed - off");
        } else if (!WriteJumpN(kTsSite[0], reinterpret_cast<const void *>(&TsShakeStub), 6)) {
            Log(0, "0.27 time step: VirtualProtect failed at 0x%08lx (%lu) - shake off", kTsSite[0], GetLastError());
        } else {
            g_shakePatched = true;
            g_shakeOn = 1;
            Log(1, "0.27 time step: [Camera] ShakeTuTimeStep=1 - %u code checks passed; tru+0x1f339e runs TU "
                   "0x822af510..0x822af51c: the camera shake pool gets dt [0xe7f188] / world scale [0xe7f1a0] (read again "
                   "at run time at most once per second)",
                static_cast<unsigned>(sizeof(kShakeChecks) / sizeof(kShakeChecks[0])));
        }
    } else {
        Log(1, "0.27 time step: [Camera] ShakeTuTimeStep=0 - camera shake on the world-scaled frame time (retail)");
    }
    if (!g_playerTimeStep) {
        Log(1, "0.27 time step: [Player] TuTimeStep=0 - the five player sites on the world-scaled frame time (retail)");
        return;
    }
    const char *bad = nullptr;
    for (const auto &c : kPlayerChecks)
        if (!HexBytesAt(c.at, c.hex)) {
            bad = c.what;
            Log(0, "0.27 time step: code at 0x%08lx does not match (%s)", c.at, c.what);
        }
    if (bad) { Log(0, "0.27 time step: [Player] TuTimeStep=1 - checks failed - off (no site patched)"); return; }
    BYTE *t = static_cast<BYTE *>(VirtualAlloc(nullptr, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!t) { Log(0, "0.27 time step: VirtualAlloc failed (%lu) - player sites off", GetLastError()); return; }
    memcpy(t, reinterpret_cast<const void *>(kTsSite[4]), 6);     // push ebp; mov ebp,esp; and esp,-16 (no rel operand)
    t[6] = 0xe9;
    const DWORD back = (kTsSite[4] + 6) - (reinterpret_cast<DWORD>(t) + 11);
    memcpy(t + 7, &back, 4);
    FlushInstructionCache(GetCurrentProcess(), t, 16);
    g_addCollideBody = reinterpret_cast<DWORD>(t);
    g_playerOn = 1;                                              // before the jumps: the stubs read it
    void (*const stubs[5])() = {TsQueryStub, TsMessageStub, TsSmoothRideStub, TsAddCollideStub, TsVelocityStub};
    int done = 0;
    for (int i = 1; i < kTsSites; ++i) {
        if (!WriteJumpN(kTsSite[i], reinterpret_cast<const void *>(stubs[i - 1]), 6)) {
            Log(0, "0.27 time step: VirtualProtect failed at 0x%08lx (%lu) - %d of 5 player sites patched", kTsSite[i],
                GetLastError(), done);
            break;
        }
        ++done;
    }
    g_playerPatched = done > 0;
    if (done == 5)
        Log(1, "0.27 time step: [Player] TuTimeStep=1 - %u code checks passed; tru+0x30a70a (query 0xe0, TU 0x8240dbc4), "
               "tru+0x320ed7 (message 0x190, TU 0x8240fab4), tru+0x300bda (ComputeSmoothRide, TU 0x82411b64), "
               "tru+0x31bfa0 (RazielAdditionalCollide: gt+0x100 = dt / world scale for its body, TU 0x82411c84 / "
               "0x82411f98), tru+0x302a43 (GetAttachedToVelocity, TU 0x8241a004) divide by world scale [0xe7f1a0] (read "
               "again at run time at most once per second)",
            static_cast<unsigned>(sizeof(kPlayerChecks) / sizeof(kPlayerChecks[0])));
}

// ---- 0.25 [Camera] Trace: the PC side of the camera comparison with TruXenia (project doc
// Plan-Kamera-Vergleich-Xenia-PC-1111.md; Xbox side: tools/truxenia.py --camtrace, address file section "camera") ----
// Read only, game thread (from MeterTick, i.e. only while Lara exists and updates), one TSV row every
// [Camera] TraceInterval ms (default 50) into TruCam.log next to this plugin (opened shared, a header at every open).
// The columns are TruXenia's CAM_COLS (tools/truxenia.py), side "pc". Sources (each pinned in kCamTraceChecks):
//   manager 0xe804f0: requested mode +0x58 (= TU +0x54; chooser 0x5e80b9), current camera +0x44 (focus getter
//     0x5e7920 = TU 0x822aabd0), gameplay camera +0xb80 (manager update 0x5f3cbb, = TU +0xb50), LaraCameraRewrite
//     vtable 0x85600c;
//   of the current camera, only when its vtable slot holds the base getter: rotation +0xa0 (slot 0x34 0x5e1c60; x =
//     pitch, z = yaw in radians - the getter 0x5e78a0 ENGINE.md / fight.trace call "position" returns this rotation),
//     transform +0x10 (slot 0x38 0x5e1c70; world position = row 3 at +0x40), FOV +0xb0 (slot 0x40 0x5e1c90);
//   Lara: instance [0xe7f094] +0x20 position, +0x38 yaw (read as at 0x752c73);
//   recenter (gameplay camera): clock +0x1e4 (look step 0x5ffe80), settings = lookup 0x54df80([cam+0x1d0]) or of
//     [[0xe7ee50]+0x144] (0x6026b6, GlobalInfo 0x5d4080), S = lookup + 0x10 (0x6026ea), delay S+0xb4, ramp S+0xb8,
//     weight = clamp((clock - delay) / ramp, 0, 1) as 0x5ffa90 (TU 0x822bc198 / 0x822c20b8 the same, but in
//     doppelganger mode the TU falls back to GlobalInfo +0x14c = DTP 21237);
//   world scale [0xe7f1a0], scaled frame time [0xe7f188], power = meter flag 1, Lara's record index of machine 0
//     ([[0xfadb58]+0xf10] +0x510 in [[machine+4]+0xc], as TruMenu combo.trace), pad 0 right stick / buttons as this
//     plugin's pad hook gets them (raw, before TruMenu's masking), cam_step = tu when 0.24's four stubs are in.
// delta_yaw = camera yaw - Lara yaw (-180..180); cam_dir = bearing camera -> Lara in the camera's convention
// (forward = (-sin z, cos z)). Nothing is written into the game.
const DWORD kCtMgr = 0x00e804f0;
const DWORD kCtRewriteVt = 0x0085600c;
const DWORD kCtGetRot = 0x005e1c60, kCtGetXf = 0x005e1c70, kCtGetFov = 0x005e1c90;
const DWORD kCtSetTable = 0x00c36f28, kCtGlobalInfo = 0x00e7ee50;
const CodeCheck kCamTraceChecks[] = {
    {0x005e80b9, "c7465834000000"},                                         // requested mode manager+0x58
    {0x005e7920, "8b0d3405e800 8b01 8b5048 ffd2 85c0 7505 a194f0e700 c3"},  // current camera [mgr+0x44] (TU 0x822aabd0)
    {0x005f3cbb, "8b5e44 8bbe800b0000"},                                    // manager +0x44 / gameplay +0xb80
    {0x005e1c60, "8d81a0000000 c3"},                                        // slot 0x34: rotation +0xa0
    {0x005e1c70, "8d4110 c3"},                                              // slot 0x38: transform +0x10
    {0x005e1c90, "d981b0000000 c3"},                                        // slot 0x40: FOV +0xb0
    {0x005ffe80, "d996e4010000"},                                           // look step: clock +0x1e4
    {0x005ffa9d, "d981e4010000 d8a0b4000000 d8b0b8000000"},                 // weight: clock, S+0xb4, S+0xb8
    // 0.26: the settings lookup 0x54df80 is checked in CamTraceOpen with CamSettingsState (original bytes OR
    // TruDataGuard's 5-byte jump + original tail, as state 2102 since 0.13) - 0.25 listed the original bytes here and
    // refused the trace whenever TruDataGuard.asi was installed (live 2026-11-10 22:23:31). The fallback block
    // 0x6026b6 (GlobalInfo +0x144): checked in CamTraceOpen as well (original or 0.25's patch).
    {0x006026ea, "8d7010"},                                               // S = lookup + 0x10
    {0x005d4080, "a150eee700 c3"},                                          // GlobalInfo [0xe7ee50]
    {0x00752c73, "8b0d94f0e700 d94138"},                                    // Lara yaw [[0xe7f094]+0x38]
    {0x00768c50, "a158dbfa00 56 8bb0100f0000 57 8bb8140f0000 8bce e8f6f10100"},  // chart machines +0xf10 / +0xf14
};
int g_camTrace = 0;                                            // [Camera] Trace (read again at run time)
int g_camTraceMs = 50;                                         // [Camera] TraceInterval
int g_camTraceOk = -1;                                         // -1 not checked, 0 code differs, 1 ok
FILE *g_camTraceFile = nullptr;
char g_camTracePath[MAX_PATH];
DWORD g_camTraceTick = 0, g_camTraceSwitchTick = 0;
LONG g_camTraceRows = 0;
LARGE_INTEGER g_camTraceT0, g_camTraceFreq;
int g_camTraceIni = 0;                                         // the last [Camera] Trace value read from the ini
DWORD g_ctLastRec = 0;
int g_ctLastIdx = -1;

bool CtD(DWORD a, DWORD *v) {
    __try { *v = *reinterpret_cast<const volatile DWORD *>(a); return true; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
bool CtF(DWORD a, float *v) {
    DWORD d = 0;
    if (!a || !CtD(a, &d)) return false;
    memcpy(v, &d, 4);
    return _finite(*v) != 0;
}
bool CtB(DWORD a, BYTE *v) {
    __try { *v = *reinterpret_cast<const volatile BYTE *>(a); return true; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
double CtWrap(double a) {
    double r = fmod(a + 180.0, 360.0);
    if (r < 0.0) r += 360.0;
    return r - 180.0;
}
// settings entry as 0x54df80: [0xc36f28 + 4 * id], used when set and its byte +4 is 0
DWORD CtEntry(LONG id) {
    DWORD e = 0;
    BYTE busy = 1;
    if (id < 0 || id > 0xffff || !CtD(kCtSetTable + 4 * static_cast<DWORD>(id), &e) || !e) return 0;
    return CtB(e + 4, &busy) && busy == 0 ? e : 0;
}
int DgDecision(DWORD disp);                                    // 0.25 DoppelgangerSettings, defined below
bool DgBlockOk(DWORD at, DWORD disp);
bool g_dgPatched = false;                                      // 0.25: the 34 fallback blocks are patched
bool g_dgModesOn = false;                                      // 0.26: the stand-in carries 21237's mode tables
int g_dgSettings = 0;                                          // [Camera] DoppelgangerSettings (0 / 1 / 2)
const LONG kTuDgId144 = 21237, kTuDgId148 = 21238;             // TU GlobalInfo +0x14c / +0x150 (doppelganger)
const DWORD kDgSynthSize = 0x1008;                             // PC generalbank DTP 20: 4104 bytes
__declspec(align(16)) BYTE g_dgSynth[kDgSynthSize + 8];        // 0.25 stand-in for DTP 21237 (mode 2)
// the settings a camera with own id `id` gets (as 0x602690 & co. with 0.25's patched fallback blocks): returns the
// lookup result (data; S = data + 0x10) or 0, and names the choice in `t`
DWORD CtPick(LONG id, DWORD disp, char *t, size_t n) {
    DWORD e = 0, gi = 0, fid = 0;
    if (id != -1 && (e = CtEntry(id)) != 0) {
        _snprintf_s(t, n, _TRUNCATE, "id %ld", id);
        return e + 0x10;
    }
    const int d = DgDecision(disp);
    const LONG tu = disp == 0x144 ? kTuDgId144 : kTuDgId148;
    if (d == 1 && (e = CtEntry(tu)) != 0) {
        _snprintf_s(t, n, _TRUNCATE, "TU id %ld (doppelganger)", tu);
        return e + 0x10;
    }
    if (!CtD(kCtGlobalInfo, &gi) || !gi || !CtD(gi + disp, &fid)) {
        _snprintf_s(t, n, _TRUNCATE, "GI+0x%lx unreadable", disp);
        return 0;
    }
    if (d == 2) {
        _snprintf_s(t, n, _TRUNCATE, "stand-in %ld = GI+0x%lx id %ld + TU delay/ramp%s", tu, disp,
                    static_cast<LONG>(fid), g_dgModesOn ? " + modes" : "");
        return reinterpret_cast<DWORD>(g_dgSynth);
    }
    e = CtEntry(static_cast<LONG>(fid));
    _snprintf_s(t, n, _TRUNCATE, e ? "GI+0x%lx id %ld" : "GI+0x%lx id %ld (no entry)", disp, static_cast<LONG>(fid));
    return e ? e + 0x10 : 0;
}
int CtRecordIndex() {
    DWORD tracker = 0, machine = 0, rec = 0, defs = 0, arr = 0;
    if (!CtD(kPlayerStatePtr, &tracker) || !tracker || !CtD(tracker + 0xf10, &machine) || !machine ||
        !CtD(machine + 0x510, &rec) || !rec)
        return -1;
    if (rec == g_ctLastRec) return g_ctLastIdx;
    g_ctLastRec = rec;
    g_ctLastIdx = -2;                                          // record set, index not found
    if (!CtD(machine + 4, &defs) || !defs || !CtD(defs + 0xc, &arr) || !arr) return g_ctLastIdx;
    for (int i = 0; i < 8192; ++i) {
        DWORD v = 0;
        if (!CtD(arr + 4 * i, &v)) break;
        if (v == rec) { g_ctLastIdx = i; break; }
    }
    return g_ctLastIdx;
}

void CamTraceClose(const char *why) {
    if (!g_camTraceFile) return;
    fclose(g_camTraceFile);
    g_camTraceFile = nullptr;
    Log(1, "0.25 camera trace: off (%s) - %ld rows in %s", why, g_camTraceRows, g_camTracePath);
}

bool CamTraceOpen() {
    if (g_camTraceOk < 0) {
        g_camTraceOk = 1;
        if (!DgBlockOk(0x006026b6, 0x144) && !g_dgPatched) {
            Log(0, "0.25 camera trace: the settings fallback block 0x6026b6 does not match - no trace");
            g_camTraceOk = 0;
        }
        // 0.26: every check is run and every mismatch named (0.25 stopped at the first one)
        for (const auto &c : kCamTraceChecks) {
            if (!HexBytesAt(c.address, c.bytes)) {
                Log(0, "0.26 camera trace: code at 0x%08lx does not match - no trace", c.address);
                g_camTraceOk = 0;
            }
        }
        DWORD target = 0;
        const int lookup = CamSettingsState(&target);
        if (lookup == 0) {
            Log(0, "0.26 camera trace: settings lookup 0x0054df80 is neither the original nor TruDataGuard's jump - no "
                   "trace");
            g_camTraceOk = 0;
        }
        if (g_camTraceOk)
            Log(1, "0.26 camera trace: %u code checks + settings lookup 0x0054df80 (%s) + the fallback block 0x6026b6 "
                   "passed", static_cast<unsigned>(sizeof(kCamTraceChecks) / sizeof(kCamTraceChecks[0])),
                lookup == 2 ? "TruDataGuard's jump + original tail, accepted - the trace reads the table itself"
                            : "original bytes");
    }
    if (!g_camTraceOk) return false;
    g_camTraceFile = _fsopen(g_camTracePath, "a", _SH_DENYNO);
    if (!g_camTraceFile) {
        Log(0, "0.25 camera trace: cannot open %s (errno %d) - off until [Camera] Trace is switched 0 -> 1 again",
            g_camTracePath, errno);
        g_camTrace = 0;                                        // no retry per frame; CamTraceReadSwitch re-arms on 0 -> 1
        return false;
    }
    fputs("host_time\tt\tside\tcam_mode\tcam_obj\tcam_x\tcam_y\tcam_z\tlara_x\tlara_y\tlara_z\tcam_yaw\tcam_pitch\t"
          "lara_yaw\tdelta_yaw\tcam_dir\tcam_dist\tcam_fov_deg\tcam_clock\tcam_delay\tcam_ramp\tcam_weight\t"
          "cam_settings\tworld_scale\tworld_dt\tpower\tmeter\tdopp\tlara_rec0\tcam_step\tpad_rx\tpad_ry\tpad_buttons\n",
          g_camTraceFile);
    fflush(g_camTraceFile);
    QueryPerformanceFrequency(&g_camTraceFreq);
    QueryPerformanceCounter(&g_camTraceT0);
    g_camTraceRows = 0;
    Log(1, "0.25 camera trace: on - %s every %d ms (columns = TruXenia --camtrace)", g_camTracePath, g_camTraceMs);
    return true;
}

// "%.Nf" or "-" into a small buffer
const char *CtNum(char *b, size_t n, bool ok, double v, int decimals) {
    if (!ok) { strcpy_s(b, n, "-"); return b; }
    _snprintf_s(b, n, _TRUNCATE, "%.*f", decimals, v);
    return b;
}

// game thread, from MeterTick (Lara exists)
void CamTraceTick() {
    if (!g_camTrace) {
        if (g_camTraceFile) CamTraceClose("[Camera] Trace=0");
        return;
    }
    const DWORD now = GetTickCount();
    if (g_camTraceFile && now - g_camTraceTick < static_cast<DWORD>(g_camTraceMs)) return;
    g_camTraceTick = now;
    if (!g_camTraceFile && (g_camTraceOk == 0 || !CamTraceOpen())) return;
    DWORD mode = 0, cur = 0, gp = 0, vt = 0, slot = 0, lara = 0;
    bool modeOk = CtD(kCtMgr + 0x58, &mode);
    CtD(kCtMgr + 0x44, &cur);
    CtD(kCtMgr + 0xb80, &gp);
    if (cur) CtD(cur, &vt);
    float cx = 0, cy = 0, cz = 0, rx = 0, rz = 0, fov = 0, lx = 0, ly = 0, lz = 0, lyaw = 0;
    bool posOk = false, rotOk = false, fovOk = false, laraOk = false, yawOk = false;
    if (vt && CtD(vt + 0x38, &slot) && slot == kCtGetXf)
        posOk = CtF(cur + 0x40, &cx) && CtF(cur + 0x44, &cy) && CtF(cur + 0x48, &cz);
    if (vt && CtD(vt + 0x34, &slot) && slot == kCtGetRot) rotOk = CtF(cur + 0xa0, &rx) && CtF(cur + 0xa8, &rz);
    if (vt && CtD(vt + 0x40, &slot) && slot == kCtGetFov) fovOk = CtF(cur + 0xb0, &fov);
    if (CtD(0x00e7f094, &lara) && lara) {
        laraOk = CtF(lara + 0x20, &lx) && CtF(lara + 0x24, &ly) && CtF(lara + 0x28, &lz);
        yawOk = CtF(lara + 0x38, &lyaw);
    }
    const double kDeg = 57.29577951308232;
    const double camYaw = CtWrap(rz * kDeg), laraYaw = CtWrap(lyaw * kDeg);
    double dist = 0.0, dir = 0.0;
    if (posOk && laraOk) {
        const double dx = static_cast<double>(lx) - cx, dy = static_cast<double>(ly) - cy;
        dist = sqrt(dx * dx + dy * dy);
        dir = atan2(0.0 - dx, dy) * kDeg;
    }
    // recenter clock + settings of the gameplay camera (0x602690 / 0x5ffa90; with 0.25 DoppelgangerSettings the pick
    // of the patched fallback blocks)
    DWORD gvt = 0, sid = 0, data = 0;
    float clock = 0, delay = 0, ramp = 0;
    bool clockOk = false, setOk = false;
    char setText[64] = "-";
    if (gp && CtD(gp, &gvt) && gvt == kCtRewriteVt) {
        clockOk = CtF(gp + 0x1e4, &clock);
        if (CtD(gp + 0x1d0, &sid)) data = CtPick(static_cast<LONG>(sid), 0x144, setText, sizeof(setText));
        if (data) setOk = CtF(data + 0x10 + 0xb4, &delay) && CtF(data + 0x10 + 0xb8, &ramp);
    }
    double weight = 0.0;
    const bool weightOk = clockOk && setOk && ramp != 0.0f;
    if (weightOk) {
        weight = (static_cast<double>(clock) - delay) / ramp;
        weight = weight < 0.0 ? 0.0 : weight > 1.0 ? 1.0 : weight;
    }
    float scale = 0, wdt = 0;
    const bool scaleOk = CtF(0x00e7f1a0, &scale), wdtOk = CtF(0x00e7f188, &wdt);
    const int rec = CtRecordIndex();
    LARGE_INTEGER q;
    QueryPerformanceCounter(&q);
    const double t = g_camTraceFreq.QuadPart ? static_cast<double>(q.QuadPart - g_camTraceT0.QuadPart) /
                                                   static_cast<double>(g_camTraceFreq.QuadPart) : 0.0;
    SYSTEMTIME st;
    GetLocalTime(&st);
    char obj[64], recText[16], b[20][24];
    if (cur)
        _snprintf_s(obj, sizeof(obj), _TRUNCATE, "%s 0x%08lx vt 0x%08lx", cur == gp ? "gameplay" : "other", cur, vt);
    else
        strcpy_s(obj, sizeof(obj), "-");
    if (rec >= 0) _snprintf_s(recText, sizeof(recText), _TRUNCATE, "%d", rec);
    else strcpy_s(recText, sizeof(recText), rec == -2 ? "?" : "-");
    fprintf(g_camTraceFile,
            "%02d:%02d:%02d.%03d\t%.3f\tpc\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t"
            "%s\t%s\t%s\t%d\t%.1f\t%d\t%s\t%s\t%d\t%d\t0x%04x\n",
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds, t, CtNum(b[0], 24, modeOk, mode, 0), obj,
            CtNum(b[1], 24, posOk, cx, 1), CtNum(b[2], 24, posOk, cy, 1), CtNum(b[3], 24, posOk, cz, 1),
            CtNum(b[4], 24, laraOk, lx, 1), CtNum(b[5], 24, laraOk, ly, 1), CtNum(b[6], 24, laraOk, lz, 1),
            CtNum(b[7], 24, rotOk, camYaw, 2), CtNum(b[8], 24, rotOk, rx * kDeg, 2), CtNum(b[9], 24, yawOk, laraYaw, 2),
            CtNum(b[10], 24, rotOk && yawOk, CtWrap(camYaw - laraYaw), 2), CtNum(b[11], 24, posOk && laraOk, dir, 2),
            CtNum(b[12], 24, posOk && laraOk, dist, 0), CtNum(b[13], 24, fovOk, fov * kDeg, 1),
            CtNum(b[14], 24, clockOk, clock, 3), CtNum(b[15], 24, setOk, delay, 2), CtNum(b[16], 24, setOk, ramp, 2),
            CtNum(b[17], 24, weightOk, weight, 3), setText, CtNum(b[18], 24, scaleOk, scale, 3),
            CtNum(b[19], 24, wdtOk, wdt, 4), (g_meter.flags & 1) ? 1 : 0, g_meter.value, Doppelganger(), recText,
            g_camDtOk ? "tu" : "retail", static_cast<int>(g_padRx), static_cast<int>(g_padRy),
            static_cast<unsigned>(g_padButtons));
    fflush(g_camTraceFile);
    ++g_camTraceRows;
}

// [Camera] Trace / TraceInterval read again at most once a second (game thread, from the pad hook)
void CamTraceReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_camTraceSwitchTick < 1000) return;
    g_camTraceSwitchTick = now;
    const int v = GetPrivateProfileIntA("Camera", "Trace", g_camTrace, g_iniPath) ? 1 : 0;
    int ms = GetPrivateProfileIntA("Camera", "TraceInterval", g_camTraceMs, g_iniPath);
    if (ms < 10) ms = 10;
    if (ms > 5000) ms = 5000;
    if (ms != g_camTraceMs) {
        Log(1, "0.25 camera trace: [Camera] TraceInterval %d -> %d ms", g_camTraceMs, ms);
        g_camTraceMs = ms;
    }
    if (v != g_camTraceIni) {
        Log(1, "0.25 switch: [Camera] Trace %d -> %d (read again from TruShadowPower.ini)", g_camTraceIni, v);
        g_camTraceIni = v;
        g_camTrace = v;
    }
}

// ---- 0.25 [Camera] DoppelgangerSettings: the TU's camera settings choice in doppelganger mode ----
// TU 0x822bc198 (38 calls: LaraCamera / LaraCameraRewrite code, e.g. the update 0x822c39e4, the recenter weight
// 0x822c20cc, the instant recenter 0x822c2144) and 0x822c61d8 (10 calls, LaraCombatCamera): a camera's own settings id
// first; else the GlobalInfo default [[0x829ca200]+0x144] (+0x148 combat), but +0x14c (+0x150) when
// [[0x829892b0]+0x1244] (doppelganger) is set. The TU's GlobalInfo holds 21237 / 21238 there (live 2026-11-10 21:48:
// "GI+0x14c id 21237", delay 0.25 s / ramp 5.0 s; TU generalbank DTP 21237 data +0xc4 / +0xc8). The PC's GlobalInfo
// has other DTPs at +0x14c / +0x150 (DTP 22 ...), so the port uses the TU ids, not the PC offsets.
// PC: the lookup is inlined as `call 0x5d4080; mov eax,[eax+0x144|0x148]; push eax; call 0x54df80; add esp,4` - 28
// blocks (+0x144) in 0x5f9a6c..0x6026b6 and 6 (+0x148) in 0x602b5c..0x604d5d (work\camcmp_1111\pc_fallback_sites.py:
// exactly these 34 blocks in the exe; the other 17 / 5 GlobalInfo +0x144 / +0x148 readers have another form and are not
// camera fallbacks). Each block becomes `call DgStub144|148` + 15 nops; the stub keeps ecx / edx and returns the lookup
// result in eax like the block (the game's lookup 0x54df80 is called, so TruDataGuard's jump there stays in the path).
// Modes: 0 = retail (nothing patched, default), 1 = the TU choice 1:1 - in doppelganger mode id 21237 / 21238 when that
// DTP is loaded, else the retail default (the installed PC generalbank has NO DTP 21237 / 21238 - a data port is
// needed for mode 1 to change anything), 2 = like 1, and while DTP 21237 is not loaded a STAND-IN for it: a copy of the
// loaded default (PC DTP 20, checked: word0 0xb, delay 5.0, ramp 2.0, rate 1.0) with the TU's delay 0.25 / ramp 5.0.
// The stand-in is a PARTIAL port: TU 21237 equals PC DTP 20 in its scalar head except these two words, but its curve
// tables from S+0x124 on differ (work\camcmp_1111\cmp_dtp20_21237_full.txt) and are not ported. Combat 21238 has no
// stand-in. State 2102 (0.11, instant recenter) uses the same choice since 0.25 (before: PC GlobalInfo +0x14c = DTP 22).
const DWORD kDgSites144[] = {0x005f9a6c, 0x005f9b5c, 0x005f9f56, 0x005fa09c, 0x005faaec, 0x005fac1d, 0x005fc886,
                             0x005fcaa1, 0x005fcd9c, 0x005fd99d, 0x005fdd6b, 0x005fde0b, 0x005fdef0, 0x005fe2f6,
                             0x005fe94c, 0x005fea3c, 0x005fee36, 0x005fef7c, 0x005ff81c, 0x005ff94d, 0x00600c36,
                             0x00600e61, 0x0060115c, 0x00601d5d, 0x0060212b, 0x006021cb, 0x006022b0, 0x006026b6};
const DWORD kDgSites148[] = {0x00602b5c, 0x00602f41, 0x006031ba, 0x00604496, 0x00604b46, 0x00604d5d};
const DWORD kDgLookup = 0x0054df80, kDgGlobalInfoFn = 0x005d4080;
typedef DWORD(__cdecl *DgLookupFn)(int id);
volatile LONG g_dgSynthOn = 0;
bool g_dgSynthTried = false;
volatile LONG g_dgLastDecision[2] = {-1, -1};                  // per family, for the log
volatile LONG g_dgCalls[2][3] = {{0, 0, 0}, {0, 0, 0}};        // decisions counted (log)
char g_dgSetText[64] = "";                                     // ReportCamSettings: last logged choice
float g_dgSetDelay = -1.0f, g_dgSetRamp = -1.0f;
DWORD g_dgSetTick = 0;

// 0 = retail default, 1 = the TU id (its DTP is loaded), 2 = the stand-in (mode 2, +0x144 only)
int DgDecision(DWORD disp) {
    if (!g_dgPatched || !g_dgSettings || !Doppelganger()) return 0;
    if (CtEntry(disp == 0x144 ? kTuDgId144 : kTuDgId148)) return 1;
    if (g_dgSettings == 2 && disp == 0x144 && g_dgSynthOn) return 2;
    return 0;
}

// called by the patched blocks (game thread, camera code): the block's result
DWORD __cdecl CamFallback(DWORD disp) {
    const int d = DgDecision(disp);
    const int f = disp == 0x144 ? 0 : 1;
    InterlockedIncrement(&g_dgCalls[f][d]);
    if (InterlockedExchange(&g_dgLastDecision[f], d) != d) {
        static const char *const what[3] = {"the retail GlobalInfo default", "the TU id (DTP loaded)",
                                            "the stand-in (PC default + TU delay 0.25 / ramp 5.0)"};
        Log(1, "0.25 doppelganger settings: %s fallback now %s (%s, doppelganger %d)", f ? "combat camera (+0x148)"
            : "Lara camera (+0x144)", what[d], d ? (f ? "id 21238" : "id 21237") : "as retail", Doppelganger());
    }
    if (d == 2) return reinterpret_cast<DWORD>(g_dgSynth);
    const DWORD gi = reinterpret_cast<DWORD(__cdecl *)()>(kDgGlobalInfoFn)();
    const int id = d == 1 ? static_cast<int>(f ? kTuDgId148 : kTuDgId144) : *reinterpret_cast<const int *>(gi + disp);
    return reinterpret_cast<DgLookupFn>(kDgLookup)(id);
}

__declspec(naked) void DgStub144() {             // replaces call 0x5d4080 .. add esp,4 (20 bytes) at kDgSites144
    __asm {
        push ecx
        push edx
        push 0x144
        call CamFallback
        add esp, 4
        pop edx
        pop ecx
        ret
    }
}
__declspec(naked) void DgStub148() {             // the same for the combat camera blocks (+0x148)
    __asm {
        push ecx
        push edx
        push 0x148
        call CamFallback
        add esp, 4
        pop edx
        pop ecx
        ret
    }
}

bool DgBlockOk(DWORD at, DWORD disp) {
    BYTE b[20];
    __try { memcpy(b, reinterpret_cast<const void *>(at), sizeof(b)); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
    DWORD rel1 = 0, rel2 = 0, d = 0;
    memcpy(&rel1, b + 1, 4);
    memcpy(&d, b + 7, 4);
    memcpy(&rel2, b + 13, 4);
    return b[0] == 0xe8 && at + 5 + rel1 == kDgGlobalInfoFn && b[5] == 0x8b && b[6] == 0x80 && d == disp &&
           b[11] == 0x50 && b[12] == 0xe8 && at + 17 + rel2 == kDgLookup && b[17] == 0x83 && b[18] == 0xc4 &&
           b[19] == 0x04;
}

bool WriteCallPad(DWORD at, const void *to, int length) {
    BYTE code[20];
    memset(code, 0x90, sizeof(code));
    code[0] = 0xe8;
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (length > 20 || !VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

void PatchDgSettings() {
    if (!g_dgSettings) {
        Log(1, "0.25 doppelganger settings: [Camera] DoppelgangerSettings=0 - the cameras keep the retail GlobalInfo "
               "defaults in doppelganger mode (PC DTP 20 / 21; TU: 21237 / 21238)");
        return;
    }
    DWORD target = 0;
    const char *bad = CamSettingsState(&target) == 0 ? "section lookup tru+0x14df80"
                      : !HexBytesAt(kCamDefaults, kCamDefaultsHex) ? "GlobalInfo getter tru+0x1d4080" : nullptr;
    for (DWORD at : kDgSites144)
        if (!bad && !DgBlockOk(at, 0x144)) bad = "a +0x144 fallback block";
    for (DWORD at : kDgSites148)
        if (!bad && !DgBlockOk(at, 0x148)) bad = "a +0x148 fallback block";
    if (bad) {
        Log(0, "0.25 doppelganger settings: code does not match (%s) - off", bad);
        return;
    }
    int n = 0;
    for (DWORD at : kDgSites144) n += WriteCallPad(at, reinterpret_cast<const void *>(&DgStub144), 20) ? 1 : 0;
    for (DWORD at : kDgSites148) n += WriteCallPad(at, reinterpret_cast<const void *>(&DgStub148), 20) ? 1 : 0;
    const int all = static_cast<int>(sizeof(kDgSites144) / sizeof(kDgSites144[0]) + sizeof(kDgSites148) /
                                     sizeof(kDgSites148[0]));
    g_dgPatched = n > 0;
    Log(n == all ? 1 : 0, "0.25 doppelganger settings: [Camera] DoppelgangerSettings=%d - %d of %d camera fallback blocks "
        "patched (TU 0x822bc198 / 0x822c61d8: doppelganger -> id 21237 / 21238 when loaded%s); DTP 21237 %s, 21238 %s "
        "now", g_dgSettings, n, all, g_dgSettings == 2 ? ", else a stand-in for 21237" : ", else retail",
        CtEntry(kTuDgId144) ? "loaded" : "not loaded", CtEntry(kTuDgId148) ? "loaded" : "not loaded");
}

// ---- 0.26 doppelganger mode tables: the per-mode part of TU DTP 21237 in the stand-in (DoppelgangerSettings=2) ----
// (project doc Plan-Kamera-Vergleich-Xenia-PC-1111.md, 0.26; tools: work\power026_1111\cam_mode_tables.py,
// cam_set_records.py, make_dg_modes.py). A camera settings DTP holds two per-mode tables (S = data + 0x10):
//   A: S+0x134 count / S+0x138 -> 16-byte entries {nModes, modes*, nParams, params*}; 0x5f99f0 returns the first entry
//      that lists the camera's mode (+0x1e0) and has params; apply 0x601d30 (from SetMode vslot 0x60 0x6020e0 / 0x64
//      0x6021b0, TU 0x822c1e38 -> 0x822c5bd0) runs the 0x18-byte params {kind 1..0x1c, payload} through 0x5ff080
//      (jump table 0x5ff2a8): kind 10 / 11 = a camera position set (0x5f9940: payload {set DTP*, index}, 0x6c-byte
//      records) for +0x3b0 / +0x620 (0x6080f0), kind 2 = +0x1320, kinds 5 / 6 inline curves +0x1248 / +0x1278, ...
//   B: S+0x13c count / S+0x140 -> 12-byte entries {i8 key, nModes, modes*}; 0x5f9960(S, key, mode) (0x5fe800 /
//      0x5fe8c0 in SetMode -> cam+0x1344 / +0x1348): modes in which a focus object with record byte +0x4d == key uses
//      its own camera curves.
// The settings in both games go through the doppelganger-aware lookup in these paths (PC: the patched fallback blocks
// 0x60212b / 0x6021cb / 0x601d5d / 0x5fee36; TU: 0x822bc198 called by 0x822c1e38 and 0x822c5bd0), so in doppelganger
// mode EVERY mode of the gameplay camera reads DTP 21237's tables on the TU. TU 21237 against the TU retail default
// DTP 21 (= PC DTP 20 by value in every mode): table A has 35 entries instead of 25 - the first hit differs for the
// modes 0, 8, 23, 32, 33, 34, 58, 59, 60, 61, 62, 63 (60 / 61 / 62 = the climb modes of the live run 2026-11-10
// 22:24, with no entry at all in the retail tables; 8: +0x1320 1580 instead of 948 and other sets; 11 / 46 / 1 / 37
// are equal) - and table B has the extra entry key 22 for the modes 60..63. The sets of 21237 are the TU DTP 22194
// (86 records; TU retail DTP 31 = PC DTP 30, 76 records, equal at every index): 22194 records equal to 31 map to PC 30
// at the same index, the 13 others (changed or new) are built here from their converted words (word rules from the 76
// retail pairs; word 25 = the shared end pointer of the set DTP, taken from PC DTP 30 record 0). 0.25's stand-in kept
// DTP 20's tables, i.e. the climb modes ran with the retail (no) per-mode parameters. 0.26: the stand-in gets table A
// = the 12 ported TU entries first, then DTP 20's 25 entries (first hit = TU 21237 for every mode 0..127, checked by
// the generator), table B = DTP 20's 13 entries + key 22. The real DTP 21237 (when a data port loads it, DgDecision 1)
// carries its own tables; nothing here is used then. Each reader is byte-checked; a mismatch keeps 0.25's stand-in.
struct DgModeEntry { int firstMode, modes, firstRec, recs; };
struct DgModeRec { DWORD kind; DWORD w[5]; int set; };   // set: -1 none, 0..75 PC DTP 30 index, 0x100 + n built set n
// The tables are converted title-update data and therefore not in the repository (owner decision 2026-11-10): they are
// generated from the player's own TitleUpdate.000 + patch.000 by tools/tu_dg_modes_inc.py into the gitignored
// TruShadowPower_dgmodes.local.inc. Built without it, DgModeTables reports "not built in" and the stand-in keeps 0.25.
#if __has_include("TruShadowPower_dgmodes.local.inc")
#include "TruShadowPower_dgmodes.local.inc"
const CodeCheck kDgModeChecks[] = {
    {0x005f99f7, "8ba834010000"},                                       // 0x5f99f0: table A count S+0x134
    {0x005f9a04, "8b8038010000"},                                       // table A entries S+0x138
    {0x005f9a10, "8b30 32d2 33c9 3bce 7312 8b5004 393c8a"},             // entry {nModes, modes*}
    {0x005f9a30, "83780800 770c 83c301 83c010"},                        // nParams +8 > 0, stride 0x10
    {0x005f9977, "39b33c010000"},                                       // 0x5f9960: table B count S+0x13c
    {0x005f9990, "8b8340010000 0fbe0406"},                              // entries S+0x140, key byte +0
    {0x005f99a0, "8b8b40010000 8b543108 8b7c3104"},                     // modes* +8, nModes +4
    {0x005f99d2, "83c60c"},                                             // stride 12
    {0x005f9940, "8b08 85c9 740e 8b4004 3b01 7307 6bc06c 034104 c3"},   // set {table*, index}, 0x6c-byte records
    {0x005ff0b5, "8b400c 03442418 8b08 83c1ff 83f91b"},                 // params +0xc, kind 1..0x1c
    {0x005ff28b, "8344241818"},                                         // param stride 0x18
    {0x00601dc5, "8bbee0010000 8bc5 e81e7cffff"},                       // apply: mode +0x1e0 -> 0x5f99f0
};
const size_t kDgModeEntryCount = sizeof(kDgModeEntries) / sizeof(kDgModeEntries[0]);
const size_t kDgModeRecCount = sizeof(kDgModeRecs) / sizeof(kDgModeRecs[0]);
const size_t kDgModeSetCount = sizeof(kDgModeSets) / sizeof(kDgModeSets[0]);
const DWORD kDgPcTabA = 25, kDgPcTabB = 13, kDgPcSets = 76;    // PC DTP 20 / DTP 30 as the generator read them
DWORD g_dgTabA[kDgModeEntryCount + kDgPcTabA][4];
DWORD g_dgTabB[kDgPcTabB + 1][3];
DWORD g_dgRecs[kDgModeRecCount][6];
DWORD g_dgSets[kDgModeSetCount][27];
DWORD g_dgSetTable[2];                                         // {count, records*} as 0x5f9940 reads a set DTP

// fills the stand-in's table A / B pointers (S+0x134..0x140); data = PC DTP 20 data (the stand-in's source)
bool DgModeTables(DWORD data, char *why, size_t n) {
    for (const auto &c : kDgModeChecks)
        if (!HexBytesAt(c.address, c.bytes)) {
            _snprintf_s(why, n, _TRUNCATE, "code at 0x%08lx differs", c.address);
            return false;
        }
    const DWORD s = data + 0x10;
    DWORD nA = 0, pA = 0, nB = 0, pB = 0;
    if (!CtD(s + 0x134, &nA) || !CtD(s + 0x138, &pA) || !CtD(s + 0x13c, &nB) || !CtD(s + 0x140, &pB) || !pA || !pB ||
        nA != kDgPcTabA || nB != kDgPcTabB) {
        _snprintf_s(why, n, _TRUNCATE, "DTP 20 tables A %lu / B %lu, expected %lu / %lu", nA, nB, kDgPcTabA, kDgPcTabB);
        return false;
    }
    // the set DTP 30 as DTP 20's own kind 10 / 11 records name it (resolved pointer, payload word 0)
    DWORD p30 = 0;
    for (DWORD i = 0; i < nA && !p30; ++i) {
        DWORD np = 0, pr = 0;
        if (!CtD(pA + 16 * i + 8, &np) || !CtD(pA + 16 * i + 12, &pr) || !pr) continue;
        for (DWORD k = 0; k < np && !p30; ++k) {
            DWORD kind = 0;
            if (CtD(pr + 0x18 * k, &kind) && (kind == 10 || kind == 11)) CtD(pr + 0x18 * k + 4, &p30);
        }
    }
    DWORD n30 = 0, r30 = 0, end30 = 0;
    if (!p30 || !CtD(p30, &n30) || n30 != kDgPcSets || !CtD(p30 + 4, &r30) || !r30 || !CtD(r30 + 25 * 4, &end30) ||
        !end30) {
        _snprintf_s(why, n, _TRUNCATE, "set DTP 30 at 0x%08lx: %lu records (expected %lu), end pointer 0x%08lx", p30, n30,
                    kDgPcSets, end30);
        return false;
    }
    for (size_t i = 0; i < kDgModeSetCount; ++i) {
        memcpy(g_dgSets[i], kDgModeSets[i], sizeof(g_dgSets[i]));
        g_dgSets[i][25] = end30;
    }
    g_dgSetTable[0] = static_cast<DWORD>(kDgModeSetCount);
    g_dgSetTable[1] = reinterpret_cast<DWORD>(g_dgSets);
    for (size_t i = 0; i < kDgModeRecCount; ++i) {
        const DgModeRec &r = kDgModeRecs[i];
        g_dgRecs[i][0] = r.kind;
        memcpy(&g_dgRecs[i][1], r.w, sizeof(r.w));
        if (r.set >= 0x100) {
            g_dgRecs[i][1] = reinterpret_cast<DWORD>(g_dgSetTable);
            g_dgRecs[i][2] = static_cast<DWORD>(r.set - 0x100);
        } else if (r.set >= 0) {
            g_dgRecs[i][1] = p30;
            g_dgRecs[i][2] = static_cast<DWORD>(r.set);
        }
    }
    for (size_t i = 0; i < kDgModeEntryCount; ++i) {
        const DgModeEntry &e = kDgModeEntries[i];
        g_dgTabA[i][0] = static_cast<DWORD>(e.modes);
        g_dgTabA[i][1] = reinterpret_cast<DWORD>(&kDgModeModes[e.firstMode]);
        g_dgTabA[i][2] = static_cast<DWORD>(e.recs);
        g_dgTabA[i][3] = reinterpret_cast<DWORD>(g_dgRecs[e.firstRec]);
    }
    __try {
        memcpy(g_dgTabA[kDgModeEntryCount], reinterpret_cast<const void *>(pA), 16 * kDgPcTabA);
        memcpy(g_dgTabB, reinterpret_cast<const void *>(pB), 12 * kDgPcTabB);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        _snprintf_s(why, n, _TRUNCATE, "DTP 20 tables unreadable");
        return false;
    }
    g_dgTabB[kDgPcTabB][0] = 22;                                   // key byte 22 (+1..+3 padding 0)
    g_dgTabB[kDgPcTabB][1] = static_cast<DWORD>(sizeof(kDgBModes22) / sizeof(kDgBModes22[0]));
    g_dgTabB[kDgPcTabB][2] = reinterpret_cast<DWORD>(kDgBModes22);
    BYTE *ss = g_dgSynth + 0x10;
    const DWORD v[4] = {static_cast<DWORD>(kDgModeEntryCount + kDgPcTabA), reinterpret_cast<DWORD>(g_dgTabA),
                        kDgPcTabB + 1, reinterpret_cast<DWORD>(g_dgTabB)};
    memcpy(ss + 0x134, v, sizeof(v));
    const DWORD e30 = CtEntry(30);
    Log(1, "0.26 doppelganger mode tables: stand-in table A %lu entries (the %u TU 21237 entries of the modes 0 8 23 32 33 "
           "34 58 59 60 61 62 63 first, then DTP 20's %lu) / table B %lu (+ key 22: modes 60..63); %u set records "
           "built (TU 22194 changed / new), PC set DTP 30 at 0x%08lx (%s the lookup of id 30)", v[0],
        static_cast<unsigned>(kDgModeEntryCount), kDgPcTabA, v[2], static_cast<unsigned>(kDgModeSetCount), p30,
        e30 && e30 + 0x10 == p30 ? "=" : "!=");
    return true;
}
#else
bool DgModeTables(DWORD, char *why, size_t n) {
    _snprintf_s(why, n, _TRUNCATE, "tables not built in: tools/tu_dg_modes_inc.py");
    return false;
}
#endif

// game thread (MeterTick): mode 2 builds the stand-in once, the first time the doppelganger flag is set and DTP 21237
// is not loaded
void DgSynthTick() {
    if (g_dgSettings != 2 || !g_dgPatched || g_dgSynthTried || !Doppelganger() || CtEntry(kTuDgId144)) return;
    g_dgSynthTried = true;
    DWORD gi = 0, fid = 0, e = 0, word0 = 0;
    float dl = 0, rp = 0, rt = 0;
    if (!CtD(kCtGlobalInfo, &gi) || !gi || !CtD(gi + 0x144, &fid) || !(e = CtEntry(static_cast<LONG>(fid)))) {
        Log(0, "0.25 doppelganger settings: no stand-in - the GlobalInfo default +0x144 is not loaded");
        return;
    }
    const DWORD data = e + 0x10;
    if (!CtD(data, &word0) || word0 != 0xb || !CtF(data + 0x10 + 0xb4, &dl) || !CtF(data + 0x10 + 0xb8, &rp) ||
        !CtF(data + 0x10 + 0xbc, &rt) || dl != 5.0f || rp != 2.0f || rt != 1.0f) {
        Log(0, "0.25 doppelganger settings: no stand-in - the default id %ld is not the known PC DTP 20 (word0 0x%lx, "
               "delay %.3f, ramp %.3f, rate %.3f)", static_cast<LONG>(fid), word0, dl, rp, rt);
        return;
    }
    __try { memcpy(g_dgSynth, reinterpret_cast<const void *>(data), kDgSynthSize); }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "0.25 doppelganger settings: no stand-in - DTP %ld unreadable", static_cast<LONG>(fid));
        return;
    }
    const DWORD tuDelay = 0x3e800000, tuRamp = 0x40a00000;     // TU generalbank DTP 21237 data +0xc4 / +0xc8
    memcpy(g_dgSynth + 0x10 + 0xb4, &tuDelay, 4);
    memcpy(g_dgSynth + 0x10 + 0xb8, &tuRamp, 4);
    char why[96] = "";
    g_dgModesOn = DgModeTables(data, why, sizeof(why));        // 0.26: the per-mode tables of 21237
    if (!g_dgModesOn)
        Log(0, "0.26 doppelganger mode tables: not ported (%s) - the stand-in keeps DTP 20's mode tables as 0.25", why);
    InterlockedExchange(&g_dgSynthOn, 1);
    Log(1, "0.25 doppelganger settings: stand-in for DTP 21237 built at 0x%08lx = DTP %ld (0x%lx bytes) with the TU's "
           "delay 0.25 s / ramp 5.00 s instead of %.2f / %.2f (rate %.2f kept; %s)",
        reinterpret_cast<DWORD>(g_dgSynth), static_cast<LONG>(fid), kDgSynthSize, dl, rp, rt,
        g_dgModesOn ? "0.26: 21237's mode tables A / B ported - outside them 21237 equals the retail default"
                    : "mode tables of 21237 not ported");
}

// game thread (MeterTick), at most once a second: the gameplay camera's settings choice, logged when it changes
void ReportCamSettings() {
    const DWORD now = GetTickCount();
    if (now - g_dgSetTick < 1000) return;
    g_dgSetTick = now;
    DWORD gp = 0, vt = 0, sid = 0;
    if (!CtD(kCtMgr + 0xb80, &gp) || !gp || !CtD(gp, &vt) || vt != kCtRewriteVt || !CtD(gp + 0x1d0, &sid)) return;
    char t[64];
    const DWORD data = CtPick(static_cast<LONG>(sid), 0x144, t, sizeof(t));
    float dl = -1.0f, rp = -1.0f;
    if (data && !(CtF(data + 0x10 + 0xb4, &dl) && CtF(data + 0x10 + 0xb8, &rp))) dl = rp = -1.0f;
    if (strcmp(t, g_dgSetText) == 0 && dl == g_dgSetDelay && rp == g_dgSetRamp) return;
    strcpy_s(g_dgSetText, sizeof(g_dgSetText), t);
    g_dgSetDelay = dl;
    g_dgSetRamp = rp;
    Log(1, "camera settings: gameplay camera 0x%08lx uses %s - recenter delay %.2f s, ramp %.2f s (doppelganger %d, "
           "[Camera] DoppelgangerSettings %d)", gp, t, dl, rp, Doppelganger(), g_dgSettings);
}

// ================================================================================================================
// 0.18 (K11, project doc Befund-TU-K9-K11-0711.md; K11 in Befund-Exe-Stellen-K8-K14-0611.md): CombatManager::Update
// tru+0x3227d0 (thiscall, ecx = [gameTracker+0x504], called once per frame by the player update at tru+0x3228ae) =
// retail 0x823daa58 = TU 0x823dca00. Same call order on all three: 0x7216b0, ADRENALINE TICK tru+0x318bd0 (retail
// 0x823dceb0, TU 0x823defa8), 0x7213a0, 0x71e490, 0x70d2a0, two handle releases with 0x70d810, 0x71d0f0, and as tail
// call the ADRENALINE BAR tru+0x2f2930 (retail 0x823ddc70, TU 0x823dfea8). The TU wraps exactly those two calls in
// `if (gameTracker+0x1244 == 0)` (0x823dca18..0x823dca2c and 0x823dcae0..0x823dcaf4; retail calls both always): in
// doppelganger mode the retail adrenaline neither ticks (R3 start / stop, message 0x3b) nor drains CM+0x3c nor writes
// the HUD value [0xfae8d4] (= meter value / [0xfad764]+0x2d0 every frame) and HUD group 1. The DLC 2 shadow meter
// drives the same HUD value (hudscreenmgr native 36), so on the PC the bar overwrote this plugin's meter every frame.
// Port: the call at tru+0x3227da and the tail jump at tru+0x322865 go to K11TickStub / K11BarStub, which test the same
// byte [[0xfadb58]+0x1244] (written by TruDlc2Player 0.4 as the TU's DoppelgangerInit) and return at once when it is
// set, else continue into the game's function. [Adrenaline] Translate=1 (default: a pure translation of the TU's two
// tests), read again at run time at most once per second; [Adrenaline] Log=1: one line per change of the decision.
// With it the adrenaline stubs of 0.9 inside the tick (tru+0x3189c6 start - only caller the tick -, tru+0x318bf3,
// tru+0x318c5d, tru+0x318cda) are no longer reached in doppelganger mode, as the TU's own doppelganger branches in
// 0x823defa8 / 0x823ded18 are dead code there; they stay patched (see the report) - stop tru+0x318ad6 is still called
// from tru+0x1d4864 / tru+0x31eff9, the camera chooser tru+0x1e80a9 and condition 1047 do not depend on the tick.
const DWORD kCmUpdate = 0x007227d0;           // retail 0x823daa58, TU 0x823dca00
const DWORD kCmTickCall = 0x007227da;         // call tru+0x318bd0 (5 bytes) - patched
const DWORD kCmBarJump = 0x00722865;          // jmp tru+0x2f2930 (5 bytes, tail call) - patched
const DWORD kAdrTickFn = 0x00718bd0;          // adrenaline tick, retail 0x823dceb0, TU 0x823defa8
const DWORD kAdrBarFn = 0x006f2930;           // adrenaline bar, retail 0x823ddc70, TU 0x823dfea8
int g_k11 = 1;                                // [Adrenaline] Translate
int g_k11Log = 1;                             // [Adrenaline] Log
bool g_k11Hooked = false;
// g_iniPath (0.18): defined next to g_logPath since 0.25 (the camera trace switch reads it earlier in the file)
DWORD g_k11SwitchTick = 0;
DWORD g_adrTickTo = kAdrTickFn, g_adrBarTo = kAdrBarFn;
volatile LONG g_k11Count[2][2];               // [tick / bar][run / skipped]
int g_k11Last[2] = {-1, -1};                  // last decision per site (log on change)

void K11ReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_k11SwitchTick < 1000) return;
    g_k11SwitchTick = now;
    const int t = GetPrivateProfileIntA("Adrenaline", "Translate", g_k11, g_iniPath) ? 1 : 0;
    if (t == g_k11) return;
    Log(1, "0.18 switch: [Adrenaline] Translate %d -> %d (read again from TruShadowPower.ini) - %s", g_k11, t,
        t ? "adrenaline tick / bar skipped in doppelganger mode as the TU" : "the PC runs them always");
    g_k11 = t;
}

// game thread, from the two stubs: 1 = skip the call (TU: gameTracker+0x1244 != 0), 0 = run the game's function
int __cdecl K11Skip(int site) {
    K11ReadSwitch();
    int skip = 0;
    if (g_k11) {
        __try {
            const BYTE *gt = GameTracker();
            skip = (gt && gt[0x1244] != 0) ? 1 : 0;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            skip = 0;
        }
    }
    const LONG n = InterlockedIncrement(&g_k11Count[site][skip]);
    const int state = g_k11 ? skip : 2;
    if (g_k11Log && state != g_k11Last[site]) {
        g_k11Last[site] = state;
        static const char *const what[2] = {"adrenaline tick tru+0x318bd0 (call tru+0x3227da, TU 0x823dca1c)",
                                            "adrenaline bar tru+0x2f2930 (tail jump tru+0x322865, TU 0x823dcae0)"};
        Log(1, "0.18 K11: %s %s (call %ld of this kind; totals run %ld / skipped %ld)%s", what[site],
            state == 2 ? "RUNS - [Adrenaline] Translate=0 (PC)"
            : skip ? "SKIPPED - doppelganger mode (gameTracker+0x1244 set), as the TU"
                   : "runs - not in doppelganger mode",
            n, g_k11Count[site][0], g_k11Count[site][1],
            site == 1 && skip ? " - HUD value [0xfae8d4] / group 1 now only from the meter (Refill / Drain)" : "");
    }
    return skip;
}

// called from tru+0x3227da instead of tru+0x318bd0: ecx = CombatManager, [esp] = tru+0x3227df; eax / edx are not used
// by the caller afterwards (the next instructions reload ecx and call), the FPU stack is empty
__declspec(naked) void K11TickStub() {
    __asm {
        push ecx
        push 0
        call K11Skip
        add esp, 4
        pop ecx
        test eax, eax
        jnz k11_tick_skip
        jmp dword ptr [g_adrTickTo]
    k11_tick_skip:
        ret
    }
}

// jumped to from tru+0x322865 instead of tru+0x2f2930 (tail call: esi already popped, [esp] = the return address into
// the player update tru+0x3228b3, which reloads ecx and uses no result); skip = return to it at once
__declspec(naked) void K11BarStub() {
    __asm {
        push ecx
        push 1
        call K11Skip
        add esp, 4
        pop ecx
        test eax, eax
        jnz k11_bar_skip
        jmp dword ptr [g_adrBarTo]
    k11_bar_skip:
        ret
    }
}

void PatchK11() {
    if (!g_k11 && !g_k11Log) {
        Log(1, "0.18 K11: [Adrenaline] Translate=0 and Log=0 - CombatManager::Update tru+0x3227d0 untouched (a later "
               "Translate=1 needs a restart)");
        return;
    }
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kCmUpdate,
         "56 8bf1 e8d8eeffff 8bce e8f163ffff 8bce e8baebffff 8bce e8a3bcffff 8bce e8acaafeff 8b460c 85c0 7424 8b08 85c9 "
         "7404 8bc1 eb1c 834004ff 750d 8b0dc4a0cd00 8908 a3c4a0cd00 c7460c00000000 33c0 8b0e 50 e8e7affeff 8b4610 85c0 "
         "7420 8b08 85c9 751c 834004ff 750d 8b15c4a0cd00 8910 a3c4a0cd00 c7461000000000 33c9 51 8b4e04 e8b5affeff 8bce "
         "e88ea8ffff 8bce 5e e9c600fdff",
         "CombatManager::Update tru+0x3227d0: 5 calls (2nd = adrenaline tick tru+0x318bd0), handles, tru+0x31d0f0, tail "
         "jump to the adrenaline bar tru+0x2f2930"},
        {0x007228a8, "8b8b04050000 e81dffffff 8b8b08050000",
         "player update: CombatManager::Update on [gameTracker+0x504] at tru+0x3228ae"},
        {kAdrTickFn, "d9ee 56 8bf1 d85e3c dfe0 f6c405 0f8a8e000000", "adrenaline tick tru+0x318bd0 (thiscall, CM+0x3c)"},
        {kAdrBarFn, "8b91fc010000 d9ee 83ec08 f7c200004000 756f", "adrenaline bar tru+0x2f2930 (thiscall, player +0x1fc)"},
        {0x006f29b2,
         "d9413c a164d7fa00 d8b0d0020000 d91dd4e8fa00 f781fc01000000004000 7519 d8593c dfe0 f6c405 7a11 6a01 e8edaf0800 "
         "83c40c e985b00800 ddd8 83c408 c3",
         "adrenaline bar: [0xfae8d4] = CM+0x3c / [0xfad764]+0x2d0 every call, HUD group 1 (tru+0x37d9d0 / tru+0x37da70)"},
        {0x00777dc0, "a158dbfa00 8a8044120000 c3", "doppelganger byte [[0xfadb58]+0x1244] (larabase f36 tru+0x377dc0)"},
    };
    for (const auto &f : facts)
        if (!HexBytesAt(f.at, f.hex)) {
            Log(0, "0.18 K11: %s at 0x%08lx does not match - CombatManager::Update left to the game", f.what, f.at);
            return;
        }
    BYTE call[5] = {0xe8}, jump[5] = {0xe9};
    DWORD rel = reinterpret_cast<DWORD>(&K11TickStub) - (kCmTickCall + 5);
    memcpy(call + 1, &rel, 4);
    rel = reinterpret_cast<DWORD>(&K11BarStub) - (kCmBarJump + 5);
    memcpy(jump + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    void *p = reinterpret_cast<void *>(kCmTickCall);
    const DWORD length = kCmBarJump + 5 - kCmTickCall;
    if (!VirtualProtect(p, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "0.18 K11: VirtualProtect failed (%lu) - CombatManager::Update left to the game", GetLastError());
        return;
    }
    memcpy(reinterpret_cast<void *>(kCmTickCall), call, 5);
    memcpy(reinterpret_cast<void *>(kCmBarJump), jump, 5);
    VirtualProtect(p, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), p, length);
    g_k11Hooked = true;
    Log(1, "0.18 K11: tru+0x3227da (adrenaline tick) and tru+0x322865 (adrenaline bar) -> plugin - [Adrenaline] Translate "
           "%d (%s), log %d; read again at run time at most once per second. In doppelganger mode the 0.9 stubs inside "
           "the tick (tru+0x3189c6 / +0x318bf3 / +0x318c5d / +0x318cda) are then not reached (TU: its own branches there "
           "are dead code as well); tru+0x318ad6 (stop, also from tru+0x1d4864 / tru+0x31eff9), tru+0x1e80a9 and "
           "condition 1047 stay in use", g_k11,
        g_k11 ? "TU 0x823dca00: both skipped while gameTracker+0x1244 is set" : "PC: both always", g_k11Log);
}

// ================================================================================================================
// 0.21 (X23, workspace docs Befund-X23-Kraftlauf-0911.md, Befund-PC-Test-0911-Abend.md rows 5 / 5b): time-scale
// request slot 6 = the gamebase natives 23 / 24 as the TU.
//
// gamebase (generalbank script 55, functions f23 @0x3f8 / f24 @0x414, static natives with two floats: args[0] target,
// args[1] seconds). Bound by the native binder of the type: TU 0x824a28c0 (stw at +0x298 / +0x2b4 = entries 23 / 24,
// pairs with retail 0x8249ced0, not with 0x8249cd98 as tu_coverage.tsv guesses), PC tru+0x3b44a0 (tru+0x3b4548:
// push 0x797cf0; push 0x17; call tru+0x1768f0 / push 0x797d10; push 0x18; ...).
//   retail 0x8249dac8 (23) / 0x8249db18 (24): ramp world 0x8277525c / player 0x8277523c = {target, seconds x 1000,
//          current scale, now} - PC tru+0x397cf0 / tru+0x397d10 call SetWorldTimeScale tru+0x376030 /
//          SetPlayerTimeScale tru+0x376090, the same ramps 0x8abeb4 / 0x8abe94.
//   TU 0x824a3238 (23) / 0x824a32f0 (24): r7 = player state [0x829892b0] (PC [0xfadb58]); if r7 != 0 and the tuning
//          lookup 0x82415518 (tracker+0x1314 extension data; plugin FindTuning) != 0 and byte r7+0x1244 != 0 and the
//          meter r7+0x508 != 0: stfs args[0] -> meter +0x70 (23) / meter +0x74 (24) (0x824a3280 / 0x824a3338), selector
//          0x823d7520(meter +0x40), return - args[1] (the duration) is loaded but not used. Else the retail body
//          (ramp 0x827754cc world for 23 / 0x827754ac player for 24).
//   The selector reads slot k at meter +0x40 + 8k: +0 player (-> ramp 0x827754ac), +4 world (-> 0x827754cc). So in
//   doppelganger mode native 23 (retail: world) requests the PLAYER scale of slot 6 and native 24 (retail: player)
//   the WORLD scale - crossed against the retail meaning; translated as it stands.
//   A value <= 0 (threshold 0x8207d538 = 0.0) leaves the slot empty: the scripts clear slot 6 by calling the native
//   with 0 or a negative value. No other TU code writes meter +0x70 / +0x74 (stores of the natives only); the meter
//   init 0x823d7700 does not touch the list.
//   Callers in the DLC data (tools/script_ref_find.py 55 0x3f8,0x414 over the B270 kit, 268 DRMs): only script 205
//   f1 (Lara, proto vtIndex 55, debug text "Heads up!!!": f24(p0, p8), f23(p4 x p0, p8)) and DLC 1 script 3583
//   (dlc_caverns). No DLC script refers to 205's prototype 2 (the virtual "Heads up"); its partners f2 / f3 ("You
//   Failed" / "Success") call gamebase f2 / f1 (current scales directly, TU 0x824a30d0 / 0x824a30b8, not slot 6).
//   Neither native tests speed, state or input - "running" is not decided here.
// Port: tru+0x397cf0 / tru+0x397d10 start with a 5-byte jump to Native23Stub / Native24Stub. Slot6Native makes the
// TU's tests (player state [0xfadb58], FindTuning, byte +0x1244; the plugin's meter always exists = +0x508) and writes
// g_meter.request[6][0] (23) / [6][1] (24) + Selector(); else (or with [TimeScale] TranslateSlot6=0) the game's own
// body runs through a trampoline (its first 7 bytes, then back to +7). Byte checks of both bodies and of the binder
// lines before any patch. One log line per slot-6 change (and per native call at LogLevel 2; the first 50 calls of
// the retail path also at LogLevel 1). TranslateSlot6 is read again at run time at most once per second (only when
// hooked at the start); switching it off releases a set slot 6 (plugin rule, not TU).
const DWORD kNative23 = 0x00797cf0;           // gamebase native 23 (TU 0x824a3238, retail 0x8249dac8)
const DWORD kNative24 = 0x00797d10;           // gamebase native 24 (TU 0x824a32f0, retail 0x8249db18)
// mov eax,[esp+0xc]; fld [eax+4]; sub esp,8; fstp [esp+4]; fld [eax]; mov eax,[esp+0xc]; mov ecx,[eax+0x14];
// fstp [esp]; call SetWorldTimeScale tru+0x376030 / SetPlayerTimeScale tru+0x376090; ret
const char *const kNative23Hex = "8b44240c d94004 83ec08 d95c2404 d900 8b44240c 8b4814 d91c24 e821e3fdff c3";
const char *const kNative24Hex = "8b44240c d94004 83ec08 d95c2404 d900 8b44240c 8b4814 d91c24 e861e3fdff c3";
const DWORD kGamebaseBind = 0x007b4548;       // in the gamebase binder tru+0x3b44a0: entries 0x17 / 0x18
const char *const kGamebaseBindHex = "68f07c7900 6a17 8bcf e89a23dcff 68107d7900 6a18 8bcf e88c23dcff";
const int kNativeMoved = 7;                   // mov eax,[esp+0xc] (4) + fld dword [eax+4] (3): no relative operand
int g_slot6 = 1;                              // [TimeScale] TranslateSlot6
bool g_slot6Hooked = false;
DWORD g_slot6SwitchTick = 0;
DWORD g_native23To = 0, g_native24To = 0;     // trampolines: the game's body of native 23 / 24
volatile LONG g_slot6Calls[2][2];             // [native 23 / 24][retail body / slot 6]

void Slot6Release(const char *why) {
    if (!(kZero < g_meter.request[6][0] || kZero < g_meter.request[6][1])) return;
    const float p = g_meter.request[6][0], w = g_meter.request[6][1];
    g_meter.request[6][0] = g_meter.request[6][1] = kNoRequest;
    Selector();
    float sp = kOne, sw = kOne;
    SelectorPick(&sp, &sw);
    Log(1, "0.21 slot 6: cleared (%s; was player %.3f / world %.3f) - selector now player %.3f, world %.3f", why, p, w,
        sp, sw);
}

void Slot6ReadSwitch() {
    if (!g_slot6Hooked || !g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_slot6SwitchTick < 1000) return;
    g_slot6SwitchTick = now;
    const int t = GetPrivateProfileIntA("TimeScale", "TranslateSlot6", g_slot6, g_iniPath) ? 1 : 0;
    if (t == g_slot6) return;
    Log(1, "0.21 switch: [TimeScale] TranslateSlot6 %d -> %d (read again from TruShadowPower.ini) - %s", g_slot6, t,
        t ? "gamebase natives 23 / 24 request slot 6 in doppelganger mode as the TU"
          : "gamebase natives 23 / 24 set the ramps directly (retail body)");
    g_slot6 = t;
    if (!t) Slot6Release("[TimeScale] TranslateSlot6=0");
}

// game thread (script VM, op66 static call of gamebase f23 / f24): 1 = handled as the TU's doppelganger branch,
// 0 = run the game's body (the TU's retail branch)
int __cdecl Slot6Native(int native, const float *args) {
    const int k = native == 24 ? 1 : 0;
    float value = kZero, seconds = kZero;
    __try {
        value = args[0];
        seconds = args[1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "0.21 slot 6: gamebase native %d - argument read fault (args 0x%08lx) - game body", native,
            reinterpret_cast<DWORD>(args));
        return 0;
    }
    Slot6ReadSwitch();
    const char *why = nullptr;
    if (!g_slot6) {
        why = "[TimeScale] TranslateSlot6=0";
    } else {
        const BYTE *gt = GameTracker();                 // TU: lwz r7, [0x829892b0]
        if (!gt) {
            why = "no player state [0xfadb58] (TU: [0x829892b0] = 0)";
        } else if (!FindTuning()) {                     // TU: bl 0x82415518
            why = "no tuning of object 858 (TU: 0x82415518 = 0)";
        } else {
            BYTE dg = 0;
            __try {
                dg = gt[0x1244];                        // TU: lbz r11, 0x1244(r7)
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                dg = 0;
            }
            if (!dg) why = "not in doppelganger mode (gameTracker+0x1244 = 0)";
            // TU: lwz r11, 0x508(r7) - the meter object; the plugin's meter always exists
        }
    }
    if (why) {
        const LONG n = InterlockedIncrement(&g_slot6Calls[k][0]);
        if (n <= 50 || g_logLevel >= 2)
            Log(n <= 50 ? 1 : 2, "0.21 slot 6: gamebase native %d (%s %.3f over %.3f s) -> game body, ramp set directly "
                                 "- %s (call %ld of this kind)", native, native == 23 ? "world" : "player", value,
                seconds, why, n);
        return 0;
    }
    const LONG n = InterlockedIncrement(&g_slot6Calls[k][1]);
    float *slot = &g_meter.request[6][native == 23 ? 0 : 1];    // TU: stfs f0, 0x70(r11) (23) / 0x74(r11) (24)
    const float was = *slot;
    *slot = value;
    Selector();                                                  // TU: bl 0x823d7520 (meter +0x40)
    float sp = kOne, sw = kOne;
    SelectorPick(&sp, &sw);
    const bool change = was != value;
    if (change || g_logLevel >= 2)
        Log(change ? 1 : 2, "0.21 slot 6: gamebase native %d (script value %.3f, duration %.3f s not used) in doppelganger "
                            "mode -> slot 6 %s (meter +0x%x) %.3f -> %.3f (TU 0x%08lx) - selector: player %.3f, world "
                            "%.3f (slot 6 now player %.3f / world %.3f; call %ld of this kind)",
            native, value, seconds, native == 23 ? "PLAYER" : "WORLD", native == 23 ? 0x70 : 0x74, was, value,
            native == 23 ? 0x824a3280UL : 0x824a3338UL, sp, sw, g_meter.request[6][0], g_meter.request[6][1], n);
    return 1;
}

// jumped to from tru+0x397cf0 / tru+0x397d10 (cdecl: [esp] = return into the script VM, [esp+0xc] = the argument
// block, as the game's body reads it); eax / ecx / edx are free, the FPU stack is empty
__declspec(naked) void Native23Stub() {
    __asm {
        mov eax, [esp + 0xc]
        push eax
        push 23
        call Slot6Native
        add esp, 8
        test eax, eax
        jnz n23_done
        jmp dword ptr [g_native23To]
    n23_done:
        ret
    }
}

__declspec(naked) void Native24Stub() {
    __asm {
        mov eax, [esp + 0xc]
        push eax
        push 24
        call Slot6Native
        add esp, 8
        test eax, eax
        jnz n24_done
        jmp dword ptr [g_native24To]
    n24_done:
        ret
    }
}

// the first kNativeMoved bytes of the game's body, then a jump back behind them
DWORD MakeNativeTrampoline(DWORD at) {
    BYTE *t = static_cast<BYTE *>(VirtualAlloc(nullptr, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!t) return 0;
    memcpy(t, reinterpret_cast<const void *>(at), kNativeMoved);
    t[kNativeMoved] = 0xe9;
    const DWORD back = (at + kNativeMoved) - (reinterpret_cast<DWORD>(t) + kNativeMoved + 5);
    memcpy(t + kNativeMoved + 1, &back, 4);
    FlushInstructionCache(GetCurrentProcess(), t, 16);
    return reinterpret_cast<DWORD>(t);
}

void PatchSlot6() {
    if (!g_slot6) {
        Log(1, "0.21 slot 6: [TimeScale] TranslateSlot6=0 - gamebase natives 23 / 24 untouched (a later 1 needs a "
               "restart)");
        return;
    }
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kNative23, kNative23Hex, "gamebase native 23 tru+0x397cf0 (args -> SetWorldTimeScale tru+0x376030)"},
        {kNative24, kNative24Hex, "gamebase native 24 tru+0x397d10 (args -> SetPlayerTimeScale tru+0x376090)"},
        {kGamebaseBind, kGamebaseBindHex, "gamebase binder tru+0x3b4548 (entries 0x17 / 0x18 = tru+0x397cf0 / tru+0x397d10)"},
        {kSetWorld, "51 a15cf1e700 db055cf1e700 85c0", "SetWorldTimeScale tru+0x376030"},
        {kSetPlayer, "51 a15cf1e700 db055cf1e700 85c0", "SetPlayerTimeScale tru+0x376090"},
    };
    for (const auto &f : facts)
        if (!HexBytesAt(f.at, f.hex)) {
            Log(0, "0.21 slot 6: %s at 0x%08lx does not match - natives 23 / 24 left to the game", f.what, f.at);
            return;
        }
    g_native23To = MakeNativeTrampoline(kNative23);
    g_native24To = MakeNativeTrampoline(kNative24);
    if (!g_native23To || !g_native24To) {
        Log(0, "0.21 slot 6: VirtualAlloc failed (%lu) - natives 23 / 24 left to the game", GetLastError());
        return;
    }
    if (!WriteJump5(kNative23, reinterpret_cast<const void *>(&Native23Stub))) {
        Log(0, "0.21 slot 6: native 23 not written (VirtualProtect %lu) - natives 23 / 24 left to the game", GetLastError());
        return;
    }
    if (!WriteJump5(kNative24, reinterpret_cast<const void *>(&Native24Stub))) {
        Log(0, "0.21 slot 6: native 24 not written (VirtualProtect %lu) - only native 23 translated", GetLastError());
    }
    g_slot6Hooked = true;
    Log(1, "0.21 slot 6: gamebase natives 23 / 24 (tru+0x397cf0 / tru+0x397d10) -> plugin: in doppelganger mode "
           "(player state, tuning 858, gameTracker+0x1244) native 23 writes request slot 6 PLAYER, native 24 slot 6 "
           "WORLD, then the selector (TU 0x824a3238 / 0x824a32f0); else the game's body. [TimeScale] TranslateSlot6 "
           "read again at run time at most once per second");
}

// ================================================================================================================
// 0.22 (K-5, workspace docs Befund-Anvisier-Kreis-0911.md section 6, Befund-TU-Abdeckung-Teilweise-1011.md): the
// combat reticle request and the adrenaline refill in doppelganger mode as the TU.
//
// Ring request - playerDrawCombatLock TU 0x823de170 (retail 0x823dc120, PC tru+0x31e710; draw chain retail = PC:
// PLAYER_DrawIndicators tru+0x3212d0 -> tru+0x31e710 -> playerDrawCombatReticle tru+0x3037d0, which writes style /
// position 0xfae8a4..bc and requests HUD group 12, drawn by HUD script 37). Without CM+0x1fc bit 11 the target is
// player +0x544 / the sense search (PC tru+0x31d0c0); then the ring is drawn when a target exists and
//   retail 0x823dc424 (to retail 0x823dc434) / PC tru+0x31e966..0x31e981: bit 9 or 10 (PC helper tru+0x2f1ed0) or 21;
//   TU 0x823de47c..0x823de4a4: bit 9 or 10, else r9 = [0x829892b0] (PC [0xfadb58]): lbz +0x1244 != 0 ->
//          (([r9+0x508])+4 >> 1) & 1 (meter flag 2) else (CM+0x1fc >> 21) & 1; 0 -> 0x823de618 (no ring).
// The PC keeps CM+0x1fc in edi from tru+0x31e92a; the site tru+0x31e979 is `mov edx,edi; shr edx,15h; test dl,1;
// je tru+0x31eb2a` (14 bytes). Port: a 5-byte jump there to RingStub, which asks RingRequestBit (the TU's two tests;
// meter = this plugin's meter, flag 2 = the shadow strike of TruShadowCombat [Strike] Translate=1) and goes on at
// tru+0x31e987 (ring) or tru+0x31eb2a (none), edx = word >> 21 as the original. TU r10 is reloaded before every later
// use (0x823de4b8 / 0x823de630 / 0x823de658), so the overwritten r10 of the doppelganger branch has no other effect.
//
// Refill - PlayerSM::DefaultMessageHandler TU 0x823ed958 (retail 0x823eb270, PC tru+0x31f1d0): the refill case
//   retail 0x823eba74 (to retail 0x823ebb54): CM = [gt]+0x504; CM+0x1fc bit 21 -> skip; else byte 0x829ca5bf = 1, if !bit 22:
//          CM+0x3c += value, byte 0x829ca5e8 = 0, at >= [0x82988b3c]+0x2d0: CM+0x3c = max and, if !bit 27, bit 22 set
//          + the two bytes again (inline); then HUD value = CM+0x3c / max, HUD group 1. PC tru+0x31f4f4 (the bit-21
//          test) + tru+0x2f28c0 (the rest, out of line; full -> tru+0x2e6630, the retail inline part).
//   TU 0x823ee158..0x823ee22c: gt+0x1244 ? meter flag 2 (0x823ee16c rlwinm 0x1f) : CM bit 21 -> skip; the full case
//          calls 0x823dfd98 instead of the inline part.
//   TU 0x823dfd98 (leaf, no .pdata; = PC tru+0x2e6630, thiscall CM): CM+0x3c = max; gt+0x1244 ? meter flag 0x40
//          (0x823dfdc4 rlwinm 0x1a) : CM bit 27 (0x823dfdd0 rlwinm 5); set -> return; else CM+0x1fc |= 0x400000
//          (bit 22), the two HUD bytes. The PC function has a second caller, the script native tru+0x377a50 (jmp
//          tru+0x2e6630 with ecx = CM) - the branch is inside the TU function, so it applies to every caller.
// Port: a 6-byte jump at tru+0x31f500 (`mov eax,[ecx+1FCh]`) to RefillGateStub (skip -> tru+0x31fcb9 = return 0, else
// tru+0x31f511) and an 8-byte jump at tru+0x2e6646 (`shr edx,1Bh; test dl,1; jne`, after the fstp: FPU empty) to
// FullStub (active -> tru+0x2e6667 = ret, else tru+0x2e664e). Not ported, still open: TU 0x823eebc0 (message
// 0x200003d - PC tru+0x31fa40 - ends at once in doppelganger mode; CM+0x1fc bit 0 + player event 0x3c on the PC).
//
// Switches [Reticle] TranslateRequest / TranslateRefill (default 1) read again at run time at most once per second;
// a site is hooked when its switch or [Reticle] Log is 1 at the start (0 = PC answer through the stub). [Reticle]
// Log=1: one line per change of a decision (the first 60 per site at LogLevel 1, then LogLevel 2), with counts.
const DWORD kRingSite = 0x0071e979;           // TU 0x823de47c
const DWORD kRingSiteCheck = 0x0071e923;
const char *const kRingSiteHex = "8bce e896e7ffff 8bbefc010000 8bd8 8bc7 c1e80a a801 895c240c 7527 a158dbfa00 "
                                 "8b8800050000 83b93401000004 7513 d9ee d89898070000 dfe0 f6c405 0f8b1b010000 85db "
                                 "0f84bc010000 8bce e85b35fdff 84c0 750e 8bd7 c1ea15 f6c201 0f84a3010000 8d442410 53 50";
const DWORD kRingEntry = 0x0071e716;          // after the foreign 5-byte jump at tru+0x31e710 (exe patch to 0x83dfd0)
const char *const kRingEntryHex = "a1b0dffa00 83ec44 53 56 8bf1 8b4804 8b11 837a0403 57 0f84dd040000 803de6b48a0000 "
                                  "0f84d0040000 8b86fc010000 c1e80b a801 0f84d3010000";
const DWORD kRefillSite = 0x0071f500;         // TU 0x823ee158
const DWORD kRefillCheck = 0x0071f4f4;
const char *const kRefillHex = "8b1558dbfa00 8b8a04050000 8b81fc010000 c1e815 a801 0f85a8070000 db4604 51 d91c24 "
                               "e8a333fdff 33c0";
const DWORD kRefillExit = 0x0071fcb9;         // pop edi; pop esi; xor eax,eax; pop ebx; mov esp,ebp; pop ebp; ret 4
const char *const kRefillExitHex = "5f 5e 33c0 5b 8be5 5d c20400";
const DWORD kRefillBody = 0x006f28c0;         // the PC's out-of-line rest of the refill (calls tru+0x2e6630 when full)
const char *const kRefillBodyHex = "c605afe8fa0001 f781fc01000000004000 7537 d9413c d8442404 d9593c 8b1564d7fa00 "
                                   "c605d8e8fa0000 d9413c d982d0020000 ded9 dfe0 f6c441 7a0e d982d0020000 d9593c "
                                   "e8263dffff d9413c a164d7fa00 d8b0d0020000 6a01 d91dd4e8fa00 e8abb00800";
const DWORD kFullFn = 0x006e6630;             // TU 0x823dfd98
const DWORD kFullSite = 0x006e6646;
const char *const kFullHex = "a164d7fa00 d980d0020000 8b81fc010000 8bd0 d9593c c1ea1b f6c201 7519 0d00004000 "
                             "8981fc010000 c605afe8fa0001 c605d8e8fa0000 c3";
const DWORD kFullNative = 0x00777a50;         // the second PC caller (script native: ecx = CM, jmp tru+0x2e6630)
const char *const kFullNativeHex = "a158dbfa00 8b8804050000 e9d0ebf6ff";
const DWORD kDgByteGetter = 0x00777dc0;       // larabase f36: the doppelganger byte [[0xfadb58]+0x1244]
const char *const kDgByteGetterHex = "a158dbfa00 8a8044120000 c3";

int g_retRequest = 1;                         // [Reticle] TranslateRequest
int g_retRefill = 1;                          // [Reticle] TranslateRefill
int g_retLog = 1;                             // [Reticle] Log
bool g_retHooked = false;
DWORD g_retSwitchTick = 0;
DWORD g_ringYes = 0x0071e987, g_ringNo = 0x0071eb2a;
DWORD g_refillGo = 0x0071f511, g_refillSkip = kRefillExit;
DWORD g_fullGo = 0x006e664e, g_fullRet = 0x006e6667;
volatile LONG g_retCalls[3];                  // ring request / refill gate / full test
volatile LONG g_retChanges[3];
int g_retLast[3] = {-1, -1, -1};              // last decision per site: 4 = switch off, else (doppelganger << 1) | answer

void ReticleReadSwitch() {
    if (!g_retHooked || !g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_retSwitchTick < 1000) return;
    g_retSwitchTick = now;
    const int r = GetPrivateProfileIntA("Reticle", "TranslateRequest", g_retRequest, g_iniPath) ? 1 : 0;
    const int f = GetPrivateProfileIntA("Reticle", "TranslateRefill", g_retRefill, g_iniPath) ? 1 : 0;
    if (r != g_retRequest)
        Log(1, "0.22 switch: [Reticle] TranslateRequest %d -> %d (read again from TruShadowPower.ini) - %s", g_retRequest,
            r, r ? "ring request by meter flag 2 in doppelganger mode as the TU" : "ring request by CM+0x1fc bit 21 (PC)");
    if (f != g_retRefill)
        Log(1, "0.22 switch: [Reticle] TranslateRefill %d -> %d (read again from TruShadowPower.ini) - %s", g_retRefill,
            f, f ? "adrenaline refill by meter flags 2 / 0x40 in doppelganger mode as the TU" : "refill by CM bits 21 / 27 (PC)");
    g_retRequest = r;
    g_retRefill = f;
}

int RetDoppelganger() {                       // TU: lbz rX, 0x1244([0x829892b0])
    __try {
        const BYTE *gt = GameTracker();
        return (gt && gt[0x1244] != 0) ? 1 : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

void RetNote(int site, int on, int dg, int answer, DWORD word) {
    const LONG n = InterlockedIncrement(&g_retCalls[site]);
    const int state = on ? (dg << 1) | answer : 4;
    if (!g_retLog || state == g_retLast[site]) return;
    g_retLast[site] = state;
    const LONG c = InterlockedIncrement(&g_retChanges[site]);
    const int level = c <= 60 ? 1 : 2;
    if (level > g_logLevel) return;
    static const char *const what[3] = {
        "ring request tru+0x31e979 (TU 0x823de47c)", "refill gate tru+0x31f500 (TU 0x823ee158)",
        "adrenaline-full test tru+0x2e6646 (TU 0x823dfd98)"};
    static const char *const tuTest[3] = {"meter flag 2", "meter flag 2", "meter flag 0x40"};
    static const char *const pcTest[3] = {"CM+0x1fc bit 21", "CM+0x1fc bit 21", "CM+0x1fc bit 27"};
    static const char *const yes[3] = {"RING requested (HUD group 12 via tru+0x3037d0)", "refill SKIPPED",
                                       "adrenaline active - bit 22 not set"};
    static const char *const no[3] = {"no ring", "refill runs", "bit 22 (0x400000) set"};
    Log(level, "0.22 reticle: %s - %s: %s = %d -> %s (meter flags 0x%03lx, CM+0x1fc 0x%08lx; call %ld, change %ld%s)",
        what[site], !on ? "[Reticle] switch 0, PC test" : dg ? "doppelganger mode, TU test" : "not in doppelganger mode",
        on && dg ? tuTest[site] : pcTest[site], answer, answer ? yes[site] : no[site], g_meter.flags, word, n, c,
        c == 60 ? "; further changes at LogLevel 2" : "");
}

// game thread, from RingStub: 1 = the third condition of the ring request holds
int __cdecl RingRequestBit(DWORD word) {
    ReticleReadSwitch();
    const int on = g_retRequest;
    const int dg = on ? RetDoppelganger() : 0;
    const int answer = dg ? static_cast<int>((g_meter.flags >> 1) & 1) : static_cast<int>((word >> 21) & 1);
    RetNote(0, on, dg, answer, word);
    return answer;
}

// game thread, from RefillGateStub: 1 = skip the refill
int __cdecl RefillGateBit(DWORD word) {
    ReticleReadSwitch();
    const int on = g_retRefill;
    const int dg = on ? RetDoppelganger() : 0;
    const int answer = dg ? static_cast<int>((g_meter.flags >> 1) & 1) : static_cast<int>((word >> 21) & 1);
    RetNote(1, on, dg, answer, word);
    return answer;
}

// game thread, from FullStub: 1 = adrenaline active (return without bit 22)
int __cdecl FullActiveBit(DWORD word) {
    ReticleReadSwitch();
    const int on = g_retRefill;
    const int dg = on ? RetDoppelganger() : 0;
    const int answer = dg ? static_cast<int>((g_meter.flags >> 6) & 1) : static_cast<int>((word >> 27) & 1);
    RetNote(2, on, dg, answer, word);
    return answer;
}

// jumped to from tru+0x31e979: edi = CM+0x1fc, ebx = the target (kept), esi = CM; continues at tru+0x31e987 (ring) or
// tru+0x31eb2a (none) with edx = word >> 21 as the original; eax / ecx restored, the FPU stack is empty
__declspec(naked) void RingStub() {
    __asm {
        push eax
        push ecx
        push edx
        push edi
        call RingRequestBit
        add esp, 4
        pop edx
        pop ecx
        mov edx, edi
        shr edx, 15h
        test eax, eax
        pop eax
        jz ring_no
        jmp dword ptr [g_ringYes]
    ring_no:
        jmp dword ptr [g_ringNo]
    }
}

// jumped to from tru+0x31f500 (ecx = CM, edx = [0xfadb58], esi = the message): skip -> tru+0x31fcb9, else
// tru+0x31f511; eax = word >> 21 as the original
__declspec(naked) void RefillGateStub() {
    __asm {
        push ecx
        push edx
        push dword ptr [ecx + 1fch]
        call RefillGateBit
        add esp, 4
        pop edx
        pop ecx
        push eax
        mov eax, [ecx + 1fch]
        shr eax, 15h
        test dword ptr [esp], 1
        lea esp, [esp + 4]
        jnz refill_skip
        jmp dword ptr [g_refillGo]
    refill_skip:
        jmp dword ptr [g_refillSkip]
    }
}

// jumped to from tru+0x2e6646 (ecx = CM, eax = edx = CM+0x1fc, CM+0x3c already = max, FPU empty): active ->
// tru+0x2e6667 (ret), else tru+0x2e664e (bit 22); edx = word >> 27 as the original
__declspec(naked) void FullStub() {
    __asm {
        push eax
        push ecx
        push eax
        call FullActiveBit
        add esp, 4
        mov edx, eax
        pop ecx
        pop eax
        push edx
        mov edx, eax
        shr edx, 1bh
        test dword ptr [esp], 1
        lea esp, [esp + 4]
        jnz full_ret
        jmp dword ptr [g_fullGo]
    full_ret:
        jmp dword ptr [g_fullRet]
    }
}

void PatchReticle() {
    const bool wantRing = g_retRequest || g_retLog, wantRefill = g_retRefill || g_retLog;
    if (!wantRing && !wantRefill) {
        Log(1, "0.22 reticle: [Reticle] TranslateRequest=0, TranslateRefill=0 and Log=0 - tru+0x31e979 / tru+0x31f500 / "
               "tru+0x2e6646 untouched (a later 1 needs a restart)");
        return;
    }
    if (!HexBytesAt(kDgByteGetter, kDgByteGetterHex)) {
        Log(0, "0.22 reticle: doppelganger byte getter tru+0x377dc0 does not match - ring request / refill left to the game");
        return;
    }
    bool ring = false, refill = false;
    if (wantRing) {
        if (!HexBytesAt(kRingSiteCheck, kRingSiteHex))
            Log(0, "0.22 reticle: ring request tru+0x31e923..0x31e98f does not match - ring request left to the game");
        else if (!HexBytesAt(kRingEntry, kRingEntryHex))
            Log(0, "0.22 reticle: playerDrawCombatLock entry tru+0x31e716 does not match - ring request left to the game");
        else if (!HexBytesAt(kAimHelper, kAimHelperHex))
            Log(0, "0.22 reticle: bit 9 / 10 helper tru+0x2f1ed0 does not match - ring request left to the game");
        else if (!WriteJumpN(kRingSite, reinterpret_cast<const void *>(&RingStub), 5))
            Log(0, "0.22 reticle: ring request not written (VirtualProtect %lu)", GetLastError());
        else
            ring = true;
    }
    if (wantRefill) {
        if (!HexBytesAt(kRefillCheck, kRefillHex) || !HexBytesAt(kRefillExit, kRefillExitHex))
            Log(0, "0.22 reticle: refill case tru+0x31f4f4 / exit tru+0x31fcb9 does not match - refill left to the game");
        else if (!HexBytesAt(kRefillBody, kRefillBodyHex))
            Log(0, "0.22 reticle: refill body tru+0x2f28c0 does not match - refill left to the game");
        else if (!HexBytesAt(kFullFn, kFullHex))
            Log(0, "0.22 reticle: adrenaline-full helper tru+0x2e6630 does not match - refill left to the game");
        else if (!HexBytesAt(kFullNative, kFullNativeHex))
            Log(0, "0.22 reticle: script native tru+0x377a50 (second caller of tru+0x2e6630) does not match - refill left "
                   "to the game");
        else if (!WriteJumpN(kRefillSite, reinterpret_cast<const void *>(&RefillGateStub), 6) ||
                 !WriteJumpN(kFullSite, reinterpret_cast<const void *>(&FullStub), 8))
            Log(0, "0.22 reticle: refill sites not written (VirtualProtect %lu)", GetLastError());
        else
            refill = true;
    }
    g_retHooked = ring || refill;
    if (ring)
        Log(1, "0.22 reticle: ring request tru+0x31e979 -> plugin - [Reticle] TranslateRequest %d (%s), log %d", g_retRequest,
            g_retRequest ? "TU 0x823de47c: in doppelganger mode meter flag 2 instead of CM+0x1fc bit 21" : "PC test",
            g_retLog);
    if (refill)
        Log(1, "0.22 reticle: refill tru+0x31f500 and adrenaline-full tru+0x2e6646 -> plugin - [Reticle] TranslateRefill "
               "%d (%s), log %d; tru+0x2e6630 is also the body of script native tru+0x377a50", g_retRefill,
            g_retRefill ? "TU 0x823ee158 / 0x823dfd98: in doppelganger mode meter flag 2 / 0x40 instead of bits 21 / 27"
                        : "PC tests", g_retLog);
    if (g_retHooked) Log(1, "0.22 reticle: switches read again at run time at most once per second");
}

// ================================================================================================================
// 0.23 (N2, testing / accessibility): [Meter] Infinite - the meter stays at max. Not a TU feature; the TU's meter code
// (tick, Drain, Refill, Start / Stop) is unchanged and runs as with a full meter: InfiniteHold (tick, before the button
// / drain / refill block) sets the value to tuning +0x10, Drain leaves it there. Read again at run time at most once
// per second from the pad poll (game thread, before the tick), also when it was 0 at the start - no game code is
// patched for it. One line per change, with what was held back while it was on.
DWORD g_infSwitchTick = 0;

void InfiniteReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_infSwitchTick < 1000) return;
    g_infSwitchTick = now;
    const int v = GetPrivateProfileIntA("Meter", "Infinite", g_infinite, g_iniPath) ? 1 : 0;
    if (v == g_infinite) return;
    if (v) {
        Log(1, "0.23 switch: [Meter] Infinite 0 -> 1 (read again from TruShadowPower.ini) - the meter is held at max: "
               "the tick fills it to tuning +0x10, every drain (tick, state 1018, TruShadowPowerMeterApi) leaves it at "
               "max; power use as with a full meter, no \"meter empty\" (meter %.1f, power %s, flags 0x%03lx)",
            g_meter.value, (g_meter.flags & 1) ? "on" : "off", g_meter.flags);
        g_infDrains = 0;
        g_infHeld = 0.0;
        g_infFills = 0;
    } else {
        Log(1, "0.23 switch: [Meter] Infinite 1 -> 0 (read again from TruShadowPower.ini) - the meter drains / refills "
               "again with the TU rates from %.1f (power %s); while on: %ld drain calls held at max (%.1f units not "
               "taken), %ld fills", g_meter.value, (g_meter.flags & 1) ? "on" : "off", g_infDrains, g_infHeld,
            g_infFills);
    }
    g_infinite = v;
}

// ---- meter interface (docs Befund-Schattenkampf.md section 5; version 1 = TruShadowCombat's proposal, version 2
// appends the HUD natives f70-f73 of larabase, TU 0x824aa060 / 0x824aa0a0 / 0x824aa120 / 0x824aa150, for a later HUD
// plugin - Plan-Nacht-Analysen-2026-11-03.md section 2). Fields are only appended; check version / size.
struct TruShadowPowerMeter {
    DWORD size;                           // sizeof this struct
    DWORD version;                        // 3 (0.12; 2 = 0.11)
    volatile DWORD *flags;                // TU meter +0x04 (1 active, 2 strike, 4 strike look, 8 value >= tuning +0x2c, ..)
    float *value;                         // +0x08
    float *startValue;                    // +0x0c
    float (*request)[2];                  // +0x40: 7 time-scale request slots {player, world}
    void(__cdecl *selector)();            // 0x823d7520
    void(__cdecl *drain)(float amount);   // 0x823d8380
    // version 2
    float *delay;                         // +0x10 refill delay (frames)
    void(__cdecl *delayStart)();          // f70 0x824aa060: +0x10 = tuning +0x24
    char(__cdecl *strikeReady)();         // f71 0x824aa0a0: flag 8 and value > tuning +0x70 x 0.01 x tuning +0x10
    char(__cdecl *canStart)();            // f72 0x824aa120: CanStart 0x823d8120 (clears flag 0x200 above +0x28)
    float(__cdecl *delayLeft)();          // f73 0x824aa150: max(+0x10, 0.0)
    // version 3 (0.12, docs Befund-Schattenkampf.md section 5 "Version 3 request")
    volatile LONG *gt1280;                // TU-only gameTracker+0x1280: move steps of states 244 (TruShadowCombat) / 245,
                                          // read by condition 1048
    // version 4 (0.14)
    void(__cdecl *strikeLookOff)();       // TU 0x823d9050 (only with meter flag 4 = [Look] StrikeLook=1; else nothing):
                                          // the strike tick 0x823d8d18 / end 0x823d9210 call it next to their drain
};

void __cdecl ApiSelector() { Selector(); }
// the tuning the meter runs with (TU 0x82415518; the plugin's last tick, incl. the file copy with [Meter] Fallback=1)
void __cdecl ApiDrain(float amount) {
    const BYTE *tuning = g_tuning;
    if (tuning) Drain(tuning, amount);
}
void __cdecl ApiDelayStart() {                                 // f70
    const BYTE *tuning = g_tuning;
    if (tuning) g_meter.delay = Tune(tuning, 0x24);
}
char __cdecl ApiStrikeReady() {                                // f71
    const BYTE *tuning = g_tuning;
    if (!GameTracker() || !tuning || !(g_meter.flags & 8)) return 0;
    float high = Tune(tuning, 0x70) * kPercent;                // fmuls f11 = +0x70 x [0x820536ec]
    high = high * Tune(tuning, kTuneMax);                       // fmuls f0 = f11 x +0x10
    return g_meter.value > high ? 1 : 0;
}
char __cdecl ApiCanStart() {                                   // f72
    return CanStart(g_tuning) ? 1 : 0;
}
float __cdecl ApiDelayLeft() {                                 // f73
    return kZero < g_meter.delay ? g_meter.delay : kZero;
}
void __cdecl ApiStrikeLookOff() {                              // 0.14: 0x823d9050
    StrikeLookOff();
}

const TruShadowPowerMeter g_meterApi = {
    sizeof(TruShadowPowerMeter), 4, reinterpret_cast<volatile DWORD *>(&g_meter.flags), &g_meter.value,
    &g_meter.startValue, g_meter.request, &ApiSelector, &ApiDrain, &g_meter.delay, &ApiDelayStart, &ApiStrikeReady,
    &ApiCanStart, &ApiDelayLeft, &g_gt1280, &ApiStrikeLookOff};

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruShadowPower.ini", dir);
    g_legacyPadStart = GetPrivateProfileIntA("ShadowPower", "LegacyPadStart", 0, ini);
    g_gameInput = GetPrivateProfileIntA("ShadowPower", "GameInput", 0, ini);
    g_adrenalineMode = GetPrivateProfileIntA("Look", "AdrenalineMode", 1, ini);
    g_condEnabled = GetPrivateProfileIntA("Conditions", "Enabled", 1, ini);
    g_statesEnabled = GetPrivateProfileIntA("States", "Enabled", 1, ini);
    g_cond1046 = GetPrivateProfileIntA("Conditions", "Cond1046", 1, ini);
    g_cond1055 = GetPrivateProfileIntA("Conditions", "Cond1055", 1, ini);
    g_enabled = GetPrivateProfileIntA("ShadowPower", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowPower", "LogLevel", 1, ini);
    g_buttons = static_cast<WORD>(GetPrivateProfileIntA("ShadowPower", "Buttons", 0x0300, ini));
    g_hudFeed = GetPrivateProfileIntA("Meter", "HudBar", 1, ini);
    g_fallback = GetPrivateProfileIntA("Meter", "Fallback", 1, ini);
    g_lookEnabled = GetPrivateProfileIntA("Look", "Enabled", 1, ini);
    g_lookMessages = GetPrivateProfileIntA("Look", "Messages", 1, ini);
    g_lookScreen = GetPrivateProfileIntA("Look", "ScreenEffect", 1, ini);
    g_gp7Enabled = GetPrivateProfileIntA("Look", "GlobalParams7", 1, ini);
    g_cineParamEnabled = GetPrivateProfileIntA("Look", "CinematicParam", 1, ini);
    g_state2102Enabled = GetPrivateProfileIntA("States", "State2102", 1, ini);
    g_loopSound = GetPrivateProfileIntA("Sound", "LoopSound", 0, ini);           // 0.14, all default 0
    g_moveEvents = GetPrivateProfileIntA("Look", "MoveEvents", 0, ini);
    g_cameraFlag = GetPrivateProfileIntA("Look", "CameraFlag", 1, ini);         // 0.20: default 1 = TU (0.14-0.19: 0)
    g_strikeLook = GetPrivateProfileIntA("Look", "StrikeLook", 0, ini);
    // 0.15, default 0; 0.25: key ClothTuTimeStep, the old name TuTimeStep is read when the new key is missing
    g_clothTimeStep = GetPrivateProfileIntA("Cloth", "ClothTuTimeStep",
                                            GetPrivateProfileIntA("Cloth", "TuTimeStep", 0, ini), ini);
    g_menuInput = GetPrivateProfileIntA("ShadowPower", "MenuInput", 1, ini);    // 0.17, default 1 (0 = 0.16)
    strcpy_s(g_iniPath, sizeof(g_iniPath), ini);                                 // 0.18: run-time read
    g_k11 = GetPrivateProfileIntA("Adrenaline", "Translate", 1, ini) ? 1 : 0;    // 0.18 (K11), default 1
    g_k11Log = GetPrivateProfileIntA("Adrenaline", "Log", 1, ini) ? 1 : 0;
    g_slot6 = GetPrivateProfileIntA("TimeScale", "TranslateSlot6", 1, ini) ? 1 : 0;   // 0.21 (X23), default 1
    g_retRequest = GetPrivateProfileIntA("Reticle", "TranslateRequest", 1, ini) ? 1 : 0;   // 0.22 (K-5), default 1
    g_retRefill = GetPrivateProfileIntA("Reticle", "TranslateRefill", 1, ini) ? 1 : 0;     // 0.22 (K-5), default 1
    g_retLog = GetPrivateProfileIntA("Reticle", "Log", 1, ini) ? 1 : 0;
    g_infinite = GetPrivateProfileIntA("Meter", "Infinite", 0, ini) ? 1 : 0;          // 0.23 (N2), default 0, live
    // 0.24 (N6), default 0; 0.25: key CameraTuTimeStep, the old name TuTimeStep is read when the new key is missing
    g_camTimeStep = GetPrivateProfileIntA("Camera", "CameraTuTimeStep",
                                          GetPrivateProfileIntA("Camera", "TuTimeStep", 0, ini), ini) ? 1 : 0;
    g_camTrace = g_camTraceIni = GetPrivateProfileIntA("Camera", "Trace", 0, ini) ? 1 : 0;     // 0.25, default 0, live
    g_camTraceMs = GetPrivateProfileIntA("Camera", "TraceInterval", 50, ini);
    if (g_camTraceMs < 10) g_camTraceMs = 10;
    if (g_camTraceMs > 5000) g_camTraceMs = 5000;
    g_dgSettings = GetPrivateProfileIntA("Camera", "DoppelgangerSettings", 0, ini);           // 0.25, default 0
    if (g_dgSettings < 0 || g_dgSettings > 2) g_dgSettings = 0;
    g_shakeTimeStep = GetPrivateProfileIntA("Camera", "ShakeTuTimeStep", 0, ini) ? 1 : 0;     // 0.27, default 0
    g_playerTimeStep = GetPrivateProfileIntA("Player", "TuTimeStep", 0, ini) ? 1 : 0;         // 0.27, default 0
    _snprintf_s(g_camTracePath, sizeof(g_camTracePath), _TRUNCATE, "%sTruCam.log", dir);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowPower.log", dir);
    ReadOptions(dir);
    InitFileTuning();
    Log(1, "TruShadowPower 0.27 loaded (enabled %d, buttons 0x%04x, HUD bar %d, fallback %d, conditions %d, states %d, "
        "condition 1046 %d, condition 1055 %d, look %d, legacy pad start %d, game input %d, adrenaline mode %d, "
        "screen effect %d, GlobalParams7 %d, cinematic param %d, state 2102 %d; 0.14: loop sound %d, move events %d, "
        "camera flag %d, strike look %d; 0.15: cloth TU time step %d; 0.17: menu input %d; 0.18: adrenaline K11 %d, "
        "log %d; 0.21: time-scale slot 6 %d; 0.22: reticle request %d, refill %d, log %d; 0.23: infinite meter %d; "
        "0.24: camera TU time step %d; 0.25: camera trace %d (%d ms), doppelganger camera settings %d; 0.27: shake TU "
        "time step %d, player TU time step %d)",
        g_enabled, g_buttons, g_hudFeed, g_fallback, g_condEnabled, g_statesEnabled, g_cond1046, g_cond1055,
        g_lookEnabled, g_legacyPadStart, g_gameInput, g_adrenalineMode, g_lookScreen, g_gp7Enabled, g_cineParamEnabled,
        g_state2102Enabled, g_loopSound, g_moveEvents, g_cameraFlag, g_strikeLook, g_clothTimeStep, g_menuInput, g_k11,
        g_k11Log, g_slot6, g_retRequest, g_retRefill, g_retLog, g_infinite, g_camTimeStep, g_camTrace, g_camTraceMs,
        g_dgSettings, g_shakeTimeStep, g_playerTimeStep);
    if (!g_enabled) { Log(1, "disabled by TruShadowPower.ini - nothing hooked"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not hooked", base, kImageBase); return; }
    if (!BytesAt(kCallSite, kCallBytes, sizeof(kCallBytes))) {
        Log(0, "pad poll call at 0x%08lx does not match (other tru.exe build?) - not hooked", kCallSite);
        return;
    }
    if (!BytesAt(kSetWorld, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetWorld + 0x1d, kWorldRamp, 5) ||
        !BytesAt(kSetPlayer, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetPlayer + 0x1d, kPlayerRamp, 5)) {
        Log(0, "time-scale setters at 0x%08lx / 0x%08lx do not match - not hooked", kSetWorld, kSetPlayer);
        return;
    }
    if (!BytesAt(kFrameDivSite, kFrameDivBytes, sizeof(kFrameDivBytes)) ||
        !BytesAt(kFrameDivConst, kFrameDivValue, sizeof(kFrameDivValue)) ||
        !BytesAt(kFrameStoreSite, kFrameStoreBytes, sizeof(kFrameStoreBytes))) {
        Log(0, "frame time store at 0x%08lx does not match - not hooked", kFrameStoreSite);
        return;
    }
    g_tableOk = BytesAt(kFindObject, kFindObjectBytes, sizeof(kFindObjectBytes)) &&
                BytesAt(kFindObjectLoop, kFindObjectLoopBytes, sizeof(kFindObjectLoopBytes));
    if (!g_tableOk) Log(0, "object table lookup at 0x%08lx does not match - tuning only from the fallback", kFindObject);
    g_hudOk = BytesAt(kHudValueGetter, kHudValueBytes, sizeof(kHudValueBytes)) &&
              BytesAt(kHudGroup, kHudGroupBytes, sizeof(kHudGroupBytes)) &&
              BytesAt(kHudUpdate, kHudUpdateBytes, sizeof(kHudUpdateBytes));
    if (!g_hudOk) Log(0, "HUD code at 0x%08lx / 0x%08lx / 0x%08lx does not match - meter runs without the HUD bar",
                      kHudValueGetter, kHudGroup, kHudUpdate);
    Log(3, "code checks passed (call site, setters, frame time, object table %d, HUD %d)", g_tableOk, g_hudOk);
    // 0.8: player event walker (TU 0x82418158) for the look events of Start / Stop
    g_lookOk = HexBytesAt(kPlayerEvent, kPlayerEventHex) && HexBytesAt(kPlayerEventType, kPlayerEventTypeHex) &&
               HexBytesAt(kPlayerEventCall, kPlayerEventCallHex);
    if (!g_lookEnabled)
        Log(1, "shadow look: off ([Look] Enabled=0) - no player events at start / stop");
    else if (!g_lookOk)
        Log(0, "shadow look: player event walker at 0x%08lx does not match - look not translated", kPlayerEvent);
    else
        Log(1, "shadow look: player event walker tru+0x318780 verified - start fires 0x89 0x32 (0x81) 0x87/0x88, stop "
               "0x33 0x7e/0x82 (TU 0x823d7d40 / 0x823d7fb8)");
    g_msgOk = HexBytesAt(kInstWalk, kInstWalkHex) && HexBytesAt(kInstNext, kInstNextHex) &&
              HexBytesAt(kInstQuery, kInstQueryHex) && HexBytesAt(kInstWake, kInstWakeHex);
    if (g_lookEnabled && g_lookMessages)
        Log(g_msgOk ? 1 : 0, g_msgOk ? "shadow look: instance list [0x%08lx] / query +0x11c / wake tru+0x1b2de0 verified - "
                                       "start / stop send 0x1f4 / 0x1f5 to the instances answering 0x172"
                                     : "shadow look: instance list code at 0x%08lx does not match - messages 0x1f4 / 0x1f5 "
                                       "not sent", g_msgOk ? kInstanceHead : kInstWalk);
    else if (g_lookEnabled)
        Log(1, "shadow look: messages 0x1f4 / 0x1f5 off ([Look] Messages=0)");
    // 0.10: the full-screen effect of event 0x32 (record 14 -> material 20744), report / remove
    g_fxOk = HexBytesAt(kEffectWalk, kEffectWalkHex) && HexBytesAt(kFx85Create, kFx85CreateHex) &&
             HexBytesAt(kFx85Material, kFx85MaterialHex) && HexBytesAt(kFx85Draw, kFx85DrawHex) &&
             HexBytesAt(kEffectKill, kEffectKillHex);
    if (g_lookEnabled && g_lookOk)
        Log(g_fxOk ? 1 : 0, g_fxOk ? "look screen effect: effect list [0x%08lx] / type-0x85 effect tru+0x135cc0 / draw "
                                     "tru+0x1469a0 verified - %s"
                                   : "look screen effect: effect list code at 0x%08lx does not match - not reported%s",
            g_fxOk ? kEffectHead : kEffectWalk,
            g_fxOk ? (g_lookScreen ? "the effect of event 0x32 is reported (needs the translated material 20744 of "
                                     "tree dlc_test50l_look, else the screen turns black)"
                                   : "the effect of event 0x32 is REMOVED ([Look] ScreenEffect=0)") : "");
    MeterInit();
    Log(1, "meter interface: TruShadowPowerMeterApi version 4 exported (flags / value / start value / requests, "
           "selector 0x823d7520, drain 0x823d8380; v2: delay, HUD natives f70-f73; v3: gameTracker+0x1280 steps; v4: "
           "strikeLookOff 0x823d9050)");
    g_tuStatesOk = true;
    for (const auto &c : kTuBlocks)
        if (!HexBytesAt(c.address, c.bytes)) {
            Log(0, "0.5 building block at 0x%08lx does not match - TU states / 1048 / 2401 / activities not registered",
                c.address);
            g_tuStatesOk = false;
            break;
        }
    RegisterLaraConditions();
    RegisterLaraStates();
    if (g_cond1046) Patch1046();
    // 0.9: TU gates of the tick / start and the game input chain
    g_gatesOk = HexBytesAt(kCinematic, kCinematicHex) && HexBytesAt(kBlockGetter, kBlockGetterHex) &&
                HexBytesAt(kBlockSetter, kBlockSetterHex) && HexBytesAt(kBlockSetterCall, kBlockSetterCallHex) &&
                HexBytesAt(kGtxFlagsCheck, kGtxFlagsCheckHex);
    g_inputOk = HexBytesAt(kInputCheck, kInputCheckHex);
    PatchGlobalParams7();               // 0.11 / 0.12 (needs g_tableOk for the tuning lookup, g_gatesOk for the cinematic test)
    if (g_legacyPadStart)
        Log(1, "tick: LEGACY 0.8 path ([ShadowPower] LegacyPadStart=1) - power in every level, no cinematic gates");
    else if (g_gatesOk)
        Log(1, "tick: TU path - only with the doppelganger flag (TU 0x824128a8); cinematic tru+0x53f00, block byte "
               "0x%08lx, game flag 0x%08lx bit 0 and health gt+0x628 gate the power as TU 0x823d7a10 / 0x823d7d40",
            kBlockByte, kGtxFlags);
    else
        Log(0, "tick: TU path, but the cinematic / block byte / game flag code does not match - those gates are off "
               "(the doppelganger gate stays)");
    if (g_gameInput && !g_inputOk) {
        Log(0, "GameInput=1 but the input chain at 0x%08lx does not match - buttons from the pad poll", kInputCheck);
        g_gameInput = 0;
    } else if (!g_legacyPadStart) {
        Log(1, "buttons: %s", g_gameInput ? "game input records +0x1a70 / +0x1b30 & 4 (TU 0x823d7b6c, GameInput=1)"
                                          : "pad poll LB / RB (XInput); the TU reads the game records +0x1a70 / +0x1b30");
    }
    if (g_legacyPadStart)
        Log(1, "adrenaline look: off with LegacyPadStart=1 (meter flag 0x40 comes from the TU tick only)");
    else if (g_lookEnabled)
        PatchAdrenalineMode();
    else
        Log(1, "adrenaline look: off ([Look] Enabled=0)");
    // 0.14: each part only when its switch is 1 (default 0: nothing checked, nothing patched - 0.13 behaviour)
    if (g_legacyPadStart && (g_loopSound || g_moveEvents)) {
        Log(1, "0.14 loop sound / move events: off with LegacyPadStart=1 (they belong to the TU tick)");
        g_loopSound = g_moveEvents = 0;
    }
    CheckLoopSound();
    CheckMoveEvents();
    CheckCameraFlag();
    PatchStrikeLook();
    PatchClothTimeStep();               // 0.15: only with [Cloth] ClothTuTimeStep=1 (independent of the doppelganger flag)
    CheckTickGate();                    // 0.16: main state / level change tests of the tick (player tests always on)
    CheckPadPoll();                     // 0.17: [ShadowPower] MenuInput (before the hook thread reads g_menuInputOk)
    PatchK11();                         // 0.18: K11 - adrenaline tick / bar skipped in doppelganger mode as the TU
    PatchSlot6();                       // 0.21: gamebase natives 23 / 24 -> request slot 6 in doppelganger mode as the TU
    PatchReticle();                     // 0.22: ring request / adrenaline refill by the meter flags in doppelganger mode
    PatchCameraTimeStep();              // 0.24: only with [Camera] CameraTuTimeStep=1 (independent of the doppelganger flag)
    PatchDgSettings();                  // 0.25: only with [Camera] DoppelgangerSettings=1|2 (after the 0.11 / 0.24 checks)
    PatchTimeStep027();                 // 0.27: only with [Camera] ShakeTuTimeStep=1 / [Player] TuTimeStep=1
    Log(1, "0.25 camera trace: [Camera] Trace %d at the start (read again at run time at most once per second; %s, "
           "every %d ms; read only)", g_camTrace, g_camTracePath, g_camTraceMs);
    Log(1, "0.23 infinite meter: [Meter] Infinite %d at the start - %s; read again at run time at most once per second "
           "(no game code patched)", g_infinite,
        g_infinite ? "the meter is held at max (tick fill + drain at max), power use as with a full meter"
                   : "the meter drains / refills with the TU rates");
    HANDLE thread = CreateThread(nullptr, 0, HookThread, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
    else Log(0, "CreateThread failed (%lu) - not hooked", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_stop = 1;
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruShadowPowerVersion() {
    return "TruShadowPower 0.27 (translated TU meter with the TU tick gates, tick only with a player in a level, LB / RB "
           "only as the game gets them (TruMenu's TruMenuPadBlock + a second pad read, no re-wrap of the pad chain, "
           "withheld buttons ignored until released), "
           "CombatManager::Update skips the adrenaline tick / bar in doppelganger mode as the TU (K11), Lara "
           "conditions 1046 / 1047 / 1048-1056 / 2401, states 243 / 245 / 1018 / 2102, activities 1009 / 1039, shadow look = TU player events of start / stop, "
           "adrenaline look = meter flag 0x40 / camera mode 0x34, look screen effect report / switch, GlobalParams[7], "
           "InstanceParams[1] in cinematics, meter interface TruShadowPowerMeterApi v4, camera flag of the start "
           "(camera bit 2, reader tru+0x1e5e8e), gamebase natives 23 / 24 -> time-scale request slot 6 in doppelganger "
           "mode (TU 0x824a3238 / 0x824a32f0), combat reticle request and adrenaline refill by the meter flags in "
           "doppelganger mode (TU 0x823de47c / 0x823ee158 / 0x823dfd98); switches default off: loop sound, move events 0x83 / 0x84, strike "
           "look 0x823d8a80 / 0x823d9050, cloth TU time step 0x82278120, camera TU time step 0x822ad048 / 0x822beeb8 / "
           "0x822c39c8 / 0x822c79d0, doppelganger camera settings 0x822bc198 / 0x822c61d8 (DTP 21237 / 21238, mode 2 "
           "with a stand-in: TU delay / ramp + 21237's per-mode tables), camera shake TU time step 0x822af4d8, player "
           "TU time step 0x8240cf88 / 0x8240e3a0 / 0x82411850 / 0x82411c30 / 0x82419c98, infinite meter [Meter] Infinite (live, not a TU feature), camera trace TruCam.log "
           "(read only))";
}

// 0.11: the TU meter object for other plugins (TruShadowCombat: condition 538, the shadow strike) - interface version
// 4 (1 = TruShadowCombat's proposal in docs Befund-Schattenkampf.md section 5, 2 adds the HUD natives f70-f73, 3 gt1280,
// 4 strikeLookOff). Pointers stay valid for the life of the process (the meter
// is re-initialised in place per game tracker). Call from the game thread only (as the meter itself).
extern "C" __declspec(dllexport) const void *__cdecl TruShadowPowerMeterApi() {
    return &g_meterApi;
}
