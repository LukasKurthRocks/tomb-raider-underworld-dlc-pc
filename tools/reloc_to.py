"""Internal relocations of one DRM section that point into given ranges (who points at a structure) - read-only;
finding 43, rock vein state chart (which transition / state holds a condition record).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/reloc_to.py FILE.drm SECTION_ID LO[-HI][,LO[-HI]..] [--be] [--up N]
  --up N   also follow the chain upwards N times (pointers to the start of the struct holding the found pointer,
           taken as the nearest relocation target at or below it)
"""
import sys, os, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv; argv = [a for a in argv if a != '--be']
    up = 0
    if '--up' in argv: k = argv.index('--up'); up = int(argv[k + 1]); del argv[k:k + 2]
    e = 'be' if be else 'le'
    D = DW.read(open(argv[0], 'rb').read(), e)
    sid = int(argv[1])
    rng = []
    for part in argv[2].split(','):
        lo, _, hi = part.partition('-')
        rng.append((int(lo, 16), int(hi, 16) if hi else int(lo, 16)))
    for s in D.sections:
        if s.id != sid or s.type != 7: continue
        it = R.parse(bytes(s.reloc), e).internal
        targets = sorted(set(t for _, t in it))
        level = 0
        while True:
            hits = [(o, t) for o, t in it if any(lo <= t <= hi for lo, hi in rng)]
            for o, t in sorted(hits):
                print('%s+0x%05x -> +0x%05x' % ('  ' * level, o, t))
            if level >= up or not hits: break
            level += 1
            rng = []
            for o, _ in hits:
                k = bisect.bisect_right(targets, o) - 1
                if k >= 0: rng.append((targets[k], targets[k]))
            print('%s(struct starts: %s)' % ('  ' * level, ', '.join('+0x%x' % a for a, _ in sorted(set(rng)))))


if __name__ == '__main__':
    main(sys.argv[1:])
