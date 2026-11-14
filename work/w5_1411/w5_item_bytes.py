"""W5 (2026-11-14): compare the whole 0xb0-byte markup2 items (unit DTP +0x30 list) and their point arrays of a PC unit
DRM against the Xbox original word by word (PC word = Xbox word byte-reversed, except +0x48 / +0x4c: two u16 / four
bytes), and the point arrays (count +0x9c, stride 0x20, every word reversed). Prints only differing words.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_item_bytes.py PC.drm XBOX.drm
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R
import markup_level as ML


def load(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    rel = []
    for s in D.sections:
        r = R.parse(bytes(s.reloc), e)
        rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
    return D, rel


def items(D, rel, f):
    t = ML.target(D, rel, 0, 0x74)
    ds, do = t
    dd = bytes(D.sections[ds].data)
    n = struct.unpack_from(f + 'I', dd, do + 0x2c)[0]
    lst = ML.target(D, rel, ds, do + 0x30)
    out = {}
    for k in range(n):
        it = ML.target(D, rel, lst[0], lst[1] + 4 * k)
        si, o = it
        d = bytes(D.sections[si].data)
        iid = struct.unpack_from(f + 'H', d, o + 0x48)[0]
        relw = set(w for w in range(0, 0xb0, 4) if ML.target(D, rel, si, o + w))
        pp = ML.target(D, rel, si, o + 0xa0)
        cnt = struct.unpack_from(f + 'i', d, o + 0x9c)[0]
        pts = b''
        if pp and 0 < cnt < 4096:
            pts = bytes(D.sections[pp[0]].data)[pp[1]:pp[1] + 0x20 * cnt]
        out[iid] = (d[o:o + 0xb0], relw, pts, k)
    return out


def main(argv):
    P, PR = load(argv[0], 'le'); X, XR = load(argv[1], 'be')
    a = items(P, PR, '<'); b = items(X, XR, '>')
    bad_items = 0
    for iid in sorted(set(a) | set(b)):
        if iid not in a or iid not in b:
            print('id %d only in %s' % (iid, 'PC' if iid in a else 'Xbox')); bad_items += 1; continue
        pd, prel, ppts, k = a[iid]; xd, xrel, xpts, _ = b[iid]
        diffs = []
        for w in range(0, 0xb0, 4):
            if w in prel or w in xrel:          # relocated pointers: values differ by layout
                continue
            pw, xw = pd[w:w + 4], xd[w:w + 4]
            if w == 0x48: good = pw[0:2] == xw[0:2][::-1] and pw[2:4] == xw[2:4][::-1]
            elif w == 0x4c: good = pw == xw
            else: good = pw == xw[::-1]
            if not good: diffs.append('+%02x PC %s Xbox %s' % (w, pw.hex(), xw.hex()))
        if len(ppts) != len(xpts): diffs.append('point bytes %d / %d' % (len(ppts), len(xpts)))
        else:
            for w in range(0, len(ppts), 4):
                if ppts[w:w + 4] != xpts[w:w + 4][::-1]:
                    diffs.append('point word +%x PC %s Xbox %s' % (w, ppts[w:w + 4].hex(), xpts[w:w + 4].hex()))
        if diffs:
            bad_items += 1
            print('id %d (item %d): %d differing words: %s' % (iid, k, len(diffs), '; '.join(diffs[:8])))
    print('%s vs %s: %d items PC, %d Xbox, %d with differences' % (os.path.basename(argv[0]), os.path.basename(argv[1]),
                                                                     len(a), len(b), bad_items))


if __name__ == '__main__':
    main(sys.argv[1:])
