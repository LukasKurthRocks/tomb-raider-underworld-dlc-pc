"""Player data breath-sound ids of any DRM (read-only; agent N11, 2026-11-04, docs Befund-Pipeline-Integration-0411.md).

For every type-7 section with an internal pointer at +0xc8 whose target block holds the air maximum 4000 (s16 at
block +0xf8, tools/objdata_idword_fix.py), print the two breath-sound ids at block +0x94 / +0x98 as the engine reads
them (one u32 in the file's byte order) and which sections of the file carry that id (type list). Used to see what a
played file (B138 DLC 1 costumes, base lara.drm) holds there, compared with a converted one.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/player_breath_ids.py FILE.drm [FILE.drm ...] [--be] [--air 4000]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv; argv = [a for a in argv if a != '--be']
    air = 4000
    if '--air' in argv: k = argv.index('--air'); air = int(argv[k + 1]); del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    e = 'be' if be else 'le'; f = '>' if be else '<'
    for path in argv:
        D = DW.read(open(path, 'rb').read(), e)
        types = collections.defaultdict(list)
        for s in D.sections: types[s.id].append(s.type)
        hits = 0
        for k, s in enumerate(D.sections):
            if s.type != 7 or not s.reloc or len(s.data) < 0xcc: continue
            t = dict(R.parse(bytes(s.reloc), e).internal).get(0xc8)
            if t is None or t + 0xfa > len(s.data): continue
            if struct.unpack_from(f + 'h', s.data, t + 0xf8)[0] != air: continue
            hits += 1
            w = [struct.unpack_from(f + 'I', s.data, t + o)[0] for o in (0x94, 0x98)]
            print('%s: section %d DTP %d block +0x%x air %d: +0x94 = 0x%08x (%s), +0x98 = 0x%08x (%s)' % (
                os.path.basename(path), k, s.id, t, air, w[0], 'types %s' % types[w[0]] if w[0] in types else 'no section',
                w[1], 'types %s' % types[w[1]] if w[1] in types else 'no section'))
        if not hits: print('%s: no player data block (DTP +0xc8 -> air %d)' % (os.path.basename(path), air))


if __name__ == '__main__':
    main(sys.argv[1:])
