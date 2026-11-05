"""Offline calibration of the game's text-at-an-instance projection that TruMenu 0.13's thrall labels use (read-only).

Reads the constants of the camera update 0x5f3df0 / 0x5e7b30 / 0x5c59f0 and of TRANS_RotTransPersVectorf 0x49f630 from
tru.exe (the operands of the byte-checked instructions) and replays the arithmetic for a camera that looks straight
along its depth axis: where do points on the edges of the field of view land in the game's text space, and what is that
space's size? Expected (if the reading of the code is right): the vertical field of view maps to y = 0 .. 448 and the
horizontal one (vertical fov x aspect) to x = 0 .. 512 for every aspect - i.e. the text space is 512 x 448 and fills the
screen, which is what draw.scale 512 448 assumes. The y direction on the screen (down = +y) and the instance anchor
(+0x20) can only be seen live.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/labels_projection_calib.py EXE [FOV_RADIANS] [ASPECT_INT ...]
     FOV_RADIANS  vertical field of view to replay (default 0.785398 = pi / 4, TruMenu camera.fov's "" value)
     ASPECT_INT   [[0xad75e4]+0x170] values (aspect x 10000; default 13333 17777 16000 21333)
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

# (name, VA, type) - VAs are the memory operands of the byte-checked instructions (precheck_013.txt)
CONSTS = [
    ('x scale a (0x5e7b37)', 0x845a90, 'd'), ('x scale b (0x5e7b3f)', 0x8454d8, 'd'),
    ('y scale num (0x5e7b60)', 0x8454d0, 'd'), ('y scale den (0x5e7b68)', 0x8559f0, 'd'),
    ('aspect divisor (0x5c59fc)', 0x844f00, 'd'), ('x aspect factor (0x5c5a22)', 0x851c50, 'd'),
    ('fov half (0x5f3edb)', 0x8413c0, 'd'), ('focal numerator (0x5f3f08)', 0x8559e8, 'd'),
    ('centre x (0x49f702)', 0x843a00, 'd'), ('centre y (0x49f713)', 0x8454c8, 'd'), ('near z (0x62257b)', 0x8451e4, 'f'),
]


def read(exe, secs, va, kind):
    for _, sva, rptr, size, _ in secs:
        if sva <= va < sva + size:
            off = rptr + va - sva
            return struct.unpack_from('<d' if kind == 'd' else '<f', exe, off)[0]
    raise ValueError('0x%x not in the file' % va)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    c = {}
    for name, va, kind in CONSTS:
        c[name] = read(exe, secs, va, kind)
        print('%-28s 0x%08x %s %.9g' % (name, va, kind, c[name]))
    fov = float(argv[1]) if len(argv) > 1 else math.pi / 4
    aspects = [int(a) for a in argv[2:]] or [13333, 17777, 16000, 21333]
    t = math.tan(fov * c['fov half (0x5f3edb)'])
    f = c['focal numerator (0x5f3f08)'] / t
    print('\nvertical fov %.6f rad: tan(fov * %.3g) = %.6f, focal [0x8906d0] = %.6g / tan = %.6f' % (
        fov, c['fov half (0x5f3edb)'], t, c['focal numerator (0x5f3f08)'], f))
    ys = c['y scale num (0x5e7b60)'] / c['y scale den (0x5e7b68)']
    cx, cy = c['centre x (0x49f702)'], c['centre y (0x49f713)']
    worst = 0.0
    for a in aspects:
        aspect = a / c['aspect divisor (0x5c59fc)']
        xs = c['x scale a (0x5e7b37)'] * c['x scale b (0x5e7b3f)'] * (1.0 / aspect) * c['x aspect factor (0x5c5a22)']
        z = 1000.0
        # camera-space points on the four edges of the view frustum (vertical fov, horizontal = atan(tan * aspect))
        top, bottom = (0.0, -t * z, z), (0.0, t * z, z)
        left, right = (-t * aspect * z, 0.0, z), (t * aspect * z, 0.0, z)
        def screen(p):
            return (p[0] * xs / p[2] * f + cx, p[1] * ys / p[2] * f + cy)
        pts = [screen(p) for p in (top, bottom, left, right)]
        print('aspect %d (%.4f): column x x %.6f, column y x %.6f; edges -> y %.3f / %.3f, x %.3f / %.3f; centre %.1f %.1f'
              % (a, aspect, xs, ys, pts[0][1], pts[1][1], pts[2][0], pts[3][0], cx, cy))
        worst = max(worst, abs(pts[0][1]), abs(pts[1][1] - 2 * cy), abs(pts[2][0]), abs(pts[3][0] - 2 * cx))
    print('\ntext space %.0f x %.0f (2 x centre); largest edge deviation from 0 / %.0f / %.0f: %.6f' % (
        2 * cx, 2 * cy, 2 * cx, 2 * cy, worst))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
