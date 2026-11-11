"""Q83: navigation data of units (read-only): does the unit carry a NavPower image (Level+0x60) and a 3D NavPower image
(Level+0x68, ENGINE.md 4.1), and how many classic markup records (Level+8 / +0xc)?

Volumetric enemies (behaviour tree 2 CreatureVolumetric: bat_enemy, sharks) move in 3D; the other kinds walk on the
2D navgraph of the unit they stand in. This prints, per unit, whether the pointers are set (relocation present) and
the first words behind them.

Usage (from the repository root):
  ../bin/pyt -t 600 work/q83_allenemies_1111/unit_nav.py MODS_DIR UNIT [UNIT ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R
from enemy_catalog import Src


def main(argv):
    S = Src(argv[0])
    for u in argv[1:]:
        g = S.get(u)
        if g is None:
            print('%-28s no DRM' % u); continue
        D = DW.read(g[2], 'le')
        lv = D.sections[0]
        rr = R.parse(bytes(lv.reloc), 'le')
        it = {o: (0, t) for o, t in rr.internal}
        it.update({s: (si, dd) for si, s, dd in rr.external})
        d = lv.data
        def words(off, n=3):
            if off not in it:
                return 'null'
            si, a = it[off]
            dd = D.sections[si].data
            return '-> sec#%d (type %d id %d, %d B) +0x%x: %s' % (
                si, D.sections[si].type, D.sections[si].id, len(dd), a,
                ' '.join('%08x' % struct.unpack_from('<I', dd, a + 4 * i)[0] for i in range(n) if a + 4 * i + 4 <= len(dd)))
        mk = struct.unpack_from('<I', d, 8)[0]
        print('%-28s [%s] Level sec id %d size %d | nav +0x60 %s | nav3d +0x68 %s | markup count +8 = %d' % (
            u, g[0], lv.id, len(d), words(0x60), words(0x68), mk))


if __name__ == '__main__':
    main(sys.argv[1:])
