"""Typed re-conversion of a state chart DTP learned from the base game's Xbox/PC pair along the pointer graph
(finding 43, rock vein: DLC 2 doppelganger_casual.drm DTP 20212 vs base lara.drm 12647 (Xbox) / 850 (PC)).
Read-only unless --out is given.

Method:
  * A block = a relocation target up to the next target. The root block (offset 0) has key 'R'. A pointer at offset f
    of a block with key K leads to a child block with key (K, f); if the parent consists of pointers only (a pointer
    list), every child gets (K, '*'). Blocks are keyed in breadth-first order, first key wins.
  * Reference pairing: the Xbox and PC base charts are walked together (same pointer offsets); for every pair of blocks
    with the same size each non-pointer word votes for the byte permutations that turn the Xbox bytes into the PC bytes
    ('32' u32 swap, '16' two u16 swaps, '16=' u16 + two bytes, '=16' two bytes + u16, '=' raw bytes).
  * A (key, word offset) is LEARNED when exactly one permutation agrees with every vote and at least one vote was
    unambiguous (all-zero words prove nothing). Variable-length blocks (lists) are also learned per element: the
    word offset is taken modulo the block's element period when the reference shows one (--period auto: the smallest
    period p in 4..32 for which all same-key blocks agree).
  * Target: the Xbox chart is walked the same way; every word at a learned (key, offset) is re-converted from the Xbox
    bytes with the learned permutation (pointer / id-ref words are never touched). Everything else stays as it is.
  * Check: the condition records found by tools/statechart_cond_fix.py's proven rule must come out identical.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/statechart_typed.py XREF.drm PCREF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID [--out OUT.drm]
       [--show N]
"""
import sys, os, struct, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PERMS = {'32': (3, 2, 1, 0), '16': (1, 0, 3, 2), '16=': (1, 0, 2, 3), '=16': (0, 1, 3, 2), '=': (0, 1, 2, 3)}


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7:
            r = R.parse(bytes(s.reloc), e)
            return D, s, bytes(s.data), dict(r.internal), set(r.pointer_offsets()) | set(r.id_offsets())
    raise SystemExit('DTP %d not in %s' % (sid, path))


def blocks(size, internal):
    t = sorted(set(internal.values()) | {0})
    ends = {a: (t[k + 1] if k + 1 < len(t) else size) for k, a in enumerate(t)}
    return ends


def walk(size, internal, ptrs):
    """{block start: key}, {block start: end}"""
    ends = blocks(size, internal)
    byblock = collections.defaultdict(list)          # block start -> [(field offset, target)]
    starts = sorted(ends)
    for o, t in internal.items():
        k = bisect.bisect_right(starts, o) - 1
        if k >= 0: byblock[starts[k]].append((o - starts[k], t))
    key = {0: ('R',)}
    order = [0]
    i = 0
    while i < len(order):
        b = order[i]; i += 1
        fields = sorted(byblock.get(b, ()))
        plist = len(fields) >= 3 and len(fields) * 4 >= (ends[b] - b) - 4
        for f, t in fields:
            if t in key: continue
            key[t] = key[b] + (('*',) if plist else (f,))
            order.append(t)
    return key, ends, byblock


def perms_ok(x, p):
    return [n for n, q in PERMS.items() if bytes(x[j] for j in q) == p]


