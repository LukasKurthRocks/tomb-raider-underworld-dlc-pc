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
2026-11-07 TruMenu 0.21.1 changes model "labels" (only a drawn placed instance suppresses its runtime copies) and adds
six: killpath (AkPick / the Kill outcome), sticky (StParse / RunStickySet), roomcheck (RkCheck / player.goto / unit.go),
unitgo (the shortcut step expansion), favrecent (page 0, QbRecentAdd, [Quick] Recent), groups (QbBuild / QbGroupSet).
2026-11-07 TruMenu 0.21.2 / TruShadowPower 0.19 add two (docs/Befund-Padkette-StartView-0711.md):
  padchain  the three pad hooks (TruMenu PadHook, TruShadowPower PadHook, TruLink PadHook with its re-entry breaker) in
            all six orders; a queued item that polls the pad again (cheat.flight 0): with the 0.21.1 rule (item always
            inside PadHook) TruLink cuts the chain in the orders where it sits outermost (TruMenu then drops out, the
            bar combo's Start reaches the game); with the 0.21.2 rule (inside PadHook only when the game called it,
            else in Present) no order cuts the chain, the item runs once and the game never sees Start of the combo.
  padblock  TruShadowPower 0.19 GameButtons with TruMenuPadBlock, the plugin inside and outside TruMenu: quick bar
            LB / RB taps, RB held through the bar close, RB pressed in the long menu (neutral pad) and held through
            its close - never counted; plain RB before / after - counted.
2026-11-07 TruMenu 0.21.3 extends chord (X / Y owned by the open bar, passed while closed, one held at the close kept until
released) and adds four (docs/Befund-TruMenu-0213-0711.md):
  xyfav     Y = QbFavPin / FavSet: pin / unpin toggled by item id (two rows of one item, 500 random presses: never twice;
            a hand-edited double goes as a whole), page 0 refreshed at once (into Favoriten, out of Zuletzt and back),
            rows with an argument / headings / groups / planned / special rows refused, Y beats X / right in one frame.
  xyexec    X = QbExecRow: action / choice / info / special rows = the right press, so every confirmation row (ai.kill,
            ai.remove, level.reload, sticky.set, chapters, spawn, checkpoint go) needs X X / X right / right X within 3 s;
            X + right in one frame counts once; game.quit arms itself (10 s); bool rows toggle; value rows nothing;
            groups open / close.
  footer    the bar's second footer line "X: ausfuehren  Y: Favorit   View + Start: zu" (EN), kept under a result.
  sndwidth  DrawSoundList with AlwaysAutoResize: the 0.21 right-corner shift kept the widest width ever, 0.21.3 aligns
            to this frame's widest row (left corners unchanged, a too long row cut at 70 %).
2026-11-07 TruMenu 0.21.4 adds three (docs/Befund-TruMenu-0214-0711.md, docs/Befund-Hall02-Zaehler-Drift-0711.md):
  h2drift   the dispatcher 11270 counter (24540 f3 / f4 / f1) with the thrall int +8 (generator birth = 2, checkpoint
            restore = 0): the live session 15:49 - 15:53 (4 pre-spawned thralls in checkpoint 11258, two deaths) ends
            with population 4 and the wall closed - exactly the measured lines.
  fixhall02 RunFixHall02: refused in another unit, without dispatcher values, with the wall broken, with a living
            object-1004 thrall (alive / Regenerate / RegenerateDeath / no brain but not hidden); allowed when every one is
            in Death / LandDeath / DrownDeath / DeferredInstantDie / kill flag / gone / hidden without a brain; tutorial
            2 only when below 2 and before population 0; then f1 (trigger 11268 enter / leave) breaks the wall in the
            drift case, never before the fix.
  scriptval H2ValueAddr = the interpreter's op14 address ([R+0xc] + 8, 0 when R or [R+0xc] is 0) for 2000 random
            memories; op2f skips a 0 address, so a read through H2ValueAddr never touches what the game would not.
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
2026-11-06 TruMenu 0.20.1 sound list adds two models (section "---- 0.20.1 sound list" of TruMenu.cpp):
 12. soundlist SnBuild / SnClassify / SnState / DrawSoundList: the wave id rule (manager + 8, 0x18 steps, 0x1400 waves),
             the group = the first ancestor node that is a group node (root 0 only when nothing else), the category by
             the ancestors (music = [cats+0] or [cats+0xc], SFX [1], speech [2], else other), the state precedence
             (ending > starting > muted > paused > virtual > playing), the filter (groups, audible only), the three
             orders (group / volume / name = streams first, then the wave id) and the line limit.
 13. mutemusic SmMusicGroups / SmMuteOn / SmMuteOff: the music groups are [cats+0] and [cats+0xc] (never SFX / speech /
             the root, no duplicate); a group is muted once (not again while muted), a group muted by someone else is
             never touched, a level load's new channel group is muted once more, no groups (loading) keeps the
             records, off unmutes only TruMenu's groups and only when the channel group is the same object and still
             muted (a rebuilt group is left alone) - no volume is ever written.

2026-11-07 TruMenu 0.21 adds six models (section "---- 0.21 arachnophobia" of TruMenu.cpp, M20Draw):
 14. spiders   ArKindOf: Match / Exclude parts on the object name (giant = its own kind, generators excluded), a name the
             object list does not know yet is not cached, the INI list normalised as AiNormList.
 15. wobble    ArDrawPictures' quad: centre = spot - bob, |bob| <= amp x size, squash / stretch on the sides, the tilt
             keeps the side lengths, the longer side = size, a still picture is axis-aligned, flip swaps only the UVs,
             phases differ per instance.
 16. drawmask  ArDrawHook: V1 sets +0x23c = -1 only during the game's draw and puts the value back (one the game wrote
             meanwhile stays), a spider the game hides is untouched, V2 writes no mask (0x200 + counter), picture-only /
             off / other instances draw normally.
 17. shake     CsShakeStub = the game's strength x ShakeScale / 100; a refused patch group is tried once until switched.
 18. labels    one label per reward pot (runtime child with the parent's intro dropped when the placed one is in the walk,
             the spawned artifact kept), LfNotDrawn (0x800, 0x20, scene entity off, +0x23c | +0x240 == -1).
 19. airemove  RunAdRemove's selection (others / nearest / all / intro id) and AdCandidate's filter.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trumenu_quick_check.py            all models, exit 1 on a failure
