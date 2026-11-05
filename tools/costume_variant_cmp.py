"""Read-only: how the Xbox DLC costumes of one model family differ (night analysis 2026-11-03, costume slots d/g/i/n).

The bikini family b / c / e / j and the tank-top costume o / f come from pack10 (DLC 1). This tool answers whether a
colour variant is defined by other textures, by other material parameters or by both, and derives the colour shift
of the never-built slots d / i / n from the only Xbox data that exists for them: the outfit preview images.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/costume_variant_cmp.py sections dlc_costume_b dlc_costume_c dlc_costume_e dlc_costume_j
      per section type: count, content md5s shared between every pair (ids ignored), meshes / skeleton equal?
  ../bin/pyt -t 900 tools/costume_variant_cmp.py materials dlc_costume_j dlc_costume_b
      pair the materials of A and B by normalised content (id / pointer words zeroed): equal, or the differing
      words (offset, value A, value B, as float when plausible); texture references (kind 5) listed per material
  ../bin/pyt -t 900 tools/costume_variant_cmp.py textures dlc_costume_j dlc_costume_b OUT_DIR
      textures of A that have no byte-equal twin in B and vice versa: id, format, size; PNG of level 0 to OUT_DIR
  ../bin/pyt -t 900 tools/costume_variant_cmp.py mesh dlc_costume_j dlc_costume_b
      object (type 11) and meshes (type 12) paired by order: size, number of differing normalised words
  ../bin/pyt -t 900 tools/costume_variant_cmp.py matdump dlc_costume_j 24275 [START_HEX]
      one material's id references and its parameter words from START (default 0x3c0) as floats (k/255 marked)
  ../bin/pyt -t 300 tools/costume_variant_cmp.py preview j d [b i o n o g ...]
      outfit preview pairs (X Y): mask = pixels whose colour differs by more than 48 in any channel; mean RGB / HSV
      of X and Y inside the mask, mask share, and the per-channel gain Y/X inside the mask
  ../bin/pyt -t 300 tools/costume_variant_cmp.py garment b 200 260 i d e j c
      garment pixels of the REF preview (hue range, saturated): mean colour of every other slot on these pixels
  ../bin/pyt -t 300 tools/costume_variant_cmp.py names pack20 40 85
      English locals.bin strings LO..HI of a pack (pack10 / pack11 / pack1 / pack2 / pack20 / tu / pcbig)
"""
import sys, os, struct, hashlib, colorsys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import drm_write as DW, drm_reloc as R
from convert_dlc import raw_dlc, R as CONTENT, PACKS
from archive import Archive
from names import crc

TYPES = {0: 'general', 2: 'anim', 5: 'texture', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shaderlib', 10: 'material',
         11: 'object', 12: 'mesh'}


def load(name):
    if not name.endswith('.drm'): name += '.drm'
    raw, pk = raw_dlc(name)
    if raw is None: sys.exit('%s not found in %s' % (name, PACKS))
    return DW.read(raw, 'be'), pk


def norm(s):
    """Section data with id-reference and pointer words zeroed (ids / layout positions differ between DRMs)."""
    r = R.parse(s.reloc, 'be'); d = bytearray(s.data)
    for o in list(r.id_offsets()) + r.pointer_offsets():
        if o + 4 <= len(d): d[o:o + 4] = b'\0\0\0\0'
    return bytes(d), r


def md5(b): return hashlib.md5(b).hexdigest()


def cmd_sections(names):
    D = {n: load(n) for n in names}
    sets = {}
    for n, (d, pk) in D.items():
        print('%s  %s  sections %d' % (n, pk.split('/')[1], len(d.sections)))
        per = {}
        for s in d.sections: per.setdefault(s.type, []).append(md5(norm(s)[0]))
        sets[n] = per
        print('   ' + '  '.join('%s %d' % (TYPES.get(t, t), len(v)) for t, v in sorted(per.items())))
    print('\npairwise: per type, normalised content shared (count of A sections whose content occurs in B) / A count')
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            row = []
            for t in sorted(set(sets[a]) | set(sets[b])):
                A = sets[a].get(t, []); B = set(sets[b].get(t, []))
                row.append('%s %d/%d' % (TYPES.get(t, t), sum(x in B for x in A), len(A)))
            print('  %s vs %s: %s' % (a, b, ', '.join(row)))


