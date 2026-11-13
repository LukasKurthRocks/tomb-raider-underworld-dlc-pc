"""P1 (2026-11-13): filter a TruTrace.log for given intro ids / object names (read-only).

Drops the per-frame noise: FLAGS lines whose only change is iflags bit 0x200 (drawn this frame) and POST message 0x1e2
(482, sent every frame by 0x6a5c20). Prints BIRTH / DEATH / other FLAGS / message lines that remain.

Usage (from trudlcport): ../bin/pyt -t 300 work/p1_med_1311/p1_trace_filter.py TruTrace.log REGEX [--from HH:MM] [--to HH:MM]
  REGEX is matched against the line (e.g. 'ms_ei_switch_oneway_wall intro (498|30)\\b').
"""
import sys, re


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    t0 = opt(argv, '--from'); t1 = opt(argv, '--to')
    if len(argv) < 2:
        print(__doc__); return 2
    rx = re.compile(argv[1])
    fl = re.compile(r'\+0x14 (0x[0-9a-f]+) -> (0x[0-9a-f]+), \+0x18 (0x[0-9a-f]+) -> (0x[0-9a-f]+)')
    n = 0
    for ln in open(argv[0], encoding='utf-8', errors='replace'):
        if not rx.search(ln): continue
        hm = ln[11:16]
        if t0 and hm < t0: continue
        if t1 and hm > t1: continue
        if 'message 0x1e2 ' in ln: continue
        m = fl.search(ln)
        if m and 'FLAGS' in ln:
            a, b, c, d = (int(x, 16) for x in m.groups())
            if (a ^ b) & ~0x200 == 0 and c == d: continue
        print(ln.rstrip()[:330]); n += 1
    print('%d lines' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
