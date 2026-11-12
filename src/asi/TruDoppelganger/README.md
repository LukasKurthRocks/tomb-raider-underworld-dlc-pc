# TruDoppelganger.asi

DLC 2 *Lara's Shadow*: the state-machine ids the Xbox title update added for the DLC 2 player (the doppelganger), for
the PC `tru.exe` - see docs/PLUGINS.md, "How the Xbox title update is brought to PC", and
docs/WINDOWS_REBUILD.md finding 43. **Not yet played** - first build 2026-10-30.

## 0.1.1: dated log lines (Q107, 2026-11-12)

Built 2026-11-12 into `work\asi\i_1211\TruDoppelganger`, not installed, not played. Only the log format changed
(shared helper `src\asi\TruLog.h`): every line of `TruDoppelganger.log` starts with `YYYY-MM-DD HH:MM:SS.mmm`, and
each game process writes one header line `=== <date time> TruDoppelganger 0.1.1 session start (pid n) ===` before its
first line. Tables and options are as in 0.1. Install:
`scripts\windows\Set-TruDoppelganger.ps1 -Install -SourceDir work\asi\i_1211\TruDoppelganger`.

| # | TO TEST 0.1.1 | expected |
|---|---|---|
| 1 | start the game once with 0.1.1 installed, read `TruDoppelganger.log` from its last `session start` line on | the header names 0.1.1; every newer line (incl. `TruDoppelganger loaded ...`) starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start |

## What it does

Lara's moves run through a data-driven state machine. Its builder (Xbox TU 0x82489500, PC tru+0x3872f0) registers
every condition, activity and state id once, from three static tables. The title update changed only these tables
(the builder and the handler functions are byte-equal to retail) and added 13 conditions, 9 activities and 8 states.
The DLC 2 player data (`player_tru_dlc2_extension.drm`) uses some of them; the PC exe has the retail tables.

| | new ids (Xbox title update) | Xbox handler | PC handler (same function, paired by shared ids) |
|---|---|---|---|
| conditions | 1048-1056, 2005, 2006, 2013 (group 2000), 2401 (group 2400) | `SCCondFunction_Default` 0x82484db0 | tru+0x382140 |
| activities | 286, 1009, 1040-1045 | 0x82488dc0 | tru+0x386f30 |
| | 1039 | 0x82488d28 | tru+0x384cf0 |
| states | 243-245, 1017-1020, 2102 | 0x82482600 (all six slots) | tru+0x381d10 |

The plugin copies the three PC tables, appends these records before the closing id-0 record and points the builder's
three `push table` operands (tru+0x387343 / +0x38735a / +0x38736a) at the copies; the builder itself is not changed.
It checks the image base, the builder code, that the builder has not run yet, the table sizes (307 / 332 / 199), the
reused handlers (at ids 21, 101, 203 and 2, and their first bytes) and that none of the new ids exists; on any
mismatch it patches nothing and logs why.

Not ported: `DoppelgangerInit` (Xbox TU 0x82412c48), the init of the TU-only player object type
`doppelganger_casual`, which sets the "doppelganger player" byte gameTracker+0x1244. Only TU code the PC exe does not
have reads that byte (and the `dlc2data` native f0), so it would change nothing yet.

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruDoppelganger` (installed Visual Studio, x86, `/MT`, imports only
  KERNEL32) -> `work\asi\TruDoppelganger.asi` + `TruDoppelganger.ini`.
- Install: `scripts\windows\Set-TruDoppelganger.ps1 -Install` (game closed); the Ultimate ASI Loader the game ships as
  `binkw32.dll` loads every `*.asi` next to `tru.exe`. Remove: `Set-TruDoppelganger.ps1 -Remove` (only our own files).
- Options: `TruDoppelganger.ini` - `Enabled`, `LogLevel` (0-3), `AddConditions`, `AddActivities`, `AddStates`. Log:
  `TruDoppelganger.log` next to `tru.exe`.

## Test

Together with TruRockVein.asi: DLC 2 right after the start, first rock vein, LB/RB + A. `TruDoppelganger.log` shows
"title-update ids registered" at game start; `TruRockVein.log` should now show "condition 607 / 608 is now
evaluated". The new conditions all use `SCCondFunction_Default`, as on the Xbox (it returns true). License: MIT, as
the repository.
