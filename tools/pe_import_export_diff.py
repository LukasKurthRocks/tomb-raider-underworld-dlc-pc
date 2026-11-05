"""Compare the imports (DLL!function, by name) and exports of two 32-bit PE files, e.g. two builds of one ASI plugin
(TruMenu 0.10.4 vs 0.10.5) - read-only. Prints the DLL list of both, every import / export only in OLD or only in NEW,
and the counts. Exit 0 always (it reports, it does not judge).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/pe_import_export_diff.py OLD.asi NEW.asi
"""
import struct, sys


def sections(pe):
    e = struct.unpack_from('<I', pe, 0x3c)[0]
    nsec = struct.unpack_from('<H', pe, e + 6)[0]
    optsz = struct.unpack_from('<H', pe, e + 20)[0]
    opt = e + 24
    secs = []
    for i in range(nsec):
        s = opt + optsz + 40 * i
        vsize, va, rsize, rptr = struct.unpack_from('<IIII', pe, s + 8)
        secs.append((va, vsize, rptr, rsize))
    return opt, secs


def off(secs, rva):
    for va, vsize, rptr, rsize in secs:
        if va <= rva < va + max(vsize, rsize): return rptr + rva - va
    raise ValueError('rva 0x%x outside the sections' % rva)


def cstr(pe, secs, rva):
    o = off(secs, rva)
    return pe[o:pe.index(b'\0', o)].decode('latin-1')


def imports(pe):
    opt, secs = sections(pe)
    rva = struct.unpack_from('<I', pe, opt + 96 + 8)[0]
    out = set()
    if not rva: return out
    d = off(secs, rva)
    while True:
        ilt, _, _, name_rva, iat = struct.unpack_from('<IIIII', pe, d)
        if name_rva == 0: break
        dll = cstr(pe, secs, name_rva).upper()
        src, k = ilt or iat, 0
        while True:
            ent = struct.unpack_from('<I', pe, off(secs, src) + 4 * k)[0]
            if ent == 0: break
            out.add('%s!%s' % (dll, ('#%d' % (ent & 0xffff)) if ent & 0x80000000 else cstr(pe, secs, ent + 2)))
            k += 1
        d += 20
    return out


def exports(pe):
    opt, secs = sections(pe)
    rva = struct.unpack_from('<I', pe, opt + 96)[0]
    out = set()
    if not rva: return out
    d = off(secs, rva)
    count, names = struct.unpack_from('<II', pe, d + 20)   # NumberOfFunctions, NumberOfNames
    names_rva = struct.unpack_from('<I', pe, d + 32)[0]
    for i in range(names):
        out.add(cstr(pe, secs, struct.unpack_from('<I', pe, off(secs, names_rva) + 4 * i)[0]))
    return out


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    old, new = (open(p, 'rb').read() for p in argv)
    io, ino = imports(old), imports(new)
    eo, eno = exports(old), exports(new)
    for label, s in (('old', io), ('new', ino)):
        dlls = sorted({x.split('!')[0] for x in s})
        print('%s imports: %d functions from %s' % (label, len(s), ', '.join(
            '%s (%d)' % (d, sum(1 for x in s if x.startswith(d + '!'))) for d in dlls)))
    for x in sorted(ino - io): print('import only in new: %s' % x)
    for x in sorted(io - ino): print('import only in old: %s' % x)
    print('old exports: %s' % ', '.join(sorted(eo)))
    print('new exports: %s' % ', '.join(sorted(eno)))
    for x in sorted(eno - eo): print('export only in new: %s' % x)
    for x in sorted(eo - eno): print('export only in old: %s' % x)
    print('new DLLs: %s' % (', '.join(sorted({x.split('!')[0] for x in ino} - {x.split('!')[0] for x in io})) or 'none'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
