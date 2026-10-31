"""Find ASCII strings in a 32-bit PE (x86) such as tru.exe by substring and list the code / data that references
them as a 32-bit immediate or pointer (read-only; developer channel / debug camera finding).

For every hit the start of the zero-terminated string is located (walk back to the previous NUL), its virtual
address printed, and all places in the image whose 4 bytes equal that address are listed (push offset, mov reg,
offset, vtable / RTTI / name tables). Byte-pattern based like tools/pe_callers.py.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_find_str.py EXE TEXT[,TEXT...] [--max N]     N = max hits per text (default 20)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def va_of(secs, o):
    for name, sva, rptr, size, _ in secs:
        if rptr <= o < rptr + size: return sva + o - rptr, name
    return None, None


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    texts = argv[1].split(',')
    mx = 20
    if '--max' in argv: mx = int(argv[argv.index('--max') + 1])
    base, secs = PE.sections(exe)
    for t in texts:
        needle = t.encode('latin-1')
        pos, n, seen = 0, 0, set()
        print('== %r' % t)
        while n < mx:
            i = exe.find(needle, pos)
            if i < 0: break
            pos = i + 1
            s = i
            while s > 0 and exe[s - 1] != 0 and i - s < 256: s -= 1
            if s in seen: continue
            seen.add(s)
            e = exe.find(b'\0', i)
            va, sec = va_of(secs, s)
            if va is None: continue
            n += 1
            print('  0x%08x %-6s %r' % (va, sec, exe[s:e][:120].decode('latin-1')))
            key = struct.pack('<I', va)
            r = 0
            while True:
                r = exe.find(key, r)
                if r < 0: break
                rva, rsec = va_of(secs, r)
                if rva is not None:
                    print('      ref 0x%08x %s' % (rva, rsec))
                r += 1


if __name__ == '__main__':
    main(sys.argv[1:])
