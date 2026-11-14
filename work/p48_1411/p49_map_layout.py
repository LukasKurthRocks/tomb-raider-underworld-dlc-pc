"""P4.9 (2026-11-14): layout of *_map.drm files (read-only): sections (type, id, size, relocs) and the collision mesh
headers found by the w1_map_bvh pointer scan, PC file vs Xbox source.

Usage (from the repository root):
  ../bin/pyt -t 600 work/p48_1411/p49_map_layout.py PC_FILE.drm [...]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'w1_1411'))
import drm_reloc as R
import w1_map_bvh as B


def show(label, S, e):
    print('%s (%s): %d sections' % (label, e, len(S)))
    for i, s in enumerate(S):
        r = R.parse(s.reloc, e)
        print('  s%-3d type %2d id %7d size %8d  int %5d ext %4d ids %d' % (
            i, s.type, s.id, len(s.data), len(r.internal), len(r.external), len(r.id_offsets())))
    rel = B.rels(S, e)
    M = B.meshes(S, rel, e)
    how = 'level'
    if not M: M = B.scan_meshes(S, rel, e); how = 'scan'
    for gi, ms, mo, nn, nf, nref in M:
        print('  mesh (%s) %s: hdr s%d+0x%x nodes %d faces %d -> node array %s' % (how, gi, ms, mo, nn, nf, nref))


def main(argv):
    for p in argv:
        S, e = B.load_file(p)
        show('pc ' + os.path.basename(p), S, e)
        X, xe = B.load_xbox(os.path.basename(p))
        if X is None: print('  no xbox source'); continue
        show('xbox ' + os.path.basename(p), X, xe)


if __name__ == '__main__':
    main(sys.argv[1:])
