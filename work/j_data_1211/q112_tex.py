"""Q112 (b), read-only: how different are the changed base-id sections of a given type (default 5 = texture) - per
row of q112_detail.tsv: share of differing bytes between the DLC section and the Xbox base copy, first differing
offset, and the 'ours' verdict. Summary per pack / DRM.

Usage (from trudlcport): ../bin/pyt -t 1800 work/j_data_1211/q112_tex.py OUT_DIR [TYPE]
"""
import sys, os, csv, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'work', 'j_data_1211'))
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import q112_detail as QD


def main(out, typ):
    rows = [r for r in csv.DictReader(open(os.path.join(out, 'q112_detail.tsv'), encoding='utf-8'), delimiter='\t')
            if r['type'] == str(typ) and r['base_holder']]
    agg = collections.defaultdict(list)
    lines = []
    for r in rows:
        pk, drm, xid = r['pack'], r['drm'], int(r['xbox_id'])
        dl = QD.secs_of(('dlc', pk, drm), lambda: QD.read_rec([QD.DLC_ROOT + QD.PACKS[pk]], 'be', drm))
        b = QD.secs_of(('base', r['base_holder']), lambda: QD.read_rec(QD.BASE, 'be', r['base_holder']))
        d, x = dl[(typ, xid)][0], b[(typ, xid)][0]
        n = min(len(d), len(x))
        diff = sum(1 for i in range(n) if d[i] != x[i]) + abs(len(d) - len(x))
        first = next((i for i in range(n) if d[i] != x[i]), n)
        frac = diff / max(len(d), 1)
        agg[(pk, drm)].append((frac, r['ours']))
        lines.append('%s\t%s\t%d\t%d\t%.4f\t0x%x\t%s' % (pk, drm, xid, len(d), frac, first, r['ours']))
    with open(os.path.join(out, 'q112_type%d_bytes.tsv' % typ), 'w', encoding='utf-8') as f:
        f.write('pack\tdrm\txbox_id\tsize\tdiff_frac\tfirst_diff\tours\n' + '\n'.join(lines) + '\n')
    for (pk, drm), v in sorted(agg.items()):
        fr = sorted(x[0] for x in v)
        oc = collections.Counter(x[1] for x in v)
        print('%-7s %-55s n %3d  diff min %.3f med %.3f max %.3f  ours %s' % (pk, drm, len(v), fr[0], fr[len(fr) // 2], fr[-1], dict(oc)))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