def cmd_materials(a, b):
    (A, _), (B, _) = load(a), load(b)
    def mats(d):
        out = []
        for s in d.sections:
            if s.type != 10: continue
            nd, r = norm(s)
            tex = [struct.unpack_from('>I', s.data, o)[0] for t, o in sorted(r.idref + r.idref_a, key=lambda e: e[1]) if t == 5]
            out.append((s, nd, tex))
        return out
    ma, mb = mats(A), mats(B)
    hb = {md5(nd): s for s, nd, _ in mb}
    eq = [s.id for s, nd, _ in ma if md5(nd) in hb]
    print('%s materials %d, %s materials %d; normalised byte-equal: %d' % (a, len(ma), b, len(mb), len(eq)))
    # pair the rest by size + position order
    rest_a = [m for m in ma if md5(m[1]) not in hb]
    used = set(md5(m[1]) for m in ma)
    rest_b = [m for m in mb if md5(m[1]) not in used]
    print('unpaired A %d, unpaired B %d (paired below by size, then order)' % (len(rest_a), len(rest_b)))
    pool = list(rest_b)
    for s, nd, tex in rest_a:
        cand = [m for m in pool if len(m[1]) == len(nd)]
        if not cand:
            print('  A %d size %d: no B material of the same size' % (s.id, len(nd))); continue
        best = min(cand, key=lambda m: sum(nd[i:i + 4] != m[1][i:i + 4] for i in range(0, len(nd), 4)))
        pool.remove(best)
        diffs = [i for i in range(0, len(nd), 4) if nd[i:i + 4] != best[1][i:i + 4]]
        print('  A %d <-> B %d size %d: %d words differ; tex A %s / B %s' % (s.id, best[0].id, len(nd), len(diffs), tex, best[2]))
        for i in diffs[:24]:
            va, vb = struct.unpack_from('>I', nd, i)[0], struct.unpack_from('>I', best[1], i)[0]
            fa, fb = struct.unpack_from('>f', nd, i)[0], struct.unpack_from('>f', best[1], i)[0]
            fl = ('  float %.4g / %.4g' % (fa, fb)) if all(1e-6 < abs(x) < 1e6 or x == 0 for x in (fa, fb)) else ''
            print('     +0x%04x  %08x / %08x%s' % (i, va, vb, fl))
    for s, nd, tex in pool: print('  B %d size %d: unpaired' % (s.id, len(nd)))


def cmd_textures(a, b, out):
    import tex_convert as T
    from PIL import Image
    (A, _), (B, _) = load(a), load(b)
    ta = {md5(s.data): s for s in A.sections if s.type == 5}
    tb = {md5(s.data): s for s in B.sections if s.type == 5}
    os.makedirs(out, exist_ok=True)
    for lab, X, Y in ((a, ta, tb), (b, tb, ta)):
        only = [s for h, s in X.items() if h not in Y]
        print('%s: %d textures, %d without byte-equal twin in the other' % (lab, len(X), len(only)))
        for s in sorted(only, key=lambda s: s.id):
            h = T.parse_xbox(s.data)
            line = '  %s tex %d  %s %dx%d mips %d' % (lab, s.id, h['fmtname'], h['w'], h['h'], h['mips'])
            try:
                img = T.pc_image(T.convert(s.data))
                p = os.path.join(out, '%s_%d.png' % (lab, s.id))
                Image.fromarray(np.ascontiguousarray(img[..., :3] if img.ndim == 3 else img)).save(p)
                if img.ndim == 3:
                    m = img[..., :3].reshape(-1, 3).mean(0); line += '  mean ch0-2 %.0f %.0f %.0f' % tuple(m)
            except Exception as e:
                line += '  (no png: %r)' % e
            print(line)


