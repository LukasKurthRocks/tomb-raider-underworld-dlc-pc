"""Top-down overlay of two (or more) stream units in ONE frame as a PNG plus a text report (read-only; 2026-11-06
markup / scale, docs/Befund-Markup-Massstab-0611.md). Built for "where does the cutscene facade set
l3_mansion_exterior_afterburn sit relative to the walkable l3_main_hall".

Frame: the live frame of the FIRST unit (the one Lara stands in): live = data - Level+0x80 of that unit
(docs/Befund-Position-und-Schrotflinte.md). Every further unit is placed like the engine places a neighbour
(0x5d14fe / 0x5d166c: offset = portal +0x90 of the own record - portal +0x90 of the matching record): its own live
frame (data - its Level+0x80) plus P = (portal points in unit A) - (matching portal points in unit B). Portal points
are stored in the unit's own live frame (StreamUnitPortal +0x90, 6 points of 16 bytes; tools/unit_debug_map.py).
Both records hold the same 6 corner points in a different order: offset = centroid difference; the report gives
the largest corner mismatch after the shift (0 = one rigid offset). Only portal neighbours of a placed unit are placed.

Drawn per unit (own colour): terrain render triangles (footprint, tools/unit_frames.terrain_triangles), trigger
volumes (IntroDataTrigger box, all 12 edges of the rotated box seen from above; rotation order x, y, z ASSUMED -
see box_corners), checkpoints, player / cinematic intros, markup2 ledges (tools/markup_level.markup2_items), portals.
--mark UID[,UID..] draws those intros big with a label; --clip X0,Y0,X1,Y1 limits the picture to that frame window.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/unit_overlay_map.py OUT.png UNIT_A.drm UNIT_B.drm [UNIT_C.drm ..] [--report OUT.txt]
        [--mark 4128,4129] [--size 2000] [--names work/generic/lists/pc_objectlist.txt]
        [--point X,Y,Z,LABEL]   (a live point of unit A, e.g. Lara; repeatable)   [--clip X0,Y0,X1,Y1]
"""
import sys, os, struct, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unit_debug_map as UDM
import markup_level as ML

COLS = [(200, 70, 20), (20, 90, 200), (20, 150, 60), (150, 40, 160)]
TERR = [(230, 140, 90, 38), (90, 140, 230, 38), (90, 200, 120, 38), (190, 120, 200, 38)]


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name); v = argv[i + 1]; del argv[i:i + 2]; return v
    return default


def opts(argv, name):
    out = []
    while name in argv:
        i = argv.index(name); out.append(argv[i + 1]); del argv[i:i + 2]
    return out


def unit_name(path):
    return os.path.basename(path).rsplit('.', 1)[0].lower()


BOX_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def box_corners(c, ext, rot):
    """8 corners of a box with half extents ext rotated by the intro rotation (x, y, z radians), ASSUMED order:
    x first, then y, then z (R = Rz * Ry * Rx). For a centred box the top-view footprint does not depend on the
    order when only one axis is non-zero or the z angle is 0 / 180 degrees (the case for 4128 / 4129)."""
    rx, ry, rz = rot
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    out = []
    for dz in (-ext[2], ext[2]):
        for dy in (-ext[1], ext[1]):
            for dx in (-ext[0], ext[0]):
                x, y, z = dx, dy * cx - dz * sx, dy * sx + dz * cx            # Rx
                x, z = x * cy + z * sy, -x * sy + z * cy                       # Ry
                x, y = x * cz - y * sz, x * sz + y * cz                        # Rz
                out.append((c[0] + x, c[1] + y, c[2] + z))
    return out


def euler_note(rot):
    return 'rot (%.1f %.1f %.1f) deg' % tuple(math.degrees(r) for r in rot)


