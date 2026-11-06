"""Offline model checks for TruMenu 0.17 (read-only; 2026-11-06 TruMenu 0.17 quick toggles).

The rules of three new TruMenu.cpp parts, re-implemented here line by line as a MODEL (this does not run the C++ code -
it checks that the rules themselves do what the build report claims):
  1. depth   DpMapping's six view forms (row / column, camera-relative, of the inverse) with a least-squares scale k over
             five test points, |k| = 1 first, the first candidate whose projection passes (incl. the 0.17 span rule):
             for random cameras every form x scale x handedness is built from the true camera and must be accepted with
             the right z for 5 random points; one frame of lag (20 units / 0.5 degrees) must be accepted; views of
             unrelated cameras (depth axis > 10 degrees off) must be refused - at most 1 % coincidental fits pass.
  2. chord   QbPad's chord window: both combo buttons in one poll, staggered inside ChordMs, a lone tap (released early:
             the game gets a 100 ms tap), a lone hold (the game gets it late), the open bar owning D-pad / LB / RB, a
             D-pad held at the close staying away until released.
  3. frames  pos.go's conversion target = saved - P(saved) + P(now) against the memory dump numbers of
             docs/Befund-Position-und-Schrotflinte.md (test 50h: live - data = -V + P per unit).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trumenu_quick_check.py            all three, exit 1 on a failure
"""
import math, random, sys

NEAR = 16.5


# ---------------------------------------------------------------------------------------------------------------- depth
def cam_z(m, p):                       # the 0.14 camera: z' = m2 p0 + m6 p1 + m10 p2 + m14 (DvToCam)
    return m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]


