"""Find memory ranges in an x86 minidump in which every dword fits a bit mask (read-only; night analysis N5
04.11.2026, F16: the FMOD output object at 0x0533c9f0 held only values <= 0x1fff, as if every dword of the block
had been ANDed with 0x1fff).

Scans [FROM, TO) in pages of PAGE bytes (default 0x1000). A page counts as "masked" when every dword d satisfies
d & ~MASK == 0 and at least MINNZ dwords are non-zero (all-zero pages are reported as "zero" and break nothing:
they do not end a masked run). Prints each run of masked pages (with zero pages inside) and, for the first pages
of every run, a short sample. With --edges it also prints the dwords around the start and the end of every run.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/mem_mask_scan.py DUMP FROM TO [--mask 0x1fff] [--minnz 8] [--page 0x1000] [--edges]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minidump_read import Minidump


def arg(name, default):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    d = Minidump(sys.argv[1])
    lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
    mask = int(arg('--mask', '0x1fff'), 16)
    minnz = int(arg('--minnz', '8'))
    page = int(arg('--page', '0x1000'), 16)
    edges = '--edges' in sys.argv
    inv = ~mask & 0xffffffff
    runs = []
    cur = None   # [start, end, masked_pages, zero_pages]
    stats = {'masked': 0, 'zero': 0, 'other': 0, 'missing': 0}
    va = lo
    while va < hi:
        b = d.read(va, page)
        if b is None or len(b) < page:
            kind = 'missing'
        else:
            w = struct.unpack('<%dI' % (page // 4), b)
            nz = sum(1 for x in w if x)
            if nz == 0:
                kind = 'zero'
            elif all((x & inv) == 0 for x in w) and nz >= minnz:
                kind = 'masked'
            else:
                kind = 'other'
        stats[kind] += 1
        if kind == 'masked':
            if cur is None:
                cur = [va, va + page, 1, 0]
            else:
                cur[1] = va + page
                cur[2] += 1
        elif kind == 'zero' and cur is not None:
            cur[1] = va + page
            cur[3] += 1
        else:
            if cur is not None:
                runs.append(cur)
                cur = None
        va += page
    if cur is not None:
        runs.append(cur)
    print('range 0x%08x-0x%08x page 0x%x mask 0x%x: pages %s' % (lo, hi, page, mask, stats))
    total = 0
    for s, e, m, z in runs:
        total += m
        print('masked run 0x%08x-0x%08x  (%d KB, %d masked pages, %d zero pages)' % (s, e, (e - s) // 1024, m, z))
        if edges:
            for p in (s - 0x20, s, e - 0x20):
                b = d.read(p, 0x20)
                if b:
                    print('   0x%08x: %s' % (p, ' '.join('%08x' % x for x in struct.unpack('<8I', b))))
            b = d.read(e, 0x20)
            if b:
                print('   0x%08x: %s  (first page after the run)' % (e, ' '.join('%08x' % x for x in struct.unpack('<8I', b))))
    print('runs %d, masked pages %d' % (len(runs), total))


if __name__ == '__main__':
    main()
