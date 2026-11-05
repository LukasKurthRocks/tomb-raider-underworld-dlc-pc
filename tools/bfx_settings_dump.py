"""List the NavPower (BabelFlux "bfx") debug settings compiled into a 32-bit PE such as tru.exe, with the byte each
setting switches and the code that reads that byte (read-only; debug view research 2026-11-05, workspace
docs\\Befund-Debug-Ansicht-0511.md).

Engine facts this tool relies on (Steam tru.exe, tools/pe_dis.py 2026-11-05):
  * the bfx Setting constructor tru+0x28030 (0x428030): `mov eax, ecx; mov ecx, [0x8c0f58]; mov [eax], 0x84299c;
    mov [eax+4], ecx; mov [eax+8], 0; mov [0x8c0f58], eax` = a linked list of every setting (head 0x8c0f58, next +4);
  * each static initialiser then writes `[obj] = vtable` (0x841144 = BoolSetting), `[obj+0xc] = name`,
    `[obj+0x10] = pointer to the variable`, `[obj+0x14] = al` (the default, read from the variable before);
  * a few settings are static objects in .data (vtable dword in the file, e.g. 0x88f03c "timings").
For every setting: object, vtable, name, variable, its initial byte in the file and the instructions that use the
variable (linear capstone sweep of the executable sections, memory operand or immediate equal to the address).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/bfx_settings_dump.py EXE [--ctor 0x428030] [--uses N]
     --uses N   print at most N use sites per variable (default 6)
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    ctor = int(opt(argv, '--ctor', '0x428030'), 16)
    nuse = int(opt(argv, '--uses', '6'))
    if not argv:
        print(__doc__)
        return 2
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)

    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        return None

    def cstr(va):
        o = off(va)
        if o is None: return None
        z = exe.find(b'\0', o, o + 200)
        if z < 0: return None
        s = exe[o:z]
        return s.decode('latin-1') if s and all(32 <= c < 127 for c in s) else None

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    settings = {}
    # 1. static initialisers: b9 OBJ / e8 -> ctor, then the stores
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        blob = exe[rptr:rptr + size]
        i = blob.find(b'\xb9')
        while i >= 0 and i + 10 <= len(blob):
            if blob[i + 5] == 0xe8:
                tgt = sva + i + 10 + struct.unpack_from('<i', blob, i + 6)[0]
                if tgt == ctor:
                    obj = struct.unpack_from('<I', blob, i + 1)[0]
                    rec = settings.setdefault(obj, {'init': sva + i})
                    for ins in md.disasm(blob[i + 10:i + 90], sva + i + 10):
                        if ins.mnemonic in ('ret', 'call') and ins.address > sva + i + 10 + 2: break
                        if ins.mnemonic != 'mov' or len(ins.operands) != 2: continue
                        a, b = ins.operands
                        if a.type == capstone.x86.X86_OP_MEM and a.mem.base == 0 and a.mem.index == 0 \
                                and b.type == capstone.x86.X86_OP_IMM:
                            k = a.mem.disp - obj
                            if 0 <= k < 0x30: rec[k] = b.imm & 0xffffffff
            i = blob.find(b'\xb9', i + 1)
    vtables = {r.get(0) for r in settings.values() if r.get(0)}
    # 2. static objects in data sections: vtable dword + name pointer at +0xc
    for name, sva, rptr, size, ch in secs:
        if ch & 0x20000000: continue
        for o in range(0, size - 0x18, 4):
            v = struct.unpack_from('<I', exe, rptr + o)[0]
            if v in vtables:
                nm = struct.unpack_from('<I', exe, rptr + o + 0xc)[0]
                if cstr(nm):
                    obj = sva + o
                    if obj not in settings:
                        settings[obj] = {'init': None, 0: v, 0xc: nm,
                                         0x10: struct.unpack_from('<I', exe, rptr + o + 0x10)[0],
                                         0x14: struct.unpack_from('<I', exe, rptr + o + 0x14)[0]}
    vars_ = {r[0x10] for r in settings.values() if r.get(0x10)}
    uses = {v: [] for v in vars_}
    keys = {'0x%x' % v: v for v in vars_}
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        md2 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md2.skipdata = True
        for ins in md2.disasm(exe[rptr:rptr + size], sva):
            s = ins.op_str
            if '0x8' not in s: continue
            for k, v in keys.items():
                if k in s and (s.find(k + ']') >= 0 or s.endswith(k) or (k + ',') in s):
                    uses[v].append('0x%08x %s %s' % (ins.address, ins.mnemonic, s))
    print('NavPower settings: %d (vtables %s); list head 0x8c0f58' % (len(settings), ', '.join('0x%x' % v for v in sorted(vtables))))
    print('%-10s %-10s %-10s %-30s %-10s %-4s %-6s %s' % ('object', 'init', 'vtable', 'name', 'variable', 'file', 'uses', 'first uses'))
    for obj in sorted(settings, key=lambda o: settings[o].get(0x10) or 0):
        r = settings[obj]
        var = r.get(0x10)
        o = off(var) if var else None
        init = exe[o] if o is not None and o < len(exe) else None
        u = uses.get(var, [])
        not_ctor = [x for x in u if not (r['init'] and r['init'] <= int(x.split()[0], 16) < r['init'] + 0x60)]
        print('0x%08x %-10s 0x%08x %-30s %-10s %-4s %-6d %s' % (
            obj, ('0x%x' % r['init']) if r['init'] else 'data', r.get(0, 0), cstr(r.get(0xc, 0)) or '?',
            ('0x%x' % var) if var else '-', ('%d' % init) if init is not None else '-', len(not_ctor),
            ' | '.join(not_ctor[:nuse])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
