"""Print the zero-terminated UTF-16LE strings at one or more virtual addresses of a 32-bit PE (x86) such as tru.exe
(read-only; game settings study 2026-11-10: the registry value names that the settings read 0x477ea0 / graphics read
0x51e120 push as wide string pointers). With --dis FROM TO every `push imm` / `mov reg, imm` in that code range whose
immediate points at a wide string is listed together with the string (the value name next to its RegQueryValueExW).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/pe_wcstr.py EXE VA[,VA...] [MAXLEN]       MAXLEN default 100 characters
  ../bin/pyt -t 120 tools/pe_wcstr.py EXE --dis FROM TO
  ../bin/pyt -t 120 tools/pe_wcstr.py EXE --fields FROM TO REG   value name -> first store [REG + off] after its query
      (graphics read 0x51e120 0x51e920 ebp: ebp = the graphics settings block, 0x890388 at start)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def wstr(exe, secs, va, maxlen=100):
    o = off_of(secs, va)
    if o < 0: return None
    out = []
    for k in range(maxlen):
        c = struct.unpack_from('<H', exe, o + 2 * k)[0]
        if c == 0: break
        if c < 0x20 or c > 0x7e: return None
        out.append(chr(c))
    else:
        return None
    return ''.join(out) if len(out) >= 2 else None


def main(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    if argv[1] == '--fields':
        # --fields FROM TO REG: for each wide value name pushed in [FROM, TO), the first store to [REG + off] (or to an
        # absolute [0xADDR]) after the next indirect call (RegQueryValueEx) = the field that value is read into
        import capstone
        a, b, reg = int(argv[2], 16), int(argv[3], 16), argv[4]
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        o = off_of(secs, a)
        name, called = None, False
        for ins in md.disasm(exe[o:o + (b - a)], a):
            if ins.mnemonic == 'push' and ins.op_str.startswith('0x'):
                s = wstr(exe, secs, int(ins.op_str, 16))
                if s:
                    if name and not called: pass
                    name, called = s, False
                    continue
            if name and ins.mnemonic == 'call' and not ins.op_str.startswith('0x'):
                called = True
                continue
            if name and called and ins.mnemonic in ('mov', 'fstp') and ins.op_str.split(',')[0].count('[') and (
                    ('[%s + ' % reg) in ins.op_str.split(',')[0] or ('[%s]' % reg) in ins.op_str.split(',')[0]
                    or ins.op_str.split(',')[0].strip().split('[')[1].startswith('0x')):
                print('%-28s 0x%08x  %s %s' % (name, ins.address, ins.mnemonic, ins.op_str))
                name, called = None, False
        return
    if argv[1] == '--dis':
        import capstone
        a, b = int(argv[2], 16), int(argv[3], 16)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        o = off_of(secs, a)
        for ins in md.disasm(exe[o:o + (b - a)], a):
            if ins.mnemonic in ('push', 'mov', 'lea'):
                for tok in ins.op_str.replace(',', ' ').split():
                    if tok.startswith('0x') and len(tok) >= 8:
                        s = wstr(exe, secs, int(tok, 16))
                        if s: print('0x%08x  %-8s %-40s %s' % (ins.address, ins.mnemonic, ins.op_str, s))
        return
    maxlen = int(argv[2]) if len(argv) > 2 else 100
    for v in argv[1].split(','):
        va = int(v, 16)
        print('0x%08x  %r' % (va, wstr(exe, secs, va, maxlen)))


if __name__ == '__main__':
    main(sys.argv[1:])