0.21.5 (2026-11-07 Fixes + frozen ring): switches (SwNext / RunSwSet: bool / int / choice steps, X toggle / wrap,
listed key, type, INI exists, unchanged = no write, live / restart / live-if), swfold (one group open at a time,
largest page <= 64 rows), ringparity (every ring entry of the shipped file is a bar row, ring frozen at 172).
0.21.6 (2026-11-07 costumes / flight line / quick command line): cosbar (QbCosRows: 4 rows + the open list from the
cycle list, the current costume marked, every row refused without a level, labels "<slot> <text> (<object>)" only for
dlc_costume_a..p, records only with an object id; page / row limits: own page <= 64 rows for any list up to 60, the
Lara page would overflow, 16 pages), cosdebounce (QbCosAct / QbCosTick: a step only picks, the switch runs once the
pick stood 0.5 s - tapping / holding switches once; X = now; wraps at both ends; the negative model "switch on every
step" is caught), flighthint (FlightHintWanted truth table, the line above the bottom-right windows, never overlapping),
quickcmd (QcPadTick: L3 alone toggles, L3 + R3 / ring hold never, bar / menu / ring close it, A runs once per press,
B closes, D-pad history = the menu bar's walk, 4 answers newest first, one run path), togglerows (the pass / Navmesh
rows are bool rows: right = on, left = off, X flips; NavRowNote's "(Ebene fehlt)" / "(nur mit Flaechen)" rule; every
shipped toggle row is a bool row).
"""
import itertools, math, random, sys

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
OWN = 0xC30F                            # D-pad + LB + RB (0.17) + X / Y (0.21.3)


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
    # 0.21.3: X (0x4000) / Y (0x8000) belong to the open bar; closed they pass; one held at the close stays away
    X, Y, A = 0x4000, 0x8000, 0x1000
    out, pad = run([(0, 100, V | S), (100, 200, 0), (200, 300, X | Y | A), (300, 400, 0)])
    mid = [g for t, g, _ in out if 200 <= t < 300]
    r = pad.open and all(g & (X | Y) == 0 and g & A for g in mid)
    lines.append(('0.21.3 open: X / Y kept from the game, A passes', r)); ok &= r
    out, pad = run([(0, 100, X | Y), (100, 200, 0)])
    r = not pad.open and all(g & (X | Y) == X | Y for t, g, _ in out if t < 100)
    lines.append(('0.21.3 closed: X / Y reach the game unchanged', r)); ok &= r
    out, pad = run([(0, 100, V | S), (100, 200, 0), (200, 600, Y), (300, 400, V | S), (600, 700, 0), (700, 800, Y)])
    held = [g for t, g, _ in out if 400 <= t < 600]
    again = [g for t, g, _ in out if 700 <= t < 800]
    r = not pad.open and all(g & Y == 0 for g in held) and all(g & Y for g in again)
    lines.append(('0.21.3 closed with Y held: kept until released, the next press passes', r)); ok &= r
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


# ------------------------------------------------------------------------------------------------- 0.20.1 sound list
MUSIC, SFX, SPEECH, OTHER = 0, 1, 2, 3
ST_PLAYING, ST_VIRTUAL, ST_PAUSED, ST_MUTED, ST_PENDING, ST_ENDING = range(6)


def sn_wave(sample, mgr):                     # SnBuild: wave id or -1 (stream buffer)
    lo = mgr + 8 if mgr else 0
    hi = mgr + 8 + 0x1400 * 0x18 if mgr else 0
    return (sample - lo) // 0x18 if lo <= sample < hi and (sample - lo) % 0x18 == 0 else -1


def sn_classify(node, parent_of, group_nodes, cats):   # SnClassify: (group, category)
    group, depth = -1, 0
    while node and depth < 24:
        g = group_nodes.index(node) if node in group_nodes else -1
        if g == 0 and group < 0: group = 0
        if g > 0:
            if group < 0: group = g
            if g in (cats[0], cats[3]): return group, MUSIC
            if g == cats[1]: return group, SFX
            if g == cats[2]: return group, SPEECH
        parent = parent_of.get(node, 0)
        if parent == node: break
        node, depth = parent, depth + 1
    return group, OTHER


def sn_state(v):                              # SnState
    if not v['playing'] or v['ending']: return ST_ENDING
    if v['pending']: return ST_PENDING
    if v['muted']: return ST_MUTED
    if v['paused'] or v['grp_paused']: return ST_PAUSED
    return ST_VIRTUAL if v['virt'] else ST_PLAYING


def sn_before(a, b, sort):                    # SnBefore
    if sort == 1 and a['vol'] != b['vol']: return a['vol'] > b['vol']
    if sort == 2:
        if (a['wave'] < 0) != (b['wave'] < 0): return a['wave'] < 0
        if a['wave'] != b['wave']: return a['wave'] < b['wave']
    if a['cat'] != b['cat']: return a['cat'] < b['cat']
    if a['group'] != b['group']: return a['group'] < b['group']
    return a['vol'] > b['vol']


def sn_lines(voices, show, only, sort, lines):   # DrawSoundList: filter, insertion sort, the shown lines
    order = []
    for v in voices:
        if not show[v['cat']]: continue
        if only and sn_state(v) != ST_PLAYING: continue
        k = len(order)
        order.append(v)
        while k > 0 and sn_before(v, order[k - 1], sort):
            order[k] = order[k - 1]
            k -= 1
        order[k] = v
    return order[:lines], len(order)


def check_soundlist():
    mgr = 0x30000000
    good = sn_wave(mgr + 8, mgr) == 0 and sn_wave(mgr + 8 + 0x18 * 1234, mgr) == 1234
    good &= sn_wave(mgr + 8 + 0x18 * 0x1400, mgr) == -1 and sn_wave(mgr + 9, mgr) == -1 and sn_wave(0x1234, 0) == -1
    # groups: 0 root, 1 music (slider), 2 SFX, 3 speech, 4 "music" channel group (under 1), 5 default (under 2), 6 free
    cats = [1, 2, 3, 4, 5]
    gn = [0x100 + 0x84 * i for i in range(7)]                       # group nodes R+0x50
    parent = {gn[1]: gn[0], gn[2]: gn[0], gn[3]: gn[0], gn[4]: gn[1], gn[5]: gn[2], gn[6]: gn[0]}

    def voice_node(group, via_owner):                               # params node -> (owner node) -> group node
        p, o = 0x9000 + group * 0x10 + (8 if via_owner else 0), 0xa000 + group * 0x10
        if via_owner: parent[p], parent[o] = o, gn[group]
        else: parent[p] = gn[group]
        return p
    want = {1: (1, MUSIC), 2: (2, SFX), 3: (3, SPEECH), 4: (4, MUSIC), 5: (5, SFX), 6: (6, OTHER), 0: (0, OTHER)}
    for g, w in want.items():
        for via in (False, True):
            got = sn_classify(voice_node(g, via), parent, gn, cats)
            if got != w:
                good = False
                print('  soundlist: group %d via owner %s -> %s, want %s' % (g, via, got, w))
    good &= sn_classify(0x7777, {}, gn, cats) == (-1, OTHER)        # not under any group
    good &= sn_classify(0x5000, {0x5000: 0x5000}, gn, cats) == (-1, OTHER)   # its own parent ends the walk
    base = dict(playing=True, ending=False, pending=False, muted=False, paused=False, grp_paused=False, virt=False)
    states = [(dict(base), ST_PLAYING), (dict(base, playing=False), ST_ENDING),
              (dict(base, ending=True, muted=True), ST_ENDING), (dict(base, pending=True, muted=True), ST_PENDING),
              (dict(base, muted=True, paused=True), ST_MUTED), (dict(base, grp_paused=True, virt=True), ST_PAUSED),
              (dict(base, virt=True), ST_VIRTUAL)]
    good &= all(sn_state(v) == w for v, w in states)
    rng = random.Random(201)
    voices = []
    for _ in range(60):
        st = rng.choice([{}, {}, {}, {'paused': True}, {'muted': True}, {'virt': True}, {'ending': True}])
        v = dict(base, cat=rng.randrange(4), group=rng.randrange(1, 7), wave=rng.choice([-1, rng.randrange(5000)]),
                 vol=round(rng.random(), 2))
        v.update(st)
        voices.append(v)
    show = [1, 1, 1, 1]
    for sort in (0, 1, 2):
        shown, total = sn_lines(voices, show, False, sort, 16)
        full, _ = sn_lines(voices, show, False, sort, 99)
        good &= total == 60 and len(shown) == 16 and shown == full[:16]
        good &= all(not sn_before(full[k + 1], full[k], sort) for k in range(len(full) - 1))   # sorted
    full, _ = sn_lines(voices, show, False, 2, 99)
    streams = [v['wave'] < 0 for v in full]
    good &= streams == sorted(streams, reverse=True)                 # name order: every stream before every wave
    waves = [v['wave'] for v in full if v['wave'] >= 0]
    good &= waves == sorted(waves)
    full, _ = sn_lines(voices, show, False, 1, 99)
    good &= [v['vol'] for v in full] == sorted((v['vol'] for v in voices), reverse=True)
    only, n_only = sn_lines(voices, [1, 0, 1, 0], True, 0, 99)
    good &= n_only == sum(1 for v in voices if v['cat'] in (0, 2) and sn_state(v) == ST_PLAYING) and n_only > 0
    good &= all(v['cat'] in (0, 2) and sn_state(v) == ST_PLAYING for v in only)
    good &= sn_lines(voices, [0, 0, 0, 0], False, 0, 16) == ([], 0)
    print('soundlist: wave id rule, group / category by the ancestors (direct and via an owner node, root, loop), '
          'state precedence, filters, the three orders, line limit  %s' % ('ok' if good else 'FAIL'))
    return good


class Mute:                                   # SmMusicGroups / SmMuteOn / SmMuteOff over a model of the group table
    def __init__(self):
        self.rec = [{'cg': 0, 'group': 0, 'ours': False}, {'cg': 0, 'group': 0, 'ours': False}]
        self.active, self.calls, self.lines = False, [], []

    @staticmethod
    def groups(cats):
        if cats is None: return []
        out = []
        for w in (cats[0], cats[3]):
            if w <= 0 or w == cats[1] or w == cats[2] or (len(out) == 1 and out[0] == w): continue
            out.append(w)
        return out

    def on(self, game):
        for k, g in enumerate(self.groups(game['cats'])):
            cg = game['cg'].get(g, 0)
            if not cg: continue
            if game['muted'].get(cg):
                if self.rec[k]['cg'] != cg: self.rec[k] = {'cg': cg, 'group': g, 'ours': False}
                continue
            again = self.rec[k]['ours'] and self.rec[k]['cg'] and self.rec[k]['cg'] != cg
            game['muted'][cg] = True
            self.calls.append(('mute', cg))
            self.lines.append('new' if again else 'muted')
            self.rec[k] = {'cg': cg, 'group': g, 'ours': True}
            self.active = True

    def off(self, game):
        for m in self.rec:
            if m['ours']:
                cg = game['cg'].get(m['group'], 0)
                if cg and cg == m['cg'] and game['muted'].get(cg):
                    game['muted'][cg] = False
                    self.calls.append(('unmute', cg))
            m['cg'], m['ours'] = 0, False
        self.active = False


def check_mutemusic():
    good = Mute.groups([1, 2, 3, 4, 5]) == [1, 4] and Mute.groups([1, 2, 3, 1, 5]) == [1]
    good &= Mute.groups([0, 2, 3, 4, 5]) == [4] and Mute.groups([2, 2, 3, 3, 5]) == [] and Mute.groups(None) == []
    game = {'cats': [1, 2, 3, 4, 5], 'cg': {1: 0xa1, 4: 0xa4, 2: 0xa2}, 'muted': {}}
    m = Mute()
    for _ in range(5): m.on(game)                                     # 5 frames: one mute per group
    good &= m.calls == [('mute', 0xa1), ('mute', 0xa4)] and m.lines == ['muted', 'muted']
    good &= not game['muted'].get(0xa2)                               # SFX untouched
    game['cg'] = {1: 0xb1, 4: 0xb4, 2: 0xb2}                          # level load: new channel groups
    m.on(game)
    m.on(game)
    good &= m.calls[2:] == [('mute', 0xb1), ('mute', 0xb4)] and m.lines[2:] == ['new', 'new']
    saved = dict(game['cg'])
    game['cats'], game['cg'] = None, {}                               # loading: no sound info, no groups
    m.on(game)
    good &= len(m.calls) == 4 and m.rec[0]['ours'] and m.rec[1]['ours']   # the records stay
    game['cats'], game['cg'] = [1, 2, 3, 4, 5], saved
    m.off(game)
    good &= m.calls[4:] == [('unmute', 0xb1), ('unmute', 0xb4)] and not m.active
    good &= not game['muted'][0xb1] and not game['muted'][0xb4]
    # a group muted by someone else is never touched; a rebuilt group is not unmuted
    game = {'cats': [1, 2, 3, 4, 5], 'cg': {1: 0xc1, 4: 0xc4}, 'muted': {0xc4: True}}
    m = Mute()
    m.on(game)
    good &= m.calls == [('mute', 0xc1)] and not m.rec[1]['ours']
    game['cg'][1] = 0xd1                                              # rebuilt while on, before the next frame
    m.off(game)
    good &= m.calls == [('mute', 0xc1)] and game['muted'][0xc4] and not game['muted'].get(0xd1)
    print('mutemusic: music groups [cats+0] / [cats+0xc] only, one mute per group, level load re-mute, loading keeps '
          'the records, off restores only its own unchanged groups, foreign mute untouched, no volume written  %s'
          % ('ok' if good else 'FAIL'))
    return good


# ------------------------------------------------------------------------------------------------ 0.21 arachnophobia
def ar_norm(text):                            # AiNormList: lower case, comma list of a-z 0-9 _ *
    parts = [p for p in ''.join(c if c.isalnum() or c in '_*' else ',' for c in text.lower()).split(',') if p]
    return ','.join(parts)


class ArKinds:                                # ArKindOf: 1 spider, 3 giant spider, 2 none; cached once the name is known
    def __init__(self, match='spider,tarantula', exclude='_generator'):
        self.match, self.exclude, self.cache = ar_norm(match), ar_norm(exclude), {}

    def kind(self, oid, names):
        if oid in self.cache: return self.cache[oid]
        name = names.get(oid)
        if name is None: return 2             # the object list does not know it yet: not cached
        low = name.lower()
        hit = any(p and p in low for p in self.match.split(','))
        if hit and self.exclude and any(p and p in low for p in self.exclude.split(',')): hit = False
        k = (3 if 'giant' in low else 1) if hit else 2
        self.cache[oid] = k
        return k


def check_spiders():
    names = {1: 'giant_albino_tarantula', 2: 'small_albino_spider', 3: 'small_brown_spider', 4: 'spider_generator',
             5: 'tarantula_generator', 6: 'thrall_a', 7: 'Panther_Thrall', 8: 'bat_enemy', 9: 'ca_rw_artifact'}
    k = ArKinds()
    got = {oid: k.kind(oid, names) for oid in names}
    good = got == {1: 3, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2}
    late = {}
    good &= k.kind(10, late) == 2 and 10 not in k.cache            # unknown now ...
    late[10] = 'giant_brown_spider'
    good &= k.kind(10, late) == 3                                    # ... a spider once the list knows it
    k2 = ArKinds('Spider, Tarantula', '')                            # INI spelling, no exclude: generators are spiders
    good &= k2.match == 'spider,tarantula' and k2.kind(4, names) == 1
    print('spiders: Match / Exclude on the object name (giant = 3, generators excluded, other enemies none), cached only '
          'once the name is known, the INI list normalised  %s' % ('ok' if good else 'FAIL'))
    return good


def ar_quad(size, aspect, amp, hz, squash, tilt_deg, phase, t, x, y, mirror, u=1.0, v=1.0):
    """ArDrawPictures: the four corners and UVs of one picture"""
    w = 2 * math.pi * hz * t + phase
    bob = math.sin(w) * amp * size
    sq = math.sin(2 * w) * squash
    tilt = math.radians(tilt_deg) * math.sin(0.5 * w + phase)
    iw, ih = (size, size / aspect) if aspect >= 1 else (size * aspect, size)
    iw *= 1 + sq
    ih *= 1 - sq
    cx, cy, cs, sn = x, y - bob, math.cos(tilt), math.sin(tilt)
    hx, hy = (-iw / 2, iw / 2, iw / 2, -iw / 2), (-ih / 2, -ih / 2, ih / 2, ih / 2)
    q = [(cx + hx[k] * cs - hy[k] * sn, cy + hx[k] * sn + hy[k] * cs) for k in range(4)]
    u0, u1 = (u, 0.0) if mirror else (0.0, u)
    return q, [(u0, 0.0), (u1, 0.0), (u1, v), (u0, v)], bob, sq, tilt


def check_wobble(rng):
    good = True
    for _ in range(2000):
        size, aspect = rng.uniform(16, 600), rng.uniform(0.3, 3)
        amp, hz, squash, tilt = rng.uniform(0, 0.5), rng.uniform(0, 10), rng.uniform(0, 0.5), rng.uniform(0, 45)
        x, y, t, phase = rng.uniform(0, 1920), rng.uniform(0, 1080), rng.uniform(0, 600), rng.uniform(0, 6.283)
        q, uv, bob, sq, tl = ar_quad(size, aspect, amp, hz, squash, tilt, phase, t, x, y, rng.random() < 0.5)
        mx, my = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
        good &= abs(mx - x) < 1e-6 and abs(my - (y - bob)) < 1e-6 and abs(bob) <= amp * size + 1e-9
        top = math.dist(q[0], q[1])
        side = math.dist(q[1], q[2])
        iw, ih = (size, size / aspect) if aspect >= 1 else (size * aspect, size)
        good &= abs(top - iw * (1 + sq)) < 1e-6 and abs(side - ih * (1 - sq)) < 1e-6   # rotation keeps the sides
        good &= abs(sq) <= squash + 1e-12 and abs(math.degrees(tl)) <= tilt + 1e-9
        good &= max(iw, ih) <= size + 1e-9                                           # the longer side = size
    q, uv, *_ = ar_quad(100, 2.0, 0, 1, 0, 0, 0, 3, 500, 300, False)                 # still: axis-aligned 100 x 50
    good &= [tuple(round(c, 6) for c in p) for p in q] == [(450, 275), (550, 275), (550, 325), (450, 325)]
    good &= uv == [(0, 0), (1, 0), (1, 1), (0, 1)]
    q2, uv2, *_ = ar_quad(100, 2.0, 0, 1, 0, 0, 0, 3, 500, 300, True)
    good &= q2 == q and uv2 == [(1, 0), (0, 0), (0, 1), (1, 1)]                      # mirrored = UVs swapped only
    ph = {((inst >> 4) * 2654435761 % (1 << 32)) % 6283 for inst in range(0x10000000, 0x10000000 + 64 * 0x40, 0x40)}
    good &= len(ph) >= 60                                                            # phases differ per instance
    print('wobble: centre = spot - bob (|bob| <= amp x size), squash / stretch on the sides, the tilt keeps them, '
          'longest side = size, still picture axis-aligned, flip only swaps the UVs, phases differ  %s'
          % ('ok' if good else 'FAIL'))
    return good


def ar_draw(inst, hook, thread, logic, game_writes=None):
    """ArDrawHook: returns (geometry drawn?, mask after, 0x200 set?, counter delta, picture listed?)"""
    m23c0, count0, listed = inst['m23c'], inst['count'], False
    def game_draw():                          # 0x5bba90: 0x200 + counter first, then the mask exit
        inst['f14'] |= 0x200
        inst['count'] += 1
        drew = (inst['m23c'] | inst['m240']) != 0xffffffff
        if game_writes is not None: inst['m23c'] = game_writes        # the game itself writes during the call
        return drew
    def result(drew): return drew, inst['m23c'], bool(inst['f14'] & 0x200), inst['count'] - count0, listed
    if not (hook['hide'] or hook['pic']) or not inst['spider']:
        return result(game_draw())
    game_draws = (inst['m23c'] | inst['m240']) != 0xffffffff
    if game_draws and hook['pic']: listed = True
    if not game_draws or not hook['hide']:
        return result(game_draw())
    if not logic or thread == logic:                                   # V1
        inst['m23c'] = 0xffffffff
        drew = game_draw()
        if inst['m23c'] == 0xffffffff: inst['m23c'] = m23c0
        return result(drew)
    inst['f14'] |= 0x200                                               # V2
    inst['count'] += 1
    return result(False)


def check_drawmask():
    def spider(m23c=0, m240=0): return {'m23c': m23c, 'm240': m240, 'f14': 0, 'count': 0, 'spider': True}
    on, pic_only, off = {'hide': True, 'pic': True}, {'hide': False, 'pic': True}, {'hide': False, 'pic': False}
    good = ar_draw(spider(0x5), on, 7, 7) == (False, 0x5, True, 1, True)                 # V1: no geometry, mask back
    good &= ar_draw(spider(0x5), on, 7, 7, game_writes=0x9) == (False, 0x9, True, 1, True)   # the game's write stays
    good &= ar_draw(spider(0xffffffff, 0xffffffff), on, 7, 7) == (False, 0xffffffff, True, 1, False)   # game hides it
    good &= ar_draw(spider(0x5), on, 9, 7) == (False, 0x5, True, 1, True)                # V2: never written
    good &= ar_draw(spider(0x5), on, 9, 0) == (False, 0x5, True, 1, True)                # game thread not known: V1
    good &= ar_draw(spider(0x5), pic_only, 7, 7) == (True, 0x5, True, 1, True)           # picture only: model stays
    good &= ar_draw(spider(0x5), off, 7, 7) == (True, 0x5, True, 1, False)
    other = {'m23c': 0, 'm240': 0, 'f14': 0, 'count': 0, 'spider': False}
    good &= ar_draw(other, on, 7, 7) == (True, 0, True, 1, False)                        # not a spider
    print('drawmask: V1 sets -1 only during the call and puts the game\'s value back (a value the game wrote meanwhile '
          'stays), a spider the game hides is left alone, V2 writes no mask (0x200 + counter as the game), picture-only / '
          'off / other instances draw normally  %s' % ('ok' if good else 'FAIL'))
    return good


def check_shake():
    good = True
    for game in (0.0, 0.37, 1.0, 2.5):
        for pct in range(0, 101):
            scale = pct / 100.0                                           # g_csScaleF
            stub = game * scale                                           # the game's 0x5eb460, then fmul
            good &= abs(stub - game * pct / 100.0) < 1e-12
        good &= game * (100 / 100.0) == game and game * 0.0 == 0.0
    group = {'on': False, 'refused': False, 'tries': 0}
    def apply(want, ok=True):                                             # M21PatchGroup's retry rule
        if want == group['on']: return
        if want:
            if group['refused']: return
            group['tries'] += 1
            if not ok:
                group['refused'] = True
                return
            group['on'] = True
        else:
            group['on'] = False
    for _ in range(60): apply(True, ok=False)                             # 60 frames of a foreign patch: one try
    good &= group['tries'] == 1 and not group['on']
    group['refused'] = False                                              # the item was switched again
    apply(True)
    apply(True)
    apply(False)
    good &= group['tries'] == 2 and not group['on']
    print('shake: strength x ShakeScale / 100 (100 = the game\'s own, no patch; 0 = none), a refused patch is tried once '
          'until switched again  %s' % ('ok' if good else 'FAIL'))
    return good


def lf_not_drawn(i):                          # LfNotDrawn
    if i['f14'] & 0x800: return 1
    if i['f14'] & 0x20: return 2
    off = bool(i['f18'] & 0x400000) or bool(i['objflag'] & 0x40000000)
    if off and not (i['f1c'] & 0x200): return 3
    if (i['m23c'] | i['m240']) == 0xffffffff: return 4
    return 0


def lf_labels(insts):
    """M20Draw 0.21: hidden instances get no label, a runtime child whose placed instance of the same kind is in the walk
    is dropped; 0.21.1 (live 2026-11-07, pot without a label): only a DRAWN placed instance registers its intro - of a
    hidden template and its drawn runtime copy the copy gets the label"""
    placed, marks, hidden = [], [], 0
    for i in insts:
        is_placed = not i['intro'] or i['id'] == i['intro_id']
        if lf_not_drawn(i):
            hidden += 1
            continue
        if i['intro'] and is_placed: placed.append((i['intro'], i['kind']))
        marks.append((i['name'], 0 if is_placed else i['intro'], i['kind']))
    kept = [m for m in marks if not (m[1] and (m[1], m[2]) in placed)]
    return [m[0] for m in kept], hidden, len(marks) - len(kept)


def check_labels():
    def inst(name, kind, intro, iid, intro_id, **f):
        d = {'name': name, 'kind': kind, 'intro': intro, 'id': iid, 'intro_id': intro_id, 'f14': 0, 'f18': 0, 'f1c': 0,
             'objflag': 0, 'm23c': 0, 'm240': 0}
        d.update(f)
        return d
    pot = inst('pot 10810', 'pot', 0xA000, 10810, 10810)
    copy = inst('pot 0x40000017', 'pot', 0xA000, 0x40000017, 10810)          # BirthObject: the parent's intro
    spawned = inst('tp_rw_artifact_spawned', 'artifact', 0xA000, 0x40000018, 10810)
    other = inst('pot 9854', 'pot', 0xB000, 9854, 9854)
    good = lf_labels([pot, copy, spawned, other]) == (['pot 10810', 'tp_rw_artifact_spawned', 'pot 9854'], 0, 1)
    good &= lf_labels([copy, pot]) == (['pot 10810'], 0, 1)                   # order in the list does not matter
    good &= lf_labels([copy]) == (['pot 0x40000017'], 0, 0)                   # no placed one in the walk: the child stays
    broken = dict(pot, f14=0x800)
    # 0.21.1: the placed template hidden, the runtime copy drawn (live 07.11. 11:02: "0 drawn of 6 ... 2 hidden and 2
    # runtime copies without label") -> the copy gets the label; the 0.21 rule dropped both
    good &= lf_labels([broken, copy]) == (['pot 0x40000017'], 1, 0)
    good &= lf_labels([copy, broken]) == (['pot 0x40000017'], 1, 0)           # order in the walk does not matter
    good &= lf_labels([broken, dict(copy, f14=0x800)]) == ([], 2, 0)          # both hidden: none
    picked = inst('ma_rw_artifact 9856', 'artifact', 0xC000, 9856, 9856, f14=0x800)
    good &= lf_labels([picked]) == ([], 1, 0)                                 # picked up (hidden): no label in mid air
    cases = [({'f14': 0x800}, 1), ({'f14': 0x20}, 2), ({'f18': 0x400000}, 3), ({'objflag': 0x40000000}, 3),
             ({'f18': 0x400000, 'f1c': 0x200}, 0), ({'m23c': 0xffffffff, 'm240': 0xffffffff}, 4),
             ({'m23c': 0xffffffff}, 4), ({'m23c': 0xffff0000, 'm240': 0x0000ffff}, 4),   # the OR is tested (0x5bbb23)
             ({'m23c': 0x1, 'm240': 0x2}, 0), ({}, 0)]
    for fields, want in cases:
        good &= lf_not_drawn(inst('x', 'artifact', 0, 1, 1, **fields)) == want
    print('labels: one label per reward pot (the runtime copy with the parent\'s intro dropped, the spawned artifact '
          'kept, a lone copy kept; 0.21.1: a hidden template\'s drawn copy keeps its label), hidden / collected / being '
          'removed / scene-entity off / masks -1 -> no label  %s' % ('ok' if good else 'FAIL'))
    return good


def ad_select(cands, mode, want=None):        # RunAdRemove: which candidates are flagged, which one is kept
    if not cands: return [], None
    nearest = min(range(len(cands)), key=lambda i: cands[i]['d2'])
    take = []
    for i, c in enumerate(cands):
        if mode == 'nearest': t = i == nearest
        elif mode == 'others': t = i != nearest
        elif mode == 'all': t = True
        else: t = c['intro'] == want
        if t: take.append(c['intro'])
    kept = cands[nearest]['intro'] if mode == 'others' else None
    return take, kept


def check_airemove():
    def c(intro, d): return {'intro': intro, 'd2': d * d}
    cands = [c(101, 900), c(102, 300), c(103, 1200)]
    good = ad_select(cands, 'others') == ([101, 103], 102) and ad_select(cands, 'nearest') == ([102], None)
    good &= ad_select(cands, 'all') == ([101, 102, 103], None) and ad_select(cands, 'id', 103) == ([103], None)
    good &= ad_select(cands, 'id', 999) == ([], None) and ad_select([], 'others') == ([], None)
    good &= ad_select([c(7, 50)], 'others') == ([], 7)                        # the only one is kept
    def candidate(e):                                                          # AdCandidate
        return bool(e['brain'] and e['family'] == 14 and not e['lara'] and not (e['f14'] & (0x20 | 0x20000 | 0x400))
                    and 'doppel' not in e['name'])
    base = {'brain': 1, 'family': 14, 'lara': False, 'f14': 0, 'name': 'thrall_a'}
    good &= candidate(base) and not candidate(dict(base, family=1)) and not candidate(dict(base, brain=0))
    good &= not candidate(dict(base, f14=0x20)) and not candidate(dict(base, f14=0x400))
    good &= not candidate(dict(base, lara=True)) and not candidate(dict(base, name='doppelganger_casual'))
    print('airemove: others = all but the nearest to Lara, nearest, all, one intro id; only AI enemies of family 14, not '
          'Lara, not flagged (0x20 / 0x20000 / 0x400), not the doppelganger  %s' % ('ok' if good else 'FAIL'))
    return good


# ---- 0.21.1 (2026-11-07) ----
PC_CASE = [0, 0, 0, 2, 0, 2, 0, 2, 0, 2, 0, 1, 2, 0, 0, 2, 0]   # byte table 0x6376c4, bound 0x10 (0 = A, 1 = B, 2 = C)
TU_CASE = PC_CASE + [2] + [0] * 10                                  # TruShadowCombat [Damage] Translate: 28 entries, 0x1b
DEATH = ('Death', 'LandDeath', 'DrownDeath', 'DeferredInstantDie')


def ak_case(t, table, bound):                 # AkCaseOf
    if t < 0 or t > bound: return 2
    return table[t]


def ak_should_regen(t, sub, flag, regen):     # ShouldRegenerate 0x67f040 on the Tune+0x64 list {type, sub, flag bit 0}
    for et, es, ef in regen:
        if (et == -1 or et == t) and (es == 0 or es == sub) and (ef & 1) == flag: return True
    return False


def ak_pick(e, table=PC_CASE, bound=0x10):    # AkPick: (type, None) or (None, why)
    if e['f8'] & 0x800: return None, 'no damage'
    if e['fc'] & 2: return None, 'no death check'
    if e['state'] in DEATH: return None, 'already dying'
    for t in (6, 4, 2, 1, 0):
        if ak_case(t, table, bound) != 0: continue
        if (e['mask'][t >> 5] >> (t & 31)) & 1: continue
        if ak_should_regen(t, 0, 0, e['regen']): continue
        return t, None
    return None, 'none'


def ak_outcome(e, t):                         # Kill(type t): damage case A, LP -= LP, death check 0x620380
    lp = e['lp'] - e['lp']                    # amount = LP (absorbed types were skipped by the pick)
    if lp > 0 or e['fc'] & 2: return e['state']
    return 'RegenerateDeath' if ak_should_regen(t, 0, 0, e['regen']) else 'Death'


def check_killpath():
    thrall_regen = [(0, 1, 0)] + [(t, 0, 0) for t in range(18, 23)] + [(23, 2, 0), (24, 2, 0)]   # tutorial viking
    yeti_regen = [(0, 0, 0)] + [(t, 0, 0) for t in range(18, 25)]
    base = {'f8': 0, 'fc': 0, 'state': 'Getup', 'mask': [0], 'regen': thrall_regen, 'lp': 500.0}
    good = ak_pick(base) == (6, None) and ak_outcome(base, 6) == 'Death'                 # the game's own type first
    good &= ak_pick(dict(base, regen=yeti_regen)) == (6, None)
    good &= ak_pick(base, TU_CASE, 0x1b) == (6, None)                                    # TruShadowCombat table: same
    good &= ak_pick(dict(base, mask=[1 << 6])) == (4, None)                              # immune to 6: Explosion
    good &= ak_pick(dict(base, mask=[(1 << 6) | (1 << 4)])) == (2, None)
    good &= ak_pick(dict(base, regen=[(-1, 0, 0)])) == (None, 'none')                    # regenerates on anything
    good &= ak_pick(dict(base, regen=[(6, 0, 0), (4, 0, 0)])) == (2, None)               # 6 / 4 would only lay it down
    good &= ak_pick(dict(base, regen=[(-1, 0, 1)])) == (6, None)                         # flag 1 entries need reset 1
    good &= ak_pick(dict(base, f8=0x800))[0] is None and ak_pick(dict(base, fc=2))[0] is None
    good &= all(ak_pick(dict(base, state=s))[0] is None for s in DEATH)
    good &= ak_pick(dict(base, state='RegenerateDeath', lp=-10.0)) == (6, None)          # a lying thrall dies for good
    good &= ak_outcome(dict(base, state='RegenerateDeath', lp=-10.0), 6) == 'Death'
    # every type the pick returns ends in Death (no RegenerateDeath) for any list it was checked against
    lists = [thrall_regen, yeti_regen, [(6, 0, 0)], [(-1, 2, 0)], []]
    for lst in lists:
        for m in (0, 1 << 6, (1 << 6) | (1 << 4) | (1 << 2)):
            e = dict(base, regen=lst, mask=[m])
            t, why = ak_pick(e)
            if t is not None: good &= ak_outcome(e, t) == 'Death' and ak_case(t, PC_CASE, 0x10) == 0
    def guard(used, cap, lock):              # RunAkKill: no kill in the physics step or with < 60 free bodies
        return not (lock & 1) and cap - used >= 60
    good &= guard(0, 405, 0) and guard(345, 405, 0) and not guard(346, 405, 0) and not guard(10, 405, 1)
    good &= not guard(405, 405, 0)                                                       # the ChunkDoll crash pool
    print('killpath: ai.kill takes type 6 (the game\'s own Kill) unless absorbed / on the regeneration list, then 4 / 2 / '
          '1 / 0; never with brain+8 0x800, brain+0xc bit 1 or in a death state; the TruShadowCombat table changes '
          'nothing for these types; every pick ends in Death (counts), a lying RegenerateDeath thrall too; refused in the '
          'physics step or with fewer than 60 of 405 bodies free  %s' % ('ok' if good else 'FAIL'))
    return good


def st_parse(text):                           # StParse: owner = intro id (kind 0) or <kind>:<id>, key u16
    parts = text.split()
    if len(parts) < 2: return None
    ow, k = parts[0], parts[1]
    kind = 0
    if ':' in ow:
        kind, ow = int(ow.split(':')[0]), ow.split(':')[1]
    try:
        owner, key = int(ow, 0), int(k, 0)
    except ValueError:
        return None
    if not 0 <= kind <= 2 or key > 0xffff: return None
    return kind, owner, key, ' '.join(parts[2:])


def st_set(stores, text, want=None):           # RunStickySet: (store, index, value) or the refusal
    p = st_parse(text)
    if not p: return 'usage'
    kind, owner, key, rest = p
    if not rest: return 'usage'
    hits = [(t, i) for t, ids in enumerate(stores) for i, e in enumerate(ids) if e == (owner, key, kind)]
    hits = [h for h in hits if want is None or h[0] == want]
    if not hits: return 'no entry'            # never created (the game's Find would append - not used)
    if len(hits) > 1: return 'ambiguous'
    t, i = hits[0]
    if t == 2:
        try:
            v = float(rest)
        except ValueError:
            return 'bad value'
    else:
        try:
            v = int(rest, 0)
        except ValueError:
            return 'bad value'
        if t == 1 and v not in (0, 1): return 'bad value'
    return (t, i, v)


def check_sticky():
    ints = [(4086, 195, 2), (11270, 8914, 0), (11270, 17287, 0), (11270, 18509, 0)]
    bools = [(4086, 10814, 0), (11270, 10029, 0)]
    floats = [(663, 77, 0)]
    stores = [ints, bools, floats]
    good = st_set(stores, '11270 17287 0') == (0, 2, 0) and st_set(stores, '11270 18509 2') == (0, 3, 2)
    good &= st_set(stores, '11270 10029 1') == (1, 1, 1) and st_set(stores, '11270 10029 2') == 'bad value'
    good &= st_set(stores, '663 77 0.8') == (2, 0, 0.8) and st_set(stores, '663 77 x') == 'bad value'
    good &= st_set(stores, '11270 99 1') == 'no entry' and st_set(stores, '11270 17287') == 'usage'
    good &= st_set(stores, '2:0x012500BA 195 4') == 'no entry'                           # kind 2 is another owner space
    good &= st_set([ints + [(0x012500BA, 195, 2)], bools, floats], '2:0x012500BA 195 4') == (0, 4, 4)
    dup = [ints + [(5, 5, 0)], bools + [(5, 5, 0)], floats]
    good &= st_set(dup, '5 5 1') == 'ambiguous' and st_set(dup, '5 5 1', want=1) == (1, len(bools), 1)
    good &= st_parse('11270') is None and st_parse('3:1 1') is None and st_parse('1 70000') is None
    print('sticky: sticky.set finds (kind, owner, key) in the three stores without creating one, refuses an absent / '
          'ambiguous entry and a bad value (bool 0 / 1), kind 2 owners by <kind>:<id>; the hall02 repair 11270 17287 0 / '
          '18509 2 hits the int store  %s' % ('ok' if good else 'FAIL'))
    return good


def rk_check(inst, units, lara_unit, lara_pos, far=25000.0):   # RkCheck: 0 ok, 1 not loaded, 2 parked, 3 not drawn, 4 far
    u = units.get(inst['unit'])
    if not u or u['state'] != 2: return 1
    if u['flags'] & 1: return 2
    if inst['notdrawn']: return 3
    d = sum((a - b) ** 2 for a, b in zip(inst['pos'], lara_pos)) ** 0.5
    if d > far and inst['unit'] != lara_unit: return 4
    return 0


def goto(inst, units, lara_unit, lara_pos, force=False):   # RunGoto: jump or refuse
    r = rk_check(inst, units, lara_unit, lara_pos)
    return 'jump' if (r == 0 or force) else 'refused %d' % r


def unit_go(target, lara_unit, loaded, portal_owners):    # RkUnitGoSteps
    if target == lara_unit: return ''
    if target in loaded and portal_owners.get(target):
        return 'cheat.flight 1;pos.portal %s' % target
    return 'level.load %s' % target


def check_roomcheck():
    units = {91: {'state': 2, 'flags': 0}, 108: {'state': 2, 'flags': 0}, 7: {'state': 2, 'flags': 1}, 5: {'state': 1, 'flags': 0}}
    lara = (0.0, 0.0, 0.0)
    near = {'unit': 91, 'notdrawn': 0, 'pos': (1000.0, 0.0, 0.0)}
    good = goto(near, units, 91, lara) == 'jump'
    spider = {'unit': 7, 'notdrawn': 0, 'pos': (43091.0, 32000.0, 0.0)}                  # live 07.11. 10:54
    good &= goto(spider, units, 91, lara) == 'refused 2' and goto(spider, units, 91, lara, True) == 'jump'
    good &= goto(dict(near, notdrawn=1), units, 91, lara) == 'refused 3'
    good &= goto(dict(near, unit=5), units, 91, lara) == 'refused 1' and goto(dict(near, unit=99), units, 91, lara) == 'refused 1'
    good &= goto(dict(near, unit=108, pos=(30000.0, 0.0, 0.0)), units, 91, lara) == 'refused 4'
    good &= goto(dict(near, unit=91, pos=(30000.0, 0.0, 0.0)), units, 91, lara) == 'jump'   # far but in Lara's unit
    good &= goto(dict(near, unit=108, pos=(9000.0, 0.0, 0.0)), units, 91, lara) == 'jump'   # a loaded neighbour
    # unit.go: DLC 2 chain level2_start -> hall01 -> hall02 (docs/Befund-Unit-Streaming-0611.md)
    loaded = {'dlc_level2_start', 'dlc_yggdrasil_hall01'}
    owners = {'dlc_yggdrasil_hall01': 'dlc_level2_start', 'dlc_yggdrasil_hall02': 'dlc_yggdrasil_hall01'}
    good &= unit_go('dlc_yggdrasil_hall02', 'dlc_level2_start', loaded, owners) == 'level.load dlc_yggdrasil_hall02'
    loaded2 = {'dlc_yggdrasil_hall01', 'dlc_yggdrasil_hall02', 'dlc_level2_start'}
    good &= unit_go('dlc_yggdrasil_hall02', 'dlc_yggdrasil_hall01', loaded2, owners) == \
        'cheat.flight 1;pos.portal dlc_yggdrasil_hall02'
    good &= unit_go('dlc_yggdrasil_hall02', 'dlc_yggdrasil_hall02', loaded2, owners) == ''
    print('roomcheck: player.goto refuses a parked template (resident unit), an unloaded unit, a not drawn target and one '
          'far outside Lara\'s unit, "force" jumps; unit.go = nothing / portal of a loaded unit / level.load (hall02 from '
          'the DLC 2 start: level.load - two portals away)  %s' % ('ok' if good else 'FAIL'))
    return good


def sc_expand(steps, index, expansion, cap=12):   # ShortcutTick: unit.go replaced in place by its expansion
    consumed = steps[index]
    assert consumed.startswith('unit.go ')
    parts = [p for p in expansion.split(';') if p]
    if len(steps) + len(parts) - 1 > cap: return None
    return steps[:index] + parts + steps[index + 1:]


def check_unitgo():
    s = ['unit.go dlc_yggdrasil_hall02', 'cheat.god 1']
    good = sc_expand(s, 0, 'level.load dlc_yggdrasil_hall02') == ['level.load dlc_yggdrasil_hall02', 'cheat.god 1']
    good &= sc_expand(s, 0, 'cheat.flight 1;pos.portal dlc_yggdrasil_hall02') == \
        ['cheat.flight 1', 'pos.portal dlc_yggdrasil_hall02', 'cheat.god 1']
    good &= sc_expand(s, 0, '') == ['cheat.god 1']                                      # Lara is in it: the step is gone
    good &= sc_expand(['a'] * 11 + ['unit.go x'], 11, 'b;c') is None                    # 13 steps: stopped
    good &= sc_expand(['a'] * 10 + ['unit.go x'], 10, 'b;c') == ['a'] * 10 + ['b', 'c']
    print('unitgo: the shortcut step unit.go is replaced in place by its steps (level.load / flight + portal / nothing), '
          'the rest keeps its order, more than 12 steps stop the run  %s' % ('ok' if good else 'FAIL'))
    return good


def qb_recent_add(lst, row, cap):             # QbRecentAdd: (id, arg) rows, newest first, no doubles
    if cap <= 0 or row[2] in ('label', 'planned', 'group', 'info') or row[0] == '-': return lst
    rest = [r for r in lst if r != (row[0], row[1])]
    return [(row[0], row[1])] + rest[:cap - 1]


def qb_page0(favs, recent):                   # QbFavRows: favourites, then recent rows that are no favourite
    return list(favs), [r for r in recent if not (not r[1] and r[0] in favs)]


def check_favrecent():
    lst = []
    for row in [('dbg.show', 'death', 'bool'), ('cheat.flight', '', 'bool'), ('dbg.show', 'death', 'bool'),
                ('ai.status', '', 'info'), ('-', '', 'label'), ('ai.kill', 'others', 'action')]:
        lst = qb_recent_add(lst, row, 3)
    good = lst == [('ai.kill', 'others'), ('dbg.show', 'death'), ('cheat.flight', '')]
    lst = qb_recent_add(lst, ('time.scale', '', 'value'), 3)
    good &= lst == [('time.scale', ''), ('ai.kill', 'others'), ('dbg.show', 'death')]
    good &= qb_recent_add(lst, ('x', '', 'bool'), 0) == lst
    favs, rec = qb_page0(['cheat.flight', 'dbg.show'], [('cheat.flight', ''), ('dbg.show', 'death'), ('ai.kill', 'others')])
    good &= rec == [('dbg.show', 'death'), ('ai.kill', 'others')]                       # the favourite not twice
    text = ';'.join('%s%s%s' % (i, ' ' if a else '', a) for i, a in lst)                  # [Quick] Recent round trip
    back = [(e.split(' ', 1)[0], e.split(' ', 1)[1] if ' ' in e else '') for e in text.split(';') if e]
    good &= back == lst and text == 'time.scale;ai.kill others;dbg.show death'
    print('favrecent: page 0 = favourites, then the last RecentMax rows that ran (newest first, a row again moves to the '
          'top, no info / heading / planned / group rows, no favourite twice), [Quick] Recent round trip  %s'
          % ('ok' if good else 'FAIL'))
    return good


def qb_build(rows, closed):                   # QbBuild: a closed group hides its rows up to the next heading / group
    out, hide = [], False
    for kind, key in rows:
        if kind in ('label', 'group'): hide = False
        elif hide: continue
        out.append(key)
        if kind == 'group': hide = key in closed
    return out


def qb_group_set(text, key, closed):          # QbGroupSet: rewrite the comma list
    keys = [k for k in text.split(',') if k and k != key]
    if closed: keys.append(key)
    return ','.join(keys)


def check_groups():
    rows = [('row', 'flat'), ('group', 'ki_dumm'), ('row', 'all'), ('row', 'sharks'), ('group', 'ki_spawn'), ('row', 'spawn'),
            ('group', 'ki_weg'), ('row', 'kill'), ('label', 'other'), ('row', 'x')]
    good = qb_build(rows, set()) == [k for _, k in rows]
    good &= qb_build(rows, {'ki_dumm'}) == ['flat', 'ki_dumm', 'ki_spawn', 'spawn', 'ki_weg', 'kill', 'other', 'x']
    good &= qb_build(rows, {'ki_dumm', 'ki_spawn', 'ki_weg'}) == ['flat', 'ki_dumm', 'ki_spawn', 'ki_weg', 'other', 'x']
    good &= qb_build(rows, {'ki_weg'})[-2:] == ['other', 'x']                            # a heading ends the group
    t = qb_group_set('', 'ki_spawn', True)
    t = qb_group_set(t, 'ki_dumm', True)
    good &= t == 'ki_spawn,ki_dumm' and qb_group_set(t, 'ki_spawn', False) == 'ki_dumm'
    good &= qb_group_set(t, 'ki_dumm', True) == 'ki_spawn,ki_dumm'                      # closing twice: once
    # the view -> row map: every shown view acts on its own row (no index shift)
    shown = qb_build(rows, {'ki_dumm'})
    good &= all(rows[[k for _, k in rows].index(v)][1] == v for v in shown)
    print('groups: a closed group hides its rows up to the next heading / group, the views map to their own rows, '
          '[Quick] Closed is rewritten as a comma list (no doubles)  %s' % ('ok' if good else 'FAIL'))
    return good


# ---- 0.21.2 / TruShadowPower 0.19 (2026-11-07, docs/Befund-Padkette-StartView-0711.md) ----
P_START, P_VIEW, P_L3, P_R3, P_LB, P_RB = 0x0010, 0x0020, 0x0040, 0x0080, 0x0100, 0x0200
QB_OWN = 0xC30F                                   # 0.21.3: + X / Y (the padblock model stays the same for LB / RB)


class PadChain:
    """The three hooks on 0x00a02b8c as in their sources: TruMenu PadHook (t_padDepth guard, bar combo masked, queued
    item), TruShadowPower 0.19 PadHook (g_inPadHook guard -> XInputGetState, no re-wrap), TruLink PadHook (TLS guard: a
    same-thread re-entry switches g_next to XInputGetState for good). order = outer -> inner."""

    def __init__(self, order, rule):
        self.order, self.rule = list(order), rule
        self.orig = {p: (order[i + 1] if i + 1 < len(order) else 'x') for i, p in enumerate(order)}
        self.depth = self.sp_in = self.link_tls = 0
        self.link_cut, self.latched = False, False
        self.pending = self.deferred = self.runs = self.menu_calls = 0
        self.pad = 0

    def call(self, who, caller):
        return self.pad if who == 'x' else getattr(self, 'h_' + who)(caller)

    def h_link(self, caller):
        if self.link_tls:                         # "pad hook re-entered ... calling XInputGetState directly from now on"
            self.link_cut = True
            self.orig['link'] = 'x'
            return self.pad
        self.link_tls = 1
        r = self.call(self.orig['link'], 'link')
        self.link_tls = 0
        return r

    def h_sp(self, caller):
        if self.sp_in: return self.pad
        self.sp_in = 1
        r = self.call(self.orig['sp'], 'sp')
        self.sp_in = 0
        return r

    def h_menu(self, caller):
        if self.depth: return self.pad
        self.depth += 1
        r = self.call(self.orig['menu'], 'menu')
        self.depth -= 1
        self.menu_calls += 1
        combo = P_START | P_VIEW                  # QbPad: the combo poll and the latch keep both from the game
        if r & combo == combo: self.latched = True
        if self.latched:
            if not r & combo: self.latched = False
            r &= ~combo
        if self.pending == 1:
            if self.rule == '0.21.1' or caller == 'game': self.run_item()
            else: self.deferred = 1               # DeferPending
        return r

    def run_item(self):                           # RunPending: cheat.flight 0 -> message 12 -> one pad poll of the game
        self.pending = 2
        self.runs += 1
        self.game_poll()
        self.pending = 0

    def game_poll(self):
        return self.call(self.order[0], 'game')

    def present(self):                            # Render: (deferred || padIdle) && pending
        if self.deferred and self.pending == 1: self.run_item()
        self.deferred = 0


def padchain_run(order, rule):
    c = PadChain(order, rule)
    c.pending = 1                                 # the bar row "Fliegen" queued cheat.flight 0
    for _ in range(3):
        c.game_poll()
        c.present()
    calls = c.menu_calls
    c.pad = P_START | P_VIEW                      # View + Start: the bar closes / opens
    seen = c.game_poll()
    c.present()
    c.pad = 0
    c.game_poll()
    ok = c.runs == 1 and not c.link_cut and c.menu_calls > calls and not seen & P_START
    return ok, c


def check_padchain():
    orders = list(itertools.permutations(('menu', 'sp', 'link')))
    bad_old = {o for o in orders if not padchain_run(o, '0.21.1')[0]}
    bad_new = {o for o in orders if not padchain_run(o, '0.21.2')[0]}
    expect_old = {('link', 'sp', 'menu'), ('link', 'menu', 'sp')}   # TruLink outermost (14:53 session: link, sp, menu)
    good = bad_old == expect_old and not bad_new
    live = padchain_run(('link', 'sp', 'menu'), '0.21.1')[1]
    good &= live.link_cut and live.runs == 1                       # the live case: cut once, Start then reaches the game
    print('padchain: 0.21.1 cuts the chain in %d of 6 orders (%s), 0.21.2 in %d; the item runs once, Start of the '
          'combo never reaches the game with 0.21.2  %s'
          % (len(bad_old), ', '.join('/'.join(o) for o in sorted(bad_old)), len(bad_new), 'ok' if good else 'FAIL'))
    return good


class MenuPad:
    """TruMenu's pad side reduced to what TruMenuPadBlock reports: long menu (L3 + R3, [Pad] BlockInput -> neutral pad,
    swallow until L3 / R3 are up), quick bar (View + Start; open: D-pad / LB / RB owned, one held at the close stays
    owned until released)."""

    def __init__(self):
        self.menu = self.bar = self.swallow = False
        self.owned = self.prev = 0

    def process(self, raw):                       # OnPad + QbPad: returns what the game gets
        down = raw & ~self.prev
        self.prev = raw
        if raw & (P_L3 | P_R3) == (P_L3 | P_R3) and down & (P_L3 | P_R3):
            self.menu, self.swallow = not self.menu, True
        if self.swallow and not raw & (P_L3 | P_R3): self.swallow = False
        if not self.menu and raw & (P_START | P_VIEW) == (P_START | P_VIEW) and down & (P_START | P_VIEW):
            self.bar = not self.bar
        if self.bar and not self.menu: self.owned |= raw & QB_OWN
        self.owned &= raw
        if self.menu or self.swallow: return 0
        return raw & ~self.owned & ~(P_START | P_VIEW if raw & (P_START | P_VIEW) == (P_START | P_VIEW) else 0)

    def block(self):                              # TruMenuPadBlock (low word)
        out = 0xFFFF if (self.menu or self.swallow) else 0
        if self.bar: out |= QB_OWN
        return out | self.owned


def game_buttons(withheld, seen, block, held, buttons=P_LB | P_RB):   # TruShadowPower 0.19 GameButtons (same packet)
    seen, block, held = seen & buttons, block & buttons, held & buttons
    game = seen & ~block
    withheld = (withheld | (held & ~game)) & held
    return game & ~withheld, withheld


def padblock_run(inside, use_block):
    plain, quiet = True, False
    steps = [(P_RB, plain)] * 3 + [(0, quiet)]                                       # A: plain RB
    steps += [(P_START | P_VIEW, quiet), (0, quiet), (P_RB, quiet), (P_RB, quiet), (0, quiet), (P_LB, quiet),
              (0, quiet)]                                                             # B: bar open, LB / RB taps
    steps += [(P_RB, quiet), (P_RB, quiet), (P_RB | P_START | P_VIEW, quiet)] + [(P_RB, quiet)] * 3 + [(0, quiet)]
    steps += [(P_RB, plain)] * 2 + [(0, quiet)]                                       # C: RB through the close; D
    steps += [(P_L3 | P_R3, quiet), (0, quiet), (P_RB, quiet), (P_RB, quiet), (P_RB | P_L3 | P_R3, quiet)]
    steps += [(P_RB, quiet)] * 3 + [(0, quiet)] + [(P_RB, plain)] * 2 + [(0, quiet)]  # E: long menu; F
    m, withheld, ok = MenuPad(), 0, True
    for raw, expect in steps:
        if inside:                                # TruShadowPower inside TruMenu: raw pad, TruMenu's state of the last poll
            block = m.block() if use_block else 0
            seen = raw
            m.process(raw)
        else:                                     # outside: the masked pad, TruMenu's state of this poll
            seen = m.process(raw)
            block = m.block() if use_block else 0
        eff, withheld = game_buttons(withheld, seen, block, raw)
        ok &= bool(eff & P_RB or eff & P_LB) == expect
    return ok


def check_padblock():
    good = padblock_run(True, True) and padblock_run(False, True)
    good &= padblock_run(False, False) and not padblock_run(True, False)   # without the export: only outside (= 0.17)
    print('padblock: TruShadowPower 0.19 with TruMenuPadBlock inside and outside TruMenu - bar LB / RB, RB through the '
          'bar / menu close never counted, plain RB counted; without the export only the outside order works  %s'
          % ('ok' if good else 'FAIL'))
    return good


# ---- 0.21.3 X / Y in the quick bar, the sound list width (2026-11-07, docs/Befund-TruMenu-0213-0711.md) ----
B_LEFT, B_RIGHT, B_X, B_Y = 0x0004, 0x0008, 0x4000, 0x8000


class QRow:                                       # QbRow reduced to what QbActRow / QbExecRow / QbFavPin read
    def __init__(self, id, arg='', kind='action', confirm=False, grey=False):
        self.id, self.arg, self.kind, self.confirm, self.grey = id, arg, kind, confirm, grey


class QBar:
    """QuickTick after the row choice (one of Y / X / left-right per frame, Y first) -> QbFavPin / QbExecRow / QbActRow,
    QbConfirm (3 s, one key), game.quit arming itself in its item (10 s), FavSet on [Favorites] Ids (toggled by item id,
    case-insensitive; the rewrite keeps only usable ids, every copy of the id goes on a removal)"""

    def __init__(self, favs=(), usable=None):
        self.favs, self.usable = list(favs), usable
        self.arm_key, self.arm_t, self.quit_t, self.quit = '', 0, 0, False
        self.on, self.closed, self.values = {}, set(), {}
        self.runs, self.footer, self.marks = [], '', []

    def confirm(self, key, t):                    # QbConfirm
        if self.arm_t and t - self.arm_t <= 3000 and self.arm_key == key:
            self.arm_key, self.arm_t = '', 0
            return True
        self.arm_key, self.arm_t = key, t or 1
        self.footer = 'rechts / X nochmal (3 s) = ausfuehren'
        return False

    def run(self, row, arg, t):                   # QbRun -> InvokeCore
        if row.id == 'game.quit':                 # RunQuit: arms itself, a second run within 10 s quits
            if self.quit_t and t - self.quit_t <= 10000: self.quit = True
            else: self.quit_t = t or 1
        self.runs.append((row.id, arg))

    def act(self, page, row, d, t):               # QbActRow
        if row.kind == 'label': return
        if row.kind == 'group':
            close = d < 0
            if (row.arg in self.closed) != close:
                if close: self.closed.add(row.arg)
                else: self.closed.discard(row.arg)
            return
        if row.kind == 'planned': self.footer = 'geplant'; return
        if row.kind == 'choice' and d < 0: self.footer = 'next choice'; return
        if row.grey: self.footer = 'why'; return
        if row.kind == 'info':
            self.footer = 'rechts = anzeigen' if d < 0 else 'value shown'
            return
        key = '%d/%s %s' % (page, row.id, row.arg)
        if row.kind == 'choice':
            if row.confirm and not self.confirm(key + ' kind', t): return
            self.run(row, 'kind', t)
            return
        if row.kind == 'bool':
            want, on = d > 0, self.on.get(row.id, False)
            if on == want: return
            self.on[row.id] = want
            self.run(row, '1' if want else '0', t)
            return
        if row.kind == 'value':
            self.values[row.id] = self.values.get(row.id, 1) + d
            return
        if d < 0: self.footer = 'rechts = starten'; return
        if row.confirm and not self.confirm(key, t): return
        self.run(row, row.arg, t)

    def special(self, kind, d, t):                # QbSpecialAct (two kinds: checkpoint go, TO TEST)
        if kind == 'cp':
            if d < 0: self.marks.append('marker'); return
            if self.confirm('dbg.cpgo 123', t): self.runs.append(('dbg.cpgo', '123'))
        elif kind == 'todo':
            self.marks.append('ok' if d > 0 else 'fail')

    def exec(self, page, row, t):                 # QbExecRow
        k = row.kind
        if k == 'label': return
        if k == 'group': return self.act(page, row, 1 if row.arg in self.closed else -1, t)
        if k == 'bool': return self.act(page, row, -1 if not row.grey and self.on.get(row.id, False) else 1, t)
        if k == 'value':
            self.footer = 'Wert mit links / rechts (X: nichts)'
            return
        return self.act(page, row, 1, t)

    def fav_pin(self, row):                       # QbFavPin -> FavSet
        if row is None or row.kind in ('label', 'group', 'planned') or row.id == '-':
            self.footer = 'Y: keine Item-Zeile'
            return 'refused'
        if row.arg:
            self.footer = 'Favorit nur ohne Argument'
            return 'arg'
        ok = (lambda f: self.usable is None or f.lower() in {u.lower() for u in self.usable})   # FindItem: _stricmp
        if not ok(row.id): return 'err'
        had = any(f.lower() == row.id.lower() for f in self.favs if ok(f))
        keep = [f for f in self.favs if ok(f) and not (had and f.lower() == row.id.lower())]
        self.favs = keep if had else keep + [row.id]
        return 'del' if had else 'add'

    def frame(self, page, row, edges, t, special=None):   # QuickTick: Y, else X, else left / right
        if edges & B_Y: return self.fav_pin(row)
        if edges & B_X:
            if row is not None: return self.exec(page, row, t)
            if special: return self.special(special, 1, t)
            return None
        if edges & (B_LEFT | B_RIGHT):
            d = -1 if edges & B_LEFT else 1
            if row is not None: return self.act(page, row, d, t)
            if special: return self.special(special, d, t)
        return None


def check_xyfav():
    usable = {'cheat.flight', 'player.health', 'player.unstuck', 'dbg.show', 'ai.kill', 'weapon.give', 'time.scale'}
    ok, lines = True, []
    b = QBar(['player.health'], usable)
    recent = [('cheat.flight', ''), ('dbg.show', 'death'), ('player.unstuck', '')]
    flight = QRow('cheat.flight', kind='bool')
    r = b.frame(2, flight, B_Y, 1000) == 'add' and b.favs == ['player.health', 'cheat.flight']
    favs, rec = qb_page0(b.favs, recent)
    r &= favs == ['player.health', 'cheat.flight'] and rec == [('dbg.show', 'death'), ('player.unstuck', '')]
    lines.append(('Y on a bool row: pinned, page 0 at once (out of Zuletzt, into Favoriten)', r)); ok &= r
    r = b.frame(0, flight, B_Y, 1200) == 'del' and b.favs == ['player.health']
    r &= qb_page0(b.favs, recent)[1] == recent
    lines.append(('Y again (also from page 0): unpinned, back in Zuletzt', r)); ok &= r
    unstuck_a, unstuck_b = QRow('player.unstuck'), QRow('Player.Unstuck')   # the same item on two pages (Notfall, Tests)
    seq = [b.frame(1, unstuck_a, B_Y, 0), b.frame(7, unstuck_b, B_Y, 0), b.frame(1, unstuck_a, B_Y, 0)]
    r = seq == ['add', 'del', 'add'] and sum(1 for f in b.favs if f.lower() == 'player.unstuck') == 1
    lines.append(('the same item from two rows: toggled by id, never twice in [Favorites] Ids', r)); ok &= r
    rng = random.Random(213)
    rows = [flight, unstuck_a, unstuck_b, QRow('time.scale', kind='value'), QRow('weapon.give', kind='choice')]
    worst = 0
    for _ in range(500):
        b.frame(rng.randrange(13), rng.choice(rows), B_Y, 0)
        worst = max([worst] + [sum(1 for f in b.favs if f.lower() == x.id.lower()) for x in rows])
    r = worst <= 1
    lines.append(('500 random Y presses on 5 rows: no id ever twice (max %d)' % worst, r)); ok &= r
    d = QBar(['player.health', 'player.health', 'gone.item'], usable)   # a hand-edited list with a double / unknown id
    r = d.frame(1, QRow('player.health'), B_Y, 0) == 'del' and d.favs == []
    r &= d.frame(1, QRow('player.health'), B_Y, 0) == 'add' and d.favs == ['player.health']
    lines.append(('hand-edited double: Y removes every copy, the next Y adds one (unknown ids dropped as FavSet)', r)); ok &= r
    e = QBar(['player.health'], usable)
    refused = [e.frame(4, QRow('dbg.show', 'death', 'bool'), B_Y, 0), e.frame(5, QRow('ai.kill', 'others', confirm=True), B_Y, 0),
               e.frame(5, QRow('-', 'ki_weg', 'group'), B_Y, 0), e.frame(3, QRow('-', '', 'label'), B_Y, 0),
               e.frame(11, QRow('-', 'x|y', 'planned'), B_Y, 0), e.frame(8, None, B_Y, 0, special='cp')]
    r = refused == ['arg', 'arg', 'refused', 'refused', 'refused', 'refused'] and e.favs == ['player.health'] and not e.runs
    lines.append(('rows with an argument / heading / group / planned / special rows: refused, nothing changed', r)); ok &= r
    f = QBar([], usable)
    r = f.frame(1, QRow('weapon.give', kind='choice'), B_Y | B_X | B_RIGHT, 0) == 'add' and not f.runs
    lines.append(('Y with X / right in the same frame: only the pin', r)); ok &= r
    r = ','.join(QBar(['player.health'], usable).favs + ['cheat.flight']) == 'player.health,cheat.flight'
    lines.append(('[Favorites] Ids written as today (comma list of item ids)', r)); ok &= r
    for text, good in lines: print('xyfav: %-90s %s' % (text, 'ok' if good else 'FAIL'))
    return ok


def check_xyexec():
    ok, lines = True, []
    act = QRow('player.health')
    b = QBar()
    b.frame(1, act, B_X, 1000)
    r = b.runs == [('player.health', '')]
    lines.append(('action row: X runs it once (= right)', r)); ok &= r
    for rid, arg in (('ai.kill', 'others'), ('ai.kill', 'all'), ('ai.remove', 'others'), ('level.reload', ''),
                     ('sticky.set', '11270 17287 0'), ('level.load', 'l1_seatop')):
        row = QRow(rid, arg, confirm=True)
        cases = [([(B_X, 1000), (B_X, 2500)], 1), ([(B_X, 1000), (B_RIGHT, 2000)], 1), ([(B_RIGHT, 1000), (B_X, 2000)], 1),
                 ([(B_X, 1000), (B_X, 4100)], 0), ([(B_X, 1000), (B_X | B_RIGHT, 1500)], 1),
                 ([(B_X | B_RIGHT, 1000)], 0), ([(B_X, 1000), (B_LEFT, 1500)], 0)]
        good = 0
        for presses, runs in cases:
            c = QBar()
            for edges, t in presses: c.frame(5, row, edges, t)
            good += 1 if len(c.runs) == runs else 0
        other = QBar()
        other.frame(5, row, B_X, 1000)
        other.frame(5, QRow('ai.kill', 'nearest', confirm=True), B_X, 1500)
        other.frame(5, row, B_X, 2000)
        r = good == len(cases) and not other.runs
        lines.append(('confirm row %s %s: X arms, X / right within 3 s runs, late / other row / X+right once: no' % (rid, arg),
                      r)); ok &= r
    q = QBar()
    for t in (1000, 2000): q.frame(1, QRow('game.quit'), B_X, t)
    late = QBar()
    for t in (1000, 12000): late.frame(1, QRow('game.quit'), B_X, t)
    r = q.quit and not late.quit and late.quit_t == 12000
    lines.append(('game.quit: X arms (its own 10 s), a second X within 10 s quits, later re-arms', r)); ok &= r
    flight = QRow('cheat.flight', kind='bool')
    c = QBar()
    for t in (0, 100, 200): c.frame(2, flight, B_X, t)
    r = c.runs == [('cheat.flight', '1'), ('cheat.flight', '0'), ('cheat.flight', '1')] and c.on['cheat.flight']
    g = QBar()
    g.frame(2, QRow('dbg.flat', kind='bool', grey=True), B_X, 0)
    r &= not g.runs and g.footer == 'why'
    lines.append(('bool row: X toggles off -> on -> off -> on; greyed: says why, runs nothing', r)); ok &= r
    v = QBar()
    v.frame(3, QRow('dbg.alpha', kind='value'), B_X, 0)
    r = not v.runs and not v.values and v.footer.startswith('Wert')
    lines.append(('value row: X does nothing (footer hint), left / right unchanged', r)); ok &= r
    grp = QRow('-', 'ki_dumm', 'group')
    h = QBar()
    h.frame(5, grp, B_X, 0)
    shut = 'ki_dumm' in h.closed
    h.frame(5, grp, B_X, 100)
    r = shut and 'ki_dumm' not in h.closed and not h.runs
    lines.append(('group row: X closes an open group, opens a closed one', r)); ok &= r
    k = QBar()
    k.frame(5, QRow('ai.spawn', kind='choice', confirm=True), B_X, 0)
    k.frame(5, QRow('ai.spawn', kind='choice', confirm=True), B_X, 900)
    k.frame(1, QRow('weapon.give', kind='choice'), B_X, 2000)
    k.frame(5, QRow('ai.status', kind='info'), B_X, 2100)
    k.frame(3, QRow('-', '', 'label'), B_X, 2200)
    k.frame(11, QRow('-', 'a|b', 'planned'), B_X, 2300)
    r = k.runs == [('ai.spawn', 'kind'), ('weapon.give', 'kind')] and k.footer == 'geplant'
    lines.append(('choice rows run with the current choice (spawn: X twice), info shows, heading / planned nothing', r))
    ok &= r
    s = QBar()
    s.frame(8, None, B_X, 0, special='cp')
    s.frame(8, None, B_X, 500, special='cp')
    s.frame(7, None, B_X, 600, special='todo')
    r = s.runs == [('dbg.cpgo', '123')] and s.marks == ['ok']
    lines.append(('special rows: X = right (checkpoint go X twice, TO TEST = ok)', r)); ok &= r
    for text, good in lines: print('xyexec: %-104s %s' % (text, 'ok' if good else 'FAIL'))
    return ok


def qb_footer(de, combo='View + Start', result=None):   # DrawQuick: line 1 hint (or a result for 5 s), line 2 always
    hint = ('hoch / runter: Zeile   links / rechts: aus / an   LB / RB: Seite' if de
            else 'up / down: row   left / right: off / on   LB / RB: page')
    close = '%s   %s: %s' % ('X: ausfuehren  Y: Favorit' if de else 'X: run  Y: favourite', combo, 'zu' if de else 'close')
    return (result or hint), close


def check_footer():
    de, en = qb_footer(True), qb_footer(False)
    r = de[1] == 'X: ausfuehren  Y: Favorit   View + Start: zu' and en[1] == 'X: run  Y: favourite   View + Start: close'
    r &= 'X: ausfuehren  Y: Favorit' in de[1] and qb_footer(True, result='Fliegen: an')[1] == de[1]
    r &= all(len(x[1]) < 112 and len(x[1]) <= len(x[0]) for x in (de, en))   # buffer; never wider than the hint line
    r &= de[0].startswith('hoch / runter') and en[0].startswith('up / down')
    print('footer: second line "X: ausfuehren  Y: Favorit   View + Start: zu" (EN "X: run  Y: favourite ..."), kept while '
          'a result replaces line 1, not wider than the hint line (%d / %d chars)  %s'
          % (len(de[1]), len(de[0]), 'ok' if r else 'FAIL'))
    return r


def sn_frames(frames, right, rule, cap=1344.0):
    """DrawSoundList + ImGui AlwaysAutoResize, one window: the window's content width of a frame = the furthest right end
    of its rows; the next frame's window (and its content region, 'avail') is that width, capped at 70 % of the screen.
    0.21: a right-corner row is shifted by avail - w (ends at the window edge); 0.21.3: by edge - w, edge = this frame's
    widest row, at most avail. Returns [(avail, row right ends)] per frame and the final window width."""
    width, out = 0.0, []
    for rows in frames:
        avail = width
        if not right: ends = list(rows)
        elif rule == '0.21':
            ends = [avail if avail > w else w for w in rows]
        else:
            edge = max(rows)
            if avail > 0 and edge > avail: edge = avail
            ends = [edge if edge > w else w for w in rows]
        out.append((avail, ends))
        width = min(max(ends), cap)
    return out, width


H2_DEATH4 = ('Death', 'LandDeath', 'DrownDeath', 'DeferredInstantDie')   # kAkDeathNames: their Enter fires vt 31


class H2Dispatcher:                           # script 24540: sticky ints / bool of 11270, f1 / f3 / f4
    def __init__(self, population=0, deathcount=0, tutorial=0, broken=0):
        self.population, self.deathcount, self.tutorial, self.broken = population, deathcount, tutorial, broken
        self.spawning = True

    def f1(self):                             # check: trigger 11268 enter / leave, a counted death
        if 2 <= self.tutorial and not self.broken and self.population == 0:
            self.broken = 1                   # state 1: f7 "clear", the wall breaks
        return self.broken

    def f3(self):                             # generator OnSpawn (22809 f0 after +8 = 2)
        self.population += 1

    def message(self, value):                 # f0: channel(+24).f3(msg) && msg.value == 2 -> f4
        if value != 2: return False
        self.deathcount += 1
        self.population -= 1
        self.f1()
        if 3 <= self.deathcount:
            self.spawning = False             # generator f4: no more spawns
            self.tutorial = 2
            self.f1()
        return True


def check_h2drift():
    """the live session 07.11. 15:49 - 15:53: births +8 = 2, checkpoint restores +8 = 0 (save block, no 22809 f0)"""
    d = H2Dispatcher()
    alive = []
    for _ in range(4):                        # 15:49:33 - 37: pre-spawned in hall01
        d.f3(); alive.append(2)
    cp = (d.population, d.deathcount, d.tutorial, d.broken, len(alive))   # 15:49:39 checkpoint 11258
    for _ in range(3):                        # 15:49:39 - 41: births 5 .. 7
        d.f3(); alive.append(2)
    good = cp == (4, 0, 0, 0, 4) and d.population == 7
    counted = []
    for new_deaths, old_deaths in ((2, 3), (3, 4)):   # rounds 2 and 3 after a restore each
        d = H2Dispatcher(*cp[:4])
        alive = [0] * cp[4]                   # restored: +8 = 0
        for _ in range(3):
            d.f3(); alive.append(2)
        n = 0
        for v in [2] * new_deaths + [0] * old_deaths:
            n += d.message(v)
        counted.append((n, d.population, d.broken))
    good &= counted[0] == (2, 5, 0)           # round 2: only the two new ones counted (15:51:23 / 26)
    good &= counted[1] == (3, 4, 0)           # round 3: three counted, deathcount 3 -> spawning off, population 4
    d = H2Dispatcher(4, 3, 2, 0)
    good &= d.f1() == 0                       # walking through 11268 does not help
    print('h2drift: birth +8 = 2, restore +8 = 0, the dispatcher counts only 2 - the live rounds give 2 / 3 counted '
          'deaths and population 4 with the wall closed (as measured 15:53:10)  %s' % ('ok' if good else 'FAIL'))
    return good


def h2_alive(t):                              # H2Alive
    if not t.get('own', 1): return False
    if t.get('flags', 0) & 0x20: return False
    if t.get('brain', True):
        return t.get('state', 'Idle') not in H2_DEATH4
    return not (t.get('flags', 0) & 0x800)


def h2_fix(unit, st, thralls):                # RunFixHall02: ('refused', why) or ('ok', [(key, value) written])
    if unit.lower() != 'dlc_yggdrasil_hall02': return ('refused', 'unit')
    if any(k not in st for k in ('population', 'tutorial', 'broken')): return ('refused', 'values')
    if st['broken']: return ('refused', 'broken')
    if any(h2_alive(t) for t in thralls if t.get('obj', 1004) == 1004): return ('refused', 'alive')
    writes = []
    if st['tutorial'] < 2:
        writes.append((18509, 2)); st['tutorial'] = 2
    if st['population'] != 0:
        writes.append((17287, 0)); st['population'] = 0
    return ('ok', writes)


def check_fixhall02():
    base = {'population': 4, 'deathcount': 3, 'tutorial': 2, 'broken': 0}
    dead = [{'state': s} for s in H2_DEATH4] + [{'flags': 0x20}, {'own': 0}, {'brain': False, 'flags': 0x800}]
    good = h2_fix('dlc_yggdrasil_hall01', dict(base), dead) == ('refused', 'unit')
    good &= h2_fix('DLC_YGGDRASIL_HALL02', dict(base), dead) == ('ok', [(17287, 0)])     # case-insensitive unit
    good &= h2_fix('dlc_yggdrasil_hall02', {'population': 4}, dead) == ('refused', 'values')
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, broken=1), dead) == ('refused', 'broken')
    for living in ({'state': 'Idle'}, {'state': 'Regenerate'}, {'state': 'RegenerateDeath'}, {'brain': False}):
        good &= h2_fix('dlc_yggdrasil_hall02', dict(base), dead + [living]) == ('refused', 'alive')
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base), dead + [{'obj': 931, 'state': 'Idle'}]) == ('ok', [(17287, 0)])
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, tutorial=0), dead) == ('ok', [(18509, 2), (17287, 0)])
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, tutorial=1), []) == ('ok', [(18509, 2), (17287, 0)])
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, tutorial=5), []) == ('ok', [(17287, 0)])          # kept
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, population=0), []) == ('ok', [])
    good &= h2_fix('dlc_yggdrasil_hall02', dict(base, population=-1), []) == ('ok', [(17287, 0)])
    st = dict(base)
    d = H2Dispatcher(st['population'], st['deathcount'], st['tutorial'], st['broken'])
    good &= d.f1() == 0                       # before the fix: trigger 11268 does nothing
    r = h2_fix('dlc_yggdrasil_hall02', st, dead)
    d.population, d.tutorial = st['population'], st['tutorial']
    good &= r[0] == 'ok' and d.f1() == 1      # after it: the next enter / leave breaks the wall
    print('fixhall02: refused in another unit / without values / broken / with a living tutorial thrall (Idle, '
          'Regenerate, RegenerateDeath, no brain), dead = the four count states, kill flag, gone, hidden; tutorial 2 '
          'only below 2 and first; the next 11268 check breaks the wall  %s' % ('ok' if good else 'FAIL'))
    return good


def h2_value_addr(mem, inst):                 # H2ValueAddr: [[inst+0x60]+0xc]+8, 0 = none
    ref = mem.get(inst + 0x60, 0)
    if not ref: return 0
    data = mem.get(ref + 0xc, 0)
    return data + 8 if data else 0


def vm_op14(mem, r, off):                     # interpreter op14 (0x57d04b): 0 when R or [R+0xc] is 0
    if not r or not mem.get(r + 0xc, 0): return 0
    return mem[r + 0xc] + off


def check_scriptval(rng):
    good = True
    for _ in range(2000):
        mem, inst = {}, rng.randrange(0x1000, 0x8000) * 16
        ref = rng.choice((0, rng.randrange(0x10000, 0x20000) * 4))
        mem[inst + 0x60] = ref
        if ref: mem[ref + 0xc] = rng.choice((0, rng.randrange(0x30000, 0x40000) * 4))
        good &= h2_value_addr(mem, inst) == vm_op14(mem, mem[inst + 0x60], 8)
    print('scriptval: H2ValueAddr = the interpreter\'s op14 address of "R.+8" (22809 f0) for 2000 random memories, 0 '
          'when the script or its member data is missing (op2f then stores nothing)  %s' % ('ok' if good else 'FAIL'))
    return good


def check_sndwidth():
    seq = [[300.0, 200.0], [500.0, 100.0], [250.0, 120.0], [250.0, 120.0], [250.0, 120.0]]
    old_r, w_old_r = sn_frames(seq, True, '0.21')
    new_r, w_new_r = sn_frames(seq, True, '0.21.3')
    _, w_old_l = sn_frames(seq, False, '0.21')
    _, w_new_l = sn_frames(seq, False, '0.21.3')
    good = w_old_r == 500.0 and w_new_r == 250.0                     # the bug (right corners) and the fix
    good &= w_old_l == 250.0 and w_new_l == 250.0                    # left corners: unchanged, they always followed
    good &= new_r[-1][1] == [250.0, 250.0]                           # right alignment kept: every row ends at the edge
    grow, _ = sn_frames([[200.0], [400.0, 100.0], [400.0, 100.0]], True, '0.21.3')
    good &= grow[2][1] == [400.0, 400.0]                             # growing: aligned again one frame later
    cap, w_cap = sn_frames([[2000.0, 300.0]] * 3, True, '0.21.3')
    good &= w_cap == 1344.0 and cap[-1][1] == [2000.0, 1344.0]       # too long: cut, the others at the visible edge
    print('sndwidth: right corner 0.21 keeps the widest width ever (%.0f), 0.21.3 follows this frame (%.0f); left corners '
          '%.0f / %.0f; rows stay right-aligned, a growing list re-aligns one frame later, a row over 70 %% is cut  %s'
          % (w_old_r, w_new_r, w_old_l, w_new_l, 'ok' if good else 'FAIL'))
    return good


def sw_value_ok(typ, lo, hi, choices, v):     # SwValueOk
    if typ == 'bool': return v in ('0', '1')
    if typ == 'choice': return v.lower() in [c.lower() for c in choices]
    return v.lstrip('-').isdigit() and len(v) <= 9 and lo <= int(v) <= hi


def sw_next(typ, lo, hi, step, choices, cur, d):   # SwNext: d -1 / +1 stop at the end, d 2 = X (toggle / wrap)
    if typ == 'bool':
        on = int(cur) != 0
        want = (not on) if d == 2 else d > 0
        return None if want == on else str(int(want))
    if typ == 'int':
        x = min(max(int(cur), lo), hi)
        nxt = x + (-step if d < 0 else step)
        if d == 2 and nxt > hi: nxt = lo
        nxt = min(max(nxt, lo), hi)
        return None if nxt == int(cur) else str(nxt)
    low = [c.lower() for c in choices]
    i = low.index(cur.lower()) if cur.lower() in low else (len(choices) if d < 0 else -1)
    nxt = i + (-1 if d < 0 else 1)
    if d == 2 and nxt >= len(choices): nxt = 0
    return None if nxt < 0 or nxt >= len(choices) or nxt == i else choices[nxt]


def sw_set(ini, listed, row, v, live_if_on=True):   # RunSwSet: ('refused', why) / ('same',) / ('written', live)
    key, typ, lo, hi, choices, when = row
    if key not in listed: return ('refused', 'not listed')
    if not sw_value_ok(typ, lo, hi, choices, v): return ('refused', 'value')
    if ini is None: return ('refused', 'no ini')
    if ini.get(key) == v: return ('same',)
    ini[key] = v
    return ('written', when == 'live' or (when == 'live-if' and live_if_on))


def check_switches():
    good = True
    b = ('k', 'bool', 0, 1, (), 'live')
    good &= [sw_next('bool', 0, 1, 1, (), '0', d) for d in (-1, 1, 2)] == [None, '1', '1']
    good &= [sw_next('bool', 0, 1, 1, (), '1', d) for d in (-1, 1, 2)] == ['0', None, '0']
    good &= [sw_next('int', 0, 3, 1, (), '3', d) for d in (-1, 1, 2)] == ['2', None, '0']
    good &= [sw_next('int', 0, 20000, 500, (), '4000', d) for d in (-1, 1)] == ['3500', '4500']
    good &= sw_next('int', 0, 3, 1, (), '0', -1) is None and sw_next('int', 1, 100, 1, (), '100', 1) is None
    good &= sw_next('int', 1, 100, 1, (), '500', -1) == '99'            # out of range in the INI: back into the range
    good &= sw_next('int', 1, 100, 1, (), '500', 1) == '100'
    lang = ('en', 'fr', 'de', 'it', 'es', 'off')
    good &= [sw_next('choice', 0, 0, 1, lang, 'es', d) for d in (-1, 1, 2)] == ['it', 'off', 'off']
    good &= sw_next('choice', 0, 0, 1, lang, 'off', 2) == 'en' and sw_next('choice', 0, 0, 1, lang, 'off', 1) is None
    good &= sw_next('choice', 0, 0, 1, lang, 'xx', 1) == 'en' and sw_next('choice', 0, 0, 1, lang, 'xx', -1) == 'off'
    ini = {'k': '0'}
    good &= sw_set(ini, {'k'}, b, '1') == ('written', True) and ini['k'] == '1'
    good &= sw_set(ini, {'k'}, b, '1') == ('same',)
    good &= sw_set(ini, {'k'}, b, '2') == ('refused', 'value') and ini['k'] == '1'
    good &= sw_set(ini, set(), b, '0') == ('refused', 'not listed')
    good &= sw_set(None, {'k'}, b, '0') == ('refused', 'no ini')
    r = ('e', 'bool', 0, 1, (), 'restart')
    good &= sw_set({'e': '1'}, {'e'}, r, '0') == ('written', False)
    m = ('l', 'choice', 0, 0, lang, 'live-if')
    good &= sw_set({'l': 'es'}, {'l'}, m, 'de', False) == ('written', False)
    good &= sw_set({'l': 'es'}, {'l'}, m, 'de', True) == ('written', True)
    good &= sw_set({}, {'n'}, ('n', 'bool', 0, 1, (), 'live'), '1') == ('written', True)   # key missing: written
    print('switches: SwNext (bool left / right / X toggle, int steps / ends / wrap / out-of-range INI, choice prev / next / '
          'wrap / unknown), RunSwSet (listed key, type / range, INI exists, unchanged = no write, live / restart / '
          'live-if)  %s' % ('ok' if good else 'FAIL'))
    return good


def sw_fold(groups, g, d):                     # QbSwAct on a group row: one group open at a time
    open_now = groups[g]
    want = (not open_now) if d == 2 else d > 0
    if want == open_now: return groups
    return [False] * len(groups) if not want else [i == g for i in range(len(groups))]


def sw_rows(counts, groups):                   # QbSwRows: group row + the open group's rows
    return sum(1 + (c if o else 0) for c, o in zip(counts, groups))


def check_swfold():
    good = True
    counts = [14, 25, 19, 5, 7, 5, 8, 4, 28]   # the shipped file's groups
    g = [True] + [False] * 8
    good &= sw_rows(counts, g) == 9 + 14
    g = sw_fold(g, 8, 1)
    good &= g == [False] * 8 + [True] and sw_rows(counts, g) == 9 + 28
    good &= sw_fold(g, 8, 1) == g and sw_fold(g, 3, -1) == g
    g = sw_fold(g, 8, 2)
    good &= g == [False] * 9
    worst = max(sw_rows(counts, [i == k for i in range(9)]) for k in range(9))
    good &= worst <= 64                       # kQbViewMax
    allopen = sw_rows(counts, [True] * 9)
    print('swfold: one group open at a time (right / X opens and closes the others, left / X closes, no change = no '
          'action); largest page %d rows <= 64 (all open would be %d > 64)  %s' % (worst, allopen, 'ok' if good else 'FAIL'))
    return good


def check_ringparity():
    """the shipped files: every ring entry is a bar row (the checker's ring_parity on TruMenu.cpp), ring = 172"""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import trumenu_ini_check as c
    src = open(c.CPP, encoding='utf-8').read()
    miss = c.ring_parity(src, c.RADIAL)
    n = len(c.ring_entries(c.RADIAL))
    rows = c.qb_rows(src)
    good = not miss and n == c.RING_FROZEN
    # the rule itself: a bool row covers 0 / 1 / no argument, a value row its steps, a choice row only its choices
    good &= c.row_covers(('t', '', 'x.b', '', 'kQbBool', '-1'), 'x.b', '1', src)
    good &= not c.row_covers(('t', '', 'x.b', '', 'kQbBool', '-1'), 'x.b', '2', src)
    good &= c.row_covers(('t', '', 'weapon.give', '', 'kQbChoice', '-1'), 'weapon.give', 'wp_uzi', src)
    good &= not c.row_covers(('t', '', 'weapon.give', '', 'kQbChoice', '-1'), 'weapon.give', 'wp_none', src)
    good &= not c.row_covers(('t', '', 'a', 'x', 'kQbAction', '-1'), 'a', 'y', src)
    print('ringparity: %d ring entries (frozen at %d), %d bar rows, %d entries without a bar row; the rule (bool 0 / 1, '
          'choice list, same argument)  %s' % (n, c.RING_FROZEN, len(rows), len(miss), 'ok' if good else 'FAIL'))
    return good


# ---- 0.21.6 page Kostueme, flight line, quick command line ----
def cos_label(obj, slots):                    # CosLabelOf
    p = 'dlc_costume_'
    if obj[:len(p)].lower() == p and len(obj) == len(p) + 1 and 'a' <= obj[-1] <= 'p':
        return '%s %s (%s)' % (obj[-1], slots[ord(obj[-1]) - 97], obj)
    return obj


def cos_why(level, experimental=True, code=True):   # CosWhy
    if not experimental: return 'Experimental=0'
    if not code: return 'code check failed'
    return '' if level else 'needs a level'


def cos_rows(ids, now, list_open, level, max_rows=64):   # QbCosRows: [(kind, id, marked, why)]
    why = cos_why(level)
    rows = [('pick', now, True, why), ('next', 0, False, why), ('rec', 0, False, why), ('group', 0, False, '')]
    for i in ids if list_open else ():
        if len(rows) >= max_rows: break
        rows.append(('cos', i, i == now, why))
    return rows


def cos_records(records, names):            # CosRefresh: player records whose name is in the object list
    return [(i, names[n]) for i, (n, player) in enumerate(records) if player and names.get(n, 0)]


def check_cosbar():
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import trumenu_ini_check as c
    slots = c.Q216_COS_NAMES
    good = len(slots) == 16
    ids = list(range(100, 136))                # a cycle list of 36 (the size of the player records)
    closed = cos_rows(ids, 105, False, True)
    good &= len(closed) == 4 and [r[0] for r in closed] == ['pick', 'next', 'rec', 'group']
    opened = cos_rows(ids, 105, True, True)
    good &= len(opened) == 40 and [r[1] for r in opened[4:]] == ids
    good &= [r[1] for r in opened if r[0] == 'cos' and r[2]] == [105]          # exactly the current one marked
    good &= cos_rows(ids, 999, True, True)[0][2] and not any(r[2] for r in cos_rows(ids, 999, True, True)[4:])
    nolevel = cos_rows(ids, 105, True, False)
    good &= all(r[3] == 'needs a level' for r in nolevel if r[0] != 'group')   # every row refuses with the reason
    good &= cos_why(True, experimental=False) == 'Experimental=0' and cos_why(True, code=False) == 'code check failed'
    good &= cos_label('dlc_costume_f', slots) == 'f Casual Explorer (dlc_costume_f)'
    good &= cos_label('dlc_costume_m', slots) == "m People's Choice (dlc_costume_m)"
    good &= all(cos_label(o, slots) == o for o in ('lara_casual', 'dlc_doppel_costume_a', 'doppelganger_casual',
                                                     'dlc_costume_q', 'dlc_costume_ff'))   # no mapping known: the name
    recs = cos_records([('lara', True), ('x', False), ('lara_bikini', True), ('dlc_costume_d', True)],
                       {'lara': 7, 'lara_bikini': 8, 'x': 9})
    good &= recs == [(0, 7), (2, 8)]          # not a player record / not in the object list (d never built): left out
    # limits: own page 4 + N <= 64 up to N = 60 (cut beyond, the head says so); the Lara page would be 15 static rows +
    # 8 positions + 4 + N - over 64 from N = 38 on (TruDlc2Player's 37th record is already close)
    good &= all(len(cos_rows(list(range(n)), 0, True, True)) == min(4 + n, 64) for n in range(0, 129))
    lara_first_over = min(n for n in range(200) if 15 + 8 + 4 + n > 64)
    src = open(c.CPP, encoding='utf-8').read()
    block = src[src.index('const QbPage kQbPages[] = {'):]
    body = block[:block.index('\n};')]
    pages = body.count('\n    QB_PAGE(') + body.count('\n    {"')   # 0.22.16: comment lines in the table do not count
    good &= pages == 17 and lara_first_over == 38   # 0.21.11: 17 pages (+ Rettung; g_qbRow[17])
    print('cosbar: 4 rows + the open list (36 -> 40 rows), only the current one marked, no level = every row refused, '
          'labels for dlc_costume_a..p only, records with an object id; own page <= 64 rows (list cut after 60), Lara '
          'page over 64 from N = %d, %d pages  %s' % (lara_first_over, pages, 'ok' if good else 'FAIL'))
    return good


def cos_step(i, d, n):                        # CosStep
    if n <= 0: return -1
    if i < 0 or i >= n: return n - 1 if d < 0 else 0
    return (i + (n - 1 if d < 0 else 1)) % n


def cos_sim(events, n, start, settle=500, debounce=True, end=3000):
    """QbCosAct / QbCosTick at 60 fps: events = [(ms, 'L' | 'R' | 'X')]; returns the switches [(ms, index)]"""
    now, pick, pending, tick, out = start, None, False, 0, []
    ev = sorted(events)

    def apply(t, i):
        nonlocal now
        if i != now:                          # CosApply: the costume worn already = nothing
            out.append((t, i))
            now = i
    for t in range(0, end, 16):
        while ev and ev[0][0] <= t:
            _, k = ev.pop(0)
            shown = pick if pending else now
            if k == 'X':
                pending = False
                apply(t, shown)
                continue
            pick, pending, tick = cos_step(shown, -1 if k == 'L' else 1, n), True, t
            if not debounce:                  # the negative model: a switch on every step
                pending = False
                apply(t, pick)
        if pending and t - tick >= settle:
            pending = False
            apply(t, pick)
    return out


def burst_ok(events, switches, settle=500):   # the owner's rule: one switch per burst of steps (gaps < settle)
    steps = sorted(t for t, k in events if k != 'X')
    bursts = 1 + sum(1 for a, b in zip(steps, steps[1:]) if b - a >= settle) if steps else 0
    return len(switches) <= bursts


def check_cosdebounce():
    good = True
    taps = [(100 * k, 'R') for k in range(5)]                     # 5 quick taps
    s = cos_sim(taps, 10, 0)
    good &= len(s) == 1 and s[0][1] == 5 and 900 <= s[0][0] <= 920 and burst_ok(taps, s)
    held = [(0, 'R')] + [(400 + 120 * k, 'R') for k in range(9)]   # held right: QuickTick repeat 400 / 120 ms
    s = cos_sim(held, 36, 3)
    good &= len(s) == 1 and s[0][1] == 13 and burst_ok(held, s)
    two = [(0, 'R'), (700, 'R')]
    good &= [i for _, i in cos_sim(two, 10, 0)] == [1, 2]
    good &= cos_sim([(0, 'R')], 10, 9) [0][1] == 0 and cos_sim([(0, 'L')], 10, 0)[0][1] == 9   # wraps at both ends
    good &= cos_step(-1, 1, 10) == 0 and cos_step(-1, -1, 10) == 9 and cos_step(3, 1, 0) == -1
    x = cos_sim([(0, 'L'), (50, 'X')], 10, 4)
    good &= x == [(64, 3)]                    # X = at once, no second switch later
    circle = [(60 * k, 'R') for k in range(10)]
    good &= cos_sim(circle, 10, 2) == []      # all the way round: back on the worn one, nothing runs
    bad = cos_sim(taps, 10, 0, debounce=False)
    caught = len(bad) == 5 and not burst_ok(taps, bad)
    good &= caught
    print('cosdebounce: 5 taps / a held right switch once 0.5 s after the last step, two steps 0.7 s apart twice, wraps '
          'at both ends, X at once, full circle = nothing; negative model (switch on every step: %d switches) caught  %s'
          % (len(bad), 'ok' if good else 'FAIL'))
    return good


def hint_wanted(ini, flight, menu, level):   # FlightHintWanted
    return bool(ini and flight and not menu and level)


def hint_bottom(w, h, windows):              # DrawFlightHint: above the bottom-right windows of this frame
    bottom = h - 10.0
    for x0, y0, x1, y1 in windows:
        if x1 < w * 0.5 or y1 < h * 0.5: continue
        bottom = min(bottom, y0 - 6.0)
    return bottom


def check_flighthint(rng):
    combos = [c for c in itertools.product((0, 1), repeat=4) if hint_wanted(*c)]
    good = combos == [(1, 1, 0, 1)]
    w, h, line = 1920.0, 1080.0, 22.0
    for _ in range(2000):
        wins = []
        for _ in range(rng.randint(0, 2)):    # sound list / flow line in a random corner, random size
            ww, wh = rng.uniform(100, 900), rng.uniform(20, 700)
            right, low = rng.random() < 0.6, rng.random() < 0.6
            x0 = w - 10 - ww if right else 10.0
            y0 = h - 10 - wh if low else 10.0
            wins.append((x0, y0, x0 + ww, y0 + wh))
        b = hint_bottom(w, h, wins)
        top = b - line
        for x0, y0, x1, y1 in wins:
            if x1 >= w * 0.5 and y1 >= h * 0.5: good &= b <= y0 - 6.0 and not (top < y1 and b > y0)
    print('flighthint: shown only with FlightHint=1 + flight on + menu closed + a level (1 of 16 cases); 2000 random '
          'corner layouts: the line never overlaps a bottom-right window  %s' % ('ok' if good else 'FAIL'))
    return good


QC_PAD = (0x0040, 0x0080, 0x1000, 0x2000, 0x0001, 0x0002)   # L3, R3, A, B, D-pad up, down


def qc_sim(frames, toggle=0x00C0, hold=0x00C0, fb=0x0040):
    """QcPadTick: frames = [(buttons, blocked)]; returns the events"""
    _, _, A_, B_, UP, DOWN = QC_PAD
    prev, armed, open_, ev = 0, False, False, []
    for buttons, blocked in frames:
        edges = buttons & ~prev
        prev = buttons
        if blocked:
            armed = False
            if open_: ev.append('close')
            open_ = False
            continue
        others = (toggle | hold) & ~fb
        down = (buttons & fb) == fb
        if down and edges & fb: armed = True
        if down and buttons & others: armed = False
        if not down and armed:
            armed = False
            open_ = not open_
            ev.append('open' if open_ else 'close')
            continue
        if not down: armed = False
        if not open_: continue
        if edges & B_:
            open_ = False
            ev.append('close')
            continue
        if edges & A_: ev.append('run')
        if edges & UP: ev.append('up')
        if edges & DOWN: ev.append('down')
    return ev


def qc_history(hist, pos, up):               # QcHistory: (new pos, text)
    count = len(hist)
    pos = count - 1 if pos >= count else pos
    if up: pos = count - 1 if pos < 0 else pos - 1 if pos > 0 else 0
    else: pos = -1 if pos < 0 or pos + 1 >= count else pos + 1
    return pos, hist[pos] if pos >= 0 else ''


def check_quickcmd():
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import trumenu_ini_check as c
    L3, R3, A_, B_, UP, DOWN = QC_PAD
    f = lambda *b: [(x, False) for x in b]
    good = qc_sim(f(L3, 0)) == ['open'] and qc_sim(f(L3, 0, L3, 0)) == ['open', 'close']
    good &= qc_sim(f(L3, L3 | R3, R3, 0)) == [] and qc_sim(f(R3, L3 | R3, L3, 0)) == []   # L3 + R3 = menu / ring
    good &= qc_sim(f(L3, L3 | R3, L3, 0)) == []                   # R3 released first: still not a lone L3
    good &= qc_sim([(L3, False), (L3, True), (0, False)]) == []   # the menu opened while L3 was held
    good &= qc_sim(f(L3, 0) + [(0, True)]) == ['open', 'close']   # bar closed / menu / ring = closed
    good &= qc_sim(f(L3, 0, A_, A_, A_, 0, A_, 0)) == ['open', 'run', 'run']   # one run per press
    good &= qc_sim(f(L3, 0, B_, 0, A_, 0)) == ['open', 'close']   # B closes, A then belongs to the game again
    good &= qc_sim(f(L3, 0, UP, 0, UP, DOWN)) == ['open', 'up', 'up', 'down']
    good &= qc_sim(f(A_, 0, UP, 0)) == []                          # closed: A / D-pad are not the line's
    hist, pos, seen = ['a', 'b', 'c'], -1, []
    for up in (True, True, True, True, False, False, False, False):
        pos, t = qc_history(hist, pos, up)
        seen.append(t)
    good &= seen == ['c', 'b', 'a', 'a', 'b', 'c', '', '']
    good &= qc_history([], -1, True) == (-1, '')
    outs = []
    for k in range(6):                        # QcRun: the last 4 answers, newest first
        outs = ([k] + outs)[:4]
    good &= outs == [5, 4, 3, 2]
    src = open(c.CPP, encoding='utf-8').read()
    sec = src[src.find('// ---- 0.21.6 quick command line'):src.find('// ---- end of 0.21.6 quick command line')]
    good &= sec.count('CmdRunLine(') == 1 and not any(t in sec for t in c.Q216_EXEC)
    print('quickcmd: L3 alone opens / closes, L3 + R3 (either order) never, menu / bar close it, A runs once per press, '
          'B closes, D-pad = history (the menu bar\'s walk), 4 answers newest first, one run path (CmdRunLine)  %s'
          % ('ok' if good else 'FAIL'))
    return good


def tog_press(flag, kind, key):               # QbActRow / QbExecRow on a toggle row: (new flag, written?)
    if kind == 'action': return (not flag, True)   # 0.21.5: every right press flipped it blind ("rechts")
    want = (not flag) if key == 'X' else key == 'R'
    return (want, True) if want != flag else (flag, False)


def nav_note(kind, on, areas_on, mask, bits):   # NavRowNote
    if not on or kind > 1: return ''
    if kind == 1 and not areas_on: return '(nur mit Flaechen)'
    if not mask or (bits and not mask & bits): return '(Ebene fehlt)'
    return ''


def check_togglerows():
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import trumenu_ini_check as c
    good = True
    f, w = False, 0                            # bool row: right twice = on once, left = off, X flips
    for key in ('R', 'R', 'L', 'L', 'X', 'X'):
        f, wrote = tog_press(f, 'bool', key)
        w += wrote
    good &= f is False and w == 4
    f, _ = tog_press(False, 'action', 'R')
    f, _ = tog_press(f, 'action', 'R')
    good &= f is False                        # the old action row: two "right = on" presses ended off
    good &= nav_note(0, True, True, 0x1, 0x2) == '(Ebene fehlt)' and nav_note(0, True, True, 0, 0x2) == '(Ebene fehlt)'
    good &= nav_note(0, True, True, 0x3, 0x2) == '' and nav_note(0, True, True, 0x1, 0) == ''   # no graph: no claim
    good &= nav_note(1, True, False, 0x3, 0x2) == '(nur mit Flaechen)' and nav_note(2, True, True, 0, 0x2) == ''
    good &= nav_note(0, False, True, 0, 0x2) == ''                             # off: nothing to say
    src = open(c.CPP, encoding='utf-8').read()
    rows = [r for r in c.qb_rows(src) if r[2] in c.Q216_TOGGLE_ITEMS and r[3] and ' ' not in r[3]]
    nav = [r for r in rows if r[2] in ('nav.draw', 'dbg.flatpass')]
    good &= len(nav) == 14 and all(r[4] == 'kQbBool' for r in rows)
    print('togglerows: bool rows right = on (no second write), left = off, X flips (the old action row ended off after '
          'two rights); NavRowNote "(Ebene fehlt)" only with a graph layer outside the mask, "(nur mit Flaechen)" for '
          'the area-loop switches; shipped bar: %d toggle rows all bool (%d nav.draw / dbg.flatpass)  %s'
          % (len(rows), len(nav), 'ok' if good else 'FAIL'))
    return good


# ---- 0.21.7 (2026-11-07/08 night build): footer Y, help line, UTF-8 cut, refused costumes, uber text, navmesh walk,
# chapter units, shader live letters ----
def fav_ok(row):                                  # QbFavOk: the rule of QbFavPin without its messages
    return row is not None and row.kind not in ('label', 'group', 'planned') and row.id != '-' and not row.arg


def check_yfooter():
    """the footer's "Y: Favorit" / "Y: -" (QbFavOk) agrees with what Y does (QbFavPin in the 0.21.3 model QBar) for every
    row kind, with / without an argument, special rows (None) - and the footer line stays within 64 characters"""
    usable = {'cheat.flight', 'player.health', 'dbg.show', 'ai.kill', 'weapon.give', 'time.scale', 'level.load'}
    rows = [QRow('cheat.flight', kind='bool'), QRow('player.health'), QRow('dbg.show', 'death', 'bool'),
            QRow('ai.kill', 'others', confirm=True), QRow('-', 'ki_weg', 'group'), QRow('-', '', 'label'),
            QRow('-', 'x|y', 'planned'), QRow('weapon.give', kind='choice'), QRow('time.scale', kind='value'),
            QRow('level.load', 'dlc2_goo_room', confirm=True), None]
    ok = True
    for r in rows:
        b = QBar([], usable)
        got = b.frame(1, r, B_Y, 0, special='cp')
        ok &= (got in ('add', 'del')) == fav_ok(r)
    lines = []
    for de in (True, False):
        full = '%s  %s   %s' % ('X: ausfuehren  Y: Favorit' if de else 'X: run  Y: favourite',
                                'L3: Befehlszeile' if de else 'L3: cmd line', 'View + Start: zu' if de else 'View + Start: close')
        lines += [full, 'X: ausfuehren  Y: -' if de else 'X: run  Y: -']
    ok &= all(len(l) <= 64 for l in lines)
    print('yfooter: "Y: -" exactly where Y is refused (11 row kinds incl. special rows), footer <= 64 chars (%d)  %s'
          % (max(len(l) for l in lines), 'ok' if ok else 'FAIL'))
    return ok


def utf8_trim(b):                                 # Utf8TrimTail on bytes
    lead = len(b)
    while lead > 0 and (b[lead - 1] & 0xc0) == 0x80: lead -= 1
    if lead == 0: return b
    c = b[lead - 1]
    need = 4 if c >= 0xf0 else 3 if c >= 0xe0 else 2 if c >= 0xc0 else 1
    return b[:lead - 1] if lead - 1 + need > len(b) else b


def check_utf8cut(rng):
    """SwCopyText: a German text cut at any byte length (strncpy_s _TRUNCATE into char[n]) and trimmed is valid UTF-8 and a
    prefix of the text, at most one character lost"""
    words = ['Doppelgängerin', 'Kostüm', 'Söldner-Sprache', 'Zustände 243-245', 'Tödlicher Stoß', 'außerhalb', 'Ä Ö Ü ß €']
    ok, n = True, 0
    for _ in range(3000):
        text = ' '.join(rng.choice(words) for _ in range(rng.randrange(1, 6))).encode('utf-8')
        size = rng.randrange(1, 70)
        cut = utf8_trim(text[:size - 1])          # strncpy_s keeps size - 1 bytes + NUL
        try:
            s = cut.decode('utf-8')
        except UnicodeDecodeError:
            ok = False
            continue
        ok &= text.decode('utf-8').startswith(s) and len(text[:size - 1]) - len(cut) <= 3
        n += 1
    print('utf8cut: %d random German texts cut at random sizes: valid UTF-8, a prefix, at most one character lost  %s'
          % (n, 'ok' if ok else 'FAIL'))
    return ok


def cos_pick(i, d, offered):                     # QbCosAct kQdCosPick with the 0.21.7 skip (None = every entry refused)
    n = len(offered)
    nxt = i
    for _ in range(n):
        nxt = cos_step(nxt, d, n)
        if offered[nxt] != 0: break
    return None if offered[nxt] == 0 else nxt


def check_cosvalid(rng):
    """refused cycle-list entries (the game's check 0x5c54e0 = 0) are never picked by left / right, the offered ones are all
    reached in both directions (wrap), unknown (-1, not checked yet) counts as offered, all refused = refusal"""
    ok = True
    for _ in range(400):
        n = rng.randrange(1, 40)
        offered = [rng.choice((1, 1, 1, 0, -1)) for _ in range(n)]
        good = {k for k in range(n) if offered[k] != 0}
        for d in (-1, 1):
            i, seen = rng.randrange(-1, n), set()
            for _ in range(2 * n + 2):
                i2 = cos_pick(i, d, offered)
                if i2 is None:
                    ok &= not good
                    break
                ok &= offered[i2] != 0
                seen.add(i2)
                i = i2
            ok &= seen == good
    print('cosvalid: 400 random lists: left / right never land on a refused entry, every offered one reached both ways, '
          'all refused = refused  %s' % ('ok' if ok else 'FAIL'))
    return ok


GATE = {'nodes': ['closed', 'open', 'reset'], 'trans': {0: [(1, 2.0, 2)], 1: [(16, 1, 0), (1, 25.0, 0)], 2: [(16, 0, 1)]}}


def uber_text(node, trans_target, t, wait):      # UberText on the gate graph DTP 20851 (gate-like, German)
    names = GATE['nodes']
    word = {'open': 'oben', 'closed': 'unten', 'reset': 'unten, bereit'}

    def secs(s): return ('%.0f s' % s) if s >= 9.95 else ('%.1f s' % max(s, 0.0))
    if trans_target is not None:
        tgt = names[trans_target]
        s = 'faehrt hoch' if tgt == 'open' else 'faehrt runter' if tgt == 'closed' else 'wechselt -> ' + word.get(tgt, tgt)
        return s + (' (Animation)' if wait & 1 else '')
    best, to = None, None
    for cond, arg, target in GATE['trans'].get(node, []):
        if cond != 1: continue
        rest = max(arg - t, 0.0)
        if best is None or rest < best: best, to = rest, target
    name = names[node]
    if best is None: return word.get(name, name)
    if name == 'closed' and names[to] == 'reset': return 'unten, bereit in %s' % secs(best)
    return '%s, noch %s' % (word.get(name, name), secs(best))


def check_uber():
    """UberText on the gate graph of docs/Befund-Tore-CavernsHall-0711.md section 3 (open -> closed after 25.0 s, closed ->
    reset after 2.0 s, commands 16 never timed): the owner's wording, the countdown over a whole cycle"""
    cases = [((1, None, 13.0, 0), 'oben, noch 12 s'), ((1, None, 24.2, 0), 'oben, noch 0.8 s'),
             ((0, None, 0.5, 0), 'unten, bereit in 1.5 s'), ((2, None, 40.0, 0), 'unten, bereit'),
             ((-1, 1, 0.0, 1), 'faehrt hoch (Animation)'), ((-1, 0, 0.0, 0), 'faehrt runter')]
    ok = all(uber_text(*a) == want for a, want in cases)
    last, mono = 99.0, True                       # the open node: the time left falls over the 25 s
    for k in range(0, 251):
        v = float(uber_text(1, None, k / 10.0, 0).split('noch ')[1].split(' s')[0])
        mono &= v <= last + 1e-6
        last = v
    ok &= mono and last == 0.0
    print('uber: gate texts "oben, noch 12 s" / "unten, bereit in 1.5 s" / "unten, bereit" / "faehrt hoch|runter", the '
          'countdown falls 25 -> 0 s  %s' % ('ok' if ok else 'FAIL'))
    return ok


def check_navwalk(rng):
    """NlCollect's walk of one graph's area block (0x41290b): area + 0x38 + 0x14 * (flags & 0x7f) visits every area of a
    packed block exactly once and stops at the block end (random blocks, flag bits 26 / 27 / others do not disturb it);
    the filled colour rule of 0x40c69a (red > magenta > yellow > green)"""
    ok = True
    for _ in range(300):
        n = rng.randrange(1, 60)
        edges = [rng.randrange(3, 12) for _ in range(n)]
        flags = [e | (rng.randrange(2) << 26) | (rng.randrange(2) << 27) | (rng.randrange(0, 16) << 7) for e in edges]
        starts, a = [], 0
        for e in edges:
            starts.append(a)
            a += 0x38 + 0x14 * e
        size, seen, a, k = a, [], 0, 0
        while a < size and k < 20000:
            seen.append(a)
            a += 0x38 + 0x14 * (flags[starts.index(a)] & 0x7f)
            k += 1
        ok &= seen == starts and a == size

    def fill(f, v): return 1 if f & (1 << 27) else 2 if f & (1 << 26) else 3 if ((v >> 12) & 0xf) > 1 else 0
    ok &= [fill(1 << 27 | 1 << 26, 0), fill(1 << 26, 0x2000), fill(0, 0x2000), fill(0, 0x1000), fill(0, 0x0f00)] == [1, 2, 3, 0, 0]
    print('navwalk: 300 random area blocks walked area by area to the exact end; fill colour red > magenta > yellow > '
          'green  %s' % ('ok' if ok else 'FAIL'))
    return ok


def check_chapters():
    """page Kapitel: the groups of the level list kUnits (TruMenu.cpp) in order, one open at a time; with any one group
    open the page stays within 64 rows; DLC 2 units other than dlc_level2_start carry the note"""
    import os, re
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'asi', 'TruMenu',
                            'TruMenu.cpp'), encoding='utf-8').read()
    block = src[src.index('const UnitRow kUnits[] = {'):]
    units = re.findall(r'\{"([^"]+)", "([^"]+)", "[^"]+"\}', block[:block.index('\n};')])
    groups = []
    for g, _ in units:
        if g not in groups: groups.append(g)
    sizes = [sum(1 for x, _ in units if x == g) for g in groups]
    ok = len(units) == 111 and len(groups) == 10
    open_g = -1
    for g in [3, 3, 8, -1, 9, 0, 6]:              # open 3, again, 8 (3 closes), close, 9, 0, 6 (the largest: l1? no - any)
        open_g = g
        ok &= 10 + len(groups) + (sizes[open_g] if open_g >= 0 else 0) <= 64
    ok &= 10 + len(groups) + max(sizes) <= 64
    notes = [u for g, u in units if g == 'DLC 2' and u != 'dlc_level2_start']
    ok &= len(notes) == 10 and 'dlc_yggdrasil_hall02' in notes
    print('chapters: %d units in %d groups from kUnits, one group open, page <= 64 rows (largest group %d), %d DLC 2 units '
          'with the note  %s' % (len(units), len(groups), max(sizes), len(notes), 'ok' if ok else 'FAIL'))
    return ok