def cam_pos(m):                        # DvCamPos: solve A p = -t
    a = [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]]
    b = [-m[12], -m[13], -m[14]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    out = []
    for c in range(3):
        aa = [row[:] for row in a]
        for r in range(3): aa[r][c] = b[r]
        d = (aa[0][0] * (aa[1][1] * aa[2][2] - aa[1][2] * aa[2][1]) - aa[0][1] * (aa[1][0] * aa[2][2] - aa[1][2] * aa[2][0])
             + aa[0][2] * (aa[1][0] * aa[2][1] - aa[1][1] * aa[2][0]))
        out.append(d / det)
    return out


def inv4(m):                           # general 4 x 4 inverse of the 16 stored floats (as DpInvert: same layout)
    a = [[m[r * 4 + c] for c in range(4)] + [1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-20: return None
        a[col], a[piv] = a[piv], a[col]
        f = a[col][col]
        a[col] = [x / f for x in a[col]]
        for r in range(4):
            if r != col:
                g = a[r][col]
                a[r] = [x - g * y for x, y in zip(a[r], a[col])]
    return [a[r][4 + c] for r in range(4) for c in range(4)]


def conv_z(conv, V, Vi, cam, p):       # DpConvZ
    M = Vi if conv >= 5 else V
    q = [p[k] - cam[k] for k in range(3)] if conv in (3, 4) else list(p)
    if conv & 1: return M[2] * q[0] + M[6] * q[1] + M[10] * q[2] + M[14]
    return M[8] * q[0] + M[9] * q[1] + M[10] * q[2] + M[11]


AHEAD, RIGHT, UP = (1000, 3000, 2000, 6000, 4000), (0, 700, 0, -1500, 900), (0, 0, 700, 0, -1200)   # kDpAhead ..


def projection(k, sign, near=16.0, far=100000.0):
    """a perspective projection in the scene's units (near / far scaled with k), row-vector layout as the scene's +0x100"""
    n, f = near * abs(k), far * abs(k)
    P = [0.0] * 16
    P[10], P[11], P[14], P[15] = sign * f / (f - n), sign, -n * f / (f - n), 0.0
    return P


def proj_ok(P, kk):                    # DpMapping's projection test for one candidate
    sign = -1.0 if kk < 0 else 1.0
    if abs(abs(P[11]) - 1.0) <= 0.02: w, b = P[11], P[14]
    elif abs(abs(P[14]) - 1.0) <= 0.02: w, b = P[14], P[11]
    else: return False
    if w == 0.0 or not abs(P[15]) < 1e-3 or not w * sign > 0.0: return False
    a = P[10]
    zn = (a * kk * NEAR + b) / (w * kk * NEAR)
    z1 = (a * kk * 1000.0 + b) / (w * kk * 1000.0)
    zf = (a * kk * 50000.0 + b) / (w * kk * 50000.0)
    near_ok = -0.03 < zn < 0.05 or 0.95 < zn < 1.03
    mono = zn < z1 < zf or zn > z1 > zf
    return near_ok and mono and -0.05 < zf < 1.05 and abs(zf - zn) >= 0.5


def mapping(V, P, m, ux, uy):          # DpMapping's view part: (form, k, inverse, camera) or None
    cam = cam_pos(m)
    f = [m[2], m[6], m[10]]
    r = [m[0] * ux, m[4] * ux, m[8] * ux]
    u = [m[1] * uy, m[5] * uy, m[9] * uy]
    fl = math.sqrt(sum(x * x for x in f))
    pts = [[cam[k] + f[k] / (fl * fl) * AHEAD[i] + r[k] * RIGHT[i] + u[k] * UP[i] for k in range(3)] for i in range(5)]
    zq = [cam_z(m, p) for p in pts]
    if min(zq) <= 100.0: return None
    Vi = inv4(V)
    cands = []
    for conv in range(1, 7):
        if conv >= 5 and Vi is None: continue
        z = [conv_z(conv, V, Vi, cam, p) for p in pts]
        k = sum(a * b for a, b in zip(z, zq)) / sum(b * b for b in zq)
        ak = abs(k)
        if not 1e-3 <= ak <= 1e3: continue
        err = max(abs(a - k * b) / (ak * b) for a, b in zip(z, zq))
        if all(abs(a - k * b) <= 0.03 * ak * b + 5.0 * ak for a, b in zip(z, zq)):
            cands.append((0 if abs(ak - 1.0) <= 0.03 else 1, err, conv, k))
    for _, _, conv, k in sorted(cands):
        if proj_ok(P, k): return conv, k, Vi, cam
    return None


def rot(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    rz = [[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]
    rx = [[1, 0, 0], [0, cp, -sp], [0, sp, cp]]
    ry = [[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]]
    mul = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(rz, rx), ry)


def camera(rng):
    """a 0.14-style camera: rows of R (world -> camera), translation -R c, x / y columns scaled (text space)"""
    R = rot(rng.uniform(-3, 3), rng.uniform(-1.2, 1.2), rng.uniform(-0.2, 0.2))
    c = [rng.uniform(-30000, 30000) for _ in range(3)]
    sx, sy = rng.uniform(0.8, 1.4), rng.uniform(1.0, 1.3)
    return cam_matrix(R, c, sx, sy), c, 1.0 / sx, 1.0 / sy


def cam_matrix(R, c, sx, sy):
    t = [-sum(R[i][k] * c[k] for k in range(3)) for i in range(3)]
    m = [0.0] * 16
    for k in range(3):                  # m[k*4 + i] = row i of R at column k (DvToCam: x' = m0 p0 + m4 p1 + m8 p2 + m12)
        m[k * 4 + 0] = R[0][k] * sx
        m[k * 4 + 1] = R[1][k] * sy
        m[k * 4 + 2] = R[2][k]
    m[12], m[13], m[14], m[15] = t[0] * sx, t[1] * sy, t[2], 1.0
    return m


def scene_view(m, c, form, k, sign):
    """the scene's view [scene+0x140] in a given form, its z row scaled by k (and sign = handedness)"""
    row = [m[0] / 1, m[1], m[2] * k * sign, 0.0, m[4], m[5], m[6] * k * sign, 0.0, m[8], m[9], m[10] * k * sign, 0.0,
           m[12], m[13], m[14] * k * sign, 1.0]
    if form in (3, 4):                  # camera-relative: no translation, applied to p - c
        row[12] = row[13] = row[14] = 0.0
    if form in (5, 6):                  # the stored matrix is the inverse (camera -> world)
        row = inv4(row)
    if form in (2, 4, 6):               # column vectors: the transpose
        row = [row[c4 * 4 + r4] for r4 in range(4) for c4 in range(4)]
    return row


def check_depth(rng):
    fails, refused_ok, false_accept, n = 0, 0, 0, 0
    why = {}
    for _ in range(400):
        m, c, ux, uy = camera(rng)
        for form in range(1, 7):
            for k in (1.0, 0.01, 2.54):
                for sign in (1.0, -1.0):
                    n += 1
                    V = scene_view(m, c, form, k, sign)
                    got = mapping(V, projection(k, sign), m, ux, uy)
                    key = 'form %d k %g sign %+d' % (form, k, sign)
                    if not got:
                        fails += 1
                        why[key + ': refused'] = why.get(key + ': refused', 0) + 1
                        continue
                    conv, kk, Vi, cam = got
                    for _ in range(5):          # the accepted form must give the true scene z for random points
                        p = [c[i] + rng.uniform(-8000, 8000) for i in range(3)]
                        want = cam_z(m, p) * k * sign
                        z = conv_z(conv, V, Vi, cam, p)
                        bad = abs(z - want) > 1e-6 * max(1.0, abs(want)) + 1e-3 or \
                            abs(kk * cam_z(m, p) - want) > 1e-6 * max(1.0, abs(want)) + 1e-3
                        if bad:
                            fails += 1
                            tag = '%s: accepted as form %d k %.4g, wrong z' % (key, conv, kk)
                            why[tag] = why.get(tag, 0) + 1
                            break
        # an unrelated view (another camera whose depth axis differs by more than 10 degrees, any form) must be refused -
        # with the same depth axis a camera-relative view gives the right depth anyway
        while True:
            m2, c2, _, _ = camera(rng)
            dot = m[2] * m2[2] + m[6] * m2[6] + m[10] * m2[10]
            if dot < math.cos(math.radians(10)): break
        k2, f2 = rng.choice((1.0, 0.01, 2.54)), rng.randint(1, 6)
        got = mapping(scene_view(m2, c2, f2, k2, 1.0), projection(k2, 1.0), m, ux, uy)
        if got:
            false_accept += 1
            tag = 'unrelated form %d k %g accepted as form %d k %.4g, cameras %.0f units apart' % (
                f2, k2, got[0], got[1], math.sqrt(sum((c[i] - c2[i]) ** 2 for i in range(3))))
            why[tag] = why.get(tag, 0) + 1
        else: refused_ok += 1
    # one frame of lag: the scene's view from a camera moved by up to 20 units / 0.5 degrees - accepted, z within 3 %
    lag_ok = lag_n = 0
    for _ in range(400):
        R = rot(rng.uniform(-3, 3), rng.uniform(-1.2, 1.2), rng.uniform(-0.2, 0.2))
        c = [rng.uniform(-30000, 30000) for _ in range(3)]
        m = cam_matrix(R, c, 1.1, 1.17)
        d = math.radians(0.5)
        R2 = rot(0.0, 0.0, 0.0)
        R2 = [[sum(R[i][k] * rot(rng.uniform(-d, d), rng.uniform(-d, d), 0.0)[k][j] for k in range(3)) for j in range(3)]
              for i in range(3)]
        c2 = [c[i] + rng.uniform(-20, 20) for i in range(3)]
        form = rng.randint(1, 6)
        V = scene_view(cam_matrix(R2, c2, 1.1, 1.17), c2, form, 1.0, 1.0)
        lag_n += 1
        got = mapping(V, projection(1.0, 1.0), m, 1 / 1.1, 1 / 1.17)
        if got and got[1] > 0 and abs(got[1] - 1.0) < 0.03: lag_ok += 1
    print('depth: %d form / scale / sign cases, %d wrong; unrelated views refused %d, falsely accepted %d; one frame of lag '
          'accepted %d / %d' % (n, fails, refused_ok, false_accept, lag_ok, lag_n))
    for tag in sorted(why)[:20]: print('depth:   %s x%d' % (tag, why[tag]))
    # six forms give an unrelated view more chances to fit by coincidence: up to 1 % is accepted as the known limit
    # (the effect would be wrongly hidden lines, nothing else) - the build report quotes the measured number
    return fails == 0 and false_accept <= (refused_ok + false_accept) // 100 and lag_ok == lag_n


# ---------------------------------------------------------------------------------------------------------------- chord
OWN = 0x030F


class Pad:                              # QbPad's per-pad state (one pad), times in ms
    def __init__(self, combo=0x0030, chord=250):
        self.combo, self.chord = combo, chord
        self.prev = self.gated = self.passed = self.owned = self.inject = 0
        self.gate_from = self.inject_until = 0
        self.latched = False
        self.open = False

    def poll(self, now, buttons, active=True):
        c = buttons & self.combo
        down, up = c & ~self.prev, self.prev & ~c
        self.prev = c
        clear, toggled = 0, False
        if self.latched:
            if c: clear |= c
            else: self.latched = False
        elif not active:
            self.gated = 0; self.gate_from = 0; self.passed = c
        elif c == self.combo and down:
            toggled = True; self.latched = True; self.gated = self.passed = 0; self.gate_from = 0; clear |= c
        else:
            fresh = down & ~self.passed
            if fresh:
                if not self.gated: self.gate_from = now
                self.gated |= fresh
            tap = up & self.gated
            if tap:
                self.inject |= tap; self.inject_until = now + 100; self.gated &= ~tap
            if self.gated and now - self.gate_from >= self.chord:
                self.passed |= self.gated; self.gated = 0
            if not self.gated: self.gate_from = 0
            clear |= self.gated
        self.passed &= c
        inject = 0
        if self.inject:
            if now < self.inject_until: inject = self.inject
            else: self.inject = 0
        if toggled: self.open = not self.open
        if self.open and active: self.owned |= buttons & OWN
        self.owned &= buttons
        clear |= self.owned
        clear &= ~inject
        return (buttons & ~clear) | inject   # what the game gets


def run(seq, pad=None, step=16):
    """seq = [(t_from, t_to, buttons)]; returns [(t, game buttons)] every 16 ms"""
    pad = pad or Pad()
    out, t, end = [], 0, max(s[1] for s in seq)
    while t <= end:
        b = 0
        for a, z, bb in seq:
            if a <= t < z: b |= bb
        out.append((t, pad.poll(t, b), pad.open))
        t += step
    return out, pad


def check_chord():
    ok, lines = True, []
    V, S, UP, LB = 0x0020, 0x0010, 0x0001, 0x0100
    # 1. View + Start in the same poll: toggles, the game never sees either
    out, pad = run([(0, 200, V | S), (200, 400, 0)])
    r = pad.open and all(g & (V | S) == 0 for _, g, _ in out)
    lines.append(('both at once: opens, game sees nothing', r)); ok &= r
    # 2. staggered 100 ms (inside ChordMs 250): toggles, the game never sees either
    out, pad = run([(0, 300, V), (100, 300, S), (300, 500, 0)])
    r = pad.open and all(g & (V | S) == 0 for _, g, _ in out)
    lines.append(('View, then Start 100 ms later: opens, game sees nothing', r)); ok &= r
    # 3. a lone tap of Start (80 ms): no toggle, the game gets Start as a tap right after the release
    out, pad = run([(0, 80, S), (80, 400, 0)])
    seen = [t for t, g, _ in out if g & S]
    r = not pad.open and seen and seen[0] >= 80 and seen[-1] - seen[0] <= 100
    lines.append(('lone Start tap 80 ms: game gets a tap at %s ms' % (seen[0] if seen else '-'), bool(r))); ok &= bool(r)
    # 4. a lone hold of Start (600 ms): the game gets it after ChordMs, held until the release
    out, pad = run([(0, 600, S), (600, 800, 0)])
    seen = [t for t, g, _ in out if g & S]
    r = not pad.open and seen and 240 <= seen[0] <= 270 and seen[-1] < 600
    lines.append(('lone Start hold 600 ms: game gets it from %s ms' % (seen[0] if seen else '-'), bool(r))); ok &= bool(r)
    # 5. open bar: D-pad / LB stay away from the game, B (0x2000) and the sticks pass
    out, pad = run([(0, 100, V | S), (100, 200, 0), (200, 300, UP | LB | 0x2000), (300, 400, 0)])
    mid = [g for t, g, _ in out if 200 <= t < 300]
    r = pad.open and all(g & (UP | LB) == 0 and g & 0x2000 for g in mid)
    lines.append(('open: D-pad / LB kept, B passes', r)); ok &= r
    # 6. close while D-pad held: the D-pad stays away until it is released (no press edge at the close)
    out, pad = run([(0, 100, V | S), (100, 200, 0), (200, 600, UP), (300, 400, V | S), (600, 700, 0), (700, 800, UP)])
    held = [g for t, g, _ in out if 400 <= t < 600]
    again = [g for t, g, _ in out if 700 <= t < 800]
    r = not pad.open and all(g & UP == 0 for g in held) and all(g & UP for g in again)
    lines.append(('closed with D-pad held: kept until released, the next press passes', r)); ok &= r
    # 7. menu / ring own the pad (active False): no toggle, nothing changed
    pad = Pad()
    seen = [pad.poll(t, V | S, active=False) for t in range(0, 300, 16)]
    r = not pad.open and all(g == V | S for g in seen)
    lines.append(('menu / ring open: no toggle, the pad unchanged (their own neutral pad applies)', r)); ok &= r
    for text, good in lines: print('chord: %-75s %s' % (text, 'ok' if good else 'FAIL'))
    return ok


# --------------------------------------------------------------------------------------------------------------- frames
def check_frames():
    # docs/Befund-Position-und-Schrotflinte.md, test 50h (Lara in hall01): live - data = -V + P per unit
    units = {'dlc_yggdrasil_hall01': ((-756.2, 696.1, 2119.6), (0.0, 0.0, 0.0)),
             'dlc_level2_start': ((0.0, -3048.9, 683.2), (-11569.0, -3696.0, -172.0)),
             'dlc_yggdrasil_hall02': ((-4597.0, 6469.0, -951.5), (2479.0, 17149.0, -3070.0))}
    dump = {'dlc_yggdrasil_hall01': (756.2, -696.1, -2119.6), 'dlc_level2_start': (-11569.0, -647.1, -855.2),
            'dlc_yggdrasil_hall02': (7076.0, 10680.0, -2118.5)}
    ok = True
    for u, (V, P) in units.items():
        d = tuple(-V[i] + P[i] for i in range(3))
        good = all(abs(d[i] - dump[u][i]) < 0.15 for i in range(3))
        print('frames: %-22s -V + P = %8.1f %8.1f %8.1f  dump %8.1f %8.1f %8.1f  %s' % ((u,) + d + dump[u] + ('ok' if good else 'FAIL',)))
        ok &= good
    # save in dlc_level2_start while Lara is there (P = 0), go while Lara is in hall01 (P = the dump's value)
    data = (684.0, -4197.9, -7263.8)                      # floor point of shot PC-Test50h_58 (data coordinates)
    V, P_now = units['dlc_level2_start']
    saved = tuple(data[i] - V[i] for i in range(3))       # live then (P = 0): 684 / -1149 / -7947 as the shot shows
    target = tuple(saved[i] - 0.0 + P_now[i] for i in range(3))
    want = tuple(data[i] - V[i] + P_now[i] for i in range(3))
    good = all(abs(target[i] - want[i]) < 1e-6 for i in range(3)) and abs(saved[1] - (-1149.0)) < 0.2
    print('frames: saved in level2_start %.1f %.1f %.1f -> from hall01 %.1f %.1f %.1f (= data - V + P now)  %s'
          % (saved + target + ('ok' if good else 'FAIL',)))
    return ok and good


def main():
    rng = random.Random(17)
    results = [check_depth(rng), check_chord(), check_frames()]
    print('all ok' if all(results) else 'FAILED')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
