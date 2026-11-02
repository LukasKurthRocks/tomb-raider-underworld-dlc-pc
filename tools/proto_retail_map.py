"""Name map: 2007 prototype (tr8_Content, with linker map) -> Xbox retail -> PC tru.exe (read-only; Befund-Prototyp-2007).

The prototype of 16.08.2007 is the only TR8 Xbox build with symbol names (tools/proto_symbols.py). Its code is
14 months older than retail, so functions are paired by evidence, never by name or address, with confidence tiers:
  * exact     - identical body after masking only what relinking moves (b/bl targets, lis/addi/ori/ld/st halves of
                global addresses tracked from a lis): structure offsets, constants and control flow are equal; the
                hash is unique on both sides and the function has >= 8 instructions
  * shape     - same body with ALL 16-bit immediates / displacements masked (tools/xbox_func_diff.norm_hash),
                unique on both sides, >= 12 instructions (struct offsets may differ)
  * string    - both reference the same string that only one function per image references
  * float     - the same unusual float constant, unique on both sides
  * callgraph - propagated from pairs (ordered callees aligned, function-pointer lists, single unmatched caller,
                vtable slots), tools/xbox_pc_funcmap.align / resolve, size ratio 0.5..2
  * similar   - between consecutive pairs (longest chain in both address orders), unmatched functions with an
                instruction-shape similarity (difflib ratio of opcode tokens) >= 0.78 and 0.05 ahead of the runner-up
                (ratio >= 0.90 counts like an anchor, tier C)
  * layout    - source order kept between consecutive pairs, gaps aligned by size (weak)
Tier per pair: A exact; B verified (>= 2 paired callees that are callees of the retail partner, >= half of all);
C anchor (string / float / shape / similarity >= 0.90, or both address neighbours paired the same way);
D unverified (single-vote callgraph / layout); callgraph runs first with >= 2 votes, then with single votes;
X contradicted (callees disagree). The retail address is then chained to PC with work/xmap/xbox_pc_map.tsv
(its own method / tier are carried along) and, for globals, xbox_pc_data.tsv.
Data globals proto -> retail are voted from the ordered global references of A/B pairs (the same position in
identical code = the same variable).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/proto_retail_map.py PROTO.pe MAP RETAIL.bin XMAP_DIR OUT_DIR
  e.g. ../bin/pyt -t 3600 tools/proto_retail_map.py work/proto2007/pe/content/tr8_Content.pe \
          work/proto2007/map/tr8_Content.map work/xenia_dump/retail_image_82000000.bin work/xmap work/proto2007
Outputs in OUT_DIR: proto_retail_pc_names.tsv (functions), proto_retail_pc_data.tsv (globals), name_map_summary.txt.
Only addresses, names, methods and counts are written - no game bytes.
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import xbox_func_diff as XD
import xbox_pc_funcmap as FM
import proto_symbols as PS

BASE = 0x82000000


def strict_hash(d, fs, fe):
    """mask only relink-dependent bits: branch targets of b/bl, and the immediates of instructions whose base
    register was loaded by lis (global addresses); keep struct displacements and constants"""
    h = hashlib.md5()
    hi = set()
    for a in range(fs, fe, 4):
        w = struct.unpack_from('>I', d, a - BASE)[0]
        op = w >> 26
        rd, ra = (w >> 21) & 31, (w >> 16) & 31
        if op == 18:
            w &= 0xfc000003
        elif op == 15 and ra == 0:
            w &= 0xffff0000
            hi.add(rd)
        elif op in (14, 24, 25) or op in P.LOADSTORE:
            base = ra if op in (14,) or op in P.LOADSTORE else rd   # ori/oris: source reg is the rs field
            if base in hi:
                w &= 0xffff0000
            dest = rd if op in (14,) or (op in P.LOADSTORE and (op < 36 or 40 <= op < 44 or 48 <= op < 52)) \
                else (ra if op in (24, 25) else None)
            if dest is not None and dest != base:
                hi.discard(dest)
        else:
            if op in (31, 21, 20, 28, 29, 7, 8, 12, 13):
                hi.discard(ra if op in (31, 21, 20, 28, 29) else rd)
                hi.discard(rd)
        h.update(struct.pack('>I', w))
    return h.hexdigest()[:20] + ':%d' % ((fe - fs) // 4)


def hash_anchor(X, R, fn, min_insn, pairs, rev, method):
    hx, hr = collections.defaultdict(list), collections.defaultdict(list)
    for s, e in X.funcs:
        if (e - s) // 4 >= min_insn:
            hx[fn(X.d, s, e)].append(s)
    for s, e in R.funcs:
        if (e - s) // 4 >= min_insn:
            hr[fn(R.d, s, e)].append(s)
    n = 0
    for k, xs in hx.items():
        rs = hr.get(k)
        if rs and len(xs) == 1 and len(rs) == 1 and xs[0] not in pairs and rs[0] not in rev:
            pairs[xs[0]] = (rs[0], method, 'high' if method == 'exact' else 'medium', 1)
            rev[rs[0]] = xs[0]
            n += 1
    return n


def propagate(X, R, pairs, rev, vtmap, minv=1):
    votes, vvotes = collections.Counter(), collections.Counter()
    for x, (p, *_r) in list(pairs.items()):
        FM.align(X.calls.get(x, []), R.calls.get(p, []), pairs, rev, votes)
        FM.align(X.fptrs.get(x, []), R.fptrs.get(p, []), pairs, rev, votes)
        ux = [c for c in X.callers.get(x, ()) if c not in pairs]
        up = [c for c in R.callers.get(p, ()) if c not in rev]
        if len(ux) == 1 and len(up) == 1:
            votes[(ux[0], up[0])] += 1
        xv, pv = X.vts.get(x, []), R.vts.get(p, [])
        if xv and len(xv) == len(pv):
            for a, b in zip(xv, pv):
                vvotes[(a, b)] += 1
    for (a, b), n in vvotes.most_common():
        if a not in vtmap and b not in vtmap.values() and abs(len(X.vt[a]) - len(R.vt[b])) <= 3:
            vtmap[a] = b
    for a, b in vtmap.items():
        w = 2 if len(X.vt[a]) == len(R.vt[b]) else 1
        for u, v in zip(X.vt[a], R.vt[b]):
            if u not in pairs and v not in rev:
                votes[(u, v)] += w
    if minv > 1:
        votes = collections.Counter(dict((k, v) for k, v in votes.items() if v >= minv))
    return FM.resolve(votes, pairs, rev, 'callgraph', lambda n: 'medium' if n >= 2 else 'low', X.size, R.size,
                      ratio=(0.5, 2.0))


def op_tokens(d, fs, fe):
    """instruction shape tokens: primary opcode (+ extended opcode for the X/XO/A forms)"""
    out = []
    for a in range(fs, fe, 4):
        w = struct.unpack_from('>I', d, a - BASE)[0]
        op = w >> 26
        if op in (31, 63, 19, 30):
            out.append((op << 10) | ((w >> 1) & 0x3ff))
        elif op in (59, 4):
            out.append((op << 10) | ((w >> 1) & 0x1f))
        else:
            out.append(op << 10)
    return out


def similar_fill(X, R, pairs, rev, tok_x, tok_r, thr=0.78, margin=0.05, cap=120):
    """between consecutive layout anchors (longest chain increasing in both orders), pair unmatched functions by
    instruction-shape similarity (difflib ratio); accepted only above thr and clearly better than the runner-up"""
    import difflib, bisect as bs
    chain = FM.lis_pairs(pairs)
    new = 0
    for (x1, r1), (x2, r2) in zip(chain, chain[1:]):
        gx = [f for f in X.starts[bs.bisect_right(X.starts, x1):bs.bisect_left(X.starts, x2)] if f not in pairs]
        gr = [f for f in R.starts[bs.bisect_right(R.starts, r1):bs.bisect_left(R.starts, r2)] if f not in rev]
        if not gx or not gr or len(gx) > cap or len(gr) > cap:
            continue
        cand = []
        for a in gx:
            ta = tok_x(a)
            if len(ta) < 6:
                continue
            for b in gr:
                r = R.size[b] / float(max(1, X.size[a]))
                if not (0.6 <= r <= 1.67):
                    continue
                tb = tok_r(b)
                sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
                if sm.real_quick_ratio() < thr or sm.quick_ratio() < thr:
                    continue
                s = sm.ratio()
                if s >= thr - margin:
                    cand.append((s, a, b))
        best_a, best_b = collections.defaultdict(list), collections.defaultdict(list)
        for s, a, b in cand:
            best_a[a].append(s)
            best_b[b].append(s)
        for s, a, b in sorted(cand, reverse=True):
            if s < thr or a in pairs or b in rev:
                continue
            sa = sorted(best_a[a], reverse=True)
            sb = sorted(best_b[b], reverse=True)
            if (len(sa) > 1 and sa[1] > s - margin) or (len(sb) > 1 and sb[1] > s - margin):
                continue
            pairs[a] = (b, 'similar', 'medium' if s >= 0.9 else 'low', int(round(100 * s)))
            rev[b] = a
            new += 1
    return new


def run_prop(X, R, pairs, rev, vtmap):
    """callgraph propagation to a fixpoint, first with >= 2 votes per pair, then with single votes"""
    total = 0
    for minv in (2, 1):
        for rnd in range(1, 60):
            n = propagate(X, R, pairs, rev, vtmap, minv)
            total += n
            if not n:
                break
    return total


def neighbours(X, R, pairs, x):
    """how many of the address neighbours (previous / next function) are paired with the partner's neighbours"""
    import bisect as bs
    p = pairs[x][0]
    i, j = bs.bisect_left(X.starts, x), bs.bisect_left(R.starts, p)
    n = 0
    for di in (-1, 1):
        if 0 <= i + di < len(X.starts) and 0 <= j + di < len(R.starts):
            q = pairs.get(X.starts[i + di])
            if q and q[0] == R.starts[j + di]:
                n += 1
    return n


