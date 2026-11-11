"""generalbank.drm for the DLC port from the player's PC original (patch.000) + recorded knowledge + our ring menu - no
kit file, no Xbox data on the player's side (night package Q2, 2026-11-11; docs Befund-Generalbank-PC-Basis-1111.md).

Until now the Generalbank step (tools/generalbank_build.py, 23 steps + K12) started from the B138 kit's generalbank and
converted title-update sections with two runs of the generic converter (Xbox base game + TitleUpdate.000). The
installed, live-tested file (ring tree 7, md5 b8b1eb71...) differs from the PC patch.000 generalbank in 14 of 1 265
sections; every one is reproduced here:

  class          sections                              origin (developer chain)                         here
  kit_b138_tu    DTP 36 (+688 B, extras list),         B138 kit = PC + title-update edits (DTP 36 = TU   knowledge
                 script 72 (3 words)                   DTP 37 growth; script 72 = TU script 72 chapter
                                                       records, Xbox 441 / 104 / 104 -> locmap 482 / 127)
  kit_b138_menu  script 7: P3 (member 0xc4c 163 ->     tools/menu_dlc_patch.py P3 (B90 menu_dlc_B);      recipe P3 here,
                 130) + the three slot-7 sites in      the sites in the kit's `b138` form (B132           sites: ring D1
                 the `b138` form + 3 call relocations  pause-menu QUIT) - the ring step D1 rewrites them
  pipeline_tu    scripts 6, 9, new 21239 / 20082,      tools/generalbank_build.py steps 1-23            knowledge
                 script 104, DTP 47                    (TU loading screen, hint box, mission screen
                                                       style, S104, the 6 TU input bindings)
  k12            DTP 2 (+60 B)                         tools/globalinfo_player_list_fix.py (TU list    knowledge
                                                       of 29 player ids, + 857)
  hud_tu         scripts 37 / 213, new textures        tools/generalbank_hud_build.py (R6, shadow       knowledge
                 7899 / 7036                           meter HUD; tree dlc_test50l_hud_input)
  ring_p14       script 7                              tools/menu_ring_p14.py build (tree 7, live       sub-step (same
                                                       10.11.: QUIT on position 14, DLC on slot 7)      tool, in-process)
  tu_camera      new DTPs 21237 / 21238 / 22194        tools/tu_camera_dtp.py (TU doppelganger camera   knowledge, added
                 (after the ring, not in tree 7)       settings + their curve records; 2026-11-11)      after the ring

Knowledge file (docs/data/generalbank_pc.json, schema 3, written by `learn`; owner decision 2026-11-10: the repository
holds NO copies of game data, only references, rules and hashes): per section a SOURCE table (sections of the player's
own files, each with its md5: `pc:T:ID` = the PC patch.000 generalbank, `tu:T:ID` = the Xbox title update
TitleUpdate.000 generalbank, `tex:T:ID` = tools/tex_convert.convert of that TU texture section, `xr:T:ID` = that TU
section's relocations converted to the PC file by rule, `own:NAME@T:ID+HEX` = our own recipe made by its tool) and,
for the data and the relocation blob, a word PROGRAM over them: `<src><form><byte offset>+<words>` takes words of a
source in a form (id / kp = bytes kept, sw = u32 byte swap Xbox -> PC, h = u16-pair swap, sa / sb / sab = h with the
first / second / both u16 halves mapped as cdc::Symbol), `L<n>` / `T<n>` take n residual words / tail bytes. The forms
are the word rules of the converters that made the recorded bytes (generic converter / script converter /
tex_convert / tu_camera_dtp), recorded per word run. RULES (schema 3, Q29 2026-11-11, docs
Befund-Generalbank-Rest-Regeln-1111.md): `rules.symbols` = the converter's Xbox -> PC Symbol map for the Symbols the
ported scripts use, as runs of equal delta (DataMember offset | name, userType, ScriptName words; the ported scripts
keep the Xbox data offsets); `rules.scripts` = the script ids the converter's id map renumbers (external relocation
targets). Source xr applies them to the TU relocations (target index in the result order, call offsets through
script_conv.offset_map as tools/drm_put_sections.py --xbox); own:vtable31 = tools/script_vtable_insert.py (PC slot 31),
own:dlc2_stub = tools/script_dlc2_flag_stub.py. RESIDUAL = result bytes no rule derives yet (our own values: locals
string ids of our merged table, relocation table counts, ...): up to INLINE_MAX bytes per section are kept INLINE as
hex (listed per section in the report), larger residuals only in the LOCAL knowledge file (default
../data/local/generalbank_pc.local.json, outside the repository; since K20261111-3 no section needs it and build does
not read it) - the build names the sections it cannot make without it. Every source section, residual and result is
md5-checked.

Build (player path): PC patch.000 record pc-w\\generalbank.drm (raw md5 checked against the knowledge file) + the
player's TitleUpdate.000 generalbank (raw md5 checked) -> recipe P3 -> the recorded sections -> steps/01_pc_knowledge
.drm (raw md5 checked) -> menu_ring_p14 build (in this process; its own verify runs) -> steps/02_ring.drm, md5 checked
against expect.ring_md5 (= the installed, live-tested tree 7) -> the tu_camera sections appended at the end (no other
byte moves) -> OUT/mods/generalbank.drm, md5 checked against expect.md5 (--no-tu-camera: OUT/mods = step 02 = tree 7).
Guard: an audit hook refuses (exit 2) every file open / directory listing / process start whose path names a kit, a
kit-derived tree, the installed game, the Xbox data other than TitleUpdate.000 or the reference files (KIT_PATTERNS);
every file read is listed in OUT/build_report.json.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/generalbank_pc_build.py build [OUT_DIR] [--pc PATCH000] [--tu TITLEUPDATE000]
                                                       [--knowledge JSON] [--local JSON] [--expect MD5|none]
                                                       [--no-tu-camera] [--tailoring]
        default OUT_DIR work/rebuild/generalbank_pc (replaced), -> OUT_DIR/mods/generalbank.drm, OUT_DIR/build_report.json
        --tailoring (opt-in, Q40 2026-11-11, docs Befund-Hauptmenue-Schwierigkeit-1111.md): rule tu134_tailoring on
        the result (steps/03_before_tailoring.drm = the default result): the title update's script 134 function 9
        main-menu reset of the player tailoring to Medium (print + uiexperienceadjustmentmenu f6..f10 with 1) as an
        appended block of PC script 104 function 9 before the level test; verified (tailoring-verify) and md5-checked
        against knowledge post_ring_rules; default expect = that rule's md5 / md5_no_camera
  ../bin/pyt -t 900 tools/generalbank_pc_build.py tailoring-verify BEFORE AFTER [TITLEUPDATE000]
        read-only: AFTER = BEFORE + exactly rule tu134_tailoring (only script 104; every changed old word planned:
        the site op63, instance size, f9 stackSize; members / deps pointers retargeted, everything else appended;
        AFTER = the plan; block decoded from AFTER = the TU block; shape gate: opcode 3-grams in PC scripts 104 / 121)
  ../bin/pyt -t 900 tools/generalbank_pc_build.py rules-record BUILD_OUT_DIR [--knowledge JSON] [--tu TU] [--write]
        developer: the md5s of the post-ring rules from a default build's mods/generalbank.drm + steps/02_ring.drm
        (learn records them too); --write stores them in the knowledge file (version K20261111-4)
  ../bin/pyt -t 900 tools/generalbank_pc_build.py gate FILE REFERENCE [--allow-extra T:ID,...] [--report R.json]
        read-only: header, section order and every section word by word (data + relocations), exit 1 on any difference;
        --allow-extra: these sections may exist in FILE only, at its end (the header's section count differs by them)
  ../bin/pyt -t 900 tools/generalbank_pc_build.py learn REF_PRE_RING EXPECT_FILE [--pc PATCH000] [--tu TITLEUPDATE000]
                                                       [--knowledge JSON] [--local JSON] [--add-sections DRM] [--write]
        developer: record the sections of REF_PRE_RING (the K12 + HUD file the ring was built on, md5 9a2466fe...)
        that differ from the PC file, check that script 7 differs only by P3 + the three slot-7 sites, build in memory
        and compare with EXPECT_FILE (tree 7); --add-sections: every section of DRM (tools/tu_camera_dtp.py convert)
        is recorded as a tu_camera section added after the ring; --write stores the knowledge file (+ the local file)
"""
import sys, os, re, json, struct, hashlib, time, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
KNOW = os.path.join(REPO, 'docs', 'data', 'generalbank_pc.json')
LOCAL = os.path.join(os.path.dirname(REPO), 'data', 'local', 'generalbank_pc.local.json')   # outside the repository
PC_ARCH = '../data/pc/patch.000'
PC_NAME = 'pc-w\\generalbank.drm'
TU_ARCH = '../data/TombRaiderUnderworld_Patched/TitleUpdate.000'     # the player's own title update (workspace copy)
TU_NAME = 'xenon-w\\generalbank.drm'
OUT_DEFAULT = 'work/rebuild/generalbank_pc'
VERSION = 'K20261111-4'      # knowledge version (-4, Q40: + post_ring_rules tu134_tailoring) (Plan-Spielerweg 5.2); a new learn with other content = a new version
SCHEMA = 3                   # 1 = literal copies (K20261111-1, retired 2026-11-11), 2 = references + residual
                             # (K20261111-2), 3 = 2 + rules: symbol map, script id map, converted TU relocations (xr),
                             # our own recipes (own) - the three ported scripts need no local file any more (Q29)
INLINE_MAX = 64              # residual bytes per section kept inline (small values); more -> local knowledge file
# path fragments the build must never touch (lower case, forward slashes)
KIT_PATTERNS = ('b138', 'b270', 'b269', 'b132', 'b90', '/release/', 'kit', 'pristine', 'b138_fixes', '_repair',
                'menu_dlc/', 'ring_p14_1011', 'generalbank_build', 'hud50l', 'test50l', 'datafix_0711', 'truguard')
# Xbox base game / DLC packs / emulator (the player path needs only TitleUpdate.000 of the Xbox files for this file)
XBOX_PATTERNS = ('tombraiderunderworld_patched', 'input/xbox-game', 'titleupdate', 'xenia', 'layer1.', 'layer2.')
TU_ALLOWED = set()           # realpaths of the TitleUpdate.000 given to build (exempt from XBOX_PATTERNS)
# script 7 recipe P3 (tools/menu_dlc_patch.py TEXT): init word of member 0xc4c 163 'EXIT' -> 130 'DOWNLOADABLE CONTENT'
P3_AT, P3_OLD, P3_NEW = 0x25934, 163, 130
SLOT7_WINDOWS = ((0x6288, 0x62a4), (0x9688, 0x96a4), (0x188dc, 0x188f8))     # 7 words each (menu_quit_slot_check)
SLOT7_CALLS = (0x6294, 0x9694, 0x188e8)


def md5(b):
    return hashlib.md5(bytes(b)).hexdigest()


def key(s):
    return '%d:%d' % (s.type, s.id)


# ---------------------------------------------------------------- guard
class Guard:
    """audit hook: refuse kit / reference / Xbox / game-folder paths, list every file opened for reading"""
    def __init__(self):
        self.read, self.written, self.refused, self.on = [], [], [], False

    def hook(self, event, args):
        if not self.on: return
        if event in ('open', 'os.listdir', 'os.scandir', 'subprocess.Popen', 'os.system', 'os.startfile'):
            p = args[0] if args else None
            if event in ('subprocess.Popen', 'os.system', 'os.startfile'):
                self.refused.append('%s %r' % (event, p)); raise PermissionError('generalbank_pc_build guard: %s' % event)
            if isinstance(p, int) or p is None: return
            if isinstance(p, bytes): p = p.decode('utf-8', 'replace')
            q = os.path.realpath(str(p)).replace('\\', '/').lower()
            root = REPO.replace('\\', '/').lower() + '/'
            rel = q[len(root):] if q.startswith(root) else q
            # the game folder (../data/pc is a junction to it): only its archives patch.000 / bigfile.000 (+ parts)
            game_ok = 'steamapps' in q and '/mods/' not in q and '/backup/' not in q and \
                re.search(r'/(patch|bigfile)\.\d{3}$', q) is not None
            if 'steamapps' in q and not game_ok or any(k in rel for k in KIT_PATTERNS) or \
                    (q not in TU_ALLOWED and any(k in q for k in XBOX_PATTERNS)):
                self.refused.append(q); raise PermissionError('generalbank_pc_build guard refused: %s' % p)
            if event == 'open':
                mode = args[1] if len(args) > 1 else 'r'
                w = isinstance(mode, str) and any(c in mode for c in 'wax+')
                if mode is None and len(args) > 2 and isinstance(args[2], int):
                    w = bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
                if not q.endswith(('.py', '.pyc', '.pyd', '.dll')) and '/lib/' not in q:
                    (self.written if w else self.read).append(q)


