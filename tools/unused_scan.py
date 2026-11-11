"""Unused-content scan (Q66, 2026-11-11, read-only): which objects, scripts, script natives and localised texts of the
PC game (bigfile + patch, optionally the installed DLC mods tree) does nothing reference?

`index` reads every DRM once (patch.000 wins over bigfile.000 by name; mods files are read as they are) and keeps only
ids, offsets and counts - no game bytes - in work/q66_unused_1111/index.pkl:
  * sections per DRM (type, id)
  * script roots (type 8): self id +0x14, base class (idref at +0x18), package / native name strings (native types)
  * references to scripts: external relocations from any other section (target script id, target offset, call flag =
    the word before is op 0x65 / 0x66 as tools/native_calls_check.py), id references (resource / kind A) of type 8,
    and intro +0x7c of every unit DTP (instance script of a placed object)
  * intros of unit DRMs: object id (+0x50), unique id (+0x58), script id (+0x7c) (layout: tools/unit_ids.level_info)
  * text ids: the locals string id leaves of script members (UI text element userType 301 path [0, 92], PDA list entry
    userType 223 path [0, 0]; ENGINE.md section 2, Q46 / Q48) and the uitext record form of
    tools/script_text_records.py; one walk per distinct script body (cache by id + crc32)
Reports (read the index, write TSV + summary to work/q66_unused_1111/):
  objects   every object id of the PC + title-update object lists: units that list it (objlist.dat), units that place
            it (intro), whether a DRM exists, name references in other files (tools/hidden_scan.py index, optional)
  scripts   scripts no other section, intro or DRM references; native script functions no script calls
  texts     locals ids of the PC table that no text leaf / record names (candidates: computed ids, DTP or exe
            references are not seen - see the report header)
Limits: an id built at run time (script arithmetic such as the chapter titles 388 + n), ids in DTP records and exe
immediates are not seen, so "unreferenced" is a candidate list, not a proof; the reports say so.

Usage (from the repository root):
  ../bin/pyt -t 7200 tools/unused_scan.py index [--no-mods] [--mods DIR]
  ../bin/pyt -t 900  tools/unused_scan.py objects [--no-tokens]
  ../bin/pyt -t 900  tools/unused_scan.py scripts
  ../bin/pyt -t 900  tools/unused_scan.py texts [--lang fffff7e1]
  ../bin/pyt -t 300  tools/unused_scan.py script ID       one script: copies, references (who), native functions
"""
import sys, os, struct, collections, pickle, zlib, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'work', 'q66_unused_1111')
IDX = os.path.join(OUT, 'index.pkl')
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')
MODS = os.path.join(ROOT, '..', 'data', 'pc', 'mods')
TEXT_LEAVES = {(301, (0, 92)), (223, (0, 0))}      # PC userType, path in the member's init tree (Q46 / Q48)


def cstr(d, o):
    z = d.find(b'\0', o)
    return d[o:z].decode('latin1', 'replace') if 0 <= o < len(d) and z > o else None


class Script:
    """per distinct script body: root ids, native strings, function entries, text leaves"""
    __slots__ = ('self_id', 'super_id', 'pkg', 'nat', 'funcs', 'texts', 'records', 'bad')


