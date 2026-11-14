"""W5 (2026-11-14): list the object markup arrays (classic 0x5c records hanging off an object DTP: count +0x54,
records +0x58, tru+0x5d0656) of every DRM in a folder, with the poly line in the object's LOCAL frame (the engine
transforms it with the bone matrix of the owner instance, 0x5be360 -> 0x49ba20 at 0x5c46ac / 0x5c470c).

Optional --project "m0 m1 m2 | m4 m5 m6 | m8 m9 m10 | t m12 m13 m14" (a TruMenu 0.13 'matrix 0xe804a0' log line,
focal 463.53, back buffer W x H): also print where TruMenu 0.3 DrawMarkup (which draws record points untransformed)
puts each poly line on a 1280 x 720 screenshot.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_obj_markup.py FOLDER [--be] [--types 1,15] [--project "..."] [--shot 1280x720]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R
import markup_level as ML

STRIDE = 0x5c


def object_arrays(path, be):
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(path, 'rb').read(), e)
    rel = []
    for s in D.sections:
        r = R.parse(bytes(s.reloc), e)
        rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
    out = []
    for si, s in enumerate(D.sections):
        d = bytes(s.data)
        if s.type != 7 or len(d) < 0x5c: continue
        t = ML.target(D, rel, si, 0x58)
        n = struct.unpack_from(f + 'I', d, 0x54)[0]
        if t is None or t[0] != si or not 1 <= n <= 1000 or t[1] + n * STRIDE > len(d): continue
        ro = t[1]
        if not all(struct.unpack_from(f + 'I', d, ro + k * STRIDE + 0x28)[0] == 0 for k in range(n)): continue
        recs = []
        for k in range(n):
            o = ro + k * STRIDE
            rid = struct.unpack_from(f + 'h', d, o + 0x2e)[0]
            bone = struct.unpack_from(f + 'h', d, o + 0x30)[0]
            skip = d[o + 0x32]
            typ = struct.unpack_from('b', d, o + 0x33)[0]
            pos = struct.unpack_from(f + '3f', d, o + 0x34)
            pts = []
            pl = ML.target(D, rel, si, o + 0x58)
            if pl:
                pd = bytes(D.sections[pl[0]].data)
                cnt = struct.unpack_from(f + 'i', pd, pl[1])[0]
                if 0 < cnt < 512:
                    for j in range(cnt):
                        po = pl[1] + 0x10 + 16 * j
                        if po + 12 <= len(pd): pts.append(struct.unpack_from(f + '3f', pd, po))
            recs.append((k, rid, bone, skip, typ, pos, pts))
        out.append((s.id, n, recs))
    return out


def parse_matrix(txt):
    parts = txt.replace('t', '|').split('|')
    rows = [[float(v) for v in p.split()] for p in parts if p.strip()]
    m = [0.0] * 16
    for r in range(3):
        m[4 * r:4 * r + 3] = rows[r]
    m[12:15] = rows[3]
    return m


def project(m, p, f=463.53, sw=1280, sh=720):
    x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12]
    y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13]
    z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]
    if not z > 16.0: return None
    return ((x / z * f + 256.0) * sw / 512.0, (y / z * f + 224.0) * sh / 448.0)


def main(argv):
    be = '--be' in argv
    types = None
    m = None
    if '--types' in argv:
        k = argv.index('--types'); types = set(int(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--project' in argv:
        k = argv.index('--project'); m = parse_matrix(argv[k + 1]); del argv[k:k + 2]
    argv = [a for a in argv if not a.startswith('--')]
    folder = argv[0]
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith('.drm') and 'truguard' not in n.lower())
    tot = collections.Counter()
    for name in names:
        try:
            arrs = object_arrays(os.path.join(folder, name), be)
        except Exception as ex:                  # noqa: BLE001 - report and go on
            print('%s: read error %s' % (name, ex)); continue
        for dtp, n, recs in arrs:
            shown = [r for r in recs if types is None or r[4] in types]
            if not shown: continue
            print('%s dtp %d: %d object markup records' % (name, dtp, n))
            for k, rid, bone, skip, typ, pos, pts in shown:
                tot[ML.tname(typ)] += 1
                closed = len(pts) > 2 and all(abs(pts[0][i] - pts[-1][i]) < 0.5 for i in range(3))
                xs = [p[0] for p in pts] or [pos[0]]; ys = [p[1] for p in pts] or [pos[1]]; zs = [p[2] for p in pts] or [pos[2]]
                line = ('  #%2d id %5d type %2d %-12s bone %3d skip %d pos (%.0f %.0f %.0f) %2d pts%s x %.0f..%.0f y %.0f..%.0f '
                        'z %.0f..%.0f' % (k, rid, typ, ML.tname(typ), bone, skip, pos[0], pos[1], pos[2], len(pts),
                                          ' closed' if closed else '', min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
                if m is not None and pts:
                    sp = [project(m, p) for p in pts]
                    sp = [q for q in sp if q]
                    if sp:
                        line += '  screen x %.0f..%.0f y %.0f..%.0f' % (min(q[0] for q in sp), max(q[0] for q in sp),
                                                                      min(q[1] for q in sp), max(q[1] for q in sp))
                print(line)
    print('records by type: ' + ', '.join('%s %d' % kv for kv in sorted(tot.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
