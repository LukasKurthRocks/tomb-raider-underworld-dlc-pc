"""Pipeline step `scriptclash` (stage 2b, tools/dlc_fixes_build.py): DLC script classes re-authored under the id of
an always-resident PC script with another INSTANCE layout get their own PC id, by rule (WINDOWS_REBUILD.md
findings 45 / 46; workspace docs Befund-Thrall-Absturz.md sections 9 / 11).

Why: the engine keeps the first loaded section of an id. The PC generalbank (always loaded) holds the main-game
version of such a script, so the DLC copy is dropped and every DLC class that derives from it runs on the resident
layout. Proven case: DLC 2 re-authored the thrall base class (Xbox 8453 -> PC 12433) with an 8-byte instance (health
+4) while the resident main-game 12433 has 16 bytes (playersensor +4 / +8, health +12); on unload the resident
member description released the DLC instance pointer as a playersensor (crash tru+0x1976a3, writer tru+0xa342c).

Rule (no hard-coded list): a type-8 section X of a DRM in the tree is renumbered when
  * its id is held by the RESIDENT bank (default pc:generalbank.drm, the PC patch version; --resident adds more),
  * neither copy is a native class (nativeName empty - natives bind by name, a renumbered native class would not),
  * its instance layout (size, align, member offsets / kinds) differs from the resident one, and
  * at least one DLC class of the tree derives from it (directly or through other DLC classes; one is enough for
    the whole group, so every copy of the group gets the same id).
Groups = (old id, DLC instance layout). Each group gets a PC id from docs/data/script_clash_ids.json (stable across
rebuilds; 12433 with the 8-byte DLC 2 layout -> 26884 as in test tree dlc_test51a_thrall). A new group gets
max(DLC id table type 8, PC index, file) + 1 and is appended to the file (reported); every run checks that each
id is free (PC index, DLC id table, every DRM of the tree apart from the renumbered copies). The rewrite per DRM:
the section id and every type-8 id reference (idref / idref_a) with the old value; section order, sizes and
relocations do not change. Differences of the vtable size only (scripts 3581 / 72: the PC appends a slot, same
instance layout, no DLC class derives from them) are reported, never changed.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script_clash_fix.py scan TREE [--resident R.drm,...]
  ../bin/pyt -t 900 tools/script_clash_fix.py apply SRC_TREE OUT_DIR [--resident ...]   changed DRMs -> OUT_DIR/<rel>
  ../bin/pyt -t 900 tools/script_clash_fix.py check TREE [--resident ...] [--report OUT.json]
        exit 1 when an instance-layout clash with a derived DLC class is left (pipeline check after Fixes)
  ../bin/pyt -t 900 tools/script_clash_fix.py compare DIR_A DIR_B     md5 per common DRM (the proof against a test tree)
In the pipeline: tools/dlc_fixes_build.py fix `scriptclash` (last fix) runs run_tree() over the stage-2b tree in place.
"""
import sys, os, struct, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import script_func_list as FL

HERE = os.path.dirname(os.path.abspath(__file__))
IDS_FILE = os.path.join(HERE, '..', 'docs', 'data', 'script_clash_ids.json')
RESIDENT = 'pc:generalbank.drm'


def layout(d, rl, e='le'):
    """dict(size, align, mem ((off, kind), ...), vt, base, native) of a script section, or None"""
    if len(d) < 0x48: return None
    E = '>' if e == 'be' else '<'
    rel = R.parse(rl, e)
    it = dict(rel.internal); ids = rel.id_offsets()

    def u32(o): return struct.unpack_from(E + 'I', d, o)[0]
    mem = []
    if 0x2c in it:
        t = it[0x2c]
        for k in range(u32(t - 4)):
            a = t + 20 * k
            if a + 20 > len(d): break
            mem.append((struct.unpack_from(E + 'H', d, a + 12)[0], u32(a) & 0xf))
    nat = None
    if 0x10 in it:
        o = it[0x10]; z = d.find(b'\0', o)
        nat = d[o:z].decode('latin-1') if z > o else None
    size, align = struct.unpack_from(E + 'HH', d, 0x1c)
    return dict(size=size, align=align, mem=tuple(mem), vt=struct.unpack_from(E + 'H', d, 0x3c)[0],
                base=u32(0x18) if 0x18 in ids else None, native=nat)


