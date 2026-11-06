"""Language variants of the voice / speech streams of a game archive (read-only, index only - no record is read).

Groups the records under audio\\streams\\vo\\<folder> (and cinstream\\) by folder and spec word and counts, per
folder, how many stream names exist in each language (spec ffffffe1 EN/default, ffffe002 FR, ffffe004 DE,
ffffe008 IT, ffffe010 ES, ffffffff language-neutral). Names come from the Yura file list of the platform.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/vo_lang_stats.py [SRC ...] [--list REGEX]
      SRC = archive keys of tools/locals.SRC (default: pcbig pcpatch); --list prints every matching name with its specs
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L
from vo_refs_scan import LANG

ORDER = ('en', 'fr', 'de', 'it', 'es', 'all')


def main(argv):
    pat = None
    if '--list' in argv:
        i = argv.index('--list'); pat = re.compile(argv[i + 1], re.I); argv = argv[:i] + argv[i + 2:]
    srcs = argv or ['pcbig', 'pcpatch']
    import locals as LC
    per = collections.defaultdict(lambda: collections.defaultdict(set))   # folder -> lang -> names
    specs = collections.defaultdict(set)                                    # name -> langs (+ src)
    for src in srcs:
        path, e, pre = LC.SRC[src]
        names = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
        A = Archive(path, e)
        for r in A.idx:
            n = names.get(r['hash'])
            if not n: continue
            nl = n.lower()
            if '\\audio\\streams\\vo\\' in nl:
                folder = '\\'.join(nl.split('\\')[3:-1])
            elif '\\cinstream\\' in nl:
                folder = 'cinstream'
            else:
                continue
            lg = LANG.get(r['spec'], '%08x' % r['spec'])
            per[folder][lg].add(nl)
            specs[nl].add('%s:%s' % (src, lg))
    print('folder'.ljust(28) + ''.join(x.rjust(7) for x in ORDER) + '  other')
    for f in sorted(per):
        other = {k: len(v) for k, v in per[f].items() if k not in ORDER}
        print(f.ljust(28) + ''.join(str(len(per[f].get(x, ()))).rjust(7) for x in ORDER) + '  ' + (str(other) if other else ''))
    if pat:
        for n in sorted(specs):
            if pat.search(n): print('%-70s %s' % (n, ' '.join(sorted(specs[n]))))


if __name__ == '__main__':
    main(sys.argv[1:])
