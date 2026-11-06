"""Who reads / writes the fields of the SweepAndPrune owner object (read-only heuristic data-flow scan).

2026-11-06 SweepAndPrune: the TU inserted a field +0x1c (= 3000) into the global SAP owner object (PC ctor
tru+0x1be3a0, retail 0x8227eda8, TU 0x8227b9f0) and shifted the later fields by 4. To know what a 1:1 translation
must touch, every access to the owner's fields is listed, on the PC (x86) and on the Xbox images (PowerPC).

Method: per function, a linear scan tracks which registers hold the owner pointer:
  * a load from one of the global pointer cells that hold the owner (GLOBALS),
  * register copies (mov / mr),
  * 'this' at entry (ecx on x86, r3 on PPC) for the 'method' functions: the vtable entries given with --vt and every
    function that is called while the 'this' register holds the owner (closure, iterated to a fixpoint).
On PPC the code between .pdata functions (leaf functions) is scanned as well, cut after each blr.
Calls kill the volatile registers. Branches are ignored (linear), so a hit is a lead to check by hand, not proof;
a field access through a pointer stored somewhere else (not a global, not 'this') is NOT found.
Reported: every memory access whose base register holds the owner and whose displacement is < LIMIT.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/sap_owner_field_users.py pc  EXE  GLOBALS [--vt VT:N[,VT:N]] [--limit 0x28] [--getter A[,A]]
  ../bin/pyt -t 900 tools/sap_owner_field_users.py ppc IMAGE GLOBALS [--vt VT:N[,VT:N]] [--limit 0x28]
      GLOBALS: comma list of hex addresses of global cells that hold the owner pointer
      --vt: vtable address + entry count; entries are scanned as methods ('this' = owner)
      --getter (pc): functions that return the owner in eax (e.g. a one-line "mov eax, [global]; ret")
"""
import sys, os, struct
import capstone
from capstone import x86 as CX
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as X
import pe_callers as PE

PPC_BASE = 0x82000000


# ---------------------------------------------------------------- PowerPC
def ppc_written(w):
    """register numbers written by one PPC instruction (approximation for the common forms)"""
    op = w >> 26
    rd, ra = (w >> 21) & 31, (w >> 16) & 31
    if op in (32, 33, 34, 35, 40, 41, 42, 43, 46):           # loads (incl. update forms write ra too)
        return {rd, ra} if op in (33, 35, 41, 43) else {rd}
    if op in (36, 37, 38, 39, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54, 55):
        return {ra} if op in (37, 39, 45, 49, 51, 53, 55) else set()
    if op in (20, 21, 23, 24, 25, 26, 27, 28, 29):           # rlw*, ori, oris, xori, xoris, andi., andis.
        return {ra}
    if op in (7, 8, 12, 13, 14, 15):                          # mulli subfic addic addic. addi addis
        return {rd}
    if op == 31:
        xo = (w >> 1) & 0x3ff
        logical = {28, 60, 124, 284, 316, 412, 444, 476, 24, 536, 792, 824, 922, 954, 26, 986}
        if xo in logical:
            return {ra}
        if xo in (151, 183, 215, 247, 407, 439, 663, 695, 727, 759, 918, 662, 534, 790, 150):   # stores
            return {ra} if xo in (183, 247, 439, 695, 759) else set()
        return {rd}
    if op == 58:                                              # ld
        return {rd}
    return set()


