"""Place the cut dlc2_uo_jump_target (object 1042) back into the PC dlc2_machine_room (test 50l, 2026-11-03).

The Lara's Shadow prototype (Feb 2009) places object 1042 twice in dlc2_machine_room (unique ids 12126 / 12127), each
intro with its own instance script (8:24920 / 8:24921, subclass of the object script 8:24924) whose instanceref
member names the neighbouring piston_b intro. The final unit lost both. This tool reads the prototype unit (Xbox,
decoded) and the converted prototype scripts, and writes a PC unit with the two intros + scripts added.

Modes (from the repository root; --be = the DRM is an Xbox big-endian file):
  ../bin/pyt -t 300 tools/jump_target_place.py refs DRM SECINDEX [TARGET_HEX] [--be]
      every internal / external relocation that points INTO section SECINDEX (who uses that section, at which offset)
  ../bin/pyt -t 300 tools/jump_target_place.py uids DRM UID[,UID] [--be]
      the intro records (unit DTP Level+0x74) with these unique ids: object id, position, script id (+0x7c)
  ../bin/pyt -t 900 tools/jump_target_place.py uidscan FOLDER UID[,UID] [--be]
      every unit DRM under FOLDER: is one of the unique ids an intro (+0x58) or node (unit DTP +0xb4 record +0x20) id?
  ../bin/pyt -t 1800 tools/jump_target_place.py uidpack BIGFILE UID[,UID] [--be]
      the same for every DRM record of a bigfile (PC base: ../data/pc/bigfile.000, ../data/pc/patch.000)
  ../bin/pyt -t 300 tools/jump_target_place.py layout UNIT.drm [--be]
      where the intro array sits in the unit DTP and which relocations point into / behind it
  ../bin/pyt -t 300 tools/jump_target_place.py introblocks UNIT.drm [UID,UID] [--be]
      the blocks the intros point to (+0x78 / +0x84), with their users (unique ids) and first words
  ../bin/pyt -t 300 tools/jump_target_place.py cmp A.drm B.drm TYPE [ID,ID] [--be]
      sections of TYPE shared by id: identical (data + relocations, external targets by type:id) or not
  ../bin/pyt -t 300 tools/jump_target_place.py symuse DRM SYM[,SYM] [--be]
      scripts named by these Symbol ids, and member DataTypes whose userType is one of them (with the script id)
  ../bin/pyt -t 900 tools/jump_target_place.py build RETAIL_PC_UNIT CONVERTED_PROTO_PC_UNIT PROTO_XBOX_UNIT
                    FINAL_XBOX_UNIT OBJECT_PC_DRM OUT.drm [--uids 12126,12127]
      writes OUT = the retail PC unit with the prototype intros of these unique ids added:
      * record words from the prototype (Xbox) by the byte-order rule that holds for every retail pair (final Xbox <->
        PC by unique id); words without one rule: per u16 half (swap / value table), the object id by name through the
        object lists, or a whole-word value table; the result must equal the converter's output of the whole prototype
        unit (CONVERTED_PROTO_PC_UNIT = convert_dlc.py + dlc_fixes_build.py of the prototype unit) word for word
      * pointer slots (+0x84): the retail block whose users are exactly the prototype block's other users
      * a fresh intro array (retail order, each new intro after its nearest prototype predecessor) at the end of the
        unit DTP, count +0xc and pointer +0x10 updated; the old array stays (refused if anything else points into it)
      * the intros' instance scripts (+0x7c) from the converted prototype unit plus the closure of their external
        pointers (from OBJECT_PC_DRM where it has the section - must be identical to the converted copy); a needed
        section the retail unit has must be identical, else STOP
      * CDRM like the input; read back: relocation bounds, old intros and every other section unchanged
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import unit_ids as U


def load(path, en):
    return DW.read(open(path, 'rb').read(), en)


def secdicts(D):
    return [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]


def cmd_refs(argv, en):
    D = load(argv[0], en); tgt = int(argv[1])
    only = int(argv[2], 16) if len(argv) > 2 else None      # optional: only pointers to this target offset (hex)
    hits = collections.defaultdict(list)
    for si, s in enumerate(D.sections):
        r = R.parse(s.reloc, en)
        if si == tgt:
            for o, t in r.internal:
                if only is None or t == only: hits[si].append((o, t, 'int'))
        for xs, o, t in r.external:
            if xs == tgt and (only is None or t == only): hits[si].append((o, t, 'ext'))
    for si in sorted(hits):
        s = D.sections[si]
        l = sorted(hits[si])
        print('section %4d %2d:%-6d -> %d pointers into section %d' % (si, s.type, s.id, len(l), tgt))
        for o, t, k in l[:60]:
            print('    %s +0x%06x -> +0x%06x' % (k, o, t))
        if len(l) > 60: print('    ... %d more' % (len(l) - 60))


def intro_map(D, en):
    L = U.level_info(secdicts(D), en)
    if L is None: raise SystemExit('not a unit DRM')
    E = '>' if en == 'be' else '<'
    out = {}
    for si, o in L['intros']:
        d = D.sections[si].data
        out[struct.unpack_from(E + 'I', d, o + 0x58)[0]] = (si, o)
    return L, out


def cmd_uids(argv, en):
    D = load(argv[0], en); E = '>' if en == 'be' else '<'
    L, m = intro_map(D, en)
    for u in (int(x) for x in argv[1].split(',')):
        if u not in m: print('unique id %d: no intro' % u); continue
        si, o = m[u]; d = D.sections[si].data
        oid = struct.unpack_from(E + 'H', d, o + 0x50)[0] if en == 'le' else struct.unpack_from(E + 'H', d, o + 0x50)[0]
        print('unique id %6d: section %d +0x%x  object +0x50 words %08x  pos %.1f %.1f %.1f  rot %.4f %.4f %.4f  +0x7c %d' % (
            u, si, o, struct.unpack_from(E + 'I', d, o + 0x50)[0], *struct.unpack_from(E + '3f', d, o + 0x10),
            *struct.unpack_from(E + '3f', d, o), struct.unpack_from(E + 'I', d, o + 0x7c)[0]))


def unit_uids(D, en):
    """{unique id: kind} of every intro (+0x58) and node (unit DTP +0xb4 record +0x20) of a unit DRM, or None"""
    L = U.level_info(secdicts(D), en)
    if L is None: return None
    E = '>' if en == 'be' else '<'
    out = {}
    for si, o in L['intros']: out[struct.unpack_from(E + 'I', D.sections[si].data, o + 0x58)[0]] = 'intro'
    for si, o in L['nodes']: out.setdefault(struct.unpack_from(E + 'I', D.sections[si].data, o + 0x20)[0], 'node')
    return out


def cmd_uidscan(argv, en):
    """every unit DRM of a folder (and sub folders): do the given unique ids exist as intro / node ids?"""
    root = argv[0]; want = {int(x) for x in argv[1].split(',')}
    n = 0; hits = 0; lo = hi = None
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.lower().endswith('.drm'): continue
            try: D = load(os.path.join(dp, f), en)
            except Exception: continue
            m = unit_uids(D, en)
            if m is None: continue
            n += 1
            if m:
                lo = min(m) if lo is None else min(lo, min(m)); hi = max(m) if hi is None else max(hi, max(m))
            for u in sorted(want & set(m)):
                hits += 1; print('%s: unique id %d is a %s' % (os.path.relpath(os.path.join(dp, f), root), u, m[u]))
    print('%d unit DRMs scanned under %s, unique ids %s..%s, %d hits for %s' % (n, root, lo, hi, hits, sorted(want)))


def cmd_uidpack(argv, en):
    """as uidscan, for every DRM record of a bigfile (e.g. ../data/pc/bigfile.000, patch.000)"""
    from archive import Archive
    A = Archive(argv[0], en); want = {int(x) for x in argv[1].split(',')}
    seen = set(); n = 0; hits = 0; lo = hi = None
    for r in A.idx:
        if r['hash'] in seen: continue
        seen.add(r['hash'])
        try: D = DW.read(A.read(r), en)
        except Exception: continue
        m = unit_uids(D, en)
        if m is None: continue
        n += 1
        if m:
            lo = min(m) if lo is None else min(lo, min(m)); hi = max(m) if hi is None else max(hi, max(m))
        for u in sorted(want & set(m)):
            hits += 1; print('0x%08x: unique id %d is a %s' % (r['hash'], u, m[u]))
    print('%d unit DRMs in %s, unique ids %s..%s, %d hits for %s' % (n, argv[0], lo, hi, hits, sorted(want)))


def intro_array(D, en):
    """(section index, array start, count) of the unit's intro array (unit DTP Level+0x74: +0xc count, +0x10 pointer)"""
    L = U.level_info(secdicts(D), en)
    if L is None or not L['intros']: raise SystemExit('no intro array')
    si = L['intros'][0][0]
    return si, L['intros'][0][1], len(L['intros'])


