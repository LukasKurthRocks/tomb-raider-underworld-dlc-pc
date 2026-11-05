"""Object data DTP fixes: texture group counts (F16) and particle record words (F3 / B24) of converted DLC DRMs
(read-only unless --out-dir; agent N7, night 04.11.2026, docs Befund-Ton-und-Abstuerze-0411.md).

The object data DTP is the DTP an object section (type 11) names at +8 (id reference to type 7). Engine facts and the
two converter faults (analysis N5, same night):

  texcount  tru+0x12b360 (object post-load) walks u16 [D+0x64] groups at [D+0x68]: {u32 n, u32 textureId[n]} and ANDs
            every id with 0x1fff. The converter left some group counts n raw (Xbox 00000003 -> PC 03000000), so the
            engine ANDs 0x1fff over 50 M dwords of game memory (F16 crash after level.load dlc2_machine_room, FMOD
            mixer object destroyed). Truth: n is a u32 on both platforms (proof below), PC n = Xbox n.
  rec       the 0x17c-byte particle records (u16 [D+0x0c] x 0x17c at [D+0x10]) carry byte / u16 fields that the
            emitter set-up (tru+0x1442b9 ff., tru+0x1453a5) reads one by one; the converter swapped some of them as
            u32 (record +0x148 {u8 anim, u8, u16 spawn bits}: anim 0x41 = 65 instead of 0xff -> B24 crash
            tru+0x42e62). Truth: the per-offset byte class (s32 / s16 / u16u8u8 / u8u8u16 / raw) proven on the base
            Xbox / PC pairs (tools/objdata_rec_classes.py calibrate, cache work/generic/objdata_rec_rules.pkl).

Both steps change only words whose PC bytes are another byte order of the Xbox bytes (same byte multiset); a word
with other bytes (re-numbered on purpose) is kept and counted. Relocated pointer / id slots are never touched. Every
copy of a DTP id in the DRM is fixed (the engine loads the FIRST copy; F3: goo_drips 24414 section 1 wrong, section
48 right); copies are paired in order with the Xbox copies (or all with the single Xbox copy).

Modes (from the repository root):
  ../bin/pyt -t 1800 tools/objdata_fx_fix.py proof [OBJECTLIST]
        base pairs (PC objectlist ids 1..821, default work/generic/lists/pc_objectlist.txt): texture group counts and
        ids Xbox vs PC (walked independently on both sides), record rules recomputed in memory and compared with
        the cache (the cache is not written)
  ../bin/pyt -t 1800 tools/objdata_fx_fix.py check PATH [PATH ...] [--steps texcount,rec] [--out-dir DIR]
        [--pack pack11] [--log FILE] [-v]
        PATH = PC .drm or folder (not recursive); the Xbox source by name (tools/convert_dlc.raw_dlc,
        TRUDLC_PACK_FIRST = --pack, default pack11). Prints per file / DTP / copy the planned words; --out-dir writes
        each changed DRM as DIR/<name> and proves: written file reads back, the decoded raw DRM differs from the
        input ONLY in the planned words, all relocation blobs / section headers identical, re-check plans 0 words.
        DIR/md5.tsv (md5 TAB path, the format of the other work/rebuild trees) lists the written files.
  ../bin/pyt -t 300 tools/objdata_fx_fix.py xbox NAME.drm OUT.drm [--pack pack11]
        writes the decoded Xbox source of NAME (for the other check tools)
Library (tools/dlc_struct_fixes.py steps 'objtex' / 'objrec'): fix_drm(XD, PD, steps, rules) -> (changes, notes).
"""
import sys, os, struct, pickle, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R
import objdata_rec_classes as RC

ROOT = os.path.abspath(os.path.join(HERE, '..'))
PERMS = RC.PERMS
REC = RC.REC
STEPS = ('texcount', 'rec')


def perm(b, p):
    return bytes(b[i] for i in p)


def load_rules():
    return pickle.load(open(RC.RULES, 'rb'))


def od_ids(D, e):
    return RC.objdata_dtps(D.sections, e, lambda s: (s.type, s.data, s.reloc, s.id))


def copies(D, did):
    return [s for s in D.sections if s.type == 7 and s.id == did]


def pair_copies(xc, pc):
    if not xc or not pc:
        return None
    if len(xc) == len(pc):
        return list(zip(xc, pc))
    if len(xc) == 1:
        return [(xc[0], p) for p in pc]
    return None


