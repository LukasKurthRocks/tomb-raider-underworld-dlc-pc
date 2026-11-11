"""Which files of the upstream release kits (B138, B270) does our own pipeline already produce? Read-only inventory
(2026-11-10, docs Befund-Kit-Unabhaengigkeit-1011.md).

For every file a kit writes (manifest 'files' + 'extra' / 'exe'), the file of the same relative path is looked up in
our pipeline output trees and classified:
  identical       our file has the kit's md5 (or, for DRMs, the same decompressed content)
  differs         we produce the file, the content differs; reason = differing DRM section types (paired and
                  compared as tools/compare_drm.py / tools/kit_tree_compare.py) or the file kind (audio, image ...)
  kit_based       only our trees built ON the kit have it (Repair = B138 + fixes, Generalbank = B138's + steps)
  only_kit        none of our trees has the file
Origin per file: the B90_gold_L4 manifest origin (upstream build / overlay layer, DLC 1 files) and the kit's own
source record (Xbox pack, PC file, authored).

Nothing is written but --tsv and --md. The TSV holds names, md5 hashes, sizes, classes and section-type counts only.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/kit_dependency.py [--run work/rebuild/pipeline_check_1011] [--no-sections]
        [--tsv docs/data/kit_dependency.tsv] [--md work/kitdep_1011/summary.md]
  defaults: B138 kit ../release/B138/kit/manifest.json, its files from <run>_repair/b138_pristine/mods;
            B270 kit work/b270_kit/kit/manifest.json, its files from work/b270_kit/mods (tools/kit_rebuild.py output);
            independent trees <run>/dlc1/mods, <run>/dlc2/mods, work/rebuild/costumes_0913/<pack>/stage2b/mods;
            kit-based trees <run>_repair/b138_fixes/mods, <run>_gb/generalbank_build/mods
  --own OWN_DIR (2026-11-11): the assembled own tree of tools/own_tree.py (OWN_DIR/mods, OWN_DIR/exe/tru.exe) is the
            only tree; its manifest's kit_derived column decides 'kit_based'. --b138-mods DIR: where the B138 kit
            files are when <run>_repair does not exist (read only, e.g. work/rebuild/pipeline_check_1011_repair/...)
"""
import sys, os, json, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_inspect as KI

TYPE_NAME = {0: 'general', 2: 't2', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
             11: 'obj', 12: 'mesh', 13: 't13'}


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def content_md5(p):
    b = open(p, 'rb').read()
    if p.lower().endswith('.drm'):
        import kit_rebuild as K
        b = K.cdrm_decode(b, 'le')
    return hashlib.md5(b).hexdigest()


def find(root, rel):
    """case-insensitive lookup of rel below root"""
    if not root or not os.path.isdir(root): return None
    p = os.path.join(root, rel.replace('/', os.sep))
    if os.path.isfile(p): return p
    cur = root
    for part in rel.split('/'):
        if not os.path.isdir(cur): return None
        hit = [n for n in os.listdir(cur) if n.lower() == part.lower()]
        if not hit: return None
        cur = os.path.join(cur, hit[0])
    return cur if os.path.isfile(cur) else None


def sec_types(kit_p, our_p):
    """differing section types between the kit file and ours: {type: n} (+ 'only kit' / 'only ours' counts)"""
    import compare_drm as C
    sa, sb = C.load(open(kit_p, 'rb').read()), C.load(open(our_p, 'rb').read())
    m = C.section_matches(sa, sb); pa = {i for i, _, _ in m}; pb = {j for _, j, _ in m}
    st = collections.Counter(); ident = 0
    for i, j, _ in m:
        x, y = sa[i], sb[j]
        if x['data'] == y['data'] and C.norm_reloc(x, sa) == C.norm_reloc(y, sb): ident += 1; continue
        st[TYPE_NAME.get(x['type'], 't%d' % x['type'])] += 1
    for i, x in enumerate(sa):
        if i not in pa: st['kitonly_' + TYPE_NAME.get(x['type'], 't%d' % x['type'])] += 1
    for j, y in enumerate(sb):
        if j not in pb: st['ouronly_' + TYPE_NAME.get(y['type'], 't%d' % y['type'])] += 1
    return st, ident, len(sa)


