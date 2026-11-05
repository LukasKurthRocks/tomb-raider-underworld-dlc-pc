"""Write TREE/md5.tsv (md5 TAB path relative to TREE/mods, the format of the other work/rebuild test trees) and print it
(writes only TREE/md5.tsv; agent N11, 2026-11-04).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tree_md5.py work/rebuild/dlc_test51g_costumes
"""
import sys, os, hashlib


def main(argv):
    if len(argv) != 1: sys.exit(__doc__)
    tree = argv[0]; mods = os.path.join(tree, 'mods')
    if not os.path.isdir(mods): sys.exit('no mods folder: %s' % mods)
    rows = []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            q = os.path.join(dp, f)
            rows.append((hashlib.md5(open(q, 'rb').read()).hexdigest(), os.path.relpath(q, mods).replace('\\', '/')))
    rows.sort(key=lambda r: r[1])
    with open(os.path.join(tree, 'md5.tsv'), 'w', encoding='utf-8', newline='\n') as h:
        h.write('md5\tpath\n')
        for m, p in rows: h.write('%s\t%s\n' % (m, p))
    for m, p in rows: print('%s  %s' % (m, p))
    print('wrote %s (%d files)' % (os.path.join(tree, 'md5.tsv'), len(rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
