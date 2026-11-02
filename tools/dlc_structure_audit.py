"""Structure audit of a converted DLC DRM against its Xbox original (2026-11-01, Befund-Felsrinne.md "Structure audit
of the DLC 2 player and pipeline steps"). Read-only unless --out.

Why: every live test of the DLC 2 player (doppelganger_casual, object 857) crashed on the next misconverted structure
(state records, event lists, model record list, shader slots, anim event lists), each found after a crash. This tool
looks at EVERY section of a converted DRM up front.

Method (generalises tools/statechart_twins.py from the chart families to every section type):
* Sections Xbox <-> PC are paired by (type, id) through the converter's id map (tools/dlc_generic.DlcIds: base map,
  then the DLC table; the k-th copy of an id with the k-th copy), then by position among the leftovers of the same
  (type, size, reloc size).
* A section is split into blocks at its internal relocation targets. Block shape = (size, relocated word offsets,
  family). Families: the state-chart families of tools/statechart_corpus.py (chart / table / alist), 'animfx' (anim
  event list, tools/animfx_list_fix.walk), 'objev' (object event list: the DTP a type-11 object names at +4), 'model'
  (the DTP an object names at +8), else 't<type>'.
* Base corpus = every base Xbox / PC DRM pair of work/generic/pairs.pkl (section pairs of tools/generic_ids
  .section_matches, same size, data kept for types 0 1 2 3 4 7 8 10 11 13). Only base blocks whose shape (or array
  element key) also occurs in the target are kept. Truth levels as in statechart_twins (exact / value / eexact /
  evalue): a PC word is known only when every base observation of the key gives the same PC bytes and they are a byte
  permutation of the Xbox word (re-numbered ids are never copied).
* Leave-one-DRM-out precision over the kept base observations, per family and level ('xval', every 5th base DRM by
  default); 'check' applies only the levels / families with >= --min-n predictions and >= --min-prec % (table in
  the report).
* A PC word that differs from the truth is "wrong" only when it is a byte permutation of the Xbox word (a byte-order
  error); a PC word that is no byte order of the Xbox word was re-authored by the converter or a later fix (material
  slot remaps, script strings, ...) and is reported as a "conflict", never changed. Proven record layouts
  (tools/dlc_struct_fixes.py steps) run after the twins and win where they disagree.
* Sections whose PC size differs from the Xbox size (media re-encoded by the converter: textures, meshes, shader
  libraries, sounds; or a layout change) are not word-checkable and are listed per type. Size-kept sections whose
  root-block shape has a size change in the base pairs are flagged as layout-shift candidates (the class of the model
  record list, test 48d).

Modes (from the repository root; ../bin/pyt only):
  ../bin/pyt -t 5400 tools/dlc_structure_audit.py check XBOX.drm PC.drm [XBOX2.drm PC2.drm ...] [--report R.txt] [--xval-every 5]
        [--out OUT_DIR] [--list N] [--min-prec 99.9] [--min-n 20] [--allowed-from EARLIER_REPORT.txt]
      all target pairs share one corpus pass (~10 min truth tables + ~10 min precision); --out writes every PC file
      with the wrong truth words set (OUT_DIR/<basename of PC>), relocated words untouched, read back;
      --allowed-from takes the precision table of an earlier report of the same targets instead of the xval pass
  ../bin/pyt -t 600 tools/dlc_structure_audit.py filter XBOX.drm BEFORE.drm AFTER.drm OUT.drm
      keep only AFTER's byte-order corrections (for --out files of the first 2026-11-01 run, before 'conflict')
"""
import sys, os, struct, collections, pickle, bisect, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import statechart_twins as ST
import statechart_corpus as CO
import animfx_list_fix as AF

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
LEVELS = ST.LEVELS
T0 = time.time()


def log(*a):
    print('[%6.0fs]' % (time.time() - T0), *a, flush=True)


