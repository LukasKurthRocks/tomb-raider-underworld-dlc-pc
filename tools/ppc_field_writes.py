"""Every PowerPC instruction that can write a structure field or a global (read-only; 2026-11-02, TU function
comparison item L4: who clears the doppelganger flag gameTracker+0x1244 on a level / game change?).

tools/ppc_xrefs.py `disp` lists only the D-form loads / stores with exactly that displacement. A flag can also be
written by a wider store that covers it (stw / std / stmw / stfd at a lower displacement), by a vector store with an
index register (`li rX, IMM` + stvx / stvx128), or by a memset / memcpy-like call on the whole object. This tool scans
all code sections word by word (code without .pdata entries included):

  field IMAGE DISP          stores whose byte range covers DISP: stb/sth/stw/std/stmw/stfs/stfd (+ update forms),
                            vector stores stvx / stvx128 / stvlx128 with `li rX, imm` (imm <= DISP < imm + 16) in
                            the 6 instructions before; and calls (bl) with r3 = rY + imm (imm <= DISP, `addi`) or
                            r3 = rY (`mr`) and a length `li / lis+ori r5, N` covering DISP in the 8 instructions
                            before (memset / memcpy / constructor-style candidates; listed as 'call')
  global IMAGE ADDR         stores to a global address ADDR: `lis rH, hi` + `stw/stb/sth/std/stfs rS, lo(rH)`
                            within 12 instructions (rH not overwritten) - who sets a global pointer
Each hit: instruction address, containing function (.pdata start or '?'), the decoded store.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_field_writes.py field work/xenia_dump/tu_image_82000000.bin 0x1244
  ../bin/pyt -t 300 tools/ppc_field_writes.py global work/xenia_dump/tu_image_82000000.bin 0x829892b0
Only addresses and decoded instruction text are printed - no game bytes.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS
import ppc_xrefs as P

BASE = 0x82000000
# D-form stores: op -> (mnemonic, width)
DSTORE = {36: ('stw', 4), 37: ('stwu', 4), 38: ('stb', 1), 39: ('stbu', 1), 44: ('sth', 2), 45: ('sthu', 2),
          52: ('stfs', 4), 53: ('stfsu', 4), 54: ('stfd', 8), 55: ('stfdu', 8)}


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


def code_words(d):
    for name, start, size, ch in XS.sections(d, BASE):
        if not (ch & 0x20):
            continue
        off = start - BASE
        n = min(size, len(d) - off) // 4
        yield start, struct.unpack_from('>%dI' % n, d, off)


def vstore(w):
    """(name, ra, rb) of an indexed vector store or None"""
    op = w >> 26
    if op == 31 and ((w >> 1) & 0x3ff) in (231, 487):                      # stvx / stvxl
        return ('stvx', (w >> 16) & 31, (w >> 11) & 31)
    if op == 4:
        xo = w & 0x7f3
        names = {0x1c3: 'stvx128', 0x3c3: 'stvxl128', 0x503: 'stvlx128', 0x543: 'stvrx128', 0x183: 'stvewx128',
                 0x703: 'stvlxl128', 0x743: 'stvrxl128'}
        if xo in names:
            return (names[xo], (w >> 16) & 31, (w >> 11) & 31)
    return None


def field(d, funcs, disp):
    hits = 0
    for start, w in code_words(d):
        for i, x in enumerate(w):
            op = x >> 26
            va = start + 4 * i
            rs, ra, imm = (x >> 21) & 31, (x >> 16) & 31, s16(x & 0xffff)
            txt = None
            if op in DSTORE:
                nm, wd = DSTORE[op]
                if imm <= disp < imm + wd:
                    txt = '%s r%d, 0x%x(r%d)' % (nm, rs, imm & 0xffff, ra)
            elif op == 62 and (x & 3) in (0, 1):                                 # std / stdu (DS form)
                ds = s16(x & 0xfffc)
                if ds <= disp < ds + 8:
                    txt = '%s r%d, 0x%x(r%d)' % ('std' if (x & 3) == 0 else 'stdu', rs, ds & 0xffff, ra)
            elif op == 47:                                                       # stmw rS..r31
                if imm <= disp < imm + 4 * (32 - rs):
                    txt = 'stmw r%d, 0x%x(r%d)' % (rs, imm & 0xffff, ra)
            else:
                v = vstore(x)
                if v:
                    nm, ra2, rb = v
                    for j in range(max(0, i - 6), i):
                        y = w[j]
                        if y >> 26 == 14 and (y >> 16) & 31 == 0 and (y >> 21) & 31 == rb:
                            li = s16(y & 0xffff)
                            if li <= disp < li + 16:
                                txt = '%s (r%d + li r%d=0x%x at 0x%08x)' % (nm, ra2, rb, li, start + 4 * j)
                if not txt and op == 18 and (x & 3) == 1:                       # bl: memset-like candidates
                    r3, r5 = None, None
                    for j in range(max(0, i - 8), i):
                        y = w[j]
                        yo = y >> 26
                        if yo == 14 and (y >> 21) & 31 == 3 and (y >> 16) & 31 != 0:
                            r3 = ('addi', (y >> 16) & 31, s16(y & 0xffff))
                        if yo == 31 and ((y >> 1) & 0x3ff) == 444 and (y >> 16) & 31 == 3 and \
                                (y >> 21) & 31 == (y >> 11) & 31:
                            r3 = ('mr', (y >> 21) & 31, 0)
                        if yo == 14 and (y >> 21) & 31 == 5 and (y >> 16) & 31 == 0:
                            r5 = s16(y & 0xffff)
                        if yo == 15 and (y >> 21) & 31 == 5 and (y >> 16) & 31 == 0:
                            r5 = (y & 0xffff) << 16
                        if yo == 24 and (y >> 16) & 31 == 5 and r5 is not None:
                            r5 |= y & 0xffff
                    if r3 and r5 and r5 > 0 and r3[2] <= disp < r3[2] + r5 and r5 >= 0x100:
                        li = x & 0x03fffffc
                        if li & 0x02000000:
                            li -= 0x04000000
                        txt = 'call 0x%08x with r3 = %s r%d+0x%x, r5 = 0x%x' % ((va + li) & 0xffffffff, r3[0], r3[1],
                                                                              r3[2] & 0xffff, r5)
            if txt:
                f = P.func_of(funcs, va)
                print('0x%08x  in %-10s  %s' % (va, ('0x%08x' % f[0]) if f else '?', txt))
                hits += 1
    print('%d hits' % hits)


def glob(d, funcs, addr):
    hi = ((addr + 0x8000) >> 16) & 0xffff
    lo = s16(addr & 0xffff)
    hits = 0
    for start, w in code_words(d):
        for i, x in enumerate(w):
            if x >> 26 != 15 or (x >> 16) & 31 != 0 or (x & 0xffff) != hi:
                continue
            rh = (x >> 21) & 31
            for j in range(i + 1, min(len(w), i + 13)):
                y = w[j]
                yo = y >> 26
                if (yo in DSTORE or yo == 62) and (y >> 16) & 31 == rh and s16(y & 0xffff & (0xfffc if yo == 62 else
                                                                                             0xffff)) == lo:
                    nm = DSTORE[yo][0] if yo in DSTORE else 'std'
                    va = start + 4 * j
                    f = P.func_of(funcs, va)
                    print('0x%08x  in %-10s  %s r%d, 0x%x(r%d)   (lis at 0x%08x)' % (
                        va, ('0x%08x' % f[0]) if f else '?', nm, (y >> 21) & 31, y & 0xffff, rh, start + 4 * i))
                    hits += 1
                # rH overwritten: any D-form / arithmetic with rD == rH (rough)
                if yo not in DSTORE and yo != 62 and (y >> 21) & 31 == rh and yo in (14, 15, 24, 32, 34, 40, 31):
                    break
    print('%d hits' % hits)


def main(argv):
    if len(argv) != 3 or argv[0] not in ('field', 'global'):
        sys.exit(__doc__)
    d, secs = P.load(argv[1])
    funcs = P.pdata(d, secs)
    if argv[0] == 'field':
        field(d, funcs, int(argv[2], 0))
    else:
        glob(d, funcs, int(argv[2], 0))


if __name__ == '__main__':
    main(sys.argv[1:])
