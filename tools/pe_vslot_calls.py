"""List every C++ virtual call through one vtable slot in a 32-bit PE (x86) such as tru.exe, with context (read-only).

Night 04.11. (workspace docs Befund-Restrisiken-0411.md, task A): the PC class cdc::ScriptUIScreen overrides the
UISuperWidget C++ slot 80 (+0x140) with tru+0xbe090, which forwards the call to the SCRIPT vtable slot that the
uiscreen binder read from prototype 111 of script 93 (= slot 31 on PC). Who calls C++ slot +0x140?

A call site is one of
  * `call dword ptr [REG + SLOT]`
  * `mov R, dword ptr [REG + SLOT]` followed (within --window instructions, R not overwritten) by `call R` / `jmp R`
where REG is not esp / ebp (stack frames). For each site the --ctx instructions before it are printed, so the
receiver (`mov REG, [obj]` = vtable load) and the pushed arguments can be read.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_vslot_calls.py EXE SLOT [--from VA] [--to VA] [--ctx N] [--window N] [--out FILE]
  SLOT / VA hex (0x...)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import pe_callers as PE


def main(argv):
    def opt(name, default, conv):
        if name in argv:
            k = argv.index(name); v = conv(argv[k + 1]); del argv[k:k + 2]; return v
        return default
    lo = opt('--from', None, lambda s: int(s, 16)); hi = opt('--to', None, lambda s: int(s, 16))
    ctx = opt('--ctx', 10, int); window = opt('--window', 8, int); out = opt('--out', None, str)
    if len(argv) != 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read(); slot = int(argv[1], 16)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True; md.detail = True
    from capstone import x86
    lines = []; n = 0
    for name, sva, rptr, size, chars in secs:
        if not (chars & 0x20000000): continue
        ins = list(md.disasm(exe[rptr:rptr + size], sva))
        for i, a in enumerate(ins):
            if lo is not None and a.address < lo: continue
            if hi is not None and a.address >= hi: continue
            if a.id == 0 or not a.operands: continue
            site = None
            mems = [o for o in a.operands if o.type == x86.X86_OP_MEM]
            if not mems: continue
            m = mems[0].mem
            if m.disp != slot or m.index != 0 or m.base in (0, x86.X86_REG_ESP, x86.X86_REG_EBP): continue
            if a.mnemonic in ('call', 'jmp') and a.operands[0].type == x86.X86_OP_MEM:
                site = a
            elif a.mnemonic == 'mov' and a.operands[0].type == x86.X86_OP_REG:
                r = a.operands[0].reg
                for b in ins[i + 1:i + 1 + window]:
                    if b.mnemonic in ('call', 'jmp') and b.operands and b.operands[0].type == x86.X86_OP_REG \
                            and b.operands[0].reg == r:
                        site = b; break
                    if b.operands and b.operands[0].type == x86.X86_OP_REG and b.operands[0].reg == r \
                            and b.mnemonic not in ('push', 'cmp', 'test'):
                        break
                    if b.mnemonic in ('ret', 'call', 'jmp'):
                        break
            if site is None: continue
            n += 1
            lines.append('== site %d: 0x%08x (tru+0x%x) %s %s' % (n, site.address, site.address - base,
                                                                   site.mnemonic, site.op_str))
            for b in ins[max(0, i - ctx):i + 1]:
                lines.append('   0x%08x  %s %s' % (b.address, b.mnemonic, b.op_str))
            if site is not a:
                k = ins.index(site)
                for b in ins[i + 1:k + 1]:
                    lines.append('   0x%08x  %s %s' % (b.address, b.mnemonic, b.op_str))
    lines.append('slot 0x%x: %d call sites' % (slot, n))
    text = '\n'.join(lines) + '\n'
    if out:
        open(out, 'w', encoding='utf-8').write(text); print('slot 0x%x: %d call sites -> %s' % (slot, n, out))
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
