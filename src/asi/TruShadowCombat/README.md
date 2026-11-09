# TruShadowCombat.asi - DLC 2 combat of the title update (0.6.8)

0.6.8 (2026-11-09, **offline, not yet seen in game**; TODO N18 K-1b, main workspace
`docs\Befund-K1b-Entscheidung-0911.md`, ENGINE.md 13): build `work\asi\combat068`, byte pre-checks
`work\asi\combat068\precheck_068.txt` (7 checks, 0 mismatches against the installed tru.exe).
* **Impulse gate** (`[Hit] TranslateImpulseGate`, live, default **1**; TU 0x823e1870..0x823e1884): Lara's contact-hit
  sender tru+0x319050 (CombatManager in edi, hit instance in ebx, attack data A = `[edi+0xc4]`) sends the hit message
  0x11c and then, when A+0x10 > 0 and no special body was hit, the impulse message 0x91 (tru+0x3192da..+0x319394). The
  title update skips that impulse when `[[inst+0x10]]+4` has bit 0x400000 (enemies with a brain, the thrall too) and
  continues at 0x823e1934 (= PC tru+0x319398); retail and the PC always send it, so on the PC the impulse receiver
  tru+0x224c60 throws the thrall into Fall on every punch. Jump at tru+0x3192da (5 bytes `lea edx, [esp+0x20]; push
  edx`) -> `ImpulseGateStub`; flag set and switch on -> tru+0x319398, else the two moved instructions and back to
  tru+0x3192df (switch 0 = PC). Other impulse senders (weapons, surroundings) are not touched. Side effect: Lara's melee
  no longer reaches the 0.6.1 lethal-impulse path in tru+0x224c60; death comes through 0x11c + the death check, as in
  the TU.
* **Log** (`[Hit] Log`, same cap `[Hit] MaxLines`): per skipped impulse `0.6.8 impulse gate: <enemy> type <A+0xc> force
  A+0x10 <f>, [[inst+0x10]]+4 0x... -> impulse 0x91 not sent (TU 0x823e1870, #<n>, ...)`. Load line `0.6.8 impulse
  gate on (...)`.
* **Hit line label fixed:** `0.6.7 hit:` now prints the subtype msg+0x64 as `sub` (2 for Lara's contact hit, builder
  argument 17 at tru+0x31914b) and msg+0x54 (argument 16, fixed -1 at tru+0x31914d) as `msg+0x54`; 0.6.7 printed
  msg+0x54 under `sub`.
* **Test (hall02, tutorial thrall):** single punches during the thrall's attack with the switch 1 / 0: expected with 1
  `impulse gate` lines, Hit instead of Fall, Fall only for types 21 / 23..27 (records with s+0x20 = 1).

0.6.7 (2026-11-09, **offline, not yet seen in game**; for the combat tests of TODO N18 "Kampf wie Xbox"): K-1 hit
structures + knockback and K-7 chunkdoll limit (main workspace `docs\Befund-K1-Umfallen-0911.md`, ENGINE.md 13). Build
`work\asi\combat067`, byte pre-checks `work\asi\combat067\precheck_067.txt` (15 checks, 0 mismatches against the
installed tru.exe). Switches in `TruShadowCombat.ini` `[Hit]` (live, read again at most once per second through
`kP1dKeys`) and `[Chunk] Limit8` (start only); all default **1**; a switch at 0 runs the PC code.
* **Hit structures** (`[Hit] Translate`, TU 0x82301dc0 = retail 0x823042a8 + instance): the selector tru+0x2159a0
  (cdecl &s, hit message, D) knows damage types 0..16 only; Lara's DLC 2 melee hits are types 18..27, so the PC gives
  them no structure and the decision tru+0x223410 skips its flag tests (heavy reaction every time). The TU first
  searches the companion's hit records (extension 870 / 932 / 944: `[comp+0x2c]` count, `[comp+0x28]` base, 0xc4 bytes
  each, +0 = type == message +0x50) and takes record +0xc; the D+0x758 redirect (tru+0x213c70) and the return (bit 30
  of +0x14) stay. Placed at the selector calls tru+0x223429 (decision, instance = argument 1) and tru+0x23b157 (hit
  reaction, esi). **Not 1:1:** tru+0x24f338 (inside tru+0x24f230 = TU 0x82329810, which got the instance as a new
  argument) gets the instance only on the path from the knockback tru+0x220650 (return 0x6206e8); its callers
  tru+0x24f5ad / tru+0x25215d keep the PC selector.
* **Knockback** (`[Hit] TranslateKnockback`, TU 0x822f73a8, block 0x822f77e4..0x822f783c + fneg 0x822f7894): the force
  factor is record +0x40 of the same companion record (extension 870: 3 for 18-20 / 22 / 25, 9 for 26, 12 for 21, 18 for
  23 / 24 / 27), 3.0 without a record, instead of the PC's fixed 3.0 / -3.0 (tru+0x220940 `fmul qword [0x8415e8]`,
  tru+0x220971 `fld dword [0x845338]`). **Not translated:** the TU's sideways direction for type 25 with a companion
  (0x822f7558..0x822f75bc) and `brain+0x1254 |= 1` before the second call (0x822f788c, not compared with the PC).
* **Chunkdoll limit** (`[Chunk] Limit8`, start only): `cmp [0xecfc70], 4` at tru+0x296fa8 -> 8 as the TU 0x82376700
  (retail 0x823769e0: 4). The counter has no array behind it (only inc tru+0x2970b8 / dec tru+0x296e5c / this compare).
  Was held back until the lethal-impulse translation (0.6.1 `[Chunk] Translate`) was seen live - 09.11.: 5 impulses
  inside the physics step caught, no crash.
* **Log** (`[Hit] Log`, cap `[Hit] MaxLines` 3000): per hit decision `0.6.7 hit: <enemy> type <t> sub <s> amount <a> -
  structure: companion record (TU) / PC table / no structure (flags +0x14 ...) -> HEAVY (knockback) / light (MoveHit)`,
  per knockback `0.6.7 knockback: <enemy> type <t> force <f> (companion record +0x40 (TU) / 3.0 ...)`. Together with
  TruMenu 0.22.10 `combo.trace 1` this shows per hit what happened. Load line `0.6.7: hit structures on ...`.
* **Test (hall02, tutorial thrall):** with `[Hit] Translate=1` punches (type 18) should show `companion record (TU)` and
  flags 0x10000000; compare heavy / light against `Translate=0` (PC: `no structure -> HEAVY` every time).

