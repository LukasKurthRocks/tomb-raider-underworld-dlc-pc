"""Draw batches of a terrain section (type 12 without 'Mesh' magic, tools/terrain_convert.parse) for one material,
Xbox and PC side by side (read-only). Finding 43 follow-up: the DLC 2 waterfall is material 24920 (the base eitr
water surface, converted like the base) - does its geometry differ, e.g. vertex colour / alpha (D3DCOLOR, type 4)?
Per batch (Y record) with that material: vertex buffer, vertex count, vertex format (semantic, offset, type) and,
for every D3DCOLOR element, mean / min / max of A, R, G, B over the buffer's vertices; plus the Y record words.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/terrain_batches.py XBOX.drm PC.drm SECTION_ID MATERIAL_ID[:PC_MATERIAL_ID]
  SECTION_ID 0 = every terrain section; PC_MATERIAL_ID for base pairs (Xbox and PC ids differ)
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, terrain_convert as TC


def report(d, reloc, e, mid, label):
    u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    T = TC.parse(d, e); H = T['H']
    ptr = dict(R.parse(reloc, 'le' if e == '<' else 'be').internal)     # pointer words are placeholders on disk
    ml = ptr[0x0C]; mats = list(struct.unpack_from(e + '%dI' % u(ml), d, ml + 4))
    for yi, y in enumerate(T['Y']):
        if y[0] >= len(mats) or mats[y[0]] != mid: continue
        vdo, _, nv, vfi = T['vbs'][y[1]]
        vf = T['vfs'][vfi]
        print('%s  Y %d: material index %d, vb %d (%d verts, stride %d), Y words %s' % (
            label, yi, y[0], y[1], nv, vf['stride'], ' '.join('%x' % w for w in y[2:])))
        print('      format: %s' % ', '.join('%08x@%d t%d' % (s, o, t) for s, o, t, _ in vf['elems']))
        for s, o, t, _ in vf['elems']:
            if t != 4: continue
            v = np.array([u(H + vdo + k * vf['stride'] + o) for k in range(nv)], dtype=np.uint64)
            ch = {'A': v >> 24 & 255, 'R': v >> 16 & 255, 'G': v >> 8 & 255, 'B': v & 255}
            print('      colour %08x: %s' % (s, '  '.join('%s %5.1f [%d..%d]' % (c, x.mean(), x.min(), x.max()) for c, x in ch.items())))


def main(argv):
    xp, pp, sid = argv[0], argv[1], int(argv[2])
    mids = [int(x) for x in argv[3].split(':')]; mids += mids[:1] * (2 - len(mids))      # XBOX_ID[:PC_ID]
    for (path, e, label), mid in zip(((xp, '>', 'xbox'), (pp, '<', 'pc  ')), mids):
        D = DW.read(open(path, 'rb').read(), 'le' if e == '<' else 'be')
        for s in D.sections:      # SECTION_ID 0: every terrain section of the file
            if s.type == 12 and (s.id == sid or (sid == 0 and TC.is_terrain(s.data))):
                report(s.data, s.reloc, e, mid, '%s %d' % (label, s.id))


if __name__ == '__main__':
    main(sys.argv[1:])
