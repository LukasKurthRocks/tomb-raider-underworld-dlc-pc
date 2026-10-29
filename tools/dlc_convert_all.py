"""Convert DLC DRMs (Xbox, from work/generic/dlc_drms.pkl) to PC DRMs with dlc_generic.convert_drm and check them.

Checks per output DRM: parses back with drm_write.read (LE), reloc blobs parse + bounds (drm_reloc.check),
every id reference resolves (same DRM, PC base universe, or another converted DLC DRM), Obj section ids are
in the merged objectlist, route statistics per section type.
Usage: python3 -I tools/dlc_convert_all.py [--media] [--write] [name-substring ...]
  --media : use dlc_generic.default_media (textures/terrain/mesh/material/silent waves; shaders pass through)
  --write : write <out>/<name>.drm (CDRM, LE) to work/generic/out/
  --extra-fixes : convert_drm(..., extra_fixes=True) - the DLC post-passes that assemble_dlc enables with
                  material 'dlc' (model points, DTP lists/align, SoundPlex fields, script SArray counts, tag 0x403,
                  portals, uberobject descriptors, link ratios, analog id guard); off by default as before
  --out DIR : write to DIR instead of work/generic/out/ (experiments; subfolders pack10/pack11 as usual)
  --jobs N  : N processes (default: environment TRUDLC_JOBS, else 1). Each loads the store and the learned tables
              once and needs ~18 GB RAM; a file written by two records is written only by the last one, as before.
              Verified: --jobs 2 writes the same 300 files byte for byte as --jobs 1 (finding 36)
"""
import sys, os, pickle, struct, collections, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW, dlc_generic as DG, generic_store
W = DG.W

def check(secs, pc_ids, dlc_defined, objids):
    st = collections.Counter()
    infos = [dict(size=len(s.data)) for s in secs]
    have = {(s.type, s.id) for s in secs}
    for s in secs:
        r = R.parse(s.reloc, 'le')
        st['reloc_bounds_bad'] += bool(R.check(r, len(s.data), infos))
        for t, o in r.idref + r.idref_a:
            if o + 4 > len(s.data): continue
            v, = struct.unpack_from('<I', s.data, o)
            if v in (0, 0xffffffff): continue
            if (t, v) in have: st['idref_local'] += 1
            elif v in pc_ids.get(t, ()): st['idref_pc_base'] += 1
            elif (t, v) in dlc_defined: st['idref_other_dlc'] += 1
            else: st['idref_DANGLING'] += 1; st['dangling_type_%d' % t] += 1
        if s.type == 11: st['obj_ok' if s.id in objids else 'obj_BAD'] += 1
    return st

C = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
PACK_PATHS = [C + '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000', C + '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000']
_CTX = {}


def _init(media_on, extra, dlc_defined, objids):
    """per process: the large tables (store, learned table, id map); also used in-process for --jobs 1"""
    _CTX.update(store=generic_store.load(), ids=DG.DlcIds(), T=DG.table(), media=DG.default_media if media_on else None,
                extra=extra, dlc_defined=dlc_defined, objids=objids, archives={})


def convert_one(task):
    """task = (pack index, record index, out file or None) -> (route counter, check counter, symbol stats, missing)"""
    from archive import Archive
    from drm import cdrm_decode, sections_with_data
    pi, ri, dst = task
    A = _CTX['archives'].get(pi)
    if A is None: A = _CTX['archives'][pi] = Archive(PACK_PATHS[pi], 'be')
    r = A.idx[ri]
    ids = _CTX['ids']
    s0, m0 = collections.Counter(ids.sym_stats), collections.Counter(ids.missing)
    raw = cdrm_decode(A.read(r), 'be')
    X = DW.read(raw, 'be')
    h, xsecs = sections_with_data(raw, 'be')
    secs, rep = DG.convert_drm(xsecs, ids, _CTX['store'], media=_CTX['media'], T=_CTX['T'], extra_fixes=_CTX['extra'])
    routes = collections.Counter((t, route) for k, t, xid, nid, route in rep)
    D = DW.Drm(secs, X.names, X.pad, X.ver, X.u0, X.u1)
    praw = D.write('le')
    back = DW.read(praw, 'le')
    tot = collections.Counter(drm=1)
    tot['readback_ok'] += len(back.sections) == len(xsecs) and all(a.data == b.data and a.reloc == b.reloc for a, b in zip(back.sections, secs))
    tot.update(check(secs, _CTX['store']['pc_ids'], _CTX['dlc_defined'], _CTX['objids']))
    if dst:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(DW.cdrm_encode(praw, 'le'))
    return routes, tot, collections.Counter(ids.sym_stats) - s0, collections.Counter(ids.missing) - m0