def slot_set(reloc, e):
    return RC.slots(reloc, e)[0]


# ---------------------------------------------------------------- texcount
def tex_plan(xs, ps):
    """(changes [(off, old, new, note)], stats Counter) or (None, reason)"""
    xd, pd = bytes(xs.data), bytes(ps.data)
    st = collections.Counter()
    if len(pd) < 0x6c or len(xd) < 0x6c:
        return [], st
    xg = struct.unpack_from('>H', xd, 0x64)[0]
    pg = struct.unpack_from('<H', pd, 0x64)[0]
    if not xg and not pg:
        return [], st
    if xg != pg:
        return None, 'u16 group count +0x64 Xbox %d PC %d' % (xg, pg)
    xi = dict(R.parse(xs.reloc, 'be').internal) if xs.reloc else {}
    pi = dict(R.parse(ps.reloc, 'le').internal) if ps.reloc else {}
    if 0x68 not in xi or xi.get(0x68) != pi.get(0x68):
        return None, 'group pointer +0x68 Xbox %s PC %s' % (xi.get(0x68), pi.get(0x68))
    psl = slot_set(ps.reloc, 'le') | slot_set(xs.reloc, 'be')
    p = pi[0x68]
    out = []
    for g in range(pg):
        if p + 4 > len(xd) or p + 4 > len(pd):
            return None, 'group %d header past the DTP end' % g
        xn = struct.unpack_from('>I', xd, p)[0]
        if p + 4 + 4 * xn > len(xd) or p + 4 + 4 * xn > len(pd):
            return None, 'Xbox group %d count %d runs past the DTP end' % (g, xn)
        want = struct.pack('<I', xn)
        got = pd[p:p + 4]
        st['groups'] += 1
        if got != want:
            if p in psl or sorted(got) != sorted(want):
                return None, 'group %d count at +0x%x PC %s Xbox n %d: no byte order of the Xbox word - not touched' % (
                    g, p, got.hex(), xn)
            out.append((p, got, want, 'group %d count (PC read 0x%08x, Xbox %d)' % (g, struct.unpack('<I', got)[0], xn)))
        for j in range(xn):
            q = p + 4 + 4 * j
            xv = struct.unpack_from('>I', xd, q)[0]
            pv = struct.unpack_from('<I', pd, q)[0]
            st['ids'] += 1
            if xv == pv:
                st['ids_same'] += 1
            elif pd[q:q + 4] == xd[q:q + 4]:
                st['ids_raw'] += 1
            else:
                st['ids_other'] += 1
        p += 4 + 4 * xn
    return out, st


# ---------------------------------------------------------------- rec
def rec_plan(xs, ps, rules):
    xr, xsl = RC.records(bytes(xs.data), 'be', xs.reloc)
    pr, psl = RC.records(bytes(ps.data), 'le', ps.reloc)
    st = collections.Counter()
    if not xr and not pr:
        return [], st
    if not xr or not pr or len(xr) != len(pr):
        return None, 'record lists differ (Xbox %s, PC %s)' % (None if xr is None else len(xr), None if pr is None else len(pr))
    xd, pd = bytes(xs.data), bytes(ps.data)
    out = []
    for k, (bx, bp) in enumerate(zip(xr, pr)):
        st['records'] += 1
        for o, (cls, n, _) in sorted(rules.items()):
            if (bx + o) in xsl or (bp + o) in psl:
                st['slot'] += 1
                continue
            xb, pb = xd[bx + o:bx + o + 4], pd[bp + o:bp + o + 4]
            want = perm(xb, PERMS[cls])
            st['words'] += 1
            if pb == want:
                continue
            if sorted(pb) != sorted(xb):
                st['kept_other'] += 1
                continue
            how = [c for c in PERMS if perm(xb, PERMS[c]) == pb]
            st['wrote_' + (how[0] if how else 'other')] += 1
            out.append((bp + o, pb, want, 'rec %d +0x%03x %s (Xbox %s, converter %s)' % (
                k, o, cls, xb.hex(), how[0] if how else 'other')))
    return out, st


