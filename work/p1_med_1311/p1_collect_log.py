"""P1 (2026-11-13): which reward indices a played session collected, from TruTrace 'gamedata:' lines (read-only).

Game block [0xc59264] (TruTrace watches it at buffer +0): collected bits +0x3ed90 + (index >> 3), bit (index & 7)
(the engine tests dwords, 0x5db6ca; little-endian bytes give the same bit); counters +0x3ee90 + (kind * 16 + c) * 4
(kind 1 treasure, 2 relic; c = chapter column of DTP 36, p1_reward_table.py): chapter 1 treasures +0x3eed4, relic
+0x3ef14. Each 'gamedata:' line lists changed ranges '+0xOFF (data+0xOFF) N: old bytes -> new bytes' (cut with '..'
after some ranges - a range past the cut is lost; the counters are printed to check that).
Prints per change: time, unit, newly set indices (with --tsv: where they lie), the chapter-1 counters; at the end
the final bit set and, with --chapter-indices, the indices of a record that were never set.

Usage (from trudlcport):
  ../bin/pyt -t 300 work/p1_med_1311/p1_collect_log.py TruTrace.log [--tsv collect.tsv] [--chapter-indices 1,2,..]
"""
import sys, re


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


BITS0, BITS1 = 0x3ed90, 0x3ed90 + 0x40     # 512 indices are far more than the 206 of DTP 36
CNT = {0x3eed4: 'treasures ch1', 0x3ef14: 'relics ch1', 0x3eed0: 'treasures col0', 0x3ef10: 'relics col0'}


def main(argv):
    tsv = opt(argv, '--tsv')
    want = opt(argv, '--chapter-indices')
    if not argv:
        print(__doc__); return 2
    place = {}
    if tsv:
        for ln in open(tsv, encoding='utf-8').read().splitlines()[1:]:
            f = ln.split('\t')
            if f[9] != '-' and f[3] in ('artifact', 'treasure', 'shard', 'reward', 'pot_reward'):
                place[int(f[9])] = '%s %s %s' % (f[0], f[1], f[2])
    rx = re.compile(r'\+0x([0-9a-f]+) \(data\+0x[0-9a-f]+\) (\d+): ([0-9a-f ]+?) -> ([0-9a-f ]+?)(?: \.\.)?(?:;|$)')
    bits = bytearray(BITS1 - BITS0)
    cnt = {}
    for ln in open(argv[0], encoding='utf-8', errors='replace'):
        if 'gamedata:' not in ln or '0x3e' not in ln: continue
        t = ln[11:23]
        m = re.search(r'\[([^\]]*)\]', ln)
        unit = m.group(1) if m else '?'
        new, cchg = [], []
        for mm in rx.finditer(ln):
            off = int(mm.group(1), 16)
            nb = [int(x, 16) for x in mm.group(4).split()]
            ob = [int(x, 16) for x in mm.group(3).split()]
            for k, b in enumerate(nb):
                o = off + k
                if BITS0 <= o < BITS1:
                    old = bits[o - BITS0]
                    if ob[k] != old:
                        new.append('(byte +0x%x old %02x, replay had %02x)' % (o, ob[k], old))
                    for bit in range(8):
                        if b & (1 << bit) and not old & (1 << bit): new.append(str((o - BITS0) * 8 + bit))
                        if old & (1 << bit) and not b & (1 << bit): new.append('-%d' % ((o - BITS0) * 8 + bit))
                    bits[o - BITS0] = b
                for c0 in CNT:
                    if c0 <= o < c0 + 4 and k == 0 and o == c0:
                        cnt[CNT[c0]] = b
                        cchg.append('%s %d -> %d' % (CNT[c0], ob[0], b))
        if new or cchg:
            print('%s [%s] new: %s | %s' % (t, unit, ', '.join(
                '%s%s' % (x, (' = ' + place[int(x)]) if x.isdigit() and int(x) in place else '') for x in new) or '-',
                '; '.join(cchg)))
    have = [i for i in range(len(bits) * 8) if bits[i >> 3] & (1 << (i & 7))]
    print('final set: %d indices: %s' % (len(have), ' '.join(map(str, have))))
    print('final counters: %s' % ', '.join('%s %d' % kv for kv in sorted(cnt.items())))
    if want:
        w = [int(x) for x in want.split(',')]
        miss = [i for i in w if i not in have]
        print('of %d wanted indices %d not set: %s' % (len(w), len(miss), ', '.join(
            '%d%s' % (i, (' = ' + place[i]) if i in place else '') for i in miss)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
