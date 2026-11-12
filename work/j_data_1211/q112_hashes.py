"""Q112 (b), read-only: hashes for the report - raw record md5 of the DLC DRMs that carry a base-game DRM name
(Xbox base vs pack), and for chosen section keys the normalised content hashes (first 8 hex) on the Xbox base side
(per source) and in the packs (q112_scan.pkl).

Usage (from trudlcport): ../bin/pyt -t 300 work/j_data_1211/q112_hashes.py OUT_DIR TYPE:ID [TYPE:ID ...]
"""
import sys, os, pickle, collections


def main(out, keys):
    D = pickle.load(open(os.path.join(out, 'q112_scan.pkl'), 'rb'))
    print('== DRM records with a base-game name')
    for pk, i, h, spec, name, secs, md5, path in D['dlc']:
        if not secs: continue
        hits = {k[2]: v for k, v in D['base_rec_md5'].items() if k[0] == h and k[1] == spec}
        if hits:
            print('  %-7s %-28s pack md5 %s  base %s' % (pk, name, md5[:8], ', '.join('%s %s' % (s, v[0][:8]) for s, v in sorted(hits.items()))))
    for k in keys:
        t, i = (int(x) for x in k.split(':'))
        b = D['base'].get((t, i), {})
        print('== section %d:%d  Xbox base contents: %s' % (t, i, '; '.join('%s (%s, %d DRMs)' % (h[:8], '/'.join(sorted({s for s, _ in v})), len(v)) for h, v in b.items())))
        c = collections.defaultdict(set)
        for pk, _, _, _, name, secs, _, _ in D['dlc']:
            for tt, ii, size, hh in secs or []:
                if (tt, ii) == (t, i): c[(pk, hh[:8], size)].add(name)
        for (pk, hh, size), names in sorted(c.items()):
            print('   %-7s %s %6d B  %d DRMs  e.g. %s' % (pk, hh, size, len(names), sorted(names)[0]))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
