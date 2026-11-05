"""Assemble the stage-1 mods/ tree of DLC 1 (pack10) in the B138 layout (missing glue, reconstructed).

The upstream tools convert each file kind separately and partly without a command line (music_convert's per-track
loop, convert_streams, mul_convert per file, raw_image_convert.dlc_gen); how their outputs were put together into the
first baselines is not in the repository. This script does it for one pack:

  DRMs        work/generic/out/<pack>/*.drm (dlc_convert_all --write) -> <rel path of the Xbox name>
              (streamgroups/, cinstream/, root); unnamed records get their name from work/generic/dlc_names.txt
  cinstream   xenon-w\\cinstream\\*.mul       -> mul_convert.convert (silent audio)
  audio       xenon-w\\audio\\streams\\**.mul  -> music_convert.convert_streams (silent audio)
  music       xenon-w\\music\\<d>\\<d>.mus/.sam/.mul -> music_convert (as its main loop; silent audio); for pack10
              also the pack11 tracks (DLC 2), as the release kit ships them (docs/INSTALL.md: DLC 2 menu music)
  image       raw_image_convert.dlc_gen (all packs; files of other packs show up as 'extra' in compare_b138)
  tr8         work/generic/merged/tr8/pc-w/* (objlist_merge.py)
locals.bin_* and padshock are written by their own tools (locals.py build, padshock_convert.py build).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_media_build.py [OUT_MODS_DIR] [pack10]
  default OUT_MODS_DIR: work/rebuild/stage1/mods (replaced on every run; must be below work/rebuild)
"""
import sys, os, shutil, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc, load, L
from convert_dlc import R as ROOT, PACKS

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
PACK_INDEX = {'pack10': 0, 'pack11': 1, 'pack1': 2, 'pack2': 3, 'pack20': 4}
# music written for a pack: the B138 kit ships the DLC 2 (pack11) tracks with DLC 1
MUSIC_PACKS = {'pack10': ('pack10', 'pack11')}


def dlc_names(pack):
    """{hash: full xenon-w name} for one pack from dlc_names.txt (columns: hash pack ... name; '?' = unknown)"""
    out = {}
    for l in open(os.path.join(W, 'dlc_names.txt'), encoding='utf8', errors='ignore'):
        t = l.split()
        if len(t) >= 3 and t[1] == pack and t[-1] != '?' and t[-1].lower().startswith('xenon-w\\'):
            out[int(t[0], 16)] = t[-1]
    return out


def rel_of(name):
    return os.path.join(*name.split('\\')[1:])


def main(argv):
    out = argv[0] if argv else 'work/rebuild/stage1/mods'
    pack = argv[1] if len(argv) > 1 else 'pack10'
    st = collections.Counter()
    # build into a fresh tree: files of earlier runs (renamed DRMs, old tracks) would flow into every later stage
    from build_util import check_out
    check_out(out, must_be_below=True)
    if os.path.exists(out): print('replacing previous output', out, flush=True); shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    names = dict(dlc_names(pack)); names.update({h: n for h, n in xn.items()})
    A = Archive(ROOT + PACKS[PACK_INDEX[pack]], 'be')

    # DRMs: file names as dlc_convert_all writes them, placed at the rel path of the full Xbox name
    conv = os.path.join(W, 'out', pack)
    for r in A.idx:
        b = A.read(r)
        if b[:4] not in (b'CDRM', b'\0\0\0\x13'): continue
        short = xn.get(r['hash'], '0x%08x' % r['hash']).split('\\')[-1]
        fn = short if short.endswith('.drm') else short + ('_%08x' % r['spec']) + '.drm'
        full = names.get(r['hash'])
        if full is None: st['drm_unnamed_skipped'] += 1; continue
        src = os.path.join(conv, fn)
        if not os.path.exists(src): st['drm_not_converted'] += 1; continue
        dst = os.path.join(out, rel_of(full))
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); st['drm'] += 1

    # cinstream .mul
    import mul_convert as M, dlc_generic as DG
    ids = DG.DlcIds(None, None)
    for r in A.idx:
        nm = names.get(r['hash'], '')
        if nm.lower().startswith('xenon-w\\cinstream\\') and nm.lower().endswith('.mul') and r['spec'] in (0xffffffff, 0xffffffe1):
            dst = os.path.join(out, rel_of(nm))
            if os.path.exists(dst) and r['spec'] != 0xffffffff: continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(M.convert(A.read(r), ids)); st['cinstream_mul'] += 1

    # audio streams (silent)
    import music_convert as MC
    MC.convert_streams(out, packs=(pack,)); st['audio_streams'] = 'done'

    # music tracks (as music_convert's main loop); tracks named in the base filelist but not in the pack are skipped
    pairs = MC.base_pairs(); MC.template(pairs)
    pc_sam = pairs['l3_chapel_mus_01']['sam'][1]
    for mp in MUSIC_PACKS.get(pack, (pack,)):
        mnames = dict(dlc_names(mp)); mnames.update(xn)
        MA = A if mp == pack else Archive(ROOT + PACKS[PACK_INDEX[mp]], 'be')
        tracks = sorted({n.split('\\')[2] for n in mnames.values() if n.lower().startswith('xenon-w\\music\\') and n.count('\\') == 3})
        for d in tracks:
            files = {}
            for e in ('mus', 'sam', 'mul'):
                rr = MA.find(crc('xenon-w\\music\\%s\\%s.%s' % (d, d, e)))
                if rr: files[e] = MA.read(rr[0])
            if not files: continue
            if len(files) != 3: st['music_incomplete_' + mp] += 1; continue
            ol, T = MC.convert_mul(files['mul'])
            om, bad = MC.convert_mus(files['mus'], T)
            dd = os.path.join(out, 'music', d); os.makedirs(dd, exist_ok=True)
            for e, b in (('mus', om), ('sam', pc_sam), ('mul', ol)): open(os.path.join(dd, '%s.%s' % (d, e)), 'wb').write(b)
            st['music_track_' + mp] += 1

    # images (all packs), then only the image/ subtree goes into the mods tree
    import raw_image_convert as RI
    tmp = os.path.join(os.path.dirname(os.path.abspath(out)), 'images_tmp')
    if os.path.isdir(tmp): shutil.rmtree(tmp)
    RI.dlc_gen(os.path.abspath(tmp))
    if os.path.isdir(os.path.join(tmp, 'image')):
        shutil.copytree(os.path.join(tmp, 'image'), os.path.join(out, 'image'), dirs_exist_ok=True); st['images'] = 'done'
    if os.path.isdir(tmp): shutil.rmtree(tmp)

    # merged object/unit lists
    shutil.copytree(os.path.join(W, 'merged', 'tr8'), os.path.join(out, 'tr8'), dirs_exist_ok=True); st['tr8'] = 'done'

    for k, v in sorted(st.items()): print(k, v)
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1:])
