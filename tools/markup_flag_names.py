"""Markup type -> MUD flag bit -> flag name, from the 2007 prototype and the PC exe (read-only; 2026-11-06 markup /
scale, docs/Befund-Markup-Massstab-0611.md).

Three sources, printed side by side so a type name is only claimed where the bytes agree:
  * PC tru.exe: TRMarkupManager vtable 0x855214 slot +0x1c = 0x5d6f90 (type -> flag bit, jump table 0x5d704c,
    types 0..20) and slot +0x20 = 0x5d70a0 (type -> class word, table 0x5d70d0, types 1..21).
  * Prototype tr8_Content.pe (2007-08-16, linker map work/proto2007/map/tr8_Content.map):
    MarkupManager::GetMUDFlag 0x8211e318 (no .pdata entry, decoded here by a small register tracker),
    MarkupManager::GetAdditionalMUDFlags 0x8211e438, nFlagNames 0x82843fcc and MUD_Flagnames 0x82843fd0 (char*[],
    used by DEBUG_MarkupType 0x8226ad70: entry i names flag bit (31 - i); GetDebugFlagnameArrayIndex 0x8252cec8
    replaces the index for bit 0x08000000 by 6 (hpole) / 4 (wall vpole) / 5 (vpole)).
Nothing is written; only names, addresses and numbers are printed.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/markup_flag_names.py [EXE]
      EXE default: ../data/pc/tru.exe (the workspace copy of the Steam exe, md5 5560abac...)
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

EXE = '../data/pc/tru.exe'
PROTO = 'work/proto2007/pe/content/tr8_Content.pe'
PBASE = 0x82000000


def pc_reader(path):
    exe = open(path, 'rb').read()
    _, secs = PE.sections(exe)

    def dw(va):
        for _, sva, rptr, size, _c in secs:
            if sva <= va < sva + size:
                return struct.unpack_from('<I', exe, rptr + va - sva)[0]
        raise ValueError('VA 0x%x not in image' % va)
    return exe, secs, dw


def pc_flag_of(dw, exe, secs, t):
    """value returned by 0x5d6f90 for type t (jump table 0x5d704c, cases 'mov eax,imm32; ret 4')"""
    if t > 0x14:
        return 0
    tgt = dw(0x5d704c + 4 * t)
    for _, sva, rptr, size, _c in secs:
        if sva <= tgt < sva + size:
            o = rptr + tgt - sva
            if exe[o] == 0xb8:
                return struct.unpack_from('<I', exe, o + 1)[0]
            if exe[o:o + 2] == b'\x33\xc0':
                return 0
    return None


def pc_class_of(dw, exe, secs, t):
    """value returned by 0x5d70a0 for type t (eax = 0 before the jump; table 0x5d70d0 for t-1 in 0..0x14)"""
    if not 1 <= t <= 0x15:
        return 0x80000000
    tgt = dw(0x5d70d0 + 4 * (t - 1))
    for _, sva, rptr, size, _c in secs:
        if sva <= tgt < sva + size:
            o = rptr + tgt - sva
            if exe[o] == 0xb8:
                return struct.unpack_from('<I', exe, o + 1)[0]
            if exe[o] == 0xc2:            # ret 4 with eax still 0
                return 0
    return None


def proto_cstr(d, va):
    o = va - PBASE
    if not 0 <= o < len(d):
        return None
    e = d.index(b'\0', o)
    return d[o:e].decode('latin-1')


def proto_case_value(d, md, start, limit=24, seed=None):
    """track li / lis / ori / addi / mr until blr; follow unconditional b; return r3"""
    regs = dict(seed or {})
    a = start
    for _ in range(limit):
        ins = next(md.disasm(d[a - PBASE:a - PBASE + 4], a), None)
        if ins is None:
            return None
        m, ops = ins.mnemonic, [x.strip() for x in ins.op_str.split(',')]
        try:
            if m == 'li':
                regs[ops[0]] = int(ops[1], 0) & 0xffffffff
            elif m == 'lis':
                regs[ops[0]] = (int(ops[1], 0) << 16) & 0xffffffff
            elif m == 'ori' and ops[1] in regs:
                regs[ops[0]] = regs[ops[1]] | int(ops[2], 0)
            elif m == 'addi' and ops[1] in regs:
                regs[ops[0]] = (regs[ops[1]] + int(ops[2], 0)) & 0xffffffff
            elif m == 'mr' and ops[1] in regs:
                regs[ops[0]] = regs[ops[1]]
            elif m == 'b':
                a = int(ops[0], 0); continue
            elif m == 'blr':
                return regs.get('r3')
        except ValueError:
            pass
        a += 4
    return None


def proto_switch(d, md, fstart, flen):
    """find 'lis r12,hi; addi r12,r12,lo; ... bctr' in the function and return (bound, table VA, entries)"""
    bound = tab = None
    hi = None
    for a in range(fstart, fstart + flen, 4):
        ins = next(md.disasm(d[a - PBASE:a - PBASE + 4], a), None)
        if ins is None:
            continue
        ops = [x.strip() for x in ins.op_str.split(',')]
        if ins.mnemonic == 'cmplwi' and bound is None:
            bound = int(ops[-1], 0)
        if ins.mnemonic == 'lis' and ops[0] == 'r12':
            hi = int(ops[1], 0)
        if ins.mnemonic == 'addi' and ops[0] == 'r12' and hi is not None:
            tab = ((hi << 16) + int(ops[2], 0)) & 0xffffffff
        if ins.mnemonic == 'bctr':
            break
    if bound is None or tab is None:
        return None
    ent = [struct.unpack_from('>I', d, tab - PBASE + 4 * i)[0] for i in range(bound + 1)]
    return bound, tab, ent


def main(argv):
    exe_path = argv[0] if argv else EXE
    exe, secs, dw = pc_reader(exe_path)
    print('PC %s' % exe_path)
    print('  vtable 0x855214: +0x1c -> 0x%08x, +0x20 -> 0x%08x' % (dw(0x855230), dw(0x855234)))
    d = open(PROTO, 'rb').read()
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    n_names = struct.unpack_from('>I', d, 0x82843fcc - PBASE)[0]
    names = []
    for i in range(46):
        p = struct.unpack_from('>I', d, 0x82843fd0 - PBASE + 4 * i)[0]
        names.append(proto_cstr(d, p) if p else None)
    print('prototype nFlagNames = %d; MUD_Flagnames (entry i = flag bit 31 - i):' % n_names)
    for i, nm in enumerate(names):
        if i < n_names or nm:
            print('  [%2d] bit %2d 0x%08x  %s' % (i, 31 - i if i < 32 else -1, (1 << (31 - i)) if i < 32 else 0, nm))
    sw = proto_switch(d, md, 0x8211e318, 288)
    proto_flag = {}
    if sw:
        bound, tab, ent = sw
        print('prototype GetMUDFlag 0x8211e318: cmplwi bound %d, jump table 0x%08x' % (bound, tab))
        for t, tgt in enumerate(ent):
            proto_flag[t] = proto_case_value(d, md, tgt)
    else:
        print('prototype GetMUDFlag: switch not found')
    sw2 = proto_switch(d, md, 0x8211e438, 236)
    proto_cls = {}
    if sw2:
        bound, tab, ent = sw2
        for t1, tgt in enumerate(ent):
            proto_cls[t1 + 1] = proto_case_value(d, md, tgt, seed={"r11": 0})  # li r11,0 before the switch

    def bitname(v):
        if not v:
            return '-'
        out = []
        for b in range(31, -1, -1):
            if v >> b & 1:
                i = 31 - b
                out.append(names[i] if i < len(names) and names[i] else 'bit%d' % b)
        return '|'.join(out)

    print()
    print('type | PC flag bit (0x5d6f90) | proto GetMUDFlag | same | PC class (0x5d70a0) | proto class | flag name (MUD_Flagnames)')
    for t in range(0, 24):
        pf = pc_flag_of(dw, exe, secs, t)
        pc = pc_class_of(dw, exe, secs, t)
        xf = proto_flag.get(t)
        xc = proto_cls.get(t, 0x80000000 if t > 21 or t == 0 else None)
        same = 'yes' if (pf == xf or (t > 20 and xf is None and pf == 0)) else 'NO'
        print('%4d | 0x%08x | %s | %s | 0x%08x | %s | %s' % (
            t, pf if pf is not None else 0xffffffff, ('0x%08x' % xf) if xf is not None else '-', same,
            pc if pc is not None else 0xffffffff, ('0x%08x' % xc) if xc is not None else '-', bitname(pf)))


if __name__ == '__main__':
    main(sys.argv[1:])
