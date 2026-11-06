"""Offline self-test of TruMenu 0.16's new math (read-only, no input files; 2026-11-06 TruMenu 0.16 readability,
docs Befund-TruMenu-Lesbarkeit-0611.md).

Three parts, each written the way TruMenu.cpp does it:
  1. "Lara in" (DvInside): |(p - centre) . row_i| <= h_i with the rows of M = Rz * Ry * Rx, against the engine's box
     test 0x46b730 as decoded in tools/trigger_box_math.py (local = rotate(conjugate(q), p - centre), q = quaternion of
     the Euler matrix 0x49d500): random boxes / points must agree (points within 0.1 % of a face are skipped), and the
     live data point of 2026-11-06 (triggervolume 4537 in l3_main_bedroom, rotation z = float bits 0x3fc2d6fe, centre
     (1029.5, -3729.3, -2643.1), half (181.1, 527.1, 300)) must say: Lara at (1488.26, -3798.57, -2890.41) + 200 up is
     inside (she played the heat-shield animation), at (1654.91, -3484.06, -2890.41) + 200 up outside.
  2. Depth mapping (DpMapping / DpDepth): random cameras with a scene view V and a perspective projection P in both
     conventions (row vectors as D3DX: w = z * P[2][3]; column vectors: the transpose), left- and right-handed, normal and
     reversed Z; TruMenu's "0.14 camera" = V with the x / y columns scaled (text space). The convention / sign search and
     the depth formula must give the depth p * V * P gives (no bias), and an orthographic P / a different camera must be
     refused.
  3. Interpolation: for a perspective projection the depth value and 1 / z' are affine in screen space along a projected
     segment - what DpLineDraw / DpQuad / the dashes rely on.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trumenu_readability_check.py [N]     N random cases per part (default 2000); exit 0 = pass
"""
import math, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trigger_box_math as TB


def rows_of(r):
    """TruMenu DvEulerRows: rows of M = Rz * Ry * Rx (closed form)"""
    cx, sx, cy, sy, cz, sz = math.cos(r[0]), math.sin(r[0]), math.cos(r[1]), math.sin(r[1]), math.cos(r[2]), math.sin(r[2])
    return [[cz * cy, sz * cx + cz * sy * sx, sz * sx - cz * sy * cx],
            [-sz * cy, cz * cx - sz * sy * sx, cz * sx + sz * sy * cx],
            [sy, -cy * sx, cy * cx]]


def inside_truemenu(c, h, r, p):
    d = [p[k] - c[k] for k in range(3)]
    rows = rows_of(r)
    return all(abs(sum(d[k] * rows[i][k] for k in range(3))) <= h[i] for i in range(3))


def margin(c, h, r, p):
    d = [p[k] - c[k] for k in range(3)]
    rows = rows_of(r)
    return min(abs(abs(sum(d[k] * rows[i][k] for k in range(3))) - h[i]) / h[i] for i in range(3))


def inside_engine(c, h, r, p):
    """0x46b730 as decoded in trigger_box_math.py, with the quaternion of 0x49d500's matrix (0x49d720)"""
    return TB.engine_box_inside(p, c, TB.quat_of(TB.euler_matrix(r)), h)


def part1(n, rnd):
    bad = skipped = 0
    for _ in range(n):
        c = [rnd.uniform(-5000, 5000) for _ in range(3)]
        h = [rnd.uniform(20, 2000) for _ in range(3)]
        r = [rnd.uniform(-math.pi, math.pi) for _ in range(3)]
        p = [c[k] + rnd.uniform(-1.5, 1.5) * max(h) for k in range(3)]
        if margin(c, h, r, p) < 1e-3:
            skipped += 1
            continue
        if inside_truemenu(c, h, r, p) != inside_engine(c, h, r, p): bad += 1
    zrot = struct.unpack('<f', struct.pack('<I', 0x3fc2d6fe))[0]
    c, h, r = (1029.5, -3729.3, -2643.1), (181.1, 527.1, 300.0), (0.0, 0.0, zrot)
    p1, p2 = (1488.26, -3798.57, -2890.41 + 200.0), (1654.91, -3484.06, -2890.41 + 200.0)
    live = [inside_truemenu(c, h, r, p1), inside_engine(c, h, r, p1), inside_truemenu(c, h, r, p2), inside_engine(c, h, r, p2)]
    d = [p1[k] - c[k] for k in range(3)]
    loc1 = [sum(d[k] * rows_of(r)[i][k] for k in range(3)) for i in range(3)]
    d = [p2[k] - c[k] for k in range(3)]
    loc2 = [sum(d[k] * rows_of(r)[i][k] for k in range(3)) for i in range(3)]
    ok = bad == 0 and live == [True, True, False, False]
    print('part 1 Lara in: %d random cases, %d disagree with the engine box test (%d skipped at a face); live 4537: '
          'rot z %.4f rad (%.2f deg), point 1 local (%.1f, %.1f, %.1f) inside %s / engine %s, point 2 local (%.1f, %.1f, '
          '%.1f) inside %s / engine %s -> %s' % (n, bad, skipped, zrot, math.degrees(zrot), loc1[0], loc1[1], loc1[2],
                                                 live[0], live[1], loc2[0], loc2[1], loc2[2], live[2], live[3],
                                                 'pass' if ok else 'FAIL'))
    return ok


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transpose(m):
    return [[m[j][i] for j in range(4)] for i in range(4)]


