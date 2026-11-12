"""Q102 (read-only): level-load phases from TruTrace.log (TruTrace 0.3, categories level / stream / timevec).

For every `level: REQUEST level change to '<unit>'` after the given session start line it prints:
  request -> STREAM_LevelLoadAndInit (load entry 0x5dded0) -> main unit slot state 2 (loaded) -> last adjacent unit
  state 2 -> `PLACEMENT done` (0x5de179, end of the wait loop 0x5de142 in 0x5de040)
and the mean of the per-second TimeVector dt [0xe7f188] samples (1.0 = 33.3 ms per loop iteration) in the load, plus
an estimate of loop iterations = sum over the samples of (1 s / (dt x 33.33 ms)).

Plugin logs carry no dates before 2026-11-12: pass the line number of a session's "TruTrace ... loaded" line; only
lines after it are used, and the scan stops at the next "loaded" line.

Usage (from the repository root):
  ../bin/pyt -t 600 work/b_nav_1211/q102/q102_load_times.py TRUTRACE_LOG START_LINE [START_LINE ...]
"""
import sys, re

RE_T = re.compile(r'^(\d\d):(\d\d):(\d\d)\.(\d\d\d) ')
RE_REQ = re.compile(r"level: REQUEST level change to '([^']+)' \(doneType (\d+)")
RE_INIT = re.compile(r"level: STREAM_LevelLoadAndInit '([^']+)' from")
RE_SLOT = re.compile(r"stream: stream unit slot (\d+): id (\d+) '([^']+)' state (\d)")
RE_PLACE = re.compile(r'level: PLACEMENT done')
RE_DT = re.compile(r'timevec: .* dt \[0xe7f188\] ([0-9.]+)')
RE_LOADED = re.compile(r'trace: TruTrace .* loaded')


def secs(line):
    m = RE_T.match(line)
    if not m: return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def fmt(t):
    if t is None: return '-'
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return '%02d:%02d:%06.3f' % (h, m, s)


def scan(path, start):
    loads = []; cur = None
    with open(path, 'rb') as f:
        for no, raw in enumerate(f, 1):
            if no < start: continue
            line = raw.decode('latin-1').rstrip('\r\n')
            if no > start and RE_LOADED.search(line): break
            t = secs(line)
            if t is None: continue
            m = RE_REQ.search(line)
            if m and '- IGNORED' not in line:
                if cur: loads.append(cur)
                cur = {'unit': m.group(1), 'done': m.group(2), 'line': no, 'req': t, 'init': None, 'main': None,
                       'adj': [], 'place': None, 'dts': []}
                continue
            if not cur: continue
            if cur['place'] is not None: continue
            m = RE_INIT.search(line)
            if m and cur['init'] is None: cur['init'] = t; continue
            m = RE_SLOT.search(line)
            if m and m.group(4) == '2' and cur['init'] is not None:
                if m.group(3).lower() == cur['unit'].lower() and cur['main'] is None: cur['main'] = t
                elif cur['main'] is not None: cur['adj'].append((m.group(3), t))
                continue
            if RE_PLACE.search(line) and cur['init'] is not None: cur['place'] = t; continue
            m = RE_DT.search(line)
            if m and cur['init'] is not None: cur['dts'].append(float(m.group(1)))
    if cur: loads.append(cur)
    return loads


def main(argv):
    path = argv[0]
    print('| line | unit | doneType | request | ->init s | ->main unit s | ->last adjacent s | ->placement s | total s | '
          'dt samples | mean dt | est. iterations | samples dt<0.75 | min dt | samples dt 0.95..1.05 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for start in (int(x) for x in argv[1:]):
        for L in scan(path, start):
            r = L['req']
            def d(t): return '%.2f' % (t - r) if t is not None else '-'
            last_adj = L['adj'][-1][1] if L['adj'] else None
            dts = L['dts']
            mean = sum(dts) / len(dts) if dts else 0
            it = sum(30.0 / x for x in dts if x > 0)
            fast = sum(1 for x in dts if x < 0.75)      # samples faster than 40 fps (limiter at 60 could matter)
            at30 = sum(1 for x in dts if 0.95 <= x <= 1.05)  # samples at exactly two 60 Hz vblanks per iteration
            print('| %d | %s | %s | %s | %s | %s | %s | %s | %s | %d | %.2f | %.0f | %d | %.2f | %d |' % (
                L['line'], L['unit'], L['done'], fmt(r), d(L['init']), d(L['main']), d(last_adj), d(L['place']),
                d(L['place']), len(dts), mean, it, fast, min(dts) if dts else 0, at30))
            if L['adj']:
                print('|  | adjacent: %s |' % ', '.join('%s %.2f' % (u, t - r) for u, t in L['adj']))


if __name__ == '__main__':
    main(sys.argv[1:])
