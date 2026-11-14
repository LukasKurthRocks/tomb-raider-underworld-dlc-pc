"""Learn / apply / evaluate the Xbox->PC word permutation per semantic label of the typed Script walker
(script_conv.Walk).  Table = {label: Counter(class -> #words where the class reproduces the PC word)}; lookup
falls back from the full label to shorter prefixes, then to the walker's prior kind.

Usage: tools/venv/bin/python -I tools/script_learn.py [eval|save]
  eval : 2-fold held-out (split by Script name symbol, so all copies/versions of one script are in one fold)
         + in-sample, per-pair exactness and residual categories
  save : train on all pairs -> work/script/script_table.pkl
"""
import sys, os, struct, collections, pickle, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import generic_learn as G
import script_conv as S
WS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'script')
TABLE = os.path.join(WS, 'script_table.pkl')

CLASSES = ('s32', 's16', 'raw', 'b2s16', 's16b2', 'id16a:100', 'id16b:100', 'id16ab:100', 'id32:8', 'syma_r', 'r_symb',
           # other id spaces referenced from script data (native init blocks, code operands): DTP ids, object ids (u16),
           # unit ids (u16), intro unique ids (u32, generic_type0 113), localisation string ids (101, tools/locals.py)
           'id32:7', 'id16a:11', 'id16a:110', 'id32:113', 'id16a:101', 'id32:101', 'id32:6', 'id32:114')
PREF = {c: i for i, c in enumerate(CLASSES)}
# P4.8 (2026-11-14, PW.1 / Q124, workspace docs Befund-PW1-Wasserhoehe-1311.md, Befund-P48-P49-Pipeline-1411.md):
# member init words of base type 10 with the userType Symbol 4261 (Xbox; PC 4697) are an instance / marker reference
# {u16 intro id, u16 0} (dungeon water scripts 20415 / 20774: target markers of SetWaterDepthToMarkerZVal). The learned
# table has 134 base words of that label and NONE informative for its classes (the PC intro ids are renumbered, no
# u16 class with the intro map existed), so the label fell back to ('init', 10, 1, 0) = id16a:100 and the intro ids
# were converted as Symbols (9622 -> 12154 ...): the markers were not found, the dungeon water never lowered. Now:
# the u16 stays in place through the intro id map (ids(113, x): identity for DLC intros unless renumbered, e.g.
# 9395 -> 29395 = generic_type0.intro_new), the second u16 in place. Proof on the base pairs and the gate:
# tools/instref_gate.py (proof / check). TRUDLC_SCRIPT_INSTREF=off restores the learned classes (A/B runs).
INSTREF_UT = 4261           # Xbox userType Symbol of the reference (DlcIds.sym(4261) = PC 4697)
INSTREF_CLASS = 'intro16a'


def instref(lab, xw=None):
    """True for a walker label ('init', 10, depth, 0, INSTREF_UT): the FIRST word of the init block, any depth (the
    block goes on with other fields: base words at k = 12 are u32, l7_yggdrasil_end 11117 +0x190 0000000f -> 0f000000).
    With the Xbox word: only when its high u16 is not 0 (no intro has id 0; DLC 1 20774 +0x130 = 00000002 is a k = 12
    word of the block at +0x124 that is also a pointer target, so the walker starts a block there - left to the table)"""
    return isinstance(lab, tuple) and len(lab) >= 5 and lab[0] == 'init' and lab[1] == 10 and lab[3] == 0 \
        and lab[4] == INSTREF_UT and (xw is None or xw[:2] != b'\0\0')

def apply_word(xw, c, ids):
    if c == INSTREF_CLASS:      # {u16 intro / marker id, u16}: intro id map (generic_type0 INTRO = 113), u16 in place
        a, b = struct.unpack('>HH', xw)
        return struct.pack('<HH', ids(113, a) & 0xffff if a not in (0, 0xffff) else a, b)
    if c == 'syma_r':
        a, = struct.unpack('>H', xw[:2])
        return struct.pack('<H', ids(G.SYM, a) & 0xffff if a not in (0, 0xffff) else a) + xw[2:4]
    if c == 'r_symb':
        b, = struct.unpack('>H', xw[2:4])
        return xw[0:2] + struct.pack('<H', ids(G.SYM, b) & 0xffff if b not in (0, 0xffff) else b)
    if c.startswith('id16'):
        which, t = c[4:].split(':'); t = int(t)
        a, b = struct.unpack('>HH', xw)
        if 'a' in which and a not in (0, 0xffff): a = ids(t, a) & 0xffff
        if 'b' in which and b not in (0, 0xffff): b = ids(t, b) & 0xffff
        return struct.pack('<HH', a, b)
    return G.apply_word(xw, c, ids)