# ------------------------------------------------------------------------------------------------ blocks
class Blocks(ST.Chart):
    """ST.Chart with a fast shape() (bisect on the sorted relocated offsets instead of a scan of every word)"""
    def __init__(self, d, reloc, e):
        ST.Chart.__init__(self, d, reloc, e)
        self.smask = sorted(self.mask)

    def shape(self, b, extra=()):
        n = self.end[b] - b
        i = bisect.bisect_left(self.smask, b); j = bisect.bisect_left(self.smask, b + n - 3)
        rel = set(o - b for o in self.smask[i:j] if (o - b) % 4 == 0)
        if extra:
            if getattr(self, '_exid', None) is not extra:
                self._exid = extra; self._ex = sorted(extra)
            ex = self._ex
            i = bisect.bisect_left(ex, b); j = bisect.bisect_left(ex, b + n - 3)
            rel.update(o - b for o in ex[i:j] if (o - b) % 4 == 0)
        return (n, tuple(sorted(rel)))


def obj_refs(secs, e):
    """{dtp id: 'objev' | 'model'} named by the type-11 objects at +4 / +8 (secs: dicts)"""
    f = '>' if e == 'be' else '<'
    out = {}
    for s in secs:
        if s['type'] != 11 or s['data'] is None or len(s['data']) < 12: continue
        ids = R.parse(bytes(s['reloc']), e).id_offsets()
        if ids.get(4) == 7: out.setdefault(struct.unpack_from(f + 'I', s['data'], 4)[0], 'objev')
        if ids.get(8) == 7: out.setdefault(struct.unpack_from(f + 'I', s['data'], 8)[0], 'model')
    return out


def family(s, e, refs):
    t = s['type']
    if t != 7: return 't%d' % t
    d = bytes(s['data'])
    f = CO.family(d, s['id'], s['reloc'], e)
    if f: return f
    if AF.walk(d, e) is not None: return 'animfx'
    return refs.get(s['id'], 't7')


def dicts(D):
    return [{'i': k, 'type': s.type, 'id': s.id, 'size': len(s.data), 'data': s.data, 'reloc': s.reloc}
            for k, s in enumerate(D.sections)]


# ------------------------------------------------------------------------------------------------ target pairing
def pair_target(sx, sp, ids):
    """[(xbox dict, pc dict, how)] for one target DRM pair"""
    used = set(); out = []
    pc_by = collections.defaultdict(list)
    for s in sp: pc_by[s['type'], s['id']].append(s)
    seen = collections.Counter()
    rest = []
    for s in sx:
        k = seen[s['type'], s['id']]; seen[s['type'], s['id']] += 1
        hit = None
        for pid in (s['id'], ids(s['type'], s['id'])):
            c = [p for p in pc_by.get((s['type'], pid), []) if p['i'] not in used]
            if c and len(c) > 0:
                cc = [p for p in c if p['size'] == s['size']] or c
                hit = cc[0]; break
        if hit is not None:
            used.add(hit['i']); out.append((s, hit, 'id'))
        else:
            rest.append(s)
    gp = collections.defaultdict(list)
    for p in sp:
        if p['i'] not in used: gp[p['type'], p['size'], len(p['reloc'])].append(p)
    for s in rest:
        g = gp.get((s['type'], s['size'], len(s['reloc'])))
        if g: p = g.pop(0); used.add(p['i']); out.append((s, p, 'pos'))
        else: out.append((s, None, 'none'))
    return out, [p for p in sp if p['i'] not in used]


# ------------------------------------------------------------------------------------------------ corpus
class GTruth(ST.Truth):
    def __init__(self, obs):
        self.min_slot, self.with_slot = 3, False
        self.exact = collections.defaultdict(collections.Counter)
        self.value = collections.defaultdict(collections.Counter)
        self.slot = collections.defaultdict(collections.Counter)
        self.eexact = collections.defaultdict(collections.Counter)
        self.evalue = collections.defaultdict(collections.Counter)
        self.obs = obs
        for n, sh, xc, pc in obs: self.add(sh, xc, pc, 1)

    def add(self, sh, xc, pc, k):
        """ST.Truth.add without the byte-order invariant words (all four bytes equal: no evidence, never checked)"""
        self.exact[sh, xc][pc] += k
        rel = set(sh[1])
        for r in range(0, sh[0] - 3, 4):
            if r in rel: continue
            xw = xc[r:r + 4]
            if xw == xw[:1] * 4: continue
            pw = pc[r:r + 4]
            self.value[sh, r, xw][pw if ST.is_perm(xw, pw) else ST.REAUTH] += k
        ek = ST.elem_key(sh)
        if ek:
            p = ek[1]; erel = set(ek[2])
            for e in range(0, sh[0], p):
                xe, pe = xc[e:e + p], pc[e:e + p]
                self.eexact[ek, xe][pe] += k
                for r in range(0, p, 4):
                    if r in erel: continue
                    xw = xe[r:r + 4]
                    if xw == xw[:1] * 4: continue
                    pw = pe[r:r + 4]
                    self.evalue[ek, r, xw][pw if ST.is_perm(xw, pw) else ST.REAUTH] += k


