"""Xbox side of one script call (read-only): find the Xbox script section of an Xbox DLC DRM that contains a marker
string, list its external relocations (source offset -> target type, id, offset) and, for targets that are script
sections, the prototype record at the target offset (class id, vtable slot, name symbol). Compare with the PC copy.

Usage (from trudlcport):
  ../bin/pyt -t 600 work/dlc1warp_1311/xbox_call_target.py PACK DRM_NAME MARKER [SRC_OFFSET,...]
  PACK = pack10 (DLC 1) / pack11 (DLC 2); DRM_NAME e.g. dlc_level1_start.drm
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import dtp_word_classes as C
import drm_reloc as R
from convert_dlc import R as DLC_ROOT, PACKS


def main(argv):
    pack, name, marker = argv[0], argv[1], argv[2].encode()
    want = [int(x, 0) for x in argv[3].split(',')] if len(argv) > 3 else None
    paths = [DLC_ROOT + p for p in PACKS if p.endswith('/%s.000' % pack)]
    X = C.find(paths, 'be', 'xenon-w' + chr(92) + name)
    if X is None:
        sys.exit('not found: %s in %s' % (name, pack))
    byid = {(s['type'], s['id']): s for s in X}
    hits = [s for s in X if s['type'] == 8 and s['data'] and marker in s['data']]
    print('%s %s: %d sections, %d script(s) with the marker' % (pack, name, len(X), len(hits)))
    for s in hits:
        rel = R.parse(s['reloc'], 'be')
        print('script id %d size %d externals %d' % (s['id'], len(s['data']), len(rel.external)))
        for si, so, do in sorted(rel.external, key=lambda q: q[1]):
            if want is not None and so not in want:
                continue
            t = X[si]
            line = '  src 0x%04x -> (%d,%d)+0x%x' % (so, t['type'], t['id'], do)
            if t['type'] == 8 and t['data'] and do + 12 <= len(t['data']):
                cid, w1, w2 = struct.unpack_from('>IHH', t['data'], do)[0], None, None
                a, b = struct.unpack_from('>HH', t['data'], do + 4)
                c, dd = struct.unpack_from('>HH', t['data'], do + 8)
                line += '  record: class %d (0x%x) halves %04x %04x | %04x %04x' % (cid, cid, a, b, c, dd)
            print(line)


if __name__ == '__main__':
    main(sys.argv[1:])
