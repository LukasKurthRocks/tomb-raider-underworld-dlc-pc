"""Typed rules for seven record families of the converter fault class "learned type-7 table" (17n, 2026-11-08; the
families were found by 17h-B / 17h-C / 17j-b / 17l in the night 07./08.11., docs ENGINE.md section 2). Every DTP or
Level section without a same-size base twin takes the generic `convert` route, which classes each word by the learned
type-7 table (label key + Xbox value shape) - these records came out with the right bytes in the wrong order for the
field width. Each rule below re-derives its truth from base-game Xbox / PC pairs at run time (`proof`), changes a word
only where the PC word is ANOTHER BYTE ORDER of the Xbox word (anything else is kept and counted), and proves every
write (decoded DRM differs only in the planned bytes, file / section headers and relocations identical, re-plan 0).

Rules (step names of tools/dlc_struct_fixes.py):
  fadecard   fade-record DTPs (card / flash / key-glow objects; Xbox signature: beebbeeb at +0x08 and +0x48, u16 count
             n at +0x44, size 0x90 + 12 n): header +0x44 {u16 n, u16 0} and every record {u16 from, u16 to}
             {u16 frames, u16 word2} {u8 r, g, b, a} -> s16, s16, raw (17h-B, work/endcine_0811/fade_fix.py)
  uberanim   uber play-anim words (object DTP +0xc8 -> uber block 0x8080b00b; action kind 2 argument +4 and every
             transition +0x28) = {u16 mode, u16 anim} -> s16 (17h-C crash 08.11. 00:27, work/crash_0811/uber_anim_fix.py;
             engine 0x4d86d9 / 0x4d4a26)
  basecopy   type-7 DTPs whose Xbox payload equals the base Xbox DTP of the same id (one Xbox content in the base game;
             the PC id = the converter's base id map, one PC content): payload = the PC base copy word for word; a
             36-byte DLC trailer {.., 9c6f3e84, size, .., cafebabe} after the payload is kept (unread on PC); the
             payload relocations must equal the PC base copy's (17j-b vs_base_pc.py, 17l judge.py basecopy)
  leveltwin  Level sections (section 0, type 0) of units without a same-size base twin: the twin is the l7_* base unit
             with the most same-offset equal non-zero Xbox words (>= 50 % and >= 256 words); a word whose DLC Xbox word equals the base
             Xbox word at the same offset and whose base PC word is a byte permutation of it gets the base PC word;
             pointer / id slots of all four sides and the NavGraph image (step navraw) are left alone (17j-b
             work/endb270_0811/sec0_judge.py, ygg_fix.py L); since 2026-11-09 also a non-zero DLC Xbox word that
             DIFFERS from the twin where the twin pair is s32 -> s32 (only when the PC word is a byte order of it:
             dlc_yggdrasil_end Level +0x148 / +0x168 / +0x178 / +0x188 = installed = B270; 0813 had u16 pairs)
  introtyped unit DTP (Level+0x74 target) intro data: intro +0x7c u32 (s32), intro data blocks by (PC object id, block
             size) with one byte order over every base intro of the BASE_UNITS (17j-b unit_dtp.py / scan_unit.py),
             name strings (>= 8 printable bytes at a pointer target) raw; the root +0xa4 block +0x90 / +0x94 has no
             rule over the base units (l7_yggdrasil_end +0x94 raw, l7_yggdrasil_hall02 +0x94 s32), but since 2026-11-09
             the unit's own base twin (the leveltwin twin of its Level) decides where its Xbox word is the same
             (root_twin_words: dlc_yggdrasil_end 21218 +0x14f04 = 18550 -> raw)
  fxrec      FX particle records (anchor bf800000 x3, c04a468e x2): record +0x18 and +0x38 with an Xbox word XX000000
             -> raw (17j-b pattern_twins.py: DTP 22819 of dlc2_checkpoint, 13 DRMs)
  sgmesh     streamgroup mesh-list DTPs {u32 n, n x {u32 mesh id (idref 12), u32, u32, u32}}: every word s32 (the id
             words are left to the converter's id map) (17j-b sg_mesh_list.py)
  fxrecread  the 0x17c particle records of the object data DTP (object +8 -> DTP, u16 count +0x0c, records at [+0x10];
             reader tru.exe 0x543f70, record = [objdata+0x10] + i * 0x17c at 0x543fc2) at the 12 offsets objrec does
             not rule (tools/objdata_rec_classes.py): the reader reads +0x40 / +0x90 bytes 0-2, +0x68 / +0x88 bytes
             0-1, +0x7c / +0x12c / +0x14c byte 0, +0x11c / +0x174 bytes 0-3 as u8 -> raw (bytes read in place);
             +0x58 {u8, u8, u16} -> b2s16, +0x5c u16 at byte 0 -> s16b2, +0x160 {u16, u16} -> s16 (17o p2_fields /
             p3_bytes, 18e)
introtyped also takes, since 18e (2026-11-08), the words of the unit-DTP pointer-path table (17o d4_table): every
  pointer-target region of the unit DTP labelled by its pointer path from the root (intros by object name), base samples
  of all base units with an Xbox + PC unit DTP of the same intro count / names (77), tiers K1 exact (label, size, offset)
  -> KS root/+1a4 stride 0x100 -> KA alias -> K3 last step wild (17o's size-only tier KZ is not used: on the 0812
  pipeline copies it typed DLC 1 float records as u16 pairs); a tier decides when the intersection of its samples'
  byte orders gives ONE wanted word for this Xbox word, no sample is 'other' and >= 10 votes come from base samples of
  the same zero / non-zero byte shape as the DLC word; the 17j-b rules above win where they speak. NOT the word unit DTP 23100 +0x6268 (dlc_yggdrasil_hall02: the
  17l fp rule says s32, the table s16 - owner decision open).
Not built here (owner decision pending, 17l / 17m): odtwin (aligned thrall object data), fpkeys (dtp_audit keys),
the DTP 24392 re-spacing + twin step, class-d words.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/typed_family_fix.py proof [--rules a,b] [--report R.json]
        base proof of every rule (exit 1 when a pinned count differs or a base word contradicts a rule)
  ../bin/pyt -t 3600 tools/typed_family_fix.py scan TREE [--rules a,b] [--pack pack11] [--names a.drm,b.drm]
        per DRM / rule the words a fix would change (nothing written); exit 1 when any
Library (steps of tools/dlc_struct_fixes.py): fix_drm(rule, XD, raw, rel) -> (new raw or None, changes [(section index,
  offset, old, new, section id, tag)], info dict(rows, kept, notes)); proven(rule) -> (ok, lines) once per process.
"""
import sys, os, struct, collections, json, io, contextlib, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_reloc as R, drm_write as DW

RULES = ('fadecard', 'uberanim', 'basecopy', 'leveltwin', 'introtyped', 'fxrec', 'sgmesh', 'fxrecread')
PERMS = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'raw': (0, 1, 2, 3)}
# u16 / u8 mixes (unit-DTP path table and fxrecread): b2s16 = bytes 0, 1 in place + u16 at byte 2, s16b2 = u16 at byte 0
XPERMS = dict(PERMS, b2s16=(0, 1, 3, 2), s16b2=(1, 0, 2, 3))
# fxrecread: record offset -> byte order, from the reads of tru.exe 0x543f70 (offsets that objrec does not rule)
FXREAD = {0x40: 'raw', 0x68: 'raw', 0x7c: 'raw', 0x88: 'raw', 0x90: 'raw', 0x11c: 'raw', 0x12c: 'raw', 0x14c: 'raw',
          0x174: 'raw', 0x58: 'b2s16', 0x5c: 's16b2', 0x160: 's16'}