# ---------------------------------------------------------------- per DRM
def fix_drm(XD, PD, steps, rules):
    """apply the steps to PD in place; returns (changes {(section index, off): (old, new, note, step)}, notes)"""
    changes = {}
    notes = []
    ids = sorted(set(od_ids(PD, 'le')) & set(od_ids(XD, 'be')))
    idx = {id(s): k for k, s in enumerate(PD.sections)}
    for did in ids:
        pairs = pair_copies(copies(XD, did), copies(PD, did))
        if pairs is None:
            notes.append('DTP %d: copies Xbox %d / PC %d cannot be paired - skipped' % (
                did, len(copies(XD, did)), len(copies(PD, did))))
            continue
        for c, (xs, ps) in enumerate(pairs):
            k = idx[id(ps)]
            d = bytearray(ps.data)
            for step in steps:
                if step == 'texcount':
                    plan, st = tex_plan(xs, ps)
                else:
                    plan, st = rec_plan(xs, ps, rules)
                if plan is None:
                    notes.append('DTP %d copy %d (section %d) %s: %s' % (did, c, k, step, st))
                    continue
                if st:
                    notes.append('DTP %d copy %d (section %d) %s: %d words set; %s' % (
                        did, c, k, step, len(plan), dict(sorted(st.items()))))
                for off, old, new, note in plan:
                    assert bytes(d[off:off + 4]) == old
                    d[off:off + 4] = new
                    changes[(k, off)] = (old, new, 'DTP %d copy %d %s' % (did, c, note), step)
            ps.data = bytes(d)
    return changes, notes


def xbox_drm(name):
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    raw, pk = raw_dlc(name)
    if raw is None:
        return None, None
    return DW.read(cdrm_decode(raw, 'be'), 'be'), pk.split('/')[-1]


def data_bases(D):
    p = 24 + 20 * len(D.sections) + len(D.names) + len(D.pad)
    out = []
    for s in D.sections:
        p += len(s.reloc)
        out.append(p)
        p += len(s.data)
    return out


def verify(orig_raw, new_raw, changes, XD, steps, rules):
    """proofs on the written file; returns list of lines (raises on a failed proof)"""
    D0 = DW.read(orig_raw, 'le')
    dec0 = DW.cdrm_decode(orig_raw, 'le')
    assert D0.write('le') == bytes(dec0), 'writer is not lossless for the input'
    D1 = DW.read(new_raw, 'le')
    dec1 = DW.cdrm_decode(new_raw, 'le')
    assert len(dec0) == len(dec1), 'raw size changed'
    assert len(D0.sections) == len(D1.sections)
    for a, b in zip(D0.sections, D1.sections):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, a.reloc, len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, b.reloc, len(b.data)), 'section header / reloc changed'
    assert (D0.names, D0.pad, D0.ver, D0.u0, D0.u1) == (D1.names, D1.pad, D1.ver, D1.u0, D1.u1)
    bases = data_bases(D0)
    # byte-exact: the raw DRM differs from the input exactly in the bytes the planned words change (section data
    # need not start 4-aligned in the file, so the comparison is per byte, then counted per planned word)
    planned_b = {bases[k] + off + j for (k, off), (old, new, _, _) in changes.items() for j in range(4) if old[j] != new[j]}
    diff_b = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
    assert diff_b == planned_b, 'byte diff %d bytes, planned %d (extra %s, missing %s)' % (
        len(diff_b), len(planned_b), sorted(diff_b - planned_b)[:5], sorted(planned_b - diff_b)[:5])
    diffw = {(k, off) for (k, off) in changes if any(bases[k] + off + j in diff_b for j in range(4))}
    planned = set(changes)
    assert diffw == planned
    again, notes = fix_drm(XD, DW.read(new_raw, 'le'), steps, rules)
    assert not again, 're-check still plans %d words' % len(again)
    nrel = sum(1 for s in D1.sections if s.reloc)
    return ['  proof: readback ok, raw DRM %d bytes, %d words / %d bytes differ = planned, 0 other bytes; %d sections, '
            'headers + %d relocation blobs identical; re-check plans 0 words' % (
                len(dec1), len(diffw), len(diff_b), len(D1.sections), nrel)]


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'):
                    yield os.path.join(p, n)
        else:
            yield p


