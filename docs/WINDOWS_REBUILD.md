# Rebuilding the pipeline on Windows (branch `windows`)

Running log of what it takes to reproduce the stage 0-1 pipeline (docs/PIPELINE.md) on a Windows PC from the user's
own files. Goal: rebuild DLC 1 (*Beneath the Ashes*) step by step, compare every produced file with the B138 kit
manifest, and then use the same pipeline for DLC 2 (*Lara's Shadow*) and the costume packs.

Where the fixes of stage 2b come from (upstream's `work/ws/` folders, builds, overlay layers): `docs/WS_MAP.md`.

## Environment

* Python 3.14 in a venv **outside** the repository (`..\bin\venv`), packages from `requirements.txt`
  (numpy, Pillow, capstone).
* All tools are run **from the repository root**: `..\bin\venv\Scripts\python.exe -u -I -X utf8 tools\<tool>.py`
  (`-X utf8`: finding 19).
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
* The stages are driven by `scripts/windows/Invoke-TruPipeline.ps1 -Step <name>` (logs every tool's output; overview
  in `docs/ARCHITECTURE.md`); the commands below are what it runs.

## Stage order (as reconstructed)

| Step | Commands (from the repository root) | Output |
|---|---|---|
| Index | `tools/index_all.py work/idx_pc.json le ../data/pc/bigfile.000@7ff00000 ../data/pc/patch.000@7ff00000`<br>`tools/index_all.py work/idx_xbox_base.json be <layer1>@7ff00000 <layer2>@7ff00000 <TitleUpdate.000>@7ff00000`<br>`tools/index_all.py work/idx_dlc.json be <pack10>@7ff00000 <pack11>@7ff00000` | `work/idx_*.json` |
| Cache | `tools/generic_cache.py`, `tools/generic_cache.py patch` | `work/generic/pairs.pkl`, `pairs_patch.pkl` |
| Ids | `tools/generic_store.py`, `generic_ids.py`, `objlists_extract.py` (**new**), `objlist_merge.py` | `store.pkl`, `idmap.json`, `merged/` |
| Learn | `generic_learn.py save`, `generic_symbols.py seed`, `script_pairs.py`, `unit_ids.py` | `mask_table.pkl`, symbols (key 100) in `idmap.json`, `work/script/pairs_*.pkl`, `unit_idmaps.json` |
| Tables | `dlc_drms_build.py` (**new**), `dlc_generic.py` (provisional), `script_learn.py save`, `generic_type0.py save07`, `script_name_match.py`, `tex_idmap.py`, `dlc_generic.py` (final) | `dlc_drms.pkl`, `dlc_idmap.json`, `work/script/script_table.pkl`, refined `idmap.json` |
| Prep | `generic_type0.py save07`, `pc_vers_build.py` (**new**), `model_point_fix.py learn`, `model_point_fix.py selftest`, `dtpid_evidence.py` (finding 32) | `type0_table.pkl`, `type7_table.pkl`, `pc_vers.json`, `pc_vers_content.json`, `work/chain_aim/model_point_rules.pkl`, `work/generic/dtpid_evidence.pkl` |
| Convert | `tools/dlc_convert_all.py --media --write --extra-fixes` (findings 32, 36: `--jobs`) | `work/generic/out/` |
| Names | `tools/dlc_names.py` (also takes the Xbox source names of `docs/data/*.kit_manifest.json` when the hash matches) | `work/generic/dlc_names.txt` (names of unnamed DLC records) |
| Media | `dlc_media_build.py work/rebuild/stage1/mods pack10` (**new**; music of pack10 + pack11), `locals.py build work/rebuild/stage1`, `padshock_convert.py build work/rebuild/stage1/mods`, `compare_b138.py work/rebuild/stage1/mods stage1` (**new**), `compare_sections.py work/rebuild/stage1/mods stage1` (**new**) | DLC 1 stage-1 tree in the B138 layout + per-file and per-section-type comparison |
| Audio | `dlc_audio_build.py work/rebuild/stage1/mods work/rebuild/stage2a/mods` (**new**: `wave_swap` for every DRM incl. sub folders + `mul_audio_batch`), `compare_b138.py work/rebuild/stage2a/mods stage2a`, `compare_sections.py work/rebuild/stage2a/mods stage2a` | DLC 1 tree with real audio (B43) |
| Assemble (optional, after Media) | `render_tables_build.py build`, `rend_extract.py pairs`, `render_tables_build.py check`, `rend_extract.py dlc`, `shader_map.py`, `material_rules.py`, `material_dlc.py`, `pc_shader_sections.py`, `terrain_validate.py`, `mesh_tables_build.py` (**new**, finding 37), `dlc_assemble_build.py work/rebuild/stage1/mods work/rebuild/asm_stage1/mods` (**new**; `--pack pack11` for DLC 2), `dlc_audio_build.py` into `asm_stage2a`, `compare_b138.py`, `compare_sections.py` | upstream's full stage-1 route (findings 28, 34, 37): render and mesh tables in `work/render/`, DLC 1 tree with PC shader sections and DLC materials |

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
| 2a | Audio: `wave_swap.py` (Wave sections in place), `mul_audio_nch.py` (`.mul` streams, one channel per Xbox stream, game convention; B43's `mul_audio_batch.py` with `--mul b43`) | done; wave sections 86.5 % = B138, `.mul` vs Xbox source median 44.4 dB (findings 17, 18) | 2.5 min |
| 2a+ | Remaining audio differences: wave = decoder rounding (explained, finding 17); `.mul`: what B138 changed on 6 files beyond re-encoding, listening test in game | partly open | - |
| 2b | Data fixes B1-B47 (LINEAGE.md) in `tools/dlc_fixes_build.py`: `cine` (B44/B45), `float` (B46/B47), `tag404` raft rings (B33), `postfix`, `analog` done; next the remaining layers of `docs/WS_MAP.md` | in progress (findings 20-26) | minutes per fix; much work |
| 3 | Shaders B72-B89 (`work/ws/shader4/`) | open | largest block |
| 4 | Last layers to B90_gold_L4 (Giro 5-7), then CHANGELOG changes up to B138 | open | - |
| - | 40 `vm_mods_expected`/`vm_extra` files | check after 1c; else take from B138 | - |
| - | patched `tru.exe`, `movies/credits_DLC1.bik` | from the B138 kit (rebuild via Steamless + guards optional) | - |

### Stage 3 plan (shaders and materials, drafted 2026-10-27, not started)

Source: `docs/PIPELINE.md` "Stage 3", `work/ws/shader4/`, `work/ws/contratti/`, `work/ws/codefirst/`,
`work/ws/giro5/`, `work/ws/giro6/`. State before stage 3: 2409 shader-lib sections in our DLC 1 DRMs, 1929 paired
with B138, **0 identical**; materials 83 %, meshes 32 % (they reference shader ids).

| Build | What | Upstream script | Reads |
|---|---|---|---|
| B72 | first translated lib (Xbox lib 2173 -> SM3, adapted to the PC MaterialParams layout) | `shader4/f4_build.py` (+ `xenos2sm3.py`, `sm3asm.py`) | previous baseline |
| B73-B83 | light transplant (Xbox lit shader + PC light block from a donor, `f9_transplant.py`), all DLC libs (`f10_build_dlc.py`, `f12_build_all.py`), unlit libs translated directly (`f13_unlit.py`) | `shader4/f9*`, `f10`, `f12`, `f13` | previous baseline |
| B86 `contratti` | sampler contract: Xbox sampler register -> PC slot of the canonical material | `contratti/f14_slotmap.py`, `test_contract.py` (16 tests) | B83/B84 |
| B87 `materiali19` | 19 materials re-translated (ids 2756-2774) | `codefirst/build_B87.py` | B86 |
| B88b `acqua` | 7 unlit water libs (2775-2781) | `giro5/build_unlit.py` | B87 |
| B89 / L-layers | textures 259/2224, libs 975/976/2782 (`giro6/build_20323.py`), stage 4 `layers.py` | `giro6/` | B88b |

Approach: run each builder against our stage tree instead of `work/baseline/B<n>` (paths to adapt per script; only 2
of the shader4/contratti/B87 scripts carry the author's local paths), measure shader-lib and material sections with
`compare_sections.py` after each build, keep the gate `shader4/gate_stesso_id.py` (same material => same lib bytes in
every DRM). Pixel shaders can be validated on this Windows PC directly with Direct3D 9 (`CreatePixelShader`, as
upstream's `tools/vm_ps_validate.ps1` did inside its VM) - no VM needed.

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
17. **Decoded audio vs B138** (`tools/compare_audio.py work/rebuild/stage2a/mods stage2a`, report
   `work/rebuild/audio_stage2a.json`):
   * **Wave sections are effectively equal.** 1085 differing sections, all mono, same length; 72 213 of 65 153 664
     samples differ (0.11 %), max |diff| median 25, SNR median 90.7 dB, minimum 35.9 dB (wave id 1140, shared by four
     unit DRMs). The differences sit at single IMA block boundaries: rounding of the decoded XMA, not a missing fix.
     7 sections also differ in the FSB header.
   * **`.mul`: B138 is encoded for the game's decoder** (nibble 0 ignored): decoding B138 with that convention and ours
     with the FSB convention gives 34-47 dB for 22 of 39 files. Our `mul_audio_batch.py` (B43) still writes the FSB
     convention, i.e. the crackling version; the B138 re-encoder is not in the repository.
   * **17 `.mul` differ in the right channel only** (left channel correlation 0.994-1.000, right ~0): B138 maps other
     Xbox streams to the right channel. Two-stream music (`l3_caverns_mus_01`): same as ours (L = 0, R = 1). Six-stream
     music (`dlc_dungeon_mus_01`, three stereo layers): ours L = 0, R = 1, B138 L = 0, **R = 3**. Mono voice
     (`c_zip_1_pdlc1_invasion_01`): ours L = R = stream 0, B138 R uncorrelated with the only Xbox stream. Whether this
     is intended (how the PC music system reads layers) or a bug is not documented; to check against PC base-game
     `.mul`/`.mus` files with several layers. Probes: `mul_audio.xb_channels` + correlation per stream.
   * **Caution - this right-channel result may be a measurement artefact.** `compare_audio.py` (like
     `mul_audio.pc_pcm`) splits every PC audio block into two halves = L/R. But `music_convert.convert_mul` keeps the
     Xbox channel count in the PC header and sizes each block for *all* channels (6 for `dlc_dungeon_mus_01`), while
     `mul_audio.swap` assumes 2 channels (`nbytes // 72`) and fills the 6-channel space with a continuous L stream in
     the first half and R in the second. So for files with more than 2 Xbox streams "left/right" above means "first
     half / second half of the block", and for mono sources the layout question is the same. Do not draw conclusions
     from the L/R numbers of multi-stream files until the PC base-game layout is known (being checked against the
     32 base-game music pairs, `music_convert.base_pairs`). -> resolved in finding 18; the count is 19, not 17, and
     the whole right-channel observation was this artefact (the files are not stereo).
18. **PC `.mul` layout and convention, learned from the base game - B43's `mul_audio.swap` is wrong for every `.mul`
   that is not stereo; B138 is right** (see the correction at the end of this finding).
   * Base game (32 music pairs Xbox layer1/2 vs PC bigfile): PC channel count = Xbox stream count (7 x 2, 20 x 4,
     5 x 6). Every PC audio block holds the channels one after another (`nbytes / 36` = channels x blocks of 64
     samples); **PC channel k = Xbox stream k** (correlation 0.99-1.00, no reordering).
   * **Nibble convention: the game's** (header sample, nibble 0 ignored, nibbles 1..63): base tracks
     `l2_cliffclimb_mus_01` / `_02` decode against the Xbox source at 38.7 / 45.4 dB, lag 0; with the FSB
     convention only 24.6 / 26.0 dB at lag 1-2 (`l1_intro` matches neither: a different PC mix). B138's re-encode
     follows this convention; `mul_audio_batch.py` (B43) does not.
   * The 39 DLC `.mul`: 20 x 2 channels, 5 x 1 (voice), 13 x 4, 1 x 6 (Xbox header = stream count = PC header in ours
     and in B138). `mul_audio.swap` always encodes stereo (`nbytes // 72`, first half L, second half R), so for the
     **19 non-stereo files** the B43 audio is time-scrambled across the channel slots. These are the 19 files at
     ~0 dB in finding 17: all 5 DLC voice lines and the layered ambient music.
   * Fix (stage 2a): `tools/mul_audio_nch.py` encodes every Xbox stream into its own channel slot with the game
     convention; `dlc_audio_build.py` uses it by default (`--mul b43` keeps upstream's B43 behaviour).
   * **Correction (same day): B138 is NOT scrambled.** An earlier version of this finding said B138 had the same
     defect ("left half identical to ours, second half stream 3"). That was an artefact of the half/half decoder of
     finding 17 (caution there). Decoded per channel (`compare_audio.py`, header channel count), B138 matches the Xbox
     source for the 19 non-stereo files at median 45.1 dB (worst channel). The B138 re-encoder (not in the
     repository) handles channels correctly; only B43 / `mul_audio.swap` is wrong. Not an upstream bug report.
   * Result after the fix (`compare_audio.py work/rebuild/stage2a/mods stage2a`, worst channel per file):
     ours vs Xbox source min 25.1 / median 44.4 / max 54.8 dB (stereo 27.6 / 44.0, other 25.1 / 44.5);
     ours vs B138 median 39.9 dB (non-stereo 43.7). B138 vs Xbox source is lower than ours on some files -
     `light_flash_huge_a_07` 7.5 dB, `pdlc1_010_intro` 12.8, `c_zip_2_pdlc1_water_01` 14.2,
     `dlc2_ceremony_room_amb_02` 15.0, `dlc2_machine_room_amb_03` 15.2, `pdlc1_030_finale` 16.0 - so B138 changed
     these beyond re-encoding (perhaps its anti-click work: CHANGELOG "≈432 clicks/min, now ≈9 in the offline
     emulation"). Open: what B138 did there, and whether our version clicks in game (needs a listening test).
19. **Text encodings on Windows (pipes, code pages).**
   * Python started with `-I` ignores `PYTHONIOENCODING`; writing to a pipe it then uses cp1252, and any character
     outside cp1252 (e.g. `→`, game text) raises `UnicodeEncodeError` - reproduced 2026-10-27 with a print of `→`.
     `Invoke-TruPipeline.ps1` therefore runs the tools with `-u -I -X utf8` and reads stdout/stderr as UTF-8
     (`ProcessStartInfo.StandardOutputEncoding`).
   * PowerShell decodes the output of native programs (git) with the console code page: UTF-8 umlauts and dashes
     come out as mojibake (`├╝`, `ΓÇô`). `Test-TruUploadReady.ps1` switches `[Console]::OutputEncoding` to UTF-8
     around its git calls.
   * Our `.ps1` files are ASCII only (plus UTF-8 BOM): Windows PowerShell 5.1 reads a file without BOM as ANSI, where
     the UTF-8 bytes of typographic quotes and dashes turn into characters PowerShell treats as quotes (strings
     break). Markdown keeps its dashes and arrows (UTF-8, rendered by GitHub).
   * A double BOM (`EF BB BF EF BB BF`) makes PowerShell parse the `<#` help block as code (ParserError on the first
     `-` in the help text). Check the first bytes after rewriting a script.
20. **Stage 2b map: what still differs, by upstream origin** (`tools/rebuild_status.py stage2a`, joins
   `sections_stage2a.json` with the origin column of the B90 manifest; 133 DRMs, 2026-10-27, after the audio fix):

   | Origin (B90 manifest) | Files | Fully identical | Differing section types (identical / total) |
   |---|---|---|---|
   | `derived:B43` | 31 | 0 | general 109/115, wave 2122/2476, DTP 561/597, script 1215/1781, mat 131/136, mesh 2/41 |
   | `vm_mods_expected` | 30 | 9 | script 737/753, mat 49/50, mesh 4/20, 13 20/21 |
   | `derived:B90_gold` | 13 | 0 | tex 1724/1732, wave 2724/2982, DTP 9532/9660, script 471/480, mat 418/505, mesh 32/48 |
   | `derived:B87_materiali19` | 12 | 0 | wave 190/346, DTP 285/343, script 603/616, mat 89/125, mesh 1/19 |
   | `mods_fix18_awf_extra` | 11 | 0 | DTP 53/66, script 475/488, mesh 0/11 |
   | `derived:B86_contratti` | 9 | 0 | tex 534/538, wave 76/113, DTP 56/82, script 204/208, mat 103/134, mesh 13/28 |
   | `derived:B90_gold_L4` | 6 | 0 | general 35/37, tex 773/782, wave 587/655, DTP 132/139, script 251/451, mat 167/230, mesh 8/12 |
   | `derived:B45` | 2 | 0 | DTP 0/4 (`pdlc1_030_finale` 0 %, `pdlc1_010_intro` 79 %) |
   | `derived:B47` | 2 | 0 | general 56/76, wave 992/1171, DTP 210/215, script 267/682, mat 24/26, mesh 0/21 |
   | others (B41, B44, B46, B83, B88b, fix14, glitchfix, current) | 16 | 0 | small rests |

   Shader libs (type 9) are 0 % everywhere (stage 3); materials and meshes partly reference shader ids, so some of
   their differences may only close after stage 3. Script (type 8) differences concentrate in the big level DRMs
   (B43, B47, L4): word-level data fixes = stage 2b. Wave differences are the decoder rounding of finding 17.
   Order chosen for 2b: cutscene command lists (B44/B45, `work/ws/cine/`), float words (B46/B47, `float_fix.py`),
   raft rings (B33, `work/ws/raftring/`), then the remaining overlay layers of `docs/WS_MAP.md`.
21. **Stage 2b, fix 1: cutscenes (B44/B45)** - `tools/dlc_fixes_build.py work/rebuild/stage2a/mods
   work/rebuild/stage2b/mods` (new; applies the fixes in order, report `work/rebuild/fixes_report.json`) calls
   `work/ws/cine/build_cine.py` for `pdlc1_010_intro` and `pdlc1_030_finale`: command DTPs 22643 / 23766 / 22604
   (40 + 16 + 10 words changed) and the effect DTP 23767 (420 words).
   * Result (`compare_sections.py ... stage2b`): the three command DTPs now equal B138 (DTP total 11 126 -> 11 129
     identical). Effect DTP 23767: 417 -> **9** differing words of 2908; all 9 are u16 halves in the other order.
     `fx_apply.py` keeps the value of the author's B44 tree for words without a learned rule - that tree is not
     public, so these 9 stay open (candidate: the u16-pair float fix of B46/B47).
   * `work/ws/` scripts still carry the author's local paths: 407 of 578 contain `/path/to/`, `~/Downloads/tru-port`
     or `expanduser('~...')`. They are fixed one by one when a script is used, with the same rule as `tools/`
     (game = `../data/pc`, Xbox files = `../data/...`). Done: `work/ws/cine/cinepairs.py` (PC bigfile, Xbox layers).
   * `cinepairs.load()` caches the base-game cutscene pairs in `work/ws/cine/pairs.pkl` (first run only).
22. **Stage 2b, fix 2: float words (B46/B47)** - fix `float` in `dlc_fixes_build.py` runs
   `work/ws/cine/float_fix.py` in mode `s16` (u16 halves swapped; 12 words: `dlc1_uo_water_wheel` DTP 20790 x 8,
   `dlc1_uo_pillory` 20630 x 3, `dlc1_uo_bend_switches` 20651 x 1) and then `raw` (still Xbox byte order; 44 words in
   `dlc_dungeon` DTP 20256). LINEAGE.md mentions "69 verified raw floats" for B46/B47; on our tree the script finds
   56 in total - the rest may come from steps not public or from a different input state.
   * Every one of the 56 changes moves the word to the B138 value (none made a word wrong): `dlc_dungeon` 20256
     65 -> 21 differing words, `dlc1_uo_pillory` 20630 3 -> 0, `dlc1_uo_bend_switches` 20651 4 -> 3; DTP sections
     identical 11 129 -> 11 131.
   * `float_fix.py` only reads the top folder of the tree, so `cinstream/` (the 9 open words of finding 21) and
     `streamgroups/` are not covered.
   * The fix report is `work/rebuild/stage2b/fixes_report.json` (= `<OUT>/../`).
23. **Stage 2b, fix 3: raft/grapple rings (B33, record tag `0x404`)**.
   * Upstream's `work/ws/progress/tag_records.py` (read-only; rules per (tag, offset) learned from the base pairs) on
     stage2b: 22 rules, 329 record words of the DLC checked, **0 defects** - its rules for `0x404` (+0xc, +0x10,
     +0x20) already hold. It learns no rule for +4, the word FINDINGS.md says must stay raw.
   * `tools/tag404_check.py` (new, read-only) compares the +4 word of every `0x404` record with B138: 23 records;
     B138 keeps the raw Xbox bytes in all 17 records of the new DLC DTPs (id >= 20000), and the converted s32 value
     in the 6 records of the base-game DTP 2154 in the costume DRMs. Ours had 16 of the 17 swapped.
   * Fix `tag404` in `dlc_fixes_build.py`: +4 word raw in `0x404` records of DTPs with id >= 20000, all DRMs incl.
     sub folders -> 16 words in 6 DRMs (caverns, dungeon, dungeonhallb, pillory, treasureroom, water_wheel);
     `tag404_check`: **23 of 23 = B138**. The DTPs still differ elsewhere (e.g. `dlc_dungeon` 20258 873 -> 868
     differing words, `dlc_water_wheel` 20661 20 -> 17, `dlc_treasureroom` 21153 6 -> 3), so the identical-section
     count stays 11 131.
24. **Stage 2b, fix 4: upstream's DLC 1 post-step (`tools/dlc1_postfix.py`, steps 1-2)**.
   * Which fix tools are already part of `Convert`: `dlc_generic.py` imports `dtpid_sweep`, `dtp_align_fix`,
     `model_point_fix`, `tag403_fix`, `portal_fix`, `link_ratio_fix`, `dtp_descfix`, `aidata_fix`, `soundplex_fix`.
     **Correction (2026-10-28, finding 32): imported is not applied** - most of these run only with
     `convert_drm(..., extra_fixes=True)`, which `assemble_dlc` sets and our step Convert (`dlc_convert_all.py`)
     does not.
     Not wired: `dlc1_postfix` (uses `streamname_fix`, `refs_scan`), `name_string_fix` (targeted, raft chain
     'chain_free'), `analog_word_fix` (scan/fix of near-clone DTPs), `unbound_fix` (shader samplers -> stage 3).
   * `dlc1_postfix.py` is upstream's own post-step for DLC 1: (1) streamgroup name tables of unit DRMs (a broken name
     made "Create new savegame" hang), (2) R12 name strings of type-0 sections (`refs_scan.string_fixes`), (3) single
     words from `work/ws/dtpkeys/out/min/log_words.tsv` - **that log is not in the repository**, so step 3 is skipped.
     Its `main()` only writes below `work/ws/converge/`; fix `postfix` calls steps 1-2 per DRM directly.
   * Tried alone on a copy of stage2b (`stage2c`): streamname 0 sections (ours already right, e.g.
     `dlc_watertunnel` type 0 17/17 = B138), R12 20 strings fixed (`dlc_dungeon` 17, `dlc_treasureroom` 2,
     `dlc_pillory` 1), 0 manual. Type-0 sections identical **230 -> 246 of 259 (88.8 -> 95.0 %)**:
     `dlc_treasureroom` 17 -> 19 of 19, `dlc_dungeon` 31 -> 44 of 50, `dlc_pillory` 27 -> 28 of 29.
25. **Checks without a fix needed, and a path pitfall.**
   * Raft chain name (`tools/name_string_fix.py`, the author's case `chain_free` -> `hcian_free` that kept the
     underwater chain from being released): `dlc1_uo_raft_bridge` DTP 20765 +1312 is `chain_free` in stage2b, B138
     and on the Xbox - the current converter already gets it right, the fix is not needed.
   * Two conventions for "overlay" folders: `dtp_audit.overlay(dirs)` resolves relative paths against `work/`,
     `load_overlay(dirs)` (`dtpid_sweep.py`, `soundplex_fix.py`, used by `analog_word_fix.py` and others) against the
     current folder. A first `analog_word_fix.py scan rebuild/stage2b/mods` therefore saw **0 files** and printed an
     empty result (`TOTAL {}`) - not a finding. Pass `work/rebuild/...` to `load_overlay` tools.
26. **Stage 2b, fix 5: near-clone DTPs (`tools/analog_word_fix.py`)**. Scan on stage2b (with the correct path): 33
   words in 18 DRMs, all `fix` (no re-authored analog skipped) - mostly u8/u16 fields converted as one u32 in effect
   DRMs (glare, waterfall, bugs, water spout), `knight_thrall` (8), `knight_thrall_chunkdoll` (2), `wp_dlc_gold_shotgun`
   (2). Fix `analog` in `dlc_fixes_build.py` (fix mode as a library; every changed word is compared with B138 and
   noted): **33 of 33 = B138**. All five fixes together (stage2a -> stage2b): DTP sections identical 11 131 -> 11 157
   (97.6 %); `rebuild_status`: `cinstream/pdlc1_030_finale.drm` (origin `derived:B45`) is now fully identical, 10 of
   133 DRMs in total.
27. **Script sections: most differences are shifted Symbol ids, caused by one bogus entry in our symbol map.**
   * `tools/script_diff.py work/rebuild/stage2b/mods stage2b` (new, read-only; classifies each differing word by how
     it came from the Xbox word, in ours and in B138): 9580 differing words in 86 DRMs (most in the big units:
     `dlc_dungeon` 1880, `dlc_water_wheel` 1457, `dlc_watertunnel` 854). 8277 are "other / other" (neither side is a
     byte permutation of the Xbox word) - different values, not byte order; 1092 are s16 in ours / other in B138.
   * The "other" words are u16 Symbol ids (often the high half of a word): 1644 distinct (ours, B138) pairs, and they
     follow fixed offsets - ours `dc30 dda0 e26d dcc7 dd03 dd88` = B138 `41d0 4340 480d 4267 42a3 4328` + `0x9a60`;
     ours `2a7a 2b29` = B138 `4258 4307` - `0x17de`; ours `0229` vs `0228`.
   * Cause: `dlc_generic.DlcIds.sym()` maps an Xbox Symbol by the learned map (idmap key 100); Xbox symbols above the
     base maximum `xs_max` are DLC-new and shifted by `pc_max - xs_max`; others are interpolated / guessed, and a guess
     that collides becomes `40000 + xs`. Our map has **one outlier, Xbox 48875 -> 48875 = `0xBEEB`** (the marker of the
     effect DTPs, `BE EB BE EB`), learned as a symbol. It makes `xs_max` = 48875 (`dlc_idmap.json` sym_info:
     xbox_max 48875, pc_max 48875, **shift 0**), so no DLC symbol counts as new: they are guessed and collide, e.g.
     Xbox 16368 -> ours 56368 = `0xdc30` (40000 + 16368) where B138 has 16848 = `0x41d0` (16368 + 480). Without the
     outlier `xs_max` = 16347 (all other 7530 entries are <= 16347), `pc_max` = 16828 (`PC_SYM_MAX`), shift 481 -
     one off B138's 480, still to explain. Convert's symbol stats agree: `guess_collision_new` 24386, `dlc_new_shift`
     2700.
   * **Cause (confirmed):** the entry is already in `work/generic/idmap_pre_snm.json` (backup taken before
     `script_name_match`, 13:07), so it comes from `generic_symbols.py seed` (step Learn). Its harvest round collects
     votes from words whose learned class is a symbol field in **types 7 and 8**; the effect-DTP marker
     `BE EB BE EB` was classed as a symbol field and voted 0xBEEB -> 0xBEEB. `generic_symbols.py` has a range guard
     (`XS_MAX, PS_MAX = 20000, 17000`, "Xbox base 16347 / TU 19634, PC 16828") and applies it in `raw_votes` and
     `bootstrap` - but not on the `seed` result. 48875 is the only entry outside the guard.
   * **Fix:** the `seed` path now applies the same guard to its result (one line in `tools/generic_symbols.py`).
     Rerun needed because the symbol map feeds everything after it: Learn from tool 2 (`generic_symbols seed`,
     `script_pairs`, `unit_ids`), Tables, Prep, Convert, Names, Media, Audio, then the 2b fixes - about 1.5 h.
     Expected: `dlc_idmap.json` sym_info with xbox_max 16347 and shift > 0, Convert's `guess_collision_new` far
     below 24386, and most of the 8277 shifted script words equal to B138.
29. **Symbol fix applied: the rerun confirms the cause of finding 27, and B138's shift is 480, not 481.**
   * Rerun with the guarded `generic_symbols.py seed` (Learn from tool 2, Tables, Prep, Convert, Names, Media,
     Audio, 2026-10-27 20:02-23:09): symbol map 7498 entries (was 7531 incl. 0xBEEB), `dlc_idmap.json` sym_info
     xbox_max **16347**, pc_max 16828, shift **481** (was 0). Convert symbol stats: `guess_collision_new`
     24 386 -> **1 219**, `dlc_new_shift` 2 700 -> **43 215**, `interpolated` 48 290, `guess_lower` 7 467.
   * Tables took 6 977 s this time (last `dlc_generic.py` call 5 392 s, the first call of the same step 5 s; the
     first Tables run took 824 s in total). Not the cause: `generic_type0.space_maps()` (checked - it only loads the
     small `unit_idmaps.json`). Suspected: memory pressure - `dlc_generic.py` loads `dlc_drms.pkl` (~3 GB) and the
     generic store while my parallel analysis jobs (all cores) ran between 20:12 and 22:09. **Verified 2026-10-28
     00:22:** `dlc_generic.py` alone takes **4 s** (log `logs/Manual_Timing-dlc_generic_20261028_002212.log`), with an
     identical `new` id table (sym_info now records shift 480). Rule: no heavy parallel jobs while a pipeline step
     that loads `dlc_drms.pkl` / the store runs.
   * After the 2b fixes (`analog` still 33/33 = B138): script words differing from B138 unchanged in number (9 580),
     but `script_diff.py` (now with a delta histogram of the differing u16 halves) shows why: **8 552 of 10 810
     differing halves (79.1 %) are exactly +1**, 8 006 of them with a B138 value >= 16828 (the DLC-new symbol range) -
     e.g. ours `4341` / B138 `4340`, `c161` / `c160`. B138 shifts DLC-new symbols by 480.
   * The rule `pc_max - xs_max` = 16828 - 16347 = 481 (`PC_SYM_MAX = 16828`, "largest PC symbol seen anywhere");
     the highest PC symbol in our map is 16799, so 16828 itself is not used by a mapped symbol. To match the played
     B138, `dlc_generic.DlcIds` now has `DLC_SYM_SHIFT = 480` (measured; `None` restores the rule). Only Convert
     uses `sym()`, so the rerun starts at Convert.
   * Smaller remaining deltas (+83, -39939, -334, -337, -1, -12 ...) are other id kinds, to look at after this run.
   * **Result with shift 480** (chain Convert -> Media -> Audio -> 2b fixes -> comparisons, tools called directly,
     log `logs/Manual_SymShift480_20261027_233600.log`, 23:36-00:20): **script sections identical 4 917 -> 5 899 of
     6 184 (79.5 % -> 95.4 %)**; differing script words 9 580 in 86 DRMs -> **2 593 in 49 DRMs**; +1 deltas in the
     DLC-new symbol range 8 006 -> 0; fully identical DRMs 10 -> 11 (`vm_mods_expected` 9 -> 10). `analog` fix still
     33/33 = B138. Other section types unchanged.
   * Remaining differing u16 halves (2 570): +83 504, -39939 432 (ours = a `40000 + xs` collision value where B138
     has a small symbol), +1 312 (mostly `0229` / `0228` - a base-range symbol, not the DLC shift), -334 192,
     -337 144, -1 94, -12 92, -338 72, -329 60, +38667 56. Next step of the script analysis.
30. **The remaining 2 593 script words (after findings 27/29) fall into two groups** (`script_diff.py`, now also
   listing the Xbox u16 behind the most frequent differing pairs):
   * **Xbox half = 0, PC value non-zero** - not derived from the Xbox word but a PC-side field filled while
     assembling: ours 553 / B138 552 (312 halves), ours 552 / B138 553 (73), ours 5829 / B138 5841 (92), ours 44441 /
     B138 5823 (51), ours 4075 / B138 4022 (29), ours 1205 / B138 41178 (24). Probably counters or ids assigned to
     DLC-new scripts/types in a different order - to trace in `dlc_generic.py` (script routes `pc_copy` / `template`
     / `convert`).
   * **Collisions in ours where B138 has a mapping** - e.g. Xbox 4479: ours 44479 (= 40000 + 4479, guess collided),
     B138 5812; Xbox 4710: ours 44710, B138 6038; Xbox 4709: ours 6160, B138 6037; Xbox 4447: ours 5841, B138 5827;
     Xbox 515: ours 517, B138 333; Xbox 1974: ours 2035, B138 1952. The author's learned symbol map knew entries ours
     lacks (7 498 entries here; his count unknown). Candidates: `script_name_match.py` (adds symbols from matched
     script names) and the harvest/bootstrap rounds of `generic_symbols.py`. A B138-derived check is possible: every
     (Xbox, B138) pair of this list is a known mapping.
31. **The 30 files from the author's test VM (`vm_mods_expected`), after findings 27/29** (`tools/rebuild_status.py
   stage2b --detail vm_mods_expected`, new option): 10 fully identical (the `_map` DRMs and `co_lights`), 10 differ
   only in shader / material / mesh sections (stage 3), 9 effect DRMs differ in **exactly one script word** plus
   render sections, 1 (`dlc_watertunnel_map`) in one type-13 section.
   * The one script word is at +0x68 (once +0xa8) of the DRM's DLC-new script (ids 20357, 21263, 21411, 23524,
     23764, 24021, 24073, 24114, 24248; 20590 at +0xa8) and has only two value pairs: ours 4075 / B138 4022
     (`0feb` / `0fb6`, 7 files) and ours 5829 / B138 5841 (`16c5` / `16d1`, 3 files).
     ~~Most likely the script's super-class reference (a PC script id)~~ ~~So the word is a DTP reference that is 0 on
     the Xbox and filled on PC from a base-game script used as template~~ - **both wrong, see finding 33**: the Xbox
     word is not 0 (the "Xbox half = 0" reading came from comparing the wrong half) and the word is a Symbol.
     (Kept for the record: there is no PC script with id 4022/4075/5829/5841; 4022 and 5841 happen to be PC DTP ids
     too - a coincidence.) The trace plan below (post-passes) is obsolete: finding 32 showed the word does not
     come from a post-pass.
33. **The remaining script words are mostly unmapped Xbox Symbols guessed from the wrong neighbour.**
   * The +0x68 word of finding 31 is Xbox `0f10 0000` / `1161 0000` (BE): Symbol 3856 / 4449 in the first u16. Both
     are **not in our symbol map**. `dlc_generic.DlcIds.sym()` guesses from the lower mapped neighbour
     (3855 -> 4074 gives 4075; 4448 -> 5828 gives 5829); B138 has the value from the **upper** neighbour
     (3857 -> 4023 gives 4022; 4450 -> 5842 gives 5841).
   * `tools/symbol_guess_check.py stage2b` (new, read-only; every differing script half whose Xbox u16 is an
     unmapped base-range Symbol): 2 842 halves, 172 distinct Xbox values. B138 = upper-neighbour guess in 545 halves
     (493 where ours = lower guess, 52 where ours collided to 40000 + xs); 2 142 halves have another B138 value; 155
     collide in ours and match neither guess in B138.
   * Per Xbox value, B138 uses **one** value everywhere for all 172 (0 with several values); 168 of those values are
     free in our map, but only 19 lie between the two mapped neighbours. So either many of these words are not
     Symbol fields (only in the Symbol range by chance), or the author's symbol map was larger / not monotone there.
     Candidate list: `work/rebuild/symbol_candidates_stage2b.json` (`--write`).
   * Not applied to the pipeline: taking values from B138 is calibration; for real Symbols it would also help DLC 2
     (one Symbol space), for non-Symbol words it would be wrong. Next: an experiment run with these candidates as
     extra map entries, measured separately (finding 35).
34. **Upstream's full stage-1 route (`assemble_dlc`, material 'dlc') on the rebuilt render tables.**
   * `tools/dlc_assemble_build.py work/rebuild/stage1/mods work/rebuild/asm_stage1/mods` (new; same calls as
     `convert_dlc.py` / the author's `work/ws/rebuild/convert_fresh.py`, non-DRM files taken from the stage-1 tree),
     then Audio, the five 2b fixes and the comparisons into `asm_stage2a` / `asm_stage2b` (log
     `logs/Manual_Assemble_20261029_030905.log`): **134 of 134 pack10 DRMs, 0 errors**, 2 164 s.
   * Against B138 (stage2b = our previous route -> asm_stage2b): **shader libs 0 % -> 97.7 %** (2 238 of 2 291;
     the route puts the PC shader sections in place of the Xbox ones), **materials 83.2 % -> 90.4 %** (1 311 of
     1 450), meshes unchanged 31.7 %, all other types unchanged (DTP 98.7 %, script 95.4 %, type 0 95.8 %,
     wave 86.5 %); fully identical DRMs 11 -> 13 (`vm_mods_expected` 11, one `derived:B90_gold`, one `derived:B45`);
     files MD5-identical still 92 of 275.
   * Measurement artefact found and fixed: `script_diff.py` first reported only 24 differing script words for
     `asm_stage2b`. `dtp_audit.section_pairs` pairs sections by index only when the whole layout matches the Xbox
     DRM, else only DTPs - the assemble route changes the shader sections, so the scripts were not paired at all.
     `script_diff.py` now pairs the Script sections by their order when the counts agree: 2 581 in both trees.
   * So the assemble route is the better stage 1: same data results, real shaders and better materials. Meshes
     (type 12) are the largest open render type next to the remaining materials.
35. **Experiment: the 168 Symbol candidates of finding 33 as extra map entries** (environment variable
   `TRUDLC_SYM_EXTRA`, default off; assemble route into `work/rebuild/exp_sym_*`, log
   `logs/Manual_SymExtra-exp_20261029_035718.log`; regression check with the new `tools/script_diff_compare.py`).
   * Run 1 (candidates inserted into the symbol map): script sections 95.4 % -> 99.1 %, differing script words
     2 581 -> 157, fully identical DRMs 13 -> 15, all other types unchanged, `analog` 33/33. But the regression check
     shows **2 510 words fixed, 71 left, 86 NEW differences** (words that were = B138 before). Cause: as map
     entries the candidates also became neighbours for guessing *other* unmapped symbols and shifted those guesses
     (e.g. script 72 +0x3ba0 in nine DRMs: Xbox 0x0185, B138 0x0187 = the old guess, now 0x0293). Pruning the
     candidates whose own Xbox value appears in a new difference removes only 1 of 168 - confirms the cause.
   * Caution on the method: the candidates come from B138 itself, so "fixed" words are partly circular; the
     regression count is the meaningful number. The first comparison of this run reported "24 -> 157" - the base
     report was stale (a `| head -1` had killed `script_diff.py` before it saved its report).
   * Run 2: candidates used for exact lookups only (`DlcIds.sym_extra`, not neighbours; log
     `logs/Manual_SymExtra-exp2_20261029_044532.log`): script sections **99.2 %** = B138 (6 137 of 6 184), differing
     script words 2 581 -> **95**; regression check: 2 498 fixed, 83 left, **12 new**; fully identical DRMs 13 -> 15;
     other types unchanged, `analog` 33/33. The 12 new differences are one word in 12 unit DRMs (script +0xe80 of
     22899 / 22901 / 22902 / 24261 / 24363 / 24710 / 26109 / 26178 / 26179): Xbox 0x050a, ours 0x1437 (the candidate
     value), B138 0x0527 - so Xbox 1290 is a Symbol in one field and something else here; that candidate must go.
   * Open decision (not applied): taking Symbol values from B138 is calibration on the finished build; it is only
     useful for DLC 2 if these are real Symbols (one Symbol space for the whole game). Run 3 = run 2 without the
     candidates that cause new differences (`script_diff_compare.py --prune`).
   * Run 3: 167 candidates (`work/rebuild/symbol_candidates_pruned2.json`, the one for Xbox 1290 dropped), exact-only
     (log `logs/Manual_SymExtra-exp3_20261029_062211.log`): script sections **99.2 %** = B138, differing script words
     2 581 -> **95**, regression check **2 486 fixed, 95 left, 0 new**; fully identical DRMs 15; other types
     unchanged, `analog` 33/33. So 167 Symbol values from B138 explain 96 % of the remaining script differences
     without breaking anything else.
   * **Adopted 2026-10-29:** the 167 values are `docs/data/b138_symbol_calibration.json` and `dlc_generic.DlcIds`
     loads them by default (exact lookups only; `TRUDLC_SYM_EXTRA` = another file or `off`). They are global
     Symbols, so DLC 2 uses them too.
   * Pipeline rerun with the calibration (Convert, Media, Audio, Assemble through `Invoke-TruPipeline.ps1`, then the
     2b fixes and comparisons, log `logs/Manual_2b-compare_20261029_095957.log`): Convert symbol stats `extra` 8 729,
     `guess_collision_new` 1 219 -> 100; **script sections 99.2 %** in both trees, 95 differing words; assemble tree
     (asm_stage2b): shader libs 97.7 %, materials 90.4 %, **15 DRMs fully identical**, `analog` 33/33 = B138 -
     the same as experiment run 3.
32. **Our Convert ran without upstream's DLC post-passes (`extra_fixes`).**
   * `dlc_generic.convert_drm(..., extra_fixes=False)` is the default; `assemble_dlc.assemble()` passes
     `extra_fixes=(material == 'dlc')`, `dlc_convert_all.py` passed nothing. Gated by it (`dlc_generic.py`): model
     'point' arrays (`model_point_fix`), DTP id lists / align (`dtp_align_fix`), SoundPlex float/u32 fields, script
     SArray counts, tag-0x403 object-id records, cell portal words, uberobject graph descriptors, link-joint ratios,
     and the analog id-coincidence guard (`analog_idcoin`). So finding 24's "these run inside Convert" was wrong for
     most of them (corrected there).
   * New option `dlc_convert_all.py --extra-fixes`. First test on `dlc_fx_haze.drm` failed: `model_point_fix` needs
     `work/chain_aim/model_point_rules.pkl` (not in the repository). Generated with `tools/model_point_fix.py learn`:
     1055 base model pairs, 38 rules, 2-fold held-out 0 words changed; `selftest` on the real PC bytes of all base
     pairs: 0 words changed - exactly upstream's numbers (log `logs/Manual_ModelPointRules_20261028_002755.log`).
     `work/chain_aim/` added to `.gitignore` (derived from game data).
   * Retest with the rules: exit 0, no error. The script word of finding 31 (+0x68 of script 24073) stays 4075 - it
     comes from the learned script table (route `convert`, `script_learn.py save` in Tables), not from a post-pass.
   * Step Convert in `Invoke-TruPipeline.ps1` now passes `--extra-fixes`.
   * First full run stopped at the second missing input: `dtpid_sweep.classify` needs
     `work/generic/dtpid_evidence.pkl` (not in the repository) - generated with `tools/dtpid_evidence.py` (base-pair
     evidence; "rule precision on base pairs: 418 707 words, 405 577 remapped, 96.86 %, 4 319 values", 10 s).
   * **Full run with extra fixes** (log `logs/Manual_ExtraFixes-full_20261028_003451.log`, Convert 42 min,
     readback 307/307, `reloc_bounds_bad` 0; then Media, Audio, the five 2b fixes, comparisons): DTP sections
     identical 11 157 -> **11 274 (98.7 %)**, type 0 246 -> 248 (95.8 %), other types unchanged; differing script
     words 2 593 -> 2 581; `analog` fix still 33/33 = B138; files MD5-identical still 92 of 275, DRMs fully
     identical still 11.
   * DLC 2 note: run `model_point_fix.py learn` and `dtpid_evidence.py` before converting with extra fixes (both
     learn from base pairs only).
   * Since 2026-10-29 both are tools of step Prep (`model_point_fix.py learn`, `model_point_fix.py selftest` - aborts
     the step if a rule changes a real PC word - and `dtpid_evidence.py`), so a fresh run needs no manual step.
36. **Convert and the assemble route are single-process - and one process needs a lot of memory.**
   * Why a Convert run takes 42-80 min (2026-10-29, measured while it ran): `python` used ~1.3 of 36 logical
     CPUs, total CPU load 5 %, disks idle, 41 of 64 GB RAM free. `dlc_convert_all.py` (and `dlc_assemble_build.py`)
     convert the DRMs one after another in one process, so the run time follows the speed of one core and
     whatever else runs on the PC.
   * `dlc_convert_all.py --jobs N` (new, default 1 = unchanged): tasks per pack record, each process loads the
     store, the id map and the learned tables once; a file written by two records (7 duplicate records) is written
     only by its last record, as the sequential version did by overwriting.
   * **First test failed on memory:** one converting process holds **11-15 GB private memory** (the sequential
     Convert 18 GB), not the 2-3 GB its working set suggested. 6 processes next to a running Convert used all 64 GB
     (free RAM 0, paging). Test stopped; the orphaned worker processes had to be ended by hand. Rule: at most
     (free RAM / 15 GB) processes, i.e. **3 on a 64 GB PC with nothing else running**; never next to another Convert.
     (First estimate; the measured rule below is (free RAM - 8 GB) / 18 GB.)
   * Still to do: equivalence test (1 process vs N processes must give byte-identical files), then the same for
     `dlc_assemble_build.py`.
   * **Measured** (`scripts/windows/Measure-TruProcessMemory.ps1`, new, read-only, 10 s samples during the rerun
     Convert..2b of 2026-10-29; peak private memory of one process):

     | Tool | Peak per process | Processes |
     |---|---|---|
     | `dlc_convert_all.py` (Convert) | **18.2 GB** | 1 |
     | `dlc_assemble_build.py` (Assemble) | **15.6 GB** | 1 |
     | `dlc_fixes_build.py` (2b) | 2.8 GB | 1 |
     | `dlc_media_build.py`, `rend_extract.py`, `terrain_validate.py` | ~1.4 GB | 1 (+ 8 rend_extract workers up to 1.3 GB each) |
     | `shader_map.py` | 0.25 GB | 1 |
     | `dlc_audio_build.py`, `compare_*.py`, `script_diff.py` | < 20 MB | up to 36 |

     Pool workers show up as "(no script)" in the sampler (their command line does not name the tool).
     Consequence for a shared limit: light tools may keep many processes (cap ~24 to leave cores for the user);
     Convert / Assemble at most floor(free RAM / 18 GB) - on this 64 GB PC 2, with nothing else running 3.
   * **Equivalence test passed:** `dlc_convert_all.py --jobs 2` (free RAM stayed > 4 GB, watched every 30 s) wrote
     the same **300 of 300 files byte for byte** as the sequential run (`tools/tree_compare.py`, new), same symbol
     and route statistics; **2 824 s instead of 4 683 s**.
   * Settings now: `Invoke-TruPipeline.ps1 -Jobs N -LightJobs N` (0 = automatic: Jobs = (free RAM - 8 GB) / 18 GB
     between 1 and 3, LightJobs = logical CPUs - 4, at most 24), passed as `TRUDLC_JOBS` / `TRUDLC_JOBS_LIGHT`;
     read by `dlc_convert_all.py`, `dlc_assemble_build.py` (heavy) and `dlc_audio_build.py`, `compare_sections.py`,
     `compare_audio.py`, `script_diff.py` (light; unset = all CPUs as before). Upstream's `rend_extract.py` /
     `generic_cache.py` keep their fixed 8 processes.
   * `dlc_assemble_build.py` got the same `--jobs` (per-DRM tasks, report rows in task order). Equivalence test
     with 2 processes (~15.3 GB each, free RAM stayed > 17 GB): **271 of 271 files of the tree byte-identical** to
     the sequential `asm_stage1`, 134/134 DRMs, **1 439 s instead of 2 266 s** (log
     `logs/Manual_ParallelAssemble-test_20261029_111058.log`).
   * Note on the memory sampler: run it with an outer timeout longer than `-DurationMinutes`; the first run was
     cut by an equal timeout right before its summary (the CSV with all samples is complete).
   * Where step Assemble spends its time besides `dlc_assemble_build`: `terrain_validate.py` ran 596 s on one core
     (learning its table takes seconds, the check of 335 terrain pairs the rest). The pair checks now run in
     `TRUDLC_JOBS_LIGHT` processes with results merged in order: **72 s instead of 596 s**, `terrain_validate.txt`
     and `terrain_yhash.pkl` byte-identical to the sequential run (16 processes; log
     `logs/Manual_TerrainParallel-test_20261029_135232.log`). `mesh_tables_build.py` (finding 37) takes 34 s and
     stays sequential (an estimate of several minutes was wrong).
37. **Meshes: two learnt tables of `mesh_convert.py` were missing - one rule (each Xbox mesh counted once) makes
    them match B138.**
   * Where the meshes differ (`tools/mesh_diff.py`, new, read-only: type-12 sections paired by (type, id), parsed
     with `mesh_convert.parse`, compared region by region): on the assemble tree with symbol calibration
     (2026-10-29) Mesh 31.7 % identical; all 153 differing same-size meshes differ in the vertex declaration, 120 of
     them also in the vertex data - nothing else (header, bone map, mesh info, palettes, faces, groups, lists, tail,
     relocations all equal). The declarations had the same elements and differed only in their 8-byte hash; the
     vertex data by +-1 in the bytes of NORMAL / TANGENT / BINORMAL.
   * Cause: `mesh_convert.pc_decl_hash()` reads `work/render/pc_vdecl_hash.pkl` and `dec3n_lut()` reads
     `work/render/dec3n_lut.pkl`; neither file is in the repository and **no tool writes them**. Without them the
     converter uses a synthetic md5 hash and the formula `trunc(127.5 + s/4)` ("89 % agreement" in its docstring).
   * `tools/mesh_tables_build.py` (new) learns both from the base pairs (`work/render/pairs_render.pkl`; Mesh
     sections paired by position as `mesh_validate.py` does): the hash of every PC vertex format (18 formats, no
     format with two hashes), and for DEC3N (Xbox type 0x11 -> PC UBYTE4N type 5 at the same offset, batches with
     the same vertex count) the majority PC byte of each of the 1 024 10-bit values (1 value never seen: formula).
   * First version counted every pair (15.3 M components, majority agreement 95.5 %): vertex declarations 153 -> 0
     differences, Mesh 31.7 % -> **73.1 %**; 59 meshes still differed in vertex data only.
   * `tools/dec3n_check.py` (new, read-only) pairs the Xbox DLC meshes (`dlc_render.pkl`, ids mapped with
     `DlcIds`) with the B138 tree: B138 maps every DEC3N value to exactly one byte (1 023 values seen, none
     ambiguous) and differs from our table in only **3 values** (242, -254, -242), each a near tie in the base
     votes (e.g. 5 089 : 4 913). `--variants` tries subsets of the base votes (semantics, components, same-size
     pairs, first pair per Xbox id): **counting each Xbox mesh id once (its first pair) gives 0 differing values**
     (11.65 M components); every other subset gives 1 or more. That is the rule `mesh_validate.py` already uses
     ("unique Xbox ids"), so it is a rule, not values copied from B138. Upstream's docstring says "8.2M base-pair
     components" - our count is 11.65 M; the difference is not explained (perhaps a smaller pair set), but the
     resulting table matches B138 on every value the DLC uses.
   * Pitfall on the way: the first `dec3n_check` run paired nothing - the B138 Mesh sections carry the magic as
     `Mesh` or `hseM` and DLC ids are remapped on PC; check the printed section counts before reading results.
   * `mesh_tables_build.py` is now a tool of pipeline step Assemble (after `terrain_validate.py`).
   * Note (code review): the "first pair" rule counts an Xbox id after a successful parse and a non-empty check,
     while `mesh_validate.py` marks ids as seen before; with B138 as the judge our variant gives 0 differing values,
     so it stays.
   * **Result with the final tables** (step Assemble through `Invoke-TruPipeline.ps1`, then 2b and the comparisons;
     log `logs/Manual_MeshTables2-assemble_20261029_131838.log`): `dlc_assemble_build` 134/134 DRMs OK (1 320 s,
     2 processes); **all 174 Mesh sections byte-identical to B138** (`mesh_diff.py`: no differing region; the 2
     remaining type-12 differences are terrain sections); type 12 overall 31.7 % -> **99.1 %** (225 of 227); other
     section types unchanged (script 99.2 %, DTP 98.7 %, shader 97.7 %, material 90.4 %); **DRMs fully identical
     15 -> 46 of 133** (`rebuild_status.py asm_stage2b`: e.g. 29 of 30 `vm_mods_expected` files, 11 of 11
     `mods_fix18_awf_extra`); files MD5-identical still 92 of 275 (the DRMs that changed still differ elsewhere).
   * `mesh_dlc.py` (upstream) with the tables: all 285 DLC meshes of both packs valid, geometry equal to the Xbox
     source, 1 mesh (DLC 2) with a vertex format unknown on PC - see `docs/DLC2.md`.
   * DLC 2 note: the tables are learnt from the base game only, so they apply to DLC 2 unchanged.
38. **Ten DRM names exist in pack10 and pack11 with different content - lookups by name took the pack10 one.**
   * `tools/pack_overlap.py` (new, read-only): 10 names are in both DLC packs, none byte-identical - each DLC was sold
     separately and ships its own copy of shared files. `--sections` (Xbox sections, pack10 vs pack11):

     | Files | pack10 -> pack11 | Reading |
     |---|---|---|
     | `co_dlc_earphonecam`, `co_dlc_eitr_stone`, `co_dlc_knight_thrall`, `co_dlc_knight_thrall_pieces`, `co_lights` | only script 56 changed (same size); knight_thrall also DTP 21046 | pack11 carries a newer version of the same object |
     | `g_pda` | 0 sections only in pack10, 5 only in pack11, 27 changed (mission list with DLC 1 and DLC 2) | pack11 is a superset |
     | `dlc_fx_goo_dun_ist`, `dlc_fx_goo_tres_ist`, `dlc_fx_goo_tres_line_ist`, `dlc_fx_cine_thrall_death` | effect DTPs re-authored; pack10 has texture 2824 (goo) / a type-2 section (thrall death) that pack11 lacks | not a superset |

   * The conversion itself is not affected (`dlc_media_build` and `dlc_assemble_build` read the record of their own
     pack). But every tool that looks up "the Xbox source" of a file by name goes through upstream's
     `convert_dlc.raw_dlc()`, which returns the first pack (pack10): `wave_swap` (audio step) and all stage-2b fixes
     except `cine` (which reads pack10 only). In the first DLC 2 audio run the waves of `g_pda` and the three goo
     effects were taken from the pack10 records. Upstream knew of one case: `engine_walk_check.py` has
     `XBOX_PACK = {('dlc2', 'g_pda.drm'): 'pack11'}`.
   * Fix: `convert_dlc.raw_dlc()` honours `TRUDLC_PACK_FIRST` (the named pack is searched first; unset = upstream
     order); `dlc_audio_build.py` and `dlc_fixes_build.py` take `--pack pack11` and set it for their workers;
     `fix_cine` now processes every `cinstream/*.drm` of the tree and reads its Xbox source from that pack. DLC 1 is
     unchanged (pack10 is first anyway) - checked: stage 2b rebuilt from `asm_stage2a` = the previous `asm_stage2b`,
     **271 of 271 files byte-identical** (`tree_compare.py`). DLC 2 audio rebuilt with `--pack pack11`: **293 of 293
     files identical** to the first run - the wave data of the four affected files is the same in both packs, so that
     lookup did no harm; the fix matters for the stage-2b fixes (log `logs/Manual_DLC2-fixes_20261029_154941.log`).
   * Open for installing both DLCs: the PC `mods/` folder can hold only one file per name. Only DLC 1 -> pack10
     versions, only DLC 2 -> pack11 versions, both -> most likely the pack11 versions (newer; `g_pda` is a superset),
     but the goo effects are not a superset, and which copy the Xbox loads when both packages are installed is not
     known yet. Test in Xenia/in game before the installer offers "both".
39. **`float_fix` would have damaged the DLC 2 doppelganger models - they are Lara-type character models.**
   * First DLC 2 stage 2b: `float` changed 16 243 words, 16 105 of them in DTP 22493 of `doppelganger_casual.drm` and
     DTP 25050 of `lara_doppelganger.drm` (DLC 1: 60 words). New read-only tools to check it without a reference:
     `tools/dtp_word_classes.py` (how a PC DTP encodes each word of its Xbox source: s32 / s16 / raw / same) and
     `tools/dtp_format_scan.py` (all DTPs of one header format in the Xbox base game and the packs).
   * The two DTPs have header `04c20453` and relocated array pointers at +0x24 and +0x34, like the character-model
     DTPs of every Lara costume of the base game (`lara.drm` 535 252 bytes, `lara_bikini.drm`, the wetsuits, ...)
     and of the DLC costume files. Their PC versions are almost entirely 16-bit data:

     | DTP | s32 | s16 |
     |---|---|---|
     | base `lara.drm` 12649 vs PC | 2.5 % | 96.8 % |
     | base `lara_bikini.drm` 12601 vs PC | 2.5 % | 96.9 % |
     | DLC 1 `dlc_costume_o.drm` 21090 vs B138 | 2.5 % | 96.8 % |
     | DLC 2 `doppelganger_casual.drm` 22493, our conversion | 3.1 % | 96.1 % |
     | the same after upstream's `float_fix` | 12.5 % | 86.7 % |

     The converter was right; `float_fix` turned 16-bit pairs that look like floats into s32. Upstream avoids this by
     name: `float_fix.py` skips files with 'costume' in the name - the doppelganger models have no such name. The
     changes also cascaded: the fix checks the neighbours in the buffer it is changing, so each fixed word vouched
     for the next (all 10 136 changes of DTP 22493 lie in its 16-bit array at 0x322ec-0x6947c).
   * Three attempts, each checked against B138 on DLC 1 (dead ends kept on purpose):
     1. neighbours from the unmodified DTP (no cascade): DLC 1 lost 11 correct changes (`dlc_dungeon.drm` float
        pairs/triples need the cascade) - rejected;
     2. skip every DTP with header `04c20453`: DLC 1 lost 11 correct changes (`dlc1_uo_water_wheel` 8,
        `dlc1_uo_pillory` 3) - this header is a general DTP header (1 484 DTPs, `dtp_format_scan.py`) - rejected;
     3. **skip DTPs with header `04c20453` AND array pointers at +0x24 and +0x34** (character models only; the small
        object DTPs and `co_doppelganger` / DLC 1 `doppelganger` have neither): DLC 1 stage 2b **271 of 271 files
        byte-identical, float 60 = B138**; DLC 2 float 138 words in 17 files, the doppelganger DTPs keep the
        base-game pattern (96.1 / 96.2 % s16). Applied in `work/ws/cine/float_fix.py` (one marked condition).
   * DLC 2 note: any rule that worked on DLC 1 can meet data DLC 1 does not have - check its changes against the
     closest base-game structure (here `lara.drm`) before trusting a large count.
40. **`g_pda.drm` (PDA): merge the DLC sections into the PC version instead of replacing it.**
   * Every DLC pack ships a complete replacement `g_pda.drm`; the PC game has its own in `patch.000`. Upstream leaves
     `g_pda` out of the DLC 1 kit (B138 has none) - our DLC 1 tree still contains it (the one "extra" file of
     `compare_b138`), to be dropped there the same way.
   * `tools/gpda_compare.py` (new, read-only), sections against the Xbox base `g_pda`: Xbox base 425, PC base 426;
     pack10 366 unchanged / 53 changed / 4 new; **pack11 373 unchanged / 46 changed (28 scripts, 13 textures, 5 DTPs)
     / 9 new (4 scripts, 4 textures, 1 DTP)**; 6 base sections are not in pack11. Of the 373 unchanged sections our
     conversion already gives the PC bytes for 347; the other 26 are 17 textures, 8 waves, 1 mesh (converter
     differences, no scripts or DTPs).
   * `tools/drm_merge_pc.py` (new): start from the converted pack11 file; unchanged base sections take the PC section
     (data + relocations); changed and new sections stay converted; PC sections the converted file lacks (PC-only and
     the 6 dropped ones) are appended. First attempt: 23 sections with out-of-bounds relocations - **external
     relocations address sections by their index in the file**, so the relocations of every section taken from the PC
     file are remapped (PC index -> (type, id) -> index in the merged file). Result `work/rebuild/dlc2_merge/g_pda.drm`:
     435 sections, read back, 0 out-of-bounds relocations, all 373 unchanged sections = PC bytes (50 taken from the
     PC file, 24 relocation lists remapped, 7 sections appended).
   * Open: test in game (PDA journal lists DLC 1 + DLC 2, DLC 2 control pages); which `g_pda` to install when only DLC 1
     or both are installed (finding 38).
   * **Not safe as built (2026-10-29 22:40, test 12): a NEW BASE GAME crashed** after the opening (explosion and text
     shown) at `tru.exe` +0xca260 - the `cdc::UIMenuWdgt` null-list crash of finding 43, its "count" field holding a
     pointer to glyph-string init data next to the strings `pda_bg_1280` / `pda_bg_960`, i.e. a PDA script. The merged
     file replaces **12 PC scripts** with their converted DLC versions (3347, 3360-3362, 3365, 3367, 3368, 213, 3248,
     66, 3257, 3384) and adds 4 (26427, 26428, 24318, 90). Those converted base scripts have every problem script 6
     had (finding 43): member init blocks in Xbox byte order and the Xbox layout of struct 351, Xbox glyph codes,
     and **vtables one slot short** (3347: 55 vs PC 57, 3360: 40 vs 41, 3361: 49 vs 50, 3362: 37 vs 38, 3365, 3368,
     3384: -1; they inherit from script 93, which has the PC-only slot 31); 3367, 213 and 66 also have more functions
     than the PC version (DLC additions). In the DLC 2 level (tests 1, 5a-5f) the PDA was not opened, so it did not
     show.
   * Consequence: the merged `g_pda` needs the same port as script 6 (vtable slot, init from PC, struct re-layout,
     names, call offsets) per replaced script, with extra care where the DLC version adds functions (vtable slots by
     name). Until then test trees use the PC `g_pda` (test tree 13: `dlc_finish_build.py --drop g_pda.drm`).
41. **The DLC mission screen has six slots; DLC 1 is level 1, DLC 2 is level 2 - an entry most likely appears when
    its start file exists.**
   * `generalbank.drm` script PC id 104 (the mission screen, `docs/DLC_MENU.md`) names `dlc_level1_start.drm` ..
     `dlc_level6_start.drm` and `dlc_level1_preview` .. `dlc_level6_preview` (`tools/drm_strings.py`).
   * DLC 1 ships `dlc_level1_start.drm`, DLC 2 `dlc_level2_start.drm` (+ `_map`). The installed B138 tree has
     `dlc_level1_start` only but the preview images of levels 1 and 2 (and the DLC 2 control pages) - and the PC menu
     lists only *Beneath the Ashes*. So the entry most likely depends on the start DRM, not on the image (not read
     from the script code yet - an in-game test decides).
   * The menu item itself ("Downloadable content" in the main menu) is the `generalbank.drm` patch of the B138 kit
     (`tools/menu_dlc_patch.py`, variant B); it is not pack-specific, so DLC 2 should not need another menu patch.
   * `tools/dlc_finish_build.py` (new) finishes a tree for testing: copy a stage-2b tree, replace/drop files (merged
     `g_pda`), string tables (`locals.py build`: one table for both DLCs, from the title update) and padshock, then
     `tree_check.py`. DLC 2: `work/rebuild/dlc2_test/mods`, 166 DRMs, 0 out-of-bounds relocations.
   * Confirmed in game (2026-10-29, `docs/DLC2.md`): *Lara's Shadow* appears as the second entry.
42. **The DLC mission flow lives in title-update scripts of `generalbank.drm` that the PC game does not have.**
   * First in-game test of DLC 2 (`docs/DLC2.md`): loading screen without the DLC image and text, Lara's costume and
     weapon choice instead of the doppelganger, no intro cutscene.
   * `tools/tu_script_changes.py` (new, read-only; and `drm_strings.py xbox:NAME`): the Xbox title update (TU) changed
     48 scripts of `generalbank.drm` and added 2; the PC version keeps the retail state for nearly all of them:

     | Xbox script | retail -> TU (bytes) | PC | strings in the TU script |
     |---|---|---|---|
     | 6 (loading screen, "uiloading") | 66 660 -> 75 124 | 66 900 (retail + PC changes) | "Loading DLC 1 background render image", "Loading DLC 2 background render image", **"DLC CINE: About to broadcast message from loading screen"** |
     | 21239 (new in the TU) | - -> 297 | missing | "dlc2data" |
     | 7 (pause / main menu ring) | 186 784 -> 195 744 | own PC version (+ B138 menu patch) | "DLC", LoadMenu entries |
     | 38 | 75 908 -> 81 732 | retail | golden shotgun (upstream: "needs title-update scripts the PC exe lacks") |
     | 134 (mission screen) | 20 068 -> 20 900 | retail (`docs/DLC_MENU.md`) | `dlc_level1/2_start` |
     | 10, 110, 40, 255, 66, 39, 211, ... | grown | retail | - |

   * Reading: the loading screen script chooses the DLC background and **triggers the DLC intro cutscene** - both
     missing on PC because script 6 is the retail one. The costume choice / doppelganger part is not located yet
     (candidates: 21239 "dlc2data", the grown scripts without strings).
   * What the Xbox title update consists of (`TitleUpdate.000`, 12 records, 1.9 MB, plus the exe patch
     `default.xexp`, 0.96 MB) and where the PC stands:

     | TU part | What it adds | On PC (B138 kit + this branch) |
     |---|---|---|
     | `generalbank.drm` | 48 scripts changed + 2 new, 65 textures, 11 DTPs: mission screen, loading screen with DLC background and intro trigger, golden shotgun, pause menu, "dlc2data" | partly: menu item + mission screen (B138 patch, our text style fix); loading screen, intro trigger, "dlc2data", golden shotgun missing |
     | `local/locals.bin` x 6 languages | 1 284 -> 1 407 strings: real DLC names/descriptions instead of retail placeholders ("DLC TEST MISSION 2", "Extra Costume 1"), hint texts | merged into the PC tables (`tools/locals.py`) |
     | `tr8/objectlist.txt`, `objlist.dat`, `unitlist.txt` | registers DLC objects and level units | merged (`work/generic/merged/tr8`, in B138) |
     | `globalsoundinfo.drm` | 1 script + 1 sound DTP grown | in B138 |
     | `padshock/padshocklib.tfb` | 1 rumble entry (`dlc1_adren_bridge`; missing = crash) | `tools/padshock_convert.py` |
     | `default.xexp` (exe patch) | engine code - presumably mounting DLC packages and the licence check | none on PC: the mod loader replaces it; the related engine natives are stubs on PC (finding 41, `tools/menu_dlc_patch.py`) |

     The retail game - and so the PC version - already had the DLC skeleton (six mission slots, 16 costume slots,
     placeholder strings); the title update filled it in. The PC never received it.
   * Probe (`tools/base_convert_check.py`, new; whole `generalbank.drm` converted without PC copies, then compared
     per script; log `logs/Manual_BaseConvert-generalbank_20261029_181930.log`). Word-by-word at the same offset is
     misleading where the PC inserted bytes (script 6: +240), so the tool also gives an **aligned** score (difflib on
     32-bit words):

     | Xbox script -> PC | retail converted vs PC, aligned | TU converted vs PC, aligned |
     |---|---|---|
     | 6 (loading screen) | 87.0 % | 67.5 % |
     | 134 -> PC 104 (mission screen; the id map wrongly gives 134, `--pc 8:134=104`) | 92.4 % | 75.9 % |
     | 10 -> PC 9 | 96.2 % | 90.2 % |
     | 110 -> PC 122 | 91.7 % | 85.1 % |
     | 40 -> PC 39 | 93.4 % | 87.4 % |

     The converter reproduces the PC versions of base `generalbank` scripts to 87-96 % - good, but a TU script
     dropped in as converted would carry 4-13 % wrong words. Dead end for direct use; instead a **three-way merge**:
     the difference converted-retail -> converted-TU (same converter, its errors cancel out) applied to the real PC
     script, so PC-only parts and correct PC bytes stay. TU-only scripts (21239 "dlc2data" 297 bytes, 20082 196 bytes)
     have no PC version and must come from the conversion.
   * Where converted retail script 6 and PC script 6 differ (difflib on words, scratch analysis): 14 554 words equal,
     ~1 400 small same-length replacements, only ~90 small insertions/deletions (mostly 3 words); **1 217 replaced
     words differ by exactly +3**, others by +2, +22, -257 - a systematic value offset (likely Symbol ids, cf. the +480
     shift of finding 29), not random errors. Internal relocations: retail-converted 1 630, PC 1 631, TU-converted 1 806.
   * Value-map test (scratch, leave-one-out): learn "converter value -> PC value" (only values that always map to
     the same other value, relocation pointers excluded) from the other scripts and apply it to one retail script:

     | Script -> PC | aligned before | after (map from the other scripts) |
     |---|---|---|
     | 6 | 87.0 % | 87.9 % |
     | 134 -> 104 | 92.4 % | 94.8 % |
     | 9 | 96.2 % | 97.0 % |
     | 122 | 91.7 % | 95.2 % |
     | 39 | 93.4 % | 95.5 % |

     The map generalises (every script improves without having been used to learn it), but it is only part of the
     answer (+1 to +3.5 points); script 6 gains least because most of its differing values occur only in it. The rest
     are structural (small PC insertions, shifted pointers). Next: find what the +3 values are (which field / symbol
     range), so the converter itself can be corrected instead of patching its output.
   * The +3 words are **not converter errors** (scratch analysis of script 6): all 1 217 are passed through unchanged
     (Xbox word = converted word), small and consecutive (0x25d, 0x25e, 0x25f, ... at a 4-16-byte stride) - running
     indices into a table; on PC every one is 3 higher, consistent with the PC script having **three more entries**
     in that table before them (the small 3-word PC insertions). Only 45 of the values are in the learned symbol map,
     so they are not Symbol ids. Consequence: a converted Xbox script is internally consistent in Xbox numbering;
     mixing it word by word with the PC script would need renumbering. For a first test, the converted TU script is
     used **as a whole** (losing the PC's own small additions to script 6, purpose not known yet).
43. **The title-update loading screen calls an engine function that only the Xbox title update's exe patch has.**
   * DLC 2 test 2 (converted TU script 6 in the PC `generalbank`) froze and crashed before the loading screen (jump to
     address 2, `docs/DLC2.md`). Cause 1: of the 1 020 external relocations of script 6, 213 point into scripts whose
     PC version has another layout, and `drm_put_sections.py` had remapped only the target section, not the offset.
   * `drm_put_sections.py --xbox generalbank.drm` (new option) remaps those offsets with upstream's
     `script_conv.offset_map` (Xbox TU script -> PC script, functions/prototypes matched by name Symbol): **176 call
     offsets remapped, 1 unresolved**, 0 out-of-bounds relocations (`work/rebuild/dlc2_gb3/generalbank.drm`).
   * The unresolved one (scratch analysis): script 6 +0x7934 calls **function 93 of script 63 = `uigamedata`**
     (native package `game/script/ui/ui`), name Symbol 19315. Script 63 has 93 functions in the Xbox retail, **95
     in the TU** (93: Symbol 19315, 94: Symbol 19316, both new), 117 on PC (own PC additions, not these two). Both new
     functions have **no script code** (0 code words) - they are **natives**: their code is in the exe, i.e. in the
     title update's exe patch `default.xexp`, which the PC never got.
   * So the DLC branch of the loading screen needs an engine function the PC exe does not have. Options: (a) change
     the call site in script 6 - find out what native 93 returns (probably "which DLC is loading") and get that value
     another way; (b) add the native to `tru.exe` (Ghidra, exe patch) - the "program part" of the title update
     (finding 42 table). Both also matter for the later "PC loads DLC itself" idea.
   * Option (a) chosen. Disassembly of TU script 6 (`menu_dlc_probe.dis`, variants `xt`/`xl`): native 93 is called
     once, as the first statement of function 3 (`local0 = uigamedata.f93()`, then `print("*** CURRENT LEVEL = ",
     local0)`); in the retail version of function 3 `local0` is the parameter and there is no call - the TU only
     overwrites it. The DLC branches do **not** use it: the background image compares a level number from script 86
     function 22 with **101 (DLC 1) / 102 (DLC 2)**; the intro trigger compares the level name (uigamedata function 33,
     present on PC) with `"dlc_level1_start"` and then broadcasts "DLC CINE".
   * `tools/script_nop_call.py` (new) replaces the 4 call words (op04 0, op0f 1024, op65, operand) with the preceding
     debug line marker (op00) and drops their relocation - function 3 behaves like the retail one for that value.
     Result `work/rebuild/dlc2_gb4/generalbank.drm`: 176 call offsets remapped, **0 unresolved**, 0 out-of-bounds
     relocations; test tree 3 `work/rebuild/dlc2_test3/mods` (only `generalbank.drm` differs from test tree 1).
   * Note for DLC 2: the intro trigger compares with `dlc_level1_start` only in the part read so far - whether the TU
     handles `dlc_level2_start` the same way is not checked yet (the test will tell).
   * **Test 3 (2026-10-29 19:05): same freeze + crash, same signature** (Windows log: exception 0xc0000005, module
     unknown, offset 0x00000002). So the native call was not the (only) cause - kept as a ruled-out lead.
   * Next lead - script 6 layout (scratch): functions 34 / prototypes 30 / states 5 in retail, TU and PC; members
     retail 198, **TU 211**, PC 198; **vtable size retail 52, TU 52, PC 53** (one more virtual slot on PC, presumably
     a PC-only virtual function of the parent class); prototype name Symbols PC = Xbox + 2. A converted TU script 6
     with 52 vtable entries lets the engine read slot 53 beyond the table -> garbage pointer -> jump to a small
     address. The probe converted without the PC template (`template=False`); next: convert with the template
     (`base_convert_check.py --template`) and check vtable size and members.
   * With the template (`work/rebuild/base_convert/tu_tpl_generalbank.drm`, log
     `logs/Manual_BaseConvert-tpl_20261029_190612.log`): script 6 comes out the same (75 124 bytes, vtable size 52,
     211 members) - the template route does not touch this script. The vtable has to be brought to the PC layout
     another way (next: what the 53rd PC slot points to). Before that: check in game how B138 shows DLC 1's loading
     screen and intro - if the author solved it for DLC 1 without TU script 6, the same way may serve DLC 2.
   * **B138 DLC 1 in game (2026-10-29 19:13, Steam PC, game on the primary monitor, RTX 3080 Ti; the PC has a second
     GPU, a GT 1030, and 6 monitors - 4 on the RTX, 2 on the GT 1030; native Direct3D 9, no dgVoodoo2)**: the loading
     screen is the generic Croft Manor background **without DLC image and text** - the author did not solve the DLC
     loading screen either, so this work serves both DLCs. Right after it the game showed **"A problem has occurred
     with your display driver"** (twice, after the setup dialog), i.e. the case `docs/TROUBLESHOOTING.md` describes
     as "fixed in B133, not yet confirmed on a real GPU" - here it is **not** fixed on a real GPU; the author's
     suspect are the 113 pixel shaders longer than 512 instructions in DLC files. Our DLC 2 test tree did not show the
     box (other shader route; a hint, not proof). The author's `tools/native_test` (read-only, creates every shader /
     vertex layout / texture format of the installed `mods\` on the GPU) can name the failing objects.
     Open variable (not checked): two GPUs and several monitors - a Direct3D 9 game creates its device on one adapter,
     normally the one of the primary display; whether the second card plays a part in the error box is unknown. To
     rule it out: the native test, and if possible one run with only the RTX's monitors active.
   * Plan (checkable): (1) convert the Xbox **retail** script 6 with our converter and compare it with PC script 6 - if
     nearly equal, the converter can be trusted on `generalbank`; (2) convert the **TU** script 6 (and 21239, ...) and
     merge them into the PC `generalbank` with `tools/drm_merge_pc.py`; (3) test in game.
   * **vtable layout (2026-10-29 evening).** Slot-by-slot comparison of script 6 (VTE -> function index + name):
     retail and TU have 52 slots, the PC 53 - the PC **inserts one slot at 31** (a VTE with one external pointer into
     another script, i.e. inherited), and every Xbox slot from 31 on sits one higher on PC (Xbox 31 = function 6 ->
     PC 32 = function 6, ..., Xbox 51 -> PC 52). The prototypes agree: of the 30 TU prototypes, the **21 with vtIndex
     >= 31 have vtIndex + 1 on PC**, the 8 below 31 are equal, 1 has none. A converted TU script 6 therefore dispatches
     every virtual call from slot 31 on to the wrong function, and slot 52 reads past its table.
   * `tools/script_vtable_insert.py` (new): appends a new table to the converted section (old slots 0-30, the PC
     reference's slot-31 VTE copied with its external relocation, old slots 31-51), sets vtableSize 53, retargets the
     root pointer, adds 1 to prototype vtIndex >= 31. Nothing else in the section moves.
   * Checking the result against the PC showed 51 of 53 slots equal - slots 14 and 28 pointed to the right functions,
     but with other **name Symbols** (333 / 340 instead of PC 517 / 523). Cause: the learned symbol map does not know
     Xbox 515 / 521, and the B138 calibration (finding 35, learned from DLC 1 words) maps them to 333 / 340; the base
     game says 517 / 523 (same function, same slot, same code length on retail Xbox and PC).
   * `tools/sym_calibration_check.py` (new) collects that base evidence: `script_conv.offset_map` pairs the functions
     and prototypes of every script that exists on retail Xbox and PC; pairs whose Xbox name the learned map does not
     know vote Xbox -> PC Symbol. On `generalbank.drm`: **161 scripts paired, 965 name Symbols outside the learned
     map with evidence; the converter (`DlcIds.sym`) gets 747 right and 218 wrong**; the calibration agrees with the
     base on 2, **disagrees on 5** (515 -> 333 vs 517, 521 -> 340 vs 523, 986 -> 1287 vs 1005, 2047 / 2048 ->
     42047 / 42048 vs 2108 / 2109) and has no entry for 958. It writes `work/rebuild/sym_base_evidence.json`
     (calibration + base evidence, base wins).
   * Open question (recorded, not decided): the calibration was learned from B138's DLC 1 words, the evidence from
     base-game function names. Either the 5 calibration entries are wrong (B138 would then carry the same wrong
     names, harmless for DLC 1 so far) or the same Xbox Symbol means something else in DLC files. For **base-game
     scripts** (the TU `generalbank`) the base evidence is the right source. Whether the 218 wrong guesses matter for
     DLC scripts is the next check (which DLC 1 / DLC 2 scripts use those names).
   * Test tree 4: TU `generalbank` reconverted with `TRUDLC_SYM_EXTRA=work/rebuild/sym_base_evidence.json` (script 6
     aligned 67.6 % of the PC words), then the same steps as test 3 (`script_nop_call.py`, `drm_put_sections.py
     --xbox`: 176 call offsets remapped, 0 unresolved) plus `script_vtable_insert.py ... 6 31`; script 6 now has
     **53 of 53 vtable slots and all 30 prototype names and vtIndex values equal to the PC**, 0 out-of-bounds
     relocations (`work/rebuild/dlc2_gb5/generalbank.drm`, log `logs/Manual_DLC2-gb5_*.log`).
     `work/rebuild/dlc2_test4/mods`: 301 files, `tree_check` 167/167 DRMs clean; only `generalbank.drm` differs from
     test tree 3.
   * **Test 4 (2026-10-29 19:45): same crash** (0xc0000005, offset 0x00000002).
   * Forgotten jump point: `data/pc` is a junction to the game folder, so after a test install
     `data/pc/mods/generalbank.drm` IS the test file - two comparisons right after the install compared our file with
     itself. The vtable check above ran before the install and stays valid. Since then the base is a saved copy of
     B138's file (`work/rebuild/base_b138/`, from the `Install-TruTree` backup); `drm_put_sections.py` notes it.
   * `tools/script_ext_check.py` (new): classifies every external relocation of a script by its target (start of a
     function / prototype / member, inside an element, nowhere). Converted TU script 6: 1 020 relocations, all on
     element starts (1 017 functions, 3 prototypes), like the PC's own script 6 (917: 915 / 2). No suspects. Also equal
     to the PC: no natives in script 6, the parent chain (6 -> 93 -> 228/230; parent 93 has 31 vtable slots on Xbox,
     **32 on PC** - the source of the extra slot), no script inherits from 6. Instance size TU 2 092 vs PC 1 973 (13
     more members). Id references: TU +45 (scripts that exist, textures 111/112, the TU-only script 20082).
   * **Control tests** to separate "TU content" from "our procedure":
     * Test 5a (`work/rebuild/dlc2_test5a`): B138 `generalbank` + only the TU-only scripts 21239 / 20082 -
       **no crash**, plays like test 1 (no loading-screen text, costume and weapon choice, level playable, waterfall
       shader wrong). The two extra scripts are harmless.
     * Test 5b (`work/rebuild/dlc2_test5b`): the **retail** script 6 through the same procedure (our converter,
       `drm_put_sections --xbox --retail` (new option): 168 call offsets remapped, vtable insert) - **crash, same
       signature** (2026-10-29 20:19). A script that should behave like the PC's own crashes: the error is in the
       procedure, not in the title-update content. Good news: the PC script is now an exact reference.
   * Retail-converted vs PC script 6, structure by structure (scratch compare): 34 functions, 30 prototypes, 198
     members, 182 SFI, 5 states, 53 vtable slots on both sides. Code of the 31 functions with equal length differs
     only in debug line markers (op00); 3 functions are re-authored on PC (359 -> 389, 114 -> 117, 127 -> 130 words).
     Dependencies: same 26 scripts, other order. **51 of 198 member names differ** (e.g. 706 instead of 368) - names
     the learned symbol map does not know and the converter guessed.
   * `sym_calibration_check.py` now also pairs DataMember names (members, function arguments, locals; by position
     and equal data offset): **1 846** name Symbols outside the learned map have base evidence in `generalbank`, the
     converter gets **451 wrong**, the B138 calibration disagrees with the base game on **131**. The learned map itself
     agrees on 1 151 member/argument/local names and disagrees on 18 (arguments - probably pairing errors of the check).
   * Test 5c (member names fixed, `work/rebuild/dlc2_test5c`): **same crash** - names ruled out as the cause (kept as
     a correction). Test 6 (TU script with the same fixes): same crash.
   * **Crash dumps.** Windows writes a dump per crash (`%LOCALAPPDATA%\CrashDumps\tru.exe.*.dmp`); read with `cdb`
     (Windows SDK debugger, `cdb -z DUMP -y "" -i GAME_DIR -c ".ecxr; kv"`). Every crash of tests 2-6 is the same
     call: `tru.exe` +0x1a4d4b `call edx` with `edx = [[esi]+4] = 2` (return address +0x1a4d4d), called from
     +0xca30e. The caller (+0xca2a0) walks a list at +0x21c (count) / +0x220 (records) of an object, a routine at
     +0xd08e0 reads UTF-16 text.
   * Lead "PC-only calls" (ruled out): the PC version of script 6 calls four parent-class functions the Xbox scripts
     do not have (script 93 functions 84 / 85 in function 2, 109 at the end of function 3, 110 at the end of function
     32). Test 7 = the PC's own script 6 with only these calls neutralised (`script_nop_call.py`): **no crash** - they
     are not required.
   * Found on the way (a real error, not the crash): the call-offset remap paired unknown function names by position;
     where the PC inserted functions into a script it picked the neighbour - 10 calls of the retail script 6 went to
     the wrong native (script 63 function 17 is PC function 18; script 87 function 31 is PC 35, not 33).
     `sym_calibration_check.py` now also votes from **call sites** (functions paired by index, equal-length code
     compared word by word: both sides call something at the same word -> same function; weight 10, 2 194 votes) and
     assigns PC Symbols injectively (strongest first). `drm_put_sections.py --symbols FILE` uses those names. Retail
     script 6 then calls exactly the PC's targets (apart from the four PC-only calls). Test 5d: **still the same crash**.
   * **Full dump** (Lukas enabled `LocalDumps\tru.exe` DumpType 2; to be removed after the tests): the object with the
     list is a `cdc::UIMenuEntry` (RTTI); its count at +0x21c is **0x00010000** and its record pointer points **into
     our script 6**, at a member init block (`{-1, 2, ptr, two UTF-16 characters}` = a static wide string with a
     button glyph pair). Script 6 found in memory by a code pattern of function 2.
   * **Cause: the converter's byte order for member init blocks.** Init blocks hold mixed fields (u32 numbers, u8
     flags, u16 pairs, UTF-16 characters); `script_conv` labels their words `('init', base type, depth, offset,
     userType of the top-level member)`, so one label covers different field types of nested structs, and the
     learned permutation is wrong for many of them. Examples in script 6: u32 `1` came out as `0x00010000` (should be
     `01 00 00 00`), a word of four u8 flags got its halves swapped (should stay raw), the glyph pair `U+018C U+0169`
     came out in reverse order (should be swapped per 16-bit character). The earlier structure comparison skipped
     pointer fields and so never looked into init blocks.
   * The PC's glyph codes differ as well: the PC build shifted the button glyphs by 2 (`U+018E U+016B` where the
     Xbox has `U+018C U+0169`) - Xbox values are wrong on PC even with the right byte order.
   * `tools/script_init_from_pc.py` (new): for a base-game script, pairs data members (members, args, locals) with
     the PC version by name / type tag / userType, walks both init trees in parallel and copies every non-pointer word
     from the PC (nodes of another shape are reported and kept). Retail script 6: 184 members + 65 locals paired, **521
     words changed**, 3 nodes of other shape. TU script 6: 526 words changed, 7 nodes of other shape, **19 TU-only
     data members / locals with init keep their converted values** (open risk; need field-type rules).
   * TU-only members (no PC counterpart): `script_init_from_pc.py --xbox generalbank.drm` learns per (type tag,
     userType, path in the init tree) the byte order that turns the Xbox word into the PC word in every paired member
     (134 field rules), or a u16 value map where values differ (glyphs), and re-derives the TU-only words from the
     Xbox data: 44 words changed (e.g. the count `1` of three menu-entry structs), 100 already right, 248 without a
     rule (mostly zeros and floats, already right as converted), 7 glyph words with a value the map does not know
     (`0x4021`; byte order fixed, value kept).
   * **Loading-screen texts**: three TU-only members hold locals string ids (native init type of the locals table):
     Xbox 1285 / 1288 / 1292, converted to 1314 / 1317 / 1321 = tutorial hints on PC. `locals.py build` appends the
     title update's strings after the PC table; its `locmap_xbox_to_pc.json` maps them to **5170** ("Recently I have
     come across an old file of my father's ...", DLC 1), **5173** ("The Doppelganger is a dark and deadly reflection
     of Lara ...", DLC 2) and **5177** ("Natla created the Doppelganger ...", DLC 2). `--locmap FILE` applies it.
   * Test trees: 5e (`dlc2_test5e`, retail script 6 + PC init values) and 9 (`dlc2_test9`, TU script 6 with all fixes:
     base-evidence names, `--symbols` call remap, vtable slot 31, f93 call neutralised, PC init values, TU-only init
     rules, locals ids). Script 6 of test 9: 53/53 vtable slots = PC, 0 out-of-bounds relocations, 167/167 DRMs clean.
   * **Results 2026-10-29 evening.** 5e (retail + PC init values): crash at a NEW place - `tru.exe` +0xca260 reads a
     null list of a `cdc::UIMenuWdgt` (+0x264 count held a pointer into script 6, +0x268 list = 0). Cause: the PC
     re-authored native struct 351 (menu widget parameters): same size, but three packed u8 fields became u32 and the
     array pointer moved one word; `script_init_from_pc.py` now re-lays such nodes out to the PC layout (relocations
     moved; 2 nodes). Test 9 (TU before that fix): same new place. **5f (retail, fixed): no crash** - level loads,
     costume and weapon choice, no loading-screen texts (expected: the retail script has no DLC branch). Test 10 (TU,
     fixed): the old glyph crash again, now with count 1: the one TU-only glyph member holds `0x4021`, a value the
     learned Xbox -> PC glyph map does not know; test 11 empties that glyph list (count 0).
   * **Test 11: freeze, no crash** (`tru.exe` not responding, one core busy). Snapshot of the running process without
     ending it: `cdb -pv -p PID -c ".dump /ma FILE; qd"` (non-invasive attach, detach). The main thread loops in
     `NtCreateFile` -> `STATUS_OBJECT_NAME_NOT_FOUND` for **`mods\image\loading_bg_dlc2.raw_004`** - the title-update
     loading screen now runs on PC, recognises DLC 2 and asks for its background image.
   * The image exists in pack11 (`image\loading_bg_dlc2.raw`, 3 768 448 bytes; `loading_bg_dlc1.raw` in pack10/11)
     but our media step never wrote it: `raw_image_convert.dlc_gen` names files from `work/generic/dlc_names.txt`,
     which lacks these two names, so they stayed `UNNAMED_*` (not installable). Converted with
     `raw_image_convert.py file` (1280x720, checked as PNG) into `work/rebuild/dlc2_loading_bg/`; test tree 12 = 11 +
     both images (plain name and the `_004` name the game asked for).
   * **Test 12 (2026-10-29 22:23): the DLC 2 intro cinematic plays** (`pdlc2_000_fight`: the Doppelganger fights
     Lara, Natla lifts her - screenshots in the workspace) - first time on PC. Problems: (1) about one frame every
     two seconds with looping sound; (2) Lara wears the costume chosen before the level (camo bikini) - the
     costume/Doppelganger choice is still the open "dlc2data" point; (3) after the intro a crash (22:32:52,
     `tru.exe` +0x1a8616): a `cdc::UIVec3TimeLine` (UI animation of a vec3 property) walks its target list (+0x28),
     one target points into the stack (0x0019fae4 - an object that no longer exists) and the list ends early.
   * Slowness samples (the running game, `cdb -pv` stack of the main thread, six samples): out of focus the game
     sleeps (`Sleep(100)`); in focus one sample in Direct3D re-uploading a managed 512x512 mip-mapped texture during a
     draw (`d3d9 UpdateTextures -> CreateSurface`), three in a float loop (`tru.exe` +0x45f0xx, called from the
     game update +0x5b8254). Not conclusive yet.
   * Checked and ruled out for the TU-only members: their struct types (320, 306, 301, 361, 223) have the same init
     shapes on Xbox and PC (unlike 351). `.mus` files of the DLC 2 music are installed (25). The DLC 2 cine fix ran
     (6 command DTPs, e.g. `pdlc2_000_fight` 100 of 227 words changed).
   * Last file names in the crash dump's memory: `cinstream\pdlc2_000_fight.mul`, `music\dlc2_level2_start_mus_01.mus`
     / `.mul`, `..._amb_01`, `wp_dlc_handgun.drm`, `co_cine000_impact.drm`, `co_dlc_lara.drm`, `dlc_fx_goo_*`,
     `camerashake*`, `dlc_costume*` (all present).
   * **Test 13 (12 with the PC `g_pda`, 2026-10-29 22:45-23:01):** a new base game runs (to the boat, saved). DLC 2:
     the intro again plays at about one frame per two seconds for 6-7 minutes, then the same crash as test 12
     (`tru.exe` +0x1a8616). The `cdc::UIVec3TimeLine` in the dump runs from 506.8 s to 507.8 s of game time (a
     one-second UI transition started when the intro ends); the entry of its callback list holds a function
     (`tru.exe` +0x197448) and an object pointer into the stack (0x0019fae4, zeroed by now) - the callback object no
     longer exists when the transition finishes.
   * The DLC 2 start script (`dlc_level2_start.drm`, script 23129) differs from DLC 1's (20068): function 0 calls a
     title-update check (script 118), prints "(SECOND) DLC Title Update has been found!" and calls script 98; it has
     no state that waits for a loading-screen message, so the author's `cine_nowait` patch for DLC 1 has no DLC 2
     counterpart in this script.
   * Upstream's `tools/native_test` (creates every shader / vertex declaration / texture format of the installed
     `mods\` on the GPU) prepared: `native_extract.py` (run with the workspace venv instead of a system `python`)
     found **294 DRMs, 2 564 unique shaders, 396 generated by the port** (test tree 13 installed). The GPU part
     (`native_test.ps1` in 32-bit PowerShell) is run by the owner of the machine; result in `native_report.txt`
     (ignored). Lead: a shader the driver rejects may be re-created on every draw (slow intro).
   * **Native test result (2026-10-29 23:06, RTX 3080 Ti, driver 32.0.15.6094; B138 DLC 1 + test tree 13
     installed)**: the driver rejects **272 of the 396 port-generated pixel shaders** (`D3DERR_INVALIDCALL`), none of
     the 2 168 copied/converted ones; the negative control was rejected (test valid); PS30Slots = 4096 and length
     probes up to 4 096 instructions pass, so length is not the problem on this GPU (the author's suspect - pixel
     shaders longer than 512 instructions - does not hold here).
   * **Exact cause** (new read-only tools: `tools/shader_disasm.py` = Windows' `D3DDisassemble`,
     `tools/shader_validate.py` = reassembly with D3DX9's `D3DXAssembleShader`, `tools/shader_reject_check.py` =
     feature counts): all 272 rejected shaders fail with **one** error and none of the 124 accepted ones does -
     `error X5584: 2 different constant registers (c#) read by instruction. Max. different constant registers
     readable per instruction is 1.` (e.g. `cmp r4, c216.xxxy, r3.zxyy, c221.y`). The Xbox GPU allows two constants
     per instruction, Direct3D 9 shader model 3 does not; the port's shader translator (stage 3, B72-B89) emits such
     instructions. Fix (not done yet): before such an instruction `mov rN, cX` into a free temp register and read
     `rN` instead - mechanical, checkable with `shader_validate.py`.
   * The rejected shaders all sit in the port's own shader libraries (sections 2173, 2720-2783) and those exist only
     in **B138's DLC 1 files** (38 files, e.g. `dlc1_ei_grapple_wall.drm`); our DLC 1 / DLC 2 trees have none (stage 3
     not rebuilt; their shaders all pass). So this explains B138's "A problem has occurred with your display driver"
     when entering DLC 1 on a real GPU, **not** the slow DLC 2 intro.
   * **Fixed offline (2026-10-29 night)**: `tools/shader_const_fix.py` inserts `mov rT, c#` before every instruction
     that reads more than one constant register (rT = a temp the shader never uses; the same free temps serve every
     instruction because the copy is read right away) and rebuilds the ShaderLib sections (format checked: a rebuild
     without changes is byte-identical for all 107 libraries; slots may share an entry, e.g. lib 2776). Every changed
     shader must disassemble and reassemble without error before it is written. `tools/shader_lib_check.py`
     validates all unique pixel shaders of a folder offline and reproduces the GPU result exactly: B138 **272
     rejected / 124 valid** (= native test) -> after the fix **396 valid, 0 rejected** (392 shader instances fixed,
     1 176 `mov` inserted). 22 of the 38 B138 DLC 1 files change (2 more were missed - see 2026-10-30 01:00 below) (`dlc1_*` objects, `dlc_costume_f`,
     `knight_thrall`, `knight_thrall_chunkdoll`, `wp_dlc_gold_shotgun`); `tree_check` 22/22 clean
     (`work/rebuild/b138_shaderfix/out`). First attempt left 30 shaders unfixed (temps given out once per shader) -
     corrected. Not yet tested in game: install the 22 files over B138 and enter DLC 1 (the display-driver box
     should be gone).
   * **In-game test of the shader fix (2026-10-30 00:15, unattended run, B138 + the 22 fixed files): the
     display-driver box still appears** when entering DLC 1 (after loading screen, outfit and weapon choice; text
     "Es ist ein Problem mit Ihrem Grafikkartentreiber aufgetreten ..."). The 272 invalid shaders were real, but not
     (only) what triggers the box. Engine side: the box is shown by the main loop (`tru.exe` +0x7ad50) when a global
     flag (+0x5eee30) is set and a device status at `[[+0x6d75e4]+0x10]` is -4 / -3; message id 0x1397 / 0x1388.
     The code that SETS the flag is not found by a direct memory-operand search (only the read/clear at +0x7ad52 /
     +0x7ad5d) - it is written through a pointer. Next: a write breakpoint on the flag (`ba w1`) in a debugger run.
   * How the unattended test was driven (for the next runs): TRU in windowed mode (registry `Fullscreen` 0, saved
     before in the workspace backup); screenshots of the TRU window (GDI copy works); the main ring menu ignores
     arrow keys but follows the RELATIVE mouse motion (the game cursor moves by about twice the injected delta; the
     highlighted item follows the direction from the ring centre; click without moving the cursor); list menus
     (outfit, weapon) and dialogs take arrow keys / Enter (scan-code input). Path: ring -> "Inhalte zum
     Herunterladen" -> "Mission spielen" -> mission screen -> Enter -> outfit -> weapon.
   * Limits of driving the ring menu by injected mouse motion (second run 00:26-00:28): the gain of the relative
     motion varies (about 1.8x-2.1x), the highlight sticks to the LAST item the cursor crossed, so an item is reached
     only when the path crosses no other item (worked: approach the DLC icon from the bottom right). Hitting "Mission
     spielen" reliably failed twice; the run was stopped there to avoid a trial-and-error loop. A gamepad (or a
     keyboard path for the ring) would make this deterministic. After an error box TRU opens its Setup dialog;
     "Abbrechen" ends the game by itself.
   * **The DLC 1 "display driver" box, traced (2026-10-30 00:45, B138 + fixed shaders, unattended run with a
     debugger)**: a hardware write breakpoint on the flag (`ba w1`, condition value != 0, then `.dump` and detach)
     fired at `tru.exe` +0x7ad5d in the main loop: the flag = "device status `[[+0x6d75e4]+0x10]` != 0"; the status
     was **-4**. No GPU reset in the System log (no nvlddmkm / display event), i.e. not a TDR; the box text
     ("Grafikkartentreiber") is the engine's generic message for status -4 / -3.
   * First reading, **wrong** (kept as a dead end): -4 is also written at +0x122750 after a failed
     `IDirect3D9::CreateDevice` (call at +0x122736, log text "PCDeviceManager: CreateDevice() failed"), so the box
     was first blamed on a device re-creation (commit e498ca6). A breakpoint run at +0x122736 / +0x122738 never fired
     - CreateDevice is not called when entering the level.
   * **Actual path (write breakpoint `ba w4` on the status field itself, 00:50)**: -4 is set by the status setter
     +0x1223f0 (`push -4` at +0x122570) called from +0x124d68, the failure branch of the shader object's create
     function +0x124d40: `call [device+0x1a8]` = **`IDirect3DDevice9::CreatePixelShader`** (vtable index 106) with
     the bytecode pointer at `[obj+0x14]`; on a negative HRESULT it calls +0x124c50 -> +0x122570. Stack: render
     path (+0x126113 <- +0x106b05, inside `d3d9!SetPixelShaderConstantF`) - the shaders are created lazily at their
     first draw, so one invalid pixel shader anywhere in the level is enough.
   * **The failing shader, captured (01:00, `bp` at +0x124d68 with `.writemem` of the bytecode)**: one call failed,
     HRESULT **0x8876086C = `D3DERR_INVALIDCALL`**, a ps_3_0 shader of 8 340 bytes, library hash
     0x06515d8171980288. `tools/shader_validate.py`: `X5584 ... 2 different constant registers` at
     `cmp r0, c219.xxxy, r3.zxyy, c221.y` - the same defect as above, **not fixed in the installed tree**. New
     read-only tool `tools/shader_find.py DUMP DIR...` (finds a dumped shader in the ShaderLib sections of DRM
     files): it sits in **`co_dlc_knight_thrall.drm` and `co_dlc_knight_thrall_pieces.drm`** (libs 2726 / 2723,
     slot 7) - two B138 DLC 1 files the shader fix never saw. `shader_lib_check.py` over the installed `mods`
     folder: **24 unique pixel shaders still rejected** (396 valid).
   * Why they were missed (forgotten jump point): the fix input (`b138_shaderfix/in`) was copied from the game
     folder by a filter "files with a port shader library" while the DLC 2 test tree 13 was still installed; test
     13's `co_dlc_knight_thrall*.drm` have **no** port shader library (the filter finds 0 files in
     `dlc2_test13/mods`), so they were skipped (38 instead of 40 files), and the later `-Restore` brought back
     B138's unfixed versions. Rule: copy fix inputs only from a clean, known tree (or from the release folder),
     never from the game folder while a test tree may be installed; and validate the INSTALLED folder after every
     install (`shader_lib_check.py <game>/mods`).
   * **Fixed and tested (01:05-01:17)**: `shader_const_fix.py` over the whole installed `mods` folder writes exactly
     these 2 files (80 shader instances, 240 `mov`; `b138_shaderfix/out3`), installed with `Install-TruTree`
     (stacked on the 22-file tree). Installed folder: **396 unique pixel shaders valid, 0 rejected**. In game:
     no failed `CreatePixelShader`, no error flag; the DLC 1 intro (journal page with the hammer fragment) plays
     and **Lara stands in the DLC 1 level** ("Beneath the Ashes") - the display-driver box is gone. B138 + 24
     fixed files = **first DLC 1 level start on this PC**.
   * Outfit in that run: the first list entry is "Bikini Schwarz-Weiss" (B/W bikini; list: B/W bikini, camo
     bikini, Freizeitforscher, gold bikini, grey jungle shorts), so the bare skin in the level is correct, not a
     missing texture.
   * Debugger limit: `cdb -p` keeps "kill on exit" - when `timeout` ends cdb, Windows ends the game too. Unattended
     runs need a clean detach: a hard stop with `qd` in a breakpoint (after N hits / on the awaited event), or end
     the game normally (cdb ends with it). The idea "`sxe -c "qd" bpe` + `DebugBreakProcess` from outside" did not
     detach in its one try (02:43, no break event logged).
   * **Code review of this session's tools (2026-10-30 night, 10 findings, all fixed in 01d9bea)**:
     `script_init_from_pc.py` moved relocations one by one (two pointers that move by one word could overwrite each
     other), learned field rules after the re-layout (wrong Xbox/PC pairs for re-laid-out nodes) and wrote output
     with out-of-bounds relocations; `shader_const_fix.py` found the END token with an unaligned byte search and kept
     its own copy of the port's library list; `script_vtable_insert.py` did not check that IN and REF have the same
     section at the copied VTE's external indices, crashed on null / external vtable slots and wrote output with
     out-of-bounds relocations; `exe_xref.py --write` used a mnemonic list (missed `inc` / `or` ..., counted `cmp`)
     - now capstone's operand access flags; `sym_calibration_check.py` could write a non-injective map (two
     calibration entries for one PC Symbol). Documented as a limit instead of changed: arguments / locals are paired
     by name across functions, not per function (surplus is counted). Re-run after the fixes: shader fix, retail and
     TU init outputs and `sym_base_evidence.json` are **byte-identical** to before - the findings did not affect the
     results so far.
   * **Slow intro, sampled (2026-10-29 23:15-23:25, test tree 13)**: a background watcher took a stack sample of the
     main thread every few seconds while the game ran in the foreground (`cdb -pv -pn tru.exe -c "~0 kv; qd"`,
     nothing ended; 49 samples; the same crash at +0x1a8616 at the end). **42 of 49 samples** are in one path: game
     update (+0x1e01ba -> +0x1e0005) -> +0xa1fb0 (calls a function pointer stored at +0x1d4 of an object) -> +0x601c0
     -> +0x5fab0 / +0x5ffa0 -> vector maths (+0x5e..., +0x5f...). +0x601c0 runs `n = [obj+0x40] * [obj+0x3c]` steps of
     `[obj+0x24] / n` each - a sub-stepped simulation whose step count comes from data. Wrong counts (e.g. a byte
     order mistake) would explain one frame per two seconds. The object no longer exists in the crash dump.
   * Lead (not checked yet): the intro shows the Doppelganger and Natla, the level so far only Lara; a hair / cloth
     simulation of a DLC 2 character model fits "steps x sub-steps" - and finding 39 kept `float_fix` away from the
     DLC 2 character-model DTPs. Next: read the two counts in a running game (snapshot or breakpoint at +0x601ca
     while the intro is slow), then find the DTP field they come from.
   * **It is the cloth simulation** (static, `tools/exe_xref.py` = capstone cross-references over `tru.exe`, plus RTTI
     in the dump): +0x60200 is slot 0 of the vtable of `JobHarness_JobClothSimulate` (vtable +0x443ce8, set at
     +0x60291 in the job entry +0x60260); it copies positions into the simulation object (`[job+0xdc]`) and tail-calls
     the stepper +0x601c0 (`n = [sim+0x40] * [sim+0x3c]` sub-steps). The job is started at +0x57b75 after DMA-style
     buffers sized from the cloth object: `[+0x18]` x 64 bytes, `[+0x1c]` x 48, `[+0x20]` x 128 (particles,
     constraints, ...). The data source of +0x3c / +0x40 is not traced yet. Candidates in the intro: the
     Doppelganger's and Lara's hair / clothes (Lara wore the camo-bikini costume - a B138 costume conversion).
   * **Counts read in the running game (2026-10-30 01:26 / 01:40, breakpoint at +0x601ca, `esi` = simulation
     object; new `tools/cdb_cloth_summary.py` sums the cdb log)**: DLC 1 (B138, fast): 3 objects, sizes
     (+0x18 particles, +0x1c constraints, +0x20 collision shapes) = (7, 6, 9) and (15, 36, 4); DLC 2 intro (test tree
     13, slow): 7 objects - the same Lara types plus (32, 84, 3), 2 x (9, 16, 3) and (7, 6, 4). `[+0x3c]` = 3 always.
     **`[+0x40]` is not data**: it follows the elapsed time `[+0x24]` (first frame 15.0 -> 15, then 2.0 -> 2; DLC 1
     settles at ~0.6 -> still 2). So a call runs 6 sub-steps (45 after a long frame). In DLC 2 `[+0x24]` stays at
     the cap 1.99998 for the whole intro = every frame is slow; 2 580 stepper calls in about 8 minutes = ~0.8 frames
     per second (7 objects per frame).
   * The step code is bounded by those small counts (static, `cdb -z ... uf / u`): +0x5fab0 loops over `[+0x18]`
     and `[+0x1c]`; +0x5ffa0 repeats `[+0x30]` (= 4) times: constraints `[+0x1c]`, then every collision shape
     (`[+0x20]`, 0x80 bytes each at `[+0x14]`, type byte +0x70 / mode +0x71) -> +0x5ed20 or +0x5f600, whose loops
     all run over `[+0x18]` or `[+0x1c]`; +0x414170 there is a `memset` of a per-particle buffer. **The cloth counts
     do not explain the slow intro** - the earlier stack samples (42 of 49 in this path) need another explanation
     (per-call cost, e.g. invalid floats, or a caller that repeats the job). Next: time one stepper call directly.
   * **Timed (01:54, breakpoints at entry +0x601c0 and return +0x601f8 with `.time`; new
     `tools/cdb_time_summary.py`)**: six objects take 1-3 ms per call, **one takes 962-1 187 ms** - that object alone
     is the slow intro. Its dump (breakpoint with `.if (@ecx == <object>)`): sizes (7, 6, 4) and **`[+0x30]` =
     0x00040000 = 262 144** where every other object has 4 - the outer pass count of +0x5ffa0 (constraints +
     collision), i.e. 65 536 times the work. The earlier "+0x30 = 4" reading above was right for the other objects
     only.
   * **Source of the value** (new read-only `tools/drm_find_bytes.py` over the test tree, then
     `tools/dlc_section_compare.py` = Xbox section from the pack archive next to the converted one): every Lara-type
     model DTP carries three cloth parameter blocks `{u32, ptr, u32, ptr, f32, f32, u32 iterations, u32 2, u32 5,
     u32 3, f32 0.5, ...}`. In `co_dlc_lara.drm` (DTP 24717) and `co_dlc_lara_f.drm` (DTP 25808) - new DLC 2 DTPs,
     route `convert` with the learned type-7 table - the third block's count (Xbox `00000004` at +0x204) was encoded
     as two s16 halves (`00000400`); its neighbours and the first two blocks of the same DTP are s32, and all three
     blocks of `lara_doppelganger`, `doppelganger_casual` and B138's `dlc_costume_f` hold `04000000`. A per-label
     class error of the learned table, not a data error. (`co_dlc_lara*` exist only in DLC 2; B138 has no such file.)
   * **Fix: stage-2b fix `cloth` in `tools/dlc_fixes_build.py`** - on the Xbox source, a word becomes s32 only when
     the whole block matches (pointer slots at -20 / -12, small integers at the count and at +4 / +8 / +12) and the
     converted word differs. DLC 2 stage 2b: exactly the 2 words above; DLC 1 stage 2b: **0 changes** (stays
     byte-identical to B138). In game (test tree 13 + the 2 files, 02:05): all 7 objects 1-2 ms per call, **the
     DLC 2 intro plays at normal speed (about 1 minute instead of 7-8)**. The crash after the intro remains (dump
     02:06).
   * Lesson for the checklist: when one frame is slow, time the calls per object before reading counts - an
     average over all objects hid the one bad object; and compare a suspicious word with its sibling blocks in the
     same DTP and in the matching base / B138 model.
   * **The crash after the intro, traced further (2026-10-30 02:13-02:23, test tree 13 + cloth fix; the intro now
     ends after about a minute, so each run takes ~5 minutes)**:
     * RTTI in the dump: `cdc::UIVec3TimeLine` vtable +0x451fa4, constructor +0x1ace80, update +0x1a85b0 (crash at
       +0x1a8616). Its target list (+0x28) holds nodes {next, ..., +0x10 start vec4, +0x20 target object}; the update
       calls `target->vtable[0x1c/4](value)` for every node.
     * A breakpoint after each constructor call plus a hardware write breakpoint on the list head of the last ones
       (`ba w4`): the crashing timeline (13th of the level) gets its node from +0x1a9214 (list insert) <- +0xcca87
       <- native thunk +0x3a77e3 <- script VM (+0x17c238), **with target = 0x0019fae4 = a stack address**.
     * How a stack address gets there: a timeline is built from a data descriptor (+0xcfbd0: `{u32, u8 +4, u8 +5,
       u8 +6, u32 n_targets +8, targets +0xc, u32 n_keys +0x10, keys +0x14}`; keys 16 bytes = time + vec3). The
       script native +0xcca00.. resolves each target path for a widget: +0xd08e0 walks the path (u16 ids, entries
       `{u32 n, u16 *ids}` with inline data) - child lookup +0xc8420, else property lookup +0xd0850; **when an
       element is not found it returns `&local` (`lea eax,[esp+1Ch]`) instead of null**, and the caller inserts that
       stack address as the target. One second later (end of the transition) the update calls through it.
     * The crashing descriptor sits in a new DLC 2 script (id 26449 in `dlc_level2_start.drm` +0xbc0, the same
       script in 26 level files): one target, path `{2, ->[0x0266, 0x07b9]}` (PC bytes `6602b907`, Xbox
       `07b90266`), keys (0, 38, 0, 0) -> (1, 38, 1, 0).
     * Dead end (kept): "the converter swapped the u16 path as s32, so the ids trade places". New read-only
       `tools/script_u16array_check.py` (inline u16 arrays `{n, ptr -> next word, u16[n]}` in scripts, PC vs Xbox):
       DLC 2 122 arrays, all s32-encoded - but **B138 / the PC base game encode them the same way** (base script 72
       in `dlc1_health_pack.drm` = PC copy: Xbox `07b90266` -> PC `6602b907`, 171 arrays incl. DLC 2 files, all
       s32). So the path bytes match the PC convention; the failing element must be found differently (which
       widget, which id). Next run: log every path element (+0xd0930), child / property results and the widget
       when the resolver returns a stack address.
     * **What the path elements are** (02:30, breakpoints in the resolver): the widget is a `NsUIScreen` (RTTI);
       +0xc8420 searches the **data members of the script class** (`[class+0x2c]`, 0x14-byte entries, u16 name
       Symbol at +0xe, offset at +0xc - the DataMember layout known from script 6), +0xd0850 the prototypes up the
       parent chain. The path elements are **member name Symbols**. Elements 0x012f / 0x0266 were not found
       (child 0, property 0) -> stack address; 0x0131 on another object was found.
     * Experiment 1 (test 15, kept as a dead end): Xbox element order with the Xbox values (`script_u16array_fix.py
       --mode s16`): the first element 0x07b9 is not found either - order alone is not it.
     * **Cause: the converter maps Symbols in the script class tables but not in these u16 arrays** - they keep
       the Xbox numbers. `tools/sym_lookup.py` (new, the converter's own `DlcIds.sym`): Xbox 0x07b9 -> PC 0x07a3,
       0x0266 -> 0x0268, 0x012f -> 0x0131 (the one id that WAS found in the trace is the PC id of 0x012f).
     * **Fix (test 16, 02:40): every element -> the converter's PC Symbol, Xbox element order, u16 LE**
       (`tools/script_u16array_fix.py`, default mode; 122 arrays in 14 DLC 2 files, symbol routes extra 52 /
       mapped 26 / interpolated 96 / guess 66 / DLC-new shift 4). In game: **no stack target, no crash - the DLC 2
       level is playable** (the player character - the Doppelganger in her suit - stands in the level, walks with
       W). Built into stage 2b as fix `uipath` (`dlc_fixes_build.py`; DLC 2 stage 2b: 127 arrays incl. 5 in
       `g_pda`).
     * **B138 has the same defect in DLC 1** (25 arrays in new DLC 1 scripts, e.g. `dlc_watertunnel.drm` script
       22902: Xbox `064d019a` -> B138 `9a014d06`); DLC 1 shows no crash, so those UI animations probably just do
       nothing (target = a dead stack slot that happens to be harmless, or never updated). `uipath` therefore runs
       for DLC 2 trees only (`--pack pack11`) - DLC 1 stays byte-identical to B138 until the owner decides.
     * Still open in DLC 2 (test 16): **Esc opens no pause menu** (in DLC 1 it does; input itself works). The game
       was closed with `WM_CLOSE` (no dump). `TruDetach.ps1` (`DebugBreakProcess`) did NOT detach cdb (no break
       event in the log) - ending the game ends cdb cleanly instead.
     * Control (03:00): DLC 1 still starts with the DLC 2 test files installed on top (shared names, finding 38) -
       Lara in the level, quit through the pause menu.
     * DLC 1 played by the owner (2026-10-30 morning, controller): runs through the intro, the bridge, a spider
       fight; the grapple points show **two yellow rings** - whether that is the intended look is open (no
       reference yet). **The intro speaks English on a German game.**
     * Grapple ring, checked (2026-10-30 noon): the owner's Xbox reference shows a **rusty metal ring** with a round
       Y-button prompt below it -> the flat yellow ring on PC is a rendering defect. New read-only tools:
       `tools/drm_sections.py` (sections of a DRM), `tools/drm_textures_png.py` (PCD9 textures -> PNG + contact
       sheet), `tools/shader_lib_dump.py` (disassembly per ShaderLib entry). `dlc1_ei_grapple_wall.drm`: textures
       decode correctly (rusty metal 6650 / 6852 / 4294 / 6770, normal map 6463), materials 21093 / 21164, port
       library 2762 with 8 lit pixel shaders (12-13 samplers, 440-580 instructions). **Not caused by the shader fix**:
       the diff B138 vs fixed per shader is exactly the inserted `mov r23, c222` before the three `cmp ..., c167.zzzy,
       ..., c222.y` (r23 unused before) - same result bit for bit. So the yellow comes from B138's own translated
       shaders or material (stage 3, the shader translator B72-B89, not rebuilt yet). Lead: the port shaders read
       material constants at Xbox register numbers (e.g. `c167.zzzy` as a select); if the PC engine fills other
       registers, a highlight / tint term can win - compare which constant registers material 21093 sets on PC with
       the ones the shaders read.
     * Ring materials compared (2026-10-30 12:30; new `tools/bigfile_extract.py`, material references in
       `drm_sections.py`): the DLC object is a re-textured variant of the base `ar_ei_grapple_wall` (2 materials,
       3 meshes, same texture formats). DLC material 21093 (wall) / 20344 (ceiling) on Xbox: shaders 2116 / 2117 /
       2118 / 2119; shader_map: 2116 class D -> 1016 (score 0.108), 2117 C2 -> 1017 (0.45), 2118 C3 -> 1018 (0.246),
       2119 B -> 211; B138 uses 1016 / 1017 / **its translated 2762 (2756)** / 211. The other material (21164 /
       20345) uses PC shaders only (205 / 206 / 207 / 233). Base PC ring: 1704-1707 / 1775-1778.
     * Test 19 (`tools/material_shader_swap.py`: main pass 2762 / 2756 -> PC surrogate 1018, owner at the bridge):
       **the ring stays yellow** (with a small green arc) - not the translated main-pass shader. Test 20: all three
       pixel passes of 21093 / 20344 -> 205 / 206 / 207, to see whether the ring belongs to this material at all.
     * **Test 20, zoomed with the in-game camera (owner)**: the ring mesh itself is flat yellow and its bracket
       green - the colours of the object's NORMAL MAP (6463, green-yellow in `drm_textures_png.py`). So a shader
       samples the normal map where it expects the colour texture. Material texture entries are `{u32 texture id,
       0, u32 slot, u32 flags}` (`drm_sections.py --dump`); DLC 21164 has slot 1 = rust colour 6770, slot 3 =
       normal map 6463 - the same roles as the base ring material 16637 (slot 1 colour 5257, slot 3 normal map
       5258), Xbox and PC consistent. The material is right; the SURROGATE shaders 205 / 206 / 207 (class D / B / C3
       for Xbox 2224 / 2253 / 2254) read the slots in other roles. Since tests 19 / 20 on 21093 changed nothing,
       the ring is most likely material 21164 (ceiling 20345).
     * Test 21: the base game's own PC ring shaders 1704-1707 copied into the DLC files and assigned to 21164 /
       20345 (`material_shader_swap.py --add-libs-from`; 21093 / 20344 stay as in test 20). **Result (owner, zoomed):
       the ring is dark metal now** - the base PC shaders read the slots in the intended roles. The bracket (and
       some ring edges) are still lime green = material 21093, still on the surrogates 205-207 (normal map as
       colour). Test 22: 21093 / 20344 -> the base ring's second shader set 1775-1778.
     * **Test 22 result (owner, 2026-10-30 12:50): in the normal game view both rings and their brackets are dark,
       rusty metal - fixed.** In the in-game camera the brackets glow flat yellow (green in test 21): the camera
       draws a highlight pass on interactive objects (like Legend's RAD, owner); the highlight colour followed the
       shader swap, so whether yellow is the intended look is open (no Xbox camera reference yet).
     * **Xenia reference (owner, 13:00, `references\DLC1\Xenia-TU_DLC1_*`)**: the ring is rusty brown / copper with
       light edges; the bracket is a short rod; **the in-game camera shows NO highlight** on Xbox - so our yellow
       camera glow on the bracket is a defect. Also captured: the DLC 1 loading screen title "BENEATH THE ASHES"
       centred above the line (the PC lacks it) and the outfit list.
     * Material texture entries decoded further: `{u32 texture id, 0, u32 role, u32 0x0002RR00}` with RR = the
       SAMPLER REGISTER (base 16638: registers 0-4; DLC bracket material 21093: registers 0-7, normal map 6463 on
       register 2, where the base shader 1777 expects a white helper texture). 21093 is a richer 8-texture material
       without an exact base counterpart (why B138 translated its shader); the camera's highlight / flash pass reads
       register 2 and shows the normal-map colour. Open, cosmetic (camera only): a better shader for 21093, or remap
       its registers to what 1775-1778 expect.
     * Better reading (owner's idea: LOD): the object has two detail levels - far = mesh with material 21164, near
       (camera zoom, or Lara close / hanging) = material 21093. That explains tests 19 / 20 (21093 changed, far view
       unchanged) and the bracket colour following 21093 only when zoomed - so the near-LOD defect shows in normal
       play too, not only in the camera. B138's translated near-LOD shader 2762 was never looked at from close by.
       Test 23: far 21164 / 20345 -> base PC shaders 1704-1707 (as test 21), near 21093 / 20344 back to B138's state
       (1016 / 1017 / translated 2762 / 2756 / 211). **Result (owner, same spot as an Xbox gameplay video, 13:08):
       at mid distance the ring is dark with yellow-green patches** (Xbox: bright copper rust) - the near LOD is
       already in use there, and B138's translated shader shows the normal-map colour as well. Far LOD fine, near
       LOD wrong with every shader tried (2762, 1018, 205-207, 1775-1778).
     * Test 24 (`tools/material_copy.py`): the near-LOD material 21093 / 20344 becomes a copy of the far-LOD material
       21164 / 20345 (base PC shaders 1704-1707) - less detail close up, but the colours of the far LOD.
       **Result (owner, 13:16): no flat yellow / green any more at any distance** - dark metal with rust patches,
       the bracket matches. Remaining difference to the Xbox: the hue is olive-yellow instead of copper-brown and
       the ring is darker; candidate: the material's parameter block before the texture entries (e.g. 21164
       `3e851d69 447a0000 3f333333 3f800000`) read differently by the base shader than by the Xbox one. Current
       state for the ring: test 24 (`tree_20261030_131100`).
     * Xenia at the same spot (owner, 13:27): the ring is GLOSSY copper (strong specular highlights) - ours is
       olive and matte, so the specular / material parameters are the next suspect, not the colour textures; a
       Y-button prompt appears next to Lara; the camera has depth of field (focus on the background when looking
       through the ring). Left for later (stage 3 may cover part of it).
   * **Pipeline integration of the tested fixes (2026-10-30 afternoon)**:
     * `tools/b138_snapshot.py`: a pristine B138 `mods` tree rebuilt from the game folder and the Install-TruTree
       backups (plus `backup\mods` / `work\rebuild\base_b138` for the locals and generalbank changed outside it),
       every file checked against the kit manifest MD5 - **275 / 275** (`work\rebuild\b138_pristine\mods`), so the
       stacked test trees do not have to be undone.
     * `tools/b138_fix_tree.py`: the repair tree from that copy - shader constant fix (24 files, 472 shaders, 1 416
       `mov`), grapple ring (base PC shaders 1704-1707 for the far LOD, near LOD = copy of it), cinematic languages
       (10 for DLC 1, 35 with `--dlc2`). **All 34 files of the DLC 1 run are byte-identical to the files tested in
       game today** (shader fix `out` + `out3`, ring test 24, `lang_mul`).
     * `tools/tree_merge.py`: one tree from an ordered stack (later wins) with a source manifest and
       `--check-against` the installed game. `work\rebuild\play_20261030\mods` = repair tree + DLC 2 test trees 13 /
       14 / 16 / 17 / 18 + all languages: **355 of 361 files equal to the installed, tested state**, the other 6 are
       `local\locals.bin_*`, which Install-TruTree skips by default (DLC menu text fix) - so one install of this tree
       over B138 reproduces today's state.
     * `Invoke-TruPipeline.ps1`: new steps `Fixes` (dlc_fixes_build for DLC 1 and DLC 2) and `Repair`
       (b138_snapshot + b138_fix_tree --dlc2).
     * **Rule learned**: a DLC object that is a re-textured variant of a base object (same materials / meshes /
       texture slot roles) renders correctly with the BASE object's own PC shader libraries; the similarity-voted
       surrogates (`shader_map.py`, 1016-1018 / 205-207 here) can read the texture slots in other roles (normal map
       as colour) and B138's translated shader did not cure it either. Next: find such pairs automatically (DLC
       material <-> base material with the same texture slot set and Xbox vertex shader) and assign the base PC
       tuple in the pipeline; then check the DLC 2 "waterfall" the same way.
     * DLC 2 "waterfall" (a flat, grey, opaque surface where the Xbox shows a bright translucent fall of the blue
       liquid): DLC 2 has no translated shaders (stage 3 not rebuilt, finding 43 native test); every NEW DLC shader
       (`shader_map.py` classes C1-C3 / D) is mapped to a SURROGATE base PC shader chosen by constant / sampler
       similarity. For additive / refracting effects such a surrogate draws the right textures with the wrong
       blend or pass - the expected look of an untranslated shader. Candidates: `dlc_fx_goo_column_displace*` (a
       displacement effect: material 7111 / 3693, base libs 19-22 / 145-148) and the level materials of the first
       room. Both visual defects (ring, fall) therefore belong to stage 3 (shader translation), the largest open
       block: DLC 1's translator outputs exist in B138 (library 2762 etc.), DLC 2 needs the translator itself.
     * Language lead (read-only, new `tools/pack_records.py` = records of a pack with their `spec` word): pack10 has
       **7 records in five languages each** (spec `ffffffe1` and `ffffe002 / 004 / 008 / 010`, names not in the
       name list; two of them 4.4 / 5.4 MB = most likely the speech of the intro and the finale), so the German
       speech exists on Xbox. The kit installs one `cinstream\pdlc1_0x0_*.mul`. The ModLoader binary contains the
       name format `%s_%03d` - the same suffix the language files `local\locals.bin_001 .. _032` use. Next: name the
       7 records (hash of the cinstream names), convert each language variant and install it as `<name>_NNN`,
       then check in game that German is played; the same for the DLC 2 cinematics. (Confirmed in
       `tools/locals.py`: the ModLoader name is `'%s_%03d' % (path, language)` for any language-specific file.)
     * **Language variants, worked out (2026-10-30 noon)**: `tools/pack_records.py --hash` names the big records:
       `xenon-w\cinstream\pdlc1_010_intro.mul` (0xb7ee05e0) and `pdlc1_030_finale.mul` (0x5ce06f1d); pack11 has the
       same for 5 of its 6 cinematics (`pdlc2_000_fight` is language-neutral). The PC base game does it alike
       (`pack_records.py pcbig cinstream`: 38 cinematic `.mul` in specs ffffffe1 / ffffe002 / 004 / 008 / 010, 15
       neutral). The `.mul` carries the speech AND the subtitles (text tails of the cine blocks). Our stage 1
       (`dlc_media_build` -> `mul_convert`) and stage 2a (`mul_audio_nch` via `mul_audio_batch.find_xb`) take the
       English record (spec ffffffe1) only - hence the English intro on a German game.
     * ModLoader (v1.2, private PDB symbols load in `cdb -z ModLoader.asi`): `HookFileSystem::SetSpecialisationMask`
       stores `mask & 0x7fffffff` at +0xc; `HookFileSystem::FindFile` formats `"%s_%03d"` with path and that value,
       uses `<path>_NNN` when it exists in `mods\`, **else the plain path**. So each language goes in as
       `cinstream\<name>_NNN` (001 EN, 002 FR, 004 DE, 008 IT, 016 ES) and the plain name stays as the fallback
       (Dutch has no speech variant on Xbox either). New `tools/mul_lang_build.py`: per variant `mul_convert.convert`
       + `mul_audio_nch.swap`, as stages 1 / 2a do for the English file.
     * **Tested by the owner (2026-10-30 ~11:50, all 35 variants installed as one tree): the DLC 1 intro speaks
       German** on the German game. Each variant carries all subtitle languages (only the speech differs). Noted:
       the speech sounds a little noisy in places - the XMA -> IMA re-encoding (finding 18: >= 25 dB against the
       decoded Xbox source); to compare with the base game's own German cinematics later.
     * **Empty DLC 2 hint box, first look (2026-10-30 morning)**: new `tools/locals_find.py` (search / index /
       `--glyphs` over string tables): the hint "The shadow meter drains when LB or RB is held" is pack11 index 1403
       = PC index 5288 in all six installed tables (German "Die Schatten-Anzeige leert sich ..."); the Xbox table is
       base 0-1283 + DLC 1284-1406, the PC table is larger, so DLC strings sit at 5169-5291
       (`locmap_xbox_to_pc.json`); PC indices 1401-1406 are EMPTY strings. The button glyphs of the DLC strings use
       the same code points as the base strings. B138's `generalbank` script 7 (the author's port of the TU hint
       code) already holds the PC ids 5286-5289. String lookup in `tru.exe`: +0x9a7a0 `GetLocalString(id)` (table
       pointer [+0x603854], count at +4; out of range -> a default string). A breakpoint there (ids >= 5136 or out of
       range) saw only id 5173 in four minutes, while the box was shown once - so the box does not ask for 5288.
       Dead ends (kept): the ids 1401-1403 found in script 74 / DTP 4748 are byte-identical to the PC base game (not
       string ids); in the new scripts 26655 / 25657 / 26635 the word `7b050000` after `ffffffff 40016060` is a
       Symbol (Xbox 1374 -> PC 1403 interpolated), not the hint string. Next: log every lookup of ids 1280-1420 and
       >= 5136 with the caller while the box is on screen (`locals2.cdb`), the owner triggers the hint.
     * **Found (11:15, `locals2.cdb`, already on the DLC 2 mission screen; 400 hits in seconds)**: the game keeps
       asking for the **Xbox ids 1287 / 1326 / 1345** (pack11: "GOLDENE SCHROTFLINTE", "KEIN TEXT", "Raffinerie-Tipp
       2.1"; PC entries 1287-1345 are empty, the right PC ids are 5172 / 5211 / 5230). Every call comes from the script
       VM (+0x1c5a3a) through one native (+0x1a7a42) into `GetLocalString`. First reading "constants in the
       bytecode" was wrong (kept): new `tools/script_const_calls.py` (pushes `op0f N` before calls) found none of
       these ids as constants - the values pushed in range are sizes / offsets (multiples of 4). Also a dead end:
       the "hint ids" 5286-5289 in B138's script 7 and 1401-1406 in the TU script 7 are **line markers** (`op00 N`,
       script words = opcode in the top byte, operand in the low 24 bits), not string ids.
     * **Cause: string ids in script DATA of the new DLC scripts, encoded as Symbols.** Two record kinds (Xbox source
       vs our PC file with `tools/dlc_section_compare.py`, PC base layout from `tools/bigfile_find.py` on the PC
       `generalbank` script 7):
       * UI text element `{u32 0xffffffff, u32 colour ARGB, u32 string id, u32 flags, ...}` - in the base game all
         32-bit (Xbox `ffffffff ff606060 0000000c 00000001` = PC `ffffffff 606060ff 0c000000 01000000`); in the new
         DLC 2 scripts the Xbox word holds the id in its HIGH u16 (`0511 0000` = 1297 "OBJECTIVE REVEALED - Press
         [Back] to view"); the converter's learned table took colour and id for Symbol pairs (colour -> `40016060`,
         id 1297 -> Symbol 1326). The engine reads the word as u32 -> `GetLocalString(1326)` -> empty.
       * hint list `{ptr, u32 id << 16, 0, 0}` (script 20089 in `dlc_level2_start`: 1402 "Press [Back] to access
         the Information screen", 1403 "The shadow meter drains ..."; script 25393: 1404 / 1405) - same Symbol
         mapping (1403 -> 1432). The same field also holds larger values (0x1ba2), so only ids inside the Xbox DLC
         string range 1284-1406 are taken as strings.
     * Pipeline gap found on the way: `dlc_generic.DlcIds.loc` reads `work/generic/locals/locmap_xbox_to_pc.json`,
       which no step writes (`locals.py build` writes `work/rebuild/stage1/locmap_xbox_to_pc.json`, after Convert) -
       so the converter never mapped ANY string id (every LOC word kept its Xbox number). To check what else that
       affects once the map is in place before Convert.
     * **Fix `uitext`** (`tools/script_uitext_fix.py`, stage-2b fix in `dlc_fixes_build.py`, map from
       `TRUDLC_LOCMAP` or `work/rebuild/stage1/`): colour s32, string id -> PC id as u32, only on exactly these
       Xbox patterns. **Test 17 (11:26, test 16 + 14 files: 118 text elements, 88 hint entries): the hint box shows
       German text with the right button glyphs** (see the next point for the box itself; "Die Schatten-Anzeige leert sich, wenn Sie [LB] oder [RB]
       gedrückt halten.", "Halten Sie [LB] oder [RB] gedrückt und springen Sie mit [A] auf eine Felsrinne zu."); the
       lookups of empty ids stopped, the game now asks 5182 / 5201 (the HUD notices). Still missing against the Xbox:
       the box background, the Lara icon on its left and "Press [A] to continue"; the text sits top right instead of
       top centre. DLC 2 stage 2b: 120 elements + 150 hint entries (incl. the merged `g_pda`). **DLC 1 / B138 has the
       same unmapped records** (26 elements; the 12 entries turned out to be PC ids already, test 28: system messages 1286 / 1289 / 1290 "update required" /
       1374 "returning to main menu") - `uitext` runs for DLC 2 only, like `uipath`, until the owner decides.
     * **The hint box itself (box, Lara icon, "Press [A] to continue", centred) is title-update code** (2026-10-30
       noon; Xbox reference from the owner in `references\DLC2`): "Press [A] to continue" is DLC string 1293 (PC 5178);
       its only text element (`ffffffff ff606060 050d0000`) is in the **TU `generalbank` script 10** (`bigfile_find.py
       tu`), absent from the retail Xbox script 10 (`xbase`: 0 hits). The TU grew script 10 from 3 012 to 5 636 bytes
       (`tu_script_changes.py`); the PC game ships the retail version (PC script 9, 3 028 bytes, installed
       unchanged), which shows a hint as plain text top right - exactly what test 17 shows. To get the Xbox look:
       port TU script 10 to PC like script 6 (vtable layout, call-site names, init values from PC, glyphs, string
       ids) and check that the icon image exists on PC. Not started.
     * **Loading screen title (both DLCs)**: the Xbox shows the title above the line ("LARA'S SHADOW", owner's
       reference), on PC only the description types in (`references\DLC1` / `DLC2`: `*_Ladebildschirm_ohneTitel`).
       DLC 1 asked `GetLocalString(1284)` 1 499 times while loading = Xbox "BENEATH THE ASHES" unmapped (PC 1284 is
       "[A] JA"). Its text element sits in the PORTED TU script 6 (`ffffffff ff606060 0504 0000` at +0xe940, same
       offset on PC); `uitext` skips base scripts. New `script_uitext_fix.py --ported IN OUT 6 --locmap MAP` (PC-side,
       named ported scripts only): 1 record, 1284 -> 5169 (test 18, `work/rebuild/dlc2_test18_gbtitle`). Now the game
       asks 5169 "UNTER DER ASCHE" every frame - **but the title is still not visible**. Checked and ruled out: the
       element's other words equal the Xbox ones (floats, colours, flags); the 46 inline path arrays of script 6 are
       no longer in the unmapped form (the port took them from PC; new `script_u16array_fix.py --tu-ported`); the 10
       timelines created while loading (timeline logger) have sane keys and PC Symbol paths. Open: why the element
       stays invisible (draw order / parent widget / a visibility member of the TU-only part).
     * Debugger technique used here (for the next string problem): breakpoint on `GetLocalString` (+0x9a7a0) with a
       condition on the id range and `kv 4` for the caller, a hit cap with `qd` (the log fills in seconds when a HUD
       asks every frame); the owner plays to the spot while the log runs. Found in minutes what four static
       searches missed.
   * **Code review of the tools since b142a18 (2026-10-30 03:05, 10 findings)** - fixed: `fix_cloth` changed any
     word of a matching block (now only the s16 defect itself, so a raw word kept by `tag404` can't be undone) and
     skipped a block ending at the section end (off by one); `script_u16array_fix` took every `{n, ptr->next}`
     array (now entry lists only - the first entry is a pointer target, the next ones follow it -, PC words that
     are exactly the whole-word swap, non-zero elements, mapped values <= 0xffff; DLC 2 stage 2b 127 -> 125 arrays,
     the 2 left out are not entry lists; the test-16 tree rebuilt byte-identical); equal u16 halves are reported
     as `s32=s16` instead of a defect; `cdb_time_summary` survives a cut-off log; `dlc_section_compare` refuses a
     section of another type; `shader_find` skips a malformed ShaderLib instead of aborting. Documented, not
     changed: TIN/TOUT pairing ignores the thread (the stepper ran on the main thread); **`cloth` and `uipath` are
     post-passes - the root causes sit in the converter** (the learned type-7 word class; Symbols mapped in class
     tables but not in inline u16 arrays) and belong there in a later converter change; `fix_cloth` repeats
     `fix_tag404`'s loop (one shared helper later).
   * Author's history (found only now - a forgotten jump point): `tools/generalbank_dlc.py` (2026-10-09) already put
     the converted TU script 6 into the PC generalbank (same native-93 neutralisation at 0x7928); his note in
     `tools/dlc_generic.py` says "replacing it crashes the base game (gb1.dmp)", so he patched DLC 1's start script
     instead (`cine_nowait`: 20068 no longer waits for the loading screen's broadcast). DLC 2's start script needs the
     same if the loading screen route fails; with the TU script working, the broadcast may come from script 6 itself.
   * Consequence beyond script 6 (to check): DLC scripts are converted with the same init rules. B138 DLC 1 runs, so
     the common cases work there, but any DLC script whose init blocks carry u8 / u16 / glyph fields may be wrong the
     same way.
   * **Offline afternoon 2026-10-30 (no game runs; test trees prepared for the owner)**:
     * **DLC 2 waterfall = material 26812** of `streamgroups\dlc2_goo_room_goo_room_all.drm`. New
       `tools/shader_peer_report.py` (per material of an Xbox DLC DRM: shader tuple, `shader_map` class per library,
       constant / sampler names, most similar base libraries with the base objects that use them, `--summary`,
       `--words` = render-state words Xbox -> PC of the base materials with the same tuple). The spout object
       `dlc2_goo_spout` is NOT the cause: its scrolling material 25265 uses the base libraries 158-161 exactly
       (class A) and its render-state word `+0x4c` converts `7f060001 -> 0103037f` like all 29 base materials with
       that tuple; its other two materials are lit rock (normal maps, lights). In the room's streamgroup 26 materials
       have no base twin; 26812 is the only animated, unlit one (`TimeVector` in vertex AND pixel shader, "Setup"
       param textures, no light constants) - a new DLC 2 shader (pixel pass 0 class D, pass 2 C3, even the vertex
       shader C1) whose surrogates have similarity **0.073 / 0.128** (practically random). Its textures: eitr worms
       (7000), a green normal / distortion map (7001), blue water (6957), grey noise (6999) - the blue-white /
       grey-streaked sheet seen on PC. Base counterpart: the eitr falls `ca_ani_goo_falls.drm` (Xbox material 18506
       = PC 14299) use the plain scrolling-texture tuple 158-161 -> PC 201-204 with one soft cyan gradient texture
       (4996). Material 24299 / 24690 (11 textures, cracked mud) is a blended rock surface, not the fall. The walls'
       dark streaks: the 16 materials of the tuple 2344-2347 (e.g. 25124) are new multi-layer blend shaders (a
       "Setup" blend map, five colour + three normal layers); their surrogates score 0.23 (best pass-0 peer
       `co_zip_laptop`, best pass-2 peers base terrain blends at 0.355) - the layers get mixed by an unrelated
       shader. No base object shares them, so a material transplant cannot help: stage 3 (translation) work.
     * New `tools/material_transplant.py`: material from ANOTHER PC DRM into a DLC material (section id kept), copies
       the ShaderLibs / textures it references when missing (refuses sections with external relocations), remaps
       texture ids (`--tex OLD=NEW`), and checks first that the source's per-pass vertex-input lists are covered by
       the destination's. Test trees: `work\rebuild\dlc2_test25a_fall` (26812 := base 14299 with the DLC's blue water
       6957) and `dlc2_test25b_fall` (base texture 4996 copied in); vertex inputs covered, 201-204 already in the
       file; the input file equals the installed one (MD5).
     * **Grapple ring hue (olive / matte) explained**: the base PC shaders 1704-1707 read their samplers in the BASE
       material's roles, the DLC material keeps the DLC register layout (entries `{tex, 0, role, 0x0002RR00}`):

       | register | base 16637 expects (role, texture) | DLC 21164 / 20345 binds |
       |---|---|---|
       | s0 | 3, 5258 normal map (DXT5 512) | 7, 6580 (64 x 64 mask) |
       | s1 | 1, 5257 colour | 1, 6770 colour |
       | s2 | 7, 255 white dummy | 2, 6770 colour again |
       | s3 | 5, 5570 red mask | 4, 4796 black |
       | s4 | 2, 5254 dark specular | 3, 6463 **green normal map** |

       So the specular term is tinted by the normal map (olive) and the surface normals come from a mask (matte).
       Test trees: `dlc1_test26a_ring` (far + near LOD of wall and ceiling := base material 16637 with its own
       textures = exactly the base ring) and `dlc1_test26b_ring` (base material, DLC textures by role: normal 6463,
       colour 6770, specular 6770; dummy 255 and mask 5570 copied). Same rule as before, extended: **with base
       shaders, take the base MATERIAL (texture slot roles + params), not only the shader ids**.
     * Toward automating it: new `tools/dlc_base_twins.py` (DLC DRM names without `dlc1_` / `dlc2_` / `dlc_` against
       base PC names without a level prefix): **16 of 277 DLC DRMs have a base twin by name** (grapple ceiling /
       wall, `dlc1_ei_hpole_a`, dispatcher, doppelganger, checkpoint, `dlc_fx_cine_snow`, the reused Yggdrasil halls,
       `g_pda`, camerashakes). The swing pole `dlc1_ei_hpole_a` needs nothing: its 4 materials are class A (exact base
       shaders); the ring's two are D / C2 / C3 with no base material of the same tuple. Rule for a pipeline step:
       DLC material with a class C / D library AND a base twin -> base material via `material_transplant.py`
       (vertex-input check), texture roles kept from the base.
     * **Hint box: TU generalbank script 10 ported (test 27 prepared)**. `tools/generalbank_dlc.py --scripts 6,10`
       converts TU script 10 -> PC script 9 (5 636 bytes; plus TU script 21239, identical to the one already in
       B138); a fresh build of script 6 alone is NOT byte-identical to B138's generalbank, so only the two sections
       were put into the installed file (`drm_put_sections.py ... 8:9,8:21239 --add-missing --xbox generalbank.drm`:
       1 call offset remapped, no UNRESOLVED). New `tools/script_word_classes.py` (same-layout script pair, word
       classes): script 10 -> 9 = 928 same / 50 swapped halves / 106 other / 325 relocations. The swapped halves are
       right in the header (u16 pairs, the retail PC script has them too) but **wrong in the TU-only text elements**:
       colours `ff606060 -> 60600140`, `4 -> 0x40000`, `-1.0f -> 0000c160`, string id 1293 as Symbol 1322. The
       retail Xbox script 10 holds one of these records byte for byte (+0x670 = TU +0xd40), so Crystal's own PC
       conversion of it is the template: new `tools/script_record_template.py` (per position u32 / bytes / PC
       constant, string id via the locmap): 19 words in 4 records, "Press [A] to continue" -> PC 5178. TU script 10
       has no inline u16 path arrays (`script_u16array_fix.py --tu-ported ... 9=10`: 1 section paired, 0 arrays).
       Tree `dlc2_test27_hintbox` (generalbank only, on top of test 18). Risk: the other converted words of the
       TU-only part are unverified (no template), and script 9 is global - base-game hints use it too.
     * **Code review of the tools since 2afc5f1 (11 findings)**, checked one by one: fixed - `uitext` pattern B could
       hit a one-element u16 path array (now skipped and counted), pattern A had no upper id bound (now 1284-1406),
       loop bounds one word short (3 places); `b138_fix_tree` rmtree guard (now `build_util.check_out`: below
       work/rebuild, apart from PRISTINE); `b138_snapshot` exited 0 with missing files and merged into an old OUT
       (now exit 1 and a fresh OUT); `tree_merge` ignored a missing input folder, could write its manifest outside
       OUT and failed on another drive (all fixed); inherited `TRUDLC_PACK_FIRST` / `TRUDLC_LOCMAP` could switch the
       pipeline's DLC 1 fixes (now cleared for the run and restored afterwards); `material_shader_swap
       --add-libs-from` copied sections with external relocations (now refused); `pack_records` matched `pack1`
       to pack10 (exact name now). Documented, not changed: `uitext --ported` has no Xbox section to compare with
       (prints every rewrite; script 6: 1 record); the DLC 2 input of `Fixes` (`dlc2_asm_stage2a`) is still built
       by hand (no DLC 2 Convert step in the pipeline yet). Found on the way: `script_u16array_check.arrays()` read
       past a truncated Xbox section (crash, not a silent skip as assumed) - fixed. Checks: `uitext` on the DLC 2
       input with the new guards = **120 elements + 150 hint entries, 0 skipped** (the guards change nothing in the
       data); the Repair step re-run after the fixes is **byte-identical, 334 / 334 files** (275 pristine + 59).
     * **DLC 1 decision prepared as test 28** (`work\rebuild\dlc1_test28_ui`, 10 DLC 1 DRMs, B138 + repair tree as
       input, all 10 equal to the installed files): `uipath` with pack10 = **25 arrays in 10 files** (as counted
       before); `uitext` = 26 text elements + 12 hint entries matched (ids 1286 / 1289 / 1290 x24 / 1374 x12), but
       **only the 26 elements change - B138's 12 hint entries already hold PC ids** (correction of the "38 unmapped
       records" above: 26). What they are (`tools/locals_find.py`): 24 elements are Xbox 1290 "Warning: You do not
       have an update required to play this level ... Xbox Dashboard" - B138 maps it as Symbol 1319, so the PC would
       show "Press [Y] to pull on the grapple line"; one each 1286 "Continue" and 1289 "TEST WEAPON". The message
       never appears on PC (the engine's DLC / update queries are stubs, `menu_dlc_patch.py`), which is why the 25
       unmapped timeline paths of the same UI never crashed DLC 1. **Owner's decision (2026-10-30): apply both fixes
       to DLC 1 too** - the stubs stay (wanted: there is no Xbox update on PC), only the latent crash and the wrong
       text go. `dlc_fixes_build` runs `uipath` / `uitext` for both DLCs now (`srcs` = read folders, so
       `b138_fix_tree` reuses them as its new step `ui`); the repair tree has **69 files** (59 + these 10), the 10 are
       byte-identical to test tree 28, the other 59 unchanged. `Fixes` re-run (log
       `Invoke-TruPipeline_Fixes_20261030_145413`, 1 724 s, all exit 0): DLC 1 `uipath` 25 arrays, `uitext` 26 elements
       **and 12 hint entries** - our rebuild had the hint entries as Symbols too, B138 not, so the author had the
       string id map at least for those; DLC 2 still **292 / 292 identical** to the tested state.
     * New pipeline step `Dlc2` (`dlc_media_build pack11`, `dlc_assemble_build --pack pack11`, `dlc_audio_build
       --pack pack11`, `tree_check`): the DLC 2 input of `Fixes`, until now built by hand (review 2, finding 7). The
       hand-built `dlc2_asm_stage2a` and `dlc2_asm_stage2a_p11` (`--pack pack11` audio) are identical (293 / 293).
       **First run** (log `Invoke-TruPipeline_Dlc2_20261030_*`, 2 431 s, all exit 0, 166 / 166 DRMs ok): its
       `dlc2_asm_stage2a` is **identical to the hand-built one, 293 / 293** - DLC 2 is now reproducible from the
       pipeline end to end (Convert ... Assemble, Dlc2, Fixes).
     * **Owner's tests 2026-10-30 ~15:45** (screenshots `references\DLC1\PC-Test26a-*`): **26a ring = rusty copper with
       highlights, holder without highlight** - close to the Xenia reference; adopted: `b138_fix_tree`'s ring step
       now also transplants the base material 16637 into both LODs (the two files are byte-identical to test tree
       26a). **28**: DLC 1 runs as before (nothing visible expected); the loading-screen title is still missing
       (separate point). **29** (lookahead encoder): Lara's "s" sounds still crackle in game, Zip (a radio voice,
       band-limited) sounds fine.
     * **Voice lines have language variants too**: the five DLC 1 radio / voice streams
       (`audio\streams\vo\dlc1\lara|zip\*.mul`) exist in five languages in pack10 (specs as the cinematics);
       `music_convert.convert_streams` and B138 write only the English record. `mul_lang_build.py` now also writes
       every localised `audio\streams` .mul as `<path>_NNN` (B138's English voice lines measure 14-33 dB against the
       decoded Xbox source, ours 32-36 dB, so the plain name gets our English conversion); pack11 has no localised
       voice streams. Repair tree: **99 files** (24 shader + 10 ui + 35 cinematic + 30 voice).
     * **The crackling "s" (Lara, intro)**: WAVs of the Xbox source, our current encode and the lookahead encode
       (`ima_encoder_check.py --wav`, decoded with our model of the game's decoder) sound **identical** to the owner -
       so our encode is fine as we decode it, and the game must play it differently. Lara speaks "live" with full
       high frequencies, Zip over a radio filter - a decoder mismatch grows with frequency, which fits. The nibble
       convention was measured on base MUSIC (finding 18), never on cinematics; measuring it on Crystal's base
       cinematics (`tools/mul_convention_check.py`, cross-correlated lag) is inconclusive - their PC streams match
       the Xbox ones only to 3-16 dB (a different mix / edit), whatever the convention. Listening tests instead:
       **test 30** = German intro at -6 dB (if the crackle goes: the game's mixer clips), **test 31** = the same with
       the FSB nibble convention (if the crackle goes: cinematics are decoded as FSB) -
       `work\rebuild\dlc1_test30_audio`, `dlc1_test31_audio` (`ima_encoder_check.py --write ... --gain -6`,
       `--convention fsb`). **Owner's results (~16:15)**: 31 (FSB) is worse, even Zip - **the game convention is
       right** for cinematics too; 30 (-6 dB) a little better, the high-frequency crackle stays - clipping is at most a
       small part. Crystal did not cut the highs for PC either (`mul_convention_check.py`: power above 8 kHz, PC vs
       Xbox, 0.10 / 0.14 %, 1.08 / 1.09 %, 8.39 / 5.07 % on three German base cinematics). Base-game check by the
       owner: Lara's German "s" sounds in the prologue / boat cinematics are **cleaner** than in our DLC intro - so
       Crystal's PC encodes handle sibilants better than ours (they also differ from the Xbox audio by 3-16 dB, a
       different master or encoder). Open.
     * Waterfall, owner's test 25a: unchanged (blue-white, opaque) - material 26812 is most likely NOT the fall
       (screenshot `references\DLC2\PC-Test25a-*_08`). Marker test 25c (`tools/material_paint.py`, new: all texture
       references of a material -> one marker texture): 26812 -> green normal map 7001, `co_dlc2_goo` -> black /
       white blocks 7386, `dlc2_uo_goo_upcolumn` -> rust 7390, `dlc2_goo_spout` -> flat lime 7388
       (`work\rebuild\dlc2_test25c_paint`, 4 files equal to the installed ones before painting).
       **25c: no colour anywhere** - none of the four. **25d** (every material of the room's streamgroup -> 7001, the
       pool surface DRM -> 7386, all 44 eitr effect / object DRMs -> 7390): only the splashes changed (effect
       particles) - the streamgroup's materials are **ignored because the same material ids were already loaded
       from `dlc_level2_start.drm`** (e.g. 24299 sits in 8 DRMs; the engine keeps the first section of an id - a rule
       for any later paint or material fix: change the FIRST loaded copy). **25e** (`dlc_level2_start.drm`: 24691 ->
       7001, 24920 -> 7386, its other 23 materials -> 7390): **the fall shows the block marker = material 24920**;
       with the marker (DXT5 with alpha) it even turns partly blue-translucent. Screenshots
       `references\DLC2\PC-Test25c..e-*`.
     * **What 24920 is**: the base game's eitr water-surface material on a vertical mesh. Its tuple 820-822 is class A
       (exact base shaders -> PC 1593-1595, the tuple of base 7990 `l5_valaskjalf` / `l7_helheim01` /
       `l7_yggdrasil_hall02` and 11578 `ar_goo_watersurface`); the render-state words convert like the base pair
       (`7f060008 -> 0803037f`, `01070700 -> 00070701`); the texture entries have the same roles / registers as base
       14311; the textures are the same images as the base pool's (`tools/texture_channels.py`, new: RGBA mean /
       std per channel - 7001 = 4975, 6999 = 4972, 6957 = 4973, 7000 = 4974, also after DXN -> DXT5); only the
       material parameters differ (e.g. 30.0 vs 4.0 at +0x564) and are copied 1:1 like Crystal's base conversion.
       So the material conversion is right; what differs from the Xbox must be the geometry / vertex data of the
       fall (e.g. vertex colour or alpha) or how the PC port of the shader treats a vertical surface with these
       parameters. Mesh 22994 (the one unknown vertex format) is a switch object, not the fall. Next: find the fall's
       geometry in `dlc_level2_start.drm` and compare its vertex colours / alpha with the Xbox; check a base PC eitr
       surface with this tuple in game.
     * **Geometry checked, cause found (most likely)**: new `tools/terrain_batches.py` (draw batches of a terrain
       section per material, vertex format, D3DCOLOR statistics, Xbox / PC): the fall is batch Y 64 of terrain
       20085 (31 360 vertices, stride 32: position, normal, two UV sets, **vertex colour** - alpha mean 117, range
       0..255); format and colours are identical on Xbox and PC. The base water surface with the same material tuple
       (`l7_yggdrasil_hall02`, terrain 11740 / 19280) has no vertex colour and one UV set. The Y record holds
       `cccccccc 4 cc cc` (uninitialised build-tool bytes) on both platforms - the Xbox renders with them, so not the
       cause. New `tools/shader_slots_compare.py`: Xbox vertex-shader library 822 has 72 permutation slots, Crystal's
       PC 1595 only 60 - **missing 40-42, 104-106, 168-170, 232-234** (bits 8 + 32: most likely second UV set +
       vertex colour, exactly the fall's format; the base game never needed it, so the PC library was built
       without it). The PC therefore draws the fall with a variant that ignores the vertex alpha: opaque. Test 25f
       (`tools/shader_slot_fill.py`, new: empty slots point at an existing entry, only the slot table changes):
       1595 in `dlc_level2_start.drm` (the first loaded copy) with 40 <- 32, 104 <- 96, 168 <- 160, 232 <- 224 (and
       +1 / +2) - vertex colour kept, the second UV set's effect lost (`work\rebuild\dlc2_test25f_vslots`).
       Pixel libraries 1593 / 1594 have more slots on PC than on Xbox (no gap).
       **Result: 25f and 25g (the same slot fill in all 22 DRMs that carry 1595) change nothing** - the grey column
       stays opaque, the translucent blue sheets were there before as well. The missing variants are not the cause
       (or not the only one); kept as a dead end. Next: number textures on the 8 slots of 24920 (which texture lands
       on the column), and which shader variant is really bound (debugger).
     * **Debugger session with the owner (2026-10-30 17:14-17:23)**: `cdb` attached to the running game
       (`session_titles.cdb` in the workbench: GetLocalString +0x9a7a0 for ids 59 / 5169-5170 / 5173 / 432 / 450 /
       451 with caller, max 15 each, and every new UI timeline +0xcfc00 with a time stamp, max 300; caps disable the
       breakpoints instead of quitting - the game ran on and was quit normally). Note: in a `cdb` script a `;` also
       ends a `$$` comment. Results: base text 59 ("Was bisher bei Tomb Raider geschah...") and the DLC descriptions
       5170 / 5173 are fetched ONCE through `tru+0x19e289` (set the text of an element); the DLC 1 title 5169 first
       through `tru+0x1a0580` and then **every frame through `tru+0x1a7a42`**, called from the UI draw loop
       (`+0x1c5a3a` -> `+0x1e0146`) - the same path the visible menu names 450 / 451 take. So **the title element is
       drawn, only invisibly** (alpha, position or scale). The base loading screen's title "TOMB RAIDER: UNDERWORLD" is
       a separate element above the line (screenshot `references\Basisspiel\PC-20261030_Basis_Ladebildschirm_*`) and
       visible - next session: log its id and compare its element data with the DLC title's (first argument of the
       draw-path call). 171 UI timelines were created in the session (9 at the DLC 1 loading screen, 17:19:32).
     * Loading-screen layout (owner's screenshots): base and DLC 2 text start below the line; **the DLC 1 text starts
       one line higher, on the line** - most likely the text block is centred vertically and the German DLC 1
       description has 4-5 lines (DLC 2 / base 3); to confirm with a shortened test string.
     * **Xenia snapshots (owner, 17:31 / 17:35)**: `cdb -pv` on `xenia_canary.exe` (frozen, read-only,
       `xenia_snapshot.cdb`); the emulated Xbox memory sits in Xenia's process at host 0x1_00000000 .. 0x3_00000000,
       mirrored several times (virtual and physical views). Found: the title texts and the TU script 6 title record
       (one place, four mirrors, the same in both snapshots) - static script data, not the live UI object. The dumps
       around the hits failed (loop variable `a` read as the hex number 0xA - renamed). In Xenia the outfit / weapon
       choice waits for its fade-in animation too: original behaviour, not a port defect.
     * **Waterfall, test 25h (`tools/texture_digits.py`, new: numbered A8R8G8B8 textures 1-8 with a grid per material
       slot; ids from unused gaps below the highest DLC texture id, 7669 / 7683-7685 / 7895-7898; the base game uses
       up to 6438)**: the opaque column shows **slot 2** (originally 6999, grey noise) at full strength; where the
       digit is black the column is see-through - the column is drawn **additively**, so the mid-grey noise looks like
       an opaque wall. The pool turned too: it is the same material 24920 (the "rust" in 25e was the block marker at
       a grazing angle). The translucent blue sheets are another material and look right. So on the vertical column
       slot 2 comes through unattenuated; on the Xbox reference the fall is a soft bright glow - the attenuation
       (most likely the vertex alpha, mean 117 / 255, or a term the PC port of the shader handles differently) is
       missing. Pragmatic test next: slot 2 of 24920 only, darkened (~0.45) as a new texture; proper fix: translate
       the shader (stage 3).
     * **"Skip cinematic" bar**: PC "(A) JA - Zwischensequenz überspringen? - (B) NEIN" spread over the width, Xbox TU
       "SKIP CINEMATIC? (A) YES (B) NO" grouped on the right (`references\DLC1\Xenia-TU_DLC1_10_*`) - a layout
       difference, most likely another title-update UI script like the hint box. Lead: the question (TU 982, PC
       1283) is pushed by TU generalbank scripts 7 / 38 / 74 / 199 and by PC scripts 7 / 37 / 74 / 201
       (`bigfile_find.py`); which of them lays out the bar is open.
     * **Waterfall, test 25i** (`tools/texture_scale.py`, new: one slot of one material gets a scaled copy of its
       texture under a new id; slot 2 of 24920 at 0.45, mean 97 -> 43): the column now shows the **green-yellow
       normal map** (slots 1 / 5) and, from afar, the worm / mud textures - on the vertical column the shader adds
       several textures as raw colour, the normal map included (which should only distort), while the pool with the
       same material looks right. Darkening is no fix; the vertical case of this shader is the problem (stage 3), or
       a separate material for the column (it shares terrain batch Y 64 with the pool, so splitting needs a new
       material index - not done).
     * **Debugger run 2 (17:54-17:58, `session_titles2.cdb`: at GetLocalString for 51 / 5169 / 59 / 5170 registers,
       stack and 0xC0 bytes at each register via `titles2_dump.cdb`, called with `$$><` inside the branch so nothing
       runs for other ids)**: the visible base title is string **51 "TOMB RAIDER: UNDERWORLD"**; both titles are
       fetched every frame through `+0x1a7a42` with the text element object in `esi` (same class, vtable
       `008533ac`). The objects differ in their property blocks ({owner, type, value, 0} from +0x50): base +0x80
       (another type, a boolean) = **1**, DLC = **0**; base +0x60 = a pointer, DLC 0; +0x70 0x100 vs 0xdc6800.
     * **Cause of the invisible loading-screen title found**: `tools/script_text_records.py` (new: every UI text
       element record `ffffffff|00ffffff 0 colour colour | id w1 w2 w3` of a script, `all` = scripts with w2 = 0)
       on PC script 6: Crystal's retail script 6 has 10 records, all with **w2 = 0x00010000**; the ported TU script 6
       keeps that for its 10 retail-part records, but its two **TU-only records have w2 = 0**: the DLC 1 title
       (5169, +0xe930) and - newly found - **the DLC 2 title (+0xea40) with the unmapped Xbox id 410 "LARA'S SHADOW"
       (= PC 432 "LARAS SCHATTEN")**, which `uitext --ported` skipped because 410 lies in the base range. w2 is the
       word whose PC value we already met as a "PC constant" in the retail hint record (finding: TU script 10), and
       it matches the boolean property 1 / 0. **Test 32** (`work\rebuild\dlc_test32_title`, generalbank only, new
       `tools/script_word_set.py`: set words only when the old value matches): +0xe948 0 -> 0x10000, +0xea50 410 ->
       432, +0xea58 0 -> 0x10000. After it no record in generalbank has w2 = 0.
     * Same pattern in the DLC level scripts (`script_text_records.py ...:all` over the play tree): one shared new
       script in most DLC 1 and DLC 2 levels has two records (+0xe70 / +0xf80: 5175 the Xbox "update required"
       warning, 5259 "returning to main menu in...") and DLC 1 `dlc_dungeon` script 23339 one ("Continue", 5171) -
       all with w2 = 0 **and w1 / w3 in swapped halves** (`00040000`, `000c0000`), the defect of the TU hint box
       before `script_record_template.py`. Harmless for the never-shown update message; a general stage-2b fix
       (records of new DLC scripts converted with the retail template rules) is the clean follow-up.
     * **Which generalbank carries the loading screen**: B138's own `generalbank` keeps the PC **retail** script 6
       (66 900 bytes, no DLC branch - B138 starts DLC 1 through its start-script patch `cine_nowait`), which is why
       B138's DLC 1 loading screen shows no text at all (`references\DLC1\PC-B138-Test-20261029_*`). The installed
       file is OUR port of TU script 6 (75 348 bytes, DLC 2 tests 2-13, then test 18's id mapping) - the only one with
       the DLC description and title records. So the title fix (test 32) belongs to the build of our generalbank,
       which is **not a pipeline step yet** (DLC 2 tests 2-13 built it by hand: `generalbank_dlc.py`, vtable insert,
       PC init values, `drm_put_sections.py`) - to be made a step, with `script_uitext_fix.py --ported` and the
       record words.
     * **General record fix, measured and prepared (test 34)**: new `tools/script_records_dlc.py` (every UI text
       element record of the new DLC scripts against the retail template rules `s32 s32 s32 s32 s32 s32 pc s32
       bytes s32 ...`, Xbox section and PC section have one layout; string id and relocation words untouched):
       DLC 1 **38 records / 234 words in 10 DRMs** (the update-warning records, incl. -1.0f stored as `0000c160`),
       DLC 2 **104 records / 645 words in 15 DRMs** (the same shared scripts, a runtime-filled record at +0x10a0,
       and in our merged `g_pda` script 26427 the PDA buttons Xbox 353 "BACK" / 98 "SELECT" = PC 375 / 5138 - the
       merged g_pda is not in use yet). Test tree `work\rebuild\dlc_test34_records` (24 DRMs of both DLCs, from the
       installed play tree; the pack10 and pack11 runs give byte-identical DLC 1 files). Mostly never-shown text, so
       the test is "both DLCs still run"; then a stage-2b fix `uirecord`.
     * **Menu wait (stage C of the multi-step test)**: the session-1 timeline log shows, per menu screen (outfit,
       weapon, ...), 13 UI timelines created at once; each group has one with keys `0 4 4 0` (most likely a 4-second
       timeline) and one with `0 0.5 0.5 -20`; the loading screen's group has `0 7 4.5 50` and several `0.5`. Lead
       for the owner's idea (make the choice usable at once): the 4-second timeline - shorten its key time in the
       script descriptor and see whether input is enabled earlier. Not tried.
     * **Test 32 + 34 in the game (owner, 2026-10-30 evening; installed: play tree + test 32 generalbank + test 34
       records)**: both DLCs and the base game run; **the record words alone do not show the titles** (DLC 1 / DLC 2
       loading screens as before, `references\DLC1\PC-Test32u34-*_17_*`, `references\DLC2\PC-Test32u34-*_26_*`;
       base loading screen unchanged). The hint box still has no frame (`..._27_*`). So the boolean at element +0x88
       is set at run time, not copied from the record's w2.
     * **Live debugger: the visibility switch confirmed (18:41 DLC 1, 18:51 DLC 2)**: `session_live.cdb` (workbench)
       breaks at GetLocalString +0x9a7a0, and for id 5169 / 432 on an element with vtable `008533ac` runs
       `knobs.cdb` - a one-line file that can be edited while the game runs - and logs the element's property blocks
       every 120th frame. With `ed @esi+0x88 1` (the boolean property found in debugger run 2) **"UNTER DER ASCHE"
       and "LARAS SCHATTEN" appear above the line** like the base title 51 (`references\DLC1\PC-Test32u34-Live-*_18_*`,
       `references\DLC2\PC-Test32u34-Live-*_28_*`). The title elements are complete (text, font, position); only
       the boolean +0x88 = 0 hides them. Open: which script code sets it for the base title (the permanent fix,
       part of the generalbank build). The DLC 1 text still starts on the line with the title shown.
       Side note: in the first session the game sat in the outfit list after a long pause (preview did not change);
       two read-only snapshots (`cdb -pv`) showed the main thread drawing at 60 fps and no loader thread busy - the
       game waited, no deadlock; not reproduced, not investigated further. (A second "endless loading" in the
       outfit list later the same evening was no hang: the level only goes on loading after the choice is
       confirmed - the owner's wording, not a defect. The first case, where the preview did not react, stays open.)
     * **Windowed mode and a live debugger with a command channel (evening)**: with TRAWindowed (`Set-TruDisplay.ps1
       -Windowed`) the game runs in a window and keeps taking controller input while another window has the focus.
       The installed `tru.exe` (no Steam stub, `steam_appid.txt`) starts directly while Steam runs, so the game can
       be started UNDER `cdb` with the owner's Steam option reproduced: `cmd /c start "" /b /wait /affinity FFFF cdb
       -hd -cf session_live2.cdb tru.exe` (module name then `tr8_win32_gm` instead of `tru`). Pitfalls: right after
       the start the GetLocalString breakpoint sees `esi = 0` - a failing `poi(@esi)` aborts the breakpoint command
       before `gc` and cdb, reading EOF from stdin, quits and takes the game with it (guard: test the string id first,
       then `esi > 0x10000`); inside a quoted breakpoint command paths need `\\`; an EMPTY command file fails with
       Win32 error 87. The command channel: every 30th GetLocalString call runs `cmd.cdb`, which can be rewritten while
       the game runs (no text fetches in the main menu, so it acts from the loading screen on) - e.g. to set new
       breakpoints live.
     * **UI timeline keys are (time, ?, ?, value) rows**: a timeline created at level start (the loading spinner) has
       keys `0 0 0 0 / 0.4 0 0 360 / 0.8 0 0 0` - first column time in seconds, last column the value (degrees). So the
       menu timeline `0 4 4 0 / 0.5 4.5 4.5 0` is NOT a 4-second timeline (about 0.5 s; the 4 / 4.5 are other key
       fields): the "menu wait" lead above is most likely wrong. A live patch (4 -> 0.5) did not apply anyway - the
       weapon menu's timelines were created before the breakpoint was set (with the outfit menu). Next try: set the
       timeline breakpoint at the loading screen and log all menu timelines with their times.
     * **Test 33 (title bits + ported TU script 10, hint box) crashes at the DLC 2 level load** (2026-10-30 19:33,
       under cdb): access violation at address 0 - the script interpreter's native call at `tru+0x17deae`
       (`mov ecx,[ecx+14h]` - `call ecx`; the function pointer of the called native's descriptor is 0). The same
       class as finding 42's TU-only native `uigamedata` 93: the ported script 10 most likely calls a function the PC
       exe does not implement (call offsets were remapped without UNRESOLVED, so a vtable slot / inherited native is
       the likely path). Test 27 (the same script 10 on top of test 18) was never played, so this is its first run.
       Next: breakpoint at `tru+0x17dea3` with `poi(@ecx+14) == 0` to dump the descriptor (name Symbol) and the
       caller; then NOP or redirect that call like `script_nop_call.py` did for script 6. Test 33 uninstalled again.
     * **The null native is `dlc2data` f0 (offline + live, 19:42-19:47)**: offline (new `tools/script_func_list.py`,
       details in the workspace note `docs\Befund-Test33-Native.md`): the TU-only native type `dlc2data` (script
       21239, package `game/script/game/game`, f0 +0x54 name Symbol 3955 / PC 4124, f1 +0x70 19728 / 20208, no script
       code) is unknown to `tru.exe` (no name string), so its descriptors keep a null function pointer; our ported
       script 9 calls it 5 times (f0 at +0x43c / +0x960, f1 at +0x754 / +0x864 / +0x9b8), Crystal's PC script 9 never.
       A conditional breakpoint before the call (`tru+0x17dea3`) is far too expensive - it fires on every script
       native call and stalled the level load; instead the AV handler reads the descriptor from the script operand
       (`[[ebp+0xc]-4]`), logs it and skips the call (`eip = [esp]`, `esp += 4`, `eax = 0` or `1`, `gh`). Live: 5
       calls, all f0 at the same site, name Symbol 0x101c = 4124 - confirmed. With the calls skipped the level runs,
       but **no hint at all** appears at the wall (not even the text that showed without test 33) and the screen is
       white for ~10 s after the level start (`references\DLC2\PC-Test33-Live-*_29_*`), with f0 = 0 and with f0 = 1.
       So `dlc2data` explains the crash, not the missing box; the other defects of the port the offline check found
       are the next suspects: the prototype count at +0x1020 is `0x000b0000` (u16 halves swapped, should be 11) and
       the vtable is still in the Xbox layout (script 9 inherits from 93; vtableSize 35 with Xbox vtIndex 31-34,
       Crystal's PC script 9 has f1 at 32 and f4 at 33 - needs `script_vtable_insert.py ... 9 31` and vtIndex + 1
       like script 6). Test 35 = test 33 with these fixes and the `dlc2data` calls replaced.
     * **Tests 35 / 35b / 36: the hint box works (2026-10-30 evening)** - details and every changed word in the
       workspace note `docs\Befund-Test33-Native.md` ("Test 35 build", "Test 36 build"). Script interpreter opcodes
       checked in `tru.exe` (jump table `tru+0x17e52c`): `op04 N` pushes byte N, `op06 N` a local, `op09 N` the
       ADDRESS of local N, `op0f N` an object member, `op64 N` jumps on 0, a native call (`op65`) pushes no result -
       `dlc2data` f0 writes its result through a pointer into a local, so the live "eax = 0 / 1" skips never reached
       the script. Test 35: prototype count +0x1020 `000b0000` -> 11, vtable 35 -> 36 entries (entry 31 inserted from
       Crystal's PC script 9, vtIndex f1/f4/f8/f10 + 1), the 3 f1 calls NOPed, the 2 f0 calls -> line markers and the
       consuming `op06` -> `op04 0` (35) / `op04 1` (35b). In game: 35 = white screen ~10 s after the level start, no
       hint at all; **35b (f0 = 1): the hint LOGIC works** - the game pauses at the wall, plays the box sound and
       waits for A - but nothing is visible; a live probe forcing every drawn text element with bool +0x88 = 0 found
       none (the box texts were not drawn at all). Test 36 (`tools/script_init_dump.py`, `script_init_from_pc.py
       --xbox-id`): the converter had broken the element init blocks of script 9, old and TU-only elements alike
       (the leading 1 -> 65 536 as in script 6, both size floats converted like Symbol numbers - the TU image element
       17480 had -1.1e8 x 5.8e35 instead of 0.8 x 1.66 = the full-screen white quad -, colours); 10 words set to
       Crystal's PC values, 6 from learned rules, element 17478 by hand, f9's name 333 -> 517. **Played (f0 = 1, md5
       685bf6d5..., kept as `work\rebuild\dlc_test36_played_685bf6`): the hint box shows like on the Xbox** - Lara
       icon, German text with LB/RB glyphs, "Drücken Sie A, um fortzufahren.", top centre, the game waits for A
       (`references\DLC2\PC-Test36-*_30/31_*`); only the dark translucent box background is much fainter than on
       the Xbox. A later revision of the build set a shared cell (+0x12e0, probably a font number) from the TU's 8
       back to the PC's 3 (md5 4e4579e5...) - not played; the played 8 works, so it stays. Also found offline
       (`tools/drm_section_ids_diff.py`): the TU generalbank carries sections the PC one lacks - 14 textures (7036,
       7171, 7215-7219, 7350, 7669, 7895-7899), section 37 (probably a font), 21237 / 21238 / 22194, 267-269; not
       needed for the box as played, but note that test 25h's "free" digit texture ids 7669 / 7895-7898 collide with
       them.
     * **How the mission screen starts a DLC (traced live, `session_trace.cdb` / `session_test35.cdb`)**: the
       `dlcsystem` natives (bound in `tru+0x3b3f20`: f0 `7a40a0`, f1 `7973c0`, f2 `7973e0`, f3 `797400`, f4/f5
       `797420`, f6 `797430`, f7 `796620`) run only at the main menu (f7 once, f1 28 times - probably the DLC
       availability check), not at the start. On "start" the mission screen script 104 calls `uigamedata` f22
       (`7a0d00` -> `tru+0x37bc90`, no arguments) and right after it f27 (`7a0d40`, three bools from the argument
       block: true, false, true -> `tru+0x37e170`); its third `uigamedata` native f37 (`7a0e90`, returns a bool)
       runs every frame in the level. Found through the native type objects: each type registers its natives by
       index in vtable slot 3 of its type object (`uigamedata` binder `tru+0x3af0c0`). Lead for a direct test start
       (owner's idea: skip the menu clicks): which earlier call names the DLC level - then a test-only script patch
       can make the main menu start it at once.
     * **Hints: the modal box is DLC 2 only (Xenia reference, 20:21-20:25)**: on the Xbox with the title update the
       DLC 1 hint "Press up to use a health pack" is shown top right in a faint box, without "press A" and without a
       pause (`references\DLC1\Xenia-TU_DLC1_11_*`); in DLC 2 every hint is the modal box - the shadow meter one with
       Lara icon and a clearly dark rounded box, the rock vein one without icon (`references\DLC2\Xenia-TU_DLC2_15..19`;
       after A the shadow text stays on screen for a while). Test 36 fixed `dlc2data` f0 to 1, so on PC the DLC 1
       hints became modal too (`references\DLC1\PC-Test36-*_19_*`) - wrong. Offline (new `tools/drm_script_refs.py`,
       details in `docs\Befund-Test33-Native.md` "Test 37 build"): no script of pack10 / pack11 / the TU / the PC tree
       calls `dlc2data` or the hint script - the TU exe decides f0 itself ("DLC 2 level active"); f1 only mirrors it.
       Interpreter opcodes read from `tru.exe` in addition: `op0f` pushes a member ADDRESS, `op0c` / `op0d` / `op0e`
       a member byte / u16 / u32, `op2e` / `op2f` store a byte / u32 through an address, `op31` assigns a string,
       `op4f` compares two strings, `op63` relative jump (24-bit signed), `op64` jump if 0. `dlcsystem` f0 is a stub
       returning false on PC. Plan for test 37: append a code stub to section (8,9) - fetch the current unit name with
       `uigamedata` f34 (`tru+0x3a0e10`, as TU script 6 f9 does), compare it with the 10 DLC 2 unit names
       (`dlc_level2_start`, `dlc_yggdrasil_end`, `dlc_yggdrasil_hall01/02`, six `dlc2_*`), store the result in the
       local f0 used to fill, and jump back.
     * **TU loading screen script 6 (disassembly `menu_dlc_probe.py dis xt 6`)**: function 9 is "current level
       number": it gets the unit name (`uigamedata` f33), maps `l1`..`l8` to 1..8, the DLC 1 unit names to **101**
       ("Loading DLC1 level starting unit!") and the DLC 2 names to **102** ("Loading DLC2 unit..."), else -1 ("ERROR
       in uiloading script. Could not get current..."); it is called from the state function 32. The script holds
       **10 title text elements** with identical record layout - ids 51-58 (base game levels) plus the TU's 5169 (DLC 1)
       and 432 (DLC 2); 101 / 102 appear nowhere else in the script, so the title is most likely picked by an index
       derived from that number - the next question for the title fix. Live trace prepared (`session_titlefix.cdb`):
       logs every bool property set on a text element (setters `tru+0x1ab5e0` / `+0x19c920` / `+0x1ab5f0`, property
       object at element+0x84 with the owner at -4) with the value, the script code pointer (`[ebp+0xc]`, read inside
       `.catch` so a bad frame cannot abort the breakpoint) and the stack - load a base game save once (title 51) and
       start a DLC (5169 / 432) to see which code switches 51 on and whether the DLC titles are ever touched.
     * **Test 37b: hints like on the Xbox in all three parts (played 20:51-20:54)** - `tools/script_dlc2_flag_stub.py`
       appends a stub to the hint script 9 (82 code words + the 10 unit names): fetch the current unit name
       (`uigamedata` f34 + `corebase` f14, as TU script 6 f9 does), compare it with the DLC 2 unit names (`op08 12,
       op05 <string>, op4f, op64, op63`), store the result in local 1 and in the embedded `dlc2data` member (+0x50)
       that now serves as the flag; f9 reads that member, the three f1 calls write it. Test 37 crashed in the base
       game (Lara diving into the sea, the first hint): the stub lacked the `op05` before each string pointer, so a
       pointer word was executed as `op03` and pushed its low 24 bits as a "string" (AV in `op4f`, `tru+0x17dbf3`).
       37b in game: base game hints top right in a dark box, no pause, no crash; DLC 1 medipack hint top right, no
       pause; DLC 2 shadow and rock vein hints modal with pause - all as in Xenia (`references\*\PC-Test37b-*`).
     * **Waterfall test 42 (prepared 2026-10-30 22:40, not played)**: test 25a had transplanted the base game's eitr
       fall material (`ca_ani_goo_falls.drm`, PC material 14299, scrolling-texture shaders 201-204, one soft cyan
       gradient texture 4996) onto the WRONG material (26812); now onto **24920** in `dlc_level2_start.drm` (the fall
       and the pool below it, terrain batch Y 64): `material_transplant.py` (vertex inputs of 14299 covered by
       24920's mesh; ShaderLibs 201-204 and texture 4996 copied in). Base: the installed `dlc_level2_start.drm`
       (md5 b67e513e, test 34 state). `work\rebuild\dlc_test42_waterfall` (base texture 4996, md5 9bca8c87) and
       `dlc_test42b_waterfall_bluewater` (texture remapped to the DLC's blue water 6957, md5 40c250fb); tree_check
       0 errors. Expected: the grey additive column replaced by Crystal's PC eitr-fall look (scrolling, translucent);
       risk: the pool uses the same material and will scroll like a fall. Workspace note `docs\Befund-Wasserfall.md`.
     * **Hint-box background: no texture is missing (test 43, offline)**: a userType-320 bitmap member names its
       texture by section id, made absolute by a kind-A id relocation (new `tools/drm_idrefs.py`): our script 9 =
       TU script 10 references texture 56 (the box, retail member 1274) and 76 (the Lara icon, TU member 17479);
       none of the 14 TU-only generalbank textures (those belong to TU scripts 7 / 38). Texture 56 is identical in
       TU and retail; texture 76 differs between them, but converting the TU section (new
       `tools/generalbank_tu_textures.py`, `tools/drm_section_head.py`) gives exactly the texture 76 Crystal's PC
       generalbank already has. All init words of the three bitmaps equal the Xbox values. So the faint modal box
       on PC is not a data defect of our generalbank - next: compare the box's colour / alpha / scale at draw time
       (PC cdb vs Xenia snapshot). `generalbank_build.py` unchanged (md5 57f52266...).
     * **ASI step 3.1 played (22:47-22:52): the shadow-power slow motion works as a plugin** - no debugger; holding RB / LB
       slows the waterfall (world time) like on the Xbox; rock veins (LB/RB + A) still do nothing (next TU part).
       Test 42 / 42b (base eitr-fall material on 24920): the column turns translucent (42: green eitr colour, 42b:
       blue, with a green stripe left), but the pool shares the material and looks frozen (static) - the transplant
       alone is no fix; fall and pool need separate materials (`references\DLC2\PC-Test42*`).
     * **ASI step 3.1: `TruShadowPower.asi` (built, not yet played)** - the first piece of the title update rebuilt as
       PC code: `src/asi/TruShadowPower/` (C++, no external libraries, `/MT`, imports only KERNEL32), built by
       `scripts/windows/Build-TruAsi.ps1` (VS 2022 x86 toolchain -> `work\asi\`), installed / removed by
       `Set-TruShadowPower.ps1`. Loaded by the Ultimate ASI Loader the installed game ships as `binkw32.dll` (it lists
       binkw32Hooked.dll / *.asi; `tru.exe` itself imports no loader - `ModLoader.asi` is loaded the same way). It
       swaps the stored XInputGetState pointer (0x00a02b8c, called per frame at tru+0x84b82) for a wrapper that, on the
       LB/RB edge, calls the engine's `SetWorldTimeScale` / `SetPlayerTimeScale` with the Xbox values (0.3 / 1.2,
       33 ms; 1.0 on release) - what the debugger prototype of test 39b did. Byte checks at all addresses before
       hooking; `TruShadowPower.ini` / `.log` next to the exe. Active in every level (no DLC 2 check yet); meter, blur,
       rock veins, shadow jump and combat are not covered.
     * **Direct start into DLC 2 for tests (test 41e, played 22:28, works)** - test-only generalbank, never for the
       install; `tools/script_directstart_stub.py`, details in the workspace note `docs\Befund-Direktstart.md`. The
       mission screen (script 104) starts a DLC by writing the unit name to a member and calling `uigamedata` f22, then
       **f27(unit name, 1, 0, 1)**, then closing its screens (`stdscreenmgr` f19 / f7); `dlcsystem` only checks that
       the DRM exists. Hosting the same sequence in the main menu failed three times: script 7 is `uipause` (main AND
       pause menu) whose functions run on events only (41, 41b: never reached); from its OnOpen (41c) f27 ran but the
       frontend was not ready - stuck on the menu background; 41d hooked a branch that is not the attract path. The
       attract (intro) video is started by script 60 `AttractTimer` (f2: "stopTitleMusic", f22, f26 = attract mode);
       41e jumps right after its f22 (+0x538) into the stub: once per game start f27('dlc_level2_start', 1, 0, 1) +
       f19 / f7 instead of f26. Played: start the game, skip the intros, wait in the main menu - instead of the video
       the DLC 2 level loads, outfit / weapon choice works (log: DIRECTSTART 0..4, f27 with `dlc_level2_start`).
     * **Shadow-power slow motion reproduced on PC (test 39b, played 22:08-22:12, debugger prototype)**: live snapshots
       in Xenia (25 snapshots while LB was toggled, `tools/snapshot_toggle_words.py`) showed the TU switching two time
       scales, world 1.0 -> 0.3 and player 1.0 -> 1.2; the TU's selector (0x823d7520) calls the engine's world / player
       time-scale setters with a 33 ms ramp - the same engine system exists in the retail Xbox exe and in the PC exe
       (`SetWorldTimeScale` tru+0x376030, `SetPlayerTimeScale` tru+0x376090, script natives `gamebase` #23 / #24,
       ramps 0x8abeb4 / 0x8abe94, applied in the frame update tru+0x1da4ab). Writing the ramps or the current factor
       directly had no visible effect; injecting the CALLS from a breakpoint right after the per-frame
       `XInputGetState` (tru+0x84b88, LB 0x100 / RB 0x200) did: with RB held the camera turns slower, water and the
       waterfall run slower, Lara keeps her speed (world factor 0.3, player 1.2 in the log); jump height unchanged
       (the longer shadow jump is separate TU code). Next: the same as an ASI, then meter / blur; rock veins and
       combat moves remain TU code to re-implement. Function-level diff of the Xbox exe without vs with the TU
       (`tools/xbox_func_diff.py`): 391 new (~157 KB), 937 changed functions.
     * **Rock vein / shadow power (offline `docs\Befund-Felsrinne.md`, live 20:43 and 20:53)**: all 166 DLC 2 files
       present, terrain materials and textures complete; the markup loader's "Bad Markup Type, disabling markup"
       path (`tru+0x1ce569`) is NOT hit while DLC 2 loads; the HUD shows the shadow meter (green and yellow
       silhouettes), but LB only makes Lara sprint and RB + A at the rock vein does nothing. Most likely the player's
       shadow power (meter drain, long jump, rock vein attach) is code of the title update's exe patch
       (`default.xexp`, 958 KB) that the PC exe never got - the largest missing piece so far. Side finding: the TU
       `achievement` native type has 21 natives, the PC one 16; DLC 1 / DLC 2 scripts reference offsets +0x214..+0x284
       beyond the PC table (B138 too) - a call into the void like `dlc2data` if an achievement fires. The live
       bool-setter trace (`tru+0x19c920`) costs too much in menus (the pause menu stalled, the game had to be ended):
       the DLC 2 title element (432) never had its visibility set; text visibility is set by the native at
       `tru+0x3a6886`, called from the interpreter at `tru+0x17b051` - next: identify that native and trace only it.
     * **Loading-screen titles fixed (test 38, played 21:19 without any debugger forcing)**: `tru+0x3a6870` is slot 6 of
       the `uitext` native type object (vtable at `0x864984`), and its caller `tru+0x17b051` is not an opcode but the
       routine that applies a new script object's **member init values** (a list of {u16 offset, value} -> `+0x179770`)
       - the visibility comes from the init block, not from script code. `tools/script_init_dump.py` on script 6:
       the base titles 51-58 (init blocks 0xe060 .. 0xe7d0) have word 0 = 1, the TU-only DLC title members 16894
       (0xe8e0) and 16908 (0xe9f0) had **0** (Xbox: 1) - the same converter defect as the hint box's word 0 in test 36.
       `script_word_set.py ... 6 e8e4=00000000:00000001,e9f4=00000000:00000001` on test 37b = test 38 (md5 57f52266):
       the debugger now reads the bool +0x88 = 1 by itself for both titles, and "UNTER DER ASCHE" / "LARAS SCHATTEN"
       stand above the line (`references\DLC1\PC-Test38-*_21_*`, `references\DLC2\PC-Test38-*_38_*`). The record words
       of test 32 were not the switch. Open: the DLC 1 text still starts one line too high; TU-only member 16896
       (userType 361, init 0xeda0) has the same word 0 = 0 vs Xbox 1 - untested. Also: the Xbox exe's `dlc2data` f0
       reads a byte of the central game-state object that only `DoppelgangerInit` sets ("playing with the shadow
       power"), so the unit-name check of test 37b is equivalent in practice (first pass of option A,
       `docs\Befund-Schattenkraft.md`: ~235 functions / <= 163 KB PowerPC code depend on that byte, >= 64 KB new).
     * **Our generalbank is a pipeline step now** (`tools/generalbank_build.py OUT_DIR`, step `Generalbank`, also run by
       `Repair`; `b138_fix_tree.py --generalbank FILE` puts it into the repair tree): 21 steps with the existing
       tools, each checking the words it replaces - B138's generalbank + mission screen style, the TU conversion
       (`base_convert_check.py ... --out`, new option), script 6 (nop of `uigamedata` 93, put with `--symbols`,
       vtable slot 31, init values, text record ids), script 10 -> 9 (`generalbank_dlc.py --scripts 6,10`, put,
       record template), the title words of test 32 and the hint-box steps of tests 35-37b. Run 2026-10-30 21:28-21:36
       (`logs\Manual_GeneralbankBuild_20261030-212847.log`, ~8 min, the two converter steps 265 s / 182 s): the
       result is **byte-identical to the played test 38 file (md5 `57f52266...`)**. Every intermediate of the hand
       builds (gb6 / gb8 / gb11 / tests 18, 27, 32, 33, 35, 36, 36b, 37b) was reproduced on the way; today's TU
       conversion differs from the 2026-10-29 one in 7 sections the build does not take (8:7, 63, 72, 87, 93, 3383,
       3000007), the taken 8:6 / 21239 / 20082 are identical. The two title words of test 38 now come from
       `script_init_from_pc.py` itself: its "empty the glyph list" step (a TU glyph the PC font map lacks crashed the
       menu-entry code, DLC 2 test 10) zeroed word 0 of **every** TU-only member in which a learned u16 glyph map
       met an unknown value - also the two userType-301 title texts, so their flag stayed 0 instead of the Xbox's 1.
       Restricted to the glyph-list struct (userType 361), the learned s32 rule gives exactly test 38's two words.
       The one member it still empties is 16896 (userType 361, init 0xeda0): the TU-only button-glyph entry whose
       glyph `0x4021` the PC does not know - word 0 is its glyph count, 0 on purpose since test 11 (untested with 1).
     * **Calls into the TU-only `achievement` natives neutralised (test 40, structurally checked, not played)**: new
       `tools/script_missing_native_fix.py MODS_DIR REF.drm OUT_DIR [--types ...] [--check]` decodes every function's
       code and finds each `op65` (native call) whose operand points into a native type script of REF (the installed
       generalbank) at an offset that is no PC function entry - a call through a null native pointer like
       `dlc2data`. In the installed tree exactly **11 such calls, all `achievement`** (PC 16 natives, TU 21): +0x214
       `dlc_treasureroom` 23210 (DLC 1), +0x230 the shared script 26418 in `dlc2_ceremony_room` /
       `dlc2_hall_ceremony_goo` / `dlc2_hall_machine_ceremony` / `dlc2_treasure_room_cine`, +0x24c `dlc2_goo_room`
       24994 / 25086 and `dlc2_hall_ceremony_goo` 24994, +0x268 `dlc2_hall_machine_ceremony` 26335, +0x284
       `dlc_yggdrasil_end` / `dlc_yggdrasil_hall02` 23101. Each is `op0f <member> / op65 / operand` (object only, no
       argument, no out parameter), so the three words become the preceding line marker and the relocation is dropped
       (tools/script_nop_call.py pattern; sequences with `op09` out parameters or non-push ops would be reported and
       left alone - none). The other "NO FUNCTION ENTRY" lines of `native_calls_check.py` are no calls: 42 `op67`
       operands -> +0x3c of `dispatcherbase` / `checkpointbase` / `uiscreen` (a header field; Crystal's own
       generalbank scripts 7 / 33 / 268 / 269 do the same) and header / vtable references from data (+0x44 etc.).
       Test tree `work\rebuild\dlc_test40_achievements\mods` (8 DRMs): re-check 0 calls, walker problems [] for all
       changed scripts, `script_ext_check` unchanged (the one suspect of 26418, root +0x40 -> 3523, is in the
       installed file too), `tree_check` 0 errors, `native_calls_check` no `achievement` line. Not yet in the
       pipeline's `Fixes` step - after a play test. Details: workspace `docs\Befund-Erfolge.md`.
     * (Superseded by debugger run 2: the base title is a separate string 51.) Loading-screen title: the base game's start screen text "Was bisher bei Tomb Raider geschah..." is ONE string
       (PC 59: heading line + body), while the DLC loading screen has a separate title element (5169) next to the
       description - the description shows, the title element stays invisible. Next: GetLocalString breakpoint on 59
       (base start) and 5169 (DLC) with the caller (`kv`) to compare the two elements.
     * `work\rebuild\exp_sym*` (the intermediate trees of finding 35's three runs, 9.7 GB) deleted - the result is
       adopted (`docs/data/b138_symbol_calibration.json`), logs and `sections_exp_sym*.json` stay.
     * **Pipeline step `Fixes` re-run with all stage-2b fixes** (log `Invoke-TruPipeline_Fixes_20261030_140516`,
       1 645 s, all exit 0; DLC 2: `uipath` 125 arrays, `uitext` 120 + 150): `tools/tree_compare.py
       work/rebuild/dlc2_asm_stage2b/mods work/rebuild/play_20261030/mods` = **292 identical, 0 different**; only
       `g_pda.drm` differs in presence (the stage-2b tree has the merged one, the tested trees keep the PC `g_pda`,
       finding 40). So the tested DLC 2 state is reproducible from the pipeline.
     * **Noisy speech (DLC cinematics)** measured with new `tools/ima_encoder_check.py` (decoded Xbox source vs our
       IMA re-encode, game decoder). German DLC 1 intro (spec ffffe004, 44.1 kHz stereo): our encoder **25.4 / 25.0
       dB**, largest single error 16 941 / 19 652, 0.76 / 0.93 % of the 64-sample blocks with an error > 4096.
       (For comparison, finding 18: Crystal's own encoder on base music 38.7 / 45.4 dB; English intro, ours 31.0 dB,
       B138 12.8 dB.) The encoder takes each block's start index from a warm-up over the previous block and picks
       nibbles greedily - after a quiet block the step is too small for a sudden onset. Variants: start index searched
       per block (all 89) = 26.6 / 26.3 dB, 0.32 / 0.36 %; **plus one sample of lookahead per nibble = 26.6 / 26.2 dB,
       largest error 9 799 / 8 860, 0.11 / 0.16 % bad blocks** - the mean barely moves, the audible spikes become
       6-7x rarer. Listening test 29: `work\rebuild\dlc1_test29_audio` (German intro `_004` with the lookahead
       encoder, same size as the installed one, only audio bytes differ). If it sounds cleaner: make it the encoder of
       `mul_audio_nch` (all DLC `.mul`, ~1 min per stream).
28. **Our Convert used the generic media route, not upstream's stage-1 route - and its render tables do not exist.**
   * `docs/PIPELINE.md` stage 1: `tools/convert_dlc.py OUTDIR name.drm ...` -> `assemble_dlc.assemble()` ->
     `dlc_generic.convert_drm()` with media callbacks (materials via `material_dlc.py` / `material_convert.py`,
     meshes `mesh_convert.py`, terrain `terrain_convert.py`); the author's own rebuild check
     (`work/ws/rebuild/convert_fresh.py`) also calls `assemble_dlc.assemble(..., material='dlc')`.
     `tools/dlc_convert_all.py --media` (our step Convert) uses `dlc_generic.default_media` instead - "converts and
     self-checks", but without the DLC material route. Likely part of why materials (83 %) and meshes (32 %) differ
     from B138, not only the missing shaders.
   * `assemble_dlc` / `material_dlc` / `material_reslot` / `shader_map` / `mesh_convert` read tables from
     **`work/render/`, which is not in the repository** and is not created by any documented step:
     `material_x2p.pkl` (read by `material_dlc.py`, `material_reslot.py`; **no generator found in the repository**),
     `pc_shader_sections.pkl` (`tools/pc_shader_sections.py`), `dlc_shader_map.json` + `dlc_material_shaders.json`
     (`tools/shader_map.py`), `param_rules.pkl` (`tools/material_rules.py`), `terrain_yhash.pkl`
     (`tools/terrain_validate.py`).
   * Stage-3 builders also read data files that are not in the repository: `work/ws/shader4/` holds only `.py`
     files - `pc_ctab_by_pos.json` (written by `shader4/learn_names.py`), `illuminati.tsv` (`shader4/f4_tables.py`),
     validation outputs of upstream's VM runs (`valid_all/`, `draw_result.txt`) - and the baselines
     `work/baseline/B45|B73|B86_contratti|B87_materiali19/mods`.
   * Next (after the symbol rerun): generate the render tables that have a generator, find or rebuild
     `material_x2p.pkl` (Xbox material id -> PC material id for the 252 base materials, per `material_dlc.py`), then
     convert with `convert_dlc.py` / `assemble_dlc` and compare materials and meshes again.
   * Dependency chain of `work/render/` (read from the code, 2026-10-27 night; nothing generated yet):

     | File | Written by | Reads |
     |---|---|---|
     | `pairnames.json` | **no generator** | - (list of base DRM names that exist on Xbox and PC) |
     | `pairs_render.pkl` | `tools/rend_extract.py pairs` | `pairnames.json`, `pairs.py` (base archives) |
     | `dlc_render.pkl` | `tools/rend_extract.py dlc` | `work/idx_dlc.json`, DLC packs |
     | `material_x2p.pkl`, `shader_x2p.pkl` | **no generator** | - (Xbox -> PC material / shader id maps) |
     | `dlc_shader_map.json`, `dlc_material_shaders.json` | `tools/shader_map.py` | `pairs_render.pkl`, `dlc_render.pkl` |
     | `param_rules.pkl` | `tools/material_rules.py` | `pairs_render.pkl`, `material_x2p.pkl`, `shader_x2p.pkl`, idmap |
     | `dlc_materials_pc.pkl` | `tools/material_dlc.py` | `material_x2p.pkl`, `shader_x2p.pkl`, ... |
     | `pc_shader_sections.pkl` | `tools/pc_shader_sections.py` | `dlc_shader_map.json`, `dlc_materials_pc.pkl`, `pairs_render.pkl` |
     | `terrain_yhash.pkl` | `tools/terrain_validate.py` | `pairs_render.pkl`, `material_x2p.pkl`, idmap |

   * Reconstruction ideas, **not verified yet**: `pairnames.json` = the names of the 1054 base pairs of
     `generic_cache` (`work/generic/pairs.pkl`); `material_x2p.pkl` / `shader_x2p.pkl` = the type 10 / type 9 maps that
     `generic_ids.py` already writes into `work/generic/idmap.json` (2244 / 2046 entries) - to check against
     `material_dlc.py`'s statement "252 byte-identical base materials" and the B138 materials before use.
   * Code survey (2026-10-29, read-only):
     * No code in `tools/` or `work/ws/` (scratch folders included) writes any of the three files; the only `x2p` dict
       built anywhere (`override_merge.py:61`) is local.
     * Expected structures: `material_x2p` and `shader_x2p` are plain `{int xbox_id: int pc_id}` dicts (`material_dlc.py:47,51,83`,
       `material_rules.py:13-14,36`, `shader_map.py:101,127,130,134`, `material_reslot.py:257,289`,
       `terrain_validate.py:50`, `mesh_validate.py:151`). `material_rules.py` zips Xbox and PC type-10 sections of a
       pair by position and keeps a pair only if `mx2p[x.id] == p.id`, so the map must agree with the positional
       section order.
     * `generic_ids.py` matches types 9/10 the same way (media types: fingerprint `(type,)`, matched by position when
       the per-type counts agree, then known-id pass and id-reference votes; non-injective ids dropped). Size check:
       `material_convert.py` "verified on 2247 paired material ids", `shader_map.py` "2233/2247 base material pairs"
       vs idmap type 10 = 2244. "252" / "505/505" count DLC ids that also exist in the Xbox base, not map sizes.
     * `pairnames.json` = JSON list of base DRM names without platform prefix (e.g. `alister.drm`), exactly what
       `generic_cache.names()` builds (PC `pc-w\` names that also exist as `xenon-w\`) = the keys of
       `work/generic/pairs.pkl` without the `patch:*` keys of `pairs_patch.pkl`.
     * Plan: `pairnames.json` from `generic_cache.names()` (high confidence); `material_x2p` / `shader_x2p` from idmap
       types 10 / 9 (medium-high / medium), then check: number of type-10 pairs that pass `material_rules`'s zip +
       id test, `material_validate.py`, and for shaders: every Xbox shader id of a base material's tuple (offset 0x28)
       maps to the PC material's shader at the same tuple position (PC re-slots pixel shaders, `shader_map.py:108-110`).
   * **Built and checked (2026-10-29)** with `tools/render_tables_build.py build|check` (new; log
     `logs/Manual_RenderTables_20261029_025611.log`): `pairnames.json` 1 054 names (= the 1 054 pairs of
     `generic_cache`), `material_x2p.pkl` 2 244 and `shader_x2p.pkl` 2 046 entries, both injective;
     `tools/rend_extract.py pairs`: 1 054 pairs, 0 failures (`pairs_render.pkl`). Check over all base pairs:
     9 273 Xbox material sections, **9 155 pass `material_rules`'s positional zip + id test** (118 do not);
     shader tuples of those: **9 145 equal** to the PC material's tuple after mapping, 10 different, 0 with an
     unmapped shader (4 588 empty slots 0 / 0xffffffff kept). The idmap-derived maps reproduce the PC data - good
     enough to run the render tools. `work/render/` is ignored (derived from game data).
   * **Render tools run on them** (log `logs/Manual_RenderTools_20261029_025732.log`, all exit 0):
     `rend_extract.py dlc` (`dlc_render.pkl`); `shader_map.py`: 1 028 DLC shader libs, classes A 489 / B 234 /
     C1 120 / C2 47 / C3 81 / D 57, **0 unmapped**, VS coverage violations 0, 391 of 565 new materials use only
     (VS, PS) pairs that ship on PC; `material_rules.py`: 34 rule keys, in-sample exact 2 154 / leave-one-out exact
     2 142; `material_dlc.py`: **804 DLC materials, 804 converted, 0 failed** (239 base materials, 231 of them
     convert == PC; flags: 152 param count differs from the surrogate, 59 fewer textures, 11 tuple unseen);
     `pc_shader_sections.py`; `terrain_validate.py`: 335 terrain pairs, all valid, 333 reloc-exact, 83 exact,
     245 semantic. Next: convert with `assemble_dlc` (material 'dlc') and compare materials/meshes with B138.

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
| 2026-10-27 | Audio | `compare_audio.py` (decoded audio): waves 0.11 % of samples differ, SNR median 90.7 dB; `.mul` 19 non-stereo files ~0 dB -> layout learned from the base game (finding 18) |
| 2026-10-27 | Audio | rerun with `mul_audio_nch.py` (tools called directly): `MUL OK 39 of 39 (mode nch)`; `compare_audio`: ours vs Xbox source min 25.1 / median 44.4 dB, ours vs B138 median 39.9 dB |
| 2026-10-27 | Media | from the new place `scripts/windows/` (after the move into the repository): 92 identical of 275, 36 s; then with `-X utf8`: same result, 35 s |
| 2026-10-27 | Fixes (2b) | `dlc_fixes_build.py` stage2a -> stage2b, fix `cine`: 3 command DTPs = B138, effect DTP 23767 417 -> 9 words; first run of `build_cine.py` failed on the author's local paths in `cinepairs.py` (fixed) |
| 2026-10-27 | Fixes (2b) | fixes `cine` + `float`: float_fix s16 12 words, raw 44 words; `compare_sections` stage2b: DTP 11 131 identical (stage2a 11 126), script 4917, general 230 (unchanged) |
| 2026-10-27 | Fixes (2b) | `tag_records.py` on stage2b: 329 record words, 0 defects; `tag404_check`: 16 of 23 `0x404` +4 words differ; fixes `cine` + `float` + `tag404`: `tag404_check` 23 of 23 = B138, DTP sections 11 131 identical |
| 2026-10-27 | Fixes (2b) | all four fixes `cine`, `float`, `tag404`, `postfix` (stage2a -> stage2b): `compare_sections` stage2b: general 246/259 (95.0 %), 2 100 %, tex 99.6 %, wave 86.5 %, DTP 11 131 (97.4 %), script 4917 (79.5 %), shader 0 %, mat 83.2 %, Obj 100 %, mesh 31.7 %, 13 95.2 %; `rebuild_status`: `derived:B43` general 112/115 (was 109), still 9 of 133 DRMs fully identical (all `vm_mods_expected`) |
| 2026-10-27 | Fixes (2b) | `analog_word_fix.py scan`: first run with `rebuild/...` saw 0 files (path relative to CWD), rerun with `work/rebuild/...`: 33 words; five fixes (`cine`, `float`, `tag404`, `postfix`, `analog`): DTP 11 157 identical (97.6 %), 10 DRMs fully identical |
| 2026-10-27 | Learn..Audio | rerun after the symbol-guard fix (Learn from tool 2, Tables 6 977 s, Prep 865 s, Convert 2 509 s, Names, Media, Audio; all exit 0): sym_info xbox_max 16347 / shift 481; collisions 24 386 -> 1 219 |
| 2026-10-28 | Convert..2b | with `DLC_SYM_SHIFT = 480` (tools directly, `logs/Manual_SymShift480_20261027_233600.log`): script sections 95.4 % = B138 (was 79.5 %), 2 593 differing script words (was 9 580), 11 DRMs fully identical |
| 2026-10-28 | Convert..2b | with `--extra-fixes` (after generating `model_point_rules.pkl` and `dtpid_evidence.pkl`): DTP 98.7 % = B138 (was 97.6 %), type 0 95.8 %, script words 2 581 |
| 2026-10-29 | Prep..Audio | **reproducibility run through `scripts/windows/Invoke-TruPipeline.ps1`** (Windows PowerShell 5.1, `powershell.exe -NoProfile -NonInteractive -File`): Prep 1 755 s (incl. model_point learn/selftest 0 changes, dtpid_evidence 96.86 %), Convert 4 449 s (`--extra-fixes`, readback 307/307), Media 61 s, Audio 93 s, all exit 0; then 2b fixes + comparisons (`logs/Manual_2b-compare_20261029_024654.log`): **same numbers as 2026-10-28** - DTP 98.7 %, script 95.4 %, type 0 95.8 %, 2 581 script words, 11 DRMs identical, `analog` 33/33 = B138 |
| 2026-10-29 | Render tables + tools | `render_tables_build.py build/check`, `rend_extract.py pairs/dlc`, `shader_map`, `material_rules`, `material_dlc`, `pc_shader_sections`, `terrain_validate` - all exit 0 (finding 28) |
| 2026-10-29 | Assemble route | `dlc_assemble_build.py` -> asm_stage1, Audio, 2b fixes, comparisons: 134/134 DRMs, shader libs 97.7 %, materials 90.4 % = B138 (finding 34) |
| 2026-10-29 | Assemble (step) | new optional pipeline step `Assemble` through `Invoke-TruPipeline.ps1` (PowerShell 5.1): all 13 tools exit 0, 2 934 s (terrain_validate 596 s, dlc_assemble_build 2 184 s); asm_stage2a: shader libs 97.7 %, materials 90.4 %, script 95.4 % - same as the manual run |
| 2026-10-29 | Symbol experiment | runs 1-3 (finding 35): run 3 (167 candidates, exact-only) scripts 99.2 %, 95 words left, 0 new differences |
| 2026-10-29 | Parallel runs | `dlc_convert_all --jobs 2` 2 824 s, 300/300 files identical to the sequential run; `dlc_assemble_build --jobs 2` 1 439 s, 271/271 identical; step Audio through the script with automatic counts: "processes: heavy 2, light 24 (free RAM 46 GB, 36 logical CPUs)", 97 s, scripts 99.2 % (finding 36) |
| 2026-10-29 | Convert..Assemble + 2b | with the adopted symbol calibration through the PowerShell script (Convert 4 880 s, Media 64 s, Audio 93 s, Assemble 3 036 s, all exit 0): scripts 99.2 %, asm tree shader 97.7 % / material 90.4 %, 15 DRMs identical; memory sampled (finding 36) |
| 2026-10-27 | DLC 2 Media | `dlc_media_build.py work/rebuild/dlc2_stage1/mods pack11` (parallel to the DLC 1 run): 167 DRMs, 19 music tracks, 6 cinstream `.mul`, exit 0 (see `docs/DLC2.md`) |
| 2026-10-27 | Prep | ok, 818 s: `generic_type0 save07` 796 s (type0_table 9 827 722 keys, type7_table 4 084 298 keys, + slim npz); `pc_vers_build` 21 s: 1060 PC DRMs indexed, pc_vers 37 813 (1818 with several versions, 2481 from patch.000), pc_vers_content 28 928 (856 multi) |
