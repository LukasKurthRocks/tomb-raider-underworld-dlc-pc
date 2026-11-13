r"""P4a: compare two shader_translate recipes (tsv) group by group (key xlib + smap + dxn + copies).
Usage: ../bin/pyt -t 60 work/p4a_shader_1311/compare_recipe.py OLD.tsv NEW.tsv"""
import sys


def read(p):
    L = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')]
    return {(r['xlib'], r['smap'], r['dxn'], r['copies']): r for r in (dict(zip(L[0], x)) for x in L[1:])}


def main(a):
    A, B = read(a[0]), read(a[1]); same = 0
    for k in sorted(set(A) | set(B)):
        x, y = A.get(k), B.get(k)
        if x is None: print('NEW   xlib %s %s: %s %s %s' % (k[0], k[3][:90], y['action'], y['lib'], y['md5'])); continue
        if y is None: print('GONE  xlib %s %s' % (k[0], k[3][:90])); continue
        d = [c for c in ('action', 'lib', 'md5', 'vs', 'vs_md5', 'lanes_kept') if x[c] != y[c]]
        if d: print('DIFF  xlib %s %s: %s' % (k[0], k[3][:90], '; '.join('%s %s -> %s' % (c, x[c], y[c]) for c in d)))
        else: same += 1
    print('SUMMARY %d groups identical, old %d / new %d groups' % (same, len(A), len(B)))


if __name__ == '__main__':
    main(sys.argv[1:])
