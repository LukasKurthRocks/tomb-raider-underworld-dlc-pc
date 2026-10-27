"""Where does a rebuilt tree still differ from B138, and from which upstream step did those files come?

Joins the per-file section comparison (work/rebuild/sections_<label>.json, written by compare_sections.py) with the
origin column of docs/data/B90_gold_L4.manifest.tsv (derived:B43, mods_fix12, vm_mods_expected, ...). Per origin:
files, files fully identical, and identical / total sections per section type. Files not in the B90 manifest are
listed under 'after B90' (added between B90 and B138).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/rebuild_status.py [LABEL]      default label: stage2a
"""
import sys, os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, '..', 'work', 'rebuild')
TYPES = {0: 'general', 2: '2', 5: 'tex', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shader', 10: 'mat', 11: 'Obj',
         12: 'mesh', 13: '13'}


def main(argv):
    label = argv[0] if argv else 'stage2a'
    rep = json.load(open(os.path.join(W, 'sections_%s.json' % label)))
    origin = {}
    for l in open(os.path.join(HERE, '..', 'docs', 'data', 'B90_gold_L4.manifest.tsv'), encoding='utf8'):
        t = l.rstrip('\n').split('\t')
        if len(t) == 4 and t[0] != 'relpath': origin[t[0]] = t[3]
    groups = collections.defaultdict(lambda: {'files': 0, 'same': 0, 'st': collections.Counter(), 'worst': []})
    for rel, st in rep['files'].items():
        if 'error' in st: continue
        g = groups[origin.get(rel, 'after B90')]
        g['files'] += 1
        tot = sum(v for k, v in st.items() if k.endswith(' total'))
        same = sum(v for k, v in st.items() if k.endswith(' identical'))
        if tot and same == tot: g['same'] += 1
        g['st'].update(st)
        g['worst'].append((same / tot if tot else 1.0, rel))
    print('DRMs compared: %d (label %s)' % (len(rep['files']), label))
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]['files']):
        types = sorted({int(k.split()[0]) for k in g['st']})
        cells = []
        for t in types:
            n, i = g['st']['%d total' % t], g['st']['%d identical' % t]
            if n and i < n: cells.append('%s %d/%d' % (TYPES.get(t, t), i, n))
        print('\n%-26s files %3d, fully identical %3d' % (name, g['files'], g['same']))
        print('   differing types:', ', '.join(cells) or '-')
        worst = sorted(g['worst'])[:3]
        print('   furthest files:', ', '.join('%s %.0f%%' % (r, 100 * s) for s, r in worst))


if __name__ == '__main__':
    main(sys.argv[1:])
