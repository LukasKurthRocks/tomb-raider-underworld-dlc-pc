// TruDlc2Player.asi - DLC 2 "Lara's Shadow": make the doppelganger the player object, as the Xbox title update (TU)
// does, for the PC tru.exe (Steam, image base 0x400000).
//
// How the Xbox TU gets object 857 doppelganger_casual (and with it object 858 player_tru_dlc2_extension) loaded:
//   1. data: the mission screen starts dlc_level2_start without costume selection (TU generalbank script 134; PC
//      script 104 - tools/dlc2_player_fix.py);
//   2. exe, TU 0x82297d30 GAMELOOP_LevelLoadAndInit (retail 0x8229b3f0 = PC tru+0x1de2b0): after the costume name is
//      chosen (chosen costume, else the unit's default - dlc_level2_start: object 11 lara_doppelganger), the TU added
//          if (strcmp(name, "lara_doppelganger") == 0) { name = "doppelganger_casual"; costume id = id of name; }
//      before GAMELOOP_RequestPlayerCostumeLoad(name) (TU 0x82297a88);
//   3. exe data, TU player type table 0x8275ae38 (records {name, init, f2..f6}; an object's type is the record whose
//      name equals the object's name, PC tru+0x1bf0e0): the TU added the record "doppelganger_casual" {init
//      DoppelgangerInit 0x82412c48, f2..f6 the player's}. The PC table (0x8aba28) has no such record - an object of
//      that name would get type -1, i.e. no player functions at all;
//   4. TU 0x82412c48 DoppelgangerInit: base player init (TU 0x82412ca0 = PC tru+0x321f80), then if the instance flag
//      0x20000 at +0x14 is clear, gameTracker+0x1244 = 1 ("DoppelgangerInit finished");
//   5. object 857's child id list (chart DTP +0x48) holds 858, so the object loader loads the extension with it (data;
//      tools/dlc2_player_fix.py ids fixes two base ids of that list).
//
// This plugin translates 2-4:
//   * costume: a 6-byte detour at tru+0x1de3a3 (push esi; call print - all costume paths meet there with esi = the
//     name, right before the id lookup tru+0x1bf770 and the costume load request tru+0x1c1760) applies the TU's
//     substitution; the PC then computes the id from the new name exactly as the TU's 0x82297a88 does.
//   * type table: a copy of the PC table with the TU's record appended after the last PC record (PC indices 0-38
//     unchanged; the TU inserted it at 35 and shifted four debug records - the PC code keeps its own indices), the 11
//     code operands that address the table pointed at the copy (tru+0x1bf00a .. 0x1c547b, all checked first).
//   * DoppelgangerInit: base init tru+0x321f80, then the flag; the plugin keeps the flag (export
//     TruDlc2PlayerDoppelganger) for later readers (dlc2data f0, TU-only code - not on PC) and, since 0.4, also stores
//     it into the PC game tracker +0x1244 as the TU does (0.1-0.3 assumed the PC tracker had no such byte - wrong, see
//     0.4 below).
// Every patched byte is compared with the expected code / data first; on a mismatch that part is left alone and the
// reason is logged. Options: TruDlc2Player.ini, log TruDlc2Player.log.
//
// 0.2 (2026-11-02, docs Befund-TU-Funktionen L4): the doppelganger flag is reset like the TU resets it. The TU never
// stores 0 into gameTracker+0x1244 (its only writer is DoppelgangerInit's `stb 1` at 0x82412c84); the reset is the
// allocation: every player init that takes the alloc path (TU 0x82412ca0, instance +0x14 bit 0x20000 clear) builds a
// new tracker with the constructor 0x82413878 = memset(tracker, 0, 0x1320) and publishes it (0x82413354). The PC does
// the same (constructor tru+0x31c2d0 = memset 0x1310, called only at tru+0x322445, published at tru+0x32247b) - but up
// to 0.3 the flag lived only in this plugin (g_doppelganger) and was never cleared: after DLC 2 a
// DLC 1 / main-game level in the same session still answered 1 (live 2026-11-02). FlagReset redirects the constructor
// call at tru+0x322445 to TrackerConstructed, which runs the constructor and then clears the plugin's flag - the
// plugin's copy of the TU memset. DoppelgangerInit runs the base init (which constructs the tracker) before it sets 1,
// so the DLC 2 player still ends with 1, as on the TU. Export TruDlc2PlayerTrackerGeneration counts the constructed
// trackers (other plugins re-initialise their copies of tracker-owned TU objects, e.g. the meter +0x508).
//
// 0.3 (2026-11-03, test paket06 F12, docs Befund-Kostuem-Reset-DLC1): chosen-costume reset outside DLC 2. The game's
// state save (PC tru+0x155cb1, TU 0x821ff10c / 0x821ff118) stores the current costume into the chosen costume
// (game data +0x20c), so after DLC 2 it holds 857 doppelganger_casual (the TU stores 11 lara_doppelganger there - its
// save maps the one to the other - which the TU level load turns back into doppelganger_casual: the same result). The
// TU never loads another unit with that word: every mission start goes through MainTracker_UILoadLevel (TU 0x8247d818)
// with the 4th argument 1, which calls the new-game reset 0x821fe9a8 at 0x8247d95c (+0x210 / +0x20e / +0x20c = 0 at
// 0x821feb2c..0x821feb34; PC tru+0x156abe). The PC's direct level change (TruMenu level.load, the debug path) skips
// that reset, so DLC 1 loaded the doppelganger (live 2026-11-03 21:07). CostumeReset: when the level load's costume is
// the DLC 2 player (lara_doppelganger / doppelganger_casual) but the unit's own default costume (the level load's
// fallback, tru+0x1de379 / TU 0x82297e7c: stream unit data +0x70 -> u16 +0x294) is not lara_doppelganger - i.e. the
// unit is not a DLC 2 unit (data: dlc_level2_start / dlc_yggdrasil_* 11, DLC 1 units 25) - the plugin does the TU
// mission start's costume part: +0x210 / +0x20e / +0x20c = 0 and the level load takes the unit default, as it does
// with a chosen costume of 0. Not a TU code path (the TU has no direct level change), its outcome only.
//
// 0.4 (2026-11-04 night, docs Befund-Schattenleiste-HUD.md "Nacht 04.11.", F17): DoppelgangerInit writes the TU flag
// into the game tracker itself. Up to 0.3 the comment said "the PC game tracker has no +0x1244" - wrong: the PC
// tracker (constructor tru+0x31c2d0, memset 0x1310) has the byte, and two retail readers use it exactly as the TU:
// larabase native f36 (PC tru+0x39a290 -> tru+0x377dc0 `mov eax,[0FADB58h]; mov al,[eax+1244h]`; TU binder entry 36
// = 0x824a1188, the same function as dlc2data f0; retail 0x824a4260) and the player code tru+0x3200df (= retail
// 0x8240b7b4 = TU 0x8240e5f4, identical). The TU's DoppelgangerInit stores `stb 1, 0x1244([0x829892b0])` at
// 0x82412c84; [0x829892b0] = PC [0xfadb58] (kTrackerPublish). Without that store larabase f36 answers 0 on PC and the
// TU HUD script (generalbank 37 function 15, `op69 larabase f36; op50; op64 -> +0x180c`) never enters its shadow-meter
// block (larabase f70-f73, red / pulse). TrackerFlag=1 makes the store; the PC's memset in the tracker constructor
// clears it with every new tracker, as the TU's does. g_doppelganger (export) stays as before.
//
// 0.5 (2026-11-04, docs Befund-Menue-Dlc2Player-0411b.md; Befund-Kostuem-Reset-DLC1.md section 7): the TU's costume
// mapping 857 doppelganger_casual <-> 11 lara_doppelganger in the four places the TU added it - only all four
// together (one alone would load lara_doppelganger as the player). `[Costume] TuMapping=1` (default 0 = as 0.4, nothing
// patched). Translated 1:1 from the TU disassembly (work/asi/combat02/analysis/tu_all.txt); the name -> id lookup is
// TU 0x822809e0 = PC tru+0x1bf770 (same table walk over the object names, [0x829bffc8] / [0xdb94d0]):
//   * state save TU 0x821fef58 (PC tru+0x155be0), TU 0x821ff0dc..0x821ff118:
//       if (id("doppelganger_casual") == current) +0x20c = id("lara_doppelganger"); else +0x20c = current
//     PC site tru+0x155cb1 `mov ax,[0E7F1C8h]; mov [edx+20Ch],ax` (retail 0x82201080 = the plain store);
//   * state load TU 0x821ff1e0 (PC tru+0x156e90), TU 0x821ff518..0x821ff540:
//       v = (s16) +0x20c; current = (v == id("lara_doppelganger")) ? id("doppelganger_casual") : v
//     PC site tru+0x156fbd `movsx ecx,word [eax+20Ch]; mov [0E7F1C8h],ecx` (retail 0x82201468 = the plain load);
//   * player spawn TU 0x822973b0 (PC tru+0x1d40c0), TU 0x822976b0..0x822976d8, after the spawn record (PC esi) got
//     its costume: if (u16 record+0x50 == id("lara_doppelganger")) { current = id("doppelganger_casual");
//     record+0x50 = that } - PC site tru+0x1d42e9 (after the print of the position record, before `test edi,edi`);
//   * player spawn TU 0x82297f10 (PC tru+0x1d4340, the costume switch's spawn, record 0xe7f2a0), TU
//     0x8229803c..0x82298064: the same test on +0x50 (0xe7f2f0) after the unit-default fallback - PC site tru+0x1d4469
//     (where both paths of the fallback meet, before the spawn call tru+0x1bd080).
// Not part of the mapping, not ported: the TU load also stores the old current costume into altPlayerObjectID
// (TU 0x821ff514 `stw r11, 0x144(r29)` = PC [0xe7f1cc]; read and cleared by the TU-changed 0x82475628), and TU spawn
// 0x822973b0 got a validity test + unit-default fallback before the mapping (0x82297688..0x822976ac; retail and PC
// have none there). With the mapping a PC save written in DLC 2 holds 11 like the TU's; the level load turns 11 into
// doppelganger_casual (0.1) and outside DLC 2 the 0.3 reset zeroes it (both names are handled there).
//
// 0.6 (2026-11-11, Q7, docs Befund-Kostuemauswahl-DLC2-1111.md): DLC 2 started from the game (pause menu -> DLC ->
// mission screen -> yes / no dialog) without the outfit / weapon selection, as the TU. That start is not script code:
// the dialog's accept handler ScriptDialogYesNo::RegisterAcceptChanges (TU 0x8247f0c0, retail 0x824796a0, PC tru+0x37e790
// - xbox_pc_map "string, verified") switches on the pending action [0xfae918]; case 8 (jump table tru+0x37e97c entry 7)
// starts the level named by the dialog. Retail 0x82479884..0x824798a8 and PC tru+0x37e8a9..0x37e8e3 (UILoadLevel
// inlined with the 4th argument 0: selection byte [0xfae8d9] = 1, game data +0x90 = 0 twice, tru+0x1dfb20(name, 0)):
//     MainTracker_UILoadLevel(&name, 1, 0, 0)          -> always the selection (main state 9), chosen costume kept
// TU 0x8247f2c8..0x8247f510:
//     (tailoring reset to Medium, see below), print "Attempting to load level: %s",
//     sel = name in {dlc_level2_start, dlc_level3_start, dlc_level4_start, dlc_level5_start, dlc_level6_start}
//           (string table 0x820760f8..0x82076148, byte compare = strcmp) ? 0 : 1
//     MainTracker_UILoadLevel(&name, sel, 0, 1)        -> 4th argument 1: the new-game block with reset 0x821fe9a8
// MainTracker_UILoadLevel is unchanged by the TU (TU 0x8247d818 = retail 0x82477dc0, moved-equal) and is PC uigamedata
// f27 tru+0x37e170 (its arg-4 = 0 tail tru+0x37e411..0x37e434 is exactly the inlined PC case 8). DialogStart replaces
// the 35 bytes tru+0x37e8c0..0x37e8e3 (whole instructions, no branch into them: tools/pe_patch_site_check.py) with a
// jump to AcceptStartLevel, which calls f27(&name, sel, 0, 1) as the TU does; the PC's own case-8 tail (vcall +0x148,
// stdscreenmgr f7 / f19) follows unchanged. With sel 0 and the reset the level load takes the unit default (dlc_level2
// _start: lara_doppelganger -> doppelganger_casual by 0.1), as the main-menu start (script 104 as the TU) already does.
// Not ported in 0.6: the TU's tailoring reset in the same case and the TU-only `stb 0, 0x1f94(0x829be044)` after the
// case - both translated by 0.7 ([Mission] DialogDifficulty, below).
//
// 0.7 (2026-11-11, Q33, docs Befund-DLC-Schwierigkeit-1111.md): the rest of the TU's case 8, behind
// [Mission] DialogDifficulty (default 0 = as 0.6; needs DialogStart=1, whose detour it extends).
//   a) TU 0x8247f2d8..0x8247f3a0 "Resetting player tailoring to Medium difficulty.": for EnemyHP / AmmoAdj / PlayerHP /
//      SavingGrabAdj 0x822a2b50(name, old value, 1) + game data ([0x829be4a8]) +0x3efa0 / a4 / ac / b0 = 1, then
//      +0x3efb4 = 1. That is word for word the body of the TU's tailoring setters 0x824be628 / 680 / 6d8 / 730 / 788
//      (script natives (8,120) f6..f10; retail 0x824ba640 / 698 / 6f0 / 748 / 7a0, moved-equal, the same offsets) with
//      the value 1. Their PC partners (xbox_pc_map "string, anchor", strings EnemyHP 0x85ddf8 ... SavingGrabAdj
//      0x85de14) are tru+0x2e75a0 / 0x2e75e0 / 0x2e7620 / 0x2e7660 / 0x2e76a0 (natives f6..f10 of the class registered
//      by tru+0x3aede0): `v <= 2 ? (0x6457a0(name, old, v), [[0xc59264]+0x3ef98 / 9c / a4 / a8 / ac] = v)`. So
//      0x822a2b50 = GameMetrics SendSettingChangedMetric (TU: two "%d" strings, then 0x822a2c38 builds a metric
//      "Setting" / "Prev" / "New", error "[GameMetrics] SendSettingChangedMetric NewMetric NULL") = PC tru+0x2457a0, the
//      folded empty function (`ret`, 2143 callers) - metrics are compiled out of the PC build. The plugin calls the
//      five PC setters with 1 in the TU's order, before f27 (as the TU: reset, print, rule, UILoadLevel); 1 is also
//      the PC's own default (tru+0x2e7500 sets all five to 1).
//   b) TU 0x8247f570..0x8247f57c `stb 0, 0x1f94(0x829be044)` = byte 0x829bffd8 (retail 0x829bdf54 + 0x1f94 =
//      0x829bfee8), after the case's tail. Retail writers 0x8229d6d0 (1) / 0x8229d5d0 (0) = PC tru+0x1d4780 / 0x1d4700
//      (xbox_pc_map verified; the same state +0xbb = 6 / 0 and flag masks) store it through tru+0x1bfdf0(b) =
//      `[0xdb94de] = b` (TruMenu 0.10.4: the pause menu's render-clock hold, read only by tru+0x1bf840: dt 0 while
//      set). The plugin redirects the tail's last call tru+0x37e8f9 (call tru+0xbe5e0 = retail `bl 0x821669e0` at
//      0x824798dc, inlined by the TU at 0x8247f558..0x8247f56c) to a stub that makes that call and then
//      tru+0x1bfdf0(0), the TU's store right after it.
//   Not translated (no plugin site): the TU's main-menu start (script 134 function 9, no game in progress) also calls
//   natives (8,120) f6..f10 with 1; the PC script 104 function 9 (pipeline S104) has no such calls - a data change,
//   since Q40 the opt-in rule tu134_tailoring of tools/generalbank_pc_build.py (build --tailoring).
//
// 0.8 (2026-11-11, Q40, docs Befund-Hauptmenue-Schwierigkeit-1111.md): the same TU-only render-hold store after cases
// 4 and 6 of RegisterAcceptChanges, behind [Mission] DialogHoldClear (default 0 = as 0.7, nothing patched; independent
// of DialogStart / DialogDifficulty). TU vs retail vs PC, instruction by instruction (jump tables TU 0x8247f118, retail
// 0x82479700, PC tru+0x37e97c; entries 3 / 5):
//   case 4 (opened by script 7 f8 with action 4 on TU and PC): TU 0x8247f1b4..0x8247f1cc = retail 0x82479788..0x824797a0
//      ([0x829ca6d9] = 1, [0x829ca6d3] = 3, bl 0x8247e000 = retail 0x82478590 = PC tru+0x37e460) = PC tru+0x37e7f0..0x37e7fe
//      ([0xfae8dc] = 1, [0xfae8da] = 3, call tru+0x37e460; the PC's extra call tru+0x83810 before them is PC-only),
//      then TU 0x8247f1d0..0x8247f1dc `stb 0, 0x1f94(0x829be044)` - not in retail / PC. The plugin redirects the call
//      tru+0x37e7fe (5 bytes, next jmp tru+0x37e94a) to a stub: tru+0x37e460, then tru+0x1bfdf0(0).
//   case 6 (level "ee_01" / "Ee_01" -> selection 0, else 1): TU 0x8247f20c..0x8247f2a4 = retail 0x824797c4..0x82479870
//      (two compares, MainTracker_UILoadLevel(&name, sel, 1, 0); the TU joins retail's two call sites into one) = PC
//      tru+0x37e808..0x37e895 (UILoadLevel inlined twice: [0xfae8d9] = sel, game data +0x90 = 0, tru+0x1dfb20(name, 1)),
//      then TU 0x8247f2a8..0x8247f2b4 `stb 0, 0x1f94(0x829be044)` after the call - not in retail / PC. The plugin
//      redirects both calls tru+0x37e860 / tru+0x37e88d (each followed by add esp,8; jmp tru+0x37e94a) to a cdecl stub:
//      tru+0x1dfb20(name, arg), then tru+0x1bfdf0(0).
//   Every site: whole instruction, no branch into it (tools/pe_patch_site_check.py), bytes checked before the write.
//   case 9 needs nothing: TU 0x8247f584..0x8247f5c0 = retail 0x824798e4..0x824798f8 with the two getters inlined
//   ([0x829ca6d9] = 1; [0x829be084] vcall +8 = retail bl 0x821666c0; [0x829be07c] vcall +0xc = retail bl 0x821669a0)
//   = PC tru+0x37e900..0x37e911 ([0xfae8dc] = 1; tru+0xbe560 = [0xa13f58] vcall +8; tru+0xbdd90 = [0xa13f50] vcall +0xc).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "../TruLog.h"                      // Q107: date + time in every log line, session header
extern "C" __declspec(dllexport) const char *TruDlc2PlayerVersion();  // Q107 session header (defined at the end)

