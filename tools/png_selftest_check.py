"""Check the PNG files of TruMenu 0.10.5's offline shot test (src/asi/TruMenu/selftest/TruShotPngTest.cpp writes
test_<n>.png, test_<n>.src and manifest.txt into one folder) - read-only.

For every case: PNG signature, every chunk's CRC-32, IHDR (w, h, 8-bit RGB, no interlace), IDAT inflated with Python's
zlib (checks the deflate stream and the Adler-32), the five PNG row filters undone here, and the pixels compared with
this tool's own conversion of the raw back-buffer pixels in test_<n>.src (kind 1 X8R8G8B8 / A8R8G8B8, 2 R5G6B5,
3 X1R5G5B5 / A1R5G5B5, 4 A2R10G10B10; row pitch from the manifest, padding ignored). With --png FILE only that one PNG
is decoded and summarised (e.g. a real shot from TruShots\\).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/png_selftest_check.py DIR            exit 1 on any difference
  ../bin/pyt -t 120 tools/png_selftest_check.py --png FILE
"""
import os, struct, sys, zlib


def decode(data):
    """(w, h, rgb bytes, notes) of an 8-bit RGB PNG; raises ValueError with the reason"""
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('no PNG signature')
    pos, idat, ihdr, chunks = 8, b'', None, []
    while pos < len(data):
        n, typ = struct.unpack_from('>I4s', data, pos)
        body = data[pos + 8:pos + 8 + n]
        crc = struct.unpack_from('>I', data, pos + 8 + n)[0]
        if zlib.crc32(typ + body) & 0xffffffff != crc: raise ValueError('CRC of chunk %s wrong' % typ)
        chunks.append(typ.decode('ascii'))
        if typ == b'IHDR': ihdr = struct.unpack('>IIBBBBB', body)
        elif typ == b'IDAT': idat += body
        elif typ == b'IEND': break
        pos += 12 + n
    if not ihdr: raise ValueError('no IHDR')
    w, h, depth, ctype, comp, filt, inter = ihdr
    if (depth, ctype, comp, filt, inter) != (8, 2, 0, 0, 0): raise ValueError('IHDR %s' % (ihdr,))
    raw = zlib.decompress(idat)              # also checks the Adler-32
    row = w * 3
    if len(raw) != h * (row + 1): raise ValueError('inflated %d bytes, want %d' % (len(raw), h * (row + 1)))
    out = bytearray(h * row)
    used = [0] * 5
    for y in range(h):
        t = raw[y * (row + 1)]
        if t > 4: raise ValueError('row %d filter %d' % (y, t))
        used[t] += 1
        src = raw[y * (row + 1) + 1:(y + 1) * (row + 1)]
        cur = bytearray(row)
        up = out[(y - 1) * row:y * row] if y else bytearray(row)
        for x in range(row):
            a = cur[x - 3] if x >= 3 else 0
            b = up[x]
            c = up[x - 3] if x >= 3 else 0
            if t == 0: p = 0
            elif t == 1: p = a
            elif t == 2: p = b
            elif t == 3: p = (a + b) // 2
            else:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            cur[x] = (src[x] + p) & 0xff
        out[y * row:(y + 1) * row] = cur
    return w, h, bytes(out), 'chunks %s, filters None/Sub/Up/Avg/Paeth rows %s' % ('+'.join(chunks), used)


def convert(src, w, h, kind, pitch):
    """this tool's own conversion of the raw source pixels to RGB"""
    out = bytearray()
    for y in range(h):
        line = src[y * pitch:y * pitch + pitch]
        for x in range(w):
            if kind == 1:
                b, g, r = line[4 * x], line[4 * x + 1], line[4 * x + 2]
            elif kind == 4:
                v = struct.unpack_from('<I', line, 4 * x)[0]
                r, g, b = ((v >> 20) & 1023) >> 2, ((v >> 10) & 1023) >> 2, (v & 1023) >> 2
            else:
                v = struct.unpack_from('<H', line, 2 * x)[0]
                if kind == 2:
                    r5, g6, b5 = (v >> 11) & 31, (v >> 5) & 63, v & 31
                    g = (g6 << 2) | (g6 >> 4)
                else:
                    r5, g5, b5 = (v >> 10) & 31, (v >> 5) & 31, v & 31
                    g = (g5 << 3) | (g5 >> 2)
                r, b = (r5 << 3) | (r5 >> 2), (b5 << 3) | (b5 >> 2)
            out += bytes((r, g, b))
    return bytes(out)


def main(argv):
    if not argv: sys.exit(__doc__)
    if argv[0] == '--png':
        data = open(argv[1], 'rb').read()
        w, h, rgb, notes = decode(data)
        print('ok %s: %dx%d, %d bytes (%.1f %% of raw RGB), %s' % (argv[1], w, h, len(data), 100.0 * len(data) / len(rgb),
                                                                 notes))
        return 0
    folder = argv[0]
    bad = 0
    lines = open(os.path.join(folder, 'manifest.txt')).read().split('\n')
    for line in lines:
        if not line.strip(): continue
        n, w, h, kind, pitch, ms, size = line.split()
        n, w, h, kind, pitch, size = int(n), int(w), int(h), int(kind), int(pitch), int(size)
        png = open(os.path.join(folder, 'test_%d.png' % n), 'rb').read()
        src = open(os.path.join(folder, 'test_%d.src' % n), 'rb').read()
        try:
            pw, ph, rgb, notes = decode(png)
        except ValueError as e:
            print('FAIL case %d: %s' % (n, e))
            bad += 1
            continue
        want = convert(src, w, h, kind, pitch)
        if (pw, ph) != (w, h) or len(png) != size:
            print('FAIL case %d: size %dx%d / %d bytes, manifest %dx%d / %d' % (n, pw, ph, len(png), w, h, size))
            bad += 1
        elif rgb != want:
            first = next(i for i in range(len(rgb)) if rgb[i] != want[i])
            print('FAIL case %d: pixel byte %d differs (png %d, source %d)' % (n, first, rgb[first], want[first]))
            bad += 1
        else:
            print('ok case %d: %dx%d kind %d pitch %d, %d bytes PNG = %.1f %% of raw RGB, encode %s ms, pixels equal; %s'
                  % (n, w, h, kind, pitch, len(png), 100.0 * len(png) / max(1, len(rgb)), ms, notes))
    print('%d case(s) failed' % bad if bad else 'all cases ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
