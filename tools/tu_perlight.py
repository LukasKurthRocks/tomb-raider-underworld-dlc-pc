"""Test 50a, second route for the TU lit shaders WITHOUT an equivalent base light block (doppelganger face 2679, body
skin 2682 / 2685, holster 2688): per-light work on the translated programs (read-only analysis + builds into a work
dir). Uses tools/tu_light_transplant.py (upstream f9 transplant with the test-50a patches).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_perlight.py xblock D|X XID SLOT OUT.txt
      translated (noopt) program with the light block marked and constant names annotated
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs


def cmd_xblock(which, xid, slot, outp):
    L = libs(); lib = L[which][xid]
    blob = lib['entries'][lib['slots'][slot]]['blob']
    K = F9.Consts([])
    prog, i0, i1, tr = F9.translate_x(blob, K.fn, lambda n, c: c, F9.xbools(blob))
    inv = {}
    for n, (ri, rc) in K.pfl.items():
        for j in range(rc): inv.setdefault(ri + j, '%s[%d]' % (n, j))
    for (n, j), r in K.extra.items(): inv[r] = '%s[%d]' % (n, j)
    for j in range(32): inv[100 + j] = 'MP[%d]' % j
    sh = XL.parse(blob); bn = F9.bool_names(sh)
    out = ['; light block [%d,%d), bools %s' % (i0, i1, sorted(bn.items()))]
    for k, i in enumerate(F9.body(prog)):
        names = sorted({inv.get(o.num, '?') for o in i.ops if o.rtype == sm3asm.RT_CONST and not o.isdst})
        out.append('%4d %s %s   %s' % (k, '|' if i0 is not None and i0 <= k < i1 else ' ', sm3asm.fmt_instr(i, 'ps'),
                                        ('; ' + ' '.join(names)) if names else ''))
    open(outp, 'w').write('\n'.join(out) + '\n'); print('wrote %s (%d instr, block [%s,%s))' % (outp, len(out) - 1, i0, i1))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'xblock': cmd_xblock(a[1], int(a[2]), int(a[3]), a[4]); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
