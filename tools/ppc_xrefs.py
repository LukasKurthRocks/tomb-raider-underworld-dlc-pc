"""Cross references in an Xbox 360 executable image dumped from Xenia (PowerPC, big-endian; read-only).

Finding 43 follow-up (DLC 2 shadow power, option A): no Ghidra project needed for a first pass. Uses the image's
.pdata (function start + length) and scans .text / .embsec_ code for
  * address constants: `lis rD,hi` followed (same function, before rD is overwritten) by `addi/ori rX,rD,lo` or a
    load / store with displacement on rD -> the full address,
  * direct calls: `bl target`.

Commands:
  funcs DUMP                     function count and size statistics from .pdata
  refs  DUMP ADDR[,ADDR..]       functions that build one of the addresses (string / table / global)
  str   DUMP TEXT                find TEXT in the image (exact bytes), then its referencing functions
  func  DUMP ADDR                the function containing ADDR: range, size, callees, callers, referenced addresses
  words DUMP ADDR N              N big-endian words at ADDR (e.g. a vtable)
  items DUMP FROM TO             built addresses and calls between two instruction addresses (one function)
  dis   DUMP ADDR N              N instructions from ADDR, minimal decoding (lis/addi/ori/loads/stores/branches)
  disp  DUMP DISP                every load / store with displacement DISP (a structure field) in the code
  exclusive DUMP ROOTS           ROOTS (file or comma list of function starts) + all functions called only from them
Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_xrefs.py refs work/xenia_dump/tu_image_82000000.bin 0x82078c30
"""
import sys, os, struct, pickle, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS

BASE = 0x82000000
LOADSTORE = {32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 48, 49, 50, 51, 52, 53, 54, 55}


def load(path):
    d = open(path, 'rb').read()
    secs = XS.sections(d, BASE)
    return d, secs


