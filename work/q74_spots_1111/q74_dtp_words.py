"""Q74 (2026-11-11): print words of the object DTP (section 11 word +0 -> type-7 DTP) of PC object DRMs at given offsets,
with internal-pointer targets and the 16 bytes behind each pointer (read-only). Used for the uber subclass constructor
0x6d60b0, which copies DTP +0x40 / +0x44 into the uber's interaction record slots +0xd4 / +0xd8.

Usage (from the repository root):
  ../bin/pyt -t 120 work/q74_spots_1111/q74_dtp_words.py OFFS(hex,comma) OBJ.drm [OBJ.drm ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R


def main(argv):
    offs = [int(x, 16) for x in argv[0].split(',')]
    for p in argv[1:]:
        D = DW.read(open(p, 'rb').read(), 'le')
        o11 = [s for s in D.sections if s.type == 11]
        if not o11:
            print('%s: no object section' % p); continue
        did = struct.unpack_from('<I', bytes(o11[0].data), 0)[0]
        dtp = [s for s in D.sections if s.type == 7 and s.id == did]
        if not dtp:
            print('%s: dtp %d missing' % (p, did)); continue
        d = bytes(dtp[0].data); it = dict(R.parse(bytes(dtp[0].reloc), 'le').internal)
        out = []
        for o in offs:
            w = struct.unpack_from('<I', d, o)[0]
            t = it.get(o)
            if t is not None:
                out.append('+0x%x -> 0x%x {%s}' % (o, t, ' '.join('%08x' % v for v in struct.unpack_from('<4I', d, t))))
            else:
                out.append('+0x%x = %08x' % (o, w))
        print('%-36s dtp %d: %s' % (os.path.basename(p), did, '; '.join(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
