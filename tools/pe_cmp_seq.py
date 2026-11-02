"""Find x86 code in a 32-bit PE (tru.exe) that compares against a given sequence of small constants within a short
window (read-only; 2026-11-02, TU function comparison item L2: the PC partner of the retail leaf 0x823dd7a8, which
tests a mode word for 0xc, 7, 3, 4 in a row and has no .pdata entry / no mapped caller).

Byte patterns (no disassembler): `cmp r32, imm8` (83 F8+r ib), `cmp r/m32, imm8` with [reg+disp8 / disp32]
(83 78+r d8 ib, 83 B8+r d32 ib), `cmp eax, imm32` (3D id), `cmp r32, imm32` (81 F8+r id). A hit = every constant of
the list found in that order, each within WINDOW bytes of the previous one. Prints the address of the first compare
and the function start guess (the address after the last int3 run before it).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_cmp_seq.py EXE IMM[,IMM..] [--window 24]
  e.g. "<game folder>/tru.exe" 0xc,7,3,4
Only addresses are printed.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_pc_funcmap as FM


def cmps(t):
    """[(offset, value)] of the compare forms above"""
    out = []
    n = len(t)
    for i in range(n - 6):
        b = t[i]
        if b == 0x83:
            m = t[i + 1]
            if 0xf8 <= m <= 0xff:
                out.append((i, t[i + 2] - 256 if t[i + 2] & 0x80 else t[i + 2]))
            elif 0x78 <= m <= 0x7f and m != 0x7c:
                out.append((i, t[i + 3] - 256 if t[i + 3] & 0x80 else t[i + 3]))
            elif 0xb8 <= m <= 0xbf and m != 0xbc:
                out.append((i, t[i + 6] - 256 if t[i + 6] & 0x80 else t[i + 6]))
        elif b == 0x3d:
            out.append((i, struct.unpack_from('<i', t, i + 1)[0]))
        elif b == 0x81 and 0xf8 <= t[i + 1] <= 0xff:
            out.append((i, struct.unpack_from('<i', t, i + 2)[0]))
    return out


def main(argv):
    win = 24
    if '--window' in argv:
        k = argv.index('--window'); win = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 2:
        sys.exit(__doc__)
    Pc = FM.PC(argv[0])
    seq = [int(x, 0) for x in argv[1].split(',')]
    t, va = Pc.text, Pc.tva
    c = cmps(t)
    hits = 0
    for k, (o, v) in enumerate(c):
        if v != seq[0]:
            continue
        last, j, ok = o, k + 1, True
        for want in seq[1:]:
            while j < len(c) and c[j][0] - last <= win and c[j][1] != want:
                j += 1
            if j < len(c) and c[j][0] - last <= win and c[j][1] == want:
                last = c[j][0]; j += 1
            else:
                ok = False; break
        if ok:
            s = o
            while s > 1 and not (t[s - 1] == 0xcc and t[s - 2] == 0xcc):
                s -= 1
            print('0x%08x  sequence %s, function start guess 0x%08x' % (va + o, argv[1], va + s))
            hits += 1
    print('%d hits' % hits)


if __name__ == '__main__':
    main(sys.argv[1:])
