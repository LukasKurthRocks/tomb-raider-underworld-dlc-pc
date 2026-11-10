"""Compare the record indices of two PC game archives (bigfile.000 + parts), read-only: language spec words,
records only in one of them, same record (hash + spec) with another size. Built for a language-variant survey
(a second retail PC build against our PC 1.1 bigfile); only the 4-byte index is read, never the record data,
unless --names asks for a record by name.

Spec word: a record is found when (spec & mask) == mask, mask = 1 << language (SetLanguage 0x49a900;
tru.exe languages 0 en, 1 fr, 2 de, 3 it, 4 es, 5 ja, 6 pt, 7 pl, 8 uk-en, 9 ru, 10 cs, 11 nl, 12 hu).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/bigfile_lang_diff.py A.000 B.000 [--names LIST.txt] [--show N]
      A, B: bigfile.000 of each build (little endian); LIST: path list to name hashes (default: the PC list)
  ../bin/pyt -t 600 tools/bigfile_lang_diff.py --specs A.000 [--names LIST.txt]
      one archive: spec word histogram with language bits and example names
  ../bin/pyt -t 600 tools/bigfile_lang_diff.py --find A.000 PATH [PATH ...]
      records of these full paths (by name hash), e.g. to probe another platform prefix
  ../bin/pyt -t 600 tools/bigfile_lang_diff.py --extract A.000 PATH SPEC OUT
      one record (spec hex) to a file, CDRM-decoded
  --prefix P: name the hashes with the PC list re-prefixed (pc-w\\ -> P\\), for a build with another root folder
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigfile import read_index
from names import load, L

LANGS = ['en', 'fr', 'de', 'it', 'es', 'ja', 'pt', 'pl', 'uk', 'ru', 'cs', 'nl', 'hu']


def langs_of(spec):
    if spec == 0xffffffff: return 'all'
    return ','.join(n for i, n in enumerate(LANGS) if spec & (1 << i)) or '-'


def specs(idx, nm, show=4):
    c = collections.Counter(r['spec'] for r in idx)
    ex = collections.defaultdict(list)
    for r in idx:
        if len(ex[r['spec']]) < show: ex[r['spec']].append(nm.get(r['hash'], '0x%08x' % r['hash']))
    tot = collections.Counter()
    for r in idx: tot[r['spec']] += r['size']
    for s, k in sorted(c.items(), key=lambda kv: -kv[1]):
        print('  spec %08x  %6d records %8.1f MB  langs %-34s e.g. %s' % (s, k, tot[s] / 1048576.0, langs_of(s), ', '.join(ex[s])))


def main(argv):
    names = L + 'Tomb Raider Underworld (PC).txt'
    if '--names' in argv: k = argv.index('--names'); names = argv[k + 1]; del argv[k:k + 2]
    show = 25
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    nm = load(names)
    remap = {}
    if '--prefix' in argv:                       # B uses another root folder: map its hashes to the pc-w ones
        from names import crc
        k = argv.index('--prefix'); pre = argv[k + 1]; del argv[k:k + 2]
        for h, n in list(nm.items()):
            if n.lower().startswith('pc-w\\'): remap[crc(pre + n[4:])] = h; nm[crc(pre + n[4:])] = n
    if argv and argv[0] == '--specs':
        idx = read_index(argv[1], 'le')
        print('%s: %d records, %d stored zlib-compressed in the index (clen > 0)'
              % (os.path.basename(argv[1]), len(idx), sum(1 for r in idx if r['clen'] > 0)))
        parts = collections.Counter((r['offset'] << 11) // 0x7FF00000 for r in idx)
        print('  records per part file: %s' % ', '.join('.%03d %d' % kv for kv in sorted(parts.items())))
        specs(idx, nm)
        return
    if argv and argv[0] == '--find':             # --find A.000 PATH [PATH ...] : records of these paths (by hash)
        from names import crc
        idx = read_index(argv[1], 'le')
        by = collections.defaultdict(list)
        for r in idx: by[r['hash']].append(r)
        def crc_raw(s, up=False):                # the same CRC-32 without lower-casing (or upper-cased)
            h = 0xffffffff
            for c in (s.upper() if up else s):
                h ^= ord(c) << 24
                for _ in range(8):
                    h = ((h << 1) ^ 0x4c11db7) & 0xffffffff if h & 0x80000000 else (h << 1) & 0xffffffff
            return ~h & 0xffffffff
        for p in argv[2:]:
            for tag, h in (('lower', crc(p)), ('as-is', crc_raw(p)), ('upper', crc_raw(p, True)),
                           ('slash', crc(p.replace('\\', '/')))):
                rs = by.get(h, [])
                print('%08x %-5s %-60s %s' % (h, tag, p, ' '.join('spec %08x size %d' % (r['spec'], r['size']) for r in rs) or '-'))
        return
    if argv and argv[0] == '--size-match':       # --size-match A.000 B.000 : name B's hashes by unique record sizes
        A, B = read_index(argv[1], 'le'), read_index(argv[2], 'le')
        ca = collections.Counter(r['size'] for r in A); cb = collections.Counter(r['size'] for r in B)
        sa = {r['size']: r for r in A if ca[r['size']] == 1}
        pairs = [(sa[r['size']], r) for r in B if cb[r['size']] == 1 and r['size'] in sa]
        print('B records with a size unique in both archives: %d' % len(pairs))
        for a, b in pairs[:show]:
            print('  B %08x spec %08x size %10d  =  A %s spec %08x' % (b['hash'], b['spec'], b['size'],
                                                                     nm.get(a['hash'], '0x%08x' % a['hash']), a['spec']))
        return
    if argv and argv[0] == '--extract':          # --extract A.000 PATH SPEC OUT : one record, CDRM-decoded
        from archive import Archive
        from names import crc
        from drm import cdrm_decode
        A = Archive(argv[1], 'le')
        spec = int(argv[3], 16)
        rs = A.find(crc(argv[2]), spec)
        if not rs: sys.exit('not found: %s spec %08x (specs here: %s)' % (argv[2], spec,
                            ' '.join('%08x' % r['spec'] for r in A.find(crc(argv[2])))))
        d = A.read(rs[0])
        raw = cdrm_decode(d, 'le')
        open(argv[4], 'wb').write(raw)
        print('%s spec %08x: stored %d bytes (%s), written %d bytes -> %s' % (argv[2], spec, len(d), d[:4], len(raw), argv[4]))
        return
    if len(argv) != 2: sys.exit(__doc__)
    A, B = read_index(argv[0], 'le'), read_index(argv[1], 'le')
    if remap:
        for r in B: r['hash'] = remap.get(r['hash'], r['hash'])
        print('B hashes mapped to the pc-w names: %d of %d' % (sum(1 for r in B if r['hash'] in nm), len(B)))
    print('A: %d records, B: %d records' % (len(A), len(B)))
    for tag, idx in (('A', A), ('B', B)):
        print('%s spec words:' % tag); specs(idx, nm)
    ka = {(r['hash'], r['spec']): r for r in A}
    kb = {(r['hash'], r['spec']): r for r in B}
    ha, hb = set(r['hash'] for r in A), set(r['hash'] for r in B)
    print('hashes: A %d, B %d, common %d, only A %d, only B %d' % (len(ha), len(hb), len(ha & hb), len(ha - hb), len(hb - ha)))
    print('records (hash, spec): common %d, only A %d, only B %d' % (len(ka.keys() & kb.keys()), len(ka.keys() - kb.keys()),
                                                                     len(kb.keys() - ka.keys())))
    same = sum(1 for k in ka.keys() & kb.keys() if ka[k]['size'] == kb[k]['size'])
    print('common records with the same size: %d, other size: %d' % (same, len(ka.keys() & kb.keys()) - same))
    for tag, x, y in (('only A', ka, kb), ('only B', kb, ka)):
        ks = sorted(x.keys() - y.keys())
        c = collections.Counter(k[1] for k in ks)
        print('%s by spec: %s' % (tag, ', '.join('%08x (%s) %d' % (s, langs_of(s), n) for s, n in c.most_common())))
        # same hash present in the other build with another spec?
        hs = collections.defaultdict(list)
        for k in y: hs[k[0]].append(k[1])
        other = collections.Counter((k[1], tuple(sorted(hs[k[0]]))) for k in ks if k[0] in hs)
        for (s, os_), n in other.most_common(12):
            print('   %d x spec %08x here, the other build has the same hash as %s' % (n, s, ' '.join('%08x' % v for v in os_)))
            grp = [nm.get(k[0], '0x%08x' % k[0]) for k in ks if k[1] == s and tuple(sorted(hs.get(k[0], []))) == os_]
            byext = collections.Counter(os.path.splitext(g)[1] or '?' for g in grp)
            bydir = collections.Counter(os.path.dirname(g) for g in grp)
            print('      extensions %s; folders %s' % (', '.join('%s %d' % kv for kv in byext.most_common(6)),
                                                    ', '.join('%s %d' % kv for kv in bydir.most_common(6))))
            if n <= 400: print('      e.g. %s' % ', '.join(sorted(grp)[:8]))
        for k in ks[:show]:
            r = x[k]
            print('   %-62s spec %08x size %10d' % (nm.get(k[0], '0x%08x' % k[0]), k[1], r['size']))
    diff = sorted((k for k in ka.keys() & kb.keys() if ka[k]['size'] != kb[k]['size']),
                  key=lambda k: -abs(ka[k]['size'] - kb[k]['size']))
    ext = collections.Counter(os.path.splitext(nm.get(k[0], '?.unnamed'))[1] for k in diff)
    print('other size by extension: %s' % ', '.join('%s %d' % kv for kv in ext.most_common()))
    for k in diff[:show]:
        print('   %-62s spec %08x  A %10d  B %10d' % (nm.get(k[0], '0x%08x' % k[0]), k[1], ka[k]['size'], kb[k]['size']))


if __name__ == '__main__':
    main(sys.argv[1:])