namespace {

const DWORD kImageBase = 0x00400000;

// ---- costume substitution (TU 0x82297d30) ----
const DWORD kLevelLoadInit = 0x005de2b0;   // PC GAMELOOP_LevelLoadAndInit
const BYTE kLevelLoadInitBytes[] = {0x55, 0x8b, 0x6c, 0x24, 0x08, 0x55, 0xe8, 0xe5, 0x74, 0x06, 0x00};
const DWORD kCostumeSite = 0x005de3a3;     // push esi; call 6457A0h | push esi; call 5BF770h; push eax; mov [0E7F1C8h],eax
const BYTE kCostumeSiteBytes[] = {0x56, 0xe8, 0xf7, 0x73, 0x06, 0x00, 0x56, 0xe8, 0xc1, 0x13, 0xfe, 0xff,
                                  0x50, 0xa3, 0xc8, 0xf1, 0xe7, 0x00};
const DWORD kCostumeBack = 0x005de3a9;     // continue at the id lookup
const DWORD kPrint = 0x006457a0;           // debug print (a plain ret in the retail build)
const DWORD kGameData = 0x00c59264;        // pointer: +0x1f4 mode, +0x20c / +0x210 chosen costume (object id)
const DWORD kCostumeId = 0x00e7f1c8;       // costume object id written by the PC after the lookup (TU 0x82efb598)
const char kFromName[] = "lara_doppelganger";
const char kToName[] = "doppelganger_casual";

// ---- player type table (TU 0x8275ae38, record 35 "doppelganger_casual") ----
const DWORD kTypeTable = 0x008aba28;       // 39 records {name, init, f2..f6} + a zero record
const int kTypeCount = 39;
struct TypeRec { const char *name; DWORD init, f[5]; };
struct Operand { DWORD at, value; };       // imm32 operands that address the table (instruction operand address)
const Operand kTypeOperands[] = {
    {0x005bf00a, 0x008aba34}, {0x005bf03a, 0x008aba40}, {0x005bf06a, 0x008aba30}, {0x005bf09a, 0x008aba38},
    {0x005bf0ca, 0x008aba3c}, {0x005bf123, 0x008aba28}, {0x005bf12a, 0x008aba28}, {0x005bf14f, 0x008aba28},
    {0x005bf157, 0x008aba28}, {0x005bf169, 0x008aba28}, {0x005c547b, 0x008aba2c}};
const int kTypeOperandCount = sizeof(kTypeOperands) / sizeof(kTypeOperands[0]);
const DWORD kBaseInit = 0x00721f80;        // PC player init (TU 0x82412ca0): push ebp; mov ebp,esp; and esp,-16
const BYTE kBaseInitBytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x24, 0x8b, 0x45, 0x0c};
const DWORD kPlayerFn[5] = {0x007228e0, 0x006ee4b0, 0x00709fd0, 0x0071ffe0, 0x0071bfa0};   // f2..f6 of every player record

