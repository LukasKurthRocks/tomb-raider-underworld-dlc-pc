"""Q113 Paket R: print the expected TruTrace 0.3.1 lines (MOVE / HIT / SAVE skeletons, '...' = values of the run) for
paket_r_expected.tsv - the same formats as src/asi/TruTrace/TruTrace.cpp MoveUnitEnter / PortalEnter / SaveEnter.
Usage (from trudlcport): ../bin/pyt -t 60 work/q113_chain_1211/paket_r_lines.py EXPECTED.tsv OUT.txt
"""
import sys


def main(exp, out):
    rows = [ln.rstrip('\n').split('\t') for ln in open(exp, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
    L = []
    for r in rows:
        step, u, uid, frm, fid, hit, cps, cines, ch, sure, note = (r + [''] * 11)[:11]
        L.append('# step %s  %s%s%s  %s' % (step, u, ('  chapter ' + ch) if ch else '', ('  cutscenes ' + cines) if cines else '', sure))
        if frm:
            alt = hit.split(' / ')
            L.append("[portal] HIT stream portal %s (record 0x... '%s') in unit %s '%s' to unit %s '%s' by inst 0x... obj ... "
                     "intro ... (player) at ..." % (alt[0] + (' (or %s)' % ' / '.join(alt[1:]) if len(alt) > 1 else ''), u, fid, frm, uid, u))
            L.append("[level]  MOVE into a new stream unit: %s '%s' -> %s '%s' (player +0xe0; 0x5dfc8e); player ..." % (fid, frm, uid, u))
        else:
            L.append("[level]  PLACEMENT in unit %s '%s' (...)  (or MOVE into %s from the save's unit)" % (uid, u, u))
        for c in [c for c in cps.split(',') if c]:
            L.append("[save]   SAVE_SaveGame(0) by CHECKPOINT reached (checkpoint message handler 0x6a1a70): inst 0x... obj ... "
                     "checkpoint intro %s at ..., unit +0xe0 %s; ..." % (c, uid))
            L.append("[save]   SAVE_SaveGame done: checkpoint copy now unit '%s', checkpoint id +0x90 %s, ..." % (u, c))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('%d steps, %d lines -> %s' % (len(rows), len(L), out))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
