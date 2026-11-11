"""Q83 all enemies for the test arena: every enemy object (base game + DLC 1 + DLC 2) with its child objects, home units
and DRM sizes (read-only).

Enemy = an object whose DRM holds the enemy data magic 0xdaf00018 (tools/enemy_data_scan.py; the enemy init 0x63c190
builds a brain only for such data). Child objects = the u16 list the loader requests after the object is loaded
(type-11 header -> root DTP +0x48, tools/child_list_scope.py; runtime walk 0x54e84b..0x54e899), resolved recursively.

Sources, in the order the game resolves them (ModLoader mods folder first, then patch.000, then bigfile.000):
  MODS_DIR (flat <name>.drm), data/pc/patch.000, data/pc/bigfile.000.
Object list / unit lists: the installed MODS_DIR/tr8/pc-w/objectlist.txt + objlist.dat.

Usage (from the repository root):
  ../bin/pyt -t 1800 work/q83_allenemies_1111/enemy_catalog.py MODS_DIR [--tsv OUT.tsv]
Prints per enemy: id, name, source, stored / decoded size, tree byte, child tree (id name size source), DRM dependency
names, units that list the enemy (and whether each unit also lists every child), a total size of object + children.
"""
import sys, os, struct, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import objlists as OL
import drm_write as DW
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode
from child_list_scope import plist

MAGIC = 0xdaf00018
TREES = {1: 'Creature', 2: 'CreatureVolumetric', 3: 'Thrall'}


class Src:
    def __init__(self, mods):
        self.mods = mods
        self.arch = []
        for s in ('pcpatch', 'pcbig'):
            path, e, pre = LC.SRC[s]
            self.arch.append((s, Archive(path, e), pre))
        self.cache = {}

    def get(self, name):
        """(source, stored size, decoded bytes) or None"""
        if name in self.cache:
            return self.cache[name]
        r = None
        p = os.path.join(self.mods, name + '.drm')
        if os.path.isfile(p):
            st = open(p, 'rb').read()
            r = ('mods', len(st), cdrm_decode(st, 'le'))
        else:
            for s, A, pre in self.arch:
                recs = A.find(crc(pre + '\\' + name + '.drm'))
                if recs:
                    st = A.read(recs[-1])
                    r = (s, len(st), cdrm_decode(st, 'le'))
                    break
        self.cache[name] = r
        return r


def enemy_rec(raw):
    D = DW.read(raw, 'le')
    for s in D.sections:
        d = bytes(s.data)
        for o in range(0, len(d) - 0x40, 4):
            if struct.unpack_from('<I', d, o)[0] == MAGIC:
                return D, (s.id, o, struct.unpack_from('b', d, o + 0x0c)[0], d[o + 0x18])
    return D, None


def dep_names(D):
    return [x.decode('latin1') for x in D.names.split(b'\0') if x.strip()]


def main(argv):
    mods = argv[0]
    tsv = argv[argv.index('--tsv') + 1] if '--tsv' in argv else None
    lst = os.path.join(mods, 'tr8', 'pc-w')
    names = OL.read_objectlist(open(os.path.join(lst, 'objectlist.txt'), 'rb').read())
    recs, _ = OL.read_objlist(open(os.path.join(lst, 'objlist.dat'), 'rb').read(), 'le')
    units_of = {}
    unit_ids = {}
    for u, ids in recs:
        unit_ids[u] = set(ids)
        for i in ids:
            units_of.setdefault(i, []).append(u)
    S = Src(mods)
    byname = {v.lower(): k for k, v in names.items()}

    def info(oid):
        n = names.get(oid, '?%d' % oid)
        g = S.get(n)
        if g is None:
            return n, None, 0, 0, None, []
        src, st, raw = g
        D = DW.read(raw, 'le')
        r = plist(D)
        kids = r[2] if r else []
        return n, src, st, len(raw), D, kids

    rows = []
    n_scan = 0
    for oid in sorted(names):
        n = names[oid]
        if re.search(r'chunkdoll|generator|^co_|^cine|^fx_|_extension$|^ar_|^ms_|^wp_|^ui_|^lara|^player|^cam', n, re.I):
            continue
        g = S.get(n)
        if g is None:
            continue
        n_scan += 1
        try:
            D, er = enemy_rec(g[2])
        except Exception as ex:
            print('%d %s parse error %s' % (oid, n, ex)); continue
        if er is None:
            continue
        rows.append((oid, n, g, D, er))
    print('%d objects scanned, %d with an enemy record' % (n_scan, len(rows)))
    out = []
    for oid, n, g, D, er in rows:
        src, st, raw = g
        r = plist(D)
        kids = r[2] if r else []
        print('\n%d %s  [%s, stored %d B, decoded %d B]  tree %d %s  +0x18=%d  (data sec %d +0x%x)' % (
            oid, n, src, st, len(raw), er[2], TREES.get(er[2], 'Soldier'), er[3], er[0], er[1]))
        deps = dep_names(D)
        if deps:
            print('  DRM dependency names: %s' % ', '.join(deps))
        seen = set(); tot_st = st; tot_dec = len(raw); missing = []
        all_ids = []

        def walk(ids, depth):
            nonlocal tot_st, tot_dec
            for k in ids:
                if k in seen:
                    print('  %s%d %s (again)' % ('  ' * depth, k, names.get(k, '?'))); continue
                seen.add(k); all_ids.append(k)
                cn, csrc, cst, cdec, CD, ck = info(k)
                if csrc is None:
                    missing.append(k)
                    print('  %s%d %s  MISSING (no DRM in mods / patch / bigfile)' % ('  ' * depth, k, cn)); continue
                tot_st += cst; tot_dec += cdec
                typ = ''
                dd = dep_names(CD)
                print('  %s%d %s  [%s, %d B / %d B]%s%s' % ('  ' * depth, k, cn, csrc, cst, cdec,
                      ('  deps: ' + ', '.join(dd)) if dd else '', typ))
                walk(ck, depth + 1)
        print('  children (load order): %s' % (' '.join(str(k) for k in kids) or '-'))
        walk(kids, 1)
        us = units_of.get(oid, [])
        full = [u for u in us if all(k in unit_ids[u] for k in all_ids)]
        print('  total object + children: stored %d B (%.1f MB), decoded %d B (%.1f MB)%s' % (
            tot_st, tot_st / 1048576.0, tot_dec, tot_dec / 1048576.0, ('; MISSING %s' % missing) if missing else ''))
        print('  units listing it (%d): %s' % (len(us), ', '.join(us) or '-'))
        if us and len(full) != len(us):
            print('  units listing it AND every child (%d): %s' % (len(full), ', '.join(full) or '-'))
        out.append('\t'.join(str(x) for x in (oid, n, src, st, len(raw), er[2], TREES.get(er[2], 'Soldier'), er[3],
                   ' '.join('%d:%s' % (k, names.get(k, '?')) for k in all_ids), tot_st, tot_dec,
                   ' '.join(str(m) for m in missing), ' '.join(us))))
    if tsv:
        with open(tsv, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('id\tname\tsource\tstored\tdecoded\ttree\ttree_name\tb18\tchildren\ttotal_stored\ttotal_decoded'
                    '\tmissing\tunits\n')
            for line in out:
                f.write(line + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
