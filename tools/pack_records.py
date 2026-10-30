"""List the records of a DLC pack archive whose name contains a pattern: name, spec word (language / platform
bits; locals use 001/002/004/008/016/032 = EN/FR/DE/IT/ES/NL), size. Read-only. Used to see whether a file
(e.g. the speech of a cinematic, `.mul`) exists once or per language (finding 43 follow-up, DLC 1 intro in English).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pack_records.py pack10|pack11 PATTERN [PATTERN ...]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlc_convert_all import PACK_PATHS
from archive import Archive
from names import load, L


def main(argv):
    pack, pats = argv[0], [p.lower() for p in argv[1:]]
    pi = [i for i, p in enumerate(PACK_PATHS) if pack in os.path.basename(p)][0]
    A = Archive(PACK_PATHS[pi], 'be'); xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    n = 0
    for r in A.idx:
        name = xn.get(r['hash'], '0x%08x' % r['hash'])
        if pats and not any(p in name.lower() for p in pats): continue
        n += 1
        print('%-60s spec %08x  %s' % (name, r['spec'], ' '.join('%s=%s' % (k, v) for k, v in r.items() if k not in ('hash', 'spec'))))
    print('records: %d' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
