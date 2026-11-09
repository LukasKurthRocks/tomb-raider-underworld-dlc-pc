"""Find 32-bit words with given values in every script section (type 8) of a DRM (read-only): which script holds a
text id / constant, at which offset, and whether that word is an id relocation (N15 package H 2026-11-09: who shows the
DLC 2 hint-box texts 1296 / 1322 and the "OBJECTIVE / HINT REVEALED" lines 1297 / 1316 of the title-update locals?).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/script_word_find.py SOURCE VALUE[,VALUE..] [SOURCE ...]
    SOURCE as tools/script_func_list.sections (a PC DRM file, or pc:/xbox:/dlc:/xtu: NAME.drm); values decimal or 0x..
    prints 'SOURCE script ID +OFF value V [id-reloc type T]' per hit (word-aligned), then 'hits N'
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    vals = set(int(x, 0) for x in argv[1].split(','))
    srcs = [argv[0]] + argv[2:]
    n = 0
    for src in srcs:
        S, e = FL.sections(src)
        E = '>' if e == 'be' else '<'
        for ty, sid, d, rl in S:
            if ty != 8 or not d:
                continue
            ids = R.parse(rl, e).id_offsets() if rl else {}
            for o in range(0, len(d) - 3, 4):
                w = struct.unpack_from(E + 'I', d, o)[0]
                if w in vals:
                    n += 1
                    extra = ' id-reloc type %d' % ids[o] if o in ids else ''
                    print('%s script %d +0x%x value %d%s' % (src, sid, o, w, extra))
    print('hits %d' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
