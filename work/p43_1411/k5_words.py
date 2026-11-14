r"""P4.4 K-5 (14.11.): bytes around given offsets of one type-7 DTP - Xbox source, own tree, B270 - plus what
dtp_audit.string_spans finds there (short identifier strings < 8 characters, K-5).
Usage: ../bin/pyt -t 600 work/p43_1411/k5_words.py NAME.drm DTP OFF[,OFF..] TREE B270TREE"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R, dtp_audit as DA
from convert_dlc import raw_dlc
from drm import cdrm_decode


def sec(path_or_raw, e, sid):
    D = DW.read(cdrm_decode(path_or_raw, e), e)
    return next((s for s in D.sections if s.type == 7 and s.id == sid), None)


def find(tree, name):
    for dp, dn, fn in os.walk(tree):
        for f in fn:
            if f.lower() == name.lower(): return os.path.join(dp, f)


def main(a):
    name, sid, offs = a[0], int(a[1]), [int(x, 0) for x in a[2].split(',')]
    xr, src = raw_dlc(name); X = sec(xr, 'be', sid)
    P = sec(open(find(a[3], name), 'rb').read(), 'le', sid); K = sec(open(find(a[4], name), 'rb').read(), 'le', sid)
    xd = bytes(X.data); rel = R.parse(bytes(X.reloc), 'be')
    sp = DA.string_spans(xd, rel)
    print('string_spans: %d spans, near the offsets: %s' % (len(sp), [s for s in sp if any(s[0] - 16 <= o <= s[1] + 16 for o in offs)]))
    print('internal pointer targets near: %s' % sorted(t for _, t in rel.internal if any(abs(t - o) <= 16 for o in offs)))
    for o in offs:
        for lab, d in (('xbox', xd), ('own', bytes(P.data)), ('b270', bytes(K.data))):
            b = d[o - 8:o + 12]
            print('+%#x %-5s %s  %r' % (o, lab, b.hex(), bytes(c if 32 <= c < 127 else 46 for c in b).decode()))


if __name__ == '__main__':
    main(sys.argv[1:])
