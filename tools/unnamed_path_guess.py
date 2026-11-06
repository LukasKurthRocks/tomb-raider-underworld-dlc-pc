"""Name unnamed archive records from path-like strings inside DRMs (read-only).

TR Underworld data names streams by a relative path without root and extension (dialogue DTP: "vo\\dlc2\\x\\NAME",
sound DTPs: "env\\...", music: "music\\..."). tools/hidden_scan.py guess combines single tokens with known folders and
therefore misses folders no file list contains. This tool takes every path-like string (two or more segments joined by
a backslash) of the DRMs of the given archives, builds candidate archive paths with several roots / extensions and
compares their hash with the wanted (unnamed) hashes.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/unnamed_path_guess.py WANT.tsv SRC [SRC ...]
      WANT.tsv: tools/hidden_scan.py unnamed output (column 2 = hash[@spec]); SRC = archive keys of tools/locals.SRC
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from names import crc
import vo_refs_scan as V

ROOTS = ('', 'audio\\streams\\', 'audio\\', 'music\\', 'audio\\streams\\music\\', 'cinstream\\', 'image\\')
EXTS = ('.mul', '.raw', '.drm', '')


def wanted(path):
    w = set()
    for l in open(path, encoding='utf8'):
        if l.startswith('#') or not l.strip(): continue
        t = l.split('\t')
        if len(t) > 1: w.add(int(t[1].split('@')[0], 16))
    return w


def main(argv):
    want = wanted(argv[0])
    pat = r'[A-Za-z0-9_()]+\\[A-Za-z0-9_()\\]+'
    texts = set()
    for src in argv[1:]:
        hits, pre = V.scan(src, pat, 0)
        texts.update(h['text'].strip('\\').lower() for h in hits)
    print('%d wanted hashes, %d distinct path strings' % (len(want), len(texts)))
    found = {}
    for t in sorted(texts):
        for root in ROOTS:
            for ext in EXTS:
                p = 'xenon-w\\' + root + t + ext
                h = crc(p)
                if h in want: found.setdefault(h, p)
    for h, p in sorted(found.items()): print('NAMED 0x%08x = %s' % (h, p))
    print('%d of %d named' % (len(found), len(want)))


if __name__ == '__main__':
    main(sys.argv[1:])
