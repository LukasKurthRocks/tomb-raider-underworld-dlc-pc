# TruRockVein.asi

DLC 2 *Lara's Shadow*: the rock veins ("Felsrinnen") for the PC `tru.exe` - step 3.4a of bringing the Xbox title
update to PC (see docs/PLUGINS.md, "How the Xbox title update is brought to PC", and docs/WINDOWS_REBUILD.md
finding 43). 0.1 played 2026-10-30 (patched, never asked - see 0.2); 0.2 built 2026-10-31, not yet played. Since 0.10
also the title update's SweepAndPrune limits of the markup manager (section 0.10), since 0.11 its ledge-corner nudge,
since 0.12 its jump targets on vertical segments (pillar jumps) - base-game fixes the PC never got.

## What it does

Lara's moves run through a data-driven state machine whose transitions test numbered conditions. The Xbox title
update added two markup conditions to `SCCondTest_MarkupType`: **607** ("the player's markup has type 23") and
**608** ("... type 22") - most likely the rock vein and its jump target. The PC exe has no case for them (its jump
table sends ids 604-609 to the "unhandled condition" default), so LB/RB + A at a rock vein can never start the attach
move. The plugin points the two jump-table entries at small stubs with exactly the title update's logic:

| | Xbox title update | PC |
|---|---|---|
| condition test | `SCCondTest_MarkupType` 0x82486dd8 | tru+0x382810, jump table tru+0x382a54 (ids 601-628) |
| context | argument r7 | argument at `[esp+1Ch]` inside the function |
| markup type | `[ctx+0x24]` -> byte +0x4d, else `[ctx+0x20]` -> byte +0x33 | the same getter exists: tru+0x1be340 (thiscall) |
| 607 / 608 | type == 23 / 22 | stubs call the getter, set `bl`, jump to the common exit tru+0x382a3f |

The other ids that end in the default case (604-606, 609, 619, 621, 622, 627) are logged once each (option
`LogUnhandled`) and then run the original default - if the rock vein needs more title-update conditions, they show up
in `TruRockVein.log`.

Before anything is written the plugin checks the image base, the dispatch code, the default case, the common exit, the
use of the context argument, the type getter and all 28 original table entries; on any mismatch it patches nothing and
logs why. Not covered: the climbing itself if it needs more title-update code (actions, animations), the shadow meter
coupling (TruShadowPower.asi), the shadow jump.

## 0.2: why 0.1 never fired, and two read-only probes