def main(argv):
    out = None; show = 10; check_img = None
    if '--check' in argv: k = argv.index('--check'); check_img = argv[k + 1]; del argv[k:k + 2]
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    _, _, xr, xri, xrp = load(argv[0], 'be', int(argv[2]))
    _, _, pr, pri, prp = load(argv[1], 'le', int(argv[3]))
    xk, xe, xby = walk(len(xr), xri, xrp)
    pk, pe, pby = walk(len(pr), pri, prp)
    # pair reference blocks along the pointer graph
    pairs = {0: 0}; order = [0]; i = 0
    while i < len(order):
        xb = order[i]; pb = pairs[xb]; i += 1
        pf = dict(pby.get(pb, ()))
        for f, t in xby.get(xb, ()):
            if t in pairs or f not in pf: continue
            pairs[t] = pf[f]; order.append(t)
    obs = collections.defaultdict(list)          # key -> [(r, frozenset(perms))] informative observations
    sizes = collections.defaultdict(set)
    paired_same = 0
    allp = frozenset(PERMS)
    for xb, pb in pairs.items():
        if xe[xb] - xb != pe[pb] - pb or xb not in xk: continue
        paired_same += 1
        K = xk[xb]; sizes[K].add(xe[xb] - xb)
        for r in range(0, xe[xb] - xb - 3, 4):
            if xb + r in xrp or pb + r in prp: continue
            ok = frozenset(perms_ok(xr[xb + r:xb + r + 4], pr[pb + r:pb + r + 4]))
            obs[K].append((r, ok))                      # empty set = no permutation fits (re-authored word)

    def classes(K, p):
        """{class: intersection of perm sets} or None on a conflict / a word no permutation explains"""
        cl = {}; remap = set()
        for r, ok in obs[K]:
            c = r % p if p else r
            if not ok: remap.add(c); continue           # value changed by more than a byte order (id remap, re-authored)
            cl[c] = cl.get(c, allp) & ok
            if not cl[c]: return None
        for c in remap: cl[c] = allp                    # never touched
        return cl
    learned = {}; period = {}
    nconf = 0
    for K in obs:
        mx = max(sizes[K])
        best = None
        for p in range(4, min(0x100, mx // 2) + 1, 4):
            cl = classes(K, p)
            if cl is not None: best = (p, cl); break
        if best is None:
            cl = classes(K, 0)
            if cl is None: nconf += 1; continue
            best = (0, cl)
        period[K] = best[0]
        for c, s in best[1].items():
            if s == allp: continue                       # nothing informative
            learned[K, c] = next(iter(s)) if len(s) == 1 else tuple(sorted(s))
    # second key: the block's shape (size + relative pointer offsets) - for blocks whose path key differs in the
    # target; learned only where every reference block of that shape agrees
    def shape(byb, b, end):
        return (end - b, tuple(sorted(f for f, _ in byb.get(b, ()))))
    sobs = collections.defaultdict(list)
    for xb, pb in pairs.items():
        if xe[xb] - xb != pe[pb] - pb: continue
        S = ('S',) + shape(xby, xb, xe[xb])
        for r in range(0, xe[xb] - xb - 3, 4):
            if xb + r in xrp or pb + r in prp: continue
            sobs[S].append((r, frozenset(perms_ok(xr[xb + r:xb + r + 4], pr[pb + r:pb + r + 4]))))
    nshape = 0
    for S, lst in sobs.items():
        cl = {}; bad = False; remap = set()
        for r, ok in lst:
            if not ok: remap.add(r); continue
            cl[r] = cl.get(r, allp) & ok
            if not cl[r]: bad = True; break
        if bad: continue
        nshape += 1
        for r, s in cl.items():
            if s != allp and r not in remap: learned[S, r] = next(iter(s)) if len(s) == 1 else tuple(sorted(s))
    print('shape keys: %d of %d consistent' % (nshape, len(sobs)))
    print('reference: %d blocks paired, %d with equal size; %d keys (%d periodic, %d with a conflict = skipped); '
          '%d slots learned (%d single, %d multi)'
          % (len(pairs), paired_same, len(obs), sum(1 for p in period.values() if p), nconf, len(learned),
             sum(1 for v in learned.values() if isinstance(v, str)), sum(1 for v in learned.values() if not isinstance(v, str))))
    # target
    XD, xs, xd, xdi, xdp = load(argv[4], 'be', int(argv[6]))
    PD, ps, pd, pdi, pdp = load(argv[5], 'le', int(argv[6]))
    if len(xd) != len(pd): raise SystemExit('target sizes differ')
    tk, te, tby = walk(len(xd), xdi, xdp)
    newd = bytearray(pd)
    covered = changed = multi_used = by_shape = 0; unknown = 0; nwords = 0
    for b, K in tk.items():
        p = period.get(K)
        fixed_ok = p == 0 and (te[b] - b) in sizes.get(K, ())
        for r in range(0, te[b] - b - 3, 4):
            o = b + r
            if o in xdp or o in pdp: continue
            nwords += 1
            if p: m = learned.get((K, r % p))
            elif fixed_ok: m = learned.get((K, r))
            else: m = None
            if m is None:
                m = learned.get((('S',) + shape(tby, b, te[b]), r))
                if m is not None: by_shape += 1
            if m is None: unknown += 1; continue
            x = xd[o:o + 4]
            if isinstance(m, tuple):
                outs = {bytes(x[j] for j in PERMS[n]) for n in m}
                if len(outs) != 1: unknown += 1; continue
                y = outs.pop(); multi_used += 1
            else:
                y = bytes(x[j] for j in PERMS[m])
            covered += 1
            if bytes(newd[o:o + 4]) != y:
                changed += 1
                if changed <= show:
                    print('  +0x%05x key %s r 0x%x  %s: PC %s -> %s' % (o, '/'.join(str(z) for z in K[-3:]), r, m,
                                                                      bytes(newd[o:o + 4]).hex(), y.hex()))
                newd[o:o + 4] = y
    print('target: %d blocks keyed of %d, %d data words, %d covered by learned slots (%d by shape), %d changed, %d not covered'
          % (len(tk), len(te), nwords, covered, by_shape, changed, unknown))
    if check_img:
        # independent check on the words whose truth is known: the condition records of statechart_cond_fix's rule
        import statechart_cond_fix as SC
        ids = SC.tu_ids(open(check_img, 'rb').read())
        recs = SC.records(xd, '>', ids, xdp | pdp)
        st = collections.Counter()
        for o, k, i, v, f6, f7 in recs:
            want = struct.pack('<3H', k, i, v) + bytes((f6, f7))
            for w in (0, 4):
                before = pd[o + w:o + w + 4] == want[w:w + 4]; after = bytes(newd[o + w:o + w + 4]) == want[w:w + 4]
                st[('ok' if before else 'bad') + '->' + ('ok' if after else 'bad')] += 1
        print('check on %d condition records (%d words): %s' % (len(recs), 2 * len(recs),
              ', '.join('%s %d' % kv for kv in sorted(st.items()))))
    if out:
        ps.data = bytes(newd)
        raw = PD.write('le')
        if open(argv[5], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out, 'wb').write(raw)
        DW.read(open(out, 'rb').read(), 'le')
        print('written %s' % out)


if __name__ == '__main__':
    main(sys.argv[1:])
