"""Pair the functions of the Xbox 360 retail exe and the title-update (TU) exe by evidence, not by position
(read-only; 2026-11-02, docs/Plan-TU-Funktionsvergleich.md section 2.1).

tools/xbox_func_diff.py aligns the normalised function hashes in address order and pairs the functions inside a
replaced run by position. The TU relinked the exe, so its 937 "changed" / 556 "removed" / 391 "new" functions are
partly moved functions. This tool pairs them by evidence, in rounds:
  aligned      - equal normalised hash in the address-order alignment (xbox_func_diff's "equal")
  moved        - equal normalised hash, unique among the still unpaired functions on both sides (moved, unchanged)
  string/float - a string / unusual float referenced by exactly one unpaired function on each side
  callgraph    - propagated from paired functions: ordered callee lists aligned (difflib), function-pointer lists,
                 the single unpaired caller, vtables built by a pair (slot by slot)
  similarity   - between two consecutive pairs of the longest address-monotonic chain, the unpaired functions are
                 aligned by opcode similarity (dynamic programming), a pair needs similarity >= 0.5
  position     - last resort: xbox_func_diff's positional pair when both are still unpaired and similarity >= 0.5
Every pair has a size-ratio guard (TU / retail 0.4 .. 2.5). Status per function: moved-equal (aligned or moved),
paired (method + confidence), tu-only, retail-only.
Functions (Q49, 12.11.2026): the .pdata functions plus every bl target outside them (leaf functions without an unwind
entry, ~1 900 per image; end = first unconditional return / branch out that no in-function branch jumps past, see
leaf_end) - column no_pdata says which side has such a function. --check-leaf runs leaf_end on the .pdata functions
(how often it finds their known end) and prints how many functions without .pdata it adds.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/tu_func_pair.py RETAIL.bin TU.bin OUT_DIR
  ../bin/pyt -t 900 tools/tu_func_pair.py --check-leaf IMAGE.bin [IMAGE.bin ...]
  e.g. work/xenia_dump/retail_image_82000000.bin work/xenia_dump/tu_image_82000000.bin work/tu_funcdiff
Output: OUT_DIR/pairs.tsv (tu, retail, status, method, confidence, score, sizes, xbox_func_diff class of the TU
function and of the retail function, no_pdata),
OUT_DIR/pair_summary.txt. Only addresses, sizes, methods and counts - no game bytes.
The module also exports the instruction helpers used by tools/tu_func_classify.py (skeleton tokens, similarity).
"""
import sys, os, struct, difflib, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import xbox_func_diff as XD
import xbox_pc_funcmap as FM

BASE = 0x82000000
XO_OPS = {19, 31, 59, 63}


