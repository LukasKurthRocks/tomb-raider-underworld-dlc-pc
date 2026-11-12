"""SoundPlex Wave leaves (node type 2): the wave id at data +0 and the {u8 priority, u8, u16} word at data +4
(Q4 2026-11-11, docs Befund-Doppelgaenger-Wellen-1111.md in the workspace docs). Read-only except `fix`.

Engine (tru.exe 2008 Steam build, ENGINE.md 18.1): the leaf handler 0x591220 reads data {+0 u32 wave id, +4 u8 FMOD
priority byte, +5 u8, +6 u16}; the wave id is looked up among the loaded wave sections (section type 6) by id - there is
no relocation on that word, so a wrong id is a silent leaf, not a crash.

Fault (night package A1, docs Befund-Soundgruppen-77-78-1111.md): the learned type-7 table (generic_type0.table7)
gives the wave id word of these DLC trees the DTP-id class id32:7 (124 words) or no class (s32 fallback, 38 words;
work/q4_waves_1111/cause_probe.txt; none of the Xbox ids is a DTP id of the DRM, so not the dtpid sweep). In
doppelganger_casual the group-78 trees then point at ids(7, x) or x (Xbox 4510 -> 4872, 444 -> 454, 562 -> 572, 462 ->
462 ...), while the DRM's own wave sections carry ids(6, x) (DLC-new waves keep their Xbox id, base waves the base wave
map).

Rule: PC data +0 = ids(6, Xbox data +0) (tools/dlc_generic.DlcIds: base wave map work/generic/idmap.json type 6, DLC-new
ids work/generic/dlc_idmap.json); 0 / 0xffffffff stay. PC data +4 = the Xbox word with the u16 half swapped (u8 u8 u16).
Base proof (`proof`): every Wave leaf of the base Xbox / PC DTP pairs (same size + same internal relocations) whose Xbox id
is a mapped wave id holds the mapped id on PC (PROOF_EXPECT, 0 contradicting); +4 likewise u8u8u16.
Leaves: SoundPlex DTPs only (word 0 = root node {u32 1..13, ptr}, tools/dtp_audit.node0), every node reachable from the
root over the child pointers (tools/sound_groups.Sec.children logic, both byte orders), type 2, data words +0 / +4 no
pointer / id slot.

Step `waveid` of tools/dlc_struct_fixes.py (after playerblock, before the typed families): only words of Wave leaves of
DTPs paired by position with the same id, size and internal relocations (renumbered base DTPs = the PC game's own section,
left alone); +0 is written only when the new id is a wave section of the same DRM or a base PC wave id, and the old PC
word is a known wrong form (ids(7, x), the Xbox id unmapped, or a byte order of the Xbox word); +4 only when the old PC
word is a byte order of the Xbox word. Anything else is UNEXPECTED (reported; the check fails, nothing is guessed).

Embedded trees (E1-1, 2026-11-12): anim event-list DTPs hold SoundPlex trees whose root is NOT at DTP +0 (the kind-0
sound records point at them, event_roots). `proof --embedded` proves the same rule on the embedded trees of the base
pairs (4 leaves: the base trees reach their waves almost only through Indirect nodes); `scan`, tools/wave_ref_check.py
and the step (fix_drm, since E2: pipeline_check_1111c DLC 2 had 5 wrong embedded wave ids, goo cannon / goo converter)
walk them too; plan(embedded=False) / `scan --root0` = the old scope.

Modes (from the repository root):
  ../bin/pyt -t 1800 tools/soundplex_wave_id_fix.py proof [--embedded]
  ../bin/pyt -t 900 tools/soundplex_wave_id_fix.py scan DRM_OR_DIR[,..] [--pack PACK] [--report R.json] [--root0]
        every Wave leaf whose words differ from the rule (embedded trees included unless --root0); exit 1 when any is
        wrong or unexpected
  ../bin/pyt -t 900 tools/soundplex_wave_id_fix.py fix SRC.drm OUT.drm [--pack PACK]
        one DRM, only the planned words, proven (decoded bytes differ only there, headers / relocations identical,
        re-plan 0)
Library: wave_leaves(data, reloc, endian), plan(XD, PD, ids), fix_drm(XD, raw) -> (new raw or None, changes, info).
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

WAVE = 2
PERMS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2)}
NULLS = (0, 0xffffffff)
MAX_WAVE_ID = 0x10000
# base proof, measured 2026-11-11 (Q4, work/q4_waves_1111/proof_run2.txt): 750 base DTP pairs, 4718 Wave leaves, +0 =
# base wave map in all (4655 changed ids, 62 identity-mapped, 1 null), +4 raw = u8u8u16 in all (byte +6 = +7; the u32
# swap would differ in all 4718 -> u32 ruled out; u8u8u16 against raw is decided by the reader 0x591220: u16 at +6)
PROOF_EXPECT = {'pairs': 750, 'leaves': 4718, 'contra0': 0, 'contra4': 0, 'mapped_id': 4655, 'mapped_identity': 62,
                'plus4_raw_or_u8u8u16': 4718}
# the same rule on the trees EMBEDDED in base anim event-list DTPs (E1-1, 2026-11-12, `proof --embedded`; measured
# work/e2_pipeline_1211/proof_embedded.txt): 2398 Xbox base event lists, 1624 with sound roots (15061 kind-0 sound
# records, 14899 point at an Assign), 1623 paired - but their trees reach the waves almost only through Indirect nodes
# (DTPs with their own root at +0, walked above): only 4 Wave leaves sit in an embedded tree itself, all = the rule
PROOF_EXPECT_EMBEDDED = {'pairs': 4, 'leaves': 4, 'contra0': 0, 'contra4': 0, 'mapped_id': 4, 'mapped_identity': 0,
                         'plus4_raw_or_u8u8u16': 4}


# ---------------------------------------------------------------- tree walk (both byte orders)
def plex_nodes(d, reloc, e):
    """(nodes {node off: (type, data off)}, internal {slot: target}, pointer / id slots) - sound_groups.Sec, any order"""
    E = '<' if e == 'le' else '>'
    rel = R.parse(reloc, e) if isinstance(reloc, (bytes, bytearray)) else reloc
    it = dict(rel.internal)
    slots = set(rel.pointer_offsets()) | set(rel.id_offsets())
    nd = {}
    for o, tg in rel.internal:
        if o < 4 or o % 4 or (o - 4) in slots or tg % 4 or tg + 4 > len(d): continue
        t = struct.unpack_from(E + 'I', d, o - 4)[0]
        if t > 13: continue
        nd[o - 4] = (t, tg)
    return nd, it, slots


def _children(d, E, it, nd, off):
    t, tg = nd[off]
    out = []
    if t in (1, 2, 3): return out
    for o in range(tg, min(tg + 0x60, len(d)), 4):
        p = it.get(o)
        if p is None: continue
        if p in nd and p != off:
            out.append(p); continue
        for q in range(p, min(p + 0x100, len(d)), 4):
            p2 = it.get(q)
            if p2 is None:
                if q > p + 8 and q + 4 <= len(d) and struct.unpack_from(E + 'I', d, q)[0] > 13: break
                continue
            if p2 in nd and p2 != off: out.append(p2)
        if t == 4: break                                       # Assign: only +0 is a child pointer
    return out


def event_roots(d, e, nd, it):
    """roots of the SoundPlex trees EMBEDDED in an anim event-list DTP (E1-1, 2026-11-12; ENGINE.md 18.2): the list
    (tools/animfx.walk: u32 0 head, records {u16 h, s16 frame, u8 b4 + 3, payload}) holds kind-0 records whose payload
    {u8 0 = sound emitter, u8 flags, s16 segment, ptr root} points at the root node with payload +4 = record +12
    (internal relocation; 0x5b99c0 -> 0x5935d0). The DTP's root is not at +0, so the walk from +0 never sees them."""
    import animfx as AF
    w = AF.walk(d, '<' if e == 'le' else '>')
    if w is None: return []
    out = set()
    for a, h, fr, sz in w[0]:
        if h & 3 or sz < 16 or d[a + 8] != 0: continue
        p = it.get(a + 12)
        if p is not None and p in nd and 1 <= nd[p][0] <= 13: out.add(p)
    return sorted(out)


