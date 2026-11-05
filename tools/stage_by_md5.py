"""Stage the exact input files of an earlier fix run by md5 (read-only on the search folders; agent N11, 2026-11-04).

A stand-alone fix tool (e.g. tools/objdata_fx_fix.py check --out-dir) logs the md5 of every input it changed. To prove
that a pipeline step reproduces such a test tree byte for byte, the same inputs have to be fed to the step: this tool
finds each wanted (name, md5) among the .drm files of the search folders (recursive; only files with the wanted base
name are hashed) and copies the first match to OUT_DIR/<name>.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/stage_by_md5.py OUT_DIR --search DIR [DIR ...] (--log FIX.log | --want name=md5[,name=md5])
        [--tsv REPORT.tsv]
  --log: lines '<name>.drm (Xbox <pack>, md5 <md5>): ...' as tools/objdata_fx_fix.py check prints them
  --tsv: name TAB md5 TAB source path of every staged file (default OUT_DIR/../staged_sources.tsv)
Exit 1 when a wanted file is not found (the others are staged anyway).
"""
import sys, os, re, hashlib, shutil


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main(argv):
    if not argv or '--search' not in argv: sys.exit(__doc__)
    out = argv[0]
    want = {}
    tsv = None
    if '--tsv' in argv: k = argv.index('--tsv'); tsv = argv[k + 1]; del argv[k:k + 2]
    if '--log' in argv:
        k = argv.index('--log')
        for ln in open(argv[k + 1], encoding='utf-8', errors='replace'):
            m = re.match(r'^(\S+\.drm) \(Xbox [^,]+, md5 ([0-9a-f]{32})\)', ln)
            if m: want.setdefault(m.group(1).lower(), m.group(2))
        del argv[k:k + 2]
    if '--want' in argv:
        k = argv.index('--want')
        for kv in argv[k + 1].split(','):
            n, m = kv.split('='); want[n.lower()] = m.lower()
        del argv[k:k + 2]
    k = argv.index('--search'); dirs = argv[k + 1:]
    if not want or not dirs: sys.exit(__doc__)
    found = {}
    for d in dirs:
        for dp, dn, fn in os.walk(d):
            dn.sort()
            for f in sorted(fn):
                n = f.lower()
                if n not in want or n in found: continue
                p = os.path.join(dp, f)
                if md5(p) == want[n]: found[n] = p
        if len(found) == len(want): break
    os.makedirs(out, exist_ok=True)
    tsv = tsv or os.path.join(os.path.dirname(os.path.abspath(out)), 'staged_sources.tsv')
    rows = []
    for n in sorted(want):
        if n not in found:
            print('NOT FOUND %s md5 %s' % (n, want[n])); continue
        shutil.copyfile(found[n], os.path.join(out, n))
        assert md5(os.path.join(out, n)) == want[n]
        rows.append((n, want[n], found[n].replace('\\', '/')))
        print('staged %s md5 %s from %s' % (n, want[n], found[n]))
    with open(tsv, 'w', encoding='utf-8', newline='\n') as h:
        h.write('name\tmd5\tsource\n')
        for r in rows: h.write('%s\t%s\t%s\n' % r)
    print('staged %d of %d files to %s (sources %s)' % (len(rows), len(want), out, tsv))
    return 0 if len(rows) == len(want) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