def ikey(L):
    """instance layout key"""
    return (L['size'], L['align'], L['mem'])


def resident(spec=None):
    out = {}
    for r in (spec or RESIDENT).split(','):
        S, e = FL.sections(r)
        for q in S:
            if q[0] == 8 and q[2] and q[1] not in out:
                L = layout(q[2], q[3], e)
                if L: out[q[1]] = L
    return out


SKIP = {'generalbank.drm'}     # the resident bank itself (b138_fixes / test trees ship our generalbank build)


def tree_drms(tree):
    for dp, dn, fn in os.walk(tree):
        dn.sort()
        for f in sorted(fn):
            if f.lower().endswith('.drm') and f.lower() not in SKIP:
                p = os.path.join(dp, f)
                yield p, os.path.relpath(p, tree).replace(os.sep, '/')


def type8_refs(D, value):
    """[(section index, offset)] of type-8 id references (idref + idref_a) holding value"""
    out = []
    for i, s in enumerate(D.sections):
        if not s.reloc: continue
        rel = R.parse(s.reloc, 'le')
        for t, o in rel.idref + rel.idref_a:
            if t == 8 and o + 4 <= len(s.data) and struct.unpack_from('<I', s.data, o)[0] == value:
                out.append((i, o))
    return out


def plan(tree, res):
    """scan a tree: {group key (old id, ikey): dict(layout, resident, drms, derived, vt_only)} and the vt-only list.
    group key as a JSON-able string via gkey()"""
    groups = collections.OrderedDict(); vt_only = collections.OrderedDict(); ids_in_tree = collections.Counter()
    for p, rel in tree_drms(tree):
        try: D = DW.read(open(p, 'rb').read(), 'le')
        except Exception as x: print('  %s: read failed %s' % (rel, x)); continue
        own = {}
        for s in D.sections:
            if s.type == 8 and s.data:
                ids_in_tree[s.id] += 1
                L = layout(s.data, s.reloc)
                if L: own.setdefault(s.id, L)
        for sid, L in own.items():
            if sid not in res: continue
            r = res[sid]
            if L['native'] or r['native']: continue
            if ikey(L) == ikey(r):
                if L['vt'] != r['vt']:
                    v = vt_only.setdefault(sid, dict(dlc_vt=set(), res_vt=r['vt'], drms=[]))
                    v['dlc_vt'].add(L['vt']); v['drms'].append(rel)
                continue
            g = groups.setdefault((sid, ikey(L)), dict(old=sid, layout=L, res=r, drms=[], derived=collections.Counter()))
            g['drms'].append(rel)
            # DLC classes of this DRM that derive from it (chain through the DRM's own, non-resident classes)
            for did, DL in own.items():
                if did in res: continue
                b = DL['base']; seen = set()
                while b is not None and b not in seen:
                    seen.add(b)
                    if b == sid: g['derived'][did] += 1; break
                    if b in res or b not in own: break
                    b = own[b]['base']
    return groups, vt_only, ids_in_tree


def gkey(old, ik):
    return '%d:%d/%d:%s' % (old, ik[0], ik[1], ','.join('%d.%d' % m for m in ik[2]))


def load_ids():
    if os.path.exists(IDS_FILE): return json.load(open(IDS_FILE, encoding='utf-8'))
    return {'rule': __doc__.split('\n\n')[2], 'ids': []}


def taken_ids():
    """type-8 ids the PC base index and the DLC id table use"""
    used = set()
    for rec in json.load(open(os.path.join(HERE, '..', 'work', 'idx_pc.json'))):
        for s in rec[5] or []:
            if s[0] == 8: used.add(s[1])
    d = json.load(open(os.path.join(HERE, '..', 'work', 'generic', 'dlc_idmap.json')))
    used |= {int(v) for v in d['new'].get('8', {}).values()}
    return used