def script_facts(d, rl):
    import drm_reloc as R, script_conv as SC, script_init_from_pc as SIP
    S = Script()
    rel = R.parse(rl, 'le'); it = dict(rel.internal)
    ids = dict((o, t) for t, o in rel.idref + rel.idref_a)
    S.self_id = struct.unpack_from('<I', d, 0x14)[0] if len(d) >= 0x18 else None
    S.super_id = struct.unpack_from('<I', d, 0x18)[0] if 0x18 in ids else 0
    S.pkg = cstr(d, it[0x0c]) if 0x0c in it else None
    S.nat = cstr(d, it[0x10]) if 0x10 in it else None
    S.funcs = {}; S.texts = []; S.records = []; S.bad = 0
    try:
        W = SC.Walk(d, rel, 'le').run()
    except Exception:
        S.bad = 1; return S
    protos = {}
    for name, t, n, sz in W.arrays:
        if name == 'protos':
            for k in range(n): protos[t + k * sz] = struct.unpack_from('<H', d, t + k * sz + 8)[0]
    for name, t, n, sz in W.arrays:
        if name == 'funcs':
            for k in range(n):
                a = t + k * sz
                S.funcs[a] = (k, protos.get(it.get(a)), it.get(a + 0x18) is None)
    try:
        for (arr, nm, tag, ut), la in SIP.members(W, d, 'le').items():
            for ma in la:
                ia = W.it.get(ma + 16)
                if ia is None: continue
                for path, o in SIP.leaves(W, W.it, ia):
                    if (ut, path) in TEXT_LEAVES and o + 4 <= len(d):
                        S.texts.append((ut, struct.unpack_from('<I', d, o)[0]))
    except Exception:
        S.bad = 2
    for o in range(0, len(d) - 31, 4):            # uitext records (tools/script_text_records.py form)
        a, b, c1, c2, sid = struct.unpack_from('<5I', d, o)
        if a in (0xffffffff, 0x00ffffff) and b == 0 and c1 >> 24 in (0, 0xff) and c2 >> 24 == 0xff and c1 != 0:
            S.records.append(sid)
    return S


def level_intros(D):
    """[(object id, unique id, script id)] of a unit DRM (section 0 = Level, unit DTP at Level+0x74)"""
    import drm_reloc as R
    s0 = D.sections[0] if D.sections else None
    if s0 is None or s0.type != 0 or len(s0.data) < 0x78: return None
    rx = R.parse(s0.reloc, 'le')
    ext = {so: (si, do) for si, so, do in rx.external}
    if 0x74 not in ext or 0 not in ext: return None
    di, do = ext[0x74]
    s = D.sections[di]
    if s.type != 7 or do != 0 or len(s.data) < 0x14: return None
    ri = dict(R.parse(s.reloc, 'le').internal)
    n = struct.unpack_from('<I', s.data, 0xc)[0]; t = ri.get(0x10)
    if t is None or t + 0x90 * n > len(s.data): return []
    out = []
    for k in range(n):
        o = t + 0x90 * k
        out.append((struct.unpack_from('<H', s.data, o + 0x50)[0], struct.unpack_from('<I', s.data, o + 0x58)[0],
                    struct.unpack_from('<I', s.data, o + 0x7c)[0]))
    return out


def sources(mods):
    """yield (label, raw DRM bytes): patch first, then bigfile (names not in patch), then the mods tree"""
    import locals as LC
    from archive import Archive
    from hidden_scan import name_map
    nm = name_map('pc-w'); seen = set()
    for src in ('pcpatch', 'pcbig'):
        path, e, pre = LC.SRC[src]
        A = Archive(path, e)
        for r in A.idx:
            name = nm.get(r['hash'])
            if not name or not name.lower().endswith('.drm') or r['hash'] in seen: continue
            seen.add(r['hash'])
            yield '%s:%s' % (src, name.split('\\')[-1].lower()), lambda A=A, r=r: A.read(r)
    if mods and os.path.isdir(mods):
        for f in sorted(os.listdir(mods)):
            if f.lower().endswith('.drm'):
                yield 'mods:%s' % f.lower(), lambda p=os.path.join(mods, f): open(p, 'rb').read()


