"""Chunkdoll piece records (0x14 bytes each) of the DLC chunkdoll objects: typed byte-order rule, base proof, gate and
fix (docs Befund-ChunkDoll-Absturz-0711.md section 4 / 7 no. 2; the same fault class as upstream's fix18 /
tools/analog_word_fix.py at knight_thrall_chunkdoll DTP 20951 +0x130 / +0x158).

Engine (PC tru.exe, same reads in the Xbox retail / TU exe; docs section 1 / 4):
  create chunkdoll tru+0x296f90 (retail 0x823769a0, TU 0x823766c0): D = [[object]+0xc8],
    D+0x18 s32 piece count N, D+0x1c ptr -> N records of 0x14 bytes
  spawn piece tru+0x296b90 (retail 0x823761d0, TU 0x82375ea0) reads per record:
    +0x00 u8  model index (-> birth tru+0x1bd270 and body create tru+0x97270)   +0x01 u8
    +0x02 s16 bone A   +0x04 s16 bone B   +0x06 s16   +0x08 f32 lerp A -> B   +0x0c ptr (relocated on both platforms: never touched)   +0x10 u32 flags (bit 0)
So the PC record is the Xbox record with each FIELD in little-endian order:
    word +0x0 = {u8, u8, s16}  -> PC bytes x0 x1 x3 x2       word +0x4 = {s16, s16} -> x1 x0 x3 x2
    word +0x8 / +0x10 = 32-bit                          -> x3 x2 x1 x0

Why the converter breaks it (mode `explain`): the new DLC 2 chunkdoll DTPs have no base twin of the same size
(other piece counts than viking_thrall_chunkdoll 14 / yeti_thrall_chunkdoll 13), so they take the generic route
'convert' (tools/dlc_generic.py -> generic_type0.convert_section0 with the learned type-7 table). The table picks a
class per word from the label key (pointer path + offset inside the region) and the coarse value shape of the Xbox
word (generic_type0.shape); for a record word +0x0 like `02 00 00 16` (model 2, bone 22: shape 'HH') several keys hold
'u16u16' (learned from other DTPs whose word at that place is a real u16 pair), so model / byte +1 are swapped:
`00 02 16 00` = model 0. Words with another shape or key happen to get the right class - hence only some records.

Rule = this module: every word of every piece record := the typed PC bytes above, but only where the PC word is
another byte order of the Xbox word (raw / u32 / u16u16 / u8u8u16 / u16u8u8); a PC word that is no byte order of the
Xbox word cannot be explained (UNEXPECTED: fix_drm raises SystemExit, the gate fails). Header words of D and the
relocated words are never touched. Chunkdoll objects are recognised by the DRM name (`chunkdoll` in the file name)
AND the structure (object id reference +0 -> DTP, pointer +0xc8 -> D, D+0x18 count 1..64, D+0x1c pointer to N
records inside the section; on the Xbox: byte +1 = 0, flags 0 / 1, lerp 0..1).

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 900 tools/chunkdoll_record_fix.py proof
        base-game Xbox / PC pairs (viking_thrall_chunkdoll, yeti_thrall_chunkdoll; Xbox TU / layer2 / layer1, PC
        patch / bigfile): every record word against the typed rule; exit 1 on any contradicting word or when a
        count differs from PROOF_EXPECT
  ../bin/pyt -t 900 tools/chunkdoll_record_fix.py explain NAME [--pack PACK]
        the type-7 table class (key, shape, class) the converter used for every record word of an Xbox DLC
        chunkdoll (NAME e.g. viking_thrall_chunkdoll_dlc2_.drm; loads work/generic/type7_table)
  ../bin/pyt -t 900 tools/chunkdoll_record_fix.py scan LIST_OR_DIR [--pack PACK] [--all] [--report R.json]
        chunkdoll DRMs of a folder / list file / single .drm (several joined with ','; later name wins); exit 1 when
        any record word is wrong or unexpected (the gate)
  ../bin/pyt -t 900 tools/chunkdoll_record_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the DRMs with wrong words to OUTDIR, proves each (only the planned bytes differ, headers /
        relocations identical, re-plan 0); md5.tsv + chunkdoll_record_fix.log.txt in OUTDIR's parent folder
Library (step `chunkrec` of tools/dlc_struct_fixes.py, see the integration plan in docs Befund-Datenfixes-0711.md):
  plan(XD, PD, rel), fix_drm(XD, raw, rel) -> (new raw or None, changes, info)
"""
import sys, os, struct, collections, hashlib, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

