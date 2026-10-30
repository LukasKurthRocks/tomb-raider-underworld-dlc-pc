r"""Rebuild a pristine copy of the installed B138 `mods\` tree, verified file by file against the kit manifest
(read-only on the game folder). Every output file of the kit (manifest `files[].rel` / `md5`) is taken from the
first candidate whose MD5 matches: the game's `mods\<rel>`, else the backups of `Install-TruTree.ps1`
(`<workspace>\backup\tree_*\files\<rel>`, also the `.restored` ones). So test trees stacked over B138 do not have to
be undone to get the B138 originals as the input of a fix step (finding 43, pipeline integration of the fixes).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/b138_snapshot.py KIT_MANIFEST.json GAME_MODS_DIR BACKUP_ROOT OUT_MODS_DIR [EXTRA_DIR ...]
  e.g. ../release/B138/kit/manifest.json "<game>/mods" ../backup work/rebuild/b138_pristine/mods
       ../backup/mods work/rebuild/base_b138
  EXTRA_DIR: searched recursively by file name, also Install-TruModFile backups named '<name>.<md5>'
  OUT_MODS_DIR must lie below work/rebuild; an existing one is replaced. Exit 1 when a non-optional file is missing.
"""
import sys, os, json, glob, hashlib, shutil, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main(argv):
    man, game, backups, out = argv[:4]
    extra = argv[4:]          # more folders, searched recursively by file name (also 'name.<md5>' backups)
    BU.require_dir(game, 'GAME_MODS_DIR')
    BU.check_out(out, game, must_be_below=True)           # own output below work/rebuild: replaced, never merged
    if os.path.exists(out): print('replacing previous output', out); shutil.rmtree(out)
    by_name = collections.defaultdict(list)
    for d in extra:
        for dp, dn, fn in os.walk(d):
            for x in fn: by_name[x.split('.')[0] + '.' + x.split('.')[1] if x.count('.') >= 2 else x].append(os.path.join(dp, x))
    files = json.load(open(man))['files']
    trees = sorted(glob.glob(os.path.join(backups, 'tree_*')))
    st = collections.Counter(); missing = []
    for f in files:
        rel = f['rel']
        cands = [os.path.join(game, rel)] + [os.path.join(t, 'files', rel) for t in trees] + by_name.get(os.path.basename(rel), [])
        hit = next((c for c in cands if os.path.exists(c) and os.path.getsize(c) == f['size'] and md5(c) == f['md5']), None)
        if hit is None:
            st['missing' + (' (optional %s)' % f['optional'] if f.get('optional') else '')] += 1; missing.append(rel); continue
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copy2(hit, q)
        st['from game' if hit == cands[0] else 'from backup'] += 1
    for m in missing[:20]: print('  missing:', m)
    print(dict(st), 'of', len(files))
    need = [f['rel'] for f in files if f['rel'] in missing and not f.get('optional')]
    if need: raise SystemExit('%d B138 files not found with the manifest MD5 - the snapshot is incomplete' % len(need))


if __name__ == '__main__':
    main(sys.argv[1:])
