# DLC 2 *Lara's Shadow* (`pack11.000`) - notes

Status upstream: "the converter handles generic parts, nothing was tested" (INVESTIGATION.md item 9). The B138
installer only takes DLC 2 menu images and music from `pack11.000`; the PC DLC menu lists only installed DLC, so
*Lara's Shadow* does not appear there yet.

## Xbox reference (Xenia Canary 02d2cb5, game + TU 0.0.2.3 + DLC, 16:9)

Reference screenshots are kept outside this repository (local `references/` folder of the workspace).

* DLC menu: title light blue, description = locals index 457, 5 lines with hard breaks.
* Loading screen: title "LARA'S SHADOW" in a ring, description text types itself in
  ("The Doppelganger is a dark and deadly reflection of Lara. Created as a sinister trick by Lara's ...").
* In the level the player controls the Doppelganger. First tutorial hint: **"The shadow meter drains when LB or RB
  is held."** - a DLC-2-only mechanic (shadow meter in the HUD, shoulder buttons). To check early whether the PC
  exe (retail-based, without the Xbox title-update code) has everything this needs (scripts, HUD widget, input
  bindings for the shoulder buttons on PC).
* HUD: top left a green Lara silhouette = **shadow meter** next to the weapon/ammo widget; holding RB triggers a
  blurred "shadow" ability effect (screen-wide motion blur). Needs a HUD widget, an effect and input handling on PC.
