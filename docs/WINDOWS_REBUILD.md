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
| 2026-10-27 | Prep | ok, 818 s: `generic_type0 save07` 796 s (type0_table 9 827 722 keys, type7_table 4 084 298 keys, + slim npz); `pc_vers_build` 21 s: 1060 PC DRMs indexed, pc_vers 37 813 (1818 with several versions, 2481 from patch.000), pc_vers_content 28 928 (856 multi) |
