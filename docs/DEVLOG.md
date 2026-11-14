# Development log

Snapshots from development builds - what the test tools show along the way, newest first. Nothing here is needed to
install or play; the [README](../README.md) and [INSTALL](INSTALL.md) cover that. Images are development builds (debug
overlays, log lines, sometimes substitute shaders), scaled down to 1280 px. The README shows the current state; older
pictures move here.

## 2026-11-14 - the sonar in Lara's Shadow says "MAP"

![Development build: the PDA sonar at the start of Lara's Shadow with TruMenu's full map on - instead of a map of the room it shows huge 3D block letters "MAP", with checkpoint flags and the portal to Yggdrasil hall 1 drawn by the debug view](screenshots/dev-sonar-map-placeholder-dlc2-2026-11-14.jpg)

*Development build, TruMenu 0.22.48 "full sonar map" on (draw every vertex as revealed, display only) with the
placeholder filter off, debug view labels on. At the foot of the Eitr fall (checkpoint 9400) the sonar map file of the
DLC 2 start unit holds no map of the room - only the developers' placeholder: the word "MAP" as a 100-face block mesh.
The same placeholder sits in base-game units that never got a sonar map (e.g. `l7_monastery`) and in every new
`dlc2_*` room; the Xbox 360 source and the DLC 2 prototype hold the identical mesh, so this is not a port error. Only
the three Yggdrasil units DLC 2 reuses from the main game have real maps. In normal play the letters are rarely seen
(the sonar reveals only what is near and in sight); with the full map TruMenu hides them by default (`[Sonar]
HidePlaceholder=1`). See [TRU-Knowledge.md](TRU-Knowledge.md) section 6, rows "Sonar maps DLC 2" / "Sonar maps DLC 1 /
base".*

## 2026-11-13 - "I am a rock": a hidden developer object in the Mediterranean

