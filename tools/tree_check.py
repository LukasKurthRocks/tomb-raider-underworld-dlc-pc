"""Structural self-check of a converted mods tree without a reference build (read-only; for DLC 2, which has no B138).

Per DRM: does it read back as a PC (LE) DRM; per section: relocations within bounds (drm_reloc.check, the same test as
dlc_convert_all's readback); id references (relocation idrefs) that point to a section in the same DRM vs elsewhere;
per-type section counts. Run it on a known-good tree (e.g. DLC 1 asm_stage2b) and on the new tree to compare.
Without the generic store it cannot tell PC-base ids from dangling ones (use dlc_convert_all's readback for that).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/tree_check.py MODS_DIR LABEL
Report: work/rebuild/tree_check_<LABEL>.json
"""
import sys, os, json, struct, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')


def check_file(args):
    import drm_write as DW, drm_reloc as R
    rel, path = args
    st = collections.Counter()
    try:
        D = DW.read(open(path, 'rb').read(), 'le')
    except Exception as e:
        return rel, {'readback_error': '%s: %s' % (type(e).__name__, str(e)[:120])}
    secs = D.sections
    infos = [dict(size=len(s.data)) for s in secs]
    have = {(s.type, s.id) for s in secs}
    for s in secs:
        st['sections'] += 1; st['type_%d' % s.type] += 1
        try:
            r = R.parse(s.reloc, 'le')
        except Exception:
            st['reloc_parse_error'] += 1; continue
        st['reloc_bounds_bad'] += bool(R.check(r, len(s.data), infos))
        for t, o in r.idref + r.idref_a:
            if o + 4 > len(s.data): st['idref_out_of_section'] += 1; continue
            v, = struct.unpack_from('<I', s.data, o)
            if v in (0, 0xffffffff): st['idref_null'] += 1
            elif (t, v) in have: st['idref_local'] += 1
            else: st['idref_elsewhere'] += 1
    return rel, dict(st)


def main(argv):
    from build_util import require_dir
    mods, label = argv[0], argv[1]
    require_dir(mods, 'MODS_DIR')
    jobs = []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if f.endswith('.drm'):
                p = os.path.join(dp, f); jobs.append((os.path.relpath(p, mods).replace(os.sep, '/'), p))
    out, tot = {}, collections.Counter()
    with ProcessPoolExecutor(max_workers=int(os.environ.get('TRUDLC_JOBS_LIGHT') or os.cpu_count())) as ex:
        for rel, st in ex.map(check_file, sorted(jobs)):
            out[rel] = st
            if 'readback_error' in st: tot['readback_error'] += 1; continue
            tot['readback_ok'] += 1; tot.update(st)
    print('DRMs %d: readback ok %d, errors %d' % (len(jobs), tot['readback_ok'], tot['readback_error']))
    print('sections %d, reloc parse errors %d, sections with reloc out of bounds %d' % (
        tot['sections'], tot['reloc_parse_error'], tot['reloc_bounds_bad']))
    print('id references: local %d, elsewhere %d, null %d, outside their section %d' % (
        tot['idref_local'], tot['idref_elsewhere'], tot['idref_null'], tot['idref_out_of_section']))
    print('sections by type:', {k[5:]: v for k, v in sorted(tot.items(), key=lambda kv: int(kv[0][5:]) if kv[0].startswith('type_') else 0)
                                if k.startswith('type_')})
    for rel, st in out.items():
        if 'readback_error' in st: print('   readback error', rel, st['readback_error'])
    os.makedirs(W, exist_ok=True)
    rep = os.path.join(W, 'tree_check_%s.json' % label)
    json.dump({'mods': mods, 'total': dict(tot), 'files': out}, open(rep, 'w'), indent=0)
    print('report', os.path.abspath(rep))


if __name__ == '__main__':
    main(sys.argv[1:])