607 / 608 are not condition ids but the **value** (+4) of a state-chart condition record `{u16 key, u16 id, u16 value,
u8 flags, u8}`; the record id (610-613) selects the handler from Lara's link array, which passes the record to the
markup test. In the converted DLC 2 player data (`doppelganger_casual.drm`, DTP 20212) these values were stored in
Xbox byte order (608 -> 24578), so the test went straight to its default and the 607 / 608 stubs never ran. The data
is re-converted by `tools/statechart_fix_all.py` (layouts proven on the base game's `lara.drm`). 0.2 keeps the stubs
and adds two probes that change no result:

| option | where | logs |
|---|---|---|
| `LogBadValues` (default 1) | 5-byte detour on `sub eax,259h` at tru+0x38288d | every markup value > 628 except 1000, once each ("state chart data in the wrong byte order?"); with `LogLevel=2` also the first call of each value 601-628 |
| `LogDefaultConditions` (default 1) | detour on the entry of the condition default handler tru+0x382140 (Xbox `SCCondFunction_Default`) | each condition id answered by the default handler (always true), once, with record key / value and the agent's state name - ids missing in the agent's link array |

Both sites are byte-checked first (the default handler with its first 31 bytes and the format-string push at
tru+0x382182); a mismatch switches only that probe off.

## 0.3: markup types 22 / 23 (source only, not built yet)

The first live run with the fixed chart (2026-11-01 15:47) evaluated 607 / 608 at the rock channel, but with context
0 (no markup next to Lara). Cause in code, not data: when a markup record is added, its type char is mapped to a flag
class by TRMarkupManager vtable +0x20 (tru+0x5d70a0). The PC function is the Xbox retail one (types 1-21; anything
else returns 0x80000000 = "Bad Markup Type, disabling markup", print compiled out on PC), and a box with a negative flag
word is skipped by the markup queries. The title update's version (0x822a12e8) accepts 1-23 and returns 1 for 22 / 23.
Every type-22 markup found in the converted DLC 2 files sits on objects (pistons a / c / square, machine column, goo
converter; `tools/markup_level.py --objects`), and the PC disables all of it. `PatchMarkupTypes` (option `MarkupTypes`, default 1, not in the sample ini so the 0.2 ini stays "ours") checks the
vtable slot 0x855234, the 29 code bytes, the 21 table entries at 0x5d70d0 and the 8 padding bytes behind them, then
writes two entries (types 22 / 23 -> `mov eax,1; ret 4` at 0x5d70b5) into the padding and the bound 0x14 -> 0x16
(tru+0x5d70ab). Log line: "markup types 22 / 23 accepted". Live 2026-11-01 (test 48i): accepted, 608 true at the wall.

## 0.4: title-update type checks in the markup manager (2026-11-01)

With 0.3 the game crashed 237 ms after 608 became true, in TRMarkupManager slot +0x08 (tru+0x1dba20, wall normal of
a box) with box 0. The title update added the new types to three slots of the manager's vtable (TU 0x8206827c, PC
0x855214); the PC has the retail bodies: slot 0 (TU 0x822a0bc8: flag bits 0x04480010 or predicate **or type 22**),
slot 1 (TU 0x822a0c68: bits 0x61870000 or predicate **or type 23**), slot +0x08 (TU 0x822a0d08: edge normal when bits
0x20408000 **or type 22**). Without them the attach dispatcher tru+0x307b90 never sets the attach box
gameTracker+0xc94 for a type-22 box and the state code reads it as 0. `PatchSlots` (option `MarkupSlots`, default 1)
checks the three vtable entries and 34 code bytes of each body, then points slots 0 / 1 at plugin functions (original
first, then the TU type test) and replaces the `je` at tru+0x1dba3c by a jump to a stub with the TU branch.
`NullBoxGuard` (default 1, diagnostic, not a translation) points slot +0x08 at a check that logs the caller of a call
with box 0 and returns a zero vector. Neither option is in the sample ini (it stays the 0.2 / 0.3 one). Log lines:
"markup slots: 0 also true for type 22 ...", "markup slot 0 (wall, type 22) true by the title-update type check ...",
"markup slot +0x08 called with box 0 from 0x........". Built 2026-11-01 into `work\asi_rv04`; live test 48j: the
guard fired (from tru+0x32ba5b, +0xc94 = 0) and the game crashed in the next box function - the slots are needed but
not enough.

## 0.5: markup action 608 (2026-11-01)

The attach box is set by PLAYER_AttachToJumpTarget (PC tru+0x307b90 = TU 0x823fd178, the same on both). The title
update calls it from a new case of the markup-action selector (PC tru+0x372ca0 = TU 0x82463538, second switch on the
state parameter 0x19a, values 601..629): **case 608** (TU 0x82463a28) = if gameTracker+0xa64 != 0:
`PLAYER_AttachToJumpTarget(zero vector, 0.0f)`, then gameTracker+0xca0 = gameTracker+0xd90. All other cases have the
same target pattern on PC and TU; the PC sends 608 to its default. `PatchSelector` (option `MarkupAction608`, default
1) checks the 29 switch bytes, the byte-table entry of 608 (0x10 = default), the default entry, the exit bytes and the
first 20 bytes of tru+0x307b90, then replaces `lea eax,[ebx-259h]` at tru+0x372f8a by a jump to a stub that runs the
TU case for 608 and jumps to the selector's exit tru+0x3730af. `NullBoxGuard` also guards tru+0x32ba40 (attach point on
a box, the caller of the second crash site tru+0x1c39e2). Log lines: "markup action 608 added ...", "markup action 608
(attach to jump target, title update) call N: ... -> gameTracker+0xc94 0x........", "attach point tru+0x32ba40 called
with box 0 ...". Built 2026-11-01 into `work\asi_rv05`, not loaded.

