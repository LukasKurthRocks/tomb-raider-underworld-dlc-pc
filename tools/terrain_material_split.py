"""Split one draw batch (Y record) of a PC terrain section into two materials by triangle orientation (finding 43,
DLC 2 waterfall test 44: the eitr fall column and the pool below it share terrain batch Y 64 / material 24920 in
dlc_level2_start.drm; the fall needs another material without touching the pool).

Terrain layout: tools/terrain_convert.py (H-relative header: offY/nY, offVB, offZ draw-list table, offIdx/nIdx; the
material id list sits behind the internal pointer at section+0x0C). Triangles of the batch whose face normal is
"vertical" (|n . up| < --limit) go to a NEW Y record (copy of the old one) whose material index points at a NEW entry
of a NEW material id list (old ids + the new material id); everything else stays on the old Y record. All new data
is APPENDED at the end of the section (16-byte aligned): the Y array (copied + 1), the material id list (copied + 1),
the index buffer (copied + the regrouped indices of the split draw entries) and the changed draw lists; the header
fields offY / nY / offIdx / nIdx and the draw-list table slots are plain H-relative values, the material list
pointer (section+0x0C) is an internal relocation whose target is moved; one id reference (type 10) is added for the
new list entry (and the old list's references are kept). Old regions stay in place, unused. Every value that is
replaced is checked against the expected old value first.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/terrain_material_split.py report PC.drm SECTION_ID Y_INDEX [--limit 0.5] [--up z]
  ../bin/pyt -t 300 tools/terrain_material_split.py around PC.drm SECTION_ID Y_INDEX   (Y records in the same x/y box)
  ../bin/pyt -t 300 tools/terrain_material_split.py coverage PC.drm SECTION_ID Y_INDEX  (index ranges no entry draws)
  ../bin/pyt -t 300 tools/terrain_material_split.py attrs PC.drm SECTION_ID Y_INDEX     (colour / UV ranges of its vertices)
  ../bin/pyt -t 300 tools/terrain_material_split.py split IN.drm OUT.drm SECTION_ID Y_INDEX NEW_MATERIAL_ID
      [--limit 0.5] [--up z]
  ../bin/pyt -t 300 tools/terrain_material_split.py retarget IN.drm OUT.drm SECTION_ID Y_INDEX NEW_MATERIAL_ID
      (the WHOLE batch to the new material: new material list entry, Y record's material index changed in place)
  NEW_MATERIAL_ID must already exist as a material section (type 10) in IN.drm. report: --be reads an Xbox file.
Test 44 finding: in dlc_level2_start terrain 20085 batch Y 64 (material 24920) is the flat pool only (z = -7468, on
the Xbox too) - the fall column reaches 24920 another way; so the pool gets a copy of the original material
(retarget) and 24920 itself can change. Test 44 played: the column is batch Y 61 (material 24691), which reads the
pool's leftover samplers s2 / s3 (docs/WINDOWS_REBUILD.md finding 43, tests 44b / 44c).
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, terrain_convert as TC

AX = {'x': 0, 'y': 1, 'z': 2}


def opts(argv):
    lim, up = 0.5, 'z'
    if '--limit' in argv: k = argv.index('--limit'); lim = float(argv[k + 1]); del argv[k:k + 2]
    if '--up' in argv: k = argv.index('--up'); up = argv[k + 1]; del argv[k:k + 2]
    return lim, AX[up]


def load(path, sid, e='<'):
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le' if e == '<' else 'be')
    s = next(x for x in D.sections if x.type == 12 and x.id == sid)
    if not TC.is_terrain(s.data): raise SystemExit('section %d is not a terrain section' % sid)
    return raw, D, s


def geometry(d, T, yi, e='<'):
    """positions (float3 at the position element) of the batch's vertex buffer, the index array, the draw entries"""
    H = T['H']; y = T['Y'][yi]
    vdo, _z, nv, vfi = T['vbs'][y[1]]; vf = T['vfs'][vfi]
    pos_off = next(o for sem, o, t, _ in vf['elems'] if t == 2)          # first float3 = position
    P = np.array([struct.unpack_from(e + '3f', d, H + vdo + k * vf['stride'] + pos_off) for k in range(nv)])
    idx = np.frombuffer(d, dtype=e + 'u2', count=T['nIdx'], offset=H + T['offIdx'])
    ents = []                                  # (slot, list_off(abs), entry_no, count, start)
    for slot, seq, lst in TC.draw_lists(d, T, e):
        L = H + struct.unpack_from(e + 'I', d, H + T['offZ'] + 4 * slot)[0]
        for j, (yy, cnt, st) in enumerate(lst):
            if yy == yi: ents.append((slot, L, j, cnt, st))
    return P, idx, ents