def cmd_index(argv):
    import drm_write as DW, drm_reloc as R
    mods = None if '--no-mods' in argv else (argv[argv.index('--mods') + 1] if '--mods' in argv else MODS)
    os.makedirs(OUT, exist_ok=True)
    drms = []                                   # [label]
    secs = []                                   # per drm: [(type, id)]
    cache = {}                                  # (id, len, crc) -> Script
    copies = collections.defaultdict(list)      # script id -> [(drm, key)]
    refs = collections.defaultdict(lambda: collections.defaultdict(set))   # sid -> kind -> {drm}
    calls = collections.Counter()               # (sid, target offset, call?) -> n
    intros = {}                                 # drm -> [(obj, uid, script)]
    texts = collections.defaultdict(set)        # text id -> {(kind, drm)}
    st = collections.Counter()
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else None     # quick test runs
    for label, get in sources(mods):
        if limit is not None and st['drms'] >= limit: break
        try:
            D = DW.read(get(), 'le')
        except Exception:
            st['read errors'] += 1; continue
        k = len(drms); drms.append(label); st['drms'] += 1
        secs.append([(s.type, s.id) for s in D.sections])
        for s in D.sections:
            if s.type != 8 or not s.data: continue
            key = (s.id, len(s.data), zlib.crc32(s.data) ^ zlib.crc32(s.reloc))
            if key not in cache:
                cache[key] = script_facts(s.data, s.reloc); st['distinct script bodies'] += 1
            copies[s.id].append((k, key))
            S = cache[key]
            for ut, v in S.texts: texts[v].add(('leaf%d' % ut, k))
            for v in S.records: texts[v].add(('record', k))
        for s in D.sections:
            if not s.reloc: continue
            rel = R.parse(s.reloc, 'le')
            for si, so, do in rel.external:
                if si >= len(D.sections): continue
                t = D.sections[si]
                if t.type != 8 or (s.type == 8 and t.id == s.id): continue
                call = s.type == 8 and so >= 4 and struct.unpack_from('<I', s.data, so - 4)[0] >> 24 in (0x65, 0x66)
                refs[t.id]['ext%d' % s.type].add(k)
                calls[(t.id, do, call)] += 1
            for ty, o in rel.idref + rel.idref_a:
                if ty != 8 or o + 4 > len(s.data): continue
                v = struct.unpack_from('<I', s.data, o)[0]
                if s.type == 8 and v == s.id: continue
                kind = 'super' if s.type == 8 and o == 0x18 else 'idref%d' % s.type
                refs[v][kind].add(k)
        L = level_intros(D)
        if L is not None:
            intros[k] = L
            for obj, uid, sid in L:
                if sid: refs[sid]['intro'].add(k)
        if st['drms'] % 500 == 0: print('  %d DRMs, %d script bodies' % (st['drms'], st['distinct script bodies']), flush=True)
    D = dict(drms=drms, secs=secs, scripts=cache, copies=dict(copies), refs={a: dict(b) for a, b in refs.items()},
             calls=calls, intros=intros, texts=dict(texts), stats=st, mods=mods)
    with open(IDX, 'wb') as f: pickle.dump(D, f, protocol=4)
    print(' '.join('%s %d' % kv for kv in sorted(st.items())), '->', IDX)


def load():
    return pickle.load(open(IDX, 'rb'))


def write(name, lines):
    p = os.path.join(OUT, name)
    with open(p, 'w', encoding='utf-8', newline='\n') as f: f.write('\n'.join(lines) + '\n')
    return p


