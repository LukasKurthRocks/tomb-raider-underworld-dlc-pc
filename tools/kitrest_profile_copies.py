"""Which copy (md5, supplying tree) of given files each test profile installs (read-only; kit-rest tasks 2 / 3,
workspace docs Befund-Kit-Reste-0511.md). Replays the install order with tools/profile_fix_plan.py (install /
tree_files / base_files, used read-only; --base-undo as there). Groups the profiles by the md5 tuple.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/kitrest_profile_copies.py --profile "tests/profiles/*.json" --base GAME/mods
        [--base-undo STATE.json] NAME.drm [NAME.drm ...]   (names relative to mods, e.g. cinstream/pdlc1_010_intro.drm)
"""
import sys, os, glob, json, io, contextlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_fix_plan as PFP
import profile_last_source as PLS


def main(a):
    profiles = []
    while '--profile' in a:
        k = a.index('--profile'); profiles += sorted(glob.glob(a[k + 1])) or [a[k + 1]]; del a[k:k + 2]
    base = None
    if '--base' in a: k = a.index('--base'); base = a[k + 1]; del a[k:k + 2]
    if '--base-undo' in a: k = a.index('--base-undo'); PFP.BASE_UNDO = a[k + 1]; del a[k:k + 2]
    names = [n.replace('\\', '/').lower() for n in a]
    groups = collections.defaultdict(list)
    for pp in profiles:
        prof = json.load(open(pp, encoding='utf-8-sig'))
        trees = []
        for t in prof.get('trees') or []:
            if not t: continue
            src = PLS.resolve(t['source'])
            seg = t['source'].replace('\\', '/').rstrip('/').split('/')
            label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
            trees.append((label, PFP.tree_files(src, t.get('exclude'))))
        files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fin = PFP.install(trees, files, base)
        if buf.getvalue().strip(): print(buf.getvalue().strip())
        key = tuple((n, PFP.md5(fin[n][0]) if n in fin else '-', fin[n][1] if n in fin else '-') for n in names)
        groups[key].append(os.path.basename(pp)[:-5])
    for i, (key, ps) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        print('\nGROUP %d: %d profile(s): %s' % (i + 1, len(ps), ', '.join(ps)))
        for n, m, lab in key:
            print('  %-44s %s  from %s' % (n, m, lab))


if __name__ == '__main__':
    main(sys.argv[1:])
