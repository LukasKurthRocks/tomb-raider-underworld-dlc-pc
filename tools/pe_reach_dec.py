"""Find the x86 instructions that DECREMENT a memory dword at a given displacement (default +4) in a 32-bit PE such as
tru.exe - either in every function reachable through direct calls from one or more roots, or in the whole code
(read-only; thrall link crash tru+0x1976a3: during the removal of a thrall instance something turns its +4 link
(the pointer to the next older instance of its category list) into "pointer - 1", docs Befund-Thrall-Absturz.md).

Classes reported (the memory operand is [base (+ index*scale) + DISP], base not esp / ebp):
  dec        dec dword ptr [r+DISP]
  sub1       sub dword ptr [r+DISP], 1
  add-1      add dword ptr [r+DISP], -1
  xadd       (lock) xadd dword ptr [r+DISP], reg   (interlocked add; usually reg = -1 for a release)
  mov-1      mov dword ptr [r+DISP], reg  where reg was made by dec / sub reg,1 / add reg,-1 / lea reg,[x-1] at most
             4 instructions before (same linear run)
  byte       any write of a BYTE at [r+DISP] (low byte of a dword link: 0x..60 -> 0x..5f is possible)
  ilockdec   call dword ptr [IAT InterlockedDecrement / InterlockedExchangeAdd] (argument not resolved)
Reachable mode: recursive descent per function (jcc both ways, jmp tables read from the image, ret / int3 end a run),
only DIRECT calls are followed (calls through registers / vtables / instance callbacks are counted, not followed - give
their targets as extra roots, e.g. the type callbacks of "enemy" 0x6187c0 / 0x627a80). Output: one line per hit with
the function it lies in, the call depth and the shortest call path from a root.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_reach_dec.py EXE ROOT[,ROOT..] [--depth 4] [--disp 0x4] [--max-funcs 4000] [--no-byte]
  ../bin/pyt -t 900 tools/pe_reach_dec.py EXE --global [--disp 0x4] [--no-byte] [--context N]   every executable
                     section; --context N = also print the N instructions before each hit (same linear run)
  e.g. ../bin/pyt -t 900 tools/pe_reach_dec.py tru.exe 0x5bcba0,0x6187c0,0x627a80 --depth 5
Exit code: 0 = done, 2 = usage error.
"""
import sys, os, struct, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from capstone import x86 as X
import pe_callers as PE

IAT_DEC = {0x0083e174: 'InterlockedDecrement', 0x0083e0bc: 'InterlockedExchangeAdd'}   # tru.exe Steam build
BAD_BASE = {X.X86_REG_ESP, X.X86_REG_EBP}


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


class Image:
    def __init__(self, path):
        self.pe = open(path, 'rb').read()
        self.base, self.secs = PE.sections(self.pe)
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True
        self.cache = {}

    def exec_range(self, va):
        for name, sva, rptr, size, ch in self.secs:
            if (ch & 0x20000000) and sva <= va < sva + size:
                return sva, rptr, size
        return None

    def u32(self, va):
        for name, sva, rptr, size, ch in self.secs:
            if sva <= va and va + 4 <= sva + size:
                return struct.unpack_from('<I', self.pe, rptr + va - sva)[0]
        return None

    def insn(self, va):
        if va in self.cache:
            return self.cache[va]
        r = self.exec_range(va)
        ins = None
        if r:
            sva, rptr, size = r
            o = rptr + va - sva
            for i in self.md.disasm(self.pe[o:o + 16], va, 1):
                ins = i
        self.cache[va] = ins
        return ins


def mem_ops(ins):
    return [op for op in ins.operands if op.type == X.X86_OP_MEM]


def classify(ins, disp, prev, no_byte):
    """class name or None"""
    m = ins.mnemonic
    if m == 'call' and ins.operands and ins.operands[0].type == X.X86_OP_MEM:
        op = ins.operands[0]
        if op.mem.base == 0 and op.mem.index == 0 and (op.mem.disp & 0xffffffff) in IAT_DEC:
            return 'ilockdec ' + IAT_DEC[op.mem.disp & 0xffffffff]
        return None
    ops = ins.operands
    if not ops or ops[0].type != X.X86_OP_MEM:
        return None
    mo = ops[0].mem
    if (mo.disp & 0xffffffff) != disp or mo.base in BAD_BASE or (mo.base == 0 and mo.index == 0):
        return None
    size = ops[0].size
    if size == 1 and not no_byte and m not in ('cmp', 'test', 'push'):
        if m.startswith(('mov', 'dec', 'sub', 'add', 'and', 'or', 'xor', 'inc', 'set', 'xchg', 'neg', 'not', 'shr',
                         'shl', 'sar', 'rol', 'ror', 'btr', 'bts', 'btc')):
            return 'byte'
        return None
    if size != 4:
        return None
    if m == 'dec':
        return 'dec'
    if m == 'sub' and len(ops) == 2 and ops[1].type == X.X86_OP_IMM and ops[1].imm == 1:
        return 'sub1'
    if m == 'add' and len(ops) == 2 and ops[1].type == X.X86_OP_IMM and (ops[1].imm & 0xffffffff) == 0xffffffff:
        return 'add-1'
    if m == 'xadd':
        return 'xadd'
    if m == 'mov' and len(ops) == 2 and ops[1].type == X.X86_OP_REG:
        r = ops[1].reg
        for p in prev[-4:]:
            if not p.operands or p.operands[0].type != X.X86_OP_REG or p.operands[0].reg != r:
                continue
            pm, po = p.mnemonic, p.operands
            if pm == 'dec' or (pm == 'sub' and len(po) == 2 and po[1].type == X.X86_OP_IMM and po[1].imm == 1) or \
               (pm == 'add' and len(po) == 2 and po[1].type == X.X86_OP_IMM and (po[1].imm & 0xffffffff) == 0xffffffff) or \
               (pm == 'lea' and po[1].type == X.X86_OP_MEM and po[1].mem.disp == -1):
                return 'mov-1 (%s %s @0x%x)' % (pm, p.op_str, p.address)
    return None


