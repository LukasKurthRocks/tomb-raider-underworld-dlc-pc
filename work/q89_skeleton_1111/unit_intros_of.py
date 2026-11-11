"""Q89 / Q80: intros (placed instances) of given object ids in PC units, read only.

Unit DRM resolved like the game (MODS_DIR flat <unit>.drm, then patch.000, bigfile.000); intro records via
work/endb270_0811/unit_dtp.py (unit(), intros(): count +0xc, array +0x10, 0x90 B, object id +0x50, uid +0x58).
Position = intro +0x10..+0x18 floats (layout ENGINE.md 5.2).

Usage (from the repository root):
  ../bin/pyt -t 1800 work/q89_skeleton_1111/unit_intros_of.py MODS_DIR --units U1,U2 --ids 768,223 [--all]
  --all lists every intro of the unit (id name uid)
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'q83_allenemies_1111'))
sys.path.insert(0, os.path.join(HERE, '..', 'endb270_0811'))
import objlists as OL
import drm
from enemy_catalog import Src
import unit_dtp as UD


def main(argv):
    mods = argv[0]
    units = argv[argv.index('--units') + 1].split(',')
    ids = set(int(x) for x in argv[argv.index('--ids') + 1].split(','))
    lst = os.path.join(mods, 'tr8', 'pc-w')
    names = OL.read_objectlist(open(os.path.join(lst, 'objectlist.txt'), 'rb').read())
    S = Src(mods)
    for un in units:
        p = os.path.join(mods, un + '.drm')
        if os.path.isfile(p):
            raw = open(p, 'rb').read(); src = 'mods'
        else:
            src = None
            for s, A, pre in S.arch:
                recs = A.find(UD.crc(pre + '\\' + un + '.drm'))
                if recs:
                    raw = A.read(recs[-1]); src = s
                    break
            if src is None:
                print('%s: no unit DRM' % un); continue
        Ssec, u, ptr = UD.unit(raw, 'le')
        its = UD.intros(u, ptr, 'le')
        cnt = collections.Counter(i['obj'] for i in its)
        print('\n%s [%s]: %d intros' % (un, src, len(its)))
        for i in its:
            if i['obj'] in ids or '--all' in argv:
                pos = struct.unpack_from('<3f', u['data'], i['o'] + 0x10)
                print('  intro %3d obj %4d %-28s uid %6d pos %.0f %.0f %.0f data %d B' % (
                    i['k'], i['obj'], names.get(i['obj'], '?'), i['uid'], pos[0], pos[1], pos[2], i['dsz']))
        miss = [x for x in sorted(ids) if not cnt.get(x)]
        print('  no intro for: %s' % ', '.join('%d %s' % (x, names.get(x, '?')) for x in miss))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
