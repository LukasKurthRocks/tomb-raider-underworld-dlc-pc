"""Find the static objects whose first word is a given vtable and print their name string (read-only; 2026-11-09
TruXenia: which enemy state owns the TU Enter function behind a vtable slot?).

Enemy state objects are static: [obj+0] = vtable, [obj+8] = name pointer (ENGINE.md section 13.2). For each vtable
address the image is scanned for aligned big-endian words equal to it; each hit is printed with the C string at
[hit+8] (if it points into the image).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/xbox_vtable_owner.py IMAGE VTABLE[,VTABLE..] [--slot N --of ADDR]
    --slot N --of ADDR: instead of a vtable, give a function address ADDR and its slot N (vtable = word address - 4*N)
Only addresses and names are printed - no game bytes.
"""
import struct
import sys

BASE = 0x82000000


def cstr(d, a):
    o = a - BASE
    if o < 0 or o >= len(d):
        return None
    e = d.find(b'\0', o, o + 96)
    if e < 0:
        return None
    s = d[o:e]
    return s.decode('ascii', 'replace') if s and all(32 <= c < 127 for c in s) else None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    d = open(argv[0], 'rb').read()
    targets = [int(x, 16) for x in argv[1].split(',')]
    if '--slot' in argv:
        slot = int(argv[argv.index('--slot') + 1])
        fn = int(argv[argv.index('--of') + 1], 16)
        word = struct.pack('>I', fn)
        targets = []
        o = d.find(word)
        while o >= 0:
            if o % 4 == 0:
                targets.append(BASE + o - 4 * slot)
            o = d.find(word, o + 1)
        print('function 0x%08x as slot %d -> vtable candidates %s' % (fn, slot, ' '.join('0x%08x' % t for t in targets)))
    for vt in targets:
        word = struct.pack('>I', vt)
        o = d.find(word)
        n = 0
        while o >= 0:
            if o % 4 == 0:
                name_ptr = struct.unpack_from('>I', d, o + 8)[0] if o + 12 <= len(d) else 0
                print('vtable 0x%08x  object 0x%08x  name %s' % (vt, BASE + o, cstr(d, name_ptr)))
                n += 1
            o = d.find(word, o + 1)
        if not n:
            print('vtable 0x%08x  no object found' % vt)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