0.6.6 (2026-11-08, **offline, not yet seen in game**): N4c - T5 (immediate death in the hit reaction) and P1c (the
Vaulted Enter of the title update with the chain that feeds it); `docs\Befund-P1d-Begleiter-0711.md` section 2 rows T5 /
P1c in the main workspace, disassemblies in `work\combat066_0711`. Build `work\asi\combat066`. All three switches
(`TranslateT5`, `TranslateVaulted`, `TranslateVaultedClock`) default **1**, read again at run time (`P1dReadSwitches`, key table `kP1dKeys`, at most once per second from the hooks); the
hooks are placed at the start whenever their byte checks pass, a switch at 0 runs exactly the PC code.
* **T5** (`[Death] TranslateT5`): the enemy hit reaction tru+0x23ad50 (TU 0x823038d8 = retail 0x82305d40; cdecl inst,
  hit data, a3, a4 -> float amount). The TU inserted at its start (0x8230390c..0x82303a78): with a companion, LP <=
  hit amount (+0x4c) and ShouldRegenerate (TU 0x8235ece8 = H1's companion list + the PC tune list) no -> hit direction
  `(data+0x70 ? data+0x10 : [data+0x30]+0x20) - (data+0x72 ? data+0 : inst+0x20)`, z = 0, normalised (TU 0x8213e838:
  zero unless the squared length is finite and > FLT_MIN), for type 0x19 crossed with (0, 0, -1, 0), then the death
  switch tru+0x241650 kind 7 (the same call as H7 / H8) and return the amount - no damage message, no hit animation.
  The companion is only tested for existence: T5 reads no extension field (needs no data fix). Jump at tru+0x23ad82
  (7 bytes) -> `T5Stub`, back at tru+0x23ad89 or the stub's own epilogue (= tru+0x23b312 without brain+0x2c50 = 0, as
  the TU's 0x8230443c). Log `0.6.6 T5: ... lethal hit type .. -> death switch kind 7 as the TU 0x82303a74, direction ..`.
* **P1c** (`[Death] TranslateVaulted`): the TU-only Vaulted Enter 0x8232b630 (PC tru+0x24fcf0 = retail 0x8232cb18) reads
  a new data field +0x44 = the companion step. Six links, placed together or not at all:
  F retail strike record (PC tru+0x31d5cc -> tru+0x245e40): +0x34 = 0 (TU 0x823e0294);
  E finisher 1013 record (tru+0x31d895, the 0.4 site): +0x3c = 0 in every mode (TU 0x823e0e84; 0.4 did it only in
  doppelganger mode);
  A enemy message handler case 0xbe (tru+0x23b421 -> record copy tru+0x245de0): copy +0x3c = incoming +0x34 (TU
  0x8230743c; the TU strike - `StrikeAt`, `[Strike] Translate` - writes its step there);
  B Vaulted switch from a record (tru+0x223fa2 -> tru+0x20ed80): data +0x44 = record +0x3c (TU 0x823044dc);
  D Vaulted slot 3 copier (tru+0x25a4a2 -> tru+0x24d350): copies +0x44 too (TU 0x8232300c);
  C Enter (tru+0x24fdb9, 5 bytes -> `VaultedAnimStub`): state data +0xb8 = step; companion -> brain+0x2c7c = 0x0fffffff
  (the PC never reads that field); step 0 = the PC's own (retail) animation choice; step != 0 = the companion's step
  table entry `[comp+0x20] + (step - 1) * 0x14` when step <= `[comp+0x24]`, else 0 = no animation (TU 0x8232b3f8).
  **Data guard:** the step table is read only from the FIXED extension layout (record count +0x2c <= 64, step count
  +0x24 <= 64, table set, every entry's anim pair < 0x1000). The installed converted files fail it (0x000f0000) - one
  line `0.6.6: extension data not fixed - install work\extfix_0711 / thrall_extension_fix ...`, the PC choice runs.
  Log `0.6.6 vaulted: ... message 0xbe with step n ...`, `... Vaulted Enter step n: companion step table entry 0x...
  (anim pair {a, b}) ...`.
* **K Vaulted clock** (`[Death] TranslateVaultedClock`, needs the chain): the TU lets an enemy that enters Vaulted run
  5 s without slow motion. Globals `[0x82efb458]` = PC 0xe7f088 (as TruShadowPower's dt translation): +0xd4 = 0xe7f15c
  ms counter, +0x100 = 0xe7f188 time multiplier, +0x118 = 0xe7f1a0 slow motion factor (the PC player update does the
  same at tru+0x3228e9 / +0x3229eb). Enter (TU 0x8232b698, in link C): bit 0x10 of brain+0xc clear -> set, clock = now,
  multiplier /= slow motion. Enemy update tru+0x238d40 (TU 0x822db190): after the brain the multiplier is saved (TU
  brain+0x5084); with bit 0x10: now - clock >= 5000 ms -> bit cleared, else multiplier *= 1 / slow motion; restored at
  the end of the main path (TU 0x822db4e0) - not on the brain+8 bit 0x20000 exit (TU 0x822db364, as the TU). brain+0x5080
  / +0x5084 lie in the block the TU added to the brain (TU +0x5088 = PC +0x5030), so the plugin keeps them: clock word
  per instance in a 64-entry table keyed by instance + serial (+0x44); an entry lives only while its bit runs, ends when
  the update clears the bit, when the serial differs (instance reused - unload / level change), or when the table is full
  (oldest dropped, logged); a missing entry = expired. The save is one slot {instance, value, valid} (updates do not
  nest). Sites: call tru+0x238d6f (-> `ClockStartStub`), tru+0x238e76 (11 bytes -> `ClockExitStub`), epilogue
  tru+0x238efb (7 bytes -> `ClockEndStub`); TruMenu's byte-checked ranges tru+0x238d59..0x238d6e / 0x238ed4..0x238ee2
  are not touched. Not translated: the two script commands 0x822d6844 / 0x822d6880 (set / clear). Log `0.6.6 clock: ...
  Vaulted Enter: brain+0xc bit 0x10 set ...`, `... clock ended after n ms ...`.
* **Not in 0.6.6:** Vaulted slot 10 case 0xbe (next step, TU 0x8232be54), slot 11 0x8232c068, Exit 0x8232b930,
  the strike's step queries 0x165..0x167 (TU 0x82308850), and the rest of RegenerateDeath / Regenerate slot 10 (lying
  animation from companion +0x10 on 0x15 / 0x8a - needs the TU's 2-byte RegenerateDeath state data +8 / +9, which the
  PC state lacks; the subtype-2 sound 0x82399b48 (changed against retail 0x82399e98, 4 arguments) - the PC's call of
  the same pattern in the hit reaction, tru+0x23b0cd -> tru+0x2a5dd0, passes 5; pairing not proven).
* Byte checks: 42 used by the plugin + 6 proof-only (`work\asi\combat066\prechecks_combat066.txt`, generated from the
  source by `work\combat066_0711\facts066.py`; 48, 0 mismatches); earlier lists combat01..combat065 545, 0 mismatches.
  No branch of the patched PC functions lands inside a patched range (`work\combat066_0711\branch_into.py`, 9 ranges).
  Imports unchanged (81, KERNEL32 only), exports unchanged.

New writes into game memory (for the TruGuard author):

| when | address | what |
|---|---|---|
| start, checks passed | 0x63ad82 (`.text`, 7) | `jmp rel32` -> `T5Stub` + 2 `nop` |
| start (all six or none) | 0x71d5cc / 0x63b421 / 0x623fa2 / 0x65a4a2 (`.text`, 5 each) | `call rel32` -> `StrikeRecordHook` / `RecCopyHook` / `VaultSwitchStub` / `VaultCopyStub` (were tru+0x245e40 / +0x245de0 / +0x20ed80 / +0x24d350) |
| start (with them) | 0x64fdb9 (`.text`, 5) | `jmp rel32` -> `VaultedAnimStub` |
| run time | message records (ring tru+0x1c0b10) | +0x34 = 0 (F), +0x3c = 0 (E, the 0.4 hook), +0x3c = step (A) |
| run time | Vaulted switch data / its copy | +0x44 = step (B, D) |
| start (with the chain) | 0x638d6f (`.text`, 5) / 0x638e76 (11) / 0x638efb (7) | `call rel32` -> `ClockStartStub` (was tru+0x2e7710); `jmp rel32` + 6 `nop` -> `ClockExitStub`; `jmp rel32` + 2 `nop` -> `ClockEndStub` |
| run time | Vaulted state data, brain | state data +0xb8 = step; brain+0x2c7c = 0x0fffffff (companion); brain+0xc bit 0x10 set (Vaulted Enter) / cleared (5 s later, enemy update) |
| run time | 0xe7f188 (time multiplier, `.data`) | Vaulted Enter: /= [0xe7f1a0]; enemy update: saved, *= 1 / [0xe7f1a0] while the clock runs, restored at the end (every enemy update while the clock part is on) |
| run time | - | game function calls on the game thread: death switch tru+0x241650 (T5), ShouldRegenerate tru+0x27f040, record builders tru+0x245e40 / +0x245de0, SwitchToVaulted tru+0x20ed80, copy tru+0x24d350 |

| # | TO TEST 0.6.6 (hall02 tutorial thralls; **extension test tree `work\extfix_0711\testtree\mods` installed** for P1c) | expected |
|---|---|---|
| 1 | load, read `TruShadowCombat.log` once | `TruShadowCombat 0.6.6 (`, `0.6.6: T5 on (...), P1c Vaulted chain on (...), clock on (...)`, no "does not match" |
| 2 | kill a tutorial thrall with a non-regenerating lethal hit (finisher 1013, a type outside the regenerate lists) while it stands | `0.6.6 T5: ... lethal hit type .. with companion, ShouldRegenerate no -> death switch kind 7 ...`; the thrall dies at once (no hit animation) |
| 3 | lethal hit with a regenerating type (combo 18..24, heavy) | no T5 line; `0.6.3 death: ... notification 33` / RegenerateDeath as in 0.6.5 |
| 4 | `[Strike] Translate=1`, shadow strike on a thrall | `0.6.6 vaulted: ... message 0xbe with step n`, `... Vaulted Enter step n: companion step table entry ...`; the thrall plays the step animation of its extension. With the old (unfixed) files: one `extension data not fixed` line, PC animation |
| 5 | main game finisher / strike (no companion) | no `0.6.6 vaulted` step lines (step 0 = PC choice), finishers as before |
| 6 | an enemy enters Vaulted (finisher / strike), shadow slow motion on | `0.6.6 clock: ... Vaulted Enter: brain+0xc bit 0x10 set ... time multiplier a -> b`; the enemy moves at normal speed for 5 s, then `... clock ended after ~5000 ms`; without slow motion (factor 1) nothing visible |
| 7 | trouble | `[Death] TranslateVaultedClock=0`, `TranslateT5=0` / `TranslateVaulted=0` (live); send the log |

0.6.5 (2026-11-07, **offline, not yet seen in game**): P1d - the thrall's companion instance (T4) and the title-update
code that hangs on it (`docs\Befund-P1d-Begleiter-0711.md` section 3 in the main workspace; T1 / T2 of
`Befund-Thrall-Felder-0611.md`, T-M3 of `Befund-P1b-MeleeAttack-0711.md`, notifications 34 / 38 of
`Befund-Hall02-Tutorial-Stufe2-0711.md`). Build `work\asi\combat065`. Every part default **1**, every switch read again
at run time (at most once per second, from the hooks); the hooks are placed at the start whenever their byte checks
pass, a switch at 0 runs exactly the PC code.
* **H0 companion** (`[Companion] Translate` / `Log`): the TU builds a companion instance in the enemy init (TU-only
  0x822da800): the first child of the thrall object's id list `[[inst+0x10]+0x2c]` whose object table entry (0xdb7400,
  state 2) has data `[o+0x5c]` of type 0x3d (u16 +2) and `[o+0x60]` != 0 - 870 (viking / tutorial viking), 932 (yeti),
  944 (armoured yeti); 1007 is type 0x3b (chunkdoll), not it. Its readers (0x822da918) only ask "is it there" and take
  its data (= `[o+0x5c]`, PC tru+0x1ba84c). The PC loads these objects already but makes no instance. The plugin answers
  the readers' question from the object table on every use and keeps nothing. `[o+0x60]` is the object's name pointer
  on the PC (tru+0x1bf0fb) - set for every loaded object (the open point of the finding). Log: one line per thrall
  instance the first time a hook sees it, `0.6.5 companion: 0x... obj 1004 viking_thrall_tutorial_dlc2_ serial ...
  (first seen: MeleeAttack slot 13) - companion object 870 viking_thrall_dlc2_extension, data 0x... (type 0x3d), byte
  +0x18 = 0, regeneration list count 1, entry 0 {2, 0, 0}; children: ...` or `- none: <reason>; children: <id reason,
  ..>` (max 400).
* **H6 notification 34** (`[Death] TranslateNotify34`): RegenerateDeath slot 12 (Exit, vtable 0x85b104 = tru+0x27eeb0,
  retail 0x8235ea38) = TU 0x8235e338 = the same body + `PlayNotification(34)` - every time an enemy leaves
  RegenerateDeath. No companion needed. hall02: closes the finisher hint `hint_17` (23101 f3, f4).
* **H7 / H8 finisher 38** (`[Death] TranslateNotify38`): the TU-new first block of RegenerateDeath slot 10 (vtable
  0x85b0fc = tru+0x282490, TU 0x8235e3a8) and Regenerate slot 10 (0x85b15c = tru+0x282680, TU 0x8235e998): hit message
  0x11c with data, a companion and type 16 (or type 1 subtype 1) -> death switch kind 7 (tru+0x241650 with the vector
  (0, 0, 1, 0) of TU 0x8207db00, the same switch as 0.6.1) and `PlayNotification(38)`, return 1; else the PC handler.
* **H1 regeneration list** (`[Death] TranslateRegenList`): ShouldRegenerate (TU 0x8235ece8, PC tru+0x27f040 = retail)
  asks the companion's list (+0x40 / +0x44, entries {type -1 any, subtype 0 any, flag bit 0}; the three extensions: 1
  entry {2 Heavy, 0, 0}) after the same preconditions and before the tune list. The three calls tru+0x2203e4 (death
  check), tru+0x2824b9 (RegenerateDeath slot 10), tru+0x2826d3 (Regenerate slot 10) go to the plugin; the function is
  not patched (TruMenu byte-checks its head and calls it).
