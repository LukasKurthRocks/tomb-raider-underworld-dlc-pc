"""Compare two folders file by file (MD5): identical / different / only in A / only in B (read-only).

Used to prove that a parallel run (--jobs N) writes byte-identical files to the sequential run.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/tree_compare.py DIR_A DIR_B
"""
import sys, os, hashlib


def files(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            h = hashlib.md5()
            with open(p, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
            out[os.path.relpath(p, root).replace(os.sep, '/')] = h.hexdigest()
    return out


def main(argv):
    a, b = files(argv[0]), files(argv[1])
    same = [k for k in a if k in b and a[k] == b[k]]
    diff = sorted(k for k in a if k in b and a[k] != b[k])
    only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
    print('files A %d, B %d: identical %d, different %d, only in A %d, only in B %d'
          % (len(a), len(b), len(same), len(diff), len(only_a), len(only_b)))
    for k in diff[:20]: print('  different:', k)
    for k in only_a[:10]: print('  only in A:', k)
    for k in only_b[:10]: print('  only in B:', k)
    sys.exit(0 if not diff and not only_a and not only_b else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
