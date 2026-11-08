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
| Chunkdoll limit | 8 | 4 | not ported (deliberate) |
| Sound-slot 5th argument | TU 0x8226de00 | retail | ⬜ not ported |
| Main-game bug fixes in the TU | none proven (528 real changes reviewed in part) | - | - |

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
| **Fault class "learned type-7 table"** (08.11.): every DTP without a same-size base twin takes the generic `convert` route (generic_type0 with the learned type-7 table: class per word from label key + Xbox value shape). Seven unrelated record families came out with the same fault - the right bytes in the wrong order for the field width (u16 pair <-> u32 <-> raw): chunkdoll piece records (13.6), DTP 22497 player tuning (targeter / K9 pair table, 20.1), type-0x3d thrall extension data (13.4), melee records reached only via the +0x1c8 link (13.5), pool generator intro data (10; also our DLC 1 route), costume model u16 arrays + list counts (count remapped like a DTP id, 19), the SoundPlex type-12 DSP kind u16 (18.1), fade-record DTPs of the cine cards (above), uber play-anim words (action kind 2 argument / TRANS +0x28, section 9: 18 words in 7 DLC 2 objects, crash 08.11.; the learned table decides differently per run - the 0811 pipeline copy still has 8 in 4 files). The pipeline fixes them after conversion with typed rules: steps `chunkrec`, `exttuning`, `thrallext`, `meleelink`, `genintro`, `costumedtp`, `dspkind` in `tools/dlc_struct_fixes.py` (after `objid`, before `seqrepeat`), only where the PC word is another byte order of the Xbox word; twins / statechart run before, the `converter_faults_fix` families after and leave these words alone (check: 0 on the 0711 copies) | ✅ | P2 / N8 report 08.11., `tools/dlc_struct_fixes.py` docstring |
| The **installed** `doppelganger_casual.drm` predates the twins step: 392 words in 34 SoundPlex DTPs (incl. the moan trees) are still in the converter's byte order; a fresh pipeline run fixes them (test tree in progress) | ✅ data | section 18.1, `work/moan_0711` |
| Cutscene command lists: records `{u16 type, u16 frame}{u32 uid}{u16, u8, u8}{u16 msg, u16 par}[extra]`, length = 12 + 4 * (type >> 12) (format A) or 8 + ... (format B, with an initial DTP id); terminator `ffff0000`. Converted as plain u32 words, type / frame swap and the cinematic never gets `Cine_Start` | ✅ | (from FINDINGS.md) |
| Physics records of custom-range grapple rings (tag 0x404): the enable byte at +4 must stay raw | ✅ | (from FINDINGS.md) |
| **Fade-record DTP** (card / flash / key-glow objects: `co_white_flash`, `co_dlc_black_card` 22651, `co_dlc_white_card` 26832, keys, gems, g_pda): +0x04 / +0x08 and +0x44 / +0x48 = {u16 count, u16 0} / pointer to the records at +0x90, 12 B each {u16 from, u16 to}{u16 frames, u16 word2}{u8 r, g, b, a}; PC word classes s16, s16, raw (42 of 42 base records in 14 DTPs). The learned type-7 table broke them in the installed DLC 2 cards: black card 17 / white card 3 words in the wrong byte order (pod fade-in 6400 instead of 25 frames, finale from / to reversed, ghoul record 5 colour `ffff00ff`); B270 is right. Fix test tree `work/endcine_0811` (= B270 md5); pipeline step `fadecard` ⬜ | ✅ | 17h-B 08.11. (`work/endcine_0811/fade_layout_scan.py`, `fade_fix.py`) |
| Fault class "learned table" also hits **type-0 Level sections without a same-size base twin**: `dlc_yggdrasil_end` Level (0x1a6710 B vs base 0x1a6810) had 3476 words in the wrong byte order (float records under Level+0xe0 / +0xe4 and across the section, {u16, u8, u8} heads); at the same offset 3472 Xbox words equal the base pair `l7_yggdrasil_end`, whose byte order proves B270 right; the Levels of hall02 / ceremony_room / treasure_room_cine / level2_start equal B270. Reader of Level+0xe0 / +0xe4 ⬜ | ✅ data / 🔶 route | 17j-b 08.11. (`work/endb270_0811/sec0_judge.py`, `ygg_fix.py`) |
| **Base-id DTPs in DLC copies**: DTP 18577 (Xbox 10994) = environment colour LUT (256-entry ramps / curves, referenced from Level+0x70 -> DTP 20984 +0x2d0); the DLC Xbox payload 0..0x31c0 is byte-identical to the base, so the PC copy must be the PC base copy (installed end / hall02: 843 words s32-swapped; B270 82 wrong). DLC 2 copies of 18577 / 18579 / 18581 / 19289-19291 carry a 36-byte trailer {00010000, ptr, ptr, 9c6f3e84, u32 payload size, 0, ptr -> 0, ptr -> trailer, cafebabe}, absent from all 1057 PC base DRMs and with no `cafebabe` constant in tru.exe -> unread on PC | ✅ / 🔶 trailer unread | `vs_base_pc.py`, `trailer_scan.py` |
| Unit DTP intro data | intro +0x7c = u32 (s32 on every DLC intro; base: remapped id in 451 / 525 - B270 left it raw, wrong); watervolume (object 7, 0xc0 B) +0x38 / +0x50 = u16 pairs; triggerplane (object 126, 0x50 B) +0x30 / +0x44 = raw bytes; unit DTP root +0xa4 block +0x90 / +0x94 raw; name strings (`MARKUP\|markup_ledge251`, `SIGNALS\|Yggdrasil_END`) raw (installed end had them swapped) | ✅ data | `unit_dtp.py classes`, `unit_root_block.py` |
| FX particle record (anchor `bf800000` x3, `c04a468e` x2): word +0x18 never s32 (raw 557 / s16 45); +0x38 with an id at +0x34 always raw - 18091 base records; DTP 22819 (`dlc2_checkpoint` object data, in 13 DRMs) had 3 words wrong | ✅ data | `pattern_twins.py` |
| Streamgroup mesh-list DTP {u32 n, n x {u32 mesh id (idref 12), u32 0, u32 1, u32 k}}: all u32 (80 base DTPs); `dlc2_machine_room_machine_room_all` DTP 25512 had 16 words wrong | ✅ data | `sg_mesh_list.py` |
| Symbol evidence: base script 3581 (Xbox 1015, 3 units) prototype / argument names 515 -> 517, 521 -> 523, 522 -> 524 on PC; the B138 calibration maps 333 / 340 / 341; B270 uses 517 in DLC class 24693. B270 also inserts vtable slot 31 in the UI level classes (we keep the Xbox layout, Finding 46) | 🔶 | `base_words.py`, `script_labels.py` |
| **B270 vs installed, all 295 DLC DRMs** (17l, 08.11.): class a (ours wrong, B270 right) 11 349 words + 5 re-spaced model DTPs, b (B270 wrong) 79, c (intended: encoder waves, own shader libs, material translation, B270 vtable slot 31, scriptclash relink, NOPs, record relayout, pack choice, jump-target intros, K8 / K12) 4.65 M, d (unclear) 4 757. Every installed file passes the 12 existing check steps unchanged; B270 fails exttuning (10 words), objrec (8), meleelink (8), genintro (4), seqrepeat (2), intro +0x7c (6) and shifts script init blocks (15). Tonight's test trees fix 4 623 of the a-words; test tree `work/b270cmp_0811/tree` 5 534 more | ✅ data | `work/b270cmp_0811/judge.py`, `typed.py`, `final.py` |
| **Second model copy DTP 24392** (doppelganger_casual + 4 DLC 2 thrall DRMs; Xbox = model 20134 but 1 word; idref'd at +0x0 from DTPs 26764 / 26765 (doppelganger) and 24500 (thralls), no external reloc into it, no object +8): the 75-record list at +0x380 must be re-spaced 36 -> 40 B like 20134 (`model_reclist_fix fix ... 24392 --words` handles it: +304 B -> 221 128 B = B270, reloc check ok; the `reclist` step only walks object +8 models); after re-spacing the list equals our 20134, but 5960 body words after the list are in another byte order than our 20134 (B270 = our 20134 in 5952, = our 24392 in 8) - needs a twin step too; all 5 copies in one step (DTP id resolution across files ⬜) | ✅ data / 🔶 visible effect | `work/merge17m_0811/m24392.py`, `tools/model_reclist_fix.py` |
| `[Level+0x90]` section (type 0) +0x1c idref -> DTP of one family ({u32 n, ptr, ptr, float records}, pointer-delimited blocks): all words u32-swapped - 47 same-size base pairs / 301 268 words, 0 raw (direct twins end 20983 = l7 18548, hall02 23098 = l7 19283). Installed `dlc2_ceremony_room` DTP 25696 has 107 raw words (BE floats left; as BE f32 all 107 plausible, as installed LE f32 only 23; B270 right), machine_room 25390 6 (17l class a). Reader ⬜ | ✅ data | 17p 08.11. (`work/q17p_0811/q3_words.txt`, `q3_level1c_base.txt`) |
| Environment-LUT base copies also in `dlc_yggdrasil_hall01` DTP 19397 (ramp bytes 00 01 02 03 ..., installed s32-swapped, 802 words + 42 also wrong in B270) and `dlc2_uo_goo_cannonball` DTP 4190 (846); rule: the PC base copy | ✅ data | `judge.py` basecopy |
| DLC 2 thrall object data (24424 / 24534 / 24575 / 24888 family): the aligned base twin (`viking_thrall.drm` / `yeti_thrall.drm` object data, difflib, >= 85 % of the words in equal blocks) gives the PC byte order of 3177 differing words (3177 a / 0 b); installed has the converter's s32 default (byte flags XX000000, u16 pairs) | ✅ data | `align_twin.py` |
| dtp_audit structure keys with >= 100 informative base samples all of one byte order: 1184 differing words, B270 right in all (byte flags at +0 swapped as u32, u16 pairs / half floats in the doppelganger mesh DTPs 22493 / 25050, floats left raw in machine_room 25390) | ✅ data | `keystats.py --fp` |
| Particle record (0x17c) offsets +0x40 / +0x68 / +0x7c / +0x88 / +0x11c / +0x14c / +0x174 have no objrec rule (mixed base classes); without a base twin (machine column, goo drips, faulty treadmill blocks) about 800 words stay open - a reader-typed rule by emitter kind is needed | ⬜ | `objrec_map.py` |
| `co_dlc_knight_thrall` DTP 21046 (DLC 1): installed = B138 values (no byte order of the Xbox word: 0x28 -> 0x29, colours doubled, 0.3 / 0.4 -> 0), B270 = Xbox in objrec rule order (21 words) - an upstream re-authoring, owner decision | 🔶 | `objrec_map.py`, `final.py` |
| `dlc2_machine_room` unit DTP 25392 +41 760 B (2 intros more) = `jump_target_place.py` (test 50l), not a converter fault | ✅ | `growth.py` |
| Cine command type 0x2001 msg 34 (0x22): par = fade-record index of the target object; fade 0x1000 = invisible, 0 = opaque (ghoul f0 rec 5 / f833 rec 4, pod f0 rec 0, podon, finale, crush); meaning of word2 ⬜ | 🔶 data | `work/endcine_0811/cine_drm_cmp.py` |
| Each translated material gets its own shader lib id (2756-2774, 2775-2781, 2782; 975 / 976 are VS / PS donors copied into streamgroups), because of the first-copy-wins rule below | ✅ | (from FINDINGS.md), [LINEAGE.md](LINEAGE.md) |
| Language variants: `ArchiveFileSystem::FindEntry` 0x4726e0 takes the first record with `(spec & mask) == mask`; English loads `<name>_001` (spec 0xffffffe1) before the base name | ✅ | section 18.5 |

---

## 3. Main loop and global state

| Item | PC | Notes | St |
|---|---|---|---|
| Main state | dword 0xe7ed60, dispatcher 0x5e0090 (jump table 0x5e015c, index state-1) | 1 = in level (GAMELOOP_Process 0x5e0050), 2 = level start / load (0x5de7e0), 9 = outfit / weapon selection, 10 = front end. Level load sets 2 at 0x5de9ca, 1 at 0x5de9f0 | ✅ |
| GameTracker | 0xe7f088 (TU 0x82efb458) | +0xc = 0xe7f094 player instance; +0x2c = 0xe7f0b4 progress bits; +0x38 start unit name; +0xb9 = 0xe7f141 level change pending; +0xbb = 6 / 10 skips unit changes; +0xbc = 0xe7f144 cheatMode; +0xc0 = 0xe7f148 main stream unit id; +0x100 = 0xe7f188 scaled frame dt; +0x118 = 0xe7f1a0 world time scale; +0x138 = 0xe7f1c0 (cinematic test 0x453f00); +0x148 = 0xe7f1d0 timeDilation; +0x16a requireImmediateAdjacentUnitLoad; streamFlags 0xe7f0b8 (0x1000 pause, 0x200000 keep info between loads) | ✅ |
| Player tracker | `[0xfadb58]`, ctor 0x71c2d0 (memset 0x1310, only call 0x722445), published 0x72247b, cleared 0x722304 | +0x500 weapon manager, +0x504 player instance, +0x628 health, +0xa64 jump-target markup box, +0xc94 attached markup box, +0x1244 doppelganger flag, +0x1288 engaged-enemy counter. TU tracker is 0x1320 bytes (memset 0x82413878, global 0x829892b0) | ✅ (+0xa64 / +0xc94 live ⬜) |
| Frame time | unscaled 0xe7f190; scaled 0xe7f188 / 0xe7f194; game clock 0xe7f15c; 64-bit tick clock `[0xecfaec]` / 0xecfaf0 (enemy timers) | ticks per second ⬜ (30 assumed 🔶) | ✅ |
| Time scale | ramps player 0x8abe94, world 0x8abeb4; current player 0xe7f1d4, world 0xe7f1a0; SetWorldTimeScale 0x776030, SetPlayerTimeScale 0x776090 (`gamebase` natives 23 / 24) | used by shadow-power slow motion | ✅ |
| Fatal error | 0x596cb0 (message box, process stays alive) | e.g. "ChunkDoll: failed to create geom" | ✅ |
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
| Unit list | `tr8/pc-w/unitlist.txt`, 119 units (l1..l7 = 23 / 16 / 9 / 11 / 6 / 6 / 13, DLC 1 = 12, DLC 2 = 11, other DLC starts 4). Chapter titles are not in it (they come from script 72, section 8.2); TruMenu `kUnits` groups them by chapter. `dlc_level1_left` / `dlc_level1_right` are listed (also on the Xbox) but have no DRM; the installed mods tree is flat (`mods\<unit>.drm`) and also lacks `dlc_level3_start` .. `dlc_level6_start` (in bigfile.000? ⬜); TruMenu 0.21.9 `UnitDrmScan` greys out DLC 1 / 2 units without a DRM. Checkpoint intro +0x52 counts up along the path in hall02 / end (24465 ...); `dlc2_machine_room` has 4465 ... (converter? 🔶) | ✅ |
| Units without a DRM | `dlc_level3_start` .. `dlc_level6_start` and `dlc_level1_left` / `_right` exist in no archive (PC bigfile / patch, Xbox layer1 / layer2 / TU, packs 10 / 11 / 1 / 2 / 20; positive control: level1 / level2_start found); named only in the unit lists, `objlist.dat`, generalbank script 104 (DLC mission screen: f7 / f10 check `dlc_levelN_start.drm` with `dlcsystem` f1, f8 / f9 start the slot via `uigamedata` f27) and script 6 -> 4 unused retail DLC slots (never built 🔶) | ✅ (`work/q17p_0811/q4_names.txt`, `dis_script104.txt`) |

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

### 4.3 Coordinates and scale

| Fact | St |
|---|---|
| live position = data - Level+0x80 + P; P = 0 for Lara's unit, the portal difference for a neighbour (memory dump) | ✅ |
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
| Pause menu (script 7 `uipause`) | TU sends `HODRefresh("DLC",1)` and `PauseMsgCh` paused / unpaused; ported by `tools/script7_pause_port.py` (members 3208 / 3228), not in the pipeline | ✅ built |
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
`Befund-Erweitertes-Ende.md`, `Befund-Direktstart.md`, `Befund-Versteckte-Inhalte.md`.

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
| Play-anim data rule | PC word = u16 pair of the Xbox word (base game 575 / 575 words in 98 uber objects); the DLC converter wrote 18 words as u32 in 7 DLC 2 files (goo_cannonball 964 DTP 25328 +0x6d4 {mode 0, anim 1} -> {1, 0} = the crash in `dlc2_ceremony_room` 08.11. 00:27, AV 0x444c62; natlapod, machine_column, extending_bridge (+ _long / _special), corkscrew_200cm); B270 right everywhere; fix tree `work/crash_0811/tree` (`uber_anim_fix.py`), pipeline step `uberanim` ⬜ | ✅ data |
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

Base script 3484 (trigger volume) +4 = sticky key 1724. Trigger kind is only known from the object name ⬜.
Plugin: TruMenu 0.14 `dbg.triggers` / `dbg.portals` / `dbg.checkpoints` draw exactly this test. Source: `Befund-TruMenu-Trigger-0611.md`.

---

## 12. Lara's state chart (player moves)

| Item | PC | Xbox TU | St |
|---|---|---|---|
| Builder (registers condition / activity / state ids from 3 static tables) | 0x7872f0; table push operands 0x787343 / 0x78735a / 0x78736a; sizes 307 / 332 / 199 | 0x82489500 (unchanged; only the tables grew) | ✅ |
| Chart transition | 0x787890 (TruTrace hook); chart machine 0x7873c0 | | ✅ |
| Condition default handler | 0x782140 | 0x82484db0 | ✅ |
| Markup condition test | 0x782810, jump table 0x782a54 (ids 601-628), type getter 0x5be340 | `SCCondTest_MarkupType` 0x82486dd8 | ✅ |
| Condition record | {u16 key, u16 id, u16 value, u8 flags, u8}; 607 / 608 are the **value** (markup type 23 / 22), the record id (610-613) picks the handler | | ✅ |
| Lara registration table | PC 0x768b60 (TU 0x82473b50 adds states 243 / 245 / 1018, conditions 1048 / 2401, activities 1009 / 1039) | | ✅ |
| Activity 1005 | attack record `[[0xfadb58]+0x504]+0xc4` (handler 0x767e90, table 0x8b2280) | | ✅ |
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
field. TruShadowCombat 0.6.6 `[Death] TranslateT5` (jmp at 0x63ad82, 7 bytes): built, live ⬜.

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
| Physics system `[0xa037f4]` (0x2120 B) | 405 bodies, 1200 geoms, 300 joints (same on all exes); lock +0x20f8: `PhysicsSystem::Step` 0x4f0ab0 sets 3, ORs 8; AllocBody 0x4e9590 returns 0 while locked; FreeBody 0x4e9610 silently refuses while locked | | ✅ |
| **Crash root cause** | step -> pair callback 0x492980 -> msg 0x26 to Lara -> CombatManager 0x719050 sends 0x11c then **0x91** -> enemy handler case 0x91 -> impulse handler **0x624c60**: LP <= 0 + chunk record -> chunkdoll **inside the physics step** -> fatal | 0x82305ba0: no immediate chunkdoll; hit vector 0x656430, then death switch kind 7; the Death state builds it later | ✅ live 07.11. (lock = 3, 13 / 405 bodies used) |
| Leak | 0x48ea80 clears inst+0x274 even when FreeBody refused | | 🔶 |

Plugin TruShadowCombat 0.6.1 `[Chunk] Translate` (6-byte jmp at 0x624caa): built. Data errors (model bytes in DTP 24559
/ 26190): `tools/chunkdoll_records.py`, `chunkdoll_record_fix.py` (pipeline step `chunkrec` since 08.11.). Limit 4 -> 8 deliberately not ported.
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
| Camera / scene | camera getters 0x5e7850 (transform), 0x5e7870 (inverse), 0x5e78a0 (position), 0x5e78d0 (FOV), matrix 0xe804a0; scene block 0xe496e0 (0x5caff0; row 1 negated), near 16.0, far 12000.0 (`[0x8aa764]`); projection `TRANS_RotTransPersVectorf` 0x49f630 | ✅ |
| Cheat "no texture" flags | 0xe7edac / 0xe7edb0 toggled, 0 readers | ✅ |
| Projected light binding | 0x50a5f0 / 0x5076e0: `X+0x418` sometimes holds a pointer to a render view instead of the texture -> AV 0x5076fa; the B138 exe's `light_tex_guard` restores it when it differs from the invariant of `FinalizeInitialization` | ✅ (from FINDINGS.md) |
| D3D device creation | 0x7c493d: a boot crash at 0x7c4984 (sources write tru+0x3c4984) is infrastructure (driver / VM), not data | ✅ (from FINDINGS.md) |

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
| Shader labels: EQUIV | proven 1:1 pairs count as O (Xbox VS 2456 = PC 1911 / 1737 / 1718 / 1689; proof `work/n6shaders_0711/vs_twin_cmp.txt`, `work/endcolumn_0711/vs_slot_cmp.txt`); `--no-equiv` = the old letters byte-identically | `tools/shader_labels.py selftest` (16) | ✅ |
| Refused patterns | sampler used as 2D and cube (2666 / 2673 / 2694 / 2706 / 2715), L-lane 2057, lint 2106 / 2387, record mismatch 2052 / 2118, light block "L None" 2195; upstream kill bug (vector kill with zero write mask dropped) worked around | `column_shader_translate.py` | ✅ |
| DXN normals | Xbox DXN -> PC DXT5 with x in R, y in A (`dxn` option) | | ✅ |
| VS equality proof (C1 Xbox VS kept as PC VS) | PC VS P is a 1:1 equivalent of DLC VS D when a base Xbox VS X with x2p(X) = P has the byte-identical entry in every slot P occupies: holds for 2456 / 1911 (23164); fails for 2371 / 1911, 2633 / 802, 2274 / 114, 2062 / 831, 2713 / 1595, 2462 / 1908 (30-60 PC slots differ) -> those materials stay PART | `work/n6shaders_0711/vs_twin_cmp.py` | ✅ |
| MaterialParams longer on PC | `tu_unlit apply` keeps a PC params block that is longer than the Xbox one (32 copies in n6); harmless per copy: the new PS reads no c100+j with j >= Xbox count | `verify_n6.py` | ✅ |
| ABS_CONST in lit translations | `fix_abs_consts` makes abs uniform per register (X6045) but leaves `-\|cN\|` forms; 41 lit libs carry them (22 installed: 2527-2584, 2810-2815); NVIDIA accepts, the AMD driver rejected the form on 20.10. | native D3D9 test | ⬜ AMD |

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
`tools/vo_lang_variants.py`. ✅ Source: `Befund-Tonspuren-Soeldner-0611.md`, [TruMercLang README](../src/asi/TruMercLang/README.md).

Crash guards in this area (B138 exe, from FINDINGS.md): `fmod_init_guard` - audio init 0x582200: a failed FMOD
`System::init` leaves three locals uninitialised -> AV 0x7b92fb; the guard zeroes them. `soundplex_guard` hooks 0x5920d5
and returns NULL for null-data nodes (not for types 2 and 8, which handle it themselves). The exact bytes are in
`tools/*_guard.py`.

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
| Shake | `camerashakes.drm` (20 DTPs of 992 B); pool 8 x 0x90 at 0xe80020 (+0x10 intensity); start 0x5ee7f0; intensity 0x5eb460 (callers 0x5eea55, 0x5eb56d) | ✅ |
| Reload crash (K12) | Lara camera 0x5ff7f0 reads focus `cam+0x1cc` (camera 0xe83860) without a null test (0x5ff851) | ✅ |

Plugins: TruShadowPower 0.20 `[Look] CameraFlag=1` (TU default), TruMenu `cam.shakescale` / `cam.rumble`. Sources:
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
