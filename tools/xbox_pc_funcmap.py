"""Function correspondence table Xbox 360 retail exe <-> PC tru.exe (read-only; finding 43, DLC 2 shadow power).

Step 1 of the "rule of three": the PC game is the Xbox retail game compiled for x86; the Xbox title update (TU) is
retail + a delta. To translate the delta, every retail function the TU code calls needs its PC counterpart. This tool
builds that map automatically, every pair with a method and a confidence:
  * string   - both functions reference the same string that only one function per exe references (anchor)
  * float    - the same unusual float constant, unique on both sides (weaker anchor)
  * callgraph- propagated from matched pairs: their ordered callee lists are aligned (difflib); unmatched callees in
               equal-length gaps pair by position; also function-pointer lists (native binders), a single unmatched
               caller, and vtables built by a matched pair (slot by slot); a candidate needs a plausible size ratio
               and wins by votes
  * layout   - both compilers keep source order: between consecutive pairs of the longest monotonic chain the
               unmatched functions are aligned by size (dynamic programming) - weak, a candidate only
Every pair gets a tier: verified (>= 2 matched callees, >= half also callees on PC), anchor (string / float without
that evidence), unverified, contradicted. Data globals are mapped the same way (ordered references to .data of
paired functions, by position).

Inputs: the Xenia memory images of the Xbox exe (retail and TU, guest base 0x82000000, see tools/ppc_xrefs.py) and
the PC tru.exe file (x86, image base from the PE header). PC function starts are derived (16-byte aligned starts
after int3 padding, plus call / jmp rel32 targets); PC calls are E8 / E9 rel32 to such starts; PC references are
any 4-byte little-endian value inside the function equal to a string / float / .data address.

Focus report ("shadow power"): TU roots = the TU's NEW functions + the TU functions flagged by --disp / --mark
(e.g. readers of the game-state field 0x1244, writers of the time scales). Their callees are classified: TU-new
(must be re-implemented), retail function with a PC counterpart, or retail function without one (missing).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/xbox_pc_funcmap.py RETAIL.bin TU.bin TRU_EXE OUT_DIR [--disp 0x1244] [--mark A,..]
       [--data A,..]
  OUT_DIR (e.g. work/xmap): xbox_pc_map.tsv (functions), xbox_pc_data.tsv (globals), shadow_focus.tsv, summary.txt
  --data: TU guest data addresses to resolve to retail and PC (e.g. 0x829892b0,0x827754ac,0x827754cc)
Only addresses, methods and counts are written - no game bytes.
"""
import sys, os, struct, difflib, bisect, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import xbox_func_diff as XD

XBASE = 0x82000000
COMMON_FLOATS = {0.0, 1.0, -1.0, 0.5, -0.5, 2.0, -2.0, 0.25, 4.0, 10.0, 100.0, 1000.0, 3.0, 0.1, 0.01, 0.001,
                 255.0, 256.0, 0.75, 1.5, 8.0, 16.0, 32.0, 64.0, 128.0, 360.0, 180.0, 90.0, 0.2, 5.0}


def cstr(d, off, limit=200):
    if off < 0 or off >= len(d):
        return None
    e = d.find(b'\0', off, off + limit)
    if e < 0:
        return None
    s = d[off:e]
    if len(s) >= 4 and all(32 <= c < 127 for c in s):
        return s.decode('ascii')
    return None


def fkey(v):
    if not math.isfinite(v) or v in COMMON_FLOATS or abs(v) < 1e-6 or abs(v) > 1e7:
        return None
    if v == int(v) and abs(v) <= 4096:
        return None
    return '%.6g' % v


