r"""Build the repair tree for an installed B138 (DLC 1) from a pristine B138 `mods` copy (tools/b138_snapshot.py),
with the fixes found and tested in game on 2026-10-30 (docs/WINDOWS_REBUILD.md finding 43). Output = a mods-style
folder with only the changed / added files, to install with scripts/windows/Install-TruTree.ps1 over B138.

  1. shaders   tools/shader_const_fix.py over every port shader library: at most one constant register per
               instruction (the "display driver" box when entering DLC 1; 24 files)
  2. ring      dlc1_ei_grapple_wall / _ceiling: the far-LOD materials 21164 / 20345 get the base game's own PC ring
               shaders 1704-1707 (copied from the PC `ar_ei_grapple_wall.drm`), the near-LOD materials 21093 / 20344
               become copies of them (surrogate / translated shaders showed the normal map as colour; test 24); then
               both LODs get the base ring MATERIAL 16637 with its textures (tools/material_transplant.py: the base
               shaders read the slots in the base roles - specular from the DLC normal map looked olive; test 26a)
  3. ui        stage-2b fixes `uipath` + `uitext` (tools/dlc_fixes_build.py) over the B138 files: 25 UI timeline paths
               and 26 text elements in 10 DLC 1 level DRMs (the never-shown Xbox "update required" message; owner's
               decision 2026-10-30, same fixes as DLC 2; test 28)
  4. language  tools/mul_lang_build.py: the cinematic streams in all five languages as `<name>_NNN` (the ModLoader
               loads the game's language, the plain name stays as fallback); pack10, with --dlc2 also pack11

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/b138_fix_tree.py PRISTINE_MODS OUT_MODS [--dlc2] [--replace] [--skip shaders,ring,ui,language]
  OUT_MODS must lie below work/rebuild and apart from PRISTINE_MODS (build_util.check_out)
  --replace: remove an existing OUT_MODS (a '...\mods' folder) and its OUT_MODS_tmp first
"""
import sys, os, shutil, contextlib, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU

RING = {'dlc1_ei_grapple_wall.drm': (21164, 21093), 'dlc1_ei_grapple_ceiling.drm': (20345, 20344)}
BASE_RING, BASE_LIBS, BASE_MATERIAL = 'ar_ei_grapple_wall.drm', [1704, 1705, 1706, 1707], 16637


def run(mod, args):
    """call a tool's main() with argv-style arguments, return its printed output"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = mod.main(list(args))
    if r not in (None, 0): raise SystemExit('%s failed: %s' % (mod.__name__, r))
    return buf.getvalue()


def main(argv):
    skip = set()
    if '--skip' in argv: k = argv.index('--skip'); skip = set(argv[k + 1].split(',')); del argv[k:k + 2]
    dlc2 = '--dlc2' in argv; replace = '--replace' in argv
    argv = [a for a in argv if a not in ('--dlc2', '--replace')]
    src, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
    tmp = out + '_tmp'
    BU.require_dir(src, 'PRISTINE_MODS')
    for d in (out, tmp): BU.check_out(d, src, must_be_below=True)     # below work/rebuild, apart from PRISTINE
    if replace and os.path.basename(out) == 'mods':                     # own output only
        for d in (out, tmp):
            if os.path.isdir(d): shutil.rmtree(d)
    if os.path.isdir(out) or os.path.isdir(tmp): raise SystemExit('output exists: %s (or %s) - remove it first' % (out, tmp))
    os.makedirs(out); os.makedirs(tmp)
    if 'shaders' not in skip:
        import shader_const_fix as SCF
        print('== shaders'); print(run(SCF, [src, out]).strip())
    if 'ring' not in skip:
        import bigfile_extract as BE, material_shader_swap as MSS, material_copy as MC, material_transplant as MT
        print('== ring')
        base = os.path.join(tmp, BASE_RING)
        run(BE, ['pcbig', BASE_RING, base])
        for name, (far, near) in RING.items():
            cur = os.path.join(out, name) if os.path.exists(os.path.join(out, name)) else os.path.join(src, name)
            for slot, lib in enumerate(BASE_LIBS):
                nxt = os.path.join(tmp, '%s.%d' % (name, slot))
                extra = ['--add-libs-from', base, ','.join(map(str, BASE_LIBS))] if slot == 0 else []
                print(run(MSS, [cur, nxt, str(far), str(slot), str(lib)] + extra).strip().splitlines()[-1])
                cur = nxt
            nxt = os.path.join(tmp, '%s.copy' % name)
            print(run(MC, [cur, nxt, str(near), str(far)]).strip())
            # base MATERIAL, not only its shaders: the base shaders read the texture slots in the base roles (test 26a)
            for i, mid in enumerate((far, near)):
                dst = os.path.join(out, name) if i == 1 else os.path.join(tmp, '%s.far' % name)
                print(run(MT, [nxt, dst, str(mid), base, str(BASE_MATERIAL)]).strip().splitlines()[-1])
                nxt = dst
    if 'ui' not in skip:
        import dlc_fixes_build as FB
        print('== ui')
        os.environ['TRUDLC_PACK_FIRST'] = 'pack10'        # B138 = DLC 1: Xbox sources from pack10
        for fx in (FB.fix_uipath, FB.fix_uitext):
            r = fx(out, srcs=[src, out]); print('%s: %d files, %s' % (fx.__name__, len(r['files']), r['log'][-1]))
    if 'language' not in skip:
        import mul_lang_build as MLB
        print('== language')
        for pack in (['pack10', 'pack11'] if dlc2 else ['pack10']):
            print(run(MLB, [out, pack]).strip().splitlines()[-1])
    shutil.rmtree(tmp)
    n = sum(len(fn) for _, _, fn in os.walk(out))
    print('repair tree: %s (%d files)' % (out, n))


if __name__ == '__main__':
    main(sys.argv[1:])
