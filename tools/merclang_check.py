"""Offline check for TruMercLang.asi (merc barks in another language): which record would the game's file lookup pick
for every merc voice stream, with the game language's mask and with the chosen one (read-only, index only - no
record is read).

The archive index (hash table + 16-byte records size / offset / spec / clen) is what ArchiveFileSystem::FindEntry
(tru.exe 0x4726e0) searches: a binary search over the sorted hashes, then - among the records with the same hash -
the first one with (spec & mask) == mask, probing the landing index, then backwards, then forwards. That search is
ported 1:1 below, so the record picked here is the one the game picks (as long as the archive keeps its file order
in memory). Mask = 1 << language (en 0, fr 1, de 2, it 3, es 4 - tru.exe SetLanguage 0x49a900).

Per name under the filter (default \\vo\\enemy\\merc\\) the result is one of
  redirect   the chosen language has its own record (different from the game language's one)
  same       both masks pick the same record (language-neutral, spec ffffffff - e.g. voice m11, all gat barks)
  fallback   no record for the chosen language - the plugin keeps the game's record
  absent     no record for the game language either (would not play at all)
and the tool also reports hash groups that mix a neutral record with language records (the pick then depends on
the record order) and whether the index is sorted (the binary search needs it).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/merclang_check.py [SRC ...] [--lang es] [--game de] [--filter /vo/enemy/merc/]
                                            [--list] [--tsv OUT.tsv]
      SRC = archive keys of tools/locals.SRC (default: pcbig pcpatch). --filter takes / or \\ (Git Bash mangles \\).
      --list prints every name with its specs and both picks; --tsv writes the same table to a file.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L

LANGS = {'en': 0, 'fr': 1, 'de': 2, 'it': 3, 'es': 4}
SPEC_NAME = {0xffffffe1: 'en', 0xffffe002: 'fr', 0xffffe004: 'de', 0xffffe008: 'it', 0xffffe010: 'es',
             0xffffffff: 'all'}


def half(x):
    # cdq; sub eax, edx; sar eax, 1 = signed division by 2 rounding toward zero
    return x // 2 if x >= 0 else -((-x) // 2)


def find_entry(h, spec, target, mask):
    """Index of the record tru.exe 0x4726e0 returns for this hash and mask, or None (port of 0x4726e0-0x472872)."""
    n = len(h)
    if n == 0:
        return None
    ecx = half(n)
    prev = n                        # [esp+0x10]
    edi = ecx + 1
    esi = n - ecx
    while True:
        ebx = ecx
        v = h[ecx]
        if target > v:              # 0x47271e
            if esi < 2:
                return None
            ecx += half(esi)
            esi += ebx - ecx
            edi = ecx - ebx
            prev = ebx
            continue
        if target < v:              # 0x472742
            if edi < 2:
                return None
            ecx -= half(edi)
            edi += ecx - ebx
            esi = ebx - ecx
            prev = ebx
            continue
        break
    if spec[ecx] & mask == mask:    # 0x4727c6: returns 0 when the landing index equals the previous probe
        return ecx if prev != ecx else None
    i = ecx - 1                     # 0x4727e5 backwards over equal hashes
    while i >= 0 and h[i] == target:
        if spec[i] & mask == mask:
            return i
        i -= 1
    i = ecx + 1                     # 0x47281d forwards
    while i < n and h[i] == target:
        if spec[i] & mask == mask:
            return i
        i += 1
    return None


def main(argv):
    opts = {'--lang': 'es', '--game': 'de', '--filter': '/vo/enemy/merc/', '--tsv': None}
    listing = False
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in opts:
            opts[a] = argv[i + 1]; i += 2; continue
        if a == '--list':
            listing = True; i += 1; continue
        rest.append(a); i += 1
    for k in ('--lang', '--game'):
        if opts[k] not in LANGS:
            sys.exit('%s must be one of %s' % (k, ' '.join(LANGS)))
    flt = opts['--filter'].replace('/', '\\').lower()
    mask = 1 << LANGS[opts['--lang']]
    gmask = 1 << LANGS[opts['--game']]
    srcs = rest or ['pcbig', 'pcpatch']
    import locals as LC
    rows = []
    for src in srcs:
        path, e, pre = LC.SRC[src]
        names = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
        A = Archive(path, e)
        h = [r['hash'] for r in A.idx]
        spec = [r['spec'] for r in A.idx]
        unsorted = sum(1 for k in range(1, len(h)) if h[k] < h[k - 1])
        groups = collections.defaultdict(list)
        for k, x in enumerate(h):
            groups[x].append(k)
        hits = {x: n for x, n in names.items() if flt in n.lower() and x in groups}
        stats = collections.Counter()
        mixed = []
        for x in sorted(hits, key=lambda y: hits[y].lower()):
            specs = [spec[k] for k in groups[x]]
            if 0xffffffff in specs and len(set(specs)) > 1:
                mixed.append(hits[x])
            pg = find_entry(h, spec, x, gmask)
            pc = find_entry(h, spec, x, mask)
            if pg is None and pc is None:
                kind = 'absent'
            elif pc is None:
                kind = 'fallback'
            elif pg == pc:
                kind = 'same'
            else:
                kind = 'redirect'
            stats[kind] += 1
            rows.append((src, hits[x].lower(), kind, ' '.join(SPEC_NAME.get(s, '%08x' % s) for s in specs),
                         '-' if pg is None else '%08x' % spec[pg], '-' if pc is None else '%08x' % spec[pc]))
        print('%s: %d records, index %s, %d names under %s; game %s (mask 0x%02x) -> chosen %s (mask 0x%02x): %s'
              % (src, len(h), 'sorted' if not unsorted else '%d hashes out of order' % unsorted, len(hits), flt,
                 opts['--game'], gmask, opts['--lang'], mask,
                 ', '.join('%s %d' % (k, stats[k]) for k in ('redirect', 'same', 'fallback', 'absent'))))
        print('  hash groups mixing a neutral record with language records: %d%s'
              % (len(mixed), (' (' + ', '.join(mixed[:10]) + ')') if mixed else ''))
        same = [r[1] for r in rows if r[0] == src and r[2] == 'same']
        if same:
            per = collections.Counter()
            for n in same:
                base = n.rsplit('\\', 1)[-1]
                parts = base.split('_')
                per['_'.join(parts[:3]) if len(parts) >= 3 else base] += 1
            print('  unchanged (same record in both languages), per voice_category: '
                  + ', '.join('%s %d' % kv for kv in sorted(per.items())))
        for kind in ('fallback', 'absent'):
            names_k = [r[1] for r in rows if r[0] == src and r[2] == kind]
            if names_k:
                print('  %s: %s' % (kind, ', '.join(names_k[:40]) + (' ...' if len(names_k) > 40 else '')))
    if listing:
        for r in rows:
            print('%-8s %-62s %-9s %-26s game %-8s chosen %s' % r)
    if opts['--tsv']:
        with open(opts['--tsv'], 'w', encoding='utf-8', newline='\n') as f:
            f.write('src\tname\tresult\tspecs\tgame_pick\tchosen_pick\n')
            for r in rows:
                f.write('\t'.join(r) + '\n')
        print('table: %s (%d rows)' % (opts['--tsv'], len(rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
