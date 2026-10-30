"""Terrain material / texture references of a converted PC level DRM checked against a mods tree (read-only).
For every terrain section (type 12 without 'Mesh' magic): the material id list (+0x0C) and texture id list (+0x08),
how many draw batches (Y records) use each material, and whether a material / texture section with that id exists
in the same file or anywhere in the tree (first file found). A material missing from the tree leaves its batches
undrawn. Finding 43 follow-up (DLC 2 rock vein: the vein strip on the wall is not drawn on PC).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/terrain_material_check.py PC_LEVEL.drm MODS_DIR
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import terrain_convert as TC


def tree_index(mods):
    """{(type, id): first relative file name} over every .drm of the tree"""
    idx = {}
    for root, _, files in os.walk(mods):
        for f in files:
            if not f.endswith('.drm'): continue
            p = os.path.join(root, f)
            try: D = DW.read(open(p, 'rb').read(), 'le')
            except Exception: continue
            for s in D.sections:
                if s.type in (5, 10): idx.setdefault((s.type, s.id), os.path.relpath(p, mods))
    return idx


def main(argv):
    path, mods = argv
    D = DW.read(open(path, 'rb').read(), 'le')
    own = {(s.type, s.id) for s in D.sections}
    idx = tree_index(mods)
    for s in D.sections:
        if s.type != 12 or not TC.is_terrain(s.data): continue
        d = s.data; u = lambda o: struct.unpack_from('<I', d, o)[0]
        ptr = dict(R.parse(s.reloc, 'le').internal)
        T = TC.parse(d, '<')
        ml, tl = ptr[0x0C], ptr[0x08]
        mats = list(struct.unpack_from('<%dI' % u(ml), d, ml + 4))
        texs = list(struct.unpack_from('<%dI' % u(tl), d, tl + 4))
        use = collections.Counter(y[0] for y in T['Y'])
        print('terrain section %d: %d materials, %d textures, %d batches' % (s.id, len(mats), len(texs), len(T['Y'])))
        for k, m in enumerate(mats):
            where = 'own file' if (10, m) in own else idx.get((10, m), 'MISSING')
            print('  material[%2d] %6d  batches %4d  %s' % (k, m, use[k], where))
        miss = [t for t in texs if (5, t) not in own and (5, t) not in idx]
        print('  textures missing from the tree: %d %s' % (len(miss), miss[:40]))


if __name__ == '__main__':
    main(sys.argv[1:])
