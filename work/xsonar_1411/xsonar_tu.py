"""xsonar 1411 (read-only): find the Xbox TU twins of the PC sonar globals in the TU image (for TruXenia `sonar`).

Usage (from trudlcport):
  ../bin/pyt work/xsonar_1411/xsonar_tu.py dis ADDR N          N instructions from ADDR
  ../bin/pyt work/xsonar_1411/xsonar_tu.py ea LO HI            loads / stores / addi whose address = lis base + d is in
                                                              [LO, HI) (base register tracked from its lis, <= 64 ins,
                                                              forgotten at b / blr / bctr) - candidates, verify with dis
  ../bin/pyt work/xsonar_1411/xsonar_tu.py low16 VALUE         li / addi / addis / ori / oris / cmpwi / cmplwi with
                                                              that 16-bit immediate
  ../bin/pyt work/xsonar_1411/xsonar_tu.py calls TARGET        bl TARGET
  ../bin/pyt work/xsonar_1411/xsonar_tu.py fn ADDR             start of the function around ADDR (previous `mflr r12`
                                                              or the word after the previous blr)
  ../bin/pyt work/xsonar_1411/xsonar_tu.py data ADDR N         N words from ADDR (hex + float)
  ../bin/pyt work/xsonar_1411/xsonar_tu.py str TEXT ...        VA of each ASCII occurrence
  ../bin/pyt work/xsonar_1411/xsonar_tu.py words ADDR=WORD ... proof words: compare each word with the image (exit 1
                                                              on a mismatch)
Image: work/xenia_dump/tu_image_82000000.bin (guest base 0x82000000). Output: addresses, words, instruction text only.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
import capstone  # noqa: E402

BASE = 0x82000000
TU = os.path.join(ROOT, 'work', 'xenia_dump', 'tu_image_82000000.bin')
CODE_LO, CODE_HI = 0x820c0000, 0x82700000
MEM_OPS = {32: 'lwz', 33: 'lwzu', 34: 'lbz', 35: 'lbzu', 36: 'stw', 37: 'stwu', 38: 'stb', 39: 'stbu', 40: 'lhz',
           42: 'lha', 44: 'sth', 48: 'lfs', 50: 'lfd', 52: 'stfs', 54: 'stfd', 14: 'addi'}


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def word(d, va):
    return struct.unpack_from('>I', d, va - BASE)[0]


def dis(d, lo, n):
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    for k in range(n):
        va = lo + 4 * k
        w = word(d, va)
        ins = list(md.disasm(struct.pack('>I', w), va))
        print('0x%08x  %08x  %s' % (va, w, ('%s %s' % (ins[0].mnemonic, ins[0].op_str)) if ins else '.word'))


def is_flow_end(w):
    op = w >> 26
    return (op == 18 and not w & 1) or (op == 19 and ((w >> 1) & 0x3ff) in (16, 528) and (w >> 21) & 31 == 20)


def ea_scan(d, lo, hi):
    his = {}
    for va in range(CODE_LO, min(CODE_HI, BASE + len(d)) - 3, 4):
        w = word(d, va)
        op = w >> 26
        rt, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
        if op == 15 and ra == 0:                                   # lis rt, imm
            his[rt] = (va, (imm << 16) & 0xffffffff)
            continue
        if op in MEM_OPS and ra in his and va - his[ra][0] <= 256:
            ea = (his[ra][1] + s16(imm)) & 0xffffffff
            if lo <= ea < hi:
                print('0x%08x  %08x  %s r%d, 0x%08x (lis r%d at 0x%08x)' % (va, w, MEM_OPS[op], rt, ea, ra, his[ra][0]))
        if op in MEM_OPS and op not in (36, 37, 38, 39, 44, 52, 54) and rt in his and rt != ra:
            del his[rt]                                            # rt overwritten by a load / addi
        if op == 18 and w & 1:                                     # bl: volatile registers are gone
            his = {r: v for r, v in his.items() if r >= 13}
        elif is_flow_end(w):
            his = {}


def main(a):
    d = open(TU, 'rb').read()
    mode = a[0]
    if mode == 'dis':
        dis(d, int(a[1], 16), int(a[2]))
    elif mode == 'ea':
        ea_scan(d, int(a[1], 16), int(a[2], 16))
    elif mode == 'low16':
        v = int(a[1], 0) & 0xffff
        for va in range(CODE_LO, min(CODE_HI, BASE + len(d)) - 3, 4):
            w = word(d, va)
            op = w >> 26
            if op in (10, 11, 14, 15, 24, 25) and (w & 0xffff) == v:
                print('0x%08x  %08x  op %d r%d r%d' % (va, w, op, (w >> 21) & 31, (w >> 16) & 31))
    elif mode == 'calls':
        t = int(a[1], 16)
        for va in range(CODE_LO, min(CODE_HI, BASE + len(d)) - 3, 4):
            w = word(d, va)
            if w >> 26 == 18 and w & 3 == 1:
                off = w & 0x03fffffc
                if off & 0x02000000:
                    off -= 0x04000000
                if (va + off) & 0xffffffff == t:
                    print('0x%08x  %08x  bl 0x%08x' % (va, w, t))
    elif mode == 'fn':
        va = int(a[1], 16)
        while va > CODE_LO:
            w = word(d, va)
            if w == 0x7d8802a6:
                print('0x%08x  mflr r12' % va)
                return
            if w == 0x4e800020 and va != int(a[1], 16):
                print('0x%08x  (after blr at 0x%08x)' % (va + 4, va))
                return
            va -= 4
    elif mode == 'data':
        lo, n = int(a[1], 16), int(a[2])
        for k in range(n):
            va = lo + 4 * k
            w = word(d, va)
            print('0x%08x  %08x  %g' % (va, w, struct.unpack('>f', struct.pack('>I', w))[0]))
    elif mode == 'str':
        for t in a[1:]:
            b = t.encode('latin1')
            i = d.find(b)
            while i >= 0:
                print('%-40s 0x%08x' % (t[:40], BASE + i))
                i = d.find(b, i + 1)
    elif mode == 'words':
        bad = 0
        for item in a[1:]:
            ad, wd = item.split('=')
            got = word(d, int(ad, 16))
            ok = got == int(wd, 16)
            bad += 0 if ok else 1
            print('%s %s expected %s got 0x%08x' % ('OK  ' if ok else 'FAIL', ad, wd, got))
        print('%d words, %d mismatches' % (len(a) - 1, bad))
        return 1 if bad else 0
    else:
        raise SystemExit('unknown mode ' + mode)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