def reason_of(rel, st):
    """short reason / stage from the differing section types (DRM) or the file kind"""
    r = rel.lower()
    if st is None:
        if r.endswith('.mul'): return 'audio_mul'
        if r.endswith('.mus') or r.endswith('.sam'): return 'music'
        if r.endswith('.raw'): return 'image'
        if r.endswith('.bik'): return 'video'
        if r.endswith('.exe'): return 'exe'
        if r.endswith('.bin') or r.startswith('local'): return 'text'
        return 'other'
    keys = set(k.split('_', 1)[-1] for k in st)
    out = []
    if keys & {'shaderlib', 'material', 'mesh'}: out.append('shader_material')
    if keys & {'wave'}: out.append('wave')
    if keys & {'dtp', 'script', 'general', 'obj', 't2', 't13'}: out.append('data')
    if keys & {'texture'}: out.append('texture')
    if any(k.startswith('kitonly_') or k.startswith('ouronly_') for k in st): out.append('sections_unpaired')
    return '+'.join(out) or 'header_or_order'


def main(argv):
    run = arg(argv, '--run', 'work/rebuild/pipeline_check_1011')
    tsv = arg(argv, '--tsv', 'docs/data/kit_dependency.tsv')
    md = arg(argv, '--md', 'work/kitdep_1011/summary.md')
    own = arg(argv, '--own')
    b138_mods = arg(argv, '--b138-mods', run + '_repair/b138_pristine/mods')
    nosec = '--no-sections' in argv
    kits = [('B138', '../release/B138/kit/manifest.json', b138_mods),
            ('B270', 'work/b270_kit/kit/manifest.json', 'work/b270_kit/mods')]
    indep = [('dlc1', run + '/dlc1/mods'), ('dlc2', run + '/dlc2/mods')]
    for pk in ('pack1', 'pack2', 'pack20'):
        indep.append(('cost_' + pk, 'work/rebuild/costumes_0913/%s/stage2b/mods' % pk))
    based = [('repair', run + '_repair/b138_fixes/mods'), ('gb', run + '_gb/generalbank_build/mods')]
    if own:
        # the assembled own tree is the only tree; files its manifest marks kit_derived count as 'kit_based'
        indep, based = [('own', own + '/mods'), ('own_exe', own + '/exe')], []
        mp = os.path.join(own, 'own_manifest.tsv')
        kd = set()
        if os.path.isfile(mp):
            for ln in open(mp, encoding='utf-8').read().splitlines()[1:]:
                c = ln.split('\t')
                if len(c) > 6 and c[6] == 'yes': kd.add(c[0].lower())
        if kd: raise SystemExit('own tree has kit_derived files (%s): not supported with --own' % ', '.join(sorted(kd)))
    for l, d in indep + based:
        print('tree %-12s %s %s' % (l, d, 'ok' if os.path.isdir(d) else 'MISSING'))
    b90 = {}
    for ln in open('docs/data/B90_gold_L4.manifest.tsv', encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 4: b90[c[0].lower()] = c[3]
    rows = []
    cache = {}
    for kname, mpath, kmods in kits:
        man = json.load(open(mpath, encoding='utf-8'))
        ents = list(man['files']) + list(man.get('extra', []))
        if man.get('exe'): ents.append(man['exe'])
        for e in ents:
            rel = e['rel'].replace('\\', '/')
            src = e.get('source') or {}
            dlc = e.get('dlc') or ('dlc1' if kname == 'B138' else '')
            area = KI.area(dict(rel=rel, source=e.get('source'))) if 'source' in e else 'other'
            if rel.lower().endswith('.exe'): area = 'exe'
            elif rel.lower().endswith('.bik'): area = 'video'
            srck = src.get('kind') or src.get('where') or ('authored' if e.get('source') is None else '')
            srca = src.get('archive') or src.get('file') or ''
            kp = find(kmods, rel)
            kit_ok = '-' if kp is None else ('ok' if md5_file(kp) == e['md5'] else 'md5_differs')
            if kit_ok == 'md5_differs' and e.get('raw_md5') and content_md5(kp) == e['raw_md5']:
                kit_ok = 'content_ok'          # rebuilt kit DRM: same decompressed content, other zlib stream
            kit_raw = e.get('raw_md5') or (content_md5(kp) if kp and kit_ok == 'ok' and rel.lower().endswith('.drm') else None)
            # our trees: preferred by the kit's dlc field, then the others
            order = sorted(indep, key=lambda t: 0 if t[0] == dlc or (dlc.startswith('cost') and t[0].startswith('cost')) else 1)
            if area == 'costume': order = sorted(indep, key=lambda t: 0 if t[0].startswith('cost') else 1)
            tree, op = '', None
            for l, d in order:
                q = find(d, rel)
                if q: tree, op = l, q; break
            cls, reason, secs, our_md5 = '', '', '', ''
            if op:
                our_md5 = md5_file(op)
                if our_md5 == e['md5']: cls = 'identical'
                elif rel.lower().endswith('.drm') and kit_raw and content_md5(op) == kit_raw:
                    cls, reason = 'identical', 'zlib_only'
                else:
                    cls = 'differs'
                    st = None
                    if rel.lower().endswith('.drm') and kp and not nosec:
                        key = (kp, op)
                        if key not in cache:
                            try: cache[key] = sec_types(kp, op)
                            except Exception as ex: cache[key] = ('%s: %s' % (type(ex).__name__, ex), 0, 0)
                        st, ident, nsec = cache[key]
                        if isinstance(st, str): secs, st = st, collections.Counter(error=1)
                        else: secs = 'ident %d/%d; ' % (ident, nsec) + ','.join('%s=%d' % kv for kv in sorted(st.items()))
                    reason = reason_of(rel, st)
            else:
                for l, d in based:
                    q = find(d, rel)
                    if q: tree, op = l, q; break
                if op:
                    our_md5 = md5_file(op); cls = 'kit_based'
                    reason = 'identical_to_kit' if our_md5 == e['md5'] else 'kit_plus_fixes'
                else:
                    cls, reason = 'only_kit', reason_of(rel, None)
            rows.append(dict(kit=kname, rel=rel, dlc=dlc or '-', area=area, size=e.get('size', 0), kit_md5=e['md5'],
                             mode=e.get('mode', '-'), source_kind=srck or '-', source=srca or '-',
                             b90_origin=b90.get(rel.lower(), '-'), kit_file=kit_ok, our_tree=tree or '-',
                             our_md5=our_md5 or '-', cls=cls, reason=reason or '-', sections=secs or '-'))
        print('%s: %d entries' % (kname, len(ents)))
    cols = ['kit', 'rel', 'dlc', 'area', 'size', 'kit_md5', 'mode', 'source_kind', 'source', 'b90_origin', 'kit_file',
            'our_tree', 'our_md5', 'cls', 'reason', 'sections']
    os.makedirs(os.path.dirname(tsv) or '.', exist_ok=True)
    with open(tsv, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows: f.write('\t'.join(str(r[c]) for c in cols) + '\n')
    # summary
    L = ['# Kit dependency (tools/kit_dependency.py)', '', ('own tree: `%s`' % own) if own else ('run: `%s`' % run), '']
    for kname, _, _ in kits:
        rs = [r for r in rows if r['kit'] == kname]
        c = collections.Counter(r['cls'] for r in rs)
        L += ['## %s (%d files)' % (kname, len(rs)), '', '| class | files | bytes |', '|---|---|---|']
        for k in ('identical', 'differs', 'kit_based', 'only_kit'):
            L.append('| %s | %d | %d |' % (k, c[k], sum(r['size'] for r in rs if r['cls'] == k)))
        L += ['', '| dlc / area | identical | differs | kit_based | only_kit |', '|---|---|---|---|---|']
        g = collections.defaultdict(collections.Counter)
        for r in rs: g['%s / %s' % (r['dlc'], r['area'])][r['cls']] += 1
        for k in sorted(g): L.append('| %s | %d | %d | %d | %d |' % (k, g[k]['identical'], g[k]['differs'], g[k]['kit_based'], g[k]['only_kit']))
        L += ['', '| class / reason | files |', '|---|---|']
        g2 = collections.Counter('%s / %s' % (r['cls'], r['reason']) for r in rs)
        for k, n in sorted(g2.items()): L.append('| %s | %d |' % (k, n))
        L += ['', '| class / B90 origin (DLC 1) | files |', '|---|---|']
        g3 = collections.Counter('%s / %s' % (r['cls'], r['b90_origin'].split(':')[0] if r['b90_origin'].startswith('derived') else r['b90_origin']) for r in rs)
        for k, n in sorted(g3.items()): L.append('| %s | %d |' % (k, n))
        kf = collections.Counter(r['kit_file'] for r in rs)
        L += ['', 'kit files checked against the manifest md5: ' + ', '.join('%s %d' % kv for kv in sorted(kf.items())), '']
    os.makedirs(os.path.dirname(md) or '.', exist_ok=True)
    open(md, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    print('wrote', tsv, md)


if __name__ == '__main__':
    main(sys.argv[1:])
