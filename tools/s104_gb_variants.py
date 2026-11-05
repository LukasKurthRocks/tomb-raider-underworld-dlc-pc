"""S104 (2026-11-05): compare generalbank variants and show what the test profiles install (read-only).

  compare KIND=NEW_FILE ... --ref KIND=FILE ...
      md5 of every file; per kind: is the new file byte-identical with each reference file of the same kind
  profiles PROFILE_DIR KIND=NEW_FILE ... [--root WORKSPACE]
      per profile (*.json directly in PROFILE_DIR): the generalbank.drm it installs (the last tree in "trees" whose
      source holds generalbank.drm and does not exclude it), its md5, the new variant with the fewest different DRM
      sections (= the same kind) and those sections; "would change" = installing that new variant instead changes the
      file. WORKSPACE (default ..) is the folder the tree sources are relative to.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/s104_gb_variants.py compare plain=A.drm hud=B.drm --ref plain=C.drm --ref plain=D.drm
  ../bin/pyt -t 600 tools/s104_gb_variants.py profiles tests/profiles plain=A.drm hud=B.drm pause=C.drm hud_pause=D.drm
"""
import sys, os, json, hashlib, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

_md5 = {}
_secs = {}


def md5(p):
    p = os.path.abspath(p)
    if p not in _md5:
        _md5[p] = hashlib.md5(open(p, 'rb').read()).hexdigest()
    return _md5[p]


def sections(p):
    h = md5(p)
    if h not in _secs:
        _secs[h] = _keyed(DW.read(open(p, 'rb').read(), 'le'))
    return _secs[h]


def _keyed(D):
    """{(type, id, n-th of that type / id): (data, relocations)}"""
    out = {}; seen = {}
    for s in D.sections:
        n = seen.get((s.type, s.id), 0); seen[(s.type, s.id)] = n + 1
        out[(s.type, s.id, n)] = (s.data, s.reloc)
    return out


def sec_diff(a, b):
    A, B = sections(a), sections(b)
    keys = sorted(set(A) | set(B))
    return ['%d:%d%s%s' % (t, i, '#%d' % n if n else '', '' if k in A and k in B else (' only new' if k in B else ' only old'))
            for k in keys for t, i, n in [k] if A.get(k) != B.get(k)]


def pairs(items):
    out = []
    for x in items:
        k, _, p = x.partition('=')
        if not p:
            sys.exit('expected KIND=FILE, got %s' % x)
        out.append((k, p))
    return out


def compare(argv):
    refs = []
    while '--ref' in argv:
        k = argv.index('--ref'); refs.append(argv[k + 1]); del argv[k:k + 2]
    new = pairs(argv); refs = pairs(refs)
    bad = 0
    for kind, p in new:
        print('%-10s new  %s  %s' % (kind, md5(p), p))
        for rk, rp in refs:
            if rk != kind:
                continue
            same = open(p, 'rb').read() == open(rp, 'rb').read()
            bad += not same
            print('%-10s ref  %s  %s  %s' % (kind, md5(rp), 'byte-identical' if same else 'DIFFERENT: ' +
                                              ', '.join(sec_diff(rp, p)[:8]), rp))
    print('compare: %d kinds, %d references, %d different' % (len(new), len(refs), bad))
    if bad:
        sys.exit(1)


def profile_gb(prof, root):
    j = json.load(open(prof, encoding='utf-8-sig'))
    found = None
    for t in j.get('trees', []):
        src = os.path.join(root, t['source'])
        if 'generalbank.drm' in (t.get('exclude') or []):
            continue
        p = os.path.join(src, 'generalbank.drm')
        if os.path.isfile(p):
            found = (t['source'], p, (t.get('md5') or {}).get('generalbank.drm'))
        elif (t.get('md5') or {}).get('generalbank.drm'):
            found = (t['source'] + ' (MISSING on disk)', None, t['md5']['generalbank.drm'])
    for f in j.get('files', []) or []:
        if isinstance(f, dict) and str(f.get('target', '')).replace('\\', '/').endswith('generalbank.drm'):
            found = ('files entry %s' % f, None, None)
    return found


def profiles(argv):
    root = '..'
    if '--root' in argv: k = argv.index('--root'); root = argv[k + 1]; del argv[k:k + 2]
    pdir = argv[0]; new = pairs(argv[1:])
    rows = []; change = 0; n = 0
    for prof in sorted(glob.glob(os.path.join(pdir, '*.json'))):
        n += 1
        name = os.path.splitext(os.path.basename(prof))[0]
        f = profile_gb(prof, root)
        if f is None:
            print('%-36s no generalbank.drm in its trees' % name); continue
        src, p, rec = f
        if p is None:
            print('%-36s %s  recorded %s - cannot compare' % (name, src, rec)); continue
        h = md5(p)
        best = min(((len(sec_diff(p, q)), k, q) for k, q in new), key=lambda x: x[0])
        nd, kind, q = best
        diff = sec_diff(p, q)
        after = md5(q)
        mark = 'same' if h == after else 'WOULD CHANGE'
        change += h != after
        print('%-36s before %s  kind %-9s after %s  %-12s %s%s  tree %s' % (
            name, h, kind, after, mark, '%d sections: %s' % (nd, ', '.join(diff[:6])) if nd else '0 sections',
            '' if rec in (None, h) else '  (profile records %s!)' % rec, src))
    print('profiles: %d, generalbank would change in %d (installing the new variant of the same kind)' % (n, change))


def main(argv):
    if not argv:
        sys.exit(__doc__)
    if argv[0] == 'compare':
        compare(argv[1:])
    elif argv[0] == 'profiles':
        profiles(argv[1:])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