def sh_live(file_slots, pc, sur, live, first_new=2047, file_status='SURR'):   # ShLive: letters + status
    letters = []
    for k in range(4):
        lid = live[k]
        if lid is None:
            letters.append('-')
            continue
        c = '?'
        if lid and lid == pc[k]: c = file_slots[k]
        elif lid and lid == sur[k]: c = 'S'
        elif lid >= first_new: c = 'T'
        letters.append(c)
    s = ''.join(letters)
    if all(x is None for x in live): return s, 'LEER'
    if s == file_slots: return s, file_status
    if s[2] == 'S': return s, 'SURR'
    if 'S' in s: return s, 'PART'
    if '?' in s: return s, 'UNK'
    if 'T' in s: return s, 'TU'
    return s, file_status


def check_shlive():
    """ShLive on material 23164 (docs/Befund-Shader-Etiketten-0711.md 1.3): installed = file (SURR S-SS), the 50m / 50o
    test copy (PS2 2851) = S-TS PART, 51x (2988) = S-TS, a full translation T-TT = TU, cleared slots = LEER, an unknown
    base-game lib = ?"""
    pc, sur, slots = (1909, None, 1910, 1911), (1909, None, 1910, 1911), 'S-SS'
    cases = [((1909, None, 1910, 1911), ('S-SS', 'SURR')), ((1909, None, 2851, 1911), ('S-TS', 'PART')),
             ((1909, None, 2988, 1911), ('S-TS', 'PART')), ((2491, None, 2851, 2900), ('T-TT', 'TU')),
             ((None, None, None, None), ('----', 'LEER')), ((1909, None, 1090, 1911), ('S-?S', 'PART'))]
    ok = all(sh_live(slots, pc, sur, live) == want for live, want in cases)
    print('shlive: 23164 installed S-SS SURR, test copy 2851 / 2988 S-TS PART, full T-TT TU, cleared LEER, foreign lib ?  %s'
          % ('ok' if ok else 'FAIL'))
    return ok