# ------------------------------------------------------------------------------------------------ objects
def cmd_objects(argv):
    import objlists as OL
    I = load()
    objs = OL.read_objectlist(open(os.path.join(LISTS, 'xboxtu_objectlist.txt'), 'rb').read())   # Xbox ids (DLC 822+)
    pc = OL.read_objectlist(open(os.path.join(LISTS, 'pc_objectlist.txt'), 'rb').read())
    pcid = {v.lower(): k for k, v in pc.items()}
    lists = {}
    for pfx, e in (('pc', 'le'), ('xboxtu', 'be')):
        recs, _ = OL.read_objlist(open(os.path.join(LISTS, pfx + '_objlist.dat'), 'rb').read(), e)
        lists[pfx] = recs
    in_list = collections.defaultdict(set)              # name -> units
    for pfx, recs in lists.items():
        names = pc if pfx == 'pc' else objs
        for unit, ids in recs:
            for i in ids:
                if i in names: in_list[names[i].lower()].add(unit.split('\\')[-1].lower())
    # placed: PC base units use PC ids; mods units (converted DLC) keep Xbox ids >= 822 and PC ids below
    placed = collections.defaultdict(set)
    for k, L in I['intros'].items():
        unit = I['drms'][k].split(':', 1)[1].rsplit('.', 1)[0]
        for obj, uid, sid in L:
            nm = pc.get(obj) if obj <= 821 else objs.get(obj)
            if nm: placed[nm.lower()].add(unit)
    have = set(lbl.split(':', 1)[1].rsplit('.', 1)[0] for lbl in I['drms'])
    tok = None
    if '--no-tokens' not in argv:
        import hidden_scan as HS
        H = HS.Index(); units = HS.all_units()
        tok = lambda n: [r for r in H.users(n) if HS.rec_kind(H, r, units) not in ('list',) and HS.base(H.recs[r][1]) != n]
    allnames = sorted(set(v.lower() for v in objs.values()) | set(pcid))
    rows = ['# object\tpc_id\txbox_id\tdrm(PC/mods)\tlisted_by_units\tplaced_in_units\tname_refs(other files)\tclass']
    cnt = collections.Counter()
    xid = {v.lower(): k for k, v in objs.items()}
    for n in allnames:
        lu, pu = in_list.get(n, set()), placed.get(n, set())
        refs = tok(n) if tok else []
        rk = sorted(set(HS.rec_kind(H, r, units) for r in refs)) if tok else []
        if not lu and n not in have: c = 'A no unit, no DRM'
        elif not lu: c = 'B DRM, no unit lists it'
        elif not pu: c = 'C listed, never placed'
        else: c = 'D placed'
        cnt[c] += 1
        rows.append('%s\t%s\t%s\t%s\t%d %s\t%d %s\t%d %s\t%s' % (
            n, pcid.get(n, '-'), xid.get(n, '-'), 'yes' if n in have else 'no', len(lu), ','.join(sorted(lu)[:4]),
            len(pu), ','.join(sorted(pu)[:4]), len(refs), ','.join(rk), c))
    p = write('objects.tsv', rows)
    print('objects %d: %s -> %s' % (len(allnames), ', '.join('%s %d' % kv for kv in sorted(cnt.items())), p))


