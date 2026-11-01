"""Find virtual calls through a given vtable slot shortly after the calls to a getter / loads of a global
(read-only; rock vein / wall run 2026-11-01: who calls TRMarkupManager slot +0x08 (tru+0x1dba20, wall normal of a box)
- the manager comes from the getter tru+0x1be390 = `mov eax,[0xdb94cc]`).

For every direct call (E8) to one of the GETTER addresses, the next N instructions are disassembled with capstone and
every `call dword ptr [reg + SLOT]` is printed with the instructions before it (the pushed arguments).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_vcall_after.py EXE GETTER[,GETTER..] SLOT [N] [--ctx K]
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def main(argv):
    ctx = 8
    if '--ctx' in argv: k = argv.index('--ctx'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    exe = open(argv[0], 'rb').read()
    getters = set(int(x, 16) for x in argv[1].split(','))
    slot = int(argv[2], 16)
    n = int(argv[3]) if len(argv) > 3 else 40
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    want = ('+ 0x%x]' % slot) if slot > 9 else ('+ %d]' % slot)
    for name, sva, rptr, size, chars in secs:
        if not (chars & 0x20000000): continue
        blob = exe[rptr:rptr + size]
        for i in range(len(blob) - 5):
            if blob[i] != 0xe8: continue
            tgt = (sva + i + 5 + struct.unpack_from('<i', blob, i + 1)[0]) & 0xffffffff
            if tgt not in getters: continue
            at = sva + i
            o = off_of(secs, at)
            ins = list(md.disasm(exe[o:o + n * 8], at))[:n]
            for k, x in enumerate(ins):
                hit = x.op_str.endswith(want) if slot else (len(x.op_str) == 15 and x.op_str[-1] == ']')
                if x.mnemonic == 'call' and len(x.op_str) == 3 and k > 0:
                    # call REG with REG = [base + SLOT] loaded before (as the wrapper tru+0x1c3cc0 does)
                    for y in reversed(ins[max(0, k - 6):k]):
                        if y.mnemonic == 'mov' and y.op_str.startswith(x.op_str + ', dword ptr ['):
                            src = y.op_str.split('[', 1)[1]
                            hit = src.endswith(want) if slot else len(src) == 4
                            break
                    if hit:
                        print('getter call 0x%08x -> vcall 0x%08x (register)' % (at, x.address))
                        for y in ins[max(0, k - ctx):k + 1]:
                            print('    %08x  %s %s' % (y.address, y.mnemonic, y.op_str))
                        break
                    continue
                if x.mnemonic == 'call' and x.op_str.startswith('dword ptr [') and hit:
                    print('getter call 0x%08x -> vcall 0x%08x' % (at, x.address))
                    for y in ins[max(0, k - ctx):k + 1]:
                        print('    %08x  %s %s' % (y.address, y.mnemonic, y.op_str))
                    break


if __name__ == '__main__':
    main(sys.argv[1:])
