"""TruDataGuard offline checks (read-only): callers of the section lookup, the table in crash dumps, rule replay.

The section lookup tru+0x14df80 (VA 0x54df80) reads `[id*4 + 0xc36f28]`; the table has 0x8000 entries (the register
function tru+0x14dd10 asserts 0 < id < 0x8000). TruDataGuard.asi returns 0 ("not found") for an id >= 0x8000 or an
entry that is not a plausible section record. This tool checks that decision offline.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dataguard_check.py callers EXE
        every call / jmp of 0x54df80 and 0x54df70, classified by what the caller does with the result before it
        dereferences it: TESTS (test / cmp with 0 + jcc), DEREF (memory access through the result first), PASS (pushed
        as an argument / stored, handled elsewhere), RET (tail return), UNKNOWN. Writes nothing.
  ../bin/pyt -t 900 tools/dataguard_check.py table DUMP [DUMP ...]
        reads the 0x8000-entry table from a full crash dump (tru_av2_full.dmp), applies the plugin's rule to every
        entry (all non-zero entries must pass = good ids) and prints the record field statistics; then replays the
        recorded bad ids of 2026-11-02 (50d / 50e / 50f / 50h) and the faulting id of the dump's own exception.
  ../bin/pyt -t 60 tools/dataguard_check.py replay
        the recorded bad ids against the rule without a dump (out-of-range ids only need the bound).
  ../bin/pyt -t 300 tools/dataguard_check.py prechecks EXE src/asi/TruDataGuard/TruDataGuard.cpp OUT.txt
        checks that the plugin's kGuardedCallers equals the TESTS callers found now and writes the plugin's byte
        checks as a list for tools/pe_bytes_check.py --file.
Exit code 1 if a good entry is rejected or a bad id is accepted (table / replay) or the caller lists differ.
The caller classes are a straight-line heuristic (conditional branches other than the 0 test are not followed); the
0 path of a TESTS caller is followed as well (ZDEREF = it dereferences the 0 anyway, ZRET = it returns it).
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

LOOKUP = 0x54df80          # section lookup: record + 0x10 or 0 (cdecl, one argument)
EXISTS = 0x54df70          # exists test: setne al (cdecl, one argument)
TABLE = 0xc36f28
COUNT = 0x8000
MIN_PTR = 0x10000
ALIGN_MASK = 0xf           # the same constants as TruDataGuard.cpp (kTableCount, kMinPointer, kAlignMask)

# recorded bad inputs (docs Befund-Felsrinne.md; runs\20261102_*): (run, id, caller return address, note)
BAD_IDS = [
    ('50d', 0x688c0000, 0x535ec5, 'player event 0x87 sub 0x32, id 26764 with swapped u16 halves (read 0xa2f36f28)'),
    ('50e', 0x495f0000, 0x5920f4, 'fx node id; table read gave entry 0x2104 (cmp byte [eax+4] faulted)'),
    ('50f', 0x04900000, 0x75eefe, 'state-chart parameter id 1112 with swapped u16 halves'),
    ('50h', 0x00652000, 0x5953f2, 'thrall anim event list: next record header 0020 6500 read as id'),
]


def rule(id_, entry, rec):
    """The plugin's decision. rec = 16 bytes of the record or None (unreadable). Returns (result, reason):
    result 'ok' (engine path), 'zero' (engine's own not-found: entry 0 or record still loading), 'reject' (guard)."""
    if id_ >= COUNT:
        return 'reject', 'id out of the table (>= 0x%x)' % COUNT
    if entry == 0:
        return 'zero', 'entry 0'
    if entry < MIN_PTR or entry & ALIGN_MASK:
        return 'reject', 'entry 0x%08x not a record pointer' % entry
    if rec is None:
        return 'reject', 'record 0x%08x not readable' % entry
    refs, = struct.unpack_from('<H', rec, 0)
    loading, kind = rec[4], rec[5]
    if refs == 0 or loading > 1 or kind > 0x7f:
        return 'reject', 'record 0x%08x fields refs %d loading %d type %d' % (entry, refs, loading, kind)
    if loading:
        return 'zero', 'record still loading'
    return 'ok', ''


# ---- callers ----

SUBREGS = {'al': 'eax', 'ah': 'eax', 'ax': 'eax', 'cl': 'ecx', 'ch': 'ecx', 'cx': 'ecx', 'dl': 'edx', 'dh': 'edx',
           'dx': 'edx', 'bl': 'ebx', 'bh': 'ebx', 'bx': 'ebx', 'si': 'esi', 'di': 'edi', 'bp': 'ebp'}
X86 = capstone.x86


def walk(md, exe, secs, pc, aliases, slot=None, depth=0):
    """Follow straight-line code from pc. aliases: {register: offset from the lookup result}; slot: in a callee, the
    stack offset (from esp at the callee's entry) that holds the result. Returns (class, detail).
    TESTS = compared with 0 + je / jne before any memory access through it; DEREF = memory access first; RET = returned
    to the caller; PASS = stored somewhere we do not follow; UNKNOWN = no decision."""
    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        return -1
    aliases = dict(aliases)
    delta = 0                  # bytes pushed since the start (esp tracking; None = unknown)
    ebp_delta = None           # delta when ebp = esp was set
    pushed_at = None           # number of pushes since the result was pushed (argument index at the next call)
    stored = []
    jumps = 0
    test = None
    for _ in range(80):
        o = off(pc)
        if o < 0: return 'UNKNOWN', 'outside the image at 0x%08x' % pc
        ins = next(md.disasm(exe[o:o + 16], pc), None)
        if ins is None: return 'UNKNOWN', 'undecodable at 0x%08x' % pc
        m, ops = ins.mnemonic, ins.op_str
        opnds = list(ins.operands)
        if test is not None:
            if m in ('je', 'jne'):
                what = '%s at 0x%08x, %s 0x%08x' % (test[0], test[1], m, opnds[0].imm)
                # the branch taken for 0 must not dereference it either (e.g. 0x5d6448 reads [edi+10h] on both paths)
                zero_pc = opnds[0].imm if m == 'je' else ins.address + ins.size
                if depth >= 4: return 'TESTS', what + ' (0 path not followed)'
                zcls, zdet = walk(md, exe, secs, zero_pc, aliases if test[2] else {}, None, depth + 1)
                if zcls == 'DEREF': return 'ZDEREF', what + '; but the 0 path dereferences: ' + zdet
                if zcls == 'RET': return 'ZRET', what + '; the 0 path returns it: ' + zdet
                return 'TESTS', what + '; 0 path: ' + zcls.lower() + ' (' + zdet + ')'
            # the compiler may schedule flag-neutral moves between the compare and the branch
            if m not in ('mov', 'lea', 'push', 'movzx', 'movsx', 'fld', 'fstp', 'fild'):
                test = None
        # memory operands: through an alias = dereference; the result's stack slot = a load / compare
        for op in opnds:
            if op.type != X86.X86_OP_MEM: continue
            base = ins.reg_name(op.mem.base) if op.mem.base else None
            index = ins.reg_name(op.mem.index) if op.mem.index else None
            if m != 'lea' and ((base in aliases) or (index in aliases)):
                return 'DEREF', '0x%08x %s %s' % (ins.address, m, ops)
        def slot_of(op):
            """the operand is the result's stack slot"""
            if slot is None or op.type != X86.X86_OP_MEM or op.mem.index: return False
            base = ins.reg_name(op.mem.base) if op.mem.base else None
            if base == 'esp' and delta is not None: return op.mem.disp - delta == slot
            if base == 'ebp' and ebp_delta is not None: return op.mem.disp + ebp_delta == slot
            return False
        d = opnds[0] if opnds else None
        s = opnds[1] if len(opnds) > 1 else None
        dreg = ins.reg_name(d.reg) if d is not None and d.type == X86.X86_OP_REG else None
        sreg = ins.reg_name(s.reg) if s is not None and s.type == X86.X86_OP_REG else None
        if m == 'test' and dreg and dreg == sreg and aliases.get(dreg) == 0:
            test = (dreg, ins.address, True)
        elif m == 'cmp' and dreg in aliases and aliases[dreg] == 0 and (
                (s.type == X86.X86_OP_IMM and s.imm == 0) or sreg):
            test = ("cmp %s" % ops, ins.address, True)
        elif m == 'cmp' and d is not None and slot_of(d) and s.type == X86.X86_OP_IMM and s.imm == 0:
            test = ("cmp %s (argument)" % ops, ins.address, False)
        elif m == 'mov' and dreg:
            if sreg in aliases: aliases[dreg] = aliases[sreg]
            elif s is not None and slot_of(s): aliases[dreg] = 0
            else:
                aliases.pop(dreg, None)
                if dreg == 'ebp' and sreg == 'esp': ebp_delta = delta
        elif m == 'mov' and d is not None and d.type == X86.X86_OP_MEM and sreg in aliases:
            stored.append('0x%08x mov %s' % (ins.address, ops))
            if d.mem.base and ins.reg_name(d.mem.base) == 'esp' and not d.mem.index and delta is not None:
                pushed_at = ('esp', d.mem.disp - delta)     # slot relative to esp at delta 0
        elif m == 'push':
            if delta is not None: delta += 4
            if pushed_at is not None and pushed_at[0] == 'push': pushed_at = ('push', pushed_at[1] + 1)
            if dreg in aliases and aliases[dreg] == 0:
                stored.append('0x%08x push %s' % (ins.address, ops))
                pushed_at = ('push', 0)
        elif m == 'pop':
            if delta is not None: delta -= 4
            if dreg: aliases.pop(dreg, None)
        elif m in ('add', 'sub') and dreg == 'esp':
            if delta is not None and s.type == X86.X86_OP_IMM: delta += -s.imm if m == 'add' else s.imm
            else: delta = None
        elif m == 'and' and dreg == 'esp':
            delta = None
        elif m in ('add', 'sub') and dreg in aliases and s.type == X86.X86_OP_IMM:
            aliases[dreg] += s.imm if m == 'add' else -s.imm
        elif m == 'lea' and dreg:
            base = ins.reg_name(s.mem.base) if s.mem.base else None
            if base in aliases and not s.mem.index: aliases[dreg] = aliases[base] + s.mem.disp
            else: aliases.pop(dreg, None)
        elif m == 'call':
            target = opnds[0].imm if opnds[0].type == X86.X86_OP_IMM else None
            if pushed_at is not None and pushed_at[0] == 'push' and target and depth < 2:
                cls, det = walk(md, exe, secs, target, {}, 4 + 4 * pushed_at[1], depth + 1)
                return cls, 'argument %d of call 0x%08x: %s' % (pushed_at[1], target, det)
            if aliases.get('ecx') == 0 and target and depth < 2:
                cls, det = walk(md, exe, secs, target, {'ecx': 0}, None, depth + 1)
                return cls, 'this of call 0x%08x: %s' % (target, det)
            for r in ('eax', 'ecx', 'edx'): aliases.pop(r, None)
            if stored and not aliases and slot is None: return 'PASS', '; '.join(stored) + ' -> call ' + ops
            if not aliases and slot is None: return 'UNKNOWN', 'result dropped before call at 0x%08x' % ins.address
            if slot is not None and not aliases and delta is None:
                return 'UNKNOWN', 'callee: stack not tracked at call 0x%08x' % ins.address
        elif m == 'jmp':
            if opnds[0].type == X86.X86_OP_IMM and jumps < 3:
                target = opnds[0].imm
                if pushed_at is not None and pushed_at[0] == 'esp' and depth < 2 and delta is not None:
                    at = pushed_at[1] + delta
                    cls, det = walk(md, exe, secs, target, {}, at, depth + 1)
                    return cls, 'tail jmp 0x%08x with the result at [esp+%d]: %s' % (target, at, det)
                jumps += 1
                pc = target
                continue
            return 'UNKNOWN', 'indirect jmp at 0x%08x' % ins.address
        elif m in ('ret', 'retn'):
            if aliases.get('eax') == 0: return 'RET', 'returned at 0x%08x' % ins.address
            if stored: return 'PASS', '; '.join(stored)
            return 'UNKNOWN', 'ret at 0x%08x without testing it' % ins.address
        elif dreg:
            aliases.pop(dreg, None)
            if dreg in SUBREGS: aliases.pop(SUBREGS[dreg], None)
        if not aliases and slot is None:
            if stored: return 'PASS', '; '.join(stored)
            return 'UNKNOWN', 'result overwritten at 0x%08x %s %s' % (ins.address, m, ops)
        pc = ins.address + ins.size
    return 'UNKNOWN', 'no decision in 80 instructions'


def classify(md, exe, secs, site):
    """Follow the code after the `call` at site."""
    return walk(md, exe, secs, site + 5, {'eax': 0})


def cmd_callers(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    sites = []
    for name, va, rptr, size, chars in secs:
        if not chars & 0x20000000: continue
        blob = exe[rptr:rptr + size]
        for i in range(1, len(blob) - 4):
            if blob[i - 1] not in (0xe8, 0xe9): continue
            t = (va + i + 4 + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff
            if t in (LOOKUP, EXISTS):
                at = va + i - 1
                ins = next(md.disasm(blob[i - 1:i + 4], at), None)
                if ins is None or ins.mnemonic not in ('call', 'jmp'): continue
                sites.append((at, ins.mnemonic, t))
    counts = {}
    print('# callers of 0x%08x (section lookup) and 0x%08x (exists test); return address = site + 5' % (LOOKUP, EXISTS))
    for at, kind, t in sites:
        if kind == 'jmp':
            cls, detail = 'RET', 'tail jmp (result goes to the caller of the function)'
        elif t == EXISTS:
            cls, detail = classify(md, exe, secs, at)
        else:
            cls, detail = classify(md, exe, secs, at)
        counts[(t, cls)] = counts.get((t, cls), 0) + 1
        print('0x%08x %-4s 0x%08x ret 0x%08x %-7s %s' % (at, kind, t, at + 5, cls, detail))
    print('# summary')
    for (t, cls), n in sorted(counts.items()):
        print('#   0x%08x %-7s %d' % (t, cls, n))
    print('#   total %d sites' % len(sites))


# ---- dumps ----

def memory_info(m):
    """Committed regions from the MemoryInfoList stream: list of (base, size, protect)."""
    out = []
    if 16 not in m.streams: return out
    _, r = m.streams[16]
    hsize, esize, n = struct.unpack_from('<IIQ', m.d, r)
    for k in range(n):
        e = r + hsize + esize * k
        base, abase, aprot, _, size, state, prot, typ = struct.unpack_from('<QQIIQIII', m.d, e)
        if state == 0x1000: out.append((base, size, prot, typ))
    return out


def cmd_table(argv):
    import minidump_read as MD
    bad = 0
    for path in argv:
        print('== %s' % path)
        m = MD.Minidump(path)
        raw = m.read(TABLE, COUNT * 4)
        if raw is None:
            print('   table 0x%08x not in the dump' % TABLE); bad += 1; continue
        entries = struct.unpack('<%dI' % COUNT, raw)
        regions = memory_info(m)
        stats = {'ok': 0, 'zero': 0, 'reject': 0}
        lo, hi, aligns, kinds, loadings, refmax = 0xffffffff, 0, {}, {}, {}, 0
        for id_, e in enumerate(entries):
            rec = m.read(e, 16) if e else None
            res, why = rule(id_, e, rec)
            if e and res == 'reject':
                bad += 1
                print('   GOOD ENTRY REJECTED id 0x%04x entry 0x%08x: %s' % (id_, e, why))
            stats[res] += 1
            if e:
                lo, hi = min(lo, e), max(hi, e)
                a = (e & -e) if e else 0
                aligns[min(a, 0x40)] = aligns.get(min(a, 0x40), 0) + 1
                if rec:
                    kinds[rec[5]] = kinds.get(rec[5], 0) + 1
                    loadings[rec[4]] = loadings.get(rec[4], 0) + 1
                    refmax = max(refmax, struct.unpack_from('<H', rec, 0)[0])
        nz = COUNT - entries.count(0)
        print('   entries: %d non-zero of 0x%x; table[0] 0x%08x; range 0x%08x..0x%08x' % (nz, COUNT, entries[0], lo, hi))
        print('   rule: ok %d, engine not-found %d (entry 0 / loading), rejected %d' % (stats['ok'], stats['zero'],
                                                                                        stats['reject']))
        print('   pointer alignment (lowest set bit, capped 0x40): %s' % ', '.join(
            '0x%x x%d' % kv for kv in sorted(aligns.items())))
        print('   +4 loading byte: %s; +5 type byte: %s; max refcount %d' % (
            dict(sorted(loadings.items())), dict(sorted(kinds.items())), refmax))
        print('   word before the table [0x%08x] = %s, after [0x%08x] = %s' % (
            TABLE - 4, '0x%08x' % m.u32(TABLE - 4) if m.u32(TABLE - 4) is not None else 'n/a', TABLE + COUNT * 4,
            '0x%08x' % m.u32(TABLE + COUNT * 4) if m.u32(TABLE + COUNT * 4) is not None else 'n/a'))
        if regions:
            inside = sum(1 for e in entries if e and any(b <= e < b + s for b, s, _, _ in regions))
            print('   non-zero entries inside committed memory: %d of %d' % (inside, nz))
        if m.exception:
            r = m.regs(m.exception['ctx'])
            if r['eip'] in (0x54df84, 0x54df8f, 0x54df74):
                sp = r['esp']
                ret, arg = m.u32(sp), m.u32(sp + 4)     # the lookup pushes nothing: [esp] return, [esp+4] id
                e = None
                if arg is not None and arg < COUNT: e = entries[arg]
                res, why = rule(arg, e if e is not None else 0xffffffff, None)
                print('   dump exception at 0x%08x: id 0x%08x, return 0x%08x -> rule: %s (%s)' % (
                    r['eip'], arg, ret, res, why))
                if res != 'reject': bad += 1
        bad += replay(entries)
    return bad


def replay(entries=None):
    bad = 0
    print('   recorded bad ids:')
    for run, id_, ret, note in BAD_IDS:
        e = entries[id_] if entries is not None and id_ < COUNT else None
        res, why = rule(id_, e if e is not None else 0, None)
        flag = 'ok' if res == 'reject' else 'NOT REJECTED'
        if res != 'reject': bad += 1
        print('     %-4s id 0x%08x caller ret 0x%08x -> %s, %s [%s] (%s)' % (run, id_, ret, res, why, flag, note))
    # the swapped-halves partner of each recorded id is a good id (when it is in range) - must stay in range
    for run, id_, ret, note in BAD_IDS:
        swapped = ((id_ & 0xffff) << 16) | (id_ >> 16)
        if swapped < COUNT:
            e = entries[swapped] if entries is not None else None
            info = 'entry 0x%08x' % e if e is not None else 'no dump'
            print('     %-4s swapped halves 0x%04x (the intended id) in range, %s' % (run, swapped, info))
    return bad


def guarded_sites(exe, secs):
    """return addresses of the TESTS callers of the lookup (the plugin's kGuardedCallers)"""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    out = []
    for name, va, rptr, size, chars in secs:
        if not chars & 0x20000000: continue
        blob = exe[rptr:rptr + size]
        for i in range(1, len(blob) - 4):
            if blob[i - 1] != 0xe8: continue
            if (va + i + 4 + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff != LOOKUP: continue
            at = va + i - 1
            ins = next(md.disasm(blob[i - 1:i + 4], at), None)
            if ins is None or ins.mnemonic != 'call': continue
            if classify(md, exe, secs, at)[0] == 'TESTS': out.append(at + 5)
    return sorted(out)


def cmd_prechecks(argv):
    """prechecks EXE CPP OUT: the plugin's byte checks as a pe_bytes_check.py list; CPP's kGuardedCallers must equal
    the TESTS callers found now"""
    import re
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    src = open(argv[1], encoding='ascii').read()
    block = re.search(r'kGuardedCallers\[\] = \{(.*?)\};', src, re.S).group(1)
    cpp = [int(x, 16) for x in re.findall(r'0x[0-9a-f]{8}', block)]
    found = guarded_sites(exe, secs)
    same = cpp == found
    print('kGuardedCallers in %s: %d entries; TESTS callers now: %d; identical: %s' % (argv[1], len(cpp), len(found),
                                                                                    same))
    if not same:
        print('  only in the source: %s' % ', '.join('0x%08x' % a for a in sorted(set(cpp) - set(found))))
        print('  only found now:     %s' % ', '.join('0x%08x' % a for a in sorted(set(found) - set(cpp))))
    hexes = dict(re.findall(r'const char \*const (k\w+Hex) = "([0-9a-f ]+)"', src))
    lines = ['# TruDataGuard 0.1 byte checks (generated by tools/dataguard_check.py prechecks from TruDataGuard.cpp)',
             '0054df80 ' + hexes['kLookupHex'], '0054df70 ' + hexes['kExistsHex'], '0054dd10 ' + hexes['kRegisterHex'],
             '005c1b50 ' + hexes['kUnitLookupHex'], '005c1c4e ' + hexes['kUnitStoreHex'],
             '005c1c28 ' + hexes['kUnitNameHex'],
             '# exists caller: call 0x54df70; add esp,4; test al,al; jne',
             '0052cd85 e8%s 83c404 84c0 7517' % struct.pack('<I', (EXISTS - 0x52cd8a) & 0xffffffff).hex(),
             '# guarded callers: E8 call to 0x54df80 right before each return address']
    for r in cpp:
        lines.append('%08x e8%s' % (r - 5, struct.pack('<I', (LOOKUP - r) & 0xffffffff).hex()))
    open(argv[2], 'w', encoding='ascii', newline='\n').write('\n'.join(lines) + '\n')
    print('wrote %s (%d checks)' % (argv[2], sum(1 for l in lines if not l.startswith('#'))))
    return 0 if same else 1


def main(argv):
    if not argv:
        print(__doc__); return 2
    if argv[0] == 'callers': cmd_callers(argv[1:]); return 0
    if argv[0] == 'prechecks': return cmd_prechecks(argv[1:])
    if argv[0] == 'table': return 1 if cmd_table(argv[1:]) else 0
    if argv[0] == 'replay':
        print('== replay without a dump'); return 1 if replay() else 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
