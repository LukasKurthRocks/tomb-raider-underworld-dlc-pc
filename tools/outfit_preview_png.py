"""Outfit preview images of the 16 costume slots (image\\dlc_outfit_costume_a..p.raw) from the Xbox DLC packs -> PNG,
read-only on the packs. Test 50k (cut content, costume slots d / g / i / n that never got a costume DRM).

Format: the '!WAR' image of tools/raw_image_convert.py (128-byte header of 32 u32 in platform byte order: [3] format
3 = Xbox 2D tiled / 13 = linear rows padded to 64 pixels, [5] width, [6] height, [8] bpp 32; pixels A8R8G8B8). The
decoder is raw_image_convert.decode_xbox (proven byte-exact on the base-game Xbox / PC image pairs, its `selftest`).
Proof per image here: the PC file made from the Xbox record (raw_image_convert.xbox_to_pc) is compared by md5 with
the PC file of the B138 kit manifest (`rel` image/dlc_outfit_costume_X.raw) and the manifest's Xbox source md5 with
the pack record.

Per slot it also measures what can tell a recolour from a new model: the alpha silhouette (IoU against every other
slot), the luminance-gradient correlation inside the common silhouette (shape / folds independent of colour) and the
mean hue / saturation / value of the opaque pixels.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/outfit_preview_png.py OUT_DIR [--packs DIR] [--manifest docs/data/B138.kit_manifest.json]
  --packs: folder with the final Xbox DLC content folders (default ../input/xbox-dlc); every */pack*.000 is searched
Writes OUT_DIR/dlc_outfit_costume_X.png (one per slot; the largest record when packs differ), OUT_DIR/Uebersicht.png
(all slots, labelled) and prints a table (slot, pack(s), size, header, md5s, proof, colour stats) plus the
similarity matrix.
"""
import sys, os, glob, json, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import raw_image_convert as RI
from archive import Archive
from names import crc

SLOTS = 'abcdefghijklmnop'


def records(packs_dir):
    """{slot: [(pack name, xbox bytes)]} for every outfit record found"""
    out = {}
    for p in sorted(glob.glob(os.path.join(packs_dir, '*', 'pack*.000'))):
        a = Archive(p, 'be')
        for s in SLOTS:
            for r in a.find(crc('xenon-w\\image\\dlc_outfit_costume_%s.raw' % s)):
                if r['spec'] != 0xffffffff: continue
                out.setdefault(s, []).append((os.path.basename(p), a.read(r)))
    return out


def hsv_stats(rgba):
    """mean hue (deg, circular), saturation, value of the opaque pixels"""
    m = rgba[..., 3] > 128
    c = rgba[..., :3][m].astype(np.float64) / 255.0
    if len(c) == 0: return None
    mx = c.max(1); mn = c.min(1); d = mx - mn
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    h = np.zeros(len(c))
    k = d > 1e-6
    rr = k & (mx == r); gg = k & (mx == g) & ~rr; bb = k & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = (b - r)[gg] / d[gg] + 2
    h[bb] = (r - g)[bb] / d[bb] + 4
    h *= 60.0
    sat = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    w = sat * k                                  # weight hue by saturation (grey pixels have no hue)
    ang = np.deg2rad(h)
    mh = np.rad2deg(np.arctan2((np.sin(ang) * w).sum(), (np.cos(ang) * w).sum())) % 360 if w.sum() > 0 else 0.0
    return dict(hue=mh, sat=float(sat.mean()), val=float(mx.mean()), opaque=int(m.sum()))


def grad(rgba):
    y = rgba[..., :3].astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    gy, gx = np.gradient(y)
    return np.hypot(gx, gy)


