"""Dump the init trees of data members (members, args, locals) of one PC generalbank script next to the Xbox words
(finding 43, test 36: TU-only members of the hint-box script 9 kept their converted init values).

Per member with an init value: kind, name Symbol, type tag, userType, then every non-pointer word of the init tree as
path / offset / our word (LE file bytes) / Xbox word (BE file bytes at the same offset) / class (same / s32 / s16 /
other - the byte order that turns the Xbox bytes into ours). Read-only.

Usage (from the repository root):
  ../bin/pyt tools/script_init_dump.py PC_DRM SCRIPT_ID XBOX_NAME XBOX_ID [--only-tu REF_DRM]
  --only-tu REF_DRM: only members without a counterpart (name, tag, userType) in REF_DRM's script SCRIPT_ID
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC
import script_init_from_pc as I
import dtp_word_classes as C


def cls(x, o):
    for name in ('raw', 's32', 's16', 'u8u8u16', 'u16u8u8'):
        if I.perm(x, name) == o: return name
    return 'other'


def main(argv):
    ref = None; retail = "--retail" in argv; argv = [a for a in argv if a != "--retail"]
    if '--only-tu' in argv: k = argv.index('--only-tu'); ref = argv[k + 1]; del argv[k:k + 2]
    src, sid, xname, xid = argv[0], int(argv[1]), argv[2], int(argv[3])
    D = DW.read(open(src, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    ra = R.parse(s.reloc, 'le'); w = SC.Walk(s.data, ra, 'le'); w.run(); it = dict(ra.internal)
    x = next(q for q in C.find(C.BASE[1:] if retail else C.BASE, 'be', 'xenon-w' + chr(92) + xname) if q['type'] == 8 and q['id'] == xid)['data']
    skip = set()
    if ref:
        P = DW.read(open(ref, 'rb').read(), 'le'); p = next(q for q in P.sections if q.type == 8 and q.id == sid)
        rb = R.parse(p.reloc, 'le'); wb = SC.Walk(p.data, rb, 'le'); wb.run()
        skip = set(I.members(wb, p.data, 'le'))
    for key, L in I.members(w, s.data, 'le').items():
        if key in skip: continue
        for a in L:
            ia = it.get(a + 16)
            if ia is None: continue
            print('%s name %d tag 0x%x ut %d (entry 0x%x, init 0x%x)' % (key[0], key[1], key[2], key[3], a, ia))
            for path, o in I.leaves(w, it, ia):
                ours = bytes(s.data[o:o + 4]); xb = bytes(x[o:o + 4]) if o + 4 <= len(x) else b''
                print('   %-14s 0x%04x  ours %s  xbox %s  %s' % ('.'.join(str(v) for v in path), o, ours.hex(),
                      xb.hex(), cls(xb, ours) if xb else '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
