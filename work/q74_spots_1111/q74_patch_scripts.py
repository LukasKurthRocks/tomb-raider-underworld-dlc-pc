"""Q74 (2026-11-11): which scripts does the PC 1.1 patch generalbank (patch.000) add as resident copies, and do they
differ from the copies in the units / objects of bigfile.000 beyond the dependency list (read-only)?

For every type-8 section of the patch generalbank that the bigfile generalbank does not have, look up the same id in
the given DRMs (first hit wins), compare the data word by word and classify each differing word with
tools/script_conv.Walk labels ('dep' = dependency id list): 'same code' (only dep words differ), 'CODE DIFF' (n words),
'size differs', or 'not found in the given DRMs'.

Usage (from the repository root):
  ../bin/pyt -t 900 work/q74_spots_1111/q74_patch_scripts.py PATCH_GB.drm BIG_GB.drm UNIT.drm [UNIT.drm ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R
import script_conv as SC


def labels(d, rl):
    try:
        W = SC.Walk(d, R.parse(rl, 'le'), 'le').run()
    except Exception:
        return {}
    # word labels as tools/drm_section_worddiff.py prints them, e.g. ('dep',) for the dependency id list
    return {o: (v[0] if isinstance(v, tuple) and v else v) for o, v in W.lab.items()}


def main(argv):
    P = DW.read(open(argv[0], 'rb').read(), 'le'); B = DW.read(open(argv[1], 'rb').read(), 'le')
    have = set((s.type, s.id) for s in B.sections)
    new = [s for s in P.sections if s.type == 8 and (8, s.id) not in have]
    units = []
    for p in argv[2:]:
        D = DW.read(open(p, 'rb').read(), 'le')
        units.append((os.path.basename(p), {s.id: s for s in D.sections if s.type == 8}))
    counts = {}
    for s in new:
        hits = [(name, m[s.id]) for name, m in units if s.id in m]
        res = []
        for name, u in hits:
            a, b = bytes(u.data), bytes(s.data)
            if len(a) != len(b):
                res.append('%s: size %d (patch %d)' % (name, len(a), len(b)))
                continue
            lab = labels(a, bytes(u.reloc))
            diff = [o for o in range(0, len(a) - 3, 4) if a[o:o + 4] != b[o:o + 4]]
            code = [o for o in diff if lab.get(o) != 'dep']
            res.append('%s: %s' % (name, 'same code' if not code else 'CODE DIFF %d words' % len(code)))
        if not hits:
            cls = 'not found'
        elif all(r.endswith('same code') for r in res):
            cls = 'same code in all %d copies' % len(hits) if len(hits) > 1 else 'same code (1 copy)'
        else:
            cls = 'COPIES DIFFER (id clash)' if len(hits) > 1 else 'CODE DIFF (1 copy)'
        key = cls.split(' in all')[0]
        counts[key] = counts.get(key, 0) + 1
        print('script %5d (%5d B): %s | %s' % (s.id, len(s.data), cls, '; '.join(res)))
    print('summary: %s' % ', '.join('%s %d' % kv for kv in sorted(counts.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
