"""Fix the DLC mission screen text layout on PC: title overlapping the description, title not blue.

Finding (Xbox title update Script id 134 vs PC Script id 104, member init blocks of the uitext widgets):
  title widgets of DLC 1/2 (PC members 0x0cc, 0x0e4)         +0x4c colour  Xbox 0xff78afeb (light blue) / PC 0xffc0c0c0
  description widgets of DLC 1/2 (PC members 0x0d8, 0x0f0)   +0x18, +0x24  Xbox 7.5 / PC 8.0   (shadow offsets)
                                                             +0x34         Xbox 12.0 / PC 1.0
                                                             +0x6c (bool)  Xbox 1 / PC 0
                                                             +0x74         Xbox 0 / PC 8        (vertical alignment?)
All other differences of these blocks are platform symbol / text ids. Levels 3-6 are unused and identical.
The patch writes the Xbox values in place (same size, no relocation changes) and checks the old values first.
Reference screenshots: TRU-DLC project, Referenzen/.

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_screen_text_style.py [src]
  src defaults to ../data/pc/mods/generalbank.drm (the installed menu_dlc build).
  -> work/dlc_screen_text/generalbank.drm (+ md5.txt, patch_log.txt)
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import drm_write as DW
import script_conv as SC

SRC = sys.argv[1] if len(sys.argv) > 1 else '../data/pc/mods/generalbank.drm'
OUT = 'work/dlc_screen_text/'
PC_ID = 104
F = lambda x: struct.unpack('<I', struct.pack('<f', x))[0]
# member offset -> [(field offset, PC value, Xbox TU value)]
PATCHES = {
    0x0cc: [(0x4c, 0xffc0c0c0, 0xff78afeb)],
    0x0e4: [(0x4c, 0xffc0c0c0, 0xff78afeb)],
    0x0d8: [(0x18, F(8.0), F(7.5)), (0x24, F(8.0), F(7.5)), (0x34, F(1.0), F(12.0)), (0x6c, 0, 1), (0x74, 8, 0)],
    0x0f0: [(0x18, F(8.0), F(7.5)), (0x24, F(8.0), F(7.5)), (0x34, F(1.0), F(12.0)), (0x6c, 0, 1), (0x74, 8, 0)],
}


def main():
    log = []
    raw_in = open(SRC, 'rb').read()
    drm = DW.read(raw_in, 'le')
    idx = [i for i, s in enumerate(drm.sections) if s.type == 8 and s.id == PC_ID]
    assert len(idx) == 1
    sec = drm.sections[idx[0]]
    d = bytearray(sec.data)
    rel = R.parse(sec.reloc, 'le')
    W = SC.walk(bytes(d), rel, 'le')
    it = dict(rel.internal)
    log.append('source %s md5 %s, section #%d (8,%d)' % (SRC, hashlib.md5(raw_in).hexdigest(), idx[0], PC_ID))
    _, mt, mn, _ = [a for a in W.arrays if a[0] == 'members'][0]
    by_off = {struct.unpack_from('<H', d, mt + 20 * k + 12)[0]: mt + 20 * k for k in range(mn)}
    for moff, fields in sorted(PATCHES.items()):
        init = it[by_off[moff] + 16]             # member init block
        obj = it[init]                           # first word of the block points at the widget object
        for foff, old, new in fields:
            a = obj + foff
            assert a not in it and a not in rel.id_offsets(), 'field is a pointer/id: member 0x%x +0x%x' % (moff, foff)
            cur = struct.unpack_from('<I', d, a)[0]
            assert cur == old, 'member 0x%x +0x%x: expected %08x, found %08x' % (moff, foff, old, cur)
            struct.pack_into('<I', d, a, new)
            log.append('member 0x%03x +0x%02x (data +0x%x): %08x -> %08x' % (moff, foff, a, old, new))
    sec.data = bytes(d)
    raw = drm.write('le')
    assert len(raw) == len(DW.cdrm_decode(raw_in, 'le'))
    enc = DW.cdrm_encode(raw, 'le')
    assert DW.cdrm_decode(enc, 'le') == raw
    os.makedirs(OUT, exist_ok=True)
    open(OUT + 'generalbank.drm', 'wb').write(enc)
    md5 = hashlib.md5(enc).hexdigest()
    open(OUT + 'md5.txt', 'w').write('%s  generalbank.drm\n' % md5)
    log.append('output %sgeneralbank.drm CDRM %d B md5 %s' % (OUT, len(enc), md5))
    open(OUT + 'patch_log.txt', 'w').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
