"""P1 (2026-11-13, Mediterranean objects): extract named object DRMs from the PC archives (read-only on the archives).

pcpatch wins over pcbig (as work/b_nav_1211/q105_extract_units.py). Object DRMs sit next to the units as
<prefix>\\<object>.drm. Names come from the command line or from a file (one name per line, '#' comments).

Usage (from trudlcport): ../bin/pyt -t 900 work/p1_med_1311/p1_extract_objects.py OUTDIR NAME [NAME ...] | @LISTFILE
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode


def main(out, names):
    os.makedirs(out, exist_ok=True)
    arcs = []
    for src in ('pcpatch', 'pcbig'):
        path, e, pre = LC.SRC[src]
        arcs.append((src, Archive(path, e), e, pre))
    missing = []
    for n in names:
        for src, A, e, pre in arcs:
            recs = A.find(crc(pre + '\\' + n + '.drm'))
            if not recs:
                continue
            data = cdrm_decode(A.read(recs[-1]), e)
            open(os.path.join(out, n + '.drm'), 'wb').write(data)
            print('%-44s %-8s %9d' % (n, src, len(data)))
            break
        else:
            missing.append(n)
    print('%d names, %d extracted, missing: %s' % (len(names), len(names) - len(missing), ', '.join(missing) or '-'))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    nm = []
    for a in sys.argv[2:]:
        if a.startswith('@'):
            for ln in open(a[1:], encoding='utf-8'):
                ln = ln.split('#')[0].strip()
                if ln: nm.append(ln)
        else:
            nm.append(a)
    sys.exit(main(sys.argv[1], nm))
