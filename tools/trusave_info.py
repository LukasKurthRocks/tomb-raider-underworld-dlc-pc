"""Read-only check of Tomb Raider: Underworld PC save files (*.TRUSave), TruMenu 0.9 "Saves" page finding.

Prints only structure (offsets, sizes, CRC results) - no save content - so the output may be quoted in docs.

Format as proven in tru.exe (Steam, image base 0x400000; see docs/Menue-Funktionen-Katalog.md section 11.4):
  folder   0x78b550: SHGetFolderLocation(CSIDL_PERSONAL = 5) [fallback: registry Shell Folders "Personal",
           then L"C:\\My Documents"] + L"\\Eidos\\" + L"Tomb Raider - Underworld" + L"\\" (CreateDirectoryW each step);
           file names L"<name>.TRUSave" (0x8614b0), enumeration L"*.TRUSave" (0x8614e4), autosave L"Autosave".
  0x0000   Windows "rich saved game" header (written at 0x6db2f0): 'RGMH', version 1, header size 0x2028,
           thumbnail offset (u64, relative to the header end), thumbnail size, game GUID, 4 x WCHAR[256]
           (game name, save name, level name, comments).
  0x2028   'PCUD' block (read at 0x6dbb4f / checked at 0x6dbba7, struct copy at object +0x214):
           +0 'PCUD' +4 version 0x100 +8 'SURT' +0xc 0x100 +0x10 entry count
           +0x14 table CRC (= crc(table, count * 12), check 0x6dbc8d) +0x18 header CRC (= crc(+0..+0x18), 0x6dbbd5)
  0x2044   table, count x {u32 size, u32 file offset, u32 data CRC (check 0x6dbcc6)}
  then     the thumbnail (PNG) and the data block(s).
CRC = 0x596d80: table 0x596ce0 (polynomial 0x04C11DB7, MSB first), init 0xFFFFFFFF, final NOT (CRC-32/BZIP2).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trusave_info.py FILE_OR_FOLDER [...]
"""
import os, struct, sys

_TABLE = []


def crc_table():
    if not _TABLE:
        for i in range(256):
            c = i << 24
            for _ in range(8):
                c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else (c << 1)
                c &= 0xFFFFFFFF
            _TABLE.append(c)
    return _TABLE


def crc(data):
    t = crc_table()
    c = 0xFFFFFFFF
    for b in data:
        c = ((c << 8) & 0xFFFFFFFF) ^ t[(c >> 24) ^ b]
    return c ^ 0xFFFFFFFF


def wstr(b):
    s = b.decode('utf-16-le', errors='replace')
    return s.split('\0', 1)[0]


def check(path):
    d = open(path, 'rb').read()
    print('== %s  (%d bytes)' % (os.path.basename(path), len(d)))
    o = 0
    if d[:4] == b'RGMH':
        ver, hsize, toff, tsize = struct.unpack_from('<IIQI', d, 4)
        names = [wstr(d[0x28 + 0x200 * k:0x28 + 0x200 * (k + 1)]) for k in range(4)]
        print('  RGMH version %d, header 0x%x, thumbnail at 0x%x size 0x%x, game name set %s, save name len %d, '
              'level name len %d, comments len %d' % (ver, hsize, hsize + toff, tsize, 'yes' if names[0] else 'no',
                                                     len(names[1]), len(names[2]), len(names[3])))
        if d[hsize + toff:hsize + toff + 8] == b'\x89PNG\r\n\x1a\n':
            print('  thumbnail: PNG')
        o = hsize
    else:
        print('  no RGMH header (raw PCUD file)')
    magic, ver, game, gver, count, tcrc, hcrc = struct.unpack_from('<4sI4sIIII', d, o)
    hc = crc(d[o:o + 0x18])
    print('  %s version 0x%x game %r 0x%x, entries %d; header CRC %s' % (
        magic.decode('latin-1'), ver, game.decode('latin-1'), gver, count, 'ok' if hc == hcrc else
        'BAD (stored 0x%08x, computed 0x%08x)' % (hcrc, hc)))
    t = o + 0x1c
    tc = crc(d[t:t + 12 * count])
    print('  table at 0x%x; table CRC %s' % (t, 'ok' if tc == tcrc else 'BAD (stored 0x%08x, computed 0x%08x)' % (tcrc, tc)))
    ok = hc == hcrc and tc == tcrc
    for k in range(count):
        size, off, dcrc = struct.unpack_from('<III', d, t + 12 * k)
        inside = off + size <= len(d)
        c = crc(d[off:off + size]) if inside else None
        ok = ok and inside and c == dcrc
        print('  entry %d: offset 0x%x size 0x%x, ends at 0x%x (file 0x%x); data CRC %s' % (
            k, off, size, off + size, len(d), ('ok' if c == dcrc else 'BAD') if inside else 'outside the file'))
    print('  RESULT %s' % ('all CRCs ok' if ok else 'MISMATCH'))
    return ok


def main(argv):
    if not argv: sys.exit(__doc__)
    files = []
    for a in argv:
        if os.path.isdir(a):
            files += sorted(os.path.join(a, f) for f in os.listdir(a) if f.lower().endswith('.trusave'))
        else:
            files.append(a)
    bad = sum(0 if check(f) else 1 for f in files)
    print('%d file(s), %d with a mismatch' % (len(files), bad))


if __name__ == '__main__':
    main(sys.argv[1:])
