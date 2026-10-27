"""Stage 2b of the DLC 1 rebuild: apply upstream's data fixes, in order, to a copy of the stage-2a tree.

Each fix is one function below, in the order of docs/WINDOWS_REBUILD.md finding 20; it reads the current OUT tree and
replaces the files it fixes there. Upstream's own scripts in work/ws/ are called, not copied.

  cine   B44/B45: cutscene command lists and effect DTPs of cinstream/pdlc1_010_intro.drm and pdlc1_030_finale.drm
         (work/ws/cine/build_cine.py; command rules validated 106/106 on the base game, effect rules learned from
         the base pairs)

Report: <OUT>/../fixes_report.json (per fix: files, log lines).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dlc_fixes_build.py SRC_MODS_DIR OUT_MODS_DIR [--only fix,fix]
  e.g. work/rebuild/stage2a/mods work/rebuild/stage2b/mods
"""
import sys, os, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(HERE, '..', 'work', 'ws')


def fix_cine(out):
    sys.path.insert(0, os.path.join(WS, 'cine'))
    import build_cine as BC, fxdtp as F
    tab = F.learn(F.samples())
    log = []
    for nm in ('pdlc1_010_intro', 'pdlc1_030_finale'):
        p = os.path.join(out, 'cinstream', nm + '.drm')
        tmp = p + '.new'
        log += BC.build(nm, p, tmp, tab)
        os.replace(tmp, p)
    return {'files': ['cinstream/pdlc1_010_intro.drm', 'cinstream/pdlc1_030_finale.drm'], 'log': log}


FIXES = [('cine', fix_cine)]


def main(argv):
    only = None
    if '--only' in argv:
        k = argv.index('--only'); only = set(argv[k + 1].split(',')); del argv[k:k + 2]
    src, out = argv[0], argv[1]
    if os.path.exists(out):
        rebuild = os.path.realpath(os.path.join(HERE, '..', 'work', 'rebuild'))
        if os.path.commonpath([os.path.realpath(out), rebuild]) != rebuild:
            sys.exit('output exists and is not below work/rebuild, remove it yourself: ' + out)
        print('replacing previous output', out, flush=True)
        shutil.rmtree(out)
    shutil.copytree(src, out)
    report = {}
    for name, fn in FIXES:
        if only and name not in only: continue
        print('== fix', name, flush=True)
        r = fn(out)
        for l in r['log']: print('  ', l, flush=True)
        report[name] = r
    json.dump(report, open(os.path.join(os.path.dirname(os.path.abspath(out)), 'fixes_report.json'), 'w'), indent=1)
    print('fixes applied:', ', '.join(report) or '-')


if __name__ == '__main__':
    main(sys.argv[1:])
