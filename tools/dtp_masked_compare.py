"""Compare two PC DTPs word by word with the relocated words (pointers, id refs) of either side left out
(read-only; finding 43, state chart scope: are the DLC costume / lara_doppelganger charts the PC base chart?).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_masked_compare.py A.drm SID_A B.drm SID_B [--list N]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statechart_twins as TW


def main(argv):
    n = 10
    if '--list' in argv: k = argv.index('--list'); n = int(argv[k + 1]); del argv[k:k + 2]
    _, a = TW.load_sec(argv[0], 'le', int(argv[1])); _, b = TW.load_sec(argv[2], 'le', int(argv[3]))
    A = TW.Chart(a.data, a.reloc, 'le'); B = TW.Chart(b.data, b.reloc, 'le')
    if len(A.d) != len(B.d):
        print('sizes differ: 0x%x / 0x%x' % (len(A.d), len(B.d))); return
    diff = [o for o in range(0, len(A.d) - 3, 4) if o not in A.mask and o not in B.mask and A.d[o:o + 4] != B.d[o:o + 4]]
    print('%d words, relocated %d / %d, mask equal %s, %d other words differ' % (len(A.d) // 4, len(A.mask), len(B.mask),
                                                                               A.mask == B.mask, len(diff)))
    for o in diff[:n]: print('  +0x%05x  %s  %s' % (o, A.d[o:o + 4].hex(), B.d[o:o + 4].hex()))


if __name__ == '__main__':
    main(sys.argv[1:])