def cmd_matdump(name, ids, start=0x3c0):
    """One material: texture references (offset -> id) and the words from START on as float (x255 when a colour-like
    value k/255) - the MaterialParams constants that hold tints / strengths."""
    d, _ = load(name)
    want = set(int(x) for x in ids.split(','))
    for s in d.sections:
        if s.type != 10 or s.id not in want: continue
        r = R.parse(s.reloc, 'be'); idoff = r.id_offsets(); ptr = set(r.pointer_offsets())
        print('%s material %d: %d B; refs %s' % (name, s.id, len(s.data), ' '.join(
            '+%x:%s%d' % (o, {5: 't', 9: 'sh', 10: 'm'}.get(t, '%d:' % t), struct.unpack_from('>I', s.data, o)[0]) for o, t in sorted(idoff.items()))))
        row = []
        for o in range(start, len(s.data), 4):
            if o in idoff or o in ptr: row.append('+%x:ref' % o); continue
            v = struct.unpack_from('>f', s.data, o)[0]; u = struct.unpack_from('>I', s.data, o)[0]
            if u == 0: continue
            if 1e-6 < abs(v) < 1e6:
                k = v * 255
                row.append('+%x:%.4g%s' % (o, v, ('(=%d/255)' % round(k)) if 0 < k <= 255 and abs(k - round(k)) < 0.02 and v < 1 else ''))
            else: row.append('+%x:%08x' % (o, u))
        for i in range(0, len(row), 8): print('    ' + '  '.join(row[i:i + 8]))


def cmd_mesh(a, b):
    """Pair the meshes (type 12) and the object (type 11) by order: size, differing words, first differing offsets."""
    (A, _), (B, _) = load(a), load(b)
    for t in (11, 12):
        for sa, sb in zip([s for s in A.sections if s.type == t], [s for s in B.sections if s.type == t]):
            na, nb = norm(sa)[0], norm(sb)[0]
            if len(na) != len(nb):
                print('%s %d (%d B) vs %d (%d B): sizes differ' % (TYPES[t], sa.id, len(na), sb.id, len(nb))); continue
            d = [i for i in range(0, len(na), 4) if na[i:i + 4] != nb[i:i + 4]]
            print('%s %d vs %d: %d B, %d of %d words differ; first: %s' % (TYPES[t], sa.id, sb.id, len(na), len(d), len(na) // 4,
                  ' '.join('+%x:%08x/%08x' % (i, struct.unpack_from('>I', na, i)[0], struct.unpack_from('>I', nb, i)[0]) for i in d[:10])))


def preview(slot):
    for p in PACKS:
        a = Archive(CONTENT + p, 'be')
        r = [x for x in a.find(crc('xenon-w\\image\\dlc_outfit_costume_%s.raw' % slot))]
        if r:
            import raw_image_convert as RI
            return RI.decode_xbox(a.read(r[0]))[1].astype(np.float64), p.split('/')[1]
    sys.exit('preview %s not found' % slot)


