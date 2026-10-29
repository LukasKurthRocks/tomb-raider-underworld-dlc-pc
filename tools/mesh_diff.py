"""Where do our Mesh sections (type 12, 'Mesh' magic) differ from B138? (read-only)

Mesh sections of a rebuilt tree and of the reference tree are paired by (type, id). Per pair: same size or not;
for same-size pairs both are parsed with mesh_convert.parse (PC, LE) and compared region by region:
  header (before the first region), bonemap, meshinfo (52 B records), palettes, vdecl (vertex formats),
  vdata (vertex data), faces (indices), groups, lists (texture/material ids), tail (render tree + skeleton),
  reloc (relocation blob)
Non-'Mesh' type-12 sections (e.g. terrain) are counted separately. Totals per region, the files with most
differing meshes, and work/rebuild/mesh_diff_<label>.json with every pair.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/mesh_diff.py MODS_DIR LABEL [--ref REF_MODS_DIR]
  default REF_MODS_DIR: ../data/pc/mods (the installed B138 tree)
"""
import sys, os, json, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')
REGIONS = ('header', 'bonemap', 'meshinfo', 'palettes', 'vdecl', 'vdata', 'faces', 'groups', 'lists', 'tail', 'reloc')


def regions(sec):
    import mesh_convert as MC
    M = MC.parse(sec.data, 'le', sec.reloc)
    d = sec.data
    if M['empty']: return None
    m = M['m']
    out = dict(header=d[:M['hdr_end']], bonemap=M['bonemap'] or b'', reloc=sec.reloc,
               meshinfo=b''.join(bytes(str(b['raw']), 'ascii') for b in M['batches']),
               palettes=repr([b['palette'] for b in M['batches']]).encode(),
               vdecl=repr([b['vf'] for b in M['batches']]).encode(),
               vdata=b''.join(b['vdata'] for b in M['batches']),
               faces=repr(M['indices']).encode(),
               groups=b''.join(M['groups']),
               lists=d[M['lists'][0]:M['lists'][1]], tail=d[M['tail']:])
    return out


def diff_file(args):
    import drm_write as DW
    rel, ours, ref = args
    try:
        A = DW.read(open(ours, 'rb').read(), 'le'); B = DW.read(open(ref, 'rb').read(), 'le')
    except Exception as e:
        return rel, {'error': '%s: %s' % (type(e).__name__, e)}
    bm = {(s.type, s.id): s for s in B.sections}
    res = []
    for s in A.sections:
        if s.type != 12: continue
        b = bm.get((12, s.id))
        kind = 'mesh' if s.data[16:20] in (b'hseM', b'Mesh') else 'other'
        if b is None: res.append(dict(id=s.id, kind=kind, status='no_ref')); continue
        if s.data == b.data and s.reloc == b.reloc: res.append(dict(id=s.id, kind=kind, status='identical')); continue
        if len(s.data) != len(b.data): res.append(dict(id=s.id, kind=kind, status='size', ours=len(s.data), ref=len(b.data))); continue
        if kind != 'mesh': res.append(dict(id=s.id, kind=kind, status='same_size')); continue
        try:
            ra, rb = regions(s), regions(b)
        except Exception as e:
            res.append(dict(id=s.id, kind=kind, status='parse_error', error=str(e)[:100])); continue
        if ra is None or rb is None: res.append(dict(id=s.id, kind=kind, status='empty_mesh')); continue
        res.append(dict(id=s.id, kind=kind, status='same_size', regions=[k for k in REGIONS if ra[k] != rb[k]]))
    return rel, res


def main(argv):
    ref = '../data/pc/mods'
    if '--ref' in argv:
        k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    mods, label = argv[0], argv[1]
    from build_util import require_dir
    require_dir(mods, 'MODS_DIR'); require_dir(ref, 'REF_MODS_DIR')
    jobs = []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if not f.endswith('.drm'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, mods).replace(os.sep, '/')
            if os.path.exists(os.path.join(ref, rel)): jobs.append((rel, p, os.path.join(ref, rel)))
    out, st, reg, per = {}, collections.Counter(), collections.Counter(), collections.Counter()
    with ProcessPoolExecutor(max_workers=int(os.environ.get('TRUDLC_JOBS_LIGHT') or os.cpu_count())) as ex:
        for rel, res in ex.map(diff_file, sorted(jobs)):
            out[rel] = res
            if isinstance(res, dict): st['file_error'] += 1; continue
            for r in res:
                st['%s %s' % (r['kind'], r['status'])] += 1
                if r['status'] != 'identical': per[rel] += 1
                for g in r.get('regions', ()): reg[g] += 1
    print('type-12 sections by kind and status:')
    for k, n in sorted(st.items()): print('   %-26s %5d' % (k, n))
    print('same-size Mesh sections: differing regions (a section can count in several):')
    for g in REGIONS: print('   %-10s %5d' % (g, reg[g]))
    print('files with most differing type-12 sections:')
    for rel, n in per.most_common(10): print('   %4d  %s' % (n, rel))
    json.dump(out, open(os.path.join(W, 'mesh_diff_%s.json' % label), 'w'), indent=0)
    print('report', os.path.abspath(os.path.join(W, 'mesh_diff_%s.json' % label)))


if __name__ == '__main__':
    main(sys.argv[1:])
