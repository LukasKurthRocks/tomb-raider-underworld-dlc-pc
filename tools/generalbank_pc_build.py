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

Knowledge file (docs/data/generalbank_pc.json, schema 2, written by `learn`; owner decision 2026-11-10: the repository
holds NO copies of game data, only references, rules and hashes): per section a SOURCE table (sections of the player's
own files, each with its md5: `pc:T:ID` = the PC patch.000 generalbank, `tu:T:ID` = the Xbox title update
TitleUpdate.000 generalbank, `tex:T:ID` = tools/tex_convert.convert of that TU texture section) and, for the data and
the relocation blob, a word PROGRAM over them: `<src><form><byte offset>+<words>` takes words of a source in a form
(id / kp = bytes kept, sw = u32 byte swap Xbox -> PC, h = u16-pair swap), `L<n>` / `T<n>` take n residual words /
tail bytes. The forms are the word rules of the converters that made the recorded bytes (generic converter / script
converter / tex_convert / tu_camera_dtp), recorded per word run. RESIDUAL = result bytes no rule derives yet (our own
values, the PC layout's member offset / symbol words of converted scripts, shifted relocation entries): a few bytes
per section are kept INLINE as hex (small values, listed per section in the report), larger residuals only in the
LOCAL knowledge file (default ../data/local/generalbank_pc.local.json, outside the repository) - the build names
the sections it cannot make without it. Every source section, residual and result is md5-checked.

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
                                                       [--no-tu-camera]
        default OUT_DIR work/rebuild/generalbank_pc (replaced), -> OUT_DIR/mods/generalbank.drm, OUT_DIR/build_report.json
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
import sys, os, re, json, struct, hashlib, time
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
VERSION = 'K20261111-2'      # knowledge version (Plan-Spielerweg 5.2); a new learn with other content = a new version
SCHEMA = 2                   # 1 = literal copies (K20261111-1, retired 2026-11-11), 2 = references + rules + residual
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
# byte swap (Xbox big endian -> PC), h = u16-pair swap (two u16 fields in one word)
FORMS = ('id', 'kp', 'sw', 'h')
TOK = re.compile(r'^([A-Z])(id|kp|sw|h)(\d+)\+(\d+)$')


def form(b, f):
    """apply word form f to bytes b (whole words; id / kp keep every byte)"""
    if f in ('id', 'kp'): return bytes(b)
    n = len(b) // 4
    if f == 'sw': return struct.pack('<%dI' % n, *struct.unpack('>%dI' % n, b[:4 * n]))
    if f == 'h': return struct.pack('<%dH' % (2 * n), *struct.unpack('>%dH' % (2 * n), b[:4 * n]))
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


class Sources:
    """section sources of the player's files: pc:T:ID (PC generalbank), tu:T:ID (TU generalbank), tex:T:ID
    (tools/tex_convert.convert of the TU texture section); part 'data' / 'reloc'"""
    def __init__(self, raw_pc, raw_tu):
        self.pc = {key(s): s for s in DW.read(raw_pc, 'le').sections} if raw_pc is not None else {}
        self.tu = {key(s): s for s in DW.read(raw_tu, 'be').sections} if raw_tu is not None else {}
        self.tex = {}

    def get(self, ref, part):
        kind, k = ref.split(':', 1)
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
    if not os.path.isfile(path): return None, need
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
    return K


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


def record_section(k, s, SRC):
    """the result section s (key k) as a reference program over the player's files -> (entry part, residuals)"""
    ty, i = (int(x) for x in k.split(':'))
    tu = TU_FROM.get(k, []) + ['%d:%d' % (ty, i + d) for d in (0, 1, -1)]
    tu = [c for j, c in enumerate(tu) if c in SRC.tu and c not in tu[:j]]
    refs = (['pc:' + k] if k in SRC.pc else []) + ['tu:' + c for c in tu] + (['tex:' + c for c in tu] if ty == 5 else [])
    if len(refs) > len(LETTERS): raise SystemExit('%s: too many sources' % k)
    table = {LETTERS[j]: r for j, r in enumerate(refs)}
    part = {}
    for p in ('data', 'reloc'):
        forms = {'pc': ('id',), 'tex': ('id',), 'tu': ('sw', 'kp', 'h') if p == 'data' else ('sw', 'kp')}
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
        'forms id / kp (bytes kept), sw (u32 swap), h (u16-pair swap). No game data is stored here: residual bytes no '
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
        order_md5=md5(','.join(rk).encode()), sections=secs, totals=totals)
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
    if expect is None: expect = K['expect']['md5'] if post else K['expect']['ring_md5']
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
    SRC = Sources(raw_pc, raw_tu)
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
        open(out, 'wb').write(DW.cdrm_encode(append_sections(DW.cdrm_decode(ring_b, 'le'), post, SRC, local, log),
                                             'le'))
    else:
        open(out, 'wb').write(ring_b)
        log.append('no post-ring sections (%s)' % ('--no-tu-camera' if not camera else 'none recorded'))
    got = md5(open(out, 'rb').read())
    GUARD.on = False
    ok = ring_ok and (expect.lower() == 'none' or got == expect)
    log.append('result %s md5 %s %s' % (out, got, 'not compared' if expect.lower() == 'none' else
                                        ('= expected %s (%s)' % (expect, 'ring tree 7 + %d new sections' % len(post)
                                                                 if post else 'ring tree 7') if got == expect else
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
