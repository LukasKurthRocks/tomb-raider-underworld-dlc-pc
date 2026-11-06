"""Which files of hand-built test trees a pipeline run reproduces now, and whether an earlier run reproduced them
(read-only; agent pv0511, 2026-11-05: full pipeline check run against pipeline_check_0411b and the test trees).

For every file of every TREE (its mods folder when present; path relative to it) the md5 is compared with the file of
the same relative path in every NEW and every OLD output folder (label=DIR; several folders because DLC 1 and DLC 2
carry files of the same name, finding 38). Per file one status:
  same        a NEW copy and an OLD copy both equal the test file (reproduced then and now)
  GAINED      a NEW copy equals the test file, no OLD copy did
  LOST        an OLD copy equalled the test file, no NEW copy does
  differs     no copy equals the test file, then or now; 'new=old' tells whether the NEW copies equal the OLD ones
  absent      no NEW folder has the path
Summary per tree, then every file that is not 'same' (and with --all every file).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/repro_matrix.py --new L=DIR[,L=DIR...] --old L=DIR[,L=DIR...] TREE [TREE ...] [--all]
Exit 0 always (a report, not a gate).
"""
import sys, os, hashlib, collections

_cache = {}


def md5(p):
    if p not in _cache:
        h = hashlib.md5()
        with open(p, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b''): h.update(chunk)
        _cache[p] = h.hexdigest()
    return _cache[p]


def files(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace(os.sep, '/').lower()] = p
    return out


def parse_dirs(s):
    out = []
    for item in s.split(','):
        lab, d = item.split('=', 1)
        out.append((lab, files(d)))
    return out


def main(argv):
    if '--new' not in argv or '--old' not in argv: sys.exit(__doc__)
    new = parse_dirs(argv[argv.index('--new') + 1]); old = parse_dirs(argv[argv.index('--old') + 1])
    show_all = '--all' in argv
    skip = {argv.index('--new'), argv.index('--new') + 1, argv.index('--old'), argv.index('--old') + 1}
    trees = [a for i, a in enumerate(argv) if i not in skip and not a.startswith('--')]
    total = collections.Counter()
    for t in trees:
        root = os.path.join(t, 'mods') if os.path.isdir(os.path.join(t, 'mods')) else t
        tf = files(root)
        st = collections.Counter(); rows = []
        for rel in sorted(tf):
            tm = md5(tf[rel])
            nh = [(lab, md5(fs[rel])) for lab, fs in new if rel in fs]
            oh = [(lab, md5(fs[rel])) for lab, fs in old if rel in fs]
            n_eq = [lab for lab, m in nh if m == tm]; o_eq = [lab for lab, m in oh if m == tm]
            if not nh: s = 'absent'
            elif n_eq and o_eq: s = 'same'
            elif n_eq: s = 'GAINED'
            elif o_eq: s = 'LOST'
            else: s = 'differs'
            om = dict(oh)
            neo = ','.join('%s:%s' % (lab, 'new=old' if om.get(lab) == m else ('new!=old' if lab in om else 'no-old'))
                           for lab, m in nh)
            st[s] += 1; total[s] += 1
            rows.append((s, rel, tm, '+'.join(n_eq) or '-', '+'.join(o_eq) or '-', neo,
                         ' '.join('%s=%s' % (lab, m[:8]) for lab, m in nh)))
        print('TREE %s: %d files  %s' % (t, len(tf), dict(sorted(st.items()))))
        for r in rows:
            if show_all or r[0] != 'same':
                print('  %-7s %-70s test=%s now=%s then=%s %s [%s]' % (r[0], r[1], r[2][:8], r[3], r[4], r[5], r[6]))
    print('TOTAL %s' % dict(sorted(total.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