# ---------------------------------------------------------------- Xbox side
class Xbox:
    def __init__(self, path):
        self.path = path
        self.d, self.secs = P.load(path)
        self.funcs, self.res = P.cached(path)
        self.starts = [f[0] for f in self.funcs]
        self.size = dict((s, e - s) for s, e in self.funcs)
        rd = [s for s in self.secs if s[0] == '.rdata']
        self.rdata = (rd[0][1], rd[0][1] + rd[0][2]) if rd else (0, 0)
        dt = [s for s in self.secs if s[0] == '.data']
        self.data = (dt[0][1], dt[0][1] + dt[0][2]) if dt else (0, 0)
        sset = set(self.starts)
        # vtables: runs of >= 3 big-endian code pointers (function starts) in .rdata
        self.vt = {}
        a = self.rdata[0] & ~3
        while a < self.rdata[1] - 4:
            v = struct.unpack_from('>I', self.d, a - XBASE)[0]
            if v in sset:
                b = a
                ents = []
                while b < self.rdata[1] - 4:
                    w = struct.unpack_from('>I', self.d, b - XBASE)[0]
                    if w not in sset:
                        break
                    ents.append(w); b += 4
                if len(ents) >= 3:
                    self.vt[a] = ents
                a = b + 4 if b > a else a + 4
            else:
                a += 4
        self.calls, self.strs, self.flts, self.globs, self.vts, self.fptrs = {}, {}, {}, {}, {}, {}
        for fs, items in self.res.items():
            cl, st, fl, gl, vl, fp = [], set(), set(), [], [], []
            for a, k, v in items:
                if k == 'call':
                    if v in sset and v != fs and v not in cl:
                        cl.append(v)
                    continue
                if v in self.vt:
                    if v not in vl:
                        vl.append(v)
                    continue
                if v in sset:
                    fp.append(v)
                    continue
                o = v - XBASE
                if self.rdata[0] <= v < self.rdata[1] or self.data[0] <= v < self.data[1]:
                    s = cstr(self.d, o)
                    if s:
                        st.add(s); continue
                if self.rdata[0] <= v < self.rdata[1] and o + 4 <= len(self.d):
                    k2 = fkey(struct.unpack_from('>f', self.d, o)[0])
                    if k2:
                        fl.add(k2)
                    continue
                if self.data[0] <= v < self.data[1]:
                    gl.append(v)
            self.calls[fs], self.strs[fs], self.flts[fs], self.globs[fs] = cl, st, fl, gl
            self.vts[fs], self.fptrs[fs] = vl, fp
        self.callers = collections.defaultdict(set)
        for fs, cl in self.calls.items():
            for c in cl:
                self.callers[c].add(fs)


