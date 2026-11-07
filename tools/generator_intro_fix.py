"""Intro data of the pool / spawn generator instances: typed byte-order rule, retail proof, gate and fix (docs
Befund-Hall02-TU-Vergleich-0711.md section 4 / 6 F1-F2, Befund-Generator-Datenfix-0711.md).

Why: the converter types the generator intro data per word with the learned type-7 classes; for some DLC 2 records the
classes are wrong (+0x30 max alive kept raw: 1 -> 256, +0x38 / +0x5c as 32-bit: group size 1 -> 0 and the flag bit 0
"automatic spawning off" moved into +0x5e, the group delay +0x44 as two u16, +0x54 kept raw ...). The hall02 tutorial
generator therefore spawns on its own as soon as the unit loads, before the script starts it - the checkpoint 11258
stores the spawned thralls and the wall softlock after a death follows (docs Befund-Hall02-TU-Vergleich-0711.md 4.3).

Layout of the generator intro data (Intro +0x78, relocated; engine readers PC tru+0x380d24 Init / tru+0x380eb0 Spawn /
tru+0x381510 Simulate, TU 0x82481f70 / 0x82480c88 / 0x82481530; the generator instance keeps the pointer at +0x104):
  header +0x00 .. +0x6f, fixed offsets:
    +0x28 pointer (-> +0x70), +0x30 u16 max alive, +0x32 u16, +0x34 s16 total limit, +0x36 u16, +0x38 u16 group size,
    +0x3c / +0x40 / +0x44 / +0x48 f32 delays, +0x4c .. +0x58 f32 (+0x54 / +0x58 distance), +0x5c u16 flags (bit 0 =
    start with automatic spawning off, bit 1 / 2 tested in Spawn), +0x60 pointer (alternative spawn list, unused:
    0 in every retail and DLC record), +0x64 pointer -> spawn list, +0x68 f32
  spawn list (at +0x64, = +0x70 in every record): u32 count n, then n entries of 0x1c bytes (PC tru+0x380c36
    `lea eax, [eax + idx*28 + 4]`): entry +0x00 {u16 object id (remapped by object name), u8, u8}, +0x10 / +0x18
    pointers, the other words typed by the table below
  What follows the spawn list is NOT part of this rule: entry +0x10 points to the 0x390-byte enemy AI record of the
  spawned archetype (u32 0x0d at +0, typed by tools/aidata_fix.py inside the converter), entry +0x18 to an optional
  pointer list; mode `scan --tail` only counts those words (DLC and retail show the same class mix).

Identification: an intro is a pool generator when its object name contains `generator` AND its data has the layout
above (relocated header words exactly +0x28 / +0x64, both -> +0x70, count 1..16, entry pointers relocated).
`proof` shows on every retail pair that the layout alone selects only `*_generator*` objects and that the one
`*_generator*` object without it (merc_generator_run) has another layout (relocated +0x28 / +0x34 / +0x38) - it is
left alone.

Rule: per header / entry offset the set of byte orders (raw / u32 / u16x2 / u8u8u16 / u16u8u8) that explains EVERY
retail word at that offset (Eidos' own PC conversion: Xbox layer1 / layer2 / TU against PC bigfile / patch; relocated
words excluded; entry +0x00 compared after the object id remap). The table is fixed in TYPES; `proof` derives it anew
and reports PROVEN only when it is equal and nothing contradicts. A DLC word is set only where the PC word is ANOTHER
byte order of the Xbox word and the proven orders agree on the bytes; a PC word that is no byte order of the Xbox word
is UNEXPECTED (fix_drm raises SystemExit, the gate fails); if the proven orders give different bytes and the PC word is
one of them the word is UNJUDGED (left alone, listed). Pointers / relocations / ids are never written.

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 1800 tools/generator_intro_fix.py proof [--report R.json]
        every base-game unit with generator intros (pc_unitlist), every PC (pcbig / pcpatch) x Xbox (xbase / xbase2 /
        tu) copy: derives the table, checks identification and that the rule leaves the retail pairs unchanged
  ../bin/pyt -t 1800 tools/generator_intro_fix.py scan LIST_OR_DIR [--pack PACK] [--all] [--tail] [--report R.json]
        unit DRMs of a folder / list file / single .drm (several joined with ','; later name wins); exit 1 when any
        generator word is wrong or unexpected (the gate)
  ../bin/pyt -t 1800 tools/generator_intro_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the DRMs with wrong words to OUTDIR, proves each (only the planned bytes differ, headers / relocations
        identical, re-plan 0); md5.tsv + generator_intro_fix.log.txt in OUTDIR's parent folder
  ../bin/pyt -t 1800 tools/generator_intro_fix.py verify OLD.drm NEW.drm [--pack PACK]
        an existing pair: only generator words differ, all of them planned, re-plan of NEW 0
Library (step `genintro` of tools/dlc_struct_fixes.py, plan in docs Befund-Generator-Datenfix-0711.md 7):
  plan(XD, PD, rel, xnames, pnames), fix_drm(XD, raw, rel, pack) -> (new raw or None, changes, info)
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW, unit_ids as U

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')
PC_DLC_NAMES = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')
BASE_NAMES = {'pcbig': 'pc_objectlist.txt', 'pcpatch': 'pc_objectlist.txt', 'xbase': 'xbox_objectlist.txt',
              'xbase2': 'xbox_objectlist.txt', 'tu': 'xboxtu_objectlist.txt'}

ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16x2': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}
HDR = 0x70                      # header words +0x00 .. +0x6c
LIST = 0x70                     # spawn list: u32 count, entries of ENTRY bytes from +4
ENTRY = 0x1c
HDR_PTRS = (0x28, 0x64)         # relocated header words, both -> +0x70 (+0x60: null pointer in every record)
ENTRY_PTRS = (0x10, 0x18)       # relocated entry words
ENTRY_OBJ = 0x00                # entry +0x00 = {u16 object id, u8, u8}
MAXN = 16

# Proven table (measured 2026-11-07 with `proof`, docs Befund-Generator-Datenfix-0711.md 2): key -> orders that explain
# every retail word. 'h+XX' header offset, 'n' list count, 'e+XX' entry offset. All orders = every retail word is
# byte-symmetric there (0 / -1 / equal bytes): no evidence, such a word is only judged when all orders agree.
ALL = 'raw u16u8u8 u16x2 u32 u8u8u16'
TYPES_TEXT = """
h+00 u32
h+04 ALL
h+08 ALL
h+0c raw u8u8u16
h+10 ALL
h+14 u32
h+18 ALL
h+1c ALL
h+20 ALL
h+24 ALL
h+2c ALL
h+30 u16x2
h+34 u16x2
h+38 u16u8u8 u16x2
h+3c u32
h+40 u32
h+44 u32
h+48 u32
h+4c u32
h+50 u32
h+54 u32
h+58 u32
h+5c u16u8u8 u16x2
h+60 ALL
h+68 u32
h+6c ALL
n u32
e+00 u16u8u8
e+04 ALL
e+08 u32
e+0c u32
e+14 ALL
"""
# where the retail data leave two orders that give different bytes, the engine reader decides (PC / TU code, docs
# Befund-Hall02-TU-Vergleich-0711.md 4.1): +0x38 `u16` group size and +0x5c `u16` flags are 16-bit fields, their
# neighbours +0x3a / +0x5e are 16-bit too (u16x2); +0x0c is read as single bytes (raw). Used only when the proven
# orders disagree for a DLC word.
CODE_TIE = {'h+0c': 'raw', 'h+38': 'u16x2', 'h+5c': 'u16x2'}
# measured 2026-11-07 (`proof`); the derived table must equal TYPES_TEXT and these counts must be met
PROOF_EXPECT = {'contradicting': 0, 'retail_wrong': 0, 'layout_non_generator': 0}
VALUE_KEYS = ('h+00', 'h+0c', 'h+30', 'h+34', 'h+38', 'h+5c', 'n', 'e+00')     # value statistics printed by `proof`


def types_table():
    t = {}
    for line in TYPES_TEXT.strip().splitlines():
        k, v = line.split(None, 1)
        t[k] = frozenset((ALL if v.strip() == 'ALL' else v).split())
    return t


TYPES = types_table()


def perm(w, p):
    return bytes(w[i] for i in p)


def orders_of(xw, pw):
    return frozenset(n for n, p in ORDERS.items() if perm(xw, p) == pw)


# ---------------------------------------------------------------- names, units
def names(path):
    d = {}
    for line in open(path, encoding='utf8', errors='ignore'):
        a = line.strip().split(',', 1)
        if len(a) == 2 and a[0].isdigit(): d[int(a[0])] = a[1]
    return d


_NAMES = {}


def names_for(label):
    """object id -> name for a source label: pcbig / pcpatch / xbase / xbase2 / tu / pack10 / pack11 / ... / pcdlc"""
    if label not in _NAMES:
        if label == 'pcdlc': p = PC_DLC_NAMES
        elif label in BASE_NAMES: p = os.path.join(LISTS, BASE_NAMES[label])
        else: p = os.path.join(LISTS, 'dlc_%s_objectlist.txt' % label)
        _NAMES[label] = names(p) if os.path.exists(p) else {}
    return _NAMES[label]


class Unit:
    """intros of a unit DRM (any endian) with their data pointer and the relocation sets per section"""
    def __init__(self, D, endian):
        self.D, self.e = D, endian
        self.E = '>' if endian == 'be' else '<'
        secs = [dict(type=s.type, data=bytes(s.data), reloc=bytes(s.reloc), size=len(s.data)) for s in D.sections]
        self.L = U.level_info(secs, endian)
        self.data = [s['data'] for s in secs]
        self.rel = [R.parse(s['reloc'], endian) for s in secs]
        self.ptr = []
        for r in self.rel:
            m = {o: ('int', t) for o, t in r.internal}
            m.update({s: ('ext', (di, d)) for di, s, d in r.external})
            m.update({o: ('id', t) for t, o in r.idref + r.idref_a})
            self.ptr.append(m)
        self.intros = []
        if self.L is None: return
        for k, (si, o) in enumerate(self.L['intros']):
            d = self.data[si]
            it = dict(k=k, at=(si, o), obj=struct.unpack_from(self.E + 'H', d, o + 0x50)[0],
                      uid=struct.unpack_from(self.E + 'I', d, o + 0x58)[0],
                      pos=struct.unpack_from(self.E + '3f', d, o + 0x10), data=None)
            p = self.ptr[si].get(o + 0x78)
            if p and p[0] == 'int': it['data'] = (si, p[1])
            elif p and p[0] == 'ext': it['data'] = p[1]
            self.intros.append(it)

    def u32(self, si, o):
        return struct.unpack_from(self.E + 'I', self.data[si], o)[0]


def layout(Un, it):
    """-> dict(si, do, n, words=[(key, offset in section)], ptrs=[offsets]) when the intro data has the pool generator
    layout, else (None, reason)"""
    if it['data'] is None: return None, 'no data'
    si, do = it['data']
    d = Un.data[si]
    if do + LIST + 4 > len(d): return None, 'too short'
    pm = Un.ptr[si]
    hp = tuple(o for o in range(0, HDR, 4) if do + o in pm)
    if hp != HDR_PTRS: return None, 'header relocations %s' % ' '.join('+0x%x' % o for o in hp)
    for o in HDR_PTRS:
        if pm[do + o] != ('int', do + LIST): return None, 'header pointer +0x%x -> %s' % (o, pm[do + o])
    n = Un.u32(si, do + LIST)
    if not 1 <= n <= MAXN or do + LIST + 4 + n * ENTRY > len(d): return None, 'spawn list count %d' % n
    words, ptrs = [], [do + o for o in HDR_PTRS]
    for o in range(0, HDR, 4):
        if o not in HDR_PTRS: words.append(('h+%02x' % o, do + o))
    words.append(('n', do + LIST))
    for j in range(n):
        b = do + LIST + 4 + j * ENTRY
        ep = tuple(o for o in range(0, ENTRY, 4) if b + o in pm)
        if ep != ENTRY_PTRS: return None, 'entry %d relocations %s' % (j, ' '.join('+0x%x' % o for o in ep))
        ptrs += [b + o for o in ENTRY_PTRS]
        for o in range(0, ENTRY, 4):
            if o not in ENTRY_PTRS: words.append(('e+%02x' % o, b + o))
    return dict(si=si, do=do, n=n, words=words, ptrs=ptrs, end=do + LIST + 4 + n * ENTRY), None


def pair_intros(UX, UP, xn, pn):
    """[(Xbox intro, PC intro)] of the generator-named intros; index pairing when the intro lists agree (name and
    position), else by (name, position)"""
    def key(it, nm): return nm.get(it['obj'], '?'), tuple(round(v, 2) for v in it['pos'])
    if len(UX.intros) == len(UP.intros) and all(key(a, xn) == key(b, pn) for a, b in zip(UX.intros, UP.intros)):
        prs = list(zip(UX.intros, UP.intros))
    else:
        by = collections.defaultdict(list)
        for b in UP.intros: by[key(b, pn)].append(b)
        prs = [(a, by[key(a, xn)][0]) for a in UX.intros if len(by.get(key(a, xn), [])) == 1]
    return [(a, b) for a, b in prs if 'generator' in pn.get(b['obj'], '').lower()]


# ---------------------------------------------------------------- the rule
def remap_obj(xw, xn, pn, pnr):
    """entry +0x00 {u16 object id, u8, u8}: the Xbox word with the id replaced by the PC id of the same object name"""
    xid = struct.unpack('>H', xw[:2])[0]
    nm = xn.get(xid)
    pid = pnr.get(nm) if nm else None
    if pid is None: return None, xid, nm
    return struct.pack('>H', pid) + xw[2:], xid, nm


def judge(key, xw, pw, table=TYPES):
    """-> (status, wanted bytes or None, note): ok / fix:<PC order> / UNEXPECTED / UNJUDGED"""
    cands = table.get(key, frozenset(ORDERS))
    outs = {perm(xw, ORDERS[c]) for c in cands}
    note = ''
    if len(outs) == 1: want = next(iter(outs))
    elif key in CODE_TIE and CODE_TIE[key] in cands:
        want = perm(xw, ORDERS[CODE_TIE[key]]); note = 'code tie-break %s' % CODE_TIE[key]
    else:
        want = None
    if want is not None and pw == want: return 'ok', want, note
    od = orders_of(xw, pw)
    if not od: return 'UNEXPECTED', want, note
    if want is None: return 'UNJUDGED', None, 'orders %s give different bytes' % '/'.join(sorted(cands))
    return 'fix:%s' % '/'.join(sorted(od)), want, note


def plan(XD, PD, rel='unit', xlabel='pack11', plabel='pcdlc', UX=None, UP=None, table=TYPES):
    """-> dict(rows=[(PC section index, section id, offset, intro uid, object name, key, Xbox word, PC word, wanted,
    status, note)], gens=[...], other=[...], skip). The Xbox word of entry +0x00 is taken after the object remap."""
    res = dict(rows=[], gens=[], other=[], mismatch=[], skip=None, tail=collections.Counter())
    UX = UX or Unit(XD, 'be'); UP = UP or Unit(PD, 'le')
    if UX.L is None or UP.L is None: res['skip'] = 'no unit'; return res
    xn, pn = names_for(xlabel), names_for(plabel)
    pnr = {v: k for k, v in pn.items()}
    prs = pair_intros(UX, UP, xn, pn)
    if not prs: res['skip'] = 'no generator intros'; return res
    for a, b in prs:
        nm = pn.get(b['obj'], '?')
        lx, wx = layout(UX, a)
        lp, wp = layout(UP, b)
        if lx is None or lp is None:
            res['other'].append((b['uid'], nm, wx or 'ok', wp or 'ok'))
            if (lx is None) != (lp is None): res['mismatch'].append(b['uid'])   # one side has the layout: converter damage
            continue
        if (lx['n'], [k for k, _ in lx['words']]) != (lp['n'], [k for k, _ in lp['words']]):
            res['other'].append((b['uid'], nm, 'Xbox n %d' % lx['n'], 'PC n %d' % lp['n'])); continue
        res['gens'].append(dict(uid=b['uid'], xuid=a['uid'], name=nm, si=lp['si'], do=lp['do'], n=lp['n'],
                                xsec=(lx['si'], lx['do']), end=lp['end']))
        xd, pd = UX.data[lx['si']], UP.data[lp['si']]
        sid = PD.sections[lp['si']].id
        for (key, xo), (_, po) in zip(lx['words'], lp['words']):
            xw, pw = xd[xo:xo + 4], pd[po:po + 4]
            if key == 'e+%02x' % ENTRY_OBJ:
                xr, xid, onm = remap_obj(xw, xn, pn, pnr)
                if xr is None:
                    res['rows'].append((lp['si'], sid, po, b['uid'], nm, key, xw, pw, None, 'UNEXPECTED',
                                        'object %d (%s) has no PC id' % (xid, onm))); continue
                xw = xr
            st, want, note = judge(key, xw, pw, table)
            res['rows'].append((lp['si'], sid, po, b['uid'], nm, key, xw, pw, want, st, note))
        # tail: words after the spawn list up to the next intro data / 0x420 (not judged; counted for the report)
        for q in range(4, 0x420 - (lp['end'] - lp['do']), 4):
            po, xo = lp['end'] - 4 + q, lx['end'] - 4 + q
            if po + 4 > len(pd) or xo + 4 > len(xd): break
            if po in UP.ptr[lp['si']] or xo in UX.ptr[lx['si']]: res['tail']['relocated'] += 1; continue
            od = orders_of(xd[xo:xo + 4], pd[po:po + 4])
            res['tail']['other value' if not od else ('symmetric' if len(od) == len(ORDERS) else
                                                       ('u32' if 'u32' in od else 'not u32: ' + '/'.join(sorted(od))))] += 1
    return res


def fix_drm(XD, raw, rel='unit', pack='pack11'):
    """-> (new raw or None, changes [(section index, offset, old, new, section id, key, uid)], plan info); SystemExit on
    an UNEXPECTED word. The written bytes are proven (verify)."""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, rel, pack)
    if info['skip']: return None, [], info
    bad = [r for r in info['rows'] if r[9] == 'UNEXPECTED']
    if bad:
        raise SystemExit('genintro %s: %d UNEXPECTED word(s) (no byte order of the Xbox word): %s' % (rel, len(bad), ', '.join(
            'intro %d %s +%#x Xbox %s PC %s %s' % (r[3], r[5], r[2], r[6].hex(), r[7].hex(), r[10]) for r in bad[:10])))
    todo = [r for r in info['rows'] if r[9].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    secs = {}
    for si, sid, o, uid, nm, key, xw, pw, want, st, note in todo:
        b = secs.setdefault(si, bytearray(PD.sections[si].data))
        assert bytes(b[o:o + 4]) == pw
        b[o:o + 4] = want
        changes.append((si, o, pw, want, sid, key, uid))
    for si, b in secs.items(): PD.sections[si].data = bytes(b)
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, rel, pack)
    return new, changes, info


def verify(raw, new, changes, XD, rel='unit', pack='pack11'):
    """assert: only the planned bytes differ, headers / relocations / names identical, re-plan finds 0 words"""
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, *_ in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B, rel, pack)['rows'] if r[9] not in ('ok', 'UNJUDGED')]
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


# ---------------------------------------------------------------- retail proof
def base_units():
    p = os.path.join(LISTS, 'pc_unitlist.txt')
    return [l.strip().split(chr(92))[-1] for l in open(p, encoding='utf8') if chr(92) in l]


def proof(report=None):
    import locals as LC
    from archive import Archive
    from names import crc
    arch = {s: Archive(LC.SRC[s][0], LC.SRC[s][1]) for s in BASE_NAMES if os.path.exists(LC.SRC[s][0])}
    sets = {}                       # key -> intersection of explaining orders
    seen = collections.Counter()    # key -> words
    informative = collections.Counter()
    contra = []; wrong = []; pairs = []; ident = collections.Counter(); other_layout = collections.Counter()
    gens = 0; words = 0
    tails = collections.Counter(); values = collections.defaultdict(collections.Counter)
    for u in base_units():
        recs = {}
        for s, A in arch.items():
            pre = LC.SRC[s][2]
            r = [x for x in A.find(crc(pre + chr(92) + u + '.drm')) if x['spec'] == 0xffffffff]
            if r: recs[s] = r[0]
        pcs = [s for s in ('pcbig', 'pcpatch') if s in recs]; xbs = [s for s in ('xbase', 'xbase2', 'tu') if s in recs]
        if not pcs or not xbs: continue
        cache = {}

        def get(s):
            if s not in cache:
                D = DW.read(arch[s].read(recs[s]), LC.SRC[s][1]); cache[s] = (D, Unit(D, LC.SRC[s][1]))
            return cache[s]
        D0, U0 = get(pcs[0])
        if U0.L is None or not any('generator' in names_for(pcs[0]).get(i['obj'], '').lower() for i in U0.intros):
            continue
        for p in pcs:
            for x in xbs:
                PD, UP = get(p); XD, UX = get(x)
                pn, xn = names_for(p), names_for(x)
                # identification: every intro whose data has the layout, by object name (PC side)
                for it in UP.intros:
                    lo, _ = layout(UP, it)
                    if lo is not None: ident[pn.get(it['obj'], '?')] += 1
                prs = pair_intros(UX, UP, xn, pn)
                pnr = {v: k for k, v in pn.items()}
                ng = 0
                for a, b in prs:
                    lx, wx = layout(UX, a); lp, wp = layout(UP, b)
                    nm = pn.get(b['obj'], '?')
                    if lx is None or lp is None:
                        other_layout['%s: Xbox %s / PC %s' % (nm, wx or 'layout', wp or 'layout')] += 1; continue
                    ng += 1
                    xd, pd = UX.data[lx['si']], UP.data[lp['si']]
                    for (key, xo), (_, po) in zip(lx['words'], lp['words']):
                        xw, pw = xd[xo:xo + 4], pd[po:po + 4]
                        if key == 'e+%02x' % ENTRY_OBJ:
                            xr, xid, onm = remap_obj(xw, xn, pn, pnr)
                            if xr is None:
                                contra.append((u, p, x, nm, key, xw.hex(), pw.hex(), 'object %d %s no PC id' % (xid, onm)))
                                continue
                            xw = xr
                        od = orders_of(xw, pw)
                        seen[key] += 1; words += 1
                        if key in VALUE_KEYS: values[key][xw.hex()] += 1
                        if len(od) < len(ORDERS): informative[key] += 1
                        sets[key] = sets.get(key, frozenset(ORDERS)) & od
                        if not od: contra.append((u, p, x, nm, key, xw.hex(), pw.hex(), 'no byte order'))
                        st, want, note = judge(key, xw, pw)
                        if st != 'ok': wrong.append((u, p, x, nm, key, xw.hex(), pw.hex(), st, note))
                gens += ng
                if ng: tails.update(plan(XD, PD, u, x, p, UX=UX, UP=UP)['tail'])
                pairs.append('%s %s/%s: %d generators paired, %d intros' % (u, p, x, ng, len(UP.intros)))
                print(pairs[-1], flush=True)
        cache.clear()
    derived = {k: v for k, v in sets.items()}
    diff = sorted(k for k in set(derived) | set(TYPES) if derived.get(k) != TYPES.get(k))
    print('identification: intro data with the pool generator layout, by object name: %s' % dict(ident))
    print('generator-named intros without the layout: %s' % dict(other_layout))
    non_gen = sum(c for n, c in ident.items() if 'generator' not in n.lower())
    for k in sorted(set(derived) | set(TYPES)):
        print('  %-5s words %5d informative %5d  derived %-30s table %-30s %s' % (
            k, seen[k], informative[k], ' '.join(sorted(derived.get(k, ()))) or '-', ' '.join(sorted(TYPES.get(k, ()))) or '-',
            'ok' if derived.get(k) == TYPES.get(k) else 'DIFFERS'))
    for k in VALUE_KEYS: print('  Xbox values %-5s %s' % (k, dict(values[k].most_common(10))))
    print('tail words after the spawn list (not judged, for comparison with a DLC scan --tail): %s' % dict(tails))
    for c in contra[:30]: print('  CONTRADICTS %s %s/%s %s %s Xbox %s PC %s (%s)' % c)
    for w in wrong[:30]: print('  RETAIL WORD NOT OK %s %s/%s %s %s Xbox %s PC %s %s %s' % w)
    got = {'contradicting': len(contra), 'retail_wrong': len(wrong), 'layout_non_generator': non_gen}
    ok = got == PROOF_EXPECT and not diff and gens > 0
    print('pairs %d, generators %d, words %d; table differences %s' % (len(pairs), gens, words, diff or 'none'))
    print('rule typed generator intro data: %s  %s (expected %s)' % ('PROVEN' if ok else 'FAILED', got, PROOF_EXPECT))
    if report:
        json.dump(dict(result='PROVEN' if ok else 'FAILED', counts=got, pairs=pairs, generators=gens, words=words,
                       identification=dict(ident), other_layout=dict(other_layout),
                       table={k: sorted(v) for k, v in derived.items()}, seen=dict(seen), informative=dict(informative),
                       contradicting=contra, retail_wrong=wrong, tail=dict(tails),
                       values={k: dict(values[k]) for k in VALUE_KEYS}), open(report, 'w', encoding='utf-8'), indent=1)
    return 0 if ok else 1


# ---------------------------------------------------------------- files
def file_list(spec):
    import soundplex_sequence_fix as SQ
    return SQ.file_list(spec)


def has_generators(PD):
    UP = Unit(PD, 'le')
    if UP.L is None: return None
    pn = names_for('pcdlc')
    return UP if any('generator' in pn.get(i['obj'], '').lower() for i in UP.intros) else None


def check_file(path, pack=None):
    """-> (status, plan info or None, Xbox Drm or None, pack label)"""
    import soundplex_sequence_fix as SQ
    PD = DW.read(open(path, 'rb').read(), 'le')
    UP = has_generators(PD)
    if UP is None: return 'no generator intros', None, None, None
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None, None
    best = None
    for XD, pk in cands:
        pk = pk.split('.')[0]                               # 'pack11.000' -> 'pack11' (object list label)
        info = plan(XD, PD, path, pk, UP=UP)
        score = (info['skip'] is None, len(info['gens']), -sum(1 for r in info['rows'] if r[9] != 'ok'))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    _, XD, pk, info = best
    return 'ok (%s)' % pk, info, XD, pk


def row_text(r):
    si, sid, o, uid, nm, key, xw, pw, want, st, note = r
    return 'intro %d %s sec %d (id %d) +%#07x %-5s Xbox %s PC %s rule %s %s%s' % (
        uid, nm, si, sid, o, key, xw.hex(), pw.hex(), want.hex() if want else '?',
        'ok' if st == 'ok' else ('WRONG (PC = %s)' % st[4:] if st.startswith('fix:') else st), (' [%s]' % note) if note else '')


def scan(paths, show_all, pack=None, tail=False):
    tot = collections.Counter(); lines = []; files = []

    def say(t):
        print(t, flush=True); lines.append(t)
    for path in paths:
        st, info, XD, pk = check_file(path, pack)
        if info is None:
            tot['files without generators'] += 1; continue
        tot['files'] += 1
        if info['skip']: say('%s: %s; %s' % (path, st, info['skip'])); tot['skipped'] += 1; continue
        bad = [r for r in info['rows'] if r[9] != 'ok']
        tot['generators'] += len(info['gens']); tot['words'] += len(info['rows'])
        tot['wrong'] += sum(1 for r in bad if r[9].startswith('fix:'))
        tot['unexpected'] += sum(1 for r in bad if r[9] == 'UNEXPECTED')
        tot['unjudged'] += sum(1 for r in bad if r[9] == 'UNJUDGED')
        tot['other layout'] += len(info['other'])
        tot['layout mismatch'] += len(info['mismatch'])
        if any(r[9].startswith('fix:') or r[9] == 'UNEXPECTED' for r in bad): files.append(path.replace(chr(92), '/'))
        wrong_gens = sorted({r[3] for r in bad if r[9].startswith('fix:')})
        say('%s: %s, %d generators (%s), %d words, %d not ok; wrong generators %s' % (
            path, st, len(info['gens']), ', '.join('%d %s' % (g['uid'], g['name']) for g in info['gens']),
            len(info['rows']), len(bad), wrong_gens or '-'))
        for o in info['other']: say('   not the pool generator layout (left alone): intro %d %s Xbox %s PC %s' % o)
        for r in (info['rows'] if show_all else bad): say('   ' + row_text(r))
        if tail: say('   tail words after the spawn list (not judged): %s' % dict(info['tail']))
    # a file with generator-named intros that cannot be planned (no Xbox source / no pairing) fails the gate too
    res = 'FAIL' if tot['wrong'] or tot['unexpected'] or tot['skipped'] or tot['layout mismatch'] else 'ok'
    say('TOTAL %s' % dict(tot)); say('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, only, pack):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))          # log + md5.tsv next to mods\, never inside it
    log = open(os.path.join(top, 'generator_intro_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath\tsource_md5']
    for path in file_list(spec):
        name = os.path.basename(path)
        if only and name not in only: continue
        st, info, XD, pk = check_file(path, pack)
        if info is None or info['skip'] or not any(r[9].startswith('fix:') for r in info['rows']): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw, path, pk)
        if new is None: continue
        for k, q, pw, want, sid, key, uid in changes:
            line = '%s intro %d %s: section %d (id %d) +%#07x %s -> %s' % (name, uid, key, k, sid, q, pw.hex(), want.hex())
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        ndiff = verify(raw, open(dst, 'rb').read(), changes, XD, path, pk)
        h = hashlib.md5(new).hexdigest(); h0 = hashlib.md5(raw).hexdigest()
        line = '%s (%s): %d words, %d bytes differ from %s (md5 %s; all inside the planned words), headers + ' \
               'relocations identical, re-plan 0; new md5 %s sha256 %s' % (name, pk, len(changes), ndiff, path, h0, h,
                                                                       hashlib.sha256(new).hexdigest())
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s\t%s' % (h, name, h0))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def verify_pair(old, new, pack):
    import soundplex_sequence_fix as SQ
    raw, nraw = open(old, 'rb').read(), open(new, 'rb').read()
    st, info, XD, pk = check_file(old, pack)
    if info is None: print('%s: %s' % (old, st)); return 1
    changes = [(r[0], r[2], r[7], r[8], r[1], r[5], r[3]) for r in info['rows'] if r[9].startswith('fix:')]
    try:
        n = verify(raw, nraw, changes, XD, old, pk)
    except AssertionError as e:
        print('verify %s -> %s: FAILED %s' % (old, new, e)); return 1
    print('verify %s -> %s: ok, %d planned words, %d bytes differ, re-plan 0' % (old, new, len(changes), n))
    return 0


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    show_all = '--all' in a; tail = '--tail' in a
    a = [x for x in a if x not in ('--all', '--tail')]
    if a[0] == 'proof': return proof(report)
    if a[0] == 'scan' and len(a) >= 2:
        r, tot, files, lines = scan(file_list(a[1]), show_all, pack, tail)
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
