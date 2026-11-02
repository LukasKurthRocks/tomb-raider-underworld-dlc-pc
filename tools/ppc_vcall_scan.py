"""Find virtual calls through given vtable slots in an Xbox 360 image, optionally only on an object loaded from a given
global pointer (read-only; 2026-11-02, TU function comparison item L9: who sets / clears / tests the camera manager's
+0x7c bits through (*0x82efc780)->vtbl[0x8c..0xac]?).

Pattern (window of --window instructions, default 8): `lwz rV, 0(rO)` -> `lwz rF, SLOT(rV)` -> `mtctr rF` -> `bctrl`
(or `bctr`, a tail call). The object register rO is traced back up to 12 instructions for `lwz rO, lo(rH)` after
`lis rH, hi` (a global pointer) - printed as 'obj [GLOBAL]'; --global G keeps only those sites. With --classes the
containing function's retail partner / class / area from work/tu_funcdiff/classes.tsv is added.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_vcall_scan.py IMAGE SLOT[,SLOT..] [--global 0x82efc780] [--classes FILE] [--window 8]
Only addresses and decoded operands are printed.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS
import ppc_xrefs as P


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


def main(argv):
    glob, classes, win = None, None, 8
    for opt in ('--global', '--classes', '--window'):
        if opt in argv:
            k = argv.index(opt); v = argv[k + 1]; del argv[k:k + 2]
            if opt == '--global': glob = int(v, 16)
            elif opt == '--classes': classes = v
            else: win = int(v)
    if len(argv) != 2:
        sys.exit(__doc__)
    d, secs = P.load(argv[0])
    funcs = P.pdata(d, secs)
    slots = set(int(x, 16) for x in argv[1].split(','))
    info = {}
    if classes:
        with open(classes, encoding='utf-8') as f:
            f.readline()
            for line in f:
                v = line.rstrip('\n').split('\t')
                if v[0]:
                    info[int(v[0], 16)] = 'retail %s %s %s' % (v[1] or '-', v[4], v[5])
    n = 0
    for name, start, size, ch in XS.sections(d, 0x82000000):
        if not (ch & 0x20):
            continue
        off = start - 0x82000000
        m = min(size, len(d) - off) // 4
        w = struct.unpack_from('>%dI' % m, d, off)
        for i in range(m):
            x = w[i]
            if x >> 26 != 32 or (x & 0xffff) not in slots:          # lwz rF, SLOT(rV)
                continue
            rf, rv, slot = (x >> 21) & 31, (x >> 16) & 31, x & 0xffff
            ok = False
            for j in range(i + 1, min(m, i + win)):
                y = w[j]
                if y == (0x7c0903a6 | (rf << 21)):                  # mtctr rF
                    for q in range(j + 1, min(m, j + 4)):
                        if w[q] in (0x4e800421, 0x4e800420):
                            ok = True
                    break
            if not ok:
                continue
            ro, gl = None, None
            for j in range(i - 1, max(-1, i - win), -1):
                y = w[j]
                if y >> 26 == 32 and (y >> 21) & 31 == rv and (y & 0xffff) == 0:
                    ro = (y >> 16) & 31
                    for q in range(j - 1, max(-1, j - 12), -1):
                        z = w[q]
                        if z >> 26 == 32 and (z >> 21) & 31 == ro:
                            rh = (z >> 16) & 31
                            for u in range(q - 1, max(-1, q - 12), -1):
                                t = w[u]
                                if t >> 26 == 15 and (t >> 16) & 31 == 0 and (t >> 21) & 31 == rh:
                                    gl = (((t & 0xffff) << 16) + s16(z & 0xffff)) & 0xffffffff
                                    break
                            break
                    break
            if glob is not None and gl != glob:
                continue
            va = start + 4 * i
            f = P.func_of(funcs, va)
            print('0x%08x  slot 0x%x  obj %s  in %s %s' % (va, slot, ('[0x%08x]' % gl) if gl else '?',
                                                          ('0x%08x' % f[0]) if f else '?',
                                                          info.get(f[0], '') if f else ''))
            n += 1
    print('%d sites' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
