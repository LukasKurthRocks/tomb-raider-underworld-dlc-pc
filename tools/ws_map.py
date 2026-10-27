"""Overview of upstream's work/ws/ folders: per folder the number of files and scripts, the builds its scripts refer to
(B<n>, B<n>_<label>; most frequent first) and the overlay layers they name (mods_fix<n>, mods_<label>).
Output: a Markdown table on stdout (used for docs/WS_MAP.md).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/ws_map.py [WS_DIR]
  default WS_DIR: work/ws
"""
import sys, os, re, collections

BUILD = re.compile(r'\bB\d{1,3}(?:_[a-z0-9]+|[a-z])?\b')
LAYER = re.compile(r'\bmods_(?:fix\d+[a-z_]*|[a-z]+)\b')


def main(argv):
    ws = argv[0] if argv else 'work/ws'
    print('| Folder | Files | Scripts | Builds referenced | Layers referenced |')
    print('|---|---|---|---|---|')
    for d in sorted(os.listdir(ws)):
        p = os.path.join(ws, d)
        if not os.path.isdir(p): continue
        files = scripts = 0
        builds, layers = collections.Counter(), collections.Counter()
        for dp, dn, fn in os.walk(p):
            for f in fn:
                files += 1
                if not f.endswith('.py'): continue
                scripts += 1
                t = open(os.path.join(dp, f), encoding='utf8', errors='ignore').read()
                builds.update(BUILD.findall(t)); layers.update(LAYER.findall(t))
        fmt = lambda c: ', '.join('%s (%d)' % kv for kv in c.most_common(4)) or '-'
        print('| `%s` | %d | %d | %s | %s |' % (d, files, scripts, fmt(builds), fmt(layers)))


if __name__ == '__main__':
    main(sys.argv[1:])