// ---- 0.2: new game tracker = flag 0 (TU constructor 0x82413878 / publish 0x82413354) ----
const DWORD kTrackerCtor = 0x0071c2d0;     // thiscall(tracker): push ebx/esi/edi; memset(this, 0, 0x1310); ...; ret
const char *const kTrackerCtorHex = "53 56 57 6810130000 33ff 8bf1 57 56 e88d7e0f00";
const DWORD kTrackerCtorCall = 0x00722445; // the only caller: lea ecx,[edi+40h]; call 0x71c2d0; mov [esp+0Ch],edi
const DWORD kTrackerCtorCallCheck = 0x00722442;
const char *const kTrackerCtorCallHex = "8d4f40 e8869effff 897c240c";
const DWORD kTrackerPublish = 0x0072247b;  // add edi,40h (before); mov [0FADB58h],edi
const char *const kTrackerPublishHex = "83c740 893d58dbfa00";   // [0xfadb58] = TU 0x829892b0

// ---- 0.3: chosen-costume reset outside DLC 2 (TU mission start: UILoadLevel 0x8247d95c -> reset 0x821fe9a8) ----
const DWORD kUnitDefault = 0x005de379;     // the level load's unit default: mov ecx,[0E7F148h]; push ecx; call 5C1B50h;
                                           // mov edx,[eax+8]; mov eax,[edx+70h]; movzx eax,word [eax+294h]; mov ecx,[0DB94D0h]
const char *const kUnitDefaultHex = "8b0d48f1e700 51 e8cb37feff 8b5008 8b4270 0fb78094020000 8b0dd094db00";
const DWORD kUnitId = 0x00e7f148;          // current stream unit id
const DWORD kStreamUnit = 0x005c1b50;      // cdecl(unit id) -> stream unit entry (0xd8 bytes, +8 unit data) or 0
const char *const kStreamUnitHex = "56 8b742408 33c0 33d2 b940abdb00";
const DWORD kNames = 0x00db94d0;           // pointer: +0 count, name of object id n at +n*8 (validator tru+0x1c54e0)

// ---- 0.5: TU costume mapping 857 <-> 11 (save / load / two spawns), [Costume] TuMapping ----
const DWORD kNameLookup = 0x005bf770;      // cdecl(name) -> object id (index + 1) or 0 = TU 0x822809e0
const char *const kNameLookupHex = "8b0dd094db00 56 33f6 3931 57 7e27 8b7c240c 8b44f108";
struct MapSite {
    const char *what; DWORD at, back; const char *hex;   // patched bytes (whole instructions)
    DWORD ctxAt; const char *ctxHex;                    // a neighbouring instruction that pins the registers' roles
};
const MapSite kMapSites[] = {
    // TU 0x821ff0dc: the state save's store of the current costume into the chosen costume
    {"state save", 0x00555cb1, 0x00555cbe, "66a1c8f1e700 6689820c020000", 0x00555cab, "8b156492c500"},
    // TU 0x821ff518: the state load's chosen costume -> current costume (eax = game data)
    {"state load", 0x00556fbd, 0x00556fca, "0fbf880c020000 890dc8f1e700", 0x00556fb8, "a16492c500"},
    // TU 0x822976b0: spawn record esi (+0x50 = [0xe7f1c8] at 0x5d41c7..0x5d41d6), after `push edi; call print`
    {"player spawn", 0x005d42e9, 0x005d42ee, "83c404 85ff", 0x005d41c4, "8d34c0 0fb705c8f1e700 c1e604 6689443e50 03f7"},
    // TU 0x8229803c: costume switch spawn, record 0xe7f2a0 (+0x50 = 0xe7f2f0), after the unit-default fallback
    {"switch spawn", 0x005d4469, 0x005d4471, "6a00 56 68a0f2e700", 0x005d445e, "a3c8f1e700 66a3f0f2e700"},
};
const int kMapSiteCount = sizeof(kMapSites) / sizeof(kMapSites[0]);
const DWORD kSpawnRecordB = 0x00e7f2a0;    // TU 0x83208430 (spawn 0x82297f10's static record)
const DWORD kSpawnCall = 0x005d4471;       // call 0x5bd080 (TU 0x82270fa0) right after the switch-spawn site
const char *const kSpawnCallHex = "e80a8cfeff";

// ---- 0.6: dialog accept case 8 as the TU (RegisterAcceptChanges TU 0x8247f2c8..0x8247f510), [Mission] DialogStart ----
const DWORD kAcceptFn = 0x0077e790;        // RegisterAcceptChanges: mov eax,[0FAE914h]; sub esp,8; push ebx/ebp/esi/edi
const char *const kAcceptFnHex = "a114e9fa00 83ec08 53 55 56 57";
const DWORD kAcceptSwitch = 0x0077e7b4;    // mov eax,[0FAE918h]; mov ebp,[esp+14h]; add eax,-1; xor ebx,ebx; cmp eax,0Ah;
const char *const kAcceptSwitchHex = "a118e9fa00 8b6c2414 83c0ff 33db 83f80a 0f877a010000 ff24857ce97700";  // ja; jmp [tbl]
const DWORD kAcceptTable = 0x0077e97c;     // jump table, entry 7 = case 8
const DWORD kCase8 = 0x0077e8a9;           // cmp ebp,ebx; je out; mov edx,[esp+10h]; mov eax,[0C59268h]; mov [0FAE914h],edx
const char *const kCase8Hex = "3beb 0f8499000000 8b542410 a16892c500 891514e9fa00";
const DWORD kCase8Site = 0x0077e8c0;       // the inlined UILoadLevel(&name, 1, 0, 0), 35 bytes, whole instructions
const char *const kCase8SiteHex = "c605d9e8fa0001 899890000000 8b0d6492c500 53 55 899990000000 e84012e6ff 83c408";
const DWORD kCase8Back = 0x0077e8e3;       // call 0x5a48d0 (the PC's own case-8 tail)
const char *const kCase8BackHex = "e8e85fe2ff";
const DWORD kUiLoadLevel = 0x0077e170;     // uigamedata f27 = MainTracker_UILoadLevel (TU 0x8247d818 = retail 0x82477dc0)
const char *const kUiLoadLevelHex = "55 8bec 83e4f8 81ec54020000 807d0c00 8b4508 8b08 53 0f95c2 807d1400 56 57 894c2448 "
                                    "8815d9e8fa00 0f8472020000";
const DWORD kUiLoadTail = 0x0077e411;      // f27's 4th-argument-0 path = the PC's inlined case 8
const char *const kUiLoadTailHex = "8b0d6892c500 33c0 898190000000 8b156492c500 8b4c2448 898290000000 8b4510 50 51 "
                                   "e8e716e6ff";
const DWORD kSelectByte = 0x00fae8d9;      // costume / weapon selection (TU 0x829ca6d2)
// TU string table 0x820760f8 .. 0x82076148, in the TU's order
const char *const kNoSelectUnits[] = {"dlc_level2_start", "dlc_level3_start", "dlc_level4_start", "dlc_level5_start",
                                      "dlc_level6_start"};
typedef void(__cdecl *UiLoadLevelFn)(const DWORD *args, int select, int arg3, int newGame);

