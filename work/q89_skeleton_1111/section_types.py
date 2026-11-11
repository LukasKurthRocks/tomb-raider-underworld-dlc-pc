"""Q89: section type histogram + type-14 (cloth) section ids / sizes of object DRMs, read only.

Usage (from the repository root):
  ../bin/pyt -t 900 work/q89_skeleton_1111/section_types.py MODS_DIR NAME [NAME ...]
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'q83_allenemies_1111'))
import drm_write as DW
from enemy_catalog import Src


def main(argv):
    S = Src(argv[0])
    for nm in argv[1:]:
        g = S.get(nm)
        if g is None:
            print('%s: no DRM' % nm); continue
        D = DW.read(g[2], 'le')
        c = collections.Counter(s.type for s in D.sections)
        cl = [(s.id, len(s.data)) for s in D.sections if s.type == 14]
        print('%-24s %s | type 14: %s' % (nm, dict(sorted(c.items())), cl[:8]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
