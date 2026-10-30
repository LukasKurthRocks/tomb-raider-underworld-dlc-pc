"""EXPERIMENT tool: replace one material (type 10) of a DRM by a copy of another material of the same DRM (data and
relocations; the section id stays), e.g. give an object's near-LOD material the far-LOD material that renders
correctly. Finding 43 follow-up: the DLC 1 grapple ring's near LOD (21093 / 20344, 8 texture registers) shows the
normal map as colour with every shader tried; the far LOD (21164 / 20345) renders right with the base PC shaders.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/material_copy.py IN.drm OUT.drm DST_MATERIAL_ID SRC_MATERIAL_ID
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    src, out, dst_id, src_id = argv[0], argv[1], int(argv[2]), int(argv[3])
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    d = next(s for s in D.sections if s.type == 10 and s.id == dst_id)
    s = next(x for x in D.sections if x.type == 10 and x.id == src_id)
    old = len(d.data)
    d.data, d.reloc = s.data, s.reloc
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('material %d (%d bytes) := copy of %d (%d bytes)' % (dst_id, old, src_id, len(s.data)))


if __name__ == '__main__':
    main(sys.argv[1:])
