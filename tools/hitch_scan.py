"""Game-thread stalls ("hitches") from a test run's TruMenu.log, with context, plus the cdb breakpoints of the run
(read-only; F10 / B29 shotgun stutter, 04.11.2026).

How a stall shows up: TruMenu's Present hook (TruMenu.cpp Render, "pad: slot not polled") logs "slot not polled" when
the game has not called XInputGetState for > 250 ms at a Present, and "slot polled again" at the next Present after a
poll. During normal play the game polls every frame, so the pair never appears. A pair whose second line follows
within SHORT_MS (one or two frames) means: ONE frame took > 250 ms (the game thread stalled), then play went on.
Longer pairs are phases without pad polling (movies, loading, front end) and are listed apart.

cdb.log: the software / hardware breakpoints the session set (lines "0:000> bp.. / ba.."), the generic instance
breakpoints of session_thrall_watch2 (tru+0x1bb47e, 0x1bc4f2, 0x1bc588, 0x1bc70d, 0x1bc712, 0x1b2f92) are named, and
the spacing of consecutive LOGGED stops (marker line + "Debug session time") is measured = what one logged stop with
output costs the game (the game is frozen while cdb runs the command).

The script never reads TruGuard files.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/hitch_scan.py RUN_DIR                 stalls with context + breakpoints + stop spacing
  ../bin/pyt -t 300 tools/hitch_scan.py --summary RUN_DIR ...   one line per run: generic bps yes/no, stalls in levels
"""
import sys, os, re

SHORT_MS = 100
BURST_MS = 2500
TS = re.compile(r'^(?:\d{4}-\d\d-\d\d )?(\d\d):(\d\d):(\d\d)\.(\d{3}) (.*)$')   # optional date since Q107
DBGTIME = re.compile(r'^Debug session time: \w+ \w+ +\d+ (\d\d):(\d\d):(\d\d)\.(\d{3}) ')
BPLINE = re.compile(r'^0:000> (b[pa]\d*)\s+(\S+(?:\s+\S+)?)')
GENERIC = {
    0x1bb47e: 'bp20 after the category-list push of the queued spawn 0x5bb160',
    0x1bc4f2: 'bp21 INSTANCE_ReallyRemoveInstance 0x5bc4e0, instance with script data (+0x60 != 0)',
    0x1bc588: 'bp22 INSTANCE_ReallyRemoveInstance, every removal',
    0x1bc70d: 'bp23 unlink call 0x597690, every removal',
    0x1bc712: 'bp24 after the unlink, every removal',
    0x1b2f92: 'bp25 after the list insert 0x5b2f40 (birth path 0x5ba650 -> 0x5ba6ec)',
}


def ms_of(h, m, s, f):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(f)


