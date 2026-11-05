"""Converter fault families as fixed pipeline steps (2026-11-03). The crash dumps of tests 50d-50j uncovered six word
classes that the generic DTP converter writes in the wrong byte order (or not renumbered) in DLC data; each rule was
proven on the base pair x_lara / pc_lara (Xbox layer2 lara.drm / PC bigfile lara.drm, chart DTP 12647 / 850) by its
own tool (docs/WINDOWS_REBUILD.md finding 44). This tool applies them over a whole tree, in this order:

  objevent  tools/obj_eventlist_fix.py   object event lists (the DTP a type-11 object names at +4): record words by
            the base-pair rules (key (kind, payload words, word index[, payload byte 0]) -> u16 / u32 / raw / u8u8u16 /
            u16u8u8), self ids after the terminator = u32 of the PC list id (test 50j: 39 words in 13 lists). The
            kind-1 sub-0x32 id word is left to `idword` (its own reader proof).
  idword    tools/eventlist_idword_fix.py  object event lists, kind-1 records of sub 0x32: payload word 1 is one u32
            section id (reader tru+0x1486b2; tests 50d/50e: player events 0x85 / 0x87, test 50j: the thralls)
  animlist  tools/animlist_check.py      anim event lists (u32 0 head, tools/animfx.py walk): record words by the same
            base rules, kind-1 sub-0x32 word = u32 (tests 50h/50i: 717 words in 37 files)
  fxnode    tools/fxnode_id_fix.py       effect description nodes (kind-0 event targets) {u32 type, ptr data, u32 self
            id = the PC DTP id, u32 0}: the header words and the id word of type-1 nodes are u32 (tests 50e/50f: 16
            type-1 ids, doppelganger + goo machine fx; 2026-11-03 also nodes whose self id the converter left raw /
            swapped - the single tool only saw nodes it could detect on the PC side, which needs a correct self id)
  statevm   tools/statevm_check.py       state-program VM code words (opcode words and literals): one u32 each
            (tests 50d/50e heap crash: 5 words)
  chartid   tools/chart_idvalue_fix.py   state-chart activity entries of value types 3 / 5: a section id, u32,
            renumbered to the PC id (base-pair value for the same (id, type, Xbox value), else the PC id of the
            aligned DTP; tests 50f/50g: 14 values)

Sections are paired with their Xbox original BY POSITION (the converter keeps the section order; the two lists are
aligned by (type, size) with difflib, appended sections such as own fade libraries have no partner). Pairing by id is
wrong for base-derived DRMs (dlc_costume_*, lara_doppelganger: base DTPs carry renumbered PC ids that coincide with
other Xbox ids). A pair whose PC id is not the Xbox id is "base-mapped" (a renumbered base DTP the converter took from
the base game): rule differences there are reported (kept_base_mapped), never changed, never a failure. The Xbox source
of a DRM is convert_dlc.raw_dlc (TRUDLC_PACK_FIRST / TRUDLC_EXTRA_XBOX honoured, as every 2b step); a DRM without one
makes the run fail (its pack is missing from convert_dlc.PACKS).

Each step only sets a word when the Xbox word and the proven rule give a definite PC value and the PC word differs;
words the rule cannot explain are NOT changed - they are reported as "unexpected" and make the run fail (exit 1), so a
new pattern stops the pipeline instead of being guessed. Idempotent: a second run over the output changes 0 words.

Modes (from the repository root):
  ../bin/pyt -t 3600 tools/converter_faults_fix.py fix SRC_DIR [SRC_DIR ..] OUT_DIR [--steps a,b] [--pack P]
        [--names a.drm,..] [--report R.json]
        later SRC_DIRs win; every changed DRM is written to OUT_DIR (relative path kept, CDRM kept), read back and
        checked again (0 wrong words left, else exit 1). R.json: counts per step / file and every changed word.
  ../bin/pyt -t 3600 tools/converter_faults_fix.py check DIR [DIR ..] [--steps a,b] [--pack P] [--names ..] [--report R.json]
        read-only; exit 1 if any step finds a wrong or unexpected word
  ../bin/pyt -t 1800 tools/converter_faults_fix.py proof [XREF.drm PREF.drm]
        every rule on the base pair (default: extracted from the game archives into
        work/rebuild/converter_faults_ref/): the PC side must equal the rule's conversion of the Xbox side word for
        word (expected counts in PROOF_EXPECT); exit 1 otherwise
  ../bin/pyt -t 1800 tools/converter_faults_fix.py compare NEW_DIR REF_DIR [--before DIR] [--report R.json]
        [--changes FIX_REPORT.json ..]
        every DRM of REF_DIR against the same file of NEW_DIR, section by section and word by word; with --changes
        (this tool's fix report or dlc_fixes_build's fixes_report.json of the run that built NEW_DIR) each differing
        word is marked: set by a fault step or not, and every word a fault step set is compared with REF; --before
        (the same pipeline without the fault steps) splits the differences into removed / new / in both; --detail
        lists every differing section, --classify names the structure of each differing word from the Xbox original
        (anim list / object event list / effect node / VM code / state chart / markup / other; set --pack)
Library: run_tree(srcs, out, steps, names=None, check_only=False) -> result dict.
"""
import sys, os, json, struct, collections, shutil, tempfile, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R

W = os.path.join(HERE, '..', 'work')
REF_DIR = os.path.join(W, 'rebuild', 'converter_faults_ref')
STEPS = ('objevent', 'idword', 'animlist', 'fxnode', 'statevm', 'chartid')
CHART_X, CHART_P = 12647, 850          # Lara's state chart DTP in x_lara / pc_lara
SUB_ID = 0x32                          # kind-1 sub type whose payload word 1 is a u32 section id
# base-pair proof (x_lara / pc_lara), counts measured 2026-11-02 by the single tools (Befund-Felsrinne.md 50e-50j)
# (fxnode: the one pair whose node layout differs is the state chart 12647 / 850 itself - 549 808 / 550 112 bytes, a
# re-authored PC layout with node look-alikes - not a node DTP; chartid: 10 of 11 values by the DTP map, the 11th
# (id 1114 type 3, Xbox 0xd -> PC 0xc) is no DTP id and comes from the base table)
PROOF_EXPECT = {
    'statevm': {'sections': 218, 'words': 108908, 'wrong': 0},
    'fxnode': {'type1': 10680, 'header_words': 66501, 'wrong': 0, 'layout_differs': 1},
    'chartid': {'entries': 11, 'by_dtp_map': 10, 'wrong': 0},
    'animlist': {'ok': 46408, 'wrong': 0},
    'objevent': {'lists': 1, 'words': 494, 'wrong': 0},
    'idword': {'records': 0, 'wrong': 0},
}


