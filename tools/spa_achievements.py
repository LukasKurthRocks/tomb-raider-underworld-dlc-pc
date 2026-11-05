"""Read-only: the achievement list of an Xbox 360 spa.bin (XDBF) with English label, description and unachieved text
(night analysis 2026-11-03: which in-game event each TU-only achievement native f16-f20 awards, for the live test
steps in docs/Befund-Erfolge.md). Parser: tools/proto_dlc_compare.spa_info.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/spa_achievements.py SPA.bin [ID,ID,...]
  e.g. ../bin/pyt -t 120 tools/spa_achievements.py ../input/xbox-dlc/600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/spa.bin 47,54,55,56,57
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proto_dlc_compare import spa_info


def main(argv):
    if not argv: sys.exit(__doc__)
    I = spa_info(argv[0])
    want = set(int(x) for x in argv[1].split(',')) if len(argv) > 1 else None
    en = I['strings'].get(1, {})
    print('%s: title %s, %d achievements, gamerscore %d' % (os.path.basename(argv[0]), I.get('title_id'), len(I['ach']),
                                                           sum(a[5] for a in I['ach'])))
    for aid, lab, desc, unach, img, gs in I['ach']:
        if want and aid not in want: continue
        print('%3d  %3d G  %s | %s | locked: %s' % (aid, gs, en.get(lab, '?'), en.get(desc, '?'), en.get(unach, '?')))


if __name__ == '__main__':
    main(sys.argv[1:])
