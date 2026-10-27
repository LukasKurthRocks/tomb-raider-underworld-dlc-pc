"""Compare the DRMs of a mods/ tree with a reference mods/ tree (e.g. the installed B138), per section type.

Files are paired by relative path; sections inside a file by compare_drm.section_matches (fingerprint, then
(type, id), then position). A section counts as identical when data and normalised relocations are equal.
Totals per type go to the console, the per-file numbers to work/rebuild/sections_<label>.json.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/compare_sections.py MODS_DIR [LABEL] [--ref REF_MODS_DIR]
  default REF_MODS_DIR: ../data/pc/mods (the installed B138 tree)
"""
import sys, os, json, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')
TYPES = {0: 'general', 2: '2', 5: 'texture', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shader lib', 10: 'material',
         11: 'Obj', 12: 'mesh', 13: '13'}


def compare_file(args):
    import compare_drm as C
    rel, ours, ref = args
    try:
        so, sp = C.load(open(ours, 'rb').read()), C.load(open(ref, 'rb').read())
    except Exception as e:
        return rel, {'error': '%s: %s' % (type(e).__name__, e)}
    st = collections.Counter()
    for s in so: st['%d total' % s['type']] += 1
    for i, j, how in C.section_matches(so, sp):
        a, b = so[i], sp[j]
        t = a['type']
        st['%d matched' % t] += 1
        if a['data'] == b['data'] and C.norm_reloc(a, so) == C.norm_reloc(b, sp): st['%d identical' % t] += 1
    return rel, dict(st)


def main(argv):
    ref = '../data/pc/mods'
    if '--ref' in argv:
        k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    mods = argv[0]
    label = argv[1] if len(argv) > 1 else os.path.basename(os.path.dirname(os.path.abspath(mods)))
    jobs, no_ref = [], []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if not f.endswith('.drm'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, mods).replace(os.sep, '/')
            r = os.path.join(ref, rel)
            if os.path.exists(r): jobs.append((rel, p, r))
            else: no_ref.append(rel)
    per_file, tot, errors = {}, collections.Counter(), []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for rel, st in ex.map(compare_file, sorted(jobs)):
            per_file[rel] = st
            if 'error' in st: errors.append((rel, st['error'])); continue
            tot.update(st)
    print('DRMs %d, with reference %d, without %d, errors %d' % (len(jobs) + len(no_ref), len(jobs), len(no_ref), len(errors)))
    print('%-12s %8s %8s %10s %7s' % ('type', 'ours', 'matched', 'identical', '%'))
    for t in sorted({int(k.split()[0]) for k in tot}):
        n, m, i = tot['%d total' % t], tot['%d matched' % t], tot['%d identical' % t]
        print('%-12s %8d %8d %10d %6.1f%%' % ('%d %s' % (t, TYPES.get(t, '')), n, m, i, 100.0 * i / n if n else 0))
    for rel, e in errors: print('error', rel, e)
    os.makedirs(W, exist_ok=True)
    rep = os.path.join(W, 'sections_%s.json' % label)
    json.dump({'ref': ref, 'files': per_file, 'no_ref': no_ref}, open(rep, 'w'), indent=1)
    print('report', os.path.abspath(rep))


if __name__ == '__main__':
    main(sys.argv[1:])
