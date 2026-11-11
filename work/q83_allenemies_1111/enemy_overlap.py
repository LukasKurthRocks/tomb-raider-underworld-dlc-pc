"""Q83: shared section ids between enemy groups (read-only).

The engine keeps several section kinds in global tables keyed by id and the FIRST loaded copy wins (anim pool
0x8c1240: an existing id only gets refcount +1 at 0x438f49; materials / shader libs 0x551ec9, ENGINE.md section 2;
DTP table 0xc36f28 handler 0x54dd10 keeps an existing entry). Two enemy groups that carry the same (type, id) with
different bytes therefore depend on load order when both are resident. This lists, per pair of enemy groups (object +
child objects, enemy_catalog.tsv), how many (type, id) they share and how many of those differ in content (md5 of the
section data; relocation-dependent words included, so 'differ' is an upper bound).

Usage (from the repository root):
  ../bin/pyt -t 3600 work/q83_allenemies_1111/enemy_overlap.py MODS_DIR CATALOG.tsv [--arena UNIT ...]
  --arena: also compare every group with these unit DRMs (the arena levels).
"""
import sys, os, hashlib, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import objlists as OL
from enemy_catalog import Src

TYPES = {0: 'general', 2: 'anim', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
         11: 'object', 12: 'mesh', 13: 'unit'}


def secmap(S, names):
    m = {}
    for n in names:
        g = S.get(n)
        if g is None:
            continue
        for s in DW.read(g[2], 'le').sections:
            if s.type in (0, 11):
                continue
            m.setdefault((s.type, s.id), hashlib.md5(bytes(s.data)).hexdigest())
    return m


def main(argv):
    mods, tsv = argv[0], argv[1]
    arena = []
    if '--arena' in argv:
        for x in argv[argv.index('--arena') + 1:]:
            if x.startswith('--'):
                break
            arena.append(x)
    names = OL.read_objectlist(open(os.path.join(mods, 'tr8', 'pc-w', 'objectlist.txt'), 'rb').read())
    S = Src(mods)
    groups = []
    for r in [l.rstrip('\r\n').split('\t') for l in open(tsv, encoding='utf-8')][1:]:
        kids = [names.get(int(x.split(':')[0]), '?') for x in r[8].split()] if r[8] else []
        groups.append((r[1], secmap(S, [r[1]] + kids)))
    for u in arena:
        groups.append(('UNIT:' + u, secmap(S, [u])))
    if '--pair' in argv:
        # --pair A B (after --arena units): list the differing shared ids of one pair (types other than wave)
        k = argv.index('--pair'); a, b = argv[k + 1], argv[k + 2]
        G = dict(groups)
        A, B = G[a], G[b]
        diff = sorted(x for x in set(A) & set(B) if A[x] != B[x] and x[0] != 6)
        print('%s vs %s: %d differing shared ids (waves not listed): %s' % (
            a, b, len(diff), ' '.join('%s:%d' % (TYPES.get(t, t), i) for t, i in diff)))
        return
    print('pairs with differing shared ids (type: shared / differ):')
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            a, A = groups[i]; b, B = groups[j]
            shared = set(A) & set(B)
            if not shared:
                continue
            per = collections.defaultdict(lambda: [0, 0])
            for k in shared:
                per[k[0]][0] += 1
                per[k[0]][1] += A[k] != B[k]
            ndiff = sum(v[1] for v in per.values())
            print('%-34s %-34s shared %5d differ %5d  %s' % (a, b, len(shared), ndiff, ' '.join(
                '%s %d/%d' % (TYPES.get(t, t), v[0], v[1]) for t, v in sorted(per.items()))))


if __name__ == '__main__':
    main(sys.argv[1:])