GUARD = Guard()


# ---------------------------------------------------------------- reference programs (schema 2)
# word forms: id / kp = bytes kept (PC words / Xbox bytes that keep their order: u8 tables, byte strings), sw = u32
# byte swap (Xbox big endian -> PC), h = u16-pair swap (two u16 fields in one word); the symbol forms (schema 3) are h
# with cdc::Symbol halves mapped Xbox -> PC by the knowledge's symbol rule (sym): sb = (u16 kept, Symbol) = DataMember
# offset | name, sa = (Symbol, u16 kept) = DataType userType | pad, sab = (Symbol, Symbol) = ScriptName
FORMS = ('id', 'kp', 'sw', 'h', 'sa', 'sb', 'sab')
TOK = re.compile(r'^([A-Z])(id|kp|sw|h|sab|sa|sb)(\d+)\+(\d+)$')
SYMBOL_LABELS = (('dm.off', 'b'), ('dt.user', 'a'), ('proto', 'ab'), ('root', 'ab'), ('state', 'ab'))
RULES = dict(runs=[], starts=[], scripts={})     # set by set_rules from the knowledge file (schema 3)


def set_rules(rules):
    """symbol rule: runs [Xbox first, Xbox last, delta] (PC Symbol = Xbox Symbol + delta inside a run, else kept);
    script rule: {Xbox file key T:ID: PC key} where the converter's id map renumbers (else the same key)"""
    runs = sorted((rules or {}).get('symbols', {}).get('runs', []))
    RULES.update(runs=runs, starts=[r[0] for r in runs], scripts=dict((rules or {}).get('scripts', {}).get('map', {})))


def sym(x):
    k = bisect.bisect_right(RULES['starts'], x) - 1
    if k >= 0 and x <= RULES['runs'][k][1]: return (x + RULES['runs'][k][2]) & 0xffff
    return x


def sym_dict():
    """the symbol rule as a dict over its runs (script_conv.offset_map takes a dict)"""
    return {x: (x + d) & 0xffff for a, b, d in RULES['runs'] for x in range(a, b + 1)}


def form(b, f):
    """apply word form f to bytes b (whole words; id / kp keep every byte)"""
    if f in ('id', 'kp'): return bytes(b)
    n = len(b) // 4
    if f == 'sw': return struct.pack('<%dI' % n, *struct.unpack('>%dI' % n, b[:4 * n]))
    if f == 'h': return struct.pack('<%dH' % (2 * n), *struct.unpack('>%dH' % (2 * n), b[:4 * n]))
    if f in ('sa', 'sb', 'sab'):
        v = list(struct.unpack('>%dH' % (2 * n), b[:4 * n]))
        if f != 'sb': v[0::2] = [sym(x) for x in v[0::2]]
        if f != 'sa': v[1::2] = [sym(x) for x in v[1::2]]
        return struct.pack('<%dH' % (2 * n), *v)
    raise ValueError('unknown form %r' % f)


def encode_refs(dst, sources):
    """dst bytes as a program over sources [(letter, bytes, forms)] -> (ops, residual bytes)
    ops: (letter, form, byte offset, n words) | ('L', n words) | ('T', n bytes); greedy longest run, a run continues
    the previous one when it can; id / kp forms also at the byte phases 1..3 (shifted byte strings)"""
    views = []
    for letter, b, forms in sources:
        for f in forms:
            for ph in ((0, 1, 2, 3) if f in ('id', 'kp') else (0,)):
                views.append((letter, f, ph, form(b[ph:], f)))
    idx2, idx1 = {}, {}
    for vi, (_, _, _, b) in enumerate(views):
        W = [b[4 * i:4 * i + 4] for i in range(len(b) // 4)]
        for i in range(len(W) - 1):
            l = idx2.setdefault(W[i] + W[i + 1], [])
            if len(l) < 64: l.append((vi, i))
        for i, w in enumerate(W): idx1.setdefault(w, (vi, i))
    nd = len(dst) // 4
    T = [dst[4 * i:4 * i + 4] for i in range(nd)]
    ops, res, i, nxt = [], bytearray(), 0, None
    while i < nd:
        cands = ([nxt] if nxt else []) + (idx2.get(T[i] + T[i + 1], []) if i + 1 < nd else [])
        bl, bs = 0, None
        for vi, c in cands:
            b = views[vi][3]; nw = len(b) // 4; n = 0
            while i + n < nd and c + n < nw and T[i + n] == b[4 * (c + n):4 * (c + n) + 4]: n += 1
            if n > bl: bl, bs = n, (vi, c)
        if bl == 0 and T[i] in idx1: bl, bs = 1, idx1[T[i]]
        if bl:
            vi, c = bs; letter, f, ph, _ = views[vi]
            ops.append((letter, f, ph + 4 * c, bl)); i += bl; nxt = (vi, c + bl)
        else:
            if ops and ops[-1][0] == 'L': ops[-1] = ('L', ops[-1][1] + 1)
            else: ops.append(('L', 1))
            res += T[i]; i += 1; nxt = None
    tail = dst[4 * nd:]
    if tail: ops.append(('T', len(tail))); res += tail
    return ops, bytes(res)


def decode_refs(ops, srcs, res):
    """program + {letter: bytes} + residual bytes -> bytes"""
    out, p = bytearray(), 0
    for o in ops:
        if o[0] == 'L': out += res[p:p + 4 * o[1]]; p += 4 * o[1]
        elif o[0] == 'T': out += res[p:p + o[1]]; p += o[1]
        else:
            letter, f, off, n = o
            b = srcs[letter][off:off + 4 * n]
            if len(b) != 4 * n: raise SystemExit('program reads past source %s (+%d, %d words)' % (letter, off, n))
            out += form(b, f)
    if p != len(res): raise SystemExit('residual not used up (%d of %d bytes)' % (p, len(res)))
    return bytes(out)


def ops_str(ops):
    """text form, space separated: '<src><form><byte offset>+<words>', 'L<words>' residual, 'T<bytes>' residual tail"""
    return ' '.join('%s%d' % o if o[0] in ('L', 'T') else '%s%s%d+%d' % o for o in ops)


def ops_parse(s):
    out = []
    for tok in s.split():
        if tok[0] in 'LT' and tok[1:].isdigit(): out.append((tok[0], int(tok[1:]))); continue
        m = TOK.match(tok)
        if not m: raise SystemExit('bad program token %r' % tok)
        out.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4))))
    return out


def residual_need(ops):
    return sum(4 * o[1] if o[0] == 'L' else o[1] for o in ops if o[0] in ('L', 'T'))


# ---------------------------------------------------------------- PC input
def read_pc(path):
    from archive import Archive
    from names import crc
    a = Archive(path, 'le')
    r = a.find(crc(PC_NAME))
    if len(r) != 1: sys.exit('expected exactly one %s record in %s, found %d' % (PC_NAME, path, len(r)))
    return DW.cdrm_decode(a.read(r[0]), 'le')


def read_tu(path):
    """the player's TitleUpdate.000: raw (big endian) generalbank.drm (the record of all languages, spec ffffffff)"""
    from archive import Archive
    from names import crc
    if not os.path.isfile(path):
        raise SystemExit('title update not found: %s (give the player\'s TitleUpdate.000 with --tu)' % path)
    a = Archive(path, 'be')
    r = [x for x in a.find(crc(TU_NAME)) if x['spec'] == 0xffffffff]
    if len(r) != 1: raise SystemExit('expected exactly one %s record in %s, found %d' % (TU_NAME, path, len(r)))
    return DW.cdrm_decode(a.read(r[0]), 'be')


# scripts ported from the title update with the Xbox data offsets kept (result key: TU key; tools/generalbank_build.py
# steps 2-21, tools/generalbank_hud_build.py): their relocations are the TU's, converted by rule (source xr)
PORTS = {'8:6': '8:6', '8:9': '8:10', '8:37': '8:38', '8:21239': '8:21239', '8:20082': '8:20082'}
# our own recipes appended to a ported script (source own:NAME@T:ID+HEX = made by the recipe's own tool at data offset
# HEX of that section): vtable31 = tools/script_vtable_insert.py (the PC parent's extra vtable slot 31: VTE copy from
# the PC script + new table, root 0x3c / 0x44; generalbank_build steps 5 / 14, generalbank_hud_build), dlc2_stub =
# tools/script_dlc2_flag_stub.py (step 21)
OWN = {'8:6': ('vtable31',), '8:9': ('vtable31', 'dlc2_stub'), '8:37': ('vtable31',)}
VT_SLOT = 31


class Sources:
    """section sources of the player's files: pc:T:ID (PC generalbank), tu:T:ID (TU generalbank), tex:T:ID
    (tools/tex_convert.convert of the TU texture section), xr:T:ID (the TU section's relocations converted to the PC
    file by rule, data part empty), own:NAME+HEX (our own recipe bytes at that data offset); part 'data' / 'reloc'.
    order = the section keys of the result file (PC order + the new sections) - xr / own address sections by index"""
    def __init__(self, raw_pc, raw_tu, order=None):
        D = DW.read(raw_pc, 'le') if raw_pc is not None else None
        T = DW.read(raw_tu, 'be') if raw_tu is not None else None
        self.pc = {key(s): s for s in D.sections} if D else {}
        self.tu = {key(s): s for s in T.sections} if T else {}
        self.tu_keys = [key(s) for s in T.sections] if T else []
        self.order = order
        self.tex, self.xr, self.omaps, self.own = {}, {}, {}, {}

    def index(self, k):
        if self.order is None: raise SystemExit('source needs the result section order')
        if not hasattr(self, '_idx'): self._idx = {x: i for i, x in enumerate(self.order)}
        return self._idx.get(k)

    def xreloc(self, k):
        """TU section k's relocations in the PC file (rule, schema 3): internal / id entries kept (the ported script
        keeps the Xbox data offsets); external entries: target section = the TU target through the script rule (its
        index in the result order; a target missing there is dropped - the residual keeps it), destination offset
        = script_conv.offset_map(TU target, PC target, symbol rule) when the target is a PC script that is not one of
        the ported scripts (they keep the Xbox layout) - the call-offset rule of tools/drm_put_sections.py --xbox"""
        if k in self.xr: return self.xr[k]
        import script_conv as SC
        r = R.parse(self.tu[k].reloc, 'be')
        ext = []
        for si, src, dst in r.external:
            tk = self.tu_keys[si]
            pk = RULES['scripts'].get(tk, tk)
            i = self.index(pk)
            if i is None: continue
            if pk.startswith('8:') and pk in self.pc and pk not in PORTS and tk in self.tu and self.tu[tk].data:
                if tk not in self.omaps:
                    x, p = self.tu[tk], self.pc[pk]
                    self.omaps[tk] = SC.offset_map(x.data, R.parse(x.reloc, 'be'), p.data, R.parse(p.reloc, 'le'),
                                                   sym_dict())
                dst = self.omaps[tk].get(dst, dst)
            ext.append((i, src, dst))
        self.xr[k] = R.write(R.Reloc(list(r.internal), ext, list(r.idref_a), list(r.unk3), list(r.idref)), 'le')
        return self.xr[k]

    def own_part(self, k, part):
        """own:NAME@T:ID+HEX - our own recipe for section T:ID, made by its tool's rule at data offset HEX: data =
        the words the recipe writes, reloc = its relocation entries (8 bytes each, internal then external)"""
        if k not in self.own:
            name, rest = k.split('@'); sk, at = rest.split('+'); at = int(at, 16)
            if name == 'dlc2_stub':
                import script_dlc2_flag_stub as ST
                S = ST.build_stub(at, self.index('8:%d' % ST.F34[0]), self.index('8:%d' % ST.F14[0]))
                data = S['blob'] + b''.join(struct.pack('<I', w) for a, w in S['sites'])
                ints, exts = S['internal'], S['external']
            elif name == 'vtable31':
                import script_vtable_insert as VT
                t, p = self.tu[PORTS[sk]], self.pc[sk]      # the ported TU script, the PC script (the reference)
                it = dict(R.parse(t.reloc, 'be').internal)
                size = struct.unpack_from('>H', t.data, 0x3c)[0]
                vb, pext = VT.ref_vte(p.data, R.parse(p.reloc, 'le'), VT_SLOT)
                blk, table, ints, exts = VT.appended(at, [it[it[0x44] + 4 * j] for j in range(size)], VT_SLOT, vb, pext)
                data = struct.pack('<H', size + 1) + t.data[0x3e:0x40] + blk      # root 0x3c (vtableSize + 1) + block
            else:
                raise SystemExit('unknown own recipe %r' % name)
            rel = b''.join(struct.pack('<II', a, b) for a, b in ints) + \
                b''.join(struct.pack('<Q', R.pack_ext(*e)) for e in exts)
            self.own[k] = dict(data=data, reloc=rel)
        return self.own[k][part]

    def get(self, ref, part):
        kind, k = ref.split(':', 1)
        if kind == 'xr': return b'' if part == 'data' else self.xreloc(k)
        if kind == 'own': return self.own_part(k, part)
        if kind == 'tex':
            if part == 'reloc': return b''
            if k not in self.tex:
                import tex_convert as TC
                if k not in self.tu: raise SystemExit('source %s: texture %s not in the title update' % (ref, k))
                self.tex[k] = bytes(TC.convert(bytes(self.tu[k].data)))
            return self.tex[k]
        S = self.pc if kind == 'pc' else self.tu if kind == 'tu' else None
        if S is None or k not in S: raise SystemExit('source %s not found in the player\'s files' % ref)
        return getattr(S[k], part)