FX_REC = 0x17c
# introtyped path table
TABLE_MIN = 10                     # votes a tier key needs
TABLE_EXCLUDE = {(23100, 0x6268): 'rule conflict (17l fp rule s32, path table K1 s16) - owner decision open'}
PC_FILELIST = os.path.join(HERE, '..', 'ref', 'yura-release', 'FileLists', 'Tomb Raider Underworld (PC).txt')
LISTS = os.path.join(HERE, '..', 'work', 'generic', 'lists')
BEEB = b'\xbe\xeb\xbe\xeb'
UBER_MAGIC = 0x8080b00b
FX_ANCHOR = b'\xbf\x80\x00\x00' * 3 + b'\xc0\x4a\x46\x8e' * 2
CAFE = b'\xca\xfe\xba\xbe'
TRAILER = 36
L7_UNITS = ('l7_arctic_sea', 'l7_helheim01', 'l7_helheim02', 'l7_helheim03', 'l7_helheim_hall01', 'l7_helheim_hall02',
            'l7_himalaya_end', 'l7_monastery', 'l7_thin_ice', 'l7_yggdrasil', 'l7_yggdrasil_end', 'l7_yggdrasil_hall01',
            'l7_yggdrasil_hall02')
# introtyped: the base units whose intros give the (object, block size) table (17j-b scan_unit.BASES)
BASE_UNITS = ('l7_yggdrasil_end', 'l7_yggdrasil_hall02', 'l7_yggdrasil_hall01', 'l7_yggdrasil')
TWIN_MIN = 0.5               # leveltwin: share of the DLC Level's non-zero Xbox words equal at the same offset
TWIN_MIN_WORDS = 256         # ... and at least this many: unrelated l7 units share up to 9 words of the Level head
                             # (proof leveltwin), a tiny Level (dlc2_costumes 0xa0 B: 9 of 14) is no twin
XLAYERS = ['../data/TombRaiderUnderworld_Patched/layer%d.000' % i for i in (1, 2)]
PCBIG = '../data/pc/bigfile.000'

# pinned base counts (calibrated 2026-11-08 on work/generic/store.pkl and the l7_* units of layer1 / layer2 / PC
# bigfile.000); `proof` fails when a count differs or a base word contradicts the rule
PROOF_EXPECT = {
    'fadecard': {'dtps': 14, 'records': 42, 'ok': 139, 'amb': 1, 'contra': 0},
    'uberanim': {'dtps': 179, 'amb': 987, 'ok': 288, 'contra': 0},
    'basecopy': {'ids_one_xbox_content': 8979, 'ok': 8979, 'contra': 0},
    'leveltwin': {'units': 13, 'ok': 299, 'not_perm': 3, 'contra': 0},
    'introtyped': {'units': 4, 'intros': 595, 'keys': 10, 'keys_with_rules': 10, 'rule_words': 181, 'i7c_u32': 595,
                   'contra': 0, 'root_block_not_one_order': 1, 'string_raw': 1167,
                   # unit-DTP path table (18e = 17o d4_table: 81 base units, 77 with equal intro count / names)
                   'tbl_units_all': 81, 'tbl_units': 77, 'tbl_samples': 774257, 'tbl_keys_K1': 254442, 'tbl_keys_KS': 64,
                   'tbl_keys_K3': 186022, 'loo_K1_n': 315349, 'loo_K1_wrong': 3,
                   'loo_K3_n': 203862, 'loo_K3_wrong': 21, 'loo_KS_n': 19526, 'loo_KS_wrong': 0},
    'fxrec': {'records': 4695, 'ok': 228, 'contra': 0},
    'sgmesh': {'dtps': 84, 'ok': 188, 'amb': 178, 'contra': 0},
    # 18e: 11 032 base particle records (17o p1_base), 12 offsets x records, 0 slots
    'fxrecread': {'objrec_overlap': 0, 'objects': 471, 'records': 11032, 'ok': 64929, 'amb': 67455, 'contra': 0},
}


def perm(w, c): return bytes(w[i] for i in PERMS[c])


def byteorder(x, p):
    """p is some byte order of x (the same four bytes)"""
    return len(x) == 4 and len(p) == 4 and sorted(x) == sorted(p)


def cls(x, p):
    """'s32' / 's16' / 'raw' (one byte order), 'amb' (several: symmetric bytes), 'perm' (another permutation),
    'other' (no byte order of x)"""
    c = [n for n, pm in PERMS.items() if bytes(x[i] for i in pm) == p]
    if not c: return 'perm' if byteorder(x, p) else 'other'
    return c[0] if len(c) == 1 else 'amb'


def slots(s, e):
    """pointer / id offsets of a section (both kinds of relocation slot)"""
    r = R.parse(bytes(s.reloc) if hasattr(s, 'reloc') else s['reloc'], e)
    return set(r.pointer_offsets()) | set(r.id_offsets())


# ------------------------------------------------------------------------------------------------ shared inputs
_ST = {}


def store():
    """(store, ids, pc content count per PC DTP id) of the generic converter (work/generic/store.pkl, idmap)"""
    if 'st' not in _ST:
        import dtpid_sweep as DS
        st, ids = DS.ctx()
        pvc = json.load(open(os.path.join(HERE, '..', 'work', 'generic', 'pc_vers_content.json')))
        pcn = collections.Counter()
        for k in pvc:
            t, i, h = k.split(':')
            if t == '7' and not h.startswith('n'): pcn[int(i)] += 1
        _ST['st'] = (st, ids, pcn)
    return _ST['st']


def base_pairs7():
    """[(xbox id, pc id, xbox rec, pc rec)] of the same-size type-7 base pairs of the store"""
    if 'p7' not in _ST:
        st, ids, _ = store()
        out = []
        for (t, x), xb in st['xb_store'].items():
            if t != 7: continue
            p = ids.base[7].get(x)
            pc = st['pc_store'].get((7, p)) if p is not None else None
            if pc is None or len(pc['data']) != len(xb['data']): continue
            out.append((x, p, xb, pc))
        _ST['p7'] = out
    return _ST['p7']


def base_unit(name):
    """(Xbox Drm, PC Drm) of a base unit (Xbox layer1 / layer2, PC bigfile.000) or (None, None)"""
    k = ('unit', name)
    if k not in _ST:
        from archive import Archive
        from names import crc
        X = P = None
        for path in XLAYERS:
            A = Archive(path, 'be')
            r = [q for q in A.find(crc('xenon-w\\' + name + '.drm')) if q['spec'] == 0xffffffff]
            if r: X = DW.read(A.read(r[0]), 'be'); break
        A = Archive(PCBIG, 'le')
        r = [q for q in A.find(crc('pc-w\\' + name + '.drm')) if q['spec'] == 0xffffffff]
        if r: P = DW.read(A.read(r[0]), 'le')
        _ST[k] = (X, P)
    return _ST[k]


def pairs(XD, PD):
    import converter_faults_fix as CF
    return CF.pairs_by_position(XD, PD)


# ------------------------------------------------------------------------------------------------ detectors
def fade_words(xd):
    """{offset: class} of a fade-record DTP (Xbox bytes) or {}"""
    if len(xd) < 0x9c or xd[8:12] != BEEB or xd[0x48:0x4c] != BEEB: return {}
    n = struct.unpack_from('>H', xd, 0x44)[0]
    if not n or len(xd) != 0x90 + 12 * n: return {}
    out = {0x44: 's16'}
    for k in range(n):
        o = 0x90 + 12 * k
        out[o] = 's16'; out[o + 4] = 's16'; out[o + 8] = 'raw'
    return out


class _Sec:
    def __init__(self, data, reloc, e):
        self.d = data; self.e = '<' if e == 'le' else '>'
        self.ptr = dict(R.parse(reloc, e).internal)

    def u32(self, o):
        return struct.unpack_from(self.e + 'I', self.d, o)[0] if 0 <= o <= len(self.d) - 4 else None


