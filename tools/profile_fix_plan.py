"""Where a fix tree has to go in a test profile's tree list (read-only proposal; agent F5/F25 pipeline, 2026-11-05).

A fix tree (e.g. work/rebuild/dlc_test51q_dungeon) was built from certain input copies of its DRMs (md5 known from
its fix log). Stacked into a profile it replaces whatever copy the profile would install otherwise - a pure fix only
when that copy IS the fix tree's input (or already its output). This tool replays a profile's install order (as
tools/profile_last_source.installed_map / scripts/windows/Install-TruTree.ps1: trees in order, sub folders, the
"exclude" top folders, then "files"; with --base the files of DIR no tree brings), and for every fix tree finds the
LATEST position in the tree list where
  * every file whose final copy would be the fix tree's had, without it, exactly the fix tree's input or output copy
    (nothing else is replaced), and
then reports what the two checks say about the final installed set:
  texlist  tools/objdata_texlist_check.check_drm (object data texture group counts, finding 47)
  seq      tools/soundplex_sequence_fix.check_file (Sequence word +0xc; 'repeat' = the byte the engine reads is wrong,
           'pad' = only the bytes +0xd..+0xf, finding 49)
Nothing is written except stdout (and --json).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/profile_fix_plan.py --profile P.json [--profile ...] [--base DIR]
        --fix NAME=TREE_DIR:INPUTS [--fix ...] [--combo NAME,NAME ...] [--own-after NAME] [--json OUT.json]
  A fix tree without a valid position is also evaluated "forced last" (checks + the other copies it would replace).
  Last per profile: the files a profile-specific seqrepeat tree would have to carry (final copies with a wrong Sequence
  word, after the fix tree --own-after at its latest valid position), grouped over all profiles by (name, md5).
  TREE_DIR: the fix tree (its mods folder is used when present); INPUTS: the fix log with lines
  '<name>.drm (Xbox <pack>, md5 <md5>): ...' (tools/objdata_fx_fix.py check) or a TSV 'name<TAB>md5<TAB>source'
  (tools/stage_by_md5.py); a combo is applied in the order given, each tree at its latest valid position in the list
  that already holds the earlier ones.
  ../bin/pyt -t 300 tools/profile_fix_plan.py table OUT.json      markdown table of a saved --json report
"""
import sys, os, json, glob, hashlib, re, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_last_source as PLS

_MD5 = {}
_CHK = {}


