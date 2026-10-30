"""Xbox Symbol id -> PC Symbol id as the DLC converter maps it (dlc_generic.DlcIds.sym, read-only), plus the
mapping route (base map, extra, DLC-new shift, interpolated, guess). Ids decimal or 0x-hex. Finding 43: the target
paths of UI timeline descriptors are script member Symbols stored as inline u16 arrays.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/sym_lookup.py 0x07b9 0x0266 ...
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dlc_generic as DG


def main(argv):
    ids = DG.DlcIds()
    print('symbol map: %s' % ids.sym_info)
    for a in argv:
        xs = int(a, 0)
        ids.sym_stats = collections.Counter()
        pc = ids.sym(xs)
        print('xbox %5d (0x%04x) -> pc %5d (0x%04x)  %s' % (xs, xs, pc, pc, ', '.join(ids.sym_stats)))


if __name__ == '__main__':
    main(sys.argv[1:])
