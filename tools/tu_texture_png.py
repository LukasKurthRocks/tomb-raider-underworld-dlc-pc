"""Save textures (type 5) of an Xbox base-game DRM (title update or retail) as PNG, read-only on the game data.
Converts each Xenos texture with tex_convert.convert (as tools/generalbank_tu_textures.py does) and writes the base
level as PNG, plus one line per texture (size, format, md5). For a look at the title update's new generalbank
textures (pause menu 7171, 7215-7219, 7350, 7669, 7895-7898; HUD 7899 / 7036) without building anything.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_texture_png.py SRC:NAME.drm IDS OUT_DIR
  SRC   tu or retail (tools/drm_idrefs.load), e.g. tu:generalbank.drm
  IDS   comma-separated texture ids;  OUT_DIR below work/ (git-excluded), never in the repository
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_convert as T
import drm_idrefs as IR


def main(argv):
    if len(argv) != 3: sys.exit(__doc__)
    src, ids, out = argv[0], [int(x) for x in argv[1].split(',')], argv[2]
    os.makedirs(out, exist_ok=True)
    tex = {i: d for t, i, d, _ in IR.load(src)[0] if t == 5}
    from PIL import Image
    import numpy as np
    for i in ids:
        x = tex.get(i)
        if x is None:
            print('texture %d: not in %s' % (i, src)); continue
        new = T.convert(bytes(x))
        h = struct.unpack_from('<4sIIIHHBBH', new, 0)
        im = np.asarray(T.pc_image(new), dtype=np.uint8)
        p = os.path.join(out, 'tex%d.png' % i)
        Image.fromarray(im).save(p)
        print('texture %d: %dx%d fmt 0x%x mips %d, Xbox %d B md5 %s -> %s' % (
            i, h[4], h[5], h[1], h[7], len(x), hashlib.md5(bytes(x)).hexdigest(), p))


if __name__ == '__main__':
    main(sys.argv[1:])
