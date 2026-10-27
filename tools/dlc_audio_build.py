"""Real audio for a stage-1 mods tree (B43): copy the tree, then swap the silent placeholders for converted XMA audio.

  DRMs  wave_swap.swap_file for every .drm, also in sub folders (streamgroups/, cinstream/). wave_swap's own main only
        takes the top folder and looks the Xbox source up by the bare file name (convert_dlc.raw_dlc('x.drm')), which
        misses sub folders; here each worker maps the file name back to its path relative to xenon-w\\.
  .mul  mul_audio_batch.job for every .mul (cinstream, music, audio\\streams) - it already walks sub folders.
Both tools only replace audio payloads of the same length; everything else stays byte-identical (they check it).
Files they skip keep the stage-1 copy. Reports: <OUT>/../wave_swap_report.json, mul_audio_report.json.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_audio_build.py SRC_MODS_DIR OUT_MODS_DIR
  e.g. work/rebuild/stage1/mods work/rebuild/stage2a/mods
"""
import sys, os, json, shutil, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_REL = {}


def _init(rel_by_name):
    """worker: wave_swap looks the Xbox source up by the bare file name - give it the path below xenon-w\\"""
    import wave_swap as WS
    _REL.update(rel_by_name)
    orig = WS.raw_dlc
    WS.raw_dlc = lambda name: orig(_REL.get(name, name))


def _wave_job(args):
    import wave_swap as WS
    return WS.swap_file(args)


def _mul_job(args):
    import mul_audio_batch as MAB
    return MAB.job(args)


def main(argv):
    src, out = argv[0], argv[1]
    if os.path.exists(out):
        rebuild = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')
        if os.path.commonpath([os.path.realpath(out), os.path.realpath(rebuild)]) != os.path.realpath(rebuild):
            sys.exit('output exists and is not below work/rebuild, remove it yourself: ' + out)
        print('replacing previous output', out, flush=True)
        shutil.rmtree(out)
    shutil.copytree(src, out)
    rep_dir = os.path.dirname(os.path.abspath(out))

    drms = []
    for dp, dn, fn in os.walk(src):
        for f in fn:
            if f.endswith('.drm'):
                rel = os.path.relpath(os.path.join(dp, f), src)
                drms.append((os.path.join(dp, f), os.path.join(out, rel), rel))
    names = collections.Counter(os.path.basename(r) for _, _, r in drms)
    assert all(n == 1 for n in names.values()), 'file name used twice: %s' % [k for k, n in names.items() if n > 1]
    rel_by_name = {os.path.basename(r): r.replace('/', '\\').replace(os.sep, '\\') for _, _, r in drms}

    reps = []
    with ProcessPoolExecutor(max_workers=os.cpu_count(), initializer=_init, initargs=(rel_by_name,)) as ex:
        for r in ex.map(_wave_job, [(s, o) for s, o, _ in drms]):
            reps.append(r)
            if r['waves']: print('wave %-50s waves=%4d swapped=%4d  %s' % (r['file'], r['waves'], r['swapped'], r['status']), flush=True)
    json.dump(reps, open(os.path.join(rep_dir, 'wave_swap_report.json'), 'w'), indent=1)
    print('WAVES swapped', sum(r['swapped'] for r in reps), 'files OK', sum(r['status'] == 'OK' for r in reps),
          'skipped', sum(r['status'].startswith('SKIP') for r in reps), flush=True)

    muls = []
    for dp, dn, fn in os.walk(src):
        for f in fn:
            if f.endswith('.mul'):
                rel = os.path.relpath(os.path.join(dp, f), src)
                muls.append((os.path.join(dp, f), os.path.join(out, rel), rel))
    mreps = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for r in ex.map(_mul_job, sorted(muls)):
            mreps.append(r); print('mul  %-70s %s' % (r['file'], r['status']), flush=True)
    json.dump(mreps, open(os.path.join(rep_dir, 'mul_audio_report.json'), 'w'), indent=1)
    print('MUL OK', sum(r['status'] == 'OK' for r in mreps), 'of', len(mreps))


if __name__ == '__main__':
    main(sys.argv[1:])
