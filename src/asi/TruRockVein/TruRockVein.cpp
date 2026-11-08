// TruRockVein.asi - DLC 2 "Lara's Shadow" rock veins for the PC tru.exe (Steam, image base 0x400000).
//
// Lara's moves run through a data-driven state machine; transitions test numbered conditions. The Xbox title update
// added two markup conditions to SCCondTest_MarkupType (Xbox TU 0x82486dd8, retail 0x82480e78; docs Befund-Felsrinne
// "step 3.4"): 607 = "the player's markup has type 23", 608 = "... type 22" - most likely the rock vein and its jump
// target. The PC exe (like the Xbox retail exe) has no case for them: its jump table sends 604-609 to the default
// "unhandled condition" case, so every state transition that needs them is false and LB/RB + A at a rock vein does
// nothing. This plugin adds the two cases with exactly the title update's logic:
//
//   Xbox TU 607 / 608: ctx == 0 -> false; markup = [ctx+0x24] ? type byte +0x4d : ([ctx+0x20] ? type byte +0x33 : -)
//                      result = (signed char)type == 23 (607) / 22 (608)
//   PC   tru+0x1be340  the same getter already exists (thiscall: [ecx+24h]->+4Dh, else [ecx+20h]->+33h, else 0)
//   PC   tru+0x382810  SCCondTest_MarkupType (cdecl; after its push ebx / push esi: [esp+14h] condition record,
//                      [esp+18h] markup flags, [esp+1Ch] the context the TU code reads)
//   PC   tru+0x382a54  jump table for ids 601-628 (index = id - 601), default case tru+0x382a19 ("unhandled
//                      condition (%d)"), common exit tru+0x382a3f (result in bl, negation flag of the record applied)
//
// The two table entries (index 6 = 607, 7 = 608) are pointed at small stubs that compute bl and jump to the common
// exit. Optionally every other "unhandled" entry is pointed at a stub that logs the id once and then runs the
// original default case - so the next missing title-update condition shows up in TruRockVein.log.
// Every address is checked against the expected bytes first; on any mismatch nothing is patched and the reason is
// logged. Loaded by the Ultimate ASI Loader the installed game ships as binkw32.dll. Options: TruRockVein.ini.
//
// 0.2 (2026-10-31) - diagnostics for the morning test (docs Befund-Felsrinne "Rock vein: why 607/608 are never
// evaluated"). 607 / 608 are not condition ids but the u16 VALUE (+4) of a condition record {u16 key, u16 id, u16
// value, u8 flags}; the record id (610..613) selects the handler from Lara's link array, which passes the record to
// SCCondTest_MarkupType. Our converted DLC 2 state chart had these values in Xbox byte order (608 -> 24578), so the
// dispatch went to the default before the jump table and the 0.1 stubs never ran. Two read-only probes, no change of
// the game's results:
//   * LogBadValues: a 5-byte detour on `sub eax,259h` at tru+0x38288d logs every markup value > 628 (except the
//     special 1000) once - with a correct chart there are none; and at LogLevel 2 the first call of each 601..628.
//   * LogDefaultConditions: a detour on the entry of the condition default handler tru+0x382140 (Xbox
//     SCCondFunction_Default 0x82484db0: formats "You must add a condition function ...", returns true) logs each
//     condition id that reaches it once, with record key / value and the agent's state name - the title-update
//     conditions Lara's own link array lacks (TU-Abdeckung.md: 1048-1056, 2005, 2006, 2013, 2401) show up here.
//
// 0.3 (2026-11-01, docs Befund-Felsrinne "Rock vein: no markup context at the wall") - live 607 / 608 ran with ctx 0:
// the PC disables every markup of type 22 / 23 when it is added (type -> flag mapper tru+0x5d70a0 = Xbox retail, only
// types 1..21; the title update 0x822a12e8 maps 22 / 23 to flag class 1). PatchMarkupTypes adds the two cases.
//
// 0.4 (2026-11-01, docs Befund-Felsrinne "Wall run: crash on entering the attach state (tru+0x1dba2d)") - with 0.3 the
// condition 608 was true and the game crashed 237 ms later in TRMarkupManager slot +0x08 (tru+0x1dba20, the wall normal
// of a box) with box = NULL. A box of flag class 1 carries none of the move bits, so on PC the attach dispatcher
// tru+0x307b90 (box = gameTracker+0xa64) finds neither slot 0 ("wall", bits 0x04480010) nor slot 1 (bits 0x61870000)
// nor bit 0x8000 true and never sets the attach box gameTracker+0xc94; the next state code reads +0xc94 = 0. The title
// update added the new types to exactly these slots (TU vtable 0x8206827c): slot 0 0x822a0bc8 "... || type == 22",
// slot 1 0x822a0c68 "... || type == 23", slot +0x08 0x822a0d08 takes the edge (cross product) path also for type 22.
// PatchSlots translates the three 1:1 (type = second markup +0x4d, else record +0x33, as the TU code reads it).
// NullBoxGuard (diagnostic, not a translation - the TU would read address 0x28 too): slot +0x08 with box 0 logs the
// return addresses (into the wrapper tru+0x1c3cc0 and its caller) and returns a zero vector instead of crashing.
//
// 0.5 (2026-11-01, live test 48j with 0.4: guard fired from tru+0x32ba5b, +0xc94 = 0, then AV in tru+0x1c39e2 with
// the same box 0) - the attach box is set by PLAYER_AttachToJumpTarget (PC tru+0x307b90 = TU 0x823fd178, unchanged),
// and the title update calls it for the new markup action 608: the markup-action selector (PC tru+0x372ca0 = TU
// 0x82463538) switches on the state parameter 0x19a; the TU added case 608 (0x82463a28: if gameTracker+0xa64 != 0 ->
// PLAYER_AttachToJumpTarget(zero vector, 0.0) and gameTracker+0xca0 = gameTracker+0xd90), every other case of
// 601..629 has the same target pattern on PC and TU. The PC sends 608 to its default ("unknown", print compiled out),
// so no attach happens and state 572 (parameter 0x1e1 = 611) reads +0xc94 = 0. PatchSelector adds the case.
// NullBoxGuard also covers tru+0x32ba40 (attach point on a box, cdecl(out, box)), the second crash site's caller.
//
// 0.6 (2026-11-01, live test 48k with 0.5: Lara attaches, but faces the wrong way, does not stick to the wall and drops
// off far too early; docs Befund-Felsrinne "Wall run: orientation, magnet and duration"). Chart DTP 20212: the wall run
// is chart record 1477 (Lara states 236 / 230 / 2102, parameter 0x19a = 608) under the root 1482 (states 420 / 572 /
// 1900, parameter 0x19e = 1, 0x1e1 = 611). Three title-update pieces on that path, translated 1:1:
//   * Facing (TU 0x824006a8 = PC tru+0x2fe7e0, result -> gameTracker+0xcc0 at attach): the TU inserts "type == 22 ->
//     facing = edge normal of segment 0" before the retail default (direction from the player position). On PC the
//     default block starts at tru+0x2feb05; FacingDefault sends a type-22 box to the existing flag-0x8000 case
//     tru+0x2feae4 (the same code the TU branch has: manager slot +0x08(box, 0) -> facing).
//   * Attached movement (TU 0x8245d6c8 = PC tru+0x370ba0): flag bit 0x10 "or type(gameTracker+0xc94) == 22" -> the wall
//     handler 0x8244c2c8 = PC tru+0x353d30; else the wall predicate path. MoveDefault (at tru+0x370de1, the predicate
//     path) sends a type-22 attach box to tru+0x370dd2 (push edi; push ebx; call 0x753d30).
//   * State 420 slot 1 (TU 0x8245e450, new): besides the callback store, in doppelganger mode (TU gameTracker+0x1244 =
//     TruDlc2Player's flag) and with the bool parameter 0x19e it runs the attached movement like slot 0 (PC tru+0x3712db:
//     0x75d8d0(agent); agent+0xf0 &= ~0x3f; 0x770ba0(agent); 0x76d270(+0xc94, +0xc98, agent)). State420Slot1 replaces
//     the PC slot 1 tru+0x371320 (callback store through the template tru+0x381d80, then the TU part).
// ChartLog (diagnostic): the machine's per-frame update tru+0x387e60 reads the current chart record [machine+0x510];
// when it changes for the player's machine and the old or new record index is in the wall-run range (ini), the change
// is logged with the record's Lara state ids - the test then shows the chart path (entry, loop, exit).
//
// 0.7 (2026-11-01, live test 48l: the 0.6 parts fire, Lara runs further; then AV tru+0x448198 on leaving the loop -
// a data error of doppelganger_casual.drm (VM literal, tools/vm_literal_fix.py), no code change for it): ChartLog keeps
// the last record per machine (the player has two machines; 0.6 logged "-1 -> N" every frame) and names the machine;
// the first 608 line also dumps the second markup +0x24 of the box (48l: file record id 2326 type 0, type 22 from +0x24).
//
// 0.8 (2026-11-02, docs Fehlliste-2026-11-02 / Befund-Felsrinne "Condition 528 and the missing list"): the remaining
// title-update type-22 branches of the attach geometry on the jump-off / fall path (option JumpGeometry). Each is the
// TU's inline type test (second markup +0x4d, else file record +0x33, == 22) inserted where the TU inserted it:
//   segment range   TU 0x823fe9d0 -> tru+0x2fe040: flag 0x400000 OR type 22 -> last segment index - 1
//   TNode point     TU 0x823fd890 -> tru+0x307c60: before the print default, type 22 -> position + 47.4075 x
//                   normalize(facing), z - 474.075 (constants TU 0x82051bc0 / 0x8207e5ac; facing = the function's
//                   own call of tru+0x2fe7e0 = TU 0x824006a8)
//   bone point      TU 0x823fe130 -> tru+0x311530: before the print default, type 22 -> position + 47.4075 x
//                   normalize(tru+0x2fe7e0(box, segment, position))
//   corner angle    TU 0x82400bc0 -> tru+0x309500, sites 0x7097cb / 0x709894: flag 0x400000 OR type 22 -> skip
// Hits are counted in the stubs and logged from the chart probe (ChartTick) on the game thread.
//
// 0.9 (2026-11-02, docs Befund-TU-Funktionen L1): the fifth geometry function. Retail 0x82427750 = PC tru+0x34d390
// (TU 0x8242a7c8). After the flag test `box +0x28 & 0x400000` (TU 0x8242a884..0x8242a894) the TU inserted
// 0x8242a898..0x8242a8c4: the same inline type test (second markup +0x4d, else file record +0x33, sign-extended) and
// `type == 22 -> 0x8242abac`, the block the 0x400000 flag takes (vcall through 0x829bffc4 slot +8 = PC tru+0x34d4bf
// `call 0x5c3cc0`, jmp 0x74d710). SkipGeometryStub replaces `test eax,400000h; je 0x74d4d5` at tru+0x34d4b8 (eax =
// [esi+28h], esi = box): flag or type 22 -> 0x74d4bf, else 0x74d4d5 with eax kept for the next tests (0x8000 /
// 0x40000000). Option SkipGeometry; hit counter 5 of the chart probe. With it 11 of 11 TU geometry functions.
//
// 0.10 (2026-11-08, docs Befund-SweepAndPrune-0611 section 3, Befund-P5-Kleinkram-0711 row 7b; K2 / N2b): the
// MarkupManager's SweepAndPrune limits as the title update. The owner constructor (PC tru+0x1be3a0 = retail 0x8227eda8
// = TU 0x8227b9f0; built once by the game init tru+0x1df390, owner [0xdb94cc]) creates its SAP core with
// create(1000, 200) on PC / retail and create(3000, 500) in the TU: 3000 boxes, pair pool M x 16 bytes = 1000 links
// (PC 400). The TU also writes 500 into the never-read copy of the pair parameter (TU [this+0x24] = retail / PC
// [this+0x20]; the TU's new field +0x1c = 3000 has 0 readers and would shift the layout - not taken). PatchSweepAndPrune
// ([SweepAndPrune] Translate, default 1) rewrites the two push immediates at tru+0x1be3a7 and the field immediate at
// tru+0x1be3c4 in DllMain, i.e. before the game init (checked: the owner pointer must still be 0). Control: on the first
// machine update (the chart probe, also installed for this alone) one line with core +0x24 / +0x2c / +0x20 and owner
// +0x20 (TU: 3000 / 500 / 620001 / 500). Memory: +412 800 bytes once from the game allocator.
//
// 0.11 (2026-11-08, package 18a; ENGINE.md section 14 "Ledge corner", docs Befund-17w-TU-Fixes-0811 row 2): the title
// update's ledge-corner nudge (published fix "Lara getting stuck on ledge corners"). Ledge function PC tru+0x34e5a0 =
// retail 0x8242bc30 = TU 0x8242ecd8, player tracker [0xfadb58] (TU [0x829892b0]): +0xc94 box, +0xc98 t, +0xeac partner
// box, +0xeb0 partner t. After the tests "box and partner set, both with flag 0x40000000" (PC 0x74e7c6..0x74e80e = TU
// ..0x8242eea8) the TU inserted block 0x8242eeac..0x8242ef40 runs before the segment fetch (TU 0x8227b6e0 = PC
// 0x5c3aa0):
//   dir = LookAheadDirection(arg)                          (TU 0x82489d10 = retail 0x82483c40 = PC 0x787ef0)
//   if partner box == box and floorf(partner t) == floorf(t):
//       t = floorf(t) - 0.001f   if dir == 4              (TU f30 = [0x82053608] = 0x3a83126f)
//       t = floorf(t) + 1.01f    else                     (TU [0x8207ddf8] = 0x3f8147ae)
// and the TU uses that one result again at 0x8242f094 (cmpwi r30,4), where retail / PC call it (PC site 0x74eaed,
// result compared with 4 at 0x74eafe). The lookup is not free of side effects (0x783f50 stores the resolved node in
// [arg+0x520], 0x784b30 counts the access in the node and rebalances), so the plugin keeps the TU's single call:
// LedgeCornerStub replaces `movss xmm1,[0x841134]` at tru+0x34e814 (8 bytes, executed in the stub; x87 stack empty,
// eax = tracker, ebx = arg, xmm0 live - all registers kept), and the call at tru+0x34eaed goes to LookAheadReuse,
// which returns the stored result (else, never expected, it runs the original 0x787ef0). Straight line from 0x74e814
// to 0x74eaed (one forward je inside, no jump into the range). floorf = the exe's floor 0x813510 rounded to float (TU:
// floor 0x8268b7a0 + frsp). Option [LedgeCorner] Translate (default 1); log line on the first nudge, at LogLevel 2
// every power of two.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>

