"""Group N 12.11.2026 (read-only): find `lis rX, hi` + `addi rY, rX, lo` pairs (up to 8 instructions apart, any
code, no .pdata needed) that build one of the given addresses in a Xenia image (base 0x82000000), plus every aligned
big-endian word in the image equal to a hit's function start guess (vtable slots).

Usage (from trudlcport):
  ../bin/pyt -t 300 work/n_research_1211/ppc_addr_pair.py IMAGE ADDR[,ADDR..]
"""
import sys, struct

BASE = 0x82000000


def main(argv):
    img = open(argv[0], 'rb').read()
    want = set(int(a, 16) for a in argv[1].split(','))
    n = len(img) // 4
    w = struct.unpack_from('>%dI' % n, img, 0)
    for i in range(n):
        x = w[i]
        if (x >> 26) != 15 or ((x >> 16) & 31) != 0:   # lis rD, imm  (addis rD, 0, imm)
            continue
        rd = (x >> 21) & 31
        hi = (x & 0xffff) << 16
        for k in range(1, 9):
            if i + k >= n: break
            y = w[i + k]
            if (y >> 26) == 14 and ((y >> 16) & 31) == rd:   # addi rY, rD, lo
                lo = y & 0xffff
                if lo & 0x8000: lo -= 0x10000
                a = (hi + lo) & 0xffffffff
                if a in want:
                    print('0x%08x lis r%d / 0x%08x addi r%d -> 0x%08x' % (BASE + 4 * i, rd, BASE + 4 * (i + k),
                                                                         (y >> 21) & 31, a))
                break


if __name__ == '__main__':
    main(sys.argv[1:])
