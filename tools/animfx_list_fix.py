"""Anim event lists (type-7 DTPs that start with a u32 0, tools/animfx.py format): check their record words against
the Xbox original by the layout proven on base pairs, and with --out repair them (read-only unless --out; test 48g
crash 2026-10-31 22:39, AV tru+0x14df8f `cmp byte [eax+4], 0` with eax = [0xc36f28 + 4 * 0x000e2000] when Lara (as
doppelganger_casual) reached a ledge).

Reader chain (tru.exe 2008 Steam build, disassembly with tools/pe_dis.py):
  anim player -> 0x5b26c0 walks the list (u32 0, records {u16 h, s16 frame, u8 type, 3 bytes, payload (h >> 12) * 4},
  end u16 0xffff) -> player callback 0x7181a0 msg 6 / 7 (case 0x7183c9): header nibble h & 0xf == 2 -> 0x716f30,
  == 1 -> 0x547b40, else -> 0x5b9c40 -> switch (h & 3) table 0x5b9f60: kind 0 -> 0x5b99c0(payload, instance, ...):
    payload byte 0 == 0: sound, *(u32 *)(payload + 4) = sound struct pointer (0x5935d0)
    payload byte 0 == 1: effect: +1 u8 flags, +2 s16, +4 s16 segment, +6 / +7 s8, **+8 u32 object id**, +0xc .. +0x18
                         floats -> 0x5953e0 -> 0x54df80(id): `[0xc36f28 + 4 * id]` (object table, no bound check),
                         then `cmp byte [obj + 4], 0` (the crash when the id is not an object id)

Key of a record word: (kind, payload words, word index, payload byte 0) as in tools/obj_eventlist_fix.py.

Modes (from the repository root):
  ../bin/pyt -t 900 tools/animfx_list_fix.py proof XBOX_REF.drm PC_REF.drm
        base pair, lists paired by position (same size and pointer layout): which byte order turns each Xbox word into
        the PC word, per key
  ../bin/pyt -t 900 tools/animfx_list_fix.py check XBOX_REF.drm PC_REF.drm XBOX.drm PC.drm [--out OUT.drm] [--v]
        lists of XBOX.drm paired with PC.drm by DTP id; expected PC bytes by the proven rules; differences; effect
        records whose PC object id is not an object id of the file / base; --out writes the repaired DRM
  ../bin/pyt -t 1700 tools/animfx_list_fix.py scan XBOX_REF.drm PC_REF.drm PC_MODS_DIR
        every DRM of a tree with an Xbox original in work/generic/dlc_drms.pkl: counts only
XBOX_REF == 'all': every base pair of work/generic/pairs.pkl (PC_REF ignored, e.g. 'x').
Kind 2 with one payload word is keyed by its u16 event type as well (the form of the other 2 bytes depends on it).
Words where the base classes give different bytes are kept (not proven); the effect object id word (no byte class,
the PC re-numbers base ids) is only set to the u32 of the Xbox id where the PC value is > 0xffff (u16 pair written).
Copies of one DTP id in a DRM are paired in order (k-th Xbox copy with the k-th PC copy).
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import obj_eventlist_fix as OE

CLASSES = OE.CLASSES
conv = OE.conv


def walk(d, e):
    """records [(off, h, size)] and the terminator offset of an anim event list, or None"""
    if len(d) < 8 or bytes(d[:4]) != b'\0\0\0\0': return None
    f = '>' if e == 'be' else '<'
    a = 4; recs = []
    while a + 4 <= len(d):
        h, fr = struct.unpack_from(f + 'Hh', d, a)
        if h == 0xffff: return (recs, a) if recs else None
        sz = (h >> 12) * 4 + 8
        if fr < 0 or not 1 <= (h >> 12) <= 8 or a + sz > len(d): return None
        recs.append((a, h, sz)); a += sz
    return None


def word_keys(d, e, rel):
    w = walk(d, e)
    if w is None: return None
    recs, end = w
    skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
    out = {}
    for a, h, sz in recs:
        for k in range(sz // 4):
            o = a + 4 * k
            kk = OE.key(d, e, a, h, k)
            if kk == (2, 1, 2, 0):          # kind 2, 1 payload word: u16 event type + 2 bytes whose form depends on it
                kk += (struct.unpack_from(('>' if e == 'be' else '<') + 'H', d, a + 8)[0],)
            out[o] = 'P' if o in skip else kk
    out[end] = 'T'
    return out, recs, end


def lists(D, e):
    return [s for s in D.sections if s.type == 7 and walk(s.data, e) is not None]


def proof_table(xref, pref):
    """XREF == 'all': every base pair of work/generic/pairs.pkl (PREF ignored)"""
    T = {}; st = collections.Counter()
    if xref == 'all':
        import pickle
        pairs = pickle.load(open(os.path.join(OE.W, 'pairs.pkl'), 'rb'))
        for nm, (X, P) in sorted(pairs.items()):
            if X is None or not isinstance(P, tuple): continue
            st['drms'] += 1
            _proof_one(OE._drm(X[1]), OE._drm(P[1]), T, st)
        del pairs
        return T, st
    XD = DW.read(open(xref, 'rb').read(), 'be'); PD = DW.read(open(pref, 'rb').read(), 'le')
    _proof_one(XD, PD, T, st)
    return T, st


def _proof_one(XD, PD, T, st):
    xs = [s for s in XD.sections if s.type == 7]; ps = [s for s in PD.sections if s.type == 7]
    st['x_type7'] = len(xs); st['p_type7'] = len(ps)
    # pair by position among the type-7 sections; fall back to the unique same-size / same-pointer-layout section
    for i, xl in enumerate(xs):
        if walk(xl.data, 'be') is None: continue
        st['x_lists'] += 1
        xr = R.parse(bytes(xl.reloc), 'be')
        cand = [p for p in ps if len(p.data) == len(xl.data)
                and sorted(R.parse(bytes(p.reloc), 'le').pointer_offsets()) == sorted(xr.pointer_offsets())
                and walk(p.data, 'le') is not None]
        pl = ps[i] if i < len(ps) and ps[i] in cand else (cand[0] if len(cand) == 1 else None)
        if pl is None: st['no_pc_twin'] += 1; continue
        wk = word_keys(xl.data, 'be', xr); pw = walk(pl.data, 'le')
        if [(a, h) for a, h, _ in wk[1]] != [(a, h) for a, h, _ in pw[0]]: st['framing_differs'] += 1; continue
        st['lists'] += 1; st['records'] += len(wk[1])
        for o, kk in wk[0].items():
            if kk == 'P': st['ptr_words'] += 1; continue
            x4 = bytes(xl.data[o:o + 4]); p4 = bytes(pl.data[o:o + 4])
            if kk == 'T': x4, p4 = x4[:2] + b'\0\0', p4[:2] + b'\0\0'
            cs = set(c for c in CLASSES if conv(x4, c) == p4)
            ent = T.setdefault(kk, [0, 0, set(CLASSES), collections.Counter(), []])
            ent[0] += 1; ent[1] += len(cs) < len(CLASSES); ent[2] &= cs; ent[3].update(cs or {'none'})
            if not cs and len(ent[4]) < 4: ent[4].append((xl.id, pl.id, o, x4.hex(), p4.hex()))
    return T, st


def show_table(T, st):
    print('base pair:', dict(st))
    for kk in sorted(T, key=str):
        n, nv, cs, cnt, ex = T[kk]
        print('  key %-22s words %5d non-invariant %5d classes %-34s -> %-7s %s %s' % (
            kk, n, nv, sorted(cs), OE.rule(T, kk), '' if cs else dict(cnt), ex if not cs else ''))


def objects_ids(D):
    return {s.id for s in D.sections if s.type == 11}


def check_lists(T, XD, PD):
    # the same DTP id can occur several times in one DRM (e.g. 22267 x3): pair the k-th Xbox copy with the k-th PC copy
    pd = collections.defaultdict(list)
    for s in PD.sections:
        if s.type == 7: pd[s.id].append(s)
    seen = collections.Counter()
    xd7 = collections.Counter(s.id for s in XD.sections if s.type == 7)
    res = []
    for xl in lists(XD, 'be'):
        k = seen[xl.id]; seen[xl.id] += 1
        cand = pd.get(xl.id, [])
        pl = cand[k] if len(cand) == xd7[xl.id] else (cand[0] if len(cand) == 1 else None)
        if pl is None or len(pl.data) != len(xl.data):
            res.append((xl, pl, None, [], collections.Counter())); continue
        xr = R.parse(bytes(xl.reloc), 'be')
        wk = word_keys(xl.data, 'be', xr)
        diffs = []; unk = collections.Counter()
        for o, kk in sorted(wk[0].items()):
            if kk == 'P': continue
            x4 = bytes(xl.data[o:o + 4]); p4 = bytes(pl.data[o:o + 4])
            c = OE.rule(T, kk)
            if c is None and kk == ID_KEY:
                # effect object id: the PC re-numbers base ids (no byte class fits on the base pair; the converter's
                # map handles those); an id the map does not know must stay the same number, i.e. a u32
                xv = struct.unpack('>I', x4)[0]; pv = struct.unpack('<I', p4)[0]
                if pv > 0xffff and xv <= 0xffff: diffs.append((o, kk, x4, p4, struct.pack('<I', xv)))
                continue
            if c is None:
                if x4 != x4[::-1] or conv(x4, 'u16') != x4: unk[kk] += 1
                continue
            want = conv(x4, c)
            if kk == 'T': want = want[:2] + p4[2:]
            elif kk in T and len(set(conv(x4, c2) for c2 in T[kk][2])) > 1:
                unk[('amb',) + kk] += 1; continue     # base classes disagree on this word's bytes: not proven, keep
            if p4 != want: diffs.append((o, kk, x4, p4, want))
        res.append((xl, pl, wk, diffs, unk))
    return res


ID_KEY = (0, 8, 4, 1)


def branch_report(xd, pd, recs):
    """kind-0 records (not skipped) whose payload byte 0 (0x5b99c0: 0 sound, 1 effect, 2 / 3 other) differs between
    the Xbox and the PC: [(off, payload words, xbox byte 0, pc byte 0, u32 the PC reads at payload + 8)]"""
    out = []
    for a, h, sz in recs:
        if h & 3 or h & 4 or xd[a + 8] == pd[a + 8]: continue
        rd = struct.unpack_from('<I', pd, a + 16)[0] if a + 20 <= len(pd) else None
        out.append((a, h >> 12, xd[a + 8], pd[a + 8], rd))
    return out


def effect_ids(d, e, recs):
    """[(record off, object id)] of kind-0 effect records (payload byte 0 == 1, >= 3 payload words)"""
    f = '>' if e == 'be' else '<'
    return [(a, struct.unpack_from(f + 'I', d, a + 16)[0]) for a, h, sz in recs
            if h & 3 == 0 and not h & 4 and sz >= 20 and d[a + 8] == 1]


def check(argv):
    out_path = None; verbose = '--v' in argv
    if verbose: argv.remove('--v')
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    T, st = proof_table(argv[0], argv[1])
    show_table(T, st)
    XD = DW.read(open(argv[2], 'rb').read(), 'be')
    PD = DW.read(open(argv[3], 'rb').read(), 'le')
    oids = objects_ids(PD) | (objects_ids(DW.read(open(argv[1], 'rb').read(), 'le')) if os.path.isfile(argv[1]) else set())
    res = check_lists(T, XD, PD)
    total = nl = nbad = 0; byk = collections.Counter(); how = collections.Counter(); badfx = []; branches = []
    for xl, pl, wk, diffs, unk in res:
        if wk is None:
            print('  DTP %d: no PC twin of the same size (PC %s) - not checked' % (xl.id, None if pl is None else hex(len(pl.data))))
            continue
        nl += 1
        pw = walk(pl.data, 'le')
        fx = effect_ids(pl.data, 'le', pw[0]) if pw else []
        xfx = dict(effect_ids(xl.data, 'be', wk[1]))
        for a, v in fx:
            if v not in oids and (v > 0xffff or xfx.get(a, 0) > 0xffff): badfx.append((xl.id, a, xfx.get(a), v))
        for b in branch_report(xl.data, pl.data, wk[1]):
            branches.append((xl.id,) + b)
        if diffs or unk or pw is None:
            nbad += bool(diffs)
            print('  DTP %d: %d records, %d words differ, PC walk %s, unknown keys %s' % (
                xl.id, len(wk[1]), len(diffs), 'ok' if pw and [(a, h) for a, h, _ in pw[0]] == [(a, h) for a, h, _ in wk[1]] else 'MIS-FRAMED', dict(unk)))
        for o, kk, x4, p4, want in diffs:
            byk[kk] += 1
            hw = [c for c in CLASSES if conv(x4, c) == p4] or ['other']
            how[hw[0]] += 1
            if verbose: print('     +0x%04x key %-18s Xbox %s PC %s (%s) want %s' % (o, kk, x4.hex(), p4.hex(), hw[0], want.hex()))
        total += len(diffs)
        if out_path and diffs:
            b = bytearray(pl.data)
            for o, kk, x4, p4, want in diffs: b[o:o + 4] = want
            pl.data = bytes(b)
    print('lists checked %d, lists with wrong words %d, wrong words %d' % (nl, nbad, total))
    print('  by key: %s' % dict(byk))
    print('  converter wrote: %s' % dict(how))
    print('  effect records whose PC object id is not an object (type 11) id of the file / PC base: %d' % len(badfx))
    for i, a, xv, v in badfx[:40]:
        print('     DTP %d +0x%04x Xbox id %s PC id 0x%08x' % (i, a, None if xv is None else '0x%08x' % xv, v))
    bc = collections.Counter((b[3], b[4]) for b in branches)
    print('  kind-0 records whose payload byte 0 (sound 0 / effect 1 / other) differs Xbox -> PC: %d %s' % (
        len(branches), {'%d->%d' % k: n for k, n in sorted(bc.items())}))
    crash = [b for b in branches if b[4] == 1 and b[2] < 3]
    print('  of them PC effect records with < 3 payload words (the reader takes the next record header as the object '
          'id): %d' % len(crash))
    for i, a, nw, xb, pb, rd in crash:
        print('     DTP %d +0x%04x words %d Xbox byte0 %d PC byte0 %d -> object id read 0x%08x%s' % (
            i, a, nw, xb, pb, rd or 0, '  <== crash value' if rd == 0x000e2000 else ''))
    if out_path:
        raw = PD.write('le')
        if open(argv[3], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        again = check_lists(T, XD, chk)
        nfx = 0
        for xl, pl, wk, diffs, unk in again:
            if wk is None: continue
            pw = walk(pl.data, 'le')
            nfx += sum(1 for a, v in (effect_ids(pl.data, "le", pw[0]) if pw else []) if v > 0xffff)
        print('written %s (%d bytes, read back ok; re-check: %d words differ, %d effect ids not an object id)' % (
            out_path, len(raw), sum(len(r[3]) for r in again), nfx))


def scan(argv):
    """scan XREF PREF PC_MODS_DIR: every DRM of the dir with an Xbox original in work/generic/dlc_drms.pkl (counts only)"""
    import pickle
    T, st = proof_table(argv[0], argv[1])
    print('base pair:', dict(st))
    C = pickle.load(open(os.path.join(OE.W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    xb = {}
    for kk, v in C.items(): xb.setdefault(base(kk[1]), v[1])
    tot = collections.Counter()
    for fn in sorted(os.listdir(argv[2])):
        if not fn.lower().endswith('.drm') or fn[:-4].lower() not in xb: continue
        XD = DW.Drm([DW.Section(s['type'], s['id'], s['data'], s['reloc']) for s in xb[fn[:-4].lower()] if s['data'] is not None])
        if not lists(XD, 'be'): continue
        PD = DW.read(open(os.path.join(argv[2], fn), 'rb').read(), 'le')
        c = collections.Counter()
        for xl, pl, wk, diffs, unk in check_lists(T, XD, PD):
            if wk is None: c['not_checked'] += 1; continue
            c['lists'] += 1; c['wrong_lists'] += bool(diffs); c['words'] += len(diffs)
            br = branch_report(xl.data, pl.data, wk[1])
            c['branch'] += len(br); c['crash_type'] += sum(1 for b in br if b[3] == 1 and b[1] < 3)
        tot['drms'] += 1; tot.update(c)
        if c['words'] or c['not_checked']:
            print('  %-40s lists %4d wrong %4d words %5d sound/effect branch changed %4d (effect with < 3 words %4d) not checked %d'
                  % (fn, c['lists'], c['wrong_lists'], c['words'], c['branch'], c['crash_type'], c['not_checked']))
    print('total', dict(tot))


def proof(argv):
    T, st = proof_table(argv[0], argv[1])
    show_table(T, st)


if __name__ == '__main__':
    a = sys.argv[1:]
    {'proof': proof, 'check': check, 'scan': scan}[a[0]](a[1:])
