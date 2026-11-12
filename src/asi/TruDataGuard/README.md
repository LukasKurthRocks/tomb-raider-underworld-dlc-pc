# TruDataGuard.asi

A safety net and detector for converter data faults: an invalid section id becomes a logged "not found" instead of a
crash - at known lookup points only, using the engine's own not-found path. The real fix stays in the converter.
Brief: `docs\Plan-TruDataGuard.md` (workspace). 0.1 built 2026-11-02 into `work\asi\dataguard01` (live runs 50j /
50k), 0.2 built 2026-11-02 into `work\asi\dataguard02` (installed 2026-11-02), 0.2.1 built 2026-11-12 into
`work\asi\i_1211\TruDataGuard` (not installed, not played).

## 0.2.1: dated log lines (Q107, 2026-11-12)

Only the log format changed (shared helper `src\asi\TruLog.h`): every line of `TruDataGuard.log` starts with
`YYYY-MM-DD HH:MM:SS.mmm`, and each game process writes one header line
`=== <date time> TruDataGuard 0.2.1 session start (pid n) ===` before its first line. Hooks, options and checks are as
in 0.2. Install: `scripts\windows\Set-TruDataGuard.ps1 -Install -SourceDir work\asi\i_1211\TruDataGuard`.

| # | TO TEST 0.2.1 | expected |
|---|---|---|
| 1 | start the game once with 0.2.1 installed, read `TruDataGuard.log` from its last `session start` line on | header and `loaded` line name 0.2.1; every newer line starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start |

## 0.2: no false positives in the unload callback (refs 0 is legitimate)

**Seen with 0.1** (runs `20261102_213052_regress_shadowlara_50j`, `20261102_221539_..._50k`,
`20261102_224047_..._50k`): at a level change 20 detailed hit lines within ~0.2 s (`LogFirst=20`; later hits only
counted - the 221539 run reached hit 233), all `table entry ... is not a section record` from caller tru+0x18bd3a
(does not test for 0, so 0.1 only logged and ran the original lookup; no crash from it).
Ids 0x5950, 0x4ef5, 0x03b4, 0x68f1, ... - all below 0x8000, entries 16-byte aligned heap pointers.

**Cause** (static, byte-checked by `dataguard_check.py hits --exe`): the section release tru+0x14f320 (section manager
vtable 0x84c990 +0x18) decrements `refs`; at 0 it calls the type pre-unload tru+0x14f200 and then the unload callback of
the type handler, `[0xc57000 + type*4]` vtable +8, with the id - the entry is still in the table, the record still
intact, only `refs` is already 0. After the callback it frees the record and clears the entry. The type-13 handler
(object with vtable 0x84ca70, stored at [0xc57034] by tru+0x15259d) has tru+0x18bd30 as +8: `lookup(id)` (return
tru+0x18bd3a), result passed to tru+0x18b3b0 with `ecx = [0x8a8100]` (the same manager as the music code next to it).
0.1 rejected `refs 0`, i.e. exactly this release state. In the later full dump of 50j all 20 ids are loaded again with
type 13 (refs 1), which matches the handler. Other legitimate field values: the register tru+0x14dd10 / re-register
tru+0x14ddb0 write `loading` 1 (cleared to 0 by tru+0x14deb0), `refs` 1 or the old count, `type` a byte (masked
`& 0x7f` in tru+0x14ddb0; the handler table 0xc57000 has 0x80 slots).

**Rule 0.2**: `refs` is no longer checked. Still rejected: id >= 0x8000 (id -1 -> 0 without a hit), entry not 16-byte
aligned or below 0x10000, loading flag > 1, type > 0x7f; entry 0 / loading 1 -> the engine's 0 as before. A hit line
for a rejected record now shows its header (`... is not a section record: refs N, loading N, type N`).

