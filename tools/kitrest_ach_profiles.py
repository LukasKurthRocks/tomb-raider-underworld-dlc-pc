"""Per test profile: script calls into natives the PC exe does not implement, in the set the profile installs
(read-only; kit-rest task 1, workspace docs Befund-Kit-Reste-0511.md).

Replays every profile's install order with tools/profile_fix_plan.py (its install / tree_files / base_files, used
read-only; --base-undo as there) and runs the check of the pipeline fix `achievement`
(tools/script_missing_native_fix.fix_section, apply=False, reference = the original PC generalbank 'pc') on every
final .drm. Counted per profile: calls into `achievement` (FIX = the fix would neutralise it, SKIP = a call the fix
leaves alone), calls into any other native type (types 'all'), and the files. Cached by md5.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/kitrest_ach_profiles.py --profile "tests/profiles/*.json" --base GAME/mods
        [--base-undo ../runs/installed-state.json] [--detail]
"""
import sys, os, glob, re, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_fix_plan as PFP
import profile_last_source as PLS
import drm_write as DW
import script_missing_native_fix as MN

_C = {}
LINE = re.compile(r'^(FIX |SKIP).*?(\S+\.drm):(\d+)\+0x([0-9a-f]+) -> (\S+) \+0x([0-9a-f]+)')


def calls(path, nat):
    """[(kind, type name, script id, operand offset, native offset)] of one DRM, cached by md5"""
    h = PFP.md5(path)
    if h not in _C:
        rep = []
        try:
            D = DW.read(open(path, 'rb').read(), 'le')
        except Exception as e:                     # not a readable DRM (e.g. other formats): no scripts
            _C[h] = [('ERR', str(e)[:60], 0, 0, 0)]; return _C[h]
        for s in D.sections:
            if s.type == 8 and s.data:
                MN.fix_section(D, s, nat, 'all', False, os.path.basename(path), rep)
        out = []
        for l in rep:
            m = LINE.match(l)
            if m: out.append((m.group(1).strip(), m.group(5), int(m.group(3)), int(m.group(4), 16), int(m.group(6), 16)))
        _C[h] = out
    return _C[h]


def main(a):
    profiles = []
    while '--profile' in a:
        k = a.index('--profile'); profiles += sorted(glob.glob(a[k + 1])) or [a[k + 1]]; del a[k:k + 2]
    base = None
    if '--base' in a: k = a.index('--base'); base = a[k + 1]; del a[k:k + 2]
    if '--base-undo' in a: k = a.index('--base-undo'); PFP.BASE_UNDO = a[k + 1]; del a[k:k + 2]
    detail = '--detail' in a
    nat = MN.native_types('pc')
    print('reference: original PC generalbank, %d native type scripts' % len(nat))
    rows = []
    for pp in profiles:
        import json
        prof = json.load(open(pp, encoding='utf-8-sig'))
        trees = []
        for t in prof.get('trees') or []:
            if not t: continue
            src = PLS.resolve(t['source'])
            seg = t['source'].replace('\\', '/').rstrip('/').split('/')
            label = seg[-2] if seg[-1].lower() == 'mods' and len(seg) > 1 else seg[-1]
            trees.append((label, PFP.tree_files(src, t.get('exclude'))))
        files = {f['name'].replace('\\', '/').lower(): PLS.resolve(f['source']) for f in (prof.get('files') or []) if f}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fin = PFP.install(trees, files, base)
        if buf.getvalue().strip(): print(buf.getvalue().strip())
        pn = os.path.basename(pp)[:-5]
        ach, other, err = [], [], []
        for rel, (p, label) in sorted(fin.items()):
            if not rel.endswith('.drm'): continue
            for kind, tname, sid, so, do in calls(p, nat):
                if kind == 'ERR': err.append(rel); continue
                (ach if tname == 'achievement' else other).append((os.path.basename(rel), label, kind, tname, sid, so, do))
        rows.append((pn, ach, other, err))
        print('\nPROFILE %s: achievement calls %d (%s) | other-native calls %d | unreadable %d' % (
            pn, len(ach), ', '.join(sorted(set('+0x%x' % x[6] for x in ach))) or '-', len(other), len(err)))
        if detail or ach or other:
            for x in ach + other:
                print('  %s %-12s %s:%d+0x%x -> +0x%x   (from %s)' % (x[2], x[3], x[0], x[4], x[5], x[6], x[1]))
    print('\n| Profil | achievement-Aufrufe | Dateien | andere native Typen |')
    print('|---|---|---|---|')
    for pn, ach, other, err in rows:
        print('| %s | %d | %s | %d |' % (pn, len(ach), ', '.join(sorted(set(x[0] for x in ach))) or '-', len(other)))
    print('\nprofiles %d, with achievement calls %d, total calls %d' % (len(rows), sum(1 for r in rows if r[1]),
                                                                       sum(len(r[1]) for r in rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
