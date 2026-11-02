"""Which channels of a PC texture carry which channels of its Xbox original (read-only; test 50d arms / gloves: are the
PC twins of the Xbox DXN normal maps really in our DXN -> DXT5 layout R = x, A = y that the translated shaders assume?).

The Xbox texture is converted with tools/tex_convert.convert (DXN -> DXT5: R = x, A = y) and decoded; the PC texture is
decoded as stored. Both top mips are compared after resampling the larger one to the smaller size (nearest).
Per PC channel: mean, and the correlation with each channel of the converted Xbox image (|r| close to 1 = the same
data; r close to -1 = inverted).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tex_channel_map.py PC.drm XBOX.drm PCID:XID [PCID:XID ...]
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, tex_convert as TC

CH = 'RGBA'


def img(d):
    im = TC.pc_image(d).astype(np.float32) / 255.0
    if im.shape[-1] == 3: im = np.concatenate([im, np.ones(im.shape[:2] + (1,), np.float32)], axis=-1)
    return im


def main(argv):
    if len(argv) < 3: print(__doc__); return 2
    P = {(s.type, s.id): s for s in DW.read(open(argv[0], 'rb').read(), 'le').sections}
    X = {(s.type, s.id): s for s in DW.read(open(argv[1], 'rb').read(), 'be').sections}
    for pair in argv[2:]:
        pid, xid = (int(v) for v in pair.split(':'))
        sp, sx = P.get((5, pid)), X.get((5, xid))
        if sp is None or sx is None: print('%s: missing' % pair); continue
        hx = TC.xbox_levels(sx.data)[0]
        hp = TC.parse_pc(sp.data)
        a = img(sp.data)
        try: b = img(TC.convert(sx.data))
        except Exception as e: print('%s: Xbox convert failed: %s' % (pair, e)); continue
        h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
        ra = a[(np.arange(h) * a.shape[0] // h)][:, (np.arange(w) * a.shape[1] // w)]
        rb = b[(np.arange(h) * b.shape[0] // h)][:, (np.arange(w) * b.shape[1] // w)]
        print('PC %d (%s %dx%d) <- Xbox %d (%s %dx%d, converted)' % (pid, TC.pc_kind(hp['fmt']), hp['w'], hp['h'], xid,
                                                                    hx['fmtname'], hx['w'], hx['h']))
        print('   Xbox conv. means ' + ' '.join('%s %.3f' % (CH[j], rb[..., j].mean()) for j in range(4)))
        for i in range(4):
            x = ra[..., i].ravel()
            cs = []
            for j in range(4):
                y = rb[..., j].ravel()
                r = np.corrcoef(x, y)[0, 1] if x.std() > 1e-4 and y.std() > 1e-4 else float('nan')
                cs.append('%s %+.3f' % (CH[j], r))
            print('   PC %s mean %.3f std %.3f | corr with Xbox conv. %s' % (CH[i], x.mean(), x.std(), '  '.join(cs)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