# ---------------------------------------------------------------- PC side
class PC:
    def __init__(self, path):
        d = open(path, 'rb').read()
        self.d = d
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        n = struct.unpack_from('<H', d, pe + 6)[0]
        opt = struct.unpack_from('<H', d, pe + 20)[0]
        self.base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
        self.secs = {}
        for i in range(n):
            o = pe + 24 + opt + 40 * i
            name = d[o:o + 8].rstrip(b'\0').decode('latin-1')
            vsize, va, rsize, raw = struct.unpack_from('<IIII', d, o + 8)
            self.secs[name] = (self.base + va, vsize, raw, rsize)
        tva, tvs, traw, trs = self.secs['.text']
        self.tva = tva
        self.text = d[traw:traw + min(tvs, trs)]
        self.rd = self.secs.get('.rdata')
        self.dt = self.secs.get('.data')

    def read(self, va, n):
        for va0, vs, raw, rs in self.secs.values():
            if va0 <= va < va0 + min(vs, rs) - n + 1:
                return self.d[raw + va - va0: raw + va - va0 + n]
        return None

    def in_sec(self, sec, va):
        return sec and sec[0] <= va < sec[0] + sec[1]

    def build(self):
        t, va = self.text, self.tva
        starts = set()
        # int3 padding: a 16-aligned address directly after 0xCC
        for i in range(16, len(t), 16):
            if t[i - 1] == 0xCC and t[i] != 0xCC:
                starts.add(va + i)
        # call / jmp rel32 targets that look like function starts
        tg = collections.Counter()
        for i in range(len(t) - 5):
            if t[i] in (0xE8, 0xE9):
                x = (va + i + 5 + struct.unpack_from('<i', t, i + 1)[0]) & 0xffffffff
                if va <= x < va + len(t):
                    o = x - va
                    if x % 16 == 0 or (o > 0 and t[o - 1] in (0xCC, 0xC3)):
                        tg[x] += 1
        starts |= set(x for x, c in tg.items() if c >= 1)
        self.starts = sorted(starts)
        ends = self.starts[1:] + [va + len(t)]
        self.size = dict((s, e - s) for s, e in zip(self.starts, ends))
        sset = set(self.starts)
        # strings of .rdata / .data
        self.strat = {}
        for sec in (self.rd, self.dt):
            if not sec:
                continue
            va0, vs, raw, rs = sec
            blob = self.d[raw:raw + min(vs, rs)]
            i = 0
            while i < len(blob):
                e = blob.find(b'\0', i)
                if e < 0:
                    break
                s = blob[i:e]
                if len(s) >= 4 and all(32 <= c < 127 for c in s) and (i == 0 or blob[i - 1] == 0):
                    self.strat[va0 + i] = s.decode('ascii')
                i = e + 1
        strset = self.strat
        # vtables: runs of >= 3 little-endian pointers to function starts in .rdata
        self.vt = {}
        if self.rd:
            va0, vs, raw, rs = self.rd
            blob = self.d[raw:raw + min(vs, rs)]
            o = 0
            while o < len(blob) - 4:
                v = struct.unpack_from('<I', blob, o)[0]
                if v in sset:
                    q, ents = o, []
                    while q < len(blob) - 4:
                        w = struct.unpack_from('<I', blob, q)[0]
                        if w not in sset:
                            break
                        ents.append(w); q += 4
                    if len(ents) >= 3:
                        self.vt[va0 + o] = ents
                    o = q + 4 if q > o else o + 4
                else:
                    o += 4
        self.calls, self.strs, self.flts, self.globs, self.vts, self.fptrs = {}, {}, {}, {}, {}, {}
        for s in self.starts:
            self.calls[s], self.strs[s], self.flts[s], self.globs[s] = [], set(), set(), []
            self.vts[s], self.fptrs[s] = [], []
        # one pass over .text: calls and dword references, attributed to the containing function
        idx_starts = self.starts
        cur_i = 0
        rd, dt = self.rd, self.dt
        for i in range(len(t) - 4):
            a = va + i
            while cur_i + 1 < len(idx_starts) and idx_starts[cur_i + 1] <= a:
                cur_i += 1
            f = idx_starts[cur_i]
            if a < f:
                continue
            b = t[i]
            if b in (0xE8, 0xE9) and i + 5 <= len(t):
                x = (a + 5 + struct.unpack_from('<i', t, i + 1)[0]) & 0xffffffff
                if x in sset and x != f and x not in self.calls[f]:
                    self.calls[f].append(x)
            v = struct.unpack_from('<I', t, i)[0]
            if v < 0x400000:
                continue
            if v in self.vt:
                if v not in self.vts[f]:
                    self.vts[f].append(v)
            elif v in sset:
                if b not in (0xE8, 0xE9) and (i == 0 or t[i - 1] not in (0xE8, 0xE9)):
                    self.fptrs[f].append(v)
            elif v in strset:
                self.strs[f].add(strset[v])
            elif rd and rd[0] <= v < rd[0] + rd[1]:
                raw = self.read(v, 4)
                if raw:
                    k = fkey(struct.unpack('<f', raw)[0])
                    if k:
                        self.flts[f].add(k)
            elif dt and dt[0] <= v < dt[0] + dt[1]:
                self.globs[f].append(v)
        self.callers = collections.defaultdict(set)
        for fs, cl in self.calls.items():
            for c in cl:
                self.callers[c].add(fs)


# ---------------------------------------------------------------- matching
def unique_anchor(xmap, pmap, method):
    """{feature: {funcs}} on both sides -> votes for features unique on both sides"""
    xi, pi = collections.defaultdict(set), collections.defaultdict(set)
    for f, feats in xmap.items():
        for k in feats:
            xi[k].add(f)
    for f, feats in pmap.items():
        for k in feats:
            pi[k].add(f)
    votes = collections.Counter()
    for k, xs in xi.items():
        ps = pi.get(k)
        if ps and len(xs) == 1 and len(ps) == 1:
            votes[(next(iter(xs)), next(iter(ps)))] += 1
    return votes


