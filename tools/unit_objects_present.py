"""Objects a unit requests (objlist.dat) and whether each object's DRM exists in a game archive (read-only).

Question (deleted extended ending): is everything l7_himalaya_end needs (co_amanda, co_cine343_rock, ...) still on the
PC disc, or is something missing (a forum poster said the files seem broken)?

Usage (from the repository root):
  ../bin/pyt -t 300 tools/unit_objects_present.py SOURCE UNIT [UNIT ...]
    SOURCE: pcbig / xbase / ... (tools/locals.py); lists: work/generic/lists/pc_* for pc sources, xbox_* otherwise
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
import objlists as OL

LISTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'lists')


def main(argv):
    src, units = argv[0], [u.lower() for u in argv[1:]]
    path, e, pre = LC.SRC[src]
    pfx = 'pc' if pre == 'pc-w' else 'xbox'
    names = OL.read_objectlist(open(os.path.join(LISTS, pfx + '_objectlist.txt'), 'rb').read())
    recs, _ = OL.read_objlist(open(os.path.join(LISTS, pfx + '_objlist.dat'), 'rb').read(), e)
    A = Archive(path, e)
    for u in units:
        lst = [ids for n, ids in recs if n.lower() == u]
        if not lst: print('%s: not in objlist.dat' % u); continue
        miss = 0
        print('%s: %d objects' % (u, len(lst[0])))
        for oid in lst[0]:
            nm = names.get(oid, '?')
            ok = bool(A.find(crc(pre + '\\' + nm + '.drm')))
            miss += not ok
            print('  %5d  %-45s %s' % (oid, nm, 'present' if ok else 'MISSING'))
        print('%s: %d missing' % (u, miss))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
