"""Print GlobalInfo's player object list (generalbank DTP 2, GlobalInfo +4) of PC / converted / Xbox generalbanks
(read-only; 2026-11-06 exe sites K8-K14, docs Befund-Exe-Stellen-K8-K14-0611.md, item K12).

What the list is (proven on the PC code, tru.exe; GlobalInfo = [0xe7ee50], DTP 2 +0xf0 on the PC files):
  GlobalInfo +4 -> {u16 count; pad; u16 *ids at +4} = the player (costume) object ids. Readers: tru+0x183441 (index of
  the current costume [0xe7f1c8] in the list), tru+0x2f0acd (next costume of the cycle), tru+0x1d4166 (unit spawn
  records whose object id is in the list are rewritten to the current costume), tru+0x1c1820 / tru+0x1c1900 (a
  unit's object list: ids in this list are neither requested nor dumped with the unit), tru+0x1de62d.
Prints count and ids with names from an objectlist.txt ("N" header, then "id,name" lines).

Usage (from the repository root; FILE = a PC / converted DRM or tu:NAME / retail:NAME for the Xbox originals):
  ../bin/pyt -t 120 tools/globalinfo_player_list.py FILE[,FILE..] [--gi OFFSET] [--objectlist objectlist.txt]
      --gi       offset of GlobalInfo in DTP 2 (default: 0xf0)
      --objectlist  default work/generic/lists/xboxtu_objectlist.txt
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_idrefs as IR, objlists as OL

HERE = os.path.dirname(os.path.abspath(__file__))


def player_list(spec, gi):
    secs, e = IR.load(spec)
    s = next((x for x in secs if x[0] == 7 and x[1] == 2), None)
    if s is None: return None, 'DTP 2 not found'
    d = bytes(s[2]); f = '>' if e == 'be' else '<'
    it = dict(R.parse(bytes(s[3]), e).internal)
    p = it.get(gi + 4)
    if p is None: return None, 'GlobalInfo +4 (DTP 2 +0x%x) is not a pointer' % (gi + 4)
    n = struct.unpack_from(f + 'H', d, p)[0]
    q = it.get(p + 4)
    if q is None: return None, 'list +4 (DTP 2 +0x%x) is not a pointer' % (p + 4)
    ids = [struct.unpack_from(f + 'H', d, q + 2 * k)[0] for k in range(n)]
    return (p, q, ids), None


def main(argv):
    gi = 0xf0
    if '--gi' in argv: k = argv.index('--gi'); gi = int(argv[k + 1], 16); del argv[k:k + 2]
    ol = os.path.join(HERE, '..', 'work', 'generic', 'lists', 'xboxtu_objectlist.txt')
    if '--objectlist' in argv: k = argv.index('--objectlist'); ol = argv[k + 1]; del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    names = OL.read_objectlist(open(ol, 'rb').read()) if os.path.exists(ol) else {}
    for spec in argv[0].split(','):
        r, err = player_list(spec, gi)
        if err:
            print('%s: %s' % (spec, err)); continue
        p, q, ids = r
        print('%s: GlobalInfo +4 -> DTP 2 +0x%x, %d ids at +0x%x' % (spec, p, len(ids), q))
        print('  ' + ', '.join('%d %s' % (i, names.get(i, '?')) for i in ids))


if __name__ == '__main__':
    main(sys.argv[1:])
