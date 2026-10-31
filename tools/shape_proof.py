"""Prove a field layout for one block shape of a DTP on the base game's Xbox/PC pair, then apply it to a target
(finding 43, rock vein: transitions of the DLC 2 player state chart). Read-only unless --out is given.

A block = relocation target up to the next target; its shape = (size, relative offsets of its pointer words). LAYOUT
is a list of field codes covering the block: h = u16, b = u8, w = u32, p = pointer word (kept), e.g. for the 20-byte
transition {u16 target state, u16, u16 count, u16, ptr, ptr, u32}: "hhhhppw".
Proof: every reference Xbox block of the shape is converted with LAYOUT; the multiset of results must equal the
multiset of the PC reference blocks of the shape (pointer words masked). Then the target blocks of that shape are
re-converted from their Xbox bytes (pointer / id-ref words untouched).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/shape_proof.py XREF.drm PCREF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID SIZE PTROFFS LAYOUT
        [--out OUT.drm] [--show N]
  SIZE hex; PTROFFS comma list of hex offsets ('-' for none)
"""
import sys, os, struct, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

SZ = {'h': 2, 'b': 1, 'w': 4, 'p': 4}


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7:
            r = R.parse(bytes(s.reloc), e)
            return D, s, bytes(s.data), dict(r.internal), set(r.pointer_offsets()) | set(r.id_offsets())
    raise SystemExit('DTP %d not in %s' % (sid, path))


def shaped(d, internal, size, ptroffs):
    t = sorted(set(internal.values()) | {0})
    byb = collections.defaultdict(list)
    for o in internal:
        k = bisect.bisect_right(t, o) - 1
        byb[t[k]].append(o - t[k])
    out = []
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(d)
        if end - a == size and tuple(sorted(byb.get(a, ()))) == ptroffs: out.append(a)
    return out


def convert(xb, layout):
    out = bytearray(); o = 0
    for c in layout:
        n = SZ[c]; f = xb[o:o + n]
        out += f if c in 'bp' else f[::-1]
        o += n
    return bytes(out)


def mask(b, ptroffs):
    b = bytearray(b)
    for f in ptroffs: b[f:f + 4] = b'\0\0\0\0'
    return bytes(b)


def main(argv):
    out = None; show = 10
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    size = int(argv[7], 16)
    ptroffs = () if argv[8] == '-' else tuple(sorted(int(x, 16) for x in argv[8].split(',')))
    layout = argv[9]
    if sum(SZ[c] for c in layout) != size: raise SystemExit('layout covers %d bytes, block has %d' % (sum(SZ[c] for c in layout), size))
    _, _, xr, xri, _ = load(argv[0], 'be', int(argv[2]))
    _, _, pr, pri, _ = load(argv[1], 'le', int(argv[3]))
    xs = shaped(xr, xri, size, ptroffs); ps = shaped(pr, pri, size, ptroffs)
    xc = collections.Counter(mask(convert(xr[a:a + size], layout), ptroffs) for a in xs)
    pc = collections.Counter(mask(pr[a:a + size], ptroffs) for a in ps)
    common = sum((xc & pc).values())
    print('reference: Xbox %d blocks, PC %d blocks, %d identical after conversion "%s"' % (len(xs), len(ps), common, layout))
    if '--dump' in sys.argv and len(xs) <= 3 and len(ps) <= 3:     # small shapes: show the reference words side by side
        for a, b in zip(xs, ps):
            print('  ref Xbox +0x%x / PC +0x%x' % (a, b))
            for o in range(0, size, 4):
                print('    +0x%02x  xbox %s  pc %s' % (o, xr[a + o:a + o + 4].hex(), pr[b + o:b + o + 4].hex()))
    XD, s2, xd, xdi, xdp = load(argv[4], 'be', int(argv[6]))
    PD, ps2, pd, pdi, pdp = load(argv[5], 'le', int(argv[6]))
    ts = shaped(xd, xdi, size, ptroffs)
    newd = bytearray(pd); nch = 0
    for a in ts:
        y = convert(xd[a:a + size], layout)
        for o in range(0, size, 4):
            if a + o in xdp or a + o in pdp: continue
            if bytes(newd[a + o:a + o + 4]) != y[o:o + 4]:
                if nch < show:
                    print('  +0x%05x+0x%x  PC %s -> %s' % (a, o, bytes(newd[a + o:a + o + 4]).hex(), y[o:o + 4].hex()))
                nch += 1
                newd[a + o:a + o + 4] = y[o:o + 4]
    print('target: %d blocks of the shape, %d words changed' % (len(ts), nch))
    if out:
        ps2.data = bytes(newd)
        raw = PD.write('le')
        if open(argv[5], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out, 'wb').write(raw)
        DW.read(open(out, 'rb').read(), 'le')
        print('written %s' % out)


if __name__ == '__main__':
    main(sys.argv[1:])