def cmd_layout(argv, en):
    """where the intro array sits in the unit DTP and what points into / behind it"""
    D = load(argv[0], en); E = '>' if en == 'be' else '<'
    si, a0, n = intro_array(D, en); a1 = a0 + 0x90 * n
    s = D.sections[si]; r = R.parse(s.reloc, en)
    print('unit DTP: section %d %d:%d, %d bytes; intro array +0x%x .. +0x%x (%d x 0x90); count word +0xc = %d' % (
        si, s.type, s.id, len(s.data), a0, a1, n, struct.unpack_from(E + 'I', s.data, 0xc)[0]))
    inside = [(o, t) for o, t in r.internal if a0 <= o < a1]
    print('  internal pointers stored inside the array: %d' % len(inside))
    for o, t in inside[:20]: print('    +0x%x (intro %d +0x%x) -> +0x%x' % (o, (o - a0) // 0x90, (o - a0) % 0x90, t))
    into = [(o, t) for o, t in r.internal if a0 <= t <= a1]
    print('  internal pointers to the array (start .. end incl.): %d' % len(into))
    for o, t in into[:20]: print('    +0x%x -> +0x%x%s' % (o, t, ' (start)' if t == a0 else ' (end)' if t == a1 else ''))
    behind = [(o, t) for o, t in r.internal if t > a1 or o >= a1]
    print('  internal pointers stored behind / pointing behind the array: %d' % len(behind))
    ids_in = [(t, o) for t, o in r.idref + r.idref_a if a0 <= o < a1]
    print('  id references inside the array: %d, behind it: %d' % (len(ids_in), sum(1 for t, o in r.idref + r.idref_a if o >= a1)))
    ext_out = [(x, o, t) for x, o, t in r.external if o >= a0]
    print('  external pointers stored inside / behind the array: %d' % len(ext_out))
    ext_in = []
    for sj, t in enumerate(D.sections):
        for x, o, d in R.parse(t.reloc, en).external:
            if x == si: ext_in.append((sj, o, d))
    print('  external pointers from other sections into the unit DTP: %d (into / behind the array: %d)' % (
        len(ext_in), sum(1 for _, _, d in ext_in if d >= a0)))
    for sj, o, d in ext_in[:20]:
        print('    section %d %d:%d +0x%x -> +0x%x' % (sj, D.sections[sj].type, D.sections[sj].id, o, d))


def norm_reloc(D, s, en):
    """relocations of section s with the external targets named by (type, id) instead of section index"""
    r = R.parse(s.reloc, en)
    ext = sorted((D.sections[x].type, D.sections[x].id, o, d) for x, o, d in r.external)
    return (sorted(r.internal), ext, sorted(r.idref_a), sorted(r.idref))


def same_section(A, a, B, b, en='le'):
    return a.data == b.data and norm_reloc(A, a, en) == norm_reloc(B, b, en)


def block_sig(s, r_int, t, n=0x30, E='<'):
    """first n bytes of the unit DTP at t, with every internal pointer slot replaced by its target relative to t"""
    d = bytearray(s.data[t:t + n])
    for o in range(t, t + n, 4):
        if o in r_int: d[o - t:o - t + 4] = struct.pack(E + 'i', r_int[o] - t)
    return bytes(d)


def cmd_introblocks(argv, en):
    """the blocks the intros point to with +0x78 / +0x84: target, users (by unique id), signature words"""
    D = load(argv[0], en); E = '>' if en == 'be' else '<'
    si, a0, n = intro_array(D, en); s = D.sections[si]; ri = dict(R.parse(s.reloc, en).internal)
    users = collections.defaultdict(list)
    for k in range(n):
        o = a0 + 0x90 * k
        uid = struct.unpack_from(E + 'I', s.data, o + 0x58)[0]
        for f in (0x78, 0x84):
            if o + f in ri: users[ri[o + f], f].append(uid)
    want = {int(x) for x in argv[1].split(',')} if len(argv) > 1 else None
    for (t, f), us in sorted(users.items()):
        if want and not want & set(us): continue
        sig = block_sig(s, ri, t, E=E)
        print('+0x%06x via +0x%02x: %3d intros (%s)  %s' % (t, f, len(us), ' '.join(map(str, (us if want else us[:6]))) + (' ..' if len(us) > 6 and not want else ''),
              ' '.join('%08x' % w for w in struct.unpack_from(E + '12I', sig, 0))))


def cmd_cmp(argv, en):
    """sections of the given type shared by id between two PC DRMs: identical (data + relocations with external
    targets by type:id) or not; for the differing ones the number of differing words / relocation lists"""
    A = load(argv[0], en); B = load(argv[1], en); typ = int(argv[2])
    only = {int(x) for x in argv[3].split(',')} if len(argv) > 3 else None
    a = {s.id: s for s in A.sections if s.type == typ}; b = {s.id: s for s in B.sections if s.type == typ}
    shared = sorted(i for i in set(a) & set(b) if only is None or i in only)
    same = 0
    for i in shared:
        if same_section(A, a[i], B, b[i], en): same += 1; continue
        x, y = a[i], b[i]
        nw = sum(1 for o in range(0, min(len(x.data), len(y.data)) - 3, 4) if x.data[o:o + 4] != y.data[o:o + 4])
        ra, rb = norm_reloc(A, x, en), norm_reloc(B, y, en)
        print('  %d:%d differs: size %d / %d, %d words differ, reloc lists differ: %s' % (typ, i, len(x.data), len(y.data), nw,
              ','.join(k for k, p, q in zip(('int', 'ext', 'idA', 'id'), ra, rb) if p != q) or 'none'))
    print('type %d: A %d, B %d, shared %d, identical %d' % (typ, len(a), len(b), len(shared), same))
    if only:
        for i in sorted(only):
            print('  %d:%d in A: %s, in B: %s' % (typ, i, i in a, i in b))


# ---------------------------------------------------------------------------------------------------------------- build

RULES = {'swap32': lambda w: w[::-1], 'swap16x2': lambda w: w[1::-1] + w[3:1:-1], 'keep': lambda w: w}


def intro_records(D, en):
    """[(unique id, record bytes, {field offset: internal pointer target})] in array order"""
    E = '>' if en == 'be' else '<'
    si, a0, n = intro_array(D, en); s = D.sections[si]; ri = dict(R.parse(s.reloc, en).internal)
    out = []
    for k in range(n):
        o = a0 + 0x90 * k
        out.append((struct.unpack_from(E + 'I', s.data, o + 0x58)[0], s.data[o:o + 0x90],
                    {f: ri[o + f] for f in range(0, 0x90, 4) if o + f in ri}))
    return out


def learn_intro_rules(F, P):
    """per word of the 0x90-byte intro: the byte-order rules that hold for EVERY retail pair (final Xbox F, PC P,
    paired by unique id); None = a pointer slot in at least one pair"""
    xf = {u: (r, p) for u, r, p in intro_records(F, 'be')}; pf = {u: (r, p) for u, r, p in intro_records(P, 'le')}
    pairs = [(xf[u], pf[u]) for u in xf if u in pf]
    rules = {}
    for f in range(0, 0x90, 4):
        ok = set(RULES)
        for (xr, xp), (pr, pp) in pairs:
            if f in xp or f in pp: ok = None; break
            ok &= {k for k, fn in RULES.items() if fn(xr[f:f + 4]) == pr[f:f + 4]}
        rules[f] = ok
        if ok == set():                                         # no byte rule: show the value pairs (distinct)
            ex = collections.Counter((xr[f:f + 4].hex(), pr[f:f + 4].hex()) for (xr, _), (pr, _) in pairs)
            print('  +0x%02x has no byte-order rule; %d distinct Xbox -> PC values, e.g. %s' % (
                f, len(ex), ', '.join('%s->%s x%d' % (a, b, c) for (a, b), c in ex.most_common(8))))
            # half-word rules: each u16 stays in place, byte-swapped ('swap16') or through a value table learned from
            # the pairs ('table'); and a whole-word value table (every pair with this Xbox value has one PC value)
            halves = []
            for h in (0, 2):
                sw = all(pr[f + h:f + h + 2] == xr[f + h:f + h + 2][::-1] for (xr, _), (pr, _) in pairs)
                tab = collections.defaultdict(set)
                for (xr, _), (pr, _) in pairs: tab[xr[f + h:f + h + 2]].add(pr[f + h:f + h + 2])
                halves.append('swap16' if sw else ('table', {k: next(iter(v)) for k, v in tab.items() if len(v) == 1}))
            wt = collections.defaultdict(set)
            for (xr, _), (pr, _) in pairs: wt[xr[f:f + 4]].add(pr[f:f + 4])
            rules[f] = ('halves', halves, {k: next(iter(v)) for k, v in wt.items() if len(v) == 1})
            print('        u16 halves: %s; whole-word values with one PC value: %d' % (
                ', '.join(h if h == 'swap16' else 'table of %d values' % len(h[1]) for h in halves), len(rules[f][2])))
    return rules, len(pairs)


def objlist_names(path):
    d = {}
    for l in open(path, encoding='utf8', errors='ignore'):
        p = l.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1].lower()
    return d


XBOX_OBJECTLIST = 'work/generic/lists/dlc_pack11_objectlist.txt'
PC_OBJECTLIST = 'work/generic/merged/tr8/pc-w/objectlist.txt'


def conv_word(rule, f, xw, notes):
    """PC bytes of one plain (non-pointer) intro word xw (Xbox bytes) by the learned rule, or None"""
    if isinstance(rule, set):
        res = {RULES[q](xw) for q in rule}
        return res.pop() if len(res) == 1 else None
    _, halves, wtab = rule
    if xw in wtab: notes.append('+0x%02x whole-word value table %s -> %s' % (f, xw.hex(), wtab[xw].hex())); return wtab[xw]
    out = b''
    for h, hr in zip((0, 2), halves):
        xv = xw[h:h + 2]
        if hr == 'swap16': out += xv[::-1]; continue
        if xv in hr[1]: out += hr[1][xv]; notes.append('+0x%02x half %d value table' % (f, h)); continue
        if f == 0x50 and h == 0:                                # Intro.objectID: by name through the object lists
            xid = struct.unpack('>H', xv)[0]
            xn = objlist_names(XBOX_OBJECTLIST).get(xid)
            pid = [k for k, v in objlist_names(PC_OBJECTLIST).items() if v == xn]
            if xn and len(pid) == 1:
                out += struct.pack('<H', pid[0]); notes.append('+0x50 object id Xbox %d %s -> PC %d (object lists by name)' % (xid, xn, pid[0])); continue
        return None
    return out


def users_of(recs, field, target):
    return frozenset(u for u, _, p in recs if p.get(field) == target)


def remap_ext(donor, s, out_index):
    """relocation blob of donor section s with external section indices remapped to the output file"""
    r = R.parse(s.reloc, 'le')
    ext = []
    for x, o, d in r.external:
        t = donor.sections[x]
        if t.type == 0: raise SystemExit('STOP: section %d:%d points into a type-0 section (ambiguous)' % (s.type, s.id))
        ext.append((out_index[t.type, t.id], o, d))
    r.external = ext
    return R.write(r, 'le')


def cmd_build(argv, en):
    """build RETAIL_PC_UNIT CONVERTED_PROTO_PC_UNIT PROTO_XBOX_UNIT FINAL_XBOX_UNIT OBJECT_PC_DRM OUT [--uids A,B]"""
    retail, conv, proto_x, final_x, objdrm, out = argv[:6]
    uids = [int(x) for x in argv[argv.index('--uids') + 1].split(',')] if '--uids' in argv else [12126, 12127]
    P = load(retail, 'le'); C = load(conv, 'le'); X = load(proto_x, 'be'); F = load(final_x, 'be'); O = load(objdrm, 'le')
    bad = []

    # 1. the intro records: from the prototype (Xbox) by the byte-order rules every retail pair obeys; cross-checked
    #    against the converter's output of the whole prototype unit
    rules, npairs = learn_intro_rules(F, P)
    print('intro byte-order rules learned from %d retail pairs (final Xbox <-> PC by unique id):' % npairs)
    print('  ' + ' '.join('+%02x:%s' % (f, 'ptr' if r is None else ('halves' if isinstance(r, tuple) else '/'.join(sorted(r)))) for f, r in sorted(rules.items())))
    xrecs = intro_records(X, 'be'); crecs = intro_records(C, 'le'); precs = intro_records(P, 'le')
    xmap = {u: (k, r, p) for k, (u, r, p) in enumerate(xrecs)}; cmap = {u: (r, p) for u, r, p in crecs}
    pu = [u for u, _, _ in precs]
    for u in uids:
        if u in pu: raise SystemExit('STOP: unique id %d already exists in the retail unit' % u)
    new = []
    for u in uids:
        k, xr, xp = xmap[u]
        rec = bytearray(0x90); notes = []
        for f in range(0, 0x90, 4):
            if f in xp: continue                                # pointer slot: set below
            r = rules[f]
            if r is None:                                       # a pointer slot in the retail pairs, plain here
                if xr[f:f + 4] != b'\0\0\0\0': bad.append('uid %d +0x%x: retail pointer slot holds %s' % (u, f, xr[f:f + 4].hex()))
                continue
            w = conv_word(r, f, xr[f:f + 4], notes)
            if w is None: bad.append('uid %d +0x%x: no rule gives one value for %s' % (u, f, xr[f:f + 4].hex())); continue
            rec[f:f + 4] = w
        for nt in notes: print('  uid %d: %s' % (u, nt))
        cr, cp = cmap[u]
        diff = [f for f in range(0, 0x90, 4) if f not in xp and rec[f:f + 4] != cr[f:f + 4]]
        print('uid %d (prototype index %d): object %d, pos %.1f %.1f %.1f, rot %.4f %.4f %.4f, scale %.4f %.4f %.4f, '
              'script +0x7c %d; words != converter output: %s' % (
                  u, k, struct.unpack_from('<H', rec, 0x50)[0], *struct.unpack_from('<3f', rec, 0x10),
                  *struct.unpack_from('<3f', rec, 0), *struct.unpack_from('<3f', rec, 0x40),
                  struct.unpack_from('<I', rec, 0x7c)[0], ['+0x%x' % f for f in diff] or 'none'))
        if diff: bad.append('uid %d differs from the converter at %s' % (u, diff))
        if set(cp) != set(xp): bad.append('uid %d pointer slots Xbox %s / converter %s' % (u, sorted(xp), sorted(cp)))
        for f in xp: rec[f:f + 4] = cr[f:f + 4]                 # the relocated slot's file bytes (placeholder) as converted
        # pointer slots: the block the same neighbours share in the retail unit
        ptrs = {}
        for f, t in sorted(xp.items()):
            peers = users_of(xrecs, f, t) - set(uids)
            cand = sorted({p.get(f) for v, _, p in precs if v in peers and f in p})
            match = [t2 for t2 in cand if users_of(precs, f, t2) == peers]
            print('  +0x%02x -> prototype block +0x%x shared by %d other intros; retail block with exactly these users: %s'
                  % (f, t, len(peers), ['+0x%x' % m for m in match] or 'NONE'))
            if len(match) != 1 or not peers: bad.append('uid %d +0x%x: no unique retail block' % (u, f)); continue
            ptrs[f] = match[0]
        new.append((u, k, bytes(rec), ptrs))
    if bad:
        for b in bad: print('STOP: ' + b)
        raise SystemExit(1)

    # 2. the new intro array: retail order, each new intro behind its prototype predecessor (the nearest one the
    #    retail unit has), written as a fresh array at the end of the unit DTP; the old array stays as it is (nothing
    #    but the array pointer +0x10 points into it - checked), so no other byte of the unit moves
    si, a0, n = intro_array(P, 'le'); s = P.sections[si]; r = R.parse(s.reloc, 'le')
    a1 = a0 + 0x90 * n
    inside = [o for o, t in r.internal if a0 < t < a1]
    ext_inside = [(j, o) for j, t in enumerate(P.sections) for x, o, d in R.parse(t.reloc, 'le').external if x == si and a0 <= d < a1]
    ids_inside = [o for t, o in r.idref + r.idref_a if a0 <= o < a1] + [o for x, o, d in r.external if a0 <= o < a1]
    print('retail unit DTP %d:%d: %d intros at +0x%x; pointers into the array other than its start: internal %d, external %d; '
          'id / external relocations inside it: %d' % (s.type, s.id, n, a0, len(inside), len(ext_inside), len(ids_inside)))
    if inside or ext_inside or ids_inside: raise SystemExit('STOP: something points into the intro array')
    order = [(u, rec, p) for u, rec, p in precs]
    xorder = [u for u, _, _ in xrecs]
    for u, k, rec, ptrs in new:
        pos = len(order)
        for prev in reversed(xorder[:k]):
            hit = [i for i, (v, _, _) in enumerate(order) if v == prev]
            if hit: pos = hit[0] + 1; print('uid %d placed after %d (its nearest prototype predecessor the retail unit has), new index %d' % (u, prev, pos)); break
        order.insert(pos, (u, rec, ptrs))
    data = bytearray(s.data)
    data += b'\0' * (-len(data) % 16)
    b0 = len(data)
    internal = list(r.internal)
    for i, (u, rec, ptrs) in enumerate(order):
        data += rec
        internal += [(b0 + 0x90 * i + f, t) for f, t in sorted(ptrs.items())]
    struct.pack_into('<I', data, 0xc, len(order))
    if sum(1 for o, t in internal if o == 0x10 and t == a0) != 1: raise SystemExit('STOP: no internal pointer +0x10 -> array')
    internal = [(o, b0 if o == 0x10 else t) for o, t in internal]
    r.internal = internal
    print('new intro array: %d records at +0x%x (unit DTP %d -> %d bytes), count +0xc %d -> %d, pointer +0x10 -> +0x%x' % (
        len(order), b0, len(s.data), len(data), n, len(order), b0))
    s.data = bytes(data); s.reloc = R.write(r, 'le')

    # 3. the instance scripts + every section their external pointers need (closure); a section the retail unit
    #    already has must be identical (data + relocations by type:id) to the donor's, else the pointer offsets differ
    want = [(8, struct.unpack_from('<I', rec, 0x7c)[0]) for _, _, rec, _ in new]
    cs = {(t.type, t.id): t for t in C.sections}; obs = {(t.type, t.id): t for t in O.sections}
    have = {(t.type, t.id): t for t in P.sections}
    added = []; queue = [(k, C) for k in want]; seen = set()
    while queue:
        key, via = queue.pop(0)
        if key in seen: continue
        seen.add(key)
        if key in have:
            if key in want: raise SystemExit('STOP: %d:%d already in the retail unit' % key)
            dv = (cs if via is C else obs)[key]
            ok = same_section(via, dv, P, have[key])
            print('  needed %d:%d is in the retail unit; identical to the donor copy: %s' % (key + (ok,)))
            if not ok: raise SystemExit('STOP: %d:%d differs' % key)
            continue
        donor, src = (O, 'object DRM') if key in obs else (C, 'converted prototype unit')
        sec = (obs if donor is O else cs)[key]
        if donor is O and key in cs and not same_section(O, sec, C, cs[key]): raise SystemExit('STOP: %d:%d object / unit differ' % key)
        added.append((key, donor, sec, src))
        for x, o, d in R.parse(sec.reloc, 'le').external:
            t = donor.sections[x]; queue.append(((t.type, t.id), donor))
    base = len(P.sections)
    for key, donor, sec, src in added:
        P.sections.append(DW.Section(sec.type, sec.id, sec.data, sec.reloc, sec.flags, sec.ver, sec.spec, sec.pad))
    cnt = collections.Counter((t.type, t.id) for t in P.sections if t.type != 0)
    index = {(t.type, t.id): j for j, t in enumerate(P.sections) if t.type != 0 and cnt[t.type, t.id] == 1}
    for j, (key, donor, sec, src) in enumerate(added):
        P.sections[base + j].reloc = remap_ext(donor, sec, index)
        rr = R.parse(sec.reloc, 'le')
        print('added %d:%d as section %d (%d bytes, from the %s): internal %d, external %d, id refs %s' % (
            key + (base + j, len(sec.data), src, len(rr.internal), len(rr.external),
                   ' '.join(sorted({'%d:%d' % (t, struct.unpack_from('<I', sec.data, o)[0]) for t, o in rr.idref + rr.idref_a})))))

    # 4. write (CDRM like the retail file), read back, check
    raw = P.write('le')
    blob = DW.cdrm_encode(raw, 'le') if open(retail, 'rb').read(4) == b'CDRM' else raw
    open(out, 'wb').write(blob)
    Q = load(out, 'le')
    secs = secdicts(Q); probs = 0
    for t in Q.sections:
        probs += len(R.check(R.parse(t.reloc, 'le'), len(t.data), secs))
    qrecs = intro_records(Q, 'le')
    got = {u: (rec, p) for u, rec, p in qrecs}
    for u, k, rec, ptrs in new:
        if got[u][0] != rec or got[u][1] != ptrs: probs += 1; print('read back: uid %d differs' % u)
    old = {u: (rec, p) for u, rec, p in precs}
    probs += sum(1 for u in old if got.get(u) != old[u])
    probs += sum(1 for t, q in zip(load(retail, 'le').sections, Q.sections) if (t.type, t.id) != (q.type, q.id)
                 or ((t.data, t.reloc) != (q.data, q.reloc) and (t.type, t.id) != (s.type, s.id)))
    print('written %s: %d bytes (%d raw), %d sections, %d intros; read back: relocation bounds, the %d retail intros, the '
          'new intros and every other retail section unchanged - problems %d' % (out, len(blob), len(raw), len(Q.sections),
                                                                               len(qrecs), len(old), probs))
    if probs: raise SystemExit(1)


def cmd_symuse(argv, en):
    """where Symbol ids (u16) occur as script names (root +0x08 / +0x0a) or as a member's DataType userType (the u16
    at +4 of a 12-byte DataType whose union word is an id-8 reference): which scripts carry / use them"""
    D = load(argv[0], en); E = '>' if en == 'be' else '<'
    want = {int(x, 0) for x in argv[1].split(',')}
    for s in D.sections:
        if s.type != 8 or len(s.data) < 0x10: continue
        a, b = struct.unpack_from(E + 'HH', s.data, 8)
        if a in want or b in want: print('8:%d name symbols 0x%04x 0x%04x' % (s.id, a, b))
        r = R.parse(s.reloc, en)
        for t, o in r.idref:                                    # DataType: tag @o-8, userType u16 @o-4, id8 @o
            if t != 8 or o < 8: continue
            ut = struct.unpack_from(E + 'H', s.data, o - 4)[0]
            if ut in want:
                print('8:%d +0x%x: DataType tag 0x%x userType 0x%04x -> script 8:%d' % (
                    s.id, o - 8, struct.unpack_from(E + 'I', s.data, o - 8)[0], ut, struct.unpack_from(E + 'I', s.data, o)[0]))


def main(argv):
    en = 'be' if '--be' in argv else 'le'
    argv = [a for a in argv if a != '--be']
    {'refs': cmd_refs, 'uids': cmd_uids, 'uidscan': cmd_uidscan, 'uidpack': cmd_uidpack, 'layout': cmd_layout,
     'cmp': cmd_cmp, 'introblocks': cmd_introblocks, 'build': cmd_build, 'symuse': cmd_symuse}[argv[0]](argv[1:], en)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
