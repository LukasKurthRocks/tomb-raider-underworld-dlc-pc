"""Collision meshes of a unit DRM (TerrainGroup meshes) with per-face flag statistics against the face slope
(read-only; 2026-11-06 debug render mode, workspace docs\\Befund-Debug-Rendermodus-0611.md).

Layout read from the data (l3_main_hall / l4_trailtube / l2_cliffclimb / l7_thin_ice pcbig, see the finding):
  Level+0 -> Terrain (24 B): +0x08 TerrainGroup count, +0x0c -> TerrainGroups (0x50 B), +0x10 -> one more group.
  TerrainGroup +0x00 vec3 offset, +0x24 index, +0x28 u32 id, +0x30 -> (unit DTP), +0x34 -> Level, +0x38 -> collision
  Mesh header or NULL.
  Mesh header (0x60 B): +0x00 bbox min vec4, +0x10 bbox max vec4 (mesh-local), +0x20 vec4 position (= the group's
  offset), +0x30 -> vertices (16 B: float x, y, z, pad), +0x34 -> faces (20 B, the last record stored without its
  3 trailing pad bytes), +0x38 -> BVH nodes (16 B), +0x3c -> owning TerrainGroup, +0x40 u32 node count, +0x44 u32
  face count, +0x48 u32 vertex count, +0x4c / +0x50 u32 (unknown), +0x54 u16 / u16 (unknown).
  Face (20 B): +0x00 / +0x04 / +0x08 u32 vertex indices, +0x0c u32 FLAGS (bytes b0 b1 b2 b3), +0x10 u8 (unknown).

Modes (from the repository root):
  ../bin/pyt -t 600 tools/collision_faces.py stats UNIT.drm [UNIT.drm ...]
      per unit: meshes, faces; histogram of each flag byte / the +0x10 byte / each FLAGS bit against the slope class
      of the face (floor < 30 deg, 30-45, 45-60, 60-80, wall >= 80, ceiling = normal pointing down)
  ../bin/pyt -t 600 tools/collision_faces.py faces UNIT.drm [--mesh K] [--limit N]
      face rows: mesh, index, slope (deg), normal z, flags hex, +0x10 byte, centre (world = local + position)
  ../bin/pyt -t 600 tools/collision_faces.py bitmap UNIT.drm BITMASK
      faces whose FLAGS & BITMASK != 0: count per slope class and the centres of the first 30
"""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

CLASSES = ['floor<30', '30-45', '45-60', '60-80', 'wall>=80', 'ceiling']


