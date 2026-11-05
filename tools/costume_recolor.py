"""Costume slots d / i as colour variants of the bikini family (test 51k, 2026-11-04; plan
docs Plan-Nacht-Analysen-2026-11-03.md section 1). Works on PC DRMs (little endian, CDRM or raw).

  inspect E.drm B.drm
      read-only: object section (type 11, id and +0x14), meshes (type 12: id, texture / material lists), the
      materials and textures of E that B lacks (and vice versa, by id), every relocation id reference to them,
      main-material word diff E vs B
  pairs E.drm B.drm TYPE EID:BID [...]
      read-only: word diff of paired sections (e.g. the costume-own DTPs of E and B); which differing words are
      explained by the id pairs (self ids / references) and which of them are relocation slots
  verify E.drm OUT.drm OLD:NEW[,...] MAT_OFFSETS_HEX[,...]
      read-only, independent of the build code: every difference OUT vs E must be a listed id renumbering (section
      header or data word), a listed main-material offset, the object +0x14 word or an appended DXT1 texture
  texpng DRM TEX[,TEX] OUT_DIR
      read-only: level 0 of the textures as PNG plus mean RGB
  uvcheck E.drm E_TEX B.drm B_TEX [OUT_DIR]
      read-only: are the diffuse textures of E and B laid out on the same UV atlas? Rasterises the UV triangles of
      every mesh batch whose material uses the texture (TEXCOORD0) into a 512 x 512 mask per DRM and compares the
      masks (IoU); optional PNGs of the two masks
  build E.drm OUT.drm --object OLD:NEW --renumber TYPE:OLD:NEW [...] --texture B.drm:SRC_TEX:NEW_TEX:GR,GG,GB
        --retexture MAT:OLD_TEX:NEW_TEX [...] --words MAT:OFF:HEX [...] [--rawids-like B.drm@EID:BID,...]
      writes OUT: type 11 section OLD -> NEW (section id and every type-11 id word equal to OLD in that section);
      every --renumber: the section (TYPE, OLD) gets id NEW and every relocation id reference (kind TYPE) with value
      OLD in the DRM is rewritten; --texture: B's texture SRC_TEX (DXT1) recoloured in the compressed space (both
      565 end points of every block times the channel gains, clamped; when the order of the end points flips, they
      are swapped and the indices remapped, so every block keeps its DXT1 mode and the palette follows exactly) and
      appended as NEW_TEX with B's section header fields; --retexture: in material MAT (after renumbering) every
      texture record id OLD_TEX -> NEW_TEX; --words: raw bytes at OFF of material MAT (e.g. the specular colour taken
      from B); --rawids-like: unrelocated words inside the renumbered DTPs that equal one of the old DTP ids are
      rewritten to the new id - only at offsets where the sister costume B (pairs EID:BID) holds its own paired id,
      i.e. where B and E prove the word is an id field (else the build stops).
      Refuses --object ...:26 / ...:33 and an OUT named dlc_costume_g.drm / dlc_costume_n.drm (slots g / n are left
      out of the port, owner decision E4 2026-11-05) unless --allow-left-out-slot is given.
      Re-reads OUT and lists every changed word per section against E (paired by position).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/costume_recolor.py inspect E.drm B.drm
  ../bin/pyt -t 900 tools/costume_recolor.py uvcheck E.drm 7203 B.drm 7098 OUT_DIR
  ../bin/pyt -t 900 tools/costume_recolor.py build E.drm OUT.drm --object 24:23 --renumber 10:23551:NEW ...
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import drm_write as DW, drm_reloc as R
from mesh_tr8 import Mesh, H

TEXCOORD0 = None   # semantic hash of TEXCOORD0, looked up from mesh_tr8.SEM
LEFT_OUT_OBJECTS = (26, 33)   # dlc_costume_g / dlc_costume_n: left out of the port (owner decision E4, 2026-11-05)


def load(p):
    raw = open(p, 'rb').read()
    return raw, DW.read(raw, 'le')


def sec(D, t, i):
    h = [s for s in D.sections if s.type == t and s.id == i]
    return h[0] if h else None


def idrefs_to(D, t, v):
    """[(section index, offset)] of relocation id references of kind t whose word == v"""
    out = []
    for k, s in enumerate(D.sections):
        if not s.reloc: continue
        r = R.parse(s.reloc, 'le')
        for kk, o in r.idref + getattr(r, 'idref_a', []):
            if kk == t and o + 4 <= len(s.data) and struct.unpack_from('<I', s.data, o)[0] == v: out.append((k, o))
    return out


def tex_records(s):
    ip = dict(R.parse(s.reloc, 'le').internal)
    if 0x54 not in ip: return []
    n = max(s.data[0x4F], s.data[0x52]); out = []
    for k in range(n):
        o = ip[0x54] + 16 * k
        tid, _u1, typ, _b0, slot, _f = struct.unpack_from('<IIIBBH', s.data, o)
        out.append((k, o, tid, typ, slot))
    return out


def inspect(a):
    _, E = load(a[0]); _, B = load(a[1])
    for name, D in (('E', E), ('B', B)):
        for s in D.sections:
            if s.type == 11: print('%s object section id %d, %d bytes, +0x14 = %d' % (name, s.id, len(s.data), struct.unpack_from('<I', s.data, 0x14)[0]))
        for s in D.sections:
            if s.type == 12:
                try:
                    m = Mesh(s.data, 'le'); print('%s mesh %d: %d bytes, textures %s, materials %s' % (name, s.id, len(s.data), m.textures, m.materials))
                except Exception as ex:
                    print('%s mesh %d: %d bytes (%s)' % (name, s.id, len(s.data), ex))
    for t in (5, 10, 12, 7):
        ie = {s.id for s in E.sections if s.type == t}; ib = {s.id for s in B.sections if s.type == t}
        print('type %d: E %d, B %d, only E %s, only B %s' % (t, len(ie), len(ib), sorted(ie - ib)[:20], sorted(ib - ie)[:20]))
        same = sum(1 for i in ie & ib if sec(E, t, i).data == sec(B, t, i).data)
        print('   shared %d, byte-identical %d' % (len(ie & ib), same))
    for s in E.sections:
        if s.type == 11:
            r = R.parse(s.reloc, 'le')
            print('E object %d id references: %s' % (s.id, ', '.join('kind %d +%#x = %d' % (t, o, struct.unpack_from('<I', s.data, o)[0]) for t, o in r.idref)))
    for t, i in [(x.type, x.id) for x in E.sections if x.type in (7, 10, 12) and sec(B, x.type, x.id) is None]:
        refs = idrefs_to(E, t, i)
        print('E %d:%d referenced %d times: %s' % (t, i, len(refs), ', '.join('%d:%d+%#x' % (E.sections[k].type, E.sections[k].id, o) for k, o in refs)))
        if t == 10:
            for k, o, tid, typ, slot in tex_records(sec(E, 10, i)):
                print('   record %d +%#x texture %d type %d s%d' % (k, o, tid, typ, slot))
    oe = [s for s in E.sections if s.type == 10 and sec(B, 10, s.id) is None]
    ob = [s for s in B.sections if s.type == 10 and sec(E, 10, s.id) is None]
    for x in oe:
        for y in ob:
            if len(x.data) != len(y.data): continue
            diff = [o for o in range(0, len(x.data), 4) if x.data[o:o + 4] != y.data[o:o + 4]]
            print('material E %d vs B %d (%d bytes): %d words differ' % (x.id, y.id, len(x.data), len(diff)))
            for o in diff:
                fa, fb = struct.unpack_from('<f', x.data, o)[0], struct.unpack_from('<f', y.data, o)[0]
                print('   +%#05x %s / %s  (%.4g / %.4g)' % (o, x.data[o:o + 4].hex(), y.data[o:o + 4].hex(), fa, fb))


def pairs(a):
    """read-only: E.drm B.drm TYPE EID:BID [...] - word diff of paired sections; per differing word whether it is
    explained by the id pairs (E word == an E id and B word == the paired B id) and whether it is a relocation slot"""
    _, E = load(a[0]); _, B = load(a[1]); t = int(a[2])
    pr = [tuple(map(int, x.split(':'))) for x in a[3:]]
    idmap = dict(pr)
    for eid, bid in pr:
        x, y = sec(E, t, eid), sec(B, t, bid)
        slots = {o for _k, o in R.parse(x.reloc, 'le').idref} if x.reloc else set()
        same_reloc = x.reloc == y.reloc
        if len(x.data) != len(y.data): print('%d:%d vs %d:%d sizes %d / %d' % (t, eid, t, bid, len(x.data), len(y.data))); continue
        diff = [o for o in range(0, len(x.data) - 3, 4) if x.data[o:o + 4] != y.data[o:o + 4]]
        expl = [o for o in diff if idmap.get(struct.unpack_from('<I', x.data, o)[0]) == struct.unpack_from('<I', y.data, o)[0]]
        other = [o for o in diff if o not in expl]
        print('%d:%d vs %d:%d: %d bytes, relocations equal %s, %d words differ, %d explained by the id pairs (%d of them relocation slots), %d other %s' % (
            t, eid, t, bid, len(x.data), same_reloc, len(diff), len(expl), len([o for o in expl if o in slots]), len(other),
            ' '.join('+%#x %08x/%08x' % (o, struct.unpack_from('<I', x.data, o)[0], struct.unpack_from('<I', y.data, o)[0]) for o in other[:8])))


def uv_tris(D, tex):
    """UV triangles (first texture coordinate, TEXCOORD1 in mesh_tr8 naming; short2 = raw integers, float2 as is) of
    every draw group whose material references texture tex -> (array [n, 3, 2], materials, groups)"""
    from mesh_tr8 import SEM
    uvsem = [h for h, n in SEM.items() if n == 'TEXCOORD1']
    mats = {s.id for s in D.sections if s.type == 10 and any(r[2] == tex for r in tex_records(s))}
    tris = []; used = 0
    for s in D.sections:
        if s.type != 12: continue
        m = Mesh(s.data, 'le'); d = s.data
        idx = m.indices() if m.numIndices else ()
        for b in m.meshes:
            vf = b['vf']
            if not vf: continue
            el = {sm: (o, t) for sm, o, t, _ in vf['elems']}
            uv = [h for h in uvsem if h in el]
            if not uv: continue
            uo, ut = el[uv[0]]
            base = H + b['vdataOff']; st = vf['stride']
            for g in m.groups:
                if g['material'] >= len(m.materials) or m.materials[g['material']] not in mats: continue
                if not (b['baseIndex'] <= g['baseIndex'] < b['baseIndex'] + 3 * b['numTris']): continue
                used += 1
                tri = idx[g['baseIndex']:g['baseIndex'] + 3 * g['numTris']]
                for k in range(0, len(tri) - 2, 3):
                    pts = []
                    for vi in tri[k:k + 3]:
                        if ut == 1: u, v = struct.unpack_from('<2f', d, base + vi * st + uo)
                        elif ut == 0x13: u, v = struct.unpack_from('<2h', d, base + vi * st + uo)
                        else: raise SystemExit('texcoord element type %#x not handled' % ut)
                        pts.append((float(u), float(v)))
                    tris.append(pts)
    return np.array(tris, float).reshape(-1, 3, 2), mats, used


def rasterise(tris, lo, hi, size=512):
    mask = np.zeros((size, size), bool)
    sc = (size - 1e-6) / np.maximum(hi - lo, 1e-9)
    for pts in (tris - lo) * sc:
        xs, ys = pts[:, 0], pts[:, 1]
        x0, x1 = max(0, int(xs.min())), min(size - 1, int(xs.max()) + 1)
        y0, y1 = max(0, int(ys.min())), min(size - 1, int(ys.max()) + 1)
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = pts
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        mask[y0:y1 + 1, x0:x1 + 1] |= (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
    return mask


def uvcheck(a):
    _, E = load(a[0]); te = int(a[1]); _, B = load(a[2]); tb = int(a[3]); out = a[4] if len(a) > 4 else None
    tre, mse, ue = uv_tris(E, te); trb, msb, ub = uv_tris(B, tb)
    allp = np.concatenate([tre.reshape(-1, 2), trb.reshape(-1, 2)])
    lo, hi = allp.min(0), allp.max(0)
    print('UV range (raw units, common to both): u %g .. %g, v %g .. %g' % (lo[0], hi[0], lo[1], hi[1]))
    me, mb = rasterise(tre, lo, hi), rasterise(trb, lo, hi)
    inter, union = int((me & mb).sum()), int((me | mb).sum())
    print('E texture %d: materials %s, draw groups %d, covered %d px' % (te, sorted(mse), ue, int(me.sum())))
    print('B texture %d: materials %s, draw groups %d, covered %d px' % (tb, sorted(msb), ub, int(mb.sum())))
    print('IoU %.4f (intersection %d, union %d, only E %d, only B %d)' % (inter / max(1, union), inter, union,
          int((me & ~mb).sum()), int((mb & ~me).sum())))
    if out:
        from PIL import Image
        os.makedirs(out, exist_ok=True)
        img = np.zeros((512, 512, 3), np.uint8); img[..., 0] = me * 255; img[..., 2] = mb * 255
        Image.fromarray(img).save(os.path.join(out, 'uv_E%d_red_B%d_blue.png' % (te, tb)))
        print('written %s' % os.path.join(out, 'uv_E%d_red_B%d_blue.png' % (te, tb)))


def verify(a):
    """read-only: E.drm OUT.drm OLD:NEW[,OLD:NEW...] MAT_OFFSETS(hex,...) - independent of the build path: sections
    paired by position; header ids may change only OLD -> NEW; a changed data word is allowed when old == OLD and
    new == NEW of a listed pair, or when it lies at one of MAT_OFFSETS of the (renumbered) main material; appended
    sections must be PCD9 DXT1 textures. Prints counts per class; 'other' must be 0."""
    raw_e, E = load(a[0]); raw_o, O = load(a[1])
    idp = {}
    for x in a[2].split(','):
        o, n = map(int, x.split(':')); idp.setdefault(o, set()).add(n)
    moff = {int(x, 16) for x in a[3].split(',')}
    print('E %s md5 %s, OUT %s md5 %s' % (os.path.basename(a[0]), hashlib.md5(raw_e).hexdigest(), os.path.basename(a[1]), hashlib.md5(raw_o).hexdigest()))
    n = len(E.sections); cls = collections.Counter(); other = []
    for i in range(n):
        x, y = E.sections[i], O.sections[i]
        if x.type != y.type or x.reloc != y.reloc or len(x.data) != len(y.data) or (x.flags, x.ver, x.spec, x.pad) != (y.flags, y.ver, y.spec, y.pad):
            other.append('section #%d header / reloc / size' % i); continue
        if x.id != y.id:
            if y.id in idp.get(x.id, ()): cls['header id'] += 1
            else: other.append('section #%d id %d -> %d' % (i, x.id, y.id))
        if x.data == y.data: continue
        for o in range(0, len(x.data) - 3, 4):
            wo, wn = x.data[o:o + 4], y.data[o:o + 4]
            if wo == wn: continue
            vo, vn = struct.unpack('<I', wo)[0], struct.unpack('<I', wn)[0]
            if vn in idp.get(vo, ()): cls['id word %d:%d' % (x.type, y.id)] += 1
            elif x.type == 10 and o in moff: cls['material %d +%#x' % (y.id, o)] += 1
            elif x.type == 11 and o == 0x14: cls['object +0x14 %d -> %d' % (vo, vn)] += 1
            else: other.append('%d:%d +%#x %08x -> %08x' % (x.type, x.id, o, vo, vn))
    for s in O.sections[n:]:
        ok = s.type == 5 and s.data[:4] == b'PCD9' and struct.unpack_from('<I', s.data, 4)[0] == 0x31545844
        cls['appended texture %d %s' % (s.id, 'DXT1' if ok else 'NOT DXT1')] += 1
        if not ok: other.append('appended %d:%d' % (s.type, s.id))
    for k in sorted(cls): print('  %-40s %d' % (k, cls[k]))
    print('other changes: %d %s' % (len(other), other[:10]))


def texpng(a):
    """read-only: DRM TEX[,TEX] OUT_DIR - level 0 as PNG and the mean RGB of each texture"""
    import tex_convert as T
    from PIL import Image
    _, D = load(a[0]); out = a[2]; os.makedirs(out, exist_ok=True)
    for t in map(int, a[1].split(',')):
        s = sec(D, 5, t)
        img = np.asarray(T.pc_image(s.data))
        p = os.path.join(out, '%s_%d.png' % (os.path.splitext(os.path.basename(a[0]))[0], t))
        Image.fromarray(img[..., :3].astype(np.uint8)).save(p)
        m = img[..., :3].reshape(-1, 3).mean(0)
        print('texture %d: %dx%d mean RGB %.1f %.1f %.1f -> %s' % (t, img.shape[1], img.shape[0], m[0], m[1], m[2], p))


def c565(c):
    return ((c >> 11) & 31, (c >> 5) & 63, c & 31)


def p565(r, g, b):
    return (r << 11) | (g << 5) | b


def recolor_dxt1(data, gains):
    """recolour a PCD9 DXT1 section payload (24-byte header + levels); returns new bytes and stats"""
    hdr = data[:24]
    fmt = struct.unpack_from('<I', data, 4)[0]
    if fmt != 0x31545844: raise SystemExit('texture is not DXT1 (format %#x)' % fmt)
    out = bytearray(data); n = (len(data) - 24) // 8; flips = equal = 0
    gr, gg, gb = gains
    for k in range(n):
        o = 24 + 8 * k
        c0, c1, ix = struct.unpack_from('<HHI', data, o)
        mode4 = c0 > c1
        def sc(c):
            r, g, b = c565(c)
            return p565(min(31, int(round(r * gr))), min(63, int(round(g * gg))), min(31, int(round(b * gb))))
        n0, n1 = sc(c0), sc(c1)
        if mode4:
            if n0 < n1:                     # order flipped: swap end points, indices 0<->1, 2<->3
                n0, n1 = n1, n0; flips += 1
                ix = sum(([1, 0, 3, 2][(ix >> (2 * p)) & 3]) << (2 * p) for p in range(16))
            elif n0 == n1:                  # 4-colour block collapsed: every palette entry is that colour
                equal += 1; ix = 0
                if n0 == 0: n1 = 0          # c0 = c1 = 0 -> 3-colour mode; index 0 is black, opaque
        else:
            if n0 > n1:                     # 3-colour (punch-through) block: keep c0 <= c1, indices 0<->1
                n0, n1 = n1, n0; flips += 1
                ix = sum(([1, 0, 2, 3][(ix >> (2 * p)) & 3]) << (2 * p) for p in range(16))
        struct.pack_into('<HHI', out, o, n0, n1, ix)
    return bytes(out), n, flips, equal


def build(a):
    inp, outp = a[0], a[1]; opts = a[2:]
    raw, D = load(inp)
    dec = DW.cdrm_decode(raw, 'le')
    if D.write('le') != dec: raise SystemExit('round trip of %s not byte-identical' % inp)
    E0 = DW.read(raw, 'le')
    def take(flag):
        v = []
        while flag in opts:
            k = opts.index(flag); v.append(opts[k + 1]); del opts[k:k + 2]
        return v
    obj = take('--object'); ren = take('--renumber'); tex = take('--texture'); retex = take('--retexture'); words = take('--words')
    like = take('--rawids-like')
    allow = '--allow-left-out-slot' in opts
    if allow: opts.remove('--allow-left-out-slot')
    if opts: raise SystemExit('unknown arguments %s' % opts)
    # owner decision E4 (2026-11-05): slots g (object 26) and n (object 33) are left out of the port - the Xbox data
    # only has "Grey Jungle Shorts" (= o) for both (tools/costume_scope_check.py, docs/COSTUMES.md "Left out")
    bad = [s for s in obj if int(s.split(':')[1]) in LEFT_OUT_OBJECTS]
    if os.path.basename(outp).lower() in ('dlc_costume_g.drm', 'dlc_costume_n.drm'): bad.append(os.path.basename(outp))
    if bad and not allow:
        raise SystemExit('refused: costume slot g / n is left out of the port (E4, %s); --allow-left-out-slot overrides' % bad)
    for spec in obj:
        old, new = map(int, spec.split(':'))
        s = sec(D, 11, old)
        if s is None: raise SystemExit('no object section %d' % old)
        d = bytearray(s.data)
        if struct.unpack_from('<I', d, 0x14)[0] != old: raise SystemExit('object %d: +0x14 is not the object id' % old)
        struct.pack_into('<I', d, 0x14, new)          # the one word the Xbox costumes differ in (20 + slot)
        s.data = bytes(d); s.id = new
        print('object section %d -> %d (section id and +0x14)' % (old, new))
        other = [o for o in range(0, len(d) - 3, 4) if struct.unpack_from('<I', d, o)[0] == old]
        if other: print('   NOTE: object section still has words == %d at %s (not object-id fields, unchanged)' % (old, other))
        refs = idrefs_to(D, 11, old)
        if refs: print('   NOTE: %d type-11 id references to %d elsewhere (not changed): %s' % (len(refs), old, refs))
    for spec in ren:
        t, old, new = map(int, spec.split(':'))
        if sec(D, t, new) is not None: raise SystemExit('%d:%d already in the file' % (t, new))
        s = sec(D, t, old)
        if s is None: raise SystemExit('no section %d:%d' % (t, old))
        refs = idrefs_to(D, t, old)
        s.id = new
        for k, o in refs:
            d = bytearray(D.sections[k].data); struct.pack_into('<I', d, o, new); D.sections[k].data = bytes(d)
            print('reference %d:%d +%#x  %d -> %d' % (D.sections[k].type, D.sections[k].id, o, old, new))
        print('section %d:%d -> %d, %d references rewritten' % (t, old, new, len(refs)))
    for spec in like:
        # raw (unrelocated) id words inside the renumbered DTPs, rewritten ONLY where the sister costume B proves the
        # word is an id field: B's paired section has the paired B id at the same offset (b vs e differ exactly there)
        bpath, rest = spec.split('@') if '@' in spec else (None, None)
        if bpath is None: raise SystemExit('--rawids-like B.drm@EID:BID,EID:BID,...')
        _, BB = load(bpath)
        prs = [tuple(map(int, x.split(':'))) for x in rest.split(',')]
        newid = {old: new for t, old, new in (map(int, r.split(':')) for r in ren) if t == 7}
        e2b = dict(prs); total = 0
        for eid, bid in prs:
            if eid not in newid: raise SystemExit('%d is not renumbered' % eid)
            s = sec(D, 7, newid[eid]); y = sec(BB, 7, bid)
            slots = {o for _k, o in R.parse(s.reloc, 'le').idref} if s.reloc else set()
            d = bytearray(s.data); hits = []
            for o in range(0, len(d) - 3, 4):
                if o in slots: continue
                w = struct.unpack_from('<I', d, o)[0]
                if w in e2b:
                    if y is None or len(y.data) != len(d) or struct.unpack_from('<I', y.data, o)[0] != e2b[w]:
                        raise SystemExit('7:%d +%#x == %d but %s does not prove an id field there' % (eid, o, w, os.path.basename(bpath)))
                    struct.pack_into('<I', d, o, newid[w]); hits.append(o)
            s.data = bytes(d); total += len(hits)
            print('raw id words in 7:%d (now %d): %d rewritten (B 7:%d has its own ids there) %s' % (
                eid, newid[eid], len(hits), bid, ' '.join('+%#x' % o for o in hits[:20])))
        print('raw id words rewritten: %d' % total)
    for spec in tex:
        src, st, nt, g = spec.rsplit(':', 3)          # the path may hold a drive colon
        st, nt = int(st), int(nt); gains = tuple(float(x) for x in g.split(','))
        if sec(D, 5, nt) is not None: raise SystemExit('texture %d already in the file' % nt)
        _, S = load(src); s = sec(S, 5, st)
        if s is None: raise SystemExit('texture %d not in %s' % (st, src))
        data, n, flips, equal = recolor_dxt1(s.data, gains)
        D.sections.append(DW.Section(5, nt, data, s.reloc, s.flags, s.ver, s.spec, s.pad))
        w, h, mips = struct.unpack_from('<HHxB', s.data, 0x10)
        print('texture %d (%s, %dx%d mips %d, %d blocks) recoloured x %s -> %d: %d blocks swapped, %d collapsed; md5 %s' % (
            st, os.path.basename(src), w, h, mips, n, g, nt, flips, equal, hashlib.md5(data).hexdigest()))
    for spec in retex:
        mid, ot, nt = map(int, spec.split(':'))
        s = sec(D, 10, mid); d = bytearray(s.data); n = 0
        for k, o, tid, typ, slot in tex_records(s):
            if tid == ot: struct.pack_into('<I', d, o, nt); n += 1; print('material %d record %d (s%d type %d) texture %d -> %d' % (mid, k, slot, typ, ot, nt))
        if not n: raise SystemExit('material %d has no record with texture %d' % (mid, ot))
        s.data = bytes(d)
    for spec in words:
        mid, off, hx = spec.split(':'); mid, off = int(mid), int(off, 16); b = bytes.fromhex(hx)
        s = sec(D, 10, mid); d = bytearray(s.data)
        print('material %d +%#x: %s -> %s' % (mid, off, d[off:off + len(b)].hex(), hx)); d[off:off + len(b)] = b; s.data = bytes(d)
    o = D.write('le')
    data = DW.cdrm_encode(o, 'le') if raw[:4] == b'CDRM' else o
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True); open(outp, 'wb').write(data)
    B2 = DW.read(open(outp, 'rb').read(), 'le')
    n0 = len(E0.sections); tot = 0
    if len(B2.sections) != n0 + len(tex): raise SystemExit('readback: %d sections' % len(B2.sections))
    for i in range(n0):
        x, y = E0.sections[i], B2.sections[i]
        if (x.type, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) != (y.type, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)):
            raise SystemExit('readback: section #%d header / reloc / size changed' % i)
        if x.id != y.id: print('readback: section #%d %d:%d -> id %d' % (i, x.type, x.id, y.id))
        if x.data != y.data:
            ws = [o for o in range(0, len(x.data), 4) if x.data[o:o + 4] != y.data[o:o + 4]]
            tot += len(ws)
            print('readback: section #%d %d:%d -> %d: %d words differ (%s)' % (i, x.type, x.id, y.id, len(ws), ' '.join('+%#x' % w for w in ws[:12])))
    # raw (non-relocated) words still equal to a renumbered old id - would be an unrelocated reference
    for spec in ren:
        t, old, new = map(int, spec.split(':'))
        slots = {}
        for k, s in enumerate(B2.sections):
            if s.reloc:
                r = R.parse(s.reloc, 'le'); slots[k] = {o for _kk, o in r.idref + getattr(r, 'idref_a', [])}
        raw_hits = [(B2.sections[k].type, B2.sections[k].id, o) for k, s in enumerate(B2.sections) if s.type in (7, 10, 11, 12)
                    for o in range(0, len(s.data) - 3, 4)
                    if struct.unpack_from('<I', s.data, o)[0] == old and o not in slots.get(k, ())]
        left = idrefs_to(B2, t, old)
        print('renumber %d:%d -> %d: relocated references left %d, raw words == %d in DTP / material / object / mesh sections %d %s' % (
            t, old, new, len(left), old, len(raw_hits), raw_hits[:6]))
    print('readback ok: %d sections + %d new, %d words changed in total' % (n0, len(tex), tot))
    print('%s  %d bytes  md5 %s' % (outp, len(data), hashlib.md5(data).hexdigest()))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    {'inspect': inspect, 'pairs': pairs, 'uvcheck': uvcheck, 'build': build, 'texpng': texpng,
     'verify': verify}[sys.argv[1]](sys.argv[2:])
