"""Compare one byte range of a script section (type 8) word by word between the Xbox original (BE) and the converted
PC file (LE), read-only: per word the Xbox value, the PC value, the value a plain u32 swap would give, the value a
2 x u16 swap would give, and which of the two the PC holds (N15 package H 2026-11-09: init blocks of the DLC 2
objective / hint notifier text elements, script 26078 / 26430).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_block_cmp.py XBOX_SOURCE PC_SOURCE SCRIPT_ID FROM TO [PC_FROM]
    SCRIPT_ID: one id, or XBOX_ID/PC_ID when the ids differ (2026-11-09 K-5: TU HUD script 38 = PC 37);
    sources as tools/script_func_list.sections; FROM / TO hex (0x..) or decimal, TO exclusive; PC_FROM: the PC block
    starts elsewhere (base-game reference where PC and Xbox scripts differ in size)
    columns: offset, Xbox word, PC word, verdict (same-u32 / u16x2 / equal / other / reloc)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def sec(src, sid):
    S, e = FL.sections(src)
    q = next((q for q in S if q[0] == 8 and q[1] == sid and q[2]), None)
    if q is None:
        return None, None, None
    rel = R.parse(q[3], e)
    marks = set(rel.id_offsets()) | set(dict(rel.internal)) | {so for _, so, _ in rel.external}
    return q[2], e, marks


def main(argv):
    if len(argv) not in (5, 6):
        print(__doc__)
        return 2
    shift = int(argv[5], 0) - int(argv[3], 0) if len(argv) == 6 else 0
    xid, _, pid = argv[2].partition('/')    # XBOX_ID/PC_ID when the ids differ (TU HUD 38 = PC 37)
    xd, xe, xm = sec(argv[0], int(xid))
    pd, pe, pm = sec(argv[1], int(pid or xid))
    if xd is None or pd is None:
        print('script not found')
        return 1
    lo, hi = int(argv[3], 0), int(argv[4], 0)
    cnt = {}
    for o in range(lo, min(hi, len(xd), len(pd) - shift) - 3, 4):
        xw = struct.unpack_from('>I', xd, o)[0]
        pw = struct.unpack_from('<I', pd, o + shift)[0]
        h16 = struct.unpack('<I', struct.pack('<HH', *struct.unpack('>HH', xd[o:o + 4])))[0]
        if o in xm or (o + shift) in pm:
            v = 'reloc'
        elif pw == xw and h16 == xw:
            v = 'equal'
        elif pw == xw:
            v = 'same-u32'
        elif pw == h16:
            v = 'u16x2'
        else:
            v = 'other'
        cnt[v] = cnt.get(v, 0) + 1
        print('+0x%04x  X %08x  P %08x  %s' % (o, xw, pw, v))
    print('summary %s' % ' '.join('%s %d' % kv for kv in sorted(cnt.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
