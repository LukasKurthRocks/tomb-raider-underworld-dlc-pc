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

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/tu_func_pair.py RETAIL.bin TU.bin OUT_DIR
  e.g. work/xenia_dump/retail_image_82000000.bin work/xenia_dump/tu_image_82000000.bin work/tu_funcdiff
Output: OUT_DIR/pairs.tsv (tu, retail, status, method, confidence, score, sizes, xbox_func_diff class of the TU
function and of the retail function),
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
    if len(argv) != 3:
        sys.exit(__doc__)
    retail, tu, out = argv
    os.makedirs(out, exist_ok=True)
    log = []
    say = lambda s: (print(s, flush=True), log.append(s))
    rd, rf, rh = XD.functions(retail)
    td, tf, th = XD.functions(tu)
    hr = dict((f[0], h) for f, h in zip(rf, rh))
    ht = dict((f[0], h) for f, h in zip(tf, th))
    ocls, oremoved = old_classes(rf, rh, tf, th)
    say('retail %d functions, TU %d functions; xbox_func_diff: equal %d, changed %d, new %d, removed %d' % (
        len(rf), len(tf), sum(1 for c in ocls.values() if c[0] == 'equal'),
        sum(1 for c in ocls.values() if c[0] == 'changed'), sum(1 for c in ocls.values() if c[0] == 'new'),
        len(oremoved)))
    R = FM.Xbox(retail)
    T = FM.Xbox(tu)
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
        f.write('tu\tretail\tstatus\tmethod\tconfidence\tscore\ttu_size\tretail_size\tdiff_class\tretail_class\n')
        rchg = set(r for c, r in ocls.values() if c == 'changed')
        for t, r, status, meth, conf, score in rows:
            oc = ocls.get(t, ('', None))[0] if t is not None else ''
            rc = '' if r is None else 'removed' if r in oremoved else 'changed' if r in rchg else 'equal'
            f.write('%s\t%s\t%s\t%s\t%s\t%.3f\t%d\t%d\t%s\t%s\n' % (
                ('0x%08x' % t) if t is not None else '', ('0x%08x' % r) if r is not None else '', status, meth, conf,
                score, T.size.get(t, 0) if t is not None else 0, R.size.get(r, 0) if r is not None else 0, oc, rc))
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
