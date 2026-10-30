"""Occupied permutation slots of a ShaderLib (type 9): Xbox library vs its PC counterpart (read-only). A vertex-shader
library has 256 slots, one per vertex-format variant; the PC port may lack variants the base game never used.
Finding 43 follow-up: the DLC 2 waterfall (material 24920, base eitr water surface 820-822 -> PC 1593-1595) is the
only user of that material with a vertex COLOUR element - does PC 1595 have the slot that variant selects?

Usage (from the repository root):
  ../bin/pyt -t 120 tools/shader_slots_compare.py XBOX.drm XBOX_LIB_ID PC.drm PC_LIB_ID
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
from shaderlib import parse


def slots(path, lid, e):
    D = DW.read(open(path, 'rb').read(), e)
    s = next(x for x in D.sections if x.type == 9 and x.id == lid)
    lib = parse(s.data, e)
    return lib['kind'], [i for i, o in enumerate(lib['slots']) if o != 0xffffffff], len(lib['slots'])


def main(argv):
    kx, sx, nx = slots(argv[0], int(argv[1]), 'be')
    kp, sp, np_ = slots(argv[2], int(argv[3]), 'le')
    print('xbox lib %s: kind %d, %d of %d slots occupied: %s' % (argv[1], kx, len(sx), nx, sx))
    print('pc   lib %s: kind %d, %d of %d slots occupied: %s' % (argv[3], kp, len(sp), np_, sp))
    print('only on xbox: %s' % sorted(set(sx) - set(sp)))
    print('only on pc:   %s' % sorted(set(sp) - set(sx)))


if __name__ == '__main__':
    main(sys.argv[1:])
