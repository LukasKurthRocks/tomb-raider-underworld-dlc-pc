"""Q74 (2026-11-11): list the DRM names in PC patch.000 (1.1) and whether bigfile.000 (1.0 content) has the same name
(read-only). Names come from tools/hidden_scan.name_map('pc-w') (the same name map tools/unused_scan.py uses).

Usage (from the repository root):
  ../bin/pyt -t 300 work/q74_spots_1111/q74_patch_list.py [--grep TEXT]
Prints one line per patch entry: name, size in patch, 'also in bigfile' or 'patch only'; unnamed hashes are counted.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import locals as LC
from archive import Archive
from hidden_scan import name_map


def main(argv):
    g = argv[argv.index('--grep') + 1].lower() if '--grep' in argv else None
    nm = name_map('pc-w')
    P = Archive(LC.SRC['pcpatch'][0], 'le')
    B = Archive(LC.SRC['pcbig'][0], 'le')
    bh = set(r['hash'] for r in B.idx)
    unnamed = 0
    rows = []
    for r in P.idx:
        n = nm.get(r['hash'])
        if not n:
            unnamed += 1
            continue
        if g and g not in n.lower():
            continue
        rows.append('%s | %s' % (n, 'also in bigfile' if r['hash'] in bh else 'patch only'))
    for x in sorted(set(rows)):
        print(x)
    print('patch entries %d, named shown %d, unnamed %d' % (len(P.idx), len(set(rows)), unnamed))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