namespace {

const DWORD kImageBase = 0x00400000;
const DWORD kDispatch = 0x0078288d;     // sub eax,259h; cmp eax,1Bh; ja default; jmp [table+eax*4]
const BYTE kDispatchBytes[] = {0x2d, 0x59, 0x02, 0x00, 0x00, 0x83, 0xf8, 0x1b, 0x0f, 0x87, 0x7e, 0x01, 0x00, 0x00,
                               0xff, 0x24, 0x85, 0x54, 0x2a, 0x78, 0x00};
const DWORD kTable = 0x00782a54;        // 28 entries, ids 601-628
const int kTableCount = 28;
const DWORD kDefault = 0x00782a19;      // cmp dx,3E8h ... "--- SCCondTest_MarkupType unhandled condition (%d) ---"
const BYTE kDefaultBytes[] = {0x66, 0x81, 0xfa, 0xe8, 0x03};
const DWORD kExit = 0x00782a3f;         // test byte [esi+6],1; je ...; test bl,bl; pop esi
const BYTE kExitBytes[] = {0xf6, 0x46, 0x06, 0x01, 0x74, 0x08, 0x84, 0xdb, 0x5e};
const DWORD kCtxUse = 0x007828c3;       // case 603: mov eax,[esp+1Ch]; push eax (the context argument)
const BYTE kCtxUseBytes[] = {0x8b, 0x44, 0x24, 0x1c, 0x50};
const DWORD kGetType = 0x005be340;      // markup type getter (thiscall), same logic as the TU's 607 / 608
const BYTE kGetTypeBytes[] = {0x8b, 0x41, 0x24, 0x85, 0xc0, 0x74, 0x05, 0x0f, 0xbe, 0x40, 0x4d, 0xc3,
                              0x8b, 0x49, 0x20, 0x85, 0xc9, 0x74, 0x05, 0x0f, 0xbe, 0x41, 0x33, 0xc3};
// the original table (tru.exe 2008 Steam build) - every entry is checked before anything is written
const DWORD kTableOriginal[kTableCount] = {
    0x007829da, 0x00782938, 0x007828b1, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19,  // 601-608
    0x00782a19, 0x007828db, 0x00782923, 0x007828a2, 0x0078295a, 0x00782969, 0x00782978, 0x00782987,  // 609-616
    0x00782997, 0x007829a6, 0x00782a19, 0x007829b5, 0x00782a19, 0x00782a19, 0x007829c2, 0x007829ce,  // 617-624
    0x00782a0d, 0x00782978, 0x00782a19, 0x007828ea};                                                  // 625-628

// 0.2 probes
const DWORD kDispatchNext = 0x00782892; // cmp eax,1Bh (after the 5-byte sub eax,259h we detour)
const DWORD kCondDefault = 0x00782140;  // condition default handler: sub esp,204h; mov eax,[__security_cookie] ...
const BYTE kCondDefaultBytes[] = {0x81, 0xec, 0x04, 0x02, 0x00, 0x00, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4,
                                  0x89, 0x84, 0x24, 0x00, 0x02, 0x00, 0x00, 0x8b, 0x84, 0x24, 0x10, 0x02, 0x00, 0x00,
                                  0x0f, 0xbf, 0x40, 0x02};   // ... mov eax,[esp+210h] (record); movsx eax,word [eax+2]
const DWORD kCondDefaultNext = 0x00782146;
// 0.3: markup type -> flag class, TRMarkupManager vtable 0x855214 slot +0x20 (called by the markup add loop
// tru+0x5ce55b for every record whose +0x28 is 0). PC = Xbox retail 0x822a42d8: types 1..21 only, any other type
// returns 0x80000000 = "Bad Markup Type, disabling markup" (the print is compiled out on PC) and the query loops skip
// a box with a negative flag word (tru+0x5ce459 js). The title update 0x822a12e8 accepts 1..23 and returns 1 for the
// two new types 22 / 23 (the DLC 2 rock-vein markup of the pistons / machine column / goo converter objects).
const DWORD kTypeFlagsSlot = 0x00855234;     // vtable 0x855214 + 0x20
const DWORD kTypeFlags = 0x005d70a0;
const BYTE kTypeFlagsBytes[] = {0x8b, 0x4c, 0x24, 0x04, 0x83, 0xc1, 0xff, 0x33, 0xc0, 0x83, 0xf9, 0x14, 0x77, 0x17,
                                0xff, 0x24, 0x8d, 0xd0, 0x70, 0x5d, 0x00, 0xb8, 0x01, 0x00, 0x00, 0x00, 0xc2, 0x04, 0x00};
const DWORD kTypeFlagsLimit = 0x005d70ab;    // imm8 of cmp ecx,14h (index = type - 1)
const DWORD kTypeFlagsTable = 0x005d70d0;    // 21 entries, then 12 bytes int3 padding
const DWORD kTypeFlagsOne = 0x005d70b5;      // mov eax,1; ret 4
const DWORD kTypeFlagsTableOriginal[21] = {
    0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5,
    0x005d70ca, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70bd, 0x005d70bd, 0x005d70bd,
    0x005d70bd, 0x005d70bd, 0x005d70ca};
const BYTE kTypeFlagsPad[8] = {0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc};
const BYTE kFormatPush[] = {0x68, 0xa8, 0x06, 0x86, 0x00};  // tru+0x382182 push "You must add a condition ..." format
const DWORD kFormatPushAt = 0x00782182;

// 0.4: TRMarkupManager vtable 0x855214 slots 0 / 1 / +0x08 (Xbox TU 0x822a0bc8 / 0x822a0c68 / 0x822a0d08)
const DWORD kSlot0At = 0x00855214, kSlot0 = 0x005d6e50;   // thiscall(mgr, box): [box+28h] & 4480010h || 0x741720(box)
const DWORD kSlot1At = 0x00855218, kSlot1 = 0x005d6e80;   // thiscall(mgr, box): [box+28h] & 61870000h || 0x733f60(box)
const DWORD kSlot8At = 0x0085521c, kSlot8 = 0x005dba20;   // thiscall(mgr, out, box, segment), ret 0Ch
const BYTE kSlot0Bytes[] = {0x8b, 0x44, 0x24, 0x04, 0xf7, 0x40, 0x28, 0x10, 0x00, 0x48, 0x04, 0x75, 0x10, 0x50, 0xe8,
                            0xbd, 0xa8, 0x16, 0x00, 0x83, 0xc4, 0x04, 0x84, 0xc0, 0x75, 0x03, 0xc2, 0x04, 0x00, 0xb0,
                            0x01, 0xc2, 0x04, 0x00};
const BYTE kSlot1Bytes[] = {0x8b, 0x44, 0x24, 0x04, 0xf7, 0x40, 0x28, 0x00, 0x00, 0x87, 0x61, 0x75, 0x10, 0x50, 0xe8,
                            0xcd, 0xd0, 0x15, 0x00, 0x83, 0xc4, 0x04, 0x84, 0xc0, 0x75, 0x03, 0xc2, 0x04, 0x00, 0xb0,
                            0x01, 0xc2, 0x04, 0x00};
// slot +0x08 entry up to the branch: ... mov ebx,[ebp+0Ch]; test dword [ebx+28h],20408000h; push esi;
// mov esi,[ebp+8]; push edi; mov edi,[ebx+20h]; je 0x5dbac8 (6 bytes at 0x5dba3c)
const BYTE kSlot8Bytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x24, 0x53, 0x8b, 0x5d, 0x0c, 0xf7, 0x43,
                            0x28, 0x00, 0x80, 0x40, 0x20, 0x56, 0x8b, 0x75, 0x08, 0x57, 0x8b, 0x7b, 0x20, 0x0f, 0x84,
                            0x86, 0x00, 0x00, 0x00};
const DWORD kSlot8Branch = 0x005dba3c;  // je 0x5dbac8 -> jmp Slot8Branch; nop
const DWORD kSlot8Edge = 0x005dba42;    // mask bits set: normal of the poly-line edge (cross product)
const DWORD kSlot8Other = 0x005dbac8;   // no mask bit: the retail fallback (player position based)
const DWORD kWrapperRet = 0x005c3cda;   // return address inside the wrapper tru+0x1c3cc0 (box in ecx)

// 0.5: markup-action selector tru+0x372ca0, second switch (values 601..629, ebx = state parameter 0x19a, esi = agent)
const DWORD kSelSwitch = 0x00772f8a;    // lea eax,[ebx-259h]; cmp eax,1Ch; ja default; movzx edx,byte [eax+77316Ch]; jmp
const BYTE kSelSwitchBytes[] = {0x8d, 0x83, 0xa7, 0xfd, 0xff, 0xff, 0x83, 0xf8, 0x1c, 0x0f, 0x87, 0x01, 0x01, 0x00,
                                0x00, 0x0f, 0xb6, 0x90, 0x6c, 0x31, 0x77, 0x00, 0xff, 0x24, 0x95, 0x28, 0x31, 0x77, 0x00};
const DWORD kSelNext = 0x00772f90;      // cmp eax,1Ch (after the 6-byte lea we detour)
const DWORD kSelIndex608 = 0x00773173;  // byte table entry of 608: 0x10 = the default target
const DWORD kSelDefaultEntry = 0x00773168;   // jump table entry 16 = 0x77309a (default)
const DWORD kSelDefault = 0x0077309a;
const DWORD kSelExit = 0x007730af;      // after the switch: push 191h (state parameter 0x191 ...)
const BYTE kSelExitBytes[] = {0x68, 0x91, 0x01, 0x00, 0x00};
const DWORD kAttachToJumpTarget = 0x00707b90;   // cdecl(const vec4 *, float), PC of TU 0x823fd178
const BYTE kAttachBytes[] = {0xa1, 0x58, 0xdb, 0xfa, 0x00, 0x8b, 0x88, 0x64, 0x0a, 0x00, 0x00, 0x56, 0x8b, 0x71, 0x28,
                             0xe8, 0xec, 0x67, 0xeb, 0xff};
const DWORD kGameTracker = 0x00fadb58;
// tru+0x32ba40: attach point on a box, cdecl(out, box) (e.g. state 572 tru+0x36ddab with box = gameTracker+0xc94)
const DWORD kPointOnBox = 0x0072ba40;
const BYTE kPointOnBoxBytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x18, 0x56, 0x8b, 0x75, 0x08, 0x57,
                                 0x8b, 0x7d, 0x0c};
const DWORD kPointOnBoxNext = 0x0072ba46;

// 0.6: facing function tru+0x2fe7e0 cdecl(out, box, segment, player position) - esi = box, flags class switch at +0x2fe82a
const DWORD kFacingSwitch = 0x006fe82a;   // mov eax,[esi+28h]; and eax,0FFFFFC10h; test eax,8000h; jne 0x6feae4
const char *const kFacingSwitchHex = "8b4628 2510fcffff a900800000 0f85a7020000";
const DWORD kFacingDefault = 0x006feb05;  // retail default: mov eax,[0E7F094h]; mov ecx,[eax+90h]; movaps xmm0,[ecx+10h]
const char *const kFacingDefaultHex = "a194f0e700 8b8890000000 0f284110";
const DWORD kFacingNext = 0x006feb0a;
const DWORD kFacingEdge = 0x006feae4;     // flag 0x8000 case: push 0; lea eax,[esp+104h]; push eax; mov ecx,esi;
const char *const kFacingEdgeHex = "6a00 8d842404010000 50 8bce e8cb51ecff e958010000";   // call 0x5c3cc0; jmp 0x6fec52
// 0.6: attached movement tru+0x370ba0 (flags of the attach box in eax / [esp+1Ch], ebx = agent, edi = 2nd argument)
const DWORD kMoveFlag10 = 0x00770dce;     // test al,10h; je 0x770de1; push edi; push ebx; call 0x753d30; add esp,8; jmp
const char *const kMoveFlag10Hex = "a810 740f 57 53 e8572ffeff 83c408 e99e000000";
const DWORD kMoveWall = 0x00770dd2;
const DWORD kMoveDefault = 0x00770de1;    // mov eax,[0FADB58h]; mov ecx,[eax+0C94h]; push ecx; call 0x741720
const char *const kMoveDefaultHex = "a158dbfa00 8b88940c0000 51 e82e09fdff";
const DWORD kMoveNext = 0x00770de6;
// 0.6: state 420 slot 1 tru+0x371320 (table entry 0x8b0f98) and the building blocks of the TU slot 1 body
const DWORD kS420Slot1 = 0x00771320, kS420Slot1Entry = 0x008b0f98;
const char *const kS420Slot1Hex = "8b4c2404 68d00e7700 e8520a0100 c3";
const DWORD kS420Body = 0x007712db;       // PC slot 0 body = TU slot 0 body (pins the three callees)
const char *const kS420BodyHex = "56 e8efc5feff 83a6f0000000c0 56 e8b2f8ffff a158dbfa00 d980980c0000 83c408 56 51 "
                                 "8b88940c0000 d91c24 51 e863bfffff 83c40c";
