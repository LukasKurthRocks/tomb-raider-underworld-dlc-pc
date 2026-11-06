"""List the named enemy states of tru.exe: the static registry that maps a state name string to its state singleton
(read-only; thrall state 2026-11-06: TruMenu labels want a readable state per thrall).

Engine facts (tru.exe Steam, md5 5560abacbc6968cdc17871c3ec8ca21c, static):
  * ENEMY_SwitchState-style helpers (e.g. 0x60ed80) pass a state NAME (e.g. 0x857d4c "Vaulted") to the state
    machine at brain+0x1254 (0x671df0 / 0x671d90), which looks the name up in a binary tree rooted at [0xecfb4c]
    (0x670750: node +0x00 name, +0x0c left, +0x10 right, +0x14 state object) and switches the layer to that object;
  * the nodes are static objects, each inserted by a tiny static initialiser `push NODE; call 0x6702d0; mov ecx,eax;
    call 0x6706b0`;
  * the state machine keeps the current state object of layer 0 / 1 at SM+0x08 / SM+0x0c (0x67108e, 0x671d58) and the
    pending one at SM+0x6a4 / +0x6a8 (0x671135), SM = brain+0x1254.
So: name = registry lookup of the pointer at [brain+0x125c] (layer 0) or [brain+0x1260] (layer 1).

The tool finds every initialiser by its byte pattern, reads the node, the state object, its vtable and the MSVC RTTI
class name of that vtable, and prints one line per state (sorted by state object address).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_enemy_state_names.py EXE [--registry-get 0x6702d0] [--insert 0x6706b0]
"""
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    get_fn, ins_fn = 0x6702d0, 0x6706b0
    if '--registry-get' in argv: k = argv.index('--registry-get'); get_fn = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--insert' in argv: k = argv.index('--insert'); ins_fn = int(argv[k + 1], 16); del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)

    def off(va):
        for _, sva, raw, size, _ in secs:
            if sva <= va < sva + size: return raw + va - sva
        return None

    def u32(va):
        o = off(va)
        return None if o is None else struct.unpack_from('<I', exe, o)[0]

    def cstr(va):
        o = off(va)
        if o is None: return None
        e = exe.find(b'\0', o, o + 128)
        return exe[o:e].decode('latin-1') if e > o else ''

    def rtti(vt):
        col = u32(vt - 4)
        if not col: return '?'
        td = u32(col + 0xc)
        if not td: return '?'
        n = cstr(td + 8)
        return n or '?'

    rows = []
    for name, va, raw, size, chars in secs:
        if not chars & 0x20000000: continue
        code = exe[raw:raw + size]
        for m in re.finditer(rb'\x68(....)\xe8(....)\x8b\xc8\xe8(....)', code, re.S):
            a = va + m.start()
            node = struct.unpack('<I', m.group(1))[0]
            c1 = a + 5 + 5 + struct.unpack('<i', m.group(2))[0]
            c2 = a + 12 + 5 + struct.unpack('<i', m.group(3))[0]
            if c1 != get_fn or c2 != ins_fn: continue
            nm = cstr(u32(node) or 0)
            st = u32(node + 0x14)
            vt = u32(st) if st else None
            rows.append((st or 0, nm, node, vt, rtti(vt) if vt else '?', a))
    for st, nm, node, vt, cls, a in sorted(rows):
        print('state 0x%08x  vtable 0x%08x  %-32s %-45s node 0x%08x init 0x%08x' % (st, vt or 0, nm, cls, node, a))
    print('%d named state(s)' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
