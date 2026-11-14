"""Read-only: raw bytes of condition records {u16 key, u16 id, u16 value, u8 flags, u8} in a DTP of a converted
(little-endian) DRM, e.g. the vault-off strike entry list of lara DTP 850 at +0x720a0 (7 records).

Usage (from the repository root):
  ../bin/pyt -t 120 work/adrnotarget_1411/cond_bytes.py PC.drm SID OFFSET_HEX COUNT
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW


def main(argv):
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    sid, off, count = int(argv[1]), int(argv[2], 16), int(argv[3])
    s = [x for x in D.sections if x.id == sid][0]
    d = bytes(s.data)
    for k in range(count):
        o = off + 8 * k
        key, cid, val, fl, b7 = struct.unpack_from('<HHHBB', d, o)
        print('+0x%05x  %s  {%d,%d,%d} flags 0x%02x byte7 0x%02x' % (o, d[o:o + 8].hex(), key, cid, val, fl, b7))
    print('hex', d[off:off + 8 * count].hex())


if __name__ == '__main__':
    main(sys.argv[1:])
