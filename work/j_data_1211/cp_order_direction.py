"""Group J (B follow-up), read-only: is the checkpoint +0x52 index of the base-game units the walking direction?

Input: the intro list of group B (tools/manor_gate_scan.py intros ... --grep "checkpoint|cinematic_object", lines
'== unit: ...', '   portal -> target   centre as stored (x y z)', '   intro N checkpoint   live (x y z) +0x52 K script S')
and B's play order (work/b_nav_1211/q105_order_table.py ORDER).
Per unit with >= 2 checkpoints (object 'checkpoint' only) and an entry portal (portal to the nearest earlier unit of the
order that has one): every pair of checkpoints with different +0x52 is concordant when the smaller +0x52 is nearer
to the entry portal (3D distance), discordant otherwise. Portal centres and intro positions are in the same frame
(checked on l1_norse_hallway_a: entry checkpoint 1 m from the seafloor portal).
Also prints how often +0x52 repeats inside a unit and the first value per unit.

Usage (from trudlcport): ../bin/pyt -t 300 work/j_data_1211/cp_order_direction.py INTROS.txt
"""
import sys, os, re, math, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'work', 'b_nav_1211'))
import q105_order_table as OT


def parse(path):
    units = {}; u = None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', ln)
        if m: u = units.setdefault(m.group(1), {'portals': {}, 'cps': [], 'cines': []}); continue
        m = re.match(r'^\s+portal -> (\S+)\s+centre as stored \((\S+) (\S+) (\S+)\)', ln)
        if m and u is not None:
            u['portals'].setdefault(m.group(1), (float(m.group(2)), float(m.group(3)), float(m.group(4)))); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+)\s+live \(\s*(\S+)\s+(\S+)\s+(\S+)\)\s+\+0x52\s+(\d+)', ln)
        if m and u is not None:
            rec = (int(m.group(1)), int(m.group(6)), (float(m.group(3)), float(m.group(4)), float(m.group(5))))
            if m.group(2) == 'checkpoint': u['cps'].append(rec)
            elif m.group(2) == 'cinematic_object': u['cines'].append(rec)
    return units


def main(path):
    U = parse(path)
    tot = collections.Counter()
    for lvl, rows in OT.ORDER.items():
        names = [r[0] for r in rows]
        for k, name in enumerate(names):
            u = U.get(name)
            if not u: continue
            vals = [c[1] for c in u['cps']]
            dup = len(vals) - len(set(vals))
            entry = None
            for prev in reversed(names[:k]):
                if prev in u['portals']: entry = prev; break
            if len(u['cps']) < 2 or entry is None:
                print('%-30s cps %d  entry %-26s  (no test)  +0x52 %s' % (name, len(u['cps']), entry, sorted(vals)))
                tot['untested'] += 1; continue
            p = u['portals'][entry]
            con = dis = 0
            cps = u['cps']
            for i in range(len(cps)):
                for j in range(i + 1, len(cps)):
                    a, b = cps[i], cps[j]
                    if a[1] == b[1]: continue
                    da, db = math.dist(a[2], p), math.dist(b[2], p)
                    if (a[1] < b[1]) == (da < db): con += 1
                    else: dis += 1
            verdict = 'ok' if dis == 0 and con else ('mixed' if con and dis else ('reversed' if dis else 'ties only'))
            tot[verdict] += 1; tot['pairs_con'] += con; tot['pairs_dis'] += dis; tot['units_dup'] += 1 if dup else 0
            order = ' '.join('%d@%.0fm' % (c[1], math.dist(c[2], p) / 100) for c in sorted(cps, key=lambda c: (c[1], c[0])))
            print('%-30s cps %d  entry %-26s  %-9s con %3d dis %3d dup %d   %s' % (name, len(cps), entry, verdict, con, dis, dup, order))
    print('TOTAL', dict(tot))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