**Replay** (`work\asi\dataguard02`):
- `hits_replay.txt` (`dataguard_check.py hits --exe EXE <4 logs> --dump <50j dump>`): 61 hit lines of the four 0.1
  logs (one log without hits) - 60 table-entry hits of tru+0x18bd3a, replayed in the release state (refs 0, loading 0,
  type 13): 0.1 rejects 60, 0.2 rejects 0; 1 out-of-table id (0x68f40000, 50k hit 233 at guarded caller tru+0x194cad,
  dlc_yggdrasil_hall02 - a true hit, swapped u16 halves of 0x68f4): rejected by both. Release path bytes: 5 of 5 ok.
- `table_replay.txt` (`dataguard_check.py table` on the full dumps of 50f / 50h / 50j / 50k): every non-zero entry
  passes (2317 / 2718 / 2734 / 2734, rejected 0 under 0.1 and 0.2); the recorded bad ids 0x688c0000 (50d),
  0x495f0000 (50e), 0x04900000 (50f), 0x00652000 (50h) and 0x68f40000 (50k) are rejected; the dump exceptions of
  50f / 50h are rejected.
- Self test `selftest.txt`: 31 passed, 0 failed (new: refs 0 -> record, refs 0 + loading -> 0 without hit, loading
  flag 2 -> rejected, 0x68f40000 -> rejected, unguarded caller with refs 0 -> no hit).
- Byte checks `prechecks_dg02.txt` (identical to 0.1's): 93 checks, 0 mismatches (`prechecks_result.txt`).

0.1's `TruDataGuard.asi` (sha256 40e29d09...) and the unchanged sample .ini (0c48da5d...) are listed in
`Set-TruDataGuard.ps1` `$earlierBuilds`, so `-Install` of 0.2 replaces 0.1 and `-Remove` removes either.

## 0.1: section lookup tru+0x14df80 and exists test tru+0x14df70

| | PC tru.exe |
|---|---|
| lookup | tru+0x14df80 (cdecl, id): `[id*4 + 0xc36f28]` -> record; 0, or record still loading (`+4` != 0) -> 0; else record + 0x10 |
| exists test | tru+0x14df70 (cdecl, id): `[id*4 + 0xc36f28] != 0` in `al`; one caller tru+0x12cd85 (`test al,al`) |
| table bound | 0x8000 entries: the register function tru+0x14dd10 asserts `0 < id < 0x8000` (byte-checked at load) |
| record | `{u16 refs, u16, u8 loading, u8 type (flags >> 1 & 0x7f)}`, 0x10-byte header, data at +0x10; free clears the entry |

Crashes of 2026-11-02 that went through the lookup (docs `Befund-Felsrinne.md`): id 0x688c0000 (50d, player event
0x87, read 0xa2f36f28), 0x495f0000 (50e, fx node, entry 0x2104), 0x04900000 (50f, state-chart parameter), 0x00652000
(50h, thrall anim event list). All four are outside the table.

**Rule** (checked before anything is dereferenced): id >= 0x8000 -> rejected (id -1 = the engine's "none" -> 0, no
hit); entry 0 / loading -> the engine's 0 as before; entry not 16-byte aligned, below 0x10000, refs 0 (0.1 only, see
0.2), loading flag > 1 or type > 0x7f -> rejected. In the full dumps of 50f / 50h every non-zero entry passes (2317 / 2718, all 16-byte
aligned, refs 1..9, type <= 34) and all four recorded ids are rejected (`work\asi\dataguard01\table_replay.txt`).

