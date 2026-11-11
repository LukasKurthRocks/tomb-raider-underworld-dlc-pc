"""Xbox <-> PC script section pairs of one converted DLC DRM, by the converter's id map (Q46, 2026-11-11).

Why: the pipeline steps uitext / uirecord looked the PC section up under the XBOX id (and only for ids >= 20000), the
step uiinit the Xbox section under the PC id. The converter gives every Xbox script the PC id DlcIds(8, xid) (base
scripts: the base id map, e.g. g_pda Xbox 3207 = PC 3347), and the step scriptclash renumbers some DLC copies
(docs/data/script_clash_ids.json, 12433 -> 26884). Renumbered scripts were therefore never paired (and a same-size
script that merely shares the number would have been taken); measured on work/rebuild/pipeline_check_1111b in
docs Befund-UI-Textids-1111.md (workspace docs folder).

pairs(xs, D, ids, store) -> ({PC section index: (Xbox section dict, route)}, Counter)
  PC id = DlcIds(8, xid) or its script_clash_ids.json id; the pair needs the same script name Symbol (DlcIds.sym of
  the Xbox name at +0x08 == the PC name), else no pair (counted). Two Xbox scripts on one PC section: no pair (counted).
  route = the converter's type-8 route (dlc_generic._convert_drm order):
    'pc_copy'   the Xbox content is an Xbox base content of that id, or a PC re-authored base script: PC bytes
    'template'  base id, same size / relocation layout as the Xbox and PC base: PC base bytes with the words the DLC
                changed re-converted
    'convert'   Xbox layout through the learned word tables (DLC-new scripts, base scripts the DLC re-authored)
"""
import os, sys, json, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CLASH_FILE = os.path.join(HERE, '..', 'docs', 'data', 'script_clash_ids.json')
_CLASH = None
_STORE = None


def clash_ids():
    """{old PC id: new PC id} of type 8 from docs/data/script_clash_ids.json (step scriptclash)"""
    global _CLASH
    if _CLASH is None:
        d = json.load(open(CLASH_FILE, encoding='utf-8')) if os.path.exists(CLASH_FILE) else {'ids': []}
        _CLASH = {e['old']: e['new'] for e in d['ids'] if e['type'] == 8}
    return _CLASH


def store():
    """the converter's section store (work/generic/store.pkl), loaded once"""
    global _STORE
    if _STORE is None:
        import generic_store
        _STORE = generic_store.load()
    return _STORE


def name_sym(d, e):
    return struct.unpack_from(('>' if e == 'be' else '<') + 'HH', d, 0x08)


def route(x, xs, ids, st, nid):
    """the converter's route for Xbox script x (PC id nid): 'pc_copy' / 'template' / 'convert'"""
    import dlc_generic as DG
    from generic_store import norm_hash
    xid = x['id']; key = (8, xid); bm = ids.base.get(8, {})
    if xid in bm and (8, nid) in st['pc_store'] and norm_hash(x, xs, 'be') in st['xb_hash'].get(key, ()):
        return 'pc_copy'
    if key in DG.reauthored(st, ids) and norm_hash(x, xs, 'be') in st['xb_hash'].get(key, ()):
        return 'pc_copy'
    xb = st['xb_store'].get(key); pc = st['pc_store'].get((8, nid))
    if xid in bm and xb is not None and pc is not None and len(xb['data']) == len(x['data']) == len(pc['data']) \
            and DG._same_layout(xb['reloc'], x['reloc']):
        return 'template'
    return 'convert'


def pairs(xs, D, ids, st=None, need_route=True):
    """({PC section index: (Xbox section dict, route or None)}, Counter) for the type-8 sections of PC DRM D"""
    c = collections.Counter()
    pool = {}
    for k, s in enumerate(D.sections):
        if s.type == 8 and s.data: pool.setdefault(s.id, []).append(k)
    clash = clash_ids()
    got = {}
    for x in xs:
        if x['type'] != 8 or x['data'] is None: continue
        nid = ids(8, x['id'])
        cand = [nid] + ([clash[nid]] if nid in clash else [])
        ks = [k for i in cand for k in pool.get(i, ())]
        if not ks: c['Xbox scripts without a PC section of the mapped id'] += 1; continue
        if len(ks) > 1: c['Xbox scripts with several PC sections of the mapped id (no pair)'] += 1; continue
        k = ks[0]; xa, xb = name_sym(x['data'], 'be')
        if name_sym(D.sections[k].data, 'le') != (ids.sym(xa), ids.sym(xb)):
            c['Xbox scripts whose mapped PC section has another name (no pair)'] += 1; continue
        got.setdefault(k, []).append((x, nid))
    out = {}
    for k, lst in got.items():
        if len(lst) > 1: c['PC sections claimed by several Xbox scripts (no pair)'] += 1; continue
        x, nid = lst[0]
        r = route(x, xs, ids, st if st is not None else store(), nid) if need_route else None
        out[k] = (x, r)
        c['pairs'] += 1
        if x['id'] != D.sections[k].id: c['pairs with another PC id (renumbered)'] += 1
        if r: c['pairs route %s' % r] += 1
    return out, c