* **H3 / H4 / H3b T2 Land** (`[Death] TranslateLand`): Land slot 9 (tru+0x25afe0, TU 0x82328aa0) with LP <= 0 and a
  companion whose data byte +0x18 is 0 -> notification 33 (only with `[Death] TranslateNotify33=1`) and RegenerateDeath
  with the 2-byte data {([state data+0x30] >> 1) & 1, 1} (TU 0x8230c050 = PC tru+0x23d4a0 with 0x8afa4c, the helper of
  the Getup branch beside it; the PC's RegenerateDeath copies / reads no transition data), else LandDeath as before.
  Jump at tru+0x25b181. Land slot 13 (vtable 0x858c90 = tru+0x241d30, TU-only 0x82329060): with a companion
  RegenerateDeath and Death may interrupt Land (6; PC -1 - the state machine tru+0x271080 would refuse T2's switch, so
  T2 is placed only with it). Land exception of T3 (TU 0x822f6654, in the 0.6.3 hook): a lethal regenerate hit while
  in Land sends 33 but switches nothing (return 0) - the landing decides.
* **H5 T-M3** (`[Melee] TranslateInterrupt`): MeleeAttack slot 13 (vtable 0x859160 = tru+0x242f40, TU 0x82330830):
  where the PC answers -1, Vaulted (0x8ae8bc) and - with a companion - RegenerateDeath may interrupt too, answer
  tru+0x270400(next) = `[next+4]` (read: `next ? [next+4] : 0`).
* **33 + 34 + 38 belong together**: the shipped .ini has all three at 1. 33 alone (0.6.3 / 0.6.4) opens the finisher hint
  and nothing closes it (hall02 run 1, 07.11.); with 34 it closes when the thrall stands up or dies, with 38 at once on
  the finisher. Keep `TranslateNotify33=0` in the game .ini only while 34 / 38 are off.
* **Not in this build:** T5 (TU 0x823038d8: companion + lethal + not regenerating -> death kind 7 at once), the rest of
  RegenerateDeath / Regenerate slot 10 (0x15 / 0x8a with companion: lying animation from data +0x10; the sound
  0x82399b48; Regenerate 0x15 only without data), P1c (Vaulted Enter 0x8232b630) - P1c / T5 read the extensions'
  stage table +0x20 / +0x24 and the 0xc4 records +0x28 / +0x2c, which the converter got wrong (count 0x000f0000 instead
  of 15): data fix of 870 / 932 / 944 first.
* Byte checks: 36 used by the plugin + 9 proof-only (`work\asi\combat065\prechecks_combat065.txt`, generated from the
  source by `work\combat065_0711\facts065.py`; 45, 0 mismatches); earlier lists combat01..combat064 500, 0 mismatches.
  Imports unchanged (81, KERNEL32 only), exports unchanged.

New writes into game memory (for the TruGuard author):

| when | address | what |
|---|---|---|
| start, checks passed | 0x85b104 (`.rdata`, 4 bytes) | RegenerateDeath vtable slot 12: 0x67eeb0 -> `RdExitHook` |
| start | 0x85b0fc (`.rdata`, 4) | RegenerateDeath slot 10: 0x682490 -> `RdMsgHook` |
| start | 0x85b15c (`.rdata`, 4) | Regenerate slot 10: 0x682680 -> `RgMsgHook` |
| start | 0x858c90 (`.rdata`, 4) | Land slot 13: 0x641d30 -> `LandIntHook` |
| start | 0x859160 (`.rdata`, 4) | MeleeAttack slot 13: 0x642f40 -> `MeleeIntHook` |
| start | 0x6203e4 / 0x6824b9 / 0x6826d3 (`.text`, 5 each) | `call rel32` 0x67f040 -> `RegenListHook` (all three or none) |
| start | 0x65b181 (`.text`, 6) | `jmp rel32` -> `LandStub` + `nop` (only with the Land slot 13 entry) |
| run time | - | no data writes; calls of game functions on the game thread: PlayNotification tru+0x37a540 (34 / 38 / 33), death switch tru+0x241650 (kind 7), state switch tru+0x23d4a0 (RegenerateDeath) |

All `.rdata` / `.text` writes through `VirtualProtect` (old protection restored) + `FlushInstructionCache`, once at
the start. Note for TruMenu: its ai.kill check list holds `{0x006203e4, "e857ec0500 ..."}` - it runs when TruMenu
loads (before this plugin, alphabetical), so it still passes; a later re-check would see the H1 call.

| # | TO TEST 0.6.5 (hall02 tutorial thralls, TruMenu `[Debug] EnemyStateLog=1`, game .ini `[Death]` 33 / 34 / 38 = 1) | expected |
|---|---|---|
| 1 | load, read `TruShadowCombat.log` once | `TruShadowCombat 0.6.5 (`, `0.6.5 companion: lookup ready ...`, `0.6.5: H6 notification 34 on, H7 / H8 finisher 38 on / on, H1 regeneration list on (3 of 3 calls), H4 Land slot 13 on, H3 T2 Land on, H3b Land exception on, H5 T-M3 on`, no "does not match" |
| 2 | first tutorial thrall attacks | one `0.6.5 companion: ... obj 1004 ... companion object 870 ... type 0x3d ... byte +0x18 = 0, regeneration list count 1, entry 0 {2, 0, 0}` per thrall (or `none: <reason>` - send the line) |
| 3 | knock a thrall down so that it regenerates (finisher hint appears) | `0.6.3 death: ... notification 33 sent`; `hint_17` shows |
| 4 | let it stand up | `0.6.5 death: ... leaves RegenerateDeath: notification 34 sent`; the hint closes, the punch / kick hint comes back |
| 5 | next thrall down, finisher (type 16 hit) while it lies | `0.6.5 death: ... RegenerateDeath hit type 16 ... -> death switch kind 7 and notification 38`; thrall dies, hint closes at once |
| 6 | punch + kick afterwards | `tutorial` goes to 2 (TruMenu hall02 counter), wall opens after the next kill |
| 7 | heavy attack as the last hit | `0.6.5 regen: ... companion regeneration list entry 0 -> ShouldRegenerate yes` - the thrall regenerates instead of dying |
| 8 | thrall killed in the air / on landing | `0.6.5 land: ... lands with LP <= 0, companion byte +0x18 = 0: notification 33 sent, RegenerateDeath ...` (not LandDeath); with the lethal hit in Land first `0.6.3 death: ... no switch in Land` |
| 9 | trouble | switch the part off (TruMenu Fixes page or the .ini, live): `TranslateNotify38`, `TranslateLand`, `TranslateRegenList`, `[Melee] TranslateInterrupt`, `[Companion] Translate`; send the log |

0.6.4 (2026-11-07, **offline, not yet seen in game**): P1b - the title update's three small changes to the enemy state
`MeleeAttack` (T-M1..T-M3 of `docs\Befund-Thrall-MeleeAttack-Freeze-0711.md` section 4; full proof
`docs\Befund-P1b-MeleeAttack-0711.md` in the main workspace), T-M1 and T-M2 translated. Build `work\asi\combat064`.
The thrall freeze in MeleeAttack itself was a data bug (combo link record, `tools\melee_link_record_fix.py`); this
version does not touch it.
* State object 0x8aea00 "MeleeAttack", vtable 0x85912c = retail vtable 0x8206d160 / TU 0x8206d450 (18 slots). State
  data `(brain+0x1273 + ([brain+0x18d4+4i] + 2i) * 0x19c) & ~0xf` on all three exes (TU writes it as brain+0x1254 +
  0x680 / +0x1f), record = `[data+0x50]`. Update tru+0x265f10 and the follow-up helper tru+0x25bc10 are TU = retail =
  PC; the anim callback tru+0x225c60 sends 0x15 with data 0.
* **T-M1** message slot tru+0x266350 (retail 0x82331c28, TU 0x82330d40): retail / PC set data+0xa4 = 2 (= leave the
  attack) on 0x15 / 0x8a always and on 0xbe unless its data points at the instance; the TU (0x82331164..0x8233117c)
  only when the message data pointer is 0. The plugin points jump table tru+0x26672c entries 0 (0x15 / 0x8a) and 5
  (0xbe) at a stub: data != 0 -> switch default tru+0x266721 (return 0 = TU 0x82331578), data == 0 -> tru+0x2663c7
  (PC code unchanged). The byte table is checked: index 0 = exactly 0x15 / 0x8a, index 5 = exactly 0xbe.
* **T-M2** Enter slot tru+0x25c7b0 (retail 0x82330a88, TU 0x8232fb48): the TU added after the "record+8 bit 24 ->
  brain+8 |= 0x800000" step (PC tru+0x25c9da -> tru+0x2224c0) `if (!(record+8 & 4)) brain+0xc |= 1`
  (0x8232fd6c..0x8232fd8c) - the bit message 0xcb sets (PC tru+0x26670e = TU 0x8233155c) and 0xd1 clears. The plugin
  jumps from tru+0x25c9ea (10 bytes moved) into a stub with that test, back at tru+0x25c9f4.
* **Not translated: T-M3** (interruption slot 13, TU 0x82330830 / PC tru+0x242f40): the TU also lets Vaulted (TU
  0x82779bb0 = PC 0x8ae8bc) and RegenerateDeath interrupt - the latter only with the companion instance (TU
  0x822da918 = T4, missing on the PC). Belongs to the finisher / regeneration package T1-T4.
* `[Melee] Translate=1` (default **1**, a pure TU translation with proven twins); 0 = nothing patched. Read at the start
  only. Log lines (max 300 each): `0.6.4 melee: ... MeleeAttack message 0x15 with data 0x... ignored as the TU
  0x82331164 ...` and `0.6.4 melee: ... MeleeAttack Enter, record+8 bit 2 clear -> brain+0xc |= 1 as the TU 0x8232fd8c
  (bit was 0)`.
* New byte checks: 12 used by the plugin + 6 proof-only (`work\asi\combat064\prechecks_combat064.txt`, 18, 0 mismatches
  on the Steam exe); the earlier lists (combat01..combat063, 482 checks) still 0 mismatches. Imports unchanged (81,
  KERNEL32 only).

| # | TO TEST 0.6.4 (DLC 2 `dlc_yggdrasil_end` or hall02, God Mode; TruMenu `[Debug] EnemyStateLog=1`) | expected |
|---|---|---|
| 1 | load | `0.6.4 melee: [Melee] Translate 1 - T-M1 on ..., T-M2 on ...`, no "does not match" |
| 2 | let thralls attack (MeleeWindup -> MeleeAttack) | each attack ends with `FinishAttack` as before; `0.6.4 melee: ... MeleeAttack Enter, record+8 bit 2 clear ...` lines for records without flag bit 2 |
| 3 | watch for `message 0x.. with data` lines | note count / message (which PC sender passes data is not known; the normal anim end has data 0) |
| 4 | trouble | `[Melee] Translate=0`, restart |

0.6.3 (2026-11-07, **offline, not yet seen in game**): P1a - script notification 33 of the title update's thrall
death (T3 of `docs\Befund-Thrall-Felder-0611.md` 3.2; full proof `docs\Befund-P1a-ThrallTod-0711.md` in the main
workspace) and K14 on by default. Build `work\asi\combat063`.
* The enemy death check tru+0x220380 (retail 0x822f8c88, TU 0x822f6578) runs from the damage case tru+0x237630
  (flags bit 0): LP <= 0 -> ShouldRegenerate tru+0x27f040 -> yes: EnterRegenerateDeath tru+0x282780 (= retail
  0x8235efd8, state RegenerateDeath 0x8afa4c). The TU sends `TRScriptUnitManager::PlayNotification(33)` (TU 0x8247b0f0
  with `[0x829ca684]` = PC tru+0x37a540 with `[0xfae880]`, the pair of the script event handler TU 0x82473928 / PC
  tru+0x368a20) right there, before its query 0x182 / state switch. hall02's level script 23101 f3 answers 33 with
  the finisher hint `hint_17` (once, sticky +188); the wall does not wait for 33.
* `[Death] TranslateNotify33=1` (default **1**, a pure TU translation): the call at tru+0x2203fb goes to the plugin,
  which sends 33 and then calls tru+0x282780 with the same arguments (result unchanged). 0 = only the call (PC). Read
  again at run time at most once per second when the site is reached. One log line per such hit (max 1000):
  `0.6.3 death: 0x... obj 1004 viking_thrall_tutorial_dlc2_ lethal hit, ShouldRegenerate yes (LP -17, state not Land):
  notification 33 sent (TU 0x822f6638); then RegenerateDeath tru+0x282780 (PC)`.
* **Not translated (needs T4):** the TU's Land path T2 (TU 0x82328aa0, PC tru+0x25afe0) sends 33 and switches into
  RegenerateDeath only when the thrall's companion instance (TU 0x822da918: handle brain+0x5090 / +0x5094, set up by
  TU-only 0x822da800) exists and its data byte +0x18 is 0; without it the TU switches to LandDeath, exactly as the PC.
  The PC brain is 0x5040 bytes, it has no companion. T3's "no switch in Land" exception only makes sense together with
  T2, and the TU's own switch feeds its changed RegenerateDeath state (2-byte data, Enter 0x8235dff8) - both stay PC.
  The log names the Land case (`state Land ... the TU would not switch in Land`).
