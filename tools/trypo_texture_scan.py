"""Trypophobia candidate scan (read-only): decode the textures (type 5) of game DRMs straight from the archives and give
each one a heuristic "cluster of small holes / bumps" score, so a person can look at the highest-scoring textures
first. The score only SORTS candidates - it does not decide what triggers anyone (that is subjective).

Score (numpy only, on a mip level of at most 256 px): difference-of-blurs band pass at three blob scales; local
minima (dark spots = holes) and maxima (bright spots = bumps / bubbles) above a contrast threshold are counted;
fill = share of the area covered by such spots, cv = spread of the nearest-neighbour distances between spots (low =
evenly spaced like a honeycomb), contrast = mean band-pass response at the spots. score = fill * contrast term *
(1.2 - cv), best scale wins. Gravel, rock noise and tiled stone also score high - look at the pictures.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/trypo_texture_scan.py scan OUT.tsv SPEC [SPEC ...]
      SPEC = SRC:NAME (NAME without .drm; SRC = a source of tools/locals.py: pcbig, pcpatch, pack10, pack11, ...;
      SRC "pc" = pcpatch first, then pcbig; "any" = pcpatch, pcbig, pack10, pack11; "dir=PATH" = PATH/NAME.drm of
      a PC tree such as the converted DLC units) or SRC:@FILE (names one per line, '#' comments)
  ../bin/pyt -t 900 tools/trypo_texture_scan.py sheet IN.tsv OUT.png [--top N] [--min S] [--drm SUBSTR]
      [--role diffuse|normal|atlas|any] [--ids ID,ID] [--cell 128] [--cols 6] [--alpha]
      contact sheet of the selected rows (sorted by score), label "id score drm"; --alpha keeps transparency
      (composited on grey, e.g. particle sprites)
  ../bin/pyt -t 300 tools/trypo_texture_scan.py variants SPEC ID OUT.png [--size 256]
      one texture as four panels: original | blurred | blurred + half desaturated | flat mean colour - a preview of
      what a runtime "tone down" replacement would look like (nothing is written into game data)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode
import drm_write as DW
import tex_convert as T

_ARCH = {}
COLS = ['family', 'src', 'drm', 'sec', 'id', 'fmt', 'w', 'h', 'role', 'std', 'holes', 'bumps', 'scale', 'fill', 'cv',
        'contrast', 'score', 'drms']


def archive(src):
    if src not in _ARCH:
        path, e, pre = LC.SRC[src]
        _ARCH[src] = (Archive(path, e), e, pre)
    return _ARCH[src]


def load(spec):
    """'SRC:NAME' -> (src, endian, raw DRM bytes) or None. SRC 'dir=PATH' reads PATH/NAME.drm (a PC tree, e.g. the
    converted DLC units, little endian)."""
    src, name = spec.split(':', 1)
    if src.startswith('dir='):
        p = os.path.join(src[4:], name + '.drm')
        return (src, 'le', cdrm_decode(open(p, 'rb').read(), 'le')) if os.path.exists(p) else None
    order = {'pc': ['pcpatch', 'pcbig'], 'any': ['pcpatch', 'pcbig', 'pack10', 'pack11']}.get(src, [src])
    for s in order:
        if s not in LC.SRC or not os.path.exists(LC.SRC[s][0]): continue
        A, e, pre = archive(s)
        recs = A.find(crc(pre + '\\' + name + '.drm'))
        if recs: return s, e, cdrm_decode(A.read(recs[-1]), e)
    return None


def expand(specs):
    for sp in specs:
        src, name = sp.split(':', 1)
        if name.startswith('@'):
            for line in open(name[1:], encoding='utf-8'):
                line = line.split('#')[0].strip()
                if line: yield '%s:%s' % (src, line)
        else:
            yield sp


def pc_payload(sec_data, endian):
    """Texture section data -> PC PCD9 payload (Xbox data is converted with tools/tex_convert.py)."""
    return sec_data if endian == 'le' else T.convert(sec_data)


def small_image(pc, maxdim=256):
    """PC payload -> (RGBA uint8 image at the first mip level <= maxdim, header, kind)."""
    h, kind, res = T.pc_levels(pc)
    lv = 0
    while lv < len(res[0]) - 1 and max(res[0][lv][1], res[0][lv][2]) > maxdim: lv += 1
    blk, w, hh = res[0][lv]
    return T.blocks_to_image(blk, kind, w, hh), h, kind


def role_of(im):
    """'normal' when red and blue are almost constant but green / alpha vary (DXN-style .ag normal map), else 'diffuse'."""
    f = im.reshape(-1, 4).astype(np.float32)
    sd = f.std(0)
    if sd.max() < 2: return 'flat'
    if sd[0] < 6 and sd[2] < 6 and (sd[1] > 10 or sd[3] > 10): return 'normal'
    mean = f.mean(0)
    if 70 < mean[0] < 200 and mean[1] > 170 and mean[2] < 70: return 'normal'      # lime look of the .ag layout
    if sd[3] < 1 and abs(mean[0] - 128) < 20 and abs(mean[1] - 128) < 20 and mean[2] > 180: return 'normal'
    # data atlases (encoded lighting / blend maps): large share of fully saturated primary / secondary colours
    rgb = f[:, :3]
    mx, mn = rgb.max(1), rgb.min(1)
    lit = mx > 90
    pure = lit & (mn < 0.25 * mx)
    if (mx > 200).mean() > 0 and pure.mean() > 0.30: return 'atlas'
    if lit.mean() > 0.05 and pure.sum() > 0.6 * lit.sum() and (rgb[lit].std(0) > 60).sum() >= 2: return 'atlas'
    return 'diffuse'


def box(a, r):
    """Box blur with wrap-around (textures tile), separable, via cumulative sums."""
    if r < 1: return a
    for ax in (0, 1):
        p = np.pad(a, [(r + 1, r) if k == ax else (0, 0) for k in (0, 1)], mode='wrap')
        c = np.cumsum(p, axis=ax, dtype=np.float64)
        n = a.shape[ax]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax)
        lo = np.take(c, np.arange(0, n), axis=ax)
        a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def blur(a, s):
    r = max(1, int(round(s * 0.9)))
    return box(box(box(a, r), r), r)


def roll_ext(a, r, fn):
    out = a.copy()
    for ax in (0, 1):
        cur = out.copy()
        for d in range(1, r + 1):
            cur = fn(cur, np.roll(out, d, axis=ax)); cur = fn(cur, np.roll(out, -d, axis=ax))
        out = cur
    return out


def nn_cv(ys, xs, shape):
    if len(ys) < 6: return 1.0
    if len(ys) > 1500:
        k = np.random.default_rng(1).choice(len(ys), 1500, replace=False); ys, xs = ys[k], xs[k]
    H, W = shape
    dy = np.abs(ys[:, None] - ys[None, :]).astype(np.float32); dy = np.minimum(dy, H - dy)
    dx = np.abs(xs[:, None] - xs[None, :]).astype(np.float32); dx = np.minimum(dx, W - dx)
    d = np.sqrt(dy * dy + dx * dx); np.fill_diagonal(d, np.inf)
    nn = d.min(1)
    return float(nn.std() / (nn.mean() + 1e-6))


def score_image(im, role):
    f = im.astype(np.float32) / 255.0
    g = f[..., 1] if role == 'normal' else (0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2])
    H, W = g.shape
    sd = float(g.std())
    best = dict(std=sd, holes=0, bumps=0, scale=0, fill=0.0, cv=1.0, contrast=0.0, score=0.0)
    if min(H, W) < 32 or sd < 0.02: return best
    for s2 in (1.5, 3.0, 5.0):
        if 6 * s2 > min(H, W): continue
        dog = blur(g, s2) - blur(g, 2 * s2)
        thr = max(0.015, 1.2 * float(dog.std()))
        r = max(1, int(round(s2)))
        lo = roll_ext(dog, r, np.minimum); hi = roll_ext(dog, r, np.maximum)
        holes = (dog <= lo) & (dog < -thr); bumps = (dog >= hi) & (dog > thr)
        nh, nb = int(holes.sum()), int(bumps.sum())
        main = holes if nh >= nb else bumps
        ys, xs = np.nonzero(main)
        n = len(ys)
        if n < 6: continue
        fill = min(1.0, n * np.pi * (1.4 * s2) ** 2 / (H * W))
        contrast = float(np.abs(dog[main]).mean())
        cv = nn_cv(ys, xs, (H, W))
        sc = fill * min(1.5, contrast / 0.06) * max(0.0, 1.2 - cv)
        if sc > best['score']:
            best = dict(std=sd, holes=nh, bumps=nb, scale=s2, fill=fill, cv=cv, contrast=contrast, score=sc)
    return best


def textures(raw, endian):
    D = DW.read(raw, endian)
    for i, s in enumerate(D.sections):
        if s.type == 5: yield i, s


def cmd_scan(argv):
    out, specs = argv[0], list(expand(argv[1:]))
    rows = {}                      # (family, id, payload size) -> row
    for n, sp in enumerate(specs):
        got = load(sp)
        if not got:
            print('[%d/%d] %s: not found' % (n + 1, len(specs), sp)); continue
        src, e, raw = got
        fam = 'pc' if e == 'le' else 'xbox'
        name = sp.split(':', 1)[1]
        cnt = new = 0
        for i, s in textures(raw, e):
            cnt += 1
            key = (fam, s.id, len(s.data))
            if key in rows:
                rows[key]['drms'].append(name); continue
            row = dict(family=fam, src=src, drm=name, sec=i, id=s.id, drms=[name])
            try:
                pc = pc_payload(s.data, e)
                im, h, kind = small_image(pc)
                if h['flags'] & 0x8000: kind += '-cube'
                role = role_of(im)
                row.update(fmt=kind, w=h['w'], h=h['h'], role=role)
                row.update(score_image(im, role) if not kind.endswith('cube') else dict(score=0.0))
            except Exception as ex:
                row.update(fmt='err:' + type(ex).__name__, w=0, h=0, role='?', score=0.0)
            rows[key] = row; new += 1
        print('[%d/%d] %s (%s): %d textures, %d new' % (n + 1, len(specs), sp, src, cnt, new))
        del raw
    with open(out, 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('\t'.join(COLS) + '\n')
        for r in sorted(rows.values(), key=lambda r: -r.get('score', 0)):
            vals = []
            for c in COLS:
                v = r.get(c, '')
                if c == 'drms': v = ','.join(dict.fromkeys(v))
                elif isinstance(v, float): v = '%.4f' % v
                vals.append(str(v))
            fo.write('\t'.join(vals) + '\n')
    print('rows %d -> %s' % (len(rows), out))


def read_tsv(path):
    lines = open(path, encoding='utf-8').read().splitlines()
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:] if l]


def opt(argv, key, default):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def cmd_sheet(argv):
    from tex_dlc import contact_sheet
    top = int(opt(argv, '--top', '24')); mn = float(opt(argv, '--min', '0')); sub = opt(argv, '--drm', '')
    role = opt(argv, '--role', 'diffuse'); ids = opt(argv, '--ids', ''); cell = int(opt(argv, '--cell', '128'))
    cols = int(opt(argv, '--cols', '6'))
    keep_alpha = '--alpha' in argv
    argv = [a for a in argv if a != '--alpha']
    tsv, out = argv[0], argv[1]
    rows = read_tsv(tsv)
    if ids:
        want = {int(x) for x in ids.split(',')}
        rows = [r for r in rows if int(r['id']) in want]
    else:
        rows = [r for r in rows if float(r['score'] or 0) >= mn and (role == 'any' or r['role'] == role)
                and (not sub or sub in r['drms'])][:top]
    by = {}
    for r in rows: by.setdefault((r['src'], r['drm']), []).append(r)
    imgs = {}
    for (src, drm), rs in by.items():
        got = load('%s:%s' % (src, drm))
        if not got: continue
        _, e, raw = got
        want = {int(r['sec']) for r in rs}
        for i, s in textures(raw, e):
            if i in want:
                im, _, _ = small_image(pc_payload(s.data, e), cell * 2)
                imgs[(drm, i)] = im
    sel = []
    for r in rows:
        im = imgs.get((r['drm'], int(r['sec'])))
        if im is None: continue
        label = '%s %.2f %s' % (r['id'], float(r['score'] or 0), r['drm'])
        if keep_alpha:
            label = label[:21] + 'a'          # tools/tex_dlc.contact_sheet composites labels ending in 'a' on grey
        else:
            im = im.copy(); im[..., 3] = 255
        sel.append((label, im))
    contact_sheet(sel, out, cell=cell, cols=cols)
    print('%d textures -> %s' % (len(sel), out))


def cmd_variants(argv):
    from PIL import Image, ImageDraw
    size = int(opt(argv, '--size', '256'))
    spec, tid, out = argv[0], int(argv[1]), argv[2]
    got = load(spec)
    if not got: raise SystemExit('not found: ' + spec)
    _, e, raw = got
    im = None
    for i, s in textures(raw, e):
        if s.id == tid: im, _, _ = small_image(pc_payload(s.data, e), size); break
    if im is None: raise SystemExit('texture %d not in %s' % (tid, spec))
    rgb = im[..., :3].astype(np.float32)
    sig = max(2.0, rgb.shape[1] * 0.02)
    bl = np.stack([blur(rgb[..., c], sig) for c in range(3)], -1)
    grey = bl.mean(-1, keepdims=True)
    half = bl * 0.5 + grey * 0.5
    flat = np.broadcast_to(rgb.reshape(-1, 3).mean(0), rgb.shape)
    panels = [('original', rgb), ('blurred', bl), ('blur + half grey', half), ('flat mean colour', flat)]
    hh, ww = rgb.shape[:2]
    sheet = Image.new('RGB', (4 * ww, hh + 14), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    for k, (lab, a) in enumerate(panels):
        sheet.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), (k * ww, 0))
        d.text((k * ww + 3, hh + 1), lab, fill=(255, 255, 0))
    sheet.save(out)
    print('%s id %d %dx%d -> %s' % (spec, tid, ww, hh, out))


def main(argv):
    if not argv or argv[0] not in ('scan', 'sheet', 'variants'): sys.exit(__doc__)
    {'scan': cmd_scan, 'sheet': cmd_sheet, 'variants': cmd_variants}[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
