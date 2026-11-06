"""Find x86 code in a 32-bit PE (tru.exe) that loads a pointer from [reg + DISP] and then tests a flag bit through it
within a few instructions (read-only; 2026-11-06 TruMenu 0.15 render mode: who reads the TerrainGroup "extra" pointer
+0x30 and tests its flags word for 0x800 = enemy-only collision, the TRLAU value).

Linear sweep of the executable sections with capstone (like tools/pe_disp_scan.py). A hit = an instruction
`mov R, dword ptr [B + DISP]` followed within WINDOW instructions by an instruction that uses R (as a register or as
the base of a memory operand, also after `mov R2, [R]`) together with the immediate MASK - or, for a mask with a set
bit in byte 1, `test/and byte ptr [R + 1], MASK >> 8` / `test Rh, MASK >> 8`. Prints the load and the test with the
instructions between them; read the hits in context with tools/pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_load_flag_scan.py EXE DISP MASK [--window 8] [--from VA] [--to VA]
  e.g. ../data/pc/tru.exe 0x30 0x800
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

HIGH = {'eax': 'ah', 'ebx': 'bh', 'ecx': 'ch', 'edx': 'dh'}


def opt(argv, name, default, conv):
    if name in argv:
        k = argv.index(name)
        v = conv(argv[k + 1])
        del argv[k:k + 2]
        return v
    return default


def main(argv):
    window = opt(argv, '--window', 8, int)
    lo = opt(argv, '--from', None, lambda s: int(s, 16))
    hi = opt(argv, '--to', None, lambda s: int(s, 16))
    if len(argv) != 3: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    disp, mask = int(argv[1], 16), int(argv[2], 16)
    want_imm = '0x%x' % mask
    byte1 = mask >> 8 if mask & 0xff == 0 and mask < 0x10000 else None
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = 0
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        ins = list(md.disasm(exe[rptr:rptr + size], sva))
        for i, a in enumerate(ins):
            if lo is not None and a.address < lo: continue
            if hi is not None and a.address >= hi: continue
            if a.mnemonic != 'mov' or len(a.operands) != 2: continue
            d, s = a.operands
            if d.type != x86.X86_OP_REG or s.type != x86.X86_OP_MEM or s.mem.disp != disp or s.size != 4: continue
            regs = {a.reg_name(d.reg)}
            for k in range(i + 1, min(i + 1 + window, len(ins))):
                b = ins[k]
                text = b.op_str
                # follow one dereference: mov R2, [R]
                if b.mnemonic == 'mov' and len(b.operands) == 2 and b.operands[0].type == x86.X86_OP_REG and \
                        b.operands[1].type == x86.X86_OP_MEM and b.operands[1].mem.base and \
                        b.reg_name(b.operands[1].mem.base) in regs and b.operands[1].mem.disp == 0:
                    regs.add(b.reg_name(b.operands[0].reg))
                    continue
                uses = any(r in text for r in regs) or any(HIGH.get(r, '#') in text for r in regs)
                if not uses or b.mnemonic not in ('test', 'and', 'or', 'bt', 'cmp'): continue
                ok = want_imm in text
                if not ok and byte1 is not None:
                    ok = text.endswith(', 0x%x' % byte1) or text.endswith(', %d' % byte1)
                    ok = ok and ('+ 1]' in text or any(HIGH.get(r, '#') in text for r in regs))
                if ok:
                    hits += 1
                    print('0x%08x  %s %s' % (a.address, a.mnemonic, a.op_str))
                    for m in ins[i + 1:k + 1]:
                        print('   0x%08x  %s %s' % (m.address, m.mnemonic, m.op_str))
                    break
    print('%d hit(s) for [reg + 0x%x] then mask 0x%x' % (hits, disp, mask))


if __name__ == '__main__':
    main(sys.argv[1:])
