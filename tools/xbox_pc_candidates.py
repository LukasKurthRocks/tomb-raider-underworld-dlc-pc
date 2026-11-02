"""PC tru.exe candidates for one Xbox retail function that tools/xbox_pc_funcmap.py did not pair (read-only;
2026-11-02, TU function comparison items L1 / L2 / L3).

Evidence, from the retail function's neighbours in the call graph that DO have a PC partner (work/xmap/xbox_pc_map.tsv,
tiers verified / anchor / unverified; contradicted pairs are skipped):
  caller  - the PC partner of a retail caller calls the candidate (the PC callee lists come from the derived PC
            function table, direct E8 / E9 calls only)
  callee  - the candidate calls the PC partner of a retail callee
  layout  - the candidate lies between the PC partners of the nearest mapped retail functions before / after it
            (both compilers keep source order)
Score = caller + callee votes (+1 inside the layout window); size ratio PC / Xbox shown (map median 0.71).
Also lists the retail callers / callees and their PC partners, so the pairing can be checked by hand.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/xbox_pc_candidates.py RETAIL.bin TRU_EXE RETAIL_ADDR[,ADDR..] [--map work/xmap/xbox_pc_map.tsv]
       [--cache work/tu_funcdiff/pc_cache.pkl] [--top 8]
Only addresses, sizes and counts are printed.
"""
import sys, os, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_pc_funcmap as FM
import tu_func_classify as TC


def load_map(path):
    m = {}
    with open(path, encoding='utf-8') as f:
        f.readline()
        for line in f:
            v = line.rstrip('\n').split('\t')
            m[int(v[0], 16)] = (int(v[1], 16), v[8], v[2])
    return m


def main(argv):
    mp, cache, top = 'work/xmap/xbox_pc_map.tsv', 'work/tu_funcdiff/pc_cache.pkl', 8
    for opt in ('--map', '--cache', '--top'):
        if opt in argv:
            k = argv.index(opt); v = argv[k + 1]; del argv[k:k + 2]
            if opt == '--map': mp = v
            elif opt == '--cache': cache = v
            else: top = int(v)
    if len(argv) != 3:
        sys.exit(__doc__)
    X = FM.Xbox(argv[0])
    pc = TC.PCInfo(argv[1], cache)
    pcalls = pc.k['calls']
    psize = pc.k['size']
    pcallers = collections.defaultdict(set)
    for f, cl in pcalls.items():
        for c in cl:
            pcallers[c].add(f)
    m = load_map(mp)
    good = dict((x, v) for x, v in m.items() if v[1] != 'contradicted')
    mx = sorted(good)
    for addr in [int(a, 16) for a in argv[2].split(',')]:
        f = TC.P.func_of(X.funcs, addr)
        if not f:
            print('0x%08x: no retail function' % addr); continue
        x = f[0]
        print('retail 0x%08x (%d B)%s' % (x, X.size[x], ('  already mapped: PC 0x%08x %s %s' % m[x]) if x in m else ''))
        votes = collections.Counter()
        why = collections.defaultdict(list)
        callers = sorted(X.callers.get(x, ()))
        callees = X.calls.get(x, [])
        print('  callers: %s' % ' '.join('0x%08x%s' % (c, ('->PC 0x%08x(%s)' % (good[c][0], good[c][1][0]))
                                                       if c in good else '') for c in callers))
        print('  callees: %s' % ' '.join('0x%08x%s' % (c, ('->PC 0x%08x(%s)' % (good[c][0], good[c][1][0]))
                                                       if c in good else '') for c in callees))
        for c in callers:
            if c in good:
                for p in pcalls.get(good[c][0], []):
                    votes[p] += 1; why[p].append('caller 0x%08x' % c)
        for c in callees:
            if c in good:
                for p in pcallers.get(good[c][0], ()):
                    votes[p] += 1; why[p].append('callee 0x%08x' % c)
        i = bisect.bisect_left(mx, x)
        lo = good[mx[i - 1]][0] if i > 0 else 0
        hi = good[mx[i]][0] if i < len(mx) and mx[i] != x else (good[mx[i + 1]][0] if i + 1 < len(mx) else 0)
        print('  layout window: PC 0x%08x (retail 0x%08x) .. 0x%08x' % (lo, mx[i - 1] if i > 0 else 0, hi))
        for p in list(votes):
            if lo < p < hi:
                votes[p] += 1; why[p].append('layout')
        taken = set(v[0] for v in m.values())
        for p, n in votes.most_common(top):
            print('    PC 0x%08x  score %d  size %d (ratio %.2f)%s  %s' % (
                p, n, psize.get(p, 0), psize.get(p, 0) / float(X.size[x]), ' [already paired]' if p in taken else '',
                ', '.join(why[p][:6])))


if __name__ == '__main__':
    main(sys.argv[1:])
