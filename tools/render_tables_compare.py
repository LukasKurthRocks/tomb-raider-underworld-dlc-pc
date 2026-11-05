"""Read-only proofs for rebuilding the work/render DLC tables with more DLC packs (costume packs, 2026-11-03).

Adding packs to the DLC index (work/idx_dlc.json) and re-running rend_extract dlc / shader_map / material_dlc /
pc_shader_sections must not change anything DLC 1 / DLC 2 already use: every old entry must stay byte-identical,
only new keys may appear. This tool checks that, and compares two output trees file by file.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/render_tables_compare.py index OLD_IDX.json NEW_IDX.json
      old index = prefix of the new one (same records in the same order); per pack file: records added
  ../bin/pyt -t 1800 tools/render_tables_compare.py tables OLD_RENDER_DIR NEW_RENDER_DIR
      dlc_render.pkl (old list = prefix of the new), shaderlibs.pkl (X, P, XM, PM equal; D, DM: old keys equal),
      dlc_shader_map.json, dlc_material_shaders.json, dlc_materials_pc.pkl, pc_shader_sections.pkl (old keys equal),
      plus: section ids of the new records that an older record already had with OTHER bytes (types 9 / 10;
      first record wins in shader_map.load_libs, so such a new record would be converted with the old bytes)
  ../bin/pyt -t 1800 tools/render_tables_compare.py tree DIR_A DIR_B
      every file below both folders: sha256 equal / different / only in A / only in B (exit 1 if not identical)
"""
import sys, os, json, pickle, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _pack(path):
    return os.path.basename(path)


def cmd_index(old_p, new_p):
    old = json.load(open(old_p)); new = json.load(open(new_p))
    prefix = new[:len(old)] == old
    print('old records %d, new records %d, old = prefix of new: %s' % (len(old), len(new), prefix))
    c = collections.Counter(_pack(r[0]) for r in new[len(old):])
    e = collections.Counter(_pack(r[0]) for r in new[len(old):] if isinstance(r[5], str))
    d = collections.Counter(_pack(r[0]) for r in new if isinstance(r[5], list))
    for k in sorted(c): print('  added %-12s %4d records, %d read errors' % (k, c[k], e[k]))
    for k in sorted(d): print('  DRM records (with a section list) %-12s %4d' % (k, d[k]))
    return 0 if prefix else 1


def _eq_keys(name, old, new):
    """old keys whose value differs or that are missing in new; number of added keys"""
    changed = [k for k in old if k not in new or new[k] != old[k]]
    added = [k for k in new if k not in old]
    print('  %-34s old %6d  new %6d  old keys changed/missing %d %s  added %d' % (
        name, len(old), len(new), len(changed), sorted(changed)[:10], len(added)))
    return changed, added


def cmd_tables(od, nd):
    bad = 0
    # dlc_render.pkl: list of (path, record index, hash, sections)
    O = pickle.load(open(os.path.join(od, 'dlc_render.pkl'), 'rb')); N = pickle.load(open(os.path.join(nd, 'dlc_render.pkl'), 'rb'))
    pre = N[:len(O)] == O
    print('dlc_render.pkl: old %d DRM records, new %d, old = prefix of new: %s' % (len(O), len(N), pre))
    bad += not pre
    # ids of types 9 / 10 that new records carry with bytes different from the first (old) record
    first = {}
    for path, i, h, secs in O:
        for s in secs or []:
            if s['type'] in (9, 10): first.setdefault((s['type'], s['id']), (s['data'], s['reloc']))
    coll = collections.Counter(); same = collections.Counter(); fresh = collections.Counter(); ex = collections.defaultdict(set)
    for path, i, h, secs in N[len(O):]:
        for s in secs or []:
            if s['type'] not in (9, 10): continue
            k = (s['type'], s['id'])
            # first record wins also among the new packs (pack1 before pack2 before pack20)
            if k not in first: fresh[(s['type'], _pack(path))] += 1; first[k] = (s['data'], s['reloc']); continue
            if first[k] == (s['data'], s['reloc']): same[(s['type'], _pack(path))] += 1
            else: coll[(s['type'], _pack(path))] += 1; ex[(s['type'], _pack(path))].add(s['id'])
    for k in sorted(set(coll) | set(same) | set(fresh)):
        print('  new records type %d %-11s sections: id first seen %4d, id seen before + same bytes %4d, + OTHER bytes %4d %s' % (
            k[0], k[1], fresh[k], same[k], coll[k], sorted(ex[k])[:8]))
    del O, N
    # shaderlibs.pkl
    LO = pickle.load(open(os.path.join(od, 'shaderlibs.pkl'), 'rb')); LN = pickle.load(open(os.path.join(nd, 'shaderlibs.pkl'), 'rb'))
    print('shaderlibs.pkl:')
    for key in ('X', 'P', 'XM', 'PM'):
        eq = LO[key] == LN[key]
        print('  %-34s equal: %s (%d entries)' % (key, eq, len(LO[key])))
        bad += not eq
    for key in ('D', 'DM'):
        ch, ad = _eq_keys(key, LO[key], LN[key]); bad += bool(ch)
    del LO, LN
    for fn in ('dlc_shader_map.json', 'dlc_material_shaders.json'):
        ch, ad = _eq_keys(fn, json.load(open(os.path.join(od, fn))), json.load(open(os.path.join(nd, fn)))); bad += bool(ch)
    for fn in ('dlc_materials_pc.pkl', 'pc_shader_sections.pkl'):
        ch, ad = _eq_keys(fn, pickle.load(open(os.path.join(od, fn), 'rb')), pickle.load(open(os.path.join(nd, fn), 'rb'))); bad += bool(ch)
    print('RESULT: %s' % ('old entries all unchanged' if not bad else '%d table(s) with changed old entries' % bad))
    return 1 if bad else 0


def _files(d):
    out = {}
    for root, _ds, fs in os.walk(d):
        for n in fs:
            p = os.path.join(root, n)
            out[os.path.relpath(p, d).replace('\\', '/')] = p
    return out


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def cmd_tree(a, b):
    A = _files(a); B = _files(b)
    eq, diff = [], []
    for k in sorted(set(A) & set(B)):
        (eq if _sha(A[k]) == _sha(B[k]) else diff).append(k)
    oa = sorted(set(A) - set(B)); ob = sorted(set(B) - set(A))
    drm = lambda l: sum(1 for k in l if k.lower().endswith('.drm'))
    print('A %s: %d files; B %s: %d files' % (a, len(A), b, len(B)))
    print('sha256 equal %d (DRM %d), different %d (DRM %d), only in A %d, only in B %d' % (
        len(eq), drm(eq), len(diff), drm(diff), len(oa), len(ob)))
    for k in diff[:40]: print('  different:', k)
    for k in oa[:20]: print('  only in A:', k)
    for k in ob[:20]: print('  only in B:', k)
    print('RESULT: %s' % ('identical' if not (diff or oa or ob) else 'NOT identical'))
    return 0 if not (diff or oa or ob) else 1


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == 'index': sys.exit(cmd_index(a[1], a[2]))
    if len(a) == 3 and a[0] == 'tables': sys.exit(cmd_tables(a[1], a[2]))
    if len(a) == 3 and a[0] == 'tree': sys.exit(cmd_tree(a[1], a[2]))
    sys.exit(__doc__)
