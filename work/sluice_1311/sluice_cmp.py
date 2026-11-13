"""sluice_1311: section-by-section comparison of one DLC DRM: our tree vs the old played tree vs a kit vs the Xbox
source (pack record). Read-only. Textures: PC header (format, size, mips, flags), md5 per side, level 0 decoded and
compared against the Xbox section converted with tools/tex_convert (PSNR, like the Q24 / tex_validate check).
Mesh: md5 per side, group -> material table. Materials / shader libs: md5 per side, differing words own vs old.

usage (from trudlcport): ../bin/pyt -t 900 work/sluice_1311/sluice_cmp.py NAME.drm OWN.drm OLD.drm [KIT.drm]
"""
import sys, os, hashlib, math, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm, tex_convert as T, convert_dlc as CD
from mesh_tr8 import Mesh


def secs(raw, e):
    return drm.sections_with_data(drm.cdrm_decode(raw, e), e)[1]


def md5(b): return hashlib.md5(bytes(b)).hexdigest()[:8]


def psnr(a, b):
    if a.shape != b.shape: return None
    m = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if m == 0 else 10 * math.log10(255 * 255 / m)


def img(d):
    return np.asarray(T.pc_image(bytes(d)), dtype=np.uint8)


def main(a):
    name, own, old = a[0], a[1], a[2]
    kit = a[3] if len(a) > 3 else None
    sides = [('own', secs(open(own, 'rb').read(), 'le')), ('old', secs(open(old, 'rb').read(), 'le'))]
    if kit: sides.append(('kit', secs(open(kit, 'rb').read(), 'le')))
    os.environ['TRUDLC_PACK_FIRST'] = 'pack10'
    xr, src = CD.raw_dlc(name)
    X = secs(xr, 'be') if xr is not None else []
    print('xbox source %s: %d sections; own %d, old %d%s' % (src, len(X), len(sides[0][1]), len(sides[1][1]),
                                                              (', kit %d' % len(sides[2][1])) if kit else ''))
    key = lambda L: {(s['type'], s['id']): s for s in L}
    K = {n: key(L) for n, L in sides}
    # Xbox type-5 sections, converted once
    xt = []
    for i, s in enumerate(X):
        if s['type'] != 5: continue
        try:
            h = T.parse_xbox(bytes(s['data']))
            c = T.convert(bytes(s['data']))
            xt.append((i, s['id'], h, img(c), c))
        except Exception as ex:
            xt.append((i, s['id'], None, None, str(ex)))
    print('\n== textures (type 5): own header | md5 own/old/kit | best Xbox match (PSNR level 0) | Xbox header')
    used = set()
    for s in sides[0][1]:
        if s['type'] != 5: continue
        d = bytes(s['data']); h = T.parse_pc(d)
        try: kind = T.pc_kind(h['fmt'])
        except KeyError: kind = hex(h['fmt'])
        m = [md5(K[n][(5, s['id'])]['data']) if (5, s['id']) in K[n] else '-' for n, _ in sides]
        same = 'all equal' if len(set(m)) == 1 else 'DIFF ' + '/'.join(m)
        try: io = img(d)
        except Exception as ex: io = None; print('  %d decode error %s' % (s['id'], ex))
        best = None
        for (i, xid, xh, xi, c) in xt:
            if xi is None or io is None or xi.shape != io.shape: continue
            p = psnr(io, xi)
            if best is None or p > best[0]: best = (p, i, xid, xh, c == d)
        if best:
            used.add(best[1]); xh = best[3]
            xs = '%s %dx%d mips %d flags 0x%x tiled %s' % (xh['fmtname'], xh['w'], xh['h'], xh['mips'], xh['flags'], xh['tiled'])
            print('  %5d %s %4dx%-4d mips %2d flags 0x%04x size %7d | %s | xbox sec %d id %d PSNR %.1f%s | %s'
                  % (s['id'], kind, h['w'], h['h'], h['mips'], h['flags'], len(d), same, best[1], best[2], best[0],
                     ' (bytes = converter)' if best[4] else '', xs))
        else:
            print('  %5d %s %4dx%-4d mips %2d flags 0x%04x size %7d | %s | no Xbox texture of that size'
                  % (s['id'], kind, h['w'], h['h'], h['mips'], h['flags'], len(d), same))
    for (i, xid, xh, xi, c) in xt:
        if xi is None: print('  xbox sec %d id %d: not converted (%s)' % (i, xid, c))
    print('\n== meshes (type 12)')
    for s in sides[0][1]:
        if s['type'] != 12: continue
        m = [md5(K[n][(12, s['id'])]['data']) if (12, s['id']) in K[n] else '-' for n, _ in sides]
        print('  %d md5 %s' % (s['id'], '/'.join(m)))
        try:
            M = Mesh(bytes(s['data']), 'le')
            print('    materials %s textures %s' % (M.materials, M.textures))
            for g in M.groups:
                print('    group tris %5d verts %5d drawGroup %d material idx %d -> %s'
                      % (g['numTris'], g['numVerts'], g['drawGroup'], g['material'],
                         M.materials[g['material']] if 0 <= g['material'] < len(M.materials) else '?'))
        except Exception as ex:
            print('    not a Mesh: %s' % ex)
    for x in X:
        if x['type'] == 12:
            try:
                M = Mesh(bytes(x['data']), 'be')
                print('  xbox mesh id %d: materials %s, groups %s' % (x['id'], M.materials,
                      [(g['numTris'], g['material']) for g in M.groups]))
            except Exception as ex:
                pass
    print('\n== materials (10) / shader libs (9): md5 own/old/kit, words own vs old')
    allk = []
    for n, L in sides:
        for s in L:
            k = (s['type'], s['id'])
            if s['type'] in (9, 10) and k not in allk: allk.append(k)
    for k in allk:
        m = [md5(K[n][k]['data']) + ':%d' % len(K[n][k]['data']) if k in K[n] else '-' for n, _ in sides]
        line = '  %d:%-6d %s' % (k[0], k[1], ' / '.join(m))
        if k in K['own'] and k in K['old'] and K['own'][k]['data'] != K['old'][k]['data'] and k[0] == 10:
            a_, b_ = bytes(K['own'][k]['data']), bytes(K['old'][k]['data'])
            diffs = ['+0x%x %s|%s' % (o, a_[o:o + 4].hex(), b_[o:o + 4].hex())
                     for o in range(0, min(len(a_), len(b_)) - 3, 4) if a_[o:o + 4] != b_[o:o + 4]]
            line += '  words own|old: ' + ' '.join(diffs)
        print(line)


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