// ---- 0.7: the rest of the TU's case 8 (tailoring reset 0x8247f2d8..0x8247f3a0, store 0x8247f570..0x8247f57c),
// [Mission] DialogDifficulty ----
struct TailorSetter {
    const char *name;                      // the metric name the setter passes (TU 0x82072374 ...), or the native
    DWORD fn, pcOff, tuOff;                // PC setter, PC game-data field, TU game-data field
    const char *hex;                       // the whole PC setter (byte check)
};
const TailorSetter kTailor[] = {
    // TU 0x8247f2e8..0x8247f324 (setter 0x824be628, native f6)
    {"EnemyHP", 0x006e75a0, 0x3ef98, 0x3efa0,
     "56 8b742408 83fe02 7726 a16492c500 8b8898ef0300 56 51 68f8dd8500 e8dfe1f5ff 8b156492c500 83c40c 89b298ef0300 5e c3"},
    // TU 0x8247f30c..0x8247f34c (setter 0x824be680, native f7)
    {"AmmoAdj", 0x006e75e0, 0x3ef9c, 0x3efa4,
     "56 8b742408 83fe02 7726 a16492c500 8b889cef0300 56 51 6800de8500 e89fe1f5ff 8b156492c500 83c40c 89b29cef0300 5e c3"},
    // TU 0x8247f334..0x8247f374 (setter 0x824be6d8, native f8)
    {"PlayerHP", 0x006e7620, 0x3efa4, 0x3efac,
     "56 8b742408 83fe02 7726 a16492c500 8b88a4ef0300 56 51 6808de8500 e85fe1f5ff 8b156492c500 83c40c 89b2a4ef0300 5e c3"},
    // TU 0x8247f35c..0x8247f39c (setter 0x824be730, native f9)
    {"SavingGrabAdj", 0x006e7660, 0x3efa8, 0x3efb0,
     "56 8b742408 83fe02 7726 a16492c500 8b88a8ef0300 56 51 6814de8500 e81fe1f5ff 8b156492c500 83c40c 89b2a8ef0300 5e c3"},
    // TU 0x8247f384..0x8247f3a0 (setter 0x824be788, native f10: no metric)
    {"native f10", 0x006e76a0, 0x3efac, 0x3efb4, "8b442404 83f802 770c 8b0d6492c500 8981acef0300 c3"},
};
const int kTailorCount = sizeof(kTailor) / sizeof(kTailor[0]);
const int kTailorMedium = 1;               // TU li r5,1 / li r31,1 ("Medium"); the PC default (tru+0x2e7500)
const DWORD kMetricStub = 0x006457a0;      // PC partner of TU 0x822a2b50 (SendSettingChangedMetric): `ret` (folded)
const char *const kMetricStubHex = "c3 cc";
const DWORD kTailCall = 0x0077e8f9;        // case-8 tail: call 0x4be5e0; jmp 0x77e94a (TU store after the inlined call)
const char *const kTailCallHex = "e8e2fcd3ff eb4a";
const DWORD kTailCallee = 0x004be5e0;      // mov ecx,[0A13F50h]; mov eax,[ecx]; mov edx,[eax+10h]; jmp edx
const char *const kTailCalleeHex = "8b0d503fa100 8b01 8b5010 ffe2";
const DWORD kHoldSet = 0x005bfdf0;         // cdecl(BYTE b): [0xdb94de] = b (retail stb 0x829bfee8, TU 0x829bffd8)
const char *const kHoldSetHex = "8a442404 a2de94db00 c3";
const DWORD kHoldByte = 0x00db94de;
typedef void(__cdecl *SetterFn)(int);
typedef void(__cdecl *VoidFn)();
typedef void(__cdecl *HoldSetFn)(BYTE);

// ---- 0.8: the TU's render-hold store after cases 4 and 6 (TU 0x8247f1dc / 0x8247f2b4), [Mission] DialogHoldClear ----
const DWORD kCase4 = 0x0077e7eb;           // table entry 3: call 0x483810; [0xfae8dc] = 1; [0xfae8da] = 3; call 0x77e460
const char *const kCase4Hex = "e82050d0ff c605dce8fa0001 c605dae8fa0003";
const DWORD kCase4Call = 0x0077e7fe;       // call 0x77e460; jmp 0x77e94a (TU bl 0x8247e000 at 0x8247f1cc, then the store)
const char *const kCase4CallHex = "e85dfcffff e942010000";
const DWORD kCase4Callee = 0x0077e460;     // TU 0x8247e000 = retail 0x82478590 (xbox_pc_map verified): call 0x4be580; ...
const char *const kCase4CalleeHex = "e81b01d4ff e8f600d4ff 8b0d20e9fa00";
const DWORD kCase6 = 0x0077e808;           // table entry 5: cmp ebp,ebx; je out; mov ecx,[esp+10h]; mov [0FAE914h],ecx
const char *const kCase6Hex = "3beb 0f843a010000 8b4c2410 890d14e9fa00";
struct LoadSite { DWORD at; const char *hex; const char *what; };
const LoadSite kCase6Calls[] = {           // the two inlined UILoadLevel(&name, sel, 1, 0) of case 6 (sel 1 / sel 0)
    {0x0077e860, "e8bb12e6ff 83c408 e9dd000000", "sel 1 (not ee_01)"},
    {0x0077e88d, "e88e12e6ff 83c408 e9b0000000", "sel 0 (ee_01 / Ee_01)"}};
const DWORD kLevelRequest = 0x005dfb20;    // cdecl(name, BYTE arg) - the call of f27's 4th-argument-0 tail
const char *const kLevelRequestHex = "53 8a5c240c 84db 56 b8d0498500";
typedef void(__cdecl *LevelRequestFn)(const char *, int);

// options (TruDlc2Player.ini, section [Dlc2Player])
int g_enabled = 1, g_logLevel = 1, g_costume = 1, g_typeRecord = 1, g_flagReset = 1, g_costumeReset = 1;
int g_trackerFlag = 1;                     // 0.4: DoppelgangerInit also stores [[0xfadb58]]+0x1244 = 1 (TU 0x82412c84)
int g_tuMapping = 0;                       // 0.5: [Costume] TuMapping - the TU's 857 <-> 11 in save / load / spawns
volatile LONG g_mapCount = 0;              // 0.5: mappings done (each one logged)
int g_dialogStart = 1;                     // 0.6: [Mission] DialogStart - dialog accept case 8 as the TU
volatile LONG g_dialogStarts = 0;          // 0.6: case-8 starts done (each one logged)
int g_dialogDifficulty = 0;                // 0.7: [Mission] DialogDifficulty - tailoring reset + hold store of case 8
bool g_difficultyOk = false;               // 0.7: setters checked and the tail call redirected
int g_dialogHoldClear = 0;                 // 0.8: [Mission] DialogHoldClear - the TU's hold store after cases 4 / 6
volatile LONG g_caseHolds = 0;             // 0.8: hold clears done in cases 4 / 6 (each one logged)
const DWORD kTrackerPtr = 0x00fadb58;      // TU 0x829892b0 (the game tracker / player state block)
const DWORD kTrackerFlag = 0x1244;         // TU flag byte, read by larabase f36 tru+0x377dc0 and tru+0x3200df
const DWORD kF36Body = 0x00777dc0;         // larabase f36 body: mov eax,[0FADB58h]; mov al,[eax+1244h]; ret
const char *const kF36BodyHex = "a158dbfa00 8a8044120000 c3";
const DWORD kFlagReader = 0x007200d6;      // player code: mov ecx,[0FADB58h]; add esp,4; cmp byte [ecx+1244h],0
const char *const kFlagReaderHex = "8b0d58dbfa00 83c404 80b94412000000";
bool g_trackerFlagOk = false;
bool g_resetOk = false;                    // 0.3: unit-default code checked
volatile LONG g_trackers = 0;              // trackers constructed since load (export TruDlc2PlayerTrackerGeneration)

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
TypeRec g_types[kTypeCount + 2];           // PC records, the TU record, the zero record
volatile LONG g_doppelganger = 0;          // TU gameTracker+0x1244
volatile LONG g_costumeCalls = 0;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[600];
    int n = TruLogStamp(line, sizeof(line));     // Q107: "YYYY-MM-DD HH:MM:SS.mmm "
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        TruLogSessionStart(f, "TruDlc2Player", TruDlc2PlayerVersion());
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

