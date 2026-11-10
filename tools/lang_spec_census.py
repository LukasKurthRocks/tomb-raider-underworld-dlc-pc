"""Census of the language specialisation words of whole game archives (read-only, index only - no record is read).

Answers "is there any Dutch (or other) speech?" for every record, named or not. A record serves language n when
(spec & (1 << n)) == (1 << n) - the test of ArchiveFileSystem::FindEntry 0x4726e0 with the mask 1 << language that
SetLanguage 0x49a900 sets. EN ffffffe1 serves bits 0 and 5..31 (every language without an own record falls back to
it), FR ffffe002, DE ffffe004, IT ffffe008, ES ffffe010, neutral ffffffff. "own bitN" = a record that serves bit N
but not bit 0 (English), i.e. a language-own record. Dutch is game language 11 (SubtitleLanguage 11, mask 0x800):
a Dutch-own record would show as "own bit11"; bit 5 is counted as well.

Groups: cinstream, audio\\streams\\vo\\<folder>, other audio\\streams, music, local (text tables), .drm, other,
unnamed (hash not in the Yura list of the platform). For each group: records per exact spec word, and the number of
distinct names that have a language-own record per bit.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/lang_spec_census.py [SRC ...] [--names REGEX] [--mods DIR]
      SRC     archive keys of tools/locals.SRC (default: pcbig pcpatch pack10 pack11)
      --names print every language-specific named record whose path matches REGEX with its spec words
      --mods  also count the language suffixes _NNN of the files under DIR (the installed mods\\ tree of the port)
      --bink  also list the audio track ids of the Bink videos in DIR (e.g. ../data/pc/Movies)
  An empty SRC list with --mods / --bink only: give the key "none".
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L

SPEC = {0xffffffe1: 'en', 0xffffe002: 'fr', 0xffffe004: 'de', 0xffffe008: 'it', 0xffffe010: 'es', 0xffffffff: 'all'}


def group_of(n):
    if n is None: return 'unnamed'
    nl = n.lower()
    if '\\cinstream\\' in nl: return 'cinstream'
    if '\\audio\\streams\\vo\\' in nl:
        p = nl.split('\\audio\\streams\\vo\\', 1)[1].split('\\')
        return 'vo\\' + '\\'.join(p[:-1][:2])
    if '\\audio\\streams\\' in nl: return 'streams\\' + nl.split('\\audio\\streams\\', 1)[1].split('\\')[0]
    if '\\music\\' in nl: return 'music'
    if '\\local\\' in nl: return 'local'
    if nl.endswith('.drm'): return '.drm'
    return 'other'


def own_bits(spec):
    """language bits 1..12 this record serves while it does not serve bit 0 (English)"""
    if spec & 1: return []
    return [b for b in range(1, 13) if spec & (1 << b)]


def census(src):
    import locals as LC
    path, e, pre = LC.SRC[src]
    if not os.path.isfile(path):
        print('%s: %s not found - skipped' % (src, path)); return None
    names = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
    A = Archive(path, e)
    specs = collections.defaultdict(collections.Counter)      # group -> spec -> records
    own = collections.defaultdict(lambda: collections.defaultdict(set))   # group -> bit -> hashes
    allspec = collections.Counter()
    for r in A.idx:
        n = names.get(r['hash'])
        g = group_of(n)
        specs[g][r['spec']] += 1
        allspec[r['spec']] += 1
        for b in own_bits(r['spec']):
            own[g][b].add(r['hash'])
    print('== %s (%s, %d records)' % (src, os.path.basename(path), len(A.idx)))
    print('   spec words over the whole archive: ' +
          ', '.join('%08x %s=%d' % (s, SPEC.get(s, '?'), c) for s, c in sorted(allspec.items())))
    for b in (5, 11):
        n = sum(c for s, c in allspec.items() if (s & (1 << b)) and not (s & 1))
        print('   records serving bit %d (0x%x) without serving English: %d' % (b, 1 << b, n))
    for g in sorted(specs):
        row = ', '.join('%s %d' % (SPEC.get(s, '%08x' % s), c) for s, c in sorted(specs[g].items()))
        ow = ' | own names: ' + ', '.join('bit%d %d' % (b, len(h)) for b, h in sorted(own[g].items())) if own[g] else ''
        print('   %-26s %s%s' % (g, row, ow))
    return A, names


def list_names(A, names, pat):
    per = collections.defaultdict(list)
    for r in A.idx:
        n = names.get(r['hash'])
        if n and pat.search(n): per[n].append(SPEC.get(r['spec'], '%08x' % r['spec']))
    for n in sorted(per):
        if per[n] != ['all']: print('   %-78s %s' % (n, ' '.join(sorted(per[n]))))   # language-specific names only


def mods_census(d):
    suf = collections.defaultdict(collections.Counter)
    rx = re.compile(r'^(.*)_(\d{3})$')
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if 'truguard' not in x.lower()]
        rel = os.path.relpath(root, d).lower()
        top = 'cinstream' if rel.startswith('cinstream') else ('\\'.join(rel.split(os.sep)[:4]) if rel.startswith('audio') else rel.split(os.sep)[0])
        for f in files:
            if 'truguard' in f.lower(): continue
            m = rx.match(f)
            suf[top][m.group(2) if m else 'plain'] += 1
    print('== mods tree %s (file name suffix _NNN = ModLoader language variant)' % d)
    for t in sorted(suf):
        print('   %-40s %s' % (t, ', '.join('%s %d' % kv for kv in sorted(suf[t].items()))))


def bink_tracks(d):
    """audio tracks of every Movies\\*.bik (Bink 1 header: track count at 0x28, per track 4 B + 4 B rate/flags, then
    4 B track ids); tru.exe picks track [0x8906b8] (game language, >= 13 -> 0) with BinkSetSoundTrack at 0x4a0d9e"""
    import struct
    print('== Bink videos %s (audio track ids; the game asks for track = game language)' % d)
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith('.bik'): continue
        with open(os.path.join(d, f), 'rb') as fh: h = fh.read(0x2c + 12 * 32)
        if h[:3] != b'BIK':
            print('   %-28s not a Bink 1 file (%r)' % (f, h[:4])); continue
        n = struct.unpack_from('<I', h, 0x28)[0]
        if n > 32:
            print('   %-28s track count %d (implausible, skipped)' % (f, n)); continue
        ids = struct.unpack_from('<%dI' % n, h, 0x2c + 8 * n) if n else ()
        print('   %-28s %d audio track(s), ids %s' % (f, n, list(ids)))


def main(argv):
    pat = None; mods = None; bink = None
    if '--bink' in argv:
        i = argv.index('--bink'); bink = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    if '--names' in argv:
        i = argv.index('--names'); pat = re.compile(argv[i + 1], re.I); argv = argv[:i] + argv[i + 2:]
    if '--mods' in argv:
        i = argv.index('--mods'); mods = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    for src in (argv or ['pcbig', 'pcpatch', 'pack10', 'pack11']):
        if src == 'none': continue
        res = census(src)
        if res and pat: list_names(res[0], res[1], pat)
    if mods: mods_census(mods)
    if bink: bink_tracks(bink)


if __name__ == '__main__':
    main(sys.argv[1:])
