"""Find a byte pattern in one DRM inside a game archive (read-only): sources as in tools/locals.py (xbase, tu,
pcbig, pcpatch, pack10, pack11, ...). Prints section index / type / id, offset and the bytes around each hit.
Finding 43 follow-up: where the Xbox title-update script 7 keeps the DLC 2 hint string ids.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/bigfile_find.py SOURCE NAME.drm HEX [--context N] [--section ID]
  e.g. tu generalbank.drm 0000057b   (Xbox data is big-endian)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC, drm_write as DW
from archive import Archive
from names import crc
from drm import cdrm_decode


def main(argv):
    ctx = 16; only = None
    if '--context' in argv: k = argv.index('--context'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    if '--section' in argv: k = argv.index('--section'); only = int(argv[k + 1]); del argv[k:k + 2]
    src, name, pat = argv[0], argv[1], bytes.fromhex(argv[2].replace(' ', ''))
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + name))
    if not recs: raise SystemExit('%s not in %s' % (name, src))
    D = DW.read(cdrm_decode(A.read(recs[-1]), e), e)
    hits = 0
    for si, s in enumerate(D.sections):
        if only is not None and s.id != only: continue
        o = s.data.find(pat)
        while o >= 0:
            hits += 1; a = max(0, o - ctx)
            print('HIT sec %d type %d id %d off 0x%x: %s' % (si, s.type, s.id, o, s.data[a:o + len(pat) + ctx].hex()))
            o = s.data.find(pat, o + 1)
    print('%s %s: %d sections, %d hits' % (src, name, len(D.sections), hits))


if __name__ == '__main__':
    main(sys.argv[1:])
