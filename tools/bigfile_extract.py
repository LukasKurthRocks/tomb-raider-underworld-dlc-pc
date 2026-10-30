"""Extract one DRM from a game archive (sources of tools/locals.py: pcbig, pcpatch, xbase, tu, pack10, pack11, ...)
to a file, CDRM-decoded (read-only on the archive). Finding 43 follow-up: base-game objects as references for the
DLC ones (e.g. the PC grapple rings ar_ei_grapple_wall.drm against dlc1_ei_grapple_wall.drm).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/bigfile_extract.py SOURCE NAME.drm OUT.drm
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode


def main(argv):
    src, name, out = argv
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + name))
    if not recs: raise SystemExit('%s not in %s' % (name, src))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(cdrm_decode(A.read(recs[-1]), e))
    print('%s -> %s (%s endian)' % (name, out, e))


if __name__ == '__main__':
    main(sys.argv[1:])
