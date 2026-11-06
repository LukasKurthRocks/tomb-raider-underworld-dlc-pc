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
                'Fade', 'Fill', 'LabelShort', 'LaraIn')                                              # 0.16
DV_RANGES = {'TriggerMax': (1, 512), 'TriggerRadius': (500, 200000), 'TriggerLabelMax': (0, 64),
             'NameRadius': (100, 200000), 'NameMax': (1, 64), 'NameScale': (0.5, 3),
             'CollRadius': (500, 200000), 'CollMax': (100, 20000), 'CensusFrames': (10, 1200),   # 0.15
             'Depth': (0, 2), 'DepthDim': (5, 80), 'DepthCall': (-1, 7), 'LineAlpha': (10, 100),  # 0.16 (0.17: -1 auto)
             'LineBright': (30, 150), 'FadeStart': (0, 100000), 'FadeEnd': (500, 200000), 'FadeMin': (0, 100),
             'FillAlpha': (2, 40), 'ViewLabelMax': (0, 64), 'Enclosing': (0, 2), 'EnclosingSize': (100, 100000),
             'MarkerMax': (2, 50)}
DV_FLOAT_KEYS = ('TriggerRadius', 'NameRadius', 'NameScale', 'CollRadius',     # the others are whole numbers
                 'FadeStart', 'FadeEnd', 'EnclosingSize')                      # 0.16
DV_ITEMS = {'dbg.view': 'bool', 'dbg.triggers': 'bool', 'dbg.show': 'action', 'dbg.portals': 'bool',
            'dbg.checkpoints': 'bool', 'dbg.legend': 'bool', 'dbg.status': 'info', 'dbg.names': 'bool',
            'dbg.namefilter': 'action', 'dbg.namecolour': 'action', 'dbg.namesize': 'action',
            # 0.15 render mode
            'dbg.census': 'action', 'dbg.flat': 'bool', 'dbg.flatpass': 'action', 'dbg.flatpasses': 'action',
            'dbg.flatcolour': 'action', 'dbg.flatmodels': 'bool', 'dbg.flatedges': 'bool', 'dbg.flatanyrt': 'bool',
            'dbg.render': 'info', 'dbg.slide': 'bool', 'dbg.enemycoll': 'bool',
            # 0.16 readability
            'dbg.depth': 'action', 'dbg.alpha': 'action', 'dbg.bright': 'action', 'dbg.fade': 'bool', 'dbg.fill': 'bool',
            'dbg.short': 'bool', 'dbg.larain': 'bool', 'dbg.enclosing': 'action', 'dbg.style': 'info'}
# 0.16: ring entries with a fixed set of arguments (each once), percent presets, switches without an argument (once)
DP_RING_ARGS = {'dbg.depth': ('on', 'dim', 'off'), 'dbg.enclosing': ('normal', 'dim', 'hide')}
DP_RING_PERCENT = {'dbg.alpha': (10, 100), 'dbg.bright': (30, 150)}
DP_RING_SWITCHES = ('dbg.fade', 'dbg.fill', 'dbg.short', 'dbg.larain', 'dbg.style')
DV_OWN_ITEM = {'portals': 'dbg.portals', 'checkpoints': 'dbg.checkpoints', 'legend': 'dbg.legend', 'names': 'dbg.names',
               'slide': 'dbg.slide', 'enemycoll': 'dbg.enemycoll'}
# 0.15: the pass ids of the flat view (kRmPassNames in TruMenu.cpp), their mask, the ring switches without an argument
RM_PASSES = ('0x200', '0x100', '0x80', '0x400', '0x800', '1', '2')
RM_PASS_ALL = 0xf83
RM_RING_SWITCHES = ('dbg.flat', 'dbg.census', 'dbg.flatedges', 'dbg.flatmodels', 'dbg.flatanyrt', 'dbg.render')
DV_LAYER_COUNT = 15
# 0.17 quick toggles: [Quick] keys / ranges, the buttons the open bar owns, [Shot] OnCine ranges, the new items, the row
# tables of the bar and the items a value row may use
QB_KEYS = ('Enabled', 'OpenButtons', 'ChordMs', 'ShowClosed', 'Language', 'Top', 'Scale')
QB_RANGES = {'ChordMs': (50, 1000), 'Top': (5, 80), 'Scale': (0.5, 3)}
QB_OWN = 0x030F
OC_RANGES = {'OnCinePairs': (1, 50), 'OnCineFastPairs': (1, 50), 'OnCineIntervalMs': (250, 10000),
             'OnCineSlowMs': (250, 60000)}