REC = 0x14
FIELDS = {0x0: ('u8u8s16', (0, 1, 3, 2)), 0x4: ('s16s16', (1, 0, 3, 2)), 0x8: ('f32', (3, 2, 1, 0)),
          0xc: ('u32', (3, 2, 1, 0)), 0x10: ('u32', (3, 2, 1, 0))}
ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}
BASE = ('viking_thrall_chunkdoll', 'yeti_thrall_chunkdoll')
# measured 2026-11-07 (tools/chunkdoll_record_fix.py proof): 2 pairs, 27 records, 108 words (+0xc is a pointer, relocated in every record); 0 contradicting
PROOF_EXPECT = {'pairs': 2, 'records': 27, 'words': 108, 'contradicting': 0}


def perm(w, p):
    return bytes(w[i] for i in p)


def wanted(xw, field):
    return perm(xw, FIELDS[field][1])


def order_of(xw, pw):
    """name of the first byte order of the Xbox word that gives the PC word, or None"""
    for n, p in ORDERS.items():
        if perm(xw, p) == pw: return n
    return None


# ---------------------------------------------------------------- structure
def _ptr(rel, si, off):
    for o, t in rel[si].internal:
        if o == off: return si, t
    for di, s, d in rel[si].external:
        if s == off: return di, d
    return None


def records(D, endian):
    """-> dict(obj=object id, dtp=DTP id, d=(section index, offset of D), rec=(section index, offset), n=count,
    relocated=set of record word offsets that carry a relocation) or None when the object is no chunkdoll shape"""
    e = '>' if endian == 'be' else '<'
    rel = [R.parse(bytes(s.reloc), endian) for s in D.sections]
    oi = next((i for i, s in enumerate(D.sections) if s.type == 11), None)
    if oi is None: return None
    ids = {o: t for t, o in rel[oi].idref}
    if 0 not in ids or len(D.sections[oi].data) < 4: return None
    dtp_id = struct.unpack_from(e + 'I', D.sections[oi].data, 0)[0]
    di = next((i for i, s in enumerate(D.sections) if s.type == ids[0] and s.id == dtp_id), None)
    if di is None: return None
    p = _ptr(rel, di, 0xc8)
    if p is None: return None
    si, so = p
    sd = D.sections[si].data
    if so + 0x20 > len(sd): return None
    n = struct.unpack_from(e + 'i', sd, so + 0x18)[0]
    q = _ptr(rel, si, so + 0x1c)
    if q is None or not 1 <= n <= 64: return None
    ri, ro = q
    if ro + n * REC > len(D.sections[ri].data): return None
    rs = {o: 'internal' for o, _ in rel[ri].internal}
    rs.update({s: 'external' for _, s, _ in rel[ri].external})
    rs.update({o: 'id type %d' % t for t, o in rel[ri].idref})
    relocated = {ro + k * REC + f: rs[ro + k * REC + f] for k in range(n) for f in FIELDS if ro + k * REC + f in rs}
    return dict(obj=D.sections[oi].id, dtp=dtp_id, d=(si, so), rec=(ri, ro), n=n, relocated=relocated,
                rec_id=(D.sections[ri].type, D.sections[ri].id))


def xbox_shape_ok(XD, r):
    """Xbox records look like piece records: byte +1 = 0, flags 0 / 1, lerp a float in 0..1"""
    d = XD.sections[r['rec'][0]].data
    for k in range(r['n']):
        b = r['rec'][1] + k * REC
        lerp = struct.unpack_from('>f', d, b + 8)[0]
        fl = struct.unpack_from('>I', d, b + 0x10)[0]
        if d[b + 1] != 0 or fl not in (0, 1) or not (math.isfinite(lerp) and 0.0 <= lerp <= 1.0): return False
    return True


def is_chunkdoll(rel):
    return 'chunkdoll' in os.path.basename(rel.replace('\\', '/')).lower()


