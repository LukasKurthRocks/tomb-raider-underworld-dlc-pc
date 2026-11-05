"""Read-only: highest PC id of one section type in the DLC id tables (work/generic/idmap.json base pairs and
work/generic/dlc_idmap.json 'new' table), and whether given ids are taken there. Test 51j / 51k (2026-11-04): new
diagnostic / costume texture ids must not collide with ids the pipeline already hands out.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/id_table_max.py TYPE [ID ...]
"""
import sys, os, json

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def main(argv):
    if not argv: sys.exit(__doc__)
    t = argv[0]; ids = {int(x) for x in argv[1:]}
    base = json.load(open(os.path.join(W, 'idmap.json'))).get(t, {})
    new = json.load(open(os.path.join(W, 'dlc_idmap.json')))['new'].get(t, {})
    bpc = {int(v) for v in base.values()}; npc = {int(v) for v in new.values()}
    print('type %s: base pairs %d (highest PC id %s), new table %d (highest PC id %s)' % (
        t, len(bpc), max(bpc) if bpc else '-', len(npc), max(npc) if npc else '-'))
    for i in sorted(ids):
        print('  id %d: base %s, new %s' % (i, 'TAKEN' if i in bpc else 'free', 'TAKEN' if i in npc else 'free'))


if __name__ == '__main__':
    main(sys.argv[1:])