# ---- 0.21.8 (TruMenu 0.21.8) ----
def q218_src():
    import os, re
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import trumenu_ini_check as c
    src = open(c.CPP, encoding='utf-8').read()
    m = re.search(r'const CmdDanger kCmdDanger\[\] = \{(.*?)\n\};', src, re.S)
    return src, c.item_types(src), re.findall(r'\{"([a-z0-9_.]+)", "', m.group(1)) if m else []


def danger_of(line, items, dids):            # CmdDangerOf
    words = line.split()
    if not words: return None
    w, arg = words[0].lower(), ' '.join(words[1:])
    if w in ('help', 'list', 'get'): return None   # builtins
    k = items.get(w)
    if k is None or k in ('info', 'todo'): return None
    if k in ('bool', 'int', 'float') and not arg: return None   # "<value id>" alone = its value
    for d in dids:
        if (d.endswith('.') and w.startswith(d)) or w == d: return d
    return None


def check_qcdanger():
    """CmdDangerOf on the source's kCmdDanger and item kinds: the owner's accident line "cheat.god 0" asks, its read
    "cheat.god" / "get cheat.god" / info items never; level / save / costume reset / sw.set lines ask; every exact id of
    the table is an item"""
    _, items, dids = q218_src()
    cases = {'cheat.god 0': 'cheat.', 'cheat.god': None, 'get cheat.god': None, 'cheat.list': None, 'cheat.fillup': 'cheat.',
             'player.invincible 1': 'player.invincible', 'player.invincible': None,
             'level.load dlc_level2_start': 'level.load', 'level.reload': 'level.reload', 'save.load autosave': 'save.load',
             'save.list': None, 'save.backup': None, 'costume.reset': 'costume.reset', 'costume.next': None,
             'sw.set TruShadowCombat:Death:TranslateNotify33 0': 'sw.set', 'sw.list': None, 'time.scale 0.5': None,
             'fav.add cheat.god': None, 'help': None, 'list cheat': None, 'nonsense.id 1': None, 'game.quit': 'game.quit'}
    bad = [(l, danger_of(l, items, dids), w) for l, w in cases.items() if danger_of(l, items, dids) != w]
    missing = [d for d in dids if not d.endswith('.') and d not in items]
    prefixed = sum(1 for i in items if i.startswith('cheat.') and items[i] not in ('info', 'todo'))
    ok = not bad and not missing and prefixed >= 5
    print('qcdanger: %d lines (cheat.god 0 asks, its reads never; level / save / costume reset / sw.set ask), %d table ids '
          'all items, %d cheat items  %s' % (len(cases), len(dids), prefixed, 'ok' if ok else 'FAIL %s %s' % (bad, missing)))
    return ok


