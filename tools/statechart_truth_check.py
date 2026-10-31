"""Independent check of a re-converted state chart against ground truth taken from the base game (finding 43, state
chart conversion). Read-only.

Ground truth without any learned layout:
  exact  a block of the target Xbox DTP (relocation target up to the next target) whose bytes - pointer and id-ref
         words masked - are identical to a block of the base Xbox chart that is paired (along the pointer graph) with a
         base PC block of the same size: the correct PC bytes are that PC block's bytes. Used only when every such
         base block with these Xbox bytes has the same PC bytes.
  value  a word of a target block that has no exact twin: key (block shape = size + pointer / id-ref offsets, word
         offset in the block, Xbox word value); the correct PC word is the base PC word when every base observation
         of this key gives the same PC word and that word is a byte permutation of the Xbox word (re-authored values
         are left out).
Words with no truth are counted as 'unknown'. For BEFORE (the converted file) and AFTER (the re-converted file) each
known word is right or wrong; the report gives ok->ok, ok->bad (regressions), bad->ok, bad->bad, and the 'unknown'
words split into changed / unchanged by the fix.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/statechart_truth_check.py XREF.drm PCREF.drm XREF_ID PCREF_ID XBOX.drm SID BEFORE.drm AFTER.drm
        [--list N] [--sid-pc SID]
  e.g. work/rockvein/ref/x_lara.drm work/rockvein/ref/pc_lara.drm 12647 850 work/rockvein/ref/x_doppelganger_casual.drm
       20212 work/rebuild/dlc2_asm_stage2b/mods/doppelganger_casual.drm work/rockvein/fix/doppelganger_casual.drm
"""
import sys, os, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PERMS = ((0, 1, 2, 3), (3, 2, 1, 0), (1, 0, 3, 2), (1, 0, 2, 3), (0, 1, 3, 2))


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7:
            r = R.parse(bytes(s.reloc), e)
            return bytes(s.data), dict(r.internal), set(r.pointer_offsets()), set(r.id_offsets())
    raise SystemExit('DTP %d not in %s' % (sid, path))


class Chart:
    def __init__(self, d, internal, ptr, idw):
        self.d, self.internal, self.mask = d, internal, ptr | idw
        self.starts = sorted(set(internal.values()) | {0})
        self.end = {a: (self.starts[k + 1] if k + 1 < len(self.starts) else len(d)) for k, a in enumerate(self.starts)}
        self.fields = collections.defaultdict(dict)        # block -> {field offset: target}
        for o, t in internal.items():
            b = self.starts[bisect.bisect_right(self.starts, o) - 1]
            self.fields[b][o - b] = t

    def shape(self, b):
        return (self.end[b] - b, tuple(r for r in range(0, self.end[b] - b, 4) if b + r in self.mask))

    def content(self, b):
        """block bytes with masked words zeroed"""
        x = bytearray(self.d[b:self.end[b]])
        for r in range(0, len(x), 4):
            if b + r in self.mask: x[r:r + 4] = b'\0\0\0\0'
        return bytes(x)


