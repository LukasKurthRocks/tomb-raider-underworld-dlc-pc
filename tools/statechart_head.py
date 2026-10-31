"""Print the first words of DTPs (type 7) of a DRM as u32 / u16 pairs, plus size and relocation counts (read-only;
finding 43, state-chart scope: what do the doppelganger DTPs 20134 / 20172 / 20212 and the base chart 850 / 12647
look like at the start).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/statechart_head.py FILE.drm be|le SID[,SID...] [--words N] [--blocks MINSIZE]  (blocks: list
  the blocks (relocation target .. next target) of at least MINSIZE bytes instead of the words)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    n = 16; blocks = 0
    if '--words' in argv: k = argv.index('--words'); n = int(argv[k + 1]); del argv[k:k + 2]
    if '--blocks' in argv: k = argv.index('--blocks'); blocks = int(argv[k + 1], 0); del argv[k:k + 2]
    e = argv[1]; f = '>' if e == 'be' else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    want = {int(x) for x in argv[2].split(',')}
    for s in D.sections:
        if s.type != 7 or s.id not in want: continue
        r = R.parse(bytes(s.reloc), e); d = bytes(s.data)
        ptr = set(r.pointer_offsets()); ids = set(r.id_offsets())
        print('DTP %d: 0x%x bytes, %d internal, %d pointer words, %d id words' % (s.id, len(d), len(r.internal), len(ptr), len(ids)))
        if blocks:
            ri = dict(r.internal)
            t = sorted(set(ri.values()) | {0})
            src = {}
            for o, tg in ri.items(): src.setdefault(tg, o)
            for k, a in enumerate(t):
                end = t[k + 1] if k + 1 < len(t) else len(d)
                if end - a >= blocks: print('  block +0x%05x size 0x%x (first pointer to it at +0x%x)' % (a, end - a, src.get(a, -1)))
            continue
        for o in range(0, min(n * 4, len(d)), 4):
            w = struct.unpack_from(f + 'I', d, o)[0]; a, b = struct.unpack_from(f + 'HH', d, o)
            print('  +0x%03x %08x  %10d  (%5d, %5d)%s' % (o, w, w, a, b, ' ptr' if o in ptr else ' id' if o in ids else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