def flat(m):
    return [m[i][j] for i in range(4) for j in range(4)]


def rand_rot(rnd):
    rows = rows_of([rnd.uniform(-math.pi, math.pi) for _ in range(3)])
    return rows


def make_case(rnd, rh, reversed_z, n_=16.0, f_=12000.0):
    """world -> view V (row vectors, 4x4) with orthonormal rotation, P perspective (row vectors), cam position"""
    R = rand_rot(rnd)                        # rows = camera axes in world (right, up, forward)
    cam = [rnd.uniform(-8000, 8000) for _ in range(3)]
    # view: v_i = (p - cam) . axis_i  ->  row-vector matrix with columns = axes
    V = [[R[0][0], R[1][0], R[2][0], 0.0], [R[0][1], R[1][1], R[2][1], 0.0], [R[0][2], R[1][2], R[2][2], 0.0],
         [0.0, 0.0, 0.0, 1.0]]
    for j in range(3): V[3][j] = -sum(cam[k] * R[j][k] for k in range(3))
    s = -1.0 if rh else 1.0                  # right-handed: forward = -z in view space
    if rh:
        for i in range(4): V[i][2] = -V[i][2]
    if not reversed_z:
        a, b = f_ / (f_ - n_), -n_ * f_ / (f_ - n_)
    else:
        a, b = -n_ / (f_ - n_), n_ * f_ / (f_ - n_)
    P = [[1.2, 0.0, 0.0, 0.0], [0.0, 1.6, 0.0, 0.0], [0.0, 0.0, a * s, s], [0.0, 0.0, b, 0.0]]
    return V, P, cam, R


def part2(n, rnd):
    bad = refused = wrong_accept = 0
    worst = 0.0
    for i in range(n):
        rh, rev, col = bool(i & 1), bool(i & 2), bool(i & 4)
        V, P, cam, R = make_case(rnd, rh, rev)
        # TruMenu's 0.14 camera matrix (row vectors, flat 16): columns 0 / 1 scaled, column 2 = forward depth
        m14 = [[0.0] * 4 for _ in range(4)]
        for r_ in range(3):
            m14[r_][0] = R[0][r_] * 1.7
            m14[r_][1] = R[1][r_] * -2.3
            m14[r_][2] = R[2][r_]
        for j, axis in enumerate((R[0], R[1], R[2])):
            sc = (1.7, -2.3, 1.0)[j]
            m14[3][j] = -sum(cam[k] * axis[k] for k in range(3)) * sc
        m14[3][3] = 1.0
        mf = flat(m14)
        Vf, Pf = (flat(transpose(V)), flat(transpose(P))) if col else (flat(V), flat(P))
        res = mapping(mf, Vf, Pf)
        if res is None:
            refused += 1
            bad += 1
            continue
        A, B, W, sign, less = res
        VP = mat_mul(V, P)
        for _ in range(5):                   # random points in front of the camera
            zc = rnd.uniform(20.0, 11000.0)
            p = [cam[k] + R[2][k] * zc + R[0][k] * rnd.uniform(-zc, zc) * 0.5 + R[1][k] * rnd.uniform(-zc, zc) * 0.4
                 for k in range(3)]
            hv = [p[0], p[1], p[2], 1.0]
            clip = [sum(hv[k] * VP[k][j] for k in range(4)) for j in range(4)]
            true_z = clip[2] / clip[3]
            zq = sum(hv[k] * m14[k][2] for k in range(4))
            zv = sign * zq
            ours = (A * zv + B) / (W * zv)
            worst = max(worst, abs(ours - true_z))
            if abs(ours - true_z) > 1e-6: bad += 1
            if less != (not rev): bad += 1
    # negative: orthographic projection, and a view of another camera
    V, P, cam, R = make_case(rnd, False, False)
    ortho = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0 / 12000.0, 0], [0, 0, 0, 1.0]]
    m14 = [[0.0] * 4 for _ in range(4)]
    for r_ in range(3):
        for c_ in range(3): m14[r_][c_] = R[c_][r_]
    for j in range(3): m14[3][j] = -sum(cam[k] * R[j][k] for k in range(3))
    m14[3][3] = 1.0
    if mapping(flat(m14), flat(V), flat(ortho)) is not None: wrong_accept += 1
    V2, P2, cam2, R2 = make_case(rnd, False, False)
    if mapping(flat(m14), flat(V2), flat(P2)) is not None: wrong_accept += 1
    ok = bad == 0 and wrong_accept == 0
    print('part 2 depth mapping: %d cameras (row / column, LH / RH, normal / reversed Z) x 5 points, %d wrong (%d refused), '
          'worst |z - z_true| %.2e; negative cases accepted %d of 2 -> %s' % (n, bad, refused, worst, wrong_accept,
                                                                            'pass' if ok else 'FAIL'))
    return ok


