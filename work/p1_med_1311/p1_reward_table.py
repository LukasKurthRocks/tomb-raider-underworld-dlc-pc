"""P1 (2026-11-13): the reward table of the PC game (read-only) - which reward index is a treasure / relic, which chapter.

Engine (tru.exe, reward pickup 0x5db6a0(index), tools/pe_dis.py 0x5db6a0 0x5db890, group N):
  collected bit = game block [0xc59264] +0x3ed90 + (index >> 5) * 4, bit (index & 31); set once (0x5db6d7), a second
  pickup of the same index is skipped (0x5db6d1).
  table T = [0xe7f338] = DTP GlobalInfo +0x194 (0x5db6ee: [[0xe7ee50]+0x194] -> 0x54df80 DTP by id) - GlobalInfo =
  generalbank DTP 2 +0xf0 (tools/globalinfo_player_list.py), so the id word is DTP 2 +0x284.
  entry = [T+4] + index * 8: {u16 c (chapter column, -1 = none), pad, u32 r}; record = [T+0x14] + r * 16: +0 kind,
  +4 count (incremented at 0x5db77f). Counter game block +0x3ee90 + (kind * 16 + c) * 4 (0x5db73d).
  The switch on c at 0x5db75a (c <= 14) re-adds the count to c = 0 / 14 / 15 (chapter groups, read here only as data).
Prints the DTP id, the record table and every index with c, r, kind; --units TSV adds where each index is placed
(the p1_collectibles.py TSV: unit / uid / object of the intro whose data +0x30 = index).

Usage (from trudlcport):
  ../bin/pyt -t 120 work/p1_med_1311/p1_reward_table.py generalbank.drm [--tsv collect.tsv] [--max N]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import drm_write as DW


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    tsv = opt(argv, '--tsv')
    mx = int(opt(argv, '--max', '400'))
    if not argv:
        print(__doc__); return 2
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    dtp = {s.id: s for s in D.sections if s.type == 7}
    g = dtp[2]
    gd = bytes(g.data)
    rid = struct.unpack_from('<I', gd, 0xf0 + 0x194)[0]
    print('GlobalInfo +0x194 (DTP 2 +0x%x) = %d (0x%x)' % (0xf0 + 0x194, rid, rid))
    if rid not in dtp:
        print('DTP %d not in %s' % (rid, argv[0])); return 1
    s = dtp[rid]
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    print('DTP %d: %d B; words +0..+0x70: %s' % (rid, len(d), ' '.join('%08x' % w for w in struct.unpack_from('<29I', d, 0))))
    print('  floats +0x58..+0x6c: %s' % ' '.join('%.2f' % f for f in struct.unpack_from('<6f', d, 0x58)))
    pe, pr = it.get(4), it.get(0x14)
    ne = struct.unpack_from('<I', d, 0)[0]
    nr = struct.unpack_from('<I', d, 0x10)[0]
    print('  entries -> +0x%s (count word +0 = %d), records -> +0x%s (count word +0x10 = %d)' % (
        '%x' % pe if pe is not None else '?', ne, '%x' % pr if pr is not None else '?', nr))
    if pe is None or pr is None: return 1
    place = {}
    if tsv:
        for ln in open(tsv, encoding='utf-8').read().splitlines()[1:]:
            f = ln.split('\t')
            if f[3] in ('artifact', 'treasure', 'shard', 'reward', 'pot_reward') and f[9] != '-':
                place.setdefault(int(f[9]), []).append('%s %s %s' % (f[0], f[1], f[2]))
    # records (16 B): +0 kind (1 treasure, 2 relic, 0 other), +4 count (runtime), +8 n, +0xc -> u32 list of indices.
    # The entry word +4 (record of an index) is -1 in the file: the init 0x5d5f80 (called once at 0x5db70a) fills it,
    # so the index -> record link is read here from the record lists.
    KIND = {0: 'other', 1: 'treasure', 2: 'relic'}
    rec_of = {}
    for r in range(min(nr, 64)):
        k, cnt, n = struct.unpack_from('<3I', d, pr + 16 * r)
        lp = it.get(pr + 16 * r + 12)
        lst = list(struct.unpack_from('<%dI' % n, d, lp)) if lp is not None and n < 1000 else []
        for i in lst: rec_of.setdefault(i, []).append(r)
        cs = sorted({struct.unpack_from('<I', d, pe + 8 * i)[0] for i in lst if i < ne})
        print('  record %2d: kind %d %-8s n %3d, column(s) c %s, indices %s' % (
            r, k, KIND.get(k, '?'), n, cs, ' '.join(str(i) for i in lst)))
    n = min(ne, mx)
    for i in range(n):
        o = pe + 8 * i
        c, r = struct.unpack_from('<Ii', d, o)
        rr = rec_of.get(i, [])
        kinds = '/'.join(KIND.get(struct.unpack_from('<I', d, pr + 16 * q)[0], '?') for q in rr) or '-'
        print('  index %3d: c %2d  file r %2d  record %-6s %-9s %s' % (i, c, r, ','.join(map(str, rr)) or '-', kinds,
                                                                   '; '.join(place.get(i, []))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
