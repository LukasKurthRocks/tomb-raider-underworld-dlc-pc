"""Direct callers / jumpers of an address in a 32-bit PE (x86) such as tru.exe (read-only; finding 43).

Scans the executable sections for E8 (call rel32) and E9 (jmp rel32) whose target is one of the given addresses,
and for 32-bit immediates equal to them (push offset / mov reg, imm / data tables). Fast first pass without a
disassembler: byte-pattern based, so an E8 / E9 inside another instruction can show up as a false positive.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_callers.py EXE ADDR[,ADDR...]
"""
import sys, struct


def sections(pe):
    off = struct.unpack_from('<I', pe, 0x3c)[0]
    nsec = struct.unpack_from('<H', pe, off + 6)[0]
    opt = struct.unpack_from('<H', pe, off + 20)[0]
    base = struct.unpack_from('<I', pe, off + 24 + 28)[0]
    out = []
    for i in range(nsec):
        s = off + 24 + opt + i * 40
        name = pe[s:s + 8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, va, rsize, rptr = struct.unpack_from('<IIII', pe, s + 8)
        chars = struct.unpack_from('<I', pe, s + 36)[0]
        out.append((name, base + va, rptr, min(vsize, rsize), chars))
    return base, out


def main(argv):
    pe = open(argv[0], 'rb').read()
    targets = set(int(x, 16) for x in argv[1].split(','))
    base, secs = sections(pe)
    for name, va, rptr, size, chars in secs:
        blob = pe[rptr:rptr + size]
        code = bool(chars & 0x20000000)
        for i in range(len(blob) - 4):
            v = struct.unpack_from('<I', blob, i)[0]
            if v in targets:
                print('%s 0x%08x imm32 -> 0x%08x' % (name, va + i, v))
            if code and i >= 1 and blob[i - 1] in (0xe8, 0xe9):
                t = (va + i + 4 + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff
                if t in targets:
                    print('%s 0x%08x %s -> 0x%08x' % (name, va + i - 1, 'call' if blob[i - 1] == 0xe8 else 'jmp', t))


if __name__ == '__main__':
    main(sys.argv[1:])
