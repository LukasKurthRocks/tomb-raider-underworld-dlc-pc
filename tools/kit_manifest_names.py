"""Which names of a names list does a release kit manifest ship? (read-only)

For each '0x<hash> <full xenon-w name>' line of a names file (default docs/data/dlc_names_extra.txt) it looks in one or
more kit manifests (docs/data/*.kit_manifest.json, format 2: files[].rel / files[].source.name) for
  source  a file whose Xbox source name hashes to the same hash (fcrc, as tools/dlc_names.py)
  rel     a file whose 'rel' is the name below xenon-w\\ ('/' separators), also with a ModLoader language suffix _NNN
and prints one line per name and manifest: 'SHIPPED' (rel and / or source found) or 'MISSING'.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/kit_manifest_names.py [--names docs/data/dlc_names_extra.txt] MANIFEST.json [MANIFEST.json ...]
"""
import sys, os, re, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlc_names import fcrc, EXTRA


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--names', default=EXTRA)
    ap.add_argument('manifests', nargs='+')
    a = ap.parse_args()
    names = []
    for l in open(a.names, encoding='utf8'):
        t = l.split()
        if len(t) == 2 and t[0].startswith('0x'): names.append((int(t[0], 16), t[1]))
    print('names', len(names), 'from', a.names)
    for m in a.manifests:
        files = json.load(open(m, encoding='utf8')).get('files', [])
        by_src = {}
        by_rel = {}
        for e in files:
            s = e.get('source') or {}
            if s.get('name'): by_src.setdefault(fcrc(s['name']), []).append(e['rel'])
            rel = e['rel'].lower()
            by_rel.setdefault(re.sub(r'_\d{3}$', '', rel), []).append(e['rel'])
        print('manifest', os.path.basename(m), 'build', json.load(open(m, encoding='utf8')).get('build'), 'files', len(files))
        miss = 0
        for h, n in names:
            rel = n.split('\\', 1)[1].replace('\\', '/').lower()
            src = by_src.get(h, [])
            rr = by_rel.get(rel, [])
            ok = bool(src or rr)
            miss += not ok
            print('  %-7s 0x%08x %s%s%s' % ('SHIPPED' if ok else 'MISSING', h, n,
                                            ('  source->' + ','.join(src)) if src else '', ('  rel=' + ','.join(rr)) if rr else ''))
        print('  missing', miss, 'of', len(names))


if __name__ == '__main__':
    main()