const DWORD kTemplate = 0x00781d80;       // thiscall(agent, callback): agent+0x51c = callback, ret 4
const char *const kTemplateHex = "8b442404 89811c050000 c20400";
const DWORD kS420Callback = 0x00770ed0;   // PC of TU 0x8245df50
const DWORD kParamNode = 0x00783f50, kParamBool = 0x00784c20;
const char *const kParamNodeHex = "56 8bf1 8b8620050000 85c0";
const char *const kParamBoolHex = "8b442404 50 e806ffffff 85c0";
const DWORD kPrepare = 0x0075d8d0, kAttachedMove = 0x00770ba0, kAttachedPos = 0x0076d270;
const DWORD kPlayerPtr = 0x00e7f094;
// 0.6: chart log - per-frame update of a machine tru+0x387e60: mov eax,[esi+510h]; push eax; call 0x7857d0
const DWORD kChartTick = 0x00787ebf;
const char *const kChartTickHex = "8b8610050000 50 e805d9ffff";
const DWORD kChartTickNext = 0x00787ec5;

typedef void(__cdecl *AttachFn)(const float *vec, float value);
typedef void(__fastcall *TemplateFn)(void *agent, void *, DWORD callback);
typedef void *(__fastcall *ParamNodeFn)(void *agent, void *, int id);
typedef char(__fastcall *ParamBoolFn)(void *node, void *, int id, char *out);
typedef void(__cdecl *AgentFn)(void *agent);
typedef void(__cdecl *AttachedPosFn)(void *box, float value, void *agent);
typedef int(__cdecl *DoppelgangerFn)();
typedef int(__fastcall *GetTypeFn)(void *ctx, void *unused);   // thiscall getter, no stack arguments
typedef char(__thiscall *BoxPredFn)(void *mgr, void *box);

// options (TruRockVein.ini, section [RockVein])
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info + first unhandled ids, 2 result changes, 3 every call
int g_logUnhandled = 1;
int g_type607 = 23, g_type608 = 22;     // Xbox title update values
int g_logBadValues = 1;                 // 0.2: markup values outside 601..628 (data in the wrong byte order)
int g_logDefaultConditions = 1;         // 0.2: condition ids answered by the default handler
int g_markupTypes = 1;                  // 0.3: accept the title-update markup types 22 / 23 (flag class 1)
int g_markupSlots = 1;                  // 0.4: TU type checks in TRMarkupManager slots 0 / 1 / +0x08
int g_nullBoxGuard = 1;                 // 0.4: diagnostic guard for slot +0x08 with box 0 (logs the caller)
DWORD g_slot8Orig = kSlot8, g_slot8Edge = kSlot8Edge, g_slot8Other = kSlot8Other;
volatile LONG g_slotHits[3] = {0, 0, 0};   // slot 0 / 1 / +0x08 answered by the TU type check
volatile LONG g_nullBoxCalls = 0;
DWORD g_nullBoxCallers[16];
int g_markupAction608 = 1;              // 0.5: TU markup action 608 (attach to the jump target)
DWORD g_selNext = kSelNext, g_selExit = kSelExit, g_pointOnBoxNext = kPointOnBoxNext;
volatile LONG g_action608Calls = 0;
int g_attachGeometry = 1;               // 0.6: TU type-22 facing (0x824006a8) and attached movement (0x8245d6c8)
int g_state420Slot1 = 1;                // 0.6: TU state 420 slot 1 (0x8245e450)
int g_chartLog = 1;                     // 0.6: log the player's chart record changes (LogLevel >= 1)
int g_chartFrom = 1470, g_chartTo = 1510;
int g_jumpGeometry = 1;                 // 0.8: TU type-22 branches of the jump-off / fall geometry ([RockVein] JumpGeometry)
int g_skipGeometry = 1;                 // 0.9: TU type-22 branch of tru+0x34d390 (TU 0x8242a7c8) ([RockVein] SkipGeometry)
int g_sapTranslate = 1;                 // 0.10: SweepAndPrune limits as the TU ([SweepAndPrune] Translate)
int g_ledgeCorner = 1;                  // 0.11: TU ledge-corner nudge (TU 0x8242eeac) ([LedgeCorner] Translate)
DWORD g_facingNext = kFacingNext, g_facingEdge = kFacingEdge, g_moveNext = kMoveNext, g_moveWall = kMoveWall;
DWORD g_chartTickNext = kChartTickNext;
volatile LONG g_facingHits = 0, g_moveHits = 0, g_slot1Calls = 0, g_slot1Runs = 0, g_chartLines = 0;
// (0.7: the per-machine last record is g_chartLasts, next to ChartTick)
DoppelgangerFn g_doppelganger = nullptr;
int g_doppelgangerLooked = 0;
DWORD g_dispatchNext = kDispatchNext;
DWORD g_condDefaultNext = kCondDefaultNext;
volatile LONG g_valueSeen[29];          // 601..628 first-call flags (index value - 600)
volatile LONG g_badSeen = 0;            // number of distinct bad values logged
WORD g_badValues[64];
volatile LONG g_defaultSeen[65536 / 32];   // bit per condition id
volatile LONG g_defaultCount = 0;

char g_logPath[MAX_PATH];
char g_dir[MAX_PATH];                   // folder of the plugin (= game folder), with trailing backslash
CRITICAL_SECTION g_logLock;
DWORD g_exitAddress = kExit;            // jump targets read by the stubs
DWORD g_defaultAddress = kDefault;
int g_last[2] = {-2, -2};               // last logged (type, result) per condition, packed
LONG g_calls[2] = {0, 0};
LONG g_unhandledSeen[64];               // per table index: calls of an unhandled id

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

int SafeType(void *ctx, int *ok) {
    __try {
        *ok = 1;
        return reinterpret_cast<GetTypeFn>(kGetType)(ctx, nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *ok = 0;
        return -1;
    }
}

// called from the stubs on the game thread: 1 if the context's markup has the wanted type (TU 607 / 608 semantics)
int __stdcall CheckType(void *ctx, int id, int want) {
    int slot = id == 607 ? 0 : 1;
    LONG calls = InterlockedIncrement(&g_calls[slot]);
    int type = -1, ok = 1, result = 0;
    if (ctx) {
        type = SafeType(ctx, &ok);
        result = ok && type == want;
    }
    int packed = (type & 0xff) | (result << 8) | (ctx ? 0 : 0x10000) | (ok ? 0 : 0x20000);
    if (g_logLevel >= 3)
        Log(3, "condition %d: ctx 0x%08lx type %d -> %d (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result, calls);
    else if (packed != g_last[slot])
        Log(2, "condition %d: ctx 0x%08lx type %d -> %d%s (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result,
            ok ? "" : " (read failed)", calls);
    if (calls == 1) Log(1, "condition %d is now evaluated (first call: type %d -> %d)", id, type, result);
    g_last[slot] = packed;
    return result;
}

void __stdcall LogUnhandled(int index) {
    if (index < 0 || index >= 64) return;
    LONG n = InterlockedIncrement(&g_unhandledSeen[index]);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))   // first call, then 2, 4, 8 ... at level 2
        Log(1, "unhandled markup condition %d (call %ld) - not implemented on PC", 601 + index, n);
}

// jump-table targets: run inside SCCondTest_MarkupType's frame (after its push ebx / push esi), so the context
// argument is [esp+1Ch]; after pushad (32 bytes) it is [esp+32+1Ch].
__declspec(naked) void Cond607() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type607]
        push 607
        push eax
        call CheckType
        mov [esp + 16], eax             // saved EBX of pushad -> bl = result
        popad
        jmp dword ptr [g_exitAddress]
    }
}

__declspec(naked) void Cond608() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type608]
        push 608
        push eax
        call CheckType
        mov [esp + 16], eax
        popad
        jmp dword ptr [g_exitAddress]
    }
}

// for the other unhandled ids: eax = id - 601 (the dispatch index) - log, then the original default case
__declspec(naked) void CondUnhandled() {
    __asm {
        pushad
        push eax
        call LogUnhandled
        popad
        jmp dword ptr [g_defaultAddress]
    }
}

// ---- 0.2 probes (read only; the game's own code runs unchanged after them) ----

