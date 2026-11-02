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
checked with `dumpbin` and offline byte checks only - not yet run in the game (section "Regression, Cheats, camera
log (0.8)"). `camera.free` is still a todo (see "0.4 items").**

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
| Regression | 0.8, under TO TEST, collapsed (header "Regression DLC 1 + DLC 2 (n open, n ok, n fail, n skip)"): selector **DLC 1 / DLC 2 / all**, the rows of `TruMenu.regress_dlc1.txt` / `_dlc2.txt` (next to the `.asi`, copied by `Set-TruMenu.ps1`); checks **A = OK, X = FAIL, Y = SKIP**, buttons OK / FAIL / SKIP / **Note** (puts `regress.note <list>:<id> ` into the command bar and opens the on-screen keyboard; Enter saves); steps: A = run its item + done; "Reload lists" (A twice). Every mark / note is appended to `TruMenu.regress_results.txt` (section "Regression, Cheats, camera log (0.8)") | `regress.list`, `regress.load dlc1\|dlc2\|all`, `regress.mark <dlc1:id\|dlc2:id\|id> ok\|fail\|skip\|open\|done [note]`, `regress.note <list:id> <text>`, `regress.export` |
| Cheats (2007 prototype evaluation) | 0.8: one row per cheat with its **category** (PC has it / re-attach / cheat-code path / rebuild from prototype); a failed byte pre-check greys the row and names the reason in red; in a level only; the "rebuild" rows are listed read-only as "not built yet" | `cheat.list`, `cheat.god [0/1]`, `cheat.godfull [0/1]`, `cheat.onehitkill [0/1]`, `cheat.enemyhealth [0/1]`, `cheat.ammo [0/1]`, `cheat.fillup`, `cheat.code <1\|2\|9\|10\|11>` |
| Status | TruMenu version, `tru.exe` PE time stamp / image size, all code checks, whether a level is loaded; current unit + stream unit id; game state; costume line (current costume, game-data base, `+0x1f4`, chosen `+0x20c` / `+0x20e` / `+0x210`, unit default); player line (instance, object id / name, type record, object-table entry); our plugins (`TruShadowPower`, `TruDoppelganger`, `TruDlc2Player`, `TruRockVein`, `TruLink`: loaded? `<Name>Version()` string), ModLoader.asi, the pad chain (what the game calls, what PadHook calls, with module names), the `d3d9.dll` in use (game folder = TRAWindowed proxy, else system), device / window; 0.7.2: button **"Quit game (press twice)"** at the end (section "Mission start, outfit rule, game.quit (0.7.2)") | `status.version`, `status.hooks`, `status.unit`, `status.state`, `status.costume`, `status.player`, `status.plugins`, 0.7.2 `game.quit` |
| Outfits (next level load) | the same costume facts, then one button per **player record of the game's type table** (index, name, object id; `[chosen]` / `[current]` marked), "Reset chosen costume", checkbox "reload the current unit after choosing" | `costume.records`, `costume.current`, `costume.choose <index\|name> [20c\|210]`, `costume.choosereload <index\|name>`, `costume.choosereset`; the 0.2 ids `costume.setreload` / `costume.reset` still work. **0.3 changed** `costume.list` (now the live cycle list; the 0.2 list = `costume.records`) and `costume.set` (now the live switch; the 0.2 meaning = `costume.choose`) |
| Overlay: Lara's position | checkbox for a small top-left overlay with Lara's position and heading; position / rotation in the page | `overlay.position`, `player.position` |
| Free camera | known facts; experimental `CAMERA_SetMode(mode)` with a mode slider (TRLAU enters its free camera with mode 11; TruLink notes that retail switches only for 6, 11, 12) and "Restore game camera". **TODO** own free camera (moving the camera transform with the sticks) | `camera.current`, `camera.mode <n>`, `camera.restore`, `camera.free` (todo) |
| Cheat / flight | `GameTracker.cheatMode` + player message 12 (TRLAU "skew" cheat); while on and the menu is closed **RT lifts, LT lowers** Lara (`[Cheat] FlightSpeed` per 30 fps frame) | `cheat.flight [0/1]`, `cheat.speed <v>` |
| Markup / collision draw | 0.3: experimental markup drawing (boxes / poly lines of the MarkupManager projected with the game's view matrix into ImGui's background draw list), "ledges only", projected-space size. `draw.debugflag` was **removed** (debugFlags2 0x100 is the TR7 / TRAE path, catalog section 7) | `draw.markup [0/1]`, `draw.ledges [0/1]`, `draw.scale <w> <h>` |
| Quick access / Favourites | 0.3, **first page, open when the menu opens** (Status is now collapsed): one widget per favourite id (bool = checkbox, info = value, other = button that runs the item with its default argument); **Y** on an item pins / unpins it (on this page, in "Add an item" and on the Developer menu rows - other pages: use "Add an item" or TruLink); saved in `[Favorites] Ids`; default list (empty `Ids`): `player.invincible, player.health, time.scale, time.pause, level.reload, overlay.position, log.overlay, costume.next` (`camera.free` is skipped while it is a todo) | `fav.list`, `fav.add <id>`, `fav.del <id>` |
| Developer menu (original) | 0.3: Crystal's own debug menu, read at load from the tables in `.data` and drawn row by row: page links switch pages, flags / bools as checkboxes, ints as sliders / inputs with the table's limits, actions as buttons; the table's callbacks / functions run on the game thread. Every row shows its static facts (who reads the target in retail, empty functions) in blue; "All pages" lists every page, also those the retail root no longer links | `dev.list`, `dev.<label slug>` (42 ids, list below) |
| Time / player / HUD | 0.3: time scale slider, freeze world, hide HUD; player control, ragdoll death, mark / back to mark, camera fov; weapons / ammo / health (experimental, catalog section 17) | `time.scale <f>`, `time.pause [0/1]`, `ui.hide [0/1]`, `player.control [0/1]`, `player.die`, `player.teleport x y z`, `player.mark`, `player.recall`, `player.goto <inst>`, `camera.fov <rad>`, `player.health [n]`, `player.invincible [0/1]`, `weapon.list`, `weapon.give <name>`, `ammo.show`, `ammo.set <type> <n>`; 0.4 (TruLink / favourites, no own widgets on this page): `weapon.slots`, `weapon.has <name>`, `ammo.fill`, `gear.give <name>` |
| Instances | 0.3: the instance list (name filter, max 200 shown), per instance: Lara goes there, bring to Lara, unhide, remove; "Unhide all" | `instance.list [filter]`, `instance.info <inst>`, `instance.bring <inst>`, `instance.unhide <inst>`, `instance.unhideall`, `instance.remove <inst>` (`<inst>` = intro id, `0x<address>` or `#<index>`) |
| Outfits (live switch) | 0.3: "Next outfit" and one button per id of the game's outfit cycle list; switches at once (needs a level) | `costume.list`, `costume.next`, `costume.set <name\|id>` |
| Debug / Log | 0.3: the last lines of every `Tru*.log` next to the `.asi` / `tru.exe` (tailed once per second by the worker thread, shared read, only new bytes), the game's script prints (`log.script`), lines mentioning errors / exceptions in red, counters (exception lines, exceptions TruMenu caught in its own game calls); source filter buttons (TruLink.log holds the last TruLink commands); corner overlay bottom left. 0.4: repeated lines of a source collapse into one `text x42 (17:09:02-17:09:33)`, TruLink's read-type command lines are dropped, filter all / warnings + errors / errors (warnings yellow, errors red), at most `[Log] MaxLinesPerSecond` new lines per source and second (then one line "(n lines dropped ...)"), counters for all three | `log.page`, `log.show`, `log.script [0/1]`, `log.overlay [0/1]`, `log.lines <n>`, `log.filter <source\|all>`, `log.clear`; 0.4: `log.collapse [0/1]`, `log.hidereads [0/1]`, `log.level 0\|1\|2` (or `all` / `warn` / `error`), `log.rate <n>`; 0.7.2: `log.overlaysources <list\|*>`, `log.overlayexclude <list\|none>` (overlay only, section "Log overlay filter (0.7.2)") |
| Settings | 0.3: every `TruMenu.ini` key with its current value, changed keys marked `*` (yellow) with their default, missing keys shown with the default; "Favourites back to the default list" and "Reset all settings" - both need **A twice** (the button turns red: "press A again to confirm", 5 s) | `settings.show`, `settings.reset` (backup `TruMenu.ini.bak_<yyyymmdd_hhmmss>`, rewrite from the defaults table, reload the options; Scale / Enabled / Script apply at the next start), `fav.reset` |
| Media: videos | 0.3: `Movies\*.bik`, "Play" (main menu only), "as menu loop" | `media.video.list`, `media.video.play <name>`, `media.video.menuloop [name]` |
| Level select | current unit name (GameTracker+0x38), one button per unit of `[Levels] List` (default `dlc_level1_start`, `dlc_level2_start`), "Reload current unit", 0.7.1: "Start DLC 1 / DLC 2 as the mission menu (intro)" (0.7.2: DLC 1 first; a grey line says why level.load / level.start are refused right now), then **all 111 playable units** in tree nodes per group (see below). Any other unit: `menu level.load <unit>` over TruLink | `level.current`, `level.list` (all units: `group: unit unit ...; ...`), `level.presets` (`[Levels] List`; was `level.list` in 0.1), `level.load <unit>`, `level.reload`, 0.7.1 `level.start [dlc2\|dlc1\|<unit>]` (game thread, main menu only; "Game input frozen (0.7.1)") |
| Dev channel | there is no developer channel in `tru.exe` (TCP 9264 is FMOD's profiler). **TODO** re-enable the compiled-out log stub 0x6457a0 | `dev.log` (todo) |
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
later quits. Then: `TruMenu.log` line `game.quit by the owner (TruMenu) - logs flushed next, then TerminateProcess(...)`,
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
  `tests\regress\dlc2.txt` (DLC 2: 7 steps + 23 checks, from `docs/Regression-Schattenlara.md`), the row format of
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
  mark). At most 64 rows; `test.add` on a full list answers `err list full`.
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
| `[Test] AutoStart` | (empty = off) | 0.7.1, test only: `dlc2` / `dlc1` / a unit name - once per game start, when the main menu is up, `level.start` (mission menu path, intro plays); without the verified path `level.load` + log line "intro skipped" |
| `[Test] AutoStartDelay` | 3 | 0.7.1: seconds the main menu must be up before AutoStart starts, 1 .. 60 |
| `[Regress] List` | `all` | 0.8: list the Regression page shows at start: `dlc1`, `dlc2` or `all` |

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
