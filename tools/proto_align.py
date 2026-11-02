"""Local side-by-side alignment of one prototype object file (address range) with a retail address range
(read-only; docs/Befund-Prototyp-2007.md).

Where the global name map (tools/proto_retail_map.py) leaves gaps, an object file's functions usually still sit in
the same order in retail. This tool lists the prototype functions of PROTO_FROM..PROTO_TO and the retail functions of
RETAIL_FROM..RETAIL_TO and aligns the two sequences by dynamic programming over instruction-shape similarity
(difflib ratio of opcode tokens, tools/proto_retail_map.op_tokens) with gap costs; existing pairs of the global map are
forced. Each output row: prototype name / size, retail address / size, similarity, the global map's pair (if any) and
the retail function's PC partner from work/xmap/xbox_pc_map.tsv. A row is evidence for a manual pair only when the
similarity is high AND it sits between forced pairs; the tool decides nothing.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/proto_align.py PROTO_FROM PROTO_TO RETAIL_FROM RETAIL_TO
  e.g. ../bin/pyt -t 600 tools/proto_align.py 0x82345238 0x82346660 0x82248600 0x82249200      (srmusic.obj)
"""
import sys, os, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import proto_retail_map as M
import proto_chain as PCH


def funcs_in(path, a, b):
    d, secs = P.load(path)
    funcs, res = P.cached(path)
    return d, [(s, e) for s, e in funcs if a <= s < b]


def main(argv):
    if len(argv) != 4:
        sys.exit(__doc__)
    pa, pb, ra, rb = (int(x, 16) for x in argv)
    C = PCH.Chain()
    xd, xf = funcs_in(PCH.PROTO, pa, pb)
    rd, rf = funcs_in(PCH.RETAIL, ra, rb)
    xt = [M.op_tokens(xd, s, e) for s, e in xf]
    rt = [M.op_tokens(rd, s, e) for s, e in rf]
    forced = {}
    for i, (s, e) in enumerate(xf):
        rows = C.by_proto.get(s, [])
        if rows and rows[0]['retail']:
            forced[i] = int(rows[0]['retail'], 16)
    n, m = len(xf), len(rf)
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            r = (rf[j][1] - rf[j][0]) / float(max(1, xf[i][1] - xf[i][0]))
            if i in forced:
                sim[i][j] = 1.0 if forced[i] == rf[j][0] else -1.0
            elif 0.4 <= r <= 2.5:
                sm = difflib.SequenceMatcher(None, xt[i], rt[j], autojunk=False)
                sim[i][j] = sm.ratio() if sm.quick_ratio() >= 0.5 else 0.0
    GAP = 0.25
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    B = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0], B[i][0] = D[i - 1][0] - GAP, 'x'
    for j in range(1, m + 1):
        D[0][j], B[0][j] = D[0][j - 1] - GAP, 'r'
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = [(D[i - 1][j - 1] + sim[i - 1][j - 1] - 0.5, 'm'), (D[i - 1][j] - GAP, 'x'), (D[i][j - 1] - GAP, 'r')]
            D[i][j], B[i][j] = max(c)
    out = []
    i, j = n, m
    while i > 0 or j > 0:
        b = B[i][j] if i > 0 and j > 0 else ('x' if i > 0 else 'r')
        if b == 'm':
            out.append((i - 1, j - 1)); i, j = i - 1, j - 1
        elif b == 'x':
            out.append((i - 1, None)); i -= 1
        else:
            out.append((None, j - 1)); j -= 1
    out.reverse()
    print('%-52s %-10s %5s | %-10s %5s %5s  %-22s %s' % ('prototype name', 'proto', 'size', 'retail', 'size', 'sim',
                                                         'global map', 'PC (retail->PC tier)'))
    for i, j in out:
        if i is not None:
            rows = C.by_proto.get(xf[i][0], [])
            nm = ' | '.join(sorted(set(r['name'] for r in rows)))[:52] or '?'
            gm = ('%s %s %s' % (rows[0]['retail'], rows[0]['method'], rows[0]['tier'])) if rows and rows[0]['retail'] \
                else ''
            left = '%-52s 0x%08x %5d' % (nm, xf[i][0], xf[i][1] - xf[i][0])
        else:
            left, gm = '%-52s %-10s %5s' % ('', '', ''), ''
        if j is not None:
            pc = C.xpc.get(rf[j][0])
            s = sim[i][j] if i is not None else None
            right = '0x%08x %5d %5s  %-22s %s' % (rf[j][0], rf[j][1] - rf[j][0], ('%.2f' % s) if s is not None else '',
                                                 gm, ('%s (%s)' % (pc['pc'], pc['tier'])) if pc else '-')
        else:
            right = '%-10s %5s %5s  %-22s' % ('', '', '', gm)
        print(left + ' | ' + right)


if __name__ == '__main__':
    main(sys.argv[1:])
