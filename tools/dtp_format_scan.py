"""Find DTP sections of one record format (first 32-bit word, Xbox big-endian) in the Xbox base game and the DLC packs.
(read-only) Prints name, DTP id, size and the header words given with --words, so that examples using optional parts of
a format (non-zero pointers) can be found and their PC versions compared with tools/dtp_word_classes.py.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dtp_format_scan.py 04c20453 [--words 0x24,0x34]
"""
import sys, os, json, struct
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ARCH = ['../data/TombRaiderUnderworld_Patched/' + f for f in ('layer1.000', 'layer2.000', 'TitleUpdate.000')]


def names():
    """name hash -> xenon-w name (Yura file list + DLC names)"""
    from names import load
    xn = load(os.path.join(ROOT, 'ref', 'yura-release', 'FileLists', 'Tomb Raider Underworld (Xenon).txt'))
    return {h: n for h, n in xn.items()}


def scan(job):
    from archive import Archive
    from drm import cdrm_decode, sections_with_data
    path, i, magic, offs = job
    a = Archive(path, 'be'); r = a.idx[i]
    try:
        raw = a.read(r)
        if raw[:4] not in (b'CDRM', b'\0\0\0\x13'): return []
        secs = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]
    except Exception:
        return []
    out = []
    for s in secs:
        d = s['data']
        if s['type'] == 7 and d and len(d) >= 4 and d[:4] == magic:
            out.append((path.split('/')[-1], r['hash'], s['id'], len(d),
                        [struct.unpack_from('>I', d, o)[0] if o + 4 <= len(d) else None for o in offs]))
    return out


def main(argv):
    magic = bytes.fromhex(argv[0]); offs = []
    if '--words' in argv: offs = [int(x, 16) for x in argv[argv.index('--words') + 1].split(',')]
    from archive import Archive
    from convert_dlc import R, PACKS
    jobs = []
    for p in ARCH + [R + q for q in PACKS]:
        if not os.path.exists(p): continue
        a = Archive(p, 'be')
        jobs += [(p, i, magic, offs) for i, r in enumerate(a.idx) if r['spec'] == 0xffffffff]
    nm = names()
    rows = []
    with ProcessPoolExecutor(max_workers=int(os.environ.get('TRUDLC_JOBS_LIGHT') or os.cpu_count())) as ex:
        for res in ex.map(scan, jobs, chunksize=16): rows += res
    seen = set()
    print('DTPs with format %s: %d' % (argv[0], len(rows)))
    for arc, h, sid, size, words in sorted(rows, key=lambda r: (-r[3], r[2])):
        key = (h, sid)
        if key in seen: continue
        seen.add(key)
        print('   %-16s %-40s DTP %6d  %7d bytes  %s' % (arc, nm.get(h, '%08x' % h)[:40], sid, size,
              ' '.join('%#x=%s' % (o, '-' if w is None else '%08x' % w) for o, w in zip(offs, words))))


if __name__ == '__main__':
    main(sys.argv[1:])
