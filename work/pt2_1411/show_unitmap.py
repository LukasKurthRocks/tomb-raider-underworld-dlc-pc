"""PT.2 (2026-11-14): print the Xbox -> PC unit id map (space 'unit' of work/generic/unit_idmaps.json) for a range.
Read-only. Usage (from the repository root): ../bin/pyt -t 60 work/pt2_1411/show_unitmap.py [LO HI]"""
import sys, os, json
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'generic')
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (80, 120)
d = json.load(open(os.path.join(W, 'unit_idmaps.json')))
print('spaces:', sorted(d))
m = {int(a): b for a, b in d['unit'].items()}
for a in sorted(m):
    if lo <= a <= hi or (isinstance(m[a], int) and lo <= m[a] <= hi): print('xbox %d -> pc %s' % (a, m[a]))
