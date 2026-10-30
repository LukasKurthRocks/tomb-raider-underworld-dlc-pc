"""Which game archives contain given DRM names (read-only): every source of tools/locals.py (Xbox layers, title
update, DLC packs, PC bigfile / patch). Finding 43 follow-up (DLC 2 rock vein: object-list entries without a DRM
in pack11 or the tree - do they come with the Xbox title update?).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/archive_has.py NAME[.drm] [NAME ...]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc


def main(argv):
    names = [n if n.endswith('.drm') else n + '.drm' for n in argv]
    arch = {}
    for src, (path, e, pre) in LC.SRC.items():
        if not os.path.exists(path): continue
        try: arch[src] = (Archive(path, e), pre)
        except Exception as ex: print('skip %s: %s' % (src, ex))
    for n in names:
        found = [src for src, (A, pre) in arch.items() if A.find(crc(pre + '\\' + n))]
        print('%-45s %s' % (n, ', '.join(found) or 'nowhere'))


if __name__ == '__main__':
    main(sys.argv[1:])
