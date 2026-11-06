"""Where do the bytes of one section come from? (read-only; 2026-11-05, docs Befund-Navmesh-Kombi-0511.md)

For a DRM name and a list of trees: md5 of the whole file and of the chosen sections (DTP type 7 by id, all copies of
the id in file order) per tree, and which trees share each section md5 - e.g. whether the thrall chart DTP 24536 of a
test tree carries the bytes of a pipeline tree with or without the step `statechart`.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/dtp_lineage.py NAME.drm TREE[,TREE...] [--ids 24536,24392] [--type 7]
        TREE: a folder (its mods sub folder is used when present) or a .drm path; without --ids every section of the
        given --type (default 7) that differs between at least two trees is listed
"""
import sys, os, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def find(tree, name):
    if tree.lower().endswith('.drm'): return tree if os.path.isfile(tree) else None
    root = os.path.join(tree, 'mods') if os.path.isdir(os.path.join(tree, 'mods')) else tree
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.lower() == name.lower(): return os.path.join(r, f)
    return None


def md5(b):
    return hashlib.md5(b).hexdigest()


def main(a):
    ids = None; typ = 7
    if '--ids' in a: k = a.index('--ids'); ids = [int(x) for x in a[k + 1].split(',')]; del a[k:k + 2]
    if '--type' in a: k = a.index('--type'); typ = int(a[k + 1]); del a[k:k + 2]
    if len(a) != 2: sys.exit(__doc__)
    name, trees = a[0], a[1].split(',')
    per = collections.OrderedDict()
    for t in trees:
        p = find(t, name)
        if p is None: print('%-60s (no %s)' % (t, name)); continue
        raw = open(p, 'rb').read()
        D = DW.read(raw, 'le')
        secs = collections.defaultdict(list)
        for s in D.sections:
            if s.type == typ: secs[s.id].append(md5(bytes(s.data)) + ('+r' + md5(bytes(s.reloc))[:6]))
        per[t] = (md5(raw), len(raw), secs)
        print('%-60s file md5 %s (%d bytes, %d sections)' % (t, md5(raw), len(raw), len(D.sections)))
    if not per: return 1
    allids = sorted(set(i for v in per.values() for i in v[2]))
    show = ids if ids else [i for i in allids if len(set(tuple(v[2].get(i, ())) for v in per.values())) > 1]
    for i in show:
        print('type %d id %d:' % (typ, i))
        groups = collections.OrderedDict()
        for t, (fm, n, secs) in per.items():
            groups.setdefault(tuple(secs.get(i, ())), []).append(t)
        for k, (sig, ts) in enumerate(groups.items()):
            print('   variant %d %s: %s' % (k + 1, ' / '.join(x[:12] for x in sig) or '(absent)', ', '.join(
                os.path.basename(os.path.normpath(x)) if not x.endswith('mods') else os.path.basename(os.path.dirname(os.path.normpath(x)))
                for x in ts)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