## 0.6: type-22 facing, wall movement, state 420 slot 1, chart log (2026-11-01)

Test 48k with 0.5: Lara attaches but faces the wrong way, does not stick and drops off early. The wall run is chart
record 1477 (Lara states 236 / 230 / 2102, parameter 0x19a = 608) under the root 1482 (states 420 / 572 / 1900).
Three title-update pieces on that path, each translated 1:1 (docs `Befund-Felsrinne.md` "Wall run: orientation,
magnet and duration"):

- **Facing** (option `AttachGeometry`): TU 0x824006a8 = PC tru+0x2fe7e0 (result -> gameTracker+0xcc0 at attach) has a
  new "type == 22 -> edge normal of segment 0" branch before the retail default. `FacingDefault` (5-byte jump at the
  default tru+0x2feb05) sends a type-22 box to the existing flag-0x8000 case tru+0x2feae4 (same code as the TU branch).
- **Wall movement** (`AttachGeometry`): TU 0x8245d6c8 = PC tru+0x370ba0: flag bit 0x10 "or type(gameTracker+0xc94)
  == 22" -> wall handler PC tru+0x353d30. `MoveDefault` (5-byte jump at tru+0x370de1) adds the type test.
- **State 420 slot 1** (`State420Slot1`): TU 0x8245e450 runs the attached movement also in slot 1 when doppelganger
  mode (TU gameTracker+0x1244 = `TruDlc2PlayerDoppelganger()` of TruDlc2Player.asi) and the bool parameter 0x19e are
  set; replaces PC tru+0x371320 (which keeps its callback store through the template tru+0x381d80).
- **Chart log** (`ChartLog`, `ChartLogFrom` / `ChartLogTo`, default 1470..1510; diagnostic): logs the player's chart
  record changes (machine update tru+0x387ebf, `[machine+0x510]`) with the record index and its Lara state ids.

Log lines: "attach facing: type 22 -> edge normal ...", "attached movement: attach box type 22 -> wall handler ...",
"state 420 slot 1: title-update body added ...", "chart log: ..."; at the wall "attach facing (...) type-22 box ...",
"attached movement (...) attach box 0x... type 22 ...", "state 420 slot 1 (TU 0x8245e450) call N: doppelganger 1,
parameter 0x19e 1 -> attached movement run", "chart: player record A -> B (Lara states [...])", and the 608 line now
with the record id (owner object) and the facing +0xcc0. The sample ini is unchanged (all new options default to 1).
Built 2026-11-01 into `work\asi_rv06`, not loaded.

## 0.7: chart log per machine, second-markup dump (2026-11-01)

Test 48l: all 0.6 parts fired; the crash after the wall run (AV tru+0x48198) was a data error (a VM literal of
doppelganger_casual.drm, fixed by `tools/vm_literal_fix.py`, docs `Befund-Felsrinne.md` point 9). 0.7 changes only
diagnostics: the chart log keeps the last record per machine (the player has two machines; 0.6 logged "-1 -> N" every
frame) and names the machine; the first 608 line also dumps 0x50 bytes of the box's second markup `[box+0x24]` (the
type 22 comes from there). Built into `work\asi_rv07`, not loaded.

## 0.8: type-22 jump-off / fall geometry (2026-11-02)

The remaining title-update type-22 branches of the attach geometry (docs `Fehlliste-2026-11-02.md`, `Befund-Felsrinne.md`
"Condition 528 and the missing list"), option `JumpGeometry` (default 1; the sample ini is unchanged). Each piece uses
the TU's inline type test (second markup `+0x24` -> byte `+0x4d`, else file record `+0x20` -> byte `+0x33`, == 22) and
checks its bytes first (`work\asi_rv08\prechecks_v08.txt`, 12 checks, 0 mismatches against the Steam `tru.exe`):

