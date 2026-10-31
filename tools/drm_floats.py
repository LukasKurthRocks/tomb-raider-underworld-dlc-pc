"""Print the sections of a PC (little-endian) DRM and, for chosen ones, every 32-bit word as hex and float (read-only).

Finding 43, ASI step 3.2 (DLC 2 shadow meter): the title update's meter code reads its tuning (max, drain / refill
rates, thresholds) from the doppelganger player object's data; this tool shows which small DTP / object sections of
player_tru_dlc2_extension.drm hold plausible float tables.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/drm_floats.py FILE.drm                 list sections (index, type, id, size)
  ../bin/pyt -t 120 tools/drm_floats.py FILE.drm ID[,ID..] [N]   words of the sections with these ids (first N words)
                                                                 plus their internal / external relocations (pointers)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def fmt(w):
    f = struct.unpack('<f', struct.pack('<I', w))[0]
    plain = '%.6g' % f if (w == 0 or 1e-6 < abs(f) < 1e7) else ''
    return '%08x %s' % (w, plain)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    if len(argv) == 1:
        for i, s in enumerate(D.sections):
            print('%3d type %2d id %6d size %6d' % (i, s.type, s.id, len(s.data)))
        return
    ids = set(int(x) for x in argv[1].split(','))
    n = int(argv[2]) if len(argv) > 2 else 200
    for s in D.sections:
        if s.id not in ids:
            continue
        d = bytes(s.data)
        print('== type %d id %d size %d' % (s.type, s.id, len(d)))
        for o in range(0, min(len(d) // 4, n) * 4, 4):
            print('  +0x%03x  %s' % (o, fmt(struct.unpack_from('<I', d, o)[0])))
        r = R.parse(bytes(s.reloc), "le")
        for o, t in r.internal:
            print("  reloc internal +0x%03x -> +0x%03x" % (o, t))
        for si, o, t in r.external:
            print("  reloc external +0x%03x -> section %d (id %d) +0x%03x" % (o, si, D.sections[si].id, t))


if __name__ == '__main__':
    main(sys.argv[1:])
