"""Group N 12.11.2026 (read-only): print one section of a DRM file as words (+ floats) with its internal relocations,
and optionally every section of the file holding a given u32 / u16 value.

Usage (from trudlcport):
  ../bin/pyt -t 120 work/n_research_1211/sec_words.py FILE.drm TYPE ID [--be]
  ../bin/pyt -t 120 work/n_research_1211/sec_words.py FILE.drm find VALUE [--be]     VALUE decimal or 0x hex
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv
    argv = [a for a in argv if a != '--be']
    e = '>' if be else '<'
    d = DW.read(open(argv[0], 'rb').read(), 'be' if be else 'le')
    if argv[1] == 'find':
        v = int(argv[2], 0)
        for s in d.sections:
            b = s.data or b''
            hits32 = [o for o in range(0, len(b) - 3, 4) if struct.unpack_from(e + 'I', b, o)[0] == v]
            hits16 = [o for o in range(0, len(b) - 1, 2) if struct.unpack_from(e + 'H', b, o)[0] == v]
            if hits32 or hits16:
                print('%d:%d  u32 at %s  u16 at %s' % (s.type, s.id, [hex(o) for o in hits32][:12],
                                                     [hex(o) for o in hits16][:12]))
        return
    t, i = int(argv[1]), int(argv[2])
    s = next(q for q in d.sections if q.type == t and q.id == i)
    b = s.data or b''
    r = R.parse(s.reloc, 'be' if be else 'le')
    ints = dict(r.internal) if getattr(r, 'internal', None) else {}
    print('type %d id %d: %d bytes, relocations int %d' % (t, i, len(b), len(ints)))
    for attr in ('external', 'idref_a', 'idref'):
        v = getattr(r, attr, None)
        if v: print('  %s: %s' % (attr, list(v)[:40]))
    for o in range(0, len(b) - 3, 4):
        w = struct.unpack_from(e + 'I', b, o)[0]
        f = struct.unpack_from(e + 'f', b, o)[0]
        tag = ('-> +0x%x' % ints[o]) if o in ints else ''
        fs = ('%g' % f) if 1e-6 < abs(f) < 1e7 else ''
        print('+0x%04x  %08x  %10d  %-12s %s' % (o, w, w if w < 0x80000000 else w - (1 << 32), fs, tag))


if __name__ == '__main__':
    main(sys.argv[1:])
