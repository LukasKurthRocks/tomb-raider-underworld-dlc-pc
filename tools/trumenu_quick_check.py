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
2026-11-06 TruMenu 0.18 adds two models:
  4. segments  shot.oncine's segments (OnCineTick / OcSegReason / OcSegStart): the live case 18:12:56 - 18:16:00 (0.17
             rules: one cutscene, 10 pairs used up after ~35 s; 0.18: a second segment with pairs in the exterior part),
             a cinematic object appearing after the camera signal (adopted, no new segment), a script print and the 1 s
             minimum, a unit name differing only in case (no change), the 2 s end debounce.
  5. confirm   the bar's second-press confirmation (QbConfirm / QbArmed: same key within 3 s).
2026-11-06 TruMenu 0.19 dumb AI adds three models (section "---- 0.19 dumb AI" of TruMenu.cpp):
  6. presets   RunAiDumb / AiPresetOn / RadialOn: ring and bar rows "ai.dumb <preset>" get "<preset> 0|1" from the shown
             state; one setting at a time (a group replaces the other), "<preset> 0" switches off only its own active
             setting, "" / "1" bring the last setting back (also an own list), "filter" = [AI] DumbFilter.
  7. burst     AiSecondTick's log rule at 60 frames per second: per-frame removals never give more than one line per
             burst end, a long burst one line every 30 s, a pause under 2 s keeps the burst, 2 s ends it.
  8. bits      AiBitsSet / AiBitsSweep: only the brain+8 bits TruMenu set are cleared again (a bit the game set stays),
             a bit the game clears is set again while on, out of scope / off clears TruMenu's bits, a gone brain drops
             its record without a write.
2026-11-06 TruMenu 0.20 changes model 4 and adds three models:
  4. segments  (0.20) OcSegReason no longer starts a segment on a TRACK change of the same cinematic object (the track
             is followed): the live case 20:23 (track 0 -> 28 -> 60 -> 92 .. once a second = a new pair every second
             with the 0.18 rule) must give ONE segment; a new cinematic object, a unit change and a script print still
             start one (the 0.18 cases keep their results).
  9. goload    RunPosGoLoad's path: loaded -> flight + pos.go; not loaded with a portal of a loaded unit (portal name =
             the target unit, case-insensitive, never the target's own portals) -> flight + pos.portal + wait.unit +
             pos.go; no such portal or "load" -> level.load + flight + pos.go.
 10. waitunit  ShortcutTick's wait.unit: the unit must be loaded 1 s in a row (a flicker restarts the second), at most
             30 s, then the run stops with the reason.
 11. forget    AiForgetOnce: once per enemy {instance, handle id} and setting; a new setting / ai.dumb off / a level
             change forgets again; the slot rule (mode 1 = Lara's handle, mode 0 = a sense whose target is Lara, mode -1 /
             2 / another target untouched); +0x30 / +0xf0 cleared, +0x70 / +0xb0 only counted.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trumenu_quick_check.py            all eleven, exit 1 on a failure
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


# ------------------------------------------------------------------------------------------------- 0.18 cutscene segments
def oc_run(timeline, end, segments=True, pairs=10, fast=4, fast_ms=1500, slow_ms=8000, end_ms=2000, seg_min=1000,
           track_seg=False):
    """OnCineTick / OcSegReason / OcSegStart as a model, polled every 50 ms. timeline(t) -> (signal, unit, cine, track,
    script_tick). Returns [(segment, [pair times])]. track_seg=True = the 0.18 rule (a track change starts a segment),
    False = 0.20 (the track of the same cinematic is followed)."""
    st = None
    segs = []
    for t in range(0, end, 50):
        sig, unit, cine, track, script = timeline(t)
        if st is not None:
            if not sig:
                st['off'] = st['off'] if st['off'] is not None else t
                if t - st['off'] >= end_ms: st = None
                continue
            st['off'] = None
            why = ''
            if segments and t - st['seg_start'] >= seg_min:
                if unit and st['unit'] and unit.lower() != st['unit'].lower(): why = 'unit'
                elif cine and track != -1 and (not st['cine'] or st['track'] == -1):
                    st['cine'], st['track'] = cine, track          # adopt, no new segment
                elif cine and track != -1 and (cine != st['cine'] or (track_seg and track != st['track'])): why = 'cine'
                elif cine and track != -1: st['track'] = track             # 0.20: followed, no new segment
                if not why and script and script != st['script'] and script > st['seg_start']: why = 'script'
            if why:
                st.update(seg_start=t, next=t, done=0, unit=unit, cine=cine, track=track, script=script)
                segs.append((len(segs) + 1, []))
        else:
            if not sig: continue
            st = dict(seg_start=t, next=t, done=0, unit=unit, cine=cine, track=track, script=script, off=None)
            segs.append((len(segs) + 1, []))
        if st['done'] < pairs and t >= st['next']:
            segs[-1][1].append(t)
            st['done'] += 1
            st['next'] = t + (fast_ms if st['done'] < fast else slow_ms)
    return segs


