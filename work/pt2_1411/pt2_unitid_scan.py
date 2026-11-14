"""PT.2 (2026-11-14): scan converted DLC DRMs for StreamUnitIDs left in Xbox numbering. Read-only.

For every DRM of OWN_DIR (top level) that also exists in OLD_DIR and has an Xbox original in work/generic/dlc_drms.pkl,
compare all type-7 sections (same id, same size) as u16 pairs {u16 a, u16 b}: report a pair where
  xbox a is a DLC-range unit id (map value 88..108) and  own == xbox raw  and  old == {map(a), b}
= the old tree remapped the unit id (Xbox -> PC, work/generic/unit_idmaps.json space 'unit'), the own tree did not.
Background: the per-cell stream lists of a unit's scene ({u16 StreamUnitID, u16 streamgroup index}, read by 0x5b8e80)
in dlc_pillory DTP 20536 keep Xbox ids (PC id - 1) -> the pillory main cell asks for dlc_water_wheel group 1 (does not
exist) -> streamgroup request with a garbage name -> file system queue stuck -> next loading screen hangs.

Usage (repository root): ../bin/pyt -t 900 work/pt2_1411/pt2_unitid_scan.py OWN_DIR OLD_DIR [--list]
"""
import sys, os, pickle, json, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
W = os.path.join(HERE, '..', 'generic')


def main(a):
    lst = '--list' in a
    a = [x for x in a if x != '--list']
    own, old = a[0], a[1]
    d = json.load(open(os.path.join(W, 'unit_idmaps.json')))
    M = {int(k): v for k, v in d['unit'].items()}
    dlc = {k for k, v in M.items() if isinstance(v, int) and 88 <= v <= 108}
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    X = {}
    for k, v in C.items(): X.setdefault(base(k[1]), v)
    tot = collections.Counter(); files = 0
    for f in sorted(os.listdir(own)):
        if not f.lower().endswith('.drm'): continue
        b = base(f)
        po, pl = os.path.join(own, f), os.path.join(old, f)
        if b not in X or not os.path.exists(pl): continue
        files += 1
        h, xs = X[b]
        xsec = {(s['type'], s['id']): s['data'] for s in xs if s['type'] == 7}
        O = {(s.type, s.id): s.data for s in DW.read(open(po, 'rb').read(), 'le').sections if s.type == 7}
        L = {(s.type, s.id): s.data for s in DW.read(open(pl, 'rb').read(), 'le').sections if s.type == 7}
        for k in sorted(O):
            if k not in L or k not in xsec: continue
            do, dl, dx = O[k], L[k], xsec[k]
            if not (len(do) == len(dl) == len(dx)): continue
            hits = []; fixed = 0
            for o in range(0, len(do) - 3, 4):
                xa, xb = struct.unpack_from('>HH', dx, o)
                if xa not in dlc: continue
                oa, ob = struct.unpack_from('<HH', do, o)
                la, lb = struct.unpack_from('<HH', dl, o)
                if (la, lb) == (M[xa], xb) and (oa, ob) == (xa, xb): hits.append((o, xa, xb, oa, la))
                elif (la, lb) == (M[xa], xb) and (oa, ob) == (la, lb): fixed += 1
            if hits:
                tot['sections'] += 1; tot['pairs'] += len(hits)
                print('%s sec %d: %d pairs left in Xbox numbering (%d mapped like old)' % (f, k[1], len(hits), fixed))
                if lst:
                    for o, xa, xb, oa, la in hits:
                        print('   +0x%05x  xbox/own %d/%d  old %d/%d' % (o, xa, xb, la, xb))
    print('files compared %d; sections with unmapped unit ids %d; pairs %d' % (files, tot['sections'], tot['pairs']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
