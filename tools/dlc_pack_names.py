"""DRM names of the decoded DLC packs (work/generic/dlc_drms.pkl) compared with a converted mods tree and with the
merged object list (read-only): which pack DRMs the tree lacks, and which object-list entries have no DRM in the
pack nor in the tree. Finding 43 follow-up (DLC 2 rock vein: is an object of the level missing from the tree?).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dlc_pack_names.py MODS_DIR [--pack ack11.000] [--grep TEXT]
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def main(argv):
    pack = 'ack11.000'; grep = None
    if '--pack' in argv: k = argv.index('--pack'); pack = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    if '--grep' in argv: k = argv.index('--grep'); grep = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    mods = argv[0]
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    names = sorted({base(k[1]) for k in C if k[0] == pack})
    tree = {os.path.splitext(f)[0].lower() for r, _, fs in os.walk(mods) for f in fs if f.endswith('.drm')}
    if grep:
        for n in names:
            if grep in n: print('pack %-50s tree %s' % (n, 'yes' if n in tree else 'NO'))
        return
    miss = [n for n in names if n not in tree and not n.startswith('0x')]
    print('%s: %d DRMs, %d not in the tree: %s' % (pack, len(names), len(miss), ' '.join(miss[:80])))
    ol = os.path.join(mods, 'tr8', 'pc-w', 'objectlist.txt')
    if os.path.exists(ol):
        objs = [l.split(',', 1)[1].strip().lower() for l in open(ol, encoding='latin-1').read().splitlines()[1:] if ',' in l]
        inpack = set(names)
        lost = [o for o in objs if o in inpack and o not in tree]
        print('object-list entries in this pack but not in the tree: %d %s' % (len(lost), ' '.join(lost)))


if __name__ == '__main__':
    main(sys.argv[1:])