def check_segments():
    """the live case 2026-11-06 18:12:56 - 18:16:00: cutscene 160 (main hall) flowed into 170 (exterior, a level change)
    without the gameplay camera coming back; plus the adopt / script / case / end-debounce rules"""
    ok = True
    change = 118000                                     # ~18:14:54: the exterior cutscene 170 (unit + cinematic change)
    def live(t):
        if t < change: return True, 'l3_main_hall', 0x1000, 160, 0
        return True, 'l3_mansion_exterior_afterburn', 0x2000, 170, 0
    old = oc_run(live, 184000, segments=False, slow_ms=5000)   # 0.17 rules
    new = oc_run(live, 184000)
    last_old = old[0][1][-1] if old and old[0][1] else -1
    good = len(old) == 1 and len(old[0][1]) == 10 and 33000 <= last_old <= 36000   # live: used up at 18:13:31 (+35 s)
    print('segments: 0.17 rules - %d segment, %d pairs, the last at +%.1f s (live: +35 s)  %s'
          % (len(old), len(old[0][1]) if old else 0, last_old / 1000.0, 'ok' if good else 'FAIL'))
    ok &= good
    after = sum(1 for s, ts in new for x in ts if x >= change)
    good = len(new) == 2 and after >= 4 and all(len(ts) <= 10 for s, ts in new)
    print('segments: 0.18 rules - %d segments (%s pairs), %d pair(s) in the exterior part  %s'
          % (len(new), ' + '.join(str(len(ts)) for s, ts in new), after, 'ok' if good else 'FAIL'))
    ok &= good
    # the camera signal comes first, the cinematic object 0.3 s later: adopted, no second segment
    def late(t): return True, 'u', (0x1000 if t >= 300 else 0), (5 if t >= 300 else -1), 0
    s = oc_run(late, 20000)
    good = len(s) == 1
    print('segments: cinematic appears 0.3 s after the camera signal -> %d segment(s)  %s' % (len(s), 'ok' if good else 'FAIL'))
    ok &= good
    # a script print 'StartCinematic called' at +12 s -> segment 2; a unit change 0.5 s later waits for the 1 s minimum
    def script(t): return True, ('a' if t < 12500 else 'b'), 0x1000, 1, (12000 if t >= 12000 else 0)
    s = oc_run(script, 30000)
    starts = [ts[0] if ts else -1 for _, ts in s]
    good = len(s) == 3 and starts[1] == 12000 and starts[2] == 13000
    print('segments: script print at 12.0 s, unit change at 12.5 s -> segment starts %s  %s'
          % ([x / 1000.0 for x in starts], 'ok' if good else 'FAIL'))
    ok &= good
    # case only: "L3_main_bedroom" vs "l3_main_bedroom" is no unit change
    def case(t): return True, ('L3_main_bedroom' if t < 5000 else 'l3_main_bedroom'), 0x1000, 1, 0
    s = oc_run(case, 20000)
    good = len(s) == 1
    print('segments: unit name changes only in case -> %d segment(s)  %s' % (len(s), 'ok' if good else 'FAIL'))
    ok &= good
    # the signal gone 1.9 s keeps the cutscene, 2.1 s ends it (a new one starts when it comes back)
    def gap(t): return (t < 5000 or t >= 6900), 'u', 0, -1, 0
    def gap2(t): return (t < 5000 or t >= 7100), 'u', 0, -1, 0
    a, b = oc_run(gap, 15000), oc_run(gap2, 15000)
    good = len(a) == 1 and len(b) == 2
    print('segments: signal gone 1.9 s -> %d burst(s), 2.1 s -> %d  %s' % (len(a), len(b), 'ok' if good else 'FAIL'))
    ok &= good
    # 0.20: the live case 2026-11-06 20:23 - one cinematic object, its track 0 -> 28 -> 60 -> 92 .. once a second, 60 s
    def track(t): return True, 'dlc_level1_start', 0x3000, (t // 1000) * 32 - (4 if t >= 1000 else 0), 0
    old = oc_run(track, 60000, track_seg=True)
    new = oc_run(track, 60000)
    old_pairs = sum(len(ts) for s, ts in old)
    good = len(old) >= 50 and len(new) == 1 and len(new[0][1]) == 10
    print('segments: 0.20 - track changes of one cinematic every second for 60 s -> 0.18 rule %d segments / %d pairs, '
          '0.20 rule %d segment / %d pairs  %s' % (len(old), old_pairs, len(new), sum(len(ts) for s, ts in new),
                                                    'ok' if good else 'FAIL'))
    ok &= good
    # 0.20: a new cinematic object at +20 s still starts a segment (with the track running in both)
    def obj(t): return True, 'u', (0x3000 if t < 20000 else 0x4000), (t // 1000) * 32, 0
    s = oc_run(obj, 40000)
    good = len(s) == 2 and s[1][1] and s[1][1][0] == 20000
    print('segments: 0.20 - another cinematic object at 20 s -> %d segments  %s' % (len(s), 'ok' if good else 'FAIL'))
    return ok and good


# ---------------------------------------------------------------------------------------------------- 0.20 pos.goload
def goload_steps(name, unit, loaded_units, portals, force=False):
    """RunPosGoLoad as a model. loaded_units: names with state 2; portals: {owner unit: [portal names]}. Returns the step
    list of the shortcut."""
    loaded = any(u.lower() == unit.lower() for u in loaded_units)
    portal = None
    if not loaded and not force:
        for owner in loaded_units:                      # PosPortalTo: loaded units, never the target itself
            if owner.lower() == unit.lower(): continue
            if any(p.lower() == unit.lower() for p in portals.get(owner, [])):
                portal = owner
                break
    if loaded: return ['cheat.flight 1', 'pos.go %s' % name]
    if portal: return ['cheat.flight 1', 'pos.portal %s' % unit, 'wait.unit %s' % unit, 'pos.go %s' % name]
    return ['level.load %s' % unit, 'cheat.flight 1', 'pos.go %s' % name]


def check_goload():
    portals = {'l3_main_bedroom': ['l3_bedroom_hall', 'l3_chamberrockhall'], 'l3_bedroom_hall': ['L3_Main_Hall']}
    cases = [
        (('glas', 'l3_main_bedroom', ['l3_main_bedroom'], portals), 'cheat.flight 1|pos.go glas'),
        (('glas', 'l3_bedroom_hall', ['l3_main_bedroom'], portals),
         'cheat.flight 1|pos.portal l3_bedroom_hall|wait.unit l3_bedroom_hall|pos.go glas'),
        (('glas', 'l3_main_hall', ['l3_main_bedroom', 'l3_bedroom_hall'], portals),        # name case differs
         'cheat.flight 1|pos.portal l3_main_hall|wait.unit l3_main_hall|pos.go glas'),
        (('glas', 'l3_main_hall', ['l3_main_bedroom'], portals),                           # two hops: no portal path
         'level.load l3_main_hall|cheat.flight 1|pos.go glas'),
        (('glas', 'l3_bedroom_hall', ['l3_main_bedroom'], portals, True),                  # "load" forces level.load
         'level.load l3_bedroom_hall|cheat.flight 1|pos.go glas'),
    ]
    ok = 0
    for args, want in cases:
        got = '|'.join(goload_steps(*args))
        ok += got == want
        if got != want: print('goload: %s -> %s, want %s  FAIL' % (args[:3], got, want))
    good = ok == len(cases)
    print('goload: %d / %d path cases (loaded / portal / case / two hops / forced load)  %s'
          % (ok, len(cases), 'ok' if good else 'FAIL'))
    return good


def waitunit(loaded_at, end=40000, step=16):
    """ShortcutTick's wait.unit as a model: loaded_at(t) -> bool; returns ('done', t) or ('stopped', t)"""
    start, ready = 0, None
    for t in range(0, end, step):
        if t - start > 30000: return 'stopped', t
        if not loaded_at(t):
            ready = None
            continue
        if ready is None:
            ready = t
            continue
        if t - ready < 1000: continue
        return 'done', t


def check_waitunit():
    cases = [(lambda t: t >= 2000, 'done', 3000, 3100),               # streamed after 2 s, 1 s in a row
             (lambda t: t >= 2000 and not 2500 <= t < 2600, 'done', 3600, 3700),   # a flicker restarts the second
             (lambda t: False, 'stopped', 30000, 30100),              # never: stopped after 30 s
             (lambda t: t >= 29500, 'stopped', 30000, 30100)]         # too late for the 1 s
    ok = 0
    for f, want, lo, hi in cases:
        what, t = waitunit(f)
        ok += what == want and lo <= t <= hi
    good = ok == len(cases)
    print('waitunit: %d / %d cases (1 s in a row, flicker, 30 s limit)  %s' % (ok, len(cases), 'ok' if good else 'FAIL'))
    return good


# ---------------------------------------------------------------------------------------------------- 0.20 ai forget
class Forget:
    """AiForgetOnce / AiForgetReset / AiSlotLara as a model"""
    def __init__(self):
        self.done, self.cleared, self.counted = set(), [], 0

    def reset(self): self.done = set()

    @staticmethod
    def slot_lara(slot, lara):
        mode = slot.get('mode', -1)
        if mode == 1: return slot.get('inst') == lara['inst'] and slot.get('id') == lara['id']
        if mode == 0: return slot.get('sense_target') == lara['inst']
        return False

    def once(self, enemy, lara):
        key = (enemy['inst'], enemy['id'])
        if key in self.done: return False
        self.done.add(key)
        for off in (0x30, 0xf0):
            if self.slot_lara(enemy['slots'].get(off, {}), lara):
                self.cleared.append((key, off))
                enemy['slots'][off] = {'mode': -1}
        for off in (0x70, 0xb0):
            if self.slot_lara(enemy['slots'].get(off, {}), lara): self.counted += 1
        return True


def check_forget():
    lara = {'inst': 0x1000, 'id': 7}
    def enemy(inst, eid, slots): return {'inst': inst, 'id': eid, 'slots': slots}
    f = Forget()
    a = enemy(0x2000, 1, {0x30: {'mode': 1, 'inst': 0x1000, 'id': 7}, 0xf0: {'mode': 0, 'sense_target': 0x1000},
                          0x70: {'mode': 1, 'inst': 0x1000, 'id': 7}})
    b = enemy(0x3000, 2, {0x30: {'mode': 1, 'inst': 0x1000, 'id': 6},               # stale handle id: not Lara
                          0xf0: {'mode': 2}, 0xb0: {'mode': 0, 'sense_target': 0x5000}})
    c = enemy(0x4000, 3, {0x30: {'mode': 0, 'sense_target': 0x1000}})
    frames = [f.once(e, lara) for e in (a, b, c)] + [f.once(e, lara) for e in (a, b, c)]   # the second frame: nothing
    good = frames == [True, True, True, False, False, False]
    good &= sorted(f.cleared) == sorted([((0x2000, 1), 0x30), ((0x2000, 1), 0xf0), ((0x4000, 3), 0x30)]) and f.counted == 1
    good &= b['slots'][0x30]['mode'] == 1 and b['slots'][0xf0]['mode'] == 2           # untouched
    f.reset()                                                                         # a new setting / off / level change
    a['slots'][0x30] = {'mode': 1, 'inst': 0x1000, 'id': 7}                           # the enemy picked Lara again
    again = f.once(a, lara) and a['slots'][0x30]['mode'] == -1
    respawn = f.once(enemy(0x2000, 9, {0x30: {'mode': 1, 'inst': 0x1000, 'id': 7}}), lara)   # same slot, new handle id
    good &= again and respawn
    print('forget: once per enemy and setting, slot rule (mode 1 / 0 / -1 / 2, stale id), +0x70 / +0xb0 only counted, '
          'reset and a reused instance slot  %s' % ('ok' if good else 'FAIL'))
    return good


# ----------------------------------------------------------------------------------------------------- 0.18 bar confirm
def check_confirm():
    """QbConfirm / QbArmed: a second right press on the same key within 3 s runs, a later one re-arms, another key
    re-arms (the first one is then no longer armed), a third press after a run arms again"""
    arm = {'key': '', 'tick': 0}
    def confirm(key, t):
        if arm['tick'] and t - arm['tick'] <= 3000 and arm['key'] == key:
            arm.update(key='', tick=0)
            return True
        arm.update(key=key, tick=t or 1)
        return False
    cases = [([('a', 1000), ('a', 2500)], [False, True]), ([('a', 1000), ('a', 4100)], [False, False]),
             ([('a', 1000), ('b', 1500), ('a', 2000)], [False, False, False]),
             ([('a', 1000), ('a', 2000), ('a', 2500)], [False, True, False])]
    good = 0
    for presses, want in cases:
        arm.update(key='', tick=0)
        good += 1 if [confirm(k, t) for k, t in presses] == want else 0
    ok = good == len(cases)
    print('confirm: %d / %d press sequences as expected (3 s window, same key)  %s' % (good, len(cases), 'ok' if ok else 'FAIL'))
    return ok


# ------------------------------------------------------------------------------------------------- 0.19 dumb AI presets
AI_PRESETS = {'all': '', 'sharks': 'shark', 'spiders': 'spider,tarantula', 'thralls': 'thrall'}


class AiModel:
    """mode 0 off / 1 all / 2 filter, list, the last setting (RunAiDumb, AiApply, AiSetting, AiPresetOn)"""
    def __init__(self, ini_filter=''):
        self.mode, self.list, self.ini = 0, '', ini_filter
        self.last, self.last_mode, self.last_list = 'all', 1, ''

    def apply(self, mode, lst, setting):
        self.mode, self.list = mode, lst
        if mode and setting:
            self.last, self.last_mode, self.last_list = setting, mode, lst

    def preset_on(self, name):
        if not self.mode: return False
        if name == 'all': return self.mode == 1
        if self.mode != 2: return False
        lst = self.ini if name == 'filter' else AI_PRESETS.get(name)
        return lst is not None and lst == self.list

    def setting(self, name):
        if name == 'all': return 1, ''
        if name == 'filter': return 2, self.ini
        return (2, AI_PRESETS[name]) if name in AI_PRESETS else None

    def run(self, arg):
        words = arg.split()
        a, rest = (words[0] if words else ''), ' '.join(words[1:])
        if a in ('0', 'off') or (not a and self.mode):
            self.apply(0, self.list, None)
            return 'off'
        if not a or a in ('1', 'on'):
            self.apply(self.last_mode, self.last_list, self.last)
            return 'on'
        if a == '2': a = 'filter'
        if a == 'list':
            parts = ','.join(p for p in rest.replace(' ', ',').split(',') if p).lower()
            if not parts: return 'err'
            if '*' in parts: self.apply(1, '', 'all')
            else: self.apply(2, parts, 'list')
            return 'on'
        s = self.setting(a)
        if not s: return 'err'
        if rest == '0':
            if not self.preset_on(a): return 'unchanged'
            self.apply(0, self.list, None)
            return 'off'
        if rest not in ('', '1'): return 'err'
        self.apply(s[0], s[1], a)
        return 'on'

    def ring(self, preset):                  # RadialRun / QbAct bool row: the target state from the shown one
        return self.run('%s %d' % (preset, 0 if self.preset_on(preset) else 1))


def check_presets():
    cases = []
    m = AiModel()
    m.ring('sharks')
    cases.append(('ring sharks', (m.mode, m.list, m.preset_on('sharks'), m.preset_on('all')), (2, 'shark', True, False)))
    m.ring('spiders')
    cases.append(('ring spiders replaces sharks', (m.mode, m.list, m.preset_on('sharks'), m.preset_on('spiders')),
                  (2, 'spider,tarantula', False, True)))
    r = m.run('sharks 0')
    cases.append(('sharks 0 while spiders are on', (r, m.mode, m.list), ('unchanged', 2, 'spider,tarantula')))
    m.ring('spiders')
    cases.append(('ring spiders again = off', (m.mode, m.preset_on('spiders')), (0, False)))
    m.run('')
    cases.append(('"" brings spiders back', (m.mode, m.list), (2, 'spider,tarantula')))
    m.run('list Tiger, panther')
    m.run('0')
    m.run('1')
    cases.append(('own list, off, 1 = the list again', (m.mode, m.list, m.last), (2, 'tiger,panther', 'list')))
    m.run('list *')
    cases.append(('list * = all', (m.mode, m.preset_on('all')), (1, True)))
    m2 = AiModel(ini_filter='shark')
    m2.run('2')
    cases.append(('2 = filter from the INI; equal to the sharks preset', (m2.preset_on('filter'), m2.preset_on('sharks')),
                  (True, True)))
    cases.append(('unknown preset', (m2.run('cats'), m2.mode), ('err', 2)))
    cases.append(('bad state word', (m2.run('sharks 2'), m2.mode), ('err', 2)))
    ok = True
    for name, got, want in cases:
        good = got == want
        ok &= good
        if not good: print('presets: %s -> %s, want %s  FAIL' % (name, got, want))
    print('presets: %d / %d ring / bar / command sequences as expected  %s' % (
        sum(1 for _, g, w in cases if g == w), len(cases), 'ok' if ok else 'FAIL'))
    return ok


# --------------------------------------------------------------------------------------------------- 0.19 burst log rule
def burst_lines(active, end_ms, fps=60):
    """AiSecondTick at fps frames per second; active(t) = removals in the frame at t ms; returns [(t, what)]"""
    lines, sec_start, sec_sum = [], 0, 0
    b = {'on': False, 'start': 0, 'last_active': 0, 'last_line': 0}
    t = 1.0
    while t < end_ms:
        now = int(t)
        sec_sum += active(now)
        if not sec_start: sec_start = now
        if now - sec_start >= 1000:
            sec_start, total, sec_sum = now, sec_sum, 0
            if total:
                if not b['on']: b.update(on=True, start=now - 1000, last_line=now - 1000)
                b['last_active'] = now
                if now - b['last_line'] >= 30000:
                    lines.append((now, 'goes on'))
                    b['last_line'] = now
            elif b['on'] and now - b['last_active'] >= 2000:
                lines.append((b['last_active'], 'ended'))
                b['on'] = False
        t += 1000.0 / fps
    return lines


def check_burst():
    cases = [
        ('per-frame removals for 95 s', lambda t: 1 if t < 95000 else 0, 100000, ['goes on'] * 3 + ['ended']),
        ('3 short bursts 5 s apart', lambda t: 1 if t % 5000 < 400 else 0, 15500, ['ended'] * 3),
        ('pause of 1.5 s inside a burst', lambda t: 1 if t < 4000 or 5500 <= t < 9000 else 0, 15000, ['ended']),
        ('pause of 3.5 s splits it', lambda t: 1 if t < 4000 or 7500 <= t < 9000 else 0, 15000, ['ended', 'ended']),
        ('nothing happens', lambda t: 0, 20000, []),
    ]
    ok = True
    for name, fn, end, want in cases:
        got = [w for _, w in burst_lines(fn, end)]
        good = got == want
        ok &= good
        print('burst: %s -> %d line(s) %s  %s' % (name, len(got), ' / '.join(got) or '-', 'ok' if good else 'FAIL'))
    return ok


# ------------------------------------------------------------------------------------------------- 0.19 brain+8 records
def check_bits():
    """one brain with its record (AiBitsSet in the walk, then AiBitsSweep); want = the wanted bits of this frame"""
    INV, ATK = 0x80, 0x20 | 0x100000
    state = {'flags': 0, 'rec': None, 'alive': True}

    def frame(want):
        if state['alive'] and want:          # AiBitsSet
            missing = want & ~state['flags']
            if missing:
                if state['rec'] is None: state['rec'] = 0
                state['flags'] |= missing
                state['rec'] |= missing
        if state['rec'] is not None:         # AiBitsSweep
            if state['alive']:
                clear = state['rec'] & ~want
                if clear:
                    state['flags'] &= ~clear
                    state['rec'] &= ~clear
            if not state['alive'] or not state['rec']: state['rec'] = None

    cases = []
    state.update(flags=0x40 | INV, rec=None, alive=True)       # the game set 0x80 itself (intro flag)
    frame(INV | ATK)
    cases.append(("on: only the missing bits are TruMenu's", (state['flags'], state['rec']), (0x40 | INV | ATK, ATK)))
    state['flags'] &= ~0x20                                      # the game clears 0x20 (0x6507f6)
    frame(INV | ATK)
    cases.append(('the game cleared 0x20 -> set again', (state['flags'], state['rec']), (0x40 | INV | ATK, ATK)))
    frame(0)
    cases.append(("off: the game's 0x80 stays", (state['flags'], state['rec']), (0x40 | INV, None)))
    state.update(flags=0, rec=None, alive=True)
    frame(ATK)
    state['alive'] = False
    frame(ATK)
    cases.append(('brain gone: record dropped, no write', (state['flags'], state['rec']), (ATK, None)))
    ok = True
    for name, got, want in cases:
        good = got == want
        ok &= good
        if not good: print('bits: %s -> %s, want %s  FAIL' % (name, got, want))
    print("bits: %d / %d record cases as expected (only TruMenu's bits are cleared)  %s" % (
        sum(1 for _, g, w in cases if g == w), len(cases), 'ok' if ok else 'FAIL'))
    return ok


def main():
    rng = random.Random(17)
    results = [check_depth(rng), check_chord(), check_frames(), check_segments(), check_confirm(), check_presets(),
               check_burst(), check_bits(), check_goload(), check_waitunit(), check_forget()]   # 0.20: + three
    print('all ok' if all(results) else 'FAILED')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
