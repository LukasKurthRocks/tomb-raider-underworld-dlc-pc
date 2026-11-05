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

Additions (2026-11-05, agent Seq-Baeume, docs Befund-Seq-Baeume-0511.md):
  --base-undo STATE.json   the base as the NEXT harness run sees it: DIR (--base) with the installs of the previous run
        undone (runs/installed-state.json of scripts/windows/Invoke-TruTestRun.ps1 Undo-PreviousInstall: its tree
        backups in reverse order, replaced files from backup/<tree>/files/<path> (md5 checked against the manifest),
        added files removed). Without it the game folder counts as it stands, open runner installs included.
  --own-after-last         the --own-after fix tree is appended at the END (not at its latest valid position)
  --own-lists DIR          per seqrepeat input set N: DIR/setN.paths (absolute path of each file, one per line, input
        of tools/stage_by_md5.py --paths) and DIR/setN.profiles
  --tex-fix NAME --seq NAME=TREE_DIR:INPUTS [--seq ...]   simulation per profile ("sim"): profile clean now ->
        "no change"; else the --fix tree NAME appended at the end when the texture check fails, then the --seq tree
        whose every file replaces exactly its input copy (0 other copies, 0 added, none shadowed by a "files" entry)
        appended at the end when the Sequence check fails; reports both checks after, every file whose installed md5
        changes, and per appended tree the files it replaces (intended = the tree's input copy, same = already the
        output, other = another copy). INPUTS of a --seq tree: the staged_sources.tsv of its stage_by_md5 run.

Additions (2026-11-05 night, agent Clash-Baeume, docs Befund-Clash-Baeume-0511.md):
  every check now also counts the script clash (tools/script_clash_fix.unfixed_in_file, findings 45 / 46: a DLC
  script class under a resident PC id with another instance layout and a DLC class deriving from it in the same DRM,
  e.g. the thrall base 12433 that the step scriptclash renumbers to 26884); 'clash' in every summary.
  --clash-lists DIR        per profile the final copies (after the steps the simulation appends before the clash step,
        else the profile as it is) that still carry a clash, grouped over all profiles by (name, md5):
        DIR/clash<N>.paths + DIR/clash<N>.profiles (input of tools/stage_by_md5.py --paths and script_clash_fix apply)
  --clash NAME=TREE_DIR:INPUTS [--clash ...]   simulation: after the texture / Sequence steps, when the clash check
        fails, the --clash tree whose every file replaces exactly its input copy is appended at the end (same choice
        rule as --seq); the verdict needs texlist 0, Sequence 0 and clash 0.
