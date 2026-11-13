"""sluice_1311: check a file built by water_transplant.py against its input, by position: the first len(IN) sections
must be byte-equal (data + relocations) except the replaced materials; list the appended sections with md5 (read-only).

usage (from trudlcport): ../bin/pyt -t 600 work/sluice_1311/verify_built.py IN.drm BUILT.drm
"""
import sys, os, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW


def main(a):
    A = DW.read(open(a[0], 'rb').read(), 'le'); B = DW.read(open(a[1], 'rb').read(), 'le')
    diff = []
    for i, s in enumerate(A.sections):
        t = B.sections[i]
        if (s.type, s.id) != (t.type, t.id): diff.append('pos %d: %d:%d -> %d:%d' % (i, s.type, s.id, t.type, t.id)); continue
        if s.data != t.data or s.reloc != t.reloc: diff.append('%d:%d changed' % (s.type, s.id))
    app = ['%d:%d %d B md5 %s' % (t.type, t.id, len(t.data), hashlib.md5(t.data + t.reloc).hexdigest()[:8])
           for t in B.sections[len(A.sections):]]
    print('%s: %d -> %d sections; changed: %s; appended: %s'
          % (os.path.basename(a[1]), len(A.sections), len(B.sections), ', '.join(diff) or '-', ', '.join(app) or '-'))


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1:])
