"""Simple preview of the Mesh sections (type 12) of a DRM as a PNG (four flat-shaded orthographic views: front, side,
top, isometric) plus its textures as PNG, read-only on the DRM. For a first look at an object nothing loads
(dlc_rewards, object 891, Befund-Versteckte-Inhalte.md 3.1) without starting the game.

Per mesh it prints the bounding box (game units; about 290 units = 1 m in TRU, Lara is ~511 units tall), batch / vertex / triangle counts, the
texture and material ids of the mesh's material table and, for small meshes (<= 64 vertices), the distinct vertex
positions. Textures: PC files through tex_convert.pc_image, Xbox files (:be) first through tex_convert.convert
(the converter the port uses), then the same; per texture size, format tag and mean RGBA.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mesh_preview_png.py FILE.drm[:be] OUT_DIR [--size 320]
Writes OUT_DIR/mesh_<id>.png (2 x 2 views, labelled) and OUT_DIR/tex_<id>.png (+ tex_<id>_x32.png, nearest-neighbour
enlarged, for tiny textures).
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import tex_convert as T
from mesh_tr8 import Mesh, SEM, H

POS = 0xD2F7D823


def batch_geometry(m, d, e):
    """[(verts [n,3] float, tris [k,3] int)] per batch (POSITION as 3 floats, type 2; local index list)"""
    idx = m.indices() if m.numIndices else ()
    out = []
    for b in m.meshes:
        vf = b['vf']
        if not vf: continue
        el = {s: (o, t) for s, o, t, _ in vf['elems']}
        if POS not in el or el[POS][1] != 2:
            print('   batch: POSITION type %s not supported' % (el.get(POS),)); continue
        po, st = el[POS][0], vf['stride']
        base = H + b['vdataOff']
        v = np.array([struct.unpack_from(e + '3f', d, base + i * st + po) for i in range(b['numVerts'])], dtype=float)
        t = np.array(idx[b['baseIndex']:b['baseIndex'] + 3 * b['numTris']], dtype=int).reshape(-1, 3)
        out.append((v, t))
    return out


def render(views, size, title):
    from PIL import Image, ImageDraw
    pad = 24
    img = Image.new('RGB', (2 * size, 2 * size + pad), (235, 235, 235))
    dr = ImageDraw.Draw(img)
    dr.text((6, 6), title, fill=(0, 0, 0))
    allv = np.vstack([v for v, t in views])
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    # projections: (name, 2x3 screen matrix with x right / y up, view direction for depth sort)
    iso = np.array([[0.7071, 0.7071, 0.0], [-0.4082, 0.4082, 0.8165]])
    P = [('front (x / z)', np.array([[1.0, 0, 0], [0, 0, 1.0]]), np.array([0, 1.0, 0])),
         ('side (y / z)', np.array([[0, 1.0, 0], [0, 0, 1.0]]), np.array([-1.0, 0, 0])),
         ('top (x / y)', np.array([[1.0, 0, 0], [0, 1.0, 0]]), np.array([0, 0, -1.0])),
         ('iso', iso, -np.cross(iso[0], iso[1]))]       # view direction = into the screen (larger = farther)
    for k, (name, M, vd) in enumerate(P):
        ox, oy = (k % 2) * size, pad + (k // 2) * size
        dr.rectangle([ox, oy, ox + size - 1, oy + size - 1], outline=(150, 150, 150))
        dr.text((ox + 4, oy + 4), name, fill=(60, 60, 60))
        s2 = allv @ M.T
        lo, hi = s2.min(0), s2.max(0)
        span = max(float((hi - lo).max()), 1e-6)
        sc = (size - 40) / span
        ctr = (lo + hi) / 2
        tris = []
        for v, t in views:
            for a, b, c in t:
                p = v[[a, b, c]]
                n = np.cross(p[1] - p[0], p[2] - p[0]); ln = np.linalg.norm(n)
                if ln == 0: continue
                n /= ln
                shade = 0.35 + 0.65 * abs(float(n @ light))
                depth = float((p.mean(0)) @ vd)
                q = (p @ M.T - ctr) * sc
                pts = [(ox + size / 2 + x, oy + size / 2 - y) for x, y in q]
                tris.append((depth, pts, shade))
        for depth, pts, shade in sorted(tris, key=lambda x: -x[0]):
            g = int(60 + 170 * shade)
            dr.polygon(pts, fill=(g, int(g * 0.85), int(g * 0.55)), outline=(30, 30, 30))
    return img


def main(argv):
    size = 320
    if '--size' in argv:
        k = argv.index('--size'); size = int(argv[k + 1]); del argv[k:k + 2]
    spec, out = argv[0], argv[1]
    path, en = (spec[:-3], 'be') if spec.endswith(':be') else (spec, 'le')
    e = '>' if en == 'be' else '<'
    os.makedirs(out, exist_ok=True)
    D = DW.read(open(path, 'rb').read(), en)
    from PIL import Image
    for s in D.sections:
        if s.type == 5:
            try:
                data = T.convert(bytes(s.data)) if en == 'be' else s.data
                im = np.asarray(T.pc_image(data), dtype=np.uint8)
            except Exception as ex:
                print('texture 5:%d: %s' % (s.id, ex)); continue
            p = os.path.join(out, 'tex_%d.png' % s.id)
            Image.fromarray(im).save(p)
            if max(im.shape[:2]) <= 32:
                Image.fromarray(im).resize((im.shape[1] * 32, im.shape[0] * 32), Image.NEAREST).save(
                    os.path.join(out, 'tex_%d_x32.png' % s.id))
            mean = [int(round(float(x))) for x in im.reshape(-1, im.shape[-1]).mean(0)]
            uniq = len({tuple(px) for px in im.reshape(-1, im.shape[-1])})
            print('texture 5:%d  %dx%d  %s  mean RGBA %s  distinct pixels %d -> %s'
                  % (s.id, im.shape[1], im.shape[0], data[4:8].decode('ascii', 'replace'), mean, uniq, p))
    for s in D.sections:
        if s.type != 12 or s.data[0x10:0x14] not in (b'hseM', b'Mesh'): continue
        m = Mesh(s.data, en)
        geo = batch_geometry(m, s.data, e)
        if not geo: print('mesh 12:%d: no geometry' % s.id); continue
        allv = np.vstack([v for v, t in geo])
        lo, hi = allv.min(0), allv.max(0)
        print('mesh 12:%d  %d bytes  batches %d  verts %d  tris %d  textures %s  materials %s'
              % (s.id, len(s.data), len(geo), len(allv), sum(len(t) for v, t in geo), m.textures, m.materials))
        print('   bbox min (%.2f, %.2f, %.2f)  max (%.2f, %.2f, %.2f)  size %.2f x %.2f x %.2f units'
              % (tuple(lo) + tuple(hi) + tuple(hi - lo)))
        if len(allv) <= 64:
            pts = sorted({tuple(round(float(c), 3) for c in p) for p in allv})
            print('   distinct positions %d: %s' % (len(pts), ' '.join('(%g, %g, %g)' % p for p in pts)))
        p = os.path.join(out, 'mesh_%d.png' % s.id)
        render(geo, size, '%s  mesh 12:%d  %d verts / %d tris  size %.1f x %.1f x %.1f units'
               % (os.path.basename(path), s.id, len(allv), sum(len(t) for v, t in geo), *(hi - lo))).save(p)
        print('   ->', p)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
