"""Object event lists (the list the type-11 object header names at +4): check their byte order against the Xbox
original and with --out repair them (read-only unless --out; test 48c crash 2026-10-31, AV tru+0x193659 with
edi = 0x0009000b right after DoppelgangerInit).

Readers in tru.exe (2008 Steam build):
* 0x5ba480 (instance init) -> 0x5ba000(instance, object, ...): `cmp word [obj+0x6e], 0`, esi = [obj+4] (the type-11
  section's +4 = id reference to a DTP, resolved to the DTP start), records walked from the first byte:
    +0 u16 h   bits 0-1 kind, bit 2 skip, bits 4-9 id (0 = any), bits 12-15 payload words
    +4 u8      event type (compared with the caller's type: 0 at instance init, 0x2e, 0x0d, 0x0e, 0x30)
    +8 payload (h >> 12) * 4 bytes;  next record = rec + (h >> 12) * 4 + 8;  end at u16 h == 0xffff
  -> 0x5b9f70 switch(kind): 0 -> 0x5b99c0(payload): payload byte 0 == 0 -> 0x5935d0(out, *(u32*)(payload + 4), 0.0)
  which reads [ptr + 8] (the crash: ptr = 0x0009000b); 1 -> 0x547b40, 2 -> 0x5b69c0(.., byte [rec+6]), 3 -> 0x5b2820.
  Same record format as the anim event lists of tools/animfx.py (there the list starts with a u32 0; here it does
  not, so animfx.detect never matched these DTPs).

Modes (from the repository root):
  ../bin/pyt -t 300 tools/obj_eventlist_fix.py dump DRM ENDIAN [N]
  ../bin/pyt -t 300 tools/obj_eventlist_fix.py proof XBOX_REF.drm PC_REF.drm
        base pair, objects (type-11 sections) matched by order, records by position: which byte order turns each
        Xbox word into the PC word, per key (kind, payload words, word index[, payload byte 0])
  ../bin/pyt -t 300 tools/obj_eventlist_fix.py check XBOX_REF.drm PC_REF.drm XBOX.drm PC.drm [--out OUT.drm]
        expected PC bytes from the Xbox list by the proven rules; differences; PC walk before / after; --out writes
  ../bin/pyt -t 1800 tools/obj_eventlist_fix.py scan XBOX_REF.drm PC_REF.drm PC_MODS_DIR [--pack P]
        every converted object of a tree with an Xbox original in work/generic/dlc_drms.pkl: counts only
"""
import sys, os, struct, collections, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
CLASSES = ('raw', 'u32', 'u16', 'u8u8u16', 'u16u8u8')    # byte transforms Xbox -> PC of one 4-byte word


def conv(x4, c):
    if c == 'raw': return bytes(x4)
    if c == 'u32': return bytes(x4[::-1])
    if c == 'u16': return bytes(x4[1::-1] + x4[3:1:-1])
    if c == 'u8u8u16': return bytes(x4[0:2] + x4[3:1:-1])
    if c == 'u16u8u8': return bytes(x4[1::-1] + x4[2:4])
    raise ValueError(c)


def objects(D, e):
    """[(k, object section, event list DTP or None)] in section order"""
    f = '>' if e == 'be' else '<'
    dtp = {s.id: s for s in D.sections if s.type == 7}
    out = []
    for s in [x for x in D.sections if x.type == 11]:
        lst = None
        if len(s.data) >= 8:
            ids = R.parse(bytes(s.reloc), e).id_offsets()
            if ids.get(4) == 7:
                lst = dtp.get(struct.unpack_from(f + 'I', s.data, 4)[0])
        out.append((len(out), s, lst))
    return out


def walk(d, e, limit=100000):
    """records [(off, h, size)] and the terminator offset (None if the walk leaves the section)"""
    f = '>' if e == 'be' else '<'
    a = 0; recs = []
    while a + 2 <= len(d) and len(recs) < limit:
        h = struct.unpack_from(f + 'H', d, a)[0]
        if h == 0xffff: return recs, a
        sz = (h >> 12) * 4 + 8
        if a + sz > len(d): return recs, None
        recs.append((a, h, sz)); a += sz
    return recs, None


def key(d, e, a, h, w):
    """structural key of word w of the record at a"""
    k = (h & 3, h >> 12, w)
    if w >= 2: k += (d[a + 8],)          # payload byte 0 (kind 0: 0 = sound, pointer at payload + 4)
    return k


