# TruMenu.asi

In-game debug menu for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld, image base 0x400000), operated with the
**Xbox controller** and drawn with [Dear ImGui](../third_party/imgui/README.md) (MIT, v1.91.9). Every menu entry is also
an **item with a stable id** that tools can list and run without the controller (exports `TruMenuList` /
`TruMenuInvoke`, TruLink command `menu`).

**Status: 0.1.3 runs in the game (menu drawn through the swap chain's Present, L3 + R3, items over TruLink). 0.2
(status page, outfits page, level select with the base game) and 0.3 (Crystal's original developer menu drawn from
the exe's own tables, time / player / HUD, instances, live outfit switch, Debug / Log page + overlay, videos,
experimental markup drawing, weapons / ammo / health) built 2026-10-31 and checked with `dumpbin` only (x86 DLL,
imports `KERNEL32.dll` + `USER32.dll`, exports `TruMenuVersion` / `TruMenuList` / `TruMenuInvoke`) - not yet run in
the game.**

## Controls

| Input | Effect |
|---|---|
| **L3 + R3** (both sticks pressed together) | open / close the menu (edge-triggered; `[Menu] ToggleButtons`) |
| D-pad / left stick | move between entries |
| A | activate (button, checkbox, open a page) |
| B | back / cancel (ImGui) |
| LB / RB, triggers | ImGui navigation tweaks (sliders) |
| `[Menu] ToggleKey` (off by default, e.g. 119 = F8) | open / close from the keyboard |
| mouse / keyboard | work while the menu is open (forwarded from the game window's message loop) |

While the menu is open the game gets a **neutral pad** (no buttons, sticks centred, triggers 0; the packet number is
kept). After a toggle the pad stays neutral until both sticks are released, so the game never sees the L3 / R3 press
that closed the menu. Keyboard and mouse messages still reach the game. The very first stick pressed (before the
second one completes the combo) does reach the game for a frame or two.

## Pages and items

The menu window holds collapsible pages. The id in brackets is the item that the button runs.

| Page | Content | Items |
|---|---|---|
| Status | TruMenu version, `tru.exe` PE time stamp / image size, all code checks, whether a level is loaded; current unit + stream unit id; game state; costume line (current costume, game-data base, `+0x1f4`, chosen `+0x20c` / `+0x20e` / `+0x210`, unit default); player line (instance, object id / name, type record, object-table entry); our plugins (`TruShadowPower`, `TruDoppelganger`, `TruDlc2Player`, `TruRockVein`, `TruLink`: loaded? `<Name>Version()` string), ModLoader.asi, the pad chain (what the game calls, what PadHook calls, with module names), the `d3d9.dll` in use (game folder = TRAWindowed proxy, else system), device / window | `status.version`, `status.hooks`, `status.unit`, `status.state`, `status.costume`, `status.player`, `status.plugins` |
| Outfits (next level load) | the same costume facts, then one button per **player record of the game's type table** (index, name, object id; `[chosen]` / `[current]` marked), "Reset chosen costume", checkbox "reload the current unit after choosing" | `costume.records`, `costume.current`, `costume.choose <index\|name> [20c\|210]`, `costume.choosereload <index\|name>`, `costume.choosereset`; the 0.2 ids `costume.setreload` / `costume.reset` still work. **0.3 changed** `costume.list` (now the live cycle list; the 0.2 list = `costume.records`) and `costume.set` (now the live switch; the 0.2 meaning = `costume.choose`) |
| Overlay: Lara's position | checkbox for a small top-left overlay with Lara's position and heading; position / rotation in the page | `overlay.position`, `player.position` |
| Free camera | known facts; experimental `CAMERA_SetMode(mode)` with a mode slider (TRLAU enters its free camera with mode 11; TruLink notes that retail switches only for 6, 11, 12) and "Restore game camera". **TODO** own free camera (moving the camera transform with the sticks) | `camera.current`, `camera.mode <n>`, `camera.restore`, `camera.free` (todo) |
| Cheat / flight | `GameTracker.cheatMode` + player message 12 (TRLAU "skew" cheat); while on and the menu is closed **RT lifts, LT lowers** Lara (`[Cheat] FlightSpeed` per 30 fps frame) | `cheat.flight [0/1]`, `cheat.speed <v>` |
| Markup / collision draw | 0.3: experimental markup drawing (boxes / poly lines of the MarkupManager projected with the game's view matrix into ImGui's background draw list), "ledges only", projected-space size. `draw.debugflag` was **removed** (debugFlags2 0x100 is the TR7 / TRAE path, catalog section 7) | `draw.markup [0/1]`, `draw.ledges [0/1]`, `draw.scale <w> <h>` |
| Quick access / Favourites | 0.3, **first page, open when the menu opens** (Status is now collapsed): one widget per favourite id (bool = checkbox, info = value, other = button that runs the item with its default argument); **Y** on an item pins / unpins it (on this page, in "Add an item" and on the Developer menu rows - other pages: use "Add an item" or TruLink); saved in `[Favorites] Ids`; default list (empty `Ids`): `player.invincible, player.health, time.scale, time.pause, level.reload, overlay.position, log.overlay, costume.next` (`camera.free` is skipped while it is a todo) | `fav.list`, `fav.add <id>`, `fav.del <id>` |
| Developer menu (original) | 0.3: Crystal's own debug menu, read at load from the tables in `.data` and drawn row by row: page links switch pages, flags / bools as checkboxes, ints as sliders / inputs with the table's limits, actions as buttons; the table's callbacks / functions run on the game thread. Every row shows its static facts (who reads the target in retail, empty functions) in blue; "All pages" lists every page, also those the retail root no longer links | `dev.list`, `dev.<label slug>` (42 ids, list below) |
| Time / player / HUD | 0.3: time scale slider, freeze world, hide HUD; player control, ragdoll death, mark / back to mark, camera fov; weapons / ammo / health (experimental, catalog section 17) | `time.scale <f>`, `time.pause [0/1]`, `ui.hide [0/1]`, `player.control [0/1]`, `player.die`, `player.teleport x y z`, `player.mark`, `player.recall`, `player.goto <inst>`, `camera.fov <rad>`, `player.health [n]`, `player.invincible [0/1]`, `weapon.list`, `weapon.give <name>`, `ammo.show`, `ammo.set <type> <n>` |
| Instances | 0.3: the instance list (name filter, max 200 shown), per instance: Lara goes there, bring to Lara, unhide, remove; "Unhide all" | `instance.list [filter]`, `instance.info <inst>`, `instance.bring <inst>`, `instance.unhide <inst>`, `instance.unhideall`, `instance.remove <inst>` (`<inst>` = intro id, `0x<address>` or `#<index>`) |
| Outfits (live switch) | 0.3: "Next outfit" and one button per id of the game's outfit cycle list; switches at once (needs a level) | `costume.list`, `costume.next`, `costume.set <name\|id>` |
| Debug / Log | 0.3: the last lines of every `Tru*.log` next to the `.asi` / `tru.exe` (tailed once per second by the worker thread, shared read, only new bytes), the game's script prints (`log.script`), lines mentioning errors / exceptions in red, counters (exception lines, exceptions TruMenu caught in its own game calls); source filter buttons (TruLink.log holds the last TruLink commands); corner overlay bottom left | `log.page`, `log.show`, `log.script [0/1]`, `log.overlay [0/1]`, `log.lines <n>`, `log.filter <source\|all>`, `log.clear` |
| Settings | 0.3: every `TruMenu.ini` key with its current value, changed keys marked `*` (yellow) with their default, missing keys shown with the default; "Favourites back to the default list" and "Reset all settings" - both need **A twice** (the button turns red: "press A again to confirm", 5 s) | `settings.show`, `settings.reset` (backup `TruMenu.ini.bak_<yyyymmdd_hhmmss>`, rewrite from the defaults table, reload the options; Scale / Enabled / Script apply at the next start), `fav.reset` |
| Media: videos | 0.3: `Movies\*.bik`, "Play" (main menu only), "as menu loop" | `media.video.list`, `media.video.play <name>`, `media.video.menuloop [name]` |
| Level select | current unit name (GameTracker+0x38), one button per unit of `[Levels] List` (default `dlc_level1_start`, `dlc_level2_start`), "Reload current unit", then **all 111 playable units** in tree nodes per group (see below). Any other unit: `menu level.load <unit>` over TruLink | `level.current`, `level.list` (all units: `group: unit unit ...; ...`), `level.presets` (`[Levels] List`; was `level.list` in 0.1), `level.load <unit>`, `level.reload` |
| Dev channel | there is no developer channel in `tru.exe` (TCP 9264 is FMOD's profiler). **TODO** re-enable the compiled-out log stub 0x6457a0 | `dev.log` (todo) |

Items that need a level (camera, cheat) answer / show **"needs a level"** while no player instance exists
(`[0xe7f094]` = 0, e.g. in the main menu). Level select works from the main menu as well.

### Item interface (no controller)

```c
const char *__cdecl TruMenuList(void);                          // "id\ttype\tvalue\tlabel\n" per item
const char *__cdecl TruMenuInvoke(const char *id, const char *arg);   // "ok ..." / "err ..."
```

- Types: `bool` (arg `""` toggles, `0` / `1` / `on` / `off` set), `int` / `float` / `action` (arg as described),
  `info` (read-only: `TruMenuInvoke` returns `ok <id> <value>`), `todo` (answers `err todo`).
- `menu.open`, `overlay.position`, `cheat.speed` run at once on the caller's thread (0.3: also `time.scale`,
  `player.mark`, `instance.list` / `instance.info`, the `log.*` settings, `draw.*`, `player.invincible`,
  `media.video.menuloop`). `camera.mode`, `camera.restore`, `cheat.flight`, `level.load`, `level.reload`, the
  `costume.*` actions, every `dev.<slug>` row and the other 0.3 actions (`time.pause`, `player.*`, `ui.hide`,
  `camera.fov`, `instance.bring` / `unhide` / `unhideall` / `remove`, `log.script`, `media.video.play`,
  `weapon.give`, `ammo.set`, `player.health`) are queued (one slot) and run on the **game thread**
  - inside PadHook, or inside the Present hook while the game does not poll the pad; `TruMenuInvoke` waits up to 3 s
  and returns the result, else `ok queued <id> (...)` and the item runs at the next frame. A second request while one
  is pending answers `err busy`.
- The returned text lives in a buffer of the calling thread until that thread's next call.
- TruLink 0.2: `menu list`, `menu <id> [arg]` (e.g. `Invoke-TruLink.ps1 -Command 'menu level.load dlc_level2_start'`).
- Values are one line (`; ` between entries) so `level.list` / `costume.list` fit TruLink's one-line answer; the
  per-thread buffers are 48 KB (answer) / 16 KB (one value).

## Level list (0.2)

Source: the PC unit list the game loads, `tr8/pc-w/unitlist.txt` (119 units; the repository's merged list
`work/generic/merged/tr8/pc-w/unitlist.txt`, byte-identical to the installed `mods/tr8/pc-w/unitlist.txt` on
2026-10-31). `tools/menu_unit_table.py` turns it into the `kUnits` table in `TruMenu.cpp` (re-run it and paste the rows
when the list changes). Groups, all from the list itself:

| Group | Rule | Units |
|---|---|---|
| Base game l1 .. l7 | `levels\...`, by the unit name prefix `l1_` .. `l7_` (the `l7_*` units sit in the folder `levels\l5`) | 23, 16, 9, 11, 6, 6, 13 |
| DLC 1 | `dlc\dlc_level1\...` | 12 |
| DLC 2 | `dlc\dlc_level2\...` | 11 |
| DLC other starts | `dlc\dlc_level3..6\dlc_levelN_start` | 4 |

Not offered (not playable units): `container\*`, `dlc\container\*`, `dlc\dlc_costume_containers\*`, `imf\*`,
`special\cinefx`. Chapter / location titles ("Mediterranean Sea" ...) are **not** shown: they are not in the unit list
and were not verified against the game's text data (TRLAU-menu-hook has such names; not taken).

## Outfits (0.2)

All addresses read from the PC `tru.exe` with `tools/pe_dis.py` / `pe_callers.py` / `player_type_table.py` and
checked against the expected bytes at load (`costume` / `unit table` on the Status page).

| Fact | PC address | Notes |
|---|---|---|
| game data pointer | `[0x00c59264]` | re-allocated by the new-game reset tru+0x156940 - read fresh every time |
| level load: chosen costume | tru+0x1de2d6 in `GAMELOOP_LevelLoadAndInit` tru+0x1de2b0 | `u16 +0x1f4 == 0 ? +0x20c : +0x210` (as retail Xbox 0x8229b3f0); if non-zero and accepted by the validator the name is `[0xdb94d0][id*8]`; in `l1_seatop` (string 0x85539c) it takes `lara_wetsuit_warm` instead; a name in byte buffer `0x0084216c` (empty) overrides all; else the unit default `[[unit+8]+0x70]+0x294` |
| costume validator | `0x005c54e0` bool cdecl(id) | id <= object count, then tru+0x1bf7b0(name) (`<name>.drm` present) |
| current costume | `[0x00e7f1c8]` | object id written by the level load (= the player object) |
| object names | `[0x00db94d0]` | +0 count, name of id n at +n*8; name -> id tru+0x1bf770 |
| type table | operand of tru+0x1bf121 (orig. `0x008aba28`, 0x1c per record) | the Outfits list = records whose f2 is the player's `0x007228e0` (36 on PC: records 0-11 and 15-38; 37 with TruDlc2Player's `doppelganger_casual`); index = record index |
| state save | tru+0x155cb1 | `word [gd+0x20c] = word [0xe7f1c8]` - the game's own write of the field |
| new-game reset | tru+0x156abe .. 0x156ad7 (PC partner of TU 0x821fe9a8) | `+0x210 = +0x20e = +0x20c = 0`, then `+0x228 / +0x226 / +0x224 = 100` |
| unit default | stream unit table `0x00dbab40` (0xd8 per unit, +0 id, +4 state 2, +8 data), unit id `[0x00e7f148]` | tru+0x1c1b50, read at tru+0x1de379 |

- `costume.set <index|name> [20c|210]` (game thread): record must be a player record and in the object list; the
  game's validator 0x5c54e0 must accept it; then **u16 object id -> game data + 0x20c** (or **+0x210** while
  `+0x1f4 != 0`; the optional slot argument forces one). Takes effect at the next level load. `costume.setreload` also
  reloads the current unit (`level.reload`).
