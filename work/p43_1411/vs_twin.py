r"""P4.3 (14.11.): base Xbox VS libs whose PC twin (TLT.x2p) is PCVS - the xbase argument of tu_vs.py vsmerge.
Usage: ../bin/pyt -t 600 work/p43_1411/vs_twin.py PCVS"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_light_transplant as TLT


def main(a):
    pv = int(a[0])
    xs = sorted(x for x, p in TLT.x2p().items() if p == pv)
    print('PC %d <- base Xbox %s' % (pv, xs))


if __name__ == '__main__':
    main(sys.argv[1:])
