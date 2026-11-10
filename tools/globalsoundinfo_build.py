"""globalsoundinfo.drm for the DLC port from the player's PC original + recorded title-update knowledge (no kit, no
Xbox data on the player's side).

What the title update changed (learned from the Xbox retail <-> TU pair, docs/data/globalsoundinfo_tu.json):
  The file holds the game's 80 sound groups (tools/sound_groups.py: globalSoundInfo = DTP 792 + 0xe0; Xbox id 775).
  Retail Xbox and PC ship 77 groups; the TU adds groups 77, 78, 79 for DLC 2 (parents 8, 77, 53), appends group 79 to
  the pause list, gives every new group a runtime area (+0x80 pointer; 2 x 32 B for 77 / 78, 16 B zero for 79) and
  raises the two counts (groups 77 -> 80, pause list 4 -> 5): +480 bytes, 3 new internal relocations. All other 51
  sections of the PC file stay the PC original (the TU also swaps two dependency words in script Xbox 56 and permutes
  scripts 220 / 221 and 768 - 770; the B138 kit took none of that, neither do we - list in the knowledge file).
  The PC sound DTP has the same layout as the retail Xbox one (relocations equal), so the TU edit applies at the same
  offsets. Words are u32 (proven: PC = u32-swapped retail in every word the edit touches or copies, `learn`).
  New group entries are copies of existing PC entries plus a few set words (copy source = the retail entry that the
  TU entry differs least from), so only 88 bytes of TU values are recorded (16 floats of the two new areas, 3 entry
  words, 1 list word, 2 counts).
  The relocation list is written sorted by offset, as the B138 kit file has it (PC retail / TU keep two pointers at
  the end; the order is not known to matter - kept for the md5 gate).

Gate: the raw (decompressed) DRM is md5-equal to the B138 kit file (= B270): raw md5 94a70736...; with --kit also
section by section. The CDRM md5 of the kit (444484..., docs/data/B138.kit_manifest.json) is reported, not gated: it
depends on the zlib build - the project venv's zlib-ng 1.3.1 does not re-encode even the PC original byte-equal
(work/kitfree_1011/cdrm_probe.py: ours 17 704 B, kit 17 698 B, same content).

One field is not u32: group entry +0x7c is a u16 DSP kind (engine 0x58de54 / 0x587620; base entries 58 / 59 =
u16 halves). The kit wrote the two new values (groups 77 / 78: 4 / 1) u32-swapped, so on PC their u16 reads 0 (no
DSP effect). Default build = the kit bytes (md5 gate, the file B138 / B270 players run); --tu-form writes those 2
words in the base-rule form (gate: recorded md5, and against --kit exactly these 2 words differ). Which one the
pipeline installs is the owner's decision (live sound check of the DLC 2 groups 77 / 78 first).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/globalsoundinfo_build.py build [OUT_DIR] [--tu-form] [--knowledge JSON]
        -> OUT_DIR/mods/globalsoundinfo.drm (default work/rebuild/globalsound) + OUT_DIR/globalsound_check.json;
           exit 1 (nothing written) when the PC original or the result does not match the recorded md5
  ../bin/pyt -t 120 tools/globalsoundinfo_build.py --check [FILE] [--tu-form] [--kit KIT_FILE] [--knowledge JSON]
        build in memory (or read FILE) and run the gate; --kit also compares section by section with a kit file
  ../bin/pyt -t 300 tools/globalsoundinfo_build.py learn [--write] [--knowledge JSON]      (developer: Xbox data)
        derive the edit from Xbox retail + TitleUpdate.000 (+ PC for the layout / byte-order proof) and compare it
        with the recorded knowledge file; --write records it (expect md5s are kept from the existing file)
"""
import sys, os, json, struct, hashlib, difflib, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from drm import cdrm_decode, sections_with_data
import drm_reloc as R
import drm_write as DW

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..')
KNOW = os.path.join(REPO, 'docs', 'data', 'globalsoundinfo_tu.json')
MANIFEST = os.path.join(REPO, 'docs', 'data', 'B138.kit_manifest.json')
OUT = os.path.join('work', 'rebuild', 'globalsound')
B = '../data/'
NAME = 'globalsoundinfo.drm'
PC_SRC = ['pc/patch.000', 'pc/bigfile.000']           # patch.000 first (it has no globalsoundinfo; checked)
XB_RETAIL = ['TombRaiderUnderworld_Patched/layer1.000', 'TombRaiderUnderworld_Patched/layer2.000']
XB_TU = 'TombRaiderUnderworld_Patched/TitleUpdate.000'
ENTRY = 0x84
GSI = 0xe0                 # globalSoundInfo inside the DTP (sound_groups.GSI_OFF)


