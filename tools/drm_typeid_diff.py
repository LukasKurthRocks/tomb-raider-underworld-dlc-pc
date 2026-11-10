"""Compare two DRMs by section (type, id) instead of position (read-only): per section type how many sections
exist in both / only in one, and of the common ones how many have equal data, equal size, other size.
Built for the language-variant survey (one object DRM of two retail PC builds, e.g. generalbank.drm).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_typeid_diff.py A.drm B.drm [--be] [--list TYPE]
      --list TYPE: print the (type, id) keys of that type that are only in A / only in B / differ
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def keyed(D):
    out = collections.OrderedDict()
    for i, s in enumerate(D.sections):
        k = (s.type, s.id)
        while k in out: k = (k[0], k[1], len(k))      # duplicate (type, id): keep apart by occurrence
        out[k] = (i, s)
    return out


def main(argv):
    lst = None
    if '--list' in argv: k = argv.index('--list'); lst = int(argv[k + 1]); del argv[k:k + 2]
    en = 'be' if '--be' in argv else 'le'; argv = [a for a in argv if a != '--be']
    if len(argv) != 2: sys.exit(__doc__)
    A, B = (keyed(DW.read(open(p, 'rb').read(), en)) for p in argv)
    print('sections: A %d, B %d' % (len(A), len(B)))
    types = sorted(set(k[0] for k in A) | set(k[0] for k in B))
    print('%5s %7s %7s %7s %7s %7s %7s %7s' % ('type', 'A', 'B', 'common', 'onlyA', 'onlyB', 'equal', 'othsize'))
    for t in types:
        ka = [k for k in A if k[0] == t]; kb = [k for k in B if k[0] == t]
        com = [k for k in ka if k in B]
        eq = sum(1 for k in com if A[k][1].data == B[k][1].data)
        osz = sum(1 for k in com if len(A[k][1].data) != len(B[k][1].data))
        print('%5d %7d %7d %7d %7d %7d %7d %7d' % (t, len(ka), len(kb), len(com), len(ka) - len(com),
                                                    sum(1 for k in kb if k not in A), eq, osz))
        if lst == t:
            print('  only A: %s' % ' '.join(str(k[1]) for k in ka if k not in B))
            print('  only B: %s' % ' '.join(str(k[1]) for k in kb if k not in A))
            print('  differ: %s' % ' '.join('%d(%d/%d)' % (k[1], len(A[k][1].data), len(B[k][1].data))
                                            for k in com if A[k][1].data != B[k][1].data))


if __name__ == '__main__':
    main(sys.argv[1:])
