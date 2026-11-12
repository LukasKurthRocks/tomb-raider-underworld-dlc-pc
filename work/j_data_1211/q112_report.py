"""Q112 (b), read-only: evaluate q112_scan.pkl (work/j_data_1211/q112_scan.py).

Per pack and section type: new / base-same / base-old / changed (definitions in q112_scan.py).
Record level: pack records with a base name (name hash + spec) - raw md5 equal or not.
Changed sections: grouped by (type, Xbox id) with the packs / DRMs that carry the changed version, sizes, the base
holders (how many base DRMs, which), and whether the DLC copies agree among themselves.
Writes OUT_DIR/q112_changed.tsv (one row per changed (pack, DRM, type, id)).

Usage (from trudlcport): ../bin/pyt -t 900 work/j_data_1211/q112_report.py OUT_DIR
"""
import sys, os, pickle, collections

TYPES = {0: 'general', 2: 'anim', 5: 'texture', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shader', 10: 'material',
         11: 'Obj', 12: 'mesh', 13: 'type13'}


def main(out):
    D = pickle.load(open(os.path.join(out, 'q112_scan.pkl'), 'rb'))
    base, dlc = D['base'], D['dlc']
    cls = collections.defaultdict(collections.Counter)
    changed = collections.defaultdict(list)       # (t, id) -> [(pack, drm, size, hash)]
    rows = []
    for pk, i, h, spec, name, secs, md5, path in dlc:
        if not secs: continue
        for t, sid, size, hh in secs:
            b = base.get((t, sid))
            if b is None: c = 'new'
            elif any(s != 'retail-old' for s in (x[0] for x in b.get(hh, []))): c = 'base-same'
            elif hh in b: c = 'base-old'
            else: c = 'changed'
            cls[pk][(c, t)] += 1
            if c in ('changed', 'base-old'):
                changed[(t, sid)].append((pk, name, size, hh, c))
    print('== section classes per pack (type: new / base-same / base-old / changed)')
    for pk in sorted(cls):
        C = cls[pk]
        ts = sorted({t for _, t in C})
        print(pk, ' | '.join('%s %d/%d/%d/%d' % (TYPES.get(t, t), C[('new', t)], C[('base-same', t)], C[('base-old', t)],
                                                 C[('changed', t)]) for t in ts))
    print('\n== record level: pack records with a base-game name')
    brm = D['base_rec_md5']
    for pk, i, h, spec, name, secs, md5, path in dlc:
        hits = {k[2]: v for k, v in brm.items() if k[0] == h and k[1] == spec}
        if not hits: continue
        print('  %-7s %-60s spec %08x  base: %s' % (pk, name, spec & 0xffffffff,
              ', '.join('%s %s' % (src, ('raw-equal' if v[0] == md5 else 'raw-different') if md5 else '(no DRM, md5 not taken)')
                        for src, v in sorted(hits.items()))))
    print('\n== changed base sections: %d keys' % len(changed))
    bytype = collections.Counter()
    with open(os.path.join(out, 'q112_changed.tsv'), 'w', encoding='utf-8') as f:
        f.write('type\txbox_id\tclass\tpack\tdrm\tsize\tdlc_hash\tbase_contents\tbase_sizes\tbase_holders\n')
        for (t, sid), lst in sorted(changed.items()):
            b = base[(t, sid)]
            holders = sorted({n for v in b.values() for _, n in v})
            bsizes = sorted({s for (src, n, s) in D['basekeys'].get((t, sid), [])})
            dl_h = {x[3] for x in lst}
            bytype[(t, lst[0][4])] += 1
            for pk, name, size, hh, c in lst:
                f.write('%d\t%d\t%s\t%s\t%s\t%d\t%s\t%d\t%s\t%s\n' % (t, sid, c, pk, name, size, hh[:8], len(b),
                        ','.join(map(str, bsizes)), ';'.join(holders[:6]) + (';+%d' % (len(holders) - 6) if len(holders) > 6 else '')))
    print('changed keys per type/class:', {('%s' % TYPES.get(t, t), c): n for (t, c), n in sorted(bytype.items())})
    # per pack: changed keys and DRMs
    perpack = collections.defaultdict(lambda: collections.defaultdict(set))
    for (t, sid), lst in changed.items():
        for pk, name, size, hh, c in lst: perpack[pk][(t, c)].add(sid)
    for pk in sorted(perpack):
        print('  %s: %s' % (pk, {('%s' % TYPES.get(t, t), c): len(v) for (t, c), v in sorted(perpack[pk].items())}))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
    main(sys.argv[1])