"""
import sys, os, json, glob, hashlib, re, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_last_source as PLS

_MD5 = {}
_CHK = {}
_BASE = {}
BASE_UNDO = None          # --base-undo STATE.json


def base_files(base):
    """{rel: (path, 'base')} of DIR, with BASE_UNDO the open runner installs undone (cached per DIR)"""
    if base not in _BASE:
        m = {rel: (p, 'base') for rel, p in tree_files(base, []).items()}
        if BASE_UNDO:
            st = json.load(open(BASE_UNDO, encoding='utf-8-sig'))
            if [f for f in (st.get('files') or []) if f]:
                sys.exit('--base-undo: the state lists single-file installs (Install-TruModFile) - not supported')
            bk = os.path.join(PLS.WS, 'backup')
            nrep = nadd = 0
            for t in reversed([t for t in (st.get('trees') or []) if t]):
                man = json.load(open(os.path.join(bk, t, 'manifest.json'), encoding='utf-8-sig'))
                for a in man.get('added') or []:
                    if m.pop(a.replace('\\', '/').lower(), None): nadd += 1
                for r in man.get('replaced') or []:
                    q = os.path.join(bk, t, 'files', r['path'])
                    if md5(q) != r['md5'].lower(): sys.exit('--base-undo: %s does not match its manifest md5' % q)
                    m[r['path'].replace('\\', '/').lower()] = (q, 'base'); nrep += 1
            print('base %s with the installs of %s undone (%d trees: %d replaced files restored, %d added files '
                  'removed)' % (base, st.get('run'), len([t for t in st.get('trees') or [] if t]), nrep, nadd))
        _BASE[base] = m
    return _BASE[base]


def md5(p):
    p = os.path.abspath(p)
    if p not in _MD5:
        h = hashlib.md5()
        with open(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
        _MD5[p] = h.hexdigest()
    return _MD5[p]


_RES = []                 # resident script layouts of tools/script_clash_fix (loaded once)


def clash_count(path):
    """unfixed script clash groups (with a derived DLC class) of one DRM; 0 for the resident bank itself"""
    import script_clash_fix as SC
    if os.path.basename(path).lower() in SC.SKIP: return 0
    if not _RES: _RES.append(SC.resident())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return len(SC.unfixed_in_file(path, _RES[0]))


def check(path):
    """(texlist problems, seq repeat-wrong words, seq pad-only words, seq unexpected, script clash groups) of one
    file, cached by md5"""
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
        _CHK[h] = (nbad, rep, pad, unexp, clash_count(path))
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
    out = dict(base_files(base)) if base else {}
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
    tl, rep, pad, unexp, cl = [], [], [], [], []
    for rel, (p, label) in sorted(final.items()):
        if not rel.endswith('.drm'): continue
        a, b, c, d, e = check(p)
        if a: tl.append(os.path.basename(rel))
        if b: rep.append(os.path.basename(rel))
        if c: pad.append(os.path.basename(rel))
        if d: unexp.append(os.path.basename(rel))
        if e: cl.append(os.path.basename(rel))
    return dict(texlist=tl, seq_repeat=rep, seq_pad=pad, seq_unexpected=unexp, clash=cl)


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


def classify(cur, files, base, fix):
    """appending fix at the END of the tree list cur: per file of the fix tree what it replaces"""
    prev = install(cur, files, base)
    out = dict(intended=[], same=[], other=[], added=[], shadowed=[])
    for rel in sorted(fix['files']):
        n = os.path.basename(rel)
        if rel in files: out['shadowed'].append(n); continue      # a "files" entry wins over every tree
        if rel not in prev: out['added'].append(n); continue
        m = md5(prev[rel][0])
        if m == fix['outputs'][rel]: out['same'].append(n)
        elif m == fix['inputs'].get(rel): out['intended'].append(n)
        else: out['other'].append('%s %s from %s' % (n, m[:8], prev[rel][1]))
    return out


def seq_bad(s):
    return len(s['seq_repeat']) + len(s['seq_pad']) + len(s['seq_unexpected'])


def pick(cur, files, base, cands, badness):
    """the candidate tree whose every file replaces exactly its input copy (0 other copies, 0 added, none shadowed),
    appended at the end: (step dict, new tree list, also matching names) or (None, closest dict, [])"""
    ok, best = [], None
    for f in cands:
        c = classify(cur, files, base, f)
        miss = len(c['other']) + len(c['added']) + len(c['shadowed'])
        if best is None or miss < best[0]: best = (miss, f, c)
        if not miss and c['intended']:
            cand = cur + [(f['name'], f['files'])]
            ok.append((badness(summary(install(cand, files, base))), f, c, cand))
    if not ok:
        return None, dict(best=best[1]['name'] if best else None, **(best[2] if best else {})), []
    # clean result first; among those the tree that carries the fewest files the profile has already
    # (e.g. the 1-file Crushers tree for a profile whose other 14 copies are fixed)
    ok.sort(key=lambda x: (x[0], len(x[2]['same'])))
    _, f, c, cand = ok[0]
    return dict(tree=f['name'], **c), cand, [x[1]['name'] for x in ok[1:]]


def sim(trees, files, base, texfix, seqfixes, clashfixes=()):
    """the profile + (texfix if the texture check fails) + (the matching seq tree if the Sequence check fails) + (the
    matching clash tree if the script clash check fails), each appended at the end -> dict(now, after, steps, changed,
    verdict, pre_clash = the tree list before the clash step)"""
    first = install(trees, files, base)
    now = summary(first)
    res = dict(now=now, steps=[], changed=[], pre_clash=list(trees))
    if not now['texlist'] and not seq_bad(now) and not now['clash']:
        res.update(after=now, verdict='no change'); return res
    cur = list(trees)
    if now['texlist'] and texfix:
        c = classify(cur, files, base, texfix)
        res['steps'].append(dict(tree=texfix['name'], **c))
        cur = cur + [(texfix['name'], texfix['files'])]
    mid = summary(install(cur, files, base))
    res['mid'] = mid
    if seq_bad(mid) and seqfixes:
        st, cand, also = pick(cur, files, base, seqfixes, seq_bad)
        if st:
            res['steps'].append(st); cur = cand
            if also: res['also_matching'] = also
        else: res['no_seq_tree'] = cand
    res['pre_clash'] = list(cur)
    mid2 = summary(install(cur, files, base))
    if mid2['clash'] and clashfixes:
        st, cand, also = pick(cur, files, base, clashfixes, lambda s: len(s['clash']) + seq_bad(s) + len(s['texlist']))
        if st:
            res['steps'].append(st); cur = cand
            if also: res['also_matching_clash'] = also
        else: res['no_clash_tree'] = cand
    fin = install(cur, files, base)
    after = summary(fin)
    res['after'] = after
    res['changed'] = sorted(os.path.basename(rel) for rel in fin if rel not in first or md5(fin[rel][0]) != md5(first[rel][0]))
    # a set: a later step (clash) may replace the output of an earlier one (seq) - same file, counted once
    intended = sorted({n for s in res['steps'] for n in s['intended']})
    other = [x for s in res['steps'] for x in s['other'] + s['added'] + s['shadowed']]
    clean = not after['texlist'] and not seq_bad(after) and not after['clash']
    res['verdict'] = 'ok' if clean and not other and res['changed'] == intended else 'FAIL'
    return res


def sim_table(report):
    print('\n| Profile | trees to append (in order) | texlist now -> after | Sequence (repeat / pad / unexpected) now -> after | clash DRMs now -> after | files replaced | verdict |')
    print('|---|---|---|---|---|---|---|')
    for r in report:
        s = r['sim']
        tr = ', '.join(x['tree'] for x in s['steps']) or ('-' if s['verdict'] == 'no change' else 'NONE MATCHES')
        q = lambda d: '%d / %d / %d' % (len(d['seq_repeat']), len(d['seq_pad']), len(d['seq_unexpected']))
        print('| %s | %s | %d -> %d | %s -> %s | %d -> %d | %d | %s |' % (r['profile'], tr, len(s['now']['texlist']),
              len(s['after']['texlist']), q(s['now']), q(s['after']), len(s['now']['clash']), len(s['after']['clash']),
              len(s['changed']), s['verdict']))


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
    global BASE_UNDO
    if '--base-undo' in a: k = a.index('--base-undo'); BASE_UNDO = a[k + 1]; del a[k:k + 2]
    own_last = '--own-after-last' in a
    a = [x for x in a if x != '--own-after-last']
    own_lists = texfix_name = None
    if '--own-lists' in a: k = a.index('--own-lists'); own_lists = a[k + 1]; del a[k:k + 2]
    if '--tex-fix' in a: k = a.index('--tex-fix'); texfix_name = a[k + 1]; del a[k:k + 2]
    seqfixes = []
    while '--seq' in a:
        k = a.index('--seq'); seqfixes.append(load_fix(a[k + 1])); del a[k:k + 2]
    for f in seqfixes:
        print('seq tree %s: %s, %d files, inputs known for %d' % (f['name'], f['root'], len(f['files']),
                                                              sum(1 for v in f['inputs'].values() if v)))
    clashfixes = []
    while '--clash' in a:
        k = a.index('--clash'); clashfixes.append(load_fix(a[k + 1])); del a[k:k + 2]
    for f in clashfixes:
        print('clash tree %s: %s, %d files, inputs known for %d' % (f['name'], f['root'], len(f['files']),
                                                                sum(1 for v in f['inputs'].values() if v)))
    clash_lists = None
    if '--clash-lists' in a: k = a.index('--clash-lists'); clash_lists = a[k + 1]; del a[k:k + 2]
    cgroups, cpaths = {}, {}
    if a: sys.exit('unknown arguments: %s' % a)
    groups = {}
    paths_of = {}
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
            if not os.path.isdir(src): print('  WARNING %s: tree source %s does not exist' % (os.path.basename(pp), src))
            seg = t['source'].replace('\\', '/').rstrip('/').split('/')
            label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
            trees.append((label, tree_files(src, t.get('exclude'))))
        files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
        pn = os.path.basename(pp)[:-5]
        now = summary(install(trees, files, base))
        print('\nPROFILE %s: %d trees (%s)' % (pn, len(trees), ', '.join(t[0] for t in trees)))
        print('  now: texlist %s | seq repeat %s | seq pad-only %s | seq unexpected %s | clash %s' % (
            now['texlist'] or '-', now['seq_repeat'] or '-', now['seq_pad'] or '-', now['seq_unexpected'] or '-',
            now['clash'] or '-'))
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
            if own_last: cur = cur + [(own_after, byname[own_after]['files'])]
            else:
                k, cand, _ = place(cur, files, base, byname[own_after])
                if k is not None: cur = cand
        fin = install(cur, files, base)
        need = []
        for rel, (p, label) in sorted(fin.items()):
            if not rel.endswith('.drm'): continue
            a_, b_, c_, d_, _e = check(p)
            if b_ or c_ or d_: need.append((os.path.basename(rel), md5(p), label, b_, c_, d_))
        sig = tuple((n, h) for n, h, *_ in need)
        if sig: groups.setdefault(sig, []).append(pn)
        if sig and sig not in paths_of:
            paths_of[sig] = [os.path.abspath(fin[rel][0]) for rel in sorted(fin) if rel.endswith('.drm') and
                             any(os.path.basename(rel) == n and md5(fin[rel][0]) == h for n, h in sig)]
        pre_clash = list(trees)
        if seqfixes or texfix_name or clashfixes:
            s = sim(trees, files, base, byname.get(texfix_name), seqfixes, clashfixes)
            pre_clash = s.pop('pre_clash')
            rep['sim'] = s
            print('  sim: %s; appended %s; texlist %d -> %d; seq repeat/pad/unexpected %d/%d/%d -> %d/%d/%d; clash DRMs '
                  '%d -> %d; %d files change (%s)' % (
                      s['verdict'], ', '.join(x['tree'] for x in s['steps']) or '-', len(s['now']['texlist']),
                      len(s['after']['texlist']), len(s['now']['seq_repeat']), len(s['now']['seq_pad']),
                      len(s['now']['seq_unexpected']), len(s['after']['seq_repeat']), len(s['after']['seq_pad']),
                      len(s['after']['seq_unexpected']), len(s['now']['clash']), len(s['after']['clash']),
                      len(s['changed']), ', '.join(s['changed']) or '-'))
            if s.get('no_clash_tree'):
                nb = s['no_clash_tree']
                print('    NO matching clash tree; closest %s: other %d (%s), added %d, shadowed %d' % (
                    nb.get('best'), len(nb.get('other') or []), ', '.join(nb.get('other') or []),
                    len(nb.get('added') or []), len(nb.get('shadowed') or [])))
            if s.get('also_matching_clash'): print('    also matching (clash): %s' % ', '.join(s['also_matching_clash']))
            for x in s['steps']:
                print('    + %s: intended %d, same %d, other %d%s, added %d%s, shadowed %d' % (
                    x['tree'], len(x['intended']), len(x['same']), len(x['other']),
                    (' (%s)' % ', '.join(x['other'])) if x['other'] else '', len(x['added']),
                    (' (%s)' % ', '.join(x['added'])) if x['added'] else '', len(x['shadowed'])))
            if s.get('no_seq_tree'):
                nb = s['no_seq_tree']
                print('    NO matching seq tree; closest %s: other %d (%s), added %d, shadowed %d' % (
                    nb.get('best'), len(nb.get('other') or []), ', '.join(nb.get('other') or []),
                    len(nb.get('added') or []), len(nb.get('shadowed') or [])))
            if s.get('also_matching'): print('    also matching: %s' % ', '.join(s['also_matching']))
            if s['verdict'] != 'no change':
                print('    after: texlist %s | seq repeat %s | seq pad-only %s | seq unexpected %s | clash %s' % (
                    s['after']['texlist'] or '-', s['after']['seq_repeat'] or '-', s['after']['seq_pad'] or '-',
                    s['after']['seq_unexpected'] or '-', s['after']['clash'] or '-'))
        print('  own seqrepeat tree (after %s): %d files: %s' % (own_after or '-', len(need), ', '.join(
            '%s %s from %s (repeat %d, pad %d%s)' % (n, h[:8], lb, b_, c_, (', UNEXPECTED %d' % d_) if d_ else '')
            for n, h, lb, b_, c_, d_ in need)))
        rep['own_seqrepeat'] = [dict(name=n, md5=h, source=lb, repeat=b_, pad=c_, unexpected=d_) for n, h, lb, b_, c_, d_ in need]
        # files a profile-specific scriptclash tree would have to carry: the final copies (after the steps the
        # simulation appends before its clash step) that still carry a clash group
        pfin = install(pre_clash, files, base)
        cneed = [(os.path.basename(rel), md5(p), label, check(p)[4]) for rel, (p, label) in sorted(pfin.items())
                 if rel.endswith('.drm') and check(p)[4]]
        csig = tuple((n, h) for n, h, *_ in cneed)
        if csig:
            cgroups.setdefault(csig, []).append(pn)
            cpaths.setdefault(csig, [os.path.abspath(pfin[rel][0]) for rel in sorted(pfin) if rel.endswith('.drm') and
                                     any(os.path.basename(rel) == n and md5(pfin[rel][0]) == h for n, h in csig)])
            sub = [rel for rel in sorted(pfin) if '/' in rel and any(os.path.basename(rel) == n for n, h in csig)]
            if sub: print('  WARNING clash copies in a sub folder (a flat staged tree would put them at the root): %s' % sub)
        print('  own scriptclash tree (after %s): %d files: %s' % (', '.join(t[0] for t in pre_clash[len(trees):]) or 'the profile',
              len(cneed), ', '.join('%s %s from %s (groups %d)' % (n, h[:8], lb, g) for n, h, lb, g in cneed)))
        rep['own_scriptclash'] = [dict(name=n, md5=h, source=lb, groups=g) for n, h, lb, g in cneed]
        report.append(rep)
    print('\nown seqrepeat trees: %d distinct input sets' % len(groups))
    for i, (sig, ps) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        print('  set %d (%d files): %s' % (i + 1, len(sig), ', '.join(ps)))
        print('     %s' % ', '.join('%s %s' % (n, h[:8]) for n, h in sig))
        if own_lists:
            os.makedirs(own_lists, exist_ok=True)
            with open(os.path.join(own_lists, 'set%d.paths' % (i + 1)), 'w', encoding='utf-8', newline='\n') as h:
                for p in paths_of[sig]: h.write(p.replace('\\', '/') + '\n')
            with open(os.path.join(own_lists, 'set%d.profiles' % (i + 1)), 'w', encoding='utf-8', newline='\n') as h:
                for p in ps: h.write(p + '\n')
            for p in paths_of[sig]: print('     path %s %s' % (md5(p), p.replace('\\', '/')))
    print('\nown scriptclash trees: %d distinct input sets' % len(cgroups))
    for i, (sig, ps) in enumerate(sorted(cgroups.items(), key=lambda kv: (-len(kv[1]), kv[1]))):
        print('  clash set %d (%d files): %s' % (i + 1, len(sig), ', '.join(ps)))
        print('     %s' % ', '.join('%s %s' % (n, h[:8]) for n, h in sig))
        for p in cpaths[sig]: print('     path %s %s' % (md5(p), p.replace('\\', '/')))
        if clash_lists:
            os.makedirs(clash_lists, exist_ok=True)
            with open(os.path.join(clash_lists, 'clash%d.paths' % (i + 1)), 'w', encoding='utf-8', newline='\n') as h:
                for p in cpaths[sig]: h.write(p.replace('\\', '/') + '\n')
            with open(os.path.join(clash_lists, 'clash%d.profiles' % (i + 1)), 'w', encoding='utf-8', newline='\n') as h:
                for p in ps: h.write(p + '\n')
    if seqfixes or texfix_name or clashfixes: sim_table(report)
    if outj:
        json.dump(report, open(outj, 'w', encoding='utf-8'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
