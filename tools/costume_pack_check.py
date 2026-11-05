r"""Read-only checks for the costume packs (pack1 Wetsuit k/p, pack2 Classic a/h, pack20 Designer l/m).

  idmap OLD NEW          every (type, xbox id) entry of OLD dlc_idmap.json is unchanged in NEW; prints what NEW adds
  lists                  costume units and objlist.dat records of every pack list (work/generic/lists) and of the
                         merged PC list (work/generic/merged/tr8/pc-w), with the object names of each record
  names LOCALS LOCMAP    costume display names: Xbox string index 61 + slot (a = 61 .. p = 76, docs/COSTUMES.md) ->
                         PC string id (LOCMAP = locmap_xbox_to_pc.json of tools/locals.py build) -> string of LOCALS
                         (a PC locals.bin_NNN); also the Xbox strings of each costume pack's English locals.bin
  render                 which materials / shader libraries of each costume DRM the Assemble step's render tables
                         (work/render/dlc_materials_pc.pkl, pc_shader_sections.pkl) know
  images                 md5 / size of each outfit image record (image\dlc_outfit_costume_<x>.raw) in every pack
  tree DIR [OUT.tsv]     md5, size and relative path of every file below DIR (sorted); OUT.tsv also written if given
  xids                   Xbox ids of the types 2 / 7 / 8 of every costume DRM (work/idx_dlc.json) against the base and
                         DLC id maps and against the DLC 1 costume b (explains the pc_copy / template vs convert routes)
  sections A.drm B.drm   per section type: count and how many sections are byte-identical (id-independent) between
                         two PC DRMs (e.g. a new costume against a DLC 1 costume of the same family)

Usage (from the repository root):
  ../bin/pyt -t 300 tools/costume_pack_check.py idmap work/rebuild/costumes_0311/backup_before/dlc_idmap.json work/generic/dlc_idmap.json
  ../bin/pyt -t 300 tools/costume_pack_check.py lists
  ../bin/pyt -t 300 tools/costume_pack_check.py names work/rebuild/b138_pristine/mods/local/locals.bin_001 work/rebuild/stage1/locmap_xbox_to_pc.json
  ../bin/pyt -t 300 tools/costume_pack_check.py tree work/rebuild/dlc_test50l_costumes/mods
"""
import sys, os, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
WG = os.path.join(HERE, '..', 'work', 'generic')
SLOTS = 'abcdefghijklmnop'
PACK_SLOTS = {'pack1': 'kp', 'pack2': 'ah', 'pack20': 'lm'}


def cmd_idmap(old, new):
    a = json.load(open(old))['new']; b = json.load(open(new))['new']
    changed = 0; added = collections.Counter(); kept = 0
    for t, d in a.items():
        nd = b.get(t, {})
        for x, v in d.items():
            if nd.get(x) != v: changed += 1; print('CHANGED type %s xid %s: %s -> %s' % (t, x, v, nd.get(x)))
            else: kept += 1
    for t, d in b.items():
        for x in d:
            if x not in a.get(t, {}): added[int(t)] += 1
    print('old entries kept %d, changed %d; added per type %s' % (kept, changed, dict(sorted(added.items()))))
    return 1 if changed else 0


def cmd_lists():
    import objlists as O
    srcs = [(p, os.path.join(WG, 'lists', p + '_'), 'be') for p in ('dlc_pack1', 'dlc_pack2', 'dlc_pack20', 'dlc_pack10', 'dlc_pack11', 'xboxtu')]
    srcs += [('pc', os.path.join(WG, 'lists', 'pc_'), 'le'), ('merged', os.path.join(WG, 'merged', 'tr8', 'pc-w') + os.sep, 'le')]
    for name, pre, e in srcs:
        ol = O.read_objectlist(open(pre + 'objectlist.txt', 'rb').read())
        units = O.read_unitlist(open(pre + 'unitlist.txt', 'rb').read())
        recs, _ = O.read_objlist(open(pre + 'objlist.dat', 'rb').read(), e)
        cu = [u for u in units if 'costume' in u.lower()]
        print('== %-10s objects %4d units %3d records %3d; costume objects %s' % (
            name, len(ol), len(units), len(recs), ' '.join('%d=%s' % (k, v) for k, v in sorted(ol.items()) if 'costume' in v)))
        for u in cu: print('   unit', u)
        for n, l in recs:
            if 'costume' in n.lower():
                print('   record %-14s %d objects: %s' % (n, len(l), ' '.join(ol.get(i, '#%d' % i) for i in l)))


