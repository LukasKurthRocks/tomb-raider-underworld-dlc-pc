"""Which DRM names exist in more than one DLC pack, and are their Xbox records identical? (read-only)

Upstream's convert_dlc.raw_dlc() returns the first pack that has a name (pack10 before pack11), so for a name in both
packs every tool that looks up "the Xbox source" of a DLC 2 file gets the pack10 record. This lists those names and
whether the records are byte-identical (then it does not matter).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/pack_overlap.py [--sections]
  --sections: per shared name, which sections are only in one pack, equal, or changed (is pack11 a superset?)
"""
import sys, os, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from convert_dlc import R, PACKS

WG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def main():
    names = collections.defaultdict(set)
    for line in open(os.path.join(WG, 'dlc_names.txt'), encoding='latin1'):
        f = line.split()
        if len(f) >= 6 and f[-1].lower().endswith('.drm') and f[-1].lower().startswith('xenon-w\\'): names[f[-1]].add(f[1])
    arcs = {p.split('/')[-1].split('.')[0]: Archive(R + p, 'be') for p in PACKS}
    multi = {n: sorted(ps) for n, ps in names.items() if len(ps) > 1}
    print('DRM names in more than one pack: %d' % len(multi))
    same = diff = 0
    for n, ps in sorted(multi.items()):
        md5 = {}
        for p in ps:
            if p not in arcs: continue
            recs = [r for r in arcs[p].find(crc(n)) if r['spec'] == 0xffffffff]
            md5[p] = hashlib.md5(arcs[p].read(recs[0])).hexdigest()[:12] if recs else None
        ident = len(set(md5.values())) == 1
        same += ident; diff += not ident
        print('   %-55s %s %s' % (n, ' '.join('%s:%s' % kv for kv in md5.items()), 'identical' if ident else 'DIFFERENT'))
    print('identical %d, different %d' % (same, diff))
    if '--sections' not in sys.argv: return
    # per shared name: sections (type, id) only in one pack, in both with equal data, in both with different data
    from drm import cdrm_decode, sections_with_data
    print('sections pack10 vs pack11 (only10 / only11 / same / changed; changed listed as type:id size10->size11):')
    for n in sorted(multi):
        secs = {}
        for p in ('pack10', 'pack11'):
            recs = [r for r in arcs[p].find(crc(n)) if r['spec'] == 0xffffffff]
            secs[p] = {(s['type'], s['id']): s['data'] for s in sections_with_data(cdrm_decode(arcs[p].read(recs[0]), 'be'), 'be')[1]}
        a, b = secs['pack10'], secs['pack11']
        only10 = sorted(set(a) - set(b)); only11 = sorted(set(b) - set(a)); both = set(a) & set(b)
        changed = sorted(k for k in both if a[k] != b[k])
        print('   %-42s %3d / %3d / %3d / %3d   %s%s' % (n.split('\\')[-1], len(only10), len(only11), len(both) - len(changed),
              len(changed), ' '.join('%d:%d %d->%d' % (k[0], k[1], len(a[k] or b''), len(b[k] or b'')) for k in changed[:6]),
              ('  only10: ' + ' '.join('%d:%d' % k for k in only10[:6])) if only10 else ''))


if __name__ == '__main__':
    main()