def plan(XD, PD, rel='chunkdoll', base=False):
    """-> dict(rows=[(PC section index, section id, offset, record, field, Xbox word, PC word, wanted, status)],
    info...) status: ok / fix:<PC byte order> / UNEXPECTED; info['skip'] says why a DRM is not planned.
    base=True: a base-game pair (the PC renumbered the object / DTP ids): only offsets and count must agree"""
    res = dict(rows=[], skip=None, obj=None, dtp=None, n=0, relocated={})
    if not is_chunkdoll(rel): res['skip'] = 'no chunkdoll name'; return res
    rx, rp = records(XD, 'be'), records(PD, 'le')
    if rx is None or rp is None:
        res['skip'] = 'no chunkdoll structure (Xbox %s, PC %s)' % (rx is not None, rp is not None); return res
    res.update(obj=rp['obj'], dtp=rp['dtp'], n=rp['n'])
    kinds = collections.Counter()
    for o, kd in list(rp['relocated'].items()) + [(o, 'Xbox ' + kd) for o, kd in rx['relocated'].items()]:
        kinds['+0x%x %s' % ((o - rp['rec'][1]) % REC, kd)] += 1
    res['relocated'] = dict(kinds)
    lx = (rx['d'][1], rx['rec'][1], rx['n']) + (() if base else (rx['obj'], rx['dtp'], rx['rec_id']))
    lp = (rp['d'][1], rp['rec'][1], rp['n']) + (() if base else (rp['obj'], rp['dtp'], rp['rec_id']))
    if lx != lp:
        res['skip'] = 'layout differs: Xbox %s PC %s' % ((rx['obj'], rx['dtp'], rx['rec_id'], hex(rx['rec'][1]), rx['n']),
                                                        (rp['obj'], rp['dtp'], rp['rec_id'], hex(rp['rec'][1]), rp['n']))
        return res
    if not xbox_shape_ok(XD, rx): res['skip'] = 'Xbox records do not have the piece record shape'; return res
    xd = bytes(XD.sections[rx['rec'][0]].data); pd = bytes(PD.sections[rp['rec'][0]].data)
    for k in range(rp['n']):
        for f in FIELDS:
            o = rp['rec'][1] + k * REC + f
            if o in rp['relocated'] or o in rx['relocated']: continue
            xw, pw = xd[o:o + 4], pd[o:o + 4]
            want = wanted(xw, f)
            if pw == want: st = 'ok'
            else:
                od = order_of(xw, pw)
                st = 'fix:%s' % od if od else 'UNEXPECTED'
            res['rows'].append((rp['rec'][0], rp['rec_id'][1], o, k, f, xw, pw, want, st))
    return res


def fix_drm(XD, raw, rel='chunkdoll'):
    """-> (new raw or None, changes [(section index, offset, old, new, section id)], plan info); SystemExit on an
    UNEXPECTED word. The written bytes are proven (verify)."""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, rel)
    bad = [r for r in info['rows'] if r[8] == 'UNEXPECTED']
    if bad:
        raise SystemExit('chunkrec %s: %d UNEXPECTED word(s) (no byte order of the Xbox word): %s' % (rel, len(bad), ', '.join(
            'DTP %d +%#x Xbox %s PC %s' % (r[1], r[2], r[5].hex(), r[6].hex()) for r in bad[:10])))
    todo = [r for r in info['rows'] if r[8].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    for si, sid, o, k, f, xw, pw, want, st in todo:
        s = PD.sections[si]; b = bytearray(s.data)
        assert bytes(b[o:o + 4]) == pw
        b[o:o + 4] = want; s.data = bytes(b)
        changes.append((si, o, pw, want, sid))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, rel)
    return new, changes, info


def verify(raw, new, changes, XD, rel='chunkdoll'):
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
    again = [r for r in plan(XD, B, rel)['rows'] if r[8] != 'ok']
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


# ---------------------------------------------------------------- base proof
def load_named(name, order, endian):
    """(Drm, source) of a base-game DRM by name from the archives of locals.SRC, or (None, None)"""
    import locals as LC
    from archive import Archive
    from names import crc
    n = name if name.endswith('.drm') else name + '.drm'
    for src in order:
        path, e, pre = LC.SRC[src]
        if e != endian or not os.path.exists(path): continue
        A = Archive(path, e)
        r = [x for x in A.find(crc(pre + '\\' + n)) if x['spec'] == 0xffffffff]
        if r: return DW.read(A.read(r[0]), e), src          # drm_write.read decodes CDRM itself
    return None, None