def fmt(t):
    return '%02d:%02d:%02d.%03d' % (t // 3600000, t // 60000 % 60, t // 1000 % 60, t % 1000)


def read_lines(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


def scan_menu(path):
    """returns (stalls, phases, level_ms) - stalls: dicts with time, gap and context"""
    state = {'unit': '-', 'weapon': '-', 'weapon_t': None, 'cam': '?', 'radial': False, 'menu': False,
             'scale': '1.000', 'pause': '0'}
    stalls, phases = [], []
    pending = None
    first_unit = last_t = None
    for line in read_lines(path):
        m = TS.match(line)
        if not m: continue
        t = ms_of(*m.groups()[:4])
        txt = m.group(5)
        last_t = t
        if txt.startswith('unit: '):
            state['unit'] = txt[6:].split(' ')[0]
            if first_unit is None: first_unit = t
        mw = re.search(r'GiveWeaponByName 0x[0-9a-f]+\("([^"]+)"', txt)
        if mw: state['weapon'], state['weapon_t'] = mw.group(1), t
        mc = re.match(r'camera: mode (\d+) -> (\d+)', txt)
        if mc: state['cam'] = mc.group(2)
        mc = re.match(r'camera: mode (\d+) \(', txt)
        if mc: state['cam'] = mc.group(1)
        if txt.startswith('radial: opened'): state['radial'] = True
        if txt.startswith('radial: closed'): state['radial'] = False
        if txt.startswith('menu opened'): state['menu'] = True
        if txt.startswith('menu closed'): state['menu'] = False
        ms = re.search(r'time\.scale ([0-9.]+) \(timeDilation', txt)
        if ms: state['scale'] = ms.group(1)
        mp = re.match(r'item time\.pause: time\.pause (\d)', txt)
        if mp: state['pause'] = mp.group(1)
        if txt.startswith('pad: slot not polled'):
            pending = (t, dict(state))
        elif txt.startswith('pad: slot polled again') and pending:
            t0, st = pending
            pending = None
            gap = t - t0
            rec = {'t': t0, 'gap': gap, **st}
            if st['weapon_t'] is not None: rec['since'] = (t0 - st['weapon_t']) / 1000.0
            (stalls if gap <= SHORT_MS else phases).append(rec)
    level_ms = (last_t - first_unit) if (first_unit is not None and last_t is not None) else 0
    return stalls, phases, level_ms, first_unit


def scan_cdb(path):
    bps, generic, stops = [], [], []
    if not os.path.isfile(path): return None, None, None
    lines = read_lines(path)
    marker = None
    for i, line in enumerate(lines):
        m = BPLINE.match(line)
        if m:
            bps.append(line[7:120])
            for off, what in GENERIC.items():
                if ('tr8_win32_gm+0x%x ' % off) in line or ('tru+0x%x ' % off) in line:
                    generic.append('%s  (%s)' % (m.group(1), what))
        if re.match(r'^[A-Z][A-Z0-9_]+( dyn\d)?$', line):
            marker = line
        md = DBGTIME.match(line)
        if md and marker:
            stops.append((ms_of(*md.groups()), marker))
            marker = None
    return bps, generic, stops


def in_level(rec, first_unit):
    return first_unit is not None and rec['t'] >= first_unit


def detail(run):
    menu = os.path.join(run, 'TruMenu.log')
    stalls, phases, level_ms, first_unit = scan_menu(menu)
    print('run %s' % run)
    print('first unit line %s, level time %.1f min' % (fmt(first_unit) if first_unit else '-', level_ms / 60000.0))
    print('\n== stalls (pair gap <= %d ms = one frame > 250 ms)' % SHORT_MS)
    print('time          gap  unit                     weapon (s since give)        cam  radial menu scale pause')
    prev = None
    for r in stalls:
        since = ('%.1f' % r['since']) if 'since' in r else '-'
        d = ('  +%.2f s' % ((r['t'] - prev) / 1000.0)) if prev is not None else ''
        print('%s  %4d  %-24s %-20s (%5s)  %4s  %-6s %-4s %-5s %s%s' % (
            fmt(r['t']), r['gap'], r['unit'], r['weapon'], since, r['cam'], r['radial'], r['menu'], r['scale'],
            r['pause'], d))
        prev = r['t']
    print('\n== phases without pad polling (gap > %d ms)' % SHORT_MS)
    for r in phases:
        print('%s  %6d ms  %s  cam %s' % (fmt(r['t']), r['gap'], r['unit'], r['cam']))
    bps, generic, stops = scan_cdb(os.path.join(run, 'cdb.log'))
    if bps is None:
        print('\nno cdb.log (run without debugger)')
        return
    print('\n== cdb breakpoints (%d)' % len(bps))
    for b in bps: print('  ' + b)
    print('generic instance breakpoints: %d' % len(generic))
    for g in generic: print('  ' + g)
    print('\n== logged stops: %d; spacing of consecutive logged stops < 200 ms (cost of one stop with output)' % len(stops))
    ds = []
    for (a, ma), (b, mb) in zip(stops, stops[1:]):
        if 0 <= b - a < 200:
            ds.append(b - a)
            print('  %s %-16s -> %s %-16s %3d ms' % (fmt(a), ma, fmt(b), mb, b - a))
    if ds:
        ds.sort()
        print('  n %d, min %d ms, median %d ms, max %d ms' % (len(ds), ds[0], ds[len(ds) // 2], ds[-1]))


def summary(runs):
    print('run                                        cdb  generic  level_min  stalls_in_level  per_min  shotgun  burst   '
          'burst units   (burst = another stall within %.1f s; shotgun = last given weapon is a shotgun)'
          % (BURST_MS / 1000.0))
    for run in runs:
        menu = os.path.join(run, 'TruMenu.log')
        if not os.path.isfile(menu):
            print('%-42s no TruMenu.log' % os.path.basename(run.rstrip('/\\')))
            continue
        stalls, phases, level_ms, first_unit = scan_menu(menu)
        bps, generic, stops = scan_cdb(os.path.join(run, 'cdb.log'))
        lv = [r for r in stalls if in_level(r, first_unit)]
        sg = [r for r in lv if 'shotgun' in r['weapon']]
        # burst = a stall with another stall within BURST_MS before or after (repeated stalls, e.g. while shooting)
        ts = [r['t'] for r in lv]
        burst = sum(1 for i, t in enumerate(ts)
                    if (i > 0 and t - ts[i - 1] <= BURST_MS) or (i + 1 < len(ts) and ts[i + 1] - t <= BURST_MS))
        units = sorted(set(r['unit'] for r in lv if r['t'] in ts and (
            (ts.index(r['t']) > 0 and r['t'] - ts[ts.index(r['t']) - 1] <= BURST_MS) or
            (ts.index(r['t']) + 1 < len(ts) and ts[ts.index(r['t']) + 1] - r['t'] <= BURST_MS))))
        mins = level_ms / 60000.0
        print('%-42s %-4s %7s  %9.1f  %15d  %7.2f  %7d  %6d  %s' % (
            os.path.basename(run.rstrip('/\\')), 'yes' if bps is not None else 'no',
            ('-' if generic is None else len(generic)), mins, len(lv), (len(lv) / mins) if mins > 0 else 0, len(sg),
            burst, ','.join(units)))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == '--summary':
        summary(argv[1:])
    else:
        detail(argv[0])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
