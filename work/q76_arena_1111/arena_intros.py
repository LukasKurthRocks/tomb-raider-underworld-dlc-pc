"""Q76 test arena: enemy / generator / checkpoint intros of candidate units with live positions (read-only).

Usage (from the repository root):
  ../bin/pyt -t 900 work/q76_arena_1111/arena_intros.py SIDE UNIT.drm [UNIT.drm ...]
    SIDE = pc (PC bigfile, base units) / inst (installed mods\\ copy, DLC units) - as work/endb270_0811/unit_dtp.py load()
Prints per intro whose object name is an enemy, a generator or a checkpoint: intro index, object id + name, unique id,
data position (intro +0x10) and live position (data - Level+0x80, ENGINE.md 4.3; valid when the unit is Lara's own unit),
then per unit the z range of those intros and the x / y box of the enemy + generator intros.
Object names: the installed merged objectlist (PC base ids 1..821 + DLC ids).
"""
import sys, os, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'endb270_0811'))
import unit_dtp as UD
import base_twin as BT

KEEP = re.compile(r'thrall|merc|tiger|panther|spider|tarantula|yeti|shark|bat_enemy|generator|checkpoint|amanda|natla_end')
DROP = re.compile(r'chunkdoll|^co_|^ar_|^ms_|^fx_|lying|extension|lara_mom')


def names():
    p = os.path.join(BT.GAME, 'tr8', 'pc-w', 'objectlist.txt')
    d = {}
    for l in open(p, 'rb').read().decode('latin1').split('\r\n')[1:]:
        if l:
            a, s = l.split(',', 1); d[int(a)] = s
    return d


def main(argv):
    side, units = argv[0], argv[1:]
    N = names()
    for rel in units:
        d, e = UD.load(side, rel)
        S, u, ptr = UD.unit(d, e)
        off = struct.unpack_from('<3f', S[0]['data'], 0x80)
        print('== %s (%s): Level+0x80 = %.1f %.1f %.1f' % (rel, side, off[0], off[1], off[2]))
        zs, box = [], [1e9, 1e9, -1e9, -1e9]
        for it in UD.intros(u, ptr, e):
            nm = N.get(it['obj'], '?%d' % it['obj'])
            if not KEEP.search(nm) or DROP.search(nm): continue
            x, y, z = struct.unpack_from('<3f', u['data'], it['o'] + 0x10)
            lx, ly, lz = x - off[0], y - off[1], z - off[2]
            print('  #%-4d %4d %-44s uid %-6d data %9.1f %9.1f %9.1f  live %9.1f %9.1f %9.1f' %
                  (it['k'], it['obj'], nm, it['uid'], x, y, z, lx, ly, lz))
            zs.append(lz)
            if 'checkpoint' not in nm:
                box = [min(box[0], lx), min(box[1], ly), max(box[2], lx), max(box[3], ly)]
        if zs:
            print('  live z range %.1f .. %.1f; enemy / generator x %.0f .. %.0f, y %.0f .. %.0f (%.0f x %.0f units)' %
                  (min(zs), max(zs), box[0], box[2], box[1], box[3], box[2] - box[0], box[3] - box[1]))


if __name__ == '__main__':
    main(sys.argv[1:])