def assign(groups, ids_in_tree, log, write_file=True):
    """{(old, ikey): new id} for the groups with derived DLC classes; checks every id is free"""
    J = load_ids(); have = {e['key']: e['new'] for e in J['ids']}
    used = taken_ids()
    out = {}; added = False
    for (old, ik), g in groups.items():
        if not g['derived']: continue
        k = gkey(old, ik)
        if k not in have:
            new = max(used | set(have.values()) | set(ids_in_tree) | {0}) + 1
            J['ids'].append(dict(type=8, old=old, key=k, new=new, size=ik[0], members=len(ik[2]),
                                 resident_size=g['res']['size'], resident_members=len(g['res']['mem'])))
            have[k] = new; added = True
            log('NEW GROUP %s -> id %d (appended to %s)' % (k, new, os.path.relpath(IDS_FILE, os.path.join(HERE, '..'))))
        new = have[k]
        if new in used: raise SystemExit('script clash id %d (for %s) is taken by the PC index or the DLC id table' % (new, k))
        if ids_in_tree.get(new) and ids_in_tree.get(old) is None:
            log('id %d already in the tree and no %d left - tree already fixed' % (new, old))
        out[(old, ik)] = new
    if added and write_file:
        json.dump(J, open(IDS_FILE, 'w', encoding='utf-8', newline='\r\n'), indent=1)
    return out


def fix_raw(raw, mapping, rel, log):
    """new raw bytes or None; mapping {(old, ikey): new}"""
    D = DW.read(raw, 'le')
    done = []
    for i, s in enumerate(D.sections):
        if s.type != 8 or not s.data: continue
        L = layout(s.data, s.reloc)
        if L is None: continue
        new = mapping.get((s.id, ikey(L)))
        if new is None: continue
        if any(x.type == 8 and x.id == new for x in D.sections):
            raise SystemExit('%s: holds script %d already next to %d - not renumbered' % (rel, new, s.id))
        done.append((i, s.id, new))
    if not done: return None, None
    words = 0
    for i, old, new in done:
        rr = type8_refs(D, old)
        for k, o in rr:
            b = bytearray(D.sections[k].data); struct.pack_into('<I', b, o, new); D.sections[k].data = bytes(b)
        D.sections[i].id = new
        words += len(rr)
        log('%s: script %d -> %d (section #%d) + %d id words' % (rel, old, new, i, len(rr)))
    out = D.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    return out, [(old, new) for i, old, new in done]


def verify(old_raw, new_raw, pairs):
    """(renumbered words, other changed words, references to an old id left)"""
    A = DW.read(old_raw, 'le'); B = DW.read(new_raw, 'le')
    assert len(A.sections) == len(B.sections)
    m = dict(pairs); words = other = 0
    for a, b in zip(A.sections, B.sections):
        assert a.type == b.type and len(a.data) == len(b.data) and a.reloc == b.reloc
        if a.id != b.id: assert a.type == 8 and m.get(a.id) == b.id
        for o in range(0, len(a.data) - 3, 4):
            if a.data[o:o + 4] != b.data[o:o + 4]:
                if m.get(struct.unpack_from('<I', a.data, o)[0]) == struct.unpack_from('<I', b.data, o)[0]: words += 1
                else: other += 1
        r = len(a.data) % 4
        if r and a.data[-r:] != b.data[-r:]: other += 1
    left = sum(len(type8_refs(B, old)) for old, new in pairs)
    return words, other, left


