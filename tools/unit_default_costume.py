"""Read the default player costume index of a level unit DRM (read-only; object 858 investigation).

The level load (Xbox retail 0x8229b3f0 / TU 0x82297d30 GAMELOOP_LevelLoadAndInit, PC tru+0x1de2b0) takes the player
costume from the unit when no chosen costume applies: unit data (+8 of the stream unit = the DRM's root section)
-> pointer +0x70 -> u16 +0x294 = index into the costume name table (Xbox [0x829bffc8], PC [0xdb94d0], 8-byte entries).
This tool follows the same path in the file: the root section (last section by default, or --sec INDEX), the pointer
at +0x70 (internal or external relocation) and the u16 at +0x294 of its target, and prints the neighbouring words.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/unit_default_costume.py FILE.drm [--be] [--sec INDEX] [--ptr 0x70] [--field 0x294]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv
    argv = [a for a in argv if a != '--be']
    sec, ptr, field = None, 0x70, 0x294
    if '--sec' in argv:
        k = argv.index('--sec'); sec = int(argv[k + 1]); del argv[k:k + 2]
    if '--ptr' in argv:
        k = argv.index('--ptr'); ptr = int(argv[k + 1], 0); del argv[k:k + 2]
    if '--field' in argv:
        k = argv.index('--field'); field = int(argv[k + 1], 0); del argv[k:k + 2]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    if sec is None:                         # candidates: sections whose +ptr is a relocated pointer
        for i, c in enumerate(D.sections):
            rc = R.parse(bytes(c.reloc), e)
            if ptr in dict(rc.internal) or ptr in {o for _, o, _ in rc.external}:
                print('candidate section index %d: type %d id %d size 0x%x' % (i, c.type, c.id, len(c.data)))
        print('(default: last section; pick one with --sec)')
    si = len(D.sections) - 1 if sec is None else sec
    s = D.sections[si]
    print('root section index %d: type %d id %d size 0x%x' % (si, s.type, s.id, len(s.data)))
    r = R.parse(bytes(s.reloc), e)
    intern = dict(r.internal)
    ext = {o: (xi, t) for xi, o, t in r.external}
    if ptr in intern:
        tsec, toff = s, intern[ptr]
        print('+0x%x -> internal +0x%x' % (ptr, toff))
    elif ptr in ext:
        xi, toff = ext[ptr]
        tsec = D.sections[xi]
        print('+0x%x -> section index %d (type %d id %d) +0x%x' % (ptr, xi, tsec.type, tsec.id, toff))
    else:
        print('+0x%x is not relocated (word 0x%08x) - wrong root section?' % (ptr, struct.unpack_from(f + 'I', s.data, ptr)[0]))
        return
    d = bytes(tsec.data)
    a = toff + field
    if a + 2 > len(d):
        print('field +0x%x outside the target (size 0x%x)' % (field, len(d) - toff))
        return
    v = struct.unpack_from(f + 'H', d, a)[0]
    print('u16 at target +0x%x = %d (0x%04x)' % (field, v, v))
    lo = (a & ~3) - 8
    for o in range(max(lo, 0), min(lo + 24, len(d)), 4):
        w = struct.unpack_from(f + 'I', d, o)[0]
        print('  +0x%x: %08x  (u16 %d, %d)' % (o - toff, w, *struct.unpack_from(f + 'HH', d, o)))


if __name__ == '__main__':
    main(sys.argv[1:])