def resolve(votes, pairs, rev, method, conf_of, xsize, psize, ratio=(0.15, 6.0)):
    best = collections.defaultdict(list)
    for (x, p), n in votes.items():
        best[x].append((n, p))
    pbest = collections.defaultdict(list)
    for (x, p), n in votes.items():
        pbest[p].append((n, x))
    new = 0
    for x, cands in best.items():
        if x in pairs:
            continue
        cands.sort(reverse=True)
        n, p = cands[0]
        if len(cands) > 1 and cands[1][0] == n:
            continue
        if p in rev:
            continue
        pc = sorted(pbest[p], reverse=True)
        if pc[0][1] != x or (len(pc) > 1 and pc[1][0] == pc[0][0]):
            continue
        r = psize.get(p, 1) / float(max(1, xsize.get(x, 1)))
        if not (ratio[0] <= r <= ratio[1]):
            continue
        pairs[x] = (p, method, conf_of(n), n)
        rev[p] = x
        new += 1
    return new


def align(cx, cp, pairs, rev, votes):
    if not cx or not cp:
        return
    ka = ['M%x' % pairs[c][0] if c in pairs else 'U' for c in cx]
    kb = ['M%x' % c if c in rev else 'U' for c in cp]
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('equal', 'replace') and (i2 - i1) == (j2 - j1):
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if ka[i] == 'U' and kb[j] == 'U':
                    votes[(cx[i], cp[j])] += 1


def propagate(X, Pc, pairs, rev, vtmap):
    votes, vvotes = collections.Counter(), collections.Counter()
    for x, (p, *_r) in list(pairs.items()):
        align(X.calls.get(x, []), Pc.calls.get(p, []), pairs, rev, votes)          # callees in order
        align(X.fptrs.get(x, []), Pc.fptrs.get(p, []), pairs, rev, votes)          # function pointers (binders)
        ux = [c for c in X.callers.get(x, ()) if c not in pairs]                   # single unmatched caller
        up = [c for c in Pc.callers.get(p, ()) if c not in rev]
        if len(ux) == 1 and len(up) == 1:
            votes[(ux[0], up[0])] += 1
        xv, pv = X.vts.get(x, []), Pc.vts.get(p, [])                               # vtables built by the pair
        if xv and len(xv) == len(pv):
            for a, b in zip(xv, pv):
                vvotes[(a, b)] += 1
    for (a, b), n in vvotes.most_common():
        # slot counts may differ a little (the PC run of pointers stops at a slot whose target was not detected as
        # a function start); base-class slots come first, so the common prefix is paired
        if a not in vtmap and b not in vtmap.values() and abs(len(X.vt[a]) - len(Pc.vt[b])) <= 3:
            vtmap[a] = b
    for a, b in vtmap.items():
        w = 2 if len(X.vt[a]) == len(Pc.vt[b]) else 1
        for u, v in zip(X.vt[a], Pc.vt[b]):
            if u not in pairs and v not in rev:
                votes[(u, v)] += w
    return resolve(votes, pairs, rev, 'callgraph', lambda n: 'medium' if n >= 2 else 'low', X.size, Pc.size,
                   ratio=(0.2, 4.0))


def lis_pairs(pairs):
    """the longest chain of pairs increasing in both address orders (layout anchors)"""
    seq = sorted((x, p[0]) for x, p in pairs.items())
    tails, idx, prev = [], [], [None] * len(seq)
    for i, (x, p) in enumerate(seq):
        k = bisect.bisect_left(tails, p)
        if k == len(tails):
            tails.append(p); idx.append(i)
        else:
            tails[k] = p; idx[k] = i
        prev[i] = idx[k - 1] if k else None
    out, i = [], idx[-1] if idx else None
    while i is not None:
        out.append(seq[i]); i = prev[i]
    return out[::-1]


