# TruGuard.asi

Developer plugin for the PC `tru.exe`: reports faults that happen **inside the game's own code** with enough detail
to fix the data or script that caused them, optionally writes one minidump per fault site and - only when explicitly
enabled - lets the game continue past a known bad read/write. Diagnosis only; it patches no game code and changes no
gameplay value outside the resume option.

Built 2026-11-02 (0.4). Offline-tested against a stand-alone 32-bit test program (handled fault, unhandled fault,
dump, on-demand dump with thread snapshot, fault chain, resume, resume storm, no-rule fallback, replaced
unhandled-exception filter, ignore list, dump failure, stack overflow, rail/event/context exports); **not yet
played**. See `OPENCODE-FUNDE.md` in the repository root and `docs/TruGuard-Plan.md`; the GuardRails design is in
`docs/GuardRails.md`.

## What it does

- First-chance vectored handler, but only for addresses inside `tru.exe` (`[base, base + SizeOfImage)`), so other
  ASIs' guarded probes, guard pages, breakpoints, single-step and debug prints are untouched.
- Codes: access violation, illegal instruction, div/0, integer overflow, privileged instruction, in-page error,
  stack overflow.
- Compact first-chance line **once per site**; with `FirstChanceDetail=1` (default) the full record is written at the
  first occurrence as well, so faults the game handles itself (its own `__try/__except`) are also documented. The
  unhandled-exception filter only adds the fatal state and the dump.
- `tru.exe` installs its own unhandled-exception filter during init (it imports `SetUnhandledExceptionFilter`), which
  replaces ours. The vectored handler therefore re-arms our filter at the next fault inside `tru.exe`; the old pointer
  is logged once. A list entry cannot be replaced, the filter pointer can.
- Full record: `tru.exe+offset`, exception code, instruction bytes + decoded length, registers, fault address and the
  memory around the involved pointers, EBP stack chain plus raw stack words, module+offset, known-site name from the
  table taken from the findings docs, and the game context (unit name/id, cheatMode, player instance, object id/name).
  Address note: the heap GameTracker is `[tru+0xfadb58]` (as in TruRockVein); the log label `playerstate` and the
  source constant `kGameTracker = 0x00e7f088` still name the static player/agent block, not the GameTracker.
