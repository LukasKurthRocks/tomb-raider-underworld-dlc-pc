"""List the x86 instructions of a 32-bit PE (tru.exe) that access a field of a structure reached through a global
pointer: `mov reg, dword ptr [GLOBAL]` followed (within a short window, the register not overwritten) by a memory
operand `[reg + DISP]` with DISP in the given list (read-only; TruTrace 0.2, 2026-11-05: who writes the checkpoint
id of the game data block `[0xc59264] + 0x90`).

Linear sweep of the executable sections with capstone (like tools/pe_disp_scan.py). The register tracking is a
heuristic: it ends at a write to the register, at ret / jmp / call (eax, ecx, edx only - callee-saved registers
survive a call) and after WINDOW instructions. Read every hit in context with tools/pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_global_field_uses.py EXE GLOBAL[,GLOBAL..] DISP[,DISP..] [--window N] [--writes]
     --writes   only instructions whose first operand is the field (stores / read-modify-write)
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

VOLATILE = {x86.X86_REG_EAX, x86.X86_REG_ECX, x86.X86_REG_EDX}
FULL = {x86.X86_REG_EAX, x86.X86_REG_EBX, x86.X86_REG_ECX, x86.X86_REG_EDX, x86.X86_REG_ESI, x86.X86_REG_EDI,
        x86.X86_REG_EBP}


def main(argv):
    window = 24
    writes_only = False
    if '--window' in argv: k = argv.index('--window'); window = int(argv[k + 1]); del argv[k:k + 2]
    if '--writes' in argv: writes_only = True; argv.remove('--writes')
    exe = open(argv[0], 'rb').read()
    globs = set(int(x, 16) for x in argv[1].split(','))
    disps = set(int(x, 16) for x in argv[2].split(','))
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    hits = 0
    for name, va, rptr, size, ch in secs:
        if not (ch & 0x20000000):
            continue
        code = exe[rptr: rptr + size]
        track = {}                                   # reg -> (global, instructions left)
        for ins in md.disasm(code, va):
            if ins.id == 0:
                track = {}
                continue
            try:
                ops = ins.operands
            except capstone.CsError:
                track = {}
                continue
            # 1. field access through a tracked register
            for i, op in enumerate(ops):
                if op.type != x86.X86_OP_MEM or op.mem.base not in track or op.mem.index != 0:
                    continue
                d = op.mem.disp & 0xffffffff
                if d not in disps:
                    continue
                is_write = i == 0 and ins.mnemonic not in ('cmp', 'test', 'push')
                if writes_only and not is_write:
                    continue
                g = track[op.mem.base][0]
                print('0x%08x  %-5s [0x%08x]+0x%x  %s %s' % (ins.address, 'WRITE' if is_write else 'read', g, d,
                                                             ins.mnemonic, ins.op_str))
                hits += 1
            # 2. register bookkeeping
            mn = ins.mnemonic
            if mn.startswith('ret') or mn == 'jmp' or mn == 'int3':
                track = {}
                continue
            if mn == 'call':
                for r in VOLATILE: track.pop(r, None)
            newly = None
            if mn == 'mov' and len(ops) == 2 and ops[0].type == x86.X86_OP_REG and ops[1].type == x86.X86_OP_MEM \
                    and ops[1].mem.base == 0 and ops[1].mem.index == 0 and (ops[1].mem.disp & 0xffffffff) in globs \
                    and ops[0].reg in FULL:
                newly = ops[0].reg
                track[newly] = (ops[1].mem.disp & 0xffffffff, window)
            else:
                try:
                    _, written = ins.regs_access()
                except capstone.CsError:
                    written = []
                for r in written:
                    track.pop(r, None)
            for r in list(track):
                if r == newly: continue
                g, left = track[r]
                if left <= 1: del track[r]
                else: track[r] = (g, left - 1)
    print('%d hit(s)' % hits)


if __name__ == '__main__':
    main(sys.argv[1:])
