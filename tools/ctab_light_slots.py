"""List the D3DX constant tables (CTAB) of shaders embedded in a raw memory image or shader file and print the
light-related constants with their register set, register count and array size (read-only; N7 2026-11-09, throne
flicker: how many lights does one Xbox draw take - LightEnabled[N], p_Lights[N], TooManyLights).

A CTAB header is {u32 Size = 0x1c, u32 Creator, u32 Version, u32 Constants, u32 ConstantInfo, u32 Flags, u32 Target},
offsets relative to the header; a constant info is {u32 Name, u16 RegisterSet, u16 RegisterIndex, u16 RegisterCount,
u16 Reserved, u32 TypeInfo, u32 DefaultValue}; a type info is {u16 Class, u16 Type, u16 Rows, u16 Columns,
u16 Elements, u16 StructMembers, u32 StructMemberInfo}. Register sets: 0 bool, 1 int4, 2 float4, 3 sampler.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ctab_light_slots.py FILE be|le [NAME_REGEX]
    default NAME_REGEX: (?i)light|shadow
    prints one line per matching constant: table offset, name, set, register index / count, class / type, rows x
    cols, elements, struct members; last line: tables found, matching constants, histogram of the element counts
    per name.
"""
import sys, re, struct, collections

SETS = {0: 'bool', 1: 'int4', 2: 'float4', 3: 'sampler'}


def cstr(d, o, lim=64):
    e = d.find(b'\0', o, o + lim)
    if e < 0:
        return None
    s = d[o:e]
    if not s or any(c < 0x20 or c > 0x7e for c in s):
        return None
    return s.decode('ascii')


def tables(d, f):
    """yield (offset, constants list) for every plausible CTAB header"""
    pat = struct.pack(f + 'I', 0x1c)
    i = d.find(pat)
    while i >= 0:
        if i + 0x1c <= len(d):
            size, creator, version, n, info, flags, target = struct.unpack_from(f + '7I', d, i)
            ok = (0 < n < 512 and info == 0x1c and creator < 0x10000 and target < 0x10000
                  and i + info + 20 * n <= len(d))
            if ok:
                cr = cstr(d, i + creator) if creator else ''
                tg = cstr(d, i + target, 16) if target else None
                if cr is not None and tg and (tg.startswith('vs_') or tg.startswith('ps_')):
                    consts = []
                    good = True
                    for k in range(n):
                        nm, rs, ri, rc, _, ti, dv = struct.unpack_from(f + 'I4H2I', d, i + info + 20 * k)
                        name = cstr(d, i + nm)
                        if name is None or i + ti + 16 > len(d):
                            good = False
                            break
                        cl, ty, rows, cols, el, sm, smi = struct.unpack_from(f + '6HI', d, i + ti)
                        consts.append((name, rs, ri, rc, cl, ty, rows, cols, el, sm))
                    if good:
                        yield i, tg, consts
        i = d.find(pat, i + 4)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    d = open(argv[0], 'rb').read()
    f = '>' if argv[1] == 'be' else '<'
    rx = re.compile(argv[2] if len(argv) > 2 else r'(?i)light|shadow')
    nt = nm = 0
    hist = collections.defaultdict(collections.Counter)
    for off, tg, consts in tables(d, f):
        nt += 1
        for name, rs, ri, rc, cl, ty, rows, cols, el, sm in consts:
            if not rx.search(name):
                continue
            nm += 1
            hist[name][el] += 1
            print('0x%08x %-7s %-26s %-7s r%-3d n%-3d class %d type %d %dx%d elements %d members %d' % (
                off, tg, name, SETS.get(rs, rs), ri, rc, cl, ty, rows, cols, el, sm))
    print('tables %d, matching constants %d' % (nt, nm))
    for name in sorted(hist):
        print('  %-26s elements: %s' % (name, ', '.join('%d x%d' % (e, c) for e, c in sorted(hist[name].items()))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
