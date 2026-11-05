"""Top-down debug map of one unit DRM as a PNG plus a text report (read-only; debug view research 2026-11-05, workspace
docs\\Befund-Debug-Ansicht-0511.md). Draws ONLY what is parsed from the unit's own data; everything else is listed as
unknown in the legend / report.

What is read (layouts with their source):
  * Level = section 0 (tools/unit_ids.level_info): +0x80 unit origin ("live = data - origin", tools/unit_frames.py),
    +0x08 count / +0x0c pointer = the unit markup list, 0x5c-byte records - the PC adds them at tru+0x5d21b4
    (`mov edx,[esi+8]; mov eax,[esi+0xc]; ... call 0x5ce4f0`, string "Adding %d markup items for %s"); record layout
    from tools/markup_fix.py (+0x2e s16 id, +0x32 skip byte, +0x33 type char, +0x34 position, +0x58 poly line
    pointer {int count; points at +0x10 + 16*i}).
    +0x60 / +0x68 = the NavPower NavGraph images handed to bfx AddResource (tru+0x48c42d: `[Level+0x60]`, first
    dword -1, image = +4; tru+0x48c4a1: `[Level+0x68]`, first dword != 0) - the binary format is NOT decoded here:
    only section, offset, size and header words are reported.
  * Intros (0x90 bytes, unit DTP Level+0x74, tools/unit_ids.level_info): +0x00 rotation (x, y, z radians), +0x10
    position, +0x40 scale, +0x50 u16 object id, +0x58 u32 unique id, +0x78 pointer to the intro data (relocated).
  * Trigger volume intro data (IntroDataTrigger, PC tru+0x5cd27a / +0x5cd3dd / +0x5cd42e): +0x30 u8 shape
    (1 = box, half extents +0x34 / +0x38 / +0x3c; 2 = sphere, radius +0x40). Applied only to intros whose object name
    contains "trigger" (the shape byte of other objects means something else).
  * Stream portals (StreamUnitPortal, 0x100 bytes, 6 points at +0x90, tools/unit_start_report.py).
  * Terrain render triangles (tools/unit_frames.terrain_triangles) as a grey footprint.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/unit_debug_map.py UNIT.drm OUT.png [--report OUT.txt] [--size 1800] [--frame live|data]
                                            [--names work/generic/lists/dlc_pack11_objectlist.txt] [--no-terrain]
  --xbox-nav pack11  draw the NavPower areas of the Xbox original (read from that pack, the image is little-endian
                     on both platforms) instead of the PC ones; Xbox areas not found unchanged in the PC image get a
                     red outline (converter damage)
  --frame live (default) subtracts the unit origin Level+0x80 (= the coordinates TruMenu's position overlay shows)
"""
import sys, os, struct, math, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R
import unit_ids as U

STRIDE = 0x5c
KIND = [  # (regex on the object name, label, colour)
    (r'checkpoint', 'checkpoint', (0, 140, 0)),
    (r'generator', 'pool / spawn generator', (200, 0, 200)),
    (r'thrall|yeti|viking|spider|bat_|naga|tiger|panther|shark|enemy_', 'enemy', (220, 30, 30)),
    (r'trigger', 'trigger', (255, 140, 0)),
    (r'watervolume', 'water volume', (0, 120, 220)),
    (r'ping_map|marker', 'map marker', (120, 120, 120)),
]
OTHER = ('other intro', (90, 90, 90))


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def kind(name):
    for rx, lab, col in KIND:
        if re.search(rx, name, re.I): return lab, col
    return OTHER


class Unit:
    def __init__(self, path):
        self.D = DW.read(open(path, 'rb').read(), 'le')
        self.secs = [dict(type=s.type, data=bytes(s.data), reloc=s.reloc, size=len(s.data)) for s in self.D.sections]
        self.rel = []
        for s in self.D.sections:
            r = R.parse(bytes(s.reloc), 'le')
            self.rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
        self.L = U.level_info(self.secs, 'le')

    def target(self, si, o):
        """(section index, offset) a relocated word at section si offset o points to, or None"""
        intl, ext = self.rel[si]
        if o in intl: return si, intl[o]
        if o in ext: return ext[o]
        return None

    def f(self, si, o, n=1):
        return struct.unpack_from('<%df' % n, self.secs[si]['data'], o)

    def u(self, si, o, fmt='I'):
        return struct.unpack_from('<' + fmt, self.secs[si]['data'], o)[0]


