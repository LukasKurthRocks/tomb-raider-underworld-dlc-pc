"""Raw scan of all code sections for places that build or hold an address (read-only; 2026-11-02: is the TU's meter
flag-2 setter 0x823d8978 referenced anywhere? tools/ppc_xrefs.py only covers functions listed in .pdata).

Finds, for each target address:
  * `lis rD, hi` followed within --window instructions (default 8) by `addi / ori rX, rD, lo` building the address,
  * `bl / b` (relative branches) to the address,
  * the address as an aligned big-endian word anywhere in the image (data tables, vtables, .pdata).
Code without .pdata entries (leaf handlers, stubs) is included.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_addr_scan.py IMAGE ADDR[,ADDR..] [--window N]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS


def s16(x): return x - 0x10000 if x & 0x8000 else x


def main(argv):
    win = 8
    if '--window' in argv: k = argv.index('--window'); win = int(argv[k + 1]); del argv[k:k + 2]
    d = open(argv[0], 'rb').read()
    targets = set(int(x, 16) for x in argv[1].split(','))
    base = 0x82000000
    n = len(d) // 4
    allw = struct.unpack_from('>%dI' % n, d, 0)
    for i, w in enumerate(allw):
        if w in targets: print('word   0x%08x = 0x%08x' % (base + 4 * i, w))
    for name, start, size, ch in XS.sections(d, base):
        if not (ch & 0x20): continue
        off = start - base
        m = min(size, len(d) - off) // 4
        w = struct.unpack_from('>%dI' % m, d, off)
        for i in range(m):
            op = w[i] >> 26
            va = start + 4 * i
            if op == 18:                                                    # b / bl
                li = w[i] & 0x03fffffc
                if li & 0x02000000: li -= 0x04000000
                t = (li if w[i] & 2 else va + li) & 0xffffffff
                if t in targets: print('branch 0x%08x %s 0x%08x' % (va, 'bl' if w[i] & 1 else 'b', t))
            if op == 15 and (w[i] >> 16) & 31 == 0:                         # lis rD, hi
                rd, hi = (w[i] >> 21) & 31, (w[i] & 0xffff) << 16
                for j in range(i + 1, min(m, i + 1 + win)):
                    x = w[j]; xo = x >> 26
                    src = (x >> 16) & 31 if xo == 14 else (x >> 21) & 31   # addi rD,rA,si / ori rA,rS,ui
                    if xo in (14, 24) and src == rd:
                        t = (hi + (s16(x & 0xffff) if xo == 14 else x & 0xffff)) & 0xffffffff
                        if t in targets: print('build  0x%08x lis r%d + 0x%08x %s -> 0x%08x' % (va, rd, start + 4 * j,
                                                                                            'addi' if xo == 14 else 'ori', t))
    print('done')


if __name__ == '__main__':
    main(sys.argv[1:])