def base_corpus(want_sh, want_ek, want_root):
    """observations [(drm index, shape, xbox content, pc content)] of the base pairs for the wanted shapes / element
    keys; root statistics {(family, root shape): Counter(same / differs)} for the wanted root shapes"""
    from generic_cache import load_pairs
    from convert_generic import IdMapper
    from generic_ids import section_matches
    P = load_pairs(patch=False)
    idm = IdMapper().m
    log('base pairs loaded: %d' % len(P))
    obs = []; roots = collections.defaultdict(collections.Counter); st = collections.Counter()
    for n, nm in enumerate(sorted(P)):
        x, p = P[nm]
        if x is None or not isinstance(p, tuple): continue
        sx, sp = x[1], p[1]
        rx, rp = obj_refs(sx, 'be'), obj_refs(sp, 'le')
        st['drms'] += 1
        for i, j, how in section_matches(sx, sp, idm):
            a, b = sx[i], sp[j]
            if a['data'] is None or b['data'] is None or a['type'] != b['type']: continue
            fam = family(a, 'be', rx)
            X = Blocks(a['data'], a['reloc'], 'be')
            rsh = X.shape(0) + (fam,)
            if rsh in want_root: roots[rsh]['same' if a['size'] == b['size'] else 'differs'] += 1
            if a['size'] != b['size']: st['size_differs'] += 1; continue
            st['sections'] += 1
            Pc = Blocks(b['data'], b['reloc'], 'le')
            for xb, pb in ST.pair_blocks(X, Pc).items():
                sx_ = X.shape(xb)
                if X.end[xb] - xb != Pc.end[pb] - pb: continue
                sh = sx_ + (fam,)
                if sh not in want_sh and ST.elem_key(sh) not in want_ek: continue
                if sx_ != Pc.shape(pb): continue
                obs.append((n, sh, X.content(xb, sx_), Pc.content(pb, sx_)))
                st['blocks'] += 1
        if n % 100 == 0: log('  %d / %d DRMs, %d observations' % (n, len(P), len(obs)))
    del P
    log('corpus: %s' % dict(st))
    return obs, roots


def xval(T, every=1):
    """leave-one-DRM-out precision per (family, level) over the kept observations (every: only every n-th base DRM
    is left out and predicted - a sample, to keep the run time down)"""
    st = collections.Counter()
    groups = collections.defaultdict(list)
    for o in T.obs:
        if o[0] % every == 0: groups[o[0]].append(o)
    for n, obs in groups.items():
        for _, sh, xc, pc in obs: T.add(sh, xc, pc, -1)
        for _, sh, xc, pc in obs:
            for r, (pw, kind) in T.block(sh, xc).items():
                if ST.invariant(xc[r:r + 4]): continue
                st[sh[2], kind, pc[r:r + 4] == pw] += 1
        for _, sh, xc, pc in obs: T.add(sh, xc, pc, 1)
    return st


# ------------------------------------------------------------------------------------------------ check
def classify(xw, pw):
    for c, q in (('raw', (0, 1, 2, 3)), ('u32', (3, 2, 1, 0)), ('u16', (1, 0, 3, 2)), ('u8u8u16', (0, 1, 3, 2)),
                 ('u16u8u8', (1, 0, 2, 3))):
        if bytes(xw[i] for i in q) == pw: return c
    return 'other'