def main(argv):
    rep = opt(argv, '--report', None)
    size = int(opt(argv, '--size', '2000'))
    names_path = opt(argv, '--names', 'work/generic/lists/pc_objectlist.txt')
    marks = set(int(v) for v in opt(argv, '--mark', '').split(',') if v)
    points = []
    clip = opt(argv, "--clip", None)
    for p in opts(argv, '--point'):
        a = p.split(',')
        points.append((float(a[0]), float(a[1]), float(a[2]), ','.join(a[3:]) or 'point'))
    if len(argv) < 3:
        print(__doc__); return 2
    out_png, paths = argv[0], argv[1:]
    from PIL import Image, ImageDraw
    import numpy as np
    import unit_frames as UF
    names = {}
    for l in open(names_path, encoding='utf8', errors='ignore'):
        p = l.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): names[int(p[0])] = p[1]
    lines = []
    P = lines.append
    units = []
    for k, path in enumerate(paths):
        un = UDM.Unit(path)
        if un.L is None:
            print('%s: not a unit DRM' % path); return 1
        units.append(dict(path=path, name=unit_name(path), un=un, origin=un.f(0, 0x80, 3), col=COLS[k % 4],
                          terr=TERR[k % 4], P=None, via=None))
    units[0]['P'] = (0.0, 0.0, 0.0)
    units[0]['via'] = 'reference frame'
    # place the others through matched portals (own record +0x80 = id of the matching record in the destination)
    changed = True
    while changed:
        changed = False
        for A in units:
            if A['P'] is None: continue
            for pa in UDM.portals(A['un']):
                tgt = pa['name'].split('\\')[-1].lower()
                for B in units:
                    if B['P'] is not None or B['name'] != tgt: continue
                    da = A['un'].secs[0]['data']
                    # portal record ids: +0x80 to, +0x82 own (tools/unit_frames.py); find B's record whose own == A's to
                    rec_a = [(si, o) for si, o in A['un'].L['portals']
                             if A['un'].secs[si]['data'][o:o + 0x80].split(b'\0', 1)[0].decode('latin-1') == pa['name']][0]
                    to_id = struct.unpack_from('<H', A['un'].secs[rec_a[0]]['data'], rec_a[1] + 0x80)[0]
                    pb = None
                    for si, o in B['un'].L['portals']:
                        if struct.unpack_from('<H', B['un'].secs[si]['data'], o + 0x82)[0] == to_id:
                            pb = [B['un'].f(si, o + 0x90 + 0x10 * q, 3) for q in range(6)]
                    if pb is None: continue
                    # both records hold the same 6 corner points (two triangles) in a different order: offset =
                    # centroid difference, check = the sorted point sets match after the shift
                    off = tuple(sum(q[i] for q in pa['pts']) / 6 - sum(q[i] for q in pb) / 6 for i in range(3))
                    sa = sorted(tuple(q) for q in pa['pts'])
                    sb = sorted(tuple(q[i] + off[i] for i in range(3)) for q in pb)
                    spread = max(abs(a[i] - b[i]) for a, b in zip(sa, sb) for i in range(3))
                    B['P'] = tuple(A['P'][i] + off[i] for i in range(3))
                    B['via'] = ('portal %s -> %s (to id %d): centroid offset, max corner mismatch after the shift %.2f '
                                'units (sorted 6-point sets)' % (A['name'], B['name'], to_id, spread))
                    changed = True
    P('overlay frame = live frame of %s (data - Level+0x80 (%.1f %.1f %.1f))' % (
        units[0]['name'], *units[0]['origin']))
    for U in units:
        if U['P'] is None:
            P('unit %s: NOT placed (no portal path from the reference unit among the given files)' % U['name'])
        else:
            P('unit %s: origin Level+0x80 (%.1f %.1f %.1f), placement P (%.1f %.1f %.1f) - %s' % (
                U['name'], *U['origin'], *U['P'], U['via']))
    placed = [U for U in units if U['P'] is not None]

    def to_frame(U, live_own):
        return tuple(live_own[i] + U['P'][i] for i in range(3))

    def data_to_frame(U, data):
        return tuple(data[i] - U['origin'][i] + U['P'][i] for i in range(3))

    xs, ys = [], []
    for U in placed:
        un = U['un']
        U['its'] = UDM.intros(un, names)
        U['pts'] = UDM.portals(un)
        U['mk2'], head = ML.markup2_items(un.D, un.rel, '<', U['origin'])
        P('  %s: %d intros, %d portals, markup2: %s' % (U['name'], len(U['its']), len(U['pts']), head))
        tri, mats, skipped = UF.terrain_triangles(un.D)
        T = tri.astype(float) - np.array(U['origin']) + np.array(U['P']) if tri is not None and len(tri) else None
        U['tri'] = T
        if T is not None:
            P('  %s terrain: %d triangles, frame bbox x %.0f..%.0f y %.0f..%.0f z %.0f..%.0f' % (
                U['name'], len(T), T[:, :, 0].min(), T[:, :, 0].max(), T[:, :, 1].min(), T[:, :, 1].max(),
                T[:, :, 2].min(), T[:, :, 2].max()))
            xs += [float(T[:, :, 0].min()), float(T[:, :, 0].max())]
            ys += [float(T[:, :, 1].min()), float(T[:, :, 1].max())]
        for it in U['its']:
            p = data_to_frame(U, it['pos']); xs.append(p[0]); ys.append(p[1])
    for x, y, z, lab in points:
        xs.append(x); ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if clip:
        x0, y0, x1, y1 = (float(v) for v in clip.split(","))
    pad = 0.04 * max(x1 - x0, y1 - y0, 1.0)
    x0 -= pad; x1 += pad; y0 -= pad; y1 += pad
    legend_w = 560
    W = size
    sc = (W - 40) / max(x1 - x0, y1 - y0)
    H = int((y1 - y0) * sc) + 90
    img = Image.new('RGB', (W + legend_w, max(H, 1000)), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    S = lambda x, y: (20 + (x - x0) * sc, 70 + (y1 - y) * sc)
    dr.text((20, 8), 'top-down overlay (x right, y up), frame = live frame of %s; grid 1000 units' % units[0]['name'],
            fill=(0, 0, 0))
    dr.text((20, 24), 'units: ' + ', '.join('%s (P %.0f %.0f %.0f)' % (U['name'], *U['P']) for U in placed),
            fill=(0, 0, 0))
    g = 1000.0
    gx = math.floor(x0 / g) * g
    while gx <= x1:
        a = S(gx, y0); b = S(gx, y1)
        dr.line([a, b], fill=(228, 228, 228)); dr.text((a[0] + 2, a[1] - 12), '%d' % gx, fill=(165, 165, 165))
        gx += g
    gy = math.floor(y0 / g) * g
    while gy <= y1:
        a = S(x0, gy); b = S(x1, gy)
        dr.line([a, b], fill=(228, 228, 228)); dr.text((a[0] + 2, a[1] + 1), '%d' % gy, fill=(165, 165, 165))
        gy += g
    for U in placed:
        if U['tri'] is not None:
            for t in U['tri']:
                dr.polygon([S(t[0][0], t[0][1]), S(t[1][0], t[1][1]), S(t[2][0], t[2][1])], fill=U['terr'])
    report = collections.defaultdict(list)
    for U in placed:
        col = U['col']
        for k, si, o, iid, aux, kind, typ, fl, pts in U['mk2']:
            if len(pts) >= 2:
                q = [S(*to_frame(U, p)[:2]) for p in pts]
                dr.line(q, fill=(0, 0, 0, 200), width=3)
                dr.line(q, fill=(255, 220, 40, 255), width=1)
        for pt in U['pts']:
            poly = [S(*to_frame(U, q)[:2]) for q in pt['pts']]
            dr.line(poly + [poly[0]], fill=(0, 160, 160), width=5)
            c = [sum(q[i] for q in poly) / len(poly) for i in range(2)]
            dr.text((c[0] + 8, c[1] - 14), '[%s] portal -> %s' % (U['name'].replace('l3_', ''), pt['name'].split('\\')[-1]),
                    fill=(0, 120, 120))
            cf = [sum(to_frame(U, q)[i] for q in pt['pts']) / 6 for i in range(3)]
            zs = [to_frame(U, q)[2] for q in pt['pts']]
            report[U['name']].append('portal -> %s: centre (%.0f %.0f %.0f), z %.0f..%.0f' % (
                pt['name'], cf[0], cf[1], cf[2], min(zs), max(zs)))
        for it in U['its']:
            p = data_to_frame(U, it['pos'])
            lab, kcol = UDM.kind(it['name'])
            big = it['uid'] in marks
            if not (big or lab in ('checkpoint', 'trigger') or it['name'] in ('player', 'cinematic_object')):
                continue
            a = S(p[0], p[1])
            if it['trig'] and it['trig']['shape'] == 1 and all(0 <= e < 1e5 for e in it['trig']['ext']) \
                    and any(it['trig']['ext']):
                corners = box_corners(p, it['trig']['ext'], it['rot'])
                for a_, b_ in BOX_EDGES:
                    dr.line([S(*corners[a_][:2]), S(*corners[b_][:2])], fill=(255, 0, 160) if big else col + (150,),
                            width=4 if big else 1)
            elif it['trig'] and it['trig']['shape'] == 2 and 0 < it['trig']['radius'] < 1e5:
                r = it['trig']['radius'] * sc
                dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], outline=col + (150,), width=1)
            r = 9 if big else (6 if lab == 'checkpoint' else 3)
            fill = (255, 0, 160) if big else (KIND_CP if lab == 'checkpoint' else col)
            if lab == 'checkpoint':
                dr.polygon([(a[0], a[1] - r), (a[0] + r, a[1]), (a[0], a[1] + r), (a[0] - r, a[1])], fill=fill,
                           outline=col)
            else:
                dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=fill, outline=col)
            if big or lab == 'checkpoint' or it['name'] in ('player', 'cinematic_object'):
                txt = '%d %s z %.0f' % (it['uid'], it['name'], p[2])
                if it['name'] == 'cinematic_object': txt += ' (+0x52 %d)' % it['w52']
                dr.text((a[0] + r + 3, a[1] - 6), txt, fill=(150, 0, 100) if big else col)
            if big or lab == 'checkpoint' or it['name'] in ('player', 'cinematic_object'):
                extra = ''
                if it['trig']:
                    extra = ', shape %d half extents %s, %s' % (it['trig']['shape'], ' '.join(
                        '%.0f' % e for e in it['trig']['ext']), euler_note(it['rot']))
                report[U['name']].append('intro %d %s (+0x52 %d): frame (%.1f %.1f %.1f)%s' % (
                    it['uid'], it['name'], it['w52'], p[0], p[1], p[2], extra))
    for x, y, z, lab in points:
        a = S(x, y)
        dr.line([a[0] - 10, a[1], a[0] + 10, a[1]], fill=(0, 0, 0), width=2)
        dr.line([a[0], a[1] - 10, a[0], a[1] + 10], fill=(0, 0, 0), width=2)
        dr.text((a[0] + 12, a[1] + 2), '%s z %.0f' % (lab, z), fill=(0, 0, 0))
        report['points'].append('%s: (%.1f %.1f %.1f)' % (lab, x, y, z))
    lx, ly = W + 10, 20
    dr.rectangle([W, 0, W + legend_w, img.size[1]], fill=(240, 240, 236))

    def say(t, c=(0, 0, 0)):
        nonlocal ly
        dr.text((lx, ly), t, fill=c); ly += 15
    say('Legend (parsed data only)'); ly += 4
    for U in placed:
        say('%-34s terrain fill + outlines' % U['name'], U['col'])
    say('magenta  marked intros (--mark), thick = trigger box', (200, 0, 130))
    say('         (12 edges of the rotated box, top view)', (200, 0, 130))
    say('diamond  checkpoint, dot player / cinematic intro', (60, 60, 60))
    say('thin box other trigger volumes / planes (rotated)', (60, 60, 60))
    say('teal     stream portal quad (both sides drawn)', (0, 140, 140))
    say('yellow   markup2 ledge / climb poly line', (160, 130, 0))
    say('cross    --point (live point of the reference unit)', (0, 0, 0))
    ly += 8
    say('Frame: live of %s; other units placed by the' % units[0]['name'])
    say('matched portal pair (engine neighbour placement).')
    say('z is not shown by the picture - see the labels / report.')
    ly += 8
    say('NOT drawn: object markup, sound volumes,', (140, 0, 0))
    say('NavPower, other non-trigger intros.', (140, 0, 0))
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    img.save(out_png)
    for name, rows in report.items():
        P('== %s' % name)
        for r in rows: P('  ' + r)
    P('png: %s (%dx%d)' % (out_png, img.size[0], img.size[1]))
    txt = '\n'.join(lines) + '\n'
    print(txt, end='')
    if rep:
        with open(rep, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt)
    return 0


KIND_CP = (0, 140, 0)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
