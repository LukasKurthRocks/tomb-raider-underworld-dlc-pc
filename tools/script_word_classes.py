"""Classify every 32-bit word of a converted script against its Xbox source when both have the same layout (same
length), read-only: `same` (u32 value kept = the s32 route), `s16` (the two halves swapped = the converter's Symbol /
s16-pair route kept the Xbox halves), `reloc` (pointer / id reference offsets), `other` (mapped to a different
value). Finding 43 follow-up: the title-update hint-box script (TU generalbank script 10 -> PC script 9) came out of
the generic converter with colours `ff606060 -> 60600140`, small integers `4 -> 0x40000` and string id 1293 as a
Symbol - this lists where, so a fix can be limited to the right words.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_word_classes.py XBOX.drm XBOX_SCRIPT_ID PC.drm PC_SCRIPT_ID [--list s16|other] [--prefix]
  (XBOX.drm decoded, big endian, e.g. from tools/bigfile_extract.py tu generalbank.drm)
  --prefix: the PC section may be longer (data appended, e.g. by tools/script_vtable_insert.py); only the Xbox
  section's length is compared
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    show = None
    if '--list' in argv: k = argv.index('--list'); show = argv[k + 1]; del argv[k:k + 2]
    prefix = '--prefix' in argv; argv = [a for a in argv if a != '--prefix']
    X = DW.read(open(argv[0], 'rb').read(), 'be'); P = DW.read(open(argv[2], 'rb').read(), 'le')
    x = next(s for s in X.sections if s.type == 8 and s.id == int(argv[1]))
    p = next(s for s in P.sections if s.type == 8 and s.id == int(argv[3]))
    if len(x.data) != len(p.data) and not (prefix and len(p.data) > len(x.data)): raise SystemExit('layouts differ: %d vs %d bytes' % (len(x.data), len(p.data)))
    xr = R.parse(x.reloc, 'be'); rel = set(xr.pointer_offsets()) | set(xr.id_offsets())
    st = collections.Counter(); rows = []
    for o in range(0, len(x.data) - 3, 4):
        xv = struct.unpack_from('>I', x.data, o)[0]; pv = struct.unpack_from('<I', p.data, o)[0]
        c = 'reloc' if o in rel else 'same' if pv == xv else 's16' if pv == ((xv & 0xffff) << 16 | xv >> 16) else 'other'
        st[c] += 1
        if c == show: rows.append('  +%#06x  xbox %08x  pc %08x' % (o, xv, pv))
    print('script %s -> %s: %d words %s' % (argv[1], argv[3], len(x.data) // 4, dict(st)))
    for r in rows: print(r)


if __name__ == '__main__':
    main(sys.argv[1:])
