"""Which base-game DRM records hold a section of a given type and SIZE (optionally together with a second size) -
from the section indices of tools/section_id_index.py (work/idx_pc.json, idx_xbox_base.json, idx_dlc.json), named
through the yura file lists. Read-only, no decoding.

Night 04.11. (workspace docs Befund-Restrisiken-0411.md, task B): find a base-game file whose DTPs have the layout
of dlc_fx_cine_object DTP 26644 (604 bytes, two records naming 12736-byte table DTPs), for a base-pair byte check.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_size_find.py pc|xbox|dlc TYPE SIZE [--with SIZE2] [--max N]
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import section_id_index as SI


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    w2 = opt('--with', None); mx = int(opt('--max', '40'))
    kind, typ, size = argv[0], int(argv[1]), int(argv[2])
    idx = json.load(open(os.path.join(SI.HERE, '..', 'work', SI.IDX[kind])))
    from names import load, L
    from archive import Archive
    lst = load(L + ('Tomb Raider Underworld (PC).txt' if kind == 'pc' else 'Tomb Raider Underworld (Xenon).txt'))
    arcs = {}; n = 0
    for rec in idx:
        secs = rec[5] or []
        hit = [s for s in secs if s[0] == typ and s[2] == size]
        if not hit: continue
        if w2 is not None and not any(s[0] == typ and s[2] == int(w2) for s in secs): continue
        n += 1
        if n > mx: continue
        path, i = rec[0], rec[1]
        if path not in arcs: arcs[path] = Archive(path, 'le' if kind == 'pc' else 'be')
        print('%s #%d %s: ids %s' % (os.path.basename(path), i, lst.get(arcs[path].idx[i]['hash'], '?'),
                                     [s[1] for s in hit]))
    print('%d records' % n)


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
