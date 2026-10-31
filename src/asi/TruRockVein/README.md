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

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruRockVein` (installed Visual Studio, x86, `/MT`, imports only
  KERNEL32) -> `work\asi\TruRockVein.asi` + `TruRockVein.ini`.
- Install: `scripts\windows\Set-TruRockVein.ps1 -Install` (game closed); the Ultimate ASI Loader the game ships as
  `binkw32.dll` loads every `*.asi` next to `tru.exe`. Remove: `Set-TruRockVein.ps1 -Remove` (only our own files).
- Options: `TruRockVein.ini` - `Enabled`, `LogLevel` (0-3), `LogUnhandled`, `Type607` / `Type608`, `LogBadValues`,
  `LogDefaultConditions`. Log:
  `TruRockVein.log` next to `tru.exe`.

## Test

DLC 2 right after the start (e.g. with the test direct start): at the first rock vein hold LB or RB and press A.
`TruRockVein.log` shows "condition 607 / 608 is now evaluated" when the state machine asks for them, and with
`LogLevel=2` every change of the result (markup type found). License: MIT, as the repository.
