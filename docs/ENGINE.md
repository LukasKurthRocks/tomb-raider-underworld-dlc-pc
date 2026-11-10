# Engine reference: how Tomb Raider: Underworld works (PC `tru.exe` 1.1 and Xbox 360 title update)

One place for everything the project learned about **how the game engine works**: what it does, its data layouts and
state flows, where it lives in the PC executable, how the Xbox title update (TU) differs, and what our plugins and tools
do about it. The aim is that with this file everything only has to be *rebuilt*, never *re-discovered*.

This file is the **index and summary**. Details, disassembly and test logs stay in the sources it names. Conversion
pipeline: [ARCHITECTURE.md](ARCHITECTURE.md), [PIPELINE.md](PIPELINE.md). The older short-facts file
[FINDINGS.md](FINDINGS.md) is only a pointer here since 08.11. (its content is merged in, marked "from FINDINGS.md"). DLC 2 notes: [DLC2.md](DLC2.md). Costumes: [COSTUMES.md](COSTUMES.md). Open work list:
[INVESTIGATION.md](INVESTIGATION.md), [STATUS.md](STATUS.md).

## Conventions

| Item | Rule |
|---|---|
| PC executable | Steam `tru.exe` 1.1, unpacked (Steamless), image base **0x400000** (md5 `5560abac...`) |
| PC addresses | **Absolute virtual addresses** everywhere in this file (e.g. `0x637590`). Many sources write `tru+0x237590`: subtract 0x400000 to compare. `[0xfadb58]` means "the dword at 0xfadb58" |
| Xbox addresses | `0x82......` = Xbox TU image (title update 0.0.2.3), unless marked *retail* (disc exe) |
| Field offsets | `+0x2c` relative to the object named in the row; `[[a]+b]` = pointer chain |
| Status | ✅ proven (decompiled + byte-checked, measured in data, or seen live - "live" is said when it was) · 🔶 inferred (read from code or names, not measured) · ⬜ open question |
| Plugin state | "built" = compiled and byte-checked, not yet seen working in the game; "live" = confirmed in the game |
| Sources | German findings `Befund-*.md` live in the project's findings folder **outside this repo** (owner workspace `docs\`, next to `trudlcport\`); they are named, not linked. Repo docs and tools are linked |
| Plugins | `src/asi/<Name>/README.md` holds the per-version detail, INI keys and test recipes |

---

## 1. TU vs PC at a glance

What the Xbox title update (the version the DLCs were built for) does differently from PC retail 1.1, and our answer.
Full table with 104 rows: `TU-Abdeckung.md` (findings folder). "Data" = fixed in the converted files, no exe change.