def wave_leaves(d, reloc, e, max_id=MAX_WAVE_ID, embedded=False, which=False):
    """data offsets of the Wave leaves reachable from the SoundPlex root at DTP +0 (none when word 0 is no root node);
    max_id None = no value filter (a checker of converted files must see byte-swapped ids too);
    embedded True = also the trees embedded in an anim event-list DTP (event_roots; only when +0 is no root);
    which True -> (leaves, 'root0' | 'embedded' | None)"""
    E = '<' if e == 'le' else '>'
    d = bytes(d)
    nd, it, slots = plex_nodes(d, reloc, e)
    roots, kind = [], None
    if len(d) >= 8 and 0 not in slots and 0 in nd and 1 <= nd[0][0] <= 13: roots, kind = [0], 'root0'
    elif embedded and len(d) >= 8:
        roots = event_roots(d, e, nd, it)
        if roots: kind = 'embedded'
    if not roots: return ([], None) if which else []
    seen = set(); stack = list(roots); out = []
    while stack:
        off = stack.pop()
        if off in seen: continue
        seen.add(off)
        t, tg = nd[off]
        if t == WAVE:
            # wave ids are small (base max 4263, DLC < 5000); a 'leaf' whose word is a float / large value is no Wave
            # record (6 base DTPs start with {2, ptr} over float data, e.g. Xbox 5623 / 4922 / 7358)
            if tg + 8 <= len(d) and tg not in slots and (tg + 4) not in slots:
                v = struct.unpack_from(E + 'I', d, tg)[0]
                if max_id is None or v in NULLS or v < max_id: out.append(tg)
            continue
        stack += _children(d, E, it, nd, off)
    return (sorted(set(out)), kind) if which else sorted(set(out))