* `[Damage] Translate` (K14) now defaults to **1** (code and sample .ini): pure TU translation, live 07.11. (-40 per hit,
  the tutorial thralls die, the hall02 wall breaks).
* New byte checks: 6 used by the plugin + 10 proof-only (`work\asi\combat063\prechecks_combat063.txt`, 16, 0
  mismatches on the Steam exe); the earlier lists 88 + 6 + 21 + 4 + 13 + 12 + 11 = 155 still 0 mismatches. Imports
  unchanged (81, KERNEL32 only); exports unchanged (4).

| # | TO TEST 0.6.3 (DLC 2 hall01 / hall02 tutorial thralls; TruDlc2Player `TrackerFlag=1`) | expected |
|---|---|---|
| 1 | load | `0.6.3 death: tru+0x2203fb ... -> plugin - [Death] TranslateNotify33 1`, `0.6 damage switch (start): extend`, no "does not match" |
| 2 | kill a tutorial thrall with Lara's DLC 2 attacks (type 0 / 18..24 = regenerate list) | `0.6.3 death: ... ShouldRegenerate yes ... notification 33 sent`; the thrall goes to `RegenerateDeath` (TruMenu label); the finisher hint `hint_17` appears once |
| 3 | `[Death] TranslateNotify33=0`, next thrall | `0.6.3 switch: ... 1 -> 0`, `no notification`; no hint |
| 4 | trouble | `[Death] TranslateNotify33=0` |

0.6.2 (2026-11-07, **offline, not yet seen in game**): K9 - `CombatManager::MeleeSplashDamage` tru+0x2e68b0 as the
title update (TU 0x823e1220, retail 0x823dedc0; `docs\Befund-TU-K9-K11-0711.md` in the main workspace). Build
`work\asi\combat062`.
* The function (event dispatcher tru+0x316f30 case 75) calls the area damage tru+0x29f1e0 (TU 0x8237ae88) once per
  splash record of the current attack; argument 13 is the damage type (`[CM+0xc4]+0x0c`), which becomes +0x50 of the
  hit message 0x11c and so the type K14's switch sees. The TU added (a) in doppelganger mode (gameTracker+0x1244) the
  type remap through the extension's pair table (object 858, DTP 22497 +0xf0 +0x78 -> +0x1b0: **0x1a -> 0x10,
  0x10 -> 0x16**) and (b) always the main target (handle CM+0x48) as an 18th argument, which the area function skips
  right after its self test (TU 0x8237af64). Both are missing on the PC and in the upstream build.
* `[Splash] Translate=1` (default **1**): the call at tru+0x2e692d goes to the plugin (remap argument 13 in place, note
  the main target via the game's handle resolver tru+0x1b39d0, then jump into tru+0x29f1e0 with the original return
  address); the loop test tru+0x29f224 (`cmp esi, edi; je next`, 8 bytes) goes to a stub that also skips the noted
  target, only in calls returning to tru+0x2e6932 - the nine other callers of tru+0x29f1e0 stay unchanged (the TU's
  other callers pass 0). The remap runs only while the K14 switch is extended (`[Damage] Translate=1`): 22 is a type
  only the TU switch accepts. Without it the doppelganger records keep their type (`HELD BACK` in the log).
* The pair table comes from the loaded object 858 (PC twin of the TU's extension instance data, as the target list /
  TruShadowPower). The converted file holds three of the four words unswapped (+0x1b0 / +0x1b8 / +0x1bc read
  0x1a000000 / 0x10000000 / 0x16000000 in every PC tree); `[Splash] Fallback=1` (default) then uses the Xbox values and
  logs it (`0.6.2 splash table: ... FALLBACK`). Data fix pending (converter).
* `[Splash] Log=1`: burst lines every 2 s, e.g. `0.6.2 splash: x2 record type 26 -> 16 - doppelganger mode: REMAPPED
  as TU 0x823e1220, table Xbox values (FALLBACK ...); main target 0x... obj 1004 viking_thrall_tutorial_dlc2_; enemy
  switch as TU (0..27): damage + death check` and `... area hit(s) on the main target held back`.
* New byte checks: 11 (`work\asi\combat062\prechecks_combat062.txt`); with 88 + 6 + 21 + 4 + 13 + 12: 155, 0
  mismatches on the Steam exe. Imports unchanged (81, KERNEL32 only); exports unchanged (4).

