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

The order of Ids/Learn follows the inputs each tool opens; it is not documented upstream and may still change.

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
8. The converter prefers `work/generic/mask_best.npz` (+ `mask_best_vocab.pkl`, from `slim_table.py` ->
   `slim2np.py`) and falls back to the full `mask_table.pkl` - same result, more memory. Not built yet.
9. **First MD5 match with B138:** the merged `tr8/pc-w/objectlist.txt`, `unitlist.txt`, `objlist.dat` written by
   `objlist_merge.py` are byte-identical to the files of the installed B138 `mods/` tree (md5 45dc3b4c…,
   2203e9bd…, e4f12246…). 1045 objects (821 base keep their PC ids, 224 DLC), 119 units, 0 dangling object refs.
10. `generic_cache.py` pairs **1054** base DRMs (its docstring says 975; `drm_reloc.py` mentions 1054). 0 errors,
   26 s with 8 processes, `pairs.pkl` 1 449 582 409 bytes, `pairs_patch.pkl` 14 782 788 bytes (patch pairs:
   g_pda, generalbank, globalsoundinfo, l2_puzzleroom).

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
| 2026-10-27 | Prep | ok, 818 s: `generic_type0 save07` 796 s (type0_table 9 827 722 keys, type7_table 4 084 298 keys, + slim npz); `pc_vers_build` 21 s: 1060 PC DRMs indexed, pc_vers 37 813 (1818 with several versions, 2481 from patch.000), pc_vers_content 28 928 (856 multi) |
