"""Find PowerPC code that sets given bits in a structure word (read-only; 2026-11-02: who sets meter flag 2, the bit
the shadow look 0x823d8a80 waits for before it sets flag 4 = condition 1055?).

Pattern: `ori / oris rA, rS, IMM` (or `li rA, IMM`) whose value has a bit of MASK, followed within --window
instructions (default 6) by `stw rA, DISP(rX)` - the usual read-modify-write of a flag word. Scans the code sections of
the image word by word (no disassembler needed); read the hits in context with tools/ppc_dis128.py.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_flag_writers.py IMAGE DISP MASK [--window N]
  e.g. work/xenia_dump/tu_image_82000000.bin 4 2        (stw to +4 after ori with bit 2)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS


def main(argv):
    win = 6
    if '--window' in argv: k = argv.index('--window'); win = int(argv[k + 1]); del argv[k:k + 2]
    d = open(argv[0], 'rb').read()
    disp = int(argv[1], 16); mask = int(argv[2], 16)
    base = 0x82000000
    hits = 0
    for name, start, size, ch in XS.sections(d, base):
        if not (ch & 0x20): continue
        off = start - base
        n = min(size, len(d) - off) // 4
        w = struct.unpack_from('>%dI' % n, d, off)
        for i in range(n):
            op = w[i] >> 26
            rs, ra, imm = (w[i] >> 21) & 31, (w[i] >> 16) & 31, w[i] & 0xffff
            if op == 24: val, dst, kind = imm, ra, 'ori r%d, r%d, 0x%x' % (ra, rs, imm)             # ori rA,rS,imm
            elif op == 25: val, dst, kind = imm << 16, ra, 'oris r%d, r%d, 0x%x' % (ra, rs, imm)     # oris
            elif op == 14 and ra == 0: val, dst, kind = imm, rs, 'li r%d, 0x%x' % (rs, imm)          # li rD,imm
            else: continue
            if not (val & mask) or (op == 24 and rs == ra == 0): continue
            for j in range(i + 1, min(n, i + 1 + win)):
                x = w[j]
                st = None
                if x >> 26 == 36 and (x >> 21) & 31 == dst and x & 0xffff == disp: st = 'stw'
                # big-endian byte store of the word's low byte (+3), sth of the low half (+2)
                if x >> 26 == 38 and (x >> 21) & 31 == dst and x & 0xffff == disp + 3 and val & mask & 0xff: st = 'stb'
                if x >> 26 == 44 and (x >> 21) & 31 == dst and x & 0xffff == disp + 2 and val & mask & 0xffff: st = 'sth'
                if st:
                    print('0x%08x  %-24s -> 0x%08x %s r%d, 0x%x(r%d)' % (start + 4 * i, kind, start + 4 * j, st, dst,
                                                                        x & 0xffff, (x >> 16) & 31))
                    hits += 1
                    break
                if (x >> 21) & 31 == dst and x >> 26 not in (36, 38, 44): break     # register overwritten (rough)
    print('%d hits' % hits)


if __name__ == '__main__':
    main(sys.argv[1:])
