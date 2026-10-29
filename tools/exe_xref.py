"""Static cross-references in tru.exe (read-only): instructions that use a given memory displacement, an immediate
value, or call/jump to an address - for tracing which engine code reads or writes an object field seen in a crash
dump (finding 43).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/exe_xref.py EXE disp 0x1d4 [--write] [--range LO HI]
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/exe_xref.py EXE imm 0x4601c0
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/exe_xref.py EXE call 0x45fab0
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/exe_xref.py EXE func 0x4601c0      (disassemble until ret/int3 run)
Linear sweep over .text with capstone (skipdata), so code after data blocks is found; output: address, instruction.
"""
import sys, struct
import capstone


def text(path):
    d = open(path, 'rb').read()
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    for k in range(n):
        name, vs, va, rs, ro = struct.unpack_from('<8sIIII', d, pe + 24 + opt + 40 * k)
        if name.startswith(b'.text'): return d[ro:ro + rs], base + va
    raise SystemExit('no .text')


def main(argv):
    path, mode, val = argv[0], argv[1], int(argv[2], 16)
    write = '--write' in argv
    lo, hi = 0, 1 << 32
    if '--range' in argv: k = argv.index('--range'); lo, hi = int(argv[k + 1], 16), int(argv[k + 2], 16)
    code, va = text(path)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    if mode == 'func':
        off = val - va; n = 0
        for ins in md.disasm(code[off:off + 0x2000], val):
            print('%08x  %-7s %s' % (ins.address, ins.mnemonic, ins.op_str)); n += 1
            if ins.mnemonic in ('ret', 'int3') or n > 400: break
        return
    for ins in md.disasm(code, va):
        if ins.id == 0 or not (lo <= ins.address < hi): continue
        hit = False
        if mode == 'disp':
            for i, op in enumerate(ins.operands):
                if op.type == capstone.x86.X86_OP_MEM and op.mem.disp == val and op.mem.base != 0:
                    if not write or (i == 0 and ins.mnemonic.startswith(('mov', 'fst', 'movss'))): hit = True
        elif mode == 'imm':
            hit = any(op.type == capstone.x86.X86_OP_IMM and (op.imm & 0xffffffff) == val for op in ins.operands)
        elif mode == 'call':
            hit = ins.mnemonic in ('call', 'jmp') and ins.op_str == hex(val)
        if hit: print('%08x  %-7s %s' % (ins.address, ins.mnemonic, ins.op_str))


if __name__ == '__main__':
    main(sys.argv[1:])
