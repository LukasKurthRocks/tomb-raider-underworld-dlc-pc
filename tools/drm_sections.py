"""List the sections of a DRM file (read-only): index, type (with name), id, size, relocation counts; for textures
(type 5) the header words, for shader libraries (type 9) the slot count. Finding 43 follow-up (grapple ring and
waterfall drawn wrongly: which textures / materials / shaders an object brings).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/drm_sections.py FILE.drm [--type N] [--endian le|be] [--dump SECTION_ID FROM_HEX LEN_HEX]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

TYPES = {0: 'general', 2: 'empty/anim', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
         11: 'object', 12: 'mesh', 13: 'unit'}


def main(argv):
    only = None; endian = 'le'
    if '--type' in argv: k = argv.index('--type'); only = int(argv[k + 1]); del argv[k:k + 2]
    if '--endian' in argv: k = argv.index('--endian'); endian = argv[k + 1]; del argv[k:k + 2]
    dump = None
    if '--dump' in argv: k = argv.index('--dump'); dump = (int(argv[k + 1]), int(argv[k + 2], 16), int(argv[k + 3], 16)); del argv[k:k + 4]
    D = DW.read(open(argv[0], 'rb').read(), endian)
    e = '<' if endian == 'le' else '>'
    if dump:      # --dump SECTION_ID FROM_HEX LEN_HEX: 32-bit words of one section (first section with that id)
        s = next(x for x in D.sections if x.id == dump[0] and (only is None or x.type == only))
        for o in range(dump[1], min(len(s.data), dump[1] + dump[2]), 16):
            print('  +%04x  %s' % (o, ' '.join('%08x' % w for w in struct.unpack_from(e + '%dI' % (min(16, len(s.data) - o) // 4), s.data, o))))
        return
    for i, s in enumerate(D.sections):
        if only is not None and s.type != only: continue
        r = R.parse(s.reloc, endian)
        extra = ''
        if s.type == 5 and len(s.data) >= 32: extra = 'hdr ' + ' '.join('%08x' % w for w in struct.unpack_from(e + '8I', s.data, 0))
        if s.type == 9 and len(s.data) >= 12: extra = 'slots %d' % (struct.unpack_from(e + 'I', s.data, 4)[0] // 4)
        if s.type == 10:       # material: the ids it references (type:id@offset), e.g. shader libs (9) and textures (5)
            refs = sorted((o, t) for t, o in r.idref)
            extra = 'refs ' + ' '.join('%s:%d@%x' % (TYPES.get(t, t), struct.unpack_from(e + 'I', s.data, o)[0], o) for o, t in refs)
        print('%4d  %-10s id %6d  size %8d  reloc int %d ext %d id %d  %s' % (
            i, TYPES.get(s.type, str(s.type)), s.id, len(s.data), len(r.internal), len(r.external), len(r.idref), extra))


if __name__ == '__main__':
    main(sys.argv[1:])
