"""TruMenu 0.9 (P1): list the srmusic tracks and the Bink videos of the PC game with their source and an "unused?" flag
(read-only; writes only into work/ and the --menu-out folder).

Tracks: every music\\<name>\\ folder - base names from the Xenon file list (yura) checked in the PC bigfile / patch
(pc-w\\music\\<name>\\<name>.{mus,sam,mul}), DLC tracks from the installed mods\\music\\ tree of the PC port (pack10 /
pack11 origin from work/generic/dlc_names.txt). Videos: Movies\\*.bik next to tru.exe.

"referenced" = the name occurs as a NUL-terminated ASCII string in a decoded DRM of the PC bigfile / patch / mods tree
(level, script and object data) or in tru.exe. Otherwise the flag is "unused?" - a name search only, so the question
mark stays (a name may be built at run time, e.g. the unit music name 0xd98f64 of 0x5b21d0).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/music_list.py [--game DIR] [--out DIR] [--menu-out DIR] [--no-refs]
    --game      game folder (default ../data/pc, the Steam folder link)
    --out       report folder (default work/media): music_list.txt, video_list.txt
    --menu-out  also write TruMenu.media.txt there (lines "kind<TAB>name<TAB>source<TAB>flags"); not committed
    --no-refs   skip the DRM search (fast; every flag becomes "-")
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from drm import cdrm_decode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLIST = os.path.join(ROOT, 'ref', 'yura-release', 'FileLists', 'Tomb Raider Underworld (Xenon).txt')
DLCN = os.path.join(ROOT, 'work', 'generic', 'dlc_names.txt')


def arg(argv, key, default):
    if key in argv:
        return argv[argv.index(key) + 1]
    return default


def base_names():
    out = set()
    for l in open(XLIST, encoding='utf-8', errors='ignore'):
        p = l.strip().split('\\')
        if len(p) == 4 and p[0].lower() == 'xenon-w' and p[1].lower() == 'music':
            out.add(p[2])
    return sorted(out)


def pack_names():
    """{track: pack} for the music folders named in dlc_names.txt (pack10 = DLC 1, pack11 = DLC 2)"""
    out = {}
    if not os.path.isfile(DLCN): return out
    for l in open(DLCN, encoding='utf8', errors='ignore'):
        t = l.split()
        if len(t) >= 3 and t[-1] != '?':
            p = t[-1].split('\\')
            if len(p) == 4 and p[1].lower() == 'music':
                out.setdefault(p[2], t[1])
    return out


def drm_blobs(game):
    """yield (label, decoded bytes) for every DRM-like entry of the PC bigfile / patch and every mods\\**.drm"""
    for name in ('bigfile.000', 'patch.000'):
        p = os.path.join(game, name)
        if not os.path.isfile(p): continue
        A = Archive(p, 'le')
        for r in A.idx:
            try:
                b = A.read(r)
            except Exception:
                continue
            if b[:4] in (b'CDRM', b'MRDC'):
                try: b = cdrm_decode(b, 'le')
                except Exception: continue
            yield '%s#%08x' % (name, r['hash']), b
    mods = os.path.join(game, 'mods')
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if not f.lower().endswith('.drm'): continue
            b = open(os.path.join(dp, f), 'rb').read()
            if b[:4] in (b'CDRM', b'MRDC'):
                try: b = cdrm_decode(b, 'le')
                except Exception: continue
            yield 'mods\\' + os.path.relpath(os.path.join(dp, f), mods), b


def find_refs(game, names, exe):
    needles = {n: n.lower().encode('latin-1') + b'\0' for n in names}
    hits = {n: [] for n in names}
    ex = exe.lower()
    for n, nd in needles.items():
        if nd in ex: hits[n].append('tru.exe')
    count = 0
    for label, b in drm_blobs(game):
        count += 1
        low = b.lower()
        for n, nd in needles.items():
            if len(hits[n]) < 6 and nd in low:
                hits[n].append(label)
    return hits, count


def main(argv):
    game = arg(argv, '--game', os.path.join(ROOT, '..', 'data', 'pc'))
    out = arg(argv, '--out', os.path.join(ROOT, 'work', 'media'))
    menu_out = arg(argv, '--menu-out', '')
    refs = '--no-refs' not in argv
    os.makedirs(out, exist_ok=True)
    big = [Archive(os.path.join(game, n), 'le') for n in ('bigfile.000', 'patch.000') if os.path.isfile(os.path.join(game, n))]
    packs = pack_names()
    tracks = []                                     # (name, source, files text)
    for d in base_names():
        files = []
        for e in ('mus', 'sam', 'mul'):
            h = crc('pc-w\\music\\%s\\%s.%s' % (d, d, e))
            r = next((x for A in big for x in A.find(h)), None)
            files.append('%s %d' % (e, r['size']) if r else '%s -' % e)
        tracks.append([d, 'base', ', '.join(files)])
    mm = os.path.join(game, 'mods', 'music')
    known = {t[0].lower(): t for t in tracks}
    if os.path.isdir(mm):
        for d in sorted(os.listdir(mm)):
            fp = os.path.join(mm, d)
            if not os.path.isdir(fp): continue
            files = []
            for e in ('mus', 'sam', 'mul'):
                f = os.path.join(fp, '%s.%s' % (d, e))
                files.append('%s %d' % (e, os.path.getsize(f)) if os.path.isfile(f) else '%s -' % e)
            pk = packs.get(d, '')
            src = 'DLC1' if pk == 'pack10' else 'DLC2' if pk == 'pack11' else 'mods'
            if d.lower() in known:
                known[d.lower()][1] += '+%s(mods override)' % src
            else:
                tracks.append([d, src, ', '.join(files)])
    videos = []
    mv = os.path.join(game, 'Movies')
    if os.path.isdir(mv):
        for f in sorted(os.listdir(mv)):
            if f.lower().endswith('.bik'):
                videos.append([f[:-4], 'base' if 'dlc' not in f.lower() else 'DLC1', 'bik %d' % os.path.getsize(os.path.join(mv, f))])
    exe = open(os.path.join(game, 'tru.exe'), 'rb').read()
    hits, scanned = ({}, 0)
    if refs:
        hits, scanned = find_refs(game, [t[0] for t in tracks] + [v[0] for v in videos], exe)

    def flag(n):
        if not refs: return '-'
        return 'referenced' if hits.get(n) else 'unused?'

    with open(os.path.join(out, 'music_list.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# tools/music_list.py; %d DRMs searched (0 = --no-refs)\n' % scanned)
        f.write('# name\tsource\tflag\tfiles\twhere referenced (first 6)\n')
        for n, s, files in tracks:
            f.write('%s\t%s\t%s\t%s\t%s\n' % (n, s, flag(n), files, ', '.join(hits.get(n, []))))
    with open(os.path.join(out, 'video_list.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# tools/music_list.py; %d DRMs searched\n# name\tsource\tflag\tfile\twhere referenced\n' % scanned)
        for n, s, files in videos:
            f.write('%s\t%s\t%s\t%s\t%s\n' % (n, s, flag(n), files, ', '.join(hits.get(n, []))))
    if menu_out:
        os.makedirs(menu_out, exist_ok=True)
        with open(os.path.join(menu_out, 'TruMenu.media.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('# TruMenu media list, generated by tools/music_list.py (kind name source flags); not game data\n')
            for n, s, _ in tracks: f.write('music\t%s\t%s\t%s\n' % (n, s, flag(n)))
            for n, s, _ in videos: f.write('video\t%s\t%s\t%s\n' % (n, s, flag(n)))
    un = sum(1 for t in tracks if flag(t[0]) == 'unused?')
    uv = sum(1 for v in videos if flag(v[0]) == 'unused?')
    print('tracks %d (base %d, other %d), unused? %d; videos %d, unused? %d; DRMs searched %d' % (
        len(tracks), sum(1 for t in tracks if t[1].startswith('base')), sum(1 for t in tracks if not t[1].startswith('base')),
        un, len(videos), uv, scanned))
    print('wrote %s, %s%s' % (os.path.join(out, 'music_list.txt'), os.path.join(out, 'video_list.txt'),
                              (', ' + os.path.join(menu_out, 'TruMenu.media.txt')) if menu_out else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
