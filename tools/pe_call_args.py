"""List every direct call of a function in a 32-bit PE (x86) such as tru.exe together with the immediate pushes and
'mov ecx, imm' right before it, decoding pointers to ASCII strings (read-only; developer channel finding: names
registered through the type registry 0x598760, e.g. 'ScriptDebugger').

For each E8 call site the up to LOOKBACK bytes before it are disassembled with capstone (start chosen so that the
call instruction itself is decoded) and the push imm / mov ecx, imm operands are printed in source order; an operand
that points at a printable zero-terminated string is shown as that string.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_call_args.py EXE FUNC_VA [LOOKBACK]        LOOKBACK default 24 bytes
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def as_str(exe, secs, v):
    o = off_of(secs, v)
    if o < 0: return None
    e = exe.find(b'\0', o, o + 160)
    if e <= o: return None
    s = exe[o:e]
    if all(32 <= c < 127 for c in s) and len(s) >= 3: return s.decode('ascii')
    return None


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    func = int(argv[1], 16)
    back = int(argv[2]) if len(argv) > 2 else 24
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for name, sva, rptr, size, chars in secs:
        if not chars & 0x20000000: continue          # executable sections only
        data = exe[rptr:rptr + size]
        i = data.find(b'\xe8')
        while i >= 0:
            if i + 5 <= len(data):
                site = sva + i
                if (site + 5 + struct.unpack_from('<i', data, i + 1)[0]) & 0xffffffff == func:
                    best = None
                    for s in range(max(0, i - back), i):
                        ins = list(md.disasm(data[s:i + 5], sva + s))
                        if ins and ins[-1].address == site and ins[-1].mnemonic == 'call':
                            best = ins; break
                    args = []
                    for ins in (best or [])[:-1]:
                        if ins.mnemonic == 'push' or (ins.mnemonic == 'mov' and ins.op_str.startswith('ecx, 0x')):
                            v = ins.op_str.split(',')[-1].strip()
                            if v.startswith('0x') or v.isdigit():
                                n = int(v, 0)
                                st = as_str(exe, secs, n)
                                pre = 'ecx=' if ins.mnemonic == 'mov' else ''
                                args.append(pre + (repr(st) if st else '0x%x' % n))
                    print('0x%08x  %s' % (site, '  '.join(args)))
            i = data.find(b'\xe8', i + 1)


if __name__ == '__main__':
    main(sys.argv[1:])
