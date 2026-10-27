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
