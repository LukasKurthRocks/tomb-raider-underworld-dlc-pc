r"""P4.3 (14.11.): for a VS lib (D = DLC Xbox, X = base Xbox) list every occupied slot with its vertex elements and
the interpolators the tu_vs translation writes (dcl o*), to find which slots export COLOR0.
Usage: ../bin/pyt -t 900 work/p43_1411/vs_slots.py D|X LIB"""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_vs as TV
from tu_light_transplant import libs


def main(a):
    which, lid = a[0], int(a[1])
    lib = libs()[which][lid]
    occ = [(k, o) for k, o in enumerate(lib['slots']) if o != 0xffffffff]
    print('%s %d: %d slots, %d occupied, %d distinct entries' % (which, lid, len(lib['slots']), len(occ), len({o for k, o in occ})))
    seen = {}
    for k, o in occ:
        if o in seen: continue
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf): TV.main(['show', which, str(lid), str(k)])
        except SystemExit: pass
        except Exception as e: buf.write('ERROR %s %s' % (type(e).__name__, e))
        txt = buf.getvalue()
        d = [l.strip() for l in txt.splitlines() if l.strip().startswith('dcl_') or 'ERROR' in l]
        seen[o] = k
        print('slot %3d entry %6d: %s' % (k, o, ' | '.join(d)))


if __name__ == '__main__':
    main(sys.argv[1:])
