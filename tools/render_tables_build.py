"""Rebuild the three work/render/ tables that no upstream tool writes (docs/WINDOWS_REBUILD.md finding 28).

  pairnames.json     list of base DRM names present on PC and Xbox, without platform prefix (e.g. 'alister.drm')
                     = generic_cache.names() (the same list that keys work/generic/pairs.pkl)
  material_x2p.pkl   {xbox material id: pc material id} = idmap.json type 10 (generic_ids.py, positional pairing)
  shader_x2p.pkl     {xbox shader lib id: pc shader lib id} = idmap.json type 9

These are reconstructions: the author's files are not public. Check them with `check` before relying on them.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/render_tables_build.py build
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/render_tables_build.py check
      needs work/render/pairs_render.pkl (tools/rend_extract.py pairs). Reports, per base pair:
      - material pairs: type-10 sections zipped by position (as material_rules.py does) where mx2p[x.id] == p.id
      - shader tuples: for those material pairs, the 4 shader ids of the Xbox tuple (material +0x28, BE u32) mapped
        with shader_x2p against the PC tuple (+0x28, LE u32): equal, equal as a set (PC re-slots), different
"""
import sys, os, json, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
GEN = os.path.join(ROOT, 'work', 'generic')
OUT = os.path.join(ROOT, 'work', 'render')


def build():
    import generic_cache
    os.makedirs(OUT, exist_ok=True)
    names = generic_cache.names()
    json.dump(names, open(os.path.join(OUT, 'pairnames.json'), 'w'))
    idm = json.load(open(os.path.join(GEN, 'idmap.json')))
    mx2p = {int(a): b for a, b in idm['10'].items()}
    sx2p = {int(a): b for a, b in idm['9'].items()}
    pickle.dump(mx2p, open(os.path.join(OUT, 'material_x2p.pkl'), 'wb'))
    pickle.dump(sx2p, open(os.path.join(OUT, 'shader_x2p.pkl'), 'wb'))
    print('pairnames %d, material_x2p %d, shader_x2p %d -> %s' % (len(names), len(mx2p), len(sx2p), os.path.abspath(OUT)))
    print('injective: materials %s, shaders %s' % (len(set(mx2p.values())) == len(mx2p), len(set(sx2p.values())) == len(sx2p)))


def check():
    mx2p = pickle.load(open(os.path.join(OUT, 'material_x2p.pkl'), 'rb'))
    sx2p = pickle.load(open(os.path.join(OUT, 'shader_x2p.pkl'), 'rb'))
    pairs = pickle.load(open(os.path.join(OUT, 'pairs_render.pkl'), 'rb'))
    st = collections.Counter(); unmapped = collections.Counter()
    for nm, X, P in pairs:
        if X is None or not isinstance(P, list): st['pair_failed'] += 1; continue
        xm = [s for s in X if s['type'] == 10]; pm = [s for s in P if s['type'] == 10]
        st['xbox_materials'] += len(xm)
        if len(xm) != len(pm): st['material_count_differs'] += 1
        for a, b in zip(xm, pm):
            if mx2p.get(a['id']) != b['id']: st['zip_id_mismatch'] += 1; continue
            st['material_pairs_ok'] += 1
            if len(a['data']) < 0x38 or len(b['data']) < 0x38: st['short_material'] += 1; continue
            xr = struct.unpack_from('>4I', a['data'], 0x28)
            # empty slots (0 / 0xffffffff) stay as they are
            xt = [v if v in (0, 0xffffffff) else sx2p.get(v, None) for v in xr]
            pt = list(struct.unpack_from('<4I', b['data'], 0x28))
            st['slots_empty'] += sum(1 for v in xr if v in (0, 0xffffffff))
            if None in xt:
                st['tuple_unmapped_shader'] += 1
                for v, w in zip(xr, xt):
                    if w is None: unmapped[v] += 1
            elif xt == pt: st['tuple_equal'] += 1
            elif sorted(xt) == sorted(pt): st['tuple_equal_as_set'] += 1
            else: st['tuple_different'] += 1
    for k in sorted(st): print('  %-26s %d' % (k, st[k]))
    print('  unmapped Xbox shader ids: %d distinct, top: %s' % (len(unmapped), unmapped.most_common(8)))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'build': build()
    elif cmd == 'check': check()
    else: sys.exit(__doc__)
