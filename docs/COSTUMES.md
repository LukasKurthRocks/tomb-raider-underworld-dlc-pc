# Xbox 360 costume packs - notes

Not handled by upstream (no mention in STATUS/FINDINGS/INVESTIGATION; `tools/costume_cmp.py` compares DLC costume
objects with the Xbox base `lara_*` objects).

## Which pack is which (from the data, 2026-10-27)

Each pack has 13 records: two costume DRMs, their outfit preview images, the object/unit lists and six
`locals.bin` (one per language). Content folders under `Content/534307EC/00000002/`:

| Pack | Content folder | Costume DRMs | Preview (outfit select image) | Pack |
|---|---|---|---|---|
| `pack1.000` | `E5AFB2B959A72C52120D73678AED11BD8752686753` | `dlc_costume_k`, `dlc_costume_p` | red wetsuit / blue wetsuit with shorts | Wetsuit Costume Pack |
| `pack2.000` | `9FDDD06617D1016DE468ACF53AC663E8BA2AD41853` | `dlc_costume_a`, `dlc_costume_h` | classic Lara (teal top, shorts) / olive top + shorts | Classic Costumes |
| `pack20.000` | `AC0089F81B621CD0E0C156B6176EFCC6C844705D53` | `dlc_costume_l`, `dlc_costume_m` | white/grey outfit / black catsuit with blue belt | Designer Costume Pack |

Community outfit chart (r/TombRaider, "Underworld enjoyers, what's your favorite outfit?", fan names) matches the
previews: k = "Drysuit Red", p = "Wetsuit Blue", a = "Classic", h = "Legend" (the *Tomb Raider: Legend* outfit),
l = "Snowsuit" (white), m = "Bodysuit" (black, blue belt). The official names of the Designer pack are
"Fashion Winner" and "People's Choice" (outfits by fashion designers, chosen by a fan vote); which is l and which
is m is not documented anywhere found so far.

Previews are `xenon-w\image\dlc_outfit_costume_<x>.raw` ('!WAR' images), converted with
`raw_image_convert.xbox_to_pc` + `to_png`. Each costume DRM is ~31-32 MB.

English costume names in the packs' `locals.bin` (spec 0xfffff7e1, pack20 version, 1407 strings):
48 "Wetsuit", 61 "Classic Lara", 62-70 bikinis (Blue, Black and White, Red, Camo, Bright Blue, Gold),
72 "Fashion Winner", 73 "People's Choice", 76 "Blue Wetsuit", 77-80 "Dopple Costume 1-4".
(Answered 2026-11-03, see "Port": index 61 + slot, so l = 72, m = 73, h = 68 "Legend Lara".) Former question: which
string index belongs to which costume object (l/m, name of h) - to be found in the outfit table
(the loading screen script, Script id 6, loads "all DLC Costume images" and lists `dlc_costume_a..p.drm` and
`dlc_doppel_costume_a..d.drm`).

## Port (2026-11-03, offline)

