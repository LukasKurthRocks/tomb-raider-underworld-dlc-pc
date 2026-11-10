"""One-off (2026-11-11, TruShadowPower 0.26): the camera 'set' records (0x6c bytes, 0x5f9940 / 0x6080f0) that the TU
doppelganger settings DTP 21237 selects - TU DTP 22194 (86 records) - against the TU retail set DTP 31 and the PC set
DTP 30 (76 records each). Read-only.

For every 22194 record: word classes (float word = equal as number, byte word = equal as raw bytes; canonical form
min(x, byteswap(x)) as in cam_mode_tables.py), the internal pointers inside the record (reloc) with their target offsets
relative to the record, and the TU 31 / PC 30 records that are equal in every word except the seven floats 1..7.
Also: are all 76 TU 31 records equal to PC 30 at the same index (proof that the index layout is the same)?

Helper of tools/tu_dg_modes_inc.py (moved from work/power026_1111 in night package Q26, 2026-11-11, rules unchanged).
Usage (from the repository root): ../bin/pyt -t 300 tools/cam_set_records.py [IDX,IDX,..]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cam_mode_tables as M  # noqa: E402


def canon(x):
    """number (u32 / float), byte field (u8: raw bytes) or u16 pair (each half a number): the PC conversion keeps the
    number, the raw bytes, or the two halves - min over the three forms makes the three kinds compare equal"""
    return min(x, struct.unpack('<I', struct.pack('>I', x))[0], ((x >> 16) | (x << 16)) & 0xffffffff)


def records(sec, e):
    d = sec['data']
    n = struct.unpack_from(e + 'I', d, 0)[0]
    p = M.ptrs(sec, e)
    base = p[4]
    out = []
    for k in range(n):
        o = base + 0x6c * k
        w = struct.unpack_from(e + '27I', d, o)
        rel = {(off - o) // 4: tgt for off, tgt in p.items() if o <= off < o + 0x6c}
        out.append((o, w, rel))
    return out, base, n, len(d)


def fl(x, e):
    return struct.unpack(e + 'f', struct.pack(e + 'I', x))[0]


def main(argv):
    want = [int(x) for x in argv[0].split(',')] if argv else [0, 2, 76, 77]
    tu = records(M.tu_dtp(22194), '>')
    t31 = records(M.tu_dtp(31), '>')
    p30 = records(M.pc_dtp(30), '<')
    for name, (recs, base, n, size) in (('TU 22194', tu), ('TU 31', t31), ('PC 30', p30)):
        ptr_words = sorted({k for _, _, rel in recs for k in rel})
        print('%s: %d records at +0x%x, %d bytes; pointer words inside records: %s' % (name, n, base, size, ptr_words))
    # the pointer word targets: relative to the record table end?
    for name, (recs, base, n, size) in (('TU 22194', tu), ('TU 31', t31), ('PC 30', p30)):
        tg = sorted({tgt for _, _, rel in recs for tgt in rel.values()})
        print('%s pointer targets (data offsets): %d distinct, first %s' % (name, len(tg), [hex(x) for x in tg[:6]]))
    same_idx = sum(1 for a, b in zip(t31[0], p30[0])
                   if all(canon(x) == canon(y) for k, (x, y) in enumerate(zip(a[1], b[1])) if k not in a[2]))
    print('TU 31 vs PC 30 at the same index, all non-pointer words equal: %d of %d' % (same_idx, min(t31[2], p30[2])))
    same_tu = sum(1 for a, b in zip(tu[0], t31[0])
                  if all(canon(x) == canon(y) for k, (x, y) in enumerate(zip(a[1], b[1])) if k not in a[2]))
    print('TU 22194 vs TU 31 at the same index (0..75), all non-pointer words equal: %d of %d' % (same_tu, t31[2]))
    diff_idx = [i for i, (a, b) in enumerate(zip(tu[0], t31[0]))
                if not all(canon(x) == canon(y) for k, (x, y) in enumerate(zip(a[1], b[1])) if k not in a[2])]
    print('TU 22194 records 0..75 that differ from TU 31: %s; records 76.. only in 22194: %s' % (
        diff_idx, list(range(t31[2], tu[2]))))
    for i in want:
        o, w, rel = tu[0][i]
        print()
        print('22194[%d] at +0x%x, pointers %s' % (i, o, {k: '+0x%x' % (t - o) for k, t in rel.items()}))
        print('  floats 1..7: %s' % ' '.join('%.4g' % fl(x, '>') for x in w[1:8]))
        print('  words: %s' % ' '.join('%08x' % x for x in w))
        rest = [canon(x) for k, x in enumerate(w) if k not in rel and not 1 <= k <= 7]
        for nm, (recs, _, _, _), e in (('TU 31', t31, '>'), ('PC 30', p30, '<')):
            hits = [j for j, (_, w2, rel2) in enumerate(recs)
                    if [canon(x) for k, x in enumerate(w2) if k not in rel2 and not 1 <= k <= 7] == rest]
            print('  %s records equal outside the floats 1..7: %s' % (nm, hits))
            if i < len(recs):
                print('  %s[%d] floats 1..7: %s' % (nm, i, ' '.join('%.4g' % fl(x, e) for x in recs[i][1][1:8])))
        # where the pointer word points relative to the record table, for both sides
        for k, t in rel.items():
            print('  word %d -> data +0x%x (record table +0x%x .. +0x%x)' % (k, t, tu[1], tu[1] + 0x6c * tu[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