def md5(b):
    return hashlib.md5(b).hexdigest()


def record(paths, endian, name):
    """compressed record bytes of name (spec 0xffffffff) from the first archive that has it -> (path, bytes)"""
    for p in paths:
        a = Archive(B + p, endian)
        r = [x for x in a.find(crc(name)) if x['spec'] == 0xffffffff]
        if r: return p, a.read(r[0])
    return None, None


def pc_original():
    src, raw = record(PC_SRC, 'le', 'pc-w\\' + NAME)
    if raw is None: raise SystemExit('PC %s not found in %s' % (NAME, ', '.join(PC_SRC)))
    return src, raw


def find_sec(D, t, i):
    k = [n for n, s in enumerate(D.sections) if s.type == t and s.id == i]
    if len(k) != 1: raise SystemExit('section %d:%d found %d times' % (t, i, len(k)))
    return k[0]


# ------------------------------------------------------------------------------------------------ apply (player)
def shift_fn(inserts):
    """byte offset in the PC section -> offset in the result (an insertion at p moves everything at >= p)"""
    ins = sorted((x['at'], x['len']) for x in inserts)
    return lambda o: o + sum(n for p, n in ins if p <= o)


def pack_word(v, form):
    """a word value (as read big-endian on the Xbox) in PC form: u32 (byte-swapped) or u16x2 (each u16 half swapped,
    halves in place)"""
    if form == 'u32': return struct.pack('<I', v)
    if form == 'u16x2': return struct.pack('<HH', v >> 16, v & 0xffff)
    raise SystemExit('unknown word form %s' % form)


def block_bytes(x, pc_data, tu_form):
    """tu_form False = the B138 kit's bytes (every set word u32); True = each set word in the form the base pair
    proves for its field (recorded per word)"""
    if 'zero' in x: return bytes(x['zero'])
    if 'u32' in x: return b''.join(struct.pack('<I', v) for v in x['u32'])
    if 'entries' in x:
        out = bytearray()
        for e in x['entries']:
            src = x['entry_base'] + e['copy'] * x['entry_size']
            b = bytearray(pc_data[src:src + x['entry_size']])
            for sw in e['set']:
                b[sw[0]:sw[0] + 4] = pack_word(sw[1], sw[2] if tu_form else 'u32')
            out += b
        return bytes(out)
    raise SystemExit('unknown insert kind: %s' % sorted(x))


def apply_edit(data, reloc, K, tu_form=False):
    """PC section data / reloc + knowledge -> new data / reloc"""
    E = K['edit']
    if len(data) != E['size_pc']: raise SystemExit('PC section size %d, knowledge expects %d' % (len(data), E['size_pc']))
    base = bytearray(data)
    for sw in E['set_u32']: struct.pack_into('<I', base, sw[0], sw[1])      # [offset, value(, meaning)]
    out = bytearray(); pos = 0
    for x in sorted(E['inserts'], key=lambda x: x['at']):
        blk = block_bytes(x, data, tu_form)
        if len(blk) != x['len']: raise SystemExit('insert at %d: %d bytes, expected %d' % (x['at'], len(blk), x['len']))
        out += base[pos:x['at']] + blk; pos = x['at']
    out += base[pos:]
    if len(out) != E['size_out']: raise SystemExit('result size %d, expected %d' % (len(out), E['size_out']))
    sh = shift_fn(E['inserts'])
    r = R.parse(reloc, 'le')
    r.internal = [(sh(o), sh(t)) for o, t in r.internal] + [tuple(v) for v in E['new_internal']]
    r.external = [(si, sh(s), d) for si, s, d in r.external]
    r.idref_a = [(t, sh(o)) for t, o in r.idref_a]
    r.idref = [(t, sh(o)) for t, o in r.idref]
    if E.get('reloc_sorted'): r.internal.sort()
    bad = R.check(r, len(out))
    if bad: raise SystemExit('relocation out of bounds: %s' % bad[:5])
    return bytes(out), R.write(r, 'le')


