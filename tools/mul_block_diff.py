"""Compare two stream files (.mul) block by block (read-only): header words, block counts per type, and per block
whether the payload is equal - cine blocks (type 1) also with their {u32 len, text} subtitle tail cut off, so two
builds that differ only in subtitle languages compare as equal. Built for the language-variant survey (is a .mul
of another retail build the same cinematic as ours apart from text and speech?).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/mul_block_diff.py A.mul B.mul
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mul_sub_records as M


def blocks(d, E):
    o, out = 0x800, []
    while o + 16 <= len(d):
        t, sz, a, b = struct.unpack_from(E + '4I', d, o)
        p = d[o + 16:o + 16 + sz]
        core = p
        if t == 1:
            w = M.tail_at(p, E)
            if w is not None: core = p[:w]
        out.append((t, a, b, p, core))
        o += 16 + sz
    return out


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    da, db = (open(p, 'rb').read() for p in argv)
    E = M.mul_endian(da)
    if not E or M.mul_endian(db) != E: sys.exit('not two .mul files of the same endian')
    ha, hb = struct.unpack_from(E + '8I', da, 0), struct.unpack_from(E + '8I', db, 0)
    print('header A: %s' % ' '.join('%08x' % x for x in ha))
    print('header B: %s' % ' '.join('%08x' % x for x in hb))
    A, B = blocks(da, E), blocks(db, E)
    ca, cb = collections.Counter(x[0] for x in A), collections.Counter(x[0] for x in B)
    print('blocks A %d %s, B %d %s' % (len(A), dict(ca), len(B), dict(cb)))
    for t in sorted(set(ca) | set(cb)):
        xa = [x for x in A if x[0] == t]; xb = [x for x in B if x[0] == t]
        n = min(len(xa), len(xb))
        eq = sum(1 for i in range(n) if xa[i][3] == xb[i][3])
        eqc = sum(1 for i in range(n) if xa[i][4] == xb[i][4])
        eqab = sum(1 for i in range(n) if xa[i][1:3] == xb[i][1:3])
        first = next((i for i in range(n) if xa[i][4] != xb[i][4]), None)
        print('  type %d: A %d, B %d; of the first %d: payload equal %d, without subtitle tail equal %d, words a/b equal %d%s'
              % (t, len(xa), len(xb), n, eq, eqc, eqab, '' if first is None else ', first difference at block %d' % first))


if __name__ == '__main__':
    main(sys.argv[1:])
