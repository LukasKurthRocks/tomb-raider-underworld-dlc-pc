"""Find Xbox 360 code that compares the result of a non-inlined markup type getter with given values (read-only;
2026-11-06 exe sites K13, docs Befund-Exe-Stellen-K8-K14-0611.md).

tools/ppc_markup_type_cmp.py only sees inlined getters (`lbz 0x4d` / `lbz 0x33` followed by a compare). Here:
  1. getters = small .pdata functions (at most --max bytes) that contain both `lbz rX, 0x4d(rY)` and
     `lbz rX, 0x33(rY)` (second markup type / record type char - the PC getter tru+0x1be340 does the same);
  2. every `bl getter` in the image, then the next --win instructions: `cmpwi / cmplwi crN, r3, V` (or of a register
     copied from r3 by mr / extsb / clrlwi) with V in VALUES.
Prints the getters with their call count and every hit (call site, compare, value, enclosing function).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_markup_getter_cmp.py IMAGE [VALUES] [--max 0x60] [--win 8]
  VALUES default 21,22,23
"""
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as PX

BASE = 0x82000000


def word(d, a):
    return struct.unpack_from('>I', d, a - BASE)[0]


def main(argv):
    mx, win = 0x60, 8
    if '--max' in argv: k = argv.index('--max'); mx = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--win' in argv: k = argv.index('--win'); win = int(argv[k + 1]); del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    vals = set(int(x, 0) for x in argv[1].split(',')) if len(argv) > 1 else {21, 22, 23}
    d, secs = PX.load(argv[0])
    funcs = PX.pdata(d, secs)
    starts = [f[0] for f in funcs]
    getters = []
    for fs, fe in funcs:
        if fe - fs > mx: continue
        seen = set()
        for a in range(fs, fe, 4):
            w = word(d, a)
            if (w >> 26) == 34: seen.add(w & 0xffff)              # lbz rD, D(rA)
        if 0x4d in seen and 0x33 in seen: getters.append(fs)
    gset = set(getters)
    calls = {g: 0 for g in getters}
    hits = []
    for fs, fe in funcs:
        for a in range(fs, fe, 4):
            w = word(d, a)
            if (w >> 26) != 18 or (w & 3) != 1: continue          # bl
            li = w & 0x03fffffc
            if li & 0x02000000: li -= 0x04000000
            t = a + li
            if t not in gset: continue
            calls[t] += 1
            regs = {3}
            for k in range(1, win + 1):
                b = a + 4 * k
                if b >= fe: break
                v = word(d, b); op = v >> 26
                if op in (10, 11):                                # cmpli / cmpi
                    ra = (v >> 16) & 31; imm = v & 0xffff
                    if op == 11 and imm & 0x8000: imm -= 0x10000
                    if ra in regs and imm in vals:
                        hits.append((a, t, b, imm, fs))
                elif op == 31 and ((v >> 1) & 0x3ff) in (444, 954):   # or (mr) / extsb
                    rs, ra = (v >> 21) & 31, (v >> 16) & 31
                    if rs in regs: regs.add(ra)
                elif op == 21:                                    # rlwinm (clrlwi)
                    rs, ra = (v >> 21) & 31, (v >> 16) & 31
                    if rs in regs: regs.add(ra)
                elif op == 18 and (v & 1): break                  # next call
    print('getters (size <= 0x%x, lbz 0x4d + lbz 0x33): %d' % (mx, len(getters)))
    for g in getters: print('  0x%08x  calls %d' % (g, calls[g]))
    print('compares with %s after a getter call: %d' % (sorted(vals), len(hits)))
    for a, t, b, imm, fs in hits:
        print('  call 0x%08x -> 0x%08x  compare at 0x%08x value %d  in function 0x%08x' % (a, t, b, imm, fs))


if __name__ == '__main__':
    main(sys.argv[1:])