**Callers** (`tools/dataguard_check.py callers`, 220 sites, `work\asi\dataguard01\callers.txt`): a rejected lookup
returns 0 only to the **86** callers that test the result for 0 and whose 0 path does not dereference it (class TESTS,
list `kGuardedCallers`; each one byte-checked at load: E8 call to tru+0x14df80 right before the return address).
Not guarded: 32 DEREF (use the result without a test, e.g. 50f's tail jump to tru+0x1ee890 `fld [eax+3d4h]`), 26
ZDEREF (test, but the 0 path dereferences too - 24 sites tru+0x1d6216..0x1d6bd7 and tru+0x1db6f5 / 0x1db8ba), 7 ZRET (0 returned to
their own callers), 14 RET / tail jumps, 13 PASS, 41 UNKNOWN (heuristic gave no answer). For them the log line is
written and then the **original lookup runs** (`UncheckedCallers=0`, crash as before); `UncheckedCallers=1` returns 0
to them as well (a null dereference in the caller instead of a read through a garbage id). The 50d / 50e / 50h callers
are guarded, the 50f caller is not.

Each stub replaces the first 5 bytes of the function by a jump; the fast path uses only `eax` and the flags, like the
original. The slow path keeps `ecx` / `edx` / `xmm0-7` around the logging call. No exception handler: nothing is caught
after a fault.

## Log, options, export

- Hit line (always contains `invalid id`): `invalid id 0x00652000 (outside the section table 0..0x7fff) in section
  lookup tru+0x14df80, caller 0x005953f2 (tru+0x1953f2, tests for 0) -> returned 0 (not found); unit <stream unit>; hit 1`.
  The first `LogFirst` (20) hits and the first hit of every caller are logged at `LogLevel=1`; `LogLevel=2` adds every
  power of two, `3` every hit.
- Load lines: `guard on: section lookup tru+0x14df80 (... for 86 of 86 checked callers ...)`, `guard on: section
  exists test tru+0x14df70 (...)`; a byte mismatch switches only that guard off (`... does not match - guard off`).
- `TruDataGuard.ini` `[DataGuard]`: `Enabled`, `LogLevel`, `SectionLookup`, `SectionExists`, `UncheckedCallers`,
  `LogFirst`, `LogUnit`.
- Exports: `TruDataGuardHits()` (hit count, for TruMenu), `TruDataGuardLastHit(&id, &caller, &kind)`,
  `TruDataGuardSelfTest(buf, size)` (offline only, refuses in the game), `TruDataGuardVersion()`.

## Checks (offline)

- Byte checks: `../bin/pyt -t 300 tools/dataguard_check.py prechecks EXE src/asi/TruDataGuard/TruDataGuard.cpp
  work/asi/dataguard01/prechecks_dg01.txt` (source list = TESTS callers found now), then `tools/pe_bytes_check.py EXE
  --file ...`: 93 checks, 0 mismatches against the Steam `tru.exe` (sha256 6905b046...).
- Self test of the built stubs: `SelfTest.exe <dir>\TruDataGuard.asi` (source `SelfTest.cpp`, build line in its
  header): test table with good / loading / refs-0 / misaligned / 0x2104 entries, the four recorded ids, id 0x8000,
  -1, the unguarded original path, register preservation, the caller list - 25 passed, 0 failed (0.1; 0.2: 31 / 0).
- Hit replay: `../bin/pyt -t 900 tools/dataguard_check.py hits --exe EXE LOG [LOG ...] [--dump DUMP ...]` (see 0.2).

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruDataGuard -OutDir <repo>\work\asi\dataguard02` (0.1: dataguard01).
- Install: `scripts\windows\Set-TruDataGuard.ps1 -Install -SourceDir <repo>\work\asi\dataguard02` (game closed).
  Remove: `Set-TruDataGuard.ps1 -Remove` (only files with the hash of a build below `work\asi` or of a released build
  in `$earlierBuilds`). Harness: ASI name
  `TruDataGuard` in a profile's `asis`.

## Not done / open

- Optional guard 2 (event walker tru+0x318780, effect tree tru+0x1920b0 / 0x1935d0, state-chart parameter lookup
  tru+0x383f50 / 0x384b30) not started.
- TruMenu does not read `TruDataGuardHits` yet. Interplay with TruGuard (it records faults at tru+0x14df84) not
  checked; TruDataGuard loads first (alphabetical) and changes the bytes at tru+0x14df80..84.

License: MIT, as the repository.