| # | TO TEST 0.6.2 (DLC 2 hall01 / hall02 tutorial thralls; TruDlc2Player 0.4 `TrackerFlag=1`) | expected |
|---|---|---|
| 1 | load | `0.6.2 splash: tru+0x2e692d (...) and tru+0x29f224 (...) -> plugin - [Splash] Translate 1`, no "does not match" |
| 2 | `[Damage] Translate=0`: shadow moves (1018) / 1015 near several thralls | `0.6.2 splash:` lines `HELD BACK - damage switch is the PC's`, types unchanged; `held back` lines when the main target stood in the radius |
| 3 | `[Damage] Translate=1`: the same | `0.6.2 splash table: ...` once; `type 26 -> 16` / `type 16 -> 22` `REMAPPED`; K14 lines `type 22 ... switch as TU: damage + death check` for the splash victims |
| 4 | trouble | `[Splash] Translate=0` (PC splash at the next splash) |

0.6.1 (2026-11-07, **offline, not yet seen in game**): the fatal `ChunkDoll: failed to create geom` after a thrall
death with `[Damage] Translate=1` (`docs\Befund-ChunkDoll-Physikschritt-0711.md` in the main workspace). Build
`work\asi\combat061`.
* Chain (PC, code + live stack 07.11.): `PhysicsSystem::Step` tru+0xf0ab0 sets the lock `[phys+0x20f8] = 3` -> contact
  pairs tru+0x6d200 -> pair callback tru+0x92980 (geometry types 3 / 9) -> message 0x26 to Lara -> CombatManager contact
  hit tru+0x319050 sends the damage message 0x11c (with K14 the thrall's LP drops to <= 0) and then the impulse message
  **0x91** to the enemy -> enemy handler tru+0x23b330 case 0x91 -> **tru+0x224c60**: LP <= 0 and a chunk record ->
  chunkdoll create tru+0x296f90 **at once** -> rigid body tru+0x97270 -> `AllocBody` refuses inside the step (lock bit
  0) -> fatal. Live 12:12 the lock read 3, 13 of 405 bodies used.
* The TU changed exactly this branch (retail 0x82307ea8 -> TU 0x82305ba0, same size): no chunkdoll there any more;
  unless the enemy is already in a death state (TU 0x82324700: Death, LandDeath, DeferredInstantDie, DrownDeath, Fade =
  PC tru+0x240e90 on `[brain+0x125c]`) it computes the hit vector (TU 0x8230e5c0 = PC tru+0x256430, from a zero
  vector) and calls the death switch (TU 0x823258c8 = PC tru+0x241650) with (1, 0, 1, **kind 7**, 1); otherwise the
  hit-reaction path. The chunkdoll then comes from the Death state's per-frame slot 8 (tru+0x26c950 = TU 0x8232cd50,
  same record check) in the enemy update - outside the physics step.
* `[Chunk] Translate=1` (default **1**, a pure TU translation): the first instruction of the PC branch (tru+0x224caa,
  `mov eax, [edi+0x168]`, 6 bytes) jumps into the plugin, which runs the TU branch with the game's own functions and
  continues at the hit-reaction path tru+0x224ccd or the function's epilogue tru+0x224cf1. `Translate=0` (read again at
  run time at most once per second when the branch is reached) runs the moved instruction and the PC branch unchanged.
* `[Chunk] Log=1` (default, changes nothing): burst lines every 2 s from an own thread, per enemy / outcome:
  `0.6.1 chunk: 0x... obj 1004 viking_thrall_tutorial_dlc2_ x1 lethal impulse (message 0x91, tru+0x224c60) at LP -17,
  physics lock 0x3 (INSIDE the physics step), chunk record yes: TU: death switch (Death, kind 7) - chunkdoll left to
  the Death state (PC alone: chunkdoll NOW, bodies refused in the step -> fatal)`. `[Chunk] MaxLines=2000`. With
  `Translate=0` and `Log=0` nothing is patched.
* New byte checks: 12 (`work\asi\combat061\prechecks_combat061.txt`); with 88 + 6 + 21 + 4 + 13: 144, 0 mismatches on
  the Steam exe. Imports unchanged (81, KERNEL32 only); exports unchanged (4).
* Not here: the swapped piece records of `viking_thrall_chunkdoll_dlc2_` (DTP 24559 +0x130 / +0x158) and
  `yeti_thrall_armored_chunkdoll_dlc_2_` (DTP 26190 +0x150) are a converter fix.

| # | TO TEST 0.6.1 (fresh start, DLC 2 hall01 / hall02 tutorial thralls, `[Damage] Translate=1`) | expected |
|---|---|---|
| 1 | load | `0.6.1 chunk: tru+0x224caa (...) -> plugin - [Chunk] Translate 1 (...)`, no "does not match" |
| 2 | kill every tutorial thrall (combo / shadow moves) | no fatal; `0.6.1 chunk:` lines with `physics lock 0x3 (INSIDE the physics step)` and `TU: death switch`; pieces appear (TruTrace births, caller 0x00696bde) shortly after the death |
| 3 | population 0 | the hall02 wall breaks |
| 4 | trouble | `[Chunk] Translate=0` (PC branch at the next lethal impulse) |

0.6 (2026-11-06, **offline, not yet seen in game**): K14 - the damage-type switch of the enemy damage function
tru+0x237590 (TU 0x822f60e0, retail 0x822f87d8; `docs\Befund-K14-Schadensarten-0611.md` in the main workspace).
Build `work\asi\combat06`.
* The function (cdecl: instance, hit vector, float amount, bool, **type**, subtype, flags) switches over the damage
  type: PC / retail bound 16, byte table 0x6376c4 -> jump table 0x6376b8 with three case bodies (damage + death check
  0x637630, stamina 0x637685, nothing 0x6376b1). The TU bounds it at 0x1b and its 28-word table adds **17 -> nothing,
  18..27 -> damage + death check** (the same case body); 0..16 are unchanged. Lara's DLC 2 attack records
  (`doppelganger_casual` DTP 20212, activity 1005 -> CombatManager+0xc4, record +0x0c, `tools/chart_attack_damage_types.py`)
  use 17..27 for most hits (18..25 for the combo steps, 26 / 27 for the shadow moves of state 1018), so on the PC
  those hits never reach the health component nor the death / regenerate check (tru+0x220380, LP <= 0) - no damage,
  no `Hit`, no `RegenerateDeath`. The finisher's own records (types 1 / 4) and the shadow step (17) are not affected.
* `[Damage] Translate=1` (default **0**): the byte-table operand of `movzx edx, byte [esi + table]` (tru+0x237625)
  points at a 28-entry table in the plugin (TU mapping), then the bound byte tru+0x23761b becomes 0x1b - jump table
  and case bodies stay the game's. Table first, bound last (off: bound first), so every intermediate state is a valid
  switch. Read again at run time at most once per second while hits come (from the entry hook, before the original
  runs); bytes that are neither the game's nor ours freeze the switch (logged).
* `[Damage] Log=1` (default, **changes nothing**): entry hook on tru+0x237590 (5 bytes -> trampoline, the original
  runs with the same arguments). Per target / type / subtype / caller it counts the hits and writes burst lines every
  2 s while hits happen (a flush thread; no game memory read or written there):
  `0.6 damage types: 0x... obj 1004 viking_thrall_tutorial_dlc2_ type 19 sub 2 x3 via hit message 0x11c
  (tru+0x23aaa0), amount 40.0, flags 0x3, LP 500 -> 500: PC: DROPPED (above the bound) (TU: damage + death check)`.
  Callers named: hit message (tru+0x23aaa0, type = message +0x50), kill (tru+0x2376e0, amount = LP), fall
  (EnemyState_Fall tru+0x25adb0, type 8). `[Damage] MaxLines=3000`. With `Log=0` and `Translate=0` the function is not
  touched (then a later `Translate=1` needs a restart).
* New byte checks: 13 (`work\asi\combat06\prechecks_combat06.txt`); with 88 + 6 + 21 + 4: 132, 0 mismatches on the
  Steam exe. Imports: `CreateThread`, `Sleep` added (81, KERNEL32 only); exports unchanged.

| # | TO TEST 0.6 (DLC 2 hall01 / hall02 tutorial thralls, god mode, `[Debug] EnemyStateLog=1` in TruMenu) | expected |
|---|---|---|
| 1 | load | `0.6 damage: entry hook tru+0x237590 placed ...`, `0.6 damage switch (start): the game's ...` |
| 2 | `Translate=0`: punch / kick / shadow move on a thrall | `0.6 damage types:` lines; types 18..27 with `DROPPED`, LP unchanged |
| 3 | `Translate=1` (INI, no restart) | `0.6 switch: [Damage] Translate 0 -> 1`, `damage switch (run time): EXTENDED ...`; LP drops, `Hit`; lethal hit with 18..24 -> `RegenerateDeath` -> `Regenerate`, others -> `Death` |
| 4 | trouble | `Translate=0` (restored at the next hit) or `Log=0` + `Translate=0` and restart |

0.5.3 (2026-11-05, **offline, not yet seen in game; read-only - behaviour unchanged**): a data export for TruMenu
0.13's thrall labels (debug view stage S1) and one fix of the 0.5.2 diagnostics. Build `work\asi\combat053`.
* Export `DWORD __cdecl TscTargeterSnapshot(DWORD tuIndex, void *out, DWORD outSize)`: tuIndex 9 only; copies
  `TscTargeterSnapshotV1` (version 1, 604 bytes; `static_assert` in both plugins): targeter 9, its target object
  (+0x90), flags / candidates / groups / bucket counts / rejected count, up to 24 list entries {instance, where = 0x10 +
  group (bucket) or 0x20 (rejected), the last WHY result for rejected ones (0x100 = eligibility passed, low byte = filter
  groups passed; 0xffffffff = not evaluated), its tick, marker data}, the player's 8-slot hit list
  `[[0xfadb58]+0x504]+0xa4`, the last condition 2011 (calls, tick, path, result, query 0x161, target). Returns 1 = a copy
  from the game thread, 0 = none (the first 8 bytes always carry size and version). Every call marks "asked"; the copy
  is built at the end of slot 9's per-frame update (after the original) only while a reader asked within 2 s, under a
  sequence counter. No game data written, no game function called for it. `[Diag] Snapshot=1` (0 = the export answers
  "none"); needs `[Diag] Targeter9=1`.
