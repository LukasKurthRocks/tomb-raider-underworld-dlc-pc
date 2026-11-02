"""Add object ids to the per-unit object lists of a PC objlist.dat (the objects a unit loads with it), read the input,
write a new file. Test 50k: the cut object dlc2_uo_jump_target (1042) is named by the final object list but no unit of
the final objlist.dat requests it (the Lara's Shadow prototype's dlc2_machine_room did).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/objlist_add.py IN_OBJLIST.dat OBJECTLIST.txt OUT_OBJLIST.dat UNIT=NAME[,NAME] [UNIT=...]
  UNIT = the unit record name as in objlist.dat (e.g. dlc2_machine_room; matched on the last path part, case-insensitive)
  NAME = object name from OBJECTLIST.txt (or a numeric id). The ids are inserted in ascending order (the format keeps
  each list sorted); the tool prints the record before / after and re-reads the written file.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objlists as OL


def main(argv):
    src, olist, dst = argv[0], argv[1], argv[2]
    names = OL.read_objectlist(open(olist, 'rb').read())
    by_name = {v.lower(): k for k, v in names.items()}
    recs, first = OL.read_objlist(open(src, 'rb').read(), 'le')
    recs = [(n, list(l)) for n, l in recs]
    for spec in argv[3:]:
        unit, objs = spec.split('=', 1)
        ids = [int(o) if o.isdigit() else by_name[o.lower()] for o in objs.split(',')]
        hit = [i for i, (n, _) in enumerate(recs) if n.lower().replace('/', '\\').split('\\')[-1] == unit.lower()]
        if len(hit) != 1: sys.exit('unit %s: %d records match' % (unit, len(hit)))
        n, l = recs[hit[0]]
        before = len(l)
        for i in ids:
            if i not in l: l.append(i)
        l.sort()
        recs[hit[0]] = (n, l)
        print('%s (record %d): %d -> %d objects, added %s' % (n, hit[0] + 1, before, len(l),
              ', '.join('%d %s' % (i, names.get(i, '?')) for i in ids)))
    out = OL.write_objlist(recs, 'le', first)
    open(dst, 'wb').write(out)
    back, _ = OL.read_objlist(out, 'le')
    assert [(n, list(l)) for n, l in back] == recs
    print('written %s (%d bytes, %d unit records), re-read ok' % (dst, len(out), len(recs)))


if __name__ == '__main__':
    if len(sys.argv) < 5: sys.exit(__doc__)
    main(sys.argv[1:])