def qc_arm_sim(events, items, dids, arm_ms=3000):   # QcRun(pad) + QcEdited / QcHistory (disarm)
    armed, at, out = '', 0, []
    for t, what, line in events:
        if what == 'edit':
            armed = ''
            continue
        pad = what == 'A'
        d = danger_of(line, items, dids) if pad else None
        if d and not (armed == line and t - at <= arm_ms):
            armed, at = line, t
            out.append('armed')
            continue
        armed = ''
        out.append('run')
    return out


def check_qcarm():
    """the second A: armed, then run within 3 s; after 3 s armed again; a history step / edit between disarms; another
    dangerous line arms itself; Enter (typed) runs at once; a harmless line runs at once"""
    _, items, dids = q218_src()
    g = 'cheat.god 0'
    cases = [([(0, 'A', g), (1000, 'A', g)], ['armed', 'run']),
             ([(0, 'A', g), (3500, 'A', g), (4000, 'A', g)], ['armed', 'armed', 'run']),
             ([(0, 'A', g), (500, 'edit', ''), (800, 'A', g)], ['armed', 'armed']),
             ([(0, 'A', g), (300, 'A', 'level.reload')], ['armed', 'armed']),
             ([(0, 'Enter', g)], ['run']),
             ([(0, 'A', 'get cheat.god'), (100, 'A', 'time.scale 0.5')], ['run', 'run']),
             ([(0, 'A', g), (1000, 'A', g), (1500, 'A', g)], ['armed', 'run', 'armed'])]   # after a run: asks again
    bad = [ev for ev, want in cases if qc_arm_sim(ev, items, dids) != want]
    print('qcarm: %d sequences (second A within 3 s, re-arm after 3 s, edit disarms, Enter at once, after a run asks '
          'again)  %s' % (len(cases), 'ok' if not bad else 'FAIL %s' % bad))
    return not bad


