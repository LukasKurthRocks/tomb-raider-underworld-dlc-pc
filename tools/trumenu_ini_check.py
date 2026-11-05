"""Check that the shipped src/asi/TruMenu/TruMenu.ini is exactly the text TruMenu writes from its defaults table
(kOpts in TruMenu.cpp, DefaultIniText) - read-only. Since TruMenu 0.8 also the regression lists tests/regress/*.txt
(TruMenu.tests.txt row format, 8 tab-separated columns; step ids step<n> = number; ids unique; every check id named in
backticks in its source doc docs/Regression-DLC1.md / docs/Regression-Schattenlara.md; ASCII only).
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

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_ini_check.py            compare + list check, print the first difference / every
                                                         list problem; exit 1 on a mismatch
  ../bin/pyt -t 60 tools/trumenu_ini_check.py --print    print the text generated from the table
  options (negative tests on copies): --ini FILE, --radial FILE, --tour FILE check that file instead of the shipped one
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
INI = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.ini')
REGRESS = {'dlc1.txt': 'Regression-DLC1.md', 'dlc2.txt': 'Regression-Schattenlara.md'}
RADIAL = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.radial.txt')
TOUR = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.tour.txt')
RADIAL_FORBIDDEN = ['game.quit', 'cmd.run', 'save.delete', 'save.restore', 'save.import', 'settings.reset']
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
LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')


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
    have = open(ini_path, encoding='utf-8', newline='').read().replace('\r\n', '\n')
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
