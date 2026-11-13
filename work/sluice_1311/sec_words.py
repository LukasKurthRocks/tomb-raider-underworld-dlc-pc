"""sluice_1311: differing 32-bit words of sections between two PC DRMs (A = ours, B = old tree), each with the Xbox word
at the same offset (pack record, section paired by type + id) and how A / B encode it (same / s32 / s16 / raw-other).
Read-only.

usage (from trudlcport): ../bin/pyt -t 300 work/sluice_1311/sec_words.py NAME.drm A.drm B.drm TYPE ID[,ID] [PACK]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm, convert_dlc as CD


def secs(raw, e):
    return drm.sections_with_data(drm.cdrm_decode(raw, e), e)[1]


def enc(x, p):
    if not x: return '?'
    if x == p: return 'same'
    if x[::-1] == p: return 's32'
    if x[1::-1] + x[:1:-1] == p: return 's16'
    return 'other'


def main(a):
    name, fa, fb, typ, ids = a[0], a[1], a[2], int(a[3]), [int(v) for v in a[4].split(',')]
    os.environ['TRUDLC_PACK_FIRST'] = a[5] if len(a) > 5 else 'pack10'
    A = {(s['type'], s['id']): bytes(s['data']) for s in secs(open(fa, 'rb').read(), 'le')}
    B = {(s['type'], s['id']): bytes(s['data']) for s in secs(open(fb, 'rb').read(), 'le')}
    xr, src = CD.raw_dlc(name)
    X = {(s['type'], s['id']): bytes(s['data']) for s in secs(xr, 'be')}
    print('xbox %s' % src)
    for i in ids:
        k = (typ, i); a_, b_, x_ = A.get(k), B.get(k), X.get(k, b'')
        print('%d:%d  A %s  B %s  xbox %s' % (typ, i, len(a_) if a_ else '-', len(b_) if b_ else '-', len(x_) or '-'))
        if not a_ or not b_: continue
        for o in range(0, min(len(a_), len(b_)) - 3, 4):
            if a_[o:o + 4] == b_[o:o + 4]: continue
            xw = x_[o:o + 4] if len(x_) >= o + 4 else b''
            fa_ = struct.unpack('<f', a_[o:o + 4])[0]; fb_ = struct.unpack('<f', b_[o:o + 4])[0]
            print('   +0x%05x xbox %s | A %s %-5s | B %s %-5s | as float A %.6g B %.6g'
                  % (o, xw.hex() if xw else '-', a_[o:o + 4].hex(), enc(xw, a_[o:o + 4]), b_[o:o + 4].hex(),
                     enc(xw, b_[o:o + 4]), fa_, fb_))


if __name__ == '__main__':
    if len(sys.argv) < 6: sys.exit(__doc__)
    main(sys.argv[1:])