bool ReadRecord(const BYTE *record, WORD *out4, BYTE *flags) {
    __try {
        for (int i = 0; i < 3; ++i) out4[i] = reinterpret_cast<const WORD *>(record)[i];
        *flags = record[6];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// from the dispatch detour: value = the markup subtest SCCondTest_MarkupType switches on (> 600 here)
void __stdcall CheckValue(int value, const BYTE *record) {
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (value >= 601 && value <= 628) {
        if (g_logLevel >= 2 && InterlockedExchange(&g_valueSeen[value - 600], 1) == 0) {
            ReadRecord(record, r, &fl);
            Log(2, "markup subtest %d first evaluated (record {%u, %u, %u, flags %u})", value, r[0], r[1], r[2], fl);
        }
        return;
    }
    if (value == 1000 || !g_logBadValues) return;
    LONG n = g_badSeen;                                 // game thread only; the list is just a log filter
    for (LONG i = 0; i < n && i < 64; ++i)
        if (g_badValues[i] == static_cast<WORD>(value)) return;
    if (n >= 64) return;
    g_badValues[n] = static_cast<WORD>(value);
    g_badSeen = n + 1;
    bool ok = ReadRecord(record, r, &fl);
    Log(1, "markup record value %d (0x%04x) is no subtest 601..628: record at 0x%08lx {%u, %u, %u, flags %u}%s - "
           "state chart data in the wrong byte order? (Xbox order of %d would be %d)",
        value, value & 0xffff, reinterpret_cast<DWORD>(record), r[0], r[1], r[2], fl, ok ? "" : " (read failed)", value,
        ((value & 0xff) << 8) | ((value >> 8) & 0xff));
}

// from the default-handler detour: agent = 1st argument, record = 3rd (as tru+0x382154 / +0x382160 read them)
void __stdcall LogDefault(const BYTE *agent, const BYTE *record) {
    if (!g_logDefaultConditions) return;
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (!ReadRecord(record, r, &fl)) return;
    int id = static_cast<short>(r[1]);
    LONG bit = 1L << (id & 31);
    if (InterlockedOr(&g_defaultSeen[(id & 0xffff) >> 5], bit) & bit) return;
    char state[64] = "?";
    WORD proc = 0;
    __try {
        const BYTE *sm = *reinterpret_cast<const BYTE *const *>(agent + 0x510);
        const char *name = sm ? *reinterpret_cast<const char *const *>(sm + 0x24) : nullptr;
        if (name) { strncpy_s(state, sizeof(state), name, _TRUNCATE); }
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(agent + 4);
        if (p) proc = *reinterpret_cast<const WORD *>(p + 2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    LONG n = InterlockedIncrement(&g_defaultCount);
    Log(1, "condition %d answered by the default handler (true): record {%u, %d, %u, flags %u}, agent 0x%08lx "
           "(AnimProcID %u) in state \"%s\" [%ld distinct]", id, r[0], id, r[2], fl, reinterpret_cast<DWORD>(agent), proc,
        state, n);
}

// detour of `sub eax,259h` (5 bytes) at tru+0x38288d: eax = value, esi = record (tru+0x382812)
__declspec(naked) void DispatchProbe() {
    __asm {
        pushad
        push esi
        push eax
        call CheckValue
        popad
        sub eax, 0x259
        jmp dword ptr [g_dispatchNext]
    }
}

// detour of `sub esp,204h` (6 bytes) at the default handler's entry: [esp+4] agent, [esp+0Ch] record
__declspec(naked) void DefaultProbe() {
    __asm {
        pushad
        push dword ptr [esp + 32 + 0x0c]      // record
        push dword ptr [esp + 32 + 0x04 + 4]  // agent (one push above)
        call LogDefault
        popad
        sub esp, 0x204
        jmp dword ptr [g_condDefaultNext]
    }
}

bool WriteJump(DWORD at, const void *to, int length) {
    BYTE code[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

void InstallProbes() {
    if (g_logBadValues || g_logLevel >= 2) {
        // the dispatch bytes were verified in Start (kDispatchBytes starts with the 5-byte sub eax,259h)
        if (WriteJump(kDispatch, &DispatchProbe, 5))
            Log(1, "probe: markup values outside 601..628 are logged (detour at 0x%08lx)", kDispatch);
        else
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kDispatch, GetLastError());
    }
    if (g_logDefaultConditions) {
        // TruDoppelganger.asi verifies the first bytes of this handler before it registers its ids; the ASI loader
        // loads alphabetically, so it normally runs first - if its file is there but it is not loaded yet, our detour
        // would make its check fail: then the probe stays off
        char other[MAX_PATH];
        _snprintf_s(other, sizeof(other), _TRUNCATE, "%sTruDoppelganger.asi", g_dir);
        if (GetFileAttributesA(other) != INVALID_FILE_ATTRIBUTES && !GetModuleHandleA("TruDoppelganger.asi")) {
            Log(0, "default-condition probe off: TruDoppelganger.asi is present but not loaded yet (load order)");
            return;
        }
        if (!BytesAt(kCondDefault, kCondDefaultBytes, sizeof(kCondDefaultBytes)) ||
            !BytesAt(kFormatPushAt, kFormatPush, sizeof(kFormatPush))) {
            Log(0, "condition default handler at 0x%08lx does not match - default-condition probe off", kCondDefault);
        } else if (WriteJump(kCondDefault, &DefaultProbe, 6)) {
            Log(1, "probe: conditions answered by the default handler are logged (detour at 0x%08lx)", kCondDefault);
        } else {
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kCondDefault, GetLastError());
        }
    }
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruRockVein.ini", dir);
    g_enabled = GetPrivateProfileIntA("RockVein", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("RockVein", "LogLevel", 1, ini);
    g_logUnhandled = GetPrivateProfileIntA("RockVein", "LogUnhandled", 1, ini);
    g_type607 = GetPrivateProfileIntA("RockVein", "Type607", 23, ini);
    g_type608 = GetPrivateProfileIntA("RockVein", "Type608", 22, ini);
    g_logBadValues = GetPrivateProfileIntA("RockVein", "LogBadValues", 1, ini);
    g_logDefaultConditions = GetPrivateProfileIntA("RockVein", "LogDefaultConditions", 1, ini);
    g_markupTypes = GetPrivateProfileIntA("RockVein", "MarkupTypes", 1, ini);
    g_markupSlots = GetPrivateProfileIntA("RockVein", "MarkupSlots", 1, ini);
    g_nullBoxGuard = GetPrivateProfileIntA("RockVein", "NullBoxGuard", 1, ini);
    g_markupAction608 = GetPrivateProfileIntA("RockVein", "MarkupAction608", 1, ini);
    g_attachGeometry = GetPrivateProfileIntA("RockVein", "AttachGeometry", 1, ini);
    g_state420Slot1 = GetPrivateProfileIntA("RockVein", "State420Slot1", 1, ini);
    g_chartLog = GetPrivateProfileIntA("RockVein", "ChartLog", 1, ini);
    g_chartFrom = GetPrivateProfileIntA("RockVein", "ChartLogFrom", 1470, ini);
    g_chartTo = GetPrivateProfileIntA("RockVein", "ChartLogTo", 1510, ini);
    g_jumpGeometry = GetPrivateProfileIntA("RockVein", "JumpGeometry", 1, ini);
    g_skipGeometry = GetPrivateProfileIntA("RockVein", "SkipGeometry", 1, ini);
    g_sapTranslate = GetPrivateProfileIntA("SweepAndPrune", "Translate", 1, ini);   // 0.10
    g_ledgeCorner = GetPrivateProfileIntA("LedgeCorner", "Translate", 1, ini);      // 0.11
}

// 0.3: the title update's markup types 22 / 23 -> flag class 1 (Xbox TU 0x822a12e8 table entries 21 / 22 = li r3,1).
// Two new table entries in the int3 padding right after the 21-entry table, then the bound 0x14 -> 0x16.
bool PatchMarkupTypes() {
    if (*reinterpret_cast<const DWORD *>(kTypeFlagsSlot) != kTypeFlags || !BytesAt(kTypeFlags, kTypeFlagsBytes,
            sizeof(kTypeFlagsBytes)) || !BytesAt(kTypeFlagsTable, reinterpret_cast<const BYTE *>(kTypeFlagsTableOriginal),
            sizeof(kTypeFlagsTableOriginal)) || !BytesAt(kTypeFlagsTable + sizeof(kTypeFlagsTableOriginal),
            kTypeFlagsPad, sizeof(kTypeFlagsPad))) {
        Log(0, "markup type mapper at 0x%08lx does not match - markup types 22 / 23 not added", kTypeFlags);
        return false;
    }
    BYTE *from = reinterpret_cast<BYTE *>(kTypeFlags);
    DWORD length = kTypeFlagsTable + sizeof(kTypeFlagsTableOriginal) + sizeof(kTypeFlagsPad) - kTypeFlags;
    DWORD old = 0;
    if (!VirtualProtect(from, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) - markup types 22 / 23 not added", GetLastError());
        return false;
    }
    DWORD *table = reinterpret_cast<DWORD *>(kTypeFlagsTable);
    table[21] = kTypeFlagsOne;                 // type 22
    table[22] = kTypeFlagsOne;                 // type 23
    *reinterpret_cast<BYTE *>(kTypeFlagsLimit) = 0x16;
    DWORD dummy = 0;
    VirtualProtect(from, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), from, length);
    Log(1, "markup types 22 / 23 accepted (flag class 1, as the title update; mapper 0x%08lx)", kTypeFlags);
    return true;
}

// ---- 0.4: title-update type checks in TRMarkupManager slots 0 / 1 / +0x08 ----

// TU slot 0 0x822a0bc8 / slot 1 0x822a0c68: (flags & mask) || predicate(box) || type == 22 / 23
void LogSlotHit(int slot, void *box, int type) {
    LONG n = InterlockedIncrement(&g_slotHits[slot]);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "markup slot %s true by the title-update type check: box 0x%08lx type %d (call %ld)",
            slot == 0 ? "0 (wall, type 22)" : slot == 1 ? "1 (type 23)" : "+0x08 (edge normal, type 22)",
            reinterpret_cast<DWORD>(box), type, n);
}

char __fastcall Slot0(void *mgr, void *, void *box) {
    if (reinterpret_cast<BoxPredFn>(kSlot0)(mgr, box)) return 1;
    int ok = 0, type = SafeType(box, &ok);
    if (!ok || type != 22) return 0;
    LogSlotHit(0, box, type);
    return 1;
}

char __fastcall Slot1(void *mgr, void *, void *box) {
    if (reinterpret_cast<BoxPredFn>(kSlot1)(mgr, box)) return 1;
    int ok = 0, type = SafeType(box, &ok);
    if (!ok || type != 23) return 0;
    LogSlotHit(1, box, type);
    return 1;
}

void __stdcall LogSlot8Edge(void *box) { LogSlotHit(2, box, 22); }

// replaces `je 0x5dbac8` at tru+0x1dba3c; flags still from `test [ebx+28h],20408000h`, ebx = box, edi = [ebx+20h].
// TU 0x822a0d40..0x822a0d68: mask bits set or type 22 -> edge path, else the retail fallback.
__declspec(naked) void Slot8Branch() {
    __asm {
        jne edge
        push eax
        mov eax, [ebx + 0x24]
        test eax, eax
        jz use20
        movsx eax, byte ptr [eax + 0x4d]
        jmp compare
    use20:
        test edi, edi
        jz other_pop
        movsx eax, byte ptr [edi + 0x33]
    compare:
        cmp eax, 22
        jne other_pop
        pushad
        push ebx
        call LogSlot8Edge
        popad
        pop eax
    edge:
        jmp dword ptr [g_slot8Edge]
    other_pop:
        pop eax
        jmp dword ptr [g_slot8Other]
    }
}

// diagnostic: who calls slot +0x08 with box 0 (the crash of test 48i at tru+0x1dba2d)
void __stdcall LogNullBox(DWORD ret, DWORD outer) {
    LONG n = InterlockedIncrement(&g_nullBoxCalls);
    DWORD caller = ret == kWrapperRet ? outer : ret;   // through the wrapper tru+0x1c3cc0: its caller
    bool known = false;
    for (int i = 0; i < 16; ++i) {
        if (g_nullBoxCallers[i] == caller) { known = true; break; }
        if (!g_nullBoxCallers[i]) { g_nullBoxCallers[i] = caller; break; }
    }
    DWORD gt = 0, a64 = 0, c94 = 0;
    __try {
        gt = *reinterpret_cast<const DWORD *>(0x00fadb58);
        if (gt) { a64 = *reinterpret_cast<const DWORD *>(gt + 0xa64); c94 = *reinterpret_cast<const DWORD *>(gt + 0xc94); }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (!known || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "markup slot +0x08 called with box 0 from 0x%08lx (return 0x%08lx, call %ld): gameTracker 0x%08lx "
               "+0xa64 0x%08lx +0xc94 0x%08lx - zero vector returned instead of the crash", caller, ret, n, gt, a64, c94);
}

// vtable slot +0x08: [esp+4] out, [esp+8] box, [esp+0Ch] segment; via the wrapper [esp+14h] = the wrapper's caller
__declspec(naked) void Slot8Guard() {
    __asm {
        cmp dword ptr [esp + 8], 0
        je null_box
        jmp dword ptr [g_slot8Orig]
    null_box:
        pushad
        push dword ptr [esp + 32 + 0x14]
        push dword ptr [esp + 32 + 4]
        call LogNullBox
        popad
        mov eax, [esp + 4]
        mov dword ptr [eax], 0
        mov dword ptr [eax + 4], 0
        mov dword ptr [eax + 8], 0
        mov dword ptr [eax + 12], 0
        ret 0x0c
    }
}

// ---- 0.5: markup action 608 (TU 0x82463a28) and the point-on-box guard ----

void ReadAttachState(DWORD *gt, DWORD *a64, DWORD *c94) {
    *gt = *a64 = *c94 = 0;
    __try {
        *gt = *reinterpret_cast<const DWORD *>(kGameTracker);
        if (*gt) { *a64 = *reinterpret_cast<const DWORD *>(*gt + 0xa64); *c94 = *reinterpret_cast<const DWORD *>(*gt + 0xc94); }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

// TU selector case 608: gameTracker+0xa64 != 0 -> PLAYER_AttachToJumpTarget(zero vector 0x8207db30, 0.0f [0x8207d538]);
// then gameTracker+0xca0 = gameTracker+0xd90 (16 bytes; both fields are the same on PC: +0xca0 is written by the attach
// functions tru+0x307530 = TU 0x823fcb28, +0xd90 by the player process tru+0x31ffe0 = retail 0x8240b560)
void __stdcall Action608(const BYTE *agent) {
    LONG n = InterlockedIncrement(&g_action608Calls);
    DWORD gt = *reinterpret_cast<const DWORD *>(kGameTracker);
    DWORD box = gt ? *reinterpret_cast<const DWORD *>(gt + 0xa64) : 0;
    if (box) {
        __declspec(align(16)) float zero[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        reinterpret_cast<AttachFn>(kAttachToJumpTarget)(zero, 0.0f);
        gt = *reinterpret_cast<const DWORD *>(kGameTracker);
        memcpy(reinterpret_cast<void *>(gt + 0xca0), reinterpret_cast<const void *>(gt + 0xd90), 16);
    }
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0)) {
        DWORD g = 0, a64 = 0, c94 = 0;
        ReadAttachState(&g, &a64, &c94);
        float f[4] = {0, 0, 0, 0}, d[4] = {0, 0, 0, 0};
        int id = -1, type = -1;
        DWORD second = 0;
        char hex[3 * 0x50 + 1] = "";
        __try {
            if (g) { memcpy(f, reinterpret_cast<const void *>(g + 0xcc0), 16); memcpy(d, reinterpret_cast<const void *>(g + 0xcb0), 16); }
            const BYTE *rec = box ? *reinterpret_cast<const BYTE *const *>(box + 0x20) : nullptr;   // file record
            if (rec) { id = *reinterpret_cast<const WORD *>(rec + 0x2e); type = static_cast<signed char>(rec[0x33]); }
            // 0.7: in 48l the file record was id 2326 / type 0 and the type 22 came from the second markup +0x24
            // (type byte +0x4d) - dump its first 0x50 bytes once so the owner can be found
            second = box ? *reinterpret_cast<const DWORD *>(box + 0x24) : 0;
            if (second && n == 1)
                for (int i = 0; i < 0x50; ++i)
                    _snprintf_s(hex + 3 * i, sizeof(hex) - 3 * i, _TRUNCATE, "%02x ", reinterpret_cast<const BYTE *>(second)[i]);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        if (n == 1 && second) Log(1, "markup action 608: box 0x%08lx second markup +0x24 = 0x%08lx: %s", box, second, hex);
        // 0.6: +0xcc0 = facing from tru+0x2fe7e0 (type 22: edge normal of segment 0), +0xcb0 = box line direction;
        // record id names the owner object (DLC 2 type-22 ids: gooconverter 2404, machine_column 2682 / 2689 (48i data
        // fix), piston_square 2690 / 2691, piston_a 2692, piston_c 2693)
        Log(1, "markup action 608 (attach to jump target, title update) call %ld: agent 0x%08lx, box 0x%08lx (record id "
               "%d, type %d) -> gameTracker+0xc94 0x%08lx%s; facing +0xcc0 (%.3f %.3f %.3f), line +0xcb0 (%.3f %.3f %.3f)",
            n, reinterpret_cast<DWORD>(agent), box, id, type, c94, box ? "" : " (no box, nothing done)", f[0], f[1], f[2],
            d[0], d[1], d[2]);
    }
}

// replaces `lea eax,[ebx-259h]` (6 bytes) at tru+0x372f8a: ebx = action value, esi = agent
__declspec(naked) void SelectorProbe() {
    __asm {
        cmp ebx, 608
        jne other
        pushad
        push esi
        call Action608
        popad
        jmp dword ptr [g_selExit]
    other:
        lea eax, [ebx - 0x259]
        jmp dword ptr [g_selNext]
    }
}

void __stdcall LogNullPoint(DWORD ret) {
    LONG n = InterlockedIncrement(&g_nullBoxCalls);
    DWORD gt, a64, c94;
    ReadAttachState(&gt, &a64, &c94);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "attach point tru+0x32ba40 called with box 0 from 0x%08lx (call %ld): gameTracker 0x%08lx +0xa64 0x%08lx "
               "+0xc94 0x%08lx - zero vector returned instead of the crash", ret, n, gt, a64, c94);
}

// tru+0x32ba40 cdecl(out, box): [esp+4] out, [esp+8] box; returns out
__declspec(naked) void PointOnBoxGuard() {
    __asm {
        cmp dword ptr [esp + 8], 0
        je null_box
        push ebp
        mov ebp, esp
        and esp, 0xfffffff0
        jmp dword ptr [g_pointOnBoxNext]
    null_box:
        pushad
        push dword ptr [esp + 32]
        call LogNullPoint
        popad
        mov eax, [esp + 4]
        mov dword ptr [eax], 0
        mov dword ptr [eax + 4], 0
        mov dword ptr [eax + 8], 0
        mov dword ptr [eax + 12], 0
        ret
    }
}

void PatchSelector() {
    if (!BytesAt(kSelSwitch, kSelSwitchBytes, sizeof(kSelSwitchBytes)) || !BytesAt(kSelExit, kSelExitBytes, sizeof(kSelExitBytes)) ||
        *reinterpret_cast<const BYTE *>(kSelIndex608) != 0x10 || *reinterpret_cast<const DWORD *>(kSelDefaultEntry) != kSelDefault ||
        !BytesAt(kAttachToJumpTarget, kAttachBytes, sizeof(kAttachBytes))) {
        Log(0, "markup-action selector at 0x%08lx does not match - markup action 608 not added", kSelSwitch);
        return;
    }
    if (WriteJump(kSelSwitch, &SelectorProbe, 6))
        Log(1, "markup action 608 added (title-update case: attach to the jump target; selector 0x%08lx)", kSelSwitch);
    else
        Log(0, "markup action 608 not written (VirtualProtect %lu)", GetLastError());
}

void PatchPointOnBox() {
    if (!BytesAt(kPointOnBox, kPointOnBoxBytes, sizeof(kPointOnBoxBytes))) {
        Log(0, "attach point function at 0x%08lx does not match - its null-box guard is off", kPointOnBox);
        return;
    }
    if (WriteJump(kPointOnBox, &PointOnBoxGuard, 6))
        Log(1, "null-box guard on the attach point function 0x%08lx (diagnostic)", kPointOnBox);
    else
        Log(0, "null-box guard at 0x%08lx not written (VirtualProtect %lu)", kPointOnBox, GetLastError());
}

// ---- 0.6: title-update attach geometry for type 22, state 420 slot 1, chart log ----

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[96];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

bool IsType22(void *box) {
    if (!box) return false;
    int ok = 0, type = SafeType(box, &ok);
    return ok && type == 22;
}

bool LogNow(LONG n) { return n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0); }

// ---- 0.10: SweepAndPrune limits as the title update (TU owner constructor 0x8227b9f0) ----
// Every byte below is pinned in work\asi\rv10\prechecks_v10.txt (tools/pe_bytes_check.py on the Steam exe).
const DWORD kSapOwnerPtr = 0x00db94cc;      // MarkupManager (zero-initialised .data; 0 until the game init builds it)
const DWORD kSapOwnerPtr2 = 0x00e7f060;     // the same pointer, second global
const DWORD kSapCtor = 0x005be3a0;          // owner ctor: push ebx; push esi; push edi; mov esi,ecx; xor edi,edi
const char *const kSapCtorHex = "53 56 57 8bf1 33ff";
const DWORD kSapArgs = 0x005be3a7;          // push 0C8h; push 3E8h = SAP create(1000, 200)
const BYTE kSapArgsOld[] = {0x68, 0xc8, 0x00, 0x00, 0x00, 0x68, 0xe8, 0x03, 0x00, 0x00};
const BYTE kSapArgsNew[] = {0x68, 0xf4, 0x01, 0x00, 0x00, 0x68, 0xb8, 0x0b, 0x00, 0x00};   // create(3000, 500)
const DWORD kSapMid = 0x005be3b1;           // vtable 0x853f54; [esi+4] = 0; [esi+1Ch] = 0; [esi+18h] = 1000 proxies
const char *const kSapMidHex = "c706543f8500 897e04 897e1c c74618e8030000";
const DWORD kSapField = 0x005be3c4;         // mov dword ptr [esi+20h],0C8h (copy of the pair parameter, never read)
const BYTE kSapFieldOld[] = {0xc7, 0x46, 0x20, 0xc8, 0x00, 0x00, 0x00};
const BYTE kSapFieldNew[] = {0xc7, 0x46, 0x20, 0xf4, 0x01, 0x00, 0x00};                     // 500 (TU [this+0x24])
const DWORD kSapCall = 0x005be3cb;          // call SAP create 0x46d180; mov [esi+4],eax (the core)
const char *const kSapCallHex = "e8b0edeaff 894604";
const DWORD kSapGetter = 0x005be390;        // mov eax,[0xdb94cc]; ret
const char *const kSapGetterHex = "a1cc94db00 c3";
const DWORD kSapOwnerStore = 0x005d9ec6;    // owner -> [0xe7f060] and [0xdb94cc] (in tru+0x1d9e70, called by tru+0x1df390)
const char *const kSapOwnerStoreHex = "893560f0e700 8935cc94db00";
const DWORD kSapCoreCaps = 0x0046c880;      // SAP core ctor: [core+24h] = N (boxes), [core+2Ch] = M (pair parameter)
const char *const kSapCoreCapsHex = "897e24 89462c";
const DWORD kSapCoreMem = 0x0046c895;       // SAP core ctor: [core+20h] = 1 (memory counter, then += each pool)
const char *const kSapCoreMemHex = "c7462001000000";
// 0 = PC limits kept (Translate=0), 1 = written in DllMain, 2 = the exe already has (3000, 500), -1 = checks failed
int g_sapState = 0;
int g_sapChecked = 0;                       // the first-frame control ran (game thread only)

// first machine update (game thread, from ChartTick): one control line - the values the core and the owner really hold
void SapControl() {
    DWORD owner = 0, core = 0, n = 0, m = 0, mem = 0, field = 0, proxies = 0;
    __try {
        owner = *reinterpret_cast<const DWORD *>(kSapOwnerPtr);
        if (!owner) return;                 // not built yet: try again on the next update
        core = *reinterpret_cast<const DWORD *>(owner + 4);
        if (!core) return;
        proxies = *reinterpret_cast<const DWORD *>(owner + 0x18);
        field = *reinterpret_cast<const DWORD *>(owner + 0x20);
        n = *reinterpret_cast<const DWORD *>(core + 0x24);
        m = *reinterpret_cast<const DWORD *>(core + 0x2c);
        mem = *reinterpret_cast<const DWORD *>(core + 0x20);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_sapChecked = 1;
        Log(0, "SweepAndPrune control: reading MarkupManager 0x%08lx / core 0x%08lx failed", owner, core);
        return;
    }
    g_sapChecked = 1;
    const bool tu = g_sapState == 1 || g_sapState == 2;
    const DWORD wantN = tu ? 3000 : 1000, wantM = tu ? 500 : 200, wantField = tu ? 500 : 200;
    const DWORD wantMem = 1 + 204 * wantN + 16 * wantM;   // 1 + 80 N (boxes) + 16 M (pairs) + 4 N + 120 N (endpoints)
    const bool ok = n == wantN && m == wantM && mem == wantMem && field == wantField && proxies == 1000;
    char verdict[128];
    if (g_sapState < 0)
        _snprintf_s(verdict, sizeof(verdict), _TRUNCATE, "load checks failed, nothing written");
    else if (ok)
        _snprintf_s(verdict, sizeof(verdict), _TRUNCATE, "%s", tu ? "as the title update (3000 / 500)" : "PC limits (Translate=0)");
    else
        _snprintf_s(verdict, sizeof(verdict), _TRUNCATE, "NOT as expected (%lu / %lu / %lu / %lu, proxies 1000)", wantN,
                    wantM, wantMem, wantField);
    Log(ok && g_sapState >= 0 ? 1 : 0, "SweepAndPrune control (first frame): MarkupManager 0x%08lx, core 0x%08lx: boxes "
        "+0x24 = %lu, pair parameter +0x2c = %lu (%lu pair links), memory +0x20 = %lu, owner +0x20 = %lu, proxies %lu -> %s",
        owner, core, n, m, 2 * m, mem, field, proxies, verdict);
}

// TU 0x824009a0..0x82400a04: before the retail default, type == 22 -> facing = manager slot +0x08(box, segment 0)
int __stdcall FacingType22(void *box) {
    if (!IsType22(box)) return 0;
    LONG n = InterlockedIncrement(&g_facingHits);
    if (LogNow(n))
        Log(1, "attach facing (tru+0x2fe7e0 = TU 0x824006a8): type-22 box 0x%08lx -> edge normal of segment 0, as the "
               "title update (call %ld)", reinterpret_cast<DWORD>(box), n);
    return 1;
}

// replaces `mov eax,[0E7F094h]` (5 bytes) at tru+0x2feb05, the first instruction of the retail default; esi = box
__declspec(naked) void FacingDefault() {
    __asm {
        pushad
        push esi
        call FacingType22
        test eax, eax
        popad
        jnz edge
        mov eax, dword ptr ds:[0x00e7f094]
        jmp dword ptr [g_facingNext]
    edge:
        jmp dword ptr [g_facingEdge]
    }
}

// TU 0x8245d904..0x8245d938: flag bit 0x10 clear -> type([gameTracker+0xc94]) == 22 -> the wall handler 0x8244c2c8
// (the TU reads the box without a null test; a null attach box here takes the retail path)
int __stdcall MoveType22() {
    DWORD gt = 0, a64 = 0, c94 = 0;
    ReadAttachState(&gt, &a64, &c94);
    if (!IsType22(reinterpret_cast<void *>(c94))) return 0;
    LONG n = InterlockedIncrement(&g_moveHits);
    if (LogNow(n))
        Log(1, "attached movement (tru+0x370ba0 = TU 0x8245d6c8): attach box 0x%08lx type 22 -> wall handler tru+0x353d30, "
               "as the title update (call %ld)", c94, n);
    return 1;
}

// replaces `mov eax,[0FADB58h]` (5 bytes) at tru+0x370de1 (start of the wall-predicate path); ebx / edi as for +0x370dd2
__declspec(naked) void MoveDefault() {
    __asm {
        pushad
        call MoveType22
        test eax, eax
        popad
        jnz wall
        mov eax, dword ptr ds:[0x00fadb58]
        jmp dword ptr [g_moveNext]
    wall:
        jmp dword ptr [g_moveWall]
    }
}

int Doppelganger() {
    if (!g_doppelgangerLooked) {
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_doppelganger = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        g_doppelgangerLooked = 1;
        if (!g_doppelganger)
            Log(0, "TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - doppelganger mode (TU gameTracker+0x1244) "
                   "reads 0, state 420 slot 1 keeps the retail behaviour");
    }
    return g_doppelganger ? g_doppelganger() : 0;
}

// state 420 slot 1 = TU 0x8245e450 (cdecl(agent) like every PC state slot)
void __cdecl State420Slot1(BYTE *agent) {
    // TU: agent+0x52c = 0x8245df50 - the PC's slot 1 does this through the template (agent+0x51c = tru+0x370ed0)
    reinterpret_cast<TemplateFn>(kTemplate)(agent, nullptr, kS420Callback);
    LONG n = InterlockedIncrement(&g_slot1Calls);
    int dg = Doppelganger();
    char on = 0;
    DWORD box = 0;
    if (dg) {
        void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, nullptr, 0x19e);   // TU 0x823d7230
        if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, nullptr, 0x19e, &on);
    }
    if (dg && on) {
        reinterpret_cast<AgentFn>(kPrepare)(agent);                                     // TU 0x8245ce48
        *reinterpret_cast<DWORD *>(agent + 0xf0) &= 0xffffffc0;                         // rlwinm 0, 0, 0x19
        reinterpret_cast<AgentFn>(kAttachedMove)(agent);                                // TU 0x8245d6c8
        const BYTE *gt = *reinterpret_cast<const BYTE *const *>(kGameTracker);
        box = *reinterpret_cast<const DWORD *>(gt + 0xc94);
        if (box)                                                                         // TU 0x8245d3a8(box, f, agent)
            reinterpret_cast<AttachedPosFn>(kAttachedPos)(reinterpret_cast<void *>(box),
                                                          *reinterpret_cast<const float *>(gt + 0xc98), agent);
        InterlockedIncrement(&g_slot1Runs);
    }
    if (LogNow(n))
        Log(1, "state 420 slot 1 (TU 0x8245e450) call %ld: doppelganger %d, parameter 0x19e %d -> attached movement %s "
               "(box 0x%08lx, %ld runs)", n, dg, on, dg && on ? (box ? "run" : "run, position skipped: attach box 0") :
               "not run (retail part only)", box, g_slot1Runs);
}

// ---- 0.8: title-update type-22 branches of the jump-off / fall geometry (counters reported from ChartTick) ----
// Hit counters, written by the naked stubs below with `lock inc` (no call inside stubs that run while the x87 stack
// may hold a value); ChartTick logs them on the game thread: first hit, then at LogLevel 2 every power of two.
// 0.9: 5 = tru+0x34d390 (TU 0x8242a7c8)
volatile LONG g_geoHits[6] = {0, 0, 0, 0, 0, 0};   // 0 segment range, 1 TNode point, 2 bone point, 3 / 4 tru+0x309500 sites
LONG g_geoReported[6] = {0, 0, 0, 0, 0, 0};
const int kGeoCount = 6;
const char *const kGeoNames[6] = {
    "segment range (tru+0x2fe040 = TU 0x823fe9d0): type-22 box -> last segment index - 1, like flag 0x400000",
    "TNode attach point (tru+0x307c60 = TU 0x823fd890): type-22 box -> position + 47.4075 x facing, z - 474.075",
    "bone attach point (tru+0x311530 = TU 0x823fe130): type-22 box -> position + 47.4075 x facing",
    "segment corner 1 (tru+0x309500 site 0x7097cb = TU 0x82400dc0): type-22 box skips the angle, like flag 0x400000",
    "segment corner 2 (tru+0x309500 site 0x709894 = TU 0x82400ea0): type-22 box skips the angle, like flag 0x400000",
    "fifth geometry function (tru+0x34d390 site 0x74d4b8 = TU 0x8242a8c4): type-22 box takes the flag-0x400000 path"};

void ReportGeometryHits() {
    for (int i = 0; i < kGeoCount; ++i) {
        LONG n = g_geoHits[i], last = g_geoReported[i];
        if (n == last) continue;
        g_geoReported[i] = n;
        bool pow2 = false;                  // did the count cross a power of two since the last report?
        for (LONG p = 1; p > 0 && p <= n; p <<= 1)
            if (p > last) { pow2 = true; break; }
        if (last == 0 || (g_logLevel >= 2 && pow2)) Log(1, "%s (%ld hits)", kGeoNames[i], n);
    }
}

// chart log: record index of a chart record pointer in the machine's record array [[machine+4]+0xc]
int RecordIndex(const BYTE *machine, DWORD rec) {
    if (!rec) return -1;
    __try {
        const DWORD *arr = *reinterpret_cast<const DWORD *const *>(*reinterpret_cast<const BYTE *const *>(machine + 4) + 0xc);
        for (int i = 0; i < 4096; ++i)
            if (arr[i] == rec) return i;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return -1;
}

// 0.7: the player instance has more than one machine (48l: "record -1 -> 1492" every frame = two machines with the
// player at +8 alternating in one shared "last record"); now one entry per machine
struct ChartLast { const BYTE *machine; DWORD rec; };
ChartLast g_chartLasts[8];

void __stdcall ChartTick(const BYTE *machine) {
    if (!g_sapChecked) SapControl();        // 0.10: once, on the first update that sees the SAP core
    if (!g_chartLog) return;                // 0.10: the probe may run for the SweepAndPrune control alone
    ReportGeometryHits();                   // 0.8
    __try {
        const BYTE *inst = *reinterpret_cast<const BYTE *const *>(machine + 8);
        if (!inst || inst != *reinterpret_cast<const BYTE *const *>(kPlayerPtr)) return;
        DWORD cur = *reinterpret_cast<const DWORD *>(machine + 0x510);
        ChartLast *slot = nullptr;
        for (int i = 0; i < 8 && !slot; ++i)
            if (g_chartLasts[i].machine == machine) slot = &g_chartLasts[i];
        for (int i = 0; i < 8 && !slot; ++i)
            if (!g_chartLasts[i].machine) { slot = &g_chartLasts[i]; slot->machine = machine; slot->rec = 0; }
        if (!slot || cur == slot->rec) return;
        DWORD prev = slot->rec;
        slot->rec = cur;
        int ci = RecordIndex(machine, cur), pi = RecordIndex(machine, prev);
        if (!((ci >= g_chartFrom && ci <= g_chartTo) || (pi >= g_chartFrom && pi <= g_chartTo))) return;
        if (InterlockedIncrement(&g_chartLines) > 5000) return;
        char sids[96] = "";
        if (cur) {
            WORD count = *reinterpret_cast<const WORD *>(cur + 0xc);
            const WORD *list = *reinterpret_cast<const WORD *const *>(cur + 0x18);
            int len = 0;
            for (int i = 0; i < count && i < 8 && len < 80; ++i)
                len += _snprintf_s(sids + len, sizeof(sids) - len, _TRUNCATE, "%s%u", i ? " " : "", list[i]);
        }
        DWORD gt = 0, a64 = 0, c94 = 0;
        ReadAttachState(&gt, &a64, &c94);
        Log(1, "chart: player machine 0x%08lx record %d -> %d (Lara states [%s]; +0xa64 0x%08lx, attach box +0xc94 "
               "0x%08lx)", reinterpret_cast<DWORD>(machine), pi, ci, sids, a64, c94);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

// replaces `mov eax,[esi+510h]` (6 bytes) at tru+0x387ebf; esi = machine (= agent)
__declspec(naked) void ChartTickProbe() {
    __asm {
        pushad
        push esi
        call ChartTick
        popad
        mov eax, [esi + 0x510]
        jmp dword ptr [g_chartTickNext]
    }
}

void PatchAttachGeometry() {
    if (!HexBytesAt(kFacingSwitch, kFacingSwitchHex) || !HexBytesAt(kFacingDefault, kFacingDefaultHex) ||
        !HexBytesAt(kFacingEdge, kFacingEdgeHex)) {
        Log(0, "facing function at 0x%08lx does not match - type-22 facing not added", kFacingDefault);
    } else if (WriteJump(kFacingDefault, &FacingDefault, 5)) {
        Log(1, "attach facing: type 22 -> edge normal of segment 0 (title update 0x824006a8; default 0x%08lx -> case 0x%08lx)",
            kFacingDefault, kFacingEdge);
    } else {
        Log(0, "attach facing not written (VirtualProtect %lu)", GetLastError());
    }
    if (!HexBytesAt(kMoveFlag10, kMoveFlag10Hex) || !HexBytesAt(kMoveDefault, kMoveDefaultHex)) {
        Log(0, "attached movement at 0x%08lx does not match - type-22 wall handler not added", kMoveDefault);
    } else if (WriteJump(kMoveDefault, &MoveDefault, 5)) {
        Log(1, "attached movement: attach box type 22 -> wall handler (title update 0x8245d6c8; 0x%08lx -> 0x%08lx)",
            kMoveDefault, kMoveWall);
    } else {
        Log(0, "attached movement not written (VirtualProtect %lu)", GetLastError());
    }
}

void PatchState420() {
    if (*reinterpret_cast<const DWORD *>(kS420Slot1Entry) != kS420Slot1 || !HexBytesAt(kS420Slot1, kS420Slot1Hex) ||
        !HexBytesAt(kS420Body, kS420BodyHex) || !HexBytesAt(kTemplate, kTemplateHex) ||
        !HexBytesAt(kParamNode, kParamNodeHex) || !HexBytesAt(kParamBool, kParamBoolHex) ||
        !HexBytesAt(kPrepare, "55 8bec 83e4f0 a158dbfa00 83ec1c") || !HexBytesAt(kAttachedMove, "55 8bec 83e4f0 a158dbfa00") ||
        !HexBytesAt(kAttachedPos, "55 8bec 83e4f0 81ec94000000")) {
        Log(0, "state 420 slot 1 at 0x%08lx (or its building blocks) does not match - TU slot 1 not added", kS420Slot1);
        return;
    }
    if (WriteJump(kS420Slot1, &State420Slot1, 5))   // a jump keeps the slot's cdecl frame (return address, agent)
        Log(1, "state 420 slot 1: title-update body added (0x8245e450: doppelganger mode + parameter 0x19e -> attached "
               "movement; 0x%08lx)", kS420Slot1);
    else
        Log(0, "state 420 slot 1 not written (VirtualProtect %lu)", GetLastError());
}

void PatchChartLog() {
    if (!HexBytesAt(kChartTick, kChartTickHex)) {
        Log(0, "machine update at 0x%08lx does not match - chart log and SweepAndPrune control off", kChartTick);
        return;
    }
    if (!WriteJump(kChartTick, &ChartTickProbe, 6))
        Log(0, "chart log not written (VirtualProtect %lu)", GetLastError());
    else if (g_chartLog)
        Log(1, "chart log: player record changes with an index in %d..%d are logged (diagnostic; 0x%08lx)", g_chartFrom,
            g_chartTo, kChartTick);
    else   // 0.10: installed for the SweepAndPrune control alone
        Log(1, "machine-update probe for the SweepAndPrune control only (ChartLog=0; 0x%08lx)", kChartTick);
}

// 0.10: write code bytes (the caller checked the old bytes)
bool WriteCode(DWORD at, const BYTE *bytes, size_t length) {
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), bytes, length);
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

// 0.10: the TU's create(3000, 500) and field 500 in the owner constructor - in DllMain, before the game init runs
void PatchSweepAndPrune() {
    if (!HexBytesAt(kSapCtor, kSapCtorHex) || !HexBytesAt(kSapMid, kSapMidHex) || !HexBytesAt(kSapCall, kSapCallHex) ||
        !HexBytesAt(kSapGetter, kSapGetterHex) || !HexBytesAt(kSapOwnerStore, kSapOwnerStoreHex) ||
        !HexBytesAt(kSapCoreCaps, kSapCoreCapsHex) || !HexBytesAt(kSapCoreMem, kSapCoreMemHex)) {
        g_sapState = -1;
        Log(0, "SweepAndPrune: owner constructor 0x%08lx (or the SAP core it creates) does not match - limits not changed",
            kSapCtor);
        return;
    }
    const bool argsOld = BytesAt(kSapArgs, kSapArgsOld, sizeof(kSapArgsOld));
    const bool fieldOld = BytesAt(kSapField, kSapFieldOld, sizeof(kSapFieldOld));
    if (BytesAt(kSapArgs, kSapArgsNew, sizeof(kSapArgsNew)) && BytesAt(kSapField, kSapFieldNew, sizeof(kSapFieldNew))) {
        g_sapState = 2;
        Log(1, "SweepAndPrune: the exe already creates (3000, 500) with field 500 - nothing written");
        return;
    }
    if (!argsOld || !fieldOld) {
        g_sapState = -1;
        Log(0, "SweepAndPrune: create arguments 0x%08lx (%s) / field 0x%08lx (%s) do not match - limits not changed", kSapArgs,
            argsOld ? "ok" : "differs", kSapField, fieldOld ? "ok" : "differs");
        return;
    }
    DWORD owner = 0, owner2 = 0;
    __try {
        owner = *reinterpret_cast<const DWORD *>(kSapOwnerPtr);
        owner2 = *reinterpret_cast<const DWORD *>(kSapOwnerPtr2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        owner = owner2 = 0xffffffff;
    }
    if (owner || owner2) {
        g_sapState = -1;
        Log(0, "SweepAndPrune: MarkupManager already built (0x%08lx / 0x%08lx) - loaded after the game init, limits not "
               "changed", owner, owner2);
        return;
    }
    if (!g_sapTranslate) {
        Log(1, "SweepAndPrune: Translate=0 - PC limits kept (1000 boxes, 400 pair links)");
        return;
    }
    if (WriteCode(kSapArgs, kSapArgsNew, sizeof(kSapArgsNew)) && WriteCode(kSapField, kSapFieldNew, sizeof(kSapFieldNew))) {
        g_sapState = 1;
        Log(1, "SweepAndPrune: limits as the title update (TU 0x8227b9f0: create(3000, 500) = 3000 boxes, 1000 pair links, "
               "+412800 bytes; arguments 0x%08lx, field +0x20 = 500 at 0x%08lx)", kSapArgs, kSapField);
    } else {
        g_sapState = -1;
        Log(0, "SweepAndPrune: limits not written (VirtualProtect %lu)", GetLastError());
    }
}

// ---- 0.8 stubs. The type test is the TU's inline one (0x823feab4..0x823feadc and the same block in the other
// functions): box +0x24 (second markup) ? its byte +0x4d : (box +0x20 (file record) ? its byte +0x33 : no type),
// sign-extended, == 22. ebx / esi / edi as at the patched instruction of each PC function.
const DWORD kSegRangeAt = 0x006fe0e5;     // test dword [esi+28h],400000h; je 0x6fe0f1; sub eax,1 (esi = box, eax = last)
const DWORD kSegRangeCheck = 0x006fe0d5;
const char *const kSegRangeHex = "8b4e20 33c0 394158 7406 8b4634 83e801 f7462800004000 7403 83e801 8b4d0c";
const DWORD kSegRangeNext = 0x006fe0f1;
const DWORD kTNodeAt = 0x00707fc8;        // retail default: out(esi) = position(edi), print, return (ebx = box)
const DWORD kTNodeCheck = 0x00707fb6;
const char *const kTNodeHex = "3d00000020 0f841f020000 3d00000040 7424 8b07 8906 8b4f04 894e04 8b5708 895608 8b470c "
                              "89460c e8bdd7f3ff 8bc6 5f 5e 5b 8be5 5d c3";
const DWORD kTNodeFacingCall = 0x00707cc6;   // push ebx; push ecx; movaps [esp+30h]; mov [esp+4Ch],edx; call facing; add esp,10h
const char *const kTNodeFacingHex = "53 51 0f29442430 8954244c e80a6bffff 83c410";   // -> the facing at [esp+40h]
const DWORD kTNodeEntry = 0x00707c60;
const char *const kTNodeEntryHex = "55 8bec 83e4f0 81ec14010000 8b4518 d9ee 8b08 8b5004 f30f10051c118400 53 8b5d14 56 8b7508 "
                                   "57 8b7d10";
const DWORD kTNodeNext = 0x00707fcf, kTNodeEnd = 0x00707fe3;
const DWORD kBoneAt = 0x007117e3;         // retail default, same shape (ebx = box, esi = out, edi = position)
const DWORD kBoneCheck = 0x007117d5;
const char *const kBoneHex = "3d00000020 742b 3d00000040 7424 8b07 8906 8b4f04 894e04 8b5708 895608 8b470c 89460c "
                             "e8a23ff3ff 8bc6 5f 5e 5b 8be5 5d c3";
const DWORD kBoneEntry = 0x00711530;
const char *const kBoneEntryHex = "55 8bec 83e4f0 81ecb4000000 f30f10051c118400 8b4d18 53 8b5d14 8b5328 8bc2 56 8b7508";
const DWORD kBoneNext = 0x007117ea, kBoneEnd = 0x007117fe;
const DWORD kCorner1At = 0x007097cb, kCorner1Next = 0x007097d6, kCorner1Skip = 0x00709883;
const char *const kCorner1Hex = "8b4728 a900004000 0f85ad000000 8d5a01 3b5f34";        // at 0x7097c8 (edi = box)
const DWORD kCorner2At = 0x00709894, kCorner2Next = 0x0070989f, kCorner2Skip = 0x00709953;
const char *const kCorner2Hex = "8b4728 a900004000 0f85b4000000 8b4c2430";              // at 0x709891
const DWORD kFacingFn = 0x006fe7e0;       // cdecl(out, box, segment, position) = TU 0x824006a8 (0.6 adds its type-22 case)
const char *const kFacingFnHex = "55 8bec 83e4f0 81ec24010000";
// TU constants (read from the TU image; the PC exe has neither value): 0x82051bc0 = 47.4075 (lfs -0xa38(r7) /
// 0x1bc0(0x82050000)), 0x8207e5ac = 474.075 (lfs -0x1a54(0x82080000))
const DWORD kTuOffsetBits = 0x423da148, kTuDropBits = 0x43ed099a;
DWORD g_segNext = kSegRangeNext, g_tnodeNext = kTNodeNext, g_tnodeEnd = kTNodeEnd, g_boneNext = kBoneNext,
      g_boneEnd = kBoneEnd, g_c1Next = kCorner1Next, g_c1Skip = kCorner1Skip, g_c2Next = kCorner2Next,
      g_c2Skip = kCorner2Skip;
typedef float *(__cdecl *FacingFn)(float *out, void *box, int segment, const float *position);

float TuFloat(DWORD bits) { float f; memcpy(&f, &bits, 4); return f; }

// TU vector normalise as in these blocks: vdot3 (x, y, z), reciprocal square root (the TU: vrsqrtefp + one Newton step;
// here 1 / sqrtf - differs only in the last bits), all four lanes scaled; length 0 -> 0 vector (vcmpeqfp / vsel)
void TuNormalize(const float *v, float *n) {
    float d = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    if (d == 0.0f) { n[0] = n[1] = n[2] = n[3] = 0.0f; return; }
    float inv = 1.0f / sqrtf(d);
    for (int i = 0; i < 4; ++i) n[i] = v[i] * inv;
}

// TU 0x823fdd9c..0x823fde10: v2 = position + normalize(facing v126) x [0x82051bc0]; z -= [0x8207e5ac]; return v2
int __stdcall TNodeType22(void *box, float *out, const float *position, const float *facing) {
    if (!IsType22(box)) return 0;
    __try {
        float n[4];
        TuNormalize(facing, n);
        float k = TuFloat(kTuOffsetBits);
        for (int i = 0; i < 4; ++i) out[i] = position[i] + n[i] * k;
        out[2] -= TuFloat(kTuDropBits);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    InterlockedIncrement(&g_geoHits[1]);
    return 1;
}

// TU 0x823fe4f8..0x823fe558: v1 = 0x824006a8(box, segment, position) (facing); return position + normalize(v1) x
// [0x82051bc0]
int __stdcall BoneType22(void *box, float *out, int segment, const float *position) {
    if (!IsType22(box)) return 0;
    __try {
        __declspec(align(16)) float face[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        reinterpret_cast<FacingFn>(kFacingFn)(face, box, segment, position);
        float n[4];
        TuNormalize(face, n);
        float k = TuFloat(kTuOffsetBits);
        for (int i = 0; i < 4; ++i) out[i] = position[i] + n[i] * k;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    InterlockedIncrement(&g_geoHits[2]);
    return 1;
}

// tru+0x2fe0e5: flag 0x400000 or type 22 -> eax (last segment index) - 1 (TU 0x823feaa4..0x823feae0)
__declspec(naked) void SegRangeStub() {
    __asm {
        test dword ptr [esi + 28h], 400000h
        jnz dec1
        push ecx
        push eax
        mov ecx, [esi + 24h]
        test ecx, ecx
        jz rec
        movsx eax, byte ptr [ecx + 4dh]
        jmp cmp22
    rec:
        mov ecx, [esi + 20h]
        test ecx, ecx
        jz no
        movsx eax, byte ptr [ecx + 33h]
    cmp22:
        cmp eax, 16h
        jne no
        lock inc dword ptr [g_geoHits]
        pop eax
        pop ecx
    dec1:
        sub eax, 1
        jmp dword ptr [g_segNext]
    no:
        pop eax
        pop ecx
        jmp dword ptr [g_segNext]
    }
}

// tru+0x307fc8 (default of the TNode attach point; esp = the frame of the function body, facing at [esp+40h])
__declspec(naked) void TNodeDefault() {
    __asm {
        pushad
        lea eax, [esp + 60h]
        push eax
        push edi
        push esi
        push ebx
        call TNodeType22
        test eax, eax
        popad
        jnz handled
        mov eax, [edi]
        mov [esi], eax
        mov ecx, [edi + 4]
        jmp dword ptr [g_tnodeNext]
    handled:
        jmp dword ptr [g_tnodeEnd]
    }
}

// tru+0x3117e3 (default of the bone attach point; segment = [ebp+0Ch])
__declspec(naked) void BoneDefault() {
    __asm {
        pushad
        push edi
        push dword ptr [ebp + 0Ch]
        push esi
        push ebx
        call BoneType22
        test eax, eax
        popad
        jnz handled
        mov eax, [edi]
        mov [esi], eax
        mov ecx, [edi + 4]
        jmp dword ptr [g_boneNext]
    handled:
        jmp dword ptr [g_boneEnd]
    }
}

// tru+0x3097cb / +0x309894: `test eax,400000h; jne skip` (eax = [edi+28h], edi = box) + the TU's type-22 test
__declspec(naked) void Corner1Stub() {
    __asm {
        test eax, 400000h
        jnz skip
        push ecx
        push eax
        mov ecx, [edi + 24h]
        test ecx, ecx
        jz rec
        movsx eax, byte ptr [ecx + 4dh]
        jmp cmp22
    rec:
        mov ecx, [edi + 20h]
        test ecx, ecx
        jz no
        movsx eax, byte ptr [ecx + 33h]
    cmp22:
        cmp eax, 16h
        jne no
        lock inc dword ptr [g_geoHits + 12]
        pop eax
        pop ecx
    skip:
        jmp dword ptr [g_c1Skip]
    no:
        pop eax
        pop ecx
        jmp dword ptr [g_c1Next]
    }
}

__declspec(naked) void Corner2Stub() {
    __asm {
        test eax, 400000h
        jnz skip
        push ecx
        push eax
        mov ecx, [edi + 24h]
        test ecx, ecx
        jz rec
        movsx eax, byte ptr [ecx + 4dh]
        jmp cmp22
    rec:
        mov ecx, [edi + 20h]
        test ecx, ecx
        jz no
        movsx eax, byte ptr [ecx + 33h]
    cmp22:
        cmp eax, 16h
        jne no
        lock inc dword ptr [g_geoHits + 16]
        pop eax
        pop ecx
    skip:
        jmp dword ptr [g_c2Skip]
    no:
        pop eax
        pop ecx
        jmp dword ptr [g_c2Next]
    }
}

void PatchJumpGeometry() {
    struct Piece { const char *name; DWORD check; const char *hex; DWORD at; const void *stub; int len; };
    const Piece pieces[5] = {
        {"segment range", kSegRangeCheck, kSegRangeHex, kSegRangeAt, &SegRangeStub, 5},
        {"TNode attach point", kTNodeCheck, kTNodeHex, kTNodeAt, &TNodeDefault, 7},
        {"bone attach point", kBoneCheck, kBoneHex, kBoneAt, &BoneDefault, 7},
        {"segment corner 1", kCorner1At - 3, kCorner1Hex, kCorner1At, &Corner1Stub, 5},
        {"segment corner 2", kCorner2At - 3, kCorner2Hex, kCorner2At, &Corner2Stub, 5}};
    // pins of the registers / frame the stubs rely on
    const bool tnodeFrame = HexBytesAt(kTNodeEntry, kTNodeEntryHex) && HexBytesAt(kTNodeFacingCall, kTNodeFacingHex);
    const bool boneFrame = HexBytesAt(kBoneEntry, kBoneEntryHex) && HexBytesAt(0x007115ea, "8b450c") &&
                           HexBytesAt(0x0071157c, "8b7d10") && HexBytesAt(kFacingFn, kFacingFnHex);
    int written = 0;
    for (int i = 0; i < 5; ++i) {
        const Piece &p = pieces[i];
        if ((i == 1 && !tnodeFrame) || (i == 2 && !boneFrame) || !HexBytesAt(p.check, p.hex)) {
            Log(0, "%s at 0x%08lx does not match - its type-22 branch not added", p.name, p.at);
            continue;
        }
        if (WriteJump(p.at, p.stub, p.len)) {
            ++written;
            Log(1, "%s: title-update type-22 branch added (0x%08lx)", p.name, p.at);
        } else {
            Log(0, "%s not written (VirtualProtect %lu)", p.name, GetLastError());
        }
    }
    Log(1, "jump geometry: %d of 5 type-22 branches added (hits are reported by the chart probe%s)", written,
        g_chartLog ? "" : " - ChartLog=0, so no hit lines");
}

// ---- 0.9: fifth geometry function tru+0x34d390 (TU 0x8242a7c8, inserted block 0x8242a898..0x8242a8c4) ----
const DWORD kGeo5Entry = 0x0074d390;      // push ebp; mov ebp,esp; and esp,-16; sub esp,0C8h; fldz; mov eax,[ebp+10h]
const char *const kGeo5EntryHex = "55 8bec 83e4f0 81ecc8000000 d9ee 8b4510 53 d95c2408 56 8b750c";   // esi = box
const DWORD kGeo5At = 0x0074d4b8;         // test eax,400000h; je 0x74d4d5 (7 bytes), after mov eax,[esi+28h]
const DWORD kGeo5Check = 0x0074d4b5;
const char *const kGeo5Hex = "8b4628 a900004000 7416 6a00 8d8424c4000000 50 8bce e8f067e7ff e93b020000 a900800000";
const DWORD kGeo5Next = 0x0074d4d5, kGeo5Flag = 0x0074d4bf;
DWORD g_g5Next = kGeo5Next, g_g5Flag = kGeo5Flag;

// tru+0x34d4b8: flag 0x400000 or type(esi) == 22 -> the flag path (TU 0x8242abac), else the 0x8000 test (eax kept)
__declspec(naked) void SkipGeometryStub() {
    __asm {
        test eax, 400000h
        jnz flag
        push ecx
        push eax
        mov ecx, [esi + 24h]
        test ecx, ecx
        jz rec
        movsx eax, byte ptr [ecx + 4dh]
        jmp cmp22
    rec:
        mov ecx, [esi + 20h]
        test ecx, ecx
        jz no
        movsx eax, byte ptr [ecx + 33h]
    cmp22:
        cmp eax, 16h
        jne no
        lock inc dword ptr [g_geoHits + 20]
        pop eax
        pop ecx
    flag:
        jmp dword ptr [g_g5Flag]
    no:
        pop eax
        pop ecx
        jmp dword ptr [g_g5Next]
    }
}

void PatchSkipGeometry() {
    if (!HexBytesAt(kGeo5Entry, kGeo5EntryHex) || !HexBytesAt(kGeo5Check, kGeo5Hex)) {
        Log(0, "fifth geometry function at 0x%08lx / 0x%08lx does not match - its type-22 branch not added", kGeo5Entry,
            kGeo5At);
        return;
    }
    if (WriteJump(kGeo5At, &SkipGeometryStub, 7))
        Log(1, "fifth geometry function: title-update type-22 branch added (tru+0x34d390 = TU 0x8242a7c8, site 0x%08lx: "
               "flag 0x400000 or type 22 -> 0x%08lx)", kGeo5At, kGeo5Flag);
    else
        Log(0, "fifth geometry function not written (VirtualProtect %lu)", GetLastError());
}

// ---- 0.11: title-update ledge-corner nudge (TU 0x8242ecd8, inserted block 0x8242eeac..0x8242ef40) ----
const DWORD kLedgeEntry = 0x0074e5a0;     // push ebp; mov ebp,esp; and esp,-16; mov eax,[0xfadb58]; fldz; mov ecx,[eax+0C94h]
const char *const kLedgeEntryHex = "55 8bec 83e4f0 a158dbfa00 d9ee 8b88940c0000";
const DWORD kLedgeArg = 0x0074e5c4;       // mov ebx,[ebp+8] - the argument (TU r27), not written again up to 0x74ea58
const char *const kLedgeArgHex = "8b5d08";
// 0x74e7c6..0x74e822: box / partner set, flag 0x40000000 on both (TU ..0x8242eea8), then the hooked movss and the
// tracker load of the segment fetch
const DWORD kLedgeCheck = 0x0074e7c6;
const char *const kLedgeCheckHex = "83b8940c000000 0f8452050000 83b8ac0e000000 0f8445050000 8b88940c0000 8b4928 "
                                   "f7c100000040 8b90ac0e0000 8b5228 c780d00e000000000000 0f841d050000 f7c200000040 "
                                   "0f8411050000 f30f100d34118400 8b3558dbfa00";
const DWORD kLedgeAt = 0x0074e814;        // movss xmm1,[0x841134] (8 bytes), executed in the stub
const DWORD kLedgeNext = 0x0074e81c;
// 0x74eace..0x74eb06: push ebx (0x74ea58) ... call 0x787ef0; ...; add esp,4; cmp eax,4 (TU 0x8242f094 reuses r30)
const DWORD kLookSiteCheck = 0x0074eace;
const char *const kLookSiteCheckHex = "a158dbfa00 d980980c0000 8b80940c0000 8b4834 d95c242c 83c101 894c2414 e8fe930300 "
                                      "d944242c 0f28442464 83c404 83f804";
const DWORD kLookPush = 0x0074ea58;       // push ebx = the argument of the look-ahead call
const DWORD kLookSite = 0x0074eaed;       // call 0x787ef0 (5 bytes)
const DWORD kLookAhead = 0x00787ef0;      // LookAheadDirection (cdecl, 1 argument): parameter 0x1f3 -> 1..6
const char *const kLookAheadHex = "51 8b4c2408 56 8d442404 50 68f3010000 33f6 68f3010000";
const DWORD kTracker = 0x00fadb58;        // player tracker pointer (TU 0x829892b0)
const DWORD kFloor = 0x00813510;          // CRT floor (double) - TU floor 0x8268b7a0
const char *const kFloorHex = "833d403e0d0100 0f844f950000 83ec08";
const DWORD kTuMinus = 0x3a83126f;        // TU f30 = [0x82053608] = 0.001f (also PC [0x841634], the t = 0 case)
const DWORD kTuPlus = 0x3f8147ae;         // TU [0x8207ddf8] = 1.01f
typedef int(__cdecl *LookAheadFn)(void *agent);
typedef double(__cdecl *FloorFn)(double);
DWORD g_ledgeNext = kLedgeNext, g_lookAhead = kLookAhead;
int g_lookHave = 0, g_lookDir = 0;       // the TU's r30: the one look-ahead result of this pass (game thread only)
volatile LONG g_ledgeNudges = 0;

void __cdecl LedgeCorner(void *agent) {
    int dir = reinterpret_cast<LookAheadFn>(kLookAhead)(agent);   // TU 0x8242eebc, before the test
    g_lookDir = dir;
    g_lookHave = 1;
    BYTE *p = *reinterpret_cast<BYTE **>(kTracker);
    if (*reinterpret_cast<DWORD *>(p + 0xc94) != *reinterpret_cast<DWORD *>(p + 0xeac)) return;   // TU 0x8242eed0
    FloorFn fl = reinterpret_cast<FloorFn>(kFloor);
    float partner = static_cast<float>(fl(*reinterpret_cast<float *>(p + 0xeb0)));
    float own = static_cast<float>(fl(*reinterpret_cast<float *>(p + 0xc98)));
    if (!(partner == own)) return;          // TU 0x8242eef8 fcmpu / bne (unordered = not equal)
    float before = *reinterpret_cast<float *>(p + 0xc98);
    float base = static_cast<float>(fl(before));
    float t = dir == 4 ? base - TuFloat(kTuMinus) : base + TuFloat(kTuPlus);   // TU 0x8242ef18 / 0x8242ef38
    *reinterpret_cast<float *>(p + 0xc98) = t;
    LONG n = InterlockedIncrement(&g_ledgeNudges);
    if (LogNow(n))
        Log(1, "ledge corner: title-update nudge (TU 0x8242eeac): box 0x%08lx, partner t %.4f, t %.4f -> %.4f "
               "(look-ahead %d) (%ld nudges)", *reinterpret_cast<DWORD *>(p + 0xc94),
            static_cast<double>(*reinterpret_cast<float *>(p + 0xeb0)), static_cast<double>(before),
            static_cast<double>(t), dir, n);
}

// tru+0x34e814: x87 stack empty, eax = tracker, ebx = argument, xmm0 = 0 (live); all registers and flags kept
__declspec(naked) void LedgeCornerStub() {
    __asm {
        pushfd
        pushad
        sub esp, 128
        movdqu [esp], xmm0
        movdqu [esp + 16], xmm1
        movdqu [esp + 32], xmm2
        movdqu [esp + 48], xmm3
        movdqu [esp + 64], xmm4
        movdqu [esp + 80], xmm5
        movdqu [esp + 96], xmm6
        movdqu [esp + 112], xmm7
        push ebx
        call LedgeCorner
        add esp, 4
        movdqu xmm0, [esp]
        movdqu xmm1, [esp + 16]
        movdqu xmm2, [esp + 32]
        movdqu xmm3, [esp + 48]
        movdqu xmm4, [esp + 64]
        movdqu xmm5, [esp + 80]
        movdqu xmm6, [esp + 96]
        movdqu xmm7, [esp + 112]
        add esp, 128
        popad
        popfd
        movss xmm1, dword ptr ds:[841134h]  // the replaced instruction
        jmp dword ptr [g_ledgeNext]
    }
}

// tru+0x34eaed: call target instead of 0x787ef0 - the TU's single result (r30), else the original lookup
__declspec(naked) void LookAheadReuse() {
    __asm {
        cmp dword ptr [g_lookHave], 0
        je orig
        mov dword ptr [g_lookHave], 0
        mov eax, dword ptr [g_lookDir]
        ret
    orig:
        jmp dword ptr [g_lookAhead]
    }
}

void PatchLedgeCorner() {
    if (!g_ledgeCorner) {
        Log(1, "ledge corner: Translate=0 - PC ledge code kept (no title-update nudge)");
        return;
    }
    if (!HexBytesAt(kLedgeEntry, kLedgeEntryHex) || !HexBytesAt(kLedgeArg, kLedgeArgHex) ||
        !HexBytesAt(kLedgeCheck, kLedgeCheckHex) || !HexBytesAt(kLookSiteCheck, kLookSiteCheckHex) ||
        !HexBytesAt(kLookPush, "53") || !HexBytesAt(kLookAhead, kLookAheadHex) || !HexBytesAt(kFloor, kFloorHex)) {
        Log(0, "ledge function at 0x%08lx (sites 0x%08lx / 0x%08lx) does not match - ledge-corner nudge not added",
            kLedgeEntry, kLedgeAt, kLookSite);
        return;
    }
    BYTE call[5] = {0xe8, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(&LookAheadReuse) - (kLookSite + 5);
    memcpy(call + 1, &rel, 4);
    // the call site first: until the stub is in, LookAheadReuse finds no stored result and runs the original
    if (WriteCode(kLookSite, call, sizeof(call)) && WriteJump(kLedgeAt, &LedgeCornerStub, 8))
        Log(1, "ledge corner: title-update nudge added (tru+0x34e5a0 = TU 0x8242ecd8, block 0x8242eeac; hook 0x%08lx, "
               "look-ahead result reused at 0x%08lx; t = floor - 0.001 (direction 4) / floor + 1.01)", kLedgeAt, kLookSite);
    else
        Log(0, "ledge corner not (fully) written (VirtualProtect %lu)", GetLastError());
}

bool WriteDword(DWORD at, DWORD value) {
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 4, PAGE_READWRITE, &old)) return false;
    *reinterpret_cast<DWORD *>(at) = value;
    VirtualProtect(reinterpret_cast<void *>(at), 4, old, &dummy);
    return true;
}

void PatchSlots() {
    const DWORD *vt = reinterpret_cast<const DWORD *>(kSlot0At);
    if (vt[0] != kSlot0 || vt[1] != kSlot1 || vt[2] != kSlot8 || !BytesAt(kSlot0, kSlot0Bytes, sizeof(kSlot0Bytes)) ||
        !BytesAt(kSlot1, kSlot1Bytes, sizeof(kSlot1Bytes)) || !BytesAt(kSlot8, kSlot8Bytes, sizeof(kSlot8Bytes))) {
        Log(0, "TRMarkupManager slots 0 / 1 / +0x08 at 0x%08lx do not match - title-update type checks not added", kSlot0At);
        return;
    }
    if (g_markupSlots) {
        bool ok = WriteDword(kSlot0At, reinterpret_cast<DWORD>(&Slot0)) && WriteDword(kSlot1At, reinterpret_cast<DWORD>(&Slot1)) &&
                  WriteJump(kSlot8Branch, &Slot8Branch, 6);
        if (ok)
            Log(1, "markup slots: 0 also true for type 22, 1 for type 23, +0x08 edge normal for type 22 (as the title "
                   "update; vtable 0x%08lx, branch 0x%08lx)", kSlot0At, kSlot8Branch);
        else
            Log(0, "markup slots not (fully) written (VirtualProtect %lu)", GetLastError());
    }
    if (g_nullBoxGuard) {
        if (WriteDword(kSlot8At, reinterpret_cast<DWORD>(&Slot8Guard)))
            Log(1, "null-box guard on markup slot +0x08 (diagnostic; vtable entry 0x%08lx)", kSlot8At);
        else
            Log(0, "null-box guard not written (VirtualProtect %lu)", GetLastError());
    }
}

bool PatchTable() {
    DWORD *table = reinterpret_cast<DWORD *>(kTable);
    DWORD old = 0;
    if (!VirtualProtect(table, kTableCount * sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) - not patched", GetLastError());
        return false;
    }
    table[607 - 601] = reinterpret_cast<DWORD>(&Cond607);
    table[608 - 601] = reinterpret_cast<DWORD>(&Cond608);
    int logged = 0;
    if (g_logUnhandled) {
        for (int i = 0; i < kTableCount; ++i) {
            if (i == 607 - 601 || i == 608 - 601 || kTableOriginal[i] != kDefault) continue;
            table[i] = reinterpret_cast<DWORD>(&CondUnhandled);
            ++logged;
        }
    }
    DWORD dummy = 0;
    VirtualProtect(table, kTableCount * sizeof(DWORD), old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), table, kTableCount * sizeof(DWORD));
    Log(1, "jump table patched: 607 -> 0x%08lx (type %d), 608 -> 0x%08lx (type %d), %d unhandled ids logged",
        reinterpret_cast<DWORD>(&Cond607), g_type607, reinterpret_cast<DWORD>(&Cond608), g_type608, logged);
    return true;
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruRockVein.log", dir);
    strncpy_s(g_dir, sizeof(g_dir), dir, _TRUNCATE);
    ReadOptions(dir);
    Log(1, "TruRockVein 0.11 loaded (enabled %d, log level %d, log unhandled %d, bad values %d, default conditions %d, "
        "markup types %d, markup slots %d, null-box guard %d, markup action 608 %d, attach geometry %d, state 420 slot 1 %d, "
        "chart log %d, jump geometry %d, skip geometry %d, SweepAndPrune translate %d, ledge corner translate %d)",
        g_enabled, g_logLevel, g_logUnhandled, g_logBadValues, g_logDefaultConditions, g_markupTypes, g_markupSlots,
        g_nullBoxGuard, g_markupAction608, g_attachGeometry, g_state420Slot1, g_chartLog, g_jumpGeometry, g_skipGeometry,
        g_sapTranslate, g_ledgeCorner);
    if (!g_enabled) { Log(1, "disabled by TruRockVein.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    PatchSweepAndPrune();                   // 0.10: first - it must run before the game init (checks itself)
    if (g_markupTypes) PatchMarkupTypes();
    if (g_markupSlots || g_nullBoxGuard) PatchSlots();
    if (g_markupAction608) PatchSelector();
    if (g_nullBoxGuard) PatchPointOnBox();
    if (g_attachGeometry) PatchAttachGeometry();
    if (g_state420Slot1) PatchState420();
    if (g_chartLog || g_sapTranslate) PatchChartLog();   // 0.10: also the SweepAndPrune control's first-frame probe
    if (g_jumpGeometry) PatchJumpGeometry();
    if (g_skipGeometry) PatchSkipGeometry();
    PatchLedgeCorner();                     // 0.11 (logs Translate=0 itself)
    if (!BytesAt(kDispatch, kDispatchBytes, sizeof(kDispatchBytes)) || !BytesAt(kDefault, kDefaultBytes, sizeof(kDefaultBytes)) ||
        !BytesAt(kExit, kExitBytes, sizeof(kExitBytes)) || !BytesAt(kCtxUse, kCtxUseBytes, sizeof(kCtxUseBytes))) {
        Log(0, "SCCondTest_MarkupType at 0x%08lx does not match (other tru.exe build?) - not patched", kDispatch);
        return;
    }
    if (!BytesAt(kGetType, kGetTypeBytes, sizeof(kGetTypeBytes))) {
        Log(0, "markup type getter at 0x%08lx does not match - not patched", kGetType);
        return;
    }
    if (!BytesAt(kTable, reinterpret_cast<const BYTE *>(kTableOriginal), sizeof(kTableOriginal))) {
        Log(0, "condition jump table at 0x%08lx is not the original (patched by something else?) - not patched", kTable);
        return;
    }
    Log(3, "code checks passed (dispatch, default case, exit, context use, type getter, table)");
    if (PatchTable()) InstallProbes();
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

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruRockVeinVersion() { return "TruRockVein 0.11 (markup conditions 607 / 608, chart probes, markup types 22 / 23, TU slot type checks, markup action 608, type-22 facing / wall movement, state 420 slot 1, chart log, type-22 jump geometry, type-22 fifth geometry function, SweepAndPrune limits as the title update, ledge-corner nudge as the title update)"; }