def _shape(xw):
    import generic_type0
    return generic_type0.shape(xw)

def prefixes(lab):
    for k in range(len(lab), 0, -1):
        yield lab[:k]

class Table:
    def __init__(self, v=None, prior=None):
        self.v = v if v is not None else collections.defaultdict(collections.Counter)
        self.prior = prior if prior is not None else {}
        self._best = {}
    def add(self, lab, cs):
        for p in prefixes(lab):
            c = self.v[p]
            for x in cs: c[x] += 1
            c['#'] += 1
    def best(self, lab):
        r = self._best.get(lab)
        if r is None:
            r = self._best[lab] = self._compute(lab)
        return r
    def _compute(self, lab):
        for p in prefixes(lab):
            c = self.v.get(p)
            if c and len(c) > 1:
                pri = self.prior.get(lab) or self.prior.get(p)
                return max((k for k in c if k != '#'), key=lambda k: (c[k], k == pri, -PREF.get(k, 99)))
        return self.prior.get(lab, 's32')
    def dump(self):
        return dict(v={k: dict(c) for k, c in self.v.items()}, prior=dict(self.prior))
    @classmethod
    def load(cls, path=TABLE):
        d = pickle.load(open(path, 'rb'))
        return cls(collections.defaultdict(collections.Counter, {k: collections.Counter(c) for k, c in d['v'].items()}), d['prior'])

def train(pairs, ids, T=None):
    T = T or Table()
    for r in pairs:
        rel = R.parse(r['xr'], 'be')
        W = S.walk(r['xd'], rel)
        for k, v in W.prior.items(): T.prior.setdefault(k, v)
        skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
        xd, pd = r['xd'], r['pd']
        for w, lab in W.lab.items():
            if w in skip: continue
            xw, pw = xd[w:w + 4], pd[w:w + 4]
            outs = {c: apply_word(xw, c, ids) for c in CLASSES}
            if len(set(outs.values())) == 1: continue           # no information
            cs = [c for c, o in outs.items() if o == pw]
            T.add(lab + ('~' + _shape(xw),), cs)        # most specific level: value shape (prefixes = plain label)
    return T

PATH_BT = (0xa, 0xb)        # base types whose member hands a ScriptType on to the next path element (tru.exe 0x4c8420)


def path_words(xd, W, e='be'):
    """Symbol path words {u16 member, u16 property} in the init data of one script (Q58, 2026-11-11): an init leaf
    (members / args / locals, script_init_from_pc.leaves) whose high half names a member of this script of base type
    0xa / 0xb and whose low half is neither 0 nor 0xffff. tru.exe resolves such paths BY NAME, two u16 Symbols in
    memory order (0x4d08e0: word [path + 2 * i]); proof on the re-authored base pairs generalbank + g_pda (Xbox <-> PC,
    members by script_member_pairs.align, work/q58_names_1111/base_path_proof.py): 1 846 path words, the PC keeps both
    halves in memory order in 1 844 (2 = the PC re-pointed 3347's path to another member), the property half = DlcIds.sym
    in 1 846 / 1 846. The learned per-label classes made 296 of 356 DLC path words s32 (byte-reversed, names unmapped:
    g_pda 3347 / 3360 / 3361 / ..., generalbank 72 copy in dlc1_health_pack; tools/script_path_check.py). -> set of
    word offsets, converted as id16ab:100. TRUDLC_SCRIPT_PATHS=off restores the learned classes (A/B runs)."""
    import script_init_from_pc as SIP
    E = '>' if e == 'be' else '<'
    obj = set()
    for nm, t, n, sz in W.arrays:
        if nm == 'members' and sz == 20:
            for k in range(n):
                a = t + 20 * k
                if a + 16 <= len(xd) and struct.unpack_from(E + 'I', xd, a)[0] & 0xf in PATH_BT:
                    obj.add(struct.unpack_from(E + 'H', xd, a + 14)[0])
    obj.discard(0); obj.discard(0xffff)
    out = set()
    if not obj: return out
    for nm, t, n, sz in W.arrays:
        if nm not in ('members', 'args', 'locals') or sz != 20: continue
        for k in range(n):
            ia = W.it.get(t + 20 * k + 16)
            if ia is None: continue
            for _, o in SIP.leaves(W, W.it, ia):
                if o + 4 > len(xd): continue
                a, b = struct.unpack_from(E + 'HH', xd, o)
                if a in obj and b not in (0, 0xffff): out.add(o)
    return out