def cmd_names(locals_path, locmap):
    import locals as LO
    from archive import Archive
    m = {int(k): v for k, v in json.load(open(locmap))['map'].items()}
    lang, pc, _ = LO.parse(open(locals_path, 'rb').read(), 'le')
    print('PC %s: language %d, %d strings' % (locals_path, lang, len(pc)))
    xb = {}
    for pk in ('pack1', 'pack2', 'pack20'):
        path, e, _ = LO.SRC[pk]
        A = Archive(path, 'be')
        from names import crc
        r = [x for x in A.find(crc('xenon-w\\local\\locals.bin')) if x['spec'] == 0xfffff7e1]
        xb[pk] = LO.parse(A.read(r[0]), 'be')[1] if r else []
    for k, s in enumerate(SLOTS):
        x = 61 + k; p = m.get(x)
        pack = next((pk for pk, sl in PACK_SLOTS.items() if s in sl), '')
        print('slot %s xbox %d -> pc %s %-28r | xbox %s' % (
            s, x, p, pc[p] if p is not None and p < len(pc) else None,
            ' '.join('%s=%r' % (pk, xb[pk][x] if x < len(xb[pk]) else None) for pk in xb)), pack)


def cmd_tree(d, out=None):
    rows = []
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            rows.append((os.path.relpath(p, d).replace('\\', '/'), os.path.getsize(p), hashlib.md5(open(p, 'rb').read()).hexdigest()))
    rows.sort()
    for rel, n, h in rows: print('%s  %10d  %s' % (h, n, rel))
    if out:
        with open(out, 'w', newline='\r\n') as f:
            f.write('md5\tbytes\tpath\n')
            for rel, n, h in rows: f.write('%s\t%d\t%s\n' % (h, n, rel))
    print('files %d' % len(rows))


def cmd_xids():
    """Xbox section ids of every costume DRM (work/idx_dlc.json section lists, no decoding) for the types the generic
    converter can copy from PC (2, 7, 8): how many ids the base id map knows (work/generic/idmap.json; only those can
    take the pc_copy / template routes of dlc_generic.convert_drm), how many the DLC id map adds, and how many
    (type, id, size) triples the DLC 1 costume b has as well"""
    from names import crc
    idx = json.load(open(os.path.join(HERE, '..', 'work', 'idx_dlc.json')))
    base = json.load(open(os.path.join(WG, 'idmap.json')))
    dlc = json.load(open(os.path.join(WG, 'dlc_idmap.json')))['new']
    by = {}
    for r in idx:
        if not isinstance(r[5], list) or r[3] != 0xffffffff: continue
        for s in SLOTS:
            if r[2] == crc('xenon-w\\dlc_costume_%s.drm' % s):
                by.setdefault((os.path.basename(r[0])[:-4], s), r[5])
    ref = {(t, i, z) for t, i, z, *_ in by.get(('pack10', 'b'), [])}
    for (p, s), secs in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        row = []
        for t in (2, 7, 8):
            ids = [(i, z) for tt, i, z, *_ in secs if tt == t]
            nb = sum(1 for i, z in ids if str(i) in base.get(str(t), {}))
            nd = sum(1 for i, z in ids if str(i) in dlc.get(str(t), {}))
            nr = sum(1 for i, z in ids if (t, i, z) in ref)
            row.append('t%d %4d base %4d dlc %4d =b %4d' % (t, len(ids), nb, nd, nr))
        print('%-7s %s: %s' % (p, s, ' | '.join(row)))
    # which Xbox base records (work/idx_xbox_base.json: layer1 / layer2 / TitleUpdate) share the most type-7
    # (id, size) pairs with each costume: tells which base data generation a costume pack was built against
    xb = json.load(open(os.path.join(HERE, '..', 'work', 'idx_xbox_base.json')))
    costume_hashes = {crc('xenon-w\\dlc_costume_%s.drm' % s) for s in SLOTS}
    recs = [(os.path.basename(r[0]), r[1], r[2], {(i, z) for t, i, z, *_ in r[5] if t == 7})
            for r in xb + [r for r in idx if r[2] not in costume_hashes] if isinstance(r[5], list)]
    for (p, s), secs in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        k7 = {(i, z) for t, i, z, *_ in secs if t == 7}
        top = sorted(((len(k7 & q), f, i, h) for f, i, h, q in recs if q), reverse=True)[:3]
        print('%-7s %s type-7 (id, size) %4d; best base records: %s' % (
            p, s, len(k7), ', '.join('%s#%d hash %08x: %d' % (f, i, h, n) for n, f, i, h in top)))
        # size difference costume - Xbox lara (layer1 record of the DLC 1 costumes' best match) for the same type-7 id
        lara = next((q for f, i, h, q in recs if f == 'layer1.000' and h == 0x1328d202), None)
        if lara:
            lz = dict(lara); d = collections.Counter(z - lz[i] for i, z in k7 if i in lz)
            print('        size(costume) - size(layer1 lara) for %d shared ids: %s' % (sum(d.values()), d.most_common(6)))


