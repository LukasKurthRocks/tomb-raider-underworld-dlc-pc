"""Print whole entries of the localised string tables (read-only), with word and character counts - for matching
voice lines to their text by length (voice-line question 06.11.).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/locals_dump.py SOURCE FROM TO [--spec HEX]     SOURCE as in tools/locals.py (pack11, tu, ...)
      every entry FROM..TO (inclusive); --spec: only the table with this spec word (e.g. fffff7e1 = English)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC


def main(argv):
    spec = None
    if '--spec' in argv:
        k = argv.index('--spec'); spec = int(argv[k + 1], 16); del argv[k:k + 2]
    src, lo, hi = argv[0], int(argv[1]), int(argv[2])
    f, e = LC.files(src)
    for sp, b in sorted(f.items()):
        if spec is not None and sp != spec: continue
        _, s, _ = LC.parse(b, e)
        print('== %s spec %08x: %d strings' % (src, sp, len(s)))
        for i in range(lo, min(hi, len(s) - 1) + 1):
            t = s[i].decode('utf-8', 'replace')
            print('[%d] (%d words, %d chars) %s' % (i, len(t.split()), len(t), t.replace('\n', ' / ')))


if __name__ == '__main__':
    main(sys.argv[1:])
