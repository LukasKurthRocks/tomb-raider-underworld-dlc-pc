"""Q89: candidate sites in tru.exe that index an instance's bone matrix array (inst+0x90, 0x40 B per bone), read only.

Linear capstone sweep over .text. A register loaded with `mov r, [b + 0x90]` is tracked for the next WINDOW
instructions (until it is overwritten); reported uses:
  fixed   memory operand [r + disp] with disp >= 0x40 -> fixed bone disp // 0x40 (row offset disp % 0x40)
  shl6    an index register shifted left by 6 (or imul 0x40) and combined with r (add / lea / [r + x])
For shl6 the instruction that last wrote the index register is printed (its source = the bone-index field), and
whether a cmp / test of that register (or of its source operand) appears between that write and the use
('bounded?' = a hint only, not a proof).

Usage (from the repository root):
  ../bin/pyt -t 600 work/q89_skeleton_1111/bone_index_sites.py EXE [--range LO HI] [--fixed-min N]
"""
import sys, os, struct
import capstone
from capstone import x86

WINDOW = 24


def text(path):
    d = open(path, 'rb').read()
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    for k in range(n):
        name, vs, va, rs, ro = struct.unpack_from('<8sIIII', d, pe + 24 + opt + 40 * k)
        if name.startswith(b'.text'):
            return d[ro:ro + rs], base + va
    raise SystemExit('no .text')


def main(argv):
    path = argv[0]
    lo, hi = 0, 1 << 32
    if '--range' in argv:
        k = argv.index('--range'); lo, hi = int(argv[k + 1], 16), int(argv[k + 2], 16)
    fmin = int(argv[argv.index('--fixed-min') + 1]) if '--fixed-min' in argv else 1
    code, va = text(path)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    hist = []          # recent instructions
    bases = {}         # reg -> (load address, age)
    shifted = {}       # reg -> (shl address, writer text)
    n_fixed = n_shl = 0
    for ins in md.disasm(code, va):
        if ins.id == 0:
            bases.clear(); shifted.clear(); hist = []
            continue
        a = ins.address
        hist.append(ins)
        if len(hist) > 40:
            hist.pop(0)
        if ins.mnemonic in ('ret', 'int3', 'jmp'):
            # keep tracking over a jmp would follow the wrong path - drop
            bases.clear(); shifted.clear()
            continue
        try:
            regs_r, regs_w = ins.regs_access()
        except Exception:
            regs_r, regs_w = [], []
        ops = ins.operands
        inrange = lo <= a < hi
        # uses of tracked bases
        for op in ops:
            if op.type == x86.X86_OP_MEM and op.mem.base in bases:
                if op.mem.index == 0 and op.mem.disp >= 0x40 and op.mem.disp // 0x40 >= fmin and inrange:
                    print('%08x fixed bone %3d (+0x%02x) %-6s %-40s base @%08x' % (
                        a, op.mem.disp // 0x40, op.mem.disp % 0x40, ins.mnemonic, ins.op_str, bases[op.mem.base][0]))
                    n_fixed += 1
                if op.mem.index in shifted and inrange:
                    s = shifted[op.mem.index]
                    print('%08x shl6 [base+idx] %-6s %-40s idx from %s | bounded? %s' % (a, ins.mnemonic, ins.op_str, s[1], s[2]))
                    n_shl += 1
        if ins.mnemonic in ('add', 'lea') and len(ops) == 2 and inrange:
            if ins.mnemonic == 'add' and ops[0].type == x86.X86_OP_REG and ops[1].type == x86.X86_OP_REG:
                r0, r1 = ops[0].reg, ops[1].reg
                if (r0 in bases and r1 in shifted) or (r1 in bases and r0 in shifted):
                    s = shifted[r1 if r1 in shifted else r0]
                    print('%08x shl6 add        %-40s idx from %s | bounded? %s' % (a, ins.op_str, s[1], s[2]))
                    n_shl += 1
        # new shifts
        if ins.mnemonic == 'shl' and len(ops) == 2 and ops[0].type == x86.X86_OP_REG and ops[1].type == x86.X86_OP_IMM \
                and ops[1].imm == 6:
            r = ops[0].reg
            src = '?'
            bounded = 'no'
            for h in reversed(hist[:-1]):
                try:
                    hr, hw = h.regs_access()
                except Exception:
                    continue
                if r in hw:
                    src = '%08x %s %s' % (h.address, h.mnemonic, h.op_str)
                    break
            for h in hist[:-1]:
                if h.mnemonic in ('cmp', 'test') and any(o.type == x86.X86_OP_REG and o.reg == r for o in h.operands):
                    bounded = 'cmp @%08x %s' % (h.address, h.op_str)
            shifted[r] = (a, src, bounded)
        else:
            for r in regs_w:
                shifted.pop(r, None)
        # base loads
        newb = None
        if ins.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == x86.X86_OP_REG and ops[1].type == x86.X86_OP_MEM \
                and ops[1].mem.disp == 0x90 and ops[1].mem.base != 0 and ops[1].mem.base != x86.X86_REG_ESP \
                and ops[1].mem.index == 0:
            newb = ops[0].reg
        for r in regs_w:
            if r != newb:
                bases.pop(r, None)
        if newb is not None:
            bases[newb] = (a, 0)
        for r in list(bases):
            ad, age = bases[r]
            if age > WINDOW:
                bases.pop(r)
            else:
                bases[r] = (ad, age + 1)
    print('# fixed-bone uses %d, shl6 uses %d' % (n_fixed, n_shl))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
