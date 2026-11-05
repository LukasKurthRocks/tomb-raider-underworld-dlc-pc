"""Compare the files of a rebuilt upstream kit (tools/kit_rebuild.py output) with our trees, file by file and, for DRMs
whose content differs, section by section (pairing and normalised relocations of tools/compare_drm.py, as
tools/compare_sections.py). Read-only on all inputs; writes only --out (2026-11-05, docs Befund-B270-Kit-0511.md).

Content equality: DRMs are compared DECOMPRESSED (a kit DRM rebuilt here can carry another zlib stream than the
author's file with the same content); other files by md5.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/kit_tree_compare.py KIT_MANIFEST KIT_MODS --ref LABEL=DIR [--ref LABEL=DIR ...]
        [--base LABEL] [--out PREFIX] [--jobs N] [--detail 12]
  KIT_MANIFEST  manifest.json of the kit (dlc / area per file); KIT_MODS its rebuilt mods folder
  --ref         reference mods folders, e.g. b138=work/rebuild/b138_pristine/mods ours=../data/pc/mods
  --base LABEL  with two refs: also classify each file as in tools/upstream_manifest_compare.py (same as base / only
                kit changed / only ours changed / both, differently) - base = the first --ref
  PREFIX.tsv    one row per kit file and ref: status, differing sections per type; PREFIX.md: counts per area
  PREFIX_sections.tsv  every section that differs (type, id, sizes, differing 32-bit words, reloc equal)
"""
import sys, os, json, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_rebuild as K
import kit_inspect as KI


def content(p):
    b = open(p, 'rb').read()
    if p.lower().endswith('.drm'): b = K.cdrm_decode(b, 'le')
    return hashlib.md5(b).hexdigest()


