"""Find strings in the localised string tables (read-only): index and text of every entry that contains a pattern,
in a source of tools/locals.py (pack10, pack11, tu, pcbig, pcpatch, ... - all its languages) or in PC files
(`locals.bin_NNN`). Finding 43 follow-up: the DLC 2 hint box ("The shadow meter drains ...") stays empty on PC.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/locals_find.py PATTERN SOURCE|FILE [...] [--index N ...]
  --index N: also print entry N of every table (e.g. the id a script asks for)
  ../bin/pyt -t 300 tools/locals_find.py --glyphs SPLIT SOURCE|FILE [...]   (button glyph code points per part)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC


def tables(src):
    """-> [(label, strings)]"""
    if os.path.exists(src):
        _, s, _ = LC.parse(open(src, 'rb').read(), 'le')
        return [(os.path.basename(src), s)]
    f, e = LC.files(src)
    out = []
    for spec, b in sorted(f.items()):
        _, s, _ = LC.parse(b, e)
        out.append(('%s spec %08x' % (src, spec), s))
    return out


def glyphs(src, split):
    """button glyphs (U+1800-U+18FF, the controller symbols inside strings): count per code point below / from index
    SPLIT (e.g. base part vs the appended DLC part of a PC table)"""
    import collections
    for label, s in tables(src):
        lo, hi = collections.Counter(), collections.Counter()
        for i, t in enumerate(s):
            for ch in t.decode('utf-8', 'replace'):
                if 0x1800 <= ord(ch) <= 0x18FF: (lo if i < split else hi)[ord(ch)] += 1
        print('== %s: below %d: %s' % (label, split, ' '.join('%04x:%d' % kv for kv in sorted(lo.items()))))
        print('   from %d: %s' % (split, ' '.join('%04x:%d' % kv for kv in sorted(hi.items()))))


def main(argv):
    if '--glyphs' in argv:
        k = argv.index('--glyphs'); split = int(argv[k + 1]); del argv[k:k + 2]
        for src in argv: glyphs(src, split)
        return
    idx = []
    while '--index' in argv:
        k = argv.index('--index'); idx.append(int(argv[k + 1])); del argv[k:k + 2]
    pat = re.compile(argv[0].encode('utf-8'), re.I)
    for src in argv[1:]:
        for label, s in tables(src):
            hits = [i for i, t in enumerate(s) if pat.search(t)]
            print('== %s: %d strings, %d hits' % (label, len(s), len(hits)))
            for i in hits[:12]:
                print('  %5d  %s' % (i, s[i][:150].decode('utf-8', 'replace')))
            for i in idx:
                print('  [%d] %s' % (i, s[i][:150].decode('utf-8', 'replace') if i < len(s) else '(no such index)'))


if __name__ == '__main__':
    main(sys.argv[1:])
