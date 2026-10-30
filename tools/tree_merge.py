r"""Merge mods-style folders into one (the later folder wins for a file both have) and write a manifest with the
source of every file - to turn a stack of tested trees into one tree that installs with a single
scripts/windows/Install-TruTree.ps1 run (finding 43, pipeline integration). With --check-against GAME_MODS every
merged file is compared with the installed one (MD5): proves the merged tree equals the tested stack.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tree_merge.py OUT_MODS DIR [DIR ...] [--check-against GAME_MODS]
"""
import sys, os, shutil, json, hashlib, collections


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main(argv):
    check = None
    if '--check-against' in argv: k = argv.index('--check-against'); check = argv[k + 1]; del argv[k:k + 2]
    out, dirs = os.path.abspath(argv[0]), argv[1:]
    if os.path.isdir(out): raise SystemExit('output exists: %s - remove it first' % out)
    src = {}
    for d in dirs:
        for dp, dn, fn in os.walk(d):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), d).replace('\\', '/')
                src[rel] = os.path.join(dp, f)
    man = {}
    for rel, p in sorted(src.items()):
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copy2(p, q)
        man[rel] = dict(source=os.path.relpath(p).replace('\\', '/'), md5=md5(q))
    json.dump(man, open(os.path.join(os.path.dirname(out), 'merge_manifest.json'), 'w'), indent=1)
    per = collections.Counter(v['source'].split('/mods/')[0] for v in man.values())
    for k, v in per.items(): print('  %4d from %s' % (v, k))
    print('merged %d files -> %s' % (len(man), out))
    if check:
        st = collections.Counter()
        for rel, v in man.items():
            g = os.path.join(check, rel)
            st['same' if os.path.exists(g) and md5(g) == v['md5'] else ('missing in game' if not os.path.exists(g) else 'DIFFERENT')] += 1
            if os.path.exists(g) and md5(g) != v['md5'] and st['DIFFERENT'] <= 10: print('  DIFFERENT:', rel)
        print('against the installed game:', dict(st))


if __name__ == '__main__':
    main(sys.argv[1:])
