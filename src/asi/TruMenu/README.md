# TruMenu.asi

In-game debug menu for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld, image base 0x400000), operated with the
**Xbox controller** and drawn with [Dear ImGui](../third_party/imgui/README.md) (MIT, v1.91.9). Every menu entry is also
an **item with a stable id** that tools can list and run without the controller (exports `TruMenuList` /
`TruMenuInvoke`, TruLink command `menu`).

**Status: 0.1 built 2026-10-31 and checked with `dumpbin` only (x86 DLL, imports `KERNEL32.dll` + `USER32.dll`,
exports `TruMenuVersion` / `TruMenuList` / `TruMenuInvoke`) - not yet run in the game.**

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
| Status | TruMenu version, `tru.exe` PE time stamp / image size, all code checks, whether a level is loaded, our plugins (`TruShadowPower`, `TruDoppelganger`, `TruDlc2Player`, `TruRockVein`: loaded? `<Name>Version()` string), ModLoader.asi, the pad chain (what the game calls, what PadHook calls, with module names), the `d3d9.dll` in use (game folder = TRAWindowed proxy, else system), device / window | `status.version`, `status.hooks` |
| Overlay: Lara's position | checkbox for a small top-left overlay with Lara's position and heading; position / rotation in the page | `overlay.position`, `player.position` |
| Free camera | known facts; experimental `CAMERA_SetMode(mode)` with a mode slider (TRLAU enters its free camera with mode 11; TruLink notes that retail switches only for 6, 11, 12) and "Restore game camera". **TODO** own free camera (moving the camera transform with the sticks) | `camera.current`, `camera.mode <n>`, `camera.restore`, `camera.free` (todo) |
| Cheat / flight | `GameTracker.cheatMode` + player message 12 (TRLAU "skew" cheat); while on and the menu is closed **RT lifts, LT lowers** Lara (`[Cheat] FlightSpeed` per 30 fps frame) | `cheat.flight [0/1]`, `cheat.speed <v>` |
| Markup / collision draw | experimental toggle of `GameTracker.debugFlags2` bit 0x100 (TRLAU: debug draw; effect in retail unknown). **TODO** own markup drawing | `draw.debugflag [0/1]`, `draw.markup` (todo) |
| Level select | current unit name (GameTracker+0x38), one button per unit of `[Levels] List` (default `dlc_level1_start`, `dlc_level2_start`), "Reload current unit". Any other unit: `menu level.load <unit>` over TruLink | `level.current`, `level.list`, `level.load <unit>`, `level.reload` |
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
- `menu.open`, `overlay.position`, `cheat.speed` run at once on the caller's thread. `camera.mode`, `camera.restore`,
  `cheat.flight`, `draw.debugflag`, `level.load`, `level.reload` are queued (one slot) and run on the **game thread**
  - inside PadHook, or inside the Present hook while the game does not poll the pad; `TruMenuInvoke` waits up to 3 s
  and returns the result, else `ok queued <id> (...)` and the item runs at the next frame. A second request while one
  is pending answers `err busy`.
- The returned text lives in a buffer of the calling thread until that thread's next call.
- TruLink 0.2: `menu list`, `menu <id> [arg]` (e.g. `Invoke-TruLink.ps1 -Command 'menu level.load dlc_level2_start'`).

## Hooks

Every address below is checked against the expected bytes at load (`Start()`); on a mismatch that part stays off,
the reason goes to `TruMenu.log` and the Status page shows `NO`. Nothing is patched in the game code itself.

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
`ppReturnedDeviceInterface` of the CreateDevice call at tru+0x122736, i.e. **manager+0x208** (`lea ebx,[esi+0x208]`
at tru+0x122711). A worker thread polls that pointer (50 ms until found, then every second for a new device) and
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
| debugFlags2 | 0xe7f09c (GameTracker+0x14), bit 0x100 | - | TRLAU `Game.h`, `modules/Debug.cpp` |
| INSTANCE_Post(instance, msg, data) | 0x5b3750, cdecl | prologue bytes | TRLAU `instance/Instance.cpp`; message 12 = flight from `Skew.cpp` |
| CAMERA_SetMode(mode) | 0x5f39f0, cdecl | prologue bytes | TRLAU `game/Camera.cpp`, docs `Befund-Entwicklerkanal.md` |
| camera restore | 0x5edf50, thiscall CameraManager 0xe804f0 | prologue bytes | TRLAU `modules/camera/Underworld.cpp` |
| GAMELOOP_RequestLevelChangeByName(name, gameTracker, doneType) | 0x5df8c0, cdecl, doneType 4 | prologue + name copy to GameTracker+0x38 | name / signature TRLAU `game/Game.cpp`; doneType 4 and the reload of GameTracker+0x38 from the game's own callers tru+0x1dfb73 / tru+0x3744b3 |
| frame time | float 0xe7f190 (30 fps units) | store at 0x5da40c | TruShadowPower |

The level change is refused while `GameTracker+0xb9` is set (the function itself ignores requests then) and for names
with characters other than `a-z 0-9 _ -` or longer than 63 characters; the menu closes after a request.

## Options (`TruMenu.ini` next to the `.asi`, optional)

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

## Credits

- **Dear ImGui** by Omar Cornut and contributors (MIT), unmodified in `src/asi/third_party/imgui`.
- **TheIndra55/TRLAU-menu-hook** (GPL v3, <https://github.com/TheIndra55/TRLAU-menu-hook>) was **read as a reference
  only** (2026-10-31, raw.githubusercontent.com): the TR8 addresses / signatures / flags marked "TRLAU" above (GameTracker
  layout, Instance position offset, INSTANCE_Post, CAMERA_SetMode / restore, cheatMode + message 12, debugFlags2 0x100,
  GAMELOOP_RequestLevelChangeByName) come from it. No code or structure of it is used; TruMenu's hooks (import filter
  for the pad, device-vtable patch found through the game's own device manager) are our own and differ from its
  approach (an inline hook of the game's D3D init function and the game's frame callbacks).
- Camera manager / mode facts cross-checked in `docs/Befund-Entwicklerkanal.md` of the project.

License: MIT, as the repository.
