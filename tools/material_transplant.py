"""EXPERIMENT tool: replace one material (type 10) of a PC DRM by a copy of a material from ANOTHER PC DRM (data and
relocations; the section id stays), copy the ShaderLib sections it references when the file lacks them, and point
its texture references at textures of the target file. Checks first that the per-pass vertex-shader input lists of
the source material are covered by the destination's (the mesh must provide what the new vertex shader reads).
Finding 43 follow-up: the DLC 2 waterfall (material 26812 in dlc2_goo_room_goo_room_all, a NEW Xbox shader tuple
without a translation, mapped to surrogates with similarity 0.07 / 0.13) gets the base game's goo fall material
(ca_ani_goo_falls, scrolling-texture shaders 201-204) as a test.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/material_transplant.py IN.drm OUT.drm DST_MATERIAL_ID SRC_PC.drm SRC_MATERIAL_ID
      [--tex OLD=NEW[,OLD=NEW]]   (texture ids in the copied material -> textures of IN.drm; textures not remapped
                                   and not in IN.drm are copied from SRC_PC.drm like the ShaderLibs)
      [--force]                   (write even when the vertex-input check fails)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from shader_map import vs_inputs


def main(argv):
    tex = {}; force = '--force' in argv; argv = [a for a in argv if a != '--force']
    if '--tex' in argv:
        k = argv.index('--tex')
        tex = {int(a): int(b) for a, b in (p.split('=') for p in argv[k + 1].split(','))}; del argv[k:k + 2]
    src, out, dst_id, other, src_id = argv[0], argv[1], int(argv[2]), argv[3], int(argv[4])
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le'); B = DW.read(open(other, 'rb').read(), 'le')
    d = next(s for s in D.sections if s.type == 10 and s.id == dst_id)
    s = next(x for x in B.sections if x.type == 10 and x.id == src_id)
    din, sin = vs_inputs(d.data, d.reloc, '<'), vs_inputs(s.data, s.reloc, '<')
    ok = all(b is None or (a is not None and set(b) <= set(a)) for a, b in zip(din, sin))
    print('vertex inputs per pass  dst %s\n                        src %s  -> %s' % (din, sin, 'covered' if ok else 'NOT covered'))
    if not ok and not force: raise SystemExit('source material reads vertex inputs the destination mesh may lack (--force to write)')
    if R.parse(s.reloc, 'le').external: raise SystemExit('source material %d has external relocations (section indices of its own file)' % src_id)
    ids = R.parse(s.reloc, 'le').idref           # [(kind, offset)]: kind 9 = ShaderLib, 5 = texture
    data = bytearray(s.data)
    have = {(x.type, x.id) for x in D.sections}
    for kind, off in sorted(ids):
        v = struct.unpack_from('<I', data, off)[0]
        if kind == 5 and v in tex: struct.pack_into('<I', data, off, tex[v]); print('texture +%#x: %d -> %d' % (off, v, tex[v])); v = tex[v]
        if (kind, v) in have: continue
        add = next((x for x in B.sections if x.type == kind and x.id == v), None) if kind in (5, 9) else None
        if add is None or R.parse(add.reloc, 'le').external:     # foreign external relocations would point at wrong sections
            raise SystemExit('section type %d id %d (ref at +%#x) is neither in %s nor copyable' % (kind, v, off, src))
        D.sections.append(add); have.add((kind, v))
        print('added %s %d (%d bytes) from %s' % ('ShaderLib' if kind == 9 else 'texture', v, len(add.data), os.path.basename(other)))
    old = len(d.data)
    d.data, d.reloc = bytes(data), s.reloc
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('material %d (%d bytes) := copy of %s material %d (%d bytes)' % (dst_id, old, os.path.basename(other), src_id, len(s.data)))


if __name__ == '__main__':
    main(sys.argv[1:])
