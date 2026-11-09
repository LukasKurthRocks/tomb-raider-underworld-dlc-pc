"""List x86 instructions in a 32-bit PE (tru.exe) that WRITE memory at given displacements [reg + DISP]
(read-only; N7 2026-11-09: who fills the scene light list +0x1234 / +0x123c that the light-set builder 0x504cc0 walks?).

Linear capstone sweep over the executable sections; reports mov / add / sub / or / and / inc / dec / xor / lea-free
writes whose first operand is a memory operand with one of the displacements (any base register, no index).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_disp_writers.py EXE DISP[,DISP..] [--lo VA] [--hi VA]
Output: 'VA disp size mnemonic operands', then 'hits N'.
"""
import sys
import os
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

WRITES = ('mov', 'or', 'and', 'add', 'sub', 'inc', 'dec', 'xor', 'movss', 'movd', 'fstp', 'fst', 'movaps', 'movups')


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    exe = a[0]
    disps = set(int(x, 0) for x in a[1].split(','))
    lo, hi = 0, 0xffffffff
    if '--lo' in a:
        lo = int(a[a.index('--lo') + 1], 0)
    if '--hi' in a:
        hi = int(a[a.index('--hi') + 1], 0)
    data = open(exe, 'rb').read()
    _, secs = PE.sections(data)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = 0
    for name, sva, rptr, size, chars in secs:
        if not (chars & 0x20000000):
            continue
        for ins in md.disasm(data[rptr:rptr + size], sva):
            if not (lo <= ins.address < hi) or ins.mnemonic not in WRITES or not ins.operands:
                continue
            op = ins.operands[0]
            if op.type != capstone.x86.X86_OP_MEM or op.mem.index != 0 or op.mem.disp not in disps:
                continue
            print('%08x 0x%x %d %s %s' % (ins.address, op.mem.disp, op.size, ins.mnemonic, ins.op_str))
            hits += 1
    print('hits %d' % hits)
    return 0


if __name__ == '__main__':
    sys.exit(main())
