"""World-space extent of the terrain geometry drawn with given materials (read-only; test 50c, rock vein strip).
For every terrain section (type 12 without 'Mesh' magic, tools/terrain_convert.parse) and every draw-list entry whose
Y record uses one of the materials: index count, the referenced vertices' position bounding box (float3 element at
the vertex format's position semantic, offset 0), size and centre. Lets a material be tied to a place (e.g. the
vertical vein strip at the first rock channel of DLC 2).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/terrain_material_bbox.py PC.drm MATERIAL_ID[,MATERIAL_ID...]
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, terrain_convert as TC


def report(d, reloc, mids, sid, e='<'):
    u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    T = TC.parse(d, e); H = T['H']
    ptr = dict(R.parse(reloc, 'le' if e == '<' else 'be').internal)
    ml = ptr[0x0C]; mats = list(struct.unpack_from(e + '%dI' % u(ml), d, ml + 4))
    idx = np.frombuffer(d, dtype=e + 'u2', count=T['nIdx'], offset=H + T['offIdx'])
    for slot, seq, lst in TC.draw_lists(d, T, e):
        for yi, cnt, start in lst:
            y = T['Y'][yi]
            if y[0] >= len(mats) or mats[y[0]] not in mids: continue
            vdo, _, nv, vfi = T['vbs'][y[1]]
            vf = T['vfs'][vfi]
            pos = [o for s, o, t, _ in vf['elems'] if t == 2]
            if not pos: print('  section %d Y %d: no float3 element' % (sid, yi)); continue
            ii = idx[start:start + cnt].astype(np.int64)
            ii = ii[ii < nv]
            P = np.array([struct.unpack_from(e + '3f', d, H + vdo + k * vf['stride'] + pos[0]) for k in np.unique(ii)])
            lo, hi = P.min(0), P.max(0)
            print('  section %d slot %d seq %d Y %d material %d: %d indices from %d, %d vertices, bbox (%.0f %.0f %.0f) - '
                  '(%.0f %.0f %.0f), size (%.0f %.0f %.0f), centre (%.0f %.0f %.0f)' % (
                      sid, slot, seq, yi, mats[y[0]], cnt, start, len(P), *lo, *hi, *(hi - lo), *((lo + hi) / 2)))


def main(argv):
    path = argv[0]; mids = {int(x) for x in argv[1].split(',')}
    D = DW.read(open(path, 'rb').read(), 'le')
    for s in D.sections:
        if s.type != 12 or not TC.is_terrain(s.data): continue
        try:
            report(s.data, s.reloc, mids, s.id)
        except Exception as ex:
            print('  section %d: %s' % (s.id, ex))


if __name__ == '__main__':
    main(sys.argv[1:])
