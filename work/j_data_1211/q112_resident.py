"""Q112 (b), read-only: PC-only residency clashes. For every changed base key of the DLC packs (q112_detail.tsv, all
types): does an always-loaded PC DRM (patch / bigfile `generalbank.drm`, `globalsoundinfo.drm`) hold its PC id while
no always-loaded Xbox DRM (TU / retail generalbank, globalsoundinfo) holds the Xbox id? Then the DLC copy works on
the Xbox but is shadowed on the PC (first loaded section of an id wins) - the 12433 / 8453 thrall class pattern.
Also lists keys whose holders on BOTH sides are always loaded (shadowed on both platforms).

Usage (from trudlcport): ../bin/pyt -t 900 work/j_data_1211/q112_resident.py OUT_DIR
"""
import sys, os, json, csv, pickle, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from names import load, L

RES = ('generalbank.drm', 'globalsoundinfo.drm')


def main(out):
    D = pickle.load(open(os.path.join(out, 'q112_scan.pkl'), 'rb'))
    pcn = load(L + 'Tomb Raider Underworld (PC).txt')
    pc_hold = collections.defaultdict(set)
    for rec in json.load(open('work/idx_pc.json')):
        if isinstance(rec[5], list):
            nm = pcn.get(rec[2], '%08x' % rec[2])
            for s in rec[5]: pc_hold[(s[0], s[1])].add((os.path.basename(rec[0]), nm))
    rows = list(csv.DictReader(open(os.path.join(out, 'q112_detail.tsv'), encoding='utf-8'), delimiter='\t'))
    keys = collections.defaultdict(set)
    for r in rows: keys[(int(r['type']), int(r['xbox_id']), r['pc_id'])].add((r['pack'], r['drm'], r['ours']))
    cnt = collections.Counter()
    for (t, xid, pcid), drms in sorted(keys.items()):
        xb = {(src, n) for (src, n, s) in D['basekeys'].get((t, xid), [])}
        xres = sorted({'%s:%s' % (s, n) for s, n in xb if n.endswith(RES) and s != 'retail-old'})
        pres = sorted({'%s:%s' % (a, n) for a, n in pc_hold.get((t, int(pcid)), set()) if n.endswith(RES)}) if pcid not in ('', 'None') else []
        if not pres and not xres: cnt['neither resident'] += 1; continue
        kind = 'PC-only resident' if pres and not xres else ('Xbox-only resident' if xres and not pres else 'both resident')
        cnt[kind] += 1
        packs = sorted({p for p, _, _ in drms}); ours = sorted({o for _, _, o in drms})
        print('%-18s type %d xbox %d pc %s  PC %s  Xbox %s  packs %s  %d DLC DRMs  ours %s' % (
            kind, t, xid, pcid, pres, xres, packs, len(drms), ours))
    print('TOTAL', dict(cnt))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
