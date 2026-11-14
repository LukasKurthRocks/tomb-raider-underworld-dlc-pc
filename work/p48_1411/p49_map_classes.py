"""P4.9 (2026-11-14): word classes of the *_map.drm collision mesh section, per region (read-only).

Regions of the mesh section (the one with the mesh header, found by the w1_map_bvh pointer scan on the Xbox side):
header 0x58 B (BBox / position floats, 3 pointers, counts, u16 vertexType / height), vertices, faces, KD nodes (16 B:
float, float, u32, 4 bytes), the rest. Every 4-byte word is classed Xbox -> PC: same / s32 / s16 / raw / other.
For the nodes the last word (+0xc) is the one of interest (P4.9: bytes axis / leaf count / 2 bytes).

Usage (from the repository root):
  ../bin/pyt -t 900 work/p48_1411/p49_map_classes.py base NAME_map.drm [...]   (Xbox base TU / layer vs PC base game)
  ../bin/pyt -t 900 work/p48_1411/p49_map_classes.py dlc PC_FILE.drm [...]     (Xbox DLC source vs a PC file)
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'w1_1411'))
import drm_reloc as R
import dtp_word_classes as C
import w1_map_bvh as B


def cls(x, p):
    if x == p: return 'same'
    if p == x[::-1]: return 's32'
    if p == x[1::-1] + x[:1:-1]: return 's16'
    return 'other'


def regions(S, e, si, h):
    E = '<' if e == 'le' else '>'
    d = S[si].data
    rel = B.rels(S, e)
    nn, nf, nv = struct.unpack_from(E + '3I', d, h + 0x40)
    vt, = struct.unpack_from(E + 'H', d, h + 0x54)
    vo = B.target(rel, si, h + 0x30)[1]; fo = B.target(rel, si, h + 0x34)[1]; no = B.target(rel, si, h + 0x38)[1]
    # face stride from the gap to the next array
    starts = sorted(set([vo, fo, no, h, len(d)]))
    nxt = lambda o: next(s for s in starts if s > o)
    fs = (nxt(fo) - fo) // nf if nf else 0
    fstride = 20 if fs >= 20 else 16
    vstride = 16 if vt == 1 else 6
    reg = [('header', h, 0x58, 4), ('vertices', vo, nv * vstride, 4), ('faces', fo, nf * fstride, fstride),
           ('nodes', no, nn * 16, 16)]
    return reg, dict(nn=nn, nf=nf, nv=nv, vt=vt, fstride=fstride, fgap=nxt(fo) - fo)


def compare(label, X, xe, P, pe):
    RX = B.rels(X, xe)
    M = B.scan_meshes(X, RX, xe)
    if not M:
        print('%s: no mesh header on the Xbox side' % label); return None
    tot = collections.Counter()
    for gi, si, h, nn, nf, nref in M:
        reg, info = regions(X, xe, si, h)
        xd, pd = X[si].data, P[si].data
        if len(xd) != len(pd):
            print('%s: section %d size differs xbox %d pc %d' % (label, si, len(xd), len(pd))); continue
        rx = R.parse(X[si].reloc, xe); skip = set(rx.pointer_offsets()) | set(rx.id_offsets())
        owner = {}
        for name, o, n, stride in reg:
            for w in range(o - o % 4, o + n, 4):
                owner.setdefault(w, (name, (w - o) % stride if stride else 0))
        c = collections.Counter()
        for w in range(0, len(xd) // 4 * 4, 4):
            if w in skip: c['ptr', ''] += 1; continue
            nm, sub = owner.get(w, ('rest', 0))
            k = cls(xd[w:w + 4], pd[w:w + 4])
            if k == 'same' and xd[w:w + 4] == xd[w:w + 4][::-1]: k = 'same(sym)'
            c[nm + '+0x%x' % sub if nm in ('header', 'nodes', 'faces') else nm, k] += 1
        print('%s: mesh %s %s' % (label, gi, info))
        for (r, k), n in sorted(c.items()):
            print('    %-16s %-10s %7d' % (r, k, n))
            tot[r, k] += n
    return tot


def main(argv):
    mode, names = argv[0], argv[1:]
    for n in names:
        if mode == 'base':
            xs = C.find(C.BASE, 'be', 'xenon-w' + C.BS + n); ps = C.find(C.PC, 'le', 'pc-w' + C.BS + n)
            if xs is None or ps is None: print('%s: not found (xbox %s pc %s)' % (n, xs is not None, ps is not None)); continue
            X = [B.Sec(s['type'], s['id'], s['data'], s['reloc']) for s in xs]
            P = [B.Sec(s['type'], s['id'], s['data'], s['reloc']) for s in ps]
            compare('base ' + n, X, 'be', P, 'le')
        else:
            P, pe = B.load_file(n); X, xe = B.load_xbox(os.path.basename(n))
            if X is None: print('%s: no xbox source' % n); continue
            compare('dlc ' + os.path.basename(n), X, xe, P, pe)


if __name__ == '__main__':
    main(sys.argv[1:])
