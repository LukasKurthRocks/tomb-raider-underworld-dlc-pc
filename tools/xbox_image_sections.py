"""Section table of an Xbox 360 executable image dumped from Xenia's guest memory (read-only).

The dump (e.g. work/xenia_dump/tu_image_82000000.bin, guest 0x82000000.., see docs Befund-Schattenkraft.md) starts
with the PE header Xenia loaded ("MZ"). Prints each section: name, guest address range, size, flags (code / data),
and for the code sections the share of non-zero bytes - so later scans know which ranges are PowerPC code.
Finding 43 follow-up (DLC 2 shadow power, option A).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/xbox_image_sections.py DUMP.bin [BASE]      BASE default 0x82000000
"""
import sys, struct


def sections(d, base=0x82000000):
    """[(name, guest_start, size, characteristics)] from the PE header at the start of the dump"""
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    if d[pe:pe + 4] != b'PE\0\0':
        raise ValueError('no PE header at 0x%x' % pe)
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    out = []
    for i in range(nsec):
        o = pe + 24 + opt + 40 * i
        name = d[o:o + 8].rstrip(b'\0').decode('latin-1')
        vsize, vaddr = struct.unpack_from('<II', d, o + 8)
        ch = struct.unpack_from('<I', d, o + 36)[0]
        out.append((name, base + vaddr, vsize, ch))
    return out


def main(argv):
    path = argv[0]
    base = int(argv[1], 0) if len(argv) > 1 else 0x82000000
    d = open(path, 'rb').read()
    print('%s: %d bytes, guest 0x%08x..0x%08x' % (path, len(d), base, base + len(d)))
    for name, start, size, ch in sections(d, base):
        kind = 'code' if ch & 0x20 else ('data' if ch & 0x40 else ('bss' if ch & 0x80 else '?'))
        off = start - base
        chunk = d[off:off + size]
        nz = sum(1 for b in chunk if b) / float(max(1, len(chunk)))
        print('  %-8s 0x%08x..0x%08x %9d B  %-4s flags 0x%08x  non-zero %.0f %%'
              % (name, start, start + size, size, kind, ch, 100 * nz))


if __name__ == '__main__':
    main(sys.argv[1:])
