# Rebuilding the pipeline on Windows (branch `windows`)

Running log of what it takes to reproduce the stage 0-1 pipeline (docs/PIPELINE.md) on a Windows PC from the user's
own files. Goal: rebuild DLC 1 (*Beneath the Ashes*) step by step, compare every produced file with the B138 kit
manifest, and then use the same pipeline for DLC 2 (*Lara's Shadow*) and the costume packs.

## Environment

* Python 3.14 in a venv **outside** the repository (`..\bin\venv`), packages from `requirements.txt`
  (numpy, Pillow, capstone).
* All tools are run **from the repository root**: `..\bin\venv\Scripts\python.exe -u -I tools\<tool>.py`.
  The branch replaces the `/path/to/` placeholders in `tools/*.py` with relative paths:
  `/path/to/trudlcport/` -> `./`, `/path/to/trudlcport/pc/` -> `../data/pc/`, `/path/to/` -> `../data/`,
  and `'tru-port/pc/'` -> `'pc/'`, `'tru-port/'` -> `'trudlcport/'` (two names for the same checkout upstream).
  `work/` notes are unchanged.
* `../data/` holds directory junctions (no copies):

  | `../data/...` | points to |
  |---|---|
  | `pc` | the Steam game folder (read only) |
  | `trudlcport` | this checkout |
  | `TombRaiderUnderworld_Patched` | Xbox 360 game (`layer1.000/.001`, `layer2.000/.001`, `default.xex`) + title update (`TitleUpdate.000`, `default.xexp`) in one folder |
  | `Xenia-SteveRepack/Content/534307EC/00000002` | the Xbox DLC content folders (pack10/11 and the costume packs 1/2/20) |

  Never delete `../data` recursively - it would follow the junctions.
* `ref/yura-release` is a junction to Yura 1.7.2 (TheIndra55/Yura, release asset `Yura.zip`,
  sha256 `4e482042b9be526de02216145458816145dda10c8a09a56c45871f652458df07`). `tools/names.py` needs
  `ref/yura-release/FileLists/Tomb Raider Underworld (PC).txt` and `(Xenon).txt` to map name hashes to file names.
  Not mentioned in SETUP.md.
* `.gitignore` additions: `ref/`, `work/generic/`, our tool outputs (`work/dlc_screen*/`, `work/dlc_text/`,
  `work/menu_dlc/`) - they contain game data.
* The stages are driven by `Invoke-TruPipeline.ps1 -Step <name>` in the parent project (logs every tool's output);
  the commands below are what it runs.

## Stage order (as reconstructed)

| Step | Commands (from the repository root) | Output |
|---|---|---|
| Index | `tools/index_all.py work/idx_pc.json le ../data/pc/bigfile.000@7ff00000 ../data/pc/patch.000@7ff00000`<br>`tools/index_all.py work/idx_xbox_base.json be <layer1>@7ff00000 <layer2>@7ff00000 <TitleUpdate.000>@7ff00000`<br>`tools/index_all.py work/idx_dlc.json be <pack10>@7ff00000 <pack11>@7ff00000` | `work/idx_*.json` |
| Cache | `tools/generic_cache.py`, `tools/generic_cache.py patch` | `work/generic/pairs.pkl`, `pairs_patch.pkl` |
| Ids | `tools/generic_store.py`, `generic_ids.py`, `objlists_extract.py` (**new**), `objlist_merge.py` | `store.pkl`, `idmap.json`, `merged/` |
| Learn | `generic_learn.py save`, `generic_symbols.py seed`, `script_pairs.py`, `unit_ids.py` | `mask_table.pkl`, symbols (key 100) in `idmap.json`, `work/script/pairs_*.pkl`, `unit_idmaps.json` |
| Tables | `dlc_drms_build.py` (**new**), `dlc_generic.py` (provisional), `script_learn.py save`, `generic_type0.py save07`, `script_name_match.py`, `tex_idmap.py`, `dlc_generic.py` (final) | `dlc_drms.pkl`, `dlc_idmap.json`, `work/script/script_table.pkl`, refined `idmap.json` |
| Prep | `generic_type0.py save07`, `pc_vers_build.py` (**new**) | `type0_table.pkl`, `type7_table.pkl`, `pc_vers.json`, `pc_vers_content.json` |
| Convert | `tools/dlc_convert_all.py --media --write` | `work/generic/out/` |
| Names | `tools/dlc_names.py` (also takes the Xbox source names of `docs/data/*.kit_manifest.json` when the hash matches) | `work/generic/dlc_names.txt` (names of unnamed DLC records) |
| Media | `dlc_media_build.py work/rebuild/stage1/mods pack10` (**new**; music of pack10 + pack11), `locals.py build work/rebuild/stage1`, `padshock_convert.py build work/rebuild/stage1/mods`, `compare_b138.py work/rebuild/stage1/mods stage1` (**new**), `compare_sections.py work/rebuild/stage1/mods stage1` (**new**) | DLC 1 stage-1 tree in the B138 layout + per-file and per-section-type comparison |
| Audio | `dlc_audio_build.py work/rebuild/stage1/mods work/rebuild/stage2a/mods` (**new**: `wave_swap` for every DRM incl. sub folders + `mul_audio_batch`), `compare_b138.py work/rebuild/stage2a/mods stage2a`, `compare_sections.py work/rebuild/stage2a/mods stage2a` | DLC 1 tree with real audio (B43) |

Comparisons: `compare_b138.py` = per file (MD5) against the B138 kit manifest; `compare_sections.py` = per DRM section
type against the installed B138 `mods/` tree (data + normalised relocations; report `work/rebuild/sections_<label>.json`).
Every number quoted in this document comes from one of these tools or another script in `tools/`.

The order of Ids/Learn follows the inputs each tool opens; it is not documented upstream and may still change.

## Plan (remaining work for DLC 1, as of 2026-10-27)

| Step | What | Status | Compute time (estimate) |
|---|---|---|---|
| 0 | Index, Cache, Ids, Learn, Tables, Prep | done | - |
| 1a | Convert (DRMs, silent audio placeholders) | done | 52 min |
| 1b | Names (`dlc_names.py`, + kit manifest names) | done; pack10: 1 record unnamed | 3 min |
| 1c | Media (`dlc_media_build.py`, locals, padshock) + `compare_b138.py` + `compare_sections.py` | done | 30 s |
| 2a | Audio: `wave_swap.py` (Wave sections in place), `mul_audio_batch.py` (`.mul` streams) = B43 | done; wave sections 86.5 % = B138, `.mul` not yet MD5-equal | 2.5 min |
| 2a+ | Explain the remaining wave differences (spread over 61 of 63 files) and the `.mul` differences (B138 re-encoded 39 `.mul`; compare decoded audio, not MD5) | open | - |
| 2b | Data fixes B1-B47 (LINEAGE.md): crashes, raft/physics words, cutscene command lists, MaterialParams | scripts partly only in `work/ws/`; order to reconstruct | small; much work |
| 3 | Shaders B72-B89 (`work/ws/shader4/`) | open | largest block |
| 4 | Last layers to B90_gold_L4 (Giro 5-7), then CHANGELOG changes up to B138 | open | - |
| - | 40 `vm_mods_expected`/`vm_extra` files | check after 1c; else take from B138 | - |
| - | patched `tru.exe`, `movies/credits_DLC1.bik` | from the B138 kit (rebuild via Steamless + guards optional) | - |

Goal for DLC 1: as many files MD5-identical to B138 as possible and every remaining difference explained - the
basis for converting DLC 2 (*Lara's Shadow*) with the same pipeline.

## Findings / missing glue

1. **`work/idx_*.json` must exist before `generic_store.py`.** `generic_store.build()` reads
   `work/idx_pc.json` (PC section ids of every DRM, bigfile + patch.000); `tex_dlc_all.py`, `tex_tally.py`,
   `rend_extract.py` read `work/idx_dlc.json`. They are written by `tools/index_all.py`, whose arguments
   (`out endian path@align ...`) are not documented; the part size is `0x7ff00000` (`tools/archive.py ALIGN`).
2. **No script writes `work/generic/dlc_drms.pkl`.** It is read by `dlc_generic.py` (`DlcIds` rebuild),
   `dlc_convert_all.py` and `param_auto.py`. Format reconstructed from the readers:
   `{(pack, name, spec): (header, sections)}` with `pack` = the last 9 characters of the archive path
   (`'ack10.000'`, as `param_auto.py` filters it), `name` = Yura Xenon file-list name (or `0x%08x`), sections from
   `drm.sections_with_data(raw, 'be')`. Rebuilt by `tools/dlc_drms_build.py` from pack10 + pack11 (the two packs
   `dlc_convert_all.py` converts; `verify_ids.py extend` adds the costume packs to the id table later).
   The packs list some files 2-3 times with the same hash, spec **and offset** (pack10: 5 keys, e.g.
   `dlc1_fx_ma_rb_pillory.drm`, `co_dlc_knight_thrall.drm`; pack11: 21 keys) - identical content, kept once.
3. **No script writes `work/generic/lists/`.** `objlists.py` loads `<prefix>_objectlist.txt / _unitlist.txt /
   _objlist.dat` for the prefixes `pc, xbox, xboxtu, dlc_pack10, dlc_pack11, dlc_pack1` (round-trip test + merge).
   Archive names (Yura lists): `\tr8\pc-w\<file>` on PC, `\tr8\xenon-w\<file>` on Xbox - with the leading
   backslash, `names.crc` hashes the line exactly as listed. Rebuilt by `tools/objlists_extract.py` (first archive
   wins: PC patch.000 before bigfile, Xbox TU separately as `xboxtu`).
4. **`unit_ids.py` must run after `script_pairs.py`**: its `intro_from_scripts` pass reads `work/script/pairs_8.pkl`
   (intro ids referenced from Script init blocks). Before that it silently records a `FileNotFoundError` in its
   statistics and writes a smaller intro map.
5. **`script_learn.py` needs `work/generic/dlc_idmap.json`** (it constructs `dlc_generic.DlcIds()`, which without
   the table tries to rebuild it and fails with `store['pc_ids']` on `None`). The table is written by
   `dlc_generic.py` (main: `DlcIds(store, dlc, rebuild=True)`), which needs `dlc_drms.pkl`. But
   `script_name_match.py` and `tex_idmap.py` rewrite the base `idmap.json` afterwards, and the DLC table is derived
   from the base map. Chosen order: build the DLC table provisionally before `script_learn`, rebuild it at the end.
   Upstream order unknown.
6. **`generic_type0.py save` is not a mode** (the docstring says `[eval|save]`): it prints
   `modes: save07 | slim | eval | eval7 | quick` and exits with code 0, writing nothing. The tables
   (`type0_table.pkl`, `type7_table.pkl` + slim versions) are written by `save07`.
7. **No script writes `work/generic/pc_vers.json` / `pc_vers_content.json`.** `dlc_generic.convert_drm` reads them
   (missing file -> empty dict, silently) to give converted base-content sections the PC section `ver` - which ends
   up in the section header, so without them the output cannot be MD5-identical. Keys, from the reader:
   `'type:pcid'` -> runtime ver (most frequent, patch.000 wins) and `'type:pcid:md5(data)[:16]'`, for Scripts also
   `'8:pcid:n' + md5(script_conv.deps_normalized(data, reloc))[:16]`. Rebuilt by `tools/pc_vers_build.py` from
   `work/idx_pc.json` and the PC side of the pair caches.
8. **ffmpeg was hard-coded to `/opt/homebrew/bin/ffmpeg`** (`tools/audio_parse.py`; `xex_extract.py` likewise for
   openssl). On Windows every Wave section (type 6) failed with `media_error:FileNotFoundError` (16 534 in the first
   full Convert) and stayed unconverted - silently, the tool still exits with 0. Now `$TRUDLC_FFMPEG`, else PATH,
   else the macOS path. The ffmpeg needs the `xma1`/`xma2` decoders (gyan.dev 9.0.2 essentials has them; fetched by
   `Get-Tools.ps1`, the runner sets `TRUDLC_FFMPEG`). Even the silent placeholder decodes the XMA to get its length.
9. **No glue assembles the non-DRM files.** B138 = 275 files: 138 DRMs (root, `streamgroups/`, `cinstream/`), 14
   `.mul` streams (`audio/streams/...`, `cinstream/`), 25 music tracks x `.mus/.sam/.mul`, 38 `image/*.raw`, 6
   `local/locals.bin_*`, `padshock/padshocklib.tfb`, 3 `tr8/` lists. The converters exist (`mul_convert`,
   `music_convert` incl. `convert_streams`, `raw_image_convert dlc`, `locals build`, `padshock_convert build`) but
   partly without a command line, and `dlc_convert_all --write` puts every DRM flat into `out/<pack>/` (unnamed records
   as `0x<hash>_<spec>.drm`). `tools/dlc_media_build.py` assembles the tree; `tools/compare_b138.py` compares any tree
   with the B138 manifest file by file. Audio stays silent at this stage (`wave_swap.py`, `mul_audio_batch.py` next).
   `wave_swap.py`'s main only processes the `.drm` files directly in its source folder and looks the Xbox source up by
   the bare file name (`convert_dlc.raw_dlc(basename)` -> `xenon-w\<basename>`), so the 17 `streamgroups/` and 2
   `cinstream/` DRMs would be skipped; `tools/dlc_audio_build.py` runs `swap_file` for every DRM with the path below
   `xenon-w\` (worker initializer), then `mul_audio_batch.job` for every `.mul`.
10. The converter prefers `work/generic/mask_best.npz` (+ `mask_best_vocab.pkl`, from `slim_table.py` ->
   `slim2np.py`) and falls back to the full `mask_table.pkl` - same result, more memory. Not built yet.
11. **First MD5 match with B138:** the merged `tr8/pc-w/objectlist.txt`, `unitlist.txt`, `objlist.dat` written by
   `objlist_merge.py` are byte-identical to the files of the installed B138 `mods/` tree (md5 45dc3b4c…,
   2203e9bd…, e4f12246…). 1045 objects (821 base keep their PC ids, 224 DLC), 119 units, 0 dangling object refs.
12. `generic_cache.py` pairs **1054** base DRMs (its docstring says 975; `drm_reloc.py` mentions 1054). 0 errors,
   26 s with 8 processes, `pairs.pkl` 1 449 582 409 bytes, `pairs_patch.pkl` 14 782 788 bytes (patch pairs:
   g_pda, generalbank, globalsoundinfo, l2_puzzleroom).
13. **The B138 kit ships DLC 2 music.** 19 `music/dlc2_*` tracks (57 files) come from `pack11.000` (*Lara's Shadow*),
   as `docs/INSTALL.md` says (DLC 2 menu images and music). `dlc_media_build.py` writes the pack11 tracks for pack10
   (`MUSIC_PACKS`); their `.mus`/`.sam` are then MD5-equal to B138.
14. **Names from the kit manifests.** `docs/data/B132/B138.kit_manifest.json` record the Xbox source name of every kit
   file; 127 of them match records the dictionary search had not named (CRC-32/BZIP2 of the name = record hash, so a
   name is only taken when it is provably right). Among them 4 pack10 music tracks and 6 audio streams the stage-1 tree
   was missing.
15. **Audio (B43) is not reproducible to the byte.** After `wave_swap.py` 86.5 % of the wave sections equal B138; the
   rest is spread over 61 of 63 files (systematic, not single files). `.mul`: B138 re-encoded 39 files (CHANGELOG,
   nibble 0 convention) and our output also differs from the B43 MD5s in the B90 manifest; ffmpeg's XMA decoder
   version is a likely factor (upstream used Homebrew ffmpeg on macOS, here ffmpeg 9.0.2). Next: compare decoded
   audio instead of MD5.
16. **The morning's per-type table was an inline one-off** (`python -c`, pairing by type + id with `drm_write.read`) and
   could not be rerun. Replaced by `tools/compare_sections.py` (pairing by `compare_drm.section_matches`); its numbers
   differ slightly from the earlier table because it pairs differently and now covers 133 named files instead of 104.

## The "VM" in upstream (what it was, what we do instead)

Upstream was developed on macOS (homebrew paths, `/path/to/` placeholders); the game ran in a **Windows 11 VM** with
the repository shared as `Z:\tru-port`. The VM was used for (1) game tests - `vm_baseline_sync.ps1` copies a baseline
into the VM's `mods/`, `vm_run.ps1` + `runner_scenarios/*.json` start the game, load a level through the
TRLAU-menu-hook F8 menu, watch for crashes, read memory, take screenshots - and (2) shader validation on a real D3D9
device (`vm_ps_validate.ps1`, `vm_ps_draw.ps1`, through dgVoodoo2's `d3d9.dll`; FINDINGS marks a boot crash as
"infrastructure (driver/VM)"). It is not a conversion step.

Manifest origins `vm_mods_expected` (30) and `vm_extra` (10) are files that were already in the VM's `mods/` and
were kept without a recorded script: e.g. the level `*_map.drm`, `co_dlc_earphonecam.drm`, `co_lights.drm`,
`dlc1_uo_pillory_collision_helper.drm` - and a log `convert_costumes.log` (costumes were converted at some point).

Here: native Windows with a real GPU replaces the VM (manual game tests by the user; the shader validation scripts
can run natively). Automated game runs are not used on the user's desktop (they take focus and send keys). Files
that cannot be reproduced by a script are taken from B138.

## Stage 1 output vs B138 (DLC 1, 2026-10-27)

`dlc_convert_all.py --media --write`, pack10: 134 DRMs; 104 have a B138 counterpart by name (30 not: unnamed
`0x...` records or other names), **0 MD5-identical** (expected: stage 2-4 still missing). Section-level comparison
(sections paired by type + id; "identical" = data, reloc and ver equal):

| Type | identical | different |
|---|---|---|
| 2 | 10 752 (100 %) | - |
| 11 Obj | 94 (100 %) | - |
| 5 texture | 3965 (99.7 %) | 2 size differs, 9 not in B138 |
| 7 DTP | 11 127 (97.7 %) | 264 same size |
| 10 material | 846 (84 %) | 87 size differs, 76 same size |
| 8 Script | 4220 (68 %) | 1964 same size |
| 12 mesh | 26 (15 %) | 153 same size |
| 0 general | 10 (4 %) | 249 size differs |
| 6 wave | 0 | 8053 size differs - stage 1 writes silence; real audio = `wave_swap.py` / `mul_audio_batch.py` |
| 9 shader lib | 0 | 1427 differ, 255 not in B138 - shader translation = stage 3 |

30 of the 104 files have a different section count. Closest files: small fx DRMs (93-98 % of sections
identical); furthest: the big units (`dlc_dungeon` 17 %, `dlc_dungeonhalla` 20 %, `dlc_pillory` 22 %).
Conclusion: the reconstructed stage 0/1 reproduces what stage 1 is supposed to produce; the differences sit in
the later stages (audio, shaders, data fixes listed in LINEAGE.md).

## Run log

| Date | Step | Result |
|---|---|---|
| 2026-10-27 | Cache | ok, 1054 pairs, 0 errors, 27 s |
| 2026-10-27 | Ids | failed in `generic_store.py`: `work/idx_pc.json` missing -> step Index added |
| 2026-10-27 | Index | ok: idx_pc 7348 files, idx_xbox_base 10252, idx_dlc 620, 0 errors, 45 s |
| 2026-10-27 | Ids | `generic_store` ok (pc_store 21327, xb 21301, multi-content PC ids 257); `generic_ids` ok (coverage: unmapped only type 5 345/36516, 7 24, 8 195, 10 8); `objlist_merge` failed: `work/generic/lists/` missing -> `objlists_extract.py` added |
| 2026-10-27 | Ids | ok, 43 s: lists extracted (PC from bigfile, no list in patch.000), all round trips ok, merged lists = B138 (MD5); `unit_ids`: unit 81, tguid 545, intro 7988, portal 161, rec 1779, all uncontested; intro_from_scripts missing input -> moved to Learn |
| 2026-10-27 | Learn | `generic_learn save` 976 s (mask_table.pkl 778 590 463 B), `generic_symbols seed` 571 s, `script_pairs` 16 s (pairs_0/7/8/13), `unit_ids` 12 s (intro_from_scripts: +193, 14 disagree with unit DTPs); `script_learn save` failed: no `dlc_idmap.json` -> step Tables |
| 2026-10-27 | Tables | `dlc_drms_build` failed on duplicate pack records -> fixed (identical content) |
| 2026-10-27 | Tables | ok, 824 s: 300 DLC DRMs (pack10 134, pack11 166; 57 unnamed), dlc_drms.pkl 2.98 GB; DLC new ids 2:2041 5:1393 6:301 7:2908 8:2370 9:539 10:565 12:357, few collisions; `script_learn` in-sample 17039 pairs, exact-mod-deps 52.3 % (100 % of the convertible rest); `script_name_match` +111 script ids, +105 symbols; `tex_idmap` 5751 content-voted (309 changed); **`generic_type0 save` wrote nothing** (wrong mode) -> step Prep with `save07` + `pc_vers_build` |
| 2026-10-27 | Convert | runner bug (single-tool step unrolled, so `dlc_convert_all.py` ran **without** options = check only, 360 s): 307 DRMs (300 + 7 duplicate records), readback_ok 307, reloc_bounds_bad 0, obj_ok 228, idref_local 357 653, idref_pc_base 158, idref_DANGLING 29 542 - only types 5/9/10 (media, expected without `--media`); routes e.g. 2 pc_copy 12 670 / convert 2267, 7 pc_copy 8023 / template 5693 / convert 2603 / analog 1286, 8 pc_copy 12 445 / convert 5055; unmapped ids {11: 119, 2: 1211, 7: 911, 8: 9, 110: 124, 111: 451, 112: 313, 114: 1200, 6: 37} |
| 2026-10-27 | Names | ok, 160 s: 646 DLC records, 210 unknown hashes, 165 recovered (76 822 strings, 1158 templates); every DRM named now (pack10 140, pack11 167, pack1/pack2 2 each); still unnamed: non-DRM records pack10 39, pack11 63 |
| 2026-10-27 | Convert | `--media --write`, 1612 s: 307 DRMs written, readback_ok 307, reloc_bounds_bad 0, **no dangling id refs** (local 384 972, PC base 2381), obj_ok 228; routes 5/10/12 media ok; **6 media_error:FileNotFoundError 16 534** (ffmpeg path, see finding 8), 9 media_error:NotImplementedError 4839 (shaders, by design) -> rerun after the ffmpeg fix |
| 2026-10-27 | Convert | rerun with ffmpeg, 3097 s: 300 DRMs, exit 0; only `9 media_error:NotImplementedError 4839` (shaders, stage 3) |
| 2026-10-27 | Media | ok, 31 s; `compare_b138` stage1: 46 identical / 149 different / 80 missing / 1 extra of 275. Missing: 19 DLC 2 music tracks (pack11, shipped by the kit), 4 music tracks + 6 audio streams of pack10 without a known name, 5 PC files (later builds / test VM); extra `g_pda.drm` |
| 2026-10-27 | Audio | ok, 117 s: 8061 waves in 64 DRMs, 10 `.mul`; no MD5 change against B138 (B138 re-encoded the `.mul`; B90's B43 MD5s also differ) |
| 2026-10-27 | Names | `dlc_names.py` + kit manifest names: 260 names, 127 matching unknown records, 56 more by dictionary; 38 records newly named, 0 changed; pack10 1 unnamed (0x753ecefd, 983 168 B), pack11 63 |
| 2026-10-27 | Media + Audio | rerun (tools called directly, log `logs/Manual_Media-Audio_20261027_162633.log`): music pack10 6 + pack11 19 tracks; **92 identical / 178 different / 5 missing / 1 extra of 275**; `.mul` 39 of 39 swapped. `compare_sections` stage2a: 2 / 11 100 %, 5 99.6 %, 7 97.4 %, 13 95.2 %, 0 88.8 %, **6 wave 86.5 %** (stage1: 0 %), 10 83.2 %, 8 79.5 %, 12 31.7 %, 9 0 % |
| 2026-10-27 | Prep | ok, 818 s: `generic_type0 save07` 796 s (type0_table 9 827 722 keys, type7_table 4 084 298 keys, + slim npz); `pc_vers_build` 21 s: 1060 PC DRMs indexed, pc_vers 37 813 (1818 with several versions, 2481 from patch.000), pc_vers_content 28 928 (856 multi) |