def word_keys(d, e, rel):
    """{word offset: key} for every record word of the list, 'T' for the terminator; pointer / id words -> 'P'"""
    recs, end = walk(d, e)
    if end is None: return None
    skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
    out = {}
    for a, h, sz in recs:
        for w in range(sz // 4):
            o = a + 4 * w
            out[o] = 'P' if o in skip else key(d, e, a, h, w)
    out[end] = 'T'
    return out, recs, end


def _drm(secs):
    return DW.Drm([DW.Section(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in secs])


def base_pairs(xref, pref):
    """[(Xbox Drm, PC Drm)]: the given pair, or with XREF == 'all' every base pair of work/generic/pairs.pkl"""
    if xref != 'all':
        return [(DW.read(open(xref, 'rb').read(), 'be'), DW.read(open(pref, 'rb').read(), 'le'))]
    pairs = pickle.load(open(os.path.join(W, 'pairs.pkl'), 'rb'))
    out = []
    for nm, (X, P) in sorted(pairs.items()):
        if X is None or not isinstance(P, tuple): continue
        if not any(s['type'] == 11 for s in X[1]): continue
        out.append((_drm(X[1]), _drm(P[1])))
    del pairs
    return out


def proof_table(xref, pref):
    """{key: [n words, n non-invariant, set of classes consistent with every word]} from the base pair(s)"""
    T = {}; st = collections.Counter()
    for XD, PD in base_pairs(xref, pref):
        st['drms'] += 1
        _proof_one(XD, PD, T, st)
    return T, st


def _proof_one(XD, PD, T, st):
    xo, po = objects(XD, 'be'), objects(PD, 'le')
    if len(xo) != len(po): st['object_count_differs'] += 1; return
    for (k, xs, xl), (_, ps, pl) in zip(xo, po):
        if xl is None or pl is None: st['no_list'] += 1; continue
        if len(xl.data) != len(pl.data): st['size_differs'] += 1; continue
        xr = R.parse(bytes(xl.reloc), 'be'); pr = R.parse(bytes(pl.reloc), 'le')
        wk = word_keys(xl.data, 'be', xr)
        pw = walk(pl.data, 'le')
        if wk is None or pw[1] is None: st['walk_fails'] += 1; continue
        if [(a, h) for a, h, _ in wk[1]] != [(a, h) for a, h, _ in pw[0]]: st['framing_differs'] += 1; continue
        st['lists'] += 1; st['records'] += len(wk[1])
        if sorted(xr.pointer_offsets()) != sorted(pr.pointer_offsets()): st['ptr_layout_differs'] += 1
        for o, kk in wk[0].items():
            if kk in ('P',): st['ptr_words'] += 1; continue
            x4 = bytes(xl.data[o:o + 4]); p4 = bytes(pl.data[o:o + 4])
            if kk == 'T': x4, p4 = x4[:2] + b'\0\0', p4[:2] + b'\0\0'
            cs = set(c for c in CLASSES if conv(x4, c) == p4)
            e = T.setdefault(kk, [0, 0, set(CLASSES), collections.Counter()])
            e[0] += 1; e[1] += len(cs) < len(CLASSES); e[2] &= cs; e[3].update(cs)
        # sound structs after the terminator: words holding the list DTP's own id -> PC: u32 of the PC DTP id
        for o in self_id_words(xl, xr, wk[2]):
            st['self_id_words'] += 1
            st['self_id_pc_u32_ok'] += struct.unpack_from('<I', pl.data, o)[0] == pl.id
    return T, st


def self_id_words(xl, xr, end):
    skip = set(xr.pointer_offsets()) | set(xr.id_offsets())
    return [o for o in range((end + 4 + 3) // 4 * 4, len(xl.data) // 4 * 4, 4)
            if o not in skip and struct.unpack_from('>I', xl.data, o)[0] == xl.id]


def choose(e):
    n, nv, cs = e[:3]
    for c in ('u16', 'u32', 'raw', 'u8u8u16', 'u16u8u8'):
        if c in cs and len(cs) <= 2 or cs == {c}: return c
    return None


def rule(T, kk):
    """class for a key: the base-pair class; header words (w 0 / 1) and the terminator are structural"""
    if kk == 'T': return 'u16'
    if kk[2] == 0: return 'u16'                      # {u16 h, s16 frame} (reader: u16 h; proven below)
    e = T.get(kk)
    if e is None:
        # unseen payload key: same kind / size / word index with any payload byte 0, if all agree
        alt = [v for k, v in T.items() if k != 'T' and k[:3] == kk[:3]]
        cs = set(CLASSES)
        for v in alt: cs &= v[2]
        return choose([1, 1, cs]) if alt else None
    return choose(e)


def show_table(T, st):
    print('base pair:', dict(st))
    for kk in sorted(T, key=str):
        n, nv, cs, cnt = T[kk]
        print('  key %-22s words %5d non-invariant %5d classes %-28s -> %s  %s' % (kk, n, nv, sorted(cs), rule(T, kk), '' if cs else dict(cnt)))


def dump(argv):
    D = DW.read(open(argv[0], 'rb').read(), argv[1])
    n = int(argv[2]) if len(argv) > 2 else 20
    for k, s, l in objects(D, argv[1]):
        if l is None: print('object %d: no list' % s.id); continue
        recs, end = walk(l.data, argv[1])
        print('object %d (+0x6e %s): list DTP %d size 0x%x, %d records, end %s' % (
            s.id, s.data[0x6e:0x70].hex() if len(s.data) >= 0x70 else '-', l.id, len(l.data), len(recs),
            None if end is None else hex(end)))
        for a, h, sz in recs[:n]:
            print('   +0x%04x h %04x kind %d skip %d id %2d words %d  %s' % (a, h, h & 3, h >> 2 & 1, h >> 4 & 0x3f,
                                                                       h >> 12, l.data[a:a + sz].hex(' ', 4)))


def proof(argv):
    T, st = proof_table(argv[0], argv[1])
    show_table(T, st)


def pc_walk_report(name, d, rel):
    """walk as the PC does: framing, kind-0 sound records (not skipped, payload byte 0 == 0) whose pointer word
    rec+12 has no relocation (the reader does not check the payload size: a 0-word record reads the next record)"""
    recs, end = walk(d, 'le')
    ptrs = set(rel.pointer_offsets())
    bad = [(a, h, d[a + 4], d[a + 12:a + 16][::-1].hex()) for a, h, sz in recs
           if h & 3 == 0 and not h & 4 and a + 16 <= len(d) and d[a + 8] == 0 and a + 12 not in ptrs]
    print('  PC walk %s: %d records, end %s, kind-0 sound records without a pointer at rec+12: %d %s' % (
        name, len(recs), None if end is None else '+0x%x' % end, len(bad),
        ['+0x%x h %04x type %d ptr 0x%s' % b for b in bad[:8]]))
    return recs, end, bad


def bad_sound(d, rel):
    recs, end = walk(d, 'le')
    ptrs = set(rel.pointer_offsets())
    return [a for a, h, sz in recs if h & 3 == 0 and not h & 4 and a + 16 <= len(d) and d[a + 8] == 0
            and a + 12 not in ptrs], recs, end


def check_lists(T, XD, PD, verbose=True):
    """[(object id, pc list section, [(off, key, xbox, pc, want)], unknown)]"""
    res = []
    for (k, xs, xl), (_, ps, pl) in zip(objects(XD, 'be'), objects(PD, 'le')):
        if xl is None or pl is None: continue
        if len(xl.data) != len(pl.data):
            print("  object %d list DTP %d: list size differs (Xbox 0x%x PC 0x%x) - not checked" % (ps.id, pl.id, len(xl.data), len(pl.data)))
            continue
        xr = R.parse(bytes(xl.reloc), 'be')
        wk = word_keys(xl.data, 'be', xr)
        if wk is None: print('  object %d: Xbox list does not walk' % ps.id); continue
        diffs = []; unk = collections.Counter()
        for o, kk in sorted(wk[0].items()):
            if kk == 'P': continue
            x4 = bytes(xl.data[o:o + 4]); p4 = bytes(pl.data[o:o + 4])
            c = rule(T, kk)
            if c is None:
                if x4 != x4[::-1] or conv(x4, 'u16') != x4: unk[kk] += 1
                continue
            want = conv(x4, c)
            if kk == 'T': want = want[:2] + p4[2:]           # terminator: only the u16 0xffff is read
            elif kk in T and len(set(conv(x4, c2) for c2 in T[kk][2])) > 1: unk[('amb',) + kk] += 1
            if p4 != want: diffs.append((o, kk, x4, p4, want))
        for o in self_id_words(xl, xr, wk[2]):
            x4 = bytes(xl.data[o:o + 4]); p4 = bytes(pl.data[o:o + 4]); want = struct.pack('<I', pl.id)
            if p4 != want: diffs.append((o, 'S', x4, p4, want))
        res.append((ps.id, xl, pl, wk, diffs, unk))
    return res


def check(argv):
    out_path = None
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    T, st = proof_table(argv[0], argv[1])
    show_table(T, st)
    XD = DW.read(open(argv[2], 'rb').read(), 'be')
    PD = DW.read(open(argv[3], 'rb').read(), 'le')
    res = check_lists(T, XD, PD)
    total = 0
    for oid, xl, pl, wk, diffs, unk in res:
        print('object %d: list DTP %d, %d records (Xbox walk), %d words differ from the proven layout, unknown / ambiguous keys %s'
              % (oid, pl.id, len(wk[1]), len(diffs), dict(unk)))
        byk = collections.Counter(('self id' if kk == 'S' else 'hdr' if kk == 'T' or kk[2] == 0 else 'w%d' % kk[2]) for o, kk, *_ in diffs)
        print('  by word: %s' % dict(byk))
        seen = collections.Counter()
        for o, kk, x4, p4, want in diffs:
            # how the converter wrote it (for the note), two examples per key
            how = [c for c in CLASSES if conv(x4, c) == p4] or ['other']
            seen[(kk, how[0])] += 1
            if seen[(kk, how[0])] <= 2:
                print('   +0x%04x key %-18s Xbox %s PC %s (%s) want %s' % (o, kk, x4.hex(), p4.hex(), how[0], want.hex()))
        print('  converter wrote: %s' % dict(collections.Counter(h for (k, h), n in seen.items() for _ in range(n))))
        pr = R.parse(bytes(pl.reloc), 'le')
        xp = sorted(R.parse(bytes(xl.reloc), 'be').pointer_offsets()); pp = sorted(pr.pointer_offsets())
        print('  pointer relocations: Xbox %d, PC %d, same offsets %s' % (len(xp), len(pp), xp == pp))
        # region after the terminator (sound structs the kind-0 records point to; tools/soundplex_* own them):
        # only reported - words that are neither a u32 swap of the Xbox word nor a pointer / id field
        skip = set(xp) | set(R.parse(bytes(xl.reloc), 'be').id_offsets())
        tail = [o for o in range((wk[2] + 4) // 4 * 4, len(xl.data) // 4 * 4, 4) if o not in skip
                and bytes(pl.data[o:o + 4]) != bytes(xl.data[o:o + 4])[::-1]]
        print('  after the terminator (+0x%x..+0x%x): %d words not a u32 swap %s' % (
            wk[2], len(xl.data), len(tail), ['+0x%x %s/%s' % (o, xl.data[o:o + 4].hex(), pl.data[o:o + 4].hex())
                                             for o in tail[:8]]))
        pc_walk_report('now', bytes(pl.data), pr)
        total += len(diffs)
        if out_path and diffs:
            b = bytearray(pl.data)
            for o, kk, x4, p4, want in diffs: b[o:o + 4] = want
            pl.data = bytes(b)
            pc_walk_report('fixed', pl.data, pr)
            fw = walk(pl.data, 'le')
            assert [(a, h) for a, h, _ in fw[0]] == [(a, struct.unpack_from('>H', xl.data, a)[0]) for a, _, _ in wk[1]]
    print('total: %d words differ' % total)
    if out_path:
        raw = PD.write('le')
        if open(argv[3], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        again = check_lists(T, XD, chk)
        print('written %s (%d bytes, read back ok; re-check: %d words differ)' % (
            out_path, len(raw), sum(len(r[4]) for r in again)))


def scan(argv):
    pack = None
    if '--pack' in argv: k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
    T, st = proof_table(argv[0], argv[1])
    print('base pair:', dict(st))
    mods = argv[2]
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    xb = {}
    for kk, v in C.items():
        if pack is None or kk[0] == pack: xb.setdefault(base(kk[1]), v[1])
    n = nl = nbad = nw = ncrash = 0
    for fn in sorted(os.listdir(mods)):
        if not fn.lower().endswith('.drm') or fn[:-4].lower() not in xb: continue
        PD = DW.read(open(os.path.join(mods, fn), 'rb').read(), 'le')
        if not any(s.type == 11 for s in PD.sections): continue
        xs = xb[fn[:-4].lower()]
        XD = DW.Drm([DW.Section(s['type'], s['id'], s['data'], s['reloc']) for s in xs if s['data'] is not None])
        n += 1
        for oid, xl, pl, wk, diffs, unk in check_lists(T, XD, PD):
            nl += 1
            pr = R.parse(bytes(pl.reloc), 'le')
            bad, recs, end = bad_sound(pl.data, pr)
            if diffs or bad or end is None or unk:
                nbad += bool(diffs); nw += len(diffs); ncrash += bool(bad)
                print('  %s object %d list DTP %d: %d records, %d words differ, PC walk %d records end %s, unrelocated '
                      'sound pointers %d, unknown / ambiguous %s' % (fn, oid, pl.id, len(wk[1]), len(diffs), len(recs),
                                                                    None if end is None else hex(end), len(bad), dict(unk)))
                if fn.lower() != 'doppelganger_casual.drm':
                    print('      %s' % ['+0x%x %s %s->%s want %s' % (o, kk, x4.hex(), p4.hex(), w.hex()) for o, kk, x4, p4, w in diffs[:8]])
    print('%s: %d converted objects with an Xbox original, %d event lists, %d wrong (%d words), %d with an '
          'unrelocated sound pointer on the PC walk' % (mods, n, nl, nbad, nw, ncrash))


if __name__ == '__main__':
    a = sys.argv[1:]
    {'dump': dump, 'proof': proof, 'check': check, 'scan': scan}[a[0]](a[1:])