def entry_bytes(e, SRC, local, part):
    """one part ('data' / 'reloc') of a knowledge entry -> bytes (every source and the result md5-checked)"""
    p = e[part]
    srcs = {}
    for letter in sorted({o[0] for o in ops_parse(p['ops']) if o[0] not in ('L', 'T')}):
        s = e['sources'][letter]
        b = SRC.get(s['ref'], part)
        if md5(b) != s[part + '_md5']:
            raise SystemExit('section %s: source %s %s md5 %s, recorded %s (not the recorded player file?)' % (
                e['key'], s['ref'], part, md5(b), s[part + '_md5']))
        srcs[letter] = b
    r = p['residual']
    if r['bytes'] == 0: res = b''
    elif r['store'] == 'inline': res = bytes.fromhex(r['hex'])
    else:
        lp = (local or {}).get(e['key'], {}).get(part)
        if lp is None:
            raise SystemExit('section %s needs %d residual %s bytes from the local knowledge file (not in the '
                             'repository): %s' % (e['key'], r['bytes'], part, local and local.get('_path') or LOCAL))
        res = bytes.fromhex(lp)
    if len(res) != r['bytes'] or md5(res) != r['md5']:
        raise SystemExit('section %s: residual %s md5 differs from the recorded one' % (e['key'], part))
    out = decode_refs(ops_parse(p['ops']), srcs, res)
    if md5(out) != e[part + '_md5']: raise SystemExit('section %s: result %s md5 differs' % (e['key'], part))
    return out


def load_local(path, K):
    """local knowledge (outside the repository): {key: {data: hex, reloc: hex}} for the residuals stored 'local'"""
    need = [e['key'] for e in K['sections'] + K.get('post_ring_sections', [])
            if any(e[p]['residual']['store'] == 'local' and e[p]['residual']['bytes'] for p in ('data', 'reloc'))]
    if not need or not os.path.isfile(path): return None, need     # no section needs it: the file is not even read
    L = json.load(open(path, encoding='utf-8'))
    if L.get('knowledge_version') != K['version']:
        raise SystemExit('local knowledge %s is for version %s, knowledge is %s' % (path, L.get('knowledge_version'),
                                                                                   K['version']))
    L['sections']['_path'] = path
    return L['sections'], need


def recipe_p3(s7, log):
    d = bytearray(s7.data)
    old = struct.unpack_from('<I', d, P3_AT)[0]
    ctx = (struct.unpack_from('<I', d, P3_AT - 0x10)[0], struct.unpack_from('<I', d, P3_AT - 4)[0],
           struct.unpack_from('<I', d, P3_AT - 0x14)[0])
    if old != P3_OLD or ctx != (131, 0xbeebbeeb, 0xbeebbeeb):
        raise SystemExit('recipe P3: script 7 +0x%x is %d (context %s), expected %d (131, beebbeeb, beebbeeb)' % (
            P3_AT, old, ctx, P3_OLD))
    struct.pack_into('<I', d, P3_AT, P3_NEW)
    s7.data = bytes(d)
    log.append('recipe P3: script 7 +0x%x %d -> %d (member 0xc4c, tools/menu_dlc_patch.py P3)' % (P3_AT, P3_OLD, P3_NEW))


def src_note(e):
    return ' '.join('%s=%s' % (l, s['ref']) for l, s in sorted(e['sources'].items()))


def res_note(e):
    r = [e[p]['residual'] for p in ('data', 'reloc')]
    return 'residual %d + %d B (%s)' % (r[0]['bytes'], r[1]['bytes'],
                                       '/'.join(sorted({x['store'] for x in r if x['bytes']})) or 'none')


def apply_knowledge(raw_pc, SRC, local, K, log):
    """PC raw DRM -> raw DRM with recipe P3 + every recorded section (before the ring step)"""
    D = DW.read(raw_pc, 'le')
    by = {key(s): s for s in D.sections}
    if len(by) != len(D.sections): raise SystemExit('duplicate section keys in the PC file')
    recipe_p3(by['8:7'], log)
    for e in K['sections']:
        k = e['key']
        base = by.get(k) if not e['new'] else None
        if e['new']:
            if k in by: raise SystemExit('section %s should be new but is in the PC file' % k)
        elif base is None: raise SystemExit('section %s missing in the PC file' % k)
        sd, sr = (base.data, base.reloc) if base is not None else (b'', b'')
        data, rel = entry_bytes(e, SRC, local, 'data'), entry_bytes(e, SRC, local, 'reloc')
        flags, ver, spec, pad = e['meta']
        if e['new']:
            t, i = (int(x) for x in k.split(':'))
            D.sections.append(DW.Section(t, i, data, rel, flags, ver, spec, pad))
        else:
            base.data, base.reloc, base.flags, base.ver, base.spec, base.pad = data, rel, flags, ver, spec, pad
        log.append('%-11s %-10s %s: %d -> %d B data, reloc %d -> %d B, from %s, %s' % (
            e['class'], k, 'new' if e['new'] else 'patched', len(sd), len(data), len(sr), len(rel), src_note(e),
            res_note(e)))
    order = ['%d:%d' % (s.type, s.id) for s in D.sections]
    if md5(','.join(order).encode()) != K['order_md5']: raise SystemExit('section order differs from the recorded one')
    return D.write('le')


def append_sections(raw, entries, SRC, local, log):
    """raw DRM + the recorded new sections (post-ring, e.g. tu_camera) appended at the end -> raw DRM"""
    D = DW.read(raw, 'le')
    have = {key(s) for s in D.sections}
    for e in entries:
        if not e['new'] or e['key'] in have: raise SystemExit('post-ring section %s is not new' % e['key'])
        data, rel = entry_bytes(e, SRC, local, 'data'), entry_bytes(e, SRC, local, 'reloc')
        t, i = (int(x) for x in e['key'].split(':'))
        flags, ver, spec, pad = e['meta']
        D.sections.append(DW.Section(t, i, data, rel, flags, ver, spec, pad))
        log.append('%-11s %-10s new (after the ring): %d B data, reloc %d B, from %s, %s' % (
            e['class'], e['key'], len(data), len(rel), src_note(e), res_note(e)))
    # relocation bounds and DTP id references of the new sections (every referenced DTP id must exist in the file)
    infos = [dict(size=len(s.data)) for s in D.sections]
    ids = {(s.type, s.id) for s in D.sections}
    for s in D.sections[len(D.sections) - len(entries):]:
        r = R.parse(s.reloc, 'le')
        bad = R.check(r, len(s.data), infos)
        miss = sorted({(ty, struct.unpack_from('<I', s.data, o)[0]) for ty, o in r.idref} - ids)
        if bad or miss: raise SystemExit('section %d:%d: relocations out of bounds %s, missing id targets %s' % (
            s.type, s.id, bad[:5], miss[:5]))
    log.append('post-ring sections: relocations in bounds, every id reference resolves in the file')
    return D.write('le')


def load_knowledge(path):
    K = json.load(open(path, encoding='utf-8'))
    if K.get('schema') != SCHEMA: raise SystemExit('unknown knowledge schema %r (this tool: %d)' % (K.get('schema'),
                                                                                                    SCHEMA))
    set_rules(K.get('rules'))
    return K


def result_order(raw_pc, K):
    """section keys of the result file before the ring: the PC order + the new recorded sections (apply_knowledge)"""
    return [key(s) for s in DW.read(raw_pc, 'le').sections] + [e['key'] for e in K['sections'] if e['new']]


# ---------------------------------------------------------------- gate (word diff per section)
def gate(a_bytes, b_bytes, allow_extra=()):
    """allow_extra: section keys that may exist only in A, all at its end (then not counted as differences)"""
    A, B = DW.read(a_bytes, 'le'), DW.read(b_bytes, 'le')
    bb = {key(s): s for s in B.sections}
    ak = [key(s) for s in A.sections]
    extra = [k for k in ak if k not in bb and k in allow_extra]
    extra_at_end = ak[len(ak) - len(extra):] == extra if extra else True
    core = [k for k in ak if k not in extra]
    rep = dict(header_same=(A.ver, A.u0, A.u1, A.names, A.pad) == (B.ver, B.u0, B.u1, B.names, B.pad),
               sections=(len(A.sections), len(B.sections)), extra_allowed=extra, extra_at_end=extra_at_end,
               order_same=core == [key(s) for s in B.sections], differing=[])
    for s in A.sections:
        if key(s) in extra: continue
        t = bb.get(key(s))
        if t is None: rep['differing'].append(dict(key=key(s), what='missing in the reference')); continue
        if s.data == t.data and s.reloc == t.reloc and (s.flags, s.ver, s.spec, s.pad) == (t.flags, t.ver, t.spec, t.pad):
            continue
        n = min(len(s.data), len(t.data)) // 4
        w = sum(1 for o in range(n) if s.data[4 * o:4 * o + 4] != t.data[4 * o:4 * o + 4])
        rep['differing'].append(dict(key=key(s), size=(len(s.data), len(t.data)), words=w,
                                     reloc_same=s.reloc == t.reloc,
                                     meta_same=(s.flags, s.ver, s.spec, s.pad) == (t.flags, t.ver, t.spec, t.pad)))
    for k in bb:
        if k not in {key(s) for s in A.sections}: rep['differing'].append(dict(key=k, what='only in the reference'))
    rep['raw_md5'] = (md5(DW.cdrm_decode(a_bytes, 'le')), md5(DW.cdrm_decode(b_bytes, 'le')))
    rep['file_md5'] = (md5(a_bytes), md5(b_bytes))
    rep['ok'] = rep['header_same'] and rep['order_same'] and not rep['differing'] and extra_at_end and \
        rep['sections'][0] - len(extra) == rep['sections'][1]
    return rep


