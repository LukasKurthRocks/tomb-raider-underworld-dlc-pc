"""Emitter lifetimes from a TruTrace 0.2 log (read-only; F5 groan loop 2026-11-05).

TruTrace [Sound] writes START lines (anim event sounds, level 1), LONG lines (emitter alive after SoundLiveMs), END
lines (emitter destructor, with the age) and REPEAT lines. This tool joins them per emitter address (an address is
reused after an END, so a START / LONG opens a new life and the next END closes it) and prints:
  * per sound id: lives seen, END count, longest / median age, lives > --min seconds, REPEAT lines, start kinds
  * every life longer than --min seconds: id, emitter, start (START time or LONG / END time minus the age), end,
    age, starter (anim event payload / frame or wrapper caller), and the claude.mark lines of TruMenu.log
    (--menu) that fall inside it

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trace_sound_life.py RUN_DIR [--min 20] [--sid 24539,20212]
        RUN_DIR holds TruTrace.log (and TruMenu.log for the marks)
"""
import sys, os, re, collections, statistics

T = re.compile(r'^(\d\d):(\d\d):(\d\d)\.(\d\d\d) ')
START = re.compile(r'sound: START sound (\d+) \(soundplex (0x[0-9a-f]+)\) emitter (0x[0-9a-f]+) (.*?): inst (0x[0-9a-f]+).*?'
                   r'payload (0x[0-9a-f]+) bytes (\w\w) (\w\w) s16 (-?\d+), record h (0x[0-9a-f]+) frame (-?\d+);.*instance list: (\w+)')
LONG = re.compile(r'sound: LONG sound (\d+) emitter (0x[0-9a-f]+) still alive after (\d+)\.(\d+) s \(refcount (\d+), flags '
                  r'\+0x24 (0x[0-9a-f]+), \+0x44 (0x[0-9a-f]+); ([^)]*)\): started by (.*)$')
END = re.compile(r'sound: END sound (\d+) emitter (0x[0-9a-f]+) after (\d+)\.(\d+) s.*?\(started: (.*)\)$')
REP = re.compile(r'sound: REPEAT sound (\d+) started (\d+) times in 10 s by (.*)$')
MARK = re.compile(r'claude\.mark (\w+): (\d\d:\d\d:\d\d\.\d\d\d) (.*)$')


def secs(line):
    m = T.match(line)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0 if m else None


def hms(t):
    t = max(0.0, t)
    return '%02d:%02d:%06.3f' % (int(t // 3600), int(t % 3600 // 60), t % 60)


def main(a):
    if not a: sys.exit(__doc__)
    run = a[0]
    mn = float(a[a.index('--min') + 1]) if '--min' in a else 20.0
    want = set(int(x) for x in a[a.index('--sid') + 1].split(',')) if '--sid' in a else None
    lives = []; openl = {}
    rep = collections.Counter(); kinds = collections.defaultdict(collections.Counter)
    for line in open(os.path.join(run, 'TruTrace.log'), encoding='utf-8', errors='replace'):
        t = secs(line)
        if t is None or ' sound: ' not in line: continue
        m = START.search(line)
        if m:
            L = dict(sid=int(m.group(1)), em=m.group(3), start=t, end=None, age=None, how='anim event inst %s payload %s '
                     'bytes %s %s s16 %s frame %s list %s' % (m.group(5), m.group(6), m.group(7), m.group(8), m.group(9),
                                                            m.group(11), m.group(12)), long=None)
            openl[L['em']] = L; lives.append(L); kinds[L['sid']]['anim START'] += 1; continue
        m = LONG.search(line)
        if m:
            em = m.group(2); age = int(m.group(3)) + int(m.group(4)) / 1000.0
            L = openl.get(em)
            if L is None or L['sid'] != int(m.group(1)) or L['end'] is not None:
                L = dict(sid=int(m.group(1)), em=em, start=t - age, end=None, age=None, how=m.group(9)[:120], long=None)
                openl[em] = L; lives.append(L); kinds[L['sid']]['LONG only'] += 1
            L['long'] = 'flags +0x24 %s +0x44 %s, %s' % (m.group(6), m.group(7), m.group(8)); continue
        m = END.search(line)
        if m:
            em = m.group(2); age = int(m.group(3)) + int(m.group(4)) / 1000.0
            L = openl.pop(em, None)
            if L is None or L['sid'] != int(m.group(1)):
                L = dict(sid=int(m.group(1)), em=em, start=t - age, end=None, age=None, how=m.group(5)[:120], long=None)
                lives.append(L); kinds[L['sid']]['END only'] += 1
            L['end'] = t; L['age'] = age; continue
        m = REP.search(line)
        if m: rep[int(m.group(1))] += 1
    marks = []
    mp = os.path.join(run, 'TruMenu.log')
    if os.path.exists(mp):
        for line in open(mp, encoding='utf-8', errors='replace'):
            m = MARK.search(line)
            if m and line[13:].startswith('claude.mark sound'):     # the tester's "sound strange" marks only
                marks.append((secs(m.group(2) + ' '), m.group(1), m.group(3)[:90]))
    by = collections.defaultdict(list)
    for L in lives: by[L['sid']].append(L)
    print('lives %d, ids %d, marks %d' % (len(lives), len(by), len(marks)))
    print('%-6s %6s %5s %9s %9s %6s %7s  %s' % ('sid', 'lives', 'ends', 'max age', 'median', '>min', 'REPEAT', 'kinds'))
    for sid in sorted(by, key=lambda s: -max([x['age'] or 0 for x in by[s]])):
        if want and sid not in want: continue
        ages = [x['age'] for x in by[sid] if x['age'] is not None]
        print('%-6d %6d %5d %9.3f %9.3f %6d %7d  %s' % (sid, len(by[sid]), len(ages), max(ages) if ages else 0,
              statistics.median(ages) if ages else 0, sum(1 for x in ages if x > mn), rep.get(sid, 0), dict(kinds[sid])))
    print('\nlives longer than %.0f s (or still open at the end of the log):' % mn)
    for L in sorted(lives, key=lambda x: x['start']):
        if want and L['sid'] not in want: continue
        if (L['age'] or 0) <= mn and L['end'] is not None: continue
        if L['end'] is None and L['long'] is None: continue
        inside = [m for m in marks if L['start'] <= m[0] <= (L['end'] or 1e9)]
        print('sound %d emitter %s: %s -> %s, age %s; %s%s' % (
            L['sid'], L['em'], hms(L['start']), hms(L['end']) if L['end'] else 'open', '%.3f s' % L['age'] if L['age'] else '-',
            L['how'], ('; LONG ' + L['long']) if L['long'] else ''))
        for m in inside: print('    mark %s %s %s' % (hms(m[0]), m[1], m[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
