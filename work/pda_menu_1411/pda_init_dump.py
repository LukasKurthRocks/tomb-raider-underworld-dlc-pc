r"""PDA menu 1411: read-only dump of init blocks / string references of one script section.

Usage (from trudlcport):
  ../bin/pyt -t 300 work/pda_menu_1411/pda_init_dump.py SOURCE SCRIPT_ID STRING[,STRING...] [START:END ...]
      SOURCE as tools/script_func_list.py (dlc:g_pda.drm with TRUDLC_PACK_FIRST=pack10/pack11, xbox:..., pc:...)
      prints for every STRING its offset(s) in the section and every internal relocation that points at it,
      then a word dump (with relocation marks) of every START:END range (hex section offsets)
Nothing is written.
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import script_func_list as FL  # noqa: E402
import drm_reloc as R  # noqa: E402


def main(a):
    if len(a) < 3:
        raise SystemExit(__doc__)
    src, sid, strs = a[0], int(a[1]), a[2].split(',')
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    back = {}
    for so, tt in it.items():
        back.setdefault(tt, []).append(so)
    print('%s script %d size %d' % (src, sid, len(d)))
    for s in strs:
        b = s.encode('latin1') + b'\0'
        k = d.find(b)
        while k >= 0:
            # the string may be reached at its start or through a 4-byte length prefix
            refs = back.get(k, []) + back.get(k - 4, [])
            print('  string %-20s @0x%x  referenced from %s' % (s, k, ' '.join('0x%x' % r for r in sorted(refs)) or '-'))
            k = d.find(b, k + 1)
    for rng in a[3:]:
        lo, hi = (int(x, 16) for x in rng.split(':'))
        print('  -- 0x%x .. 0x%x' % (lo, hi))
        for o in range(lo, hi, 4):
            w = struct.unpack_from(E + 'I', d, o)[0]
            mark = ''
            if o in it:
                tt = it[o]
                z = d.find(b'\0', tt)
                txt = d[tt:z] if 0 <= z - tt < 40 else b''
                mark = '->int 0x%x %r' % (tt, txt.decode('latin1')) if txt and all(32 <= c < 127 for c in txt) \
                    else '->int 0x%x' % tt
            elif o in ext:
                mark = '->ext (%d,%d)+0x%x' % ext[o]
            print('    %05x  %08x  %s' % (o, w, mark))


if __name__ == '__main__':
    main(sys.argv[1:])
