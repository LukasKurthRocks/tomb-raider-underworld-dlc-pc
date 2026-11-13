"""sluice_1311: differing 32-bit words of the wave sections (type 6) between two PC DRMs, with the Xbox section's
word at the same offset (read-only). Shows whether the old tree's waves differ from ours only in header / id words.

usage (from trudlcport): ../bin/pyt -t 300 work/sluice_1311/wave_words.py NAME.drm A.drm B.drm
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm, convert_dlc as CD


def secs(raw, e):
    return drm.sections_with_data(drm.cdrm_decode(raw, e), e)[1]


def main(a):
    name, fa, fb = a
    A = {(s['type'], s['id']): bytes(s['data']) for s in secs(open(fa, 'rb').read(), 'le')}
    B = {(s['type'], s['id']): bytes(s['data']) for s in secs(open(fb, 'rb').read(), 'le')}
    os.environ['TRUDLC_PACK_FIRST'] = 'pack10'
    xr, src = CD.raw_dlc(name)
    X = [s for s in secs(xr, 'be') if s['type'] == 6]
    PA = [k for k in A if k[0] == 6]
    xs = {k: bytes(x['data']) for k, x in zip(PA, X)} if len(PA) == len(X) else {}
    for k in PA:
        if k not in B or A[k] == B[k]: continue
        a_, b_ = A[k], B[k]; x_ = xs.get(k, b'')
        offs = [o for o in range(0, min(len(a_), len(b_)) - 3, 4) if a_[o:o + 4] != b_[o:o + 4]]
        print('6:%d len %d, %d words differ (first at +0x%x, last +0x%x)' % (k[1], len(a_), len(offs), offs[0], offs[-1]))
        for o in offs[:4]:
            print('   +0x%05x A %s  B %s  xbox %s' % (o, a_[o:o + 4].hex(), b_[o:o + 4].hex(), x_[o:o + 4].hex() if x_ else '-'))


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    main(sys.argv[1:])
