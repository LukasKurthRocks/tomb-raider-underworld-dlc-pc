"""Q89: the bone table a model DTP +0x68 points at (external reloc into the type-12 mesh section), read only.

The exe reads [[model+0x68]] as the segment count and [[model+0x68]+4] as the segment array when +0x68 is set
(0x43dc93 -> track +0x5e, 0x4362a6, 0x627081), else model +4 / +0xc. This dumps that table next to the model DTP's own
segment list: count, record stride (from the next internal pointer), per bone the parent word and pivot, and whether
the first nseg records equal the model DTP segments.

Usage (from the repository root):
  ../bin/pyt -t 900 work/q89_skeleton_1111/mesh_bones.py MODS_DIR NAME [NAME ...] [--all]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'q83_allenemies_1111'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from enemy_catalog import Src
from skeleton_compare import models


def main(argv):
    S = Src(argv[0])
    for nm in [x for x in argv[1:] if not x.startswith('--')]:
        g = S.get(nm)
        if g is None:
            print('%s: no DRM' % nm); continue
        D = DW.read(g[2], 'le')
        for m in models(D):
            rel = R.parse(D.sections[m['idx']].reloc, 'le')
            ext = [(si, do) for si, so, do in rel.external if so == 0x68]
            if not ext:
                print('%s model %d nseg %d: no +0x68' % (nm, m['id'], m['n'])); continue
            si, do = ext[0]
            ts = D.sections[si]
            td = ts.data
            trel = dict(R.parse(ts.reloc, 'le').internal)
            cnt = struct.unpack_from('<I', td, do)[0]
            arr = trel.get(do + 4)
            print('\n%s model DTP %d nseg %d -> mesh %d +0x%x: count %d, array %s' % (
                nm, m['id'], m['n'], ts.id, do, cnt, ('+0x%x' % arr) if arr is not None else 'not relocated'))
            if arr is None:
                continue
            stride = 0x40
            same = 0
            rows = []
            for j in range(cnt):
                o = arr + stride * j
                if o + stride > len(td):
                    break
                f = struct.unpack_from('<12f', td, o)
                p = struct.unpack_from('<i', td, o + 0x38)[0]
                a, b = struct.unpack_from('<2H', td, o + 0x34)
                eq = None
                if j < len(m['segs']):
                    ms = m['segs'][j]
                    eq = (ms['parent'] == p and all(abs(ms['f'][q] - f[q]) < 1e-3 for q in (8, 9, 10)))
                    same += 1 if eq else 0
                rows.append((j, p, f, a, b, eq, struct.unpack_from('<I', td, o + 0x30)[0], (o + 0x3c) in trel))
            print('  first %d records equal to the model DTP segments (parent + pivot): %d' % (min(cnt, m['n']), same))
            for j, p, f, a, b, eq, w30, hi in rows:
                if '--all' in argv or j >= m['n'] - 2:
                    print('  bone %3d parent %4d pivot %8.2f %8.2f %8.2f | f0-7 %s | u16 %d %d | w30 %08x | ptr3c %d | eq %s' % (
                        j, p, f[8], f[9], f[10], ' '.join('%.3g' % x for x in f[:8]), a, b, w30, hi, eq))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
