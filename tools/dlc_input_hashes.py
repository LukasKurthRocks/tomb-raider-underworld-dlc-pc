"""Read-only: size + MD5 + SHA-1 of every file below an Xbox 360 content folder (title 534307EC, type 00000002), and
whether each entry is a Xenia-extracted folder or a raw STFS package file (magic CON / LIVE / PIRS). Night analysis
2026-11-03 (installer accepts raw LIVE packages): the reference hashes the installer would check after extracting a
raw package with tools/stfs_extract.py. Hashes only - no game bytes are written.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/dlc_input_hashes.py CONTENT_DIR [--tsv OUT.tsv]
  e.g. ../bin/pyt -t 900 tools/dlc_input_hashes.py ../input/xbox-dlc --tsv work/night_analyses/dlc_input_hashes.tsv
"""
import sys, os, hashlib


def digest(path):
    m, s = hashlib.md5(), hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            m.update(b); s.update(b)
    return m.hexdigest(), s.hexdigest()


def main(argv):
    if not argv: sys.exit(__doc__)
    root = argv[0]
    tsv = argv[argv.index('--tsv') + 1] if '--tsv' in argv else None
    rows = []
    for entry in sorted(os.listdir(root)):
        p = os.path.join(root, entry)
        if os.path.isfile(p):
            with open(p, 'rb') as f: magic = f.read(4)
            kind = 'raw package (%s)' % magic.decode('latin-1') if magic in (b'CON ', b'LIVE', b'PIRS') else 'file'
            md5, sha1 = digest(p)
            rows.append((entry, '', kind, os.path.getsize(p), md5, sha1))
            continue
        for dp, dn, fn in os.walk(p):
            dn.sort()
            for n in sorted(fn):
                q = os.path.join(dp, n)
                md5, sha1 = digest(q)
                rows.append((entry, os.path.relpath(q, p).replace(os.sep, '/'), 'extracted', os.path.getsize(q), md5, sha1))
    lines = ['content_name\tfile\tkind\tsize\tmd5\tsha1'] + ['%s\t%s\t%s\t%d\t%s\t%s' % r for r in rows]
    print('\n'.join(lines))
    if tsv:
        os.makedirs(os.path.dirname(os.path.abspath(tsv)), exist_ok=True)
        with open(tsv, 'w', encoding='utf-8', newline='\n') as f: f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