* Fix: `WHY rejected` walked the rejected list by node +0 - that is the **prev** link (list append tru+0x2ecd40: tail +4
  -> new node, new node +0 = old tail; the select walk tru+0x3166f3 reads `mov esi, [esi+4]`), so 0.5.2 reported only the
  first rejected candidate. 0.5.3 follows +4 (next): up to 4 candidates as documented.
* New byte checks: 4 (`work\asi\combat053\prechecks_combat053.txt`: the two list-link facts in SetupDiag, the hit list
  owner / clear for the snapshot); with 88 + 6 + 21: 119, 0 mismatches. Imports unchanged (79); exports + 1.
* Log: `0.5.3 snapshot: TscTargeterSnapshot (read-only export for TruMenu's thrall labels) on - built only while a reader
  asks, hit list verified`.

0.5.2 (2026-11-05, **offline, not yet seen in game; log only - behaviour unchanged**): diagnostics for F21 (the
finisher 1013 is never entered because condition 2011 finds targeter 9 empty). Static result first: the TU fills
targeter 9 with the **same** code as every other targeter - the instance add 0x82406390 (mask 0x3f1, the 0.1 patch) and
the candidate add 0x82404650 (= PC tru+0x316860 / tru+0x3164d0); all five TU callers of the instance add have PC
partners (instance init tru+0x1ba5a3 / +0x1ba801, tru+0x2d6126, the list ctor tru+0x31dc93, player message 0x1dc
tru+0x31f93e; message ids TU = PC), and the per-frame sort / select / set / get functions are relink (TU = retail).
No TU-only filler, so nothing new is translated. The log answers which step loses the thrall (`[Diag]`, default on):
* entry hooks (log only, the original runs with the same arguments): candidate add tru+0x3164d0 (instance, marker
  data, mask vs. slot bit 0x200, return and outer caller: which of the five paths), set target tru+0x316730, select
  tru+0x316590 (bucket entries present but nothing passed = sight test / exclusion), remove tru+0x319f80 (target
  cleared), per-frame update tru+0x31a270 (target changes, bucket / rejected counts); redirected calls: target list
  array build tru+0x32263a / destroy tru+0x32219e (slots 0..9, slot 9 bit / parameters). Changes of +0x90 that none
  of these made are reported as "changed outside the hooked functions".
* `Targeter9Why=1`: once per second for up to 4 rejected candidates the game's own eligibility tru+0x2ecca0 and the
  filter tru+0x312090 per group (the functions the update calls for them every frame) - which test rejects them.
* condition 2011: every evaluation in doppelganger mode on change (else every 2 s) with the record {+0, +2 id, +4
  value, +6 flags}, targeter 9 before / after the get call, excluded, the answer of query 0x161.
* lines `0.5.2 diag ...`, capped by `[Diag] MaxLines=4000`. New byte checks: 21
  (`work\asi\combat052\prechecks_combat052.txt`; with the 88 of 0.5 and the 6 of 0.5.1: 115, 0 mismatches). Imports:
  `VirtualAlloc` added (trampoline page, RW -> RX). Build `work\asi\combat052`.

| # | TO TEST 0.5.2 (hall02 / Yggdrasil end, power on, all Translate switches as in the package) | expected |
|---|---|---|
| 1 | load | `0.5.2 diag: targeter 9 (log only) - entries ...`; at the level `0.5.2 diag target list BUILT ...: slot 9: index 9, bit 0x200, parameters 0x...` |
| 2 | walk to the thralls | `0.5.2 diag targeter 9 candidate TAKEN ...` with the thrall's object name = it is offered; only `not offered (mask)` lines for it = its marker flags lack bit 0 (data) |
| 3 | knock one down, stand next to it, power on | `targeter 9 state changed ...` buckets / rejected; `WHY rejected`: eligibility 0 = the thrall's answers (queries 0x14c / 0xca / 0x185 / 0x1d), groups passed 0 = distance / cone; `SELECT ... none passed` = sight test; `SET target` = it got one |
| 4 | X / Y next to it | `0.5.2 diag condition 2011 changed ...: path 2` + `query 0x161 0` = target there, thrall says no; path 3 = 2011 true (then `state 1013` should follow) |