Answered by the pack data: l = "Fashion Winner", m = "People's Choice", h = "Legend Lara" (string index 61 + slot in
every pack's `locals.bin`, `tools/costume_variant_cmp.py names`).

### What the game needs (static, retail PC / title update / our generalbank)

* **Offer:** the loading-screen script (generalbank script 6, function 26) calls `dlcsystem` f1 (native type script
  90) with `dlc_costume_a.drm` .. `dlc_costume_p.drm` and `dlc_doppel_costume_a..d.drm` and adds an outfit menu item
  (`uimenu` f14, text, `uirenderimage`) only for the files that exist. On PC f1 is `tru+0x7973c0` -> `0x776cd0`: build
  the path, get the file system (`0x472b50`), call its method +8 ("file exists") - through the ModLoader this sees
  `mods\`. The same 20-call loop is in the retail PC script (`script_dis.py pb 6`), the title update's (`xt 6`) and
  ours (`work/rebuild/generalbank_build`). The level load accepts the chosen id when `<name>.drm` exists (validator
  `0x5c54e0`, `src/asi/TruMenu/README.md`). No unlock flag for DLC costumes was found: like the Xbox (mounted
  package), presence of the file is the licence.
* **Already installed** (`tools/costume_pack_check.py`): objects 20-35 = `dlc_costume_a..p` in the PC base object
  list and the merged list (`lists`); names: Xbox index 61 + slot -> PC string 83-98, all six names in the B138
  `locals.bin_001` (`names`); preview images: the packs' `dlc_outfit_costume_{a,h,k,l,m,p}.raw` are byte-identical to
  pack11's, which B138 ships (`images`).
* **Not taken:** pack20's list-only container unit `dlc\dlc_costume_containers\dlc_costumes4` (record: `lara`,
  `dlc_costume_l`, `dlc_costume_m` + gear). No pack has a DRM for it; it would be unit-list entry 8 and move the 112
  entries after it. `dlc_doppel_costume_a` (pack20 object list) is already object 1031 in the merged list; no DRM.
* So the port is **data only**: the six `dlc_costume_<x>.drm` in `mods\`. No plugin change; TruMenu's Outfits page /
  `costume.set` can select them once the files exist.

### Pipeline

`convert_dlc.PACKS` index 4 = `pack20`; `dlc_assemble_build.PACK_INDEX` pack1 / pack2 / pack20, `dlc_media_build`
pack20; `dlc_names`, `verify_ids`, `objlists_extract`, `locals` (survey only), `music_convert.convert_streams` know
pack20. `Invoke-TruPipeline.ps1 -Step Costumes [-FixesOut work/rebuild/<dir>]` runs `verify_ids.py extend`,
`converter_faults_fix.py proof` and per pack media -> assemble -> audio -> `tree_check` -> stage 2b ->
`converter_faults_fix check`.

Run 2026-11-03 (`work/rebuild/costumes_0311`, same tools by hand):

| Step | Result |
|---|---|
| `dlc_names.txt` with pack20 | 13 lines added, all old lines unchanged (2 DRMs, 2 images, 3 lists, 6 `locals.bin`) |
| `objlists_extract` | 18 old list files byte-identical, 6 new (`dlc_pack2_*`, `dlc_pack20_*`) |
| `verify_ids.py extend` | 10 474 old entries unchanged, added type 5: 91, 7: 37, 8: 6, 9: 4, 10: 37, 12: 6; 0 unmapped ids, 0 collisions, 234/234 objects name-checked |
| `converter_faults_fix proof` | all rules hold on the base pair |
| render tables (morning) | **gap**: `work/render` was built from `idx_dlc.json` = pack10 / pack11 only. Per costume 5-17 materials were missing from `dlc_materials_pc.pkl` (k 13, p 17, a 8, h 5, l 12, m 6) - `costume_pack_check.py render`; assemble passed them through as Xbox bytes (`media_error:KeyError`) |
| index + render tables (afternoon) | Index step with pack1 / pack2 / pack20 **after** pack10 / pack11 (659 records; the old 620 are a prefix); `rend_extract dlc` 313 DRMs (was 307); `shaderlibs.pkl` cache rebuilt; `shader_map` 1052 libs (+20 A, +4 B; C/D unchanged), unmapped 0; `material_dlc` 854 materials (+50), failed 0; `pc_shader_sections` 623 ids, missing 0. `render_tables_compare.py tables`: every old entry of every table unchanged, base tables equal; no new record carries a type-9 / 10 id with other bytes than an earlier record. All 12 costume DRMs: 0 materials missing |
| DLC 1 / DLC 2 proof | assemble with the old tables, then with the new ones (same code, `TRUDLC_JOBS=1`), `render_tables_compare.py tree`: DLC 1 271 files / 134 DRMs, DLC 2 293 files / 166 DRMs - all sha256 equal. The old-table runs also equal the existing `asm_stage1` (2026-10-29) and `dlc2_asm_stage1` (2026-10-30) |
| costume chain | all six costumes: assemble OK, bad `[]`, missing shaders `[]`; audio OK; `tree_check` (stage 2a and 2b) readback ok, 0 relocation errors; 28 stage-2b fixes; `converter_faults_fix check` 0 wrong, 0 unexpected, 0 without Xbox original. Test tree `work/rebuild/dlc_test50l_costumes` (6 DRMs) + profile `regress_costumes_0311` |

**Why each costume takes 75-90 min (DLC 1 costumes: ~90 s) - and the main risk.** `costume_pack_check.py xids`:
the type-7 DTPs of all six new costumes use base ids (k: 1571 of 1577 in `idmap.json`), but only 218 of ~1511
(id, size) pairs match any Xbox base or DLC record (layer1 / layer2 / TitleUpdate / pack10 / pack11); the DLC 1
costumes match layer1 `lara` in ~1483. Size difference to the same id in layer1 `lara` (k): 0 bytes 218, +36 122,
+44 86, +448 51, +1028 46, +48 45, ... - the packs were built against a base-data generation that is not on the
disc or in the title update. So pc_copy / template (which need the Xbox base bytes / size) never apply: ~1354-1358
DTPs per costume take route `(7, 'convert')` (learned type-7 table), DLC 1 costume b takes pc_copy 751 + template 793.
`converter_faults_fix check` therefore reports, per new costume, 118 "kept_base_mapped" rows (anim event list words
146 and effect-node sections 90 per pack; DLC 1: 0) - words where the proven rule and the converter disagree inside
renumbered base DTPs. By policy the tool never changes base-mapped sections (for the DLC 1 costumes they are PC
copies); here they are converted, so these are crash candidates of the anim-list / effect-node families
(tests 50e-50i). Not changed - decision open.

Open: on 2026-10-29 the DLC 1 outfit list showed B/W bikini, camo, casual explorer, gold, grey jungle shorts - not
Blue Bikini (b), although `dlc_costume_b.drm` is installed; either it was off screen or the menu filters something
not found here.

## Left out: slots g / n and `dlc_costumes4` (owner decision E4, 2026-11-05)

Slots g and n are not real costumes in the Xbox data: both carry the name of o ("Grey Jungle Shorts", string
index 61 + slot = 67 / 74); g's preview image is byte-identical to o's, n's is a roughly tinted placeholder. pack20's
container unit `dlc\dlc_costume_containers\dlc_costumes4` has no DRM in any pack. Neither is ported.

What "left out" means, and what must stay:

| Item | Rule | Why |
|---|---|---|
| `dlc_costume_g.drm`, `dlc_costume_n.drm` | never in a mods tree | generalbank script 6 function 26 offers a slot only when its DRM exists (each of the 20 names is followed by `dlcsystem` f1 and a conditional jump - checked in the B138, `b138_fixes` and pipeline generalbank); the costume validator `0x5c54e0` also needs the file. No file = no outfit-list entry, and TruMenu's `costume.set` is refused by the game's validator |
| unit `dlc_costumes4`, objlist record `dlc_costumes4` | never in `tr8\pc-w\unitlist.txt` / `objlist.dat` | `objlists.merge` builds the lists from the PC base + the Xbox title update only, so pack20's list never reaches them; adding it would move every unit after it |
| object ids 26 = `dlc_costume_g`, 33 = `dlc_costume_n` in `objectlist.txt` | **keep** | ids are positions; the PC base list (retail), the Xbox lists and the DRMs refer to objects by id |
| `image\dlc_outfit_costume_{g,n}.raw` | **keep** | B138 / pack11 ship them; script 6 function 17 loads images only for the slots function 26 appended |

Gates: `tools/costume_scope_check.py` (read-only) - `tree DIR ...` (mods trees or a game's mods folder), `profiles`
(every tree of every test profile), `script6 GENERALBANK.drm` (the offer gate), `selftest`; exit code 1 on a
left-out item, a moved costume id or a missing gate. `tools/costume_recolor.py build` refuses object ids 26 / 33 and
an output named `dlc_costume_g.drm` / `dlc_costume_n.drm` unless `--allow-left-out-slot` is given.

## Upstream trace

The B90_gold_L4 manifest lists `convert_costumes.log` with origin `vm_extra` (a file that was in the test VM's
`mods/`): the author converted costumes at some point; no script or notes for it in the repository.

## In game (Xbox, Xenia)

Outfits are chosen on the level start screen; in a first playthrough PDA -> Revisit Location is greyed out, so the
costume menu needs a finished game (Treasure Hunt). pack20 also brings a Doppelganger costume
(`dlc_doppel_costume_a` in its object list).