def uber_words(data, reloc, e):
    """offsets of the play-anim words of an uber object DTP (work/crash_0811/uber_anim_scan.walk): DTP +0xc8 -> U
    (U+4 = 0x8080b00b), U+8 DESC count, U+0xc -> DESCs (stride 0x60, else the first stride whose node pointers are
    all relocated); DESC +4 node count, +8 -> nodes (28 B: +0x14 action count, +0x18 -> actions 16 B, kind 2 -> word
    +4); DESC +0xc transition count, +0x10 -> transitions (0x38 B, word +0x28)"""
    p = _Sec(data, reloc, e)
    U = p.ptr.get(0xc8)
    if U is None or p.u32(U + 4) != UBER_MAGIC: return []
    nd = p.u32(U + 8); D0 = p.ptr.get(U + 0xc)
    if D0 is None or not nd or nd > 64: return []
    stride = None
    for s in [0x60] + list(range(0x40, 0x100, 4)):
        if all(p.ptr.get(D0 + s * m + 8) is not None for m in range(nd)): stride = s; break
    if stride is None: stride = 0x60; nd = 1
    out = []
    for m in range(nd):
        D = D0 + stride * m
        n_nodes = p.u32(D + 4); N = p.ptr.get(D + 8)
        n_tr = p.u32(D + 0xc); Tr = p.ptr.get(D + 0x10)
        if N is not None and n_nodes and n_nodes < 500:
            for k in range(n_nodes):
                nb = N + 28 * k
                na = p.u32(nb + 0x14); A = p.ptr.get(nb + 0x18)
                if A is None or not na or na > 200: continue
                for j in range(na):
                    if p.u32(A + 16 * j) == 2: out.append(A + 16 * j + 4)
        if Tr is not None and n_tr and n_tr < 500:
            for k in range(n_tr):
                if Tr + 0x38 * k + 0x2c <= len(data): out.append(Tr + 0x38 * k + 0x28)
    return sorted(set(out))


def sgmesh_words(xd, xreloc):
    """{offset: 's32'} of a streamgroup mesh-list DTP (Xbox bytes) without the mesh id words, or {}"""
    if len(xd) < 20: return {}
    n = struct.unpack_from('>I', xd, 0)[0]
    if len(xd) != 4 + 16 * n: return {}
    idr = {o for t, o in R.parse(xreloc, 'be').idref if t == 12}
    if not all(4 + 16 * k in idr for k in range(n)): return {}
    out = {0: 's32'}
    for k in range(n):
        for w in (4, 8, 12): out[4 + 16 * k + w] = 's32'
    return out


def fx_words(xd):
    """{offset: 'raw'}: FX particle record words +0x18 / +0x38 whose Xbox word is XX000000"""
    out = {}
    o = xd.find(FX_ANCHOR)
    while o >= 0:
        if o % 4 == 0:
            for w in (0x18, 0x38):
                q = o + w; xw = xd[q:q + 4]
                if len(xw) == 4 and xw[0] and not any(xw[1:]): out[q] = 'raw'
        o = xd.find(FX_ANCHOR, o + 1)
    return out


def trailer_at(xd):
    """offset of the 36-byte DLC trailer (cafebabe at the end) or None"""
    return len(xd) - TRAILER if len(xd) >= TRAILER and xd[-4:] == CAFE else None


def unit_dtp(D, e):
    """section index of the unit DTP (Level+0x74 external target) or None"""
    if not D.sections or D.sections[0].type != 0: return None
    for si, so, do in R.parse(bytes(D.sections[0].reloc), e).external:
        if so == 0x74 and si < len(D.sections) and D.sections[si].type == 7: return si
    return None


def intros(u, e):
    """[(record offset, PC/Xbox object id, data pointer or None, data block size)] of a unit DTP (0x90-byte records,
    count +0xc, array +0x10; block size = distance to the next pointer target)"""
    E = '<' if e == 'le' else '>'
    d = bytes(u.data); ptr = dict(R.parse(bytes(u.reloc), e).internal)
    a = ptr.get(0x10)
    if a is None or len(d) < 0x14: return [], ptr
    n = struct.unpack_from(E + 'I', d, 0xc)[0]
    if a + 0x90 * n > len(d): return [], ptr
    tg = sorted(set(ptr.values()))
    import bisect
    out = []
    for k in range(n):
        o = a + 0x90 * k
        obj = struct.unpack_from(E + 'H', d, o + 0x50)[0]
        dp = ptr.get(o + 0x78)
        dsz = 0
        if dp is not None:
            j = bisect.bisect_right(tg, dp)
            dsz = (tg[j] if j < len(tg) else len(d)) - dp
        out.append((o, obj, dp, dsz))
    return out, ptr


def name_strings(xd, xptr):
    """word offsets of the name strings of a section: NUL-terminated runs of >= 8 printable bytes with >= 3 letters at
    a 4-aligned pointer target (17l judge.strings_plus, e.g. 'SIGNALS|Yggdrasil_END')"""
    out = set()
    for t in set(xptr.values()):
        if t % 4 or t >= len(xd): continue
        z = xd.find(b'\0', t, t + 256)
        if z < 0 or z - t < 8: continue
        s = xd[t:z]
        if not all(0x20 <= c < 0x7f for c in s) or sum(chr(c).isalpha() for c in s) < 3: continue
        out |= set(range(t, z + 1, 4))
    return out


# ------------------------------------------------------------------------------------------------ base tables
def intro_table():
    """from the intros of BASE_UNITS: (classes of intro +0x7c, {(obj, size): {w: class}} with one byte order,
    classes of root +0xa4 block +0x90 / +0x94, classes of name-string words, statistics)"""
    if 'it' in _ST: return _ST['it']
    i7c = collections.Counter(); D = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    root = collections.Counter(); strs = collections.Counter(); st = collections.Counter()
    for name in BASE_UNITS:
        X, P = base_unit(name)
        if X is None or P is None: st['missing'] += 1; continue
        kx, kp = unit_dtp(X, 'be'), unit_dtp(P, 'le')
        if kx is None or kp is None: st['no unit DTP'] += 1; continue
        ux, up = X.sections[kx], P.sections[kp]
        if len(ux.data) != len(up.data): st['unit DTP size differs'] += 1; continue
        st['units'] += 1
        IX, px = intros(ux, 'be'); IP, pp = intros(up, 'le')
        xd, pd = bytes(ux.data), bytes(up.data)
        for (xo, xobj, xdp, xsz), (po, pobj, pdp, psz) in zip(IX, IP):
            st['intros'] += 1
            i7c[cls(xd[xo + 0x7c:xo + 0x80], pd[po + 0x7c:po + 0x80])] += 1
            if xdp is None or pdp is None or xsz != psz: continue
            for w in range(0, psz - 3, 4):
                c = cls(xd[xdp + w:xdp + w + 4], pd[pdp + w:pdp + w + 4])
                D[(pobj, psz)][w][c] += 1
        rb = pp.get(0xa4); rbx = px.get(0xa4)
        if rb is not None and rbx is not None:
            for w in (0x90, 0x94): root[cls(xd[rbx + w:rbx + w + 4], pd[rb + w:rb + w + 4])] += 1
        for o in name_strings(xd, px):
            if o + 4 <= len(xd): strs[cls(xd[o:o + 4], pd[o:o + 4])] += 1
    rules = {}
    for key, ws in D.items():
        for w, c in ws.items():
            inf = {k: v for k, v in c.items() if k != 'amb'}
            if len(inf) == 1 and next(iter(inf)) in PERMS: rules.setdefault(key, {})[w] = next(iter(inf))
    st['keys'] = len(D); st['keys_with_rules'] = len(rules); st['rule_words'] = sum(len(v) for v in rules.values())
    _ST['it'] = (i7c, rules, root, strs, st)
    return _ST['it']


