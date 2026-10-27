# DLC 2 *Lara's Shadow* (`pack11.000`) - notes

Status upstream: "the converter handles generic parts, nothing was tested" (INVESTIGATION.md item 9). The B138
installer only takes DLC 2 menu images and music from `pack11.000`; the PC DLC menu lists only installed DLC, so
*Lara's Shadow* does not appear there yet.

## Xbox reference (Xenia Canary 02d2cb5, game + TU 0.0.2.3 + DLC, 16:9)

Screenshots in the TRU-DLC project, `Referenzen/DLC2/` (not in this repository).

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

## What the DLC 1 rebuild taught us for DLC 2 (checklist, kept up to date)

Collected while rebuilding DLC 1 step by step (`docs/WINDOWS_REBUILD.md`, findings in brackets). The big
difference: **for DLC 2 there is no finished build to compare with** (B138 only ships its music and menu images).
Every step needs another reference - the Xbox source, rules learned from the base game, or a test in game.

**Pipeline steps**
- Stages 0-1 already cover pack11: `dlc_drms_build`, `Convert` (307 DRMs = pack10 134 + pack11 166 + costumes) [7, 185].
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
- Most fix tools run inside `Convert` already (`dlc_generic.py`: dtpid, align, model points, tag 0x403, portals,
  link ratio, descriptors, aidata, soundplex) and therefore apply to pack11 too [24].
- Watch the save game: a broken streamgroup name made "Create new savegame" hang in DLC 1 (`streamname_fix`);
  test saving early in DLC 2 [24].
- Upstream's `work/ws/` scripts still carry the author's local paths (407 of 578); fix each one when it is used [21].

**Measuring**
- `compare_sections.py` / `rebuild_status.py` need a reference tree - for DLC 2 only the base-game rules and the
  Xbox source exist; plan in-game tests per level (crashes, physics, cutscenes) earlier than for DLC 1.
- Decode audio instead of comparing MD5 [17]; know each tool's assumptions (a half/half stereo decoder produced a
  false "B138 is broken" result) [17, 18].

**Environment**
- Run Python tools with `-I -X utf8` (cp1252 pipes break on non-Latin-1 output) [19].
- Menu: the PC DLC menu lists only installed DLC; DLC 2's description (locals index 457) has the same hard line
  breaks as DLC 1 -> `dlc_text_unwrap.py` already covers it [DLC_MENU].
