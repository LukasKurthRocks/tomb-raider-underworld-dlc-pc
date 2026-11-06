"""Offline self-test of TruMenu 0.14's trigger wireframe math against the engine steps read from tru.exe (read-only, no
input files; 2026-11-06 TruMenu 0.14 triggers, docs Befund-TruMenu-Trigger-0611.md).

The engine side is written step by step as decoded from the disassembly (logs/trg0611_dis_*.txt):
  0x49d500  Euler matrix: identity, then the column operations of 0x49bd40 (Z, angle +8), 0x49bc70 (Y, angle +4),
            0x49bb90 (X, angle +0) with A = cos (0x813420, fcos) and B = sin (0x813680, fsin):
              Z: c0' = c0*A - c1*B, c1' = c0*B + c1*A        Y: c0' = c0*A + c2*B, c2' = c2*A - c0*B
              X: c1' = c1*A - c2*B, c2' = c1*B + c2*A        (per row, rows 0..3)
  0x49d720  quaternion of the matrix (trace branch: x = m12 - m21, y = m20 - m02, z = m01 - m10, w = trace + 1; the
            other branches as the usual largest-diagonal formulas), normalised (0x49d130)
  0x49c940  Hamilton product (out.x = ax*bw + aw*bx + ay*bz - az*by ...)
  0x49cd40  rotate: (q (x) v) (x) conjugate(q)
  0x46b730  box test: local = rotate(conjugate(q), p - centre); inside when -h <= local <= h on every axis
  0x49ba20  point * matrix: x*row0 + y*row1 + z*row2 + row3 (plane corners (+-w, 0, +-h))
TruMenu's side (TruMenu.cpp DvEulerRows / DvPoint): rows of M = Rz * Ry * Rx in closed form, corner = centre +
(+-h) * M. The test draws random angles / extents / centres and checks that every closed-form box corner scaled by
0.999 is inside and by 1.001 outside the engine's box test, and that the closed-form plane corners equal 0x49ba20's.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trigger_box_math.py [N]                N random cases (default 2000); exit 0 = all pass
  ../bin/pyt -t 120 tools/trigger_box_math.py [N] --transposed   negative test: TruMenu's rows transposed (the other
                                                                 convention) - must FAIL (exit 1)
"""
import math, random, sys


def euler_matrix(r):
    """0x49d500 as decoded: 4x4 row-major, identity post-multiplied by Rz, Ry, Rx via the column operations"""
    m = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    a, b = math.cos(r[2]), math.sin(r[2])                    # 0x49bd40, columns 0 / 1
    for row in m:
        c0, c1 = row[0], row[1]
        row[0], row[1] = c0 * a - c1 * b, c0 * b + c1 * a
    a, b = math.cos(r[1]), math.sin(r[1])                    # 0x49bc70, columns 0 / 2
    for row in m:
        c0, c2 = row[0], row[2]
        row[0], row[2] = c0 * a + c2 * b, c2 * a - c0 * b
    a, b = math.cos(r[0]), math.sin(r[0])                    # 0x49bb90, columns 1 / 2
    for row in m:
        c1, c2 = row[1], row[2]
        row[1], row[2] = c1 * a - c2 * b, c1 * b + c2 * a
    return m


def quat_of(m):
    """0x49d720 (x, y, z, w), normalised"""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0.0:
        q = [m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0], tr + 1.0]
    else:                                                    # largest diagonal (0x49d76c..), same rotation
        i = 0 if m[0][0] >= m[1][1] and m[0][0] >= m[2][2] else (1 if m[1][1] >= m[2][2] else 2)
        j, k = (i + 1) % 3, (i + 2) % 3
        q = [0.0, 0.0, 0.0, 0.0]
        q[i] = 1.0 + m[i][i] - m[j][j] - m[k][k]
        q[j] = m[i][j] + m[j][i]
        q[k] = m[i][k] + m[k][i]
        q[3] = m[j][k] - m[k][j]
    n = math.sqrt(sum(x * x for x in q))
    return [x / n for x in q]


def hamilton(a, b):
    """0x49c940 (x, y, z, w)"""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [ax * bw + aw * bx + ay * bz - az * by,
            ay * bw + aw * by + az * bx - ax * bz,
            az * bw + aw * bz + ax * by - ay * bx,
            aw * bw - ax * bx - ay * by - az * bz]