| TU function | PC | change |
|---|---|---|
| 0x823fe9d0 segment range | tru+0x2fe040, at +0x2fe0e5 | flag 0x400000 **or type 22** -> last segment index - 1 |
| 0x823fd890 TNode attach point | tru+0x307c60, default +0x307fc8 | type 22 -> position + 47.4075 x normalize(facing), z - 474.075 (TU constants 0x82051bc0 / 0x8207e5ac) |
| 0x823fe130 bone attach point | tru+0x311530, default +0x3117e3 | type 22 -> position + 47.4075 x normalize(tru+0x2fe7e0(box, segment, position)) |
| 0x82400bc0 corner angle, 2 sites | tru+0x309500 at +0x3097cb / +0x309894 | flag 0x400000 **or type 22** -> skip the angle |

Not translated in 0.8: TU 0x8242a7c8 (see 0.9). Hits are counted in the stubs and logged by the chart probe
(`ChartLog=1`): first hit, then every power of two at `LogLevel=2`. Load lines: "<piece>: title-update type-22 branch
added (0x...)" x 5 and "jump geometry: 5 of 5 type-22 branches added". Built 2026-11-02 into `work\asi_rv08`, not loaded.

## 0.9: the fifth geometry function (2026-11-02)

Docs `Befund-TU-Funktionen.md` L1: retail 0x82427750 = **PC tru+0x34d390** (TU 0x8242a7c8; found by its constants and
calls). After the flag test `box +0x28 & 0x400000` the TU inserted 0x8242a898..0x8242a8c4: the same inline type test and
`type == 22 -> 0x8242abac`, the block the 0x400000 flag takes (PC tru+0x34d4bf: `call 0x5c3cc0` on the box, jmp
0x74d710). The stub replaces `test eax,400000h; je 0x74d4d5` at tru+0x34d4b8 (7 bytes; eax = [esi+28h], esi = box):
flag or type 22 -> tru+0x34d4bf, else tru+0x34d4d5 with eax kept for the 0x8000 / 0x40000000 tests. Option
`SkipGeometry` (default 1; sample ini unchanged), byte checks of the function entry and the site
(`work\asi\v09\prechecks_v09.txt`). With it **11 of 11** TU geometry functions are translated. Load line: "fifth
geometry function: title-update type-22 branch added (...)"; hit line (chart probe): "fifth geometry function
(tru+0x34d390 site 0x74d4b8 = TU 0x8242a8c4): type-22 box takes the flag-0x400000 path (n hits)". Built 2026-11-02 into
`work\asi_rv09`, not loaded.

**TO TEST (0.9)**

| # | test | what the owner should see |
|---|---|---|
| 1 | DLC 2, first rock vein: jump onto it, run along, jump off / fall off | load line "fifth geometry function: ... added"; at the vein "fifth geometry function (...) (1 hits)" next to the 0.8 hit lines; behaviour as 50h or better (no snap to a wrong edge) |
| 2 | main game level with ledges | unchanged (type 22 exists only in DLC 2; no hit line) |

## 0.10: SweepAndPrune limits as the title update (2026-11-08)

The MarkupManager (owner `[0xdb94cc]`) keeps the markup boxes (ledges, grabs, climb lines, rock veins) in a
SweepAndPrune collision pool. Its constructor (PC tru+0x1be3a0 = retail 0x8227eda8 = **TU 0x8227b9f0**) is run once by
the game init tru+0x1df390 (direct call chain tru+0x1df410 -> tru+0x1d9e70 -> tru+0x1d9eb7 -> ctor, measured). The
title update creates the pool larger (docs `Befund-SweepAndPrune-0611.md` section 3, `Befund-P5-Kleinkram-0711.md`
row 7b, `work\sap_0611\tu_8227b9f0.txt`):

