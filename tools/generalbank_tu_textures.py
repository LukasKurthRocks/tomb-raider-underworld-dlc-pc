"""Bring textures the Xbox title update CHANGED (or added) in generalbank into a PC generalbank (writes OUT only).

Finding 43, test 43: the DLC 2 hint box draws its background with texture 76 (kind-A id reference of TU script 10 /
our PC script 9 at +0xf90; the retail element uses texture 56). The title update replaced texture 76 in its own
generalbank (same size and header as retail, different pixels: the dark rounded box), while the PC generalbank still
carries the retail picture - so on PC the box looked faint. This tool converts the TU section with
tex_convert.convert (Xbox Xenos tiled -> PCD9) and puts it into the PC file.

Guards: an id is replaced only if the TU section differs from the retail Xbox one (otherwise the PC picture is
already Crystal's own) and the PC section has the same format / size / mip count as the converted TU picture; a
missing PC section is only added with --add-missing. Every decision is printed.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/generalbank_tu_textures.py IN.drm OUT.drm IDS [--add-missing] [--png DIR]
  IDS   comma-separated texture ids (type 5), e.g. 76
  --png DIR  also write old (PC) and new (TU) base level as PNG for a visual check
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, tex_convert as T
import drm_idrefs as IR


def md5(b):
    return hashlib.md5(bytes(b)).hexdigest()


def save_png(data, path):
    from PIL import Image
    import numpy as np
    Image.fromarray(np.asarray(T.pc_image(data), dtype=np.uint8)).save(path)


def main(argv):
    add = '--add-missing' in argv; argv = [a for a in argv if a != '--add-missing']
    png = None
    if '--png' in argv:
        k = argv.index('--png'); png = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 3: sys.exit(__doc__)
    inp, out, ids = argv[0], argv[1], [int(x) for x in argv[2].split(',')]
    if os.path.abspath(inp) == os.path.abspath(out): sys.exit('OUT must differ from IN')
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    tu = {(t, i): d for t, i, d, _ in IR.load('tu:generalbank.drm')[0] if t == 5}
    rt = {(t, i): d for t, i, d, _ in IR.load('retail:generalbank.drm')[0] if t == 5}
    if png: os.makedirs(png, exist_ok=True)
    changed = 0
    for i in ids:
        x = tu.get((5, i))
        if x is None: sys.exit('texture %d not in the title update generalbank' % i)
        r = rt.get((5, i))
        if r is not None and bytes(r) == bytes(x):
            print('texture %d: TU = retail - nothing to do' % i); continue
        new = T.convert(bytes(x))
        s = next((q for q in D.sections if q.type == 5 and q.id == i), None)
        if s is None:
            if not add: sys.exit('texture %d missing in IN (use --add-missing)' % i)
            ref = next(q for q in D.sections if q.type == 5)
            D.sections.append(DW.Section(5, i, new, b'', ref.flags, ref.ver, ref.spec))
            print('texture %d: added (TU md5 %s -> PC %d bytes md5 %s)' % (i, md5(x), len(new), md5(new))); changed += 1
            continue
        oh, nh = struct.unpack_from('<4sIIIHHBBH', s.data, 0), struct.unpack_from('<4sIIIHHBBH', new, 0)
        if oh[0] != b'PCD9' or (oh[1], oh[4], oh[5], oh[7]) != (nh[1], nh[4], nh[5], nh[7]) or len(s.data) != len(new):
            sys.exit('texture %d: PC header %s differs from the converted TU header %s - not replaced' % (i, oh, nh))
        if png:
            save_png(s.data, os.path.join(png, 'tex%d_pc_old.png' % i)); save_png(new, os.path.join(png, 'tex%d_tu_new.png' % i))
        print('texture %d: replaced, %dx%d fmt 0x%x mips %d; PC md5 %s -> %s (TU %s, retail %s)' % (
            i, nh[4], nh[5], nh[1], nh[7], md5(s.data), md5(new), md5(x), md5(r) if r is not None else '-'))
        s.data = new; changed += 1
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('%d texture(s) changed -> %s md5 %s' % (changed, out, md5(o)))


if __name__ == '__main__':
    main(sys.argv[1:])
