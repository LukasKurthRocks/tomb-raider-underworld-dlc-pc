"""Stage-1 tree of DLC 1 converted with upstream's full stage-1 route (assemble_dlc, material 'dlc').

Same calls as tools/convert_dlc.py and the author's work/ws/rebuild/convert_fresh.py:
  assemble_dlc.assemble(raw, ids, store, assemble_dlc.dlc_shader_src, wave='silence', pc_copy=True, template=True,
                        material='dlc')
i.e. DLC materials via material_dlc.py, PC shader sections in place of the Xbox ones, meshes/terrain via the render
tables in work/render/ (built by tools/render_tables_build.py + the render tools, finding 28) and convert_drm's extra
fixes. The non-DRM files (music, audio streams, images, locals, padshock, tr8) are taken from an existing stage-1
tree (dlc_media_build.py output); only the DRMs are replaced, at the rel path of their Xbox name.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -u -I -X utf8 tools/dlc_assemble_build.py SRC_MODS_DIR OUT_MODS_DIR [--only SUBSTR]
  e.g. work/rebuild/stage1/mods work/rebuild/asm_stage1/mods   (OUT is replaced, must be below work/rebuild)
Report: <OUT>/../assemble_report.tsv (per DRM: status, bytes, seconds, bad, missing shaders, routes).
"""
import sys, os, time, shutil, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
WG = os.path.join(HERE, '..', 'work', 'generic')


def pack10_drms():
    """xenon-w\\... names of the pack10 DRMs from work/generic/dlc_names.txt (columns: hash pack spec size kind name)"""
    seen = collections.OrderedDict()
    for line in open(os.path.join(WG, 'dlc_names.txt'), encoding='latin1'):
        f = line.split()
        if len(f) >= 6 and f[1] == 'pack10' and f[-1].lower().endswith('.drm') and f[-1].lower().startswith('xenon-w\\'):
            seen.setdefault(f[-1], f[0])
    return seen


def main(argv):
    only = None
    if '--only' in argv:
        k = argv.index('--only'); only = argv[k + 1]; del argv[k:k + 2]
    src, out = argv[0], argv[1]
    rebuild = os.path.realpath(os.path.join(HERE, '..', 'work', 'rebuild'))
    if os.path.commonpath([os.path.realpath(out), rebuild]) != rebuild: sys.exit('OUT must be below work/rebuild: ' + out)
    if os.path.exists(out): shutil.rmtree(out)
    shutil.copytree(src, out)
    import assemble_dlc as A, dlc_generic as DG, generic_store
    from archive import Archive
    from names import crc
    from convert_dlc import R as ROOT, PACKS
    store = generic_store.load(); ids = DG.DlcIds(store, None)
    arc = Archive(ROOT + PACKS[0], 'be')
    rep = open(os.path.join(os.path.dirname(os.path.abspath(out)), 'assemble_report.tsv'), 'w')
    rep.write('relpath\tstatus\tbytes\tsec\tbad\tmissing_sh\troutes\n')
    names = pack10_drms(); st = collections.Counter(); t00 = time.time()
    print('pack10 DRM names', len(names), flush=True)
    for name in names:
        rel = name[len('xenon-w\\'):].replace('\\', '/')
        if only and only not in rel: continue
        recs = [r for r in arc.find(crc(name)) if r['spec'] == 0xffffffff]
        if not recs: rep.write('%s\tNOT_IN_PACK10\n' % rel); st['not_in_pack'] += 1; continue
        t0 = time.time()
        try:
            data, r = A.assemble(arc.read(recs[0]), ids, store, A.dlc_shader_src, wave='silence', pc_copy=True,
                                 template=True, material='dlc')
        except Exception as e:
            rep.write('%s\tERROR %s: %s\n' % (rel, type(e).__name__, str(e)[:150])); st['error'] += 1
            print(rel, 'ERROR', type(e).__name__, str(e)[:150], flush=True); continue
        p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(data); st['ok'] += 1
        rep.write('%s\tOK\t%d\t%.1f\t%s\t%s\t%s\n' % (rel, len(data), time.time() - t0, r['bad'], r['missing_shaders'],
                                                     dict(r['routes'])))
        print('%-55s %6.1f s  bad %s  missing_sh %s' % (rel, time.time() - t0, r['bad'], r['missing_shaders']), flush=True)
    rep.close()
    print('DRMs', dict(st), 'total %.0f s' % (time.time() - t00))


if __name__ == '__main__':
    main(sys.argv[1:])
