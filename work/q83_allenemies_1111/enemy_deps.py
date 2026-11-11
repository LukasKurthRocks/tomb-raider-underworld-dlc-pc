"""Q83: what does an enemy object need beyond its own DRM and its child objects? (read-only)

For each enemy object (enemy record magic 0xdaf00018, list from enemy_catalog.tsv) and its child objects:
  * anim table: object DTP +0x54 (u16 count) / +0x58 (12-byte entries, u16 anim section id at +0). The load end
    0x54e80b -> 0x434090 resolves every id ONCE against the global anim pool 0x8c1240 (3000 x 8 B {u16 refs,
    u16 section id, ptr}); an id not resident at that moment gets slot 0xffff. So an anim section that is neither in
    the object's own DRM nor resident from elsewhere stays unresolved for this object.
  * section id references (relocation kinds A / resource) from every section to a (type, id) the DRM itself does
    not hold: textures / DTPs / scripts / materials of other DRMs (they must be resident when used).
  * wave sections (type 6) the DRM carries (sound leaves name loaded waves by id).
Unresolved ids are looked up in the installed mods folder and in the PC section index work/idx_pc.json (patch +
bigfile; names via the yura PC list) to say WHERE they live.

Usage (from the repository root):
  ../bin/pyt -t 3600 work/q83_allenemies_1111/enemy_deps.py MODS_DIR CATALOG.tsv
"""
import sys, os, struct, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R
from enemy_catalog import Src
import objlists as OL

TYPES = {0: 'general', 2: 'anim', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
         11: 'object', 12: 'mesh', 13: 'unit'}
HERE = os.path.dirname(os.path.abspath(__file__))


def root_dtp(D):
    head = next((x for x in D.sections if x.type == 11), None)
    if head is None or len(head.data) < 4:
        return None
    root = struct.unpack_from('<I', head.data, 0)[0]
    return next((x for x in D.sections if x.type == 7 and x.id == root), None)


def anim_ids(D):
    s = root_dtp(D)
    if s is None or len(s.data) < 0x5c:
        return None
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    n = struct.unpack_from('<H', s.data, 0x54)[0]
    if 0x58 not in it:
        return []
    a = it[0x58]
    return [struct.unpack_from('<H', s.data, a + 12 * i)[0] for i in range(n) if a + 12 * i + 2 <= len(s.data)]


def id_refs(D):
    out = set()
    for s in D.sections:
        if not s.reloc:
            continue
        r = R.parse(bytes(s.reloc), 'le')
        for t, o in r.idref_a + r.idref:
            if o + 4 <= len(s.data):
                out.add((t, struct.unpack_from('<I', s.data, o)[0]))
    return out


def main(argv):
    mods, tsv = argv[0], argv[1]
    lst = os.path.join(mods, 'tr8', 'pc-w')
    names = OL.read_objectlist(open(os.path.join(lst, 'objectlist.txt'), 'rb').read())
    S = Src(mods)
    rows = [l.rstrip('\r\n').split('\t') for l in open(tsv, encoding='utf-8')][1:]
    report = []
    wanted = set()
    per = []
    for r in rows:
        oid, name = int(r[0]), r[1]
        kids = [int(x.split(':')[0]) for x in r[8].split()] if r[8] else []
        group = [(oid, name)] + [(k, names.get(k, '?')) for k in kids]
        have = set(); anims = {}; refs = set(); waves = 0; secs = 0
        for k, n in group:
            g = S.get(n)
            if g is None:
                continue
            D = DW.read(g[2], 'le')
            have |= {(s.type, s.id) for s in D.sections}
            anims[n] = anim_ids(D)
            refs |= id_refs(D)
            waves += sum(1 for s in D.sections if s.type == 6)
            secs += len(D.sections)
        own_anim = {i for t, i in have if t == 2}
        miss_anim = {}
        for n, ids in anims.items():
            if ids:
                m = sorted(set(i for i in ids if i and i not in own_anim))
                miss_anim[n] = (len(ids), m)
        miss_refs = sorted(x for x in refs if x not in have)
        wanted |= set(miss_refs)
        for n, (cnt, m) in miss_anim.items():
            wanted |= {(2, i) for i in m}
        per.append((oid, name, group, secs, waves, anims, miss_anim, miss_refs))
    # where do the unresolved ids live?
    where = collections.defaultdict(set)
    for fn in sorted(os.listdir(mods)):
        if not fn.lower().endswith('.drm'):
            continue
        try:
            D = DW.read(open(os.path.join(mods, fn), 'rb').read(), 'le')
        except Exception:
            continue
        for s in D.sections:
            if (s.type, s.id) in wanted:
                where[(s.type, s.id)].add('mods:' + fn[:-4])
    idx = json.load(open(os.path.join(HERE, '..', 'idx_pc.json')))
    hits = []
    for rec in idx:
        for s in rec[5] or []:
            if (s[0], s[1]) in wanted:
                hits.append((rec[0], rec[1], (s[0], s[1])))
    try:
        from names import load, L
        from archive import Archive
        pcl = load(L + 'Tomb Raider Underworld (PC).txt')
        arcs = {}
        for path, i, key in hits:
            if path not in arcs:
                arcs[path] = Archive(path, 'le')
            nm = pcl.get(arcs[path].idx[i]['hash'], '#%d' % i)
            where[key].add(os.path.basename(path).split('.')[0] + ':' + nm.split('\\')[-1].replace('.drm', ''))
    except Exception as x:
        print('names not resolved: %s' % x)
        for path, i, key in hits:
            where[key].add('%s#%d' % (os.path.basename(path), i))
    for oid, name, group, secs, waves, anims, miss_anim, miss_refs in per:
        print('\n%d %s: %d DRMs (%s), %d sections, %d wave sections' % (
            oid, name, len(group), ' '.join(n for _, n in group), secs, waves))
        for n, ids in anims.items():
            if ids is None:
                print('  %s: no object DTP / anim table' % n); continue
            cnt, m = miss_anim.get(n, (len(ids), []))
            print('  %s anim table %d entries, %d ids not in the group DRMs%s' % (
                n, len(ids), len(m), (': ' + ' '.join('%d[%s]' % (i, ','.join(sorted(where.get((2, i), {'NOWHERE'}))))
                                                     for i in m[:12]) + (' ...' if len(m) > 12 else '')) if m else ''))
        bytype = collections.defaultdict(list)
        for t, i in miss_refs:
            bytype[t].append(i)
        for t in sorted(bytype):
            ids = bytype[t]
            loc = collections.Counter()
            for i in ids:
                for w in where.get((t, i), {'NOWHERE'}):
                    loc[w] += 1
            print('  refs to %s outside the group: %d ids; found in: %s' % (
                TYPES.get(t, t), len(ids), ', '.join('%s x%d' % kv for kv in loc.most_common(8))))
            nowhere = [i for i in ids if (t, i) not in where]
            if nowhere:
                print('    nowhere: %s' % ' '.join(str(i) for i in nowhere[:20]))


if __name__ == '__main__':
    main(sys.argv[1:])
