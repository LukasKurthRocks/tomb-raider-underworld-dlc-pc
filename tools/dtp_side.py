"""Side-by-side view of one DTP section: Xbox (big-endian) words and the PC (little-endian) words of a converted file,
with the conversion mode per word (16 = two u16 swapped, 32 = u32 swapped, = raw, amb, ?) and relocations
(read-only; finding 43, rock vein state chart).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/dtp_side.py XBOX.drm PC.drm SECTION_ID OFFSET LENGTH      (hex offset / length)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from dtp_conv_modes import mode


def sec(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return bytes(s.data), R.parse(bytes(s.reloc), e)
    raise SystemExit('DTP %d not in %s' % (sid, path))


def main(argv):
    xd, xr = sec(argv[0], 'be', int(argv[2])); pd, _ = sec(argv[1], 'le', int(argv[2]))
    off, ln = int(argv[3], 16) & ~3, int(argv[4], 16)
    it = dict(xr.internal)
    for o in range(off, min(off + ln, len(xd), len(pd)), 4):
        x, p = xd[o:o + 4], pd[o:o + 4]
        xa, xb = struct.unpack('>HH', x); pa, pb = struct.unpack('<HH', p)
        fl = struct.unpack('>f', x)[0]
        fs = ('%.4g' % fl) if (x != b'\0' * 4 and 1e-4 < abs(fl) < 1e6) else ''
        note = ('-> +0x%x' % it[o]) if o in it else ''
        print('+0x%05x  xbox %08x (%5d %5d)  pc u16 %5d %5d  %-3s %-10s %s' % (o, struct.unpack('>I', x)[0], xa, xb, pa, pb,
                                                                          mode(x, p), fs, note))


if __name__ == '__main__':
    main(sys.argv[1:])
