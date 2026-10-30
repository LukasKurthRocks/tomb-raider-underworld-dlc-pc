"""EXPERIMENT tool: give one texture slot of one material a darkened (or brightened) copy of its texture - only that
material changes, other users of the original texture keep it. The copy is uncompressed A8R8G8B8 with all mip
levels (tools/texture_digits.section_bytes), added under a new, unused texture id. Finding 43: the DLC 2 waterfall
column (material 24920, slot 2 = grey noise 6999) is drawn additively at full strength on PC; on the Xbox reference
it is a soft glow - test whether attenuating that slot gives the Xbox look.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/texture_scale.py IN.drm OUT.drm MATERIAL_ID SLOT(1..n) NEW_TEX_ID FACTOR [--alpha]
  FACTOR scales R, G, B (e.g. 0.45); --alpha scales the alpha channel instead
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, tex_convert as T
from texture_digits import section_bytes


def main(argv):
    alpha = '--alpha' in argv; argv = [a for a in argv if a != '--alpha']
    inp, out, mid, slot, nid, f = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4]), float(argv[5])
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    if any(s.type == 5 and s.id == nid for s in D.sections): raise SystemExit('texture id %d already in the file' % nid)
    m = next(s for s in D.sections if s.type == 10 and s.id == mid)
    refs = sorted(off for kind, off in R.parse(m.reloc, 'le').idref if kind == 5)
    off = refs[slot - 1]; d = bytearray(m.data); old = struct.unpack_from('<I', d, off)[0]
    src = next(s for s in D.sections if s.type == 5 and s.id == old)
    img = np.asarray(T.pc_image(src.data), dtype=np.float32)
    ch = slice(3, 4) if alpha else slice(0, 3)
    img[..., ch] = np.clip(img[..., ch] * f, 0, 255)
    if img.shape[0] & (img.shape[0] - 1) or img.shape[0] != img.shape[1]: raise SystemExit('only square power-of-two textures')
    D.sections.append(DW.Section(5, nid, section_bytes(img.astype(np.uint8)), b'', src.flags, src.ver, src.spec))
    struct.pack_into('<I', d, off, nid); m.data = bytes(d)
    print('material %d slot %d (+%#x): texture %d -> %d = copy x %.2f (%s), %dx%d' % (
        mid, slot, off, old, nid, f, 'alpha' if alpha else 'colour', img.shape[1], img.shape[0]))
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)


if __name__ == '__main__':
    main(sys.argv[1:])