def cmd_preview(pairs):
    for x, y in zip(pairs[0::2], pairs[1::2]):
        (X, px), (Y, py) = preview(x), preview(y)
        bx, by = X[..., [2, 1, 0]], Y[..., [2, 1, 0]]        # B,G,R,A -> R,G,B
        m = (np.abs(bx - by).max(-1) > 48)
        share = m.mean()
        if not m.any(): print('%s -> %s: no pixel differs by more than 48 (identical look)' % (x, y)); continue
        mx, my = bx[m].mean(0), by[m].mean(0)
        hx, hy = colorsys.rgb_to_hsv(*(mx / 255)), colorsys.rgb_to_hsv(*(my / 255))
        gain = my / np.maximum(mx, 1)
        print('%s (%s) -> %s (%s): mask %.1f %% of %d px; mean RGB %.0f %.0f %.0f -> %.0f %.0f %.0f; '
              'HSV %.0f deg %.2f %.2f -> %.0f deg %.2f %.2f; gain R %.2f G %.2f B %.2f'
              % (x, px, y, py, 100 * share, m.size, *mx, *my, hx[0] * 360, hx[1], hx[2], hy[0] * 360, hy[1], hy[2], *gain))
        # hue histogram of the mask (12 bins), Y side, to see whether the change is one colour or several
        hs = np.array([colorsys.rgb_to_hsv(*(c / 255))[0] for c in by[m][::max(1, m.sum() // 4000)]])
        hist = np.histogram(hs * 360, bins=12, range=(0, 360))[0]
        print('    hue histogram of %s in the mask (30 deg bins from 0): %s' % (y, ' '.join(str(v) for v in hist)))


def rgb_to_hsv(a):
    """(..., 3) floats 0..1 -> (..., 3) hue 0..1, saturation, value (vectorised colorsys)."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1); d = mx - mn; dd = np.where(d == 0, 1, d)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) / 6
    h = np.where(d == 0, 0, h)
    s = np.where(mx == 0, 0, d / np.where(mx == 0, 1, mx))
    return np.stack([h, s, mx], -1)


def cmd_garment(ref, hlo, hhi, others):
    """Garment mask from the REF preview (hue HLO..HHI degrees, saturation > 0.35, value > 0.15): mean RGB of REF and
    of every OTHER slot on exactly these pixels (same model + pose = same garment pixels), the luminance correlation
    REF/OTHER on the mask (shading kept?) and the per-channel gain OTHER/REF."""
    X, _ = preview(ref); rx = X[..., [2, 1, 0]] / 255
    hsv = rgb_to_hsv(rx)
    h = hsv[..., 0] * 360
    hm = (h >= hlo) & (h <= hhi) if hlo <= hhi else ((h >= hlo) | (h <= hhi))
    m = hm & (hsv[..., 1] > 0.35) & (hsv[..., 2] > 0.15)
    print('garment mask from %s, hue %g..%g: %d px' % (ref, hlo, hhi, m.sum()))
    mr = rx[m].mean(0) * 255
    lr = rx[m] @ np.array([0.299, 0.587, 0.114])
    print('  %s mean RGB %.0f %.0f %.0f' % (ref, *mr))
    for o in others:
        Y, _ = preview(o); ry = Y[..., [2, 1, 0]] / 255
        my = ry[m].mean(0) * 255; ly = ry[m] @ np.array([0.299, 0.587, 0.114])
        cor = np.corrcoef(lr, ly)[0, 1]
        hy = rgb_to_hsv(np.array([my / 255]))[0]
        print('  %s mean RGB %.0f %.0f %.0f  (HSV %.0f deg %.2f %.2f)  gain %.2f %.2f %.2f  luminance corr %.2f'
              % (o, *my, hy[0] * 360, hy[1], hy[2], *(my / np.maximum(mr, 1)), cor))


def cmd_names(src, lo, hi):
    """English locals.bin strings LO..HI of a pack (locals.SRC key, or pack20 = Designer pack)."""
    import locals as L
    if src == 'pack20':
        path, e, pre = (L.C + 'AC0089F81B621CD0E0C156B6176EFCC6C844705D53/pack20.000', 'be', 'xenon-w')
    else:
        path, e, pre = L.SRC[src]
    a = Archive(path, e)
    recs = {r['spec']: a.read(r) for r in a.find(crc(pre + '\\local\\locals.bin'))}
    b = recs.get(0xfffff7e1)
    if b is None: sys.exit('no English locals.bin (spec fffff7e1) in %s; specs %s' % (src, [hex(k) for k in recs]))
    lang, st, _ = L.parse(b, e)
    print('%s locals.bin spec fffff7e1: %d strings' % (src, len(st)))
    for i in range(lo, min(hi + 1, len(st))): print('  %4d  %s' % (i, st[i].decode('utf-8', 'replace')))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    c, rest = sys.argv[1], sys.argv[2:]
    if c == 'sections': cmd_sections(rest)
    elif c == 'materials': cmd_materials(rest[0], rest[1])
    elif c == 'textures': cmd_textures(rest[0], rest[1], rest[2])
    elif c == 'preview': cmd_preview(rest)
    elif c == 'mesh': cmd_mesh(rest[0], rest[1])
    elif c == 'names': cmd_names(rest[0], int(rest[1]), int(rest[2]))
    elif c == 'garment': cmd_garment(rest[0], float(rest[1]), float(rest[2]), rest[3:])
    elif c == 'matdump': cmd_matdump(rest[0], rest[1], int(rest[2], 16) if len(rest) > 2 else 0x3c0)
    else: sys.exit(__doc__)