# ---------------------------------------------------------------- learn (developer)
ORIGIN = {
    '7:36': ('kit_b138_tu', 'B138 kit: extras list DTP 36 (+688 B) = the title update growth of Xbox DTP 37'),
    '8:72': ('kit_b138_tu', 'B138 kit: chapter text records +0x51d0 / +0x52e0 / +0x53f0 = TU script 72 '
                            '(Xbox 441 / 104 / 104, locmap -> 482 / 127 / 127)'),
    '8:6': ('pipeline_tu', 'generalbank_build steps 2-7, 12: TU loading screen script 6'),
    '8:9': ('pipeline_tu', 'generalbank_build steps 8-21: TU script 10 as PC script 9 (hint box)'),
    '8:21239': ('pipeline_tu', 'generalbank_build steps 4 / 9: TU section 21239'),
    '8:20082': ('pipeline_tu', 'generalbank_build step 4: TU section 20082'),
    '8:104': ('pipeline_tu', 'generalbank_build step 1 (mission screen text style) + step 23 (S104 level test)'),
    '7:47': ('pipeline_tu', 'generalbank_build step 22 / hud T10: the 6 TU input bindings of set 17'),
    '7:2': ('k12', 'globalinfo_player_list_fix: TU player list 29 ids (+ 857)'),
    '8:37': ('hud_tu', 'generalbank_hud_build: TU HUD script 38 as PC 37 (shadow meter)'),
    '8:213': ('hud_tu', 'generalbank_hud_build: TU larabase native type script 211 as PC 213'),
    '5:7899': ('hud_tu', 'generalbank_hud_build T9: TU texture 7899 (converted)'),
    '5:7036': ('hud_tu', 'generalbank_hud_build T9: TU texture 7036 (converted)'),
    '7:21237': ('tu_camera', 'tu_camera_dtp: TU Lara camera settings in doppelganger mode (TU GlobalInfo +0x14c)'),
    '7:21238': ('tu_camera', 'tu_camera_dtp: TU combat camera settings in doppelganger mode (TU GlobalInfo +0x150)'),
    '7:22194': ('tu_camera', 'tu_camera_dtp: TU curve records (86), id-referenced by 21237 / 21238')}


def classify(k):
    return ORIGIN.get(k, ('unclassified', ''))[0]


# title-update sections a recorded section is converted from (the origin chain's input; learn tries them all and
# records only the ones the program uses); same type, the listed ids first, then the same id and its neighbours
TU_FROM = {'8:9': ['8:10'], '8:37': ['8:38'], '8:213': ['8:211'], '7:36': ['7:37'], '8:6': ['8:6', '8:7'],
           '7:2': ['7:3'], '7:47': ['7:48']}
LETTERS = 'ABCDEFGHIJKMNOPQRSUVWXYZ'        # no L / T (residual tokens)


def own_refs(k, s, SRC):
    """own recipe sources of result section s (developer, learn): a recipe is used only where the result holds
    exactly the block its rule makes at that offset (dlc2_stub: at the section end; vtable31: the table root 0x44
    points to, the VTE copy before its count word)"""
    out = []
    for name in OWN.get(k, ()):
        if name == 'dlc2_stub':
            import script_dlc2_flag_stub as ST
            n = len(ST.build_stub(0, 0, 0)['blob'])
            at = len(s.data) - n; skip = 0
        elif name == 'vtable31':
            import script_vtable_insert as VT
            p = SRC.pc.get(k)
            table = dict(R.parse(s.reloc, 'le').internal).get(0x44)
            if p is None or table is None: continue
            at = table - 4 - len(VT.ref_vte(p.data, R.parse(p.reloc, 'le'), VT_SLOT)[0]); skip = 4
        else:
            continue
        if at < 0 or at % 4: continue
        ref = 'own:%s@%s+%x' % (name, k, at)
        blk = SRC.get(ref, 'data')[skip:]
        if s.data[at:at + len(blk)] == blk if name == 'vtable31' else s.data[at:] == blk[:len(s.data) - at]:
            out.append(ref)
        else:
            print('%s: own recipe %s does not match the reference at +0x%x - not used' % (k, name, at))
    return out


def record_section(k, s, SRC):
    """the result section s (key k) as a reference program over the player's files -> (entry part, residuals)"""
    ty, i = (int(x) for x in k.split(':'))
    tu = TU_FROM.get(k, []) + ['%d:%d' % (ty, i + d) for d in (0, 1, -1)]
    tu = [c for j, c in enumerate(tu) if c in SRC.tu and c not in tu[:j]]
    refs = (['pc:' + k] if k in SRC.pc else []) + ['tu:' + c for c in tu] + (['tex:' + c for c in tu] if ty == 5 else [])
    refs += (['xr:' + PORTS[k]] if k in PORTS and PORTS[k] in SRC.tu else []) + own_refs(k, s, SRC)
    if len(refs) > len(LETTERS): raise SystemExit('%s: too many sources' % k)
    table = {LETTERS[j]: r for j, r in enumerate(refs)}
    part = {}
    for p in ('data', 'reloc'):
        forms = {'pc': ('id',), 'tex': ('id',), 'xr': ('id',), 'own': ('id',),
                 'tu': ('sw', 'kp', 'h', 'sa', 'sb', 'sab') if p == 'data' else ('sw', 'kp')}
        srcs = [(l, SRC.get(r, p), forms[r.split(':')[0]]) for l, r in table.items()]
        ops, res = encode_refs(getattr(s, p), [x for x in srcs if x[1]])
        if decode_refs(ops, {l: b for l, b, _ in srcs}, res) != getattr(s, p): raise SystemExit('%s %s: round trip' % (k, p))
        part[p] = (ops, res)
    used = sorted({o[0] for p in part for o in part[p][0] if o[0] not in ('L', 'T')})
    sources = {l: dict(ref=table[l], data_md5=md5(SRC.get(table[l], 'data')), reloc_md5=md5(SRC.get(table[l], 'reloc')))
               for l in used}
    total = sum(len(part[p][1]) for p in part)
    store = 'inline' if total <= INLINE_MAX else 'local'
    out, local = dict(sources=sources), {}
    for p in ('data', 'reloc'):
        ops, res = part[p]
        r = dict(bytes=len(res), md5=md5(res), store=store if res else 'none')
        if res and store == 'inline': r['hex'] = res.hex()
        if res and store == 'local': local[p] = res.hex()
        out[p] = dict(ops=ops_str(ops), residual=r)
    return out, local


def check_script7(p7, r7):
    """REF script 7 = PC script 7 + P3 + the three slot-7 windows + 3 external call relocations, nothing else"""
    if len(p7.data) != len(r7.data): raise SystemExit('script 7 size differs: %d / %d' % (len(p7.data), len(r7.data)))
    bad = []
    for o in range(0, len(p7.data), 4):
        if p7.data[o:o + 4] == r7.data[o:o + 4]: continue
        if o == P3_AT or any(a <= o < b for a, b in SLOT7_WINDOWS): continue
        bad.append(o)
    rp, rr = R.parse(p7.reloc, 'le'), R.parse(r7.reloc, 'le')
    if rp.internal != rr.internal or rp.idref != rr.idref: bad.append('reloc internal / idref')
    ext = [(a, b) for a, b in zip(rp.external, rr.external) if a != b]
    if len(rp.external) != len(rr.external) or sorted(a[1] for a, b in ext) != sorted(SLOT7_CALLS):
        bad.append('external relocations: %s' % ext)
    if bad: raise SystemExit('script 7 of the reference differs from PC outside P3 / slot-7 sites: %s' % bad[:10])
    return len(ext)


def derive_rules(Rf, SRC):
    """developer: the symbol and script id rules of the ported scripts (PORTS), read off the reference against the
    player's TU sections. Symbol pairs: every word the script walker (script_conv.Walk) labels as a Symbol field
    (SYMBOL_LABELS) at the same data offset with the same label in the TU script and the reference (the port keeps
    the Xbox offsets); script pairs: the target section of each external relocation, TU entry and reference entry
    matched by their source offset. Majority per Xbox value; a minority value stays residual (reported). Symbols are
    stored as runs of equal delta over the sorted Xbox values."""
    import script_conv as SC
    rb = {key(s): s for s in Rf.sections}; rk = [key(s) for s in Rf.sections]
    pairs, keys = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for k, tk in PORTS.items():
        s, t = rb[k], SRC.tu[tk]
        rr, tr = R.parse(s.reloc, 'le'), R.parse(t.reloc, 'be')
        Wr, Wt = SC.Walk(s.data, rr, 'le').run(), SC.Walk(t.data, tr, 'be').run()
        for o, lab in Wr.lab.items():
            if Wt.lab.get(o) != lab: continue
            halves = next((h for name, h in SYMBOL_LABELS if lab[0] == name and
                           (name not in ('root', 'proto') or lab[1] == 8)), None)
            if not halves: continue
            a, b = struct.unpack_from('<HH', s.data, o), struct.unpack_from('>HH', t.data, o)
            if 'a' in halves: pairs[b[0]][a[0]] += 1
            if 'b' in halves: pairs[b[1]][a[1]] += 1
        tx = {src: si for si, src, dst in tr.external}
        for si, src, dst in rr.external:
            if src in tx: keys[SRC.tu_keys[tx[src]]][rk[si]] += 1
    sym_conf = {x: dict(c) for x, c in pairs.items() if len(c) > 1}
    runs = []
    for x in sorted(pairs):
        d = pairs[x].most_common(1)[0][0] - x
        if runs and runs[-1][2] == d: runs[-1][1] = x
        else: runs.append([x, x, d])
    key_conf = {a: dict(c) for a, c in keys.items() if len(c) > 1}
    smap = {a: c.most_common(1)[0][0] for a, c in sorted(keys.items()) if c.most_common(1)[0][0] != a}
    rules = dict(
        symbols=dict(about='cdc::Symbol Xbox -> PC (u16) of the ported scripts: inside a run [Xbox first, Xbox last, '
                           'delta] PC = Xbox + delta, else kept. Read off the reference (the converter\'s DlcIds.sym: '
                           'learned base map, calibration / base evidence, +480 above the Xbox base max) for the %d '
                           'Symbols the ported scripts use; a rule (numbers), no game bytes' % len(pairs),
                     runs=runs, pairs=len(pairs), conflicts=len(sym_conf)),
        scripts=dict(about='section key Xbox title update -> PC file where the converter\'s id map (work/generic/'
                           'idmap.json type 8) renumbers a script; every other key is kept (%d target keys seen)'
                           % len(keys), map=smap, keys=len(keys), conflicts=len(key_conf)))
    return rules, dict(symbol_conflicts=sym_conf, key_conflicts=key_conf, symbol_pairs=pairs, key_pairs=keys)


def rules_evidence(ev):
    """developer evidence: the rules against the converter's own tables when they exist locally (DlcIds with the
    base evidence symbols of generalbank_build step 2; idmap.json type 8) - report only"""
    out = []
    try:
        if os.path.isfile(os.path.join(REPO, 'work', 'rebuild', 'sym_base_evidence.json')):
            os.environ.setdefault('TRUDLC_SYM_EXTRA', os.path.join(REPO, 'work', 'rebuild', 'sym_base_evidence.json'))
        import dlc_generic as DG
        ids = DG.DlcIds()
        diff = sorted((x, c.most_common(1)[0][0], ids.sym(x)) for x, c in ev['symbol_pairs'].items()
                      if ids.sym(x) != c.most_common(1)[0][0])
        out.append('symbol rule vs the converter (DlcIds.sym): %d of %d equal, differing (Xbox, reference, converter) '
                   '%s' % (len(ev['symbol_pairs']) - len(diff), len(ev['symbol_pairs']), diff))
        m8 = ids.base.get(8, {})
        kd = []
        for a, c in ev['key_pairs'].items():
            t, i = (int(v) for v in a.split(':'))
            want = '%d:%d' % (t, m8.get(i, i)) if t == 8 else a
            if want != c.most_common(1)[0][0]: kd.append((a, c.most_common(1)[0][0], want))
        out.append('script rule vs idmap type 8: %d of %d equal, differing %s' % (len(ev['key_pairs']) - len(kd),
                                                                                 len(ev['key_pairs']), kd))
    except (Exception, SystemExit) as e:
        out.append('converter tables not available (%s) - rules checked by the build md5 only' % e)
    return out


