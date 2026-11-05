"""Compare two upstream release kit manifests (docs/data/*.kit_manifest.json) file by file - read-only.

Per file (key `rel`, case-insensitive): only in A, only in B, same md5, or different md5 (with sizes and whether the
Xbox / PC source record changed too). Prints counts and the lists of added / removed / changed files, grouped by area
(first folder of `rel`, `dlc` field when present).

Usage: python3 -I tools/kit_manifest_diff.py docs/data/B269_nativo.kit_manifest.json docs/data/B270_acqua.kit_manifest.json
"""
import sys, json, collections


def load(path):
    m = json.load(open(path, encoding='utf8'))
    files = {}
    for e in m.get('files', []):
        files[e['rel'].replace('\\', '/').lower()] = e
    return m, files


def area(e):
    rel = e['rel'].replace('\\', '/')
    return '%s %s' % (e.get('dlc') or '-', rel.split('/')[0] if '/' in rel else '(root)')


def src(e):
    s = e.get('source') or {}
    return (s.get('kind'), s.get('name'), s.get('md5'))


def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    (ma, a), (mb, b) = load(sys.argv[1]), load(sys.argv[2])
    print('A', sys.argv[1], 'files', len(a), '| B', sys.argv[2], 'files', len(b))
    for k in ('build', 'name', 'format', 'exe'):
        if k in ma or k in mb: print('  %s: A %s | B %s' % (k, json.dumps(ma.get(k))[:120], json.dumps(mb.get(k))[:120]))
    only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
    same = [k for k in a if k in b and a[k].get('md5') == b[k].get('md5')]
    diff = sorted(k for k in a if k in b and a[k].get('md5') != b[k].get('md5'))
    print('same %d | different %d | only in A %d | only in B %d' % (len(same), len(diff), len(only_a), len(only_b)))
    for title, keys, side in (('only in A', only_a, a), ('only in B', only_b, b)):
        if keys:
            print('\n%s:' % title)
            for k in keys: print('  %-12s %s' % (area(side[k]), side[k]['rel']))
    if diff:
        print('\ndifferent (area, file, size A -> B, source record changed):')
        by = collections.Counter(area(b[k]) for k in diff)
        for k in diff:
            print('  %-12s %s  %s -> %s  %s' % (area(b[k]), b[k]['rel'], a[k].get('size'), b[k].get('size'),
                                              'source changed' if src(a[k]) != src(b[k]) else 'same source'))
        print('\ndifferent per area: ' + ', '.join('%s %d' % kv for kv in sorted(by.items())))


if __name__ == '__main__':
    main()
