# TruXenia - Xbox values from Xenia (menu + link)

TruXenia is the Xbox-side counterpart of TruMenu's diagnostics: while *Tomb Raider: Underworld* with the title update
runs in the Xenia emulator, it shows enemy and Lara values, writes a hit log in the same layout as TruMenu's
`combo.trace` on PC, offers a small command link for scripts (like TruLink on PC) and keeps a library of named Xbox
saves. The goal is to measure the same fight on both sides and compare it line by line (TODO N18 "combat like the
Xbox"). No plugin runs inside Xenia; the Xbox game behaves as it should.

## Safety

- **Read only by default.** Xenia is opened with `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION` and only
  `ReadProcessMemory` is used - no debugger, no suspend (a debugger listing of all memory regions froze Xenia once).
- **Proof words first.** Every TU address in `docs/data/xenia_tu_combat_addresses.json` carries TU instruction words
  that prove it; TruXenia compares all of them (39) with the guest memory and refuses to read on a mismatch.
- **Unproven fields are `?`.** Fields marked `"proven": false` (target slot, coordinator, instance position) are shown
  as `?`; the check box "show unproven fields" shows them marked with `~`. Lara's LP is not mapped yet (`?`).
- **Writes are locked.** `set <inst> lp|stamina <value>` exists, but only with `--allow-write` and an explicit unlock
  (GUI button with confirmation, or the link command `unlock yes`). Data words only, never code (Xenia translates the
  code ahead of time); every write is read back. Security software may flag `WriteProcessMemory`
  into another process - that is expected; nothing is hidden or obfuscated.
- **Saves:** "restore" works only while `xenia_canary.exe` is closed and backs up the current save folder first.

## Start

From the repository root (`../bin/pyt` = the project's Python runner; any Python 3 with tkinter works):

```
../bin/pyt -t 60 tools/truxenia.py --check        # Xenia running: proof words only
../bin/pyt -t 60 tools/truxenia.py --once         # one snapshot to the console
../bin/pyt -t 0  tools/truxenia.py                # window + link on 127.0.0.1:47011
../bin/pyt -t 0  tools/truxenia.py --nogui        # link only
../bin/pyt -t 120 tools/truxenia.py --selftest    # offline: simulated memory, hit log, link, saves (dry run)
```

Options: `--port N`, `--log PATH`, `--hitlog PATH`, `--unproven`, `--allow-write`, `--lang de|en`, `--verbose`,
`--debug`, `--trace`. Logs go to `<workspace>/logs/truxenia/` (`truxenia_<time>.log`, `hits_<time>.log`). Settings are
not saved (language and options only for the session).

## Window (DE / EN, flag button)

| Page | Content |
|---|---|
| Gegner / Enemies | per enemy: name + object id, LP, stamina, state layer 0 / 1, requested state, target, distance, `Ko` (attack slot, `?` until the TU coordinator is mapped); refresh every 100 ms |
| Lara | chart records of machine 0 / 1 (combo steps), shadow meter value + flags (active), world time scale (slow motion), doppelganger flag, position (unproven), LP (`?`) |
| Log / Link | recording on / off (TSV of all values), the hit lines, the link address, the write lock |
| Spielstände / Saves | named saves in `<workspace>/_archiv/xenia-saves/<name>/534307EC` (+ README): store the current saves under a name, restore one (Xenia closed) |

## Hit log

Every LP drop of an enemy gives one line after 0.5 s:

```
17:23:13.494 combo: Lara records 1477>1488 -> viking_thrall_tutorial_dlc2_ 1004 LP 500.0 -> 480.0 (-20.0), stamina 40.0 -> 40.0, state at the hit CombatStepIdle, reaction HitReaction | xbox: dist ?, meter 1000.0 active False, time scale 1.00
```

The text up to `reaction` is the same as TruMenu 0.22.9 `combo.trace` on PC; the PC line names the intro id, the
Xbox line the object id. `records` = Lara's chart records of the last 2 s (combo path), `reaction` = the first state
the enemy enters within 0.5 s after the LP drop. Damage type / sub are not readable on the Xbox side; on PC they come
from TruShadowCombat's `damage types` line.

## Link (for scripts)

`tools/truxenia_cmd.py <command>` sends one line to 127.0.0.1:47011 and prints the answer (also logged):
`status`, `enemies`, `lara`, `hits [n]`, `snapshot <file.json>`, `watch <seconds> <file.tsv>`, `saves`,
`set <inst> lp|stamina <value>` (locked), `quit`.

## Compare a fight

```
../bin/pyt -t 120 tools/combat_log_compare.py --pc-menu <game>/TruMenu.log --pc-combat <game>/TruShadowCombat.log
      --since 14:55:00 --until 15:05:00 --xbox ../logs/truxenia/hits_<time>.log --out ../logs/compare.md
```

One row per hit (n-th PC hit next to the n-th Xbox hit) and a summary per side: hits, mean / min / max damage,
reactions counted, share of knock-down reactions (Fall / Vaulted / Knockdown / Land / RegenerateDeath).

## State (2026-11-09)

Built and tested offline only (`--selftest`: 3 hit lines, link commands, locked `set`, save dry run; the TU image dump
passes the 39 proof words). Not yet run against a live Xenia. TU addresses: ENGINE.md section 13 rows "TU combat
addresses" and "TU brain shift".
