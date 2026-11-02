"""Shader inventory of the DLC materials: which materials use a title-update / DLC shader library that the PC build only
replaces by a base-game surrogate (classes C1 / C2 / C3 / D of tools/shader_map.py), in which installed DRM they are,
and a visibility group per DRM (read-only; 2026-11-02, missing list docs/Fehlliste-2026-11-02.md).

Inputs (all produced earlier, local): work/render/shaderlibs.pkl (L['DM'] = DLC Xbox materials {id: (data, reloc)}),
work/render/dlc_shader_map.json (Xbox lib id -> class / PC id / surrogate), and the installed mods folder (type-10
section ids per DRM). A material's Xbox shader tuple = four big-endian u32 at +0x28 (tools/material_convert.py
shader_key). Visibility group by DRM name: player (lara / doppelganger / co_dlc_lara / costume), enemy (thrall / yeti /
viking / knight), effect (fx), weapon / pickup (wp_ / pr_ / health), level / object (everything else).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/shader_inventory.py MODS_DIR [--libs] [--top N]
  --libs  also list every C / D library with its material and DRM counts
"""
import sys, os, pickle, struct, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'render')
UNTRANSLATED = ('C1', 'C2', 'C3', 'D')


def group(name):
    n = name.lower()
    if any(k in n for k in ('lara', 'doppelganger', 'costume')): return 'player'
    if any(k in n for k in ('thrall', 'yeti', 'viking', 'knight')): return 'enemy'
    if n.startswith(('fx', 'dlc_fx', 'dlc1_fx', 'dlc2_fx')) or '_fx_' in n: return 'effect'
    if n.startswith(('wp_', 'pr_')) or 'health' in n: return 'weapon / pickup'
    return 'level / object'


def main(argv):
    libs = '--libs' in argv; argv = [a for a in argv if a != '--libs']
    top = 40
    if '--top' in argv: k = argv.index('--top'); top = int(argv[k + 1]); del argv[k:k + 2]
    L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
    DM = L['DM']
    smap = {int(k): v for k, v in json.load(open(os.path.join(W, 'dlc_shader_map.json'))).items()}
    cls_count = collections.Counter(v['cls'] for v in smap.values())
    print('shader map: %d DLC libs, classes %s; untranslated (C1-C3, D): %d' % (
        len(smap), dict(sorted(cls_count.items())), sum(cls_count[c] for c in UNTRANSLATED)))
    mat_libs = {}
    for mid, (d, r) in DM.items():
        t = struct.unpack_from('>4I', d, 0x28)
        bad = sorted({s for s in t if s and smap.get(s, {}).get('cls') in UNTRANSLATED})
        mat_libs[mid] = bad
    nbad = sum(1 for v in mat_libs.values() if v)
    print('DLC Xbox materials: %d, with at least one untranslated library: %d' % (len(mat_libs), nbad))
    where = collections.defaultdict(list)          # material id -> [drm]
    mods = argv[0]
    for f in sorted(os.listdir(mods)):
        if not f.endswith('.drm'): continue
        try:
            D = DW.read(open(os.path.join(mods, f), 'rb').read(), 'le')
        except Exception as ex:
            print('  %s: not readable (%s)' % (f, ex)); continue
        for s in D.sections:
            if s.type == 10 and s.id in mat_libs: where[s.id].append(f)
    found = sum(1 for m in mat_libs if where.get(m))
    print('materials found by id in the installed mods: %d of %d' % (found, len(mat_libs)))
    per_drm = collections.defaultdict(lambda: [0, 0, set()])
    for m, fs in where.items():
        for f in fs:
            per_drm[f][0] += 1
            if mat_libs[m]:
                per_drm[f][1] += 1
                per_drm[f][2].update(mat_libs[m])
    per_group = collections.defaultdict(lambda: [0, 0, 0])
    for f, (n, b, ls) in per_drm.items():
        g = per_group[group(f)]
        g[0] += 1; g[1] += n; g[2] += b
    print('by visibility group: DRMs / materials / materials with untranslated libs')
    for g, (a, b, c) in sorted(per_group.items()):
        print('  %-16s %4d %5d %5d' % (g, a, b, c))
    print('DRMs with untranslated materials (most first, top %d):' % top)
    rows = sorted(((b, f, n, ls) for f, (n, b, ls) in per_drm.items() if b), reverse=True)
    print('  %d DRMs' % len(rows))
    for b, f, n, ls in rows[:top]:
        print('  %-48s %-16s %3d of %3d materials, libs %s' % (f, group(f), b, n, ' '.join(str(x) for x in sorted(ls))))
    if libs:
        lc = collections.defaultdict(lambda: [0, set()])
        for m, ls in mat_libs.items():
            for x in ls:
                lc[x][0] += 1
                lc[x][1].update(where.get(m, ()))
        print('untranslated libraries: id class surrogate materials DRMs')
        for x in sorted(lc):
            print('  %6d %-3s %6s %3d %3d %s' % (x, smap[x]['cls'], smap[x].get('surrogate'), lc[x][0], len(lc[x][1]),
                                                ' '.join(sorted(lc[x][1]))[:160]))


if __name__ == '__main__':
    main(sys.argv[1:])