# ---------------------------------------------------------------- helpers
def u16sw(x4):
    return bytes(x4[1::-1] + x4[3:1:-1])


def how(x4, p4, want):
    """how the converter wrote a wrong word (for the log)"""
    if p4 == want: return 'ok'
    if p4 == x4: return 'raw'
    if p4 == u16sw(x4): return 'u16'
    if p4 == x4[::-1]: return 'u32'
    return 'other'


_ALIGN = {}


def pairs_by_position(XD, PD):
    """[(index in PD, Xbox section, PC section)]: the converter keeps the section order, but drops / adds a few
    sections (e.g. Xbox-only GPU sections, own fade libraries appended); the two section lists are aligned by (type,
    size) (difflib, as tools/chart_idvalue_fix.id_map), and a replaced block of the same length and the same type
    sequence is paired in order (re-authored sizes of base-mapped DTPs). Cached per (XD, PD) pair."""
    key = (id(XD), id(PD))
    if key in _ALIGN and _ALIGN[key][0] is XD and _ALIGN[key][1] is PD: return _ALIGN[key][2]
    import difflib
    a = [(s.type, len(s.data)) for s in XD.sections]; b = [(s.type, len(s.data)) for s in PD.sections]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1 and
                              [t for t, _ in a[i1:i2]] == [t for t, _ in b[j1:j2]]):
            out += [(j1 + k, XD.sections[i1 + k], PD.sections[j1 + k]) for k in range(j2 - j1)]
    _ALIGN.clear(); _ALIGN[key] = (XD, PD, out)
    return out


def encode(PD, like):
    raw = PD.write('le')
    return DW.cdrm_encode(raw, 'le') if like[:4] == b'CDRM' else raw


