"""Q89 design aid: proposed bone mapping target figure -> Lara anim skeleton (113), read only.

Top-down greedy tree matching: root -> root; for every matched pair (t, s) the children of t are matched to the
children of s by the smallest distance of their bind offsets (segment +0x20..+0x28, relative to the parent), each
offset divided by the figure's hip height (|offset of bone 1|) so a 6 m yeti and Lara compare. A pair is accepted
when the normalised distance is below --tol (default 0.12) - else the target child stays unmapped and its subtree is
still searched below the nearest mapped ancestor's source children. Unmapped target bones keep their bind pose in the
plugin design; Lara bones without a target are dropped (their attachments go to the nearest mapped ancestor).

Usage (from the repository root):
  ../bin/pyt -t 1800 work/q89_skeleton_1111/skeleton_map.py MODS_DIR TARGET [TARGET ...] [--tol 0.12] [--table]
Prints per target: mapped count, unmapped target bones, Lara bones without a target, and with --table the map.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'q83_allenemies_1111'))
sys.path.insert(0, HERE)
import drm_write as DW
from enemy_catalog import Src
from skeleton_compare import models


def skel(S, name, want=None):
    g = S.get(name)
    if g is None:
        return None
    ms = models(DW.read(g[2], 'le'))
    if want:
        ms = [m for m in ms if m['n'] == want] or ms
    m = max(ms, key=lambda x: x['n']) if not want else ms[0]
    par = [s['parent'] for s in m['segs']]
    off = [s['f'][8:11] for s in m['segs']]
    return m['id'], par, off


def children(par):
    ch = {i: [] for i in range(len(par))}
    for i, p in enumerate(par):
        if p >= 0:
            ch[p].append(i)
    return ch


def norm(off):
    h = sum(x * x for x in off[1]) ** 0.5 if len(off) > 1 else 1.0
    return [tuple(x / (h or 1.0) for x in o) for o in off]


def match(src, tgt, tol):
    _, sp, so = src
    _, tp, to = tgt
    so, to = norm(so), norm(to)
    sc, tc = children(sp), children(tp)
    mp = {0: 0}
    queue = [(0, 0)]
    while queue:
        t, s = queue.pop(0)
        cand = []
        for a in tc[t]:
            for b in sc[s]:
                d = sum((to[a][k] - so[b][k]) ** 2 for k in range(3)) ** 0.5
                cand.append((d, a, b))
        cand.sort()
        used_a, used_b = set(), set(mp.values())
        for d, a, b in cand:
            if a in used_a or b in used_b or d > tol:
                continue
            mp[a] = b
            used_a.add(a); used_b.add(b)
            queue.append((a, b))
        for a in tc[t]:
            if a not in used_a:
                # unmapped target child: search its children against s's children (skip one level)
                for a2 in tc[a]:
                    best = None
                    for b in sc[s]:
                        if b in used_b:
                            continue
                        d = sum((to[a2][k] - so[b][k]) ** 2 for k in range(3)) ** 0.5
                        if d <= tol and (best is None or d < best[0]):
                            best = (d, b)
                    if best:
                        mp[a2] = best[1]; used_b.add(best[1]); queue.append((a2, best[1]))
    return mp


def main(argv):
    S = Src(argv[0])
    tol = float(argv[argv.index('--tol') + 1]) if '--tol' in argv else 0.12
    skip = set()
    if '--tol' in argv:
        skip.add(argv[argv.index('--tol') + 1])
    lara = skel(S, 'lara_casual', 113)
    for nm in [x for x in argv[1:] if not x.startswith('--') and x not in skip]:
        t = skel(S, nm)
        if t is None:
            print('%s: no DRM' % nm); continue
        mp = match(lara, t, tol)
        nt = len(t[1])
        unm = [i for i in range(nt) if i not in mp]
        lost = [b for b in range(len(lara[1])) if b not in mp.values()]
        same = sum(1 for a, b in mp.items() if a == b)
        print('%-22s model %d: %d bones, mapped %d (index-equal %d), target unmapped %d, Lara bones without target %d' % (
            nm, t[0], nt, len(mp), same, len(unm), len(lost)))
        print('   unmapped target: %s' % unm)
        print('   Lara without target: %s' % lost)
        if '--table' in argv:
            print('   map target:lara ' + ' '.join('%d:%d' % kv for kv in sorted(mp.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