def layout_fill(X, Pc, pairs, rev, ratio_med):
    """functions keep their source order on both platforms: between two consecutive layout anchors, align the
    unmatched functions by size (dynamic programming; PC may have extra functions) and pair good fits"""
    chain = lis_pairs(pairs)
    xs, ps = X.starts, Pc.starts
    new = 0
    for (x1, p1), (x2, p2) in zip(chain, chain[1:]):
        gx = [f for f in xs[bisect.bisect_right(xs, x1):bisect.bisect_left(xs, x2)] if f not in pairs]
        gp = [f for f in ps[bisect.bisect_right(ps, p1):bisect.bisect_left(ps, p2)] if f not in rev]
        if not gx or not gp or len(gx) > 40 or len(gp) > 80:
            continue
        def cost(a, b):
            r = Pc.size[b] / float(max(1, X.size[a])) / ratio_med
            return abs(math.log(max(r, 1e-3)))
        n, m = len(gx), len(gp)
        INF = 1e9
        D = [[INF] * (m + 1) for _ in range(n + 1)]
        B = [[None] * (m + 1) for _ in range(n + 1)]
        D[0] = [0.6 * j for j in range(m + 1)]
        for i in range(1, n + 1):
            D[i][0] = 0.9 * i
            for j in range(1, m + 1):
                c = [(D[i - 1][j - 1] + cost(gx[i - 1], gp[j - 1]), 'm'), (D[i - 1][j] + 0.9, 'x'),
                     (D[i][j - 1] + 0.6, 'p')]
                D[i][j], B[i][j] = min(c)
        i, j = n, m
        while i > 0 and j > 0:
            b = B[i][j]
            if b == 'm':
                a, p = gx[i - 1], gp[j - 1]
                if cost(a, p) < 0.45:
                    pairs[a] = (p, 'layout', 'low', 1); rev[p] = a; new += 1
                i, j = i - 1, j - 1
            elif b == 'x':
                i -= 1
            else:
                j -= 1
    return new, len(chain)


def callee_agreement(X, Pc, pairs, x, p):
    cx = [pairs[c][0] for c in X.calls.get(x, []) if c in pairs]
    if not cx:
        return ''
    cp = set(Pc.calls.get(p, []))
    return '%d/%d' % (sum(1 for c in cx if c in cp), len(cx))


def tier(X, Pc, pairs, x):
    """verified: >= 2 matched callees and >= half of them agree; anchor: string / float pair without that
    evidence; unverified: the rest (most layout pairs) - a candidate, not a fact"""
    p, m, c, n = pairs[x]
    a = callee_agreement(X, Pc, pairs, x, p)
    if a:
        g, t = (int(v) for v in a.split('/'))
        if t >= 2 and 2 * g >= t:
            return 'verified'
        if t >= 2:
            return 'contradicted'
    return 'anchor' if m in ('string', 'float') else 'unverified'


def data_votes(pairs_list, glob_a, glob_b):
    votes = collections.Counter()
    for a, b in pairs_list:
        ga, gb = glob_a.get(a, []), glob_b.get(b, [])
        if ga and len(ga) == len(gb):
            for u, v in zip(ga, gb):
                votes[(u, v)] += 1
    best = {}
    for (u, v), n in votes.most_common():
        if u not in best:
            best[u] = (v, n)
    return best


