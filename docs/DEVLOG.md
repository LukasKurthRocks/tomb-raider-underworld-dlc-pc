# Development log

Snapshots from development builds - what the test tools show along the way, newest first. Nothing here is needed to
install or play; the [README](../README.md) and [INSTALL](INSTALL.md) cover that. Images are development builds (debug
overlays, log lines, sometimes substitute shaders), scaled down to 1280 px. The README shows the current state; older
pictures move here.

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