def cmd_sections(a, b):
    import drm_write as DW
    A = DW.read(open(a, 'rb').read(), 'le').sections; B = DW.read(open(b, 'rb').read(), 'le').sections
    ha = collections.Counter((s.type, hashlib.md5(s.data).hexdigest()) for s in A)
    hb = collections.Counter((s.type, hashlib.md5(s.data).hexdigest()) for s in B)
    ta = collections.Counter(s.type for s in A); tb = collections.Counter(s.type for s in B)
    for t in sorted(set(ta) | set(tb)):
        same = sum(min(c, hb[k]) for k, c in ha.items() if k[0] == t)
        print('type %2d: %5d vs %5d sections, %5d identical' % (t, ta[t], tb[t], same))


def cmd_images():
    """md5 of every outfit image record per pack (same name in several packs: same picture or not)"""
    from archive import Archive
    from convert_dlc import R as ROOT, PACKS
    from names import crc
    for s in SLOTS:
        nm = 'xenon-w\\image\\dlc_outfit_costume_%s.raw' % s
        row = []
        for p in PACKS:
            A = Archive(ROOT + p, 'be')
            r = [x for x in A.find(crc(nm)) if x['spec'] == 0xffffffff]
            if r:
                b = A.read(r[0]); row.append('%s=%s/%d' % (p.split('/')[1][:-4], hashlib.md5(b).hexdigest()[:8], len(b)))
        print('slot %s: %s' % (s, ' '.join(row)))


def cmd_render():
    """render tables of the Assemble step (work/render, built from idx_dlc.json = pack10/pack11 only) against the
    costume DRMs: materials in dlc_materials_pc.pkl (material_dlc.material_for_writer looks every DLC material up there),
    shader libraries in pc_shader_sections.pkl (assemble_dlc.dlc_shader_src)"""
    import pickle
    from archive import Archive
    from convert_dlc import R as ROOT, PACKS
    from names import crc
    from drm import cdrm_decode, sections_with_data
    WR = os.path.join(HERE, '..', 'work', 'render')
    mats = pickle.load(open(os.path.join(WR, 'dlc_materials_pc.pkl'), 'rb'))
    shs = pickle.load(open(os.path.join(WR, 'pc_shader_sections.pkl'), 'rb'))
    for p in PACKS:
        A = Archive(ROOT + p, 'be')
        for nm in ('xenon-w\\dlc_costume_%s.drm' % s for s in SLOTS):
            r = [x for x in A.find(crc(nm)) if x['spec'] == 0xffffffff]
            if not r: continue
            secs = sections_with_data(cdrm_decode(A.read(r[0]), 'be'), 'be')[1]
            m = [s['id'] for s in secs if s['type'] == 10]; sh = [s['id'] for s in secs if s['type'] == 9]
            mm = [x for x in m if x not in mats]; ms = [x for x in sh if x not in shs]
            print('%-7s %-22s materials %3d, not in dlc_materials_pc %3d %s | shader libs %3d, not in pc_shader_sections %3d %s' % (
                p.split('/')[1][:-4], nm.split('\\')[-1], len(m), len(mm), mm[:6], len(sh), len(ms), ms[:6]))


def main(argv):
    if not argv: sys.exit(__doc__)
    c = argv[0]
    if c == 'images': return cmd_images()
    if c == 'render': return cmd_render()
    if c == 'idmap': return cmd_idmap(argv[1], argv[2])
    if c == 'lists': return cmd_lists()
    if c == 'names': return cmd_names(argv[1], argv[2])
    if c == 'tree': return cmd_tree(argv[1], argv[2] if len(argv) > 2 else None)
    if c == 'sections': return cmd_sections(argv[1], argv[2])
    if c == 'xids': return cmd_xids()
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
