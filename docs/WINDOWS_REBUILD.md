# Rebuilding the pipeline on Windows (branch `windows`)

Running log of what it takes to reproduce the stage 0-1 pipeline (docs/PIPELINE.md) on a Windows PC from the user's
own files. Goal: rebuild DLC 1 (*Beneath the Ashes*) step by step, compare every produced file with the B138 kit
manifest, and then use the same pipeline for DLC 2 (*Lara's Shadow*) and the costume packs.

Where the fixes of stage 2b come from (upstream's `work/ws/` folders, builds, overlay layers): `docs/WS_MAP.md`.

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
| Assemble (optional, after Media) | `render_tables_build.py build`, `rend_extract.py pairs`, `render_tables_build.py check`, `rend_extract.py dlc`, `shader_map.py`, `material_rules.py`, `material_dlc.py`, `pc_shader_sections.py`, `terrain_validate.py`, `dlc_assemble_build.py work/rebuild/stage1/mods work/rebuild/asm_stage1/mods` (**new**), `dlc_audio_build.py` into `asm_stage2a`, `compare_b138.py`, `compare_sections.py` | upstream's full stage-1 route (findings 28, 34): render tables in `work/render/`, DLC 1 tree with PC shader sections and DLC materials |

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
| 2b | Data fixes B1-B47 (LINEAGE.md) in `tools/dlc_fixes_build.py`: `cine` (B44/B45) done, `float` (B46/B47) done, next raft rings (B33), then the remaining layers of `docs/WS_MAP.md` | in progress (findings 20-22) | minutes per fix; much work |
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
