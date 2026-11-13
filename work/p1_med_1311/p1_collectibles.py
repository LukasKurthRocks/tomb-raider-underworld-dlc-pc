"""P1 (2026-11-13): collectibles and reward containers per unit, with the reward index (read-only).

For every intro whose object name holds '_rw_' (placed reward: artifact / treasure / shard) or '_pt_' + 'reward' /
'weightbreak' (breakable container) or a name given with --also: unit, intro uid, object, live position (data - Level
+0x80 origin, as TruMenu), intro +0x52, per-instance script, and the intro data words +0x30 (reward index, TruMenu 0.20
CoRewardIndex: [[inst+0x100]+0x78]+0x30) and +0x34 / +0x38. Units are given as DRM files.

Usage (from trudlcport):
  ../bin/pyt -t 600 work/p1_med_1311/p1_collectibles.py UNIT.drm [UNIT.drm ...] [--also REGEX] [--tsv OUT.tsv]
"""
import sys, os, re, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import manor_gate_scan as MG

NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'generic', 'lists', 'pc_objectlist.txt')


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def kind(nm, also):
    n = nm.lower()
    if '_rw_' in n:
        for k in ('artifact', 'treasure', 'shard'):
            if k in n: return k
        return 'reward'
    if '_pt_' in n and ('reward' in n or 'weightbreak' in n):
        return 'pot_reward' if 'reward' in n else 'pot_empty'
    if also and re.search(also, nm, re.I): return 'other'
    return None


def main(argv):
    also = opt(argv, '--also')
    tsv = opt(argv, '--tsv')
    if not argv:
        print(__doc__); return 2
    names = MG.load_names(NAMES)
    rows = []
    for path in argv:
        us = MG.UnitScan(path, names)
        for it in us.intros:
            k = kind(it['name'], also)
            if k is None: continue
            p = us.live(it['pos'])
            w = it['data'][2] if it['data'] else ()
            g = lambda o: w[o // 4] if len(w) > o // 4 else None
            rows.append((us.name, it['uid'], it['name'], k, p, it['w52'], it['script'] or 0, g(0x30), g(0x34), g(0x38)))
    out = open(tsv, 'w', encoding='utf-8', newline='\n') if tsv else None
    if out: out.write('unit\tuid\tobject\tkind\tx\ty\tz\tw52\tscript\td30\td34\td38\n')
    for r in rows:
        u, uid, nm, k, p, w52, sc, a, b, c = r
        fx = lambda v: '-' if v is None else '%d' % v
        print('%-22s %6d %-28s %-10s (%9.1f %9.1f %9.1f) +0x52 %5d script %5d  d30 %s d34 %s d38 %s' % (
            u, uid, nm, k, p[0], p[1], p[2], w52, sc, fx(a), fx(b), fx(c)))
        if out:
            out.write('\t'.join([u, str(uid), nm, k, '%.1f' % p[0], '%.1f' % p[1], '%.1f' % p[2], str(w52), str(sc),
                                 fx(a), fx(b), fx(c)]) + '\n')
    print('%d rows' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
