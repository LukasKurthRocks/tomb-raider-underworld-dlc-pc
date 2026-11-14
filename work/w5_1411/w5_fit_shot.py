"""W5 (2026-11-14): which markup poly line is the line on a screenshot? Keep the camera rotation of the nearest TruMenu
'matrix 0xe804a0' log line, fit the 3 translation values so that the item's points land on the clicked screen points
(1280 x 720 shot), and print the residual per candidate (Gauss-Newton on numpy, no scipy).

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_fit_shot.py UNIT.drm "r0 | r1 | r2 | t T" "x1,y1 x2,y2 x3,y3" [--npts 3]
"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from w5_unit_markup import load
from w5_obj_markup import parse_matrix
import markup_level as ML

F = 463.53


def proj(m, t, p):
    x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + t[0]
    y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + t[1]
    z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + t[2]
    return np.array([(x / z * F + 256.0) * 2.5, (y / z * F + 224.0) * 720.0 / 448.0]), z


def fit(m, t0, pts, obs):
    t = np.array(t0, dtype=float)
    for _ in range(60):
        r = []; J = []
        for p, o in zip(pts, obs):
            s, z = proj(m, t, p)
            if z <= 16: return None, 1e9
            r.extend(s - o)
            row = []
            for k in range(3):
                d = np.zeros(3); d[k] = 1.0
                s2, _ = proj(m, t + d, p)
                row.append(s2 - s)
            J.append([row[0][0], row[1][0], row[2][0]]); J.append([row[0][1], row[1][1], row[2][1]])
        r = np.array(r); J = np.array(J)
        step, *_ = np.linalg.lstsq(J, -r, rcond=None)
        t = t + step
        if np.linalg.norm(step) < 1e-3: break
    res = [np.linalg.norm(proj(m, t, p)[0] - o) for p, o in zip(pts, obs)]
    return t, max(res)


def main(argv):
    npts = 3
    if '--npts' in argv:
        k = argv.index('--npts'); npts = int(argv[k + 1]); del argv[k:k + 2]
    items, head, origin = load(argv[0], False)
    m = parse_matrix(argv[1])
    t0 = m[12:15]
    obs = [np.array([float(v) for v in q.split(',')]) for q in argv[2].split()]
    rows = []
    for it in items:
        pts = it[8]
        if len(pts) != npts: continue
        for order in (pts, pts[::-1]):
            t, res = fit(m, t0, order, obs)
            if t is None: continue
            rows.append((res, it[3], it[6], float(np.linalg.norm(t - np.array(t0))), t))
    rows.sort(key=lambda r: r[0])
    for res, iid, typ, moved, t in rows[:8]:
        print('id %5d type %2d %-12s max residual %6.1f px, camera t moved %7.1f units -> t %.1f %.1f %.1f' % (
            iid, typ, ML.tname(typ), res, moved, t[0], t[1], t[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
