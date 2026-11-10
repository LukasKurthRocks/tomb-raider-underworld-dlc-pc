"""Dump the game option table of tru.exe (8-byte entries {float value, callback}) with what every callback writes,
and every direct setter / getter call site per option index (read-only; game settings study 2026-11-10).

Option table 0x8ab538 (158 entries, 0..0x9d), setter 0x5d5100 cdecl (index, float, bool run callback), getter
0x5d5140 cdecl (index) -> st0. For each entry: index, initial float in the image, callback (or '-' for the empty
function NOP), and a summary of the callback up to its first ret: profile fields written through [0xc59264] /
[0xc59268] (`P+off`), absolute globals written, and direct calls. Call sites: the last `push imm` before a call of
the setter / getter is the index (a register index shows as '?').

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_option_table.py EXE [TABLE_VA COUNT SETTER GETTER NOP]
      defaults 0x8ab538 158 0x5d5100 0x5d5140 0x6457a0
  ../bin/pyt -t 300 tools/pe_option_table.py EXE --natives BINDER [REGISTER]
      script natives of a binder that set / get an option (uigamedata: binder 0x7af0c0, register 0x5768f0)
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

PROFILE = (0xc59264, 0xc59268)


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def callback_summary(md, exe, secs, va):
    o = off_of(secs, va)
    if o < 0: return 'not in image'
    prof_regs = set()
    writes, calls = [], []
    for ins in md.disasm(exe[o:o + 0x180], va):
        ops = ins.op_str
        if ins.mnemonic == 'mov' and any(('[0x%x]' % p) in ops for p in PROFILE) and ops.split(',')[0].strip() in (
                'eax', 'ecx', 'edx', 'esi', 'edi', 'ebx'):
            prof_regs.add(ops.split(',')[0].strip())
        dst = ops.split(',')[0].strip()
        if ins.mnemonic in ('mov', 'fstp', 'fst', 'or', 'and', 'inc', 'dec', 'add', 'sub') and '[' in dst:
            inner = dst[dst.index('[') + 1:dst.index(']')]
            parts = [x.strip() for x in inner.split('+')]
            if len(parts) == 2 and parts[0] in prof_regs:
                writes.append('P+%s' % parts[1])
            elif len(parts) == 1 and parts[0].startswith('0x'):
                writes.append('[%s]' % parts[0])
        if ins.mnemonic == 'call':
            calls.append(ops)
        if ins.mnemonic in ('ret', 'jmp') and ins.mnemonic == 'ret':
            break
    seen = []
    for w in writes:
        if w not in seen: seen.append(w)
    return 'writes %s; calls %s' % (' '.join(seen) or '-', ' '.join(calls) or '-')


def call_sites(md, exe, secs, target):
    out = {}
    for name, sva, rptr, size, chars in secs:
        if not chars & 0x20000000: continue
        blob = exe[rptr:rptr + size]
        for i in range(len(blob) - 5):
            if blob[i] != 0xe8: continue
            t = (sva + i + 5 + struct.unpack_from('<i', blob, i + 1)[0]) & 0xffffffff
            if t != target: continue
            site = sva + i
            idx = '?'
            # decode backwards: try start offsets so that the call is decoded as an instruction
            for back in range(24, 0, -1):
                insns = list(md.disasm(blob[i - back:i + 5], site - back))
                if insns and insns[-1].address == site and insns[-1].mnemonic == 'call':
                    for ins in reversed(insns[:-1]):
                        if ins.mnemonic == 'push':
                            idx = ins.op_str if ins.op_str.startswith('0x') or ins.op_str.isdigit() else '?'
                            break
                    break
            try: k = int(idx, 0)
            except ValueError: k = '?'
            out.setdefault(k, []).append(site)
    return out


def opt_uses(md, exe, secs, va, setter, getter, depth=0):
    """Option indices that the function at va sets / gets (directly or one call deep)."""
    o = off_of(secs, va)
    out, last_push = [], None
    for ins in md.disasm(exe[o:o + 0x60], va):
        if ins.mnemonic == 'push':
            last_push = ins.op_str
        if ins.mnemonic == 'call' and ins.op_str.startswith('0x'):
            t = int(ins.op_str, 16)
            if t in (setter, getter):
                out.append('%s %s' % ('set' if t == setter else 'get', last_push))
            elif depth == 0:
                out += opt_uses(md, exe, secs, t, setter, getter, 1)
        if ins.mnemonic == 'ret':
            break
    return out


def natives(md, exe, secs, binder, register, setter, getter):
    """Walk a script binder (push thunk; push slot; call register) and name the option index behind each slot."""
    o = off_of(secs, binder)
    pushes = []
    for ins in md.disasm(exe[o:o + 0x1000], binder):
        if ins.mnemonic == 'push':
            pushes.append(ins.op_str)
        elif ins.mnemonic == 'call' and ins.op_str == '0x%x' % register and len(pushes) >= 2:
            slot, thunk = int(pushes[-1], 16), int(pushes[-2], 16)
            uses = opt_uses(md, exe, secs, thunk, setter, getter)
            if uses: print('native f%-3d (0x%02x) thunk 0x%06x  %s' % (slot, slot, thunk, ', '.join(uses)))
            pushes = []
        elif ins.mnemonic == 'ret':
            break


def main(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    if argv[1] == '--natives':
        # --natives BINDER [REGISTER]: uigamedata binder 0x7af0c0, register 0x5768f0
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        natives(md, exe, secs, int(argv[2], 16), int(argv[3], 16) if len(argv) > 3 else 0x5768f0, 0x5d5100, 0x5d5140)
        return
    table =int(argv[1], 16) if len(argv) > 1 else 0x8ab538
    count = int(argv[2], 0) if len(argv) > 2 else 158
    setter = int(argv[3], 16) if len(argv) > 3 else 0x5d5100
    getter = int(argv[4], 16) if len(argv) > 4 else 0x5d5140
    nop = int(argv[5], 16) if len(argv) > 5 else 0x6457a0
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print('NOP 0x%x first byte 0x%02x (0xc3 = ret)' % (nop, exe[off_of(secs, nop)]))
    sets = call_sites(md, exe, secs, setter)
    gets = call_sites(md, exe, secs, getter)
    o = off_of(secs, table)
    for k in range(count):
        val, cb = struct.unpack_from('<fI', exe, o + 8 * k)
        line = '0x%02x %3d  value %-10g  ' % (k, k, val)
        if cb == nop:
            line += 'cb -'
        else:
            line += 'cb 0x%06x  %s' % (cb, callback_summary(md, exe, secs, cb))
        s = ' '.join('0x%x' % a for a in sets.get(k, []))
        g = ' '.join('0x%x' % a for a in gets.get(k, []))
        print(line)
        if s: print('        set at %s' % s)
        if g: print('        get at %s' % g)
    if '?' in sets: print('setter, index in a register: %s' % ' '.join('0x%x' % a for a in sets['?']))
    if '?' in gets: print('getter, index in a register: %s' % ' '.join('0x%x' % a for a in gets['?']))


if __name__ == '__main__':
    main(sys.argv[1:])
