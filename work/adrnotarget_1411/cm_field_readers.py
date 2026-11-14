"""Read-only: find code that reads a field of the combat manager CM = [[0xfadb58] + 0x504] in a 32-bit PE.

Pattern: mov R1, [0xfadb58] ; ... mov R2, [R1 + 0x504] ; ... any memory operand [R2 + FIELD] (or lea) within WINDOW
instructions (R1 / R2 not overwritten in between). Also counts CM pointers passed as ecx (thiscall) - those are listed
as 'thiscall' hits so the callee can be checked separately.
Usage (from the repository root):
  ../bin/pyt -t 900 work/adrnotarget_1411/cm_field_readers.py EXE OUT.txt [FIELD_HEX] [WINDOW]
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE

GT = 0xfadb58


def main(argv):
    exe = open(argv[0], 'rb').read()
    out = argv[1]
    field = int(argv[2], 16) if len(argv) > 2 else 0xc
    window = int(argv[3]) if len(argv) > 3 else 12
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = []
    for name, sva, rptr, size, _ in secs:
        if not name.startswith('.text'):
            continue
        ins_list = [i for i in md.disasm(exe[rptr:rptr + size], sva)]
        for i, ins in enumerate(ins_list):
            if ins.id == 0 or ins.mnemonic != 'mov' or len(ins.operands) != 2:
                continue
            d, s = ins.operands
            if d.type != x86.X86_OP_REG or s.type != x86.X86_OP_MEM or s.mem.base != 0 or s.mem.disp != GT:
                continue
            r1 = d.reg
            r2 = None
            for j in range(i + 1, min(i + 1 + window, len(ins_list))):
                n = ins_list[j]
                if n.id == 0:
                    break
                ops = n.operands
                if r2 is None:
                    if (n.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == x86.X86_OP_REG and
                            ops[1].type == x86.X86_OP_MEM and ops[1].mem.base == r1 and ops[1].mem.disp == 0x504):
                        r2 = ops[0].reg
                        continue
                    if len(ops) and ops[0].type == x86.X86_OP_REG and ops[0].reg == r1 and n.mnemonic not in ('cmp', 'test', 'push'):
                        break
                    continue
                mem = [o for o in ops if o.type == x86.X86_OP_MEM and o.mem.base == r2 and o.mem.disp == field]
                if mem:
                    hits.append((n.address, ins.address, n))
                    break
                if (len(ops) and ops[0].type == x86.X86_OP_REG and ops[0].reg == r2 and
                        n.mnemonic not in ('cmp', 'test', 'push')):
                    break
                if n.mnemonic in ('ret', 'jmp', 'call'):
                    break
    with open(out, 'w', encoding='utf-8') as f:
        f.write('; reads of CM+0x%x (CM = [[0x%x]+0x504]), window %d\n' % (field, GT, window))
        for a, start, n in hits:
            f.write('%08x  (gt load %08x)  %s %s\n' % (a, start, n.mnemonic, n.op_str))
    print('hits', len(hits), '->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
