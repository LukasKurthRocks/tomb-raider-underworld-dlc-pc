"""DLC 2 thrall base class under a main-game script id: give the DLC copy its own PC id (read-only unless --out).

Finding (2026-11-04, docs Befund-Thrall-Absturz.md section 9, thrall unload crash tru+0x1976a3 / writer tru+0xa342c):
  * DLC 2 re-authored the thrall base script under the id of the main-game one: Xbox script 8453 is 3300 bytes in the
    base game and in DLC 1 (instance 16 bytes: playersensor +4, playersensor +8, health +12; vtable 69) but 152 bytes
    in all 16 DLC 2 DRMs that carry it (instance 8 bytes: health +4; no functions; vtable 64). The DLC 2 thrall
    classes 24347 (viking), 22813 (viking tutorial, base 24347), 24545 (yeti), 24891 (armored yeti, base 24545) derive
    from it and place their members after 8 bytes (+8 int, +12 health, +16 messagechannel).
  * The converter maps every Xbox 8453 to the PC id of the base pair, 12433 (tools/dlc_generic.DlcIds, by id).
  * The Xbox generalbank (disc and title update) holds no thrall script, so on the Xbox the DLC copy is the one in
    use. The PC patch generalbank.drm holds the main-game 12433 (with 12435, 5816, 14578, 16595), so on the PC it is
    always resident and the engine never takes the DLC copy (first loaded section of an id wins). Live dump
    (runs/20261103_200657_paket01_yggdrasil): the base type of 24347 in memory has instance size 0x10, 3 members, vtable
    0x45 = the generalbank version.
  * On unload, tru+0x57b240 walks the unique data of the class chain (each offset once, most derived class first):
    24347 claims +8 / +12 / +16, the resident 12433 adds +4 as a playersensor, released through the playersensor
    handler (vtable +0x1c = tru+0x3ace30 -> tru+0x4a3420, u16 [ptr+4] -= 1). The DLC layout keeps the instance
    pointer there (health +4), so the instance's prev link +4 drops by 1 -> the category-list unlink crashes.
Fix: renumber the DLC 2 copy of 12433 (only a section with the DLC layout: instance 8 bytes, 1 member) to a free PC id
and every type-8 id reference to it in the same DRM (the self id +0x14 and the base ids / references of 24347 / 24545:
root +0x18 and +0x5c). Section order and data size do not change; relocations stay valid. The DLC thralls then run
on their own base class as on the Xbox; nothing in tru.exe names 12433 (no dword 0x00003091 in the image) and the
class is a pure script class (no natives; the native NsEnemyThrallBase is 12435 'enemythrallbase').

Modes (from the repository root):
  ../bin/pyt -t 600 tools/script_base_clash_fix.py proof
        the facts above from the archives: 8453 records and sizes per pack / layer, generalbank contents (Xbox disc,
        Xbox title update, PC), layout of each version
  ../bin/pyt -t 600 tools/script_base_clash_fix.py free [TREE_DIR ...]
        check that NEW_ID is unused: PC base index (work/idx_pc.json), DLC id table (work/generic/dlc_idmap.json),
        every DRM of the given trees
  ../bin/pyt -t 600 tools/script_base_clash_fix.py check PC.drm [PC2.drm ...] [--out OUT_DIR]
        per DRM: the 12433 section and its layout, every id reference to it; --out writes the renumbered DRM to
        OUT_DIR/<name> (CDRM-compressed again when the input was), reads it back and re-checks (0 references to 12433
        left, NEW_ID present with the same layout and bytes apart from the renumbered words)
"""
import sys, os, struct, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

OLD_ID = 12433          # PC id of the main-game thrall base class (Xbox 8453), resident from generalbank.drm
NEW_ID = 26884          # free PC script id for the DLC 2 copy (checked by mode `free`)
DLC_LAYOUT = (8, 4, 1)  # instance size, align, member count of the DLC 2 copy
HERE = os.path.dirname(os.path.abspath(__file__))


def layout(d, rl, e='le'):
    E = '>' if e == 'be' else '<'
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    size, align = struct.unpack_from(E + 'HH', d, 0x1c)
    nm = struct.unpack_from(E + 'I', d, it[0x2c] - 4)[0] if 0x2c in it else 0
    vt = struct.unpack_from(E + 'H', d, 0x3c)[0]
    return size, align, nm, vt


def refs(D, sid):
    """[(section index, offset)] of the type-8 id references whose value is sid"""
    out = []
    for i, s in enumerate(D.sections):
        if not s.reloc: continue
        rel = R.parse(s.reloc, 'le')
        for t, o in rel.idref + rel.idref_a:
            if t == 8 and o + 4 <= len(s.data) and struct.unpack_from('<I', s.data, o)[0] == sid:
                out.append((i, o))
    return out


def fix(raw):
    """(new raw or None, report lines)"""
    D = DW.read(raw, 'le')
    rep = []
    hits = [i for i, s in enumerate(D.sections) if s.type == 8 and s.id == OLD_ID]
    if not hits: return None, ['no script %d' % OLD_ID]
    if any(s.type == 8 and s.id == NEW_ID for s in D.sections): return None, ['NEW_ID %d already present' % NEW_ID]
    i = hits[0]
    s = D.sections[i]
    lay = layout(s.data, s.reloc)
    rep.append('script %d section #%d: %d bytes, instance size %d align %d, members %d, vtableSize %d' % (
        OLD_ID, i, len(s.data), lay[0], lay[1], lay[2], lay[3]))
    if lay[:3] != DLC_LAYOUT:
        return None, rep + ['  layout is not the DLC 2 one %s - left alone (main-game / DLC 1 copy)' % (DLC_LAYOUT,)]
    rr = refs(D, OLD_ID)
    for k, o in rr:
        rep.append('  id reference in %d:%d +0x%x' % (D.sections[k].type, D.sections[k].id, o))
    for k, o in rr:
        b = bytearray(D.sections[k].data)
        struct.pack_into('<I', b, o, NEW_ID)
        D.sections[k].data = bytes(b)
    D.sections[i].id = NEW_ID
    new = D.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    return new, rep + ['  renumbered %d -> %d: section header + %d id words' % (OLD_ID, NEW_ID, len(rr))]


