"""Find state-chart condition records {u16 id, u16 kind, u16 value, u16 flags} whose value (offset +4) is one of the
given ids in a DTP section of an Xbox DRM, and show the same 8 bytes in the converted PC DRM (read-only; finding 43,
rock vein: the markup subtests 607 / 608 are the u16 at record +4, read by SCCondTest_MarkupType PC tru+0x382819 /
Xbox 0x82486dd8, while the record id at +0 selects the handler from the agent's link array).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/cond_record_find.py XBOX.drm PC.drm SECTION_ID VALUES [--at 0|4]
  VALUES  comma list (e.g. 607,608); --at: which u16 of the record holds the value (default 4)
Prints for every 4-aligned hit in the Xbox section: offset, Xbox u16 x4, PC u16 x4, and whether the PC bytes are the
per-u16 swap (correct for these records) or a 32-bit swap (u16 halves exchanged).
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def section(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return bytes(s.data)
    raise SystemExit('section %d not in %s' % (sid, path))


def classify(xb, pb):
    """per 4-byte word: '16' = two u16 swapped, '32' = one u32 swapped, '=' unchanged, '?' other"""
    out = []
    for k in range(0, 8, 4):
        x, p = xb[k:k + 4], pb[k:k + 4]
        if x == p and x[:2] != x[:2][::-1]: out.append('=')
        elif p == x[1::-1] + x[3:1:-1] and p != x[::-1]: out.append('16')
        elif p == x[::-1] and p != x[1::-1] + x[3:1:-1]: out.append('32')
        elif p == x[::-1]: out.append('16/32')
        else: out.append('?')
    return '/'.join(out)


def main(argv):
    at = 4
    if '--at' in argv: k = argv.index('--at'); at = int(argv[k + 1]); del argv[k:k + 2]
    xp, pp, sid = argv[0], argv[1], int(argv[2])
    vals = set(int(v, 0) for v in argv[3].split(','))
    xd, pd = section(xp, 'be', sid), section(pp, 'le', sid)
    if len(xd) != len(pd): print('note: sizes differ 0x%x / 0x%x' % (len(xd), len(pd)))
    n = 0
    for o in range(0, min(len(xd), len(pd)) - 8, 4):
        v = struct.unpack_from('>H', xd, o + at)[0]
        if v not in vals: continue
        x = struct.unpack_from('>4H', xd, o); p = struct.unpack_from('<4H', pd, o)
        print('+0x%05x  xbox %5d %5d %5d %5d   pc %5d %5d %5d %5d   %s' % ((o,) + x + p + (classify(xd[o:o + 8], pd[o:o + 8]),)))
        n += 1
    print('%d hits' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
