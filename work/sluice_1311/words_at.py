"""sluice_1311: bytes of chosen 32-bit words of one section in several PC DRMs (and the Xbox pack record), to see
which pipeline stage set each word. Read-only.

usage (from trudlcport): ../bin/pyt -t 600 work/sluice_1311/words_at.py NAME.drm TYPE ID OFF[,OFF] FILE [FILE ...]
  OFF hex; Xbox = pack10 record (TRUDLC_PACK_FIRST=pack10)
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm, convert_dlc as CD


def sec(raw, e, typ, sid):
    for s in drm.sections_with_data(drm.cdrm_decode(raw, e), e)[1]:
        if s['type'] == typ and s['id'] == sid: return bytes(s['data'])
    return None


def enc(x, p):
    if x is None or p is None: return '?'
    if x == p: return 'raw'
    if x[::-1] == p: return 's32'
    if x[1::-1] + x[:1:-1] == p: return 's16'
    return 'oth'


def main(a):
    name, typ, sid = a[0], int(a[1]), int(a[2])
    offs = [int(v, 16) for v in a[3].split(',')]
    os.environ['TRUDLC_PACK_FIRST'] = 'pack10'
    xr, src = CD.raw_dlc(name)
    X = sec(xr, 'be', typ, sid)
    print('%-10s %s' % ('offset', '  '.join('%-13s' % ('+0x%x' % o) for o in offs)))
    print('%-10s %s' % ('xbox', '  '.join('%-13s' % X[o:o + 4].hex() for o in offs)))
    for f in a[4:]:
        S = sec(open(f, 'rb').read(), 'le', typ, sid)
        if S is None: print('%s: no section' % f); continue
        print('%-10s %s  %s' % (os.path.basename(os.path.dirname(os.path.dirname(f))) or '-',
                                '  '.join('%s %s' % (S[o:o + 4].hex(), enc(X[o:o + 4], S[o:o + 4])) for o in offs), f))


if __name__ == '__main__':
    if len(sys.argv) < 6: sys.exit(__doc__)
    main(sys.argv[1:])
