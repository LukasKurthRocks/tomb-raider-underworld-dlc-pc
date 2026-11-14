"""PK1-8 (2026-11-14): DLC 2 unit facts for the level chain (read-only), extends work/q113_chain_1211/q113_unit_facts.py.

Differences to the Q113 tool: DLC 2 units after dlc_yggdrasil_hall01 use object `dlc2_checkpoint` (object list 1036),
which the Q113 filter skips, so they are listed here too; and per unit and per possible entry portal the checkpoint order
by the Q113 key (d_in / (d_in + d_out) for units with two or more portals, d_in for one-portal units) is printed, so both
walking directions of the dlc2_* ring can be compared.

INTROS = tools/manor_gate_scan.py intros output over the DLC 2 unit DRMs (all intros, no --grep).

Usage (from trudlcport): ../bin/pyt -t 300 work/pk2_1411/pk2_unit_facts.py INTROS OUT [UID,UID,...]
  UID list: further intros (any object, e.g. the trigger volumes that broadcast the DLC 2 objective count) to list with
  their portal distances
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.getcwd(), 'work', 'q113_chain_1211'))
import q113_unit_facts as Q

CPS = ('checkpoint', 'invis_checkpoint', 'dlc2_checkpoint')
KINDS = ('player', 'cinematic_object') + CPS


def short(t):
    return t.split('_', 1)[1] if '_' in t else t


def main(intros, out, extra=''):
    U = Q.parse(intros)
    want = set(int(x) for x in extra.split(',') if x.strip())
    lines = []
    for name in sorted(U):
        u = U[name]
        lines.append('== %s  portals: %s' % (name, ', '.join('%s (%.0f %.0f %.0f)' % (t, *p) for t, p in u['portals'])))
        for it in u['intros']:
            if it['name'] not in KINDS and it['uid'] not in want: continue
            d = '  '.join('%s %.0fm' % (short(t), math.dist(it['pos'], p) / 100) for t, p in u['portals'])
            lines.append('   %-17s %6d  +0x52 %5d  (%8.0f %8.0f %8.0f)  script %5s   to portal: %s' % (
                it['name'], it['uid'], it['w52'], *it['pos'], it['script'], d))
        cps = [it for it in u['intros'] if it['name'] in CPS]
        for i, (tin, pin) in enumerate(u['portals']):
            rest = [p for j, (t, p) in enumerate(u['portals']) if j != i]
            keyed = []
            for it in cps:
                din = math.dist(it['pos'], pin)
                if rest:
                    dout = min(math.dist(it['pos'], p) for p in rest)
                    keyed.append((din / (din + dout) if din + dout else 0.0, it['uid']))
                else:
                    keyed.append((din, it['uid']))
            keyed.sort()
            lines.append('   order if entered from %-28s %s' % (tin + ':', ' '.join(
                '%d(%.2f)' % (uid, k) if rest else '%d(%.0fm)' % (uid, k / 100) for k, uid in keyed)))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('%d units -> %s' % (len(U), out))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:4]))
