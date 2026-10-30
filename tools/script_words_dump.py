"""Print the 32-bit words of one script section (type 8) in a range, with the walker's element labels, read-only.
Finding 43 follow-up (test 35): compare header / prototype words of the ported title-update hint-box script (PC
script 9 in a test generalbank) with Crystal's own PC script 9 and the Xbox TU script 10, to see which u16-pair
words the converter left in Xbox order.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/script_words_dump.py SOURCE SCRIPT_ID START_HEX END_HEX
  SOURCE = a PC (little-endian) DRM file, or a tools/menu_dlc_probe.py variant (xl / xt / pb / pp)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def main(argv):
    import script_conv as SC
    src, sid, a, b = argv[0], int(argv[1]), int(argv[2], 16), int(argv[3], 16)
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal); ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    W = SC.Walk(d, rel, e).run()
    arr = [(name, t, n, sz) for name, t, n, sz in W.arrays]
    for o in range(a, min(b, len(d) - 3), 4):
        lab = ''
        for name, t, n, sz in arr:
            if t <= o < t + n * sz: lab = '%s[%d]+%#x' % (name, (o - t) // sz, (o - t) % sz)
        ref = ('-> +%#x' % it[o]) if o in it else ('-> %s' % (ext[o],)) if o in ext else ''
        print('+%#06x  %08x  %-18s %s' % (o, struct.unpack_from(E + 'I', d, o)[0], lab, ref))


if __name__ == '__main__':
    main(sys.argv[1:])
