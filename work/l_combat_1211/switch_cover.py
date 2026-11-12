"""Group L 12.11. (read-only): which switch statements of tru.exe can reach a case VALUE (e.g. message 0x19b)?
Linear capstone sweep over [LO, HI): an instruction `sub REG, X` / `add REG, -X` (or none: X = 0) followed within 4
instructions by `cmp REG, N` + `ja` = a switch over X..X+N; listed when X <= VALUE <= X + N. Also lists direct
`cmp REG, VALUE`. The case target itself must be read by hand (tools/pe_switch.py).
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/switch_cover.py EXE VALUE LO HI"""
import sys, os
import capstone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE


def main(a):
    exe = open(a[0], 'rb').read()
    val, lo, hi = int(a[1], 16), int(a[2], 16), int(a[3], 16)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.skipdata = True
    for name, sva, rptr, size, ch in secs:
        if not ch & 0x20000000:
            continue
        s, e = max(lo, sva), min(hi, sva + size)
        if s >= e:
            continue
        code = exe[rptr + s - sva: rptr + e - sva]
        ins = list(md.disasm(code, s))
        # compare chains: `sub REG, k` (+ je / jne) repeated - the running sum hits VALUE
        run = {}
        for i, x in enumerate(ins):
            ops = x.op_str.split(', ')
            if x.mnemonic in ('sub', 'add') and len(ops) == 2 and ops[0] in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi') \
                    and ops[1].lstrip('-').startswith('0x'):
                try:
                    k = int(ops[1].lstrip('-'), 16) * (-1 if ops[1].startswith('-') else 1)
                except ValueError:
                    continue
                k = k if x.mnemonic == 'sub' else -k
                run[ops[0]] = run.get(ops[0], 0) + k
                if run[ops[0]] == val and i + 1 < len(ins) and ins[i + 1].mnemonic in ('je', 'jne'):
                    print('0x%08x  chain   %s reaches %s' % (x.address, ops[0], hex(val)))
            elif x.mnemonic.startswith('j') or x.mnemonic in ('test', 'cmp'):
                if x.mnemonic in ('jmp', 'ret'):
                    run = {}
            else:
                for r in list(run):
                    if r in x.op_str.split(', ')[0]:
                        del run[r]
        for i, x in enumerate(ins):
            ops = x.op_str.split(', ')
            if x.mnemonic == 'cmp' and len(ops) == 2 and ops[1].startswith('0x'):
                try:
                    n = int(ops[1], 16)
                except ValueError:
                    continue
                if n == val:
                    print('0x%08x  direct  %s %s' % (x.address, x.mnemonic, x.op_str))
                    continue
                if i + 1 >= len(ins) or ins[i + 1].mnemonic not in ('ja', 'jae'):
                    continue
                reg = ops[0]
                x0 = None
                for y in ins[max(0, i - 4):i]:
                    yo = y.op_str.split(', ')
                    if len(yo) == 2 and yo[0] == reg and yo[1].lstrip('-').startswith('0x'):
                        try:
                            k = int(yo[1], 16) if not yo[1].startswith('-') else -int(yo[1][1:], 16)
                        except ValueError:
                            continue
                        if y.mnemonic == 'sub':
                            x0 = (x0 or 0) + k
                        elif y.mnemonic == 'add':
                            x0 = (x0 or 0) - k
                if x0 is None:
                    continue
                if x0 <= val <= x0 + n:
                    print('0x%08x  switch  %s..%s (%s %s)' % (x.address, hex(x0), hex(x0 + n), x.mnemonic, x.op_str))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
