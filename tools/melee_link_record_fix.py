"""Melee attack records of the DLC enemies that the game reaches ONLY through a follow-up (combo) link: typed byte
order per field, base-game proof, gate and fix (melee freeze 2026-11-07, docs Befund-Thrall-MeleeAttack-Freeze-0711.md,
docs Befund-Melee-Kombo-Datenfix-0711.md; read-only check: tools/melee_link_record_check.py).

Engine (PC tru.exe; enemy data / tune layout: docs Befund-Thrall-Felder-0611.md section 1):
  enemy data   = [DTP + 0xc8] (magic 0xdaf00018): byte +0x18 tune count, +0x1c tune array, +0x20 default tune;
                 tune +0x1c = parent tune; tune +0x80 .. +0xac = meleeAttack1..12 (pointer to a melee record)
  melee record = 0x21c bytes + s16 list (count u32 +0x218, entries from +0x21c)
  follow-up    = MeleeAttack update tru+0x265f10: after the strike (state data +0xa4 == 2, record +0x146 <= 0)
                 tru+0x25bc10 reads the LINK FIELDS record +0x1c0 / +0x1c4 (-> state Attack) and +0x1c8 (-> state
                 MeleeAttack again with the linked record, tru+0x23d5c0). The linked record's +0x78 {u16 type, u16
                 anim} is played by tru+0x2276c0 -> tru+0x226f10; with a wrong byte order (type 50 instead of 1) no
                 animation runs, no end message 0x15 arrives, record +0x136 = -1 has no time-out: the enemy freezes.
  Link fields checked in the data (Xbox, every base-game and DLC enemy): only +0x1c8 is ever set; +0x1c0 / +0x1c4 are
  0 everywhere. Other relocated record words: only +0x120 in the small spiders (a 0x28-byte block, no melee record).
  Other tune slots that point at a melee record: rangedAttack1 (+0x68) of viking_thrall_dlc2_ (a record that a
  meleeAttack slot also references). Pointers from other sections into the records: none.

Why the converter breaks them: a record that no tune slot references has no base twin at the same place, so its words
take the generic route (learned type-7 table) and land on u32 where the record has u16 pairs / bytes.

Rule (this module): every word of every reachable melee record (tune slot or follow-up link) gets, per field offset,
the byte order of the TYPE TABLE below - proven on the base-game Xbox / PC pairs (Eidos' own PC conversion; mode
`proof`: the table from the base TUNE records, 0 contradictions, and the base LINK-ONLY record of mayan_thrall typed
the same, 0 contradictions). Where the table leaves several orders that give different bytes (the base values do not
tell them apart), the orders of the tune records of the SAME file narrow it (the "profile", as in
melee_link_record_check.py); still several -> UNJUDGED when the PC word is one of them (left alone, listed, the gate
passes), AMBIGUOUS when it is another order (not changed, the gate fails). A word is only set where the
PC word is another byte order of the Xbox word; a PC word that is no byte order of the Xbox word is UNEXPECTED
(fix_drm raises SystemExit, the gate fails). Relocated words (pointers, id references) are never touched.

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 1800 tools/melee_link_record_fix.py proof [--report R.json]
        base-game pairs (Xbox TU / layer2 / layer1 against PC patch / bigfile): derive the type table, compare with
        TYPES; exit 1 on a contradiction, a changed table or other counts than PROOF_EXPECT
  ../bin/pyt -t 1800 tools/melee_link_record_fix.py scan LIST_OR_DIR [--pack PACK] [--all] [--report R.json]
        every DRM with enemy data in a folder / list file / single .drm (several joined with ','; later name wins):
        exit 1 when any reachable record word is wrong, unexpected or ambiguous (the gate)
  ../bin/pyt -t 1800 tools/melee_link_record_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the DRMs with wrong words to OUTDIR, proves each (only the planned bytes differ, headers / relocations
        identical, re-plan 0); md5.tsv + melee_link_record_fix.log.txt in OUTDIR's parent folder
  ../bin/pyt -t 1800 tools/melee_link_record_fix.py verify ORIGINAL.drm FIXED.drm [--pack PACK]
        the fixed file against the original: only planned words differ, re-plan 0 (exit 1 otherwise)
Library (step `meleelink` of tools/dlc_struct_fixes.py, integration plan in docs Befund-Melee-Kombo-Datenfix-0711.md):
  plan(XD, PD, rel), fix_drm(XD, raw, rel) -> (new raw or None, changes, info)
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

MAGIC = 0xdaf00018
MELEE = tuple(range(0x80, 0xb0, 4))            # tune meleeAttack1..12
LINKS = (0x1c0, 0x1c4, 0x1c8)                  # record follow-up links read by tru+0x25bc10
TUNE_LEN = 0x160                               # tune fields scanned for other slots pointing at a record
CORE = 0x21c
ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16p': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2),
          'u16u8u8': (1, 0, 2, 3)}
ALL = frozenset(ORDERS)
GOOD = ('ok', 'UNJUDGED')                      # UNJUDGED: the PC word is one of several orders nothing tells apart
BASE = ('merc_generator_run', 'merc', 'merc_deux', 'bat_enemy', 'tiger', 'naga_green', 'naga_red',
        'small_albino_spider', 'small_brown_spider', 'small_brown_spider_no_jump', 'panther_thrall', 'cat_panther',
        'poacher', 'poacher_long_range', 'mayan_thrall', 'viking_thrall', 'giant_albino_tarantula',
        'giant_albino_tarantula_blind', 'yeti_thrall', 'yeti_thrall_yggdrasil', 'shark_blueshark', 'shark_greenland')

# TYPE TABLE: record word offset -> byte orders that agree with EVERY base-game tune record word at that offset
# (Eidos' PC conversion). Generated and checked by mode `proof` (2026-11-07); a short code per set, see _CODES.
# Codes = bit mask over the sorted order names: 01 raw, 02 u16p, 04 u16u8u8, 08 u32, 10 u8u8u16 (1f = all: the base
# words never tell the orders apart there, e.g. always 0 or a pointer slot).
TYPES_TEXT = ('0:1f 4:1f 8:08 c:1f 10:08 14:1f 18:08 1c:02 20:02 24:02 28:02 2c:02 30:02 34:06 38:06 3c:17 40:08 44:08 '
              '48:08 4c:08 50:08 54:08 58:08 5c:02 60:17 64:17 68:17 6c:17 70:17 74:17 78:02 7c:02 80:02 84:17 88:02 '
              '8c:02 90:17 94:17 98:02 9c:17 a0:02 a4:02 a8:17 ac:08 b0:08 b4:1f b8:08 bc:08 c0:08 c4:1f c8:1f cc:08 '
              'd0:08 d4:08 d8:08 dc:02 e0:17 e4:02 e8:02 ec:17 f0:08 f4:08 f8:1f fc:08 100:08 104:08 108:1f 10c:1f '
              '110:08 114:08 118:08 11c:08 120:1f 124:11 128:08 12c:08 130:06 134:12 138:06 13c:12 140:1f 144:1f 148:02 '
              '14c:12 150:06 154:08 158:08 15c:1f 160:1f 164:1f 168:08 16c:1f 170:11 174:08 178:1f 17c:1f 180:08 184:08 '
              '188:1f 18c:08 190:08 194:08 198:08 19c:08 1a0:12 1a4:1f 1a8:08 1ac:02 1b0:02 1b4:1f 1b8:1f 1bc:06 1c0:1f '
              '1c4:1f 1c8:1f 1cc:1f 1d0:1f 1d4:17 1d8:12 1dc:02 1e0:05 1e4:08 1e8:08 1ec:08 1f0:01 1f4:08 1f8:1f 1fc:1f '
              '200:08 204:1f 208:08 20c:08 210:02 214:1f 218:08 21c:02 220:02 224:06')
# measured 2026-11-07 (mode proof): 22 base pairs (2 sharks without melee records), 93 tune records, 12 652 words,
# 0 contradicting, 0 value differences; the one base link-only record (mayan_thrall +0x3750, link +0x1c8 of +0x3970):
# 136 / 136 words agree with the table (61 of them decided by the table alone)
PROOF_EXPECT = {'pairs': 22, 'tune_records': 93, 'link_only_records': 1, 'tune_words': 12652, 'value_differs': 0,
                'contradicting': 0, 'link_words': 136, 'link_agree': 136, 'link_decided': 61, 'offsets': 138,
                'decided_offsets': 76}


def perm(w, p):
    return bytes(w[i] for i in p)


def orders_of(xw, pw):
    return frozenset(n for n, p in ORDERS.items() if perm(xw, p) == pw)


def any_order(xw, pw):
    return next((n for n, p in ORDERS.items() if perm(xw, p) == pw), None)


# ---------------------------------------------------------------- structure
def relocated(sec, endian):
    """offsets of every relocated word of a section (internal / external pointers, id references)"""
    r = R.parse(bytes(sec.reloc), endian)
    return set(o for o, _ in r.internal) | set(s for _, s, _ in r.external) | set(o for _, o in r.idref) | \
        set(o for _, o in r.idref_a)


def internal(sec, endian):
    return dict(R.parse(bytes(sec.reloc), endian).internal)


def enemy_dtps(D, endian):
    """[(section index, internal pointer dict, enemy data offset)] of the DTPs with enemy data"""
    e = '>' if endian == 'be' else '<'
    out = []
    for k, s in enumerate(D.sections):
        if s.type != 7 or not s.reloc: continue
        ip = internal(s, endian)
        r = ip.get(0xc8)
        if r is not None and r + 0x24 <= len(s.data) and struct.unpack_from(e + 'I', s.data, r)[0] == MAGIC:
            out.append((k, ip, r))
    return out


def rec_len(d, r, e='>'):
    if r + CORE > len(d): return 0
    n = struct.unpack_from(e + 'I', d, r + 0x218)[0]
    n = n if n < 64 else 0
    return CORE + ((2 * n + 3) // 4) * 4


def walk(d, ip, root):
    """Xbox DTP (big endian): -> (records {offset: set of origins}, tunes, notes). Records = tune meleeAttack slots,
    closed over the link fields; notes = other tune slots / record words that point at a record (reported only)."""
    tunes = []
    arr = ip.get(root + 0x1c)
    if arr is not None:
        for k in range(d[root + 0x18]):
            t = ip.get(arr + 4 * k)
            if t is not None: tunes.append(t)
    if ip.get(root + 0x20) is not None: tunes.append(ip[root + 0x20])
    seen, todo = [], list(tunes)
    while todo:
        t = todo.pop()
        if t in seen: continue
        seen.append(t)
        p = ip.get(t + 0x1c)
        if p is not None: todo.append(p)
    recs = {}
    for t in seen:
        for f in MELEE:
            r = ip.get(t + f)
            if r is not None: recs.setdefault(r, set()).add('tune +0x%x' % f)
    todo = list(recs)
    while todo:
        r = todo.pop()
        for f in LINKS:
            q = ip.get(r + f)
            if q is None: continue
            new = q not in recs
            recs.setdefault(q, set()).add('link +0x%x of +0x%x' % (f, r))
            if new: todo.append(q)
    notes = []
    for t in seen:
        for o in range(t, t + TUNE_LEN, 4):
            q = ip.get(o)
            if q in recs and not (o - t) in MELEE and o - t != 0x1c:
                notes.append('tune +0x%x slot +0x%x -> record +0x%x' % (t, o - t, q))
    for r in recs:
        for o in range(r, r + rec_len(d, r), 4):
            if o in ip and o - r not in LINKS:
                q = ip[o]
                notes.append('record +0x%x word +0x%x -> +0x%x (%s)' % (r, o - r, q, 'melee record' if q in recs else 'no melee record'))
    return recs, sorted(seen), sorted(notes)


# ---------------------------------------------------------------- type table
_CODES = {}                                    # code letter <-> frozenset of order names (built from TYPES_TEXT)


def _code_sets():
    names = sorted(ORDERS)
    out = {}
    for m in range(1, 1 << len(names)):
        s = frozenset(n for i, n in enumerate(names) if m >> i & 1)
        out[s] = '%02x' % m
    return out


def types_to_text(T):
    cs = _code_sets()
    return ' '.join('%x:%s' % (o, cs[T[o]]) for o in sorted(T))


def text_to_types(txt):
    rev = {v: k for k, v in _code_sets().items()}
    out = {}
    for tok in txt.split():
        o, c = tok.split(':')
        out[int(o, 16)] = rev[c]
    return out


def types():
    if not TYPES_TEXT: raise SystemExit('melee_link_record_fix: TYPES_TEXT is not pinned - run `proof` first')
    return text_to_types(TYPES_TEXT)


# ---------------------------------------------------------------- plan
def _pair_dtp(XD, PD, xk, root, base):
    """PC section index of the twin of Xbox enemy DTP xk: same id and size (DLC); base: same size + same root"""
    xs = XD.sections[xk]
    if not base:
        c = [k for k, s in enumerate(PD.sections) if s.type == 7 and s.id == xs.id]
        return c[0] if len(c) == 1 and len(PD.sections[c[0]].data) == len(xs.data) else None
    c = [k for k, s in enumerate(PD.sections) if s.type == 7 and len(s.data) == len(xs.data) and s.reloc
         and internal(s, 'le').get(0xc8) == root]
    return c[0] if len(c) == 1 else None


def plan(XD, PD, rel='enemy', T=None, base=False):
    """-> dict(rows=[(PC section index, DTP id, offset, record, field, Xbox word, PC word, wanted or None, status,
    kind, basis)], dtps=[...], skip=None). status: ok / fix:<PC order> / UNEXPECTED / AMBIGUOUS; kind tune / link;
    basis: table / profile (how the order was settled). T = type table (default: the pinned TYPES)."""
    T = types() if T is None else T
    res = dict(rows=[], dtps=[], skip=None, notes=[])
    found = enemy_dtps(XD, 'be')
    if not found: res['skip'] = 'no enemy data'; return res
    for xk, xip, root in found:
        pk = _pair_dtp(XD, PD, xk, root, base)
        xs = XD.sections[xk]
        if pk is None:
            res['dtps'].append(dict(dtp=xs.id, skip='no PC twin (id / size)')); continue
        ps = PD.sections[pk]
        xd, pd = bytes(xs.data), bytes(ps.data)
        rel_x, rel_p = relocated(xs, 'be'), relocated(ps, 'le')
        skipped = rel_x | rel_p
        recs, tunes, notes = walk(xd, xip, root)
        res['notes'] += ['DTP %d: %s' % (xs.id, n) for n in notes]
        tune_recs = {r for r, o in recs.items() if any(x.startswith('tune') for x in o)}
        # same-file profile: orders seen on the tune records (only words some order explains)
        prof = {}
        for r in tune_recs:
            for off in range(0, rec_len(xd, r), 4):
                o = r + off
                if o in skipped: continue
                od = orders_of(xd[o:o + 4], pd[o:o + 4])
                if od: prof[off] = prof.get(off, ALL) & od
        link_only = sorted(set(recs) - tune_recs)
        res['dtps'].append(dict(dtp=xs.id, section=pk, root=root, tunes=tunes, records=len(recs),
                                tune_records=len(tune_recs), link_only=link_only,
                                origins={'+0x%x' % r: sorted(v) for r, v in recs.items()}))
        for r in sorted(recs):
            if rec_len(pd, r, '<') != rec_len(xd, r):
                res['rows'].append((pk, xs.id, r + 0x218, r, 0x218, xd[r + 0x218:r + 0x21c], pd[r + 0x218:r + 0x21c],
                                    None, 'UNEXPECTED', 'tune' if r in tune_recs else 'link', 'list count'))
                continue
            for off in range(0, rec_len(xd, r), 4):
                o = r + off
                if o in skipped: continue
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                cand = T.get(off, ALL)
                wants = {perm(xw, ORDERS[n]) for n in cand}
                basis = 'table'
                if len(wants) > 1:
                    c2 = cand & prof.get(off, ALL)
                    w2 = {perm(xw, ORDERS[n]) for n in c2}
                    if len(w2) == 1: wants, basis = w2, 'profile'
                    elif c2: wants, basis = w2, 'ambiguous'
                    else: basis = 'ambiguous'
                want = next(iter(wants)) if len(wants) == 1 else None
                if want is not None and pw == want: st = 'ok'
                elif want is None:     # neither the base table nor the same file's tune records settle the order
                    st = 'UNJUDGED' if pw in wants else ('AMBIGUOUS' if any_order(xw, pw) else 'UNEXPECTED')
                else:
                    od = any_order(xw, pw)
                    st = 'fix:%s' % od if od else 'UNEXPECTED'
                res['rows'].append((pk, xs.id, o, r, off, xw, pw, want, st, 'tune' if r in tune_recs else 'link', basis))
    return res


def fix_drm(XD, raw, rel='enemy'):
    """-> (new raw or None, changes [(section index, offset, old, new, section id)], plan info); SystemExit on an
    UNEXPECTED / AMBIGUOUS word. The written bytes are proven (verify)."""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, rel)
    bad = [r for r in info['rows'] if r[8] in ('UNEXPECTED', 'AMBIGUOUS')]
    if bad:
        raise SystemExit('meleelink %s: %d UNEXPECTED / AMBIGUOUS word(s): %s' % (rel, len(bad), ', '.join(
            'DTP %d +%#x %s Xbox %s PC %s' % (r[1], r[2], r[8], r[5].hex(), r[6].hex()) for r in bad[:10])))
    todo = [r for r in info['rows'] if r[8].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    for row in todo:
        si, sid, o, rr, off, xw, pw, want = row[:8]
        s = PD.sections[si]; b = bytearray(s.data)
        assert bytes(b[o:o + 4]) == pw
        b[o:o + 4] = want; s.data = bytes(b)
        changes.append((si, o, pw, want, sid))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify_bytes(raw, new, changes, XD, rel)
    return new, changes, info


def verify_bytes(raw, new, changes, XD, rel='enemy'):
    """assert: only the planned bytes differ, headers / relocations / names identical, re-plan finds 0 words"""
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, sid in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    # the whole decoded file (header, names, every relocation table and section): same length, only those bytes differ
    da, db = DW.cdrm_decode(raw, 'le'), DW.cdrm_decode(new, 'le')
    assert len(da) == len(db) and sum(1 for i in range(len(da)) if da[i] != db[i]) == len(planned), 'decoded file differs elsewhere'
    again = [r for r in plan(XD, B, rel)['rows'] if r[8] not in GOOD]
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


# ---------------------------------------------------------------- base proof
def derive(pairs, log):
    """pairs: [(name, XD, PD)] -> (table from the tune records, stats, contradictions, link / orphan checks)"""
    T, ev = {}, collections.Counter()
    stats = collections.Counter(); contra = []; vdiff = []; per_link = []
    keep = []
    for nm, XD, PD in pairs:
        for xk, xip, root in enemy_dtps(XD, 'be'):
            pk = _pair_dtp(XD, PD, xk, root, True)
            xs = XD.sections[xk]
            if pk is None: log('base %s DTP %d: no PC twin by size / enemy data offset' % (nm, xs.id)); stats['no twin'] += 1; continue
            ps = PD.sections[pk]
            xd, pd = bytes(xs.data), bytes(ps.data)
            skipped = relocated(xs, 'be') | relocated(ps, 'le')
            recs, tunes, notes = walk(xd, xip, root)
            tune_recs = sorted(r for r, o in recs.items() if any(x.startswith('tune') for x in o))
            link_only = sorted(set(recs) - set(tune_recs))
            stats['pairs'] += 1; stats['tune records'] += len(tune_recs); stats['link-only records'] += len(link_only)
            log('base %s: Xbox DTP %d / PC DTP %d, enemy data +0x%x, %d tune(s), %d tune record(s), link only %s%s' % (
                nm, xs.id, ps.id, root, len(tunes), len(tune_recs), ['+0x%x' % r for r in link_only] or '-',
                ('; ' + '; '.join(notes)) if notes else ''))
            keep.append((nm, xd, pd, skipped, recs, tune_recs, link_only))
            for r in tune_recs:
                if rec_len(pd, r, '<') != rec_len(xd, r): vdiff.append((nm, r, 0x218, 'list count')); continue
                for off in range(0, rec_len(xd, r), 4):
                    o = r + off
                    if o in skipped: stats['relocated words'] += 1; continue
                    xw, pw = xd[o:o + 4], pd[o:o + 4]
                    od = orders_of(xw, pw)
                    stats['tune words'] += 1
                    if not od: vdiff.append((nm, r, off, '%s/%s' % (xw.hex(), pw.hex()))); continue
                    new = T.get(off, ALL) & od
                    if not new: contra.append((nm, r, off, xw.hex(), pw.hex(), sorted(T.get(off, ALL)), sorted(od)))
                    else: T[off] = new
                    if len({perm(xw, p) for p in ORDERS.values()}) > 2: ev[off] += 1
    # link-only (and orphan-free) check against the table
    lk = collections.Counter()
    for nm, xd, pd, skipped, recs, tune_recs, link_only in keep:
        for r in link_only:
            n_ok = n_bad = 0
            for off in range(0, rec_len(xd, r), 4):
                o = r + off
                if o in skipped: continue
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                od = orders_of(xw, pw)
                if not od: lk['value differs'] += 1; continue
                lk['words'] += 1
                if od & T.get(off, ALL): n_ok += 1; lk['agree'] += 1
                else:
                    n_bad += 1; lk['CONTRADICT'] += 1
                    contra.append((nm + ' LINK', r, off, xw.hex(), pw.hex(), sorted(T.get(off, ALL)), sorted(od)))
                if len({perm(xw, ORDERS[n]) for n in T.get(off, ALL)}) == 1 and len({perm(xw, p) for p in ORDERS.values()}) > 2:
                    lk['decided by the table'] += 1
            per_link.append('%s link-only record +0x%x (%s): %d word(s) agree with the table, %d contradict' % (
                nm, r, '; '.join(sorted(recs[r])), n_ok, n_bad))
    return T, ev, stats, contra, vdiff, per_link, lk


def proof(report=None, strict=True):
    import chunkdoll_record_fix as CR
    lines = []
    def log(s): print(s); lines.append(s)
    pairs = []
    for nm in BASE:
        XD, xs = CR.load_named(nm, ('tu', 'xbase2', 'xbase'), 'be')
        PD, ps = CR.load_named(nm, ('pcpatch', 'pcbig'), 'le')
        if XD is None or PD is None: log('base %s: Xbox %s PC %s - missing' % (nm, xs, ps)); continue
        log('base %s: Xbox %s, PC %s' % (nm, xs, ps))
        pairs.append((nm, XD, PD))
    T, ev, stats, contra, vdiff, per_link, lk = derive(pairs, log)
    for c in contra: log('  CONTRADICTS %s record +0x%x field +0x%x: Xbox %s PC %s table %s word %s' % c)
    for v in vdiff: log('  value differs (excluded, no byte order) %s record +0x%x field +0x%x %s' % v)
    for p in per_link: log('  ' + p)
    txt = types_to_text(T)
    cs = {v: k for k, v in _code_sets().items()}
    log('type table (record offset: orders; evidence = distinguishing tune words):')
    for o in sorted(T):
        log('  +0x%03x %-32s evidence %d' % (o, '/'.join(sorted(T[o])), ev[o]))
    got = dict(pairs=stats['pairs'], tune_records=stats['tune records'], link_only_records=stats['link-only records'],
               tune_words=stats['tune words'], value_differs=len(vdiff), contradicting=len(contra),
               link_words=lk['words'], link_agree=lk['agree'], link_decided=lk['decided by the table'],
               offsets=len(T), decided_offsets=sum(1 for o in T if len(T[o]) == 1))
    log('TYPES_TEXT = %r' % txt)
    same = TYPES_TEXT == txt
    ok = same and got == PROOF_EXPECT and not contra
    log('rule typed melee record (base tune records -> table; base link-only records against it): %s  %s (expected %s); '
        'table %s the pinned TYPES_TEXT' % ('PROVEN' if ok else 'FAILED', got, PROOF_EXPECT, 'equals' if same else 'DIFFERS from'))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(result='PROVEN' if ok else 'FAILED', counts=got, expect=PROOF_EXPECT, types=txt, lines=lines),
                  open(report, 'w', encoding='utf-8'), indent=1)
    return 0 if ok or not strict else 1


# ---------------------------------------------------------------- files
def has_enemy_data(path):
    try:
        PD = DW.read(open(path, 'rb').read(), 'le')
    except Exception:
        return None
    return PD if enemy_dtps(PD, 'le') else None


def file_list(spec):
    import soundplex_sequence_fix as SQ
    return SQ.file_list(spec)


def check_file(path, pack=None, PD=None):
    """-> (status, plan info or None, Xbox Drm or None)"""
    import soundplex_sequence_fix as SQ
    PD = PD or DW.read(open(path, 'rb').read(), 'le')
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None
    best = None
    for XD, pk in cands:
        info = plan(XD, PD, path)
        score = (info['skip'] is None, sum(1 for d in info['dtps'] if 'skip' not in d), -sum(1 for r in info['rows'] if r[8] not in GOOD))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    _, XD, pk, info = best
    return 'ok (%s)' % pk, info, XD


def scan(paths, show_all, pack=None):
    tot = collections.Counter(); lines = []; files = []
    def out(s): print(s); lines.append(s)
    for path in paths:
        PD = has_enemy_data(path)
        tot['files'] += 1
        if PD is None: continue
        tot['enemy files'] += 1
        st, info, XD = check_file(path, pack, PD)
        if info is None or info['skip']:
            tot['skipped'] += 1
            out('%s: %s%s' % (path, st, ('; ' + info['skip']) if info and info['skip'] else '')); continue
        bad = [r for r in info['rows'] if r[8] not in GOOD]
        unj = [r for r in info['rows'] if r[8] == 'UNJUDGED']
        for d in info['dtps']:
            if 'skip' in d: out('%s: DTP %d %s' % (path, d['dtp'], d['skip'])); tot['skipped dtps'] += 1; continue
            out('%s: %s, DTP %d, %d record(s) (%d tune, link only %s)' % (path, st, d['dtp'], d['records'], d['tune_records'],
                ', '.join('+0x%x' % r for r in d['link_only']) or '-'))
            tot['records'] += d['records']; tot['link-only records'] += len(d['link_only'])
        for n in info['notes']: out('   note: ' + n)
        tot['words'] += len(info['rows'])
        for k in ('tune', 'link'):
            tot['wrong (%s)' % k] += sum(1 for r in bad if r[8].startswith('fix:') and r[9] == k)
        tot['unexpected'] += sum(1 for r in bad if r[8] == 'UNEXPECTED')
        tot['ambiguous'] += sum(1 for r in bad if r[8] == 'AMBIGUOUS')
        tot['settled by the profile'] += sum(1 for r in info['rows'] if r[10] == 'profile')
        for k in ('tune', 'link'):
            tot['unjudged (%s)' % k] += sum(1 for r in unj if r[9] == k)
        if bad: files.append(path.replace('\\', '/'))
        out('   %d word(s), %d not ok, %d unjudged (no base evidence, the file\'s tune records disagree; left alone)' % (
            len(info['rows']), len(bad), len(unj)))
        for r in (info['rows'] if show_all else bad + unj):
            out('   DTP %d +%#06x %s record +0x%x field +0x%03x: Xbox %s PC %s want %s (%s) %s' % (
                r[1], r[2], r[9], r[3], r[4], r[5].hex(), r[6].hex(), r[7].hex() if r[7] else '?', r[10],
                'ok' if r[8] == 'ok' else ('WRONG (PC = %s)' % r[8][4:] if r[8].startswith('fix:') else r[8])))
    res = 'FAIL' if tot['wrong (tune)'] or tot['wrong (link)'] or tot['unexpected'] or tot['ambiguous'] else 'ok'
    out('TOTAL %s' % dict(tot)); out('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, names, pack):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))
    log = open(os.path.join(top, 'melee_link_record_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath\tmd5_before']
    for path in file_list(spec):
        name = os.path.basename(path)
        if names and name not in names: continue
        PD = has_enemy_data(path)
        if PD is None: continue
        st, info, XD = check_file(path, pack, PD)
        if info is None or info['skip'] or not any(r[8] not in GOOD for r in info['rows']): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw, path)
        if new is None: continue
        rows = {(r[0], r[2]): r for r in info['rows']}
        for k, q, pw, xw, sid in changes:
            r = rows[(k, q)]
            line = '%s DTP %d (section %d) +%#06x (%s record +0x%x field +0x%03x, %s): %s -> %s' % (
                name, sid, k, q, r[9], r[3], r[4], r[10], pw.hex(), xw.hex())
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        ndiff = verify_bytes(raw, open(dst, 'rb').read(), changes, XD, path)
        h = hashlib.md5(new).hexdigest(); h0 = hashlib.md5(raw).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (md5 %s; all inside the planned words), headers + relocations ' \
               'identical, re-plan 0; new md5 %s sha256 %s' % (name, len(changes), ndiff, path, h0, h, hashlib.sha256(new).hexdigest())
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s\t%s' % (h, name, h0))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def verify_pair(orig, fixed, pack):
    raw, new = open(orig, 'rb').read(), open(fixed, 'rb').read()
    st, info, XD = check_file(orig, pack)
    if XD is None: print('%s: %s' % (orig, st)); return 2
    changes = [(r[0], r[2], r[6], r[7], r[1]) for r in info['rows'] if r[8].startswith('fix:')]
    try:
        n = verify_bytes(raw, new, changes, XD, fixed)
    except AssertionError as e:
        print('verify %s: FAILED (%s)' % (fixed, e)); return 1
    print('verify %s: ok - %d planned word(s), %d byte(s) differ from %s, headers + relocations identical, re-plan 0' % (
        fixed, len(changes), n, orig))
    return 0


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    show_all = '--all' in a
    a = [x for x in a if x != '--all']
    if a[0] == 'proof': return proof(report)
    if a[0] == 'scan' and len(a) >= 2:
        r, tot, files, lines = scan(file_list(a[1]), show_all, pack)
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(result=r, spec=a[1], pack=pack, totals=tot, files=files, lines=lines),
                      open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if r != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]), pack); return 0
    if a[0] == 'verify' and len(a) == 3: return verify_pair(a[1], a[2], pack)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
