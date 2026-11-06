"""Compare two dlc_names.txt files (tools/dlc_names.py output) record by record (read-only; agent pv0511, 2026-11-05).

A record = the columns before the name (hash pack spec size kind); the name is the last column ('?' = unknown).
Records are matched as multisets of their key columns, so duplicate records (same hash in several language specs)
count once each. Reports: records only in OLD / only in NEW (key differs: must be 0), records whose name changed from
'?' to a name (listed), records whose name changed from one name to another (must be 0), unknown records left in NEW.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/names_diff_check.py OLD.txt NEW.txt
Exit 0 when only '?' records got a name and nothing else changed, 1 otherwise.
"""
import sys, collections


def load(p):
    recs = collections.defaultdict(list)
    for line in open(p, encoding='utf8', errors='replace'):
        t = line.split()
        if len(t) < 6: continue
        recs[tuple(t[:5])].append(t[-1])
    return recs


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    A = load(argv[0]); B = load(argv[1])
    na = sum(len(v) for v in A.values()); nb = sum(len(v) for v in B.values())
    only_a = []; only_b = []; named = []; renamed = []; same = 0
    for k in sorted(set(A) | set(B)):
        a = sorted(A.get(k, [])); b = sorted(B.get(k, []))
        if len(a) != len(b):
            if len(a) > len(b): only_a.append((k, len(a) - len(b)))
            else: only_b.append((k, len(b) - len(a)))
        ca = collections.Counter(a); cb = collections.Counter(b)
        common = ca & cb; same += sum(common.values())
        ra = list((ca - cb).elements()); rb = list((cb - ca).elements())
        for x, y in zip(ra, rb):
            if x == '?' and y != '?': named.append((k, y))
            else: renamed.append((k, x, y))
    unknown_b = sum(v.count('?') for v in B.values()); unknown_a = sum(v.count('?') for v in A.values())
    print('OLD %s: %d records, %d unknown' % (argv[0], na, unknown_a))
    print('NEW %s: %d records, %d unknown' % (argv[1], nb, unknown_b))
    print('records unchanged %d, named (? -> name) %d, renamed (name -> other) %d, key only in OLD %d, key only in NEW %d'
          % (same, len(named), len(renamed), len(only_a), len(only_b)))
    for k, n in named: print('NAMED    %s  %s' % (' '.join(k), n))
    for k, x, y in renamed: print('RENAMED  %s  %s -> %s' % (' '.join(k), x, y))
    for k, n in only_a: print('ONLY_OLD %s  x%d' % (' '.join(k), n))
    for k, n in only_b: print('ONLY_NEW %s  x%d' % (' '.join(k), n))
    sys.exit(0 if not (renamed or only_a or only_b) else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