FAV_MAX = 1023                                  # sizeof(g_favs) - 1


def fav_arg_ok(arg):                            # FavArgOk
    return len(arg) < 96 and all(32 <= ord(ch) <= 126 and ch not in ',|' for ch in arg)


def fav_usable(i, items):                      # ItemUsable: FindItem is case-insensitive, todo items are not usable
    return items.get(i.lower()) not in (None, 'todo')


def fav_entries(text, items):                   # ForFavEntries
    out = []
    for e in text.split(','):
        if '|' in e:
            i, _, a = e.partition('|')
            i, a = i.strip(), a.strip()
            if i and fav_usable(i, items) and fav_arg_ok(a): out.append((i, a))
            continue
        out += [(i, '') for i in e.split() if fav_usable(i, items)]
    return out


def fav_set(text, items, i, a, add):            # FavSetArg: (new text, ok)
    if not fav_usable(i, items) or not fav_arg_ok(a): return text, False
    parts, had = [], False
    for f, x in fav_entries(text, items):
        if f.lower() == i.lower() and x.lower() == a.lower():
            had = True
            if not add: continue
        parts.append(f + ('|' + x if x else ''))
    if add and not had: parts.append(i + ('|' + a if a else ''))
    new = ','.join(parts)
    if len(new) > FAV_MAX: return text, False     # never a cut list
    return new, True


