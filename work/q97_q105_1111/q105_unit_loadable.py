"""Q105 (read-only): every unit of the unit lists (PC base + DLC tree) and whether a DRM for it exists in an archive
(PC bigfile / patch, Xbox layers / TU / packs via tools/locals.py sources) or in the pipeline tree's mods folders.
Usage: ../bin/pyt work/q97_q105_1111/q105_unit_loadable.py TREE OUT.tsv
Columns: list, unit, area, loadable_pc (pc archive or tree mods), sources
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import locals as LC
from archive import Archive
from names import crc

tree, out = sys.argv[1], sys.argv[2]
lists = [('base', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'generic', 'lists', 'pc_unitlist.txt'))]
for d in ('dlc1', 'dlc2'):
    lists.append((d, os.path.join(tree, d, 'mods', 'tr8', 'pc-w', 'unitlist.txt')))
arch = {}
for src, (path, e, pre) in LC.SRC.items():
    if not os.path.exists(path): continue
    try: arch[src] = (Archive(path, e), pre)
    except Exception as ex: print('skip %s: %s' % (src, ex))
print('archives:', ', '.join(arch))
mods = {}
for d in ('dlc1', 'dlc2'):
    p = os.path.join(tree, d, 'mods')
    mods[d] = set(f.lower() for f in os.listdir(p) if f.endswith('.drm'))
rows = []
for lname, path in lists:
    lines = [l.strip() for l in open(path, encoding='latin-1') if l.strip()]
    for l in lines[1:]:
        unit = l.split('\\')[-1]
        area = l.split('\\')[-2] if '\\' in l else ''
        n = unit + '.drm'
        found = [src for src, (A, pre) in arch.items() if A.find(crc(pre + '\\' + n))]
        found += ['tree_' + d for d in mods if n.lower() in mods[d]]
        pc = any(s.startswith('pc') or s.startswith('tree_') for s in found)
        rows.append((lname, unit, area, 'yes' if pc else 'NO', ','.join(found) or 'nowhere'))
with open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write('list\tunit\tarea\tloadable_pc\tsources\n')
    for r in rows: f.write('\t'.join(r) + '\n')
print('rows', len(rows), 'not loadable', sum(1 for r in rows if r[3] == 'NO'))
