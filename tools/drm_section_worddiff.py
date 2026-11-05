"""Word-level diff of ONE section between two PC (little-endian) DRM files, read-only: every 32-bit word of the common
part that differs (offset, old, new, the walker label of the old section for scripts), the size change, and the
relocation changes (internal pointers whose target moved, entries added / removed per kind, external / id entries that
point into the common part). Written for the pause-menu port (generalbank script 7, 2026-11-03): proof that a patched
script differs from its base only where intended.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_worddiff.py A.drm B.drm TYPE ID
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    a, b, ty, sid = argv[0], argv[1], int(argv[2]), int(argv[3])
    A = next(s for s in DW.read(open(a, 'rb').read(), 'le').sections if s.type == ty and s.id == sid)
    B = next(s for s in DW.read(open(b, 'rb').read(), 'le').sections if s.type == ty and s.id == sid)
    lab = {}
    if ty == 8:
        import script_conv as SC
        W = SC.Walk(A.data, R.parse(A.reloc, 'le'), 'le').run(); lab = W.lab
    m = min(len(A.data), len(B.data))
    print('section (%d, %d): %d -> %d bytes (%+d)' % (ty, sid, len(A.data), len(B.data), len(B.data) - len(A.data)))
    n = 0
    for o in range(0, m - 3, 4):
        x, y = A.data[o:o + 4], B.data[o:o + 4]
        if x != y:
            n += 1
            print('  word +0x%05x  %08x -> %08x  %s' % (o, struct.unpack('<I', x)[0], struct.unpack('<I', y)[0], lab.get(o, '')))
    print('words differing in the common part: %d' % n)
    ra, rb = R.parse(A.reloc, 'le'), R.parse(B.reloc, 'le')
    ia, ib = dict(ra.internal), dict(rb.internal)
    moved = [(o, ia[o], ib[o]) for o in ia if o in ib and ia[o] != ib[o]]
    print('internal pointers: %d -> %d; same source, other target: %d' % (len(ia), len(ib), len(moved)))
    for o, t0, t1 in moved: print('  ptr +0x%05x  -> +0x%x  now -> +0x%x  %s' % (o, t0, t1, lab.get(o, '')))
    gone = [o for o in ia if o not in ib]
    print('internal pointers removed: %d' % len(gone))
    new_common = sorted(o for o in ib if o not in ia and o < m)
    print('internal pointers added with a source in the common part: %d %s' % (len(new_common), [hex(o) for o in new_common][:10]))
    for kind in ('external', 'idref', 'idref_a', 'unk3'):
        sa, sb = set(getattr(ra, kind)), set(getattr(rb, kind))
        src = (lambda e: e[1]) if kind == 'external' else (lambda e: e[1] if isinstance(e, tuple) else 0)
        print('%s: %d -> %d, removed %d, added %d (added with a source in the common part: %d)' % (
            kind, len(sa), len(sb), len(sa - sb), len(sb - sa), sum(1 for e in sb - sa if src(e) < m)))


if __name__ == '__main__':
    main(sys.argv[1:])
