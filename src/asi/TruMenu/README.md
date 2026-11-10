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
the game. 0.4 (TO TEST checklist filled over TruLink, log page: collapse repeats / hide TruLink reads / severity
filter / rate limit, `weapon.slots` / `weapon.has`, `ammo.fill`, `gear.give`) built 2026-10-31 into `work\asi\menu04`,
checked with `dumpbin` only - not yet run in the game. 0.5 (TO TEST row kinds step / check / toggle, `test.step`,
`test.toggle`, `test.export`; for `scripts\windows\Invoke-TruTestRun.ps1`) built 2026-10-31 into `work\asi\menu05`,
checked with `dumpbin` only - not yet run in the game. 0.6 (**command bar**: one input line directly under the menu
window, autocomplete, history, pad picker, `cmd.focus` / `cmd.run` / `cmd.history`, `[Cmd]` keys; on top of the 0.5
source with the TruGuard items `guard.*`) built 2026-11-01 into `work\asi\menu06`, checked with `dumpbin` only - not
yet run in the game. 0.7 (TruGuard action `guard.dump`: full minidump + thread snapshot on the TruLink thread, also
while the game hangs; longer `guard.status` buffer) built 2026-11-02 into `work\asi`, checked with `dumpbin` only -
not yet run in the game. 0.7 also got the **command bar without a keyboard** (Steam Machine at the TV): L3 = focus +
on-screen keyboard, the mouse belongs to the menu while it is open, `[Cmd] UpOpensHistory` /
`FirstPadPressOnlyFocuses`, `cmd.keyboard`; built 2026-11-02 into `work\asi\menu07` (with guard.dump), checked with
`dumpbin` only - not yet run in the game (section "Controller and mouse (0.7)"). 0.7 was live-tested 2026-11-02 (mouse,
L3 keyboard, history, real keyboard, `time.scale` ok; typing moved Lara, Esc opened the pause menu, B closed the menu).
0.7.1 (**game input frozen while the menu is open**: `[Menu] BlockGameInput` holds the game's DirectInput keyboard and
the key messages, `[Menu] PauseGame`; B twice = keyboard, then menu; the real-keyboard switch no longer depends on
hover / focus; `level.start` + `[Test] AutoStart` = the mission menu's DLC start with intro; `[Log] UnitChanges`)
built 2026-11-02 into `work\asi\menu071`, checked with `dumpbin` and offline byte checks only - not yet run in the
game (section "Game input frozen (0.7.1)"); live test 2026-11-02 20:28: `level.start dlc2` showed the outfit selection,
a `level.load` during it hung the game. 0.7.2 (**`game.quit`** with a safety step and exit code 0x544D; level.load /
level.start **refused while a mission start is pending** (main state 2 / 9); `level.start` with the **title update's
outfit rule** - DLC 2 without the outfit selection, `[Levels] OutfitRule`; Level page DLC 1 first; log overlay filter
`[Log] OverlaySources` / `OverlayExclude`) built 2026-11-02 into `work\asi\menu072`, checked with `dumpbin` and offline
byte checks only - not yet run in the game (section "Mission start, outfit rule, game.quit (0.7.2)"). 0.8.0
(**Regression page** with the fixed DLC 1 / DLC 2 lists and `TruMenu.regress_results.txt`; **Cheats page** from the
2007 prototype evaluation - god mode, one-hit kill, enemy health, infinite ammo, fill 'er up, cheat codes, each with
its category and byte pre-check; **camera log** `[Log] CameraChanges`) built 2026-11-02 into `work\asi\menu080`,
checked with `dumpbin` and offline byte checks only - first live test 2026-11-02 22:15-22:26 (runs `221539`, `223338`,
`224047`). 0.8.1 (fixes from that test: game.quit "Quit now" button, `[Log] InputTrace`, menu keys released at open /
close, a queued item runs once, cheat.ammo reasons per weapon, `player.unstuck`, regression shortcuts) built
2026-11-02 into `work\asi\menu081`, compiled (0 warnings in TruMenu.cpp) and offline checks only - not yet run in the
game (section "Live-test fixes (0.8.1)"). 0.9 (Saves page, music) built 2026-11-02 into `work\asi\menu09` (section
"Saves page and music (0.9)"; since 0.9 the DLL also imports `SHELL32.dll` for `SHGetFolderPathW`). 0.10 (**radial
menu**: L3 + R3 held / F9 held = a ring of up to 8 entries from `TruMenu.radial.txt`, `[Radial]` keys; stage R2
`instance.spawn <object>` behind `[Radial] Spawn=1`) built 2026-11-03 into `work\asi\menu010`, compiled (0 warnings in
TruMenu.cpp), `dumpbin` and offline byte checks only - not yet run in the game (section "Radial menu (0.10)").
`camera.free` is still a todo (see "0.4 items").**

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
| 0.6: typing | goes to the **command bar** under the menu (it has the keyboard focus when the menu opens); see "Command bar (0.6)" |
| 0.6: D-pad / stick / B while the bar has the focus | the focus goes into the menu window (as before 0.6; 0.7 `[Cmd] FirstPadPressOnlyFocuses=0`: the press also moves there) |
| 0.6: View (Back) in the menu, F2, Tab | back to the bar (View: pad picker, F2 / Tab: typing) |
| 0.7: **L3** alone (press + release, menu open; `[Cmd] FocusButton`) | focus into the bar + **on-screen keyboard** under it; L3 again closes the keyboard (see "Controller and mouse (0.7)") |
| 0.7: mouse while the menu is open | belongs to the menu (`[Menu] FreeMouse`): ImGui draws a cursor, the game gets no mouse messages (no camera turn, no re-centring), its `SetCursorPos` / `ClipCursor` wait until the menu closes |
| 0.7.1: keyboard while the menu is open | belongs to the menu (`[Menu] BlockGameInput`): the game's DirectInput keyboard reads no key events, no key message reaches the game - typing does not move Lara, Esc does not open the pause menu |
| 0.7.1: **B, B** with the on-screen keyboard open | first B closes the keyboard, a second B right after it closes the menu |
| 0.10: **L3 + R3 short** (< `[Radial] HoldMs`, menu closed) | opens the menu **at the release** (with `[Radial] Enabled=1` and HoldButtons = ToggleButtons); in the open menu L3 + R3 still closes at the press |
| 0.10: **L3 + R3 held** (>= HoldMs, 500 ms) / **F9 held** / `[Radial] MouseButton` held | the **radial menu** (section "Radial menu (0.10)"): right stick / mouse picks, the release runs |

While the menu is open the game gets a **neutral pad** (no buttons, sticks centred, triggers 0; the packet number is
kept). After a toggle the pad stays neutral until both sticks are released, so the game never sees the L3 / R3 press
that closed the menu. 0.7.1 (`[Menu] BlockGameInput=1`, default): the game gets **no keyboard** either - see "Game input
frozen (0.7.1)". With `BlockGameInput=0` it is as in 0.7: key messages still reach the game except `WM_KEYDOWN` /
`WM_CHAR` / `WM_DEADCHAR` / `WM_SYSCHAR` while a text field or the on-screen keyboard has the focus (key-up messages
always pass), and the game's DirectInput keyboard is not touched (that is why typing moved Lara in the 0.7 live test).
With `[Menu] FreeMouse=1` no mouse message reaches the game while the menu is open. The very first stick pressed
(before the second one completes the combo) does reach the game for a frame or two.

## Pages and items

The menu window holds collapsible pages. The id in brackets is the item that the button runs.

| Page | Content | Items |
|---|---|---|
| TO TEST | 0.4, **first page, open, shown only while the list holds rows** (header "TO TEST (n open, n ok, n fail, n skip)"): one row per test - state, hint, id, note; on the selected row **A = OK, X = FAIL, Y = SKIP** (X / Y go to the row, not to ImGui, while a row has the focus), buttons OK / FAIL / SKIP and "Run <id>" when the id is a menu item (`id:arg` runs it with `arg`); "Remove the marked rows", "Remove all rows" (A twice). 0.5: **switches** (toggle rows, a checkbox each) on top, then **numbered steps** (NEXT marks the first open one; A = run its item + done) and checks in list order. Filled by the main session or `Invoke-TruTestRun.ps1` over TruLink; kept in `TruMenu.tests.txt` next to `tru.exe` (sections "TO TEST" below) | `test.add <id> <hint>`, `test.step <n> <id\|id:arg\|-> <text>`, `test.toggle <id> <item\|ini:Plugin:Section:Key> <text>`, `test.mark <id> ok\|fail\|skip\|open\|done\|on\|off [note]`, `test.list`, `test.export`, `test.del <id>`, `test.clear [done]` |
| Regression | 0.8, under TO TEST, collapsed (header "Regression DLC 1 + DLC 2 (n open, n ok, n fail, n skip)"): selector **DLC 1 / DLC 2 / all**, the rows of `TruMenu.regress_dlc1.txt` / `_dlc2.txt` (next to the `.asi`, copied by `Set-TruMenu.ps1`); checks **A = OK, X = FAIL, Y = SKIP**, buttons OK / FAIL / SKIP / **Note** (puts `regress.note <list>:<id> ` into the command bar and opens the on-screen keyboard; Enter saves); steps: A = run its item + done; "Reload lists" (A twice). Every mark / note is appended to `TruMenu.regress_results.txt` (section "Regression, Cheats, camera log (0.8)") | `regress.list`, `regress.load dlc1\|dlc2\|all`, `regress.mark <dlc1:id\|dlc2:id\|id> ok\|fail\|skip\|open\|done [note]`, `regress.note <list:id> <text>`, `regress.export`; 0.8.1: Quick prepare list + Prepare per row (column 9 shortcut), `regress.prepare <list:id>\|stop`, `regress.shortcuts` |
| Cheats (2007 prototype evaluation) | 0.8: one row per cheat with its **category** (PC has it / re-attach / cheat-code path / rebuild from prototype); a failed byte pre-check greys the row and names the reason in red; in a level only; the "rebuild" rows are listed read-only as "not built yet" | `cheat.list`, `cheat.god [0/1]`, `cheat.godfull [0/1]`, `cheat.onehitkill [0/1]`, `cheat.enemyhealth [0/1]`, `cheat.ammo [0/1]`, `cheat.fillup`, `cheat.code <1\|2\|9\|10\|11>` |
| Status | TruMenu version, `tru.exe` PE time stamp / image size, all code checks, whether a level is loaded; current unit + stream unit id; game state; costume line (current costume, game-data base, `+0x1f4`, chosen `+0x20c` / `+0x20e` / `+0x210`, unit default); player line (instance, object id / name, type record, object-table entry); our plugins (`TruShadowPower`, `TruDoppelganger`, `TruDlc2Player`, `TruRockVein`, `TruLink`: loaded? `<Name>Version()` string), ModLoader.asi, the pad chain (what the game calls, what PadHook calls, with module names), the `d3d9.dll` in use (game folder = TRAWindowed proxy, else system), device / window; 0.7.2: button **"Quit game (press twice)"** at the end (section "Mission start, outfit rule, game.quit (0.7.2)") | `status.version`, `status.hooks`, `status.unit`, `status.state`, `status.costume`, `status.player`, `status.plugins`, 0.7.2 `game.quit` |
| Outfits (next level load) | the same costume facts, then one button per **player record of the game's type table** (index, name, object id; `[chosen]` / `[current]` marked), "Reset chosen costume", checkbox "reload the current unit after choosing" | `costume.records`, `costume.current`, `costume.choose <index\|name> [20c\|210]`, `costume.choosereload <index\|name>`, `costume.choosereset`; the 0.2 ids `costume.setreload` / `costume.reset` still work. **0.3 changed** `costume.list` (now the live cycle list; the 0.2 list = `costume.records`) and `costume.set` (now the live switch; the 0.2 meaning = `costume.choose`) |
| Overlay: Lara's position | checkbox for a small top-left overlay with Lara's position and heading; position / rotation in the page | `overlay.position`, `player.position` |
| Free camera | known facts; experimental `CAMERA_SetMode(mode)` with a mode slider (TRLAU enters its free camera with mode 11; TruLink notes that retail switches only for 6, 11, 12) and "Restore game camera". **TODO** own free camera (moving the camera transform with the sticks) | `camera.current`, `camera.mode <n>`, `camera.restore`, `camera.free` (todo) |
| Cheat / flight | `GameTracker.cheatMode` + player message 12 (TRLAU "skew" cheat); while on and the menu is closed **RT lifts, LT lowers** Lara (`[Cheat] FlightSpeed` per 30 fps frame); 0.21.6: a key line bottom right while flying (`[Cheat] FlightHint`) | `cheat.flight [0/1]`, `cheat.speed <v>` |
| Markup / collision draw | 0.3: experimental markup drawing (boxes / poly lines of the MarkupManager projected with the game's view matrix into ImGui's background draw list), "ledges only", projected-space size. `draw.debugflag` was **removed** (debugFlags2 0x100 is the TR7 / TRAE path, catalog section 7) | `draw.markup [0/1]`, `draw.ledges [0/1]`, `draw.scale <w> <h>` |
| Quick access / Favourites | 0.3, **first page, open when the menu opens** (Status is now collapsed): one widget per favourite id (bool = checkbox, info = value, other = button that runs the item with its default argument); **Y** on an item pins / unpins it (on this page, in "Add an item" and on the Developer menu rows - other pages: use "Add an item" or TruLink); saved in `[Favorites] Ids`; default list (empty `Ids`): `player.invincible, player.health, time.scale, time.pause, level.reload, overlay.position, log.overlay, costume.next` (`camera.free` is skipped while it is a todo) | `fav.list`, `fav.add <id>`, `fav.del <id>` |
| Developer menu (original) | 0.3: Crystal's own debug menu, read at load from the tables in `.data` and drawn row by row: page links switch pages, flags / bools as checkboxes, ints as sliders / inputs with the table's limits, actions as buttons; the table's callbacks / functions run on the game thread. Every row shows its static facts (who reads the target in retail, empty functions) in blue; "All pages" lists every page, also those the retail root no longer links | `dev.list`, `dev.<label slug>` (42 ids, list below) |
| Time / player / HUD | 0.3: time scale slider, freeze world, hide HUD; player control, ragdoll death, mark / back to mark, camera fov; weapons / ammo / health (experimental, catalog section 17) | `time.scale <f>`, `time.pause [0/1]`, `ui.hide [0/1]`, `player.control [0/1]`, `player.die`, `player.teleport x y z`, `player.mark`, `player.recall`, 0.8.1 `player.unstuck [mark\|safe]`, `player.goto <inst>`, `camera.fov <rad>`, `player.health [n]`, `player.invincible [0/1]`, `weapon.list`, `weapon.give <name>`, `ammo.show`, `ammo.set <type> <n>`; 0.4 (TruLink / favourites, no own widgets on this page): `weapon.slots`, `weapon.has <name>`, `ammo.fill`, `gear.give <name>` |
| Instances | 0.3: the instance list (name filter, max 200 shown), per instance: Lara goes there, bring to Lara, unhide, remove; "Unhide all" | `instance.list [filter]`, `instance.info <inst>`, `instance.bring <inst>`, `instance.unhide <inst>`, `instance.unhideall`, `instance.remove <inst>` (`<inst>` = intro id, `0x<address>` or `#<index>`) |
| Outfits (live switch) | 0.3: "Next outfit" and one button per id of the game's outfit cycle list; switches at once (needs a level) | `costume.list`, `costume.next`, `costume.set <name\|id>` |
| Debug / Log | 0.3: the last lines of every `Tru*.log` next to the `.asi` / `tru.exe` (tailed once per second by the worker thread, shared read, only new bytes), the game's script prints (`log.script`), lines mentioning errors / exceptions in red, counters (exception lines, exceptions TruMenu caught in its own game calls); source filter buttons (TruLink.log holds the last TruLink commands); corner overlay bottom left. 0.4: repeated lines of a source collapse into one `text x42 (17:09:02-17:09:33)`, TruLink's read-type command lines are dropped, filter all / warnings + errors / errors (warnings yellow, errors red), at most `[Log] MaxLinesPerSecond` new lines per source and second (then one line "(n lines dropped ...)"), counters for all three | `log.page`, `log.show`, `log.script [0/1]`, `log.overlay [0/1]`, `log.lines <n>`, `log.filter <source\|all>`, `log.clear`; 0.4: `log.collapse [0/1]`, `log.hidereads [0/1]`, `log.level 0\|1\|2` (or `all` / `warn` / `error`), `log.rate <n>`; 0.7.2: `log.overlaysources <list\|*>`, `log.overlayexclude <list\|none>` (overlay only, section "Log overlay filter (0.7.2)") |
| Settings | 0.3: every `TruMenu.ini` key with its current value, changed keys marked `*` (yellow) with their default, missing keys shown with the default; "Favourites back to the default list" and "Reset all settings" - both need **A twice** (the button turns red: "press A again to confirm", 5 s) | `settings.show`, `settings.reset` (backup `TruMenu.ini.bak_<yyyymmdd_hhmmss>`, rewrite from the defaults table, reload the options; Scale / Enabled / Script apply at the next start), `fav.reset` |
| Media: videos | 0.3: `Movies\*.bik`, "Play" (main menu only), "as menu loop" | `media.video.list`, `media.video.play <name>`, `media.video.menuloop [name]` |
| Level select | current unit name (GameTracker+0x38), one button per unit of `[Levels] List` (default `dlc_level1_start`, `dlc_level2_start`), "Reload current unit", 0.7.1: "Start DLC 1 / DLC 2 as the mission menu (intro)" (0.7.2: DLC 1 first; a grey line says why level.load / level.start are refused right now), then **all 111 playable units** in tree nodes per group (see below). Any other unit: `menu level.load <unit>` over TruLink | `level.current`, `level.list` (all units: `group: unit unit ...; ...`), `level.presets` (`[Levels] List`; was `level.list` in 0.1), `level.load <unit>`, `level.reload`, 0.7.1 `level.start [dlc2\|dlc1\|<unit>]` (game thread, main menu only; "Game input frozen (0.7.1)") |
| Dev channel | there is no developer channel in `tru.exe` (TCP 9264 is FMOD's profiler). **TODO** re-enable the compiled-out log stub 0x6457a0 | `dev.log` (todo) |
| Radial menu (0.10, no page: a ring over the game) | the entries of `TruMenu.radial.txt`; the Status page has a line `radial (0.10): ...`, the Settings page the `[Radial]` keys (section "Radial menu (0.10)") | `radial.status`, `radial.list`, `radial.reload`, `radial.open [path]`; stage R2 `instance.spawn <object>` (`[Radial] Spawn=1`) |
| Command bar (0.6, own window under the menu) | one input line: `<id> [arg]`, `get <id>`, `list [filter]`, `help`; autocomplete, history, pad picker (section "Command bar (0.6)"); 0.7: on-screen keyboard under the bar (section "Controller and mouse (0.7)") | `cmd.focus`, `cmd.run <line>`, `cmd.history`; 0.7: `cmd.keyboard` |

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
- 0.4: the `test.*` items, `log.collapse` / `log.hidereads` / `log.level` / `log.rate`, `weapon.slots` and
  `weapon.has` (read-only, our own reads under `__try`) run at once on the caller's thread; `ammo.fill` and
  `gear.give` are queued for the game thread.
- 0.6: `cmd.focus`, `cmd.run` and `cmd.history` run at once on the caller's thread; `cmd.run <line>` then runs the
  line's own item through the same path (a game-thread item waits as usual), see "Command bar (0.6)". 0.7:
  `cmd.keyboard` (open the menu, focus the bar, show the on-screen keyboard) runs at once as well.
- The returned text lives in a buffer of the calling thread until that thread's next call.
- TruLink 0.2: `menu list`, `menu <id> [arg]` (e.g. `Invoke-TruLink.ps1 -Command 'menu level.load dlc_level2_start'`).
- Values are one line (`; ` between entries) so `level.list` / `costume.list` fit TruLink's one-line answer; the
  per-thread buffers are 48 KB (answer) / 16 KB (one value).

## Command bar (0.6)

One input line in a small window **directly under the menu window** (same width, follows the menu when it is moved;
pushed up to stay on screen). It is a window of its own, so the menu window and its navigation are unchanged: TO TEST
/ Quick access still open first in the menu. The bar is drawn whenever the menu is open (`[Cmd] Enabled=1`).

| Line | Effect |
|---|---|
| `<id>` on a value item (bool / int / float / info, developer-menu flag / bool / int rows) | shows the value: `ok time.scale = 1.000` (does **not** toggle - unlike `menu <id>` over TruLink) |
| `<id>` on an action | runs it without argument (`level.reload`, `costume.next`, `player.mark`) |
| `<id> <arg>` | sets / runs with the argument: `time.scale 0.5`, `ui.hide 1`, `costume.set doppelganger_casual`, `level.load dlc_level2_start`, `dev.fog_far 9000`, `fav.add dev.fog_far` |
| `get <id>` | the value (alias of `<id>` alone, also for actions: `get level.load` = current unit) |
| `list [filter]` | ids containing the filter (`list cost`) |
| `help` | the short help in the result line |

- **Execution:** every line goes through `InvokeCore` - the function behind `TruMenuInvoke`; the bar calls it without
  waiting: items for the game thread go into the same one-slot queue (`ok queued <id> ...`, `err busy` while another
  request is pending) and their answer replaces the result line when the game thread has run them (within 5 s).
- **Result line** under the input: the line, its source (`bar`, `TruLink`, `menu`) and the answer, green for `ok`, red
  for `err`; long answers (`list`, `help`, `level.list`) in a small scroll box.
- **Autocomplete** while typing: a list above the bar with the matching ids (prefix matches first, then ids that
  contain the text), each with its current value (re-read every 0.5 s) and label. After `<id> ` the list holds the
  known arguments: `0` / `1` for bool items and flag rows, the outfit cycle list for `costume.set`, the player records
  for `costume.choose` / `costume.choosereload` / `costume.setreload`, the 111 units for `level.load`, `Movies\*.bik`
  for `media.video.play` / `media.video.menuloop`, the weapon names for `weapon.give` / `weapon.has`, `0..2` for
  `guard.mode` / `log.level`, the favourites for `fav.del`, all ids for `get` / `fav.add`.
- **Keyboard:** Tab = take the highlighted (or first) suggestion (with a space when the item takes an argument);
  Down / Up = move in the list; Enter = run (the highlighted suggestion if one is highlighted, else the line); Up in
  the **empty** bar = history (Up older, Down newer, Down past the newest = empty line); Down in the empty bar, Up /
  Down with nothing to choose and Esc = focus into the menu; **F2** (always) or **Tab** (while no text field is
  active) = back to the bar. Typed keys do not reach the game (see Controls). 0.7: `[Cmd] UpOpensHistory=0` makes Up
  in the empty bar go into the menu as well (Ctrl + Up = history).
- **History:** the last `[Cmd] HistorySize` (32) lines, a repeated line moves to the end; `TruMenu.history.txt` next to
  `tru.exe` (a `#` comment line, then one line per command, oldest first), rewritten after every line, read at start.
  Lines from TruLink's `cmd.run` go into the history as well.
- **Focus:** when the menu opens the keyboard focus is in the bar (type at once). The pad keeps working as before:
  the first D-pad / stick / B press moves the focus into the menu window (that press is not passed on, the next ones
  navigate); A in the empty bar does the same, A with text runs the line.
- **Pad picker** (View / Back in the menu or in the bar, or the "Pick (View)" button): the list shows every id (or
  the matches of the typed text); D-pad up / down (hold = repeat), left / right = 8 rows; **A**: a toggle runs with
  the other state (`<id> 0|1`), an action runs without argument, an info item shows its value, an item with known
  arguments opens their list (A runs `<id> <value>`, B back to the ids), an int / float item opens the value picker
  (**LB - / RB +**, hold RT = x10, A = set, B = back; steps: `time.scale` 0.1, `camera.fov` 0.05, `player.health` 10,
  developer-menu ints 1 or range / 64 within their range); **Y** pins / unpins the id (favourites); **B** = into the
  menu; View = back to typing.

TruLink:

```text
menu cmd.run time.scale 0.5          runs the line as typed into the bar (bar rules: "menu cmd.run ui.hide" shows the value)
menu cmd.run list costume            answer: ok list: <n> of <total> ids matching costume: ...
menu cmd.focus                       opens the menu (if closed) and puts the keyboard focus into the bar
menu cmd.history                     <n>: newest; ...; oldest
```

`cmd.run` waits for the game thread like any `menu <id>` (3 s); `cmd.run cmd.run ...` is refused.

## Controller and mouse (0.7)

Goal: the command bar is usable on a Steam Machine at the TV **without a keyboard**, and the mouse can click into the
menu / bar at any time.

### L3 = focus into the bar

While the menu is open, **L3 pressed and released alone** (`[Cmd] FocusButton`, default 64 = 0x0040 L3) puts the focus
into the command bar and opens the on-screen keyboard - from anywhere in the menu window, also from the pad picker.
L3 again closes the keyboard (the bar keeps the focus). A press that becomes part of the open / close combo (L3 + R3)
does not count: as soon as another button of `[Menu] ToggleButtons` is down while L3 is held, the tap is cancelled, so
closing the menu never opens the keyboard. With `[Cmd] Keyboard=0` L3 only focuses the text field.

### On-screen keyboard

Drawn inside the bar window **under** the input line and the result line (rounded keys in the menu's button colours,
the key under the cursor with the yellow frame of the suggestion list, a pressed key lights up shortly). It opens when
the bar gets the focus **by controller**: L3, A in the idle bar (bar focused, text field not active), View in the pad
picker ("back to typing"), `menu cmd.keyboard` over TruLink. It does **not** open when the menu opens (the text field
gets the keyboard focus as in 0.6) nor for F2 / Tab.

| Row | Content |
|---|---|
| 0 suggestions | the matching ids / argument values of the line (the same list as the 0.6 autocomplete: `time.` -> `time.scale`, `time.pause`; `level.load ` -> the units); while the line is **empty**: the history, newest first. The highlighted chip (also when the cursor is in another row) is what **Y** takes; its value and label are shown under the keyboard |
| 1 quick tokens | `time.` `player.` `costume.` `level.` `dev.` `menu.` `0` `1` space `.` |
| 2..5 keyboard | number row `1 .. 0 -`, then QWERTZ `q w e r t z u i o p _`, `a s d f g h j k l : #`, `y x c v b n m , . /` (lower case: ids and unit / outfit names are lower case, `#` / `:` for `instance.*` and `id:arg`) |
| 6 | space, backspace (X), clear, close (B), run (Start) |

| Pad | Effect |
|---|---|
| D-pad / left stick | move (hold = repeat); up / down go to the nearest key of the next row, the rows wrap |
| A | type the key / take the suggestion chip under the cursor |
| X | backspace (hold = repeat) |
| Y | take the highlighted suggestion (an id that takes an argument gets a space, so row 0 then lists its values) |
| Start | run the line (as Enter; the result line shows the answer; the line is emptied, the keyboard stays open) |
| B | close the keyboard (the bar keeps the focus; D-pad then goes into the menu as in 0.6); 0.7.1: **a second B** right after it (no other button between) closes the menu |
| LB / RB | jump between the rows suggestions -> tokens -> keyboard (letters) |
| View | pad picker (0.6) |
| L3 | close the keyboard |

- The text field is not active while the keyboard is open; the keys edit the line directly (the field shows it).
- **A real keyboard wins:** a typed character (or Backspace) closes the on-screen keyboard and puts the focus into the
  text field with the line so far (cursor at the end); Esc closes it; a mouse click into the field does the same. While
  the on-screen keyboard is open, typed keys do not reach the game (as for the text field in 0.6).
- 0.7.1: the switch no longer depends on the bar focus, the mouse hover or the selected key (live test 2026-11-02:
  sometimes incomplete with the cursor elsewhere and no key selected yet). Any real key press the window procedure sees
  (not Esc, modifiers, F2, Tab, the toggle key) switches; the typed characters are taken out of ImGui's queue (no
  double insert), and for up to 20 frames the focus is requested again and further characters still go into the line
  until the text field is really active. The open keyboard owns the pad whatever has the focus.
- 0.7.1: the keyboard comes back with the menu when it was open at the last close (owner decision 2026-11-02; in 0.7
  this only happened by chance) - B, B or L3 before closing gives a menu without it.
- Mouse: every key is clickable.
- The bar window grows by the keyboard; it is pushed up to stay on screen (it can then cover the lower part of the menu
  window while the keyboard is open).

### Mouse while the menu is open (`[Menu] FreeMouse=1`)

Owner report (0.6): the game keeps the mouse centred and swaps in its own cursor, so clicking into the bar after a focus
loss failed. Static facts (Steam `tru.exe`, `dumpbin /imports` + `tools/pe_dis.py` / `pe_callers.py`, 2026-11-02):

| Fact | Address | Check at load |
|---|---|---|
| USER32 import address table | 0x0083e278; `SetCursorPos` slot **0x0083e308** (entry 36), `ClipCursor` slot **0x0083e2e0** (entry 26), also `GetCursorPos` 0x0083e2a0, `ShowCursor` 0x0083e30c, `SetCursor` 0x0083e2cc | both slots found by name in the import directory at load and compared with these addresses |
| class window procedure | 0x478bc0 (`WNDCLASS.lpfnWndProc` written at tru+0x790cf), starts with `cmp edi, WM_MOUSEMOVE` | `81ff00020000` at 0x478bda, `c744241cc08b4700` at 0x4790cf |
| mouse look | `WM_MOUSEMOVE` while captured: `ShowCursor(FALSE)` until hidden, `ClipCursor(client rect)` (0x478e75), delta = position - client centre -> 0x4827d0, `SetCursorPos(centre)` (0x478f15); not captured: `ShowCursor(TRUE)`, absolute position -> 0x482670 (the game's own cursor), `ClipCursor(NULL)` | `ff15e0e28300` at 0x478e75, `ff1508e38300` at 0x478f15 |
| activation path | `SetCursorPos(centre)` 0x4791b6, `ClipCursor(rect)` 0x4791c1 | both call bytes |
| other input | no raw input imports; DirectInput8 is created (CoCreateInstance, `EnumDevices` tru+0x865f7, callback 0x486380), `GUID_SysMouse` is not in the file - **not verified live** that no mouse input comes that way. 0.7.1: the callback enumerates devices by type: 0x12 mouse -> wrapper 0x485ae0 at input manager +0x28, 0x13 keyboard -> wrapper 0x485e00 at +0x24 (see "Game input frozen (0.7.1)"); so a DirectInput **mouse** device exists as well - not hooked (the 0.7 live test showed no camera turn while the menu was open) | - |

While the menu is open TruMenu therefore:

1. passes **mouse messages** (`WM_MOUSEMOVE` .. `WM_MOUSEHWHEEL`, `WM_MOUSELEAVE`) and `WM_SETCURSOR` (client area)
   **to ImGui only** - the game's window procedure never sees them: no camera turn, no re-centring, no `ShowCursor`;
2. lets ImGui draw its own cursor (`io.MouseDrawCursor`, the system cursor is hidden with `SetCursor(NULL)`);
3. points the two **import slots** `SetCursorPos` / `ClipCursor` to holders that only remember the game's request (only
   while the menu is open; the slots are written back on close, only if they still hold ours) and releases the clip
   (`ClipCursor(NULL)` through TruMenu's own import);
4. on close (game window in front): the game's last `ClipCursor` / `SetCursorPos` request, or else the clip and the cursor
   position from before the menu, are applied once - so the game's next mouse delta starts at its centre (no camera jump).

Mouse positions are scaled from client to back-buffer pixels (ImGui draws in back-buffer pixels; with a scaling window
proxy they differ - in 0.6 the mouse was off then). Status page / `status.hooks`: line `mouse (0.7): ...`; `TruMenu.log`
"0.7 mouse: SetCursorPos slot ...". `[Menu] FreeMouse=0` = 0.6 behaviour (the game gets the mouse as well).

### The two open owner questions (0.6 log page) as options

| Key | Default (= 0.6 behaviour) | Other value |
|---|---|---|
| `[Cmd] UpOpensHistory` | 1: Up in the empty bar opens the history (Up older, Down newer) | 0: Up goes into the menu like Down; **Ctrl + Up** still opens the history |
| `[Cmd] FirstPadPressOnlyFocuses` | 1: the first D-pad / stick press in the bar only moves the focus into the menu (not passed on) | 0: the same press also moves in the menu at once (the held direction is handed to ImGui in the next frame) |

## Game input frozen (0.7.1)

Live test 2026-11-02 (0.7): typing into the command bar moved Lara, Esc in the menu opened the game's pause menu, B
with the on-screen keyboard open closed the whole menu, and the real-keyboard switch was sometimes incomplete.

### Keyboard while the menu is open (`[Menu] BlockGameInput=1`)

How `tru.exe` reads the keyboard (Steam exe, `tools/pe_dis.py`, `pe_callers.py`, `pe_abs_uses.py`, `exe_xref.py`,
`dumpbin /imports`, 2026-11-02):

| Fact | Address |
|---|---|
| no `GetAsyncKeyState` / `GetKeyState` / `GetKeyboardState` / raw input imports; DirectInput8 through `CoCreateInstance` | import table |
| `EnumDevices` callback 0x486380 sorts by `dwDevType & 0xff`: 0x12 mouse -> new 0x890 bytes, wrapper 0x485ae0, stored at input manager `[0xa02b9c]+0x28`; **0x13 keyboard** -> new 0x894 bytes, wrapper **0x485e00**, stored at `[0xa02b9c]+0x24`; 0x14 / 0x15 joystick / gamepad (XInput devices skipped) | 0x486393, 0x4863f3, 0x48641f, 0x48642a |
| keyboard wrapper 0x485e00: vtable **0x844f5c**, `IDirectInputDevice8` at +4; `CreateDevice`, `SetDataFormat(0x8654dc)`, `SetProperty(DIPROP_BUFFERSIZE, 64)`, `SetCooperativeLevel([0x9eedec], DISCL_NONEXCLUSIVE \| DISCL_FOREGROUND)`, `EnumObjects(0x482420)` | 0x485e3f (`mov [esi], 0x844f5c`) |
| vtable slot 2 (**0x844f64** = 0x486100) = `Read(events, room, full)` (thiscall, `ret 0xc`): not full and no resync flag (+0x890) -> buffered `GetDeviceData` 0x486020; else buffered + full `GetDeviceState` 0x485f10 (also after `DIERR_INPUTLOST` / `NOTACQUIRED` -> `Acquire`) | 0x486100, 0x486020, 0x485f10 |
| events: 16 bytes `{1, DIK code, time stamp, value 1.0 / 0.0}` (buffered: `dwOfs`, `dwTimeStamp`, `dwData & 0x80`; full: index, `GetTickCount` via slot 3, state byte & 0x80) | 0x48609d, 0x485fb1 |
| the input manager's read 0x483db0 (its vtable 0x844c54 slot 2) calls pad (+0x2c), mouse (+0x28), keyboard (+0x24) each through `call [vtable+8]` with `(events, room, full)`; keyboard ids + 0x80; byte +0x1a of the manager zeroes keyboard values (the game's own switch 0x4825b0, used by its UI 0x5ac98c / 0x780060 - not touched by TruMenu) | 0x483eea |
| window procedure 0x478bc0: `WM_KEYDOWN` not handled; `WM_KEYUP` + `VK_ESCAPE` -> 0x477ae0 (puts 0x1b into the character queue 0x9eeb40, count 0x9eedf8); `WM_CHAR` -> the same queue (128 entries); `WM_SYSKEYDOWN` only filters Alt combinations (not Alt + F4) | 0x478c0e, 0x478c27, 0x478caa, 0x478d7d |

What 0.7.1 does:

1. At load, after the byte checks below, slot 2 of the keyboard wrapper vtable (0x844f64, `.rdata`) points to
   `KbdReadHook` (only the keyboard wrapper uses this vtable: constructor 0x485e3f, destructor 0x486160). The hook calls
   the game's own read first (the device buffer is emptied as usual, nothing piles up), tracks which keys are down, and:
   - menu open: returns **no** events, except once a release event (value 0) for every key the game saw going down -
     the neutral state (Lara stops if a movement key was held when the menu opened);
   - menu closed: passes the events on, but a key that was held when the menu closed stays away from the game until its
     release (the release is dropped too - the game never saw it go down), so no key "arrives" pressed after the close.
2. While the menu is open `WM_KEYDOWN` / `WM_KEYUP` / `WM_CHAR` / `WM_DEADCHAR` / `WM_SYSCHAR` / `WM_SYSDEADCHAR` go
   to ImGui only (the Esc key-up no longer reaches the game's character queue); the key-up of a key that went down
   while the menu was open is kept away after the close as well. `WM_SYSKEYDOWN` / `WM_SYSKEYUP` pass (Alt + Tab,
   Alt + F4).
3. Pad (neutral, `[Pad] BlockInput`) and mouse (`[Menu] FreeMouse`) as in 0.7. The DirectInput mouse device is not
   touched.

A check that fails switches the DirectInput part off with a log line ("0.7.1 keyboard: code 0, slot ... -> code / slot
NOT matched - DirectInput keyboard not held, only the key messages"); the message part still works. Status page /
`status.hooks`: `keyboard (0.7.1): ...` with the counters (events held, releases sent, kept after close).

Byte pre-checks (all `ok` against the Steam `tru.exe` 2026-11-02 with `tools/pe_bytes_check.py --file
work\asi\menu071\precheck_071.txt`, 36 checks, 0 mismatches):

| Address | Bytes | Meaning |
|---|---|---|
| 0x844f64 | `00614800` | vtable slot 2 = 0x486100 (dword read, then replaced) |
| 0x486100 | `56 8bf1 837e0400 7506 33c0 5e c20c00 807c241000 751e 80be9008000000` | Read(events, room, full) |
| 0x485e3f | `c7065c4f8400` | constructor writes the vtable |
| 0x4863f3 | `83f813 754a` | enum callback: type 0x13 keyboard |
| 0x48641f | `e8dcf9ffff 8b0d9c2ba000 894124` | builds the wrapper, stores it at +0x24 |
| 0x483eea | `8b4f24 8b01 8b4008 52 55 56 ffd0` | input manager calls slot 2 of the keyboard |
| 0x48609d | `8970f4 8b79fc 8978f8 f60180` | buffered event layout |
| 0x485fb1 | `f6440c1480 8970f4 8948f8` | full-state event layout |
| 0x478c0e / 0x478c27 / 0x478caa | `2df1000000 0f850a030000 83bc24800000001b` / `6a1b e8b2eeffff` / `0fb7942484000000` | window procedure Esc key-up / WM_CHAR (documentation; not needed for the hook) |

### `[Menu] PauseGame` (default 0)

1 = the `time.pause` bit (streamFlags 0xe7f0b8 bit 0x1000, checked as for `time.pause`) is set while the menu is open
(Present, as the menu state changes). On close only what TruMenu set is cleared: a pause from before the menu stays,
and `time.pause` used while the menu is open takes over (no restore). Status `status.hooks` `pause=...`.

### B twice, keyboard reopen

B with the on-screen keyboard open closes only the keyboard; a **second B** right after it (no other pad button between)
closes the menu (`TruMenu.log`: "menu closed (B twice: keyboard, then menu)"). B in the idle bar otherwise still moves
the focus into the menu (0.6). Why 0.7 closed the menu on the first B could **not** be found statically: the 0.7 code
only closes the keyboard on B, and the live `TruMenu.log` of 2026-11-02 has only "menu closed (pad)" (L3 + R3) and
"(level change)" lines. 0.7.1 therefore logs every open / close with its reason at `LogLevel` 1 - if a first B still
closes the menu, the log line says by what. The open keyboard now owns the pad independent of the bar focus.

### `level.start` and `[Test] AutoStart` (the mission menu's DLC start, intro plays)

`level.load` (GAMELOOP_RequestLevelChangeByName) skips the DLC intro. The mission menu (PC generalbank script 104)
starts a DLC with `uigamedata` f22, `uigamedata` f27(unit, 1, 0, 1), `stdscreenmgr` f19 + f7
(`docs/Befund-Direktstart.md`; test 41e did the same from the attract timer script and the DLC 2 intro played). The
natives, read statically:

| Native | Registration | Code | Note |
|---|---|---|---|
| `uigamedata` f22 | binder 0x7af0c0, 0x7af201 `push 0x7a0d00; push 0x16` | 0x7a0d00 jmp 0x77bc90 jmp **0x4a0f10** | `byte [0xa039b8] = 1; ret` - no arguments |
| `uigamedata` f27 | 0x7af247 `push 0x7a0d40; push 0x1b` | 0x7a0d40: the three bools of the argument block, then jmp **0x77e170** | cdecl `(DataValue *args, bool, bool, bool)`, `args[0]` = `char *unit` (copied by 0x5dfb20 into GameTracker+0x38), plain `ret` (0x77e442) |
| `stdscreenmgr` f7 | binder 0x7adca0, 0x7add0f `push 0x79ea00; push 7` | 0x79ea00 jmp **0x4be580** | ignores the script instance: `[0xa13f58]` (vtable 0x847c7c) slot 4 |
| `stdscreenmgr` f19 | 0x7addb7 `push 0x79eac0; push 0x13` | 0x79eac0 jmp **0x4be5e0** | `[0xa13f50]` (vtable 0x847cc4) slot 4 |
| slot 4 of both | 0x847c8c / 0x847cd4 = 0x4c5260 | `push ecx; mov eax, [ecx+4]; ...; call 0x7a5160; pop ecx; ret` | thiscall, no arguments |

So the sequence needs no script frame: `level.start [dlc2|dlc1|<unit>]` (game thread, main state 10 only, experimental)
calls 0x4a0f10(), 0x77e170({unit, 1, 0, 1}, 1, 0, 1) (0.7.2: the 2nd value follows `[Levels] OutfitRule`, section
"Mission start, outfit rule, game.quit (0.7.2)"), 0x4be5e0(), 0x4be580() inside `__try`, after checking that no
level change is pending and that both screen managers exist with the expected vtables (singletons created at 0x4ccd3d /
0x4ccd96). Not reproduced from script 104 (as in test 41e): the `dlcsystem` existence check, the "game in progress"
dialog, the `messagechannel` "enableSound" broadcast. Level select page: two buttons "Start DLC 2 / DLC 1 as the
mission menu (intro)".

`[Test] AutoStart=dlc2` (or `dlc1` or a unit name; default empty = off): once per game start, when the main menu
(main state 10) has been up for `[Test] AutoStartDelay` seconds (default 3), TruMenu queues `level.start <unit>` -
the TruMenu replacement for the generalbank test patch 41e, which must never ship. Without the verified path (a check
failed) it queues `level.load` instead and logs "AutoStart: intro skipped (mission start path not available)". Needs
`[Cheat] Experimental=1`. Byte checks (all `ok`, same precheck file): 0x7af201, 0x7af247, 0x7a0d00, 0x77bc90,
0x4a0f10, 0x7a0d40, 0x7a0d69 (`e902d4fdff`), 0x77e170, 0x77e425 (name -> 0x5dfb20, `ret`), 0x7add0f, 0x7addb7,
0x79ea00, 0x79eac0, 0x4be580, 0x4be5e0, 0x847c8c, 0x847cd4, 0x4c5260, 0x4ccd3d, 0x4ccd96; at the call additionally
the two singleton pointers and their vtables.

### `[Log] UnitChanges` (default 1): the stream unit Lara is in

`GameTracker+0x38` (`status.unit`, `level.current`) is only the unit the level load started with. The stream unit Lara
is in: the game loop (0x5dfc88) compares `GameTracker+0xc0` (0xe7f148) with the player instance's +0xe0 and on a
difference calls `STREAM_MoveIntoNewStreamUnit` 0x5c1bf0, which stores the new id into 0xe7f148 (0x5c1c4e) and prints
the name at **entry +0xc** of the stream unit table (0xdbab40, 0xd8 per entry, +0 id, +4 state byte 2 = loaded; lookup
0x5c1b50; format "STREAM_MoveIntoNewStreamUnit(%s)" at 0x5c1c33); the name lookup 0x5c1b90 compares entry +0xc too.
TruMenu's worker thread reads id + name every 250 ms (read-only) and logs a line only on a change:
`unit: dlc2_goo_room (was dlc_level2_start; stream unit id 7)` - into `TruMenu.log`, so also onto the log page and the
log overlay (`log.overlay`). `status.unit` shows the stream unit name too. Checks: 0x5c1bf0, 0x5c1c28, 0x5c1c4e,
0x5c1b9c, 0x5dfc88 and the 0.2 unit table check; a mismatch switches the option off with a log line.

## Mission start, outfit rule, game.quit (0.7.2)

Live test 2026-11-02 (`TruMenu.log`): 20:28:40 `level.start dlc2` from the open main menu -> outfit selection; 20:29:17
`level.load dlc_level2_start` during that screen was accepted ("level change ... requested") -> black screen, game hung,
TruMenu still drawn; 20:32:03 a further `level.load` said "a level change is already pending (GameTracker+0xb9)".

### What a mission start does after f27 (static, `tools/pe_dis.py`, `tools/pe_callers.py`)

| Step | Code | Fact |
|---|---|---|
| game loop | 0x5e01ab `push 0xe7f088; push 0xe7ed60; call 0x5e0090` | the main-state dispatcher gets `&mainState` (0xe7ed60) and the GameTracker; jump table 0x5e015c on `state - 1` (states 1 .. 10; 1 = in a level, 10 = main menu) |
| f27 = 0x77e170 | 0x77e17c `cmp byte [ebp+0xc], 0` ... 0x77e193 `mov [0xfae8d9], dl` | its **2nd argument** is stored as the selection byte 0xfae8d9 ("costume / weapon selection", TU `MainTracker_UILoadLevel`) |
| 0x5dfb20 (end of f27) | 0x5dfb5c `cmp [0xe7ed60], 1`, 0x5dfb83 `mov [0xe7ed60], 2` | unit name -> GameTracker+0x38; in a level `GAMELOOP_RequestLevelChangeByName`, otherwise **main state = 2** - GameTracker+0xb9 is not set |
| state 2 | 0x5e0160 -> 0x5e00cd -> 0x5de7e0; 0x5de877 `cmp [0xfae8d9], 0`, 0x5de884 `mov [state], 9` | selection byte set -> **main state 9 = outfit / weapon selection** (0x5e017c -> 0x5e012e); else the level load (0x5de2b0) |
| selection done | 0x77e450 `mov byte [0xfae8d9], 0; jmp 0x5de9c0` | the byte is cleared, the load goes on |

So during the outfit selection GameTracker+0xb9 is 0 (0.7.1 only tested that), and a `level.load` there sets a request
the state-9 screen never serves -> hang. **0.7.2:** `level.load`, `level.reload` and `level.start` are refused with
`refused: level change pending (<reason>)` (in `TruMenu.log` as `item level.load: err refused: ...`) while
GameTracker+0xb9 is set **or** the main state is 2 (start being set up) or 9 (outfit / weapon selection). `status.state`
and the Level page show the reason. Byte checks (`work\asi\menu072\precheck_072.txt`, all ok on the Steam exe):
0x5e01ab, 0x5e0096, 0x5e0160, 0x5e017c, 0x5e00cd, 0x5de877, 0x5dfb5c, 0x5dfb83; a mismatch keeps the 0.7.1 test
(GameTracker+0xb9 only) with a log line.

### Outfit rule (`[Levels] OutfitRule`, default 1) - translated from the title update

TU generalbank **script 134 function 9** (`tools/menu_dlc_probe.py dis xt 134`, +0x257c .. +0x2608; copy in
`work\asi\menu072\notes\xt134.dis`): `if unit == dlc_level4_start || dlc_level5_start || dlc_level6_start ||
dlc_level2_start: uigamedata f26(unit, 0, 0, 1) else f26(unit, 1, 0, 1)`. The PC script 104 function 9 (`dis pp 104`,
+0x23c0 .. +0x2438) tests only levels 4 / 5 / 6, so on PC DLC 2 gets `f27(unit, 1, 0, 1)` = the selection. (The TU exe's
in-game yes / no path has the same rule, string "Attempting to load DLC2 starting unit without costume/weapon select";
`docs/Befund-Felsrinne.md` step a.) The installed test generalbank 47 (md5 3a2b9a1d...) already carries the TU test in
script 104 and a `(0, 0, 1)` direct-start stub - that is why the old direct start showed no outfit screen.
`level.start` now passes **0** for `dlc_level2_start` (and 4 .. 6) and **1** for every other unit (DLC 1 keeps its
selection, as on the Xbox: `Xenia-TU_DLC1_13`). Without the selection the level load takes the unit default costume
(`lara_doppelganger`, which TruDlc2Player maps to `doppelganger_casual`). `OutfitRule=0` = the PC rule (always 1).
Checks: the mission path, the pending checks, 0x77e17c, 0x77e186, 0x77e193, 0x77e450; a mismatch keeps 1 with a log
line. Still open: the live Xbox observation (Xenia checklist 12c).

### `game.quit` (owner wish 2026-11-02)

Status page, last button "Quit game (press twice)", and the item `game.quit` (command bar, favourites, TO TEST "Run").
**Safety step:** the first run arms it (button turns red: "CONFIRM: quit the game now (n s)"), a second run 0.3 .. 5 s
later quits. **0.8.1:** the countdown label broke the second press with pad / keyboard (see "Live-test fixes (0.8.1)");
now a fixed "Quit game (press twice, or hold 1 s)" button, while armed a separate red **"Quit now"** button (the focus
moves to it once the arming press is released) with "armed - n s left" beside it, a **10 s** window, and holding A /
Enter / Space / the mouse **1 s** on either button quits as well (progress bar "hold 1 s to quit"). Then: `TruMenu.log` line `game.quit by the owner (TruMenu) - logs flushed next, then TerminateProcess(...)`,
the TO TEST list and the command history are written once more, the CRT streams flushed and `TruMenu.log` committed
(`FlushFileBuffers`), then `TerminateProcess(GetCurrentProcess(), 0x544D)` - runs on the render / bar thread, so it
works while the game thread hangs (as long as the menu is still drawn); `TerminateProcess` instead of `ExitProcess` so
no DLL detach can block. **Never automatic:** over TruLink (`menu game.quit`, `cmd.run game.quit`) it answers `err` and
logs "game.quit refused"; TO TEST toggles refuse it; nothing in TruMenu queues it. `Invoke-TruTestRun.ps1` shows exit
code 21581 (0x544D) as "ended via TruMenu game.quit (exit code 0x544D, not a crash)" in the status and the verdict
notes; owner checks still count.

### Log overlay filter (`[Log] OverlaySources`, `[Log] OverlayExclude`)

In the 0.7.1 live test TruShadowPower's "activity 1009 (player +0xc8 = record +4) ... value 0" lines (several per
second) flooded the overlay. The corner overlay now shows only the sources of `[Log] OverlaySources` (default
`TruMenu,TruGuard`; comma list of log names - the file name without `.log`, plus `script`; `*` or empty = all) and
drops lines holding one of the texts of `[Log] OverlayExclude` (comma list of substrings, default empty). Only the
overlay: the Debug / Log page and the log files stay complete. At run time: `log.overlaysources TruMenu,TruShadowPower`,
`log.overlayexclude activity 1009` (`none` = off; no argument = show the value). The overlay says "(log: no lines - n
kept out by ...)" when the filter hid everything.

## Regression, Cheats, camera log (0.8)

Spec: `docs\Plan-TruMenu-Medien.md` (workspace) P0, P0c, P0b. Byte pre-checks of every new engine address:
`work\asi\menu080\precheck_080.txt` (30 checks, `tools/pe_bytes_check.py --file`, all ok on the Steam `tru.exe`
2026-11-02); at load TruMenu checks the same bytes, a mismatch disables that row with a log line
(`0.8 cheats: cheat.x disabled - <reason>`) and a grey row with the reason in red.

### Regression page (P0)

- **Lists** `tests\regress\dlc1.txt` (DLC 1: 6 steps + 12 checks, from `docs/Regression-DLC1.md`) and
  `tests\regress\dlc2.txt` (DLC 2: 7 steps + 23 checks, from `docs/Regression-DLC2.md`), the row format of
  `TruMenu.tests.txt` (`id<TAB>state<TAB>hint<TAB>note<TAB>time<TAB>kind<TAB>target<TAB>number`; check ids = the ids in
  the docs, steps `step<n>`; step 5 of DLC 2 runs `time.scale 0.5`). ASCII only, no game data.
  `tools/trumenu_ini_check.py` checks them too (8 columns, unique ids, every check id named in its doc).
  `Set-TruMenu.ps1 -Install` copies them next to the `.asi` as `TruMenu.regress_dlc1.txt` / `TruMenu.regress_dlc2.txt`
  (from the build folder if it holds them, else from `tests\regress`; a list is ours when its first line starts with
  `# TruMenu regression list`; `-Remove` deletes only ours).
- **Page**: loaded at the menu start without harness / TruLink; every row starts **open** at each game start (the list
  files are never written). Selector DLC 1 / DLC 2 / all (`[Regress] List`, default `all`); checks A ok / X fail /
  Y skip (as TO TEST; X / Y go to the focused row), **Note** = command bar `regress.note dlc2:<id> <text>` + on-screen
  keyboard; steps A = run + done.
- **Results** `TruMenu.regress_results.txt` next to the `.asi`, appended, CRLF, tab separated:
  `#session<TAB><session start><TAB><versions><TAB><sha256>` once per game start before its first row (versions = each
  loaded plugin's `<Name>Version()` up to " (", e.g. `TruMenu=TruMenu 0.8.0; TruShadowPower=...; TruDataGuard=no`;
  sha256 = the loaded `Tru*.asi` files, computed once by the worker thread), then one line per mark / note
  `yyyy-mm-dd hh:mm:ss<TAB>dlc2<TAB>hint-vein<TAB>fail<TAB><note><TAB><session start>`.
- **TruLink**: `menu regress.load dlc2` (re-read, rows open, page selection), `menu regress.export` (block as
  `test.export`: `ok+ regress.export ...`, then `list kind id state number target hint note time` per row, then `.`),
  `menu regress.mark dlc2:wall-run ok`, `menu regress.list`.
- **Harness (not built in 0.8)** - what `scripts\windows\Invoke-TruTestRun.ps1` needs: (1) a profile key
  `"regression": "dlc1" | "dlc2" | "all"`; after the TO TEST preload send `menu regress.load <value>`; (2) after the run
  copy `TruMenu.regress_results.txt` from the game folder into the run folder (`$run.collected`) and, optionally, the
  answer of `menu regress.export` while the game still runs; (3) a reader `Read-RegressResults` that keeps the lines of
  the **last** `#session` block (the run's game start), the newest state per `list + id`; (4) `summary.md` section
  "Regression rows" (list, id, state, note, time) and `summary.json.regression`; (5) the verdict counts them like owner
  checks (fail -> FAIL, open / skip -> INCOMPLETE); (6) `-Compare` lists changed regression states.

### Cheats page (P0c)

Source `docs\Befund-Prototyp-2007.md` 3i (workspace); every address re-read with `tools/pe_dis.py`,
`tools/pe_abs_uses.py`, `tools/pe_callers.py`. All rows run on the game thread (queued), only in a level, need
`[Cheats] Enabled=1` and `[Cheat] Experimental=1`, and log on / off (`cheat: god mode ON (...)`). `[Cheats] Persist=0`
(default): the bytes are `.bss` / weapon data, so after a game start everything is off; `Persist=1` writes the ids that
are on into `[Cheats] State` and switches them on again in the first level of the next start.

| Item | Category | What it does (PC) | Notes |
|---|---|---|---|
| `cheat.god` | PC has it (switchable) | byte `0xfadf60` (`gInvincibleCheat`, cheat code 2 toggles it at 0x5d355a) = 1; `ProcessHealth` 0x6f5160 then keeps the hit-invulnerability timer `P+0x638` = 30.0 and `P+0x63c` = 5 every frame | as the prototype: damage types 8 / 5, `0x6e7930(type)` types and instant deaths still pass |
| `cheat.godfull` | PC has it (switchable) | `cheat.god` + `GameTracker.cheatMode` 0xe7f144 bit 0 (`PlayerTakeDamage` 0x6f5030 returns at once, 0x6f5031) | the bit is also `cheat.flight`'s switch and has **60 uses** in `tru.exe` (`pe_abs_uses.py`) - side effects likely; off clears only a bit TruMenu set (and not while `cheat.flight` is on) |
| `cheat.onehitkill` | PC has it (switchable) | byte `0xe91ffd` through **`ENEMY_ToggleOneHitKill` 0x60f670** (the game's own toggle, cheat code 1 jumps there), called only when the state differs | readers 0x62e39f, 0x633eb3, 0x63bb68 |
| `cheat.enemyhealth` | PC has it (switchable) | byte `0xe91ffc` = 1; reader 0x638ed4 in `EnemyProcessFunc` 0x638d40 prints `[enemy+0x2c64]` through 0x622600 (format 0x858608) | whether retail draws that debug text = live test |
| `cheat.ammo` | logic present, entry cut (re-attach) | per weapon in the 15 slots (`WM+4/+0xc+0x10*slot`, handle check as 0x5b39d0): `T = INSTANCE_Query(inst, 0x36)` (0x5b36f0 -> `inst+0x11c`), `T+0x88 |= 0x80` -> the reloads 0x69c600 / 0x6e7ae0 refill the clip without the reserve; `ResetAmmo` 0x6f58d1 passes the same slot instances to 0x6e7ae0 (proof of the path) | T is the weapon object's shared data; weapons with ammo type 0xff are skipped; new weapons are picked up every 30 game frames; off clears only bits TruMenu set and only on weapon data a slot still returns |
| `cheat.fillup` | logic present, entry cut (re-attach) | `GainHealth` 0x6f4ef0 **cdecl `(float amount, bool noClamp)`** (`fld [esp+4]`, `cmp byte [esp+8], 0`, plain `ret`; ecx unused) with `(MaxHealth 0x6e7990(), 0)` -> health = max, HUD trigger 0x77d9d0 inside; then `ammo.fill` (prototype `DEBUG_FillUpAll` = health + ammo) | |
| `cheat.code <n>` | cheat-code path | `DEBUG_ApplyCheatCode` 0x5d3520 cdecl `(code)`: first `0x6a5dd0(player, 0x71, 0xff, 0, &player.pos)` (hit-reaction effect; `[0xe7f094]` used **without** a null check), then jump table 0x5d358c / index 0x5d35a8: 1 -> 0x60f670, 2 -> toggle 0xfadf60, 9 -> xor 0xe7edb0, 10 -> xor 0xe7edac, 11 -> toggle 0xe91ffc; 3..8, 65, 66 = `ret` | built: the game itself calls it every frame from `GAMELOOP_Process` (0x5dfc5f, unless gameMode `[0xe7f143]` is 6 / 10); TruMenu calls it on the game thread with the same guard + a player; 9 / 10 have no readers on PC (nothing visible expected) |
| no fall damage, enemies ignore Lara, no AI, infinite grenades, enemies don't attack / no attack damage / no health / don't move / don't investigate / no barks | flag + reader gone (rebuild from prototype) | listed read-only, "not built yet" (`cheat.list`) | the prototype function per row is on the page |

### Camera log (P0b, `[Log] CameraChanges`, default 1)

Read-only poll on the render thread every 200 ms: the camera manager 0xe804f0 is processed by 0x5f3c70 (called at
0x5f3e0c with `ecx = 0xe804f0`; vtable 0x855ae4 slot 10), which calls the **mode chooser 0x5e7fe0 with `this` = the
manager**: it writes the requested mode to **manager+0x58** (0x5e80b9 `mov [esi+0x58], 0x34` = adrenaline mode,
others seen there 1 / 0x13 / 0x30 / 0x33 / 0x36) and at 0x5e80da compares it with the applied mode +0x54 (on a
difference: current camera `vtbl[0x60](mode)`, +0x54 = +0x58, time in mode +0x5c = 0). Lines in `TruMenu.log` (log
page / overlay, source TruMenu): `camera: mode 1 -> 52 (0x1 -> 0x34; requested manager+0x58, applied +0x54 = 1)` and,
for the current camera object (manager+0x44 = 0xe80534), `camera: object 0x00e80610 (manager+0x120, vtable 0x...) ->
0x... (manager+0x5b90, vtable 0x...)` (the manager's camera objects +0x120 / +0x670 / +0x5b90 / pointer +0xb80 are named).
**No target instance / object name**: no field of the PC camera struct is proven to hold one (the 2007
`CAMERA_SetInstanceFocus` offsets do not transfer). `camera.log [0/1]` switches it for the session, its value shows
the current fields and the change counters. Checks: 0x5f3e0c, 0x5f3d12, 0x5e7feb, 0x5e8041, 0x5e80b9, 0x5e80da,
0x5e810b, 0x5f3cb0.

## Live-test fixes (0.8.1)

Spec: `docs\Plan-TruMenu-Medien.md` (workspace) P00c; evidence: `TruMenu.log` of the runs `20261102_221539`,
`_223338`, `_224047` (`regress_shadowlara_50k`). No new engine address (`work\asi\menu081\precheck_081.txt` only
re-reads the reload bytes behind the cheat.ammo finding, 2 checks ok).

- **game.quit, second press lost** - cause: the armed label `CONFIRM: quit the game now (%lu s) ...##quit` changed
  every second. In ImGui `##` only hides the rest of a label; the **id is the hash of the whole label**, so the button
  got a new id each second. The pad / keyboard focus (`NavId`) then named a widget that no longer existed, and A /
  Enter activated nothing; after 5 s the label was `Quit game (press twice)##quit` again - the first id, the focus
  was alive again and that press **re-armed** (22:24:06 / :12 / :17 / :24, 5.2-7.3 s apart; with the command bar the
  same item worked, 22:47:57 / 22:48:01). A mouse click only failed when a second boundary fell between press and
  release. Not involved: `FirstPadPressOnlyFocuses` (command bar only), pad ownership (the bar did not have the
  focus). Fix: fixed labels with `###` ids, a separate red "Quit now" button while armed, 10 s, hold 1 s (section
  `game.quit` above). The same bug class was fixed on every label that changes with its state: `ConfirmButton` ("press
  A again to confirm" - Reload lists, settings / favourites reset), item buttons with their value, TO TEST /
  Regression rows ([OK] / [FAIL] / [DONE] / NEXT), the list selectors, live outfit / costume / instance buttons,
  the flight button.
- **Input trace** (`[Log] InputTrace=1`, lines at LogLevel 2; `log.inputtrace`): while the menu is open every pad
  button edge (A B X Y LB RB L3 R3 Start View D-pad, down / up; source "XInput hook" = the game's poll through PadHook,
  "Present fallback" = TruMenu's own read), every mouse button and every key message (no auto-repeat) is queued and
  written one frame later as `input: pad0 A down (XInput hook) -> activated 'Quit now  [game.quit]' (0x...)` or
  `-> not activated: <reason> (focus '<label>' 0x... in <window>)`. Reasons: no widget has the nav focus / the focused
  widget was not drawn (id changed - the game.quit case) / disabled / pressed and released between two frames / not
  the menu's pad / command bar or on-screen keyboard owns the pad (with what the bar did, e.g. "swallowed by
  FirstPadPressOnlyFocuses") / X = fail, Y = skip on a row / menu combo. D-pad and arrow keys: `focus 'a' -> 'b'`.
  Labels come from wrappers around Button / SmallButton / Checkbox / Selectable / CollapsingHeader (`TraceItem`);
  other widgets show their id. At every close (also with InputTrace=0, LogLevel 1): `input while the menu was open:
  n pad presses (A n: n activated, n not), n mouse clicks, n keys`.
- **Stuck Enter in the command bar** (found in run 224047, 22:47:45-53: 70 runs of an empty line every 100 ms, plus
  single letters "u", "i", "." while the owner typed): key messages reach ImGui only while the menu is open; the
  Enter of `level.load ...` in the bar closed the menu before Enter went up, so ImGui kept Enter down and repeated it
  at the next open. Fix: ImGui's keys are released (`io.ClearInputKeys`) at every open / close, and the bar runs a line
  only on a fresh Enter (a repeat keeps the text and the focus).
- **cheat.flight on and off within 16 ms** (22:19:54.690 / .706 after ONE "queued"): `RunPending` tested the request
  flag outside its lock and not again inside, so a second caller that passed the test while the first one ran waited
  for the lock and ran the same request again - with the button's "" (= flip) the flag flipped back. Which second
  caller it was (another thread through PadHook, the Present fallback, or a re-entry through the pad poll - the lock
  is recursive) is not visible in the 0.8.0 log. Fix: the request is claimed with one interlocked exchange (1 queued
  -> 2 running), so it runs exactly once whatever calls it; the flight button sends the target state (1 / 0); the
  "pad slot not polled" test is signed (a newer tick stored between two reads looked like 49 days).
- **cheat.ammo "2 weapon(s), 0 bit(s) set"** (run 223338, hall02): not a failed write. The reload 0x69c600 queries
  0x36 and skips the reserve when **T+0xa == 0xff or T+0x88 & 0x80** (bytes re-read: 0x69c61b..0x69c635). The two
  slot weapons were most likely the pistol pair (left / right hand), whose ammo type is 0xff (unlimited already) - so
  nothing had to be set. 0.8.1 names every slot weapon in the answer and the log: `slot 0 wp_pistol: T 0x... type -1
  flags 0x.. -> ammo type 0xff = unlimited already` / `-> bit set` / `-> bit 0x80 set already` / `query 0x36 = 0 - no
  weapon data`. Live: give a weapon with ammo (`weapon.give wp_shotgun`) and switch it on again.
- **player.unstuck** (Lara slid into the eitr in hall02 with god mode): a ring of 16 "safe ground" spots - every
  ~0.5 s (game thread, 15 game frames) with the menu closed, flight off, health > 0 and Lara's height changed less than
  5 units over ~1 s, a spot at least 100 units from the newest one is kept (no proven on-ground flag yet - read from the
  position). `player.unstuck` takes the newer of `player.mark` (same unit) and the newest spot that is >= 3 s old and
  >= 150 units away from Lara; again within 20 s = one spot further back; `player.unstuck mark|safe` forces the source.
  Button "Unstuck" on the Time / player / HUD page.
- **Regression shortcuts**: optional 9th column `shortcut` in `tests\regress\*.txt` = `#title;cmd;cmd ...` (title
  optional, at most 12 commands). Button **Prepare** on the row and a **Quick prepare** list at the top of the
  Regression page (one button per distinct shortcut, tooltip = the commands, a status line and Stop while one runs);
  `regress.prepare <list:id>|stop`, `regress.shortcuts`. The commands run one after the other through the command bar
  path (source "shortcut", history + TruMenu.log line each) from the render thread: the next one when the game-thread
  slot is free; after `level.*` it waits until no level change is pending, a player exists and (level.load) the unit
  is the requested one for 2 s (timeout 120 s); an `err` answer stops it; `game.quit` is refused. Shipped shortcuts:
  DLC 1 step3 (`level.load dlc_level1_start`), step5 (`cheat.god 0`), dlc1-treasure (`level.load dlc_treasureroom`);
  DLC 2 step4 (`level.load dlc_level2_start`, rock channel ahead), health (`cheat.god 0`), step5 (`cheat.god 0;
  time.scale 0.5`), new **step7 thrall fight** (`level.load dlc_yggdrasil_hall02;cheat.god 1`; the old step7 "Mark
  the checks" is now step8). `tools/trumenu_ini_check.py` checks the column (known item ids, no game.quit, level.load
  unit name, bool args 0 / 1).

## Saves page and music (0.9)

Spec: `docs\Plan-TruMenu-Medien.md` (workspace) P0d, P1-P3; facts with addresses and tools: workspace
`docs\Menue-Funktionen-Katalog.md` sections 11.3 (music) and 11.4 (saves). Byte checks:
`work\asi\menu09\precheck_09.txt` (19 checks, 0 mismatches). Nothing of this was run in the game yet.

### Saves page (P0d)

- **Folder** as `tru.exe` builds it (0x78B550): Documents (`CSIDL_PERSONAL`) + `\Eidos\Tomb Raider - Underworld\`,
  files `<name>.TRUSave` (the game's own names, e.g. `Autosave.TRUSave`); `[Saves] Folder` overrides it. Backups,
  export and import live in **`TruMenu.saves\`** next to tru.exe (never touched by `Set-TruMenu.ps1`).
- **Format** (all proven, `tools/trusave_info.py`): `RGMH` rich saved game header (0x2028) + `PCUD` container (entry
  table, three CRC-32/BZIP2 checks as the reader 0x6DBBA7 / 0x6DBC8D / 0x6DBCC6) + PNG thumbnail + one 0x140000-byte
  data block; in the block only +0x10 (unit name) and +0x90 (checkpoint id) are proven. The list shows name, date,
  size, unit, checkpoint and whether all CRCs match.
- Items: `save.folder`, `save.list`, `save.backups` (info); `save.backup [label]` (all files ->
  `TruMenu.saves\<yyyyMMdd_HHmmss>[_label]\`), `save.export <save>` (-> `TruMenu.saves\export\`, never overwrites);
  **owner only, safety step** (the same command twice within 10 s; menu: a separate red `CONFIRM` button with a stable
  id, `cancel`; refused over TruLink): `save.delete <save>` (full backup `<time>_deleted` first, then the file is
  deleted from the save folder - the copy stays), `save.restore <backup>` (backup `<time>_before_restore` first, then
  the backup's files are copied over; other saves stay), `save.import <name>` (`TruMenu.saves\import\<name>.TRUSave`,
  CRCs must match; backup `<time>_before_import` first).
- **No save field is written** (no unlocks / chapter / inventory / costume / end-game edits in 0.9): nothing beyond
  +0x10 / +0x90 has a proven reader yet.

### Music (P1-P3, Media: music page)

- Engine path only (translate, don't imitate): `media.music.play <track> [slot]` = **`SRMUSIC_LoadMusic` 0x594320
  `(slot, name, fade, fade)`** exactly as the game's unit start 0x5B2211 (slot 0, 60 frames); `media.music.stop
  [slot|all]` = `LoadMusic(slot, NULL, fade, 0)` as the stop native 0x4AA490; `media.music.now` = the 8 slots at
  0xCC5260 (+0 current, +0x100 requested, +0x51C loaded object) and the unit music name 0xD98F64. Game thread,
  experimental, main menu (main state 10) always, a level only with `[Media] MusicInLevels=1`.
- Track names only from **`TruMenu.media.txt`** next to the .asi, written by `tools/music_list.py --menu-out <build
  folder>` and copied by `Set-TruMenu.ps1` (not in the repository). Without it nothing can be played. The list carries
  the source (base / DLC1 / DLC2 / mods override) and `referenced` / `unused?` (today: none unused). DLC tracks of the
  port are silent (converted with silent audio).
- `dev.musicvars` / `dev.monstermusicvars` switch the developer flags 0xE7F098 & 0x10000000 / 0xE7F0A0 & 0x01000000,
  only when the original developer table has that row (found at runtime). `media.video.flags` lists the videos with
  source + flag.
- `weapon.give` was already complete in 0.8.1 (item + "Give <name>" buttons on Time / player / HUD) - unchanged.

### TO TEST 0.9 (owner, in this order)

| # | Where | Step | Expected |
|---|---|---|---|
| 1 | load | Start the game with 0.9 | TruMenu.log: `TruMenu 0.9 (Saves page ...`, `0.9 music 1 (LoadMusic 0x594320 ok, ...)`, media list with 63 rows, `0.9 saves: folder ...\Eidos\Tomb Raider - Underworld\` |
| 2 | main menu, Saves page | open the page | every save with date, unit (e.g. `dlc_caverns`), checkpoint, `CRC ok` |
| 3 | Saves page | `Back up all saves now` | log `saves: backup <time>: n file(s) copied, 0 failed`; the folder appears under backups; files in `TruMenu.saves\<time>\` |
| 4 | Saves page | `Export` on one save | file in `TruMenu.saves\export\`; a second export of the same save gets a time suffix |
| 5 | Saves page | `Delete` on a test save, then wait 11 s | the first press only arms (red CONFIRM + seconds left); after 10 s the arm is gone, nothing deleted |
| 6 | Saves page | `Delete` again, then `CONFIRM` | backup `<time>_deleted` holds ALL saves incl. the deleted one; the file is gone from the save folder; the game's load menu no longer lists it |
| 7 | Saves page | `Restore` on that `_deleted` backup, `CONFIRM` | backup `<time>_before_restore` made first; the save is back, listed in the game's load menu and it loads |
| 8 | TruLink | `menu save.delete <name>` | refused: `err save.delete only from the menu or the command bar (owner)` |
| 9 | main menu, Music page | `Stop all slots`, then `Play` on `l2_waters_of_thailand` | note whether the title music stops; the track fades in (~2 s); `now:` shows slot 0 = the track, object loaded |
| 10 | Music page | `Stop slot 0` | the track fades out (~2 s); `now:` slot 0 without object |
| 11 | Music page | `Show Music Vars` on | is anything drawn in the main menu? (retail draw path unknown) - note it, switch off again |
| 12 | Media: videos | `Play explode` (0.6 item, first live test) | the video plays, the menu comes back; `media.video.flags` lists 6 videos `referenced` |
| 13 | level, only with `MusicInLevels=1` | play / stop once in `dlc_level1_start` | no crash, no stuck audio; the unit music comes back at the next unit change |

## Radial menu (0.10)

Spec: workspace `docs\Konzept-Bau-Rad.md` (stage R1; R2 behind a switch). The ring is only a faster way to run the
existing items - every entry is an item id as typed into the command bar and runs through the same path
(`InvokeCore`, game-thread items queued). Built 2026-11-03 into `work\asi\menu010`; compiled, `dumpbin` and offline
checks only - **not yet seen in the game**.

### Controls

| Input | Effect |
|---|---|
| **L3 + R3 held** >= `HoldMs` (500 ms, menu closed) | the ring opens in **hold mode**: the **right stick** picks a sector live, **releasing** the buttons runs it and closes the ring; released with the stick in the **centre** = nothing (cancel); released on a **level** (`Cheats >`) = that level opens and the ring stays (**latched**) |
| L3 + R3 short (< HoldMs) | TruMenu as before, but it opens at the **release** (owner decision: release variant). In the open menu L3 + R3 closes at the press as in 0.9 |
| **F9 held** (`[Radial] Key`; Steam Controller back button -> F9 in Steam Input) | the ring at once (no HoldMs: F9 has no short meaning); the **mouse direction** (a white dot) or the right stick picks; releasing F9 runs |
| `[Radial] MouseButton` held (3 middle, 4 / 5 side) | as F9 |
| **A** (also left click) | run the pick and **stay open** (several steps in a row: hold, pick, A, A, A); on a level: open it |
| **B** (also right click) | one level back (the pick = the folder you came from); at the top: close |
| LB / RB | page back / on (a level with more than 8 entries) |
| **R3 alone** (latched ring) | run the pick and close (pick with the right stick, then click it) |
| L3 + R3 / F9 again (latched ring) | hold mode again: the release runs the pick (the stick must point at it) |

- **Hold mode** picks live: back in the centre = no pick. **Latched** keeps the pick when the stick springs back (the
  thumb goes to A). The release uses the pick of the frame before (the stick may spring back in the release poll).
- **Remember** (`RememberPosition=1`): a close keeps level, page and pick; the next open shows them highlighted, but a
  release without moving the stick still cancels (centre rule). Repeating an entry = A in the open ring. `0` = top.
- The ring and TruMenu are never open together: opening the menu (F8 / TruLink) closes the ring.
- **Pad while the ring is open:** the game gets a neutral pad (buttons, right stick, triggers), with `PassLeftStick=1`
  the left stick still reaches it (Lara walks). After the close the pad stays neutral until every button is up (the
  B / A / R3 of the close never reach the game). While L3 + R3 wait for HoldMs the game gets the same neutral pad.
- **Keyboard:** `[Radial] Key` never reaches the game while the ring is enabled: `KbdReadHook` drops its DirectInput
  events (DIK = `MapVirtualKey(VK, VSC_EX)`, F9 = 0x43; needs `[Menu] BlockGameInput=1`, which installs the hook) and
  the window procedure drops its `WM_KEYDOWN` / `WM_KEYUP`; other keys pass (WASD walks). **F9 in the game:** tru.exe
  holds no key-name strings at all (`tools/pe_find_str.py` / `pe_find_wstr.py`: no `F9`, `Escape`, `Backspace`,
  `Keyboard`, ASCII or UTF-16) - the PC bindings come from the game data, not read; if the owner has F9 bound in the
  game, set another `Key`.
- **Mouse:** with `[Menu] FreeMouse=1` the ring holds the mouse like the menu (no camera turn, the game's
  `SetCursorPos` / `ClipCursor` held, cursor restored at the close); the middle / side button of `MouseButton` never
  reaches the game.
- `SlowMotion` > 0: `time.scale` = that value while the ring is open; at the close the old value comes back unless
  an entry changed it meanwhile.
- Not built (concept options): a "recently used" sector, "Y = add to the ring" in the menu, the input trace for the
  ring (`[Log] InputTrace` records while the menu is open only - test 102 checks the neutral pad by sight).

### `TruMenu.radial.txt` (next to tru.exe)

```text
# TruMenu radial menu ...                      first line = marker (Set-TruMenu.ps1: ours)
path | label | item id [argument]
Cheats | Gott-Modus | cheat.god
Objekte/Kisten | Kiste A | instance.spawn sh_ei_combat_crate_a       "/" = a level below
```

- A level holds the folders of its sub-paths (`Cheats >`, in the order of their first line) and its entries in file
  order; 8 sectors per page. Limits: 256 entries incl. folders, 48 levels, 64 per level.
- **Bool items without an argument** (`cheat.god`, `time.pause`, `player.invincible`) show **on / off** in the sector
  and run with the other state (`cheat.god 1` / `0` - never "" = flip, the 0.8.1 lesson).
- **Greyed out** with the reason (in the centre when picked, "not available - ..." when run): an unknown id (logged at
  load: `radial: line 31: unknown item 'x' - entry greyed out`), a failed byte pre-check of the item (the Cheats page
  reasons, weapon / ammo / health / time checks, `instance.spawn`), `[Cheats] Enabled=0`, `[Cheat] Experimental=0` for
  game-thread items, `[Radial] Spawn=0`, and "needs a level" for `cheat.*`, `player.*`, `weapon.give`, `ammo.*`,
  `gear.*`, `instance.spawn` / `bring` / `remove` / `unhide`, `camera.mode` / `restore` / `fov`, `costume.next` / `set`.
- **Never offered** (dropped at load with a log line; `RadialRun` refuses them again): `game.quit` (owner rule:
  button-only), `cmd.run`, `save.delete`, `save.restore`, `save.import`, `settings.reset`.
- Every run logs `radial: <path> -> <item> [arg]: <answer>` (LogLevel 1). Queued items show their answer as "last
  action" under the ring.
- Shipped default (`src\asi\TruMenu\TruMenu.radial.txt`, German labels without umlauts - the menu font has none):
  top = Cheats, Marken, Zeit, Waffen, Spieler, Objekte.

| Level | Entries (item) |
|---|---|
| Cheats | Gott-Modus `cheat.god`, Gott-Modus voll `cheat.godfull`, Ein Treffer toetet `cheat.onehitkill`, Gegner-Leben zeigen `cheat.enemyhealth`, Munition endlos `cheat.ammo`, Alles auffuellen `cheat.fillup` |
| Marken | Marke setzen `player.mark`, Zur Marke `player.recall`, Befreien (Marke) `player.unstuck mark` |
| Zeit | Normal 1.0 / Zeitlupe 0.5 / 0.25 `time.scale 1 / 0.5 / 0.25`, Welt einfrieren `time.pause` |
| Waffen | `weapon.give wp_shotgun`, `wp_uzi`, `wp_dlc_gold_shotgun`, `wp_assault_rifle`, `wp_tranq`; Munition voll `ammo.fill` |
| Spieler | Befreien `player.unstuck`, Volle Gesundheit `player.health` ("" = MaxHealth), Unverwundbar `player.invincible` |
| Objekte (R2) | `instance.spawn g_healthpack`, `sh_ei_combat_crate_a`, `_b`, `_c`, `wp_shotgun` (greyed while `Spawn=0`) |

- `Set-TruMenu.ps1 -Install` copies the file next to tru.exe (from the build folder, else `src\asi\TruMenu`; ours =
  first line `# TruMenu radial menu`), `-Remove` deletes only ours; `Build-TruAsi.ps1` puts it into the build folder.
  `../bin/pyt -t 60 tools/trumenu_ini_check.py` checks it (ASCII, three fields, known ids, the forbidden list equal to
  `kRadForbidden`, bool args 0 / 1, one name for `instance.spawn` / `weapon.give` / `level.load`, the limits).

### Items (TruLink / command bar)

| Item | Meaning |
|---|---|
| `radial.status` | the `[Radial]` options, file state (entries / levels / dropped / unknown / skipped), ring state (closed / hold / latched, by pad / key / mouse / radial.open, level, page), entries run, spawn check; also the Status page line `radial (0.10): ...` (0.10.1: `radial (0.10.1)`, plus mode / freeze / quit sector / tests level / tour) and `status.hooks` `radial=...` |
| `radial.list` | every entry `path \| label \| item [arg]` with `= greyed: <reason>` |
| `radial.reload` | read the file again (ring closed) |
| `radial.open [path]` | open the ring latched at that level (test without the pad; B at the top closes) |

### Stage R2: `instance.spawn <object>` (`[Radial] Spawn=1`)

The catalog row "Spawn object at Lara" (workspace `docs\Menue-Funktionen-Katalog.md` section 6), every address re-read
on the Steam exe with `tools/pe_dis.py`, `pe_callers.py`, `pe_cstr.py` and the new `tools/pe_find_bytes.py`;
`work\asi\menu010\precheck_010.txt` = 20 checks, `tools/pe_bytes_check.py --file`: **0 mismatches** (2026-11-03). The
same bytes are checked at load (`SpawnCheck`); a mismatch disables the item with the reason (log line
`0.10 instance.spawn disabled - ...`).

| Step | Function (cdecl) | Fact / check |
|---|---|---|
| DRM present | `0x5bf7b0(name)` -> bool | the game's own composition of the catalog step: `LOAD_UnitFileName 0x477970(buf[0x100], name)` (`sprintf("%s%s.drm" 0x8443bc, prefix 0xa03824, name)` - on PC two arguments, `.drm` is in the format) + `GetFS 0x472b50` (`[0x9ce278]`) -> vtable +8 (FileExists); used by the costume validator (tail call 0x5c54f8) and the level load (0x5de368) |
| object id | `OBTABLE_GetObjectID 0x5bf770` != 0 | 0.2 check (TruMenu's `ObjectId` reads the same table) |
| tracker | `STREAM_GetObjectTrackerByName 0x5c17d0(name)` | id -> `0x5c1550(id, 0)`: finds or requests the entry of table 0xdb7400 (0xcc entries of 0x24: +8 Object*, +0xc s16 id, +0xe u16 status; a new entry gets status 1 at 0x5c1670). No free entry = `"Out of objecttracker space!"` (0x854154 through 0x596cb0) - so TruMenu refuses with fewer than 2 free entries |
| load | `STREAM_PollLoadQueue 0x5c1da0()` until status 2 | 1 while busy (0x5c1dc3 / 0x5c1ddb); status 2 = loaded is the game's own test (0x5bf2e0 `cmp word [eax+0xe], 2` in the loaded-object lookup); the costume switch 0x6f0bc5 polls the same way after 0x5c17d0. TruMenu: at most 3000 ms, `Sleep(1)` between polls - the game thread blocks (a stutter) |
| birth | `INSTANCE_BirthObjectNoParent 0x5bd0f0(unit, &pos, &rot, NULL, object, 0, 1)` | 7 arguments: the script native at 0x780aaf passes `(unit, &pos, &rot, x, object, 0, 1)`, `add esp, 0x1c`; pos / rot are copied at once (0x5bd180, 16 bytes each into +0x20 / +0x30); returns the instance (0 = refused). unit = StreamUnitID `[0xe7f148]` (GameTracker+0xc0, compared with the player's +0xe0 by the game loop 0x5dfc88; both are logged) |

Gates: `Spawn=1`, `[Cheat] Experimental=1`, main state 1 with a player, no level change pending, name `a-z 0-9 _`.
Everything runs on the game thread (queued) inside `__try`; the answer / `TruMenu.log`: `instance.spawn: g_healthpack
(id 55) born at Lara (x y z): instance 0x...; tracker 0x... was in the table / requested now, n polls / m ms; stream
unit u (player +0xe0 = v)`. **Lara's position exactly** (as the catalog) - a crate appears inside Lara; placing in
front of her is stage R3.

**Spawn candidates** (harmless pickups / crates / a weapon object; 2026-11-03):

| Object | id (merged list) | DRM (`tools/archive_has.py`) | Units that load it (`tools/objlist_users.py`, merged `objlist.dat`) | Note |
|---|---|---|---|---|
| `g_healthpack` | 55 | xbase, xbase2, **pcbig** | 115 units incl. `dlc_level2_start`, `dlc_yggdrasil_hall01` / `hall02`, every `dlc2_*` unit | already loaded in DLC 2: no load, tests the birth only - first test |
| `sh_ei_combat_crate_a` | 296 | xbase, **pcbig** | l1 / l6 ship units only | loaded on demand (tests the tracker + load queue) |
| `sh_ei_combat_crate_b` | 297 | xbase, **pcbig** | l1 / l6 ship units only | as a |
| `sh_ei_combat_crate_c` | 306 | xbase, **pcbig** | l1 / l6 ship units only | as a |
| `wp_shotgun` | 40 | xbase2, **pcbig** | l3 units, the DLC 1 units, `container_all_weapons` | a weapon object without an owner - test last |

Not taken: `sh_ei_combat_crate_d` (same kind), `sh_ei_exploading_barrel` (explodes), `wp_dlc_gold_shotgun` /
`dlc1_health_pack` (only in the port's mods, pack10). **Open (before more objects):** whether born instances are
written into saves (back up the saves first - Saves page), how objects without their unit scripts behave, whether a
crate keeps physics without its unit.

### Owner questions of the concept, answered by defaults (all configurable)

| Question (concept section 8) | Default in 0.10 |
|---|---|
| objects first | R2 candidates above (health pack, three crates, the shotgun object); enemies / traps not offered |
| slow motion at the open | off (`SlowMotion=0`) |
| Lara walks while the ring is open | yes (`PassLeftStick=1`) |
| release variant (menu opens up to 0.5 s later) | yes (`HoldMs=500`); `[Radial] Enabled=0` = the 0.9 press variant |
| R1 now, R2 later | both built, R2 off (`Spawn=0`) |

## Radial menu (0.10.1)

Owner wish 2026-11-03: the ring should work like a menu, not like a hold-and-release weapon wheel (workspace
`docs\Konzept-Bau-Rad.md` section 10 "Bedienung v2"), plus a "Tests" level. Built into `work\asi\menu0101`; compiled
(0 warnings in TruMenu.cpp), `dumpbin` and offline checks only - **not yet seen in the game**. `[Radial] Mode=wheel`
keeps the 0.10 ring above unchanged (no Freeze, no built-in sectors).

### `[Radial] Mode=menu` (default)

| Input (ring open) | Effect |
|---|---|
| **L3 + R3 held** >= HoldMs / **F9 tapped** / `MouseButton` tapped / `radial.open` | the ring opens and **stays open** after the release; nothing runs on a release |
| **left stick**, right stick, mouse direction | move the pick (the stronger stick wins; the pick stays when the stick springs back; the mouse picks only while it moves) |
| **D-pad left / right**, arrow keys left / right | the previous / next sector of the page |
| **A** / Enter / left click | runs the pick or opens its level (`Cheats >`); the ring stays open |
| **B** / Backspace / Esc / right click | one level back (the folder you came from is picked); at the top: close |
| LB / RB | page back / on (a level with more than 8 entries) |
| **L3 + R3 again** / F9 again / `MouseButton` again | close (level, page and pick are kept with `RememberPosition=1`) |

- The game gets the **whole pad neutral** while the ring is open (`PassLeftStick` applies to `Mode=wheel` only) and,
  with `[Menu] BlockGameInput=1`, **no keys** (DirectInput events and key messages held as for the menu; a key that
  went down meanwhile stays away from the game until it is released). After the close the pad stays neutral until every
  button is up. L3 + R3 short (< HoldMs) still opens TruMenu at the release.
- A **level.\*** entry (file, tour, a TO TEST row's Run) and "Prepare" **close the ring** after they ran: whether a
  level change goes on while the time.pause bit is set is not proven, the freeze must end (see below).

### `[Radial] Freeze` (Mode=menu; read again at every open - the TO TEST switch `radial-freeze` works at once)

- `world` (or `1`, default): at the open in a level the **time.pause bit** (streamFlags 0xe7f0b8 bit 0x1000, the 0.3 code
  check `g_pauseOk`, the same as `[Menu] PauseGame`) is set; at the close it is cleared **only if the ring set it** and
  nobody ran `time.pause` meanwhile - `time.pause` run from the ring (Zeit -> Welt einfrieren) clears the ring's claim,
  the user's choice stays. A pause from before the ring stays. The game's own pause menu (gameMode 6, 0x5d479b /
  0x5d4810) clears the bit when it opens - then nothing is restored.
- `player` (or `2`): `player.control 0` at the open (the 0.3 byte 0x8ab4e6, `[Cheat] Experimental=1`), the value from
  before back at the close unless `player.control` ran meanwhile or something else changed the byte; the pad is
  neutral anyway.
- `0`: nothing. Outside a level nothing is frozen. Log lines (LogLevel 2): `radial: freeze world - time.pause bit set by
  the ring ...`, `radial: freeze world released (time.pause bit cleared)`.

**Queued items while the world is frozen (static, `tools/pe_dis.py` / `pe_callers.py` / `pe_abs_uses.py`; pinned in
`work\asi\menu0101\precheck_0101.txt`, 17 checks, 0 mismatches):** the main loop 0x5e0190 calls the state dispatcher
0x5e0090 and then `STREAM_PollLoadQueue` 0x5c1da0 every iteration (0x5e01ab). State 1 (in a level, 0x5dffe0) first
calls the input update **0x483810** (no streamFlags test: only `[0xa02b78] && ![0xa02b79]`), which runs 0x483520 per
input manager -> its device object's slot 2 0x483db0 -> the pad object (`[obj+0x2c]`, constructor 0x484520, vtable
0x844dcc, stored at 0x486268) slot 2 0x484b70 -> `call [0xa02b8c]` = **PadHook**, where `RunPending` runs the queued
item - all **before** `GAMELOOP_Process` 0x5dfbe0, which holds every 0x1000 test (0x5dfc2c, 0x5dfcad, 0x5dfd89,
0x5dfdcd, 0x5dfe36, 0x5dfeb2, 0x5dff2c). So the queue does **not** stall: `instance.spawn` (its own poll loop on
0x5c1da0, which the main loop also calls unpaused, then the birth) and the other game-thread items run while frozen;
a born instance is not processed until the close (the instance loop 0x5bbe70 sits in the skipped 0x5dfeb2 block). Not
traced: that the manager's device object `[0xa02b68 + 8]` is the object at `[0xa02b9c]` that holds the pad (same
layout, +0x24 keyboard / +0x2c pad); the existing safety net covers it anyway - when PadHook is not called for 250 ms
the Present hook runs `RunPending` itself. What **does** wait: PadHook's per-game-frame ticks (FlightTick, WeaponsTick
- the weapon re-post after a costume switch -, InvincibleTick, CheatsTick - the cheat.ammo re-apply -, SafeGroundTick)
run when the game clock GameTracker+0xd4 (`kGameClock`, 0xe7f15c) changes, and 0x5dfc2c advances it only without the
pause bit - they go on at the close. No temporary unpause was built.

### Built-in sector "Spiel beenden" (`[Radial] QuitSector=1`, Mode=menu)

The last sector of the **top level only** - not from `TruMenu.radial.txt` (the file check still rejects `game.quit`,
`RadialLoad` still drops it). Same safety as the Status page button of 0.8.1: the first **A** (Enter / left click)
**arms** it (the sector turns red, label `A nochmal = beenden (n s)`, a 10 s window); a **second A** >= 0.3 s later or
**A held 1 s** runs the same path as `game.quit` (`QuitNow`: `game.quit by the owner (TruMenu) - logs flushed next,
then TerminateProcess(...)`, TO TEST list / history written, logs flushed, exit code 0x544D). **Pointing away**, a page
change, **B** and **closing** disarm (`game.quit (radial sector): disarmed - <why>`); 10 s without a second press as
well. The ring has no ImGui widgets, so the 0.8.1 id lesson is kept the other way round: the arm belongs to the
sector's item index, the label only shows the seconds. Its own arm time (the Status button's arm is separate). Only
`RadialTick` reaches it, from real pad / keyboard / mouse edges: no item, no TruLink command (`radial.open` only opens),
no TO TEST toggle, no favourite, no list, no shortcut. Log lines: `game.quit armed by the owner (radial sector 'Spiel
beenden', pad A) - ...`, `game.quit (radial sector): confirmed by the owner (pad A, second press after n ms)` or
`... held 1 s by the owner`, `... second press too fast (n ms) - still armed`.

The top level of the shipped file: Cheats, Marken, Zeit, Waffen, Spieler, Objekte + **Tests** + **Spiel beenden** = 8
sectors (more than 8 = pages; `trumenu_ini_check.py` counts them).

### Built-in level "Tests" (`[Radial] TestsLevel=1`, Mode=menu; owner request 2026-11-03)

No second copy of a list: the levels below Tests are made **every frame** from the lists the pages show (`g_tests` of
`TruMenu.tests.txt`, `g_reg` / column 9 of `TruMenu.regress_dlc1/2.txt`, under `g_testLock`) into one reserved level
slot; every action calls the page's own function, so log lines and result files are the same as on the pages.

| Level (label with counts) | Entries | A on an entry |
|---|---|---|
| `TO TEST n/m offen` | the **open** rows (steps not done, checks open; toggles are in Schalter), list order; steps `S<n> <text>`, checks their id | opens the row: **Run `<item>`** (only when the step's target / the check's id is a usable item and not one of `kRadForbidden` - never `game.quit`), **OK / Fail / Skip** (checks) or **Done** (steps), **Hint** (the hint under the ring; the centre shows it for every entry of the row). OK / Fail / Skip / Done = `TestMarkFromMenu` (`tests: test.mark <id> <state>`, `TruMenu.tests.txt` written) and back to the list |
| `Regression n/m offen` -> `DLC 1` / `DLC 2` / `Alle` `n/m offen` | every row with its state (`[ok]`, `[FAIL]`, `[skip]`, `[done]`) | the row: Run (steps with a target), OK / Fail / Skip (checks) or Done / `Wieder offen` (steps), **Prepare** (rows with a shortcut), Hint - `RegMarkFromMenu` (`TruMenu.regress_results.txt` as the page) |
| `Prepare (n)` | one entry per distinct regression shortcut (as the page's "Quick prepare"), `Stop` while one runs | `RunRegressPrepare` + `SetLastAction` (the page's Prepare button); the ring closes (its first command is a level change) |
| `Schalter n/m an` | the TO TEST **toggles** of the loaded list (e.g. `radial-spawn`, `radial-freeze`) with on / off | `TestMarkFromMenu(id, on / off)` - the page's checkbox (INI written at once / item run with 1 / 0) |
| `Rundgang` | `TruMenu.tour.txt` next to tru.exe, a level per section of the shader tour (Start, hall02, Yggdrasil-Ende, Maschinenraum, Halle Maschine-Zeremonie, Zeremonienraum, Halle Zeremonie-Goo, Goo-Raum, Nur in Zwischensequenzen, DLC 1) and of the hidden-content tour (Versteckt: golden shotgun, `container1`, extended ending) - 11 levels, 2 pages (0.10.2: the DLC 2 rooms below `Rundgang/DLC 2`, section "TruMenu 0.10.2") | the stop's command: `player.goto <intro id>`, `level.start dlc2 / dlc1`; a stop that needs a unit has a `Laden <unit>` entry (`level.load`) in front of it (once per unit); a stop without a command (cutscene, "RB halten") runs `status.unit`. Labels `NN <title>`, `(?)` = place unverified in the doc (04, 06, 17, 23) |

- `TruMenu.tour.txt` (38 entries: 28 stops + 10 `Laden`; 2026-11-03 afternoon: + level `Versteckt` - `Laden
  dlc_dungeon`, `26 Goldene Schrotflinte` = `player.goto 9475` (the `ma_rw_treasure` pickup), `27 container1: Test-Einheit
  (Saves sichern!)` = `level.load container1`, `28 Erweitertes Ende (Saves sichern!)` = `level.load l7_himalaya_end`) is
  written by `../bin/pyt -t 60 tools/tour_from_rundgang.py <workspace>\docs\Shader-Rundgang.md
  <workspace>\docs\Versteckte-Inhalte-Rundgang.md src\asi\TruMenu\TruMenu.tour.txt` (read-only on the docs, several
  docs in order; a stop whose only command is a `level.load` is that entry itself; `Laden` once per unit and section;
  first line `# TruMenu tour`) - also into the build folder `work\asi\menu0101` (data only, no rebuild; Set-TruMenu.ps1
  installs it from there); the radial file format and rules (forbidden ids dropped, unknown ids greyed), log `radial: tour n entries
  from ...TruMenu.tour.txt (0 dropped, 0 unknown, 0 lines skipped)`. `Build-TruAsi.ps1` puts it into the build
  folder, `Set-TruMenu.ps1 -Install` copies it next to tru.exe (ours = the marker line), `-Remove` deletes only ours.
  `trumenu_ini_check.py` checks it like the radial file.
- B on a row -> its list (the row picked), on a list -> the level above, on the first level -> Tests. A row that vanished
  (test.clear, regress.load) -> its list. With RememberPosition the ring reopens on the same virtual level, made anew.
- 0.10.1 also raises the TO TEST / regression list limit `kTestMax` from 64 to 128 rows: `Invoke-TruTestRun.ps1`
  sends the profile rows one by one and the 0.10 profile `regress_shadowlara_50l_radial` has 77 (rows 65 - 77 got
  "list full" with the 0.10 build), `_radial2` has 98 (94 + the two TruShadowCombat 0.4.1 switch steps / checks),
  `_50n_radial2` 62, `_50l_hud_radial2` 60. The virtual level holds up to 128 entries (a file level still 64).
- Deviation from the request: steps have no Fail / Skip (the TO TEST row kinds allow `done` / `open` only for steps);
  "TO TEST" shows checks as well as steps (both are open rows); the regression lists show all rows with their state;
  a note (Regression page "Note") is not offered (it needs the keyboard).

### Keys, status, check

| Key | Default | Meaning |
|---|---|---|
| `[Radial] Mode` | `menu` | `menu` / `wheel` (anything else = menu) |
| `[Radial] Freeze` | `world` | `world` / `1`, `player` / `2`, `0` (Mode=menu) |
| `[Radial] QuitSector` | `1` | the built-in "Spiel beenden" sector (Mode=menu) |
| `[Radial] TestsLevel` | `1` | the built-in "Tests" level (Mode=menu) |

`TruMenu.log` at the start: `0.10.1 radial: mode menu (stays open, A confirms, ...), freeze world (read again at every
open), quit sector 1 (built in), tests level 1 (tour 38 stops / entries), pause code ok, control code ok`; Status page
`radial (0.10.1): ... ; 0.10.1: mode menu, freeze world (ini now world; last open: ...), quit sector on / ARMED, tests
level on (tour ...)` (`radial.status`); `status.hooks` `radial=open (menu) (enabled 1, mode menu)`; `radial.list` names
the quit sector as `- | Spiel beenden | (built-in game.quit safety sector)` (the virtual levels are not listed).
`tools/trumenu_ini_check.py` checks the new keys (values in the INI: Mode menu / wheel, Freeze world / player / 0 / 1 / 2,
QuitSector / TestsLevel 0 / 1), the tour file and the limits with the built-ins (`--ini` / `--radial` / `--tour FILE`
check a copy - the negative test).

## TruMenu 0.10.2 (fixes from the 03.11. ring tests)

Built into `work\asi\menu0102` (asi, ini, radial, tour, `precheck_0102.txt`); compiled with 0 warnings in TruMenu.cpp,
`dumpbin` ok, byte checks 0102 (10) + the older lists 010 / 0101 / 071 / 072 / 080 / 081 / 09 (136): 0 mismatches,
`trumenu_ini_check.py` ok - offline only, **not yet seen in the game**. Owner note (German):
`<workspace>\docs\TruMenu-0.10.2.md`.

### `cheat.godfull` without flight (F15, los7 21:22:21)

0.8 - 0.10.1 set `GameTracker.cheatMode` bit 0: PlayerTakeDamage returns at once, but the same bit is the flight
cheat's switch (55 `test` sites gate player behaviour with it) - Lara flew. 0.10.2 leaves cheatMode alone and uses the
player's **own no-damage bit** `[0xfada74] & 0x20000` (the 2007 prototype's `ControlFlag` bit "rlwinm 14,14", workspace
`docs\Abakus-Pruefung.md` 18.7 and item 1):

| Site | Code | Effect of the bit |
|---|---|---|
| ApplyDamage 0x6f4f70 | first instruction 0x6f4f71 `test [0xfada74], 0x20000; jne ret` | no damage at all; ApplyDamage is the only code that lowers `P+0x628` (all `+0x628` writes in 0x6e0000..0x780000: 0x6f4e6c / 0x7000d9 refill, 0x6f4f2e GainHealth, 0x6f4fd7 / 0x6f5004 ApplyDamage, 0x6f55cc HealthInstantDeath) |
| PlayerTakeDamage 0x6f5030 | 0x6f5042, **before** the type 8 (raw) / 5 tests | types 8 / 5 are blocked too (cheat.god lets them through) |
| DamageBypass 0x6f5140, 0x703008 | the other two ApplyDamage callers | blocked |
| 0x721c8d | skips ProcessHealth 0x6f5160 | the hit timer / death check do not run while it is set (as in the game's death state, `mov [0xfada74], 0x40020208` at 0x75a447) |

Every player state entry rewrites the word (`mov [0xfada74], imm`), so `NoDamageTick` (PadHook, once per game frame,
before `GAMELOOP_Process`) ORs the bit in again - a state entry and a hit **in the same frame** can still let one hit
through. **Instant deaths** (`HealthInstantDeath` 0x6f55a0, callers 0x75afda in the death state's process / 0x75b099)
test neither this bit nor cheatMode: they still kill (the old variant only avoided them because Lara flew). The off
clears the bit only while the word is still the one the tick left (otherwise it is the game's own), sets
`gInvincibleCheat` 0 as before, and **ends a left-over flight**: cheatMode bit 0 set while `cheat.flight` is off ->
cleared + `INSTANCE_Post(player, 12, 0)` (as `cheat.flight 0`). Pre-check: the five tests and the call 0x6f50aa
(`g_godFullWhy` names them). Ring label: `Gott-Modus voll (ausser Sofort-Tod)`. Log: `cheat: god mode full ON (byte
0x00fadf60 = 1, mode flags [0x00fada74] = 0x...)`; answer `cheat.godfull 1 (gInvincibleCheat + no-damage bit ... per
frame, no flight; instant deaths still kill)`.

### `player.unstuck` / marks (F6, B28)

- **No sampling** while TruMenu or the ring is open, the time.pause bit (streamFlags 0x1000) is set, the main state is
  not 1, a **cinematic** runs (the game's own test tru+0x53f00 - `[0xe7f1c0] && byte +0xdd && dword +0x2c != -1`, the
  gate TruShadowPower 0.9 uses; read here, not called; bytes checked at load, `g_cineOk`), player control is off,
  `time.scale` is not 1, flight is on or health <= 0; the window starts again after each pause. los3 (20:35:58): the
  spot used lay ~7300 units above Lara (`-1311 4869 -683` vs `684 -1149 -7947`) - it was taken during the DLC 2 intro.
- **Ground test (heuristic, no proven on-ground flag):** 7 samples 5 game frames apart (~1 s); the middle one becomes a
  spot when every sample is within 12 units of the chord from the first to the last (free flight is a parabola: ~120
  units off over 1 s at ~980 units/s^2, 1 unit ~ 1 cm) and the slope first -> last is at most 0.8 plus 10 units for
  steps. Walking up / down ramps and over small bumps passes (los7: "height changed < 5 in 1 s" let almost nothing
  through on uneven ground). **Blind spots:** hanging at a ledge / shimmying, swimming at the surface, a moving
  platform look like ground.
- **Facing:** `player.mark` and every safe spot store Lara's yaw (instance +0x38); `player.recall` / `player.unstuck`
  write it back with the position (x / y rotation untouched). **Not done:** movement state and velocity - no
  player-state / velocity field and no "stand now" call is proven, so a recall during a jump or fall keeps that state
  (los7: she grabbed a ledge in reach). Recall while she stands.
- `player.safeground` (info, ring `Spieler/Helfer/Befreien: Stand`): `n safe spots, newest ...; mark set; ground windows
  a ok / b not; waiting: <reason>`. Start log: `0.10.2: cheat.godfull = no-damage bit ..., safe ground: 7 samples x 5
  frames, chord 12, slope 0.8 + 10, cinematic test 1, marks keep the yaw`.

### Tour and `level.start` (F8)

- `tools/tour_from_rundgang.py`: the "DLC 2 - <room>" sections of the shader tour go below **`Rundgang/DLC 2/<room>`**
  (8 rooms = one page); DLC 1, Versteckt, Paket-Ziele and "Nur in Zwischensequenzen" stay on the Rundgang level (5
  sectors). Every `level.start` stop gets a `Laden <start unit>` entry in front (dlc2 -> `dlc_level2_start`, dlc1 ->
  `dlc_level1_start`): `level.start` works from the main menu only (los7 21:22:37 `err main menu only (main state 1)`),
  the `Laden` entry is the in-level way (no intro). 33 stops, 46 entries, 12 sections.
- The ring greys `level.start` out outside the main menu (main state != 10): `main menu only - in a level: 'Laden ...'
  (level.load, no intro)`. The item itself is unchanged (TruLink / TO TEST / AutoStart).
- Note: `Laden dlc_level1_start` from DLC 2 is the cross-DLC load of F12 (Lara loads as the doppelganger; the fix is
  TruDlc2Player 0.3 `[Dlc2Player] CostumeReset`, offline) - without it, start DLC 1 from the main menu.

## TruMenu 0.10.3 (F7: sound with the world freeze)

Built into `work\asi\menu0103` (asi, ini, radial, tour, `precheck_0103.txt`); 0 warnings in TruMenu.cpp, `dumpbin`
ok, byte checks 0103 (15) + 0102 (10): 0 mismatches, `trumenu_ini_check.py` ok - offline only, **not yet heard in
the game**. Owner note (German): `<workspace>\docs\TruMenu-0.10.2.md`, section "0.10.3".

**Switches (both 0 = off by default, live test first):** `[Radial] FreezeSound=1` - while `[Radial] Freeze=world`
holds the world (the ring set the pause bit itself) the sound pauses too; `[Menu] PauseSound=1` - for every other
world pause in a level (`time.pause` from ring / menu / bar, `[Menu] PauseGame`). Items (runtime only, TruMenu.ini is
not written; a value changed in the ini is taken over within a second, so the TO TEST switches
`ini:TruMenu:Radial:FreezeSound` / `ini:TruMenu:Menu:PauseSound` work too): `time.freezesound`, `time.pausesound`
(bool), `time.sound` (info: switches, pause bit, gameMode, `[0xccde88]`, last action). Ring: `Zeit` -> `Ton mit
Rad-Einfrieren`, `Ton mit Welt einfrieren`, `Ton-Pause: Stand`.

**The game's functions (static, `tools/pe_dis.py` / `pe_callers.py` / `pe_abs_uses.py`):**

| Function | What it does | Callers |
|---|---|---|
| 0x5874b0 | `0x5873a0(1)`; `[0xccde88] = 1`; `jmp 0x4831c0` | pause menu open 0x5d47b6 (0x5d4780), 0x5d4821 (0x5d4810) |
| 0x5874d0 | `0x5873a0(0)`; `[0xccde88] = 0`; `jmp 0x4831d0` | pause menu close 0x5d4738 (only at gameMode 6), level start 0x5de4a5, level loads 0x5df80c / 0x5dfb7d / 0x5dfb8e |
| 0x5873a0(b) | for each index in the list `[0xccdea0]` (+0x1c count, +0x20 ints): bit 0 of `+0x10` of the sound group `[0x8a80d8] + index * 0x84` := b | the two above |
| `[0xccde88]` | 1 = the stream / music update 0x595250 (8 players at 0xcca9a0, 0x178 bytes) returns at once | set only by the pair, 0 at init 0x586435 |
| 0x4831c0 / 0x4831d0 | input manager 0xa02bd0: 0x4816f0 clears, 0x481750 sets again one byte flag in 4 slots of 4 pads | only the pair (rumble not proven: XInputSetState is called from 0x484940, another object) |

- **No counter, no toggle:** the pair *sets* a state - two pauses and one resume = running. `[0xccdea0]` is read
  without a null test and is 0 between levels (set 0x5df0c9, cleared 0x5df961) - TruMenu never calls the pair then.
  Which sound groups the list holds (sfx / voice / music?) is game data, not code. The window-focus pause
  (0x587410 / 0x587460, flag `[0xccde92]`, master group via 0x7b9490) is separate and not touched.
- **Balance with the pause menu:** the menu's open clears the pause bit 0x1000 itself and pauses the sound; its close
  resumes only at gameMode 6. TruMenu (`SoundFreezeTick`, game thread, every pad poll) acts only on the edges of its
  own want (the same answer on two polls), only when `[0xccde88]` is the other state, never at gameMode 6 (an own
  pause is dropped then - the menu resumes at its close), and once the game resumed the sound itself (level start /
  load) it is not paused again until the next freeze. A fault in a call turns the feature off (`__try`).
- Load check `SoundCheck`: both functions, 0x5873a0's list read, the reader 0x595253, the pause menu's open
  (gameMode 6 + call) and close (gameMode test + call). Start log: `0.10.3 sound with the freeze: code ok ...`.
- Log lines: `sound: sound paused (0x5874b0) - ring freeze, [Radial] FreezeSound`, `sound: sound resumed (0x5874d0) -
  pause bit cleared`, `sound: the pause menu opened - ...`, `sound: time.freezesound 1 (...)`.

**Light shaft (B29, not built):** the shader clock `TimeVector` (PS c53 / VS c23, uploaded at 0x5096c7 from
RenderDevice `[0xa1407c]` +0xfa4c / +0xfa48) advances by the dt of 0x5bf840 = `[0xe7f188]` (frame time x time scale),
which the pause bit 0x1000 does not stop (it only skips the instances). Only the pause menu stops it, through
0x5bfdf0(1) (`[0xdb94de] = 1`, back to 0 at the close 0x5d4765). So every `TimeVector` material keeps moving in the
freeze - in `dlc_level2_start.drm` (Xbox materials with `TimeVector`: 23157 = tuple 1058-1061, unlit one-texture
material with opacity and height fog, base twins in `l7_helheim0x` / `l7_yggdrasil_end` = the likely light shaft;
24920 eitr water surface, 24691 eitr column, 24736 / 26444 / 26445, 972 distortion). The unit's 41 objects contain no
light-ray object (`tools/objlist_unit_compare.py --units dlc_level2_start --list`), so the shaft is level geometry.
Proposal: a later `[Radial] FreezeShaders` calls 0x5bfdf0(1) / (0) with the same edge / gameMode-6 rules.

## TruMenu 0.10.4 (F7: shader clock with the world freeze; F6 stand state not built)

Built into `work\asi\menu0104` (asi, ini, radial, tour, `precheck_0104.txt`); 0 warnings in TruMenu.cpp (2 x C4100
in `imgui_demo.cpp` as before), exports / imports as 0.10.3, byte checks 0104 (14) + 0103 (15) + 0102 (10): 0
mismatches, `trumenu_ini_check.py` ok (60 keys) - offline only, **not yet seen in the game**. Owner note (German):
`<workspace>\docs\Befund-Menue-Dlc2Player-0411b.md`.

**Switch (0 = off by default):** `[Radial] FreezeShaderClock=1` - while the world is frozen in a level (pause bit
0x1000: the ring's `Freeze=world`, `time.pause`, `[Menu] PauseGame`) the shader clock `TimeVector` holds too. Item
`time.freezeclock` (bool, runtime only; a value changed in the ini is taken over within a second, TO TEST switch
`ini:TruMenu:Radial:FreezeShaderClock`), info `time.clock` (switch, pause bit, gameMode, `[0xdb94de]`, RenderDevice
+0xfa4c / +0xfa48, last action). Ring: `Zeit` -> `Shader-Uhr mit Einfrieren`.

**How the game makes the value (static, `pe_dis.py` / `pe_callers.py` / `pe_disp_scan.py`):**

| Step | PC | What |
|---|---|---|
| dt | 0x5bf840 (only caller 0x5cebc0, once per frame) | `[0xdb94de]` != 0 -> dt = 0 (`fldz`), else `[0xe7f188]` / `[0x8439b8]` (double 30.0; or `[0xe7f194]` / `[0x84bd00]` while `[0xe7f0b4]` & 0x10000000) |
| accumulate | RenderDevice `[0xa1407c]` vtable +0xc = 0x506f10(dt) | `+0xfa48` = dt; `+0xfa4c` += (int)(dt x `[0x8416d8]`, double 1000.0) - an integer accumulator (getter 0x509190; also written at 0x508900, `mov [esi+0FA4Ch], ebx`); only when the device state test at 0x506f67..0x506f7b passes |
| upload | 0x5096c7 | TimeVector = ((`+0xfa4c` mod 1000000) x `[0x8416d0]` (double 0.001), `+0xfa48`, 0, 0) -> PS c53 (0x509711) / VS c23 (0x509721) |
| hold | 0x5bfdf0(b) = `[0xdb94de]` := b | pause menu open 0x5d47ae (1), close 0x5d4765 (0), level start 0x5de3c7 (0), unknown menu 0x6e4887 / 0x6e548c |

The pause bit does not touch this path; the pause menu holds it with 0x5bfdf0(1): dt 0, the accumulator stays (x held,
y = 0), and after 0x5bfdf0(0) it goes on from the held value - **no jump, so no offset is needed**. TruMenu
(`ShaderClockTick`, game thread, every pad poll) calls the same function with the 0.10.3 sound rules: own edges only
(two polls agree), never at gameMode 6 (the pause menu owns the byte: claim dropped), the game's own release (level
start) is not fought. Load check `ClockCheck` (reader, setter, accumulator, upload, pause menu open / close). Log:
`shader clock: ON - TimeVector held (0x5bfdf0(1), ring freeze, ...): accumulator +0xfa4c N, dt ...`, `shader clock:
OFF - TimeVector runs on (0x5bfdf0(0), ...) after S s: accumulator N (held at N: unchanged = no jump)`, `shader clock:
the pause menu opened - ...`, `shader clock: the game released the clock itself ...`.

**Costume check:** the state save tru+0x155cb1 is accepted as the game's store or as TruDlc2Player 0.5's
`[Costume] TuMapping` detour (`jmp` out of tru.exe + 8 nops) - log `costume: state save 0x00555cb1 is a detour to ...
accepted`; 0.10.3 turns its costume items off in that case.

**F6 "Zur Marke" stand state - not built (`[Menu] MarkSetStand` not added):** no game function that puts the player
into standing was found offline. Every player state change on PC goes through the data-driven chart:
SCAgent::ChangeState tru+0x387890 (string `* Agent %d ChangeState to NULL is illegal!` 0x861070) is called only from
the agent's own transition / event code (tru+0x387c78 / 0x387d53 / 0x387d9e). The 2007 prototype map names the
script teleport `NsInstance::WarpTo` (position, stream unit, rotation only) and `INSTANCE_SetPositionPlayerFindGround`
(ground probe + `STREAM_SetInstancePosition` + `PLAYER_ResetSmoothRide`) - neither touches the state; a respawn builds
a new tracker / agent (initial chart state), which is not a teleport. Which chart state is "stand" is data, so a state
log (TruTrace) has to show it first. `player.recall` is unchanged.

## TruMenu 0.10.5 (screenshots, Claude marks)

Built into `work\asi\menu0105` - offline only, **not yet seen in the game**. Owner note (German):
`<workspace>\docs\Befund-TruMenu-Shot-0511.md`. Goal: the test session gets named in-game screenshots in the run
folder instead of ShareX files (no useful names, wrong times), and marks the player sets while playing.

**Screenshots.** Item `shot.save [ui|clean] [name]` (command bar, TruLink `menu shot.save <name>`, ring `Spieler` ->
`Screenshot`), the export `TruMenuShot(const char *name)` for other plugins, and the Claude marks below. A request gets
its file name at once: `[Shot] Folder` (default `TruShots\` next to tru.exe) + `shot_<HHMMSS>_<step>_<name>.png`,
`<step>` = `step<n>` of the lowest TO TEST step that is not done, else `-`; `<name>` sanitised to `A-Z a-z 0-9 _ - .`
(at most 40, empty = `-`); the same second / step / name again = `_2`, `_3`; a file left from an earlier session =
`-2` .. `-9`. The copy is taken by the existing Present hooks (device Present slot 17 and swap-chain Present slot 3 -
**no new hook**): before `Render()` = clean (no menu, ring, command bar or TruMenu overlay; default `[Shot] Clean=1`),
after it = as on screen (`shot.save ui ...` or `Clean=0`). On the render thread only: `GetBackBuffer(0)`, for a
multisampled back buffer `CreateRenderTarget` + `StretchRect`, `CreateOffscreenPlainSurface(D3DPOOL_SYSTEMMEM)` +
`GetRenderTargetData`, `LockRect` + row copy, all surfaces released in the same call (nothing is held over a Reset).
Pixel conversion (X8R8G8B8 / A8R8G8B8, R5G6B5, X1R5G5B5 / A1R5G5B5, A2R10G10B10), PNG encoding (`TruShotPng.h`, own
code: per-row PNG filter, fixed-Huffman deflate with a 32 KB hash-chain LZ77, CRC-32, Adler-32) and the file write
run on a worker thread (at most 2 at once; a request waits a frame while they are busy; queue of 4). One log line
per file:

```text
shot: <folder>\shot_142233_step3_lightshaft.png 1920x1080 1672169 bytes, capture <ms> ms (render thread), encode <ms> ms + write <ms> ms (worker); clean, TruLink
```

The capture time is the GPU sync of `GetRenderTargetData` and only known from a live run; the offline encoder test
took 255.5 ms for a synthetic 1920x1080 image (worker thread). Over TruLink the answer waits up to 2 s for the copy:
`ok captured <path> (the PNG is written on a worker thread ...)`; from the menu / ring / bar it is `ok queued <path>
...`. Refusals: `shots off ([Shot] Enabled=0)`, `no d3d9 device hooked yet`, `busy (...)`, `more than N shots per
minute ([Shot] MaxPerMinute)` (log line `shot: <source> refused - ...`, at most one per second). `shot.status` shows
the options, the folder, the counters and the last file / error.

**Claude marks.** Ring level `Claude` on the top level, drawn in coral #D97757 (217, 119, 87) with white text:
`Jetzt` (now), `Gut` (good), `Fehler` (bug), `Grafik komisch` (gfx), `Ton komisch` (sound), `Ruckler / Haenger`
(stutter) = item `claude.mark <kind>` (also command bar / TruLink `menu claude.mark bug`, export
`TruMenuMark(const char *kind)`, `[Shot] Hotkey` = `now`). Each writes one TruMenu.log line and requests a clean shot
named `<kind>`; the ring closes after the pick (play goes on at once; the shot is clean either way):

```text
HH:MM:SS.mmm claude.mark <kind>: <HH:MM:SS.mmm> unit=<stream unit> pos=<x> <y> <z> step=<step<n>|-> shot=<file|-> src=<ring|hotkey|menu|TruLink|TruMenuMark>[ (no shot: <reason>)]
```

`unit` = the stream unit Lara is in (as `[Log] UnitChanges`; else the unit at GameTracker+0x38, else `-`), `pos` =
Lara's position rounded (`- - -` without a player), `shot` = the file name in `[Shot] Folder`. Marks are rate-limited
like shots (`MaxPerMinute`, own window). To make room on the top level (8 sectors, one page), the R2 level `Objekte`
moved to `Spieler/Objekte` (`Claude` takes its sector; Cheats, Marken, Zeit, Waffen, Spieler, Tests, Spiel beenden keep
their places).

**Options** `[Shot]`: `Enabled=1` (requests only - nothing is taken automatically), `Folder=` (empty = `TruShots`
next to tru.exe, relative = below the game folder), `Clean=1`, `Hotkey=0` (e.g. `0x7A` = F11 -> `claude.mark now`;
the game still gets the key), `MaxPerMinute=30` (1 .. 120, 0 = no limit).

**Offline proof:** `selftest\TruShotPngTest.cpp` (built with the same x86 compiler, not part of the asi) encodes 8
test images in every supported format with padded rows; `tools/png_selftest_check.py` decodes each PNG on its own
(chunk CRCs, zlib / Adler-32, the five filters) and compares the pixels with its own conversion of the raw source
pixels: 8 / 8 equal. `tools/pe_import_export_diff.py` 0.10.4 vs 0.10.5: imports unchanged (141 functions, KERNEL32 /
SHELL32 / USER32; the D3D9 calls go through the device vtable), exports + `TruMenuShot`, `TruMenuMark`.
`tools/src_hook_sites_diff.py`: vtable patches 4 / 4, code writes 12 / 12, VirtualProtect 6 / 6, byte checks 147 / 147
- the new lines are 5 device calls in `ShotCapture`, 1 `CreateThread` (worker) and the 2 exports.
`tools/trumenu_ini_check.py` checks the `[Shot]` values and the Claude level.

## TruMenu 0.11 "Ablauf" (guided test runs)

Owner wish 2026-11-05 (stage 2 of the Claude marks): a test run is a **flow** of steps that the ring shows one after
the other, with counters that fill themselves from the plugin logs. Built into `work\asi\menu011`; compiled, offline
checks only - **not yet seen in the game**. Everything is off without `[Flow] Enabled=1` (the profile sets it); the
ring entries of the flow are then greyed out ("kein Ablauf").

### `TruMenu.flow.txt` (next to tru.exe, `[Flow] File`)

UTF-8 (BOM optional), one record per line, fields separated by `|` (so `|` cannot appear inside a field), `#` lines and
empty lines skipped. First line `# TruMenu flow ...` = ours (`Set-TruMenu.ps1`, `Invoke-TruTestRun.ps1`). Written by
the workbench generator `New-FlowFile.ps1` from a test profile; the parser is `TruFlowCore.h` (own code) and the same
rules in PowerShell in `Invoke-TruTestRun.ps1` / `Test-TruPreflight.ps1`.

```text
flow    | <id> | <title>                               once, optional
counter | <id> | <source> | <target> | <text>          target 0 = only counted
step    | <id> | action|observe|mark | <text> [| key=value ...]
```

| Step kind | Weiter (`flow.next`) | Gut / Fehler (`claude.mark good / bug`) | other Claude mark |
|---|---|---|---|
| `action` | runs its `do=` commands (the regression-shortcut path: one command per free game-thread slot, `level.*` waited for, an `err` stops); ok when they are done and (if any) a `check=` is met | ok / fail | recorded on the step |
| (any kind) | | | `mark:<name>` conditions and `mark:` counters see it |
| `observe` | leaves it open (no result) and goes on | ok / fail | recorded |
| `mark` (an instruction) | done (ok) | ok / fail | done (ok) |

| Step key | Meaning |
|---|---|
| `do=<cmd>;<cmd>` | action only; at most 12 commands / 319 characters (`kShortcutLen`), never `game.quit`, no `#title` |
| `after=<cond>` | all must be met before Weiter runs an action (repeatable, at most 4); the status line shows "wartet: ..." |
| `check=<cond>` | any one met after the step started = ok (an action: after its commands); at most 4 |
| `fail=<cond>` | any one met after the step started = fail; at most 4 |
| `count=<counter>[,<counter>]` | at most 4; the first one is shown in the status line |
| `skip=<reason>` | skipped when the flow reaches it |
| `hint=<text>` | third line of the status line / the ring centre |

Conditions: `step:<id>` (that step ok), `done:<id>` (ok / fail / skip), `counter:<id>` (target reached; target must
be > 0), `mark:<name>` (a Claude mark of that kind while the step is current: `now`/`Jetzt`, `good`/`Gut`,
`bug`/`Fehler`, `gfx`/`Grafik`, `sound`/`Ton`, `stutter`/`Ruckler`), `log:<TruX.log>:<pattern>`,
`trace:<category>:<pattern>` (TruTrace.log lines `time [unit] <category>: text`, an empty pattern = any line).

Counter sources:

| Source | Counts | From |
|---|---|---|
| `units[:<unit>]` | stream unit slots that became loaded | TruTrace 0.2 `stream: stream unit slot n: id x '<unit>' state 2 = loaded` |
| `levels[:<unit>]` | level loads (result of `STREAM_LevelLoadAndInit`) | TruTrace 0.2 `level: STREAM_LevelLoadAndInit '<unit>' (...) -> unit entry` |
| `restores` | checkpoint restores | TruTrace 0.2 `save: SAVE_RestoreGame(n) -> r` |
| `deaths` | player deaths | the rising edge of bit 0x10000 of the player state-mode word `[0xfada74]` (below) |
| `toggle:<id>` | TO TEST switch flips | `test.mark <id> on/off` (page, ring Schalter, TruLink) |
| `item:<id>` | runs of an item (not info reads) | `InvokeCore` (menu, ring, bar, TruLink, shortcuts) |
| `mark:<name>` | Claude marks of that kind | `claude.mark` (ring, hotkey, TruLink, `TruMenuMark`) |
| `log:<TruX.log>:<pattern>` / `trace:<cat>:<pattern>` | matching lines | the tail below |

Patterns: plain text = substring (case-sensitive); `re:<expr>` = a regex subset (literals, `.`, `\d \w \s \D \W \S`,
escaped punctuation, classes `[a-z]` / `[^...]`, the postfix `* + ?`, `^` first and `$` last; no groups, no `|`, no
`{n}`), matched as a state set (linear in the line, no backtracking). Texts are shown in ASCII (`ae oe ue ss`).
Limits: 64 steps, 16 counters, 48 distinct log patterns, 8 log files, 159 bytes per text.

**Why the log tail and not a TruTrace export:** TruTrace writes the unit / level / restore lines anyway; reading them
needs no interface between the two plugins (no load-order or version coupling, no change to TruTrace, works with an
older TruTrace for the other counters and degrades to "0" without it). TruMenu's own tail (worker thread, every
`[Flow] PollMs` = 500 ms) reads **every** new byte of the files the flow names (at most 256 KB per file and poll; more
is skipped with a log line), not the 6 KB window of the log page. TruTrace rate-limits its categories (40 lines / s) -
unit / level / restore lines are far below that. A pattern line is "after the step started" with poll granularity.

**Player deaths (static, `tools/pe_flag_bit_writers.py data/pc/tru.exe 0xfada74 0x10000`, pinned in
`work\asi\menu011\precheck_011.txt`, 14 / 14 ok):** of the 33 instructions that write `[0xfada74]` only one sets bit
0x10000: `or dword [0xfada74], 0x10408` at 0x75aa69 in `DeathState::Entry` 0x75aa50; 11 clear it (the immediate stores
of every other state entry and the store of ecx = 0x81 at 0x7522da), 20 keep it, 1 (0x752320, ecx = 0x81 from 0x7522d5,
no ecx write in between - read by hand) clears it too. TruMenu reads the word once per frame (render thread, no hook)
and counts a rising edge while a player exists; the bytes at 0x75aa69 are checked at load (mismatch = deaths not
counted, said in the load line).

### Ring level "Claude" (TruMenu.radial.txt)

Page 1: **Weiter** (`flow.next`, label "Weiter: <current step>"), **Ueberspringen** (`flow.skip`), Jetzt, **Gut**,
**Fehler**, Grafik komisch, Ton komisch, Ruckler / Haenger (the 0.10.5 marks, order kept); page 2 (RB): **Zurueck**
(`flow.back`), **Ablauf n/m** (`flow.status`). The centre shows the current step, its hint and what it waits for. Gut /
Fehler write the 0.10.5 mark line + clean shot and set the current step ok / fail; Weiter that ran / finished a step
closes the ring (as a mark does). Shot names use the current flow step instead of the TO TEST step.

### Status line, toast

`[Flow] Overlay=1`: `Claude-Ablauf  Schritt n/m | <counter a/b> | naechster: <text>` in coral in the corner
`[Flow] Position` (tl / tr / bl / br, default br), `Size`, `Lines` (2 = + the current step, 3 = + waits for / hint).
`flow.say <text>`: a coral toast at the top for `[Flow] ToastSeconds` (6 s). Both drawn by TruMenu (not in clean shots).

### Items (TruLink `menu <id> [arg]`, command bar)

| Item | Meaning |
|---|---|
| `flow.status` | file, step n/m with state / waits for, results, deaths, every counter (one line) |
| `flow.list` | every step `n id kind state by` (`>` = current) |
| `flow.next` / `flow.back` | Weiter / Zurueck (the step before is reopened) |
| `flow.skip [<id> [reason]]` | skip (no id = the current step) |
| `flow.goto <id>` | that step is current (reopened) |
| `flow.add <record>` | append a counter or step record (file syntax) |
| `flow.say <text>` | toast + log line |
| `flow.result ok` / `fail [note]` | = `claude.mark good / bug` (+ the note on the step) |
| `flow.reload` | read the file again (all states anew) |

TruLink needs no change (`menu` passes the rest of the line), but its tokenizer keeps at most 24 words per line and
joins them with single spaces: a long `flow.add` record is cut, double spaces in a pattern become one.

### `TruMenu.log` lines (Invoke-TruTestRun.ps1 builds the summary section "Ablauf" from them)

```text
flow: loaded <path>: n steps, m counters, w log patterns, e errors (id <id>: <title>); deaths counted (...)
flow: error line <n>: <message>
flow: step <id> start|run|open|ok|fail|skip <i>/<n> t=<s since load> [dur=<s>] [by=<Weiter|Gut|Fehler|auto|commands|file|...>] [note=<text>]
flow: counter <id> <value>/<target> t=<s>[ reached]          (at most one line per counter and second)
flow: mark <kind> step=<id|-> shot=<file|-> t=<s>
flow: death <n> ([0x00fada74] = 0x..., DeathState entry bit 0x10000) t=<s>
flow: say <text> | flow: add <record> -> ok|err ... | flow: goto <id> | flow: done ... | flow: end (game.quit) ...
```

### Keys, checks

| Key | Default | Meaning |
|---|---|---|
| `[Flow] Enabled` | `0` | 1 = read the flow file (worker thread), tail the logs it names, flow entries in the ring |
| `[Flow] File` | `TruMenu.flow.txt` | relative = next to tru.exe |
| `[Flow] Overlay` / `Position` / `Size` / `Lines` | `1` / `br` / `1.0` / `2` | status line |
| `[Flow] AutoAdvance` | `1` | a step finished by check / fail / its commands moves on |
| `[Flow] ToastSeconds` / `PollMs` | `6` / `500` | toast time, tail interval |

Offline checks: `/W4` 0 warnings in `TruMenu.cpp` / `TruFlowCore.h`; `tools/pe_import_export_diff.py` 0.10.5 vs 0.11:
exports unchanged, one new import `KERNEL32!GetFileAttributesExA` (the tail's start size); `tools/src_hook_sites_diff.py`:
no new hook / patch / write, one new byte pre-check (0x75aa69); `tools/trumenu_ini_check.py` (`[Flow]` values, flow
items, the flow entries in the level Claude); `selftest/TruFlowCoreTest.cpp` + the workbench test compare the C++
parser / matcher with the PowerShell parser and .NET Regex.

## TruMenu 0.12 "Debug-Zeichnung" (NavPower debug drawing, debug view stage S0)

Built into `work\asi\menu012`; compiled, offline checks only - **not yet seen in the game**. Owner notes (German):
`<workspace>\docs\Befund-Debug-Ansicht-0511.md` section 1.1 (the research) and `<workspace>\docs\Befund-TruMenu-Debug-0511.md`
(this build). Everything is off without `[Debug] Enabled=1`; the ring entries are greyed then.

**What it switches.** The Steam `tru.exe` contains the complete debug drawing of the NavPower ("BabelFlux", `bfx`)
middleware: 39 `BoolSetting` objects (vtable 0x841144, `tools/bfx_settings_dump.py`), each pointing at one switch byte in
`.bss` (0 in retail; `tools/pe_abs_uses.py`: no instruction writes them). Every game frame 0x5da141 -> 0x489c60 ->
`jmp 0x42f900` runs the draw function of every NavPower component while `[[0x8c0f0c]+0x10] == 1`; the planner's
(0x418870, registered at 0x4211ad) calls the planner draw 0x418680 and the obstacle draw 0x407690 and draws the recent
navprobes. Lines go through Crystal's renderer bridge `CDCRenderer` (vtable 0x845224, object `[0x8c0f3c]`) slot 0
0x48a500 -> `DRAW_DrawLines` 0x5bfcd0. TruMenu only writes those data bytes (and the layer mask below) - **no game code
is changed, no new hook**. Middleware text goes to the empty stub 0x6457a0 (invisible), so only line switches are offered:

| Switch (`nav.draw <name>`) | Byte | Reader(s) | Draws | Note |
|---|---|---|---|---|
| `planner_areas` | 0x8bf2e5 | 0x41869c, 0x40c3a0 | navmesh areas, outline | drives the per-area loop |
| `planner_areas_solid` | 0x8bf2e6 | 0x4186a5, 0x40c3ba, 0x40c68d | navmesh areas, filled | drives the per-area loop; cost unknown |
| `planner_connectivity` | 0x8bf2e7 | 0x40c8bb | a line from each area to each neighbour | **only with `planner_areas` or `_solid` on** |
| `planner_area_normals` | 0x8bf2ec | 0x40c7c8 | the normal of each area | **only with `planner_areas` or `_solid` on** |
| `obstacles` | 0x8bf308 | 0x407690 | dynamic obstacles (list `[0x8bf2f8]`) | own path |
| `recent_navprobes` | 0x8bf309 | 0x418880, 0x420583, 0x4205bf | the latest navmesh probes of the AI | the probe query 0x420580 records each probe while on (one extra call 0x41b4b0 in the query path) |
| `draw_mover3d_path` | 0x8bf006 | 0x40432d | the path of each Mover3D | flyers only (list `[0x8bf00c]`, component 4) - probably empty in the Yggdrasil units |

Why connectivity / normals need the areas: 0x418680 jumps over the whole per-layer loop (0x416750 -> 0x413250 -> per area
0x40c3a0) unless `planner_areas` or `planner_areas_solid` is set; both are read only inside 0x40c3a0. The answer and the log
line say so.

**Layer mask `[0x88e454]`** (dword, `.data`, file value 0xffffffff; 5 references in the exe: 4 reads in 0x418680, the only
writer 0x48aa23 in the CDC init, which sets `(1 << n) | (1 << (n + 16))`, n = `[0xa03590]`). The planner draws nothing when
it is 0 and layer i (of 32) only when bit i is set. `nav.mask 1` writes the file value 0xffffffff (every layer) and keeps
the value before; `nav.mask 0` / `nav.off` write that value back - unless the game changed the mask meanwhile (then it
stays). The mask is used by nothing but the draw function. `nav.status` lists the layers that hold something (tested as
0x4186bb .. 0x4186cd: bit i, `[[0x8bf310] + 4i] != 0`, `[layer + 8] != 0`), so a missing drawing can be told apart from a
mask that leaves the navmesh layers out.

### Items (TruLink `menu <id> [arg]`, command bar)

| Item | Meaning |
|---|---|
| `nav.draw <switch> [0\|1]` | one switch; no 0 / 1 = flip; no switch = usage + every state |
| `nav.mask [0\|1]` | bool: layer mask = 0xffffffff / the value before |
| `nav.off` | every switch TruMenu wrote back to the value before its first write (0 in retail), then the mask |
| `nav.status` | read-only, any time: `[Debug]`, check results, CDCRenderer / line buffer / NavPower state, mask, layers, every switch |

Guards of every write (as `CheatGate` + `instance.spawn`): `[Debug] Enabled=1`, `[Cheat] Experimental=1`, the byte
checks below, a player instance, main state `[0xe7ed60]` = 1, no level change pending (`GameTracker+0xb9`, main state 2 /
9) - never while loading -, `[0x8c0f3c]` = an object with vtable 0x845224, line buffer `[0x8c0f48]` != 0; per switch at
run time the setting object still pairs name and byte (`[obj]` = 0x841144, `[obj+0xc]` = the name string, the string itself,
`[obj+0x10]` = the byte). The items run on the calling thread (one byte / dword write each; no game function is called).

### Ring level `Spieler/Debug` (TruMenu.radial.txt)

Page 1: Navmesh Flaechen, Navmesh gefuellt, Navmesh Verbindungen, Hindernisse, Nav-Proben, Laufweg (Flieger), Alle Ebenen
(`nav.mask`), Alles aus (`nav.off`); page 2 (RB): Flaechen-Normalen, Debug: Stand (`nav.status`). Each switch shows on /
off: an entry `nav.draw <switch>` (one word) is treated as a bool of that switch byte, the ring sends
`nav.draw <switch> 0|1`. Below `Spieler` so the top level keeps its 8 sectors (as `Spieler/Objekte` in 0.10.5).

### `TruMenu.log` lines

```text
0.12 debug drawing: [Debug] Enabled <0|1> (NavDraw <list|->, NavMask <0|1>), draw path ok, layer mask ok (0x<mask> now), 7 / 7 switches ok
nav.draw <switch> <0|1> (byte 0x<addr> <before> -> <after>; <what it draws>; mask [0x0088e454] = 0x<mask>, layers <n n ..|none|no planner> (0x<bits>), NavPower state <s>; src=<ring|menu|TruLink|[Debug] NavDraw>)[ - <note>]
nav.draw <switch> <0|1> refused - <reason> (src=...)
nav.mask <0|1> ([0x0088e454] 0x<before> -> 0x<after>: <every layer|the value before|...>; layers ...; src=...)
nav.off: <n> switch(es) back to the value before (<names>|-), <n> failed; <mask answer> (src=...)
nav: [Debug] NavDraw / NavMask applied in the first loaded level: <n> ok, <n> failed
```

Notes after `nav.draw`: `draws only together with planner_areas / planner_areas_solid ...`, `layer mask [0x88e454] = 0:
the planner draws nothing (nav.mask 1)`, `no layer that holds a navgraph is in the layer mask (nav.mask 1)`.

### Keys, checks

| Key | Default | Meaning |
|---|---|---|
| `[Debug] Enabled` | `0` | 1 = the nav items may write (ring entries usable) |
| `[Debug] NavDraw` | (empty) | comma list of switches turned on once in the first loaded level (game thread, same guards) |
| `[Debug] NavMask` | `0` | 1 = with NavDraw also `nav.mask 1` |

**Byte checks** (`NavCheck` at load; pinned in `work\asi\menu012\precheck_012.txt`, `tools/pe_bytes_check.py` on the Steam
exe: 33 / 33 ok; `tools/trumenu_precheck_match.py`: the 33 lines = the 33 checks in the source section): the draw path
(CDCRenderer creation 0x48a95f, vtable slot 0, frame calls 0x5da141 / 0x489c68, component loop 0x42f98a, planner
registration 0x4211ad, planner frame draw 0x418870), the mask (its 4 reads + its only writer 0x48aa23), the area chain
(0x4167a4, 0x4132d2), per switch its readers and the static initialiser that stores name and byte into the setting object
(e.g. 0x83098e `c7053cf48b0000268400 c70540f48b00e5f28b00` for `planner_areas`). A failed check greys that switch (or all
of them) with the reason; one log line per disabled switch.

Offline checks: `/W4` 0 warnings in `TruMenu.cpp`; `tools/pe_import_export_diff.py` 0.11 vs 0.12: imports and exports
unchanged; `tools/src_hook_sites_diff.py`: no new hook, patch or VirtualProtect, 1 new raw store (the mask dword), 11 new
byte pre-check lines (= the 33 checks, the table rows run in one loop); `tools/trumenu_ini_check.py` (`[Debug]` values, the
nav items, the nav entries of the radial file: `nav.draw` one switch name of `kNavSwitches`, the others without argument).

**TO TEST (0.12)** - `[Debug] Enabled=1`, `dlc_yggdrasil_hall02`:

1. `TruMenu.log`: `0.12 debug drawing: ... 7 / 7 switches ok`.
2. Ring -> Spieler -> Debug -> Navmesh Flaechen: lines on the floor = the engine drawing works on PC (log `nav.draw
   planner_areas 1 ...`, note the layers and the mask). Nothing: Alle Ebenen, look again; still nothing = the lines do
   not reach the screen (`DRAW_DrawLines` path) - `nav.status` into the log (Debug: Stand).
3. With the areas on: Navmesh Verbindungen, then Nav-Proben near thralls, Hindernisse; frame rate with Navmesh gefuellt.
4. Alles aus: everything gone, log `nav.off: n switch(es) back ...`.

## TruMenu 0.13 "Thrall-Labels" (debug view stage S1, F28)

Built into `work\asi\menu0130` (`menu013` already held an older build from 31.10. and was not touched); compiled, offline
checks only - **not yet seen in the game**. Owner notes (German): `<workspace>\docs\Befund-Thrall-Labels-0511.md`. Off
unless `[Debug] Enabled=1` and `dbg.labels 1` (ring `Spieler/Debug` -> Thrall-Labels, or `[Debug] Labels=1`).

**What it draws.** Every Present while on, in a loaded level only (player instance, main state 1, no level change
pending - the guards of `nav.draw`): for the instances within `[Debug] LabelRadius` of Lara whose object name contains a
part of `[Debug] LabelMatch` (default `thrall`; `*` = every instance), thralls first, then the nearest, at most
`LabelMax`, a label in ImGui's foreground draw list at the projected instance position (+0x20):

* line 1: object name, intro id (+0x58), distance to Lara (game units), `LP <hit points>` for names containing `thrall`
  - EnemyProcessFunc 0x638d40's own value: brain = `[[inst+0x2d0]]+0x2ec` (0x638d59), hit points brain+0x2c64 (the value
  `cheat.enemyhealth` prints at 0x638edd);
* line 2 (only with TruShadowCombat 0.5.3, export `TscTargeterSnapshot`): `Z9 ZIEL` (yellow, targeter 9's target),
  `Z9 Fach <g>` (green, in the bucket of filter group g), `Z9 abgelehnt E0` / `F<xx>` / `(Grund ?)` (orange, in the
  rejected list: eligibility tru+0x2ecca0 failed / filter groups passed as a bit mask / not evaluated yet - the last WHY
  result of TruShadowCombat's diagnostics), `Z9 -` (white, not in targeter 9), ` | H` (in the player's hit list
  `[[0xfadb58]+0x504]+0xa4`), ` | 2011 Pfad <p> q<query> = <result> (<age>s)` (the last condition 2011 had this instance
  as target; path 1 empty / excluded, 2 query 0x161 = 0, 3 ok);
* a magenta cross at Lara's position (`[Debug] LabelCross`, default 1) - the live check of the projection.

No state-chart state id: the only chart machine constructor tru+0x3873c0 has one caller (tru+0x2eff9a, the player's
machines at playerstate +0xf10..); where the thralls' charts run is unknown, so nothing is shown (translate, don't
imitate).

**Projection = the game's own text-at-an-instance path** (EnemyProcessFunc's health text 0x6224e0, not the TRANS matrix
0xa038f0 that `draw.markup` reads - that one holds whatever 0x49f620 set last): matrix = the address the getter 0x5e7890
returns (0xe804a0), projected like TRANS_RotTransPersVectorf 0x49f630 (`x' = m[0] x + m[4] y + m[8] z + m[12]`, ...;
screen `x = x' / z' * f + 256.0`, `y = y' / z' * f + 224.0`, f = `[0x8906d0]`), drawn when `16.0 < z'` (0x62257b).
0xe804a0 is written once per game frame by the camera update 0x5f3df0 (called at 0x5d46a9, right after the instance
walk): a copy of the camera's world -> camera matrix, column x scaled by `(4 / 3) / aspect` (0x5c59f0, aspect =
`[[0xad75e4]+0x170] / 10000`), column y by `448 / 384` (0x5e7b30); `f = 192 / tan(fov / 2)` (0x5f3ef6, tan = 0x813870
with `fptan`, stored by 0x49f610). So the text space is 512 x 448 with a vertical field of view; it is scaled to the back
buffer with `draw.scale` (default 512 448, shared with `draw.markup`). Constants and the derivation: `tools/pe_dis.py`,
`tools/pe_float_consts.py` (new, logs `labels0511_*`).

**Live checks** (cannot be done offline): the magenta cross must sit on Lara's origin (feet); with `cheat.enemyhealth 1`
the game's own `%8.2f` hit points must appear at the anchor dot of a thrall's label (same matrix, same projection); if
the cross is offset by a constant factor, `draw.scale <w> <h>` fixes the text-space size (log line below prints the
matrix, focal, aspect, back buffer and Lara's projected point every 10 s).

### Item, ring, keys

| Item / key | Default | Meaning |
|---|---|---|
| `dbg.labels [0\|1]` | 0 | bool; needs `[Debug] Enabled=1` and the byte checks; may be switched outside a level (draws in the next one) |
| `[Debug] Labels` | `0` | 1 = on from the start (needs `Enabled=1`) |
| `[Debug] LabelRadius` | `3000` | game units, 100 .. 50000 |
| `[Debug] LabelMax` | `12` | 1 .. 32 |
| `[Debug] LabelMatch` | `thrall` | comma list of name parts, `*` = every instance |
| `[Debug] LabelCross` | `1` | the magenta cross at Lara |

Ring `Spieler/Debug`: entry 11 "Thrall-Labels" (page 2), shows on / off. Cost per frame: one walk of the instance list
(position read, distance test; the name test is cached per object id), at most 32 projections and labels; fixed static
buffers, no allocation by TruMenu (ImGui reuses its draw list buffers). TruShadowCombat builds its copy on the game
thread only while TruMenu asked within 2 s.

**Byte checks** (`LabelCheck` at load; pinned in `work\asi\menu0130\precheck_013.txt`, `tools/pe_bytes_check.py` on the
Steam exe: 20 / 20 ok; `tools/trumenu_precheck_match.py --from "---- 0.13 Thrall-Labels" --to "---- favourites"`: 20 =
20): the game's instance-text path (0x5e7890, 0x6224ed, 0x62257b), the camera update (0x5d46a9, 0x5f3e25, 0x5e7b30,
0x5e7b5d, 0x5e7b87, 0x5c59f1, 0x5f3ef6, 0x5f3f19, 0x49f610), the projection and its constants (0x49f6f8, 0x49f702,
0x49f713, 256.0 at 0x843a00, 224.0 at 0x8454c8, 16.0 at 0x8451e4), the health chain (0x638d59, 0x638edd); plus the 0.3
instance-list, player and main-state checks. A failed check disables `dbg.labels` with the reason.

### `TruMenu.log` lines

```text
0.13 thrall labels: checks ok; [Debug] Labels <0|1> (on now <0|1>), LabelRadius <r>, LabelMax <n>, LabelMatch '<list>', LabelCross <0|1>; projection matrix 0x00e804a0, focal [0x8906d0], text space 512 x 448 (draw.scale)
0.13 thrall labels: <TruShadowCombat not loaded | TruShadowCombat without TscTargeterSnapshot (older than 0.5.3) | export found>
dbg.labels <0|1> (src=<ring|menu|TruLink>)
0.13 thrall labels: <n> shown (<k> thralls), <m> in <r> units; TruShadowCombat: <state>; matrix 0xe804a0 rows ...; t ...; focal <f>, aspect [[0xad75e4]+0x170] <a>, back buffer <w> x <h>; Lara (<x y z>) -> screen <sx> <sy>
```

The last line comes with the first labelled frame after `dbg.labels 1` and then every 10 s while on (log only).

**TO TEST (0.13)** - `[Debug] Enabled=1`, TruShadowCombat 0.5.3 (`work\asi\combat053`), `dlc_yggdrasil_hall02`:

1. `TruMenu.log`: `0.13 thrall labels: checks ok`; `TruShadowCombat.log`: `0.5.3 snapshot: TscTargeterSnapshot ... on`.
2. Ring -> Spieler -> Debug -> Thrall-Labels: magenta cross on Lara, a label above each thrall (name, intro id,
   distance, LP). `cheat.enemyhealth 1`: the game's number at the label's dot?
3. Knock a thrall down, stand next to it, power on: line 2 changes `Z9 -` -> `Z9 abgelehnt ...` / `Z9 Fach 0` /
   `Z9 ZIEL`; X / Y at the thrall: `2011 Pfad ...` on its label.

## TruMenu 0.14 "Debug view" (triggers, loading areas, checkpoints, object names; debug view stage S3)

Built into `work\asi\menu014`; compiled, offline checks only - **not yet seen in the game**. Owner notes (German):
`<workspace>\docs\Befund-TruMenu-Trigger-0611.md`. Everything is read-only (no game memory written, no game function
called) and off unless `[Debug] Enabled=1` plus a layer switch. Drawn at Present (background draw list; legend in the
foreground) in a loaded level only - player instance, main state 1, no level change pending, the gates of `dbg.labels`;
nothing about Lara's own state, so it keeps drawing during the 0.8.1 flight (`cheat.flight`, RT up / LT down). Fixed
static buffers, nothing allocated by TruMenu per frame; projection as 0.13 (matrix 0xe804a0, 0x49f630) plus clipping of
every line at the near plane (`z' > 16`), so a box the camera stands in still shows its visible edges.

**Triggers (`dbg.triggers`, per kind `dbg.show <kind>`).** The two lists the game tests every frame (0x5cd520): planes
`[0xdba21c]` / 0xda61c8, volumes `[0xdba220]` / 0xdb6be0 (at most 0x200 each, adders 0x5c8990 / 0x5c89e0); entry +0x20 =
the trigger instance, +0x24 bit 31 = enabled (0x4a4360; disabled entries are skipped by the game and drawn dim), bit 30
= tested against the player (0x4a4450). Data = `[[instance+0x100]+0x78]` (IntroDataTrigger). Drawn the way the engine
tests them:

* volume, shape byte +0x30 = 1 (box): centre = instance +0x20, half extents +0x34 / +0x38 / +0x3c along the rows of
  `M = Rz * Ry * Rx` from the instance Euler angles +0x30 (0x49d500: identity post-multiplied by 0x49bd40 / 0x49bc70 /
  0x49bb90, cos 0x813420 / sin 0x813680; row vectors). The game tests through the quaternion of M (0x49d720) as
  `|conjugate(q) rotated (p - centre)| <= h` (0x46b730, Hamilton product 0x49c940), i.e. corner = centre + (+-h) * M -
  12 lines. `tools/trigger_box_math.py` checks the closed form against those steps (2000 random cases: 0 matrix
  elements off, 16000 / 16000 corners inside at x0.999 and outside at x1.001, 8000 / 8000 plane corners equal; the
  transposed matrix fails as it must);
* volume, shape 2 (sphere): squared distance to instance +0x20 below radius +0x40 squared (0x4355d0) - 3 circles;
* plane (0x5ccc20): the quad `(+-w, 0, +-h) * M + instance +0x20` (0x435220 -> 0x49ba20 adds row 3), w = +0x34,
  h = +0x3c; byte +0x44 = 0 = one-sided (the crossing direction is tested) -> an arrow along row 1 (the quad normal).
  The game tests the segment of the player's test point between two frames against the two triangles (0x461640);
* the test point itself: player +0x20 + (0, 0, 200.0) (`[0x853f08]`) - a white cross.

Kind (colour) from the trigger instance's object name, first match wins: `checkpoint` (green), `death` / `kill` (red),
`fire` / `burn` / `flame` (orange), `water` / `swim` (blue), `sound` / `swoosh` / `audio` / `music` / `sfx` (violet);
no keyword = plain volume (yellow) / plane (cyan); no intro data, unknown shape or no name = unknown (grey). A full
memory dump of DLC 2 (30.10., `dlc_level2_start` + `dlc_yggdrasil_hall01` loaded, `tools/debugview_dump_check.py`) holds 7 planes (`triggerplane`) and 19
volumes (`triggervolume`, `soundvolume`, `soundtriggervolume`), all boxes; the generic names carry no death / fire
meaning there - what a plain trigger does is in its script, which 0.14 does not read. Selection: the triggers nearest to
the camera first, at most `[Debug] TriggerMax` (64) within `TriggerRadius` (20000 units from the camera, so it still works
from high above), names for the nearest `TriggerLabelMax` (`dbg.show trglabels`: object name, intro id, B / K / E1 / E2
= box / sphere / one-sided / two-sided plane, `(aus)` = disabled).

**Loading areas (`dbg.portals`).** Every loaded stream unit (table 0xdbab40, state 2): entry +8 Level, `[Level]`
Terrain, Terrain +2 s16 count, +4 array of 0x100-byte StreamUnitPortal (0x5d295f, 0x5d2ab5); quad corners +0xb0 /
+0xc0 / +0xd0 / +0xe0, normal +0xf0 (layout from the unit DRMs; in the DLC 2 dump the two records of the
`dlc_level2_start` <-> `dlc_yggdrasil_hall01` connection lie on the same quad, normals opposite). White quad, diagonals,
normal arrow, label `<unit> -> <destination>`. What actually starts a unit load is the signal geometry of a terrain group
(0x5d2ca0 -> 0x5d2aa0); the quad is the portal's boundary.

**Checkpoints (`dbg.checkpoints`).** Instances whose object name contains `checkpoint` (`checkpoint`,
`invis_checkpoint`, `dlc2_checkpoint`): a post with a diamond and `CP <intro id>`; the active one (game data
`[0xc59264]` +0x90, +0x114 when the word +0x1f4 is not 0 - the id the player placement 0x5d40c0 uses) in yellow with
`AKTIV`. In the DLC 2 dump: 5 `checkpoint` instances, game data id 9400 = one of them.

**Object names (`dbg.names`).** The object name of every instance from the **live PC object list** `[0xdb94d0]` (via
`[[inst+0x10]+0x14]`, the `ObjectName` / `LabelKind` path - never a name table from the Xbox data), with the intro id
(`[Debug] NameIds`), nearest to the camera first, at most `NameMax` within `NameRadius`; filter `NameMatch` / item
`dbg.namefilter <parts|*>` (ring presets: all, thralls, triggers); font size `NameScale` / `dbg.namesize 0.5 .. 3`;
colour `NameColour` / `dbg.namecolour white|yellow|cyan|magenta|RRGGBB` (menu: colour picker). The 0.13 Thrall-Labels
(`dbg.labels`) stay as they were.

**Legend (`dbg.legend`)**: top right, every layer that is on with its colour and `drawn / found`.

**Master (`dbg.view`)**: on = every 0.14 layer whose checks passed + `dbg.labels` + `draw.markup` + the NavPower
switches of `[Debug] ViewNav` (default `planner_areas,planner_connectivity,obstacles`; these need a loaded level and
`[Cheat] Experimental=1` like `nav.draw`); off = all of them off (`nav.off`). Afterwards every switch works alone; the
value of `dbg.view` is 1 while any of them is on.

### Items, keys, menu, ring

| Item | Type | Meaning |
|---|---|---|
| `dbg.view [0\|1]` | bool | master switch (above) |
| `dbg.triggers [0\|1]` | bool | every trigger kind |
| `dbg.show <layer> [0\|1]` | action | one layer: `death fire checkpoint water sound volume plane unknown` (trigger kinds), `portals checkpoints trglabels legend names` |
| `dbg.portals` / `dbg.checkpoints` / `dbg.legend` / `dbg.names` | bool | the same layers as items of their own (ring on / off) |
| `dbg.namefilter <parts\|*>`, `dbg.namecolour <preset\|RRGGBB>`, `dbg.namesize <f>` | action | object name settings |
| `dbg.status` | info | checks, layers on, what the last frame drew |

`[Debug]` keys (all 0 / off by default): `View`, `ViewNav`, `Triggers`, `TrgDeath`, `TrgFire`, `TrgCheckpoint`,
`TrgWater`, `TrgSound`, `TrgVolume`, `TrgPlane`, `TrgUnknown`, `Portals`, `Checkpoints`, `TrgLabels`, `Legend`,
`Markup`, `TriggerMax` (64, 1 .. 256), `TriggerRadius` (20000, 500 .. 200000), `TriggerLabelMax` (16, 0 .. 64), `Names`,
`NameMatch` (empty = all), `NameRadius` (5000), `NameMax` (24, 1 .. 64), `NameScale` (1.0, 0.5 .. 3), `NameColour`
(FFFFFF), `NameIds` (1), `Persist` (0; 1 = every switch of the debug view - layers, Labels, Markup, NavDraw, name
settings - is written back into `TruMenu.ini` at once; `Set-TruMenu.ps1` then treats the file as owner-edited and keeps
it on updates).

Menu page **"Debug view / Debug-Ansicht (0.12 - 0.14)"**: master checkbox; groups Level data / Leveldaten (triggers
all, loading areas, checkpoints, the eight kinds with colour swatch and drawn / found, trigger names, sliders), AI / KI
(the seven NavPower switches, every layer, Thrall-Labels), Object names / Objektnamen (switch, filter text + presets,
radius, max, font size, colour picker + presets, intro id), Lara (markup, ledges), Display / Anzeige (legend, Persist
note). Ring **`Spieler/Debug`**: `Alles an / aus` (dbg.view), folders `Leveldaten` (12 entries, 2 pages), `KI` (the
0.12 NavPower entries + Thrall-Labels, 10 entries, 2 pages - moved from `Spieler/Debug`), `Namen` (11, 2 pages),
`Lara` (markup), then `Legende`, `Debug: Stand` (dbg.status), `Navmesh: Stand` (nav.status). Every switch shows on / off.

**Byte checks** (`DebugViewCheck` at load; pinned in `work\asi\menu014\precheck_014.txt`, `tools/pe_bytes_check.py` on
the Steam exe: 68 / 68 ok; `tools/trumenu_precheck_match.py --from "---- 0.14 Debug view" --to "---- favourites"`: 68 =
68): trigger lists, loop and adders (0x5cd527 .. 0x5c89f1), the enabled / player bits (0x4a4360, 0x4a4450), the volume
test (test point lift, data chain, shape, extents, radius, branches, 0x4355d0), the box test (0x46b75f .. 0x46b7c6,
0x49cdce, 0x49cdea, 0x49c987), the Euler matrix (0x49d50b .. 0x49d63f, constants 0.0 / 1.0, fcos / fsin, the three
axis rotations), the quaternion (0x49d720), the plane test (0x5ccc40 .. 0x5ccf55, 0x435259, 0x49ba20 / 0x49ba4b), the
portal walk (0x5d295f, 0x5d2a48, 0x5d2ab5, 0x5d2aca), the checkpoint game data reader (0x5d41df, 0x5d4214) and names
(0x85512c, 0x855118); plus the 0.13 projection checks and the 0.3 instance / player / main-state checks. A failed group
disables its layers with the reason (`dbg.status`, greyed ring entries).

### `TruMenu.log` lines

```text
0.14 debug view: triggers <ok|why>, portals <ok|why>, checkpoints <ok|why>, object names <ok|why>; [Debug] View <0|1>, Triggers <0|1>, <n> layer(s) on now, Markup <0|1>, ViewNav '<list>', TriggerMax <n>, ...
dbg.show <layer> <0|1> (src=<ring|menu|TruLink>)      dbg.triggers <0|1> (all 8 kinds, src=...)
dbg.view <0|1>: <n> layer(s), labels: <answer>, markup: <answer>, nav: <switch on|refused, ...> (src=...)
0.14 debug view drawn: triggers <n> drawn (box b, sphere s, plane p) of <m> listed, <k> off-screen, ...; portals ...; checkpoints ...; names ...
```

The `drawn` line is written once with the first frame after a switch (no per-frame logging).

**TO TEST (0.14)** - `[Debug] Enabled=1`, a loaded level (e.g. Croft Manor `l3_*` via the level select):

1. `TruMenu.log`: `0.14 debug view: triggers ok, portals ok, checkpoints ok, object names ok`.
2. Ring -> Spieler -> Debug -> `Legende`, then Leveldaten -> `Trigger alle`, `Ladebereiche`, `Checkpoints`: boxes /
   quads where doors, rooms and corridors are; the white cross 200 above Lara; walking into a box triggers what it
   should (the box is where the game tests).
3. `cheat.flight 1`, RT up, look down; `Alles an / aus`: everything stays drawn from above, the nearest first.
4. Namen -> `Objektnamen`, `Filter: alle`, `Farbe gelb`, `Schrift 1.5x`.

Fixed in 0.15: in 0.14 the Present hook returned before the ImGui frame unless the menu / ring was open or labels /
markup were on, so a 0.14 layer disappeared as soon as the ring closed (`DvAnyOn()` is now part of that test).

## TruMenu 0.15 "Render mode" (render census, flat view, collision overlay; debug render stages R0 / R1 / R2)

Built into `work\asi\menu015`; compiled, offline checks only - **not yet seen in the game**. Owner notes:
`<workspace>\docs\Befund-TruMenu-Rendermodus-0611.md` (research: `docs\Befund-Debug-Rendermodus-0611.md`). Off unless
`[Debug] Enabled=1` plus a switch. The renderer is Crystal's cdc PC renderer (RTTI): `cdc::PCTerrainDrawable` (vtable
0x849944) and `cdc::PCModelDrawable` (0x849754) have `Draw` in slot 1 (0x510dd0 / 0x50f4a0, thiscall `(pass,
previous drawable)`, `ret 8`), called by the draw list 0x4f6080 for the pass ids 1, 2, 0x80, 0x100, 0x200, 0x400, 0x800
(`PCScene::Draw` 0x5150e0 hands its lists over in the order 0x200, 0x100, 0x80, 0x800, 0x80). The device is created
PURE (0x522687: behaviour flags 0x50), so TruMenu asks the device for no state: the game's state manager
`[[0xad75e4]+0x284]` (device at +0xc) keeps the pixel shader it set at +0x20 (0x526630; the `IDirect3DPixelShader9` at
PCPixelShader +0xc) and every render state at `+0x168 + 4 * state` (0x502b70).

**R0 census (`dbg.census [frames]`).** For N frames (`[Debug] CensusFrames`, 120) TruMenu counts per pass id and class
(terrain / model) the drawable calls and their device draws, render target 0 (pointer, size, format; up to 3 per pass),
RT1 bound, and from the state manager's cache Z, Z write, alpha test, alpha blend and colour write 0 per draw, the
material pass `[0x8a2340]`, plus the `PCScene::Draw` calls per frame (render target at entry) and the device draws
outside a drawable. Then **one block** of `0.15 census` lines in `TruMenu.log`, a verdict per pass (colour candidate /
no colour writes / other target size / blended) and the suggested pass mask (passes drawn into a target of the back
buffer's size with colour writes and mostly without blending). `dbg.flatpasses census` takes it over.

**R1 flat view (`dbg.flat`).** Inside the terrain (and with `dbg.flatmodels` the model) `Draw` of a pass in
`[Debug] FlatPasses` (default 0x200, the first opaque list - a guess until the census), every device
`DrawIndexedPrimitive` / `DrawPrimitive` draws with one of 16 palette pixel shaders, then the game's own pixel shader is
set again at once (state manager +0x20), so the state manager's cache and the device stay equal. Colour = hash of the
current material `[0xa14188]` (`dbg.flatcolour material`) or terrain one colour / models another (`class`). The palette
shaders are built from tokens at run time (`def c0, r, g, b, 1` + `mov oC0, c0`, no constant register written) as
ps_2_0 and ps_3_0; the version of the game's shader of that draw picks the set (a vs_3_0 needs a ps_3_0 and the other
way round; `GetFunction` once per game shader). `tools/trumenu_flat_ps_check.py` disassembles all 34 with the Windows
`d3dcompiler_47.dll` and compares the HLSL compiler's own ps_2_0 / ps_3_0 output (same tokens without its comment
block). Edge pass (`dbg.flatedges`): the same draw again in wireframe with a dark shader, depth bias -0.00005 / slope
-1, Z write off; fill mode, depth bias and Z write come back from the state manager's cache. By default only into a
render target of the back buffer's size (`dbg.flatanyrt` / `[Debug] FlatAnyTarget=1` = every target), so shadow maps
and reflections keep the game's shading even with a wrong pass mask. Water, effects, HUD are other classes - unchanged;
fog / DOF still tint the result. **Not part of `dbg.view`** (a big separate switch; the master covers the overlays).

**Writes into game memory (R0 / R1 only, TruGuard).** Only while the census runs or the flat view is on, in a loaded
level (player instance, main state 1, no level change pending): `.rdata` words **0x849948** (PCTerrainDrawable::Draw,
game value 0x510dd0) and **0x849758** (PCModelDrawable::Draw, 0x50f4a0), during a census also **0x849a2c**
(PCScene::Draw, 0x5150e0). A word is written only while it holds the game's value (else refused with a log line),
`WriteDword` = VirtualProtect + interlocked store + VirtualProtect back; it is put back (only while it still holds
TruMenu's hook) when switched off, when the level is left or a level change starts, when the census ends and at unload.
The same for the game device's vtable slots 81 / 82 (`DrawPrimitive` / `DrawIndexedPrimitive`, memory of d3d9.dll or of
a proxy such as TRAWindowed, not of tru.exe). Everything is patched / unpatched in the Present hook, between two frames.
The palette shaders are created on the game's device in the Present hook and released in the Reset hook (created again
at the next Present).

**R2 collision overlay (`dbg.slide`, `dbg.enemycoll`; layers `slide` / `enemycoll` of the 0.14 table, part of
`dbg.view`).** Read-only. The collision meshes of every loaded stream unit: table 0xdbab40 (state 2) +8 Level,
`[Level]` Terrain, +8 group count, +0xc TerrainGroups (0x50 bytes), group +0x38 mesh - taken only when mesh +0x3c points
back to the group (0x48d2d4 reads it that way); faces 20 bytes at mesh +0x34 (count +0x44), vertices at +0x30 (mesh +0x54
word 0: 3 x s16 converted without a scale, else 16-byte floats - 0x460770 / 0x460690 / 0x460824), world = vertex + mesh
+0x20 (the mesh query 0x78d040 subtracts it). Read once per change of the loaded units into a static buffer (24576
triangles, no allocation), drawn as translucent triangles with edges through the 0.14 projection (near plane clipped),
the nearest to the camera first (`[Debug] CollRadius` 8000, `CollMax` 3000), **on top** (no depth test - visible
through walls). Slide = clientFlags (face +0x0e) & 0x04 (0x5d3af0 / ground probe 0x5dd356): **red** when steeper than
the tuning angle s16 `[[0xfad764]+0x100e]` degrees (0x5dd3ba: the game slides only then), **orange** when flatter.
Enemy-only = TerrainGroup extra flags (`[group +0x30]` +0) & 0x800, **violet**: the name is TRLAU's; in tru.exe the
collision filter 0x48d2d0 (collide kinds 7 and 4, registered at 0x4964eb / 0x4964ff) skips such groups and the filter
0x48d280 of kind 3 does not - which kind is the player's is not proven. A `0.15 collision: read ...` line per reading.

### Items, keys, menu, ring

| Item | Type | Meaning |
|---|---|---|
| `dbg.census [frames]` | action | R0: one census of N frames (10 .. 1200), result in `TruMenu.log` |
| `dbg.flat [0\|1]` | bool | R1 flat view |
| `dbg.flatpass <0x200\|0x100\|0x80\|0x400\|0x800\|1\|2> [0\|1]` | action | one pass id in / out of the mask (live) |
| `dbg.flatpasses <mask>\|census\|default` | action | the whole mask (`census` = the last census' suggestion) |
| `dbg.flatcolour material\|class` | action | colour per material, or terrain / models |
| `dbg.flatmodels`, `dbg.flatedges`, `dbg.flatanyrt` | bool | models flat too, edge pass, every render target |
| `dbg.render` | info | checks, patched slots, last frame (flat draws, skipped), census state / suggestion |
| `dbg.slide`, `dbg.enemycoll` (also `dbg.show slide` / `enemycoll`) | bool | R2 overlay layers |

`[Debug]` keys (0 / off by default): `Slide`, `EnemyColl`, `CollRadius` (8000, 500 .. 200000), `CollMax` (3000, 100 ..
20000), `Census` (1 = one census in the first loaded level), `CensusFrames` (120, 10 .. 1200), `Flat`, `FlatPasses`
(0x200), `FlatColour` (material / class), `FlatModels`, `FlatEdges`, `FlatAnyTarget`. With `Persist=1` the switches are
written back as the 0.14 ones.

Menu page "Debug view": new group **Render (0.15)** at the top (flat view, census button + state, one checkbox per pass
id, census suggestion / default buttons, colour mode, models, edges, every target, state line); `slide faces` in Level
data (after checkpoint objects) with the sliders CollRadius / CollMax, `enemy-only collision` in AI / KI. Ring
`Spieler/Debug`: `Render` as the second entry (page 1: Flach-Ansicht, Render-Zaehlung, Kanten, Figuren einfaerben,
Farbe: Material, Farbe: Terrain / Figuren, Jedes Ziel (auch Schatten), Render: Stand; page 2: Pass 0x200 .. Pass 2,
Passe aus Zaehlung), `Rutschflaechen` in Leveldaten (4th), `Gegner-Kollision` in KI (5th); `Navmesh: Stand` moved to
page 2 of `Spieler/Debug`.

**Byte checks** (`RenderModeCheck` at load; `work\asi\menu015\precheck_015.txt`, 46 / 46 ok on the Steam exe;
`tools/trumenu_precheck_match.py --from "---- 0.15 Render mode" --to "---- favourites"`: 46 = 46): R0 / R1 (27) - the
three vtable words, the constructors' stores, the draw list call, the Draw heads / tails, the terrain pass dispatch, the
device draw sites (vtable +0x148), the scene's list dispatch, the state manager getter / SetPixelShader / SetRenderState
wrappers, the material pointer / pass globals; R2 (19) - face clientFlags reader, ground probe masks, tuning angle
reader and pi / 180, mesh query / vertex fetch (both vertex formats), the collision filters and their registration. A
failed group disables its part with the reason (`dbg.render`, greyed ring entries).

### `TruMenu.log` lines

```text
0.15 render mode: census / flat view <ok|why>, collision overlay <ok|why>; [Debug] Flat <0|1> (passes ..., colour ..., models, edges, any target), Census .., Slide .., EnemyColl .., CollRadius .., CollMax ..
dbg.flat <0|1> (passes 0x200, colour material, models 0, edges 0, any target 0; src=...)   dbg.flatpass 0x100 1 (mask now 0x300; src=...)
0.15 flat view: 34 palette pixel shaders created (17 ps_2_0 + 17 ps_3_0) on device 0x........
0.15 render mode patched (flat view): +PCTerrainDrawable::Draw 0x00849948 (0x00510dd0 -> TruMenu), +PCModelDrawable::Draw ..., +device DrawIndexedPrimitive (82) ..., +device DrawPrimitive (81) ...
0.15 render mode unpatched (<why: not while loading / flat view off / census done>): -PCTerrainDrawable::Draw 0x00849948, ...
0.15 flat view drawn: flat 1 (passes ...), slots 0x1b; last frame: <n> drawable calls, <n> flat (terrain .., model ..), <n> without game shader / version, <n> other pass, <n> other target
0.15 census started: 120 frames, back buffer 1920x1080
0.15 census (done): 120 frame(s), back buffer ...; PCScene::Draw <f> per frame (render target 0 at entry: ...); device draws outside a drawable ...
0.15 census pass 0x200: terrain .. calls / .. DIP .. DP, model ..; per draw Z ..%, Z write ..%, alpha test ..%, blend ..%, colour write 0 ..%, RT1 bound ..%; [0x8a2340] ... -> colour candidate
0.15 census pass 0x200: render target 0 0x........ 1920x1080 fmt 21 (n), ...
0.15 census: suggested [Debug] FlatPasses=0x... (...) - 'dbg.flatpasses census' sets it; now 0x200
0.15 collision: read <n> unit(s), <n> mesh(es) (...), <n> faces: <n> slide (clientFlags 0x04), <n> in <n> enemy-only group(s) ...
```

No line per frame: the `drawn` line once after a switch, patch / unpatch lines only when the slots change (switch,
level change), the census block once, the collision line once per reading of the loaded units.

## TruMenu 0.16 "Readability" (debug view after the first live run, 2026-11-06)

Owner feedback from the first live run of 0.15 in the Croft Manor prologue: it works, but it is hard to read (lines
over Lara and through walls, labels on top of each other, legend cut off, huge enclosing volumes, the active checkpoint
marker filling the foreground, 15 triggers silently missing at TriggerMax 64). Workspace report
`docs\Befund-TruMenu-Lesbarkeit-0611.md`; byte checks `work\asi\menu016\precheck_016.txt` (17, section
"---- 0.16 depth" of `TruMenu.cpp`); offline math `tools/trumenu_readability_check.py`.

* **Depth** (`dbg.depth off|on|dim`, `[Debug] Depth` 0 / 1 / 2, default 0): with 1 / 2 the lines and faces of every
  debug view layer are not drawn by ImGui at Present but kept in a world-space buffer and drawn by TruMenu inside the
  next frame, right after `PCScene::Draw` returned (vtable word 0x849a2c - the 0.15 census slot, patched while Depth is
  on and a layer is on), into the render target / depth surface the scene left bound: pre-transformed vertices, x / y
  from the 0.14 projection, z from the scene's own projection `[scene+0x100]` applied to the depth (after checking that
  the scene's view `[scene+0x140]` gives the same depth as the 0.14 camera), Z test on, Z write off. `dim` draws the
  hidden parts first at `DepthDim` % with the inverse test. Only a scene without its own target object
  (`[scene+0x1c0]` = 0), render target 0 of the back buffer's size and a depth surface; `DepthCall` picks the n-th such
  scene of a frame. Device state through a `D3DSBT_ALL` state block (captured before, applied after - as ImGui's DX9
  backend), own dynamic vertex buffer (released in the Reset hook). If anything does not fit, that frame draws as
  Depth 0 (lines on top) and `dbg.style` / the legend say why. Labels and the legend stay on top (ImGui).
* **Style**: `[Debug] LineAlpha` (60 %, `dbg.alpha`), `LineBright` (100 %, `dbg.bright`), distance fade `Fade` /
  `FadeStart` 2000 / `FadeEnd` 10000 / `FadeMin` 20 % (`dbg.fade`), faint faces `Fill` / `FillAlpha` 10 % (`dbg.fill`,
  default off) - for every 0.14 / 0.15 overlay (triggers, loading areas, checkpoints, collision faces).
* **Labels**: trigger, loading-area and checkpoint labels are candidates drawn at the end of the frame, nearest first,
  at most `ViewLabelMax` (10), each nudged up / down or skipped when it overlaps one already drawn or the legend;
  coincident triggers (same kind, centres within 25 units) get one label `TV x3 (4535..4537)`, both directions of one
  loading area `a <-> b`. `LabelShort` (`dbg.short`, 1): `TV 4463`, `TP 4129`, `FIRE 4492`, `-> main_bedroom`; the nearest
  label and the one nearest to the screen centre keep the full text. Every label (also `dbg.names`) shows the distance
  to Lara and the height difference in game units (`6100u v1500u`) and the owner unit when it is not Lara's
  (`[mansion_exterior_afterburn]`, from the loaded unit whose intro array holds the instance's intro). Dark background
  box, text in the kind's colour, anchored at the top centre.
* **Lara in** (`dbg.larain`, `[Debug] LaraIn` 1): the point the engine tests (Lara +0x20 + 200 up) against every listed
  trigger with the engine's math; the containing ones bold with a pulsing white outline, the legend line
  `Lara in: triggervolume 4537` (3 names, then +N; "(aus)" / "(nicht Spieler)" when the engine would skip the entry).
  Planes: "near" within 50 units (the engine tests a crossing). The engine keeps no inside flag of its own (0x5cd1b0
  returns 0 / 1 / 2 / 3 = out / inside / enter / exit from the old and the new position every frame).
* **Clutter**: boxes around the camera, or big ones (`EnclosingSize` 1500) around Lara, dim + dashed
  (`dbg.enclosing normal|dim|hide`, `[Debug] Enclosing` 1); `ViewSkip` (default `sound`) = layers `dbg.view` / `View=1`
  leave off; checkpoint markers at most `MarkerMax` (8 %) of the screen height; `TriggerMax` 256 (was 64, 1 .. 512).
* **Legend**: fully inside the screen, right-aligned, as wide as its text, counts (drawn / found) in their own column,
  colour squares at the right edge; extra rows `GEKAPPT / capped` (warning colour) when TriggerMax cuts, `Lara in`,
  enclosing count, depth state.
* **Ring**: `Spieler/Debug` page 1 Alles an / aus, **Fliegen** (`cheat.flight`), **Darstellung**, Render, Leveldaten, KI,
  Namen, Lara; page 2 Legende, Debug: Stand, Navmesh: Stand, Flug-Tempo 10 / 20 / 40 (`cheat.speed`).
  `Spieler/Debug/Darstellung` (17 entries, 3 pages): Tiefe an / gedimmt / aus, Deckkraft 100 / 60 / 35, Ferne blasser,
  Flaechen fuellen | Kurze Namen, Lara drin markieren, Heller / normal / Dunkler, Umhuellende blass / aus / normal |
  Darstellung: Stand. Menu page "Debug view": new first group "Display / Darstellung (0.16)" (legend and Persist note
  moved there).
* **Script prints into TruMenu.log** (`log.scriptfile`, `[Log] ScriptToFile`, default 0; checkbox on the Log page): with
  `log.script` on, every script line also as `script: <text>` in `TruMenu.log` - at most `[Log] MaxLinesPerSecond` per
  second (the rest counted: `script: <n> line(s) dropped`), a line repeated at once is counted (`script: (last line x N
  more)`, at the latest every 10 s) instead of written again. Note: the log page tails `TruMenu.log` too, so such a line
  shows there once as `script` and once as `TruMenu`.

Writes into game memory added by 0.16: the vtable word 0x00849a2c (`PCScene::Draw`, 0x005150e0 -> TruMenu) now also
while Depth is 1 / 2, a debug view layer is on and a level is loaded (same rules, same log lines as the 0.15 census:
written only while it holds the game's function, put back at off / level change / unload). Device calls inside the
frame (render thread, after the game's scene Draw): CreateStateBlock / Capture / Apply, SetViewport, SetFVF,
SetStreamSource, Set(Vertex|Pixel)Shader(NULL), SetTexture(0, NULL), 30 SetRenderState, 7 SetTextureStageState,
DrawPrimitive, GetRenderTarget / GetDepthStencilSurface; CreateVertexBuffer once per device.

```text
0.16 readability: depth <ok|why>, Lara in <ok|why>, owner units <ok|why>; [Debug] Depth off (DepthDim 25, DepthCall 0), LineAlpha 60, ...
dbg.depth on (DepthDim 25, DepthCall 0; src=ring)
0.15 render mode patched (depth lines (0.16)): +PCScene::Draw 0x00849a2c (0x005150e0 -> TruMenu)
0.16 depth: vertex buffer created on device 0x........ (6144 vertices, dynamic, default pool)
0.16 depth drawn: an (scene 0 of 1 qualifying, 3 calls; row vectors, z LESSEQUAL, z(16.5) 0.0000; 812 lines, 0 faces)
0.16 depth waits (180 frames): wartet, Linien oben / waits, lines on top: <why> (.. scene calls, .. qualifying)
```

## TruMenu 0.17 "Schnellschalter" (quick-toggle bar, cutscene shots, depth diagnosis, checkpoints, positions; 2026-11-06)

A third control next to the long menu and the ring, for switching the debug view while playing, plus the live findings
of 0.16. Workspace report `docs\Befund-TruMenu-Schnellschalter-0611.md`; byte checks `work\asi\menu017\precheck_017.txt`
(6, section "// ---- 0.17 quick toggles ----" .. "// ---- 0.3 pages ----"); offline models `tools/trumenu_quick_check.py`.

* **Schnellschalter** (`quick.open`, `[Quick]`): a small panel at the LEFT screen edge (`Top` % of the height), the game
  keeps running - no freeze, no neutral pad. **View + Start** (`OpenButtons` 0x0030) opens / closes it; D-pad up / down
  = row, left / right = off / on (value rows: one step down / up), LB / RB = page; a held direction repeats after 400 ms.
  While it is open only D-pad, LB and RB are kept from the game (masked in the state PadHook hands the game; one held at
  the close stays away until released). The combo itself never reaches the game: a lone View / Start is held back for
  `ChordMs` (250); released inside that window the game gets it as a 100 ms tap at once, held longer it gets it late.
  Why View + Start: every pad button is bound in the PC input map (generalbank DTP 47, `tools/input_map_find.py`):
  D-pad and LB / RB are gameplay, L3 + R3 is TruMenu's own menu / ring combo; View and Start are menu buttons (pause /
  PDA, actions 9 / 10 / 71 / 89 in set 0) and no binding uses both together.
* Pages (the menu / ring group order): **Debug** (Alles an / aus, Legende, Fliegen, Flug-Tempo, Zwischensequenz-Fotos,
  Sprache), **Darstellung** (Tiefe, Deckkraft, Helligkeit, Ferne blasser, Flaechen fuellen, Kurze Namen, Lara drin,
  Umhuellende), **Render** (Flach-Ansicht, Pass, Zaehlung, Rutschflaechen, Gegner-Kollision), **Leveldaten** (Alle
  Trigger, Tod, Feuer, Checkpoint-Trigger, Wasser, Ton, Trigger, Ebenen, Unbekannt, Ladebereiche, Checkpoints,
  Trigger-Namen - the start page), **KI / Namen / Lara** (Thrall-Labels, Objektnamen, Markup, Nur Kanten) and
  **Checkpoints** (the nearest 14, marker off / on). Rows in their layer colour with the count drawn in the last frame;
  greyed rows say why. Every row runs the existing item (`dbg.show`, `dbg.depth`, `dbg.alpha`, `cheat.flight`, ...)
  through the ring's path and reads its state the ring's way - no state of its own. One `quick: <page> / <row> ->
  <item> <arg>: <answer>` line per action. Closed: one line `Debug: N an` (`ShowClosed`, with `[Debug] Enabled=1`, in a
  level). `quick.lang de|en` / `[Quick] Language` (TruMenu has no global language switch).
* **shot.oncine** (`[Shot] OnCine*`, ring Spieler / Debug): when a cutscene starts in a level - the game's cinematic
  test 0x453f00 or the camera leaving the gameplay camera `[0xe804f0+0xb80]` (`OnCineSignal` both) - pairs of shots, a
  clean one and a ui one of the same Present (`cine<NN>_<i>_clean / _ui`): the first `OnCineFastPairs` (4) every
  `OnCineIntervalMs` (1500), then every `OnCineSlowMs` (5000), at most `OnCinePairs` (10). The cutscene ends when the
  signal has been gone for 2 s (camera flips inside a cutscene keep one burst); pairs have their own MaxPerMinute window.
* **Depth diagnosis** (live: `[scene+0x140]` never mapped): `dbg.depthdump` writes one block per PCScene::Draw call of
  the next frame (scene +0xe0 .. +0x1fc, the 0.14 camera, 0xa038f0, five test points against six view forms);
  `DpMapping` now tries six view forms (row / column, camera-relative, of the inverse) with a least-squares scale over
  five test points, |k| = 1 first, and needs the projection to span half the depth range; `[Debug] DepthCall` -1 (new
  default) = the first qualifying scene that maps.
* Ring entries that set a value show the current one ("= an (wartet)", "jetzt 60%"), switches show an / aus.
* Legend in short English terms (`Death`, `Fire`, `Checkpoint trg`, ..., `CAPPED`, `Lara in: ...`, `Depth: on (waits)`);
  labels whose anchor lies outside the screen are skipped (they were pinned to the screen edges).
* **Checkpoint list** (`dbg.cp <id> 0|1`, `dbg.cpall 0|1`, `dbg.cplist`, `dbg.cpgo <id>|active`, `[Debug]
  CheckpointHide`): menu page Debug view, the bar's page Checkpoints, ring Leveldaten.
* **Positions** (`pos.save [name]`, `pos.list`, `pos.go <name>|last`, `TruMenu.positions.txt` next to tru.exe): unit,
  live position, yaw, the unit's shift P and origin V; `pos.go` only while that unit is loaded, converted with its shift
  then and now (live = data - V + P), otherwise refused with the reason.

```text
0.17 quick toggles: [Quick] Enabled 1, OpenButtons 0x0030 (Start + View), ChordMs 250, ... cutscene shots: camera checks ok, cinematic test ok, ...
0.17 checkpoint list: 0 marker(s) hidden ([Debug] CheckpointHide); positions: ok, file <game>\TruMenu.positions.txt
quick: opened (pad 0: Start + View)
quick: Leveldaten / Tod -> dbg.show death 1: ok dbg.show death 1
shot.oncine: cutscene 01 start - camera left [manager+0xb80]; camera 0x00e80de0 (other, vtable ...); main state 1; ...
shot.oncine: cutscene 01 end (gameplay camera back 2 s) - 7 pair(s) taken, 0 refused; 21.4 s
0.17 depthdump frame 1234 call 0: scene 0x........ - qualifying; [scene+0x1c0] 0x00000000; target 1920x1080 (...)
```

## TruMenu 0.18 (Lara in overlay, owner units, cutscene segments, bar pages, save.load; 2026-11-06)

Lukas' live wishes after 0.17 plus the found bugs. Workspace report `docs\Befund-TruMenu-018-0611.md`; byte checks
`work\asi\menu018\precheck_018.txt` (33, section "// ---- 0.18 save.load" .. the next "// ======" line); static load-path
research `logs\r18_load_*.txt` (workspace).

* **Lara in** (`overlay.larain`, `[Menu] OverlayLaraIn` 1): the position overlay (top left) has a second line
  `Lara in: triggervolume 4537, ...` - up to 3 names (most dangerous kind first) and `+N`, each in its kind's colour
  (death red, fire orange, checkpoint green, water blue, sound violet, trigger yellow, plane cyan, unknown grey). It is
  computed every 100 ms from both trigger lists with the 0.16 test (player +0x20 + (0, 0, 200); box / sphere inside,
  plane within 50 units), whether a trigger layer is drawn or not. The legend's row is gone (`[Debug] LegendLaraIn` 1
  brings it back); the pulsing outline of `dbg.larain` stays.
* **Owner units**: stream table names come in two spellings (`L3_main_bedroom` from the new-game start data,
  `l3_main_hall` from a portal) - the label prefix cut is case-insensitive now, Lara's stream entry is found in the
  whole table (0.16 stopped after 16 units), GameTracker+0x38 is the fallback when no loaded entry has Lara's id; one
  `0.18 units:` log line when the two names differ.
* **shot.oncine segments** (`[Shot] OnCineSegments` 1): inside a running cutscene a new segment with its own pair budget
  starts when GameTracker+0x38 changes, the cinematic object `[0xe7f1c0]` / its track +0x2c changes, or a script prints
  `StartCinematic called` / `Cine about to play` (with `log.script`); at least 1 s per segment. `OnCineSlowMs` 8000 (was
  5000): 4 pairs every 1.5 s, then every 8 s up to 10 per segment (~54 s). Names `cine<NN>_<i>` / `cine<NN>s<k>_<i>`;
  log lines per segment and one summary per cutscene.
* **Quick-toggle bar: 10 pages** - Notfall / Cheats, Lara (+ the saved positions), Debug / Darstellung, Leveldaten
  (start page), Render / KI, Zeit / Test, Checkpoints, Saves, Kapitel (debug), Barrierefreiheit. New row kinds: info
  (right = the item's value in the footer), choice (left = next choice, right = run: weapons, Claude marks), heading,
  planned (greyed, right = what it will do). Dangerous rows need a second right press within 3 s (die, unit reload,
  chapter loads, checkpoint go, "load + go" of a position); restore / load keep the 0.9 double confirmation (10 s).
  Long pages scroll with the selection.
* **save.load** `<save>|autosave` (`[Saves] DirectLoad` 1; menu Saves page "Load" + CONFIRM, bar page Saves, never over
  TruLink, never in the ring): the game's own load path - `0x788a50()`, `0x789de0(index)`, step index `[0xfaf7a4]` = 2
  (TruMenu's confirmation replaces the game's yes / no box); the game then reads the file, runs `SAVE_RestoreGame` and
  changes the level. Only in a level (main state 1, no level change pending), with the save system idle and the name in
  the game's own list (index by name; Autosave = 0x38). Runs on the game thread; while it runs `LevelChangePending`
  says so. Not seen live yet.
* **pos.goload** `<name>|last`: level.load of the position's unit when it is not loaded, then `cheat.flight 1` and
  `pos.go` (the 0.8.1 shortcut runner waits for the level). Explicit only; a level.load may change story state.
* **Kapitel (debug)**: one bar row per chapter start the game's level select uses (`L1_seatop`, `L2_cliffclimb`,
  `L3_caverns_start`, `L4_trailstart`, `L5_startsnow`, `l6_ship_exterior`, `L7_thin_ice` - generalbank script (8, 119))
  plus the prologue `l3_main_bedroom` and the DLC starts; right twice = `save.backup kapitel`, then `level.load` - no
  story value is set.
* **Barrierefreiheit** (skeleton): menu page, ring level Spieler / Barrierefreiheit, bar page - the five categories of
  the game paper (Sehen / Hoeren / Verstehen / Steuerung / Sonstige); working assists only (Zeitlupe 0.5 / 0.75 / 1,
  Befreien, Befreien: Stand, Unverwundbar, Gott voll), everything else greyed "geplant".

```text
0.18 save.load: ok ([Saves] DirectLoad 1; 33 byte checks)
0.17 quick toggles: ... 10 pages (0.18), 82 item rows + 10 planned, 0 unknown item(s); ... segments 1)
shot.oncine: cutscene 01 segment 2 start - unit l3_main_hall -> l3_mansion_exterior_afterburn; unit ...; up to 10 pair(s)
save.load: 'Slot 2' (list index 1) loading - 0x789de0 = 1, step 2 set; Lara was in l3_main_hall
save.load: 'Slot 2' loaded - unit l4_trailstart (14.2 s)
```

## TruMenu 0.19 "Dumme KI" (enemies ignore Lara; 2026-11-06)

Workspace finding `docs\Befund-Gegner-Wahrnehmung-0611.md` (one brain class for every AI enemy, one perception list),
report `docs\Befund-TruMenu-019-DummeKI-0611.md`; byte checks `work\asi\menu019\precheck_019.txt` (33, section
"// ---- 0.19 dumb AI" .. the next "// ======" line).

* **`ai.dumb`** `off|all|sharks|spiders|thralls|filter [0|1]` or `list <name parts>` (`[AI] Dumb` 0 / 1 / 2,
  `[AI] DumbFilter`): every AI enemy, or those whose object name contains a part (sharks `shark`, spiders
  `spider,tarantula`, thralls `thrall`, filter = the INI list), ignore Lara. One setting at a time - switching a group
  on replaces the other; `<preset> 0` only switches off its own active setting; `""` / `1` bring the last one back.
  Not AI enemies (no effect): jellyfish, kraken, Natla, `natla_thrall` (DLC 2).
* **Method** (`ai.mode`, `[AI] DumbMode`): `purge` (default, stage A, no code patch) - once per game frame (PadHook,
  game thread) every enemy in scope gets each sense slot that holds Lara reset with the engine's own `0x65a140` (the
  function `EnemySense::DoProcess` calls when a target is gone). Lara can be sensed again by the scan of the same frame;
  whether that is enough is the first live question. `gate` (stage B) - only while `ai.dumb` is on in a loaded level:
  the rel32 of the calls `0x6648bb` / `0x659d8f` / `0x664a64` (AddToSenses) and `0x623e5f` (noise override) and the
  EnemySense vtable slot `0x85a2fc` lead through TruMenu, which passes everything except Lara for an enemy in scope;
  patched / put back on the game thread, all or nothing, only over the game's bytes; back when off, at a level change
  and at unload.
* **`ai.noinvestigate` / `ai.noattack`** (`[AI] NoInvestigate` / `NoAttack`): the prototype's flags rebuilt as brain+8
  bits - 0x80 (Investigate), 0x20 (Attack / ScriptAttack) + 0x100000 (Melee); set once per frame for the enemies in
  scope (the ai.dumb filter, else every AI enemy), only TruMenu's bits are cleared again. `ai.noattack` is partial
  (close / ranged combat states not checked).
* **Where**: ring Spieler / Debug / KI (8 entries) and Spieler / Barrierefreiheit (Haie / Spinnen ignorieren Lara),
  quick-toggle bar Render / KI (heading + 9 rows, count = enemies in scope), Notfall ("Gegner ignorieren Lara"),
  Barrierefreiheit (Sonstige: the planned row "Haie" is now "Haie ignorieren Lara", plus "Spinnen ignorieren Lara"),
  menu page "AI / KI: enemies ignore Lara (0.19)"; `ai.status` = setting, checks, enemies seen / in scope, last second.
* **Log**: one line per switch change, one per burst of removals / gate blocks (when it ends, every 30 s while it lasts),
  never per frame. Cheats page: the rebuild rows "no senses" / "don't attack" / "don't investigate" name their 0.19 item;
  "no barks" is unknown (0x616c20 is the EnemyProcess constructor, not ENEMY_UpdateBark).

```text
0.19 dumb AI: purge (stage A) ok (11 checks), gate (stage B) ok (15), brain flags ok (7); [AI] Dumb -> off, ...
ai.dumb sharks (src=ring): off -> filter 'shark'; purge (stage A): the engine's sense reset 0x65a140 once per frame
ai.dumb: burst ended after 4.0 s (4 active second(s)) - stage A purge 37 sense(s); gate 0 add(s) / 0 override(s) ...
ai.dumb gate (stage B) on (ai.dumb on): A1 scan 0x6648bb, A2 AddTarget 0x659d8f, ... -> TruMenu
```

## TruMenu 0.20 (collectibles, enemies, forget, goload over portals, mutes; 2026-11-06)

Report `docs\Befund-TruMenu-020-0611.md`; byte checks `work\asi\menu020\precheck_020.txt` (16, section
"// ---- 0.20 collectibles, enemies" .. "// ---- end of 0.20 collectibles"); analysis files `work\m020_0611`.

* **`dbg.collect`** (layer `collect`, `[Debug] Collect`): every instance whose object name holds `_rw_` (artifact gold,
  treasure pink, shard turquoise, other reward light gold) and every reward container (`_pt_` + `reward`:
  `dlc1_pt_reward_pot`, `*_pt_weightbreak_reward`) as a magenta ring with **"enthaelt Artefakt #<index>"** - the
  container's object type data names `tp_rw_artifact_spawned` (the same for every pot), the reward index is intro data
  +0x30 (`[[inst+0x100]+0x78]+0x30`). "Collected" is not shown (not verified cheaply).
* **`dbg.enemies`** (layer `enemies`, `[Debug] Enemies`): every AI enemy (the 0.19 brain test) coloured by kind -
  thrall, spider / tarantula, shark, tiger / panther, naga, bat, merc / poacher, other; label name, intro id, LP,
  distance; thralls with the 0.13 targeter 9 line. While on, `dbg.labels` leaves AI enemies to it. Both layers: the
  nearest `[Debug] MarkMax` within `MarkRadius`, legend rows per kind (found in the loaded units).
* **ai.dumb forget**: when ai.dumb comes on (and for an enemy entering scope while on) the enemy's current target
  (`EnemyTargeting` +0x30) and override (+0xf0) are cleared once with the engine's slot setter `0x653cf0` when they
  hold Lara, then her senses are purged. **`[AI] DumbMode=gate` is the default** (purge = fallback).
* **`shot.oncine`**: a track change of the same cinematic no longer starts a segment (unit change, another cinematic
  object or a StartCinematic print still do).
* **`pos.goload <name> [load]`**: a target unit that a loaded unit has a stream portal to is reached over that portal -
  `cheat.flight 1;pos.portal <unit>;wait.unit <unit>;pos.go <name>` (`wait.unit` = the runner waits until the unit is
  loaded 1 s in a row, at most 30 s); `level.load` only without such a portal or with `load`.
* **`media.mutemusic`** (`[Media] MuteMusic`): `SOUND_SetMusicVolume 0x589520(0)` whenever the music comes back
  (level loads re-apply the slider); off = the player's value `[0x8900d8]`. **`media.muteambient`**
  (`[Media] MuteAmbient`): `_amb_` srmusic tracks (DLC 2) stopped when they start; base-game ambience not covered.
* Defaults: `[Debug] Depth=2` (dim), `FlatPasses=0x600`. Bar: Leveldaten "Sammelgegenstaende", Render / KI "Gegner",
  "Gegner-Leben zeigen", "Kanten", Zeit / Test "Musik aus" / "Ambient aus", Notfall last row "Spiel beenden"
  (`game.quit`: right arms, right again within 10 s quits). Ring: Leveldaten, KI, Zeit.

## TruMenu 0.20.1 (sound list, music mute without the slider, enemy state on the labels; 2026-11-06)

Report `docs\Befund-TruMenu-0201-0611.md`; byte checks `work\asi\menu0201\precheck_0201.txt` (44, section
"// ---- 0.20.1 sound list" .. "// ---- end of 0.20.1 sound list"); analysis files `work\m0201_0611`.

* **FMOD Ex is linked into `tru.exe`**: the exe imports no `fmodex.dll` (the DLL next to it is not used by the exe);
  `tools/pe_fmod_api_map.py` lists the linked public wrappers (System 26, Channel 24, ChannelGroup 5, DSP / Sound 21)
  and their callers. `FMOD::System*` = `[0xcc9f80]`.
* **`snd.list`** (`[Sound] List`): an overlay, **bottom left** by default, header "Ton (n spielen)", one line per voice:
  group (MUSIK / SFX / SPRACHE / ?, plus the group number), wave id (`Welle 1234`; sounds carry no name in memory) or
  `Stream`, the channel volume the game set and the group volume, state (spielt / virtuell / pausiert / stumm /
  startet / endet; not audible = dimmed), distance to Lara for 3D voices; MUSIK lines add the srmusic tracks
  (`media.music.now`). Source: the game's voice pool `0x8a8108` - `VoicePool::Play 0x58bfc0` is the only caller of
  `System::playSound`, so every channel the game plays is in it. Built on the game thread every `RefreshMs` (also while
  paused): memory reads plus the game's read-only FMOD wrappers `Channel::isPlaying / getPaused / getVolume /
  isVirtual`. Groups: music = categories [0] (slider "Musik") and [3] (FMOD channel group "music"), SFX = [1], speech
  = [2] (the third option slider, speech / cutscenes).
* Settings `[Sound]` Position (bl / tl / tr / br), MaxLines 16, RefreshMs 1000, Sort (group / volume / name), FontScale,
  OnlyPlaying, ShowMusic / ShowSfx / ShowSpeech / ShowOther; items `snd.list / pos / lines / refresh / sort / scale /
  playing / music / sfx / speech / other / status`. Menu page Debug view, group "Sound list / Ton-Liste"; bar Debug /
  Darstellung (every switch; Ort / Zeilen / Sortierung as value rows) and Zeit / Test (Ton-Liste, ins Log); ring
  Spieler/Debug/Ton (on / off, dump, four corners, audible only, sort group / volume, status) and Zeit | Ton-Liste. The
  ring is now at TruMenu's 256-entry limit - the group filters stay on the bar and the menu page.
* **`snd.dump`** (game thread, once): every voice, unfiltered, with addresses / flags / position into `TruMenu.log`;
  `snd.list` on writes one burst line (FMOD system, voices, groups), never per frame.
* **`media.mutemusic`** now mutes the **FMOD channel groups** of the music groups (FMOD's own
  `ChannelGroupI::setMute 0x7c48cd`; no public wrapper is linked, the game never mutes a group) - no game volume and
  not the option slider is written; muted again after a level load (new groups); off unmutes only the groups TruMenu
  muted. Fallback when those checks fail: the 0.20 `SOUND_SetMusicVolume` path (logged at load).
* **Enemy state** (coordinator): the `dbg.enemies` label and the thrall line of `dbg.labels` show the behaviour state
  `(char *)[[brain+0x125c]+8]` (e.g. Vaulted, Land, Getup, RegenerateDeath, Regenerate); RegenerateDeath adds the rest
  until it stands up (`~n s` from the measured game clock rate; `(wacht)` when due). `[Debug] EnemyStateLog=1`: one log
  line per state change of a labelled enemy.

## TruMenu 0.21 (Arachnophobie stage 1, camera shake, label fixes, ai.remove, Koop placeholder; 2026-11-07)

Report `docs\Befund-TruMenu-021-0611.md`; plan `docs\Befund-Arachnophobie-Stufe1-Kamera-0611.md`; byte checks
`work\asi\menu021\precheck_021.txt` (65, section "// ---- 0.21 arachnophobia" .. "// ---- end of 0.21 arachnophobia");
analysis files `work\m021_0611` (`labels\`, `airemove\`).

* **Arachnophobie** (`[Arachno] Enabled`, item `arachno.on`, default off) - the master switch of three parts (each 1 by
  default, so switching the master on gives the whole mode):
  * **Model off** (`Hide`, `arachno.hide`): the `InstanceDrawable` vtable slot 7 (`.rdata` word `0x853ad8` = `0x5bba90`)
    leads through TruMenu while the mode is on in a level; for a spider the engine wants to draw, the draw-group mask
    `+0x23c` is `-1` **only during its draw call** (the engine's own "all groups hidden" exit) and the game's value comes
    back right after. Logic, collision, AI, hits and Lara's aim are untouched; the shadow goes with the model. If the
    draw runs on another thread than the game logic (logged once: `arachno: spider draw calls run on thread ...`), V2
    skips the call instead of writing the mask.
  * **Picture** (`Picture`, `arachno.picture`): a wobbling picture (bob / squash / tilt, `WobbleAmp / WobbleHz /
    SquashAmp / TiltDeg`) at the spider's projected bones, size relative to them (`Scale`, `MinPx`, `MaxScreen`), faded
    closer than `FadeNear`, none beyond `MaxDist` or at LP 0, mirrored while it moves left (`Flip`). Drawn over the game
    and its HUD (walls do not hide it yet - the depth path is 0.22).
  * **Sounds off** (`Mute`, `arachno.mute`): spider sounds are not started - 6 call gates (anim sound `0x5b99c0`, random
    set `0x5b2820`) + the sound-slot jump table word `0x5b6b1c`; TruTrace's checked call bytes `0x5b6a2f` stay.
  * Spiders = object names with a part of `Match` (`spider,tarantula`) and none of `Exclude` (`_generator`).
    `arachno.list` writes every spider (drawable class, flags, masks, bones, children, LP, draw thread) into the log;
    `arachno.status` shows the state.
  * **The picture file**: `TruMenu.arachno.png` next to `tru.exe` (`[Arachno] Image`, PNG with alpha, read with
    stb_image - `src\asi\third_party\stb`, public domain / MIT, no new DLL import). **The owner's own image is local
    only**: it is not in the repository (`.gitignore` `TruMenu.arachno*.png`, `work/arachno_owner/`), never shipped,
    and `Set-TruMenu.ps1` never copies, overwrites or removes it (`Assert-NotOwnerImage`); `tools/pending_upload_scan.py`
    reports a pending `*.arachno*.png` or `work/arachno_owner/` path as an error. Without the file a built-in picture
    (a friendly cat face drawn by code) is used.
* **Camera shake** `[Camera] ShakeScale` (`cam.shakescale 0 .. 100`, 100 = the game's own, no patch): the two callers of
  the shake strength `0x5eb460` (camera apply `0x5eea55`, shake sum `0x5eb56d`) call a stub that multiplies the result.
  **Rumble** `[Camera] Rumble` (`cam.rumble 0 .. 100`): the resolved `XInputSetState` pointer `[0xa02b90]` is wrapped while
  below 100. Test helpers `cam.shakelist` (the `camerashakes` table into the log), `cam.shake <n>` (the game's start by
  key `0x5ee940`), `cam.shakestate`.
* **Labels** (0.20 live test): a reward pot is labelled once - a runtime copy (`INSTANCE_BirthObject` gives a child the
  parent's intro record and a runtime id from `0x40000000`) is skipped while the placed instance (`+0x58` =
  `[intro+0x58]`) is in the walk; instances the game does not draw (hide bit `0x800`, kill flag `0x20`, scene entity
  off, draw masks `-1`) get no label - a picked-up artifact no longer keeps its label in mid air.
* **`ai.remove nearest | others | all | <intro id>`** (game thread): AI enemies out of the world the way the game's
  despawn behaviour does it (`0x61cda0`: hide `0x800`, `CSenseManager::RemoveInstance 0x71dcb0`, the generator's
  notification, kill flag `0x20`; the game's sweep `0x5bcbb0` removes them in the next frame). No damage, no death, no
  save mark (back after a reload). Bar Render / KI "Alle bis auf den naechsten" / "Den naechsten" (right twice), menu
  page AI. A level script waiting for those enemies to die will not go on.
* **Sound list**: bottom right by default (`[Sound] Position=br`; bottom left is the quick-toggle bar's side), rows
  right-aligned in a right corner, the srmusic tracks once in a MUSIK header line (not on every music row); the bar's
  value rows Ton: Ort / Zeilen / Sortierung show their value (0.20.1 showed `?`).
* **Places**: bar page Barrierefreiheit (Arachnophobie + 3 parts + state, Kamera-Wackeln / Vibration 100 / 50 / 0 %;
  the planned rows are replaced, "Blitze daempfen" stays planned), new bar page **Koop** (planned rows only, no
  function yet), menu groups "Arachnophobia, camera shake" and "Co-op / Koop (planned)". The ring has no new entries
  (it is at its 256-entry limit).

## TruMenu 0.21.1 (ai.kill, sticky, room check, physics bodies, enemy spawn, bar page 0 / Tests / groups; 2026-11-07)

Report `docs\Befund-TruMenu-0211-0711.md`; byte checks `work\asi\menu0211\precheck_0211.txt` (62, section
"// ---- 0.21.1 ai.kill" .. "// ---- end of 0.21.1 ai.kill"); analysis files `work\m0211_0711` (`dis_*.txt`).

* **`ai.kill nearest | others | all | <intro id>`** (game thread): enemies die the game's own way - the game's "Kill"
  `0x6376e0` (its only caller `0x63831c` passes type 6 RigidBody) = the damage function `0x637590` with amount = LP,
  then the death check `0x620380` -> `0x641650` -> state `EnemyState_Death`, whose Enter fires the instance's script
  event (vt 31) - level scripts count it (the hall02 wall waits for these deaths, `docs\Befund-Hall02-Wand-0711.md`).
  Per enemy the type is picked first: 6, else 4 / 2 / 1 / 0 - the first one whose case in the live type switch is
  "damage + death check" (TruShadowCombat's `[Damage] Translate` table is read as well), not absorbed by the health mask
  and not on the enemy's regeneration list (the game's `ShouldRegenerate 0x67f040` asked) - so the enemy ends in
  `Death`, not `RegenerateDeath`. Refused for an enemy with brain+8 `0x800`, brain+0xc bit 1 or already dying, and for
  the whole call while the physics step runs or fewer than 60 of the 405 physics bodies are free (a death may build a
  chunkdoll - the "ChunkDoll: failed to create geom" crash). One log line per call, one line ~1 s later with each
  enemy's state.
* **`ai.remove`** warns: an enemy from a generator or with a script is a story enemy - "zaehlt nicht als Tod - Skripte
  warten evtl." in the log line, the answer and the bar's confirmation text.
* **`sticky.get <owner> <key>`**, **`sticky.set [int|bool|float] <owner> <key> <value>`** (set on the game thread):
  owner = an intro id (kind 0) or `<kind>:<id>`; the StickyManager `[0xa13f18]` stores are searched like the game's Find
  (never appended); set writes the value as the game's setters do and calls their change notification; old and new value
  logged. hall02 repair: `sticky.set 11270 17287 0` (population) and `sticky.set 11270 18509 2` (tutorial), then walk
  through the arena trigger 11268 (bar Render / KI, menu AI).
* **Room check**: `player.goto <instance> [force]` refuses a target whose stream unit (`+0xe0`) is not loaded, a
  resident unit's template ("geparkt", parked at (32000, 32000, -32000)), one the game does not draw and one farther than
  25000 units outside Lara's unit; `force` jumps anyway. The enemy / collectible labels say `| geparkt`. `pos.go` to a
  unit behind a portal of Lara's own unit takes the portal path; `pos.goload` and `pos.portal` use only Lara's own
  unit's portals for that (from a neighbour's portal the engine never requests the target). **`unit.go <unit>`** (also a
  shortcut step): nothing when Lara is in it, `cheat.flight 1;pos.portal <unit>` when it is loaded, else `level.load` -
  the regression Prepare "Thrall fight: hall02 + god mode" (`tests\regress\dlc2.txt` step 7) uses it. Two portals away
  (DLC 2 start -> hall02) still needs `level.load`: the engine's unit switch is not built.
* **Physics bodies** (read only): `phys.status` / bar Render / KI "Physik-Koerper n/405" (`[0xa037f4]+0x20a8`, lock
  `+0x20f8`, chunkdolls `[0xecfc70]`), a log line when the used count crosses 300 / 380 / 400 (and back under 280),
  `phys.dump` = the used list grouped by name, orphans (owner 0 or the owner's `+0x274` is another body) one by one.
* **Enemy spawn** `ai.spawn <object> [1..5] [lara|front]`, `ai.spawncount`, `ai.spawnat`: an AI enemy object loaded in
  this level (object tracker status 2, family 14; no generators / chunkdolls / doppelganger) through
  `INSTANCE_BirthObjectNoParent 0x5bd0f0` at Lara or 250 units in front (the debug view's camera); `save.backup spawn`
  before the first spawn of a session; needs `[Cheat] Experimental`. "KI dumm only for these", "model only", gear,
  behaviour and the navmesh check are planned rows.
* **Health bar** `dbg.hpbar` / `[Debug] EnemyHpBar=1`: the enemy labels of the layer Gegner show a bar (green -> red,
  LP / max LP of the difficulty, the number in it) instead of `| LP n`.
* **`menu.hidecursor`** / `[Menu] HideCursor=0`: no mouse cursor over the game picture while the menu is closed
  (WM_SETCURSOR in the client area; no game memory).
* **Quick-toggle bar**: page 0 **Favoriten / Zuletzt** (the favourites, then the last `[Quick] RecentMax` rows that ran,
  kept in `[Quick] Recent`); page **Tests** after Zeit / Test (teleports, the regression Prepare shortcuts - right twice -,
  Stop, the TO TEST rows: right = OK / done / on, left = Fehler / open / off); **collapsible groups** (row kind
  `kQbGroup`: `[-]` open / `[+]` closed, right = open, left = close, `[Quick] Closed`); page Render / KI in the groups
  "Dumme KI", "Gegner spawnen", "Gegner entfernen / toeten" (ai.kill rows, ai.remove rows, the hall02 repair rows),
  "Physik-Koerper", "Lebensleiste"; the long menu's page AI has the same three groups as collapsible sections.
* **Export `TruMenuPadBlock(DWORD pad)`**: the buttons TruMenu keeps from the game right now (0xFFFF = neutral pad; bar
  open: D-pad / LB / RB) plus bits 16 / 17 / 18 = menu / ring / bar open - for plugins that read the pad themselves.
  The pad import filter: while the pad pointer is still empty a rewritten import slot `0x83e08c` is logged with the
  module that wrote it (`pad: import slot ... was rewritten ...`, diagnosis only).

```text
0.21.1: ai.kill ok (27 checks), sticky ok (16 checks), room check ok (3 checks), physics bodies ok (11 checks), enemy spawn ok (1 check), health bar ok (4 checks); [Debug] EnemyHpBar 1, [Menu] HideCursor 0, [Quick] RecentMax 8, Closed ''
ai.kill others (src=quick): 3 of 4 AI enemy(ies) killed the game's way (...); kept the nearest ... - viking_thrall_tutorial_dlc2_ 0 (type 6 RigidBody, LP 500 -> 0, script), ...
ai.kill: 1 s later 3 of 3 in a death state (...): viking_thrall_tutorial_dlc2_ 0 Death, ...
sticky.set int 0:11270 key 17287 (index 37): 3 -> 0 (src=quick; the game's set + change notification 0x004af740)
phys: bodies used 301 / 405 (crossed 300; peak 301), chunkdolls 1 / 4, lock 0 - ...
```

## TruMenu 0.21.2 (queued items outside the pad hooks of other plugins; 2026-11-07)

Report `docs\Befund-Padkette-StartView-0711.md`; build `work\asi\menu0212`; no new byte check (no new game address).

Live 2026-11-07 14:55 (DLC 2): from one moment on, every View + Start of the quick bar also opened the game's pause
menu. Cause: the bar row "Fliegen" queued `cheat.flight 0`; the item runs on the game thread inside PadHook and its
message 12 to the player makes the game poll the pad again through 0x00a02b8c. In that run TruLink sat outermost
(`game -> TruLink -> TruShadowPower -> TruMenu -> XInputGetState`), was still on the stack and took the same-thread
re-entry for a hook loop: `pad hook re-entered (hook chain loops back to TruLink) - calling XInputGetState directly
from now on` (TruLink.log 14:55:07.230). TruShadowPower and TruMenu were out of the chain for the rest of the session
(`pad: slot not polled - reading the pad in Present`, never "polled again"); the bar then worked from TruMenu's own
reads in Present, which cannot mask - the game got Start. The same happened once before (16:14:39, also
`cheat.flight 0`, TruLink outermost); `cheat.flight 0` in the other orders (TruMenu or TruShadowPower outermost) never
cut the chain.

0.21.2: PadHook runs a queued item only when the **game itself** called it (return address inside tru.exe - no other
pad hook is outside PadHook on this thread); otherwise the item waits for the Present hook (same thread, between two
polls, the path the front end has always used) - at most one frame later. One log line per caller module
(`pad: PadHook is called through another pad hook (TruLink.asi, return 0x...) - queued items run in the Present hook
instead ...`), later items at LogLevel 2. Without a Present hook (d3d9 code check failed) items run in PadHook as
before. The per-frame ticks of PadHook are unchanged. The order of the three pad hooks still depends on load timing
(the import slot is rewritten to KERNEL32's GetProcAddress after TruMenu's filter in every run - by whom is unproven);
with this rule and TruShadowPower 0.19
(TruMenuPadBlock, no re-wrap) no order cuts the chain (model `padchain` in `tools\trumenu_quick_check.py`, all six
orders).

## TruMenu 0.21.3 (quick bar: X runs, Y pins; sound list width; 2026-11-07)

Report `docs\Befund-TruMenu-0213-0711.md`; build `work\asi\menu0213`; no new byte check (no new game address), no new
option (only the comments of `[Quick] Enabled` / `OpenButtons` name X / Y).

* **X and Y belong to the open bar.** Before 0.21.3 the bar kept only D-pad / LB / RB from the game (`kQbOwn 0x030F`) -
  X and Y reached the game while the bar was open. Now `kQbOwn = 0xC30F`: QbPad masks X / Y in the state the game gets
  while the bar is open, a button held at the close stays away until it is released (as the D-pad), and the export
  `TruMenuPadBlock` reports them while the bar is open (same meaning: the buttons the game does not get).
* **Y = favourite** (as Y in the long menu / `fav.add` / `fav.del`): pins / unpins the selected row's item in
  `[Favorites] Ids` (toggled by item id, so an item is never in the list twice and every row of that item shares the
  state); the footer says "als Favorit angeheftet (Seite 1)" / "Favorit entfernt", page 0 "Favoriten / Zuletzt" is
  rebuilt every frame (a pinned row moves out of "Zuletzt" at once). Only rows that are one item **without an
  argument** can be favourites - `[Favorites] Ids` holds item ids; `dbg.show death`, `ai.dumb sharks`, `shot.save ui`,
  `ai.kill others`, the chapter rows etc. are refused with a footer line. Headings, groups, planned rows and the special
  rows (positions, checkpoints, saves, Prepare, TO TEST) say "keine Item-Zeile". Log: `quick: <page> / <row> -> Y: fav
  add|del <id> (...)`.
* **X = execute.** Action, choice, info and planned rows and every special row: exactly the right press - so every
  confirmation row keeps its safety: the first X arms (footer "rechts / X nochmal (3 s) = ausfuehren"), a second X **or**
  right on the same row within 3 s runs it (Spiel beenden arms itself for 10 s; the Saves rows ask twice inside their
  items as before). bool rows: X toggles. Group rows: X opens / closes. **Value rows: X does nothing** (footer "Wert mit
  links / rechts (X: nichts)") - a value row has no default step of its own; left / right stay the way. One of Y, X,
  left / right per frame (Y first): an X and a right press in the same frame never count twice.
* **Footer**: the second line (never replaced by a result) reads `X: ausfuehren  Y: Favorit   View + Start: zu`
  (EN `X: run  Y: favourite   View + Start: close`); the page-0 heading `Favoriten (Y = anheften / loesen, hier und im
  Menue)`.
* **Sound list width** (`snd.list`): the box now follows the rows of the current frame. Cause of the old behaviour: in a
  right corner every row was shifted to end at the window's right edge (`avail - w`), which made the content always as
  wide as the window, so `AlwaysAutoResize` could only grow it. Now the rows are gathered first, the widest one of this
  frame sets the right edge (at most the window's content width), right alignment in the right corners stays; left
  corners were not affected.

Checks: `tools\trumenu_ini_check.py` `check_0213` (14 negatives), `tools\trumenu_quick_check.py` chord (+3 X / Y cases)
and models `xyfav`, `xyexec`, `footer`, `sndwidth`.

## TruMenu 0.21.4 (hall02 counter rescue, thrall script value; 2026-11-07)

Report `docs\Befund-TruMenu-0214-0711.md`; build `work\asi\menu0214`; 19 new byte checks (`precheck_0214.txt`, table
`kH2Checks`), no new option (the sample `TruMenu.ini` is the 0.21.3 one). Background: `docs\Befund-Hall02-Zaehler-Drift-
0711.md` (why population stays at 4) and `docs\Befund-Hall02-TU-Vergleich-0711.md` (root cause: the intro data of
generator 10028 are mis-converted on the PC, so checkpoint 11258 stores pre-spawned thralls - the Xbox never does). The
real fix belongs into the data; TruMenu only rescues saves that already hold them.

* **`fix.hall02`** (game thread, bar page Tests "hall02-Zaehler reparieren" right / X twice, long menu page AI group
  "Gegner entfernen / toeten"): refused unless Lara's stream unit is `dlc_yggdrasil_hall02`, the dispatcher 11270 has its
  sticky values, `broken` (10029) is 0 and **no** object-1004 `viking_thrall_tutorial_dlc2_` is alive (alive = present
  `[inst+0x44] != 0`, no kill flag `+0x14 & 0x20`, brain not in Death / LandDeath / DrownDeath / DeferredInstantDie -
  RegenerateDeath counts as alive; without a readable brain: hidden = gone, else alive). Then `tutorial` (18509) = 2 if
  below 2, `population` (17287) = 0 - both through `sticky.set` (the game's write + change notification, old / new
  logged). The answer: "jetzt einmal durch den Arena-Trigger 11268 zurueck- oder hineinlaufen (Pruefung nur beim
  Betreten / Verlassen)" with the trigger's live position and distance; with `[Debug] Enabled` the debug view layers
  Trigger + Trigger-Namen are switched on (drawing only) so the trigger is visible.
* **`thrall.scriptval`** (read only, bar page Tests, long menu): every object-1004 thrall with intro (runtime / placed),
  state and its thrall-script int +8, plus every other generator enemy (raw +8, other script) into `TruMenu.log`;
  expected: restored 0, generator-born 2. Address = the game's own path: `[[inst+0x60]+0xc]+8` - `[inst+0x60]` is the
  script reference the generator hands to OnSpawn (0x781342) and the death event uses (0x66c31f); the interpreter's
  op14 (0x57d04b) takes member data `[R+0xc]` (0 when R or the data is 0), script 22809 f0 writes "R.+8 = 2" with it.
* Not built (coordinator, after the TU comparison): the restore-time safety net E3 (`[Fix] Hall02Restore`) - it would
  imitate behaviour the Xbox does not have.

Checks: `tools\trumenu_ini_check.py` `check_0214` (17 negatives), `tools\trumenu_quick_check.py` models `h2drift`,
`fixhall02`, `scriptval`.

## TruMenu 0.21.5 (page Fixes: plugin INI switches; the ring is frozen; 2026-11-07)

**Bar page "Fixes" / menu section "Fixes"** - one data file `TruMenu.switches.txt` (source `src\asi\TruMenu\`,
`Build-TruAsi.ps1` copies it into the build folder, `Set-TruMenu.ps1` installs it next to `tru.exe` with the
first-line rule of the radial / tour files: ours = first line starts with `# TruMenu switches`; `-Remove` deletes only
ours). Format (also in the file header):

```text
group | <key> | <DE heading> | <EN heading> [| open]
<Plugin> | <Section> | <Key> | bool | int:<lo>..<hi>[:<step>] | choice:<a>,<b> | <DE> | <EN> | live | restart | live-if:<Key> | <default> | <hint> [| <since>]
```

- `live` = the plugin re-reads the key while the game runs (about once a second): TruShadowCombat `[Damage]`,
  `[Chunk]`, `[Splash]` `Translate`, `[Strike] Translate`, `[States] Translate1013 / 1019 / 1020 / 1004 / 231Slot0 /
  231Slot1`, `[Death] TranslateNotify33` (0.6.3), TruShadowPower `[Adrenaline] Translate` (K11); `live-if:LiveReload` =
  TruMercLang `Enabled` / `Language` (live only with `LiveReload=1` at the start); every other key is read once in
  DllMain (`restart` / "Neustart"). Some live keys only act when their hook was installed at the start (the hint says
  so, e.g. `[Damage] Translate` needs `Translate` or `Log` = 1 at the start).
- 112 switches in 9 groups (DLC 2 Kampf, Schattenkraft, Kampf Grundschalter / Diagnose, HUD, Felsader,
  Doppelgaengerin, DLC 2 Spielerin / Kostuem, Soeldner-Sprache, TruTrace): every key of the eight plugin INIs except
  the text filters (`PathFilter`, `SpawnFilter`, `ProgressFilter`). Keys that exist only in code (TruShadowPower
  `Cond1046` / `Cond1055`, the hidden TruRockVein keys) are not listed (not in the sample INIs). TruGuard is not part
  of it.
- Bar: one group row per group (`[+]` / `[-]`); **one group open at a time** (right / X opens and closes the others,
  left / X closes; kept until the game ends, the file's `open` mark = the start state) - with all groups open the page
  would have 124 rows (`kQbViewMax` 64). Switch row: name, value (`an` / `aus`, `< 3 >`, `< es >`; a key missing in
  the INI shows the default in brackets, a plugin without INI `keine INI`), count column `live` / `Neustart`. Right /
  left = on / off or one step (stops at the end), **X** = toggle (bool) or one step up with wrap (int / choice). **Y**
  is refused ("Fix-Schalter sind kein Favorit"): `[Favorites] Ids` holds item ids without an argument and a switch row
  is `sw.set <target> <value>` - no pinning, no recent rows for these rows.
- Long menu: section "Fixes: plugin switches / Plugin-Schalter (0.21.5)" - tree node per group, checkbox / - + /
  choice buttons, tooltip = hint; buttons `sw.reload` / `sw.list`.
- One write path, item `sw.set <Plugin>:<Section>:<Key> <value>` (bar, menu, TruLink): only keys listed in the file,
  only values of the row's type / range, only into an existing `<Plugin>.ini` next to the `.asi` files (a plugin that
  is not installed never gets an INI), never an unchanged value; `WritePrivateProfileStringA` as the TO TEST toggle
  rows (`TestIniTarget`). The live re-reads pass the current value as their default, so a read that meets the write
  keeps the old value one second longer. Log `sw.set <Plugin> [<Section>] <Key>: old -> new (live|restart) in <path>
  (src=...)`. `sw.list` logs every row with its INI value, `sw.reload` reads the file again.

**Ring frozen** ("aktuell nicht weiter gemacht"): `TruMenu.radial.txt` keeps its 172 entries, no new ones (header
note). Every ring entry is now a bar row: 52 were ring-only and became rows - Notfall (Befreien (Marke), Saves
sichern), Lara (Foto wie im Rad, Positionen: Liste, group "Objekte spawnen (Rad-Stufe R2)" with the five
`instance.spawn` rows, right / X twice), Debug / Darstellung (Schnellschalter, Darstellung / Debug / Ton: Stand),
Leveldaten (Checkpoints alle zeigen / verbergen / Liste), Zeit / Test (Ton mit Welt anhalten, Shader-Uhr mit anhalten,
Musik Thailand / stoppen) and the new page **Render-Details** (groups Flach-Ansicht Farbe / Paesse, Navmesh,
Objektnamen). The long menu got the section "Quick bar pages / Schnellleiste-Seiten (0.21.5)": every static row of
every bar page from the same tables (confirmation rows with the menu's A-twice `ConfirmButton`, chapters back up
first) - so the menu reaches every ring entry too. The bar now has 15 pages.

Checks: `tools\trumenu_ini_check.py` `check_0215` (switches file format, every key in its plugin INI with the shipped
default, live claims against the plugins' re-read functions, every INI key covered; ring frozen + every entry a bar
row; 19 negatives), `tools\trumenu_quick_check.py` models `switches`, `swfold`, `ringparity`. No new game address, no
new byte check, imports / exports unchanged. Not in 0.21.5: the SweepAndPrune read-out (P6a) and the shader labels
(room for 0.21.6).

## TruMenu 0.21.6 (bar page Kostueme, flight key line, quick command line; 2026-11-07)

Owner wishes 2026-11-07: "Kostuem-Wechsel in der Leiste waere auch gut" (a list or one row switched with left / right -
both), "beim Fliegen anzeigen, mit welchen Tasten man fliegt, die stehen ja nicht da", and the TODO item "Kleine
Kommandozeile in der Leiste" ("bau das direkt mit"). Build `work\asi\menu0216`; no new game address, no new byte check;
one new option `[Cheat] FlightHint`.

**Bar page "Kostueme"** (page 4 of 16, right after Lara - its own page: with the list open it has 4 + N rows, N = the
outfit cycle list, about 36; on the Lara page that would be 15 + 8 positions + 4 + N > 64 = `kQbViewMax`; the bar is now
at its 16-page limit, `kQbStartPage` = 5 = Leveldaten). Every row runs the existing items on the data of the long menu
sections "Outfits (live switch)" / "Outfits (next level load)" - no new write path:

| Row | Keys | Item |
|---|---|---|
| `Kostuem: < name >` | left / right = previous / next entry of the cycle list GlobalInfo `[0xe7ee50]+4`, **wraps** at both ends; only the shown name changes, the switch runs once the choice stood still **0.5 s** (`kCosSettleMs`; `QbCosTick` every frame, also with the bar closed) - holding or tapping quickly never switches on every step; one switch = one `quick: Kostueme / Kostuem -> costume.set <id>` line; **X** = the shown entry now; the entry worn already = "schon an", nothing runs | `costume.set <object id>` (live, 0x6f0a90) |
| `Naechstes Kostuem` | right / X | `costume.next` (the game's own cycle step) - kept: the only costume row **Y** can pin as a favourite (no argument) |
| `Fuers naechste Laden + neu laden` | left / right = a player record of the type table (wraps, only records whose name is in the object list), **X** arms, X or right within 3 s runs (the confirmation of the other reload rows) | `costume.choosereload <record index>` (choose + reload the unit) |
| `[+] Alle Kostueme (N)` | closed at the start; right / X open, left / X close (as a Fixes group; kept until the game ends) | - |
| one row per cycle entry | right / X = this costume now; the worn one is marked (green square, "aktuell") | `costume.set <object id>` |

Head line: the current costume `[0xe7f1c8]`, the list / record counts. Labels: `dlc_costume_<a..p>` = `<slot> <the game's
outfit text> (<object name>)`, e.g. `f Casual Explorer (dlc_costume_f)` - the texts are PC locals ids 83 + slot (B138
`locals.bin_001`, measured in `work\rebuild\costumes_0311\logs\check_names.txt`, `docs\Befund-Kostueme-Port.md`; g, n and
o all read "Grey Jungle Shorts"). Every other costume (`lara_*`, `dlc_doppel_costume_a..d`, `doppelganger_casual`) shows
its object name only - no text mapping is known for them. Without a level (or with `[Cheat] Experimental=0`, or a failed
costume code check) the rows are grey with the reason in the right column ("braucht ein Level") and refuse with it. **Y**
on a costume row other than "Naechstes Kostuem" is refused ("Kostuem-Zeilen sind kein Favorit"): `[Favorites] Ids` holds
item ids without an argument (as page Fixes in 0.21.5). The footer's first line names the selected row's keys.

**Flight key line** (`[Cheat] FlightHint`, default 1): while `cheat.flight` is on, in a level, and the menu is closed,
one line bottom right: `Fliegen: RT hoch | LT runter | Stick bewegt | Tempo 20` (EN `Flight: RT up | LT down | stick
moves | speed 20`, the bar's language `[Quick] Language` / `quick.lang`). The bottom-right corner may already hold the
sound list (`[Sound] Position` br, the default) and the flow status line (`[Flow] Position` br): the line is drawn after
them and goes above whichever of their windows of this frame reaches into the bottom-right quarter - it never covers
them. The same text is the footer of the bar rows "Fliegen" / "Flug-Tempo" while selected and the tooltip of the menu's
flight button (Cheat page) and of the row in the section "Quick bar pages". Keyboard: FlightTick reads the pad only -
there is **no** key for up / down (horizontal movement = the game's walking keys); "Tastatur: nicht belegt" did not fit
the short line, it is in the tooltip ("pad only - no keyboard key for up / down").

**Quick command line** (TODO "Kleine Kommandozeile in der Leiste"): in the open bar `[Cmd] FocusButton` (**L3**, the
button that focuses the menu's command bar) pressed and released **alone** opens / closes a compact command line right
of the bar: one input line, the last 4 answers (newest first, coloured ok / err), a key line. L3 is free in the bar (the
bar owns D-pad / LB / RB / X / Y, View + Start toggle it); a press that becomes part of L3 + R3 (long menu / ring hold:
`[Menu] ToggleButtons`, `[Radial] HoldButtons`) is not one - R3 down while L3 is held cancels it, as the 0.7 FocusButton
rule. It is the 0.6 command bar's line, **one command path**: every run goes through `CmdRunLine` (same parser `help` /
`list` / `get` / `<id> [arg]`, same items, the history shared with the menu's bar and TruLink `cmd.run`, the log line
`cmd (quick): <line> -> <answer>`, queued game-thread answers via `CmdNoteQueued` / `CmdPollQueued`).

- Keyboard: typing goes to the line - key messages go to ImGui only and the game's DirectInput keyboard gets no events
  while it is open (as the menu with `[Menu] BlockGameInput=1`); Tab = the first suggestion of the command bar's list,
  Up / Down = history, Enter = run, Esc = close.
- Pad: D-pad up / down = history (older / newer), **A** = run, **B** = close, L3 = close. While the bar is open L3 is
  kept from the game, while the line is open A and B too (`QbPad`; `TruMenuPadBlock` reports them); the bar's rows wait.
- Closing the bar, opening the long menu or the ring closes the line. `[Cmd] Enabled=0` = refused. Log `quick: command
  line opened / closed (<why>)`.
- Not built: the 0.7 on-screen keyboard (it lives inside the long menu window - DrawOsk and its focus rules); with the
  pad only history lines can be run.

**Toggle rows show their state** (owner live test 2026-11-07 20:52: the Navmesh rows only said "rechts"): the rows that
flip a flag per argument are bool rows now - page Render-Details, group Navmesh (`nav.draw planner_areas` /
`planner_areas_solid` / `planner_connectivity` / `planner_area_normals` / `obstacles` / `recent_navprobes` /
`draw_mover3d_path`) and group Flach-Ansicht (`dbg.flatpass 0x200` / `0x100` / `0x80` / `0x400` / `0x800` / `1` / `2`).
State `an` / `aus` from the ring's `RadialOn` (the NavPower switch byte the item writes, e.g. `0x008bf2e5`; the pass bit
of the flat view's mask); right = on, left = off (no blind flip; "schon an" writes nothing), X = toggle; the item gets
`<switch> 1|0` (no new write path). A Navmesh row that is on but cannot draw shows `an` in orange with the reason in the
right column - `(Ebene fehlt)` when no layer that holds a navgraph is in the layer mask `[0x88e454]` (nav.mask 1),
`(nur mit Flaechen)` for connectivity / normals without planner_areas(_solid) - the conditions of NavSet's log notes,
read only (`NavRowNote`). The other action rows of the bar were checked: none else flips a readable flag (setters with a
fixed value - `dbg.flatcolour`, `dbg.namefilter` / `namecolour` / `namesize`, `dbg.cpall 0` / `1` - stay action rows).

Checks: `tools\trumenu_ini_check.py` `check_0216` (FlightHint key, page / row limits, costume rows from the cycle list
and the records, debounce + wrap, refusal without a level, Y refused, flight line rule, one command path, toggle rows =
bool rows with a RadialOn state, NavRowNote read only; 22 negatives in `work\m0216_0711\make_negative.py`),
`tools\trumenu_quick_check.py` models `cosbar`, `cosdebounce`, `flighthint`, `quickcmd`, `togglerows`.

### TO TEST 0.21.6 (owner)

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.6 (` |
| 2 | main menu: bar (View + Start), RB to page **Kostueme** | rows grey, right column "braucht ein Level"; right on "Kostuem" = refused with the reason |
| 3 | in a level: page Kostueme, head line | "aktuell: <costume> - N im Wechsel, M Spieler-Records" |
| 4 | "Kostuem": right 5 x quickly | the name steps (wraps at the end), Lara changes **once** about 0.5 s after the last press; `TruMenu.log` one `quick: Kostueme / Kostuem -> costume.set` line |
| 5 | "Kostuem": left once, then X at once | switches at once (no 0.5 s wait) |
| 6 | "[+] Alle Kostueme": right, then right on a DLC costume | list opens (`f Casual Explorer (dlc_costume_f)` style names), the costume is worn, marked "aktuell" |
| 7 | Y on a list row / on "Naechstes Kostuem" | refused "Kostuem-Zeilen sind kein Favorit" / pinned (page 1) |
| 8 | "Fuers naechste Laden + neu laden": right to a record, X, X | unit reloads with that costume |
| 9 | Lara page "Fliegen" on, close the bar | bottom right: "Fliegen: RT hoch \| LT runter \| Stick bewegt \| Tempo 20"; with the sound list on (br) the line sits above it |
| 10 | open the long menu | the line disappears; Cheat page: hover the flight button = the keys as tooltip |
| 11 | `[Cheat] FlightHint=0`, restart, fly | no line |
| 12 | bar open, L3 alone; type `get cheat.speed`, Enter | command line right of the bar; answer `ok cheat.speed = 20`; `cmd (quick):` line in the log |
| 13 | D-pad up, A | the last line again from the history, runs |
| 14 | L3 + R3 with the bar open | long menu opens, the command line does **not** toggle (and closes) |
| 15 | B | command line closes, the game never saw A / B / L3 |
| 16 | page Render-Details, group Navmesh: "Navmesh Flaechen" right, right, left | `an`, "schon an", `aus`; X toggles |
| 17 | "Navmesh Flaechen" on with "Alle Ebenen" off in a level whose navgraph layer is not in the mask | `an` orange, right column "(Ebene fehlt)"; "Alle Ebenen" on = white `an`, no reason |
| 18 | group Flach-Ansicht: "Pass 0x200" left / right | `aus` / `an` as the flat view's mask (`dbg.render`) |

## TruMenu 0.21.7 (footer / help, umlauts, refused costumes, chapter units, uber / shader / navmesh labels; 2026-11-07)

Night build after the owner's live test of 0.21.5 / 0.21.6 (`docs\Autopilot-2026-11-07.md` from 20:38). Build
`work\asi\menu0217`; 85 new byte checks (three read-only label layers, the SweepAndPrune read-out), no new hook,
imports / exports unchanged.

**Bar footer.** The X / Y line says `Y: -` where Y is refused (`QbFavOk` = the rule of `QbFavPin`: one item without an
argument - page Fixes, costume, chapter-unit, position / checkpoint / save rows and rows with an argument), adds
`L3: Befehlszeile` (EN `cmd line`; the `[Cmd] FocusButton` name, only with `[Cmd] Enabled=1`) and, while the game is
not calling PadHook (the pad is read in Present: front end / loading), `(Pad NICHT gesperrt)` in orange.

**Help line** (TODO "kurze Hilfe-Zeile"): rows that are not self-explanatory have one line "DE|EN" of at most 60
characters per language - the bar's footer (a third line while the row is selected) and the long menu's tooltip. Bar
rows: table `kQbHelp` keyed by item + argument (`*` = any argument; 46 rows: Navmesh / Render-Details / flat view,
debug view, flight, triggers, time / sound, costume.next, chapter starts, the new label layers). Page Fixes: the hint
column of `TruMenu.switches.txt` is now `<DE help> // <EN help>` (each at most 60 characters). Costume and chapter-unit
rows have their own lines (a refused costume says why).

**`TruMenu.switches.txt` with umlauts.** UTF-8 without BOM (a BOM is skipped anyway); the German texts use their umlauts
(`Doppelgängerin`, `Kostüm`, `Söldner`, `Zustände` ...), plugin / section / key / type / when / default stay ASCII. The
bar font (ImGui's built-in ProggyClean, range 0x20 .. 0xFF) has the glyphs - `work\m0217_0711\font_glyphs.py`
decompresses the embedded font and finds outlines for ä ö ü Ä Ö Ü ß. Texts cut by a field limit lose at most the
partial last character (`SwCopyText` / `Utf8TrimTail`). 114 switches now (+ TruShadowHud 0.2 `TranslateDlc2F1`;
TruShadowPower 0.20 `CameraFlag` default 1 - both from tonight's plugin builds, rows from the coordinator). The code's own texts stay ASCII (no `/utf-8` in the build).

**Costumes the game refuses** (live 21:14: object 33 "refused by the game's check 0x005c54e0 (no .drm?)"): while page
Kostueme is shown, `CosValidTick` runs that check once per changed cycle list on the game thread (the pad hook's
once-per-frame block, where `costume.set` runs it too); refused entries are grey ("abgelehnt (keine .drm?)"), the
`Kostuem` row's left / right passes over them, right / X on one is refused, the head line counts them, one log line
`costumes: N cycle-list entries checked ..., K refused`. No new write path.

**Page Kapitel: units per chapter** (TODO "Abschnitte je Level"): below the chapter starts one foldable group per chapter
/ DLC with its units from the level list (`kUnits`, 111 units in 10 groups; one group open at a time). A unit row runs
exactly what a chapter row runs - right / X twice within 3 s = `save.backup kapitel`, then `level.load <unit>` (debug, no
story values). DLC 2 units other than `dlc_level2_start` are orange with "Doppel-Zustand?" and the confirmation says
"Doppelgaengerin evtl. nicht aufgesetzt (besser DLC-2-Start + laufen)". Lara's unit is marked "Lara hier".

**Uber labels** (`dbg.uber`, bar page Leveldaten "Tore / Plattformen (Zustand)"; `uber.dump`; `[Debug] UberLabels /
UberRadius 8000 / UberMax 12 / UberMatch switch,lever`): every instance with an uber state (the engine's path 0x4d5d59:
`[[inst+0x2d0]]+0x2ec - 0x10`, magic 0xF0012345) within UberRadius of Lara - independent of LabelMatch / LabelRadius
(the dlc_caverns_hall gates stood 3165 / 3357 units away, LabelRadius was 3000) - gets "<object> <intro> | <distance>"
and its state: the node name, for a timed transition (condition 1 = time in node, 0x4d3204) the time left, for a running
transition the target. Gates (object name holds "gate"): `Tor: oben, noch 12 s` / `Tor: faehrt runter` / `Tor: unten,
bereit in 1.5 s` / `Tor: unten, bereit`. Instances matching UberMatch without an uber state get a plain label.

**Shader labels** (`shader.labels`, `shader.dump`, `shader.reload`; bar page Render-Details group "Shader-Etiketten";
`[Shader] Labels / File / LabelRadius 15000 / LabelMax 40 / ShowOrig`; stage S1 of `docs\Befund-Shader-Etiketten-0711.md`
section 4): terrain batches of `TruMenu.shaderlabel.txt` (written by `tools\shader_labels.py build`, generated locally,
`Set-TruMenu.ps1` installs it from the build folder when present) whose owner unit / streamgroup is loaded, nearest to
Lara by box distance, one per material within 2000 units. Line 1: material, file status, slots, PC libs, terrain section;
line 2: the **live** state - the material's `PCMaterial` from the game's hash map, its four lib pointers, their ids from
the lib hash map: `live = Datei` or `live PART S-TS 1909/-/2851/1911 (Datei SURR)`. Colour by the live status (SURR red,
PART orange, UNK violet, TU green, ORIG / BASE yellow; ORIG / BASE only with ShowOrig=1). Not built: the red tint per draw
(S2), `shader.pick` / `shader.aim`, object (O) and streamgroup (G) labels.

**Navmesh labels** (`nav.labels`, Render-Details group Navmesh "Navmesh beschriften"; `[Debug] NavLabels /
NavLabelRadius 3000 / NavLabelMax 40`; stage 1 of TODO "Navmesh beschriften"): at each area of the layers the planner
draws (the mask: "Alle Ebenen" = `nav.mask 1`) near Lara: `E<layer>.<graph> #<area> <unit>` and `27:x 26:x b8:x b12:x | n
Kanten` in the area's fill colour, plus one legend line of the engine's edge colours (0x40c3a0: light blue edge type
0x200, red bit 27 on either side, orange +0x34 bits 8..11 > 1, yellow bits 12..15 > 1, blue bit 26 differs, magenta bit 26,
green). Path: planner [0x8bf310] -> 32 layers -> 8 graphs -> area block `[g+0x1c]`, size `[[g+0x18]+8]`, stride 0x38 +
0x14 * edges. The unit name comes from an address test against the units' NavPower images (Level+0x60) - shown only when
it matches. Areas cut by obstacles are labelled as their static area. Not built: stage 2 (the NavPower text stub
0x6457a0), islands.

**SweepAndPrune read-out** (P6a; `sap.status` info, `sap.reset`; bar page Render / KI "Kanten-Kollision (SAP)";
`[Debug] SapWatch` default 1; `docs\Befund-SweepAndPrune-0611.md` section 4): the markup collision pool of the
MarkupManager `[0xdb94cc]` read every 250 ms (render thread, read only, the finding's chain with all its plausibility
checks - N 1000 / 3000, M 200 / 500, memory 1 + 204 N + 16 M, endpoints 2 b): boxes b / N, pair links p / 2M, proxies u /
1000 (list walk), session peaks, frames with a full pool, the warning mark ("Out of space for pairs / boxes" in 0xa035f0).
One `sap: new peak in <unit> - boxes ... pair links ... proxies ...` line per new peak (at most every 2 s). Decision rule of
the finding: boxes >= 800 or pairs >= 320 (80 %) or any full frame -> translate the TU constants.

**Front-end pad (research, not blocked):** the game reads the pad only through the XInputGetState pointer 0x00a02b8c (3
call sites: 0x482619 / 0x48620a device checks, 0x484b82 the per-frame poll) - no second input path. The miss in the DLC 2
mission menu is most likely PadHook not being called there (unproven - an archived run's main menu did call it; in the
Present fallback `QbPad`'s clear never reaches the game - the footer now says "(Pad NICHT gesperrt)"); 0.21.7 logs `quick: bar open while PadHook is not called ...`
and `quick: bar buttons 0x.... pressed while PadHook is not called - the game reads them too (diagnosis 0.21.7)` once per
bar opening - read only, nothing blocked yet (a block needs the live answer which hook chain the front end runs).

Checks: `tools\trumenu_ini_check.py` `check_0217` (+ the 0.21.7 rules of `check_switches`: UTF-8 / umlauts / hint halves;
33 negatives in `work\m0217_0711\make_negative.py`), `tools\trumenu_quick_check.py` models `yfooter`, `utf8cut`,
`cosvalid`, `uber`, `navwalk`, `chapters`, `shlive`; byte lists `work\asi\menu0217\precheck_0217_uber.txt` (8) /
`_shader.txt` (27, = `work\shaderlabel_0711\precheck_shaderlabel.txt`) / `_nav.txt` (30) / `_sap.txt` (20, =
`work\sap_0611\precheck.txt`).

### TO TEST 0.21.7 (owner)

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.7 (`, `0.21.7 uber labels: checks ok (8 rows)`, `shader labels: checks ok (27 rows)`, `navmesh labels: checks ok (30 rows)` |
| 2 | bar, page Fixes, a switch row | footer `X: ausfuehren  Y: -  L3: Befehlszeile`, help line in blue (e.g. "Schadensarten 17-27 wie TU ..."); group names with umlauts (Doppelgängerin, Söldner) |
| 3 | page Render-Details, "Navmesh Flaechen" | help "Umrisse der Gegner-Laufflaechen - braucht 'Alle Ebenen'"; on a plain item row (e.g. "Alle Ebenen") `Y: Favorit` |
| 4 | page Kostueme in a level, open "Alle Kostueme" | refused entries grey "abgelehnt (keine .drm?)"; head line "N vom Spiel abgelehnt"; `TruMenu.log` one `costumes: ... refused` line; "Kostuem" left / right skips them |
| 5 | page Kapitel, group "Abschnitte DLC 2 ...", right on dlc_yggdrasil_hall02 | orange "Doppel-Zustand?", footer note "besser DLC-2-Start + laufen"; second right = backup + load |
| 6 | dlc_caverns_hall, Leveldaten "Tore / Plattformen (Zustand)" on | both gates labelled from the switches' platform; switch on: "Tor: faehrt hoch", "Tor: oben, noch 25 s" counting down, "faehrt runter", "unten, bereit in 2 s", "unten, bereit"; `uber.dump` lines |
| 7 | `TruMenu.shaderlabel.txt` installed, dlc_yggdrasil_end, Render-Details "Shader-Etiketten" on | red labels "23164 SURR S-SS 1909/-/1910/1911 [Gelaende 20969]" at the goo tube; line 2 `live = Datei` (installed tree) or `live PART S-TS ... (Datei SURR)` with the shader test copy; `shader.dump` block in the log |
| 8 | hall02, "Navmesh Flaechen" + "Alle Ebenen" + "Navmesh beschriften" on | legend line at the top; labels `E11.0 #n` with flag bits; the red / magenta areas show `27:1` / `26:1` |
| 8b | big DLC 2 rooms (end, machine room) / F2 flight, page Render / KI "Kanten-Kollision (SAP)" right | "Boxen b/N (Spitze ..), Paare p/2M ..." with the limits read from the core (PC 1000 / 400; 3000 / 1000 with TruRockVein 0.10 `[SweepAndPrune] Translate=1` - 0.21.8 adds "Grenzen ..."); `sap: new peak` lines in the log |
| 9 | DLC 2 mission menu: bar open, left, X | if X still starts the mission: footer "(Pad NICHT gesperrt)" and the log's "diagnosis 0.21.7" lines; if neither shows, PadHook was called and the leak is elsewhere (note the time) |

## TruMenu 0.21.8 (quick command line: suggestions, keyboard, history safety; favourites with an argument; story values; sound group sliders; 2026-11-08)

Night build `work\asi\menu0218` (TODO items "TruMenu 0.21.8", "kleine Befehlszeile ausbauen" (2) / (3), the history
accident of 2026-11-07 21:23:53 - `cheat.god 0` from the quick command line's history). 6 new byte checks (sound
groups), one check row moved, one second form accepted; no new hook, imports / exports unchanged.

**Byte checks next to other plugins' patches.** TruShadowCombat 0.6.5 H1 rewrites the call at 0x6203e4 (death check ->
`RegenListHook`); `kAkChecks` (ai.kill) now checks `{0x006203e9, "83c410 84c0 7417"}` (the bytes after the call) - it
passed before only because TruMenu.asi loads first. No other TruMenu check touches the 0.6.5 sites 0x6824b9 / 0x6826d3 /
0x65b181 or the vtable entries 0x85b104 / 0x85b0fc / 0x85b15c / 0x858c90 / 0x859160 (`work\m0218_0711\overlap_scan.py`).
TruRockVein 0.10 (`[SweepAndPrune] Translate`) rewrites 0x5be3a7 (create(3000, 500)) and 0x5be3c4 (field 500):
`SapCheck` accepts the retail row or its TruRockVein form (`kSapChecksTu`, only for the same row); `sap.status` says which
limits the core has ("Grenzen PC 1000/400" / "TU 3000/1000 (TruRockVein 0.10)"). `TruMenu.switches.txt` has the new
rows TruRockVein `[SweepAndPrune] Translate` and TruShadowCombat 0.6.6 `[Death] TranslateT5` / `TranslateVaulted` /
`TranslateVaultedClock` (live, `P1dReadSwitches`) - 125 switches. TruShadowCombat 0.6.6's patch sites (0x63ad82,
0x71d5cc, 0x63b421, 0x623fa2, 0x65a4a2, 0x64fdb9, 0x638d6f, 0x638e76, 0x638efb) touch no TruMenu check either.

**Quick command line (L3 in the open bar).**
- Suggestions: while a typed line has some, the menu bar's list (`CmdBuildSuggestions` + the shared `CmdSugRows`) is
  shown under the input (6 rows: id / value / label). Keyboard: Up / Down choose among them (else the history), Tab takes
  the selected (else the first), Enter on a selected one runs it - the menu bar's rules.
- On-screen keyboard: **Y** opens the 0.7 keyboard of the long menu - the same code, now with a target (`OskTarget`: the
  menu bar `g_oskMenu` or this line `g_oskQc`; `DrawOsk` / `OskInput` draw and steer whichever). Keys as in the menu: A
  type, X backspace, Y take suggestion, Start run, B back to the compact line (B again closes it), LB / RB rows, L3
  closes the line; an empty line starts on the history chips. While it is open the bar also keeps **Start** from the
  game (`kQcOskOwn`; in `QbPad` it is never a gated combo tap, so its release is not passed to the game). A real key
  switches back to typing (the characters are kept).
- Safety: the line a pad step put into the input is shown with its item label (`A fuehrt aus: cheat.god 0 - ...`) and,
  for a line of `kCmdDanger`, an orange "Vorsicht: ..." before anything runs. A pad run (A, the keyboard's Start / run
  key) of such a line only **arms**: red footer `ACHTUNG: <line> (<why>) - A nochmal in 2.4 s = ausfuehren`; the same line
  again within 3 s (`kQcArmMs`) runs it, any edit / history step disarms. Enter on the real keyboard runs at once (typed
  on purpose). `kCmdDanger` (one table): `cheat.*`, `player.invincible`, `player.die`, `level.load` / `start` / `reload`,
  `unit.go`, `pos.goload`, `regress.prepare`, `save.load` / `delete` / `restore` / `import`, `costume.reset` /
  `choosereset` / `setreload` / `choosereload`, `sw.set`, `sticky.set`, `fix.hall02`, `ai.kill`, `ai.remove`,
  `instance.remove`, `settings.reset`, `fav.reset`, `game.quit`. Reads never ask: `help` / `list` / `get`, info items,
  a value item without an argument (shows its value). Log `quick: '<line>' <why> - armed ...`.

**Favourites with an argument + star.** `[Favorites] Ids` entries are `<id>` or `<id>|<argument>` (argument without ',' /
'|', < 96 characters); old lists (comma or space separated) read as before, a TruMenu before 0.21.8 skips the new
entries. Y now pins rows with an argument: static rows (e.g. `dbg.flatpass 0x200`), page Fixes switches
(`sw.set|<Plugin>:<Section>:<Key>` - on page 0 the switch row itself with its value, right / left / X as on Fixes),
costume list rows (`costume.set|<id>`), chapter units (`level.load|<unit>` - on page 0 with the chapter rows' right-twice
+ backup). Group / chooser / position / checkpoint / save rows still refuse Y. A row whose item + argument is a
favourite shows a yellow ` *` (every page). `fav.add` / `fav.del` take `<id> <argument>` (or `<id>|<argument>`); the
long menu's favourites page lists them (switches as their widget, others as a button; Y unpins), page Fixes: Y on a
switch pins it. A list that would not fit (1023 characters) is refused unchanged.

**Story values** (`story.values`, info; bar page Leveldaten "Story-Werte (nur lesen)" and Tests / hall02 group
"hall02-Werte (live)"): the known sticky values of Lara's level through the `sticky.get` read (`StFind` / `StValue`,
nothing written): hall02 dispatcher 11270 population / deaths / tutorial / wall (the `fix.hall02` keys), Croft Manor
dispatcher 4086 IsLevelZeroDone / IsL3_Reset_OK (Befund-Manor-Prolog row 4). `-` = no entry yet.

**Sound group sliders** (`docs\Befund-Ton-Gruppen-0611.md` sections 4 / 5; bar page Zeit / Test, group "Ton-Gruppen
(Lautstaerke)"; items `snd.group <Key> <0..100>`, `snd.groups`, `snd.vol.<key>`; `[SoundGroups] Ambience / Steps /
Weapons / Enemies / Lara / Objects / Dlc2 / Hud`, default 100, kept in TruMenu.ini): the eight proposed sliders (15; 32 +
78; 58 + 60 + 51 + 31; 27 + 65; 68 + 70 + 72 + 77; 43; 79; 54 .. 57). Game thread, next to the music mute: factor =
`*(float *)(cg + 0x38)` of the group's FMOD channel group, then FMOD's own recompute 0x7c4774; the game's group volume
(entry +0) is never written. A group whose ancestor (entry +0x68) is in the same slider is skipped (60 under 58); two
sliders on one path multiply. New channel groups after a level load are written again; 100 % puts the value from before
TruMenu back. Open (finding section 6): whether the factor is audible, whether the game writes cg + 0x38 itself.

Not built: Arachno 0.22 (occlusion = picture quads in the depth path with their own render-state patch condition, glitch
effects - `docs\Befund-Arachnophobie-Stufe1-Kamera-0611.md` 0.22-A / B; too large for this night and not testable
offline), the front-end pad block (research only until the 0.21.7 diagnosis lines were seen live).

Checks: `tools\trumenu_ini_check.py` `check_0218` (36 negatives `work\m0218_0711\make_negative.py`; the 0.21.7
negatives adapted in `make_negative_0217.py`), `tools\trumenu_quick_check.py` models `qcdanger`, `qcarm`, `favargs`,
`sgcover`, `qcsuggest`; byte lists `work\asi\menu0218\precheck_0218_sndgroups.txt` (6) and `precheck_0218_aikill.txt`
(62, the 0.21.1 list with the moved row).

### TO TEST 0.21.8 (owner)

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.8 (`, `0.21.1 ... checks ok`, `0.21.8 sound group sliders: checks ok (6 rows)`, `SweepAndPrune read-out: checks ok (20 rows, N in the TruRockVein 0.10 form)` (N = 0 while TruMenu.asi loads before TruRockVein.asi, as today; 2 if it ever loads after); with TruRockVein 0.10 on, `sap.status` ends "Grenzen TU 3000/1000 (TruRockVein 0.10)" |
| 2 | bar open, L3, type `cheat.g` | suggestions under the input (`cheat.god`, `cheat.godfull` with values); Down + Enter runs the selected one |
| 3 | D-pad up until `cheat.god 0` shows | blue `A fuehrt aus: cheat.god 0 - ...`, orange `Vorsicht: aendert einen Cheat ...` |
| 4 | A once | nothing runs; red `ACHTUNG: cheat.god 0 ... A nochmal in 3.0 s`; log `quick: 'cheat.god 0' ... armed` |
| 5 | A again within 3 s / after 3 s | runs (`cmd (quick): cheat.god 0`) / arms again |
| 6 | `get cheat.god` from the history, A | runs at once (a read) |
| 7 | Y in the open line | the menu's keyboard under the line; A types, X deletes, Start runs, B back, B again closes; Start does not pause the game |
| 8 | page Fixes, a switch, Y | `als Favorit angeheftet (Seite 1)`; ` *` after the name; page 0 shows the switch with its value, right / left / X switch it |
| 9 | page Kostueme list row / page Kapitel unit, Y | pinned with ` *`; on page 0 the unit row asks right twice + backup |
| 10 | TruMenu.ini `[Favorites] Ids` | `...,sw.set|TruShadowCombat:Death:TranslateNotify33,...` style entries |
| 11 | hall02, Leveldaten "Story-Werte (nur lesen)" | `Bev 1, Tote 0, Tutorial 1, Wand 0` (live values; kill a thrall: Tote / Bev change) |
| 12 | Zeit / Test, "Ton-Gruppen": Umgebung left to 0 near a waterfall / wind | ambience goes, footsteps stay; log `snd.group Ambience: group 15 factor 0.00 ...`; back to 100 = `back to 1.00` |
| 13 | Sonstiges (HUD) 0, then Lara-Stimme 0 | HUD / menu sounds off; Lara's breathing / hints off - note anything that stays (finding section 6) |
| 14 | level load with a slider below 100 | `new (level load) group ...` lines; the factor holds |

## TruMenu 0.21.9 (test spots, DLC units in play order with checkpoints, units without a DRM, goo / navmesh labels with meaning, B7, F11; 2026-11-08)

Night build `work\asi\menu0219` from the gap list `docs\Befund-17i-Menue-Luecken-0811.md` (data
`work\menu17i_0811\dlc_intros_all.txt`) and `docs\Befund-R17e-Goo-Navmesh-0811.md`. No new byte check (no new code
address is read: the goo label uses the 0.21.7 uber read path, the navmesh labels the bits of the area words they already
read), no hook, imports / exports unchanged, `TruMenu.ini` unchanged (= the 0.21.8 sample).

**`cp.jump <unit> <checkpoint intro>`** (new action item, not on the game thread): one shortcut of the 0.8.1 runner -
`save.backup kapitel;unit.go <unit>;wait.unit <unit>;dbg.cpgo <id>`. `unit.go` decides when its step comes (Lara in the
unit: nothing; loaded with a stream portal: flight + portal; else `level.load`); `dbg.cpgo <id>` as a shortcut step now
runs its two steps in place (`cheat.flight 1;player.goto <id>`, `ShortcutTick`) instead of starting a second shortcut over
the running one (`dbg.cpgo active` stays a command). Refused: a unit not in the level list, a unit without a DRM, a
pending level change. In `kCmdDanger` (the quick command line asks twice).

**Page Tests: test spots** (group "Teststellen (rechts 2x)"): "End-Szene (020_ghoul)" = `cp.jump dlc_yggdrasil_end 9608`
(help: CP 9608 lies most likely inside trigger volume 10026 - the cutscene 020_ghoul starts at once), "Boden 25057 (CP
9970)" = `cp.jump dlc_yggdrasil_end 9970` (the nearest data checkpoint, ~1300 units from the floor spot), "Zeremonienraum
030_pod" = `level.load dlc2_ceremony_room` with backup. Not in the tour file: `trumenu_ini_check.py` counts 256 of 256
ring entries with the built-ins (`kRadMaxItems`), new tour entries would be dropped - and the ring is frozen since 0.21.5.

**Units without a DRM** (17i: `dlc_level1_left` / `dlc_level1_right` are in unitlist.txt, also on the Xbox, but no DRM
exists): at start every DLC 1 / DLC 2 unit of the level list is checked once against `<tru.exe folder>\mods\<unit>.drm`
(log `0.21.9 units: 23 DLC 1 / DLC 2 units checked ..., 2 without a .drm: dlc_level1_left, dlc_level1_right`). Such a
unit is grey "keine .drm / nicht ladbar" on page Kapitel and in the long menu's level list, its command-line value says
"no .drm in mods", Y does not pin it, and `level.load` refuses it (`LoadUnit`). Base-game units (bigfile) and the other
DLC starts are never marked (0.21.10: the other DLC starts are marked too - section "TruMenu 0.21.10").

**Page Kapitel: DLC 1 / DLC 2 in play order with checkpoints** (`kChapOrder`, every id from `dlc_intros_all.txt`,
objects 83 `checkpoint` / 1036 `dlc2_checkpoint`, ordered by their +0x52 index): DLC 2 level2_start (4 CP) -> hall01 (1)
-> hall02 (3) -> end (4) -> ceremony_room (9) -> "-- Rundweg (Richtung nicht in den Daten)": machine_ceremony (7) /
machine_room (18) / goo_machine (3) / goo_room (10) / ceremony_goo (5), each "(Rundweg)" -> treasure_room_cine; DLC 1
level1_start (1) -> caverns (3) -> caverns_hall (1) -> water_wheel (3) -> pillory (6) -> dungeonhalla (3) / dungeonhallb
(3) -> watertunnel (1) -> dungeon (7) -> treasureroom, then the two units without a DRM. A unit row shows `[+] 4 CP`;
**left** opens its checkpoint rows (one unit at a time, "rechts 2x, links: CP"), a checkpoint row "CP 9608" runs `cp.jump
<unit> <id>` on right twice (end / 9608 says "020_ghoul sofort"). Right on the unit row = backup + `level.load` as
before. Page rows with the biggest unit open: at most 50 of 64.

**Goo drip label** (`dbg.uber`, `uber.dump`; only objects 926 `dlc2_uo_goo_drips` / 937 `_sml` and only when the live
graph has 8 nodes with node 3 "goo_off" - DTP 24411 / 24872): `goo: leicht, naechster Tropfen 0.3 s` (easy: drop on
entering node 4, every 0.7 s), `goo: leicht (Startpause), naechster Tropfen 2.1 s` (node 7, 4 s), `goo: hart (ohne
Ausgang), naechster Tropfen 0.2 s` (nodes 1 / 2: drops at 0.3 / 0.6 s; no command leaves hard), `goo: ..., Tropfen
jetzt` (the auto nodes 0 / 5), `goo: aus (Befehl 0 = hart / 1 = leicht)` (goo_off), `goo: ein Tropfen, dann aus`
(spawn_one). Rest = `[trans+0x1c] - [b+0x88]` of the node's timed transition (condition 1), as the 0.21.7 gate label.

**Navmesh labels / legend with meaning** (`nav.labels`; ENGINE.md section 15): line 1 `E<layer>.<graph> #<area> <unit>
Insel <n|->` (+0x30 bits 7..16, 0x3ff = none), line 2 `gesperrt (Hindernis) custom (handgebaut) | Strafe x3 / fest x1 | 5
Kanten | 27:1 26:1` (bit 27 = blocked by an obstacle, runtime; bit 26 = custom, else `auto`; +0x34 bits 8..11 obstacle /
12..15 static penalty multiplier, shown when one is above 1). The legend wraps into rows that fit the screen: "rot Bit 27 =
von Hindernis gesperrt (Laufzeit)", "orange ... = Hindernis-Strafe", "gelb ... = feste Strafe", "blau Bit 26 verschieden
(custom / auto)", "magenta Bit 26 = custom (handgebaut)", plus the hint row "lila / violette Flaeche ohne Etikett = wohl
dbg.enemycoll (Gegner-Kollision), kein Navmesh" (r17e 2b, still to be confirmed live).

**B7: the TO TEST switch note** (`test.toggle <id> ini:<Plugin>:<Section>:<Key>` and toggling it): instead of "INI: takes
effect at the next start" the note names the switch's "when" column of `TruMenu.switches.txt` (`SwWhenNote`): "INI: live
(~1 s, TruMenu.switches.txt)", "INI: after a restart (...)", "INI: live while <Key>=1 (now 0), else after a restart
(...)", or "not in TruMenu.switches.txt - when it takes effect is unknown". No new switches row.

**F11**: the bar's default key line ends with `F11: Foto + Marke` while `[Shot] Enabled=1` and a `[Shot] Hotkey` is set
(0x7A in the installed INI; another key shows as `F<n>` / `0x..`), and the shot rows (page Lara "Foto mit UI" / "Foto
sauber", the shot rows of the other pages) have the help "Foto jetzt; Taste F11 ([Shot] Hotkey) = Marke + Foto".

**`Set-TruMenu.ps1 -ShaderLabelFile <path>`** (Install only): installs that file as `TruMenu.shaderlabel.txt` instead of
the build folder's one (e.g. `work\shader17c_0811\trumenu\<variant>\TruMenu.shaderlabel.txt`); the first line must be
`# shaderlabel v1`, checked before anything is copied. Without it nothing changes. `$earlierBuilds` now knows the 0.21.7
/ 0.21.8 builds and sample INIs (the installed 0.21.7 asi would otherwise be "not a build of ours"). `work\asi\menu0219`
holds no shader label file - pick a variant with the parameter (or the old one stays installed).

Checks: `tools\trumenu_ini_check.py` green (check_0218 now reads its part of the version line, as check_0217);
`work\asi\menu0219\check_0219.py` (CP ids = data, play order, test spots, the DRM list against the game's mods, the goo
graph against the r17e dumps, a ShortcutTick model of cp.jump, source rules) with 10 negatives
(`make_negative_0219.py`); `tools\trumenu_quick_check.py` all ok.

### TO TEST 0.21.9 (owner)

Install: `.\scripts\windows\Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu0219 -ShaderLabelFile
.\work\shader17c_0811\trumenu\<variant>\TruMenu.shaderlabel.txt` (game closed).

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.9 (`, `0.21.9 units: 23 DLC 1 / DLC 2 units checked ..., 2 without a .drm: dlc_level1_left, dlc_level1_right` |
| 2 | bar, page Kapitel, group "Abschnitte DLC 1 ..." | play order level1_start .. treasureroom; `dlc_level1_left` / `_right` last, grey "keine .drm", right = "keine .drm in mods - nicht ladbar"; `menu level.load dlc_level1_left` = "refused: ... no .drm in mods" |
| 3 | group "Abschnitte DLC 2 ...", left on `dlc_yggdrasil_end  [+] 4 CP` | rows CP 10036 / 9953 / 9970 / 9608 below it; CP 9608 "020_ghoul sofort"; the ring units under "-- Rundweg" with "(Rundweg)" |
| 4 | CP 9970: right, right | backup, then (not in end) level.load or portal, Lara flies to CP 9970; log `shortcut 'CP 9970 (dlc_yggdrasil_end)' ... dbg.cpgo -> cheat.flight 1;player.goto 9970` |
| 5 | page Tests, "End-Szene (020_ghoul)" right twice | help line "CP 9608 liegt wohl im Trigger 10026 ..."; Lara at CP 9608, 020_ghoul starts at once (note whether it does) |
| 6 | page Tests, "Boden 25057 (CP 9970)" / "Zeremonienraum 030_pod" | Lara at CP 9970 (floor 25057 ~1300 units away) / ceremony room loads after a backup (does 030_pod play?) |
| 7 | end room, Leveldaten "Tore / Plattformen (Zustand)" on, near the light columns | goo drips: `goo: leicht, naechster Tropfen 0.x s` counting down (or `goo: aus (Befehl 0 = hart / 1 = leicht)` as on 07.11.); note every change while the fight runs |
| 8 | hall02 / DLC 1 caverns, "Navmesh Flaechen" + "Alle Ebenen" + "Navmesh beschriften" | legend in rows with the meanings and the violet hint; labels `... Insel n`, `custom (handgebaut)` (DLC 1 caverns) / `auto`; then toggle `dbg.enemycoll`: does the violet ramp go away? |
| 9 | `menu test.toggle x ini:TruShadowCombat:Death:TranslateT5 x` (any live row of page Fixes) | TO TEST row note "INI: live (~1 s, TruMenu.switches.txt)" instead of "takes effect at the next start"; a restart row says "after a restart" |
| 10 | bar open on a row without its own key line; page Lara "Foto sauber" | key line ends with `F11: Foto + Marke`; help line "Foto jetzt; Taste F11 ..."; F11 = a Claude mark + clean shot as before |
| 11 | shader labels in end (Render-Details "Shader-Etiketten") | labels from the variant given to `-ShaderLabelFile` (compare a `shader.dump` block with the variant's notes) |

## TruMenu 0.21.10 (unused DLC slots 3 - 6 and left / right: proven without data, grey, refused with the engine's reaction; 2026-11-08)

Build `work\asi\menu0220` from package 17s (`work\units17s_0811\PROGRESS.md`; 17p Q4 `work\q17p_0811\PROGRESS.md`). No new
hook, no new byte check (the start-up scan is file tests only), imports / exports = 0.21.9, `TruMenu.ini` unchanged (=
the 0.21.8 sample).

**Why these six are grey.** `dlc_level3_start` .. `dlc_level6_start` and `dlc_level1_left` / `_right` have **no data
anywhere**: no archive index holds them (PC bigfile / patch, Xbox layer1 / layer2 / TU, packs 10 / 11 / 1 / 2 / 20; 6
units x 8 path forms x 4 prefixes by name hash, with positive controls `l1_seatop`, `dlc_level1_start` /
`dlc_level2_start`, `dlc_levelN_preview.raw`), and a plain search through every record (25.2 GB decoded) plus the
installed mods tree, the B270 kit, tru.exe and the Xbox exe images finds the names only in generalbank (scripts 6 / 104),
`objlist.dat`, `unitlist.txt`, the kit manifest (preview image names) and the TU exe. Every unit DRM names itself (2 - 10
times), so a renamed copy would have been found. The retail mission screen (generalbank script 104) only adds a slot when
`dlcsystem` f1 finds `dlc_levelN_start.drm` (function 7, `uimenu` f25), so slots 3 - 6 never appear; their data in the
game are placeholders only: names 452 - 455 "DLC Mission 3" .. "6", descriptions 458 - 461 "Unavailable", preview
images `image\dlc_level3_preview.raw` .. `6` = 64 x 36 "M 3" .. "M 6" (Xbox 64 x 64), error text 464 "ERROR : Cannot find
selected DLC level pack." (DE "FEHLER: Das ausgewählte herunterladbare Level Pack konnte nicht gefunden werden.").

**What the engine would do on a load (static, tru.exe, 17s task 2).** `level.load` (`GAMELOOP_RequestLevelChangeByName`
0x5df8c0) and the mission start (`uigamedata` f27 0x77e170 -> 0x5dfb20) both end in 0x5dded0 -> `STREAM_LevelLoadAndInit`
0x5d30d0 -> `STREAM_LoadLevel` 0x5d23f0, which builds `pc-w\<unit>.drm` (0x477970, `%s%s.drm`) and requests it (0x551470)
**without an exists test** (only `STREAM_LoadOverlayUnit` 0x5d2610 has one). The file system (MultiFS, vtable 0x8440ec)
sends a name no archive has to its slot 0 (`GetFS` 0x473560: miss -> index 0; the patch archive is mounted at the front,
0x478997), whose `RequestRead` 0x472890 finds nothing (lookup 0x4726e0 -> 0) and calls the fatal-error path 0x596cb0
with **"Can't open file pc-w\<unit>.drm"** -> 0x478b00: window hidden in full screen, the game's error dialog
(`DialogBoxParamW`, template 0x7d) -> 0x478a10: `ExitProcess(0)` (main thread) / `TerminateProcess` (other threads).
So: no fallback to the menu, no hang, no crash dump - an error box, then the game is gone (unsaved progress lost).
ModLoader's own file system layer is not read (it hooks 0x472c50 / 0x472b31 / 0x478930 / 0x49a84f by signature); if it
answered a miss itself the message could differ (🔶). No safe load path exists, so nothing is offered behind a
confirmation.

**Changes.**
- `kUnitsNoData` (the six) and `UnitUnused` (one of the six **and** no `mods\<unit>.drm` - a file built later would load).
  `UnitDrmChecked` also file-tests the group "DLC other starts" (dlc_level3..6_start), so the start-up line is now
  `0.21.10 units: 27 DLC units (DLC 1 / DLC 2 / slots 3 - 6) checked against ...mods\<unit>.drm, 6 without a .drm:
  dlc_level1_left, dlc_level1_right, dlc_level3_start, dlc_level4_start, dlc_level5_start, dlc_level6_start, 6 of them
  unused slots without data (17p / 17s; grey, level.load / level.start refuse them)`.
- **Page Kapitel**: the last group is now "Ungenutzte DLC-Plaetze 3 - 6 + left / right" ("Unused DLC slots 3 - 6 + left /
  right", head column "keine Daten (17p/17s)") with six grey rows `dlc_level3_start` .. `dlc_level6_start`,
  `dlc_level1_left`, `dlc_level1_right` - state "ungenutzt", column "keine Daten (17p/17s)"; left / right stay at the end
  of the DLC 1 group with the same text. Help line (the footer's third line): "In keinem Archiv (17s); Laden:
  Fehlerfenster + Spielende" / "In no archive (17s); a load: error box + the game exits"; key line "ungenutzt - keine
  Daten (17p/17s), nicht ladbar"; right / X answers "ungenutzt - in keinem Archiv und nicht in mods (17p/17s); Laden =
  Fehlerfenster "Can't open file" + Spielende - nicht angeboten". Y does not pin them (0.21.9 rule).
- Long menu level list: the six are grey "(ungenutzt - keine Daten / unused - no data, 17p/17s)" with a tooltip naming the
  error box; command-line value "unused slot - no data (17s)".
- `level.load` and now also **`level.start`** refuse a unit without a DRM; for the six the answer is `refused:
  dlc_level3_start is an unused slot - no data in any archive or in mods (17p / 17s); the engine would stop with "Can't
  open file pc-w\dlc_level3_start.drm" (error box, then the game exits)`.
- Comment at `MissionSelectArg`: the TU exe's yes / no dialog accept path (`ScriptDialogYesNo::RegisterAcceptChanges`,
  0x8247f3b8 .. 0x8247f510, "Attempting to load level: %s") skips the outfit selection for `dlc_level2_start` ..
  `dlc_level6_start` (level 3 included, table 0x820760f8); not copied (no data for 3, the PC exe has no such strings).
- `Set-TruMenu.ps1`: `$earlierBuilds` knows the 0.21.9 asi (sha256 cf4f3871...), example `-SourceDir .\work\asi\menu0220`.

Checks: `tools\trumenu_ini_check.py` green (exit 0), `tools\trumenu_quick_check.py` all ok, `work\asi\menu0219\check_0219.py`
all ok (its version test now reads the 0.21.9 part), `work\asi\menu0220\check_0220.py` all ok (proof files, the table, the
mods tree, the exe bytes of the load / error chain, source rules) with 11 / 11 negatives caught
(`make_negative_0220.py`).

### TO TEST 0.21.10 (owner)

Install: `.\scripts\windows\Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu0220` (game closed; add `-ShaderLabelFile`
as for 0.21.9 if wanted).

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.10 (`, `0.21.10 units: 27 DLC units ... 6 without a .drm: dlc_level1_left, dlc_level1_right, dlc_level3_start, ... 6 of them unused slots` |
| 2 | bar, page Kapitel, last group "Ungenutzte DLC-Plaetze 3 - 6 + left / right" | 6 grey rows "ungenutzt" / "keine Daten (17p/17s)"; help line "In keinem Archiv (17s); Laden: Fehlerfenster + Spielende"; right = the refusal text, nothing loads |
| 3 | group "Abschnitte DLC 1", last two rows | `dlc_level1_left` / `_right` grey with the same texts |
| 4 | `menu level.load dlc_level4_start`, `menu level.start dlc_level5_start` (main menu) | both `refused: ... unused slot ... "Can't open file pc-w\..."`; the game keeps running |
| 5 | long menu, Levels, group "DLC other starts" | the four grey with "(ungenutzt - keine Daten ...)" and the tooltip |
| 6 | DLC mission menu (retail screen) | only "UNTER DER ASCHE" and "LARAS SCHATTEN" listed (slots 3 - 6 are never added) |

Not to test: a real load of one of the six - it would end the game (see above). If the owner wants the engine's reaction
seen once: a throw-away session, windowed (TRAWindowed), save backed up, TruTrace on (it logs `STREAM_LevelLoadAndInit`
0x5d30d0 before the box), cdb with breakpoints on 0x596cb0 (log the format + name) and 0x478a10; load through the 0.21.8
asi (no refusal) or `GAMELOOP_RequestLevelChangeByName` from cdb. Expected: the box "Can't open file pc-w\dlc_level3_start.drm"
(note its title / buttons), then the process ends with exit code 0.

## Switches data 2026-11-08: group "Komfort (TruQoL)" (TruMenu binary unchanged 0.21.10; `work\asi\menu0221`)

Data only: `TruMenu.switches.txt` gets the group `truqol` "Komfort (TruQoL)" / "Comfort (TruQoL)" with the 10 keys of
the player plugin TruQoL 0.1.1 - live: `[TruQoL] LogLevel`, `[FrameLimit] Enabled` / `MaxFps` (choice 30 .. 144) /
`AutoOff` / `SpinUs`, `[Camera] Fov` (choice `0,0.9,1.0,1.1,1.15,1.2,1.3`) / `FovCutscenes` / `ShakeScale` (choice
`0,0.25,0.5,0.75,1.0`); restart: `[TruQoL] Enabled`, `[Startup] ThreadCap`. Float keys are `choice:` rows of exact INI
texts - `SwChoiceHas` compares text, so `1.0` is a value of its own (an INI holding `1` shows `1`; right / X then goes
to the first choice, left to the last). No code change: the parser takes any `Tru<name>` plugin with an INI next to tru.exe; now 135
switches in 10 groups (limits 160 / 24), page Fixes at most 37 rows (`kQbViewMax` 64); the ring stays frozen.
`tools\trumenu_ini_check.py` knows TruQoL (`SW_PLUGINS`, `SW_LIVE` -> `LiveReadOptions`) and accepts a dot in choice
values. `work\asi\menu0221` = the menu0220 files + the new switches file; checks `work\qol17y_0811\check_0221.py`
(+ 14 negatives). TruQoL's `[Camera] ShakeScale` below 1.0 makes TruMenu's own `cam.shakescale` refuse ("another
plugin?"); back at 1.0 TruQoL gives the two calls back - move TruMenu's slider once more to retry.

TO TEST (owner, with TruQoL 0.1.1 installed): page Fixes, group "Komfort (TruQoL)": `MaxFps` 60 -> 30 and back, `Fov`
1.2, `ShakeScale` 0.5 -> 1.0 - each takes effect within about a second (`TruQoL.log` one `live:` line each); the rows
`TruQoL an` / `Start-Fix ...` show "Neustart". Without TruQoL installed the group shows "keine INI" and writes nothing.

## TruMenu 0.21.11 (light.list / light.shadow for the flashlight shadow; page Rettung for players; 2026-11-08)

Build `work\asi\menu0222` from package 18d (`work\menu18d_0811\PROGRESS.md`, `finding_18d.md`; facts of 18b
`work\research18b_0811\finding_18b.md`, ENGINE.md section 16 "Shadow caster gate"). No new hook, imports / exports =
0.21.10, `TruMenu.ini` unchanged (= the 0.21.8 sample), ring untouched (`kRadMaxItems` 256 frozen, radial / tour files
unchanged). `TruMenu.switches.txt` = the source file at build time.

**Lights (section "0.21.11 lights").** The scene light list is proven statically (tru.exe 5560abac): `[0xa1407c]` = the
PCRenderDevice (vtable 0x8492cc), scene = device + 0xfdfc, every PCRenderLight sits in the array count `[scene+0x14]` /
data `[scene+0x1c]` from its ctor (0x50b120 -> push_back 0x5054f0) to its dtor (0x50b1e0 -> remove 0x504a10). 18b's
"scene+0x20, count +0x1020" is the per-frame list of light **instances** (`[E]` = the light, E+0x64 / +0x65 run-time
flags; reset to 0 by 0x504c50, so outside the device frame it may be empty). 18b's "device" `[L+0x1c]` is the light's
**PCLightResource** (vtable 0x8494ec): CastsShadow 0x50a080 = `(L+0xc5 & 4) && res+0x1878`, and RenderShadowMaps'
`vf1c()+0x144d` is res+0x1879 (res vf+0x1c 0x50a030 = res+0x42c). Before the first read TruMenu checks 13 byte patterns
and 4 vtable slots (`LtCheck`; a mismatch = "disabled: bytes differ at ...").
- **`light.list`** (action, game thread, read only): one `TruMenu.log` line per light - `light.list #3 0x0a1b2c40 type 1
  +0xc5 0x05 (bit 2 1) +0xc4 0 | res 0x0c3d4e00 +0x42c 1 +0x1878 1 +0x1879 (vf1c+0x144d) 0 -> CastsShadow 1 | frame E
  0x... +0x64 1 +0x65 1 | pos 120.0 -40.5 310.0 (Lara 85u) NEW` - plus a head line (count, frame list count, +0x1240 list
  count, EnableShadows `[[0xad75e4]+0x184]`). The answer is short: `#3 t1 s1 85u NEW; ... | 12 lights, 3 cast (s1), 1 NEW,
  frame 0, EnableShadows 1`. **NEW** = not in the previous `light.list`: list with the flashlight off, switch it on, list
  again - the NEW light near Lara is the flashlight. Position = row 3 of the light transform L+0x20 (L+0x50, 🔶 live).
- **`light.shadow <n|0x<light>> 0|1`** (action, game thread): SetCastShadows vf+0x4c 0x50a3a0 of light `n` of
  `light.list` (or its address); refuses an index out of range, an address not in the array, a vtable other than
  PCRenderLight 0x849594 and any value but 0 / 1; logs +0xc5 and CastsShadow before / after and says when res+0x1878 = 0
  keeps the light unshadowed anyway.
- What the result means (18b): bit 2 clear on the flashlight -> data / setter; bit 2 set and res+0x1878 = 0 -> the light
  resource (res+0x42c kind 0 clears +0x1878 in 0x50afb0); both set -> slice / budget (0x504f30, <= 16 slices) or
  EnableShadows 0 (then only the first light with res+0x1879 is shadowed).
- Bar page Render-Details, group "Lichter (Schatten)": "Lichter ins Log" (`light.list`), "Licht-Schatten ..." (opens the
  quick command line with `light.shadow `).

**Page Rettung / Rescue** (bar page 1, right after Favoriten / Zuletzt; long menu: section "Quick bar pages"): the
existing soft-lock helpers of finding 18b part D in one place, every row an item of 0.21.10 - no new game logic.

| Group | Row (DE / EN) | Item | Note |
|---|---|---|---|
| Festgesteckt / Stuck | Befreien / Unstuck | `player.unstuck` | |
| | Befreien (Marke) / Unstuck (mark) | `player.unstuck mark` | |
| | Befreien: Stand / Safe ground state | `player.safeground` | info |
| | Punkt merken / Mark here | `player.mark` | |
| | Zum Punkt / Back to mark | `player.recall` | |
| | Unit neu laden / Reload unit | `level.reload` | right / X twice (kQfConfirm; kCmdDanger) |
| Spielstaende / Saves | Saves sichern / Back up saves | `save.backup rettung` | folder `<time>_rettung` |
| | Sicherungen (Liste) / Backups (list) | `save.backups` | info |
| | Sicherung zurueck ... / Restore a backup ... | `save.restore` | line; kCmdDanger + its own double confirm |
| Objekte / Objects | Objekte suchen ... / Find objects ... | `instance.list` | line (name filter) |
| | Objekt zu Lara ... / Bring object ... | `instance.bring` | line (#index / intro id) |
| | Objekt einblenden ... / Unhide object ... | `instance.unhide` | line |
| Ausruestung / Gear | Gegenstand geben ... / Give item ... | `gear.give` | line (object name) |
| | Medipack geben / Give medipack | `gear.give g_healthpack` | |
| | Waffe geben / Give weapon | `weapon.give` | choice (the five ring weapons) |
| | Munition voll / Ammo fill | `ammo.fill` | |

Rows marked "line" (new row flag `kQfLine`; the label ends in "...") need a typed argument: right / X puts `<item> ` into
the quick command line and opens it (type the argument, A runs it through `CmdExecute` - `kCmdDanger` asks twice for
`save.restore` / `level.reload` as for every line); in the long menu the button puts the line into the command bar and
focuses it. Y refuses them (a favourite without its argument would only answer "usage"). Every row has a help line
(`kQbHelp`, DE / EN <= 60 characters each).
Limits: 17 bar pages now (`g_qbRow[17]`, `static_assert(kQbPageN <= 17)`; was 16 - full), `kQbStartPage` 6 = still
Leveldaten; page Rettung 20 rows, Render-Details 43 (`kQbViewMax` 64); `tools\trumenu_ini_check.py` (`QB_PAGES_MAX` 17,
`kQbRescue` in `QB_TABLES`) and `tools\trumenu_quick_check.py` (cosbar: 17 pages) follow the new limit.

`Set-TruMenu.ps1`: `$earlierBuilds` knows the 0.21.10 asi (sha256 148066e8...), example `-SourceDir .\work\asi\menu0222`.

Checks: build 0 warnings (/W4, TruMenu.cpp; the 2 C4100 of imgui_demo as before), `tools\trumenu_ini_check.py` exit 0,
`tools\trumenu_quick_check.py` all ok, `work\menu18d_0811\check_0222.py` all ok (exe proof + LtCheck patterns / slots
against the exe, light rules, page Rettung, ring, source, folder) with 22 / 22 negatives caught (`make_negative_0222.py`);
`work\asi\menu0220\check_0220.py` / `menu0219\check_0219.py` all ok (0220's version test and its negative now read the
0.21.10 part).

### TO TEST 0.21.11 (owner)

Install: `.\scripts\windows\Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu0222` (game closed; add `-ShaderLabelFile`
as for 0.21.9 if wanted).

| # | Step | Expected |
|---|---|---|
| 1 | game start | `TruMenu.log`: `TruMenu 0.21.11 (` |
| 2 | in a level, flashlight OFF: `menu light.list` (or bar Render-Details "Lichter ins Log") | answer `... N lights, S cast (s1) ...`; per light a `light.list #i ...` line; no "disabled: bytes differ" |
| 3 | flashlight ON, `light.list` again | one (or more) light marked `NEW`, a few units from Lara (`(Lara <d>u)`); note its line: +0xc5 bit 2, res+0x1878, +0x1879, CastsShadow, frame flags |
| 4 | `menu light.shadow <n of the NEW light> 1` | `cast bit 1 (+0xc5 0x.. -> 0x..), CastsShadow x -> y`; does a flashlight shadow appear? (if "res+0x1878 is 0" - resource side, note it) |
| 5 | `light.shadow <n> 0`, then `light.shadow 999 1`, `light.shadow 0x12345678 1` | shadow gone again (if it came); refused: "index 999 out of range" / "not in the scene's light array" |
| 6 | bar: RB once from page 0 | page "Rettung" with the four groups; help line under each row |
| 7 | Rettung "Objekt zu Lara ..." right | quick command line opens with `instance.bring `; type `#<n>` from "Objekte suchen ...", A = object at Lara |
| 8 | Rettung "Unit neu laden" right once / twice | first: arms (footer), second within 3 s: reload |
| 9 | Rettung "Sicherung zurueck ..." | line `save.restore `; type a folder of "Sicherungen (Liste)"; A asks twice (kCmdDanger), then the restore's own confirmation |
| 10 | long menu, Quick bar pages, "Rettung / Rescue" | same rows; the "..." buttons fill the command bar |

## TruMenu 0.22 (cutscene pause: cine.pause / cine.step / cine.status; 2026-11-08)

Build `work\asi\menu0223` (TODO N12; facts: `docs\Befund-Szenenpause-0811.md` of the workspace, ENGINE.md section 3
"Cinematic stream clock"). Asked for to look at the flicker at the throne in the DLC 2 end cutscene: hold the cutscene
only, while the world goes on. `TruMenu.ini` unchanged, ring untouched, no new import.

**How (section "0.22 cutscene pause").** Every multiplex stream (a cutscene is one: animation and sound in one stream
object) is advanced once per frame by a list walk: head `[0xccdc64]`, update 0x5901a0 (thiscall, float dt) returns the
next stream `[obj+0x14]`; the walk exists twice, its calls are 0x5904e3 / 0x5954f8. For a cutscene stream
(`[obj+0x77c]` = its cinematic handler, `[obj+0x18]` = 4 playing) the update reads the stream file, feeds the sound
ring (its sample counter is the cutscene clock), sets the cutscene time `[obj+0x384]`, plays the keys between the old
and the new time and runs the handler update. While `cine.pause` is on, the rel32 of both calls point to a gate that
skips the update of a playing cutscene stream only and returns its next pointer: cutscene time, actors and camera
stand still; world time, particles, shader time and lights run on; other streams (music, ambience) are untouched.
Patched on the game thread while the pause is on, put back when it is off; **off by itself** when the main state
`[0xe7ed60]` leaves 1 (a load). Before the first use 7 byte patterns are checked (a mismatch = "disabled: pre-check
failed"). Not used on purpose: the pause bit 0xe7f0b8 & 0x1000 (stops the instance updates, so the effects too) and
the capture mode 0xe7f0a4 & 4 (a fixed 1/30 s per frame, so double speed at 60 fps).

| Item | Kind | What |
|---|---|---|
| `cine.pause [0\|1]` | bool | hold / release a playing cutscene (no argument = toggle); needs a loaded level |
| `cine.step [n]` | action | let n frames (default 1, at most 600) of the held cutscene through |
| `cine.status` | info | the stream list: the cutscene stream (state, time, handler, sound), GameTracker cinematic `[0xe7f1c0]`, the pause |

Bar page **Tests**, group "Zwischensequenz": Szene anhalten (bool), Ein Bild weiter, Szenen-Strom (live). Log lines:
on / off, one "holds cutscene stream 0x... at time ..." per held stream, the held frames when it is released.

Open (live): what the sound does while held - the sound ring is not fed, so FMOD may play silence or repeat the ring;
whether the cinematic handler counts its own times that would jump on release.

### TO TEST 0.22

| # | Step | Expected |
|---|---|---|
| 1 | log after the first `cine.status` | `0.22 cine.pause: 7 checks ok` |
| 2 | in a level without a cutscene: `cine.status` | "no cutscene stream", a few streams (music / ambience) |
| 3 | DLC 2 end cutscene `020_ghoul` (bar Tests "End-Szene"), while it plays: `cine.pause 1` | picture of the scene stands, particles / lights move on; log "holds cutscene stream" |
| 4 | `cine.step` a few times, then `cine.step 30` | one frame / half a second of the scene each time |
| 5 | listen while held | note: silence or a repeating sound |
| 6 | `cine.pause 0` | the scene goes on from where it stood, sound in sync |
| 7 | held, then a load (level.load / checkpoint) | log "off by itself"; the load works |

Live 2026-11-08 (0.22, DLC 2 end-room cutscene at the throne): the pause works - the scene stands, torches and the
flicker go on, the stream is recognised (its handler = GameTracker cinematic). The sound looped: the stream's sound
ring is no longer fed and FMOD plays it again (fixed in 0.22.1). A TruLink `menu cine.pause` without an argument
flipped the pause (0.22.1: report only).

## TruMenu 0.22.1 (cutscene pause: sound held, badge, mark / pause at; 2026-11-08)

Build `work\asi\menu0224`, live wishes of the 0.22 test. `TruMenu.ini` unchanged, no new import.

- **Sound held with the picture.** The cutscene time is the sound position (the sample counter of the stream's DSP
  ring), so the sound must stop with it - else FMOD repeats the ring and on release the play cursor no longer matches
  the clock. The game's own "pause all sound" (0x587420 / 0x587460) pauses the master channel group:
  System_GetMasterChannelGroup 0x7b99b9 and ChannelGroup_SetPaused 0x7b9490 -> ChannelGroupI::setPaused 0x7c4875
  (flag +0x59, every child group and channel). While a cutscene is held TruMenu pauses the master group - only if it
  was not paused already, and it gives it back only if TruMenu paused it (the game's pause screen keeps its own).
  Music and ambience stand still with it.
- **Steps without drift.** `cine.step n` lets n game frames through with the sound running **muted**
  (ChannelGroupI::setMute 0x7c48cd, flag +0x58): the clock is the sound, so picture and sound move on together.
- **Badge** top centre while held: `||  Szene angehalten  <s> s  -  Ton angehalten` (EN with `quick.lang 1`); while
  stepping `> Bild weiter`. Seconds = `[obj+0x384]` / 30 (the cutscene time counts 1/30 s: dt x 30.0 `[0x8439b8]`,
  the sound path 0x5800d0 multiplies by the same constant).
- **`cine.mark`** remembers the playing cutscene's time (seconds); **`cine.pauseat [seconds|off]`** holds the next
  cutscene that reaches it (no argument = the mark) and stays armed over loads: mark, reload the checkpoint, the
  cutscene plays and stops at the same spot. No real rewind: the stream is read forward from disk, the cutscene fires
  one-shot events, and the clock is the sound.
- **`cine.pause` without an argument only reports** (the bar, the command bar and the menu always send 1 / 0).
- Byte checks: 4 more (`kCnSndChecks`); without them the picture pause still works and the badge says "Ton: Schleife".
- Bar page Tests, group "Zwischensequenz": + Stelle merken, Bei Marke anhalten.

Live 2026-11-08 (20:44 - 21:08): the first build released and paused the sound every 30 - 130 ms (unsigned tick
difference, fixed); the master group alone did not hold the cutscene line - the sound category groups form their own
tree (master: 12 plain channels, no child group). The final build pauses the master group and the root of every
category tree (log: "2 channel group(s) paused"): silence while held, the line goes on exactly where it stopped, in
sync. Steps and `cine.pauseat` not yet tried live.

## TruMenu 0.22.2 (light.frame: per-frame light capture; 2026-11-08)

Build `work\asi\menu0225`. `light.frame [n]` (default 60, at most 600): while it runs, the rel32 of the frame end call
0x5098ca (the reset 0x504c50 of the scene lists, ecx = scene) points to a gate that records this frame's lists before
the reset: light instances (pointers scene+0x20, count +0x1020; 0x80 bytes each), the light behind each instance
(0x100 bytes, only when new or changed), light resources (scene+0x1024, count +0x11a4, slot R+0x1d18) and the third
count +0x1228. After n frames the game thread writes `TruMenu.lightframe.txt` next to tru.exe and puts the call back;
the file ends with one `S` line per light: frames present, instance / light byte changes, `BLINK?` when it was missing
in frames or changed in more than a quarter of them. 3 byte checks. Bar page Tests: "Lichter mitschreiben (60 Bilder)".

Played 2026-11-08 21:30 (DLC 2 end cutscene held at the throne): 14 lights, all in every frame; 4 torch lights change
their colour every frame (flicker, wanted), the 3 shadow-casting cutscene lights run a 5-frame cycle (instance +0x60
1, 1, 1, 2, 3; +0x78 0 / 1.0); with global shadows off the throne stood still - the flicker is their shadow rendering.

## TruMenu 0.22.3 - 0.22.5 (light.stable: steady scene light order, on by default; 2026-11-08)

`light.stable 1|0` (no argument = report). 0.22.3 sorted the scene lights in the visible-entity list before the light
pass 0x56d5c0 - never needed (0 of 111 frames), flicker unchanged. 0.22.4 sorts the light pass's own collected list
(+0x250, count +0x258) by address right after the collection loop: the 6 bytes `mov ecx, [esi+0x250]` at 0x56d69a
become `jmp LsStub` + nop (the stub saves all registers, sorts, runs the instruction, jumps back to 0x56d6a0), written on
the game thread only while on and only over the expected bytes, put back when off. **Played:** the collected order of
the 15 scene lights changed in every frame (112 of 112); with the switch the brightness of the lit figures stood still
(spread 13.9 -> 0.0, off / on / off) - cause of the end-cutscene flicker proven (ENGINE.md 16). The five cycling states
are different light combinations (warm torch light vs. a cool front light on Natla); the sorted order keeps one of them.
**0.22.5: on by default** - `[Light] Stable=1` (missing key = 1), the owner prefers a steady light set to the flicker
until the real fix (a stable order by weight, or the right weights in the DLC light data, checked against Xenia / the
Xbox original). The sort applies in every scene; `Stable=0` gives the game's own order. Bar page Tests: "Licht-
Reihenfolge fest (Flacker-Test)".

## TruMenu 0.22.6 / 0.22.7 (Steam overlay guard, umlauts, cutscene keys; 2026-11-09)

- **0.22.6 Present re-entry guard** (crash of 2026-11-08 with the Steam overlay: TruMenu's swap-chain Present hook and
  the overlay's d3d9 detour called each other until the stack overflowed): per thread the device and the swap-chain
  Present hook note that they run; a nested call draws nothing and goes straight to d3d9 behind the overlay's `jmp`
  through a trampoline that rebuilds the 5 hot-patch bytes (`mov edi, edi; push ebp; mov ebp, esp`), built only when the
  original starts with E9 and a function body follows; otherwise the nested call returns D3D_OK. One log line.
  Not yet tested with the overlay.
- **0.22.6 umlauts:** the German texts show umlauts; `tools/trumenu_umlauts.py` wrote 251 words of a fixed list as octal
  UTF-8 escapes inside the string literals (the INI option table stays ASCII).
- **0.22.7 cutscene keys** in `[Cine]`: `PauseKey`, `StepKey`, `ShotKey` (keyboard, virtual key code, hex or decimal -
  0x78 F9, 0x79 F10) and `PausePad`, `StepPad`, `ShotPad` (XInput masks pressed together - 0x0100 LB, 0x0200 RB, 0x0020
  View, 0x0010 Start, 0x1000 A, 0x2000 B, 0x4000 X, 0x8000 Y; e.g. 0x0120 = View + LB). Pause toggles `cine.pause`, Step
  = `cine.step 1`, Shot = `claude.mark now` (mark line + clean shot). Edges only; the game still gets the keys and
  buttons; the pad combos act only while neither the menu nor the ring owns the pad. All 0 by default. To use the
  8BitDo's R4 / L4: map them in the pad's own software to such a combo (the pad sends no own XInput bit for them).
- **0.22.8:** the pad combos are on by default - `PausePad=0x0120` (View + LB), `StepPad=0x0220` (View + RB),
  `ShotPad=0x0320` (View + LB + RB). Pause acts only while a cutscene plays or is held (a stray combo in normal play
  cannot arm the pause for the next cutscene), step only while held. The pause badge shows a second line with the keys /
  combos as set now (e.g. `LB + View = weiter . RB + View = 1 Bild . LB + RB + View = Foto`), built from the INI values,
  so it follows any change.

## 0.22.14 - sub.lang switches the shown subtitle lines at once (2026-11-10)

Built into `work\asi\menu0237`, not installed. Byte checks: `work\asi\menu0237\precheck_02214.txt` (13 checks, 0
mismatches against `data\pc\tru.exe` and the installed `tru.exe`); the 21 checks of 0.22.13 stay. Background: ENGINE.md
rows "Subtitle record format", "Subtitle line clock", "Subtitle language at run time"; workspace
`docs\Befund-Untertitel-Live-0911.md`.

Before, `sub.lang` changed only the profile word: the two lines in the subtitle box 0xccdec0 are finished copies, so the
old language stayed on screen until the next line - in a cutscene held by `cine.pause` (0.22.13 holds the line clock)
until the user stepped on.

- **Subtitle record (static, from the code):** the cinematic handler update 0x457100 copies a frame's subtitle text
  (at most 0xfff bytes, NUL at the end) to the static buffer 0x9ccfa0 and calls the reader 0x4538d0 with it (call
  0x4574ec). One record holds **every language**: `<id>\r<text>\r<id>\r<text>\r...` (ids 0 en, 1 fr, 2 de, 3 it, 4 es,
  11 nl in DLC 2). Per entry the reader takes `atoi` of the id, the text up to the next `\r` (**255 bytes at most**, the
  rest is skipped), and shows it when the handler's kind byte `[[ecx+4]+4]` is not 2 and (id == the profile word, or
  word -1 and id == the game language `[0x8906b8]` and kind 1). A shown entry is cut at `\n` (strtok) into lines; each
  line loses a leading `<speaker>: ` and goes to 0x583db0(box, line, 90) - **one record adds 0..n lines** (n = the `\n`
  lines of the chosen entry; usually 1). Text bytes are **UTF-8** (`tools/mul_sub_records.py`: 107 non-ASCII entries
  in 76 records of the installed `cinstream\*.mul`, all valid UTF-8); the box keeps them as they are (strcpy).
- **Record ring:** the call 0x4574ec goes to TruMenu's `SrReader`, which copies the **whole record** (not the pointer -
  0x9ccfa0 is reused for the next frame) with the kind byte, the profile word and the game language into its ring of the
  last 2 records, then calls the reader. The call 0x453a17 (reader -> box) goes to `SrAddLine`, which notes each line
  the box takes (not in game state 6 / 10, where 0x583db0 drops it), then calls 0x583db0. Both are rel32 call patches,
  set once on the first game frame after 13 byte checks (`kSrChecks`) - after the 0.22.13 checks, which also read
  0x4574ec. A patch site that is not the game's (another plugin) is left alone: `patch refused` in the log and in
  `sub.lang` (no argument), and `sub.lang <n>` works as in 0.22.13. Because of that order the `0.22 cine.pause: ...
  checks` log line now comes at the first game frame, not at the first `cine.pause`.
- **Rewrite on `sub.lang <n>`** (after the option setter and the settings save, game thread): each non-empty box line
  (+0 upper, +0x100 newest) is looked up among the stored lines (newest first; the box moves the newest line up at the
  next line, 0x583d80, and when the clock runs out); the record's lines for the new language are built exactly as the
  reader does, and the line is written into the box (<= 0x100 bytes incl. NUL). If the two box lines followed each
  other, the upper one becomes the line before the new newest one. The clock +0x208 and the floats +0x200 / +0x204 are
  not touched - in a held cutscene the new line stands at once and the clock stays held. A line that did not come from
  a stored record (Bink movie 0x4a09c8 / 0x4a0a02, the 0xfff-text line 0x4574d7, an older record) stays and is logged
  (`did not come from a stored subtitle record ... left unchanged`); a record without the new language leaves the line
  before it as the newest (as the game would). Log per record: ids, kind, word, lines then / now and `TruMenu's parse
  agrees` (the reader's own lines against TruMenu's copy of the parse; `DIFFERS` = report it).
- `sub.lang` (no argument) adds `instant switch on (n records read, n lines, n rewrite(s))`; the reply of
  `sub.lang <n>` says `shown lines: 2 rewritten, 0 left ...`.
- Checks: `tools/trumenu_ini_check.py` check_02214, `tools/trumenu_quick_check.py` model `sublang` (13 cases: the
  DLC 2 record of `pdlc2_030_pod.mul`, back to English, French UTF-8, clock expired, Bink line, -1 / kind, 2 lines -> 1,
  no German entry, speaker strip, 255 bytes, id -1).

### TO TEST 0.22.14

| # | Step | Expected |
|---|---|---|
| 1 | game start (first game frame, front end) | log `0.22.14: sub.lang instant switch (subtitle records) ok (13 checks)` and `0.22.14 sub.lang: subtitle record ring on (checks ok): S1 ..., S2 ... -> TruMenu` |
| 2 | `sub.lang` (no argument) after a cutscene line | `... instant switch on (n records read, n lines, 0 rewrite(s))` |
| 3 | DLC 2 ceremony room `pdlc2_030_pod` (English subtitles), hold the cutscene with a line on screen (LB + View), `sub.lang 0` first if needed | the line stays English |
| 4 | held: `sub.lang 2` | **the shown line switches to German at once** (both lines if two are shown); reply `shown lines: 1 rewritten` (or 2); log `sub.lang: box +0x100 (record #n line 1/1) '...' -> '...'`, `TruMenu's parse agrees`; badge still `Untertitel stehen` |
| 5 | held: `sub.lang 0` | **back to English at once** |
| 6 | held: `sub.lang 2`, then step with RB + View until the next line | the next line in German; the clock still held after the step |
| 7 | release (LB + View) | the cutscene runs on, the lines in German and in sync |
| 8 | `sub.lang 0` during a running (not held) cutscene | the shown line switches at once, the next lines English |
| 9 | Bink movie with subtitles, `sub.lang 2` during it | its line stays (log `did not come from a stored subtitle record`), next movie German |
| 10 | `sub.lang -1` (game language) in a held cutscene | the line in the game's language (German game -> German) |
| 11 | regression: the 0.22.13 rows 1, 5, 8 | unchanged |

## 0.22.13 - pad combos on release, subtitles held, sub.lang kept, ring bits, goo drip columns (2026-11-10)

Built into `work\asi\menu0236`, not installed. Byte checks: `work\asi\menu0236\precheck_02213.txt` (21 checks, 0
mismatches against the installed `tru.exe`). Background (workspace): `docs\Befund-PC-Test-0911-Abend.md` rows 6, 7, 7b,
9 and "TruMenu 0.22.12", `docs\Befund-Goo-Tropfen-1011.md` section 3, `docs\Befund-Anvisier-Kreis-0911.md` section 6.

- **Cutscene pad combos (row 6: LB + View pressed before RB fired "weiter" on the way to the photo).** A combo whose
  buttons are part of another combo - by default LB + View (weiter) and RB + View (1 Bild), both inside LB + RB + View
  (Foto) - now fires on **release** (when one of its buttons is let go) and only if no other combo button was added
  while it was held. A combo that is part of no other (the photo) fires as soon as exactly its buttons are held. One
  action per press; then every combo waits until no combo button was held for 120 ms (as 0.22.9). A press that had
  another combo button in it and does nothing writes `cine pad: combo 0x.... let go after 0x.... was held - no action`.
  Keyboard keys (`[Cine] PauseKey` ...) unchanged. Model: `tools/trumenu_quick_check.py` `cinepad` (11 cases).
- **The pause holds the subtitle lines too (row 7b).** Static (2026-11-10): a cutscene's subtitle text comes with its
  stream frames - the cinematic handler update 0x457100 (skipped by the 0.22 gate) hands it to the reader 0x4538d0,
  which adds each line with 0x583db0(text, 90) to the subtitle box 0xccdec0 (two 0x100-byte lines, line clock +0x208).
  The only thing that counts the clock down is the subtitle **draw** 0x583e20 (from the game display 0x5da17d):
  `+0x208 -= [0xe7f188]` (the scaled frame time) unless the game state byte 0xe7f143 is 6 / 10 (the game's pause); at
  <= 0 the newest line moves up, the lower one is cleared and the clock restarts at 90 (3 s) - that is why the lines
  scrolled away while picture and sound stood. While a cutscene is held, the disp32 of that `fsub` (0x583f24) points to
  TruMenu's own float: 0.0 while held, the game's frame time while stepping (`cine.step`) or while nothing is held; it
  goes in and out with the stream walk calls. 6 byte checks (`kCnSubChecks`); a mismatch keeps only this part off
  (`0.22.13 subtitle clock: 6 checks ...` in the first `cine.pause` log line). The badge says `, Untertitel stehen`; the
  "holds cutscene stream" line shows the clock and both lines.
- **`sub.lang` survives a restart.** The game writes its settings only in **0x478010**, whose only caller is the
  shutdown path 0x5df930 (0x5df935) - a game ended by `game.quit` (TerminateProcess) or a crash never saves, so the
  option was back at -1. `sub.lang <n>` now calls 0x478010 right after the option setter (game thread, `__try`, 3 byte
  checks `kSbSaveChecks`, `[0xad75e4]` must be set): it writes the settings as they are now - graphics copy, options,
  volumes, `SubtitleLanguage` - to `HKCU\...\Tomb Raider: Underworld`, exactly what the game writes at a clean exit. Log:
  `sub.lang: settings save 0x478010 done (#1) - registry mirror [0x8900e8] now 2`. No INI value needed.
- **Enemy panel:** `Kampf-Spur: an (203 Zeilen)` / `Fight trace: on (203 lines)` (was `Kampf-Spur: Zeilen 203`), and a
  new line `Ring: Bits 9:0 10:1 11:0 21:0 | HUD12 1 | Stil 2 | Fk40 0x0040 (6:1 9:0)`.
- **`ring.bits` (info, bar page Tests "Ziel-Ring: Bits (live)")** - the combat reticle request (K-5, ENGINE.md "Combat
  reticle"): CM = `[[0xfadb58]+0x504]`, `+0x1fc` bits 9 / 10 (helper 0x6f1ed0) / 11 (lock-on, 0x71e73f) / 21, HUD group
  bit 12 of 0xfae924 (0x77d9d0), style byte 0xfae8ac (0x77a680), position 0xfae8a4 / a8, reticle `[CM+0]` word +0x40
  (bits 6 / 9, 0x71e992 / 0x7037dc). Read only, never switches anything. 7 byte checks `kRgChecks`; bit 21's own
  readers 0x71e979 / 0x715026 are only checked offline - TruShadowPower patches 0x71e979.
- **`fight.trace` new columns (at the end; the TruXenia order and every older column unchanged):** `pc_ring_bits`
  (`9:0 10:1 11:0 21:0 (0x<word>)`), `pc_hud_g12`, `pc_ret_style`, `pc_ret40`; goo drips `pc_drip_q10706`,
  `pc_drip_q10707` (uber node of each source + time in it, `Spawn_easy@0.35`, `->Done` while a transition runs),
  `pc_drip_n` (copies of object 929 / 942), the nearest copy (x / y distance to Lara): `pc_drip_near_x/_y/_z`,
  `pc_drip_near_dxy`, `pc_drip_near_dz` (copy - Lara), `pc_drip_near_iflags` (inst+0x14), `pc_drip_near_node`; and
  `pc_lara_dmg` (Lara's LP drop in this 100 ms sample, `-2000.0 dead` when the LP is gone). The drip columns are filled
  only when a source (intro 10706 / 10707 of object 926) is loaded and Lara is within 2500 units (x / y) of their mid
  point; there a line is written every sample. A line is also written when the ring bits change or Lara loses LP. A
  header line is written at every `fight.trace 1` (the column count grew; `tools/fight_trace_compare.py` takes repeated
  headers). **No hook on 0x637590:** TruShadowCombat hooks it (`[Damage] Log`: target, type, sub, amount as `damage
  types` lines); TruMenu logs once whether the entry is the game's or a foreign jump and uses the LP drop.

### TO TEST 0.22.13

| # | Step | Expected |
|---|---|---|
| 1 | first `cine.status` / `cine.pause` | log `... 0.22.13 subtitle clock: 6 checks ok` |
| 2 | end cutscene with subtitles, LB + View, release | pause on when released (not on pressing); log `cine key (pad (released))` |
| 3 | held: LB + View, then add RB | photo only; the pause stays on (no "weiter"); log `cine key (pad)` with the shot |
| 4 | held: RB + View, release | one frame on |
| 5 | held for 10 s with a subtitle line on screen | the line stays (badge `, Untertitel stehen`); log line "holds cutscene stream ... subtitle clock ... held" |
| 6 | `cine.step 30` while held | the subtitle moves on with the frames |
| 7 | release (LB + View) | the line runs on from where it stood, next lines in sync with the speech |
| 8 | `sub.lang 2` | log `sub.lang: settings save 0x478010 done (#1) - registry mirror [0x8900e8] now 2` |
| 9 | quit the game (also with `game.quit`), start again, `sub.lang` | `subtitles now 2 (Deutsch) ... registry mirror 2` |
| 10 | `enemy.panel 1`, `fight.trace 1` | panel: `Kampf-Spur: an (n Zeilen)` and a `Ring:` line |
| 11 | bar Tests "Ziel-Ring: Bits (live)" while Lara aims at a thrall (LT), then with the power (RB) | bits / HUD12 / style change; note which ones (K-5: target + bit 9/10/21 -> HUD12 1) |
| 12 | DLC 2 end level, goo drip corridor with `fight.trace 1` (with / without power, die once) | TruFight.log: lines every 100 ms there, `pc_drip_*` filled, `pc_lara_dmg` at the death; log `0.22.13: damage function 0x637590 ...` once |

## 0.22.12 - fight trace follows Lara, quick bar shows trace states (2026-11-09)

Built into `work\asi\menu0235`, not installed. No new hooks (no byte checks needed).

- **`fight.trace`:** a Lara-only line (enemy columns `-`, the same column layout as 0.22.11, TruXenia compatible) is
  also written when Lara's chart record of machine 2 (`lara_rec1`) or her machine-1 state ids (`pc_lara_states`)
  change. Before only machine 1's record (`lara_rec0`), the camera, the power mode and enemy changes started a line, so
  phases where only Lara changed (aiming next to an idle tutorial thrall) were missing or only caught by chance (PC log
  2026-11-09 20:18-20:19: `lara_rec1` 48 / 40 only on lines written for other reasons). Still at most one line per
  100 ms sample; an enemy line in the same sample carries Lara's columns anyway.
- **Quick bar:** the bool rows Kampf-Spur (`fight.trace`) and Kombo-Spur (`combo.trace`) always showed "aus": their
  value text starts with the id (`fight.trace 1; 12 line(s) -> ...`) and the on / off reader looked only at the first
  character. It now skips a leading `<id> ` - the same reader serves the ring and the menu's bar pages. The switch
  itself worked (log `fight.trace 1`). `enemy.panel`, `light.stable`, `light.stablecut`, `light.cutlabels` already
  showed their state (value text starts with 0 / 1).
- **Quick bar:** an action row of an item with a short value shows the value before "rechts" - Untertitel-Sprache
  (`sub.lang`) shows the subtitle language now, e.g. `Deutsch (2) - rechts`.

## 0.22.11 - Xbox comparison, PC side: fight trace and enemy panel (2026-11-09)

Built into `work\asi\menu0234`, not installed. Byte checks: `work\asi\menu0234\precheck_0231.txt` (13 checks, 0
mismatches against the installed `tru.exe`). Goal: the PC logs the same values as TruXenia (`tools/truxenia.py`
`watch`) does on the Xbox in Xenia, so both runs of the same test card (`docs\Testkarte-Kampf-0911.md` in the
workspace) can be put side by side. Read-only: no game value is written; every pointer is checked before it is read.

- **`fight.trace 1|0`** (default 0, bar page Tests "Kampf-Spur (TruFight.log)"): tab-separated lines into
  **`TruFight.log`** next to TruMenu.log (opened shared, readable while the game writes; header line when the file is
  empty, at most 200000 lines per session). Sampled every 100 ms on the game thread; a line is written when an enemy's
  LP, state (layer 0 / 1), requested state or target changes, and a Lara line (`inst` = `-`) when Lara's chart record,
  the camera mode / position, power active, a time scale or a time-scale request changes. Columns - the TruXenia ones
  first, in its order and format: `host_time inst obj_id obj_name lp stamina state0 state1 req target dist lara_rec0
  lara_rec1 meter active time_scale`, then the PC-only ones: `pc_intro pc_ko pc_attack pc_hit pc_lara_lp pc_lara_states
  pc_lara_x pc_lara_y pc_lara_z pc_x pc_y pc_z pc_power_mode pc_player_time_scale pc_doppelganger pc_cam_obj
  pc_cam_mode pc_cam_req pc_cam_dx pc_cam_dy pc_cam_dz pc_cam_dist pc_cam_fov_deg pc_ts_requests pc_ts_selected
  pc_ramp_last`.
  - `time_scale` = world time scale `[0xe7f1a0]` (TU gameTracker+0x118, the TruXenia column), `pc_player_time_scale`
    = `[0xe7f1d4]`; `meter` / `active` from `TruShadowPowerMeterApi` (value, flags bit 0); `pc_power_mode` `slow`
    (world < 0.99) / `fast` (active at 1.0 - the Xbox goo-drip run, X23) / `-`.
  - `pc_ts_requests` = the meter's 7 time-scale request slots (TU meter +0x40, `{player, world}`, empty = -1) as
    `slot:player/world` for each occupied slot; `pc_ts_selected` = what the selector takes (highest occupied slot,
    `P1.20(s0) W0.30(s0)`). TruShadowPower 0.20 fills slots 0 / 4 / 5 only - the column shows it, nothing is changed.
  - `pc_ramp_last` = the last call of the retail time-ramp natives SetWorldTimeScale 0x776030 / SetPlayerTimeScale
    0x776090 (`gamebase` natives 23 / 24, the ones the TU routes to slot 6). While fight.trace or enemy.panel is on, a
    pass-through counter sits on both (6-byte jump after a byte check of the prologue, trampoline back; arguments and
    result unchanged) and writes one TruMenu.log line per call: `time ramp: world <- 0.300 over 0.250 s (gamebase native
    23; caller 0x... in <module>)` (24 for player; at most 2000 lines); `pc_ramp_last` = `hh:mm:ss.mmm W0.300@0.250s
    <module>`. It stays in place until the game ends.
  - `pc_attack` while an enemy is in MeleeAttack: the attack record (state data+0x50) and its anim refs +0x78 / +0x7c /
    +0x80 (`0x... a<type>/<anim> ...`) - which melee attack runs (the spit attack, X22).
  - `pc_hit` = the last hit of this enemy: amount, the state at the hit, the reaction (the first other layer-0 state
    within 1.5 s). Damage type and knockback come from TruShadowCombat's own lines (`damage types`, `0.6.7 hit`,
    `0.6.7 knockback`) in TruMenu.log, joined by time - TruShadowCombat does not export them.
  - Camera: position = vtable +0x34 of the current camera (base 0x5e1c60 `lea eax,[ecx+0xa0]`, snapshot 0xe8eeb0 while
    byte `[0xe8eec8]`), FOV = vtable +0x40 (base 0x5e1c90 `fld [ecx+0xb0]`, radians, logged in degrees), read only when
    the camera's vtable slot holds that base function; `pc_cam_d*` / `pc_cam_dist` = camera minus Lara. The look-at
    point is **not** logged (no proven field yet).
- **`enemy.panel 1|0`** (default 0, bar page Tests "Gegneranzeige"): a fixed panel at the right edge for the nearest
  enemy within 3000 units (the trace takes 6000; DE / EN with the language switch):
  ```
  Gegner viking_thrall (11270) - 312
  [#########.....] 420 / 500
  St 0.0 | Zustand Hit / - | Soll -
  Ziel Lara | Ko ja 1/2
  Treffer -60 Hit | -40 Hit | -20 Hit
  Lara 1000 | Kraft 967 Zeitlupe | Zeit Welt / Lara 0.30 / 1.20
  Zeit-Anforderungen 0:1.20/0.30 -> P1.20(s0) W0.30(s0)
  ```
  `St` stamina, `Zustand` layer 0 / 1, `Soll` requested state, `Ziel` target (Lara / ? / -), `Ko` attack coordinator
  (holds a slot ja / nein, grants / calls; `Ko 0` = no record, `Ko ?` = not read), `Angriff` line during MeleeAttack,
  `Treffer` the last 3 hits (amount and reaction), then Lara's LP, the power and both time scales, the request slots.
- Compare: new read-only `tools/fight_trace_compare.py --pc TruFight.log --xbox <truxenia watch .tsv>` (time
  filters per side, `--enemy`, `--show COL`): the n-th hit of each side in one table (time, enemy, LP, damage, state at
  the hit -> reaction, the same rule on both sides), the state sequence per enemy, reaction counts and the power phases.
  `tools/combat_log_compare.py` (combo lines) is unchanged.
- Open: the look-at point; whether the PC also routes script ramps into a request slot (the column shows it live);
  `stamina` on the PC is the brain field the 0.22.9 label shows (meaning against the Xbox column still to compare).

## 0.22.10 - light cut diagnosis and a stable light choice per object (2026-11-09)

Built into `work\asi\menu0233`, not installed. Byte checks: `work\asi\menu0233\precheck_0230.txt` (9 checks, 0
mismatches against the installed `tru.exe`). Background: workspace `docs\Befund-Licht-Kuerzung-0911.md`, ENGINE.md 16
"Light set builder". The PC cuts every object's lights in the set builder **0x504cc0**: it walks the object's light
list in order and keeps the first lights that fit - at most 7, sun 1, shadow slots 3 (of them at most 2 with a shadow
map), plain 3 (overflow into free shadow slots); a light that fits nowhere is dropped (0x504e56), lights after the 7th
are not looked at. When the order of the list changes from frame to frame (the throne end cutscene), an object with more
fitting lights than slots gets another choice every frame - the flicker. The Xbox shaders take 7 lights of any kind
(Xenia 2026-11-09: no flicker, Natla lit warm and cool at once).

- **`light.cutlabels 1|0`** (bar page Tests next to "Licht-Reihenfolge fest", no argument = report): a line top left
  `Licht-Kürzung Bild <n>: <sets> Sätze, <cut> gekürzt; stärkste: Li 9 -> 7 (S1 M2 C1 P3) drop 2` and a label at every
  light that was dropped in the last frame (`Licht #<index from light.list> (<kind>)` / `verworfen <n>x, behalten <n>x`).
  `Li a -> b` = lights offered to the set -> kept; `S` sun, `M` with a shadow map, `C` shadow slots without a map
  (shadow casters and plain lights that overflowed there), `P` plain slots; `drop` = taken out again because no slot
  was free. Kinds: Sonne / Schattenkarte / Schattenwerfer / einfach - the builder's own tests (res+0x42c == 2,
  res+0x418 && res+0x42c, CastsShadow 0x50a080, rest). The label position is the light's transform row L+0x50 (as
  light.list - to be confirmed live).
- **`light.cut [frames] [all]`** (bar: "Licht-Kürzung ins Log (3 Bilder)"): frames (default 3, at most 30) into
  TruMenu.log - per frame a summary line, then per set `caller`, offered -> kept, category byte, drop, "not looked at",
  and the offered list in order: `+` kept, `-` dropped, `.` not looked at, each `#index 0xlight kind (position)`.
  Default only the sets that dropped a light; `all` = every set (several hundred lines per frame). Info only. A set
  cannot be named by the game object it belongs to (the builder only gets the light list); the list and the caller
  address tell them apart.
- **`light.stablecut 1|0`** and **`[Light] StableCut`** (default 0, live from the bar): before the cut, the object's list
  is ordered by kind (sun, shadow map, shadow caster, plain), then by the light's address - stable from frame to frame,
  only for the per-object choice; the collected scene list and with it the shadow atlas order stay the game's.
  **How it relates to `light.stable` (`[Light] Stable=1`, default since 0.22.5):** light.stable sorts the whole
  collected list +0x250 at 0x56d69a (also the shadow atlas order) and keeps the choice that the address order gives
  (warm at the throne, the cool front light on Natla missing); light.stablecut only fixes the per-object choice and puts
  the shadow-mapped and shadow-casting lights first. Both on is allowed (StableCut decides the per-object order then).
  **A / B at the throne:** (1) Stable=1, StableCut=0 (as now) and (2) Stable=0, StableCut=1 - each with
  `light.cutlabels 1` and a `light.cut 3` while Natla is on screen; compare the flicker and which light is dropped.
- Hooks: `jmp` at 0x504e56 (5 bytes `80 44 24 1a ff`, back 0x504e5b) and at 0x504eb9 (8 bytes `8b 4e 0c 51 8d 54 24 18`,
  back 0x504ec1) only while the labels are on or a capture runs; `jmp` at 0x504cd9 (6 bytes `8b 86 34 12 00 00`, back
  0x504cdf) only while StableCut is on. All written on the game thread and put back when off; refused (one log line)
  when the bytes are not the game's.

### TO TEST 0.22.10

| # | Step | Expected |
|---|---|---|
| 1 | log | `0.22.10 light cut: 9 checks ok` (first use) |
| 2 | throne cutscene, "Licht-Kürzung anzeigen" on, `cine.pause` | summary line top left; labels at dropped lights; `light cut diagnosis on` in the log |
| 3 | `light.cut 3` while Natla is on screen | 3 frames of `light.cut f<n>` lines: which light is `-` (dropped) and whether it changes per frame |
| 4 | light.stable off, "Licht-Auswahl je Objekt fest" on | no flicker; compare Natla's light with the Xenia picture (warm + cool) |
| 5 | both off | the flicker is back (proves the order is the cause) |

## 0.22.9 - enemy diagnosis, combo trace, subtitle language live, combo fix (2026-11-09)

Built into `work\asi\menu0232`, not installed. Byte checks: `work\asi\menu0232\precheck_0229.txt` (9 checks, 0
mismatches against the installed `tru.exe`).

- **Third enemy label line** (dbg.enemies, every AI enemy, light blue): why an enemy attacks or not and how it took the
  last hit. Live symptom 2026-11-09: the hall02 tutorial thrall walks to Lara, follows her, stays in `CombatStepIdle`
  and never attacks. Example: `Ziel Lara 312 | Ko nein 0/14 2s | Soll - | L1 - | Sp - | St 40 | Tr 3 -20>HitReaction`.
  - `Ziel` - the enemy's current target (EnemyTargeting brain+0x4e10, slot +0x30: mode 0 sense / 1 instance / 2
    position): `Lara <distance>`, another instance, or `- (m<mode>)` = none.
  - `Ko` - attack slots: the coordinator 0x67d780 (asked before Attack / MeleeAttack, callers 0x63a731, 0x64fefb,
    0x65b9f9, 0x65bd26, 0x673981) counted per enemy: `ja` / `nein` = last answer, granted / calls, seconds since the last
    call; `Ko 0` = the enemy never asked. A pass-through detour on its 5-byte prologue (`83 ec 18 53 56` ->
    trampoline), placed on the game thread the first time a label or `ai.why` needs it; it never changes the answer.
  - `Soll` - the requested state (brain+0x18f8), `L1` - the layer 1 state (brain+0x1260); `-` = none, else the state name.
  - `Sp` - the game's gate bits brain+8: `A` = 0x20 Attack / ScriptAttack off, `M` = 0x100000 Melee off, `X` = 0x800 no
    damage; `-` = none set.
  - `St` - stamina (health component brain+0x2c60 +0xc, lowered by 0x620ea0).
  - `Tr n -x>State` - hits seen (LP drops), the last amount, and the first state the enemy entered within 1.5 s after it
    (= the hit reaction the game chose: e.g. HitReaction / Vaulted / Fall / RegenerateDeath).
- **`ai.why [intro id|0xINSTANCE]`** (bar page Tests, group "Gegner-Diagnose"): the nearest AI enemy (or the given one),
  one long line in TruMenu.log - L0 / L1 / requested states, brain+8 and +0xc, target slot and override slot (+0xf0) with
  "Lara", the 12 senses (how many hold Lara), attack-slot calls / grants / last answer, LP / damage taken / stamina, hits
  and the last reaction. Read-only, never toggles anything.
- **`combo.trace 1|0`** (off by default, live, no argument = report): per AI enemy hit within 3000 units one log line
  `combo: Lara records <path> -> <enemy> LP a -> b (-x), stamina s -> t, state at the hit ..., reaction ...`. Path =
  Lara's chart records of chart machine 1 (`[[0xfadb58]+0xf10]`, update 0x787e60 from 0x768c65), the last up to 6 record
  indices within 2 s - the combo steps; the damage type / sub / amount of the same hit is TruShadowCombat's
  `damage types` line with the same time stamp. Not traced: the input / link window of each chart transition (needs a
  hook on the transition 0x787890, which TruTrace already logs), no bar line yet.
- **`sub.lang -1|0..4|7|9..12`** (no argument = report): the subtitle language live, as `docs\Befund-Untertitel-Live-0911.md`
  (workspace) proposes - the game's option setter 0x5d5100(0xb, value, 1) on the game thread; its callback 0x5d4dc0
  writes both profile words `[[0xc59264]+0x208]` / `[[0xc59268]+0x208]`, which every subtitle line reads (0x453990);
  movies take it at their next start; the next settings save keeps it in the registry. Checks 0x5d5100, 0x5d4dc0,
  0x453990; at run time `[0x8ab594] == 0x5d4dc0` and both profiles set.
- **Cutscene pad combos fixed** (live 2026-11-09 15:13: the photo combo View + LB + RB also fired View + LB = pause off
  and View + RB = step): only the buttons of the three combos count, a combo fires when exactly its buttons are held and
  that set stood still for 120 ms (pressing View, LB, RB one after the other gives the photo, not the pause on the way),
  once per press - then all combos wait until no combo button was held for 120 ms. Keyboard keys unchanged (edges).

### TO TEST 0.22.9

| # | Step | Expected |
|---|---|---|
| 1 | log | `0.22.9: ai.why / enemy diagnosis line ok (5 checks)`; after the first labels `coordinator 0x67d780 counted` |
| 2 | hall02 tutorial thrall, dbg.enemies on | third line; while it idles: `Ko 0` (never asks) or `Ko nein n/m` (asks, refused) - decides the next step |
| 3 | bar Tests: "Warum greift er nicht an?" | one `ai.why:` line in TruMenu.log |
| 4 | "Kombo-Spur" on, hit a thrall with X X X | `combo:` lines, path grows per step; reaction state per hit |
| 5 | cutscene, View + LB + RB | photo only - no pause toggle, no step |
| 6 | cutscene with subtitles, `sub.lang 0` then `sub.lang 2` | next line in English, then German |

### TO TEST 0.22.1

| # | Step | Expected |
|---|---|---|
| 1 | log | `0.22 cine.pause: 7 checks ok; 0.22.1 sound pause: 4 checks ok` |
| 2 | end cutscene, Szene anhalten | badge top centre, sound silent (no loop); log "master channel group ... paused" |
| 3 | wait 10 s, release | speech goes on where it stopped, lips and sound in sync |
| 4 | held: Ein Bild weiter a few times, `cine.step 60` | the scene moves on a little, no sound, still in sync after release |
| 5 | at the throne: Stelle merken; reload the checkpoint; Bei Marke anhalten | the cutscene stops at the same spot by itself |
| 6 | held, open the game's pause screen, close it | sound stays held (TruMenu did not pause it twice); release gives it back |

## TO TEST (0.4)

A checklist the main session (Claude over TruLink) fills while the player plays; the player marks the rows with the controller.

```text
menu test.add level.reload Reload the current unit - Lara at the same spot?   new row (or new hint: state open again)
menu test.add level.load:dlc_level2_start Load DLC 2                          "Run" runs level.load dlc_level2_start
menu test.add look-shadow Shadows at the start look right?                    free key (no item: no Run button)
menu test.mark look-shadow fail dark band at the left wall                    ok | fail | skip | open, optional note
menu test.list                                                                 read the states back
menu test.del <id>      menu test.clear      menu test.clear done                (done = only the marked rows)
```

- **`test.list`** answers one line: `<n> rows (<o> open, <k> ok, <f> fail, <s> skip): <id> [<state>] <hint> {<note>} |
  <id> [<state>] <hint> | ...` (`{note}` only when there is one). Tabs / line breaks in hints and notes become
  spaces, `|` becomes `/`, `{` `}` become `(` `)`, so the answer stays parseable; spaces in an id become `_`.
- **TruLink limits** (TruLink's tokenizer, not TruMenu): a line has at most 24 words, so a hint gets at most 21 words
  (`test.mark` notes 20) - more are cut without a message; runs of spaces become one; a last word `force` is taken
  as TruLink's force flag and dropped; the argument is cut at 511 characters.
- **File** `TruMenu.tests.txt` next to `tru.exe`, rewritten on every change, read at start (survives a restart):
  a `#` comment line, then one line per row `id<TAB>state<TAB>hint<TAB>note<TAB>time` (time = `HH:MM:SS` of the last
  mark). At most 64 rows (0.10.1: 128 - the radial profiles send 77 / 98 rows; also the regression lists); `test.add`
  on a full list answers `err list full`.
- **In the menu** the page "TO TEST" is the first page (open) and is not drawn while the list is empty. A marks the
  selected row OK (also a mouse click), X FAIL, Y SKIP; while a row has the nav focus TruMenu keeps X and Y away from
  ImGui (else X would jump to the title bar layer and Y would activate the row = OK). A mark from the menu keeps the
  note; `TruMenu.log` gets a line `tests: test.mark <id> <state>` for every change (also visible on the Log page).

## TO TEST 0.5: steps, checks, switches

Goal: go through a test **in order** in the game without the chat, and switch features on / off yourself to find the
step or feature that crashes (bisecting) instead of one run per step. Three row kinds:

| Kind | Command | Row id | States | In the menu |
|---|---|---|---|---|
| `check` | `test.add <id> <hint>` (as 0.4) | `<id>` | open / ok / fail / skip | A = OK, X = FAIL, Y = SKIP, buttons, "Run" for `id` / `id:arg` |
| `step` | `test.step <n> <id\|id:arg\|-> <text>` (n = 1..999) | `step<n>` | open / done (not checkable) | "NEXT->" on the first open step; A = run the item (if any) + done; "Run <id arg>" only runs, "Done" / "Open again" only marks |
| `toggle` | `test.toggle <id> <target> <text>` | `<id>` | on / off | a checkbox in "Switches" at the top of the page |

```text
menu test.step 1 - Wait in the main menu                                       step without an item
menu test.step 4 level.load:dlc_level2_start Load the DLC 2 start              "Run level.load dlc_level2_start"
menu test.add d3d-box No D3D error box after the load?                         a check as in 0.4
menu test.toggle sp-states ini:TruShadowPower:States:Enabled States 243/245    INI switch (next start)
menu test.toggle flight cheat.flight Flight cheat on                           item switch: runs cheat.flight 1 / 0
menu test.mark sp-states off      menu test.mark step4 done                    switch / step from TruLink
menu test.export                                                               the whole list as a block
```

- **Order:** a new step goes in front of the first step with a higher number, so steps stay in number order; checks
  and toggles are appended. Sending the rows in the wanted order (step 1, step 2, check, step 3, ...) gives exactly
  that order; `test.step` with an existing number replaces that step (text / item, open again).
- **Toggle targets:** a TruMenu item id (bool items: on = `<id> 1`, off = `<id> 0`, run like a menu click; the state
  shown is the item's value when the row is added: `1` / `on` / `true` = on) or `ini:<Plugin>:<Section>:<Key>` -
  `<Plugin>.ini` next to the `.asi` files, written **at once** with `1` / `0` (`WritePrivateProfileString`). Our
  plugins read their `.ini` only at start, so the row carries the note "INI: takes effect at the next start". The
  plugin name must start with `Tru` (letters / digits), section and key letters / digits / `_`; a missing `.ini` is
  not created (`err ... not found`). INI toggles show the INI value again when the list is loaded at start.
- **`test.mark`** takes the state that fits the kind: checks `ok|fail|skip|open`, steps `done|open`, toggles `on|off`
  (switches the target); a wrong one answers `err <id> is a <kind> row: ...`.
- **`test.export`** answers a TruLink block: `ok+ test.export <n> rows; checks <o> open <k> ok <f> fail <s> skip;
  steps <d>/<t> done; toggles <on>/<t> on (...)`, then one line per row `kind<TAB>id<TAB>state<TAB>number<TAB>target
  <TAB>hint<TAB>note<TAB>time`, then `.`. In `menu list` its value is only the counts line.
- **`test.list`** stays one line; steps / toggles carry their kind: `step4 (step 4 -> level.load:dlc_level2_start)
  [open] ...`, `sp-states (toggle ini:TruShadowPower:States:Enabled) [on] ...`. The header counts (`TO TEST (n
  open, ...)`, `test.list`) count checks only; `test.clear done` removes only marked checks (steps and toggles stay).
- **TruLink limits** as above: `test.step` / `test.toggle` texts get at most 20 words.
- **File:** 0.5 writes three more columns, `id<TAB>state<TAB>hint<TAB>note<TAB>time<TAB>kind<TAB>target<TAB>number`;
  a 0.4 file (5 columns) loads as checks. (0.4 reading a 0.5 file sees steps / toggles as checks with odd states.)
- **Regression runs:** `scripts\windows\Invoke-TruTestRun.ps1 -RunProfile <name>` preloads the rows of
  `tests\profiles\<name>.json` (`test.clear`, then the rows in profile order) and collects `TruMenu.tests.txt`
  after the run ([scripts/windows/README.md](../../../scripts/windows/README.md)).

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

## 0.4 items: facts

Sources: catalog `docs/Menue-Funktionen-Katalog.md` section 17 and our disassembly with `tools/pe_dis.py` on
2026-10-31 (Steam `tru.exe`); every address checked at load (Status page line "0.4: ...", `TruMenu.log` "0.4
checks"). Not yet run in the game.

| Item(s) | Fact | Check at load |
|---|---|---|
| `weapon.slots`, `weapon.has` | weapon manager `WM = [[0xfadb58]+0x500]`; 15 slots, right hand handle `{instance, id}` at `WM+4+0x10*slot`, left hand at `WM+0xc+0x10*slot` (reader 0x6e7b90: `cmp esi, 0xe`, `[esi+edi+4/8]`, `[esi+edi+0xc/0x10]`); a handle is valid when `[instance+0x44] == id` (the game's check 0x5b39d0 - TruMenu repeats it with its own reads instead of calling it); object name `[[instance+0x10]+0x60]` (as the gear callback reads it at 0x715ea2); selected slot `WM+0x138` | 0x5b39d0 bytes, 0x6e7b98 / 0x6e7bb9 / 0x6e7bde |
| `ammo.fill` | for type 0..5: `reserve[type]` (u16 `playerstate+0x51c+2*type`) = *MaxAmmo* 0x6eeae0 cdecl `(s8 type) -> u16` (6-entry jump table, `0xffff` for other types; reads the player's object data `[[0xe7f094]+0x50]`, so a level is needed); the clips are **not** refilled (0x6e7ae0 not used) | 0x6eeae0 prologue + jump, 0x6eec67 `or ax, 0xffff; ret` |
| `gear.give` | *GiveObject* 0x555f60 cdecl `(owner = player instance, objectId, callback 0x715e90, flag 1)`: an existing instance of the object (0x5b3950) goes to the callback at once, else 0x5550a0 loads / births it first; the callback with flag 1 calls *WM::AddGear* (catalog 17.1 step 5). Main state 1 only | 0x555f60 and 0x715e90 bytes, 0x715eb2 `mov eax, [0xfadb58]; mov ecx, [eax+0x500]` |
| Log collapse / filters | in `PushLine`: a leading `HH:MM:SS[.mmm] ` is the time stamp; the newest line of the same source with the same text is counted and moved to the head; TruLink lines `> read* / scan* / watch* / ping` and `[>] menu <id>` with an info item (or `status.*`, `list`) are dropped when `HideLinkReads=1`; severity by words (errors: fail, error, exception, ` NO `, `err `, crash; warnings: warn, not match, mismatch, busy, refused, unreadable, timeout, missing, skipped, not verified); rate limit counted per source and second, the dropped count is written as one line when the second is over | - |
| `camera.free` | **still todo**: the free camera needs the offsets of the camera's `transform` / `invTransform` and the per-frame rebuild (catalog section 9). Found on 2026-10-31 only a lead: 0x5edb50 writes a matrix at 0xe8ee30 (via 0x431e10) and its inverse at 0xe8ee70 (`0x49be10(0xe8ee70, src)`), i.e. inverse = transform + 0x40 for that camera object; which camera / base it is and whether mode 11 keeps the game from overwriting it is **not verified** | - |

## Hooks

Every address below is checked against the expected bytes at load (`Start()`); on a mismatch that part stays off,
the reason goes to `TruMenu.log` and the Status page shows `NO`. Nothing is patched in the game code itself - with one
opt-in exception since 0.3: `log.script` writes a 5-byte `jmp` over the start of the 8 script print / log natives
(restored when it is turned off; see "0.3 items: facts"). Import slots: `GetProcAddress` (pad, since 0.1) and, 0.7,
only while the menu is open, `SetCursorPos` / `ClipCursor` (see "Controller and mouse (0.7)").

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

Observed since 2026-11-06 (TruMenu.log, `Befund-TruShadowPower-017-0611.md`, `Befund-Padkette-StartView-0711.md`): the
import filter never handed out PadHook - the slot is rewritten to KERNEL32's GetProcAddress after the filter - so
PadHook is always placed late and the order of the three hooks depends on load timing. TruLink's same-thread re-entry
breaker also fires when an item run inside PadHook polls the pad while TruLink sits outside PadHook; since 0.21.2 such
items run in the Present hook (section "TruMenu 0.21.2").

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
| `[Menu] FreeMouse` | 1 | 0.7: while the menu is open the mouse belongs to the menu (cursor drawn, no mouse messages to the game, its `SetCursorPos` / `ClipCursor` held until close); 0 = as 0.6 |
| `[Menu] BlockGameInput` | 1 | 0.7.1: while the menu is open the game gets no keyboard (its DirectInput keyboard reads no key events, a key it saw going down is released once, a key held at the close stays away until released; key messages to the menu only); 0 = as 0.7 |
| `[Menu] PauseGame` | 0 | 0.7.1: 1 = also set the `time.pause` bit while the menu is open; on close only what TruMenu set is cleared |
| `[Pad] BlockInput` | 1 | 0 = the game sees the pad while the menu is open |
| `[Cheat] Experimental` | 1 | 0 = no game-changing actions (pages read-only) |
| `[Cheat] FlightSpeed` | 20 | units per 30 fps frame at full trigger |
| `[Cheat] FlightHint` | 1 | 0.21.6: 1 = while flight is on and the menu is closed one line bottom right names the keys (RT up, LT down, stick moves, the speed); 0 = no line |
| `[Cheats] Enabled` | 1 | 0.8: 1 = the Cheats page can switch (also needs `[Cheat] Experimental=1`); 0 = list only |
| `[Cheats] Persist` | 0 | 0.8: 0 = every cheat off at each game start; 1 = the ids that are on are kept in `State` and switched on again in the first level of the next start |
| `[Cheats] State` | (empty) | 0.8: written by TruMenu when `Persist=1` (comma list of cheat ids) |
| `[Levels] List` | `dlc_level1_start,dlc_level2_start` | units offered as buttons on the Level select page |
| `[Levels] OutfitRule` | 1 | 0.7.2: `level.start` as the title update's mission menu - `dlc_level2_start` (and `dlc_level4..6_start`) without the outfit / weapon selection, other units with it; 0 = PC script 104 (always with the selection) |
| `[Favorites] Ids` | (empty = default list) | favourite item ids, comma list; rewritten by TruMenu when you pin / unpin (`WritePrivateProfileString` on this file) |
| `[Cmd] Enabled` | 1 | 0.6: 1 = command bar under the menu window (0 = no bar; `cmd.run` still works, `cmd.focus` answers `err`) |
| `[Cmd] HistorySize` | 32 | 0.6: lines kept in `TruMenu.history.txt` next to `tru.exe`, 1 .. 64 |
| `[Cmd] FocusButton` | 64 (0x0040 L3) | 0.7: XInput button (pressed and released alone, menu open) = focus into the bar + on-screen keyboard; 0 = off |
| `[Cmd] Keyboard` | 1 | 0.7: on-screen keyboard when the bar gets the focus by controller; 0 = L3 / A only focus the text field |
| `[Cmd] UpOpensHistory` | 1 | 0.7: 1 = Up in the empty bar = history; 0 = Up into the menu like Down (Ctrl + Up = history) |
| `[Cmd] FirstPadPressOnlyFocuses` | 1 | 0.7: 1 = the first D-pad / stick press in the bar only focuses the menu; 0 = it also moves there |
| `[Log] Overlay` | 0 | 1 = log lines in the bottom-left corner from the start |
| `[Log] Lines` | 12 | lines on the Debug / Log page and in the overlay (1 .. 64) |
| `[Log] Script` | 0 | 1 = redirect the 8 script print / log natives from the start (patched at load, before any script runs; needs `Experimental=1`) |
| `[Log] Collapse` | 1 | 0.4: repeated lines (same source, same text after the time stamp) become one line `text x42 (first-last)` (`log.collapse`) |
| `[Log] HideLinkReads` | 1 | 0.4: drop TruLink's echo of `read*` / `scan*` / `watch*` / `ping` and its `menu` lines for info items (`status.*`, `test.list`, ...) (`log.hidereads`) |
| `[Log] MinLevel` | 0 | 0.4: 0 all lines, 1 warnings + errors, 2 errors only (`log.level`) |
| `[Log] MaxLinesPerSecond` | 40 | 0.4: new lines per source and second, more are dropped and counted; 0 = no limit (`log.rate`) |
| `[Log] UnitChanges` | 1 | 0.7.1: a line `unit: <name> (was <name>; stream unit id N)` in `TruMenu.log` (log page / overlay) when Lara moves into another stream unit |
| `[Log] OverlaySources` | `TruMenu,TruGuard` | 0.7.2: sources the corner overlay shows (log names without `.log`, plus `script`); `*` or empty = all; overlay only (`log.overlaysources`) |
| `[Log] OverlayExclude` | (empty) | 0.7.2: overlay only - lines holding one of these texts (comma list) are not shown (`log.overlayexclude`; `none` = off) |
| `[Log] CameraChanges` | 1 | 0.8: `camera: mode A -> B` / `camera: object ...` lines when the camera manager's mode (manager+0x58) or current camera changes (read-only poll, 200 ms; `camera.log`) |
| `[Log] InputTrace` | 1 | 0.8.1: with `[Menu] LogLevel=2` one `input: ...` line per pad button edge / mouse click / key while the menu is open, with the source and what the menu did (focus, activated or why not); 0 = only the summary line at each close (`log.inputtrace`) |
| `[Test] AutoStart` | (empty = off) | 0.7.1, test only: `dlc2` / `dlc1` / a unit name - once per game start, when the main menu is up, `level.start` (mission menu path, intro plays); without the verified path `level.load` + log line "intro skipped" |
| `[Test] AutoStartDelay` | 3 | 0.7.1: seconds the main menu must be up before AutoStart starts, 1 .. 60 |
| `[Regress] List` | `all` | 0.8: list the Regression page shows at start: `dlc1`, `dlc2` or `all` |
| `[Media] MusicInLevels` | 0 | 0.9: 1 = `media.music.play` / `stop` also in a level; 0 = main menu only (until a live test proves it safe) |
| `[Media] MusicFade` | 60 | 0.9: fade in / out frames (30 per second) of `media.music.play` / `stop`, 0 .. 300 (the game's unit start uses 60) |
| `[Saves] Folder` | (empty) | 0.9: save folder of the Saves page; empty = the game's own (Documents\Eidos\Tomb Raider - Underworld) |
| `[Radial] Enabled` | 1 | 0.10: radial menu on; 0 = TruMenu exactly as 0.9 (L3 + R3 toggles at the press, F9 reaches the game) |
| `[Radial] HoldButtons` | `0x00C0` | 0.10: pad buttons held for the ring (hex or decimal; L3 + R3); 0 = no pad hold. Same mask as `[Menu] ToggleButtons` = short press menu (at the release), held = ring; another mask = watched on its own |
| `[Radial] HoldMs` | 500 | 0.10: hold time in ms, 100 .. 3000 |
| `[Radial] Key` | `0x78` | 0.10: virtual key held for the ring (F9; Steam Controller back button -> F9 in Steam Input); kept from the game (DirectInput event + key messages); 0 = off |
| `[Radial] MouseButton` | 0 | 0.10: 3 = middle, 4 / 5 = side buttons held = ring (mouse direction picks); 0 = off |
| `[Radial] RememberPosition` | 1 | 0.10: the ring opens at the level / page / pick of its last close; 0 = always at the top |
| `[Radial] PassLeftStick` | 1 | 0.10: the left stick reaches the game while the ring is open (Lara walks); 0 = neutral pad |
| `[Radial] SlowMotion` | 0 | 0.10: `time.scale` while the ring is open (e.g. 0.25), the old value comes back at the close (unless an entry changed it); 0 = off |
| `[Radial] Deadzone` | 0.5 | 0.10: stick deflection that picks a sector, 0.2 .. 0.95 (mouse: 30 px x Scale at 0.5) |
| `[Radial] Scale` | 1.0 | 0.10: ring size relative to the back-buffer height, 0.5 .. 2 |
| `[Radial] Spawn` | 0 | 0.10 stage R2: 1 = `instance.spawn <object>` works (ring level Objekte - `Spieler/Objekte` since 0.10.5, command bar, TruLink); 0 = refused. Read again from the ini at most once a second, so a TO TEST switch `ini:TruMenu:Radial:Spawn` works in the running game |
| `[Shot] Enabled` | 1 | 0.10.5: screenshots on request (`shot.save`, ring, `claude.mark`, Hotkey, exports `TruMenuShot` / `TruMenuMark`); nothing automatic; 0 = every shot refused (mark lines still written, `shot=-`) |
| `[Shot] Folder` | (empty) | 0.10.5: PNG folder; empty = `TruShots` next to tru.exe, relative = below the game folder |
| `[Shot] Clean` | 1 | 0.10.5: 1 = copied before TruMenu draws; 0 = after (as on screen); `shot.save ui` / `clean` per shot; `claude.mark` always clean |
| `[Shot] Hotkey` | 0 | 0.10.5: virtual key (e.g. `0x7A` = F11) = `claude.mark now`; the game still gets it; 0 = off |
| `[Shot] MaxPerMinute` | 30 | 0.10.5: shots (and, separately, marks) per minute, 1 .. 120; 0 = no limit |

## Build, install, test (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Name TruMenu -Verbose   # also compiles src\asi\third_party\imgui -> work\asi\TruMenu.asi
.\scripts\windows\Set-TruMenu.ps1 -Install                  # copies .asi + .ini next to tru.exe (game closed)
.\scripts\windows\Set-TruMenu.ps1 -Remove                   # removes them again (only if they are a build of ours)
```

Static runtime (`/MT`), imports `KERNEL32.dll` and `USER32.dll` only (since 0.9 also `SHELL32.dll`:
`SHGetFolderPathW` for the save folder; 0.10 added `GetWindowThreadProcessId` / `MapVirtualKeyA` from USER32). Test plan
for the first run:

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

0.4 additions (built with `-OutDir work\asi\menu04`; install the `.asi` **and** the new `TruMenu.ini` - it has four
new `[Log]` keys, an old ini works too: missing keys take the defaults). Every step: note the result, send
`TruMenu.log`, `TruLink.log` and `TruMenu.tests.txt`.

22. Status page: the line `0.4: weapon slots ok, ammo.fill ok, gear.give ok; TO TEST file <tru.exe folder>\TruMenu.tests.txt`;
    `TruMenu.log` holds "0.4 checks". With no `TruMenu.tests.txt` there is **no** TO TEST page; Quick access is first.
23. TO TEST over TruLink: `menu test.add level.reload Reload - Lara at the same spot?`, `menu test.add
    ui.hide:1 HUD gone?`, `menu test.add look-shadow Shadows at the start look right?` - open the menu: "TO TEST (3
    open, ...)" is the first page, rows with "Run level.reload" / "Run ui.hide 1" and none for `look-shadow`.
24. Marking with the pad: D-pad to a row, A -> `[OK]` green, X -> `[FAIL]` red (the focus stays on the row, no jump to
    the title bar), Y -> `[SKIP]` grey (the row is **not** marked OK first); the buttons OK / FAIL / SKIP do the same;
    "Run ui.hide 1" hides the HUD. `menu test.list` shows the states; `menu test.mark look-shadow fail dark band left`
    -> the row shows the note.
25. Restart the game: the rows and states are back (`TruMenu.log` "tests: 3 rows from ..."); "Remove the marked rows"
    removes the marked ones; "Remove all rows" needs A twice; the page disappears; `menu test.clear` answers `0 left`.
26. Log page: let TruLink poll (e.g. `watch add` + repeated `read32 player`): no `> read32` lines; a line that repeats
    shows as `... x<n> (<first>-<last>)`; "warnings + errors" / "errors" hide the info lines; set `menu log.rate 2`,
    produce many lines - one yellow line "(n lines dropped ...)"; `menu log.page` shows the same; `menu log.collapse 0`
    / `log.hidereads 0` bring the raw lines back (only new ones). The counter line under the list counts all three.
27. Weapons in a level: `menu weapon.slots` (slot numbers + names, the selected slot), `menu weapon.has wp_handgun`
    (yes, slot n), `menu weapon.has wp_uzi` before / after `weapon.give wp_uzi`; `menu ammo.fill` -> `menu ammo.show`
    gives the MaxAmmo values (HUD reserve full?); `menu gear.give g_binoculars` (note whether the item appears /
    whether anything breaks - static facts only).

0.5 additions (built with `-OutDir work\asi\menu05`; `TruMenu.ini` unchanged from 0.4;
`Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu05` replaces 0.1.3 - 0.4 builds as ours):

28. `menu test.clear`, `menu test.step 2 - Second`, `menu test.step 1 - First`, `menu test.add c1 Check one`,
    `menu test.step 3 ui.hide:1 Hide the HUD` - the page shows "NEXT->  1. First", "2. Second", the check, "3. Hide
    the HUD" with "Run ui.hide 1"; A on step 1 -> `[DONE]`, NEXT moves to step 2; A on step 3 hides the HUD and marks it
    done; "Open again" opens it again. `menu test.mark step2 ok` -> `err step2 is a step row: open|done`.
29. `menu test.toggle sp-states ini:TruShadowPower:States:Enabled States` (TruShadowPower installed): a checkbox under
    "Switches", state = the INI value, note "INI: takes effect at the next start"; untick it -> `TruShadowPower.ini`
    holds `Enabled=0` in `[States]` at once (the plugin still runs as before); restart: the row shows off and the
    plugin log says states 0. `menu test.toggle x ini:Foo:A:B x` -> `err bad ini target`.
30. `menu test.toggle fly cheat.flight Flight` - tick: flight on (as `menu cheat.flight 1`), untick: off.
31. `menu test.export` -> `ok+ test.export ...`, one tab-separated line per row, `.`; `Invoke-TruLink.ps1 -Command
    'menu test.export'` prints the block. Restart: steps / toggles / checks and their states are back; a 0.4
    `TruMenu.tests.txt` loads as checks.

0.6 additions (built with `-OutDir work\asi\menu06`; install the `.asi` **and** the new `TruMenu.ini` - it has the
`[Cmd]` section, an old ini works too: `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu06`). Every step: note the
result, send `TruMenu.log`, `TruLink.log` and `TruMenu.history.txt`.

32. Main menu, open the menu (L3 + R3): the bar sits directly under the menu window, the text cursor blinks in it;
    TO TEST / Quick access are still the first pages. Type `time.scale` - the list above the bar shows `time.scale = 1.000`
    first; Enter -> green `ok time.scale = 1.000`. Type `ui.hide` + Enter -> its value, the HUD does **not** change.
33. Keys do not leak: type `wasd` and Esc in the bar while in a level - Lara does not move, no pause menu; Esc puts the
    focus into the menu; F2 brings it back.
34. Autocomplete: `cost` -> `costume.*` ids first (prefix), Down / Down / Tab takes the third one; `costume.set ` (with
    space, in a level) lists the outfit cycle names, `doppel` filters them; Enter runs `costume.set doppelganger_casual`
    -> `ok queued costume.set ...`, then (next game frame) the real answer replaces it. `level.load ` lists the units.
35. `time.scale 0.5` (world slower), `time.scale 1`; `get level.load`; `list fog`; `help`; `nonsense` -> red
    `err unknown item 'nonsense'`; `costume.sett` -> `... did you mean costume.set?`.
36. History: run three lines, empty bar, Up / Up / Down - the lines come back in order; restart the game - Up still
    shows them (`TruMenu.history.txt` next to `tru.exe`); `menu cmd.history` over TruLink lists them newest first.
37. Pad with the bar focused (menu just opened): D-pad down -> the focus is in the menu (TO TEST / Quick access header),
    D-pad again navigates as in 0.5; A / B / X / Y on the pages work as before (TO TEST: A = OK, X = FAIL, Y = SKIP).
38. Pad picker: in the menu press View - the list shows all ids with values; D-pad to `ui.hide`, A -> the HUD toggles
    (result line `ok ...`); to `time.scale`, A -> value picker, RB x5 -> 1.5, A -> world faster, B, B -> back in the
    menu; to `level.load`, A -> unit list, A on `dlc_level1_start` loads it; Y on an id pins it (Quick access).
39. TruLink: `menu cmd.run time.scale 0.5` -> answer as `menu time.scale 0.5`, the bar shows `TruLink: time.scale 0.5`;
    `menu cmd.focus` opens the menu with the focus in the bar; with `[Cmd] Enabled=0` there is no bar and
    `menu cmd.focus` answers `err command bar off`.

0.7 additions (built with `-OutDir work\asi\menu07`; install the `.asi` **and** the new `TruMenu.ini` - five new keys,
an old ini works too: `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu07`; the 0.6 builds `work\asi\menu06` /
`work\asi` and the 0.6 ini are recognised as ours). Every step: note the result, send `TruMenu.log`, `TruLink.log` and
`TruMenu.history.txt`.

40. Status page: line `mouse (0.7): ready (...)`; `TruMenu.log` holds "0.7 cmd: focus button 0x0040, ..." and "0.7
    mouse: SetCursorPos slot 0x0083e308, ClipCursor slot 0x0083e2e0 ... game code 1 -> ready". (`slots NOT matched`:
    send the log - only the mouse messages are held then.)
41. Controller only, in a level: open the menu (L3 + R3) - **no** keyboard appears and closing with L3 + R3 opens none
    either. Open, D-pad into the menu, press **L3** alone: the bar gets the focus, the keyboard appears under it with the
    cursor on `q`; row 0 shows the history (or "(no history yet ...)").
42. Keyboard: RB -> tokens row, A on `time.` -> the line is `time.`, row 0 lists `time.scale`, `time.pause`; LB -> row 0,
    A (or Y from any row) takes `time.scale ` (with space); type `0`, `.`, `5` with the D-pad / A; Start -> green
    `ok ...`, the world runs at half speed; `time.scale 1` back. X deletes (hold = repeat). B closes the keyboard, D-pad
    then goes into the menu as in 0.6. View with the keyboard open -> pad picker; View there -> keyboard again.
43. Look: rounded keys, highlighted key with a yellow frame, pressed key lights up; Run key green; nothing cut off at the
    right edge (also at `[Menu] Scale` 1.0 / 2.0 - note how it looks on the TV).
44. Keyboard + real keyboard: with the on-screen keyboard open, type `ui` on the real keyboard -> it closes, the field
    holds the line + `ui` with the cursor at the end (nothing selected), Lara does not move. Esc with the on-screen
    keyboard open only closes it.
45. Mouse in a level (camera follows the mouse when the menu is closed): open the menu - an ImGui cursor appears, moving
    the mouse does **not** turn the camera and the cursor is not pulled back to the centre; click into the bar, type,
    click a menu button, click a key of the on-screen keyboard (L3 first). Alt + Tab away and back, click into the bar
    - it takes the focus (0.6 failed here). Close the menu: the camera does not jump, mouse look works as before, the
    cursor is hidden / clipped again. Windowed (TRAWindowed): the cursor tip matches the clicked widget.
46. `[Menu] FreeMouse=0` (restart): behaviour as 0.6 (camera turns while the menu is open). Back to 1.
47. Options: `[Cmd] UpOpensHistory=0` -> Up in the empty bar goes into the menu, Ctrl + Up opens the history;
    `[Cmd] FirstPadPressOnlyFocuses=0` -> the first D-pad press in the bar moves the focus into the menu **and** one
    entry further (hold = repeats); `[Cmd] Keyboard=0` -> L3 only focuses the text field; `[Cmd] FocusButton=0` -> L3
    does nothing.
48. TruLink: `menu cmd.keyboard` (menu closed) -> menu opens with the bar focused and the keyboard shown;
    `menu status.hooks` ends with `mouse=...`.

0.7.1 additions (built with `-OutDir work\asi\menu071`; install the `.asi` **and** the new `TruMenu.ini` - five new
keys, an old ini works too: `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu071`; the 0.7 build `work\asi\menu07`
and its ini are recognised as ours). Every step: note the result, send `TruMenu.log`, `TruLink.log` and
`TruMenu.history.txt`.

49. `TruMenu.log` after the start: "0.7.1 keyboard: wrapper vtable slot 0x00844f64 0x00486100 -> KbdReadHook -> ready
    ..." and "0.7.1: block game input 1 (keyboard hooked), pause game 0 (...), mission start path 1, stream unit name 1
    ...". Status page: line `keyboard (0.7.1): ready ...`.
50. In a level, Lara standing: open the menu, type `wasd` and Enter into the command bar (also hold `w` for a second)
    - **Lara must not move**; close the menu - she stays standing (also when `w` is still held while closing: she only
    walks after `w` is released and pressed again). Status line counters: events held > 0.
51. Hold `w` (Lara runs), open the menu with L3 + R3 while still holding it - Lara **stops** (neutral state, "releases
    sent" > 0); release `w`, close the menu - she stays standing.
52. Esc in the menu (bar focused, on-screen keyboard open, and in the menu window): **no pause menu** of the game; with
    the on-screen keyboard open Esc only closes it. After closing the TruMenu, Esc opens the game's pause menu as usual.
53. B twice: L3 (keyboard open), **B** -> only the keyboard closes (menu stays, bar focused); **B** again -> the menu
    closes (`TruMenu.log`: "menu closed (B twice: keyboard, then menu)"). Variant: L3, B, D-pad down -> focus in the
    menu (no close). If a single B still closes the menu: send the log line "menu closed (...)".
54. Real keyboard switch with the mouse elsewhere: L3 (keyboard open, cursor on `q`), move the mouse cursor away (over
    the menu window or outside the game), do **not** touch the pad, type `ui` on the real keyboard -> the keyboard closes,
    the field holds `ui` with the cursor at the end, typing goes on (`.hide`), Enter runs it. Repeat with the
    cursor over the bar and after selecting a key with the D-pad.
55. Keyboard reopen: L3 (keyboard open), close the menu with L3 + R3, open again -> the keyboard is back; B (closes it),
    L3 + R3, L3 + R3 -> menu without keyboard.
56. `[Menu] PauseGame=1` (restart): in a level with enemies / moving water, open the menu - the world stands still,
    close - it moves on. `time.pause 1` before opening -> still paused after closing; `time.pause` used inside the menu
    -> its state is kept after closing. Back to 0.
57. `[Menu] BlockGameInput=0` (restart): as 0.7 (typing in the bar can move Lara again) - only to confirm the switch.
58. Lara's stream unit: `log.overlay 1`, walk through DLC 2 from the start room into the next rooms - the overlay shows
    lines `unit: <name> (was <name>; stream unit id N)` at each room change; `menu status.unit` shows "Lara's unit".
    Note the names (catalog of the internal room names).
59. `level.start dlc2` from the main menu (command bar or Level select button "Start DLC 2 as the mission menu
    (intro)"): the DLC 2 **intro plays**, then the level (compare `level.load dlc_level2_start`: no intro). Outfit /
    weapon choice as with the mission menu? Sound on?
60. `[Test] AutoStart=dlc2` (restart, game data **without** test patch 41e): after the main menu has been up for 3 s the
    DLC 2 intro starts by itself, once per game start (quit to the main menu: it stays). `TruMenu.log`: "AutoStart:
    main menu up ..." and "AutoStart: level.start dlc_level2_start queued ...". Back to empty.

0.7.2 additions (built with `-OutDir work\asi\menu072`; install the `.asi` **and** the new `TruMenu.ini` - three new
keys, an old ini works too: `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu072`; the 0.7.1 build
`work\asi\menu071` and its ini are recognised as ours). Every step: note the result, send `TruMenu.log`.

61. `TruMenu.log` after the start: "0.7.2: pending check 1 (main state 2 / 9 + GameTracker+0xb9), outfit rule 1 (ini 1;
    ...), game.quit ready (exit code 0x544d, ...)". `menu level.start` (value) shows "outfit rule title update ...;
    pending check main state 2 / 9 + GameTracker+0xb9".
62. Level select page: the two mission-menu buttons in the order **DLC 1, DLC 2**.
63. `level.start dlc2` from the main menu: the DLC 2 intro plays and **no outfit / weapon selection** comes; Lara is the
    doppelganger (TruDlc2Player log: costume "lara_doppelganger" -> doppelganger_casual). `TruMenu.log`: "mission start
    'dlc_level2_start': ... f27('dlc_level2_start', 0, 0, 1) ... no outfit / weapon selection". Compare with the Xbox
    (Xenia checklist 12c).
64. `level.start dlc1` from the main menu: the outfit / weapon selection **does** come (`f27(..., 1, 0, 1)`). While it is
    open: open the menu, `level.load dlc_level2_start` and `level.start dlc2` -> both answer `refused: level change
    pending (main state 9: the outfit / weapon selection of a level start is open)`; the Level page shows the grey
    reason line; `status.state` says "outfit / weapon selection ...". Close the menu, choose an outfit - DLC 1 loads
    normally (no hang).
65. `[Levels] OutfitRule=0` (restart): `level.start dlc2` shows the outfit selection again (as 0.7.1). Back to 1.
66. `game.quit`: Status page (expand "Status"), last button "Quit game (press twice)" - press once: it turns red
    "CONFIRM: quit the game now (5 s)"; wait > 5 s: back to normal, nothing happens. Press twice: the game ends at once.
    `TruMenu.log` ends with "game.quit armed by the owner ..." and "game.quit by the owner (TruMenu) - logs flushed
    next, then TerminateProcess(...)". Also from the command bar: `game.quit`, Enter, `game.quit`, Enter.
67. TruLink: `menu game.quit` -> `err game.quit only from the menu, the command bar or a favourite (owner) - never over
    TruLink`; the game keeps running.
68. Harness: a run of `Invoke-TruTestRun.ps1` ended with `game.quit` -> `summary.md` status "... - ended via TruMenu
    game.quit (exit code 0x544D, not a crash)", exit code row `21581 (0x544D: ended via TruMenu game.quit)`, first
    crash marker `-`, the verdict notes name it and the owner checks still count. Only the exit code is mapped: under
    `-Debugger` the code is the one cmd / cdb hand back, and a session that echoes `TERMINATEPROCESS` still counts that
    marker as a crash (not changed in 0.7.2).
69. Log overlay filter: `log.overlay 1` in DLC 2 with TruShadowPower: the overlay shows only TruMenu / TruGuard lines
    (unit changes readable, no "activity 1009" lines); the Debug / Log page still shows TruShadowPower.
    `log.overlaysources *` -> all again; `log.overlayexclude activity 1009` -> those lines gone from the overlay only;
    `log.overlayexclude none` -> back.

0.8 additions (built with `-OutDir work\asi\menu080`; install with `Set-TruMenu.ps1 -Install -SourceDir
.\work\asi\menu080` - it copies the `.asi`, the new `TruMenu.ini` (five new keys; an old ini works too) and the two
regression lists; the 0.7.2 build `work\asi\menu072` and its ini are recognised as ours). Every step: note the result,
send `TruMenu.log` and `TruMenu.regress_results.txt`.

70. `TruMenu.log` after the start: "0.8 cheats (enabled 1, persist 0): god 1, god full 1, one-hit kill 1, enemy health
    1, infinite ammo 1, fill 'er up 1, cheat code 1" (no "disabled" line) and "0.8: camera log 1 (...), regression lists
    ... (dlc1 18 rows, dlc2 30 rows, page shows all)". Status page: line "0.8: cheats god ok ...".
71. Regression page (main menu is enough): header "Regression DLC 1 + DLC 2 (35 open, ...)"; DLC 1 / DLC 2 / all switch
    the rows. On a check: A -> green [OK], X -> red [FAIL], Y -> grey [SKIP] (X / Y must not act on anything else).
    `TruMenu.regress_results.txt` next to the `.asi`: one `#session` line (plugin versions incl. `TruMenu=TruMenu
    0.8.0`, sha256 of every loaded `Tru*.asi` - compare TruMenu's with this build), then one line per mark.
72. Note: "Note" on a row -> the command bar shows `regress.note dlc2:<id> ` with the on-screen keyboard; type a word,
    Run / Enter -> the row shows "- <word>", a result line with the note. Restart the game: every row open again, the
    results file keeps the old lines, a new `#session` line comes before the next mark.
73. TruLink: `menu regress.load dlc2` -> page shows DLC 2, all rows open; `menu regress.mark dlc2:waterfall ok bright`;
    `menu regress.mark no-crash ok` with "all" selected -> `err 'no-crash' is in both lists - write dlc1:no-crash or
    dlc2:no-crash`; `menu regress.export` -> block with 48 rows, ends with `.`.
74. Cheats page in the main menu: every switch greyed out, "needs a level". In a level: `cheat.god` on (log "cheat: god
    mode ON") - an enemy hit / small fall does not lower health; a deep fall still kills (instant death passes, as in
    the prototype). Off again.
75. `cheat.godfull` on: no damage at all (also types 8 / 5)? Watch for side effects of cheatMode bit 0 (no-clip /
    flight behaviour, camera, controls); then off - `cheat.flight` must still work as before.
76. `cheat.onehitkill` on: one shot kills an enemy (log "toggle 0x0060f670 called"); off: normal damage.
77. `cheat.enemyhealth` on: is a hit-point number drawn at enemies? (may draw nothing in retail - mark what you see).
78. `cheat.ammo` on with pistols + another weapon: shoot past one clip - the reserve (`ammo.show`) does not drop; pick up
    / give another weapon (`weapon.give wp_shotgun`), wait 1 s - it reloads without reserve as well; off: reserve drops
    again (the pistols keep their own behaviour).
79. `cheat.fillup` after taking damage: health back to max (HUD health silhouette flashes), reserves at max
    (`ammo.show`); log "cheat: fill 'er up - health a -> b".
80. Cheat codes in a level: `cheat.code 2` -> Lara shows the hit-reaction effect, `cheat.god` reads 1; again -> 0;
    `cheat.code 1` / `11` toggle `cheat.onehitkill` / `cheat.enemyhealth`; `cheat.code 9` / `10`: nothing visible
    expected (no readers); `cheat.code 4` -> usage error. No crash.
81. `[Cheats] Persist=1` (restart): switch `cheat.god` on, quit, start again, load a level -> log "cheats: [Cheats]
    Persist=1 - cheat.god on again"; `[Cheats] State=cheat.god` in the ini. Back to 0 (and clear State).
82. Camera log (DLC 2, `log.overlay 1`): walk - "camera: mode ... at the start of the log"; hold RB / aim -> mode lines;
    the second DLC 2 hint (rock channel) that swings the camera to the wall: which "camera: mode" / "camera: object"
    lines come (copy them into the report). `camera.log 0` -> no more lines.

0.8.1 additions (built with `-OutDir work\asi\menu081`; install with `Set-TruMenu.ps1 -Install -SourceDir
.\work\asi\menu081` - `.asi`, the new `TruMenu.ini` (one new key `[Log] InputTrace`) and the two regression lists; the
0.8.0 build and its ini are recognised as ours). Run with `[Menu] LogLevel=2` (the harness profiles do) and send
`TruMenu.log` + `TruMenu.regress_results.txt`.

83. Start: `TruMenu.log` holds "0.8.1: input trace 1 (... now 2), game.quit window 10 s + hold 1 s, request slot claimed
    once, regression shortcuts 7, player.unstuck ring 16 spots".
84. **game.quit with the pad**: Status page, D-pad to "Quit game (press twice, or hold 1 s)", A once -> a red
    "Quit now" button appears beside it with "armed - 10 s left" (the label does not change), the focus jumps to
    "Quit now" after you let go of A; A again within 10 s -> the game ends (exit code 0x544D). Log: two
    `input: pad0 A down (XInput hook) -> activated '...'` lines, "game.quit armed", "game.quit by the owner".
85. game.quit, hold: A on "Quit game ..." and keep it held -> a progress bar "hold 1 s to quit" fills, after 1 s the game
    ends (log "game.quit: button held 1 s by the owner"). Same with the PC keyboard (arrow keys + Enter) and with the
    mouse (click "Quit game", then click "Quit now"; or hold the mouse 1 s). Let it run out once: after 10 s the red
    button disappears and nothing happens.
86. Input trace: open the menu, press A on a few buttons, D-pad around, a key, a mouse click; close. `TruMenu.log`: one
    `input:` line per press / release with "activated" / "focus 'a' -> 'b'" / a "not activated: <reason>" that makes
    sense, and at the close "input while the menu was open: n pad presses (A n: n activated, n not), ...". Try the
    bar: D-pad down from the bar -> "command bar owns the pad: focus from the bar into the menu - swallowed by
    FirstPadPressOnlyFocuses". `log.inputtrace 0` -> only the summary lines.
87. Stuck Enter: in the bar type `level.load dlc_level2_start`, Enter (menu closes, level loads); open the menu again
    -> the bar must NOT run empty lines (no "cmd (bar):  -> err empty line" lines in the log); hold Enter in the bar
    with a typed line -> it runs once.
88. cheat.flight: Cheat / flight page, "Cheat / flight ON" -> one `item cheat.flight: cheat.flight 1` line only (no
    "0" right after), Lara flies with RT / LT (menu closed); "OFF" -> one `cheat.flight 0` line. Several times.
89. cheat.ammo in hall02 with only the pistols: answer lists every slot weapon, e.g. "slot 0 ...: type -1 ... ammo type
    0xff = unlimited already" (copy the line). Then `weapon.give wp_shotgun` (or any ammo weapon), wait 1 s, `cheat.ammo
    0` + `cheat.ammo 1` -> that weapon shows "bit set"; shoot past one clip: the reserve (`ammo.show`) does not drop.
90. player.unstuck: in hall02 walk around on firm ground for ~10 s, then jump / slide into the eitr (god mode on);
    `player.unstuck` (button on Time / player / HUD or command bar) -> Lara stands on ground she walked on before; again
    within 20 s -> one spot further back. `player.mark` somewhere, walk away, `player.unstuck` -> back at the mark
    (newer). Before walking anywhere: "no target: ..." (no crash).
91. Regression shortcuts: Regression page -> "Quick prepare" list with "Thrall fight: hall02 + god mode (dlc2:step7)",
    "DLC 2 start unit ...", "Treasure room", ... A on "Thrall fight" -> the menu closes for the level load, hall02
    loads, about 2 s later god mode switches on (`TruMenu.log`: "shortcut 'Thrall fight: hall02 + god mode' 1/2:
    level.load ... 2/2: cheat.god 1 -> ok ..., done"); the page line "shortcut: ...: done". "Prepare" on the dlc2 step5
    row: god mode off + time.scale 0.5. `menu regress.prepare dlc2:step7` over TruLink works the same; `regress.prepare
    stop` while it waits stops it.

0.10 additions (radial menu; built with `-OutDir work\asi\menu010`, profile `regress_shadowlara_50l_radial`; install with
`Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu010` - also copies `TruMenu.radial.txt`; the new `TruMenu.ini` has the
`[Radial]` section, an edited ini is kept and takes the defaults). Section "Radial menu (0.10)".

92. Start: `TruMenu.log` holds "0.10 radial: enabled 1, hold buttons 0x00c0 500 ms (= the menu combo: short press = menu
    at the release), key 0x78 (DirectInput 0x43, kept from the game) ..." and "radial: 27 entries in 7 levels from
    ...TruMenu.radial.txt (0 dropped, 0 unknown, 0 lines skipped)"; Status page line `radial (0.10): ...`; Settings page
    lists the 11 `[Radial]` keys.
93. L3 + R3 **short** (main menu or level): TruMenu opens when you let go ("menu opened (pad, short press)"); L3 + R3 in
    the open menu closes it at once. Lara does not crouch / look while you press.
94. In a level, **hold** L3 + R3: after 0.5 s the ring with Cheats, Marken, Zeit, Waffen, Spieler, Objekte; the right
    stick lights one sector; release on **Zeit** -> the Zeit level opens and the ring stays open.
95. Latched ring in Zeit: stick to "Zeitlupe 0.5", **A** -> the world runs slower, the ring stays, `TruMenu.log`
    "radial: Zeit -> time.scale 0.5: ok time.scale 0.500 ..."; stick to "Normal 1.0", **R3** -> runs and closes.
96. Hold, leave the stick in the **centre**, release -> nothing runs ("radial: closed (released in the centre)" at
    LogLevel 2). Hold, release on Cheats, **B** -> top level, **B** -> closed.
97. Remember: close the ring in Cheats with a sector picked; hold again -> it opens in Cheats with that sector lit;
    release without moving the stick -> nothing runs. `[Radial] RememberPosition=0` (restart) -> always the top.
98. Cheats -> Gott-Modus shows **off**; A -> **on** (green), log "radial: Cheats -> cheat.god 1"; A again -> off
    ("cheat.god 0"). Same for Spieler -> Unverwundbar and Zeit -> Welt einfrieren.
99. Main menu (no level): hold -> Cheats / Spieler / Waffen entries grey with "needs a level" in the centre; A on one ->
    "not available - needs a level" under the ring. Objekte entries grey "[Radial] Spawn=0 (stage R2 off)".
100. Keyboard: **hold F9** -> the ring at once; move the mouse -> a white dot and the sector in that direction; release
    F9 -> runs. The game does not react to F9. Steam Controller: Steam Input, map a back button to F9 -> the same.
101. `[Radial] MouseButton=3` (restart): hold the middle mouse button -> ring, mouse picks, release runs; left click = A,
    right click = B.
102. While the ring is open: the camera does not turn (right stick, mouse), A / B / LB / RB do nothing in the game,
    Lara walks with the left stick; `[Radial] PassLeftStick=0` (restart) -> she stands. After closing with B / R3 the
    game does not see that button.
103. `[Radial] SlowMotion=0.25` (restart): the world slows while the ring is open and is back to normal after the close;
    with "Zeitlupe 0.5" run from the ring it stays at 0.5.
104. Waffen -> Schrotflinte (in hall02 or dlc_level2_start): `weapon.give wp_shotgun` queued, "last action" shows the
    answer; the shotgun is in the inventory. Munition voll -> `ammo.show` at max.
105. `[Radial] Enabled=0` (restart): L3 + R3 toggles at the press as in 0.9, holding does nothing else, F9 reaches the
    game; `radial.status` says "enabled 0".
106. TruLink: `menu radial.status`, `menu radial.list` (27 entries, the Objekte ones "= greyed: [Radial] Spawn=0"), `menu
    radial.open Zeit` (ring opens latched at Zeit, B B closes), `menu radial.reload`.

Stage R2 - **only with `[Radial] Spawn=1`, back up the saves first** (Saves page "Back up all saves now"; the key is
read again while the game runs - in the profile the TO TEST switch `radial-spawn` sets it, no restart):

107. `TruMenu.log` at the start: "0.10 radial: ... spawn (R2) code ok, [Radial] Spawn=0"; switch it on (TO TEST switch or
    ini) -> within a second the Objekte entries are no longer grey (in a level); `radial.status` "... (Spawn=1)".
108. hall02 (or dlc_level2_start): Objekte -> **Medipack** -> `TruMenu.log` "instance.spawn: g_healthpack (id 55) born
    at Lara ...: instance 0x...; tracker ... was in the table, 0 polls" - a health pack at Lara's feet; walk away, look,
    pick it up if possible. `instance.list healthpack` lists it.
109. Objekte -> **Kiste A**: a short stutter (load), "... requested now, n polls / m ms"; a crate at Lara (inside her -
    step out); push / shoot it, note physics. Kiste B / C the same. A second Kiste A: "was in the table", no stutter.
110. Objekte -> **Schrotflinte (Objekt)** last: note what appears (pickup or bare model), whether it can be taken, no
    crash. Then a save / load (checkpoint): are the spawned objects in the loaded game? Note it (open point of R2).
111. Command bar: `instance.spawn sh_ei_combat_crate_a` works the same; `instance.spawn nosuch` -> "not in the object
    list"; `[Radial] Spawn=0` again afterwards.

0.10.1 additions (radial menu as a menu, Freeze, quit sector, Tests level; built with `-OutDir work\asi\menu0101`,
profile `regress_shadowlara_50l_radial2`; install with `Set-TruMenu.ps1 -Install -SourceDir .\work\asi\menu0101` - also
copies `TruMenu.tour.txt`). Section "Radial menu (0.10.1)". Tests 93 - 104 above describe `[Radial] Mode=wheel` now.

112. Start: `TruMenu.log` "0.10.1 radial: mode menu (...), freeze world ..., quit sector 1 (built in), tests level 1
    (tour 38 stops / entries) ..." and "radial: tour 38 entries from ...TruMenu.tour.txt (0 dropped, 0 unknown, 0 lines
    skipped)" (34 with the tour file of the first 0.10.1 build); Settings page lists the 15 `[Radial]` keys.
113. In a level **hold** L3 + R3 0.5 s: the ring with Cheats, Marken, Zeit, Waffen, Spieler, Objekte, Tests, Spiel
    beenden (8 sectors); **let go** - it stays open, nothing runs.
114. **Left stick** to Zeit, let the stick go - Zeit stays picked; nothing runs. **A** -> the Zeit level. D-pad right /
    left steps through the entries. A on "Zeitlupe 0.5" -> runs (`radial: Zeit -> time.scale 0.5`), the ring stays.
115. **B** -> top level (Zeit picked), **B** -> closed. Hold L3 + R3 again -> it opens in the top level with Zeit lit;
    **L3 + R3** again -> closed. Lara never moved, the camera never turned, A / B never reached the game.
116. Freeze world (TO TEST switch `radial-freeze` on = `[Radial] Freeze=1`): open the ring next to a thrall / moving
    water -> everything stands still while it is open, runs on after the close (`radial: freeze world - time.pause bit
    set by the ring`, `... released`). Switch `radial-freeze` off, open again -> the world keeps running.
117. Freeze on: Zeit -> "Welt einfrieren" shows **on** -> A (off) -> the world runs in the open ring and stays running
    after the close (the user's choice). Freeze off: A on it (on) -> close -> the world stays frozen; open, A (off).
118. Spawn while frozen (only with `radial-spawn`, after "Back up all saves now"): Objekte -> Medipack -> TruMenu.log
    `instance.spawn: g_healthpack ... born at Lara` while the world stands; it moves / can be taken after the close.
119. **F9 tapped** -> ring; the mouse moves the pick; **Enter** / left click runs; Backspace = back; **F9** again closes.
    The game never saw F9 / Enter / Backspace.
120. Top level **Spiel beenden**: A -> red, "A nochmal = beenden (10 s)" counting down; wait 11 s -> disarmed (log
    `game.quit (radial sector): disarmed - 10 s passed`). A, then the stick to another sector -> disarmed ("the pick left
    the sector"). A, then B -> disarmed ("B") and closed. A, then L3 + R3 -> disarmed ("ring closed").
121. Tests -> `TO TEST n/m offen` -> a row -> Hint (text under the ring), Run (if offered), OK / Done -> back in the
    list, the row is gone, the TO TEST page shows it marked (`tests: test.mark ...`). Tests -> Schalter -> `radial-freeze`
    toggles on / off as the page's checkbox. Tests -> Regression -> DLC 2 -> a check -> OK (`regress: ...` line,
    `TruMenu.regress_results.txt`). Tests -> Prepare -> one shortcut runs (ring closes). Tests -> Rundgang -> Maschinenraum
    -> "Laden dlc2_machine_room" (ring closes); after the load reopen -> "10 Maschinensaeule" -> Lara at the column.
    Tests -> Rundgang -> **Versteckt** shows `Laden dlc_dungeon`, `26 Goldene Schrotflinte ...`, `27 container1: ...
    (Saves sichern!)`, `28 Erweitertes Ende (Saves sichern!)` - run 27 / 28 only after "Back up all saves now", in a
    run of its own (workspace `docs\Versteckte-Inhalte-Rundgang.md`).
122. **Last step - ends the game:** top level Spiel beenden, A (red), A again within 10 s (or hold A 1 s) -> the game
    ends; `TruMenu.log` `game.quit (radial sector): confirmed by the owner ...` then `game.quit by the owner (TruMenu)
    ...`; the run summary says "ended via TruMenu game.quit (exit code 0x544D, not a crash)".

## Ideas

- **`[Test] SkipHintBoxes`** (research only, nothing built): the DLC 2 hint boxes come from the ported generalbank script
  9 (`popUpTitleMessage`, TU script 10; `docs/Befund-Test33-Native.md`): it pauses the game until A (Xenia reference: DLC
  2 hints modal with pause, DLC 1 top right without). Known from that finding: script 9 inherits from script 93
  (`uiscreen`); its f7 lies near the "paused" string and calls the replaced `dlc2data` f1(0), f8 calls f1(1), f9 reads
  f0 and calls f1(0); its external calls include `inputaction` f0 and `uiscreen` f90 / f91 / f99. Not yet found: which
  native / engine flag the modal box uses to pause the game (candidates, unverified: a `uiscreen` modal flag, a
  `uigamedata` pause native, streamFlags) and which call closes it on A. Next step: disassemble script 9 f7 / f8 / f9
  (`tools/menu_dlc_probe.py`, `script_func_list.py`) and map their `op65` calls to exe natives as done for f22 / f27
  above; an auto-confirm could then run the close path's natives on the game thread while the box is up - only with
  byte checks and as a test option.
- The DirectInput mouse device (input manager +0x28, wrapper 0x485ae0) could be held the same way as the keyboard if a
  live test ever shows mouse clicks reaching the game while the menu is open.

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