# ------------------------------------------------------------------------------------------------ scripts
def cmd_scripts(argv):
    I = load()
    drms = I['drms']; refs = I['refs']; cache = I['scripts']
    rows = ['# script\tcopies\tfirst_drm\tnative\tfuncs\tbase\treferenced_by (kind:drms)\tclass']
    cnt = collections.Counter()
    for sid, cp in sorted(I['copies'].items()):
        S = cache[cp[0][1]]
        r = refs.get(sid, {})
        own = set(k for k, _ in cp)
        # a reference from the script's own DRM counts; only self-references were dropped at index time
        kinds = {kd: len(ks) for kd, ks in r.items()}
        nat = '%s/%s' % (S.pkg, S.nat) if S.nat else ''
        if not r: c = 'unreferenced'
        elif set(r) <= {'super'}: c = 'base only'
        else: c = 'used'
        cnt[c + (' native' if nat else '')] += 1
        rows.append('%d\t%d\t%s\t%s\t%d\t%s\t%s\t%s' % (sid, len(cp), drms[cp[0][0]], nat, len(S.funcs),
                    S.super_id or '', ' '.join('%s:%d' % kv for kv in sorted(kinds.items())), c))
    p = write('scripts.tsv', rows)
    print('scripts %d: %s -> %s' % (len(I['copies']), ', '.join('%s %d' % kv for kv in sorted(cnt.items())), p))
    # second look at the unreferenced ones: the script id as a plain u32 word in a non-script section of a DRM that
    # holds a copy (object data names its class script by id, not by relocation)
    import drm_write as DW
    un = [int(r.split('\t')[0]) for r in rows[1:] if r.endswith('\tunreferenced')]
    by = collections.defaultdict(list)
    for sid in un:
        for k, _ in I['copies'][sid]: by[k].append(sid)
    get = dict(sources(I.get('mods')))
    hits = collections.defaultdict(list)
    for k, sids in by.items():
        D = DW.read(get[I['drms'][k]](), 'le')
        for s in D.sections:
            if s.type in (2, 5, 6, 8, 9, 12) or not s.data: continue      # media / scripts: no id fields
            for o in range(0, len(s.data) - 3, 4):
                v = struct.unpack_from('<I', s.data, o)[0]
                if v in sids: hits[v].append('%d:%d+0x%x' % (s.type, s.id, o))
    out = ['# unreferenced script\tfirst drm\tnative\tid as u32 in a non-script section of its DRMs (type:id+offset)\tstrings']
    c2 = collections.Counter()
    for sid in un:
        cp = I['copies'][sid]; S = I['scripts'][cp[0][1]]
        h = sorted(set(hits.get(sid, [])))
        c2['id word in object data' if h else 'no reference at all'] += 1
        out.append('%d\t%s\t%s\t%s' % (sid, I['drms'][cp[0][0]], ('%s/%s' % (S.pkg, S.nat)) if S.nat else '',
                                        ' '.join(h[:6]) + (' +%d' % (len(h) - 6) if len(h) > 6 else '')))
    p3 = write('scripts_unref.tsv', out)
    print('unreferenced scripts %d: %s -> %s' % (len(un), ', '.join('%s %d' % kv for kv in sorted(c2.items())), p3))
    # native functions without a call
    # two counts per function entry: op65 / op66 call relocations (tools/native_calls_check.py filter) and ANY
    # external relocation onto the entry from another script (other call forms, subclass vtables) - only the second
    # being 0 means "nothing in the data points at it"
    called = collections.Counter(); anyref = collections.Counter()
    for (sid, off, call), n in I['calls'].items():
        anyref[(sid, off)] += n
        if call: called[(sid, off)] += n
    nrows = ['# native script\tname\tfunc index\tproto symbol\toffset\top65/66 calls\tany reference (all DRMs)']
    tot = collections.Counter()
    for sid, cp in sorted(I['copies'].items()):
        S = cache[cp[0][1]]
        if not S.nat: continue
        for off, (k, proto, native) in sorted(S.funcs.items()):
            if not native: continue
            n, a = called.get((sid, off), 0), anyref.get((sid, off), 0)
            tot['native functions'] += 1; tot['no op65/66 call' if not n else 'op65/66 call'] += 1
            if not a: tot['no reference at all'] += 1
            nrows.append('%d\t%s/%s\tf%d\t%s\t0x%x\t%d\t%d' % (sid, S.pkg, S.nat, k, proto, off, n, a))
    p2 = write('natives.tsv', nrows)
    print('native functions: %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(tot.items())), p2))


def cmd_script(argv):
    I = load(); sid = int(argv[0], 0)
    cp = I['copies'].get(sid)
    if not cp: print('script %d: no copy' % sid); return
    S = I['scripts'][cp[0][1]]
    print('script %d: %d copies (%d bodies), native %s/%s, base %s, funcs %d, text leaves %d, records %d' % (
        sid, len(cp), len(set(k for _, k in cp)), S.pkg, S.nat, S.super_id, len(S.funcs), len(S.texts), len(S.records)))
    print('  in: %s' % ', '.join(I['drms'][k] for k, _ in cp[:12]) + (' ...' if len(cp) > 12 else ''))
    for kd, ks in sorted(I['refs'].get(sid, {}).items()):
        print('  ref %-8s %4d DRMs: %s' % (kd, len(ks), ', '.join(I['drms'][k] for k in sorted(ks)[:8])))
    if S.nat:
        called = collections.Counter()
        for (s, off, call), n in I['calls'].items():
            if s == sid and call: called[off] += n
        for off, (k, proto, native) in sorted(S.funcs.items()):
            print('  f%-3d proto %-6s +0x%04x %s calls %d' % (k, proto, off, 'native' if native else 'code  ', called.get(off, 0)))


# ------------------------------------------------------------------------------------------------ texts
def cmd_texts(argv):
    import locals as LC
    spec = int(argv[argv.index('--lang') + 1], 16) if '--lang' in argv else 0xfffff7e1
    I = load()
    f, e = LC.files('pcpatch')
    _, strings, offs = LC.parse(f[spec], e)
    n = len(strings)
    ref = I['texts']
    used = {i for i in ref if i < n}
    kinds = collections.Counter()
    for i in used:
        for kd in set(kd for kd, _ in ref[i]): kinds[kd] += 1
    empty = {i for i in range(n) if not strings[i].strip()}
    rows = ['# PC locals (patch, spec %08x): %d ids; referenced by a script text leaf / record: %d (%s); empty strings %d'
            % (spec, n, len(used), ', '.join('%s %d' % kv for kv in sorted(kinds.items())), len(empty)),
            '# limits: computed ids (script arithmetic), DTP records and exe immediates are NOT seen - candidates only',
            '# id\tchars\tclass (no text copied)']
    runs = []
    for i in range(n):
        if i in used or i in empty: continue
        rows.append('%d\t%d\tunreferenced' % (i, len(strings[i])))
        if runs and runs[-1][1] == i - 1: runs[-1][1] = i
        else: runs.append([i, i])
    p = write('texts_unref.tsv', rows)
    print(rows[0]); print('unreferenced non-empty: %d in %d runs -> %s' % (len(rows) - 3, len(runs), p))
    print('runs (>= 5 ids): ' + ', '.join('%d-%d' % (a, b) for a, b in runs if b - a >= 4))
    if '--ids' in argv:
        for x in argv[argv.index('--ids') + 1].split(','):
            i = int(x)
            print('  %d: %s' % (i, sorted(set(('%s %s' % (kd, I['drms'][k])) for kd, k in ref.get(i, set())))[:6]))


def cmd_idwords(argv):
    """idwords REGEX ID[,ID|A-B..] [--u16]: every u32 (or u16 at even offsets) word equal to one of the ids in the
    sections of the indexed DRMs whose label matches REGEX (e.g. 'generalbank|g_pda'); counts per section"""
    import drm_write as DW
    I = load(); rx = re.compile(argv[0]); want = set()
    for p in argv[1].split(','):
        a, _, b = p.partition('-'); want |= set(range(int(a), int(b or a) + 1))
    w16 = '--u16' in argv
    get = dict(sources(I.get('mods')))
    hits = collections.defaultdict(list)
    for lbl in I['drms']:
        if not rx.search(lbl): continue
        D = DW.read(get[lbl](), 'le')
        for s in D.sections:
            if not s.data or s.type in (2, 5, 6, 9, 12): continue
            fmt, step = ('<H', 2) if w16 else ('<I', 4)
            for o in range(0, len(s.data) - step + 1, step):
                v = struct.unpack_from(fmt, s.data, o)[0]
                if v in want: hits[v].append('%s %d:%d+0x%x' % (lbl, s.type, s.id, o))
    for v in sorted(want):
        h = hits.get(v, [])
        print('%5d  %3d  %s' % (v, len(h), ' | '.join(h[:5])))


def main(argv):
    if not argv: print(__doc__); return 2
    if argv[0] == 'idwords': return cmd_idwords(argv[1:])
    cmd = argv[0]
    return {'index': cmd_index, 'objects': cmd_objects, 'scripts': cmd_scripts, 'texts': cmd_texts,
            'script': cmd_script}[cmd](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
