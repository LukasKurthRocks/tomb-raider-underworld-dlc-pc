"""W5 (2026-11-14): unit markup2 items of a unit DRM in the live frame (M * p - Level+0x80, tools/markup_level.py), with
type names, and - with --project - where a TruMenu 0.13 'matrix 0xe804a0' log line puts them on a 1280 x 720 shot.
--shift X,Y,Z adds a vector to every point (another unit's frame: live position of this unit's origin difference).
--compare B.drm [--be-b]: per markup id, compare type and points with a second DRM (own <-> old <-> Xbox).

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_unit_markup.py UNIT.drm [--be] [--project "r0 | r1 | r2 | t T"] [--onscreen]
      [--shift X,Y,Z] [--compare OTHER.drm [--be-b]]
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R
import markup_level as ML
from w5_obj_markup import parse_matrix, project


def load(path, be):
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(path, 'rb').read(), e)
    rel = []
    for s in D.sections:
        r = R.parse(bytes(s.reloc), e)
        rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
    hd = bytes(D.sections[0].data)
    origin = struct.unpack_from(f + '3f', hd, 0x80)
    items, head = ML.markup2_items(D, rel, f, origin)
    return items or [], head, origin


def main(argv):
    be = '--be' in argv; beb = '--be-b' in argv; onscreen = '--onscreen' in argv
    m = shift = other = None
    if '--project' in argv:
        k = argv.index('--project'); m = parse_matrix(argv[k + 1]); del argv[k:k + 2]
    if '--shift' in argv:
        k = argv.index('--shift'); shift = tuple(float(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--compare' in argv:
        k = argv.index('--compare'); other = argv[k + 1]; del argv[k:k + 2]
    near = None; radius = 2500.0
    if '--near' in argv:
        k = argv.index('--near'); near = tuple(float(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--radius' in argv:
        k = argv.index('--radius'); radius = float(argv[k + 1]); del argv[k:k + 2]
    argv = [a for a in argv if not a.startswith('--')]
    items, head, origin = load(argv[0], be)
    if near is not None:
        def dist(it):
            pts = it[8]
            segs = list(zip(pts, pts[1:])) or [(pts[0], pts[0])] if pts else []
            return min((ML.seg_dist(near, a, b) for a, b in segs), default=1e9)
        items = [it for it in items if dist(it) <= radius]
        print('near (%.1f %.1f %.1f) within %.0f: %d items' % (near[0], near[1], near[2], radius, len(items)))
    print('%s: origin (%.1f %.1f %.1f), %s' % (os.path.basename(argv[0]), origin[0], origin[1], origin[2], head))
    print('types: ' + ', '.join('%s %d' % kv for kv in sorted(collections.Counter(ML.tname(it[6]) for it in items).items())))
    if other:
        oitems, ohead, oorigin = load(other, beb)
        print('compare %s: origin (%.1f %.1f %.1f), %s' % (os.path.basename(other), oorigin[0], oorigin[1], oorigin[2], ohead))
        a = {it[3]: it for it in items}; b = {it[3]: it for it in oitems}
        same = diff = 0
        for iid in sorted(set(a) | set(b)):
            if iid not in a or iid not in b:
                print('  id %d only in %s' % (iid, 'A' if iid in a else 'B')); diff += 1; continue
            pa, pb = a[iid][8], b[iid][8]
            dmax = max((max(abs(p[c] - q[c]) for c in range(3)) for p, q in zip(pa, pb)), default=0.0)
            if a[iid][6] != b[iid][6] or len(pa) != len(pb) or dmax > 0.05 or a[iid][7] != b[iid][7] or a[iid][5] != b[iid][5]:
                diff += 1
                print('  id %d: type %d/%d kind %d/%d +50 %02x/%02x pts %d/%d max point diff %.2f' % (
                    iid, a[iid][6], b[iid][6], a[iid][5], b[iid][5], a[iid][7], b[iid][7], len(pa), len(pb), dmax))
            else:
                same += 1
        print('  same %d, different %d (ids A %d, B %d)' % (same, diff, len(a), len(b)))
        return
    for k, si, o, iid, aux, kind, typ, fl, pts in items:
        if shift: pts = [tuple(p[c] + shift[c] for c in range(3)) for p in pts]
        xs = [p[0] for p in pts] or [0]; ys = [p[1] for p in pts] or [0]; zs = [p[2] for p in pts] or [0]
        line = '  id %5d type %2d %-12s kind %d %2d pts x %.0f..%.0f y %.0f..%.0f z %.0f..%.0f' % (
            iid, typ, ML.tname(typ), kind, len(pts), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
        if m is not None:
            sp = [q for q in (project(m, p) for p in pts) if q]
            vis = [q for q in sp if 0 <= q[0] <= 1280 and 0 <= q[1] <= 720]
            if onscreen and not vis: continue
            if sp:
                line += '  screen ' + ' '.join('(%.0f %.0f)' % q for q in sp[:4]) + (' ...' if len(sp) > 4 else '')
        elif onscreen:
            continue
        print(line)


if __name__ == '__main__':
    main(sys.argv[1:])