def classify(P, tri, lim, up):
    a, b, c = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
    n = np.cross(b - a, c - a); ln = np.linalg.norm(n, axis=1); ln[ln == 0] = 1
    return np.abs(n[:, up] / ln) < lim       # True = vertical face (fall)


def report(argv):
    lim, up = opts(argv)
    e = '>' if '--be' in argv else '<'; argv = [a for a in argv if a != '--be']
    path, sid, yi = argv[0], int(argv[1]), int(argv[2])
    _raw, D, s = load(path, sid, e); d = s.data; T = TC.parse(d, e)
    P, idx, ents = geometry(d, T, yi, e)
    print('section %d Y %d: %d draw entries, vb %d (%d verts), index buffer %d; up axis %s, limit %.2f'
          % (sid, yi, len(ents), T['Y'][yi][1], len(P), T['nIdx'], 'xyz'[up], lim))
    tv = th = 0
    for slot, L, j, cnt, st in ents:
        tri = idx[st:st + cnt].reshape(-1, 3).astype(np.int64)
        v = classify(P, tri, lim, up); nv_, nh = int(v.sum()), int((~v).sum()); tv += nv_; th += nh
        lo, hi = P[tri.ravel()].min(0), P[tri.ravel()].max(0)
        print('  slot %4d entry %d: %5d tris  vertical %5d  other %5d  bbox %s .. %s'
              % (slot, j, cnt // 3, nv_, nh, np.round(lo, 1), np.round(hi, 1)))
    print('total: vertical %d, other %d triangles' % (tv, th))


def around(argv):
    """every Y record with triangles inside the (x, y) box of Y_INDEX's triangles, vertical / other counts and its
    material id - to find the batch that really holds a vertical surface next to a flat one"""
    lim, up = opts(argv)
    path, sid, yi = argv[0], int(argv[1]), int(argv[2])
    _raw, D, s = load(path, sid); d = s.data; T = TC.parse(d, '<'); H = T['H']
    r = R.parse(s.reloc, 'le'); ml = dict(r.internal)[0x0C]
    nm = struct.unpack_from('<I', d, ml)[0]; mats = struct.unpack_from('<%dI' % nm, d, ml + 4)
    P, idx, ents = geometry(d, T, yi)
    pts = np.concatenate([P[idx[st:st + cnt]] for _s, _L, _j, cnt, st in ents])
    lo, hi = pts.min(0), pts.max(0)
    print('box of Y %d: %s .. %s' % (yi, np.round(lo, 1), np.round(hi, 1)))
    for y2 in range(T['nY']):
        P2, idx2, ents2 = geometry(d, T, y2)
        nv_ = nh = 0; zlo, zhi = 1e9, -1e9
        for _s, _L, _j, cnt, st in ents2:
            tri = idx2[st:st + cnt].reshape(-1, 3).astype(np.int64)
            c = P2[tri].mean(1)
            inside = np.all((c[:, :2] >= lo[:2]) & (c[:, :2] <= hi[:2]), axis=1)
            if not inside.any(): continue
            v = classify(P2, tri[inside], lim, up); nv_ += int(v.sum()); nh += int((~v).sum())
            zs = P2[tri[inside].ravel()][:, up]; zlo, zhi = min(zlo, zs.min()), max(zhi, zs.max())
        if nv_ or nh:
            print('  Y %3d material idx %3d id %6d vb %d: vertical %5d other %5d  %s %.0f .. %.0f'
                  % (y2, T['Y'][y2][0], mats[T['Y'][y2][0]] if T['Y'][y2][0] < nm else -1, T['Y'][y2][1],
                     nv_, nh, 'xyz'[up], zlo, zhi))


def coverage(argv):
    """index-buffer coverage: ranges no draw entry references (geometry drawn by another mechanism?), and
    for each uncovered range its vertical / other triangle counts and z span (vertex buffer of Y_INDEX)"""
    lim, up = opts(argv)
    path, sid, yi = argv[0], int(argv[1]), int(argv[2])
    _raw, D, s = load(path, sid); d = s.data; T = TC.parse(d, '<')
    P, idx, _e = geometry(d, T, yi)
    used = np.zeros(T['nIdx'], bool); n = 0
    for _slot, _seq, lst in TC.draw_lists(d, T, '<'):
        for yy, cnt, st in lst: used[st:st + cnt] = True; n += 1
    print('%d draw entries, index buffer %d, covered %d, uncovered %d' % (n, T['nIdx'], used.sum(), (~used).sum()))
    k = 0
    while k < T['nIdx']:
        if used[k]: k += 1; continue
        j = k
        while j < T['nIdx'] and not used[j]: j += 1
        seg = idx[k:j - (j - k) % 3].reshape(-1, 3).astype(np.int64)
        if len(seg) and seg.max() < len(P):
            v = classify(P, seg, lim, up); zs = P[seg.ravel()][:, up]
            print('  uncovered %d..%d (%d tris, vb of Y %d): vertical %d other %d  %s %.0f .. %.0f'
                  % (k, j, len(seg), yi, int(v.sum()), int((~v).sum()), 'xyz'[up], zs.min(), zs.max()))
        else:
            print('  uncovered %d..%d (%d indices, not all < %d)' % (k, j, j - k, len(P)))
        k = j


def attrs(argv):
    """per-vertex attributes of the vertices the batch draws: D3DCOLOR channels and the s16 sets (UVs) as
    histograms / ranges, and the x/y boxes of vertices with high and low colour alpha - to see whether a flat batch
    carries data a vertex shader could use to raise part of it (e.g. a fall extruded from the pool)"""
    path, sid, yi = argv[0], int(argv[1]), int(argv[2])
    _raw, D, s = load(path, sid); d = s.data; T = TC.parse(d, '<'); H = T['H']
    P, idx, ents = geometry(d, T, yi)
    vdo, _z, nv, vfi = T['vbs'][T['Y'][yi][1]]; vf = T['vfs'][vfi]
    used = np.unique(np.concatenate([idx[st:st + cnt] for _s, _L, _j, cnt, st in ents]).astype(np.int64))
    print('Y %d draws %d distinct vertices of vb %d; elements %s' % (yi, len(used), T['Y'][yi][1],
          ' '.join('%08x@%d:t%#x' % (sem, o, t) for sem, o, t, _ in vf['elems'])))
    for sem, o, t, _ in vf['elems']:
        base = H + vdo + o
        if t == 4:
            v = np.array([struct.unpack_from('<I', d, base + k * vf['stride'])[0] for k in used], dtype=np.int64)
            for name, sh in (('A', 24), ('R', 16), ('G', 8), ('B', 0)):
                c = v >> sh & 255
                print('  colour %08x %s: mean %.1f min %d max %d  histogram(8 bins) %s'
                      % (sem, name, c.mean(), c.min(), c.max(), np.histogram(c, bins=8, range=(0, 256))[0].tolist()))
            a = v >> 24 & 255
            for lab, m in (('alpha > 128', a > 128), ('alpha < 32', a < 32)):
                if m.any():
                    q = P[used[m]]
                    print('    %s: %d verts, box %s .. %s' % (lab, m.sum(), np.round(q.min(0), 0), np.round(q.max(0), 0)))
        elif t in (0x13, 0x0A):
            n = 2 if t == 0x13 else 4
            v = np.array([struct.unpack_from('<%dh' % n, d, base + k * vf['stride']) for k in used])
            print('  s16x%d %08x @%d: min %s max %s' % (n, sem, o, v.min(0).tolist(), v.max(0).tolist()))


def retarget(argv):
    src, out, sid, yi, newmat = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4])
    raw, D, s = load(src, sid)
    if not any(x.type == 10 and x.id == newmat for x in D.sections): raise SystemExit('material %d not in %s' % (newmat, src))
    d = bytearray(s.data); r = R.parse(s.reloc, 'le'); T = TC.parse(bytes(d), '<'); H = T['H']
    u = lambda o: struct.unpack_from('<I', d, o)[0]
    ml = dict(r.internal).get(0x0C)
    if ml is None: raise SystemExit('no material list pointer at +0x0C')
    nm = u(ml); mats = list(struct.unpack_from('<%dI' % nm, d, ml + 4))
    if newmat in mats: raise SystemExit('material %d already in the list' % newmat)
    yrec = H + T['offY'] + 32 * yi
    old = u(yrec)
    if old != T['Y'][yi][0] or old >= nm: raise SystemExit('Y %d material index %d unexpected' % (yi, old))
    align16(d); ml2 = len(d)
    d += struct.pack('<I', nm + 1) + struct.pack('<%dI' % nm, *mats) + struct.pack('<I', newmat)
    align16(d)
    struct.pack_into('<I', d, yrec, nm)
    r.internal = [(o, ml2 if o == 0x0C else t) for o, t in r.internal]
    for k in range(nm + 1): r.idref.append((10, ml2 + 4 + 4 * k))
    s.data = bytes(d); s.reloc = R.write(r, 'le')
    bad = R.check(r, len(s.data))
    if bad: raise SystemExit('relocation check failed: %s' % bad[:5])
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(o)
    print('section %d: Y %d material index %d (%d) -> %d (%d); material list %d -> %d entries'
          % (sid, yi, old, mats[old], nm, newmat, nm, nm + 1))