def markups(U_):
    out = []
    n = U_.u(0, 8)
    t = U_.target(0, 0xc)
    if t is None or not 0 < n < 20000: return out, n, t
    si, ro = t
    d = U_.secs[si]['data']
    for k in range(n):
        o = ro + k * STRIDE
        if o + STRIDE > len(d): break
        pos = U_.f(si, o + 0x34, 3)
        pl = []
        pt = U_.target(si, o + 0x58)
        if pt is not None:
            psi, po = pt
            cnt = U_.u(psi, po)
            if 0 < cnt < 4096 and po + 0x10 + 16 * cnt <= len(U_.secs[psi]['data']):
                pl = [U_.f(psi, po + 0x10 + 16 * i, 3) for i in range(cnt)]
        out.append(dict(i=k, id=U_.u(si, o + 0x2e, 'h'), type=d[o + 0x33], skip=d[o + 0x32], pos=pos, poly=pl,
                        words=struct.unpack_from('<6f', d, o + 0x40)))
    return out, n, t


def intros(U_, names):
    out = []
    for si, o in U_.L['intros']:
        oid = U_.u(si, o + 0x50, 'H')
        nm = names.get(oid, '?')
        rot = U_.f(si, o + 0x00, 3)
        pos = U_.f(si, o + 0x10, 3)
        it = dict(uid=U_.u(si, o + 0x58), obj=oid, name=nm, pos=pos, rot=rot, scale=U_.f(si, o + 0x40, 3),
                  w52=U_.u(si, o + 0x52, 'H'), w7c=U_.u(si, o + 0x7c), data=None, trig=None)
        dt = U_.target(si, o + 0x78)
        if dt is not None:
            dsi, do = dt
            dd = U_.secs[dsi]['data']
            it['data'] = (dsi, do, struct.unpack_from('<%dI' % min(20, (len(dd) - do) // 4), dd, do))
            if 'trigger' in nm.lower() and do + 0x44 <= len(dd):
                shape = dd[do + 0x30]
                ext = struct.unpack_from('<3f', dd, do + 0x34)
                rad = struct.unpack_from('<f', dd, do + 0x40)[0]
                it['trig'] = dict(shape=shape, ext=ext, radius=rad)
        out.append(it)
    return out


def portals(U_):
    out = []
    for si, o in U_.L['portals']:
        d = U_.secs[si]['data']
        name = d[o:o + 0x80].split(b'\0', 1)[0].decode('latin-1')
        pts = [U_.f(si, o + 0x90 + 0x10 * k, 3) for k in range(6)]
        out.append(dict(name=name, pts=pts))
    return out


def navgraphs(U_):
    out = []
    for off in (0x60, 0x68):
        t = U_.target(0, off)
        if t is None:
            out.append(dict(field=off, target=None)); continue
        si, o = t
        d = U_.secs[si]['data']
        out.append(dict(field=off, target=t, type=U_.secs[si]['type'], size=len(d) - o,
                        head=struct.unpack_from('<%dI' % min(12, (len(d) - o) // 4), d, o)))
    return out


def navareas(U_):
    """Areas of the NavPower image at Level+0x60, read with the record layout seen in the data (tools/navgraph_probe.py
    dumps, 2026-11-05; NOT from NavPower documentation): image header +0x30 = end offset of the area block, +0x48 /
    +0x54 = bounding box min / max (3 floats each); area record = +0x00 centre (3 floats), +0x0c normal (3 floats),
    +0x18 float = distance centre -> farthest corner (checked per record), +0x28 0x7f7fffff, +0x30 dword whose low 7 bits = edge count n, +0x38 n edges of 0x14
    bytes {x, y, z, u32 word +0x0c, u32 word +0x10}. Records are walked from the first one after the header; a word
    that does not fit is skipped (counted as resync)."""
    t = U_.target(0, 0x60)
    if t is None: return None
    si, o = t
    d = U_.secs[si]['data']
    return navareas_bytes(d, o, si)


def xbox_image(unit, pack):
    """the Level+0x60 image bytes of the Xbox original (the NavPower image is little-endian on both platforms:
    base pair l7_yggdrasil_hall02 xbase / pcbig byte-identical, tools/navgraph_probe.py --compare)"""
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode
    path, e, pre = LC.SRC[pack]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + unit + '.drm'))
    if not recs: return None
    X = DW.read(cdrm_decode(A.read(recs[-1]), 'be'), 'be')
    r0 = R.parse(bytes(X.sections[0].reloc), 'be')
    ext = {so: (si, do) for si, so, do in r0.external}
    if 0x60 not in ext: return None
    si, o = ext[0x60]
    return bytes(X.sections[si].data), o


def navareas_bytes(d, o, si=None):
    if len(d) < o + 0x60 or struct.unpack_from('<I', d, o)[0] != 0xffffffff: return None
    end = o + struct.unpack_from('<I', d, o + 0x30)[0]
    lo = struct.unpack_from('<3f', d, o + 0x48)
    hi = struct.unpack_from('<3f', d, o + 0x54)
    inbox = lambda p: all(lo[i] - 1.0 <= p[i] <= hi[i] + 1.0 for i in range(3))
    areas = []
    resync = 0
    skips = []
    p = o + 0x60
    while p + 0x38 <= min(end, len(d)):
        ok = False
        if struct.unpack_from('<I', d, p + 0x28)[0] == 0x7f7fffff:
            n = struct.unpack_from('<I', d, p + 0x30)[0] & 0x7f
            if 3 <= n <= 64 and p + 0x38 + 0x14 * n <= len(d):
                edges = [struct.unpack_from('<3fII', d, p + 0x38 + 0x14 * k) for k in range(n)]
                cen = struct.unpack_from('<3f', d, p)
                rad = struct.unpack_from('<f', d, p + 0x18)[0]
                bad = None
                zs = [e[2] for e in edges]
                if not (min(zs) - 1.0 <= cen[2] <= max(zs) + 1.0) and inbox((cen[0], cen[1], lo[2])):
                    # the centre of a convex area must lie within its corners' z range; a centre z outside it while
                    # x / y fit is kept, flagged with its raw word (data defect lead) and drawn with the mean corner z
                    bad = struct.unpack_from('<I', d, p + 8)[0]
                    cen = (cen[0], cen[1], sum(e[2] for e in edges) / n)
                far = max(math.sqrt(sum((e[i] - cen[i]) ** 2 for i in range(3))) for e in edges)
                # check seen in every hall02 area: +0x18 = distance from the centre to the farthest corner
                tol = 0.5 + (0.03 if bad is not None else 1e-3) * rad
                if inbox(cen) and all(inbox(e[:3]) for e in edges) and abs(far - rad) <= tol:
                    areas.append(dict(off=p - o, centre=cen, cz_raw=bad, normal=struct.unpack_from('<3f', d, p + 0xc),
                                      r=struct.unpack_from('<f', d, p + 0x18)[0],
                                      flags=struct.unpack_from('<I', d, p + 0x30)[0],
                                      w34=struct.unpack_from('<I', d, p + 0x34)[0], edges=edges))
                    p += 0x38 + 0x14 * n
                    ok = True
        if not ok:
            if any(d[p:p + 4]):
                resync += 1
                if not skips or p - o > skips[-1][1] + 4: skips.append([p - o, p - o])
                else: skips[-1][1] = p - o
            p += 4
    return dict(section=si, off=o, end=end - o, lo=lo, hi=hi, areas=areas, resync=resync, skips=skips)


def main(argv):
    rep = opt(argv, '--report', None)
    size = int(opt(argv, '--size', '1800'))
    frame = opt(argv, '--frame', 'live')
    names_path = opt(argv, '--names', 'work/generic/lists/dlc_pack11_objectlist.txt')
    xpack = opt(argv, '--xbox-nav', None)
    no_terrain = '--no-terrain' in argv
    argv = [a for a in argv if a != '--no-terrain']
    if len(argv) < 2:
        print(__doc__)
        return 2
    from PIL import Image, ImageDraw
    import numpy as np
    names = {}
    for l in open(names_path, encoding='utf8', errors='ignore'):
        p = l.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): names[int(p[0])] = p[1]
    un = Unit(argv[0])
    if un.L is None:
        print('not a unit DRM'); return 1
    unit = os.path.basename(argv[0]).rsplit('.', 1)[0]
    origin = un.f(0, 0x80, 3)
    sub = origin if frame == 'live' else (0.0, 0.0, 0.0)
    tx = lambda p: (p[0] - sub[0], p[1] - sub[1], p[2] - sub[2])
    # stream portal points: in hall02 they meet the terrain ends only WITHOUT the origin shift (map 2026-11-05), so
    # they are taken as stored in the live frame already; --frame data adds the origin to them
    add = (0.0, 0.0, 0.0) if frame == 'live' else origin
    ptx = lambda p: (p[0] + add[0], p[1] + add[1], p[2] + add[2])
    mk, mk_n, mk_t = markups(un)
    its = intros(un, names)
    pts = portals(un)
    navs = navgraphs(un)
    nav = navareas(un)
    xnav = None
    if xpack:
        xi = xbox_image(unit, xpack)
        if xi is not None:
            xnav = navareas_bytes(xi[0], xi[1])
            pc_set = {(a['off'], tuple(tuple(round(v, 1) for v in e[:3]) for e in a['edges'])) for a in (nav or {}).get('areas', [])}
            for a in xnav['areas']:
                a['same_on_pc'] = (a['off'], tuple(tuple(round(v, 1) for v in e[:3]) for e in a['edges'])) in pc_set
    tri = None
    if not no_terrain:
        import unit_frames as UF
        tri, mats, skipped = UF.terrain_triangles(un.D)
    lines = []
    P = lines.append
    P('unit %s  (%s)' % (unit, argv[0]))
    P('frame %s: origin Level+0x80 = (%.1f %.1f %.1f)%s' % (frame, origin[0], origin[1], origin[2],
      ', subtracted (live = data - origin)' if frame == 'live' else ', not subtracted'))
    P('markup list Level+0x08 = %d, Level+0x0c -> %s: %d records read' % (mk_n, mk_t, len(mk)))
    tc = collections.Counter(m['type'] for m in mk)
    P('  type chars: %s' % ', '.join('%d: %d' % kv for kv in sorted(tc.items())))
    for m in mk:
        p = tx(m['pos'])
        P('  markup #%-3d id %5d type %3d skip %d pos (%8.1f %8.1f %8.1f) poly %3d  +0x40.. %s' % (
            m['i'], m['id'], m['type'], m['skip'], p[0], p[1], p[2], len(m['poly']),
            ' '.join('%.1f' % w for w in m['words'])))
    P('intros: %d' % len(its))
    for it in its:
        p = tx(it['pos'])
        lab, _ = kind(it['name'])
        P('  intro %6d obj %4d %-44s %-22s pos (%8.1f %8.1f %8.1f) yaw %7.1f deg  +0x52 %5d  +0x7c 0x%x%s' % (
            it['uid'], it['obj'], it['name'], lab, p[0], p[1], p[2], math.degrees(it['rot'][2]), it['w52'],
            it['w7c'], ('  data sec %d +0x%x: %s' % (it['data'][0], it['data'][1], ' '.join('%08x' % w for w in it['data'][2][:12])))
            if it['data'] else ''))
        if it['trig']:
            P('      trigger data: shape %d, half extents %s, radius %.1f' % (
                it['trig']['shape'], ' '.join('%.1f' % e for e in it['trig']['ext']), it['trig']['radius']))
    P('portals: %d' % len(pts))
    for pt in pts:
        c = [sum(q[i] for q in pt['pts']) / 6 for i in range(3)]
        c = ptx(c)
        P('  portal -> %-28s centre (%.0f %.0f %.0f)' % (pt['name'], c[0], c[1], c[2]))
    for nv in navs:
        if nv['target'] is None:
            P('NavPower image Level+0x%02x: no pointer' % nv['field'])
        else:
            P('NavPower image Level+0x%02x -> section %d (type %d) +0x%x, %d bytes to section end; header %s  '
              '(format not decoded)' % (nv['field'], nv['target'][0], nv['type'], nv['target'][1], nv['size'],
                                        ' '.join('%08x' % w for w in nv['head'])))
    if nav is not None:
        ne = sum(len(a['edges']) for a in nav['areas'])
        nz = sum(1 for a in nav['areas'] for e in a['edges'] if e[3])
        P('NavPower areas (layout read from the data, see navareas()): %d areas, %d edges (%d with edge word +0x0c '
          '!= 0), area block image +0x60..+0x%x, %d non-zero words skipped; bbox (%.0f %.0f %.0f)..(%.0f %.0f %.0f)'
          % (len(nav['areas']), ne, nz, nav['end'], nav['resync'], *nav['lo'], *nav['hi']))
        badz = [a for a in nav['areas'] if a['cz_raw'] is not None]
        P('  areas whose centre z word (+0x08) lies outside the z range of its corners: %d%s' % (len(badz), (' - first: ' + ' '.join(
            '+0x%x:%08x(mean corner z %.1f)' % (a['off'], a['cz_raw'], a['centre'][2]) for a in badz[:8])) if badz else ''))
        P('  skipped ranges (image offsets, first 12 of %d): %s' % (len(nav['skips']), ' '.join(
            '+0x%x..+0x%x' % (a, b + 3) for a, b in nav['skips'][:12])))
        P('  area flags (dword +0x30, low 7 bits = edges): %s' % ', '.join(
            '0x%x: %d' % kv for kv in sorted(collections.Counter(a['flags'] for a in nav['areas']).items())))
        for a in nav['areas']:
            c = tx(a['centre'])
            P('  area +0x%05x centre (%8.1f %8.1f %8.1f) normal (%.3f %.3f %.3f) r %.1f flags 0x%08x +0x34 0x%x edges %d: %s' % (
                a['off'], c[0], c[1], c[2], *a['normal'], a['r'], a['flags'], a['w34'], len(a['edges']),
                ' '.join('(%.0f %.0f %.0f %x)' % (*tx(e[:3]), e[3]) for e in a['edges'])))
    if xpack:
        if xnav is None:
            P('Xbox NavPower image (%s): not found' % xpack)
        else:
            P('Xbox NavPower image (%s/%s): %d areas, %d non-zero words skipped; %d of them found unchanged in the PC '
              'image, %d differ or are missing on PC (drawn with a red outline)' % (
                  xpack, unit, len(xnav['areas']), xnav['resync'], sum(a['same_on_pc'] for a in xnav['areas']),
                  sum(not a['same_on_pc'] for a in xnav['areas'])))
    if tri is not None:
        P('terrain: %d render triangles (%d batches skipped)' % (len(tri), skipped))
    # ---- bounds -------------------------------------------------------------------------------------------------
    xs, ys = [], []
    for it in its:
        p = tx(it['pos']); xs.append(p[0]); ys.append(p[1])
    for m in mk:
        p = tx(m['pos']); xs.append(p[0]); ys.append(p[1])
        for q in m['poly']:
            q = tx(q); xs.append(q[0]); ys.append(q[1])
    for pt in pts:
        for q in pt['pts']:
            q = ptx(q); xs.append(q[0]); ys.append(q[1])
    if tri is not None and len(tri):
        T2 = tri[:, :, :2].astype(float) - np.array(sub[:2])
        xs += [float(T2[:, :, 0].min()), float(T2[:, :, 0].max())]
        ys += [float(T2[:, :, 1].min()), float(T2[:, :, 1].max())]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = 0.04 * max(x1 - x0, y1 - y0, 1.0)
    x0 -= pad; x1 += pad; y0 -= pad; y1 += pad
    legend_w = 520
    W = size
    sc = (W - 40) / max(x1 - x0, y1 - y0)
    H = int((y1 - y0) * sc) + 80
    img = Image.new('RGB', (W + legend_w, max(H, 900)), (250, 250, 247))
    dr = ImageDraw.Draw(img, 'RGBA')
    S = lambda x, y: (20 + (x - x0) * sc, 60 + (y1 - y) * sc)       # +x right, +y up (top-down view)
    dr.text((20, 8), '%s  top-down (x right, y up), frame %s, 100 units = 1 m' % (unit, frame), fill=(0, 0, 0))
    # grid every 10 m
    g = 1000.0
    gx = math.floor(x0 / g) * g
    while gx <= x1:
        a = S(gx, y0); b = S(gx, y1)
        dr.line([a, b], fill=(225, 225, 225)); dr.text((a[0] + 2, a[1] - 12), '%d' % gx, fill=(170, 170, 170))
        gx += g
    gy = math.floor(y0 / g) * g
    while gy <= y1:
        a = S(x0, gy); b = S(x1, gy)
        dr.line([a, b], fill=(225, 225, 225)); dr.text((a[0] + 2, a[1] + 1), '%d' % gy, fill=(170, 170, 170))
        gy += g
    if tri is not None and len(tri):
        for t in T2:
            dr.polygon([S(t[0][0], t[0][1]), S(t[1][0], t[1][1]), S(t[2][0], t[2][1])], fill=(150, 150, 150, 40))
    if xnav is not None:          # the Xbox original's areas; red outline = not found unchanged in the PC image
        for a in xnav['areas']:
            q = [S(*tx(e[:3])[:2]) for e in a['edges']]
            dr.polygon(q, fill=(60, 200, 90, 60), outline=(0, 110, 40) if a['same_on_pc'] else (230, 0, 0))
            if not a['same_on_pc']:
                dr.line(q + [q[0]], fill=(230, 0, 0), width=3)
    elif nav is not None:
        for a in nav['areas']:
            q = [S(*tx(e[:3])[:2]) for e in a['edges']]
            dr.polygon(q, fill=(60, 200, 90, 60) if a['cz_raw'] is None else (255, 60, 60, 90))
            for k in range(len(q)):
                e = a['edges'][k]
                dr.line([q[k], q[(k + 1) % len(q)]], fill=(0, 110, 40) if e[3] == 0 else (140, 220, 160), width=2 if e[3] == 0 else 1)
    for pt in pts:
        poly = [S(*ptx(q)[:2]) for q in pt['pts']]
        dr.line(poly + [poly[0]], fill=(0, 160, 160), width=4)
        c = [sum(q[i] for q in poly) / len(poly) for i in range(2)]
        dr.text((c[0] + 6, c[1] - 14), 'portal -> %s' % pt['name'], fill=(0, 120, 120))
    for m in mk:
        p = tx(m['pos'])
        if m['poly']:
            dr.line([S(*tx(q)[:2]) for q in m['poly']], fill=(30, 90, 255), width=2)
        a = S(p[0], p[1])
        dr.rectangle([a[0] - 3, a[1] - 3, a[0] + 3, a[1] + 3], outline=(30, 90, 255))
        dr.text((a[0] + 4, a[1] + 2), 'mk %d t%d' % (m['id'], m['type']), fill=(30, 90, 255))
    for it in its:
        p = tx(it['pos'])
        lab, col = kind(it['name'])
        a = S(p[0], p[1])
        if it['trig'] and it['trig']['shape'] == 2 and 0 < it['trig']['radius'] < 1e5:
            r = it['trig']['radius'] * sc
            dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], outline=col, width=2)
        elif it['trig'] and it['trig']['shape'] == 1 and all(0 < e < 1e5 for e in it['trig']['ext']):
            ex, ey = it['trig']['ext'][0], it['trig']['ext'][1]
            yaw = it['rot'][2]
            cs, sn = math.cos(yaw), math.sin(yaw)
            corners = [(p[0] + cs * dx - sn * dy, p[1] + sn * dx + cs * dy) for dx, dy in
                       ((-ex, -ey), (ex, -ey), (ex, ey), (-ex, ey))]
            q = [S(*c) for c in corners]
            dr.line(q + [q[0]], fill=col, width=2)
        r = 7 if lab in ('enemy', 'pool / spawn generator', 'checkpoint') else 4
        if lab == 'checkpoint':
            dr.polygon([(a[0], a[1] - r), (a[0] + r, a[1]), (a[0], a[1] + r), (a[0] - r, a[1])], fill=col)
        elif lab == 'pool / spawn generator':
            dr.rectangle([a[0] - r, a[1] - r, a[0] + r, a[1] + r], outline=col, width=3)
        else:
            dr.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=col)
        if lab != 'map marker':
            dr.text((a[0] + r + 3, a[1] - 6), '%d %s (z %.0f, yaw %.0f)' % (it['uid'], it['name'], p[2],
                                                                          math.degrees(it['rot'][2])), fill=col)
    # ---- legend --------------------------------------------------------------------------------------------------
    lx = W + 10
    ly = 20
    dr.rectangle([W, 0, W + legend_w, img.size[1]], fill=(240, 240, 236))

    def say(t, c=(0, 0, 0)):
        nonlocal ly
        dr.text((lx, ly), t, fill=c); ly += 15
    say('Legend (only parsed data)', (0, 0, 0)); ly += 5
    say('diamond  checkpoint intro', KIND[0][2])
    say('square   pool / spawn generator intro', KIND[1][2])
    say('dot      enemy intro (start position)', KIND[2][2])
    say('outline  trigger volume (IntroDataTrigger)', KIND[3][2])
    say('dot      water volume intro (no extents parsed)', KIND[4][2])
    say('small    map marker / other intro', OTHER[1])
    say('blue     unit markup record (pos + poly line)', (30, 90, 255))
    say('teal     stream portal (6 points, stored frame: see report)', (0, 160, 160))
    say('grey     terrain render triangles (footprint)', (120, 120, 120))
    say('green    NavPower area (polygon from Level+0x60 image;', (0, 110, 40))
    say('         dark edge: edge word +0x0c = 0, light: != 0;', (0, 110, 40))
    say('         record layout read from the data, unverified)', (0, 110, 40))
    say('red fill NavPower area whose centre z word is outside', (200, 30, 30))
    say('         its corners z range (converter defect, report;', (200, 30, 30))
    say('         tools/navgraph_probe.py --compare)', (200, 30, 30))
    ly += 8
    say('Labels: intro unique id, object name, z, yaw (Intro +0x08).')
    say('Facing arrows not drawn: forward axis of the yaw is')
    say('not verified for TR8 instances.')
    ly += 8
    say('Counts: %d intros, %d markup records, %d portals' % (len(its), len(mk), len(pts)))
    for nv in navs:
        if nv['target'] is None: say('NavGraph Level+0x%02x: none' % nv['field'])
        else: say('NavGraph Level+0x%02x: %d bytes' % (nv['field'], nv['size']))
    if nav is not None:
        say('NavPower areas drawn: %d (%d words skipped)' % (len(nav['areas']), nav['resync']), (0, 110, 40))
    ly += 8
    say('NOT in this map (unknown / runtime only):', (160, 0, 0))
    for t in ('- NavPower data after the area block (links, grid;',
              '  live: NavPower draw flag planner_areas 0x8bf2e5)',
              '- enemy perception / attack radii (field meaning',
              '  unknown, see Befund-Finisher-Thralls 2.3)',
              '- AI paths, targeter lists, AI state (runtime)',
              '- object-attached markup (needs instance transform)',
              '- spawned instances of the pool generators'):
        say(t, (120, 0, 0))
    os.makedirs(os.path.dirname(os.path.abspath(argv[1])), exist_ok=True)
    img.save(argv[1])
    P('png: %s (%dx%d)' % (argv[1], img.size[0], img.size[1]))
    txt = '\n'.join(lines) + '\n'
    print(txt, end='')
    if rep:
        with open(rep, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
