"""Q105 (2026-11-12, group B): extract every base-game unit of the q105 TSV (list 'base', loadable) from the PC
archives to a folder (CDRM-decoded, read-only on the archives). pcpatch wins over pcbig (the engine mounts the patch
archive in front, ENGINE / README 0.21.10). Prints per unit the source and size; units in neither archive are listed.

Usage (from trudlcport): ../bin/pyt -t 900 work/b_nav_1211/q105_extract_units.py OUTDIR
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode

TSV = os.path.join(HERE, '..', 'q97_q105_1111', 'q105_units.tsv')


def main(out):
    os.makedirs(out, exist_ok=True)
    units = []
    for line in open(TSV, encoding='utf-8').read().splitlines()[1:]:
        f = line.split('\t')
        if f[0] == 'base' and f[3] == 'yes' and f[2] not in ('container', 'special'):
            units.append(f[1])
    arcs = []
    for src in ('pcpatch', 'pcbig'):
        path, e, pre = LC.SRC[src]
        arcs.append((src, Archive(path, e), e, pre))
    missing = []
    for u in units:
        for src, A, e, pre in arcs:
            recs = A.find(crc(pre + '\\' + u + '.drm'))
            if not recs: continue
            data = cdrm_decode(A.read(recs[-1]), e)
            open(os.path.join(out, u + '.drm'), 'wb').write(data)
            print('%-36s %-8s %9d' % (u, src, len(data)))
            break
        else:
            missing.append(u)
    print('%d units, %d extracted, missing: %s' % (len(units), len(units) - len(missing), ', '.join(missing) or '-'))


if __name__ == '__main__':
    main(sys.argv[1])
