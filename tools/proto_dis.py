"""Annotated disassembly of a prototype (2007) or retail Xbox function, with prototype map names (read-only;
docs/Befund-Prototyp-2007.md).

Capstone + the VMX128 decoder of tools/ppc_dis128.py. Every `bl` target and every global address built by
lis + addi/ori/load/store is annotated with the prototype map symbol (prototype image) and, via the name map, the
retail / PC partner. For a retail image the annotation is the prototype name of the retail partner (if paired).
Used to describe compiled-out prototype logic precisely enough to port it 1:1 (fields, calls, globals). The global
annotation comes from tools/ppc_xrefs.py (lis tracking); after a register is reused for a pointer load the note on a
following displacement can be wrong (read the instruction, not only the note). Nothing is
copied out of the image except instruction text in the terminal.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/proto_dis.py NAME_OR_ADDR [--retail] [--max N]
      NAME_OR_ADDR: exact prototype function name (first match) or hex address; --retail: the address is in the
      retail image work/xenia_dump/retail_image_82000000.bin; --max: instruction limit (default 400)
"""
import sys, os, struct, bisect
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import ppc_dis128 as V
import proto_symbols as PS
import proto_chain as PCH

BASE = 0x82000000
MAP = 'work/proto2007/map/tr8_Content.map'


def main(argv):
    if not argv:
        sys.exit(__doc__)
    retail = '--retail' in argv
    mx = 400
    if '--max' in argv:
        k = argv.index('--max'); mx = int(argv[k + 1]); del argv[k:k + 2]
    argv = [a for a in argv if a != '--retail']
    C = PCH.Chain()
    syms = PS.load_map(MAP)
    keys = [s[0] for s in syms]
    path = PCH.RETAIL if retail else PCH.PROTO
    d, secs = P.load(path)
    funcs, res = P.cached(path)
    tgt = argv[0]
    if tgt.startswith('0x'):
        a = int(tgt, 16)
    else:
        hits = [r for r in C.names if r['name'] == tgt]
        if not hits:
            sys.exit('no prototype function named %s' % tgt)
        a = int(hits[0]['proto'], 16)
    f = P.func_of(funcs, a)
    if not f:
        sys.exit('no function at 0x%08x' % a)

    def pname(v):
        i = bisect.bisect_right(keys, v) - 1
        if i < 0:
            return '?'
        s = syms[i]
        nm = PS.demangle(s[1])
        if nm == '<str>':
            nm = '"%s"' % (PS.str_text(s[1]) or '')[:40]
        return nm + ('+0x%x' % (v - s[0]) if v != s[0] else '')

    def note(v):
        if retail:
            rows = C.by_retail.get(v, [])
            pc = C.xpc.get(v)
            return '%s%s' % (rows[0]['name'] if rows else '', (' PC ' + pc['pc']) if pc else '')
        rows = C.by_proto.get(v, [])
        r0 = rows[0] if rows else None
        extra = ''
        if r0 and r0['retail']:
            extra = ' [retail %s %s%s]' % (r0['retail'], r0['tier'], (' PC ' + r0['pc']) if r0['pc'] else '')
        return pname(v) + extra

    items = dict((x, (k, v)) for x, k, v in res[f[0]])
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    head = note(f[0]) if not retail else (note(f[0]) or '?')
    print('== %s 0x%08x..0x%08x (%d B): %s' % ('retail' if retail else 'proto', f[0], f[1], f[1] - f[0], head))
    a = f[0]
    n = 0
    while a < f[1] and n < mx:
        w = struct.unpack_from('>I', d, a - BASE)[0]
        text = None
        if (w >> 26) in (5, 6) or ((w >> 26) == 4 and (w & 0x7f3) in V.LS128):
            text = V.vmx128(w)
        if text is None:
            ins = list(md.disasm(struct.pack('>I', w), a, 1))
            text = ('%s %s' % (ins[0].mnemonic, ins[0].op_str)) if ins else (V.vmx128(w) or '.long 0x%08x' % w)
        c = ''
        if a in items:
            k, v = items[a]
            c = '  ; ' + ('call ' if k == 'call' else '') + note(v)
        print('0x%08x  %-40s%s' % (a, text, c))
        a += 4
        n += 1


if __name__ == '__main__':
    main(sys.argv[1:])
