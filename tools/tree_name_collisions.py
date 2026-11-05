"""Which other trees under work/rebuild contain files of a given tree (same path below mods/, case-insensitive)?

For a tree that should stack order-independently on top of the others: every hit means the install order decides.
Per other tree: number of common paths, how many of them are byte-identical, the first few names. Trees whose name
contains 'test' are listed first (test trees = what the packages stack), the pipeline trees (stage*, asm_*, b138_*, ...)
after them.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tree_name_collisions.py work/rebuild/dlc_test51f_audio [--root work/rebuild]
"""
import sys, os, hashlib


def files(mods):
    out = {}
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            p = os.path.join(dp, f); out[os.path.relpath(p, mods).replace('\\', '/').lower()] = p
    return out


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def main(argv):
    root = 'work/rebuild'
    if '--root' in argv:
        k = argv.index('--root'); root = argv[k + 1]; del argv[k:k + 2]
    tree = os.path.normpath(argv[0]); mine = files(os.path.join(tree, 'mods'))
    print('tree %s: %d files' % (tree, len(mine)))
    hits = []
    for d in sorted(os.listdir(root)):
        t = os.path.normpath(os.path.join(root, d))
        if t == tree or not os.path.isdir(os.path.join(t, 'mods')): continue
        other = files(os.path.join(t, 'mods'))
        common = sorted(set(mine) & set(other))
        if common:
            same = sum(md5(mine[c]) == md5(other[c]) for c in common)
            hits.append((0 if 'test' in d else 1, d, common, same))
    for kind, d, common, same in sorted(hits):
        print('%-5s %-36s common %3d  byte-identical %3d  e.g. %s' % (
            'TEST' if kind == 0 else 'pipe', d, len(common), same, ', '.join(c.split('/')[-1] for c in common[:4])))
    print('test trees with common names: %d, other trees: %d' % (sum(h[0] == 0 for h in hits), sum(h[0] == 1 for h in hits)))


if __name__ == '__main__':
    main(sys.argv[1:])