def base_refs(xref=None, pref=None):
    """(x_lara, pc_lara) paths; extracted once from the game archives (tools/bigfile_extract.py)"""
    if xref: return xref, pref
    xl, pl = os.path.join(REF_DIR, 'x_lara.drm'), os.path.join(REF_DIR, 'pc_lara.drm')
    if not (os.path.exists(xl) and os.path.exists(pl)):
        import io, contextlib, bigfile_extract as BE
        os.makedirs(REF_DIR, exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            BE.main(['xbase2', 'lara.drm', xl]); BE.main(['pcbig', 'lara.drm', pl])
    return xl, pl


class Ctx:
    """shared inputs of one run (base-pair rule tables), built on first use"""
    def __init__(self, xref=None, pref=None):
        self.xref, self.pref = base_refs(xref, pref)
        self._T = self._base = None

    def oe_table(self):
        if self._T is None:
            import io, contextlib, obj_eventlist_fix as OE
            with contextlib.redirect_stdout(io.StringIO()):
                self._T = OE.proof_table(self.xref, self.pref)[0]
        return self._T

    def chart_base(self):
        """(id, type, Xbox value) -> {PC value} of the base pair's chart (chart_idvalue_fix --base)"""
        if self._base is None:
            import state_actlist_fix as SA
            BX = [s for s in DW.read(open(self.xref, 'rb').read(), 'be').sections if s.type == 7 and s.id == CHART_X][0]
            BP = [s for s in DW.read(open(self.pref, 'rb').read(), 'le').sections if s.type == 7 and s.id == CHART_P][0]
            self._base = base_chart_table(BX, BP)
        return self._base


def base_chart_table(BX, BP, types=(3, 5)):
    import state_actlist_fix as SA
    out = {}
    for tx, tp in zip(SA.records(BX, 'be'), SA.records(BP, 'le')):
        for i in range(tx[2][5]):
            eid, et = struct.unpack_from('>HH', BX.data, tx[3] + 8 * i)
            if et in types:
                out.setdefault((eid, et, struct.unpack_from('>I', BX.data, tx[3] + 8 * i + 4)[0]), set()).add(
                    struct.unpack_from('<I', BP.data, tp[3] + 8 * i + 4)[0])
    return out


class Result:
    """per step: counts, changed words, unexpected words"""
    def __init__(self):
        self.cnt = collections.defaultdict(collections.Counter)      # step -> Counter
        self.files = collections.defaultdict(collections.Counter)    # step -> file -> words set / wrong
        self.changes = []                                             # dicts
        self.unexpected = []                                          # strings

        self.kept = []                                                # rule differences in base-mapped sections
        self.xid = None; self.mapped = False                          # the section pair being checked

    def pair(self, x, p):
        """start a section pair. Base-mapped = the PC id is not the Xbox id: a base DTP that the converter renumbered
        and took from the base game (PC store / template / analog routes) - not a plain conversion of this Xbox
        section, so a rule difference there is reported, never 'fixed' and never a failure"""
        self.xid = x.id; self.mapped = x.id != p.id
        return self.mapped

    def change(self, step, rel, k, s, o, old, new, note=''):
        """a wrong word; returns True when it is to be set (False: base-mapped section, only reported)"""
        e = {'step': step, 'file': rel, 'index': k, 'type': s.type, 'id': s.id, 'xbox_id': self.xid, 'off': o,
             'old': bytes(old).hex(), 'new': bytes(new).hex(), 'note': note}
        if self.mapped:
            self.kept.append(e); self.cnt[step]['base-mapped words differing (kept)'] += 1
            return False
        self.changes.append(e); self.files[step][rel] += 1; self.cnt[step]['wrong'] += 1
        return True

    def odd(self, step, rel, text):
        if self.mapped:
            self.cnt[step]['base-mapped sections not matching (kept)'] += 1
            self.kept.append({'step': step, 'file': rel, 'xbox_id': self.xid, 'note': text}); return
        self.cnt[step]['unexpected'] += 1
        self.unexpected.append('%s %s: %s' % (step, rel, text))


# ---------------------------------------------------------------- steps
# each: (ctx, rel, XD, PD, res, fix) -> number of words set (fix) / found wrong (check); PD sections changed in place

def s_objevent(ctx, rel, XD, PD, res, fix):
    import io, contextlib, obj_eventlist_fix as OE
    T = ctx.oe_table(); c = res.cnt['objevent']
    # lists check_lists cannot compare (it only prints them): another size, or the Xbox list does not walk
    for (_, xs, xl), (_, ps, pl) in zip(OE.objects(XD, 'be'), OE.objects(PD, 'le')):
        if xl is None or pl is None: continue
        if len(xl.data) != len(pl.data) or OE.walk(xl.data, 'be')[1] is None:
            res.pair(xl, pl); c['lists not checked'] += 1
            res.odd('objevent', rel, 'object %d list 7:%d: Xbox 0x%x / PC 0x%x bytes%s' % (
                ps.id, pl.id, len(xl.data), len(pl.data), '' if OE.walk(xl.data, 'be')[1] is not None else ', Xbox list does not walk'))
    with contextlib.redirect_stdout(io.StringIO()):
        lists = OE.check_lists(T, XD, PD, False)
    n = 0
    index = {id(s): k for k, s in enumerate(PD.sections)}
    for oid, xl, pl, wk, diffs, unk in lists:
        res.pair(xl, pl)
        c['lists'] += 1; c['records'] += len(wk[1])
        c['unknown / ambiguous keys'] += sum(unk.values())
        idw = {a + 12 for a, h, sz in wk[1] if h & 3 == 1 and sz >= 16 and struct.unpack_from('>H', xl.data, a + 8)[0] == SUB_ID}
        diffs = [d for d in diffs if d[0] not in idw]
        c['words checked'] += sum(1 for kk in wk[0].values() if kk != 'P')
        if not diffs: continue
        b = bytearray(pl.data)
        for o, kk, x4, p4, want in diffs:
            if res.change('objevent', rel, index[id(pl)], pl, o, p4, want, '%s %s' % (kk, how(x4, p4, want))):
                n += 1
                if fix: b[o:o + 4] = want
        if fix and bytes(b) != pl.data:
            pl.data = bytes(b)
            fw = OE.walk(pl.data, 'le')
            if [(a, h) for a, h, _ in fw[0]] != [(a, struct.unpack_from('>H', xl.data, a)[0]) for a, _, _ in wk[1]]:
                res.odd('objevent', rel, 'object %d list %d: PC walk differs from the Xbox records after the fix' % (oid, pl.id))
    return n


def s_idword(ctx, rel, XD, PD, res, fix):
    import obj_eventlist_fix as OE
    c = res.cnt['idword']; n = 0
    ids = {s.id for s in PD.sections}
    index = {id(s): k for k, s in enumerate(PD.sections)}
    for (_, xs, xl), (_, ps, pl) in zip(OE.objects(XD, 'be'), OE.objects(PD, 'le')):
        if xl is None or pl is None: continue
        res.pair(xl, pl)
        rp, ep = OE.walk(pl.data, 'le'); rx, ex = OE.walk(xl.data, 'be')
        if len(xl.data) != len(pl.data) or len(rp) != len(rx) or any(a[:3] != b[:3] for a, b in zip(rp, rx)):
            continue                                  # objevent reports lists that do not walk alike
        d = bytearray(pl.data)
        for a, h, sz in rx:
            if h & 3 != 1 or sz < 16 or struct.unpack_from('>H', xl.data, a + 8)[0] != SUB_ID: continue
            if a + 12 in set(R.parse(bytes(xl.reloc), 'be').pointer_offsets()): continue
            x4 = bytes(xl.data[a + 12:a + 16]); p4 = bytes(d[a + 12:a + 16]); want = x4[::-1]
            c['records'] += 1
            if p4 == want: c['ok'] += 1; continue
            xw = struct.unpack('>I', x4)[0]
            k = how(x4, p4, want)
            if k in ('raw', 'u16') and xw in ids:
                if res.change('idword', rel, index[id(pl)], pl, a + 12, p4, want, 'sub 0x32 id %d %s' % (xw, k)):
                    n += 1
                    if fix: d[a + 12:a + 16] = want
            else:
                res.odd('idword', rel, 'object %d list %d +0x%x: Xbox %s PC %s (%s, id %s)' % (
                    ps.id, pl.id, a + 12, x4.hex(), p4.hex(), k, 'names a section' if xw in ids else 'NOT a section'))
        if fix and bytes(d) != pl.data: pl.data = bytes(d)
    return n


def same_framing(T, x, p, lw):
    """every structural word (record header u16 h / s16 frame, terminator) of the PC list = the rule's conversion of
    the Xbox list's word"""
    import animlist_check as AL
    for o, kk, a in lw:
        if kk != 'T' and kk[2] != 0: continue
        exp, cl = AL.expected(T, x, o, kk, a)
        if exp is None or bytes(p.data[o:o + len(exp)]) != exp: return False
    return True


def s_animlist(ctx, rel, XD, PD, res, fix):
    import animlist_check as AL, animfx as AF
    T = ctx.oe_table(); c = res.cnt['animlist']; n = 0
    for k, x, p in pairs_by_position(XD, PD):
        if x.type != 7 or len(x.data) != len(p.data): continue
        lw = AL.list_words(x)
        if lw is None: continue
        c['lists'] += 1
        if res.pair(x, p) and same_framing(T, x, p, lw):
            # a base-mapped DTP whose records are this Xbox list's records (every header word {u16 h, s16 frame} and
            # the terminator equal the conversion): it IS a conversion of this list, so the rule applies (dlc_costume_*
            # / lara_doppelganger DTP 1581: payload words as u16 pairs, B138 has the rule's bytes). Lists with other
            # records (another frame / type: a base copy) stay as they are.
            res.mapped = False; c['base-mapped lists with the Xbox record framing (checked)'] += 1
        d = bytearray(p.data)
        for o, kk, a in lw:
            exp, cl = AL.expected(T, x, o, kk, a)
            if exp is None: c['no rule'] += 1; continue
            got = bytes(d[o:o + len(exp)])
            if got == exp: c['ok'] += 1; continue
            if res.change('animlist', rel, k, p, o, got, exp, '%s %s (Xbox %s)' % (kk, cl, x.data[o:o + 4].hex())):
                n += 1
                if fix: d[o:o + len(exp)] = exp
        if fix and bytes(d) != p.data:
            p.data = bytes(d)
            wp, wx = AF.walk(p.data, '<'), AF.walk(x.data, '>')
            if wp is None or [r[:2] for r in wp[0]] != [r[:2] for r in wx[0]]:
                res.odd('animlist', rel, '7:%d: PC walk differs from the Xbox records after the fix' % p.id)
    return n


def s_fxnode(ctx, rel, XD, PD, res, fix):
    import fxnode_id_fix as FX
    c = res.cnt['fxnode']; n = 0
    ids = {s.id for s in PD.sections}
    for k, x, p in pairs_by_position(XD, PD):
        if x.type != 7: continue
        nx = FX.nodes(x, 'be')
        if not nx: continue
        if len(x.data) != len(p.data): c['size differs (re-authored, not checked)'] += 1; continue
        res.pair(x, p)
        # the nodes as the Xbox file has them (the PC detection needs a correct self id: tools/fxnode_id_fix.nodes);
        # node = u32 type, ptr data, u32 self id (= the PC DTP id), u32 0 - on the base pair every node DTP is found
        # alike on both sides (proof), so these header words are u32 on the PC
        pin = dict(R.parse(bytes(p.reloc), 'le').internal)
        d = bytearray(p.data); np_ = []
        for o, t, dx in nx:
            dp = pin.get(o + 4)
            if dp != dx:
                res.odd('fxnode', rel, '7:%d node +0x%x: PC pointer at +4 %s, Xbox -> +0x%x' % (
                    p.id, o, 'missing' if dp is None else '-> +0x%x' % dp, dx)); continue
            np_.append((o, t, dp))
            for w, val in ((0, t), (8, p.id), (12, 0)):
                x4 = bytes(x.data[o + w:o + w + 4]); p4 = bytes(d[o + w:o + w + 4]); want = struct.pack('<I', val)
                c['header words'] += 1
                if p4 == want: continue
                cl = how(x4, p4, want) if val == struct.unpack('>I', x4)[0] else 'other'
                if cl in ('raw', 'u16'):
                    if res.change('fxnode', rel, k, p, o + w, p4, want, 'node +0x%x %s %s' % (o, ('type', '', 'self id', 'zero')[w // 4], cl)):
                        c['wrong header words'] += 1; n += 1
                        if fix: d[o + w:o + w + 4] = want
                else:
                    res.odd('fxnode', rel, '7:%d node +0x%x word +%d: PC %s Xbox %s want %s' % (p.id, o, w, p4.hex(), x4.hex(), want.hex()))
        for o, t, dp in np_:
            dx = dp
            if t != 1 or dp + 4 > len(p.data) or dx + 4 > len(x.data): continue
            c['type1'] += 1
            p4 = bytes(d[dp:dp + 4]); x4 = bytes(x.data[dx:dx + 4])
            pw = struct.unpack('<I', p4)[0]; xw = struct.unpack('>I', x4)[0]
            cl = FX.cls(pw, xw)
            if cl == 'ok': c['ok'] += 1; continue
            if cl == 'other' and pw in ids: c['renumbered'] += 1; continue
            if cl in ('raw', 'u16') and xw in ids:
                want = struct.pack('<I', xw)
                if res.change('fxnode', rel, k, p, dp, p4, want, 'node +0x%x type-1 id %d %s' % (o, xw, cl)):
                    c['wrong type-1 ids'] += 1; n += 1
                    if fix: d[dp:dp + 4] = want
                continue
            res.odd('fxnode', rel, '7:%d node +0x%x data +0x%x: PC 0x%08x Xbox 0x%08x (%s, PC value %s a section)' % (
                p.id, o, dp, pw, xw, cl, 'is' if pw in ids else 'NOT'))
        if fix and bytes(d) != p.data: p.data = bytes(d)
    return n


def s_statevm(ctx, rel, XD, PD, res, fix):
    import statevm_check as SV
    c = res.cnt['statevm']; n = 0
    for k, x, p in pairs_by_position(XD, PD):
        if x.type != 7: continue
        wx = SV.code_words(x, 'be')
        if not wx: continue
        wp = SV.code_words(p, 'le'); res.pair(x, p)
        if len(x.data) != len(p.data) or set(wp) != set(wx):
            if len(x.data) == len(p.data): res.odd('statevm', rel, '7:%d: code layout differs (same size)' % p.id)
            else: c['size differs (re-authored, not checked)'] += 1
            continue
        c['sections'] += 1; c['words'] += len(wp)
        d = bytearray(p.data)
        for o in sorted(wp):
            if wp[o] == wx[o]: continue
            x4 = bytes(x.data[o:o + 4]); p4 = bytes(d[o:o + 4]); want = x4[::-1]
            cl = how(x4, p4, want)
            if cl in ('raw', 'u16'):
                if res.change('statevm', rel, k, p, o, p4, want, cl):
                    n += 1
                    if fix: d[o:o + 4] = want
            else:
                res.odd('statevm', rel, '7:%d +0x%x: PC 0x%08x Xbox 0x%08x (%s)' % (p.id, o, wp[o], wx[o], cl))
        if fix and bytes(d) != p.data: p.data = bytes(d)
    return n


def s_chartid(ctx, rel, XD, PD, res, fix):
    import statechart_corpus as CO, state_actlist_fix as SA, chart_idvalue_fix as CI
    c = res.cnt['chartid']; n = 0; M = None
    for k, x, p in pairs_by_position(XD, PD):
        if x.type != 7 or CO.fam_be(bytes(x.data), x.id) != 'chart': continue
        if len(x.data) != len(p.data): c['size differs (re-authored, not checked)'] += 1; continue
        res.pair(x, p)
        rx, rp = SA.records(x, 'be'), SA.records(p, 'le')
        if len(rx) != len(rp):
            res.odd('chartid', rel, '7:%d: state record count differs (Xbox %d PC %d)' % (p.id, len(rx), len(rp))); continue
        c['charts'] += 1
        if M is None: M = CI.id_map(XD, PD); base = ctx.chart_base()
        d = bytearray(p.data)
        for tx, tp in zip(rx, rp):
            for i in range(tx[2][5]):
                ex, ep = tx[3] + 8 * i, tp[3] + 8 * i
                eid, et = struct.unpack_from('>HH', x.data, ex)
                if et not in (3, 5): continue
                c['entries'] += 1
                xv = struct.unpack_from('>I', x.data, ex + 4)[0]; p4 = bytes(d[ep + 4:ep + 8])
                t7 = sorted({q for t, q in M.get(xv, set()) if t == 7})
                if (eid, et, xv) in base and len(base[(eid, et, xv)]) == 1: exp, src = next(iter(base[(eid, et, xv)])), 'base pair'
                elif len(t7) == 1: exp, src = t7[0], 'DTP map'
                else:
                    res.odd('chartid', rel, '7:%d entry +0x%x id %d type %d Xbox 0x%x: no proven PC value' % (p.id, ep, eid, et, xv))
                    continue
                want = struct.pack('<I', exp)
                if p4 == want: c['ok'] += 1; continue
                if res.change('chartid', rel, k, p, ep + 4, p4, want, 'id %d type %d Xbox 0x%x -> %d (%s)' % (eid, et, xv, exp, src)):
                    n += 1
                    if fix: d[ep + 4:ep + 8] = want
        if fix and bytes(d) != p.data: p.data = bytes(d)
    return n


FNS = {s: globals()['s_' + s] for s in STEPS}


# ---------------------------------------------------------------- tree runs
def xbox_of(rel):
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    raw, src = raw_dlc(rel.replace('/', '\\'))
    if raw is None: raw, src = raw_dlc(os.path.basename(rel))
    if raw is None: return None, None
    return DW.read(cdrm_decode(raw, 'be'), 'be'), src


def run_tree(srcs, out, steps, names=None, check_only=False, ctx=None, log=print):
    """srcs: folders (later wins). fix: changed DRMs -> out (read back, re-checked). Returns a result dict."""
    import dtp_audit as DA
    ctx = ctx or Ctx(); res = Result()
    files = sorted(DA.overlay([os.path.abspath(s) for s in srcs], names).items())
    written, no_xbox = [], []; pairing = collections.Counter()
    for rel, path in files:
        XD, src = xbox_of(rel)
        if XD is None: no_xbox.append(rel); continue
        raw = open(path, 'rb').read()
        PD = DW.read(raw, 'le')
        pp = pairs_by_position(XD, PD); pairing['PC type-7 sections'] += sum(1 for s in PD.sections if s.type == 7)
        pairing['paired with an Xbox section'] += sum(1 for k, x, p in pp if p.type == 7)
        pairing['paired, same size'] += sum(1 for k, x, p in pp if p.type == 7 and len(x.data) == len(p.data))
        per = {}
        for st in steps:
            per[st] = FNS[st](ctx, rel, XD, PD, res, not check_only)
        if any(per.values()):
            log('%s (%s): %s' % (rel, src, ', '.join('%s %d' % (k, v) for k, v in per.items() if v)))
        if check_only or not any(per.values()): continue
        new = encode(PD, raw)
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
        # read back: same sections, then every step again on the written file - nothing may be left
        DR = DW.read(open(q, 'rb').read(), 'le')
        assert [(a.type, a.id, a.data, a.reloc) for a in DR.sections] == [(b.type, b.id, b.data, b.reloc) for b in PD.sections]
        again = Result()
        left = {st: FNS[st](ctx, rel, XD, DR, again, False) for st in steps}
        if any(left.values()):
            res.odd('readback', rel, 'words still wrong after the fix: %s' % left)
        written.append(rel)
    out_d = {'steps': list(steps), 'mode': 'check' if check_only else 'fix', 'sources': [os.path.abspath(s) for s in srcs],
             'files': len(files), 'files_without_xbox_original': no_xbox, 'written': written, 'pairing': dict(pairing),
             'counts': {st: dict(res.cnt[st]) for st in steps},
             'files_changed': {st: dict(res.files[st]) for st in steps},
             'unexpected': res.unexpected, 'kept_base_mapped': res.kept, 'changes': res.changes}
    return out_d


def summary(r, log=print):
    for st in r['steps']:
        c = r['counts'].get(st, {})
        log('%-9s %s' % (st, ', '.join('%s %d' % kv for kv in sorted(c.items())) or '-'))
        if r['mode'] == 'fix' and r['files_changed'].get(st):
            log('          set in %d file(s): %s' % (len(r['files_changed'][st]), ', '.join(
                '%s %d' % kv for kv in sorted(r['files_changed'][st].items()))))
    log('pairing: %s' % ', '.join('%s %d' % kv for kv in r.get('pairing', {}).items()))
    log('files %d (without Xbox original %d), written %d, unexpected %d' % (
        r['files'], len(r['files_without_xbox_original']), len(r['written']), len(r['unexpected'])))
    for u in r['unexpected'][:200]: log('UNEXPECTED ' + u)
    for f in r['files_without_xbox_original']: log('NO XBOX ORIGINAL ' + f + ' (not checked: add its pack to convert_dlc.PACKS or set TRUDLC_EXTRA_XBOX)')


def failed(r):
    wrong = sum(r['counts'].get(st, {}).get('wrong', 0) for st in r['steps']) if r['mode'] == 'check' else 0
    return bool(r['unexpected']) or bool(r['files_without_xbox_original']) or wrong > 0


# ---------------------------------------------------------------- proof on the base pair
def proof(xref=None, pref=None):
    """every rule applied to the base pair itself, sections paired by order (the PC renumbers base ids)"""
    import io, contextlib
    import statevm_check as SV, fxnode_id_fix as FX, animlist_check as AL, animfx as AF, obj_eventlist_fix as OE
    import state_actlist_fix as SA
    ctx = Ctx(xref, pref)
    XD = DW.read(open(ctx.xref, 'rb').read(), 'be'); PD = DW.read(open(ctx.pref, 'rb').read(), 'le')
    got = {}
    # statevm: k-th VM DTP of each file
    xv = [s for s in XD.sections if s.type == 7 and SV.code_blocks(s, 'be')]
    pv = [s for s in PD.sections if s.type == 7 and SV.code_blocks(s, 'le')]
    ns = nw = nb = 0
    for x, p in zip(xv, pv):
        wx, wp = SV.code_words(x, 'be'), SV.code_words(p, 'le')
        if set(wx) != set(wp): nb += 1; continue
        ns += 1; nw += len(wp); nb += sum(1 for o in wp if wp[o] != wx[o])
    got['statevm'] = {'sections': ns, 'words': nw, 'wrong': nb + abs(len(xv) - len(pv))}
    # fxnode: k-th node DTP of each file; type 1 = one LE u32 naming a PC section
    ids = {s.id for s in PD.sections}
    xn = [s for s in XD.sections if FX.nodes(s, 'be')]; pn = [s for s in PD.sections if FX.nodes(s, 'le')]
    t1 = bad = hdr = 0; lay = []
    for x, p in zip(xn, pn):
        a, b = FX.nodes(x, 'be'), FX.nodes(p, 'le')
        if [(o, t) for o, t, _ in a] != [(o, t) for o, t, _ in b]:
            lay.append('Xbox 7:%d (%d bytes, %d nodes) / PC 7:%d (%d bytes, %d nodes)' % (
                x.id, len(x.data), len(a), p.id, len(p.data), len(b)))
            continue
        pin = dict(R.parse(bytes(p.reloc), 'le').internal)
        for (o, t, dx), (_, _, dp) in zip(a, b):
            # header words: u32 type, u32 self id (= the PC DTP id, renumbered), u32 0 - and the pointer at +4
            hdr += 3
            tw, _, sid, z = struct.unpack_from('<IIII', p.data, o)
            if (tw, sid, z) != (t, p.id, 0) or pin.get(o + 4) != dp: bad += 1
            if t != 1: continue
            t1 += 1
            pw = struct.unpack_from('<I', p.data, dp)[0]
            if pw not in ids: bad += 1
    got['fxnode'] = {'type1': t1, 'header_words': hdr, 'wrong': bad + abs(len(xn) - len(pn)), 'node_dtps': len(xn), 'layout_differs': len(lay)}
    for l in lay: print('fxnode node layout differs (not compared): %s' % l)
    # chartid: every type-3 / 5 value = the PC id of the aligned DTP or the base value (the table is the pair itself,
    # so the check that matters is the DTP map: entries the map explains)
    import chart_idvalue_fix as CI
    M = CI.id_map(XD, PD)
    BX = [s for s in XD.sections if s.type == 7 and s.id == CHART_X][0]; BP = [s for s in PD.sections if s.type == 7 and s.id == CHART_P][0]
    ent = bad = by_map = 0
    for tx, tp in zip(SA.records(BX, 'be'), SA.records(BP, 'le')):
        for i in range(tx[2][5]):
            eid, et = struct.unpack_from('>HH', BX.data, tx[3] + 8 * i)
            if et not in (3, 5): continue
            ent += 1
            xv_ = struct.unpack_from('>I', BX.data, tx[3] + 8 * i + 4)[0]; pv_ = struct.unpack_from('<I', BP.data, tp[3] + 8 * i + 4)[0]
            t7 = sorted({q for t, q in M.get(xv_, set()) if t == 7})
            if len(t7) == 1:
                by_map += 1
                if pv_ != t7[0]: bad += 1
    got['chartid'] = {'entries': ent, 'by_dtp_map': by_map, 'wrong': bad}
    # animlist: k-th anim list of each file, every rule word
    T = ctx.oe_table()
    xa = [s for s in XD.sections if s.type == 7 and AF.walk(s.data, '>') is not None]
    pa = [s for s in PD.sections if s.type == 7 and AF.walk(s.data, '<') is not None]
    tot = collections.Counter()
    for x, p in zip(xa, pa):
        with contextlib.redirect_stdout(io.StringIO()):
            cc = AL.check_sec(T, x, p, '', None)
        if cc: tot.update(cc)
        else: tot['size differs'] += 1
    got['animlist'] = {'ok': tot['ok'], 'no_rule': tot['no rule'], 'wrong': tot['wrong'] + tot['size differs']}
    # objevent: the rule table is learned from this pair - every rule word must reproduce (no ambiguity)
    with contextlib.redirect_stdout(io.StringIO()):
        lists = OE.check_lists(T, XD, PD, False)
    got['objevent'] = {'lists': len(lists), 'words': sum(sum(1 for kk in r[3][0].values() if kk != 'P') for r in lists),
                       'wrong': sum(len(r[4]) for r in lists)}
    # idword: sub-0x32 records in the base pair (none: the rule rests on the reader tru+0x1486b2)
    rec = 0
    for (_, xs, xl), (_, ps, pl) in zip(OE.objects(XD, 'be'), OE.objects(PD, 'le')):
        if xl is None or pl is None: continue
        for a, h, sz in OE.walk(xl.data, 'be')[0]:
            if h & 3 == 1 and sz >= 16 and struct.unpack_from('>H', xl.data, a + 8)[0] == SUB_ID: rec += 1
    for x, p in zip(xa, pa):
        for a, h, fr, sz in AF.walk(x.data, '>')[0]:
            if h & 3 == 1 and sz >= 16 and struct.unpack_from('>H', x.data, a + 8)[0] == SUB_ID: rec += 1
    got['idword'] = {'records': rec, 'wrong': 0}
    ok = True
    md5 = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest()
    print('base pair: %s (md5 %s) / %s (md5 %s)' % (os.path.relpath(ctx.xref), md5(ctx.xref), os.path.relpath(ctx.pref), md5(ctx.pref)))
    for st in STEPS:
        exp = PROOF_EXPECT[st]
        good = all(got[st].get(k) == v for k, v in exp.items())
        ok &= good
        print('%-9s %s  %s (expected %s)' % (st, 'PROVEN' if good else 'FAILED', got[st], exp))
    print('proof: %s' % ('all rules hold on the base pair' if ok else 'FAILED'))
    return 0 if ok else 1


# ---------------------------------------------------------------- comparison with a reference tree
def load_changes(paths):
    """{(file, section index, offset): change} from converter_faults_fix reports or dlc_fixes_build fixes_report.json"""
    changed = {}
    for rp in paths:
        r = json.load(open(rp, encoding='utf-8'))
        lists = [r['changes']] if 'changes' in r else [v['changes'] for v in r.values() if isinstance(v, dict) and 'changes' in v]
        for lst in lists:
            for ch in lst:
                changed[(ch['file'].lower(), ch['index'], ch['off'])] = ch
    return changed


def word_diffs(x, y):
    return {o for o in range(0, len(x.data) - 3, 4) if x.data[o:o + 4] != y.data[o:o + 4]}


class Regions:
    """which structure a word of an Xbox section belongs to (for explaining differences): 'anim list', 'object
    event list' (records / after the terminator), 'effect node', 'VM code', 'state chart', 'markup', else 'other'"""
    def __init__(self, XD, PD):
        import obj_eventlist_fix as OE
        self.XD = XD; self.cache = {}; self.xk = {k: x for k, x, p in pairs_by_position(XD, PD)}
        self.lists = {xl.id for _, _, xl in OE.objects(XD, 'be') if xl is not None}

    def of(self, k, o):
        import animfx as AF, obj_eventlist_fix as OE, fxnode_id_fix as FX, statevm_check as SV, statechart_corpus as CO
        if k not in self.xk: return 'no Xbox partner'
        x = self.xk[k]
        if x.type != 7: return 'type %d' % x.type
        if k not in self.cache:
            reg = []
            w = AF.walk(x.data, '>')
            if w is not None: reg.append(('anim list', [(a, a + sz) for a, h, fr, sz in w[0]] + [(w[1], w[1] + 4)]))
            if x.id in self.lists:
                recs, end = OE.walk(x.data, 'be')
                reg.append(('object event list', [(a, a + sz) for a, h, sz in recs] + ([(end, len(x.data))] if end is not None else [])))
            nd = FX.nodes(x, 'be')
            if nd: reg.append(('effect node', [(a, a + 16) for a, t, d in nd] + [(d, d + 4) for a, t, d in nd if t == 1]))
            cw = SV.code_words(x, 'be')
            if cw: reg.append(('VM code', [(a, a + 4) for a in cw]))
            if CO.fam_be(bytes(x.data), x.id) == 'chart': reg.append(('state chart', [(0, len(x.data))]))
            if len(x.data) >= 0x5c:
                n = struct.unpack_from('>I', x.data, 0x54)[0]; ro = dict(R.parse(bytes(x.reloc), 'be').internal).get(0x58)
                if ro is not None and 1 <= n <= 1000 and ro + n * 0x5c <= len(x.data): reg.append(('markup', [(ro, ro + n * 0x5c)]))
            self.cache[k] = reg
        for name, spans in self.cache[k]:
            if any(a <= o < b for a, b in spans): return name
        return 'other'


def compare(new_dir, ref_dir, change_reports, before_dir=None, detail=False, classify=False):
    """per DRM of ref_dir: sections paired by position, differing words; with change reports every differing word
    is split by 'set by a fault step', and every fault-step word is compared with REF; with before_dir (the same
    pipeline without the fault steps) the differences are split into: removed by the new steps (before differs, new =
    REF), new differences (new differs, before = REF) and differences in both (not caused by the fault steps)"""
    import dtp_audit as DA
    changed = load_changes(change_reports)
    refs = DA.overlay([os.path.abspath(ref_dir)], None)
    newl = {k.lower(): v for k, v in DA.overlay([os.path.abspath(new_dir)], None).items()}
    befl = {k.lower(): v for k, v in DA.overlay([os.path.abspath(before_dir)], None).items()} if before_dir else {}
    rep = {'new': os.path.abspath(new_dir), 'ref': os.path.abspath(ref_dir), 'before': before_dir and os.path.abspath(before_dir),
           'files': {}}
    tot = collections.Counter()
    for rel in sorted(refs):
        q = newl.get(rel.lower())
        if q is None:
            rep['files'][rel] = {'status': 'only in REF'}; tot['only in REF'] += 1
            print('%-48s only in REF' % rel); continue
        a, b = open(q, 'rb').read(), open(refs[rel], 'rb').read()
        A, B = DW.read(a, 'le'), DW.read(b, 'le')
        C = DW.read(open(befl[rel.lower()], 'rb').read(), 'le') if rel.lower() in befl else None
        RG = None
        if classify:
            XD, _ = xbox_of(rel)
            RG = Regions(XD, A) if XD is not None else None
        fr = {'md5_new': hashlib.md5(a).hexdigest(), 'md5_ref': hashlib.md5(b).hexdigest(), 'sections_new': len(A.sections),
              'sections_ref': len(B.sections)}
        c = collections.Counter(); secs = []
        for k, (x, y) in enumerate(zip(A.sections, B.sections)):
            if (x.type, x.id) != (y.type, y.id):
                c['sections paired differently'] += 1; secs.append({'index': k, 'new': [x.type, x.id], 'ref': [y.type, y.id]})
                continue
            z = C.sections[k] if C is not None and k < len(C.sections) and (C.sections[k].type, C.sections[k].id) == (x.type, x.id) else None
            same_new = x.data == y.data and x.reloc == y.reloc
            same_bef = z is not None and z.data == y.data and z.reloc == y.reloc
            if same_new and (z is None or same_bef): c['identical sections'] += 1; continue
            e = {'index': k, 'type': x.type, 'id': x.id, 'size_new': len(x.data), 'size_ref': len(y.data),
                 'reloc_same': x.reloc == y.reloc}
            if len(x.data) == len(y.data):
                dn = word_diffs(x, y)
                fault = {o for o in dn if (rel.lower(), k, o) in changed}
                e.update({'words': len(dn), 'words_at_fault_step_words': len(fault), 'first': ['+0x%x' % o for o in sorted(dn)[:6]],
                          'bytes new/ref/before': ['+0x%x %s/%s/%s' % (o, x.data[o:o + 4].hex(), y.data[o:o + 4].hex(), z.data[o:o + 4].hex() if z is not None and len(z.data) == len(y.data) else '-') for o in sorted(dn)[:3]]})
                c['differing words'] += len(dn); c['differing words at fault-step words'] += len(fault)
                if z is not None and len(z.data) == len(y.data):
                    db = word_diffs(z, y)
                    gone, new, both = db - dn, dn - db, dn & db
                    e.update({'removed_by_new_steps': len(gone), 'new_differences': len(new), 'in_both': len(both),
                              'new_differences_at_fault_step_words': len(new & fault),
                              'removed_at_fault_step_words': sum(1 for o in gone if (rel.lower(), k, o) in changed)})
                    c['words: removed by the new steps'] += len(gone); c['words: new differences'] += len(new)
                    c['words: new differences at fault-step words'] += len(new & fault); c['words: in both'] += len(both)
                    parts = (('new', new), ('both', both))
                else:
                    parts = (('differs', dn),)
                if RG is not None:
                    reg = collections.Counter()
                    for cat, ws in parts:
                        for o in ws: reg['%s / %s' % (cat, RG.of(k, o))] += 1
                    e['regions'] = dict(reg); c.update({'region ' + kk: v for kk, v in reg.items()})
            else:
                c['sections of another size'] += 1
            if not same_new: c['differing sections'] += 1
            secs.append(e)
        if len(A.sections) != len(B.sections): c['section count differs (new %d, ref %d)' % (len(A.sections), len(B.sections))] += 1
        # every word a fault step set in this file: does REF have the same bytes?
        for (f, k, o), ch in changed.items():
            if f != rel.lower(): continue
            if k < len(B.sections) and (B.sections[k].type, B.sections[k].id) == (ch['type'], ch['id']):
                same = bytes(B.sections[k].data[o:o + len(bytes.fromhex(ch['new']))]) == bytes.fromhex(ch['new'])
                c['fault-step words = REF' if same else 'fault-step words != REF'] += 1
                c['fault-step words %s %s' % (ch['step'], '= REF' if same else '!= REF')] += 1
            else:
                c['fault-step words in sections REF does not have'] += 1
        fr['status'] = 'identical' if a == b else 'identical sections' if not any(
            'words' not in s or s['words'] for s in secs) and len(A.sections) == len(B.sections) else 'differs'
        fr['counts'] = dict(c); fr['sections'] = secs
        rep['files'][rel] = fr
        tot[fr['status']] += 1; tot.update({k: v for k, v in c.items() if k != 'identical sections'})
        print('%-48s %-18s %s' % (rel, fr['status'], ', '.join('%s %d' % kv for kv in sorted(c.items()) if kv[0] != 'identical sections')))
        if detail:
            for s in secs:
                if 'new' in s: print('    #%d paired differently: new %s, ref %s' % (s['index'], s['new'], s['ref'])); continue
                print('    #%d %d:%d size %d/%d reloc %s words %s removed %s new %s both %s first %s' % (
                    s['index'], s['type'], s['id'], s['size_new'], s['size_ref'], 'same' if s['reloc_same'] else 'DIFF',
                    s.get('words', '-'), s.get('removed_by_new_steps', '-'), s.get('new_differences', '-'),
                    s.get('in_both', '-'), ' '.join(s.get('first', []))) + (' regions %s' % s['regions'] if s.get('regions') else '') +
                      (' bytes new/ref/before %s' % s['bytes new/ref/before'] if s.get('bytes new/ref/before') else ''))
    rep['total'] = dict(tot)
    print('total: %s' % ', '.join('%s %d' % kv for kv in sorted(tot.items())))
    return rep


# ---------------------------------------------------------------- command line
def main(argv):
    if not argv: print(__doc__); return 2
    opt = {}
    for k in ('--steps', '--pack', '--names', '--report', '--changes', '--before'):
        while k in argv:
            i = argv.index(k); opt.setdefault(k, []).append(argv[i + 1]); del argv[i:i + 2]
    if '--pack' in opt: os.environ['TRUDLC_PACK_FIRST'] = opt['--pack'][0]
    steps = [s for s in STEPS if s in opt['--steps'][0].split(',')] if '--steps' in opt else list(STEPS)
    if '--steps' in opt and len(steps) != len(opt['--steps'][0].split(',')): raise SystemExit('unknown step in %s (steps: %s)' % (opt['--steps'][0], ', '.join(STEPS)))
    names = set(opt['--names'][0].split(',')) if '--names' in opt else None
    report = opt.get('--report', [None])[0]
    mode, args = argv[0], argv[1:]
    if mode == 'proof':
        return proof(*args[:2]) if len(args) >= 2 else proof()
    if mode == 'compare':
        r = compare(args[0], args[1], opt.get("--changes", []), opt.get("--before", [None])[0], "--detail" in args, "--classify" in args)
        if report: json.dump(r, open(report, 'w', encoding='utf-8'), indent=1)
        return 0
    if mode not in ('fix', 'check'): print(__doc__); return 2
    if mode == 'fix':
        if len(args) < 2: raise SystemExit('fix: SRC_DIR [SRC_DIR ..] OUT_DIR')
        srcs, out = args[:-1], args[-1]
    else:
        srcs, out = args, None
    r = run_tree(srcs, out, steps, names, mode == 'check')
    summary(r)
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(r, open(report, 'w', encoding='utf-8'), indent=1)
    if failed(r):
        print('FAILED: %s' % ('unexpected words (see UNEXPECTED lines) - nothing guessed' if r['unexpected'] else
                             'DRMs without an Xbox original (see NO XBOX ORIGINAL lines)' if r['files_without_xbox_original'] else 'wrong words left'))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