def run_tree(src, out, res_spec=None, log=print, write_ids=True):
    """apply the rule to every DRM of src, write changed DRMs to out/<rel> (out may equal src: in place);
    returns dict(files, groups, vt_only, stats)"""
    res = resident(res_spec)
    groups, vt_only, ids_in_tree = plan(src, res)
    for (old, ik), g in groups.items():
        log('group %s: DLC size %d members %d vs resident size %d members %d; %d DRMs; derived DLC classes %d%s' % (
            gkey(old, ik), ik[0], len(ik[2]), g['res']['size'], len(g['res']['mem']), len(g['drms']), len(g['derived']),
            '' if g['derived'] else ' -> left alone (nothing derives from it)'))
    for sid, v in vt_only.items():
        log('vtable size only: script %d DLC vt %s vs resident %d in %d DRMs - left alone (same instance layout)' % (
            sid, sorted(v['dlc_vt']), v['res_vt'], len(v['drms'])))
    mapping = assign(groups, ids_in_tree, log, write_ids)
    st = collections.Counter(); files = []
    if mapping:
        for p, rel in tree_drms(src):
            raw = open(p, 'rb').read()
            new, pairs = fix_raw(raw, mapping, rel, log)
            if new is None: continue
            w, o, left = verify(raw, new, pairs)
            if o or left: raise SystemExit('%s: verify failed (%d other words, %d references left)' % (rel, o, left))
            q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
            open(q, 'wb').write(new); files.append(rel)
            st['files'] += 1; st['id words'] += w
    log('total %s; ids %s' % (dict(st), {gkey(*k): v for k, v in mapping.items()}))
    return dict(files=files, mapping={gkey(*k): v for k, v in mapping.items()}, stats=dict(st),
                vt_only={str(k): dict(dlc_vt=sorted(v['dlc_vt']), res_vt=v['res_vt'], drms=len(v['drms'])) for k, v in vt_only.items()})


def check(tree, res_spec=None, report=None):
    res = resident(res_spec)
    groups, vt_only, ids_in_tree = plan(tree, res)
    J = load_ids(); fixed = {e['new']: e for e in J['ids']}
    bad = [(k, g) for k, g in groups.items() if g['derived']]
    for (old, ik), g in groups.items():
        print('%s group %s: %d DRMs, %d derived DLC classes' % ('UNFIXED' if g['derived'] else 'info   ', gkey(old, ik),
                                                               len(g['drms']), len(g['derived'])))
    for sid, v in vt_only.items():
        print('info    vtable size only: script %d DLC vt %s vs resident %d (%d DRMs)' % (sid, sorted(v['dlc_vt']), v['res_vt'], len(v['drms'])))
    present = {n: ids_in_tree[n] for n in fixed if ids_in_tree.get(n)}
    print('renumbered ids present in the tree: %s' % (present or '-'))
    print('check: %s' % ('FAIL - %d instance-layout clash group(s) with derived DLC classes left' % len(bad) if bad else 'ok'))
    if report:
        json.dump(dict(unfixed=[gkey(*k) for k, g in bad], present=present,
                       vt_only={str(k): sorted(v['dlc_vt']) for k, v in vt_only.items()}), open(report, 'w'), indent=1)
    return 1 if bad else 0


def compare(a, b):
    n = same = 0
    for p, rel in tree_drms(a):
        q = os.path.join(b, rel)
        if not os.path.exists(q): print('only in A: %s' % rel); continue
        n += 1
        ha = hashlib.md5(open(p, 'rb').read()).hexdigest(); hb = hashlib.md5(open(q, 'rb').read()).hexdigest()
        if ha == hb: same += 1
        else: print('DIFFERS %s: %s vs %s' % (rel, ha, hb))
    print('compare: %d common DRMs, %d identical, %d differ' % (n, same, n - same))
    return 0 if n == same else 1


def main(argv):
    rs = None
    if '--resident' in argv: k = argv.index('--resident'); rs = argv[k + 1]; del argv[k:k + 2]
    rep = None
    if '--report' in argv: k = argv.index('--report'); rep = argv[k + 1]; del argv[k:k + 2]
    cmd = argv[0]
    if cmd == 'scan':
        res = resident(rs); groups, vt_only, ids_in_tree = plan(argv[1], res)
        for (old, ik), g in groups.items():
            print('group %s: %d DRMs, derived %s' % (gkey(old, ik), len(g['drms']), dict(g['derived'])))
        for sid, v in vt_only.items(): print('vt only %d: %s vs %d (%d DRMs)' % (sid, sorted(v['dlc_vt']), v['res_vt'], len(v['drms'])))
    elif cmd == 'apply':
        r = run_tree(argv[1], argv[2], rs)
        print('written %d file(s) to %s' % (len(r['files']), argv[2]))
    elif cmd == 'check': sys.exit(check(argv[1], rs, rep))
    elif cmd == 'compare': sys.exit(compare(argv[1], argv[2]))
    else: sys.exit(__doc__)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
