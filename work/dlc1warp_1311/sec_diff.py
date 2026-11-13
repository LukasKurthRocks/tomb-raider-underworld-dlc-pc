"""Per-section difference of two PC (LE) DRM files (read-only): for every (type, id) say equal / data words differ /
size differs / reloc differs / only in one file. Media sections (texture, wave, shader lib, material, mesh) are
summarised as counts only unless --all.

Usage (from trudlcport): ../bin/pyt -t 300 work/dlc1warp_1311/sec_diff.py A.drm B.drm [--all] [--types 0,7,8,11]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW

MEDIA = {5, 6, 9, 10, 12}


def secs(p):
    out = collections.OrderedDict()
    for k, s in enumerate(DW.read(open(p, 'rb').read(), 'le').sections):
        key = (s.type, s.id)
        if key in out:
            key = (s.type, s.id, k)
        out[key] = s
    return out


def main(argv):
    a, b = argv[0], argv[1]
    allm = '--all' in argv
    types = None
    if '--types' in argv:
        types = set(int(x) for x in argv[argv.index('--types') + 1].split(','))
    A, B = secs(a), secs(b)
    cnt = collections.Counter()
    for key in list(A) + [k for k in B if k not in A]:
        t = key[0]
        if types is not None and t not in types:
            continue
        sa, sb = A.get(key), B.get(key)
        if sa is None or sb is None:
            st = 'only A' if sb is None else 'only B'
            cnt[(t, st)] += 1
            if allm or t not in MEDIA:
                print('%-8s type %2d id %6d size %s' % (st, t, key[1], len((sa or sb).data or b'')))
            continue
        da, db = sa.data or b'', sb.data or b''
        ra, rb = sa.reloc or b'', sb.reloc or b''
        if da == db and ra == rb:
            cnt[(t, 'equal')] += 1
            continue
        n = min(len(da), len(db)) // 4
        wd = sum(1 for i in range(n) if da[4 * i:4 * i + 4] != db[4 * i:4 * i + 4])
        st = 'differ'
        cnt[(t, st)] += 1
        if allm or t not in MEDIA:
            print('differ   type %2d id %6d size %d/%d words %d reloc %s' % (
                t, key[1], len(da), len(db), wd, 'same' if ra == rb else 'diff (%d/%d)' % (len(ra), len(rb))))
    print('summary', sorted(cnt.items()))


if __name__ == '__main__':
    main(sys.argv[1:])
