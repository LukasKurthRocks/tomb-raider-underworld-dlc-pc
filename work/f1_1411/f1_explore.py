"""F1 (2026-11-14): explore the cell stream list layout in a converted unit DRM (PC, LE). Read-only.
Prints the Level section relocs (which offsets point where), and for section SECID the internal relocs whose target
lies in [LO, HI) plus the words of that range.
Usage (repository root): ../bin/pyt -t 300 work/f1_1411/f1_explore.py DRM SECID LO HI
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R


def main(a):
    path, sid, lo, hi = a[0], int(a[1]), int(a[2], 0), int(a[3], 0)
    D = DW.read(open(path, 'rb').read(), 'le')
    S = D.sections
    for i, s in enumerate(S[:3]):
        r = R.parse(s.reloc, 'le')
        print('sec#%d type %d id %d size %d ext %s' % (i, s.type, s.id, len(s.data),
              [(si, hex(so), hex(do), S[si].type, S[si].id) for si, so, do in r.external][:40]))
    idx = [i for i, s in enumerate(S) if s.id == sid and s.type == 7]
    print('sections with id', sid, idx)
    k = idx[0]; s = S[k]; d = s.data
    r = R.parse(s.reloc, 'le')
    print('size %d internal %d external %d' % (len(d), len(r.internal), len(r.external)))
    for so, do in sorted(r.internal):
        if lo - 0x100 <= do < hi or lo - 0x100 <= so < hi: print('  int  src 0x%05x -> 0x%05x' % (so, do))
    for si, so, do in r.external:
        if lo - 0x100 <= so < hi: print('  ext  src 0x%05x -> sec#%d(%d:%d) 0x%x' % (so, si, S[si].type, S[si].id, do))
    # who points at this section from other sections
    for i, q in enumerate(S):
        for si, so, do in R.parse(q.reloc, 'le').external:
            if si == k: print('  in   sec#%d(%d:%d) +0x%x -> 0x%x' % (i, q.type, q.id, so, do))
    for o in range(lo - 0x40, hi, 16):
        w = [struct.unpack_from('<I', d, o + j)[0] for j in range(0, 16, 4) if o + j + 4 <= len(d)]
        h = [struct.unpack_from('<HH', d, o + j) for j in range(0, 16, 4) if o + j + 4 <= len(d)]
        print('  +0x%05x %s   %s' % (o, ' '.join('%08x' % x for x in w), ' '.join('%d/%d' % x for x in h)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