![Development build: Lara floating with TruMenu's flight cheat below the Mediterranean sea floor; under her a dark flat plane labelled "co_rock - I am a rock", behind her the sonar eye puzzle gate of the first underwater puzzle](screenshots/dev-co-rock-seafloor-2026-11-14.jpg)

*Development build, TruMenu flight cheat and debug view labels on (object names, checkpoints, portals, trigger volumes). Below the
playable geometry of `l1_seafloor`, near the eye puzzle gate of the first underwater puzzle, lies an object called
`co_rock` - in game a dark flat plane, its start state named "I am a rock". The data show a leftover developer cheat
object: its class script reads controller input (north / south / east / west and two diagonal moves), answers a wrong
step with "Nope", and its sub-objects print lines such as "activate cheeet", "ragdoll" and "game completed". No
script, cutscene or trigger of the game ever uses it, and floating through it does nothing - the input sequence is
still unknown. See [ENGINE.md](ENGINE.md) row "`co_rock` cheat object" and [TRU-Knowledge.md](TRU-Knowledge.md) row
"Cheats".*

## 2026-11-09 (evening) - thralls stop falling at every punch

No picture, the proof is in the logs: with TruShadowCombat 0.6.8 the tutorial thrall in hall02 takes three single
punches as on the Xbox 360 - attack, **Hit** (-20), back to waiting - instead of falling down, getting up and attacking
again and again. The cause was one check the Xbox title update added to Lara's contact hit: after the hit message the
game sends a short push (message 0x91); the title update skips it for enemies (flag 0x400000 on the thrall, now
measured), the PC - built from the code before that update - pushed every enemy into a fall. The plugin translates
that check 1:1 (`[Hit] TranslateImpulseGate`); switched off live, the old falling came straight back. Still open: the
punch combo does not chain yet (every press is punch 1), and a melee kill with the check on still has to be watched
([ENGINE.md](ENGINE.md) section 1, rows "Impulse 0x91" and "Lara's punch combo").

## 2026-11-09 (evening) - the light choice, frame by frame

![The throne in the held end-room cutscene, six frames 0.1 s apart: top row the game's own light order (the dropped shadow light changes every frame), bottom row TruMenu's fixed order (always the same light dropped)](screenshots/dev-throne-light-choice-2026-11-09.png)

*Development build, TruMenu's `light.cutlabels` on: every light the PC had to drop for an object in that frame gets a
label. Top row, the game's own order: the dropped shadow light alternates between #90 and #93 from frame to frame (first misread as #98) -
the throne's brightness jumps between 65 and 74 (of 255). Bottom row, `light.stable` (the default fix): always #94 is
dropped, the brightness stays at 65-69. The flicker explained in the entry below, now seen at work.*

## 2026-11-09 - the throne flicker explained: three lights too many

![Natla in the throne cutscene: top PC (lit warm, then cool, alternating), bottom Xbox 360 original in an emulator (warm hair and cool face at once)](screenshots/dev-natla-pc-vs-xbox-2026-11-09.png)

*Top: PC, six frames of the held cutscene (8 Nov) - Natla's face switches between a warm and a cool light. Bottom:
the same scene on the Xbox 360 original in the Xenia emulator (9 Nov), three frames - no flicker, and she is lit by
both lights at once. The cause, read from the code: a PC material shader takes at most 3 shadow lights + 3 plain
lights + the sun per drawn object, the Xbox shaders take 7 lights of any kind. The PC's light-set builder keeps the
first lights that fit, in the order of a light list that changes from frame to frame - so Natla gets a different
light every frame ([ENGINE.md](ENGINE.md) section 16, "Per-draw light limit" / "Light set builder"). Worked around
with TruMenu's `[Light] Stable` (a fixed order: no flicker, but only the warm light), a finer per-object order is in
test (`light.stablecut`); the full Xbox look would need different PC shaders.*

The README's title picture until 9 Nov, the same flicker up close:

![The throne in the end-room cutscene of Lara's Shadow, held with TruMenu's cutscene pause - its shadow light still flickers](screenshots/dev-throne-flicker-closeup-2026-11-08.gif)

## 2026-11-08 - the flicker at the throne, with the cutscene held

![The throne in the DLC 2 end-room cutscene flickering while the cutscene stands still](screenshots/dev-flicker-throne-2026-11-08.gif)

*Development build, test overlays on (object names, sound list). The end-room cutscene of Lara's Shadow is held with
TruMenu's new cutscene pause (`cine.pause`, 0.22): time, actors and camera stand still, the world runs on - and the
throne still switches between lit and dark, the figures on the stairs with it. So the flicker is not the cutscene's
timeline but something that exists only while the cutscene runs (in normal play the throne does not flicker). Ruled
out so far: a doubled pod model (`dlc2_uo_natlapod`, an exact runtime copy on top of the placed one - removed live,
the flicker stayed) and the black fade card. The walls with baked light stay steady, so the next suspect is the
dynamic light per model (the cutscene brings its own lights around the figures). Recorded 4 s of the game window, 12
frames per second. (Explained on 9 Nov, see above.)*

## 2026-11-08 - the README's former status block (state 2026-11-05, updated 2026-11-08)

On 2026-11-08 the README got a short status table instead; the plugin details moved to [PLUGINS.md](PLUGINS.md). The
former text is kept here as it was (links adjusted to this folder).

The former introduction: *For Lara's Shadow this fork takes its own route: its own conversion of the DLC 2 data, and
the Doppelgänger's shadow power - which came to the Xbox with a game update, not with the DLC files - rebuilt as small
add-ons for the PC game, together with tools that repair converted data and help testing in the game.*

**Current state (2026-11-05, tested on one PC, not a release)**

- DLC 1 (B138): fixes found while testing - the "display driver" box on entering the DLC (shader constants), the
  grapple ring's look, cinematic speech in all five languages. Rebuilt reproducibly by the pipeline step `Repair`.
  DLC 1 starts correctly after playing DLC 2 in the same session (played).
- DLC 2 (*Lara's Shadow*), played in our test builds through the Yggdrasil halls: intro, loading-screen title and
  hint boxes like on the Xbox; the Doppelgänger's original look (title-update shaders translated); the shadow power
  (slow motion, meter and its HUD); the wall run on the rock veins with its camera; the shadow combat moves; the
  waterfall. The crash when thralls were unloaded is fixed, dying around the wall run no longer crashes. The end area
  was reached by a level change, not yet played through in one go. Test evening 8 Nov 2026: the end cutscene is
  visible (it was black), the ceremony room no longer crashes while the goo cannonballs fly, the end-room floor is
  textured and the goo particles look right (soft drips instead of square dots).
- Both DLC: the data fixes found through crash dumps are pipeline steps (WINDOWS_REBUILD.md findings 44-48); our
  `generalbank` (the title update's loading-screen and hint-box scripts ported to PC) is built by the pipeline step
  `Generalbank`.
- Testing: test runs from profiles with automatic log checks (`Invoke-TruTestRun.ps1`, `tests/profiles/`), an
  in-game controller menu with a radial menu and a guided test flow (`TruMenu`), a local link for scripted checks
  (`TruLink`) and a log-only trace of sounds, state changes, spawns and level loads (`TruTrace`).

The README picture's former caption: *Current development build (7 Nov 2026): the start of Lara's Shadow with the test
menu's quick bar, page "Kostueme" (TruMenu 0.21.6) - every outfit of the game's cycle list, here the DLC costume f
"Casual Explorer".*

**Still missing (short list)**

- DLC 2, **where manual play stops now (8 Nov 2026):** jumping from a ledge to a rock vein - Lara reaches the vein's
  attach state, then turns back to the ledge within half a second (state-chart log taken, analysis pending). Getting
  further needs the test menu's teleports.
- DLC 2: the shadow finisher never starts (its target list stays empty); thralls now take damage and die with the
  translated damage switch (`TruShadowCombat` `[Damage] Translate`, live test 07.11.), a full playthrough of the first
  thrall fight is being tested; a moaning sound loops; Lara's ponytail stretches during the slow motion (the title
  update's cloth time step is translated behind a switch, off by default); some title-update shaders are still drawn
  with substitutes; the achievement fix is untested in game.
- DLC 1: a crash while loading the dungeon in our current test builds (under investigation).
- Costume packs: converted and checked offline (pipeline step `Costumes`), not played yet.
- What we check after every change: [Regression-DLC2.md](Regression-DLC2.md) (DLC 2) and
  [Regression-DLC1.md](Regression-DLC1.md).

## 2026-11-07 - the enemy navmesh, drawn by the game itself

The PC `tru.exe` still contains the complete debug drawing of the pathfinding middleware (NavPower). The switches are
plain bytes in the executable and are off in the retail build. TruMenu 0.21 turns them on from the quick bar (page
*Render-Details*, group *Navmesh*); this evening they were seen on screen for the first time.

![Development build: navmesh outlines in the corridor between Yggdrasil hall 02 and the end area](screenshots/dev-navmesh-hall02-corridor-2026-11-07.jpg)
*Lara's Shadow, corridor from the second Yggdrasil hall to the end area. Green: the outlines of the navmesh areas -
the floor the thralls may walk on. It only appears with two quick bar rows on: "Navmesh Flaechen" (the game's
`planner_areas` switch) and "Alle Ebenen" (the layer mask; the navgraphs of this unit sit on layers 11 and 12, which
the game leaves out of the mask). Bottom left: TruMenu's log overlay with exactly these two switches.*

![Development build: navmesh on the towers and platforms of the end area, seen from above](screenshots/dev-navmesh-end-towers-2026-11-07.jpg)
*The end area from above (TruMenu's flight mode; key line bottom right). The outlines lie on the tower tops, ledges and
platforms; large areas also reach across the water, and one group floats without floor near the waterfall - possibly
left over from the base-game level this area was built from (not checked yet). The hint at the top is the title
update's finisher hint, which our port shows but does not close yet (the closing messages 34 / 38 are still to be
translated).*

Edge colours, read from the game's draw function (`0x40c3a0`, colours at `0x88e484` ff.): green = plain edge,
red = one side has area flag bit 27, blue / magenta = area flag bit 26 differs / is set, yellow / orange = two 4-bit
area values compared. What the flags mean is not known yet. The installed navgraphs are byte-identical to the Xbox
data, so none of this is a conversion artefact.

## 2026-11-07 - quick bar pages: plugin switches, costumes, a borrowed outfit

![Development build: quick bar page Fixes in the DLC 2 mission menu](screenshots/dev-quickbar-fixes-2026-11-07.jpg)
*TruMenu 0.21.5, page "Fixes": all 113 INI switches of our plugins in one place, one group open at a time, "live" or
"Neustart" (takes effect after a restart) per row. Here the shadow power group, over the DLC 2 mission menu.*

![Development build: Lara in the doppelganger outfit with the DLC 2 shadow meter](screenshots/dev-doppelganger-costume-hud-2026-11-07.jpg)
*Costume test in TruMenu 0.21.6 at the start of Lara's Shadow: switched back from costume f to `doppelganger_casual`, the
outfit that loads the DLC 2 player extension with it - the game then treats Lara as the doppelganger again and shows
the shadow meter (top left, red and yellow).*

## 2026-11-06 - debug view at Croft Manor

![Development build: TruMenu debug view, Croft Manor forecourt](../assets/dev-debugview-manor-forecourt-2026-11-06.jpg)
*The test menu's debug view (TruMenu 0.15) in the base game, on the forecourt at Croft Manor's entrance during the
end-of-chapter cutscene. Trigger volumes by kind (red: fire that kills, yellow: plain, cyan: planes), the loading area
between the main hall and the exterior, the active checkpoint and object names. The main hall's triggers hang beside
the cutscene's facade set - the walkable interior is not behind it.*

## 2026-11-02 - thralls in the second Yggdrasil hall

![Development build: Lara's Shadow, Yggdrasil hall 02](../assets/dev-dlc2-hall02-thralls-2026-11-02.jpg)
*DLC 2 in the second Yggdrasil hall with the test menu's log overlay. The thralls still use substitute shaders here
(translated since).*