- One minidump per site into `TruGuardDumps\`, at most `MaxDumps` files per run (dbghelp is loaded dynamically, so the plugin imports only KERNEL32). Dumps are serialized: while one `MiniDumpWriteDump` runs, a second one is skipped with a log line instead of blocking.
- **Fault ring:** the last 16 faults (tick, offset, code, access, address, thread) are kept in a seqlock-protected ring and appended to a fatal record as `previous faults (n, newest first)`, so a chain of handled faults before the crash is visible.
- **Handled note:** about 2 s after the last hit at a site the worker checks whether the unhandled-exception filter followed; if not, it logs `TRUGUARD_HANDLED` once per site. This is what turns the noise measurement into a concrete "handled by the game" list.
- **On-demand dump:** `TruGuardDump(reason)` writes a full-memory minidump plus a snapshot of all other threads (EIP/ESP/EBP as module+offset), without waiting for a fault. It works while the render loop is hung (TruLink runs on its own thread) and ignores `Dump`/`MaxDumps`.
- **Resume safety:** a skip is only taken when `eip+skip` is executable according to `VirtualQuery`; `MaxResumesPerSecond` (default 20, 0 = off) stops a fault loop (`TRUGUARD_RESUME_STOP`).
- **Ignore list:** `[Ignore] SiteN=0x…` (up to 32) suppresses the first-chance line, the first-chance record and the handled note for that site (counters keep running); a fatal record and its dump are still written, and `[Sites]` rules still apply.
- **GuardRails (0.4):** the worker samples `[GameTracker+0xa64]` (current box), `[GameTracker+0xc94]` (attach box) and `[agent+0x3ed]` (condition 528) every 200 ms into a 32-entry context ring; a fatal record lists the last samples. `TruGuardEvent(id,a,b,c)` stores a 32-entry plugin event ring; `TruGuardRail(id,value)` returns `1` (allow) or `0` (block) according to `[Rail.*]`, with `Action=off|log|block` and `Limit`. The plugin only reports/decides; the caller owns the game-side safe action. `TRUGUARD_RAIL` logs `state572_attach`, `point_on_box`, `slot8_box`, or the passive `attach_pending` (box set, attach box still 0). `TruGuardContext` returns the latest sample.
- Machine-readable marker lines in `TruGuard.log` (grep-friendly, also with `LogLevel=1`):
  `TRUGUARD_FAULT site=tru+0x. code=. access=. addr=. hits=.`,
  `TRUGUARD_DETAIL . state=firstchance|resumed|unhandled dump=<file>|none|earlier|failed`,
  `TRUGUARD_RESUME site=. skip=. to=.`,
  `TRUGUARD_PREV count=. newest=.`, `TRUGUARD_HANDLED site=. hits=.`,
  `TRUGUARD_DUMP kind=manual path=<file>`, `TRUGUARD_RESUME_STOP .`,
  `TRUGUARD_RAIL id=. value=. action=log|block hits=.`, `TRUGUARD_CONTEXT t=. gt=. box=. attach=. agent528=.`,
  and (at `LogLevel>=2`) `TRUGUARD_EVENT name=. a=. b=. c=.`.
  `Invoke-TruTestRun.ps1` reads all of them, treats `state=unhandled` as a crash even in a plain run without a
  debugger and lists `HANDLED` / `PREV` / `DUMP` / `RESUME_STOP` as their own rows in the TruGuard table.
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
`FirstChance`, `FirstChanceDetail` (full record at first chance, default 1), `FirstChanceDump` (also dump at first
chance, default 0 - slow), `HandledNote` (write `TRUGUARD_HANDLED` for sites the game handled, default 1),
`MaxResumesPerSecond` (rate cap, default 20, 0 = off), `LogStack`, `LogContext`. `[Sites]` takes
`SiteN=<offset>,<skip>[,<eax>[,<ecx>[,<limit>]]]` with the `tru.exe` offset in hex, `-1` = leave the register alone,
`skip < 0` = decode the instruction length, `skip = 0` = never continue at this site.

`[Ignore]` takes up to 32 entries `SiteN=0x<offset>` (same offset as in `[Sites]`); listed sites are counted but their
first-chance line/record and handled note are not written.

`[GuardRails]` takes `Enabled` (default 1; 0 turns sampling, events and rail calls off), `Events` (default 1) and
`AttachPending` (default 1). `[Rail.<name>]` takes `Action=off|log|block` and `Limit` (max `TRUGUARD_RAIL` lines; the
return value is not limited). Shipped rails: `state572_attach`, `point_on_box`, `slot8_box`.

The shipped INI keeps both documented NULL-native sites commented out:

```
; Site1=0x17dea3,3,-1,-1,8
; Site2=0x17deae,2,0,-1,8
```

## Reading it from the other tools

Exports: `TruGuardVersion`, `TruGuardCount` (first-chance exceptions), `TruGuardDistinct` (sites),
`TruGuardDump(reason)` (on-demand dump, returns 1 on success), `TruGuardMode`, `TruGuardLast`, `TruGuardStatus`,
`TruGuardSetMode`, `TruGuardRail(id,value)` (1 allow / 0 block), `TruGuardEvent(id,a,b,c)` (breadcrumb),
`TruGuardContext(out,size)` (latest passive sample).

TruMenu: `guard.status`, `guard.count`, `guard.last`, `guard.mode` (0..2), `guard.overlay` (top-right corner),
`guard.dump` (action; optional argument = reason). TruLink reaches the same items with `menu <id>`,
e.g. `menu guard.status`, `menu guard.mode 2`, `menu guard.dump stuck` - also usable while the game is hung.

## GuardRails (0.4, passive)

0.4 adds passive context samples (GameTracker, current/attach box, `agent+0x3ed`), the plugin event/rail API and
the `[GuardRails]`/`[Rail.*]` policy. It still patches no game code: `TruGuardEvent` only records breadcrumbs,
`TruGuardRail(id, value)` only returns `log`/`block`; the caller (TruRockVein, TruShadowPower) performs the safe
action. The existing consumer guards at `tru+0x32ba40`, vtable `0x85521c` and the selector/chart probes stay
owned by RockVein and are not patched twice. The open wall-run rail is State 572 (`tru+0x36dcd0`, check
`[GameTracker+0xc94]`); a guard-owned stub for it is designed but **not built**. Full design, rail catalogue,
INI/API sketch and test plan: `docs/GuardRails.md`.

## Build, install, remove

- Build: `scripts\windows\Build-TruAsi.ps1 -Name TruGuard` -> `work\asi\TruGuard.asi` + `TruGuard.ini`.
- Install: `scripts\windows\Set-TruGuard.ps1 -Install` (game closed). Remove: `-Remove` (only our own files; log and
  dumps stay).
- Log: `TruGuard.log`, dumps: `TruGuardDumps\TruGuard_<run>_site<offset>_<n>.dmp` (fault) and
  `TruGuard_<run>_manual<nn>_<reason>.dmp` (on demand) next to `tru.exe`. `Invoke-TruTestRun.ps1` collects both into
  the run folder.

## Limits

- Minidumps are written from inside the exception handler; dbghelp can block briefly. Turn dumps off (`Dump=0`) if a
  run must not stall. A helper thread for the dump is not built. `guard.dump` blocks its caller (the TruLink thread)
  for the duration of the (full-memory) dump and deliberately ignores `Dump`/`MaxDumps`.
- The thread snapshot suspends each other thread only briefly for `GetThreadContext`; it is best-effort, not a frozen
  process image. A thread holding the log spinlock can delay a line (the timeout writes anyway).
- Under a debugger Windows may skip the unhandled-exception filter (a session that stops at the exception never
  returns to it); then only the first-chance lines and the (default) first-chance record exist, no dump.
- Re-arming the filter means a later, unrelated crash in another module is also reported by TruGuard (one extra log
  line); the game's own filter is not chained because its `GetExceptionInformation` context is no longer valid.
- The stack walk follows the EBP chain only (functions without a frame pointer are missing); raw stack words help.
- The known-site names are a snapshot from the documentation, not symbols.
- `SkipUnknown=1` guesses; it can turn a clean crash into a wrong value. Keep it off except for hunting more sites.
- `TRUGUARD_HANDLED` is a 2 s heuristic: a very late handled fault can look handled and still become fatal later
  (both lines then appear). `[Ignore]` only hides the first chance, never a fatal record.
- The resume rate cap is a 1 s window, not a total budget; the per-site limit still applies on top.
- Context samples are snapshots every 200 ms, not a transaction log: a very short `box`/`attach` window can be
  missed, and the pointers are read with `VirtualQuery`/`memcpy` (stale but safe). They are for the record, not for
  control flow.
- `TruGuardRail` never changes game state. If the caller ignores the return value, nothing is blocked; a guard-owned
  State 572 stub is designed (`docs/GuardRails.md`) but not part of 0.4.
- Byte-level details (skip length, register values) for the documented sites can only be confirmed in-game.
