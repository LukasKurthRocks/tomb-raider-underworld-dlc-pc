"""Dump the render data of the Mesh sections (type 12, 'Mesh' magic) of DRM files side by side, read-only: per batch
vertex count, stride, vertex format (semantic / offset / type), format hash (known from the PC base pairs or not),
bone palette size, triangle count, index range; per mesh the validity checks of tools/mesh_validate.py (PC files).
Test 48d (2026-10-31): the doppelganger figure makes the D3D9 device fail ~10 s after DoppelgangerInit - which part
of its model differs from working player figures (lara_casual, dlc_costume_*).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/mesh_render_dump.py FILE[:be] [FILE[:be] ...] [--batches]
  :be = Xbox file (big endian); --batches: one line per batch (default: summary per mesh)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import mesh_convert as MC
from mesh_tr8 import Mesh, SEM, H


def known_hashes():
    MC.pc_decl_hash([])
    return {v for v in (MC._DECL or {}).values()}


def main(argv):
    detail = '--batches' in argv; argv = [a for a in argv if a != '--batches']
    known = known_hashes()
    for spec in argv:
        path, en = (spec[:-3], 'be') if spec.endswith(':be') else (spec, 'le')
        D = DW.read(open(path, 'rb').read(), en)
        for s in D.sections:
            if s.type != 12 or s.data[0x10:0x14] not in (b'hseM', b'Mesh'): continue
            m = Mesh(s.data, en)
            types = collections.Counter(); fmts = collections.Counter(); unk = 0
            maxpal = 0; verts = 0; tris = 0
            idx = m.indices() if m.numMeshes else []
            for i, b in enumerate(m.meshes):
                vf = b['vf']
                if vf:
                    fmts[(vf['stride'], tuple((SEM.get(se, hex(se)), o, t) for se, o, t, _ in vf['elems']))] += 1
                    for se, o, t, _ in vf['elems']: types[t] += 1
                    hk = struct.pack('<Q', vf['hash']) if isinstance(vf['hash'], int) else vf['hash']
                    if en == 'le' and hk not in known and struct.pack('>Q', vf['hash'] if isinstance(vf['hash'], int) else 0) not in known: unk += 1
                maxpal = max(maxpal, b['skinSize']); verts += b['numVerts']; tris += b['numTris']
                if detail:
                    seg = idx[b['baseIndex']:b['baseIndex'] + 3 * b['numTris']]
                    print('  %s 12:%d batch %3d  verts %5d stride %3s tris %5d pal %2d  idx %s..%s  vf %s hash %s'
                          % (os.path.basename(path), s.id, i, b['numVerts'], vf['stride'] if vf else '-', b['numTris'],
                             b['skinSize'], min(seg) if seg else '-', max(seg) if seg else '-',
                             ' '.join('%s@%d:t%x' % (SEM.get(se, hex(se))[:6], o, t) for se, o, t, _ in vf['elems']) if vf else '-',
                             ('%016x' % vf['hash']) if vf and isinstance(vf['hash'], int) else '-'))
            bad = []
            if en == 'le':
                import mesh_validate as MV
                bad = MV.validity(s.data, s.reloc)
            print('%s 12:%d  %d bytes  meshes %d groups %d bones %d indices %d  verts %d tris %d  max palette %d  '
                  'formats %d (unknown hash %d)  elem types %s  validity %s'
                  % (os.path.basename(path), s.id, len(s.data), m.numMeshes, m.numGroups, m.numBones, m.numIndices,
                     verts, tris, maxpal, len(fmts), unk, dict(sorted(types.items())), bad or 'ok'))
            for (st, el), n in sorted(fmts.items()):
                print('    fmt x%-3d stride %3d  %s' % (n, st, ' '.join('%s@%d:t%x' % e for e in el)))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
