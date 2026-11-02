"""Find the PC tru.exe partner of an Xbox retail function by its constants (read-only; 2026-11-02, TU function
comparison items L1 / L2: retail functions that tools/xbox_pc_funcmap.py could not pair).

Fingerprint of the Xbox function (tools/tu_func_classify.py tokens): the float / double constants it loads from
.rdata, its string references, and its integer immediates / masks (li, cmpwi, andi., ori, rlwinm masks turned into
the bit mask; |v| >= 3, stack offsets excluded). Every PC function (derived table, work/tu_funcdiff/pc_cache.pkl) is
scanned for the same values: floats inline or in a referenced .rdata dword, strings by address, integers as imm32 /
imm8 bytes after an x86 opcode byte (rough). Score = sum over the fingerprint values the PC function contains of
log(N / (1 + number of PC functions containing the value)) - rare values weigh more. Optional --window LO,HI limits
the PC range (e.g. between the PC partners of the neighbouring mapped retail functions).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/xbox_pc_constmatch.py RETAIL.bin TRU_EXE RETAIL_ADDR[,ADDR..] [--window 0x5a0000,0x5c0000]
       [--top 10] [--cache work/tu_funcdiff/pc_cache.pkl]
Only addresses, values (constants of the code) and scores are printed.
"""
import sys, os, math, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tu_func_classify as TC


def mask_of(rot):
    """rlwinm MB..ME mask (big-endian bit numbering)"""
    mb, me = (rot >> 6) & 31, (rot >> 1) & 31
    m = 0
    for b in range(32):
        inside = (mb <= b <= me) if mb <= me else (b >= mb or b <= me)
        if inside:
            m |= 1 << (31 - b)
    return m


def fingerprint(img, x):
    toks, _f = TC.analyse(img, x, lambda a: a)
    fl, st, it = set(), set(), set()
    for t in toks:
        d = t[3]
        if not d:
            continue
        if d[0] == 'val' and d[1][0] == 'F':
            fl.add(d[1][1])
        elif d[0] == 'val' and d[1][0] == 'S':
            st.add(d[1][1])
        elif d[0] == 'imm' and isinstance(d[1], int) and abs(d[1]) >= 3:
            it.add(d[1] & 0xffffffff)
        elif d[0] == 'rot':
            m = mask_of(d[1])
            if m not in (0xffffffff, 0) and bin(m).count('1') <= 4:
                it.add(m)
    return fl, st, it


def pc_values(pc, f):
    b = pc.body(f)
    fl, ints = set(), set()
    for i in range(len(b) - 3):
        v = struct.unpack_from('<I', b, i)[0]
        ints.add(v)
        x = struct.unpack_from('<f', b, i)[0]
        if math.isfinite(x) and x != 0:
            fl.add('%.7g' % x)
        if pc.rd and pc.rd[0] <= v < pc.rd[0] + pc.rd[1]:
            r = pc.read(v, 8)
            if r:
                fl.add('%.7g' % struct.unpack('<f', r[:4])[0])
                fl.add('%.12g' % struct.unpack('<d', r)[0])
    for i in range(len(b) - 1):
        if b[i] in (0x83, 0x6a, 0x80, 0xb0, 0xb1, 0xb2, 0xb3, 0x3c, 0xa8, 0xf6):
            ints.add(b[i + 1])
    return fl, ints


def main(argv):
    top, cache, win = 10, 'work/tu_funcdiff/pc_cache.pkl', None
    for opt in ('--top', '--cache', '--window'):
        if opt in argv:
            k = argv.index(opt); v = argv[k + 1]; del argv[k:k + 2]
            if opt == '--top': top = int(v)
            elif opt == '--cache': cache = v
            else: win = tuple(int(a, 16) for a in v.split(','))
    if len(argv) != 3:
        sys.exit(__doc__)
    R = TC.Img(argv[0], 'retail')
    pc = TC.PCInfo(argv[1], cache)
    starts = [f for f in pc.k['starts'] if not win or win[0] <= f < win[1]]
    vals = {}
    for f in starts:
        vals[f] = pc_values(pc, f)
    strs = pc.k['strs']
    N = len(starts)
    for addr in [int(a, 16) for a in argv[2].split(',')]:
        f = TC.P.func_of(R.X.funcs, addr)
        x = f[0]
        fl, st, it = fingerprint(R, x)
        print('retail 0x%08x (%d B): floats %s; strings %d; ints %s' % (
            x, R.size[x], ' '.join(sorted(fl)), len(st), ' '.join('0x%x' % v for v in sorted(it))))
        cnt = collections.Counter()
        for p in starts:
            pf, pi = vals[p]
            for v in fl:
                if v in pf: cnt[('f', v)] += 1
            for v in it:
                if v in pi: cnt[('i', v)] += 1
            for s in st:
                if s in strs.get(p, ()): cnt[('s', s)] += 1
        score = collections.Counter()
        hits = collections.defaultdict(list)
        for p in starts:
            pf, pi = vals[p]
            for k, v in [('f', v) for v in fl] + [('i', v) for v in it] + [('s', s) for s in st]:
                ok = (v in pf) if k == 'f' else (v in pi) if k == 'i' else (v in strs.get(p, ()))
                if ok:
                    score[p] += math.log(N / (1.0 + cnt[(k, v)]))
                    hits[p].append(('%s' % v) if k != 'i' else '0x%x' % v)
        for p, s in score.most_common(top):
            print('  PC 0x%08x  score %.1f  size %d (ratio %.2f)  %d of %d values: %s' % (
                p, s, pc.k['size'].get(p, 0), pc.k['size'].get(p, 0) / float(R.size[x]), len(hits[p]),
                len(fl) + len(it) + len(st), ' '.join(hits[p][:12])))


if __name__ == '__main__':
    main(sys.argv[1:])
