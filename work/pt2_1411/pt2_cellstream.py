"""PT.2 (2026-11-14): find the per-cell stream lists {u16 unit id, u16 streamgroup index} of a unit's scene and compare
Xbox original (work/generic/dlc_drms.pkl), own tree and an old tree. Read-only.

The game (0x5b8e80, loop at 0x5b8f20) reads, for the cell Lara stands in, a list of pairs {u16 StreamUnitID, u16 group
index}; for every pair whose unit is loaded it takes record base + 0x14 * (index + 1) of that unit's streamgroup table and
queues "<root>StreamGroups\\<record+0xc>.drm" (0x5b8dc0). A pair with a wrong unit id can therefore point past the
records of another unit (bound check at 0x5b8f5c is index < count incl. the 'default' record).

The live list of the 13.11. pillory cell starts with the bytes of KEY (own tree). This tool finds the section holding
the list in every file given, then walks all such lists in that section (same layout: 6 pairs found next to each other)
and prints the pairs side by side with the Xbox->PC unit id map applied to the Xbox values.

Usage (repository root): ../bin/pyt -t 600 work/pt2_1411/pt2_cellstream.py UNIT OWN_DRM OLD_DRM [SECID]
"""
import sys, os, pickle, json, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
W = os.path.join(HERE, '..', 'generic')


def umap():
    d = json.load(open(os.path.join(W, 'unit_idmaps.json')))
    return {int(a): b for a, b in d['unit'].items()}


def xbox_sections(unit):
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    for k, v in C.items():
        if base(k[1]) == unit:
            h, secs = v
            return {(s['type'], s['id']): s['data'] for s in secs}
    return {}


def pc_sections(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    return {(s.type, s.id): s.data for s in D.sections}


def pairs(data, end):
    """all u16 pairs of the section data (as {unit, idx}) - caller slices the region"""
    f = '>' if end == 'be' else '<'
    return [struct.unpack_from(f + 'HH', data, o) for o in range(0, len(data) - 3, 4)]


def main(a):
    unit, own, old = a[0], a[1], a[2]
    sid = int(a[3]) if len(a) > 3 else 20536
    M = umap()
    X = xbox_sections(unit)
    O = pc_sections(own)
    L = pc_sections(old)
    kx = [k for k in X if k[1] == sid]
    ko = [k for k in O if k[1] == sid]
    kl = [k for k in L if k[1] == sid]
    print('unit %s section id %d: xbox %s own %s old %s' % (unit, sid, kx, ko, kl))
    if not (kx and ko and kl):
        print('section missing'); return 1
    dx, do, dl = X[kx[0]], O[ko[0]], L[kl[0]]
    print('sizes xbox %d own %d old %d' % (len(dx), len(do), len(dl)))
    n = min(len(dx), len(do), len(dl)) // 4
    px, po, pl = pairs(dx, 'be'), pairs(do, 'le'), pairs(dl, 'le')
    # print only words where own != old (the converted ones that differ), with the Xbox value and its mapped value
    diff = 0; same_x = 0; same_m = 0
    for i in range(n):
        if po[i] != pl[i]:
            diff += 1
            xu, xi = px[i]
            mu = M.get(xu, '?')
            if po[i] == px[i]: same_x += 1
            if pl[i] == (mu, xi): same_m += 1
            print('  +0x%04x xbox %3d/%d (map %s) own %3d/%d old %3d/%d' % (i * 4, xu, xi, mu, po[i][0], po[i][1],
                                                                       pl[i][0], pl[i][1]))
    print('words differing own vs old: %d; own == xbox raw: %d; old == xbox mapped: %d' % (diff, same_x, same_m))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