| | PC / retail | title update | 0.10 on PC |
|---|---|---|---|
| SAP create (boxes N, pair parameter M) | (1000, 200) | (**3000, 500**) TU 0x8227ba18 / 0x8227ba20 | tru+0x1be3a7 `68 c8 00 00 00 68 e8 03 00 00` -> `68 f4 01 00 00 68 b8 0b 00 00` |
| pair links (pool M x 16 bytes, 2 links per entry) | 400 | 1000 | 1000 |
| copy of the pair parameter (never read) | +0x20 = 200 | +0x24 = **500** (0x8227ba3c; the TU inserted +0x1c) | tru+0x1be3c4 `c7 46 20 c8 00 00 00` -> `c7 46 20 f4 01 00 00` |
| new field +0x1c = 3000 | - | 0 readers | not taken (would shift the owner layout) |
| proxies +0x18 | 1000 | 1000 | unchanged |
| core memory counter +0x20 | 207 201 | - | 620 001 (+412 800 bytes once, game allocator) |
| box 0x50 -> 0x70 bytes + move threshold (UpdateBox) | - | yes | not taken (K2b, no capacity effect) |

`PatchSweepAndPrune` (option `[SweepAndPrune] Translate`, default 1, now in the sample ini) runs first in DllMain. It
checks the constructor entry, the bytes between and after both sites, the getter tru+0x1be390, the owner store
tru+0x1d9ec6 and the two core-constructor stores tru+0x6c880 / +0x6c895 (`work\asi\rv10\prechecks_v10.txt`, 10 checks,
0 mismatches against the Steam `tru.exe`), and that `[0xdb94cc]` / `[0xe7f060]` are still 0 (zero-initialised data:
the game init has not run). An exe that already holds (3000, 500) is left alone. Control: on the first machine update
(the 0.6 chart probe at tru+0x387ebf, now also installed when `ChartLog=0` but `Translate=1`) one line with the values
the game really holds. With `Translate=0` the same line shows the PC values.

Log lines: "SweepAndPrune: limits as the title update (TU 0x8227b9f0: create(3000, 500) = 3000 boxes, 1000 pair links,
+412800 bytes; ...)", then "SweepAndPrune control (first frame): MarkupManager 0x..., core 0x...: boxes +0x24 = 3000,
pair parameter +0x2c = 500 (1000 pair links), memory +0x20 = 620001, owner +0x20 = 500, proxies 1000 -> as the title
update (3000 / 500)". Errors: "... does not match - limits not changed", "MarkupManager already built ... - loaded after
the game init", "control ... NOT as expected". TruMenu 0.21.7 `sap.status` reads N and M from the core, so it shows
"Boxen b/3000, Paare p/1000". Built 2026-11-08 into `work\asi\rv10` (install: `Set-TruRockVein.ps1 -Install -SourceDir
work\asi\rv10`), not loaded.

**TO TEST (0.10)**

| # | test | what the owner should see |
|---|---|---|
| 1 | start the game with 0.10 installed, load any level | `TruRockVein.log`: "SweepAndPrune: limits as the title update ..." at load, then one "SweepAndPrune control (first frame): ... boxes +0x24 = 3000, pair parameter +0x2c = 500 (1000 pair links), memory +0x20 = 620001, owner +0x20 = 500, proxies 1000 -> as the title update (3000 / 500)" |
| 2 | TruMenu `sap.status` in a markup-rich unit (DLC 2 rock-vein area, a main-game climbing hall) | "Boxen b/3000 ..., Paare p/1000 ..."; no "Out of space" warning |
| 3 | `[SweepAndPrune] Translate=0`, restart | control line "... boxes +0x24 = 1000, pair parameter +0x2c = 200 (400 pair links), memory +0x20 = 207201, owner +0x20 = 200 ... -> PC limits (Translate=0)"; `sap.status` "b/1000, p/400" |
| 4 | play a while (loading areas, DLC 2) | no change in behaviour, no crash (memory +412 800 bytes only) |

## 0.11: ledge-corner nudge as the title update (2026-11-08)

