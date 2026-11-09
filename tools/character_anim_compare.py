"""Compare two character_anim_report.py --json outputs (PC vs Xbox), read only (N22 stage 1).
Per label: skeleton segment counts / parent lists, anim table (section ids), per-anim frames / segment counts, melee
record anim refs - equal or the first differences. Usage: ../bin/pyt tools/character_anim_compare.py PC.json XBOX.json
Exit 0 = all equal, 1 = differences."""
import sys, json
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
bad = 0
for k in sorted(set(a) & set(b)):
    x, y = a[k], b[k]
    if 'error' in x or 'error' in y:
        print(k, 'error', x.get('error'), y.get('error')); bad += 1; continue
    r = []
    sx = [(s['segments'], tuple(s['parents'])) for s in x['skeletons']]
    sy = [(s['segments'], tuple(s['parents'])) for s in y['skeletons']]
    r.append('skeletons ' + ('equal' if sx == sy else 'DIFFER %s / %s' % ([s[0] for s in sx], [s[0] for s in sy])))
    r.append('anim table ' + ('equal (%d)' % len(x['anims']) if x['anims'] == y['anims'] else 'DIFFER (%d / %d, first %s)' % (
        len(x['anims']), len(y['anims']), next(((i, p, q) for i, (p, q) in enumerate(zip(x['anims'], y['anims'])) if p != q), None))))
    ax, ay = x['anim_sections'], y['anim_sections']
    dif = [i for i in ax if i in ay and (ax[i]['frames'], ax[i]['segments']) != (ay[i]['frames'], ay[i]['segments'])]
    r.append('anim headers frames/segments ' + ('equal (%d)' % len(set(ax) & set(ay)) if not dif else 'DIFFER %d e.g. %s' % (len(dif), dif[:3])))
    mx = [(m['slot'], m['tune'], [tuple(q) for q in m['refs']]) for m in x['melee']]
    my = [(m['slot'], m['tune'], [tuple(q) for q in m['refs']]) for m in y['melee']]
    r.append('melee refs ' + ('equal (%d)' % len(mx) if mx == my else 'DIFFER'))
    if any('DIFFER' in t for t in r): bad += 1
    print('%-14s %s' % (k, ' | '.join(r)))
sys.exit(1 if bad else 0)
