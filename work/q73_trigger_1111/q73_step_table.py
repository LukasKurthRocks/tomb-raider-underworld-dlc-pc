"""Q73 (2026-11-11): trigger volume thickness against Lara's step per frame (read-only, text input only).

Input: the text files written by tools/manor_gate_scan.py intros (lines 'intro N name live (x y z) ... shape S half
(hx hy hz) r R'). For every requested intro id: full extents 2*h per axis (boxes; the boxes in question have no
rotation, checked with --uid raw records) and the critical speed v_crit = thinnest extent / dt above which the
engine's two-point test 0x5cd1b0 (old frame point vs new frame point, no sweep) can step over the box in one frame.
dt = 1 / fps, but never more than 2 / 30 s: the frame-time function 0x5da230 clamps the elapsed time to 66 666 us
(0x5da455 cmp eax, 0x1046a) before dividing by 33 333.3 us (0x855280), so below 15 fps the game slows down instead
of taking longer steps.

Usage (from the repository root):
  ../bin/pyt -t 120 work/q73_trigger_1111/q73_step_table.py INTROS.txt[,INTROS.txt..] ID[,ID..] [--speeds 1000,2000]
Prints one row per id: unit, name, half extents, full extents, thinnest axis, v_crit at 15 (clamp) / 30 / 60 / 144 fps
and for each --speeds value the step per frame at 30 / 60 / 144 fps and at the clamp.
"""
import sys, re

ROW = re.compile(r'intro\s+(\d+)\s+(\S+)\s+live \(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\).*?shape (\d+) half \(([-\d.]+) ([-\d.]+) ([-\d.]+)\) r ([-\d.]+)')
FPS = (15, 30, 60, 144)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    files = argv[0].split(',')
    ids = set(int(x) for x in argv[1].split(','))
    speeds = []
    if '--speeds' in argv:
        speeds = [float(x) for x in argv[argv.index('--speeds') + 1].split(',')]
    found = {}
    for fn in files:
        unit = '?'
        for ln in open(fn, encoding='utf-8', errors='replace'):
            if ln.startswith('== '):
                unit = ln.split()[1].rstrip(':')
                continue
            m = ROW.search(ln)
            if m and int(m.group(1)) in ids:
                found[int(m.group(1))] = (unit, m)
    print('id | unit | name | shape | half x y z | full x y z | thinnest | v_crit u/s at ' +
          ' / '.join('%d fps' % f for f in FPS))
    for i in sorted(ids):
        if i not in found:
            print('%d | not found' % i)
            continue
        unit, m = found[i]
        shape = int(m.group(6))
        h = [float(m.group(k)) for k in (7, 8, 9)]
        if shape == 2:
            full = [2 * float(m.group(10))] * 3
        else:
            full = [2 * x for x in h]
        thin = min(full)
        axis = 'xyz'[full.index(thin)]
        vc = ['%.0f' % (thin * f) for f in FPS]
        print('%d | %s | %s | %d | %.1f %.1f %.1f | %.1f %.1f %.1f | %.1f (%s) | %s' % (
            i, unit, m.group(2), shape, h[0], h[1], h[2], full[0], full[1], full[2], thin, axis, ' / '.join(vc)))
    for v in speeds:
        print('speed %.0f u/s: step per frame %s' % (v, ' / '.join('%.1f u at %d fps' % (v / f, f) for f in FPS)))
    # --points ID[,ID..]: is the engine test point (position + (0, 0, 200), [0x853f08]) of these intros (checkpoints,
    # player starts) inside each listed box? Only valid for unrotated boxes (rotation checked separately).
    if '--points' in argv:
        pts = set(int(x) for x in argv[argv.index('--points') + 1].split(','))
        PT = re.compile(r'intro\s+(\d+)\s+(\S+)\s+live \(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)')
        pos = {}
        for fn in files:
            unit = '?'
            for ln in open(fn, encoding='utf-8', errors='replace'):
                if ln.startswith('== '):
                    unit = ln.split()[1].rstrip(':')
                    continue
                m = PT.search(ln)
                if m and int(m.group(1)) in pts:
                    pos[int(m.group(1))] = (unit, m.group(2), [float(m.group(k)) for k in (3, 4, 5)])
        for p in sorted(pts):
            if p not in pos:
                print('point %d not found' % p)
                continue
            pu, pn, pp = pos[p]
            tp = [pp[0], pp[1], pp[2] + 200.0]
            for i in sorted(found):
                unit, m = found[i]
                if unit != pu or int(m.group(6)) != 1:
                    continue
                c = [float(m.group(k)) for k in (3, 4, 5)]
                h = [float(m.group(k)) for k in (7, 8, 9)]
                d = [abs(tp[k] - c[k]) - h[k] for k in range(3)]
                inside = all(x <= 0 for x in d)
                print('point %d %s (%s) test point (%.1f %.1f %.1f) vs box %d: %s, margin per axis %.1f %.1f %.1f '
                      '(<= 0 = inside on that axis)' % (p, pn, pu, tp[0], tp[1], tp[2], i,
                                                        'INSIDE' if inside else 'outside', d[0], d[1], d[2]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
