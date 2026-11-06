"""Compare the SweepAndPrune (SAP) collision core between the retail and the TU Xbox 360 images (read-only).

2026-11-06 SweepAndPrune: the TU raised the SAP pool from (1000, 200) to (3000, 500) and inserted a field +0x1c in
the owner object (docs/Befund-Exe-Vergleich-0511.md section 7). This tool pairs the .pdata functions of a retail
address range with those of a TU address range (same order in both images) and prints, per pair, the sizes and an
instruction diff. Branch / call targets are rewritten as 'L+off' (inside the function) or 'F:<retail-or-tu addr>'
so pure relocation does not show up as a difference; immediates and displacements are kept, so changed constants
and changed structure offsets do show up.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/sap_xbox_core_diff.py RETAIL_IMG TU_IMG R_FROM R_TO T_FROM T_TO [--full]
      R_FROM..R_TO / T_FROM..T_TO: hex address ranges (function starts inside them are paired in order)
      --full: print the whole diff of every changed pair (default: first 80 diff lines per pair)
  ../bin/pyt -t 300 tools/sap_xbox_core_diff.py RETAIL_IMG TU_IMG --pair R_ADDR T_ADDR
      diff of one function pair (full)
"""
import sys, os, struct, difflib
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as X
import ppc_dis128 as D

BASE = 0x82000000


def dis_func(d, fs, fe, md):
    """normalized text lines of one function"""
    out = []
    for a in range(fs, fe, 4):
        w = struct.unpack_from('>I', d, a - BASE)[0]
        op = w >> 26
        if op == 18:                                   # b / bl
            li = w & 0x03fffffc
            li = li - 0x04000000 if li & 0x02000000 else li
            t = (a + li) & 0xffffffff
            tgt = ('L+0x%x' % (t - fs)) if fs <= t < fe else 'F'
            out.append('%s %s' % ('bl' if w & 1 else 'b', tgt))
            continue
        if op == 16:                                   # bc
            bd = w & 0xfffc
            bd = bd - 0x10000 if bd & 0x8000 else bd
            t = (a + bd) & 0xffffffff
            tgt = ('L+0x%x' % (t - fs)) if fs <= t < fe else 'F'
            out.append('bc %d,%d,%s%s' % ((w >> 21) & 31, (w >> 16) & 31, tgt, 'l' if w & 1 else ''))
            continue
        text = None
        if op in (5, 6) or (op == 4 and (w & 0x7f3) in D.LS128):
            text = D.vmx128(w)
        if text is None:
            ins = list(md.disasm(struct.pack('>I', w), a, 1))
            text = ('%s %s' % (ins[0].mnemonic, ins[0].op_str)) if ins else (D.vmx128(w) or '.long 0x%08x' % w)
        out.append(text)
    return out


def leaf(d, a, limit=400):
    """leaf function without a .pdata entry: from A up to and including the first blr (at most LIMIT words)"""
    for k in range(limit):
        if struct.unpack_from('>I', d, a + 4 * k - BASE)[0] == 0x4e800020:
            return (a, a + 4 * k + 4)
    return (a, a + 4 * limit)


def in_range(funcs, lo, hi):
    return [f for f in funcs if lo <= f[0] < hi]


def show_pair(dr, dt, fr, ft, md, limit):
    a = dis_func(dr, fr[0], fr[1], md)
    b = dis_func(dt, ft[0], ft[1], md)
    same = a == b
    print('retail 0x%08x %5d B   TU 0x%08x %5d B   %s' % (fr[0], fr[1] - fr[0], ft[0], ft[1] - ft[0],
          'equal' if same else 'CHANGED'))
    if same:
        return
    n = 0
    # unified diff with instruction indices so each line can be located: retail addr / TU addr
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        for i in range(i1, i2):
            if limit and n >= limit:
                break
            print('   - R 0x%08x  %s' % (fr[0] + 4 * i, a[i])); n += 1
        for j in range(j1, j2):
            if limit and n >= limit:
                break
            print('   + T 0x%08x  %s' % (ft[0] + 4 * j, b[j])); n += 1
        if limit and n >= limit:
            print('   ... (truncated, use --full / --pair)')
            break


def main(argv):
    rp, tp = argv[0], argv[1]
    dr, sr = X.load(rp)
    dt, st = X.load(tp)
    fr_all = X.pdata(dr, sr)
    ft_all = X.pdata(dt, st)
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    if argv[2] == '--pair':
        fr = X.func_of(fr_all, int(argv[3], 16)) or leaf(dr, int(argv[3], 16))
        ft = X.func_of(ft_all, int(argv[4], 16)) or leaf(dt, int(argv[4], 16))
        show_pair(dr, dt, fr, ft, md, 0)
        return
    r0, r1, t0, t1 = (int(x, 16) for x in argv[2:6])
    full = '--full' in argv
    fr = in_range(fr_all, r0, r1)
    ft = in_range(ft_all, t0, t1)
    print('retail functions %d, TU functions %d' % (len(fr), len(ft)))
    for k in range(max(len(fr), len(ft))):
        if k >= len(fr) or k >= len(ft):
            print('unpaired: %s' % (('TU 0x%08x' % ft[k][0]) if k < len(ft) else ('retail 0x%08x' % fr[k][0])))
            continue
        show_pair(dr, dt, fr[k], ft[k], md, 0 if full else 80)


if __name__ == '__main__':
    main(sys.argv[1:])