def explore(img, roots, depth_max, disp, max_funcs, no_byte):
    owner = {}                       # insn va -> function start
    funcs = collections.OrderedDict()   # start -> (depth, parent)
    q = collections.deque()
    for r in roots:
        funcs[r] = (0, None)
        q.append(r)
    hits, indirect = [], collections.Counter()
    while q:
        f = q.popleft()
        d = funcs[f][0]
        work = [f]
        while work:
            a = work.pop()
            prev = []
            while True:
                if a in owner:
                    break
                ins = img.insn(a)
                if ins is None:
                    break
                owner[a] = f
                c = classify(ins, disp, prev, no_byte)
                if c:
                    hits.append((ins.address, '%s %s' % (ins.mnemonic, ins.op_str), c, f))
                prev.append(ins)
                m = ins.mnemonic
                nxt = a + ins.size
                if m in ('ret', 'retf', 'int3', 'hlt', 'ud2'):
                    break
                if m == 'call':
                    op = ins.operands[0]
                    if op.type == X.X86_OP_IMM:
                        t = op.imm & 0xffffffff
                        if img.exec_range(t) and t not in funcs and d + 1 <= depth_max and len(funcs) < max_funcs:
                            funcs[t] = (d + 1, f)
                            q.append(t)
                    else:
                        indirect[f] += 1
                    a = nxt
                    continue
                if m == 'jmp':
                    op = ins.operands[0]
                    if op.type == X.X86_OP_IMM:
                        t = op.imm & 0xffffffff
                        if t < f or t > f + 0x8000:      # tail call into another function
                            if img.exec_range(t) and t not in funcs and d + 1 <= depth_max and len(funcs) < max_funcs:
                                funcs[t] = (d + 1, f)
                                q.append(t)
                        else:
                            work.append(t)
                    elif op.type == X.X86_OP_MEM and op.mem.index != 0 and op.mem.scale == 4 and op.mem.base == 0:
                        tbl = op.mem.disp & 0xffffffff
                        for k in range(512):
                            v = img.u32(tbl + 4 * k)
                            if v is None or not img.exec_range(v):
                                break
                            work.append(v)
                    else:
                        indirect[f] += 1
                    break
                if m.startswith('j') or m.startswith('loop'):
                    op = ins.operands[0]
                    if op.type == X.X86_OP_IMM:
                        work.append(op.imm & 0xffffffff)
                a = nxt
    return funcs, hits, indirect


def path_of(funcs, f):
    p = []
    while f is not None:
        p.append(f)
        f = funcs[f][1]
    return ' <- '.join('0x%x' % x for x in p)


def main(argv):
    argv = list(argv)
    disp = int(opt(argv, '--disp', '0x4'), 16)
    depth = int(opt(argv, '--depth', '4'))
    max_funcs = int(opt(argv, '--max-funcs', '4000'))
    context = int(opt(argv, '--context', '0'))
    no_byte = '--no-byte' in argv
    if no_byte:
        argv.remove('--no-byte')
    glob = '--global' in argv
    if glob:
        argv.remove('--global')
    if len(argv) != (1 if glob else 2):
        print(__doc__)
        return 2
    img = Image(argv[0])
    if glob:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = True
        md.skipdata = True
        n, cnt = 0, collections.Counter()
        for name, sva, rptr, size, ch in img.secs:
            if not (ch & 0x20000000):
                continue
            prev = []
            for ins in md.disasm(img.pe[rptr:rptr + size], sva):
                if ins.id == 0:
                    prev = []
                    continue
                c = classify(ins, disp, prev, no_byte)
                if c:
                    n += 1
                    cnt[c.split(' ')[0]] += 1
                    ctx = ' | '.join('%s %s' % (p.mnemonic, p.op_str) for p in prev[-context:]) if context else ''
                    print('0x%08x  %-8s %s %s%s' % (ins.address, c.split(' ')[0], ins.mnemonic, ins.op_str,
                                                    ('    <- ' + ctx) if ctx else ''))
                prev.append(ins)
                if len(prev) > 6:
                    prev.pop(0)
                if ins.mnemonic in ('ret', 'int3', 'jmp'):
                    prev = []
        print('# global: %d hit(s) at disp 0x%x: %s' % (n, disp, ', '.join('%s %d' % kv for kv in sorted(cnt.items()))))
        return 0
    roots = [int(x, 16) for x in argv[1].split(',')]
    funcs, hits, indirect = explore(img, roots, depth, disp, max_funcs, no_byte)
    print('# roots %s, depth %d, disp 0x%x: %d function(s) reached (direct calls only), %d indirect call/jmp site(s) '
          'not followed' % (', '.join('0x%x' % r for r in roots), depth, disp, len(funcs), sum(indirect.values())))
    cnt = collections.Counter(h[2].split(' ')[0] for h in hits)
    for a, t, c, f in sorted(hits, key=lambda h: (funcs[h[3]][0], h[0])):
        print('0x%08x  tru+0x%06x  %-10s %-40s fn 0x%x depth %d  path %s' % (
            a, a - 0x400000, c.split(' ')[0], t, f, funcs[f][0], path_of(funcs, f)))
        if c.startswith('mov-1') or c.startswith('ilockdec'):
            print('            %s' % c)
    print('# hits: %d (%s)' % (len(hits), ', '.join('%s %d' % kv for kv in sorted(cnt.items())) or 'none'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
