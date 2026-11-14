r"""PDA menu 1411: read-only list of the sections of a DRM with the given (type, id) pairs, plus one u32 per
(script id, offset) - to see whether texture ids named in a script's init data exist in the same file.

Usage (from trudlcport):
  ../bin/pyt -t 300 work/pda_menu_1411/pda_sections.py SOURCE T:ID[,T:ID...] [SCRIPT_ID:HEXOFF ...]
      SOURCE as tools/script_func_list.py (dlc:g_pda.drm with TRUDLC_PACK_FIRST, xbox:..., pc:..., or a PC DRM file)
Nothing is written.
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import script_func_list as FL  # noqa: E402


def main(a):
    if len(a) < 2:
        raise SystemExit(__doc__)
    S, e = FL.sections(a[0])
    E = '>' if e == 'be' else '<'
    want = [tuple(int(x) for x in p.split(':')) for p in a[1].split(',')]
    print('%s: %d sections, endian %s' % (a[0], len(S), e))
    for t, i in want:
        hits = [k for k, q in enumerate(S) if q[0] == t and q[1] == i]
        print('  section %d:%d -> %s' % (t, i, ', '.join('index %d size %d' % (k, len(S[k][2] or b'')) for k in hits)
                                          or 'not in file'))
    for p in a[2:]:
        sid, off = p.split(':')
        d = next(q[2] for q in S if q[0] == 8 and q[1] == int(sid) and q[2])
        o = int(off, 16)
        w = struct.unpack_from(E + 'I', d, o)[0]
        print('  script %s +0x%x = 0x%08x (%d)' % (sid, o, w, w))


if __name__ == '__main__':
    main(sys.argv[1:])
