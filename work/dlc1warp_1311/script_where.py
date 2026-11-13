"""Where does an offset of a script section fall (read-only)? Lists the walker arrays of the script (name, start, count,
element size) and names the array element that contains each given offset; for function entries also the code
pointer and the prototype name pointer (C string) when present.

Usage (from trudlcport): ../bin/pyt -t 300 work/dlc1warp_1311/script_where.py FILE.drm SCRIPT_ID OFFSET[,OFFSET...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import script_func_list as FL
import script_conv as SC


def cstr(d, o):
    if o is None or o >= len(d):
        return None
    e = d.find(b'\0', o)
    return d[o:e if e >= 0 else o + 40][:60].decode('latin-1')


def main(argv):
    src, sid = argv[0], int(argv[1])
    offs = [int(x, 0) for x in argv[2].split(',')]
    S, e = FL.sections(src)
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    W = SC.Walk(d, rel, e).run()
    print('script %d size %d' % (sid, len(d)))
    for name, t, n, sz in W.arrays:
        print('  array %-12s @0x%04x n=%d size=%d end=0x%04x' % (name, t, n, sz, t + n * sz))
    for o in offs:
        hit = [(name, t, n, sz) for name, t, n, sz in W.arrays if t <= o < t + n * sz]
        print('offset 0x%x:' % o)
        if not hit:
            # nearest internal pointer target / string
            print('   in no walker array; word 0x%08x; cstr %r' % (struct.unpack_from('<I', d, o)[0] if o + 4 <= len(d) else 0, cstr(d, o)))
        for name, t, n, sz in hit:
            k = (o - t) // sz
            a = t + k * sz
            print('   %s[%d] @0x%x (+0x%x into element)' % (name, k, a, o - a))
            words = [struct.unpack_from('<I', d, a + j)[0] for j in range(0, min(sz, 0x40), 4)]
            print('   words', ' '.join('%08x' % w for w in words))
            for j in range(0, min(sz, 0x40), 4):
                if a + j in it:
                    tgt = it[a + j]
                    print('     +0x%02x -> int 0x%x %r' % (j, tgt, cstr(d, tgt)))


if __name__ == '__main__':
    main(sys.argv[1:])
