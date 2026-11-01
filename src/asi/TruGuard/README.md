# TruGuard.asi

Developer plugin for the PC `tru.exe`: reports faults that happen **inside the game's own code** with enough detail
to fix the data or script that caused them, optionally writes one minidump per fault site and - only when explicitly
enabled - lets the game continue past a known bad read/write. Diagnosis only; it patches no game code and changes no
gameplay value outside the resume option.

Built 2026-11-01. Offline-tested against a stand-alone 32-bit test program (handled fault, unhandled fault, dump,
resume, no-rule fallback, stack overflow); **not yet played**. See `OPENCODE-FUNDE.md` in the repository root and
`docs/TruGuard-Plan.md`.

## What it does

- First-chance vectored handler, but only for addresses inside `tru.exe` (`[base, base + SizeOfImage)`), so other
  ASIs' guarded probes, guard pages, breakpoints, single-step and debug prints are untouched.
- Codes: access violation, illegal instruction, div/0, integer overflow, privileged instruction, in-page error,
  stack overflow.
- Compact first-chance line **once per site**; the full record comes from the unhandled-exception filter (a real
  crash) or immediately in `Mode=2`. So faults the game handles itself (its own `__try/__except`) stay one-liners.
- Full record: `tru.exe+offset`, exception code, instruction bytes + decoded length, registers, fault address and the
  memory around the involved pointers, EBP stack chain plus raw stack words, module+offset, known-site name from the
  table taken from the findings docs, and the game context (unit name/id, cheatMode, player instance/state, object
  id/name).
- One minidump per site into `TruGuardDumps\`, at most `MaxDumps` files per run (dbghelp is loaded dynamically, so the plugin imports only KERNEL32).
- Everything in the handler uses a pre-opened log handle, fixed stack buffers, a re-entry flag and a short spinlock
  timeout - no heap, no CRT file locks. If the handler itself faults, it steps aside and the game crashes normally.

## Modes

| `Mode` | behaviour |
|---|---|
| 0 | log only (no dump, never continues) |
| 1 | log + dump (default) |
| 2 | log + dump + continue when a `[Sites]` rule says how (or `SkipUnknown=1`) |

Continuing is only attempted for a site with a rule and only for a read/write/execute access that the rule allows
(`AllowWriteSkip`, `AllowExecuteSkip`). A DEP fault (`access=8` with `eip == fault`) and a stack overflow are never
resumed. Without a matching rule the process crashes exactly as before.

## Options (`TruGuard.ini`, next to `tru.exe`)

`Enabled`, `LogLevel` (0-3; the log is `TruGuard.log` next to `tru.exe`), `Mode` (0-2), `Dump`, `DumpType` (0/1/2 ->
none / mini / full memory), `MaxDumps`, `MaxHitsPerSite`, `SkipUnknown`, `AllowWriteSkip`, `AllowExecuteSkip`,
`FirstChance`, `LogStack`, `LogContext`. `[Sites]` takes `SiteN=<offset>,<skip>[,<eax>[,<ecx>[,<limit>]]]` with the
`tru.exe` offset in hex, `-1` = leave the register alone, `skip < 0` = decode the instruction length, `skip = 0` =
never continue at this site.

The shipped INI keeps both documented NULL-native sites commented out:

```
; Site1=0x17dea3,3,-1,-1,8
; Site2=0x17deae,2,0,-1,8
```

## Reading it from the other tools

Exports: `TruGuardVersion`, `TruGuardCount` (first-chance exceptions), `TruGuardDistinct` (sites),
`TruGuardMode`, `TruGuardLast`, `TruGuardStatus`, `TruGuardSetMode`.

TruMenu: `guard.status`, `guard.count`, `guard.last`, `guard.mode` (0..2), `guard.overlay` (top-right corner).
TruLink reaches the same items with `menu <id>`, e.g. `menu guard.status`, `menu guard.mode 2`.

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruGuard` -> `work\asi\TruGuard.asi` + `TruGuard.ini`.
- Install: `scripts\windows\Set-TruGuard.ps1 -Install` (game closed). Remove: `-Remove` (only our own files; log and
  dumps stay).
- Log: `TruGuard.log`, dumps: `TruGuardDumps\TruGuard_<run>_site<offset>_<n>.dmp` next to `tru.exe`.
  `Invoke-TruTestRun.ps1` collects both into the run folder.

## Limits

- Minidumps are written from inside the exception handler; dbghelp can block briefly. Turn dumps off (`Dump=0`) if a
  run must not stall. A helper thread for the dump is not built.
- Under a debugger Windows may skip the unhandled-exception filter; then only the compact first-chance lines exist.
- The stack walk follows the EBP chain only (functions without a frame pointer are missing); raw stack words help.
- The known-site names are a snapshot from the documentation, not symbols.
- `SkipUnknown=1` guesses; it can turn a clean crash into a wrong value. Keep it off except for hunting more sites.
- Byte-level details (skip length, register values) for the documented sites can only be confirmed in-game.
