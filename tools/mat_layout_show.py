"""Read-only: layout of material sections (type 10) of a DRM - size, header words +0x28..+0x6C, internal pointers
(offset -> target, and the u32 stored at the offset), MaterialParams blocks (PS +0x58 / +0x5C, VS +0x68 / +0x6C).
Test 50a: decides whether a PC material's PS MaterialParams block can be grown in place (block at the section end).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mat_layout_show.py FILE.drm le|be ID[,ID]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(a):
    path, e, ids = a[0], a[1], [int(x) for x in a[2].split(',')]
    f = '>' if e == 'be' else '<'
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.type != 10 or s.id not in ids: continue
        r = R.parse(s.reloc, e)
        print('material %d: %d bytes, reloc int %d ext %d idref %d' % (s.id, len(s.data), len(r.internal), len(r.external), len(r.idref)))
        print('   +0x28 libs %s  +0x4C..+0x53 bytes %s' % (struct.unpack_from(f + '4I', s.data, 0x28), s.data[0x4C:0x54].hex()))
        for o in (0x54, 0x58, 0x5C, 0x60, 0x64, 0x68, 0x6C, 0x70):
            if o + 4 <= len(s.data): print('   +%#x = %#x' % (o, struct.unpack_from(f + 'I', s.data, o)[0]))
        for off, tgt in sorted(r.internal):
            print('   int +%#x -> %#x (stored %#x)' % (off, tgt, struct.unpack_from(f + 'I', s.data, off)[0]))
        for t, off in sorted(r.idref, key=lambda x: x[1]):
            print('   id  +%#x type %d = %d' % (off, t, struct.unpack_from(f + 'I', s.data, off)[0]))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
