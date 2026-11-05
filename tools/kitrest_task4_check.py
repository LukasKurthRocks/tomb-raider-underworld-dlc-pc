"""Kit-rest task 4: the raw ids / words that the B270 kit still carries (thrall event ids `idword`, goo machine effect
node ids `fxnode`, doppelganger_casual chart value `chartid`, fx_waterwheel_fsfx float `animlist`, raft bridge
particle words `objrec`) - are they also wrong in the copies OUR test profiles install? (read-only; workspace docs
Befund-Kit-Reste-0511.md).

Replays every profile (tools/profile_fix_plan.py install, read-only; --base-undo as there), collects the distinct
copies (md5) of the named files, adds his B270 copy (calibration), and runs on each copy the existing check of the
family: tools/converter_faults_fix.run_tree(check_only=True, steps=...) resp. tools/objdata_fx_fix.fix_drm(['rec'])
(planned words = wrong words). Xbox source pack: --pack (run once per DLC: DLC 2 names pack11, DLC 1 names pack10).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/kitrest_task4_check.py --profile "tests/profiles/*.json" --base GAME/mods
        [--base-undo STATE.json] --pack pack11 --steps idword,fxnode,chartid,animlist NAME.drm [...] [--his DIR]
  steps: converter_faults_fix step names and/or 'objrec'
"""
import sys, os, glob, json, io, contextlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_fix_plan as PFP
import profile_last_source as PLS


def main(a):
    profiles = []
    while '--profile' in a:
        k = a.index('--profile'); profiles += sorted(glob.glob(a[k + 1])) or [a[k + 1]]; del a[k:k + 2]
    base = his = None; pack = 'pack11'; steps = ['idword', 'fxnode', 'chartid', 'animlist']
    if '--base' in a: k = a.index('--base'); base = a[k + 1]; del a[k:k + 2]
    if '--base-undo' in a: k = a.index('--base-undo'); PFP.BASE_UNDO = a[k + 1]; del a[k:k + 2]
    if '--pack' in a: k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    if '--steps' in a: k = a.index('--steps'); steps = a[k + 1].split(','); del a[k:k + 2]
    if '--his' in a: k = a.index('--his'); his = a[k + 1]; del a[k:k + 2]
    os.environ['TRUDLC_PACK_FIRST'] = pack
    names = [n.replace('\\', '/').lower() for n in a]
    copies = collections.OrderedDict()           # (name, md5) -> [path, labels set, profiles list]
    for pp in profiles:
        prof = json.load(open(pp, encoding='utf-8-sig'))
        trees = []
        for t in prof.get('trees') or []:
            if not t: continue
            seg = t['source'].replace('\\', '/').rstrip('/').split('/')
            label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
            trees.append((label, PFP.tree_files(PLS.resolve(t['source']), t.get('exclude'))))
        files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fin = PFP.install(trees, files, base)
        for n in names:
            if n not in fin: continue
            p, lab = fin[n]; m = PFP.md5(p)
            c = copies.setdefault((n, m), [p, set(), []]); c[1].add(lab); c[2].append(os.path.basename(pp)[:-5])
    if his:
        for n in names:
            p = os.path.join(his, n)
            if os.path.isfile(p):
                m = PFP.md5(p); c = copies.setdefault((n, m), [p, set(), []]); c[1].add('HIS-B270')
    import converter_faults_fix as CF
    ctx = CF.Ctx()
    fsteps = [s for s in steps if s != 'objrec']
    if 'objrec' in steps:
        import objdata_fx_fix as OF, drm_write as DW
        rules = OF.load_rules()
    print('pack first: %s, steps %s, copies %d' % (pack, ','.join(steps), len(copies)))
    for (n, m), (p, labs, profs) in copies.items():
        cells = []
        if fsteps:
            lines = []
            r = CF.run_tree([os.path.dirname(p)], None, fsteps, names=[os.path.basename(p)], check_only=True, ctx=ctx,
                            log=lines.append)
            for st in fsteps:
                c = r['counts'].get(st, {})
                cells.append('%s wrong %d' % (st, c.get('wrong', 0)))
            if r['unexpected']: cells.append('unexpected %d' % len(r['unexpected']))
            if r['files_without_xbox_original']: cells.append('NO XBOX ORIGINAL')
            if r['files'] != 1: cells.append('files matched %d' % r['files'])
        if 'objrec' in steps:
            XD, pk = OF.xbox_drm(os.path.basename(p))
            if XD is None: cells.append('objrec: no Xbox source')
            else:
                ch, _ = OF.fix_drm(XD, DW.read(open(p, 'rb').read(), 'le'), ['rec'], rules)
                cells.append('objrec wrong %d' % len(ch))
        print('%-36s %s %-34s %s | profiles %d: %s' % (n, m[:8], '/'.join(sorted(labs)), '; '.join(cells), len(profs),
                                                    ', '.join(profs[:6]) + (' ...' if len(profs) > 6 else '')))


if __name__ == '__main__':
    main(sys.argv[1:])
