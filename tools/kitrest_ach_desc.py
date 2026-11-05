"""What the PC interpreter reads when a DLC script calls a TU-only `achievement` native (read-only; kit-rest task 1,
workspace docs Befund-Kit-Reste-0511.md).

A DLC script's `op65` operand is an external relocation into script 66 (`achievement`); the engine resolves it to the
RESIDENT copy (PC generalbank), so the descriptor address is <PC script 66> + OFF. The op65 handler (tru+0x17de34,
VA 0x57de34) reads [desc] (prototype pointer), [[desc]+0xc] (parameter list), byte [[desc]+0x10] & 0xf (return
type) and calls [desc+0x14] with no null check (tru+0x17dea3 / +0x17deae). This tool prints, for each OFF, what the
PC script 66 holds there: section size, the walker array the word belongs to (name, element, field), the dwords at
OFF / OFF+0x14 and whether each is an internal relocation (= a pointer after load) and where it points.
For comparison the same for the last PC function entries and for the Xbox TU copy (pack10 / pack11 DLC copy is not
needed: the resident one is what the engine uses).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/kitrest_ach_desc.py [GENERALBANK.drm|pc] [OFF ...]     default: pc, 0x214 0x230 0x24c 0x268 0x284
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import script_conv as SC
from native_calls_check import func_table


def sections(ref):
    if ref == 'pc':
        import dtp_word_classes as C
        return [(s['type'], s['id'], s['data'], s['reloc']) for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + 'generalbank.drm')]
    return [(s.type, s.id, s.data, s.reloc) for s in DW.read(open(ref, 'rb').read(), 'le').sections]


def where(arrays, o):
    for name, t, n, sz in arrays:
        if t <= o < t + n * sz:
            k = (o - t) // sz
            return '%s[%d]+0x%x (array 0x%x, %d x 0x%x)' % (name, k, o - t - k * sz, t, n, sz)
    return 'no walker array'


def main(a):
    ref = 'pc'
    if a and not a[0].startswith('0x'): ref = a.pop(0)
    offs = [int(x, 16) for x in a] or [0x214, 0x230, 0x24c, 0x268, 0x284]
    sec = [x for x in sections(ref) if x[0] == 8 and x[1] == 66 and x[2]]
    if not sec: sys.exit('script 66 not found in ' + ref)
    _, _, d, rl = sec[0]
    rel = R.parse(rl, '<'); it = dict(rel.internal)
    ext = {so: (si, do) for si, so, do in rel.external}
    W = SC.Walk(d, rel, '<').run()
    ft = func_table(d, rl)
    print('reference %s: script 66, %d bytes data, %d internal relocs, %d external' % (ref, len(d), len(rel.internal),
                                                                                    len(rel.external)))
    print('walker arrays: ' + ', '.join('%s @0x%x n=%d sz=0x%x' % x for x in W.arrays))
    print('function entries: %d (%s)' % (len(ft), ' '.join('+0x%x' % k for k in sorted(ft))))
    last = max(ft) if ft else 0
    print('last PC function entry +0x%x, end of entry +0x%x' % (last, last + 0x1c))

    def word(o):
        if o + 4 > len(d): return 'beyond section end (0x%x)' % len(d)
        v = struct.unpack_from('<I', d, o)[0]
        s = '%08x' % v
        if o in it: s += ' internal reloc -> +0x%x (%s)' % (it[o], where(W.arrays, it[o]))
        elif o in ext: s += ' external reloc -> section %d +0x%x' % ext[o]
        else: s += ' plain (no relocation)'
        return s + ' | ' + where(W.arrays, o)

    for o in sorted(ft)[-2:] + offs:
        tag = 'PC entry %d' % ft[o][0] if o in ft else 'TU-only offset'
        print('\n+0x%x (%s):' % (o, tag))
        print('  [desc+0x00] proto ptr : ' + word(o))
        if o in it and it[o] + 0x14 <= len(d):
            p = it[o]
            print('    proto+0x0c          : ' + word(p + 0xc))
            print('    proto+0x10 (ret)    : ' + word(p + 0x10))
        print('  [desc+0x14] native fn : ' + word(o + 0x14))
        print('  [desc+0x18] code ptr  : ' + word(o + 0x18))


if __name__ == '__main__':
    main(sys.argv[1:])