def cam_pos(m):
    """DvCamPos: solve A p = -t, A = 3x3 part (q_x = m0 x + m4 y + m8 z + m12 ...)"""
    a = [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]]
    b = [-m[12], -m[13], -m[14]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
           a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12: return None
    out = []
    for col in range(3):
        mm = [row[:] for row in a]
        for r_ in range(3): mm[r_][col] = b[r_]
        d = (mm[0][0] * (mm[1][1] * mm[2][2] - mm[1][2] * mm[2][1]) - mm[0][1] * (mm[1][0] * mm[2][2] - mm[1][2] * mm[2][0]) +
             mm[0][2] * (mm[1][0] * mm[2][1] - mm[1][1] * mm[2][0]))
        out.append(d / det)
    return out


def to_cam(m, p):
    return [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
            m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]]


def mapping(m, V, P):
    """TruMenu DpMapping (flat row-major 16-float matrices); None = refused, else (A, B, W, sign, less)"""
    cam = cam_pos(m)
    if cam is None: return None
    ux = 1.0 / math.sqrt(m[0] ** 2 + m[4] ** 2 + m[8] ** 2)
    f = [m[2], m[6], m[10]]
    r = [m[0] * ux, m[4] * ux, m[8] * ux]
    fl = math.sqrt(sum(x * x for x in f))
    if not 0.5 < fl < 2.0: return None
    pts = [[cam[k] + f[k] / (fl * fl) * 1000.0 for k in range(3)],
           [cam[k] + f[k] / (fl * fl) * 3000.0 + r[k] * 700.0 for k in range(3)]]
    form, sign = 0, 1.0
    for conv in (1, 2):
        ok, s = True, 0.0
        for i, p in enumerate(pts):
            zq = to_cam(m, p)[2]
            zv = (V[2] * p[0] + V[6] * p[1] + V[10] * p[2] + V[14]) if conv == 1 else \
                 (V[8] * p[0] + V[9] * p[1] + V[10] * p[2] + V[11])
            si = -1.0 if zv < 0 else 1.0
            ok = ok and zq > 100.0 and abs(abs(zv) - zq) <= 0.03 * zq + 5.0 and (i == 0 or si == s)
            s = si
        if ok:
            form, sign = conv, s
            break
    if not form: return None
    if abs(abs(P[11]) - 1.0) <= 0.02: w, b = P[11], P[14]
    elif abs(abs(P[14]) - 1.0) <= 0.02: w, b = P[14], P[11]
    else: return None
    if not abs(P[15]) < 1e-3 or not w * sign > 0: return None
    a = P[10]
    z = lambda zc: (a * sign * zc + b) / (w * sign * zc)
    zn, z1, zf = z(16.5), z(1000.0), z(50000.0)
    near_ok = (-0.03 < zn < 0.05) or (0.95 < zn < 1.03)
    mono = (zn < z1 < zf) or (zn > z1 > zf)
    if not near_ok or not mono or not -0.05 < zf < 1.05: return None
    return a, b, w, sign, z1 > zn


def part3(n, rnd):
    worst_z = worst_i = 0.0
    a_, b_ = 12000.0 / 11984.0, -16.0 * 12000.0 / 11984.0
    for _ in range(n):
        p0 = [rnd.uniform(-3000, 3000), rnd.uniform(-2000, 2000), rnd.uniform(20, 9000)]
        p1 = [rnd.uniform(-3000, 3000), rnd.uniform(-2000, 2000), rnd.uniform(20, 9000)]
        s0 = (p0[0] / p0[2], p0[1] / p0[2])
        s1 = (p1[0] / p1[2], p1[1] / p1[2])
        for t in (0.1, 0.25, 0.5, 0.8):
            # the 3D point that projects to screen parameter t (perspective-correct: 1/z linear in t)
            inv = (1 - t) / p0[2] + t / p1[2]
            u = (t / p1[2]) / inv
            p = [p0[k] + (p1[k] - p0[k]) * u for k in range(3)]
            sp = (p[0] / p[2], p[1] / p[2])
            # the screen point at t really is that point
            if abs(sp[0] - (s0[0] + (s1[0] - s0[0]) * t)) > 1e-6 * (1 + abs(sp[0])): worst_i = max(worst_i, 1.0)
            z_true = a_ + b_ / p[2]
            z_lin = (a_ + b_ / p0[2]) * (1 - t) + (a_ + b_ / p1[2]) * t
            worst_z = max(worst_z, abs(z_true - z_lin))
            worst_i = max(worst_i, abs(1.0 / p[2] - inv))
    ok = worst_z < 1e-9 and worst_i < 1e-12
    print('part 3 interpolation: %d segments x 4 points, worst |z_lin - z_true| %.1e, worst |1/z - lerp| %.1e -> %s'
          % (n, worst_z, worst_i, 'pass' if ok else 'FAIL'))
    return ok


def main(argv):
    n = int(argv[0]) if argv else 2000
    rnd = random.Random(20261106)
    results = [part1(n, rnd), part2(n, rnd), part3(n, rnd)]
    print('all pass' if all(results) else 'FAIL')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
