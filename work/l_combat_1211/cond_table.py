"""Group L 12.11. (read-only): dump the chart registration tables of tru.exe as 12-byte records {u32 id, u32 group,
u32 handler} (conditions / activities / states), aligned to a known record, from START back and forward while the
handler lies in .text (0x401000..0x800000) or the record is a {0, 0, default} terminator.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/cond_table.py EXE ANCHOR_VA [ID ...]
  without IDs: every record; with IDs (decimal): only records whose id is listed (all occurrences)."""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size:
            return rptr + a - sva
    return -1


def main(a):
    exe = open(a[0], 'rb').read()
    base, secs = PE.sections(exe)
    anchor = int(a[1], 16)
    want = set(int(x) for x in a[2:])

    def rec(va):
        o = off_of(secs, va)
        if o < 0:
            return None
        return struct.unpack_from('<III', exe, o)

    def ok(r):
        return r is not None and (0x401000 <= r[2] < 0x800000) and r[0] < 0x10000 and r[1] < 0x10000
    va = anchor
    while ok(rec(va - 12)):
        va -= 12
    start = va
    n = 0
    while ok(rec(va)):
        r = rec(va)
        if not want or r[0] in want:
            print('0x%08x  id %5d  group %5d  handler 0x%08x' % (va, r[0], r[1], r[2]))
        va += 12
        n += 1
    print('# table 0x%08x .. 0x%08x, %d records' % (start, va, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
