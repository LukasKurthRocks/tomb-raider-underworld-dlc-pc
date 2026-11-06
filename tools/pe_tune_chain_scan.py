"""Find the enemy tune-chain lookups in a 32-bit PE (tru.exe): loops of the form

    L: cmp dword ptr [R + X], 0      ; does this tune define sub-record X? (also `cmp [R + X], Z`, Z = 0
                                     ; kept in a register, and `mov R2, [R + X]; test R2, R2`)
       jne found
       mov R, dword ptr [R + 0x1c]    ; no -> parent tune
       test R, R
       jne L

and print, per tune field X, every site (read-only; thrall data fields 2026-11-06: which code reads which pointer of
an enemy tune - the DLC thrall floats sit in the records behind tune +0x94 / +0x11c).

Engine background (tru.exe Steam, static): the enemy data block [inst+0x50] (magic 0xdaf00018) holds at +0x18 a
byte count, at +0x1c a pointer to that many tune pointers and at +0x20 the default tune (0x62dd30); the brain keeps
the active tune at brain+0x168 and resolves each sub-record by walking tune -> tune+0x1c until one is non-null
(e.g. +0x30 senses data, +0x3c health data, 0x63c241 / 0x63c362).

Indexed lookups (`cmp [R + I*4 + X], 0`, an array of sub-records in the tune) are reported with the index register.
The scan is a linear capstone sweep of the executable sections; a site prints the loop address, the register, the
field X, the instruction after the found branch (often `mov R2, [R + X]`) and the enclosing function start guess
(the first byte after a run of int3 padding).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_tune_chain_scan.py EXE [--field X[,X..]] [--next 1c]
    --field  only these tune fields (hex), default all
    --next   parent link displacement (hex, default 1c)
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def func_start(code, va, a):
    i = a - va
    while i > 2:
        if code[i - 1] == 0xcc and code[i - 2] == 0xcc: return va + i
        i -= 1
    return va


def main(argv):
    fields = None
    nxt = 0x1c
    if '--field' in argv:
        k = argv.index('--field'); fields = {int(x, 16) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    if '--next' in argv:
        k = argv.index('--next'); nxt = int(argv[k + 1], 16); del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    hits = {}
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
            if len(i.operands) != 2: continue
            if i.mnemonic == 'cmp':
                # cmp [R + X], 0  or  cmp [R + X], Z  (Z a register the compiler keeps at zero)
                m, imm = i.operands
                if m.type != x86.X86_OP_MEM: continue
                if not ((imm.type == x86.X86_OP_IMM and imm.imm == 0) or imm.type == x86.X86_OP_REG): continue
            elif i.mnemonic == 'mov':
                # mov R2, [R + X] ; test R2, R2 ; jne found
                r2, m = i.operands
                if r2.type != x86.X86_OP_REG or m.type != x86.X86_OP_MEM: continue
                t = ins[n + 1] if n + 1 < len(ins) else None
                if t is None or t.mnemonic != 'test' or len(t.operands) != 2 \
                        or any(o.type != x86.X86_OP_REG or o.reg != r2.reg for o in t.operands): continue
                if r2.reg == m.mem.base: continue
            else:
                continue
            if m.mem.base == 0 or m.size != 4: continue
            reg, fld = m.mem.base, m.mem.disp
            idx = '' if m.mem.index == 0 else ' + %s*%d' % (i.reg_name(m.mem.index), m.mem.scale)
            if fields is not None and fld not in fields: continue
            # within the next 4 instructions: mov reg, [reg + nxt] and a backward jne to i
            ok = False
            found_tgt = None
            for j in range(n + 1, min(len(ins), n + 6)):
                t = ins[j]
                if t.mnemonic == 'jne' and found_tgt is None and t.operands[0].type == x86.X86_OP_IMM:
                    found_tgt = t.operands[0].imm
                if t.mnemonic == 'mov' and len(t.operands) == 2 and t.operands[0].type == x86.X86_OP_REG \
                        and t.operands[0].reg == reg and t.operands[1].type == x86.X86_OP_MEM \
                        and t.operands[1].mem.base == reg and t.operands[1].mem.disp == nxt:
                    for k in range(j + 1, min(len(ins), j + 4)):
                        u = ins[k]
                        if u.mnemonic in ('jne', 'jnz', 'jmp') and u.operands[0].type == x86.X86_OP_IMM \
                                and u.operands[0].imm <= i.address and u.operands[0].imm >= i.address - 0x20:
                            ok = True
                    break
            if not ok: continue
            after = ''
            if found_tgt is not None:
                for t in ins[n:n + 400]:
                    if t.address == found_tgt:
                        after = '%s %s' % (t.mnemonic, t.op_str)
                        break
            fs = func_start(code, va, i.address)
            hits.setdefault(fld, []).append((i.address, i.reg_name(reg) + idx, fs, after))
    for fld in sorted(hits):
        print('tune +0x%x: %d site(s)' % (fld, len(hits[fld])))
        for a, r, fs, after in hits[fld]:
            print('   %08x  reg %-3s  func ~%08x  found: %s' % (a, r, fs, after))
    print('%d tune field(s), %d site(s)' % (len(hits), sum(len(v) for v in hits.values())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
