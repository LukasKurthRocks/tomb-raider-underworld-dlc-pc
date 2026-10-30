"""Convert a base-game DRM from the Xbox (retail or title update) with the DLC converter and compare chosen sections
with the PC base game (finding 42: can TU-only scripts of generalbank.drm be converted for the PC?).

The conversion runs without PC copies or templates (assemble_dlc.assemble(..., pc_copy=False, template=False,
reauthored=False)), so every section really goes through the converter. For the retail source the PC sections are the
reference (how close does the converter get?); for the TU source the output carries the TU-only changes.
Compared per section: size equal, 32-bit words equal (% of the PC section), and the first differing offsets.

Usage (from the repository root; loads the generic store, ~16 GB RAM, finding 36):
  ..\\bin\\venv\\Scripts\\python.exe -u -I -X utf8 tools/base_convert_check.py NAME retail|tu [--ids 8:6,8:21239] [--pc 8:134=104] [--compare-only]
  Output DRM: work/rebuild/base_convert/<retail|tu>[_tpl]_<NAME> or --out FILE; --compare-only reuses it (no store, seconds)
  --template: let the converter use the PC section as layout template (as the normal DLC route does)
  Two scores: words equal at the same offset (shifted by any inserted bytes) and aligned (difflib on 32-bit words).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C

BS = chr(92)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild', 'base_convert')


def aligned(c, p):
    """words of the PC section matched by an aligned comparison (difflib on 32-bit words; insertions do not shift)"""
    import difflib
    cw = [c[o:o + 4] for o in range(0, len(c) - 3, 4)]; pw = [p[o:o + 4] for o in range(0, len(p) - 3, 4)]
    m = sum(b.size for b in difflib.SequenceMatcher(None, cw, pw, autojunk=False).get_matching_blocks())
    return m, len(pw)


def main(argv):
    want = None; pcids = {}
    if '--ids' in argv:
        k = argv.index('--ids'); want = [tuple(int(v) for v in x.split(':')) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--pc' in argv:          # explicit PC id for an Xbox id the id map gets wrong, e.g. 8:134=104 (docs/DLC_MENU.md)
        k = argv.index('--pc'); pcids = {tuple(int(v) for v in x.split('=')[0].split(':')): int(x.split('=')[1])
                                         for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    compare_only = '--compare-only' in argv; argv = [x for x in argv if x != '--compare-only']
    template = '--template' in argv; argv = [x for x in argv if x != '--template']   # PC section as layout template
    out = None      # --out FILE: write the converted DRM there instead of work/rebuild/base_convert (generalbank_build.py)
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    name, source = argv[0], argv[1]
    if source not in ('retail', 'tu'): sys.exit('source must be retail or tu')
    import dlc_generic as DG, drm_write as DW
    out = out or os.path.join(OUT, '%s%s_%s' % (source, '_tpl' if template else '', name))
    if compare_only:
        ids = DG.DlcIds()
        data = open(out, 'rb').read()
    else:
        from archive import Archive
        from names import crc
        import assemble_dlc as A, generic_store
        path = C.BASE[0] if source == 'tu' else C.BASE[1]
        a = Archive(path, 'be'); recs = [r for r in a.find(crc('xenon-w' + BS + name)) if r['spec'] == 0xffffffff]
        if not recs: sys.exit('%s not in %s' % (name, path))
        t0 = time.time(); store = generic_store.load(); ids = DG.DlcIds(store, None)
        print('store loaded %.0f s' % (time.time() - t0), flush=True)
        data, rep = A.assemble(a.read(recs[0]), ids, store, A.dlc_shader_src, wave='silence', pc_copy=False, template=template,
                               reauthored=False)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(data)
        print('converted %s (%s): %d bytes, routes %s, bad %s -> %s' % (name, source, len(data), dict(rep['routes']), rep['bad'][:5], out))
    D = DW.read(data, 'le')
    conv = {(s.type, s.id): s.data for s in D.sections}
    pc = {(s['type'], s['id']): s['data'] for s in C.find(C.PC, 'le', 'pc-w' + BS + name)}
    keys = [(t, ids(t, i)) for t, i in want] if want else sorted(k for k in conv if k[0] == 8)
    for (t, i), k in zip(want or keys, keys):
        c = conv.get(k)
        pk = (t, pcids[(t, i)]) if (t, i) in pcids else k
        p = pc.get(pk)
        if c is None: print('   %d:%d -> converted id %d: not in the converted file' % (t, i, k[1])); continue
        if p is None: print('   %d:%d -> PC id %d: converted %d bytes, no PC section (TU-only)' % (t, i, pk[1], len(c))); continue
        n = min(len(c), len(p)) // 4
        same = sum(1 for o in range(n) if c[o * 4:o * 4 + 4] == p[o * 4:o * 4 + 4])
        m, npw = aligned(c, p)
        print('   %d:%d -> PC id %d: converted %d bytes, PC %d bytes; words equal at the same offset %.1f %%, aligned %.1f %% of %d PC words' % (
            t, i, pk[1], len(c), len(p), 100.0 * same / n if n else 0, 100.0 * m / npw if npw else 0, npw))


if __name__ == '__main__':
    main(sys.argv[1:])