def main(argv):
    write = '--write' in argv
    out_arg = argv[argv.index('--out') + 1] if '--out' in argv else None
    # --jobs N, else TRUDLC_JOBS (set by Invoke-TruPipeline.ps1 from the free memory), else 1
    jobs = int(argv[argv.index('--jobs') + 1]) if '--jobs' in argv else int(os.environ.get('TRUDLC_JOBS') or 1)
    jobs_arg = argv[argv.index('--jobs') + 1] if '--jobs' in argv else None
    pats = [a for a in argv if not a.startswith('--') and a not in (out_arg, jobs_arg)]
    dlc = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    ids0 = DG.DlcIds()
    objids = set(json.load(open(os.path.join(W, 'merged', 'object_id_remap_xbox_to_pc.json'))).values())
    dlc_defined = {(s['type'], ids0(s['type'], s['id'])) for _, (h, secs) in dlc.items() for s in secs}
    del dlc
    out = out_arg or os.path.join(W, 'out')      # --out: e.g. an experiment folder below work/rebuild
    os.makedirs(out, exist_ok=True)
    from archive import Archive
    from names import load, L
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    # task list in archive order; a file name that occurs twice (duplicate records) is written by its LAST record
    # only, as the sequential version did by overwriting - so no two processes write the same file
    tasks, last = [], {}
    for pi, pk in enumerate(PACK_PATHS):
        A = Archive(pk, 'be')
        for ri, r in enumerate(A.idx):
            name = xn.get(r['hash'], '0x%08x' % r['hash']).split('\\')[-1]
            if pats and not any(p in name for p in pats): continue
            if A.read(r)[:4] not in (b'CDRM', b'\0\0\0\x13'): continue
            fn = name if name.endswith('.drm') else name + ('_%08x' % r['spec']) + '.drm'
            dst = os.path.join(out, os.path.basename(pk).split('.')[0], fn) if write else None
            last[dst] = len(tasks); tasks.append([pi, ri, dst])
    for k, t in enumerate(tasks):
        if t[2] is not None and last[t[2]] != k: t[2] = None
    tot = collections.Counter(); routes = collections.Counter(); sym = collections.Counter(); missing = collections.Counter()
    t0 = time.time(); init = ('--media' in argv, '--extra-fixes' in argv, dlc_defined, objids)
    if jobs <= 1:
        _init(*init); results = map(convert_one, tasks)
    else:
        from concurrent.futures import ProcessPoolExecutor
        ex = ProcessPoolExecutor(max_workers=jobs, initializer=_init, initargs=init)
        results = ex.map(convert_one, tasks, chunksize=1)
    for rt, tt, ss, mm in results:
        routes.update(rt); tot.update(tt); sym.update(ss); missing.update(mm)
    if jobs > 1: ex.shutdown()
    print('DRMs %d in %.0fs (jobs %d)' % (tot['drm'], time.time() - t0, jobs))
    for k, v in sorted(tot.items(), key=str): print(' ', k, v)
    for k, v in sorted(routes.items(), key=str): print('  route', k, v)
    print('symbol stats', dict(sym), 'unmapped ids', dict(missing))

if __name__ == '__main__':
    main(sys.argv[1:])
