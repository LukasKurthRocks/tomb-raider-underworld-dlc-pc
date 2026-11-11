"""Q89 / Q80: which objects reference given object ids, read only.

For every object listed by the given units (objlist.dat) plus extra names: child id list (type-11 root DTP +0x48, the
list the loader requests, tools/child_list_scope.py plist) and a plain u16 / u32 scan of every type-7 / type-8 section
for the wanted ids (a scan hit is only a candidate: any 16-bit value can match). Also prints the unit's full object list
(id name) so a test level's resident set is visible.

Usage (from the repository root):
  ../bin/pyt -t 1800 work/q89_skeleton_1111/who_uses.py MODS_DIR --units U1,U2 --ids 769,792 [--extra NAME,NAME]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'q83_allenemies_1111'))
import drm_write as DW
import objlists as OL
from enemy_catalog import Src
from child_list_scope import plist


def main(argv):
    mods = argv[0]
    units = argv[argv.index('--units') + 1].split(',')
    ids = [int(x) for x in argv[argv.index('--ids') + 1].split(',')]
    extra = argv[argv.index('--extra') + 1].split(',') if '--extra' in argv else []
    lst = os.path.join(mods, 'tr8', 'pc-w')
    names = OL.read_objectlist(open(os.path.join(lst, 'objectlist.txt'), 'rb').read())
    recs, _ = OL.read_objlist(open(os.path.join(lst, 'objlist.dat'), 'rb').read(), 'le')
    byname = {v: k for k, v in names.items()}
    S = Src(mods)
    todo = []
    for u, oids in recs:
        if u in units:
            print('unit %s: %d objects: %s' % (u, len(oids), ' '.join('%d:%s' % (i, names.get(i, '?')) for i in oids)))
            todo += oids
    todo += [byname[n] for n in extra if n in byname]
    seen = set()
    for oid in todo:
        if oid in seen:
            continue
        seen.add(oid)
        nm = names.get(oid)
        g = S.get(nm) if nm else None
        if g is None:
            continue
        D = DW.read(g[2], 'le')
        r = plist(D)
        kids = r[2] if r else []
        hit_k = [k for k in kids if k in ids]
        scan = []
        for s in D.sections:
            if s.type not in (7, 8):
                continue
            d = s.data
            for w in ids:
                p16 = struct.pack('<H', w)
                o = d.find(p16)
                n = 0
                while o >= 0:
                    if o % 2 == 0:
                        n += 1
                    o = d.find(p16, o + 1)
                if n:
                    scan.append('%d in sec type %d id %d x%d' % (w, s.type, s.id, n))
        if hit_k or (scan and oid not in ids):
            print('%d %s: child list %s | child hits %s | u16 scan %s' % (oid, nm, kids, hit_k, '; '.join(scan[:6])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
