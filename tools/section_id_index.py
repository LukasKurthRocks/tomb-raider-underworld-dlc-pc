"""Which base-game / DLC DRM records hold a section (type, id), with its size - from the section indices
work/idx_pc.json (PC patch + bigfile), work/idx_xbox_base.json (Xbox layer1 / layer2 / TitleUpdate) and
work/idx_dlc.json (Xbox DLC packs), named through the yura file lists where possible. Read-only, no decoding.

Written for the thrall unload crash (2026-11-04, docs Befund-Thrall-Absturz.md section 9): which main-game DRMs carry
the base-class script of the thralls (PC 12433 / Xbox 8453), so it is known which version is resident when DLC 2 thralls
load.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/section_id_index.py pc|xbox|dlc TYPE ID [ID ...]
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = {'pc': 'idx_pc.json', 'xbox': 'idx_xbox_base.json', 'dlc': 'idx_dlc.json'}


def names(kind):
    """{(archive basename, record index): DRM name} via the archive name hashes (best effort)"""
    from names import load, L, crc
    from archive import Archive
    lst = load(L + ('Tomb Raider Underworld (PC).txt' if kind == 'pc' else 'Tomb Raider Underworld (Xenon).txt'))
    return lst, crc


def main(argv):
    kind, typ = argv[0], int(argv[1]); want = set(int(x) for x in argv[2:])
    idx = json.load(open(os.path.join(HERE, '..', 'work', IDX[kind])))
    hits = collections.defaultdict(list)
    for rec in idx:
        secs = rec[5] or []
        for s in secs:
            if s[0] == typ and s[1] in want:
                hits[s[1]].append((rec[0], rec[1], rec[3], s[2]))
    # names: the record's name hash (archive index entry #i) looked up in the yura file list
    rev = {}
    try:
        from names import load, L
        from archive import Archive
        lst = load(L + ('Tomb Raider Underworld (PC).txt' if kind == 'pc' else 'Tomb Raider Underworld (Xenon).txt'))
        arcs = {}
        for path in set(h[0] for v in hits.values() for h in v):
            arcs[path] = Archive(path, 'le' if kind == 'pc' else 'be')
        for v in hits.values():
            for path, i, spec, size in v:
                rev[(path, i)] = lst.get(arcs[path].idx[i]['hash'], '?')
    except Exception as x:
        print('names not resolved: %s' % x)
    for sid in sorted(hits):
        sizes = collections.Counter(h[3] for h in hits[sid])
        print('type %d id %d: %d records, sizes %s' % (typ, sid, len(hits[sid]), dict(sizes)))
        for path, i, spec, size in hits[sid]:
            print('   %s #%d spec %08x size %d %s' % (os.path.basename(path), i, spec & 0xffffffff, size, rev.get((path, i), '')))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
