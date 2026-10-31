"""Find 16- / 32-bit values in the (decoded) sections of DRM files (read-only; finding 43, rock vein).

Example: the title update's player state conditions 607 / 608 ("attached / jump-target markup has type 23 / 22",
SCCondTest_MarkupType) - which DLC 2 player / level data references them.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_find_values.py FILE.drm [FILE2 ...] --values 607,608 [--be] [--u16] [--align N]
  --u16    also search 16-bit values (default: 32-bit only)
  --align  alignment of the hits (default 4 for 32-bit, 2 for 16-bit)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    be = '--be' in argv; u16 = '--u16' in argv
    argv = [a for a in argv if a not in ('--be', '--u16')]
    k = argv.index('--values'); vals = [int(x, 0) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    align = None
    if '--align' in argv:
        k = argv.index('--align'); align = int(argv[k + 1]); del argv[k:k + 2]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    for path in argv:
        D = DW.read(open(path, 'rb').read(), e)
        hits = 0
        for s in D.sections:
            d = s.data
            for v in vals:
                pats = [(struct.pack(f + 'I', v), align or 4, 'u32')]
                if u16:
                    pats.append((struct.pack(f + 'H', v), align or 2, 'u16'))
                for pat, al, kind in pats:
                    i = d.find(pat)
                    while i >= 0:
                        if i % al == 0:
                            print('%s type %d id %d +0x%05x %s %d' % (os.path.basename(path), s.type, s.id, i, kind, v))
                            hits += 1
                        i = d.find(pat, i + 1)
        print('== %s: %d hits' % (os.path.basename(path), hits))


if __name__ == '__main__':
    main(sys.argv[1:])
