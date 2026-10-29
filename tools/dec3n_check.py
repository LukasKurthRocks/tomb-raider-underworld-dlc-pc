"""Which Xbox DEC3N values does a converted tree map differently from our learnt table? (read-only, finding 37)

For every DLC Mesh section (Xbox, work/render/dlc_render.pkl) that also exists in the PC tree (type 12, Xbox id
mapped with dlc_generic.DlcIds):
batches with the same vertex count, Xbox element type 0x11 against PC type 5 at the same offset; every 10-bit
component votes Xbox value -> PC byte. Prints whether the tree's mapping is a function (one byte per value), and
every value where it differs from work/render/dec3n_lut.pkl, with the base-pair vote of that value
(work/render/dec3n_votes.pkl from tools/mesh_tables_build.py) for comparison.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dec3n_check.py [MODS_DIR] [--variants]   (default ../data/pc/mods = B138)
  --variants: which subset of the base-pair votes (semantic, component, same-size pairs, first pair per Xbox id)
              reproduces the tree's mapping (needs work/render/dec3n_votes_by.pkl from tools/mesh_tables_build.py)
"""
import sys, os, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesh_convert as MC, drm_write as DW

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'render')


def main(argv):
    variants = '--variants' in argv; argv = [a for a in argv if a != '--variants']
    mods = argv[0] if argv else '../data/pc/mods'
    pc = {}
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if not f.endswith('.drm'): continue
            for s in DW.read(open(os.path.join(dp, f), 'rb').read(), 'le').sections:
                if s.type == 12 and s.data[16:20] in (b'hseM', b'Mesh'): pc.setdefault(s.id, s)
    xb = {}
    for path, i, h, secs in pickle.load(open(os.path.join(W, 'dlc_render.pkl'), 'rb')):
        for s in secs or []:
            if s['type'] == 12 and s['data'][0x10:0x14] == b'hseM': xb.setdefault(s['id'], s)
    lut = pickle.load(open(os.path.join(W, 'dec3n_lut.pkl'), 'rb'))
    vp = os.path.join(W, 'dec3n_votes.pkl')
    base = pickle.load(open(vp, 'rb')) if os.path.exists(vp) else None
    import dlc_generic as DG
    ids = DG.DlcIds()    # Xbox id -> PC id (work/generic/dlc_idmap.json, as the converter maps it)
    votes = [collections.Counter() for _ in range(1024)]; st = collections.Counter()
    for sid, a in xb.items():
        b = pc.get(ids(12, sid))
        if b is None: st['no_pc'] += 1; continue
        Mx = MC.parse(a['data'], 'be', a['reloc']); Mp = MC.parse(b.data, 'le', b.reloc)
        if Mx['empty'] or Mp['empty'] or len(Mx['batches']) != len(Mp['batches']): st['skipped'] += 1; continue
        st['meshes'] += 1
        for xbb, pbb in zip(Mx['batches'], Mp['batches']):
            if not xbb['vf'] or not pbb['vf'] or xbb['numVerts'] != pbb['numVerts']: continue
            xs, ps = xbb['vf']['stride'], pbb['vf']['stride']
            pt = {eo: t for s, eo, t, _ in pbb['vf']['elems']}
            for s, eo, t, _ in xbb['vf']['elems']:
                if t != 0x11 or pt.get(eo) != 5: continue
                for v in range(xbb['numVerts']):
                    x = struct.unpack_from('>I', xbb['vdata'], v * xs + eo)[0]
                    q = pbb['vdata'][v * ps + eo:v * ps + eo + 3]
                    for c, byte in zip(((x >> 20) & 0x3ff, (x >> 10) & 0x3ff, x & 0x3ff), q):
                        votes[c][byte] += 1
    seen = [v for v in range(1024) if votes[v]]
    multi = [v for v in seen if len(votes[v]) > 1]
    diff = [v for v in seen if votes[v].most_common(1)[0][0] != lut[v]]
    print('PC Mesh sections %d, Xbox DLC Mesh sections %d' % (len(pc), len(xb)))
    print('stats', dict(st), 'components', sum(sum(c.values()) for c in votes))
    print('values seen %d, mapped to more than one byte %d, majority differs from dec3n_lut %d' % (len(seen), len(multi), len(diff)))
    for v in diff:
        sv = v - 1024 if v >= 512 else v
        bv = dict(base[v].most_common(3)) if base else '-'
        print('   x %4d (s %4d): tree %s   ours %3d   base votes %s' % (v, sv, dict(votes[v].most_common(3)), lut[v], bv))
    for v in multi[:20]:
        print('   ambiguous x %4d: %s' % (v, dict(votes[v].most_common(4))))
    if variants: study(votes, seen)


def study(votes, seen):
    """Which subset of the base-pair votes (work/render/dec3n_votes_by.pkl) reproduces the tree's mapping?"""
    import itertools
    by = pickle.load(open(os.path.join(W, 'dec3n_votes_by.pkl'), 'rb'))
    target = {v: votes[v].most_common(1)[0][0] for v in seen}
    sems = sorted({k[0] for k in by})

    def subsets(xs):
        return [c for n in range(1, len(xs) + 1) for c in itertools.combinations(xs, n)]
    rows = []
    for ss in subsets(sems):
        for cs in subsets((0, 1, 2)):
            for size_only in (False, True):
                for first_only in (False, True):
                    keys = [k for k in by if k[0] in ss and k[1] in cs and (k[2] or not size_only) and (k[3] or not first_only)]
                    tot = [collections.Counter() for _ in range(1024)]
                    for k in keys:
                        for v in range(1024): tot[v].update(by[k][v])
                    n = sum(sum(c.values()) for c in tot)
                    miss = sum(1 for v in seen if not tot[v] or tot[v].most_common(1)[0][0] != target[v])
                    rows.append((miss, n, [hex(x) for x in ss], cs, size_only, first_only))
    rows.sort(key=lambda r: (r[0], -r[1]))
    print('variants (values differing from the tree, components, semantics, components used, same-size only, first pair only):')
    for r in rows[:25]: print('   %4d  %9d  %s %s size_only=%s first_only=%s' % r)


if __name__ == '__main__':
    main(sys.argv[1:])
