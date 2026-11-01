# TruRockVein.asi

DLC 2 *Lara's Shadow*: the rock veins ("Felsrinnen") for the PC `tru.exe` - step 3.4a of bringing the Xbox title
update to PC (see the repository README, "How the Xbox title update is brought to PC", and docs/WINDOWS_REBUILD.md
finding 43). 0.1 played 2026-10-30 (patched, never asked - see 0.2); 0.2 built 2026-10-31, not yet played.

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

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruRockVein` (installed Visual Studio, x86, `/MT`, imports only
  KERNEL32) -> `work\asi\TruRockVein.asi` + `TruRockVein.ini`.
- Install: `scripts\windows\Set-TruRockVein.ps1 -Install` (game closed); the Ultimate ASI Loader the game ships as
  `binkw32.dll` loads every `*.asi` next to `tru.exe`. Remove: `Set-TruRockVein.ps1 -Remove` (only our own files).
- Options: `TruRockVein.ini` - `Enabled`, `LogLevel` (0-3), `LogUnhandled`, `Type607` / `Type608`, `LogBadValues`,
  `LogDefaultConditions`, `MarkupTypes`, `MarkupSlots`, `NullBoxGuard`, `MarkupAction608`. Log:
  `TruRockVein.log` next to `tru.exe`.

## Test

DLC 2 right after the start (e.g. with the test direct start): at the first rock vein hold LB or RB and press A.
`TruRockVein.log` shows "condition 607 / 608 is now evaluated" when the state machine asks for them, and with
`LogLevel=2` every change of the result (markup type found). License: MIT, as the repository.
