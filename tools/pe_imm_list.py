"""List the 32-bit immediates in an address range of a 32-bit PE (x86, e.g. tru.exe) that point into the image -
push offset / mov reg, offset operands (read-only; TU coverage audit: which tables a registration function passes).

Byte-pattern based like tools/pe_callers.py: every 4-byte window in the range is tested, so an address can show up
once per byte shift only when it really is in the code; E8 / E9 call / jmp targets are listed separately.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_imm_list.py EXE FROM_VA TO_VA
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) != 3: sys.exit(__doc__)
    pe = open(argv[0], 'rb').read()
    lo, hi = int(argv[1], 0), int(argv[2], 0)
    base, secs = PE.sections(pe)
    top = max(va + size for _, va, _, size, _ in secs)
    for name, va, rptr, size, ch in secs:
        if not (va <= lo < va + size): continue
        blob = pe[rptr + lo - va:rptr + min(hi, va + size) - va + 4]
        for i in range(len(blob) - 4):
            v = struct.unpack_from('<I', blob, i)[0]
            if i >= 1 and blob[i - 1] in (0xe8, 0xe9):
                t = (lo + i + 4 + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff
                if base <= t < top:
                    print('0x%08x  %s tru+0x%x' % (lo + i - 1, 'call' if blob[i - 1] == 0xe8 else 'jmp ', t - base))
            elif base <= v < top and (i == 0 or blob[i - 1] in (0x68, 0xb8, 0xb9, 0xba, 0xbb, 0xbe, 0xbf, 0x05, 0x15, 0x1d, 0x0d, 0x35, 0x3d)):
                print('0x%08x  imm  0x%08x (tru+0x%x)' % (lo + i, v, v - base))


if __name__ == '__main__':
    main(sys.argv[1:])