def proof(strict=True):
    tot = collections.Counter(); per = collections.defaultdict(collections.Counter); contra = []
    for nm in BASE:
        XD, xs = load_named(nm, ('tu', 'xbase2', 'xbase'), 'be')
        PD, ps = load_named(nm, ('pcpatch', 'pcbig'), 'le')
        if XD is None or PD is None:
            print('base %s: Xbox %s PC %s - missing' % (nm, xs, ps)); tot['missing'] += 1; continue
        info = plan(XD, PD, nm + '.drm', base=True)
        if info['skip']:
            print('base %s: %s' % (nm, info['skip'])); tot['skipped'] += 1; continue
        tot['pairs'] += 1; tot['records'] += info['n']
        for si, sid, o, k, f, xw, pw, want, st in info['rows']:
            tot['words'] += 1
            # informative: the wanted order gives another PC word than every other byte order of this Xbox word
            others = {perm(xw, p) for n, p in ORDERS.items() if p != FIELDS[f][1]}
            inf = want not in others
            per[FIELDS[f][0] + ' +0x%x' % f]['agree' + ('' if inf else ' (uninformative)') if st == 'ok' else 'CONTRADICTS'] += 1
            if st != 'ok': contra.append((nm, sid, o, k, f, xw.hex(), pw.hex(), want.hex()))
        print('base %s: Xbox %s / PC %s, PC object %d, PC DTP %d, %d records; relocated record words (left alone): %s' % (
            nm, xs, ps, info['obj'], info['dtp'], info['n'], info['relocated'] or '-'))
    for f, c in sorted(per.items()): print('  field %-14s %s' % (f, dict(c)))
    for c in contra: print('  CONTRADICTS %s DTP %d +%#x record #%d field +0x%x: Xbox %s PC %s rule %s' % c)
    got = {'pairs': tot['pairs'], 'records': tot['records'], 'words': tot['words'], 'contradicting': len(contra)}
    ok = got == PROOF_EXPECT
    print('rule typed piece record {u8,u8,s16 | s16,s16 | f32 | ptr | u32}: %s  %s (expected %s)' % (
        'PROVEN' if ok else 'FAILED', got, PROOF_EXPECT))
    return 0 if ok or not strict else 1


# ---------------------------------------------------------------- cause: the learned type-7 table
def explain(name, pack):
    import convert_dlc as CD, generic_type0 as G0, generic_learn as GL
    from drm import cdrm_decode, sections_with_data
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    raw, pk = CD.raw_dlc(name)
    if raw is None: print('%s: no Xbox source' % name); return 2
    xraw = cdrm_decode(raw, 'be')
    XD = DW.read(xraw, 'be')
    r = records(XD, 'be')
    if r is None: print('%s: no chunkdoll structure' % name); return 2
    secs = sections_with_data(xraw, 'be')[1]
    ri = r['rec'][0]
    labs = G0.labels(secs, 'be')
    T7 = G0.table7()
    keys = {w: (key, ck) for w, key, ck in GL.word_keys(len(secs[ri]['data']), labs[ri])}
    xd = bytes(XD.sections[ri].data)
    print('%s (%s): object %d DTP %d, %d records at section (%d, %d) +0x%x' % (
        name, pk, r['obj'], r['dtp'], r['n'], r['rec_id'][0], r['rec_id'][1], r['rec'][1]))
    cnt = collections.Counter()
    for k in range(r['n']):
        for f in FIELDS:
            o = r['rec'][1] + k * REC + f
            if o in r['relocated']: continue        # pointer (+0xc): convert_section0 byte-reverses it after the table
            xw = xd[o:o + 4]
            key, ck = keys[o]
            c, src = G0.lookup(T7, None, key, ck, xw)
            if c is None: c, src = ('raw' if GL.is_text(xw) and xw != xw[::-1] else 's32'), 'fallback'
            # class names of generic_learn.PERM: s32 = u32 swap, s16 = u16 pair, b2s16 = {u8,u8,u16}, s16b2, raw
            conv = G0.apply_word(xw, c, None) if c in GL.BASIC or c.startswith('K:') else None
            v = struct.unpack('>I', xw)[0]
            if v in G0.VMAP: conv = struct.pack('<I', G0.VMAP[v])
            want = wanted(xw, f)
            good = conv == want if conv is not None else None
            cnt[(FIELDS[f][0], c, src, G0.shape(xw), good)] += 1
            if f == 0 or good is False:
                print('  #%-2d +0x%-2x (DTP +0x%x) Xbox %s shape %-2s key %s -> class %-8s via %-12s -> %s %s' % (
                    k, f, o, xw.hex(), G0.shape(xw), (key[0][0], len(key[0][1]), key[1]), c, src,
                    conv.hex() if conv is not None else '?', 'ok' if good else ('WRONG (rule %s)' % want.hex() if good is False else '')))
    for kk, v in sorted(cnt.items(), key=str): print('  summary %s: %d' % (kk, v))
    return 0


