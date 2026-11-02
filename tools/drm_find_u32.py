"""Find u32 values in every section of a DRM file (read-only; test 48l 2026-11-01: where the bad VM literal
0x04b10000 popped by the anim native tru+0x448100 comes from - a big-endian u32 1201 converted as two u16).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_find_u32.py DRM ENDIAN VALUE[,VALUE..] [--ctx N]
  ENDIAN: le (PC file) or be (Xbox original); VALUE hex; --ctx N prints N words before / after each hit (default 2)
Output per hit: section index, type, id, offset, the words around it ('*' = the hit, 'P' = relocated pointer).
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    ctx = 2
    if '--ctx' in argv: k = argv.index('--ctx'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    e = argv[1]
    f = '<' if e == 'le' else '>'
    D = DW.read(open(argv[0], 'rb').read(), e)
    vals = set(int(x, 16) for x in argv[2].split(','))
    n = 0
    for si, s in enumerate(D.sections):
        d = bytes(s.data)
        try:
            it = dict(R.parse(bytes(s.reloc), e).internal) if s.reloc else {}
        except Exception:
            it = {}
        for o in range(0, len(d) - 3, 4):
            if struct.unpack_from(f + 'I', d, o)[0] not in vals: continue
            n += 1
            words = []
            for p in range(max(0, o - 4 * ctx), min(len(d) - 3, o + 4 * ctx + 1), 4):
                words.append('%s%08x%s' % ('*' if p == o else '', struct.unpack_from(f + 'I', d, p)[0], 'P' if p in it else ''))
            print('section %4d type %2d id %6d +0x%06x: %s' % (si, s.type, s.id, o, ' '.join(words)))
    print('%d hits' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