def word_class(xw, pw):
    return frozenset(n for n, pm in PERMS.items() if bytes(xw[i] for i in pm) == pw)


# ---------------------------------------------------------------- base proof
def base_stats(embedded=False):
    """embedded False: the trees rooted at DTP +0 (PROOF_EXPECT); True: only the trees embedded in anim event-list DTPs
    (event_roots; PROOF_EXPECT_EMBEDDED, E1-1)"""
    import dtpid_sweep as DS
    st, ids = DS.ctx()
    b6 = ids.base[6]
    c0 = collections.Counter(); c4 = collections.Counter(); contra0 = []; contra4 = []; npairs = 0
    for (t, x), xb in st['xb_store'].items():
        if t != 7: continue
        p = ids.base[7].get(x); pc = st['pc_store'].get((7, p)) if p is not None else None
        if pc is None or len(pc['data']) != len(xb['data']): continue
        if dict(R.parse(pc['reloc'], 'le').internal) != dict(R.parse(xb['reloc'], 'be').internal): continue
        if embedded:
            lv, kind = wave_leaves(xb['data'], xb['reloc'], 'be', embedded=True, which=True)
            if kind != 'embedded': continue
        else:
            lv = wave_leaves(xb['data'], xb['reloc'], 'be')
        if not lv: continue
        npairs += 1
        xd, pd = xb['data'], pc['data']
        for tg in lv:
            xv = struct.unpack_from('>I', xd, tg)[0]; pv = struct.unpack_from('<I', pd, tg)[0]
            if xv in NULLS: k = 'null_kept' if pv == xv else 'null_changed'
            elif xv in b6: k = ('mapped_id' if b6[xv] != xv else 'mapped_identity') if pv == b6[xv] else 'contradicting'
            else: k = 'unmapped_kept' if pv == xv else 'unmapped_changed'
            c0[k] += 1
            if k in ('contradicting', 'null_changed', 'unmapped_changed'): contra0.append((x, p, tg, xv, pv))
            xw, pw = xd[tg + 4:tg + 8], pd[tg + 4:tg + 8]
            c = word_class(xw, pw)
            k4 = 'uninformative' if 'u8u8u16' in c and len(c) > 1 else ('u8u8u16' if 'u8u8u16' in c else 'contradicting')
            c4[k4] += 1; c4['classes ' + ('+'.join(sorted(c)) or 'none')] += 1
            if k4 == 'contradicting': contra4.append((x, p, tg, xw.hex(), pw.hex(), xv, pv, '+'.join(sorted(c))))
    return dict(pairs=npairs, leaves=sum(c0.values()), c0=c0, c4=c4, contra0=contra0, contra4=contra4)