def check_pair(T, tp, allowed, nlist, rep):
    """per target pair: stats per family; {pc section index: {offset: word}} of the wrong words"""
    st = collections.Counter(); fixes = {}
    sizes = collections.defaultdict(collections.Counter)
    for xs, ps, fam, X, Pc in tp['blocks']:
        if ps is None: sizes[xs['type']]['no_pc_twin'] += 1; continue
        if xs['size'] != ps['size']: sizes[xs['type']]['size_differs'] += 1; continue
        sizes[xs['type']]['same_size'] += 1
        tw = ST.truth_words(T, X, Pc.mask, fam)
        pd = ps['data']; xd = xs['data']
        key = (xs['type'], fam)
        nwrong = 0
        for o in range(0, len(xd) - 3, 4):
            if o in X.mask or o in Pc.mask: st[key, 'reloc'] += 1; continue
            xw = xd[o:o + 4]
            if ST.invariant(xw):
                st[key, 'invariant'] += 1
                v = tw.get(o)
                if v is not None and pd[o:o + 4] != v[0]: st[key, 'invariant_changed'] += 1
                continue
            v = tw.get(o)
            if v is None or (fam, v[1]) not in allowed:
                st[key, 'unprovable'] += 1
                if pd[o:o + 4] != xw and classify(xw, pd[o:o + 4]) == 'other': st[key, 'unprovable_renumbered'] += 1
                continue
            st[key, 'checked'] += 1
            if pd[o:o + 4] == v[0]: continue
            cl = classify(xw, pd[o:o + 4])
            st[key, 'conv_' + cl] += 1
            if cl == 'other':
                # the PC word is no byte order of the Xbox word: a value the converter or a later fix re-authored
                # (material slot remaps, script strings, fixed chart fields) - a conflict, not a byte-order error
                st[key, 'conflict'] += 1
            else:
                st[key, 'wrong'] += 1; st[key, 'wrong_' + v[1]] += 1; nwrong += 1
                fixes.setdefault(ps['i'], {})[o] = v[0]
            if st[key, 'shown'] < nlist:
                st[key, 'shown'] += 1
                rep.append('     %s DTP/sec %d:%d +0x%05x (%s) Xbox %s PC %s (%s) truth %s' % (
                    tp['name'], xs['type'], ps['id'], o, v[1], xw.hex(), pd[o:o + 4].hex(), classify(xw, pd[o:o + 4]), v[0].hex()))
        if nwrong: st[key, 'sections_wrong'] += 1
        st[key, 'sections'] += 1
    return st, fixes, sizes


def load_target(xpath, ppath, ids):
    XD = DW.read(open(xpath, 'rb').read(), 'be'); PD = DW.read(open(ppath, 'rb').read(), 'le')
    sx, sp = dicts(XD), dicts(PD)
    pairs, pc_only = pair_target(sx, sp, ids)
    rx = obj_refs(sx, 'be')
    blocks = []
    for xs, ps, how in pairs:
        fam = family(xs, 'be', rx)
        X = Blocks(xs['data'], xs['reloc'], 'be')
        Pc = Blocks(ps['data'], ps['reloc'], 'le') if ps is not None else None
        blocks.append((xs, ps, fam, X, Pc))
    return dict(name=os.path.basename(ppath), xpath=xpath, ppath=ppath, PD=PD, blocks=blocks, pc_only=pc_only,
                how=collections.Counter(h for _, _, h in pairs))


def wanted(tps):
    sh, ek, root = set(), set(), set()
    for tp in tps:
        for xs, ps, fam, X, Pc in tp['blocks']:
            root.add(X.shape(0) + (fam,))
            if ps is None or xs['size'] != ps['size']: continue
            for b in X.starts:
                s = X.shape(b, extra=Pc.mask) + (fam,)
                sh.add(s)
                e = ST.elem_key(s)
                if e: ek.add(e)
    return sh, ek, root