def main(argv):
    nlist = 15
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    X = Chart(*load(argv[0], 'be', int(argv[2]))); P = Chart(*load(argv[1], 'le', int(argv[3])))
    # pair base blocks along the pointer graph
    pairs = {0: 0}; order = [0]; i = 0
    while i < len(order):
        xb = order[i]; i += 1; pb = pairs[xb]
        pf = P.fields.get(pb, {})
        for f, t in sorted(X.fields.get(xb, {}).items()):
            if t in pairs or f not in pf: continue
            pairs[t] = pf[f]; order.append(t)
    exact = collections.defaultdict(set)           # (shape, xbox content) -> {pc content}
    value = collections.defaultdict(set)           # (shape, r, xbox word) -> {pc word}
    npair = 0
    for xb, pb in pairs.items():
        if X.end[xb] - xb != P.end[pb] - pb: continue
        sx = X.shape(xb)
        if sx != P.shape(pb): continue
        npair += 1
        exact[sx, X.content(xb)].add(P.content(pb))
        for r in range(0, sx[0] - 3, 4):
            if r in sx[1]: continue
            xw = X.d[xb + r:xb + r + 4]; pw = P.d[pb + r:pb + r + 4]
            value[sx, r, xw].add(pw if any(bytes(xw[j] for j in q) == pw for q in PERMS) else None)
    print('base: %d blocks paired, %d with the same shape; %d exact contents (%d unambiguous), %d value keys '
          '(%d unambiguous)' % (len(pairs), npair, len(exact), sum(1 for v in exact.values() if len(v) == 1), len(value),
                               sum(1 for v in value.values() if len(v) == 1 and None not in v)))
    T = Chart(*load(argv[4], 'be', int(argv[5])))
    B = load(argv[6], 'le', int(argv[5]))[0]; A = load(argv[7], 'le', int(argv[5]))[0]
    if not (len(T.d) == len(B) == len(A)): raise SystemExit('sizes differ')
    st = collections.Counter(); by = collections.defaultdict(collections.Counter); reg = []
    for b in T.starts:
        sh = T.shape(b)
        tr = exact.get((sh, T.content(b)))
        how = 'exact' if tr is not None and len(tr) == 1 else None
        want = next(iter(tr)) if how else None
        for r in range(0, sh[0] - 3, 4):
            o = b + r
            if r in sh[1]: continue
            st['words'] += 1
            if how: w = want[r:r + 4]; kind = 'exact'
            else:
                v = value.get((sh, r, T.d[o:o + 4]))
                if v is not None and len(v) == 1 and None not in v: w = next(iter(v)); kind = 'value'
                else: w = None; kind = 'unknown'
            if w is None:
                st['unknown_' + ('changed' if B[o:o + 4] != A[o:o + 4] else 'same')] += 1; continue
            k = ('ok' if B[o:o + 4] == w else 'bad') + '->' + ('ok' if A[o:o + 4] == w else 'bad')
            by[kind][k] += 1
            if k == 'ok->bad': reg.append((o, b, kind, T.d[o:o + 4].hex(), B[o:o + 4].hex(), A[o:o + 4].hex(), w.hex()))
            if k == 'bad->bad' and kind == 'exact': st['exact_badbad_list'] += 1
    print('target: %d data words' % st['words'])
    for kind in ('exact', 'value'):
        c = by[kind]
        print('  %-5s truth: %6d words  ok->ok %6d  ok->bad %5d  bad->ok %6d  bad->bad %5d'
              % (kind, sum(c.values()), c['ok->ok'], c['ok->bad'], c['bad->ok'], c['bad->bad']))
    print('  no truth: %d words (%d changed by the fix, %d unchanged)' % (st['unknown_changed'] + st['unknown_same'],
                                                                         st['unknown_changed'], st['unknown_same']))
    for o, b, kind, x, bb, aa, w in reg[:nlist]:
        print('  REGRESSION +0x%05x (block +0x%05x, %s): xbox %s before %s after %s truth %s' % (o, b, kind, x, bb, aa, w))
    if '--badbad' in sys.argv:
        n = 0
        for b in T.starts:
            sh = T.shape(b)
            tr = exact.get((sh, T.content(b)))
            if not (tr is not None and len(tr) == 1): continue
            want = next(iter(tr))
            for r in range(0, sh[0] - 3, 4):
                o = b + r
                if r in sh[1] or A[o:o + 4] == want[r:r + 4]: continue
                n += 1
                if n <= nlist:
                    print('  STILL WRONG +0x%05x (block +0x%05x size 0x%x r 0x%x): xbox %s after %s truth %s'
                          % (o, b, sh[0], r, T.d[o:o + 4].hex(), A[o:o + 4].hex(), want[r:r + 4].hex()))


if __name__ == '__main__':
    main(sys.argv[1:])
