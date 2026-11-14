"""W5 (2026-11-14): which markup segments are the three parallel yellow lines of ShareX 21:20:12 (sx_212012_kJhUUhMFIf)?

Candidates (all in the dlc_caverns live frame, where Lara stood at (-458.8 -1333.3 -122.1)):
  * markup2 segments of dlc_caverns, dlc_caverns_hall, dlc_level1_start (other units moved by their origin difference -
    the W3 bridge copies prove that rule: dlc_level1_start 9920 + (start origin - caverns origin) = dlc_caverns 9865)
  * object markup segments of the DLC 1 objects as TruMenu 0.3 DrawMarkup draws them (record points untransformed =
    the object's local frame placed at the world origin)
For every triple of mutually parallel segments (within 4 degrees, each >= 300 units) the no-roll camera of the
0xe804a0 matrix (w5_fit_camera.py) is fitted to the 6 end points plus Lara's feet (TruMenu cross, about (610, 690)), in
both segment directions and every assignment of the three segments to the top / middle / bottom line. Vectorised
over a 1-degree yaw / pitch grid, then refined.

Usage (from the repository root):
  ../bin/pyt -t 1800 work/w5_1411/w5_line_search.py OWN_UNIT_DIR OWN_OBJECT_DIR
"""
import sys, os, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from w5_unit_markup import load
from w5_obj_markup import object_arrays

F = 463.53
SX, SY = 0.75, 448.0 / 384.0
SHOT = [((435, 177), (940, 147)), ((412, 278), (974, 248)), ((349, 563), (1071, 539))]   # top, middle, bottom
LARA = np.array([-458.8, -1333.3, -122.1]); LARA_SHOT = (610.0, 690.0)


def segments(unit_dir, obj_dir):
    segs = []
    base = None
    for u in ('dlc_caverns', 'dlc_caverns_hall', 'dlc_level1_start'):
        items, head, origin = load(os.path.join(unit_dir, u + '.drm'), False)
        if base is None: base = np.array(origin)
        shift = np.array(origin) - base
        for it in items:
            pts = [np.array(p) + shift for p in it[8]]
            for a, b in zip(pts, pts[1:]):
                segs.append(('%s markup2 %d' % (u, it[3]), a, b))
    for n in sorted(os.listdir(obj_dir)):
        if not n.endswith('.drm'): continue
        for dtp, cnt, recs in object_arrays(os.path.join(obj_dir, n), False):
            for k, rid, bone, skip, typ, pos, pts in recs:
                pts = [np.array(p) for p in pts]
                for a, b in zip(pts, pts[1:]):
                    segs.append(('%s object %d (local at origin)' % (n[:-4], rid), a, b))
    return [s for s in segs if np.linalg.norm(s[2] - s[1]) >= 300.0]


def grid_fit(P, S, step=1.0, a0=None, b0=None, span=None):
    if a0 is None:
        A = np.radians(np.arange(0, 360, step)); B = np.radians(np.arange(-89, 89.01, step))
    else:
        A = a0 + np.radians(np.arange(-span, span, step)); B = b0 + np.radians(np.arange(-span, span, step))
    aa, bb = np.meshgrid(A, B, indexing='ij'); aa = aa.ravel(); bb = bb.ravel()
    r = np.stack([np.cos(aa), np.sin(aa), np.zeros_like(aa)], 1)
    d = np.stack([-np.sin(aa) * np.cos(bb), np.cos(aa) * np.cos(bb), np.sin(bb)], 1)
    dn = np.cross(d, r)
    u = (S[:, 0] / 2.5 - 256.0) / F; v = (S[:, 1] * 448.0 / 720.0 - 224.0) / F
    rp = SX * r @ P.T; dp = d @ P.T; np_ = SY * dn @ P.T              # (G, N)
    G, N = rp.shape
    M = np.zeros((G, 2 * N, 3)); y = np.zeros((G, 2 * N))
    M[:, 0::2, 0] = 1.0; M[:, 0::2, 2] = -u; y[:, 0::2] = -rp + u * dp
    M[:, 1::2, 1] = 1.0; M[:, 1::2, 2] = -v; y[:, 1::2] = -np_ + v * dp
    MT = np.transpose(M, (0, 2, 1))
    t = np.linalg.solve(MT @ M + 1e-9 * np.eye(3), (MT @ y[..., None]))[..., 0]
    x = rp + t[:, 0:1]; yy = np_ + t[:, 1:2]; z = dp + t[:, 2:3]
    ok = np.all(z > 16.0, axis=1)
    sx = (x / np.where(z > 1e-6, z, 1e-6) * F + 256.0) * 2.5
    sy = (yy / np.where(z > 1e-6, z, 1e-6) * F + 224.0) * 720.0 / 448.0
    err = np.max(np.hypot(sx - S[:, 0], sy - S[:, 1]), axis=1)
    err[~ok] = 1e9
    i = int(np.argmin(err))
    return float(err[i]), aa[i], bb[i], t[i]


def main(argv):
    segs = segments(argv[0], argv[1])
    print('%d candidate segments (>= 300 units)' % len(segs))
    # second pass (the full search was too slow): only segments whose midpoint lies within 8000 units of Lara, the
    # three lines assigned top / middle / bottom by the height of their midpoints (no roll), heights >= 80 apart
    segs = [s for s in segs if np.linalg.norm((s[1] + s[2]) / 2.0 - LARA) <= 8000.0]
    print('%d of them within 8000 units of Lara' % len(segs), flush=True)
    dirs = [(s[2] - s[1]) / np.linalg.norm(s[2] - s[1]) for s in segs]
    S = np.array([p for line in SHOT for p in line] + [LARA_SHOT], dtype=float)
    results = []
    cos_lim = np.cos(np.radians(3.0))
    n = len(segs)
    mz = [float((s[1][2] + s[2][2]) / 2.0) for s in segs]
    for i, j, k in itertools.combinations(range(n), 3):
        if abs(dirs[i] @ dirs[j]) < cos_lim or abs(dirs[i] @ dirs[k]) < cos_lim: continue
        order = tuple(sorted((i, j, k), key=lambda q: -mz[q]))
        if mz[order[0]] - mz[order[1]] < 80.0 or mz[order[1]] - mz[order[2]] < 80.0: continue
        for order in (order,):
            for flip in (False, True):
                P = []
                for q in order:
                    a, b = segs[q][1], segs[q][2]
                    if (dirs[q] @ dirs[i] < 0) != flip: a, b = b, a
                    P.extend([a, b])
                P.append(LARA)
                P = np.array(P)
                e, a, b, t = grid_fit(P, S, step=2.0)
                if e < 400:
                    e, a, b, t = grid_fit(P, S, step=0.1, a0=a, b0=b, span=2.0)
                results.append((e, [segs[q][0] for q in order], flip, np.degrees(a), np.degrees(b)))
    results.sort(key=lambda r: r[0])
    print('%d parallel triples x orders tried' % len(results))
    for e, names, flip, a, b in results[:12]:
        print('worst error %6.1f px  yaw %6.1f pitch %5.1f  top / middle / bottom = %s%s' % (
            e, a, b, ' | '.join(names), ' (flipped)' if flip else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
