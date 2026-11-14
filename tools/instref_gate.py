r"""Intro / marker reference gate for script init words (P4.8, 2026-11-14; from work/pw1_1311/pw1_instref_scan.py,
workspace docs Befund-PW1-Wasserhoehe-1311.md / Befund-P48-P49-Pipeline-1411.md). Read only.

Why: the dungeon water scripts of DLC 1 (20415 / 20774, dlc_dungeon + three neighbour units) name their target markers
in member init words {u16 intro id, u16 0} (walker label ('init', 10, depth, k, 4697): base type 10, userType 4697).
The walker labels the Xbox section, so the label carries the Xbox userType Symbol 4261 (= PC 4697). The learned script
table had no informative entry for that label and fell back to ('init', 10, 1, 0) = id16a:100, so the intro ids were
converted as Symbols (9622 -> 12154 ...). SetWaterDepthToMarkerZVal then finds no marker and the water stays at the
top of the volume: the main hall is flooded at the start, the land enemies drown (Q124). The converter keeps these
words as u16 through the intro id map since 2026-11-14 (tools/script_learn.py INSTREF_UT / instref()); this tool
proves the rule on the base pairs and gates the trees.

  proof   every base script pair word (work/script/pairs_8.pkl) labelled ('init', 10, depth, 0, 4261) with a non-zero
          high u16: the rule's word = the PC word (base intro map); exit 1 on a contradiction or another pinned count
  check   for every DRM of the tree with an Xbox twin (convert_dlc.raw_dlc; --pack PACK = that pack first):
          * intro / marker ids of every unit DRM (unit DTP intros +0x58 and the marker list root +0x1c / +0x20, record
            +0x58), Xbox and PC, paired record by record (same unit, same position) -> {Xbox id: PC ids}
          * every script (type 8) of the Xbox source with a PC twin (DlcIds type-8 id, same size): each first init word
            with the label base type 10 / userType USERTYPE whose Xbox high u16 is an intro or marker id of a unit of the
            tree must hold, on PC, the PC id of that same intro / marker (first u16, little-endian) and the Xbox second
            half. Values that are no intro / marker id of a unit of the tree (DLC 1: script 22559 9644 .. 9656,
            23212 9730 - in no intro / marker list) are counted 'not_intro', not judged.
          Exit 1 on a word that does not resolve, a missing tree folder, no DRM with an Xbox twin, or (--expect-refs)
          no resolving reference word at all; else 0.
  fix     rewrite the reference words of already converted DRMs with the converter's class (offline proofs / A-B)
Usage (from the repository root):
  ../bin/pyt -t 1800 tools/instref_gate.py proof [--report R.json]
  ../bin/pyt -t 1800 tools/instref_gate.py check TREE[,TREE..] [--pack PACK] [--usertype 4261] [--report R.json] [--expect-refs]
        TREE,TREE: the first tree that holds a file wins (layer stack, as the other gates)
  ../bin/pyt -t 1800 tools/instref_gate.py fix OUTDIR SRCDIR[,SRCDIR..] [--pack PACK] name.drm [...]
Library: unit_ids(D, e), intro_pairs(trees, raw_dlc), ref_words(XD, PD, ids, usertype), judge(xw, pw, pairs).
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

USERTYPE = 4261      # Xbox userType Symbol of the instance / marker reference {u16 intro id, u16 0} (PC 4697; PW.1, Q124)
USERTYPE_PC = 4697
# pinned base proof (2026-11-14): script pairs work/script/pairs_8.pkl, first words of the init blocks labelled
# ('init', 10, depth, 0, 4261): depth 0 = 134 sentinels beebbeeb (every order the same), depth 1 = 134 intro
# references, rule = PC word 268 / 268, the learned fallback id16a:100 wrong 134 / 134; the later block words (k > 0,
# 277, e.g. u32 at k = 12) are not ruled
PROOF_EXPECT = {'pairs': 17115, 'words': 268, 'words_depth0': 134, 'intro_unmapped_depth0': 134, 'ok': 268,
                'learned_id32:114_ok': 134, 'words_depth1': 134, 'learned_id16a:100_wrong': 134,
                'block_words_k_gt_0_not_ruled': 277}


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def unit_ids(D, e):
    """([intro ids in record order], [marker ids in record order]) of a unit DRM (DW.read result), or None"""
    import unit_ids as U
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    try:
        L = U.level_info(secs, e)
    except Exception:
        return None
    if not L: return None
    E = '<' if e == 'le' else '>'
    intro = [struct.unpack_from(E + 'I', secs[si]['data'], o + 0x58)[0] for si, o in L['intros']]
    mark = []
    ext = {so: (si, do) for si, so, do in R.parse(secs[0]['reloc'], e).external}
    if 0x74 in ext:
        di, _ = ext[0x74]
        d = secs[di]['data']; ri = dict(R.parse(secs[di]['reloc'], e).internal)
        if d is not None and len(d) >= 0x24:
            n = struct.unpack_from(E + 'I', d, 0x1c)[0]; t = ri.get(0x20)
            if t is not None and n < 4096:
                mark = [struct.unpack_from(E + 'I', d, t + 0x90 * k + 0x58)[0] for k in range(n) if t + 0x90 * k + 0x5c <= len(d)]
    return intro, mark


def tree_names(trees):
    return sorted({os.path.relpath(os.path.join(r, f), d).replace('\\', '/') for d in trees for r, _, fs in os.walk(d)
                   for f in fs if f.endswith('.drm')})


def tree_path(trees, nm):
    return next((os.path.join(d, nm) for d in trees if os.path.isfile(os.path.join(d, nm))), None)


def xbox_raw(raw_dlc, nm):
    raw, _ = raw_dlc(nm.replace('/', '\\'))
    if raw is None: raw, _ = raw_dlc(os.path.basename(nm))
    return raw


def load_pair(trees, nm, raw_dlc):
    raw = xbox_raw(raw_dlc, nm)
    if raw is None: return None, None
    return DW.read(raw, 'be'), DW.read(open(tree_path(trees, nm), 'rb').read(), 'le')


def intro_pairs(trees, raw_dlc, st=None):
    """{Xbox intro / marker id: set(PC ids)}, set of PC ids, per-unit notes; units = tree DRMs with a Level"""
    st = st if st is not None else collections.Counter()
    pm = collections.defaultdict(set); pc_all = set(); notes = []
    for nm in tree_names(trees):
        XD, PD = load_pair(trees, nm, raw_dlc)
        if XD is None: continue
        ux, up = unit_ids(XD, 'be'), unit_ids(PD, 'le')
        if ux is None or up is None: continue
        st['units'] += 1
        for kind, a, b in (('intro', ux[0], up[0]), ('marker', ux[1], up[1])):
            pc_all.update(b)
            if len(a) != len(b):
                st[kind + '_count_differs'] += 1
                notes.append('%s: %s count Xbox %d PC %d - not paired' % (nm, kind, len(a), len(b))); continue
            for x, p in zip(a, b):
                pm[x].add(p); st[kind + 's'] += 1
                if x != p: st[kind + '_renumbered'] += 1
    return pm, pc_all, notes


def ref_words(XD, PD, ids, usertype=USERTYPE, st=None):
    """[(PC script id, Xbox script id, offset, label, Xbox word, PC word)] of the init words with base type 10 and
    the userType (usertype < 0: every userType, first word of a block only), Xbox script paired with its PC twin"""
    import script_conv as SC
    st = st if st is not None else collections.Counter()
    pool = {(s.type, s.id): s for s in PD.sections}
    out = []
    for s in XD.sections:
        if s.type != 8 or not s.data: continue
        p = pool.get((8, ids(8, s.id)))
        if p is None or len(p.data) != len(s.data): st['scripts_unpaired'] += 1; continue
        try:
            W = SC.walk(bytes(s.data), R.parse(bytes(s.reloc), 'be'))
        except Exception:
            st['scripts_walk_error'] += 1; continue
        st['scripts'] += 1
        for o, lab in W.lab.items():
            if not (isinstance(lab, tuple) and len(lab) >= 5 and lab[0] == 'init' and lab[1] == 10): continue
            if (usertype >= 0 and lab[4] != usertype) or lab[3] != 0: continue      # first word of the block only
            if o + 4 > len(s.data): continue
            out.append((p.id, s.id, o, lab, bytes(s.data[o:o + 4]), bytes(p.data[o:o + 4])))
    return out


def judge(xw, pw, pm):
    """'null' / 'not_intro' / 'ok' / 'wrong' for one reference word (Xbox BE, PC LE)"""
    xa, xb = struct.unpack('>HH', xw); pa, pb = struct.unpack('<HH', pw)
    if xa in (0, 0xffff): return 'null'
    if xa not in pm: return 'not_intro'
    return 'ok' if pa in {v & 0xffff for v in pm[xa]} and pb == xb else 'wrong'


def scan(trees, ids, raw_dlc, usertype, p):
    tot = collections.Counter(); bad = []
    pm, pc_all, notes = intro_pairs(trees, raw_dlc, tot)
    for n in notes: p('  note ' + n)
    for nm in tree_names(trees):
        XD, PD = load_pair(trees, nm, raw_dlc)
        if XD is None: tot['no_xbox'] += 1; continue
        tot['files'] += 1
        for pid, xid, o, lab, xw, pw in ref_words(XD, PD, ids, usertype, tot):
            tot['words'] += 1
            j = judge(xw, pw, pm)
            tot[j] += 1
            if j == 'wrong':
                xa = struct.unpack('>H', xw[:2])[0]; pa = struct.unpack('<H', pw[:2])[0]
                row = dict(file=nm, script=pid, xbox_script=xid, off=hex(o), label=list(lab), xbox=xw.hex(), pc=pw.hex(),
                           xbox_id=xa, pc_id=pa, want=sorted(pm[xa]), pc_id_exists=pa in pc_all)
                bad.append(row)
                p('  WRONG %s script %d +0x%x: Xbox %s (intro %d) PC %s (u16 %d) want %s' % (
                    nm, pid, o, xw.hex(), xa, pw.hex(), pa, sorted(pm[xa])))
    return tot, bad, notes


class _BaseIds:
    """base id maps only (Xbox base -> PC base); unmapped -> the value itself, counted"""
    def __init__(self, base): self.base = base; self.miss = collections.Counter()
    def __call__(self, t, v):
        m = self.base.get(t, {})
        if v not in m: self.miss[t] += 1
        return m.get(v, v)


def proof(p=print):
    """the converter class (script_learn INSTREF_CLASS: intro id map u16 + u16 in place) on every base script pair word
    labelled ('init', 10, *, *, USERTYPE): ok = PC word, amb = 0 / 0xffff halves (no id), contra = anything else"""
    import pickle, script_learn as SL, script_conv as SC, dlc_generic as DG
    P = SL.load_pairs(8)
    ids = _BaseIds(DG.DlcIds().base)
    got = collections.Counter(); lines = []
    for r in P:
        try:
            W = SC.walk(r['xd'], R.parse(r['xr'], 'be'))
        except Exception:
            got['walk_error'] += 1; continue
        for o, lab in W.lab.items():
            if not SL.instref(lab, r['xd'][o:o + 4]):
                if isinstance(lab, tuple) and len(lab) >= 5 and lab[:2] == ('init', 10) and lab[4] == USERTYPE:
                    got['block_words_k_gt_0_not_ruled'] += 1
                continue
            xw, pw = r['xd'][o:o + 4], r['pd'][o:o + 4]
            got['words'] += 1; got['words_depth%d' % lab[2]] += 1
            a = struct.unpack('>H', xw[:2])[0]
            if a in (0, 0xffff):
                w = SL.apply_word(xw, SL.INSTREF_CLASS, ids)
                got['null_ok' if w == pw else 'null_contra'] += 1
                if w != pw and got['null_contra'] <= 10:
                    lines.append('  NULL-CONTRA %s script %d +0x%x %s: Xbox %s PC %s rule %s' % (
                        r.get('name'), r.get('xid', 0), o, lab, xw.hex(), pw.hex(), w.hex()))
                continue
            n0 = ids.miss[113]
            w = SL.apply_word(xw, SL.INSTREF_CLASS, ids)
            if ids.miss[113] != n0:
                got['intro_unmapped_depth%d' % lab[2]] += 1
                if got['intro_unmapped_depth%d' % lab[2]] <= 3:
                    lines.append('  unmapped intro id (kept) %s script %d +0x%x %s: Xbox %s PC %s' % (
                        r.get('name'), r.get('xid', 0), o, lab, xw.hex(), pw.hex()))
            if w == pw: got['ok'] += 1
            else:
                got['contra'] += 1
                if got['contra'] <= 10:
                    lines.append('  CONTRA %s script %d +0x%x %s: Xbox %s PC %s rule %s' % (
                        r.get('name'), r.get('xid', 0), o, lab, xw.hex(), pw.hex(), w.hex()))
            # what the learned table gives (the fallback of the label before 2026-11-14)
            c = SL.Table.best(SL.table(), lab + ('~' + SL._shape(xw),))
            got['learned_%s_%s' % (c, 'ok' if SL.apply_word(xw, c, ids) == pw else 'wrong')] += 1
        got['pairs'] += 1
    return dict(got), lines


def fix_file(path, XD, ids, usertype=USERTYPE):
    """rewrite the reference words of an already converted DRM with the converter class -> (bytes, changes)"""
    import script_learn as SL
    raw_old = open(path, 'rb').read()
    D = DW.read(raw_old, 'le')
    pool = {(s.type, s.id): s for s in D.sections}
    ch = []
    for pid, xid, o, lab, xw, pw in ref_words(XD, D, ids, usertype):
        if not SL.instref(lab, xw): continue
        w = SL.apply_word(xw, SL.INSTREF_CLASS, ids)
        if w != pw:
            s = pool[(8, pid)]; b = bytearray(s.data); b[o:o + 4] = w; s.data = bytes(b)
            ch.append((pid, o, pw.hex(), w.hex()))
    data = D.write('le')
    if raw_old[:4] == b'CDRM': data = DW.cdrm_encode(data, 'le')
    return data, ch


def main(a):
    if not a or a[0] not in ('check', 'proof', 'fix'): sys.exit(__doc__)
    a = list(a)
    pack = opt(a, '--pack'); report = opt(a, '--report'); ut = opt(a, '--usertype')
    ut = USERTYPE if ut is None else int(ut)
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    if a[0] == 'proof':
        got, lines = proof()
        for l in lines: print(l)
        rc = 0 if got.get('contra', 0) == 0 and got.get('null_contra', 0) == 0 and got.get('ok') and \
            (not PROOF_EXPECT or got == PROOF_EXPECT) else 1
        if PROOF_EXPECT and got != PROOF_EXPECT: print('pinned counts differ: want %s' % PROOF_EXPECT)
        print('%s: %s' % ('ok' if rc == 0 else 'FAIL', got))
        if report: json.dump(dict(gate='instref_proof', got=got, want=PROOF_EXPECT, exit=rc), open(report, 'w'), indent=1)
        return rc
    from convert_dlc import raw_dlc
    import dlc_generic as DG
    ids = DG.DlcIds()
    if ids.sym(USERTYPE) != USERTYPE_PC:
        print('FAIL: Xbox userType Symbol %d maps to PC %d, not %d - the label constant is stale' % (
            USERTYPE, ids.sym(USERTYPE), USERTYPE_PC)); return 1
    if a[0] == 'fix':
        out, srcs = a[1], a[2].split(',')
        rc = 0
        for nm in a[3:]:
            path = tree_path(srcs, nm); raw = xbox_raw(raw_dlc, nm)
            if path is None or raw is None: print('%s: not found / no Xbox source' % nm); rc = 1; continue
            data, ch = fix_file(path, DW.read(raw, 'be'), ids, ut)
            for c in ch: print('  %s script %d +0x%x %s -> %s' % (nm, c[0], c[1], c[2], c[3]))
            op = os.path.join(out, nm); os.makedirs(os.path.dirname(op), exist_ok=True)
            open(op, 'wb').write(data)
            print('%s: %d words -> %s' % (nm, len(ch), op))
        return rc
    expect = '--expect-refs' in a
    a = [x for x in a if x != '--expect-refs']
    trees = a[1].split(',')
    miss = [t for t in trees if not os.path.isdir(t)]
    if miss: print('FAIL: tree folder(s) not found: %s' % miss); return 1
    tot, rows, notes = scan(trees, ids, raw_dlc, ut, print)
    rc = 1 if tot['wrong'] or (expect and not tot['ok']) or not tot['files'] else 0
    print('%s: %s %s' % ('ok' if rc == 0 else 'FAIL', ','.join(trees), dict(tot)))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(gate='instref', trees=trees, pack=pack, usertype=ut, totals=dict(tot), notes=notes, wrong=rows,
                       exit=rc), open(report, 'w', encoding='utf-8'), indent=1)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
