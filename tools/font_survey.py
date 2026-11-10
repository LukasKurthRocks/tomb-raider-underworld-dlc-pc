"""Font survey (read-only): find and describe the game's bitmap font in a DRM.

PC 1.1: the font is DTP section (type 7) id 46 of generalbank.drm. Its descriptor, as the font constructor
0x475260 reads it:
  +0x00 texture page 0 (section id ref, type 5)   +0x04 texture page 1 (section id ref, type 5)
  +0x08 u32 (46 on PC)   +0x0c u32 glyph count n   +0x10 pointer to the glyph entries (internal relocation)
  +0x14 u32   +0x18 / +0x1c f32 (copied to font +0x424 / +0x428)   +0x20 u16, +0x22 s16 (read by the 3D text
  path 0x4754d0)
Glyph entry, 12 bytes, sorted by code (binary search 0x4751e0, comparator 0x4f1ba0; codes < 0x100 cached,
U+00A0 drawn as U+0020; a missing code falls back to the glyph of [0x851630]):
  u32 code point, u16 width, u16 x, u16 y, u8 +10, u8 +11
Text is UTF-8, decoded per character (0x597bf0 length, 0x597c40 decode, 1..4 bytes).

Finding the descriptor: every section whose relocations have two type-5 id refs at +0 / +4 and an internal
pointer at +0x10, with a plausible count at +0x0c and ascending codes in the array.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/font_survey.py scan FILE.drm [--be]               every font descriptor + code ranges
  ../bin/pyt -t 300 tools/font_survey.py glyphs FILE.drm SECTION_ID [--be]  all glyph entries of that descriptor
  ../bin/pyt -t 300 tools/font_survey.py pages FILE.drm SECTION_ID OUT_DIR  (PC only) both texture pages as PNG
                                                                            + page 0 with the glyph boxes
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def descriptors(D, e):
    """[(section index, descriptor dict)] for every font descriptor in the DRM."""
    out = []
    for si, s in enumerate(D.sections):
        if not s.reloc or len(s.data) < 0x24: continue
        r = R.parse(s.reloc, e)
        ids = r.id_offsets()
        intr = dict(r.internal)
        if ids.get(0) != 5 or ids.get(4) != 5 or 0x10 not in intr: continue
        w = struct.unpack_from(e + '6I', s.data, 0)
        n, arr = w[3], intr[0x10]
        if not (1 <= n <= 0x10000) or arr + 12 * n > len(s.data) + 12: continue
        ents = []
        for i in range(n):
            b = s.data[arr + 12 * i:arr + 12 * i + 12].ljust(12, b'\0')   # the PC section is cut 1 byte short
            ents.append(struct.unpack(e + 'IHHHBB', b))
        codes = [x[0] for x in ents]
        if any(b <= a for a, b in zip(codes, codes[1:])): continue
        out.append((si, dict(tex0=w[0], tex1=w[1], w8=w[2], n=n, arr=arr, w14=w[5],
                             f18=struct.unpack_from(e + 'f', s.data, 0x18)[0], f1c=struct.unpack_from(e + 'f', s.data, 0x1c)[0],
                             h20=struct.unpack_from(e + 'H', s.data, 0x20)[0], h22=struct.unpack_from(e + 'h', s.data, 0x22)[0],
                             ents=ents)))
    return out


def ranges(codes):
    rs = []
    for c in codes:
        if rs and c == rs[-1][1] + 1: rs[-1][1] = c
        else: rs.append([c, c])
    return rs


BLOCKS = [(0x0000, 0x007f, 'Basic Latin'), (0x0080, 0x00ff, 'Latin-1'), (0x0100, 0x024f, 'Latin Extended'),
          (0x0370, 0x03ff, 'Greek'), (0x0400, 0x04ff, 'Cyrillic'), (0x1800, 0x18af, 'private: pad buttons (Mongolian block)'),
          (0x2000, 0x206f, 'General Punctuation'), (0x2100, 0x22ff, 'Letterlike / Math'), (0x2460, 0x27bf, 'Symbols'),
          (0x3000, 0x303f, 'CJK Symbols and Punctuation'), (0x3040, 0x309f, 'Hiragana'), (0x30a0, 0x30ff, 'Katakana'),
          (0x4e00, 0x9fff, 'CJK Unified Ideographs'), (0xe000, 0xf8ff, 'Private Use Area'), (0xff00, 0xffef, 'Halfwidth and Fullwidth Forms')]


def block_counts(codes):
    c = collections.Counter()
    for x in codes:
        for a, b, name in BLOCKS:
            if a <= x <= b: c[name] += 1; break
        else: c['other'] += 1
    return c


def describe(D, si, d, show_all=False):
    s = D.sections[si]
    print('section %d (type %d, id %d, %d bytes): font descriptor' % (si, s.type, s.id, len(s.data)))
    print('  texture pages: id %d, id %d' % (d['tex0'], d['tex1']))
    for t in (d['tex0'], d['tex1']):
        x = [q for q in D.sections if q.type == 5 and q.id == t]
        print('    id %d: %s' % (t, ('%d bytes, header %s' % (len(x[0].data), x[0].data[:8].hex())) if x else 'not in this DRM'))
    print('  +0x08 %d  +0x0c count %d  glyph array +0x%x  +0x14 %d  +0x18 %g  +0x1c %g  +0x20 %d  +0x22 %d'
          % (d['w8'], d['n'], d['arr'], d['w14'], d['f18'], d['f1c'], d['h20'], d['h22']))
    ents = d['ents']
    codes = [x[0] for x in ents]
    print('  code points: %d, U+%04X..U+%04X' % (len(codes), codes[0], codes[-1]))
    for k, v in sorted(block_counts(codes).items()): print('    %-42s %d' % (k, v))
    rs = ranges(codes)
    print('  %d ranges: %s' % (len(rs), ', '.join('U+%04X' % a if a == b else 'U+%04X..%04X' % (a, b) for a, b in rs)))
    for k, name in ((1, 'width'), (2, 'x'), (3, 'y'), (4, '+10'), (5, '+11')):
        vals = collections.Counter(x[k] for x in ents)
        print('  %-6s min %d max %d distinct %d  top %s' % (name, min(vals), max(vals), len(vals),
              ' '.join('%d:%d' % kv for kv in vals.most_common(6))))
    lim = len(ents) if show_all else min(len(ents), 12)
    for i in range(lim):
        x = ents[i]
        ch = chr(x[0]) if x[0] >= 0x20 and not 0xd800 <= x[0] < 0xe000 else '?'
        print('    %5d  U+%04X %-4r w %3d  x %4d  y %4d  %3d %3d' % ((i, x[0], ch) + x[1:]))


def pages(D, si, d, out):
    import tex_convert as T
    from PIL import Image, ImageDraw
    os.makedirs(out, exist_ok=True)
    h = d['h22'] if d['h22'] > 0 else 40
    for k, t in enumerate((d['tex0'], d['tex1'])):
        x = [q for q in D.sections if q.type == 5 and q.id == t]
        if not x: print('  page %d id %d: not in this DRM' % (k, t)); continue
        im = Image.fromarray(T.pc_image(x[0].data))
        p = os.path.join(out, 'font_page%d_id%d.png' % (k, t)); im.save(p)
        print('  %s  %dx%d %s' % (p, im.width, im.height, im.mode))
        if k == 0:
            bx = Image.new('RGBA', im.size, (0, 0, 0, 255)); bx.alpha_composite(im.convert('RGBA'))   # white glyphs
            dr = ImageDraw.Draw(bx)
            for c, w, gx, gy, _, _ in d['ents']:
                dr.rectangle([gx, gy, gx + w - 1, gy + h - 1], outline=(255, 0, 0, 255))
            p = os.path.join(out, 'font_page0_boxes.png'); bx.save(p); print('  %s (box height %d)' % (p, h))


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    e = '>' if '--be' in argv else '<'
    show_all = argv[0] == 'glyphs'
    argv = [a for a in argv if a != '--be']
    D = DW.read(open(argv[1], 'rb').read(), 'be' if e == '>' else 'le')
    found = descriptors(D, e)
    if argv[0] == 'scan':
        for si, d in found: describe(D, si, d)
        print('font descriptors: %d' % len(found))
        return
    sid = int(argv[2])
    sel = [(si, d) for si, d in found if D.sections[si].id == sid]
    if not sel: sys.exit('no font descriptor in section id %d' % sid)
    if argv[0] == 'glyphs': describe(D, sel[0][0], sel[0][1], True)
    elif argv[0] == 'pages': pages(D, sel[0][0], sel[0][1], argv[3])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