def old_fav_ids(text, items):                   # TruMenu < 0.21.8: strtok ", " + ItemUsable
    return [w for w in text.replace(',', ' ').split() if fav_usable(w, items)]


def check_favargs(rng):
    """the favourite list with "<id>|<argument>": old lists (comma or space) read as before, pairs added / removed
    without touching the rest, ',' / '|' refused, a list that would not fit refused unchanged, case-insensitive pairs, a
    pre-0.21.8 TruMenu reading a new list keeps its id-only favourites and skips the rest"""
    _, items, _ = q218_src()
    ok = fav_entries('player.invincible time.scale,level.reload', items) == [('player.invincible', ''), ('time.scale', ''),
                                                                           ('level.reload', '')]
    ok &= items.get('camera.free') != 'todo' or fav_entries('camera.free', items) == []   # a todo item is not usable
    t, a = fav_set('time.scale', items, 'sw.set', 'TruShadowCombat:Death:TranslateNotify33', True)
    t, b = fav_set(t, items, 'costume.set', '25', True)
    t, c2 = fav_set(t, items, 'level.load', 'dlc_yggdrasil_hall02', True)
    ok &= a and b and c2 and t == 'time.scale,sw.set|TruShadowCombat:Death:TranslateNotify33,costume.set|25,level.load|' \
                                   'dlc_yggdrasil_hall02'
    t2, d = fav_set(t, items, 'COSTUME.SET', '25', False)
    ok &= d and 'costume.set' not in t2 and t2.startswith('time.scale,sw.set|')
    ok &= fav_set(t, items, 'level.load', 'a,b', True) == (t, False) and fav_set(t, items, 'level.load', 'a|b', True) == (t, False)
    ok &= old_fav_ids(t, items) == ['time.scale']   # 0.21.7 skips "sw.set|..." etc. (no such item)
    # random round trips and the size limit
    ids = sorted(i for i in items if items[i] != 'todo')
    text = ''
    for _ in range(400):
        i = rng.choice(ids)
        arg = rng.choice(['', '1', '0x200', 'dlc_yggdrasil_hall02', 'TruRockVein:SweepAndPrune:Translate', 'a' * 90])
        before = fav_entries(text, items)
        new, okk = fav_set(text, items, i, arg, rng.random() < 0.7)
        if okk:
            after = fav_entries(new, items)
            ok &= len(new) <= FAV_MAX and all(e in after for e in before if (e[0].lower(), e[1].lower()) != (i.lower(), arg.lower()))
            text = new
        else:
            ok &= new == text
    full, okf = fav_set('x' * 0 + ','.join(['time.scale|' + 'a' * 90] * 10), items, 'level.load', 'b' * 90, True)
    ok &= not okf and full.count('|') == 10
    print('favargs: old lists, pairs add / remove, separators refused, full list refused unchanged, case-insensitive, old '
          'TruMenu keeps id-only favourites, 400 random steps  %s' % ('ok' if ok else 'FAIL'))
    return ok


def sg_covered(groups, g, parent):            # SgCovered
    p = parent.get(g, -1)
    for _ in range(16):
        if p <= 0: return False
        if p in groups: return True
        p = parent.get(p, -1)
    return False


def check_sgcover():
    """sound group sliders on the finding's tree (section 1.1): weapons {58, 60, 51, 31} writes 58 / 51 / 31 and skips 60
    (child of 58 - one factor per path); a group under another slider's group is written (55 under 51: weapons x hud);
    the factor sequence 50 -> 30 -> 100 writes twice and puts the old value back once"""
    import os, re
    src, _, _ = q218_src()
    parent = {15: 14, 32: 14, 78: 77, 77: 8, 58: 14, 60: 58, 51: 14, 31: 14, 27: 14, 65: 64, 64: 9, 68: 64, 70: 57, 72: 64,
              43: 14, 79: 53, 54: 53, 55: 51, 56: 53, 57: 53, 14: 6, 6: 5, 5: 4, 9: 8, 8: 4, 53: 4, 4: 0}
    sg = src[src.find('// ---- 0.21.8 sound group sliders'):src.find('// ---- end of 0.21.8 sound group sliders')]
    sliders = {k: [int(x) for x in g.split(',')][:int(c)] for k, g, c in
               re.findall(r'\{"([A-Za-z0-9]+)", "[^"]*", "[^"]*", \{([0-9, ]+)\}, (\d)\}', sg)}
    written = {k: [g for g in v if not sg_covered(v, g, parent)] for k, v in sliders.items()}
    ok = written.get('Weapons') == [58, 51, 31] and written.get('Hud') == [54, 55, 56, 57] and written.get('Lara') == [68, 70, 72, 77]
    ok &= sum(len(v) for v in written.values()) == sum(len(v) for v in sliders.values()) - 1
    # write sequence of one group (SgTick): orig 1.0
    st = {'ours': False, 'set': 0.0, 'orig': 0.0}
    cur, writes, restores = 1.0, 0, 0
    for pct in (50, 50, 30, 30, 100, 100):
        if pct >= 100:
            if st['ours'] and abs(cur - st['set']) < 0.0005:
                cur, restores = st['orig'], restores + 1
            st['ours'] = False
            continue
        want = pct / 100.0
        if st['ours'] and abs(cur - want) < 0.0005: continue
        if not st['ours']: st['orig'] = cur
        cur, writes = want, writes + 1
        st.update(ours=True, set=want)
    ok &= writes == 2 and restores == 1 and cur == 1.0
    print('sgcover: 8 sliders, weapons skips 60 (child of 58), cross-slider paths written, 50 -> 30 -> 100 = 2 writes + 1 '
          'restore  %s' % ('ok' if ok else 'FAIL %s' % written))
    return ok


def check_qcsuggest():
    """the small line's Up / Down (QcCallback): a typed line with suggestions walks the suggestions (-1 .. count-1, as the
    menu bar), an empty line or a history line walks the history; Tab takes the selected one, else the first"""
    def step(sel, count, up, typed, hist_pos):
        if hist_pos < 0 and typed and count:
            return ('sug', sel - 1 if up and sel >= 0 else sel if up else min(sel + 1, count - 1))
        return ('hist', None)
    ok = step(-1, 3, False, True, -1) == ('sug', 0) and step(2, 3, False, True, -1) == ('sug', 2)
    ok &= step(0, 3, True, True, -1) == ('sug', -1) and step(-1, 3, True, True, -1) == ('sug', -1)
    ok &= step(-1, 0, True, True, -1) == ('hist', None) and step(-1, 3, True, False, -1) == ('hist', None)
    ok &= step(1, 3, True, True, 2) == ('hist', None)
    tab = lambda sel, count: sel if 0 <= sel < count else 0
    ok &= tab(-1, 4) == 0 and tab(2, 4) == 2 and tab(7, 4) == 0
    print('qcsuggest: Up / Down walk the suggestions of a typed line, else the history; Tab = selected or first  %s'
          % ('ok' if ok else 'FAIL'))
    return ok


def cine_pad_sim(polls, masks=(0x0120, 0x0220, 0x0320), active=True):
    """0.22.13 CnPadTick / CnPadIsSub as a model: polls = [(ms, buttons)], one poll every given time; returns the actions
    fired as (ms, combo index). A combo inside a larger one fires on release when the peak is exactly its set; a combo
    inside no other fires as soon as exactly its buttons are held; one action per press (latch until 120 ms released)."""
    def is_sub(i):
        m = masks[i]
        return bool(m) and any(j != i and masks[j] and masks[j] != m and (masks[j] & m) == m for j in range(3))
    allm = masks[0] | masks[1] | masks[2]
    st = dict(prev=0, since=0, latch=False, peak=0)
    out = []
    for now, buttons in polls:
        held, before = buttons & allm, st['prev'] & allm
        if held != before: st['since'] = now
        st['prev'] = buttons
        stable = now - st['since'] >= 120
        if st['latch']:
            if not held and stable: st['latch'], st['peak'] = False, 0
            continue
        if not held and stable: st['peak'] = 0
        fired = False
        for i in range(3):
            m = masks[i]
            if not before or not m or not is_sub(i) or (before & m) != m or (held & m) == m: continue
            st['latch'] = True
            if (st['peak'] | before) == m and active: out.append((now, i))
            fired = True
            break
        if fired: continue
        st['peak'] |= held
        if not active or not held: continue
        for i in range(3):
            if masks[i] and held == masks[i] and not is_sub(i):
                st['latch'] = True
                out.append((now, i))
                break
    return out


def check_cinepad():
    """0.22.13 (live 2026-11-09 21:04: LB + View pressed before RB fired 'continue' on the way to the photo combo)"""
    LB, RB, VIEW = 0x0100, 0x0200, 0x0020
    def run(seq, step=10, **kw):                 # seq = [(ms from, buttons)] -> polls every 10 ms up to the last + 400
        polls, end = [], seq[-1][0] + 400
        for t in range(0, end, step):
            b = 0
            for at, bt in seq:
                if t >= at: b = bt
            polls.append((t, b))
        return [i for _, i in cine_pad_sim(polls, **kw)]
    cases = [
        ('LB, View, then RB (the live case) -> photo only', [(0, LB), (50, LB | VIEW), (400, LB | VIEW | RB), (700, 0)], [2]),
        ('LB + View held 1 s, released -> continue once', [(0, LB | VIEW), (1000, 0)], [0]),
        ('LB + View, LB let go first -> continue at once', [(0, LB | VIEW), (300, VIEW), (600, 0)], [0]),
        ('RB + View, released -> one frame', [(0, VIEW | RB), (200, 0)], [1]),
        ('all three in one poll -> photo', [(0, LB | RB | VIEW), (300, 0)], [2]),
        ('photo, then RB let go while LB + View stay -> nothing more', [(0, LB | RB | VIEW), (300, LB | VIEW), (900, 0)], [2]),
        ('LB + View, RB tapped for 10 ms -> photo (at once), no continue',
         [(0, LB | VIEW), (200, LB | VIEW | RB), (210, LB | VIEW), (500, 0)], [2]),
        ('View alone -> nothing', [(0, VIEW), (300, 0)], []),
        ('LB + RB, RB let go, View added, released -> nothing (RB was part of this press)',
         [(0, LB | RB), (100, LB), (150, LB | VIEW), (400, 0)], []),
        ('two presses of LB + View -> continue twice', [(0, LB | VIEW), (200, 0), (500, LB | VIEW), (700, 0)], [0, 0]),
    ]
    ok = True
    for name, seq, want in cases:
        got = run(seq)
        good = got == want
        ok &= good
        print('cinepad: %s: %s  %s' % (name, got, 'ok' if good else 'FAIL (want %s)' % want))
    got = run([(0, LB | VIEW), (300, 0)], active=False)
    ok &= got == []
    print('cinepad: menu / ring own the pad (not active) -> nothing: %s  %s' % (got, 'ok' if got == [] else 'FAIL'))
    return ok


# ---- 0.22.14 sublang: the reader's parse (SrLines, as 0x4538d0) and the box rewrite (SrRewrite)
def sr_space(c):
    return c == 0x20 or 9 <= c <= 13


def sr_atoi(b, p):                               # CRT atoi from p (the reader's id; p is not at whitespace here)
    i, sign, v = p, 1, 0
    while i < len(b) and sr_space(b[i]): i += 1
    if i < len(b) and b[i] in (0x2b, 0x2d):
        sign = -1 if b[i] == 0x2d else 1
        i += 1
    while i < len(b) and 0x30 <= b[i] <= 0x39:
        v = v * 10 + b[i] - 0x30
        i += 1
    return sign * v