# ---------------------------------------------------------------- files
def file_list(spec):
    import soundplex_sequence_fix as SQ
    return [p for p in SQ.file_list(spec) if is_chunkdoll(p)]


def check_file(path, pack=None):
    """-> (status, plan info or None, Xbox Drm or None): the Xbox copy (convert_dlc.raw_dlc, --pack first) whose
    chunkdoll object / DTP ids equal the PC file's"""
    import soundplex_sequence_fix as SQ
    PD = DW.read(open(path, 'rb').read(), 'le')
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None
    best = None
    for XD, pk in cands:
        info = plan(XD, PD, path)
        score = (info['skip'] is None, len(info['rows']))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    _, XD, pk, info = best
    return 'ok (%s)' % pk, info, XD


def scan(paths, show_all, pack=None):
    tot = collections.Counter(); lines = []; files = []
    for path in paths:
        st, info, XD = check_file(path, pack)
        tot['files'] += 1
        if info is None or info['skip']:
            tot['skipped'] += 1
            ln = '%s: %s%s' % (path, st, ('; ' + info['skip']) if info and info['skip'] else '')
            print(ln); lines.append(ln); continue
        bad = [r for r in info['rows'] if r[8] != 'ok']
        tot['records'] += info['n']; tot['words'] += len(info['rows'])
        tot['wrong'] += sum(1 for r in bad if r[8].startswith('fix:')); tot['unexpected'] += sum(1 for r in bad if r[8] == 'UNEXPECTED')
        tot['wrong_model'] += sum(1 for r in bad if r[4] == 0 and r[5][0] != r[6][0])
        if bad: files.append(path.replace('\\', '/'))
        ln = '%s: %s, object %d DTP %d, %d records, %d words, %d not ok' % (path, st, info['obj'], info['dtp'], info['n'],
                                                                         len(info['rows']), len(bad))
        print(ln); lines.append(ln)
        for r in (info['rows'] if show_all else bad):
            ln = '   DTP %d +%#06x record #%d field +0x%x (%s): Xbox %s PC %s rule %s %s%s' % (
                r[1], r[2], r[3], r[4], FIELDS[r[4]][0], r[5].hex(), r[6].hex(), r[7].hex(),
                'ok' if r[8] == 'ok' else ('UNEXPECTED (no byte order)' if r[8] == 'UNEXPECTED' else 'WRONG (PC = %s)' % r[8][4:]),
                (' - model PC %d, Xbox %d' % (r[6][0], r[5][0])) if r[4] == 0 and r[8] != 'ok' else '')
            print(ln); lines.append(ln)
    res = 'FAIL' if tot['wrong'] or tot['unexpected'] else 'ok'
    print('TOTAL %s' % dict(tot)); print('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, names, pack):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))          # log + md5.tsv next to mods\, never inside it
    log = open(os.path.join(top, 'chunkdoll_record_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in file_list(spec):
        name = os.path.basename(path)
        if names and name not in names: continue
        st, info, XD = check_file(path, pack)
        if info is None or info['skip'] or not any(r[8] != 'ok' for r in info['rows']): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw, path)
        if new is None: continue
        for k, q, pw, xw, sid in changes:
            line = '%s DTP %d (section %d) +%#06x: %s -> %s' % (name, sid, k, q, pw.hex(), xw.hex())
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        ndiff = verify(raw, open(dst, 'rb').read(), changes, XD, path)
        h = hashlib.md5(new).hexdigest(); sh = hashlib.sha256(new).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (md5 %s; all inside the planned words), headers + relocations ' \
               'identical, re-plan 0; new md5 %s sha256 %s' % (name, len(changes), ndiff, path, hashlib.md5(raw).hexdigest(), h, sh)
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s' % (h, name))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    show_all = '--all' in a
    a = [x for x in a if x != '--all']
    if a[0] == 'proof': return proof()
    if a[0] == 'explain' and len(a) >= 2: return explain(a[1], pack)
    if a[0] == 'scan' and len(a) >= 2:
        r, tot, files, lines = scan(file_list(a[1]), show_all, pack)
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(result=r, spec=a[1], pack=pack, totals=tot, files=files, lines=lines),
                      open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if r != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]), pack); return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
