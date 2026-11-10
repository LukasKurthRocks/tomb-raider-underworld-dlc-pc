"""Player data block of converted player objects (object data `[inst+0x50]` = PC `[0xfad764]`, the target of the
player object DTP's relocated pointer +0xc8, 0x1034 bytes, air maximum s16 at +0xf8): every word in the byte order the
base-game player pairs prove, as a pipeline rule with gate and fix (K-5b 2026-11-10, docs Befund-Lock-Tuning-1011.md).

Why: doppelganger_casual DTP 20212 (the DLC 2 player object 857) has no same-size base twin, so the converter took the
generic `convert` route (fault class "learned type-7 table", docs/ENGINE.md section 2). The player block inside it has
the layout of the base player objects, but two words came out in the wrong byte order:
  +0x294  Xbox 08 00 05 00, PC 00 05 00 08: four u8 (PC readers `movzx byte [tuning+0x294 / +0x295 / +0x296]`
          0x72170f / 0x75e15f / 0x75e17f / 0x75e19f). Byte +0x294 is the LT lock-on time: lock update 0x7216b0 sets
          P+0x58c = byte +0x294 while LT (action 35) is held -> 0 on the PC = the lock never engages (no record 718, no
          combat ring; live aim.trace 2026-11-10 16:34 tune294 = 0)
  +0x25c  Xbox 00 01 00 10, PC 10 00 01 00: a u16 pair converted as one u32 (halves exchanged)
The five base pairs (lara, lara_casual, lara_bikini, lara_wetsuit_cold, lara_snow_light: Xbox layer2 / layer1, PC
bigfile; all with this block at DTP +0x28f80) give each word's PC byte order; their intersection decides (`proof`:
leave-one-out, 4800 decided words, 0 contradicting on 2026-11-10). Where the base words fit several orders that give different wanted words (+0x294 = 08 08 05 00
on lara is `same` and `s16b2`), the PC readers decide (READERS, code-proven field widths); a word without a decision
is left alone and listed. Pointer / id slots (relocations of any side) and words whose base pair is no byte order (ids
renumbered by the converter's id map, e.g. +0x94 / +0x98 breath sounds = step objid) are left alone.

Rule: a word is set only where the PC word is ANOTHER BYTE ORDER of the Xbox word and the wanted word is decided; a
PC word that is no byte order of the Xbox word is kept and counted ('other'). Every write is proven (decoded DRM
differs only in the planned bytes, headers / relocations identical, re-plan 0).

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 900 tools/player_block_fix.py proof
        leave-one-out over the base pairs: the order set of each pair must hold for the other (exit 1 on a
        contradiction); prints the words decided by READERS
  ../bin/pyt -t 900 tools/player_block_fix.py scan LIST_OR_DIR [--pack PACK] [--all]
        every DRM with a player block of the base length: words to fix (exit 1 when any = the gate)
  ../bin/pyt -t 900 tools/player_block_fix.py fix LIST_OR_DIR OUTDIR [--pack PACK]
        writes the fixed DRMs to OUTDIR (md5.tsv + player_block_fix.log.txt in OUTDIR's parent)
Library (step `playerblock` of tools/dlc_struct_fixes.py): plan(XD, PD), fix_drm(XD, raw, rel)
"""
import sys, os, struct, collections, hashlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