def align16(b):
    while len(b) % 16: b.append(0)


def split(argv):
    lim, up = opts(argv)
    src, out, sid, yi, newmat = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4])
    raw, D, s = load(src, sid)
    if not any(x.type == 10 and x.id == newmat for x in D.sections): raise SystemExit('material %d not in %s' % (newmat, src))
    d = bytearray(s.data); r = R.parse(s.reloc, 'le'); T = TC.parse(bytes(d), '<'); H = T['H']
    u = lambda o: struct.unpack_from('<I', d, o)[0]
    ptr = dict(r.internal)
    if 0x0C not in ptr: raise SystemExit('no material list pointer at +0x0C')
    ml = ptr[0x0C]; nm = u(ml); mats = list(struct.unpack_from('<%dI' % nm, d, ml + 4))
    if newmat in mats: raise SystemExit('material %d already in the list' % newmat)
    P, idx, ents = geometry(bytes(d), T, yi)
    if not ents: raise SystemExit('no draw entries for Y %d' % yi)
    # header words checked before anything is written
    hY, hIdx = H + 0x28, H + 0x50
    assert (u(hY), u(hY + 4)) == (T['offY'], T['nY']) and (u(hIdx), u(hIdx + 4)) == (T['offIdx'], T['nIdx'])
    newy = T['nY']                                   # index of the new Y record
    # 1. Y array copy + new record (material index -> new list entry nm)
    align16(d); offY = len(d) - H
    d += bytes(d[H + T['offY']:H + T['offY'] + 32 * T['nY']])
    rec = bytearray(d[H + T['offY'] + 32 * yi:H + T['offY'] + 32 * yi + 32])
    struct.pack_into('<I', rec, 0, nm); d += rec
    # 2. material id list copy + new id
    align16(d); ml2 = len(d)
    d += struct.pack('<I', nm + 1) + struct.pack('<%dI' % nm, *mats) + struct.pack('<I', newmat)
    # 3. index buffer copy + regrouped indices; 4. draw lists rewritten
    old_idx = bytes(d[H + T['offIdx']:H + T['offIdx'] + 2 * T['nIdx']])
    extra = []; nidx = T['nIdx']; lists = {}
    for slot, L, j, cnt, st in ents:
        tri = idx[st:st + cnt].reshape(-1, 3)
        v = classify(P, tri.astype(np.int64), lim, up)
        lists.setdefault((slot, L), []).append((j, tri[~v], tri[v]))
    newlists = {}
    for (slot, L), parts in lists.items():
        n, seq = struct.unpack_from('<HH', d, L)
        entries = [list(struct.unpack_from('<HHI', d, L + 4 + 8 * k)) for k in range(n)]
        add = []
        for j, pool, fall in parts:
            assert entries[j][0] == yi
            if len(pool):
                entries[j] = [yi, 3 * len(pool), nidx]; extra.append(pool.ravel()); nidx += 3 * len(pool)
            if len(fall):
                add.append([newy, 3 * len(fall), nidx]); extra.append(fall.ravel()); nidx += 3 * len(fall)
                if not len(pool): entries[j] = None
        entries = [e for e in entries if e is not None] + add
        newlists[slot] = (seq, entries)
    if nidx > 0xFFFFFFFF or any(e[1] > 0xFFFF for _s, (_q, es) in newlists.items() for e in es):
        raise SystemExit('index count overflow')
    align16(d); offIdx = len(d) - H
    d += old_idx + np.concatenate(extra).astype('<u2').tobytes()
    if nidx & 1: d += b'\0\0'
    for slot, (seq, entries) in sorted(newlists.items()):
        while len(d) % 32: d.append(0)             # draw lists are 32-byte aligned
        L2 = len(d) - H
        d += struct.pack('<HH', len(entries), seq) + b''.join(struct.pack('<HHI', *e) for e in entries)
        so = H + T['offZ'] + 4 * slot
        assert u(so) and H + u(so) in [L for (sl, L) in lists if sl == slot]
        struct.pack_into('<I', d, so, L2)
    align16(d)
    struct.pack_into('<II', d, hY, offY, T['nY'] + 1)
    struct.pack_into('<II', d, hIdx, offIdx, nidx)
    r.internal = [(o, ml2 if o == 0x0C else t) for o, t in r.internal]
    r.idref.append((10, ml2 + 4 + 4 * nm))
    for k in range(nm): r.idref.append((10, ml2 + 4 + 4 * k))
    s.data = bytes(d); s.reloc = R.write(r, 'le')
    bad = R.check(r, len(s.data))
    if bad: raise SystemExit('relocation check failed: %s' % bad[:5])
    T2 = TC.parse(s.data, '<')
    for _slot, _seq, lst in TC.draw_lists(s.data, T2, '<'):         # every entry in range
        for yy, cnt, st in lst:
            if st + cnt > T2['nIdx'] or yy >= T2['nY']: raise SystemExit('draw entry out of range after split')
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(o)
    moved = sum(len(e) for e in extra) // 3
    print('section %d: Y %d split -> new Y %d (material list entry %d = %d), %d draw lists rewritten, %d triangles '
          'regrouped, index buffer %d -> %d, section %d -> %d bytes' % (sid, yi, newy, nm, newmat, len(newlists),
                                                                       moved, T['nIdx'], nidx, len(raw), len(o)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('report', 'around', 'coverage', 'attrs', 'split', 'retarget'): sys.exit(__doc__)
    {'report': report, 'around': around, 'coverage': coverage, 'attrs': attrs, 'split': split, 'retarget': retarget}[a[0]](a[1:])