def convert(xd, rel, ids, T, fallback=None, W=None):
    """xd: Xbox section data, rel: parsed BE reloc. fallback(w, xw) -> class for words the walker did not label.
    Symbol path words (path_words) are converted as two Symbols (id16ab:100) whatever the label table says."""
    W = W or S.walk(xd, rel)
    out = bytearray(xd)
    skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
    paths = path_words(xd, W) if os.environ.get('TRUDLC_SCRIPT_PATHS', '').lower() != 'off' else set()
    iref = os.environ.get('TRUDLC_SCRIPT_INSTREF', '').lower() != 'off'      # P4.8 (2026-11-14), see INSTREF_UT
    for w in range(0, len(xd) // 4 * 4, 4):
        if w in skip: continue
        xw = xd[w:w + 4]
        lab = W.lab.get(w)
        if w in paths: c = 'id16ab:100'
        elif iref and instref(lab, xw): c = INSTREF_CLASS
        elif lab is not None: c = T.best(lab + ('~' + _shape(xw),))
        elif fallback is not None: c = fallback(w, xw)
        else: c = 'raw' if G.is_text(xw) and xw != xw[::-1] else 's32'
        out[w:w + 4] = apply_word(xw, c, ids)
    for o in rel.pointer_offsets():
        out[o:o + 4] = xd[o:o + 4][::-1]
    for o, t in rel.id_offsets().items():
        v, = struct.unpack_from('>I', xd, o)
        struct.pack_into('<I', out, o, ids(t, v) if v not in (0, 0xffffffff) else v)
    return bytes(out), W

_TAB = None
def table():
    global _TAB
    if _TAB is None: _TAB = Table.load(TABLE)
    return _TAB

# ------------------------------------------------------------------------------- evaluation
def name_key(r):
    return struct.unpack_from('>H', r['xd'], 8)[0] if len(r['xd']) >= 12 else 0

def folds(pairs):
    A = [r for r in pairs if zlib.crc32(b'%d' % name_key(r)) & 1 == 0]
    B = [r for r in pairs if zlib.crc32(b'%d' % name_key(r)) & 1 == 1]
    return A, B

def evaluate(pairs, ids, T, st=None, detail=None):
    st = st if st is not None else collections.Counter()
    for r in pairs:
        rel = R.parse(r['xr'], 'be')
        d, W = convert(r['xd'], rel, ids, T)
        st['n'] += 1
        pd = r['pd']
        if d == pd: st['exact'] += 1; continue
        bad = [w for w in range(0, len(d), 4) if d[w:w + 4] != pd[w:w + 4]]
        st['badwords'] += len(bad)
        # (a) dependency array order: PC order is build-order dependent (not derivable), runtime-irrelevant
        deps = [(t, n) for nm_, t, n, sz in W.arrays if nm_ == 'deps']
        dset = {t + 4 * k for t, n in deps for k in range(n)}
        nd = [w for w in bad if w not in dset]
        if not nd and all(sorted(d[t + 4 * k:t + 4 * k + 4] for k in range(n)) == sorted(pd[t + 4 * k:t + 4 * k + 4] for k in range(n)) for t, n in deps):
            st['exact_mod_deps'] += 1
        else:
            # (b) PC content differs: some wrong word that NO class reproduces (re-authored script / map gap)
            unexpl = sum(1 for w in nd if w + 4 <= len(d) and all(apply_word(r['xd'][w:w + 4], c, ids) != pd[w:w + 4] for c in CLASSES))
            st['pc_differs' if unexpl else 'explainable_wrong'] += 1
        labs = collections.Counter(W.lab.get(w, ('unk',))[:2] for w in bad)
        for l, n in labs.items(): st['lab', l] += n
        if detail is not None: detail.append((r['name'], r['xid'], len(bad), labs.most_common(3)))
    return st

def report(st, title):
    n = st['n']
    print('-- %s: %d pairs, exact %d = %.2f%%, exact-mod-dependency-order %d = %.2f%%, wrong words %d' % (title, n, st['exact'],
          100. * st['exact'] / max(1, n), st['exact'] + st['exact_mod_deps'], 100. * (st['exact'] + st['exact_mod_deps']) / max(1, n), st['badwords']))
    conv = n - st['pc_differs']
    print('   PC content differs (a wrong word no class reproduces): %d ; over the convertible rest (%d): exact-mod-deps %.2f%%, '
          'explainable wrong %d' % (st['pc_differs'], conv, 100. * (st['exact'] + st['exact_mod_deps']) / max(1, conv), st['explainable_wrong']))
    for k, v in sorted(((k, v) for k, v in st.items() if isinstance(k, tuple)), key=lambda kv: -kv[1])[:25]:
        print('     %-50s %d' % (k[1], v))

def load_pairs(t=8):
    return pickle.load(open(os.path.join(WS, 'pairs_%d.pkl' % t), 'rb'))

if __name__ == '__main__' and sys.argv[1:2] != ['symmap']:
    import dlc_generic as DG
    ids = DG.DlcIds()
    P = load_pairs(8)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'eval'
    if mode == 'eval':
        A, B = folds(P)
        TA = train(A, ids); TB = train(B, ids)
        st = evaluate(B, ids, TA); evaluate(A, ids, TB, st)
        report(st, 'HELD-OUT (2-fold by script name)')
    T = train(P, ids)
    det = []
    report(evaluate(P, ids, T, detail=det), 'IN-SAMPLE')
    pickle.dump(det, open(os.path.join(WS, 'detail.pkl'), 'wb'))
    if mode in ('save', 'eval'):
        pickle.dump(T.dump(), open(TABLE, 'wb'))

# ------------------------------------------------------------------------------- symbol map
SYM_FIELDS_AB = (('proto', 8), ('state',), ('root', 8))

def symbol_votes(pairs):
    """(xsym -> pcsym) votes from walker fields that are certainly Symbols (prototype/state/script names,
    DataMember names with an equal u16 offset, DataType userType with an equal pad half)."""
    v = collections.defaultdict(collections.Counter)
    for r in pairs:
        rel = R.parse(r['xr'], 'be'); W = S.walk(r['xd'], rel)
        xd, pd = r['xd'], r['pd']
        for w, lab in W.lab.items():
            xa, xb = struct.unpack_from('>HH', xd, w); pa, pb = struct.unpack_from('<HH', pd, w)
            h = lab[0]
            if lab in SYM_FIELDS_AB:
                v[xa][pa] += 1; v[xb][pb] += 1
            elif h == 'dm.off' or lab == ('root', 0x4c):
                if xa == pa: v[xb][pb] += 1
            elif h == 'dt.user':
                if xb == pb or xb == ((pb & 0xff) << 8 | pb >> 8): v[xa][pa] += 1
    v.pop(0, None); v.pop(0xffff, None)
    return v

def build_symmap(pairs, old):
    """script-field votes are authoritative (they disagree with the old raw-vote bootstrap map on 125 low
    symbols, e.g. 26->26 not 26->48); old entries are kept for symbols the scripts never vote on, unless they
    would collide with a script-voted PC symbol."""
    v = symbol_votes(pairs)
    m = {}
    for x, c in v.items():
        (p, n), = c.most_common(1)
        if n >= 0.8 * sum(c.values()): m[x] = p
    inv = collections.Counter(m.values())
    m = {x: p for x, p in m.items() if inv[p] == 1}
    used = set(m.values()); kept = 0
    for x, p in old.items():
        if x not in m and p not in used: m[x] = p; used.add(p); kept += 1
    return m, dict(script_voted=len(m) - kept, kept_old=kept, old=len(old))

if __name__ == '__main__' and sys.argv[1:2] == ['symmap']:
    import json, shutil
    from generic_ids import section_matches
    path = os.path.join(G.W, 'idmap.json')
    bak = os.path.join(G.W, 'idmap_pre_script.json')
    if not os.path.exists(bak): shutil.copy(path, bak)
    d = json.load(open(path))                    # CURRENT map (other tools add entries too); only key 100 is touched
    old = {int(a): b for a, b in d['100'].items()}
    m, info = build_symmap(load_pairs(8), old)
    d['100'] = {str(a): b for a, b in sorted(m.items())}
    json.dump(d, open(path, 'w'))
    print('symbol map', info, 'total', len(m))
