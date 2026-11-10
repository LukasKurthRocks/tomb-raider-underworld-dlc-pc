"""Check that the shipped src/asi/TruMenu/TruMenu.ini is exactly the text TruMenu writes from its defaults table
(kOpts in TruMenu.cpp, DefaultIniText) - read-only. Since TruMenu 0.8 also the regression lists tests/regress/*.txt
(TruMenu.tests.txt row format, 8 tab-separated columns; step ids step<n> = number; ids unique; every check id named in
backticks in its source doc docs/Regression-DLC1.md / docs/Regression-DLC2.md; ASCII only).
Since TruMenu 0.8.1 a row may have a 9th column "shortcut" (Prepare button / regress.prepare): ';'-separated commands,
optional first element "#title"; checked: at most 12 commands, 319 characters, every command starts with an item id of
kItems in TruMenu.cpp, no game.quit, level.load takes one unit name (a-z 0-9 _ -), bool items take 0 / 1.
Since TruMenu 0.10 also the radial menu file src/asi/TruMenu/TruMenu.radial.txt ("path | label | item id [arg]"):
ASCII only, first line "# TruMenu radial menu", three fields, path segments / labels at most 47 characters, every item
id in kItems (dev.<slug> rows are only known at run time and are accepted), none of the ids TruMenu never offers in the
ring (kRadForbidden in TruMenu.cpp - the list here must be the same: game.quit, cmd.run, save.*, settings.reset), bool
items take 0 / 1, instance.spawn / level.load one name, the limits of TruMenu.cpp (256 entries, 48 levels, 64 per level).
Since TruMenu 0.10.1 also the tour file src/asi/TruMenu/TruMenu.tour.txt (written by tools/tour_from_rundgang.py; the
same format and rules, first line "# TruMenu tour", its levels below Tests/Rundgang), the [Radial] values of the INI
(Mode menu / wheel, Freeze world / player / 0 / 1 / 2, QuitSector and TestsLevel 0 / 1; since 0.10.3 FreezeSound
0 / 1, since 0.10.4 FreezeShaderClock 0 / 1) and the limits with the built-in entries of Mode=menu (top level + "Tests" + "Spiel beenden", Tests = 4 virtual
folders + Rundgang + 1 slot).
Since TruMenu 0.10.5 also the [Shot] values (Enabled / Clean 0 / 1, Hotkey a virtual key 0 .. 0xFE as hex or decimal,
MaxPerMinute 0 .. 120, Folder without < > " | ? *), the ids shot.save / shot.status / claude.mark in kItems, the six
Claude marks of the radial file (level "Claude" on the top level: claude.mark now / good / bug / gfx / sound / stutter,
no other item there) and the exports TruMenuShot / TruMenuMark in TruMenu.cpp.
Since TruMenu 0.11 also the [Flow] values (Enabled / Overlay / AutoAdvance 0 / 1, Position tl / tr / bl / br, Size 0.5 ..
3, Lines 1 .. 3, ToastSeconds 1 .. 30, PollMs 100 .. 5000, File), the flow items in kItems, the include of TruFlowCore.h,
and the flow entries flow.next / flow.skip / flow.back / flow.status (no argument, once each) allowed in the level Claude
next to the six marks (which keep their order).
Since TruMenu 0.12 also the [Debug] values (Enabled / NavMask 0 / 1, NavDraw a comma list of the switch names of
kNavSwitches in TruMenu.cpp), the items nav.status / nav.draw / nav.mask / nav.off in kItems and the nav.* entries of the
radial file (nav.draw takes exactly one switch name of kNavSwitches, nav.mask / nav.off / nav.status no argument).
Since TruMenu 0.13 also the [Debug] label values (Labels / LabelCross 0 / 1, LabelRadius 100 .. 50000, LabelMax 1 .. 32,
LabelMatch a comma list of name parts a-z 0-9 _ or *), the item dbg.labels in kItems and exactly one dbg.labels entry
in the radial file (no argument).
Since TruMenu 0.14 (2026-11-06 TruMenu 0.14 triggers) also the [Debug] debug view values (View / Triggers / Trg* /
Portals / Checkpoints / TrgLabels / Legend / Markup / Persist 0 / 1, TriggerMax 1 .. 256, TriggerRadius 500 .. 200000,
TriggerLabelMax 0 .. 64, ViewNav a comma list of kNavSwitches names), the items dbg.view / dbg.triggers / dbg.show /
dbg.portals / dbg.checkpoints / dbg.legend / dbg.status in kItems, every layer of kDvLayers once in the radial file
(dbg.show <layer> or its own bool item) and dbg.show taking exactly one layer name of kDvLayers; the object name keys
(Names / NameIds 0 / 1, NameMatch a comma list or empty, NameRadius 100 .. 200000, NameMax 1 .. 64, NameScale 0.5 .. 3,
NameColour RRGGBB), the items dbg.names / dbg.namefilter / dbg.namecolour / dbg.namesize and their ring arguments.
Since TruMenu 0.15 (2026-11-06 TruMenu 0.15 render mode) also the render mode keys (Slide / EnemyColl / Census / Flat /
FlatModels / FlatEdges / FlatAnyTarget 0 / 1, CollRadius 500 .. 200000, CollMax 100 .. 20000, CensusFrames 10 .. 1200,
FlatPasses a hex / decimal mask of the pass ids 0x200 0x100 0x80 0x400 0x800 1 2 (0xf83), FlatColour material / class),
kDvLayers with 15 layers (slide / enemycoll have their own items dbg.slide / dbg.enemycoll), the items dbg.census /
dbg.flat / dbg.flatpass / dbg.flatpasses / dbg.flatcolour / dbg.flatmodels / dbg.flatedges / dbg.flatanyrt / dbg.render /
dbg.slide / dbg.enemycoll in kItems and their ring entries: each switch once without an argument, dbg.flatpass once per
pass id, dbg.flatcolour once for material and once for class, dbg.flatpasses with census / default / a mask.
Since TruMenu 0.16 (2026-11-06 TruMenu 0.16 readability) also the display keys (Fade / Fill / LabelShort / LaraIn 0 / 1,
Depth 0 .. 2, DepthDim 5 .. 80, DepthCall 0 .. 7, LineAlpha 10 .. 100, LineBright 30 .. 150, FadeStart 0 .. 100000,
FadeEnd 500 .. 200000, FadeMin 0 .. 100, FillAlpha 2 .. 40, ViewLabelMax 0 .. 64, Enclosing 0 .. 2, EnclosingSize 100 ..
100000, MarkerMax 2 .. 50, TriggerMax now 1 .. 512, ViewSkip a comma list of kDvLayers names or empty), the items
dbg.depth / dbg.alpha / dbg.bright / dbg.fade / dbg.fill / dbg.short / dbg.larain / dbg.enclosing / dbg.style in kItems
and their ring entries (dbg.depth once each for on / dim / off, dbg.enclosing once each for normal / dim / hide,
dbg.alpha 10 .. 100, dbg.bright 30 .. 150, the switches once without an argument) and the flight entries of the ring
(cheat.flight once without an argument, cheat.speed with a number 0 .. 1000).
Since TruMenu 0.17 (2026-11-06 TruMenu 0.17 quick toggles) also DepthCall -1 .. 7, the [Quick] keys (Enabled / ShowClosed
0 / 1, OpenButtons a mask without D-pad / LB / RB, ChordMs 50 .. 1000, Language de / en, Top 5 .. 80, Scale 0.5 .. 3),
[Shot] OnCine 0 / 1, OnCinePairs / OnCineFastPairs 1 .. 50, OnCineIntervalMs 250 .. 10000, OnCineSlowMs 250 .. 60000,
OnCineSignal cine / camera / both, [Debug] CheckpointHide (intro ids or empty), the items quick.* / shot.oncine /
dbg.depthdump / dbg.cp* / pos.* in kItems, the quick-toggle bar's row tables kQbDebug .. kQbAi (every item id in kItems,
bool rows on bool items or dbg.show <layer>, value rows on the value items, every kDvLayers layer reachable) and the new
ring entries (quick.open / shot.oncine / dbg.depthdump / dbg.cplist / dbg.cpall 0 / dbg.cpall 1 once each).
Since TruMenu 0.18 (2026-11-06 TruMenu 0.18) also [Menu] OverlayLaraIn / [Debug] LegendLaraIn / [Saves] DirectLoad /
[Shot] OnCineSegments 0 / 1, the items overlay.larain / pos.goload / save.load in kItems, save.load in kRadForbidden (and
never in the ring), the bar's row tables kQbEmergency .. kQbAccess (new kinds: info rows on info items, choice rows on
action items, label / planned rows with id "-" and a planned row's text "German|English"; kQfConfirm / kQfBackup rows
are actions; level.load rows take one unit name a-z 0-9 _; time.scale is a value item), the ring's overlay.larain once
(no argument), pos.goload with a saved name or last, time.scale with a number 0 .. 10.
Since TruMenu 0.19 (2026-11-06 TruMenu 0.19 dumb AI) also the [AI] keys (Dumb 0 .. 2, DumbFilter a comma list of name
parts a-z 0-9 _ or empty, DumbMode purge / gate, NoInvestigate / NoAttack 0 / 1), every INI comment shorter than 512
characters (DefaultIniText cuts there), the items ai.dumb / ai.mode / ai.noinvestigate / ai.noattack / ai.status in
kItems, the presets of kAiPresets (all / sharks / spiders / thralls) plus filter, bool rows "ai.dumb <preset>" in the bar
(the only bool rows with an argument besides dbg.show), ai.mode as a value row, the ring's ai.dumb entries (exactly one
preset word, all / sharks / spiders each at least once, sharks / spiders also in Spieler/Barrierefreiheit), ai.noinvestigate
/ ai.noattack / ai.status once each without an argument, the Barrierefreiheit bar page without the planned row "Haie",
and the 0.19 precheck tables kAiChecks / kAiGateChecks / kAiBitChecks present with at most 64 bytes per check.
Since TruMenu 0.20 (2026-11-06 TruMenu 0.20) also 17 layers (collect / enemies with their own items dbg.collect /
dbg.enemies), [Debug] Collect / Enemies 0 / 1, MarkRadius 500 .. 200000, MarkMax 1 .. 64, [Media] MuteMusic / MuteAmbient
0 / 1, the defaults DumbMode gate / Depth 2 / FlatPasses 0x600 in kOpts, the items dbg.collect / dbg.enemies /
media.mutemusic / media.muteambient / pos.portal, the owner's bar rows (Leveldaten collectibles; Render / KI enemies,
enemy health, edges; Zeit / Test music / ambience off; game.quit as the last plain action row of Notfall), the ring's
dbg.collect / dbg.enemies / media.mutemusic / media.muteambient once without an argument (pos.portal never), and the
precheck tables kCoChecks / kAiForgetChecks / kSndMusicChecks with at most 64 bytes per check.
Since TruMenu 0.20.1 (2026-11-06 sound list) also the [Sound] values (List / OnlyPlaying / ShowMusic / ShowSfx /
ShowSpeech / ShowOther 0 / 1, Position bl / tl / tr / br, MaxLines 1 .. 40, RefreshMs 100 .. 10000, Sort group / volume /
name, FontScale 0.5 .. 3) and [Debug] EnemyStateLog 0 / 1, the snd.* items in kItems (snd.dump on the game thread),
snd.pos / snd.lines / snd.sort as value rows, the bar rows on Debug / Darstellung (every snd.* switch) and Zeit / Test
(snd.list, snd.dump), the ring's snd.* entries (snd.list in Zeit and Spieler/Debug/Ton, the four corners once each,
snd.dump once, snd.sort group / volume / name, snd.lines 1 .. 40, bool / info / dump entries without argument), the
precheck tables kSnChecks / kSmChecks / kEsChecks with at most 64 bytes per check, and SndMuteTick trying the FMOD group
mute (g_smOk / SmMuteOn) before the 0.20 SOUND_SetMusicVolume path.
Since TruMenu 0.21.3 (2026-11-07 quick bar X / Y, sound list width) also: kQbOwn = 0xC30F (D-pad / LB / RB + X / Y; a
[Quick] OpenButtons holding X or Y is refused like D-pad / LB / RB), QuickTick takes Y before X before left / right,
QbExecRow (value rows never run, bool rows toggle from QbRowOn, the rest = the right press), QbFavPin (rows with an
argument refused before FavSet, no other write of the favourites), the footer "X: ausfuehren  Y: Favorit" (DE / EN) and
the confirmation text "rechts / X nochmal", TruMenuPadBlock unchanged in meaning (kQbOwn while open, bits 16 / 17 / 18),
the [Quick] Enabled / OpenButtons comments naming X / Y, SnRow aligned to the frame's widest row (no
GetContentRegionAvail in SnRow; DrawSoundList measures every row before it draws one).
Since TruMenu 0.21.4 (2026-11-07 hall02 counter) also: the items fix.hall02 (action, game thread; help text names the
saves whose checkpoint 11258 already holds thralls) and thrall.scriptval (action, not on the game thread, read only);
the page Tests rows (fix.hall02 = action with kQfConfirm, thrall.scriptval); RunFixHall02's guards in order (unit
hall02, dispatcher values present, broken refused, a living object-1004 thrall refused - all before the first
sticky.set), tutorial before population, the 18509 rule (only when below 2), exactly two sticky.set calls and no other
write, the reply naming the arena trigger 11268 and "Betreten / Verlassen"; H2Alive (present, kill flag, AkDying = the
four death states, RegenerateDeath not among them); H2ValueAddr ([inst+0x60] -> +0xc -> +8, zero pointers refused);
H2IsThrall by object id 1004 and name; thrall.scriptval without any write; no E3 safety net (no [Fix] Hall02Restore,
no H2Tick / fix.hall02restore - docs/Befund-Hall02-TU-Vergleich-0711.md: a PC data bug, the Xbox never restores
thralls there); the precheck table kH2Checks (whole bytes, at most 64, no foreign byte); no code patch and no direct
store in the section (no WriteDword / VirtualProtect / volatile write).

Since TruMenu 0.21.5 (2026-11-07 Fixes + frozen ring) also the switches file src/asi/TruMenu/TruMenu.switches.txt
(first line "# TruMenu switches", ASCII, group lines "group | key | DE | EN [| open]", switch lines "Plugin | Section |
Key | bool / int:lo..hi[:step] / choice:a,b | DE | EN | live / restart / live-if:<Key> | default | hint [| since]",
at most 160 rows / 24 groups, no key twice): every key in its shipped plugin INI (src/asi/<Plugin>/<Plugin>.ini) with
the default = the INI value (a row whose "since" version is newer than the plugin source may wait), the INI value
fits the type, every live / live-if row has the plugin re-read function of SW_LIVE (body holds the section and key
literals), no restart row is re-read, every key of the eight plugin INIs has a row (text filters excepted); the items
sw.set / sw.list / sw.reload (not game thread), page Fixes, RunSwSet order (listed key, value fits, INI exists,
value changed, then the one write), the marker in SwLoadLocked, Y refused on page Fixes, X with kQbXDir, the menu
sections PageSwitches / PageQbAll, Build-TruAsi.ps1 / Set-TruMenu.ps1 copy the file; the frozen ring: its header
says so ("aktuell nicht weiter gemacht"), at most 172 entries, every entry is a bar row (ring_parity: bool rows take
0 / 1 / no argument, value rows their steps, choice rows their choices, other rows the same argument).
Options: --switches FILE checks that file instead of the shipped one.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_ini_check.py            compare + list check, print the first difference / every
                                                         list problem; exit 1 on a mismatch
  ../bin/pyt -t 60 tools/trumenu_ini_check.py --print    print the text generated from the table
  options (negative tests on copies): --ini FILE, --radial FILE, --tour FILE check that file instead of the shipped one;
  since 0.19 also --cpp FILE (a copy of TruMenu.cpp: the table rules of the bar, kItems, kAiPresets, the precheck tables)
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
INI = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.ini')
# 0.22.6 (2026-11-09): TruMenu's German texts carry umlauts as octal UTF-8 escapes (tools/trumenu_umlauts.py); the checks
# below compare with the ASCII spelling, so the source is read with those escapes turned back into ae / oe / ue / ss
# (a text with umlauts then counts 2 characters per umlaut - stricter than on screen)
UMLAUT_ESCAPES = {r'\303\244': 'ae', r'\303\266': 'oe', r'\303\274': 'ue', r'\303\204': 'Ae', r'\303\226': 'Oe',
                  r'\303\234': 'Ue', r'\303\237': 'ss'}


def read_cpp():
    src = open(CPP, 'r', encoding='utf-8').read()
    for esc, ascii_text in UMLAUT_ESCAPES.items():
        src = src.replace(esc, ascii_text)
    return src
REGRESS = {'dlc1.txt': 'Regression-DLC1.md', 'dlc2.txt': 'Regression-DLC2.md'}
RADIAL = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.radial.txt')
TOUR = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.tour.txt')
RADIAL_FORBIDDEN = ['game.quit', 'cmd.run', 'save.delete', 'save.restore', 'save.import', 'settings.reset', 'save.load']
RADIAL_VALUES = {'Mode': ('menu', 'wheel'), 'Freeze': ('world', 'player', '0', '1', '2'), 'QuitSector': ('0', '1'),
                 'TestsLevel': ('0', '1'), 'FreezeSound': ('0', '1'), 'FreezeShaderClock': ('0', '1')}
SHOT_VALUES = {'Enabled': ('0', '1'), 'Clean': ('0', '1')}       # 0.10.5; Hotkey / MaxPerMinute / Folder in check_shot
CLAUDE_KINDS = ['now', 'good', 'bug', 'gfx', 'sound', 'stutter']
# 0.11 Ablauf: [Flow] values, the flow items, the flow entries allowed directly in the ring level Claude
FLOW_VALUES = {'Enabled': ('0', '1'), 'Overlay': ('0', '1'), 'AutoAdvance': ('0', '1'),
               'Position': ('tl', 'tr', 'bl', 'br')}
FLOW_RANGES = {'Size': (0.5, 3.0), 'Lines': (1, 3), 'ToastSeconds': (1, 30), 'PollMs': (100, 5000)}
FLOW_ITEMS = ['flow.status', 'flow.list', 'flow.next', 'flow.back', 'flow.skip', 'flow.goto', 'flow.add', 'flow.say',
              'flow.result', 'flow.reload']
FLOW_RING = ['flow.next', 'flow.skip', 'flow.back', 'flow.status']
# 0.12 Debug-Zeichnung: the nav items and their types
NAV_ITEMS = {'nav.status': 'info', 'nav.draw': 'action', 'nav.mask': 'bool', 'nav.off': 'action'}
# 0.13 Thrall-Labels: the [Debug] label keys, their ranges, the item
LABEL_KEYS = ('Labels', 'LabelRadius', 'LabelMax', 'LabelMatch', 'LabelCross')
LABEL_RANGES = {'LabelRadius': (100, 50000), 'LabelMax': (1, 32)}
LABEL_ITEMS = {'dbg.labels': 'bool'}
# 0.14 debug view: the [Debug] keys (0 / 1 or ranges), the items, the layers that have a bool item of their own
DV_BOOL_KEYS = ('View', 'Triggers', 'TrgDeath', 'TrgFire', 'TrgCheckpoint', 'TrgWater', 'TrgSound', 'TrgVolume',
                'TrgPlane', 'TrgUnknown', 'Portals', 'Checkpoints', 'TrgLabels', 'Legend', 'Markup', 'Persist', 'Names',
                'NameIds',
                'Slide', 'EnemyColl', 'Census', 'Flat', 'FlatModels', 'FlatEdges', 'FlatAnyTarget',   # 0.15
                'Fade', 'Fill', 'LabelShort', 'LaraIn',                                              # 0.16
                'Collect', 'Enemies')                                                                # 0.20
DV_RANGES = {'TriggerMax': (1, 512), 'TriggerRadius': (500, 200000), 'TriggerLabelMax': (0, 64),
             'NameRadius': (100, 200000), 'NameMax': (1, 64), 'NameScale': (0.5, 3),
             'CollRadius': (500, 200000), 'CollMax': (100, 20000), 'CensusFrames': (10, 1200),   # 0.15
             'Depth': (0, 2), 'DepthDim': (5, 80), 'DepthCall': (-1, 7), 'LineAlpha': (10, 100),  # 0.16 (0.17: -1 auto)
             'LineBright': (30, 150), 'FadeStart': (0, 100000), 'FadeEnd': (500, 200000), 'FadeMin': (0, 100),
             'FillAlpha': (2, 40), 'ViewLabelMax': (0, 64), 'Enclosing': (0, 2), 'EnclosingSize': (100, 100000),
             'MarkerMax': (2, 50),
             'MarkRadius': (500, 200000), 'MarkMax': (1, 64)}                                       # 0.20
DV_FLOAT_KEYS = ('TriggerRadius', 'NameRadius', 'NameScale', 'CollRadius',     # the others are whole numbers
                 'FadeStart', 'FadeEnd', 'EnclosingSize',                      # 0.16
                 'MarkRadius')                                                 # 0.20
DV_ITEMS = {'dbg.view': 'bool', 'dbg.triggers': 'bool', 'dbg.show': 'action', 'dbg.portals': 'bool',
            'dbg.checkpoints': 'bool', 'dbg.legend': 'bool', 'dbg.status': 'info', 'dbg.names': 'bool',
            'dbg.namefilter': 'action', 'dbg.namecolour': 'action', 'dbg.namesize': 'action',
            # 0.15 render mode
            'dbg.census': 'action', 'dbg.flat': 'bool', 'dbg.flatpass': 'action', 'dbg.flatpasses': 'action',
            'dbg.flatcolour': 'action', 'dbg.flatmodels': 'bool', 'dbg.flatedges': 'bool', 'dbg.flatanyrt': 'bool',
            'dbg.render': 'info', 'dbg.slide': 'bool', 'dbg.enemycoll': 'bool',
            # 0.16 readability
            'dbg.depth': 'action', 'dbg.alpha': 'action', 'dbg.bright': 'action', 'dbg.fade': 'bool', 'dbg.fill': 'bool',
            'dbg.short': 'bool', 'dbg.larain': 'bool', 'dbg.enclosing': 'action', 'dbg.style': 'info',
            # 0.20 collectibles / enemies
            'dbg.collect': 'bool', 'dbg.enemies': 'bool'}
# 0.16: ring entries with a fixed set of arguments (each once), percent presets, switches without an argument (once)
DP_RING_ARGS = {'dbg.depth': ('on', 'dim', 'off'), 'dbg.enclosing': ('normal', 'dim', 'hide')}
DP_RING_PERCENT = {'dbg.alpha': (10, 100), 'dbg.bright': (30, 150)}
DP_RING_SWITCHES = ('dbg.fade', 'dbg.fill', 'dbg.short', 'dbg.larain', 'dbg.style')
DV_OWN_ITEM = {'portals': 'dbg.portals', 'checkpoints': 'dbg.checkpoints', 'legend': 'dbg.legend', 'names': 'dbg.names',
               'slide': 'dbg.slide', 'enemycoll': 'dbg.enemycoll',
               'collect': 'dbg.collect', 'enemies': 'dbg.enemies'}                                  # 0.20
# 0.15: the pass ids of the flat view (kRmPassNames in TruMenu.cpp), their mask, the ring switches without an argument
RM_PASSES = ('0x200', '0x100', '0x80', '0x400', '0x800', '1', '2')
RM_PASS_ALL = 0xf83
RM_RING_SWITCHES = ('dbg.flat', 'dbg.census', 'dbg.flatedges', 'dbg.flatmodels', 'dbg.flatanyrt', 'dbg.render')
DV_LAYER_COUNT = 17                          # 0.20: + collect, enemies
# 0.17 quick toggles: [Quick] keys / ranges, the buttons the open bar owns, [Shot] OnCine ranges, the new items, the row
# tables of the bar and the items a value row may use
QB_KEYS = ('Enabled', 'OpenButtons', 'ChordMs', 'ShowClosed', 'Language', 'Top', 'Scale')
QB_RANGES = {'ChordMs': (50, 1000), 'Top': (5, 80), 'Scale': (0.5, 3)}
QB_OWN = 0xC30F                              # D-pad / LB / RB (0.17) + X / Y (0.21.3)
OC_RANGES = {'OnCinePairs': (1, 50), 'OnCineFastPairs': (1, 50), 'OnCineIntervalMs': (250, 10000),
             'OnCineSlowMs': (250, 60000)}
QB_ITEMS = {'quick.open': 'bool', 'quick.lang': 'action', 'quick.status': 'info', 'shot.oncine': 'bool',
            'dbg.depthdump': 'action', 'dbg.cp': 'action', 'dbg.cpall': 'action', 'dbg.cplist': 'info',
            'dbg.cpgo': 'action', 'pos.save': 'action', 'pos.list': 'info', 'pos.go': 'action'}
QB_TABLES = ('kQbEmergency', 'kQbLara', 'kQbDebug', 'kQbLevel', 'kQbRender', 'kQbTimeTest', 'kQbChapters', 'kQbAccess',
             'kQbCoop',                                                          # 0.21 Koop (planned rows only)
             'kQbTests',                                                         # 0.21.1 Tests (teleports + specials)
             'kQbRenderMore',                                                    # 0.21.5 Render-Details (ring frozen)
             'kQbRescue')                                                        # 0.21.11 Rettung (soft-lock helpers)
QB_VALUE_ITEMS = ('dbg.depth', 'dbg.alpha', 'dbg.bright', 'dbg.enclosing', 'cheat.speed', 'dbg.flatpasses', 'quick.lang',
                  'time.scale', 'ai.mode',                                       # 0.19 ai.mode
                  'snd.pos', 'snd.lines', 'snd.sort',                            # 0.20.1 sound list
                  'cam.shakescale', 'cam.rumble',                                # 0.21 camera shake / rumble
                  'ai.spawncount', 'ai.spawnat',                                 # 0.21.1 enemy spawn
                  'snd.vol.ambience', 'snd.vol.steps', 'snd.vol.weapons',       # 0.21.8 sound group sliders
                  'snd.vol.enemies', 'snd.vol.lara', 'snd.vol.objects', 'snd.vol.dlc2', 'snd.vol.hud')
# 0.18: the new items, the 0 / 1 keys, the bar pages (QbPage rows of kQbPages: 10 pages, special ones without a table)
Q18_ITEMS = {'overlay.larain': 'bool', 'pos.goload': 'action', 'save.load': 'action'}
Q18_KEYS = (('Menu', 'OverlayLaraIn'), ('Debug', 'LegendLaraIn'), ('Saves', 'DirectLoad'), ('Shot', 'OnCineSegments'))
QB_PAGES_MAX = 17                            # 0.21: + Koop; 0.21.1: + Favoriten / Zuletzt, Tests; 0.21.5: + Render-Details, Fixes;
                                             # 0.21.6: + Kostueme (16); 0.21.11: + Rettung (= g_qbRow[17], the limit)
# 0.21.6 (2026-11-07): bar page Kostueme, flight key line ([Cheat] FlightHint), quick command line
Q216_COS_NAMES = ('Classic Lara', 'Blue Bikini', 'Black and White Bikini', 'Red Bikini', 'Camo Bikini', 'Casual Explorer',
                  'Grey Jungle Shorts', 'Legend Lara', 'Bright Blue Bikini', 'Gold Bikini', 'Red Drysuit',
                  'Fashion Winner', "People's Choice", 'Grey Jungle Shorts', 'Grey Jungle Shorts', 'Blue Wetsuit')
Q216_COS_ITEMS = ('costume.set', 'costume.next', 'costume.choosereload')   # the only items the page runs
Q216_SETTLE = (300, 1000)                   # kCosSettleMs: "about 0.5 s" (owner / coordinator spec)
Q216_TOGGLE_ITEMS = ('nav.draw', 'dbg.flatpass', 'dbg.show', 'ai.dumb')   # "<item> <one word>" flips a flag
Q216_EXEC = ('InvokeCore(', 'CmdExecute(', 'QueueItem(', 'InvokeItem(', 'QbRun(', 'RunPending(', 'ShortcutStart(')
# 0.19 dumb AI: the items, the presets (kAiPresets + "filter"), the [AI] keys
Q19_ITEMS = {'ai.dumb': 'action', 'ai.mode': 'action', 'ai.noinvestigate': 'bool', 'ai.noattack': 'bool',
             'ai.status': 'info'}
AI_PRESETS = ('all', 'sharks', 'spiders', 'thralls')
AI_SETTINGS = AI_PRESETS + ('filter',)
AI_KEYS = ('Dumb', 'DumbFilter', 'DumbMode', 'NoInvestigate', 'NoAttack')
# 0.20: the new items, the [Media] mute keys, the bar rows the owner asked for (table, item, arg), the ring entries once
Q20_ITEMS = {'dbg.collect': 'bool', 'dbg.enemies': 'bool', 'media.mutemusic': 'bool', 'media.muteambient': 'bool',
             'pos.portal': 'action'}
Q20_MEDIA_KEYS = ('MuteMusic', 'MuteAmbient')
Q20_BAR = (('kQbLevel', 'dbg.collect', ''), ('kQbRender', 'dbg.enemies', ''), ('kQbRender', 'cheat.enemyhealth', ''),
           ('kQbRender', 'dbg.flatedges', ''), ('kQbTimeTest', 'media.mutemusic', ''),
           ('kQbTimeTest', 'media.muteambient', ''), ('kQbEmergency', 'game.quit', ''))
Q20_RING = ('dbg.collect', 'dbg.enemies', 'media.mutemusic', 'media.muteambient')
Q20_DEFAULTS = (('AI', 'DumbMode', 'gate'), ('Debug', 'Depth', '2'), ('Debug', 'FlatPasses', '0x600'))
# 0.20.1: the sound list - items, [Sound] keys (key, rule), bar rows (table, item, kind), check tables
Q201_ITEMS = {'snd.list': 'bool', 'snd.pos': 'action', 'snd.lines': 'action', 'snd.refresh': 'action',
              'snd.sort': 'action', 'snd.scale': 'action', 'snd.playing': 'bool', 'snd.music': 'bool', 'snd.sfx': 'bool',
              'snd.speech': 'bool', 'snd.other': 'bool', 'snd.dump': 'action', 'snd.status': 'info'}
SND_POS = ('bl', 'tl', 'tr', 'br')
SND_SORT = ('group', 'volume', 'name')
Q201_KEYS = (('List', 'bool'), ('Position', SND_POS), ('MaxLines', (1, 40)), ('RefreshMs', (100, 10000)),
             ('Sort', SND_SORT), ('FontScale', (0.5, 3.0)), ('OnlyPlaying', 'bool'), ('ShowMusic', 'bool'),
             ('ShowSfx', 'bool'), ('ShowSpeech', 'bool'), ('ShowOther', 'bool'))
Q201_BAR = (('kQbDebug', 'snd.list', 'kQbBool'), ('kQbDebug', 'snd.pos', 'kQbValue'),
            ('kQbDebug', 'snd.lines', 'kQbValue'), ('kQbDebug', 'snd.sort', 'kQbValue'),
            ('kQbDebug', 'snd.playing', 'kQbBool'), ('kQbDebug', 'snd.music', 'kQbBool'),
            ('kQbDebug', 'snd.sfx', 'kQbBool'), ('kQbDebug', 'snd.speech', 'kQbBool'),
            ('kQbDebug', 'snd.other', 'kQbBool'), ('kQbDebug', 'snd.dump', 'kQbAction'),
            ('kQbTimeTest', 'snd.list', 'kQbBool'), ('kQbTimeTest', 'snd.dump', 'kQbAction'))
Q201_TABLES = ('kSnChecks', 'kSmChecks', 'kEsChecks')
DV_NAME_COLOURS = ('white', 'yellow', 'cyan', 'magenta', 'weiss', 'gelb')
# 0.21: Arachnophobie / camera / ai.remove - items, game-thread items, [Arachno] / [Camera] keys (key, rule), defaults,
# bar rows (table, item, kind, arg), check tables, the planned rows they replace, the Koop page
Q21_ITEMS = {'arachno.on': 'bool', 'arachno.hide': 'bool', 'arachno.picture': 'bool', 'arachno.mute': 'bool',
             'arachno.list': 'action', 'arachno.status': 'info', 'cam.shakescale': 'action', 'cam.rumble': 'action',
             'cam.shakelist': 'action', 'cam.shake': 'action', 'cam.shakestate': 'info', 'ai.remove': 'action'}
Q21_GAME_THREAD = ('arachno.list', 'cam.shakelist', 'cam.shake', 'ai.remove')
Q21_ARACHNO_KEYS = (('Enabled', 'bool'), ('Hide', 'bool'), ('Picture', 'bool'), ('Mute', 'bool'), ('Match', 'list'),
                    ('Exclude', 'list0'), ('Image', 'png'), ('Scale', (0.2, 5.0)), ('MinPx', (4, 256)),
                    ('MaxScreen', (0.1, 1.0)), ('FadeNear', (0, 2000)), ('MaxDist', (500, 50000)),
                    ('WobbleAmp', (0.0, 0.5)), ('WobbleHz', (0.0, 10.0)), ('SquashAmp', (0.0, 0.5)), ('TiltDeg', (0, 45)),
                    ('Flip', 'bool'))
Q21_CAMERA_KEYS = (('ShakeScale', (0, 100)), ('Rumble', (0, 100)))
Q21_DEFAULTS = (('Arachno', 'Enabled', '0'), ('Camera', 'ShakeScale', '100'), ('Camera', 'Rumble', '100'),
                ('Sound', 'Position', 'br'))
Q21_BAR = (('kQbAccess', 'arachno.on', 'kQbBool', ''), ('kQbAccess', 'arachno.hide', 'kQbBool', ''),
           ('kQbAccess', 'arachno.picture', 'kQbBool', ''), ('kQbAccess', 'arachno.mute', 'kQbBool', ''),
           ('kQbAccess', 'cam.shakescale', 'kQbValue', ''), ('kQbAccess', 'cam.rumble', 'kQbValue', ''),
           ('kQbRender', 'ai.remove', 'kQbAction', 'others'))
Q21_TABLES = ('kArDrawChecks', 'kArSoundChecks', 'kCsChecks', 'kRbChecks', 'kLfChecks', 'kAdChecks')
Q21_REPLACED = ('Arachnophobie', 'Kamera-Wackeln aus')
AD_ARGS = ('nearest', 'others', 'all')
# 0.21.1 (2026-11-07): ai.kill, sticky, room check, physics bodies, enemy spawn, bar groups / page 0 / Tests page
Q211_ITEMS = {'ai.kill': 'action', 'sticky.get': 'action', 'sticky.set': 'action', 'unit.go': 'action',
              'phys.status': 'info', 'phys.dump': 'action', 'ai.spawn': 'action', 'ai.spawncount': 'action',
              'ai.spawnat': 'action', 'dbg.hpbar': 'bool', 'menu.hidecursor': 'bool'}
Q211_GAME_THREAD = ('ai.kill', 'sticky.set', 'phys.dump', 'ai.spawn')
Q211_NOT_GAME_THREAD = ('unit.go', 'sticky.get')   # unit.go starts a shortcut (render side); get only reads
Q211_QUICK_KEYS = (('Closed', 'groups'), ('RecentMax', (0, 16)), ('Recent', 'recent'))
Q211_GROUPS = (('ki_dumm', 'ai.dumb'), ('ki_spawn', 'ai.spawn'), ('ki_weg', 'ai.kill'))   # key, an item inside
Q211_TABLES = ('kAkChecks', 'kStChecks', 'kRkChecks', 'kPhChecks', 'kSpChecks', 'kHpChecks')
Q211_SWITCHES = (('Debug', 'EnemyHpBar', '1'), ('Menu', 'HideCursor', '0'))   # 0 / 1 keys and their defaults
# bytes other plugins patch at run time - never a TruMenu byte check: TruShadowCombat 0.6 (damage entry, switch bound,
# table operand), TruTrace's call bytes
Q211_FOREIGN = [(0x637590, 5), (0x63761b, 1), (0x637625, 4), (0x5b6a2f, 2)]
Q211_KILL_TYPES = '{6, 4, 2, 1, 0}'          # 6 RigidBody = the game's own Kill (0x63831c) first
TRUTRACE_BYTES = (0x5b6a2f, 0x5b6a30)        # the call TruTrace checks - never a TruMenu patch site
# 0.21.3 (2026-11-07): the bar's X / Y footer texts (DE, EN) and the confirmation text
Q213_FOOTER = ('"X: ausfuehren  Y: Favorit"', '"X: run  Y: favourite"')
Q213_CONFIRM = ('"rechts / X nochmal (3 s) = ausfuehren"', '"right / X again (3 s) = run"')
# 0.21.4 (2026-11-07): hall02 counter (fix.hall02, thrall.scriptval, [Fix] Hall02Restore)
Q214_ITEMS = {'fix.hall02': ('action', 'true'), 'thrall.scriptval': ('action', 'false')}
Q214_DROPPED = ('Hall02Restore', 'fix.hall02restore', 'H2Tick', 'H2RestorePass')   # E3, not built (coordinator 17:30)
Q214_REPLY = ('Arena-Trigger 11268', 'Betreten / Verlassen', 'arena trigger 11268', 'enter / leave')
LIT =re.compile(r'"((?:[^"\\]|\\.)*)"')


def item_types(src):
    """{item id: type} from the kItems table of TruMenu.cpp"""
    block = src[src.index('const Item kItems[] = {'):]
    block = block[:block.index('\n};')]
    return dict(re.findall(r'\{"([a-z][a-z0-9_.]*)", "([a-z]+)"', block))


def check_shortcut(where, text, items):
    """problems of one shortcut column (empty list = fine)"""
    out = []
    if len(text) > 319: out.append('%s: shortcut longer than 319 characters' % where)
    parts = [p.strip() for p in text.split(';') if p.strip()]
    if parts and parts[0].startswith('#'): parts = parts[1:]
    if not parts: out.append('%s: shortcut without a command' % where)
    if len(parts) > 12: out.append('%s: shortcut with %d commands, at most 12' % (where, len(parts)))
    for p in parts:
        if p.startswith('#'):
            out.append('%s: title "%s" must be the first element' % (where, p))
            continue
        word, _, arg = p.partition(' ')
        arg = arg.strip()
        if word == 'game.quit': out.append('%s: game.quit is never run by a shortcut' % where)
        elif word not in items: out.append('%s: unknown item id %s' % (where, word))
        elif word == 'level.load' and not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', arg):
            out.append('%s: level.load needs one unit name, got "%s"' % (where, arg))
        elif items[word] == 'bool' and arg not in ('', '0', '1'):
            out.append('%s: %s is a bool item, arg "%s" (0 / 1)' % (where, word, arg))
    return out


def check_lists():
    """problems of tests/regress/*.txt (empty list = fine) and a summary per file"""
    problems, summary = [], []
    items = item_types(read_cpp())
    for name, doc in sorted(REGRESS.items()):
        path = os.path.join(ROOT, 'tests', 'regress', name)
        if not os.path.exists(path):
            problems.append('%s missing' % name)
            continue
        raw = open(path, 'rb').read()
        if any(b > 126 or (b < 32 and b not in (9, 10, 13)) for b in raw):
            problems.append('%s: non-ASCII bytes (the menu font has no umlauts)' % name)
        doc_text = open(os.path.join(ROOT, 'docs', doc), encoding='utf-8').read()
        doc_ids = set(re.findall(r'`([a-z0-9][a-z0-9-]+)`', doc_text))
        seen, steps, checks, shortcuts = set(), 0, 0, 0
        for n, line in enumerate(raw.decode('ascii', 'replace').splitlines(), 1):
            if not line or line.startswith('#'): continue
            f = line.split('\t')
            if len(f) not in (8, 9):
                problems.append('%s:%d: %d columns, want 8 (or 9 with a shortcut)' % (name, n, len(f)))
                continue
            if len(f) == 9:
                shortcuts += 1
                problems += check_shortcut('%s:%d' % (name, n), f[8], items)
            rid, state, hint, note, when, kind, target, num = f[:8]
            if rid in seen: problems.append('%s:%d: id %s twice' % (name, n, rid))
            seen.add(rid)
            if kind not in ('step', 'check'): problems.append('%s:%d: kind %s' % (name, n, kind))
            if state != 'open' or note or when: problems.append('%s:%d: state / note / time must be open / empty' % (name, n))
            if not hint or len(hint) > 239: problems.append('%s:%d: hint empty or longer than 239' % (name, n))
            if kind == 'step':
                steps += 1
                if rid != 'step%s' % num: problems.append('%s:%d: step id %s vs number %s' % (name, n, rid, num))
            else:
                checks += 1
                if target or num != '0': problems.append('%s:%d: a check has no target / number' % (name, n))
                if rid not in doc_ids: problems.append('%s:%d: check id %s not in docs/%s' % (name, n, rid, doc))
        summary.append('%s %d steps + %d checks, %d shortcuts' % (name, steps, checks, shortcuts))
    return problems, summary


def check_radial(path=RADIAL, name='TruMenu.radial.txt', marker='# TruMenu radial menu', items=None):
    """problems of a radial-format file (TruMenu.radial.txt, 0.10.1 also TruMenu.tour.txt; empty list = fine), a summary
    line and its levels {path: [entries]} (for the limits with the built-in entries)"""
    problems = []
    src = read_cpp()
    items = items or item_types(src)
    m = re.search(r'kRadForbidden\[\] = \{(.*?)\};', src, re.S)
    cpp_forbidden = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if sorted(cpp_forbidden) != sorted(RADIAL_FORBIDDEN):
        problems.append('kRadForbidden in TruMenu.cpp %s differs from this tool %s' % (cpp_forbidden, RADIAL_FORBIDDEN))
    if not os.path.exists(path):
        return problems + ['%s missing' % name], '', {'': []}
    raw = open(path, 'rb').read()
    if any(b > 126 or (b < 32 and b not in (9, 10, 13)) for b in raw):
        problems.append('%s: non-ASCII bytes (the menu font has no umlauts)' % name)
    lines = raw.decode('ascii', 'replace').splitlines()
    if not lines or not lines[0].startswith(marker):
        problems.append('%s: first line must start with "%s" (Set-TruMenu.ps1 marker)' % (name, marker))
    levels = {'': []}                        # path -> entries (folders + items) in order, as RadialLoad builds them
    seen, entries = set(), 0
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'): continue
        where = '%s:%d' % (name, n)
        f = line.split('|')
        if len(f) != 3:
            problems.append('%s: want "path | label | item id [arg]" (%d fields)' % (where, len(f)))
            continue
        path, label, cmd = (x.strip() for x in f)
        segs = [s.strip() for s in path.split('/') if s.strip()]
        word, _, arg = cmd.partition(' ')
        arg = arg.strip()
        if not label or len(label) > 47: problems.append('%s: label empty or longer than 47' % where)
        for s in segs:
            if len(s) > 47 or not re.fullmatch(r'[A-Za-z0-9 _().-]+', s):
                problems.append('%s: path segment "%s" (letters, digits, space _ ( ) . -; at most 47)' % (where, s))
        if len('/'.join(segs)) > 95: problems.append('%s: path longer than 95' % where)
        if word in RADIAL_FORBIDDEN:
            problems.append('%s: %s is never offered in the radial menu' % (where, word))
            continue
        if word not in items and not word.startswith('dev.'):
            problems.append('%s: unknown item id %s' % (where, word))
        elif items.get(word) == 'bool' and arg not in ('', '0', '1'):
            problems.append('%s: %s is a bool item, arg "%s" (0 / 1)' % (where, word, arg))
        elif items.get(word) == 'todo':
            problems.append('%s: %s is a todo item' % (where, word))
        if word in ('instance.spawn', 'weapon.give', 'level.load') and not re.fullmatch(r'[a-z0-9_-]{1,63}', arg):
            problems.append('%s: %s needs one name (a-z 0-9 _ -), got "%s"' % (where, word, arg))
        key = ('/'.join(segs).lower(), label.lower())
        if key in seen: problems.append('%s: label "%s" twice in "%s"' % (where, label, '/'.join(segs)))
        seen.add(key)
        full = ''
        for s in segs:                       # folders on the way (case-insensitive like RadLevelFor)
            child = (full + '/' + s) if full else s
            if not any(e == ('folder', child.lower()) for e in levels[full]):
                levels[full].append(('folder', child.lower()))
                levels.setdefault(child.lower(), [])
            full = child.lower()
        levels.setdefault(full, []).append(('item', label))
        entries += 1
    total = entries + sum(1 for v in levels.values() for e in v if e[0] == 'folder')
    if total > 256: problems.append('%s: %d entries incl. folders, TruMenu keeps 256' % (name, total))
    if len(levels) > 48: problems.append('%s: %d levels, TruMenu keeps 48' % (name, len(levels)))
    for p, v in levels.items():
        if len(v) > 64: problems.append('%s: level "%s" has %d entries, TruMenu keeps 64' % (name, p, len(v)))
    paged = ['%s (%d)' % (p or 'top', len(v)) for p, v in sorted(levels.items()) if len(v) > 8]
    summary = '%d entries in %d levels (top %d sectors)%s' % (entries, len(levels), len(levels['']),
                                                            ', pages: ' + ', '.join(paged) if paged else '')
    return problems, summary, levels


def check_builtins(rows, radial_levels, tour_levels):
    """0.10.1: the limits / top sectors with the built-in entries the table defaults give (Mode=menu: "Tests" with 4
    virtual folders + "Rundgang" (the tour levels below it) + 1 virtual slot, "Spiel beenden" last on the top level)"""
    d = {k: v for s, k, v, _ in rows if s == 'Radial'}
    menu = d.get('Mode') == 'menu'
    tests = menu and d.get('TestsLevel') == '1'
    quit_ = menu and d.get('QuitSector') == '1'
    top = len(radial_levels['']) + (1 if tests else 0) + (1 if quit_ else 0)
    entries = sum(len(v) for v in radial_levels.values())
    levels = len(radial_levels)
    if tests:                                # Tests folder, 4 virtual folders, Rundgang folder, the tour file
        entries += 1 + 4 + 1 + sum(len(v) for p, v in tour_levels.items())
        levels += 1 + 1 + 1 + sum(1 for p in tour_levels if p)
    if quit_: entries += 1
    problems = []
    if entries > 256: problems.append('built-ins: %d entries with Tests / Rundgang / quit sector, TruMenu keeps 256' % entries)
    if levels > 48: problems.append('built-ins: %d levels with Tests / Rundgang / the virtual slot, TruMenu keeps 48' % levels)
    pages = (top + 7) // 8
    return problems, 'top level %d sectors with the built-ins (%s%s), %d page(s); %d entries, %d levels' % (
        top, 'Tests' if tests else '', ' + Spiel beenden' if quit_ else '', pages, entries, levels)


def check_ini_values(ini_path):
    """0.10.1: the [Radial] values of the INI file that is checked (Mode / Freeze / QuitSector / TestsLevel)"""
    problems, section = [], None
    for n, line in enumerate(open(ini_path, encoding='utf-8').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if section != 'Radial' or not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if key in RADIAL_VALUES and value.lower() not in RADIAL_VALUES[key]:
            problems.append('%s:%d: [Radial] %s=%s (%s)' % (os.path.basename(ini_path), n, key, value,
                                                          ' / '.join(RADIAL_VALUES[key])))
    return problems


def check_shot(ini_path, radial_path):
    """0.10.5: the [Shot] values of the INI, the shot items / exports in TruMenu.cpp, the Claude level of the radial file"""
    problems, section, seen = [], None, set()
    name = os.path.basename(ini_path)
    for n, line in enumerate(open(ini_path, encoding='utf-8').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if section != 'Shot' or not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        seen.add(key)
        if key in SHOT_VALUES and value not in SHOT_VALUES[key]:
            problems.append('%s:%d: [Shot] %s=%s (%s)' % (name, n, key, value, ' / '.join(SHOT_VALUES[key])))
        elif key in ('Hotkey', 'MaxPerMinute'):
            try:
                v = int(value, 0)
            except ValueError:
                v = -1
            hi = 0xFE if key == 'Hotkey' else 120
            if not 0 <= v <= hi: problems.append('%s:%d: [Shot] %s=%s (0 .. %d)' % (name, n, key, value, hi))
        elif key == 'Folder' and re.search(r'[<>"|?*]', value):
            problems.append('%s:%d: [Shot] Folder=%s has a character Windows does not allow' % (name, n, value))
    for key in ('Enabled', 'Folder', 'Clean', 'Hotkey', 'MaxPerMinute'):
        if key not in seen: problems.append('%s: [Shot] %s missing' % (name, key))
    src = read_cpp()
    items = item_types(src)
    for item, typ in (('shot.save', 'action'), ('shot.status', 'info'), ('claude.mark', 'action')):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    for export in ('TruMenuShot', 'TruMenuMark'):
        if not re.search(r'__declspec\(dllexport\) int __cdecl %s\(const char \*' % export, src):
            problems.append('TruMenu.cpp: export %s(const char *) missing' % export)
    kinds, top, flow_ring = [], [], []
    if os.path.exists(radial_path):
        for line in open(radial_path, encoding='ascii', errors='replace').read().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            path, label, cmd = (x.strip() for x in line.split('|'))
            first = path.split('/')[0].strip()
            if first not in top: top.append(first)
            if first.lower() != 'claude': continue
            word, _, arg = cmd.partition(' ')
            if word in FLOW_RING and path.strip().lower() == 'claude' and not arg.strip():   # 0.11 Ablauf entries
                flow_ring.append(word)
                continue
            if word != 'claude.mark' or path.strip().lower() != 'claude':
                problems.append('radial: level Claude holds "%s | %s" (only claude.mark <kind> and the flow entries %s '
                                'directly in Claude)' % (path, cmd, ' / '.join(FLOW_RING)))
            else:
                kinds.append(arg.strip())
    if kinds != CLAUDE_KINDS:
        problems.append('radial: level Claude marks %s, want %s in this order' % (kinds, CLAUDE_KINDS))
    if len(set(flow_ring)) != len(flow_ring):
        problems.append('radial: level Claude holds a flow entry twice (%s)' % ', '.join(flow_ring))
    return problems, 'Claude marks %s, flow entries %s; file top levels %s' % (' '.join(kinds), ' '.join(flow_ring) or '-',
                                                                              ', '.join(top))


def check_flow(ini_path):
    """0.11: the [Flow] values of the INI, the flow items in kItems, the parser header included by TruMenu.cpp"""
    problems, section, seen = [], None, set()
    name = os.path.basename(ini_path)
    for n, line in enumerate(open(ini_path, encoding='utf-8').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if section != 'Flow' or not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        seen.add(key)
        if key in FLOW_VALUES and value not in FLOW_VALUES[key]:
            problems.append('%s:%d: [Flow] %s=%s (%s)' % (name, n, key, value, ' / '.join(FLOW_VALUES[key])))
        elif key in FLOW_RANGES:
            lo, hi = FLOW_RANGES[key]
            try:
                v = float(value) if key == 'Size' else int(value, 0)
            except ValueError:
                v = lo - 1
            if not lo <= v <= hi: problems.append('%s:%d: [Flow] %s=%s (%s .. %s)' % (name, n, key, value, lo, hi))
        elif key == 'File' and (not value or re.search(r'[<>"|?*]', value)):
            problems.append('%s:%d: [Flow] File=%s empty or with a character Windows does not allow' % (name, n, value))
    for key in ('Enabled', 'File', 'Overlay', 'Position', 'Size', 'Lines', 'AutoAdvance', 'ToastSeconds', 'PollMs'):
        if key not in seen: problems.append('%s: [Flow] %s missing' % (name, key))
    src = read_cpp()
    items = item_types(src)
    for item in FLOW_ITEMS:
        want = 'info' if item in ('flow.status', 'flow.list') else 'action'
        if items.get(item) != want: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, want))
    if '#include "TruFlowCore.h"' not in src: problems.append('TruMenu.cpp does not include TruFlowCore.h')
    return problems


def nav_switches(src):
    """0.12: the switch names of kNavSwitches in TruMenu.cpp (in table order)"""
    if 'const NavSwitch kNavSwitches[] = {' not in src: return []
    block = src[src.index('const NavSwitch kNavSwitches[] = {'):]
    block = block[:block.index('\n};')]
    return re.findall(r'\{"([a-z0-9_]+)", 0x', block)


def dv_layers(src):
    """0.14: the layer names of kDvLayers in TruMenu.cpp (in table order)"""
    if 'const DvLayerDef kDvLayers[kDvCount] = {' not in src: return []
    block = src[src.index('const DvLayerDef kDvLayers[kDvCount] = {'):]
    block = block[:block.index('\n};')]
    return re.findall(r'\{"([a-z]+)", "[A-Za-z]+", ', block)


def check_debug(ini_path, radial_path):
    """0.12: the [Debug] values of the INI, the nav items in kItems, the nav.* entries of the radial file; 0.13 the
    label keys / dbg.labels; 0.14 the debug view keys, items and ring entries"""
    problems, section, seen = [], None, set()
    name = os.path.basename(ini_path)
    src = read_cpp()
    switches = nav_switches(src)
    if not switches: problems.append('TruMenu.cpp: kNavSwitches missing or empty')
    layers = dv_layers(src)
    if len(layers) != DV_LAYER_COUNT:
        problems.append('TruMenu.cpp: kDvLayers has %d layers, want %d' % (len(layers), DV_LAYER_COUNT))
    for n, line in enumerate(open(ini_path, encoding='utf-8').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if section != 'Debug' or not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        seen.add(key)
        if key in ('Enabled', 'NavMask', 'Labels', 'LabelCross') and value not in ('0', '1'):
            problems.append('%s:%d: [Debug] %s=%s (0 / 1)' % (name, n, key, value))
        elif key in LABEL_RANGES:
            lo, hi = LABEL_RANGES[key]
            try:
                ok = lo <= float(value) <= hi and (key != 'LabelMax' or value.isdigit())
            except ValueError:
                ok = False
            if not ok: problems.append('%s:%d: [Debug] %s=%s (%g .. %g)' % (name, n, key, value, lo, hi))
        elif key == 'LabelMatch' and (not value or not re.match(r'^[A-Za-z0-9_*, ]+$', value)):
            problems.append('%s:%d: [Debug] LabelMatch=%s (comma list of name parts a-z 0-9 _ or *)' % (name, n, value))
        elif key in ('NavDraw', 'ViewNav'):
            for word in [w for w in re.split(r'[ ,]+', value) if w]:
                if word not in switches: problems.append('%s:%d: [Debug] %s names "%s" (not in kNavSwitches)'
                                                         % (name, n, key, word))
        elif key in DV_BOOL_KEYS and value not in ('0', '1'):        # 0.14
            problems.append('%s:%d: [Debug] %s=%s (0 / 1)' % (name, n, key, value))
        elif key in DV_RANGES:
            lo, hi = DV_RANGES[key]
            try:
                ok = lo <= float(value) <= hi and (key in DV_FLOAT_KEYS or re.fullmatch(r'-?\d+', value) is not None)
            except ValueError:
                ok = False
            if not ok: problems.append('%s:%d: [Debug] %s=%s (%g .. %g)' % (name, n, key, value, lo, hi))
        elif key == 'NameColour' and not re.fullmatch(r'[0-9A-Fa-f]{6}', value):
            problems.append('%s:%d: [Debug] NameColour=%s (RRGGBB)' % (name, n, value))
        elif key == 'NameMatch' and value and not re.match(r'^[A-Za-z0-9_*, ]+$', value):
            problems.append('%s:%d: [Debug] NameMatch=%s (comma list of name parts a-z 0-9 _ or *, may be empty)'
                            % (name, n, value))
        elif key == 'FlatPasses':                # 0.15: a mask of the pass ids, hex or decimal
            try:
                mask = int(value, 0)
                ok = mask > 0 and not (mask & ~RM_PASS_ALL)
            except ValueError:
                ok = False
            if not ok: problems.append('%s:%d: [Debug] FlatPasses=%s (a mask of 0x200 0x100 0x80 0x400 0x800 1 2, e.g. '
                                       '0x200)' % (name, n, value))
        elif key == 'FlatColour' and value not in ('material', 'class'):
            problems.append('%s:%d: [Debug] FlatColour=%s (material / class)' % (name, n, value))
        elif key == 'ViewSkip':                  # 0.16: layer names of kDvLayers, may be empty
            for word in [w for w in re.split(r'[ ,]+', value) if w]:
                if word not in layers: problems.append('%s:%d: [Debug] ViewSkip names "%s" (not in kDvLayers)'
                                                       % (name, n, word))
    for key in (('Enabled', 'NavDraw', 'NavMask', 'ViewNav', 'NameColour', 'NameMatch', 'FlatPasses', 'FlatColour',
                 'ViewSkip') + LABEL_KEYS + DV_BOOL_KEYS + tuple(sorted(DV_RANGES))):
        if key not in seen: problems.append('%s: [Debug] %s missing' % (name, key))
    items = item_types(src)
    for item, typ in sorted(NAV_ITEMS.items()) + sorted(LABEL_ITEMS.items()) + sorted(DV_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    entries, used, labels, flight = 0, set(), 0, 0
    dv_seen = {}                             # 0.14: layer / item -> count of ring entries
    if os.path.exists(radial_path):
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            path, label, cmd = (x.strip() for x in line.split('|'))
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            if word in LABEL_ITEMS:          # 0.13: dbg.labels, no argument (the ring flips it)
                labels += 1
                if arg: problems.append('%s:%d: %s takes no argument in the ring, got "%s"'
                                        % (os.path.basename(radial_path), n, word, arg))
                continue
            if word in DV_ITEMS:             # 0.14: dbg.show <layer>, the others no argument
                where = '%s:%d' % (os.path.basename(radial_path), n)
                if word == 'dbg.show':
                    if arg not in layers:
                        problems.append('%s: dbg.show needs one layer of kDvLayers, got "%s"' % (where, arg))
                    elif arg in DV_OWN_ITEM:
                        problems.append('%s: layer %s has its own item %s - use that' % (where, arg, DV_OWN_ITEM[arg]))
                    else:
                        dv_seen[arg] = dv_seen.get(arg, 0) + 1
                elif word == 'dbg.namefilter':
                    if not re.fullmatch(r'[A-Za-z0-9_*,]+', arg):
                        problems.append('%s: dbg.namefilter needs one list of name parts (a-z 0-9 _ , or *), got "%s"'
                                        % (where, arg))
                elif word == 'dbg.namecolour':
                    if arg not in DV_NAME_COLOURS and not re.fullmatch(r'[0-9A-Fa-f]{6}', arg):
                        problems.append('%s: dbg.namecolour needs a preset %s or RRGGBB, got "%s"'
                                        % (where, '/'.join(DV_NAME_COLOURS), arg))
                elif word == 'dbg.namesize':
                    try:
                        ok = 0.5 <= float(arg) <= 3.0
                    except ValueError:
                        ok = False
                    if not ok: problems.append('%s: dbg.namesize needs 0.5 .. 3, got "%s"' % (where, arg))
                elif word == 'dbg.flatpass':         # 0.15: one pass id, once each
                    if arg not in RM_PASSES:
                        problems.append('%s: dbg.flatpass needs one pass id of %s, got "%s"'
                                        % (where, ' '.join(RM_PASSES), arg))
                    else:
                        dv_seen[word + ' ' + arg] = dv_seen.get(word + ' ' + arg, 0) + 1
                elif word == 'dbg.flatcolour':       # 0.15: material / class, once each
                    if arg not in ('material', 'class'):
                        problems.append('%s: dbg.flatcolour needs material or class, got "%s"' % (where, arg))
                    else:
                        dv_seen[word + ' ' + arg] = dv_seen.get(word + ' ' + arg, 0) + 1
                elif word == 'dbg.flatpasses':       # 0.15: census / default / a mask
                    try:
                        ok = arg in ('census', 'default') or (int(arg, 0) > 0 and not (int(arg, 0) & ~RM_PASS_ALL))
                    except ValueError:
                        ok = False
                    if not ok: problems.append('%s: dbg.flatpasses needs census, default or a pass mask, got "%s"'
                                               % (where, arg))
                elif word in DP_RING_ARGS:           # 0.16: dbg.depth on / dim / off, dbg.enclosing normal / dim / hide
                    if arg not in DP_RING_ARGS[word]:
                        problems.append('%s: %s needs one of %s, got "%s"' % (where, word, ' / '.join(DP_RING_ARGS[word]),
                                                                              arg))
                    else:
                        dv_seen[word + ' ' + arg] = dv_seen.get(word + ' ' + arg, 0) + 1
                elif word in DP_RING_PERCENT:        # 0.16: dbg.alpha / dbg.bright presets
                    lo, hi = DP_RING_PERCENT[word]
                    if not (arg.isdigit() and lo <= int(arg) <= hi):
                        problems.append('%s: %s needs a percent %d .. %d, got "%s"' % (where, word, lo, hi, arg))
                elif arg:
                    problems.append('%s: %s takes no argument in the ring, got "%s"' % (where, word, arg))
                else:
                    dv_seen[word] = dv_seen.get(word, 0) + 1
                continue
            if word == 'cheat.flight':           # 0.16: the flight switch in the ring, once, no argument
                flight += 1
                if arg: problems.append('%s:%d: cheat.flight takes no argument in the ring, got "%s"'
                                        % (os.path.basename(radial_path), n, arg))
                continue
            if word == 'cheat.speed':            # 0.16: speed presets
                try:
                    ok = 0.0 < float(arg) < 1000.0
                except ValueError:
                    ok = False
                if not ok: problems.append('%s:%d: cheat.speed needs a number 0 .. 1000, got "%s"'
                                           % (os.path.basename(radial_path), n, arg))
                continue
            if not word.startswith('nav.'): continue
            entries += 1
            where = '%s:%d' % (os.path.basename(radial_path), n)
            if word == 'nav.draw':
                if arg not in switches:
                    problems.append('%s: nav.draw needs one switch of kNavSwitches, got "%s"' % (where, arg))
                else:
                    used.add(arg)
            elif arg:
                problems.append('%s: %s takes no argument in the ring, got "%s"' % (where, word, arg))
    if os.path.exists(radial_path) and labels != 1:
        problems.append('%s: dbg.labels must be in the radial file once, found %d' % (os.path.basename(radial_path), labels))
    if os.path.exists(radial_path):          # 0.14: every layer and every dbg.* switch item once
        want = [DV_OWN_ITEM.get(l, l) for l in layers] + ['dbg.view', 'dbg.triggers', 'dbg.status']
        want += list(RM_RING_SWITCHES) + ['dbg.flatpass ' + p for p in RM_PASSES] + \
            ['dbg.flatcolour material', 'dbg.flatcolour class']                     # 0.15 render mode
        want += list(DP_RING_SWITCHES) + ['%s %s' % (w, a) for w, args in sorted(DP_RING_ARGS.items()) for a in args]
        for w in want:
            if dv_seen.get(w, 0) != 1:
                problems.append('%s: debug view entry %s must be in the radial file once, found %d'
                                % (os.path.basename(radial_path), w, dv_seen.get(w, 0)))
        if flight != 1:                      # 0.16
            problems.append('%s: cheat.flight must be in the radial file once, found %d'
                            % (os.path.basename(radial_path), flight))
    return problems, ('%d switches in kNavSwitches, %d nav entries in the radial file (%d switches), %d dbg.labels entry, '
                      '%d debug view layers, %d debug view entries' % (len(switches), entries, len(used), labels,
                                                                       len(layers), sum(dv_seen.values())))


def ini_section(ini_path, wanted):
    """[(line number, key, value)] of one INI section"""
    out, section = [], None
    for n, line in enumerate(open(ini_path, encoding='utf-8').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if section != wanted or not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        out.append((n, key.strip(), value.strip()))
    return out


def qb_rows(src, with_tail=False):
    """0.17: the rows of the quick-toggle bar tables: [(table, de, id, arg, kind, layer)]; 0.18: id may be "-" (label /
    planned rows), the argument may be several adjacent string literals, with_tail adds the rest of the row (flags)"""
    rows = []
    for table in QB_TABLES:
        start = 'const QbRow %s[] = {' % table
        if start not in src: continue
        block = src[src.index(start):]
        block = block[:block.index('\n};')]
        for m in re.finditer(r'\{"([^"]*)", "([^"]*)", "([a-z][a-z0-9_.]*|-)", ((?:"[^"]*"\s*)+), (kQb[A-Za-z]+), '
                             r'(-1|kDv[A-Za-z]+),([^{}]*)\}', block, re.S):
            arg = ''.join(re.findall(r'"([^"]*)"', m.group(4)))
            row = (table, m.group(1), m.group(3), arg, m.group(5), m.group(6))
            rows.append(row + (m.group(7),) if with_tail else row)
    return rows


def check_quick(ini_path, radial_path):
    """0.17 (2026-11-06 TruMenu 0.17 quick toggles): the [Quick] values, [Shot] OnCine*, [Debug] CheckpointHide; the new
    items in kItems; the bar's rows (every item id in kItems, bool rows on bool items or dbg.show <layer>, value rows on
    the value items, every debug view layer reachable from the bar); the new ring entries"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    seen = set()
    for n, key, value in ini_section(ini_path, 'Quick'):
        seen.add(key)
        where = '%s:%d: [Quick] %s=%s' % (name, n, key, value)
        if key in ('Enabled', 'ShowClosed') and value not in ('0', '1'): problems.append(where + ' (0 / 1)')
        elif key == 'OpenButtons':
            try:
                v = int(value, 0)
            except ValueError:
                v = -1
            if not 1 <= v <= 0xFFFF: problems.append(where + ' (an XInput button mask 1 .. 0xFFFF)')
            elif v & QB_OWN: problems.append(where + ' (must not hold D-pad / LB / RB / X / Y = 0x%04X: the open bar '
                                             'owns them)' % QB_OWN)
        elif key in QB_RANGES:
            lo, hi = QB_RANGES[key]
            try:
                ok = lo <= float(value) <= hi and (key == 'Scale' or value.isdigit())
            except ValueError:
                ok = False
            if not ok: problems.append(where + ' (%g .. %g)' % (lo, hi))
        elif key == 'Language' and value not in ('de', 'en'): problems.append(where + ' (de / en)')
    for key in QB_KEYS:
        if key not in seen: problems.append('%s: [Quick] %s missing' % (name, key))
    seen = set()
    for n, key, value in ini_section(ini_path, 'Shot'):
        if not key.startswith('OnCine'): continue
        seen.add(key)
        where = '%s:%d: [Shot] %s=%s' % (name, n, key, value)
        if key == 'OnCine' and value not in ('0', '1'): problems.append(where + ' (0 / 1)')
        elif key == 'OnCineSignal' and value not in ('cine', 'camera', 'both'): problems.append(where + ' (cine / camera / both)')
        elif key in OC_RANGES:
            lo, hi = OC_RANGES[key]
            if not (value.isdigit() and lo <= int(value) <= hi): problems.append(where + ' (%d .. %d)' % (lo, hi))
    for key in ['OnCine', 'OnCineSignal'] + sorted(OC_RANGES):
        if key not in seen: problems.append('%s: [Shot] %s missing' % (name, key))
    hide = [v for n, k, v in ini_section(ini_path, 'Debug') if k == 'CheckpointHide']
    if len(hide) != 1: problems.append('%s: [Debug] CheckpointHide missing' % name)
    elif hide[0] and not all(w.isdigit() and int(w) < 65536 for w in re.split(r'[ ,]+', hide[0]) if w):
        problems.append('%s: [Debug] CheckpointHide=%s (comma list of intro ids 0 .. 65535, or empty)' % (name, hide[0]))
    items = item_types(src)
    for item, typ in sorted(QB_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    rows = qb_rows(src)
    if len(rows) < 20: problems.append('TruMenu.cpp: quick-toggle bar tables: only %d rows found' % len(rows))
    layers = dv_layers(src)
    reach = set()
    for table, de, item, arg, kind, layer in rows:
        where = 'TruMenu.cpp: %s row "%s" (%s %s)' % (table, de, item, arg)
        if kind in ('kQbLabel', 'kQbPlanned') or item == '-':   # 0.18: checked in check_018
            continue
        if item not in items: problems.append(where + ': item not in kItems')
        elif kind == 'kQbBool':
            if item == 'dbg.show':
                if arg not in layers: problems.append(where + ': dbg.show needs a layer of kDvLayers')
                reach.add(arg)
            elif item == 'ai.dumb':          # 0.19: "ai.dumb <preset>" (the bar adds 0 / 1)
                if arg not in AI_SETTINGS: problems.append(where + ': ai.dumb needs one of %s' % ' / '.join(AI_SETTINGS))
            elif item == 'nav.draw':         # 0.21.6: "nav.draw <switch>" (RadialOn: the switch byte)
                if arg not in nav_switches(src): problems.append(where + ': nav.draw needs a switch of kNavSwitches')
            elif item == 'dbg.flatpass':     # 0.21.6: "dbg.flatpass <pass>" (RadialOn: the pass bit)
                if arg not in RM_PASSES: problems.append(where + ': dbg.flatpass needs one of %s' % ' / '.join(RM_PASSES))
            elif items[item] != 'bool' or arg: problems.append(where + ': a bool row needs a bool item without argument')
        elif kind == 'kQbValue' and item not in QB_VALUE_ITEMS:
            problems.append(where + ': a value row needs one of %s' % ', '.join(QB_VALUE_ITEMS))
        elif kind == 'kQbAction' and items[item] != 'action' and not (item == 'player.health' and not arg):
            problems.append(where + ': an action row needs an action item (or player.health without argument)')
        elif kind == 'kQbInfo' and items[item] != 'info': problems.append(where + ': an info row needs an info item')
        elif kind == 'kQbChoice' and items[item] != 'action': problems.append(where + ': a choice row needs an action item')
        for lname, own in DV_OWN_ITEM.items():
            if item == own: reach.add(lname)
    for lname in layers:
        if lname not in reach: problems.append('TruMenu.cpp: layer %s is not reachable from the quick-toggle bar' % lname)
    counts = {}
    if os.path.exists(radial_path):
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            cmd = line.split('|')[2].strip()
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            where = '%s:%d: %s' % (os.path.basename(radial_path), n, cmd)
            if word in ('quick.open', 'shot.oncine', 'dbg.depthdump', 'dbg.cplist', 'pos.list'):
                counts[word] = counts.get(word, 0) + 1
                if arg: problems.append(where + ' (no argument in the ring)')
            elif word == 'dbg.cpall':
                counts['dbg.cpall ' + arg] = counts.get('dbg.cpall ' + arg, 0) + 1
                if arg not in ('0', '1'): problems.append(where + ' (0 / 1)')
            elif word == 'dbg.cpgo' and not (arg == 'active' or arg.isdigit()):
                problems.append(where + ' (active or an intro id)')
            elif word == 'pos.go' and not re.fullmatch(r'[A-Za-z0-9_-]+', arg):
                problems.append(where + ' (a saved name or last)')
            elif word == 'pos.save' and arg and not re.fullmatch(r'[A-Za-z0-9_-]+', arg):
                problems.append(where + ' (no argument or a name a-z 0-9 _ -)')
        for want in ('quick.open', 'shot.oncine', 'dbg.depthdump', 'dbg.cplist', 'dbg.cpall 0', 'dbg.cpall 1'):
            if counts.get(want, 0) != 1:
                problems.append('%s: %s must be in the radial file once, found %d'
                                % (os.path.basename(radial_path), want, counts.get(want, 0)))
    return problems, '%d bar rows in %d tables (every one of %d layers reachable), %d new items, [Quick] %d keys' % (
        len(rows), len({r[0] for r in rows}), len(layers), len(QB_ITEMS), len(QB_KEYS))


def check_018(ini_path, radial_path):
    """0.18 (2026-11-06 TruMenu 0.18): the 0 / 1 keys, the new items, kQbPages (at most QB_PAGES_MAX pages, every table
    on a page), label / planned rows, confirm / backup flags only on action rows, level.load rows with one unit name, the
    ring's overlay.larain (once, no argument), pos.goload (a name or last), time.scale (a number 0 .. 10)"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    for section, key in Q18_KEYS:
        found = [(n, v) for n, k, v in ini_section(ini_path, section) if k == key]
        if len(found) != 1: problems.append('%s: [%s] %s missing' % (name, section, key))
        elif found[0][1] not in ('0', '1'):
            problems.append('%s:%d: [%s] %s=%s (0 / 1)' % (name, found[0][0], section, key, found[0][1]))
    items = item_types(src)
    for item, typ in sorted(Q18_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    block = src[src.index('const QbPage kQbPages[] = {'):]
    block = block[:block.index('\n};')]
    pages = re.findall(r'QB_PAGE\("([^"]*)", "([^"]*)", (kQb[A-Za-z]+), (kQs[A-Za-z]+)\)', block)
    special = re.findall(r'\{"([^"]*)", "([^"]*)", nullptr, 0, (kQs[A-Za-z]+)\}', block)
    if len(pages) + len(special) > QB_PAGES_MAX:
        problems.append('TruMenu.cpp: kQbPages has %d pages (at most %d)' % (len(pages) + len(special), QB_PAGES_MAX))
    on_page = {p[2] for p in pages}
    for table in QB_TABLES:
        if table not in on_page: problems.append('TruMenu.cpp: row table %s is on no page of kQbPages' % table)
    planned = labels = confirm = 0
    for table, de, item, arg, kind, layer, tail in qb_rows(src, True):
        where = 'TruMenu.cpp: %s row "%s" (%s %s)' % (table, de, item, arg)
        flags = 'kQfConfirm' in tail or 'kQfBackup' in tail
        if (item == '-') != (kind in ('kQbLabel', 'kQbPlanned', 'kQbGroup')):   # 0.21.1 kQbGroup
            problems.append(where + ': id "-" exactly on label / planned / group rows')
        if kind == 'kQbPlanned':
            planned += 1
            if arg.count('|') != 1 or not all(arg.split('|')): problems.append(where + ': planned text "German|English"')
        if kind == 'kQbLabel': labels += 1
        if flags:
            confirm += 1
            if kind != 'kQbAction' and not (kind == 'kQbChoice' and 'kQfBackup' not in tail):   # 0.21.1 spawn
                problems.append(where + ': kQfConfirm / kQfBackup only on action rows (kQfConfirm also on choice rows)')
        if item == 'level.load' and not re.fullmatch(r'[a-z0-9_]+', arg):
            problems.append(where + ': level.load takes one unit name a-z 0-9 _')
        if item == 'level.load' and 'kQfConfirm' not in tail: problems.append(where + ': level.load rows need kQfConfirm')
        if not re.fullmatch(r'[\x20-\x7e]*', de + arg): problems.append(where + ': ASCII only')
    counts = {}
    if os.path.exists(radial_path):
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            cmd = line.split('|')[2].strip()
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            where = '%s:%d: %s' % (os.path.basename(radial_path), n, cmd)
            if word == 'overlay.larain':
                counts[word] = counts.get(word, 0) + 1
                if arg: problems.append(where + ' (no argument in the ring)')
            elif word == 'pos.goload' and not re.fullmatch(r'[A-Za-z0-9_-]+', arg):
                problems.append(where + ' (a saved name or last)')
            elif word == 'time.scale':
                try:
                    ok = 0.0 <= float(arg) <= 10.0
                except ValueError:
                    ok = False
                if not ok: problems.append(where + ' (a number 0 .. 10)')
        if counts.get('overlay.larain', 0) != 1:
            problems.append('%s: overlay.larain must be in the radial file once, found %d'
                            % (os.path.basename(radial_path), counts.get('overlay.larain', 0)))
    return problems, '%d pages (%d special), %d label + %d planned rows, %d confirm rows, %d new items, %d keys' % (
        len(pages) + len(special), len(special), labels, planned, confirm, len(Q18_ITEMS), len(Q18_KEYS))


def check_019(ini_path, radial_path, rows):
    """0.19 (2026-11-06 TruMenu 0.19 dumb AI): the [AI] keys, every INI comment < 512 characters, the ai.* items, the
    presets of kAiPresets, the bar's ai.dumb rows (presets) and Barrierefreiheit page, the ring's ai.* entries, the 0.19
    precheck tables (present, at most 64 bytes a check - HexBytesAt's buffer)"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    found = {}
    for n, key, value in ini_section(ini_path, 'AI'):
        found[key] = (n, value)
    for key in AI_KEYS:
        if key not in found:
            problems.append('%s: [AI] %s missing' % (name, key))
            continue
        n, value = found[key]
        where = '%s:%d: [AI] %s=%s' % (name, n, key, value)
        if key == 'Dumb' and value not in ('0', '1', '2'): problems.append(where + ' (0 / 1 / 2)')
        elif key == 'DumbFilter' and value and not re.fullmatch(r'[A-Za-z0-9_]+( *, *[A-Za-z0-9_]+)*', value):
            problems.append(where + ' (comma list of name parts a-z 0-9 _, or empty)')
        elif key == 'DumbMode' and value not in ('purge', 'gate'): problems.append(where + ' (purge / gate)')
        elif key in ('NoInvestigate', 'NoAttack') and value not in ('0', '1'): problems.append(where + ' (0 / 1)')
    for sec, key, default, comment in rows:
        if len(comment) >= 512:
            problems.append('TruMenu.cpp: kOpts [%s] %s comment has %d characters (DefaultIniText keeps 511)'
                            % (sec, key, len(comment)))
    items = item_types(src)
    for item, typ in sorted(Q19_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    m = re.search(r'const AiPreset kAiPresets\[\] = \{(.*?)\};', src, re.S)
    cpp_presets = tuple(re.findall(r'\{"([a-z]+)", "', m.group(1))) if m else ()
    if cpp_presets != AI_PRESETS:
        problems.append('TruMenu.cpp: kAiPresets %s differs from this tool %s' % (cpp_presets, AI_PRESETS))
    for table in ('kAiChecks', 'kAiGateChecks', 'kAiBitChecks'):
        m = re.search(r'const DvCheck %s\[\] = \{(.*?)\n\};' % table, src, re.S)
        if not m:
            problems.append('TruMenu.cpp: %s missing' % table)
            continue
        for a, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', m.group(1)):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: %s %s "%s" (whole bytes, at most 64)' % (table, a, h))
    bar_ai = {}
    access = []
    for table, de, item, arg, kind, layer, tail in qb_rows(src, True):
        if item == 'ai.dumb':
            if kind != 'kQbBool': problems.append('TruMenu.cpp: %s row "%s": ai.dumb rows are bool rows' % (table, de))
            bar_ai[arg] = bar_ai.get(arg, 0) + 1
        if item == 'ai.mode' and kind != 'kQbValue':
            problems.append('TruMenu.cpp: %s row "%s": ai.mode is a value row' % (table, de))
        if table == 'kQbAccess': access.append((de, item, arg, kind))
    for want in AI_SETTINGS:
        if not bar_ai.get(want): problems.append('TruMenu.cpp: no bar row ai.dumb %s' % want)
    if any(de == 'Haie' and kind == 'kQbPlanned' for de, item, arg, kind in access):
        problems.append('TruMenu.cpp: kQbAccess still has the planned row "Haie" (0.19: ai.dumb sharks)')
    for want in ('sharks', 'spiders'):
        if not any(item == 'ai.dumb' and arg == want for de, item, arg, kind in access):
            problems.append('TruMenu.cpp: kQbAccess has no row ai.dumb %s' % want)
    counts, access_ring = {}, set()
    if os.path.exists(radial_path):
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            path, label, cmd = (x.strip() for x in line.split('|'))
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            where = '%s:%d: %s' % (os.path.basename(radial_path), n, cmd)
            if word == 'ai.dumb':
                if arg not in AI_SETTINGS:
                    problems.append(where + ' (exactly one of %s - the ring adds 0 / 1)' % ' / '.join(AI_SETTINGS))
                counts[word + ' ' + arg] = counts.get(word + ' ' + arg, 0) + 1
                if path.lower() == 'spieler/barrierefreiheit': access_ring.add(arg)
            elif word in ('ai.noinvestigate', 'ai.noattack', 'ai.status'):
                counts[word] = counts.get(word, 0) + 1
                if arg: problems.append(where + ' (no argument in the ring)')
            elif word == 'ai.mode' and arg not in ('purge', 'gate'):
                problems.append(where + ' (purge / gate)')
        for want in ('ai.noinvestigate', 'ai.noattack', 'ai.status'):
            if counts.get(want, 0) != 1:
                problems.append('%s: %s must be in the radial file once, found %d'
                                % (os.path.basename(radial_path), want, counts.get(want, 0)))
        for want in ('all', 'sharks', 'spiders'):
            if not counts.get('ai.dumb ' + want):
                problems.append('%s: ai.dumb %s missing in the radial file' % (os.path.basename(radial_path), want))
        for want in ('sharks', 'spiders'):
            if want not in access_ring:
                problems.append('%s: Spieler/Barrierefreiheit has no ai.dumb %s' % (os.path.basename(radial_path), want))
    return problems, '%d [AI] keys, %d items, presets %s, %d bar ai.dumb rows, %d ring ai.* entries' % (
        len(AI_KEYS), len(Q19_ITEMS), '/'.join(cpp_presets), sum(bar_ai.values()), sum(counts.values()))


def check_020(ini_path, radial_path, rows):
    """0.20 (2026-11-06 TruMenu 0.20): the [Media] mute keys 0 / 1, the new defaults (DumbMode gate, Depth 2, FlatPasses
    0x600) in kOpts, the new items in kItems, the bar rows the owner asked for (collectibles on Leveldaten, enemies /
    enemy health / edges on Render / KI, the mutes on Zeit / Test, game.quit as the LAST row of Notfall), the ring entries
    once without an argument, the 0.20 precheck tables present with at most 64 bytes a check"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    found = {k: (n, v) for n, k, v in ini_section(ini_path, 'Media')}
    for key in Q20_MEDIA_KEYS:
        if key not in found: problems.append('%s: [Media] %s missing' % (name, key))
        elif found[key][1] not in ('0', '1'):
            problems.append('%s:%d: [Media] %s=%s (0 / 1)' % (name, found[key][0], key, found[key][1]))
    defaults = {(sec, key): default for sec, key, default, comment in rows}
    for sec, key, want in Q20_DEFAULTS:
        if defaults.get((sec, key)) != want:
            problems.append('TruMenu.cpp: kOpts [%s] %s default "%s", want "%s" (0.20)' % (sec, key, defaults.get((sec, key)),
                                                                                       want))
    items = item_types(src)
    for item, typ in sorted(Q20_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    bar = qb_rows(src, True)
    for table, item, arg in Q20_BAR:
        if not any(t == table and i == item and a == arg for t, de, i, a, kind, layer, tail in bar):
            problems.append('TruMenu.cpp: %s has no row %s%s' % (table, item, ' ' + arg if arg else ''))
    emergency = [r for r in bar if r[0] == 'kQbEmergency']
    if emergency and emergency[-1][2] != 'game.quit':
        problems.append('TruMenu.cpp: kQbEmergency - game.quit must be the last row (got %s)' % emergency[-1][2])
    for t, de, i, a, kind, layer, tail in bar:
        if i == 'game.quit' and ('kQfConfirm' in tail or kind != 'kQbAction'):
            problems.append('TruMenu.cpp: %s row "%s": game.quit is a plain action row (the item arms itself, 10 s)'
                            % (t, de))
    counts = {}
    if os.path.exists(radial_path):
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            cmd = line.split('|')[2].strip()
            word, _, arg = cmd.partition(' ')
            if word in Q20_RING or word == 'pos.portal':
                counts[word] = counts.get(word, 0) + 1
                if arg.strip(): problems.append('%s:%d: %s (no argument in the ring)' % (os.path.basename(radial_path), n,
                                                                                         cmd))
        for want in Q20_RING:
            if counts.get(want, 0) != 1:
                problems.append('%s: %s must be in the radial file once, found %d'
                                % (os.path.basename(radial_path), want, counts.get(want, 0)))
        if counts.get('pos.portal'):
            problems.append('%s: pos.portal is a pos.goload step, not a ring entry' % os.path.basename(radial_path))
    for tbl in ('kCoChecks', 'kAiForgetChecks', 'kSndMusicChecks'):
        m = re.search(r'const DvCheck %s\[\] = \{(.*?)\n\};' % tbl, src, re.S)
        if not m:
            problems.append('TruMenu.cpp: %s missing' % tbl)
            continue
        body = re.sub(r'"\s*\n\s*"', '', m.group(1))           # a literal split over two lines is one literal
        for a, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', body):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: %s %s (whole bytes, at most 64; got %d)' % (tbl, a, len(hexs) // 2))
    return problems, '%d items, [Media] %d keys, %d bar rows, %d ring entries, defaults %s' % (
        len(Q20_ITEMS), len(Q20_MEDIA_KEYS), len(Q20_BAR), sum(counts.get(w, 0) for w in Q20_RING),
        ', '.join('%s %s' % (k, v) for s, k, v in Q20_DEFAULTS))


def snd_value_ok(rule, v):
    if rule == 'bool': return v in ('0', '1')
    if isinstance(rule[0], str): return v.lower() in rule
    try:
        x = float(v)
    except ValueError:
        return False
    return rule[0] <= x <= rule[1] and (isinstance(rule[0], float) or v.isdigit())


def check_0201(ini_path, radial_path):
    """0.20.1 (2026-11-06 sound list): [Sound] values, [Debug] EnemyStateLog, the snd.* items (snd.dump on the game
    thread), the bar rows, the ring entries and their arguments, the precheck tables, the mute order in SndMuteTick"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    found = {k: (n, v) for n, k, v in ini_section(ini_path, 'Sound')}
    for key, rule in Q201_KEYS:
        if key not in found:
            problems.append('%s: [Sound] %s missing' % (name, key))
        elif not snd_value_ok(rule, found[key][1]):
            problems.append('%s:%d: [Sound] %s=%s (%s)' % (name, found[key][0], key, found[key][1],
                                                           '0 / 1' if rule == 'bool' else ' .. '.join(map(str, rule))
                                                           if not isinstance(rule[0], str) else ' / '.join(rule)))
    dbg = {k: (n, v) for n, k, v in ini_section(ini_path, 'Debug')}
    if 'EnemyStateLog' not in dbg: problems.append('%s: [Debug] EnemyStateLog missing' % name)
    elif dbg['EnemyStateLog'][1] not in ('0', '1'):
        problems.append('%s:%d: [Debug] EnemyStateLog=%s (0 / 1)' % (name, dbg['EnemyStateLog'][0],
                                                                     dbg['EnemyStateLog'][1]))
    items = item_types(src)
    for item, typ in sorted(Q201_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    m = re.search(r'\{"snd\.dump", "action", (?:"[^"]*"\s*)+, (true|false),', src)
    if not m or m.group(1) != 'true':
        problems.append('TruMenu.cpp: snd.dump must run on the game thread (gameThread true)')
    bar = qb_rows(src)
    for table, item, kind in Q201_BAR:
        if not any(t == table and i == item and k == kind and not a for t, de, i, a, k, layer in bar):
            problems.append('TruMenu.cpp: %s has no %s row %s' % (table, kind, item))
    counts, levels = {}, {}
    if os.path.exists(radial_path):
        rname = os.path.basename(radial_path)
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            path, _, cmd = [p.strip() for p in line.split('|')]
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            if not word.startswith('snd.'): continue
            key = word + (' ' + arg if arg else '')
            counts[key] = counts.get(key, 0) + 1
            levels.setdefault(word, set()).add(path)
            where = '%s:%d: %s' % (rname, n, cmd)
            if word not in Q201_ITEMS: problems.append(where + ' (unknown snd.* item)')
            elif word == 'snd.pos' and arg not in SND_POS: problems.append(where + ' (bl / tl / tr / br)')
            elif word == 'snd.sort' and arg not in SND_SORT: problems.append(where + ' (group / volume / name)')
            elif word == 'snd.lines' and not (arg.isdigit() and 1 <= int(arg) <= 40): problems.append(where + ' (1 .. 40)')
            elif word == 'snd.refresh' and not (arg.isdigit() and 100 <= int(arg) <= 10000):
                problems.append(where + ' (100 .. 10000)')
            elif word == 'snd.scale' and not snd_value_ok((0.5, 3.0), arg): problems.append(where + ' (0.5 .. 3)')
            elif (Q201_ITEMS[word] in ('bool', 'info') or word == 'snd.dump') and arg:
                problems.append(where + ' (no argument)')
        for pos in SND_POS:
            if counts.get('snd.pos ' + pos, 0) != 1:
                problems.append('%s: snd.pos %s must be in the ring once, found %d'
                                % (rname, pos, counts.get('snd.pos ' + pos, 0)))
        for want in ('Zeit', 'Spieler/Debug/Ton'):
            if want not in levels.get('snd.list', set()):
                problems.append('%s: snd.list missing in level %s' % (rname, want))
        if counts.get('snd.dump', 0) != 1:
            problems.append('%s: snd.dump must be in the ring once, found %d' % (rname, counts.get('snd.dump', 0)))
    for tbl in Q201_TABLES:
        mt = re.search(r'const DvCheck %s\[\] = \{(.*?)\n\};' % tbl, src, re.S)
        if not mt:
            problems.append('TruMenu.cpp: %s missing' % tbl)
            continue
        body = re.sub(r'"\s*\n\s*"', '', mt.group(1))
        for a, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', body):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: %s %s (whole bytes, at most 64; got %d)' % (tbl, a, len(hexs) // 2))
    ms = re.search(r'\nvoid SndMuteTick\(\) \{(.*?)\n\}', src, re.S)
    body = ms.group(1) if ms else ''
    if 'SmMuteOn()' not in body or not (0 <= body.find('g_smOk') < body.find('g_sndOk')):
        problems.append('TruMenu.cpp: SndMuteTick must try the FMOD group mute (g_smOk / SmMuteOn) before the 0.20 path')
    return problems, '%d items, [Sound] %d keys + [Debug] EnemyStateLog, %d bar rows, %d ring snd.* entries, tables %s' % (
        len(Q201_ITEMS), len(Q201_KEYS), len(Q201_BAR), sum(counts.values()), ' / '.join(Q201_TABLES))


def q21_value_ok(rule, v):
    if rule == 'bool': return v in ('0', '1')
    if rule == 'list': return bool(re.fullmatch(r'[A-Za-z0-9_]+( *, *[A-Za-z0-9_]+)*', v))
    if rule == 'list0': return not v or bool(re.fullmatch(r'[A-Za-z0-9_]+( *, *[A-Za-z0-9_]+)*', v))
    if rule == 'png': return bool(v) and v.lower().endswith('.png') and not re.search(r'[<>"|?*]', v)
    try:
        x = float(v)
    except ValueError:
        return False
    return rule[0] <= x <= rule[1] and (isinstance(rule[0], float) or v.isdigit())


def check_021(ini_path, radial_path, rows):
    """0.21 (2026-11-07 Arachnophobie / camera / labels / ai.remove): [Arachno] / [Camera] values, the new defaults
    (Enabled 0, ShakeScale / Rumble 100, Sound Position br), the items (types, game thread), the bar rows (the planned
    rows Arachnophobie / Kamera-Wackeln aus replaced, ai.remove with a confirmation, the Koop page with planned rows only,
    right after Barrierefreiheit), the ring entries of these items (arguments), the precheck tables (at most 64 bytes),
    the slot-7 hook's mask order (set -1, the game's draw, the game's value back), no patch site on TruTrace's call bytes,
    and the owner-picture rules (.gitignore, Set-TruMenu.ps1, tools/pending_upload_scan.py)"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    for section, keys in (('Arachno', Q21_ARACHNO_KEYS), ('Camera', Q21_CAMERA_KEYS)):
        found = {k: (n, v) for n, k, v in ini_section(ini_path, section)}
        for key, rule in keys:
            if key not in found:
                problems.append('%s: [%s] %s missing' % (name, section, key))
            elif not q21_value_ok(rule, found[key][1]):
                problems.append('%s:%d: [%s] %s=%s (%s)' % (name, found[key][0], section, key, found[key][1],
                                                            rule if isinstance(rule, str) else
                                                            ' .. '.join(map(str, rule))))
    defaults = {(sec, key): default for sec, key, default, comment in rows}
    for sec, key, want in Q21_DEFAULTS:
        if defaults.get((sec, key)) != want:
            problems.append('TruMenu.cpp: kOpts [%s] %s default "%s", want "%s" (0.21)' % (sec, key, defaults.get((sec, key)),
                                                                                       want))
    items = item_types(src)
    for item, typ in sorted(Q21_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    for item in Q21_GAME_THREAD:
        m = re.search(r'\{"%s", "action", (?:"[^"]*"\s*)+, (true|false),' % re.escape(item), src)
        if not m or m.group(1) != 'true':
            problems.append('TruMenu.cpp: %s must run on the game thread (gameThread true)' % item)
    bar = qb_rows(src, True)
    for table, item, kind, arg in Q21_BAR:
        if not any(t == table and i == item and k == kind and a == arg for t, de, i, a, k, layer, tail in bar):
            problems.append('TruMenu.cpp: %s has no %s row %s%s' % (table, kind, item, ' ' + arg if arg else ''))
    for t, de, i, a, k, layer, tail in bar:
        where = 'TruMenu.cpp: %s row "%s"' % (t, de)
        if t == 'kQbAccess' and k == 'kQbPlanned' and de in Q21_REPLACED:
            problems.append(where + ': still planned (0.21 built it)')
        if i == 'ai.remove':
            if a not in AD_ARGS: problems.append(where + ': ai.remove needs nearest / others / all')
            if k != 'kQbAction' or 'kQfConfirm' not in tail: problems.append(where + ': ai.remove = action row with kQfConfirm')
        if t == 'kQbCoop' and k not in ('kQbLabel', 'kQbPlanned'):
            problems.append(where + ': the Koop page has planned rows only (no function yet)')
    if not any(t == 'kQbCoop' and k == 'kQbPlanned' for t, de, i, a, k, layer, tail in bar):
        problems.append('TruMenu.cpp: kQbCoop has no planned row')
    pages = re.findall(r'QB_PAGE\("([^"]*)", "([^"]*)", (kQb[A-Za-z]+), (kQs[A-Za-z]+)\)', src)
    tables = [p[2] for p in pages]
    if 'kQbCoop' not in tables: problems.append('TruMenu.cpp: kQbPages has no page Koop (kQbCoop)')
    elif 'kQbAccess' in tables and tables.index('kQbCoop') != tables.index('kQbAccess') + 1:
        problems.append('TruMenu.cpp: page Koop must follow Barrierefreiheit')
    counts = {}
    if os.path.exists(radial_path):
        rname = os.path.basename(radial_path)
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            cmd = line.split('|')[2].strip()
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            if word not in Q21_ITEMS: continue
            counts[word] = counts.get(word, 0) + 1
            where = '%s:%d: %s' % (rname, n, cmd)
            if word in ('cam.shakescale', 'cam.rumble') and not (arg.isdigit() and int(arg) <= 100):
                problems.append(where + ' (0 .. 100)')
            elif word == 'ai.remove' and arg not in AD_ARGS and not arg.isdigit():
                problems.append(where + ' (nearest / others / all / an intro id)')
            elif word == 'cam.shake' and not arg.isdigit(): problems.append(where + ' (a shake number)')
            elif Q21_ITEMS[word] in ('bool', 'info') and arg: problems.append(where + ' (no argument)')
    for tbl in Q21_TABLES:
        mt = re.search(r'const DvCheck %s\[\] = \{(.*?)\n\};' % tbl, src, re.S)
        if not mt:
            problems.append('TruMenu.cpp: %s missing' % tbl)
            continue
        body = re.sub(r'"\s*\n\s*"', '', mt.group(1))
        for a, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', body):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: %s %s (whole bytes, at most 64; got %d)' % (tbl, a, len(hexs) // 2))
    mh = re.search(r'\nvoid __fastcall ArDrawHook\(.*?\n\}', src, re.S)
    body = mh.group(0) if mh else ''
    i_set = body.find('AiPutDword(inst + 0x23c, 0xffffffffu)')
    i_draw = body.find('game(self, edx, a, b)', i_set if i_set >= 0 else 0)
    i_back = body.find('AiPutDword(inst + 0x23c, m23c)')
    if not (0 <= i_set < i_draw < i_back):
        problems.append('TruMenu.cpp: ArDrawHook must set +0x23c = -1, call the game\'s draw, then put the game\'s value back')
    mp = re.search(r'AiPatch g_arSndPatches\[\d+\] = \{(.*?)\n\};', src, re.S)
    sites = [int(x, 16) for x in re.findall(r'\{(0x[0-9a-fA-F]+),', mp.group(1))] if mp else []
    if len(sites) != 7: problems.append('TruMenu.cpp: g_arSndPatches must have the 6 call sites + the table word (got %d)'
                                        % len(sites))
    for s in sites:
        if s in TRUTRACE_BYTES: problems.append('TruMenu.cpp: sound gate patches 0x%x - TruTrace checks those bytes' % s)
    gi = os.path.join(ROOT, '.gitignore')
    gtext = open(gi, encoding='utf-8', errors='replace').read() if os.path.exists(gi) else ''
    for want in ('TruMenu.arachno*.png', 'work/arachno_owner/'):
        if want not in gtext.split('\n') and want + '\r' not in gtext.split('\n'):
            problems.append('.gitignore: line %s missing (owner picture)' % want)
    st = os.path.join(ROOT, 'scripts', 'windows', 'Set-TruMenu.ps1')
    stext = open(st, encoding='utf-8-sig', errors='replace').read() if os.path.exists(st) else ''
    for line in stext.split('\n'):
        if re.search(r'\b(Copy-Item|Remove-Item)\b', line) and 'Assert-NotOwnerImage' not in line:
            problems.append('Set-TruMenu.ps1: "%s" without Assert-NotOwnerImage (owner picture rule)' % line.strip()[:80])
    if "$ownerImagePattern = 'TruMenu.arachno*.png'" not in stext:
        problems.append('Set-TruMenu.ps1: $ownerImagePattern = \'TruMenu.arachno*.png\' missing')
    us = os.path.join(ROOT, 'tools', 'pending_upload_scan.py')
    utext = open(us, encoding='utf-8', errors='replace').read() if os.path.exists(us) else ''
    if 'arachno_owner' not in utext or r'\.arachno' not in utext:
        problems.append('tools/pending_upload_scan.py: the Owner rule (*.arachno*.png, work/arachno_owner/) missing')
    return problems, ('%d items, [Arachno] %d + [Camera] %d keys, %d bar rows, Koop page, %d ring entries, tables %s, '
                      'owner-picture rules' % (len(Q21_ITEMS), len(Q21_ARACHNO_KEYS), len(Q21_CAMERA_KEYS), len(Q21_BAR),
                                               sum(counts.values()), ' / '.join(Q21_TABLES)))


def check_0211(ini_path, radial_path, rows):
    """0.21.1 (2026-11-07 ai.kill / sticky / room check / physics / spawn / bar): the items (types, threads), [Quick]
    Closed / RecentMax / Recent, the bar (page 0 Favoriten / Zuletzt = kQsFav, page Tests = kQbTests + kQsTests after
    Zeit / Test, the three KI groups on Render / KI with their keys unique and an item inside, ai.kill rows with a
    confirmation and nearest / others / all, the hall02 repair rows), the ring entries of the new items, the precheck
    tables (whole bytes, at most 64, none on a byte another plugin patches), the kill path (types in order, the pick
    before the call, the game's own kill), sticky.set never creates an entry, player.goto takes the room check, the pot
    rule (placed intros only from drawn instances), the thrall-fight Prepare takes unit.go"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    items = item_types(src)
    for item, typ in sorted(Q211_ITEMS.items()):
        if items.get(item) != typ: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
    for item in Q211_GAME_THREAD + Q211_NOT_GAME_THREAD:
        m = re.search(r'\{"%s", "(?:action|info)", (?:"[^"]*"\s*)+,\s*(true|false),' % re.escape(item), src)
        want = 'true' if item in Q211_GAME_THREAD else 'false'
        if not m or m.group(1) != want:
            problems.append('TruMenu.cpp: %s must %srun on the game thread (gameThread %s)'
                            % (item, '' if want == 'true' else 'not ', want))
    found = {k: (n, v) for n, k, v in ini_section(ini_path, 'Quick')}
    for key, rule in Q211_QUICK_KEYS:
        if key not in found:
            problems.append('%s: [Quick] %s missing' % (name, key))
            continue
        n, v = found[key]
        if rule == 'groups': ok = not v or bool(re.fullmatch(r'[a-z0-9_]+(,[a-z0-9_]+)*', v))
        elif rule == 'recent': ok = not v or all(re.fullmatch(r'[a-z][a-z0-9_.]*( [^;]+)?', e) for e in v.split(';'))
        else: ok = v.isdigit() and rule[0] <= int(v) <= rule[1]
        if not ok: problems.append('%s:%d: [Quick] %s=%s (%s)' % (name, n, key, v, rule))
    defaults = {(sec, key): default for sec, key, default, comment in rows}
    for sec, key, want in Q211_SWITCHES:
        fs = {k: (n, v) for n, k, v in ini_section(ini_path, sec)}
        if key not in fs: problems.append('%s: [%s] %s missing' % (name, sec, key))
        elif fs[key][1] not in ('0', '1'): problems.append('%s:%d: [%s] %s=%s (0 / 1)' % (name, fs[key][0], sec, key, fs[key][1]))
    for sec, key, want in (('Quick', 'Closed', ''), ('Quick', 'RecentMax', '8'), ('Quick', 'Recent', '')) + Q211_SWITCHES:
        if defaults.get((sec, key)) != want:
            problems.append('TruMenu.cpp: kOpts [%s] %s default "%s", want "%s" (0.21.1)' % (sec, key, defaults.get((sec, key)),
                                                                                         want))
    block = src[src.index('const QbPage kQbPages[] = {'):]
    block = block[:block.index('\n};')]
    order = re.findall(r'(?:QB_PAGE\("([^"]*)", "[^"]*", (kQb[A-Za-z]+), (kQs[A-Za-z]+)\)|\{"([^"]*)", "[^"]*", nullptr, 0, '
                       r'(kQs[A-Za-z]+)\})', block)
    pages = [(a or d, b or None, c or e) for a, b, c, d, e in order]
    if not pages or pages[0][2] != 'kQsFav': problems.append('TruMenu.cpp: page 0 must be Favoriten / Zuletzt (kQsFav)')
    tables = [p[1] for p in pages]
    if 'kQbTests' not in tables: problems.append('TruMenu.cpp: kQbPages has no page Tests (kQbTests)')
    elif pages[tables.index('kQbTests')][2] != 'kQsTests': problems.append('TruMenu.cpp: page Tests needs kQsTests')
    elif 'kQbTimeTest' in tables and tables.index('kQbTests') != tables.index('kQbTimeTest') + 1:
        problems.append('TruMenu.cpp: page Tests must follow Zeit / Test')
    ms = re.search(r'const int kQbStartPage = (\d+);', src)
    if not ms or int(ms.group(1)) >= len(pages) or pages[int(ms.group(1))][1] != 'kQbLevel':
        problems.append('TruMenu.cpp: kQbStartPage must point at Leveldaten (kQbLevel)')
    bar = qb_rows(src, True)
    keys = {}
    group = None
    inside = {}
    for t, de, i, a, k, layer, tail in bar:
        where = 'TruMenu.cpp: %s row "%s"' % (t, de)
        if k == 'kQbGroup':
            if not re.fullmatch(r'[a-z0-9_]+', a): problems.append(where + ': a group needs a key a-z 0-9 _ (arg)')
            if a in keys: problems.append(where + ': group key %s twice (also %s)' % (a, keys[a]))
            keys[a] = de
            group = a
            inside[a] = []
            continue
        if k == 'kQbLabel': group = None
        elif group: inside[group].append(i)
        if i == 'ai.kill':
            if a not in AD_ARGS: problems.append(where + ': ai.kill needs nearest / others / all')
            if k != 'kQbAction' or 'kQfConfirm' not in tail: problems.append(where + ': ai.kill = action row with kQfConfirm')
        if i == 'sticky.set' and (k != 'kQbAction' or 'kQfConfirm' not in tail or not re.fullmatch(r'\d+ \d+ -?\d+', a)):
            problems.append(where + ': sticky.set = action row "<owner> <key> <value>" with kQfConfirm')
        if i == 'ai.spawn' and (k != 'kQbChoice' or 'kQfConfirm' not in tail or 'kQvSpawnKind' not in tail):
            problems.append(where + ': ai.spawn = choice row (kQvSpawnKind) with kQfConfirm')
    for key, item in Q211_GROUPS:
        if key not in keys: problems.append('TruMenu.cpp: group %s missing (KI page)' % key)
        elif item not in inside.get(key, []): problems.append('TruMenu.cpp: group %s has no %s row' % (key, item))
    renders = [k for k in keys if any(t == 'kQbRender' and kk == 'kQbGroup' and a == k for t, de, i, a, kk, layer, tail in bar)]
    if len(renders) != 3: problems.append('TruMenu.cpp: Render / KI needs the three KI groups (got %d)' % len(renders))
    for want in ('11270 17287 0', '11270 18509 2'):
        if not any(i == 'sticky.set' and a == want for t, de, i, a, k, layer, tail in bar):
            problems.append('TruMenu.cpp: no bar row sticky.set %s (hall02 repair)' % want)
    if not any(i == 'phys.status' and k == 'kQbInfo' and 'kQcPhys' in layer + tail for t, de, i, a, k, layer, tail in bar):
        problems.append('TruMenu.cpp: no info row phys.status with the count kQcPhys')
    counts = {}
    if os.path.exists(radial_path):
        rname = os.path.basename(radial_path)
        for n, line in enumerate(open(radial_path, encoding='ascii', errors='replace').read().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#') or line.count('|') != 2: continue
            cmd = line.split('|')[2].strip()
            word, _, arg = cmd.partition(' ')
            arg = arg.strip()
            if word not in Q211_ITEMS: continue
            counts[word] = counts.get(word, 0) + 1
            where = '%s:%d: %s' % (rname, n, cmd)
            if word == 'ai.kill' and arg not in AD_ARGS and not arg.isdigit():
                problems.append(where + ' (nearest / others / all / an intro id)')
            elif word == 'sticky.set' and not re.fullmatch(r'((int|bool|float) )?(\d:)?\w+ \d+ \S+', arg):
                problems.append(where + ' ([type] <owner> <key> <value>)')
            elif word == 'unit.go' and not re.fullmatch(r'[A-Za-z0-9_]+', arg): problems.append(where + ' (one unit name)')
            elif Q211_ITEMS[word] == 'info' and arg: problems.append(where + ' (no argument)')
    for tbl in Q211_TABLES:
        mt = re.search(r'const DvCheck %s\[\] = \{(.*?)\n\};' % tbl, src, re.S)
        if not mt:
            problems.append('TruMenu.cpp: %s missing' % tbl)
            continue
        body = re.sub(r'"\s*\n\s*"', '', mt.group(1))
        for a, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', body):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: %s %s (whole bytes, at most 64; got %d)' % (tbl, a, len(hexs) // 2))
            lo, hi = int(a, 16), int(a, 16) + len(hexs) // 2
            for f, size in Q211_FOREIGN:
                if lo < f + size and f < hi:
                    problems.append('TruMenu.cpp: %s %s covers 0x%x - another plugin patches it' % (tbl, a, f))
    if Q211_KILL_TYPES not in src: problems.append('TruMenu.cpp: kAkTypes must be %s (the game\'s own type first)' % Q211_KILL_TYPES)
    mk = re.search(r'\nbool RunAkKill\([^;{]*\) \{.*?\n\}', src, re.S)
    body = mk.group(0) if mk else ''
    i_pick, i_call = body.find('AkPick('), body.find('AkKillOne(')
    if not (0 <= i_pick < i_call): problems.append('TruMenu.cpp: RunAkKill must pick the kill path (AkPick) before AkKillOne')
    if 'kAkKill = 0x006376e0' not in src: problems.append('TruMenu.cpp: ai.kill must call the game\'s Kill 0x6376e0')
    ma = re.search(r'\nconst char \*AkPick\([^;{]*\) \{.*?\n\}', src, re.S)
    pick = ma.group(0) if ma else ''
    for need in ('0x800', 'fc & 2', 'AkDying', 'AkCaseOf(t) != 0', '0x2c60 + 0x1c', 'kAkRegen'):
        if need not in pick: problems.append('TruMenu.cpp: AkPick lacks the rule "%s"' % need)
    mset = re.search(r'\nbool RunStickySet\([^;{]*\) \{.*?\n\}', src, re.S)
    sbody = mset.group(0) if mset else ''
    if '0x4aee30' in sbody or '0x4b16a0' in sbody or 'StFind(' not in sbody:
        problems.append('TruMenu.cpp: sticky.set must find the entry itself (StFind) and never call Find / create 0x4aee30 / '
                        '0x4b16a0')
    mf = re.search(r'\nint StFind\([^;{]*\) \{.*?\n\}', src, re.S)
    if not mf or re.search(r'WriteDword|AiPutDword|volatile|\(\*reinterpret_cast', mf.group(0)):
        problems.append('TruMenu.cpp: StFind must only read (ReadDword / ReadWord / ReadByte)')
    mg = re.search(r'\nbool RunGoto\([^;{]*\) \{.*?\n\}', src, re.S)
    gbody = mg.group(0) if mg else ''
    i_rk, i_set = gbody.find('RkCheck('), gbody.find('SetPosition(')
    if not (0 <= i_rk < i_set) or 'force' not in gbody:
        problems.append('TruMenu.cpp: player.goto must run the room check (RkCheck, "force") before SetPosition')
    mm = re.search(r'\nvoid M20Draw\([^;{]*\) \{.*?\n\}', src, re.S)
    mbody = mm.group(0) if mm else ''
    i_nd = mbody.find('if (LfNotDrawn(inst)) {      // 0.21: picked up')
    i_reg = mbody.find('placedIntro[placedN] = intro;')
    i_else = mbody.find('} else {', i_nd)
    if not (0 <= i_nd < i_else < i_reg): problems.append('TruMenu.cpp: M20Draw must register placed intros only for drawn '
                                                         'instances (0.21.1 pot rule)')
    reg = os.path.join(ROOT, 'tests', 'regress', 'dlc2.txt')
    rtext = open(reg, encoding='ascii', errors='replace').read() if os.path.exists(reg) else ''
    if '#Thrall fight: hall02 + god mode;unit.go dlc_yggdrasil_hall02;' not in rtext:
        problems.append('tests/regress/dlc2.txt: the thrall-fight Prepare must take unit.go dlc_yggdrasil_hall02')
    return problems, ('%d items, [Quick] %d keys, pages 0 / Tests, %d groups, %d ring entries, tables %s, kill path, sticky, '
                      'room check, pot rule, Prepare' % (len(Q211_ITEMS), len(Q211_QUICK_KEYS), len(keys),
                                                        sum(counts.values()), ' / '.join(Q211_TABLES)))


def fn_body(src, head):
    """the text of a top-level function (head = the start of its line, e.g. 'void QuickTick('), '' when missing"""
    m = re.search(r'\n' + re.escape(head) + r'[^;{]*\) \{.*?\n\}', src, re.S)
    return m.group(0) if m else ''


def check_0213(ini_path):
    """0.21.3 (2026-11-07 quick bar X / Y, sound list width): see the module text"""
    problems = []
    src = read_cpp()
    m = re.search(r'const WORD kQbOwn = (0x[0-9A-Fa-f]+);', src)
    if not m or int(m.group(1), 16) != QB_OWN:
        problems.append('TruMenu.cpp: kQbOwn must be 0x%04X (D-pad / LB / RB + X / Y), got %s' % (QB_OWN, m.group(1) if m
                                                                                                     else 'none'))
    if not re.search(r'const WORD kQbX = 0x4000, kQbY = 0x8000;', src):
        problems.append('TruMenu.cpp: kQbX / kQbY must be 0x4000 / 0x8000 (XINPUT_GAMEPAD_X / _Y)')
    tick = fn_body(src, 'void QuickTick(')
    i_y, i_x, i_d = tick.find('if (edges & kQbY)'), tick.find('if (edges & kQbX)'), tick.find('QbAct(g_qbPage')
    if not (0 <= i_y < i_x < i_d):
        problems.append('TruMenu.cpp: QuickTick must take Y (QbFavPin) before X (QbExecRow) before left / right (QbAct)')
    else:
        yb, xb = tick[i_y:i_x], tick[i_x:i_d]
        if 'QbFavPin(' not in yb or 'return;' not in yb:
            problems.append('TruMenu.cpp: QuickTick: Y must call QbFavPin and return (no other press in that frame)')
        if 'QbExecRow(' not in xb or 'return;' not in xb or 'QbSpecialAct(p.special, row - g_qbStaticN, ' not in xb:
            problems.append('TruMenu.cpp: QuickTick: X must call QbExecRow (special rows: QbSpecialAct dir 1) and return')
    if 'pad.wButtons & kQbOwn' not in tick:
        problems.append('TruMenu.cpp: QuickTick must read the open bar\'s buttons as pad.wButtons & kQbOwn')
    ex = fn_body(src, 'void QbExecRow(')
    mv = re.search(r'case kQbValue:(.*?)return;', ex, re.S)
    if not ex: problems.append('TruMenu.cpp: QbExecRow missing')
    else:
        if not mv or 'QbActRow' in mv.group(1) or 'QbRun' in mv.group(1):
            problems.append('TruMenu.cpp: QbExecRow: X on a value row must do nothing (no QbActRow / QbRun)')
        mb = re.search(r'case kQbBool:(.*?)return;', ex, re.S)
        if not mb or 'QbRowOn(r)' not in mb.group(1) or '? -1 : 1' not in mb.group(1):
            problems.append('TruMenu.cpp: QbExecRow: X on a bool row must toggle from QbRowOn (on -> -1, off -> +1)')
        if 'default: QbActRow(page, r, 1);' not in ex:
            problems.append('TruMenu.cpp: QbExecRow: action / choice / info / planned rows = the right press '
                            '(QbActRow(page, r, 1)) - keeps the confirmation rows')
        if 'QbRun(' in ex or 'InvokeCore(' in ex or 'QbConfirm(' in ex:
            problems.append('TruMenu.cpp: QbExecRow must not run items itself (only through QbActRow)')
    fav = fn_body(src, 'void QbFavPin(')
    # 0.21.8: rows with an argument are pinnable ("<id>|<argument>"); the argument passes FavArgOk before FavSetArg
    # (0.21.3: refused before FavSet)
    i_arg, i_set = fav.find('if (!FavArgOk(r->arg))'), fav.find('FavSetArg(r->id, r->arg')
    if not (0 <= i_arg < i_set):
        problems.append('TruMenu.cpp: QbFavPin must check the argument (FavArgOk) before FavSetArg ([Favorites] Ids)')
    if fav and ('WritePrivateProfileString' in fav or 'g_favs' in fav or 'FavHasArg(r->id, r->arg)' not in fav):
        problems.append('TruMenu.cpp: QbFavPin must toggle through FavHasArg / FavSetArg only (no own write of the '
                        'favourites)')
    draw = fn_body(src, 'void DrawQuick(')
    for t in Q213_FOOTER:
        if t not in draw: problems.append('TruMenu.cpp: DrawQuick lacks the footer text %s' % t)
    conf = fn_body(src, 'bool QbConfirm(')
    for t in Q213_CONFIRM:
        if t not in conf: problems.append('TruMenu.cpp: QbConfirm lacks %s (X arms / confirms as right)' % t)
    pb = fn_body(src, 'extern "C" __declspec(dllexport) DWORD __cdecl TruMenuPadBlock(')
    for need in ('if (bar) out |= kQbOwn;', 'out |= static_cast<DWORD>(g_qbPad[pad].owned | g_qbPad[pad].gated);',
                 'out &= 0xFFFF;', 'out |= 1u << 16;', 'out |= 1u << 17;', 'out |= 1u << 18;'):
        if need not in pb: problems.append('TruMenu.cpp: TruMenuPadBlock changed its meaning (missing "%s")' % need)
    opts = {(s, k): c for s, k, d, c in table(src)[1]}
    if 'X = run' not in opts.get(('Quick', 'Enabled'), '') or 'X and Y are kept' not in opts.get(('Quick', 'Enabled'), ''):
        problems.append('TruMenu.cpp: kOpts [Quick] Enabled comment must name X / Y (run, favourite, kept from the game)')
    if 'X or Y' not in opts.get(('Quick', 'OpenButtons'), ''):
        problems.append('TruMenu.cpp: kOpts [Quick] OpenButtons comment must forbid X / Y')
    sr = fn_body(src, 'void SnRow(')
    if not sr or 'float edge' not in sr or 'GetContentRegionAvail' in sr:
        problems.append('TruMenu.cpp: SnRow must align to the frame\'s widest row (edge), not the window\'s content width')
    sd = fn_body(src, 'void DrawSoundList(')
    i_meas, i_row = sd.find('CalcTextSize(g_snRowBuf[i].text)'), sd.find('SnRow(')
    if not (0 <= i_meas < i_row):
        problems.append('TruMenu.cpp: DrawSoundList must measure every row (CalcTextSize) before it draws one (SnRow)')
    if 'ImGuiWindowFlags_AlwaysAutoResize' not in sd:
        problems.append('TruMenu.cpp: DrawSoundList: the box must stay AlwaysAutoResize')
    return problems, 'kQbOwn 0x%04X, Y > X > left / right, X / Y rules, footer + confirm texts, TruMenuPadBlock, sound ' \
                     'list width' % QB_OWN


def check_0214(ini_path, rows):
    """0.21.4 (2026-11-07 hall02 counter): see the module text"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    for item, (typ, thread) in sorted(Q214_ITEMS.items()):
        m = re.search(r'\{"%s", "%s", (?:"[^"]*"\s*)+,\s*(true|false),' % (re.escape(item), typ), src)
        if not m: problems.append('TruMenu.cpp: item %s (%s) missing in kItems' % (item, typ))
        elif m.group(1) != thread:
            problems.append('TruMenu.cpp: %s gameThread must be %s' % (item, thread))
    m = re.search(r'\{"fix\.hall02", "action", ((?:"[^"]*"\s*)+),', src)
    if not m or 'already holds tutorial' not in ''.join(re.findall(r'"([^"]*)"', m.group(1))).replace('  ', ' '):
        problems.append('TruMenu.cpp: the fix.hall02 help text must say it is for saves whose checkpoint 11258 already '
                        'holds tutorial thralls')
    # E3 was dropped (docs/Befund-Hall02-TU-Vergleich-0711.md: PC data bug, the Xbox never restores thralls there)
    ini_text = open(ini_path, encoding='utf-8', errors='replace').read()
    for word in Q214_DROPPED:
        if word in src: problems.append('TruMenu.cpp: %s present - the E3 safety net must not be built' % word)
        if word in ini_text: problems.append('%s: %s present - the E3 safety net must not be built' % (name, word))
    if any(sec == 'Fix' for sec, key, default, comment in rows):
        problems.append('TruMenu.cpp: kOpts has a [Fix] section (E3 dropped)')
    tests = [r for r in qb_rows(src, True) if r[0] == 'kQbTests']
    want = {'fix.hall02': ('kQbAction', True), 'thrall.scriptval': ('kQbAction', False)}
    for item, (kind, confirm) in want.items():
        hit = [r for r in tests if r[2] == item]
        if not hit: problems.append('TruMenu.cpp: page Tests has no %s row' % item)
        elif hit[0][4] != kind or hit[0][3] or (confirm and 'kQfConfirm' not in hit[0][6]):
            problems.append('TruMenu.cpp: page Tests row %s must be %s without argument%s' % (
                item, kind, ' with kQfConfirm (right / X twice)' if confirm else ''))
    fx = fn_body(src, 'bool RunFixHall02(')
    marks = [fx.find(s) for s in ('_stricmp(unit, kH2Unit)', 'if (!hp || !ht || !hb)', 'if (broken)', 'if (alive)',
                                  'RunStickySet(')]
    if not fx or -1 in marks or marks != sorted(marks):
        problems.append('TruMenu.cpp: RunFixHall02 must refuse in this order before the first sticky.set: wrong unit, '
                        'missing dispatcher values, broken, a living thrall (got %s)' % marks)
    i_tut, i_pop = fx.find('RunStickySet("int 11270 18509 2"'), fx.find('RunStickySet("int 11270 17287 0"')
    if not (0 <= i_tut < i_pop): problems.append('TruMenu.cpp: RunFixHall02 sets tutorial (18509) before population (17287)')
    if 'if (tut < 2)' not in fx: problems.append('TruMenu.cpp: RunFixHall02 sets tutorial 2 only when it is below 2')
    if fx.count('RunStickySet(') != 2 or re.search(r'WriteDword|volatile|kStNotify', fx):
        problems.append('TruMenu.cpp: RunFixHall02 writes only through two sticky.set calls')
    for t in Q214_REPLY:
        if t not in fx: problems.append('TruMenu.cpp: the fix.hall02 reply lacks "%s"' % t)
    al = fn_body(src, 'bool H2Alive(')
    for need in ('0x44', 'flags & 0x20', 'AkDying(brain', 'flags & 0x800'):
        if need not in al: problems.append('TruMenu.cpp: H2Alive lacks the rule "%s"' % need)
    mn = re.search(r'const char \*const kAkDeathNames\[4\] = \{([^}]*)\}', src)
    if not mn or 'Regenerate' in mn.group(1):
        problems.append('TruMenu.cpp: kAkDeathNames must be the four count-event states (RegenerateDeath = alive)')
    va = fn_body(src, 'DWORD H2ValueAddr(')
    i60, ic, i8 = va.find('inst + kH2ScriptRef'), va.find('ref + kH2ScriptData'), va.find('data + kH2ThrallInt')
    if not (0 <= i60 < ic < i8) or '!ref' not in va or '!data' not in va:
        problems.append('TruMenu.cpp: H2ValueAddr must be [[inst+0x60]+0xc]+8 with zero pointers refused')
    for const, val in (('kH2ScriptRef', '0x60'), ('kH2ScriptData', '0xc'), ('kH2ThrallInt', '8'),
                       ('kH2RuntimeIntro', '0x40000000'), ('kH2ThrallObject', '1004')):
        if not re.search(r'\b%s = %s\b' % (const, val), src): problems.append('TruMenu.cpp: %s must be %s' % (const, val))
    sc = fn_body(src, 'bool H2IsThrall(')
    if 'kH2ThrallObject' not in sc or 'kH2ThrallName' not in sc:
        problems.append('TruMenu.cpp: H2IsThrall must match object 1004 by id and name')
    for fn in ('bool RunThrallScript(', 'void ValThrallScript(', 'int H2Scan(', 'DWORD H2ValueAddr(', 'bool H2Alive('):
        b = fn_body(src, fn)
        if not b or re.search(r'RunStickySet|kStNotify|WriteDword|volatile|values\[', b):
            problems.append('TruMenu.cpp: %s) must only read' % fn.strip('('))
    a, b = src.find('// ---- 0.21.4 hall02 counter'), src.find('// ---- end of 0.21.4')
    sec = src[a:b] if 0 <= a < b else ''
    if not sec: problems.append('TruMenu.cpp: section "0.21.4 hall02 counter" .. "end of 0.21.4" missing')
    elif re.search(r'WriteDword|VirtualProtect|WriteProcessMemory|volatile [A-Z]+ \*>?\(?[a-z.]*\)? *=|'
                   r'\*reinterpret_cast<volatile', sec):
        problems.append('TruMenu.cpp: section 0.21.4 must not patch code or store directly (only sticky.set writes)')
    mt = re.search(r'const DvCheck kH2Checks\[\] = \{(.*?)\n\};', src, re.S)
    if not mt: problems.append('TruMenu.cpp: kH2Checks missing')
    else:
        body = re.sub(r'"\s*\n\s*"', '', mt.group(1))
        for ad, h in re.findall(r'\{(0x[0-9a-fA-F]+), "([0-9a-fA-F ]+)"\}', body):
            hexs = h.replace(' ', '')
            if len(hexs) % 2 or len(hexs) // 2 > 64:
                problems.append('TruMenu.cpp: kH2Checks %s (whole bytes, at most 64)' % ad)
            lo, hi = int(ad, 16), int(ad, 16) + len(hexs) // 2
            for f, size in Q211_FOREIGN:
                if lo < f + size and f < hi: problems.append('TruMenu.cpp: kH2Checks %s covers 0x%x (another plugin)' % (ad, f))
    if 'M214Check();' not in src: problems.append('TruMenu.cpp: M214Check is never called')
    return problems, '2 items, page Tests rows, fix.hall02 help / guards / order / 18509 rule / reply, alive rule, +8 ' \
                     'address, read-only scriptval, no E3 safety net, kH2Checks'


SWITCHES = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.switches.txt')
PLUGINS = os.path.join(ROOT, 'src', 'asi')
# 0.21.5 (2026-11-07 TruMenu 0.21.5 Fixes): the plugins of the switches file (never TruGuard); text keys are no switches
SW_PLUGINS = ('TruShadowPower', 'TruShadowCombat', 'TruShadowHud', 'TruRockVein', 'TruDoppelganger', 'TruDlc2Player',
              'TruMercLang', 'TruTrace', 'TruQoL')   # 2026-11-08 (17y): + the player plugin TruQoL 0.1.1
SW_TEXT_KEYS = {('TruMercLang', 'MercLang', 'PathFilter'), ('TruTrace', 'Trace', 'SpawnFilter'),
                ('TruTrace', 'Trace', 'ProgressFilter')}
# the run-time re-read of every live key: (plugin, section, key) -> function head in the plugin source whose body holds
# the section and key literals (read from the plugin sources 2026-11-07; everything else is read once in DllMain)
SW_LIVE = {
    ('TruShadowCombat', 'Damage', 'Translate'): 'void DamageReadSwitch(',
    ('TruShadowCombat', 'Chunk', 'Translate'): 'void ChunkReadSwitch(',
    ('TruShadowCombat', 'Splash', 'Translate'): 'void SplashReadSwitch(',
    ('TruShadowCombat', 'Death', 'TranslateNotify33'): 'void DeathReadSwitch(',
    # 0.6.5 (P1d): P1dReadSwitches loops over the key table kP1dKeys (once per second)
    ('TruShadowCombat', 'Companion', 'Translate'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Companion', 'Log'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateNotify34'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateNotify38'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateRegenList'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateLand'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Melee', 'TranslateInterrupt'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateT5'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),            # 0.6.6
    ('TruShadowCombat', 'Death', 'TranslateVaulted'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Death', 'TranslateVaultedClock'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Hit', 'Translate'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),               # 0.6.7
    ('TruShadowCombat', 'Hit', 'TranslateKnockback'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Hit', 'Log'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),
    ('TruShadowCombat', 'Hit', 'TranslateImpulseGate'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),    # 0.6.8
    ('TruShadowCombat', 'Death', 'Log'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),                   # 0.6.9
    ('TruShadowCombat', 'Hit', 'TranslateHitSpeed'): ('void P1dReadSwitches(', 'kP1dKeys[] = {'),       # 0.6.10
    ('TruShadowCombat', 'Strike', 'Translate'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate1013'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate1019'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate1020'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate1004'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate231Slot0'): 'void ReadSwitches(',
    ('TruShadowCombat', 'States', 'Translate231Slot1'): 'void ReadSwitches(',
    ('TruShadowPower', 'Adrenaline', 'Translate'): 'void K11ReadSwitch(',
    ('TruShadowPower', 'TimeScale', 'TranslateSlot6'): 'void Slot6ReadSwitch(',     # 0.21 (X23, 2026-11-10)
    ('TruShadowPower', 'Reticle', 'TranslateRequest'): 'void ReticleReadSwitch(',   # 0.22 (K-5, 2026-11-10)
    ('TruShadowPower', 'Reticle', 'TranslateRefill'): 'void ReticleReadSwitch(',
    ('TruMercLang', 'MercLang', 'Enabled'): 'void PollIni(',
    ('TruMercLang', 'MercLang', 'Language'): 'void PollIni(',
    # TruQoL 0.1.1 (17y): LiveTick (game thread, once a second after a change of the file time) -> LiveReadOptions
    ('TruQoL', 'TruQoL', 'LogLevel'): 'void LiveReadOptions(',
    ('TruQoL', 'FrameLimit', 'Enabled'): 'void LiveReadOptions(',
    ('TruQoL', 'FrameLimit', 'MaxFps'): 'void LiveReadOptions(',
    ('TruQoL', 'FrameLimit', 'AutoOff'): 'void LiveReadOptions(',
    ('TruQoL', 'FrameLimit', 'SpinUs'): 'void LiveReadOptions(',
    ('TruQoL', 'Camera', 'Fov'): 'void LiveReadOptions(',
    ('TruQoL', 'Camera', 'FovCutscenes'): 'void LiveReadOptions(',
    ('TruQoL', 'Camera', 'ShakeScale'): 'void LiveReadOptions(',
}
SW_MAX, SW_GROUP_MAX = 160, 24
RING_FROZEN = 172                            # 0.21.5: the ring is frozen - no new entries


def ring_entries(path):
    """0.21.5: [(line, path, label, id, arg)] of a radial-format file (comments / blank lines skipped)"""
    out = []
    for n, line in enumerate(open(path, encoding='ascii', errors='replace').read().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'): continue
        f = [x.strip() for x in line.split('|')]
        if len(f) != 3: continue
        word, _, arg = f[2].partition(' ')
        out.append((n, f[0], f[1], word, arg.strip()))
    return out


def choice_args(src, table):
    """0.21.5: the first fields of a QbChoice table (kQbWeapons / kQbMarks)"""
    m = re.search(r'const QbChoice %s\[\] = \{(.*?)\};' % table, src, re.S)
    return set(re.findall(r'\{"([^"]+)", "[^"]*", "[^"]*"\}', m.group(1))) if m else set()


def row_covers(row, word, arg, src):
    """0.21.5 ring parity rule: does a bar row (qb_rows tuple) run the ring entry (id, arg)? bool rows: the entry's
    0 / 1 / no argument; value rows: their steps; choice rows: one of their choices; others: the same argument"""
    table, de, rid, rarg, kind, layer = row[:6]
    if rid != word: return False
    if kind == 'kQbBool':
        base = (rarg + ' ') if rarg else ''
        return arg in (rarg, base + '0', base + '1') or (not rarg and arg in ('', '0', '1'))
    if kind == 'kQbValue': return True
    if kind == 'kQbChoice':
        tab = {'weapon.give': 'kQbWeapons', 'claude.mark': 'kQbMarks'}.get(word)
        return bool(tab) and arg in choice_args(src, tab)
    return rarg == arg


def ring_parity(src, radial_path):
    """0.21.5: ring entries no bar row runs ([(line, path, label, id, arg)])"""
    rows = qb_rows(src)
    return [e for e in ring_entries(radial_path) if not any(row_covers(r, e[3], e[4], src) for r in rows)]


def plugin_version(plugin):
    """'0.6.3' from the plugin sources ("<Plugin> 0.6.3" in a string literal), '' when missing"""
    best = ()
    folder = os.path.join(PLUGINS, plugin)
    for f in os.listdir(folder) if os.path.isdir(folder) else []:
        if not f.endswith(('.cpp', '.h')): continue
        for m in re.finditer(r'"%s (\d+(?:\.\d+)+)' % plugin, open(os.path.join(folder, f), encoding='utf-8',
                                                                     errors='replace').read()):
            best = max(best, tuple(int(x) for x in m.group(1).split('.')))
    return best


def plugin_source(plugin):
    folder = os.path.join(PLUGINS, plugin)
    return '\n'.join(open(os.path.join(folder, f), encoding='utf-8', errors='replace').read()
                     for f in sorted(os.listdir(folder)) if f.endswith('.cpp'))


def plugin_ini(plugin):
    """{(section, key): (line, value)} of the shipped plugin INI"""
    out, section = {}, None
    path = os.path.join(PLUGINS, plugin, plugin + '.ini')
    if not os.path.exists(path): return None
    for n, line in enumerate(open(path, encoding='utf-8', errors='replace').read().splitlines(), 1):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            section = m.group(1)
            continue
        if not line or line.startswith(';') or '=' not in line: continue
        key, _, value = line.partition('=')
        out[(section, key.strip())] = (n, value.strip())
    return out


def sw_value_ok(typ, v):
    if typ == 'bool': return v in ('0', '1')
    m = re.fullmatch(r'int:(-?\d+)\.\.(-?\d+)(?::(\d+))?', typ)
    if m: return bool(re.fullmatch(r'-?\d{1,9}', v)) and int(m.group(1)) <= int(v) <= int(m.group(2))
    if typ.startswith('choice:'): return v.lower() in [c.lower() for c in typ[7:].split(',')]
    return False


Q217_HELP_MAX = 60                           # 0.21.7: a help line (bar footer / tooltip), characters per language
# 0.21.7: German words that must be written with their umlaut in the DE texts of the switches file (Lukas: "Umlaute
# spaeter nachziehen") - an ASCII transliteration of one of them is a problem
Q217_TRANSLIT = ('Doppelgaengerin', 'Kostuem', 'Soeldner', 'Zustaende', 'Aktivitaeten', 'fuer', 'ueber', 'ausserhalb',
                 'zurueck', 'Aenderung', 'anhaengen', 'Uebersetzung', 'Toedlich', 'loescht', 'Spruenge', 'Uebergaenge',
                 'Empfaenger', 'Geaendert', 'waehrend', 'Fuellt', 'behaelt', 'pruef', 'Pruef')


def sw_translit(where, text):
    """0.21.7: ASCII transliterations (ae / oe / ue / ss) of Q217_TRANSLIT words in a DE text"""
    low = text.lower()
    return ['%s: write "%s" with its umlaut (DE text "%s")' % (where, w, text) for w in Q217_TRANSLIT if w.lower() in low]


def check_switches(path):
    """0.21.5: the switches file - format, every key in its shipped plugin INI (rows of a newer plugin version than the
    sources may wait), default = the INI value, type fits, live = the plugin's re-read function (SW_LIVE), every INI key
    of the plugins covered (text keys excepted); returns problems, summary, rows"""
    problems, rows, groups, seen, gkeys = [], [], 0, set(), set()
    name = os.path.basename(path)
    if not os.path.exists(path): return ['%s missing' % name], '', []
    raw = open(path, 'rb').read()
    # 0.21.7 (TODO "Umlaute in TruMenu.switches.txt"): UTF-8 without BOM, umlauts in the texts (the bar's font, ImGui's
    # ProggyClean, has the Latin-1 glyphs - work/m0217_0711/font_glyphs.py); was: ASCII only
    if raw.startswith(b'\xef\xbb\xbf'): problems.append('%s: UTF-8 BOM (write the file without BOM)' % name)
    if any(b == 127 or (b < 32 and b not in (9, 10, 13)) for b in raw):
        problems.append('%s: control bytes' % name)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        problems.append('%s: not UTF-8 (%s)' % (name, e))
        text = raw.decode('utf-8', 'replace')
    bad_chars = sorted({c for c in text if ord(c) > 0xff})
    if bad_chars: problems.append('%s: characters outside Latin-1 (no glyph in the bar font): %s' % (name, ''.join(bad_chars)))
    lines = text.lstrip('﻿').splitlines()
    if not lines or not lines[0].startswith('# TruMenu switches'):
        problems.append('%s: first line must start with "# TruMenu switches" (Set-TruMenu.ps1 / SwLoadLocked marker)' % name)
    inis, versions, sources = {}, {}, {}
    word = re.compile(r'[A-Za-z0-9_]+')
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith('#'): continue
        where = '%s:%d' % (name, n)
        f = [x.strip() for x in s.split('|')]
        if f[0] == 'group':
            if len(f) not in (4, 5) or not word.fullmatch(f[1]) or len(f[1]) > 23 or not f[2] or not f[3] or \
                    (len(f) == 5 and f[4] != 'open'):
                problems.append('%s: group | <key> | <DE> | <EN> [| open]' % where)
            elif f[1] in gkeys: problems.append('%s: group key %s twice' % (where, f[1]))
            if len(f) >= 4 and (len(f[2].encode('utf-8')) > 63 or len(f[3].encode('utf-8')) > 63):
                problems.append('%s: group DE / EN longer than 63 bytes (SwGroup)' % where)
            if len(f) >= 3: problems += sw_translit(where, f[2])
            gkeys.add(f[1])
            groups += 1
            continue
        if not groups: problems.append('%s: switch line before the first group line' % where)
        if len(f) not in (9, 10):
            problems.append('%s: want 9 or 10 fields, got %d' % (where, len(f)))
            continue
        plugin, section, key, typ, de, en, when, default, hint = f[:9]
        since = f[9] if len(f) == 10 else ''
        if plugin not in SW_PLUGINS: problems.append('%s: plugin %s not in %s' % (where, plugin, SW_PLUGINS))
        if not (word.fullmatch(section) and len(section) < 32 and word.fullmatch(key) and len(key) < 40):
            problems.append('%s: section / key (letters, digits, _)' % where)
        # 17y: choice values may hold a dot (TruQoL Fov / ShakeScale floats as their exact INI text)
        if not re.fullmatch(r'bool|int:-?\d+\.\.-?\d+(:\d+)?|choice:[A-Za-z0-9_.]+(,[A-Za-z0-9_.]+)+', typ):
            problems.append('%s: type %s (bool | int:<lo>..<hi>[:<step>] | choice:<a>,<b>)' % (where, typ))
        m = re.fullmatch(r'int:(-?\d+)\.\.(-?\d+)(?::(\d+))?', typ)
        if m and (int(m.group(1)) >= int(m.group(2)) or (m.group(3) and not
                  1 <= int(m.group(3)) <= int(m.group(2)) - int(m.group(1)))):
            problems.append('%s: int range / step' % where)
        if typ.startswith('choice:') and len(typ) - 7 >= 64: problems.append('%s: choice list longer than 63' % where)
        if not de or not en or len(de.encode('utf-8')) > 63 or len(en.encode('utf-8')) > 63:
            problems.append('%s: DE / EN text empty or longer than 63 bytes' % where)
        if len(hint.encode('utf-8')) > 199: problems.append('%s: hint longer than 199 bytes' % where)
        # 0.21.7: the hint column = "<DE help> // <EN help>", each half the bar's help line (at most Q217_HELP_MAX)
        halves = hint.split(' // ')
        if len(halves) != 2 or not halves[0].strip() or not halves[1].strip():
            problems.append('%s: hint must be "<DE help> // <EN help>" (got %r)' % (where, hint[:50]))
        else:
            for lang, h in zip(('DE', 'EN'), halves):
                if len(h) > Q217_HELP_MAX: problems.append('%s: %s help %d characters > %d' % (where, lang, len(h), Q217_HELP_MAX))
        for label, v in (('plugin', plugin), ('section', section), ('key', key), ('type', typ), ('when', when),
                         ('default', default), ('since', since)):
            if any(ord(c) > 126 for c in v): problems.append('%s: %s must stay ASCII' % (where, label))
        problems += sw_translit(where, de) + sw_translit(where, halves[0])
        if when not in ('live', 'restart') and not re.fullmatch(r'live-if:[A-Za-z0-9_]+', when):
            problems.append('%s: when %s (live | restart | live-if:<Key>)' % (where, when))
        if not sw_value_ok(typ, default): problems.append('%s: default %s does not fit %s' % (where, default, typ))
        if (plugin, section, key) in seen: problems.append('%s: [%s] %s of %s twice' % (where, section, key, plugin))
        seen.add((plugin, section, key))
        rows.append((n, plugin, section, key, typ, when, default, since))
        if plugin not in SW_PLUGINS: continue
        if plugin not in inis:
            inis[plugin], versions[plugin], sources[plugin] = plugin_ini(plugin), plugin_version(plugin), \
                plugin_source(plugin)
        ini = inis[plugin] or {}
        pending = False
        if since:
            sm = re.fullmatch(r'(Tru[A-Za-z0-9]+) (\d+(?:\.\d+)+)', since)
            if not sm or sm.group(1) != plugin: problems.append('%s: since "%s" (<the row\'s plugin> <version>)' % (where, since))
            else: pending = tuple(int(x) for x in sm.group(2).split('.')) > versions[plugin]
        got = ini.get((section, key))
        if got is None:
            if not pending: problems.append('%s: [%s] %s is not in %s.ini' % (where, section, key, plugin))
        else:
            if not sw_value_ok(typ, got[1]):
                problems.append('%s: %s.ini:%d %s=%s does not fit %s' % (where, plugin, got[0], key, got[1], typ))
            if got[1] != default and not pending:
                problems.append('%s: default %s, %s.ini:%d has %s' % (where, default, plugin, got[0], got[1]))
        live = SW_LIVE.get((plugin, section, key))
        if when == 'restart' and live:
            fn_name = live[0] if isinstance(live, tuple) else live
            problems.append('%s: [%s] %s is re-read at run time (%s) - mark it live' % (where, section, key, fn_name.strip('(')))
        if when != 'restart':
            if not live: problems.append('%s: [%s] %s marked %s but %s reads it only at the start' % (where, section, key,
                                                                                                  when, plugin))
            elif isinstance(live, tuple):
                # 0.6.5 form: the re-read function loops over a key table - the function must use the table and the
                # table must hold {"section", "key", ...}
                fn, table = live
                body = fn_body(sources[plugin], fn)
                src = sources[plugin]
                at = src.find(table)
                tbl = src[at:src.find('\n};', at)] if at >= 0 else ''
                if not body or table.split('[')[0] not in body or '{"%s", "%s"' % (section, key) not in tbl:
                    problems.append('%s: %s / %s has no read of [%s] %s' % (where, fn.strip('('), table, section, key))
            else:
                body = fn_body(sources[plugin], live)
                if not body or '"%s"' % key not in body or '"%s"' % section not in body:
                    problems.append('%s: %s has no read of [%s] %s' % (where, live.strip('('), section, key))
            if when.startswith('live-if:') and (section, when[8:]) not in ini:
                problems.append('%s: %s - [%s] %s not in %s.ini' % (where, when, section, when[8:], plugin))
    if len(rows) > SW_MAX: problems.append('%s: %d switch lines, TruMenu keeps %d' % (name, len(rows), SW_MAX))
    if groups > SW_GROUP_MAX: problems.append('%s: %d groups, TruMenu keeps %d' % (name, groups, SW_GROUP_MAX))
    for plugin in SW_PLUGINS:                # every switch of the plugin INIs is a row
        for (section, key), (line, value) in sorted((plugin_ini(plugin) or {}).items()):
            if (plugin, section, key) not in seen and (plugin, section, key) not in SW_TEXT_KEYS:
                problems.append('%s: %s.ini:%d [%s] %s has no row' % (name, plugin, line, section, key))
    for (plugin, section, key) in SW_LIVE:
        if (plugin, section, key) not in seen: problems.append('%s: live key [%s] %s of %s has no row' % (name, section,
                                                                                                         key, plugin))
    live_n = sum(1 for r in rows if r[5] != 'restart')
    return problems, '%d switches (%d live / live-if) in %d groups, %d plugins' % (len(rows), live_n, groups,
                                                                                len({r[1] for r in rows})), rows


def check_0215(radial_path, switches_path):
    """0.21.5 (2026-11-07 TruMenu 0.21.5 Fixes + frozen ring): see the module text"""
    problems, summary, rows = check_switches(switches_path)
    src = read_cpp()
    items = item_types(src)
    for item in ('sw.set', 'sw.list', 'sw.reload'):
        m = re.search(r'\{"%s", "action", (?:"[^"]*"\s*)+,\s*(true|false),' % re.escape(item), src)
        if not m: problems.append('TruMenu.cpp: item %s (action) missing in kItems' % item)
        elif m.group(1) != 'false': problems.append('TruMenu.cpp: %s must not be a game-thread item' % item)
    if not re.search(r'\{"Fixes", "Fixes", nullptr, 0, kQsSwitches\}', src):
        problems.append('TruMenu.cpp: kQbPages has no page Fixes (kQsSwitches)')
    sec = src[src.find('// ---- 0.21.5 Fixes'):src.find('// ---- end of 0.21.5 Fixes')]
    if not sec: problems.append('TruMenu.cpp: section "0.21.5 Fixes" missing')
    if sec.count('WritePrivateProfileStringA(') != 1:
        problems.append('TruMenu.cpp: section 0.21.5 Fixes must write the plugin INI in exactly one place (RunSwSet)')
    rs = fn_body(src, 'bool RunSwSet(')
    marks = [rs.find(t) for t in ('SwFindLocked(', 'SwValueOk(', 'GetFileAttributesA(', 'strcmp(old.text, v)',
                                  'WritePrivateProfileStringA(')]
    if not rs or -1 in marks or marks != sorted(marks):
        problems.append('TruMenu.cpp: RunSwSet must check in this order before the write: listed key, value fits, INI '
                        'exists, value changed (got %s)' % marks)
    if 'TestIniTarget(' not in rs: problems.append('TruMenu.cpp: RunSwSet must build the path with TestIniTarget')
    if 'kSwMarker' not in fn_body(src, 'void SwLoadLocked(') or '"# TruMenu switches"' not in src:
        problems.append('TruMenu.cpp: SwLoadLocked must refuse a file without the first-line marker')
    if not re.search(r'kSwMax = %d, kSwGroupMax = %d' % (SW_MAX, SW_GROUP_MAX), src):
        problems.append('TruMenu.cpp: kSwMax / kSwGroupMax differ from this tool (%d / %d)' % (SW_MAX, SW_GROUP_MAX))
    fav = fn_body(src, 'void QbFavPin(')
    if 'kQsSwitches' not in fav: problems.append('TruMenu.cpp: QbFavPin must refuse Y on page Fixes (no favourite)')
    tick = fn_body(src, 'void QuickTick(')
    if 'p.special == kQsSwitches ? kQbXDir : 1' not in tick and \
            'p.special == kQsSwitches || swRow ? kQbXDir : 1' not in tick:   # 0.21.8: + a pinned switch on page 0
        problems.append('TruMenu.cpp: QuickTick: X on page Fixes must pass kQbXDir')
    act = fn_body(src, 'void QbSwAct(')
    if 'QbRun("Fixes"' not in act or '"sw.set"' not in act:
        problems.append('TruMenu.cpp: QbSwAct must write through the item sw.set (QbRun)')
    if 'g_swGroup[g].open = false' not in act: problems.append('TruMenu.cpp: QbSwAct must keep one group open at a time')
    # 0.21.8: the widget is SwMenuWidget (also on the favourites page), the write SwMenuAfter -> RunSwSet
    if 'RunSwSet(pending' not in fn_body(src, 'void PageSwitches(') and not (
            'SwMenuAfter(pending' in fn_body(src, 'void PageSwitches(') and
            'RunSwSet(pending' in fn_body(src, 'void SwMenuAfter(')):
        problems.append('TruMenu.cpp: the menu section Fixes must write through RunSwSet')
    if 'PageSwitches();' not in src or 'PageQbAll();' not in src or 'kQbPages[p]' not in fn_body(src, 'void PageQbAll('):
        problems.append('TruMenu.cpp: the long menu needs the sections Fixes (PageSwitches) and Quick bar pages (PageQbAll '
                        'over kQbPages)')
    build = open(os.path.join(ROOT, 'scripts', 'windows', 'Build-TruAsi.ps1'), encoding='utf-8-sig').read()
    if "'switches.txt'" not in build: problems.append('Build-TruAsi.ps1 does not copy TruMenu.switches.txt')
    st = open(os.path.join(ROOT, 'scripts', 'windows', 'Set-TruMenu.ps1'), encoding='utf-8-sig').read()
    if 'TruMenu.switches.txt' not in st: problems.append('Set-TruMenu.ps1 does not install TruMenu.switches.txt')
    # the frozen ring: its header says so, no new entries, every entry is a bar row (and so a row of the menu section)
    rtext = open(radial_path, encoding='ascii', errors='replace').read()
    if 'aktuell nicht weiter gemacht' not in rtext or 'frozen' not in rtext:
        problems.append('%s: the header must say the ring is frozen ("aktuell nicht weiter gemacht")' %
                        os.path.basename(radial_path))
    entries = ring_entries(radial_path)
    if len(entries) > RING_FROZEN:
        problems.append('%s: %d entries - the ring is frozen at %d (no new entries)' % (os.path.basename(radial_path),
                                                                                       len(entries), RING_FROZEN))
    for e in ring_parity(src, radial_path):
        problems.append('%s:%d: ring entry %s | %s | %s %s is no bar row (ring frozen: every entry belongs in the bar)' %
                        ((os.path.basename(radial_path),) + e))
    return problems, '%s; items sw.*, page Fixes, RunSwSet order, Y refused, menu sections; ring %d entries all bar ' \
                     'rows' % (summary, len(entries))


def check_0216(ini_path):
    """0.21.6 (2026-11-07 TruMenu 0.21.6): bar page Kostueme (own page after Lara, page limit 16 / row limit 64; rows from
    the cycle list and the player records, the current costume marked, refused without a level; the choice row switches
    only after kCosSettleMs without a new step, wraps, X = now; Y refused; the only items costume.set / .next /
    .choosereload), the flight key line ([Cheat] FlightHint 0 / 1 default 1, drawn only while flight is on + menu closed +
    the INI switch on, above the bottom-right sound list / flow line, the same text as footer / tooltip) and the quick
    command line (L3 alone, not as part of L3 + R3; one command path = CmdRunLine only; keys held from the game)"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    if not src.startswith('//') or '0.21.6 (bar page Kostueme' not in src[:src.find('\n', src.find('kVersion = '))]:
        problems.append('TruMenu.cpp: kVersion must keep the 0.21.6 text (0.21.7: the version check moved to check_0217)')
    # [Cheat] FlightHint
    opts = {(s, k): d for s, k, d, c in table(src)[1]}
    if opts.get(('Cheat', 'FlightHint')) != '1':
        problems.append('TruMenu.cpp: kOpts [Cheat] FlightHint missing or default not 1')
    found = [(n, v) for n, k, v in ini_section(ini_path, 'Cheat') if k == 'FlightHint']
    if len(found) != 1: problems.append('%s: [Cheat] FlightHint missing' % name)
    elif found[0][1] not in ('0', '1'): problems.append('%s:%d: [Cheat] FlightHint=%s (0 / 1)' % ((name,) + found[0]))
    if 'g_flightHint = OptInt(ini, "Cheat", "FlightHint")' not in src:
        problems.append('TruMenu.cpp: [Cheat] FlightHint is never read (g_flightHint = OptInt(...))')
    # pages / rows
    block = src[src.index('const QbPage kQbPages[] = {'):]
    block = block[:block.index('\n};')]
    order = re.findall(r'(?:QB_PAGE\("([^"]*)", "[^"]*", (kQb[A-Za-z]+), (kQs[A-Za-z]+)\)|\{"([^"]*)", "[^"]*", nullptr, 0, '
                       r'(kQs[A-Za-z]+)\})', block)
    pages = [(a or d, b or None, c or e) for a, b, c, d, e in order]
    if len(pages) > QB_PAGES_MAX:             # 0.21.11: 17 (page Rettung; g_qbRow[17])
        problems.append('TruMenu.cpp: kQbPages has %d pages - g_qbRow holds %d' % (len(pages), QB_PAGES_MAX))
    specials = [p[2] for p in pages]
    if specials.count('kQsCostume') != 1:
        problems.append('TruMenu.cpp: kQbPages needs exactly one page Kostueme (kQsCostume), found %d'
                        % specials.count('kQsCostume'))
    elif pages[specials.index('kQsCostume') - 1][1] != 'kQbLara':
        problems.append('TruMenu.cpp: page Kostueme must follow page Lara')
    if 'static_assert(kQbPageN <= %d' % QB_PAGES_MAX not in src or 'g_qbRow[%d]' % QB_PAGES_MAX not in src or \
            'const int kQbViewMax = 64;' not in src:
        problems.append('TruMenu.cpp: the page / row limits (static_assert kQbPageN <= %d, g_qbRow[%d], kQbViewMax 64) '
                        'changed' % (QB_PAGES_MAX, QB_PAGES_MAX))
    sec = src[src.find('// ---- 0.21.6 costumes'):src.find('// ---- end of 0.21.6 costumes')]
    if len(sec) < 100: problems.append('TruMenu.cpp: section "0.21.6 costumes" missing')
    m = re.search(r'const DWORD kCosSettleMs = (\d+);', sec)
    if not m or not Q216_SETTLE[0] <= int(m.group(1)) <= Q216_SETTLE[1]:
        problems.append('TruMenu.cpp: kCosSettleMs must be %d .. %d ms (the choice row waits about 0.5 s)' % Q216_SETTLE)
    mn = re.search(r'kCosSlotNames\[16\] = \{(.*?)\};', sec, re.S)
    names = tuple(x.replace('\\"', '"') for x in re.findall(r'"((?:[^"\\]|\\.)*)"', mn.group(1))) if mn else ()
    if names != Q216_COS_NAMES:
        problems.append('TruMenu.cpp: kCosSlotNames differ from the game texts (PC locals 83 + slot, '
                        'work/rebuild/costumes_0311/logs/check_names.txt)')
    names_log = os.path.join(ROOT, 'work', 'rebuild', 'costumes_0311', 'logs', 'check_names.txt')
    if os.path.isfile(names_log):              # the measured texts (the log is local work data, not in the repository)
        log = dict(re.findall(r"^slot ([a-p]) xbox \d+ -> pc \d+ b['\"](.*?)['\"]\s", open(names_log, encoding='utf-8',
                                                                                          errors='replace').read(), re.M))
        for i, want in enumerate(Q216_COS_NAMES):
            got = log.get(chr(97 + i))
            if got is not None and got != want:
                problems.append('Q216_COS_NAMES slot %s "%s" != check_names.txt "%s"' % (chr(97 + i), want, got))
    refresh = fn_body(src, 'void CosRefresh(')
    for need in ('GlobalCostumes(g_cos.ids, 128)', 'TypeRecord(', 'ObjectId(', 'ReadDword(kCostumeNow'):
        if need not in refresh: problems.append('TruMenu.cpp: CosRefresh must read %s (the long menu\'s data)' % need)
    rows = fn_body(src, 'int QbCosRows(')
    for need in ('CosRefresh();', 'add(kQdCosPick', 'add(kQdCosNext', 'add(kQdCosRec', 'add(kQdCosGroup', 'add(kQdCos, g_cos.ids[i])',
                 'static_cast<DWORD>(g_cos.ids[i]) == g_cos.now', 'g_cos.listOpen && i < listN && n < max'):
        if need not in rows: problems.append('TruMenu.cpp: QbCosRows lacks %s (rows from the list, current marked, '
                                             'limit)' % need)
    why = fn_body(src, 'const char *CosWhy(')
    if '!InLevel()' not in why or '!g_experimental' not in why:
        problems.append('TruMenu.cpp: CosWhy must refuse without a level / with Experimental=0 (the long menu\'s rule)')
    act = fn_body(src, 'void QbCosAct(')
    cases = dict(re.findall(r'case (kQdCos[A-Za-z]*): \{?(.*?)(?=\n    case |\n    default:)', act, re.S))
    pick = cases.get('kQdCosPick', '')
    i_why, i_x, i_step = pick.find('CosWhy(true'), pick.find('if (x)'), pick.find('CosStep(')
    if not (0 <= i_why < i_x < i_step):
        problems.append('TruMenu.cpp: QbCosAct kQdCosPick: CosWhy first, then X (= now), then the step')
    else:
        step = pick[i_step:]
        if 'g_cos.pending = true' not in step or 'CosApply(' in step or 'QbRun(' in step:
            problems.append('TruMenu.cpp: QbCosAct: a left / right step must only pick (pending) - the switch belongs to '
                            'QbCosTick after kCosSettleMs (no switch on every step)')
        if 'CosApply(shown)' not in pick[i_x:i_step]: problems.append('TruMenu.cpp: QbCosAct: X must apply the shown entry')
    for case, rule in (('kQdCos', 'CosWhy(true'), ('kQdCosRec', 'CosWhy(false')):
        body = cases.get(case, '')
        run = max(body.find('CosApply('), body.find('QbRun('))
        if not (0 <= body.find(rule) < body.find('if (why[0]) {') < run):
            problems.append('TruMenu.cpp: QbCosAct %s must check %s and refuse before it runs' % (case, rule))
    if 'QbConfirm(' not in cases.get('kQdCosRec', ''):
        problems.append('TruMenu.cpp: QbCosAct kQdCosRec (reloads the unit) must confirm (QbConfirm)')
    tick = fn_body(src, 'void QbCosTick(')
    marks = [tick.find(t) for t in ('kCosSettleMs', 'g_cos.pending = false', 'CosWhy(true', 'CosApply(g_cos.pickId)')]
    if not tick or -1 in marks or marks != sorted(marks):
        problems.append('TruMenu.cpp: QbCosTick must wait kCosSettleMs, clear the pick, check CosWhy, then CosApply')
    step = fn_body(src, 'int CosStep(')
    if '% n' not in step or 'n - 1' not in step:
        problems.append('TruMenu.cpp: CosStep must wrap at both ends (% n, n - 1)')
    runs = re.findall(r'QbRun\("Kostueme", [^;]*?"(costume\.[a-z]+)"', sec)
    if sorted(runs) != ['costume.choosereload', 'costume.set'] or 'kQbCosNext = {"Naechstes Kostuem", "Next costume", ' \
                                                                  '"costume.next", ""' not in src:
        problems.append('TruMenu.cpp: page Kostueme must run costume.set (CosApply, once), costume.choosereload and the '
                        'row kQbCosNext = costume.next - nothing else (got %s)' % runs)
    items = item_types(src)
    for item in Q216_COS_ITEMS:
        if items.get(item) != 'action': problems.append('TruMenu.cpp: item %s missing in kItems' % item)
    if 'QbCosTick();' not in fn_body(src, 'void Render('):
        problems.append('TruMenu.cpp: Render must call QbCosTick every frame (the waiting switch also with the bar closed)')
    if 'kQsCostume' not in fn_body(src, 'void QbFavPin('):
        problems.append('TruMenu.cpp: QbFavPin must refuse Y on the costume rows (no favourite with an argument)')
    if 'p.special == kQsCostume) QbSpecialAct(p.special, row - g_qbStaticN, kQbXDir)' not in fn_body(src, 'void QuickTick('):
        problems.append('TruMenu.cpp: QuickTick: X on page Kostueme must pass kQbXDir')
    if 'kQsCostume) n = QbCosRows(' not in fn_body(src, 'int QbSpecialBuild('):
        problems.append('TruMenu.cpp: QbSpecialBuild does not build page Kostueme')
    # flight key line
    mw = re.search(r'bool FlightHintWanted\(\) \{ return ([^;]*); \}', src)
    want = mw.group(1).replace(' ', '') if mw else ''
    for need in ('g_flightHint', 'g_flight', '!g_menuOpen', 'InLevel()'):
        if need not in want.split('&&'):
            problems.append('TruMenu.cpp: FlightHintWanted must be g_flightHint && g_flight && !g_menuOpen && InLevel() '
                            '(missing %s)' % need)
    render = fn_body(src, 'void Render(')
    # 0.22.1: the early-return condition goes on with "&& !cnBadge)" (the cutscene pause badge)
    if 'const bool flightHint = FlightHintWanted();' not in render or \
            not re.search(r'!flightHint( && ![A-Za-z]+)*\)', render) or \
            'if (flightHint) DrawFlightHint();' not in render:
        problems.append('TruMenu.cpp: Render must draw the flight line only when FlightHintWanted()')
    elif render.find('if (flowDraw) DrawFlowOverlay();') > render.find('if (flightHint) DrawFlightHint();') or \
            render.find('if (g_snOn) DrawSoundList();') > render.find('if (flightHint) DrawFlightHint();'):
        problems.append('TruMenu.cpp: the flight line must be drawn after the sound list and the flow line (keeps above)')
    dh = fn_body(src, 'void DrawFlightHint(')
    for need in ('"##TruSoundList"', '"##TruMenuFlow"', 'w->Pos.y - 6.0f', 'FlightHintText(g_qbLang == 0'):
        if need not in dh: problems.append('TruMenu.cpp: DrawFlightHint lacks %s (above the bottom-right windows, the '
                                           'bar\'s language)' % need)
    ft = fn_body(src, 'void FlightHintText(')
    for need in ('RT hoch', 'LT runter', 'Stick bewegt', 'Tempo', 'RT up', 'LT down', 'g_flightSpeed'):
        if need not in ft: problems.append('TruMenu.cpp: FlightHintText lacks "%s"' % need)
    if 'FlightHintText(' not in fn_body(src, 'void PageCheat(') or 'cheat.flight' not in fn_body(src, 'bool QbRowHint('):
        problems.append('TruMenu.cpp: the keys must be the menu flight button\'s tooltip and the bar row\'s hint')
    # quick command line
    qc = src[src.find('// ---- 0.21.6 quick command line'):src.find('// ---- end of 0.21.6 quick command line')]
    if len(qc) < 100: problems.append('TruMenu.cpp: section "0.21.6 quick command line" missing')
    if qc.count('CmdRunLine(') != 1:
        problems.append('TruMenu.cpp: the quick command line must run every line through exactly one CmdRunLine call '
                        '(found %d)' % qc.count('CmdRunLine('))
    for t in Q216_EXEC:
        if t in qc: problems.append('TruMenu.cpp: second exec path: the quick command line calls %s (one command path: '
                                    'CmdRunLine only)' % t)
    pt = fn_body(src, 'bool QcPadTick(')
    for need in ('(g_toggleButtons | g_radHold) & ~fb', 'if (down && (buttons & others)) armed = false;',
                 'QcOpen(false, !g_qbOpen'):
        if need not in pt: problems.append('TruMenu.cpp: QcPadTick lacks %s (L3 alone only, closes with the bar / menu / '
                                           'ring)' % need)
    qt = fn_body(src, 'void QuickTick(')
    i_qc, i_ret = qt.find('QcPadTick('), qt.find('InterlockedExchange(&g_qbJust, 0)')
    if not (0 <= i_qc < i_ret) or 'if (qcHasPad) {' not in qt:
        problems.append('TruMenu.cpp: QuickTick must call QcPadTick before its early return and let the rows wait')
    if 'g_imguiReady && g_qcOpen && IsKeyMessage(msg)' not in fn_body(src, 'LRESULT CALLBACK WndProcHook(') or \
            'RadMenuOpen() || g_qcOpen' not in fn_body(src, 'int __fastcall KbdReadHook('):
        problems.append('TruMenu.cpp: the command line must hold the keys from the game (WndProcHook + KbdReadHook)')
    if not re.search(r'const WORD kQcOwn = 0x3000;', src) or 'g_cmdFocusButton | (g_qcOpen ? kQcOwn : 0)' not in \
            fn_body(src, 'WORD QbPad('):
        problems.append('TruMenu.cpp: QbPad must keep FocusButton (bar open) and A / B (line open) from the game')
    if 'if (quickDraw && g_qcOpen && !g_menuOpen) DrawQuickCmd();' not in render:
        problems.append('TruMenu.cpp: Render must draw the command line only with the bar open and the menu closed')
    # toggle rows (owner live test 20:52): an item that flips a flag per argument has a state function in RadialOn - its
    # bar rows must be bool rows (an / aus, right on, left off, X toggle), never action rows ("rechts", a blind flip)
    ron = fn_body(src, 'bool RadialOn(')
    toggles = 0
    for tab, de, item, arg, kind, _ in qb_rows(src):
        if item not in Q216_TOGGLE_ITEMS or not arg or ' ' in arg: continue
        toggles += 1
        if kind != 'kQbBool':
            problems.append('TruMenu.cpp: %s row "%s" (%s %s) flips a flag - toggle rows must be bool rows with a value '
                            'function (RadialOn), not %s' % (tab, de, item, arg, kind))
    for item in Q216_TOGGLE_ITEMS:
        if '!_stricmp(e.id, "%s")' % item not in ron:
            problems.append('TruMenu.cpp: RadialOn has no state (value function) for the toggle item %s' % item)
    nn = fn_body(src, 'const char *NavRowNote(')
    if not nn or 'NavRowNote(r.arg, de)' not in fn_body(src, 'void QbViewOf(') or \
            any(t in nn for t in ('PutByte(', 'WriteDword(', 'WriteByte(', 'NavSet(')):
        problems.append('TruMenu.cpp: a nav.draw row that is on but cannot draw needs NavRowNote (read only) in QbViewOf')
    return problems, 'FlightHint key, page Kostueme after Lara (%d pages), settle %s ms, %d slot names, flight line rule, ' \
                     'one command path, %d toggle rows all bool' % (len(pages), m.group(1) if m else '?', len(names), toggles)


Q217_ITEMS = {'dbg.uber': 'bool', 'uber.dump': 'action', 'shader.labels': 'bool', 'shader.reload': 'action',
              'shader.dump': 'action', 'nav.labels': 'bool',                   # 0.21.7: all render-thread, read only
              'sap.status': 'info', 'sap.reset': 'action'}
Q217_KEYS = {('Debug', 'UberLabels'): '0', ('Debug', 'UberRadius'): '8000', ('Debug', 'UberMax'): '12',
             ('Debug', 'UberMatch'): 'switch,lever', ('Debug', 'NavLabels'): '0', ('Debug', 'NavLabelRadius'): '3000',
             ('Debug', 'NavLabelMax'): '40', ('Shader', 'Labels'): '0', ('Shader', 'File'): 'TruMenu.shaderlabel.txt',
             ('Shader', 'LabelRadius'): '15000', ('Shader', 'LabelMax'): '40', ('Shader', 'ShowOrig'): '0',
             ('Debug', 'SapWatch'): '1'}
Q217_GATES = (3165, 3357)                    # live 2026-11-07: the dlc_caverns_hall gates' distances (not labelled)
Q217_WRITES = ('WriteDword(', 'PutByte(', 'WriteByte(', 'NavPutDword(', 'VirtualProtect(', 'WritePrivateProfileString',
               'QueueItem(', 'InvokeCore(', 'Fn>(')          # nothing of these in the three read-only label sections
Q217_SECTIONS = ('uber labels', 'shader labels', 'navmesh labels', 'SweepAndPrune read-out')
Q217_UMLAUT_WORDS = ('Doppelgängerin', 'Kostüm', 'Söldner', 'Zustände')   # the owner's examples, now with umlauts


def check_0217(ini_path, switches_path):
    """0.21.7 (2026-11-07/08 TruMenu 0.21.7, night build): footer "Y: -" where QbFavPin refuses (QbFavOk), "L3:
    Befehlszeile", the help line (kQbHelp "DE|EN" <= 60 characters per half, keys = bar rows, the Fixes hint column, the
    costume / chapter rows), the switches file with umlauts (UTF-8, the parser cuts at a character boundary), costume
    rows the game refuses (0x5c54e0 on the game thread, grey, skipped, refused), page Kapitel units per chapter (the
    level list's groups, level.load through QbActRow with confirm + backup, the DLC 2 note), the pad diagnosis (log /
    footer only), and the three read-only label layers (uber / shader / navmesh: byte-check tables, no writes, INI keys,
    items, bar rows, Render)"""
    problems = []
    name = os.path.basename(ini_path)
    src = read_cpp()
    # 0.21.8: the version line keeps the 0.21.7 part (as check_0216 reads its own part)
    if not src.startswith('//') or '0.21.7 (bar footer' not in src[:src.find('\n', src.find('kVersion = '))]:
        problems.append('TruMenu.cpp: kVersion must hold the 0.21.7 part "0.21.7 (bar footer"')
    # 1a footer Y
    fav = fn_body(src, 'bool QbFavOk(')
    for need in ('kQbLabel', 'kQbGroup', 'kQbPlanned', 'strcmp(r->id, "-")'):
        if need not in fav: problems.append('TruMenu.cpp: QbFavOk lacks %s (the rule of QbFavPin)' % need)
    if '!r->arg[0]' not in fav and 'FavArgOk(r->arg)' not in fav:   # 0.21.8: an argument that fits the list
        problems.append('TruMenu.cpp: QbFavOk lacks the argument rule (!r->arg[0] / 0.21.8 FavArgOk(r->arg))')
    dq = fn_body(src, 'void DrawQuick(')
    if 'QbFavOk(QbSelRow(g_qbPage, sel))' not in dq or '"X: ausfuehren  Y: -"' not in dq or '"X: run  Y: -"' not in dq:
        problems.append('TruMenu.cpp: DrawQuick must show "Y: -" where QbFavOk(QbSelRow(...)) refuses Y')
    pin = fn_body(src, 'void QbFavPin(')
    if 'kQsChapters' not in pin: problems.append('TruMenu.cpp: QbFavPin must refuse Y on the chapter unit rows')
    # 1b L3 hint
    if 'QbComboText(g_cmdFocusButton' not in dq or '"Befehlszeile"' not in dq or 'g_cmdEnabled && g_cmdFocusButton' not in dq:
        problems.append('TruMenu.cpp: DrawQuick lacks the footer hint "<FocusButton>: Befehlszeile" (only with [Cmd] Enabled)')
    # 1c umlauts
    pr = fn_body(src, 'bool SwParseRow(')
    if 'SwCopyText(r.de' not in pr or 'SwCopyText(r.en' not in pr or '" // "' not in pr or 'r.hintEn' not in pr:
        problems.append('TruMenu.cpp: SwParseRow must copy the texts with SwCopyText and split the hint at " // "')
    if 'Utf8TrimTail(o)' not in fn_body(src, 'void SwCopyText(') or '"\\xef\\xbb\\xbf"' not in fn_body(src, 'void SwLoadLocked('):
        problems.append('TruMenu.cpp: SwCopyText must cut at a UTF-8 character boundary, SwLoadLocked skip a BOM')
    stext = open(switches_path, encoding='utf-8', errors='replace').read()
    for w in Q217_UMLAUT_WORDS:
        if w not in stext: problems.append('%s: "%s" missing (German texts with umlauts)' % (os.path.basename(switches_path), w))
    # 1d help
    m = re.search(r'const QbHelp kQbHelp\[\] = \{(.*?)\n\};', src, re.S)
    helps = [(a, b, unescape(''.join(LIT.findall(t)))) for a, b, t in
             re.findall(r'\{"([a-z][a-z0-9_.]*)", "([^"]*)", ((?:"(?:[^"\\]|\\.)*"\s*)+)\}', m.group(1))] if m else []
    if not helps: problems.append('TruMenu.cpp: kQbHelp missing')
    if 'const int kQbHelpMax = %d;' % Q217_HELP_MAX not in src:
        problems.append('TruMenu.cpp: kQbHelpMax must be %d (the owner: "nicht zu lange")' % Q217_HELP_MAX)
    rows = qb_rows(src) + [('kQbCosNext', 'Naechstes Kostuem', 'costume.next', '', 'kQbAction', '-1')]
    keys = set()
    for hid, harg, text in helps:
        halves = text.split('|')
        if len(halves) != 2 or not halves[0] or not halves[1]:
            problems.append('TruMenu.cpp: kQbHelp %s %s: "DE|EN" (got %r)' % (hid, harg, text[:40]))
        for lang, h in zip(('DE', 'EN'), halves):
            if len(h) > Q217_HELP_MAX:
                problems.append('TruMenu.cpp: kQbHelp %s %s: %s %d characters > %d' % (hid, harg, lang, len(h), Q217_HELP_MAX))
        if (hid, harg) in keys: problems.append('TruMenu.cpp: kQbHelp %s %s twice' % (hid, harg))
        keys.add((hid, harg))
        if not any(r[2] == hid and (harg == '*' or r[3] == harg) for r in rows):
            problems.append('TruMenu.cpp: kQbHelp %s %s is no bar row (help without a row)' % (hid, harg))
    for need in (('nav.draw', 'planner_areas'), ('nav.mask', ''), ('cheat.flight', ''), ('dbg.uber', ''),
                 ('shader.labels', ''), ('nav.labels', '')):
        if need not in keys: problems.append('TruMenu.cpp: kQbHelp lacks %s %s' % need)
    if not any(h[0] == 'nav.draw' and h[1] == 'planner_areas' and 'Alle Ebenen' in h[2] for h in helps):
        problems.append('TruMenu.cpp: the help of "Navmesh Flaechen" must name "Alle Ebenen" (live 2026-11-07 21:57)')
    hl = fn_body(src, 'bool QbHelpLine(')
    for need in ('QbHelpText(r->id, r->arg)', 'g_sw[i].hint', 'g_sw[i].hintEn', 'kQdCosPick', 'kQdCosRec', 'kQdCos:',
                 'ChapHelp('):
        if need not in hl: problems.append('TruMenu.cpp: QbHelpLine lacks %s' % need)
    for body in (hl, fn_body(src, 'bool ChapHelp(')):
        for t in LIT.findall(body):
            if len(unescape(t)) > Q217_HELP_MAX + 2 and ' ' in t:
                problems.append('TruMenu.cpp: help text longer than %d: "%s"' % (Q217_HELP_MAX, unescape(t)[:50]))
    if 'QbHelpLine(g_qbPage, sel, de, help, sizeof(help))' not in dq or 'QbHelpText(r.id, r.arg)' not in \
            fn_body(src, 'void PageQbRow('):
        problems.append('TruMenu.cpp: the help must be the bar footer line (DrawQuick) and the menu tooltip (PageQbRow)')
    if 'r.hintEn' not in fn_body(src, 'void PageSwitches(') and not (   # 0.21.8: the widget is SwMenuWidget
            'SwMenuWidget(' in fn_body(src, 'void PageSwitches(') and 'r.hintEn' in fn_body(src, 'void SwMenuWidget(')):
        problems.append('TruMenu.cpp: PageSwitches tooltip must show both halves of the hint')
    # 1e costumes the game refuses
    pad = fn_body(src, 'DWORD WINAPI PadHook(')
    clk = pad[pad.find('if (clock != g_lastClock)'):]
    if 'CosValidTick();' not in clk or 'CosValidTick();' in fn_body(src, 'void Render('):
        problems.append('TruMenu.cpp: CosValidTick must run in the pad hook\'s once-per-game-frame block (game thread), '
                        'not in Render')
    cvt = fn_body(src, 'void CosValidTick(')
    if 'CosValidCall(' not in cvt or 'g_cosValidWant' not in cvt or '!same' not in cvt.replace('if (same) return;', '!same'):
        problems.append('TruMenu.cpp: CosValidTick must call the check only while the page is shown and the list changed')
    if 'kCostumeValid' not in fn_body(src, 'bool CosValidCall(') or any(t in cvt for t in Q217_WRITES[:5]):
        problems.append('TruMenu.cpp: CosValidCall = the game\'s check 0x5c54e0 only, CosValidTick writes nothing')
    cr = fn_body(src, 'int QbCosRows(')
    if 'CosOffered(g_cos.ids[i]) == 0' not in cr or 'g_cosValidWant' not in cr:
        problems.append('TruMenu.cpp: QbCosRows must mark the refused entries and ask CosValidTick for the check')
    act = fn_body(src, 'void QbCosAct(')
    cases = dict(re.findall(r'case (kQdCos[A-Za-z]*): \{?(.*?)(?=\n    case |\n    default:)', act, re.S))
    pick, one = cases.get('kQdCosPick', ''), cases.get('kQdCos', '')
    i_off, i_pend = pick.find('CosOffered(g_cos.ids[next]) != 0'), pick.find('g_cos.pending = true')
    if not (0 <= i_off < i_pend): problems.append('TruMenu.cpp: QbCosAct kQdCosPick must skip refused entries before it picks')
    i_ref, i_apply = one.find('CosOffered(static_cast<WORD>(q.intro)) == 0'), one.find('CosApply(')
    if not (0 <= i_ref < i_apply): problems.append('TruMenu.cpp: QbCosAct kQdCos must refuse a refused entry before CosApply')
    # 1f / 3 uber labels; 4 navmesh; 5 shader: read only, tables, INI keys
    for sec in Q217_SECTIONS:
        body = src[src.find('// ---- 0.21.7 %s' % sec):src.find('// ---- end of 0.21.7 %s' % sec)]
        if len(body) < 500: problems.append('TruMenu.cpp: section "0.21.7 %s" missing' % sec); continue
        for t in Q217_WRITES:
            if t in body: problems.append('TruMenu.cpp: section 0.21.7 %s calls %s (read only)' % (sec, t))
        if 'HexBytesAt(c.at, c.hex)' not in body: problems.append('TruMenu.cpp: section 0.21.7 %s has no byte-check loop' % sec)
    us = fn_body(src, 'DWORD UberStateOf(')
    for need in ('inst + 0x2d0', 'a + 0x2ec', 'u - 0x10', 'b + 0x70', 'kUbMagic'):
        if need not in us: problems.append('TruMenu.cpp: UberStateOf lacks %s (the engine path 0x4d5d59)' % need)
    if 'const DWORD kUbMagic = 0xf0012345;' not in src: problems.append('TruMenu.cpp: kUbMagic must be 0xf0012345')
    ut = fn_body(src, 'void UberText(')
    for need in ('cond != 1', 'tr + 0x1c', 'b + 0x88', 'b + 0x80', 'b + 0x8c', 'faehrt hoch', 'faehrt runter', 'noch %s'):
        if need not in ut: problems.append('TruMenu.cpp: UberText lacks %s' % need)
    opts = {(s, k): d for s, k, d, c in table(src)[1]}
    for key, want in Q217_KEYS.items():
        if opts.get(key) != want: problems.append('TruMenu.cpp: kOpts [%s] %s default must be %s (got %s)' % (key + (want,
                                                                                                    opts.get(key))))
        sec_rows = [(n, v) for n, k, v in ini_section(ini_path, key[0]) if k == key[1]]
        if len(sec_rows) != 1: problems.append('%s: [%s] %s missing' % ((name,) + key))
    if not all(float(opts.get(('Debug', 'UberRadius'), '0')) > g for g in Q217_GATES):
        problems.append('TruMenu.cpp: [Debug] UberRadius must reach the gates of the live test (%d / %d)' % Q217_GATES)
    sl = fn_body(src, 'ImU32 ShLabelText(')
    for need in ('ShLive(', 'kShStatusNames[fileStatus]', 'live = file', 'live %s %s %s'):
        if need not in sl: problems.append('TruMenu.cpp: ShLabelText must show file and live (lacks %s)' % need)
    lv = fn_body(src, 'bool ShLive(')
    for need in ('data + 0x28', 'ShLibId(', 'm->pc[k]', 'm->sur[k]', 'g_shFirstNew'):
        if need not in lv: problems.append('TruMenu.cpp: ShLive lacks %s (live lib ids per slot)' % need)
    nc = fn_body(src, 'int NlCollect(')
    for need in ('mask & (1ul << i)', 'layer + 0xc + 4 * k', 'g + 0x1c', 'head + 8', '0x38 + 0x14 * (flags & 0x7f)'):
        if need not in nc: problems.append('TruMenu.cpp: NlCollect lacks %s (the planner path)' % need)
    lg = fn_body(src, 'void NlLegend(')
    for need in ('gruen normal', 'rot Bit 27', 'orange +0x34 b8-11', 'gelb +0x34 b12-15', 'blau Bit 26 verschieden',
                 'magenta Bit 26', 'hellblau Kante 0x200'):
        if need not in lg: problems.append('TruMenu.cpp: NlLegend lacks "%s"' % need)
    items = item_types(src)
    for item, typ in Q217_ITEMS.items():
        mm = re.search(r'\{"%s", "%s", (?:"[^"]*"\s*)+,\s*(true|false),' % (re.escape(item), typ), src)
        if not mm: problems.append('TruMenu.cpp: item %s (%s) missing' % (item, typ))
        elif mm.group(1) != 'false': problems.append('TruMenu.cpp: %s must not be a game-thread item' % item)
        if not any(r[2] == item for r in rows): problems.append('TruMenu.cpp: item %s has no bar row' % item)
    render = fn_body(src, 'void Render(')
    for need in ('!LabelLayersOn()', 'if (g_ubOn) DrawUberLabels();', 'if (g_shOn) DrawShaderLabels();',
                 'if (g_nlOn) DrawNavLabels();'):
        if need not in render: problems.append('TruMenu.cpp: Render lacks %s' % need)
    if not (0 <= render.find('SapTick();') < render.find('!LabelLayersOn()')):
        problems.append('TruMenu.cpp: Render must call SapTick before its early return (the read-out runs without a draw)')
    sr = fn_body(src, 'bool SapRead(')
    for need in ('kSapMgr2', 'kSapVtbl', 'mgr + 0x18', 'core + 0x24', 'core + 0x2c', '1 + 204 * n + 16 * m', 'core + 0x28',
                 'ends != 2 * b', 'core + 0x30', 'p > 2 * m', 'u <= 1000'):
        if need not in sr: problems.append('TruMenu.cpp: SapRead lacks %s (the measuring plan of Befund-SweepAndPrune)' % need)
    st = open(os.path.join(ROOT, 'scripts', 'windows', 'Set-TruMenu.ps1'), encoding='utf-8-sig').read()
    if '5d6dd6301472d6139706af928b6673679b04d4c2941ef89fb69e6f0f631a14b4' not in st or 'TruMenu.shaderlabel.txt' not in st:
        problems.append('Set-TruMenu.ps1: the 0.21.6 build in $earlierBuilds / the shader label data install missing')
    # 2 chapter units
    if not re.search(r'QB_PAGE\("Kapitel \(debug\)", "Chapters \(debug\)", kQbChapters, kQsChapters\)', src):
        problems.append('TruMenu.cpp: page Kapitel must be kQsChapters (the units per chapter)')
    ub = src[src.index('const UnitRow kUnits[] = {'):]
    ub = ub[:ub.index('\n};')]
    groups = []
    for g in re.findall(r'\{"([^"]+)", "[^"]+", "[^"]+"\}', ub):
        if g not in groups: groups.append(g)
    unit_n = len(re.findall(r'\{"[^"]+", "[^"]+", "[^"]+"\}', ub))
    cg = re.search(r'const ChapGroup kChapGroups\[\] = \{(.*?)\n\};', src, re.S)
    ckeys = re.findall(r'\{"([^"]+)", "[^"]+", "[^"]+"\}', cg.group(1)) if cg else []
    if ckeys != groups: problems.append('TruMenu.cpp: kChapGroups keys %s != the groups of kUnits %s' % (ckeys, groups))
    biggest = max((len(re.findall(r'\{"%s", ' % re.escape(g), ub)) for g in groups), default=0)
    static_n = len([r for r in qb_rows(src) if r[0] == 'kQbChapters'])
    if static_n + len(groups) + biggest > 64:
        problems.append('TruMenu.cpp: page Kapitel with the biggest group open has %d rows > 64' % (static_n + len(groups) + biggest))
    qr = fn_body(src, 'int QbChapRows(')
    if '"level.load", kUnits[i].unit, kQbAction' not in qr or 'kQfConfirm | kQfBackup' not in qr:
        problems.append('TruMenu.cpp: a unit row must be level.load <unit> with kQfConfirm | kQfBackup (the chapter rows\' '
                        'path)')
    ca = fn_body(src, 'void QbChapAct(')
    if 'QbActRow(g_qbPage, r,' not in ca or any(t in ca for t in ('LoadUnit(', 'InvokeCore(', 'ShortcutStart(', 'QbRun(')):
        problems.append('TruMenu.cpp: QbChapAct must run a unit only through QbActRow (confirm, backup, one path)')
    if 'g_chapOpen = open ? g : -1' not in ca: problems.append('TruMenu.cpp: page Kapitel keeps one group open at a time')
    if 'besser DLC-2-Start + laufen' not in ca or '"DLC 2"' not in fn_body(src, 'bool ChapDlc2Note('):
        problems.append('TruMenu.cpp: the DLC 2 units need the note "besser DLC-2-Start + laufen"')
    if 'p.special == kQsChapters) QbSpecialAct(p.special, row - g_qbStaticN, kQbXDir)' not in fn_body(src, 'void QuickTick('):
        problems.append('TruMenu.cpp: QuickTick: X on page Kapitel must pass kQbXDir')
    # 1g pad diagnosis: log and footer only - QbPad (the only place that keeps bar buttons from the game) is unchanged
    qt = fn_body(src, 'void QuickTick(')
    if 'diagnosis 0.21.7' not in qt or 'g_padModeIdle && edges && !idleEdgeLogged' not in qt:
        problems.append('TruMenu.cpp: QuickTick must log the bar buttons pressed while PadHook is not called (diagnosis)')
    if 'diagnosis' in fn_body(src, 'WORD QbPad(') or 'g_qcOpen ? kQcOwn : 0' not in fn_body(src, 'WORD QbPad('):
        problems.append('TruMenu.cpp: the 0.21.7 pad diagnosis must not touch QbPad (the 0.21.6 cleared buttons stay)')
    if 'g_padModeIdle ? (de ? "   (Pad NICHT gesperrt)"' not in dq:
        problems.append('TruMenu.cpp: DrawQuick must warn while the pad is read past PadHook')
    return problems, '%d help rows, umlauts, costume check on the game thread, %d chapter groups / %d units, uber / shader / ' \
                     'navmesh layers read only with %d keys' % (len(helps), len(ckeys), unit_n, len(Q217_KEYS))


# 0.21.8 (2026-11-08 TruMenu 0.21.8, night build)
Q218_PATCHES = ((0x006203e4, 5), (0x006824b9, 5), (0x006826d3, 5), (0x0065b181, 6),   # TruShadowCombat 0.6.5 .text
                (0x0085b104, 4), (0x0085b0fc, 4), (0x0085b15c, 4), (0x00858c90, 4), (0x00859160, 4))   # .. vtable slots
Q218_RV_SAP = {0x005be3a7: '68f401000068b80b0000', 0x005be3bd: 'c74618e8030000c74620f4010000'}   # TruRockVein 0.10
Q218_DANGER = ('cheat.', 'player.invincible', 'player.die', 'level.load', 'level.start', 'level.reload', 'unit.go',
               'pos.goload', 'save.load', 'save.delete', 'save.restore', 'save.import', 'costume.reset',
               'costume.choosereset', 'costume.setreload', 'costume.choosereload', 'sw.set', 'sticky.set', 'game.quit')
Q218_SG_KEYS = ('Ambience', 'Steps', 'Weapons', 'Enemies', 'Lara', 'Objects', 'Dlc2', 'Hud')
Q218_SG_GROUPS = {'Ambience': [15], 'Steps': [32, 78], 'Weapons': [58, 60, 51, 31], 'Enemies': [27, 65],
                  'Lara': [68, 70, 72, 77], 'Objects': [43], 'Dlc2': [79], 'Hud': [54, 55, 56, 57]}   # finding section 4
Q218_STORY = ('kH2KeyPopulation', 'kH2KeyDeaths', 'kH2KeyTutorial', 'kH2KeyBroken')


def check_0218(ini_path, switches_path):
    """0.21.8: the byte check moved off TruShadowCombat 0.6.5's patch sites, the SweepAndPrune rows accept TruRockVein
    0.10's form, the quick command line (suggestions, the one on-screen keyboard with a target, history line shown,
    kCmdDanger asks twice), favourites with an argument + star, story values (read only), sound group sliders"""
    problems = []
    src = read_cpp()
    # 0.21.9: the version line keeps the 0.21.8 part (as check_0217 reads its own part)
    if not src.startswith('//') or '0.21.8 (quick command line' not in src[:src.find('\n', src.find('kVersion = '))]:
        problems.append('TruMenu.cpp: kVersion must hold the 0.21.8 part "0.21.8 (quick command line"')
    # 1 byte checks vs the patch sites of TruShadowCombat 0.6.5
    joined = re.sub(r'"\s*\n\s*"', '', src)
    rows = [(int(a, 16), len(re.sub(r'[^0-9a-fA-F]', '', h)) // 2) for a, h in
            re.findall(r'\{\s*(0x[0-9a-fA-F]{6,8})\s*,\s*"([0-9a-fA-F ]+)"', joined)]
    for site, ln in Q218_PATCHES:
        for a, n in rows:
            if a < site + ln and site < a + n:
                problems.append('TruMenu.cpp: byte check 0x%08x (+%d) covers the TruShadowCombat 0.6.5 patch 0x%08x (+%d) '
                                '- it would fail once that plugin has run' % (a, n, site, ln))
    ak = re.search(r'const DvCheck kAkChecks\[\] = \{(.*?)\n\};', src, re.S)
    if not ak or '{0x006203e9, "83c410 84c0 7417"}' not in ak.group(1):
        problems.append('TruMenu.cpp: kAkChecks must check the bytes after the call: {0x006203e9, "83c410 84c0 7417"}')
    # SweepAndPrune: the TruRockVein 0.10 form accepted for the same rows (and only there)
    tu = re.search(r'const NavCheckBytes kSapChecksTu\[\] = \{(.*?)\n\};', src, re.S)
    got = dict((int(a, 16), h.replace(' ', '')) for a, h in re.findall(r'\{(0x[0-9a-f]{8}), "([0-9a-f ]+)"\}', tu.group(1))) \
        if tu else {}
    if got != Q218_RV_SAP:
        problems.append('TruMenu.cpp: kSapChecksTu must hold exactly the TruRockVein 0.10 form of 0x5be3a7 / 0x5be3bd')
    sap = re.search(r'const NavCheckBytes kSapChecks\[\] = \{(.*?)\n\};', src, re.S)
    if not sap or '{0x005be3a7, "68c800000068e8030000"}' not in sap.group(1) or \
            '{0x005be3bd, "c74618e8030000c74620c8000000"}' not in sap.group(1):
        problems.append('TruMenu.cpp: kSapChecks must keep the retail rows (= precheck_0217_sap.txt)')
    sc = fn_body(src, 'void SapCheck(')
    if 'kSapChecksTu' not in sc or 't.at == c.at' not in sc:
        problems.append('TruMenu.cpp: SapCheck must accept the kSapChecksTu form only for the same row')
    if 'Grenzen %s' not in fn_body(src, 'void ValSap(') or 'g_sap.n == 3000 && g_sap.m2 == 1000' not in fn_body(src, 'void ValSap('):
        problems.append('TruMenu.cpp: ValSap must name the limits read from the core (PC 1000/400, TU 3000/1000)')
    stext = open(switches_path, encoding='utf-8', errors='replace').read()
    if 'TruRockVein | SweepAndPrune | Translate | bool |' not in stext:
        problems.append('%s: row TruRockVein [SweepAndPrune] Translate missing' % os.path.basename(switches_path))
    # 2a suggestions under the small line: the menu bar's list and rows
    qc = src[src.find('// ---- 0.21.6 quick command line'):src.find('// ---- end of 0.21.6 quick command line')]
    if 'CmdBuildSuggestions(g_qcBuf, false)' not in qc or 'CmdSugRows(' not in qc:
        problems.append('TruMenu.cpp: the quick command line must show CmdBuildSuggestions(g_qcBuf) with CmdSugRows')
    if 'CmdSugRows(10)' not in fn_body(src, 'void DrawCmdSuggestions('):
        problems.append('TruMenu.cpp: DrawCmdSuggestions must draw its rows with CmdSugRows (one list look)')
    # 2b one keyboard with a target
    if src.count('\nvoid DrawOsk(') != 1 or src.count('\nvoid OskInput(') != 1 or 'struct OskTarget {' not in src:
        problems.append('TruMenu.cpp: exactly one on-screen keyboard (DrawOsk / OskInput) with an OskTarget')
    for head in ('void OskAppend(', 'void OskBackspace(', 'void OskTakeSuggestion(', 'void OskRun(', 'void OskActivate(',
                 'void OskInput(', 'void DrawOsk('):
        if 'g_cmdBuf' in fn_body(src, head) or 'g_oskOpen' in fn_body(src, head):
            problems.append('TruMenu.cpp: %s...) must edit the target (g_osk), not the menu bar' % head)
    if 'DrawOsk(g_oskQc)' not in qc or 'OskInput(g_oskQc, e)' not in qc or 'DrawOsk(g_oskMenu)' not in \
            fn_body(src, 'void DrawCmdBar('):
        problems.append('TruMenu.cpp: the menu bar (g_oskMenu) and the quick command line (g_oskQc) must use the keyboard')
    if 'g_osk = &g_oskMenu;' not in fn_body(src, 'void DrawCmdBar('):
        problems.append('TruMenu.cpp: DrawCmdBar must set the keyboard target first')
    if 'const WORD kQcOskOwn = 0x0010;' not in src or 'down & ~s.passed & ~qcOsk' not in fn_body(src, 'WORD QbPad(') or \
            'kQcOskOwn' not in fn_body(src, 'extern "C" __declspec(dllexport) DWORD __cdecl TruMenuPadBlock('):
        problems.append('TruMenu.cpp: Start must be kept from the game (never a gated tap) while the line\'s keyboard is open')
    # 2c history safety
    m = re.search(r'const CmdDanger kCmdDanger\[\] = \{(.*?)\n\};', src, re.S)
    dids = re.findall(r'\{"([a-z0-9_.]+)", "', m.group(1)) if m else []
    for d in Q218_DANGER:
        if d not in dids: problems.append('TruMenu.cpp: kCmdDanger lacks %s' % d)
    dg = fn_body(src, 'const CmdDanger *CmdDangerOf(')
    for need in ('kCkInfo', 'kCkBuiltin', 'CmdIsValue(k) && !arg[0]', 'CmdCanonical('):
        if need not in dg: problems.append('TruMenu.cpp: CmdDangerOf lacks %s (reads are never dangerous)' % need)
    run = fn_body(src, 'void QcRun(')
    i_d, i_r = run.find('CmdDangerOf(line)'), run.find('CmdRunLine(')
    if not (0 <= i_d < i_r) or 'pad ? CmdDangerOf(line)' not in run or 'QcArmed()' not in run:
        problems.append('TruMenu.cpp: QcRun must arm a kCmdDanger pad run before CmdRunLine')
    if 'const DWORD kQcArmMs = 3000;' not in src:
        problems.append('TruMenu.cpp: kQcArmMs must be 3000 (the owner: "a second A within 3 s")')
    pt = fn_body(src, 'bool QcPadTick(')
    if 'QcRun(true)' not in pt or 'QcRun(false)' not in fn_body(src, 'void DrawQuickCmd(') or 'QcRun(true)' not in \
            fn_body(src, 'void QcOskRun('):
        problems.append('TruMenu.cpp: pad runs (A, the keyboard\'s Start) must be QcRun(true), Enter QcRun(false)')
    dq = fn_body(src, 'void DrawQuickCmd(')
    if '"A fuehrt aus:"' not in dq or 'g_qcHistPos >= 0 || osk' not in dq or 'ACHTUNG: %s' not in dq:
        problems.append('TruMenu.cpp: DrawQuickCmd must show the picked line before A and the armed warning')
    # 3a favourites with an argument + star
    ok = fn_body(src, 'bool FavArgOk(')
    if "arg[i] == ','" not in ok or "arg[i] == '|'" not in ok or 'kFavArgMax' not in ok:
        problems.append('TruMenu.cpp: FavArgOk must refuse "," and "|" and long arguments')
    fe = src[src.find('template <typename F> void ForFavEntries('):]
    fe = fe[:fe.find('\n}\n') + 3]
    if "strchr(e, '|')" not in fe or '" \\t"' not in fe:
        problems.append('TruMenu.cpp: ForFavEntries must read "<id>|<argument>" and the old space-separated ids')
    if 'full = true' not in fn_body(src, 'bool FavSetArg(') or 'never write a cut list' not in fn_body(src, 'bool FavSetArg('):
        problems.append('TruMenu.cpp: FavSetArg must refuse a list that does not fit (no cut write)')
    fr = fn_body(src, 'int QbFavRows(')
    if 'ForFavEntries(' not in fr or 'QbSwView(i, v[n], d[n], de)' not in fr or 'kQfConfirm | kQfBackup' not in fr:
        problems.append('TruMenu.cpp: QbFavRows must show entries with an argument (switch row, level.load with backup)')
    pin = fn_body(src, 'void QbFavPin(')
    if 'QbDynFav(dyn' not in pin or 'FavSetArg(dynId, dynArg' not in pin:
        problems.append('TruMenu.cpp: QbFavPin must pin the special rows QbDynFav names')
    dyn = fn_body(src, 'bool QbDynFav(')
    for need in ('kQdSw', 'kQdCos', 'kQdChap', '"sw.set"', '"costume.set"', '"level.load"'):
        if need not in dyn: problems.append('TruMenu.cpp: QbDynFav lacks %s' % need)
    if 'QbMarkFavs(page);' not in fn_body(src, 'void QbBuild(') or 'if (v.fav)' not in fn_body(src, 'void DrawQuick('):
        problems.append('TruMenu.cpp: the star: QbBuild must mark the favourites, DrawQuick draw " *"')
    if 'RunFavArg(arg, true' not in src or 'FavSetArg(id, arg, false' not in fn_body(src, 'void PageFavourites('):
        problems.append('TruMenu.cpp: fav.add / fav.del and the menu page must handle entries with an argument')
    # 3b story values: read only
    sv = fn_body(src, 'void ValStoryValues(')
    m = re.search(r'const StoryVal kStoryVals\[\] = \{(.*?)\n\};', src, re.S)
    for k in Q218_STORY:
        if not m or k not in m.group(1): problems.append('TruMenu.cpp: kStoryVals lacks %s (hall02)' % k)
    if 'StFind(0, s.owner' not in sv or any(t in sv for t in ('StNotify', 'kStNotify', 'WriteDword(', 'PutByte(', 'QueueItem(')):
        problems.append('TruMenu.cpp: ValStoryValues must only read (StFind / StValue)')
    if '{"story.values", "info"' not in src:
        problems.append('TruMenu.cpp: item story.values (info) missing')
    # 3c sound group sliders
    sg = src[src.find('// ---- 0.21.8 sound group sliders'):src.find('// ---- end of 0.21.8 sound group sliders')]
    sl = re.findall(r'\{"([A-Za-z0-9]+)", "[^"]*", "[^"]*", \{([0-9, ]+)\}, (\d)\}', sg)
    have = {k: [int(x) for x in g.split(',')][:int(c)] for k, g, c in sl}
    if have != Q218_SG_GROUPS:
        problems.append('TruMenu.cpp: kSgSliders must be the finding\'s eight sliders (%s)' % have)
    tick = fn_body(src, 'void SgTick(')
    if 'SgCovered(s, s.groups[k])' not in tick or 'st.orig' not in tick or '* 0x84' in tick:
        problems.append('TruMenu.cpp: SgTick must skip covered groups, restore the old factor, never write the game volume')
    wr = fn_body(src, 'bool SgWrite(')
    if 'cg + 0x38' not in wr or 'kFmCgUpdateVol' not in wr or '__try' not in wr:
        problems.append('TruMenu.cpp: SgWrite = cg + 0x38 then FMOD\'s recompute 0x7c4774 under __try')
    if 'SgTick();' not in src[src.find('        SndMuteTick();'):src.find('        SndMuteTick();') + 200]:
        problems.append('TruMenu.cpp: SgTick must run on the game thread next to SndMuteTick')
    if 'g_sgOk = g_smOk && DvChecks(kSgChecks' not in fn_body(src, 'void SgCheck(') or 'SgCheck();' not in src:
        problems.append('TruMenu.cpp: SgCheck must gate the sliders on the 0.20.1 group checks and kSgChecks')
    ini = {k: v for _, k, v in ini_section(ini_path, 'SoundGroups')}
    for k in Q218_SG_KEYS:
        if ini.get(k) != '100': problems.append('%s: [SoundGroups] %s must be 100 (got %s)' % (os.path.basename(ini_path), k,
                                                                                           ini.get(k)))
        item = 'snd.vol.%s' % k.lower()
        if '{"%s", "int"' % item not in src: problems.append('TruMenu.cpp: item %s (int) missing' % item)
        if '"%s", "", kQbValue, -1, kQcNone, kQvSndGroup' % item not in src:
            problems.append('TruMenu.cpp: bar value row for %s (kQvSndGroup) missing' % item)
    if 'r.val == kQvSndGroup ? (SgPctAt(r.id) + 5) / 10' not in fn_body(src, 'void QbActRow('):
        problems.append('TruMenu.cpp: QbActRow must step a sound group row from its item')
    return problems, 'byte check 0x6203e9, 0 checks on the 0.6.5 sites, SAP both forms, %d danger ids, one keyboard, ' \
                     'favourites with arguments, %d story values, %d sound sliders' % (
                         len(dids), len(re.findall(r'\n    \{', m.group(1))) if m else 0, len(have))


Q02213_FT_NEW = ('pc_ring_bits', 'pc_hud_g12', 'pc_ret_style', 'pc_ret40', 'pc_drip_q10706', 'pc_drip_q10707', 'pc_drip_n',
                 'pc_drip_near_x', 'pc_drip_near_y', 'pc_drip_near_z', 'pc_drip_near_dxy', 'pc_drip_near_dz',
                 'pc_drip_near_iflags', 'pc_drip_near_node', 'pc_lara_dmg')
Q02213_FT_OLD_LAST = 'pc_ramp_last'      # the 0.22.11 header ended here (TruXenia order first, then the PC columns)


def check_02213():
    """0.22.13: cutscene pad combos (sub-combos on release, the photo at once), the subtitle line clock held with the
    pause (data patch at 0x583f24, byte checks), sub.lang calls the settings save 0x478010 (byte checks, __try), the enemy
    panel text "Kampf-Spur: an (n Zeilen)", ring.bits = an info item (read only), the new fight.trace columns at the end
    (header and format agree), no hook on 0x637590 (TruShadowCombat's site), no check on TruShadowPower's 0x71e979"""
    problems = []
    src = read_cpp()
    # 1 pad combos
    pt = fn_body(src, 'void CnPadTick(')
    if 'CnPadIsSub(i)' not in pt or 'g_cnPadPeak' not in pt or 'peak == m && active' not in pt:
        problems.append('TruMenu.cpp: CnPadTick must fire a sub-combo on release only when the peak is exactly its set')
    if '!CnPadIsSub(i)' not in pt or 'held == g_cnPadMask[i]' not in pt:
        problems.append('TruMenu.cpp: CnPadTick must fire a combo that is part of no other at once (exactly its buttons)')
    sub = fn_body(src, 'bool CnPadIsSub(')
    if '(g_cnPadMask[j] & m) == m' not in sub:
        problems.append('TruMenu.cpp: CnPadIsSub must test "inside a larger combo"')
    # 2 subtitle clock
    if '{0x00583f1c, "d98308020000 d82588f1e700' not in src or 'const DvCheck kCnSubChecks[] = {' not in src:
        problems.append('TruMenu.cpp: kCnSubChecks must check the subtitle countdown 0x583f1c (fsub [0xe7f188])')
    if '{0x00583f24, kCnSubDtGame, false, "N3 subtitle clock 0x583f24"' not in src:
        problems.append('TruMenu.cpp: g_cnSubPatch must be the disp32 at 0x583f24 (data patch, not a call)')
    tick = fn_body(src, 'void CnTick(')
    i_v, i_p = tick.find('g_cnSubDt = dt;'), tick.find('M21PatchGroup(g_cnSubPatch, 1, g_cnSubOk && g_cnOn')
    if not (0 <= i_v < i_p):
        problems.append('TruMenu.cpp: CnTick must set g_cnSubDt before it patches, and patch only with the walk (g_cnOn)')
    if 'CnHeldNow() && !g_cnStepping' not in tick:
        problems.append('TruMenu.cpp: the subtitle clock stands only while held and not stepping')
    # 3 settings save
    sv = fn_body(src, 'bool SbSave(')
    if 'kSbSaveChecks' not in sv or '__try' not in sv or '0x00478010' not in sv or '0x00ad75e4' not in sv:
        problems.append('TruMenu.cpp: SbSave must byte-check 0x478010, test [0xad75e4] and call it under __try')
    if 'SbSave(saved, sizeof(saved))' not in fn_body(src, 'bool RunSb('):
        problems.append('TruMenu.cpp: RunSb must call SbSave after the option setter')
    if not re.search(r'\{"sub\.lang", "action", .*?true, ValSb, RunSb\}', src, re.S):
        problems.append('TruMenu.cpp: sub.lang must stay a game-thread item (the save runs there)')
    # 4 enemy panel text
    ep = re.sub(r'//[^\n]*', '', fn_body(src, 'void DrawEnemyPanel('))
    if '"Kampf-Spur: an (%ld Zeilen)"' not in ep or '"Fight trace: on (%ld lines)"' not in ep or 'Kampf-Spur: Zeilen' in ep:
        problems.append('TruMenu.cpp: DrawEnemyPanel must say "Kampf-Spur: an (n Zeilen)" / "Fight trace: on (n lines)"')
    # 5 ring.bits: an info item, read only
    if '{"ring.bits", "info",' not in src or 'false, ValRg, nullptr}' not in src:
        problems.append('TruMenu.cpp: ring.bits must be an info item without a runner')
    rg = src[src.find('// ---- 0.22.13 ring bits'):src.find('// ---- 0.22.13 goo drips')]
    if not rg or any(t in rg for t in ('WriteDword(', 'WriteBytes(', 'PutByte(', 'QueueItem(')):
        problems.append('TruMenu.cpp: the ring bit section must only read')
    code = re.sub(r'//[^\n]*', '', rg)
    if any(a in code for a in ('0x0071e979', '0x00715026', '0x00716f5f')):
        problems.append('TruMenu.cpp: no run-time byte check on TruShadowPower\'s patch sites 0x71e979 / 0x715026 / 0x716f5f')
    if '"Ziel-Ring: Bits (live)", "Target ring: bits (live)", "ring.bits", "", kQbInfo' not in src:
        problems.append('TruMenu.cpp: bar row "Ziel-Ring: Bits (live)" (info) missing')
    # 6 fight.trace columns: the old header unchanged, new columns at the end, the format has one field per column
    m = re.search(r'const char \*const kFtHeader = (.*?);\r?\n', src, re.S)
    head = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))).replace('\\t', '\t').replace('\\n', '\n') if m else ''
    cols = head.rstrip('\n').split('\t')
    if Q02213_FT_OLD_LAST not in cols or tuple(cols[cols.index(Q02213_FT_OLD_LAST) + 1:]) != Q02213_FT_NEW or \
            cols[:3] != ['host_time', 'inst', 'obj_id']:
        problems.append('TruMenu.cpp: kFtHeader must keep the TruXenia order and end with %s' % ', '.join(Q02213_FT_NEW))
    wr = fn_body(src, 'void FtWrite(')
    fm = re.search(r'_snprintf_s\(line, sizeof\(line\), _TRUNCATE,\s*((?:"[^"]*"\s*)+),', wr)
    fmt = ''.join(re.findall(r'"([^"]*)"', fm.group(1))) if fm else ''
    fields = fmt.count('\\t') + 1 if fmt else 0
    if fields != len(cols):
        problems.append('TruMenu.cpp: FtWrite writes %d fields, kFtHeader has %d columns' % (fields, len(cols)))
    ft = fn_body(src, 'void FtTick(')
    if 'FtDripRead(w.pos, w.drip)' not in ft or 'w.drip.zone' not in ft:
        problems.append('TruMenu.cpp: FtTick must read the goo drips (FtDripRead) and write a line every sample in the zone')
    dr = fn_body(src, 'void FtDripRead(')
    if 'oid == 926' not in dr or 'intro == 10706 || intro == 10707' not in dr or 'oid == 929 || oid == 942' not in dr or \
            '2500.0f * 2500.0f' not in dr:
        problems.append('TruMenu.cpp: FtDripRead must use the finding\'s sources 10706 / 10707 (926), copies 929 / 942, 2500')
    look = fn_body(src, 'void FtDmgLook(')
    if 'HexBytesAt(0x00637590' not in look or re.search(r'Write(Bytes|Dword)\(\s*0x00637590', src):
        problems.append('TruMenu.cpp: 0x637590 must only be looked at (TruShadowCombat hooks it), never written')
    return problems, 'pad sub-combos on release, subtitle clock 0x583f24, settings save 0x478010, panel text, ring.bits ' \
                     'info, %d fight.trace columns (%d new at the end)' % (len(cols), len(Q02213_FT_NEW))


def unescape(s):
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')


def check_02214():
    """0.22.14: sub.lang rewrites the shown subtitle lines at once - the two call patches 0x4574ec (reader) and 0x453a17
    (box add line) with their byte checks, a ring of 2 whole records (copied, not a pointer), the rewrite only after the
    option setter and the settings save, the box written only at +0 / +0x100 (never the clock +0x208 or the floats)"""
    problems = []
    src = read_cpp()
    a, b = src.find('// ---- 0.22.14 sub.lang switches'), src.find('\nbool RunSb(')
    sec = src[a:b] if 0 <= a < b else ''
    if not sec:
        return ['TruMenu.cpp: section "0.22.14 sub.lang switches" missing (before RunSb)'], ''
    for want in ('{0x004574ec, 0x004538d0, true, "S1 subtitle reader call 0x4574ec"',
                 '{0x00453a17, 0x00583db0, true, "S2 subtitle box add call 0x453a17"',
                 '{0x004574de, "68a0cf9c00 8bce c683a0cf9c0000 e8dfc3ffff"}', '{0x00453a0f, "6a5a 50 b9c0decc00 e894031300"}',
                 '{0x00453a75, "c20400"}', '{0x00583e15, "c20800"}', 'const int kSrRing = 2'):
        if want not in sec:
            problems.append('TruMenu.cpp: 0.22.14 section must hold %s' % want)
    rd = fn_body(src, 'void __fastcall SrReader(')
    if 'r.text[i] = text[i]' not in rd or '__try' not in rd or 'reinterpret_cast<SrReaderFn>(0x004538d0)' not in rd:
        problems.append('TruMenu.cpp: SrReader must copy the whole record under __try, then call the reader 0x4538d0')
    tk = fn_body(src, 'void SrTick(')
    if not (0 <= tk.find('CnCheck();') < tk.find('SrCheck()') < tk.find('M21PatchGroup(g_srPatches')):
        problems.append('TruMenu.cpp: SrTick must run CnCheck (reads 0x4574ec) and SrCheck before it patches')
    code = re.sub(r'//[^\n]*', '', fn_body(src, 'void SrRewrite('))
    if 'WriteBytes(at, buf, len + 1)' not in code or 'strnlen_s(want[s], 0xff)' not in code:
        problems.append('TruMenu.cpp: SrRewrite must write each box line with its NUL, at most 0xff bytes')
    if re.search(r'kSrBox \+ 0x20[048]', code) or 'WriteDword(' in code:
        problems.append('TruMenu.cpp: SrRewrite must not touch the clock +0x208 or the floats +0x200 / +0x204')
    rs = fn_body(src, 'bool RunSb(')
    i_set, i_save, i_rw = rs.find('0x005d5100'), rs.find('SbSave(saved'), rs.find('SrRewrite(v,')
    if not (0 <= i_set < i_save < i_rw):
        problems.append('TruMenu.cpp: RunSb must rewrite the box after the option setter and the settings save')
    if 'SrTick();' not in fn_body(src, 'DWORD WINAPI PadHook('):
        problems.append('TruMenu.cpp: SrTick must run once per game frame (PadHook)')
    return problems, 'record ring (2 whole records), calls 0x4574ec / 0x453a17, rewrite after setter + save, box +0 / ' \
                     '+0x100 only'


def check_02215():
    """0.22.15: aim.trace / aim.why read the lock-on path only - 25 byte checks (kAmChecks) behind AmCheck (which also
    needs the ring.bits and chart checks), no write into game memory and no game call in the section, the TruAim.log
    header has as many columns as AmBody writes, both items in kOpts, bar rows on page Tests next to ring.bits, AmTick
    once per game frame"""
    problems = []
    src = read_cpp()
    a, b = src.find('// ---- 0.22.15 aim.trace / aim.why'), src.find('\nvoid ValFt(')
    sec = src[a:b] if 0 <= a < b else ''
    if not sec:
        return ['TruMenu.cpp: section "0.22.15 aim.trace / aim.why" missing (before ValFt)'], ''
    tab = sec[sec.find('const DvCheck kAmChecks[] = {'):]
    tab = tab[:tab.find('\n};')]
    n_checks = len(re.findall(r'\{0x[0-9a-f]{8}, "', tab))
    if n_checks != 25:
        problems.append('TruMenu.cpp: kAmChecks must hold 25 byte checks (has %d)' % n_checks)
    for want in ('{0x006f2800, "53 8b1d58dbfa00 8b8300050000 56 8bb034010000 83fe0c"}',
                 '{0x0072170a, "a164d7fa00 0fb69094020000"}', '{0x00484c32, "c7460404000000"}',
                 '{0x007216b0, "83ec08 55 8be9 f785fc01000000000400"}', '{0x0071d97d, "898f90000000"}',
                 'g_amOk = RgCheck() && CtCheck() && DvChecks(kAmChecks'):
        if want not in sec:
            problems.append('TruMenu.cpp: 0.22.15 section must hold %s' % want)
    code = re.sub(r'//[^\n]*', '', sec)
    for bad in ('WriteDword(', 'WriteBytes(', 'WriteByte(', 'VirtualProtect(', '__asm', 'Fn>(0x00'):
        if bad in code:
            problems.append('TruMenu.cpp: the 0.22.15 section must stay read only (found %s)' % bad)
    hdr = re.search(r'kAmHeader = ((?:"[^"]*"\s*)+);', sec)
    cols = ''.join(re.findall(r'"([^"]*)"', hdr.group(1))).replace('\\t', '\t').replace('\\n', '').split('\t') if hdr else []
    body = fn_body(src, 'void AmBody(')
    fmt = re.search(r'Out\(o, n, ((?:"[^"]*"\s*)+),', body)
    nfmt = len(re.findall(r'%[-0-9.]*l?[dusxf]', ''.join(re.findall(r'"([^"]*)"', fmt.group(1))))) if fmt else -1
    # the line = host_time + AmBody's fields; the four bucket counts %lu/%lu/%lu/%lu are one column (t0_buckets)
    if not cols or len(cols) - 1 != nfmt - 3:
        problems.append('TruMenu.cpp: TruAim.log header has %d columns, AmBody writes %d' % (len(cols), nfmt - 3 + 1))
    for item in ('{"aim.trace", "bool",', '{"aim.why", "info",'):
        if item not in src:
            problems.append('TruMenu.cpp: kOpts needs %s' % item)
    rows = src.find('"ring.bits", "", kQbInfo')
    if rows < 0 or src.find('"aim.trace", "", kQbBool', rows) < 0 or src.find('"aim.why", "", kQbInfo', rows) < 0:
        problems.append('TruMenu.cpp: bar rows aim.trace (bool) / aim.why (info) must follow ring.bits on page Tests')
    if 'AmTick();' not in fn_body(src, 'DWORD WINAPI PadHook('):
        problems.append('TruMenu.cpp: AmTick must run once per game frame (PadHook)')
    return problems, '%d byte checks, read only, %d TruAim.log columns, items + bar rows, AmTick per frame' % (
        n_checks, len(cols))


def table(src):
    block = src[src.index('const OptDef kOpts[] = {'):]
    block = block[:block.index('\n};')]
    rows = []
    for entry in re.findall(r'\{("(?:[^{}])*?)\},', block, re.S):
        lits = [unescape(x) for x in LIT.findall(entry)]
        rows.append((lits[0], lits[1], lits[2], ''.join(lits[3:])))
    header = unescape(LIT.search(src[src.index('kIniHeader ='):]).group(1))
    return header, rows


def text(header, rows):
    out = ['; %s\n' % header]
    section = None
    for sec, key, default, comment in rows:
        if sec != section:
            out.append(('\n[%s]\n' if section else '[%s]\n') % sec)
            section = sec
        for line in comment.split('\n'):
            if line: out.append('; %s\n' % line)
        out.append('%s=%s\n' % (key, default))
    return ''.join(out)


def main(argv):
    global CPP
    if '--cpp' in argv[:-1]: CPP = argv[argv.index('--cpp') + 1]   # 0.19: negative tests on a copy of TruMenu.cpp
    header, rows = table(read_cpp())
    want = text(header, rows)
    if argv and argv[0] == '--print':
        sys.stdout.write(want)
        return 0
    opt = {k: argv[i + 1] for i, k in enumerate(argv[:-1]) if k in ('--ini', '--radial', '--tour', '--switches')}
    ini_path = opt.get('--ini', INI)
    problems, summary = check_lists()
    for p in problems: print('LIST %s' % p)
    if not problems: print('ok: regression lists (%s)' % ', '.join(summary))
    radial_path = opt.get('--radial', RADIAL)
    rproblems, rsummary, rlevels = check_radial(radial_path, os.path.basename(radial_path))   # 0.10
    for p in rproblems: print('RADIAL %s' % p)
    if not rproblems: print('ok: radial menu file (%s)' % rsummary)
    problems += rproblems
    tour_path = opt.get('--tour', TOUR)       # 0.10.1
    tproblems, tsummary, tlevels = check_radial(tour_path, os.path.basename(tour_path), '# TruMenu tour')
    for p in tproblems: print('TOUR %s' % p)
    if not tproblems: print('ok: tour file (%s, below Tests/Rundgang)' % tsummary)
    problems += tproblems
    bproblems, bsummary = check_builtins(rows, rlevels, tlevels)
    for p in bproblems: print('RADIAL %s' % p)
    if not bproblems: print('ok: %s' % bsummary)
    problems += bproblems
    vproblems = check_ini_values(ini_path)
    for p in vproblems: print('INI %s' % p)
    if not vproblems: print('ok: [Radial] Mode / Freeze / QuitSector / TestsLevel / FreezeSound / FreezeShaderClock values')
    problems += vproblems
    sproblems, ssummary = check_shot(ini_path, radial_path)   # 0.10.5
    for p in sproblems: print('SHOT %s' % p)
    if not sproblems: print('ok: [Shot] Enabled / Folder / Clean / Hotkey / MaxPerMinute values, shot items + exports, %s'
                            % ssummary)
    problems += sproblems
    fproblems = check_flow(ini_path)          # 0.11
    for p in fproblems: print('FLOW %s' % p)
    if not fproblems: print('ok: [Flow] Enabled / File / Overlay / Position / Size / Lines / AutoAdvance / ToastSeconds / '
                            'PollMs values, %d flow items, TruFlowCore.h included' % len(FLOW_ITEMS))
    problems += fproblems
    dproblems, dsummary = check_debug(ini_path, radial_path)   # 0.12
    for p in dproblems: print('DEBUG %s' % p)
    if not dproblems: print('ok: [Debug] Enabled / NavDraw / NavMask values, %d nav items, %s' % (len(NAV_ITEMS), dsummary))
    problems += dproblems
    qproblems, qsummary = check_quick(ini_path, radial_path)   # 0.17
    for p in qproblems: print('QUICK %s' % p)
    if not qproblems: print('ok: [Quick] / [Shot] OnCine* / CheckpointHide values, %s, ring entries' % qsummary)
    problems += qproblems
    eproblems, esummary = check_018(ini_path, radial_path)   # 0.18
    for p in eproblems: print('Q018 %s' % p)
    if not eproblems: print('ok: 0.18 keys / items / bar pages: %s' % esummary)
    problems += eproblems
    aproblems, asummary = check_019(ini_path, radial_path, rows)   # 0.19
    for p in aproblems: print('Q019 %s' % p)
    if not aproblems: print('ok: 0.19 dumb AI: %s' % asummary)
    problems += aproblems
    zproblems, zsummary = check_020(ini_path, radial_path, rows)   # 0.20
    for p in zproblems: print('Q020 %s' % p)
    if not zproblems: print('ok: 0.20: %s' % zsummary)
    problems += zproblems
    xproblems, xsummary = check_021(ini_path, radial_path, rows)   # 0.21
    for p in xproblems: print('Q021 %s' % p)
    if not xproblems: print('ok: 0.21 arachnophobia / camera / ai.remove: %s' % xsummary)
    problems += xproblems
    wproblems, wsummary = check_0211(ini_path, radial_path, rows)   # 0.21.1
    for p in wproblems: print('Q0211 %s' % p)
    if not wproblems: print('ok: 0.21.1 ai.kill / sticky / room check / physics / spawn / bar: %s' % wsummary)
    problems += wproblems
    tproblems3, tsummary3 = check_0213(ini_path)   # 0.21.3
    for p in tproblems3: print('Q0213 %s' % p)
    if not tproblems3: print('ok: 0.21.3 quick bar X / Y, sound list width: %s' % tsummary3)
    problems += tproblems3
    hproblems, hsummary = check_0214(ini_path, rows)   # 0.21.4
    for p in hproblems: print('Q0214 %s' % p)
    if not hproblems: print('ok: 0.21.4 hall02 counter: %s' % hsummary)
    problems += hproblems
    fproblems5, fsummary5 = check_0215(radial_path, opt.get('--switches', SWITCHES))   # 0.21.5
    for p in fproblems5: print('Q0215 %s' % p)
    if not fproblems5: print('ok: 0.21.5 Fixes + frozen ring: %s' % fsummary5)
    problems += fproblems5
    gproblems6, gsummary6 = check_0216(ini_path)   # 0.21.6
    for p in gproblems6: print('Q0216 %s' % p)
    if not gproblems6: print('ok: 0.21.6 costumes / flight line / quick command line: %s' % gsummary6)
    problems += gproblems6
    gproblems7, gsummary7 = check_0217(ini_path, opt.get('--switches', SWITCHES))   # 0.21.7
    for p in gproblems7: print('Q0217 %s' % p)
    if not gproblems7: print('ok: 0.21.7 footer / help / umlauts / costumes / chapters / label layers: %s' % gsummary7)
    problems += gproblems7
    gproblems8, gsummary8 = check_0218(ini_path, opt.get('--switches', SWITCHES))   # 0.21.8
    for p in gproblems8: print('Q0218 %s' % p)
    if not gproblems8: print('ok: 0.21.8 checks / command line / favourites / story / sound groups: %s' % gsummary8)
    problems += gproblems8
    nproblems, nsummary = check_0201(ini_path, radial_path)   # 0.20.1
    for p in nproblems: print('Q0201 %s' % p)
    if not nproblems: print('ok: 0.20.1 sound list: %s' % nsummary)
    problems += nproblems
    cproblems13, csummary13 = check_02213()   # 0.22.13
    for p in cproblems13: print('Q02213 %s' % p)
    if not cproblems13: print('ok: 0.22.13 %s' % csummary13)
    problems += cproblems13
    cproblems14, csummary14 = check_02214()   # 0.22.14
    for p in cproblems14: print('Q02214 %s' % p)
    if not cproblems14: print('ok: 0.22.14 %s' % csummary14)
    problems += cproblems14
    cproblems15, csummary15 = check_02215()   # 0.22.15
    for p in cproblems15: print('Q02215 %s' % p)
    if not cproblems15: print('ok: 0.22.15 %s' % csummary15)
    problems += cproblems15
    have =open(ini_path, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    if have == want:
        print('ok: TruMenu.ini = defaults table (%d keys)' % len(rows))
        return 1 if problems else 0
    a, b = have.split('\n'), want.split('\n')
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<end>'
        y = b[i] if i < len(b) else '<end>'
        if x != y:
            print('MISMATCH line %d\n  ini:   %s\n  table: %s' % (i + 1, x, y))
            break
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