def pdata(d, secs):
    """sorted [(start, end)] of functions from .pdata (8-byte entries: begin, packed length field)"""
    p = [s for s in secs if s[0] == '.pdata'][0]
    off = p[1] - BASE
    out = []
    for i in range(p[2] // 8):
        b, w = struct.unpack_from('>II', d, off + 8 * i)
        if not b:
            continue
        n = (w >> 8) & 0x3fffff          # FunctionLength in instructions (bits 8..29)
        out.append((b, b + 4 * n))
    out.sort()
    return out


def code_ranges(secs):
    return [(s[1], s[1] + s[2]) for s in secs if s[3] & 0x20]


def scan(d, secs, funcs):
    """per function: list of (insn addr, kind, value) - kind 'addr' (built constant) or 'call' (bl target)"""
    res = {}
    for fs, fe in funcs:
        regs = {}
        items = []
        for a in range(fs, fe, 4):
            w = struct.unpack_from('>I', d, a - BASE)[0]
            op = w >> 26
            rd, ra = (w >> 21) & 31, (w >> 16) & 31
            imm = w & 0xffff
            simm = imm - 0x10000 if imm & 0x8000 else imm
            if op == 15 and ra == 0:                       # lis rd, imm
                regs[rd] = (imm << 16) & 0xffffffff
                continue
            if op == 14 and ra in regs:                    # addi rd, ra, simm
                v = (regs[ra] + simm) & 0xffffffff
                items.append((a, 'addr', v))
                if rd != ra or True:
                    regs.pop(rd, None) if rd != ra else regs.pop(ra, None)
                continue
            if op == 24 and rd in regs:                    # ori ra, rs(=rd field), imm
                v = regs[rd] | imm
                items.append((a, 'addr', v))
                regs.pop(ra, None)
                continue
            if op in LOADSTORE and ra in regs:
                items.append((a, 'addr', (regs[ra] + simm) & 0xffffffff))
                if op < 36 or 40 <= op < 44 or 48 <= op < 52:   # loads overwrite rd
                    regs.pop(rd, None)
                continue
            if op == 18 and (w & 3) == 1:                  # bl
                li = w & 0x03fffffc
                if li & 0x02000000:
                    li -= 0x04000000
                items.append((a, 'call', (a + li) & 0xffffffff))
                continue
            if op not in (31,) and rd in regs and op in (14, 15, 24, 25, 28, 29, 21, 20):
                regs.pop(rd, None)
            if op == 31:
                regs.pop(rd, None)
                regs.pop(ra, None)
        res[fs] = items
    return res


def decode(d, a):
    """minimal mnemonic for the few instruction forms this first pass needs"""
    w = struct.unpack_from('>I', d, a - BASE)[0]
    op, rd, ra, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if op == 15:
        return ('lis r%d,0x%x' % (rd, imm)) if ra == 0 else 'addis r%d,r%d,0x%x' % (rd, ra, imm)
    if op == 14:
        return ('li r%d,%d' % (rd, simm)) if ra == 0 else 'addi r%d,r%d,%d' % (rd, ra, simm)
    if op == 24:
        return 'ori r%d,r%d,0x%x' % (ra, rd, imm)
    if op == 18:
        li = w & 0x03fffffc
        li = li - 0x04000000 if li & 0x02000000 else li
        return '%s 0x%08x' % ('bl' if w & 1 else 'b', (a + li) & 0xffffffff)
    if w == 0x4e800020:
        return 'blr'
    names = {32: 'lwz', 34: 'lbz', 36: 'stw', 38: 'stb', 40: 'lhz', 44: 'sth', 48: 'lfs', 50: 'lfd', 52: 'stfs'}
    if op in names:
        return '%s r%d,%d(r%d)' % (names[op], rd, simm, ra)
    if op == 11:
        return 'cmpwi cr%d,r%d,%d' % (rd >> 2, ra, simm)
    if op == 16:
        return 'bc %d,%d,0x%08x' % (rd, ra, (a + (simm & ~3)) & 0xffffffff)
    if op == 31 and ((w >> 1) & 0x3ff) == 444:
        return 'or r%d,r%d,r%d' % (ra, rd, (w >> 11) & 31)
    if op == 31 and ((w >> 1) & 0x3ff) == 339:
        return 'mfspr r%d' % rd
    if op == 31 and ((w >> 1) & 0x3ff) == 467:
        return 'mtspr r%d' % rd
    return 'op%d' % op


def cached(path):
    cache = path + '.xrefs.pkl'
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(path):
        return pickle.load(open(cache, 'rb'))
    d, secs = load(path)
    funcs = pdata(d, secs)
    res = scan(d, secs, funcs)
    pickle.dump((funcs, res), open(cache, 'wb'))
    return funcs, res


def func_of(funcs, a):
    i = bisect.bisect_right([f[0] for f in funcs], a) - 1
    if i >= 0 and funcs[i][0] <= a < funcs[i][1]:
        return funcs[i]
    return None


NARGS = {'funcs': 2, 'refs': 3, 'str': 3, 'func': 3, 'words': 4, 'items': 4, 'dis': 4, 'disp': 3, 'exclusive': 3}


def main(argv):
    # Q75 (2026-11-11): no / unknown command or too few arguments -> usage, exit 2 (was: IndexError traceback)
    if not argv or argv[0] not in NARGS or len(argv) < NARGS[argv[0]]:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cmd, path = argv[0], argv[1]
    d, secs = load(path)
    funcs, res = cached(path)
    if cmd == 'funcs':
        sizes = [e - s for s, e in funcs]
        print('%d functions, %d bytes total, median %d, max %d' % (len(funcs), sum(sizes),
              sorted(sizes)[len(sizes) // 2], max(sizes)))
        return
    if cmd == 'items':
        a, b = int(argv[2], 0), int(argv[3], 0)
        f = func_of(funcs, a)
        for x, k, v in res[f[0]]:
            if a <= x < b:
                print('0x%08x  %-4s 0x%08x' % (x, k, v))
        return
    if cmd == 'exclusive':
        # roots + every function that is called ONLY from functions already in the set (fixpoint): an estimate
        # of the code that exists just for the roots' feature
        roots = set(int(x, 0) for x in open(argv[2]).read().split() if x.strip()) if os.path.exists(argv[2]) \
            else set(int(x, 0) for x in argv[2].split(','))
        starts = set(f[0] for f in funcs)
        size = dict((s, e - s) for s, e in funcs)
        callers = {}
        for fs, items in res.items():
            for x, k, v in items:
                if k == 'call' and v in starts:
                    callers.setdefault(v, set()).add(fs)
        cur = set(r for r in roots if r in starts)
        changed = True
        while changed:
            changed = False
            for f in starts - cur:
                c = callers.get(f)
                if c and c <= cur:
                    cur.add(f)
                    changed = True
        extra = cur - roots
        print('roots %d (%d B), exclusive callees %d (%d B), total %d functions, %d B'
              % (len(roots & starts), sum(size[r] for r in roots & starts), len(extra), sum(size[f] for f in extra),
                 len(cur), sum(size[f] for f in cur)))
        return
    if cmd == 'disp':
        # loads / stores with a given displacement (a structure field), e.g. 0x1244 of the game tracker
        want = int(argv[2], 0)
        for s, e in code_ranges(secs):
            for x in range(s, e, 4):
                w = struct.unpack_from('>I', d, x - BASE)[0]
                op = w >> 26
                if op in LOADSTORE and (w & 0xffff) == want:
                    f = func_of(funcs, x)
                    print('0x%08x  %s  in %s' % (x, decode(d, x), ('0x%08x' % f[0]) if f else '?'))
        return
    if cmd == 'dis':
        a, n = int(argv[2], 0), int(argv[3])
        for k in range(n):
            x = a + 4 * k
            print('0x%08x  %08x  %s' % (x, struct.unpack_from('>I', d, x - BASE)[0], decode(d, x)))
        return
    if cmd == 'words':
        a, n = int(argv[2], 0), int(argv[3])
        for k in range(n):
            print('0x%08x  0x%08x' % (a + 4 * k, struct.unpack_from('>I', d, a + 4 * k - BASE)[0]))
        return
    if cmd == 'str':
        t = argv[2].encode('latin-1')
        targets, i = [], d.find(t)
        while i >= 0:
            targets.append(BASE + i)
            i = d.find(t, i + 1)
        print('%r at %s' % (argv[2], ' '.join('0x%08x' % x for x in targets)))
        argv = [cmd, path, ','.join('0x%x' % x for x in targets)]
        cmd = 'refs'
    if cmd == 'refs':
        targets = set(int(x, 0) for x in argv[2].split(',') if x)
        for fs, items in res.items():
            for a, kind, v in items:
                if kind == 'addr' and v in targets:
                    f = func_of(funcs, a)
                    print('0x%08x -> 0x%08x  in function 0x%08x..0x%08x (%d B)' % (a, v, f[0], f[1], f[1] - f[0]))
        return
    if cmd == 'func':
        a = int(argv[2], 0)
        f = func_of(funcs, a)
        if not f:
            print('no function at 0x%08x' % a); return
        print('function 0x%08x..0x%08x (%d B)' % (f[0], f[1], f[1] - f[0]))
        calls = [v for x, k, v in res[f[0]] if k == 'call']
        addrs = [v for x, k, v in res[f[0]] if k == 'addr']
        print('  callees: %s' % ' '.join('0x%08x' % v for v in sorted(set(calls))))
        print('  addresses: %s' % ' '.join('0x%08x' % v for v in sorted(set(addrs))))
        callers = sorted(set(fs for fs, items in res.items() for x, k, v in items if k == 'call' and v == f[0]))
        print('  callers: %s' % ' '.join('0x%08x' % v for v in callers))
        for v in sorted(set(addrs)):
            o = v - BASE
            if 0 <= o < len(d):
                s = d[o:o + 64].split(b'\0')[0]
                if len(s) >= 4 and all(32 <= c < 127 for c in s):
                    print('    0x%08x "%s"' % (v, s.decode()))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
