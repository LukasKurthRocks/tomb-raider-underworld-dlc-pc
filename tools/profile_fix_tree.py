"""ONE combined data-fix tree per test profile (2026-11-05 night, docs Befund-Navmesh-Kombi-0511.md).

The test profiles stack fix trees (dlc_test51q_dungeon, dlc_test51r_seq*, dlc_test51s_clash* ...), each built for an
input copy the profile may or may not install. This tool works on what a profile ENDS UP installing (the replay of
tools/profile_fix_plan.py: trees in order, "files" entries, the game folder as base with --base-undo) and applies every
proven data rule to exactly those copies in one pass, so a profile needs one fix tree at the end:

  statechart  tools/statechart_fix_tree.Fixer.process   chart / table / alist DTPs (twins truth), only the THRALL
              objects and their extensions (task scope F21 / F22; --statechart-all: every copy; other copies are
              reported as statechart_other: the twins disagree with upstream B138 in single words, not decided)
  animfx      tools/dlc_struct_fixes step animfx         anim event lists (test 48g crash class)
  objtex      tools/dlc_struct_fixes step objtex         object data texture group counts (finding 47)
  objrec      tools/dlc_struct_fixes step objrec         object data particle records (F3 / B24)
  objid       tools/dlc_struct_fixes step objid          player data breath-sound ids (N8)
  seqrepeat   tools/dlc_struct_fixes step seqrepeat      SoundPlex Sequence word +0xc raw (finding 49)
  navraw      tools/dlc_struct_fixes step navraw         NavPower NavGraph image raw (tools/navgraph_raw_fix.py)
  objevent idword animlist fxnode statevm chartid   tools/converter_faults_fix steps (finding 44); a word a rule
              cannot explain stops the tool
  kitdtp      tools/kitrest_dtp_fix.plan_file            DTP byte-order words of the DLC 1 files of its PLAN
              (test tree dlc_test51w_dtp, docs Befund-Kit-Reste-0511.md; his = work/b270_kit/mods, read only)
  achievement tools/script_missing_native_fix.process    calls into the TU-only achievement natives (test 40;
              on the PC such a call crashes) - the only rule that changes relocations (it drops the call's)
  scriptclash tools/script_clash_fix.fix_raw             DLC script classes under a resident id (findings 45 / 46),
              ids only from docs/data/script_clash_ids.json (a new group stops the tool - ids must stay stable)
in this order (the pipeline order of tools/dlc_fixes_build.py). Xbox source per copy: the pack whose copy pairs best
(most id- and size-equal sections by position; finding 38: 10 names in pack10 and pack11 with different content).
Options: --cache FILE (plan / verify: per copy and rule counts, reused between runs), --store DIR (build / prove:
one output and one proof per (input md5, name, rules), shared by every set that holds the same copy).

Modes (from the repository root):
  ../bin/pyt -t 14400 tools/profile_fix_tree.py plan --profile GLOB [--profile ...] --base DIR [--base-undo STATE.json]
        --out DIR [--rules statechart,objtex,...]
        every distinct final copy is checked once (cache by md5): words / groups per rule; profiles with the same set
        of (name, md5) copies that need a rule share a set: DIR/set<N>.tsv (rel, md5, path, rules), DIR/set<N>.profiles,
        DIR/plan.json; console = per profile and per set
  ../bin/pyt -t 14400 tools/profile_fix_tree.py build DIR/set<N>.tsv OUT_TREE [--rules ...]
        applies the rules to the listed copies, writes the changed ones to OUT_TREE/mods/<rel>; OUT_TREE/md5.tsv (rel,
        input md5, output md5, source path) and OUT_TREE/fix_log.txt ('<name>.drm (Xbox <pack>, md5 <input md5>): ...'
        lines, the INPUTS format of tools/profile_fix_plan.py --fix / --seq / --clash)
  ../bin/pyt -t 14400 tools/profile_fix_tree.py prove DIR/set<N>.tsv OUT_TREE [--rules ...]
        per file: section headers (scriptclash: type-8 ids by the mapping only), relocations and names identical; the
        changed bytes = the union of the bytes each rule changes ALONE on the input (no other byte, no rule overlap);
        the output re-checked by every rule: 0 words / groups left. Exit 1 on any finding
  ../bin/pyt -t 14400 tools/profile_fix_tree.py verify --profile GLOB --base DIR [--base-undo S] --tree OUT_TREE
        --tsv DIR/set<N>.tsv     the profile with OUT_TREE appended last: every replaced copy is the tree's input
        (intended) and every rule check of the final installed set is 0
"""
import sys, os, io, re, json, glob, hashlib, contextlib, collections, shutil, tempfile, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW

FAULTS = ('objevent', 'idword', 'animlist', 'fxnode', 'statevm', 'chartid')   # tools/converter_faults_fix.STEPS
ORDER = ('statechart', 'animfx', 'objtex', 'objrec', 'objid', 'seqrepeat', 'navraw') + FAULTS + (
    'kitdtp', 'achievement', 'scriptclash')
STRUCT = ('animfx', 'objtex', 'objrec', 'objid', 'seqrepeat', 'navraw')
W = os.path.join(HERE, '..', 'work')
KIT_HIS = os.path.join(W, 'b270_kit', 'mods')    # tools/kitrest_dtp_fix.py --his (read only)


def md5b(b):
    return hashlib.md5(b).hexdigest()


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a)
    return r, buf.getvalue()


class Ctx:
    """shared, lazily built inputs: temp dir, struct steps, statechart fixer, resident scripts, clash ids"""
    def __init__(self):
        os.makedirs(os.path.join(W, 'statechart'), exist_ok=True)
        self.tmp = tempfile.mkdtemp(prefix='pft_', dir=os.path.join(W, 'statechart'))
        self._S = self._F = self._res = None

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def S(self):
        if self._S is None:
            import dlc_struct_fixes as DS
            self._S = DS.Steps(self.tmp, None)
        return self._S

    def F(self):
        if self._F is None:
            import statechart_fix_tree as SF
            self._F = SF.Fixer(self.tmp)
        return self._F

    def cf(self):
        if getattr(self, '_cf', None) is None:
            import converter_faults_fix as CF
            self._cf = CF.Ctx()
        return self._cf

    def nat(self):
        if getattr(self, '_nat', None) is None:
            import script_missing_native_fix as MN
            self._nat = quiet(MN.native_types, 'pc')[0]
        return self._nat

    def res(self):
        if self._res is None:
            import script_clash_fix as SC
            self._res = quiet(SC.resident)[0]
        return self._res

    def tmpfile(self, name, raw, tag='cur'):
        """raw bytes as <tmp>/<tag>/mods/<rel>: name and sub folder stay (the Xbox source is looked up by the path below
        mods, e.g. cinstream\\pdlc1_010_intro.drm - a bare name finds no Xbox copy there)"""
        p = os.path.join(self.tmp, tag, 'mods', *name.replace('\\', '/').split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(raw)
        return p


def best_pack(path):
    """(pack name e.g. 'pack11', label) of the Xbox copy that pairs best with the PC file, or (None, reason)"""
    import soundplex_sequence_fix as SQ, converter_faults_fix as CF
    cands = SQ.xbox_candidates(path, None)
    if not cands: return None, 'no Xbox source'
    PD = DW.read(open(path, 'rb').read(), 'le')
    best = None
    for XD, pk in cands:
        same = sum(1 for k, x, p in CF.pairs_by_position(XD, PD) if x.id == p.id and len(x.data) == len(p.data))
        if best is None or same > best[0]: best = (same, pk)
    pk = best[1].split('.')[0]
    return pk, '%s%s' % (pk, '' if len(cands) == 1 else ' (best of %s)' % '/'.join(c[1].split('.')[0] for c in cands))


@contextlib.contextmanager
def pack_first(pk):
    old = os.environ.get('TRUDLC_PACK_FIRST')
    if pk and pk not in ('pack10', 'pack11', 'pack1', 'pack2', 'pack20'): raise SystemExit('pack %r is no pack name' % pk)
    if pk: os.environ['TRUDLC_PACK_FIRST'] = pk
    try:
        yield
    finally:
        if old is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = old


def faults(C, rel, raw, steps, fix):
    """tools/converter_faults_fix steps on one copy (Xbox source by TRUDLC_PACK_FIRST, as its run_tree) ->
    ({step: words}, unexpected lines, new raw or None)"""
    import converter_faults_fix as CF
    XD, src = CF.xbox_of(rel)
    if XD is None: return {}, ['no Xbox original'], None
    PD = DW.read(raw, 'le'); res = CF.Result()
    per = {}
    for st in steps:
        per[st] = quiet(CF.FNS[st], C.cf(), rel, XD, PD, res, fix)[0]
    new = CF.encode(PD, raw) if fix and any(per.values()) else None
    return per, list(res.unexpected), new


def kitdtp(rel, raw, lines):
    """tools/kitrest_dtp_fix.plan_file on one copy (its own Xbox source order, his = the B270 kit file, read only) ->
    {(section index, offset): (old, new, note)} or None when the file is not in its PLAN"""
    import kitrest_dtp_fix as KD
    key = rel.replace('\\', '/').lower()
    k = next((r for r in KD.PLAN if r.lower() == key), None)
    if k is None: return None
    xs, xsrc = quiet(KD.xbox, k)[0]
    hp = os.path.join(KIT_HIS, k)
    his = DW.read(open(hp, 'rb').read(), 'le') if os.path.isfile(hp) else None
    return quiet(KD.plan_file, k, DW.read(raw, 'le'), xs, his, False, lines)[0]


# ---------------------------------------------------------------- per-copy analysis
def analyze(C, rel, path, rules):
    """{rule: count (words / groups; -1 = rule could not pair the copy)}, notes, pack"""
    import re
    out = collections.OrderedDict(); notes = []
    pk, plabel = best_pack(path)
    if pk is None:
        notes.append('no Xbox source - only achievement / scriptclash checked'); plabel = None
    with pack_first(pk):
        if pk and 'statechart' in rules:
            import statechart_fix_tree as SF
            log = []
            rows = quiet(SF.report, C.F(), rel, path, log)[0]
            # the task scope: the thrall objects and their extensions (F21 / F22); other copies are only reported
            # (key statechart_other, never applied) unless STATECHART_ALL
            key = 'statechart' if STATECHART_ALL or 'thrall' in os.path.basename(rel).lower() else 'statechart_other'
            out[key] = sum(r[6] for r in rows)
        S = C.S()
        for st in STRUCT:
            if st not in rules: continue
            log = []
            try:
                new = quiet(S.process, rel, path, [st], log, collections.Counter())[0]
            except SystemExit as e:
                out[st] = -1; notes.append('%s: STOPPED %s' % (st, e)); continue
            m = [re.match(r'%s \S+: (\d+) words' % st, l) for l in log]
            n = sum(int(x.group(1)) for x in m if x)
            if new is not None and not n: n = 1
            if any('NOT PAIRED' in l or 'proof failed' in l for l in log): out[st] = -1
            else: out[st] = n
            notes += [l[:300] for l in log if new is not None or 'NOT PAIRED' in l or 'proof failed' in l]
        if 'objtex' in rules:
            import objdata_texlist_check as TLC
            _, nbad = quiet(TLC.check_drm, path, 64, False)[0]
            out['texlist'] = nbad
        fs = [s for s in FAULTS if s in rules]
        if pk and fs:
            per, unexp, _ = faults(C, rel, open(path, 'rb').read(), fs, False)
            for s in fs: out[s] = per.get(s, 0)
            if unexp:
                notes += ['faults UNEXPECTED: ' + u[:250] for u in unexp]
                for u in unexp: out[u.split(' ')[0]] = -1
    if 'kitdtp' in rules:
        lines = []
        ch = kitdtp(rel, open(path, 'rb').read(), lines)
        if ch is not None: out['kitdtp'] = len(ch)
    if 'achievement' in rules:
        import script_missing_native_fix as MN
        rep = []
        quiet(MN.process, rel, path, C.nat(), {'achievement'}, rep)
        out['achievement'] = sum(1 for l in rep if l.startswith('FIX'))
        notes += [l[:300] for l in rep if l.startswith('SKIP')]
    if 'scriptclash' in rules:
        import script_clash_fix as SC
        out['scriptclash'] = len(quiet(SC.unfixed_in_file, path, C.res())[0])
    return out, notes, plabel


INFO = ('texlist', 'statechart_other')     # reported, not a rule of its own (texlist -> objtex)
STATECHART_ALL = False                    # --statechart-all: every copy, not only the thrall objects


def need(counts):
    return [r for r, v in counts.items() if v and r not in INFO] + (['objtex'] if counts.get('texlist') and not counts.get('objtex') else [])


def left_of(counts):
    """what a re-check still finds (statechart_other is information only)"""
    return {k: v for k, v in counts.items() if v and k != 'statechart_other'}


# ---------------------------------------------------------------- profile replay (tools/profile_fix_plan.py)
def final_set(PFP, profile, base):
    prof = json.load(open(profile, encoding='utf-8-sig'))
    import profile_last_source as PLS
    trees = []
    for t in prof.get('trees') or []:
        if not t: continue
        src = PLS.resolve(t['source'])
        seg = t['source'].replace('\\', '/').rstrip('/').split('/')
        label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
        if any(re.match(d, label) for d in DROP): continue      # --drop: a stacked fix tree the combined tree replaces
        trees.append((label, PFP.tree_files(src, t.get('exclude'))))
    files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
    return trees, files


DROP = []      # --drop REGEX[,REGEX]: tree labels left out of every profile (e.g. dlc_test51[qrs]_)


def opt(a, key, many=False):
    vals = []
    while key in a:
        k = a.index(key); vals.append(a[k + 1]); del a[k:k + 2]
        if not many: break
    return vals if many else (vals[0] if vals else None)


def cmd_plan(a):
    import profile_fix_plan as PFP
    profiles = []
    for g in opt(a, '--profile', True): profiles += sorted(glob.glob(g)) or [g]
    base = opt(a, '--base'); PFP.BASE_UNDO = opt(a, '--base-undo'); out = opt(a, '--out')
    rules = (opt(a, '--rules') or ','.join(ORDER)).split(',')
    # --cache JSON {md5|name|scope: {rules, counts, notes, pack}} kept between runs; only rules not yet analysed for a
    # copy are run again (old entries 'md5|name|rules|scope': [counts, notes, pack] are taken over)
    cfile = opt(a, '--cache')
    os.makedirs(out, exist_ok=True)
    C = Ctx(); cache = {}; rep = []; sets = collections.OrderedDict(); noxbox = collections.OrderedDict()
    disk = json.load(open(cfile, encoding='utf-8')) if cfile and os.path.exists(cfile) else {}
    for k in [k for k in disk if k.count('|') == 3]:
        h_, n_, r_, s_ = k.split('|'); v = disk.pop(k)
        disk['%s|%s|%s' % (h_, n_, s_)] = dict(rules=r_.split(','), counts=v[0], notes=v[1], pack=v[2])
    scope = 'all' if STATECHART_ALL else 'thrall'
    try:
        for pp in profiles:
            pn = os.path.basename(pp)[:-5]
            trees, files = final_set(PFP, pp, base)
            fin = PFP.install(trees, files, base)
            todo = []; tot = collections.Counter()
            for rel, (p, label) in sorted(fin.items()):
                if not rel.endswith('.drm') or os.path.basename(rel) == 'generalbank.drm': continue
                h = PFP.md5(p)
                dk = '%s|%s|%s' % (h, os.path.basename(rel).lower(), scope)
                if h not in cache:
                    e = disk.get(dk) or dict(rules=[], counts=[], notes=[], pack=None)
                    missing = [x for x in rules if x not in e['rules']]
                    cnt = collections.OrderedDict(e['counts']); notes = list(e['notes']); pk = e['pack']
                    if missing:
                        c2, n2, pk2 = analyze(C, rel, p, missing)
                        cnt.update(c2); notes += n2; pk = pk2 if pk2 else pk
                        if cfile:
                            disk[dk] = dict(rules=sorted(set(e['rules']) | set(missing)), counts=list(cnt.items()), notes=notes, pack=pk)
                            json.dump(disk, open(cfile, 'w', encoding='utf-8'))
                        if any(cnt.values()):
                            print('  copy %s %s from %s (%s): %s' % (rel, h[:8], label, pk, dict(cnt)), flush=True)
                    # only the rules asked for this run count
                    keep = set(rules) | {'texlist' if 'objtex' in rules else '', 'statechart_other' if 'statechart' in rules else ''}
                    cache[h] = (collections.OrderedDict((k, v) for k, v in cnt.items() if k in keep), notes, pk)
                cnt, notes, pk = cache[h]
                if not pk: noxbox.setdefault(h, (rel, p, label))
                nd = need(cnt)
                for r, v in cnt.items():
                    if v: tot[r] += 1
                if nd: todo.append((rel, h, os.path.abspath(p), label, nd, pk))
            sig = tuple((rel, h) for rel, h, *_ in todo)
            if sig: sets.setdefault(sig, dict(profiles=[], files=todo))['profiles'].append(pn)
            print('PROFILE %s: %d trees, %d .drm installed, copies needing a rule %d (files per rule %s)' % (
                pn, len(trees), sum(1 for r in fin if r.endswith('.drm')), len(todo), dict(tot)), flush=True)
            rep.append(dict(profile=pn, copies=[dict(rel=r, md5=h, path=p, source=lb, rules=nd, pack=pk)
                                                for r, h, p, lb, nd, pk in todo], per_rule=dict(tot)))
    finally:
        C.close()
    print('\n%d installed copies without an Xbox source (only achievement / scriptclash checked):' % len(noxbox))
    for h, (rel, p, label) in noxbox.items(): print('  %s %s from %s (%s)' % (rel, h[:8], label, p.replace('\\', '/')))
    print('\n%d distinct sets' % len(sets))
    for i, (sig, s) in enumerate(sorted(sets.items(), key=lambda kv: (-len(kv[1]['profiles']), kv[1]['profiles'])), 1):
        with open(os.path.join(out, 'set%d.tsv' % i), 'w', encoding='utf-8', newline='\n') as f:
            f.write('rel\tmd5\tpath\tsource\trules\tpack\n')
            for rel, h, p, lb, nd, pk in s['files']:
                f.write('%s\t%s\t%s\t%s\t%s\t%s\n' % (rel, h, p.replace('\\', '/'), lb, ','.join(nd), pk))
        open(os.path.join(out, 'set%d.profiles' % i), 'w', encoding='utf-8', newline='\n').write('\n'.join(s['profiles']) + '\n')
        rc = collections.Counter(r for *_, nd, pk in s['files'] for r in nd)
        print('  set %d: %d files, rules (files) %s; profiles %s' % (i, len(s['files']), dict(rc), ', '.join(s['profiles'])))
        for rel, h, p, lb, nd, pk in s['files']:
            print('     %s %s from %s: %s' % (rel, h[:8], lb, ','.join(nd)))
    json.dump(dict(profiles=rep, copies={h: dict(counts=v[0], notes=v[1], pack=v[2]) for h, v in cache.items()}),
              open(os.path.join(out, 'plan.json'), 'w', encoding='utf-8'), indent=1)
    return 0


# ---------------------------------------------------------------- build one copy
def apply_rules(C, rel, path, rules, pk, log):
    """-> (new raw or None, {rule: note}); rules in ORDER, each on the previous result"""
    raw = open(path, 'rb').read(); cur = raw; notes = collections.OrderedDict()
    with pack_first(pk):
        if 'statechart' in rules:
            st = collections.Counter(); lg = []
            new = quiet(C.F().process, rel, C.tmpfile(rel, cur), lg, st)[0]
            notes['statechart'] = '%d truth words changed (%s)' % (st['twin_changed'], '; '.join(
                l.split(': ', 1)[-1] for l in lg if ' changed by the twins' in l and not l.endswith(': 0 truth words, 0 changed by the twins')
                and ', 0 changed by the twins' not in l)[:400])
            if new is not None: cur = new
        steps = [s for s in STRUCT if s in rules]
        if steps:
            lg = []
            new = quiet(C.S().process, rel, C.tmpfile(rel, cur), steps, lg, collections.Counter())[0]
            for s in steps:
                ls = [l for l in lg if l.startswith(s + ' ')]
                notes[s] = ' / '.join(l.split(': ', 1)[-1][:300] for l in ls) or 'nothing to do'
            if new is not None: cur = new
        fs = [s for s in FAULTS if s in rules]
        if fs:
            per, unexp, new = faults(C, rel, cur, fs, True)
            if unexp:
                raise SystemExit('%s: converter fault rule(s) cannot explain %d word(s): %s - nothing is guessed' % (
                    rel, len(unexp), '; '.join(unexp[:5])))
            for s in fs: notes[s] = '%d words' % per.get(s, 0)
            if new is not None: cur = new
    if 'kitdtp' in rules:
        lines = []
        ch = kitdtp(rel, cur, lines)
        if ch:
            D = DW.read(cur, 'le')
            for (k, o), (old, nw, note) in ch.items():
                s = D.sections[k]; d = bytearray(s.data)
                assert bytes(d[o:o + 4]) == old
                d[o:o + 4] = nw; s.data = bytes(d)
            new = D.write('le')
            cur = DW.cdrm_encode(new, 'le') if cur[:4] == b'CDRM' else new
        notes['kitdtp'] = '%d words%s' % (len(ch or {}), (' (' + '; '.join(l.strip() for l in lines)[:300] + ')') if lines else '')
    if 'achievement' in rules:
        import script_missing_native_fix as MN
        rep = []
        new = quiet(MN.process, rel, C.tmpfile(rel, cur), C.nat(), {'achievement'}, rep)[0]
        fx = [l for l in rep if l.startswith('FIX')]
        notes['achievement'] = '%d call(s) neutralised%s' % (len(fx), ('; ' + ' / '.join(l[:120] for l in rep if l.startswith('SKIP'))) if any(
            l.startswith('SKIP') for l in rep) else '')
        if new is not None:
            if cur[:4] != b'CDRM': new = DW.read(new, 'le').write('le')
            cur = new
    if 'scriptclash' in rules:
        import script_clash_fix as SC
        groups, _, ids_in_tree = quiet(SC.plan_files, [(C.tmpfile(rel, cur), rel)], C.res())[0]
        have = {e['key'] for e in SC.load_ids()['ids']}
        newg = [SC.gkey(o, ik) for (o, ik), g in groups.items() if g['derived'] and SC.gkey(o, ik) not in have]
        if newg: raise SystemExit('%s: script clash group(s) %s not in docs/data/script_clash_ids.json - no id is guessed' % (rel, newg))
        lg = []
        mapping = SC.assign(groups, ids_in_tree, lg.append, False)
        new, pairs = SC.fix_raw(cur, mapping, rel, lg.append)
        if new is not None:
            w, o, left = SC.verify(cur, new, pairs)
            if o or left: raise SystemExit('%s: scriptclash verify failed (%d other words, %d references left)' % (rel, o, left))
            cur = new
            notes['scriptclash'] = '%s; %d id words' % (', '.join('%d -> %d' % p for p in pairs), w)
        else: notes['scriptclash'] = 'nothing to do'
    for k, v in notes.items(): log.append('  %s %s: %s' % (k, rel, v))
    return (cur if cur != raw else None), notes


def read_tsv(p):
    rows = []
    for l in open(p, encoding='utf-8').read().splitlines()[1:]:
        if not l.strip(): continue
        rel, h, path, src, rules, pk = l.split('\t')
        # the plan writes the pack LABEL ('pack11 (best of pack10/pack11)'); TRUDLC_PACK_FIRST needs the bare name -
        # a label there matched no pack and silently gave pack10 first (night 06.11., first build of set 3: archived)
        pk = pk.split(' ')[0]
        rows.append(dict(rel=rel, md5=h, path=path, source=src, rules=rules.split(','), pack=None if pk == 'None' else pk))
    return rows


def store_key(r, want):
    """one built / proven copy per (input md5, bare name, rules)"""
    return '%s_%s_%s' % (r['md5'], os.path.basename(r['rel']).lower()[:-4], hashlib.md5(','.join(want).encode()).hexdigest()[:8])


def cmd_build(a):
    rules = (opt(a, '--rules') or ','.join(ORDER)).split(',')
    store = opt(a, '--store')         # DIR of copies already built (shared between the sets of one night)
    tsv, tree = a[1], a[2]
    root = os.path.join(tree, 'mods')
    if os.path.exists(root) and os.listdir(root): raise SystemExit('%s exists and is not empty - never overwrite a tree' % root)
    os.makedirs(root, exist_ok=True)
    C = Ctx(); md5s = ['rel\tinput_md5\toutput_md5\tsource']; fixlog = []
    try:
        for r in read_tsv(tsv):
            if md5b(open(r['path'], 'rb').read()) != r['md5']: raise SystemExit('%s: input md5 changed since the plan' % r['path'])
            want = [x for x in ORDER if x in r['rules'] and x in rules]
            if 'objtex' in r['rules']: want = sorted(set(want) | {'objtex'}, key=ORDER.index)
            log = []
            sk = store_key(r, want)
            if store and os.path.isfile(os.path.join(store, sk, 'notes.json')):
                # the same input copy with the same rules was built before (another set): take that output
                j = json.load(open(os.path.join(store, sk, 'notes.json'), encoding='utf-8'))
                new = open(os.path.join(store, sk, 'out.drm'), 'rb').read() if j['changed'] else None
                if new is not None and md5b(new) != j['output_md5']: raise SystemExit('%s: store copy damaged' % sk)
                notes = collections.OrderedDict(j['notes']); log.append('  (from the store %s)' % sk)
            else:
                new, notes = apply_rules(C, r['rel'], r['path'], want, r['pack'], log)
                if store:
                    os.makedirs(os.path.join(store, sk), exist_ok=True)
                    if new is not None: open(os.path.join(store, sk, 'out.drm'), 'wb').write(new)
                    json.dump(dict(rel=r['rel'], input_md5=r['md5'], rules=want, changed=new is not None,
                                   output_md5=md5b(new) if new is not None else None, notes=list(notes.items())),
                              open(os.path.join(store, sk, 'notes.json'), 'w', encoding='utf-8'), indent=1)
            for l in log: print(l, flush=True)
            if new is None:
                print('%s: NO CHANGE (rules %s)' % (r['rel'], ','.join(want))); continue
            q = os.path.join(root, r['rel']); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
            DW.read(open(q, 'rb').read(), 'le')
            md5s.append('%s\t%s\t%s\t%s' % (r['rel'], r['md5'], md5b(new), r['path']))
            fixlog.append('%s (Xbox %s, md5 %s): %s' % (os.path.basename(r['rel']), r['pack'], r['md5'], ' | '.join(
                '%s: %s' % kv for kv in notes.items())))
            print('%s: written, md5 %s' % (r['rel'], md5b(new)), flush=True)
    finally:
        C.close()
    open(os.path.join(tree, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    open(os.path.join(tree, 'fix_log.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(fixlog) + '\n')
    print('written %d files to %s' % (len(md5s) - 1, root))
    return 0


# ---------------------------------------------------------------- proof
def byte_diff(raw_a, raw_b, allow_ids=None):
    """{(section index, offset): new byte}, header problems; allow_ids {old: new} for type-8 section ids"""
    A, B = DW.read(raw_a, 'le'), DW.read(raw_b, 'le')
    probs = []
    if len(A.sections) != len(B.sections) or A.names != B.names or A.pad != B.pad or (A.ver, A.u0, A.u1) != (B.ver, B.u0, B.u1):
        return None, ['file header / names / section count differ']
    d = {}; ids = {}; rel = {}
    for k, (s, t) in enumerate(zip(A.sections, B.sections)):
        if (s.type, s.flags, s.ver, s.spec, s.pad, len(s.data)) != (t.type, t.flags, t.ver, t.spec, t.pad, len(t.data)):
            probs.append('section %d header differs' % k)
        if bytes(s.reloc) != bytes(t.reloc):
            rel[k] = bytes(t.reloc)          # only `achievement` may drop relocations (checked by the caller)
            d[('reloc', k)] = bytes(t.reloc)
        if s.id != t.id:
            ids[k] = (s.id, t.id)
            if not (s.type == 8 and allow_ids and allow_ids.get(s.id) == t.id): probs.append('section %d id %d -> %d' % (k, s.id, t.id))
        if s.data != t.data:
            a, b = bytes(s.data), bytes(t.data)
            for i in range(len(a)):
                if a[i] != b[i]: d[(k, i)] = b[i]
    return (d, ids), probs


def where(key):
    return 'relocations of section %d' % key[1] if key[0] == 'reloc' else 'section %d +%#x' % key


def cmd_prove(a):
    rules = (opt(a, '--rules') or ','.join(ORDER)).split(',')
    store = opt(a, '--store')
    tsv, tree = a[1], a[2]
    root = os.path.join(tree, 'mods')
    C = Ctx(); nbad = 0; tot = collections.Counter()
    try:
        for r in read_tsv(tsv):
            q = os.path.join(root, r['rel'])
            want = [x for x in ORDER if x in r['rules'] and x in rules]
            if 'objtex' in r['rules']: want = sorted(set(want) | {'objtex'}, key=ORDER.index)
            raw = open(r['path'], 'rb').read()
            if not os.path.exists(q):
                print('%s: not in the tree (rules %s) - %s' % (r['rel'], ','.join(want), 'checked below')); out = raw
            else: out = open(q, 'rb').read()
            sk = store_key(r, want); pj = os.path.join(store, sk, 'prove.json') if store else None
            if pj and os.path.isfile(pj):
                j = json.load(open(pj, encoding='utf-8'))
                if j['output_md5'] == md5b(out):
                    print(j['line'] + ' (proof from the store %s)' % sk, flush=True)
                    for p in j['probs']: print('    ', p)
                    for k, v in j['per'].items(): tot['words_' + k] += v
                    tot['files'] += 1; nbad += 1 if j['probs'] else 0
                    continue
            probs = []
            # the bytes each rule changes ALONE on the input
            union = {}; per = collections.Counter(); idmap = {}
            for rule in want:
                new, notes = apply_rules(C, r['rel'], r['path'], [rule], r['pack'], [])
                if new is None: continue
                if rule == 'scriptclash':
                    m = [x for x in notes['scriptclash'].split(';')[0].split(', ') if '->' in x]
                    idmap.update({int(x.split(' -> ')[0]): int(x.split(' -> ')[1]) for x in m})
                dd, pr = byte_diff(raw, new, idmap)
                if dd is None: probs += ['%s alone: %s' % (rule, p) for p in pr]; continue
                for key, v in dd[0].items():
                    if key[0] == 'reloc' and rule != 'achievement':
                        probs.append('%s alone changes the relocations of section %d' % (rule, key[1]))
                    if key in union and union[key][1] != v: probs.append('rules %s and %s disagree at %s' % (union[key][0], rule, where(key)))
                    # two rules setting the same byte to the same value (e.g. animfx and the re-check animlist) agree
                    if key in union and union[key][0] != rule and union[key][1] == v: tot['shared_' + union[key][0] + '+' + rule] += 1
                    union[key] = (rule, v)
                per[rule] = len({(k, i & ~3) for k, i in dd[0] if k != 'reloc'})
            dd, pr = byte_diff(raw, out, idmap)
            probs += pr
            if dd is not None:
                got = dd[0]
                extra = [k for k in got if k not in union or union[k][1] != got[k]]
                miss = [k for k in union if k not in got]
                if extra: probs.append('%d bytes changed that no single rule changes (first %s)' % (len(extra), where(extra[0])))
                if miss: probs.append('%d bytes a single rule changes are not changed (first %s)' % (len(miss), where(miss[0])))
            # re-check of the output by every rule
            p2 = C.tmpfile(r['rel'], out, 'out')
            cnt, notes, pk = analyze(C, r['rel'], p2, want)
            left = left_of(cnt)
            if left: probs.append('re-check of the output: %s' % left)
            if r['pack'] and not pk: probs.append('re-check found no Xbox source (the rules were not re-checked)')
            missing = [x for x in want if x not in cnt and x != 'objtex'] + (['objtex'] if 'objtex' in want and 'texlist' not in cnt else [])
            if missing: probs.append('re-check did not run %s' % missing)
            for k, v in per.items(): tot['words_' + k] += v
            tot['files'] += 1
            line = '%s: rules %s, words per rule %s, other bytes %s, headers / relocations %s, re-check %s -> %s' % (
                r['rel'], ','.join(want), dict(per), 'none' if dd and not [k for k in dd[0] if k not in union] else 'SEE BELOW',
                'identical (relocations only where achievement drops them)' if not pr else 'DIFFER',
                left_of(cnt) or 'all 0', 'OK' if not probs else 'FAIL')
            print(line, flush=True)
            for p in probs: print('    ', p)
            if pj:
                os.makedirs(os.path.dirname(pj), exist_ok=True)
                json.dump(dict(output_md5=md5b(out), line=line, probs=probs, per=dict(per)), open(pj, 'w', encoding='utf-8'), indent=1)
            if probs: nbad += 1
    finally:
        C.close()
    print('TOTAL %s, files with problems %d' % (dict(tot), nbad))
    print('prove: %s' % ('ok' if not nbad else 'FAIL'))
    return 1 if nbad else 0


# ---------------------------------------------------------------- verify the profile with the tree last
def cmd_verify(a):
    import profile_fix_plan as PFP
    profiles = []
    for g in opt(a, '--profile', True): profiles += sorted(glob.glob(g)) or [g]
    base = opt(a, '--base'); PFP.BASE_UNDO = opt(a, '--base-undo'); tree = opt(a, '--tree'); tsv = opt(a, '--tsv')
    rules = (opt(a, '--rules') or ','.join(ORDER)).split(',')
    cfile = opt(a, '--cache')     # read-only use of the plan cache is safe: a copy's md5 + name fix its counts
    disk = json.load(open(cfile, encoding='utf-8')) if cfile and os.path.exists(cfile) else {}
    cfile = opt(a, '--cache-write') or None
    paths_out = opt(a, '--paths-out')   # FILE ('{profile}' = profile name)
    root = os.path.join(tree, 'mods')
    fm = PFP.tree_files(root, [])
    ins = {r['rel'].lower(): r['md5'] for r in read_tsv(tsv)}
    fix = dict(name=os.path.basename(os.path.normpath(tree)), root=root, files=fm, inputs={k: ins.get(k) for k in fm},
               outputs={k: PFP.md5(p) for k, p in fm.items()})
    C = Ctx(); nbad = 0; cache = {}
    try:
        for pp in profiles:
            pn = os.path.basename(pp)[:-5]
            trees, files = final_set(PFP, pp, base)
            c = PFP.classify(trees, files, base, fix)
            fin = PFP.install(trees + [(fix['name'], fm)], files, base)
            if paths_out:   # the final installed .drm paths (input of the list-capable check tools)
                with open(paths_out.replace('{profile}', pn), 'w', encoding='utf-8', newline='\n') as f:
                    for rel, (p, label) in sorted(fin.items()):
                        if rel.endswith('.drm'): f.write(os.path.abspath(p).replace('\\', '/') + '\n')
            left = collections.Counter(); where = collections.defaultdict(list)
            for rel, (p, label) in sorted(fin.items()):
                if not rel.endswith('.drm') or os.path.basename(rel) == 'generalbank.drm': continue
                h = PFP.md5(p)
                if h not in cache:
                    dk = '%s|%s|%s' % (h, os.path.basename(rel).lower(), 'all' if STATECHART_ALL else 'thrall')
                    e = disk.get(dk)
                    if e and all(x in e['rules'] for x in rules):
                        cache[h] = collections.OrderedDict(e['counts'])
                    else:
                        cache[h] = analyze(C, rel, p, rules)[0]
                        if cfile:
                            disk[dk] = dict(rules=list(rules), counts=list(cache[h].items()), notes=[], pack=None)
                            json.dump(disk, open(cfile, 'w', encoding='utf-8'))
                for k, v in left_of(cache[h]).items():
                    left[k] += 1; where[k].append(os.path.basename(rel))
            ok = not left and not c['other'] and not c['added'] and not c['shadowed'] and len(c['intended']) == len(fm)
            print('PROFILE %s + %s: intended %d / %d, same %d, other %d %s, added %d, shadowed %d; rule checks of the final set: %s -> %s' % (
                pn, fix['name'], len(c['intended']), len(fm), len(c['same']), len(c['other']), c['other'] or '',
                len(c['added']), len(c['shadowed']), dict(left) or 'all 0', 'OK' if ok else 'FAIL'), flush=True)
            for k, v in where.items(): print('    %s left in %s' % (k, ', '.join(v[:12])))
            if not ok: nbad += 1
    finally:
        C.close()
    print('verify: %s' % ('ok' if not nbad else 'FAIL (%d profiles)' % nbad))
    return 1 if nbad else 0


def main(a):
    if not a: sys.exit(__doc__)
    global STATECHART_ALL
    if '--statechart-all' in a: STATECHART_ALL = True; a = [x for x in a if x != '--statechart-all']
    d = opt(a, '--drop')
    if d: DROP.extend(d.split(','))
    if a[0] == 'plan': return cmd_plan(a[1:])
    if a[0] == 'build' and len([x for x in a if not x.startswith('--')]) >= 3: return cmd_build(a)
    if a[0] == 'prove': return cmd_prove(a)
    if a[0] == 'verify': return cmd_verify(a[1:])
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
