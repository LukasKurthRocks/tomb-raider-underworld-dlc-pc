"""Find x86 pointer chains in a 32-bit PE (tru.exe): a load `mov R1, [X + D1]`, then within a few instructions an
access `[R1 + D2]` (loaded into R2 for a further step), ... - the code that walks a data structure such as
object data +0xc8 -> +0xdc -> +0x50 (read-only; thrall perception floats 2026-11-05: who reads the thrall AI records).

Linear sweep of the executable sections with capstone (detail mode). A chain step follows the loaded register until it
is written again (capstone regs_access) or the window ends; the last step may be any memory access (load / store /
compare / float load). Padding / data inside .text can give a few false instructions - read hits with pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_disp_chain.py EXE D1,D2[,D3..] [--window N] [--from VA] [--to VA]
    D* hex displacements; --window instructions between two steps (default 24)
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    win = 24
    lo = hi = None
    if '--window' in argv: k = argv.index('--window'); win = int(argv[k + 1]); del argv[k:k + 2]
    if '--from' in argv: k = argv.index('--from'); lo = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--to' in argv: k = argv.index('--to'); hi = int(argv[k + 1], 16); del argv[k:k + 2]
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    disps = [int(x, 16) for x in argv[1].split(',')]
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    hits = 0
    for name, va, raw_off, size, chars in secs:
        if not chars & 0x20000000: continue
        code = exe[raw_off:raw_off + size]
        ins = []
        off = 0
        while off < len(code):
            got = False
            for i in md.disasm(code[off:], va + off):
                ins.append(i)
                off = i.address - va + i.size
                got = True
            if not got: off += 1
        for n, i in enumerate(ins):
            if lo is not None and i.address < lo: continue
            if hi is not None and i.address >= hi: continue
            if i.mnemonic != 'mov' or len(i.operands) != 2: continue
            d, s = i.operands
            if d.type != x86.X86_OP_REG or s.type != x86.X86_OP_MEM or s.mem.disp != disps[0]: continue
            reg = d.reg
            chain = [i]
            k = n
            ok = True
            for step, disp in enumerate(disps[1:], 1):
                last = step == len(disps) - 1
                found = None
                for j in range(k + 1, min(len(ins), k + 1 + win)):
                    t = ins[j]
                    mem = [o for o in t.operands if o.type == x86.X86_OP_MEM and o.mem.base == reg and o.mem.disp == disp]
                    if mem and (last or (t.mnemonic == 'mov' and t.operands[0].type == x86.X86_OP_REG)):
                        found = j
                        break
                    try:
                        _, written = t.regs_access()
                    except capstone.CsError:
                        written = []
                    if reg in written or t.mnemonic in ('ret', 'jmp'): break
                if found is None: ok = False; break
                chain.append(ins[found])
                k = found
                if not last: reg = ins[found].operands[0].reg
            if not ok: continue
            hits += 1
            print(' | '.join('%08x %s %s' % (c.address, c.mnemonic, c.op_str) for c in chain))
    print('%d chain(s) for %s' % (hits, ' -> '.join('+0x%x' % d for d in disps)))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