def sr_lines(rec, word, game_lang, cap=8):      # SrLines
    b, kind = rec['text'], rec['kind']
    out, p = [], 0
    while p < len(b) and sr_space(b[p]): p += 1
    while p < len(b):
        idv = sr_atoi(b, p)
        while p < len(b) and b[p] != 0x0d: p += 1
        if p < len(b): p += 1
        e = bytearray()
        while p < len(b) and b[p] != 0x0d and len(e) < 0xff:
            e.append(b[p])
            p += 1
        while p < len(b) and b[p] != 0x0d: p += 1
        show = kind != 2 and (idv == word or (word == -1 and idv == game_lang and kind == 1))
        if show:
            for tok in bytes(e).split(b'\n'):
                if not tok: continue                     # strtok skips empty tokens
                t = tok
                k = 0
                while k + 2 < len(t):                    # t[k], t[k + 1], t[k + 2] all non-NUL (0x4539e0..0x453a0b)
                    if t[k] == 0x3a and t[k + 1] == 0x20:
                        t = t[k + 2:]
                        break
                    k += 1
                out.append(t)
        while p < len(b) and sr_space(b[p]): p += 1
    return out[:cap]


def sr_rewrite(recs, box, v, game_lang):        # SrRewrite: recs older first, each with 'line' = what the box got
    allp = []
    for j, r in enumerate(recs):
        for k in range(len(r['line'])): allp.append((j, k, len(r['line'])))
    nl = [sr_lines(r, v, game_lang) for r in recs]
    base, total = [], 0
    for j in range(len(recs)):
        base.append(total)
        total += len(nl[j])

    def map_new(pos):
        j, k, n = pos
        if not nl[j]: return base[j] - 1
        kk = len(nl[j]) - 1 if k == n - 1 else min(k, len(nl[j]) - 1)
        return base[j] + kk

    def new_text(q):
        for j in range(len(recs) - 1, -1, -1):
            if base[j] <= q < base[j] + len(nl[j]): return nl[j][q - base[j]]
        return None

    for r in recs:                               # 0.22.16 (U3): shown[k] = what TruMenu wrote for stored line k last
        if 'shown' not in r: r['shown'] = [None] * len(r['line'])

    def is_line(i, text):
        j, k, _ = allp[i]
        return recs[j]['line'][k] == text or recs[j]['shown'][k] == text
    pos = [-1, -1]
    if box[1]:
        for i in range(len(allp) - 1, -1, -1):
            if is_line(i, box[1]): pos[1] = i; break
    if box[0]:
        if pos[1] > 0 and is_line(pos[1] - 1, box[0]): pos[0] = pos[1] - 1
        else:
            for i in range(len(allp) - 1, -1, -1):
                if i != pos[1] and is_line(i, box[0]): pos[0] = i; break
    want = [None, None]
    q1 = -2
    if pos[1] >= 0:
        q1 = map_new(allp[pos[1]])
        want[1] = new_text(q1) if q1 >= 0 else None
    if pos[0] >= 0:
        if pos[1] >= 0 and pos[0] == pos[1] - 1: want[0] = new_text(q1 - 1) if q1 >= 1 else None
        else:
            q0 = map_new(allp[pos[0]])
            want[0] = new_text(q0) if q0 >= 0 else None
    out = [want[s][:0xff] if box[s] and pos[s] >= 0 and want[s] is not None else box[s] for s in range(2)]
    for s in range(2):                           # 0.22.16 (U3): remember the written / kept text of the stored line
        if box[s] and pos[s] >= 0 and want[s] is not None:
            j, k, _ = allp[pos[s]]
            recs[j]['shown'][k] = out[s]
    return out


def sr_read(text, word, kind=1, game_lang=0):  # what the reader gives the box when the record comes
    r = {'text': text, 'kind': kind}
    r['line'] = sr_lines(r, word, game_lang)
    return r


def sr_box(recs):                                # the box after the records: the last two lines (no clock expiry)
    lines = [l for r in recs for l in r['line']]
    return [lines[-2] if len(lines) > 1 else b'', lines[-1] if lines else b'']


def check_sublang():
    ok = True
    # the record of pdlc2_030_pod.mul @0x3e798c (tools/mul_sub_records.py), the next one made up in the same form
    pod = b'0\rAmanda cut the power.\r11\rAmanda heeft de stroom uitgezet.\r1\rAmanda a coup\xc3\xa9 le courant.\r' \
          b'2\rAmanda hat die Energiezufuhr gekappt.\r3\rAmanda ha tolto la corrente.\r4\rAmanda ha desactivado la ' \
          b'energ\xc3\xada, ve a activarla.\r'
    nxt = b'0\rZip: Go reactivate it.\r2\rZip: Schalte sie wieder ein.\r'
    cases = []
    a, b2 = sr_read(pod, 0), sr_read(nxt, 0)
    cases.append(('held cutscene, sub.lang 2: both lines German', sr_rewrite([a, b2], sr_box([a, b2]), 2, 0),
                  [b'Amanda hat die Energiezufuhr gekappt.', b'Schalte sie wieder ein.']))
    a2, b3 = sr_read(pod, 2), sr_read(nxt, 2)
    cases.append(('German shown, sub.lang 0: back to English', sr_rewrite([a2, b3], sr_box([a2, b3]), 0, 0),
                  [b'Amanda cut the power.', b'Go reactivate it.']))
    cases.append(('sub.lang 1: French keeps the UTF-8 bytes', sr_rewrite([b2, a], sr_box([b2, a]), 1, 0),
                  [b'Go reactivate it.', b'Amanda a coup\xc3\xa9 le courant.']))
    cases.append(('clock ran out (upper = newest, lower empty)', sr_rewrite([a, b2], [b'Go reactivate it.', b''], 2, 0),
                  [b'Schalte sie wieder ein.', b'']))
    cases.append(('Bink line (no stored record) stays', sr_rewrite([a, b2], [b'Movie line', b'Go reactivate it.'], 2, 0),
                  [b'Movie line', b'Schalte sie wieder ein.']))
    cases.append(('-1 = game language (2) for kind 1', sr_rewrite([a, b2], sr_box([a, b2]), -1, 2),
                  [b'Amanda hat die Energiezufuhr gekappt.', b'Schalte sie wieder ein.']))
    k0a, k0b = sr_read(pod, 0, kind=0), sr_read(nxt, 0, kind=0)
    cases.append(('-1 with kind 0: no line -> left', sr_rewrite([k0a, k0b], sr_box([k0a, k0b]), -1, 2),
                  [b'Amanda cut the power.', b'Go reactivate it.']))
    cases.append(('kind 2 shows nothing', sr_lines({'text': pod, 'kind': 2}, 0, 0), []))
    two = b'0\rLine one\nLine two\r2\rZeile eins und zwei\r'
    t = sr_read(two, 0)
    cases.append(('2 English lines -> 1 German: upper from the record before', sr_rewrite([a, t], sr_box([a, t]), 2, 0),
                  [b'Amanda hat die Energiezufuhr gekappt.', b'Zeile eins und zwei']))
    nde = b'0\rOnly English here.\r3\rSolo italiano.\r'
    o = sr_read(nde, 0)
    cases.append(('no German entry: lower = the record before, upper left',
                  sr_rewrite([a, o], sr_box([a, o]), 2, 0), [b'Amanda cut the power.', b'Amanda hat die Energiezufuhr gekappt.']))
    cases.append(('speaker strip only at ": " with a byte after it', sr_lines({'text': b'0\rNote:x\r0\rA: \r0\rB: c\r', 'kind': 1}, 0, 0),
                  [b'Note:x', b'A: ', b'c']))
    longt = b'0\r' + b'x' * 300 + b'\r2\rkurz\r'
    cases.append(('255 bytes at most', [len(l) for l in sr_lines({'text': longt, 'kind': 1}, 0, 0)], [255]))
    cases.append(('id "-1" matches word -1 directly', sr_lines({'text': b'-1\rminus\r', 'kind': 0}, -1, 2), [b'minus']))
    # 0.22.16 (U3, live 2026-11-10 13:48: EN -> DE worked, then 11 / 0 found no stored line): EN -> DE -> NL -> EN
    nx = b'0\rZip: Go reactivate it.\r2\rZip: Schalte sie wieder ein.\r11\rZip: Zet hem weer aan.\r'
    c1, c2 = sr_read(pod, 0), sr_read(nx, 0)
    box = sr_box([c1, c2])
    chain = []
    for v in (2, 11, 0):
        box = sr_rewrite([c1, c2], box, v, 0)
        chain.append(list(box))
    cases.append(('U3 chain EN -> DE -> NL -> EN (each switch rewrites again)', chain,
                  [[b'Amanda hat die Energiezufuhr gekappt.', b'Schalte sie wieder ein.'],
                   [b'Amanda heeft de stroom uitgezet.', b'Zet hem weer aan.'],
                   [b'Amanda cut the power.', b'Go reactivate it.']]))
    d1 = sr_read(pod, 0)
    one = [b'', d1['line'][0]]
    for v in (2, 11, 2, 0):
        one = sr_rewrite([d1], one, v, 0)
    cases.append(('U3 one line, four switches back to English', one, [b'', b'Amanda cut the power.']))
    for name, got, want in cases:
        good = got == want
        ok &= good
        print('sublang: %s: %s  %s' % (name, got, 'ok' if good else 'FAIL (want %s)' % want))
    return ok


AW = ['ok', 'nodata', 'noenemy', 'noweapon', 'weaponblocks', 'gamegate', 'noinput', 'nobit18', 'bit11', 'nolockbits',
      'scripted', 'notargeter', 'nocand', 'notcand', 'rejected', 'bucket', 'othertarget', 'tunezero']   # kAw* order


def am_why(s):                                  # AmRead: the first blocking step of the lock-on path (0.22.15)
    held = s.get('padOk', True) and bool(s.get('pad630', 0) & 4)
    pressed = s.get('padOk', True) and bool(s.get('pad690', 0) & 4)
    timers = s.get('t588', 0.0) > 0.0 or s.get('t58c', 0.0) > 0.0 or s.get('t798', 0.0) != 0.0   # 0x72180f..0x721836
    w = s.get('w', 0)
    lock = ((w >> 9) & 3) != 0
    near, where = s.get('near', 1), s.get('where', -1)
    if not near: return 'noenemy'
    if where == 0x30 and lock: return 'ok'
    if s.get('t788', 0.0) > 0.0: return 'scripted'
    wpn = s.get('wpn', 0)
    if wpn == -1: return 'noweapon'
    if wpn in (7, 12): return 'weaponblocks'
    if not lock and (s.get('e6', 1) == 0 or (s.get('g144', 0) & 1) or s.get('g143', 0) == 4): return 'gamegate'
    if not lock and not held and not pressed and not timers: return 'noinput'
    if not (w >> 18) & 1: return 'nobit18'
    if (w >> 11) & 1: return 'bit11'
    if not lock and pressed and not timers and s.get('tuneok', True) and s.get('tune294', 1) == 0: return 'tunezero'
    if not lock: return 'nolockbits'
    if not s.get('t0', True): return 'notargeter'
    if not s.get('ncand', 0): return 'nocand'
    if where == -1: return 'notcand'
    if where == 0x20: return 'rejected'
    if s.get('target', 0) and s.get('target', 0) != near: return 'othertarget'
    return 'bucket'


def check_aimwhy():
    """0.22.15 aim.why: the order of AmRead's tests (model of the C++ chain; the 10.11. live case first)"""
    ok = True
    b18_19 = (1 << 18) | (1 << 19)
    live = 0x065f8010                           # TruFight.log 13:30-13:31: bits 18 / 19 / 20 set, 9 / 10 / 11 clear
    cases = [
        ('bits as live 10.11. (18 / 19 set, 9 / 10 clear), no pad bit 2, timers 0', dict(w=live, wpn=0, pad630=0, ncand=1, where=0x10), 'noinput'),
        ('pad bit 2 held, no lock bits yet (one frame before 0x7216b0)', dict(w=live, wpn=0, pad630=4, t588=3.0), 'nolockbits'),
        ('held, but chart bit 18 clear', dict(w=0, wpn=0, pad630=4), 'nobit18'),
        ('LT (action 35) held, tuning byte +0x294 = 0, timers 0', dict(w=live, wpn=0, pad690=4, tune294=0), 'tunezero'),
        ('LT held, tuning byte 15 but timer not yet set', dict(w=live, wpn=0, pad690=4, tune294=15), 'nolockbits'),
        ('no weapon', dict(w=live, wpn=-1, pad630=4), 'noweapon'),
        ('weapon kind 12', dict(w=live, wpn=12, pad630=4), 'weaponblocks'),
        ('menu bit 0xe7f144', dict(w=live, wpn=0, g144=1, pad630=4), 'gamegate'),
        ('byte 0x8ab4e6 = 0', dict(w=live, wpn=0, e6=0, pad630=4), 'gamegate'),
        ('scripted target P+0x788', dict(w=live, wpn=0, t788=2.0), 'scripted'),
        ('bit 11 with input', dict(w=b18_19 | (1 << 11), wpn=0, pad630=4), 'bit11'),
        ('lock (bit 10), nearest rejected', dict(w=b18_19 | (1 << 10), wpn=0, ncand=2, where=0x20), 'rejected'),
        ('lock, nearest not offered', dict(w=b18_19 | (1 << 10), wpn=0, ncand=1, where=-1), 'notcand'),
        ('lock, no candidates', dict(w=b18_19 | (1 << 10), wpn=0, ncand=0), 'nocand'),
        ('lock, other target', dict(w=b18_19 | (1 << 10), wpn=0, ncand=2, where=0x10, target=2), 'othertarget'),
        ('soft lock (bit 9), nearest = target', dict(w=b18_19 | (1 << 9), wpn=0, ncand=1, where=0x30, target=1), 'ok'),
        ('locked target wins over a game gate', dict(w=b18_19 | (1 << 10), wpn=0, e6=0, where=0x30, target=1), 'ok'),
        ('no enemy', dict(near=0, w=live), 'noenemy'),
    ]
    for name, s, want in cases:
        got = am_why(s)
        good = got == want and got in AW
        ok &= good
        print('aimwhy: %s: %s  %s' % (name, got, 'ok' if good else 'FAIL (want %s)' % want))
    return ok


# ---- 0.22.16 settings: the subtitle look sites (SuApply), the bar steps, groups that start closed (QbGroupClosed)
SU_START_CLOSED = ('set_gfxn', 'set_tm', 'fig_combat')   # a sample of kQbStartClosed


def su_step(s):                                  # SuStep: round(22 x s / 0.6), 8 .. 60
    st = int(22.0 * s / 0.6 + 0.5)
    return max(8, min(60, st))


def su_sites(show, size, box, alpha, colour, pos, our_pos=0x10, our_size=0x14, stub=0x99):   # SuApply: wanted bytes
    default = abs(size - 0.6) < 0.001
    a = min(255, (alpha * 256 + 50) // 100)
    return [0x0084e8d0 if pos == 352 else our_pos, 0x00841bd0 if default else our_size,
            0x16 if default else su_step(size), 0x2c if default else 2 * su_step(size), 1 if box else 0, a << 24,
            0xffef32c5 if show and colour == 0 else stub]


def qb_closed(text, key, start=SU_START_CLOSED):  # QbGroupClosed (0.22.16: "+key" opens a group that starts closed)
    words = [w for w in text.replace(' ', ',').split(',') if w]
    if key in words: return True
    return key in start and '+' + key not in words


def qb_set(text, key, closed, start=SU_START_CLOSED):   # QbGroupSet
    words = [w for w in text.replace(' ', ',').split(',') if w and w != key and w != '+' + key]
    if closed and key not in start: words.append(key)
    if not closed and key in start: words.append('+' + key)
    return ','.join(words)


def check_settings():
    cases = []
    game = [0x0084e8d0, 0x00841bd0, 0x16, 0x2c, 1, 0x40000000, 0xffef32c5]
    cases.append(('defaults = the game\'s bytes at every site', su_sites(1, 0.6, 1, 25, 0, 352), game))
    cases.append(('size 0.9: own float, step 33, limit 66', su_sites(1, 0.9, 1, 25, 0, 352)[1:4], [0x14, 33, 66]))
    cases.append(('size 1.1: step 40 (imm8, limit 80 < 128)', su_sites(1, 1.1, 1, 25, 0, 352)[2:4], [40, 80]))
    cases.append(('size 0.5: step 18', su_sites(1, 0.5, 1, 25, 0, 352)[2], 18))
    cases.append(('opacity 0 / 60 / 80 / 100 %', [su_sites(1, 0.6, 1, p, 0, 352)[5] >> 24 for p in (0, 60, 80, 100)],
                  [0, 154, 205, 255]))
    cases.append(('show off or a colour: the line call goes to the stub', [su_sites(0, 0.6, 1, 25, 0, 352)[6],
                  su_sites(1, 0.6, 1, 25, 2, 352)[6]], [0x99, 0x99]))
    cases.append(('bar off: flag 0', su_sites(1, 0.6, 0, 25, 0, 352)[4], 0))
    cases.append(('volume step = round(v / 8), 17 steps', [int(v / 8.0 + 0.5) for v in (0, 4, 64, 124, 128)], [0, 1, 8, 16, 16]))
    t = ''
    cases.append(('start-closed group closed with an empty list', qb_closed(t, 'set_gfxn'), True))
    t = qb_set(t, 'set_gfxn', False)
    cases.append(('opened: "+set_gfxn" kept', (t, qb_closed(t, 'set_gfxn')), ('+set_gfxn', False)))
    t = qb_set(t, 'set_gfxn', True)
    cases.append(('closed again: the word goes', (t, qb_closed(t, 'set_gfxn')), ('', True)))
    t = qb_set('ki_dumm', 'set_sub', True)
    cases.append(('a normal group as before', (t, qb_closed(t, 'set_sub'), qb_closed(t, 'ki_dumm')),
                  ('ki_dumm,set_sub', True, True)))
    ok = True
    for name, got, want in cases:
        good = got == want
        ok &= good
        print('settings: %s: %s  %s' % (name, got, 'ok' if good else 'FAIL (want %s)' % (want,)))
    return ok


def main():
    rng = random.Random(17)
    results = [check_depth(rng), check_chord(), check_frames(), check_segments(), check_confirm(), check_presets(),
               check_burst(), check_bits(), check_goload(), check_waitunit(), check_forget(),   # 0.20: + three
               check_soundlist(), check_mutemusic(),                                         # 0.20.1: + two
               check_spiders(), check_wobble(rng), check_drawmask(), check_shake(), check_labels(),   # 0.21: + six
               check_airemove(),
               check_killpath(), check_sticky(), check_roomcheck(), check_unitgo(), check_favrecent(),   # 0.21.1: + six
               check_groups(),
               check_padchain(), check_padblock(),                                    # 0.21.2 / TruShadowPower 0.19
               check_xyfav(), check_xyexec(), check_footer(), check_sndwidth(),       # 0.21.3
               check_h2drift(), check_fixhall02(), check_scriptval(rng),              # 0.21.4
               check_switches(), check_swfold(), check_ringparity(),                  # 0.21.5
               check_cosbar(), check_cosdebounce(), check_flighthint(rng), check_quickcmd(),   # 0.21.6
               check_togglerows(),
               check_yfooter(), check_utf8cut(rng), check_cosvalid(rng), check_uber(), check_navwalk(rng),   # 0.21.7
               check_chapters(), check_shlive(),
               check_qcdanger(), check_qcarm(), check_favargs(rng), check_sgcover(), check_qcsuggest(),   # 0.21.8
               check_cinepad(),                                                       # 0.22.13
               check_sublang(),                                                       # 0.22.14
               check_aimwhy(),                                                        # 0.22.15
               check_settings()]                                                      # 0.22.16
    print('all ok' if all(results) else 'FAILED')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
