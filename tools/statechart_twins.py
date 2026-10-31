"""Ground truth for converted state-chart-like DTPs from the base game's Xbox/PC pairs ("twins"; finding 43, state
chart conversion). Library + command line; read-only unless --out is given.

Corpus: tools/statechart_corpus.py (615 base chart pairs, 20 record tables, 836 id lists; Xbox layer2 / title
update vs PC bigfile / patch). In every pair the blocks (relocation target up to the next target) are paired along
the pointer graph; a pair counts when both blocks have the same size and the same relocated word offsets. Shape =
(size, relocated offsets, DTP family) - keys never mix families.
  exact   key (shape, Xbox block bytes with relocated words zeroed) -> PC block bytes
  value   key (shape, word offset, Xbox word) -> PC word
  eexact  arrays (elem_key: >= 2 elements of p bytes, same relocated offsets in each): key (family, p, element
          relocated offsets, Xbox element bytes) -> PC element bytes - arrays of different length share them
  evalue  key (family, p, element relocated offsets, offset in the element, Xbox word) -> PC word
A key is usable only when every base observation gives the same PC bytes, and (per word) the PC word is a byte
permutation of the Xbox word (u32 swap, two u16 swaps, raw, u16 + two bytes, two bytes + u16): re-authored values
are never copied. Levels in the order above, the first that answers wins. This is a translation by the base game's
own data: the same Xbox bytes in the same block shape are converted the way the base game's PC build has them.
Leave-one-pair-out precision 2026-10-31 (3 137 184 byte-order-sensitive words): exact 2 793 343 right / 7 wrong,
value 100 693 / 20, eexact 1 275 / 0, evalue 957 / 0. A further level, slot (shape, offset) -> the byte order all
observations agree on, is only reported by 'loo --levels ...,slot': 5 584 / 126 (97.8 %) - too low, not applied.

Modes:
  loo CORPUS.pkl [--levels exact,value,eexact,evalue,slot]
                            leave-one-pair-out precision: the blocks of each base pair predicted from all other pairs
  check CORPUS.pkl XBOX.drm SID BEFORE.drm AFTER.drm [--list N] [--tu TU_IMAGE]
                            truth words of DTP SID: ok->ok / ok->bad / bad->ok / bad->bad, words without truth
  fix CORPUS.pkl XBOX.drm PC.drm SID[,SID] --out OUT.drm
                            set every truth word of the DTPs (relocated words untouched)
"""
import sys, os, pickle, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PERMS = ((0, 1, 2, 3), (3, 2, 1, 0), (1, 0, 3, 2), (1, 0, 2, 3), (0, 1, 3, 2))
REAUTH = b'reauthored'
LEVELS = ('exact', 'value', 'eexact', 'evalue')        # applied levels (slot: report only)


class Chart:
    def __init__(self, d, reloc, e):
        r = R.parse(bytes(reloc), e)
        self.d = bytes(d); self.internal = dict(r.internal)
        self.mask = set(r.pointer_offsets()) | set(r.id_offsets())
        self.starts = sorted(set(self.internal.values()) | {0})
        self.end = {a: (self.starts[k + 1] if k + 1 < len(self.starts) else len(self.d)) for k, a in enumerate(self.starts)}
        self.fields = collections.defaultdict(dict)
        for o, t in self.internal.items():
            b = self.starts[bisect.bisect_right(self.starts, o) - 1]
            self.fields[b][o - b] = t

    def shape(self, b, extra=()):
        n = self.end[b] - b
        return (n, tuple(r for r in range(0, n - 3, 4) if b + r in self.mask or b + r in extra))

    def content(self, b, sh):
        x = bytearray(self.d[b:self.end[b]])
        for r in sh[1]: x[r:r + 4] = b'\0\0\0\0'
        return bytes(x)


def pair_blocks(X, P):
    pairs = {0: 0}; order = [0]; i = 0
    while i < len(order):
        xb = order[i]; i += 1; pb = pairs[xb]
        pf = P.fields.get(pb, {})
        for f, t in sorted(X.fields.get(xb, {}).items()):
            if t in pairs or f not in pf: continue
            pairs[t] = pf[f]; order.append(t)
    return pairs


def is_perm(xw, pw):
    return any(bytes(xw[j] for j in q) == pw for q in PERMS)


def observations(corpus):
    """yield (pair index, shape, xbox content, pc content) for every same-shape block pair of the corpus; the shape
    = (size, relocated word offsets, DTP family): keys never mix the families (an id-list block of the same size
    must not decide a chart block)"""
    for n, c in enumerate(corpus):
        X = Chart(c['x'], c['xr'], 'be'); P = Chart(c['p'], c['pr'], 'le')
        for xb, pb in pair_blocks(X, P).items():
            sx = X.shape(xb)
            if X.end[xb] - xb != P.end[pb] - pb or sx != P.shape(pb): continue
            yield n, sx + (c['family'],), X.content(xb, sx), P.content(pb, sx)


