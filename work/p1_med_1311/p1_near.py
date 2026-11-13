"""P1 (2026-11-13): what lies near given intros (read-only) - nearest checkpoints, portals and other intros.

INTROS = tools/manor_gate_scan.py intros output (live frame, '== unit:' blocks, 'portal -> X centre as stored' lines -
same frame as the intro positions, group J / Q113). For each UNIT:UID prints its position and the nearest N intros
whose object name matches REGEX (default: checkpoint|portal|hpole|grapple|switch|lever|ladder|_rw_|weightbreak|
pt_weight|press_plate|plat|bridge|door), with distance in m (100 units = 1 m) and height difference dz in m.

Usage (from trudlcport):
  ../bin/pyt -t 300 work/p1_med_1311/p1_near.py INTROS UNIT:UID[,UNIT:UID..] [--n 8] [--grep REGEX]
"""
import sys, re, math

DEF = r'checkpoint|hpole|grapple|switch|lever|_rw_|weightbreak|pt_weight|press_plate|plat|bridge|door|gate|tentacle'


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def parse(path):
    units, u = {}, None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', ln)
        if m: u = units.setdefault(m.group(1), []); continue
        m = re.match(r'^\s+portal -> (\S+)\s+centre as stored \((\S+) (\S+) (\S+)\)', ln)
        if m and u is not None:
            u.append(('portal', 'portal->' + m.group(1), tuple(float(m.group(k)) for k in (2, 3, 4)))); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+)\s+live \(\s*(\S+)\s+(\S+)\s+(\S+)\)', ln)
        if m and u is not None:
            u.append((m.group(1), m.group(2), (float(m.group(3)), float(m.group(4)), float(m.group(5)))))
    return units


def main(argv):
    n = int(opt(argv, '--n', '8'))
    rx = re.compile(opt(argv, '--grep', DEF), re.I)
    if len(argv) < 2:
        print(__doc__); return 2
    U = parse(argv[0])
    for spec in argv[1].split(','):
        unit, uid = spec.split(':')
        rows = U.get(unit, [])
        me = next((r for r in rows if r[0] == uid), None)
        if me is None:
            print('%s: intro %s not found' % (unit, uid)); continue
        p = me[2]
        print('== %s intro %s %s at (%.0f %.0f %.0f)' % (unit, uid, me[1], *p))
        cand = []
        for r in rows:
            if r is me or not (r[0] == 'portal' or rx.search(r[1])): continue
            d = math.dist(p, r[2])
            cand.append((d, r))
        for d, r in sorted(cand)[:n]:
            print('   %6.1f m  dz %+6.1f m  %-8s %s' % (d / 100, (r[2][2] - p[2]) / 100, r[0], r[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
