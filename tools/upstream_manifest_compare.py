"""Compare the upstream author's release kit manifests (md5 of every file his installer writes) with what one of our
test profiles installs. Read-only; writes only the report files given by --out.

Our view of a file = the last tree of the profile (`trees[].source`, in install order) that has the file, otherwise
the file in --mods (the game folder the trees are installed on top of, e.g. ../data/pc/mods), otherwise the B138 kit
manifest (what the B138 installer wrote). Paths compared case-insensitively
with '/' separators, relative to the game's mods folder.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/upstream_manifest_compare.py --new work/upstream/B270_acqua.kit_manifest.json
        --base ../release/B138/kit/manifest.json --profile tests/profiles/paket01_yggdrasil.json
        [--profile2 tests/profiles/paket04b_shader_thrall.json] --out work/upstream/compare_B270_paket01
Classes per file:
  same_untouched   B270 = B138 = ours (nobody changed it)
  same_both        B270 = ours, both differ from B138 (both made the same change)
  upstream_only    B270 changed it, ours = B138 (a fix / change he has and we do not)
  ours_only        ours changed it, B270 = B138 (a change only we made)
  both_differ      both changed it, differently
  new_same         not in B138, B270 = ours
  new_differ       not in B138, B270 != ours
  missing_ours     in B270, we install nothing and B138 has nothing
  missing_upstream we install it, B270 has no such file
Output: <out>.tsv (one row per file) and <out>.md (counts per class and per area, lists for the interesting classes).
"""
import sys, os, json, hashlib
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))      # workspace (profiles use paths below it)


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def norm(rel):
    return rel.replace('\\', '/').strip('/').lower()


def manifest(path):
    d = json.load(open(path, encoding='utf-8'))
    return d.get('build', '?'), {norm(f['rel']): f for f in d['files']}


def md5f(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def profile_view(path):
    """rel -> (tree label, absolute file path) of the last tree that has it"""
    prof = json.load(open(path, encoding='utf-8-sig'))
    view = {}
    for t in prof.get('trees', []):
        src = t.get('source')
        if not src: continue
        d = os.path.join(ROOT, src.replace('/', os.sep))
        if not os.path.isdir(d): print('missing tree', d); continue
        label = src.replace('trudlcport/work/rebuild/', '').replace('/mods', '')
        for base, _, files in os.walk(d):
            for fn in files:
                p = os.path.join(base, fn)
                rel = norm(os.path.relpath(p, d))
                if rel in ('md5.tsv', 'bases.tsv'): continue
                view[rel] = (label, p)
    return view


def area(rel):
    if '/' not in rel: return 'drm (root)' if rel.endswith('.drm') else 'root other'
    return rel.split('/')[0]


def main(argv):
    new_path = arg(argv, '--new'); base_path = arg(argv, '--base')
    prof = arg(argv, '--profile'); prof2 = arg(argv, '--profile2'); out = arg(argv, '--out')
    mods = arg(argv, '--mods')               # optional: game mods folder as base below the trees (else B138 manifest)
    nb, new = manifest(new_path); bb, base = manifest(base_path)
    view = profile_view(prof)
    if prof2:
        for rel, v in profile_view(prof2).items():
            if rel not in view or v[0] != view[rel][0]: view.setdefault(rel, v)   # first profile wins; adds files only prof2 has
    rows, cnt, per = [], Counter(), defaultdict(Counter)
    lists = defaultdict(list)
    md5cache = {}
    for rel in sorted(set(new) | set(view)):
        n = new.get(rel); b = base.get(rel)
        if rel in view:
            lab, p = view[rel]
            if p not in md5cache: md5cache[p] = md5f(p)
            o, src = md5cache[p], lab
        elif mods and os.path.isfile(os.path.join(mods, rel)):
            p = os.path.join(mods, rel)          # the game folder the profile's trees go on top of
            if p not in md5cache: md5cache[p] = md5f(p)
            o, src = md5cache[p], 'game folder'
        elif b is not None:
            o, src = b['md5'], 'B138 (base)'
        else:
            o, src = None, '-'
        nm = n['md5'] if n else None; bm = b['md5'] if b else None
        if nm is None: c = 'missing_upstream'
        elif o is None: c = 'missing_ours'
        elif bm is None: c = 'new_same' if nm == o else 'new_differ'
        elif nm == bm and o == bm: c = 'same_untouched'
        elif nm == o: c = 'same_both'
        elif o == bm: c = 'upstream_only'
        elif nm == bm: c = 'ours_only'
        else: c = 'both_differ'
        cnt[c] += 1; per[area(rel)][c] += 1
        dlc = n.get('dlc', '') if n else ''
        rows.append('\t'.join([rel, c, dlc, src, o or '-', nm or '-', bm or '-']))
        lists[c].append((rel, dlc, src))
    with open(out + '.tsv', 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('rel\tclass\tdlc\tour_source\tmd5_ours\tmd5_%s\tmd5_%s\n' % (nb, bb))
        f.write('\n'.join(rows) + '\n')
    order = ['same_untouched', 'same_both', 'new_same', 'upstream_only', 'ours_only', 'both_differ', 'new_differ',
             'missing_ours', 'missing_upstream']
    md = ['# Upstream %s vs. our profile %s (+ %s)' % (nb, os.path.basename(prof), os.path.basename(prof2) if prof2 else '-'),
          '', 'Base: %s. Generated by `tools/upstream_manifest_compare.py`.' % bb, '',
          '| class | files |', '|---|---|'] + ['| %s | %d |' % (c, cnt[c]) for c in order] + ['', '| area | ' + ' | '.join(order) + ' |',
          '|---|' + '---|' * len(order)]
    for a in sorted(per):
        md.append('| %s | ' % a + ' | '.join(str(per[a][c]) for c in order) + ' |')
    for c in ('upstream_only', 'both_differ', 'new_differ', 'missing_ours', 'missing_upstream', 'ours_only'):
        md += ['', '## %s (%d)' % (c, cnt[c]), '']
        md += ['- `%s` (%s, ours: %s)' % (r, d or '-', s) for r, d, s in lists[c][:400]]
    with open(out + '.md', 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(md) + '\n')
    print('\n'.join(md[:14 + len(per) + 2]))
    print('written', out + '.tsv', out + '.md')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or '--new' not in a: print(__doc__); sys.exit(2)
    main(a)