AIR = 4000
LEN = 0x1034                 # block length of every base player pair (first internal relocation target above it)
ORDERS = {'same': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16': (1, 0, 3, 2), 'b2s16': (0, 1, 3, 2), 's16b2': (1, 0, 2, 3)}
# code-proven field widths for words the base pairs leave ambiguous (offset: order, why)
READERS = {
    0x294: ('same', 'u8 +0x294 / +0x295 / +0x296: tru.exe movzx byte [[0xfad764]+0x294] 0x72170f (lock update 0x7216b0, '
                    'LT lock time -> P+0x58c) and 0x75e15f, +0x295 0x75e17f, +0x296 0x75e19f'),
}
# base player objects (Xbox layer2 / layer1, PC bigfile; lara_doppelganger is TU / DLC only, no base pair)
BASES = tuple((n, ('xbase2', 'xbase'), ('pcbig', 'pcpatch')) for n in (
    'lara.drm', 'lara_casual.drm', 'lara_bikini.drm', 'lara_wetsuit_cold.drm', 'lara_snow_light.drm'))
_BASE = None


def apply(w, order):
    return bytes(w[i] for i in ORDERS[order])


def orders_of(xw, pw):
    return {n for n in ORDERS if apply(xw, n) == pw}


def block(D, e):
    """(section index, block offset, slot offsets {pointer / id slots of the section}) or None"""
    f = '>' if e == 'be' else '<'
    for k, s in enumerate(D.sections):
        if s.type != 7 or not s.reloc or len(s.data) < 0xcc: continue
        r = R.parse(bytes(s.reloc), e)
        t = dict(r.internal).get(0xc8)
        if t is None or t + LEN > len(s.data): continue
        if struct.unpack_from(f + 'h', s.data, t + 0xf8)[0] != AIR: continue
        nxt = [b for _, b in r.internal if b > t]
        if (min(nxt) if nxt else len(s.data)) - t != LEN: continue
        return k, t, set(r.pointer_offsets()) | set(r.id_offsets())
    return None


def words(D, e):
    b = block(D, e)
    if b is None: return None
    k, t, slots = b
    d = D.sections[k].data
    return k, t, [bytes(d[t + o:t + o + 4]) for o in range(0, LEN, 4)], {o - t for o in slots if t <= o < t + LEN}


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')
BASE_XLIST, BASE_PLIST = os.path.join(LISTS, 'xbox_objectlist.txt'), os.path.join(LISTS, 'pc_objectlist.txt')
DLC_PLIST = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')
_LISTS = {}


def objlist(path):
    """{id: name} of an object list file (first line = count)"""
    if path not in _LISTS:
        d = {}
        for line in open(path, encoding='utf-8', errors='replace').read().splitlines()[1:]:
            if ',' in line:
                i, n = line.split(',', 1); d[int(i)] = n.strip().lower()
        _LISTS[path] = d
    return _LISTS[path]


def dlc_xlist(pack):
    return os.path.join(LISTS, 'dlc_%s_objectlist.txt' % (pack or 'pack11'))


def id_rule(o):
    """True when every base pair holds a type-7 section id at word o: Xbox u32 v names an Xbox DTP and the PC u32 is the
    PC id of its position partner (objdata_idword_fix.id_map), with at least one pair renumbered"""
    ren = False
    for name, xw, pw, slots, pmap in base_pairs():
        v = struct.unpack('>I', xw[o // 4])[0]; q = struct.unpack('<I', pw[o // 4])[0]
        if not v or pmap.get(v) != q: return False
        ren |= v != q
    return ren


def obj_rule(o):
    """half (0 / 2) of word o that every base pair holds as an object id (u16, Xbox list name = PC list name, at least
    one pair renumbered; the other half a plain u16), or None"""
    xl, pl = objlist(BASE_XLIST), objlist(BASE_PLIST)
    for h in (0, 2):
        ok, ren = True, False
        for name, xw, pw, slots, pmap in base_pairs():
            x, p = xw[o // 4], pw[o // 4]
            a = struct.unpack('>H', x[h:h + 2])[0]; b = struct.unpack('<H', p[h:h + 2])[0]
            g = 2 - h
            if not a or xl.get(a) is None or xl.get(a) != pl.get(b) or x[g:g + 2] != p[g:g + 2][::-1]:
                ok = False; break
            ren |= a != b
        if ok and ren: return h
    return None


def base_pairs():
    """[(name, Xbox words, PC words, slots, id map)] of the base player pairs, extracted once per process"""
    global _BASE
    if _BASE is None:
        import bigfile_extract as BE, io, contextlib
        work = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'statechart')
        os.makedirs(work, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix='playerblock_', dir=work)
        import atexit, shutil
        atexit.register(shutil.rmtree, tmp, True)
        _BASE = []
        import objdata_idword_fix as IW
        for name, xs, ps in BASES:
            got, drms = [], []
            for srcs, e in ((xs, 'be'), (ps, 'le')):
                for src in srcs:
                    out = os.path.join(tmp, '%s_%s' % (src, name))
                    try:
                        with contextlib.redirect_stdout(io.StringIO()):
                            BE.main([src, name, out])
                    except SystemExit:
                        pass
                    if os.path.exists(out):
                        D = DW.read(open(out, 'rb').read(), e)
                        got.append(words(D, e)); drms.append(D); break
                else:
                    got.append(None)
            if None in got or len(got) != 2: raise SystemExit('base pair %s not found / no player block' % name)
            (_, _, xw, xs_), (_, _, pw, ps_) = got
            _BASE.append((name, xw, pw, xs_ | ps_, IW.id_map(drms[0], drms[1])))
    return _BASE


def rule(o):
    """order set at word offset o over all base pairs; None = a pair is no byte order there (id / other data) or a slot"""
    S = set(ORDERS)
    for name, xw, pw, slots, pmap in base_pairs():
        if o in slots: return None
        s = orders_of(xw[o // 4], pw[o // 4])
        if not s: return None
        S &= s
    return S


def id_want(o, x, XD, PD, pack, cache):
    """(wanted PC bytes or None, kind, why) for an id word (id_rule / obj_rule), else None"""
    if id_rule(o):
        if 'pmap' not in cache:
            import objdata_idword_fix as IW
            cache['pmap'] = IW.id_map(XD, PD)
        v = struct.unpack('>I', x)[0]
        q = cache['pmap'].get(v)
        why = 'DTP id (base pairs: Xbox id -> PC id of the position partner); Xbox %d -> PC %s' % (v, q)
        return (struct.pack('<I', q) if q is not None else None), 'id', why
    h = obj_rule(o)
    if h is not None:
        a = struct.unpack('>H', x[h:h + 2])[0]
        n = objlist(dlc_xlist(pack)).get(a)
        ids = [i for i, m in objlist(DLC_PLIST).items() if m == n] if n else []
        why = 'object id u16 at +%d (base pairs: same name Xbox / PC list); Xbox %d %s -> PC %s' % (
            h, a, n, ids[0] if len(ids) == 1 else ids)
        if len(ids) != 1: return None, 'obj', why
        g = 2 - h
        w = bytearray(4); w[h:h + 2] = struct.pack('<H', ids[0]); w[g:g + 2] = x[g:g + 2][::-1]
        return bytes(w), 'obj', why
    return None


def plan(XD, PD, pack=None):
    """rows [(section index, DTP id, block offset, word offset, Xbox, PC, wanted or None, status, why)];
    status ok / fix:<order> / fix:id / fix:obj / other (PC is no byte order of the Xbox word) / ambig / base-other /
    unmapped (id word whose Xbox id has no PC partner) / slot / contra"""
    res = dict(rows=[], skip=None)
    cache = {}
    bx, bp = words(XD, 'be'), words(PD, 'le')
    if bx is None or bp is None:
        res['skip'] = 'no player block of 0x%x bytes (Xbox %s, PC %s)' % (LEN, bx is not None, bp is not None); return res
    kx, tx, xw, xslots = bx
    kp, tp, pw, pslots = bp
    if tx != tp: res['skip'] = 'block offset differs (Xbox +0x%x, PC +0x%x)' % (tx, tp); return res
    sid = PD.sections[kp].id
    for i in range(LEN // 4):
        o = 4 * i; x, p = xw[i], pw[i]
        if o in xslots or o in pslots:
            res['rows'].append((kp, sid, tp, o, x, p, None, 'slot', '')); continue
        S = rule(o)
        if S is None:
            iw = id_want(o, x, XD, PD, pack, cache)
            if iw is None:
                res['rows'].append((kp, sid, tp, o, x, p, None, 'base-other', '')); continue
            want, kind, why = iw
            if want is None: st = 'unmapped'
            elif p == want: st = 'ok'
            elif orders_of(x, p): st = 'fix:%s' % kind        # the untranslated Xbox id in some byte order
            else: st = 'other'
            res['rows'].append((kp, sid, tp, o, x, p, want, st, why)); continue
        if not S:
            res['rows'].append((kp, sid, tp, o, x, p, None, 'contra', 'base pairs disagree')); continue
        wants = {apply(x, n) for n in S}; why = '/'.join(sorted(S))
        if len(wants) > 1:
            if o in READERS and READERS[o][0] in S:
                wants = {apply(x, READERS[o][0])}; why = 'READERS %s' % READERS[o][1]
            else:
                res['rows'].append((kp, sid, tp, o, x, p, None, 'ok' if p in wants else 'ambig', why)); continue
        want = next(iter(wants))
        if p == want: st = 'ok'
        else:
            od = orders_of(x, p)
            st = 'fix:%s' % sorted(od)[0] if od else 'other'
        res['rows'].append((kp, sid, tp, o, x, p, want, st, why))
    return res


def fix_drm(XD, raw, rel='', pack=None):
    """-> (new raw or None, changes [(section index, DTP offset, old, new, DTP id)], info); pack: the Xbox source pack
    label (object list of the object id words; default pack11)"""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, pack)
    todo = [r for r in info['rows'] if r[7].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    for k, sid, t, o, x, p, want, st, why in todo:
        s = PD.sections[k]; b = bytearray(s.data); q = t + o
        assert bytes(b[q:q + 4]) == p
        b[q:q + 4] = want; s.data = bytes(b)
        changes.append((k, q, p, want, sid))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, pack)
    return new, changes, info


def verify(raw, new, changes, XD, pack=None):
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, sid in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B, pack)['rows'] if r[7].startswith('fix:')]
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


def proof():
    """leave-one-out: for every base pair, the orders of all OTHER pairs must turn its Xbox word into its PC word
    wherever they decide one word; plus each READERS order must be one of the pair orders at that offset"""
    P = base_pairs(); bad = 0; decided = 0
    for j, (name, xw, pw, slots, pmap) in enumerate(P):
        for i in range(LEN // 4):
            o = 4 * i
            if any(o in q[3] for q in P): continue
            S = set(ORDERS); ok = True
            for k, (n2, x2, p2, s2, m2) in enumerate(P):
                if k == j: continue
                s = orders_of(x2[i], p2[i])
                if not s: ok = False; break
                S &= s
            if not ok or not orders_of(xw[i], pw[i]): continue
            wants = {apply(xw[i], n) for n in S}
            if len(wants) != 1: continue
            decided += 1
            if pw[i] not in wants:
                bad += 1; print('CONTRA %s +0x%03x Xbox %s PC %s, others say %s' % (name, o, xw[i].hex(), pw[i].hex(), sorted(S)))
    for o, (od, why) in sorted(READERS.items()):
        S = rule(o)
        st = 'ok' if S and od in S else 'CONTRA'
        if st != 'ok': bad += 1
        print('READERS +0x%03x %s: base orders %s -> %s (%s)' % (o, od, sorted(S) if S else S, st, why))
    # id words: offsets where no byte order holds on every pair but every pair holds a renumbered DTP id / object id
    idw = [o for o in range(0, LEN, 4) if rule(o) is None and not any(o in q[3] for q in P) and id_rule(o)]
    obw = [(o, obj_rule(o)) for o in range(0, LEN, 4) if rule(o) is None and not any(o in q[3] for q in P)
           and not id_rule(o) and obj_rule(o) is not None]
    rest = [o for o in range(0, LEN, 4) if rule(o) is None and not any(o in q[3] for q in P) and not id_rule(o)
            and obj_rule(o) is None]
    print('id words (DTP id, every pair = id map of its position partner): %s' % ', '.join('+0x%x' % o for o in idw))
    print('object id words (u16 half, same name in the Xbox / PC object lists): %s' % ', '.join(
        '+0x%x half %d' % oh for oh in obw))
    print('words without a rule (base pair no byte order, no id): %s' % (', '.join(
        '+0x%x (%s)' % (o, ' '.join('%s->%s' % (q[1][o // 4].hex(), q[2][o // 4].hex()) for q in P)) for o in rest) or '-'))
    print('proof: %d base pairs (%s), %d leave-one-out decided words, %d contradicting, %d id words, %d object id '
          'words, %d without a rule -> %s' % (len(P), ', '.join(p[0] for p in P), decided, bad, len(idw), len(obw),
                                             len(rest), 'ok' if not bad else 'FAIL'))
    return bad


def scan(paths, show_all, pack):
    import soundplex_sequence_fix as SQ
    tot = collections.Counter(); out = []
    for path in paths:
        PD = DW.read(open(path, 'rb').read(), 'le')
        if words(PD, 'le') is None: continue
        cands = SQ.xbox_candidates(path, pack)
        tot['files'] += 1
        if not cands:
            tot['no_xbox'] += 1; print('%s: player block, no Xbox source' % path); continue
        XD, pk = cands[0]
        info = plan(XD, PD, pk.split('.')[0])
        if info['skip']:
            tot['skipped'] += 1; print('%s (%s): %s' % (path, pk, info['skip'])); continue
        c = collections.Counter(r[7].split(':')[0] for r in info['rows'])
        tot.update({'words': len(info['rows']), 'fix': c['fix'], 'other': c['other'], 'ambig': c['ambig']})
        if c['fix']: out.append(path)
        print('%s (%s): DTP %d block +0x%x: %s' % (path, pk, info['rows'][0][1], info['rows'][0][2],
                                                  ', '.join('%s %d' % kv for kv in sorted(c.items()))))
        for k, sid, t, o, x, p, want, st, why in info['rows']:
            if st in ('ok', 'slot') or (st == 'base-other' and not show_all): continue
            print('   +0x%03x  Xbox %s PC %s want %s  %-10s %s' % (o, x.hex(), p.hex(), want.hex() if want else '-', st, why))
    res = 'FAIL' if tot['fix'] else 'ok'
    print('TOTAL %s' % dict(tot)); print('scan: %s' % res)
    return res, out


def fix(spec, outdir, pack):
    import soundplex_sequence_fix as SQ
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))
    log = open(os.path.join(top, 'player_block_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in SQ.file_list(spec):
        raw = open(path, 'rb').read()
        PD = DW.read(raw, 'le')
        if words(PD, 'le') is None: continue
        cands = SQ.xbox_candidates(path, pack)
        if not cands: continue
        XD, pk = cands[0]
        new, changes, info = fix_drm(XD, raw, path, pk.split('.')[0])
        if new is None: continue
        name = os.path.basename(path)
        for k, q, p, w, sid in changes:
            why = next(r[8] for r in info['rows'] if r[2] + r[3] == q)
            line = '%s DTP %d +0x%x (block +0x%x): %s -> %s (%s)' % (name, sid, q, q - info['rows'][0][2], p.hex(), w.hex(), why)
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        nd = verify(raw, open(dst, 'rb').read(), changes, XD, pk.split('.')[0])
        h = hashlib.md5(new).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (md5 %s), headers + relocations identical, re-plan 0; new md5 %s' % (
            name, len(changes), nd, path, hashlib.md5(raw).hexdigest(), h)
        print(line); log.write(line + '\n'); md5s.append('%s\t%s' % (h, name))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def main(a):
    if not a: sys.exit(__doc__)
    pack = None
    if '--pack' in a: k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    show_all = '--all' in a; a = [x for x in a if x != '--all']
    if a[0] == 'proof': return 1 if proof() else 0
    import soundplex_sequence_fix as SQ
    if a[0] == 'scan' and len(a) >= 2:
        return 1 if scan(SQ.file_list(a[1]), show_all, pack)[0] != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], pack); return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
