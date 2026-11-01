"""Audit the texture sections (type 5, PCD9) of PC DRM files, read-only: format, size, mip count, flags, and the
data size the header implies (level-major, cubemaps 6 faces) against the stored size - every texture that
Direct3D 9 CreateTexture / the engine's upload could reject or overrun is listed (unknown format, mips past the
1x1 level, data size mismatch, zero / non-power-of-two size).
Test 48d (2026-10-31): D3D device error with the doppelganger figure - are its textures within what the PC base
player files use?

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tex_header_audit.py FILE_OR_DIR [...] [--all]
  --all: one line per texture (default: summary per file plus the suspicious ones)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

PHDR = struct.Struct('<4sIIIHHBBH')
KIND = {0x31545844: ('DXT1', 8), 0x33545844: ('DXT3', 16), 0x35545844: ('DXT5', 16), 0x15: ('ARGB', 4)}


def need(fmt, w, h, mips, faces):
    kind, bpb = KIND[fmt]
    n = 0
    for l in range(mips + 1):
        lw, lh = max(1, w >> l), max(1, h >> l)
        blocks = lw * lh if kind == 'ARGB' else max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4)
        n += blocks * bpb * faces
    return n


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'): yield os.path.join(p, n)
        else:
            yield p


def main(argv):
    every = '--all' in argv; argv = [a for a in argv if a != '--all']
    for path in files(argv):
        D = DW.read(open(path, 'rb').read(), 'le')
        fmts = collections.Counter(); flags = collections.Counter(); bad = []; total = 0; big = 0
        for s in D.sections:
            if s.type != 5: continue
            total += 1
            d = s.data
            if len(d) < 24:
                bad.append((s.id, 'short section %d bytes' % len(d))); continue
            magic, fmt, size, pal, w, h, depth, mips, fl = PHDR.unpack_from(d, 0)
            name = KIND.get(fmt, ('0x%x' % fmt,))[0]
            fmts[name] += 1; flags['0x%04x' % fl] += 1
            big = max(big, w, h)
            faces = 6 if fl & 0x8000 else 1
            why = []
            if magic != b'PCD9': why.append('magic %r' % magic)
            if fmt not in KIND: why.append('format %s' % name)
            if w == 0 or h == 0: why.append('zero size')
            elif (w & (w - 1)) or (h & (h - 1)): why.append('non-pow2')
            if w and h and mips > max(w, h).bit_length() - 1: why.append('mips %d > log2' % mips)
            if size != len(d) - 24: why.append('size field %d != data %d' % (size, len(d) - 24))
            if fmt in KIND and w and h:
                n = need(fmt, w, h, mips, faces)
                if n != len(d) - 24: why.append('data %d != needed %d' % (len(d) - 24, n))
            if pal: why.append('palette %d' % pal)
            if why: bad.append((s.id, ' '.join(why)))
            if every:
                print('  %s 5:%-6d %s %4dx%-4d mips %2d flags 0x%04x depth %d %s'
                      % (os.path.basename(path), s.id, name, w, h, mips, fl, depth, '; '.join(why)))
        print('%s: %d textures, formats %s, flags %s, max side %d, suspicious %d'
              % (os.path.basename(path), total, dict(fmts), dict(flags.most_common(8)), big, len(bad)))
        for sid, why in bad: print('    5:%-6d %s' % (sid, why))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
