"""Read-only probe of a PS3 disc image: which parts are plain, which files exist, and whether the executables are
readable (docs/Befund-Prototyp-2007.md, section "2008-10-03 PS3 build").

A PS3 disc image starts with a region table (sector 0, big-endian): u32 count of PLAIN regions, u32 reserved, then
(start, end) sector pairs of the plain regions; everything between them is encrypted with the disc key. This tool
prints the regions, walks the ISO9660 directory tree (only through plain sectors), lists every file with its first
sector, size and whether it lies in a plain region, and for executables (EBOOT.BIN, *.self, *.sprx, *.elf) in plain
regions prints the SCE header (magic, key revision: 0x8000 = debug / fake-signed, i.e. not encrypted) or ELF magic.
Nothing is decrypted, extracted or executed; only header fields and names are printed.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ps3_iso_probe.py ISO [--all]      --all: list every file (default: executables + summary)
"""
import sys, struct

SEC = 2048


def regions(f):
    f.seek(0)
    h = f.read(SEC)
    n = struct.unpack_from('>I', h, 0)[0]
    out = []
    for i in range(min(n, 200)):
        s, e = struct.unpack_from('>II', h, 8 + 8 * i)
        out.append((s, e))
    return n, out


def plain(regs, lba):
    return any(s <= lba <= e for s, e in regs)


def walk(f, regs, lba, size, path, out, depth=0):
    if depth > 12 or not plain(regs, lba):
        out.append((path + '/', lba, size, False, True))
        return
    f.seek(lba * SEC)
    data = f.read(size)
    o = 0
    while o < len(data):
        ln = data[o]
        if ln == 0:
            o = (o // SEC + 1) * SEC
            continue
        rec = data[o:o + ln]
        elba = struct.unpack_from('<I', rec, 2)[0]
        esz = struct.unpack_from('<I', rec, 10)[0]
        flags = rec[25]
        nl = rec[32]
        name = rec[33:33 + nl]
        o += ln
        if name in (b'\0', b'\1'):
            continue
        nm = name.decode('latin-1').split(';')[0]
        if flags & 2:
            walk(f, regs, elba, esz, path + '/' + nm, out, depth + 1)
        else:
            out.append((path + '/' + nm, elba, esz, plain(regs, elba), False))


def main(argv):
    if not argv:
        sys.exit(__doc__)
    f = open(argv[0], 'rb')
    n, regs = regions(f)
    print('plain regions: %d' % n)
    for s, e in regs[:20]:
        print('  sectors %d..%d (%.1f MB)' % (s, e, (e - s + 1) * SEC / 1048576.0))
    f.seek(16 * SEC)
    pvd = f.read(SEC)
    if pvd[1:6] != b'CD001':
        print('no ISO9660 volume descriptor at sector 16')
        return
    vol = pvd[40:72].decode('latin-1').strip()
    root = pvd[156:156 + 34]
    rlba, rsz = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    print('volume "%s", root directory at sector %d' % (vol, rlba))
    out = []
    walk(f, regs, rlba, rsz, '', out)
    nplain = sum(1 for x in out if x[3])
    print('files: %d (in plain regions %d, encrypted %d, unreadable directories %d)' % (
        sum(1 for x in out if not x[4]), nplain, sum(1 for x in out if not x[3] and not x[4]),
        sum(1 for x in out if x[4])))
    exe_ext = ('.BIN', '.SELF', '.SPRX', '.ELF', '.PRX')
    for p, lba, sz, pl, isdir in out:
        is_exe = p.upper().endswith(exe_ext)
        if not ('--all' in argv or is_exe or isdir):
            continue
        hdr = ''
        if is_exe and pl:
            f.seek(lba * SEC)
            h = f.read(0x20)
            if h[:4] == b'SCE\0':
                ver, keyrev, htype = struct.unpack_from('>IHH', h, 4)
                hdr = 'SCE header v%d key_revision 0x%04x (%s) type %d' % (
                    ver, keyrev, 'debug / fake-signed' if keyrev == 0x8000 else 'retail-encrypted', htype)
            elif h[:4] == b'\x7fELF':
                hdr = 'plain ELF'
            else:
                hdr = 'unknown header %s' % h[:4].hex()
        print('  %-60s sector %9d %11d B  %s %s' % (p[:60], lba, sz, 'plain' if pl else 'ENCRYPTED',
                                                   ('dir (not readable)' if isdir else hdr)))


if __name__ == '__main__':
    main(sys.argv[1:])
