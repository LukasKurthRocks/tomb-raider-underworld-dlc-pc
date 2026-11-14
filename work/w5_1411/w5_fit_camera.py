"""W5 (2026-11-14): reconstruct the game camera of a screenshot from drawn line end points and a set of candidate 3D
lines, then check the result against an independent point (Lara's logged position vs her feet on the shot).

Camera model = the game's 0xe804a0 matrix as TruMenu logs it: no roll (third x' coefficient always 0.000 in the log),
x' = 0.75 * right (4/3 / aspect 1.7777), y' = 448/384 * (forward x right), z' = forward, + t; screen = (x'/z' * 463.53 +
256, y'/z' * 463.53 + 224) on 512 x 448, scaled to 1280 x 720. For each yaw / pitch on a 0.5 degree grid the
translation is solved linearly (least squares), then the best pose is refined on a finer grid.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_fit_camera.py CASE
  CASE = gates2120 (the three parallel lines of ShareX 21:20:12 vs the cavern gate object markup drawn untransformed)
"""
import sys
import numpy as np

F = 463.53
SX, SY = 0.75, 448.0 / 384.0


def axes(a, b):
    r = np.array([np.cos(a), np.sin(a), 0.0])
    d = np.array([-np.sin(a) * np.cos(b), np.cos(a) * np.cos(b), np.sin(b)])
    return r, d, np.cross(d, r)


def solve_t(a, b, P, S):
    r, d, dn = axes(a, b)
    A = []; y = []
    for p, s in zip(P, S):
        u = (s[0] / 2.5 - 256.0) / F
        v = (s[1] * 448.0 / 720.0 - 224.0) / F
        # SX*r.p + tx - u*(d.p + tz) = 0 ; SY*dn.p + ty - v*(d.p + tz) = 0
        A.append([1.0, 0.0, -u]); y.append(-(SX * r @ p) + u * (d @ p))
        A.append([0.0, 1.0, -v]); y.append(-(SY * dn @ p) + v * (d @ p))
    t, *_ = np.linalg.lstsq(np.array(A), np.array(y), rcond=None)
    return t


def project(a, b, t, p):
    r, d, dn = axes(a, b)
    x = SX * r @ p + t[0]; yv = SY * dn @ p + t[1]; z = d @ p + t[2]
    if z <= 16: return None
    return np.array([(x / z * F + 256.0) * 2.5, (yv / z * F + 224.0) * 720.0 / 448.0])


def resid(a, b, t, P, S):
    worst = 0.0
    for p, s in zip(P, S):
        q = project(a, b, t, p)
        if q is None: return 1e9
        worst = max(worst, float(np.linalg.norm(q - s)))
    return worst


def fit(P, S):
    best = (1e18, 0, 0, None)
    for a in np.radians(np.arange(0, 360, 0.5)):
        for b in np.radians(np.arange(-89, 89.5, 0.5)):
            t = solve_t(a, b, P, S)
            e = resid(a, b, t, P, S)
            if e < best[0]: best = (e, a, b, t)
    e, a0, b0, _ = best
    for a in a0 + np.radians(np.arange(-0.5, 0.5, 0.02)):
        for b in b0 + np.radians(np.arange(-0.5, 0.5, 0.02)):
            t = solve_t(a, b, P, S)
            e2 = resid(a, b, t, P, S)
            if e2 < best[0]: best = (e2, a, b, t)
    return best


def camera_pos(a, b, t):
    r, d, dn = axes(a, b)
    M = np.array([SX * r, SY * dn, d])
    return -np.linalg.solve(M, t)


def main(argv):
    case = argv[0] if argv else 'gates2120'
    if case != 'gates2120':
        print(__doc__); return 2
    # ShareX 21:20:12 (sx_212012_kJhUUhMFIf.jpg, 1280 x 720), end points read off the image (left, right)
    shot = {'top': ((435, 177), (940, 147)), 'mid': ((412, 278), (974, 248)), 'bot': ((349, 563), (1071, 539))}
    # object markup (local frame) of dlc1_uo_cavern_hall_gate 20854 (2309 z 468, 2310 z 1100) and _two 20861 (2311 z
    # 468, 2312 z 1418): x -55, y -575 .. 562 (work/w5_1411/obj_markup_own_2153.txt)
    lines = {'top': 1418.0, 'mid': 1100.0, 'bot': 468.0}
    lara = np.array([-458.8, -1333.3, -122.1])      # TruMenu.log 21:20:05 / 21:20:15 (Lara did not move)
    for flip in (False, True):
        P = []; S = []
        for k, z in lines.items():
            ends = [np.array([-55.0, -575.0, z]), np.array([-55.0, 562.0, z])]
            if flip: ends = ends[::-1]
            for p, s in zip(ends, shot[k]):
                P.append(p); S.append(np.array(s, dtype=float))
        e, a, b, t = fit(P, S)
        q = project(a, b, t, lara)
        c = camera_pos(a, b, t)
        print('case %s, line direction %s: worst end point error %.1f px (6 points, 5 unknowns), yaw %.1f deg, pitch %.1f deg, '
              'camera at (%.0f %.0f %.0f), t %.1f %.1f %.1f' % (case, 'flipped' if flip else 'as listed', e, np.degrees(a),
                                                                 np.degrees(b), c[0], c[1], c[2], t[0], t[1], t[2]))
        print('   Lara (%.1f %.1f %.1f) -> shot %s; camera - Lara distance %.0f units' % (
            lara[0], lara[1], lara[2], 'behind the camera' if q is None else '(%.0f %.0f)' % (q[0], q[1]),
            float(np.linalg.norm(c - lara))))
    # second run: Lara's feet (TruMenu cross at about (610, 690) on the shot) as a seventh point
    for flip in (False, True):
        P = []; S = []
        for k, z in lines.items():
            ends = [np.array([-55.0, -575.0, z]), np.array([-55.0, 562.0, z])]
            if flip: ends = ends[::-1]
            for p, s in zip(ends, shot[k]):
                P.append(p); S.append(np.array(s, dtype=float))
        P.append(lara); S.append(np.array([610.0, 690.0]))
        e, a, b, t = fit(P, S)
        errs = ['%.0f' % float(np.linalg.norm(project(a, b, t, p) - s)) if project(a, b, t, p) is not None else 'x'
                for p, s in zip(P, S)]
        print('with Lara, direction %s: worst error %.1f px, per point %s, yaw %.1f pitch %.1f' % (
            'flipped' if flip else 'as listed', e, ' '.join(errs), np.degrees(a), np.degrees(b)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