def proof(strict=True, embedded=False):
    b = base_stats(embedded)
    expect = PROOF_EXPECT_EMBEDDED if embedded else PROOF_EXPECT
    if embedded: print('trees embedded in anim event-list DTPs (event_roots):')
    print('base DTP pairs with Wave leaves %d, leaves %d' % (b['pairs'], b['leaves']))
    print('data +0 (wave id):', dict(b['c0'].most_common()))
    print('data +4 (u8 prio, u8, u16):', dict(b['c4'].most_common()))
    for c in b['contra0'][:20]: print('  +0 CONTRADICTS Xbox DTP %d / PC DTP %d leaf data +%#x: Xbox %d PC %d' % c)
    for c in b['contra4'][:20]:
        print('  +4 CONTRADICTS Xbox DTP %d / PC DTP %d leaf data +%#x: Xbox %s PC %s (+0 Xbox %d PC %d; class %s)' % c)
    got = dict(pairs=b['pairs'], leaves=b['leaves'], contra0=len(b['contra0']), contra4=len(b['contra4']),
               mapped_id=b['c0'].get('mapped_id', 0), mapped_identity=b['c0'].get('mapped_identity', 0),
               plus4_raw_or_u8u8u16=b['c4'].get('classes raw+u8u8u16', 0))
    ok = got['contra0'] == 0 and got['contra4'] == 0 and got == expect
    print('rule +0 = ids(6, Xbox), +4 = u8u8u16: %s  %s (expected %s)' % ('PROVEN' if ok else 'FAILED', got, expect))
    return 0 if ok or not strict else 1


_PROVEN = None
def proven():
    """base proof once per process (quiet), trees at DTP +0 and embedded trees (E1-1) -> (ok, lines)"""
    global _PROVEN
    if _PROVEN is None:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = proof() or proof(embedded=True)
        _PROVEN = (rc == 0, buf.getvalue().splitlines())
    return _PROVEN


# ---------------------------------------------------------------- one DRM
_IDS = None
def dlc_ids():
    global _IDS
    if _IDS is None:
        import dlc_generic as DG
        _IDS = DG.DlcIds()
    return _IDS


def bswap(v):
    return struct.unpack('<I', struct.pack('>I', v))[0]


def u16p(v):
    b = struct.pack('>I', v)
    return struct.unpack('<I', b[1::-1] + b[:1:-1])[0]


