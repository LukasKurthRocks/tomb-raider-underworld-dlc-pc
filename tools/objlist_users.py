"""Which units load an object (read-only): looks up object names / ids in an objlist.dat and lists the units whose
object lists contain them. Uses the objlist.dat / objectlist.txt parsers of tools/objlists.py (formats there).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/objlist_users.py OBJLIST.DAT OBJECTLIST.TXT le|be NAME_OR_ID [NAME_OR_ID ...]
  ../bin/pyt -t 120 tools/objlist_users.py OBJLIST.DAT OBJECTLIST.TXT le|be --unused   (every object no unit loads)
  e.g. work/generic/lists/dlc_pack10_objlist.dat work/generic/lists/dlc_pack10_objectlist.txt be wp_dlc_gold_shotgun
Prints, per object: id, name and every unit (record name of objlist.dat) that lists it - or "no unit".
Only names and ids are printed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objlists as O


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    dat, olist, endian, wanted = argv[0], argv[1], argv[2], argv[3:]
    objects = O.read_objectlist(open(olist, 'rb').read())          # {id: name}
    recs, _first = O.read_objlist(open(dat, 'rb').read(), endian)  # [(unit name, [object ids])]
    by_name = {v.lower(): k for k, v in objects.items()}
    if wanted == ['--unused']:
        used = set()
        for _unit, ids in recs:
            used.update(ids)
        free = [k for k in sorted(objects) if k not in used]
        print('%d objects, %d loaded by no unit:' % (len(objects), len(free)))
        for k in free:
            print('%5d %s' % (k, objects[k]))
        return 0
    for w in wanted:
        oid = int(w, 0) if w[:1].isdigit() else by_name.get(w.lower())
        if oid is None:
            print('%s: not in %s' % (w, olist))
            continue
        name = objects.get(oid, '?')
        units = [r[0] for r in recs if oid in r[1]]
        print('%s (id %d): %s' % (name, oid, ', '.join(units) if units else 'no unit'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
