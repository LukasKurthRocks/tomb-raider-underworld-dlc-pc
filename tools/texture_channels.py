"""Per-channel statistics (mean / standard deviation of R, G, B, A) of PC textures (type 5) in one or more DRMs,
read-only. Finding 43 follow-up: the DLC 2 waterfall material 24920 = the base eitr water-surface material, but its
normal map 7001 was Xenos DXN (two channels) on Xbox and became DXT5 on PC - does our conversion put the channels
where Crystal's own PC normal maps have them (base `ar_goo_watersurface` 4975, DXT5)?

Usage (from the repository root):
  ../bin/pyt -t 300 tools/texture_channels.py FILE.drm:ID[,ID] [FILE.drm:ID ...]
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, tex_convert as T


def main(argv):
    for spec in argv:
        path, ids = spec.rsplit(':', 1)
        D = DW.read(open(path, 'rb').read(), 'le')
        for tid in (int(x) for x in ids.split(',')):
            s = next(x for x in D.sections if x.type == 5 and x.id == tid)
            a = np.asarray(T.pc_image(s.data), dtype=np.float64)          # H x W x 4 (RGBA)
            print('%-28s %5d  %4dx%-4d  %s' % (os.path.basename(path), tid, a.shape[1], a.shape[0], '  '.join(
                '%s %5.1f+-%4.1f' % (c, a[..., k].mean(), a[..., k].std()) for k, c in enumerate('RGBA'))))


if __name__ == '__main__':
    main(sys.argv[1:])
