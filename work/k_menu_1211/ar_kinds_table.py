"""Group K (TruMenu 0.22.33, arena.load / Q83): build the C rows of kArKinds from the Q83 catalog (read only).

Inputs (work/q83_allenemies_1111, written by enemy_catalog.py / enemy_deps.py on 2026-11-11):
  enemy_catalog.tsv  id, name, source, stored, decoded, tree, tree_name, b18, children, total_stored, total_decoded, ...
  enemy_deps.txt     "<id> <name>: <n> DRMs (<drm names>), ..." + one "  <drm> anim table <k> entries" line per DRM
Output: one C row per enemy kind
  {id, "name", part, tree, drms, anims, decodedMB, "child drm names"},
  part 0 base / 1 DLC 1 / 2 DLC 2 (source mods + name), anims = sum of the anim table entries of every DRM of the group
  (an upper bound of the new anim pool entries), decodedMB = total_decoded rounded up.

Usage (from trudlcport):  ../bin/pyt work/k_menu_1211/ar_kinds_table.py [OUT.txt]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
Q83 = os.path.join(HERE, '..', 'q83_allenemies_1111')


def main(argv):
    rows = {}
    with open(os.path.join(Q83, 'enemy_catalog.tsv'), encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            c = dict(zip(head, line.rstrip('\n').split('\t')))
            rows[int(c['id'])] = c
    deps = {}
    cur = None
    for line in open(os.path.join(Q83, 'enemy_deps.txt'), encoding='utf-8'):
        m = re.match(r'^(\d+) (\S+): (\d+) DRMs \(([^)]*)\)', line)
        if m:
            cur = int(m.group(1))
            deps[cur] = {'drms': m.group(4).split(), 'anims': 0}
            continue
        m = re.match(r'^\s+(\S+) anim table (\d+) entries', line)
        if m and cur is not None:
            deps[cur]['anims'] += int(m.group(2))
    out = []
    for oid in sorted(rows):
        c = rows[oid]
        d = deps.get(oid)
        if not d:
            print('no enemy_deps group for %d %s' % (oid, c['name']), file=sys.stderr)
            return 1
        name = c['name']
        part = 0
        if c['source'] == 'mods':
            part = 1 if name.startswith('knight') else 2
        mb = (int(c['total_decoded']) + (1 << 20) - 1) >> 20
        children = ' '.join(d['drms'][1:])
        out.append('    {%d, "%s", %d, %s, %d, %d, %d, "%s"},' % (oid, name, part, c['tree'], len(d['drms']), d['anims'],
                                                               mb, children))
    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if len(argv) > 0:
        with open(argv[0], 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print('%d kinds' % len(out), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
