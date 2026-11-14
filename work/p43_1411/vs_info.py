r"""P4.3 (14.11.): shader-map entry of an Xbox lib (TB.SMAP), the PC surrogate's interpolator outputs, and the Xbox
VS interpolator table (tu_vs fetches) - what the 2057 PS needs from the VS.
Usage: ../bin/pyt -t 600 work/p43_1411/vs_info.py XVS PCVS"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_batch as TB, shaderlib as SL
from tu_light_transplant import F9, sm3asm, libs


def main(a):
    xv, pv = int(a[0]), int(a[1])
    print('SMAP[%d] = %s' % (xv, TB.SMAP.get(xv)))
    L = libs(); P = L['P']
    if pv in P:
        lib = P[pv]
        print('PC %d kind %s slots %s' % (pv, lib['kind'], lib['slots']))
        for o in sorted(set(s for s in lib['slots'] if s != 0xffffffff))[:1]:
            for i in F9.decode_pc(lib['entries'][o]['blob']).instrs():
                if i.op == 'dcl': print('   ', sm3asm.fmt_instr(i, 'vs'))
    print('Xbox libs with a base PC twin of the same VS? D has %s, X has %s' % (xv in L['D'], xv in L['X']))


if __name__ == '__main__':
    main(sys.argv[1:])
