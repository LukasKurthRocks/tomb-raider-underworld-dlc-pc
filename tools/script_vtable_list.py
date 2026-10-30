"""List the vtable of one script (type 8 section): per slot the VTE entry count and the functions its pointers address
(own function index, or script id + offset for an external one), read-only. Finding 43 follow-up (test 35): compare
the ported title-update hint-box script (PC script 9 in a test generalbank) slot by slot with Crystal's PC script 9
before and after tools/script_vtable_insert.py.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/script_vtable_list.py SOURCE SCRIPT_ID
  SOURCE = a PC (little-endian) DRM file, or a tools/menu_dlc_probe.py variant (xl / xt / pb / pp)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def vtable(S, e, sid):
    """[(slot, n, [target, ...])] with target = ('f', k) for an own function entry, ('x', script, offset) external,
    ('i', offset) other internal, None for an unrelocated word"""
    import script_conv as SC
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal); ext = {so: (S[si][1], do) for si, so, do in rel.external}
    W = SC.Walk(d, rel, e).run()
    funcs = {}
    for name, t, n, sz in W.arrays:
        if name == 'funcs': funcs = {t + k * sz: k for k in range(n)}
    size = struct.unpack_from(E + 'H', d, 0x3c)[0]; tab = it[0x44]
    out = []
    for k in range(size):
        a = tab + 4 * k
        if a not in it: out.append((k, None, [])); continue
        v = it[a]; n = struct.unpack_from(E + 'I', d, v)[0]; tg = []
        for j in range(n):
            p = v + 4 + 4 * j
            if p in it: tg.append(('f', funcs[it[p]]) if it[p] in funcs else ('i', it[p]))
            elif p in ext: tg.append(('x',) + ext[p])
            else: tg.append(None)
        out.append((k, n, tg))
    return out


def main(argv):
    S, e = FL.sections(argv[0])
    for k, n, tg in vtable(S, e, int(argv[1])):
        print('slot %2d  n=%s  %s' % (k, n, ' '.join(
            'f%d' % t[1] if t and t[0] == 'f' else 's%d+%#x' % (t[1], t[2]) if t and t[0] == 'x' else
            'i%#x' % t[1] if t else '-' for t in tg)))


if __name__ == '__main__':
    main(sys.argv[1:])
