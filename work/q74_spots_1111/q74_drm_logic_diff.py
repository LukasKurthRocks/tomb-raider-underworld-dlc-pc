"""Q74 (2026-11-11): per (type, id) difference of two PC DRMs of the SAME build (read-only), e.g. bigfile.000 vs
patch.000 copy of l2_puzzleroom (patch 1.1): sections only in A / only in B / with other data or relocations, for
every section type, plus the strings of differing / missing script sections (to name them).

Usage (from the repository root):
  ../bin/pyt -t 300 work/q74_spots_1111/q74_drm_logic_diff.py A.drm B.drm [--data]
"""
import sys, os, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW


def strings(b):
    return [m.decode('ascii', 'replace') for m in re.findall(rb'[\x20-\x7e]{6,}', b)][:6]


def main(argv):
    data_only = '--data' in argv
    argv = [a for a in argv if a != '--data']
    A = DW.read(open(argv[0], 'rb').read(), 'le'); B = DW.read(open(argv[1], 'rb').read(), 'le')
    def index(D):
        d = collections.defaultdict(list)
        for s in D.sections:
            # --data: compare section data only (relocation blobs carry section indices, which shift when the
            # patch removes sections)
            d[(s.type, s.id)].append(bytes(s.data) if data_only else bytes(s.data) + b'|' + bytes(s.reloc))
        return d
    ia, ib = index(A), index(B)
    print('A %d sections, B %d sections' % (len(A.sections), len(B.sections)))
    per = collections.Counter()
    for k in sorted(set(ia) | set(ib)):
        if k not in ib:
            per[(k[0], 'only A')] += 1
            if k[0] in (0, 7, 8, 11): print('only A: type %d id %d (%d B) %s' % (k[0], k[1], len(ia[k][0]), strings(ia[k][0])))
        elif k not in ia:
            per[(k[0], 'only B')] += 1
            if k[0] in (0, 7, 8, 11): print('only B: type %d id %d (%d B) %s' % (k[0], k[1], len(ib[k][0]), strings(ib[k][0])))
        elif sorted(ia[k]) != sorted(ib[k]):
            per[(k[0], 'differ')] += 1
            if k[0] in (0, 7, 8, 11):
                print('differ: type %d id %d (%d -> %d B) %s' % (k[0], k[1], len(ia[k][0]), len(ib[k][0]), strings(ib[k][0])))
        else:
            per[(k[0], 'equal')] += 1
    for (t, c), n in sorted(per.items()):
        print('type %d %s: %d' % (t, c, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
