"""Find x86 loops in a 32-bit PE (tru.exe) that step a register by a record size and read a field of the record
(read-only; 2026-11-06 TruMenu 0.15 render mode: who walks the TerrainGroup array of a level's Terrain (0x50-byte
records) and reads the collision mesh pointer +0x38).

Linear sweep of the executable sections with capstone. A hit = `add REG, STRIDE` (or `lea REG, [REG + STRIDE]`) with
an instruction in the WINDOW instructions before it that reads `[REG + DISP]`. Prints the step and the read; read the
hits in context with tools/pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_stride_field_scan.py EXE STRIDE DISP [--window 24]
  e.g. ../data/pc/tru.exe 0x50 0x38
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    window = 24
    if '--window' in argv:
        k = argv.index('--window')
        window = int(argv[k + 1])
        del argv[k:k + 2]
    if len(argv) != 3: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    stride, disp = int(argv[1], 16), int(argv[2], 16)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = 0
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        ins = list(md.disasm(exe[rptr:rptr + size], sva))
        for i, a in enumerate(ins):
            reg = None
            if a.mnemonic == 'add' and len(a.operands) == 2 and a.operands[0].type == x86.X86_OP_REG and \
                    a.operands[1].type == x86.X86_OP_IMM and a.operands[1].imm == stride:
                reg = a.operands[0].reg
            elif a.mnemonic == 'lea' and len(a.operands) == 2 and a.operands[1].type == x86.X86_OP_MEM and \
                    a.operands[1].mem.base == a.operands[0].reg and a.operands[1].mem.index == 0 and \
                    a.operands[1].mem.disp == stride:
                reg = a.operands[0].reg
            if reg is None: continue
            for b in ins[max(0, i - window):i]:
                if any(o.type == x86.X86_OP_MEM and o.mem.base == reg and o.mem.disp == disp for o in b.operands):
                    hits += 1
                    print('0x%08x  %s %s   <- 0x%08x  %s %s' % (a.address, a.mnemonic, a.op_str, b.address, b.mnemonic,
                                                               b.op_str))
                    break
    print('%d hit(s): step 0x%x with a read of [reg + 0x%x]' % (hits, stride, disp))


if __name__ == '__main__':
    main(sys.argv[1:])