- `costume.reset` (game thread): **+0x210, +0x20e, +0x20c = 0** in the current game data - only those three words of
  the reset; the next level load takes the unit default (`dlc_level2_start`: 11 `lara_doppelganger`, which
  TruDlc2Player turns into `doppelganger_casual`).
- The costume-selection screen's own write was **not** located: no other code writes `+0x20c` / `+0x210` by
  displacement; the scripts set costumes through `uigamedata` natives (e.g. stub 0x7a0d79 -> 0x77bd50 ->
  tru+0x1d9f40 `[0xe7f1c8] = id(name)` + costume load request tru+0x1c1760 - an immediate load, not the chosen
  field). The loading-screen script (generalbank script 6, function 5) names the base costumes `lara_casual`,
  `lara_bikini`, `lara_jungle_heavy`, `lara_jungle_a`, `lara_jungle_b`, `lara_snow_light`, `lara_snow_heavy`,
  `lara_wetsuit_cold`, `lara_wetsuit_warm` and the DLC costumes `dlc_costume_a..p`, `dlc_doppel_costume_a..d`.
- Display names (localised outfit titles) are not shown; the list shows object names.

## Developer menu (original) (0.3)

Crystal Dynamics' debug menu **data** is still in the retail `.data` (0x8aaa6c .. 0x8ab3f0); the driver that drew it
is gone (the root page 0x8aaae8 is referenced only from the tables and from the lone dword 0x8aaa9c). TruMenu reads
the rows at load (`DevRead`, check: the root row must be `{0x0b, 0, 0, 0x855070, 0x8aaa6c, 0}` with the label
"This should not be the Options Title") and draws them as their types say - labels, targets, limits, masks and
callbacks all come from the table. `tools/devmenu_dump.py` lists the same rows statically (with the retail code that
reads each target) - re-run it for this table:

```text
../bin/pyt -t 300 tools/devmenu_dump.py <tru.exe>          pages, rows, readers
../bin/pyt -t 300 tools/devmenu_dump.py <tru.exe> --md     Markdown table
../bin/pyt -t 300 tools/devmenu_dump.py <tru.exe> --raw    plain rows
```

**Row format** (0x18 bytes = 6 dwords): `+0 type`, `+4 min` (int) / argument (action), `+8 max` (int), `+0xC label`
(`char*`), `+0x10 target` (variable, function or page), `+0x14 mask` (flag) / value (bool) / callback (int).

| Type | Meaning | TruMenu |
|---|---|---|
| 0x00 flag | bit(s) `mask` of the dword at `target` | checkbox, read-modify-write of the dword |
| 0x02 bool | byte at `target`, `+0x14` = 0xffffffff (the value for "on") | checkbox, writes 0xff / 0 (all three targets are in `.rdata`: written with `VirtualProtect`) |
| 0x03 int | s32 at `target`, range `[+4, +8]`, optional callback `+0x14` called after a change | slider (range <= 255) or input with step; clamps; callback cdecl with argument 0 (as the game's own caller 0x5d3760 calls 0x5d36a0) |
| 0x09 action | cdecl function `target`, `+4` = its argument (only the Chapter rows have one: `"chapterN"`) | button; empty functions (`ret` / `jmp` to `ret`) are marked "empty in retail" |
| 0x0A page link | `target` = first row of a page | button that switches the page |
| 0x0B title | page title, `target` = parent page (root: the empty page 0x8aaa6c) | heading |
| 0x10 end | end of a page (label "", target 0xe7f098 in every end row) | - |
| 0x11 header | page header with a text layout string (`"-abs 160 40 -center"`), followed by empty 0x10 slots | note (5 such pages, all empty in retail) |

**Count (2026-10-31, Steam `tru.exe`): 101 rows in 15 pages** - 22 actions, 10 flags, 7 ints, 3 bools, 9 page links,
2 titles, 5 headers, 43 end rows; **42 value / action rows** with an id `dev.<slug of the label>` (lower case, every
run of other characters = `_`, e.g. `dev.show_spline_info`, `dev.fog_far`, `dev.perfect_game_now`,
`dev.chapter_1`). The retail root only links "Units" (with "Reload Current Unit") and the "Chapters" action; the
other pages are reachable through "All pages" in the menu.

| Row | Id | Type / target | Static facts (`devmenu_dump.py`; effect in retail not verified live) |
|---|---|---|---|
| 0x8aaab8 | `dev.reload_current_unit` | action 0x5dfba0 | if `[0xe7f141]` == 0 { if streamFlags & 0x200000: 0x5570f0(0); 0x5df760(4) }; `[0xe7f143]` = 0 |
| 0x8aab00 | `dev.keep_info_between_loads` | flag streamFlags 0xe7f0b8 & 0x200000 | live: read by 0x5dfba0 and ~20 other sites |
| 0x8aab30 | `dev.chapters` | action 0x5d37b0 | `jmp 0x6457a0` (empty): compiled out |
| 0x8aab78 | `dev.save_current_game` | action 0x6457a0 | empty function: compiled out |
| 0x8aab90 | `dev.restore_game` | action 0x555d40 | streamFlags \|= 0x200000 only |
| 0x8aabd8 | `dev.show_spline_info` | flag 0xe7f09c & 0x400000 | readers with this mask: 0x5cf331, 0x5cf434, 0x5cf57b |
| 0x8aabf0 | `dev.enable_keypad` | flag 0xe7edb4 & 1 | no reader found |
| 0x8aac38 / 50 | `dev.fog_far` / `dev.fog_near` | int 0x8aaa60 / 0x8aaa64, -1 .. 0x9400, callback 0x5d36a0 | callback writes the current unit's fog (unit +0x94 / +0x98 / +0xa0..a3) and calls 0x5bfe10 / 0x5bfe40; **needs a level** |
| 0x8aac68 / 80 / 98 | `dev.fog_red` / `green` / `blue` | int 0xe7eda0 / a4 / a8, 0 .. 255, callback 0x5d36a0 | as above |
| 0x8aacb0 | `dev.restore_fog` | action 0x5d3760 | unit fog defaults (0xe7b8a0 / 0xe7ecdc) back, then 0x5d36a0(0) |
| 0x8aacf8 | `dev.projected_shadows` | flag 0x8aaa54 & 1 | written once at init (0x5df56d = 1), no reader found |
| 0x8aad10 | `dev.show_input_actions` | flag 0xa02b80 & 1 | no reader found |
| 0x8aad28 | `dev.frame_rate_lock` | int 0xe7f1a8, 0 .. 3 | live: read at 0x5da2e9 |
| 0x8aad40 | `dev.time_mult` | int 0xe7f1a4, 0 .. 0x4000 | live: init 0x1000 (0x5d3d44), read at 0x5da380 |
| 0x8aad58 | `dev.ignore_object_scripts` | bool 0x8550c0 (`.rdata`) | no reader |
| 0x8aad70 / 88 / b8 | `dev.vv_stats` / `dev.show_music_vars` / `dev.enable_screenshot` | flag 0xe7f098 & 0x2000000 / 0x10000000 / 0x4000 | debugFlags is tested with a register mask (0x5dfd7b ...): unresolved |
| 0x8aada0 | `dev.show_monster_music_vars` | flag 0xe7f0a0 & 0x1000000 | no reader with this mask found |
| 0x8aadd0 | `dev.perfect_game_now` | action 0x5d3510 | `[0xe7f0b4]` \|= 0x100 (GameTracker+0x2c) - progress bit, TruMenu cannot undo it |
| 0x8aae18 | `dev.ui_trigger_all_fade_groups` | action 0x5d7590 | calls `[0x8ab79c](float [0x8416b4])` |
| 0x8aae30 | `dev.ui_make_hints_modal` | flag 0xe7f0a4 & 0x200000 | no reader with this mask found |
| 0x8aae48 / 0x8aaf38 | `dev.unlock_all_unlockables` / `dev.skip_all_puppet_shows` | bool 0x8550c2 / 0x8550c1 (`.rdata`) | no reader |
| 0x8ab280 .. 0x8ab3d0 | `dev.chapter_1` .. `dev.chapter_15` | action 0x6457a0("chapterN") | empty function: compiled out |

Guards: every row needs `[Cheat] Experimental=1`; ints with a callback and non-empty actions need a level (the fog
callback dereferences the current stream unit); everything runs inside `__try` (an exception is reported and counted
on the Debug / Log page). Over TruLink: `menu dev.list`, `menu dev.fog_far 9000`, `menu dev.show_spline_info 1`,
`menu dev.time_mult` (no argument = current value and range).

## 0.3 items: facts

Every address is checked at load against an instruction of the game that uses it (Status page line "0.3: ...",
`TruMenu.log` "0.3 checks"). Sources: catalog `docs/Menue-Funktionen-Katalog.md` (TRLAU facts with file / line) and
our own disassembly with `tools/pe_dis.py` / `pe_callers.py` on 2026-10-31.

| Item(s) | Fact | Check at load |
|---|---|---|
| `time.scale` | float timeDilation 0xe7f1d0 (GameTracker+0x148, TRLAU), 0..10 | init `fst [0xe7f1d0]` 0x5d3d25, reader 0x5da3a0 |
| `time.pause` | streamFlags 0xe7f0b8 bit 0x1000 (TRLAU F3) | 0x555d40 `or dword [0xe7f0b8], 0x200000` |
| `player.control` | byte 0x8ab4e6, 1 = on (TRLAU) | 0x5d5f45 / 0x5d5f60 (`mov byte [0x8ab4e6], 1 / 0`) |
| `player.die` | INSTANCE_Post(player, 4, 3) (TRLAU F11) | INSTANCE_Post prologue (0.1) |
| `ui.hide` | bool 0xcdc9a0 (TRLAU) | `cmp byte [0xcdc9a0], 0` at 0x5a434c |
| `camera.fov` | float current camera `[0xe80534]` + 0xb0 (TRLAU) | none in code; refuses unless the field already holds 0.05 .. 3.1 |
| `instance.*`, `player.goto` | first instance `[0xd98d54]`, next +0x08; +0x10 object (+0x14 object id), +0x20 position, +0x30 rotation, +0x58 intro id, +0x14 iflags, +0x23c no-draw groups (TRLAU); unhide = message 7, 0 (TRLAU) | `mov [0xd98d54], ecx` 0x5b2ec6 and the game's own walk at 0x5d467d (`esi = [0xd98d54] ... esi = [esi+8]`) |
| `instance.remove` | INSTANCE_ReallyRemoveInstance 0x5bc4e0 cdecl (inst, 0, 0) (TRLAU); refused for the player | prologue |
| `costume.next` / `costume.set` | the game's switch **0x6f0a90** (reached from the costume native 0x79db50 -> 0x778ca0, which sets altPlayerObjectID 0xe7f1cc from its table first): if `[0xe7f1cc]` != 0 it becomes the current costume, else the id after the player's object id in GlobalInfo `[0xe7ee50]+4` `{u16 count; u16 *ids at +4}`; then INSTANCE_Post(player, 35, 0) two game frames later (TRLAU: weapons). TruMenu sets `[0xe7f1cc]` itself (0 = next) and calls 0x6f0a90; `costume.set` checks the id with the game's validator 0x5c54e0 | 0x6f0a90, 0x778ca0, 0x79db50 prologues, `mov edx, [0xe7ee50]; mov edi, [edx+4]` at 0x6f0ac7 |
| `log.script` | the 8 NsCoreBase print / log natives (registered as natives 0..7 at 0x7b3920 .. 0x7b399e, cdecl `(instance, numArgs, DataValue *args)`, 4 bytes per argument): 0x795d30 print int, 0x795d50 bool, 0x795d80 float, 0x795db0 string (args: value, float time, bool newline) and 0x795dd0 / 0x795df0 / 0x795e10 / 0x795e30 log int / bool / float / string (value, newline). In retail they end in empty functions (0x574be0 `ret 0xc`, 0x7987b0 `ret 8`) or in sprintf into a dropped stack buffer (0x4a3200 .. 0x4a32c0). TruMenu writes a 5-byte `jmp` to its handlers over their first bytes while `log.script` is on (restored when off); a string argument is read as `char*` or pointer to one (not verified) | registration bytes at 0x7b3990 + the first bytes of all 8 |
| `media.video.*` | player 0x4a12b0 cdecl (name, bool loop) (catalog 11.1), only when main state `[0xe7ed60]` = 10 (TRLAU: main menu); menu background name pointer `[0x8abf20]` = "medsea_loop" 0x8552a8, read at 0x5daf35 | prologue, 0x5d56e0 reader, 0x5daf35 bytes + `[0x8abf20]` == 0x8552a8 |
| `draw.markup` / `draw.ledges` | MarkupManager `[0xdb94cc]` (vtable object); the walk 0x5c3ce0 (called with `ecx = [0xdb94cc]` at 0x5d3349): box = `[mgr+0x14]`, next `[box+4]`, `+0x20` MarkUp, `+0x28` flags; MarkUp `+0x34` position, `+0x58` poly line `{int count; points at +0x10 + 16*i}` (all moved by the world shift there = world space). Projection as TRANS_RotTransPersVectorf 0x49f630: `view = M * p`, M = 4 columns of 16 bytes at 0xa038f0; `x' = x / z * f + 256`, `y' = y / z * f + 224`, f = float `[0x8906d0]` (512.0 in the file), centre doubles 0x843a00 / 0x8454c8; drawn when z > 16 (TRLAU). The **512 x 448 screen space** is our reading of those constants and is scaled to the back buffer (`draw.scale`) - to verify live. Colour per flag bit with the catalog's (TRLAU) names, not verified for box +0x28 | 0x5c3ce8, 0x5c3d1e, 0x5c3d54, 0x5c3da2, 0x5d3349, 0x49f64e / 67f / 6f8 / 702 / 713 |
| `weapon.give` | WM::GiveWeaponByName 0x7161f0 thiscall `ecx = [[0xfadb58]+0x500]`, `(name, 1, 0)` (catalog 17.1: the default loadout's call; blocks while the object streams in) - only when main state = 1 | prologue |
| `ammo.*` | reserve u16 `playerstate+0x51c+2*type`, 6 types (catalog 17.2) | HUD reader `movzx eax, word [ecx+edx*2+0x51c]` 0x6e8475 |
| `player.health` / `player.invincible` | float `playerstate+0x628` (GetHealth 0x6e7860); MaxHealth 0x6e7990 `() -> float`; invincible = variant A of catalog 17.5 (health = MaxHealth once per game frame in PadHook; state deaths such as falls still kill) | 0x6e7860 and 0x6e7990 prologues |
| Debug / Log | `Tru*.log` in the `.asi` folder and the `tru.exe` folder, read with `FILE_SHARE_READ \| WRITE \| DELETE`, only the new bytes (at most the last ~6 KB per second, 2 KB at first sight); ring of 512 lines; per frame only a copy of the shown lines | - |

## Hooks

Every address below is checked against the expected bytes at load (`Start()`); on a mismatch that part stays off,
the reason goes to `TruMenu.log` and the Status page shows `NO`. Nothing is patched in the game code itself - with one
opt-in exception since 0.3: `log.script` writes a 5-byte `jmp` over the start of the 8 script print / log natives
(restored when it is turned off; see "0.3 items: facts").

### Pad: import filter on `GetProcAddress`

The game loads XInput itself: tru+0x824f0 calls `LoadLibraryW(L"xinput9_1_0.dll")`, then `GetProcAddress` through
its import slot **0x0083e08c** and stores `XInputGetState` in **0x00a02b8c** - the pointer the per-frame pad poll at
tru+0x84b82 (`call dword ptr [0x00a02b8c]`) calls. The same import slot serves the `Direct3DCreate9` lookup at
tru+0x1239e6. At load TruMenu replaces the slot (it is filled long before the game reaches its XInput setup) with a
filter that passes every lookup through and hands out **PadHook** for `"XInputGetState"` only. So the game itself writes
PadHook into 0x00a02b8c.

**Chaining with TruShadowPower / TruLink.** These plugins wait until 0x00a02b8c is non-zero and then wrap whatever it
holds. Because the game writes PadHook there, they always wrap TruMenu, whatever order the ASI loader loads the
plugins in: `game -> TruShadowPower / TruLink -> PadHook -> XInputGetState`. PadHook neutralises the pad *before*
the outer hooks see it, so the shadow power and TruLink's frame hook get the neutral pad while the menu is open.
TruMenu follows the project's chaining rule (shared with TruShadowPower 0.5.1 and TruLink):

1. hook once;
2. re-hook only when the slot points into the real `XInputGetState` again (address inside a module whose name starts
   with `xinput`) - never because the slot is "not mine";
3. a thread-local re-entry guard: if PadHook is entered again on the same thread (another wrapper that wrapped
   PadHook and is also called by it), the inner call goes straight to the real `XInputGetState`.

Late load (the pointer is already filled when TruMenu starts): PadHook is placed on top of whatever the slot holds,
once (compare-exchange); rule 3 keeps an older plugin that re-wraps everything (TruShadowPower 0.5) from recursing.
If even that swap fails, the menu reads the pad itself and **cannot block** the game's input (Status page says so).

Mixed versions: TruShadowPower **0.5** (re-wraps whenever the slot is not its own) together with TruLink can make
TruLink cut the loop by calling the real `XInputGetState` directly - PadHook is then no longer called. TruMenu notices
that (no PadHook call for 250 ms) and reads the pad in Present, so the menu still opens, but input is not blocked.
Use TruShadowPower **0.5.1** or later (same chaining rule) with TruLink + TruMenu.

**Front end.** If PadHook has not been called for 250 ms (main menu, loading - the game may not poll the slot
there), the Present hook reads the pad itself (`XInputGetState` of the loaded xinput module, pad index of the last
active pad) for the L3 + R3 toggle and the menu navigation, and runs queued items there. Input is not blocked then.

### Direct3D 9: device vtable

The device manager is created at tru+0x1239c0 and stored in **[0x00ad75e4]**; its `IDirect3DDevice9*` is the
`ppReturnedDeviceInterface` of the CreateDevice call at tru+0x122736, i.e. **manager+0x20** (`lea ebp,[esi+0x20]`
at tru+0x12270a; manager+0x208 holds the present parameters - 0.1 used it by mistake, fixed in 0.1.3). Since 0.1.3
the implicit swap chain's `Present` (slot 3) is hooked as well - the game presents through it. A worker thread polls that pointer (50 ms until found, then every second for a new device) and
patches the device's own vtable entries **Reset (16)** and **Present (17)** (`VirtualProtect`, original saved before
the swap). This is independent of who provides `d3d9.dll`: with TRAWindowed's proxy in the game folder the vtable
patched is the one of the object the game calls (the proxy's or the system one), and other overlays that hook later
chain on top. `d3d9.dll` is never replaced, `Direct3DCreate9` is not hooked.

- Present: when the menu or the overlay is visible, `BeginScene` -> ImGui frame -> `EndScene`, then the original
  Present. With nothing to show it only checks the keyboard toggle and the front-end pad read.
- Reset: `ImGui_ImplDX9_InvalidateDeviceObjects` before the original; the next frame re-creates them.
- ImGui is created on the first frame that shows something; window = the device's focus window (or the swap chain's
  device window); its window procedure is chained (`SetWindowLongPtr`) and forwards messages to ImGui only while the
  menu is open. `imgui.ini` is not written (`IniFilename = nullptr`).

### Game functions (experimental, `[Cheat] Experimental=1`)

| Use | Address | Check | Source of the fact |
|---|---|---|---|
| player instance | `[0xe7f094]` = GameTracker 0xe7f088 + 0xc | reader at 0x741764 | TRLAU `Game.h`, TruShadowPower |
| position / rotation | instance +0x20 / +0x30 (16-byte vectors) | - | TRLAU `Instance.h`, `cdc/math/Vector.h` |
| cheatMode | byte 0xe7f144 (GameTracker+0xbc) | - | TRLAU `Game.h`, `modules/Skew.cpp` |
| INSTANCE_Post(instance, msg, data) | 0x5b3750, cdecl | prologue bytes | TRLAU `instance/Instance.cpp`; message 12 = flight from `Skew.cpp` |
| CAMERA_SetMode(mode) | 0x5f39f0, cdecl | prologue bytes | TRLAU `game/Camera.cpp`, docs `Befund-Entwicklerkanal.md` |
| camera restore | 0x5edf50, thiscall CameraManager 0xe804f0 | prologue bytes | TRLAU `modules/camera/Underworld.cpp` |
| GAMELOOP_RequestLevelChangeByName(name, gameTracker, doneType) | 0x5df8c0, cdecl, doneType 4 | prologue + name copy to GameTracker+0x38 | name / signature TRLAU `game/Game.cpp`; doneType 4 and the reload of GameTracker+0x38 from the game's own callers tru+0x1dfb73 / tru+0x3744b3 |
| frame time | float 0xe7f190 (30 fps units) | store at 0x5da40c | TruShadowPower |

The level change is refused while `GameTracker+0xb9` is set (the function itself ignores requests then) and for names
with characters other than `a-z 0-9 _ -` or longer than 63 characters; the menu closes after a request.

## Options (`TruMenu.ini` next to the `.asi`, optional)

Since 0.3 every key, its default and its comment live in **one table** (`kOpts` in `TruMenu.cpp`): a missing key
takes the table's default, `settings.reset` writes the file from that table, and the shipped `TruMenu.ini` is that
exact text - `../bin/pyt -t 60 tools/trumenu_ini_check.py` checks it (`--print` shows the generated text). Change a
default or comment only in the table, then copy `--print` into `TruMenu.ini`.

| Section / key | Default | Meaning |
|---|---|---|
| `[Menu] Enabled` | 1 | 0 = load but hook nothing |
| `[Menu] LogLevel` | 1 | 0 errors, 1 info, 2 every toggle / item, 3 debug; `TruMenu.log` next to `tru.exe` |
| `[Menu] ToggleButtons` | 192 (0x00C0) | XInput button mask that opens / closes the menu (all buttons of the mask together) |
| `[Menu] ToggleKey` | 0 | virtual key that also toggles the menu (0 = off) |
| `[Menu] Scale` | 1.5 | font and spacing scale (0.5 .. 4) |
| `[Menu] Overlay` | 0 | 1 = position overlay on from the start |
| `[Pad] BlockInput` | 1 | 0 = the game sees the pad while the menu is open |
| `[Cheat] Experimental` | 1 | 0 = no game-changing actions (pages read-only) |
| `[Cheat] FlightSpeed` | 20 | units per 30 fps frame at full trigger |
| `[Levels] List` | `dlc_level1_start,dlc_level2_start` | units offered as buttons on the Level select page |
| `[Favorites] Ids` | (empty = default list) | favourite item ids, comma list; rewritten by TruMenu when you pin / unpin (`WritePrivateProfileString` on this file) |
| `[Log] Overlay` | 0 | 1 = log lines in the bottom-left corner from the start |
| `[Log] Lines` | 12 | lines on the Debug / Log page and in the overlay (1 .. 64) |
| `[Log] Script` | 0 | 1 = redirect the 8 script print / log natives from the start (patched at load, before any script runs; needs `Experimental=1`) |

## Build, install, test (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Name TruMenu -Verbose   # also compiles src\asi\third_party\imgui -> work\asi\TruMenu.asi
.\scripts\windows\Set-TruMenu.ps1 -Install                  # copies .asi + .ini next to tru.exe (game closed)
.\scripts\windows\Set-TruMenu.ps1 -Remove                   # removes them again (only if they are a build of ours)
```

Static runtime (`/MT`), imports `KERNEL32.dll` and `USER32.dll` only. Test plan for the first run:

1. Main menu: press L3 + R3 - the menu appears (Status page open). Check the code-check line (all `ok`), the pad line
   ("PadHook given to the game ..."), `d3d9.dll` path, "pad read in Present" (yes = the game does not poll there).
   Navigate with the D-pad / A, close with L3 + R3.
2. Level select from the main menu: "Load dlc_level2_start" (or `menu level.load ...` over TruLink).
3. In a level: open the menu - Lara must not move while it is open; Overlay page -> tick the position overlay, close
   the menu, walk: the numbers change. With TruShadowPower: LB / RB do nothing while the menu is open.
4. Cheat / flight ON, close the menu, RT / LT - Lara rises / sinks. Turn it off again.
5. Free camera page: `CAMERA_SetMode(11)`, then "Restore game camera".
6. Send `TruMenu.log` (and `TruShadowPower.log` / `TruLink.log` if loaded).

0.2 additions (built e.g. with `-OutDir work\asi\menu02` so the 0.1.3 build stays):

7. Status page: the line `costume ok, unit table ok`; unit / state / costume / player lines change between main
   menu and a level (`menu status.costume` over TruLink gives the same text).
8. Level select: open "Base game l2", load `l2_junglehub` - the level loads; then DLC 1 / DLC 2 starts as before.
9. Outfits in a level: tick "reload ...", choose `lara_bikini` - the unit reloads with that outfit; `menu
   costume.current` shows its id. "Reset chosen costume", reload: the unit default comes back.
10. With TruDlc2Player loaded the list holds `doppelganger_casual` as well (record 39).

0.3 additions (built with `-OutDir work\asi\menu03`). Every step: note the result and send `TruMenu.log`.

11. Quick access opens first with the default favourites; Y on "time.pause" removes it, "Add an item" -> Y / A adds
    it back; `TruMenu.ini` next to the `.asi` now has `[Favorites] Ids=...`; `menu fav.list` / `fav.add dev.fog_far`.
    Then the Status page: the two "0.3:" lines - every entry `ok` (`dev menu ok`, ... `markup draw ok`, `weapon.give ok`,
    `ammo ok`, `health ok`); `TruMenu.log` holds "0.3 checks" and "dev menu: 101 rows in 15 pages".
12. Developer menu page (main menu): root shows the title, "Keep Info Between Loads", "Units ->", "Chapters (empty in
    retail)"; "Units ->" and "<< root page" work; "All pages" lists 15 pages. `menu dev.list` over TruLink lists 42
    rows; `menu dev.time_mult` answers `4096 (0..16384)` (init value 0x1000).
13. Developer menu in a level, one live test per row (note what changes on screen): Show Spline Info, Projected
    Shadows, Show Input Actions, VV Stats, Show Music Vars, Show Monster Music Vars, Enable ScreenShot, UI Make Hints
    Modal; Fog Far / Near / RGB (the fog should change at once), Restore Fog; Frame Rate Lock 0..3; Time Mult (e.g.
    2048 / 8192). Leave out "Perfect Game NOW" (progress bit, not undone) unless on a throw-away save.
14. Time / player / HUD in a level: time scale 0.3 / 1.0, freeze world on / off, hide HUD on / off, player control off
    (Lara does not react) / on, mark, walk away, back to mark, camera fov slider, ragdoll death last.
15. Instances: list fills (names, positions); "Lara goes there" to a pickup (flight on), "Bring to Lara", "Remove" on a
    harmless object; `menu instance.list wp_` / `menu instance.info #0` over TruLink.
16. Outfits (live switch) in a level: "Next outfit" changes Lara at once and she keeps her weapons (message 35 a frame
    later); a button of the list switches to that outfit; `menu costume.list` gives the same ids.
17. Debug / Log: lines from TruMenu / TruLink / TruShadowPower appear within a second; filter buttons; overlay on;
    "script prints" on, play a bit - script lines appear (or not: then the natives are not called in retail - note
    it); `menu log.page`, `menu log.lines 20`, `menu log.filter TruLink`.
18. Media in the main menu: Play `intro` (watch whether the game shows it and returns to the menu), "as menu loop"
    `explode`, leave and re-enter the main menu (background changes?), "menu loop back to medsea_loop".
19. Markup draw in a level near ledges: lines / circles appear; if they are offset or scaled, try `menu draw.scale
    640 480` (or the sliders) and note the values that fit; "ledges only".
20. Weapons / health in a level (main state 1): `menu weapon.give wp_shotgun` (an already loaded weapon first),
    `menu ammo.show`, `menu ammo.set 1 50` (HUD reserve changes?), "Full health", "invincible" + a hit (no damage).
21. Settings: pin something (Ids changes, `*` on the Settings page); "Reset all settings" once - nothing happens but
    the red "press A again" - A again: `TruMenu.ini.bak_<time>` appears next to the `.asi`, the ini equals the shipped
    one, favourites are the default list again; `menu settings.show`, `menu fav.reset`.

## Credits

- **Dear ImGui** by Omar Cornut and contributors (MIT), unmodified in `src/asi/third_party/imgui`.
- **TheIndra55/TRLAU-menu-hook** (GPL v3, <https://github.com/TheIndra55/TRLAU-menu-hook>) was **read as a reference
  only** (2026-10-31, raw.githubusercontent.com): the TR8 addresses / signatures / flags marked "TRLAU" above (GameTracker
  layout, Instance position offset, INSTANCE_Post, CAMERA_SetMode / restore, cheatMode + message 12,
  GAMELOOP_RequestLevelChangeByName; 0.3: timeDilation, streamFlags 0x1000, player control byte, message 4 / 3,
  UI hidden byte, camera fov offset, instance list / offsets, message 7, INSTANCE_ReallyRemoveInstance, the costume
  switch native 0x79db50 + message 35, the script print natives, the markup flag bit names, z > 16 for drawing) come
  from it. No code or structure of it is used; TruMenu's hooks (import filter
  for the pad, device-vtable patch found through the game's own device manager) are our own and differ from its
  approach (an inline hook of the game's D3D init function and the game's frame callbacks).
- Camera manager / mode facts cross-checked in `docs/Befund-Entwicklerkanal.md` of the project.
- The **developer menu** is Crystal Dynamics' own data in `tru.exe` (labels, limits, targets, callbacks); TruMenu only
  reads and draws it. Its format was decoded by us (`tools/devmenu_dump.py`); weapons / ammo / health facts are from
  the project's static pass (catalog section 17).

License: MIT, as the repository.
