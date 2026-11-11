"""Q74 (2026-11-11): compare unit / object DRMs of the Japanese retail DVD bigfile (build 0685.1 era, data 1.0, read-only
in input/jp-dvd/Game_Files) with the Steam PC bigfile.000 (+ patch.000 = 1.1): is any unit of the dead-end sites
different between the retail disc and Steam (= a data change of patch 1.1 or of the Steam build)?

Per name: size and md5 of the CDRM-decoded DRM from each source, 'equal' / 'DIFF' / 'missing'.

Usage (from the repository root):
  ../bin/pyt -t 900 work/q74_spots_1111/q74_retail_cmp.py NAME.drm [NAME.drm ...] [--out DIR]
  --out DIR: also write the decoded JP DRMs to DIR (to dump their uber graphs with q74_uber_dump.py)
Result 2026-11-11: the JP disc is another build (all section ids renumbered, e.g. calendar_b object 569 -> 572), so
the per-id lines only say "differ"; compare contents (uber graphs, scripts) instead.
"""
import sys, os, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode

JP = os.path.join(HERE, '..', '..', '..', 'input', 'jp-dvd', 'Game_Files', 'bigfile.000')


def get(A, name, e='le'):
    recs = A.find(crc('pc-w\\' + name))
    if not recs:
        return None
    return cdrm_decode(A.read(recs[-1]), e)


def main(argv):
    if not argv:
        print(__doc__); return 2
    out = None
    if '--out' in argv:
        i = argv.index('--out'); out = argv[i + 1]; del argv[i:i + 2]
        os.makedirs(out, exist_ok=True)
    S = Archive(LC.SRC['pcbig'][0], 'le')
    P = Archive(LC.SRC['pcpatch'][0], 'le')
    J = Archive(JP, 'le')
    for n in argv:
        s = get(P, n) or get(S, n)
        j = get(J, n)
        if s is None or j is None:
            print('%-32s steam %s / jp %s' % (n, 'ok' if s else 'missing', 'ok' if j else 'missing'))
            continue
        if out:
            open(os.path.join(out, n), 'wb').write(j)
        hs, hj = hashlib.md5(s).hexdigest(), hashlib.md5(j).hexdigest()
        print('%-32s steam %9d %s | jp %9d %s | %s' % (n, len(s), hs[:8], len(j), hj[:8], 'equal' if hs == hj else 'DIFF'))
        if hs != hj:
            # logic sections only: 0 Level / general, 7 DTP, 8 script, 11 object (media and textures differ by language)
            import drm_write as DW
            A = DW.read(s, 'le'); B = DW.read(j, 'le')
            for t, tn in ((0, 'type0'), (7, 'dtp'), (8, 'script'), (11, 'object')):
                sa = {}
                for x in A.sections:
                    if x.type == t: sa.setdefault(x.id, []).append(bytes(x.data) + bytes(x.reloc))
                sb = {}
                for x in B.sections:
                    if x.type == t: sb.setdefault(x.id, []).append(bytes(x.data) + bytes(x.reloc))
                eq = sum(1 for k in sa if k in sb and sorted(sa[k]) == sorted(sb[k]))
                df = [k for k in sa if k in sb and sorted(sa[k]) != sorted(sb[k])]
                only_s = [k for k in sa if k not in sb]; only_j = [k for k in sb if k not in sa]
                print('    %-6s equal %d, differ %d %s, steam only %d %s, jp only %d %s' % (
                    tn, eq, len(df), df[:8], len(only_s), only_s[:8], len(only_j), only_j[:8]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