def check(a):
    verbose = '-v' in a
    a = [x for x in a if x != '-v']
    steps = list(STEPS)
    outdir = None
    if '--steps' in a:
        k = a.index('--steps'); steps = a[k + 1].split(','); del a[k:k + 2]
        assert all(s in STEPS for s in steps), steps
    if '--out-dir' in a:
        k = a.index('--out-dir'); outdir = a[k + 1]; del a[k:k + 2]
    if '--log' in a:
        k = a.index('--log'); logf = open(a[k + 1], 'w', encoding='utf-8'); del a[k:k + 2]
        out0 = sys.stdout

        class Tee:
            def write(self, s):
                out0.write(s); logf.write(s)

            def flush(self):
                out0.flush(); logf.flush()
        sys.stdout = Tee()
    pack = 'pack11'
    if '--pack' in a:
        k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    os.environ.setdefault('TRUDLC_PACK_FIRST', pack)
    os.chdir(ROOT)
    rules = load_rules()
    print('rules: %d record offsets from %s; steps %s; Xbox pack first: %s' % (
        len(rules), RC.RULES, ','.join(steps), os.environ['TRUDLC_PACK_FIRST']))
    tot = collections.Counter()
    written = []
    for path in files(a):
        name = os.path.basename(path)
        orig = open(path, 'rb').read()
        PD = DW.read(orig, 'le')
        XD, pk = xbox_drm(name)
        if XD is None:
            print('%s: no Xbox source - skipped' % name)
            continue
        changes, notes = fix_drm(XD, PD, steps, rules)
        bystep = collections.Counter(v[3] for v in changes.values())
        tot['files'] += 1
        if changes:
            tot['changed_files'] += 1
        tot.update(bystep)
        if changes or verbose:
            print('%s (Xbox %s, md5 %s): %s' % (name, pk, hashlib.md5(orig).hexdigest(),
                                                ', '.join('%s %d' % kv for kv in sorted(bystep.items())) or 'nothing to set'))
            for n in notes:
                print('    ' + n)
        if verbose:
            for (k, off), (old, new, note, step) in sorted(changes.items()):
                print('      section %d +0x%x %s -> %s  %s' % (k, off, old.hex(), new.hex(), note))
        elif changes and 'texcount' in bystep:
            for (k, off), (old, new, note, step) in sorted(changes.items()):
                if step == 'texcount':
                    print('      section %d +0x%x %s -> %s  %s' % (k, off, old.hex(), new.hex(), note))
        if outdir and changes:
            os.makedirs(outdir, exist_ok=True)
            raw = PD.write('le')
            if orig[:4] == b'CDRM':
                raw = DW.cdrm_encode(raw, 'le')
            for line in verify(orig, raw, changes, XD, steps, rules):
                print(line)
            q = os.path.join(outdir, name)
            open(q, 'wb').write(raw)
            assert open(q, 'rb').read() == raw
            written.append((name, hashlib.md5(raw).hexdigest(), hashlib.sha256(raw).hexdigest()))
            print('  written %s md5 %s sha256 %s' % (q, written[-1][1], written[-1][2]))
    print('total %s' % dict(sorted(tot.items())))
    if outdir and written:
        tsv = os.path.join(outdir, '..', 'md5.tsv') if os.path.basename(os.path.normpath(outdir)) == 'mods' \
            else os.path.join(outdir, 'md5.tsv')
        old = {}
        if os.path.exists(tsv):
            for ln in open(tsv, encoding='utf-8').read().splitlines()[1:]:
                if '\t' in ln:
                    m, p = ln.split('\t', 1); old[p] = m
        for n, m, _ in written:
            old[n] = m
        open(tsv, 'w', encoding='utf-8', newline='\n').write(
            'md5\tpath\n' + ''.join('%s\t%s\n' % (old[p], p) for p in sorted(old)))
        print('md5 list %s (%d files)' % (os.path.abspath(tsv), len(old)))