def load(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    rel = []
    for s in D.sections:
        r = R.parse(s.reloc, 'le')
        rel.append((dict(r.internal), {so: (si, do) for si, so, do in r.external}))
    return D, rel


def target(rel, si, o):
    itn, ext = rel[si]
    if o in itn: return si, itn[o]
    if o in ext: return ext[o]
    return None


def meshes(D, rel):
    """[(group index, group id, mesh section, mesh offset, header dict)] of the unit's TerrainGroup collision meshes"""
    t = target(rel, 0, 0)
    if t is None: return []
    ti, to = t
    td = D.sections[ti].data
    ntg = struct.unpack_from('<i', td, to + 8)[0]
    groups = []
    g = target(rel, ti, to + 0xc)
    if g is not None: groups += [(g[0], g[1] + 0x50 * k) for k in range(ntg)]
    g2 = target(rel, ti, to + 0x10)
    if g2 is not None and g2 not in groups: groups.append(g2)
    out = []
    seen = set()
    for gi, (gs, go) in enumerate(groups):
        gd = D.sections[gs].data
        gid = struct.unpack_from('<I', gd, go + 0x28)[0]
        m = target(rel, gs, go + 0x38)
        if m is None or m in seen: continue
        seen.add(m)
        ms, mo = m; md = D.sections[ms].data
        h = dict(pos=struct.unpack_from('<3f', md, mo + 0x20), nn=struct.unpack_from('<I', md, mo + 0x40)[0],
                 nf=struct.unpack_from('<I', md, mo + 0x44)[0], nv=struct.unpack_from('<I', md, mo + 0x48)[0],
                 w4c=struct.unpack_from('<I', md, mo + 0x4c)[0], w50=struct.unpack_from('<I', md, mo + 0x50)[0],
                 w54=struct.unpack_from('<2H', md, mo + 0x54), v=target(rel, ms, mo + 0x30), f=target(rel, ms, mo + 0x34),
                 n=target(rel, ms, mo + 0x38))
        out.append((gi, gid, ms, mo, h))
    return out


def faces(D, h):
    """[(i0, i1, i2, flags, b10, normal, slope_deg, centre_world)]"""
    vs, vo = h['v']; fs, fo = h['f']
    vd = D.sections[vs].data; fd = D.sections[fs].data + b'\0' * 4
    V = [struct.unpack_from('<3f', vd, vo + 16 * k) for k in range(h['nv'])]
    px, py, pz = h['pos']
    out = []
    for k in range(h['nf']):
        o = fo + 20 * k
        i0, i1, i2, fl = struct.unpack_from('<4I', fd, o); b10 = fd[o + 16]
        if max(i0, i1, i2) >= len(V): out.append((i0, i1, i2, fl, b10, None, None, None)); continue
        a, b, c = V[i0], V[i1], V[i2]
        u = [b[j] - a[j] for j in range(3)]; w = [c[j] - a[j] for j in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        ln = math.sqrt(sum(x * x for x in n)) or 1.0
        n = tuple(x / ln for x in n)
        slope = math.degrees(math.acos(max(-1.0, min(1.0, abs(n[2])))))
        cen = tuple((a[j] + b[j] + c[j]) / 3 for j in range(3))
        out.append((i0, i1, i2, fl, b10, n, slope, (cen[0] + px, cen[1] + py, cen[2] + pz)))
    return out


def cls(f):
    n, s = f[5], f[6]
    if n is None: return None
    if n[2] < -0.2: return 'ceiling'      # orientation: sign checked against the floor majority in 'stats'
    if s < 30: return 'floor<30'
    if s < 45: return '30-45'
    if s < 60: return '45-60'
    if s < 80: return '60-80'
    return 'wall>=80'


def cmd_stats(argv):
    for p in argv:
        D, rel = load(p)
        M = meshes(D, rel)
        allf = []
        print('== %s: %d collision meshes' % (os.path.basename(p), len(M)))
        for gi, gid, ms, mo, h in M:
            F = faces(D, h)
            bad = sum(1 for f in F if f[5] is None)
            up = sum(1 for f in F if f[5] is not None and f[5][2] > 0.7); dn = sum(1 for f in F if f[5] is not None and f[5][2] < -0.7)
            print('  group %d id %d mesh [%d]+0x%x: nodes %d faces %d verts %d +0x4c %d +0x50 %d +0x54 %s pos %s; '
                  'bad idx %d; normal z>0.7: %d, <-0.7: %d' % (gi, gid, ms, mo, h['nn'], h['nf'], h['nv'], h['w4c'], h['w50'],
                                                              h['w54'], tuple(round(x, 1) for x in h['pos']), bad, up, dn))
            allf += F
        allf = [f for f in allf if f[5] is not None]
        tot = {c: 0 for c in CLASSES}
        for f in allf: tot[cls(f)] += 1
        print('  slope classes: %s' % '  '.join('%s %d' % (c, tot[c]) for c in CLASSES))
        for name, get in (('b0', lambda f: f[3] & 0xff), ('b1', lambda f: f[3] >> 8 & 0xff), ('b2', lambda f: f[3] >> 16 & 0xff),
                          ('b3', lambda f: f[3] >> 24), ('+0x10', lambda f: f[4])):
            H = {}
            for f in allf:
                H.setdefault(get(f), {c: 0 for c in CLASSES})[cls(f)] += 1
            print('  byte %s: %d values' % (name, len(H)))
            for v in sorted(H, key=lambda v: -sum(H[v].values()))[:24]:
                print('     0x%02x  total %6d   %s' % (v, sum(H[v].values()), '  '.join('%s %d' % (c, H[v][c]) for c in CLASSES)))
        print('  FLAGS bits (count of faces with the bit set, per slope class; share of the class in %):')
        for b in range(32):
            S = {c: 0 for c in CLASSES}
            for f in allf:
                if f[3] >> b & 1: S[cls(f)] += 1
            if sum(S.values()) == 0: continue
            print('     bit %2d (0x%08x) %6d   %s' % (b, 1 << b, sum(S.values()), '  '.join(
                '%s %d (%.0f%%)' % (c, S[c], 100.0 * S[c] / tot[c] if tot[c] else 0) for c in CLASSES)))
    return 0


def cmd_faces(argv):
    mesh = None; limit = 200
    if '--mesh' in argv: k = argv.index('--mesh'); mesh = int(argv[k + 1]); del argv[k:k + 2]
    if '--limit' in argv: k = argv.index('--limit'); limit = int(argv[k + 1]); del argv[k:k + 2]
    D, rel = load(argv[0])
    shown = 0
    for mi, (gi, gid, ms, mo, h) in enumerate(meshes(D, rel)):
        if mesh is not None and mi != mesh: continue
        for k, f in enumerate(faces(D, h)):
            if shown >= limit: return 0
            shown += 1
            if f[5] is None: print('m%d f%d bad indices %s' % (mi, k, f[:3])); continue
            print('m%d f%5d slope %5.1f nz %6.3f flags %08x b10 %02x centre (%.0f %.0f %.0f)' % (
                mi, k, f[6], f[5][2], f[3], f[4], *f[7]))
    return 0


def cmd_bitmap(argv):
    D, rel = load(argv[0]); mask = int(argv[1], 0)
    hit = []
    for mi, (gi, gid, ms, mo, h) in enumerate(meshes(D, rel)):
        hit += [(mi, k, f) for k, f in enumerate(faces(D, h)) if f[5] is not None and f[3] & mask]
    S = {c: 0 for c in CLASSES}
    for _, _, f in hit: S[cls(f)] += 1
    print('%s: %d faces with FLAGS & 0x%x: %s' % (os.path.basename(argv[0]), len(hit), mask,
                                                 '  '.join('%s %d' % (c, S[c]) for c in CLASSES)))
    for mi, k, f in hit[:30]:
        print('  m%d f%d slope %.1f flags %08x b10 %02x centre (%.0f %.0f %.0f)' % (mi, k, f[6], f[3], f[4], *f[7]))
    return 0


def main(argv):
    if not argv: print(__doc__); return 1
    return {'stats': cmd_stats, 'faces': cmd_faces, 'bitmap': cmd_bitmap}[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
