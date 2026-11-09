"""Print the 32-bit words around given offsets of one script section (type 8), read-only, with id-relocation marks:
compare how the Xbox original and the converted PC file store one value (N15 package H 2026-11-09: the text ids of the
DLC 2 objective / hint notifier 26078 / 26430 and the hint triggers).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_word_at.py SOURCE SCRIPT_ID OFF[,OFF..] [--n N]
    SOURCE as tools/script_func_list.sections; OFF hex (0x..) or decimal; N words before / after (default 2)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def main(argv):
    n = 2
    if '--n' in argv:
        k = argv.index('--n'); n = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, sid = argv[0], int(argv[1])
    offs = [int(x, 0) for x in argv[2].split(',')]
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    sec = next((q for q in S if q[0] == 8 and q[1] == sid and q[2]), None)
    if sec is None:
        print('script %d not found in %s' % (sid, src))
        return 1
    d, rl = sec[2], sec[3]
    rel = R.parse(rl, e)
    ids = rel.id_offsets()
    it = dict(rel.internal)
    ext = {so for _, so, _ in rel.external}
    for off in offs:
        print('== %s script %d +0x%x' % (src, sid, off))
        for o in range(max(0, off - 4 * n), min(len(d) - 3, off + 4 * n + 1), 4):
            w = struct.unpack_from(E + 'I', d, o)[0]
            mark = ('id-reloc type %d' % ids[o]) if o in ids else ('int -> 0x%x' % it[o]) if o in it else (
                'ext' if o in ext else '')
            print('  %s+0x%04x  %08x  %10d  %s' % ('>' if o == off else ' ', o, w, w, mark))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