class Truth:
    def __init__(self, corpus, min_slot=3, with_slot=False):
        self.min_slot, self.with_slot = min_slot, with_slot
        self.exact = collections.defaultdict(collections.Counter)
        self.value = collections.defaultdict(collections.Counter)
        self.slot = collections.defaultdict(collections.Counter)
        self.eexact = collections.defaultdict(collections.Counter)     # array elements (see period())
        self.evalue = collections.defaultdict(collections.Counter)
        self.obs = list(observations(corpus))
        for n, sh, xc, pc in self.obs: self.add(sh, xc, pc, 1)

    def add(self, sh, xc, pc, k):
        self.exact[sh, xc][pc] += k
        for r in range(0, sh[0] - 3, 4):
            if r in sh[1]: continue
            xw = xc[r:r + 4]; pw = pc[r:r + 4]
            self.value[sh, r, xw][pw if is_perm(xw, pw) else REAUTH] += k
            if self.with_slot and not invariant(xw):        # slot level: the byte orders that explain this observation
                self.slot[sh, r][frozenset(j for j, q in enumerate(PERMS) if bytes(xw[i] for i in q) == pw)] += k
        ek = elem_key(sh)
        if ek:
            p = ek[1]
            for e in range(0, sh[0], p):
                xe, pe = xc[e:e + p], pc[e:e + p]
                self.eexact[ek, xe][pe] += k
                for r in range(0, p, 4):
                    if r in ek[2]: continue
                    xw = xe[r:r + 4]; pw = pe[r:r + 4]
                    self.evalue[ek, r, xw][pw if is_perm(xw, pw) else REAUTH] += k

    @staticmethod
    def one(c):
        ks = [k for k, v in c.items() if v > 0]
        return ks[0] if len(ks) == 1 else None

    def slot_perms(self, sh, r):
        """byte orders every informative observation of (shape, word offset) agrees on, None without >= MIN_SLOT
        observations or on a conflict (a re-authored value counts as a conflict)"""
        c = self.slot.get((sh, r))
        if not c: return None
        n = sum(v for v in c.values() if v > 0)
        if n < self.min_slot: return None
        s = frozenset(range(len(PERMS)))
        for k, v in c.items():
            if v > 0: s &= k
        return s or None

    def block(self, sh, xc, levels=LEVELS):
        """{word offset: (pc word, 'exact' | 'value' | 'slot')} for one Xbox block"""
        out = {}
        ex = self.one(self.exact.get((sh, xc), {})) if 'exact' in levels else None
        ek = elem_key(sh) if ('eexact' in levels or 'evalue' in levels) else None
        eex = {}
        for r in range(0, sh[0] - 3, 4):
            if r in sh[1]: continue
            xw = xc[r:r + 4]
            if ex is not None:
                pw = ex[r:r + 4]
                if is_perm(xw, pw): out[r] = (pw, 'exact'); continue
            if 'value' in levels:
                v = self.one(self.value.get((sh, r, xw), {}))
                if v is not None and v != REAUTH: out[r] = (v, 'value'); continue
            if ek:
                p = ek[1]; e = r - r % p; rr = r - e
                if 'eexact' in levels:
                    if e not in eex: eex[e] = self.one(self.eexact.get((ek, xc[e:e + p]), {}))
                    if eex[e] is not None:
                        pw = eex[e][rr:rr + 4]
                        if is_perm(xw, pw): out[r] = (pw, 'eexact'); continue
                if 'evalue' in levels:
                    v = self.one(self.evalue.get((ek, rr, xw), {}))
                    if v is not None and v != REAUTH: out[r] = (v, 'evalue'); continue
            if 'slot' in levels and not invariant(xw):
                s = self.slot_perms(sh, r)
                if s:
                    ys = {bytes(xw[i] for i in PERMS[j]) for j in s}
                    if len(ys) == 1: out[r] = (ys.pop(), 'slot')
        return out


def invariant(w):
    return len({bytes(w[j] for j in q) for q in PERMS}) == 1


