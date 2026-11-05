"""Every PowerPC access to one field of a global object pointer (read-only; 2026-11-04, TruShadowPower 0.14: which
code reads / writes gameTracker+0x1f0, the vector whose length TU 0x823d77f0 / 0x823d7d40 test?).

tools/ppc_xrefs.py `disp` lists every load / store with a displacement, whatever the base register holds, and
tools/ppc_field_writes.py only stores. This tool follows the register that receives the global pointer:
  `lis rH, hi` .. `lwz rG, lo(rH)` with (hi << 16) + lo == GLOBAL (default 0x829892b0 = gameTracker), then the next
  --window instructions (default 64) while rG is not overwritten (a bl ends the trace when rG is volatile r0 / r3..r12):
    D-form load / store `op rX, DISP(rG)`, `addi rX, rG, DISP` (address of the field), and indexed vector
    loads / stores (lvx / stvx / VMX128 lvx128 / stvx128 ..) `rG, rI` after `li rI, DISP`.
Each hit: instruction address, containing function (.pdata start or '?'), kind, decoded text.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_gt_field_refs.py IMAGE DISP[,DISP..] [--global 0x829892b0] [--window 64]
e.g. ../bin/pyt -t 300 tools/ppc_gt_field_refs.py work/xenia_dump/retail_image_82000000.bin 0x1f0
Only addresses and decoded instruction text are printed - no game bytes.
"""
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import ppc_dis128 as D

BASE = 0x82000000
DLOAD = {32: 'lwz', 33: 'lwzu', 34: 'lbz', 35: 'lbzu', 40: 'lhz', 41: 'lhzu', 42: 'lha', 43: 'lhau',
         48: 'lfs', 49: 'lfsu', 50: 'lfd', 51: 'lfdu', 46: 'lmw'}
DSTORE = {36: 'stw', 37: 'stwu', 38: 'stb', 39: 'stbu', 44: 'sth', 45: 'sthu', 52: 'stfs', 53: 'stfsu',
          54: 'stfd', 55: 'stfdu', 47: 'stmw'}
X_VEC = {103: 'lvx', 359: 'lvxl', 231: 'stvx', 487: 'stvxl'}
# op 31 forms whose destination is rA (logical / shift / extend); stores have no register destination
X_DEST_RA = {28, 60, 124, 284, 316, 412, 444, 476, 24, 536, 792, 824, 26, 922, 954, 986}
X_STORE = {151, 183, 215, 247, 407, 439, 663, 695, 727, 759, 231, 487, 135, 167, 199, 918, 662}


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


def main(argv):
    glob, win = 0x829892b0, 64
    for opt in ('--global', '--window'):
        if opt in argv:
            k = argv.index(opt); v = argv[k + 1]; del argv[k:k + 2]
            if opt == '--global': glob = int(v, 16)
            else: win = int(v)
    d, secs = P.load(argv[0])
    want = set(int(x, 16) for x in argv[1].split(','))
    funcs = P.pdata(d, secs)
    starts = [f[0] for f in funcs]

    def func_of(a):
        i = bisect.bisect_right(starts, a) - 1
        return funcs[i][0] if i >= 0 and funcs[i][0] <= a < funcs[i][1] else None

    hi = ((glob + 0x8000) >> 16) & 0xffff
    lo = s16(glob & 0xffff)
    hits = 0
    for cs, ce in P.code_ranges(secs):
        his = {}                                   # register -> address of its lis hi
        for a in range(cs, ce, 4):
            w = struct.unpack_from('>I', d, a - BASE)[0]
            op, rd, ra = w >> 26, (w >> 21) & 31, (w >> 16) & 31
            if op == 15 and ra == 0:
                if (w & 0xffff) == hi: his[rd] = a
                else: his.pop(rd, None)
                continue
            if not (op == 32 and ra in his and s16(w & 0xffff) == lo and a - his[ra] <= 48):
                if op in (14, 15, 32, 33, 34, 35, 40, 41, 42, 43) and rd in his: his.pop(rd, None)
                continue
            g = rd                                 # rG = the global pointer
            idx = {}                               # register -> li value (also a `li` up to 24 instructions before)
            for b in range(max(cs, a - 96), a, 4):
                x = struct.unpack_from('>I', d, b - BASE)[0]
                if (x >> 26) == 14 and ((x >> 16) & 31) == 0: idx[(x >> 21) & 31] = s16(x & 0xffff)
                elif (x >> 26) in DLOAD or (x >> 26) in (14, 15): idx.pop((x >> 21) & 31, None)
            for b in range(a + 4, min(a + 4 + 4 * win, ce), 4):
                x = struct.unpack_from('>I', d, b - BASE)[0]
                xo, xd, xa, xb = x >> 26, (x >> 21) & 31, (x >> 16) & 31, (x >> 11) & 31
                imm = s16(x & 0xffff)
                text, kind = None, None
                if xo in DLOAD and xa == g and imm in want:
                    kind, text = 'load', '%s r%d, 0x%x(r%d)' % (DLOAD[xo], xd, imm, g)
                elif xo in DSTORE and xa == g and imm in want:
                    kind, text = 'store', '%s r%d, 0x%x(r%d)' % (DSTORE[xo], xd, imm, g)
                elif xo == 14 and xa == g and imm in want:
                    kind, text = 'addr', 'addi r%d, r%d, 0x%x' % (xd, g, imm)
                elif xo == 14 and xa == 0:
                    idx[xd] = imm
                elif (xo == 31 and ((x >> 1) & 0x3ff) in X_VEC) or (xo == 4 and (x & 0x7f3) in D.LS128):
                    if xa == g and idx.get(xb) in want:
                        name = X_VEC.get((x >> 1) & 0x3ff) if xo == 31 else D.LS128[x & 0x7f3]
                        kind = 'vstore' if name.startswith('st') else 'vload'
                        text = '%s v.., r%d, r%d (= 0x%x)' % (name, g, xb, idx[xb])
                if kind:
                    hits += 1
                    f = func_of(b)
                    print('0x%08x  in %-10s  %-6s %s   (pointer loaded at 0x%08x)' %
                          (b, '0x%08x' % f if f else '?', kind, text, a))
                # end of the trace: rG overwritten, a call clobbering a volatile rG, or a return / jump
                dest = None
                if xo in DLOAD or xo in (14, 15, 7, 12, 13, 8):
                    dest = xd
                elif xo in (24, 25, 26, 27, 28, 29, 21, 20, 23):
                    dest = xa
                elif xo == 31:
                    sub = (x >> 1) & 0x3ff
                    dest = xa if sub in X_DEST_RA else (None if sub in X_STORE else xd)
                if xo == 14 and xa == 0 and xd == g: dest = g
                if dest == g: break
                if xo == 18 and (x & 1) and (g == 0 or 3 <= g <= 12): break
                if x == 0x4e800020 or (xo == 18 and not (x & 1)): break
                if xo == 14 and xa == 0: pass
                elif xo in (14, 15) and xd in idx: idx.pop(xd, None)
    print('# %d hit(s) for %s off [0x%08x]' % (hits, ','.join('0x%x' % w for w in sorted(want)), glob))


if __name__ == '__main__':
    main(sys.argv[1:])
