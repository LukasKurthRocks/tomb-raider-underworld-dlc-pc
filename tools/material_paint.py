"""DIAGNOSTIC tool: point every texture reference of one material at a single marker texture, so the object that
uses the material is recognisable in game (finding 43: which DLC 2 material is the waterfall?). The marker texture is
copied from another PC DRM when the file lacks it. Only texture ids change; shaders and parameters stay.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/material_paint.py IN.drm OUT.drm MATERIAL_ID[,ID] TEXTURE_ID [--from SRC_PC.drm]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    src = None
    if '--from' in argv: k = argv.index('--from'); src = argv[k + 1]; del argv[k:k + 2]
    inp, out, mids, tex = argv[0], argv[1], [int(x) for x in argv[2].split(',')], int(argv[3])
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    if not any(s.type == 5 and s.id == tex for s in D.sections):
        if not src: raise SystemExit('texture %d is not in %s (give --from)' % (tex, inp))
        t = next(s for s in DW.read(open(src, 'rb').read(), 'le').sections if s.type == 5 and s.id == tex)
        D.sections.append(t); print('added texture %d (%d bytes) from %s' % (tex, len(t.data), os.path.basename(src)))
    for mid in mids:
        m = next(s for s in D.sections if s.type == 10 and s.id == mid)
        d = bytearray(m.data); n = 0
        for kind, off in R.parse(m.reloc, 'le').idref:
            if kind == 5: struct.pack_into('<I', d, off, tex); n += 1
        m.data = bytes(d); print('material %d: %d texture references -> %d' % (mid, n, tex))
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)


if __name__ == '__main__':
    main(sys.argv[1:])