_EK = {}
def elem_key(sh):
    """array blocks: (family, period p, relocated offsets in an element) when the block is >= 2 elements of p bytes
    with the same relocated offsets in every element (p = smallest such period, 8..0x100, at least one relocated
    word per element); else None. Element keys never depend on the block size, so arrays of different length
    (e.g. lara.drm 12647 +0x5628 (0xd338 bytes) vs doppelganger 20212 +0x43dc (0xa998), 0x24-byte records with two
    pointers) share their observations."""
    if sh in _EK: return _EK[sh]
    size, rel, fam = sh
    res = None
    if len(rel) >= 2:
        for p in range(8, min(0x100, size // 2) + 1, 4):
            if size % p: continue
            m = tuple(sorted({o % p for o in rel}))
            if len(m) * (size // p) == len(rel):
                res = (fam, p, m); break
    _EK[sh] = res
    return res


def truth_words(T, X, pc_mask, fam):
    """{offset: (pc word, kind)} for the target Xbox DTP X of family fam (pc_mask: relocated offsets of the PC copy)"""
    out = {}
    for b in X.starts:
        sh = X.shape(b, extra=pc_mask) + (fam,)
        for r, v in T.block(sh, X.content(b, sh)).items(): out[b + r] = v
    return out


def load_sec(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.type == 7 and s.id == sid: return D, s
    raise SystemExit('DTP %d not in %s' % (sid, path))


def cmd_loo(corpus, levels=LEVELS):
    """leave one chart pair out: all its blocks are removed from the tables, predicted, and put back"""
    T = Truth(corpus, with_slot='slot' in levels)
    st = collections.Counter(); bad = []
    groups = collections.defaultdict(list)
    for o in T.obs: groups[o[0]].append(o)
    for n, obs in groups.items():
        for _, sh, xc, pc in obs: T.add(sh, xc, pc, -1)
        for _, sh, xc, pc in obs:
            for r, (pw, kind) in T.block(sh, xc, levels).items():
                if invariant(xc[r:r + 4]): continue
                ok = pc[r:r + 4] == pw
                st[kind + ('_ok' if ok else '_bad')] += 1
                if not ok and len(bad) < 20: bad.append((corpus[n]['name'], kind, sh[0], r, xc[r:r + 4].hex(), pw.hex(), pc[r:r + 4].hex()))
            st['words'] += sum(1 for r in range(0, sh[0] - 3, 4) if r not in sh[1] and not invariant(xc[r:r + 4]))
        for _, sh, xc, pc in obs: T.add(sh, xc, pc, 1)
    print('corpus: %d pairs, %d block observations; keys: exact %d, value %d, element exact %d, element value %d, slot %d'
          % (len(corpus), len(T.obs), len(T.exact), len(T.value), len(T.eexact), len(T.evalue), len(T.slot)))
    kn = sum(st[k + s] for k in levels for s in ('_ok', '_bad'))
    print('leave-one-pair-out over %d byte-order-sensitive words (levels %s): %s; no prediction %d' % (
        st['words'], ', '.join(levels), ', '.join('%s %d right / %d wrong' % (k, st[k + '_ok'], st[k + '_bad']) for k in levels),
        st['words'] - kn))
    for b in bad: print('  wrong: %s %s block 0x%x +0x%x xbox %s predicted %s pc %s' % b)
    return st


def cmd_check(corpus, xpath, sid, before, after, nlist=15, tu=None):
    T = Truth(corpus)
    _, xs = load_sec(xpath, 'be', sid); _, bs = load_sec(before, 'le', sid); _, as_ = load_sec(after, 'le', sid)
    X = Chart(xs.data, xs.reloc, 'be'); Bc = Chart(bs.data, bs.reloc, 'le')
    B, A = bytes(bs.data), bytes(as_.data)
    fam = family_of(xs)
    tw = truth_words(T, X, Bc.mask, fam)
    st = collections.Counter(); reg = []
    notruth = collections.Counter(); notruth_cls = collections.Counter()   # block size / byte order of AFTER
    proven = set()                       # words inside condition records / transitions (proven layouts)
    if tu:
        import statechart_cond_fix as SC, shape_proof as SP
        ids = SC.tu_ids(open(tu, 'rb').read())
        for r in SC.records(X.d, '>', ids, X.mask | Bc.mask): proven.update((r[0], r[0] + 4))
        for a in SP.shaped(X.d, X.internal, 0x14, (8, 0xc)): proven.update((a, a + 4, a + 0x10))
    for o in range(0, len(X.d) - 3, 4):
        if o in X.mask or o in Bc.mask: continue
        st['words'] += 1
        if o not in tw:
            k = 'none_' + ('inv' if invariant(X.d[o:o + 4]) else 'changed' if B[o:o + 4] != A[o:o + 4] else 'same')
            st[k] += 1
            if k != 'none_inv' and o in proven: st['none_proven'] += 1
            elif k != 'none_inv':
                b = X.starts[bisect.bisect_right(X.starts, o) - 1]
                notruth[X.end[b] - b] += 1
                cls = 'raw' if A[o:o + 4] == X.d[o:o + 4] else 'u32' if A[o:o + 4] == X.d[o:o + 4][::-1] else \
                    'u16' if A[o:o + 4] == X.d[o + 1:o + 2] + X.d[o:o + 1] + X.d[o + 3:o + 4] + X.d[o + 2:o + 3] else 'other'
                notruth_cls[cls] += 1
            continue
        w, kind = tw[o]
        k = ('ok' if B[o:o + 4] == w else 'bad') + '->' + ('ok' if A[o:o + 4] == w else 'bad')
        st[kind, k] += 1
        if B[o:o + 4] != A[o:o + 4]: st['changed_' + ('right' if A[o:o + 4] == w else 'wrong')] += 1
        if k == 'ok->bad': reg.append((o, kind, X.d[o:o + 4].hex(), B[o:o + 4].hex(), A[o:o + 4].hex(), w.hex()))
        if k == 'bad->ok' and st['shown'] < nlist:
            st['shown'] += 1
            print('  fixed +0x%05x (%s): xbox %s before %s after %s' % (o, kind, X.d[o:o + 4].hex(), B[o:o + 4].hex(), A[o:o + 4].hex()))
    print('DTP %d (%s): %d data words' % (sid, fam, st['words']))
    for kind in ('exact', 'value', 'eexact', 'evalue'):
        print('  %-5s truth: %6d words  ok->ok %6d  ok->bad %5d  bad->ok %6d  bad->bad %5d' % (
            kind, sum(v for k, v in st.items() if k[0] == kind), st[kind, 'ok->ok'], st[kind, 'ok->bad'],
            st[kind, 'bad->ok'], st[kind, 'bad->bad']))
    print('  no truth: byte-order invariant %d, changed by the fix %d, unchanged %d' % (st['none_inv'], st['none_changed'],
                                                                                    st['none_same']))
    print('  precision of the fix on truth words it changed: %d right, %d wrong' % (st['changed_right'], st['changed_wrong']))
    if tu: print('  no-truth words inside condition records / transitions (proven layouts): %d' % st['none_proven'])
    print('  other no-truth words (not invariant) by block size: %s' % ', '.join('0x%x:%d' % kv for kv in notruth.most_common(12)))
    print('  no-truth words (not invariant), AFTER as Xbox word: %s' % dict(notruth_cls))
    for x in reg[:nlist]: print('  REGRESSION +0x%05x (%s): xbox %s before %s after %s truth %s' % x)
    return st


def family_of(xs):
    import statechart_corpus as CO
    return CO.family(bytes(xs.data), xs.id, xs.reloc, 'be')


def fix_section(T, xs, ps):
    """re-convert the truth words of one PC section in place; returns (changed, truth words)"""
    X = Chart(xs.data, xs.reloc, 'be'); Pc = Chart(ps.data, ps.reloc, 'le')
    if len(X.d) != len(Pc.d): return 0, 0
    tw = truth_words(T, X, Pc.mask, family_of(xs))
    pd = bytearray(ps.data); n = 0
    for o, (w, kind) in tw.items():
        if pd[o:o + 4] != w: pd[o:o + 4] = w; n += 1
    ps.data = bytes(pd)
    return n, len(tw)


def main(argv):
    mode = argv[0]
    corpus = pickle.load(open(argv[1], 'rb'))
    if mode == 'loo': cmd_loo(corpus, tuple(argv[argv.index('--levels') + 1].split(',')) if '--levels' in argv else LEVELS)
    elif mode == 'check':
        nlist = 15
        if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
        tu = None
        if '--tu' in argv: k = argv.index('--tu'); tu = argv[k + 1]; del argv[k:k + 2]
        cmd_check(corpus, argv[2], int(argv[3]), argv[4], argv[5], nlist, tu)
    elif mode == 'fix':
        k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
        T = Truth(corpus)
        XD = DW.read(open(argv[2], 'rb').read(), 'be'); PD = DW.read(open(argv[3], 'rb').read(), 'le')
        xsec = {s.id: s for s in XD.sections if s.type == 7}
        for sid in (int(x) for x in argv[4].split(',')):
            ps = next(s for s in PD.sections if s.type == 7 and s.id == sid)
            n, t = fix_section(T, xsec[sid], ps)
            print('DTP %d: %d truth words, %d changed' % (sid, t, n))
        raw = PD.write('le')
        if open(argv[3], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out, 'wb').write(raw); DW.read(open(out, 'rb').read(), 'le')
        print('written %s' % out)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
