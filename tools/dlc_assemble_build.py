"""Stage-1 tree of DLC 1 (pack10) or DLC 2 (pack11) converted with upstream's full stage-1 route (assemble_dlc,
material 'dlc').

Same calls as tools/convert_dlc.py and the author's work/ws/rebuild/convert_fresh.py:
  assemble_dlc.assemble(raw, ids, store, assemble_dlc.dlc_shader_src, wave='silence', pc_copy=True, template=True,
                        material='dlc')
i.e. DLC materials via material_dlc.py, PC shader sections in place of the Xbox ones, meshes/terrain via the render
tables in work/render/ (built by tools/render_tables_build.py + the render tools, finding 28) and convert_drm's extra
fixes. The non-DRM files (music, audio streams, images, locals, padshock, tr8) are taken from an existing stage-1
tree (dlc_media_build.py output); only the DRMs are replaced, at the rel path of their Xbox name.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -u -I -X utf8 tools/dlc_assemble_build.py SRC_MODS_DIR OUT_MODS_DIR [--pack pack10|pack11] [--only SUBSTR] [--jobs N]
  --pack: which DLC (default pack10 = DLC 1; pack11 = DLC 2, SRC = its Media tree, e.g. work/rebuild/dlc2_stage1/mods;
          pack1 / pack2 / pack20 = the costume packs, 2 costume DRMs each)
  --jobs N: N processes (default: environment TRUDLC_JOBS, else 1); ~16 GB RAM each (finding 36)
  e.g. work/rebuild/stage1/mods work/rebuild/asm_stage1/mods   (OUT is replaced, must be below work/rebuild)
Report: <OUT>/../assemble_report.tsv (per DRM: status, bytes, seconds, bad, missing shaders, routes).
A DRM that fails is removed from OUT (not left as the SRC copy) and the tool exits non-zero.
"""
import sys, os, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
WG = os.path.join(HERE, '..', 'work', 'generic')


PACK_INDEX = {'pack10': 0, 'pack11': 1, 'pack1': 2, 'pack2': 3, 'pack20': 4}     # index into convert_dlc.PACKS


def pack_drms(pack):
    """xenon-w\\... names of the DRMs of a pack from work/generic/dlc_names.txt (columns: hash pack spec size kind name)"""
    seen = collections.OrderedDict()
    for line in open(os.path.join(WG, 'dlc_names.txt'), encoding='latin1'):
        f = line.split()
        if len(f) >= 6 and f[1] == pack and f[-1].lower().endswith('.drm') and f[-1].lower().startswith('xenon-w\\'):
            seen.setdefault(f[-1], f[0])
    return seen


def main(argv):
    only = None; pack = 'pack10'
    if '--only' in argv:
        k = argv.index('--only'); only = argv[k + 1]; del argv[k:k + 2]
    if '--pack' in argv:
        k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
        if pack not in PACK_INDEX: sys.exit('--pack must be one of ' + ', '.join(PACK_INDEX))
    src, out = argv[0], argv[1]
    from build_util import replace_tree
    replace_tree(src, out, must_be_below=True)
    from archive import Archive
    from names import crc
    from convert_dlc import R as ROOT, PACKS
    jobs = int(os.environ.get('TRUDLC_JOBS') or 1)
    if '--jobs' in argv: jobs = int(argv[argv.index('--jobs') + 1])
    arc = Archive(ROOT + PACKS[PACK_INDEX[pack]], 'be')
    rep = open(os.path.join(os.path.dirname(os.path.abspath(out)), 'assemble_report.tsv'), 'w')
    rep.write('relpath\tstatus\tbytes\tsec\tbad\tmissing_sh\troutes\n')
    names = pack_drms(pack); st = collections.Counter(); t00 = time.time()
    print('%s DRM names' % pack, len(names), 'jobs', jobs, flush=True)
    tasks = []
    for name in names:
        rel = name[len('xenon-w\\'):].replace('\\', '/')
        if only and only not in rel: continue
        h = crc(name)
        recs = [i for i, r in enumerate(arc.idx) if r['hash'] == h and r['spec'] == 0xffffffff]
        if not recs: rep.write('%s\tNOT_IN_%s\n' % (rel, pack.upper())); st['not_in_pack'] += 1; continue
        tasks.append((rel, recs[0], out))
    if jobs <= 1:
        _init(pack); results = map(assemble_one, tasks)
    else:
        from concurrent.futures import ProcessPoolExecutor
        ex = ProcessPoolExecutor(max_workers=jobs, initializer=_init, initargs=(pack,))
        results = ex.map(assemble_one, tasks, chunksize=1)
    for rel, row, status in results:              # in task order, whatever the number of processes
        rep.write(row); st[status] += 1
        print(row.rstrip('\n').replace('\t', '  ')[:150], flush=True)
        # a failed DRM must not stay in OUT as the SRC (generic route) copy - that would mix both routes silently
        if status == 'error' and os.path.exists(os.path.join(out, rel)): os.remove(os.path.join(out, rel))
    if jobs > 1: ex.shutdown()
    rep.close()
    print('DRMs', dict(st), 'total %.0f s' % (time.time() - t00))
    if st['error']: sys.exit('%d DRMs failed and were removed from OUT (see assemble_report.tsv)' % st['error'])


_CTX = {}


def _init(pack='pack10'):
    """per process: store and id map (the assemble route needs ~16 GB per process, finding 36)"""
    import dlc_generic as DG, generic_store
    from archive import Archive
    from convert_dlc import R as ROOT, PACKS
    store = generic_store.load()
    _CTX.update(store=store, ids=DG.DlcIds(store, None), arc=Archive(ROOT + PACKS[PACK_INDEX[pack]], 'be'))


def assemble_one(task):
    """(rel, record index, out dir) -> (rel, report row, status); writes <out>/<rel>"""
    import assemble_dlc as A
    rel, ri, out = task
    t0 = time.time()
    try:
        data, r = A.assemble(_CTX['arc'].read(_CTX['arc'].idx[ri]), _CTX['ids'], _CTX['store'], A.dlc_shader_src,
                             wave='silence', pc_copy=True, template=True, material='dlc')
    except Exception as e:
        return rel, '%s\tERROR %s: %s\n' % (rel, type(e).__name__, str(e)[:150]), 'error'
    p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)
    return rel, '%s\tOK\t%d\t%.1f\t%s\t%s\t%s\n' % (rel, len(data), time.time() - t0, r['bad'], r['missing_shaders'],
                                                   dict(r['routes'])), 'ok'


if __name__ == '__main__':
    main(sys.argv[1:])