def sec_diff(args):
    """per differing DRM: sections paired as compare_drm.section_matches; list of differing / unpaired sections"""
    import compare_drm as C
    rel, a, b = args
    try:
        sa, sb = C.load(open(a, 'rb').read()), C.load(open(b, 'rb').read())
    except Exception as e:
        return rel, dict(error='%s: %s' % (type(e).__name__, e))
    m = C.section_matches(sa, sb); pa = {i for i, _, _ in m}; pb = {j for _, j, _ in m}
    rows = []; st = collections.Counter()
    for i, j, how in m:
        x, y = sa[i], sb[j]
        de = x['data'] == y['data']; re_ = C.norm_reloc(x, sa) == C.norm_reloc(y, sb)
        st['matched'] += 1
        if de and re_: st['identical'] += 1; continue
        n = min(len(x['data']), len(y['data']))
        w = sum(1 for k in range(0, n - 3, 4) if x['data'][k:k + 4] != y['data'][k:k + 4])
        rows.append((x['type'], x['id'], y['id'], len(x['data']), len(y['data']), w, 'same' if re_ else 'differs'))
        st['differ t%d' % x['type']] += 1
    for i, x in enumerate(sa):
        if i not in pa: rows.append((x['type'], x['id'], '-', len(x['data']), 0, -1, 'only kit')); st['only kit t%d' % x['type']] += 1
    for j, y in enumerate(sb):
        if j not in pb: rows.append((y['type'], '-', y['id'], 0, len(y['data']), -1, 'only ref')); st['only ref t%d' % y['type']] += 1
    st['kit sections'] = len(sa); st['ref sections'] = len(sb)
    return rel, dict(st=dict(st), rows=rows)


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def main(argv):
    refs = []
    while '--ref' in argv:
        v = arg(argv, '--ref'); l, d = v.split('=', 1); refs.append((l, d))
    out = arg(argv, '--out', 'work/b270_kit/compare'); jobs = int(arg(argv, '--jobs', '6')); det = int(arg(argv, '--detail', '12'))
    base = arg(argv, '--base')
    man = json.load(open(argv[0], encoding='utf-8')); kmods = argv[1]
    files = [f for f in man['files']]
    res = {}       # rel -> {label: status}
    jobsl = []
    for f in files:
        rel = f['rel']; p = os.path.join(kmods, rel.replace('/', os.sep))
        r = res.setdefault(rel, {})
        if not os.path.isfile(p): r['_kit'] = 'missing'; continue
        ck = content(p); r['_kit'] = ck
        for l, d in refs:
            q = os.path.join(d, rel.replace('/', os.sep))
            if not os.path.isfile(q):
                # case-insensitive fallback
                qd = os.path.dirname(q)
                cand = [n for n in (os.listdir(qd) if os.path.isdir(qd) else []) if n.lower() == os.path.basename(q).lower()]
                q = os.path.join(qd, cand[0]) if cand else None
            if not q: r[l] = 'absent'; continue
            r[l + '_c'] = content(q)
            if r[l + '_c'] == ck: r[l] = 'identical'
            else:
                r[l] = 'differs'
                if rel.lower().endswith('.drm'): jobsl.append((rel + '|' + l, p, q))
    secs = {}
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, d in ex.map(sec_diff, jobsl, chunksize=1): secs[key] = d
    # report
    area = {f['rel']: (f.get('dlc'), KI.area(f)) for f in files}
    def group(rel):
        dlc, ar = area[rel]
        if ar == 'costume': return 'costumes'
        if ar == 'audio': return 'audio'
        if dlc == 'dlc1': return 'DLC 1'
        if dlc == 'dlc2': return 'DLC 2'
        return 'other (%s/%s)' % (dlc, ar)
    tab = collections.defaultdict(collections.Counter)
    for rel, r in res.items():
        for l, _ in refs: tab[group(rel)][(l, r.get(l, 'kit missing'))] += 1
    lines = ['# Kit files against our trees', '', 'Kit: %s (%d files), rebuilt mods: `%s`' % (man.get('build'), len(files), kmods), '']
    for l, d in refs: lines.append('- ref `%s` = `%s`' % (l, d))
    lines += ['', '| Group | Files | ' + ' | '.join('%s: identical / differs / absent' % l for l, _ in refs) + ' |',
              '|---|---|' + '---|' * len(refs)]
    for g in sorted(tab):
        n = sum(1 for rel in res if group(rel) == g)
        lines.append('| %s | %d | ' % (g, n) + ' | '.join('%d / %d / %d' % (tab[g][(l, 'identical')], tab[g][(l, 'differs')], tab[g][(l, 'absent')]) for l, _ in refs) + ' |')
    tot = collections.Counter()
    for rel, r in res.items():
        for l, _ in refs: tot[(l, r.get(l, 'kit missing'))] += 1
    lines.append('| **all** | %d | ' % len(res) + ' | '.join('%d / %d / %d' % (tot[(l, 'identical')], tot[(l, 'differs')], tot[(l, 'absent')]) for l, _ in refs) + ' |')
    if base and len(refs) >= 2:
        o = [l for l, _ in refs if l != base][0]
        cls = collections.Counter(); per = collections.defaultdict(list)
        for rel, r in res.items():
            k, b_, u = r.get('_kit'), r.get(base + '_c'), r.get(o + '_c')
            if b_ is None and u is None: c = 'new, we have none'
            elif b_ is None: c = 'new, same as ours' if k == u else 'new, differs from ours'
            elif u is None: c = 'kit has it, we do not'
            elif k == b_ == u: c = 'same as %s (nobody changed)' % base
            elif k == u: c = 'kit = ours, both changed %s' % base
            elif k == b_: c = 'only ours changed %s' % base
            elif u == b_: c = 'only the kit changed %s' % base
            else: c = 'both changed %s, differently' % base
            cls[c] += 1; per[c].append(rel)
        lines += ['', '## Three-way (base `%s`, ours `%s`, content compare)' % (base, o), '', '| Class | Files |', '|---|---|']
        for c, n in cls.most_common(): lines.append('| %s | %d |' % (c, n))
        for c in ('only the kit changed %s' % base,):
            lines += ['', '### %s' % c, ''] + ['- `%s`' % r for r in sorted(per[c])]
    # section summary per ref
    for l, _ in refs:
        st = collections.Counter(); nf = 0
        for key, d in secs.items():
            if not key.endswith('|' + l) or 'st' not in d: continue
            nf += 1
            for k, v in d['st'].items():
                if k.startswith('differ') or k.startswith('only'): st[k] += v
        lines += ['', '## Sections of differing DRMs vs `%s` (%d DRMs)' % (l, nf), '',
                  ', '.join('%s %d' % kv for kv in sorted(st.items())) or 'none']
        top = sorted(((key.split('|')[0], d) for key, d in secs.items() if key.endswith('|' + l) and 'st' in d),
                     key=lambda kd: -sum(v for k, v in kd[1]['st'].items() if k.startswith('differ') or k.startswith('only')))
        for rel, d in top[:det]:
            s = d['st']
            lines.append('- `%s`: %d/%d sections, %s' % (rel, s.get('kit sections', 0), s.get('ref sections', 0),
                         ', '.join('%s %d' % (k, v) for k, v in sorted(s.items()) if k.startswith('differ') or k.startswith('only'))))
        errs = [(key, d['error']) for key, d in secs.items() if key.endswith('|' + l) and 'error' in d]
        for key, e in errs: lines.append('- error `%s`: %s' % (key, e))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out + '.md', 'w', encoding='utf-8', newline='\n') as fo: fo.write('\n'.join(lines) + '\n')
    with open(out + '.tsv', 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('rel\tgroup\tkit_content_md5\t' + '\t'.join(l for l, _ in refs) + '\n')
        for rel in sorted(res):
            fo.write('%s\t%s\t%s\t%s\n' % (rel, group(rel), res[rel].get('_kit'), '\t'.join(res[rel].get(l, '') for l, _ in refs)))
    with open(out + '_sections.tsv', 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('rel\tref\ttype\tkit_id\tref_id\tkit_size\tref_size\twords_differ\treloc\n')
        for key in sorted(secs):
            rel, l = key.split('|')
            for row in secs[key].get('rows', []): fo.write('%s\t%s\t%s\n' % (rel, l, '\t'.join(str(x) for x in row)))
    print('\n'.join(lines))
    print('\nreports: %s.md / .tsv / _sections.tsv' % out)


if __name__ == '__main__':
    main(sys.argv[1:])