def plan(XD, PD, ids=None, embedded=False):
    """XD / PD: drm_write.Drm (Xbox BE / PC LE) -> dict(rows=[(PC section index, DTP id, leaf data off, field, Xbox
    word bytes, PC word bytes, wanted bytes, class)], wavemap {Xbox wave id: PC wave id} of the file's own wave sections
    (paired by position), mismatch [(x, file id, ids(6, x))], base_mapped, layout, sections, emb {(PC section index,
    leaf data off)} of the leaves found only through embedded=True)
    class: ok | fix:<old form> | UNEXPECTED:<why>
    embedded False (the step waveid / fix_drm): trees rooted at DTP +0 only; True (scan, wave_ref_check): also the trees
    embedded in anim event-list DTPs (E1-1) - the gate sees them, the step does not write them"""
    import converter_faults_fix as CF
    ids = ids or dlc_ids()
    pairs = CF.pairs_by_position(XD, PD)
    wavemap = {x.id: p.id for k, x, p in pairs if x.type == 6 and p.type == 6}
    pc_waves = {s.id for s in PD.sections if s.type == 6}
    base_pc_waves = set(ids.base.get(6, {}).values())
    res = dict(rows=[], wavemap=wavemap, mismatch=[], base_mapped=0, layout=[], sections=0, emb=set(), emb_sections=0)
    for x, f in sorted(wavemap.items()):
        if ids(6, x) != f: res['mismatch'].append((x, f, ids(6, x)))
    for k, x, p in pairs:
        if x.type != 7: continue
        xd = bytes(x.data)
        lv, kind = wave_leaves(xd, bytes(x.reloc), 'be', embedded=embedded, which=True)
        if not lv: continue
        res['sections'] += 1
        if kind == 'embedded':
            res['emb_sections'] += 1; res['emb'] |= {(k, tg) for tg in lv}
        if x.id != p.id and x.id in ids.base.get(7, {}):
            res['base_mapped'] += 1; continue                 # renumbered base DTP: the PC game's own section
        pd = bytes(p.data)
        if len(pd) != len(xd) or dict(R.parse(bytes(p.reloc), 'le').internal) != dict(R.parse(bytes(x.reloc), 'be').internal):
            res['layout'].append(x.id); continue
        for tg in lv:
            xw, pw = xd[tg:tg + 4], pd[tg:tg + 4]
            xv = struct.unpack('>I', xw)[0]; pv = struct.unpack('<I', pw)[0]
            if xv in NULLS: want = xv
            else: want = wavemap.get(xv, ids(6, xv))
            ww = struct.pack('<I', want)
            if pv == want: cls = 'ok'
            elif xv not in NULLS and want not in pc_waves and want not in base_pc_waves:
                cls = 'UNEXPECTED:target %d is no wave of this DRM and no base PC wave' % want
            elif pv == ids(7, xv) and ids(7, xv) != xv: cls = 'fix:dtp_id'          # converted as a DTP id
            elif pv == xv: cls = 'fix:unmapped'
            elif pv == bswap(xv): cls = 'fix:raw'
            elif pv == u16p(xv): cls = 'fix:u16pair'
            else: cls = 'UNEXPECTED:PC word %d is no known form of Xbox %d' % (pv, xv)
            res['rows'].append((k, p.id, tg, 0, xw, pw, ww, cls))
            xw, pw = xd[tg + 4:tg + 8], pd[tg + 4:tg + 8]
            ww = bytes(xw[i] for i in PERMS['u8u8u16'])
            if pw == ww: cls = 'ok'
            else:
                c = word_class(xw, pw)
                cls = ('fix:' + '+'.join(sorted(c))) if c else 'UNEXPECTED:+4 PC %s is no byte order of Xbox %s' % (pw.hex(), xw.hex())
            res['rows'].append((k, p.id, tg, 4, xw, pw, ww, cls))
    return res


def fix_drm(XD, raw, ids=None, embedded=True):
    """-> (new raw or None, changes [(section index, offset, old, new, DTP id, class)], plan info). UNEXPECTED rows are
    left (reported in info, the check fails on them). The written bytes are proven: only the planned bytes differ,
    file / section headers and relocations identical, re-plan 0 fix rows.
    embedded True (since E2 2026-11-12): the Wave leaves of the trees embedded in anim event-list DTPs too - the same
    leaf reader 0x591220, the same rule (base: 4718 leaves at +0 and 4 embedded, 0 contradicting); pipeline_check_1111c
    DLC 2: 5 words (dlc2_uo_goo_cannon DTP 25322 / 25323, dlc2_uo_gooconverter DTP 25155), DLC 1: 0"""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, ids, embedded=embedded)
    todo = [r for r in info['rows'] if r[7].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    for k, sid, tg, f, xw, pw, ww, cls in todo:
        s = PD.sections[k]; b = bytearray(s.data); q = tg + f
        assert bytes(b[q:q + 4]) == pw
        b[q:q + 4] = ww; s.data = bytes(b)
        changes.append((k, q, pw, ww, sid, cls))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, ids, embedded)
    return new, changes, info


def verify(raw, new, changes, XD, ids=None, embedded=True):
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, sid, c in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B, ids, embedded=embedded)['rows'] if r[7].startswith('fix:')]
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


def xbox_of(path, pack=None):
    """Xbox Drm of a PC DRM path (soundplex_sequence_fix.xbox_candidates: --pack first, else the best-paired pack)"""
    import soundplex_sequence_fix as SQ
    import converter_faults_fix as CF
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return None, None
    PD = DW.read(open(path, 'rb').read(), 'le')
    best = max(cands, key=lambda c: sum(1 for k, x, p in CF.pairs_by_position(c[0], PD) if x.id == p.id and len(x.data) == len(p.data)))
    return best


