"""List the sections of a PC DRM (type, id, size, relocation counts, terrain / mesh for type 12), read-only.
Finding 43, test 44b: which type-12 sections dlc_level2_start.drm has besides terrain 20085.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_sections_list.py PC.drm [--type T] [--be]   (--be: Xbox file, big endian)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    typ = None
    if '--type' in argv: k = argv.index('--type'); typ = int(argv[k + 1]); del argv[k:k + 2]
    en = 'be' if '--be' in argv else 'le'; argv = [a for a in argv if a != '--be']
    D = DW.read(open(argv[0], 'rb').read(), en)
    for i, s in enumerate(D.sections):
        if typ is not None and s.type != typ: continue
        r = R.parse(s.reloc, en)
        kind = ''
        if s.type == 12: kind = 'mesh' if s.data[0x10:0x14] in (b'hseM', b'Mesh') else 'terrain'
        print('%4d  %2d:%-6d %9d bytes  int %5d ext %4d idA %4d id %5d  %s'
              % (i, s.type, s.id, len(s.data), len(r.internal), len(r.external), len(r.idref_a), len(r.idref), kind))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
