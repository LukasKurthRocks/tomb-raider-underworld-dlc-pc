"""Group L 12.11. (read-only): data members of one script section (root +0x2c SArray, 20-byte records {DataType 12
(+0 tag, low 4 bits = base type), u16 +0xc offset, u16 +0xe name symbol, +0x10 init pointer}) with the first init words
(as u32 and f32). Optional filter: only members at the given instance offsets.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/script_members.py DRM SCRIPT_ID [OFFSET ...]"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import script_func_list as FL

S, e = FL.sections(sys.argv[1])
E = '>' if e == 'be' else '<'
sid = int(sys.argv[2])
want = set(int(x, 0) for x in sys.argv[3:])
d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
it = dict(R.parse(rl, e).internal)
arr = it.get(0x2c)
n = struct.unpack_from(E + 'I', d, arr - 4)[0] if arr else 0
print('script %d: %d members at 0x%x' % (sid, n, arr or 0))
for k in range(n):
    a = arr + 20 * k
    tag = struct.unpack_from(E + 'I', d, a)[0]
    off, sym = struct.unpack_from(E + 'HH', d, a + 12)
    if want and off not in want:
        continue
    ini = it.get(a + 16)
    vals = ''
    if ini is not None:
        w = struct.unpack_from(E + '4I', d, ini)
        vals = ' init @0x%x u32 %s f32 %s' % (ini, ['0x%x' % x for x in w],
                                             ['%g' % struct.unpack(E + 'f', struct.pack(E + 'I', x))[0] for x in w])
    print('m%-3d off %4d (0x%03x) tag 0x%08x type %d sym %d%s' % (k, off, off, tag, tag & 0xf, sym, vals))
