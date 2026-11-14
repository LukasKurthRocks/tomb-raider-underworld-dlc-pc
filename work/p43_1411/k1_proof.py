r"""P4.4 K-1 (14.11.): typed_family_fix proof counts of fpkeys at thresholds 100 and 20 (keys, samples, held-out 2-fold
decided / wrong; in-sample contradictions are 0 by construction) - the numbers to pin when FP_MIN goes 100 -> 20.
Also the keys with 20 .. 99 samples whose held-out fold decides wrong (listed).
Usage: ../bin/pyt -t 3600 work/p43_1411/k1_proof.py OUT.txt"""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import typed_family_fix as TF, dtp_audit as DA


def main(a):
    out = open(a[0], 'w', encoding='utf-8', newline='\n')
    res = {}
    for th in (100, 20):
        TF.FP_MIN = th
        res[th] = TF.proof_counts('fpkeys')
        out.write('FP_MIN %d: %s\n' % (th, res[th])); out.flush()
    # held-out errors by key sample band (20..99 vs >= 100)
    tot, folds = TF.fp_stats(); TF.FP_MIN = 20
    band = collections.Counter(); wrongkeys = collections.Counter()
    for x, p, xb, pc, xr in DA.base_pairs():
        f = DA.fold(xb['src']); xd, pd = xb['data'], pc['data']; other = folds[1 - f]
        for o, k in DA.word_keys(xd, xr):
            c = DA.cls(xd[o:o + 4], pd[o:o + 4])
            if c == DA.ALL or c == 0: continue
            v = other.get(k); w = TF.fp_want(v, xd[o:o + 4])
            if w is None: continue
            b = 'n20_99' if v[0] < 100 else 'n100'
            band[b + '_n'] += 1
            if w != pd[o:o + 4]: band[b + '_wrong'] += 1; wrongkeys[str(k)[:120]] += 1
    out.write('held-out by band (fold sample count): %s\n' % dict(band))
    for k, n in wrongkeys.most_common(30): out.write('  wrong %d  %s\n' % (n, k))
    keys20 = sum(1 for v in tot.values() if 20 <= v[0] < 100 and max(v[1:]) == v[0])
    out.write('unanimous keys with 20..99 samples: %d\n' % keys20)
    out.close(); print(res, dict(band))


if __name__ == '__main__':
    main(sys.argv[1:])
