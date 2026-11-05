"""Materials of a unit DRM with their shader libs, where they are drawn, and whether they are a known surrogate
(test questions 2026-11-05: light beams in dlc_yggdrasil_end), read-only.

Per material (type 10): ShaderLib ids of pass 0 / 1 / 2 and VS (+0x28..+0x34, '-' = no id reference = slot empty),
terrain draws (count, index total, overall bounding box; tools/terrain_material_bbox logic), the mesh sections that
reference the material, and flags:
  SURR9   one of the 9 materials still on surrogate libs after test 50o (docs/Befund-Shader-Nacht.md part 5)
  REF!=   the reference tree's copy of the same file uses other libs (e.g. 50o translation not installed)
  Xbox    with --xbox NAME: the Xbox material's libs, each with its class from work/render/dlc_shader_map.json
          (A / B = byte-identical base lib, C1-C3 / D = surrogate chosen by similarity) and the PC id it maps to
Optional --ids restricts the list; --ref DRM names the reference copy (default none).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/unit_beam_materials.py UNIT.drm [--ref REF_UNIT.drm] [--ids ID,ID] [--xbox NAME.drm]
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, terrain_convert as TC

SURR9 = {26623, 26780, 26831, 25264, 25334, 20262, 24275, 20344, 21093}


def mats(D):
    out = {}
    for s in D.sections:
        if s.type != 10: continue
        r = R.parse(s.reloc, 'le'); refs = set(r.idref)
        sl = []
        for k in range(4):
            o = 0x28 + 4 * k
            v = struct.unpack_from('<I', s.data, o)[0] if o + 4 <= len(s.data) else None
            sl.append(v if (9, o) in refs else None)
        out.setdefault(s.id, tuple(sl))
    return out


def terrain_use(D):
    use = {}
    for s in D.sections:
        if s.type != 12 or not TC.is_terrain(s.data): continue
        d = s.data; e = '<'
        try:
            T = TC.parse(d, e); H = T['H']
            ptr = dict(R.parse(s.reloc, 'le').internal)
            ml = ptr[0x0C]; n = struct.unpack_from('<I', d, ml)[0]
            ml_ids = list(struct.unpack_from('<%dI' % n, d, ml + 4))
            idx = np.frombuffer(d, dtype='<u2', count=T['nIdx'], offset=H + T['offIdx'])
            for slot, seq, lst in TC.draw_lists(d, T, e):
                for yi, cnt, start in lst:
                    y = T['Y'][yi]
                    if y[0] >= len(ml_ids): continue
                    m = ml_ids[y[0]]
                    vdo, _, nv, vfi = T['vbs'][y[1]]; vf = T['vfs'][vfi]
                    pos = [o for s2, o, t, _ in vf['elems'] if t == 2]
                    u = use.setdefault(m, [0, 0, None, None])
                    u[0] += 1; u[1] += cnt
                    if not pos: continue
                    ii = idx[start:start + cnt].astype(np.int64); ii = np.unique(ii[ii < nv])
                    P = np.array([struct.unpack_from('<3f', d, H + vdo + k * vf['stride'] + pos[0]) for k in ii])
                    if len(P):
                        lo, hi = P.min(0), P.max(0)
                        u[2] = lo if u[2] is None else np.minimum(u[2], lo)
                        u[3] = hi if u[3] is None else np.maximum(u[3], hi)
        except Exception as ex:
            print('  terrain section %d: %s' % (s.id, ex))
    return use


def mesh_use(D):
    use = {}
    for s in D.sections:
        if s.type != 12 or TC.is_terrain(s.data): continue
        for t, o in R.parse(s.reloc, 'le').idref:
            if t == 10 and o + 4 <= len(s.data):
                use.setdefault(struct.unpack_from('<I', s.data, o)[0], set()).add(s.id)
    return use


def xbox_mats(name):
    """Xbox material slots (big endian, same +0x28..+0x34 layout) of the DLC unit NAME (convert_dlc.raw_dlc)"""
    os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
    from convert_dlc import raw_dlc
    from drm import cdrm_decode, sections_with_data
    raw, _ = raw_dlc(name)
    if raw is None: return {}
    out = {}
    for s in sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]:
        if s['type'] != 10: continue
        refs = set(R.parse(s['reloc'], 'be').idref)
        sl = []
        for k in range(4):
            o = 0x28 + 4 * k
            v = struct.unpack_from('>I', s['data'], o)[0] if o + 4 <= len(s['data']) else None
            sl.append(v if (9, o) in refs else None)
        out.setdefault(s['id'], tuple(sl))
    return out


def shader_classes():
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'render', 'dlc_shader_map.json')
    return json.load(open(p)) if os.path.exists(p) else {}


def main(argv):
    ref = None; ids = None; xname = None
    if '--ref' in argv: k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    if '--xbox' in argv: k = argv.index('--xbox'); xname = argv[k + 1]; del argv[k:k + 2]
    XM = xbox_mats(xname) if xname else {}
    SC = shader_classes() if xname else {}
    if '--ids' in argv: k = argv.index('--ids'); ids = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    M = mats(D); TU = terrain_use(D); MU = mesh_use(D)
    RM = mats(DW.read(open(ref, 'rb').read(), 'le')) if ref else {}
    f = lambda v: '-' if v is None else str(v)
    print('%s: %d materials%s' % (os.path.basename(argv[0]), len(M), (' (reference %s)' % ref) if ref else ''))
    for m, sl in M.items():
        if ids and m not in ids: continue
        u = TU.get(m)
        where = []
        if u:
            where.append('terrain %d draws / %d idx' % (u[0], u[1]))
            if u[2] is not None:
                where.append('bbox (%.0f %.0f %.0f)-(%.0f %.0f %.0f) size (%.0f %.0f %.0f)' % (
                    *u[2], *u[3], *(u[3] - u[2])))
        if m in MU: where.append('meshes %s' % sorted(MU[m]))
        fl = []
        if m in SURR9: fl.append('SURR9')
        if ref and m in RM and RM[m] != sl: fl.append('REF!= %s' % '/'.join(map(f, RM[m])))
        if xname:
            xs = XM.get(m)
            if xs is None: fl.append('no Xbox material')
            else:
                cl = []
                for v in xs:
                    if v is None: cl.append('-'); continue
                    e = SC.get(str(v))
                    cl.append('%d:%s->%s' % (v, e['cls'], e['pc']) if e else '%d:?' % v)
                fl.append('Xbox ' + ' '.join(cl))
        print('  mat %6d  ps0 %5s ps1 %5s ps2 %5s vs %5s  %s  %s' % (m, *map(f, sl), '; '.join(where) or 'not drawn by this unit',
                                                                  ' '.join(fl)))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
