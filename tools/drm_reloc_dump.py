"""Print every relocation of one DRM section: internal pointers, external pointers (into another section of the same
DRM, with that section's type / id) and id references (read-only; shadow combat night 2026-11-04: where the
generalbank object (type 11 id 1) points, i.e. which section holds GlobalInfo and its input map +0x1c).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/drm_reloc_dump.py FILE.drm TYPE ID [--be] [--from HEX] [--to HEX]
  --be       Xbox (big-endian) DRM
  --from/--to only relocations whose source offset lies in [FROM, TO)
  ../bin/pyt -t 120 tools/drm_reloc_dump.py FILE.drm find OFF[,OFF..] [--be]
             every section that has a pointer (internal or external) at all the given source offsets (hex)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv
    argv = [a for a in argv if a != '--be']
    lo, hi = 0, 1 << 32
    if '--from' in argv: k = argv.index('--from'); lo = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--to' in argv: k = argv.index('--to'); hi = int(argv[k + 1], 16); del argv[k:k + 2]
    if len(argv) < 3: sys.exit(__doc__)
    e = 'be' if be else 'le'
    D = DW.read(open(argv[0], 'rb').read(), e)
    if argv[1] == 'find':
        want = set(int(x, 16) for x in argv[2].split(','))
        for si, s in enumerate(D.sections):
            if not s.reloc: continue
            r = R.parse(bytes(s.reloc), e)
            have = set(o for o, _ in r.internal) | set(o for _, o, _ in r.external)
            if want <= have: print('section %d type %d id %d size 0x%x' % (si, s.type, s.id, len(s.data)))
        return
    typ, sid = int(argv[1]), int(argv[2])
    hits = [(i, s) for i, s in enumerate(D.sections) if s.type == typ and s.id == sid]
    if not hits: sys.exit('section type %d id %d not found' % (typ, sid))
    for si, s in hits:
        r = R.parse(bytes(s.reloc), e)
        print('== section %d type %d id %d size 0x%x  (%r)' % (si, s.type, s.id, len(s.data), r))
        for o, t in sorted(r.internal):
            if lo <= o < hi: print('  int  +0x%05x -> +0x%x' % (o, t))
        for di, o, t in sorted(r.external, key=lambda x: x[1]):
            if lo <= o < hi:
                d = D.sections[di] if di < len(D.sections) else None
                print('  ext  +0x%05x -> section %d (type %s id %s) +0x%x' % (o, di, d.type if d else '?',
                                                                           d.id if d else '?', t))
        for ty, o in sorted(r.idref_a, key=lambda x: x[1]):
            if lo <= o < hi: print('  idA  +0x%05x type %d' % (o, ty))
        for ty, o in sorted(r.idref, key=lambda x: x[1]):
            if lo <= o < hi: print('  id   +0x%05x type %d' % (o, ty))


if __name__ == '__main__':
    main(sys.argv[1:])
