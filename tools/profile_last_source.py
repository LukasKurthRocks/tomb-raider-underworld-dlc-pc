"""Which file a test profile installs last (read-only; agent N7 04.11.2026).

tests/profiles/*.json install their "trees" in order (every file of the source, sub folders included, except the top
folders in "exclude", default local / padshock; scripts/windows/Install-TruTree.ps1), then the "files" entries; a later
source overwrites an earlier one. This tool replays that order without touching the game folder and prints, per file
name, the source that ends up installed and its md5.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/profile_last_source.py PROFILE.json NAME [NAME ...] [--installed RUN/installed.json]
        last source + md5 of each NAME (bare .drm name, matched case-insensitively against the relative path);
        --installed compares with the md5 a run recorded
  ../bin/pyt -t 300 tools/profile_last_source.py paths PROFILE.json
        absolute path of the last source of every installed .drm (one per line)
  ../bin/pyt -t 300 tools/profile_last_source.py which PROFILE_GLOB NAME [NAME ...]
        for each NAME the profiles (glob, e.g. "tests/profiles/paket*.json") that install it at all
"""
import sys, os, json, glob, hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WS = os.path.abspath(os.path.join(ROOT, '..'))


def resolve(p):
    p = p.replace('/', os.sep)
    return p if os.path.isabs(p) else os.path.join(WS, p)


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def installed_map(profile):
    """{relative path lower: (source file, tree / file source string, order index)}"""
    prof = json.load(open(profile, encoding='utf-8-sig'))
    out = {}
    for k, t in enumerate(prof.get('trees') or []):
        if not t:
            continue
        src = resolve(t['source'])
        ex = [e.lower() for e in (t.get('exclude') if t.get('exclude') is not None else ['local', 'padshock'])]
        for r, _, fs in os.walk(src):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), src).replace('\\', '/')
                top = rel.split('/')[0].lower()
                if '/' in rel and top in ex:
                    continue
                out[rel.lower()] = (os.path.join(r, f), t['source'], k)
    for k, f in enumerate(prof.get('files') or []):
        if not f:
            continue
        out[f['name'].replace('\\', '/').lower()] = (resolve(f['source']), f['source'], 1000 + k)
    return out


def find(m, name):
    n = name.lower()
    hits = [k for k in m if k == n or k.split('/')[-1] == n]
    return hits


def main(a):
    if not a:
        sys.exit(__doc__)
    if a[0] == 'paths':
        # one absolute path per installed .drm (the last source), e.g. as arguments of a scan tool via xargs
        for rel, (path, src, k) in sorted(installed_map(a[1]).items()):
            if rel.endswith('.drm'):
                print(path.replace('\\', '/'))
        return
    if a[0] == 'which':
        profs = sorted(glob.glob(os.path.join(ROOT, a[1])) or glob.glob(a[1]))
        maps = {os.path.basename(p): installed_map(p) for p in profs}
        for n in a[2:]:
            who = [p for p, m in maps.items() if find(m, n)]
            print('%-45s %s' % (n, ', '.join(who) if who else 'NOT IN ANY PROFILE'))
        return
    inst = {}
    if '--installed' in a:
        k = a.index('--installed')
        for e in json.load(open(a[k + 1], encoding='utf-8-sig')):
            inst[e['path'].replace('\\', '/').split('/', 1)[-1].lower()] = e['md5']
        del a[k:k + 2]
    m = installed_map(a[0])
    for n in a[1:]:
        hits = find(m, n)
        if not hits:
            print('%-45s NOT INSTALLED by %s' % (n, os.path.basename(a[0])))
            continue
        for h in hits:
            path, src, k = m[h]
            h5 = md5(path)
            note = ''
            if h in inst:
                note = ' run md5 %s %s' % (inst[h], 'same' if inst[h] == h5 else 'DIFFERS')
            print('%-45s tree %2d %-58s md5 %s%s' % (h, k, src, h5, note))


if __name__ == '__main__':
    main(sys.argv[1:])
