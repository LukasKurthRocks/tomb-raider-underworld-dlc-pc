"""md5 snapshots of chosen work files before / after a pipeline run, their diff, and the files written after a marker
(read-only on everything it lists; writes only the snapshot TSV named on the command line). Agent pv0511, 2026-11-05:
full pipeline check run, "record what a step will overwrite before it runs".

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/md5_snapshot.py snap OUT.tsv SPEC [SPEC ...]
        SPEC = DIR (recursive) | DIR/* (only the files directly in DIR) | FILE; a missing SPEC is listed as 'missing'
        OUT.tsv: md5 TAB size TAB mtime (local, ISO) TAB path (relative to the repository, '/' separators)
  ../bin/pyt -t 600 tools/md5_snapshot.py diff A.tsv B.tsv [--under PREFIX]
        counts same / changed / only in A / only in B, then every changed / only path with both md5 and sizes
        (--under: only paths below PREFIX); exit 0 = identical, 1 = differences
  ../bin/pyt -t 1800 tools/md5_snapshot.py newer MARKER DIR [--exclude PREFIX ...]
        every file below DIR (recursive) whose mtime is later than MARKER's mtime, with date + time, size and md5
        (--exclude: paths starting with PREFIX are counted but not listed); exit 0 always
"""
import sys, os, hashlib, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b''): h.update(chunk)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


def stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')


def walk_spec(spec):
    p = os.path.join(ROOT, spec.rstrip('*').rstrip('/\\')) if spec.endswith('*') else os.path.join(ROOT, spec)
    if spec.endswith('*'):
        if not os.path.isdir(p): return None
        return [os.path.join(p, f) for f in sorted(os.listdir(p)) if os.path.isfile(os.path.join(p, f))]
    if os.path.isfile(p): return [p]
    if not os.path.isdir(p): return None
    out = []
    for dp, dn, fn in os.walk(p):
        dn.sort()
        for f in sorted(fn): out.append(os.path.join(dp, f))
    return out


def snap(out, specs):
    rows = []; missing = []
    for s in specs:
        fs = walk_spec(s)
        if fs is None: missing.append(s); continue
        for f in fs:
            st = os.stat(f)
            rows.append((md5(f), st.st_size, stamp(st.st_mtime), rel(f)))
        print('%-60s %6d files' % (s, len(fs)), flush=True)
    rows.sort(key=lambda r: r[3])
    with open(out, 'w', encoding='utf-8', newline='\n') as h:
        h.write('md5\tsize\tmtime\tpath\n')
        for r in rows: h.write('%s\t%d\t%s\t%s\n' % r)
        for s in missing: h.write('missing\t0\t-\t%s\n' % s)
    print('missing specs: %d %s' % (len(missing), ' '.join(missing)))
    print('wrote %s (%d files, %d bytes)' % (out, len(rows), sum(r[1] for r in rows)))


def load(p):
    d = {}
    for line in open(p, encoding='utf-8'):
        t = line.rstrip('\n').split('\t')
        if len(t) != 4 or t[0] == 'md5' or t[0] == 'missing': continue
        d[t[3]] = (t[0], int(t[1]), t[2])
    return d


def diff(a, b, under):
    A = load(a); B = load(b)
    if under:
        A = {k: v for k, v in A.items() if k.startswith(under)}; B = {k: v for k, v in B.items() if k.startswith(under)}
    same = [k for k in A if k in B and A[k][0] == B[k][0]]
    changed = sorted(k for k in A if k in B and A[k][0] != B[k][0])
    only_a = sorted(k for k in A if k not in B); only_b = sorted(k for k in B if k not in A)
    print('A %s: %d files, B %s: %d files' % (a, len(A), b, len(B)))
    print('same %d, changed %d, only in A %d, only in B %d' % (len(same), len(changed), len(only_a), len(only_b)))
    for k in changed: print('CHANGED  %s  %s %d -> %s %d' % (k, A[k][0], A[k][1], B[k][0], B[k][1]))
    for k in only_a: print('ONLY_A   %s  %s %d' % (k, A[k][0], A[k][1]))
    for k in only_b: print('ONLY_B   %s  %s %d' % (k, B[k][0], B[k][1]))
    return 1 if (changed or only_a or only_b) else 0


def newer(marker, d, excludes):
    t0 = os.stat(os.path.join(ROOT, marker) if not os.path.isabs(marker) else marker).st_mtime
    print('marker %s mtime %s' % (marker, stamp(t0)))
    hits = 0; excl = 0
    for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f); st = os.stat(p)
            if st.st_mtime <= t0: continue
            r = rel(p)
            if any(r.startswith(x) for x in excludes): excl += 1; continue
            hits += 1
            print('NEWER  %s  %10d  %s  %s' % (stamp(st.st_mtime), st.st_size, md5(p), r))
    print('newer files: %d listed, %d below excluded prefixes' % (hits, excl))
    return 0


def main(argv):
    if not argv: sys.exit(__doc__)
    if argv[0] == 'snap' and len(argv) >= 3: return snap(argv[1], argv[2:])
    if argv[0] == 'diff' and len(argv) >= 3:
        under = argv[argv.index('--under') + 1] if '--under' in argv else None
        sys.exit(diff(argv[1], argv[2], under))
    if argv[0] == 'newer' and len(argv) >= 3:
        ex = [argv[i + 1] for i, x in enumerate(argv) if x == '--exclude']
        return newer(argv[1], argv[2], ex)
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
