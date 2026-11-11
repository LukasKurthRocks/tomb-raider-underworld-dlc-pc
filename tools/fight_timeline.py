"""State-change timeline of one object id in a TruFight.log copy (PC, TruMenu fight.trace) or a TruXenia TSV (Xbox),
read-only (2026-11-11, night package Q18): one line per change of (instance, state0) with LP, position and Lara's
position - where a tutorial thrall appears (hall02: in the pit under generator 10028, z about -1640), where it dies and
where Lara stands.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/fight_timeline.py LOG [OBJ_ID] [FROM_TIME] [TO_TIME]     OBJ_ID default 1004, times HH:MM:SS
"""
import sys


def main(argv):
    obj = argv[1] if len(argv) > 1 else '1004'
    t0 = argv[2] if len(argv) > 2 else ''
    t1 = argv[3] if len(argv) > 3 else '99'
    rows = open(argv[0], encoding='utf-8', errors='replace').read().splitlines()
    head = rows[0].split('\t')
    ix = {n: i for i, n in enumerate(head)}
    xbox = 'pos_x' in ix
    last = {}
    for ln in rows[1:]:
        c = ln.split('\t')
        if len(c) < len(head) or c[ix['obj_id']] != obj:
            continue
        t = c[ix['host_time']]
        if not (t0 <= t <= t1):
            continue
        inst, st = c[ix['inst']], c[ix['state0']]
        if last.get(inst) == st:
            continue
        last[inst] = st
        if xbox:
            pos = '%s %s %s' % (c[ix['pos_x']], c[ix['pos_y']], c[ix['pos_z']])
            lara = c[ix['lara_pos']]
        else:
            pos = '%s %s %s' % (c[ix['pc_x']], c[ix['pc_y']], c[ix['pc_z']])
            lara = '%s %s %s' % (c[ix['pc_lara_x']], c[ix['pc_lara_y']], c[ix['pc_lara_z']])
        print('%s %s %-16s LP %-7s pos %-26s Lara %s' % (t, inst, st, c[ix['lp']], pos, lara))


if __name__ == '__main__':
    main(sys.argv[1:])