def learn(argv):
    write = '--write' in argv; argv = [a for a in argv if a != '--write']
    pc, tu, kpath, lpath = PC_ARCH, TU_ARCH, KNOW, LOCAL
    if '--pc' in argv: k = argv.index('--pc'); pc = argv[k + 1]; del argv[k:k + 2]
    if '--tu' in argv: k = argv.index('--tu'); tu = argv[k + 1]; del argv[k:k + 2]
    if '--knowledge' in argv: k = argv.index('--knowledge'); kpath = argv[k + 1]; del argv[k:k + 2]
    if '--local' in argv: k = argv.index('--local'); lpath = argv[k + 1]; del argv[k:k + 2]
    add = None
    if '--add-sections' in argv: k = argv.index('--add-sections'); add = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2: sys.exit(__doc__)
    ref_path, exp_path = argv
    raw_pc, raw_tu = read_pc(pc), read_tu(tu)
    SRC = Sources(raw_pc, raw_tu)
    LOC = {}
    ref_b, exp_b = open(ref_path, 'rb').read(), open(exp_path, 'rb').read()
    P, Rf = DW.read(raw_pc, 'le'), DW.read(ref_b, 'le')
    if (P.ver, P.u0, P.u1, P.names, P.pad) != (Rf.ver, Rf.u0, Rf.u1, Rf.names, Rf.pad): sys.exit('header differs')
    pk = [key(s) for s in P.sections]; rk = [key(s) for s in Rf.sections]
    if rk[:len(pk)] != pk: sys.exit('the reference does not start with the PC section order')
    pb = {key(s): s for s in P.sections}
    n_ext = check_script7(pb['8:7'], Rf.sections[pk.index('8:7')])
    rules, ev = derive_rules(Rf, SRC)
    set_rules(rules); SRC.order = rk
    print('rules: symbol map %d pairs -> %d runs (conflicts %s), script id map %d of %d keys renumbered (conflicts %s)'
          % (rules['symbols']['pairs'], len(rules['symbols']['runs']), ev['symbol_conflicts'] or 'none',
             len(rules['scripts']['map']), rules['scripts']['keys'], ev['key_conflicts'] or 'none'))
    for line in rules_evidence(ev): print(line)
    secs, totals = [], {}
    for s in Rf.sections:
        k = key(s)
        if k == '8:7': continue
        b = pb.get(k)
        if b is not None and b.data == s.data and b.reloc == s.reloc and \
                (b.flags, b.ver, b.spec, b.pad) == (s.flags, s.ver, s.spec, s.pad):
            continue
        sd, sr = (b.data, b.reloc) if b is not None else (b'', b'')
        cls = classify(k)
        if cls == 'unclassified': sys.exit('section %s differs from PC but has no class' % k)
        prog, loc = record_section(k, s, SRC)
        e = dict(key=k, new=b is None, meta=[s.flags, s.ver, s.spec, s.pad],
                 size=[len(sd), len(s.data)], reloc_size=[len(sr), len(s.reloc)],
                 data_md5=md5(s.data), reloc_md5=md5(s.reloc), **prog)
        e['class'] = cls; e['origin'] = ORIGIN[k][1]
        if loc: LOC[k] = loc
        secs.append(e)
        tally(totals, e)
    K = dict(schema=SCHEMA, version=VERSION, about=(
        'generalbank.drm knowledge for tools/generalbank_pc_build.py: the sections of the developer reference '
        '(K12 + HUD generalbank, the base of ring tree 7) that differ from the player\'s PC patch.000 generalbank, '
        'as word programs over sections of the player\'s own files (pc = PC patch.000 generalbank, tu = Xbox title '
        'update TitleUpdate.000 generalbank, tex = tools/tex_convert of a TU texture), each source with its md5; '
        'forms id / kp (bytes kept), sw (u32 swap), h (u16-pair swap), sa / sb / sab (h with Symbol halves mapped by '
        'rules.symbols); xr = TU relocations converted by rules.symbols / rules.scripts, own = our recipe tools '
        '(script_vtable_insert, script_dlc2_flag_stub). No game data is stored here: residual bytes no '
        'rule derives yet are inline only when small (values, listed in docs Befund-Wissen-nur-Verweise-1111.md), '
        'otherwise in the local knowledge file outside the repository. Script 7 is not recorded: recipe P3 + '
        'tools/menu_ring_p14.py (its D1 rewrites the three slot-7 sites). post_ring_sections = new sections appended '
        'after the ring (tu_camera: tools/tu_camera_dtp.py rules). Classes: see the tool docstring and '
        'docs Befund-Generalbank-PC-Basis-1111.md.'),
        pc=dict(name=PC_NAME, source='pc/patch.000', raw_md5=md5(raw_pc), raw_size=len(raw_pc), sections=len(P.sections)),
        tu=dict(name=TU_NAME, source='TitleUpdate.000 (Xbox title update, supplied by the player)', raw_md5=md5(raw_tu),
                raw_size=len(raw_tu), sections=len(SRC.tu)),
        reference=dict(md5=md5(ref_b), raw_md5=md5(DW.cdrm_decode(ref_b, 'le')),
                       what='K12 + HUD generalbank (installed 07.11.2026, base of the ring trees; '
                            'generalbank_build -> generalbank_hud_build -> globalinfo_player_list_fix)'),
        script7=dict(recipe='P3', p3=[P3_AT, P3_OLD, P3_NEW], slot7_sites_in_reference='b138 form, rewritten by ring D1',
                     external_relocations_retargeted_in_reference=n_ext),
        order_md5=md5(','.join(rk).encode()), rules=rules, sections=secs, totals=totals)
    log = []
    pre = apply_knowledge(raw_pc, SRC, LOC, K, log)
    K['pre_ring_raw_md5'] = md5(pre)
    g = gate(DW.cdrm_encode(pre, 'le'), ref_b)
    print('\n'.join(log))
    print('pre-ring build vs reference: %s; differing %s' % ('IDENTICAL' if g['ok'] else 'differs', g['differing']))
    # ring step in memory (same code path as build)
    tmp = os.path.join(REPO, 'work', 'rebuild', 'generalbank_pc_learn')
    os.makedirs(tmp, exist_ok=True)
    a, b = os.path.join(tmp, '01.drm'), os.path.join(tmp, '02.drm')
    open(a, 'wb').write(DW.cdrm_encode(pre, 'le'))
    ring(a, b, os.path.join(tmp, 'ring_report.json'))
    out_b = open(b, 'rb').read()
    g2 = gate(out_b, exp_b)
    K['expect'] = dict(ring_md5=md5(out_b), ring_raw_md5=md5(DW.cdrm_decode(out_b, 'le')), file=os.path.basename(exp_path),
                       what='ring tree 7 (work/ring_p14_1011/tree7, installed + live-tested 10.11.2026)')
    print('after ring vs EXPECT_FILE: %s, md5 %s / %s; differing %s' % ('IDENTICAL' if g2['ok'] else 'differs',
                                                                       md5(out_b), md5(exp_b), g2['differing']))
    post = []
    if add:
        A = DW.read(open(add, 'rb').read(), 'le')
        for s in A.sections:
            k = key(s)
            if classify(k) == 'unclassified': sys.exit('--add-sections: no class for %s' % k)
            prog, loc = record_section(k, s, SRC)
            e = dict(key=k, new=True, meta=[s.flags, s.ver, s.spec, s.pad], size=[0, len(s.data)],
                     reloc_size=[0, len(s.reloc)], data_md5=md5(s.data), reloc_md5=md5(s.reloc), **prog)
            e.update(**{'class': classify(k), 'origin': ORIGIN[k][1], 'learned_from': os.path.basename(add)})
            if loc: LOC[k] = loc
            post.append(e)
            tally(totals, e)
        K['post_ring_sections'] = post
        fin = DW.cdrm_encode(append_sections(DW.cdrm_decode(out_b, 'le'), post, SRC, LOC, log), 'le')
        g3 = gate(fin, exp_b, allow_extra=[e['key'] for e in post])
        print('with the post-ring sections vs EXPECT_FILE: %s (extra at the end: %s)' % (
            'IDENTICAL except the allowed extra sections' if g3['ok'] else 'DIFFERS', g3['extra_allowed']))
        if not g3['ok']: g2['ok'] = False
    else:
        fin = out_b
    K['expect'].update(md5=md5(fin), raw_md5=md5(DW.cdrm_decode(fin, 'le')))
    K['post_ring_rules'] = [record_tailoring(fin, out_b, raw_tu)]
    print('rule %s (opt-in): result md5 %s' % (T134['rule'], K['post_ring_rules'][0]['md5']))
    K['local_sections'] = sorted(LOC)
    for e in secs + post:
        print('%-10s %-11s sources %-40s residual data %5d B, reloc %5d B (%s)' % (
            e['key'], e['class'], src_note(e), e['data']['residual']['bytes'], e['reloc']['residual']['bytes'],
            e['data']['residual']['store'] if e['data']['residual']['bytes'] else e['reloc']['residual']['store']))
    print('residual bytes per class %s' % json.dumps(totals))
    print('sections needing the local knowledge file: %s' % (sorted(LOC) or 'none'))
    print('final md5 %s' % md5(fin))
    if write:
        if not g2['ok']: sys.exit('not written: the build does not reproduce EXPECT_FILE')
        with open(kpath, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(K, f, indent=1)
            f.write('\n')
        print('written', kpath, os.path.getsize(kpath), 'B')
        if not LOC:
            print('no residual needs the local knowledge file - %s not written (an older one is not read by build)'
                  % lpath)
            return 0
        L = dict(schema=1, knowledge_version=VERSION, about=(
            'LOCAL generalbank knowledge (never in the repository): residual bytes of the sections no rule derives yet, '
            'for tools/generalbank_pc_build.py (docs Befund-Wissen-nur-Verweise-1111.md)'), sections=LOC)
        os.makedirs(os.path.dirname(os.path.abspath(lpath)), exist_ok=True)
        with open(lpath, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(L, f, indent=1)
            f.write('\n')
        print('written', lpath, os.path.getsize(lpath), 'B')
    return 0 if g2['ok'] else 1


def tally(totals, e):
    t = totals.setdefault(e['class'], dict(sections=0, residual_inline=0, residual_local=0))
    t['sections'] += 1
    for p in ('data', 'reloc'):
        r = e[p]['residual']
        if r['bytes']: t['residual_' + r['store']] += r['bytes']


# ---------------------------------------------------------------- rule T134 (Q40): main-menu tailoring reset
# The title update's script 134 function 9 (mission screen, branch "no game in progress", main menu -> DLC -> level ->
# yes) prints 'Resetting player tailoring to Medium difficulty.' (corebase f7) and calls uiexperienceadjustmentmenu
# f6..f10 with 1 (the five player adjustment setters, PC exe 0x6e75a0..0x6e76a0 through the natives 0x77baa0..0x77bae0;
# docs Befund-DLC-Schwierigkeit-1111.md section 4) between its internal call (op68) and the level test; PC script 104
# function 9 has no such calls. The rule translates that TU block word by word into an appended block of PC script 104,
# reached from the op63 that already leaves the op68 for the appended level test (generalbank_build step 23) and
# jumping on to that level test - the TU's order. The TU's object member (type uiexperienceadjustmentmenu, no init)
# becomes a new PC member at the next free instance offset; its entry is a copy of the PC's own member of that type
# whose script pairs with the other TU script holding the same TU member (same type, TU name, member index and
# instance offset: TU 109 m18 = PC 121 m18), so the PC name is read from the PC file, not guessed; the dependency list
# gets the native type as the TU's does; the function's stackSize = max(PC, TU) as tools/script7_pause_port.py.
# Members and dependencies are re-homed (appended copies, old arrays stay orphaned with their relocations). Everything
# is read from the player's PC + TU files; the knowledge file records only md5s (post_ring_rules). Opt-in (build
# --tailoring): the default result stays the live-tested file.
T134 = dict(pc='8:104', tu='8:134', func=9, native='uiexperienceadjustmentmenu',
            text='Resetting player tailoring to Medium difficulty.', calls=5, rule='tu134_tailoring')
CODE_EXTRA = None
JUMP_OPS = (0x63, 0x64)


def _op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def _s24(v):
    v &= 0xffffff
    return v - (1 << 24) if v & 0x800000 else v


def _cstr(d, a):
    return bytes(d[a:d.index(b'\0', a)]).decode('latin-1')


class Scr:
    """one script section of a DRM (endian e): words, relocations, arrays, members, code ranges, instructions"""
    def __init__(self, D, k, e):
        global CODE_EXTRA
        import script_conv as SC
        if CODE_EXTRA is None: CODE_EXTRA = dict(SC.Walk.EXTRA); CODE_EXTRA[0x02] = 1      # op02 float literal
        self.D, self.e, self.E = D, e, ('>' if e == 'be' else '<')
        self.keys = [key(x) for x in D.sections]
        self.k = self.keys.index(k)
        s = D.sections[self.k]
        self.d, self.rel = bytes(s.data), R.parse(s.reloc, e)
        self.it = dict(self.rel.internal)
        self.ext = {so: (si, do) for si, so, do in self.rel.external}
        self.ids = self.rel.id_offsets()
        self.arr = {n: (t, c, sz) for n, t, c, sz in SC.Walk(self.d, self.rel, e).run().arrays}

    def w(self, a): return struct.unpack_from(self.E + 'I', self.d, a)[0]
    def h(self, a): return struct.unpack_from(self.E + 'H', self.d, a)[0]

    def func(self, j):
        t, n, sz = self.arr['funcs']
        if j >= n: raise SystemExit('script has %d functions, no f%d' % (n, j))
        return t + sz * j

    def code_range(self, j):
        ct = self.it.get(self.func(j) + 0x18)
        if ct is None: raise SystemExit('f%d has no code' % j)
        return ct, ct + 4 * self.w(ct - 4)

    def instrs(self, lo, hi):
        o = lo
        while o < hi:
            x = self.w(o); n = CODE_EXTRA.get(x >> 24, 0)
            yield o, x >> 24, x, [o + 4 * (q + 1) for q in range(n)]
            o += 4 * (1 + n)

    def members(self):
        t, n, sz = self.arr['members']
        return [dict(i=j, a=t + sz * j, tag=self.w(t + sz * j), ut=self.h(t + sz * j + 4), ty=self.w(t + sz * j + 8),
                     tyref=self.ids.get(t + sz * j + 8), off=self.h(t + sz * j + 12), name=self.h(t + sz * j + 14),
                     init=self.it.get(t + sz * j + 16)) for j in range(n)]

    def deps(self):
        t, n, sz = self.arr.get('deps', (None, 0, 4))
        return [self.w(t + 4 * j) for j in range(n)] if n else []

    def target(self, a):
        si, do = self.ext[a]
        return self.keys[si], do


def _natives(D, e):
    """{section key: native name} of every native script type (root 0x10 -> name string)"""
    out = {}
    for s in D.sections:
        if s.type != 8 or not s.data: continue
        it = dict(R.parse(s.reloc, e).internal)
        if 0x10 in it: out[key(s)] = _cstr(s.data, it[0x10])
    return out


def _func_index(S, off):
    t, n, sz = S.arr['funcs']
    return (off - t) // sz if t <= off < t + n * sz and (off - t) % sz == 0 else None


def tailoring_plan(raw_in, raw_tu):
    """PC raw DRM (the ring + camera result) + the player's TU raw generalbank -> (raw out, info); refuses (SystemExit)
    on anything that is not exactly the expected input"""
    P, T = DW.read(raw_in, 'le'), DW.read(raw_tu, 'be')
    pc, tu = Scr(P, T134['pc'], 'le'), Scr(T, T134['tu'], 'be')
    pnat, tnat = _natives(P, 'le'), _natives(T, 'be')
    log = []
    # ---- the TU block: from the op05 of the text to the last of the five native calls, between op68 and the test
    lo, hi = tu.code_range(T134['func'])
    ins = [x for x in tu.instrs(lo, hi) if x[1] != 0x00]
    at = [j for j, x in enumerate(ins) if x[1] == 0x05 and x[3][0] in tu.it and _cstr(tu.d, tu.it[x[3][0]]) == T134['text']]
    if len(at) != 1: raise SystemExit('TU script 134 f9: %d prints of the tailoring text (expected 1)' % len(at))
    j0 = at[0]; j = j0; calls = 0
    while calls < T134['calls']:
        j += 1
        if j >= len(ins): raise SystemExit('TU script 134 f9: block runs past the function')
        if ins[j][1] == 0x65:
            tk, to = tu.target(ins[j][3][0])
            if tnat.get(tk) != T134['native']: raise SystemExit('TU +0x%x: call into %s, not %s' % (ins[j][0], tk, T134['native']))
            calls += 1
    tblock = ins[j0:j + 1]
    if ins[j0 - 1][1] != 0x68 or ins[j + 1][1] != 0x0e:
        raise SystemExit('TU block not between the op68 call and the level test (op%02x / op%02x)' % (ins[j0 - 1][1], ins[j + 1][1]))
    tlo, thi = tblock[0][0], tblock[-1][0] + 4 * (1 + len(tblock[-1][3]))
    log.append('TU script 134 f9 block +0x%x..+0x%x: %d instructions without the op00 markers (op68 before, op0e test after)'
               % (tlo, thi, len(tblock)))
    # ---- the PC site: f9's only op68, then the op63 to the appended level test (step 23)
    plo, phi = pc.code_range(T134['func'])
    p68 = [x for x in pc.instrs(plo, phi) if x[1] == 0x68]
    if len(p68) != 1: raise SystemExit('PC script 104 f9: %d op68 (expected 1)' % len(p68))
    site = p68[0][0] + 8
    sw = pc.w(site)
    if sw >> 24 != 0x63: raise SystemExit('PC script 104 +0x%x: %08x, not the op63 to the level test block' % (site, sw))
    old_block = site + 4 + 4 * _s24(sw)
    if not (phi <= old_block < len(pc.d)) or pc.w(old_block) >> 24 != 0x0e:
        raise SystemExit('PC script 104 +0x%x: op63 target +0x%x is not the appended level test' % (site, old_block))
    k108 = [k for k, v in pnat.items() if v == T134['native']]
    if len(k108) != 1: raise SystemExit('PC: %d scripts of native %s' % (len(k108), T134['native']))
    k108 = k108[0]
    if any(pc.keys[si] == k108 for si, so, do in pc.rel.external):
        raise SystemExit('PC script 104 already calls %s - rule applied already?' % T134['native'])
    # ---- translation tables: call targets, member
    def map_call(o):
        tk, to = tu.target(o)
        pk = RULES['scripts'].get(tk, tk)
        if tnat.get(tk) is None or tnat.get(tk) != pnat.get(pk):
            raise SystemExit('TU call target %s (%s) -> PC %s (%s): not the same native' % (tk, tnat.get(tk), pk, pnat.get(pk)))
        ps = Scr(P, pk, 'le'); ts = Scr(T, tk, 'be')
        fj = _func_index(ts, to)
        if fj is None or _func_index(ps, to) != fj: raise SystemExit('TU %s +0x%x: no function entry at the same PC offset' % (tk, to))
        return pk, to, '%s f%d (+0x%x) -> PC %s f%d' % (tk, fj, to, pk, fj)
    size, align = pc.h(0x1c), pc.h(0x1e)
    tmem = {m['off']: m for m in tu.members()}
    used = sorted({x[2] & 0xffffff for x in tblock if x[1] == 0x0f})
    if len(used) != 1: raise SystemExit('TU block uses %d members (expected 1)' % len(used))
    xm = tmem[used[0]]
    if xm['tyref'] != 8 or xm['init'] is not None: raise SystemExit('TU member %d: not a script-type member without init' % xm['off'])
    tyk = RULES['scripts'].get('8:%d' % xm['ty'], '8:%d' % xm['ty'])
    if tnat.get('8:%d' % xm['ty']) != T134['native'] or tyk != k108:
        raise SystemExit('TU member %d type 8:%d does not map to the PC native %s' % (xm['off'], xm['ty'], k108))
    pty = int(k108.split(':')[1])
    if any(m['tyref'] == 8 and m['ty'] == pty for m in pc.members()):
        raise SystemExit('PC script 104 already has a member of type %s' % k108)
    # name: the TU scripts with the same TU member (type, name) paired with a PC script by member index + offset
    pairs, pmem = [], None
    for s in T.sections:
        if s.type != 8 or not s.data or key(s) == T134['tu']: continue
        ts = Scr(T, key(s), 'be')
        if 'members' not in ts.arr: continue
        for m in ts.members():
            if m['tyref'] == 8 and m['ty'] == xm['ty'] and m['name'] == xm['name']:
                if pmem is None:          # PC members of the native type, per script (walked once)
                    pmem = []
                    for q in P.sections:
                        if q.type != 8 or not q.data: continue
                        ps = Scr(P, key(q), 'le')
                        if 'members' in ps.arr:
                            pmem += [(key(q), x) for x in ps.members() if x['tyref'] == 8 and x['ty'] == pty]
                pairs += [(key(s), qk, m['i'], m['off'], x) for qk, x in pmem if x['i'] == m['i'] and x['off'] == m['off']]
    names = {p[4]['name'] for p in pairs}
    if len(pairs) != 1 or len(names) != 1:
        raise SystemExit('member name: %d TU / PC script pairs %s (expected exactly 1)' % (len(pairs), [p[:4] for p in pairs]))
    tk_, pk_, mi, moff, tmpl = pairs[0]
    if tmpl['tag'] != xm['tag'] or tmpl['init'] is not None:
        raise SystemExit('template member %s m%d: tag %08x / init, TU %08x' % (pk_, mi, tmpl['tag'], xm['tag']))
    tsrc = Scr(P, pk_, 'le')
    new_off = (size + align - 1) // align * align if align else size
    new_size = new_off + 4
    log.append('member TU %d (type %s, name %d) -> new PC %d (type %s, name %d: TU %s m%d = PC %s m%d, offset %d); '
               'instance size %d -> %d' % (xm['off'], '8:%d' % xm['ty'], xm['name'], new_off, k108, tmpl['name'], tk_, mi,
                                          pk_, mi, moff, size, new_size))
    # ---- build
    d = bytearray(pc.d); r = R.parse(P.sections[pc.k].reloc, 'le')
    old_len = len(d)
    def pad():
        while len(d) % 4: d.append(0)
    def dup(lo_, hi_, delta):
        r.internal += [(a + delta, t) for a, t in list(r.internal) if lo_ <= a < hi_]
        r.external += [(si, a + delta, dd) for si, a, dd in list(r.external) if lo_ <= a < hi_]
        r.idref += [(t, a + delta) for t, a in list(r.idref) if lo_ <= a < hi_]
        r.idref_a += [(t, a + delta) for t, a in list(r.idref_a) if lo_ <= a < hi_]
    def retarget(a, t):
        n0 = len(r.internal)
        r.internal = [(x, y) for x, y in r.internal if x != a]
        if len(r.internal) != n0 - 1: raise SystemExit('no internal pointer at +0x%x' % a)
        r.internal.append((a, t))
    pad()
    stro = len(d); d += T134['text'].encode('latin-1') + b'\0'; pad()
    # members: count + old entries + the new one
    mt, mn, msz = pc.arr['members']
    d += struct.pack('<I', mn + 1); nmt = len(d)
    d += pc.d[mt:mt + msz * mn]; dup(mt, mt + msz * mn, nmt - mt)
    na = len(d); d += tsrc.d[tmpl['a']:tmpl['a'] + 12] + struct.pack('<HHI', new_off, tmpl['name'], 0)
    r.idref.append((8, na + 8))
    retarget(0x2c, nmt)
    # dependencies: count + old + the native type
    dt, dn, _ = pc.arr['deps']
    d += struct.pack('<I', dn + 1); ndt = len(d)
    d += pc.d[dt:dt + 4 * dn]; dup(dt, dt + 4 * dn, ndt - dt)
    d += struct.pack('<I', pty); r.idref.append((8, ndt + 4 * dn))
    retarget(0x48, ndt)
    # the block
    code = []
    for o, opc, x, ex in tblock:
        if opc in (0x03, 0x04): code.append((x, None))
        elif opc == 0x05: code.append((x, None)); code.append((PH_WORD, ('int', stro)))
        elif opc == 0x0f: code.append((_op(0x0f, new_off), None))
        elif opc in (0x65, 0x66):
            pk, po, txt = map_call(ex[0]); log.append('TU +0x%x op%02x: %s' % (o, opc, txt))
            code.append((x, None)); code.append((PH_WORD, ('ext', pc.keys.index(pk), po)))
        else: raise SystemExit('TU +0x%x: opcode %02x not handled' % (o, opc))
    blk = len(d)
    code.append((_op(0x63, (old_block - (blk + 4 * len(code) + 4)) // 4), None))
    for k_, (x, rel) in enumerate(code):
        a = blk + 4 * k_
        d += struct.pack('<I', x)
        if rel and rel[0] == 'int': r.internal.append((a, rel[1]))
        elif rel and rel[0] == 'ext': r.external.append((rel[1], a, rel[2]))
    words = {site: (sw, _op(0x63, (blk - (site + 4)) // 4), 'op63 -> the tailoring block (was -> the level test +0x%x)' % old_block)}
    struct.pack_into('<I', d, site, words[site][1])
    struct.pack_into('<H', d, 0x1c, new_size)
    words[0x1c] = (pc.w(0x1c), struct.unpack_from('<I', d, 0x1c)[0], 'instance size %d -> %d' % (size, new_size))
    f9 = pc.func(T134['func'])
    pst, tst = pc.h(f9 + 10), tu.h(tu.func(T134['func']) + 10)
    if tst > pst:
        struct.pack_into('<H', d, f9 + 10, tst)
        words[f9 + 8] = (pc.w(f9 + 8), struct.unpack_from('<I', d, f9 + 8)[0], 'f9 stackSize %d -> %d (TU %d)' % (pst, tst, tst))
    P.sections[pc.k].data = bytes(d); P.sections[pc.k].reloc = R.write(r, 'le')
    log.append('script 104: %d -> %d B; members %d -> %d (+0x%x), deps %d -> %d (+0x%x, + %s), block +0x%x (%d words, '
               'string +0x%x), site +0x%x, f9 stackSize %d -> %d' % (old_len, len(d), mn, mn + 1, nmt, dn, dn + 1, ndt,
                                                                    k108, blk, len(code), stro, site, pst, max(pst, tst)))
    info = dict(site=site, old_block=old_block, block=blk, words=len(code), new_off=new_off, new_size=new_size,
                name=tmpl['name'], k108=k108, changed=words, old_len=old_len, tu_block=(tlo, thi), nmt=nmt, ndt=ndt,
                stackSize=(pst, max(pst, tst)))
    return P.write('le'), info, log


PH_WORD = 0xBEEBBEEB


def _sec_md5(raw, k):
    s = next(x for x in DW.read(raw, 'le').sections if key(x) == k)
    return dict(data_md5=md5(s.data), reloc_md5=md5(s.reloc))


def apply_tailoring(fin, raw_tu, rule, log):
    """file bytes (CDRM) -> file bytes with rule T134, every step checked against the recorded md5s"""
    raw_b = DW.cdrm_decode(fin, 'le')
    if _sec_md5(raw_b, T134['pc']) != rule['before']:
        raise SystemExit('rule %s: script 104 before is not the recorded one %s' % (T134['rule'], rule['before']))
    raw_a, info, tlog = tailoring_plan(raw_b, raw_tu)
    log += ['rule %s: %s' % (T134['rule'], x) for x in tlog]
    probs, _ = tailoring_verify(raw_b, raw_a, raw_tu)
    if probs: raise SystemExit('rule %s: verify refused: %s' % (T134['rule'], '; '.join(probs[:10])))
    if _sec_md5(raw_a, T134['pc']) != rule['after']:
        raise SystemExit('rule %s: script 104 after is not the recorded one %s' % (T134['rule'], rule['after']))
    log.append('rule %s: verify ok (only script 104 differs, every changed word planned, block = TU script 134 '
               'f9 +0x%x..+0x%x, shape gate ok); script 104 md5 = recorded' % ((T134['rule'],) + info['tu_block']))
    return DW.cdrm_encode(raw_a, 'le')


def record_tailoring(fin_cam, fin_nocam, raw_tu):
    """developer: the post_ring_rules entry of rule T134 from the two results (with / without the tu_camera
    sections) - md5s only"""
    out = dict(rule=T134['rule'], default=False, section=T134['pc'], tu_section=T134['tu'], about=(
        'opt-in (build --tailoring): TU script 134 function 9 resets the player tailoring to Medium (corebase print + '
        'uiexperienceadjustmentmenu f6..f10 with 1) on the main-menu path; translated into an appended block of PC '
        'script 104 function 9 (new member of the native type, dependency, stackSize) - rule code in the tool, '
        'docs Befund-Hauptmenue-Schwierigkeit-1111.md'))
    for tag, fin in (('', fin_cam), ('_no_camera', fin_nocam)):
        raw_b = DW.cdrm_decode(fin, 'le')
        raw_a, info, _ = tailoring_plan(raw_b, raw_tu)
        probs, _ = tailoring_verify(raw_b, raw_a, raw_tu)
        if probs: raise SystemExit('rule %s: verify refused: %s' % (T134['rule'], probs[:10]))
        out['before' + tag], out['after' + tag] = _sec_md5(raw_b, T134['pc']), _sec_md5(raw_a, T134['pc'])
        out['md5' + tag] = md5(DW.cdrm_encode(raw_a, 'le'))
    if (out['before'], out['after']) != (out['before_no_camera'], out['after_no_camera']):
        raise SystemExit('rule %s: script 104 differs with / without the camera sections' % T134['rule'])
    del out['before_no_camera'], out['after_no_camera']
    return out


def rules_record(argv):
    """developer: rules-record OUT_DIR_OF_A_BUILD [--knowledge JSON] [--tu TU] [--write]: the build's
    mods/generalbank.drm (= expect.md5) and steps/02_ring.drm (= expect.ring_md5) -> post_ring_rules"""
    write = '--write' in argv; argv = [a for a in argv if a != '--write']
    kpath, tu = KNOW, TU_ARCH
    if '--knowledge' in argv: k = argv.index('--knowledge'); kpath = argv[k + 1]; del argv[k:k + 2]
    if '--tu' in argv: k = argv.index('--tu'); tu = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 1: sys.exit(__doc__)
    K = load_knowledge(kpath)
    cam = open(os.path.join(argv[0], 'mods', 'generalbank.drm'), 'rb').read()
    nocam = open(os.path.join(argv[0], 'steps', '02_ring.drm'), 'rb').read()
    if (md5(cam), md5(nocam)) != (K['expect']['md5'], K['expect']['ring_md5']):
        raise SystemExit('the build files are not the recorded results (%s / %s)' % (md5(cam), md5(nocam)))
    raw_tu = read_tu(tu)
    if md5(raw_tu) != K['tu']['raw_md5']: raise SystemExit('title update generalbank is not the recorded one')
    e = record_tailoring(cam, nocam, raw_tu)
    print(json.dumps(e, indent=1))
    rules = [x for x in K.get('post_ring_rules', []) if x['rule'] != e['rule']] + [e]
    if write:
        K['post_ring_rules'] = rules
        K['version'] = VERSION
        with open(kpath, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(K, f, indent=1)
            f.write('\n')
        print('written', kpath, os.path.getsize(kpath), 'B (version %s)' % VERSION)
    return 0


def tailoring_verify(raw_b, raw_a, raw_tu):
    """AFTER = BEFORE + exactly rule T134: every other section byte-identical; script 104 word diff over BEFORE's
    length only at the planned words; relocations = BEFORE's (members / deps pointers retargeted) + appended ones;
    AFTER = the plan from BEFORE byte for byte; the block decoded from AFTER alone against the TU block (opcodes,
    immediates, text, native + function index, member type); members / deps; shape gate (opcode 3-grams of the
    block in the PC compiler's code of scripts 104 / 121) -> problems"""
    import menu_ring_p14 as MR
    probs = []
    g = gate(DW.cdrm_encode(raw_a, 'le'), DW.cdrm_encode(raw_b, 'le'))
    diff =[x.get('key') for x in g['differing']]
    if not g['header_same'] or not g['order_same'] or diff != [T134['pc']]:
        probs.append('sections differing %s (expected only %s), header same %s, order same %s' % (
            diff, T134['pc'], g['header_same'], g['order_same']))
    plan, info, _ = tailoring_plan(raw_b, raw_tu)
    B, A, Q = DW.read(raw_b, 'le'), DW.read(raw_a, 'le'), DW.read(plan, 'le')
    T = DW.read(raw_tu, 'be')
    b, a = Scr(B, T134['pc'], 'le'), Scr(A, T134['pc'], 'le')
    q = Q.sections[b.k]
    if (a.d, A.sections[a.k].reloc) != (q.data, q.reloc): probs.append('script 104 is not the plan from BEFORE')
    for o in range(0, info['old_len'] - info['old_len'] % 4, 4):
        if b.w(o) != a.w(o) and o not in info['changed']: probs.append('+0x%x %08x -> %08x unexplained' % (o, b.w(o), a.w(o)))
    for o, (x, y, why) in info['changed'].items():
        if (b.w(o), a.w(o)) != (x, y): probs.append('+0x%x: %08x -> %08x, planned %08x -> %08x (%s)' % (o, b.w(o), a.w(o), x, y, why))
    bi, ai = dict(b.rel.internal), dict(a.rel.internal)
    for o, t in bi.items():
        if o in (0x2c, 0x48): continue
        if ai.get(o) != t: probs.append('internal pointer +0x%x changed' % o)
    if any(o < info['old_len'] for o in set(ai) - set(bi)): probs.append('new internal pointers inside the old bytes')
    for nm in ('external', 'idref', 'idref_a', 'unk3'):
        ob, oa = getattr(b.rel, nm), getattr(a.rel, nm)
        if oa[:len(ob)] != ob: probs.append('relocations %s: old entries changed' % nm)
        if nm == 'external' and any(so < info['old_len'] for si, so, do in oa[len(ob):]): probs.append('new external inside old bytes')
        if nm in ('idref', 'idref_a') and any(so < info['old_len'] for t, so in oa[len(ob):]): probs.append('new %s inside old bytes' % nm)
    # decode from AFTER alone
    blk = info['site'] + 4 + 4 * _s24(a.w(info['site']))
    if blk != info['block']: probs.append('site does not jump to the block')
    tu = Scr(T, T134['tu'], 'be')
    tins = [x for x in tu.instrs(*info['tu_block']) if x[1] != 0x00]
    pins = list(a.instrs(blk, blk + 4 * info['words']))
    pnat, tnat = _natives(A, 'le'), _natives(T, 'be')
    am = {m['off']: m for m in a.members()}; tm = {m['off']: m for m in tu.members()}
    if len(pins) != len(tins) + 1: probs.append('block has %d instructions, TU %d + jump' % (len(pins), len(tins)))
    for (xo, xop, xw, xex), (po, pop, pw, pex) in zip(tins, pins):
        ok = xop == pop
        if ok and xop in (0x03, 0x04): ok = xw == pw
        if ok and xop == 0x05: ok = _cstr(tu.d, tu.it[xex[0]]) == _cstr(a.d, a.it[pex[0]])
        if ok and xop in (0x65, 0x66):
            (tk, to), (pk, po_) = tu.target(xex[0]), a.target(pex[0])
            ok = tnat.get(tk) == pnat.get(pk) is not None and _func_index(tu if tk == T134['tu'] else Scr(T, tk, 'be'), to) == \
                _func_index(Scr(A, pk, 'le'), po_) is not None
        if ok and xop == 0x0f:
            xm_, pm_ = tm.get(xw & 0xffffff), am.get(pw & 0xffffff)
            ok = pm_ is not None and xm_ is not None and tnat.get('8:%d' % xm_['ty']) == pnat.get('8:%d' % pm_['ty'])
        if not ok: probs.append('TU +0x%x %08x / PC +0x%x %08x differ' % (xo, xw, po, pw))
    last = pins[-1] if pins else (0, 0, 0, [])
    if last[1] != 0x63 or last[0] + 4 + 4 * _s24(last[2]) != info['old_block']: probs.append('block does not end with op63 -> level test')
    # the level test block unchanged, members, deps
    if a.d[info['old_block']:info['old_len']] != b.d[info['old_block']:info['old_len']]: probs.append('level test block changed')
    ent = lambda m: (m['tag'], m['ut'], m['ty'], m['tyref'], m['off'], m['name'], m['init'])
    mb, ma = b.members(), a.members()
    if [ent(m) for m in mb] != [ent(m) for m in ma[:len(mb)]] or len(ma) != len(mb) + 1: probs.append('old member entries changed')
    nm_ = ma[-1] if ma else {}
    if (nm_.get('off'), nm_.get('ty'), nm_.get('tyref'), nm_.get('name'), nm_.get('init')) != \
            (info['new_off'], int(info['k108'].split(':')[1]), 8, info['name'], None) or a.h(0x1c) != info['new_size']:
        probs.append('new member / instance size')
    if a.deps() != b.deps() + [int(info['k108'].split(':')[1])]: probs.append('deps %s' % a.deps())
    # shape gate: every opcode 3-gram of the block (without the final jump) in the PC compiler's code (104 / 121)
    known = set()
    for k in (T134['pc'], '8:121'):
        S = Scr(B, k, 'le')
        for j in range(S.arr['funcs'][1]):
            if S.it.get(S.func(j) + 0x18) is None: continue
            known.update(MR.trigrams(S, *S.code_range(j)))
    for gm in MR.trigrams(a, blk, blk + 4 * (info['words'] - 1)):
        if gm not in known: probs.append('shape gate: %s does not occur in PC scripts 104 / 121' % ' '.join('op%02x' % x for x in gm))
    return probs, info


# ---------------------------------------------------------------- ring sub-step + build
def ring(a, b, report):
    import menu_ring_p14 as MR
    try:
        MR.main(['build', a, b, '--report', report])
    except SystemExit as e:
        if e.code not in (None, 0): raise SystemExit('ring step (menu_ring_p14 build) failed: %s' % e.code)
    if not os.path.isfile(b): raise SystemExit('ring step wrote no output')


def build(argv):
    pc, tu, kpath, lpath, expect = PC_ARCH, TU_ARCH, KNOW, LOCAL, None
    if '--pc' in argv: k = argv.index('--pc'); pc = argv[k + 1]; del argv[k:k + 2]
    if '--tu' in argv: k = argv.index('--tu'); tu = argv[k + 1]; del argv[k:k + 2]
    if '--knowledge' in argv: k = argv.index('--knowledge'); kpath = argv[k + 1]; del argv[k:k + 2]
    if '--local' in argv: k = argv.index('--local'); lpath = argv[k + 1]; del argv[k:k + 2]
    if '--expect' in argv: k = argv.index('--expect'); expect = argv[k + 1]; del argv[k:k + 2]
    camera = '--no-tu-camera' not in argv; argv = [a for a in argv if a != '--no-tu-camera']
    tailor = '--tailoring' in argv; argv = [a for a in argv if a != '--tailoring']
    if len(argv) > 1: sys.exit(__doc__)
    outdir = argv[0] if argv else OUT_DEFAULT
    import build_util as BU
    BU.check_out(outdir, must_be_below=True)
    if os.path.exists(outdir):
        import shutil
        print('replacing previous output', outdir, flush=True); shutil.rmtree(outdir)
    TU_ALLOWED.add(os.path.realpath(tu).replace('\\', '/').lower())
    GUARD.on = True
    t0 = time.time(); log = []
    K = load_knowledge(kpath)
    post = K.get('post_ring_sections', []) if camera else []
    rule = None
    if tailor:
        rule = next((x for x in K.get('post_ring_rules', []) if x['rule'] == T134['rule']), None)
        if rule is None: raise SystemExit('--tailoring: the knowledge file records no rule %s' % T134['rule'])
    if expect is None:
        expect = (rule['md5'] if post else rule['md5_no_camera']) if rule else \
            K['expect']['md5'] if post else K['expect']['ring_md5']
    local, need = load_local(lpath, K)
    if need and local is None:
        raise SystemExit('the local knowledge file %s is missing; sections %s still need residual bytes no rule '
                         'derives yet (docs Befund-Wissen-nur-Verweise-1111.md)' % (lpath, ', '.join(need)))
    log.append('local knowledge: %s (needed for %s)' % (lpath if local is not None else 'none', ', '.join(need) or
                                                        'no section'))
    raw_pc = read_pc(pc)
    log.append('PC %s %s: raw %d B md5 %s' % (pc, PC_NAME, len(raw_pc), md5(raw_pc)))
    if md5(raw_pc) != K['pc']['raw_md5']:
        raise SystemExit('the PC generalbank is not the recorded one (raw md5 %s, knowledge %s)' % (md5(raw_pc),
                                                                                                    K['pc']['raw_md5']))
    raw_tu = read_tu(tu)
    log.append('TU %s %s: raw %d B md5 %s' % (tu, TU_NAME, len(raw_tu), md5(raw_tu)))
    if md5(raw_tu) != K['tu']['raw_md5']:
        raise SystemExit('the title update generalbank is not the recorded one (raw md5 %s, knowledge %s)' % (
            md5(raw_tu), K['tu']['raw_md5']))
    SRC = Sources(raw_pc, raw_tu, result_order(raw_pc, K))
    log.append('rules: symbol map %d runs, script id map %d keys (knowledge %s)' % (
        len(RULES['runs']), len(RULES['scripts']), K['version']))
    pre = apply_knowledge(raw_pc, SRC, local, K, log)
    if md5(pre) != K['pre_ring_raw_md5']: raise SystemExit('pre-ring raw md5 %s != recorded %s' % (md5(pre),
                                                                                                  K['pre_ring_raw_md5']))
    st = os.path.join(outdir, 'steps'); os.makedirs(st, exist_ok=True)
    a = os.path.join(st, '01_pc_knowledge.drm')
    open(a, 'wb').write(DW.cdrm_encode(pre, 'le'))
    log.append('-> %s md5 %s (raw md5 %s = recorded)' % (a, md5(open(a, 'rb').read()), md5(pre)))
    b2 = os.path.join(st, '02_ring.drm')
    ring(a, b2, os.path.join(outdir, 'ring_report.json'))
    ring_b = open(b2, 'rb').read()
    ring_ok = md5(ring_b) == K['expect']['ring_md5']
    log.append('-> %s md5 %s %s' % (b2, md5(ring_b), '= ring tree 7 (installed, live-tested)' if ring_ok else
                                    'DIFFERS from ring tree 7 %s' % K['expect']['ring_md5']))
    out = os.path.join(outdir, 'mods', 'generalbank.drm')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if post:
        fin = DW.cdrm_encode(append_sections(DW.cdrm_decode(ring_b, 'le'), post, SRC, local, log), 'le')
    else:
        fin = ring_b
        log.append('no post-ring sections (%s)' % ('--no-tu-camera' if not camera else 'none recorded'))
    if rule:
        b3 = os.path.join(st, '03_before_tailoring.drm')
        open(b3, 'wb').write(fin)
        log.append('-> %s md5 %s (input of rule %s)' % (b3, md5(fin), T134['rule']))
        fin = apply_tailoring(fin, raw_tu, rule, log)
    open(out, 'wb').write(fin)
    got = md5(open(out, 'rb').read())
    GUARD.on = False
    ok = ring_ok and (expect.lower() == 'none' or got == expect)
    log.append('result %s md5 %s %s' % (out, got, 'not compared' if expect.lower() == 'none' else
                                        ('= expected %s (%s%s)' % (expect, 'ring tree 7 + %d new sections' % len(post)
                                                                   if post else 'ring tree 7',
                                                                   ' + rule %s' % T134['rule'] if rule else '')
                                         if got == expect else
                                         'DIFFERS from expected %s' % expect)))
    reads = sorted(set(GUARD.read))
    rep = dict(tool='generalbank_pc_build', time=time.strftime('%Y-%m-%d %H:%M:%S'), seconds=round(time.time() - t0, 1),
               knowledge=os.path.relpath(kpath, REPO), local_knowledge=lpath if local is not None else None,
               local_needed_for=need, out=out, md5=got, expect=expect, ok=ok,
               guard=dict(patterns=list(KIT_PATTERNS), refused=GUARD.refused, files_read=reads,
                          files_written=sorted(set(GUARD.written))), log=log)
    json.dump(rep, open(os.path.join(outdir, 'build_report.json'), 'w', encoding='utf-8'), indent=1)
    print('\n'.join(log))
    print('guard: %d files read (%s), refused %d' % (len(reads), ', '.join(reads), len(GUARD.refused)))
    return 0 if ok else 1


def main(argv):
    sys.addaudithook(GUARD.hook)
    if not argv: sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == 'build':
        try:
            return build(rest)
        except PermissionError as e:
            print('GUARD: %s' % e); return 2
    if cmd == 'learn': return learn(rest)
    if cmd == 'rules-record': return rules_record(rest)
    if cmd == 'tailoring-verify':
        if len(rest) not in (2, 3): sys.exit(__doc__)
        load_knowledge(KNOW)                                # rules.scripts (TU -> PC script keys)
        rb, ra =(DW.cdrm_decode(open(p, 'rb').read(), 'le') for p in rest[:2])
        probs, info = tailoring_verify(rb, ra, read_tu(rest[2] if len(rest) > 2 else TU_ARCH))
        for x in probs: print('  PROBLEM:', x)
        for o, (x, y, why) in sorted(info['changed'].items()): print('  +0x%x %08x -> %08x  %s' % (o, x, y, why))
        print('tailoring-verify: %s' % ('ok - only script 104, every word planned, block = TU, shape gate ok' if not probs
                                        else '%d problem(s)' % len(probs)))
        return 0 if not probs else 1
    if cmd == 'gate':
        rp, extra = None, []
        if '--report' in rest: k = rest.index('--report'); rp = rest[k + 1]; del rest[k:k + 2]
        if '--allow-extra' in rest: k = rest.index('--allow-extra'); extra = rest[k + 1].split(','); del rest[k:k + 2]
        if len(rest) != 2: sys.exit(__doc__)
        g = gate(open(rest[0], 'rb').read(), open(rest[1], 'rb').read(), extra)
        g['files'] = rest
        print('file md5 %s / %s, raw md5 %s / %s' % (g['file_md5'] + g['raw_md5']))
        print('header same %s, sections %d / %d, order same %s, differing sections %d, allowed extra sections %s '
              '(at the end: %s)' % (g['header_same'], g['sections'][0], g['sections'][1], g['order_same'],
                                    len(g['differing']), g['extra_allowed'], g['extra_at_end']))
        for d in g['differing']: print('  ', d)
        if rp:
            os.makedirs(os.path.dirname(os.path.abspath(rp)), exist_ok=True)
            json.dump(g, open(rp, 'w', encoding='utf-8'), indent=1)
        print('gate: %s' % (('OK - identical in every section' + (' except the allowed extra sections at the end'
                                                                  if g['extra_allowed'] else ''))
                            if g['ok'] else 'DIFFERENCES'))
        return 0 if g['ok'] else 1
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