QB_ITEMS = {'quick.open': 'bool', 'quick.lang': 'action', 'quick.status': 'info', 'shot.oncine': 'bool',
            'dbg.depthdump': 'action', 'dbg.cp': 'action', 'dbg.cpall': 'action', 'dbg.cplist': 'info',
            'dbg.cpgo': 'action', 'pos.save': 'action', 'pos.list': 'info', 'pos.go': 'action'}
QB_TABLES = ('kQbEmergency', 'kQbLara', 'kQbDebug', 'kQbLevel', 'kQbRender', 'kQbTimeTest', 'kQbChapters', 'kQbAccess')
QB_VALUE_ITEMS = ('dbg.depth', 'dbg.alpha', 'dbg.bright', 'dbg.enclosing', 'cheat.speed', 'dbg.flatpasses', 'quick.lang',
                  'time.scale', 'ai.mode')                                       # 0.19 ai.mode
# 0.18: the new items, the 0 / 1 keys, the bar pages (QbPage rows of kQbPages: 10 pages, special ones without a table)
Q18_ITEMS = {'overlay.larain': 'bool', 'pos.goload': 'action', 'save.load': 'action'}
Q18_KEYS = (('Menu', 'OverlayLaraIn'), ('Debug', 'LegendLaraIn'), ('Saves', 'DirectLoad'), ('Shot', 'OnCineSegments'))
QB_PAGES_MAX = 10
# 0.19 dumb AI: the items, the presets (kAiPresets + "filter"), the [AI] keys
Q19_ITEMS = {'ai.dumb': 'action', 'ai.mode': 'action', 'ai.noinvestigate': 'bool', 'ai.noattack': 'bool',
             'ai.status': 'info'}
AI_PRESETS = ('all', 'sharks', 'spiders', 'thralls')
AI_SETTINGS = AI_PRESETS + ('filter',)
AI_KEYS = ('Dumb', 'DumbFilter', 'DumbMode', 'NoInvestigate', 'NoAttack')
DV_NAME_COLOURS = ('white', 'yellow', 'cyan', 'magenta', 'weiss', 'gelb')
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
    items = item_types(open(CPP, encoding='utf-8').read())
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
    src = open(CPP, encoding='utf-8').read()
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
    src = open(CPP, encoding='utf-8').read()
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
    src = open(CPP, encoding='utf-8').read()
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
    src = open(CPP, encoding='utf-8').read()
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
    src = open(CPP, encoding='utf-8').read()
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
            elif v & QB_OWN: problems.append(where + ' (must not hold D-pad / LB / RB = 0x%04X: the open bar owns them)'
                                             % QB_OWN)
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
    src = open(CPP, encoding='utf-8').read()
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
        if (item == '-') != (kind in ('kQbLabel', 'kQbPlanned')):
            problems.append(where + ': id "-" exactly on label / planned rows')
        if kind == 'kQbPlanned':
            planned += 1
            if arg.count('|') != 1 or not all(arg.split('|')): problems.append(where + ': planned text "German|English"')
        if kind == 'kQbLabel': labels += 1
        if flags:
            confirm += 1
            if kind != 'kQbAction': problems.append(where + ': kQfConfirm / kQfBackup only on action rows')
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
    src = open(CPP, encoding='utf-8').read()
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


def unescape(s):
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')


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
    header, rows = table(open(CPP, encoding='utf-8').read())
    want = text(header, rows)
    if argv and argv[0] == '--print':
        sys.stdout.write(want)
        return 0
    opt = {k: argv[i + 1] for i, k in enumerate(argv[:-1]) if k in ('--ini', '--radial', '--tour')}
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
