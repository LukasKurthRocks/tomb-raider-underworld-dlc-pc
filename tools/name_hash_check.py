"""Check candidate file names against the DLC name hashes (read-only).

Hash = CRC-32/BZIP2 of the lower-case path, as in dlc_names.py (fcrc). Each candidate is tried as given and with the
prefixes 'xenon-w\\' and 'xenon-w\\audio\\streams\\' (and with '.mul' appended when it has no extension), so names as they
appear in scripts / trees can be passed directly ('/' is turned into '\\').

Usage:
  python3 -I tools/name_hash_check.py [--names work/generic/dlc_names.txt] NAME [NAME ...]
  python3 -I tools/name_hash_check.py --file candidates.txt
Output: one line per candidate: the hash of each tried form and, when it matches a record of the names file, the record
(and whether that record is still unnamed '?'). Exit 0 always (it only reports).
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlc_names import fcrc, W

PREFIXES = ('', 'xenon-w\\', 'xenon-w\\audio\\streams\\')


def forms(name):
    n = name.strip().replace('/', '\\').lstrip('\\')
    out = []
    for p in PREFIXES:
        for s in ((n,) if os.path.splitext(n)[1] else (n, n + '.mul')):
            f = (p + s) if not s.lower().startswith('xenon-w\\') else s
            if f not in out: out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('names', nargs='*', help='candidate names')
    ap.add_argument('--file', help='text file with one candidate per line')
    ap.add_argument('--names-file', default=os.path.join(W, 'dlc_names.txt'), help='dlc_names.txt to match against')
    a = ap.parse_args()
    cands = list(a.names)
    if a.file:
        cands += [l.strip() for l in open(a.file, encoding='utf8', errors='ignore') if l.strip() and not l.startswith('#')]
    recs = {}
    if os.path.exists(a.names_file):
        for l in open(a.names_file, encoding='latin1'):
            p = l.split()
            if p and p[0].startswith('0x'): recs.setdefault(int(p[0], 16), []).append(l.rstrip('\n'))
    print('names file', a.names_file, 'records', sum(len(v) for v in recs.values()),
          'unnamed', sum(1 for v in recs.values() for l in v if l.endswith(' ?')))
    hits = 0
    for c in cands:
        found = False
        for f in forms(c):
            h = fcrc(f)
            if h in recs:
                found = True; hits += 1
                for l in recs[h]:
                    print('MATCH 0x%08x %s  <- %s%s' % (h, f, l, '  (was unnamed)' if l.endswith(' ?') else ''))
        if not found:
            print('none  %s (forms: %s)' % (c, ', '.join('%s=0x%08x' % (f, fcrc(f)) for f in forms(c))))
    print('candidates', len(cands), 'matching forms', hits)


if __name__ == '__main__':
    main()
