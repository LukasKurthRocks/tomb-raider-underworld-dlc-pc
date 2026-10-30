"""Save the textures (type 5, PCD9) of a PC DRM as PNG files plus a contact sheet (read-only on the DRM).
Finding 43 follow-up: what the grapple ring / waterfall objects bring as textures (tools/tex_convert.pc_image).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_textures_png.py FILE.drm OUT_DIR
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, tex_convert as T
from tex_dlc import contact_sheet


def main(argv):
    src, out = argv[0], argv[1]
    os.makedirs(out, exist_ok=True)
    D = DW.read(open(src, 'rb').read(), 'le')
    imgs = []
    from PIL import Image
    for i, s in enumerate(D.sections):
        if s.type != 5: continue
        try:
            im = T.pc_image(s.data)
        except Exception as e:
            print('  sec %d id %d: %s' % (i, s.id, e)); continue
        p = os.path.join(out, 'sec%03d_id%d.png' % (i, s.id))
        Image.fromarray(im).save(p)
        label = 'id%d %s' % (s.id, s.data[4:8].decode('ascii', 'replace'))
        imgs.append((label + ('a' if im.shape[-1] == 4 else ''), im))
        print('  %s  %dx%d' % (p, im.shape[1], im.shape[0]))
    if imgs: contact_sheet([(l, im) for l, im in imgs], os.path.join(out, 'contact_sheet.png'))


if __name__ == '__main__':
    main(sys.argv[1:])
