"""Find code in a 32-bit PE (tru.exe) that writes two byte fields of the same base register close together
(read-only; N7 2026-11-09: who builds the light set {+2 count byte, +3 flags byte (bits 4-5 shadow count), +4 light
pointers} that the slot mapper 0x5042b0 consumes?).

Linear sweep over the executable sections with capstone; for every `mov/or/and/add byte ptr [reg + A], ...` it looks for
a second byte write `[same reg + B]` within WINDOW instructions.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_byte_field_writers.py EXE A B [WINDOW]     e.g. ../data/pc/tru.exe 2 3 12
Output: one line per hit 'VA_first VA_second reg text1 | text2', then 'hits N'.
"""
import sys
import os
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

WRITES = ('mov', 'or', 'and', 'add', 'sub', 'inc', 'dec', 'xor')


def byte_write(ins):
    """(base register, displacement) when ins writes a byte memory operand, else None"""
    if ins.mnemonic not in WRITES or not ins.operands:
        return None
    op = ins.operands[0]
    if op.type != capstone.x86.X86_OP_MEM or op.size != 1:
        return None
    if op.mem.index != 0 or op.mem.base == 0:
        return None
    return ins.reg_name(op.mem.base), op.mem.disp


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        return 2
    exe, da, db = a[0], int(a[1], 0), int(a[2], 0)
    win = int(a[3], 0) if len(a) > 3 else 12
    data = open(exe, 'rb').read()
    _, secs = PE.sections(data)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = 0
    for name, sva, rptr, size, chars in secs:
        if not (chars & 0x20000000):          # IMAGE_SCN_MEM_EXECUTE
            continue
        code = data[rptr:rptr + size]
        insns = list(md.disasm(code, sva))
        for i, ins in enumerate(insns):
            w = byte_write(ins)
            if not w or w[1] != da:
                continue
            for j in range(max(0, i - win), min(len(insns), i + win + 1)):
                w2 = byte_write(insns[j])
                if w2 and w2[0] == w[0] and w2[1] == db:
                    print('%08x %08x %s %s %s | %s %s' % (ins.address, insns[j].address, w[0], ins.mnemonic,
                          ins.op_str, insns[j].mnemonic, insns[j].op_str))
                    hits += 1
                    break
    print('hits %d' % hits)
    return 0


if __name__ == '__main__':
    sys.exit(main())
