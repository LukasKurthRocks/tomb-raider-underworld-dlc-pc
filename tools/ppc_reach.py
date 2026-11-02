"""Which of a set of Xbox functions can be reached by direct calls from given root functions (read-only; wall run
2026-11-01: which of the title-update attach-geometry functions with type-22 branches lie under Lara's wall-run
state slots). Breadth-first over the `bl` calls of tools/ppc_xrefs.py (indirect calls through vtables / bctrl are
not followed, so "not reached" means "not reached by direct calls").

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_reach.py IMAGE ROOT[,ROOT..] FIND[,FIND..] [--depth N]
Prints, for every FIND function reached, the shortest call path from a root.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as X


def main(argv):
    depth = 6
    if '--depth' in argv: k = argv.index('--depth'); depth = int(argv[k + 1]); del argv[k:k + 2]
    funcs, res = X.cached(argv[0])
    starts = set(f[0] for f in funcs)
    roots = [int(x, 16) for x in argv[1].split(',')]
    find = set(int(x, 16) for x in argv[2].split(','))
    callees = {}
    for fs, items in res.items():
        callees[fs] = sorted(set(v for x, k, v in items if k == 'call' and v in starts))
    for r in roots:
        prev = {r: None}; front = [r]
        for _ in range(depth):
            nxt = []
            for f in front:
                for c in callees.get(f, ()):
                    if c not in prev:
                        prev[c] = f; nxt.append(c)
            front = nxt
        hits = [f for f in find if f in prev]
        print('root 0x%08x: %d functions within depth %d, %d of the wanted reached' % (r, len(prev), depth, len(hits)))
        for h in sorted(hits):
            p = []; f = h
            while f is not None: p.append(f); f = prev[f]
            print('   0x%08x  via %s' % (h, ' <- '.join('0x%08x' % q for q in p)))


if __name__ == '__main__':
    main(sys.argv[1:])
