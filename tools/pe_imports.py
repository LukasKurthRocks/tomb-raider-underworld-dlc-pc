"""List the import address table of a 32-bit PE (x86) such as tru.exe: IAT slot VA -> DLL!function (read-only;
TruMenu 0.9 save-system finding, to name the `call dword ptr [0x83e0xx]` targets in tools/pe_dis.py output).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_imports.py EXE [FILTER[,FILTER...]]
  FILTER = case-insensitive substring of the function name or of the slot VA in hex (e.g. 83e0c4,CreateFile)
"""
import sys, struct


def rva_to_off(secs, rva):
    for va, vsize, rptr, rsize in secs:
        if va <= rva < va + max(vsize, rsize): return rptr + rva - va
    return None


def main(argv):
    if not argv: sys.exit(__doc__)
    pe = open(argv[0], 'rb').read()
    filters = [f.lower() for f in argv[1].split(',')] if len(argv) > 1 else []
    e = struct.unpack_from('<I', pe, 0x3c)[0]
    nsec = struct.unpack_from('<H', pe, e + 6)[0]
    optsz = struct.unpack_from('<H', pe, e + 20)[0]
    opt = e + 24
    base = struct.unpack_from('<I', pe, opt + 28)[0]
    imp_rva = struct.unpack_from('<I', pe, opt + 96 + 8)[0]
    secs = []
    for i in range(nsec):
        s = opt + optsz + 40 * i
        vsize, va, rsize, rptr = struct.unpack_from('<IIII', pe, s + 8)
        secs.append((va, vsize, rptr, rsize))

    def cstr(rva):
        o = rva_to_off(secs, rva)
        return pe[o:pe.index(b'\0', o)].decode('latin-1')

    d = rva_to_off(secs, imp_rva)
    while True:
        ilt, _, _, name_rva, iat = struct.unpack_from('<IIIII', pe, d)
        if name_rva == 0: break
        dll = cstr(name_rva)
        src = ilt or iat
        k = 0
        while True:
            ent = struct.unpack_from('<I', pe, rva_to_off(secs, src) + 4 * k)[0]
            if ent == 0: break
            fn = ('#%d' % (ent & 0xffff)) if ent & 0x80000000 else cstr(ent + 2)
            slot = base + iat + 4 * k
            line = '0x%08x  %s!%s' % (slot, dll, fn)
            if not filters or any(f in line.lower() for f in filters): print(line)
            k += 1
        d += 20


if __name__ == '__main__':
    main(sys.argv[1:])