| Area | TU behaviour | PC 1.1 | Our port |
|---|---|---|---|
| Lara state chart ids | +13 conditions, +9 activities, +8 states (243-245, 1017-1020, 2102) | retail tables | TruDoppelganger (table copies) |
| Shadow power (tick, start / stop, slow motion, meter from 858) | TU 0x823d7a10 / 0x823d7d40 / 0x824126d8 | absent | TruShadowPower ✅ live (gameplay partly played) |
| Shadow meter conditions 1049-1054 / 1056 | TU | absent | TruShadowPower `[Conditions]` (1055 left out) |
| Rock vein markup types 22 / 23, conditions 607 / 608, 5th geometry function | TU | missing | TruRockVein |
| Damage types | 0..27 (18..27 = DLC 2 hits) | 0..16, DLC 2 hits dropped | TruShadowCombat `[Damage] Translate` ✅ live 07.11. |
| Chunkdoll on lethal impulse | deferred to the Death state | created inside the physics step -> fatal | TruShadowCombat `[Chunk] Translate` (built) |
| Thrall companion instance (T4) + T1/T2/T3 death / regeneration | TU-only code | absent | TruShadowCombat 0.6.5 (companion lookup ✅ live 08.11., object 870; T1-T3 built) |
| T5 immediate death in the hit reaction; Vaulted Enter step chain (P1c) + Vaulted clock | TU-only code | absent | TruShadowCombat 0.6.6 `[Death] TranslateT5` / `TranslateVaulted` / `TranslateVaultedClock` (built) |
| Script notifications 33 / 34 / 38 | sent by enemy states | never sent | TruShadowCombat 0.6.3 / 0.6.5 (33 live 07.11. + 08.11., 34 / 38 built) |
| MeleeAttack end / interrupt (T-M1..T-M3) | changed | retail | TruShadowCombat 0.6.4 / 0.6.5 (built) |
| MeleeSplashDamage (K9), adrenaline in doppelganger mode (K11) | changed | retail | TruShadowCombat `[Splash]`, TruShadowPower `[Adrenaline]` (built) |
| SweepAndPrune pool | create(3000, 500): 3000 boxes, 1000 pair links | create(1000, 200): 1000 boxes, 400 links | TruRockVein 0.10 `[SweepAndPrune] Translate` (built, not yet loaded in the game) |
| Ledge-corner nudge | same box + same segment as the corner partner: t = floor - 0.001 / floor + 1.01 (TU 0x8242eeac) | missing (0x74e5a0 = retail) | TruRockVein 0.11 `[LedgeCorner] Translate` (built, not yet loaded in the game) |
| Brain size | 0x50a0 B; the TU-added block shifts the tail by 0x58 (TU +0x5088 = PC +0x5030) | 0x5040 B | plugins keep TU-only fields in their own tables (TruShadowCombat 0.6.6 clock) |
| Cloth / braid time step (K1) | dt / world time scale for the player | plain dt | TruShadowPower `[Cloth] TuTimeStep` (built, default 0) |
| Camera flag bit 2 on power start | set, never cleared | set / cleared by strike look | TruShadowPower 0.20 `[Look] CameraFlag=1` (built) |
| Doppelganger flag gameTracker+0x1244 | DoppelgangerInit sets it | nobody writes it | TruDlc2Player `TrackerFlag` / `FlagReset` |
| Player extension object 858 | created by TU-only 0x82412ab0 | never created | object search in 0xdb7400 + `[Meter] Fallback` ✅ |
| Costume 857 <-> 11 on save / load / spawn | mapped at 5 sites | saves 857 | TruDlc2Player `[Costume] TuMapping` (built, default 0) |
| Costume reset on mission start | `MainTracker_UILoadLevel` resets | direct `level.load` skips it | TruDlc2Player `CostumeReset` (built) |
| HUD natives larabase f70-f73, type `dlc2data` | present | absent | TruShadowHud + TU HUD generalbank (built) |
| Native type `dlc2data` in scripts | bound | not in the exe -> null call | script stub `script_dlc2_flag_stub.py` ✅ |
| Achievements f16-f20 | Live award | `achievement` has 16 natives (all `ret`) | calls NOPed (`script_missing_native_fix.py`) ✅ |
| GlobalInfo player list | 29 ids (857 included) | 28 | data fix `globalinfo_player_list_fix.py` (K12) |
| Sound groups | 80 (77-79 new) | 77 | TU `globalsoundinfo.drm` installed ✅; TruMenu 0.21.8 group volume sliders (built) |
| Input map set 17 (K8) | 6 extra bindings | missing | data fix `input_map_tu_fix.py` ✅ |
| Chunkdoll limit | 8 | 4 | TruShadowCombat 0.6.7 `[Chunk] Limit8` (built; held back until the 0.6.1 lethal-impulse fix was seen live, 09.11.) |
| Hit structures for DLC 2 melee types 18..27 + knockback per type (K-1) | companion hit records (0x82301dc0, 0x822f77e4) | none / fixed 3.0 | TruShadowCombat 0.6.7 `[Hit] Translate` / `TranslateKnockback` (built) |
| Impulse 0x91 after Lara's contact hit (K-1b) | skipped for targets with `[[inst+0x10]]+4` bit 0x400000 (0x823e1870) | always sent (= retail) -> thrall in Fall on every punch | TruShadowCombat 0.6.8 `[Hit] TranslateImpulseGate` (live 2026-11-09 21:26-21:30, tutorial thrall hall02: gate on -> 3 single punches each MeleeAttack -> Hit -> CombatStepIdle as the Xbox; gate off -> each Fall -> Land -> Getup; flag word 0x044a4000 = bit 0x400000 set, measured). Melee kills with the gate on: 5 live 2026-11-09 21:52-21:54 (tutorial thrall, yeti, 3 vikings) over 0x11c -> death check -> RegenerateDeath -> finisher hit -> death switch kind 7 (`0.6.5 death` / `0.6.6 T5` lines), 0 `0.6.1 chunk ... lethal impulse` lines; the chunkdoll comes from the Death state 0x66c9f9 as in the TU 0x8232ce28 (same tune+0x64 record +0x46 test as the impulse path) - whether it showed is not logged ⬜. Not yet seen: Fall on the big hit types 21 / 23-27 (knockback path, needs K-8), the flag on the Xbox thrall |
| Lara's punch combo (K-8) | state 1004 slot 1 (re-enter) = 0x8245efc8 (machine 1 table 0x82757948): every new combo record clears the player's hit list +0xa4 (unless parameter 0x415) -> hits on 752 / 755 / 754 / 759 / 760 / 762 (TruXenia 09.11.: -20 / -40 / -60 / -130 / -100 / -70) | no slot 1 (retail): the list keeps the target of the first punch, the contact sender 0x719050 drops every later contact of the chain (0x7190ad `call 0x6e6990` = add-if-absent) -> the chart runs 752 > 755 > 754 > 753 (X X X X; 760 needs Y = input 143) but only 752 hits (-20); 09.11. 19:50-21:56: 115 PC hits, none on 755 / 754 / 753 / 759 / 760 / 762, 77 slot-1 lines "list occupied, TU would clear" | TruShadowCombat 0.5.1 `[States] Translate1004` (built 04.11., byte-checked, ON live 05.11. without fault, default 0 - installed 0): **set 1** = the fix; live check ⬜. Chart records 750-765 Xbox = PC (`tools/chart_range_diff.py`), evidence `tools/combo_hitlist_trace.py`, `Befund-K8-Kombo-1011.md` |
| Death switch request (TU 0x823258c8) | retail 0x82327a18 with its helper 0x8230e290 inlined: 0x82349468(brain+0x1254, inst, brain+0x11e0, Death 0x82779bf8, {data, "EnemyDeathSwitchData", 0x20}, 0) | the same request: 0x641650 -> 0x63d6e0 (= 0x8230e290) -> 0x671d30 (= retail 0x82349b90 = TU 0x82349468) on brain+0x1254 | no port (13.4); TruShadowCombat 0.6.9 log points (built, offline): death switch (state before / after, caller), Death-state chunkdoll build 0x66c9f9 (`[Death] Log`), hit-list add 0x7190ad (`[Hit] Log`) - K-8 and "did it shatter" from the log ⬜ |
| Knockback speed of Lara's contact hit (K-8b) | sender 0x823e1488 passes the builder 0x8230afd8 argument 5 / 6 = **(int) A+0x10 / (int) A+0x14** (`fctiwz` 0x823e169c..0x823e16c8) -> msg+0x44 / +0x48; the knockback 0x822f73a8 runs with v = msg+0x44 -> type 21 (753, force 250) / 26 (775, 1250) fall although their record has s+0x30 = 0 | 0 / 0 (= retail 0x823df0d0 / 0x823df0d4; PC `push 0` x 3 at 0x719169, arguments 7 / 6 / 5) -> the knockback 0x620650 ends at 0x62073e for s+0x30 = 0: the 4th chain punch (-80) leaves the thrall in Hit | TruShadowCombat 0.6.10 `[Hit] TranslateHitSpeed` (built, offline; 6-byte jump at 0x719169, `cvttss2si`); the TU's type-27 substitute record `[CM+0xc8]` of the same block (0x823e160c..0x823e1674) not ported; live ⬜. Source `Befund-K8b-Art21-1011.md` |
| TU coverage list (all changed / new functions) | 824 changed + 504 new functions vs retail (12 781 equal; 10.11. similarity pairing inside replaced runs, before 937 / 391 by position) | - | `docs/data/tu_coverage.tsv` from `tools/tu_coverage.py --ref HEAD` (+ `docs/data/tu_coverage_overrides.tsv`): first pass 09.11. ported 145, irrelevant 103, open 1080. **10.11. per changed block** (TU address ranges where TU and retail differ; register / stack / layout / reorder-only blocks listed, not counted): ported 95 (every real block covered), **partial 56** (column `uncovered_blocks`, 156 blocks / 10 956 B; combat 21, player / chart 18), irrelevant 88, open 1089. A plain function start names the function, not a block; PC-address evidence and false mentions only via the override file. Pairing agrees with all 32 "TU x = retail y" plugin statements. Examples: 0x823e1488 partial (gate covered, type-27 attack-data swap 0x823e15a8 open), death switch 0x823258c8 (explained 10.11.: only retail's request helper 0x8230e290 inlined, = PC), event switch 0x8240a430 slot-4 time request open |
| Sound-slot 5th argument | TU 0x8226de00 | retail | ⬜ not ported |
| Main-game bug fixes in the TU | Published list (Eidos via TeamXbox 09.03.2009, Wayback copy read by 17u, not re-fetched 🔶) located in code by 17w: jump targeting = ParabolaVsSegment `fabs(t)` + refine through ParabolaVsPoint (TU 0x823f6b08), moving-target > 500 u/s skip (TU 0x823fa8b0); ledge corner = same-box / same-segment nudge (TU 0x8242ecd8); edge probe = stick direction gated > 0.1 and probed separately (TU 0x82294f90); trigger volumes = sphere fast path / box bounding-sphere reject (TU 0x8228d8c8, same results); Legend cheat poll removed (TU 0x82291c40). PDA-transition crash and heap-leak fixes not found. That these blocks are exactly the listed fixes is inferred (🔶) | jump 500 filter already in PC 1.1 (0x70f6c0); the rest = retail (sections 11, 14, 23) | ledge corner: TruRockVein 0.11 (built 2026-11-08, not loaded); not ported: edge probe ~1 day (0x5d84ad / 0x5d8596), parabola ~1 day (0x6fa855); trigger fast path optional; cheats kept for TruMenu |
| Depth of field | on | complete in the exe, off when the registry value `EnableDepthOfField` is missing or 0 (section 16) | registry (`Set-TruDisplay.ps1 -DepthOfField On`); TruMenu live switch possible with a guard ⬜ |
| Motion blur (per object + camera) | pass 0x10 (0x821c3280, scene list +0x74c) + post-effect object [5] (EndScene 0x821c4fe8, post-fx slot 14) | absent (opaque mask 0x50fa9d writes 0x201 only, no list, no shaders) | ⬜ port (large; shaders are built into the Xbox exe) |

---

## 2. Containers, sections, ids, relocations

Short; the converter side is in [ARCHITECTURE.md](ARCHITECTURE.md) section 3. "From FINDINGS.md" = checked against base-game
Xbox / PC pairs, decompiled code or the running game when that file was written.

| Fact | St | Proof |
|---|---|---|
| DRM = list of typed sections; CDRM = compressed DRM. Xbox big-endian, PC little-endian. Types: 0 / 2 / 7 (DTP) / 8 (script) / 11 (object), 5 texture, 6 wave, 9 shader lib, 10 material, 12 mesh / terrain, 13 map, 100 symbols | ✅ | from FINDINGS.md |
| Internal relocations = pointers inside a section; external = section-index references; `idref`s resolve by (type, id) across the loaded set. Adding / removing sections needs external-reloc remapping; appending is safe only if no reloc targets an index >= the old count | ✅ | from FINDINGS.md |
| One **global texture cache** keyed by id, per-DRM refcount: a material may use a texture from another DRM only while that DRM is resident (else R6025) | ✅ | from FINDINGS.md, `work/crash/B84_r6025/tex_lifetime_check.py` |
| Texture ids in object lists are masked with 0x1fff by 0x52b360 (caller 0x54e89c in the object reload handler 0x54e200): new texture ids must stay < 8192. A garbage count there (DTP 26321 +0xd4 = 0x03000000) masked ~40 MB and wiped FMOD's mixer (crash shows in the WINMM timer thread) | ✅ | `Befund-Ton-und-Abstuerze-0411.md`, fix `objdata_fx_fix.py texcount` |
| Material / shader lib **first loaded copy of an id wins** (hash table, refcount +1 for a second copy, 0x551ec9): every DRM copy of the same id must be byte-identical | ✅ | section 17, gate `gate_stesso_id` |
| **Dead bits**: 16352 unique-id bits; uids >= 16352 are no-ops on set and read as alive. DLC intro uids were shifted by +20000 for 5 uids | ✅ | from FINDINGS.md, INVESTIGATION.md 6 |
| Runtime-spawned instances get intro ids >= 0x40000000 (children inherit the parent's intro) | ✅ | section 5 |
| Word classes (s32 / s16 / raw / id fields) are learned from paired base-game sections; most data bugs in this file are converter word-class errors (u16 pairs swapped as u32, raw bytes swapped, counts remapped as ids) | ✅ | ARCHITECTURE.md 3 |
| **Fault class "learned type-7 table"** (08.11.): every DTP without a same-size base twin takes the generic `convert` route (generic_type0 with the learned type-7 table: class per word from label key + Xbox value shape). Seven unrelated record families came out with the same fault - the right bytes in the wrong order for the field width (u16 pair <-> u32 <-> raw): chunkdoll piece records (13.6), DTP 22497 player tuning (targeter / K9 pair table, 20.1), type-0x3d thrall extension data (13.4), melee records reached only via the +0x1c8 link (13.5), pool generator intro data (10; also our DLC 1 route), costume model u16 arrays + list counts (count remapped like a DTP id, 19), the SoundPlex type-12 DSP kind u16 (18.1), fade-record DTPs of the cine cards (above), uber play-anim words (action kind 2 argument / TRANS +0x28, section 9: 18 words in 7 DLC 2 objects, crash 08.11.; the learned table decides differently per run - the 0811 pipeline copy still has 8 in 4 files), the player data block of `doppelganger_casual` DTP 20212 (+0x294 LT lock time u8 x4 as u32 = no lock-on, +0x25c u16 pair; 10.11., step `playerblock`, row "Player data block" in 13.7). The pipeline fixes them after conversion with typed rules: steps `chunkrec`, `exttuning`, `thrallext`, `meleelink`, `genintro`, `costumedtp`, `dspkind` in `tools/dlc_struct_fixes.py` (after `objid`, before `seqrepeat`), only where the PC word is another byte order of the Xbox word; twins / statechart run before, the `converter_faults_fix` families after and leave these words alone (check: 0 on the 0711 copies). The families of the night 07./08.11. got typed steps too (17n, `tools/typed_family_fix.py`, after `dspkind`, before `seqrepeat`): `fadecard`, `uberanim`, `fxrec`, `sgmesh`, `introtyped`, `leveltwin`, `basecopy` (rows below); each re-derives its rule from the base pairs once per run (`typed_family_fix.py proof`, pinned counts, 0 contradicting words) and changes only words whose PC bytes are another byte order of the Xbox word; on copies of the installed files they find 6986 words, every one = the value tonight's test trees / 17l set (or = B270 where no tree had it) | ✅ | P2 / N8 report 08.11., `tools/dlc_struct_fixes.py` docstring, 17n |
| The **installed** `doppelganger_casual.drm` predates the twins step: 392 words in 34 SoundPlex DTPs (incl. the moan trees) are still in the converter's byte order; a fresh pipeline run fixes them (test tree in progress) | ✅ data | section 18.1, `work/moan_0711` |
| Cutscene command lists: records `{u16 type, u16 frame}{u32 uid}{u16, u8, u8}{u16 msg, u16 par}[extra]`, length = 12 + 4 * (type >> 12) (format A) or 8 + ... (format B, with an initial DTP id); terminator `ffff0000`. Converted as plain u32 words, type / frame swap and the cinematic never gets `Cine_Start` | ✅ | (from FINDINGS.md) |
| Physics records of custom-range grapple rings (tag 0x404): the enable byte at +4 must stay raw | ✅ | (from FINDINGS.md) |
| **Fade-record DTP** (card / flash / key-glow objects: `co_white_flash`, `co_dlc_black_card` 22651, `co_dlc_white_card` 26832, keys, gems, g_pda): +0x04 / +0x08 and +0x44 / +0x48 = {u16 count, u16 0} / pointer to the records at +0x90, 12 B each {u16 from, u16 to}{u16 frames, u16 word2}{u8 r, g, b, a}; PC word classes s16, s16, raw (42 of 42 base records in 14 DTPs). The learned type-7 table broke them in the installed DLC 2 cards: black card 17 / white card 3 words in the wrong byte order (pod fade-in 6400 instead of 25 frames, finale from / to reversed, ghoul record 5 colour `ffff00ff`); B270 is right. Fix test tree `work/endcine_0811` (= B270 md5); pipeline step `fadecard` (17n, `tools/typed_family_fix.py`: header +0x44 + records, base proof 14 DTPs / 42 records / 139 words, 0 contradicting; installed copies 20 words -> md5 = the test tree) | ✅ | 17h-B 08.11. (`work/endcine_0811/fade_layout_scan.py`, `fade_fix.py`), 17n |
| Fault class "learned table" also hits **type-0 Level sections without a same-size base twin**: `dlc_yggdrasil_end` Level (0x1a6710 B vs base 0x1a6810) had 3476 words in the wrong byte order (float records under Level+0xe0 / +0xe4 and across the section, {u16, u8, u8} heads); at the same offset 3472 Xbox words equal the base pair `l7_yggdrasil_end`, whose byte order proves B270 right; the Levels of hall02 / ceremony_room / treasure_room_cine / level2_start equal B270. Pipeline step `leveltwin` (17n): twin = the l7 unit with >= 50 % (and >= 256) of the DLC Level's non-zero Xbox words equal at the same offset, a word gets the twin's PC word only where the Xbox words agree and the PC word is a byte permutation (pointer / id slots and the NavGraph image excluded); base proof: 13 l7 units pairwise, 299 same-offset equal Xbox words, PC words equal in all 299; only `dlc_yggdrasil_end` qualifies (the 0x2a0 Levels have same-size twins), 3472 words; the 4 words with another Xbox value than the twin (+0x148 / +0x168 / +0x178 / +0x188, 17j-b took them with B270 as witness) stay open. Reader of Level+0xe0 / +0xe4 ⬜ | ✅ data / 🔶 route | 17j-b 08.11. (`work/endb270_0811/sec0_judge.py`, `ygg_fix.py`), 17n |
| **Base-id DTPs in DLC copies**: DTP 18577 (Xbox 10994) = environment colour LUT (256-entry ramps / curves, referenced from Level+0x70 -> DTP 20984 +0x2d0); the DLC Xbox payload 0..0x31c0 is byte-identical to the base, so the PC copy must be the PC base copy (installed end / hall02: 843 words s32-swapped; B270 82 wrong). DLC 2 copies of 18577 / 18579 / 18581 / 19289-19291 carry a 36-byte trailer {00010000, ptr, ptr, 9c6f3e84, u32 payload size, 0, ptr -> 0, ptr -> trailer, cafebabe}, absent from all 1057 PC base DRMs and with no `cafebabe` constant in tru.exe -> unread on PC. Pipeline step `basecopy` (17n): a DTP whose Xbox payload equals the base Xbox DTP of the same id (one Xbox base content, PC id from the base id map, one PC base content, payload relocations equal) = the PC base copy, trailer kept; base proof: all 8979 type-7 ids with one Xbox content have one PC content (DTP ids are global, every copy of an id is the same bytes); installed copies 3376 words (18577 end / hall02 843 each, 19397 hall01 844, 4190 cannonball 846) | ✅ / 🔶 trailer unread | `vs_base_pc.py`, `trailer_scan.py`, 17n |
| Unit DTP intro data | intro +0x7c = u32 (s32 on every DLC intro; base: remapped id in 451 / 525 - B270 left it raw, wrong); watervolume (object 7, 0xc0 B) +0x38 / +0x50 = u16 pairs; triggerplane (object 126, 0x50 B) +0x30 / +0x44 = raw bytes; name strings (`MARKUP\|markup_ledge251`, `SIGNALS\|Yggdrasil_END`) raw (installed end had them swapped). Unit DTP root +0xa4 block +0x94: NOT one byte order - `l7_yggdrasil_end` raw (`02000000`), `l7_yggdrasil_hall02` s32 (`00000004` -> `04000000`), so 17j-b's raw word +0x14f04 of the end unit DTP 21218 has no base rule (left open). Pipeline step `introtyped` (17n): +0x7c u32 (base 595 / 595 intros: remapped id or symmetric, never s16 / raw), intro data by (PC object id, block size) with one byte order over the 595 intros of the four l7_yggdrasil units (10 keys, 181 word rules, e.g. objects 7 / 85 / 86 / 126 / 603 / 662 / 705 / 767 / 790 / 794), name strings raw (1167 base words); installed copies 35 words (26 of the 27 17l a-words + 9 more, all = B270); the 0811 pipeline copy 144 (machine_room 109) + DLC 1 34 (dungeon 26, water_wheel 4, pillory 3, caverns_hall 1; = B270 = installed); the installed `dlc2_machine_room` unit DTP (+2 jump-target intros, other layout) is not checked | ✅ data | `unit_dtp.py classes`, `unit_root_block.py`, 17n |
| FX particle record (anchor `bf800000` x3, `c04a468e` x2): word +0x18 never s32 (raw 557 / s16 45); +0x38 with an id at +0x34 always raw - 18091 base records; DTP 22819 (`dlc2_checkpoint` object data, in 13 DRMs) had 3 words wrong. Pipeline step `fxrec` (17n): +0x18 / +0x38 with an Xbox word XX000000 -> raw (base, one copy per id: 4695 records, 60 + 168 such words, all raw); installed copies 49 words (22819 in 13 DRMs + 1 word +0xa4 in each of 10 `doppelganger_casual` DTPs with the anchor (22711 / 22713 / 22718-22721 / 24555 / 24556 / 26086 / 26183), = B270, 17l class d) | ✅ data | `pattern_twins.py`, 17n |
| Streamgroup mesh-list DTP {u32 n, n x {u32 mesh id (idref 12), u32 0, u32 1, u32 k}}: all u32 (80 base DTPs); `dlc2_machine_room_machine_room_all` DTP 25512 had 16 words wrong. Pipeline step `sgmesh` (17n; mesh id words left to the id map; base 84 DTPs, 188 informative words s32, 0 contradicting) | ✅ data | `sg_mesh_list.py`, 17n |
| Symbol evidence: base script 3581 (Xbox 1015, 3 units) prototype / argument names 515 -> 517, 521 -> 523, 522 -> 524 on PC; the B138 calibration maps 333 / 340 / 341; B270 uses 517 in DLC class 24693. B270 also inserts vtable slot 31 in the UI level classes (we keep the Xbox layout, Finding 46) | 🔶 | `base_words.py`, `script_labels.py` |
| **B270 vs installed, all 295 DLC DRMs** (17l, 08.11.): class a (ours wrong, B270 right) 11 349 words + 5 re-spaced model DTPs, b (B270 wrong) 79, c (intended: encoder waves, own shader libs, material translation, B270 vtable slot 31, scriptclash relink, NOPs, record relayout, pack choice, jump-target intros, K8 / K12) 4.65 M, d (unclear) 4 757. Every installed file passes the 12 existing check steps unchanged; B270 fails exttuning (10 words), objrec (8), meleelink (8), genintro (4), seqrepeat (2), intro +0x7c (6) and shifts script init blocks (15). Tonight's test trees fix 4 623 of the a-words; test tree `work/b270cmp_0811/tree` 5 534 more | ✅ data | `work/b270cmp_0811/judge.py`, `typed.py`, `final.py` |
| **Second model copy DTP 24392** (doppelganger_casual + 4 DLC 2 thrall DRMs; Xbox = model 20134 but 1 word; idref'd at +0x0 from DTPs 26764 / 26765 (doppelganger) and 24500 (thralls), no external reloc into it, no object +8): the 75-record list at +0x380 must be re-spaced 36 -> 40 B like 20134 (`model_reclist_fix fix ... 24392 --words` handles it: +304 B -> 221 128 B = B270, reloc check ok; the `reclist` step only walks object +8 models); after re-spacing the list equals our 20134, but 5960 body words after the list are in another byte order than our 20134 (B270 = our 20134 in 5952, = our 24392 in 8) - needs a twin step too; all 5 copies in one step (DTP id resolution across files ⬜) | ✅ data / 🔶 visible effect | `work/merge17m_0811/m24392.py`, `tools/model_reclist_fix.py` |
| `[Level+0x90]` section (type 0) +0x1c idref -> DTP of one family ({u32 n, ptr, ptr, float records}, pointer-delimited blocks): all words u32-swapped - 47 same-size base pairs / 301 268 words, 0 raw (direct twins end 20983 = l7 18548, hall02 23098 = l7 19283). Installed `dlc2_ceremony_room` DTP 25696 has 107 raw words (BE floats left; as BE f32 all 107 plausible, as installed LE f32 only 23; B270 right), machine_room 25390 6 (17l class a). Reader ⬜; 17q: ceremony 25696 set to u32 in `work/q17q_0811/treecer` (DTP == B270 afterwards), machine_room 25390 already in the b270cmp tree copy | ✅ data | 17p / 17q 08.11. (`work/q17p_0811/q3_words.txt`, `q3_level1c_base.txt`) |
| Environment-LUT base copies also in `dlc_yggdrasil_hall01` DTP 19397 (ramp bytes 00 01 02 03 ..., installed s32-swapped, 802 words + 42 also wrong in B270) and `dlc2_uo_goo_cannonball` DTP 4190 (846); rule: the PC base copy (pipeline step `basecopy`, 17n; the 17l common-prefix hit `yeti_thrall*_dlc2_` DTP 17090 +0x80 has no whole-payload base copy and stays open) | ✅ data | `judge.py` basecopy, 17n |
| DLC 2 thrall object data (24424 / 24534 / 24575 / 24888 family): the aligned base twin (`viking_thrall.drm` / `yeti_thrall.drm` object data, difflib, >= 85 % of the words in equal blocks) gives the PC byte order of 3177 differing words (3177 a / 0 b); installed has the converter's s32 default (byte flags XX000000, u16 pairs) | ✅ data | `align_twin.py` |
| dtp_audit structure keys with >= 100 informative base samples all of one byte order: 1184 differing words, B270 right in all (byte flags at +0 swapped as u32, u16 pairs / half floats in the doppelganger mesh DTPs 22493 / 25050, floats left raw in machine_room 25390) | ✅ data | `keystats.py --fp` |
| Particle record (0x17c) offsets +0x40 / +0x68 / +0x7c / +0x88 / +0x11c / +0x14c / +0x174 have no objrec rule (mixed base classes); without a base twin (machine column, goo drips, faulty treadmill blocks) about 800 words stay open - a reader-typed rule by emitter kind is needed - answered by the reader 0x543f70 (next row) | ✅ | `objrec_map.py`, 17o |
| **Particle / FX record reader** 0x543f70 (record = [objdata +0x10] + i * 0x17c at 0x543fc2, the only `imul r, r, 0x17c` in tru.exe; i < u16 [objdata +0x0c]; callers 0x5454e2, 0x547c4f, 0x547ccf, 0x5482b0 next to the effect chain of 17.5): reads +0x40 / +0x90 bytes 0-2, +0x68 / +0x88 bytes 0-1, +0x7c / +0x14c byte 0, +0x11c / +0x174 bytes 0-3 as u8, +0x58 {u8, u8, u16}, +0x5c u16, +0x160 {u16, u16} (field list `work/d17o_0811/p2_fields.txt`). Base check: every read byte in place in all informative samples of 11 032 base records (0 moved); the objrec calibration called these offsets ambiguous only because b2s16 / raw both fit. DLC: 835 class-d words (17l) -> B270 right (= Xbox bytes), 0 for installed (machine_column 386, thrall object data 503 / 492, goo_drips_spawned 94, faulty treadmill blocks 51 / 51). **Live 08.11.:** the goo dripping from the slanted pillar in `dlc_yggdrasil_end` was drawn as grid-like square dot sprites before and as soft glowing blobs after `fxrecread` was applied to the 21 installed DRMs (stack step 11) - confirmed. Pipeline step `fxrecread` (18e, after basecopy): raw +0x40 / +0x68 / +0x7c / +0x88 / +0x90 / +0x11c / +0x12c / +0x14c / +0x174, b2s16 +0x58, s16b2 +0x5c, s16 +0x160 (+0x12c byte 0 added: 21 / 21 base in place); base 471 objects / 11 032 records, contra 0; 0812 DLC 2 3250 words = B270; installed: 829 of the 834 17l d-words; 5 knight_thrall 21046 +0x14c words are no byte order (kept, owner item) | ✅ | 17o, 18e (`work/d17o_0811/p2_fields.py`, `p3_bytes.py`, `tools/typed_family_fix.py`) |
| **Whole-record check by the reader's widths** (2026-11-10, `tools/fx_record_check.py XBOX.drm PC.drm`): every word 0x543f70 reads (dword / u16 / byte per p2_fields) must be the Xbox bytes moved by that width. Installed `dlc_fx_goo_dun_lrg_ist` (12 records), `dlc_fx_goo_column_displace` (1), `_sml` (1), `dlc_fx_goo_tube_end` (6), `dlc2_uo_goo_drips_spawned` (19): **0 mismatches**; counter-check `work/rebuild/dlc2_asm_stage1` `_spawned` (before `fxrecread`): 275 (+0x40 / +0x58 / +0x68 / +0x7c / +0x88 / +0x11c / +0x174 ...). So the end-level steam / haze difference (X24) is not in the particle data | ✅ | workspace `Befund-Dampf-Schleier-1011.md` |
| **Unit DTP pointer-path table** (all 77 base units, 774 257 samples; regions labelled by pointer path, intros paired by object NAME - object ids differ Xbox / PC, e.g. triggerplane 110 / 126 - tiers exact / root+0x1a4 folded by 0x100 / last-step wildcard / size-only, >= 10 votes; leave-one-unit-out false rate 9.3e-6 / 0 / 2.2e-4 / 2.6e-4): root +0x1a4 = 0x100-byte records (+0x34..+0xa0, +0xc0..+0xf4 raw; +0 / +4 / +8 / +0x14 / +0x18 / +0x20 / +0x64 / +0x68 / +0xb0 / +0xb4 s32; 306 records / 35 units, 0 contradictions); intro +0x7c not provable from base (remapped id). DLC unit-DTP class-d words 470 -> 372 B270 right, 0 installed right, 98 open (symmetric base values, DLC-only data, root+4 0xe0 records +0x50 / +0xd4 with 4 non-permutation samples); taken by `introtyped` (18e) with three proven restrictions: votes only from base samples of the word's byte shape (same zero / non-zero mask), size-only tier KZ dropped (it typed DLC 1 float records such as caverns 20872 0x160 c234b9c0 as u16 pairs), KS only for 0x100-multiple regions; LOO K1 3 / 315 349, KS 0 / 19 526, K3 21 / 203 862; installed: 324 of the 372 17o words; 0812 copies: DLC 1 187 words (186 = B270), DLC 2 706 (480 = B270; **226 against B270**: machine_room 25392 / ceremony 25698 0x180 / 0x240 records = rising u16 curves, goo_room 24993 byte runs - B270 keeps the u32 swap there; no reader yet ⬜, owner decision) | ✅ data | `work/d17o_0811/d4_table.py`, `d4_run.txt`, `work/steps18e_0811/scan3_p0812_dlc2.tsv` |
| Rule conflict `dlc_yggdrasil_hall02` 23100 +0x6268: the dtp_audit fp rule says s32 (installed right), the unit-DTP path table (root/+1fc/+50, 0x160-byte record +0xe8: 11 / 11 base units + 40 more 0x160 records under root+0x6c, all s16) says s16 (B270 right) - decide before a tree; `introtyped` (18e) leaves this word alone (TABLE_EXCLUDE) | 🔶 | `work/d17o_0811/d4_words.tsv` |
| `co_dlc_knight_thrall` DTP 21046 (DLC 1): installed = B138 values (no byte order of the Xbox word: 0x28 -> 0x29, colours doubled, 0.3 / 0.4 -> 0), B270 = Xbox in objrec rule order (21 words) - an upstream re-authoring, owner decision | 🔶 | `objrec_map.py`, `final.py` |
| `dlc2_machine_room` unit DTP 25392 +41 760 B (2 intros more) = `jump_target_place.py` (test 50l), not a converter fault | ✅ | `growth.py` |
| Cine command type 0x2001 msg 34 (0x22): par = fade-record index of the target object; fade 0x1000 = invisible, 0 = opaque (ghoul f0 rec 5 / f833 rec 4, pod f0 rec 0, podon, finale, crush); meaning of word2 ⬜ | 🔶 data | `work/endcine_0811/cine_drm_cmp.py` |
| Each translated material gets its own shader lib id (2756-2774, 2775-2781, 2782; 975 / 976 are VS / PS donors copied into streamgroups), because of the first-copy-wins rule below | ✅ | (from FINDINGS.md), [LINEAGE.md](LINEAGE.md) |
| Language variants: `ArchiveFileSystem::FindEntry` 0x4726e0 takes the first record with `(spec & mask) == mask`; English loads `<name>_001` (spec 0xffffffe1) before the base name | ✅ | section 18.5 |
| File system: [0x9ce278] = MultiFS (ctor 0x4737f0, vtable 0x8440ec; list +4 stride 0x28, count +0x57c): RequestRead 0x473600, FileExists 0x472bc0, GetFS 0x473560 (first FS whose FileExists is true; miss -> slot 0), Mount 0x472c50(fs, flag, front); patch.000 mounted at the front (0x478997), BIGFILE.DAT (0x84414c) appended. ArchiveFS vtable 0x843fcc (ctor 0x473420): RequestRead 0x472890 -> FindEntry 0x4726e0 miss ("* Archived file '%s' NOT found *" 0x843f90, log sink) -> fatal 0x596cb0 "Can't open file %s". ModLoader finds 0x472c50 / 0x472b31 / 0x478930 / 0x49a84f by signature (its own layer not read 🔶) | ✅ static | `work/units17s_0811/PROGRESS.md` |

---

## 3. Main loop and global state

| Item | PC | Notes | St |
|---|---|---|---|
| Main state | dword 0xe7ed60, dispatcher 0x5e0090 (jump table 0x5e015c, index state-1) | 1 = in level (GAMELOOP_Process 0x5e0050), 2 = level start / load (0x5de7e0), 9 = outfit / weapon selection, 10 = front end. Level load sets 2 at 0x5de9ca, 1 at 0x5de9f0 | ✅ |
| GameTracker | 0xe7f088 (TU 0x82efb458) | +0xc = 0xe7f094 player instance; +0x2c = 0xe7f0b4 progress bits; +0x38 start unit name; +0xb9 = 0xe7f141 level change pending; +0xbb = 6 / 10 skips unit changes; +0xbc = 0xe7f144 cheatMode; +0xc0 = 0xe7f148 main stream unit id; +0x100 = 0xe7f188 scaled frame dt; +0x118 = 0xe7f1a0 world time scale; +0x138 = 0xe7f1c0 (cinematic test 0x453f00); +0x148 = 0xe7f1d0 timeDilation; +0x16a requireImmediateAdjacentUnitLoad; streamFlags 0xe7f0b8 (0x1000 pause, 0x200000 keep info between loads) | ✅ |
| Player tracker | `[0xfadb58]`, ctor 0x71c2d0 (memset 0x1310, only call 0x722445), published 0x72247b, cleared 0x722304 | +0x500 weapon manager, +0x504 player instance, +0x628 health, +0xa64 jump-target markup box, +0xc94 attached markup box, +0x1244 doppelganger flag, +0x1288 engaged-enemy counter. TU tracker is 0x1320 bytes (memset 0x82413878, global 0x829892b0) | ✅ (+0xa64 / +0xc94 live ⬜) |
| Frame time | unscaled 0xe7f190; scaled 0xe7f188 / 0xe7f194; game clock 0xe7f15c; 64-bit tick clock `[0xecfaec]` / 0xecfaf0 (enemy timers). Frame-time function 0x5da230 (7 callers, one per main-state handler): microsecond clock 0x597f10 (QPC 0x597e90) called at 0x5da247 / paused branch 0x5da684 (`[0xe7f0b4] & 0x10000000`), average of 6 deltas (ring 0xe7ee10), cap 66 666 us (0x5da455), dt = us / 33333.332 (double 0x855280) -> 0xe7f190 / 0xe7f194: **1.0 = 1/30 s** ✅; frame_rate_lock 0xe7f1a8 1..3 = fixed 30 / 20 / 60 fps when `[0xe7f150]` == 0. TruQoL 0.1 FrameLimit waits before both clock calls (built) | tick clock ticks per second ⬜ | ✅ |
| CPU count / > 31-thread start-up crash | 0x4a21d0: GetProcessAffinityMask at 0x4a2238 (IAT 0x83e0a8, only use); process mask != system mask -> 8 at once (0x4a2244, why `/affinity FFFF` helps); loop step 0x4a2455 `shl eax, cl` is modulo 32 -> with bit 31 set the loop never ends and 0x4a235d writes past a 256-byte stack array; called once WinMain 0x479c80 -> 0x47a0bb -> 0x4a28e0 -> 0x4a2904; the main thread is then pinned to CPU 0 (0x47a0c9). TruQoL 0.1 `[Startup] ThreadCap` caps both masks at that call. **Live 08.11. (36-thread PC, no launch option; a 32-bit process sees mask 0xffffffff = 32):** ThreadCap 31 -> the count loop ends (log `CPU count 1 ... -> 0x7fffffff`), but the game then hangs at start with CPU load ("not responding") - a second limit after the count; ThreadCap 8 (masks 0xff, = the count the launch-option path returns) -> starts and plays normally. Bisection live: **8 / 16 / 24 run (menu + DLC 2 load), 25 / 26 / 28 / 31 hang** at the first load; default becomes 8 | ✅ static / ✅ live (<= 24) |
| Cinematic stream clock (08.11., static) | Cutscenes are multiplex streams (animation + sound in one stream object). Per-frame update **0x5901a0** (thiscall, float dt, returns `[obj+0x14]`): first feeds the stream's sound ring 0x5965d0 (call at 0x5901ef; counters entry+0x34 / +0x38 += bytes / 2 at 0x5966f7 / 0x5967af), then in state `[obj+0x18]` = 4 (playing) sets the cutscene time `[obj+0x384]`: with a sound stream `[obj+0x778]` and without capture mode it is the stream's own vslot 0 = 0x5800d0 = **sound position** 0x595dc0 (entry+0x34 minus half the buffer, i.e. the cutscene follows its audio clock); without sound (or capture mode) time += dt x `[0x8439b8]`, clamped to the end, and only while streamFlags 0xe7f0b8 bit 0x1000 (pause) is clear (0x59024a); then 0x5bbfd0(old time, new time, 0, `[obj+0x79c]`) plays everything between the two times. **0xe7f0a4 bit 4 = capture mode:** the frame-time function gives a fixed 1/30 s (0x8235 us at 0x5da3da, `[0xe7f160]` = 33) and the cutscene runs on game time instead of its sound (also tested at 0x457258 and 0x5800e0). streamFlags bit 0x1000 is the general pause: the level update 0x5d4520 skips the instance updates 0x5b3090 / 0x5b3150 and more with it, so it stops the effects too. Other classes: `cdc::CinematicHandlerImpl` vtable 0x8439d0 (7 slots; 0x4561c0 takes the actors, log "Switching to CAMERA_MODE_CINEMATIC_STREAM"), `NtCineSequence` 0x845b50, `CinematicCamera` 0x855c54; "STOPPING old cinematic ... ONLY ONE" 0x58a7d4. **Stream walk:** head `[0xccdc64]`, the update returns the next stream `[obj+0x14]`; the walk runs at 0x5904d0 and inside 0x5954d0 (calls 0x5904e3 / 0x5954f8) - every multiplex stream (music, ambience, cutscenes) goes through it, a cutscene stream has `[obj+0x77c]` = its cinematic handler (its update 0x457960 -> 0x457100 is called from the stream update at 0x59030d). Used by TruMenu 0.22 `cine.pause` (skips the update of the playing cutscene stream; live 08.11.: the scene stands, effects run on, the sound ring then loops). The time `[obj+0x384]` counts 1/30 s (`[0x8439b8]` = 30.0 in both paths). **Sound pause (FMOD, static):** the game's "pause all sound" 0x587420 / resume 0x587460 = System_GetMasterChannelGroup 0x7b99b9 (stdcall system `[0xcc9f80]`, &group) + ChannelGroup_SetPaused 0x7b9490 (stdcall group, paused) -> ChannelGroupI::setPaused 0x7c4875 (flag +0x59, child groups, every channel via ChannelI::setPaused 0x7c9beb = +0x74 bit 0); Channel_SetPaused 0x7b9be0, Channel_Stop 0x7b9bbf; a stream's sound plays through a DSP channel started at 0x5839e0 (System_PlayDSP 0x7b9965 paused, Channel_SetFrequency 0x7b9dee, unpaused; not kept). **Live 08.11.:** the master group holds only plain channels and has no child group - the sound category groups (`[[0xccdea0]+0x24]`, channel group R+0x6c) form their own tree, and ChannelI::setPaused only follows the channel's own chain (+0x8c, parent +0x1c, flag +0x59), so pausing the master group alone left the cutscene line looping; pausing the master group plus each category root holds everything (2 roots in the end room), and the release continues in sync. Live 2026-11-09: the subtitle lines are **not** held by this - they run on during the hold (own clock; found 2026-11-10: row "Subtitle line clock", section 16 - TruMenu 0.22.13 holds it); pad combos fire after 120 ms of a still button set, so LB + View pressed before RB fires "continue" on the way to the photo combo (0.22.13: the two-button combos fire on release) | ✅ static / ✅ live |
| Worker pool / the 24-count limit | 0x4a28e0: workers = CPU count - 1 (or `[0x890708]` when >= 0), flag 0xa03a88; pool 0x4a2680(n): n -> `[0xa04290]`, semaphore / event 0xa039e8 / 0xa039ec (CreateSemaphore max 0x7fffffff), critical section 0xa03a70, n threads `_beginthreadex(0x4a1ed0)` handles at 0xa039f0[i] (room for 32 before the critical section); worker 0x4a1ed0: WaitForSingleObject(0xa039ec) at 0x4a1ee8, stop byte 0xa04294, job ring 0xa042b0 (128 x 0x1f8, head 0xa13eb0 / tail 0xa13eb4, `& 0x7f`), runs the job via 0x4a1d70. **Hang with ThreadCap 25 (cdb -pv, 08.11. 18:51):** main thread in the file-system wait `while (fs vf+0x18 busy) fs vf+0x1c` (0x4741a0, MultiFS check 0x472bc0 loop over the mounted FS); `[0xa04290]` = 24 workers created but only **20** alive, all idle at 0x4a1eee - 4 workers gone. Suspicion (unproven): a structure used per worker holds 23 entries, or a worker dies inside a load job, so a request never completes and the main thread waits forever. Find the per-worker table / the exit path ⬜ (not pursued: more workers bring nothing). **Load time live (08.11. 19:13-19:21, TruTrace `level: REQUEST` -> `stream unit slot ... state 2`):** dlc2_ceremony_room 2.06 s with ThreadCap 8, 2.0 s with 24, 2.13 s with 24 and no frame limit; dlc_yggdrasil_end 7.35 / 7.3 / 7.29 s; back in play (main state `[0xe7ed60]` 1 again) about 40 s / 28 s in all three runs - the worker count and the 60 fps limit change neither the unit load nor the time after it | ✅ static + live dump / 🔶 cause / ✅ live load time |
| Start-up order / ASI load | CRT 0x818241 -> GetStartupInfoA 0x818255 -> WinMain call 0x8183b3 -> 0x47a280 -> 0x479c80. `binkw32.dll` in the game folder = Ultimate ASI Loader (not ModLoader, which is itself a plugin): `dontloadfromdllmain` default 1 -> IAT hook (incl. GetStartupInfoA) -> plugins load at that first call, i.e. **before WinMain** | ✅ static (live: TruQoL.log ThreadCap line ⬜) |
| Time scale | ramps player 0x8abe94, world 0x8abeb4; current player 0xe7f1d4, world 0xe7f1a0; SetWorldTimeScale 0x776030, SetPlayerTimeScale 0x776090, called by the `gamebase` natives 23 / 24 = 0x797cf0 / 0x797d10 (binder 0x7b44a0; TU 0x824a3238 / 0x824a32f0 write request slot 6 in doppelganger mode, section 20.2) | used by shadow-power slow motion; TruShadowPower 0.21 hooks the natives | ✅ |
| Lara health / time scale reads | Lara LP = `[[0xfadb58]+0x628]` (GetHealth 0x6e7860 `mov eax,[0xfadb58]; test; je; fld [eax+0x628]`); the setters read the current value at 0x776052 (`[0xe7f1a0]`, world) / 0x7760b2 (`[0xe7f1d4]`, player); both are stdcall (float target, float seconds), ret 8, prologue `51 a1 5cf1e700 db05 5cf1e700 85c0` (TruMenu 0.22.11 counts their calls through a byte-checked 6-byte jump; TruShadowPower's selector calls them too). TruShadowPower's meter API (`TruShadowPowerMeterApi`, +0x14 `float (*)[2]`) = the TU meter +0x40: 7 request slots {player, world}, empty -1, the selector takes the highest occupied slot (TruShadowPower 0.20 fills 0 / 4 / 5) | fight.trace columns `time_scale`, `pc_player_time_scale`, `pc_ts_*`, `pc_ramp_last` | ✅ |
| Fatal error | 0x596cb0(fmt, ...): vsnprintf -> 0x478b00: hides the window in full screen ([0x890390]), 0x47b4c0 ClipCursor(0) + DialogBoxParamW(0, template 0x7d, hwnd, 0x47b180) = modal error box (the process stays alive while it is open - live); after OK 0x478a10: main thread shutdown (0x5237d0, 0x587030, 0x482540), DestroyWindow, ExitProcess(0) (0x478aec); other threads SuspendThread(main) + TerminateProcess(-1) | e.g. "ChunkDoll: failed to create geom", "Can't open file %s" (0x843fb4) | ✅ static (box live, exit after OK ⬜ live) |
| Log sink | 0x6457a0 = bare `ret` (1455 callers): all channel logs and `dev.*` stubs end here | see section 23 | ✅ |

Sources: `Befund-TruShadowPower-016-0611.md`, `Befund-Unit-Streaming-0611.md`, `Befund-Exe-Stellen-K8-K14-0611.md`,
[TruMenu README](../src/asi/TruMenu/README.md).

---

## 4. Units, streaming, portals, level load

### 4.1 Stream unit table and unit DRM

| Item | Layout | St |
|---|---|---|
| Stream unit table (StreamTracker.StreamList) | 0xdbab40, 32 x 0xd8. +0 s32 unit id, +4 u8 state (0 free, 1 loading, 2 loaded, 4 dumping), +5 overlay, +6 u16 flags (1 resident: parked at (32000, 32000, -32000), never connected; 8 WaitForUnit reload; 0x40 FinishLoad; 0x80 became main; 0x800 main at finish), +8 Level*, +0xc name[128], +0x8c load object, +0xa8 needed stamp, +0xd4 overlay parent | ✅ |
| Lookups | by id 0x5c1b50 (state 2 only, no null check), by name 0x5c1b90 | ✅ |
| Unit DRM | section 0 = Level. Level+0 Terrain (+8 / +0xc TerrainGroups 0x50 B, +0x10 current group); Level+8 / +0xc classic markup list; +0x2c flags (0 in all DLC units); +0x34 render terrain list (from +0x94, idref type 12); +0x60 NavPower image; +0x68 3D NavPower image; +0x70 environment block (fog, underwater, LUTs, ambience; +0x294 u16 default costume object); +0x74 unit DTP (intros +0xc / +0x10, 0x90 B each; markup2 +0x2c / +0x30; portal records +0x98 / +0x9c, 0x40 B); +0x80 origin | ✅ |
| Portal record (Terrain +2 count, +4 array, 0x100 B) | +0 name, +0x82 own id, +0x84 destination unit, +0x90 / +0xa0 box, +0xb0..+0xe0 quad, +0xf0 normal | ✅ |
| Unit list | `tr8/pc-w/unitlist.txt`, 119 units (l1..l7 = 23 / 16 / 9 / 11 / 6 / 6 / 13, DLC 1 = 12, DLC 2 = 11, other DLC starts 4). Chapter titles are not in it (they come from script 72, section 8.2); TruMenu `kUnits` groups them by chapter. `dlc_level1_left` / `dlc_level1_right` are listed (also on the Xbox) but have no DRM; the installed mods tree is flat (`mods\<unit>.drm`) and also lacks `dlc_level3_start` .. `dlc_level6_start` (in no archive, 17p / 17s ✅); TruMenu 0.21.9 `UnitDrmScan` greys out DLC 1 / 2 units without a DRM, 0.21.10 also the slots 3 - 6. Checkpoint intro +0x52 counts up along the path in hall02 / end (24465 ...); `dlc2_machine_room` has 4465 ... (converter? 🔶) | ✅ |
| Units without a DRM | `dlc_level3_start` .. `dlc_level6_start` and `dlc_level1_left` / `_right` exist in no archive (PC bigfile / patch, Xbox layer1 / layer2 / TU, packs 10 / 11 / 1 / 2 / 20; positive control: level1 / level2_start found); named only in the unit lists, `objlist.dat`, generalbank script 104 (DLC mission screen: f7 / f10 check `dlc_levelN_start.drm` with `dlcsystem` f1, f8 / f9 start the slot via `uigamedata` f27) and script 6 -> 4 unused retail DLC slots (never built 🔶). 17s: positive controls in every source (pc-w / xenon-w l1_seatop, dlc_level1 / 2_start, dlc_levelN_preview.raw), plain search through every record (25.2 GB) + installed mods, B270 kit, tru.exe (no `dlc_level` string), Xbox exes; placeholders only: `image\dlc_level3..6_preview.raw` (64 x 36 "M 3".."M 6"), locals 452-455 "DLC Mission 3..6" / 458-461 "Unavailable" / 464 "ERROR : Cannot find selected DLC level pack."; script 104 f7 adds a slot (uimenu f25) only if `dlcsystem` f1 finds its DRM -> 3-6 never listed | ✅ (`work/q17p_0811/q4_names.txt`, `dis_script104.txt`, `work/units17s_0811/PROGRESS.md`) |

### 4.2 Unit change and level load (state flow)

1. `SIGNAL_CollideInstanceListWithSignals` 0x5d2e50 sweeps old pos (+0xc0) -> new pos (+0x20); only signals of the instance's current unit (+0xe0) count.
2. `SIGNAL_HandleStreamLevel` 0x5d2aa0 ("Hit stream portal in %s to %s"): target = portal +0x84; if the target is not loaded and the instance is the player it busy-waits `Sleep(5)` (hangs forever if the target is in no slot).
3. Game loop 0x5dfc88 compares `[0xe7f148]` with player +0xe0 -> `INSTANCE_Post(player, 0x39)` -> `STREAM_MoveIntoNewStreamUnit` 0x5c1bf0, which tells `TRScriptUnitManager` 0xa13eec (vtable 0x860160, at 0x4b01e0) and calls `STREAM_LevelLoadAndInit` 0x5d30d0.
4. LevelLoadAndInit: MarkUnitNeeded 0x5c1d20, DumpAllUnitsNotNeeded 0x5d1a10 (no player exception), RelocateWorld 0x5cbe90 by -P, RelocateUnit 0x5d10d0, LevelLoadAdjacentUnits 0x5d2940 (portal records, flag byte +0xb bit 0 = auto-load).
5. `STREAM_LoadLevel` 0x5d23f0(name, portal, flag): portal NULL = main load (sets GameTracker+0x38, `[0xe7f148]` = -1); no free slot -> returns entry 31 without loading.
6. FinishLoad 0x5d1cd0 subtracts Level+0x80 from intro positions -> ConnectStreamToStream 0x5d13e0 (relocates only against the main unit; offset = portal +0x90 difference; SceneLayer::HookPortal 0x5cf070).

| Item | PC | St |
|---|---|---|
| Level change request | `GAMELOOP_RequestLevelChangeByName` 0x5df8c0 (cdecl name, gameTracker, doneType 4); ignored while +0xb9 is set; in main state 9 it hangs the game (TruMenu refuses) | ✅ |
| Mission start (generalbank script 104) | `uigamedata` f22 = 0x4a0f10 (byte 0xa039b8 = 1), f27 = 0x77e170 (selection byte 0xfae8d9), 0x5dfb20 copies the unit name -> RequestLevelChange or main state 2; `stdscreenmgr` f19 / f7 = 0x4be5e0 / 0x4be580 | ✅ static |
| Xbox mission start | always `MainTracker_UILoadLevel` 0x8247d818, which also resets the chosen costume (section 19) | ✅ |
| Reload after death | 0x5de480: `SAVE_RestoreGame(0)` at 0x5de537 -> `STREAM_LevelLoadAndInit` at 0x5de6a8 -> wait loop 0x5de6c1..0x5de6f2 (>= 3000 ms + loader busy 0x5c1da0 / `[0x9de714]`, does not wait for unrequested objects) -> player spawn 0x5d40c0 | ✅ |
| Timings (TruTrace) | portal hop ~0.04 s, hall02 load 1.15 s, `level.load` ~9.5 s | ✅ live |
| DLC 2 portal graph | `dlc_level2_start` 91 -> `dlc_yggdrasil_hall01` 108 -> `hall02` 107 -> `dlc_yggdrasil_end` 106; `dlc2_*` rooms 112-118 are a separate ring (only `level.load`) | ✅ (`tools/stream_unit_graph.py`) |
| WarpTo PC partner | 0x4a4140 | 🔶 |
| SetCurrentStreamUnitID 0x5b3a20 | crashes on an unloaded id | ✅ |
| Load of a unit without data | `STREAM_LoadLevel` 0x5d23f0 has no exists test (only `STREAM_LoadOverlayUnit` 0x5d2610, "%s does not exist" 0x8548a0); path %s%s.drm -> request 0x551470 -> MultiFS miss -> slot 0 -> fatal box "Can't open file pc-w\<unit>.drm", then the game exits; no menu fallback. TruMenu 0.21.10 refuses (`level.load` / `level.start`) | ✅ static / ⬜ live |
| Load entry 0x5dded0 | (unit name, GameTracker): dumps the units (0x5c1410), waits for the loader, `STREAM_LevelLoadAndInit` at 0x5de025; callers 0x5de2c1 (state 2 via 0x5de2b0) and 0x5de9a0 (`uigamedata` native thunk 0x7a0d94 -> 0x77bd70) | ✅ |
| TU dialog accept (`ScriptDialogYesNo::RegisterAcceptChanges`) | TU 0x8247f2d4..0x8247f510: "Attempting to load level: %s" (0x820760d8); names in the table at 0x820760f8 (dlc_level2..6_start) -> `MainTracker_UILoadLevel` 0x8247d818(name, 0, 0, 1) (no outfit selection), else (name, 1, 0, 1); the PC has no such strings | ✅ static |

### 4.3 Coordinates and scale

| Fact | St |
|---|---|
| live position = data - Level+0x80 + P; P = 0 for Lara's unit, the portal difference for a neighbour (memory dump) | ✅ |
| `tools/unit_intro_names.py --live` / `--near X,Y,Z,R` prints intros in live coordinates (Level+0x80 from the file); checked 2026-11-10: `dlc_yggdrasil_end` Level+0x80 = (-1511.9, -2620.9, 124.1), checkpoint 9970 live (-2898.0, -4542.7, 8597.2) = Lara's respawn in TruFight.log (-2898, -4543, 8584) | ✅ |
| Scale **~290 units per metre** (280..310; Lara's bind mesh 511 units). Older docs saying "100 = 1 m" are wrong by ~3x | 🔶 |
| Instance +0x20 is at Lara's feet; trigger test point = +0x20 + (0, 0, 200) | ✅ |

Plugins: TruMenu `level.load`, `level.start`, `unit.go` (portal or level load), `pos.goload`. No hop-by-hop unit chain built.
Sources: `Befund-Unit-Streaming-0611.md`, `Befund-Position-und-Schrotflinte.md`, `Befund-Markup-Massstab-0611.md`,
`Befund-Absturz-Neuladen-0711.md`, `Befund-Direktstart.md`.

---

## 5. Objects and instances

### 5.1 Object tracker and object data

| Item | Layout | St |
|---|---|---|
| Object tracker table | **0xdb7400**, 0xcc entries x 0x24: +8 Object*, +0xc u16 id, +0xe state (0 / 1 / 2 = loaded). Lookup 0x54e930, entry by id 0x5c1730, list dump 0x5c14b0. Xbox twin 0x82979280, same layout (an old "4-byte entries" claim is refuted) | ✅ |
| Object names | `[0xdb94d0]` (+0 count, name of id n at +n*8); name -> id 0x5bf770 (TU 0x822809e0); costume / object validator 0x5c54e0 | ✅ |
| Object load (0x54e200) | Object +0x38 u16 anim count <- object DTP +0x5c (0x54e24f), +0x3a <- DTP +0xa0, +0x3c <- DTP +0x54, +0x58 = DTP +0x60 (anim list, 0x24 B per anim), +0x5c = [DTP +0xc8] (0x54e671 / 0x54e677) | ✅ dump 08.11. |
| Object | +0x5c data pointer, +0x60 name / set pointer (README 0.6.5: name at 0x5bf0fb); u16 **object data type** at data+2; child id list `[[obj]+0x2c]` (u16, 0-terminated) | ✅ (+0x5c as data pointer on PC: 🔶 per `Befund-Schattenkraft.md`) |
| GlobalInfo | `[0xe7ee50]`: +4 player list {u16 count, u16* ids} (PC 28 ids 8..35, TU 29 incl. 857), +0x1c input map list | ✅ |

**Object data types seen** (u16 at data+2):

| Type | Meaning | Objects | St |
|---|---|---|---|
| 0x3b | chunkdoll (dismemberment pieces) | e.g. 1007, viking / yeti chunkdolls | ✅ |
| 0x3c (60) | "extra data / spawn extra data": player extension | 858 `player_tru_dlc2_extension` | ✅ |
| 0x3d | thrall companion extension (TU T4) | only 870 / 932 / 944 in all 295 DRMs | ✅ |
| enemy data | magic 0xdaf00018 at `[inst+0x50]` | 27 objects (`tools/enemy_data_scan.py`) | ✅ |

### 5.2 Instances

| Item | PC | St |
|---|---|---|
| Instance list | `[0xd98d54]`, next = +8 (writer 0x5b2ec6, walk 0x5d467d); second list `[0xdbc6c8]`; allocation counter `[0xd98d58]`; instance count `[0xd98d50]`, budget 0x3fc | ✅ |
| Instance fields | +0x10 Object; +0x14 iflags (0x800 hidden, 0x200 drawn this frame, 0x20 kill); +0x20 position; +0x30 rotation; +0x44 allocation stamp (0 after removal); +0x50 object data; +0x58 intro id; +0x60 script object (members at `[[inst+0x60]+0xc]`); +0x64 scene entity; +0x90 bone matrices (0x40 B); +0xc0 old position; +0xe0 current stream unit; +0x100 intro record; +0x110 process function, called (inst, gameTracker) by the instance process loop 0x5b6dc0 at 0x5b6f3f (from the game loop 0x5dfdbe); +0x120 message handler; +0x218 / +0x21c first child / sibling; +0x23c / +0x240 no-draw masks; +0x244 drawable (vtable 0x853abc); +0x248 sound list; +0x274 physics body; +0x2d0 extra data (enemy brain = `[[inst+0x2d0]]+0x2ec`) | ✅ |
| Intro record (0x90 B) | +0 rotation (z = yaw), +0x10 position, +0x40 scale, +0x50 object id, +0x58 unique id, +0x78 intro data pointer | ✅ |
| Intro +0x52 (u16) | editor intro number (name suffix), copied to instance +0x40 at birth (0x5bcd67, 0x5caa2d, 0x5bb84d); the readers next to the object name only feed the log sink ("INSTANCE_IntroduceSavedInstanceWithIntro %s:%s%d", 0x853c74); values PC = Xbox in all DLC 2 units and base l7 pairs (machine_room checkpoints 4465.. = Xbox, not a converter fault). Checkpoint placement 0x5d40c0 matches game block +0x90 against intro **+0x58** (loop 0x5d4243), not +0x52 | ✅ data / 🔶 meaning of +0x52 |
| `INSTANCE_Post` 0x5b3750 (inst, msg, data) | 7 hide / unhide, 12 flight, 3 / 4 die, 0x39 unit change, 35 weapons after a costume switch | ✅ |
| Birth / removal | `INSTANCE_BirthObjectNoParent` 0x5bd0f0; create child instance 0x5bd270 (TU 0x82272998); `ReallyRemoveInstance` 0x5bc4e0 (sends no death event) | ✅ |
| Children | child id list of the object (above) is how the TU finds companion / extension objects; instance child links +0x218 / +0x21c | ✅ |

Sources: `Befund-Schattenkraft.md`, `Befund-P1d-Begleiter-0711.md`, `Befund-Absturz-Neuladen-0711.md`,
`Befund-TruMenu-0214-0711.md`, `Befund-Arachnophobie-Stufe1-Kamera-0611.md`.

---

## 6. Saves, checkpoints, stickies

### 6.1 What is saved and what is not

| Saved | Not saved |
|---|---|
| Units, instances (by save class), the game block (unit, checkpoint, play time, chapter, costume), stickies, dead bits | **Script members** of instances (e.g. thrall script 22813 member +8). The member descriptor has no "save" flag: only `stickyint` (script 68) / `stickybool` (69) members persist |
| Enemy extra: 16 B {4, parent generator intro (enemy +0x4c4c; TU +0x4c9c), +0x16c, bit 23 of +0x14} | Generator OnSpawn on restore; script OnRestore |
| Generator spawn counter +0x80 and expected children +0x7c (message 0x23 -> 0x78179f) | Inventory / unlocks / achievements: location ⬜ |

Correction: "brain+8 not saved" in older notes means the **thrall script member +8**, not enemy brain+8 (brain+8 is the
AI gate field, section 13). Both PC and TU behave the same: ✅ (`Befund-Hall02-TU-Vergleich-0711.md`).

### 6.2 Save code (PC = TU, paired)

| Step | PC | TU | St |
|---|---|---|---|
| SaveInfo | 0x140000 B; main `[0xc5925c]`, buffer `[0xc59264]` = block 6 (0x41028 B), used end +0x1357f4 | | ✅ |
| `SAVE_GetSavedBlock` | 0x556310 (savedID < 7, head `id | (size>>2)<<8`) | | ✅ |
| Block types | 1 unit, 2 instance extra, 3 instance with intro, 4 saved instance, 5 small instance, 6 game block | | ✅ |
| Save order | 0x5568d0: instances 0x556680 -> units 0x5563d0 -> `SAVE_Stickies` 0x555820 | | ✅ |
| Classifier `SAVE_SaveableInstance` | 0x556020 (spawned intro >= 0x40000000 -> kind 1 -> block 3) | 0x821fd618 | ✅ |
| Dispatcher `SAVE_Instance` | 0x556680 | 0x821fe138 | ✅ |
| Writer "instance with intro" | 0x555370 | 0x821fd760 | ✅ |
| Enemy extra (query 0x17) | 0x632674 -> 0x60f7a0; restore 0x625200 | 0x82308f74 | ✅ |
| Restore list / kind 3 / others | 0x555640 / 0x5bb160 / 0x5bb640 | 0x821fdab8 / 0x82273fd0 / 0x822743f8 | ✅ |
| `SAVE_RestoreGame` | 0x556e90 (TruTrace hooks 0x557130 / `SAVE_SaveGame` 0x5570f0) | 0x821ff1e0 | ✅ |
| Kind-3 restore | rebuilds the instance, sends message 0x23 (with extra), then 0x2a | same | ✅ |
| Dead bits | +0x1357f8, 0x7fc B (set 0x5559a0, test 0x555a10, mark 0x555a80) | | ✅ |

**Game block**: +0x0a version 0x0c2c; +0x10 unit name; +0x90 checkpoint id (writer 0x555c20, restore 0x556f38 / 0x556f83);
+0x114 alternative checkpoint (used when word +0x1f4 != 0); +0x1a0 play time (s); +0x1f2 chapter; +0x20c / +0x20e /
+0x210 chosen costume words (section 19); +0x424 + 20n chapter table. Other ranges ⬜.

**Checkpoints**: active checkpoint read at 0x5d41df / 0x5d4214 by the player placement 0x5d40c0. Saving is triggered by
message 0x196 from the checkpoint script 🔶. Base script 3482 (checkpoint) +4 = sticky key 5736. Manor list:
`Manor-Checkpoints-0611.md`. Whether "Load last checkpoint" from the pause menu uses 0x5de480: ⬜.

### 6.3 Sticky store

| Item | PC | St |
|---|---|---|
| StickyManager | impl `[0xa13f18]` (created 0x4b1440 from 0x5defa2), outer `[0xa13f1c]` | ✅ |
| Stores | int `[impl+0]` cap 0x200; bool `[impl+4]` cap 0x1000 (bits); float `[impl+8]` cap 0x80. Overflow text "maximum number of stickies" 0x847410 | ✅ |
| Finder entry (12 B) | {u32 owner, u16 key Symbol, u8 kind, pad, u32 watcher}; `StickyFinder::Find` 0x4aee30 (linear, appends missing ids); CopyIDs 0x4abfd0, restore 0x4aef10 | ✅ |
| Owner kinds | 0 intro unique id; 1 unit (id meaning ⬜); 2 global script object (`u16 hdr+8 | u16 hdr+0x4e << 16`, e.g. GameGlobals 0x012500ba) | ✅ |
| Accessors | bool get 0x4b08a0 / 0x7b35a0, set 0x4b0900 / 0x7b3520; int 0x4b1770 / 0x4b17c0; float 0x4b1820 / 0x4b1870; watchers 0x4af6d0 / 0x4af740 / 0x4af7b0 | ✅ |
| Key | first word of the sticky member's init block; ids grow in creation order and are not reset by a new game 🔶 | ✅ |
| Save tail | int ids +0x13e9f8 / values +0x13e1f8; bool ids +0x1361f4 / bits +0x135ff4; float ids +0x13fbfc / values +0x13f9fc | ✅ |

Known keys: 0:4086 10814 `IsLevelZeroDone`, 10817 `IsL3_Reset_OK`; GameGlobals 195 "reached level", 216; key 5968
cinematic played (2 = playing, 1 = done 🔶); hall02 dispatcher keys in section 8.1.
Tools / plugins: `tools/trusave_diff.py` (show / diff / get), `tools/saves_lib.py`; TruMenu `sticky.set` (writes, then
calls watcher 0x4af740). Sources: `Befund-Saves-Sticky-0611.md`, `Befund-Hall02-TU-Vergleich-0711.md`,
`Befund-TruMenu-Trigger-0611.md`. Notes about "Hold clears settings" belong to another project, **not** to this game's saves.

---

## 7. Scripts

### 7.1 Script VM (object scripts)

| Item | PC | Xbox | St |
|---|---|---|---|
| Interpreter | `FUN_0057ce50`, loop / fetch 0x57ce95, jump table 0x57e52c (index opcode-1), 133 cases | 0x82223398, same structure | ✅ |
| Code word | `opcode<<24 | operand` | | ✅ |
| Native call op65 | 0x57de34; pops object + argument slots, pushes nothing; results via pointer arguments | | ✅ |
| Null native | call through null pointer at 0x57dea3 / 0x57deae = an unbound native type | | ✅ |
| Script manager | `[0xcc4f5c]`; `ScriptObject` +8 type, +0xc instance data; `CallFunction` 0x57b380 | | 🔶 (external menu-hook source) |
Opcodes (✅): op00 nop / line marker (patch hook point); op01 pop; op02 / op05 push word (op05 relocated pointer);
op03 push s24; op04 push byte; op06 / 07 / 08 / 0a push local u8 / u16 / u32; op09 address of local; op0c / 0d / 0e / 10
push member; op0f address of member; op14 `[R+0xc]` + offset (null-safe, 0x57d040..0x57d066); op2e / op2f store byte /
u32 (op2f skips address 0); op31 string assign; op43..op46 compares; op4f strcmp; op50 / 51 / 52 NOT / AND / OR (table
0x57e62c); op63 jump; op64 jump if 0; op65 native; op68 own function; op6b wait-style call; op7b return; op7d set state
and leave (0x57e50d); op7e cast along `[R+8]` (0x57e720); op80 wait N s (0x57e27e). Disassembler: `tools/script_dis.py`.

**Script section layout** (proven on 17039 Xbox / PC pairs, `tools/script_conv.py`): root +0x08 name, +0x0c native package,
+0x10 native name, +0x14 self id, +0x18 super id, +0x20 states, +0x2c members, +0x30 start function, +0x34 prototypes,
+0x38 functions, +0x3c vtable size, +0x44 vtable. Member 20 B {DataType 12, u16 offset, name, init}; prototype 28 B
{script, flags, callType, u16 vtIndex, name, args, ret}; function 28 B; SArray count at ptr-4. ✅
Port hazards: PC `uiscreen` (93) has 32 vtable slots vs 31 (`script_vtable_insert.py`); swapped u16 halves in counts;
garbage member init blocks (`script_init_from_pc.py`); **base-class clash**: a DLC rebuild of base 8453 as 152 B
against resident 12433 (3300 B) crashed the unload at 0x5976a3 (`script_base_clash_fix.py`, new id 26884). ✅

### 7.2 Natives

| Native / type | PC | Notes | St |
|---|---|---|---|
| `dlc2data` (script 21239) | **not in the exe** | TU-only; f0 = byte gameTracker+0x1244, f1 = hint-box byte (only TU reader: Guide pause listener 0x8248cea8). Scripts: `script_dlc2_flag_stub.py`; HUD: TruShadowHud registers the type (section 20.3) | ✅ |
| `achievement` (script 66) | binder 0x7abb80, all 16 natives = 0x796620 (`jmp 0x6457a0`) | TU has 21 (binder 0x8249e990, f16-f20 award DLC achievements 47 / 54 / 55 / 56 / 57); DLC calls NOPed | ✅ |
| `dlcsystem` | f0 = 0x54dc20 (always false); f1 -> 0x776cd0 -> FS 0x472b50 method +8 (file exists) | f1 drives the outfit offer (section 19). Sources write the f1 stub as `tru+0x7973c0`: probably VA 0x7973c0 ⬜ | ✅ |
| `uigamedata` f34 | 0x7a0e10 (binder 0x7af0c0) | unit name | ✅ |
| `corebase` | f7 print 0x795e30, f14 0x795f30 | | ✅ |
| `larabase` | binder 0x7b5490, 70 natives (0..0x45); f36 = 0x79a290 -> 0x777dc0 reads gameTracker+0x1244 | TU adds f70-f73 (section 20.3) | ✅ |
| `instanceref` | f6 wait until birthed, f7 bind, f9 / f15 set / get sticky bool of another intro; `InstanceRef::Birth` 0x4ac0d0 | | 🔶 (2007 map) / ✅ Birth |
| Music stop | 0x4aa490 (`push 0` -> 0x594320) = TU 0x824ae8c8 | relink only, no port needed | ✅ |
| Group fade | native 0x79c6b0 -> 0x4aa7b0 -> 0x587770 | | ✅ |
| DLC script offsets +0x214..+0x284 | past the PC function table | `tools/native_types_check.py`; `dlc2data` is the only nameless native type | ✅ |

### 7.3 Script unit manager, events, notifications

| Item | PC | TU | St |
|---|---|---|---|
| `TRScriptUnitManager` | 0xa13eec, vtable 0x860160, unit list `[0xa13ef0]` | | ✅ |
| Instance event sender | 0x799390 (vtIndex in `[0x105b864]`, binder 0x7b5174); only caller 0x4b0850: instance, then every script unit | | ✅ |
| Who sends the death event (vt31) | Death Enter 0x66c500 (via 0x66c310), LandDeath 0x66ccf0, DrownDeath 0x66d890, DeferredInstantDie 0x652630, 0x624c60, 0x6d3080. **Not**: Despawn 0x61cda0, ReallyRemoveInstance 0x5bc4e0, RegenerateDeath | | ✅ |
| `PlayNotification` | **0x77a540** (`ret 4`, this `[0xfae880]`); loops the stream table from 0xdbac08 (state 2), unit event vt23 via `[0x105b8e0]`, sender 0x79d650 | 0x8247b0f0, this `[0x829ca684]` | ✅ |
| Script message 0x20 -> PlayNotification | 0x768a20 (call 0x768a39 = the only native PC caller) | 0x82473928; the TU drops a repeat of the last id (+0x4f0), PC does not ⬜ | ✅ |
| Instance message switch | 0x5b6ba0 (needs inst+0x280): index msg-3 (3..0x23), byte map 0x5b6d98, targets 0x5b6d74, default 0x5b6d43; msg 34 (cine fade) is not handled there, its reader is not found ⬜ | | ✅ static |

**Notification ids** (receiver in DLC 2: level script 23101 f3 "OnNotification"):

| Id | Sent by (TU) | Effect in hall02 | PC port | St |
|---|---|---|---|---|
| 25, 26, 35, 36, 37 | player moves (which ones ⬜) | 25 + one of 26 / 35-37 closes `hint_08` -> tutorial stage 2 | none needed? ⬜ | 🔶 |
| 27 / 28 / 30 / 31 / 32 | player moves | close hint_18 / hint_09 / hint_10 / hint_11 / hint_12 | | 🔶 |
| 29 | ? | closes hint_17 | | ⬜ |
| **33** | Land slot 9 (T2) / death check (T3): lethal hit on a regenerating enemy | shows `hint_17` (finisher hint) once | TruShadowCombat 0.6.3 `[Death] TranslateNotify33` (call at 0x6203fb) ✅ live (07.11.; 08.11. with 0.6.5: hint shown, thrall then chunk-killed, nothing stuck) | ✅ |
| **34** | RegenerateDeath Exit (slot 12, TU 0x8235e338) on every exit | closes hint_17 | `[Death] TranslateNotify34` (vtable 0x85b104), built; not yet triggered live (08.11.: no thrall lay in RegenerateDeath) | ✅ static |
| **38** | RegenerateDeath / Regenerate slot 10 (TU 0x8235e3a8 / 0x8235e998): type 16 (or 1 / sub 1) hit on a lying thrall with companion -> death kind 7 | closes hint_17 | `[Death] TranslateNotify38` (0x85b0fc / 0x85b15c), built | ✅ static |
| 31 / 27 (TU 0x823a3d20 / 0x823de858) | not read | | | ⬜ |

**Rule: 33, 34 and 38 must be on together**; 33 alone leaves `hint_17` open and blocks `hint_08` (live 07.11.) ✅.

### 7.4 State-chart VM (second VM)

Separate small VM used by state-chart programs: interpreter 0x432b20 (push 0x432b56, byte map 0x432e48, jump table
0x432df8); native table 0x8ac128 (namespace 0: 7 natives, namespace 1: 102); context 0x2c B (ctor 0x437020: +0 code,
+4 top, +8 pc, +0xc base, +0x10 stack 0x200, +0x14 frames, +0x1c owner); opcodes 0x47-0x52 arithmetic / logic, 0x63
jump, 0x64 jump-if-false, 0x65 native, 0x7b return. Converter faults: swapped literal halves (`tools/vm_literal_fix.py`),
unswapped code words (`tools/statevm_check.py`), only in `doppelganger_casual.drm`. ✅ (`Befund-Felsrinne.md`)

### 7.5 Log channels

`ScriptDebugger` is only a log channel (0x598760, table 0xcda0d0); all channel output goes to the `ret` stub 0x6457a0.
Port 9264 is the FMOD profiler (init flags 0x200080 at 0x586f67 / 0x586f91), not a developer channel. No script debugger
server exists in the exe ✅ (`Befund-Entwicklerkanal.md`).

Sources: `Befund-Test33-Native.md`, `Befund-TruMenu-0214-0711.md`, `Befund-Hall02-Wand-0711.md`, `Befund-P1a-ThrallTod-0711.md`,
`Befund-Hall02-Tutorial-Stufe2-0711.md`, `Befund-Thrall-Absturz.md`, `Befund-Erfolge.md`, `Befund-P5a-Achievement-0711.md`.

---

## 8. Level scripts, hints, help-on-demand

### 8.1 hall02 tutorial fight (`dlc_yggdrasil_hall02`)

| Intro | What | Script | Role |
|---|---|---|---|
| 11270 | dispatcher | **24540** | fight + wall control |
| 11260 | `dlc2_uo_enemybreakwall` (obj 930, uber DTP 24548) | 24521 | the wall |
| 10028 | generator (obj 1003, spawns 1004) | 22809 | OnSpawn vt54 -> dispatcher f3; f0 sets thrall member 22813 +8 = 2 |
| 11268 | trigger volume (arena) | 24538 | enter vt70 / exit vt71 -> dispatcher f1 |
| 10608 | trigger | 23118 | tutorial start -> f2 |
| 10154 | reveal object | 22865 | -> f5 |
| 11263 | yeti behind the wall | 24533 | |
| 11258 / 10644 / 11259 | checkpoints | 24519 / 26429 / 24520 | 11259 behind the wall |
| - | level script | **23101** | hint notifications (f3), achievement f20 at +0xab4 |

Dispatcher stickies (owner 0:11270): `broken` +44 (key 10029), `tutorial` +72 (18509), `deathcount` +100 (8914),
`population` +128 (17287), `hint_17 shown` +188 (19598).
Logic ✅: f0 counts only messages with value 2 (thrall death vt31 / Symbol 108 `vthrall_dead` passes member +8; the yeti
sends 0); f1 opens the wall when `tutorial >= 2 && !broken && population == 0`; f2 `tutorial += 1`; f3 `population += 1`;
f4 (thrall dead) `deathcount++`, `population--`, f1, at `deathcount >= 3` -> generator f4 and `tutorial = 2`; f7 breaks the
wall; f8 waits 3 s, then generator f1(1). `tutorial = 2` normally comes from 23101 f3 (hint_08 + notification 25 + one of
26 / 35 / 36 / 37), fallback 3 deaths. "Stage 2 + one kill" is the TU-correct behaviour ✅ live.

**Counter drift** ✅: a checkpoint saved while thralls are alive restores them with member +8 = 0 (members are not saved),
so their deaths do not count and `population` stays > 0. Root cause on PC: generator data spawned thralls before the
tutorial (section 10). `ai.remove` despawns without vt31 and also leaves `population` high.
Plugin: TruMenu 0.21.4 `fix.hall02` (only when no live 1004 thrall: tutorial 18509 = 2, population 17287 = 0), `thrall.scriptval`.

**Hints** (text ids 5204-5210): hint_08 (5204) closed by 25 + 26 / 35-37; hint_09 by 28 / 35; hint_10 by 30; hint_11 by
31; hint_12 by 32; hint_17 (5209) shown by 33, closed by 29 / 34 / 38; hint_18 by 27.

### 8.2 Other level-script knowledge

| Topic | Fact | St |
|---|---|---|
| DLC 1 help-on-demand | DLC 1 script 24319 sends (number, "dlc_l1") on `HelpOnDemandMessageChannel`; receiver generalbank script 33 / PDA 3366 (Xbox 34) f6 knows only "l0".."l7" -> `ERROR: Level not found!`, nothing shown. No `dlc_l1` branch or texts on any platform, so the empty help is probably Xbox behaviour too (Xenia check ⬜) | ✅ chain / 🔶 Xbox |
| DLC 2 objective / hint notifier | per-unit uiscreen class (26430 hall02, 26078 end, 26449, 24482, 26535, ...): text members 5182 / 5201 ("OBJECTIVE / HINT REVEALED"), created by the objectives dispatcher (op6a) after "set" on channel_dlc2_pda; runs on PC (TruMenu script log "Linking hint revealed animation", "About to play objective revealed animation") but its member init blocks are mis-converted (floats through the symbol map, u32 as 2 x u16; `tools/ui_text_init_scan.py`: 53 of 1071 anchors, 52 DLC 2 + 1 DLC 1) -> banner not visible on PC (Xenia 09.11. shows it). Training texts (1296, 1319-1325) are in `locals.bin_004`; the combat tutorial text of hall02 shows on PC (live 09.11. 14:54). **Fix: pipeline step uiinit** (`tools/ui_init_fix.py`): UI element userTypes Xbox 299 / 301 / 314 / 318 = PC 301 / 303 / 316 / 320; base proof generalbank Xbox <-> PC (141 script pairs by name, 389 UI members paired, 23 279 words, 0 contradictions; 591 words with a re-authored PC value ignored): per (userType, tag, init path) s32 129 / raw 7 / id classes kept / one union word s32-or-text; PC-only field userType 301 path [0, 100]: Xbox 0 -> PC 0x00010000 in all 108 base observations; on the 0813 trees (+ end-level fix) DLC 2 1239 words in 15 DRMs, DLC 1 9969 words in 13 DRMs (generalbank script 72 copies), every replaced word a converter fault form of the Xbox word, word diff = planned only; `ui_text_init_scan` after: DLC 2 465 / 465, DLC 1 252 / 252 anchors ok | ✅ static, step built (not in a tree yet) / 🎮 banner live |
| Pause menu (script 7 `uipause`) | TU sends `HODRefresh("DLC",1)` and `PauseMsgCh` paused / unpaused; ported by `tools/script7_pause_port.py` (members 3208 / 3228), not in the pipeline | ✅ built |
| Ring menu slot 7 (main + pause menu, script 7) | One script for both menus: 7 ring slots (1 new game, 2 options, 3 load, 4 save, 5 audio / visual, 6 extras, 7 bottom left) + the centre (play / resume, text 123 / 122); count `m0xa40 = int(m0xa38)`, angle step `m0xa48 = m0xa68 / m0xa38` (func 0); `PositionMenuItems` (func 35) cases 1-7 = ring, cases 8+ = sub-rings (index = k + count). Slot 7 is QUIT GAME (door 0x738, text widget 0x3a8 = locals 131, click -> DialogYesNo script 128) or DOWNLOADABLE CONTENT (download 0x72c, text 0x39c = 130, click -> sub-ring 7 PLAY MISSION / COMMUNITY INFO / DOWNLOAD CONTENT), chosen at three sites: func 27 +0x6288, func 35 +0x9688, func 8 +0x188dc. PC original: corebase f17 (always true) = QUIT in both menus; B138 kit (installed): `!uigamedata.f37()` = DLC in the main menu, QUIT in the pause menu - **the main menu has no quit entry**; `menu_dlc_patch.py`: corebase f15 = DLC in both. Hit areas 0x108..0x138 = slots 1-7 (0x128 = slot 6, 0x130 = slot 5; slot 4 save shows only text 161 in the front end). Check: `tools/menu_quit_slot_check.py` (forms pc / f15 / b138, `--expect`) | ✅ static / slots 2, 5, 6 by screenshot |
| Ring geometry: 14 positions (script 7) | `m0xa70` = 14.0 (init +0x251f4), count `m0xa38` = 7, step pi/7; slot 1 at 0 deg (top), counter-clockwise; left half = slots 1-7 (index k), right half = sub-ring positions 8-14 (index 7+j at -j*step); **position 14 = bottom (-180 deg)**, 1080p (960, 848), unused on PC (Xbox "STORAGE DEVICE": icon 0x7bc, text 0x468 = 141, hit area 0x170, background 0x6b4). Images, clicks, animations, d-pad (f12: 7 <-> 14) and the lock list are tied to the fixed numbers 1-14 - a count of 8 breaks the ring. Prototype entries are 28 B: op68 operand 0x298c4 + 28k = func k. Tool `tools/menu_ring_layout.py` (`--expect-p14`) | ✅ static + screenshot (7 icons within 1.6 px) |
| Ring lock list / sub-rings (script 7) | `m0xa90` bool[14] = "position i+1 locked" (stick f18 / d-pad skip it). Writers: f19 (base state, only from f0 Run: all free, then 7..13 locked), f20 (sub-ring open, only from f24: every PC sub-ring 2-7 locks index 13 and hides background 0x6b4), the three **f8 dialog blocks** options +0x17750 / audio-visual +0x181d8 / quit +0x18944 (lock 7..13, hide the right half and icon 0x7bc, then open script 127 / 130 / 128). Open sub-ring `m0xa88`: set only by f24 (2..7 from f8 clicks) and those blocks (2 / 5 / 2); **no code closes a sub-ring** (back does nothing in the front end, in a level it closes the menu via f2). f43(m0xa88) hides 0x7bc in cases 2-7 on PC (shown on Xbox in 3 / 4). States: f1 OnOpen -> op7d 1 -> f50 ring-in animation; f24 -> op7d 2 -> f52 sub-ring animation, then f43. f21 = hide icon (uibitmap f5 + colour 1,1,1,0), f22 = show icon (f4 + colour 0.45, 0.49, 0.65, 1); uibitmap (89) f4 show / f5 hide / f15 position / f18 colour, uitext (92) f3 show / f4 hide (names from use). Click test per hit area: `uimenuitem` (88) f14 + `uiwidgetref` (94) f0 on param 0; f8 order: centre 0x178, slots 0x108..0x138, then from +0x18f50 the sub-ring dispatch | ✅ static / 🔶 native names |
| Ring layout "V3 P14, stage light" (built 2026-11-10) | `tools/menu_ring_p14.py build / verify`: slot 7 = DLC in both menus (D1: f15 form at P1 / P2 / P4), QUIT GAME on position 14 (D2 f19 +0x3d9c lock 13 = 0, D3 f29 +0x8124 NOT -> op00 places 0x7bc on PC, D4 0x7bc texture 31 -> 26 door, D5 text 0x468 141 -> 131, D6 background 0x6b4 texture 16 sub-ring disc -> 15 slot disc) + appended blocks via op63: B1a f19 +0x3da4 shows 0x6b4 / 0x7bc (uibitmap f4 + f18 colour), B1b f8 +0x17c10 / +0x18768 / +0x18e04 re-free index 13 and show them after the dialog blocks, B1c/B1d f24 +0x5274 (after f20), f24 +0x52d4 and f52 +0x1569c (after f43) keep the door visible and free while a sub-ring is open (position 14 is unused by every PC sub-ring), B1e f1 +0x43ec (OnOpen) re-applies it on every open, B2 f8 +0x18f50 click on 0x170 and not locked -> quit fall-through +0x188f8 (DialogYesNo script 128 -> uigamedata f45). Tree 1 (md5 e64ca088, live 10.11.): QUIT worked, but the door had no disc (f28 leaves every background at alpha 0, only the ring-in animation brings the slot discs up) and the game crashed after DLC / new game: B2 read the lock with the store prefix `21 0e; 1e 01; 1b` - the VM op1b handler 0x57d1af takes (base, offset) from the stack and faulted at 0x57d1c4 (3 dumps, VM pc in B2). **Lock element read = `0f a90; i; 21 0e; 1b`, write = `0f a90; i; 21 0e; 1e 01; 04 v; 2e`**. `verify` now has an opcode-shape gate (every 3-gram of an appended block must occur in the original script). Tree 2 (md5 f6477172, live 10.11.): no crash, new game / DLC / quit work; door grey (f22 colour) and hidden in sub-rings. **Ring slot colours come from their animation sets** (type 83 members, colour keys reached through the init tree, ring-in key at 0.18 s): icons 0x964 / 0x994 ARGB ff3273b9, discs 0xbb0 ffc8c8c8 (`work/ring_p14_1011/anim_tree.py`); position 14 has no set, so the blocks set these colours with uibitmap f18. Tree 3 `work/ring_p14_1011/tree3` (md5 e5ae8d8f...), not played; not in the pipeline (runs on the step 21 file too); no animation for position 14 (stage 2 "B3") | ✅ built, offline / tree 2 live: quit, DLC, new game ✅ / tree 3 ⬜ live |
| uigamedata f37 / f45 (front end, quit) | f37 = 0x7a0e90 -> 0x5d56e0: main state `[0xe7ed60]` is 6 or 10. f45 = 0x7a0f30 -> 0x77c190: 0x4be580, 0x4be5e0, StopMovie 0x4a0f10, `[0xe7ed60] = 8`; state 8 sets `[0xe7ed60+0xc] = 1` (0x5e0125). DialogYesNo (script 128) calls f45 on "yes" (+0x668 / +0xa6c) = the game's own quit; that it reaches the shutdown 0x5df930 (settings save) is not traced. uigamedata f1 = 0x79eb10 (always false on PC) | ✅ static / 🔶 path to 0x5df930 |
| Manor prologue | gate stickies 10814 / 10817 on dispatcher 4086; trigger plane 4128 (script 11574) calls PlayCinematic(4108) unconditionally (jumps to `l4_trailstart`, live) | ✅ |
| PlayCinematic | base script 3523 f0 (prototype +0x2410, vtable slot 57, Symbol 6016) | ✅ |
| Extended ending | `l7_himalaya_end` (unit 78) level script 18330 -> 18332 -> 3523 f0 plays `343_hel_engame` (59.03 s); the shipped monastery script 18497 ends the game first | ✅ data / ⬜ live |
| Direct start | `uigamedata` f27(unit, 1, 0, 1) after f22, then `stdscreenmgr` f19 + f7; script 60 = AttractTimer (test 41e: `script_directstart_stub.py`) | ✅ |
| Chapter title card | generalbank script 72 f4 `SetChapterUIData(level, chapter)`: locals text id per (level, chapter): 1 / 1-5 = 388-392, 2 / 1-4 = 393-396, 3 / 1 = 397, 4 / 1-4 = 398-401, 5 / 1-2 = 402-403, 6 / 1 = 404, 7 / 1-3 = 405-407; level titles 386 (prologue, chapter 387 🔶), 52-58; quotes 408-428; level 8 (DLC 1) only placeholders 482 / 127, level 9 (DLC 2) 432 / 433. Callers: base-game cinematic objects only (l1_seatop 997 -> (1, 1), script 8003 -> (1, 4), l2_cliffclimb 2562 -> (2, 1), l7_arctic_sea script 19599 -> (7, 1)); 28 DLC DRMs carry a copy of script 72, no DLC unit calls it -> the DLCs show no chapter cards. Save names are "<LEVEL> - <chapter>" (e.g. "SÜDLICHES MEXIKO - Xibalbá"); the save field +0x1f2 "chapter" is 0 in all 14 saved games. DLC mission names 450 / 451 (`locals.bin_001` EN, `_004` DE) | ✅ data (`work/menu17i_0811/s72_chapters_out.txt`, `refs72_*.txt`) |
| DLC sections (checkpoint objects 83 `checkpoint` / 1036 `dlc2_checkpoint`) | DLC 2: level2_start (000_fight 11291; CP 9400, 11277, 9733, 11278) -> hall01 (CP 10626) -> hall02 (11258, 10644, 11259) -> end (10036, 9953, 9970, 9608; 020_ghoul by cinematic_object 9611, trigger volume 10026 - CP 9608 lies inside it 🔶) -> ceremony_room (030_pod 11868, 040_podon 11869; CP 11845-11854) -> ring machine_ceremony / machine_room / goo_machine / goo_room / ceremony_goo (order not in the data) -> treasure_room_cine (045_finale 12163, 050_crush 12164). DLC 1: level1_start (010_intro 10656, CP 12241) -> caverns -> caverns_hall -> water_wheel -> pillory -> dungeonhalla / b -> watertunnel -> dungeon -> treasureroom (030_finale 9459); order after caverns_hall from the portal graph | ✅ data / 🔶 order |
| DLC 2 cinematics | `000_fight` level2_start -> `020_ghoul` yggdrasil_end (32.37 s; actors 9641 / 9642 co_wp_handgun, 9639 co_lights, 10038 black card; Natla 10155 via the command list DTP 24350; Xbox unit 105 -> PC 106) -> level change -> `030_pod` / `040_podon` ceremony_room -> `045_finale` / `050_crush` treasure_room_cine. Ghoul end: Cine_End, checkpoint by cinematic_object 9611, level change by name to `dlc2_ceremony_room` (0x5dfb20, doneType 4), where placement finds no intro 9611 and falls back (0x5d4330; Xbox the same? 🔶). Order and .mul (5 languages) = Xbox | ✅ data + live log 08.11. |
| Golden shotgun (884) | pickup in `dlc_dungeon` (intro 9475, script 20313 -> UI 23339); weapon-name case 5 (TU 0x8247dbc0) / reward code 0x8229fc08 missing on PC | ⬜ |

Sources: `Befund-Hall02-Wand-0711.md`, `Befund-Hall02-Zaehler-Drift-0711.md`, `Befund-Hall02-TU-Vergleich-0711.md`,
`Befund-Hall02-Tutorial-Stufe2-0711.md`, `Befund-DLC1-Hilfe.md`, `Befund-Pausemenue-TU.md`, `Befund-Manor-Prolog-0611.md`,
`Befund-Erweitertes-Ende.md`, `Befund-Direktstart.md`, `Befund-Versteckte-Inhalte.md`, `Befund-Hauptmenue-Beenden-1011.md`,
`Befund-Ring-8-Plaetze-1011.md`.

---

## 9. Uber objects (state graph in a DTP)

| Item | PC | St |
|---|---|---|
| Update | 0x4d7550: while `+0x80 == 0` check transitions (0x4d4b60) and add dt to `+0x88` | ✅ |
| Conditions | 0x4d31e0, table 0x4d3294. 1 = time in node `+0x88 >= arg - 0.001` (0x4d3204); 3 = immediately (0x4d3250); 9 = object / instance check (0x4d322a: 0x453310 + 0x4d1360); 11 / 12 = `+0x90 & 6 == 2 / 4`; 0x10 = uber command (0x4d5bb0, `+0x1c == command`, from switch 0x4d7680 kind 4); any other code is false | ✅ |
| Start node | DESC +0x14; set on the first Update (0x4d7582) or before the first message (0x4d76b5), guarded by +0x90 bit 0 | ✅ |
| Messages (0x4d7680) | record {?, kind +4, value +8}: 1 = set node = value, 2 -> 0x4d4be0, 3 -> 0x4d5b30, 4 = command (0x4d5bb0) | ✅ |
| Object command table | DTP +0x100 count / +0x104 list of {?, 1, ptr -> message}; script `uberobjectcommand (obj, n)` selects entry n | ✅ (goo drips) |
| Actions | 0x10-byte records {kind, arg}, vtable 0x847f30 slot 2 = 0x4d86a0, jump table 0x4d8a78 (26 kinds); 19 = spawn (0x4d3b50, record starts with u16 object id, INSTANCE_BirthObjectNoParent at 0x4d3c21 -> 0x5bd0f0); 4 = remove self (iflags \|= 0x800 \| 0x20, 0x4d876d) | ✅ |
| TRANS +0x34 | byte: 1 = play anim (+0x28 / +0x2a u16), 2 = wait for anim (only read with 1), 8, 0x20 (0x4d4a00) | ✅ |
| Process path | instance process 0x6d5f30 (magic 0xF0012345) -> 0x6d5e20 -> Update 0x4d7550; called through `[inst+0x110]` by the instance process loop 0x5b6dc0 (0x5b6f3f) from the game loop 0x5dfdbe | ✅ dump 08.11. |
| Action kind 2 = play anim | case 0x4d86d9: action+4 = {u16 mode, u16 anim}, anim 0xffff = none; target `[[[b+0x74]+0x280]+0x14]` -> 0x444ba0. TRANS +0x28 same layout (0x4d4a26); TRANS stride 0x38 (0x4d4b18), node 28 B, DESC 0x60 B 🔶 | ✅ |
| Anim request 0x444ba0 (thiscall req, ptr) | mode 0 -> 0x444ca7 (0x4321d0); 1 -> object anim list `[[Object+0x58]] + i * 0x24` if i < u16 Object+0x38, else null -> AV **0x444c62** (0x4428a0 tolerates null); 2 -> 0x443720; >= 3 -> nothing | ✅ static + dump |
| Wait flag +0x8c | set by TRANS flag 2 even when no anim started; cleared only at 0x4d4a0e (next transition) -> mode >= 3 with flag 2 probably stalls the object | 🔶 |
| Play-anim data rule | PC word = u16 pair of the Xbox word (base game 575 / 575 words in 98 uber objects); the DLC converter wrote 18 words as u32 in 7 DLC 2 files (goo_cannonball 964 DTP 25328 +0x6d4 {mode 0, anim 1} -> {1, 0} = the crash in `dlc2_ceremony_room` 08.11. 00:27, AV 0x444c62; natlapod, machine_column, extending_bridge (+ _long / _special), corkscrew_200cm); B270 right everywhere; fix tree `work/crash_0811/tree` (`uber_anim_fix.py`), pipeline step `uberanim` (17n, `tools/typed_family_fix.py`; base proof on the store pairs: 179 uber DTPs, 288 informative words u16 pair + 987 symmetric, 0 u32; installed copies 18 words, 6 of the 7 files md5 = the test tree, the cannonball also gets basecopy's LUT words = 17m's `tree_n6b_17m`; 0811 pipeline copy 8) | ✅ data |
| Set node | 0x4d7440: `+0x84` = node, run actions 0x4d5c60, clear +0x80 / +0x88 | ✅ |
| Start transition | 0x4d4a00: `+0x80` = trans, `+0x84 = -1`; flag 1 = play anim (TRANS +0x28 / +0x2a), flag 2 = wait for `+0x8c` | ✅ |
| Command list | `FUN_004d7680`, `FUN_004d4be0`, `FUN_004d4a00` (command list / transition; used to trace gate and bridge logic) | ✅ (from FINDINGS.md) |
| Live read path | `p = [inst+0x2d0]; u = [[p]+0x2ec]; b = u - 0x10`; valid if `[b+0x70] == 0xF0012345`; +0x78 DESC, +0x80 TRANS, +0x84 node, +0x88 time in node (f32), +0x8c bit 0 waiting for anim; node name `*(char**)([[b+0x78]+8]+28k+8)` (`tools/vm_uber_state.ps1`) | ✅ |
| Schema | `dtp_schema.py` sizes TRANS as 0x28 B, the engine reads up to +0x34 | ✅ |
| Script classes | `uberobjectcommand` (850; commands 0 / 1), `uberobjectevent`, base 3592 | ✅ |

**Gates in `dlc_caverns_hall`** (intros 9834 / 9835, objects 850 / 851, DTPs 20851 / 20859, switches 9836 / 9837 scripts
20839 / 20840): reset (2) -> open (1) on command 0; open -> closed (0) on command 1 (sent only on load) or after **25.0 s**
(f32 0x41c80000 at DTP +0x860); closed -> reset after 2.0 s. The switch has its own `wait 30`. Xbox = PC word for word:
original behaviour ✅ (live 29.995 s + ~1.85 s anim). Open: which uber event fires per node, anim lengths ⬜.
TruMenu 0.21.7 shows uber labels (node name per instance through the live read path above; `[Debug] LabelRadius` 3000
limit): ✅ live 07.11. (`dlc2_uo_goo_drips` and its runtime copies at the foot of the end-room light columns, node
"goo_off"). The caverns gates got no label in the live test because they were 3165 / 3357 units away. Sources:
`Befund-Tore-CavernsHall-0711.md`.

**Goo drips** (objects 926 `dlc2_uo_goo_drips` / 937 `_sml`, DTP 24411 / 24872, class script 24346 subclass of 3592; intros
in end 10704-10707, 11407): start node 7 `Spawn_easy_pause_to_start` -> after 4.0 s node 4 `Spawn_easy` (one 929 / 942
`_spawned` copy per 0.7 s via node 5); command 0 -> `Spawn_hard` 1 / 2 / 0 (two spawns per 0.9 s, a loop **without exit**);
node 3 `goo_off` is reached only by a direct set-node message (command table entry 0; entry 1 = command 0 hard, 2 = command 1
easy, 3 = set node 6 `spawn_one` -> 3). Class script members +4 / +12 / +20 / +28 = uberobjectcommand (926, 0..3): f0 hard, f1
goo_off, f2 easy, f3 spawn_one. Controller: intro 10706 script 24313 calls f2 (easy) for itself and 10707 / 10704 / 11407,
waits 0.8 s and loops (opcode meaning 🔶); who sent goo_off live is not found ⬜. Spawned copies: initial -> done at once,
play anim 1 and wait (TRANS flags 3), done runs action 4 (remove self). Xbox = PC except TRANS @0x430 (5 -> 1 on command 0)
in 24411 and 24872: byte +0x34 Xbox 2, PC 0 (the 2 sits in +0x37) - harmless (bit 2 is read only with bit 1) but a
converter mismatch worth a scan of all uber DTPs ⬜; DTP head +0xdc of 929 converted as a u16 pair (reader unknown ⬜).
Object 957 `goo_upcolumn` (25235) has its own graph (init, shot_goo, SetState, hide). Source: r17e 08.11. (`work/r17e_0811`).
**Corridor drips and the PC deaths (2026-11-10):** the drip corridor before checkpoint 9970 has two sources, intros **10706**
(script 24313, the controller) and **10707** (script 24314), live (data - Level+0x80) x -194.5, y -6292.2 / -5724.6, z 11951.6,
3370 units above the walkway. Both PC deaths of 09.11. (TruFight.log: -124 / -6006 / 8580 and -40 / -5980 / 8583) lie under
their midpoint (y -6008.4); Lara had LP 2000 on the line before and her body then flies on in the running direction and drops
(~200-265 units) = one hit + thrown, like the Xbox without power. Volumes there: water volume 10060 (box 201 x 895 x 20.5 at
floor height, script 22703), trigger volume 10708 = hint `hint_13` (script 24315), 10039 = objective counter (22650), plane
11406 (22663) - none is a kill volume, so the falling `_spawned` copy itself most likely deals the hit (🔶; its anim event
lists 24418 / 24419 / 24421 hold only kind-1 events {3, n}). The particle records of 929 are Xbox = PC
(`tools/fx_record_check.py`). No DLC 2 script calls the time-scale natives `gamebase` 23 / 24 except the shared base script
205 (f1 "Heads up!!!": f24 + f23; copied into every DLC DRM) and DLC 1's 3583, so the source of the Xbox world 1.0 at the drips
is still open ⬜. Logging plan (drip node / time via the live read path above, nearest 929 copy position + node, Lara damage
call 0x637590): workspace `Befund-Goo-Tropfen-1011.md` §3.

---

## 10. Generators (pool generators)

| Role | PC | TU | St |
|---|---|---|---|
| Init | 0x780d24 | 0x82481f70 | ✅ |
| Spawn | 0x780eb0 -> 0x78123c -> 0x780a90 -> `INSTANCE_BirthObjectNoParent` 0x5bd0f0 (at 0x780abb) | 0x82480c88 | ✅ |
| Simulate | 0x781510 | 0x82481530 | ✅ |
| MessageHandler | 0x781730: 0x23 restore, 0xba, 0xff, 0x100, 0x11c, 0x1e6 spawn, 0x1e7 off, 0x1e9 on | 0x82481810 | ✅ |
| OnSpawn | sender 0x798770 with `[newinst+0x60]` (set at 0x781342), event slot `[0x105b754]` | | ✅ |
| Data pointer | generator instance +0x104; counters +0x7c expected children, +0x80 spawned total, +0x84 bit 0 auto-spawn off | | ✅ |

**Intro data** (intro +0x78; proven from code + 22 retail pairs): +0x30 u16 **max alive** (child list +0x70 count >= value
-> no spawn); +0x32 u16 (no reader found); +0x34 s16 **total limit** (-1 = unlimited, counter +0x80); +0x38 u16 **group
size** (then group pause); +0x3c / +0x40 f32 in-group delay min / max; +0x44 / +0x48 f32 **pause** between groups min / max;
+0x54 / +0x58 f32 distance 🔶; +0x5c u16 flags: **bit 0 = automatic spawning off at start** (bits 1 / 2 tested in Spawn);
+0x60 alternative list (always 0); +0x64 spawn list; +0x70 list {u32 count, 0x1c-byte entries {u16 object id, u8, u8;
+0x10 -> 0x390-byte AI record}}. Every retail generator starts "off" (flags 0x0001 x80, 0x0003 x4). `merc_generator_run`
uses another layout. ✅

**Converter fault** ✅: 24 of 46 DLC 2 generators (75 words) had +0x30 raw (1 -> 256), +0x38 / +0x5c as u32 (bit 0 lands in
+0x5e), floats / bytes swapped -> 16 generators spawned on unit load (hall02 softlock). Fix `tools/generator_intro_fix.py`
(proof on 84 generators / 2688 words, 0 contradictions); pipeline step `genintro` since 08.11. (section 2). Live 07.11. with the
fix: tutorial first ✅. Open: +0x0c / +0x32 / +0x5e meaning ⬜. Sources: `Befund-Generator-Datenfix-0711.md`.

---

## 11. Triggers, trigger volumes, planes

| Item | PC | St |
|---|---|---|
| Lists | planes count `[0xdba21c]`, array 0xda61c8; volumes count `[0xdba220]`, array 0xdb6be0; max 0x200 each (adders 0x5c8990 / 0x5c89e0) | ✅ |
| Entry | +0x20 instance; +0x24 bit 31 active, bit 30 test against the player `[0xe7f094]`; +0x28 list of other instances | ✅ |
| Per-frame test | 0x5cd520; test point = player +0x20 + (0, 0, 200) (`[0x853f08]`); data `[[inst+0x100]+0x78]`; optional filter `[0xdb6a5c]` | ✅ |
| Volume (0x5cd1b0) | shape byte +0x30: 1 box (0x46b730, half extents +0x34 / +0x38 / +0x3c, Euler matrix 0x49d500 M = Rz*Ry*Rx), 2 sphere (radius +0x40) | ✅ |
| Plane (0x5ccc20) | w +0x34, h +0x3c, byte +0x44 = 0 one-sided; segment vs two triangles 0x461640; script base `triggerplanebase` 3587 events vt54 / vt55 | ✅ |
| Stream portals | 0x5d295f / 0x5d2ab5 / 0x5d2a48 (section 4.2) | ✅ |
| Water volumes | object 7, intro data type 11, extents +0x54 / +0x58 / +0x5c 🔶; not in these lists | 🔶 |
| Volume test (Xbox pair) | retail 0x82290c58 / TU 0x8228d8c8 = PC 0x5cd1b0: PC / retail build both matrices (0x5cd2d4..0x5cd3d8) before the shape switch 0x5cd437; the TU tests spheres without matrices and rejects boxes by a bounding sphere first (same results, only faster). The xmap pair 0x82254110 <-> 0x5cd520 is wrong (0x82254110 = a script-event queue; partner of 0x5cd520 ⬜) | ✅ static (17w) |

Base script 3484 (trigger volume) +4 = sticky key 1724. Trigger kind is only known from the object name ⬜.
Plugin: TruMenu 0.14 `dbg.triggers` / `dbg.portals` / `dbg.checkpoints` draw exactly this test. Source: `Befund-TruMenu-Trigger-0611.md`.

---

## 12. Lara's state chart (player moves)

| Item | PC | Xbox TU | St |
|---|---|---|---|
| Builder (registers condition / activity / state ids from 3 static tables) | 0x7872f0; table push operands 0x787343 / 0x78735a / 0x78736a; sizes 307 / 332 / 199 | 0x82489500 (unchanged; only the tables grew) | ✅ |
| Chart transition | 0x787890 (TruTrace hook); chart machine 0x7873c0 | | ✅ |
| Machine record pointer / index | `[machine+0x510]` (TruRockVein record index) | machine reset 0x82482808: chart = [machine+4], record pointer [machine+**0x520**] = [[chart+0xc] + 4 * s16 [chart+0]]; index = position in the array [chart+0xc]; record +0xc u16 state-id count, +0x18 pointer to the u16 state ids (as `tools/chart_state_path.py` reads the DTPs). TruXenia logs indices since 09.11. | ✅ |
| Condition default handler | 0x782140 | 0x82484db0 | ✅ |
| Markup condition test | 0x782810, jump table 0x782a54 (ids 601-628), type getter 0x5be340 | `SCCondTest_MarkupType` 0x82486dd8 | ✅ |
| Condition record | {u16 key, u16 id, u16 value, u8 flags, u8}; 607 / 608 are the **value** (markup type 23 / 22), the record id (610-613) picks the handler | | ✅ |
| Lara registration table | PC 0x768b60 (TU 0x82473b50 adds states 243 / 245 / 1018, conditions 1048 / 2401, activities 1009 / 1039) | | ✅ |
| Activity 1005 | attack record `[[0xfadb58]+0x504]+0xc4` (handler 0x767e90, table 0x8b2280) | | ✅ |
| Player hit list +0xa4 (8 instance slots) | add-if-absent 0x6e6990 (thiscall, al = 0 when present / full), called by the contact sender 0x719050 at 0x7190ad before 0x11c; clear 0x6e6950; state 1004 slot 0 0x75e020 clears always, no slot 1 | same loop inline in 0x823e152c..0x823e1580; state 1004 {0x8245efc8, 0x8245efc8, 0x8245f050} in machine 1 (table 0x82757948, entry 0x827588b4; machine 2 table 0x82758dd8 has no slot 1; retail both {0x8245ba70, 0, 0x8245baa0}): clear unless parameter 0x415, then 0x823dfc98; slot 1 = re-enter (K-8) | ✅ static; live ⬜ (TruShadowCombat `[States] Translate1004`; log point 0.6.9 at 0x7190ad: `0.6.9 hit list: ... added in slot k / REFUSED: already in slot k` with Lara's record, `[Hit] Log`) |
| Frame-window conditions 212-217 (combo window {210,213 / 214,22}) | 0x783950 (jump table 0x783b4c, frame from 0x438910 / 100) | 0x824855e8 (changed only by the machine field shift +0x50c -> +0x51c) | ✅ static |
| Input conditions 150-153 | test input set 17 (0x760b50 ...) | | ✅ |

TU-new ids: conditions 1048-1056, 2005, 2006, 2013, 2401; activities 286, 1009, 1039, 1040-1045; states 243-245,
1017-1020, 2102. Plugins: TruDoppelganger (tables), TruRockVein (607 / 608 stubs; data fix `tools/statechart_fix_all.py`
because DTP 20212 held 608 as 24578), TruShadowPower `[States]` / `[Conditions]`, TruShadowCombat (target list 7 -> 10,
conditions 2005 / 2006 / 2011 / 2013, states 1004 / 1007 / 1013 / 1014 / 1017 / 244). Chart record tools: `tools/chart_*.py`.
Sources: [TruDoppelganger README](../src/asi/TruDoppelganger/README.md), [TruRockVein README](../src/asi/TruRockVein/README.md),
`Befund-Felsrinne.md`, `Befund-Schattenkampf.md`.

---

## 13. Enemies: brain, AI states, damage, death

### 13.1 Instance -> brain

| Item | PC | St |
|---|---|---|
| Brain pointer | `[[inst+0x2d0]]+0x2ec` (0 = no brain); stored by enemy init 0x63c190 at 0x63c215 | ✅ |
| Brain | ctor 0x634020, **0x5040 B** (TU 0x50a0 B) | ✅ |
| Has a brain | enemy data `[inst+0x50]` magic 0xdaf00018 with byte +0x18 > 0 (0x63c1b5..0x63c1d3) | ✅ |
| Enemy function table 0x8abbb8 | init 0x63c530, process 0x638d40 (EnemyProcessFunc 0x638d59), message 0x627a80 -> 0x6254b0 -> default handler `brain+0x1c44` = 0x63b330; query `brain+0x1c48` = 0x632200 | ✅ |
| Behaviour tree byte (0x63c2e2) | 1 Creature, 2 CreatureVolumetric, 3 Thrall, else Soldier (tree vtables 0x857964 / 6c / 74 / 7c) | ✅ |

**Brain fields** ✅: +0x08 gate bits (13.8); +0x0c bit 0 melee flag, bit 1 "skip death check", 0x10 (TU Vaulted only);
+0x168 current tune, +0x16c tune id; +0x170 EnemySensesControl; +0x1a0 12 sense slots of 0xe0; +0x11a0 bits 1 / 2 Getup
decision; +0x11e0 behaviour tree; +0x1254 state machine; +0x125c / +0x1260 current state object layer 0 / 1; +0x18d4+4*layer
active data slot; +0x18f8 / +0x18fc requested state; +0x1c44 / +0x1c48 handlers; +0x2c60 health component (+0x2c64 LP,
+0x2c6c health from tune+0x3c); +0x4e10 EnemyTargeting. TU only: +0x2c7c (Vaulted Enter writes 0x0fffffff with a
companion; no PC reader), +0x5080 Vaulted clock start (ms), +0x5084 saved time multiplier, +0x5090 / +0x5094 companion
handle. The TU block sits before the brain's tail: **TU +0x5088 = PC +0x5030** (shift 0x58), so TU fields from about
+0x5030 on have no PC room and plugins keep them outside the brain (TruShadowCombat 0.6.6: 64-entry table keyed by
instance + serial +0x44). ✅ static (`Befund-P1d-Begleiter-0711.md`, TruShadowCombat README 0.6.6)

**Tune** (enemy data +0x1c array, count +0x18, default +0x20; names from the 69 retail getters
`EnemyObjectDataControl::get_*`; the 2007 prototype order is different, do not use it) ✅: +0x30 senses, +0x3c health,
+0x58 wrestle, +0x64 directionalDeath (regeneration data), +0x68..+0x70 rangedAttack1..3, +0x80..+0xac meleeAttack1..12,
+0x11c spawn, +0x13c meleeController.

### 13.2 Enemy state machine (not Lara's chart)

State objects are static (name `(char*)[obj+8]`, name tree `[0xecfb4c]`, 79 names: `tools/pe_enemy_state_names.py`);
`IsInState` 0x6711f0. State data `(brain+0x1273 + (slot + 2*layer)*0x19c) & ~0xf`, data+0x198 = state object (same on all
three exes). Helpers: switch 0x671d30, by object 0x63d4a0 (TU 0x8230bf78), typed data 0x63d6e0, refusing path 0x671080.
Vtable slots (18): 7 Enter, 8 / 9 per frame, 10 message, 11 query, 12 Exit, 13 interruption (Xbox same distance). ✅

| State | PC object | vtable / slots | TU | St |
|---|---|---|---|---|
| Land | 0x8ae808 | 0x858c5c; slot 9 0x65afe0 (LP <= 0 -> LandDeath at 0x65b1aa; LP > 0 + brain+0x11a0 bit 1 & !bit 2 -> Getup); slot 13 at 0x858c90 | slot 9 0x82328aa0 (T2), TU-only slot 13 0x82329060 | ✅ |
| Getup | 0x8ae82c | | 0x82779b20 | ✅ |
| Vaulted | 0x8ae8bc | 0x858e14; Enter 0x64fcf0 (= retail 0x8232cb18), anim end 0x64ff30 (calls death check), msg 0x64ffe0 (0x15..0x8a only) | 0x82779bb0; TU-only Enter 0x8232b630 (step chain, clock - 13.7); TU-only msg case 0xbe 0x8232be54 (next step / staged LP loss), slot 11 0x8232c068, Exit 0x8232b930 (not ported) | ✅ |
| Death | 0x8ae904 🔶 | 0x858edc; slot 7 0x66c500 (death event 31 via 0x66c310); slot 8 0x66c950 builds the chunkdoll | 0x8232cd50 | ✅ |
| LandDeath | 0x8ae928 | slot 7 0x66ccf0 | 0x82779c1c | ✅ |
| DrownDeath | | 0x66da90 | | ✅ |
| Attack / FinishAttack | 0x8ae970 / 0x8aeb20 | FinishAttack via 0x65c660 | | ✅ |
| MeleeAttack | 0x8aea00 | 0x85912c (13.5) | 0x82779cf4 | ✅ |
| Fall | 0x8ae79c | 0x858b34, slot 9 0x65adb0 (damage type 8) | | ✅ |
| RegenerateDeath | 0x8afa4c (object +0 = vtable 0x85b0d4) | 0x85b0d4; slot 7 Enter at 0x85b0f0 = **0x67ed20**; slot 9 0x67ee20 (clock >= wake -> Regenerate); slot 10 at 0x85b0fc = 0x682490 (only msg 0x11c, re-checks the list); slot 11 0x682510 (queries 0x184 / 0x183); slot 12 Exit at 0x85b104 = 0x67eeb0 | vtable 0x8206ea40, Enter 0x8235dff8, slot 10 0x8235e3a8 (TU-only), slot 12 0x8235e338 | ✅ (vtable read 08.11.: 0x67ed20 is the only reference, from 0x85b0f0. 0x67edf8 is not a function: it is the instruction inside Enter that passes tune+0x64 record +0x50 to 0x621cf0 - `Befund-Thrall-Felder-0611.md` called that site "Enter") |
| Regenerate | 0x8afa70 (object +0 = vtable 0x85b134) | 0x85b134; slot 7 Enter 0x67eef0; slot 10 at 0x85b15c = **0x682680** (msg 0x11c: brain+0xfe8 set and ShouldRegenerate 0x67f040 (call 0x6826d3) yes -> 0x614ee0 when 0x613be0(msg), else 0x65ac80(inst, msg, 1); msg 0x15: state flag + 0x671c10); slot 11 0x67efe0; slot 12 Exit 0x67ef80 | slot 10 0x8235e998 | ✅ (vtable read 08.11.; the mapping "TU 0x8235e998 = PC 0x684b80" in `Befund-Thrall-Felder-0611.md` is wrong: 0x684b80 is a function pointer stored by a table selector at 0x684e42 (next to 0x6848d0), not referenced from any state vtable) |

`IsInDeathState` 0x640e90 (Death, LandDeath, DeferredInstantDie, DrownDeath, Fade; TU 0x82324700). Death switch 0x641650
(cdecl, 7 args, `EnemyDeathSwitchData` 0x20 B, +0x14 kind; TU 0x823258c8); death kind from 0x613b40 (type 4 -> 7, 0xe -> 0,
else 5). ✅
Its end 0x64170b calls 0x63d6e0(inst, Death 0x8ae904, &data, 0) (= retail 0x8230e290): `ecx = brain+0x1254`, request
{data, 0x8588b8 "EnemyDeathSwitchData", 0x20} -> 0x671d30 (thiscall, ret 0x14; = retail 0x82349b90 = TU 0x82349468):
0x671080 files the request (al = result), then unless the current state's vtable +0x40 (inst, 1) refuses, machine+4 |= 1
and 0x671c10(inst, brain+0x11e0, 1) switches at once. The TU death switch inlines 0x8230e290 - same callee and arguments,
otherwise only stack offsets / shifted constants with equal values: **no port needed** (10.11., disassemblies
`work/asi/combat069/analysis`). TruShadowCombat 0.6.9 logs every switch (entry hook 0x641650, state before / after the
call, caller) and the Death state's chunkdoll build (call 0x66c9f9) with `[Death] Log`. ✅ static; live ⬜

### 13.3 Damage (K14)

| Item | PC | TU | St |
|---|---|---|---|
| Damage function | **0x637590** cdecl 7 args (inst, vec, f amount, reset, **type** `[esp+0x14]`, subtype, flags*: bit 0 death check, bit 1 stamina); brain+8 bit 0x800 returns at once | 0x822f60e0 | ✅ |
| Type switch | `cmp esi,0x10` at 0x637619, byte table 0x6376c4 (operand 0x637625), jump table 0x6376b8; A damage + death check 0x637630, B stamina 0x637685, C nothing 0x6376b1 | bound 0x1b, word table 0x822f61e4 (28 entries); 17 -> nothing, 18..27 -> A | ✅ |
| Type names | 0 Light, 1 Medium, 2 Heavy, 4 Explosion, 6 RigidBody, 8 Falling, 10 Fire, 11 Stamina (B); C: 3, 5, 7, 9, 12, 15 | Lara DLC 2: combo 18..25, shadow moves 26 / 27, shadow step 17, finisher 1 / 4 (DTP 20212, `tools/chart_attack_damage_types.py`) | ✅ |
| Health component | 0x62e370: mask bit `+0x1c + (type>>5)*4` absorbs; else LP (+4) -= amount, +8 += amount; then 0x62e180; stamina 0x620ea0. One-hit-kill cheat byte 0xe91ffd | 0x822f90b8 | ✅ |
| Hit message 0x11c | 0x63aaa0 (from 0x63ad50): type = msg+0x50, subtype +0x64, arg +0x6e. Builder 0x63c9b0 (0x80 B, 22 args). Lara senders 0x6e6840, 0x71917d, 0x71d871, 0x75519e | | ✅ |
| Kill | 0x6376e0 (amount = LP, flags 3; from 0x63831c, type 6) | | ✅ |

Effect on PC without the fix: thralls never die (DLC 2 hits 18..27 do nothing; live 06.11.). Plugin TruShadowCombat
`[Damage] Translate` (entry hook 0x637590, bound 0x63761b 0x10 -> 0x1b, table operand 0x637625), default on since 0.6.3:
**live 07.11.** (-40 per hit, thralls die, the hall02 wall breaks) ✅. Source: `Befund-K14-Schadensarten-0611.md`.

### 13.4 Death check, ShouldRegenerate, companion (T1-T5)

State flow on PC (✅): damage A -> **death check 0x620380** (TU 0x822f6578; guards: brain, brain+0xc bit 1 off, `IsDead`
0x620350 LP <= 0) -> **ShouldRegenerate 0x67f040** (TU 0x8235ece8; called at 0x6203e4): needs anim id +0x22 or +0x26 !=
0xffff in the tune+0x64 record (0x614610) and a match in the list (+0x64 count, +0x68 entries of 12 B {type (-1 any),
subtype (0 any), flag bit 0}) -> yes: EnterRegenerateDeath 0x682780 (called at 0x6203fb) / no: death kind 0x613b40 ->
death switch 0x641650. Regeneration data +0x28 = lying time in ticks (yeti 300, tutorial viking 210).
Hits while lying: RegenerateDeath slot 10 -> 0x614ee0 sends msg 0x3e to up to 4 attached instances.

TU changes ✅ static: **T1** ShouldRegenerate checks the companion list first; **T2** Land with LP <= 0 + companion +
extension byte +0x18 == 0 -> notify 33 + RegenerateDeath (TU 0x82328d24..d78), else LandDeath as PC; **T3** notify 33 in
the death check, no switch while in Land (0x822f6654); **T4** the companion instance; **T5** hit reaction 0x823038d8
(= retail 0x82305d40, PC 0x63ad50, cdecl inst, hit data, a3, a4 -> float amount): the TU inserted at 0x8230390c..0x82303a78
"companion exists + LP <= amount (+0x4c) + ShouldRegenerate no" -> hit direction (normalised, z = 0; type 0x19 crossed with
(0, 0, -1)) -> death switch 0x641650 kind 7, return the amount (no damage message, no hit animation); reads no extension
field. TruShadowCombat 0.6.6 `[Death] TranslateT5` (jmp at 0x63ad82, 7 bytes): built; ✅ live 2026-11-09 (`0.6.6 T5:` lines
20:43:56 / 21:52:38.835 / 21:54:13.953, death switch kind 7).

**Companion instance (T4)**: TU-only 0x822da800(inst, brain) from the enemy init 0x822da970 (PC twin 0x63c190, after
`call 0x615850` at 0x63c21b) walks the object's child id list through the object table, takes the first object with data
type **0x3d**, creates a child instance (0x82272998 = PC 0x5bd270), attaches it (0x8226f5c8) and stores the handle in
brain+0x5090 / +0x5094. Reader 0x822da918 (47 uses in 38 TU functions) returns `[[h]+0x50]`. On PC the children load but
no instance exists. Companion objects: 870 (viking + tutorial viking), 932 (yeti), 944 (armoured yeti); 1007 is a
chunkdoll, not a companion. ✅ Plugin: TruShadowCombat 0.6.5 `[Companion] Translate` (stateless lookup in 0xdb7400 on every
use), `[Death] TranslateRegenList` (calls 0x6203e4 / 0x6824b9 / 0x6826d3), `TranslateLand` (jmp 0x65b181, slot 0x858c90),
`TranslateNotify34` / `TranslateNotify38`: built; the companion lookup is ✅ **live 08.11.** (870 found for a hall02
tutorial thrall), the rest live ⬜. The 6 places that use the companion instance itself (bit 0x20 in
+0x14 on death / removal) are not rebuilt ⬜.

**Extension data (type 0x3d)**, root DTP+0xc8 -> +0xf0 ✅: +0 {u16 1, u16 0x3d}; +4 u16 0xb00b; +0xc u8; +0x10 / +0x14
anim pairs; +0x18 u8 (T2); +0x1c u8; +0x20 / +0x24 step table (0x14 B entries); +0x28 / +0x2c hit records of 0xc4 B per
damage type (extra f32 at +0x40); +0x30 / +0x34 {kind, f32} pairs; +0x38 u8; +0x3a / +0x3c anim pair; +0x40 / +0x44
regeneration list. Converter errors (u32-typed u16 pairs, counts 0x000f0000, anim id 108 remapped as object id -> 124):
`tools/thrall_extension_fix.py` (proof on 61 TU + 5 PC instructions, 9405 words, 0 contradictions; 771 words fixed); pipeline
step `thrallext` since 08.11. (section 2). Sources: `Befund-P1a-ThrallTod-0711.md`, `Befund-P1d-Begleiter-0711.md`, `Befund-N4b-Extensions-0711.md`,
`Befund-Thrall-Felder-0611.md`.

**Attack coordinator, CombatStepIdle, stamina (2026-11-09, static, TruMenu 0.22.9 diagnosis)**: attack slots are
requested through **0x67d780** (thiscall (record, enemy instance, -1 / 0), ret 0xc; al = 1 holds / got a slot, 0 refused;
inside 0x67a2e0 registered?, 0x67a270 already holds?, 0x67b800 try, 0x679080 + 0xf78 slot data); callers 0x63a731,
0x64fefb, 0x65b9f9, 0x65bd26, 0x673981 (the coordinator object comes from 0x6792f0). Which caller belongs to the idle ->
attack decision and the slot count are not read yet ⬜. `CombatStepIdle` = object 0x8aee5c, vtable 0x859c74 (7 Enter
0x66d300, 9 Update 0x66fb60, 10 message 0x643e40, 11 query 0x670430, 12 Exit 0x5b4d90, 13 interrupt 0x670440); its update
reads the target slot brain+0x4e40 (+4 mode: 0 sense handle +0x28 via 0x63fae0, 1 0x653b60 path), calls 0x61fee0(inst)
and the range test 0x6601b0 (EnemyTargeting brain+0x4e10; failing -> nothing this frame), then enemy type 5 checks
(0x60d700 on the state data +0x6c / +0x74, query 0x15c) ⬜ meaning. Current target getter 0x60e420 = EnemyTargeting+0x30
-> 0x653b60. Health component brain+0x2c60: +0 instance, +4 LP, +8 taken, **+0xc stamina** (0x620ea0 subtracts, clamps
at 0 via the tune's +0x3c chain). Lara's chart machines: `[[0xfadb58]+0xf10]` / `+0xf14` (update 0x787e60 called at
0x768c65 / 0x768c6c), current record `[machine+0x510]`. Melee link fix (`meleelink`) present in the installed
viking_thrall_dlc2_ / viking_thrall_tutorial_dlc2_ (check 09.11.: 0 findings). ✅ static

### 13.5 MeleeAttack and combo link records

| Slot | PC | TU |
|---|---|---|
| 7 Enter | 0x65c7b0 | 0x8232fb48 |
| 9 Update | 0x665f10 | 0x82330220 |
| 10 Message | 0x666350 (jump table 0x66672c, byte table 0x666764, index msg-0x15) | 0x82330d40 |
| 11 query 0x15f | 0x643010 | |
| 13 Interrupt | 0x642f40 (only if record+8 bit 2, target is a death state, or Fall / Land / FinishAttack) | 0x82330830 |

Messages ✅: 0x15 (anim callback kind 1), 0x8a, 0xbe end the attack (data+0xa4 = 2); 0x27 -> FinishAttack; 0xe0 hit event;
0xcb / 0xd1 set / clear brain+0xc bit 0. Update: hit window, damage to Lara 0x642d80 -> 0x63a8f0; exit when +0xa4 == 2 or on
timeout (record+0x136 >= 0); at exit record+0x146 > 0 -> FinishAttack, else follow-up **0x65bc10** (TU 0x8232e0c0): record
+0x1c0 / +0x1c4 -> Attack, +0x1c8 -> MeleeAttack again with the linked record (coordinator 0x67d780 must give a slot).
Selection 0x635150. Record: +8 flags (bit 2 interruptible, bit 24 -> brain+8 |= 0x800000 via 0x6224c0), +0x78 / +0x7c /
+0x80 anim refs {u16 type (1 = object anim list index, 0x4325d0), u16 anim}, +0x88 windup anim, +0x148..+0x152 cooldowns,
+0x218 count + s16 list. Stride 0x228 measured (docstring says 0x21c + list) ⬜.
The running attack's record sits at **state data+0x50** (Enter stores it at 0x65c804, after the state data address
`(brain+0x1273 + ([brain+0x18d4+4*layer] + 2*layer)*0x19c) & ~0xf` at 0x65c7df..0x65c7f9) - TruMenu 0.22.11 `pc_attack`
logs it with the three anim refs, to tell melee attacks (and the thrall spit attack, Xbox X22) apart. ✅ (bytes; live ⬜)
TU changes: **T-M1** 0x15 / 0x8a / 0xbe end only when the data pointer is 0; **T-M2** Enter sets brain+0xc bit 0 when
record+8 bit 2 is clear (PC site 0x65c9ea); **T-M3** Vaulted and (with companion) RegenerateDeath may interrupt. Plugin
TruShadowCombat 0.6.4 `[Melee] Translate`, 0.6.5 `TranslateInterrupt` (slot 0x859160): built. Meaning of brain+0xc bit 0 ⬜.
**Freeze = data bug** ✅ data: link-only records typed u32 (viking DTP 24426 +0x4290 anim {50, 1} instead of {1, 50}; yeti
24577 / armoured 24890 +0x493c); `tools/melee_link_record_check.py` / `melee_link_record_fix.py` (22 base pairs, 0
contradictions); pipeline step `meleelink` since 08.11. Sources: `Befund-P1b-MeleeAttack-0711.md`, `Befund-Thrall-MeleeAttack-Freeze-0711.md`,
`Befund-Melee-Kombo-Datenfix-0711.md`.

### 13.6 Chunkdoll (type 0x3b) and the physics pool

| Item | PC | TU | St |
|---|---|---|---|
| Data D = `[[object]+0xc8]` | +0xc f32 lifetime (DLC 2 7.5 s, base 20 s), +0x10 / +0x14 / +0x18 min / droppable / count, +0x1c records 0x14 B {u8 model, u8, s16 bone A, s16 bone B, f32 lerp, u32, flags} | | ✅ |
| Create chunkdoll | 0x696f90; limit `cmp [0xecfc70], 4` at 0x696fa8; pieces 0x697070 -> 0x696b90 -> birth 0x5bd270 -> body 0x48ea80 / 0x497270; no body -> fatal "ChunkDoll: failed to create geom" (0x85cf4c) | 0x823766c0, limit 8 | ✅ |
| Callers | 0x624d06 (impulse handler), 0x66c9f9 Death, 0x66cdca LandDeath, 0x66db82 DrownDeath | | ✅ |
| Death state chunk branch | 0x66c950: after the state timer, record = 0x614610(brain+0x168) (tune chain +0x1c, first +0x64), record +0x46 != 0 -> 0x696f90(inst), +0x48 != 0xff -> 0x6a5dd0, +0x4c > 0 -> 0x6970d0 (push the pieces); the impulse handler 0x624cc0..0x624cfe tests the same record | 0x8232cd50: same order (0x822d3d38, +0x46, 0x823766c0, 0x82399b48, 0x823768a0); TU-new 0x8232cf20..0x8232cf50 also sets +0x14 bit 0x20 on the companion instance (brain+0x5090) | ✅ static |
| Physics system `[0xa037f4]` (0x2120 B) | 405 bodies, 1200 geoms, 300 joints (same on all exes); lock +0x20f8: `PhysicsSystem::Step` 0x4f0ab0 sets 3, ORs 8; AllocBody 0x4e9590 returns 0 while locked; FreeBody 0x4e9610 silently refuses while locked | | ✅ |
| **Crash root cause** | step -> pair callback 0x492980 -> msg 0x26 to Lara -> CombatManager 0x719050 sends 0x11c then **0x91** -> enemy handler case 0x91 -> impulse handler **0x624c60**: LP <= 0 + chunk record -> chunkdoll **inside the physics step** -> fatal | 0x82305ba0: no immediate chunkdoll; hit vector 0x656430, then death switch kind 7; the Death state builds it later | ✅ live 07.11. (lock = 3, 13 / 405 bodies used) |
| Leak | 0x48ea80 clears inst+0x274 even when FreeBody refused | | 🔶 |

Plugin TruShadowCombat 0.6.1 `[Chunk] Translate` (6-byte jmp at 0x624caa): built. Data errors (model bytes in DTP 24559
/ 26190): `tools/chunkdoll_records.py`, `chunkdoll_record_fix.py` (pipeline step `chunkrec` since 08.11.). Limit 4 -> 8 (`cmp [0xecfc70], 4` at 0x696fa8; TU 0x82376700 `cmpwi r11, 8`;
the counter has no array, only inc 0x6970b8 / dec 0x696e5c): TruShadowCombat 0.6.7 `[Chunk] Limit8` (built), after
the 0.6.1 translation caught 5 lethal impulses inside the physics step live on 09.11. without a crash.
Log point TruShadowCombat 0.6.9 (built, offline): the Death state's call 0x66c9f9 (cdecl inst, al = built; record in
edi) -> `0.6.9 chunk build: ... record +0x46 / +0x48 / +0x4c -> BUILT / not built; count [0xecfc70] a -> b, physics lock`
(`[Death] Log`).
Sources: `Befund-ChunkDoll-Absturz-0711.md`, `Befund-ChunkDoll-Physikschritt-0711.md`.

### 13.7 Finisher, Vaulted, shadow strike, splash

| Item | Fact | St |
|---|---|---|
| Finisher 1013 | condition 2011 -> chart record #741 [1004, 1013] -> state 1013 slot 0 0x75e090 -> 0x71d600 (TU 0x823e0a88): hit record 0x63c9b0, message record 0x645de0 (0x40 B), sends **0xf4** | ✅ |
| 0xf4 | handler 0x63b330 case at 0x63b44b -> 0x623f50 -> Vaulted (`EnemyVaultedSwitchData`; TU also stores +0x44 = msg+0x3c) | ✅ |
| 0xbe | sent only by the shadow strike 1014 (TU enter 0x823d8978 -> 0x823d86a8, tick 0x823d8d18); 1013 sends none, so "the finisher does not kill" is not explained by 0xbe alone | ✅ |
| Targeter 9 | chain TU = PC; data DTP 22497 (`tuning_target_fix.py`); why the list was empty ⬜ | ✅ / ⬜ |
| MeleeSplashDamage (K9) | 0x6e68b0 (TU 0x823e1220): doppelganger mode remaps 0x1a -> 0x10, 0x10 -> 0x16 via the 858 table (+0x78 / +0x7c); always skips the main target CM+0x48 in area function 0x69f1e0. TruShadowCombat 0.6.2 `[Splash]` (0x6e692d, 0x69f224): built | ✅ static |
| Adrenaline (K11) | CombatManager::Update 0x7227d0 skips adrenaline tick 0x718bd0 and bar 0x6f2930 in doppelganger mode; TruShadowPower 0.18 `[Adrenaline] Translate`: built | ✅ static |
| Combat reticle (lock-on ring) | engine module game/player/CombatReticle.cpp (proto map: CCombatReticle, CCombatFadeReticle, playerDrawCombatReticle); no names in the PC exe. **Draw chain (retail = PC, same gates):** GAMELOOP_DisplayGameElements 0x8229bbd0 / 0x5da15c -> PLAYER_DrawIndicators 0x82415858 / 0x7212d0 -> playerDrawCombatLock 0x823dc120 / 0x71e710 (TU 0x823de170) -> playerDrawCombatReticle 0x823dfbb8 / 0x7037d0; the engine only feeds the HUD (style 0xfae8ac, position 0xfae8a4 / a8, more 0xfae8ad..bc, HUD group 12 = 0x77d9d0(12) + (*0xfae920)->vtbl[3]), HUD script 37 draws it. **Request:** a target (player +0x544 or sense search 0x71d0c0) and (CM+0x1fc bit 9 or 10 (helper 0x6f1ed0) or bit 21) - PC 0x71e966..0x71e981, edi = CM+0x1fc; TU 0x823de47c..0x823de4a4: in doppelganger mode (`[0x829892b0]+0x1244`) **meter flag 2** (`[+0x508]+4` bit 1, the shadow strike) instead of bit 21 - TruShadowPower 0.22 `[Reticle] TranslateRequest` (5-byte jump at 0x71e979). **Refill** (PlayerSM::DefaultMessageHandler TU 0x823ed958 / PC 0x71f1d0): case at PC 0x71f4f4 skips by bit 21 (TU 0x823ee158: meter flag 2 in doppelganger mode), rest out of line in PC 0x6f28c0 (bit-22 gate, CM+0x3c += value, HUD value 0xfae8d4 / group 1); full -> **PC 0x6e6630 = TU 0x823dfd98** (leaf, no .pdata; also the body of script native 0x777a50): CM+0x3c = max, then bit 27 (TU: meter flag 0x40 in doppelganger mode) -> return, else CM+0x1fc \|= 0x400000 + bytes 0xfae8af = 1 / 0xfae8d8 = 0 - 0.22 `[Reticle] TranslateRefill` (0x71f500, 0x6e6646). Retail 0x823de058 = PC 0x715020 = the retail strike look (anim event 5; CM+0x1fc bit 21 && !bit 29, event 0x32, 0x823e0540 = PC 0x70db20, render flag 0x200); TU 0x823e0308 adds a doppelganger branch (meter flags 2 / 4), but its only caller 0x8240a430 case 5 calls it only when +0x1244 is 0 (else 0x823d8a80) - dead on the Xbox, not ported. Retail 0x823e0540 is not ProcessReticles (reticle method: HUD groups 1 + 11, reticle +0x40 bit 6); TU 0x823e2b98 takes an optional position (0 = retail body). Still open: TU 0x823eebc0 (message 0x200003d = PC 0x71fa40 ends at once in doppelganger mode; PC sets CM+0x1fc bit 0 + player event 0x3c); the ring **without** the power (aiming, record 718: code retail = TU = PC) - live read of CM+0x1fc bits 9 / 10 / 11 / 21, `[0xfae924]` bit 12, 0xfae8ac. reticleDrawData = retail 0x82988b40 / PC 0xfad768. Sources `Befund-Anvisier-Kreis-0911.md` section 6, TruShadowPower README 0.22 | ✅ static; 0.22 built, live ⬜ |
| Lock-on path (aiming, record 718) | P = `[0xfadb58]`, CM = `[P+0x504]`. **1 input:** action records `[[[0xa02b68]+0x18]+0]` + action * 0x30 (flag 4 = held, row "Input map"): **+0x630 = action 33 = RT**, **+0x690 = action 35 = LT** (PC generalbank DTP 47: action 33 <- source 4 = pad code 5, action 35 <- source 22 = pad code 4, `input_map_find.py`; XInput poll 0x484c06..0x484c47: bLeftTrigger -> code 4, bRightTrigger -> code 5); gates byte 0x8ab4e6 != 0, `[0xe7f144]` bit 0 clear, byte `[0xe7f143]` != 4; weapon slot `[[P+0x500]+0x134]` (-1 none -> false, 7 / 12 -> false, 3 / 4 -> true). **2 chart:** condition 506 (machine-1 table 0x8b2ce8, handler 0x763c50 -> predicate 0x6f2800, ecx = CM: true on weapon 3 / 4, CM bits 9 / 10 / 30 / 21 / 24, timer P+0x588 > 0 or action 33 (RT) held) takes record 38 (parent of 39 / 40) -> 709 `{500,506,1} {500,504,0}`, 709 -> 714 `{500,506,1} {400,401,401}`, 716 -> **718** `{500,506,1} {400,401,401} {400,403,415} {500,525,0} {2100,2102,3,NOT}` (DTP 20212 records 708-720 Xbox = PC, `chart_range_diff.py`); record 710 (parent of the aim records) runs activities **1001 / 1003 / 1004 = CM+0x1fc bits 19 / 18 / 20** (switch 0x767ae3, cases 0x767afa / 0x767b31 / 0x767b68; 301 / 302 = arm anims 0x37 / 0x38). **3 lock update** 0x7216b0 (CombatManager::Update 0x7227d3): bit 18 clear -> lock off 0x71ef60 (clears 9 / 10); bit 11 -> return; P+0x58c (= tuning byte `[0xfad764]+0x294` while LT is held) and P+0x588 (= byte +0x27c while RT is held with a weapon component 0x36; `[0xfad764]` = the player instance's data +0x50, set at 0x71adbd) not > 0, P+0x798 == 0 and bit 21 clear -> off; else bit 19 -> **lock 0x71edf0** (bit 10, clears 9; P+0x784 = 0; byte P+0x50f == 0 -> targeter 0 parameters = chart parameter 0x3f6 (0x7680a0) or `[0xfad764]+0x488` via 0x713540; flags & 3 == 0 -> select 0x716590 + set 0x716730; flags \|= 1; +0x94; then 0x71d0f0) or **soft lock 0x71ec50** (bit 9, clears 10). **4 target:** 0x71d0c0 = P+0x540 while P+0x788 > 0 (scripted), else `[[0xfadfac]+0]` (targeter 0) +0x90 node (0x719f00) - the ring chain 0x71e710 reads it. **TU vs PC:** TU 0x823de858 (= PC 0x71ec50, retail 0x823dc7e8) and TU 0x823de9f0 (= PC 0x71edf0, retail 0x823dc970) are equal to retail except one added call each **0x8247b0f0([0x829ca684], 0x1b)** (TU 0x823de9b0..0x823de9bc after the parameter call, 0x823deac4..0x823dead0 inside the "bit 10 was clear" block; a broadcast over a table of 0xc8-byte records, meaning not read; `tu_coverage.tsv` changed / open, 16 B / 76 B) - not ported, not on the acquisition path (inferred); TU folds PC's inline parameter / select code into 0x823de800 / 0x82404bf0 (same calls 0x82472a40(0x3f6) / 0x824053d0, 0x82405b90 / 0x82406190); TU player fields shift by +4 here (+0x513 = PC +0x50f, 0x544.. = PC 0x540..). The other functions on the path (0x7216b0, 0x6f2800, 0x763c50, 0x71d0c0, targeter 0x713540 / 0x716590 / 0x716730 / 0x719f00 / 0x71a270) have no changed-block entry (`xbox_pc_map` / `classes.tsv` pairs for them are layout / low and partly contradicted - not used). **Live 2026-11-10 13:30** (TruFight.log): bits 18 / 19 / 20 set (0x065f8010 while machine 2 is in record 48), 9 / 10 / 11 / 21 clear, machine 1 never left 38's children -> the lock update ran the off path, so all three aim timers were 0 and condition 506 stayed false. With LT held that means (inference, not logged): either action 35 never showed "held", or the gates blocked, or the player tuning byte +0x294 is 0 (P+0x58c = that byte) - `aim.trace` columns `act35_lt_held` / `tune294` / `t58c_lt` decide it. "Z9 abgelehnt F00" = targeter **9** (TU index 9, condition 2011), not the aim targeter 0. TruMenu 0.22.15 `aim.trace` / `aim.why` (read only, 25 byte checks); Xbox side: TruXenia reads CM+0x1fc and targeter 0 `[[0x829ca648]+0]` flags +8 / target node +0x90 (address file section `aim`, 9 proof words; docs/TRUXENIA.md "Lock-on path"). **Cause (live 2026-11-10 16:34, `aim.trace`: `act35_lt_held` 1, no gate, `tune294` 0, `tune27c` 15):** `[0xfad764]` is the player data block of the DLC 2 player object 857 (`doppelganger_casual` DTP 20212 +0xc8 -> +0x20ff0, row "Player data block"); its word +0x294 is four u8 (PC readers `movzx byte` 0x72170f / 0x75e15f +0x294, 0x75e17f +0x295, 0x75e19f +0x296), Xbox `08 00 05 00` (lock time 8), the converter wrote `00 05 00 08` -> byte 0 -> P+0x58c = 0 -> the off path every frame. Pipeline step `playerblock` (`tools/player_block_fix.py`) restores `08 00 05 00`; test file `work/fix_lock_1011/mods/doppelganger_casual.drm`. Source workspace `Befund-Zielerfassung-1011.md`, `Befund-Lock-Tuning-1011.md` | ✅ static; live ⬜ |
| Player data block (`[0xfad764]`) | = `[inst+0x50]` of the player instance (stored at 0x71adbd) = the target of the player object DTP's relocated pointer **+0xc8**; 0x1034 B up to the next record, air maximum s16 +0xf8 (4000). Base `lara` / `lara_casual` / `lara_bikini` / `lara_wetsuit_cold` / `lara_snow_light`: DTP +0x28f80 (PC lara DTP 850 / Xbox 12647); DLC 2 `doppelganger_casual` DTP 20212 +0x20ff0 (same layout: 959 of 1037 words in the base byte order). Fields read on the PC: **+0x25c / +0x25e s16** (`movsx word` 0x6ee71a / 0x6ee7d9; base 1 / 16), +0x27c u8 RT aim time (15) + u8 + u16, **+0x294 / +0x295 / +0x296 u8** (+0x294 = LT lock time -> P+0x58c; base 8 / 8 / 5, DLC 2 Xbox 8 / 0 / 5), **+0x2a8 / +0x320 u32 sound DTP ids** (0x71cf8b -> 0x5954b0; 0x71e2f0 / 0x71e326 on a lock-target change -> 0x594c60; base Xbox 1163 / 1164 = PC 964 / 965), +0x94 / +0x98 breath sound ids (step `objid`), **+0x70c u16 object id** (Xbox 68 = PC 52 `fx_saving_grab_prompt`), +0x488 targeter 0 parameter, +0x600 / +0x628 edge probe. Installed DLC 2 (08.11.) had 5 wrong words: +0x25c u16 pair as u32, +0x294 u32-swapped (no lock-on), +0x2a8 / +0x320 the untranslated Xbox ids 1163 / 1164 (no such section in the PC file; its DTPs are 964 / 965), +0x70c Xbox object 68 (= PC `bullet_hit_shotgun`). Step **`playerblock`** (`tools/player_block_fix.py`, after `dspkind`; `proof`: five base pairs leave-one-out, 4800 decided words, 0 contradicting, 4 id words, 1 object id word; READERS +0x294 = u8 where the base `08 08 05 00` also fits `s16b2`). Open: +0x1030 (base Xbox 0x3c -> PC 0x40 on all five pairs, DLC 2 0x3e unchanged; no PC reader via `[0xfad764]`, meaning unknown) | ✅ static; live ⬜ |
| TU combat addresses (Xenia reader) | instance list struct 0x828aaf18 (+0 count, head [0x828aaf1c], next +8); object [inst+0x10], id [obj+0x14], name [obj+0x60]; brain [[[inst+0x2d0]]+0x2ec] (0x50a0 B); state layer 0 / 1 [brain+0x125c] / [+0x1260], name [state+8]; LP [brain+0x2c64]; stamina [brain+0x2c6c] (meaning from PC); Lara tracker [0x829892b0], chart machines +0xf10 / +0xf14, record **+0x520** (PC +0x510). `docs/data/xenia_tu_combat_addresses.json`, read-only sampler `tools/xenia_combat_sampler.py` (21 proof words checked before reading). State slot block (TU switch 0x82349600): raw = sm + (slot + 2*layer)*0x19c (sm = brain+0x1254), data passed = raw+0x10, state object at **raw+0x1a8** (0x82349704); MeleeAttack's own data = (raw+0x1f) & ~0xf (record +0x50) - with a 16-aligned brain the aligned data+0x198 is 4 bytes before the state object (TruXenia showed `?(data)` live 09.11. until fixed) | ✅ static; live 09.11. |
| TU brain shift / more TU addresses (TruXenia) | **The TU brain is shifted by +0x50 between +0x2c90 and +0x3780**: retail brain ctor 0x822d7af8 (= PC 0x634020) members +0x3780 / +0x3ec0 / +0x4600 / +0x4e10 = TU ctor 0x822d50a0 +0x37d0 / +0x3f10 / +0x4650 / +0x4e60 (same member ctors); so TU EnemyTargeting = brain **+0x4e60** (PC +0x4e10; ctor 0x82341868 instruction-equal to retail 0x82341f98). Requested state TU brain +0x18f8 (= PC; 0x822f1448 compared with the same state objects as +0x125c); coordinator requester +0x2fc4 (33 uses in retail and TU, not proven). GameTracker TU 0x82efb458: +0xc player instance, +0x100 scaled dt, +0x118 world time scale (cloth code 0x822781dc..0x822781f4). Player tracker [0x829892b0]: +0x504, +0x508 meter object (+4 flags: 1 active, 4 look; +8 value, +0xc start value - tick 0x823d7a10), +0x1244 doppelganger byte (predicate 0x8246e400). Not proven: target slot internals (position + Lara's LP: row "TU TruXenia stage 1b"). Menu + link `tools/truxenia.py` (docs/TRUXENIA.md) | ✅ static; live ✅ (09.11.) |
| TU TruXenia stage 1b (positions, attack, Lara, RegenerateDeath) | Instance +0x20 position (3 f32), +0x44 allocation stamp (TU 0x8238d384 / 0x82355158). **Enemy test** TU 0x822da9ac: `[inst+0x50]` word 0 == 0xdaf00018 and byte +0x18 != 0 -> brain allocated (= PC 0x63c1b5). **MeleeAttack** TU Enter 0x8232fb48: data = (brain+0x1254 + (slot + 2*layer)*0x19c + 0x1f) & ~0xf, slot = [brain+0x18d4+4*layer], record at data+0x50 (= PC 0x65c804; section 13.5), self-check data+0x198 == state object. Coordinator: Enter 0x8232fce8 passes brain+0x2fc4 to 0x823551b0, handle {+4 instance, +8 stamp} checked by 0x82355138, target slot manager 0x82354938()+0xf78; what it grants ⬜. **RegenerateDeath** state object 0x8277a7b8 (vtable 0x8206ea40), Enter 0x8235dff8: LP := tune maximum (0x822f8c18), so a hit in RegenerateDeath removes the restored maximum (the finisher). Lara LP = player tracker +0x628 (max +0x630, previous +0x634; TU 0x823e8068 = PC GetHealth 0x6e7860). Object table TU 0x82979280 (= PC 0xdb7400, 0xcc x 0x24; TU 0x8214684c). 91 proof words in `docs/data/xenia_tu_combat_addresses.json`; vtable owner finder `tools/xbox_vtable_owner.py` | ✅ static; live ⬜ |
| Hit struct selector / decision (K-1) | PC 0x6159a0 (= retail 0x823042a8, cdecl &s, msg, D): struct for damage types 0..16 only (D = [enemy root+0xd4], jump table D+0x50 / +0x104 / +0x1b8 ...; msg+0x6e -> D+0x53c; 0x613c70(msg, s) -> D+0x758; returns bit 30 of s+0x14); types 18..27 (Lara DLC 2 melee) get none. TU 0x82301dc0 (+ instance r6) first searches the companion's hit records ([comp+0x2c] count, [comp+0x28] base, 0xc4 B each, +0 type == msg+0x50 -> s = record+0xc), then the table; redirect / return unchanged. Callers: PC 0x623429 (decision 0x623410, inst = arg 1), 0x63b157 (hit reaction 0x63ad50, esi), 0x64f338 (in 0x64f230 = TU 0x82329810, which got the instance as a new argument; callers 0x6206e3 knockback / 0x64f5ad / 0x65215d). Decision 0x623410 (TU 0x82301fc0): no struct -> heavy; struct: flag 0x10000000 required, amount < 1.0 needs 0x20000000; else light 0x65ac80 (MoveHit). Hit reaction: decision call 0x63b183, heavy -> knockback 0x63b19a. Extension 870 records: types 18-27 + 0 / 1 / 2 / 4 (Xbox = PC, `tools/thrall_hit_records.py`). TruShadowCombat 0.6.7 `[Hit] Translate` at 0x623429 / 0x63b157 / 0x64f338 (the last only on the knockback path) | ✅ static; live ⬜ |
| Knockback force (K-1) | PC 0x620650 (= retail 0x822f9990, TU 0x822f73a8; cdecl inst, msg, ...; ebp frame): factor `fmul qword [0x8415e8]` (3.0) at 0x620940 and `fld dword [0x845338]` (-3.0) at 0x620971 for the call 0x60eeb0; TU: record +0x40 of the companion hit record of msg+0x50 (0x822f77e4..0x822f783c, default [0x820526e8] = 3.0), negated for the second call (0x822f7894); extension 870: 3 (18-20, 22, 25), 9 (26), 12 (21), 18 (23, 24, 27). **Speed** (2026-11-10, K-8b): v = `(int)` msg+0x44 (`fild [edi+0x44]` 0x620716) when > 0, else the hit record's s+0x30 (0x62072e); v <= 0 -> end at 0x62073e (TU 0x822f74c8..0x822f74f8, the same) - without either no knockback; records with s+0x30 = 0 (types 21, 26) knock back only with Lara's force in msg+0x44 (TU sender, TruShadowCombat 0.6.10). Not ported: type 25 sideways with a companion (0x822f7558..0x822f75bc, only for msg+0x50 = 25). brain+0x1254 \|= 1 (TU 0x822f788c) is no gap: the PC does it too (0x62096c -> 0x617550 = `or [brain+0x1254], 1`). TruShadowCombat 0.6.7 `[Hit] TranslateKnockback` | ✅ static; live ⬜ |
| Impulse gate of Lara's contact hit (K-1b) | Sender PC 0x719050 (thiscall, ecx = edi = CombatManager; ebx = hit instance, `[ebx+0x14]` bit 0x400000 -> `[ebx+0x4c]`; attack data A = [edi+0xc4]): A+4 > 0 -> hit message 0x11c (builder 0x63c9b0 at 0x71917d: msg+0x50 = A+0xc type, msg+0x54 = -1 fixed at 0x71914d, msg+0x64 = **2** fixed at 0x71914b = subtype; msg+0x40 / +0x48 / +0x44 = 0 at 0x719169 / 0x71916b / 0x71916d - the TU passes 0 / (int) A+0x14 / (int) A+0x10, K-8b row above, TruShadowCombat 0.6.10). A+0x10 > 0 -> special body hit: message 7 (0x48e2e0), jmp 0x719398; else **0x7192da: impulse 0x91** to ebx (send 0x71938c), then 0x719398; FPU empty and esp equal at 0x7192da / 0x719398. TU 0x823e1870..0x823e1884 (hit 0x823e1738, impulse 0x823e1920) inserted `[[r28+0x10]]+4 & 0x00400000` -> 0x823e1934 (= PC 0x719398); retail 0x823df318 has no such test. Impulse receiver 0x624c60 (TU 0x82305ba0) throws a living enemy up (0x656430 -> 0x60eeb0) -> **Fall** (PC 09.11.: 12 Fall, 0 Hit, 0 knockback lines). The flag is set on the thrall (MoveHit precondition 0x620440 tests the same bit; inferred). Knockback 0x620650 stops at s+0x20 = 0 (types 18 / 19 / 20 / 22 / 1) on both platforms. TruShadowCombat 0.6.8 `[Hit] TranslateImpulseGate`: 5-byte jump at 0x7192da, 7 byte checks. Source `Befund-K1b-Entscheidung-0911.md` | ✅ static; 🔶 flag on the thrall; live ⬜ |

Plugin switches (off by default): `[States] Translate1013`, `[Strike] Translate`, `[Strike] Gate`.

**Vaulted step chain (P1c)** ✅ static: the TU-only Vaulted Enter 0x8232b630 reads a new switch-data field **+0x44 =
companion step**, fed by six links: F retail strike record (PC 0x71d5cc -> 0x645e40) +0x34 = 0 (TU 0x823e0294); E finisher
1013 record (0x71d895) +0x3c = 0 in every mode (TU 0x823e0e84); A enemy message case 0xbe (0x63b421 -> record copy
0x645de0) copies incoming +0x34 to +0x3c (TU 0x8230743c; the TU shadow strike writes its step there); B Vaulted switch
from a record (0x623fa2 -> 0x60ed80) data +0x44 = record +0x3c (TU 0x823044dc); D Vaulted slot 3 copier (0x65a4a2 ->
0x64d350) copies +0x44 (TU 0x8232300c); C Enter (0x64fdb9): state data +0xb8 = step, companion -> brain+0x2c7c =
0x0fffffff; step 0 = the PC's own animation choice, step n = companion step table entry `[comp+0x20] + (n - 1) * 0x14`
when n <= `[comp+0x24]`, else no animation (TU 0x8232b3f8). The step table is only valid in the fixed extension layout
(13.4); the installed converted files fail it (count 0x000f0000).
**Vaulted clock** ✅ static: Enter (TU 0x8232b698) sets brain+0xc bit 0x10, clock = ms counter 0xe7f15c, time multiplier
0xe7f188 /= slow-motion factor 0xe7f1a0; the enemy update (PC 0x638d40, TU 0x822db190) saves the multiplier, keeps
multiplying by 1 / factor while the bit is set and clears it after **5000 ms**, restores at the end of the main path (TU
0x822db4e0, not on the brain+8 bit 0x20000 exit 0x822db364): an enemy knocked into Vaulted runs 5 s at normal speed during
shadow slow motion. Not ported: script commands 0x822d6844 / 0x822d6880, Vaulted slot 10 case 0xbe, slot 11, Exit, the
strike's step queries 0x165..0x167 (TU 0x82308850), the rest of RegenerateDeath / Regenerate slot 10 (needs the TU's
2-byte state data +8 / +9 that the PC state lacks). Plugin TruShadowCombat 0.6.6 `[Death] TranslateVaulted` (all six links
or none) / `TranslateVaultedClock` (default 1, read again at run time): built, live ⬜. Sources: `Befund-15h-Absturz-Finisher-0611.md`, `Befund-TU-K9-K11-0711.md`,
`Befund-Finisher-Thralls-0511.md`, `Befund-Schattenkampf-0411b.md`.

### 13.8 Perception and brain+8 gate bits

Pipeline ✅: EnemySensesControl::DoProcess 0x6647c0 (brain+0x170, vtable 0x85a3cc) -> filter 0x64c040 -> **AddToSenses
0x659bd0** (call sites 0x6648bb, 0x659d8f, 0x664a64); noise handler 0x623d40 (msg 0xbf) bypasses it via 0x653cf0;
EnemySense::DoProcess 0x664e80 (vtable 0x85a2f8), RemoveSense 0x65a140; EnemyTargeting 0x66ea00 -> select 0x6695d0; Lara
pointer `[0xe7f094]`; msgs 0x117 / 0x11f -> AddTarget 0x659d60.
brain+8 bits (✅ static, live ⬜): 0x20 no attack (msg 0x178), 0x80 no investigate (0x6370d0), 0x800 / 0x1000 msgs 0xda /
0xde (0x800 = damage immune), 0x100000 no melee, 0x800000 record bit 24 / 0x91 gate; intro-flag mapping 0x63c88b..0x63c920.
Plugin TruMenu 0.19 "dumb AI" `[AI] Dumb` / `NoInvestigate` / `NoAttack`. Source: `Befund-Gegner-Wahrnehmung-0611.md`.

### 13.9 Enemy animation, AI pause, puppet (N22 animation lab)

| Item | PC | TU | St |
|---|---|---|---|
| AI pause bit brain+8 **0x20000** | EnemyProcessFunc 0x638e76 (`shr 0x11`) returns before the behaviour tree 0x672500, the state machine 0x6722e0 / 0x670ff0 / 0x671b10 **and the anim controller 0x638570**; health regeneration and the kill plane (0x638d7c..0x638e72) still run. Set by the state machine's own 0x671470 (thiscall ecx = brain+0x1254, arg inst), cleared by 0x671410 (also resets the clock SM+0x9e4 / +0x9ec); wrappers 0x618ab0 (AI off, also `[inst+0x244]` vf+0x38(0.0), brain+0x11a0 bit 0 off; called at the end of FallDead / Death / LandDeath) and 0x618a40 (AI on; caller 0x655ff0). Other readers only 0x634d0e / 0x65601c | 0x822db358..0x822db364 (`rlwinm 15,31,31`, same exit) | ✅ static; live ⬜ |
| Anim controller brain+**0xc70** | queue 0x626f10 (thiscall; rec {u16 type, u16 index}, slot, restart byte -> mask +0x374 bit, a5 -> +0x1dc, f blend -> +0x384 (< 0 = tune +0x10), f -> +0x398, byte); per slot s: request +0x1c6+4s / **+0x1c8+4s** (0xffff = none), owner inst +0x3bc; type 1 refused when entry speed +0x14 == 0 (0x626f45) or the anim is not resident (0x616850 -> 0x5b4290 null). Apply 0x617b40(inst, s) from the update 0x638570: processor `[[inst+0x280]+0x14] + s*0x320` -> 0x444ba0(proc, &req, 0), then copies the request to the **current record +0x1b2+4s / +0x1b4+4s** and clears +0x1c8 (0x617df4). Entry 0x6276c0(inst, rec, slot, restart, a5, f blend, f, a8) = `brain+0xc70` -> 0x626f10; 70+ state callers (Puppet Enter 0x6438d8: (inst, rec, 0, 1, 0, -1.0, 1.0, 0)) | queue 0x822d8100, apply 0x822d8260 (writes +0x1b4 / +0x1b2 at 0x822d8860 / 0x822d8864), update 0x822d8880 called with brain+0xc70 at 0x822db440; same offsets | ✅ static |
| Anim slot list (bound of every type-1 request) | 0x4325d0(inst, i) (TU 0x820d8b20): 0 <= i < u16 `[Object+0x38]` (= object DTP +0x5c), entry `[[Object+0x58]] + i*0x24` (= DTP +0x60). Entry: +4 / +8 u16 list + count, +0xc / +0x10 4-byte list + count (used when +0x10 > 0), **+0x14 u16 speed 4.12** (0x1000 = 1.0; `* [0x843078]` = 1/4096 at 0x444c73 / 0x617c8c). List item = **table index** k -> 0x5b4290: `[Object+0x44] + k*12` {u16 section id, s16 run-time slot} -> loaded anim `[0x8c1244 + slot*8]`. So record indices (melee +0x78 ..) are **slot** indices: viking / tutorial 111 slots (table 115), yeti 136 (121), knight 85 (95) - the stage-1 report resolved them through the table (`tools/anim_slot_resolve.py`: e.g. viking melee1 {1, 10} = slot 10 -> table 65 -> section 6224, not 6172) | TU getter identical (Object +0x38 / +0x58) | ✅ static |
| Anim request 0x444ba0 mode 1 with an Object | arg 2 != 0 -> entry `[[arg+0x58]] + i*0x24` **without a bound** (0x444c24), the own object path is bounded (0x444c38); a null entry faults at 0x444c62 (`movzx edx, word [ebx+0x14]`). Mode 2 (0x443720) re-points the processor's object +0x310 | | ✅ static |
| Processor skeleton count | `[proc+0x88]`: `[+0x68]` ? `[[+0x68]]` (anim skeleton) : `[+4]` (0x627072); track array +0x80 (0x70 B, count byte +0xf6, current +0xf8), track +0x24 = anim section (+0x32 / +0x34 / +0x36 as the file), +0x28 time | | ✅ static |
| Instance loop and anim processors | after `[inst+0x110]` every processor `[[inst+0x280]+0x14] + i*0x320` (i < `[inst+0x280]+0x18`) gets 0x443690 (0x5b7043) - independent of EnemyProcessFunc, so an enemy with brain+8 0x20000 keeps its processors updated (whether the pose advances: live ⬜) | | ✅ static |
| State "Animation" (0x8ae754, vtable 0x858a74) | switch 0x60e9c0(inst, "Animation" 0x858354, &EnemyAnimationSwitchData 0x90 B, 0) -> 0x671df0; data ctor 0x617480 (rec ptr -> +0x44, duration -> +0x48 (-1 = until the anim-end message), vec +0x30, +0x80 = -1.0, +0x84 = 1). Enter 0x64dce0, frame 0x66f4b0 (phase +0xc4: turn 0x66f380 -> play 0x6276c0 -> wait), msg 0x64dda0 (0x15 / 0x18 / 0x8a end it when the duration was -1 -> 0x672160) | | ✅ static |
| State "Puppet" (0x8aebd4, vtable 0x8595c4) | Enter 0x643840 plays one weighted-random anim of the tune +0x40 list (0x614550, 12-byte entries from +0x10, weight +0x14) through 0x6276c0; frame slots 8 / 9 = `ret 8` stubs, msg / query 0x670430 = false. Entered only by name ("Puppet" 0x841600) from behaviour starts 0x611211 (EnemyBehavior_Puppet, vtable 0x856c2c: priority 0x61b6d0 = +0x40 when +0x3c > 0 (+1000 with the gate), else **1000 when `[0xe7f0b4]` bit 0x4000 or brain+8 bit 0**, else -1; brain+8 bit 0 is set together with the hide flag inst+0x14 0x800 (0x6252fd, 0x63b522) and cleared with it (0x618b10)), 0x612169, 0x6127e9, 0x612d09, 0x6130b9. Live: `TruMenu.log` 08.11. 18:00:34 / 18:01:44 two thralls -> Puppet 40 ms after "Cine_Start event successfully ended", back to NonCombatIdle with the next cinematic prep. A forced state switch is overridden by the behaviour tree at its next choice (🔶) | | ✅ static |

Tools: `tools/anim_slot_resolve.py` (slot -> table -> section per object DTP, melee records both readings), byte checks
`work/animlab_1011/precheck_animlab.txt` (38, `tools/pe_bytes_check.py`: 38 / 0). Sources: `Befund-Animationslabor-1011.md`,
`Plan-Animationslabor-1011.md`.

---

## 14. Markup and SweepAndPrune

| Item | PC | St |
|---|---|---|
| MarkupManager | `[0xdb94cc]` (= `[0xe7f060]`), vtable 0x855214; getter 0x5be390; allocated once at game start (0x5d9e70 from init 0x5df390) 🔶 | ✅ |
| Box list | first `[mgr+0x14]`, next `[box+4]`; +0xc owner instance, +0x20 MarkUp record (0x5c B: +0x2e id, +0x33 type, +0x34 pos, +0x58 poly), +0x24 markup2 item (0xb0 B: +0x48 id, +0x4d type), +0x28 flags (bit 31 off), +0x3c stream unit | ✅ |
| Types | getter 0x5be340; type -> MUD flag 0x5d6f90 (1 LEDGEGRAB 0x40000000 ... 15 PILLAR 0x10, 16-20 dice holds, **22 / 23 rock vein** = TU only) | ✅ |
| SAP owner (0x24 B) | ctor **0x5be3a0**: +4 core, +8 / +0x10 free / used proxies, +0x18 = 1000 proxies (64 B each at +0x1c), +0x20 = 200 (never read) | ✅ |
| SAP core (64 B) | ctor 0x46c870: +0x24 box capacity N = 1000, +0x28 used, +0x2c M = 200 -> **2M = 400 pair links**, +0x30 used, +0x20 memory 1 + 204N + 16M = 207201. Box 0x50 B. AddPair 0x4633c0, AddBox 0x4635e0, UpdateBox 0x46c9d0, RemovePair 0x463420 | ✅ |
| Overflow | pairs: "Out of space for pairs!" (0x843e14), pair silently dropped; boxes: AddBox returns 0 -> crash at 0x5be5b9 / 0x5c4573 / 0x5c4818 / 0x5c4b7e; proxies: crash 0x597678 | ✅ static |
| TU | ctor 0x8227b9f0: create(**3000, 500**) -> 3000 boxes, **1000 pair links**, proxies stay 1000; owner field +0x1c = 3000 (no reader); box 0x70 B with 0.1-unit move threshold | ✅ |
| Jump targeting | SolveCubic 0x6ebbe0 (retail 0x823f3fc8), ParabolaVsPoint 0x6f96c0 (0x823f4220), ParabolaVsSegment 0x6f9940 (0x823f43d8 / TU 0x823f6b08; general case 0x6fa83f..0x6fa91d = retail: `max(t,0)`, `min(t,tMax)`, returns the segment point; TU: `fabs(t)` then refine via ParabolaVsPoint), target search 0x70f260 (0x823f8168 / TU 0x823fa8b0; owner speed > 500 skip at 0x70f6c0, double 500 at 0x855cf8 = TU already); xmap partner 0x6fcb10 of 0x823f8168 is wrong | ✅ static (17w) |
| Ledge corner | 0x74e5a0 (retail 0x8242bc30 / TU 0x8242ecd8); player tracker `[0xfadb58]` +0xc94 / +0xc98 box / t, +0xeac / +0xeb0 partner box / t; TU block 0x8242eeac..0x8242ef40 (after the last partner-flag test 0x8242eea8 = PC 0x74e80e, before the segment fetch TU 0x8227b6e0 = PC 0x5c3aa0): look-ahead direction called once (TU 0x8242eebc `bl 0x82489d10`, r30, reused at 0x8242f094 = PC 0x74eafe), partner box == box and `floorf` of both t equal -> t = floor - 0.001 (TU [0x82053608] = 0x3a83126f, direction 4) or floor + 1.01 (TU [0x8207ddf8] = 0x3f8147ae); PC 0x74e7b9..0x74e814 = retail (floor 0x813510); look-ahead 0x787ef0 (retail 0x82483c40, PC site 0x74eaed, == 4) has side effects: 0x783f50 stores the node in [arg+0x520], 0x784b30 counts the access (`add word [ecx+2],1`) and rebalances (0x783d40) - so call it once; 0x74e814..0x74eaed is one straight line, ebx = arg (only written at 0x74e5c4). TruRockVein 0.11 `[LedgeCorner] Translate=1`: hook 0x74e814 (8-byte `movss xmm1,[0x841134]`), call at 0x74eaed -> stored result | ✅ static (18a, 27 / 27 negatives); built, not loaded |
| Edge probe | PhysicsCheckEdgesAndWalls 0x5d7fa0 (retail 0x82298780 / TU 0x82294f90): tuning `[0xfad764]` +0x628 bit 0x4000 (0x5d84b4), +0x600 probe count, fan 0x5d84ad..0x5d8578, stick-direction merge 0x5d8596..0x5d865c (retail: merged into the fan even with the stick at rest); TU: only with stick magnitude > 0.1 (0x8229545c) and as one separate probe i = -1 (0x82295534) | ✅ static (17w) |
| End level data check (2026-11-09) | dlc_yggdrasil_end: intros (164) Xbox = PC; 2 type-22 vein markup2 items (2144 / 2153, right pillar); environment block DTP 20984 and colour LUT 18577 converted like the base pair; Level +0x148 / +0x168 / +0x178 / +0x188 are s32 floats (base pair) - pipeline_check_0813 writes them as u16 pairs (regression vs the installed tree); 3 Xbox words `02000000` converted differently in installed vs 0813 (unit DTP 21218 +0x14f04, 24411 +0x464, 24420 +0x6c). Decided (`tools/endlevel_word_judge.py`): 21218 +0x14f04 = root +0xa4 block +0x94, base units disagree (l7_yggdrasil_end 18550 raw, hall02 19285 s32) but the end unit's twin 18550 has the same Xbox word -> raw (installed right); 24411 +0x464 = TRANS @0x430 +0x34 flags byte, base TRANS +0x34 raw 514 / amb 13 / 0 other over 527 TRANS of 81 uber objects -> raw (0813 right, installed wrong: wait flag in +0x37); 24420 +0x6c raw by the dtp_audit FP rule (>= 20 unanimous base samples, 17l class a; no structural reader found) - the fpkeys step is not built, so 0813 keeps it wrong (gate WARN). Fixed 2026-11-09: `leveltwin` also takes a differing non-zero Xbox word where the twin pair is s32 (the 4 Level words; tree-wide only these), `introtyped` root block from the unit twin (21218 +0x14f04); gate `endlevel_word_judge.py check` in the Fixes step (exit 1 on L / W1 / W2) | ✅ static, fixed in the rules |
| Wall run chart (DLC 2) | doppelganger_casual DTP 20212 records 1460-1517: PC conversion = Xbox original (`tools/chart_range_diff.py`, 55 / 58 equal; 1462 activity 1023 t40 field width, 1510 / 1515 activity 1114 t3 remapped id - off the wall-run path). Stay 1477 -> 1488 `{200,201,1}{200,202,1,NOT}{2000,1046,1}`, run 1488 -> 1492 / 1493 by stick direction `{400,405,450\|451}`, jump-offs under 1494: -> 1502-1505 `{400,405,450..453}{400,401,401,NOT}`, -> 1484-1487 `{7,0,0}{0,0,0}{400,405,45x}` / `{400,401,401}`; no power -> 1500 `{2000,1046,0}`. Lara condition handlers 401 0x761cd0, 405 0x764270, 640 0x7626b0. Type-22 TNode attach point: TU 0x823fddc4 loads 0x8207e5ac = 474.075 and subtracts it from z (verified 2026-11-09) | ✅ static; meaning of direction 450 ⬜ |

Plugin: TruRockVein 0.10 `[SweepAndPrune] Translate=1` patches 0x5be3a7 `68 c8 00 00 00 68 e8 03 00 00` -> `68 f4 01 00
00 68 b8 0b 00 00` and the unread copy at 0x5be3c4 (`c7 46 20 c8 00 00 00` -> `... f4 01 00 00`, owner +0x20 = 500) in
DllMain (must run before init 0x5df390 -> 0x5df410 -> 0x5d9e70 -> 0x5d9eb7 -> ctor; refuses when `[0xdb94cc]` / `[0xe7f060]`
are already set), control on the first chart-machine update: `[0xdb94cc]+4` -> core +0x24 == 3000, +0x2c == 500, memory
+0x20 = 620001 (+412800 B), proxies 1000. TU field +0x1c and the 0x70-byte box are not taken. Built 08.11., **not yet
loaded in the game** ⬜. TruMenu 0.21.7 `sap.status` (read-only, `[Debug] SapWatch`); 0.21.8 accepts the patched row in
its byte check and shows "Grenzen PC 1000/400" or "TU 3000/1000 (TruRockVein 0.10)". Tools `tools/sap_precheck.py`,
`sap_owner_field_users.py`, `sap_xbox_core_diff.py`. In-game peaks ⬜. Markup K13 (B270 patches 0x5d593f / 0x759b74) not
taken. Sources: `Befund-SweepAndPrune-0611.md`, `Befund-P5-Kleinkram-0711.md`, `Befund-Markup-Massstab-0611.md`.

---

## 15. Navmesh (NavPower / BabelFlux)

| Item | Fact | St |
|---|---|---|
| Data | Level+0x60 -> first dword 0xffffffff, image at +4 -> AddResource 0x42e990 (at 0x48c42f / 0x48c499) | ✅ |
| Image | resource 1 {0, 1, size, checksum, kind 0x10000}, u32 COUNT, COUNT resources of kind 0x20000. Little-endian on both platforms **except COUNT** (native order) - proven on 82 base pairs | ✅ |
| Area | header +0xc size, +0x10 checksum, +0x30 end, +0x48 / +0x54 bbox; area +0 centre, +0xc normal, +0x18 radius, +0x30 low 7 bits edge count, +0x34 flags (0x1100; bits 8..11 / 12..15 used by the edge colours), edges 0x14 B from +0x38 | ✅ |
| Area +0x30 bits | 0..6 edges, 7..16 island (0x3ff = none in files; `planner_islands` 0x40c9fa), 17..21 layer (0x40e3be), 22..24 graph (packer 0x40ef00), 25 A* scratch (0x41be1a / 0x410e03 🔶), **26 custom area** (hand-made, not autogenerated: stats 0x40e290 "custom areas" vs "autogen areas", 0x4187b9; only copied, 0x40ef41 / 0x41083e), **27 blocked by an obstacle** (runtime only, set by 0x413922 in 0x4137d0 when the obstacle penalty >= 15; debug text "---"), 28 -> 0x40c300 ⬜ | ✅ |
| Area +0x34 / +0x2c | +0x34 byte 0 = OR of obstacle flags; bits 8..11 = rounded obstacle penalty multiplier 1..15 (0x4137d0) ✅; bits 12..15 = static multiplier 🔶; `area_penalty_multiplier` shows the max of both. +0x2c = usage mask: when non-zero the mover mask [q+4] must hit it (0x41bd12 / 0x41c102) | ✅ / 🔶 |
| Pathfinder skip | bit 27 and (+0x34 byte 0 & mover obstacle mask) != 0 -> area skipped, unless the mover already stands in a blocked area (0x41bd26 / 0x41c0ea) | ✅ |
| Obstacles | 0x48aa30 -> 0x41b5b0 -> 0x41af30 ("ObstacleDat::m_penaltyMult") -> BoxObstacle ctor 0x413340 (vtable 0x841c00, slot 2 contains test, +0x10 penalty, +0x14 flags); penalty 15.0 (0x85d034) = full block; callers of 0x48aa30: 0x48bcb0 (from 0x48c079 / 0x48c0e8 / 0x48c84a), 0x48c220 (unit load, also 0x778806 / 0x778816), 0x69d1d0, 0x6a28f0 | ✅ chain / ⬜ which game objects |
| Data statistics (installed, 21 units, 3141 areas) | bit 27 in no file; +0x34 always 0x1100; +0x2c 0 except bit-26 areas; bit 26 only in DLC 1 (209 areas, all +0x2c = 1: caverns 27 / 40, caverns_hall 133 / 139, dungeonhallb 9 / 63, water_wheel 10 / 41, level1_start 30 / 100; 133 face downward, 12 steep -> ceiling / wall areas for spiders 🔶); DLC 2 incl. end / hall02 none; edge type 0x200 once each in end and hall02 | ✅ |
| Runtime | planner `[0x8bf310]` -> 32 layers -> 8 graphs -> area block `[g+0x1c]`, size `[[g+0x18]+8]`, stride 0x38 + 0x14 * edges | ✅ |
| Debug draw | renderer bridge vtable 0x845224 (`[0x8c0f3c]`): slot 0 -> DRAW_DrawLines 0x5bfcd0, slot 1 triangles 0x5bfa40, slot 3 text = empty stub; queue 0xe49990, flush 0x5bfd60; frame hook 0x5da141 -> 0x42f900 gated by `[[0x8c0f0c]+0x10]` | ✅ |
| Switches | 39 BoolSettings (vtable 0x841144), all 0 in .bss: planner_areas 0x8bf2e5, _solid 0x8bf2e6, planner_connectivity 0x8bf2e7, area_normals 0x8bf2ec, obstacles 0x8bf308, recent_navprobes 0x8bf309 (changes the query path), draw_mover3d_path 0x8bf006 | ✅ |
| Layer mask | `[0x88e454]` (file 0xffffffff); only writer 0x48aa23 = (1<<n)|(1<<(n+16)), n = `[0xa03590]` (probably 0 -> 0x10001 🔶); read only by planner draw 0x418680 | ✅ |
| Edge colours (0x40c3a0) | light blue = edge type 0x200; red = area bit 27 on either side; orange = +0x34 bits 8..11 > 1; yellow = bits 12..15 > 1; blue = bit 26 differs; magenta = bit 26; else green | ✅ code / ✅ live (first live draw 07.11.: red edges = bit 27) |

Converter defect ✅: COUNT swapped like the payload -> 5187 bad words in 10 DLC 2 units (and 1670 in our DLC 1 route);
rule `navraw` (`tools/navgraph_raw_fix.py`, step in `dlc_struct_fixes.py`). Effect on thrall pathing 🔶. Plugin TruMenu 0.12
`nav.draw` / `nav.mask` / `nav.status`, 0.21.7 `nav.labels`. Drawing ✅ **live 07.11.** (corridor hall02 <-> end): it needs
"Navmesh Flaechen" on **and** a navgraph layer in the mask (`nav.mask 1`), else nothing is drawn. Seen: red edges (bit 27,
installed navgraphs = Xbox, 0 differences; bit 27 = obstacle block, so the red edges at debris are probably game
obstacles 🔶), a magenta ramp where thralls jump up (end has no bit-26 area and the fill is opaque (128, 5, 254) while the
engine fills every area with alpha 0.25 (0x8415bc) -> probably TruMenu's `dbg.enemycoll` layer (TerrainGroup flag 0x800,
violet), not the navmesh 🔶; live check: toggle `dbg.enemycoll`), areas floating over water / without floor near the
end-room waterfall: the end navgraph is rebuilt for the DLC (45 of its 600 areas identical to base `l7_yggdrasil_end` with
549 areas, 58 within 60 units), so main-game leftovers can be at most ~58 areas; a floor test against the render terrain
is not valid yet (per-TerrainGroup offsets missing in `unit_frames.terrain_triangles`) ⬜. Sources: `Befund-Navmesh-Kombi-0511.md`, `Befund-Debug-Ansicht-0511.md`.

---

## 16. Rendering runtime

| Item | PC | St |
|---|---|---|
| Device | created PURE (flags 0x50 at 0x522687); device object `[0xa1407c]` | ✅ |
| State manager | SM = `[[0xad75e4]+0x284]`: pixel shader +0x20 (SetPixelShader wrapper 0x526630), render-state cache +0x168+4*s, View +0x4f0, Proj +0x530, ViewProj +0x570, World +0x5b0, per-object view offset +0x5f0 (0x502c50 / 0x49c620), dirty +0x5f4 | ✅ |
| Constant upload **0x526a20** | VS c8..c11 = Proj, c12..c15 = ViewProj (`SetVertexShaderConstantF(8, ..., 8)` at 0x526b29); World is uploaded per draw: `SetVertexShaderConstantF(0, data, 8)` at **0x526b90** writes **c0..c3 = ViewProj x World** (+0x570 x +0x5b0) and **c4..c7 = World** (+0x5b0, copied raw) at every draw call (callers 0x502ece / 0x50348c / 0x50f230 / 0x510e31, World set in 0x502c50), independent of slot or CTAB; no other call writes c4..c7 (wrapper 0x5269b0 starts at c16, 21-26, 57+, 65, 81, 85 or 254, the direct call at c8). Matches the CTABs (WVP c0, World c4, VP c12); the older note "World -> c0" meant the WVP product. A `def c4..c6` in a PC shader hides World (the 26584 def clash, fixed in `tools/tu_vs.py`, commit 0859f18). Not seen live: the D3D9 rule that a `def` only applies to its own shader | ✅ static (Befund-N5-Materialien-0711 / n5b report, 07.11.) |
| Constant wrappers | PS 0x526920, VS 0x5269b0; **the engine binds by fixed register and never reads the CTAB** (no constant names in the exe) | ✅ |
| Drawables | `PCTerrainDrawable` 0x849944 (Draw 0x510dd0), `PCModelDrawable` 0x849754 (Draw 0x50f4a0), `PCScene` 0x849a28 (Draw 0x5150e0), thiscall (pass, prev) `ret 8` | ✅ |
| Passes | 1, 2, 0x80, 0x100, 0x200, 0x400, 0x800; material apply: 1 -> 0x5064f0, 2 -> 0x505d80, 0x800 -> 0x505f40, else 0x506880; current pass `[0x8a2340]`. Meaning of each pass ⬜ (colour pass probably 0x200) | ✅ / ⬜ |
| Camera / scene | camera getters 0x5e7850 (transform), 0x5e7870 (inverse), 0x5e78a0 (position), 0x5e78d0 (FOV), matrix 0xe804a0; scene block 0xe496e0 (0x5caff0; row 1 negated), near 16.0, far 12000.0 (`[0x8aa764]`); projection `TRANS_RotTransPersVectorf` 0x49f630. FOV getter 0x5e78d0 = snapshot `[0xe8eec0]` while byte `[0xe8eec8]` (0x5e7780), else current camera vtable +0x40 (base 0x5e1c90 `fld [ecx+0xb0]`); callers 0x5cb0a8 (render projection) / 0x6b134a / 0x6e4ce4; scene near 0xe496f8, far 0xe496fc, FOV 0xe49700 (only reader 0x5ce949), aspect 0xe49704 = `[[0xad75e4]+0x170]` / 10000; perspective 0x5129d0: tan(fov x 0.5) (0.5 = double 0x8413c0, tan 0x813870) -> m00 = 1 / (aspect x tan), m11 = 1 / tan: **FOV = vertical, radians** (17x) | ✅ |
| Camera position / FOV slots | position getter 0x5e78a0 = snapshot 0xe8eeb0 while byte `[0xe8eec8]`, else current camera `[0xe80534]` vtable +0x34 (base 0x5e1c60 `lea eax,[ecx+0xa0]` -> camera+0xa0 = position); FOV vtable +0x40 base 0x5e1c90 (`fld [ecx+0xb0]`). Gameplay camera vtable 0x85600c: +0x34 = 0x856040 -> 0x5e1c60, +0x40 = 0x85604c -> 0x5e1c90. TruMenu 0.22.11 reads camera+0xa0 / +0xb0 only when the camera's slot holds the base function (else the getter's own override could differ). Look-at point: no proven field ⬜ | ✅ |
| Cheat "no texture" flags | 0xe7edac / 0xe7edb0 toggled, 0 readers | ✅ |
| Projected light binding | 0x50a5f0 / 0x5076e0: `X+0x418` sometimes holds a pointer to a render view instead of the texture -> AV 0x5076fa; the B138 exe's `light_tex_guard` restores it when it differs from the invariant of `FinalizeInitialization` | ✅ (from FINDINGS.md) |
| D3D device creation | 0x7c493d: a boot crash at 0x7c4984 (sources write tru+0x3c4984) is infrastructure (driver / VM), not data | ✅ (from FINDINGS.md) |
| Graphics settings | global 0x890388 (0x54 B): +0x25 FullscreenEffects, +0x26 EnableDepthOfField, +0x27 UseLowResDepthOfField, +0x28 EnableShadows; registry read 0x51e120 (call 0x479441; a **missing value reads 0**, any non-zero DWORD 1), write 0x51da80, code defaults 0x477a30 only when the key is missing; active copy `[0xad75e4]` (device manager) +0x15c via ApplySettings 0x522a10: DoF byte +0x182, FS +0x181, Shadows +0x184; +0x183 (low-res DoF) has no reader | ✅ static (17t) |
| Language / subtitle language | root key `HKCU\...\Tomb Raider: Underworld`, read 0x477ee7 ff. (RegQueryValueEx through esi): `Language` -> `[0x8900e4]`, `SubtitleLanguage` -> `[0x8900e8]` (both written back at 0x478134 ff.). Start-up check 0x477cca: (value + 1) indexes the byte map 0x477e8c (targets 0x477e84 keep / 0x477cfa reset): -1, 0 .. 4, 7, 9 .. 12 are kept, 5, 6, 8 become -1 (-1 = as the game language). `Set-TruDisplay.ps1 -SubtitleLanguage` | ✅ static (09.11.) / live ⬜ |
| Language ids (2026-11-10) | tru.exe enum 0..12 = en, fr, de, it, es, **ja (5)**, pt, pl, uk-en, ru, cs, **nl (11)**, hu - the Bink subtitle key table at 0x4a07a7 (`lang_english` .. `lang_hungarian`, index = the subtitle word, `cmp cx, 0xd`) and the Bink audio track (0x4a0d79: `BinkSetSoundTrack` with the language, >= 13 -> 0; a movie without that track falls back to track 0). Installer default 0x4791d0 (HKLM `LanguageString`): English 0, French 1, German 2, Italian 3, Spanish 4, Dutch 11, Polish 7, Russian 9, Czech 10, Hungarian 12, anything else 0 - no Japanese string. HKCU `Language` -> option 0x95 (0x477d84) -> SetLanguage 0x49a900 **without a range check** (-1 -> 0): mask `1 << lang` -> 0x54f2e0 -> file system vf+0x10 (0x472990, the ModLoader suffix `_%03d` of mask & 0x7fffffff): en 001, fr 002, de 004, it 008, es 016, **ja 032**, **nl 2048** - so the installed `locals.bin_032` (Dutch text) is the slot of language 5, a Dutch game asks for `_2048` and falls back to the plain name (static 🔶, live ⬜). PC 1.1 spec words: speech EN ffffffe1 has bit 5 set (a mask 0x20 finds the English speech), all six locals tables have bit 5 set, only the Dutch one (ffffffe0) has bit 11. The locals loader 0x49a800 ignores the table's language field; every entry is checked as UTF-8 (0x597dc0, else "Invalid UTF8 encoding"); it runs only while no table is loaded (`[0xa03854]`), the state machine 0x54f260 reloads it on a mask change. Language users: 0x4539a9 (subtitle reader), 0x4a0d79 (Bink track), 0x555c99 (profile word +0x206), script native 0x77c510 (scripts can read the language). A Japanese retail PC build uses spec ffffe020 (ja) / ffffffdf (all others) and cinematic subtitle id 5; a Russian retail build (0685.1) keeps one language per archive, spec ffffe200 (ru, mask 0x200 -> ModLoader `_512`), its file names under the root `pc-russ` instead of `pc-w` (`tools/hash_prefix_probe.py`) | ✅ static |
| Bitmap font (2026-11-10) | **One font for all languages: `generalbank.drm` DTP (type 7) id 46** (PC 1.1 bigfile and patch; `tools/font_survey.py`). Font object (0x42c B) built by 0x4753f0 (from SetLanguage 0x49a900 after 0x4761d0 freed the old one; source `0x54df80(id)` of `[[[0xe7ee50]+0x20]+4]`) -> `[0x9de6d4]`, constructor 0x475260 reads the descriptor: +0 / +4 texture section ids (type 5): **page 0 = id 109** (1024 x 256 A8R8G8B8, white glyphs), **page 1 = id 110** (512 x 256 DXT5, the Xbox 360 pad icons); +8 46; +0xc glyph count **205**; +0x10 pointer to the glyph array (+0x30); +0x14 extra advance per glyph (4; `movsx [desc+0x14]` 0x4764db); +0x18 / +0x1c f32 0.5 (font +0x424 / +0x428); +0x22 s16 38 (glyph height, 3D text path 0x475548). Glyph entry 12 B, sorted by code: **u32 code point, u16 width, u16 x, u16 y, u8 0xff, u8 0** (height from the descriptor). Lookup 0x475350: codes < 0x100 cached at font+0x24 (U+00A0 -> U+0020), others binary search 0x4751e0 (comparator 0x4f1ba0), a missing code draws the glyph of `[0x851630]` = U+18AF. Codes in [`[0x851628]`, `[0x85162c]`) = [0x1800, 0x18b0) come from page 1 (0x476611; U+1820 / U+1821 tinted, 0x476552). Coverage: U+0020..007E without `\` (drawn as `/`, 0x475c69), U+0080 / 0081, 61 Latin-1 letters and signs, U+1800..1825 + U+18AF (pad icons), U+2022, 2026, 2122, 2212, 221E - no Cyrillic, no CJK. Text is UTF-8, decoded per character (length 0x597bf0, decode 0x597c40, 1-4 bytes), so any code point can be looked up; the word wrap 0x475c00 breaks lines **only at U+0020** (`mov byte [edi], 0xa`). The PC 1.1 tables use 7 pad codes the font lacks (U+1826..182C, 13 uses; `tools/locals_charset.py`). The texture size is read from the texture (vf+0x1c / +0x20, 1 / size at font +8 .. +0x18), so a larger page works without code changes (a Japanese retail build ships the same descriptor format with 1373 glyphs on a 2048 x 2048 page; a Russian retail build 0685.1 ships the **same DTP 46 extended**: 501 glyphs, the 205 PC entries unchanged, + U+0400..04FF and Central European Latin, page 0 1024 x 512 - a drop-in superset of the PC font) | ✅ static |
| Language font merge (2026-11-10) | `tools/lang_retail_build.py font OUR_GB DONOR_GB OUT`: the font descriptor (DTP 46) and its page-0 texture (5:109) of a second retail build replace ours in our merged `mods\generalbank.drm` (DLC parts kept); every other section, the names and the CDRM container stay. Russian build 0685.1 into our generalbank: 1265 sections, the other 1263 byte-identical (data, relocations, flags, version, spec), no external relocations in the two moved sections (DTP 46: two type-5 id refs +0 / +4, internal pointer +0x10), relocations in bounds after a CDRM read-back, descriptor fields +8 / +0x14 / +0x18 / +0x1c / +0x20 / +0x22 equal, **our 205 glyph entries byte-identical** in the 501-entry table (sorted; U+00D3 / U+00F3 twice), our 166 page-0 glyph boxes **pixel-identical** on the 1024 x 512 page (the top 1024 x 256 differs only outside them: new glyphs in free cells), page 1 (5:110) identical in both builds and kept, texture 109 has no other user in the file; U+1826..182C still missing (as before). One font for every language, so no `_NNN` variant of generalbank | ✅ data (live ⬜) |
| Extra language from a retail build (2026-11-10) | The ModLoader name of a language file is the record path below the root folder (`pc-w\` on our build, `pc-russ\` on a Russian retail build, `tools/hash_prefix_probe.py`) + `_%03d` of `1 << lang` - laid out like the installed DLC `_001 .. _016` files: `mods\cinstream\<name>.mul_512`, `mods\audio\streams\vo\lara\<name>.mul_512`, `mods\local\locals.bin_512`. `tools/lang_retail_build.py speech DONOR.000 PREFIX SPEC LANG OUT --pc PC.000`: the Russian `.mul` (spec ffffe200: 499 Lara lines + 38 cinematics, 285 MB) are the PC format - little-endian header, block walk to the end, channels and scene name equal to the PC English record of the same path, sample-rate word within 106 Hz of it (the word is each recording's measured rate; PC variants differ alike), the cinematic DRMs byte-identical (Befund-Schrift-Japanisch-1011 6.6) - so they go in **as they are**; records without a Russian variant (490 merc lines, the 15 neutral cinematics) are found by the mask 0x200 in the PC English / neutral records (spec ffffffe1 has bit 9). `locals`: the donor text where our entry is the unchanged PC patch text (1403), ours where the donor table ends (156 DLC entries), where it is empty (19) or where our merge changed the PC text (26: costume names, DLC menu texts - English); same count / offset-0 entries as our `_001`, read back, UTF-8. Subtitles: 335 of the 832 Russian cinematic records carry id 9, 32 carry id 0 but not 9 (per-language cue times), none of them before the first id 9 of its file; the DLC cinematics carry ids 0 1 2 3 4 11 only -> TruMenu 0.22.17 subtitle fallback (row "Subtitle fallback") | ✅ data (live ⬜) |
| Subtitle language at run time | profile word `(short)[[0xc59264]+0x208]` (copy `[[0xc59268]+0x208]`), read for every subtitle line by 0x453990 (cmp 0x45399f; -1 = game language) and at each Bink movie start (0x4a0798); `[0x8900e8]` only at start / save. Option table 0x8ab538 (8 B {float, callback}), entry 0xb value 0x8ab590, callback 0x8ab594 = 0x5d4dc0 (writes both profile words); setter 0x5d5100 cdecl (index, float, bool callback); the settings save 0x478010 writes option 0xb back to `[0x8900e8]` / registry. Cinematic `.mul` streams carry every language per line. TruMenu 0.22.9 `sub.lang`. Live 2026-11-09: `sub.lang 2` during a cutscene -> the next lines in German; after a game restart the option is back at -1 (no settings save happened in between - the value is only kept by the game's next settings save) | ✅ static (09.11.) / ✅ live (not persistent) |
| Settings save (2026-11-10) | **0x478010** (cdecl, no arguments, plain ret) is the game's only settings writer; its only caller is the shutdown path **0x5df930** (call 0x5df935, then 0x4d0430 / 0x4b0ea0 / ... teardown) - a game ended by TerminateProcess (TruMenu `game.quit`) or a crash never saves. It copies the device manager's active graphics settings (`[0xad75e4]+0x15c`, 0x54 B, rep movsd) into 0x890388, reads options 0x95 / 0xb / 0x96 / 0x11 / 0xc..0xf through 0x5d5140 (`fld [index*8 + 0x8ab538]`) into 0x8900e4 / 0x8900e8 (SubtitleLanguage) / 0x8900d4 / 0x8900f0..0x890100, the sound volumes 0x587190 / 0x5870a0 / 0x5870f0 into 0x8900e0 / d8 / dc and 0x481c50 into 0x8900ec, then RegCreateKeyEx(HKCU, `Software\...`) and RegSetValueEx for each value (0x47811a ff., one REG_SZ of 0x80 B from 0x890104 at 0x47820c), RegCloseKey; when the key cannot be opened it writes nothing (0x478095). Calling it in play writes the settings as they are now = what the next clean exit would write. TruMenu 0.22.13 `sub.lang` calls it after the option setter | ✅ static |
| Option table (2026-11-10) | **0x8ab538**: 158 entries (0..0x9d, end 0x8aba28) of {f32 value, callback}; empty callback 0x6457a0 (`ret`, 140 entries). Setter 0x5d5100 cdecl (index, f32, bool: callback first, then store), getter 0x5d5140. Settings (`tools/pe_option_table.py`, names `tools/pe_wcstr.py`): 1 **SfxVolume** (cb 0x5d4cf0 -> 0x589590, sound category `[[0xccdea0]+0x24]+4`, P+0x33c), 2 **MusicVolume** (0x5d4d20 -> 0x589520, category +0, P+0x338), 3 **VoVolume** (0x5d4d50 -> 0x587140, category +8, P+0x340) - range 0..128, factor v x 1/128 (double 0x849670) into the group table `[0x8a80d8]` (stride 0x84) + dirty byte 0xccde93, live; 4 Brightness (block +0x38), 0xb SubtitleLanguage (P+0x208), 0xc..0xf Camera X / Y, Aim X / Y inverted (P+0x21c..+0x21f), 0x10 Vibration (0x5daa40, P+8), 0x11 CombatMode (P+0x221), 0x12 aspect choice 0 / 1 / 2 -> AspectRatio 0x3415 / 0x4571 / 0x3e80, 0x13 (P+0x202, 0x482a00, ⬜), 0x17 FullscreenEffects, 0x18 Shadows, 0x19 AntiAliasing, 0x1a DepthOfField, 0x1b Reflection, 0x1c WaterFX, 0x1d / 0x1e / 0x1f resolution width / height / rate (FullscreenModeID via 0x521c00 / 0x521e00), 0x2f (P+0x220, ⬜), 0x95 Language (0x49a900), 0x96 MouseSensitivity (default 10, -> 0x8900d4 / 0x8904c8), 0x97 / 0x98 input switches 2 / 3 (0x486d50, ⬜), 0x99 VolumetricFX, 0x9a TripleBuffer, 0x9b VSync, 0x9c TextureDetail, 0x9d BestTextureFilter; the rest are game-state slots without a callback (new game 0x556..., HUD / inventory 0x6e8..., 0x6f4..., 0x755...). Start: root mirrors 0x8900d4..0x890100 -> options at 0x477cf0..0x477e78 (P = `[0xc59264]`, copy `[0xc59268]`), graphics block -> options 0x4782d0..0x4784f4. The game's options menu = `uigamedata` natives f48..f105 (binder 0x7af0c0), one set + one get per option (`pe_option_table.py --natives 0x7af0c0`); the volumes go through their own natives (0x5a4af0 ...). Graphics back: **0x4798a0** builds a block from 0x890388 + the options and calls ApplySettings (next row), on success copies it to 0x890388 (0x479b71), else reloads the options 0x4782c0; native f84 (FullscreenEffects) = setter + `call 0x4798a0` (0x77c6a0). **0x4796b0** writes the root values and the `Graphics` key (0x51da80 from 0x890388); callers 0x5d473d and the start dialog 0x47a1b2 / 0x47aeb2 / 0x47b5b4 | ✅ static |
| Graphics block fields (2026-11-10) | 0x890388 / active `[0xad75e4]+0x15c`, from the registry read 0x51e120 (`pe_wcstr.py --fields 0x51e120 0x51e920 ebp`): +0 AdapterID, +4 FullscreenModeID, +8 Fullscreen, +9 LockWindowResolution, +0xa LockWindowAspect, +0xb LockWindowSize, +0xc / +0x10 LockedWindowWidth / Height, +0x14 AspectRatio, +0x18 EnableVSync, +0x1c AntiAliasing, +0x20 TextureDetail, +0x24 EnableTripleBuffer, +0x25 EnableFullscreenEffects, +0x26 EnableDepthOfField, +0x27 UseLowResDepthOfField, +0x28 EnableShadows, +0x29 DisableHardwareVP, +0x2a Disable32BitTextures, +0x2b DisableHardwareDXTC, +0x2c DisablePureDevice, +0x2d UseRefDevice, +0x2e UseD3DFPUPreserve, +0x2f DisableDriverManagement, +0x30 DisableDynamicTextures, +0x31 DisableNonPow2Textures, +0x32 DisableHardwareShadowMaps, +0x33 AtiForceFetch4Shadows, +0x34 DisableNullRenderTargets, +0x35 DontDeferShaderCreation, +0x36 AlwaysRenderZPassFirst, +0x37 CreateGameFourCC, +0x38 Brightness (f32), +0x3c EnableReflection, +0x3d EnableWaterFX, +0x3e EnableVolumetricFX, +0x3f PresentationIntervalTwo, +0x50 BestTextureFilter | ✅ static |
| Graphics apply (2026-11-10) | PCDeviceManager vtable 0x84b54c slot 0 = **ApplySettings 0x522a10** (thiscall (hwnd `[0x9eede8]`, block*), `ret 8`, al = ok): validate 0x522470 (log "Settings failed to validate"; FS with +0x31 refused, FS needs caps `[dm+0x650]` bit 8); only +0x14 / +0x38 / +0x50 differ -> copy + gamma ramp 0x5222d0, done; **group 1** (+0x25 FS, +0x26 DoF, +0x28, +0x2a, +0x2b, +0x3c..+0x3e, +0x32, +0x34, +0x35, +9..+0xb, +0xc, +0x10, +0x20) -> "--- Destroy Resources ---" (every listener vf+0x10), "--- Init and Reset ---" (0x522060 + IDirect3DDevice9::Reset, present params dm+0x208) **only** when group 2 (+0x18, +4, +8, +0x3f, +0x24, +0x1c) differs too, then "--- ResetDevice : Create Resources ---" 0x5218b0(0) (every listener vf+0xc / +4); any other field -> new device (0x5223f0(-1) + 0x522580). Render device listener vtable 0x8493e8: +4 = **0x507fb0** create (RT pool 0x51cd90, post-effect gate 0x508081, manager 0x519130 -> device+0xfdd0), +0xc 0x478510 (`jmp` vf+4), +0x10 **0x508130** release (manager dtor 0x519ac0, +0xfdd0 = 0, 0x507f60). So FS / DoF switch **live without a D3D reset** through ApplySettings with a block that differs only in +0x25 / +0x26 - the game's own menu does it for FS; the LUT (0x5174c0) and the second RT (0x51cdb5) are rebuilt with the new bytes (the 0x523ae6 crash came from flipping the byte without a rebuild). 0x4798a0 starts from 0x890388, not from the active block, so a stale field there can turn the same click into a reset / new device | ✅ static / ⬜ live |
| Settings save with Graphics (2026-11-10) | **0x4796b0** cdecl, no arguments, plain `ret`: RegCreateKeyEx (import `[0x83e014]`, 9 arguments) HKCU `0x844500` (root key), RegSetValueEx (`[0x83e018]`) of the root values from the mirrors **0x8900d4..** (it does not refresh them - 0x478010 does: options -> mirrors, active block `[0xad75e4]+0x15c` -> 0x890388), RegCloseKey, then **0x51da80(0x8447c8, 0x890388)** (the Graphics writer of the finding Befund-Spieloptionen-1011) = every Graphics value from the registry image, then 0x4782c0. So 0x478010 + 0x4796b0 writes exactly the active graphics (incl. Fullscreen / Lock* as the device manager holds them) over the Graphics key - a value written there for the next start is overwritten by it (TruMenu 0.22.16 `gfx.save` writes its own next-start values again afterwards). Subtitle line call 0x583eb6: the caller does not read eax after 0x477180 (0x583ebb `add edi, 0x16`), so a thiscall stub with `ret 0xc` may return anything (TruMenu 0.22.16 GsSubLine) | ✅ static |
| Subtitle line clock (2026-11-10) | subtitle box **0xccdec0**: two 0x100-byte lines (+0 the upper / older, +0x100 the newest), floats +0x200 / +0x204 (per line, copied up with the text), line clock **+0x208**; reset 0x583d50 (level start 0x5ddf6c, movies). Cutscene lines: the cinematic handler update 0x457100 (called from the stream update 0x5901a0 at 0x59030d) takes the frame's text and calls the reader 0x4538d0 (0x4574ec; language test 0x453990), which calls **0x583db0**(text, 90) per line (also Bink 0x4a09c8 / 0x4a0a02; a 0xfff-long text gets 0x843c30 at 0x4574d7): not in game state 6 / 10 (byte 0xe7f143); a newest line present -> moved up (0x583d80) and the clock set 0; then the text into +0x100 and clock = max(clock, 90.0). The **only countdown** is in the subtitle draw **0x583e20** (called from the game display at 0x5da17d when `[edx+0xbb]` differs, and by the Bink player at 0x4a0a0c): after drawing both lines, unless state byte 0xe7f143 is 6 / 10 (the game's pause), `+0x208 -= [0xe7f188]` (GameTracker+0x100, scaled frame time, 1.0 = one 30 fps frame) at 0x583f1c; at <= 0 the newest line moves up, the lower slot is cleared and the clock restarts at 90.0 (`[0x843cbc]`) - 3 s per step at 30 fps. So with the stream held (TruMenu `cine.pause`) the shown lines scroll up and vanish after 3 s / 6 s while no new line comes. TruMenu 0.22.13 points the disp32 of that `fsub` (0x583f24) to its own 0.0 while a cutscene is held | ✅ static (live ⬜) |
| Subtitle record format (2026-11-10) | The handler update copies a frame's subtitle text (length from the chunk, clamped to 0xfff; 0x4535a0 from the stream ring) to the **static buffer 0x9ccfa0** - at 0xfff or more it adds the fixed line 0x843c30 instead and skips the reader (0x4574b3..0x4574d7) - NUL at its end (0x4574e5), and calls the reader **0x4538d0** (thiscall, ecx = cinematic handler, [esp+4] = text, `ret 4`) at 0x4574ec - its only caller. **One record = every language:** `<id>\r<text>\r<id>\r<text>\r...`. Reader: leading isspace skipped (0x815187 = `_ctype & 8`); per entry: id = atoi (0x814fba, 0x453921), skip to `\r` (+1, 0x45392d..0x453944), copy up to `\r` / NUL into a 0x100 stack buffer, **255 bytes at most** (`cmp ecx, 0xff` 0x453954; the rest skipped 0x45396e), NUL (0x453985); the entry is **shown** when the handler's kind byte `[[ecx+4]+4]` != 2 (0x45398a) and (id == `(short)[[0xc59264]+0x208]` (0x45399f) or (word == 0xffff (0x4539a3) and id == game language 0x49a730 = `[0x8906b8]` and kind == 1 (0x4539b5))); then (0x4539c1..0x453a2d) strtok(entry, `"\n"` (0x841fb0)) - every token loses a leading `<speaker>: ` (the first `:` + space that has a byte after it, 0x4539e0..0x453a0b) and goes to **0x583db0**(0xccdec0, token, 90) at 0x453a17; isspace skipped, next entry until NUL (0x453a57). So one call adds 0..n lines (n = `\n` lines of each entry whose id matches; usually 1), and a record without the chosen id adds nothing (the old line stays). 0x583db0 copies with strcpy (no limit; the reader's 255 keeps a line < 0x100). **Text encoding UTF-8:** `tools/mul_sub_records.py` on the installed `cinstream\*.mul`: 76 records found, 107 language entries with non-ASCII bytes, all valid UTF-8 (e.g. `coup\xc3\xa9`), 2 entries with a `\n`; ids in DLC 2: 0 en, 11 nl, 1 fr, 2 de, 3 it, 4 es (those counts came from the pattern mode, which sees only records with >= 2 entries). **A record holds only the languages whose line starts at that frame** - every language has its own cue times, e.g. `pdlc2_030_pod`: frame 899 all six, 956 fr, 959 en / nl / it, 962 de, 1019 de, 1088 en / nl / de / it, 1133 de. Block mode (2026-11-10, every cine block's `{u32 len, text}` tail): 678 records in the 43 installed cinematic files, 750 non-ASCII entries all valid UTF-8, 24 entries with a `\n`, frame / ids / text bytes identical to the Xbox originals (`--xbox pack10` / `pack11`). Used by TruMenu 0.22.14 (`sub.lang` rewrites the box from its ring of the last 2 records; call patches 0x4574ec / 0x453a17) | ✅ static (live ⬜) |
| Subtitle fallback (2026-11-10, TruMenu 0.22.17) | A record without the shown id adds no line, so a language the DLC cinematics lack (Russian 9: DLC records carry 0 1 2 3 4 11) gets no DLC subtitles. Because every language has its own cue times (a Russian base cinematic: 32 of 832 records carry id 0 but not 9), "id missing -> English" must be decided **per stream, not per record**: TruMenu's reader hook (call 0x4574ec) hands the reader `'<wanted id>\r<id 0 text>\r'` when the record lacks the wanted id (profile word, or the game language for word -1 and handler kind 1; kind 2 nothing), holds id 0, and no earlier record of the same stream carried the wanted id. Stream = the cinematic handler (reader `ecx`); a new one on a handler change or when the time `[s+0x384]` of the stream whose `[s+0x77c]` is that handler goes back (list head `[0xccdc64]`, next `[s+0x14]`, the 0.22 `kCnChecks` offsets). Data evidence (`tools/lang_retail_build.py speech`): no Russian cinematic has a record with id 0 before its first record with id 9 (38 files), nor do the 3 neutral PC cinematics with subtitles - so English never stands in where the language exists. `[Settings] SubtitleFallback` (default 1) | ✅ static + data (live ⬜) |
| Volume registry write (2026-11-10, TruMenu 0.22.18) | **0x478010 never writes the volumes or the mouse:** after RegCreateKeyEx it sets the mirrors 0x8900e0 / d8 / dc from the FMOD category getters 0x587190 / 0x5870a0 / 0x5870f0 (category volume x 128.0 `[0x845680]`; 128 when the category index is <= 0) and 0x8900d4 from option 0x96, but its RegSetValueEx calls cover only 0x8900e4 Language, 0x8900e8 SubtitleLanguage, 0x8900ec Vibration, 0x8900f0 CombatMode, 0x8900f4..0x8900fc / 0x890100 (inversions), 0x8900c8, 0x890104. MouseSensitivity / VoVolume / MusicVolume / SfxVolume are written only by **0x4796b0** (0x4796ef / 0x47977a / 0x479791 / 0x4797a8, from the mirrors as they are). The game's own menu: the volume natives 0x5a4af0 / 0x5a4b30 / 0x5a4b70 call the category setter, write P+0x33c / +0x338 / +0x340 and **the mirror** (0x5a4b1c / 0x5a4b5c / 0x5a4b9c), then 0x5a4890 (UI notify); leaving the pause menu (game state 6, 0x5d4700) calls 0x4796b0 at 0x5d473d. The option callbacks 0x5d4cf0 / 0x5d4d20 / 0x5d4d50 write the category and P+off but no mirror. So a volume set through the option setter and saved with 0x478010 alone never reaches the registry (live 2026-11-10 16:44: MusicVolume stayed 0) | ✅ static (live ⬜) |
| Subtitle line alignment (2026-11-10, TruMenu 0.22.18) | 0x477180 (thiscall font, (text, float y, bool box), ret 0xc) centres **each `\n` segment** on its own: x = (`[0x9ce6cc]` - width * `[0x9ce6bc]`) * 0.5 (double `[0x8413c0]`) -> position x 0x9de6e0 (0x47720e..0x477244), width = **0x4758c0** (thiscall font, (text), float in st0, ret 4), y = the argument -> 0x9de6e4; the box extents 0x4759b0 and the queued string 0x476bc0 both use origin (0x9de6e8 / ec, set by 0x474ce0) + position. Moving the origin x around one 0x477180 call shifts that line and its bar without touching game code (TruMenu GsSubLine). The y base 352 of 0x583e20 is on the 448-high virtual screen; two lines need 2 x line step | ✅ static (live ⬜) |
| MultiFS children (2026-11-10, TruMenu 0.22.18) | MultiFS (vtable 0x8440ec, GetFS 0x472b50 = `[0x9ce278]`): children at `[fs+4 + i*0x28]`, count `[fs+0x57c]`; slot +0x10 0x472d80 calls every child's +0x10 with the mask (thiscall, ret 4); slot +0x14 0x472dc0 = the first child's +0x14 (-1 with no child); slot +0x18 0x472be0 = busy. Speech language alone = set the mask while not busy (no locals reload); used by TruMenu `voice.lang` | ✅ static (live ⬜) |
| Light slot distributor this (2026-11-10, TruMenu 0.22.18) | 0x5042b0 (thiscall, the set as argument) runs on the **same object as the set builder 0x504cc0**: it stores the set at this+0x1658 (0x5043b6) beside the builder's cache this+0x1654. Builder loop frame (after `push ebx`): this `[esp+0x10]`, light count `[esp+0x14]`, set count byte `[esp+0x1a]` (incremented before the tests, 0x504d4d), category byte `[esp+0x1b]`, entries `[esp+0x1c + i*4]` (0x504d46). Distributor: entry esi, light `[E+0]`, CastsShadow 0x50a080 (= (light+0xc5 & 4) && [light+0x1c]+0x1878) at 0x504341 decides shadow counter / plain ebx 3..5 (ebx 6 -> shadow counter). Hooks of `light.demote`: 0x504e06 (builder, full shadow part) and 0x504341 | ✅ static (live ⬜) |
| Goo drip copy position (2026-11-10) | The run-time copies (object 929 / 942) keep **inst+0x20 at the source** while they fall: TruFight.log 2026-11-10 13:39, 2145 lines in the corridor, 2 to 12 copies, the nearest copy always x -195 / y -6292 or -5725 / z 12110. The fall plays as animation 1 (uber node "Done"), so the moving point is elsewhere - candidates logged by TruMenu 0.22.18 (bone 0 `[[inst+0x90]+0x30]`, old position inst+0xc0, physics body inst+0x274) | ✅ measured (field open ⬜) |
| Subtitle draw parameters (2026-11-10) | 0x583e20 saves origin `[0x9de6e8]` / `[0x9de6ec]`, offset `[0x9de6e0]` / `[0x9de6e4]`, scale `[0x9ce6b8]` / `[0x9ce6b4]` (helpers 0x474c90..0x474d70), sets **origin (0, 352.0)** (`fld [0x84e8d0]` at 0x583e37, its only reader) and **scale 0.6 x 0.6** (`fld [0x841bd0]` at 0x583e7a, constant shared with 5 other readers), draws line 0 / 1 at y = 0 / **22** (`add edi, 0x16` 0x583ebb, `cmp edi, 0x2c` 0x583ec4) through **0x477180**(text, y, box) at 0x583eb6 with `push 1` at 0x583ea9 (ecx = font `[0x9de6d4]`), restores. Virtual screen 512 x 448 (`[0x9ce6cc]` / `[0x9ce6a4]`, font init 0x475462); x centred (512 - width x `[0x9ce6bc]`) x 0.5. 0x477180 with box: extents reset to +-1e6, gathered by 0x4759b0; per line 0x476bc0 queues a text record (list 0x9de6f0 / 0x9de6f4; +0x24 colour = current font colour **`[0x9ce6c0]`**, init 0x80ffffff at 0x475438, setters 0x474e20 (r, g, b: bytes R G B A) / 0x474e50 / 0x474e60 alpha; +0x2c / +0x30 scale; +0x3c box byte). The flush (0x476e60) draws the **bar** with 0x474f40 for records with the box byte: extents +- 4.0 (double 0x8413b0), divided by 512 / 448, vertex colour **`mov esi, 0x40000000`** (0x474f53) -> quad 0x474e90 (render device `[0xa1407c]` vf+0x50). Only the subtitle draw passes box = 1 (the other 0x477180 caller 0x45789e passes 0); Bink movies use the same draw (0x4a0a0c). All read each frame -> live patch points: y disp32 0x583e39, scale disp32 0x583e7c, line step imm8 0x583ebd / 0x583ec6, bar byte 0x583eaa, bar colour imm32 0x474f54, call 0x583eb6 (on / off, colour). The game has no subtitles on / off value of its own (menu natives f60 / f61 = option 0xb only). Xbox not compared | ✅ static (live ⬜) |
| Post-effect manager / DoF | ctor 0x519130 (device init 0x507fb0, device+0xfdd0); 2x PCColorDOFEffect (vtable 0x849c2c, ctor 0x517470) at +0xc / +0x10; built-in PS lib .shad 0x10d8fc0 (`BackBuffer s1, ColorDOFDepthScaleOffset c79, DepthBuffer s0, DepthFactors c3, DepthToW c77, Palette s2`); per frame AddParameters 0x517d60 -> update 0x516e70 (gates params+0x130e, [dm+0x182], [dm+0x181], DoF also params+0x130c; lens model 0x4545c0: near / far +0x1310 / +0x1314 + 256-byte blur curve); EndScene 0x517de0 -> 0x517570 -> drawable 0x5173c0 -> Draw 0x5177e0 (LUT effect+0x1534, quad 0x518dd0). LUT (ctor 0x523d70) and the second full-res RT (pool 0x51cd90) exist only when DoF was on at start: turning it on live after a start with 0 crashes at 0x523ae6 -> a live switch must check +0x1534 != 0. Xbox: ColorDOF drawable ctor retail 0x821c6300 / TU 0x821c41f0, Draw 0x821c4588 | ✅ static / ⬜ live (17t) |
| Post-effect settings gate (2026-11-10) | device init **0x508081**: flag = `[dev+0xfdd4] && [ebx+0x181]` (FullscreenEffects byte of the active copy; ebx = the device manager `[0xad75e4]` itself, 0x507fb4) `&& [ebx+0x18d] == 0` (2026-11-10 correction: the `je` at 0x50809f keeps the 1, so the third term is "block +0x31 DisableNonPow2Textures off"; validation 0x522470 also refuses FS with it, 0x52251a) -> first argument of the manager ctor 0x519130 (stored at +0); flag 0 jumps 0x519195 -> 0x519329 and creates **no** post effect: no shader lib 0x10d8da0, no 256 x 1 curve textures (0x523d10 at +0x3c / +0x40 / +0x44), no `PCColorDOFEffect` x2 (+0xc / +0x10), no `PCFeedbackEffect` (+0x14, 0x51a150), no `PCFinishEffect` (+0x18, 0x51aa70, vtable 0x849ce8); only +0x1c (0x51b6a0) always. AddParameters 0x517d60 calls them with one parameter block: DoF 0 at +0, DoF 1 at +0x1320, Finish at +0x2640 (9 x 256-byte curves = a 3 x 3 colour matrix as ramps, f32 +0x900 / +0x904 time factors, bytes +0x908..+0x90a, reader 0x51aab0), Noise +0x2f60, Feedback +0x2f74. A DoF block = 19 ramps (0-8 and 9-17 two 3 x 3 colour matrices, 18 the blur-over-depth curve) + 0x20 tail (+0x130c / +0x130e switches, +0x1314 far). The owner's PC runs with EnableFullscreenEffects = 0 / EnableDepthOfField = 0 (registry 10.11.) -> no DoF and no colour curves at all; the TU has no such option (🔶). Source: workspace `Befund-Dampf-Schleier-1011.md` | ✅ static |
| Post-effect parameter DTP of a unit | the unit's DTP named at environment block +0x2d0 (end level: Xbox 10994 = PC base copy 18577, 0x31c0 + trailer; earlier rows call it "environment colour LUT") is exactly that parameter block (sizes and offsets match 0x517d60). `dlc_yggdrasil_end`: DoF 0 on (switches 1 / 1, far 30 000, curve 18 = 11 / 29 / 107 of 255 at 1/4 / 1/2 / 3/4 depth), DoF 1 off, all colour matrices identity, Finish identity -> the post effects blur the far cave but tint nothing (X24) | ✅ data / 🔶 which ramp the shader reads |
| Fog getter values | 0x5c1f50: block `[[unit+8]+0x70] + 0x18`; normal case colour bytes env+0x18..+0x1a, values env+0x40, env+0x38 (env+0x3c replaces it when != 0); under water (0x5ea200) colour env+0x1c.., values env+0x4c / +0x44 / +0x48; override path when `[arg+0xa3]`. `dlc_yggdrasil_end` (Xbox = PC): colour 23 30 30, values 632 623 / 948 207 / 1 106 066 - far beyond the far plane 12 000, so no distance fog in that level on either platform | ✅ static + data |
| Shadow maps | PCShadowMap ctor 0x5156e0, created in 0x504400 (4096 x 3072 with EnableShadows, else 1024 x 1024); slice allocator 0x504f30 (<= 2048, <= 16 slices); RenderShadowMaps 0x5050c0 (= retail 0x821b3618): light type byte +0xc0 == 2 first; with EnableShadows all lights with flags +0x64 / +0x65, else only the first whose resource has +0x144d; deferred light ctor 0x50b910 (= retail 0x821b8228): +0x42c 1 = perspective (spot), 2 = ortho. PC material shaders: 3 shadowed lights (`ShadowLights c178 x15`, `WorldToShadowMap c158 x12`, b0..b2, s14) + 3 unshadowed + PSSM; Xbox: 7 lights each with a shadow bool, ShadowNoiseTexture, VSM blur (post-fx slots 12 / 13). Why Lara's flashlight casts no shadow on PC ⬜ (light-resource flags PC vs Xbox not compared) | ✅ static (17t) |
| Shadow caster gate | PCRenderLight vtable 0x849594 (0x120 B, CreateLight 0x507400 -> ctor 0x50b120; `[L+0x14]` = render device, `[L+0x1c]` = the light's **PCLightResource** (vtable 0x8494ec, ctor arg 2 at 0x50b14b - 18d correction of 18b's "device"), type +0xc0 = 0 in the ctor, ctor sets +0xc5 bit 2 at 0x50b1a5); CastsShadow vf+0x50 0x50a080 = `(L+0xc5 & 4) && res+0x1878` (writer 0x50b07c; 0x50afb0 clears it when res+0x42c == 0); SetCastShadows vf+0x4c 0x50a3a0 (bit 2 of +0xc5, dirty byte +0xc4); SetTransform vf+0x28 0x50a210 (matrix L+0x20, position L+0x50 🔶); per-object gather 0x504cc0 (<= 7 lights): light instance E +0x64 = used by a drawable (0x504d40), +0x65 = visible this frame (0x50b23d) - **run-time flags, not data**; without EnableShadows only a light whose res vf+0x1c (0x50a030 = res+0x42c) +0x144d, i.e. **res+0x1879**, is set gets the shadow (0x504e44). No game-side caller of vf+0x4c found; the flashlight light comes from object / DRM data (no "flashlight" / "torch" string) ⬜ | ✅ static (18b, 18d) |
| Scene light list | `[0xa1407c]` = PCRenderDevice (vtable 0x8492cc; new(0x11828) 0x509a80, ctor 0x5088a0, store 0x509aa3; frame function slot +0x10 0x509630 calls RenderShadowMaps 0x5050c0 with ecx = device+0xfdfc); scene = device+0xfdfc; **all PCRenderLights**: count `[scene+0x14]`, capacity +0x18, data `[scene+0x1c]` (light ctor 0x50b1be -> push_back 0x5054f0, dtor 0x50b1e0 -> remove 0x504a10, swap with last); scene+0x20 / count +0x1020 = the per-frame list of light instances E (`[E]` = light, ctor 0x50b910), reset by 0x504c50 (empty outside the frame). TruMenu 0.21.11 `light.list` / `light.shadow` (runtime byte / vtable guard). **Frame end (08.11.):** one call 0x5098ca (ecx = scene) -> 0x504c50 clears three counts: light instances +0x1020, light resources (pointers at scene+0x1024, count +0x11a4; added once by 0x50428d, R+0x1d18 = slot, -1 = none, ctor 0x50b7f0) and a third count +0x1228 (list unknown), and sets every light's L+0x18 = 0 - TruMenu 0.22.2 `light.frame` records the lists there. **Live (DLC 2 end-room cutscene held):** 14 light instances in all 60 frames; 4 torch lights change E+0x50..+0x5c (colour x flicker, ~1.6 / 1.25 / 0.58) every frame; the 3 shadow-casting cutscene lights change in a **5-frame cycle**: E+0x60 = 1, 1, 1, 2, 3, and in the 3-frame E+0x78 0 -> 1.0, E+0x0c 0 -> 0.0195, E+0x3c in three steps, E+0x66 = 0x3f80. Global shadows (byte `[[0xad75e4]+0x184]`) off -> the throne brightness stood still for 31 frames: **the end-cutscene flicker is the shadow rendering of these lights**; the writer of E+0x60 / +0x78 is to be found. **Shadow atlas (08.11. evening, static + live reads):** instances are rebuilt every frame (pool getter 0x50da60, 0x2e0 bytes; builder 0x50b910, only caller 0x50dab8; E+0x60 = its slot in the frame list, written at 0x50c413 after the append 0x50c3fb - not a cycle counter); type dispatcher 0x50db20 (L+0xc0: 1 -> 0x50c420, 2 -> 0x50ccb0), called from 0x5049be in 0x504960 (loop over the shadow manager's list). RenderShadowMaps 0x5050c0: manager = scene+0x168c, per frame +0x140 faces = 0, +0x148 count = 0, **budget +0x144 = 0xc00000** (0x505129); type-2 lights first, then the rest; every instance with E+0x64 && E+0x65 asks **0x504f30** for atlas room: size = min(0x50b5f0(), 2048), cost = faces L+0xf4 x size^2, refused when over the budget, over 16 faces or a third 2048 map; the slot follows the order. Size 0x50b5f0 = res+0x1880 (res->vf1c = res+0x42c, +0x1454), halved / quartered / eighthed by distance only when L+0xc5 bit 0x02 (thresholds L+0xc8..+0xd0). Live (end-room cutscene held): 9 type-1 lights with one face (8 x 1024, 1 x 2048 = exactly the budget), no refusal in the 60 recorded frames, but **the three cutscene shadow lights rotate their order** in a 5-frame cycle (frames 3 and 4: rotated by one each), so they swap atlas slots; their places in the scene array stay 93 / 94 / 90. Where the order comes from and whether a stale slot is sampled is open. Live manager reads (15 one-read snapshots of the instance pool): **E+0x78 = 1.0 belongs to the third slot, not to a light** (whichever light is third has it), and E+0x3c = (2 x slot + 1) / 256 - a per-slot id the shading likely uses to find the light's shadow; the face entries +0x40 are sorted by size before packing (2048 first, then 1024 by descending index). **Correction (builder 0x50b910):** E+0x3c = (R+0x1d18 + 0.5) / 128 = the light **resource's** slot in this frame's resource list (given at first use 0x504280, reset to -1 at the frame end), so the rotation moves resource slots too; the per-frame light table 0x504a60 is written into a ring [scene+0x122c] whose step is `(i + 1) & (count - 1)` with count +0x1c = 6 - live only buffers 0 and 1 are used (an engine quirk). Live test count 6 -> 4 (three buffers in use, checked): the flicker stayed - not its cause. **Light submit order (live, self-ending cdb):** lights are submitted through PCRenderLight vf+0x60 0x50e270 from 0x56db1e in the light pass **0x56d5c0** (called once per frame from 0x5723cb in the scene pass 0x572320; thiscall, one argument, ret 4), once per lit object (4 x per light here); the submit order already rotates there (2 of every 5 frames). 0x56d5c0 collects the visible entities [s+0x9c] (count +0x94) with entity+0x1e0 == 10 (scene lights) into its own list +0x250 / +0x258, only when +0x2c8 is set and the "collected" byte +0x2c9 is not (then sets it). TruMenu 0.22.3 `light.stable` sorted the type-10 entries of the visible list before the call: they never needed a change (0 of 111 frames) and the flicker stayed - the rotation comes after, in the pass's own list or its +0x2c9 handling. **Proven (0.22.4, live):** at the end of the collection loop (0x56d69a, esi = scene) the collected list +0x250 holds 15 lights; entries 10..14 are permuted in a 5-frame cycle, the rest stay. Sorting that list by address every frame (6 bytes at 0x56d69a -> stub) makes the lit figures stand still (brightness spread 13.9 -> 0.0); the cycling states are different light combinations on the figures (warm torch light vs. a cool front light), the sorted order keeps one - so the order decides which lights an object gets (likely a per-object light limit), and the real fix is a stable order of equally weighted lights or the right weights in the DLC light data | ✅ static (18d) / ✅ live (frame lists, atlas, ring, submit order, cause) |
| Pass list Xbox vs PC | Xbox model add 0x821b9df0: opaque groups 0x201 or 0x211 (+0x10 = motion blur) when instance data byte +0x88 != 0 and float +0x84 > 0; AddDrawable 0x821b3530 files bit 0x10 into scene list +0x74c; scene draw 0x821c25e8 -> 0x821c3280 (back buffer s12, depth s13, pass 0x10, then 0x400); model draw 0x821b97d8 case 0x10. PC: opaque mask 0x50fa9d writes 0x201 only, Draw 0x50f4a0 has no 0x10 case, scene struct 16 B shorter (Xbox +0x6ec..+0x73c = PC +0x608..+0x658, +0x75c.. = PC +0x668..). Camera motion blur: Xbox effect manager ctor 0x821c4bd0 object [5] (0x14 B, enable +4, strength +0xc), EndScene 0x821c4fe8 -> 0x821c7698 -> Draw 0x821c6798; the PC manager has 5 objects. Who writes +0x84 / +0x88 and [5]+4 ⬜ | ✅ static (17t) |
| Per-draw light limit | PC material shaders: at most 3 shadow lights (b0-b2, `ShadowLights` c178, 5 regs each) + 3 non-shadow lights (b3-b5, `NonShadowLights` c193) + sun (b6); slot mapper 0x5042b0 (set: byte +2 count, byte +3 bits 4-5 shadow count, +4 `PCRenderLight*`[]; sun -> slot 6, shadow -> 0.., non-shadow -> 3..5, `cmp ebx, 6` at 0x50434a, overflow into free shadow slots; bool mask via 0x526940 = SetPixelShaderConstantB). Xbox (TU-embedded shaders, `tools/ctab_light_slots.py`): `LightEnabled[7]` b14, `p_Lights[7]` c140, `p_ShadowEnabled[7]`, `TooManyLights` b21 - 7 lights of any kind per draw. Per-object light list in collected-list order (0x56d5c0 appends at 0x56d9cd to object +0xdc / +0xe4), draw path 0x56abf0 indexes lights by position (64-bit masks) -> with more lights than PC slots the order decides (throne flicker). Shadow atlas 0x504f30: budget 0xc00000 px / frame (0x5050c0), <= 16 faces, <= 2 maps of 2048, granted in submit order. Xenia 09.11.: no flicker, Natla lit warm and cool at once | ✅ static; set builder: next row |
| Light set builder (per object) | engine 0x56bbc0 (TU 0x8221f0e4, same code) gathers the object's light list [obj+0xdc] / +0xe4 in collected-list order (tests +0x2ca / +0x2cc / +0x188 / +0x174, render light via vf+0x60 of +0x140) uncut -> device SetLights (vtable 0x8492cc slot 0x70 = 0x5076a0 -> scene 0x505530, list +0x1234 count / +0x123c pointers, clears the set cache +0x1654) -> set builder **0x504cc0** (thiscall, ecx = scene; returns the cached +0x1654 when set): first fitting lights in list order, at most 7 (cmp bl, 7 at 0x504d24 - lights after the 7th are not looked at), sun 1 (light vf+0x1c 0x50a070 = [light+0x1c] = resource, res+0x42c == 2, bit 6), shadow slots 3 (bits 0-1) of which shadow-mapped (res+0x418 && res+0x42c) <= 2 (bits 4-5), shadow casters (vf+0x50 0x50a080) into shadow slots, plain 3 (bits 2-3, overflow into free shadow slots); a light that fits nowhere is taken out at **0x504e56** (`add byte [esp+0x1a], 0xff`); local set {+2 count, +3 category, +4 entries = frame instance light+0x18 via 0x50dbe0}; survivors sorted by address (0x504e78..0x504eb3), interned via 0x504700 (+0x1250) at 0x504eb9..0x504ecd; the set goes to PCModelDrawable +0x30 (ctor 0x50e6fc) / PCNGAPrimitive +0x20, then the slot mapper 0x5042b0. Xbox device side not mapped (shaders: 7 of any kind). TruMenu 0.22.10: light.cutlabels / light.cut (hooks 0x504e56, 0x504eb9), light.stablecut (0x504cd9: per-object order by kind, then address). Live 2026-11-09 (end throne, cutscene held, `light.cutlabels` bursts of 6 frames at 0.1 s): game order -> the dropped shadow caster changes every frame (#93 / #91 / #90 in the `light.cut` frames 517-519; the "#98" of the first reading was a misread #90 label), throne brightness 65-74 (YDIF mean 2.45); `light.stable 1` -> always #94 dropped, 65-69 (YDIF 0.67); `light.stablecut 1` alone 0.87 (also always #94: it sorts casters by address too). **Throne lights named (2026-11-10, `tools/light_frame_report.py` on the 08.11. `light.frame` dump + the 09.11. `light.cut` lines, matched by position; colour = instance E+0x50..+0x5c):** the dropping set (5 x caller 0x50e701) is offered 4 cutscene shadow casters #90 (warm 0.95 / 0.82 / 0.60, horizontal), #91 (white 0.86, 15 500 units away), #93 (cool 0.21 / 0.36 / 0.40, dim, horizontal), #94 (warm 0.76 / 0.61 / 0.35, from above) + 2 plain #92 (cool, dim) / #95 (warm); casters may only use the 3 shadow slots, so one always drops although a plain slot is free. #94 is not the cool front light. Cutscene lights #90-#95 = two groups of three (resources allocated together; `dlc2_ceremony_room` has two `co_lights` intros 11877 / 12224 🔶); level lights #0-#15 (cool goo point lights #0 / #2 / #3, flickering torches #10 / #12 / #13 / #15). Proposal (not built): demote the least contributing caster to a free plain slot (builder 0x504e56 + mapper 0x504341 -> 0x50434a) instead of dropping it. Source: workspace `Befund-Thron-Licht94-1011.md` | ✅ static; ✅ live (cause seen); ✅ lights named |

TruMenu 0.15-0.17 debug render modes (`dbg.census`, `dbg.flat`, `dbg.flatedges`, depth path hooking 0x849a2c, live 06.11.).
Sources: `Befund-Debug-Rendermodus-0611.md`, `Befund-TruMenu-Rendermodus-0611.md`, `Befund-Debug-Ansicht-0511.md`,
`Befund-TruMenu-Lesbarkeit-0611.md`.

---

## 17. Materials and shaders

### 17.1 Material section (type 10)

| Offset | Content | St |
|---|---|---|
| +0x28 / +0x2c / +0x30 / +0x34 | 4 shader lib ids (data) / `PCShaderLib*` (runtime): PS pass 0 (depth / alpha test), PS pass 1, PS pass 2 (colour, lit), VS. 0 = empty | ✅ |
| +0x38 | blend type (5 additive SRCALPHA / ONE, 6 reverse subtract, 2-4 / 7-9 others; `FUN_00527a80`) | ✅ |
| +0x40 | bits 0x88 = translucent sort class only | ✅ |
| +0x44 bit 1 | back-buffer users (153 / 153 such materials): render key 0x400 at 0x50fa54 -> list +0x648 instead of +0x628 (0x503367, terrain 0x5116f8) | ✅ |
| +0x4c..+0x53 | per-pass bytes; +0x51 ordinary texture records, +0x52 all records, [+0x52, +0x52 + byte +0x50) per-instance textures | ✅ |
| per-instance records | kind 1 / 2 / 3 (terrain: three per-chunk atlases fetched at texcoord0.zw - Setup = kind 3, two `..._Param` maps); the record holds a default id (PC 121 / 255 / 719, Xbox 119 / 288 / 147), the real texture comes from the terrain Y record's i32 x4 = indices into the terrain texture list (section +0x08), e.g. Y 43 of `dlc_yggdrasil_end` terrain 20273 -> 7241 / 7242 / 7243. The converter re-slots them like ordinary records (25057: Xbox s9 -> PC s8), so translations must map them too (17.4 per-instance sampler gap) | ✅ data (`work/floor_0811/terrain_inst_tex.py`, `mat_records.py`) / 🔶 kind -> texture role |
| per-instance binding (engine) | kind k samples entry[k-1] of the Y record's runtime entry: terrain init 0x510780 resolves the Y indices +0x10..+0x1c via the terrain texture list into texture pointers (-1 -> 0) and stores a 0x24-B entry per Y at [obj+0x38]; Draw 0x510dd0 passes it to 0x505d80 -> 0x505a90, loop 0x505b80 `tex = arg1[kind - 1]`, 0 -> the record default. Record word +8 ("type") is not read by the bind loops | ✅ static; data 1450 (PC) / 1329 (Xbox) Y records with kinds (1, 3) -> slots (0, 2) (`work/q17p_0811/q1_stats.txt`) |
| per-instance default id | the record's id word +0 is an id reference (type 5) like the ordinary records' (20265 4 / 4, 20264 5 / 5, PC and Xbox); default ids pair Xbox 119 -> PC 121 (kind 1: 731 / 731 installed pairs, kind 3: 2 / 2), 288 -> 255 (kind 2: 265), 147 -> 719 (kind 3: 625); f32 / filter / type equal in all 1736 paired per-instance records. 121 is not in the DLC 1 streamgroups but in their level DRMs (dlc_dungeon / dlc_pillory / dlc_treasureroom / dlc_water_wheel; 194 installed DRMs) | ✅ data (`work/q17q_0811/rec_stat.txt`, `tex121.txt`) |
| +0x58 / +0x5c | PS MaterialParams count / pointer -> **PS c100** (0x505acf) | ✅ |
| +0x68 / +0x6c | VS MaterialParams count / pointer -> **VS c25** (0x505c2a, `0x5269b0(25, ...)`); +0x3c is not a VS count | ✅ |
| texture record | {u32 id, f32, u32 type, u8 kind, u8 slot, u16 filter}; kind 9 = back buffer, 10 = depth buffer (texture from `[[renderer+0xfa50]+0x46c+kind*4]`); a sampler without a record keeps the previous draw's texture. Setup 0x505ad4..0x505bb2, bind 0x5076e0 (mip bias via 0x527840) | ✅ (who fills +0x490 / +0x494 ⬜) |

MaterialParams layouts differ between Xbox and PC per shader family (a per-lib-pair permutation / compaction derived by
role signatures: `param_rules`, `work/ws/visual2/rolefix*.py`, `work/ws/contratti`); blind scaling gave neon-green planks
and red tints (B41). (FINDINGS.md read the per-pass bytes +0x50..+0x52 as indices of the 16-byte MaterialParams records;
the table above, from the later N5 reading, has them as texture-record counts.) When a PS is replaced by a translation, the PS MaterialParams become the Xbox
values (missing vec4s appended, block grows, relocations behind it shift; empty PC block n = 0 was a `grow_params` bug,
fixed). ✅ (from FINDINGS.md, `Befund-Wasserfall.md`, `Befund-N5-Materialien-0711.md`)

### 17.2 Runtime objects

| Item | PC | St |
|---|---|---|
| MaterialSection | vtable 0x84c8d4, hash `{buckets 0x8a6ebc, nodes 0x8a6ec4}`, bucket = id % buckets; node {next, id, PCMaterial*, data, refcount, size}; resolve slots 0x550ae0 / 0x550b20; node write 0x551e84; **first copy wins** (0x551ec9) | ✅ |
| PCMaterial | 0x1c B, vtable 0x849018, ctor 0x505cf0 (RenderDevice +0xa0 = 0x507180); slot 0 0x505980 clears all 4 libs if any lib has no D3D shader | ✅ |
| ShaderLibSection | vtable 0x84c874, `{0x8a6ef0, 0x8a6ef8}`; PCShaderLib vtable 0x849a78, ctor 0x5155fc (RenderDevice +0xa8 = 0x5071f0) | ✅ |
| Current material | `[0xa14188]` (written 0x506b80 / 0x5066e0) - basis of TruMenu shader labels | ✅ |
| Loaded streamgroups | vector {count 0x8aa5cc, cap 0x8aa5d0, entries 0x8aa5d4} (12 B: record (+0xc name), u32, u8 keep); load 0x5b8dc0, streaming set 0x5b8fc0 | ✅ |

### 17.3 Shader lib container (type 9) and registers

* Xbox entry: `0xbaadf00d`, size, 8-byte hash, Xenos container (0x102a1100 PS / 0x102a1101 VS), CTAB, microcode. PC entry:
  u32 word0 (translated libs may use 0), u32 size, hash, D3D9 tokens. **PC size word = (16 + code bytes) | (dcl_cube sampler
  mask << 16)** (6139 / 6139). ✅
* Samplers: dcl >= s16 broke the driver at start-up (B75), stay in s0..s15 and check with `vm_ps_validate.ps1` +
  `vm_ps_draw.ps1`; s15 = fog / attenuation lookup `texld (v4.w, c54.z)` (the Xbox shaders read their
  `AttenuationSampler` s15 the same way); final colour `lerp(color, c0, fog)`. Xbox `p_Lights` uses 13 registers per
  light. ✅
* **Harness rules** (from FINDINGS.md): constants are random unless set; the fog read must return 0; the attenuation
  sampler s15 is marked by the 'ATT' sentinel `c54.z = 0.987654`; the direct-light share is only 50 % / 33 %, so harness
  results about direct lighting are weak. Several earlier conclusions were retracted because a harness was wrong (cobweb
  fog lookup): check that changing an input that should matter moves the output. ✅
* PS register map Xbox -> PC: MaterialParams c100 -> c100; MaterialOpacity c1 -> c98; TimeVector c33 -> c53;
  CameraPosition c35 -> c1; AlphaThreshold c4 -> c2; ScreenExtents c16 -> c51; DepthToW c36 -> c77; GlobalParams[7] c147;
  InstanceParams c132. ✅
* VS register map: MaterialParams c100 -> c25; TimeVector c98 -> c23; TexcoordScale c161 -> c254; CameraPos c16 -> c24;
  fogScaleAndOffset c96 -> c22; World / WVP / VP stay c4 / c0 / c12; PC adds NormalScaleOffset c21, WorldToPSSM0 c81,
  SkinMatrices c85 + 168. ✅
* Slots: pass-2 PS Xbox 2 -> PC 8 (PC k <- Xbox k&1); pass-0 PS Xbox 2 -> PC 4 (PC 2 = depth permutation c78, PC 3 empty);
  VS 256 permutations, PC lacks Xbox 40-42 / 104-106 / 168-170 / 232-234 and adds PSSM in 32 / 96 / 160 / 224; PC depth VS
  slots write z/w to TEXCOORD6. Which of lib 242's 8 slots a draw selects ⬜. ✅
* Built-in exe shader libs (17t): PC .shad blobs in tru.exe (e.g. ColorDOF 0x10d8fc0; 13 constant tables); Xbox render
  device fields rd+0xfd84..+0xfdb0 (ctor 0x821afd78): motion-blur VS lib 0x8272fc20 (4 shaders: `MotionBlurStrength c160,
  PrevViewProject c156[4], ViewProject c12`, one also `World c4, WVP c0`), velocity PS lib 0x82730e80 (`BackBufferSampler
  s12, DepthBufferSampler s13, DepthToW c36, VelocityScale c5`), post-fx lib 0x82710530 (22 shaders vs PC 4; slot 14 =
  camera motion blur, slots 12 / 13 = VSM blur); retail copies 0x8272e220 / 0x8272f480. Not in any DRM: a port takes them
  from the exe image through xenos2sm3. ✅ static

### 17.4 Translation pipeline (our tools)

| Part | Rule | Tool | St |
|---|---|---|---|
| Map | 1028 DLC libs: class A 489 / B 234 have a byte-identical base twin; C1 120 / C2 47 / C3 81 / D 57 use a **surrogate** (base PC lib chosen by constant / sampler similarity) | `shader_map.py` -> `dlc_shader_map.json` | ✅ |
| Two regimes, never mixed in one material | lit: the Xbox light model differs from PC's, so the PC light block is transplanted into the translated Xbox shader with numerically matched inputs / outputs (`tu_light_transplant.py`, `tu_perlight.py`, oracle `perlight_xref.py` on base-game pairs, self-test 300 / 300, accept >= 0.999); unlit: direct translation (`tu_unlit.py`). Pass 0 is not translated | `work/ws/shader4/xenos2sm3.py`, VM `sm3vm` | ✅ |
| VS translation | `tu_vs.py`: vfetch -> dcl, export 62 = position, rigid skinning index floor(BI*255+0.5)*4, constants by name, NormalScaleOffset only where the CTAB has it | `tu_vs.py` | ✅ |
| **VS merge rules** | keep the PC twin slot P whole; append outputs the DLC translation T adds (no DEPTH); PC fog slots take Xbox fog group 40 / 104 / 168 / 232; on common outputs the base twin decides; deforming VS: prove T = Tb o D, build P o D (`tu_vs_deform.py`); checks VM <= 1e-5 + D3DX9 valid | `tu_vs.py vsmerge`, `tu_vs_deform.py` | ✅ |
| **Def clashes (07.11.)** | a `def` in a merged program is global: PC 868 defines c4..c6 as literals in 8 unskinned slots (64, 72, 80, 88, 192, 200, 208, 216) while appended Xbox-2066 code reads c4..c6 as engine World rows -> wrong TEXCOORD3 / 4. Rule now: move a P def that T reads as an engine constant or that lies in T's relative range; move a T def that P reads, that lies in any relative range (c85..c252) or that differs from P's; share identical defs; moved defs go to provably free registers from c255 down; `check_merge` runs every program with its own defs; `selftest` 45 / 45 | `tu_vs.py def_clashes / selftest` (commit 0859f18) | ✅ |
| Earlier merges | 2876-2879 have the same c4 clash in 8 unskinned slots and translator defs on bones 33 / 34 in 21 skinned slots; they were never installed (only test trees 50n / 50o / 51x) and the fixed-tool rebuild is byte-identical to 3480-3483 of the n6 tree, which serve the same materials (25165 / 25528 / 26228 / 26662 / 26602) - nothing left (17c 08.11.); 2880 bone rows only; 2888 / 2889 rebuild identical | `tu_vs.py vsmerge` | ✅ |
| MaterialParams shared by passes 0 / 1 / 2 | `tu_unlit apply` writes the Xbox values for the new pass-2 PS; pass-0/1 PS that read c100+ in the old PC layout then see other values (B138 donors 240 / 241: texkill(tex.a * c100.w - c2.x), UV c102.xy; n6: 21118 pass 1 surrogate 2037 now sees c109.xy 1 -> 2, c112.w 1 -> 23, c113.z 1 -> 0.4). Rule (17c): a lane the pass-0/1 PS read keeps its old value when the new PS does not read it | `work/shader17c_0811/param_lanes.py`, `pass01_inputs.py`, `pass01_tree.py` | ✅ / ⬜ 21118 |
| Record variants DLC 1 | B138's DLC 1 copies use another PC sampler map than our DLC 2 conversion (20265 {1:2, 2:0, 3:3} DXN on s0 vs 26584 {1:3, 2:1, 3:0} DXN on s1): a PS translation is valid only for its record signature (3090 on 20265: 0.003) | `work/shader17c_0811/ps_check_2065.py` | ✅ |
| B138's own PS (2173, 2720-2783) | not proven equivalents (2783 vs Xbox 2065 on 20265: 0.000 lit and unlit, PC and Xbox params); `shader_labels` still counts them as T | | ✅ / ⬜ label rule |
| **Per-instance sampler gap (08.11.)** | `tu_light_transplant.records` read only byte(+0x52) records; tu_batch's sampler map left the per-instance records (17.1) out, a translation sampled those Xbox registers under the Xbox number; the old verify used the same map (311 / 311 1.000). Fixed: `records_all` / `pair_records` / `sampler_map` (ordinary records by position, per-instance by kind byte; a kind present on one side only = unpaired -> build refused). Proof: N6 83 of 311 copies fail the new verify (72 static, 11 swapped kinds 3408 / 3420 / 3442 only by the VM); n6b rebuild 324 / 324; 2346 rebuilt == floor proof 3460 byte-identical; N6's 2D + cube refusals 2666 / 2673 / 2694 / 2706 / 2715 were the gap itself (now translated) | `tu_batch.py selftest` (17), `work/n6b_0811` | ✅ static / ⬜ live |
| Binding check (verify / vcheck) | no sampler map: Xbox reference with Xbox sampler numbers, VM textures keyed by the record role behind each register (('ord', position, kind) / ('inst', kind), engine samplers by number); static: every record role the Xbox slot samples must be sampled by the PC slot and vice versa | `tu_batch.py binding_check`, `vcheck` | ✅ |
| Record roles differ (converter) | B138 DLC 1 copies: PC / Xbox record counts differ (20264 PC (2, 3, 3) vs Xbox (1, 4, 4): an Xbox ordinary record became PC per-instance kind 2) -> B138 lib 2783 fails vcheck in 32 installed copies; 20265 per-instance Xbox kind 1 vs PC kind 2 -> 17c's PS 3500 is NOT provable (VM 0.080, tree `work/shader17c_0811` withdrawn); ordinary type word differs positionally in 20345 / 21164 / 23462 / 20773 (reported) | `work/n6b_0811/vcheck_*.txt`, `scan_records_installed.txt` | ✅ data / ⬜ kind 1 vs 2 meaning |
| Record roles: B138 cause (17p) | B138 re-typed records, the textures did not move (Y indices + texture lists PC = Xbox): 20265 Xbox per-instance kind 1 (default 119) s0 -> PC kind 2 (255) s1, so the PC reads Y idx[1] = -1 in all 17 Y records and the atlas (6895 / 6896 / 6719, 4 Y) is never bound; 20264 Xbox ordinary 6549 s0 -> PC kind 2 (always 255), kind 1 s4 correct. Rule: per-instance records keep the Xbox kind (20265: kind 1, default 121 = PC twin of Xbox 119); 20264 needs a material rebuild (6549 back as an ordinary record, kind-2 record removed: +0x50 / +0x51 / +0x52 and table length change) | `work/q17p_0811/q1_detail.txt` | ✅ data + static / ⬜ build |
| Record kind fix (17q) | 20265: kind byte +0xc 2 -> 1 and default id 255 -> 121 (type word 7 kept - not read; Xbox has 6, in all other 1736 paired records PC type = Xbox type) -> tu_batch pairs Xbox kind 1 s0 with PC s1, map {0:1, 1:2, 2:0, 3:3}, nothing unpaired; PS 3534 8 / 8 1.000; binding-check sensitivity: 3534 on the unfixed record 0.000 (16 problems), 17c 3500 on the fixed record 0.080 | `work/q17q_0811/build20265.py`, `negctl.py` | ✅ static / ⬜ live |
| B138 re-typed records: sizes | 20264 / 23173 / 23329 / 20673 / 20676 / 20876 (20 copies): PC (3 ordinary + kinds 1, 2) vs Xbox (4 ordinary + kind 1) = 5 records on both sides -> in-place fix (+0x50 / +0x51 / +0x52 and record 3 -> the Xbox ordinary record; 20673 / 20676 / 20876 need texture 470, not local), no material size change; real size changes only 22587-22589, 21185 / 21199 / 21537 / 23814, 20344 / 21093 | `work/q17q_0811/plan20264.txt` | ✅ data / ⬜ build |
| Shader labels: EQUIV | proven 1:1 pairs count as O (Xbox VS 2456 = PC 1911 / 1737 / 1718 / 1689; proof `work/n6shaders_0711/vs_twin_cmp.txt`, `work/endcolumn_0711/vs_slot_cmp.txt`); `--no-equiv` = the old letters byte-identically | `tools/shader_labels.py selftest` (16) | ✅ |
| Refused patterns | sampler used as 2D and cube (2666 / 2673 / 2694 / 2706 / 2715), L-lane 2057, lint 2106 / 2387, record mismatch 2052 / 2118, light block "L None" 2195; upstream kill bug (vector kill with zero write mask dropped) worked around | `column_shader_translate.py` | ✅ |
| DXN normals | Xbox DXN -> PC DXT5 with x in R, y in A (`dxn` option) | | ✅ |
| VS equality proof (C1 Xbox VS kept as PC VS) | PC VS P is a 1:1 equivalent of DLC VS D when a base Xbox VS X with x2p(X) = P has the byte-identical entry in every slot P occupies: holds for 2456 / 1911 (23164); fails for 2371 / 1911, 2633 / 802, 2274 / 114, 2062 / 831, 2713 / 1595, 2462 / 1908 (30-60 PC slots differ) -> those materials stay PART | `work/n6shaders_0711/vs_twin_cmp.py` | ✅ |
| MaterialParams longer on PC | `tu_unlit apply` keeps a PC params block that is longer than the Xbox one (32 copies in n6); harmless per copy: the new PS reads no c100+j with j >= Xbox count | `verify_n6.py` | ✅ |
| ABS_CONST in lit translations | `fix_abs_consts` makes abs uniform per register (X6045) but left `-\|cN\|` forms (e.g. 2527 `cmp r8, -\|c221.xxxy\|, r5.zxyy, \|c221.y\|`): installed 35 libs (2527-2584, 2810-2827), whole install stack 56 libs / 432 shaders / 32 DRMs; NVIDIA accepts, the AMD driver rejected the form on 20.10. Fix (17r): `fix_abs_native` = `mov rT, cN` (a temp the shader never uses, reused until the next flow-control instruction, relative reads reloaded) + abs on rT; no free temp (1 / 432) -> one bit-exact def literal; never two constant registers per instruction. `vm_exact` proves it bitwise (oC0..3, oDepth, kill; 3 seeds): 432 / 432; D3DX9 1278 / 1278; tree `work/amd17r_0811/tree` (stack step 10) = ABS_CONST 0 / X5584 0, native test on NVIDIA 0 refused | `tu_light_transplant.fix_abs_native`, `tu_batch.py nativefix`, `pack_lib` | ✅ offline + NVIDIA / ⬜ AMD |
| Upstream B269 / B270 ABS_CONST rewrite | `-\|cN\|` folded into a new def literal, the second operand left as plain `cN.y` -> two constant registers in one `cmp` (X5584), e.g. B270 lib 2889 `cmp r5, c217.zzzy, r7.zxyy, c221.y` (ours 2811 `cmp r5, -\|c220.zzzy\|, r7.zxyy, \|c220.y\|`): B270 500 shaders / 1500 instructions / 88 libs; `rcp` via `mov r1, c223` + `\|r1.z\|`. B270 is therefore not native-D3D9-clean (the form B138 failed with on 30.10.); no B270 port shader is in our trees | `work/amd17r_0811/pair_examples.txt`, `b270_pattern.txt` | ✅ data |
| Native D3D9 test of the installed tree (08.11., NVIDIA, driver 32.0.15.6094, d3d9.dll 10.0.19041.5794, device HAL hardware VP + pure) | 295 DRMs, 2919 unique shaders (new PS 718 / VS 20); static: ABS_CONST 272, SINCOS_SAME 0, ERR 0, LONG 336 (GPU 4096 slots), NEW_FORM 684; GPU: **0 port shaders rejected**, negative controls 3 / 3, decl 26 / texture 104 / RT 9 ok, depth DF24 refused (ATI FOURCC, expected on NVIDIA) | `tools/native_test` v3 (copy in `work/native0811`) | ✅ NVIDIA / ⬜ AMD |
| Probes `feat_ps_add_absmod` / `cmp_absnegmod` / `mad_absmod` | refused on NVIDIA, but they read the **same constant with and without abs** in one instruction (`add r0, c0_abs, c0`, def c0) - the mixing that `fix_abs_consts` already removes; single-read `rcp` / `rsq c0_abs` pass. They do not isolate abs on a constant, so they say nothing about the AMD form. Isolated probes (17r) `probes/abs_ps_*.bin`: abs / -abs once on a uniform in cmp / add / mad, on a def literal in cmp / add, one constant read twice with abs (def / uniform), control = the 17r rewrite - all 8 accepted on NVIDIA (08.11.) | `tools/shader_disasm.py` on `tools/native_test/probes` | ✅ NVIDIA / ⬜ AMD |
| Shader form gate | `tools/shader_form_gate.py check TREE`: per unique port shader (PC-game md5s apart) the hard forms ABS_CONST / SINCOS_SAME / ERR (native_extract `analyze`) and X5584 (two distinct plain constant registers in one instruction); warnings NEW_FORM / LONG. Wired into `Install-TruTree.ps1 -ShaderGate` (before `-Check` returns / before copying) and `Invoke-TruPipeline.ps1 -ShaderGate` (Fixes: both DLC trees, Repair: b138_fixes); Install-TruTree default **Enforce** since 08.11. 15:10 (17z: all ten trees of the install stack pass `--enforce`; clean copies of steps 1 / 2 / 4 / 6 in `work/clean17z_0811`, step 10 = 2 DRMs whose ABS_CONST came from the installed folder); the pipeline stays Report until a full run is clean. Counts 08.11.: installed ABS_CONST 272 (35 libs), n6b test tree ABS_CONST 336 -> 0 (clean copy), X5584 0 / SINCOS 0 / ERR 0; selftest 6 / 6 | `tools/shader_form_gate.py selftest` | ✅ (install Enforce / pipeline Report) |

### 17.5 Known material cases

| Material | Fact | St |
|---|---|---|
| 23164 end-room light column (`dlc_yggdrasil_end`, terrain 20969) | installed surrogate PS 1910 (refraction) reads s2 = back buffer, s3 = depth -> shows the room behind it. Fix tree `work/endcolumn_0711`: PS 2851 / 2988, PS0 2491, VS 1911 kept (proven equal to 1737); installed 07.11. 23:39 for the test: translucent, blue, flowing | ✅ **live 07.11.** (first live shader translation) / ⬜ Xenia image |
| End-room tower / column on the right (23153 / 23155 / 23163) | surrogates without a refraction shader; showed rainbow fringes for a while after shadow power (afterglow of the power's look? 🔶) | ⬜ |
| 26584 DLC 2 treasure room | VS 2066 = Xbox 1258 + TEXCOORD3 / 4 -> correct VS = PC 868 + TEXCOORD3 / 4 (the def-clash case); PS 830 -> 3090, VS 831 -> 3091 in `work/n5b_0711` | ✅ / not installed |
| 8 DLC 1 streamgroup copies (23211, 20270, 23462, 20773, 21259, 20548, 20268) | translated PS libs 2961-2966 | ✅ built |
| 20744 shadow-power look | full-screen quad (event 0x32 -> 0x535cc0 -> effect 0x85 -> 0x547220 -> 0x548bf0 -> 0x546340 -> quad 0x53ef30); black because of surrogate PS 2517 + 0 MaterialParams; fixed PS 2943 / VS 2944 | ✅ |
| Streamgroups | contain only materials, shader libs, textures, terrain, tiny DTPs; 80 materials drew with surrogates (71 only in streamgroups; 19 half translated - load order decides) | ✅ |
| Coverage (installed) | 770 materials: SURR 130, PART 89, TU 38, ORIG 308, BASE 205; no shader translation installed in the kit (owner decision 07.11.; only the end-column test tree was installed for the live test) | ✅ |
| Coverage after n6 (test tree 08.11.) | installed + n5mats / n5b / extfix + n6: SURR 16 / PART 143 / TU 98 / ORIG 308 / BASE 205; end-room surrogate terrain 0 %; PART left = pass 0 / 1 (not translated by rule) or a C1 VS not proven equal; 16 SURR = refused patterns (17.4) + 24275 tail probe; PS 3400-3458, VS 3480-3486 | ✅ static / ⬜ live |
| 25057 `dlc_yggdrasil_end` floor (terrain 20273 Y 43, at the shadow-power hint 5181) | surrogate PS 732 (C3, score 0.229) mixes the Xbox `Param` map 7346 (blue) as a colour layer and goes < 0 for Setup weight R -> cyan / black blocks (Lukas live 08.11.); textures and records = Xbox (also = B270); B270's own lib 2815 is right; N6 3410 reads the wrong atlas sampler; fix tree `work/floor_0811` PS 3460 (group Xbox 2346, 16 materials / 36 copies in 12 files - an alternative to the n6 tree, never stacked) | ✅ offline harness / ⬜ live |
| 20265 DLC 1 (9 streamgroups) | same Xbox libs 2063-2066 / VS params / vertex format as 26584 -> VS 243 -> 3091; PS 2783 (B138) -> 3500 (Xbox 2065 for 20265's own record signature, 8 slots 1.000); params = Xbox except c100.w kept 1.0 for the pass-0/1 donors 240 / 241 (3500 reads only c100.xyz); test tree `work/shader17c_0811` - withdrawn 08.11.: the per-instance kind 1 (Xbox) has no PC partner (PC kind 2), the fixed verify fails 3500 (VM 0.080); 20265 stays on B138 2783 until the Y-record indices are checked | ❌ withdrawn / ⬜ |
| 20265 withdrawal cause (17p) | the B138 kind-2 record reads Y idx[1] (empty) -> after restoring kind 1 / default 121 tu_batch pairs kind 1 with kind 1 and a 3500-style PS can be rebuilt and proven; pass-0/1 donors 240 / 241 read only s3 (unaffected); B138 PS 2783 replaced in the same step | ✅ cause / ⬜ build |
| 20265 rebuilt (17q) | record kind 1 / default 121, PS 2783 -> 3534 (Xbox 2065), VS 243 -> 3091, c100.w 1.0 kept; test tree `work/q17q_0811/tree20265` (3 files on the n6b copies, 6 on installed): verify 9 / 9, vcheck 9 / 9 1.000, byte rule 9 x 0 failed, io 9 / 9, pass-0/1 inputs 18 / 18, native D3D9 0 rejected | ✅ offline / ⬜ live |
| Coverage with EQUIV (08.11.) | installed (end-column test installed): SURR 129 / PART 89 / TU 39; + n5mats + n6 (+ 17c): 16 / 142 / 99; 23164 now TU T-TO; the installed `TruMenu.shaderlabel.txt` (07.11.) is outdated (new data files in `work/shader17c_0811/trumenu`) | ✅ |
| Coverage after n6b (08.11.) | installed + n6b (n5mats / n5b / floor absorbed): SURR 7 / PART 149 / TU 101 / ORIG 308 / BASE 205; PS 3400-3460 kept where byte-identical, 3510-3533 new (lower layers 2961 / 2964 / 2965 / 3090 -> 3530-3533); 21118 pass-1 lanes open (proposal: material-own copy of 2037 with the three lanes as def literals); 23211 has two byte-identical libs 3519 / 3530 | ✅ static / ⬜ live |
| Same id, different translations | 24299 / 24690: installed `dlc_level2_start` copy = lib 2675, n6 copies = 3407 (different code); 23552 `co_dlc_lara_f` (3411 / VS 114) vs `dlc_costume_f` (2754 / VS 122) - the first loaded copy wins, unify before install | ⬜ decision |

Plugin: TruMenu 0.21.7 shader labels (`shader.labels`, data `shaderlabel.txt` from `tools/shader_labels.py`; slot letters O
twin / T translation / S surrogate; file state vs. live state from the current material `[0xa14188]`): ✅ **live 07.11.**
(column 1: file "23164 SURR S-SS 1909/-/1910/1911", live "PART T-TS 2491/-/2851/1911"; VS 1911 = 1737 should count as
equivalent, else the label says PART instead of TU). Sources: `Befund-Shader-Etiketten-0711.md`, `Befund-Saeulen-Shader-End-0711.md`,
`Befund-N5-Materialien-0711.md`, `Befund-Streamgroups-Shader-0511.md`, `Befund-Shader-Nacht.md`, `Befund-Look.md`,
`Befund-Wasserfall.md`, `Befund-Materialien-B270-0511.md`; [PIPELINE.md](PIPELINE.md) stage 3.

---

## 18. Sound

### 18.1 SoundPlex (node trees in DTPs)

| Node | Handler / layout | St |
|---|---|---|
| Walker | `FUN_005920b0`, jump table 0x5923cc, 14 types; node {u32 type, ptr data}. Null data on type 0 -> AV 0x592218; u16-swapped type words (e.g. 0xb0000) fall to the default and return NULL harmlessly (seen in costume DTPs, knight_thrall, adren_trap) | ✅ |
| 0 TimeIn | walker case 0x5921f9: allocates 0x1c B, reads **only the f32 at data+0** (`fld [data]`), ctor 0x583bf0 | ✅ |
| 1 Indirect | data -> DTP id | ✅ |
| 2 Wave (leaf) | 0x591220: data {+0 u32 wave id, +4 u8 (passed to 0x5825e0), +6 u16 (non-zero runs an extra channel-mode branch 0x7b9f6f / 0x7b9f4b with \|0x80000000)}. Group table `[0x8a80d8]` indexed by params+0x14; the bounds check 0x591281 only logs -> a raw group value is an AV. A u32-swapped +4 word turns the byte into 0 and +6 non-zero | ✅ |
| 4 Assign | 0x590970, 0x48 B: +0 child, +4..+0x3c s32 / f32, +0x40 s32 sound group (0 / -1 inherit), +0x44 {u8 max instances, u8 counter, u16} | ✅ |
| 5 Envelope | 0x590ce0: data {+0 ptr child node, +4 u32 track count, +8 ptr -> track ptrs, +0xc ptr}; allocates 16 * count (a raw count gave a 256 MB OOM). Track {u16 parameter index, u16, ptr curve}. Curve {s32 loop / hold start, s32 loop / hold end (-1 = none), u32 point count, points of 12 B {f32, f32 value, flags}}. The ctor tests BYTE [point+8]: bit 1 -> curve+0 = point index, bit 2 -> curve+4 = point index | ✅ |
| 8 | data word is an id (surface variant) | ✅ |
| 10 Sequence | ctor 0x58e070 (vtable 0x85127c), update 0x593720; data {u32 count, children, ptr, **s8 repeat** + 3 B}; **repeat 0 = endless**; the +0xc word must stay raw | ✅ |
| 12 DSP | {child, u16 DSP kind, u16 0, params, 0}; chain 0x59219f -> 0x58def0 -> 0x58dad0 -> 0x587620 (kinds 1..11, table 0x5876fc) -> FMOD createDSPByType 0x7b98ea; kind 7 -> FMOD type 5 (highpass 🔶), params 0x582ec0 (2200.0, 1.3334); out-of-range kind = no DSP, no crash | ✅ |

Data bugs: endless groans = Sequence +0xc swapped as u32 (43 words in 13 files; step `seqrepeat`,
`soundplex_sequence_fix.py`); `dlc_caverns_hall` DTP 23469 +0x74 DSP kind raw (0x0700) -> no highpass
(`soundplex_dsp_kind_fix.py`, step `dspkind` since 08.11.). ✅ Envelope flags word u32-swapped in `player_tru_dlc2_extension.drm` DTP 22864 +0x1e4
(shadow-power loop sound): no hold point; the twins truth is the u16 pair (Xbox `00 03 00 00` -> PC `03 00 00 00`, the
converter wrote `00 00 03 00`). The installed `doppelganger_casual.drm` lacks the twins words (391 wrong words in 35
SoundPlex DTPs, incl. the moan trees 26086 / 24556 / 22718 / 26183 / 22713 / 22711 / 22961): 299 Wave +4 words u32-swapped
(`0000005a`: the PC reads +4 = 0 and +6 = 0x5a00 and takes the extra 0x7b9f6f / 0x7b9f4b branch; meaning of bit 31 🔶),
41 List +0xc, 10 Assign +0x44 (u32-swapped `00000001` gives max instances 0, effect 🔶), Reaction / Overlap / Indirect.
Test tree `work/dopp_0711` (08.11.): 390 words set from the twins truth, DTP 20212 +0x4c550 kept as installed (the proven
translist layout runs after the twins and wins); the installed file was built from the 51v fix chain, so the pipeline
file must not be copied over it (31 type-9 libs incl. 2943 / 2944 and 25 materials only exist installed) ⬜ live. Open:
4 Chart 20212 words (+0x49754 / +0x49874 / +0x498e4 / +0x49b14) raw installed vs swapped in the full run 0711 ⬜. ✅ static (`work/moan_0711`: `pc_envelope_590ce0.txt`,
`pc_wave_591220*.txt`, `twins_report_*.txt`). Sources: `Befund-Stoehnen-0511.md`, `Befund-P4c-Caverns-0711.md`, N3 report
08.11., from FINDINGS.md.

### 18.2 Emitters and object sound slots

* Anim event kind 0 -> 0x5b99c0: byte0 = 0 emitter via 0x5935d0 (sound manager `[0x8a8100]`); the emitter joins the
  instance sound list `[inst+0x248]` only if payload byte1 bit 0 is set, otherwise the handle is freed at once (a looping
  plex then never ends). byte0 = 1 -> 0x5953e0 (sound by section id, 7 args; lookup 0x54df80 = `[0xc36f28+id*4]`). ✅
* Anim event kind 2 -> 0x5b9fd8 -> 0x5b69c0 (type table 0x5b6b30) -> slot object 0x593d50(slot, mode, p3, p4); instance
  sound object 0x58d6a0: count `[obj+0xa8]`, table `[obj+0xac]` (8 B per slot). TU passes a 5th argument (0x8226de00) - not
  ported ⬜. ✅

### 18.3 Sound groups (FMOD channel groups)

Table from `globalsoundinfo.drm` DTP 792 (`[0xccdea0]` = DTP+0xe0, set 0x5df0c9); runtime `[0x8a80d8]` / count
`[0x8a80dc]`; CreateGroups 0x593530 -> 0x591ef0. PC 77 groups, TU 80 (77 / 78 DLC 2 player, 79 shadow-power loop). Header:
death list 70 / 76, pause list 6 / 25 / 3 / 9 / 79 (handler 0x5874b0), category slots [0] music 1, [1] effects 4, [2] speech
7, [3] srmusic 10, [4] default 14, [5] cinstream 25, [6] 53 (reader ⬜). Entry 0x84 B: +0 f32 volume (sliders 0x587171,
SetVolume 0x587770), +0x10 flags (bit 0 paused), +0x68 parent; R+0x6c = FMOD ChannelGroupI. `SOUND_ResetGroups` 0x5895f0.
Mute `ChannelGroupI::setMute` 0x7c48cd (TruMenu `media.mutemusic`). ✅ Tool `tools/sound_groups.py`.
Group 10 (category [3], srmusic / `media.music`) is a child of 3 -> 2 -> **1 (the MusicVolume slider)**, so MusicVolume 0
silences the music players too (🔶 effective volume = product along the parents, not measured live;
`sound_groups.py table pcbig:globalsoundinfo.drm`, 2026-11-10).
Per-group factor without touching the game's volume (entry +0 stays): `*(float *)(cg + 0x38)` of the group's FMOD
ChannelGroupI, then FMOD's own recompute 0x7c4774; a group whose ancestor (+0x68) is in the same set is skipped, two
factors on one path multiply; new channel groups after a level load must be written again. TruMenu 0.21.8 `snd.group`
sliders (8 sets of groups, `[SoundGroups]`): built (6 byte checks); audible effect and whether the game writes cg + 0x38
itself ⬜.
Source: `Befund-Ton-Gruppen-0611.md`.

### 18.4 Streams (.mul) and music

* .mul streams (cinstream, vo, event, music) use the game's own MMX IMA decoder 0x5957a0 (init 0x595670), whose step table
  0x8a9588 is **capped at 0x1fff** (max per-sample delta 15358); FMOD's own IMA decoder is used for DRM wave sections only.
  The S-sound fizz came from an encoder that did not know the cap: `tools/mul_audio_nch.py` encodes against the exact
  decoder model. ✅ (`Befund-S-Laute.md`)
* History: all DLC audio was first emitted as silence on purpose; real audio = Xbox XMA decoded and re-encoded as IMA
  ADPCM into the same-size wave sections / `.mul` streams. ✅ (from FINDINGS.md)
* .mus version check 0x580eac `cmp [edi+8], 0x114`; music start 0x593eb0 (= retail 0x82248760); stream path builder 0x58aa40
  (`"%s%s.mul"`). All 25 DLC tracks are real audio. ✅ (`Befund-DLC-Musik.md`)

### 18.5 Language

Registry `Language` read at 0x477ee8 -> `[0x8900e4]`; SetLanguage 0x49a900 -> mask `1<<lang` (state machine 0x54f260,
writer 0x54f300, `SetSpecialisationMask` 0x472990). `ArchiveFileSystem::FindEntry` 0x4726e0 (hash 0x472670, binary search,
first record with `(spec & mask) == mask`). Spec words EN 0xffffffe1, FR 0xffffe002, DE 0xffffe004, IT 0xffffe008, ES
0xffffe010, neutral 0xffffffff. Merc barks: 669 names, 490 in 5 languages, only in the ship units. Plugin TruMercLang 0.1
(second FindEntry search with another mask; built). Doppelganger lines: only English installed, 20 variants built by
`tools/vo_lang_variants.py` (installed since, `_001` .. `_016`). ✅ Source: `Befund-Tonspuren-Soeldner-0611.md`, [TruMercLang README](../src/asi/TruMercLang/README.md).

Speech language at run time (2026-11-10, static; source `Befund-Sprache-Live-1011.md`, tools `tools/lang_spec_census.py`,
`tools/voice_catalog.py`):

| Fact | St |
|---|---|
| **Switch chain:** SetLanguage 0x49a900 (callers: start 0x479e35, option 0x95 callback 0x5d4f30, which also writes P+0x206) returns at once when lang == `[0x8906b8]`; else stores it and calls **0x54f2e0(1 << lang)**: when the FS mask (MultiFS vtbl +0x14) differs it stores the mask in `[0xc57200]`, state `[0x8a6eb4]` = 0, and calls the stepper **0x54f260** until the state is 2 - a blocking loop on the caller's thread: each step runs MultiFS +0x1c (process queue 0x473680) and +0x18 (busy 0x472be0) and advances the state only when idle; at state 1 it reads the old mask, calls MultiFS +0x10 **SetSpecialisationMask 0x472d80** (forwards to every mounted FS: list +4 stride 0x28, count +0x57c), reloads `locals.bin` (0x49a800) and calls **0x54f070(old, new)**: for every node of the DRM list `[0xc56fc0]` (+0x10 next, +0x1c name) with `(old ^ new) & ~[node+0x14]` != 0 it logs "Reloading DRM %s" (0x84c6dc) and queues a reload (receiver 0x54ec00, 0x70 B); meaning of node +0x14 ⬜ (the node ctor 0x5512e0 zeroes it). Then 0x49a900 refreshes UI strings (0x47a2c0) and calls 0x4753f0. Only `[0x8906b8]` readers: GetLanguage 0x49a730 (callers 0x4539a9 subtitles, 0x4a0d79 Bink, 0x555c99 profile P+0x206, 0x77c511) | ✅ static |
| **Per open, no cache:** ArchiveFS RequestRead 0x472890 runs FindEntry per request; OpenFile 0x473020 binds the record into a file object (vtbl 0x84402c, +4 record, +8 part). Every `.mul` stream object opens its file **once** in Init 0x58aa40 (only call 0x58ab72 -> 0x582770 "SNDAPP_StreamOpenFile": FileExists + OpenFile), so a mask change reaches the next stream that opens and never one that plays. Creators: **0x58ac60**(name, mode, -1) kind 0 `audio\streams\<name>.mul` (only caller the SoundPlex stream node start 0x58bab0; walker case 3 -> node ctor 0x591080), **0x58ace0**(name) kind 1 `cinstream\` + cinematic handler 0x454b80 (caller 0x5b2493), **0x58ad60**(name) kind 2 music (caller 0x58be4c) | ✅ static |
| **ModLoader 1.2** (third-party, read only): `HookFileSystem` (vtable 0x10006328, ctor 0x10001bf0: +4 inner disk FS, +8 = +0xc = 1) is mounted at the **front of the game's MultiFS** with the game's own Mount (found by the bytes of 0x472c50; args fs, 0, front 1); its SetSpecialisationMask 0x10001ef0 stores +8 and `mask & 0x7fffffff` at +0xc and does not forward; FindFile 0x10001cb0 formats `%s_%03d` with **+0xc on every call** and asks the inner FS (vtbl +8), else the plain path. So the game's MultiFS +0x10 reaches it; the ModLoader suffix for Dutch (mask 0x800) is `_2048`, while the installed `locals.bin_032` matches mask 0x20 = language 5 (ja in the enum, row "Language ids"), so a Dutch game never loads it (🔶 not seen live) | ✅ static |
| **Language census** (`lang_spec_census.py`): PC bigfile language variants only for `cinstream` 38 `.mul`, `vo\lara` 499, `vo\enemy\merc` 490 (each EN / FR / DE / IT / ES), `image\demo_controls(_4x3).raw` (5) and `local\locals.bin` (6 tables: fffff7e1 / 2 / 4 / 8 / f0, **ffffffe0 = Dutch**, game language 11); language-neutral: 15 cinematics, 24 Lara efforts, 179 merc, 188 kraken, every env / event / music stream and **all 1004 `.drm`**. pack10 7 / pack11 13 records per speech language, patch.000 and TU only `locals`. **0 audio records serve Dutch (bit 11) or any bit other than 0-4** - Dutch speech is the English record everywhere | ✅ data |
| Bink: 0x4a0d79 GetLanguage -> `BinkSetSoundTrack(1, &lang)` (lang >= 13 -> 0) at video open; `prevontr.bik` has 5 audio tracks (ids 0-4), the other 5 videos one | ✅ static / data |
| Cinematic variants differ in length (060_med_natla EN 3309 cine frames, DE / ES 3335): a mid-scene switch at the same time would not land on the same animation frame | ✅ data |
| **Speaker per line:** no subtitle carries a `<name>: ` prefix (base 3253 entries in 53 cinematics, 4484 in 711 Lara / kraken lines, DLC 0 of 678 records); the cinematic sound is one mixed stream and the cine blocks name no actor per line, so the speaker is known only from the path (`vo\lara`, `vo\dlc1\lara` / `zip`, `vo\dlc2\doppelganger`, `vo\enemy\merc\b_mNN`). Lara's help-on-demand lines `vo\lara\sc_NN_MM_{hint,answer}` (499, subtitles in the stream) are named only by `generalbank` dialogue DTPs (e.g. 574 / 575 = sc_04_01), her 24 neutral effort lines by the `lara*` costume DRMs; `generalbank` DTP 36 names all 53 cinematics, each also by its unit DTP; DLC 1 conversations = DTP 23938 (`dlc_dungeonhallb`, Zip / Lara / Zip) and 24035 (`dlc_caverns_hall`), no subtitles | ✅ data |

Crash guards in this area (B138 exe, from FINDINGS.md): `fmod_init_guard` - audio init 0x582200: a failed FMOD
`System::init` leaves three locals uninitialised -> AV 0x7b92fb; the guard zeroes them. `soundplex_guard` hooks 0x5920d5
and returns NULL for null-data nodes (not for types 2 and 8, which handle it themselves). The exact bytes are in
`tools/*_guard.py`.

**The whole B138 exe patch** (`tools/exe_cmp.py` Steamless output md5 `56d1ce2d...` -> B138 `5560abac...`, 2026-11-10,
finding Befund-Kit-Unabhaengigkeit-1011): no new section, same size; header LARGE_ADDRESS_AWARE (Characteristics
0x103 -> 0x123) and `.text` writable (0x60000020 -> 0xe0000020, for the guard counters); 5 sites + 6 caves at the zero
tail of `.text` (0x83de00..0x83dffc): `light_tex_guard` 0x50a645 / 0x50a683 -> 0x83de60 (counters 0x83de20),
`fmod_init_guard` 0x582200 -> 0x83de00, `soundplex_guard` 0x5920d5 -> 0x83df40 (counters 0x83df00) and a fourth guard
**without an upstream tool**: playerDrawCombatLock 0x71e710 (6 bytes `push ebp; mov ebp,esp; and esp,-16` -> `jmp
0x83dfd0; nop`), cave: if `this` and `[this+8]` (lock target handle) are non-zero and the handle resolver 0x5b39d0 returns
0, `[this+8] = 0`; then the three original instructions, back to 0x71e716 (TruShadowPower's `kRingEntry` hooks right
after it). The three upstream guard tools applied to the Steamless exe leave exactly 47 bytes different from B138:
the LAA bit (file offset 0x116) and this fourth guard. ✅ static (bytes compared)
The fourth guard has a tool since 2026-11-10: `tools/combat_lock_guard.py` (44-byte cave, instructions in its
docstring; `--check` says "patched" on the B138 exe, "original" on the Steamless exe; selftest 7 cases). `[this+8]` is
a pointer to a handle pair {object*, serial}; the resolver 0x5b39d0 (cdecl, writes ecx / edx) returns the object when
pointer and object are non-zero and `[object+0x44] == serial`, else 0. The cave saves ecx around the call; eax / edx
are overwritten by the function itself (0x71e716 / 0x71e725) before they are read. Not covered: a `[this+8]` that
points to freed memory (the resolver reads through it). The whole exe patch is pipeline step `Exe`
(`tools/exe_build.py`: Steamless exe md5 `56d1ce2d…` -> LAA -> `fmod_init_guard` -> `light_tex_guard` (+ `.text`
writable) -> `soundplex_guard` -> `combat_lock_guard` -> section check -> gate): output md5 = `5560abac…` = B138,
byte-identical. ✅ static (md5 gate)

---

## 19. Costumes

| Step | PC | TU | St |
|---|---|---|---|
| Current costume | `[0xe7f1c8]`; altPlayerObjectID 0xe7f1cc | +0x144(r29) | ✅ |
| Save | 0x555be0, line 0x555cb1: game block +0x20c = current | 0x821fef58: 857 -> store **11** | ✅ |
| Load | 0x556fbd: current = +0x20c | 0x821ff1e0: 11 -> 857 | ✅ |
| Level load | 0x5de2b0, decision 0x5de2d6 (`+0x1f4 == 0 ? +0x20c : +0x210`), else unit default 0x5de379 (`[[unit+8]+0x70]+0x294`) | 0x82297d30 | ✅ |
| Spawns | 0x5d42e9 (player spawn 0x5d40c0), 0x5d4469 (costume switch 0x5d4340) | 0x822973b0, 0x82297f10 | ✅ |
| New-game reset | 0x556abe (+0x210 = +0x20e = +0x20c = 0) | 0x821fe9a8, called on every mission start by `MainTracker_UILoadLevel` | ✅ |
| Validator | 0x5c54e0 (id <= object count and `<name>.drm` exists) | | ✅ |
| Player type table | 0x8aba28 (0x1c B records, 36 records 0-11, 15-38) | 0x8275ae38 record 35 = doppelganger | ✅ |

Ids: **857 = `doppelganger_casual`** (player object of DLC 2), **11 = `lara_doppelganger`** (unit default of the DLC 2
units), DLC 1 units default 25 (`dlc_costume_f`); costume objects 20-35 = `dlc_costume_a..p`. Outfit offer (generalbank
script 6 function 26): `dlcsystem` f1 per name, offered only if its DRM exists - no unlock flag (same on PC, TU, ours) ✅.
Plugins: TruDlc2Player 0.1 `Costume` (name substitution at 0x5de3a3), `TypeRecord` (record 39 appended), 0.3
`CostumeReset`, 0.5 `[Costume] TuMapping` (all four sites or none; default 0): built, live ⬜. Without the mapping PC saves
from DLC 2 hold 857. Not ported: the altPlayerObjectID store and the TU spawn fallback ⬜.
Data: costume model u16 arrays and list counters (`tools/costume_dtp_fix.py`, pipeline step `costumedtp` since 08.11.; costume f missing 586 words installed; our
own costume chain a / h / k / l / m has the same fault). Slots g / n and `dlc_costumes4` never shipped (owner decision E4).
Sources: `Befund-Kostuem-Reset-DLC1.md`, `Befund-Kostueme-Port.md`, `Befund-P4a-Kostueme-0711.md`,
`Befund-Menue-Dlc2Player-0411b.md`; [COSTUMES.md](COSTUMES.md), [TruDlc2Player README](../src/asi/TruDlc2Player/README.md).

---

## 20. Player, doppelganger, shadow power, HUD

### 20.1 Doppelganger player and extension object 858

| Item | Fact | St |
|---|---|---|
| Doppelganger flag | player tracker +0x1244; only TU writer 0x82412c84 in DoppelgangerInit 0x82412c48 (reset = new tracker memset). PC readers: larabase f36, 0x7200d6 / 0x7200df | ✅ |
| 858 `player_tru_dlc2_extension` | child of 857, data type 60; created only by TU-only 0x82412ab0 into tracker+0x1314; unloaded with 857 on reload | ✅ |
| 858 tuning | DTP 22497 block +0xf0: meter max 1000, drain 200 / s, refill 200 / s, restart 150, world scale 0.3, player scale 1.2; target-finder params +0x90 / +0x94; K9 pairs +0x1b0..+0x1bc (`tools/player_ext_tuning_fix.py`, pipeline step `exttuning` since 08.11.) | ✅ |
| Player list (K12) | 857 must be in GlobalInfo DTP 2 (PC 28 -> 29), else unit unload 0x5c1900 dumps the object (`STREAM_DumpObject` 0x5c16d0), the reload spawn returns 0 and the camera crashes at 0x5ff851. Fix `globalinfo_player_list_fix.py` ✅ live (no crash on reload) | ✅ |

Plugins: TruDlc2Player (`FlagReset` hook at 0x722445, `TrackerFlag`), TruShadowPower (object search in 0xdb7400 instead of
the TU creator, `[Meter] Fallback`).

### 20.2 Shadow power

TruShadowPower translates TU 0x823d7700..0x823d8380: tick / start / stop / gates, slow motion via the time-scale natives
(section 3), meter / bar from 858. Tick gate (0.16): `[0xfadb58]` != 0, `[0xe7f094]` != 0, main state 1, +0xb9 = 0 (fixes the
AV at 0x77bdd3 when there is no Lara). HUD feed: fraction to float 0xfae8d4 (hudscreenmgr native 36), display group via
0x77d9d0 on mask 0xfae924; the PC adrenaline bar 0x6f2930 writes 0xfae8d4 every frame. Adrenaline look: retail start
0x7189c0 / stop 0x718ad0, selector 0x5e7fe0 picks camera mode 0x34; TU uses meter flag 0x40 (`[Look] AdrenalineMode`).
Time-scale requests (TU, TruXenia): meter object +0x40 = 7 slots x {f32 player, f32 world} (0 = unused); selector
0x823d7520 (called with meter+0x40 at 0x823d7d1c) walks slot 6 -> 0, the highest slot > 0.0 wins per scale (threshold
constant 0x8207d538 = 0.0, fcmpu / ble at 0x823d7578; 0 and -1 are both empty), ramp targets
player 0x827754ac / world 0x827754cc (= PC 0x8abe94 / 0x8abeb4); slot writers in `Befund-X23-Kraftlauf-0911.md`. ✅ static.
Live 2026-11-09 (goo drip, end level, TruMenu `fight.trace`): with the power on and Lara running the PC stays at world
0.30 / player 1.20 (request `0:1.20/0.30`, power mode "slow") for the whole run; the Xbox (TruXenia 18:06) switches to
world 1.00 while running. ✅ live (difference measured). **Correction 2026-11-10:** that slot 6 causes it was an
inference and is most likely wrong - no DLC 2 script calls the gamebase natives 23 / 24 (only base Lara script 205 f1
"Heads up!!!" and DLC 1 script 3583), and TruMenu counted 372 time-scale setter calls that evening, all from
TruShadowPower, none from tru.exe. On the Xbox the meter stood still at 893.5 from 18:06:02.14 to 02.70, exactly when
the world went to 1.00, then drained ~200 / s at world 1.00. What sets world 1.00 there is open (TruXenia: log
`ts_requests` and the ramps at the goo drip). Slot 6 itself is translated in TruShadowPower 0.21 (untested).
Slot 6 (2026-11-10, static + PC log): written only by the TU versions of the `gamebase` natives 23 / 24 (script 55 f23
@0x3f8 / f24 @0x414; TU binder 0x824a28c0 +0x298 / +0x2b4 -> 0x824a3238 / 0x824a32f0; retail binder 0x8249ced0 ->
0x8249dac8 / 0x8249db18; PC binder tru+0x3b44a0 at tru+0x3b4548 -> tru+0x397cf0 / tru+0x397d10, cdecl, args at
[esp+0xc]). With player state [0x829892b0], tuning 0x82415518, +0x1244 and meter +0x508 set: args[0] -> meter +0x70
(native 23, store 0x824a3280) / +0x74 (native 24, 0x824a3338), selector; else the retail ramp (23 world, 24 player).
(`gamebase` f1 / f2 = TU 0x824a30b8 / 0x824a30d0 write the current world / player scale 0x82efb458 +0x118 / +0x150
directly, unchanged by the TU.) +0x70 is the slot's PLAYER value,
so the doppelganger branch is crossed against the retail meaning; the duration args[1] is unused; value <= 0 empties the
slot. Neither native reads speed / state / input. Script callers in the DLC data: only Lara script 205 f1 ("Heads up!!!",
vtable slot 55: f24(p0, p8), f23(p4 x p0, p8)) and DLC 1 script 3583 - no DLC script refers to 205 f1's prototype. PC
2026-11-09 evening (TruMenu ramp counter): 372 setter calls, all from TruShadowPower, none from a script - no native 23 /
24 call at the goo drip; the Xbox log there shows the meter standing at 893.5 for 0.56 s when world goes to 1.00, then
draining at 200 / s. So slot 6 is probably not the goo-drip mechanism (open). TruShadowPower 0.21 `[TimeScale]
TranslateSlot6` translates the natives (jump + trampoline, one log line per slot-6 change). ✅ static; live ⬜.
Status: gameplay partly live; look and one-shot sounds built or not ported, live ⬜. Sources: `Befund-Schattenkraft.md`, `Befund-Schattenkraft-0411b.md`,
`Befund-TruShadowPower-016-0611.md`, [TruShadowPower README](../src/asi/TruShadowPower/README.md).

### 20.3 HUD natives

* `larabase` f70-f73 (TU): f70 delay = tuning +0x24; f71 strike ready (flag 8 and > 75 %); f72 CanStart (red when 0); f73
  delay left. HUD script 37 (Xbox 38) function 15 runs them only behind larabase f36 (`op69 f36; op50; op64`). ✅
* `dlc2data` (TU-only): f0 = byte +0x1244, f1 = hint-box byte (no PC reader). TruShadowHud registers the type after larabase
  at 0x7a946f (ctor 0x574b60, vtable copy of globaleffect 0x86279c) and hooks larabase vtable 0x862a38 slot 3. Needs the TU
  HUD generalbank (`generalbank_hud_build.py`); never install that generalbank without TruShadowHud. Built, colours live ⬜.
  Source: `Befund-Schattenleiste-HUD.md`, [TruShadowHud README](../src/asi/TruShadowHud/README.md).

### 20.4 Cloth / braid time step (K1)

Cloth (type 14) update 0x5bbe70, site 0x5bbec2 (`fld [0xe7f188]`): the TU divides dt by the world time scale `[0xe7f1a0]`
for the player instance (TU 0x82278120), so the braid does not freeze in slow motion. TruShadowPower 0.15 `[Cloth]
TuTimeStep` (default 0): built. Source: `Befund-F20-Zopf-0611.md`.

---

## 21. Input

| Item | PC | St |
|---|---|---|
| XInputGetState pointer | **0xa02b8c**; only writer 0x482513 (GetProcAddress 0x482505); call sites 0x482619 (presence, every 500 ms), 0x48620a (device check), **0x484b82 per-frame poll** (function 0x484b70, pad index `[ebp+0x894]`, packet number 0x484b95, wButtons 0x484bc3) | ✅ |
| XInputSetState | `[0xa02b90]`, single call 0x4849b5 (motors from device +0x898 / +0x89c) | ✅ |
| Input map | GlobalInfo +0x1c -> PC generalbank DTP 47 (Xbox 48); bindings {u8 action, player, srcA, srcB} in 0x18 B records; action records 0x30 B, 256 per player at 0x9fcb68 + player*0x3000 (8 up, 4 held, 0x10 pressed, 0x20 released); ctors 0x4868b0 / 0x480bc0 | ✅ |
| Pad codes | A 3, B 2, X 1, Y 0, LB 6, RB 7, D-pad 0xc..0xf, Start 0xa (-> action 9 pause), View 0xb (-> 10 / 71 / 89), L3 8, R3 9 | ✅ |
| TU set 17 (K8) | 6 extra bindings (141 <- 32, 142 <- 3, 143 <- 2, 145 <- 33, 146 <- 2, 147 <- 3), tested by chart conditions 150-153; `tools/input_map_tu_fix.py` | ✅ |
| FilteredInput | PC `[0xfadfb0]` (TU 0x829ca64c): +0xb0 -> +0x18 stick magnitude, +0xc stick angle, +0x100 mode | ✅ static (17w) |
| Camera look input | 0x5ed4a0 (object at cam+0x1490): device table `[0xa02b68+pad*4]`, analog getter 0x480e50 = `[dev+0x14]+a*0x30`, digital flags `[[dev+0x18]]+a*0x30`; right stick actions 2 / 3 -> rates +0x1490 / +0x1498; mouse actions 0x10 / 0x11 (pad 0) accumulated over a 1/30 s window x 0.25 -> per-frame delta cam+0x14b0 / +0x14b4; move actions 0 / 1; invert bytes `[0xc59264]`+0x21c / +0x21d 🔶 | ✅ static (18f) |

**PadHook chain** ✅ live: the import slot is rewritten to KERNEL32 ~0.44 s after start, so every plugin hooks the pointer late
and the order is timing-dependent. TruMenu 0.21.2 runs queued items in PadHook only when the return address is in tru.exe;
TruShadowPower 0.19 uses TruMenu's export `TruMenuPadBlock(pad)` (low word withheld buttons, bits 16..18 menu / ring / quick
bar). Quick bar: View + Start within 250 ms. In front-end menus PadHook may not be called (TruMenu falls back to Present
and cannot block buttons: X reaches the game in the mission menu, live 07.11.) ⬜.
Sources: `Befund-Padkette-StartView-0711.md`, `Befund-TruShadowPower-017-0611.md`, [TruMenu README](../src/asi/TruMenu/README.md).

---

## 22. Camera

| Item | PC | St |
|---|---|---|
| Camera manager | static 0xe804f0, vtable 0x855ae4; current camera `[0xe804f0+0x44]`; gameplay camera +0xb80; transition camera +0x120; is-current 0x5e7fb0; `CAMERA_SetMode` 0x5f39f0; restore / reset 0x5edf50; FOV camera +0xb0. Xbox -> PC offsets +0xb50 -> +0xb80, +0x640 -> +0x670, +0x780 -> +0x7b0, flags +0x7c -> +0x80, mode +0x54 -> +0x58 | ✅ |
| Flag bit 2 | helpers vtable 0x8c..0xac (0x5eb1a0..0x5eb220; 0xa4 sets, 0xa8 clears, 0xac tests); **reader 0x5e5e8e in 0x5e5bc0** (= TU 0x822a9a7c, getter 0x5e7770): bit set -> second curve set +0x9c / +0xe8 of the camera tuning instead of +0x4 / +0x50 (via 0x5f20a0); reset at 0x5edf50 / store 0x5f3c48 | ✅ static / ⬜ visible effect |
| Who sets it | TU: shadow-power start, never cleared. PC retail: strike look 0x715020 / 0x718ea0 sets and clears | ✅ |
| TU camera manager (TruXenia) | TU 0x82efc780 (0x822a9a6c..0x822a9a7c, = PC 0xe804f0; slot 0xac flag test); mode +0x54, flags +0x7c (Xbox = PC +0x58 / +0x80). Current camera, position, FOV on the TU ⬜ (next: TU twins of the getters 0x5e78a0 / 0x5e78d0) | ✅ / ⬜ |
| Shake | `camerashakes.drm` (20 DTPs of 992 B); pool 8 x 0x90 at 0xe80020 (+0x10 intensity); start 0x5ee7f0; intensity 0x5eb460 (callers 0x5eea55, 0x5eb56d) | ✅ |
| Gameplay camera | `LaraCameraRewrite` = manager+0x3370 (0xe83860), ctor 0x6029d0, vtable 0x85600c (32 slots); manager ctor 0x5f3a70 stores it at +0xb80 / +0x30 / +0x44; update vslot +0x4 0x602690 -> 0x6022f0, 0x600710 (look step 0x5ffb00), 0x6009c0; SetSettings vslot +0x28 0x5ff910 (id cam+0x1d0); settings `S = [0xc36f28+id*4]+0x10` (lookup 0x54df80), fallback `[[0xe7ee50]+0x144]` = generalbank DTP 20 (the only camera-settings data in all 1059 PC DRMs); S+0x54 = FOV in degrees. PC GlobalInfo +0x148 = DTP 21, +0x14c = DTP 22 are not camera settings (the TU inserted 21237 / 21238 at +0x14c / +0x150) | ✅ static (18f) |
| Auto-recenter | **time-based**: cam+0x1e4 = time since the last look input (set 0 at 0x5ffe80 in the look step when \|yaw\| or \|pitch\| >= 1e-6, else +dt, or +S+0xbc x dt while Lara moves after the delay; cap 1000); weight 0x5ffa90 = clamp((t - S+0xb4) / S+0xb8, 0, 1), callers 0x5ffc90 (look step) and 0x6009d0 (look-at blend); scales the follow rotation 0x608b60 on +0x8f8 / +0xda0 (fmul 0x5ffdb5 / 0x5ffdd4) and the scripted hint track (short cam+0x12d0 >= 0, test 0x5fa500). DTP 20: delay **5.0 s**, ramp 2.0 s, moving rate 1.0 (TU doppelganger default DTP 21237: 0.25 s / 5.0 s). The mouse only gives input while it moves, so every pause restarts the clock. Instant recenter (t = S+0xb4 + S+0xb8): vslot +0x6c 0x602290 <- manager vslot +0xb8 0x5f2c60 (push camera data; game callers 0x6a376f, 0x6b601b, 0x72c49e = player state 1401 enter, 0x73f8eb - which moves ⬜), 0x5ff7f0 at 0x5ff843 on camera start. Xbox: TU weight vslot +0x84 0x822c20b8 (called 0x822c2a3c), TU look 0x822c2898; retail 0x822c55c0 (weight inlined 0x822c5764), look-at blend 0x822c65b0, slot 0x6c 0x822c4df8. Switch point for a player option: the call at 0x5ffc90 (keep the hint track) 🔶 not built | ✅ static / ⬜ live (18f) |
| Centre-camera button | manager update 0x5f3c70 tests action 23 at 0x5f3d88 (`[[[0xa02b68]+0x18]]+0x450` bit 0x10; action 23 = source 29 = pad code 8 = **L3** in PC DTP 47 / TU DTP 48; keyboard Q from the patch notes 🔶) -> gameplay vslot +0x54 0x5fea20 -> centre curves S+0xd8 = 7 / S+0xdc = 9 (tables GI+0x170 / +0x174) -> 0x609f10 on +0x1248 / +0x1278; turn 0x609d40 is not weighted, so it works with any auto-recenter switch | ✅ static (18f) |
| Reload crash (K12) | Lara camera 0x5ff7f0 reads focus `cam+0x1cc` (camera 0xe83860) without a null test (0x5ff851) | ✅ |

FOV camera +0xb0 = vertical radians (section 16), rewritten every frame by about 25 camera sites (e.g. cinematic keys
0x5e338b / 0x5e348d) - a player FOV option must scale, not set it.
Plugins: TruShadowPower 0.20 `[Look] CameraFlag=1` (TU default), TruMenu `cam.shakescale` / `cam.rumble`, TruQoL 0.1
`[Camera] Fov` (factor at 0x5cb0a8, gameplay camera only unless `FovCutscenes`) and `ShakeScale` (the same two shake
callers 0x5eea55 / 0x5eb56d as TruMenu; below 1 TruMenu refuses its slider); 0.1.1 reads them live (game thread, at most
once a second after a change of TruQoL.ini; the shake sites are owned only while ShakeScale < 1 and given back at 1.0). Sources:
`Befund-P5-Kleinkram-0711.md`, `Befund-Arachnophobie-Stufe1-Kamera-0611.md`, `Befund-Absturz-Neuladen-0711.md`.

---

## 23. Debug features left in the exe

| Feature | Where | Works? |
|---|---|---|
| Developer menu data | .data 0x8aaa6c..0x8ab3f0, root page 0x8aaae8, 101 rows in 15 pages (rows 0x18 B) | data only; TruMenu 0.3 draws it ✅ |
| Rows that act | reload unit 0x5dfba0; keep-info flag; fog far / near 0x8aaa60 / 0x8aaa64 (callback 0x5d36a0), fog RGB 0xe7eda0.., restore 0x5d3760; frame_rate_lock 0xe7f1a8; time_mult 0xe7f1a4; show_spline_info 0xe7f09c & 0x400000; perfect_game_now 0x5d3510 (irreversible progress bit) | ✅ |
| Chapter jumps `dev.chapter_*`, debug text, channel logs | stub 0x6457a0 | compiled out ✅ |
| NavPower debug draw | section 15 | ✅ live via TruMenu |
| Enemy health text | byte 0xe91ffc (cheat 11), font path 0x6224e0 | ✅ |
| Cheats | one-hit kill 0xe91ffd; cheatMode 0xe7f144; "no texture" flags without readers | ✅ |
| debugFlags 0xe7f098 | most masks without readers | ⬜ |
| FMOD profiler | port 9264 when init flag 0x20 is set | ✅ (not a dev channel) |
| Legend cheat poll | 0x5d74d0 (retail 0x82295458; xmap's partner "CINVIEW_Process" 0x8229d7b0 is wrong): matcher 0x5d33e0 -> dispatcher 0x5d3520 (TruMenu `cheat.code`); the TU (0x82291c40) removed the call - kept on PC on purpose | ✅ (17w) |
| Front-end state | byte 0xfae8da (0 LegalScreens, 1 IntroMovie, 2 PressStart, 3 MainMenu, 4 StartingNewGame, 5 PlayExtrasMovie, 6 StartingAttractMode, 7 InAttractMode, 8 PlayNewGameMovie; names 0x77cb20), setter 0x77bbc0 / getter 0x77bbe0 (code sets only 2 / 3 / 5 / 6 / 7); script natives = class `uigamedata` (binder 0x7af0c0): f12 0x7a0c30 SetFrontEndState, f13 0x7a0c40 GetFrontEndState (result via `[esp+0x10]`), f21 0x7a0cf0 PlayMovie -> 0x77bc60 -> video player 0x4a12b0(name, 0), f22 0x7a0d00 -> 0x4a0f10 StopMovie (stop byte 0xa039b8 = 1), f23 0x7a0d10 -> 0x4a0aa0 BinkPause(1), f24 0x7a0d20 -> 0x4a0ac0 BinkPause(0); movie names live in script data. State-1 case 0x5dae86 of the front-end switch 0x5dae20 (0x5dae7f, table 0x5db0cc) only logs and sets state 2; state 0 is not in the switch. **Intro skip:** the native is synchronous (no "finished" event) - TruQoL 0.1.2 `[Startup] SkipIntro` patches the rel32 of `call 0x4a12b0` at 0x77bc7b (main state at the intro ⬜ live). **No cinema bars exist** (no code, string or symbol; cutscene shots PC / Xbox are full frame); FMVs get the suffix `_nw` at aspect <= 4:3 (0x4a0c70, `[0x845674]`); IsWideScreen 0x5bfea0, 2D scale 9/16 vs 3/4 0x5c2630; "Cutscenes Vert-" at 21:9 = cinematic FOV (TruQoL `FovCutscenes`) | ✅ static (18b, 18c, 18f) / ⬜ live at 21:9 |
| Video player (Bink) | 0x4a12b0(name, loop): entry writes 0xa039b8 = 0, 0xa039dc = loop, 0xa039dd = 0; open 0x4a0c70 (4:3 variant name, then the plain name, both via 0x4a0b00; failure `xor eax, eax` at 0x4a0d07) -> **cannot open: return 0 at 0x4a12df**; else its own blocking frame loop 0x4a13c0 .. 0x4a14fb (frame time 0x5da230, BinkDoFrame 0x83e408 / BinkNextFrame 0x83e40c / BinkWait 0x83e3fc) until 0x4a0ae0 (last frame: handle 0xa039bc +0xc == +0x8, not looping), the stop byte, a skip press (ebp = 1 at 0x4a14cf) or 0x47afd0 fails; then BinkClose 0x83e404, handle 0xa039bc = 0. These globals are used only inside 0x4a0a00 .. 0x4a15ff. PlayMovie 0x77bc60 = log stub 0x6457a0, 0x5f6420 (`mov eax, 1`), the player, result dropped | ✅ static (18c) |
| Code-played movies | attract 0x5d5520 (list 0x8abef4 = "intro" 0x853aa4; from state 6 at 0x5db09c and main-state dispatcher 0x5e00f6; afterwards state 2), menu loop 0x5daf3e (states 2 / 3, `[0x8abf20]` = "medsea_loop", loop 1, until state 4), state 8 0x5db008 ("explode" 0x855290), movie queue 0xe7ece0 (0x5d6b39 in 0x5d6b10, 0x5dab0f in 0x5daab0; written at 0x5d6a89 / 0x5d6ab6 before state 5). `Movies\`: intro, medsea_loop, credits, credits_DLC1, explode, prevontr (.bik) - no logo / legal movie (the legal screens are script-drawn) | ✅ static (18c) |

Our debug plugins: TruMenu (menu, labels, debug views), TruTrace 0.3 (log-only hooks: chart transitions 0x787890, level
0x5df8c0 / 0x5d30d0 / 0x5d40c0, portal 0x5d2aa0, save, INSTANCE_Post, sound emitter 0x5935d0, slot play 0x593d50),
TruLink (TCP read / write channel into the game), TruDataGuard (logs bad section ids at known lookup points instead of
crashing). Sources: `Befund-TruMenu-Debug-0511.md`, `Befund-Debug-Ansicht-0511.md`, `Befund-Entwicklerkanal.md`.

---

## 24. Accessibility hooks (static research)

| Topic | Hook point | St |
|---|---|---|
| Fog / underwater | per frame 0x5c7ca0 -> fog getter 0x5c1f50 -> `CAMERA_IsCameraPositionBelowWater` 0x5ea200; environment block `[[unit+8]+0x70]` (underwater colour +0x1c.., distances +0x44 / +0x48 / +0x4c, LUT ids +0x84 / +0x88, ambience +0x68 / +0x6c) | ✅ static |
| Hide spiders (arachnophobia) | the hide bit 0x800 removes the instance from targeting (0x6f4070 / 0x715b90), so skip drawing instead: InstanceDrawable slot 7 (word 0x853ad8 -> 0x5bba90) | ✅ static, stage 1 built |
| Mip bias (trypophobia) | material sampler -> D3DSAMP_MIPMAPLODBIAS (0x505a90 -> 0x5076e0 -> 0x527840); texture id -> object ⬜ | 🔶 |

Sources: `Befund-Thalassophobie-0611.md`, `Befund-Arachnophobie-0611.md`, `Befund-Trypophobie-0711.md`.

---

## 25. Biggest open questions (engine side)

| # | Question | Section |
|---|---|---|
| 1 | ~~Which register World really occupies~~ - answered statically 07.11.: c4..c7 = World, c0..c3 = WVP at every draw (0x526b90, section 16); only a live check of D3D9 `def` scoping is left | 16 |
| 2 | ~~Meaning of navmesh area bits 26 / 27~~ - answered 08.11.: 26 = custom area, 27 = obstacle-blocked (runtime). Left: bit 28, which game objects create obstacles, floating / water areas in end (needs per-TerrainGroup offsets in `unit_frames`), the render passes | 15, 16 |
| 3 | Live result of TruShadowCombat 0.6.1-0.6.6 (chunkdoll, melee, 34 / 38, T5, Vaulted chain / clock); live so far: K14, 33, the companion lookup | 13 |
| 4 | brain+0xc bit 0, other brain+8 bits; seconds per enemy tick (TU +0x2c7c / +0x5080 answered statically 08.11., 13.1) | 13 |
| 5 | ~~Address conflicts RegenerateDeath Enter / Regenerate slot 10~~ - resolved 08.11. from the vtables: Enter 0x67ed20 (0x67edf8 is a site inside it), Regenerate slot 10 0x682680 (0x684b80 was a wrong mapping) | 13.2 |
| 6 | Which player moves send notifications 25 / 26 / 29 / 35-37 | 7.3 |
| 7 | Game block ranges beyond the known fields, inventory / unlocks location, sticky owner kind 1 id | 6 |
| 8 | SweepAndPrune peaks in DLC 2 and whether 0.10 holds them (0.10 not yet loaded in the game) | 14 |
| 13 | Is the TruMenu 0.21.8 sound group factor (cg + 0x38) audible; does the game write it itself | 18.3 |
| 9 | Units per metre (Lara's real height) | 4.3 |
| 10 | How front-end menus poll the pad | 21 |
| 11 | Uber events per node; generator +0x0c / +0x32 / +0x5e | 9, 10 |
| 12 | Sources writing `tru+0x7973c0`, `tru+0x7a0d00`, `tru+0x43e28b` (probably absolute VAs) | 7.2, 7.4, 8.2 |
| 13 | TU fixes not found in code: crash when the PDA opens during the transition to the main menu; heap-leak fix (17w: G2 native binders, PDA scripts and cdc heaps not compared yet) | 1 |
| 14 | Motion blur data: who writes Xbox instance +0x84 / +0x88 and post-effect object [5]+4; which previous transform the 4 MB VS variants use | 1, 16 |
| 15 | Flashlight shadow: light-resource flags of Lara's flashlight PC vs Xbox (data flag or missing VSM / 7-light path?) | 16 |

---

## 26. How to keep this file current

1. **Same commit rule.** Every commit or finding that adds or corrects engine knowledge (an address, a layout, a state flow,
   a TU difference, a proof) updates the matching entry here **in the same commit**, like the CHANGELOG row. If no entry
   fits, add one to the topic section - never a dated section.
2. **One row per fact, short.** Keep the form: what / PC address (absolute VA) / TU counterpart / our plugin or tool / source /
   status. Details, disassembly and logs go into the finding or the tool docstring; this file only names them.
3. **Status changes are edits, not additions.** When something is proven live, change 🔶 / ⬜ to ✅ in place (and say "live").
   When a fact is refuted, replace it and keep one line "(earlier claim X refuted, source)".
4. **Agent reports bring an "ENGINE.md addition" block**: section number, the rows to add or change, and the source file.
   The coordinator merges it in with the agent's commit.
5. **End-of-session cross-check.** Compare the new `Befund-*.md` files and `git log` of the session with this file; every new
   engine fact must have its row, every closed question must lose its ⬜ in section 25. `tools/engine_md_check.py
   <finding files>` lists the PC (`tru+0x...`, 0x5xxxxx-0x8xxxxx) and TU (0x82xxxxxx) addresses of those files that this
   file does not mention - a reading aid: most hits are sites inside known functions and stay out. Same rule for agents:
   [AGENT_GUIDE.md](AGENT_GUIDE.md) ground rule 7.
6. **Addresses**: always absolute VAs (image base 0x400000); convert `tru+X` when copying from a source. Xbox addresses are TU
   unless marked retail.
7. **No duplication.** Pipeline facts belong in [ARCHITECTURE.md](ARCHITECTURE.md) / [PIPELINE.md](PIPELINE.md), plugin INI
   detail in the plugin README; link them from here instead of copying.