* Pause ring menu in the DLC as on the base game (Resume Game in the centre).
* Xenia renders level geometry and cutscenes with heavy hatching artefacts (emulator issue, title bar shows
  "Direct3D 12 - RTV/DSV"); menus, loading screen and text render cleanly. Known for this title
  (xenia-canary/game-compatibility #418): it needs `render_target_path_d3d12 = "rov"` (or FSI on Vulkan); set
  2026-10-27 - confirmed: with ROV cutscenes and levels render correctly (slower).
* Outfit selection appears when a level is **loaded** (level start screen), not on the story transition from the
  prologue into the first level of a new game. Community guides: reload a level via PDA -> Revisit Location; some
  outfits (wetsuits, swimsuit) only in Treasure Hunt mode, which needs a finished game. Needed to identify which
  costume pack (pack1/pack2/pack20) is which.

## Inputs

`dlc_drms_build.py` reads pack11 (`600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000`) together with pack10;
`index_all` found 620 files in pack10 + pack11 (`work/idx_dlc.json`).

## First DLC 2 tree (stage 1, 2026-10-27)

`tools/dlc_media_build.py work/rebuild/dlc2_stage1/mods pack11` (log `logs/Manual_DLC2-Media_20261027_195120.log`
in the workspace): 167 DRMs (12 level units with their `_map` DRMs - ceremony room, goo room, machine room,
hall_ceremony_goo, hall_goo_machine, hall_machine_ceremony, level2_start, treasure_room_cine, yggdrasil_end,
yggdrasil_hall01/02 - plus 10 streamgroups), 19 music tracks, 6 cinstream `.mul`, 23 audio streams (all still
silent), 38 images, the merged object lists. Exit 0.

* **`player_tru_dlc2_extension.drm`** - a DLC-2-only extension of the player object, next to
  `viking_thrall_dlc2_extension` and `yeti_thrall_dlc2_extension`. The doppelganger / shadow-meter mechanics are
  therefore at least partly data (scripts in these DRMs), not only code in `tru.exe` - the first place to look for
  what the PC exe has to support.
* `g_pda.drm` is in the tree again (upstream leaves it out on purpose for DLC 1, see `docs/WS_MAP.md`).
* What the doppelganger / shadow mechanic brings as data (`tools/drm_strings.py`, new: sections + strings of a DRM,
  `--diff` against another version):
  * `player_tru_dlc2_extension.drm`: 57 sections, 44 scripts - mostly copies of base classes (`gamebase`, cameras,
    sensors); new for DLC 2 only script 22498, DTPs 22496/22497/22499/22864, mesh 22500, Obj 858.
  * Strings with "shadow" in nearly every DRM are render constants (`ShadowMapSampler`, `p_ShadowEnabled`, ...), not
    the mechanic. The level units reference the doppelganger's voice lines (`vo\dlc2\doppelganger\I_DG_PDLC2_...`).
  * `g_pda.drm` of pack11 vs the DLC 1 one: 19 sections new or changed - new script 26427 (DLC journal / objectives
    menu listing the DLC 1 and DLC 2 levels, `pda_dlc2_bg_1280/960`), new script 26428 (DLC 2 controls pages per
    language, `controls_dlc2_e/f/g/i/s/d` - most likely the LB/RB shadow-ability help), 3 new textures
    (7491, 7563, 7582), 14 grown PDA scripts (revisit-level list etc.). `uimeter` (script 204, an HUD meter class)
    is in the DLC 1 `g_pda` too, so it is generic.
  * Consequence: DLC 2 needs these `g_pda` parts, but the PC game has its own patched `g_pda.drm` (`patch.000`);
    replacing it would drop the PC patch. Plan: merge the 19 sections into the PC version instead (probably also
    why upstream leaves `g_pda` out for DLC 1). Where the shadow meter's HUD widget itself lives is still open.
* Audio (`dlc_audio_build.py work/rebuild/dlc2_stage1/mods work/rebuild/dlc2_stage2a/mods`, log
  `logs/Manual_DLC2-Audio_20261027_195456.log`): 8473 waves in 71 DRMs, 48 of 48 `.mul` (one channel per Xbox
  stream). Measured with `compare_audio.py ... dlc2_stage2a --xbox-only` (new mode, no reference tree): worst channel
  vs the decoded Xbox source min 25.1 / median 41.0 / max 53.8 dB (39 stereo median 38.1, 9 other median 44.8) -
  the same quality as DLC 1.
* Not done yet: locals/padshock, the 2b fixes, shaders. The symbol-map outlier of `docs/WINDOWS_REBUILD.md` finding
  27 affects DLC 2 scripts the same way (fixed since; finding 27).

## First DLC 2 tree through the full stage-1 route (assemble, 2026-10-29)

`tools/dlc_assemble_build.py work/rebuild/dlc2_stage1/mods work/rebuild/dlc2_asm_stage1/mods --pack pack11` (1
process, 3 008 s; with the symbol calibration and the mesh tables of finding 37), then `dlc_audio_build.py` into
`dlc2_asm_stage2a` (log `logs/Manual_DLC2-assemble_20261029_142625.log` in the workspace):

* **166 of 166 DRMs OK**; `assemble_report.tsv`: 0 DRMs with unresolved values (`bad`), 0 with missing PC shaders
  (DLC 1: also 0 / 0). Waves: 8 473 in 71 DRMs swapped, 0 skipped; `.mul` 48 of 48.
* No reference exists, so the checks are self-checks (`tools/tree_check.py`, new; same numbers for DLC 1 and B138
  as a yardstick):

  | Check | DLC 1 (asm_stage2b) | B138 | DLC 2 (dlc2_asm_stage2a) |
  |---|---|---|---|
  | DRMs read back as PC DRMs | 134 / 134 | 138 / 138 | **166 / 166** |
  | sections with relocations out of bounds | 0 | 0 | **0** |
  | id references outside their section | 0 | 0 | **0** |
  | id references to the same DRM / elsewhere | 145 366 / 1 443 | 163 493 / 1 334 | 234 127 / 935 |
  | sections | 46 793 | 49 093 | 39 411 |

* Meshes (`mesh_dlc.py`, finding 37): all DLC meshes valid and geometrically equal to the Xbox source; one DLC 2
  mesh (record 156, mesh 22994) has a vertex format unknown on PC (synthetic declaration hash, see below).
* Audio vs the decoded Xbox source (`compare_audio.py ... dlc2_asm_stage2a --xbox-only`): worst channel min 25.1 /
  median 41.0 / max 53.8 dB, 48 of 48 streams above the 25 dB target - unchanged from stage 2a.
* Stage 2b (`dlc_fixes_build.py dlc2_asm_stage2a_p11 -> dlc2_asm_stage2b --pack pack11`, finding 38; same log):
  all five fixes ran; tree still structurally clean (`tree_check.py`: 166/166 read back, 0 out-of-bounds
  relocations, 0 broken references).

  | Fix | DLC 1 (files / changes) | DLC 2 (files / changes) |
  |---|---|---|
  | `cine` | 2 / 4 command DTPs | 6 / 6 command DTPs (pdlc2_000_fight .. 050_crush; 17-100 words each) |
  | `float` | 4 / 60 | 17 / 138 (first run 18 / 16 243 - 16 105 in the two doppelganger model DTPs, wrong; fixed, finding 39) |
  | `tag404` | 6 / 16 | 1 / 14 (`doppelganger_casual.drm`) |
  | `postfix` | 3 / 20 strings | 3 / 5 strings |
  | `analog` | 18 / 33 (all = B138) | 17 / 1 088 (no reference) |

  The doppelganger models of DLC 2 are Lara-type character models (header `04c20453` with 16-bit arrays); measured
  against base `lara.drm` on PC, our conversion matches (96.1 % s16 vs 96.8 %) and upstream's `float_fix` would have
  broken them - it now skips character-model DTPs (finding 39). `analog` changed far more than on DLC 1 (1 088 vs 33,
  920 of them in `doppelganger_casual.drm`): it copies the real PC bytes of near-identical base-game DTPs where the
  Xbox bytes agree (33 of 33 = B138 on DLC 1); the doppelganger reuses many Lara DTPs, hence the count.
  Spot check (`tools/analog_report.py`, new): 1 066 fixes + **22 skipped as re-authored** (the guard works) in 157
  DTPs with 122 distinct base analogs; in `doppelganger_casual.drm` the fixes sit at the same field of 16-byte
  records (+0xc, +0x1c, +0x2c, ... in many DTPs, ~38-42 each) - one field type the learned table split wrongly,
  corrected from real base-game PC bytes of >= 90 % identical DTPs. Same kinds of byte permutation as on DLC 1.
  Judged trustworthy (unlike `float` on these files).
* `g_pda.drm` merged into the PC version (`tools/drm_merge_pc.py`, finding 40): 55 DLC 2 sections (changed + new)
  from our conversion, all 373 unchanged base sections = PC bytes, 7 PC sections appended, relocations remapped;
  0 out-of-bounds relocations. Output `work/rebuild/dlc2_merge/g_pda.drm` (not yet placed into a tree).
* Test tree `work/rebuild/dlc2_test/mods` (`tools/dlc_finish_build.py`, finding 41): stage 2b + merged `g_pda` +
  string tables (one table for both DLCs; DLC 2 description = locals index 457) + padshock; 166 DRMs, structurally
  clean. DLC 2 is mission-screen slot 2 (`dlc_level2_start.drm`); the menu patch of the B138 kit should cover it.
* Next: first test in the game - DLC 2 files on top of an installed B138 (= "both DLCs installed": the 10 shared
  files come from pack11, finding 38) with `scripts/windows/Install-TruTree.ps1 -Source work/rebuild/dlc2_test/mods`
  (dry run with `-Check`; undo with `-Restore`). Dry run against the installed B138 (2026-10-29): 186 files added,
  28 replaced (the 9 shared DRMs + 19 DLC 2 music tracks that B138 already ships in its own encoding), 79 already
  equal, `local\` and `padshock\` excluded (the installed string tables carry the DLC menu text fix and already hold
  the DLC 2 strings).
* **First test in the game (2026-10-29, Steam PC, German, test tree over the installed B138 kit)** - screenshots in
  the workspace's local `references/DLC2/` (`PC-Test-20261029_DLC2_*`), compared with the Xbox/Xenia references
  there (`Xbox-TU_DLC2_*`):

  | | Xbox (Xenia) | PC test | Reading / next step |
  |---|---|---|---|
  | DLC menu | *Lara's Shadow* with text | **works**: "Laras Schatten", preview image, full description, light-blue title (finding 41 confirmed: slot 2 appears with its start file) | - |
  | Loading screen | DLC 2 image, title and description | Croft Manor background, **no text** | the loading script does not know mission slot 2 (`generalbank` has "Invalid level id num passed in uiloading script!"); compare the Xbox TU `generalbank` loading script |
  | Costume / weapon choice | none, the mission starts | **Lara's costumes and weapons offered** | the PC flow treats DLC 2 like a normal Lara level |
  | Player character | **the doppelganger** (red hair, black outfit) | Lara in the chosen costume | follows from the costume choice; DLC 2 is played as the doppelganger - find where the Xbox flow forces her (TU `generalbank` / `player_tru_dlc2_extension`) |
  | Intro cutscene | doppelganger jumps, strangles Lara | **missing** | open (`cinstream/pdlc2_000_fight`; maybe tied to the same mission flow) |
  | Waterfall | bright, glowing | **rock-wall texture inside the water** | material / shader of the DLC 2 water - the DLC 2 shaders are not translated yet (stage 3) |
  | Hint box (top) | "The shadow meter drains when LB or RB is held ..." with icon | **grey box, no content** | the strings are present (TU index 1321/1323 -> PC 5206/5208, same in the installed and our tables) - suspects: the button-glyph characters (U+1800/1804/1806) or a wrongly mapped id in the hint data |
  | Camera pan to the wall | part of the tutorial | happens | - |
  | Stability | - | **no crash**; the level loads, Lara can move | - |

  Undo the test with `Install-TruTree.ps1 -Restore`.
* Test tree 2 (`work/rebuild/dlc2_test2/mods`, finding 42): as test tree 1 plus a `generalbank.drm` built with
  `tools/drm_put_sections.py` from the installed one (B138 + menu text fix): script 6 replaced by the converted
  **title-update loading screen** (DLC backgrounds, intro trigger), TU-only scripts 21239 ("dlc2data") and 20082
  added; 1 263 sections, 0 out-of-bounds relocations. Against the installed test tree 1 only `generalbank.drm`
  changes. To check: loading screen of DLC 2 (image + text), intro cutscene, costume choice / doppelganger, and that
  the base game and DLC 1 still load (script 6 serves every loading screen).
* Test checklist: DLC menu lists *Lara's Shadow* (slot 2) with its description (locals 457); the level starts; first
  cutscene; the doppelganger (model and shading - finding 39); the PDA (journal with both DLCs, DLC 2 control pages -
  finding 40); the shadow ability (LB/RB) and its HUD meter; afterwards DLC 1 still starts (shared files are now the
  pack11 versions).

## What the DLC 1 rebuild taught us for DLC 2 (checklist, kept up to date)

Collected while rebuilding DLC 1 step by step (`docs/WINDOWS_REBUILD.md`, findings in brackets). The big
difference: **for DLC 2 there is no finished build to compare with** (B138 only ships its music and menu images).
Every step needs another reference - the Xbox source, rules learned from the base game, or a test in game.

**Pipeline steps**
- Stages 0-1 already cover pack11: `dlc_drms_build`, `Convert` (307 DRMs = pack10 134 + pack11 166 + costumes) [run log 2026-10-27].
- **Run the DLC 2 audio and fix steps with `--pack pack11`** (`dlc_audio_build.py`, `dlc_fixes_build.py`; sets
  `TRUDLC_PACK_FIRST`): 10 file names exist in both packs with different content, and name lookups otherwise take
  the pack10 copy as the Xbox source [38]. Installing both DLCs needs one copy per name - see [38] for which.
- **The PC game is the Xbox retail state; DLC support came with the Xbox title update.** Mission screen, loading
  screen (DLC background + the trigger of the DLC intro cutscene), golden shotgun and a new "dlc2data" script are
  title-update scripts of `generalbank.drm` that the PC lacks [42]. When something DLC-specific is missing on PC,
  check `tools/tu_script_changes.py` for the file first.
- **Rules proven on DLC 1 can meet data DLC 1 does not have.** Upstream's `float_fix` (every change = B138 on DLC 1)
  would have rewritten 16 105 words of the DLC 2 doppelganger models; measuring against the closest base-game
  structure (`lara.drm` on PC, `tools/dtp_word_classes.py`) showed the converter was right [39]. Treat a large count
  from a fix as a question, and check every rule change on DLC 1 against B138 first (two of three attempts failed
  that check).
- Names first: `dlc_names.py` also takes the Xbox names of the kit manifests (hash-checked) [14]; pack11 still has
  63 unnamed non-DRM records - check which of them a DLC 2 tree needs before `Media`.
- `Media`: `dlc_media_build.py OUT pack11`; for pack11 itself `MUSIC_PACKS` falls back to pack11 only [13];
  `g_pda.drm` is left out on purpose by upstream [WS_MAP].
- `Audio`: `dlc_audio_build.py` - waves for every DRM incl. sub folders; `.mul` one channel per Xbox stream with
  the game's IMA convention (`mul_audio_nch.py`; upstream's B43 tool scrambles mono voice lines and layered music)
  [18]. Reference = the decoded Xbox source (`compare_audio.py`, `*_game_vs_xbox`), target >= 25 dB per channel.

**Data fixes (stage 2b) - what is generic, what is DLC-1-specific**
- `cine` (`work/ws/cine/build_cine.py`, `fx_apply.py`): hard-wired to pack10 (`PACKS[0]`) and the names
  `pdlc1_010_intro` / `pdlc1_030_finale` - needs the pack11 cutscene names and `PACKS[1]`. The command rules are
  generic (validated 106/106 on the base game); effect words without a rule fall back to the author's B44 tree,
  which does not exist for DLC 2 -> expect leftovers like the 9 words of [21].
- `float` (`work/ws/cine/float_fix.py`): generic for new DTPs (id >= 20000); finds its Xbox source in all packs
  (`raw_dlc`), but only reads the top folder of the tree (no `cinstream/`, `streamgroups/`) [22]. Every change was
  right on DLC 1.
- `tag404` (raft/grapple rings): generic rule - +4 word raw in `0x404` records of the new DLC DTPs; base-game DTPs
  (id < 20000) keep the converted value [23]. Check the DLC 2 rings with `tag404_check.py` against the rule itself
  (no B138 values).
- `tag_records.py` (rules per record tag learned from the base game) is a reference that works without B138: 0
  defects on DLC 1 [23].
- `postfix` (`tools/dlc1_postfix.py` steps 1-2): generic rules from the Xbox data (streamgroup name tables, type-0
  name strings) - run it on DLC 2 as is; it fixed 20 strings on DLC 1, all matching B138 [24]. Its step 3 (word log)
  is DLC-1-only and not public anyway.
- The fix tools imported by `dlc_generic.py` (dtpid, align, model points, tag 0x403, portals, link ratio,
  descriptors, aidata, soundplex) mostly run **only with `extra_fixes=True`** (`assemble_dlc` / material 'dlc'), not
  in a plain `dlc_convert_all.py` run - an earlier version of this list said otherwise [24, corrected in 32].
  Convert DLC 2 with the extra fixes on (`--extra-fixes`; needs `model_point_fix.py learn` and
  `dtpid_evidence.py` first). On DLC 1 they brought DTP sections from 97.6 % to 98.7 % = B138 [32].
- `analog` (`tools/analog_word_fix.py`): generic rule from the base game (DLC DTPs that are near-clones of a base
  DTP take the base PC bytes where the Xbox bytes agree; re-authored analogs skipped) - 33 words on DLC 1, all = B138
  [26]. Use it as is on DLC 2; `dlc_fixes_build.py` notes '= B138' only when a reference exists.
- Tools that read overlay folders: `load_overlay` paths are relative to the current folder, `dtp_audit.overlay`
  relative to `work/` - a wrong path silently scans 0 files [25].
- Symbol ids: check `work/generic/dlc_idmap.json` sym_info before converting - `xbox_max` must be the real
  Xbox maximum (base 16347, TU 19634), `shift` > 0. A bogus learned symbol (0xBEEB from the effect-DTP marker)
  once set the maximum to 48875 and shifted thousands of script words in DLC 1 [27]; fixed in `generic_symbols.py`.
  DLC-new symbols are shifted by `DLC_SYM_SHIFT = 480` (measured on B138; the rule gives 481) [29] - with both
  fixes DLC 1 scripts went from 79.5 % to 95.4 % = B138. For DLC 2 the same shift applies (one symbol space); a
  wrong shift shows up as a constant delta in `script_diff.py`'s histogram, but DLC 2 has no B138 to compare - so
  this DLC 1 calibration is what DLC 2 relies on. Since 2026-10-29 also 167 Symbol values missing from the learned
  map, calibrated on B138 (`docs/data/b138_symbol_calibration.json`, exact lookups only) [35]; DLC 2 symbols that
  are in neither table are still guessed from the lower neighbour.
- Watch the save game: a broken streamgroup name made "Create new savegame" hang in DLC 1 (`streamname_fix`);
  test saving early in DLC 2 [24].
- Upstream's `work/ws/` scripts still carry the author's local paths (407 of 578); fix each one when it is used [21].

**Stage 1 route**
- Use upstream's full route (`assemble_dlc`, material 'dlc'; `tools/dlc_assemble_build.py --pack pack11`,
  source tree = the DLC 2 Media tree): on DLC 1 it gave real PC shader sections (97.7 % = B138) and better materials (90.4 %)
  at the same data results [34]. It needs the `work/render/` tables: `render_tables_build.py build`, then
  `rend_extract.py pairs` / `dlc`, `shader_map`, `material_rules`, `material_dlc`, `pc_shader_sections`,
  `terrain_validate` [28]. `rend_extract.py dlc` and `shader_map` already cover pack11.
- Meshes need `mesh_tables_build.py` (vertex-declaration hashes + DEC3N table, learnt from the base pairs, each
  Xbox mesh id counted once; part of step Assemble) - without it every DLC mesh gets a synthetic declaration hash
  and +-1 normals [37]. Upstream's `mesh_dlc.py` (all 285 DLC meshes of both packs): 285 valid, geometry equal to
  the Xbox, **1 mesh with a vertex format the PC base game does not have: pack11 record 156, mesh 22994**
  (position, normal, blend indices, three UV sets, tangent, binormal) - it keeps the synthetic hash. What we know
  about the PC hash (18 formats, 14 hashes): it ignores BLENDWEIGHT (4 pairs of formats that differ only by it
  share a hash), so it describes the semantics a shader reads rather than the byte layout; FNV-1/1a 64, MD5, SHA-1
  and CRC32 over the semantic ids (with/without BLENDWEIGHT, sorted or not, with types/offsets) reproduce none of
  them (scratch test, 2026-10-29). Open: look for this semantic set in PC-only base meshes (outside the 1 054
  pairs), else test in game whether the engine accepts an unknown hash.

**Measuring**
- `compare_sections.py` / `rebuild_status.py` need a reference tree - for DLC 2 only the base-game rules and the
  Xbox source exist; plan in-game tests per level (crashes, physics, cutscenes) earlier than for DLC 1.
- Decode audio instead of comparing MD5 [17]; know each tool's assumptions (a half/half stereo decoder produced a
  false "B138 is broken" result) [17, 18].

**Environment**
- Do not run heavy analyses in parallel to pipeline steps that load `dlc_drms.pkl` (~3 GB) or the generic store:
  a 4-second `dlc_generic.py` took 90 minutes that way [29].
- Run Python tools with `-I -X utf8` (cp1252 pipes break on non-Latin-1 output) [19].
- Menu: the PC DLC menu lists only installed DLC; DLC 2's description (locals index 457) has the same hard line
  breaks as DLC 1 -> `dlc_text_unwrap.py` already covers it [DLC_MENU].