def cmd_filter(xpath, before, after, out):
    """keep only the changed words of AFTER (a --out file) whose BEFORE word is a byte permutation of the Xbox word
    (byte-order errors); 'other' words (re-authored by the converter or a later fix) go back to BEFORE. For --out
    files written before 'check' learned to leave such conflicts alone (2026-11-01 first run)."""
    import dlc_generic as DG
    XD = DW.read(open(xpath, 'rb').read(), 'be'); BD = DW.read(open(before, 'rb').read(), 'le')
    raw_a = open(after, 'rb').read(); AD = DW.read(raw_a, 'le')
    assert len(BD.sections) == len(AD.sections)
    pairs, _ = pair_target(dicts(XD), dicts(BD), DG.DlcIds())
    xof = {ps['i']: xs for xs, ps, how in pairs if ps is not None}
    st = collections.Counter()
    for i, (b, a) in enumerate(zip(BD.sections, AD.sections)):
        if b.data == a.data: continue
        assert len(b.data) == len(a.data) and b.reloc == a.reloc
        xs = xof[i]; xd = xs['data']; nd = bytearray(a.data)
        for o in range(0, len(b.data) - 3, 4):
            if b.data[o:o + 4] == a.data[o:o + 4]: continue
            if classify(xd[o:o + 4], b.data[o:o + 4]) == 'other':
                nd[o:o + 4] = b.data[o:o + 4]; st['reverted (conflict)', b.type] += 1
            else: st['kept (byte order)', b.type] += 1
        a.data = bytes(nd)
    raw = AD.write('le')
    if raw_a[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
    open(out, 'wb').write(raw); DW.read(open(out, 'rb').read(), 'le')
    print('words by (kind, section type): %s' % dict(st))
    print('written %s (%d bytes, read back ok)' % (out, len(raw)))


def main(argv):
    if argv and argv[0] == 'filter': return cmd_filter(*argv[1:5])
    if not argv or argv[0] != 'check': raise SystemExit(__doc__)
    argv = argv[1:]
    opt = {}
    for k in ('--report', '--out', '--list', '--min-prec', '--min-n', '--allowed-from', '--xval-every'):
        if k in argv: i = argv.index(k); opt[k] = argv[i + 1]; del argv[i:i + 2]
    nlist = int(opt.get('--list', 8)); min_prec = float(opt.get('--min-prec', 99.9)); min_n = int(opt.get('--min-n', 20))
    import dlc_generic as DG
    ids = DG.DlcIds()
    tps = [load_target(argv[k], argv[k + 1], ids) for k in range(0, len(argv), 2)]
    rep = []
    def out(s=''):
        print(s, flush=True); rep.append(s)
    for tp in tps:
        log('target %s: %d pairs (%s), PC-only sections %d' % (tp['name'], len(tp['blocks']), dict(tp['how']), len(tp['pc_only'])))
    want_sh, want_ek, want_root = wanted(tps)
    log('wanted shapes %d, element keys %d, root shapes %d' % (len(want_sh), len(want_ek), len(want_root)))
    obs, roots = base_corpus(want_sh, want_ek, want_root)
    T = GTruth(obs)
    log('truth tables: exact %d, value %d, eexact %d, evalue %d' % (len(T.exact), len(T.value), len(T.eexact), len(T.evalue)))
    allowed = set()
    if '--allowed-from' in opt:
        # the precision table of an earlier report of the same targets (lines '  family level right wrong prec yes')
        xv = collections.Counter()
        for l in open(opt['--allowed-from'], encoding='utf-8'):
            p = l.split()
            if len(p) == 6 and p[1] in LEVELS and p[5] in ('yes', 'no'):
                xv[p[0], p[1], True] = int(p[2]); xv[p[0], p[1], False] = int(p[3])
        log('precision table read from %s' % opt['--allowed-from'])
    else:
        xv = xval(T, int(opt.get('--xval-every', 5)))
        log('cross-validation done')
    # precision per (family, level): a level is used for a family only with >= min_n predictions and >= min_prec %
    fams = sorted({k[0] for k in xv})
    out('Leave-one-DRM-out precision over the base observations of the target shapes (byte-order-sensitive words):')
    out('  %-8s %-7s %9s %7s %8s  used' % ('family', 'level', 'right', 'wrong', 'prec %'))
    for f in fams:
        for lv in LEVELS:
            ok, bad = xv[f, lv, True], xv[f, lv, False]
            if not ok + bad: continue
            prec = 100.0 * ok / (ok + bad)
            use = ok + bad >= min_n and prec >= min_prec
            if use: allowed.add((f, lv))
            out('  %-8s %-7s %9d %7d %8.3f  %s' % (f, lv, ok, bad, prec, 'yes' if use else 'no'))
    for tp in tps:
        out(); out('== %s (Xbox %s)' % (tp['ppath'], tp['xpath']))
        det = []
        st, fixes, sizes = check_pair(T, tp, allowed, nlist, det)
        tp['fixes'] = fixes
        out('  sections by type: ' + ', '.join('%d: %s' % (t, dict(c)) for t, c in sorted(sizes.items())))
        out('  PC-only sections: %s' % dict(collections.Counter(p['type'] for p in tp['pc_only'])))
        out('  %-4s %-8s %8s %8s %8s %8s %6s %8s %6s %6s  converter wrote (wrong + conflict words)' % (
            'type', 'family', 'sections', 'words', 'checked', 'wrong', 'confl', 'unprov', 'secbad', 'renum'))
        keys = sorted({k[0] for k in st})
        tot = collections.Counter()
        for key in keys:
            words = sum(st[key, k] for k in ('reloc', 'invariant', 'unprovable', 'checked'))
            conv = {k[1][5:]: v for k, v in st.items() if k[0] == key and isinstance(k[1], str) and k[1].startswith('conv_')}
            out('  %-4d %-8s %8d %8d %8d %8d %8d %6d %6d %6d  %s' % (
                key[0], key[1], st[key, 'sections'], words, st[key, 'checked'], st[key, 'wrong'], st[key, 'conflict'], st[key, 'unprovable'],
                st[key, 'sections_wrong'], st[key, 'unprovable_renumbered'], conv))
            for k in ('sections', 'checked', 'wrong', 'conflict', 'unprovable', 'invariant', 'reloc', 'sections_wrong'): tot[k] += st[key, k]
        out('  total: %s' % dict(tot))
        # per-section list of the wrong words
        bysec = sorted(((len(v), i) for i, v in fixes.items()), reverse=True)
        out('  sections with wrong words: %d' % len(bysec))
        for nw, i in bysec[:60]:
            s = tp['PD'].sections[i]
            fam = next(f for xs, ps, f, X, Pc in tp['blocks'] if ps is not None and ps['i'] == i)
            out('     section %4d type %2d id %6d %-7s %5d wrong words' % (i, s.type, s.id, fam, nw))
        for l in det: out(l)
        # layout-shift candidates: same size on the target, but the base pairs of the same root shape change size
        cand = []
        for xs, ps, fam, X, Pc in tp['blocks']:
            if ps is None or xs['size'] != ps['size']: continue
            rsh = X.shape(0) + (fam,)
            c = roots.get(rsh)
            if c and c['differs'] and len(rsh[1]) >= 1: cand.append((xs['type'], ps['id'], fam, xs['size'], dict(c)))
        out('  layout-shift candidates (PC kept the Xbox size, base pairs of the same root block change size): %d' % len(cand))
        for c in cand[:40]: out('     type %d id %d %s size %d base root pairs %s' % c)
    if '--out' in opt:
        os.makedirs(opt['--out'], exist_ok=True)
        for tp in tps:
            PD = tp['PD']; n = 0
            for i, fx in tp['fixes'].items():
                b = bytearray(PD.sections[i].data)
                for o, w in fx.items(): b[o:o + 4] = w; n += 1
                PD.sections[i].data = bytes(b)
            raw = PD.write('le')
            if open(tp['ppath'], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
            op = os.path.join(opt['--out'], tp['name'])
            open(op, 'wb').write(raw)
            chk = DW.read(open(op, 'rb').read(), 'le')
            assert len(chk.sections) == len(PD.sections)
            assert all(a.data == b.data and a.reloc == b.reloc for a, b in zip(chk.sections, PD.sections))
            out('written %s: %d words set in %d sections, %d bytes, read back ok' % (op, n, len(tp['fixes']), len(raw)))
    if '--report' in opt:
        open(opt['--report'], 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
        log('report %s' % opt['--report'])


if __name__ == '__main__':
    main(sys.argv[1:])
