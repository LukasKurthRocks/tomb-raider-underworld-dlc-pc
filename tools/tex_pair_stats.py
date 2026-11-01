"""Compare textures (type 5, PCD9) with the same id in two PC DRM files, read-only: format, size, per-channel
mean / min / max (RGBA, level 0) and the mean absolute difference per channel; optional PNGs side by side.
Test 48h (2026-11-01): the doppelganger's converted normal maps differ in bytes from pc_lara's copies of the same id.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tex_pair_stats.py A.drm B.drm [--ids ID,ID] [--png DIR]
  default ids: every texture id present in both files whose bytes differ
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import drm_write as DW, tex_convert as T

FOURCC = {0x31545844: 'DXT1', 0x33545844: 'DXT3', 0x35545844: 'DXT5', 0x15: 'ARGB'}


def texs(path):
    return {s.id: s for s in DW.read(open(path, 'rb').read(), 'le').sections if s.type == 5}


def stats(im):
    a = np.asarray(im, dtype=np.float64)
    return ' '.join('%s %5.1f[%3d..%3d]' % (c, a[..., k].mean(), a[..., k].min(), a[..., k].max())
                    for k, c in enumerate('RGBA') if k < a.shape[-1])


def main(argv):
    ids = None; png = None
    if '--ids' in argv: k = argv.index('--ids'); ids = [int(x) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--png' in argv: k = argv.index('--png'); png = argv[k + 1]; del argv[k:k + 2]
    A, B = texs(argv[0]), texs(argv[1])
    if ids is None: ids = sorted(i for i in A if i in B and hashlib.md5(A[i].data).digest() != hashlib.md5(B[i].data).digest())
    if png: os.makedirs(png, exist_ok=True)
    for i in ids:
        if i not in A or i not in B: print('%d: missing in %s' % (i, 'A' if i not in A else 'B')); continue
        fa, fb = (FOURCC.get(struct.unpack_from('<I', x.data, 4)[0], '?') for x in (A[i], B[i]))
        ia, ib = T.pc_image(A[i].data), T.pc_image(B[i].data)
        a, b = np.asarray(ia, dtype=np.float64), np.asarray(ib, dtype=np.float64)
        print('%d: A %s %s  %s' % (i, fa, 'x'.join(map(str, a.shape[:2])), stats(ia)))
        print('%s  B %s %s  %s' % (' ' * len(str(i)), fb, 'x'.join(map(str, b.shape[:2])), stats(ib)))
        if a.shape == b.shape:
            print('%s  mean |A-B| %s' % (' ' * len(str(i)), ' '.join('%s %.1f' % (c, abs(a[..., k] - b[..., k]).mean())
                                                                 for k, c in enumerate('RGBA') if k < a.shape[-1])))
        if png:
            from PIL import Image
            Image.fromarray(np.asarray(ia)).save(os.path.join(png, '%d_A.png' % i))
            Image.fromarray(np.asarray(ib)).save(os.path.join(png, '%d_B.png' % i))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