def words(d, fs, fe):
    return struct.unpack_from('>%dI' % ((fe - fs) // 4), d, fs - BASE)


# ---- functions without a .pdata entry (Q49, 12.11.2026) ----
# The linker gives leaf functions (no stack frame, no calls) no .pdata entry; ppc_xrefs / xbox_func_diff only know the
# .pdata functions, so ~1 900 functions per image that are reached by `bl` were invisible to the pairing and to the
# coverage list (Q75). They are added here as functions: start = the bl target, end = see leaf_end.
BLR, BCTR = 0x4e800020, 0x4e800420


def leaf_end(d, s, limit):
    """end (exclusive) of a function starting at s that has no .pdata entry: the first unconditional return (blr /
    bctr) or unconditional branch out of [s, limit) that no in-function branch (bc / b) or in-code jump table entry
    jumps past; a zero word (padding) also ends it. Bounded by `limit` (the next known function start). Checked
    against the .pdata functions themselves: see --check-leaf"""
    maxt = s
    a = s
    while a < limit:
        w = struct.unpack_from('>I', d, a - BASE)[0]
        if w == 0:
            return a if a > s else a + 4
        op = w >> 26
        if s <= w < limit and not (w & 3) and w > a:   # absolute in-function address: jump table entry
            maxt = max(maxt, w)
        elif op == 16:
            bd = w & 0xfffc
            t = a + (bd - 0x10000 if bd & 0x8000 else bd)
            if s <= t < limit:
                maxt = max(maxt, t)
        elif op == 18 and not (w & 1):                 # b (no link)
            li = w & 0x03fffffc
            t = (a + (li - 0x04000000 if li & 0x02000000 else li)) & 0xffffffff
            if s <= t < limit and not (w & 2):
                maxt = max(maxt, t)
            elif a >= maxt:
                return a + 4                           # tail branch out of the function
        elif (w == BLR or w == BCTR) and a >= maxt:
            return a + 4
        a += 4
    return limit


def nopdata_functions(d, secs, funcs, res):
    """[(start, end)] of the bl targets outside every .pdata function, repeated over the new functions' own bl calls
    until no new target appears (leaf functions rarely call; the loop is a guard)"""
    code = P.code_ranges(secs)
    known = sorted(f[0] for f in funcs)
    pstart = [f[0] for f in funcs]
    found = {}
    todo = res
    while True:
        new = set()
        for fs, items in todo.items():
            for a, k, v in items:
                if k == 'call' and v not in found and not (v & 3) and P.func_of(funcs, v) is None and \
                        any(c0 <= v < c1 for c0, c1 in code):
                    new.add(v)
        if not new:
            break
        starts = sorted(set(known) | set(found) | new)
        ext = []
        for v in sorted(new):
            i = bisect.bisect_right(starts, v)
            lim = starts[i] if i < len(starts) else next(c1 for c0, c1 in code if c0 <= v < c1)
            lim = min(lim, next(c1 for c0, c1 in code if c0 <= v < c1))
            j = bisect.bisect_right(pstart, v)
            if j < len(pstart):
                lim = min(lim, pstart[j])
            found[v] = leaf_end(d, v, lim)
            ext.append((v, found[v]))
        todo = P.scan(d, secs, ext)
    # a later-found start can cut an earlier end: clip every end at the next start
    starts = sorted(set(known) | set(found))
    out = []
    for v in sorted(found):
        i = bisect.bisect_right(starts, v)
        e = found[v] if i >= len(starts) else min(found[v], starts[i])
        out.append((v, e))
    return out


_ALL = {}
_pdata_cached = P.cached                           # the .pdata-only cache (main() swaps P.cached while building FM.Xbox)


def cached_all(path):
    """(funcs, res) like ppc_xrefs.cached, plus the functions without .pdata (nopdata_functions) and their scan;
    funcs sorted by start. Kept in memory per process (the .pdata part comes from ppc_xrefs' cache)"""
    if path not in _ALL:
        funcs, res = _pdata_cached(path)
        d, secs = P.load(path)
        extra = nopdata_functions(d, secs, funcs, res)
        res2 = dict(res)
        res2.update(P.scan(d, secs, extra))
        _ALL[path] = (sorted(list(funcs) + extra), res2, set(s for s, e in extra))
    return _ALL[path][0], _ALL[path][1]


def nopdata_starts(path):
    """starts of the functions cached_all added (no .pdata entry)"""
    cached_all(path)
    return _ALL[path][2]


def functions_all(path):
    """as xbox_func_diff.functions (d, [(start, end)], normalised hashes), including the functions without .pdata"""
    d, secs = P.load(path)
    funcs, res = cached_all(path)
    return d, funcs, [XD.norm_hash(d, s, e) for s, e in funcs]


def check_leaf(path):
    """leaf_end applied to every .pdata function start (limit = the next .pdata start): how often does it find the
    .pdata end exactly - the error rate to expect for the functions without .pdata"""
    funcs, res = _pdata_cached(path)
    d, secs = P.load(path)
    st = collections.Counter()
    for i, (s, e) in enumerate(funcs):
        lim = funcs[i + 1][0] if i + 1 < len(funcs) else e
        x = leaf_end(d, s, lim)
        calls = any(k == 'call' for a, k, v in res.get(s, ()))
        kind = 'calls' if calls else 'leaf'
        st[(kind, 'exact' if x == e else ('short' if x < e else 'long'))] += 1
    return st


def skel(w):
    """opcode-only token of one instruction (primary opcode + extended opcode), registers / immediates dropped"""
    op = w >> 26
    if op == 59 or (op == 63 and ((w >> 1) & 0x1f) >= 18):        # A-form float ops: xo is 5 bits (frC above)
        return (op << 11) | ((w >> 1) & 0x1f)
    if op in XO_OPS:
        return (op << 11) | ((w >> 1) & 0x3ff)
    if op == 30:
        return (op << 11) | ((w >> 1) & 0xf)
    if op in (58, 62):
        return (op << 11) | (w & 3)
    if op == 4:
        return (op << 11) | (w & 0x7f3 if (w & 0x13) == 0x03 else 0x400 | (w & 0x3f))
    if op in (5, 6):
        return (op << 11) | (w & 0x3f0)
    if op == 18:
        return (op << 11) | (w & 3)
    return op << 11


def skeleton(d, fs, fe):
    return [skel(w) for w in words(d, fs, fe)]


def similarity(a, b):
    if not a or not b:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < 0.45 or sm.quick_ratio() < 0.45:
        return 0.0
    return sm.ratio()


def propagate(R, T, pairs, rev, vtmap, ratio):
    """FM.propagate with a tighter size-ratio guard (retail and TU are the same compiler)"""
    votes, vvotes = collections.Counter(), collections.Counter()
    for x, (p, *_r) in list(pairs.items()):
        FM.align(R.calls.get(x, []), T.calls.get(p, []), pairs, rev, votes)
        FM.align(R.fptrs.get(x, []), T.fptrs.get(p, []), pairs, rev, votes)
        ux = [c for c in R.callers.get(x, ()) if c not in pairs]
        up = [c for c in T.callers.get(p, ()) if c not in rev]
        if len(ux) == 1 and len(up) == 1:
            votes[(ux[0], up[0])] += 1
        xv, pv = R.vts.get(x, []), T.vts.get(p, [])
        if xv and len(xv) == len(pv):
            for a, b in zip(xv, pv):
                vvotes[(a, b)] += 1
    for (a, b), n in vvotes.most_common():
        if a not in vtmap and b not in vtmap.values() and len(R.vt[a]) == len(T.vt[b]):
            vtmap[a] = b
    for a, b in vtmap.items():
        for u, v in zip(R.vt[a], T.vt[b]):
            if u not in pairs and v not in rev:
                votes[(u, v)] += 2
    return FM.resolve(votes, pairs, rev, 'callgraph', lambda n: 'medium' if n >= 2 else 'low', R.size, T.size,
                      ratio=ratio)


def gap_fill(R, T, pairs, rev, sk_r, sk_t, ratio, min_sim=0.5, max_gap=80):
    """between consecutive chain pairs: monotonic DP over the unpaired functions, score = similarity"""
    chain = FM.lis_pairs(pairs)
    new = 0
    for (x1, p1), (x2, p2) in zip(chain, chain[1:]):
        gx = [f for f in R.starts[bisect.bisect_right(R.starts, x1):bisect.bisect_left(R.starts, x2)] if f not in pairs]
        gp = [f for f in T.starts[bisect.bisect_right(T.starts, p1):bisect.bisect_left(T.starts, p2)] if f not in rev]
        if not gx or not gp or len(gx) > max_gap or len(gp) > max_gap:
            continue
        n, m = len(gx), len(gp)
        S = [[0.0] * m for _ in range(n)]
        for i, a in enumerate(gx):
            for j, b in enumerate(gp):
                r = T.size[b] / float(max(4, R.size[a]))
                if ratio[0] <= r <= ratio[1]:
                    S[i][j] = similarity(sk_r(a), sk_t(b))
        D = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                s = S[i - 1][j - 1]
                D[i][j] = max(D[i - 1][j], D[i][j - 1], D[i - 1][j - 1] + (s if s >= min_sim else -1))
        i, j = n, m
        while i > 0 and j > 0:
            s = S[i - 1][j - 1]
            if s >= min_sim and abs(D[i][j] - (D[i - 1][j - 1] + s)) < 1e-9:
                a, b = gx[i - 1], gp[j - 1]
                conf = 'high' if s >= 0.9 else 'medium' if s >= 0.7 else 'low'
                pairs[a] = (b, 'similarity', conf, s)
                rev[b] = a
                new += 1
                i, j = i - 1, j - 1
            elif D[i][j] == D[i - 1][j]:
                i -= 1
            else:
                j -= 1
    return new


def old_classes(rf, rh, tf, th):
    """xbox_func_diff's classes: TU start -> ('equal'|'changed', retail) / ('new', None); retail removed set"""
    sm = difflib.SequenceMatcher(None, rh, th, autojunk=False)
    cls, removed = {}, set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                cls[tf[j][0]] = ('equal', rf[i][0])
        elif tag == 'insert':
            for f in tf[j1:j2]:
                cls[f[0]] = ('new', None)
        elif tag == 'delete':
            removed |= set(f[0] for f in rf[i1:i2])
        else:
            k = min(i2 - i1, j2 - j1)
            for q in range(k):
                cls[tf[j1 + q][0]] = ('changed', rf[i1 + q][0])
            for f in tf[j1 + k:j2]:
                cls[f[0]] = ('new', None)
            removed |= set(f[0] for f in rf[i1 + k:i2])
    return cls, removed


def read_pairs(path):
    """pairs.tsv -> list of dict rows (addresses as int, None when empty)"""
    rows = []
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            v = dict(zip(head, line.rstrip('\n').split('\t')))
            for k in ('tu', 'retail'):
                v[k] = int(v[k], 16) if v.get(k) else None
            rows.append(v)
    return rows


def main(argv):
    if argv and argv[0] == '--check-leaf':           # Q49: how well leaf_end finds known function ends
        for path in argv[1:]:
            st = check_leaf(path)
            funcs, res = cached_all(path)
            n = len(nopdata_starts(path))
            print('%s: .pdata functions by leaf_end result: %s; functions without .pdata added: %d' % (
                os.path.basename(path), ', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(st.items())), n))
        return
    if len(argv) != 3:
        sys.exit(__doc__)
    retail, tu, out = argv
    os.makedirs(out, exist_ok=True)
    log = []
    say = lambda s: (print(s, flush=True), log.append(s))
    rd, rf, rh = functions_all(retail)               # Q49: .pdata functions + bl targets without .pdata
    td, tf, th = functions_all(tu)
    hr = dict((f[0], h) for f, h in zip(rf, rh))
    ht = dict((f[0], h) for f, h in zip(tf, th))
    ocls, oremoved = old_classes(rf, rh, tf, th)
    say('retail %d functions, TU %d functions (without .pdata: %d / %d, Q49); address-order alignment: equal %d, '
        'changed %d, new %d, removed %d' % (
            len(rf), len(tf), len(nopdata_starts(retail)), len(nopdata_starts(tu)),
            sum(1 for c in ocls.values() if c[0] == 'equal'), sum(1 for c in ocls.values() if c[0] == 'changed'),
            sum(1 for c in ocls.values() if c[0] == 'new'), len(oremoved)))
    P.cached = cached_all                            # FM.Xbox reads ppc_xrefs.cached: give it the full function list
    try:
        R = FM.Xbox(retail)
        T = FM.Xbox(tu)
    finally:
        P.cached = _pdata_cached
    cache_r, cache_t = {}, {}
    sk_r = lambda a: cache_r.setdefault(a, skeleton(rd, a, a + R.size[a]))
    sk_t = lambda a: cache_t.setdefault(a, skeleton(td, a, a + T.size[a]))
    ratio = (0.4, 2.5)

    pairs, rev = {}, {}
    for t, (c, r) in ocls.items():
        if c == 'equal':
            pairs[r] = (t, 'aligned', 'high', 1); rev[t] = r
    say('aligned (equal hash, address order): %d' % len(pairs))
    # moved: equal hash, unique among the unpaired functions on each side
    ur = collections.defaultdict(list)
    ut = collections.defaultdict(list)
    for s in R.starts:
        if s not in pairs: ur[hr[s]].append(s)
    for s in T.starts:
        if s not in rev: ut[ht[s]].append(s)
    n = 0
    for h, xs in ur.items():
        ps = ut.get(h)
        if ps and len(xs) == 1 and len(ps) == 1:
            pairs[xs[0]] = (ps[0], 'moved', 'high', 1); rev[ps[0]] = xs[0]; n += 1
    say('moved (equal hash, unique elsewhere): %d' % n)
    # string / float anchors among the unpaired functions
    ustr_r = dict((f, v) for f, v in R.strs.items() if f not in pairs)
    ustr_t = dict((f, v) for f, v in T.strs.items() if f not in rev)
    v = FM.unique_anchor(ustr_r, ustr_t, 'string')
    n = FM.resolve(v, pairs, rev, 'string', lambda n: 'high' if n >= 2 else 'medium', R.size, T.size, ratio=ratio)
    say('string anchors: %d candidates, %d accepted' % (len(v), n))
    uflt_r = dict((f, v) for f, v in R.flts.items() if f not in pairs)
    uflt_t = dict((f, v) for f, v in T.flts.items() if f not in rev)
    v = FM.unique_anchor(uflt_r, uflt_t, 'float')
    n = FM.resolve(v, pairs, rev, 'float', lambda n: 'medium' if n >= 2 else 'low', R.size, T.size, ratio=ratio)
    say('float anchors: %d candidates, %d accepted' % (len(v), n))
    vtmap = {}
    for rnd in range(1, 12):
        m = 0
        for r2 in range(1, 40):
            k = propagate(R, T, pairs, rev, vtmap, ratio)
            m += k
            if not k:
                break
        g = gap_fill(R, T, pairs, rev, sk_r, sk_t, ratio)
        say('round %d: callgraph %d, similarity %d (total %d pairs, vtables %d)' % (rnd, m, g, len(pairs), len(vtmap)))
        if not m and not g:
            break
    # last resort: xbox_func_diff's positional pair, if both are still unpaired and the bodies are similar
    n = 0
    for t, (c, r) in ocls.items():
        if c == 'changed' and t not in rev and r not in pairs:
            s = similarity(sk_r(r), sk_t(t))
            if s >= 0.5 and ratio[0] <= T.size[t] / float(max(4, R.size[r])) <= ratio[1]:
                pairs[r] = (t, 'position', 'medium' if s >= 0.7 else 'low', s); rev[t] = r; n += 1
    say('position (xbox_func_diff pair, similarity >= 0.5): %d' % n)

    # score of every non-hash pair = opcode similarity (a check of the evidence-based pairs)
    rows = []
    stat = collections.Counter()
    for x, (p, meth, conf, votes) in pairs.items():
        if meth in ('aligned', 'moved'):
            status, score = 'moved-equal', 1.0
        else:
            status = 'paired'
            score = votes if meth in ('similarity', 'position') else similarity(sk_r(x), sk_t(p))
            if meth not in ('similarity', 'position') and hr[x] == ht[p]:
                status, score = 'moved-equal', 1.0
        stat[(status, meth, conf)] += 1
        rows.append((p, x, status, meth, conf, score))
    for s in T.starts:
        if s not in rev:
            rows.append((s, None, 'tu-only', '', '', 0.0)); stat[('tu-only', '', '')] += 1
    for s in R.starts:
        if s not in pairs:
            rows.append((None, s, 'retail-only', '', '', 0.0)); stat[('retail-only', '', '')] += 1
    rows.sort(key=lambda r: (r[0] if r[0] is not None else 0xffffffff, r[1] or 0))
    with open(os.path.join(out, 'pairs.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('tu\tretail\tstatus\tmethod\tconfidence\tscore\ttu_size\tretail_size\tdiff_class\tretail_class\t'
                'no_pdata\n')
        rchg = set(r for c, r in ocls.values() if c == 'changed')
        np_t, np_r = nopdata_starts(tu), nopdata_starts(retail)
        for t, r, status, meth, conf, score in rows:
            oc = ocls.get(t, ('', None))[0] if t is not None else ''
            rc = '' if r is None else 'removed' if r in oremoved else 'changed' if r in rchg else 'equal'
            npd = '/'.join(x for x, y in (('tu', t in np_t), ('retail', r in np_r)) if y)
            f.write('%s\t%s\t%s\t%s\t%s\t%.3f\t%d\t%d\t%s\t%s\t%s\n' % (
                ('0x%08x' % t) if t is not None else '', ('0x%08x' % r) if r is not None else '', status, meth, conf,
                score, T.size.get(t, 0) if t is not None else 0, R.size.get(r, 0) if r is not None else 0, oc, rc,
                npd))
    say('pairs by status / method / confidence:')
    for k, n in sorted(stat.items()):
        say('  %-12s %-10s %-7s %6d' % (k[0], k[1], k[2], n))
    # how the old classes re-distribute
    tst = dict((r[0], r[2]) for r in rows if r[0] is not None)
    for oc in ('changed', 'new'):
        c = collections.Counter(tst[t] for t, (k, _r) in ocls.items() if k == oc)
        say('xbox_func_diff "%s" (%d) now: %s' % (oc, sum(c.values()), dict(c)))
    rst = dict((r[1], r[2]) for r in rows if r[1] is not None)
    c = collections.Counter(rst[x] for x in oremoved)
    say('xbox_func_diff "removed" (%d) now: %s' % (len(oremoved), dict(c)))
    # changed pairs: does the evidence pairing agree with the positional one?
    agree = collections.Counter()
    better = collections.Counter()
    for t, (k, r) in ocls.items():
        if k == 'changed':
            a = 'same retail' if rev.get(t) == r else ('other retail' if t in rev else 'unpaired')
            agree[a] += 1
            if a != 'same retail':
                sp = similarity(sk_r(r), sk_t(t))
                se = similarity(sk_r(rev[t]), sk_t(t)) if t in rev else -1
                better[a + (': evidence pair more similar' if se > sp else ': positional pair more similar'
                            if sp > se else ': equal')] += 1
                better[a + (': positional similarity < 0.5' if sp < 0.5 else ': positional similarity >= 0.5')] += 1
    say('positional "changed" pairs vs evidence pairing: %s' % dict(agree))
    for k, n in sorted(better.items()):
        say('  %-60s %5d' % (k, n))
    open(os.path.join(out, 'pair_summary.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(log) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