0.5.1 (2026-11-04, **offline, not yet seen in game**): two TU differences in Lara's state table of retail states
(found while porting 1019 / 1020), translated 1:1, **default off**:
* **231** (move to gameTracker+0x1260 facing +0x1270; chart records #773 [1007, 231, 1004] and #819): TU slots 0 **and
  1** = 0x82464160 = the move helper 0x82463c18 with its doppelganger branch (0.5's `MoveTo`); PC: slot 0 only,
  tru+0x35f550 -> tru+0x35f470 (retail 0x8245f930). Switches `[States] Translate231Slot0=0`, `Translate231Slot1=0`.
  Slot 0 differs from the PC only on move paths 3..6 (frames n x 100 <= animation +0x28).
* **1004** (records #741 [1004, 1013], #756, #773): TU slots 0 / 1 = 0x8245efc8 = the player's 8-slot hit list +0xa4
  (filled by the finisher 1013) is cleared only when the state's bool parameter 0x415 is **not** set, then
  0x823dfc98 (= PC tru+0x3036c0); PC slot 0 tru+0x35e020 always clears, no slot 1. Switch `[States] Translate1004=0`.
* Slot 1 = enter while the state was already active in the previous chart record (PC enter loop tru+0x385a30, getter
  tru+0x384790); a null slot is skipped, so the log-only slot 1 with the switch off is the PC behaviour.
* Off: the PC handler runs and a line `... off (would): ...` appears whenever the TU would do something else; on: `ON:`.
  Switches read again at run time (`0.5.1 switch: [States] Translate1004 0 -> 1 ...`). `[Probe] States231And1004=0`
  leaves both records untouched (= 0.5). New byte checks: 6 (`work\asi\combat051\prechecks_combat051.txt`, plus the
  88 of 0.5; 0 mismatches). Build `work\asi\combat051`.
* **Strike look off** (TU 0x823d9050) in the translated strike (`[Strike] Translate=1`), through the meter interface
  **v4** `strikeLookOff` of TruShadowPower 0.14 (used only when `version >= 4` and `size >= 60`, else skipped, logged
  once). Order as the TU: tick, input edge with model +0x40 bit 7 clear: flag 4 -> drain all, then look off
  (0x823d8dfc..0x823d8e1c); bit 7 set: look off, then the second strike (0x823d8db0); end: flag 4 -> look off, then
  drain all (0x823d92ac..0x823d92d0). 0x823d9050 itself does nothing without flag 4. The version-3 size test of
  `gt1280` is now `size >= 56` (it was `sizeof` of the interface struct, which grew to 60). Log:
  `meter interface: strike look off (TU 0x823d9050) found (version 4) ...`, per call with flag 4 `shadow strike
  tick / end: strike look off (...), meter flags 0x... -> 0x...`.

| # | TO TEST 0.5.1 (hall02, power on) | expected |
|---|---|---|
| 1 | load | `states 231 / 1004 (...): building blocks verified, wrapped ...`; `machine 1 states: ... 231 (slots 0 / 1, log only) 1004 (slots 0 / 1, log only)` |
| 2 | knock a thrall down, finisher (switches off) | `state 1004 slot 0 / 1 ...: off (would): parameter 0x415 1, hit list slots used n -> TU: list kept` = the TU keeps the list where the PC clears it |
| 3 | `Translate1004=1`, same | `0.5.1 switch: [States] Translate1004 0 -> 1`, `ON: parameter 0x415 1 ... list kept`; **do the thralls stay down?** |
| 4 | shadow step (1007, X with power) | `state 231 slot 1 ...: off (would)` (re-entry) / slot 0 lines only on paths 3..6; with `Translate231Slot0/1=1`: `ON:` |

0.5 (2026-11-04, **offline, not yet seen in game**): the last two untranslated TU states of Lara's combat, **1019**
(TU 0x8245f420 slots 0 / 1, 0x8245f540 slot 3; chart record #756 of `doppelganger_casual` DTP 20212, the combat hub)
and **1020** (TU 0x8245f398 slots 0 / 1; record #748 after the finisher #741, list index 8 = targeter 8), with their
TU-new helpers 0x8245f2a8 (point next to the target, VMX128 math), 0x82463c18 (channel move = retail 0x8245f930 / PC
tru+0x35f470 plus a TU doppelganger branch) and 0x82463eb8 (face only). The VMX128 bodies were decoded with
`tools/ppc_dis128.py` and cross-checked against the Xenia emulator's published decoder tables with the new
`tools/vmx128_xenia_check.py` (77 / 77 words of the state code the same). 1019 keeps its target handle (TU meter
+0x20 / +0x24, only 1019 uses it - `tools/ppc_ptr_field_users.py`) in the plugin. Both are registered with Lara's
state table (needs TruDoppelganger's generic registry, as 1017 / 244) and are **log only** by default:
`[States] Translate1019=0`, `Translate1020=0` (read again at run time, at most once per second); `[Probe]
States1019=0` leaves them out (= 0.4.1). New byte checks: 17 (88 in total, `work\asi\combat05\prechecks_combat05.txt`,
0 mismatches on the Steam exe). Details: `docs\Befund-Schattenkampf-0411b.md` (main workspace).

| # | TO TEST 0.5 (after F4 is confirmed; hall02, power on) | expected |
|---|---|---|
| 1 | load | `states 1019 / 1020 (...): building blocks verified, registered ...`, `machine 1 states: ... 1019 (added, log only) 1020 (added, log only)` |
| 2 | power on near thralls, aim / fight (switches off) | `state 1019 slot 0 / 1 (...) (call n): off (would) ...` with the reason / path; `state 1019 slot 3 ...: off: nothing (no valid meter target)`; after a finisher `state 1020 ...` |
| 3 | `Translate1019=1`, `Translate1020=1` (TruMenu switch or INI) | `0.5 switch: [States] Translate1019 0 -> 1`; `ON slot 0 ... step next to it ... meter handle set`; slot 3 `ON follow the meter target`; Lara steps / turns to the thrall |
| 4 | trouble | both 0 (or `[Probe] States1019=0`) |

0.4.1 (2026-11-03, **offline, not yet seen in game**): `[Strike] Translate` and `[States] Translate1013` are read
again from `TruShadowCombat.ini` at run time - at most once per second, from the code they switch (state 1014 slots
0 / 2 / 3, the 1013 target site tru+0x31d610), so TruMenu's TO TEST switches `sc-strike` / `sc-translate1013` (which
write the INI at once) count from the next strike / finisher without a restart. Nothing new is translated: the
switches only turn on / off the code 0.4 built and byte-checked at the start. To make that possible the three 1013
sites are now patched at the start whenever their byte checks pass, also with `Translate1013=0` (then every site runs
the PC path - the same code path 0.4 used outside doppelganger mode). A strike that runs keeps the translation until
its end (meter flag 2 cleared by slot 2); a missing key keeps the current value; the 1014 wrappers need `Gate=1` (the
default) or `Translate=1` at the start. Log lines: `0.4.1 switch: [Strike] Translate 0 -> 1 (read again from
TruShadowCombat.ini)`, `0.4.1 switch: [States] Translate1013 1 -> 0 ...`, at the start `state 1013 translation: off
([States] Translate1013=0) - sites ... patched but they run the PC path ...` or `... ON (...)`. Build
`work\asi\combat041` (sha256 `24fcd9331b651f8f00657da736caae1d4d90a93b7de155fced06faa7bc4554a7`, 0 compiler warnings),
pre-checks `work\asi\combat041\prechecks_combat041.txt`: 71 checks, 0 mismatches on the Steam exe (the 0.4 list; no
new engine address). Profiles: the `_radial2` variants (`regress_shadowlara_50l_radial2`, `_50n_radial2`,
`_50l_hud_radial2`); 50l / 50n / 50l_hud keep 0.4 (`combat04`).

| # | TO TEST 0.4.1 (hall02, switches in TruMenu Tests -> Schalter or the TO TEST page) | expected |
|---|---|---|
| 1 | load | `TruShadowCombat 0.4.1 ... loaded`, `state 1013 translation: off ([States] Translate1013=0) - sites ... patched`, no "does not match" |
| 2 | downed thrall, power on: switch `sc-translate1013` on, X / Y next to it; then off | `0.4.1 switch: [States] Translate1013 0 -> 1`, then the 0.4 translation lines (row 2 below); off: `1 -> 0`, probe lines only |
| 3 | same with `sc-strike` | `0.4.1 switch: [Strike] Translate 0 -> 1`, `state 1014 slot 0 ... TU strike translation`, `shadow strike start / hit / end`; off: `1 -> 0`, `[Strike] Translate=0 - strike not run` |

0.4: `[States] Translate1013=1` (default 0 - then nothing is patched) runs the finisher state 1013 (PC tru+0x31d600)
in doppelganger mode as the TU's 0x823e0a88: target of targeter 9 (if it has a handle), the target into the player's
8-slot hit list +0xa4, hit record +0x68 = attack data (player +0xc4) byte +1 instead of 0xff, message record +0x3c =
0. Three sites in the PC function are redirected (tru+0x31d610 call, tru+0x31d825 push 0xff, tru+0x31d895 call);
outside doppelganger mode they do what the PC did. Build `work\asi\combat04`, 71 pre-checks (0 mismatches).

| # | TO TEST 0.4 (tree 50l, `Translate1013=1`) | expected |
|---|---|---|
| 1 | load | `state 1013 translation: ON (...)` |
| 2 | hall02: knock a thrall down, power on, X / Y next to it | `state 1013 translation ... target of targeter 9: 0x...`, `message 0xf4 to 0x..., hit list slot n, record +0x3c = 0`; LogLevel 2: `hit record +0x68 = n (attack data +1)`; does the thrall stay down now? |
| 3 | main game finisher (any downed enemy) | unchanged (no translation lines outside DLC 2) |
| 4 | trouble | `Translate1013=0` |

0.3: probe of state 1013 (the finisher, PC tru+0x31d600 = TU 0x823e0a88) - `[Probe] State1013=1` logs the PC
target (targeter 5) next to the TU's doppelganger target (targeter 9), the PC handler runs unchanged; meter API v3
(`gt1280`, TruShadowPower 0.12) used when present. Build `work\asi\combat03`, 65 pre-checks. TO TEST 0.3: in hall02
knock a thrall down, power on, X / Y next to it -> `state 1013 slot 0 ... PC target ... TU target ...`
(Befund-Schattenkampf section 10).

Translation of the Xbox title update's (TU) **target list**, **target conditions**, the target **states 1017 / 244 /
1007** (0.2) and the **shadow strike** (state 1014, 0.2, behind `[Strike] Translate`, default off) for Lara's Shadow on
the Steam `tru.exe` (image base 0x400000). Findings and
the full Xbox -> PC map: workspace doc `docs\Befund-Schattenkampf.md`. Rule: translate, do not imitate - every value
comes from the same data / code the Xbox uses.

Needs (loaded by the Ultimate ASI Loader, alphabetical): `TruDlc2Player.asi` (doppelganger flag = TU
gameTracker+0x1244), `TruDoppelganger.asi` (generic registry of the TU condition ids). Works next to
`TruShadowPower.asi` (its copies of Lara's tables are extended, not replaced).

## What it does

| part | TU (Xbox) | PC |
|---|---|---|
| target list 7 -> 10 | 0x824062c8 ctor (`cmpwi 0xa`), 0x82406390 instance add (mask 0x71 -> 0x3f1, 2 loops), 0x82412ca0 player init (array 0x28 bytes, destroy loop), 0x824126d8 per-frame loop, 0x823ed958 / 0x823c3eb8 / 0x823c6790 / 0x822ebc58 loops | patched constants at tru+0x322631, +0x31dc7a, +0x316916, +0x316948, +0x3169a3, +0x3169d2, +0x31acab, +0x31dcd0, +0x316845, +0x3228a5 |
| targeter parameters | 0x82402208: tuning (object 858) table +0x90 / count +0x94 first, else 0..5 retail, 6 -> +0x468, 7 -> +0x478, 8 / 9 -> none | tru+0x2ecc10 (retail switch 0..6) replaced; slot 7 = TU 6, slots 8 / 9 = TU 8 / 9, slot 6 stays the retail 6 (= TU 7) |
| condition 2005 | 0x8246ea20 / predicate 0x8246e8e0 | new record (group 2000) in both machines |
| condition 2006 | 0x8246ec68 / 0x8246eb08 | new record, machine 1 |
| condition 2013 | 0x8246eaf8 / 0x8246ea30 | new record in both machines (reads state 1017's target - 1017 not ported, so 0) |
| condition 2011 | 0x8246f270 / 0x8246f140: doppelganger -> targeter 9 + query 0x161 | handler replaced; outside DLC 2 the PC predicate tru+0x365970 |
| condition 538 | 0x8246fae0 / 0x8246faa8: doppelganger -> meter flag 8 | handler replaced; outside DLC 2 tru+0x365fa0; in DLC 2 needs `TruShadowPowerMeterApi` (not in TruShadowPower 0.9 -> 0) |
| state 1014 | 0x8245fd70 / 0x8245fdc0 / 0x8245fd98: doppelganger -> 0x823d8978 / 0x823d9210 / 0x823d8d18 (meter object) | slots 0 / 2 / 3 wrapped: in DLC 2 with `[Strike] Translate=1` and `TruShadowPowerMeterApi` (TruShadowPower 0.11+) the TU strike (placement + message 0xbe 0x823d86a8, hit tru+0x1b4de0, message 0x3f at the end); else nothing (`Gate=1`); outside DLC 2 the PC handlers |
| state 1017 slot 4 (0.2) | 0x8245f5a0: target from parameter 0x40f / aim, facing (0x82457b28), gameTracker+0x1260 / +0x1270, target handle +0x1284 | new record; facing tru+0x30b8a0; the handle feeds condition 2013 and state 244 |
| state 244 (0.2) | 0x82464198 / 0x824642a8 / 0x82463fc8: dash to the 1017 target | new record; channel mode 2 tru+0x38d00; step count +0x1280 (shared with TruShadowPower only from meter API version 3) |
| state 1007 slots 4 / 5 (0.2) | 0x8245f068 (doppelganger branch) | wrapped: doppelganger -> translation, else PC slot 4 tru+0x36d930 |

The tables are extended when Lara's registration runs (PC tru+0x368b60, reached through the vtable slot 0x85e1d4):
the current `push table` operand (original or TruShadowPower's copy) is copied with these records. Byte pre-checks:
40 (`work\asi\combat01\prechecks_combat01.txt`, `tools/pe_bytes_check.py`: 0 mismatches on the Steam exe). Any
mismatch switches the affected part off with a log line.

## Data

The targeters 8 / 9 take their parameters from DTP 22497 of `player_tru_dlc2_extension.drm`; 10 words of that
section were converted wrongly (count 2 -> 0x200, index byte, flags, record kinds / floats). Fixed file in tree
`work\rebuild\dlc_test50l_combat\mods` (= 50k_cut + this file), tool `tools/tuning_target_fix.py`. With the old file
the plugin logs "tuning +0x94 = ... implausible" and the targeters 8 / 9 get no parameters.

0.2: the tree also holds `doppelganger_casual.drm` with the list index parameter 0x40f (activity 1039, type 46, read
by the TU as one byte) fixed in 4 records (`tools/chart_act_u8_fix.py`) - without it state 1017 reads list index 0
instead of 6 in records #764 / #765 / #770 (#773: 5 -> 0).

## Options (TruShadowCombat.ini)

| key | default | meaning |
|---|---|---|
| `[ShadowCombat] Enabled` | 1 | 0 = load, patch nothing |
| `[ShadowCombat] LogLevel` | 1 | 0 errors, 1 info + first call of every translated condition / state, 2 + result changes, 3 + periodic |
| `[TargetList] Enabled` | 1 | 0 = PC list unchanged (2005 / 2006 / 2013 / 2011 in DLC 2 answer 0) |
| `[Conditions] Enabled` | 1 | the five conditions |
| `[States] Enabled` | 1 | 0.2: states 1017 / 244 / 1007 (slots 4 / 5) |
| `[Strike] Gate` | 1 | state 1014 in DLC 2 without the translation: 1 = nothing, 0 = PC retail strike as before |
| `[Strike] Translate` | 0 | 0.2: 1 = the TU shadow strike (needs `TruShadowPowerMeterApi`, logged "no meter interface" otherwise); 0.4.1: read again at run time (<= 1 / s) |
| `[States] Translate1013` | 0 | 0.4: 1 = the finisher 1013 in doppelganger mode as the TU; 0.4.1: read again at run time (<= 1 / s) |
| `[Probe] State1013` | 1 | 0.3: log the PC / TU target of the finisher 1013 |
| `[Diag] Targeter9` | 1 | 0.5.2: log-only hooks of targeter 9 (add / update / select / set / remove, list build / destroy); 0 = no hooks |
| `[Diag] Targeter9Why` | 1 | 0.5.2: eligibility / filter result of the rejected candidates of targeter 9 (once per second) |
| `[Diag] Condition2011` | 1 | 0.5.2: every evaluation of condition 2011 in doppelganger mode with its inputs |
| `[Diag] MaxLines` | 4000 | 0.5.2: total cap of the diagnostic lines |
| `[Diag] Snapshot` | 1 | 0.5.3: read-only export `TscTargeterSnapshot` for TruMenu's thrall labels (built only while asked) |
| `[Damage] Translate` | 1 | 0.6: 1 = the TU damage-type switch 0..27; read again at run time (<= 1 / s while hits come); default 1 since 0.6.3 (live 07.11.) |
| `[Damage] Log` | 1 | 0.6: burst lines of the incoming damage types (changes nothing) |
| `[Damage] MaxLines` | 3000 | 0.6: cap of the damage lines |
| `[Chunk] Translate` | 1 | 0.6.1: lethal impulse (message 0x91) as the TU - death switch kind 7 instead of a chunkdoll inside the physics step; 0 = PC branch; read again at run time (<= 1 / s) |
| `[Chunk] Log` | 1 | 0.6.1: burst lines of the lethal impulses with the physics lock (changes nothing) |
| `[Chunk] MaxLines` | 2000 | 0.6.1: cap of the chunk lines |
| `[Splash] Translate` | 1 | 0.6.2 (K9): MeleeSplashDamage as the TU - main target excluded from the splash; doppelganger remap 0x1a -> 0x10 / 0x10 -> 0x16 while `[Damage] Translate=1`; 0 = PC splash; read again at run time (<= 1 / s) |
| `[Splash] Fallback` | 1 | 0.6.2: the Xbox pair values when object 858's table differs from them (converted file: words unswapped); 0 = table as loaded |
| `[Splash] Log` | 1 | 0.6.2: burst lines of the splash records (type in / out, main target, enemy switch verdict; changes nothing) |
| `[Splash] MaxLines` | 2000 | 0.6.2: cap of the splash lines |
| `[Death] TranslateNotify33` | 1 | 0.6.3 (T3): script notification 33 before EnterRegenerateDeath in the death check tru+0x220380, as the TU 0x822f6578 (hall02: finisher hint `hint_17`); 0 = PC; read again at run time (<= 1 / s) |
| `[Melee] Translate` | 1 | 0.6.4 (T-M1 / T-M2): enemy MeleeAttack as the TU - messages 0x15 / 0x8a / 0xbe end the attack only without a data pointer (TU 0x82330d40), Enter sets brain+0xc bit 0 unless record+8 bit 2 (TU 0x8232fb48); 0 = nothing patched; start only |
| `[Companion] Translate` | 1 | 0.6.5 (H0): the thrall's companion (TU 0x822da800 / 0x822da918) as an object-table lookup; 0 = never a companion (TU without one = PC); live (<= 1 / s) |
| `[Companion] Log` | 1 | 0.6.5: one line per new thrall instance (companion object, type, byte +0x18, regeneration list; or the reason for none), max 400 |
| `[Death] TranslateNotify34` | 1 | 0.6.5 (H6): notification 34 at every RegenerateDeath exit (TU 0x8235e338); live |
| `[Death] TranslateNotify38` | 1 | 0.6.5 (H7 / H8): finisher block of RegenerateDeath / Regenerate slot 10 - type 16 (or 1 / 1) hit with companion -> death kind 7 + notification 38 (TU 0x8235e3a8 / 0x8235e998); live |
| `[Death] TranslateRegenList` | 1 | 0.6.5 (H1): companion regeneration list before the tune list in ShouldRegenerate (TU 0x8235ece8); live |
| `[Death] TranslateLand` | 1 | 0.6.5 (H3 / H4 / H3b): T2 Land with LP <= 0 -> 33 (with TranslateNotify33) + RegenerateDeath, Land slot 13 with companion, Land exception of T3; live |
| `[Melee] TranslateInterrupt` | 1 | 0.6.5 (H5, T-M3): Vaulted and (with companion) RegenerateDeath may interrupt MeleeAttack (TU 0x82330830); live |
| `[Death] TranslateT5` | 1 | 0.6.6 (T5): lethal, not regenerating hit on an enemy with a companion -> death kind 7 at once in the hit reaction (TU 0x823038d8); live |
| `[Death] TranslateVaulted` | 1 | 0.6.6 (P1c): Vaulted Enter as the TU 0x8232b630 with the step chain (records 0xbe / 0xf4, switch, copier); step table only from fixed extension data; live |
| `[Death] TranslateVaultedClock` | 1 | 0.6.6 (P1c K): the TU's Vaulted clock - 5 s without slow motion (Enter 0x8232b698, enemy update 0x822db190); needs the chain; live |

Log: `TruShadowCombat.log` next to tru.exe.

## Build / install

```
scripts\windows\Build-TruAsi.ps1 -Name TruShadowCombat -OutDir work\asi\combat02
scripts\windows\Set-TruShadowCombat.ps1 -Install -SourceDir work\asi\combat02     (game closed; replaces 0.1)
scripts\windows\Set-TruShadowCombat.ps1 -Remove
```

Byte pre-checks 0.2: 64 (`work\asi\combat02\prechecks_combat02.txt`, 0 mismatches on the Steam exe).

## TO TEST (0.2: tree `dlc_test50l_combat`, TruShadowPower 0.11)

| # | where | what | expected log / picture |
|---|---|---|---|
| 1 | game start | load | `TruShadowCombat 0.2 ... loaded (... states 1, strike gate 1, strike translate 0)`, `target list: 7 -> 10 targeters ... 10 sites patched`, `Lara registration: vtable slot 0x0085e1d4 -> hook`, no "does not match" line |
| 2 | main game level | Lara loads, a few fights | `targeter slot 0..9` lines; `machine 1 conditions: 2005 (added) 2013 (added) 2006 (added) 2011 (replaced) 538 (replaced)`, `machine 2 ...`, `machine 1 states: 1014 (slots 0 / 2 / 3 gated) 1007 (slots 4 / 5) 1017 (added) 244 (added)`; main-game combat (aim, adrenaline dodge, headshot) as before |
| 3 | DLC 2 start | load | slots 8 / 9 `DLC 2 tuning table (object 858 +0x90)` with a non-zero parameter; no "implausible" line; `TruShadowPower meter interface found (version 2 ...)` at the first doppelganger condition |
| 4 | `dlc_yggdrasil_hall02` thralls | RB near a thrall, aim at it | `condition 2011 / 2005 / 2006` lines, `condition 538` now from meter flag 8 (switches to 1 when the meter is high); `state 1017 slot 4 ... first call` and `state 244 ...`: Lara turns to / dashes at the thrall; `condition 2013 -> 1` |
| 5 | same, `[Strike] Translate=1` | knock a thrall down, power + X next to it | `state 1014 slot 0 ... TU strike translation`, `shadow strike start: target ...`, `shadow strike hit ...`, `shadow strike end: message 0x3f sent`; does the thrall stay down? how long does the strike animation run (x100 question, Befund 9.4)? |
| 6 | any | crash / odd targeting | `[Strike] Translate=0`, `[States] Enabled=0`, `[TargetList] Enabled=0`, `[Conditions] Enabled=0` in that order; send the log |
