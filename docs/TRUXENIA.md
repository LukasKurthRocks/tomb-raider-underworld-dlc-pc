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
  that prove it; TruXenia compares all of them (91, every JSON section with a `proof` block) with the guest memory
  and refuses to read on a mismatch.
- **Unproven fields are `?`.** Fields marked `"proven": false` (target slot, coordinator `Ko`) are shown as `?`; the
  check box "show unproven fields" shows them marked with `~`. Camera position / look-at / FOV are `?` (not proven).
- **Writes are locked.** `set <inst> lp|stamina <value>` exists, but only with `--allow-write` and an explicit unlock
  (GUI button with confirmation, or the link command `unlock yes`). Data words only, never code (Xenia translates the
  code ahead of time); every write is read back. Security software may flag `WriteProcessMemory`
  into another process - that is expected; nothing is hidden or obfuscated.
- **Xenia's own options are not touched.** TruXenia never edits the Xenia config (shader dump / store options are
  only mentioned below as a possible second source).
- **Saves:** "restore" works only while `xenia_canary.exe` is closed and backs up the current save folder first.

## Start

From the repository root (`../bin/pyt` = the project's Python runner; any Python 3 with tkinter works):

```
../bin/pyt -t 60 tools/truxenia.py --check        # Xenia running: proof words only
../bin/pyt -t 60 tools/truxenia.py --once         # one snapshot to the console
../bin/pyt -t 0  tools/truxenia.py                # window + link on 127.0.0.1:47011
../bin/pyt -t 0  tools/truxenia.py --nogui        # link only
../bin/pyt -t 120 tools/truxenia.py --selftest    # offline: simulated memory, hit log, link, saves (dry run)
../bin/pyt -t 60 tools/truxenia.py --dumpfile work/xenia_dump/tu_image_82000000.bin --check   # proof words vs a dump
```

Options: `--port N`, `--log PATH`, `--hitlog PATH`, `--unproven`, `--allow-write`, `--lang de|en`, `--verbose`,
`--debug`, `--trace`. Logs go to `<workspace>/logs/truxenia/` (`truxenia_<time>.log`, `hits_<time>.log`). Settings are
not saved (language and options only for the session).

## Window (DE / EN, flag button)

| Page | Content |
|---|---|
| Gegner / Enemies | real enemies only (brain test, below): kind symbol in its colour, name + object id, LP (`*` = LP note, e.g. RegenerateDeath), stamina, state layer 0 / 1, requested state, target, distance, `Ko` (`?`), Ko handle, attack (MeleeAttack record + anim ids), flight (running or last); refresh every 100 ms |
| Objekte / Objects | every instance of the instance list: kind, name, object id, enemy yes / no, distance; one coloured check box per kind = legend and filter |
| Lara | chart record **indices** of machine 0 / 1 and their state id lists, LP (max), position, shadow meter value + flags (active), world time scale, the 7 time-scale request slots and the winning slot per scale, ramp targets player / world, doppelganger flag, camera mode / flags (position / FOV `?`) |
| Geladene Daten / Loaded data | object table (loaded objects, state counts; read once per second) and the plan for units / sections / shaders (below) |
| Log / Link | recording on / off (TSV of all values), the hit lines, the link address, the write lock |
| Spielstände / Saves | named saves in `<workspace>/_archiv/xenia-saves/<name>/534307EC` (+ README): store the current saves under a name, restore one (Xenia closed) |

### Kinds (symbol, colour, filter)

The kind comes from the object name; nothing is guessed - a name that matches no rule is "other" (Sonstiges).

| Kind | Rule (object name, lower case) |
|---|---|
| Lara | the player instance of the game tracker |
| Chunkdoll (pieces) | contains `chunkdoll` |
| Generator | contains `generator` |
| Goo (drips, balls, spawners) | contains `goo` |
| Natla / scripted actor | contains `natla` |
| Yeti | enemy (brain test) and `yeti` |
| Tutorial thrall | enemy and `tutorial` and `thrall` |
| Thrall | enemy and `thrall` |
| Pickup / interactable | contains pickup, medipack, health, ammo, treasure, reward, lever, switch, button, door, chest or relic |
| Other | everything else |

**Brain test (real enemies):** TU enemy init 0x822da9ac: `[inst+0x50]` word 0 == 0xdaf00018 and byte +0x18 > 0 ->
the game allocates a brain (PC 0x63c1b5 the same test). Only instances that pass are enemies; the live log of
09.11. 17:37 (before this test) had 883 "hits" with LP values like 0x3f800000 from non-enemy objects.

## Hit log

Every LP drop of an enemy gives one line after 0.5 s:

```
18:26:19.930 combo: Lara records 1477>1488 -> viking_thrall_tutorial_dlc2_ 1004 LP 500.0 -> 480.0 (-20.0), stamina 40.0 -> 40.0, state at the hit CombatStepIdle, reaction Hit | xbox: dist 50, meter 1000.0 active False, time scale 1.00 | xbox+: kind tutorial, attack -, fly -, last flight -, Lara LP 1000.0, Lara states [], time requests -, world ramp 1.00
```

The text up to `reaction` is the same as TruMenu 0.22.9 `combo.trace` on PC; the PC line names the intro id, the
Xbox line the object id. `records` = Lara's chart record indices of the last 2 s (combo path), `reaction` = the first
state the enemy enters within 0.5 s after the LP drop. Damage type / sub are not readable on the Xbox side; on PC they
come from TruShadowCombat's `damage types` line. The `| xbox:` part is unchanged; new values come after `| xbox+:`:

| Field | Meaning | Source |
|---|---|---|
| kind | kind of the enemy (table above) | object name + brain test |
| attack | `rec <record> anim t/a t/a t/a` while the enemy is in MeleeAttack: the attack record and its 3 anim refs (type / anim) - tells e.g. the spit attack from a strike | data = (brain+0x1254 + (slot + 2*layer)*0x19c + 0x1f) & ~0xf, slot = [brain+0x18d4+4*layer], record = [data+0x50], self-check [data+0x198] == state object (TU 0x8232fb48); anim refs record+0x78 (ENGINE.md 13.5) |
| fly / last flight | horizontal way of the enemy while in Fall / Splat / Land: `320 u in 0.6 s (Fall>Land)` | instance position +0x20 (TU 0x8238d384) |
| Lara LP | Lara's health | player tracker +0x628 (max +0x630; TU 0x823e8068) |
| Lara states | state ids of Lara's current chart record (machine 0) | record +0x18 list, +0xc count |
| time requests | occupied request slots `slot:player/world` | meter +0x40, 7 x {f32 player, f32 world} |
| world ramp | world time-scale ramp target | 0x827754cc |

**Reaction `finisher-in-RegenerateDeath`:** RegenerateDeath Enter (TU 0x8235dff8, state object 0x8277a7b8) sets the
enemy's LP to the maximum of its current tune. A hit while the enemy is in RegenerateDeath therefore removes that
restored maximum - it is the finisher, not normal damage. `combat_log_compare.py` counts these separately.

Since 09.11.2026 `records` are indices: machine+0x520 holds a **record pointer**; its index is its position in the
record array `[[machine+4]+0xc]` (TU machine reset 0x82482808). Earlier logs show the raw pointer.

### Recording (TSV)

The PC-compatible columns stay first and unchanged: `host_time inst obj_id obj_name lp stamina state0 state1 req target
dist lara_rec0 lara_rec1 meter active time_scale`. Appended: `kind pos_x pos_y pos_z speed fly last_flight attack
ko_handle lp_note lara_lp lara_states lara_pos ts_requests ts_selected ramp_player ramp_world cam_mode cam_flags
aim_cm1fc aim_bits aim_t0_flags aim_t0_target` (the last four since 2026-11-10, section "Lock-on path").
`ts_requests` / `ts_selected` have the same text as TruMenu 0.22.11's `pc_ts_requests` / `pc_ts_selected`
(`0:1.20/0.30 4:0.02/1.00`, `P0.02(s4) W1.00(s4)`), so PC and Xbox can be matched by column name
(`tools/fight_trace_compare.py` reads only the shared first 16 columns so far).

## Time-scale requests (shadow-power mode)

The meter object has 7 request slots at +0x40 (stride 8: f32 player scale, f32 world scale). The selector
(TU 0x823d7520) walks from slot 6 down to slot 0 - the highest slot with a value > 0.0 wins (compare with the constant
0.0 at 0x8207d538, `ble` skips; so 0 and TruMenu's "empty = -1" are both empty), separately for player and world - and
writes the ramp targets 0x827754ac (player) / 0x827754cc (world). Slot writers (Befund X23): 0 power
start / stop, 1 meter target, 2 strike look, 3 adrenaline look, 4 player event switch / condition 2401, 5 state 1018,
6 script natives 23 / 24. The Lara page shows all 7 slots, the winner per scale and both ramp targets.

## Link (for scripts)

`tools/truxenia_cmd.py <command>` sends one line to 127.0.0.1:47011 and prints the answer (also logged):
`status`, `enemies`, `lara`, `objects [kind]`, `loaded`, `hits [n]`, `snapshot <file.json>`,
`watch <seconds> <file.tsv>`, `saves`, `set <inst> lp|stamina <value>` (locked), `quit`.

## Compare a fight

```
../bin/pyt -t 120 tools/combat_log_compare.py --pc-menu <game>/TruMenu.log --pc-combat <game>/TruShadowCombat.log
      --since 14:55:00 --until 15:05:00 --xbox ../logs/truxenia/hits_<time>.log --out ../logs/compare.md
```

One row per hit (n-th PC hit next to the n-th Xbox hit; the `xbox+` part in its own last column) and a summary per
side: hits, mean / min / max damage, reactions counted, share of knock-down reactions (Fall / Vaulted / Knockdown /
Land / RegenerateDeath), finishers in RegenerateDeath (kept out of the damage numbers), hits per kind.

## Loaded data - proven part and plan

Proven and shown: the **object table** 0x82979280 (0xcc entries of 0x24 bytes; +8 object, u16 +0xc object id, u16
+0xe state, 2 = loaded; TU 0x8214684c, PC twin 0xdb7400, ENGINE.md section 2).

Not proven yet (shown as plan text, no values):

| Wanted | PC side (known) | Missing on the Xbox side |
|---|---|---|
| script units / unit list | TRScriptUnitManager 0xa13eec | TU twin of the manager and its unit list (find the TU function by the PC call pattern, then proof words) |
| DRMs / sections | section database (not mapped on PC either) | section DB address + entry layout on both sides |
| shaders / materials | - | material / shader library list. Second source without memory reads: Xenia's own shader cache (`store_shaders`) or `dump_shaders` - Xenia options, read only here, never changed by TruXenia |

### Camera

Shown: manager 0x82efc780 (TU 0x822a9a6c = PC flag reader 0x5e5e8e), mode +0x54, flags +0x7c (ENGINE.md section 22).
`?` until proven on the Xbox: position, look-at, distance, FOV. PC addresses for the port: manager 0xe804f0, current
camera [mgr+0x44], gameplay camera 0xe83860 (focus +0x1cc), FOV camera +0xb0 (vertical radians), camera matrix
0xe804a0, getters 0x5e7850 / 0x5e7870 / 0x5e78a0 / 0x5e78d0. Next step: the TU twins of these getters.

### Attack coordinator (`Ko`)

Proven: MeleeAttack Enter passes brain+0x2fc4 (a requester with the handle {instance +4, stamp +8}) to TU 0x823551b0,
which checks the handle and the target's slot manager +0xf78. TruXenia logs the handle target (`ko_handle`); what the
coordinator grants (slot, order) is still open - `Ko` stays `?`.

### Lock-on path (aiming, 2026-11-10)

For the K-5 comparison (PC: no lock target while LT is held; PC side = TruMenu 0.22.15 `aim.trace` / `TruAim.log`,
ENGINE.md row "Lock-on path"). Address-file section `aim`, 9 proof words: CM = player tracker +0x504, **CM+0x1fc**
shown as bits 9 (soft lock, TU 0x823de858 = PC 0x71ec50) / 10 (lock, TU 0x823de9f0 = PC 0x71edf0) / 11 / 18 / 19 /
20 / 21; **targeter 0** = `[[0x829ca648]+0]`, flags +8, target = node +0x90 -> handle {instance, stamp} (stamp checked
against instance +0x44; TU getter 0x82404568 = PC 0x719f00). Lara page line "Zielen (Lock)", link `lara`, the four
`aim_*` TSV columns. Read only. Not read on the Xbox (offsets not proven there): the pad word, the aim timers
(TU player fields are shifted by +4 around +0x50f / +0x540), the candidate lists.

## State (2026-11-09)

- First live session 09.11. 17:35-18:10 (hit log, values readable, proof words passed).
- Stage 1b (09.11. evening, offline): record indices, Lara LP / states, enemy positions + flight, MeleeAttack record,
  brain test, kinds + filter, RegenerateDeath LP note, time-scale request slots, object table. `--selftest` passes
  (4 hit lines incl. the RegenerateDeath finisher, link commands, locked `set`, save dry run); both TU image dumps
  pass the 91 proof words. Not yet run live.
- 2026-11-10 (offline): lock-on values (section "Lock-on path"); `--selftest` passes with the new aim line, the TU
  image dump passes 103 proof words (0 mismatches). Not yet run live.
- Open: `Ko` meaning, camera position / FOV, units / sections / shaders, Xenia function-trace reader (stage 2).
- TU addresses: ENGINE.md section 13 rows "TU combat addresses", "TU brain shift", "TU TruXenia stage 1b".
