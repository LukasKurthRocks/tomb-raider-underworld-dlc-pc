"""Where tru.exe uploads shader constants (read-only, static): every `call dword ptr [reg + 0x178]`
(IDirect3DDevice9::SetVertexShaderConstantF, vtable index 94) and `[reg + 0x1b4]` (SetPixelShaderConstantF, 109),
with the start register and count taken from the pushes before the call when they are immediates (stdcall order:
count, data, start register, device). Finding 43, test 46: does the engine upload MaterialParams to VS c25 and
TimeVector to VS c23 (the PC registers of base VS 1908) for any material?

Usage (from the repository root):
  ../bin/pyt -t 600 tools/exe_shader_const_calls.py EXE [--reg N[,N]] [--back 14]
Prints a histogram of start registers per stage and the call sites for the registers given with --reg.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from exe_xref import text

VT = {0x178: 'VS', 0x1b4: 'PS'}


def main(argv):
    path = argv[0]; regs = set(); back = 14
    if '--reg' in argv: k = argv.index('--reg'); regs = {int(x) for x in argv[k + 1].split(',')}
    if '--back' in argv: k = argv.index('--back'); back = int(argv[k + 1])
    code, va = text(path)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    win = collections.deque(maxlen=back); hist = collections.Counter(); sites = collections.defaultdict(list)
    loaded = {}      # register -> vtable displacement loaded by `mov reg, [base + disp]` (then `call reg`)
    for ins in md.disasm(code, va):
        if ins.id == 0: win.clear(); loaded.clear(); continue
        st = None
        if ins.mnemonic == 'mov' and len(ins.operands) == 2 and ins.operands[0].type == capstone.x86.X86_OP_REG \
                and ins.operands[1].type == capstone.x86.X86_OP_MEM and ins.operands[1].mem.disp in VT and ins.operands[1].mem.base != 0:
            loaded[ins.operands[0].reg] = ins.operands[1].mem.disp
        elif ins.mnemonic == 'call' and len(ins.operands) == 1 and ins.operands[0].type == capstone.x86.X86_OP_MEM \
                and ins.operands[0].mem.disp in VT and ins.operands[0].mem.base != 0:
            st = VT[ins.operands[0].mem.disp]
        elif ins.mnemonic == 'call' and len(ins.operands) == 1 and ins.operands[0].type == capstone.x86.X86_OP_REG \
                and ins.operands[0].reg in loaded:
            st = VT[loaded.pop(ins.operands[0].reg)]
        if st:
            pushes = [w for w in reversed(win) if w.mnemonic == 'push']
            vals = []
            for p in pushes[:4]:
                op = p.operands[0]
                vals.append(op.imm & 0xffffffff if op.type == capstone.x86.X86_OP_IMM else None)
            # pushes nearest the call: device, start, data, count
            start = vals[1] if len(vals) > 1 else None; count = vals[3] if len(vals) > 3 else None
            hist[(st, start)] += 1
            sites[(st, start)].append((ins.address, count))
        win.append(ins)
    for st in ('VS', 'PS'):
        print('%s: start register (immediate) -> call sites: %s' % (st, ', '.join('%s:%d' % (k[1], n) for k, n in sorted(hist.items(), key=lambda x: (x[0][1] is None, x[0][1] or 0)) if k[0] == st)))
    for (st, r), ls in sorted(sites.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
        if r in regs: print('  %s c%d: %s' % (st, r, ' '.join('%08x(count %s)' % (a, c) for a, c in ls)))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