def l7_levels():
    """{name: (Xbox Level bytes, PC Level bytes, slot offsets of both)} of the l7_* base units"""
    if 'l7' not in _ST:
        out = {}
        for n in L7_UNITS:
            X, P = base_unit(n)
            if X is None or P is None or X.sections[0].type != 0 or P.sections[0].type != 0: continue
            out[n] = (bytes(X.sections[0].data), bytes(P.sections[0].data), slots(X.sections[0], 'be') | slots(P.sections[0], 'le'))
        _ST['l7'] = out
    return _ST['l7']


def level_twin(lx):
    """(name, equal words, non-zero words, Xbox Level, PC Level, slots) of the best l7 twin of a DLC Level (Xbox bytes)
    with >= TWIN_MIN of its non-zero words (and >= TWIN_MIN_WORDS) equal at the same offset, or None"""
    nz = sum(1 for w in range(len(lx) // 4) if lx[4 * w:4 * w + 4] != b'\0\0\0\0')
    best = None
    for n, (bx, bp, sl) in l7_levels().items():
        m = min(len(bx), len(lx)) // 4
        eq = sum(1 for w in range(m) if bx[4 * w:4 * w + 4] == lx[4 * w:4 * w + 4] and bx[4 * w:4 * w + 4] != b'\0\0\0\0')
        if best is None or eq > best[1]: best = (n, eq, nz, bx, bp, sl)
    if best is None or not nz or best[1] < TWIN_MIN * nz or best[1] < TWIN_MIN_WORDS: return None
    return best


def root_twin_words(XD, ux, px, pp, w):
    """root +0xa4 block +0x90 / +0x94 of a DLC unit DTP from the unit's base twin (the l7 unit that is the leveltwin
    twin of the DLC Level): where the DLC Xbox word equals the twin's Xbox word, w[offset] = the twin's PC word (bytes).
    -> notes"""
    if not XD.sections or XD.sections[0].type != 0: return []
    tw = level_twin(bytes(XD.sections[0].data))
    if tw is None: return []
    X, P = base_unit(tw[0])
    if X is None or P is None: return []
    kx, kp = unit_dtp(X, 'be'), unit_dtp(P, 'le')
    if kx is None or kp is None: return []
    bx, bp = X.sections[kx], P.sections[kp]
    bpx, bpp = dict(R.parse(bytes(bx.reloc), 'be').internal), dict(R.parse(bytes(bp.reloc), 'le').internal)
    rbx, rb, brx, brp = px.get(0xa4), pp.get(0xa4), bpx.get(0xa4), bpp.get(0xa4)
    if None in (rbx, rb, brx, brp) or rbx != rb: return []
    xd, bxd, bpd = bytes(ux.data), bytes(bx.data), bytes(bp.data)
    out = []
    for q in (0x90, 0x94):
        xw, twx, twp = xd[rbx + q:rbx + q + 4], bxd[brx + q:brx + q + 4], bpd[brp + q:brp + q + 4]
        if len(xw) == 4 and xw == twx and byteorder(twx, twp):
            w[rb + q] = twp
            out.append('root block +%#x: Xbox %s = twin %s Xbox -> twin PC %s' % (q, xw.hex(), tw[0], twp.hex()))
    return out


# ------------------------------------------------------------------------------------------------ unit-DTP path table
def xperm(w, c): return bytes(w[i] for i in XPERMS[c])


def fits(x, p):
    """the byte orders of XPERMS that turn the Xbox word x into the PC word p (empty = 'other')"""
    return frozenset(c for c in XPERMS if xperm(x, c) == p)


def objlist(n):
    d = {}
    for l in open(os.path.join(LISTS, n), encoding='latin-1').read().splitlines()[1:]:
        if ',' in l:
            i, s = l.split(',', 1); d[int(i)] = s.strip()
    return d


def dlc_names():
    """object id -> name for DLC units: Xbox base list + pack10 + pack11 (they agree on every common id)"""
    if 'dn' not in _ST:
        d = objlist('xbox_objectlist.txt')
        for n in ('dlc_pack10_objectlist.txt', 'dlc_pack11_objectlist.txt'):
            if os.path.exists(os.path.join(LISTS, n)): d.update(objlist(n))
        _ST['dn'] = d
    return _ST['dn']


def labels(data, ptr, intr, name_of):
    """{region start: (label, size)}, start(o): every pointer-target region of a unit DTP labelled by its pointer path
    (BFS from the root; the intro array = ('intros',); a region reached from intro k at intro offset r = (object name of
    intro k, 'i+r'); from region L at offset r = L + ('+r',)) - 17o regions.labels"""
    import bisect
    T = sorted(set(ptr.values()) | {0})
    T = [t for t in T if t < len(data)]
    size = {t: (T[i + 1] if i + 1 < len(T) else len(data)) - t for i, t in enumerate(T)}

    def start(o):
        i = bisect.bisect_right(T, o) - 1
        return T[i] if i >= 0 else 0
    ia = ptr.get(0x10); n = len(intr)
    lab = {0: ('root',)}
    if ia is not None: lab[ia] = ('intros',)
    src = collections.defaultdict(list)
    for s, t in ptr.items(): src[start(s)].append((s, t))
    q = collections.deque([0] + ([ia] if ia is not None else []))
    while q:
        rs = q.popleft(); L = lab[rs]
        for s, t in sorted(src.get(rs, [])):
            if t not in size or t in lab: continue
            if L == ('intros',) and ia is not None and ia <= s < ia + 0x90 * n:
                k, r = divmod(s - ia, 0x90); lab[t] = (name_of(k), 'i+%x' % r)
            else:
                lab[t] = L + ('+%x' % (s - rs),)
            q.append(t)
    return {t: (lab.get(t, ('unreached',)), size[t]) for t in T}, start


def alias(n):
    for a, b in (('_dlc2_', ''), ('_dlc1_', ''), ('_dlc_', ''), ('dlc2_', ''), ('dlc1_', ''), ('dlc_', '')):
        if a in n: n = n.replace(a, b)
    return n.strip('_')


def shape(w):
    """zero / non-zero mask of the four bytes (the table's votes come only from base samples of the DLC word's shape)"""
    return (w[0] != 0, w[1] != 0, w[2] != 0, w[3] != 0)


class Votes:
    """byte-order votes of one table key (17o stat2.Stat2, strict, 18e: shape votes): decided for an Xbox word when the
    intersection of all sample sets gives one wanted word, no sample is 'other' and >= TABLE_MIN samples OF THE SAME
    BYTE SHAPE as the word alone fix that word (18e: without the shape condition the table typed DLC words the base
    never showed in that shape - triggervolume +0x24 / +0x3c 01000000 from base 00000001 samples)"""
    __slots__ = ('f', 'units', 'other')

    def __init__(self): self.f = collections.Counter(); self.units = set(); self.other = 0

    def add(self, f, unit, sh):
        self.units.add(unit)
        if not f: self.other += 1
        else: self.f[(f, sh)] += 1

    def decide_for(self, xw):
        if not self.f and not self.other: return None, 'no sample'
        C = None
        for f, sh in self.f: C = set(f) if C is None else C & f
        if self.other or not C: return None, 'contradictory'
        if len({xperm(xw, c) for c in C}) != 1: return None, 'ambiguous for this word'
        mx = shape(xw)
        v = sum(n for (f, sh), n in self.f.items() if sh == mx and len({xperm(xw, c) for c in f}) == 1)
        if v < TABLE_MIN: return None, 'too few'
        return sorted(C)[0], 'votes %d' % v


def tier_keys(lab, sz, ro):
    """17o tiers K1 / KS / KA / K3; the size-only tier KZ is NOT used (18e: it typed the float records of DLC 1
    dlc_caverns 20872 root/+20/+14/+68/+4/+b8 (0x160) and dlc_dungeon 20258 as u16 pairs from unrelated base regions
    of the same size)"""
    if lab == ('intros',): return [('K1', (lab, 0x90, ro % 0x90))]
    k = [('K1', (lab, sz, ro))]
    if lab == ('root', '+1a4') and sz % 0x100 == 0: k.append(('KS', ro % 0x100))   # as the base side (0x100 records)
    if lab[0] not in ('root', 'intros') and alias(lab[0]) != lab[0]: k.append(('KA', ((alias(lab[0]),) + lab[1:], sz, ro)))
    if len(lab) >= 2: k.append(('K3', (lab[:-1] + ('*',), sz, ro)))
    return k


def judge(T, lab, sz, ro, xw):
    """(tier, byte order or None, why): the first tier with a sample decides; a contradictory / ambiguous tier stops"""
    for tn, k in tier_keys(lab, sz, ro):
        s = T[tn].get(k)
        if s is None: continue
        c, why = s.decide_for(xw)
        if c: return tn, c, why
        if why in ('too few', 'no sample'): continue
        return tn, None, why
    return '-', None, 'no base key with votes'


def table_units():
    """[(name, Xbox unit DTP, Xbox ptr, Xbox intros, PC unit DTP, PC ptr, PC intros)] of every base unit (PC file list
    pc-w\\*.drm with a Level+0x74 unit DTP, Xbox DRM of the same name from layer1 / layer2) - 17o base_units.py"""
    if 'tu' in _ST: return _ST['tu']
    from archive import Archive
    from names import crc
    names = [l.strip()[5:] for l in open(PC_FILELIST, encoding='utf-8', errors='ignore')
             if l.lower().startswith('pc-w\\') and l.strip().lower().endswith('.drm') and '\\' not in l.strip()[5:]]
    P = Archive(PCBIG, 'le'); XA = [Archive(p, 'be') for p in XLAYERS]

    def unit_of(raw, e):
        D = DW.read(raw, e)
        k = unit_dtp(D, e)
        if k is None: return None
        u = D.sections[k]
        I, ptr = intros(u, e)
        return u, ptr, I
    out = []
    for n in names:
        r = P.find(crc('pc-w\\' + n), 0xffffffff) or P.find(crc('pc-w\\' + n))
        if not r: continue
        try: pu = unit_of(P.read(r[0]), 'le')
        except Exception: continue
        if pu is None: continue
        xu = None
        for A in XA:
            q = A.find(crc('xenon-w\\' + n), 0xffffffff) or A.find(crc('xenon-w\\' + n))
            if q:
                try: xu = unit_of(A.read(q[0]), 'be')
                except Exception: pass
                break
        if xu is None: continue
        out.append((n, xu[0], xu[1], xu[2], pu[0], pu[1], pu[2]))
    _ST['tu'] = out
    return out


def table_samples():
    """[(unit, label, region size, region offset, Xbox word, fit set)] of the base units with the same intro count and
    the same intro object names on both sides; region pairs = same label + size; pointer words skipped"""
    if 'ts' in _ST: return _ST['ts']
    xn, pn = objlist('xbox_objectlist.txt'), objlist('pc_objectlist.txt')
    out = []
    for name, ux, px, IX, up, pp, IP in table_units():
        if len(IX) != len(IP) or any(xn.get(a[1]) != pn.get(b[1]) for a, b in zip(IX, IP)): continue
        xd, pd = bytes(ux.data), bytes(up.data)
        LX, _ = labels(xd, px, IX, lambda k: xn.get(IX[k][1], '?'))
        LP, _ = labels(pd, pp, IP, lambda k: pn.get(IP[k][1], '?'))
        bx = {v[0]: (t, v[1]) for t, v in LX.items()}; bp = {v[0]: (t, v[1]) for t, v in LP.items()}
        for lab in set(bx) & set(bp):
            (tx, zx), (tp, zp) = bx[lab], bp[lab]
            if zx != zp or lab == ('unreached',): continue
            for w in range(0, zp - 3, 4):
                if tx + w in px or tp + w in pp: continue
                xw = xd[tx + w:tx + w + 4]
                out.append((name, lab, zp, w, xw, fits(xw, pd[tp + w:tp + w + 4])))
    _ST['ts'] = out
    return out


def path_table():
    """{tier: {key: Votes}} over all base samples"""
    if 'pt' in _ST: return _ST['pt']
    T = {k: collections.defaultdict(Votes) for k in ('K1', 'KS', 'K3')}
    for un, lab, zp, w, xw, f in table_samples():
        sh = shape(xw)
        if lab == ('intros',): T['K1'][(lab, 0x90, w % 0x90)].add(f, un, sh); continue
        T['K1'][(lab, zp, w)].add(f, un, sh)
        if lab == ('root', '+1a4') and zp % 0x100 == 0: T['KS'][w % 0x100].add(f, un, sh)
        if len(lab) >= 2: T['K3'][(lab[:-1] + ('*',), zp, w)].add(f, un, sh)
    T = {k: dict(v) for k, v in T.items()}
    T['KA'] = T['K1']
    _ST['pt'] = T
    return T


def table_loo():
    """leave-one-unit-out per tier: {tier: (held-out decided samples, wrong)} (17o d4_table.loo)"""
    idx = {k: collections.defaultdict(lambda: collections.defaultdict(list)) for k in ('K1', 'KS', 'K3')}
    for un, lab, zp, w, xw, f in table_samples():
        ks = [('K1', (lab, 0x90, w % 0x90))] if lab == ('intros',) else [('K1', (lab, zp, w))]
        if lab == ('root', '+1a4') and zp % 0x100 == 0: ks.append(('KS', w % 0x100))
        if lab != ('intros',) and len(lab) >= 2: ks.append(('K3', (lab[:-1] + ('*',), zp, w)))
        for tn, k in ks: idx[tn][k][un].append((xw, f))
    res = {}
    for tn, K in idx.items():
        right = wrong = 0
        for k, byu in K.items():
            if len(byu) < 2: continue
            for un, mine in byu.items():
                st = Votes()
                for o, lst in byu.items():
                    if o != un:
                        for xw, f in lst: st.add(f, o, shape(xw))
                for xw, f in mine:
                    if f and len({xperm(xw, c) for c in f}) != 1: continue      # held-out sample not informative
                    c, why = st.decide_for(xw)
                    if not c: continue
                    if f and xperm(xw, c) == xperm(xw, next(iter(f))): right += 1
                    else: wrong += 1
        res[tn] = (right + wrong, wrong)
    return res


def table_words(XD, PD, kx, kp, IX, px, IP, pp):
    """{offset: wanted PC word} of the unit DTP by the path table (labels from the PC section, intro names from the
    Xbox intros), {tier: n}, notes"""
    T = path_table(); nm = dlc_names()
    u, ux = PD.sections[kp], XD.sections[kx]
    pd, xd = bytes(u.data), bytes(ux.data)
    L, start = labels(pd, pp, IP, lambda k: nm.get(IX[k][1], '?x%d' % IX[k][1]))
    out = {}; tiers = collections.Counter(); notes = []
    for o in range(0, len(pd) - 3, 4):
        if o in pp: continue
        rs = start(o); lab, sz = L[rs]
        if lab == ('unreached',): continue
        xw = xd[o:o + 4]
        tn, c, why = judge(T, lab, sz, o - rs, xw)
        if not c: continue
        if (u.id, o) in TABLE_EXCLUDE:
            notes.append('unit DTP %d +%#x: %s - left alone' % (u.id, o, TABLE_EXCLUDE[(u.id, o)])); continue
        out[o] = xperm(xw, c); tiers[tn] += 1
    return out, tiers, notes


# ------------------------------------------------------------------------------------------------ particle records
def fx_base_records():
    """[(object, Xbox record bytes, PC record bytes, slot offsets)] of the base objects (PC objectlist ids 1..821, Xbox /
    PC object data DTP named at object +8, same record count) - 17o p1_base.py / objdata_rec_classes calibrate"""
    if 'fb' in _ST: return _ST['fb']
    import objdata_rec_classes as RC
    import pairs as P
    names = []
    for ln in open(os.path.join(LISTS, 'pc_objectlist.txt'), encoding='latin-1').read().splitlines()[1:]:
        if ',' in ln:
            i, n = ln.split(',', 1)
            if int(i) <= 821: names.append(n.strip())
    get = lambda s: (s['type'], s['data'], s['reloc'], s['id'])
    out = []
    for n in names:
        try:
            xd_ = P.xbox_drm(n + '.drm'); pd_ = P.pc_drm(n + '.drm')
        except Exception:
            continue
        if not xd_ or not pd_: continue
        xs, ps = xd_[1], pd_[1]
        xi, pi = RC.objdata_dtps(xs, 'be', get), RC.objdata_dtps(ps, 'le', get)
        if not xi or not pi: continue
        xsec = [s for s in xs if s['type'] == 7 and s['id'] == xi[0]]
        psec = [s for s in ps if s['type'] == 7 and s['id'] == pi[0]]
        if not xsec or not psec: continue
        xr, xsl = RC.records(xsec[0]['data'], 'be', xsec[0]['reloc'])
        pr, psl = RC.records(psec[0]['data'], 'le', psec[0]['reloc'])
        if not xr or not pr or len(xr) != len(pr): continue
        xd, pd = xsec[0]['data'], psec[0]['data']
        for bx, bp in zip(xr, pr):
            sl = {o for o in range(0, FX_REC, 4) if (bx + o) in xsl or (bp + o) in psl}
            out.append((n, xd[bx:bx + FX_REC], pd[bp:bp + FX_REC], sl))
    _ST['fb'] = out
    return out


# ------------------------------------------------------------------------------------------------ proofs
def proof_counts(rule):
    """base-pair statistics of one rule -> dict (contra = base words that contradict the rule)"""
    got = collections.Counter()
    if rule == 'fadecard':
        for x, p, xb, pc in base_pairs7():
            fw = fade_words(xb['data'])
            if not fw: continue
            got['dtps'] += 1; got['records'] += (len(fw) - 1) // 3
            for o, c in fw.items():
                k = cls(xb['data'][o:o + 4], pc['data'][o:o + 4])
                got['ok' if k == c else 'amb' if k == 'amb' else 'contra'] += 1
    elif rule == 'uberanim':
        for x, p, xb, pc in base_pairs7():
            if R.parse(xb['reloc'], 'be').internal != R.parse(pc['reloc'], 'le').internal: continue
            ws = uber_words(pc['data'], pc['reloc'], 'le')
            if not ws: continue
            got['dtps'] += 1
            for o in ws:
                k = cls(xb['data'][o:o + 4], pc['data'][o:o + 4])
                got['ok' if k == 's16' else 'amb' if k == 'amb' else 'contra'] += 1
    elif rule == 'sgmesh':
        for x, p, xb, pc in base_pairs7():
            sw = sgmesh_words(xb['data'], xb['reloc'])
            if not sw: continue
            got['dtps'] += 1
            for o, c in sw.items():
                k = cls(xb['data'][o:o + 4], pc['data'][o:o + 4])
                got['ok' if k == c else 'amb' if k == 'amb' else 'contra'] += 1
    elif rule == 'fxrec':
        for x, p, xb, pc in base_pairs7():
            xd = xb['data']
            if FX_ANCHOR not in xd: continue
            sl = slots(xb, 'be') | slots(pc, 'le')
            fw = {o: c for o, c in fx_words(xd).items() if o not in sl}
            got['records'] += sum(1 for q in range(0, len(xd), 4) if xd[q:q + 20] == FX_ANCHOR)
            for o, c in fw.items():
                k = cls(xd[o:o + 4], pc['data'][o:o + 4])
                got['ok' if k == c else 'contra'] += 1
    elif rule == 'basecopy':
        # global DTP ids: one Xbox content in the base game -> one PC content (every PC copy of the id is the same)
        st, ids, pcn = store()
        for (t, x), hs in st['xb_hash'].items():
            if t != 7 or len(hs) != 1: continue
            p = ids.base[7].get(x)
            if p is None or not pcn.get(p): continue
            got['ids_one_xbox_content'] += 1
            got['ok' if pcn[p] == 1 else 'contra'] += 1
    elif rule == 'leveltwin':
        # same Xbox word at the same Level offset of two base units -> the same PC word (byte permutation)
        L = l7_levels(); names = sorted(L)
        got['units'] = len(names)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                xa, pa, sa = L[a]; xb, pb, sb = L[b]
                for w in range(min(len(xa), len(xb), len(pa), len(pb)) // 4):
                    o = 4 * w
                    if o in sa or o in sb: continue
                    wa = xa[o:o + 4]
                    if wa != xb[o:o + 4] or wa == b'\0\0\0\0': continue
                    if not (byteorder(wa, pa[o:o + 4]) and byteorder(wa, pb[o:o + 4])): got['not_perm'] += 1; continue
                    got['ok' if pa[o:o + 4] == pb[o:o + 4] else 'contra'] += 1
    elif rule == 'introtyped':
        i7c, rules, root, strs, st = intro_table()
        got.update({'units': st['units'], 'intros': st['intros'], 'keys': st['keys'], 'keys_with_rules': st['keys_with_rules'],
                    'rule_words': st['rule_words']})
        got['i7c_u32'] = i7c['s32'] + i7c['other'] + i7c['amb']; got['contra'] += i7c['s16'] + i7c['raw'] + i7c['perm']
        # root +0xa4 block +0x90 / +0x94: no rule (the base units disagree) - counted for the record only
        got['root_block_not_one_order'] = int(len({k for k in root if k != 'amb'}) > 1)
        got['string_raw'] = strs['raw'] + strs['amb']; got['contra'] += sum(v for k, v in strs.items() if k not in ('raw', 'amb'))
        # unit-DTP path table (18e, 17o d4_table): base units / samples / keys and the leave-one-unit-out result per
        # tier (held-out decided samples, wrong) - pinned like every other count
        got['tbl_units_all'] = len(table_units())
        S = table_samples(); got['tbl_units'] = len({s[0] for s in S}); got['tbl_samples'] = len(S)
        T = path_table()
        for tn in ('K1', 'KS', 'K3'): got['tbl_keys_' + tn] = len(T[tn])
        for tn, (n, bad) in sorted(table_loo().items()): got['loo_%s_n' % tn] = n; got['loo_%s_wrong' % tn] = bad
    elif rule == 'fxrecread':
        # every base particle record word at an FXREAD offset: PC word == the reader's byte order of the Xbox word
        # (ok; amb = the Xbox word reads the same in every byte order), else contra; objrec must not rule the offset
        import objdata_rec_classes as RC
        ruled = pickle.load(open(RC.RULES, 'rb')) if os.path.exists(RC.RULES) else None
        got['objrec_overlap'] = len(set(FXREAD) & set(ruled)) if ruled is not None else -1
        if got['objrec_overlap'] > 0: got['contra'] += got['objrec_overlap']
        B = fx_base_records()
        got['objects'] = len({b[0] for b in B}); got['records'] = len(B)
        for n, xr, pr, sl in B:
            for o, c in FXREAD.items():
                if o in sl: got['slot'] += 1; continue
                xw, pw = xr[o:o + 4], pr[o:o + 4]
                if pw != xperm(xw, c): got['contra'] += 1
                elif len({xperm(xw, k) for k in XPERMS}) == 1: got['amb'] += 1
                else: got['ok'] += 1
    got.setdefault('contra', 0)
    return dict(got)


def proof(rules=None, strict=True, report=None):
    res = {}; ok = True
    for r in rules or RULES:
        got = proof_counts(r)
        exp = (PROOF_EXPECT or {}).get(r)
        good = got.get('contra', 0) == 0 and (exp is None or got == exp)
        ok = ok and good and exp is not None
        res[r] = dict(got=got, expect=exp, ok=good)
        print('%-10s %s  %s%s' % (r, 'PROVEN' if good and exp is not None else ('CALIBRATE' if exp is None else 'FAILED'),
                                  got, '' if exp is None or got == exp else ' (expected %s)' % exp), flush=True)
    print('proof: %s' % ('every rule holds on the base pairs' if ok else 'FAILED'))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(res, open(report, 'w', encoding='utf-8'), indent=1)
    return 0 if ok or not strict else 1


_PROVEN = {}


def proven(rule):
    """the base proof of one rule once per process (stdout kept quiet) -> (ok, lines)"""
    if rule not in _PROVEN:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = proof([rule], True)
        _PROVEN[rule] = (rc == 0, [l[:300] for l in buf.getvalue().splitlines()])
    return _PROVEN[rule]


# ------------------------------------------------------------------------------------------------ plan one DRM
def _want_rows(k, x, p, words, rows, kept, tag, sl):
    """words {offset: class or bytes}: rows += (k, off, xw, pw, want, tag) where the PC word is another byte order of
    the Xbox word; kept += the ones that are no byte order"""
    xd, pd = bytes(x.data), bytes(p.data)
    for o, c in sorted(words.items()):
        if o in sl or o + 4 > len(xd) or o + 4 > len(pd): continue
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        want = perm(xw, c) if isinstance(c, str) else c
        if pw == want: continue
        if byteorder(xw, pw) and byteorder(xw, want): rows.append((k, o, xw, pw, want, tag))
        else: kept.append((k, o, xw, pw, want, tag))


def plan(rule, XD, PD, rel=''):
    """-> dict(rows=[(PC section index, offset, Xbox word, PC word, wanted word, tag)], kept=[...], notes=[...])"""
    rows, kept, notes = [], [], []
    if rule in ('fadecard', 'uberanim', 'sgmesh', 'fxrec'):
        for k, x, p in pairs(XD, PD):
            if x.type != 7 or p.type != 7 or x.id != p.id or len(x.data) != len(p.data): continue
            xd = bytes(x.data)
            if rule == 'fadecard': w = fade_words(xd)
            elif rule == 'sgmesh': w = sgmesh_words(xd, bytes(x.reloc))
            elif rule == 'fxrec': w = fx_words(xd) if FX_ANCHOR in xd else {}
            else:
                if UBER_MAGIC.to_bytes(4, 'little') not in bytes(p.data): continue
                w = {o: 's16' for o in uber_words(bytes(p.data), bytes(p.reloc), 'le')}
                if w and R.parse(bytes(x.reloc), 'be').internal != R.parse(bytes(p.reloc), 'le').internal:
                    notes.append('DTP %d: uber relocations differ from the Xbox section - skipped' % p.id); continue
            if w: _want_rows(k, x, p, w, rows, kept, '%s DTP %d' % (rule, p.id), slots(x, 'be') | slots(p, 'le'))
    elif rule == 'basecopy':
        st, ids, pcn = store()
        for k, x, p in pairs(XD, PD):
            if x.type != 7 or p.type != 7: continue
            xb = st['xb_store'].get((7, x.id))
            if xb is None: continue
            xd, bxd = bytes(x.data), xb['data']
            tr = None
            if xd != bxd:
                tr = trailer_at(xd)
                if tr is None or tr != len(bxd) or xd[:tr] != bxd: continue
            pid = ids.base[7].get(x.id)
            if pid is None or p.id != pid: continue
            why = None
            if len(st['xb_hash'].get((7, x.id), ())) != 1: why = 'several Xbox base contents'
            elif pcn.get(pid) != 1: why = '%s PC base contents' % pcn.get(pid, 0)
            pb = st['pc_store'].get((7, pid))
            if why is None and (pb is None or len(pb['data']) != len(bxd)): why = 'PC base copy of another size'
            if why is None and len(p.data) != len(xd): why = 'PC section of another size than the Xbox section'
            if why is None:
                pr = R.parse(bytes(p.reloc), 'le'); br = R.parse(pb['reloc'], 'le')
                n = len(bxd)
                if sorted(q for q in pr.internal if q[0] < n) != sorted(br.internal) or \
                        sorted((t, o) for t, o in pr.idref if o < n) != sorted(br.idref) or \
                        sorted((t, o) for t, o in pr.idref_a if o < n) != sorted(br.idref_a):
                    why = 'payload relocations differ from the PC base copy'
            if why:
                notes.append('DTP %d (Xbox %d): Xbox = base copy, %s - skipped' % (p.id, x.id, why)); continue
            w = {o: pb['data'][o:o + 4] for o in range(0, len(bxd) - 3, 4)}
            _want_rows(k, x, p, w, rows, kept, 'basecopy DTP %d (Xbox %d%s)' % (p.id, x.id, ', trailer kept' if tr else ''),
                       slots(p, 'le'))
    elif rule == 'leveltwin':
        if not PD.sections or PD.sections[0].type != 0 or not XD.sections or XD.sections[0].type != 0: return dict(rows=rows, kept=kept, notes=notes)
        x, p = XD.sections[0], PD.sections[0]
        lx = bytes(x.data)
        if len(lx) != len(p.data):
            notes.append('Level: PC size %#x != Xbox %#x - skipped' % (len(p.data), len(lx))); return dict(rows=rows, kept=kept, notes=notes)
        tw = level_twin(lx)
        if tw is None: return dict(rows=rows, kept=kept, notes=notes)
        n, eq, nz, bx, bp, bsl = tw
        if len(bx) == len(lx): return dict(rows=rows, kept=kept, notes=notes)      # same-size twin: not this rule
        sl = slots(x, 'be') | slots(p, 'le') | bsl
        import navgraph_raw_fix as NR
        img = NR.image_loc(PD, 'le')
        lim = img[1] if img is not None and img[0] == 0 else len(lx)
        w = {}
        for o in range(0, min(len(lx), len(bx), len(bp), lim) - 3, 4):
            if lx[o:o + 4] == bx[o:o + 4] and byteorder(bx[o:o + 4], bp[o:o + 4]): w[o] = bp[o:o + 4]
            # 2026-11-09 (Befund-0813-Rueckschritt-0911): another non-zero Xbox value at an offset whose twin pair is
            # s32 -> s32 as well (dlc_yggdrasil_end Level +0x148 / +0x168 / +0x178 / +0x188, float z ~10645: the generic
            # route wrote u16 pairs; = installed tree = B270; the generic route already agrees with the twin's s32 at
            # every other such word of the unit). _want_rows changes it only when the PC word is a byte order of it.
            elif lx[o:o + 4] != b'\0\0\0\0' and cls(bx[o:o + 4], bp[o:o + 4]) == 's32': w[o] = 's32'
        notes.append('Level twin %s (%d of %d non-zero Xbox words equal at the same offset, Level %#x vs %#x%s)' % (
            n, eq, nz, len(lx), len(bx), ', NavGraph image from %#x left to navraw' % lim if lim < len(lx) else ''))
        _want_rows(0, x, p, w, rows, kept, 'leveltwin %s' % n, sl)
    elif rule == 'introtyped':
        kp, kx = unit_dtp(PD, 'le'), unit_dtp(XD, 'be')
        if kp is None or kx is None: return dict(rows=rows, kept=kept, notes=notes)
        u, ux = PD.sections[kp], XD.sections[kx]
        if u.id != ux.id:      # renumbered base unit DTP (the converter's base id map): the PC game's own section
            notes.append('unit DTP %d = Xbox %d (base-mapped) - left alone' % (u.id, ux.id))
            return dict(rows=rows, kept=kept, notes=notes)
        if len(u.data) != len(ux.data):
            notes.append('unit DTP %d: Xbox %d B / PC %d B (other layout) - skipped' % (u.id, len(ux.data), len(u.data)))
            return dict(rows=rows, kept=kept, notes=notes)
        IP, pp = intros(u, 'le'); IX, px = intros(ux, 'be')
        if [(o, dp, sz) for o, ob, dp, sz in IP] != [(o, dp, sz) for o, ob, dp, sz in IX]:
            notes.append('unit DTP %d: intro layout differs from the Xbox section - skipped' % u.id)
            return dict(rows=rows, kept=kept, notes=notes)
        i7c, rules, root, strs, st = intro_table()
        w = {}
        for o, obj, dp, sz in IP:
            w[o + 0x7c] = 's32'
            for q, c in rules.get((obj, sz), {}).items(): w.setdefault(dp + q, c)
        for q in name_strings(bytes(ux.data), px): w.setdefault(q, 'raw')
        # 2026-11-09: root +0xa4 block +0x90 / +0x94 - no rule over the base units (they disagree), but the unit's own
        # base twin (the leveltwin twin of its Level) decides when its Xbox word is the same: then the twin's PC word
        # (dlc_yggdrasil_end 21218 +0x14f04 = l7_yggdrasil_end 18550: Xbox 02000000 -> PC 02000000 raw; 0813 wrote s32)
        notes.extend(root_twin_words(XD, ux, px, pp, w))
        sl = slots(ux, 'be') | slots(u, 'le')
        _want_rows(kp, ux, u, w, rows, kept, 'introtyped DTP %d' % u.id, sl)
        # the unit-DTP path table (18e) where the rules above do not speak
        tw, tiers, tn = table_words(XD, PD, kx, kp, IX, px, IP, pp)
        notes.extend(tn)
        tw = {o: v for o, v in tw.items() if o not in w}
        _want_rows(kp, ux, u, tw, rows, kept, 'introtyped DTP %d table' % u.id, sl)
    elif rule == 'fxrecread':
        import objdata_fx_fix as OF, objdata_rec_classes as RC
        ids = sorted(set(OF.od_ids(PD, 'le')) & set(OF.od_ids(XD, 'be')))
        idx = {id(s): k for k, s in enumerate(PD.sections)}
        for did in ids:
            pc = OF.pair_copies(OF.copies(XD, did), OF.copies(PD, did))
            if pc is None:
                notes.append('DTP %d: copies Xbox %d / PC %d cannot be paired - skipped' % (
                    did, len(OF.copies(XD, did)), len(OF.copies(PD, did)))); continue
            for c, (xs, ps) in enumerate(pc):
                k = idx[id(ps)]
                xr, xsl = RC.records(bytes(xs.data), 'be', bytes(xs.reloc))
                pr, psl = RC.records(bytes(ps.data), 'le', bytes(ps.reloc))
                if not xr and not pr: continue
                if not xr or not pr or len(xr) != len(pr):
                    notes.append('DTP %d copy %d: record lists differ (Xbox %s, PC %s) - skipped' % (
                        did, c, None if xr is None else len(xr), None if pr is None else len(pr))); continue
                xd, pd = bytes(xs.data), bytes(ps.data)
                for j, (bx, bp) in enumerate(zip(xr, pr)):
                    for o, cl in sorted(FXREAD.items()):
                        if (bx + o) in xsl or (bp + o) in psl or bx + o + 4 > len(xd) or bp + o + 4 > len(pd): continue
                        xw, pw = xd[bx + o:bx + o + 4], pd[bp + o:bp + o + 4]
                        want = xperm(xw, cl)
                        if pw == want: continue
                        t = (k, bp + o, xw, pw, want, 'fxrecread DTP %d copy %d rec %d +%#x %s' % (did, c, j, o, cl))
                        (rows if byteorder(xw, pw) and byteorder(xw, want) else kept).append(t)
    else:
        raise SystemExit('rule? %s' % rule)
    return dict(rows=rows, kept=kept, notes=notes)


def fix_drm(rule, XD, raw, rel=''):
    """-> (new raw or None, changes [(k, offset, old, new, section id, tag)], info). The base proof of the rule must hold
    (SystemExit otherwise). Proven write: decoded bytes differ only in the planned bytes, headers / relocations / names
    identical, re-plan 0 rows - AssertionError otherwise (the caller keeps its DRM)."""
    ok, lines = proven(rule)
    if not ok: raise SystemExit('%s: base proof FAILED - %s' % (rule, ' / '.join(lines[-2:])))
    PD = DW.read(raw, 'le')
    info = plan(rule, XD, PD, rel)
    if not info['rows']: return None, [], info
    changes = []
    for k, o, xw, pw, want, tag in info['rows']:
        s = PD.sections[k]; d = bytearray(s.data)
        assert bytes(d[o:o + 4]) == pw
        d[o:o + 4] = want; s.data = bytes(d)
        changes.append((k, o, pw, want, s.id, tag))
    out = PD.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    dec0, dec1 = DW.cdrm_decode(raw, 'le'), DW.cdrm_decode(out, 'le')
    D0, D1 = DW.read(raw, 'le'), DW.read(out, 'le')
    assert D0.write('le') == bytes(dec0), 'writer not lossless'
    assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections), 'size / section count changed'
    assert (D0.names, D0.pad, D0.ver, D0.u0, D0.u1) == (D1.names, D1.pad, D1.ver, D1.u0, D1.u1), 'file header changed'
    base = 24 + 20 * len(D0.sections) + len(D0.names) + len(D0.pad); bases = []
    for a, b in zip(D0.sections, D1.sections):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, a.reloc, len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, b.reloc, len(b.data)), 'section header / relocation changed'
        bases.append(base + len(a.reloc)); base += len(a.reloc) + len(a.data)
    planned = {bases[k] + o + j for k, o, a, b, sid, tag in changes for j in range(4) if a[j] != b[j]}
    diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
    assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
    again = plan(rule, XD, D1, rel)
    assert not again['rows'], 're-plan %d rows' % len(again['rows'])
    return out, changes, info


# ------------------------------------------------------------------------------------------------ CLI
def main(argv):
    a = list(argv)
    rules = list(RULES)
    if '--rules' in a: k = a.index('--rules'); rules = a[k + 1].split(','); del a[k:k + 2]
    rep = None
    if '--report' in a: k = a.index('--report'); rep = a[k + 1]; del a[k:k + 2]
    if '--pack' in a: k = a.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = a[k + 1]; del a[k:k + 2]
    names = None
    if '--names' in a: k = a.index('--names'); names = set(a[k + 1].split(',')); del a[k:k + 2]
    if any(r not in RULES for r in rules): raise SystemExit(__doc__)
    if a == ['proof']: sys.exit(proof(rules, True, rep))
    if len(a) != 2 or a[0] != 'scan': raise SystemExit(__doc__)
    import dtp_audit as DA
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    tot = collections.Counter(); bad = 0; out = []
    for rel, path in sorted(DA.overlay([os.path.abspath(t) for t in a[1].split(',')], names).items()):
        xr, src = raw_dlc(rel.replace('/', '\\'))
        if xr is None: xr, src = raw_dlc(os.path.basename(rel))
        if xr is None: continue
        XD = DW.read(cdrm_decode(xr, 'be'), 'be'); raw = open(path, 'rb').read()
        for r in rules:
            new, ch, info = fix_drm(r, XD, raw, rel)
            if ch or info['kept'] or info['notes']:
                line = '%-10s %-55s %d words, %d kept (no byte order)%s' % (r, rel, len(ch), len(info['kept']),
                                                                         ('; ' + '; '.join(info['notes'])) if info['notes'] else '')
                print(line, flush=True); out.append(dict(rule=r, rel=rel, words=len(ch), kept=len(info['kept']), notes=info['notes'],
                                                         changes=['%d +%#x %s -> %s' % (c[4], c[1], c[2].hex(), c[3].hex()) for c in ch]))
            tot[r] += len(ch); bad += 1 if ch else 0
    print('scan: %s' % dict(tot))
    if rep: json.dump(out, open(rep, 'w', encoding='utf-8'), indent=1)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
