"""MSVC RTTI walk for a 32-bit PE (x86) such as tru.exe: class name -> TypeDescriptor -> CompleteObjectLocator(s) ->
vtable(s) -> code that stores the vtable (constructors / destructors) (read-only; debug camera finding).

  TypeDescriptor  = address of the '.?AV<Name>@@' string minus 8
  COL             = 5 dwords {signature 0, offset, cdOffset, pTypeDescriptor, pClassHierarchy}; found by searching
                    for pTypeDescriptor and checking signature 0 at -12
  vtable          = address after a dword equal to the COL address (vtable[-1] = COL)
Prints the first N vtable slots and every 32-bit reference to the vtable (usually 'mov dword ptr [reg], vtable'
in a constructor or destructor).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_rtti_vtable.py EXE CLASS[,CLASS...] [SLOTS]      e.g. FreeCamera,CheatCamera  SLOTS=12
  (CLASS may contain a namespace in MSVC order, e.g. UIDebugText@cdc)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def va_of(secs, o):
    for name, sva, rptr, size, _ in secs:
        if rptr <= o < rptr + size: return sva + o - rptr
    return None


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def refs(exe, secs, va):
    key = struct.pack('<I', va)
    out, r = [], 0
    while True:
        r = exe.find(key, r)
        if r < 0: return out
        v = va_of(secs, r)
        if v is not None: out.append(v)
        r += 1


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    slots = int(argv[2]) if len(argv) > 2 else 12
    base, secs = PE.sections(exe)
    for cls in argv[1].split(','):
        name = ('.?AV%s@@' % cls).encode('latin-1')
        i = exe.find(name + b'\0')
        print('== %s' % cls)
        if i < 0:
            print('  type descriptor string not found'); continue
        td = va_of(secs, i) - 8
        print('  TypeDescriptor 0x%08x' % td)
        for r in refs(exe, secs, td):
            col = r - 12
            o = off_of(secs, col)
            if o < 0 or struct.unpack_from('<I', exe, o)[0] != 0: continue
            sig, off, cdoff, ptd, pch = struct.unpack_from('<5I', exe, o)
            print('  COL 0x%08x (offset %d, cdOffset %d, hierarchy 0x%08x)' % (col, off, cdoff, pch))
            for vr in refs(exe, secs, col):
                vt = vr + 4
                print('    vtable 0x%08x' % vt)
                vo = off_of(secs, vt)
                for k in range(slots):
                    print('      [%2d] +0x%02x 0x%08x' % (k, 4 * k, struct.unpack_from('<I', exe, vo + 4 * k)[0]))
                for cr in refs(exe, secs, vt):
                    print('      ref 0x%08x' % cr)


if __name__ == '__main__':
    main(sys.argv[1:])