def rotate(q, v):
    """0x49cd40: (q (x) v) (x) conjugate(q)"""
    conj = [-q[0], -q[1], -q[2], q[3]]
    return hamilton(hamilton(q, [v[0], v[1], v[2], 0.0]), conj)[:3]


def engine_box_inside(p, centre, q, h):
    """0x46b730"""
    d = [p[i] - centre[i] for i in range(3)]
    local = rotate([-q[0], -q[1], -q[2], q[3]], d)
    return all(-h[i] <= local[i] <= h[i] for i in range(3))


def point_times(m, v):
    """0x49ba20: x*row0 + y*row1 + z*row2 + row3"""
    return [v[0] * m[0][i] + v[1] * m[1][i] + v[2] * m[2][i] + m[3][i] for i in range(3)]


def truMenu_rows(r):
    """TruMenu.cpp DvEulerRows (closed form)"""
    cx, sx, cy, sy, cz, sz = math.cos(r[0]), math.sin(r[0]), math.cos(r[1]), math.sin(r[1]), math.cos(r[2]), math.sin(r[2])
    return [[cz * cy, sz * cx + cz * sy * sx, sz * sx - cz * sy * cx],
            [-sz * cy, cz * cx - sz * sy * sx, cz * sx + sz * sy * cx],
            [sy, -cy * sx, cy * cx]]


def truMenu_point(pos, rows, a, b, c):
    return [pos[k] + a * rows[0][k] + b * rows[1][k] + c * rows[2][k] for k in range(3)]


def main(argv):
    transposed = '--transposed' in argv
    argv = [a for a in argv if a != '--transposed']
    n = int(argv[0]) if argv else 2000
    rnd = random.Random(20261106)
    fails = rows_bad = plane_bad = 0
    worst = 0.0
    for case in range(n):
        r = [rnd.uniform(-math.pi, math.pi) for _ in range(3)]
        if case < 4: r = [[0, 0, 0], [0, 0, math.pi / 2], [math.pi / 2, 0, 0], [0, math.pi / 2, 0]][case]
        h = [rnd.uniform(10, 2000) for _ in range(3)]
        centre = [rnd.uniform(-20000, 20000) for _ in range(3)]
        m = euler_matrix(r)
        rows = truMenu_rows(r)
        if transposed: rows = [[rows[k][i] for k in range(3)] for i in range(3)]
        for i in range(3):
            for k in range(3):
                worst = max(worst, abs(rows[i][k] - m[i][k]))
                if abs(rows[i][k] - m[i][k]) > 1e-9: rows_bad += 1
        q = quat_of(m)
        for corner in range(8):
            s = [1.0 if corner & 1 else -1.0, 1.0 if corner & 2 else -1.0, 1.0 if corner & 4 else -1.0]
            inner = truMenu_point(centre, rows, 0.999 * s[0] * h[0], 0.999 * s[1] * h[1], 0.999 * s[2] * h[2])
            outer = truMenu_point(centre, rows, 1.001 * s[0] * h[0], 1.001 * s[1] * h[1], 1.001 * s[2] * h[2])
            if not engine_box_inside(inner, centre, q, h) or engine_box_inside(outer, centre, q, h): fails += 1
        mt = [row[:] for row in m]
        mt[3] = [centre[0], centre[1], centre[2], 1.0]
        for sw, sh in ((1, -1), (1, 1), (-1, 1), (-1, -1)):
            a = point_times(mt, [sw * h[0], 0.0, sh * h[2]])
            b = truMenu_point(centre, rows, sw * h[0], 0.0, sh * h[2])
            if max(abs(a[i] - b[i]) for i in range(3)) > 1e-6: plane_bad += 1
    print('cases %d: matrix rows closed form vs 0x49d500 steps: %d element(s) off (worst %.2e)' % (n, rows_bad, worst))
    print('box corners (x0.999 inside, x1.001 outside the 0x46b730 test): %d of %d failed' % (fails, n * 8))
    print('plane corners vs 0x49ba20 (point * M + row 3): %d of %d differ' % (plane_bad, n * 4))
    ok = not (fails or rows_bad or plane_bad)
    print('RESULT %s' % ('pass' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
