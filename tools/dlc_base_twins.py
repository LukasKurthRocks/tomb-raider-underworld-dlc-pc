"""List DLC objects that have a base-game twin by name (read-only; finding 43, "base material for variant objects":
the DLC 1 grapple ring `dlc1_ei_grapple_wall` renders right with the material of the base `ar_ei_grapple_wall`).
A DLC name loses its `dlc1_` / `dlc2_` / `dlc_` prefix; a base PC DRM is a twin when its name, after a level prefix
(`ar_`, `ca_`, `l1_` ...), equals that rest, or equals it outright. Candidates only - the shader / texture-role check
per material is tools/shader_peer_report.py, the swap tools/material_transplant.py.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/dlc_base_twins.py [pack10|pack11]
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from names import L as NAME_DIR

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_names.txt')


def main(argv):
    only = argv[0] if argv else None
    dlc = []
    for l in open(W, encoding='utf8', errors='ignore'):
        p = l.split()
        if len(p) >= 6 and p[4] == 'drm' and (only is None or p[1] == only):
            n = p[5].split('\\')[-1]
            if '\\streamgroups\\' not in p[5]: dlc.append((p[1], n))
    base = collections.defaultdict(list)
    for l in open(NAME_DIR + 'Tomb Raider Underworld (PC).txt', encoding='utf8', errors='ignore'):
        l = l.strip()
        if not l.startswith('pc-w\\') or not l.endswith('.drm') or l.count('\\') != 1: continue
        n = l.split('\\')[1]
        if n.startswith('dlc'): continue
        base[n].append(n)
        m = re.match(r'^[a-z0-9]{2,3}_(.+)$', n)
        if m: base[m.group(1)].append(n)
    hits = 0
    for pack, n in sorted(set(dlc)):
        rest = re.sub(r'^dlc[12]?_', '', n)
        tw = sorted(set(base.get(rest, [])))
        if tw:
            hits += 1
            print('%-7s %-40s %s' % (pack, n, ', '.join(tw[:6]) + (' ...' if len(tw) > 6 else '')))
    print('%d of %d DLC DRMs have a base twin by name' % (hits, len(set(dlc))))


if __name__ == '__main__':
    main(sys.argv[1:])