def verify(old_raw, new_raw):
    A = DW.read(old_raw, 'le'); B = DW.read(new_raw, 'le')
    assert len(A.sections) == len(B.sections)
    words = 0; other = 0
    for a, b in zip(A.sections, B.sections):
        assert a.type == b.type and len(a.data) == len(b.data) and a.reloc == b.reloc
        if a.id != b.id: assert (a.type, a.id, b.id) == (8, OLD_ID, NEW_ID)
        for o in range(0, len(a.data) - 3, 4):
            if a.data[o:o + 4] != b.data[o:o + 4]:
                if struct.unpack_from('<I', a.data, o)[0] == OLD_ID and struct.unpack_from('<I', b.data, o)[0] == NEW_ID: words += 1
                else: other += 1
        if len(a.data) % 4 and a.data[-(len(a.data) % 4):] != b.data[-(len(a.data) % 4):]: other += 1
    left = refs(B, OLD_ID)
    s = next(x for x in B.sections if x.type == 8 and x.id == NEW_ID)
    return words, other, len(left), layout(s.data, s.reloc)


def check(argv):
    out = None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    st = collections.Counter()
    for p in argv:
        raw = open(p, 'rb').read()
        new, rep = fix(raw)
        print('%s:' % os.path.basename(p))
        for l in rep: print('  ' + l)
        if new is None: st['unchanged'] += 1; continue
        st['to fix'] += 1
        if out:
            os.makedirs(out, exist_ok=True)
            q = os.path.join(out, os.path.basename(p))
            open(q, 'wb').write(new)
            words, other, left, lay = verify(raw, open(q, 'rb').read())
            print('  written %s (%d bytes): %d words %d -> %d, %d other words changed, %d references to %d left, '
                  'new section layout %s' % (q, len(new), words, OLD_ID, NEW_ID, other, left, OLD_ID, lay))
            if other or left: st['VERIFY FAILED'] += 1
            else: st['written'] += 1
    print('summary: %s' % dict(st))


def free(argv):
    used = collections.Counter()
    for rec in json.load(open(os.path.join(HERE, '..', 'work', 'idx_pc.json'))):
        for s in rec[5] or []:
            if s[0] == 8: used[s[1]] += 1
    print('PC base index: %d script ids, max %d; NEW_ID %d used %d times' % (len(used), max(used), NEW_ID, used[NEW_ID]))
    d = json.load(open(os.path.join(HERE, '..', 'work', 'generic', 'dlc_idmap.json')))
    nv = [int(v) for v in d['new'].get('8', {}).values()]
    print('DLC id table type 8: %d new ids, max %d; NEW_ID used %d times' % (len(nv), max(nv) if nv else 0, nv.count(NEW_ID)))
    bad = used[NEW_ID] + nv.count(NEW_ID)
    for tree in argv:
        n = 0
        for fn in sorted(os.listdir(tree)):
            if not fn.lower().endswith('.drm'): continue
            D = DW.read(open(os.path.join(tree, fn), 'rb').read(), 'le')
            for s in D.sections:
                if s.type == 8 and s.id == NEW_ID: print('  %s holds script %d' % (fn, NEW_ID)); bad += 1
                if s.reloc:
                    rel = R.parse(s.reloc, 'le')
                    for t, o in rel.idref + rel.idref_a:
                        if t == 8 and o + 4 <= len(s.data) and struct.unpack_from('<I', s.data, o)[0] == NEW_ID:
                            print('  %s %d:%d +0x%x references %d' % (fn, s.type, s.id, o, NEW_ID)); bad += 1
            n += 1
        print('tree %s: %d DRMs scanned' % (tree, n))
    print('NEW_ID %d: %s' % (NEW_ID, 'FREE' if not bad else 'TAKEN (%d)' % bad))


def proof(argv):
    import script_func_list as FL
    import section_id_index as SI
    for kind, sid in (('xbox', 8453), ('dlc', 8453), ('pc', OLD_ID)):
        print('== index %s: script %d' % (kind, sid))
        SI.main([kind, '8', str(sid)])
    for src in ('xdisc:generalbank.drm', 'xtu:generalbank.drm', 'pc:generalbank.drm'):
        S, e = FL.sections(src)
        ids = {q[1] for q in S if q[0] == 8}
        have = [x for x in (8453, 8457, 5453, 8442, 8445, OLD_ID, 12435, 5816, 14578, 16595) if x in ids]
        print('%s: %d scripts; thrall chain ids present: %s' % (src, len(ids), have))
    os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
    for src, sid in (('xdisc:viking_thrall.drm', 8453), ('dlc:viking_thrall_dlc2_.drm', 8453),
                     ('pc:generalbank.drm', OLD_ID)):
        S, e = FL.sections(src)
        q = next(q for q in S if q[0] == 8 and q[1] == sid)
        print('%s script %d: %d bytes, (size, align, members, vtableSize) %s' % (src, sid, len(q[2]), layout(q[2], q[3], e)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    {'check': check, 'free': free, 'proof': proof}[a[0]](a[1:])
