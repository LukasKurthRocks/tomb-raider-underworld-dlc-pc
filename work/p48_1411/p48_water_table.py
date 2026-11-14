"""P4.8 (2026-11-14): only the watervolume part of the introtyped proof (typed_family_fix.water_table), with the
+0x10 samples that do not fit and what the other id spaces give for the second u16. Read-only.
Usage: ../bin/pyt -t 1800 work/p48_1411/p48_water_table.py"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import typed_family_fix as T, generic_type0 as G0
print(dict(T.water_table()))
sp = G0.space_maps()
for nm, xa, xb, pa, pb, im in T._ST.get('wv_bad', [])[:60]:
    alt = {t: m.get(xb) for t, m in sp.items() if xb in m}
    print('  %-24s Xbox {%d, %d} PC {%d, %d} intro map %s  other spaces %s' % (nm, xa, xb, pa, pb, im, alt))
