"""Group F copy of work/g_research_1211/q81_natives.py (12.11.2026, read-only), own output file; used for Q78
(`screenshot` / `screenshotsystem`). Original text:
Q81 (12.11.2026, one-off, read-only): native script types of the PC exe - registration, class vtable, binder and
the native function bodies, for the types no script function references (Q66 natives.tsv).

Registration (0x7a8650 ...): new 0x24-byte class object (pkg string, type string, 8, 4, flag) -> `mov [edi], VT`;
VT slot 3 = binder; binder: `push impl; push index; mov ecx, esi; call 0x5768f0` per native function.
Per native body: up to 48 instructions until ret / jmp: calls / jumps, strings pushed, simple shape (empty / stub).
Output: the file OUT given as third argument (only addresses, names, counts); also printed.
Usage (from trudlcport): ../bin/pyt -t 600 work/f_func_1211/f_natives.py EXE TYPE[,TYPE..] OUT
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE

OUT = None   # group F: output file from the command line (the original wrote a fixed file of group G)


def main(argv):
    global OUT
    if len(argv) < 3:
        print(__doc__); return
    OUT = argv[2]
    exe = open(argv[0], 'rb').read()
    pe = exe
    base, secs = PE.sections(pe)

    def off(va):
        for name, sva, rptr, size, _ in secs:
            if sva <= va < sva + size:
                return rptr + va - sva
        return -1

    def va(o):
        for name, sva, rptr, size, _ in secs:
            if rptr <= o < rptr + size:
                return sva + o - rptr
        return None

    def dw(a):
        return struct.unpack_from('<I', exe, off(a))[0]

    def cstr(a):
        o = off(a)
        if o < 0:
            return None
        e = exe.find(b'\0', o, o + 80)
        s = exe[o:e] if e > o else b''
        return s.decode('latin-1') if len(s) >= 3 and all(32 <= c < 127 for c in s) else None

    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    for name in argv[1].split(','):
        key = b'\0' + name.encode() + b'\0'
        o = exe.find(key)
        hits = []
        while o >= 0:
            hits.append(va(o + 1))
            o = exe.find(key, o + 1)
        res = []
        for sva in hits:
            pat = b'\x68' + struct.pack('<I', sva)
            p = exe.find(pat)
            while p >= 0:
                win = exe[p:p + 40]
                k = win.find(b'\xc7\x07')
                if k >= 0:
                    res.append((va(p), struct.unpack_from('<I', win, k + 2)[0]))
                p = exe.find(pat, p + 1)
        if not res:
            out.append('== %s: no registration found (string at %s)' % (name, ', '.join('0x%x' % h for h in hits)))
            continue
        for reg, vt in res:
            binder = dw(vt + 12)
            out.append('== %s: registration push at 0x%x, class vtable 0x%x, binder (slot 3) 0x%x' % (name, reg, vt,
                                                                                                    binder))
            bo = off(binder)
            code = exe[bo:bo + 0x800]
            natives = []
            for ins in cs.disasm(code, binder):
                if ins.mnemonic == 'push' and ins.op_str.startswith('0x') and len(ins.bytes) == 5:
                    last = int(ins.op_str, 16)
                elif ins.mnemonic == 'push' and len(ins.bytes) == 2:
                    natives.append((int(ins.op_str, 0), last))
                elif ins.mnemonic in ('ret', 'retn') or ins.mnemonic.startswith('ret'):
                    break
            for idx, impl in natives:
                calls, strs, n, shape = [], [], 0, []
                for ins in cs.disasm(exe[off(impl):off(impl) + 0x200], impl):
                    n += 1
                    if ins.mnemonic in ('call', 'jmp') and ins.op_str.startswith('0x'):
                        calls.append('%s 0x%x' % (ins.mnemonic, int(ins.op_str, 16)))
                    elif ins.mnemonic == 'call':
                        calls.append('call [%s]' % ins.op_str)
                    if ins.mnemonic == 'push' and ins.op_str.startswith('0x') and len(ins.bytes) == 5:
                        s = cstr(int(ins.op_str, 16))
                        if s:
                            strs.append(s)
                    if n <= 3:
                        shape.append(ins.mnemonic + (' ' + ins.op_str if ins.op_str else ''))
                    if ins.mnemonic.startswith('ret') or (ins.mnemonic == 'jmp' and n > 0) or n >= 48:
                        break
                out.append('  f%-2d 0x%x  %3d ins  %s | %s%s' % (idx, impl, n, '; '.join(shape)[:70],
                                                              ', '.join(calls[:6]),
                                                              (' | str ' + ', '.join(strs[:3])) if strs else ''))
    open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1:])