def ppc_scan_func(d, fs, fe, globals_, this_in, limit, out, calls_with_this):
    owner = {3} if this_in else set()
    lis = {}
    for a in range(fs, fe, 4):
        w = struct.unpack_from('>I', d, a - PPC_BASE)[0]
        op = w >> 26
        rd, ra = (w >> 21) & 31, (w >> 16) & 31
        imm = w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        # memory access through an owner register
        if op in range(32, 56) and ra in owner and 0 <= simm < limit:
            kind = 'st' if op in (36, 37, 38, 39, 44, 45, 47, 52, 53, 54, 55) else 'ld'
            out.append((a, fs, kind, simm, 'r%d' % ra))
        if op == 18 and (w & 1):                              # bl
            li = w & 0x03fffffc
            li = li - 0x04000000 if li & 0x02000000 else li
            t = (a + li) & 0xffffffff
            if 3 in owner:
                calls_with_this.add(t)
            owner -= set(range(3, 13))
            lis = {k: v for k, v in lis.items() if k not in range(3, 13)}
            continue
        if op == 19 and ((w >> 1) & 0x3ff) == 528 and (w & 1):   # bctrl
            owner -= set(range(3, 13))
            continue
        new_owner = None
        if op == 15 and ra == 0:
            lis[rd] = (imm << 16) & 0xffffffff
        elif op == 32 and ra in lis and ((lis[ra] + simm) & 0xffffffff) in globals_:
            new_owner = rd
        elif op == 31 and ((w >> 1) & 0x3ff) == 444 and rd == ((w >> 11) & 31) and rd in owner:   # mr ra, rs
            new_owner = ra
        wr = ppc_written(w)
        owner -= wr
        for r in wr:
            if not (op == 15 and ra == 0 and r == rd):     # keep the value a 'lis' just set
                lis.pop(r, None)
        if new_owner is not None:
            owner.add(new_owner)


def with_leaf_gaps(d, funcs, secs):
    """.pdata functions plus pseudo-functions for the code between them (leaf functions have no .pdata entry):
    each gap is cut after every blr"""
    out = list(funcs)
    code = X.code_ranges(secs)
    for (s1, e1), (s2, e2) in zip(funcs, funcs[1:]):
        if s2 <= e1 or not any(lo <= e1 < hi for lo, hi in code):
            continue
        a = e1
        start = None
        while a < s2:
            w = struct.unpack_from('>I', d, a - PPC_BASE)[0]
            if start is None and w != 0:
                start = a
            if w == 0x4e800020 and start is not None:
                out.append((start, a + 4))
                start = None
            a += 4
        if start is not None:
            out.append((start, s2))
    out.sort()
    return out


def run_ppc(path, globals_, vts, limit):
    d, secs = X.load(path)
    funcs = with_leaf_gaps(d, X.pdata(d, secs), secs)
    methods = set()
    for vt, n in vts:
        for k in range(n):
            methods.add(struct.unpack_from('>I', d, vt + 4 * k - PPC_BASE)[0])
    done = set()
    hits = []
    # pass 1: functions that load a global (plus the method closure)
    calls = set()
    for fs, fe in funcs:
        ppc_scan_func(d, fs, fe, globals_, fs in methods, limit, hits, calls)
        done.add((fs, fs in methods))
    work = (calls | methods)
    seen = set(methods)
    while True:
        new = set()
        for t in work:
            f = X.func_of(funcs, t)
            if f is None or f[0] != t or (t, True) in done:
                continue
            calls2 = set()
            hits2 = []
            ppc_scan_func(d, f[0], f[1], globals_, True, limit, hits2, calls2)
            hits.extend(hits2)
            done.add((t, True))
            seen.add(t)
            new |= calls2 - seen
        if not new:
            break
        work = new
    return hits, sorted(seen)


# ---------------------------------------------------------------- x86
def pc_insns(md, blob, tva):
    """linear disassembly of .text, streamed; capstone stops at an undecodable byte -> resume one byte later"""
    pos = 0
    while pos < len(blob):
        last = None
        for ins in md.disasm(blob[pos:], tva + pos):
            yield ins
            last = ins
        if last is None:
            pos += 1
        else:
            pos = last.address + last.size - tva
            if pos < len(blob):
                pos += 1


