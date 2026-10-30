"""DIAGNOSTIC tool: give every texture slot of one material its own NUMBERED texture - a big digit 1..n on a
distinct background colour with a grid (shows the UV direction and scale) - so a screenshot tells which slot lands
where (finding 43: which of the 8 textures of the DLC 2 waterfall material 24920 shows on the opaque column?).
Textures are uncompressed A8R8G8B8 (format 0x15, as base-game PC textures), 256 x 256 with all mip levels, added
as new sections with the given (unused) texture ids; the material's texture references are pointed at them in
entry order (slot 1 = first texture entry). Alpha is fully opaque.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/texture_digits.py IN.drm OUT.drm MATERIAL_ID NEW_TEX_ID[,NEW_TEX_ID...]
  (one new id per texture reference of the material; pick ids no DRM uses, e.g. gaps below the highest DLC id)
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

FONT = {          # 5 x 7 bitmap digits
    '0': ['01110', '10001', '10011', '10101', '11001', '10001', '01110'],
    '1': ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
    '2': ['01110', '10001', '00001', '00010', '00100', '01000', '11111'],
    '3': ['11110', '00001', '00001', '01110', '00001', '00001', '11110'],
    '4': ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
    '5': ['11111', '10000', '11110', '00001', '00001', '10001', '01110'],
    '6': ['00110', '01000', '10000', '11110', '10001', '10001', '01110'],
    '7': ['11111', '00001', '00010', '00100', '01000', '01000', '01000'],
    '8': ['01110', '10001', '10001', '01110', '10001', '10001', '01110'],
    '9': ['01110', '10001', '10001', '01111', '00001', '00010', '01100'],
}
COLOURS = [(255, 0, 0), (0, 200, 0), (0, 80, 255), (255, 220, 0), (255, 0, 255), (0, 230, 230), (255, 128, 0),
           (128, 0, 255), (128, 128, 128), (255, 255, 255)]


def image(n, size=256):
    """RGBA uint8: slot colour background, white grid every 32 px, big black digit with white outline"""
    bg = COLOURS[(n - 1) % len(COLOURS)]
    a = np.zeros((size, size, 4), np.uint8); a[..., :3] = bg; a[..., 3] = 255
    a[::32, :, :3] = 255; a[:, ::32, :3] = 255
    s = size // 10; txt = str(n); w = len(txt) * 6 * s
    x0, y0 = (size - w) // 2, (size - 7 * s) // 2
    for k, ch in enumerate(txt):
        for r, row in enumerate(FONT[ch]):
            for c, bit in enumerate(row):
                if bit == '1':
                    x, y = x0 + (k * 6 + c) * s, y0 + r * s
                    a[y - 2:y + s + 2, x - 2:x + s + 2, :3] = 255
                    a[y:y + s, x:x + s, :3] = 0
    return a


def section_bytes(rgba):
    """PCD9 A8R8G8B8 texture section: 24-byte header + every mip level (BGRA bytes), level-major"""
    levels = []; img = rgba.astype(np.float32)
    while True:
        levels.append(img.astype(np.uint8)[..., [2, 1, 0, 3]].tobytes())
        if img.shape[0] == 1: break
        img = img.reshape(img.shape[0] // 2, 2, img.shape[1] // 2, 2, 4).mean(axis=(1, 3))
    data = b''.join(levels); h, w = rgba.shape[:2]
    hdr = struct.pack('<4sIIIHHBBH', b'PCD9', 0x15, len(data), 0, w, h, 0x20, len(levels) - 1, 0)
    return hdr + data


def main(argv):
    inp, out, mid, ids = argv[0], argv[1], int(argv[2]), [int(x) for x in argv[3].split(',')]
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    m = next(s for s in D.sections if s.type == 10 and s.id == mid)
    refs = sorted(off for kind, off in R.parse(m.reloc, 'le').idref if kind == 5)
    if len(ids) < len(refs): raise SystemExit('material %d has %d texture references, %d ids given' % (mid, len(refs), len(ids)))
    have = {s.id for s in D.sections if s.type == 5}
    if have & set(ids): raise SystemExit('texture id(s) already in the file: %s' % sorted(have & set(ids)))
    d = bytearray(m.data); tmpl = next(s for s in D.sections if s.type == 5)
    for n, (off, tid) in enumerate(zip(refs, ids), 1):
        old = struct.unpack_from('<I', d, off)[0]
        D.sections.append(DW.Section(5, tid, section_bytes(image(n)), b'', tmpl.flags, tmpl.ver, tmpl.spec))
        struct.pack_into('<I', d, off, tid)
        print('slot %d (+%#x): texture %d -> %d (digit %d, colour %s)' % (n, off, old, tid, n, COLOURS[(n - 1) % len(COLOURS)]))
    m.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)


if __name__ == '__main__':
    main(sys.argv[1:])
