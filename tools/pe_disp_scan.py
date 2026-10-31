"""List every x86 instruction of a 32-bit PE (tru.exe) whose memory operand uses one of the given displacements
(read-only; TU state translation 2026-10-31: does the PC use gameTracker / agent fields such as +0x1260 / +0x1270
the way the Xbox does?).

Linear sweep of the executable sections with capstone (detail mode); padding / data inside .text can produce a few
false instructions, so read the hits in context (tools/pe_dis.py).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_disp_scan.py EXE DISP[,DISP..] [--from VA] [--to VA]
"""
import sys, os, struct
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    lo = hi = None
    if '--from' in argv: k = argv.index('--from'); lo = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--to' in argv: k = argv.index('--to'); hi = int(argv[k + 1], 16); del argv[k:k + 2]
    exe = open(argv[0], 'rb').read()
    want = set(int(x, 16) for x in argv[1].split(','))
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    for name, va, rptr, size, ch in secs:
        if not (ch & 0x20000000):
            continue
        start, end = va, va + size
        if lo is not None: start = max(start, lo)
        if hi is not None: end = min(end, hi)
        if start >= end:
            continue
        code = exe[rptr + start - va: rptr + end - va]
        for ins in md.disasm(code, start):
            if ins.id == 0:
                continue
            try:
                ops = ins.operands
            except capstone.CsError:
                continue
            for op in ops:
                if op.type == x86.X86_OP_MEM and (op.mem.disp & 0xffffffff) in want and op.mem.base != 0:
                    print('0x%08x  %s %s' % (ins.address, ins.mnemonic, ins.op_str))
                    break


if __name__ == '__main__':
    main(sys.argv[1:])
