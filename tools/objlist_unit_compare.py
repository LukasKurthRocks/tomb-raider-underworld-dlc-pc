"""Compare the per-unit object lists (objlist.dat) of an Xbox list set and a PC list set by object NAME (read-only).

Object 858 investigation: shows which objects a unit requests on the Xbox and on the PC, and in which units given
objects (e.g. doppelganger_casual / player_tru_dlc2_extension) are listed at all.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/objlist_unit_compare.py XOBJECTLIST XOBJLIST.dat PCOBJECTLIST PCOBJLIST.dat
        [--units SUBSTR] [--find NAME,NAME..]
  Xbox lists big-endian (work/generic/lists/dlc_pack11_*), PC lists little-endian (mods/tr8/pc-w/*).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objlists as OL


def main(argv):
    units, find = None, []
    if '--units' in argv:
        k = argv.index('--units'); units = argv[k + 1]; del argv[k:k + 2]
    if '--find' in argv:
        k = argv.index('--find'); find = argv[k + 1].split(','); del argv[k:k + 2]
    xo = OL.read_objectlist(open(argv[0], 'rb').read())
    xr, _ = OL.read_objlist(open(argv[1], 'rb').read(), 'be')
    po = OL.read_objectlist(open(argv[2], 'rb').read())
    pr, _ = OL.read_objlist(open(argv[3], 'rb').read(), 'le')
    xd = {n: [xo.get(i, '#%d' % i) for i in l] for n, l in xr}
    pd = {n: [po.get(i, '#%d' % i) for i in l] for n, l in pr}
    for name in find:
        xid = [k for k, v in xo.items() if v == name]
        pid = [k for k, v in po.items() if v == name]
        print('object %s: Xbox id %s, PC id %s' % (name, xid, pid))
        print('  Xbox units: %s' % ', '.join(n for n in xd if name in xd[n]) or '-')
        print('  PC units:   %s' % ', '.join(n for n in pd if name in pd[n]) or '-')
    if units:
        for n in sorted(set(xd) | set(pd)):
            if units not in n:
                continue
            xs, ps = set(xd.get(n, [])), set(pd.get(n, []))
            print('unit %s: Xbox %s objects, PC %s objects' % (n, len(xs) if n in xd else 'no record',
                                                               len(ps) if n in pd else 'no record'))
            if xs - ps:
                print('  only Xbox: %s' % ', '.join(sorted(xs - ps)))
            if ps - xs:
                print('  only PC:   %s' % ', '.join(sorted(ps - xs)))


if __name__ == '__main__':
    main(sys.argv[1:])
