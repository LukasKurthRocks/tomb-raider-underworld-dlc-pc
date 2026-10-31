"""List the sections that differ between two PC (little-endian) DRM files of the same layout, read-only: per
(type, id) whether data and / or relocations differ and how many 32-bit words. Finding 43 follow-up (test 35): make
sure a patched test generalbank differs from its base only in the sections that were meant to change.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_diff.py A.drm B.drm
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    A = DW.read(open(argv[0], 'rb').read(), 'le'); B = DW.read(open(argv[1], 'rb').read(), 'le')
    ka = [(s.type, s.id) for s in A.sections]; kb = [(s.type, s.id) for s in B.sections]
    if ka != kb: print('section lists differ: %d vs %d sections, order equal: %s' % (len(ka), len(kb), ka == kb))
    bb = {(s.type, s.id): s for s in B.sections}
    n = 0
    for i, s in enumerate(A.sections):
        # same section list: pair by position (several generic sections share (0, 0)); else by (type, id)
        t = B.sections[i] if ka == kb else bb.get((s.type, s.id))
        if t is None: print('  %s only in A' % ((s.type, s.id),)); n += 1; continue
        if s.data == t.data and s.reloc == t.reloc: continue
        m = min(len(s.data), len(t.data))
        words = sum(s.data[o:o + 4] != t.data[o:o + 4] for o in range(0, m - 3, 4))
        print('  %s data %s (%d -> %d bytes, %d words differ in the common part), reloc %s' % (
            (s.type, s.id), 'equal' if s.data == t.data else 'DIFF', len(s.data), len(t.data), words,
            'equal' if s.reloc == t.reloc else 'DIFF'))
        n += 1
    print('%d of %d sections differ' % (n, len(A.sections)))


if __name__ == '__main__':
    main(sys.argv[1:])
