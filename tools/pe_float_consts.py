"""Print the 32-bit float and 64-bit double read at virtual addresses of a 32-bit PE such as tru.exe (read-only;
TruMenu 0.13 thrall labels: the constants of the game's own screen projection 0x5e7b30 / 0x5f3df0 / 0x49f630).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_float_consts.py EXE VA[,VA..]      hex VAs; prints dword, float and double per VA
Addresses past the raw data of a section (.bss) are reported as such (their value exists only at run time).
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    for text in argv[1].split(','):
        va = int(text, 16)
        off = -1
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size:
                off = rptr + va - sva
        if off < 0 or off + 8 > len(exe):
            print('0x%08x  not in the raw data (bss / outside the file)' % va)
            continue
        dw = struct.unpack_from('<I', exe, off)[0]
        f = struct.unpack_from('<f', exe, off)[0]
        d = struct.unpack_from('<d', exe, off)[0]
        print('0x%08x  dword 0x%08x  float %.9g  double %.17g' % (va, dw, f, d))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
