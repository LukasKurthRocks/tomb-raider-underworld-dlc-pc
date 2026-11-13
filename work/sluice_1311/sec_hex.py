"""sluice_1311: hex + ASCII dump of a byte range of one section of a DRM (read-only).

usage (from trudlcport): ../bin/pyt -t 300 work/sluice_1311/sec_hex.py FILE.drm TYPE ID FROM_HEX TO_HEX [--be]
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm


def main(a):
    e = 'be' if '--be' in a else 'le'; a = [x for x in a if x != '--be']
    f, typ, sid, lo, hi = a[0], int(a[1]), int(a[2]), int(a[3], 16), int(a[4], 16)
    for s in drm.sections_with_data(drm.cdrm_decode(open(f, 'rb').read(), e), e)[1]:
        if s['type'] == typ and s['id'] == sid:
            d = bytes(s['data'])
            for o in range(lo, min(hi, len(d)), 16):
                c = d[o:o + 16]
                print('+0x%05x  %s  %s' % (o, ' '.join(c[i:i + 4].hex() for i in range(0, 16, 4)),
                                          ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
            return
    print('section not found')


if __name__ == '__main__':
    if len(sys.argv) < 6: sys.exit(__doc__)
    main(sys.argv[1:])
