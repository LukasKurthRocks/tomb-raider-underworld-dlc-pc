"""Q112 (b), read-only: are the changed base-id textures of the DLC packs a different IMAGE or only another encoding?
Per texture row of q112_detail.tsv (unique per Xbox id + DLC content): tex_convert.convert() of the DLC Xbox texture
and of the Xbox base copy, decoded (tex_convert.pc_image, face 0, level 0), PSNR (tools/override_check.psnr rule:
99 = identical pixels, -1 = dimensions differ / not decodable). Header format / size per side.

Usage (from trudlcport): ../bin/pyt -t 1800 work/j_data_1211/q112_texpsnr.py OUT_DIR
"""
import sys, os, csv, math, hashlib, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'work', 'j_data_1211'))
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import q112_detail as QD
import tex_convert as TC


def psnr(a, b):
    import numpy as np
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    if a.shape != b.shape: return -1.0
    m = ((a - b) ** 2).mean()
    return 99.0 if m == 0 else 10 * math.log10(255 ** 2 / m)


def img(x):
    try:
        h, _, _ = TC.xbox_levels(x)
        return TC.pc_image(TC.convert(x)), '%s %dx%d' % (h.get('fmtname'), h.get('width', 0), h.get('height', 0))
    except Exception as e:
        return None, 'err %s' % type(e).__name__


def main(out):
    rows = [r for r in csv.DictReader(open(os.path.join(out, 'q112_detail.tsv'), encoding='utf-8'), delimiter='\t')
            if r['type'] == '5' and r['base_holder']]
    seen = {}; res = []
    for r in rows:
        pk, drm, xid = r['pack'], r['drm'], int(r['xbox_id'])
        dl = QD.secs_of(('dlc', pk, drm), lambda: QD.read_rec([QD.DLC_ROOT + QD.PACKS[pk]], 'be', drm))
        d = dl[(5, xid)][0]
        key = (xid, hashlib.md5(d).hexdigest())
        if key not in seen:
            b = QD.secs_of(('base', r['base_holder']), lambda: QD.read_rec(QD.BASE, 'be', r['base_holder']))
            x = b[(5, xid)][0]
            a, fa = img(d); c, fc = img(x)
            p = psnr(a, c) if a is not None and c is not None else -1.0
            seen[key] = (p, fa, fc)
        p, fa, fc = seen[key]
        res.append((pk, drm, xid, p, fa, fc, r['ours']))
    with open(os.path.join(out, 'q112_texpsnr.tsv'), 'w', encoding='utf-8') as f:
        f.write('pack\tdrm\txbox_id\tpsnr\tdlc_fmt\tbase_fmt\tours\n')
        for x in res: f.write('%s\t%s\t%d\t%.1f\t%s\t%s\t%s\n' % x)
    bins = collections.Counter()
    for pk, drm, xid, p, fa, fc, o in res:
        b = 'identical' if p >= 99 else '>=40dB' if p >= 40 else '30-40dB' if p >= 30 else '<30dB' if p >= 0 else 'n/a'
        bins[(pk, b, o)] += 1
    for k in sorted(bins): print(k, bins[k])
    u = collections.Counter('identical' if v[0] >= 99 else '>=40dB' if v[0] >= 40 else '30-40dB' if v[0] >= 30 else '<30dB' if v[0] >= 0 else 'n/a' for v in seen.values())
    print('unique (id, DLC content):', len(seen), dict(u))
    for (xid, h), v in sorted(seen.items()):
        if 0 <= v[0] < 30: print('  low', xid, round(v[0], 1), v[1], '|', v[2])


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
