"""Map any title-update (TU) code address to the retail exe, also code without a .pdata entry (read-only; 2026-11-02,
TU function comparison item L2: 0x8237e050 / 0x823df8f8 are leaf entry points that tools/ppc_xrefs.py does not list).

For ADDR the TU functions around it (the one containing it, else the nearest before and after) give retail
candidates through work/tu_funcdiff/pairs.tsv (tools/tu_func_pair.py): retail = ADDR - TU function start + retail
partner start. Each candidate is checked by comparing the opcode skeletons (tools/tu_func_pair.py skel: registers,
immediates, branch targets dropped) of N instructions from both addresses; the best candidate is printed with its
match share, plus the retail function / .pdata entry it falls into and, if any, its PC partner from
work/xmap/xbox_pc_map.tsv.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tu_to_retail.py RETAIL.bin TU.bin ADDR[,ADDR..] [--n 24] [--pairs work/tu_funcdiff/pairs.tsv]
       [--map work/xmap/xbox_pc_map.tsv]
Only addresses and match shares are printed.
"""
import sys, os, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import tu_func_pair as TP


def main(argv):
    n, pairs_path, map_path = 24, 'work/tu_funcdiff/pairs.tsv', 'work/xmap/xbox_pc_map.tsv'
    for opt in ('--n', '--pairs', '--map'):
        if opt in argv:
            k = argv.index(opt); v = argv[k + 1]; del argv[k:k + 2]
            if opt == '--n': n = int(v)
            elif opt == '--pairs': pairs_path = v
            else: map_path = v
    if len(argv) != 3:
        sys.exit(__doc__)
    rd, rsecs = P.load(argv[0])
    td, tsecs = P.load(argv[1])
    rf, tf = P.pdata(rd, rsecs), P.pdata(td, tsecs)
    t2r = dict((r['tu'], r['retail']) for r in TP.read_pairs(pairs_path) if r['tu'] and r['retail'])
    pcmap = {}
    with open(map_path, encoding='utf-8') as f:
        f.readline()
        for line in f:
            v = line.rstrip('\n').split('\t')
            pcmap[int(v[0], 16)] = (int(v[1], 16), v[8])
    ts = [f[0] for f in tf]
    for a in [int(x, 16) for x in argv[2].split(',')]:
        i = bisect.bisect_right(ts, a) - 1
        cands = set()
        for j in range(max(0, i - 3), min(len(tf), i + 4)):
            s = tf[j][0]
            if s in t2r:
                cands.add(a - s + t2r[s])
        best = None
        sk_t = [TP.skel(w) for w in TP.words(td, a, a + 4 * n)]
        for c in cands:
            sk_r = [TP.skel(w) for w in TP.words(rd, c, c + 4 * n)]
            m = sum(1 for x, y in zip(sk_t, sk_r) if x == y) / float(n)
            if not best or m > best[1]:
                best = (c, m)
        if not best:
            print('TU 0x%08x: no paired TU function nearby' % a); continue
        c, m = best
        f = P.func_of(rf, c)
        own = f and f[0] == c
        pc = pcmap.get(c)
        print('TU 0x%08x -> retail 0x%08x (skeleton match %d %% of %d instructions)%s%s' % (
            a, c, 100 * m, n, (' = .pdata start' if own else (' inside retail 0x%08x' % f[0]) if f else
                               ' (no .pdata entry)'),
            ('; PC 0x%08x (%s)' % pc) if pc else '; no PC partner in the map'))


if __name__ == '__main__':
    main(sys.argv[1:])