# ---------------------------------------------------------------- proof on base pairs
def proof(a):
    objlist = a[0] if a else os.path.join(ROOT, 'work', 'generic', 'lists', 'pc_objectlist.txt')
    os.chdir(ROOT)
    import pairs as P
    names = []
    for ln in open(objlist, encoding='latin-1').read().splitlines()[1:]:
        if ',' in ln:
            i, n = ln.split(',', 1)
            if int(i) <= 821:
                names.append(n.strip())
    get = lambda s: (s['type'], s['data'], s['reloc'], s['id'])
    tex = collections.Counter()
    stat = collections.defaultdict(collections.Counter)
    nobj = 0
    for n in names:
        try:
            xd_ = P.xbox_drm(n + '.drm'); pd_ = P.pc_drm(n + '.drm')
        except Exception:
            continue
        if not xd_ or not pd_:
            continue
        xs, ps = xd_[1], pd_[1]
        xi, pi = RC.objdata_dtps(xs, 'be', get), RC.objdata_dtps(ps, 'le', get)
        if not xi or not pi:
            continue
        xsec = [s for s in xs if s['type'] == 7 and s['id'] == xi[0]]
        psec = [s for s in ps if s['type'] == 7 and s['id'] == pi[0]]
        if not xsec or not psec:
            continue
        X, Pp = xsec[0], psec[0]
        # texture groups, each side walked with its own counts / pointer
        def groups(d, rel, e):
            f = '>' if e == 'be' else '<'
            if len(d) < 0x6c:
                return []
            g = struct.unpack_from(f + 'H', d, 0x64)[0]
            it = dict(R.parse(rel, e).internal) if rel else {}
            if not g or 0x68 not in it:
                return []
            p = it[0x68]; out = []
            for _ in range(g):
                if p + 4 > len(d):
                    return None
                c = struct.unpack_from(f + 'I', d, p)[0]
                if c > 4096 or p + 4 + 4 * c > len(d):
                    return None
                out.append((c, [struct.unpack_from(f + 'I', d, p + 4 + 4 * j)[0] for j in range(c)]))
                p += 4 + 4 * c
            return out
        gx, gp = groups(X['data'], X['reloc'], 'be'), groups(Pp['data'], Pp['reloc'], 'le')
        if gx is None or gp is None:
            tex['walk_failed'] += 1
        elif gx or gp:
            tex['objects_with_groups'] += 1
            if len(gx) != len(gp):
                tex['group_number_differs'] += 1
            for (cx, ix), (cp, ip) in zip(gx, gp):
                tex['groups'] += 1
                tex['count_equal_u32' if cx == cp else 'count_differs'] += 1
                for a1, b1 in zip(ix, ip):
                    tex['ids'] += 1
                    tex['id_equal_u32' if a1 == b1 else 'id_differs'] += 1
        # record classes (as objdata_rec_classes.calibrate, in memory)
        xr, xsl = RC.records(X['data'], 'be', X['reloc'])
        pr, psl = RC.records(Pp['data'], 'le', Pp['reloc'])
        if not xr or not pr or len(xr) != len(pr):
            continue
        nobj += 1
        for bx, bp in zip(xr, pr):
            for o in range(0, REC - 3, 4):
                if (bx + o) in xsl or (bp + o) in psl:
                    stat[o]['ptr'] += 1
                    continue
                xb, pb = X['data'][bx + o:bx + o + 4], Pp['data'][bp + o:bp + o + 4]
                fit = [k for k, p in PERMS.items() if perm(xb, p) == pb]
                stat[o][fit[0] if len(fit) == 1 else ('amb' if fit else 'none')] += 1
    print('texture groups on the base pairs: %s' % dict(sorted(tex.items())))
    rules = {}
    for o in sorted(stat):
        c = stat[o]
        inf = {k: v for k, v in c.items() if k in PERMS}
        tot = sum(inf.values())
        best = max(inf, key=inf.get) if inf else None
        if best and tot >= RC.MIN_N and inf[best] == tot and c['ptr'] == 0:
            rules[o] = (best, tot, c['none'])
    cache = load_rules()
    print('record base objects paired: %d; ruled offsets recomputed %d, cache %d, identical: %s' % (
        nobj, len(rules), len(cache), rules == cache))
    for o in sorted(rules):
        cls, n, none = rules[o]
        print('  +0x%03x %-8s informative %5d contradicting 0  (no byte class fits: %d)' % (o, cls, n, none))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'proof':
        proof(a[1:])
    elif a[0] == 'check':
        check(a[1:])
    elif a[0] == 'xbox':
        # xbox NAME.drm OUT.drm [--pack pack11]: the decoded Xbox source the steps compare with (for other check tools)
        os.environ.setdefault('TRUDLC_PACK_FIRST', a[a.index('--pack') + 1] if '--pack' in a else 'pack11')
        out = os.path.abspath(a[2])
        os.chdir(ROOT)
        XD, pk = xbox_drm(a[1])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(XD.write('be'))
        print('%s (%s) -> %s' % (a[1], pk, out))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
