"""EXPERIMENT tool: point one shader slot of a material (type 10) at another ShaderLib id of the same DRM.
A material references 4 shader libraries at +0x28 / +0x2c / +0x30 / +0x34 (pixel shader per pass 0-2, vertex
shader), each an id reference (relocation kind 9). Finding 43 follow-up: the DLC 1 grapple ring is drawn flat yellow;
swapping B138's translated main-pass shader (2762 / 2756) for the PC surrogate (1018) tells whether the translated
shader or a pass shader causes it. Refuses a target library that is not in the file.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/material_shader_swap.py IN.drm OUT.drm MATERIAL_ID SLOT(0-3) NEW_LIB_ID
      [--add-libs-from BASE_PC.drm ID,ID]   (copy PC ShaderLib sections, e.g. the base grapple ring's 1704-1707)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    add = None
    if '--add-libs-from' in argv:      # --add-libs-from BASE.drm ID[,ID]: copy PC ShaderLib sections into the file first
        k = argv.index('--add-libs-from'); add = (argv[k + 1], [int(x) for x in argv[k + 2].split(',')]); del argv[k:k + 3]
    src, out, mid, slot, new = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4])
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    if add:
        B = DW.read(open(add[0], 'rb').read(), 'le')
        have = {s.id for s in D.sections if s.type == 9}
        for s in B.sections:
            if s.type == 9 and s.id in add[1] and s.id not in have:
                if R.parse(s.reloc, 'le').external: raise SystemExit('ShaderLib %d has external relocations - not copyable' % s.id)
                D.sections.append(s); print('added ShaderLib %d (%d bytes) from %s' % (s.id, len(s.data), os.path.basename(add[0])))
    libs = {s.id for s in D.sections if s.type == 9}
    if new not in libs: raise SystemExit('library %d is not in %s' % (new, src))
    m = next(s for s in D.sections if s.type == 10 and s.id == mid)
    off = 0x28 + 4 * slot
    if (9, off) not in R.parse(m.reloc, 'le').idref: raise SystemExit('no shader id reference at +%#x' % off)
    d = bytearray(m.data); old = struct.unpack_from('<I', d, off)[0]
    struct.pack_into('<I', d, off, new); m.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('material %d slot %d (+%#x): %d -> %d' % (mid, slot, off, old, new))


if __name__ == '__main__':
    main(sys.argv[1:])