bool ReadDword(DWORD address, DWORD *value) {
    __try {
        *value = *reinterpret_cast<const DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadWord(DWORD address, WORD *value) {
    __try {
        *value = *reinterpret_cast<const WORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool WriteWord(DWORD address, WORD value) {
    __try {
        *reinterpret_cast<volatile WORD *>(address) = value;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool WriteByte(DWORD address, BYTE value) {
    __try {
        *reinterpret_cast<volatile BYTE *>(address) = value;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool SafeName(const char *p, char *out, size_t size) {
    __try {
        size_t i = 0;
        for (; i + 1 < size && p[i]; ++i) out[i] = p[i];
        out[i] = 0;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
        return false;
    }
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(reinterpret_cast<void *>(address), bytes, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(address), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), length);
    return true;
}

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[64];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

// ---------------------------------------------------------------------------------------------------------------
// 0.3: the unit default costume exactly as the level load computes it when no chosen costume applies (tru+0x1de379,
// TU 0x82297e7c): stream unit of [0xe7f148] (tru+0x1c1b50) -> unit data +8 -> +0x70 -> u16 +0x294 = object id, the
// name from the object-name table [0xdb94d0] (id 1..count, as the validator tru+0x1c54e0 accepts it)
typedef DWORD(__cdecl *StreamUnitFn)(DWORD);
bool UnitDefault(DWORD *unit, WORD *id, const char **name) {
    DWORD entry = 0, data = 0, p = 0, names = 0, count = 0, nm = 0;
    *unit = 0; *id = 0; *name = nullptr;
    if (!ReadDword(kUnitId, unit)) return false;
    __try {
        entry = reinterpret_cast<StreamUnitFn>(kStreamUnit)(*unit);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    if (!entry || !ReadDword(entry + 8, &data) || !data || !ReadDword(data + 0x70, &p) || !p || !ReadWord(p + 0x294, id))
        return false;
    if (!*id || !ReadDword(kNames, &names) || !names || !ReadDword(names, &count) || *id > count ||
        !ReadDword(names + *id * 8, &nm) || !nm)
        return false;
    *name = reinterpret_cast<const char *>(nm);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// costume: TU 0x82297d30, the added name test before GAMELOOP_RequestPlayerCostumeLoad
extern "C" const char *__cdecl ChooseCostume(const char *name) {
    LONG call = InterlockedIncrement(&g_costumeCalls);
    char shown[64];
    SafeName(name ? name : "", shown, sizeof(shown));
    DWORD game = 0;
    WORD mode = 0, chosen0 = 0, chosen1 = 0;
    if (ReadDword(kGameData, &game) && game) {
        ReadWord(game + 0x1f4, &mode);
        ReadWord(game + 0x20c, &chosen0);
        ReadWord(game + 0x210, &chosen1);
    }
    const char *result = name;
    // 0.3: the DLC 2 player costume in a unit that is not a DLC 2 unit = the chosen costume left over from DLC 2 (the
    // state save copied 857 into +0x20c); the TU's mission start would have zeroed it (UILoadLevel -> 0x821fe9a8)
    if (g_costumeReset && g_resetOk && name && (strcmp(shown, kFromName) == 0 || strcmp(shown, kToName) == 0)) {
        DWORD unit = 0;
        WORD def = 0;
        const char *defName = nullptr;
        char defShown[64];
        if (!UnitDefault(&unit, &def, &defName)) {
            Log(0, "level load %ld: costume \"%s\" - unit default of unit %lu not readable, chosen costume kept", call,
                shown, unit);
        } else {
            SafeName(defName, defShown, sizeof(defShown));
            if (strcmp(defShown, kFromName) != 0) {
                bool cleared = game && WriteWord(game + 0x210, 0) && WriteWord(game + 0x20e, 0) &&
                               WriteWord(game + 0x20c, 0);
                if (cleared) {
                    result = defName;
                    Log(1, "level load %ld: costume \"%s\" (chosen +0x20c %u / +0x210 %u) in unit %lu whose default is "
                           "\"%s\" (%u, not %s = no DLC 2 unit): chosen costume +0x210 / +0x20e / +0x20c = 0 as the TU's "
                           "mission start (UILoadLevel 0x8247d95c -> reset 0x821fe9a8), unit default loaded",
                        call, shown, chosen0, chosen1, unit, defShown, def, kFromName);
                } else {
                    Log(0, "level load %ld: costume \"%s\" in unit %lu (default \"%s\"): game data 0x%08lx not writable "
                           "- chosen costume kept", call, shown, unit, defShown, game);
                }
            } else {
                Log(2, "level load %ld: costume \"%s\" in unit %lu, default \"%s\" (DLC 2 unit) - kept", call, shown,
                    unit, defShown);
            }
        }
    }
    if (g_costume && result == name && name && strcmp(shown, kFromName) == 0) result = kToName;
    char to[64] = "";
    if (result != name) SafeName(result, to, sizeof(to));
    Log(1, "level load %ld: costume \"%s\"%s%s (game data +0x1f4 %u, chosen +0x20c %u / +0x210 %u)", call, shown,
        result != name ? " -> " : "", to, mode, chosen0, chosen1);
    return result;
}

__declspec(naked) void CostumeDetour() {
    __asm {
        pushad
        push esi
        call ChooseCostume
        add esp, 4
        mov [esp + 4], eax        // saved esi in the pushad frame
        popad
        push esi                  // the two replaced instructions: push esi; call print
        mov eax, kPrint
        call eax
        mov eax, kCostumeBack     // eax is overwritten by the id lookup that follows
        jmp eax
    }
}

bool PatchCostume() {
    if (!BytesAt(kLevelLoadInit, kLevelLoadInitBytes, sizeof(kLevelLoadInitBytes)) ||
        !BytesAt(kCostumeSite, kCostumeSiteBytes, sizeof(kCostumeSiteBytes))) {
        Log(0, "costume: GAMELOOP_LevelLoadAndInit at 0x%08lx / 0x%08lx does not match - not patched", kLevelLoadInit,
            kCostumeSite);
        return false;
    }
    // 0.3: the reset reads the unit default the way the level load does - its code and the stream-unit lookup checked
    if (g_costumeReset) {
        g_resetOk = HexBytesAt(kUnitDefault, kUnitDefaultHex) && HexBytesAt(kStreamUnit, kStreamUnitHex);
        if (!g_resetOk)
            Log(0, "costume reset: unit default code 0x%08lx / stream unit lookup 0x%08lx does not match - reset off "
                   "(after DLC 2 a direct level change keeps the doppelganger)", kUnitDefault, kStreamUnit);
    }
    BYTE jmp[6] = {0xe9, 0, 0, 0, 0, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(&CostumeDetour) - (kCostumeSite + 5);
    memcpy(jmp + 1, &rel, 4);
    if (!WriteCode(kCostumeSite, jmp, sizeof(jmp))) { g_resetOk = false; return false; }
    Log(1, "costume: \"%s\" -> \"%s\" at level load (detour at 0x%08lx)", kFromName, kToName, kCostumeSite);
    if (g_resetOk)
        Log(1, "costume reset: a level load of \"%s\" / \"%s\" in a unit whose default costume is not \"%s\" (no DLC 2 "
               "unit) zeroes the chosen costume and takes the unit default, as the TU's mission start (0x821fe9a8)",
            kFromName, kToName, kFromName);
    else if (!g_costumeReset)
        Log(1, "costume reset: off ([Dlc2Player] CostumeReset=0) - after DLC 2 a direct level change keeps the "
               "doppelganger");
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// DoppelgangerInit (TU 0x82412c48), called by the object init (PC tru+0x1c5489) as init(instance, 0E7F088h)
typedef void(__cdecl *InitFn)(void *, void *);
extern "C" void __cdecl DoppelgangerInit(void *instance, void *arg) {
    reinterpret_cast<InitFn>(kBaseInit)(instance, arg);
    DWORD flags = 0;
    if (ReadDword(reinterpret_cast<DWORD>(instance) + 0x14, &flags) && !(flags & 0x20000)) {
        // 0.4: TU 0x82412c70..0x82412c84 `lwz r11, [0x829892b0]; stb 1, 0x1244(r11)` = PC [[0xfadb58]]+0x1244 = 1
        DWORD tracker = 0;
        bool stored = false;
        if (g_trackerFlagOk && ReadDword(kTrackerPtr, &tracker) && tracker)
            stored = WriteByte(tracker + kTrackerFlag, 1);
        if (InterlockedExchange(&g_doppelganger, 1) == 0)
            Log(1, "DoppelgangerInit finished (instance 0x%08lx)%s", reinterpret_cast<DWORD>(instance),
                !g_trackerFlagOk ? "" : stored ? " - game tracker +0x1244 = 1 (TU 0x82412c84; larabase f36 now answers 1)"
                                               : " - game tracker +0x1244 NOT written (no tracker at [0xfadb58])");
        else if (g_trackerFlagOk && !stored)
            Log(0, "DoppelgangerInit: game tracker +0x1244 not written (tracker 0x%08lx)", tracker);
    }
}

// 0.4: check the two PC readers of the tracker byte (so the store means what the TU's means)
void CheckTrackerFlag() {
    if (!g_trackerFlag) {
        Log(1, "tracker flag: off ([Dlc2Player] TrackerFlag=0) - game tracker +0x1244 stays 0 (larabase f36 answers 0, "
               "the TU HUD shadow-meter block is skipped)");
        return;
    }
    if (!HexBytesAt(kF36Body, kF36BodyHex) || !HexBytesAt(kFlagReader, kFlagReaderHex)) {
        Log(0, "tracker flag: larabase f36 body 0x%08lx / reader 0x%08lx does not match - +0x1244 not written",
            kF36Body, kFlagReader);
        return;
    }
    g_trackerFlagOk = true;
    Log(1, "tracker flag: DoppelgangerInit also stores game tracker [0x%08lx]+0x%lx = 1 as the TU (0x82412c84); readers "
           "larabase f36 0x%08lx and the player code 0x%08lx verified; the tracker constructor's memset clears it",
        kTrackerPtr, kTrackerFlag, kF36Body, kFlagReader);
}

bool PatchTypeTable() {
    if (!BytesAt(kBaseInit, kBaseInitBytes, sizeof(kBaseInitBytes))) {
        Log(0, "type table: player init 0x%08lx does not match - not patched", kBaseInit);
        return false;
    }
    const TypeRec *t = reinterpret_cast<const TypeRec *>(kTypeTable);
    int n = 0;
    for (; n <= kTypeCount && t[n].name; ++n) {
        char nm[40];
        SafeName(t[n].name, nm, sizeof(nm));
        if (strcmp(nm, kToName) == 0) { Log(0, "type table: \"%s\" already present - not patched", kToName); return false; }
    }
    char last[40];
    SafeName(t[kTypeCount - 1].name, last, sizeof(last));
    if (n != kTypeCount || strcmp(last, "lara_placeholder") != 0) {
        Log(0, "type table at 0x%08lx: %d records, last \"%s\" (expected 39, lara_placeholder) - not patched", kTypeTable,
            n, last);
        return false;
    }
    // the player records (e.g. 2 lara_casual) carry the init / f2..f6 the TU record uses
    if (t[2].init != kBaseInit || memcmp(t[2].f, kPlayerFn, sizeof(kPlayerFn)) != 0) {
        Log(0, "type table: record 2 is not the player record expected - not patched");
        return false;
    }
    for (int i = 0; i < kTypeOperandCount; ++i) {
        DWORD v = 0;
        if (!ReadDword(kTypeOperands[i].at, &v) || v != kTypeOperands[i].value) {
            Log(0, "type table: operand at 0x%08lx is 0x%08lx, expected 0x%08lx - not patched", kTypeOperands[i].at, v,
                kTypeOperands[i].value);
            return false;
        }
    }
    memcpy(g_types, t, sizeof(TypeRec) * kTypeCount);
    g_types[kTypeCount].name = kToName;
    g_types[kTypeCount].init = reinterpret_cast<DWORD>(&DoppelgangerInit);
    memcpy(g_types[kTypeCount].f, kPlayerFn, sizeof(kPlayerFn));
    memset(&g_types[kTypeCount + 1], 0, sizeof(TypeRec));
    DWORD base = reinterpret_cast<DWORD>(g_types);
    int done = 0;
    for (; done < kTypeOperandCount; ++done) {
        DWORD v = base + (kTypeOperands[done].value - kTypeTable);
        if (!WriteCode(kTypeOperands[done].at, &v, 4)) break;
    }
    if (done != kTypeOperandCount) {      // put back what was changed
        for (int i = 0; i < done; ++i) WriteCode(kTypeOperands[i].at, &kTypeOperands[i].value, 4);
        Log(0, "type table: patch incomplete - original operands restored");
        return false;
    }
    Log(1, "type table: record %d \"%s\" (init DoppelgangerInit 0x%08lx, f2..f6 of the player) added; copy at 0x%08lx, "
           "%d operands moved", kTypeCount, kToName, g_types[kTypeCount].init, base, kTypeOperandCount);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// 0.2: flag reset with every new game tracker (TU player init alloc path: constructor 0x82413878 = memset 0x1320)
extern "C" void __cdecl TrackerConstructed(void *tracker) {
    LONG n = InterlockedIncrement(&g_trackers);
    LONG was = InterlockedExchange(&g_doppelganger, 0);    // the TU's memset clears +0x1244
    Log(was ? 1 : 2, "new game tracker %ld at 0x%08lx (tru+0x31c2d0 = TU 0x82413878)%s", n,
        reinterpret_cast<DWORD>(tracker), was ? ": doppelganger flag 1 -> 0" : ", doppelganger flag 0");
}

DWORD g_trackerCtor = kTrackerCtor;

// replaces `call 0x71c2d0` at tru+0x322445 (thiscall, ecx = block+0x40, no stack arguments, returns this)
__declspec(naked) void TrackerCtorHook() {
    __asm {
        push ecx
        call dword ptr [g_trackerCtor]
        pop ecx
        push eax
        push ecx
        call TrackerConstructed
        add esp, 4
        pop eax
        ret
    }
}

bool PatchFlagReset() {
    if (!HexBytesAt(kTrackerCtor, kTrackerCtorHex) || !HexBytesAt(kTrackerCtorCallCheck, kTrackerCtorCallHex) ||
        !HexBytesAt(kTrackerPublish - 3, kTrackerPublishHex)) {
        Log(0, "flag reset: tracker constructor 0x%08lx / call 0x%08lx / publish 0x%08lx does not match - not patched "
               "(the doppelganger flag then stays set for the rest of the session once DLC 2 was played)",
            kTrackerCtor, kTrackerCtorCall, kTrackerPublish);
        return false;
    }
    BYTE call[5] = {0xe8, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(&TrackerCtorHook) - (kTrackerCtorCall + 5);
    memcpy(call + 1, &rel, 4);
    if (!WriteCode(kTrackerCtorCall, call, sizeof(call))) return false;
    Log(1, "flag reset: every new game tracker (call 0x%08lx -> constructor 0x%08lx) clears the doppelganger flag, as the "
           "TU's memset (0x82413878); DoppelgangerInit sets it again afterwards", kTrackerCtorCall, kTrackerCtor);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// 0.5: the TU costume mapping 857 doppelganger_casual <-> 11 lara_doppelganger (see the header). The ids come from the
// name lookup at every call, as in the TU (bl 0x822809e0 with the string each time).
typedef int(__cdecl *NameLookupFn)(const char *);
int LookupId(const char *name) {
    __try {
        return reinterpret_cast<NameLookupFn>(kNameLookup)(name);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

bool WriteDword(DWORD address, DWORD value) {
    __try {
        *reinterpret_cast<volatile DWORD *>(address) = value;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// TU 0x821ff0dc..0x821ff118 (state save): r3 = id("doppelganger_casual"); r10 = current (lwz 0x140(r29));
// equal -> sth id("lara_doppelganger"), 0x20c; else sth current, 0x20c. Returns the word the PC stores at +0x20c.
extern "C" DWORD __cdecl MapSave() {
    DWORD cur = 0;
    ReadDword(kCostumeId, &cur);
    int dc = LookupId(kToName);
    if (static_cast<int>(cur) != dc) {
        Log(2, "costume map (state save, TU 0x821ff0dc): current %lu is not %s (%d) - chosen +0x20c = %lu", cur, kToName,
            dc, cur & 0xffff);
        return cur;
    }
    int ld = LookupId(kFromName);
    LONG n = InterlockedIncrement(&g_mapCount);
    Log(1, "costume map %ld (state save, TU 0x821ff0dc..0x821ff118): current %lu = %s -> chosen +0x20c = %d (%s)", n,
        cur, kToName, ld, kFromName);
    return static_cast<DWORD>(ld);
}

// TU 0x821ff518..0x821ff540 (state load): r30 = extsh(lhz 0x20c); r30 == id("lara_doppelganger") ->
// current = id("doppelganger_casual"), else current = r30. Stores [0xe7f1c8] (the PC's `mov [0E7F1C8h],ecx`) and
// returns the value for ecx.
extern "C" DWORD __cdecl MapLoad(DWORD gameData) {
    WORD w = 0;
    ReadWord(gameData + 0x20c, &w);
    int v = static_cast<SHORT>(w);
    int ld = LookupId(kFromName);
    int result = v;
    if (v == ld) {
        result = LookupId(kToName);
        LONG n = InterlockedIncrement(&g_mapCount);
        Log(1, "costume map %ld (state load, TU 0x821ff518..0x821ff540): chosen +0x20c %d = %s -> current %d (%s)", n, v,
            kFromName, result, kToName);
    } else {
        Log(2, "costume map (state load, TU 0x821ff518): chosen +0x20c %d is not %s (%d) - current = %d", v, kFromName,
            ld, v);
    }
    if (!WriteDword(kCostumeId, static_cast<DWORD>(result)))
        Log(0, "costume map (state load): [0x%08lx] not writable", kCostumeId);
    return static_cast<DWORD>(result);
}

// TU 0x822976b0..0x822976d8 / 0x8229803c..0x82298064 (both spawns, the same code): lhz r10, 0x50(r31);
// r10 == id("lara_doppelganger") -> stw id("doppelganger_casual"), 0x140(r26 / r30) (= current [0xe7f1c8]) and
// sth it, 0x50(r31)
void MapSpawn(DWORD record, const char *which, const char *tu) {
    WORD w = 0;
    if (!ReadWord(record + 0x50, &w)) {
        Log(0, "costume map (%s): record 0x%08lx not readable", which, record);
        return;
    }
    int ld = LookupId(kFromName);
    if (static_cast<int>(w) != ld) {
        Log(2, "costume map (%s, TU %s): record 0x%08lx +0x50 %u is not %s (%d) - kept", which, tu, record, w,
            kFromName, ld);
        return;
    }
    int dc = LookupId(kToName);
    bool ok = WriteDword(kCostumeId, static_cast<DWORD>(dc)) && WriteWord(record + 0x50, static_cast<WORD>(dc));
    LONG n = InterlockedIncrement(&g_mapCount);
    Log(ok ? 1 : 0, "costume map %ld (%s, TU %s): record 0x%08lx +0x50 %u = %s -> current [0x%08lx] and +0x50 = %d (%s)%s",
        n, which, tu, record, w, kFromName, kCostumeId, dc, kToName, ok ? "" : " - WRITE FAILED");
}
extern "C" void __cdecl MapSpawnA(DWORD record) { MapSpawn(record, "player spawn", "0x822976b0..0x822976d8"); }
extern "C" void __cdecl MapSpawnB() { MapSpawn(kSpawnRecordB, "switch spawn", "0x8229803c..0x82298064"); }

DWORD g_mapBack[4] = {0, 0, 0, 0};          // continue addresses, filled from kMapSites

// tru+0x155cb1: mov ax, word [0xe7f1c8]; mov word [edx+0x20c], ax  (eax's upper half kept as the original does)
__declspec(naked) void MapSaveDetour() {
    __asm {
        pushad
        call MapSave
        mov word ptr [esp + 28], ax  // saved eax (pushad frame: edi esi ebp esp ebx edx ecx eax)
        popad
        mov word ptr [edx + 0x20c], ax
        jmp dword ptr [g_mapBack]
    }
}
// tru+0x156fbd: movsx ecx, word [eax+0x20c]; mov [0xe7f1c8], ecx  (MapLoad stores [0xe7f1c8])
__declspec(naked) void MapLoadDetour() {
    __asm {
        pushad
        push eax
        call MapLoad
        add esp, 4
        mov [esp + 24], eax          // saved ecx
        popad
        jmp dword ptr [g_mapBack + 4]
    }
}
// tru+0x1d42e9: add esp, 4; test edi, edi  (esi = the spawn record; the jz at 0x5d42ee follows)
__declspec(naked) void MapSpawnADetour() {
    __asm {
        add esp, 4
        pushad
        push esi
        call MapSpawnA
        add esp, 4
        popad
        test edi, edi
        jmp dword ptr [g_mapBack + 8]
    }
}
// tru+0x1d4469: push 0; push esi; push 0xe7f2a0  (then call 0x5bd080)
__declspec(naked) void MapSpawnBDetour() {
    __asm {
        pushad
        call MapSpawnB
        popad
        push 0
        push esi
        push 0x00e7f2a0
        jmp dword ptr [g_mapBack + 12]
    }
}

// all four or none: every site, its context and the lookup checked first; a failed write puts back what was written
bool PatchTuMapping() {
    if (!HexBytesAt(kNameLookup, kNameLookupHex) || !HexBytesAt(kSpawnCall, kSpawnCallHex)) {
        Log(0, "costume map: name lookup 0x%08lx / spawn call 0x%08lx does not match - not patched (none of the four)",
            kNameLookup, kSpawnCall);
        return false;
    }
    for (int i = 0; i < kMapSiteCount; ++i) {
        if (!HexBytesAt(kMapSites[i].at, kMapSites[i].hex) || !HexBytesAt(kMapSites[i].ctxAt, kMapSites[i].ctxHex)) {
            Log(0, "costume map: %s at 0x%08lx (context 0x%08lx) does not match - not patched (none of the four: the TU "
                   "mapping only works as a whole)", kMapSites[i].what, kMapSites[i].at, kMapSites[i].ctxAt);
            return false;
        }
    }
    void *const detours[4] = {reinterpret_cast<void *>(&MapSaveDetour), reinterpret_cast<void *>(&MapLoadDetour),
                              reinterpret_cast<void *>(&MapSpawnADetour), reinterpret_cast<void *>(&MapSpawnBDetour)};
    BYTE saved[4][16];
    int done = 0;
    for (; done < kMapSiteCount; ++done) {
        const MapSite &s = kMapSites[done];
        size_t len = s.back - s.at;
        g_mapBack[done] = s.back;
        BYTE code[16];
        memset(code, 0x90, sizeof(code));
        code[0] = 0xe9;
        DWORD rel = reinterpret_cast<DWORD>(detours[done]) - (s.at + 5);
        memcpy(code + 1, &rel, 4);
        memcpy(saved[done], reinterpret_cast<const void *>(s.at), len);
        if (!WriteCode(s.at, code, len)) break;
    }
    if (done != kMapSiteCount) {
        for (int i = 0; i < done; ++i) WriteCode(kMapSites[i].at, saved[i], kMapSites[i].back - kMapSites[i].at);
        Log(0, "costume map: patch incomplete - original code restored (none of the four)");
        return false;
    }
    Log(1, "costume map: TU 857 <-> 11 patched at state save 0x%08lx, state load 0x%08lx, player spawn 0x%08lx, switch "
           "spawn 0x%08lx (TU 0x821ff0dc / 0x821ff518 / 0x822976b0 / 0x8229803c); a save in DLC 2 now stores %s (11) "
           "like the TU", kMapSites[0].at, kMapSites[1].at, kMapSites[2].at, kMapSites[3].at, kFromName);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// 0.7: TU 0x8247f2d8..0x8247f3a0 "Resetting player tailoring to Medium difficulty." - the five PC tailoring setters
// with 1 in the TU's order (each = the TU's metric call (a PC `ret`) + store); old / new values logged
void TailoringReset(LONG n) {
    DWORD game = 0, before[kTailorCount], after[kTailorCount];
    bool readOk = ReadDword(kGameData, &game) && game;
    for (int i = 0; i < kTailorCount; ++i) {
        before[i] = 0xffffffff;
        if (readOk) ReadDword(game + kTailor[i].pcOff, &before[i]);
    }
    for (int i = 0; i < kTailorCount; ++i) {
        __try {
            reinterpret_cast<SetterFn>(kTailor[i].fn)(kTailorMedium);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            Log(0, "dialog difficulty %ld: exception 0x%08lx in the %s setter 0x%08lx - the rest of the reset skipped", n,
                GetExceptionCode(), kTailor[i].name, kTailor[i].fn);
            return;
        }
    }
    game = 0;
    readOk = ReadDword(kGameData, &game) && game;
    for (int i = 0; i < kTailorCount; ++i) {
        after[i] = 0xffffffff;
        if (readOk) ReadDword(game + kTailor[i].pcOff, &after[i]);
    }
    Log(1, "dialog difficulty %ld: player tailoring reset to Medium (1) as the TU 0x8247f2d8..0x8247f3a0 - EnemyHP +0x%lx "
           "%ld -> %ld, AmmoAdj +0x%lx %ld -> %ld, PlayerHP +0x%lx %ld -> %ld, SavingGrabAdj +0x%lx %ld -> %ld, f10 +0x%lx "
           "%ld -> %ld (game data 0x%08lx)", n,
        kTailor[0].pcOff, static_cast<long>(before[0]), static_cast<long>(after[0]),
        kTailor[1].pcOff, static_cast<long>(before[1]), static_cast<long>(after[1]),
        kTailor[2].pcOff, static_cast<long>(before[2]), static_cast<long>(after[2]),
        kTailor[3].pcOff, static_cast<long>(before[3]), static_cast<long>(after[3]),
        kTailor[4].pcOff, static_cast<long>(before[4]), static_cast<long>(after[4]), game);
}

// 0.6: dialog accept case 8 (start a level from the game) as the TU, 0x8247f2c8..0x8247f510 (see the header)
extern "C" void __cdecl AcceptStartLevel(const char *name) {
    static DWORD args[1];                  // the DataValue f27 reads its name from (TU: &local 0x60); f27 copies the name
    LONG n = InterlockedIncrement(&g_dialogStarts);
    char shown[64];
    SafeName(name ? name : "", shown, sizeof(shown));
    if (g_difficultyOk) TailoringReset(n); // 0.7: the TU resets before the print / rule / UILoadLevel
    int select = 1;                        // TU 0x8247f3c8..0x8247f4dc: five byte-compare loops (= strcmp)
    for (const char *u : kNoSelectUnits)
        if (strcmp(shown, u) == 0) select = 0;
    Log(1, "dialog start %ld: level \"%s\" (RegisterAcceptChanges case 8) -> f27 UILoadLevel(\"%s\", %d, 0, 1) as the TU "
           "0x8247f510: %s; 4th argument 1 = new-game block with the costume reset (PC retail code: (\"%s\", 1, 0, 0))",
        n, shown, shown, select,
        select ? "WITH costume / weapon selection (not dlc_level2..6_start)"
               : "without costume / weapon selection (TU: \"Attempting to load DLC2 starting unit without "
                 "costume/weapon selection.\")", shown);
    args[0] = reinterpret_cast<DWORD>(name);
    __try {
        reinterpret_cast<UiLoadLevelFn>(kUiLoadLevel)(args, select, 0, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "dialog start %ld: exception 0x%08lx in f27 UILoadLevel(\"%s\", %d, 0, 1)", n, GetExceptionCode(), shown,
            select);
        return;
    }
    BYTE sel = 0xff;
    __try { sel = *reinterpret_cast<volatile BYTE *>(kSelectByte); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    Log(1, "dialog start %ld: f27 returned, selection byte [0x%08lx] = %u", n, kSelectByte, sel);
}

// replaces tru+0x37e8c0..0x37e8e3 (ebp = the level name, ebx = 0; eax / ecx / edx are free - the original code
// overwrites them and the tail's call 0x5a48d0 returns in eax)
DWORD g_case8Back = kCase8Back;

__declspec(naked) void AcceptCase8Detour() {
    __asm {
        pushad
        push ebp
        call AcceptStartLevel
        add esp, 4
        popad
        jmp dword ptr [g_case8Back]
    }
}

bool PatchDialogStart() {
    DWORD entry = 0;
    if (!HexBytesAt(kAcceptFn, kAcceptFnHex) || !HexBytesAt(kAcceptSwitch, kAcceptSwitchHex) ||
        !ReadDword(kAcceptTable + 7 * 4, &entry) || entry != kCase8 || !HexBytesAt(kCase8, kCase8Hex) ||
        !HexBytesAt(kCase8Site, kCase8SiteHex) || !HexBytesAt(kCase8Back, kCase8BackHex) ||
        !HexBytesAt(kUiLoadLevel, kUiLoadLevelHex) || !HexBytesAt(kUiLoadTail, kUiLoadTailHex)) {
        Log(0, "dialog start: RegisterAcceptChanges 0x%08lx / case 8 0x%08lx (table entry 0x%08lx) / site 0x%08lx / f27 "
               "0x%08lx does not match - not patched (DLC 2 from the game keeps the outfit selection)", kAcceptFn, kCase8,
            entry, kCase8Site, kUiLoadLevel);
        return false;
    }
    BYTE code[35];
    memset(code, 0x90, sizeof(code));
    code[0] = 0xe9;
    DWORD rel = reinterpret_cast<DWORD>(&AcceptCase8Detour) - (kCase8Site + 5);
    memcpy(code + 1, &rel, 4);
    if (kCase8Back - kCase8Site != sizeof(code) || !WriteCode(kCase8Site, code, sizeof(code))) return false;
    Log(1, "dialog start: RegisterAcceptChanges case 8 (a level started from the game, e.g. pause menu -> DLC) calls f27 "
           "UILoadLevel(name, 0 for dlc_level2..6_start else 1, 0, 1) as the TU 0x8247f2c8..0x8247f510 (detour at "
           "0x%08lx, 35 bytes); DLC 2 starts without the outfit selection", kCase8Site);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// 0.7: the case-8 tail's last call tru+0x37e8f9 (call 0x4be5e0) -> this; then the TU's store 0x8247f570..0x8247f57c
// `stb 0, 0x1f94(0x829be044)` = PC 0x5bfdf0(0) ([0xdb94de] = 0). Called only from case 8 (no branch into the tail:
// tools/pe_patch_site_check.py); eax / ecx / edx are free (the next instruction is jmp 0x77e94a, which loads eax)
volatile LONG g_tailHolds = 0;

extern "C" void __cdecl AcceptCase8Tail() {
    reinterpret_cast<VoidFn>(kTailCallee)();
    BYTE before = 0xff, after = 0xff;
    __try { before = *reinterpret_cast<volatile BYTE *>(kHoldByte); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    reinterpret_cast<HoldSetFn>(kHoldSet)(0);
    __try { after = *reinterpret_cast<volatile BYTE *>(kHoldByte); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    LONG n = InterlockedIncrement(&g_tailHolds);
    Log(1, "dialog difficulty %ld: case-8 tail - render hold [0x%08lx] %u -> %u (0x%08lx(0) as the TU store 0x8247f57c "
           "`stb 0, 0x1f94(0x829be044)`)", n, kHoldByte, before, after, kHoldSet);
}

bool PatchDialogDifficulty() {
    for (int i = 0; i < kTailorCount; ++i) {
        if (!HexBytesAt(kTailor[i].fn, kTailor[i].hex)) {
            Log(0, "dialog difficulty: the %s setter 0x%08lx (TU game data +0x%lx = PC +0x%lx) does not match - not "
                   "patched", kTailor[i].name, kTailor[i].fn, kTailor[i].tuOff, kTailor[i].pcOff);
            return false;
        }
    }
    if (!HexBytesAt(kMetricStub, kMetricStubHex) || !HexBytesAt(kTailCall, kTailCallHex) ||
        !HexBytesAt(kTailCallee, kTailCalleeHex) || !HexBytesAt(kHoldSet, kHoldSetHex)) {
        Log(0, "dialog difficulty: metric stub 0x%08lx / tail call 0x%08lx / its callee 0x%08lx / hold setter 0x%08lx does "
               "not match - not patched", kMetricStub, kTailCall, kTailCallee, kHoldSet);
        return false;
    }
    BYTE code[5];
    code[0] = 0xe8;
    DWORD rel = reinterpret_cast<DWORD>(&AcceptCase8Tail) - (kTailCall + 5);
    memcpy(code + 1, &rel, 4);
    if (!WriteCode(kTailCall, code, sizeof(code))) return false;
    g_difficultyOk = true;
    Log(1, "dialog difficulty: case 8 also resets the player tailoring to Medium (setters 0x%08lx / 0x%08lx / 0x%08lx / "
           "0x%08lx / 0x%08lx with 1, before f27; TU 0x8247f2d8..0x8247f3a0) and clears the render hold [0x%08lx] after "
           "its tail (call at 0x%08lx redirected; TU 0x8247f57c)", kTailor[0].fn, kTailor[1].fn, kTailor[2].fn,
        kTailor[3].fn, kTailor[4].fn, kHoldByte, kTailCall);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// 0.8: the TU's `stb 0, 0x1f94(0x829be044)` after the call of case 4 (TU 0x8247f1d0..0x8247f1dc) and of case 6
// (TU 0x8247f2a8..0x8247f2b4) = PC tru+0x1bfdf0(0) ([0xdb94de] = 0) right after the PC's partner call
void CaseHoldClear(int which, const char *what) {
    BYTE before = 0xff, after = 0xff;
    __try { before = *reinterpret_cast<volatile BYTE *>(kHoldByte); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    reinterpret_cast<HoldSetFn>(kHoldSet)(0);
    __try { after = *reinterpret_cast<volatile BYTE *>(kHoldByte); } __except (EXCEPTION_EXECUTE_HANDLER) {}
    LONG n = InterlockedIncrement(&g_caseHolds);
    Log(1, "dialog hold %ld: case %d (%s) - render hold [0x%08lx] %u -> %u (0x%08lx(0) as the TU store %s "
           "`stb 0, 0x1f94(0x829be044)`)", n, which, what, kHoldByte, before, after, kHoldSet,
        which == 4 ? "0x8247f1dc" : "0x8247f2b4");
}

// case 4: tru+0x37e7fe `call 0x77e460` -> this (next instruction jmp 0x77e94a; eax / ecx / edx are free there)
extern "C" void __cdecl AcceptCase4Call() {
    reinterpret_cast<VoidFn>(kCase4Callee)();
    CaseHoldClear(4, "after tru+0x37e460 = TU bl 0x8247e000");
}

// case 6: tru+0x37e860 / 0x37e88d `call 0x5dfb20` (cdecl, 2 arguments, the caller pops them) -> this
extern "C" void __cdecl AcceptCase6Load(const char *name, int arg) {
    reinterpret_cast<LevelRequestFn>(kLevelRequest)(name, arg);
    char shown[64];
    SafeName(name ? name : "", shown, sizeof(shown));
    char what[120];
    _snprintf_s(what, sizeof(what), _TRUNCATE, "level \"%s\", after tru+0x1dfb20(name, %d) = TU bl 0x8247d818", shown,
                arg);
    CaseHoldClear(6, what);
}

bool PatchDialogHoldClear() {
    DWORD e4 = 0, e6 = 0;
    bool ok = HexBytesAt(kAcceptFn, kAcceptFnHex) && HexBytesAt(kAcceptSwitch, kAcceptSwitchHex) &&
              ReadDword(kAcceptTable + 3 * 4, &e4) && e4 == kCase4 && ReadDword(kAcceptTable + 5 * 4, &e6) &&
              e6 == kCase6 && HexBytesAt(kCase4, kCase4Hex) && HexBytesAt(kCase4Call, kCase4CallHex) &&
              HexBytesAt(kCase4Callee, kCase4CalleeHex) && HexBytesAt(kCase6, kCase6Hex) &&
              HexBytesAt(kLevelRequest, kLevelRequestHex) && HexBytesAt(kHoldSet, kHoldSetHex);
    for (const LoadSite &s : kCase6Calls) ok = ok && HexBytesAt(s.at, s.hex);
    if (!ok) {
        Log(0, "dialog hold: RegisterAcceptChanges 0x%08lx / case 4 0x%08lx (table 0x%08lx) / case 6 0x%08lx (table "
               "0x%08lx) / call sites 0x%08lx, 0x%08lx, 0x%08lx / callees 0x%08lx, 0x%08lx / hold setter 0x%08lx do not "
               "match - not patched", kAcceptFn, kCase4, e4, kCase6, e6, kCase4Call, kCase6Calls[0].at,
            kCase6Calls[1].at, kCase4Callee, kLevelRequest, kHoldSet);
        return false;
    }
    struct Redirect { DWORD at; const void *to; } redirects[] = {
        {kCase4Call, reinterpret_cast<const void *>(&AcceptCase4Call)},
        {kCase6Calls[0].at, reinterpret_cast<const void *>(&AcceptCase6Load)},
        {kCase6Calls[1].at, reinterpret_cast<const void *>(&AcceptCase6Load)}};
    BYTE saved[3][5];
    int done = 0;
    for (const Redirect &r : redirects) {
        memcpy(saved[done], reinterpret_cast<const void *>(r.at), 5);
        BYTE code[5];
        code[0] = 0xe8;
        DWORD rel = reinterpret_cast<DWORD>(r.to) - (r.at + 5);
        memcpy(code + 1, &rel, 4);
        if (!WriteCode(r.at, code, sizeof(code))) break;
        ++done;
    }
    if (done != 3) {
        for (int i = 0; i < done; ++i) WriteCode(redirects[i].at, saved[i], 5);
        Log(0, "dialog hold: patch incomplete - original calls restored (none of the three)");
        return false;
    }
    Log(1, "dialog hold: RegisterAcceptChanges cases 4 and 6 clear the render hold [0x%08lx] after their call as the TU "
           "(case 4: call at 0x%08lx -> 0x%08lx + 0x%08lx(0), TU 0x8247f1dc; case 6: calls at 0x%08lx / 0x%08lx -> "
           "0x%08lx + 0x%08lx(0), TU 0x8247f2b4)", kHoldByte, kCase4Call, kCase4Callee, kHoldSet, kCase6Calls[0].at,
        kCase6Calls[1].at, kLevelRequest, kHoldSet);
    return true;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruDlc2Player.ini", dir);
    g_flagReset = GetPrivateProfileIntA("Dlc2Player", "FlagReset", 1, ini);
    g_enabled = GetPrivateProfileIntA("Dlc2Player", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Dlc2Player", "LogLevel", 1, ini);
    g_costume = GetPrivateProfileIntA("Dlc2Player", "Costume", 1, ini);
    g_typeRecord = GetPrivateProfileIntA("Dlc2Player", "TypeRecord", 1, ini);
    g_costumeReset = GetPrivateProfileIntA("Dlc2Player", "CostumeReset", 1, ini);
    g_trackerFlag = GetPrivateProfileIntA("Dlc2Player", "TrackerFlag", 1, ini);
    g_tuMapping = GetPrivateProfileIntA("Costume", "TuMapping", 0, ini);      // 0.5, default 0 = as 0.4
    g_dialogStart = GetPrivateProfileIntA("Mission", "DialogStart", 1, ini);  // 0.6, 0 = as 0.5
    g_dialogDifficulty = GetPrivateProfileIntA("Mission", "DialogDifficulty", 0, ini);  // 0.7, 0 = as 0.6
    g_dialogHoldClear = GetPrivateProfileIntA("Mission", "DialogHoldClear", 0, ini);    // 0.8, 0 = as 0.7
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruDlc2Player.log", dir);
    ReadOptions(dir);
    Log(1, "TruDlc2Player 0.8.1 loaded (enabled %d, log level %d, costume %d, type record %d, flag reset %d, costume "
           "reset %d, tracker flag %d, [Costume] TU mapping %d, [Mission] dialog start %d, dialog difficulty %d, dialog "
           "hold clear %d)",
        g_enabled, g_logLevel, g_costume, g_typeRecord, g_flagReset, g_costumeReset, g_trackerFlag, g_tuMapping,
        g_dialogStart, g_dialogDifficulty, g_dialogHoldClear);
    if (!g_enabled) { Log(1, "disabled by TruDlc2Player.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    CheckTrackerFlag();                    // before the type record: DoppelgangerInit reads g_trackerFlagOk
    // the record first: a substituted costume without its type record would be an object without player functions
    bool types = g_typeRecord ? PatchTypeTable() : false;
    bool costume = false;
    if (g_costume) {
        if (types) costume = PatchCostume();
        else Log(0, "costume: not patched because the type record \"%s\" is missing (an object of that name would "
                    "get no player functions)", kToName);
    }
    // 0.5: the mapping makes 857 the current costume at load / spawn - only with the type record and the level-load
    // substitution (which loads object 857 instead of 11), as on the TU where all of them belong together
    if (g_tuMapping) {
        if (types && costume) PatchTuMapping();
        else Log(0, "costume map: [Costume] TuMapping=1 but the type record / level-load costume patch is missing "
                    "(TypeRecord=1 and Costume=1 needed) - not patched");
    } else {
        Log(1, "costume map: off ([Costume] TuMapping=0) - saves keep 857 (%s) as up to 0.4", kToName);
    }
    if (g_flagReset) PatchFlagReset();
    else Log(1, "flag reset: off ([Dlc2Player] FlagReset=0) - the flag stays set after DLC 2 for the whole session");
    // 0.6: independent of the costume patches (the TU rule decides only the selection and the new-game reset)
    bool started = false;
    if (g_dialogStart) started = PatchDialogStart();
    else Log(1, "dialog start: off ([Mission] DialogStart=0) - a level started from the game (pause menu -> DLC) keeps "
                "the PC / retail UILoadLevel(name, 1, 0, 0): always the outfit selection");
    // 0.7: the rest of the TU's case 8 - only together with the 0.6 detour (the TU does all of it in one case)
    if (g_dialogDifficulty) {
        if (started) PatchDialogDifficulty();
        else Log(0, "dialog difficulty: [Mission] DialogDifficulty=1 but the DialogStart detour is not in place "
                    "(DialogStart=0 or its check failed) - not patched");
    } else {
        Log(1, "dialog difficulty: off ([Mission] DialogDifficulty=0) - a level started from the game keeps the player "
               "tailoring (the TU resets it to Medium)");
    }
    // 0.8: the TU's hold store after cases 4 and 6 - own sites, independent of the case-8 patches
    if (g_dialogHoldClear) PatchDialogHoldClear();
    else Log(1, "dialog hold: off ([Mission] DialogHoldClear=0) - cases 4 / 6 leave the render hold as the PC / retail "
                "(the TU clears it after them)");
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    }
    return TRUE;
}

// exported: plugin identification, and the TU's gameTracker+0x1244 for other plugins (1 after DoppelgangerInit)
extern "C" __declspec(dllexport) const char *TruDlc2PlayerVersion() {
    return "TruDlc2Player 0.8.1 (DLC 2 doppelganger player object, flag reset with every new game tracker, chosen-costume "
           "reset outside DLC 2, game tracker +0x1244 as the TU, [Costume] TuMapping 857 <-> 11 in save / load / "
           "spawns, [Mission] DialogStart: DLC 2 from the game without the outfit selection as the TU, [Mission] "
           "DialogDifficulty: that start also resets the player tailoring to Medium as the TU, [Mission] "
           "DialogHoldClear: dialog cases 4 / 6 clear the render hold as the TU; 0.8.1: dated log lines)";
}

extern "C" __declspec(dllexport) int TruDlc2PlayerDoppelganger() {
    return g_doppelganger ? 1 : 0;
}

// 0.2: number of game trackers constructed since load (changes = the TU would have a new tracker with zeroed fields)
extern "C" __declspec(dllexport) int TruDlc2PlayerTrackerGeneration() {
    return static_cast<int>(g_trackers);
}
