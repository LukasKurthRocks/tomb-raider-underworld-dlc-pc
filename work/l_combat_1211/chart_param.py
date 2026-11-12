"""Group L 12.11. (read-only): value of a chart parameter of an object DTP, as tru.exe 0x7820e0 / 0x782b40 resolve a
condition value with key 1000: table = [[inst+0x10]] (object data = the object DTP) +0xd0, entry = pointer table[N] ->
record {u32 type, value}; type 3 / 4 = f32 (rounded by 0x814d20), 5 = bool (byte != 0), anything else = s32.
Pointers are followed through the section's internal relocations (or external ones into another section).
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/chart_param.py DRM SECTION_ID N [N ...]"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R


def main(a):
    D = DW.read(open(a[0], 'rb').read(), 'le')
    sid = int(a[1])
    ks = [k for k, s in enumerate(D.sections) if s.id == sid and s.type == 7]
    if not ks:
        print('no DTP section with id %d' % sid)
        return 1
    k = ks[0]

    def target(k, off):
        s = D.sections[k]
        r = R.parse(bytes(s.reloc), 'le')
        t = dict(r.internal).get(off)
        if t is not None:
            return k, t
        for si, src, dst in r.external:
            if src == off:
                return si, dst
        return None
    p = target(k, 0xd0)
    if p is None:
        print('+0xd0 of DTP %d is no pointer' % sid)
        return 1
    print('DTP %d section %d: parameter table at section %d +0x%x' % (sid, k, p[0], p[1]))
    for x in a[2:]:
        n = int(x)
        e = target(p[0], p[1] + 4 * n)
        if e is None:
            print('param %d: entry +0x%x is no pointer' % (n, p[1] + 4 * n))
            continue
        d = D.sections[e[0]].data
        typ, raw = struct.unpack_from('<II', d, e[1])
        f = struct.unpack_from('<f', d, e[1] + 4)[0]
        val = ('f32 %g' % f) if typ in (3, 4) else ('bool %d' % (raw & 0xff != 0)) if typ == 5 else ('s32 %d' % struct.unpack_from('<i', d, e[1] + 4)[0])
        print('param %d: record section %d +0x%x type %d -> %s (raw 0x%08x)' % (n, e[0], e[1], typ, val, raw))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
