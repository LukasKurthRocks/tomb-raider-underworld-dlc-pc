"""Undo the words tools/script_init_from_pc.py must not change: array counts, code and record words (read-only on the
inputs, writes OUT). Shadow meter HUD (workspace Befund-Schattenleiste-HUD.md): on the title-update HUD script 38 (PC
script 37) script_init_from_pc copied Crystal's code COUNTS of functions 8 / 9 / 16 / 20 / 21 (61 / 236 / 645 / 626 /
518 words) over the title update's (80 / 301 / 732 / 720 / 595) - an init value block that ends right before a code
array runs into the array's count word (the count sits before the array start, which is the only pointer target), and
the retail-shaped PC block is copied over it. On a script whose functions keep their size (the retail control) the
copied count is the same value, so the defect stays invisible there.

BEFORE = the input of script_init_from_pc, AFTER = its output. Every word that differs and is, in BEFORE's walk, the
count word of an array (code, functions, prototypes, members, locals, args, ...), a code word, or a word of a
function / prototype / member / local / arg record, is set back to BEFORE's value; every other change is kept. The
relocations must be equal in BEFORE and AFTER (script_init_from_pc does not change them on these words).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_init_guard.py BEFORE.drm AFTER.drm OUT.drm SCRIPT_ID
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

RECORDS = ('funcs', 'protos', 'members', 'locals', 'args', 'fsfi', 'sfi', 'enums', 'structs', 'states', 'deps')


def main(argv):
    import script_conv as SC
    if len(argv) != 4: sys.exit(__doc__)
    before, after, out, sid = argv[0], argv[1], argv[2], int(argv[3])
    A = DW.read(open(before, 'rb').read(), 'le')
    rawb = open(after, 'rb').read(); B = DW.read(rawb, 'le')
    sa = next(x for x in A.sections if x.type == 8 and x.id == sid)
    sb = next(x for x in B.sections if x.type == 8 and x.id == sid)
    if len(sa.data) != len(sb.data): sys.exit('script %d: size differs (%d / %d)' % (sid, len(sa.data), len(sb.data)))
    if sa.reloc != sb.reloc: sys.exit('script %d: relocations differ - not a script_init_from_pc pair' % sid)
    W = SC.Walk(sa.data, R.parse(sa.reloc, 'le'), 'le'); W.run()
    guard = {}
    for name, t, n, sz in W.arrays:
        guard[t - 4] = '%s count' % name
        if name == 'code' or name in RECORDS:
            for o in range(t, t + n * sz, 4): guard.setdefault(o, name)
    d = bytearray(sb.data); st = collections.Counter(); undone = []
    for o in range(0, len(d) - 3, 4):
        if sa.data[o:o + 4] == sb.data[o:o + 4]: continue
        what = guard.get(o)
        if what is None: st['changes kept'] += 1; continue
        d[o:o + 4] = sa.data[o:o + 4]; st['changes undone (%s)' % what.split()[-1]] += 1
        undone.append((o, what, struct.unpack_from('<I', sb.data, o)[0], struct.unpack_from('<I', sa.data, o)[0]))
    sb.data = bytes(d)
    raw = B.write('le')
    if rawb[:4] in (b'CDRM', b'MRDC'): raw = DW.cdrm_encode(raw, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(raw)
    print('script %d: %s' % (sid, dict(st)))
    for o, what, bad, good in undone:
        print('  +%#06x %-14s %08x -> %08x (BEFORE)' % (o, what, bad, good))
    print('->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