Published TU fix (TeamXbox 09.03.2009): "Fixed a ledge corner transition problem from TRU where Lara could end up stuck
on a ledge". Located in code by 17w (ENGINE.md section 14 "Ledge corner", `docs\Befund-17w-TU-Fixes-0811.md` row 2);
translated 1:1 here (package 18a, statically proven, `work\ledge18a_0811\`).

| | retail / PC | title update | 0.11 on PC |
|---|---|---|---|
| ledge function | retail 0x8242bc30 / PC tru+0x34e5a0 (0x74e5a0) | TU 0x8242ecd8 | - |
| tracker `[0xfadb58]` (TU `[0x829892b0]`) | +0xc94 box, +0xc98 t, +0xeac partner box, +0xeb0 partner t | same fields | read, +0xc98 written |
| after "box and partner set, both flag 0x40000000" | PC 0x74e7c6..0x74e80e, then the segment fetch 0x5c3aa0 | TU ..0x8242eea8, then **inserted block 0x8242eeac..0x8242ef40**, then 0x8227b6e0 | hook **0x74e814** (8 bytes `movss xmm1,[0x841134]`, executed in the stub) |
| look-ahead direction | called late: retail 0x8242c00c, PC **0x74eaed** (`call 0x787ef0`, `cmp eax,4` at 0x74eafe) | called once at 0x8242eebc (`bl 0x82489d10`, r30), reused at 0x8242f094 | called once in the hook, result reused at 0x74eaed (`call LookAheadReuse`) |
| nudge | - | partner box == box and `floorf(partner t) == floorf(t)`: t = floor - **0.001** (direction 4), else floor + **1.01** | the same; floor = the exe's floor 0x813510 rounded to float |
| constants | PC `[0x841634]` = 0x3a83126f (already used for t = 0) | TU f30 = `[0x82053608]` = 0x3a83126f (0.001f), `[0x8207ddf8]` = 0x3f8147ae (1.01f) | the two TU words |

Why the result is reused and not computed a second time: 0x787ef0 (parameter 0x1f3 of the agent -> 1..6) is not free of
side effects - 0x783f50 stores the resolved node in `[agent+0x520]`, 0x784b30 counts each access in the node
(`add word [ecx+2],1`) and rebalances (0x783d40). The TU calls it once; so does 0.11. 0x74e814..0x74eaed is one straight
line (one forward `je` inside, no jump from outside into it, `ebx` = the argument, written only at 0x74e5c4). The stub
keeps all registers, flags and xmm0-xmm7; the x87 stack is empty at the hook. If the stub has not run,
`LookAheadReuse` calls the original 0x787ef0.

Option: `[LedgeCorner] Translate` (default 1, in the sample ini). Log lines: "ledge corner: title-update nudge added
(tru+0x34e5a0 = TU 0x8242ecd8, block 0x8242eeac; hook 0x0074e814, look-ahead result reused at 0x0074eaed; ...)" at load,
then on the first nudge (at `LogLevel=2` every power of two) "ledge corner: title-update nudge (TU 0x8242eeac): box
0x..., partner t ..., t ... -> ... (look-ahead d) (n nudges)". Errors: "ledge function at ... does not match -
ledge-corner nudge not added". `Translate=0`: "ledge corner: Translate=0 - PC ledge code kept". Built 2026-11-08 into
`work\asi\rv11` (install: `Set-TruRockVein.ps1 -Install -SourceDir work\asi\rv11`), not loaded, not tested in the game.
Known spots: our sources name no level; `docs\Recherche-QoL-Beschwerden-0811.md` links the fix to the TR Chronicles
bug list entries G5a / G15 (shimmying round corners, also on PC) - not re-checked offline.

**TO TEST (0.11)**

| # | test | what the owner should see |
|---|---|---|
| 1 | start the game with 0.11 installed | `TruRockVein.log`: "TruRockVein 0.11 loaded (... ledge corner translate 1)" and "ledge corner: title-update nudge added ..." |
| 2 | hang on a ledge and shimmy round outer and inner corners (corners where Lara used to stop or get stuck; G5a / G15 spots if known) | Lara goes round the corner; the first time one "ledge corner: title-update nudge ..." line (t moved to floor - 0.001 or floor + 1.01) |
| 3 | the same corner with `[LedgeCorner] Translate=0` | the PC behaviour as before, no nudge line |
| 4 | ledge climbing in general, DLC 2 rock veins (0.4-0.9 paths) | no change elsewhere, no crash; with `LogLevel=2` the nudge count grows only at corners |

## 0.12: jump targets on vertical segments as the title update (2026-11-11)

Published TU fix (TeamXbox 09.03.2009): "Improved jump targeting for pillar jumps". Located in code by 17w
(`docs\Befund-17w-TU-Fixes-0811.md` row 1, ENGINE.md section 14 "Jump targeting"), translated 1:1 here (Q61,
statically proven, `work\q61_jumptarget_1111\`, finding `docs\Befund-Sprungziele-Q61-1111.md` in the workspace).

Jump targeting tests Lara's jump parabola against every markup segment: ParabolaVsSegment (PC tru+0x2f9940 = retail
0x823f43d8 = **TU 0x823f6b08**). Its general case (PC 0x6fa83f, TU +0x96c) runs when the segment is (nearly)
**vertical** - PC `dl`: `|dx| + |dy| < 0.05 x max(|dz|, 0.001)` (0x6f9c41..0x6f9c8b) - and the jump has horizontal
speed (`[esp+2Fh]` = 0: `|vx| + |vy| >= 0.001 x (|vz| + 1)`, 0x6f9cf7..0x6f9d21). Ledges (horizontal) never take it;
vertical poles and pillars do.

| | retail / PC (0x6fa855..0x6fa91d) | title update (TU +0x96c..+0xa08) | 0.12 on PC |
|---|---|---|---|
| t | `-dot(v, p) / k` (p = start - A without its part along the segment, k = \|v⊥\|² + p·g: one Newton step from t = 0 towards the closest approach to the segment's line), then **max(t, 0)**, min(t, tMax) | the same, then **\|t\|** (fcmpu / bge / fneg), min(t, tMax), max(t, 0) (two fsel) | as the TU |
| target | the segment point closest to parabola(t); returns **1** with that t | the same point, then **ParabolaVsPoint**(tOut, ptOut, parabola, point, clamp 1) (TU 0x823f6950 = retail 0x823f4220 = PC **0x6f96c0**): the cubic for the closest approach to that point, **0..2** times | the PC's own 0x46ab60 and 0x6f96c0, count returned |
| constants | 0.5 (double 0x8413c0) | f29 = 0.5, -1.0 at r5-0x11a0 (the `fchs` of the PC) | 0.5f |

Hook: the 16 bytes `fchs; fdiv [esp+0A8h]; add esp,8; fstp [esp+18h]` at **0x6fa855** run in the stub (4 whole
instructions, no branch into them, 0x6fa83f is reached only by the je at 0x6fa4a0). Then the frame S: `[S+18h]` t,
`[S+48h]` tOut, `[S+4Ch]` ptOut, `[S+50h]` velocity, `[S+80h]` origin, `[S+0F0h]` gravity vector, esi parabola (+0x24
tMax), edi / ebx the segment points (not written between the hook and the call 0x6fa8f7). TU path: `JumpTargetTu`
writes the position to `[S+90h]` (mulps / addps like 0x6fa8b3..0x6fa8eb), calls 0x46ab60 into `[S+30h]`, then
0x6f96c0, and leaves through the epilogue 0x6fa488 with the count in eax. PC path: back to 0x6fa865. All five callers
take 0..2 (0x70fe22 skips 0, the four in 0x6fad70 loop over the count).

Option: `[JumpTarget] Translate` (default 1, like every untested TU translation of this plugin; in the sample ini).
0 at the game start = nothing patched; with 1 at the start the key is read again at run time (at most once a second,
when the general case runs): 0 then takes the PC path. Log lines: "jump target: title-update vertical-segment case
added (...)" at load; on the first case (at `LogLevel=2` every power of two) "jump target: title-update
vertical-segment case (TU 0x823f6b08 +0x96c): t A -> B (PC: C), segment point (x, y, z), ParabolaVsPoint -> n
target(s) t D (k cases)"; once each "jump target: first negative t ..." and "jump target: first vertical segment the
TU rejects ...". Live switch: "jump target: switch [JumpTarget] Translate 1 -> 0 ...". Errors: "ParabolaVsSegment at
... does not match - title-update jump targeting not added". Built 2026-11-11 into `work\asi\rv12` (install:
`Set-TruRockVein.ps1 -Install -SourceDir work\asi\rv12`), not loaded, not tested in the game.

Known spot: Croft Manor unit `l3_caverns_start` holds a type-15 **pillar** markup (id 963) whose two points differ only
in z (1 343 units, item matrix = identity; `tools/markup_level.py --raw` on `work\manor_0611\pcbig\`) - a vertical
segment, so a jump towards it takes the general case. Other levels are not scanned (only these 9 manor units are
extracted); every vertical pole (types 4 / 5) and pillar (15) markup is a candidate.

**TO TEST (0.12)**

| # | test | what the owner should see |
|---|---|---|
| 1 | start the game with 0.12 installed | `TruRockVein.log`: "TruRockVein 0.12 loaded (... jump target translate 1)" and "jump target: title-update vertical-segment case added ..." |
| 2 | jump at a vertical pole or pillar from the side (Croft Manor caverns start, pillar id 963; any level with vertical poles) - also jumps where Lara used to miss, grab too low / high or not aim at the pole | one "jump target: title-update vertical-segment case ..." line (t and the PC's t side by side); Lara lands on / grabs the pole; a "first negative t" line shows a case the PC aimed at the jump start |
| 3 | the same jump with `LogLevel=2`, then set `[JumpTarget] Translate=0` in the ini while the game runs, jump again | "switch [JumpTarget] Translate 1 -> 0"; the case count stops growing (PC path); 1 again switches back |
| 4 | ledge jumps, horizontal poles, DLC 2 rock veins | no change, no case line for horizontal segments, no crash |

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruRockVein` (installed Visual Studio, x86, `/MT`, imports only
  KERNEL32) -> `work\asi\TruRockVein.asi` + `TruRockVein.ini`.
- Install: `scripts\windows\Set-TruRockVein.ps1 -Install` (game closed); the Ultimate ASI Loader the game ships as
  `binkw32.dll` loads every `*.asi` next to `tru.exe`. Remove: `Set-TruRockVein.ps1 -Remove` (only our own files).
- Options: `TruRockVein.ini` - `Enabled`, `LogLevel` (0-3), `LogUnhandled`, `Type607` / `Type608`, `LogBadValues`,
  `LogDefaultConditions`, `MarkupTypes`, `MarkupSlots`, `NullBoxGuard`, `MarkupAction608`, `AttachGeometry`,
  `State420Slot1`, `ChartLog` (`ChartLogFrom` / `ChartLogTo`), `JumpGeometry`, `SkipGeometry` (0.9) - the switches from
  `MarkupTypes` on default to 1, the chart range to 1470..1510; section `[SweepAndPrune]`: `Translate` (0.10, default 1,
  read at the game start); section `[LedgeCorner]`: `Translate` (0.11, default 1); section `[JumpTarget]`: `Translate`
  (0.12, default 1, read again at run time when 1 at the start). Log:
  `TruRockVein.log` next to `tru.exe`.

## Test

DLC 2 right after the start (e.g. with the test direct start): at the first rock vein hold LB or RB and press A.
`TruRockVein.log` shows "condition 607 / 608 is now evaluated" when the state machine asks for them, and with
`LogLevel=2` every change of the result (markup type found). License: MIT, as the repository.
