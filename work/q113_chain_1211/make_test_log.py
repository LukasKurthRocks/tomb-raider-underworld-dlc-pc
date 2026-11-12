"""Q113: write a SYNTHETIC TruTrace.log (line formats of src/asi/TruTrace/TruTrace.cpp 0.3.1) to self-test
compare_trutrace.py - an old session that must be ignored, then a session that walks paket_r_expected.tsv with two
planted deviations: checkpoints 72 / 140 swapped in l1_baldrs_tomb (-> DIFF) and the seatop -> cineseatop change without
a HIT line (-> INFO). Usage (from trudlcport): ../bin/pyt -t 60 work/q113_chain_1211/make_test_log.py EXPECTED.tsv OUT.log
"""
import sys


def main(exp, out):
    rows = [ln.rstrip('\n').split('\t') for ln in open(exp, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
    ids = {r[1]: r[2] for r in rows}
    ids.update({r[3]: r[4] for r in rows if r[3]})
    t = [0]

    def ts():
        t[0] += 1
        return '2026-11-12 21:%02d:%02d.%03d' % (t[0] // 60 % 60, t[0] % 60, t[0] % 1000)

    L = ['=== 2026-11-11 20:00:00.000 TruTrace 0.3.1 session start (pid 111) ===',
         "%s [l1_seatop] level: MOVE into a new stream unit: 3 'l1_seatop' -> 6 'l1_cineseatop' (player +0xe0; 0x5dfc8e); x" % ts(),
         '=== 2026-11-12 21:00:00.000 TruTrace 0.3.1 session start (pid 222) ===']
    first = rows[0][1]
    L.append("%s [%s] level: PLACEMENT in unit %s '%s' (from 0x005ddf9a after a level load): game data x -> y: z" % (ts(), first, ids[first], first))
    L.append("%s [%s] level: MOVE into a new stream unit: 4294967295 (not loaded) -> %s '%s' (player +0xe0; 0x5dfc8e); x" % (
        ts(), first, ids[first], first))     # assumed form of the first move after a load (must be merged, not a new visit)
    for r in rows:
        u, frm, hit, cps = r[1], r[3], r[5], [c for c in r[6].split(',') if c]
        if r[0] != '1':
            if not (frm == 'l1_seatop' and u == 'l1_cineseatop'):
                L.append("%s [%s] portal: HIT stream portal %s (record 0x12345600 '%s') in unit %s '%s' to unit %s '%s' by inst "
                         "0x0a000000 obj 1 lara intro 1 (player) at 1.0 2.0 3.0 (caller 0x005d2e9f)" % (
                             ts(), frm, hit.split(' / ')[0], u, ids[frm], frm, ids[u], u))
            L.append("%s [%s] level: MOVE into a new stream unit: %s '%s' -> %s '%s' (player +0xe0; 0x5dfc8e); player" % (
                ts(), frm, ids[frm], frm, ids[u], u))
        if u == 'l1_baldrs_tomb': cps = ['72', '140', '141']
        for c in cps:
            L.append("%s [%s] save: SAVE_SaveGame(0) by CHECKPOINT reached (checkpoint message handler 0x6a1a70): inst 0x0b000000 "
                     "obj 77 checkpoint intro %s at 1.0 2.0 3.0, unit +0xe0 %s; active data unit '%s', checkpoint id +0x90 1, "
                     "+0x114 0, mode +0x1f4 0 (placement uses +0x90); checkpoint copy before none; player" % (ts(), u, c, ids[u], u))
            L.append("%s [%s] save: SAVE_SaveGame done: checkpoint copy now unit '%s', checkpoint id +0x90 %s, +0x114 0, mode "
                     "+0x1f4 0 (placement uses +0x90)" % (ts(), u, u, c))
    open(out, 'w', encoding='utf-8', newline='\r\n').write('\n'.join(L) + '\n')
    print('%d lines -> %s' % (len(L), out))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