def main(argv):
    packs = '../input/xbox-dlc'; man = 'docs/data/B138.kit_manifest.json'
    if '--packs' in argv: k = argv.index('--packs'); packs = argv[k + 1]; del argv[k:k + 2]
    if '--manifest' in argv: k = argv.index('--manifest'); man = argv[k + 1]; del argv[k:k + 2]
    out = argv[0]; os.makedirs(out, exist_ok=True)
    mf = {}
    if os.path.exists(man):
        for f in json.load(open(man, encoding='utf8'))['files']:
            if f['rel'].startswith('image/dlc_outfit_costume_'): mf[f['rel']] = f
    recs = records(packs)
    img = {}
    print('slot  pack(s)                       xbox bytes  fmt  w x h      xbox md5                          pc md5                            B138 pc / xbox source')
    for s in SLOTS:
        lst = recs.get(s, [])
        if not lst: print('%s     (no record)' % s); continue
        uniq = {}
        for pk, b in lst: uniq.setdefault(hashlib.md5(b).hexdigest(), []).append((pk, b))
        best = max(uniq.values(), key=lambda v: len(v[0][1]))
        b = best[0][1]
        h = RI.header(b, '>')
        pc = RI.xbox_to_pc(b)
        _, px = RI.decode_pc(pc)
        rgba = np.ascontiguousarray(px[..., [2, 1, 0, 3]])
        img[s] = rgba
        RI.to_png(pc, os.path.join(out, 'dlc_outfit_costume_%s.png' % s))
        xm = hashlib.md5(b).hexdigest(); pm = hashlib.md5(pc).hexdigest()
        m = mf.get('image/dlc_outfit_costume_%s.raw' % s)
        proof = '-' if m is None else '%s / %s' % ('pc=B138' if m['md5'] == pm else 'pc DIFFERS',
                                                   'src=record' if (m.get('source') or {}).get('md5') == xm else 'src differs')
        packs_s = ','.join(sorted({pk for v in uniq.values() for pk, _ in v}))
        other = []
        for v in uniq.values():
            if v is best: continue
            try:
                opc = RI.xbox_to_pc(v[0][1]); opm = hashlib.md5(opc).hexdigest()
                if len(v[0][1]) == len(b):      # a full-size variant (not a placeholder): keep its picture too
                    RI.to_png(opc, os.path.join(out, 'dlc_outfit_costume_%s_%s.png' % (s, v[0][0].split('.')[0])))
            except Exception as e: opm = 'undecodable'
            other.append('%s:%d xbox %s pc %s%s' % ('+'.join(pk for pk, _ in v), len(v[0][1]), hashlib.md5(v[0][1]).hexdigest()[:8],
                                                  opm[:8], ' (=B138)' if m is not None and m['md5'] == opm else ''))
        packs_best = '+'.join(pk for pk, _ in best)
        print("%s     %-28s  %9d  %3d  %3d x %-3d  %s  %s  %s%s" % (s, packs_best, len(b), h[3], h[5], h[6], xm, pm, proof,
              ('  other variants ' + ' '.join(other)) if other else ''))
    print()
    print('colour of the opaque pixels (hue deg weighted by saturation, mean saturation, mean value, opaque pixels)')
    for s, rgba in img.items():
        st = hsv_stats(rgba)
        print('%s  hue %5.1f  sat %.3f  val %.3f  opaque %6d' % (s, st['hue'], st['sat'], st['val'], st['opaque']))
    print()
    print('silhouette IoU (alpha > 128) | luminance-gradient correlation inside the common silhouette')
    keys = [s for s in SLOTS if s in img]
    print('    ' + ' '.join('%11s' % k for k in keys))
    for a in keys:
        row = []
        for b in keys:
            A, B = img[a], img[b]
            if A.shape != B.shape: row.append('%11s' % 'size'); continue
            ma, mb = A[..., 3] > 128, B[..., 3] > 128
            iou = (ma & mb).sum() / max(1, (ma | mb).sum())
            c = ma & mb
            ga, gb = grad(A)[c], grad(B)[c]
            cor = np.corrcoef(ga, gb)[0, 1] if len(ga) > 10 else float('nan')
            row.append('%5.2f|%5.2f' % (iou, cor))
        print('%s   ' % a + ' '.join(row))
    try:
        from PIL import Image, ImageDraw
        h0, w0 = next(iter(img.values())).shape[:2]
        cols = 8; rows = (len(keys) + cols - 1) // cols
        sheet = Image.new('RGBA', (cols * w0, rows * (h0 + 16)), (40, 40, 40, 255))
        dr = ImageDraw.Draw(sheet)
        for i, s in enumerate(keys):
            x, y = (i % cols) * w0, (i // cols) * (h0 + 16)
            im = Image.fromarray(img[s], 'RGBA')
            sheet.alpha_composite(im, (x, y + 16))
            dr.text((x + 4, y + 2), 'costume_%s' % s, fill=(255, 255, 255, 255))
        sheet.save(os.path.join(out, 'Uebersicht.png'))
        print('\nwritten', len(keys), 'PNGs + Uebersicht.png to', out)
    except Exception as e:
        print('contact sheet failed:', e)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
