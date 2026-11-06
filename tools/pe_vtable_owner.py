"""Which MSVC RTTI class owns a vtable slot address in a 32-bit PE such as tru.exe (read-only; 2026-11-06 enemy
senses: callers that reach a function only through a vtable, e.g. tru 0x8582f4 -> 0x61dc90, docs
Befund-Gegner-Wahrnehmung-0611.md).

For every given data address A (a slot that holds a function pointer, as printed by tools/pe_callers.py as
".rdata A imm32 -> F"), walk back dword by dword (at most --back slots) until a dword is found that is the address of
a CompleteObjectLocator (signature 0, pTypeDescriptor -> '.?AV' / '.?AU' name); the vtable then starts right after it
and A's slot index is (A - vtable) / 4. Also prints, for code addresses given with --func, every slot in the image
whose dword equals the function (so the owner of each slot is listed).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_vtable_owner.py EXE ADDR[,ADDR..] [--back N]
  ../bin/pyt -t 300 tools/pe_vtable_owner.py EXE --func FUNC[,FUNC..] [--back N]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    back = 200
    if '--back' in argv: k = argv.index('--back'); back = int(argv[k + 1]); del argv[k:k + 2]
    funcs = '--func' in argv
    argv = [a for a in argv if a != '--func']
    if len(argv) < 2: sys.exit(__doc__)
    pe = open(argv[0], 'rb').read()
    base, secs = PE.sections(pe)

    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        return None

    def u32(va):
        o = off(va)
        return None if o is None or o + 4 > len(pe) else struct.unpack_from('<I', pe, o)[0]

    def cstr(va):
        o = off(va)
        if o is None: return None
        e = pe.find(b'\0', o, o + 300)
        return pe[o:e].decode('latin-1') if e > 0 else None

    def col_name(va):
        if u32(va) != 0: return None
        td = u32(va + 12)
        if td is None: return None
        n = cstr(td + 8)
        return n if n and (n.startswith('.?AV') or n.startswith('.?AU')) else None

    def owner(a):
        for i in range(0, back + 1):
            v = u32(a - 4 * (i + 1))
            if v is None: break
            n = col_name(v)
            if n: return n, a - 4 * i, i
        return None, None, None

    targets = [int(x, 16) for x in argv[1].split(',')]
    if funcs:
        for f in targets:
            pat = struct.pack('<I', f)
            print('== function 0x%08x' % f)
            for name, sva, rptr, size, chars in secs:
                if chars & 0x20000000: continue  # skip executable sections
                o = pe.find(pat, rptr, rptr + size)
                while o >= 0:
                    if (o - rptr) % 4 == 0:
                        a = sva + o - rptr
                        n, vt, slot = owner(a)
                        print('   slot 0x%08x %-6s %s' % (a, name, ('%s vtable 0x%08x slot %d (+0x%x)' % (n, vt, slot, slot * 4)) if n else 'no RTTI owner within %d slots' % back))
                    o = pe.find(pat, o + 1, rptr + size)
    else:
        for a in targets:
            n, vt, slot = owner(a)
            fn = u32(a)
            print('0x%08x -> 0x%08x  %s' % (a, fn or 0, ('%s vtable 0x%08x slot %d (+0x%x)' % (n, vt, slot, slot * 4)) if n else 'no RTTI owner within %d slots' % back))


if __name__ == '__main__':
    main(sys.argv[1:])
