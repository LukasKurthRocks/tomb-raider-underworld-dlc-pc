"""Printable strings of one archive record (any type, e.g. a voice .mul), read-only - to see whether a voice stream
carries its subtitle text (voice-line question 06.11.).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/arch_record_strings.py SRC PATH|0xHASH [SPEC] [--min N] [--utf8]
      SRC = archive key of tools/locals.SRC; PATH below the platform root (e.g. audio\\streams\\vo\\lara\\x.mul) or a hash;
      SPEC hex spec word (default: every record of that hash); --min N minimum length (default 12)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc


def main(argv):
    mn = 12
    if '--min' in argv:
        k = argv.index('--min'); mn = int(argv[k + 1]); del argv[k:k + 2]
    utf8 = '--utf8' in argv
    if utf8: argv.remove('--utf8')
    import locals as LC
    path, e, pre = LC.SRC[argv[0]]
    A = Archive(path, e)
    h = int(argv[1], 16) if argv[1].lower().startswith('0x') else crc(pre + '\\' + argv[1])
    spec = int(argv[2], 16) if len(argv) > 2 else None
    seen = set()
    for r in A.find(h, spec):
        if r['spec'] in seen: continue
        seen.add(r['spec'])
        d = A.read(r)
        rx = rb'(?:[\x20-\x7e]|[\xc2-\xf4][\x80-\xbf]+){%d,}' % mn if utf8 else rb'[\x20-\x7e]{%d,}' % mn
        ss = [(m.start(), m.group()) for m in re.finditer(rx, d)]
        print('== %08x spec %08x size %d: %d strings' % (h, r['spec'], len(d), len(ss)))
        for o, s in ss: print('  +0x%x %s' % (o, s.decode('utf-8', 'replace')[:200]))


if __name__ == '__main__':
    main(sys.argv[1:])