def run_pc(path, globals_, vts, limit, getters=()):
    exe = open(path, 'rb').read()
    _, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    _, tva, traw, tsize, _ = [s for s in secs if s[0] == '.text'][0]
    blob = exe[traw:traw + tsize]

    def dword(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size:
                return struct.unpack_from('<I', exe, rptr + va - sva)[0]
        return None

    methods = set()
    for vt, n in vts:
        for k in range(n):
            methods.add(dword(vt + 4 * k))
    REG = {CX.X86_REG_EAX: 'eax', CX.X86_REG_EBX: 'ebx', CX.X86_REG_ECX: 'ecx', CX.X86_REG_EDX: 'edx',
           CX.X86_REG_ESI: 'esi', CX.X86_REG_EDI: 'edi', CX.X86_REG_EBP: 'ebp'}
    hits = set()
    # passes until no new method (function entered with ecx = owner) is found; function start = first
    # instruction after int3 padding or a method address (heuristic)
    for _pass in range(5):
        calls_with_this = set()
        owner = set()
        cur_func = None
        prev_pad = True
        for ins in pc_insns(md, blob, tva):
            if ins.mnemonic == 'int3':
                prev_pad = True
                owner = set()
                continue
            if prev_pad or (ins.address in methods and cur_func != ins.address):
                cur_func = ins.address
                owner = {'ecx'} if ins.address in methods else set()
                prev_pad = False
            ops = ins.operands
            for o in ops:
                if o.type == CX.X86_OP_MEM and o.mem.base in REG and REG[o.mem.base] in owner \
                        and o.mem.index == 0 and 0 <= o.mem.disp < limit and ins.mnemonic != 'lea':
                    hits.add((ins.address, cur_func, ins.mnemonic + ' ' + ins.op_str, o.mem.disp, REG[o.mem.base]))
            if ins.mnemonic == 'call':
                if 'ecx' in owner and ops and ops[0].type == CX.X86_OP_IMM:
                    calls_with_this.add(ops[0].imm)
                owner -= {'eax', 'ecx', 'edx'}
                if ops and ops[0].type == CX.X86_OP_IMM and ops[0].imm in getters:   # getter returns the owner
                    owner.add('eax')
                continue
            if ins.mnemonic == 'ret':
                owner = set()
                continue
            if len(ops) == 2 and ops[0].type == CX.X86_OP_REG and ops[0].reg in REG:
                dst = REG[ops[0].reg]
                src_owner = False
                if ins.mnemonic == 'mov':
                    if ops[1].type == CX.X86_OP_MEM and ops[1].mem.base == 0 and ops[1].mem.index == 0 \
                            and (ops[1].mem.disp & 0xffffffff) in globals_:
                        src_owner = True
                    elif ops[1].type == CX.X86_OP_REG and ops[1].reg in REG and REG[ops[1].reg] in owner:
                        src_owner = True
                if ins.mnemonic not in ('cmp', 'test'):
                    owner.discard(dst)
                if src_owner:
                    owner.add(dst)
            elif ins.mnemonic == 'pop' and ops and ops[0].type == CX.X86_OP_REG and ops[0].reg in REG:
                owner.discard(REG[ops[0].reg])
        new = calls_with_this - methods
        if not new:
            break
        methods |= new
    return list(hits), sorted(methods)


def main(argv):
    mode, path, glob = argv[0], argv[1], argv[2]
    globals_ = set(int(x, 16) for x in glob.split(','))
    vts = []
    limit = 0x28
    if '--vt' in argv:
        for p in argv[argv.index('--vt') + 1].split(','):
            a, n = p.split(':')
            vts.append((int(a, 16), int(n)))
    if '--limit' in argv:
        limit = int(argv[argv.index('--limit') + 1], 16)
    if mode == 'ppc':
        hits, meth = run_ppc(path, globals_, vts, limit)
        for a, fs, kind, disp, reg in sorted(set(hits)):
            print('0x%08x  func 0x%08x  %s +0x%02x  (%s)' % (a, fs, kind, disp, reg))
    else:
        getters = set(int(x, 16) for x in argv[argv.index('--getter') + 1].split(',')) if '--getter' in argv else set()
        hits, meth = run_pc(path, globals_, vts, limit, getters)
        for a, fs, text, disp, reg in sorted(set(hits)):
            print('0x%08x  func 0x%08x  +0x%02x  %s' % (a, fs, disp, text))
    print('# %d accesses, %d method candidates' % (len(set(hits)), len(meth)))
    by = {}
    for h in set(hits):
        by.setdefault(h[3], 0)
        by[h[3]] += 1
    print('# by displacement: ' + ', '.join('+0x%02x:%d' % (k, by[k]) for k in sorted(by)))


if __name__ == '__main__':
    main(sys.argv[1:])
