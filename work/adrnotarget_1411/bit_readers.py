"""Read-only: find code that tests a bit of the dword at [reg + DISP] (default CM+0x1fc bit 27) in a 32-bit PE.

Matches (within the next WINDOW instructions after a load / test of [reg + DISP]):
  shr reg, BIT ; test r8, 1          (the compiler's usual pattern in tru.exe)
  test [reg + DISP], 1 << BIT        (dword test)
  test byte [reg + DISP + BIT // 8], 1 << (BIT % 8)
  and / or with the mask
Usage (from the repository root):
  ../bin/pyt -t 900 work/adrnotarget_1411/bit_readers.py EXE OUT.txt [DISP_HEX] [BIT] [WINDOW]
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE


def main(argv):
    exe = open(argv[0], 'rb').read()
    out = argv[1]
    disp = int(argv[2], 16) if len(argv) > 2 else 0x1fc
    bit = int(argv[3]) if len(argv) > 3 else 27
    window = int(argv[4]) if len(argv) > 4 else 6
    mask = 1 << bit
    bdisp, bmask = disp + bit // 8, 1 << (bit % 8)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = []
    for name, sva, rptr, size, _ in secs:
        if not name.startswith('.text'):
            continue
        code = exe[rptr:rptr + size]
        ins_list = list(md.disasm(code, sva))
        for i, ins in enumerate(ins_list):
            if ins.id == 0:          # skipdata pseudo instruction
                continue
            mems =[op for op in ins.operands if op.type == x86.X86_OP_MEM and op.mem.base != 0]
            if not mems:
                continue
            m = mems[0].mem
            if m.disp == bdisp and ins.mnemonic == 'test':
                imms = [op.imm for op in ins.operands if op.type == x86.X86_OP_IMM]
                if imms and imms[0] & bmask:
                    hits.append((ins.address, 'byte test', ins))
                continue
            if m.disp != disp:
                continue
            if ins.mnemonic in ('test', 'and', 'or') :
                imms = [op.imm for op in ins.operands if op.type == x86.X86_OP_IMM]
                if imms and (imms[0] & 0xffffffff) & mask:
                    hits.append((ins.address, ins.mnemonic + ' mask', ins))
                    continue
            if ins.mnemonic != 'mov':
                continue
            for j in range(i + 1, min(i + 1 + window, len(ins_list))):
                n = ins_list[j]
                if n.id == 0:
                    break
                imms = [op.imm for op in n.operands if op.type == x86.X86_OP_IMM]
                if n.mnemonic == 'shr' and imms and imms[0] == bit:
                    hits.append((ins.address, 'shr %d at %08x' % (bit, n.address), ins))
                    break
                if n.mnemonic in ('test', 'and') and imms and (imms[0] & 0xffffffff) == mask:
                    hits.append((ins.address, '%s mask at %08x' % (n.mnemonic, n.address), ins))
                    break
                if n.mnemonic == 'bt' and imms and imms[0] == bit:
                    hits.append((ins.address, 'bt at %08x' % n.address, ins))
                    break
    with open(out, 'w', encoding='utf-8') as f:
        f.write('; [reg + 0x%x] bit %d readers / writers, window %d\n' % (disp, bit, window))
        for a, how, ins in hits:
            f.write('%08x  %-24s %s %s\n' % (a, how, ins.mnemonic, ins.op_str))
    print('hits', len(hits), '->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
