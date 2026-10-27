"""Compare a mods/ tree with the B138 release manifest, file by file (MD5).

Statuses: identical / different (same path, other MD5) / missing (in B138, not in the tree) / extra (in the tree,
not in B138). Printed per top folder, the report (every file) goes to work/rebuild/compare_<label>.json.
The manifest is the release kit's manifest.json (its 'files' list: rel, md5; 'extra' entries such as tru.exe are not
part of the mods tree and are ignored).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/compare_b138.py MODS_DIR [LABEL] [--manifest PATH]
  default manifest: ../release/B138/kit/manifest.json
"""
import sys, os, json, hashlib, collections

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def main(argv):
    manifest = '../release/B138/kit/manifest.json'
    if '--manifest' in argv:
        i = argv.index('--manifest'); manifest = argv[i + 1]; del argv[i:i + 2]
    tree = argv[0]
    label = argv[1] if len(argv) > 1 else os.path.basename(os.path.normpath(os.path.join(tree, '..')))
    want = {f['rel'].replace('\\', '/').lower(): f for f in json.load(open(manifest))['files']}
    have = {}
    for dp, dn, fn in os.walk(tree):
        for f in fn:
            p = os.path.join(dp, f)
            have[os.path.relpath(p, tree).replace('\\', '/').lower()] = p
    rows, st = [], collections.defaultdict(collections.Counter)
    for rel in sorted(set(want) | set(have)):
        top = rel.split('/')[0] if '/' in rel else '.'
        if rel not in have: s = 'missing'
        elif rel not in want: s = 'extra'
        else: s = 'identical' if md5_of(have[rel]) == want[rel]['md5'] else 'different'
        st[top][s] += 1
        rows.append(dict(rel=rel, status=s))
    os.makedirs(W, exist_ok=True)
    out = os.path.join(W, 'compare_%s.json' % label)
    json.dump(rows, open(out, 'w'), indent=0)
    total = collections.Counter()
    for top in sorted(st):
        total.update(st[top])
        print('%-14s %s' % (top, dict(st[top])))
    print('TOTAL          %s  (B138 files: %d)' % (dict(total), len(want)))
    print('report', out)


if __name__ == '__main__':
    main(sys.argv[1:])
