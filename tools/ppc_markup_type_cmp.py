"""Find Xbox 360 functions that compare a markup type byte with given values (read-only; wall run 2026-11-01: every
title-update place that special-cases the new markup types 22 / 23).

A hit is `lbz rY, D(rX)` with D in DISPS (default 0x4d = second markup type, 0x33 = record type char), followed within
WIN instructions (same function, from .pdata) by `cmpwi / cmplwi crN, rZ, V` with V in VALUES where rZ is rY or a
register derived from it by extsb / clrlwi / mr. Prints function range, the load and the compare.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_markup_type_cmp.py IMAGE [VALUES] [--disps 0x4d,0x33] [--win 12]
  VALUES default 22,23
"""
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as PX

BASE = 0x82000000


def main(argv):
    disps, win = {0x4d, 0x33}, 12
    if '--disps' in argv: k = argv.index('--disps'); disps = set(int(x, 16) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--win' in argv: k = argv.index('--win'); win = int(argv[k + 1]); del argv[k:k + 2]
    vals = set(int(x, 0) for x in argv[1].split(',')) if len(argv) > 1 else {22, 23}
    d, secs = PX.load(argv[0])
    funcs = PX.pdata(d, secs)
    for fs, fe in funcs:
        a = fs
        while a < fe:
            w = struct.unpack_from('>I', d, a - BASE)[0]
            if (w >> 26) == 34 and (w & 0xffff) in disps:          # lbz rD, D(rA)
                regs = {(w >> 21) & 31}
                for b in range(a + 4, min(fe, a + 4 * (win + 1)), 4):
                    x = struct.unpack_from('>I', d, b - BASE)[0]
                    op = x >> 26
                    rs, ra, rb = (x >> 21) & 31, (x >> 16) & 31, (x >> 11) & 31
                    if op == 31 and ((x >> 1) & 0x3ff) == 954 and rs in regs: regs.add(ra)          # extsb ra, rs
                    elif op == 21 and rs in regs: regs.add(ra)                                       # rlwinm / clrlwi
                    elif op == 31 and ((x >> 1) & 0x3ff) == 444 and rs == rb and rs in regs: regs.add(ra)  # mr
                    elif op in (10, 11) and ra in regs:                                              # cmplwi / cmpwi
                        v = x & 0xffff
                        if op == 11 and v & 0x8000: v -= 0x10000
                        if v in vals:
                            print('func 0x%08x..0x%08x  lbz 0x%x at 0x%08x  cmp%s %d at 0x%08x'
                                  % (fs, fe, w & 0xffff, a, 'wi' if op == 11 else 'lwi', v, b))
            a += 4


if __name__ == '__main__':
    main(sys.argv[1:])