def main(argv):
    disps, marks, datas = {0x1244}, set(), []
    if '--disp' in argv:
        k = argv.index('--disp'); disps = set(int(x, 0) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--mark' in argv:
        k = argv.index('--mark'); marks = set(int(x, 0) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--data' in argv:
        k = argv.index('--data'); datas = [int(x, 0) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if len(argv) != 4:
        sys.exit(__doc__)
    retail, tu, exe, out = argv[:4]
    os.makedirs(out, exist_ok=True)
    log = []
    say = lambda s: (print(s, flush=True), log.append(s))

    X = Xbox(retail)
    say('Xbox retail: %d functions, %d with strings, %d with floats' % (
        len(X.funcs), sum(1 for v in X.strs.values() if v), sum(1 for v in X.flts.values() if v)))
    Pc = PC(exe)
    Pc.build()
    say('PC: %d derived functions, %d strings in data, %d functions with strings' % (
        len(Pc.starts), len(Pc.strat), sum(1 for v in Pc.strs.values() if v)))

    pairs, rev = {}, {}
    v = unique_anchor(X.strs, Pc.strs, 'string')
    n = resolve(v, pairs, rev, 'string', lambda n: 'high' if n >= 2 else 'medium', X.size, Pc.size, ratio=(0.1, 10))
    say('string anchors: %d candidate pairs, %d accepted' % (len(v), n))
    v = unique_anchor(X.flts, Pc.flts, 'float')
    n = resolve(v, pairs, rev, 'float', lambda n: 'medium' if n >= 2 else 'low', X.size, Pc.size)
    say('float anchors: %d candidate pairs, %d accepted' % (len(v), n))
    both = [(x, p) for x, (p, *_r) in pairs.items() if X.vts.get(x) and Pc.vts.get(p)]
    say('vtables: Xbox %d (%d functions reference one), PC %d (%d functions); anchored pairs with vtables on both '
        'sides: %d, equal count %d' % (len(X.vt), sum(1 for v in X.vts.values() if v), len(Pc.vt),
                                       sum(1 for v in Pc.vts.values() if v), len(both),
                                       sum(1 for x, p in both if len(X.vts[x]) == len(Pc.vts[p]))))
    sl = collections.Counter()
    for x, p in both:
        for a, b in zip(X.vts[x], Pc.vts[p]):
            sl['same' if len(X.vt[a]) == len(Pc.vt[b]) else 'diff'] += 1
    say('  slot counts of positionally paired vtables: %s' % dict(sl))
    vtmap = {}
    for rnd in range(1, 60):
        n = propagate(X, Pc, pairs, rev, vtmap)
        say('callgraph round %d: %d new pairs (total %d, vtables paired %d)' % (rnd, n, len(pairs), len(vtmap)))
        if not n:
            break

    rs = sorted(Pc.size[p[0]] / float(max(1, X.size[x])) for x, p in pairs.items() if p[1] in ('string', 'float'))
    ratio_med = rs[len(rs) // 2] if rs else 1.0
    for rnd in range(1, 6):
        n, chain = layout_fill(X, Pc, pairs, rev, ratio_med)
        m = 0
        for r2 in range(1, 30):
            k = propagate(X, Pc, pairs, rev, vtmap)
            m += k
            if not k:
                break
        say('layout round %d: anchor chain %d of %d pairs, size ratio PC/Xbox median %.2f, %d layout pairs, %d more '
            'by callgraph (total %d)' % (rnd, chain, len(pairs), ratio_med, n, m, len(pairs)))
        if not n and not m:
            break

    by = collections.Counter(m for p, m, c, n in pairs.values())
    byc = collections.Counter(c for p, m, c, n in pairs.values())
    say('matched %d of %d retail functions (%.1f %%), %d of %d retail bytes; by method %s, by confidence %s' % (
        len(pairs), len(X.funcs), 100.0 * len(pairs) / len(X.funcs), sum(X.size[x] for x in pairs),
        sum(X.size.values()), dict(by), dict(byc)))

    with open(os.path.join(out, 'xbox_pc_map.tsv'), 'w', encoding='utf-8') as f:
        f.write('xbox_retail\tpc\tmethod\tconfidence\tvotes\txbox_size\tpc_size\tcallee_agreement\ttier\n')
        tiers = collections.Counter()
        for x in sorted(pairs):
            p, m, c, n = pairs[x]
            t = tier(X, Pc, pairs, x); tiers[t] += 1
            f.write('0x%08x\t0x%08x\t%s\t%s\t%d\t%d\t%d\t%s\t%s\n' % (x, p, m, c, n, X.size[x], Pc.size.get(p, 0),
                                                                        callee_agreement(X, Pc, pairs, x, p), t))
    say('tiers of all pairs: %s' % dict(tiers))

    # ---------------- TU -> retail (same pairing as xbox_func_diff)
    rd, rf, rh = XD.functions(retail)
    td, tf, th = XD.functions(tu)
    sm = difflib.SequenceMatcher(None, rh, th, autojunk=False)
    t2r, new = {}, []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                t2r[tf[j][0]] = (rf[i][0], 'equal')
        elif tag == 'insert':
            new += [f[0] for f in tf[j1:j2]]
        elif tag == 'replace':
            k = min(i2 - i1, j2 - j1)
            for q in range(k):
                t2r[tf[j1 + q][0]] = (rf[i1 + q][0], 'changed')
            new += [f[0] for f in tf[j1 + k:j2]]
    T = Xbox(tu)
    flagged = set(XD.disp_users(td, tf, disps))
    for fs, items in T.res.items():
        if any(k == 'addr' and v in marks for a, k, v in items):
            flagged.add(fs)
    roots = set(new) | flagged
    say('TU: %d new functions, %d flagged (disp %s / marks), %d roots' % (
        len(new), len(flagged), ','.join('0x%x' % x for x in sorted(disps)), len(roots)))
    callees = collections.Counter()
    for r in roots:
        for c in T.calls.get(r, []):
            callees[c] += 1
    rows, cls = [], collections.Counter()
    for c, n in callees.most_common():
        if c in roots and c in set(new):
            k, rr, pp = 'TU-new', None, None
        elif c in t2r:
            rr = t2r[c][0]
            pp = pairs.get(rr)
            k = ('pc ' + tier(X, Pc, pairs, rr)) if pp else 'missing'
        else:
            k, rr, pp = 'TU-new', None, None
        cls[k] += 1
        hint = ''
        if rr is not None:
            ss = sorted(X.strs.get(rr, []))
            hint = ss[0][:60] if ss else ''
        rows.append((c, n, k, rr, pp[0] if pp else None, T.size.get(c, 0), hint))
    with open(os.path.join(out, 'shadow_focus.tsv'), 'w', encoding='utf-8') as f:
        f.write('tu_callee\tcalled_from_roots\tclass\tretail\tpc\ttu_size\tstring_hint\n')
        for c, n, k, rr, pp, sz, hint in rows:
            f.write('0x%08x\t%d\t%s\t%s\t%s\t%d\t%s\n' % (c, n, k, ('0x%08x' % rr) if rr else '',
                                                            ('0x%08x' % pp) if pp else '', sz, hint))
    miss = [r for r in rows if r[2] == 'missing']
    say('callees of the roots: %d distinct - %s; missing retail callees %d (%d B TU size)' % (
        len(rows), dict(cls), len(miss), sum(r[5] for r in miss)))
    newsz = sum(T.size.get(x, 0) for x in new)
    say('to re-implement for PC: %d new TU functions (%d B PowerPC) + flagged changed ones; retail callees with a '
        'PC counterpart can be called directly' % (len(new), newsz))

    # ---------------- data globals: TU -> retail -> PC
    tr_pairs = [(t, r) for t, (r, k) in t2r.items()]
    dmap_tr = data_votes(tr_pairs, T.globs, X.globs)
    dmap_rp = data_votes([(x, p[0]) for x, p in pairs.items()], X.globs, Pc.globs)
    with open(os.path.join(out, 'xbox_pc_data.tsv'), 'w', encoding='utf-8') as f:
        f.write('xbox_retail_global\tpc_global\tvotes\n')
        for u in sorted(dmap_rp):
            f.write('0x%08x\t0x%08x\t%d\n' % (u, dmap_rp[u][0], dmap_rp[u][1]))
    say('data globals: %d retail -> PC by aligned references' % len(dmap_rp))
    for a in datas:
        r = dmap_tr.get(a)
        p = dmap_rp.get(r[0]) if r else None
        say('  TU 0x%08x -> retail %s -> PC %s' % (a, ('0x%08x (%d votes)' % r) if r else '?',
                                                   ('0x%08x (%d votes)' % p) if p else '?'))
    open(os.path.join(out, 'summary.txt'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
