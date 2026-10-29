"""Finish a DLC tree for installing/testing: copy a stage-2b tree, replace or drop single files, add the merged string
tables (tools/locals.py build) and the rumble library (tools/padshock_convert.py build), then check the structure.

  --replace REL=PATH  put PATH at REL (e.g. g_pda.drm=work/rebuild/dlc2_merge/g_pda.drm, finding 40); repeatable
  --drop REL          remove REL (e.g. g_pda.drm for DLC 1: B138 ships none); repeatable
locals.py build takes the title-update strings of both DLCs (one table for DLC 1 and DLC 2); padshock is the TU library.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dlc_finish_build.py SRC_MODS_DIR OUT_MODS_DIR [--replace REL=PATH] [--drop REL]
  OUT_MODS_DIR must end in /mods (locals.py writes <OUT>/../mods/local/...) and is replaced on every run
"""
import sys, os, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main(argv):
    rep, drop = [], []
    while '--replace' in argv:
        k = argv.index('--replace'); rel, path = argv[k + 1].split('=', 1); rep.append((rel, path)); del argv[k:k + 2]
    while '--drop' in argv:
        k = argv.index('--drop'); drop.append(argv[k + 1]); del argv[k:k + 2]
    src, out = argv[0], argv[1]
    if os.path.basename(os.path.normpath(out)) != 'mods': sys.exit('OUT_MODS_DIR must end in /mods: ' + out)
    from build_util import replace_tree, require_dir
    for rel, path in rep:
        if not os.path.isfile(path): sys.exit('replacement not found: ' + path)
    replace_tree(src, out)
    for rel, path in rep:
        shutil.copyfile(path, os.path.join(out, rel)); print('replaced', rel, '<-', path)
    for rel in drop:
        p = os.path.join(out, rel)
        if os.path.exists(p): os.remove(p); print('dropped', rel)
        else: print('drop: not present', rel)
    py = [sys.executable, '-u', '-I', '-X', 'utf8']
    for cmd in (['tools/locals.py', 'build', os.path.dirname(os.path.normpath(out))],
                ['tools/padshock_convert.py', 'build', out],
                ['tools/tree_check.py', out, os.path.basename(os.path.dirname(os.path.abspath(out)))]):
        print('==', ' '.join(cmd), flush=True)
        r = subprocess.run(py + cmd, cwd=os.path.join(HERE, '..'))
        if r.returncode: sys.exit('%s failed (exit %d)' % (cmd[0], r.returncode))


if __name__ == '__main__':
    main(sys.argv[1:])