def tier(X, R, pairs, x):
    """A exact; B >= 2 paired callees agree and they are at least half; X more than half disagree (>= 2);
    C anchors (string / float / shape / similarity >= 0.90) or both address neighbours paired consistently; D rest"""
    p, m, c, n = pairs[x]
    if m == 'exact':
        return 'A'
    a = FM.callee_agreement(X, R, pairs, x, p)
    if a:
        g, t = (int(v) for v in a.split('/'))
        if g >= 2 and 2 * g >= t:
            return 'B'
        if t >= 2 and 2 * g < t:
            return 'X'
    if m == 'similar' and n >= 90:
        return 'C'
    if m in ('string', 'float', 'shape') or neighbours(X, R, pairs, x) == 2:
        return 'C'
    return 'D'


def read_tsv(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            v = line.rstrip('\n').split('\t')
            rows[int(v[0], 16)] = dict(zip(head, v))
    return rows


def main(argv):
    if len(argv) != 5:
        sys.exit(__doc__)
    proto, mapf, retail, xmap, out = argv
    log = []
    say = lambda s: (print(s, flush=True), log.append(s))
    X = FM.Xbox(proto)
    R = FM.Xbox(retail)
    say('prototype: %d functions (%d B); retail: %d functions (%d B)' % (
        len(X.funcs), sum(X.size.values()), len(R.funcs), sum(R.size.values())))
    pairs, rev = {}, {}
    say('exact (strict hash, >= 8 insns): %d' % hash_anchor(X, R, strict_hash, 8, pairs, rev, 'exact'))
    say('shape (loose hash, >= 12 insns): %d' % hash_anchor(X, R, XD.norm_hash, 12, pairs, rev, 'shape'))
    v = FM.unique_anchor(X.strs, R.strs, 'string')
    say('string anchors: %d candidates, %d accepted' % (len(v), FM.resolve(
        v, pairs, rev, 'string', lambda n: 'high' if n >= 2 else 'medium', X.size, R.size, ratio=(0.25, 4))))
    v = FM.unique_anchor(X.flts, R.flts, 'float')
    say('float anchors: %d candidates, %d accepted' % (len(v), FM.resolve(
        v, pairs, rev, 'float', lambda n: 'medium' if n >= 2 else 'low', X.size, R.size, ratio=(0.4, 2.5))))
    vtmap = {}
    n = run_prop(X, R, pairs, rev, vtmap)
    say('callgraph: %d new, total %d pairs, vtables paired %d' % (n, len(pairs), len(vtmap)))
    tx, tr = {}, {}
    tok_x = lambda a: tx.setdefault(a, op_tokens(X.d, a, a + X.size[a]))
    tok_r = lambda b: tr.setdefault(b, op_tokens(R.d, b, b + R.size[b]))
    for rnd in range(1, 6):
        n = similar_fill(X, R, pairs, rev, tok_x, tok_r)
        m = run_prop(X, R, pairs, rev, vtmap)
        say('similar round %d: %d similarity pairs, %d more by callgraph (total %d)' % (rnd, n, m, len(pairs)))
        if not n and not m:
            break
    for rnd in range(1, 6):
        n, chain = FM.layout_fill(X, R, pairs, rev, 1.0)
        m = run_prop(X, R, pairs, rev, vtmap)
        say('layout round %d: chain %d, %d layout pairs, %d more by callgraph (total %d)' % (rnd, chain, n, m,
                                                                                            len(pairs)))
        if not n and not m:
            break

    tiers = dict((x, tier(X, R, pairs, x)) for x in pairs)
    xp = read_tsv(os.path.join(xmap, 'xbox_pc_map.tsv'))
    xd = read_tsv(os.path.join(xmap, 'xbox_pc_data.tsv'))
    say('pairs by method: %s' % dict(collections.Counter(p[1] for p in pairs.values())))
    say('pairs by tier: %s' % dict(sorted(collections.Counter(tiers.values()).items())))
    reach = collections.Counter(tiers[x] for x in pairs if pairs[x][0] in xp)
    say('chained to PC (retail partner in xbox_pc_map.tsv): %d; by proto tier %s' % (
        sum(reach.values()), dict(sorted(reach.items()))))

    syms = PS.load_map(mapf)
    names = collections.defaultdict(list)
    for va, raw, obj, fn, sec, static in syms:
        if fn:
            names[va].append((PS.demangle(raw), obj, raw))
    named = 0
    with open(os.path.join(out, 'proto_retail_pc_names.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('name\tobj\tproto\tsize\tretail\tmethod\ttier\tcallee_agreement\tneighbours\tpc\tpc_method\tpc_tier\n')
        for s, e in X.funcs:
            ns = names.get(s) or [('?', '-', '')]
            pr = pairs.get(s)
            ra = pr[0] if pr else None
            pc = xp.get(ra) if ra is not None else None
            for nm, obj, raw in ns:
                f.write('%s\t%s\t0x%08x\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    nm, obj, s, e - s, ('0x%08x' % ra) if pr else '', pr[1] if pr else '',
                    tiers[s] if pr else '', FM.callee_agreement(X, R, pairs, s, ra) if pr else '',
                    neighbours(X, R, pairs, s) if pr else '',
                    pc['pc'] if pc else '', pc['method'] if pc else '', pc['tier'] if pc else ''))
            if names.get(s):
                named += 1
    say('named prototype functions written: %d (with retail partner %d)' % (
        named, sum(1 for s in pairs if s in names)))

    # data globals from the strongest pairs only
    strong = [(x, p[0]) for x, p in pairs.items() if tiers[x] in ('A', 'B')]
    dm = FM.data_votes(strong, X.globs, R.globs)
    dnames = collections.defaultdict(list)
    for va, raw, obj, fn, sec, static in syms:
        if not fn and not raw.startswith('??_C@') and not raw.startswith('__'):
            dnames[va].append((PS.demangle(raw), obj))
    keys = sorted(set(va for va, raw, obj, fn, sec, static in syms if not fn))
    import bisect
    nd = 0
    with open(os.path.join(out, 'proto_retail_pc_data.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('proto\tname\tobj\tretail\tvotes\tpc\tpc_votes\n')
        for u in sorted(dm):
            r, n = dm[u]
            if u in dnames:
                nm, obj = dnames[u][0]
            else:
                i = bisect.bisect_right(keys, u) - 1
                base = keys[i] if i >= 0 else None
                nm, obj = ('%s+0x%x' % (dnames[base][0][0], u - base), dnames[base][0][1]) \
                    if base in dnames and u - base < 0x2000 else ('?', '-')
            pc = xd.get(r)
            f.write('0x%08x\t%s\t%s\t0x%08x\t%d\t%s\t%s\n' % (u, nm, obj, r, n, pc['pc_global'] if pc else '',
                                                           pc['votes'] if pc else ''))
            nd += 1
    say('data globals proto -> retail (A/B pairs): %d, of these with PC: %d' % (
        nd, sum(1 for u in dm if dm[u][0] in xd)))
    open(os.path.join(out, 'name_map_summary.txt'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