def build(K, tu_form=False):
    """-> (raw DRM, CDRM bytes, info) from the player's PC original (tu_form: see block_bytes)"""
    src, comp = pc_original()
    raw = cdrm_decode(comp, 'le')
    info = dict(pc_source=src, pc_cdrm_md5=md5(comp), pc_raw_md5=md5(raw))
    if md5(raw) != K['pc']['raw_md5']:
        raise SystemExit('PC %s (%s) raw md5 %s, the knowledge expects %s - another game version?' % (
            NAME, src, md5(raw), K['pc']['raw_md5']))
    D = DW.read(raw, 'le')
    k = find_sec(D, 7, K['edit']['section'][1])
    s = D.sections[k]
    s.data, s.reloc = apply_edit(s.data, s.reloc, K, tu_form)
    out = D.write('le')
    return out, DW.cdrm_encode(out, 'le'), info


def form_words(K):
    """[(result offset in the sound DTP, group, entry offset, form)] of the set words whose base-pair form is not u32"""
    E = K['edit']; sh = shift_fn(E['inserts']); out = []
    for x in E['inserts']:
        if 'entries' not in x: continue
        start = sh(x['at']) - x['len']
        for j, e in enumerate(x['entries']):
            for sw in e['set']:
                if sw[2] != 'u32': out.append((start + j * x['entry_size'] + sw[0], e['group'], sw[0], sw[2]))
    return out


def gate(raw, comp, K, kit=None, tu_form=False):
    """-> (ok, report dict); tu_form: expected = the recorded md5 of the base-rule variant, and against a kit file
    exactly the form words (form_words) may differ"""
    ex = K['expect']
    exp_raw = ex['tu_form_raw_md5'] if tu_form else ex['raw_md5']
    rep = dict(variant='tu_form' if tu_form else 'kit', raw_md5=md5(raw), raw_size=len(raw), cdrm_md5=md5(comp),
               cdrm_size=len(comp), expect_raw_md5=exp_raw, expect_cdrm_md5=None if tu_form else ex['cdrm_md5'])
    man = None
    if os.path.exists(MANIFEST):
        for f in json.load(open(MANIFEST))['files']:
            if f['rel'].lower() == NAME: man = f['md5']
    rep['b138_manifest_md5'] = man
    rep['raw_equal'] = md5(raw) == exp_raw
    rep['cdrm_equal'] = md5(comp) == ex['cdrm_md5']
    if man is not None and man != ex['cdrm_md5']: rep['warning'] = 'knowledge cdrm md5 != B138 manifest md5'
    if kit:
        kraw = cdrm_decode(open(kit, 'rb').read(), 'le')
        a = sections_with_data(raw, 'le')[1]; b = sections_with_data(kraw, 'le')[1]
        key = lambda x: (x['type'], x['id'], x['data'], x['reloc'], x['ver'], x['flags'])
        diff = [(x['type'], x['id']) for x, y in zip(a, b) if key(x) != key(y)]
        rep['kit'] = dict(file=kit, sections=len(b), same_count=len(a) == len(b), differing=diff)
        sid = tuple(K['edit']['section'])
        words = []
        for x, y in zip(a, b):
            if (x['type'], x['id']) == sid and x['size'] == y['size']:
                words = [o for o in range(0, x['size'], 4) if x['data'][o:o + 4] != y['data'][o:o + 4]]
        rep['kit']['sound_dtp_words_differing'] = ['0x%x' % o for o in words]
        if tu_form:
            want = sorted(o for o, _, _, _ in form_words(K))
            rep['kit']['expected_words'] = ['0x%x' % o for o in want]
            rep['kit_section_equal'] = len(a) == len(b) and diff in ([], [sid]) and words == want and \
                all(key(x) == key(y) or (x['type'], x['id']) == sid for x, y in zip(a, b)) and \
                all(x['reloc'] == y['reloc'] for x, y in zip(a, b))
        else:
            rep['kit_section_equal'] = len(a) == len(b) and not diff
    # the gate is the raw DRM: the CDRM bytes depend on the zlib build (zlib-ng 1.3.1 in the project venv does not
    # re-encode even the PC original byte-equal; classic zlib level 9 did, drm_write.py) - reported, not gated
    import zlib
    rep['zlib'] = zlib.ZLIB_RUNTIME_VERSION
    if not rep['cdrm_equal']:
        rep['cdrm_note'] = 'CDRM differs only by the compressor (raw DRM %s); not part of the gate' % (
            'equal' if rep['raw_equal'] else 'DIFFERENT')
    ok = rep['raw_equal'] and rep.get('kit_section_equal', True)
    rep['gate'] = 'ok' if ok else 'FAILED'
    return ok, rep


