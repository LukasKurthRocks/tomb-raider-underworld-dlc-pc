"""Stack check for the small state-program VM of tru.exe (tru+0x32b20) and the DTP sections that carry its code
(read-only; test 50d/50b heap crash: a VM value stack underflow writes the heap boundary tag before the stack buffer).

VM (proven from tru.exe, see docs/Befund-Felsrinne.md "Test 50e"):
  context (0x2c bytes, ctor tru+0x37020): +0x00 code, +0x04 top index (-1 = empty), +0x08 pc, +0x0c frame base,
  +0x10 stack buffer (malloc 0x200), +0x14 frame buffer (malloc 0xc0, 12-byte frames), +0x18 frame depth.
  Value at index i = [base + 4 i]; index -1 = base - 4 = the heap boundary tag of the stack buffer at depth 0.
  Code word = op << 24 | operand (24 bit). Opcodes handled (byte map tru+0x32e48, jump table tru+0x32df8):
    0x01 pop            0x02 push literal (next word)        0x47 neg (top)      0x48-0x4b add/sub/mul/div (2->1)
    0x4c-0x4e compare (2->1)  0x4f -  0x50 not (top)  0x51 and, 0x52 or (2->1)   0x5a f2i (top)  0x5c i2f (top)
    0x63 jump (operand = signed word offset from the next word)   0x64 pop, jump if false
    0x65 native: pops fn (top) and ns, calls table [0x008ac128 + 4 ns][fn](ctx); the native pops its arguments and
         pushes its result itself (helpers pop tru+0x32ed0, push float +0x32ee0, int +0x32f00, bool +0x32f20)
    0x7b return (frame pop; ends the run at depth 0)        every other opcode: no stack effect (skipped)
  Native stack effect: counted in the native's x86 body (calls of the helpers above, inline [ecx+4] arithmetic);
  natives with a different number of pushes on different branches are marked '?'.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/statevm_check.py natives EXE
  ../bin/pyt -t 300 tools/statevm_check.py dis EXE DRM SECTION_ID [--be]      disassembly + depth per word
  ../bin/pyt -t 900 tools/statevm_check.py scan EXE DRM [--be] [--all]        every type-7 section with VM code:
        min depth / underflow; --all lists clean ones too
  DRM = PC (little-endian) file; --be reads an Xbox file (natives then still from the PC EXE - compare only the code)
  ../bin/pyt -t 900 tools/statevm_check.py compare XBOX.drm PC.drm [--by-order] [--ids ID,..] [--fix OUT.drm]
        every VM code word (literals included, pointer / id fields excluded) must equal the Xbox u32 (word-wise
        conversion); --by-order pairs the k-th VM DTP of each file (base pairs re-number DTPs); --fix writes the Xbox
        words into a copy (CDRM kept) and reads it back.  Base proof x_lara / pc_lara: 218 sections, 0 differing.
  ../bin/pyt -t 1800 tools/statevm_check.py tree DIR [DIR ..]      every PC .drm against its Xbox DLC original from
        work/generic/dlc_drms.pkl (by file name, sections by id)
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE
import drm_write as DW
import drm_reloc as R

NATIVE_TABLE = 0x008ac128
POP, PUSHF, PUSHI, PUSHB = 0x00432ed0, 0x00432ee0, 0x00432f00, 0x00432f20
OPS = {0x01: (-1, 'pop'), 0x02: (+1, 'push'), 0x47: (0, 'neg'), 0x48: (-1, 'add'), 0x49: (-1, 'sub'),
       0x4a: (-1, 'mul'), 0x4b: (-1, 'div'), 0x4c: (-1, 'cmp4c'), 0x4d: (-1, 'cmp4d'), 0x4e: (-1, 'cmp4e'),
       0x50: (0, 'not'), 0x51: (-1, 'and'), 0x52: (-1, 'or'), 0x5a: (0, 'f2i'), 0x5c: (0, 'i2f'),
       0x63: (0, 'jmp'), 0x64: (-1, 'jz'), 0x65: (-2, 'native'), 0x7b: (0, 'ret')}


class Exe:
    def __init__(self, path):
        self.b = open(path, 'rb').read()
        self.base, self.secs = PE.sections(self.b)

    def off(self, a):
        for _, sva, rptr, size, _ in self.secs:
            if sva <= a < sva + size: return rptr + a - sva
        return -1

    def u32(self, a):
        return struct.unpack_from('<I', self.b, self.off(a))[0]


def native_tables(X):
    out = []
    for ns in range(2):
        t = X.u32(NATIVE_TABLE + 4 * ns)
        fns = []
        while True:
            v = X.u32(t + 4 * len(fns))
            if not (0x00401000 <= v < 0x00840000) or v in (X.u32(NATIVE_TABLE), X.u32(NATIVE_TABLE + 4)): break
            fns.append(v)
        out.append(fns)
    return out


def native_effect(X, a, md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)):
    """(pops, pushes, branchy) of a native: walk all paths (bounded), count helper calls per path."""
    o = X.off(a)
    code = X.b[o:o + 0x1000]
    ins = {}
    for i in md.disasm(code, a):
        ins[i.address] = i
        if i.mnemonic == 'int3': break
    results = set()
    REG32 = ('eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp')

    def num(t):
        t = t.strip()
        v = int(t, 16) if t.startswith('0x') or t.startswith('-0x') else int(t)
        return v - (1 << 32) if v > 0x7fffffff else v

    def walk(pc, pops, pushes, depth, seen, regs, sp):
        # regs: reg -> 'ctx' | ('top', k) (value of [ctx+4] plus k); sp = bytes pushed since entry
        if depth > 60 or len(results) > 40: return
        regs = dict(regs)
        while pc in ins:
            i = ins[pc]
            if pc in seen: return
            seen = seen | {pc}
            m, op = i.mnemonic, i.op_str
            ops = [x.strip() for x in op.split(',')] if op else []
            ctxregs = [r for r, v in regs.items() if v == 'ctx']
            if m == 'push': sp += 4
            elif m == 'pop':
                sp -= 4
                if ops and ops[0] in regs: del regs[ops[0]]
            elif m == 'sub' and ops[0] == 'esp': sp += num(ops[1])
            elif m == 'add' and ops[0] == 'esp': sp -= num(ops[1])
            if m == 'call':
                try: t = int(op, 16)
                except ValueError: t = None
                if regs.get('ecx') == 'ctx':
                    if t == POP: pops += 1
                    elif t in (PUSHF, PUSHI, PUSHB): pushes += 1
                elif t in (POP, PUSHF, PUSHI, PUSHB):
                    if t == POP: pops += 1
                    else: pushes += 1
                for r in ('eax', 'ecx', 'edx'): regs.pop(r, None)
                if t in (PUSHF, PUSHI, PUSHB): sp -= 4   # ret 4
            elif m == 'mov' and len(ops) == 2:
                dst, src = ops
                if dst in REG32:
                    if src == 'dword ptr [esp + 0x%x]' % (sp + 4) or (sp == 0 and src == 'dword ptr [esp + 4]'):
                        regs[dst] = 'ctx'
                    elif src in REG32 and src in regs: regs[dst] = regs[src]
                    elif any(src == 'dword ptr [%s + 4]' % c for c in ctxregs): regs[dst] = ('top', 0)
                    else: regs.pop(dst, None)
                elif any(dst == 'dword ptr [%s + 4]' % c for c in ctxregs) and src in regs and \
                        isinstance(regs[src], tuple):
                    k = regs[src][1]
                    if k < 0: pops -= k
                    else: pushes += k
                    regs = {r: (('top', v[1] - k) if isinstance(v, tuple) else v) for r, v in regs.items()}
            elif m in ('add', 'sub') and len(ops) == 2:
                dst, src = ops
                if dst in regs and isinstance(regs[dst], tuple) and not src in REG32:
                    k = num(src) if m == 'add' else -num(src)
                    regs[dst] = ('top', regs[dst][1] + k)
                elif any(dst == 'dword ptr [%s + 4]' % c for c in ctxregs):
                    k = num(src) if m == 'add' else -num(src)
                    if k < 0: pops -= k
                    else: pushes += k
                elif dst in regs: regs.pop(dst, None)
            elif m == 'lea' and len(ops) == 2 and ops[0] in REG32:
                src = ops[1]
                hit = None
                for r, v in list(regs.items()):
                    if isinstance(v, tuple):
                        for sign in ('+', '-'):
                            pre = 'dword ptr [%s %s ' % (r, sign) if False else '[%s %s ' % (r, sign)
                            if src.startswith(pre) and src.endswith(']') and '*' not in src:
                                k = num(src[len(pre):-1]); hit = ('top', v[1] + (k if sign == '+' else -k))
                if hit: regs[ops[0]] = hit
                else: regs.pop(ops[0], None)
            elif m in ('xor', 'or', 'and', 'movzx', 'movsx', 'imul', 'shl', 'shr', 'sar', 'sete', 'setne') and ops \
                    and ops[0] in regs:
                regs.pop(ops[0], None)
            elif m.startswith('ret'):
                results.add((pops, pushes)); return
            elif m == 'jmp':
                try: t = int(op, 16)
                except ValueError: results.add((pops, pushes)); return
                if t not in ins:   # tail call into a helper / another function
                    if t == POP: pops += 1
                    elif t in (PUSHF, PUSHI, PUSHB): pushes += 1
                    results.add((pops, pushes)); return
                pc = t; continue
            elif m.startswith('j'):
                try: t = int(op, 16)
                except ValueError: t = None
                if t is not None: walk(t, pops, pushes, depth + 1, seen, regs, sp)
            pc = i.address + i.size
    walk(a, 0, 0, 0, frozenset(), {}, 0)
    if not results: return None, None, True
    pops = {p for p, _ in results}; pushes = {q for _, q in results}
    return max(pops), max(pushes), (len(pops) > 1 or len(pushes) > 1)


def native_effects(X):
    tabs = native_tables(X)
    eff = {}
    for ns, fns in enumerate(tabs):
        for fn, a in enumerate(fns):
            eff[(ns, fn)] = (a,) + native_effect(X, a)
    return tabs, eff


def code_blocks(s, e):
    """code starts of a VM DTP: the targets of the internal pointers at +4 / +8 / +0xc when +0 points at +4"""
    rel = R.parse(s.reloc, e)
    it = dict(rel.internal)
    if it.get(0) != 4: return []
    out = []
    for o in (4, 8, 0x0c):
        if o in it: out.append(it[o])
    return out


def run_block(d, e, start, end, eff, lines=None):
    """abstract depth walk over all paths; returns (min depth, first underflow pc, natives used)"""
    E = '>' if e == 'be' else '<'
    word = lambda p: struct.unpack_from(E + 'I', d, p)[0]
    best = {}
    worst = [0, None]
    used = set()
    todo = [(start, 0)]
    steps = 0
    while todo and steps < 200000:
        pc, dep = todo.pop(); steps += 1
        while start <= pc < end:
            if best.get(pc, 99) <= dep and pc in best: break
            best[pc] = dep
            w = word(pc); op, arg = w >> 24, w & 0xffffff
            nxt = pc + 4
            if op == 0x02:
                dep += 1; nxt = pc + 8
            elif op == 0x65:
                # ns / fn are the two literals pushed right before (push ns; push fn; native)
                ns = word(pc - 12) if pc - 16 >= start and word(pc - 16) >> 24 == 2 else None
                fn = word(pc - 4) if pc - 8 >= start and word(pc - 8) >> 24 == 2 else None
                dep -= 2
                k = (ns, fn); used.add(k)
                a, pops, pushes, br = eff.get(k, (None, None, None, True))
                if pops is None:
                    if lines is not None: lines.append('   unknown native %s at +0x%x' % (k, pc))
                else:
                    if dep - pops < worst[0]: worst[:] = [dep - pops, pc]
                    dep += pushes - pops
            elif op in OPS:
                dep += OPS[op][0]
            if dep < worst[0]: worst[:] = [dep, pc]
            if op == 0x7b: break
            if op == 0x63:
                o = arg - (1 << 24) if arg & 0x800000 else arg
                nxt = pc + 4 + 4 * o
            elif op == 0x64:
                o = arg - (1 << 24) if arg & 0x800000 else arg
                todo.append((pc + 4 + 4 * o, dep))
            pc = nxt
    return worst[0], worst[1], used, best


def dis(X, path, sid, e):
    D = DW.read(open(path, 'rb').read(), e)
    s = [x for x in D.sections if x.type == 7 and x.id == sid][0]
    tabs, eff = native_effects(X)
    blocks = code_blocks(s, e)
    E = '>' if e == 'be' else '<'
    print('section 7:%d %d bytes, code blocks %s' % (sid, len(s.data), ['+0x%x' % b for b in blocks]))
    ends = sorted(blocks) + [len(s.data)]
    for b in blocks:
        end = min(x for x in ends if x > b)
        lines = []
        mn, at, used, depth = run_block(s.data, e, b, end, eff, lines)
        print('== block +0x%x .. +0x%x: min depth %d%s' % (b, end, mn, (' at +0x%x' % at) if at is not None else ''))
        for l in lines: print(l)
        p = b
        while p < end:
            w = struct.unpack_from(E + 'I', s.data, p)[0]; op, arg = w >> 24, w & 0xffffff
            txt = OPS.get(op, (0, 'op%02x' % op))[1]
            extra = ''
            if op == 0x02:
                lit = struct.unpack_from(E + 'I', s.data, p + 4)[0]
                f = struct.unpack('<f', struct.pack('<I', lit))[0]
                extra = ' 0x%x (%g)' % (lit, f)
            elif op == 0x65:
                ns = struct.unpack_from(E + 'I', s.data, p - 12)[0]; fn = struct.unpack_from(E + 'I', s.data, p - 4)[0]
                a, pops, pushes, br = eff.get((ns, fn), (None, None, None, True))
                extra = ' ns %s fn %s -> %s pops %s pushes %s%s' % (ns, fn, ('0x%08x' % a) if a else '?', pops, pushes,
                                                                    ' (branches differ)' if br else '')
            elif op in (0x63, 0x64):
                o = arg - (1 << 24) if arg & 0x800000 else arg
                extra = ' -> +0x%x' % (p + 4 + 4 * o)
            print('  +0x%04x d=%-4s %08x %s%s' % (p, depth.get(p, '-'), w, txt, extra))
            p += 8 if op == 0x02 else 4


def scan(X, path, e, show_all):
    D = DW.read(open(path, 'rb').read(), e)
    tabs, eff = native_effects(X)
    n = bad = 0
    for s in D.sections:
        if s.type != 7: continue
        blocks = code_blocks(s, e)
        if not blocks: continue
        ends = sorted(blocks) + [len(s.data)]
        for b in blocks:
            end = min(x for x in ends if x > b)
            if end - b < 4: continue
            n += 1
            mn, at, used, _ = run_block(s.data, e, b, end, eff)
            if mn < 0: bad += 1
            if mn < 0 or show_all:
                print('7:%-6d block +0x%04x len %5d min depth %3d%s natives %s' % (
                    s.id, b, end - b, mn, (' at +0x%x' % at) if at is not None else '',
                    ' '.join('%s/%s' % k for k in sorted(used, key=str))))
    print('blocks %d, underflow %d' % (n, bad))


def code_words(s, e):
    """{offset: u32} of every VM code word (literals included) of a VM DTP; pointer fields excluded"""
    blocks = code_blocks(s, e)
    if not blocks: return {}
    E = '>' if e == 'be' else '<'
    rel = R.parse(s.reloc, e)
    ptrs = set(rel.pointer_offsets()) | set(rel.id_offsets())
    out = {}
    for b in blocks:
        end = min([x for x in blocks if x > b] + [len(s.data)])
        for p in range(b, end - 3, 4):
            if p not in ptrs: out[p] = struct.unpack_from(E + 'I', s.data, p)[0]
    return out


def compare(xbox, pc, fix_out=None, ids=None, by_order=False):
    """PC code words must equal the Xbox code words (word-wise endian conversion); list / fix the others"""
    DX = DW.read(open(xbox, 'rb').read(), 'be')
    DP = DW.read(open(pc, 'rb').read(), 'le')
    xs = {(s.type, s.id): s for s in DX.sections}
    if by_order:   # base pairs re-number the DTPs: pair the k-th VM section of each file
        xv = [s for s in DX.sections if s.type == 7 and code_blocks(s, 'be')]
        pv = [s for s in DP.sections if s.type == 7 and code_blocks(s, 'le')]
        print('VM sections: Xbox %d, PC %d (paired by order)' % (len(xv), len(pv)))
        pair = {id(p): x for p, x in zip(pv, xv)}
    nsec = nwords = nbad = 0
    changed = []
    for k, s in enumerate(DP.sections):
        if s.type != 7 or (ids and s.id not in ids): continue
        x = pair.get(id(s)) if by_order else xs.get((7, s.id))
        if x is None: continue
        wp, wx = code_words(s, 'le'), code_words(x, 'be')
        if not wp: continue
        nsec += 1
        if set(wp) != set(wx):
            print('7:%d code layout differs (PC %d words, Xbox %d)' % (s.id, len(wp), len(wx))); continue
        bad = [(o, wp[o], wx[o]) for o in sorted(wp) if wp[o] != wx[o]]
        nwords += len(wp); nbad += len(bad)
        for o, a, b in bad:
            sw = struct.unpack('<I', struct.pack('>I', b))[0]
            print('7:%-6d +0x%04x PC 0x%08x Xbox 0x%08x%s' % (s.id, o, a, b,
                  '  (= Xbox word not byte-swapped)' if a == sw else ''))
        if bad and fix_out:
            d = bytearray(s.data)
            for o, a, b in bad: struct.pack_into('<I', d, o, b)
            DP.sections[k] = DW.Section(s.type, s.id, bytes(d), s.reloc, s.flags, s.ver, s.spec, s.pad)
            changed.append(s.id)
    print('VM sections compared %d, code words %d, differing %d' % (nsec, nwords, nbad))
    if fix_out:
        os.makedirs(os.path.dirname(os.path.abspath(fix_out)), exist_ok=True)
        raw = DP.write('le')
        if open(pc, 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(fix_out, 'wb').write(raw)
        # readback
        DR = DW.read(open(fix_out, 'rb').read(), 'le')
        assert len(DR.sections) == len(DP.sections)
        for a, b in zip(DR.sections, DP.sections):
            assert (a.type, a.id, a.data, a.reloc) == (b.type, b.id, b.data, b.reloc)
        print('wrote %s (%d sections changed: %s), readback ok' % (fix_out, len(changed), changed))


def compare_tree(dirs):
    """every PC .drm under DIRS against its Xbox DLC original from work/generic/dlc_drms.pkl (by file name)"""
    import pickle
    W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_drms.pkl')
    C = pickle.load(open(W, 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    byname = {}
    for k, v in C.items(): byname.setdefault(base(k[1]), []).append((k[0], v))
    tot_s = tot_w = tot_b = 0
    for top in dirs:
        for dp, dn, fn in os.walk(top):
            for f in sorted(fn):
                if not f.lower().endswith('.drm'): continue
                p = os.path.join(dp, f)
                xs = byname.get(base(f))
                if not xs: continue
                DP = DW.read(open(p, 'rb').read(), 'le')
                h, secs = xs[0][1]
                X = {(s['type'], s['id']): DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'],
                                                      s['spec']) for s in secs if s['type'] == 7}
                ns = nw = nb = 0
                for s in DP.sections:
                    x = X.get((s.type, s.id)) if s.type == 7 else None
                    if x is None: continue
                    wp, wx = code_words(s, 'le'), code_words(x, 'be')
                    if not wp: continue
                    ns += 1
                    if set(wp) != set(wx):
                        print('  %s 7:%d code layout differs' % (f, s.id)); continue
                    bad = [o for o in sorted(wp) if wp[o] != wx[o]]
                    nw += len(wp); nb += len(bad)
                    for o in bad:
                        print('  %s 7:%-6d +0x%04x PC 0x%08x Xbox 0x%08x' % (f, s.id, o, wp[o], wx[o]))
                if ns: print('%s (%s): VM sections %d, code words %d, differing %d' % (p, xs[0][0], ns, nw, nb))
                tot_s += ns; tot_w += nw; tot_b += nb
    print('total: VM sections %d, code words %d, differing %d' % (tot_s, tot_w, tot_b))


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'tree':
        compare_tree(argv[1:]); return 0
    if argv[0] == 'compare':
        ids = None
        if '--ids' in argv: k = argv.index('--ids'); ids = {int(x) for x in argv[k + 1].split(',')}
        fix = argv[argv.index('--fix') + 1] if '--fix' in argv else None
        compare(argv[1], argv[2], fix, ids, '--by-order' in argv)
        return 0
    X = Exe(argv[1])
    e = 'be' if '--be' in argv else 'le'
    if argv[0] == 'natives':
        tabs, eff = native_effects(X)
        for (ns, fn), (a, pops, pushes, br) in sorted(eff.items()):
            print('ns %d fn %3d (0x%02x) 0x%08x pops %s pushes %s%s' % (ns, fn, fn, a, pops, pushes,
                                                                       ' (branches differ)' if br else ''))
        print('ns0 %d natives, ns1 %d natives' % (len(tabs[0]), len(tabs[1])))
    elif argv[0] == 'dis':
        dis(X, argv[2], int(argv[3]), e)
    elif argv[0] == 'scan':
        scan(X, argv[2], e, '--all' in argv)
    else:
        print(__doc__); return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