def md5(p):
    p = os.path.abspath(p)
    if p not in _MD5:
        h = hashlib.md5()
        with open(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
        _MD5[p] = h.hexdigest()
    return _MD5[p]


def check(path):
    """(texlist problems, seq repeat-wrong words, seq pad-only words, seq unexpected) of one file, cached by md5"""
    h = md5(path)
    if h not in _CHK:
        import objdata_texlist_check as TLC, soundplex_sequence_fix as SQ
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _, nbad = TLC.check_drm(path, 64, False)
        st, info, XD = SQ.check_file(path)
        rep = pad = unexp = 0
        if info:
            for r in info['rows']:
                if r[6] == 'ok': continue
                if r[6] == 'other': unexp += 1
                elif r[4][0] != r[5][0]: rep += 1
                else: pad += 1
        _CHK[h] = (nbad, rep, pad, unexp)
    return _CHK[h]


def tree_files(src, exclude):
    out = {}
    ex = [e.lower() for e in (exclude if exclude is not None else ['local', 'padshock'])]
    for r, _, fs in os.walk(src):
        for f in fs:
            rel = os.path.relpath(os.path.join(r, f), src).replace('\\', '/')
            if '/' in rel and rel.split('/')[0].lower() in ex: continue
            out[rel.lower()] = os.path.join(r, f)
    return out


def install(trees, files, base):
    """trees: [(label, {rel: path})] in order -> {rel: (path, label)} incl. base files and "files" entries"""
    out = {}
    if base:
        for rel, p in tree_files(base, []).items(): out[rel] = (p, 'base')
    for label, fm in trees:
        for rel, p in fm.items(): out[rel] = (p, label)
    for rel, p in files.items(): out[rel] = (p, 'file')
    return out


def read_inputs(spec):
    want = {}
    for ln in open(spec, encoding='utf-8', errors='replace'):
        m = re.match(r'^(\S+\.drm) \(Xbox [^,]+, md5 ([0-9a-f]{32})\)', ln) or re.match(r'^(\S+\.drm)\t([0-9a-f]{32})\t', ln)
        if m: want.setdefault(m.group(1).lower(), m.group(2))
    return want


def load_fix(arg):
    name, rest = arg.split('=', 1)
    tree, inputs = rest.rsplit(':', 1) if rest.count(':') > (1 if re.match(r'^[A-Za-z]:', rest) else 0) else (rest, None)
    root = os.path.join(tree, 'mods') if os.path.isdir(os.path.join(tree, 'mods')) else tree
    fm = tree_files(root, [])
    ins = read_inputs(inputs) if inputs else {}
    return dict(name=name, root=root, files=fm, inputs={k: ins.get(os.path.basename(k)) for k in fm},
                outputs={k: md5(p) for k, p in fm.items()})


def summary(final):
    tl, rep, pad, unexp = [], [], [], []
    for rel, (p, label) in sorted(final.items()):
        if not rel.endswith('.drm'): continue
        a, b, c, d = check(p)
        if a: tl.append(os.path.basename(rel))
        if b: rep.append(os.path.basename(rel))
        if c: pad.append(os.path.basename(rel))
        if d: unexp.append(os.path.basename(rel))
    return dict(texlist=tl, seq_repeat=rep, seq_pad=pad, seq_unexpected=unexp)


def place(trees, files, base, fix):
    """latest index k (0..len) where inserting fix replaces only its own input / output copies -> (k, final, notes) or
    (None, None, reasons of the last position tried)"""
    prev = install(trees, files, base)
    reasons = None
    for k in range(len(trees), -1, -1):
        cand = trees[:k] + [(fix['name'], fix['files'])] + trees[k:]
        fin = install(cand, files, base)
        bad, adds = [], []
        for rel in fix['files']:
            if fin.get(rel, (None, None))[1] != fix['name']: continue
            if rel not in prev: adds.append(rel); continue
            m = md5(prev[rel][0])
            if m not in (fix['inputs'].get(rel), fix['outputs'][rel]):
                bad.append('%s: installed %s from %s, fix input %s' % (os.path.basename(rel), m[:8], prev[rel][1],
                                                                      (fix['inputs'].get(rel) or '?')[:8]))
        if not bad:
            return k, cand, adds
        if reasons is None: reasons = bad
    return None, None, reasons


def table(path):
    """markdown table of a --json report (no recomputation): per profile the problems now, each fix tree's latest
    valid position (or 'none' + how many other copies stacking it last would replace), the own seqrepeat tree"""
    rep = json.load(open(path, encoding='utf-8'))
    names = list(rep[0]['single']) if rep else []
    print('| Profile | texlist now | seq now (repeat / pad) | %s | own seqrepeat tree (files) |' % ' | '.join(names))
    print('|---|---|---|%s---|' % ('---|' * len(names)))
    for r in rep:
        cells = []
        for n in names:
            s = r['single'][n]
            if s.get('position') is None:
                cells.append('none (last would replace %d other)' % len(s.get('replaces_other') or []))
            else:
                a = s['after']
                cells.append('%s -> texlist %d, seq repeat %d / pad %d' % (s['where'], len(a['texlist']), len(a['seq_repeat']), len(a['seq_pad'])))
        own = r.get('own_seqrepeat') or []
        print('| %s | %d | %d / %d | %s | %d |' % (
            r['profile'], len(r['now']['texlist']), len(r['now']['seq_repeat']), len(r['now']['seq_pad']), ' | '.join(cells),
            len(own)))
    return 0


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'table' and len(a) == 2: return table(a[1])
    profiles, fixes, combos = [], [], []
    base = outj = None
    while '--profile' in a:
        k = a.index('--profile'); profiles += sorted(glob.glob(a[k + 1])) or [a[k + 1]]; del a[k:k + 2]
    while '--fix' in a:
        k = a.index('--fix'); fixes.append(load_fix(a[k + 1])); del a[k:k + 2]
    while '--combo' in a:
        k = a.index('--combo'); combos.append(a[k + 1].split(',')); del a[k:k + 2]
    if '--base' in a: k = a.index('--base'); base = a[k + 1]; del a[k:k + 2]
    if '--json' in a: k = a.index('--json'); outj = a[k + 1]; del a[k:k + 2]
    own_after = None
    if '--own-after' in a: k = a.index('--own-after'); own_after = a[k + 1]; del a[k:k + 2]
    groups = {}
    byname = {f['name']: f for f in fixes}
    for f in fixes:
        print('fix %s: %s, %d files, inputs known for %d' % (f['name'], f['root'], len(f['files']),
                                                         sum(1 for v in f['inputs'].values() if v)))
    report = []
    for pp in profiles:
        prof = json.load(open(pp, encoding='utf-8-sig'))
        trees = []
        for t in prof.get('trees') or []:
            if not t: continue
            src = PLS.resolve(t['source'])
            seg = t['source'].replace('\\', '/').rstrip('/').split('/')
            label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
            trees.append((label, tree_files(src, t.get('exclude'))))
        files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
        pn = os.path.basename(pp)[:-5]
        now = summary(install(trees, files, base))
        print('\nPROFILE %s: %d trees (%s)' % (pn, len(trees), ', '.join(t[0] for t in trees)))
        print('  now: texlist %s | seq repeat %s | seq pad-only %s | seq unexpected %s' % (
            now['texlist'] or '-', now['seq_repeat'] or '-', now['seq_pad'] or '-', now['seq_unexpected'] or '-'))
        rep = dict(profile=pn, trees=[t[0] for t in trees], now=now, single={}, combos={})
        for f in fixes:
            k, cand, notes = place(trees, files, base, f)
            if k is None:
                # what stacking it last anyway would do: the checks, and every copy it would replace that is neither
                # its input nor its output (= content of the profile lost / swapped)
                prev = install(trees, files, base)
                forced = summary(install(trees + [(f['name'], f['files'])], files, base))
                other = sorted(os.path.basename(rel) for rel in f['files'] if rel in prev and
                               md5(prev[rel][0]) not in (f['inputs'].get(rel), f['outputs'][rel]))
                print('  + %s: NO valid position; forced last would replace %d other copies (%s): texlist %s | seq repeat %s | '
                      'seq pad-only %s' % (f['name'], len(other), ', '.join(other), forced['texlist'] or '-',
                                           forced['seq_repeat'] or '-', forced['seq_pad'] or '-'))
                rep['single'][f['name']] = dict(position=None, reasons=notes, forced_last=forced, replaces_other=other)
                continue
            after = summary(install(cand, files, base))
            where = 'last' if k == len(trees) else 'after %s (index %d of %d)' % (trees[k - 1][0] if k else 'nothing', k, len(trees))
            print('  + %s %s%s: texlist %s | seq repeat %s | seq pad-only %s' % (
                f['name'], where, (' (adds %s)' % ', '.join(os.path.basename(x) for x in notes)) if notes else '',
                after['texlist'] or '-', after['seq_repeat'] or '-', after['seq_pad'] or '-'))
            rep['single'][f['name']] = dict(position=k, where=where, adds=notes, after=after)
        for c in combos:
            cur = list(trees); where = []; ok = True
            for n in c:
                k, cand, notes = place(cur, files, base, byname[n])
                if k is None:
                    where.append('%s: NO valid position (%s)' % (n, '; '.join(notes[:4]))); ok = False; break
                where.append('%s %s' % (n, 'last' if k == len(cur) else 'after %s (index %d)' % (cur[k - 1][0] if k else 'nothing', k)))
                cur = cand
            after = summary(install(cur, files, base)) if ok else None
            print('  = combo %s: %s%s' % ('+'.join(c), '; '.join(where), (' -> texlist %s | seq repeat %s | seq pad-only %s' % (
                after['texlist'] or '-', after['seq_repeat'] or '-', after['seq_pad'] or '-')) if after else ''))
            rep['combos']['+'.join(c)] = dict(steps=where, after=after, trees=[t[0] for t in cur] if ok else None)
        # files a profile-specific seqrepeat tree would have to carry: the final copies with a wrong Sequence word after
        # the texture fix (--own-after NAME: that fix tree at its latest valid position first, if it has one)
        cur = list(trees)
        if own_after and own_after in byname:
            k, cand, _ = place(cur, files, base, byname[own_after])
            if k is not None: cur = cand
        fin = install(cur, files, base)
        need = []
        for rel, (p, label) in sorted(fin.items()):
            if not rel.endswith('.drm'): continue
            a_, b_, c_, d_ = check(p)
            if b_ or c_ or d_: need.append((os.path.basename(rel), md5(p), label, b_, c_, d_))
        sig = tuple((n, h) for n, h, *_ in need)
        groups.setdefault(sig, []).append(pn)
        print('  own seqrepeat tree (after %s): %d files: %s' % (own_after or '-', len(need), ', '.join(
            '%s %s from %s (repeat %d, pad %d%s)' % (n, h[:8], lb, b_, c_, (', UNEXPECTED %d' % d_) if d_ else '')
            for n, h, lb, b_, c_, d_ in need)))
        rep['own_seqrepeat'] = [dict(name=n, md5=h, source=lb, repeat=b_, pad=c_, unexpected=d_) for n, h, lb, b_, c_, d_ in need]
        report.append(rep)
    print('\nown seqrepeat trees: %d distinct input sets' % len(groups))
    for i, (sig, ps) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        print('  set %d (%d files): %s' % (i + 1, len(sig), ', '.join(ps)))
        print('     %s' % ', '.join('%s %s' % (n, h[:8]) for n, h in sig))
    if outj:
        json.dump(report, open(outj, 'w', encoding='utf-8'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
