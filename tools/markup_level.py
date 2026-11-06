"""List the unit markup of a level DRM (read-only; DLC 2 rock vein, 607 / 608 ctx 0, 2026-11-01; fixed and extended
2026-11-06 markup / scale, docs/Befund-Markup-Massstab-0611.md).

Classic unit markup: the PC adds it at 0x5d2192 .. 0x5d21c5: `mov esi,[edi+8]` (= the Level struct = section 0 of
the unit DRM), count = [Level+8], records = [Level+0xc], stride 0x5c, add loop 0x5ce4f0 (record +0x28 flags word, 0
in the file -> flags from the type char +0x33 via TRMarkupManager vtable +0x1c (0x5d6f90) | +0x20 (0x5d70a0); +0x2e
id (s16), +0x32 byte (1 = skipped by the queries), +0x58 pointer to the poly line {int count; points at +0x10}).
FIX 2026-11-06: until then the default followed Level+0 (the terrain header, section 1) - its "records" were
TerrainGroups. The default now reads section 0 itself (same as the old `--level 0`).

Markup2 unit markup (NEW 2026-11-06; this is where the Croft Manor units keep their ledges): 0x5d21ca .. 0x5d2217
loops `[[Level+0x74]+0x2c]` items of the pointer list `[[Level+0x74]+0x30]` (unit DTP; the items lie as 0xb0-byte
records behind DTP +0x34, tools/unit_ids.py) and calls 0x5c9da0 per item, which builds a 0x5c MarkUp record
(0x5be650: record +0x2e = item +0x48 u16 id, +0x2c = item +0x4a, +0x32 = item +0x4c kind byte, +0x33 = 0, flags =
GetMUDFlag(item +0x4d type) | class | 8) and a poly line of item +0x9c points (item +0xa0, stride 0x20) transformed by
0x49ba20 (out = x*row0 + y*row1 + z*row2 + row3, rows = item +0x00 / +0x10 / +0x20 / +0x30) plus the unit vector of
[Level-owner+0xd0] vt+0x20 = -origin. So live = M * p - origin(Level+0x80). The box gets +0x24 = item, so the
engine's type getter 0x5be340 reads item +0x4d.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/markup_level.py FILE.drm [--be] [--raw] [--origin X,Y,Z] [--near X,Y,Z [--radius R]]
  --be      big-endian (Xbox) DRM, e.g. work/rockvein/dlc_level2_start_xbox.drm or a pack11 original
  --raw     also print the 23 words of every classic record / the first 0x58 bytes of every markup2 item
  --origin  unit origin for the live frame (default: Level+0x80 from the file)
  --near    live point (TruMenu position frame of this unit): sort markup2 items by the distance of their poly
            line (point-to-segment) to it and print the nearest (all within --radius, default 300)
  Other modes (unchanged): --objects [--xbox X.drm], --object DTP, --level SECTION, --find, --scan, --brute
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

STRIDE = 0x5c
ITEM2 = 0xb0
# markup type -> MUD flag name: PC GetMUDFlag 0x5d6f90 == prototype MarkupManager::GetMUDFlag 0x8211e318 for 0..20,
# names = prototype MUD_Flagnames 0x82843fd0 (entry i = bit 31 - i); 15 (bit 0x10) = MUD_FLAG_PILLAR (prototype
# PrintTestMessage 0x8225fd10); tools/markup_flag_names.py prints the proof. 21 = no move bit; 22 / 23 = TU only.
TYPE_NAME = {0: 'none', 1: 'ledgegrab', 2: 'jumplanding', 3: 'enemydropdown', 4: 'wallvertpole', 5: 'vertpole',
             6: 'horizpole', 7: 'zipline', 8: 'railslide', 9: 'ladder', 10: 'volume', 11: 'rope', 12: 'cover',
             13: 'perch', 14: 'balancebeam', 15: 'pillar', 16: '2hold', 17: '1hold', 18: '4hold', 19: '3holdtopl',
             20: '3holdtopr', 21: 'type21', 22: 'type22 (TU vein)', 23: 'type23 (TU)'}


def tname(t):
    return TYPE_NAME.get(t, 'type %d' % t)


def seg_dist(p, a, b):
    """distance of point p to segment a-b (3D)"""
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    L = sum(v * v for v in ab)
    t = 0.0 if L == 0 else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / L))
    q = [a[i] + t * ab[i] for i in range(3)]
    return sum((p[i] - q[i]) ** 2 for i in range(3)) ** 0.5


def markup2_items(D, rel, f, origin):
    """unit markup2 items: [(index, section, offset, id, aux, kind, type, flags50, live points)] (see docstring)"""
    t = target(D, rel, 0, 0x74)
    if t is None:
        return None, 'Level+0x74 not relocated'
    ds, do = t
    dd = bytes(D.sections[ds].data)
    n = struct.unpack_from(f + 'I', dd, do + 0x2c)[0]
    lst = target(D, rel, ds, do + 0x30)
    out = []
    if not n or lst is None:
        return out, 'unit DTP section %d (id %d): +0x2c = %d, +0x30 -> %s' % (ds, D.sections[ds].id, n, lst)
    for k in range(n):
        it = target(D, rel, lst[0], lst[1] + 4 * k)
        if it is None:
            continue
        si, o = it
        d = bytes(D.sections[si].data)
        M = [struct.unpack_from(f + '4f', d, o + 16 * r) for r in range(4)]
        iid, aux = struct.unpack_from(f + 'HH', d, o + 0x48)
        kind, typ = d[o + 0x4c], struct.unpack_from('b', d, o + 0x4d)[0]
        fl = d[o + 0x50]
        cnt = struct.unpack_from(f + 'i', d, o + 0x9c)[0]
        pp = target(D, rel, si, o + 0xa0)
        pts = []
        if pp and 0 < cnt < 4096:
            pd = bytes(D.sections[pp[0]].data)
            for j in range(cnt):
                x, y, z = struct.unpack_from(f + '3f', pd, pp[1] + 0x20 * j)
                w = [x * M[0][c] + y * M[1][c] + z * M[2][c] + M[3][c] for c in range(3)]
                pts.append(tuple(w[c] - origin[c] for c in range(3)))
        out.append((k, si, o, iid, aux, kind, typ, fl, pts))
    return out, 'unit DTP section %d (id %d): +0x2c = %d items, +0x30 -> section %d +0x%x' % (
        ds, D.sections[ds].id, n, lst[0], lst[1])


def target(D, rel, si, o):
    """(section index, offset) a relocated word at section si offset o points to, or None"""
    r = rel[si]
    if o in r[0]: return si, r[0][o]
    if o in r[1]: return r[1][o]
    return None


def show_markup2(D, rel, f, origin, near, radius, raw):
    items, head = markup2_items(D, rel, f, origin)
    print('markup2 (unit DTP +0x2c / +0x30, live = M * p - origin (%.1f %.1f %.1f)): %s' % (
        origin[0], origin[1], origin[2], head))
    if not items:
        return
    tc = collections.Counter((it[5], it[6]) for it in items)
    print('  kind / type counts: ' + ', '.join('kind %d %s: %d' % (k, tname(t), c) for (k, t), c in sorted(tc.items())))
    rows = []
    for k, si, o, iid, aux, kind, typ, fl, pts in items:
        dist = None
        if near is not None and pts:
            segs = list(zip(pts, pts[1:])) or [(pts[0], pts[0])]
            dist = min(seg_dist(near, a, b) for a, b in segs)
        rows.append((dist, k, si, o, iid, aux, kind, typ, fl, pts))
    if near is not None:
        rows.sort(key=lambda r: (r[0] is None, r[0]))
        print('  nearest to live (%.1f %.1f %.1f), radius %.0f:' % (near[0], near[1], near[2], radius))
    for dist, k, si, o, iid, aux, kind, typ, fl, pts in rows:
        if near is not None and (dist is None or dist > radius) and rows.index((dist, k, si, o, iid, aux, kind, typ,
                                                                                 fl, pts)) >= 3:
            continue
        ends = ' .. '.join('(%.1f %.1f %.1f)' % p for p in (pts[:1] + pts[-1:] if len(pts) > 1 else pts))
        print('  item %3d sec %d +0x%05x id %5d +4a %5d kind %d type %2d %-14s +50 %02x  %2d pts %s%s' % (
            k, si, o, iid, aux, kind, typ, tname(typ), fl, len(pts), ends,
            '' if dist is None else '  dist %.1f' % dist))
        if raw:
            d = bytes(D.sections[si].data)
            print('       ' + ' '.join('%08x' % struct.unpack_from(f + 'I', d, o + q)[0] for q in range(0, 0x58, 4)))


def main(argv):
    be = '--be' in argv
    raw = '--raw' in argv
    find = '--find' in argv
    scan = '--scan' in argv
    brute = '--brute' in argv
    objects = '--objects' in argv
    xbox = None
    if '--xbox' in argv: k = argv.index('--xbox'); xbox = argv[k + 1]; del argv[k:k + 2]
    level = obj = None
    if '--object' in argv: k = argv.index('--object'); obj = int(argv[k + 1]); del argv[k:k + 2]
    if '--level' in argv: k = argv.index('--level'); level = int(argv[k + 1]); del argv[k:k + 2]
    origin = near = None
    radius = 300.0
    if '--origin' in argv:
        k = argv.index('--origin'); origin = tuple(float(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--near' in argv:
        k = argv.index('--near'); near = tuple(float(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--radius' in argv:
        k = argv.index('--radius'); radius = float(argv[k + 1]); del argv[k:k + 2]
    argv = [a for a in argv if not a.startswith('--')]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    rel = []
    for s in D.sections:
        r = R.parse(bytes(s.reloc), e)
        rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
    if objects:                                 # every DTP with an object markup array; with --xbox X.drm compare
        X = XR = None
        if xbox:
            X = DW.read(open(xbox, 'rb').read(), 'be')
            XR = []
            for s in X.sections:
                r = R.parse(bytes(s.reloc), 'be')
                XR.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            if s.type != 7 or len(d) < 0x5c: continue
            t = target(D, rel, si, 0x58)
            n = struct.unpack_from(f + 'I', d, 0x54)[0]
            if t is None or t[0] != si or not 1 <= n <= 1000 or t[1] + n * STRIDE > len(d): continue
            ro = t[1]
            if not all(struct.unpack_from(f + 'I', d, ro + k * STRIDE + 0x28)[0] == 0 for k in range(n)): continue
            tc = collections.Counter(d[ro + k * STRIDE + 0x33] for k in range(n))
            line = 'dtp %d: %d markup records at +0x%x, types %s' % (s.id, n, ro, ', '.join(
                '%d: %d' % kv for kv in sorted(tc.items())))
            if X is not None:
                xi = next((i for i, xs in enumerate(X.sections) if xs.type == 7 and xs.id == s.id), None)
                if xi is None:      # base pairs carry other ids: the Xbox DTP whose +0x54 / +0x58 give the same array
                    for i, xs in enumerate(X.sections):
                        xd = bytes(xs.data)
                        if xs.type != 7 or len(xd) < 0x5c or len(xd) != len(d): continue
                        xt = target(X, XR, i, 0x58)
                        if xt and xt[0] == i and xt[1] == ro and struct.unpack_from('>I', xd, 0x54)[0] == n:
                            xi = i; line += '  (Xbox dtp %d)' % xs.id; break
                if xi is None:
                    line += '  (no Xbox section)'
                else:
                    xd = bytes(X.sections[xi].data)
                    bad = collections.Counter()
                    for k in range(n):
                        o = ro + k * STRIDE
                        for w in range(0, 0x58, 4):
                            xw, pw = xd[o + w:o + w + 4], d[o + w:o + w + 4]
                            if w == 0x2c:   # u16 +0x2c, u16 id +0x2e (read as a word by tru+0x5ce569)
                                good = xw[0:2] == pw[0:2][::-1] and xw[2:4] == pw[2:4][::-1]
                            elif w == 0x30:  # u16 +0x30, byte +0x32 (tested by tru+0x5ce44a), type char +0x33
                                good = xw[0:2] == pw[0:2][::-1] and xw[2:4] == pw[2:4]
                            else:           # floats / dwords
                                good = xw == pw[::-1]
                            if not good: bad['+%x' % w] += 1
                    line += '  Xbox diff words: %s' % (', '.join('%s x%d' % kv for kv in sorted(bad.items())) or 'none')
            print(line)
            if raw or 22 in tc or 23 in tc:
                for k in range(n):
                    o = ro + k * STRIDE
                    if d[o + 0x33] in (22, 23) or raw:
                        print('   #%d +0x%x id %d type %d pos (%.0f %.0f %.0f)' % ((k, o, struct.unpack_from(
                            f + 'h', d, o + 0x2e)[0], d[o + 0x33]) + struct.unpack_from(f + '3f', d, o + 0x34)))
        return
    if brute:                                   # runs of >= 3 records at stride 0x5c: +0x28 == 0, type 1..30, sane position
        def ok(d, r0):
            if r0 < 0 or r0 + STRIDE > len(d): return False
            if struct.unpack_from(f + 'I', d, r0 + 0x28)[0] != 0: return False
            if not 1 <= d[r0 + 0x33] <= 30: return False
            p = struct.unpack_from(f + '3f', d, r0 + 0x34)
            return all(v == v and abs(v) < 1e5 for v in p) and any(abs(v) > 1.0 for v in p)
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            o = 0
            while o + STRIDE <= len(d):
                if ok(d, o) and ok(d, o + STRIDE) and ok(d, o + 2 * STRIDE):
                    n = 0
                    while ok(d, o + n * STRIDE): n += 1
                    tc = collections.Counter(d[o + k * STRIDE + 0x33] for k in range(n))
                    print('section %d type %d id %d: run at +0x%x, %d records, types %s' % (
                        si, s.type, s.id, o, n, ', '.join('%d: %d' % kv for kv in sorted(tc.items()))))
                    o += n * STRIDE
                else:
                    o += 4
        return
    if scan:                                    # records found by their relocated poly-line pointer at +0x58
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            hits = []
            for o in sorted(set(rel[si][0]) | set(rel[si][1])):
                r0 = o - 0x58
                if r0 < 0 or r0 + STRIDE > len(d): continue
                typ = d[r0 + 0x33]
                pos = struct.unpack_from(f + '3f', d, r0 + 0x34)
                if not (1 <= typ <= 40) or not all(abs(v) < 1e6 for v in pos) or pos == (0.0, 0.0, 0.0): continue
                pl = target(D, rel, si, o)
                pd = bytes(D.sections[pl[0]].data)
                if pl[1] + 4 > len(pd): continue
                cnt = struct.unpack_from(f + 'i', pd, pl[1])[0]
                if not (1 <= cnt <= 512): continue
                hits.append((r0, typ, struct.unpack_from(f + 'h', d, r0 + 0x2e)[0], pos, cnt))
            if not hits: continue
            tc = collections.Counter(h[1] for h in hits)
            print('section %d type %d id %d size 0x%x: %d candidate records, types %s' % (
                si, s.type, s.id, len(d), len(hits), ', '.join('%d: %d' % kv for kv in sorted(tc.items()))))
            for r0, typ, rid, pos, cnt in hits:
                if raw or typ in (22, 23):
                    print('   +0x%05x id %5d type %2d pos (%.1f %.1f %.1f) poly %d' % (r0, rid, typ, pos[0], pos[1], pos[2], cnt))
        return
    if find:                                    # sections shaped like the level struct: +8 count, +0xc / +0x20 relocated
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            if len(d) < 0x24: continue
            if target(D, rel, si, 0xc) and target(D, rel, si, 0x20):
                n = struct.unpack_from(f + 'I', d, 8)[0]
                print('section %d type %d id %d size 0x%x: +8 = %d, +0xc -> %s, +0x20 -> %s' % (
                    si, s.type, s.id, len(d), n, target(D, rel, si, 0xc), target(D, rel, si, 0x20)))
        return
    if obj is not None:                         # object markup: count [data+0x54], records [data+0x58] (tru+0x5d0656)
        si = next(i for i, s in enumerate(D.sections) if s.id == obj and s.type == 7)
        n = struct.unpack_from(f + 'I', bytes(D.sections[si].data), 0x54)[0]
        t = target(D, rel, si, 0x58)
        print('object data section %d (dtp %d): +0x54 count %d, +0x58 -> %s' % (si, obj, n, t))
        if t is None: return
        h = None
        rs, ro = t
    elif level is not None:
        h = (level, 0)
    else:
        h = (0, 0)      # FIX 2026-11-06: the Level struct is section 0 itself (0x5d2192 mov esi,[edi+8]), not [section 0 +0]
    if obj is None:
        hs, ho = h
        hd = bytes(D.sections[hs].data)
        words = [struct.unpack_from(f + 'I', hd, ho + 4 * i)[0] for i in range(min(6, (len(hd) - ho) // 4))]
        print('level header: section %d +0x%x, words %s' % (hs, ho, ' '.join('%08x' % w for w in words)))
        for k in range(0, min(len(hd) - ho, 0x18), 4):
            t = target(D, rel, hs, ho + k)
            if t: print('  header +0x%02x -> section %d (type %d id %d, size 0x%x) +0x%x' % (
                k, t[0], D.sections[t[0]].type, D.sections[t[0]].id, len(D.sections[t[0]].data), t[1]))
        n = words[2]
        t = target(D, rel, hs, ho + 0xc)
        if level is None:
            if origin is None:
                origin = struct.unpack_from(f + '3f', hd, 0x80)
            show_markup2(D, rel, f, origin, near, radius, raw)
        if t is None:
            print('classic unit markup: Level+0x08 = %d, Level+0x0c not relocated - none' % n); return
        rs, ro = t
    rd = bytes(D.sections[rs].data)
    print('records: %d x 0x%x at section %d +0x%x (section size 0x%x)' % (n, STRIDE, rs, ro, len(rd)))
    types = collections.Counter()
    for i in range(n):
        o = ro + i * STRIDE
        if o + STRIDE > len(rd):
            print('  record %d past the section end' % i); break
        w28 = struct.unpack_from(f + 'I', rd, o + 0x28)[0]
        rid = struct.unpack_from(f + 'h', rd, o + 0x2e)[0]
        b30 = rd[o + 0x30:o + 0x34]
        pos = struct.unpack_from(f + '3f', rd, o + 0x34)
        typ = struct.unpack_from('b', rd, o + 0x33)[0]
        types[typ] += 1
        pl = target(D, rel, rs, o + 0x58)
        pls = '-'
        if pl:
            pd = bytes(D.sections[pl[0]].data)
            cnt = struct.unpack_from(f + 'i', pd, pl[1])[0]
            pts = []
            for j in (0, cnt - 1) if cnt > 0 else ():
                po = pl[1] + 0x10 + 16 * j
                if po + 12 <= len(pd): pts.append('(%.0f %.0f %.0f)' % struct.unpack_from(f + '3f', pd, po))
            pls = 'poly sec %d +0x%x n %d %s' % (pl[0], pl[1], cnt, ' .. '.join(pts))
        relw = [k for k in range(0, STRIDE, 4) if target(D, rel, rs, o + k)]
        print('  #%3d +0x%05x id %5d type %3d  +28 %08x  +30 %s  pos (%.1f %.1f %.1f)  %s  reloc %s' % (
            i, o, rid, typ, w28, b30.hex(), pos[0], pos[1], pos[2], pls, ','.join('+%x' % k for k in relw)))
        if raw:
            print('       ' + ' '.join('%08x' % struct.unpack_from(f + 'I', rd, o + k)[0] for k in range(0, STRIDE, 4)))
    print('type counts: ' + ', '.join('%d: %d' % kv for kv in sorted(types.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
