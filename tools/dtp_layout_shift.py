"""Where does a PC section's layout grow against its Xbox original? (read-only). Pairs the internal relocations of an
Xbox section and a PC section in order (pointer slot offset and target) and prints every run with the same
offset shift (PC - Xbox), so a block the PC version inserts / drops shows up as a step. Also prints the id-reference
slots the same way.
Test 48d (2026-10-31): Lara's model DTP is 256 bytes larger on PC than on the Xbox (x_lara 2517 164 732 -> pc_lara
848 164 988), the converted doppelganger model DTP 20134 kept the Xbox size (220 824) - where is the PC block?

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_layout_shift.py XBOX.drm XBOX_ID PC.drm PC_ID [--type T] [--words]
  --words: also print the PC words of the first 0x40 bytes of every shifted run (hex)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def sec(path, en, sid, typ):
    D = DW.read(open(path, 'rb').read(), en)
    return next(s for s in D.sections if s.id == sid and (typ is None or s.type == typ))


def runs(pairs):
    out = []; cur = None
    for i, (xo, po) in enumerate(pairs):
        d = po - xo
        if cur is None or d != cur[0]:
            cur = [d, xo, po, xo, po, 0]; out.append(cur)
        cur[3], cur[4] = xo, po; cur[5] += 1
    return out


def main(argv):
    typ = None
    if '--type' in argv: k = argv.index('--type'); typ = int(argv[k + 1]); del argv[k:k + 2]
    words = '--words' in argv; argv = [a for a in argv if a != '--words']
    xs = sec(argv[0], 'be', int(argv[1]), typ); ps = sec(argv[2], 'le', int(argv[3]), typ)
    xr = R.parse(xs.reloc, 'be'); pr = R.parse(ps.reloc, 'le')
    print('Xbox %d: %d bytes, %d internal, %d id refs / PC %d: %d bytes, %d internal, %d id refs'
          % (xs.id, len(xs.data), len(xr.internal), len(xr.idref), ps.id, len(ps.data), len(pr.internal), len(pr.idref)))
    xi = sorted(xr.internal); pi = sorted(pr.internal)
    if len(xi) == len(pi):
        print('internal pointer slots (offset shift runs):')
        for d, x0, p0, x1, p1, n in runs([(a[0], b[0]) for a, b in zip(xi, pi)]):
            print('  shift %+5d  Xbox +%#07x..+%#07x  PC +%#07x..+%#07x  %4d slots' % (d, x0, x1, p0, p1, n))
            if words and d: print('     PC  ' + ps.data[p0:p0 + 0x40].hex(' ', 4))
        print('pointer targets (shift runs):')
        for d, x0, p0, x1, p1, n in runs(sorted((a[1], b[1]) for a, b in zip(xi, pi))):
            print('  shift %+5d  Xbox ->%#07x..%#07x  PC ->%#07x..%#07x  %4d targets' % (d, x0, x1, p0, p1, n))
    else:
        print('internal relocation counts differ: %d / %d' % (len(xi), len(pi)))
    xd = sorted(o for t, o in xr.idref); pd = sorted(o for t, o in pr.idref)
    if len(xd) == len(pd):
        print('id reference slots (shift runs):')
        for d, x0, p0, x1, p1, n in runs(list(zip(xd, pd))):
            print('  shift %+5d  Xbox +%#07x..+%#07x  PC +%#07x..+%#07x  %4d refs' % (d, x0, x1, p0, p1, n))
    else:
        print('id reference counts differ: %d / %d' % (len(xd), len(pd)))


if __name__ == '__main__':
    if len(sys.argv) < 5: sys.exit(__doc__)
    main(sys.argv[1:])
