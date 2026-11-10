"""Ring layout of the PC main / pause menu (generalbank script 7 `uipause`), read-only (2026-11-10, finding
docs/Befund-Ring-8-Plaetze-1011.md: can the ring get an 8th slot "Quit" at the bottom?).

What it prints for one or more sources:
  * the geometry members and their init values: m0xa60 radius (5.7), m0xa68 "pi" (3.1416), m0xa70 (14.0);
    func 0 derives count m0xa38 = m0xa70 / 2, m0xa40 = int(count), step m0xa48 = m0xa68 / count
  * the 14 ring positions PositionMenuItems (func 35) computes: index k = 1..count on the left half at angle
    (k-1)*step, index count+j on the right half at -j*step; vector (-cos(a - pi/2), sin(a - pi/2)) * radius
    (corebase f11 = cos 0x813420, f12 = sin 0x813680), in units and in 1080p pixels (54.04 px per unit, centre
    960 / 540 - fitted to the screenshot references/DLC1/PC-Test-20261103_DLC1_14_Pausemenue_Ring_keineHilfe.png)
  * the 16 hit-area members 0x108 .. 0x180 (userType 361): their entries reference widgets by name symbol; shown as
    the instance offsets of the members carrying those names (bg / icon / label plate / text of each position)
  * the label text id (locals) of the slot text widgets and the texture id (id5) of the slot icons
Optional --variant 16: the same positions as if m0xa70 were 16.0 (count 8, step pi/8) - arithmetic only.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/menu_ring_layout.py SOURCE [SOURCE ...] [--variant 16]
  SOURCE as tools/script_func_list.sections (a PC generalbank.drm file, pp / pb, pc:generalbank.drm)
Exit 0 when every source has the PC layout this finding describes (m0xa70 = 14.0, 16 hit areas, position 14 =
bottom); 1 otherwise.
"""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import script_conv as SC

SID = 7
PPU, CX, CY = 54.04, 960.0, 540.0
TEXTS = [0x354, 0x360, 0x36c, 0x378, 0x384, 0x390, 0x39c, 0x3a8, 0x468]
ICONS = [0x6e4, 0x6f0, 0x6fc, 0x708, 0x714, 0x720, 0x72c, 0x738, 0x7bc]
HITS = list(range(0x108, 0x188, 8))


def load(src):
    S, e = FL.sections(src)
    if e != 'le':
        return None
    sec = next((q for q in S if q[0] == 8 and q[1] == SID and q[2]), None)
    if sec is None:
        return None
    d, rl = sec[2], sec[3]
    rel = R.parse(rl, e)
    W = SC.Walk(d, rel, e).run()
    mt = next((t, n) for name, t, n, sz in W.arrays if name == 'members')
    by, byname = {}, {}
    for k in range(mt[1]):
        a = mt[0] + 20 * k
        off, nm = struct.unpack_from('<HH', d, a + 12)
        by[off] = a
        byname.setdefault(nm, []).append(off)
    return d, dict(rel.internal), rel.id_offsets(), by, byname


def init_base(d, it, by, off):
    ini = it.get(by[off] + 16)
    return None if ini is None else it.get(ini, ini)


def positions(count, step, radius):
    out = []
    for k in range(1, 2 * count + 1):
        a = (k - 1) * step if k <= count else -(k - count) * step
        x, y = -math.sin(a) * radius, -math.cos(a) * radius
        out.append((k, math.degrees(a), x, y, CX + x * PPU, CY + y * PPU))
    return out


def report(src, variant):
    L = load(src)
    if L is None:
        print('%s: script %d not found or not a PC source' % (src, SID))
        return False
    d, it, ids, by, byname = L
    f = lambda off: struct.unpack_from('<f', d, init_base(d, it, by, off))[0]
    radius, pi, total = f(0xa60), f(0xa68), f(0xa70)
    count = int(total / 2)
    step = pi / (total / 2)
    print('== %s  script %d  %d B' % (src, SID, len(d)))
    print('  m0xa60 radius %.4g  m0xa68 pi %.6g  m0xa70 %.4g  -> count %d, step %.4f rad = %.2f deg' % (
        radius, pi, total, count, step, math.degrees(step)))
    for k, deg, x, y, px, py in positions(count, step, radius):
        side = 'slot %d' % k if k <= count else 'index %d (right half)' % k
        print('  %-22s %7.1f deg  units (%6.2f, %6.2f)  1080p (%4.0f, %4.0f)' % (side, deg, x, y, px, py))
    print('  neighbour distance %.0f px at 1080p' % (2 * radius * PPU * math.sin(step / 2)))
    if variant:
        c2 = int(variant / 2); s2 = pi / c2
        print('  -- variant m0xa70 = %g: count %d, step %.2f deg' % (variant, c2, math.degrees(s2)))
        for k, deg, x, y, px, py in positions(c2, s2, radius)[:c2]:
            print('     slot %d %7.1f deg  1080p (%4.0f, %4.0f)' % (k, deg, px, py))
        print('     neighbour distance %.0f px' % (2 * radius * PPU * math.sin(s2 / 2)))
    print('  hit areas (member -> referenced widgets by name):')
    nhit = 0
    for h in HITS:
        if h not in by:
            continue
        nhit += 1
        b = init_base(d, it, by, h)
        n = struct.unpack_from('<I', d, b)[0]
        p = it.get(b + 4)
        refs = []
        for j in range(n):
            t = it.get(p + 16 * j + 8)
            sym = struct.unpack_from('<H', d, t)[0] if t is not None else None
            refs.append(','.join('0x%x' % o for o in byname.get(sym, [])) or '?%s' % sym)
        print('    0x%03x  n=%2d  %s' % (h, n, ' '.join(refs)))
    print('  slot text widgets (locals id at init +0x5c, position x / y at +0x18 / +0x1c):')
    for t in TEXTS:
        b = init_base(d, it, by, t)
        tid = struct.unpack_from('<I', d, b + 0x5c)[0]
        x, y = struct.unpack_from('<ff', d, b + 0x18)
        print('    0x%03x  text %4d  at (%5.2f, %5.2f)' % (t, tid, x, y))
    print('  slot icons (texture id, id-relocation type 5, at init +0x5c):')
    for t in ICONS:
        b = init_base(d, it, by, t)
        o = b + 0x5c
        print('    0x%03x  id%s:%d  (word +0x%x)' % (t, ids.get(o, '-'), struct.unpack_from('<I', d, o)[0], o))
    ok = abs(total - 14.0) < 1e-4 and nhit == 16 and abs(positions(count, step, radius)[13][3] - radius) < 1e-3
    print('  -> %s' % ('PC layout: 7 slots left, 7 sub positions right, position 14 = bottom' if ok else
                       'layout differs from the finding'))
    return ok


def main(argv):
    variant = None
    if '--variant' in argv:
        k = argv.index('--variant'); variant = float(argv[k + 1]); del argv[k:k + 2]
    if not argv:
        print(__doc__)
        return 2
    ok = True
    for src in argv:
        ok &= report(src, variant)
    print('result: %s' % ('ok' if ok else 'NOT ok'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
