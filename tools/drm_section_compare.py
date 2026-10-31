"""Compare two PC DRMs section by section (read-only): which sections differ and how many 32-bit words
(finding 43, rock vein: the re-converted doppelganger_casual.drm must differ only in DTP 20212).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_compare.py A.drm B.drm
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    A = DW.read(open(argv[0], 'rb').read(), 'le'); B = DW.read(open(argv[1], 'rb').read(), 'le')
    if len(A.sections) != len(B.sections): print('section count differs: %d / %d' % (len(A.sections), len(B.sections)))
    same = 0
    for i, (a, b) in enumerate(zip(A.sections, B.sections)):
        if (a.type, a.id, a.data, a.reloc, a.flags) == (b.type, b.id, b.data, b.reloc, b.flags):
            same += 1; continue
        n = sum(1 for o in range(0, min(len(a.data), len(b.data)) - 3, 4) if a.data[o:o + 4] != b.data[o:o + 4])
        print('section %d type %d id %d differs: size %d / %d, reloc %s, %d words' % (
            i, a.type, a.id, len(a.data), len(b.data), 'same' if a.reloc == b.reloc else 'DIFFERENT', n))
    print('%d of %d sections identical; header/names %s' % (same, len(A.sections),
          'same' if (A.names, A.pad, A.ver) == (B.names, B.pad, B.ver) else 'DIFFERENT'))


if __name__ == '__main__':
    main(sys.argv[1:])