# ------------------------------------------------------------------------------------------------ learn (developer)
def sec_be(paths, name, t, i):
    p, comp = record(paths, 'be', 'xenon-w\\' + name)
    if comp is None: raise SystemExit('%s not in %s' % (name, paths))
    secs = sections_with_data(cdrm_decode(comp, 'be'), 'be')[1]
    return p, secs, [s for s in secs if s['type'] == t and s['id'] == i][0]


def learn(K_old):
    _, xsecs, X = sec_be(XB_RETAIL, NAME, 7, 775)
    _, tsecs, T = sec_be([XB_TU], NAME, 7, 775)
    src, pcomp = pc_original()
    psecs = sections_with_data(cdrm_decode(pcomp, 'le'), 'le')[1]
    P = [s for s in psecs if s['type'] == 7 and s['id'] == 792][0]
    rx, rt, rp = R.parse(X['reloc'], 'be'), R.parse(T['reloc'], 'be'), R.parse(P['reloc'], 'le')
    notes = []
    if rx != rp or X['size'] != P['size']: raise SystemExit('PC DTP 792 layout != retail DTP 775: the TU edit cannot be placed')
    notes.append('PC DTP 792 and retail DTP 775: same size %d, relocations equal (%d internal)' % (P['size'], len(rp.internal)))
    if rx.external or rx.idref or rx.idref_a or rt.external or rt.idref or rt.idref_a:
        raise SystemExit('external / id relocations in the sound DTP - not handled')
    swap = lambda b: b''.join(b[o:o + 4][::-1] for o in range(0, len(b), 4))
    nonu32 = [o for o in range(0, P['size'], 4) if P['data'][o:o + 4] != swap(X['data'][o:o + 4])]
    notes.append('PC = u32-swapped retail in %d of %d words (others at %s)' % (
        P['size'] // 4 - len(nonu32), P['size'] // 4, ', '.join('0x%x' % o for o in nonu32)))
    wx = [X['data'][o:o + 4] for o in range(0, X['size'], 4)]
    wt = [T['data'][o:o + 4] for o in range(0, T['size'], 4)]
    sets, ins = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wx, wt, autojunk=False).get_opcodes():
        if tag == 'equal': continue
        if tag == 'replace' and i2 - i1 == j2 - j1:
            sets += [[4 * (i1 + k), struct.unpack('>I', wt[j1 + k])[0]] for k in range(i2 - i1)]
        elif tag == 'insert':
            ins.append(dict(at=4 * i1, len=4 * (j2 - j1)))
        else:
            raise SystemExit('TU edit is not set / insert only (%s at 0x%x)' % (tag, 4 * i1))
    # an insertion inside a run of equal words can sit anywhere in the run: pick the positions at which the shifted
    # retail relocations are all found in the TU relocations
    def cands(x, s):
        """positions q at which inserting the block gives the same TU bytes (s = bytes inserted before it):
        left of p the retail words X[q:p] must reappear right after the block, right of p X[p:q] right before it"""
        p, n = x['at'], x['len']; xd, td = X['data'], T['data']
        c = [p]; q = p - 4
        while q >= 0 and xd[q:p] == td[q + s + n:p + s + n]:
            c.append(q); q -= 4
        q = p + 4
        while q <= X['size'] and xd[p:q] == td[p + s:q + s]:
            c.append(q); q += 4
        return sorted(c)
    tset = set(rt.internal)
    best = None
    cl = []; s = 0
    for x in ins:
        cl.append(cands(x, s)); s += x['len']
    if sum(len(c) for c in cl) > 4000: raise SystemExit('too many insert placements')
    for combo in itertools.product(*cl):
        trial = [dict(at=p, len=x['len']) for p, x in zip(combo, ins)]
        sh = shift_fn(trial)
        pred = [(sh(o), sh(t)) for o, t in rx.internal]
        hit = sum(1 for v in pred if v in tset)
        # >=: of the equally good placements the last one (each insert as far right as it can go = right before the
        # first pointer target that must move, i.e. at the start of the following area / list)
        if best is None or hit >= best[0]: best = (hit, trial, pred)
    hit, ins, pred = best
    if hit != len(rx.internal): raise SystemExit('no insert placement explains the TU relocations (%d / %d)' % (hit, len(pred)))
    new_int = [list(v) for v in rt.internal if v not in set(pred)]
    sh = shift_fn(ins)
    # content of each insert = the TU words at its place in the result
    for x in ins:
        o = sh(x['at']) - x['len']
        x['tu'] = T['data'][o:o + x['len']]
    n_ret = struct.unpack_from('>I', X['data'], GSI + 4)[0]
    ent = dict(rx.internal)[GSI + 8]
    lit = 4 * len(sets)

    def field_form(w):
        """PC byte form of entry field +w, proven on the n_ret base entries (retail <-> PC): [form, proof]"""
        conv = {'u32': lambda b: b[::-1], 'u16x2': lambda b: b[1::-1] + b[3:1:-1]}
        ok = {f: 0 for f in conv}; bad = {f: [] for f in conv}; inf = 0
        for k in range(n_ret):
            o = ent + k * ENTRY + w
            xb, pb = X['data'][o:o + 4], P['data'][o:o + 4]
            if conv['u32'](xb) != conv['u16x2'](xb): inf += 1
            for f, c in conv.items():
                if c(xb) == pb: ok[f] += 1
                else: bad[f].append(k)
        form = 'u32' if not bad['u32'] else 'u16x2' if not bad['u16x2'] else None
        if form is None: raise SystemExit('entry field +0x%x: neither u32 nor u16x2 on the base pair' % w)
        proof = 'base entries: %d of %d distinguish u32 / u16x2; u32 contradicted by %s, u16x2 by %s' % (
            inf, n_ret, bad['u32'] or 'none', bad['u16x2'] or 'none')
        return [form, proof]
    for x in ins:
        tu = x.pop('tu')
        if x['at'] == ent + n_ret * ENTRY and x['len'] % ENTRY == 0:
            x['what'] = 'sound group entries %d..%d (0x84 each): copy of a PC entry + set words' % (n_ret, n_ret + x['len'] // ENTRY - 1)
            x['entry_base'] = ent; x['entry_size'] = ENTRY; x['entries'] = []
            for j in range(x['len'] // ENTRY):
                e = tu[j * ENTRY:(j + 1) * ENTRY]
                diffs = []
                for k in range(n_ret):
                    r_ = X['data'][ent + k * ENTRY: ent + (k + 1) * ENTRY]
                    diffs.append((sum(1 for w in range(0, ENTRY, 4) if e[w:w + 4] != r_[w:w + 4]), k))
                nd, k = min(diffs)
                r_ = X['data'][ent + k * ENTRY: ent + (k + 1) * ENTRY]
                st = [[w, struct.unpack('>I', e[w:w + 4])[0]] + field_form(w)
                      for w in range(0, ENTRY, 4) if e[w:w + 4] != r_[w:w + 4]]
                bad = [w for w in range(0, ENTRY, 4) if ent + k * ENTRY + w in nonu32]
                if bad: raise SystemExit('copy source entry %d has non-u32 words %s' % (k, bad))
                x['entries'].append(dict(group=n_ret + j, copy=k, set=st))
                lit += 4 * len(st)
        elif not any(tu):
            x['what'] = 'zero bytes'; x['zero'] = x['len']
        else:
            x['what'] = 'TU u32 words'; x['u32'] = [struct.unpack_from('>I', tu, o)[0] for o in range(0, len(tu), 4)]
            lit += x['len']
        x['at_hex'] = '0x%x' % x['at']
    touched = [o for o, _ in sets] + [x['at'] for x in ins]
    near = [o for o in touched if o in nonu32]
    if near: raise SystemExit('the edit touches non-u32 words: %s' % near)
    # meaning of the places (sound_groups layout), for the record
    it = dict(rx.internal)
    for x in ins:
        if 'entries' in x: continue
        for nm, (no, po) in (('fall list', (0x0c, 0x10)), ('death list', (0x14, 0x18)), ('pause list', (0x1c, 0x20))):
            lp = it.get(GSI + po); cnt = struct.unpack_from('>I', X['data'], GSI + no)[0]
            if lp is not None and x['at'] == lp + 4 * cnt and cnt: x['what'] = '%s: appended group(s) %s' % (nm, x.get('u32'))
        for v in new_int:
            if v[1] == sh(x['at']) - x['len'] and v[0] >= sh(ent):
                g = (v[0] - sh(ent) - 0x80) // ENTRY
                x['what'] = 'runtime area (+0x80 pointer target) of new group %d%s: %s' % (
                    g, '' if x['len'] <= 16 else ' and the following new group(s)', x['what'])
    for s_ in sets:
        if s_[0] == GSI + 4: s_.append('group count')
        if s_[0] == GSI + 0x1c: s_.append('pause list count')
    # the other TU changes (not taken, as by the kit)
    other = []
    for i, (a, b) in enumerate(zip(xsecs, tsecs)):
        if (a['type'], a['id']) == (7, 775) or (a['data'] == b['data'] and a['reloc'] == b['reloc']): continue
        pcs = psecs[i]
        row = dict(index=i, type=a['type'], xbox_id=a['id'], pc_id=pcs['id'], size_retail=a['size'], size_tu=b['size'])
        if a['size'] == b['size']:
            row['words'] = sum(1 for o in range(0, a['size'] - 3, 4) if a['data'][o:o + 4] != b['data'][o:o + 4])
        same = [j for j, c in enumerate(xsecs) if c['data'] == b['data'] and c['reloc'] == b['reloc']]
        if same: row['tu_content_is_retail_index'] = same
        other.append(row)
    if len(xsecs) != len(tsecs): raise SystemExit('TU section count differs')
    E = dict(section=[7, 792], xbox_section=[7, 775], size_pc=P['size'], size_out=T['size'],
             set_u32=sets, inserts=ins, new_internal=new_int, reloc_sorted=True)
    K = dict(K_old or {})
    about = ('Title-update edit of globalsoundinfo.drm (sound DTP PC 792 / Xbox 775: 3 new sound groups for DLC 2) '
             'against the player\'s PC original, learned by tools/globalsoundinfo_build.py learn from the Xbox retail '
             '<-> TitleUpdate.000 pair. Offsets are bytes in the PC section before the edit (set_u32, inserts.at) or in '
             'the result (new_internal); values are word values as the Xbox reads them; entry set words carry the PC '
             'byte form of their field proven on the base entries ([offset, value, form, proof]). Only tu_literal_bytes '
             'bytes are TU values; entries are copies of PC entries. not_taken = the other TU changes of the file (left '
             'out, as by the B138 kit). kit_form_words = set words the kit wrote in another form (default build = kit).')
    K.update(about=about, schema=1, file=NAME,
             pc=dict(name='pc-w\\' + NAME, source=src, raw_md5=md5(cdrm_decode(pcomp, 'le')), cdrm_md5=md5(pcomp)),
             edit=E, tu_literal_bytes=lit, not_taken=other, learn_notes=notes)
    return K


def jdump(K):
    return json.dumps(K, indent=1, ensure_ascii=True)


def main(a):
    kp = KNOW
    if '--knowledge' in a: k = a.index('--knowledge'); kp = a[k + 1]; del a[k:k + 2]
    kit = None
    if '--kit' in a: k = a.index('--kit'); kit = a[k + 1]; del a[k:k + 2]
    K = json.load(open(kp)) if os.path.exists(kp) else None
    if a and a[0] == 'learn':
        L = learn(K)
        if kit:         # the gate's expected md5s = the kit file (B138 = B270), recorded once
            kc = open(kit, 'rb').read()
            L['expect'] = dict(raw_md5=md5(cdrm_decode(kc, 'le')), cdrm_md5=md5(kc), cdrm_size=len(kc),
                               source='B138 kit globalsoundinfo.drm (= B270, docs/data/kit_dependency.tsv)')
        elif 'expect' not in L:
            raise SystemExit('learn without a recorded expect: pass --kit KIT_FILE once')
        fw = form_words(L)
        L['kit_form_words'] = dict(
            words=[dict(offset=o, group=g, field=w, form=f) for o, g, w, f in fw],
            why=('the engine reads the group entry field +0x7c as a u16 (0x58de54 cmp word ptr [eax+0x7c], 0; '
                 '0x587620 movzx = DSP kind 1..11 -> FMOD DSP type, 0x7b98ea) and the base entries 58 / 59 carry it as '
                 'u16 halves (retail 00050000 -> PC 05000000); the B138 kit file has these words u32-swapped '
                 '(00000400 / 00000100: u16 at +0x7c = 0, no DSP for the new groups). Default build = kit bytes '
                 '(md5 gate), --tu-form = base-rule form') if fw else '')
        L['expect']['tu_form_raw_md5'] = md5(build(L, tu_form=True)[0])
        print('\n'.join(L['learn_notes']))
        print('edit: %d set words, %d inserts, %d new internal relocations; TU literal bytes %d' % (
            len(L['edit']['set_u32']), len(L['edit']['inserts']), len(L['edit']['new_internal']), L['tu_literal_bytes']))
        for x in L['edit']['inserts']: print('  insert at 0x%x, %d B: %s' % (x['at'], x['len'], x['what']))
        print('not taken (other TU changes):', json.dumps(L['not_taken']))
        same = K is not None and {k: K.get(k) for k in ('edit', 'pc', 'tu_literal_bytes', 'not_taken')} == \
            {k: L.get(k) for k in ('edit', 'pc', 'tu_literal_bytes', 'not_taken')}
        print('recorded knowledge %s' % ('= learned' if same else 'DIFFERS from the learned edit' if K else 'missing'))
        if '--write' in a:
            open(kp, 'w', encoding='utf-8', newline='\n').write(jdump(L) + '\n')
            print('written', kp)
            return 0
        return 0 if same else 1
    if K is None: raise SystemExit('knowledge file missing: %s' % kp)
    tu_form = '--tu-form' in a; a = [x for x in a if x != '--tu-form']
    if a and a[0] == '--check':
        if len(a) > 1:
            comp = open(a[1], 'rb').read(); raw = cdrm_decode(comp, 'le'); info = dict(file=a[1])
        else:
            raw, comp, info = build(K, tu_form)
        ok, rep = gate(raw, comp, K, kit, tu_form)
        rep.update(info)
        print(json.dumps(rep, indent=1))
        print('gate', rep['gate'])
        return 0 if ok else 1
    if a and a[0] == 'build':
        out_dir = a[1] if len(a) > 1 else OUT
        raw, comp, info = build(K, tu_form)
        ok, rep = gate(raw, comp, K, kit, tu_form)
        rep.update(info)
        print(json.dumps(rep, indent=1))
        if not ok:
            print('gate FAILED - nothing written'); return 1
        os.makedirs(os.path.join(out_dir, 'mods'), exist_ok=True)
        dst = os.path.join(out_dir, 'mods', NAME)
        open(dst, 'wb').write(comp)
        json.dump(rep, open(os.path.join(out_dir, 'globalsound_check.json'), 'w'), indent=1)
        print('written %s (%d bytes, md5 %s), gate ok' % (dst, len(comp), md5(comp)))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
