"""Disassemble a range of a 32-bit PE (x86) such as tru.exe with capstone, or the function around an address
(read-only; finding 43, rock vein state graph).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_dis.py EXE FROM TO           range [FROM, TO) (hex VAs)
  ../bin/pyt -t 120 tools/pe_dis.py EXE --func ADDR [MAX]  from the function start before ADDR (int3 / ret padding
                                                         heuristic) until MAX bytes past ADDR (default 0x200)
  ../bin/pyt -t 120 tools/pe_dis.py EXE --dwords VA N      N little-endian dwords at VA (tables, data)
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def func_start(exe, secs, a):
    o = off_of(secs, a)
    # walk back to the first byte after a run of >= 2 int3 (0xcc) or a 'ret' followed by padding
    i = o
    while i > 2:
        if exe[i - 1] == 0xcc and exe[i - 2] == 0xcc: return a - (o - i)
        i -= 1
    return a


def main(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    if argv[1] == '--dwords':
        va, n = int(argv[2], 16), int(argv[3])
        o = off_of(secs, va)
        for k in range(n):
            print('0x%08x  0x%08x' % (va + 4 * k, struct.unpack_from('<I', exe, o + 4 * k)[0]))
        return
    if argv[1] == '--func':
        a = int(argv[2], 16); mx = int(argv[3], 16) if len(argv) > 3 else 0x200
        lo = func_start(exe, secs, a); hi = a + mx
    else:
        lo, hi = int(argv[1], 16), int(argv[2], 16)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.skipdata = True
    o = off_of(secs, lo)
    for ins in md.disasm(exe[o:o + (hi - lo)], lo):
        print('%08x  %-20s %-7s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))


if __name__ == '__main__':
    main(sys.argv[1:])
