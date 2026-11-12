"""Q113 (2026-11-12): per base-game unit the facts the level chain is built from (read-only).

INTROS = tools/manor_gate_scan.py intros output over the 81 extracted base units (all intros, no --grep).
Per unit: the portals (centre as stored, same frame as the live intro positions - group J checked it on
l1_norse_hallway_a), the player intro, every checkpoint / invis_checkpoint and every cinematic_object (+0x52 = cinematic
number = story order, group J 2.2) with the distance to each portal in metres (100 units = 1 m, as J's table).

Usage (from trudlcport): ../bin/pyt -t 300 work/q113_chain_1211/q113_unit_facts.py INTROS OUT
"""
import sys, re, math


def parse(path):
    units, u = {}, None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', ln)
        if m: u = units.setdefault(m.group(1), {'portals': [], 'intros': []}); continue
        m = re.match(r'^\s+portal -> (\S+)\s+centre as stored \((\S+) (\S+) (\S+)\)', ln)
        if m and u is not None:
            u['portals'].append((m.group(1), (float(m.group(2)), float(m.group(3)), float(m.group(4))))); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+)\s+live \(\s*(\S+)\s+(\S+)\s+(\S+)\)\s+\+0x52\s+(\d+)\s+script\s+(\S+)', ln)
        if m and u is not None:
            u['intros'].append(dict(uid=int(m.group(1)), name=m.group(2), pos=(float(m.group(3)), float(m.group(4)),
                                    float(m.group(5))), w52=int(m.group(6)), script=m.group(7)))
    return units


def main(intros, out):
    U = parse(intros)
    lines = []
    for name in sorted(U):
        u = U[name]
        lines.append('== %s  portals: %s' % (name, ', '.join('%s (%.0f %.0f %.0f)' % (t, *p) for t, p in u['portals'])))
        for it in u['intros']:
            kind = it['name']
            if kind not in ('player', 'checkpoint', 'invis_checkpoint', 'cinematic_object'): continue
            d = '  '.join('%s %.0fm' % (t.split('_', 1)[1], math.dist(it['pos'], p) / 100) for t, p in u['portals'])
            lines.append('   %-17s %6d  +0x52 %5d  (%8.0f %8.0f %8.0f)  script %5s   to portal: %s' % (
                kind, it['uid'], it['w52'], *it['pos'], it['script'], d))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('%d units -> %s' % (len(U), out))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:3]))