# ---------------------------------------------------------------- modes
def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def scan(paths, pack=None, report=None, embedded=True):
    """embedded True (default since E1-1, 2026-11-12): the trees embedded in anim event-list DTPs are checked too
    (counted as emb_*; --root0 = the old scope, only trees rooted at DTP +0)"""
    import soundplex_sequence_fix as SQ
    tot = collections.Counter(); rep = []
    for path in SQ.file_list(paths):
        XD, pk = xbox_of(path, pack)
        tot['files'] += 1
        if XD is None: tot['no_xbox_source'] += 1; continue
        info = plan(XD, DW.read(open(path, 'rb').read(), 'le'), embedded=embedded)
        cl = collections.Counter(r[7].split(':')[0] if not r[7].startswith('fix:') else r[7] for r in info['rows'])
        bad = [r for r in info['rows'] if r[7] != 'ok']
        tot['leaves'] += sum(1 for r in info['rows'] if r[3] == 0)
        tot['emb_sections'] += info['emb_sections']
        tot['emb_leaves'] += sum(1 for r in info['rows'] if r[3] == 0 and (r[0], r[2]) in info['emb'])
        tot['emb_not_ok'] += sum(1 for r in bad if (r[0], r[2]) in info['emb'])
        for c, n in cl.items(): tot[c] += n
        if bad or info['mismatch'] or info['layout']:
            print('%s (Xbox %s): %d leaves, %s; layout differs %s; wave-map mismatch %s' % (
                path, pk, sum(1 for r in info['rows'] if r[3] == 0), dict(cl), info['layout'], info['mismatch'][:5]))
            for r in bad[:60]:
                print('   DTP %d leaf +%#x +%d: Xbox %s PC %s -> %s  %s%s' % (r[1], r[2], r[3], r[4].hex(), r[5].hex(), r[6].hex(),
                      r[7], ' (embedded)' if (r[0], r[2]) in info['emb'] else ''))
        rep.append(dict(file=path, pack=pk, classes=dict(cl), layout=info['layout'], mismatch=info['mismatch'],
                        emb_sections=info['emb_sections'],
                        rows=[(r[1], r[2], r[3], r[4].hex(), r[5].hex(), r[6].hex(), r[7], (r[0], r[2]) in info['emb']) for r in bad]))
    nbad = sum(n for c, n in tot.items() if c.startswith('fix:') or c == 'UNEXPECTED')
    print('scan: %s -> %s' % (dict(tot), 'FAIL (%d word(s) wrong or unexpected)' % nbad if nbad else 'ok'))
    if report:
        json.dump(dict(total=dict(tot), files=rep), open(report, 'w', encoding='utf-8'), indent=1)
    return 1 if nbad else 0


def fix_one(src, out, pack=None):
    XD, pk = xbox_of(src, pack)
    if XD is None: sys.exit('no Xbox source for %s' % src)
    raw = open(src, 'rb').read()
    new, changes, info = fix_drm(XD, raw)
    print('%s (Xbox %s, md5 %s): %d leaves, %d word(s) to change' % (src, pk, hashlib.md5(raw).hexdigest(),
          sum(1 for r in info['rows'] if r[3] == 0), len(changes)))
    for k, q, a, b, sid, cls in changes:
        print('   DTP %d +%#x %s -> %s  %s' % (sid, q, a.hex(), b.hex(), cls))
    left = [r for r in info['rows'] if r[7].startswith('UNEXPECTED')]
    for r in left: print('   LEFT DTP %d leaf +%#x +%d: %s' % (r[1], r[2], r[3], r[7]))
    if new is None: print('nothing written'); return 1 if left else 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(new); assert open(out, 'rb').read() == new
    print('proof: readback ok, only the planned bytes differ, headers + relocations identical, re-plan 0; written %s md5 %s'
          % (out, hashlib.md5(new).hexdigest()))
    return 1 if left else 0


def main(a):
    a = list(a)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    emb = '--embedded' in a; root0 = '--root0' in a
    a = [x for x in a if x not in ('--embedded', '--root0')]
    if a[:1] == ['proof']: return proof(embedded=emb)
    if a[:1] == ['scan'] and len(a) == 2: return scan(a[1], pack, report, embedded=not root0)
    if a[:1] == ['fix'] and len(a) == 3: return fix_one(a[1], a[2], pack)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
