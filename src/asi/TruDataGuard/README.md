# TruDataGuard.asi

A safety net and detector for converter data faults: an invalid section id becomes a logged "not found" instead of a
crash - at known lookup points only, using the engine's own not-found path. The real fix stays in the converter.
Brief: `docs\Plan-TruDataGuard.md` (workspace). 0.1 built 2026-11-02 into `work\asi\dataguard01`, not loaded yet.

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
hit); entry 0 / loading -> the engine's 0 as before; entry not 16-byte aligned, below 0x10000, refs 0, loading flag > 1
or type > 0x7f -> rejected. In the full dumps of 50f / 50h every non-zero entry passes (2317 / 2718, all 16-byte
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
  -1, the unguarded original path, register preservation, the caller list - 25 passed, 0 failed.

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruDataGuard -OutDir <repo>\work\asi\dataguard01`.
- Install: `scripts\windows\Set-TruDataGuard.ps1 -Install -SourceDir <repo>\work\asi\dataguard01` (game closed).
  Remove: `Set-TruDataGuard.ps1 -Remove` (only files with the hash of a build below `work\asi`). Harness: ASI name
  `TruDataGuard` in a profile's `asis`.

## Not done / open

- Optional guard 2 (event walker tru+0x318780, effect tree tru+0x1920b0 / 0x1935d0, state-chart parameter lookup
  tru+0x383f50 / 0x384b30) not started.
- TruMenu does not read `TruDataGuardHits` yet. Interplay with TruGuard (it records faults at tru+0x14df84) not
  checked; TruDataGuard loads first (alphabetical) and changes the bytes at tru+0x14df80..84.

License: MIT, as the repository.
