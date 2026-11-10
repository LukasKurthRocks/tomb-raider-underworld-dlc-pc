"""Ring menu layout "V3 P14, stage light" (owner's decision 2026-11-10, workspace finding Befund-Ring-8-Plaetze-1011.md):
generalbank script 7 (`uipause`, the ring shared by the main menu and the pause menu) gets
  * ring slot 7 = DOWNLOADABLE CONTENT in BOTH menus (the `f15` form of tools/menu_dlc_patch.py at the three slot-7
    switch sites, see tools/menu_quit_slot_check.py), and
  * QUIT GAME (door icon, text 131) on the unused ring position 14 at the bottom (-180 deg, 1080p ~ (960, 848)),
    clicking it runs the existing PC quit fall-through of slot 7 (func 8 +0x188f8: m0xa88 = 2, locks, DialogYesNo
    script 128 -> uigamedata f45 -> main state 8, the game's own quit).
Nothing else changes; no animation set for position 14 (that is stage 2, "B3").

Changes (script 7 offsets of the PC script, 197 664 B; the pause-menu port only appends, so they stay valid):
  D1  P1 func 27 +0x6288, P2 func 35 +0x9688, P4 func 8 +0x188dc: the 7 words of the `b138` (or `pc`) form -> the
      `pc` word layout, and the external relocation of the call word (+0xc) -> corebase f15 (+0x218, always false on
      PC; target copied from func 19's own corebase f15 call +0x3cb4)
  D2  func 19 +0x3d9c (base state, m0xa90[13] = 1 -> 0): position 14 is not locked in the base ring
  D3  func 29 +0x8124: op50 NOT -> op00 debug line marker: PositionMenuItems places icon 0x7bc on position 14 on PC
  D4  icon 0x7bc init +0x5c (id relocation type 5): texture 31 (Xbox STORAGE DEVICE) -> 26 (the door of icon 0x738)
  D5  text 0x468 init +0x5c: locals 141 (STORAGE DEVICE) -> 131 (QUIT GAME)
  D6  background 0x6b4 init +0x5c (id type 5): texture 16 (sub-ring disc) -> 15 (the disc of the 7 ring slots)
  B1  appended blocks, each reached by an op63 that replaces one op00 marker and jumping back after it:
      B1a func 19 +0x3da4 (end of the base state): show background 0x6b4 (uibitmap f4, as func 20 does for the
          Xbox sub-ring 1) + colour (1, 1, 1, 1) (uibitmap f18 as func 28; func 28 leaves every background at alpha
          0, the ring slots get theirs from the ring-in animation, which position 14 has none of - tree 1 showed the
          door without its disc) and icon 0x7bc (func 22, as func 43 shows 0x7bc on Xbox)
      B1b func 8 +0x17c10 (options), +0x18768 (audio / visual), +0x18e04 (quit dialog): these three "dialog blocks"
          lock positions 8-14 again and hide 0x7bc / 0x6b4 before they open their screen; the block re-frees
          m0xa90[13] and shows 0x6b4 / 0x7bc, so the door is there again when the screen / dialog closes
      Sub-rings (func 24 -> func 20 / 43) keep hiding 0x6b4 / 0x7bc and locking position 14 themselves (static:
      func 20 cases 2-7, func 43 cases 2-7 on PC) - nothing added there.
  B2  func 8 +0x18f50 (where the slot-7 click test lands when slot 7 was not clicked, before the sub-ring dispatch):
      click on hit area 0x170 (the same hit area f14 + input f0 test as slot 7 at +0x188ac, its locals 0xb2 / 0xb4)
      AND NOT m0xa90[13] -> jump to the quit fall-through +0x188f8; otherwise continue at +0x18f54
      The lock element is READ as `0f a90; 03 13; 21 14; 1b` (func 14 / 18); `1e 1` belongs to the WRITE form only.
      Tree 1 (2026-11-10, md5 e64ca088) read it with op1e: the VM's op1b handler (0x57d1af) then took a stale stack
      word as offset and crashed at 0x57d1c4 on the next click after DLC / new game (3 crash dumps, VM pc in this
      block) - the opcode shape gate of `verify` now refuses that.
Every replaced word is checked against its expected old value first (refused otherwise), every native / prototype
target of the new code is copied from an existing call of the same thing in script 7 (no guessed offsets), no jump of
script 7 may land inside a replaced window or on a block's return address.

Commands (from the repository root):
  ../bin/pyt -t 600 tools/menu_ring_p14.py build IN_GENERALBANK OUT_GENERALBANK [--report R.json]
        plan from IN, write OUT, then the same check as `verify` (OUT is removed when it fails)
  ../bin/pyt -t 600 tools/menu_ring_p14.py verify BEFORE AFTER [--report R.json]
        AFTER must be BEFORE + exactly this change: every other section and the header byte-identical; every changed
        or appended word of script 7 explained by the plan from BEFORE; relocations = BEFORE's (3 external targets
        changed as planned) + exactly the planned appended ones; AFTER decoded by itself (the three sites = f15 form,
        D2-D5 values, each block from its op63: opcodes, members, call targets by native name / function index,
        jumps); the script walker reports the same problems as for BEFORE; shape gate: every opcode 3-gram of every
        appended block (op00 markers left out, cut after each jump) occurs in the code of BEFORE's script 7, i.e.
        the blocks only use statement shapes the original compiler produced. Exit 1 = refused.
Status of any file: tools/menu_ring_layout.py (prints the position-14 state via p14_status() of this module).
"""
import sys, os, struct, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC
import menu_dlc_probe as P
import menu_quit_slot_check as QS

SID = 7
PH = 0xBEEBBEEB
COREBASE, UIGAMEDATA = 230, 63
EXTRA = dict(SC.Walk.EXTRA); EXTRA[P.PUSHF] = 1
JUMPS = (0x63, 0x64)
LOCK, HIT14, BG14, ICON14, TEXT14 = 0xa90, 0x170, 0x6b4, 0x7bc, 0x468
DOOR, QUITTEXT = 0x738, 0x3a8
QUIT_FALL = 0x188f8                  # func 8: first statement of the PC quit branch of slot 7 (after the P4 window)
D2 = dict(at=0x3d9c, old=0x04000001, new=0x04000000,
          ctx={0x3d8c: 0x0f000a90, 0x3d90: 0x0300000d, 0x3d94: 0x2100000e, 0x3d98: 0x1e000001, 0x3da0: 0x2e000000})
D3 = dict(at=0x8124, old=0x50000000, new=0x00000b3f,
          ctx={0x8110: 0x00000b3f, 0x8114: 0x09000014, 0x8118: 0x66000000, 0x8120: 0x06000014, 0x8128: 0x64000007,
               0x8130: 0x0f0007bc, 0x8140: 0x68000000})
D4 = dict(member=ICON14, old=31, new=26, donor=DOOR, at=0x22d30)
D5 = dict(member=TEXT14, old=141, new=131, donor=QUITTEXT, at=0x1e450)
D6 = dict(member=BG14, old=16, new=15, donor=0x660, at=0x21870)    # disc of the 7 ring slots (16 = sub-ring disc)
REF_COLOR = (0x7294, {0x7290: 0x0f000618}, 0x65, 'func 28 +0x7290: uibitmap f18 (colour) on background 0x618')
# references copied from existing code: (call word offset, expected words before / at it, what)
REF_SHOW = (0x4668, {0x4664: 0x0f0006b4}, 0x65, 'func 20 +0x4664: uibitmap f4 (show) on background 0x6b4')
REF_F22 = (0x106b0, {0x106ac: 0x0f0007bc}, 0x68, 'func 43 +0x106ac: func 22 (show icon) on 0x7bc')
REF_HIT = (0x188b8, {0x188ac: 0x090000b2, 0x188b0: 0x090000b4, 0x188b4: 0x0f000138}, 0x65,
           'func 8 +0x188ac: hit area f14 of the slot-7 click test')
REF_IN = (0x188c8, {0x188c0: 0x090000b4, 0x188c4: 0x09000000, 0x188d0: 0x060000b2, 0x188d4: 0x6400019e}, 0x65,
          'func 8 +0x188c0: input f0 of the slot-7 click test')
REF_F15 = (0x3cb4, {0x3cb0: 0x0900000c, 0x3cbc: 0x0600000c}, 0x66, 'func 19 +0x3cb0: corebase f15 call')
QUIT_CTX = {0x188f8: 0x00000303, 0x18904: 0x03000002, 0x18908: 0x0f000a88, 0x1890c: 0x65000000,
            0x18944: 0x0f000a90, 0x18948: 0x03000007, 0x18e14: 0x10000af8, 0x18e18: 0x6a000000}
# block sites: key, function, site (op00 marker), marker, back word, (m0xa88 value set before, open script) or None
SITES = [
    dict(key='B1a', func=19, site=0x3da4, marker=0x8a7, back_word=0x000008a8, kind='show',
         note='func 19 base state: show 0x6b4 / 0x7bc'),
    dict(key='B1b_options', func=8, site=0x17c10, marker=0x20e, back_word=0x66000000, kind='refree',
         dialog=(0x17710, 2, 0x17c30, 127), note='func 8 options dialog block (m0xa88 = 2, screen script 127)'),
    dict(key='B1b_av', func=8, site=0x18768, marker=0x2dd, back_word=0x66000000, kind='refree',
         dialog=(0x18198, 5, 0x18788, 130), note='func 8 audio / visual dialog block (m0xa88 = 5, script 130)'),
    dict(key='B1b_quit', func=8, site=0x18e04, marker=0x355, back_word=0x66000000, kind='refree',
         dialog=(0x18904, 2, 0x18e18, 128), note='func 8 quit dialog block (m0xa88 = 2, DialogYesNo script 128)'),
    dict(key='B2', func=8, site=0x18f50, marker=0x374, back_word=0x00000375, kind='click',
         note='func 8 after the slot-7 click test: click on 0x170 and position 14 free -> quit fall-through'),
]


def op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def s24(v):
    v &= 0xffffff
    return v - (1 << 24) if v & 0x800000 else v


class Refuse(Exception):
    """the input is not what the step expects - nothing is written (build) / the check fails (verify)"""


class S7:
    """script 7 of a PC generalbank: words, relocations, element tables, function code ranges"""
    def __init__(self, D):
        self.D = D
        self.idx = {(x.type, x.id): i for i, x in enumerate(D.sections)}
        if (8, SID) not in self.idx: raise Refuse('no script %d' % SID)
        self.k = self.idx[(8, SID)]
        s = D.sections[self.k]
        self.d, self.rel = s.data, R.parse(s.reloc, 'le')
        self.it = dict(self.rel.internal)
        self.ext = {so: (si, do) for si, so, do in self.rel.external}
        self.ids = self.rel.id_offsets()
        self.W = SC.Walk(self.d, self.rel, 'le').run()
        self.arr = {name: (t, n, sz) for name, t, n, sz in self.W.arrays}
        t, n, sz = self.arr['members']
        self.mem = {struct.unpack_from('<H', self.d, t + sz * j + 12)[0]: t + sz * j for j in range(n)}
        self.code = []
        t, n, sz = self.arr['funcs']
        for j in range(n):
            ct = self.it.get(t + sz * j + 0x18)
            if ct is not None:
                self.code.append((j, ct, ct + 4 * self.w(ct - 4)))
        self._nat = {}

    def w(self, a): return struct.unpack_from('<I', self.d, a)[0]

    def func_of(self, a):
        return next((j for j, lo, hi in self.code if lo <= a < hi), None)

    def func_range(self, j):
        return next((lo, hi) for k, lo, hi in self.code if k == j)

    def instrs(self, lo, hi):
        o = lo
        while o < hi:
            w = self.w(o); n = EXTRA.get(w >> 24, 0)
            yield o, w >> 24, w, [o + 4 * (q + 1) for q in range(n)]
            o += 4 * (1 + n)

    def jump_targets(self):
        """{target: [source offsets]} of every op63 / op64 in the code of every function"""
        jt = {}
        for j, lo, hi in self.code:
            for o, opc, w, ex in self.instrs(lo, hi):
                if opc in JUMPS: jt.setdefault(o + 4 + 4 * s24(w), []).append(o)
        return jt

    def target(self, a):
        """external pointer at a -> (type, id, offset)"""
        si, do = self.ext[a]; x = self.D.sections[si]; return x.type, x.id, do

    def native(self, sid):
        """(native name, {function entry offset: index}) of script sid"""
        if sid not in self._nat:
            x = self.D.sections[self.idx[(8, sid)]]
            nm = P.script_info({'data': x.data, 'reloc': x.reloc}, 'le')[1]
            rl = R.parse(x.reloc, 'le')
            W = SC.Walk(x.data, rl, 'le').run()
            fe = {}
            for name, t, n, sz in W.arrays:
                if name == 'funcs': fe = {t + sz * j: j for j in range(n)}
            self._nat[sid] = (nm, fe)
        return self._nat[sid]

    def call_name(self, a):
        """external call operand at a -> 'name fN (+0x..)'"""
        ty, sid, do = self.target(a)
        nm, fe = self.native(sid)
        return '%s f%s (+0x%x)' % (nm or 'script %d' % sid, fe.get(do), do)

    def proto_func(self, t):
        """internal pointer to a prototype -> the function index whose entry points at it"""
        ft, fn, fsz = self.arr['funcs']
        hit = [j for j in range(fn) if self.it.get(ft + fsz * j) == t]
        return hit[0] if len(hit) == 1 else None

    def init_word(self, member, rel_off):
        ini = self.it.get(self.mem[member] + 16)
        base = self.it.get(ini, ini) if ini is not None else None
        return None if base is None else base + rel_off


def expect_words(s, ctx, what):
    for a, v in ctx.items():
        if s.w(a) != v: raise Refuse('%s: +0x%x is %08x, expected %08x - nothing written' % (what, a, s.w(a), v))


def ref_call(s, ref):
    """copy the call target of an existing call: ('ext', si, do) or ('int', target), with the check of its context"""
    a, ctx, opc, what = ref
    expect_words(s, ctx, what)
    if s.w(a) != op(opc): raise Refuse('%s: +0x%x is %08x, not op%02x' % (what, a, s.w(a), opc))
    if opc == 0x68:
        if a + 4 not in s.it: raise Refuse('%s: no internal pointer at +0x%x' % (what, a + 4))
        return ('int', s.it[a + 4])
    if a + 4 not in s.ext: raise Refuse('%s: no external pointer at +0x%x' % (what, a + 4))
    return ('ext',) + s.ext[a + 4]


def plan(D):
    """script 7 of D -> (new data, new Reloc, info); Refuse on any mismatch. info['words'] = {offset: (old or None,
    new, why)}, info['ext_changed'] = {src: (old (si, do), new (si, do))}, info['ext_added'] / ['int_added']"""
    s = S7(D)
    d = bytearray(s.d); r = R.parse(D.sections[s.k].reloc, 'le')
    words, ext_changed = {}, {}
    jt = s.jump_targets()
    ci, ui = s.idx.get((8, COREBASE)), s.idx.get((8, UIGAMEDATA))
    if ci is None or ui is None: raise Refuse('corebase / uigamedata script missing')
    f15 = ref_call(s, REF_F15)
    if f15 != ('ext', ci, QS.F15): raise Refuse('func 19 +0x3cb4 does not call corebase f15 +0x218: %s' % (f15,))
    # ---- D1: the three slot-7 sites -> f15 form
    extmap = {so: s.target(so) for so in s.ext}
    forms = []
    for key, what, base, loc, jz, marker in QS.SITES:
        f, w0 = QS.classify(s.d, extmap, base, loc, jz, marker)
        forms.append(f)
        if f not in ('b138', 'pc'):
            raise Refuse('D1 %s +0x%x: form %s, expected b138 or pc - nothing written' % (key, base, f))
        bad = [t for t in jt if base < t < base + 28]
        if bad: raise Refuse('D1 %s: jumps land inside the window at %s' % (key, ', '.join('+0x%x' % t for t in bad)))
        new = [marker, op(0x09, loc), op(0x66), PH, op(0x06, loc), op(0x64, jz), marker + 1]
        for q in range(7):
            if w0[q] != new[q]:
                words[base + 4 * q] = (w0[q], new[q], 'D1 %s %s: %s form -> f15 form word %d' % (key, what, f, q))
        so = base + 12
        old = s.ext[so]; nw = (ci, QS.F15)
        if old != nw:
            ext_changed[so] = (old, nw)
            r.external = [(nw[0], x[1], nw[1]) if x[1] == so else x for x in r.external]
    # ---- D2 .. D5
    expect_words(s, D2['ctx'], 'D2 func 19 lock of position 14')
    if s.w(D2['at']) != D2['old'] or s.func_of(D2['at']) != 19:
        raise Refuse('D2: +0x%x is %08x (func %s), expected %08x in func 19' % (D2['at'], s.w(D2['at']),
                     s.func_of(D2['at']), D2['old']))
    words[D2['at']] = (D2['old'], D2['new'], 'D2 func 19 base state: m0xa90[13] (position 14) = 1 -> 0 (free)')
    expect_words(s, D3['ctx'], 'D3 func 29 case 14')
    if s.w(D3['at']) != D3['old'] or s.func_of(D3['at']) != 29 or s.target(0x811c) != (8, COREBASE, QS.F17):
        raise Refuse('D3: +0x%x is %08x, expected op50 after corebase f17 in func 29' % (D3['at'], s.w(D3['at'])))
    if D3['at'] in jt: raise Refuse('D3: a jump lands on +0x%x' % D3['at'])
    words[D3['at']] = (D3['old'], D3['new'], 'D3 func 29 case 14: op50 NOT -> op00 marker (icon 0x7bc placed on PC)')
    for nm, X, kind in (('D4', D4, 'texture'), ('D5', D5, 'text'), ('D6', D6, 'texture')):
        a = s.init_word(X['member'], 0x5c); b = s.init_word(X['donor'], 0x5c)
        if a != X['at']: raise Refuse('%s: init word of 0x%x at %s, expected +0x%x' % (nm, X['member'], a, X['at']))
        if s.w(a) != X['old'] or s.w(b) != X['new']:
            raise Refuse('%s: 0x%x %s %d (donor 0x%x %d), expected %d (%d)' % (nm, X['member'], kind, s.w(a),
                         X['donor'], s.w(b), X['old'], X['new']))
        if kind == 'texture' and (s.ids.get(a) != 5 or s.ids.get(b) != 5):
            raise Refuse('%s: id relocation types %s / %s, expected 5 / 5' % (nm, s.ids.get(a), s.ids.get(b)))
        if kind == 'text' and (a in s.ids or a in s.it or a in s.ext):
            raise Refuse('D5: +0x%x carries a relocation' % a)
        words[a] = (X['old'], X['new'], '%s 0x%x init +0x5c: %s %d -> %d (as 0x%x)' % (nm, X['member'], kind,
                    X['old'], X['new'], X['donor']))
    # ---- references for the blocks
    show = ref_call(s, REF_SHOW); f22 = ref_call(s, REF_F22); hit = ref_call(s, REF_HIT); inp = ref_call(s, REF_IN)
    colour = ref_call(s, REF_COLOR)
    if s.proto_func(f22[1]) != 22: raise Refuse('func 43 +0x106b0 does not call func 22')
    if s.call_name(REF_COLOR[0] + 4).split()[:2] != ['uibitmap', 'f18']:
        raise Refuse('func 28 +0x7298 is %s, not uibitmap f18' % s.call_name(REF_COLOR[0] + 4))
    if s.call_name(REF_SHOW[0] + 4).split()[:2] != ['uibitmap', 'f4']:
        raise Refuse('func 20 +0x4668 is %s, not uibitmap f4' % s.call_name(REF_SHOW[0] + 4))
    expect_words(s, QUIT_CTX, 'quit fall-through func 8 +0x188f8')
    if s.func_of(QUIT_FALL) != 8 or s.call_name(0x18910).split()[1] != 'f2':
        raise Refuse('quit fall-through: +0x188f8 not in func 8 / no m0xa88 set')
    if s.target(0x18e1c)[:2] != (8, 128): raise Refuse('quit fall-through does not open script 128')
    # ---- blocks
    while len(d) % 4: d.append(0)
    old_len = len(s.d)
    for a in range(old_len - old_len % 4, len(d), 4):
        words[a] = (None, struct.unpack_from('<I', d, a)[0], 'alignment')
    # element of the lock list: a WRITE is `0f a90; i; 21 14; 1e 1; 04 v; 2e` (func 19 / 20 / 8), a READ is
    # `0f a90; i; 21 14; 1b` (func 14 / 18) - tree 1 read with the write prefix (op1e) and crashed in the op1b handler
    lock13 = [(op(0x0f, LOCK), None, 'push member m0xa90 (lock list bool[14])'), (op(0x03, 13), None, 'index 13'),
              (op(0x21, 14), None, 'element of 14')]
    lock13_w = lock13 + [(op(0x1e, 1), None, 'op1e 1 (write form, as func 19 +0x3d98)')]
    one = [(op(0x03, 1), None, 'int 1'), (op(0x5c), None, 'int -> float')]
    show_bg = [(op(0x0f, BG14), None, 'push member 0x6b4 (background of position 14)'), (op(0x65), None, 'native call'),
               (PH, show, 'uibitmap f4 (show), as func 20 +0x4664')] + one * 4 + [
               (op(0x0f, BG14), None, 'push member 0x6b4'), (op(0x65), None, 'native call'),
               (PH, colour, 'uibitmap f18 colour (1, 1, 1, 1): opaque, untinted (func 21 hides with (1, 1, 1, 0); '
                            'func 28 leaves every background at alpha 0 until a ring animation fades it in)')]
    show_ic = [(op(0x0f, ICON14), None, 'push member 0x7bc (icon of position 14, door)'), (op(0x68), None, 'call'),
               (PH, f22, 'func 22 (show icon), as func 43 +0x106ac')]
    int_added, ext_added, blocks = [], [], {}
    for st in SITES:
        a = st['site']
        if s.w(a) != op(0, st['marker']) or a in s.it or a in s.ext or a in s.ids or s.func_of(a) != st['func']:
            raise Refuse('%s: +0x%x is %08x (func %s), expected op00 %d in func %d' % (st['key'], a, s.w(a),
                         s.func_of(a), st['marker'], st['func']))
        back = a + 4
        if s.w(back) != st['back_word']: raise Refuse('%s: +0x%x is %08x, expected %08x' % (st['key'], back,
                                                      s.w(back), st['back_word']))
        if back in jt: raise Refuse('%s: jumps from %s land on the return address +0x%x (would skip the block)' % (
            st['key'], ', '.join('+0x%x' % x for x in jt[back]), back))
        if 'dialog' in st:
            set_at, val, open_at, sid = st['dialog']
            lo = set_at
            if s.w(set_at) != op(0x03, val) or s.w(set_at + 4) != op(0x0f, 0xa88) or s.target(open_at + 4)[:2] != (8, sid):
                raise Refuse('%s: no m0xa88 = %d at +0x%x / script %d at +0x%x' % (st['key'], val, set_at, sid, open_at))
            seen = {LOCK: 0, ICON14: 0}
            for o, opc, w, ex in s.instrs(lo, a):
                if opc == 0x0f and (w & 0xffffff) in seen: seen[w & 0xffffff] += 1
            if seen[LOCK] != 7 or seen[ICON14] != 1:
                raise Refuse('%s: block +0x%x..+0x%x has %d lock writes / %d uses of 0x7bc (expected 7 / 1)' % (
                    st['key'], lo, a, seen[LOCK], seen[ICON14]))
            for o, opc, w, ex in s.instrs(back, open_at + 8):
                if opc in (0x0c, 0x0e, 0x0f) and (w & 0xffffff) in (LOCK, ICON14, BG14, HIT14):
                    raise Refuse('%s: +0x%x touches 0x%x after the site' % (st['key'], o, w & 0xffffff))
        code = [(op(0, st['marker']), None, 'the replaced debug line marker op00 %d' % st['marker'])]
        if st['kind'] == 'show':
            code += show_bg + show_ic
        elif st['kind'] == 'refree':
            code += lock13_w + [(op(0x04, 0), None, 'value 0'), (op(0x2e), None, 'store: m0xa90[13] = 0 (free)')]
            code += show_bg + show_ic
        else:
            code += [(op(0x09, 0xb2), None, 'push &local 0xb2 (result; the slot-7 test +0x188ac uses it the same way)'),
                     (op(0x09, 0xb4), None, 'push &local 0xb4'), (op(0x0f, HIT14), None, 'push hit area 0x170 (position 14)'),
                     (op(0x65), None, 'native call'), (PH, hit, 'hit area f14, as +0x188b8'),
                     (op(0x09, 0xb4), None, 'push &local 0xb4'), (op(0x09, 0), None, 'push &local 0 (the input event)'),
                     (op(0x65), None, 'native call'), (PH, inp, 'input f0, as +0x188c8'),
                     (op(0x06, 0xb2), None, 'push local 0xb2 (clicked)')]
            code += lock13 + [(op(0x1b), None, 'load m0xa90[13]'), (op(0x50), None, 'NOT (position 14 free)'),
                              (op(0x51), None, 'AND'), (op(0x64, 1), None, 'false -> skip the next jump')]
            code += [(None, ('jmp', QUIT_FALL), 'op63 to the PC quit fall-through +0x%x' % QUIT_FALL)]
        code += [(None, ('jmp', back), 'op63 back to +0x%x' % back)]
        block = len(d)
        for q, (word, rel, why) in enumerate(code):
            at = block + 4 * q
            if rel and rel[0] == 'jmp': word = op(0x63, (rel[1] - (at + 4)) // 4)
            d += struct.pack('<I', word)
            words[at] = (None, word, '%s: %s' % (st['key'], why))
            if rel and rel[0] == 'ext': ext_added.append((rel[1], at, rel[2]))
            elif rel and rel[0] == 'int': int_added.append((at, rel[1]))
        jump = op(0x63, (block - (a + 4)) // 4)
        words[a] = (op(0, st['marker']), jump, '%s: op00 %d -> op63 to the block +0x%x (%s)' % (
            st['key'], st['marker'], block, st['note']))
        blocks[st['key']] = dict(site=a, block=block, words=len(code), back=back)
    for a, (old, new, why) in words.items():
        if a + 4 <= len(d): struct.pack_into('<I', d, a, new)
    r.internal += int_added; r.external += ext_added
    info = dict(words=words, ext_changed=ext_changed, ext_added=ext_added, int_added=int_added, blocks=blocks,
                forms=forms, old_size=old_len, new_size=len(d))
    return bytes(d), r, info


# ---- decode a built file by itself ----------------------------------------------------------------------------

class Secs:
    """D-like view on [(type, id, data, reloc)] as tools/script_func_list.sections returns them"""
    def __init__(self, S):
        import types
        self.sections = [types.SimpleNamespace(type=t, id=i, data=d, reloc=r) for t, i, d, r in S]


def p14_full(st):
    """True when a p14_status() shows the complete stage-light layout"""
    return (st['slot7'] == 'f15' and st['lock14_base'] == 0 and st['place14_pc'] and st['icon14'] == D4['new'] and
            st['text14'] == D5['new'] and st['bg14'] == D6['new'] and len(st['shows']) == 1 and
            len(st['refree']) == 3 and st['quit_click'])


def trigrams(s, lo, hi):
    """opcode 3-grams of the instructions in [lo, hi), debug line markers (op00) left out, never across a jump:
    the sequence is cut after every op63 / op64 (the condition is consumed there, the expression stack is empty), so
    the 3-grams describe expression / statement shapes, not the order of the appended control flow"""
    out, run = [], []
    for o, opc, w, ex in s.instrs(lo, hi):
        if opc == 0x00: continue
        run.append(opc)
        if opc in JUMPS:
            out += [tuple(run[k:k + 3]) for k in range(len(run) - 2)]; run = []
    out += [tuple(run[k:k + 3]) for k in range(len(run) - 2)]
    return out


def shape_gate(sb, sa, info):
    """every opcode 3-gram of every appended block must occur in the code of the original script 7 (BEFORE):
    the blocks only re-use statement shapes the compiler produced (catches e.g. a read written with the store prefix
    op1e, tree 1's crash) - returns the problems"""
    known = set()
    for j, lo, hi in sb.code: known.update(trigrams(sb, lo, hi))
    probs = []
    for key, b in info['blocks'].items():
        for g in trigrams(sa, b['block'], b['block'] + 4 * b['words']):
            if g not in known:
                probs.append('%s block +0x%x: opcode sequence %s does not occur in the original script 7' % (
                    key, b['block'], ' '.join('op%02x' % x for x in g)))
    return probs


def p14_status(D):
    """state of position 14 / slot 7 in script 7 of D, decoded without the plan:
    {'slot7': form, 'lock14_base': value func 19 stores in m0xa90[13], 'place14_pc': bool, 'icon14': texture,
     'text14': locals id, 'shows': [block sites showing 0x7bc], 'refree': [...], 'click': [(site, jump target)]}"""
    s = S7(D)
    extmap = {so: s.target(so) for so in s.ext}
    forms = {QS.classify(s.d, extmap, base, loc, jz, marker)[0] for key, what, base, loc, jz, marker in QS.SITES}
    out = dict(slot7=forms.pop() if len(forms) == 1 else 'mixed')
    lo, hi = s.func_range(19)
    vals = []
    ins = list(s.instrs(lo, hi))
    for k, (o, opc, w, ex) in enumerate(ins):
        seq = [x[2] for x in ins[k:k + 6]]
        if seq[:4] == [op(0x0f, LOCK), op(0x03, 13), op(0x21, 14), op(0x1e, 1)] and seq[5] == op(0x2e):
            vals.append(seq[4] & 0xffffff)
    out['lock14_base'] = vals[-1] if vals else None
    out['place14_pc'] = s.w(D3['at']) >> 24 == 0x00 and s.w(D3['at'] + 0xc) == op(0x0f, ICON14)
    out['icon14'] = s.w(s.init_word(ICON14, 0x5c)); out['text14'] = s.w(s.init_word(TEXT14, 0x5c))
    out['bg14'] = s.w(s.init_word(BG14, 0x5c))
    end = max(hi for j, lo, hi in s.code)
    shows, refree, click = [], [], []
    for j, lo, hi in s.code:
        for o, opc, w, ex in s.instrs(lo, hi):
            if opc != 0x63: continue
            t = o + 4 + 4 * s24(w)
            if t < end: continue
            blk = []
            for b, bop, bw, bex in s.instrs(t, len(s.d)):
                blk.append((b, bop, bw, bex))
                if bop == 0x63 and b + 4 + 4 * s24(bw) <= end and b + 4 + 4 * s24(bw) == o + 4: break
                if len(blk) > 64: break
            mem = [bw & 0xffffff for b, bop, bw, bex in blk if bop == 0x0f]
            jumps = [b + 4 + 4 * s24(bw) for b, bop, bw, bex in blk if bop == 0x63]
            if ICON14 in mem and LOCK not in mem: shows.append('f%d +0x%x' % (j, o))
            if ICON14 in mem and LOCK in mem: refree.append('f%d +0x%x' % (j, o))
            if HIT14 in mem and LOCK in mem:
                click.append(('f%d +0x%x' % (j, o), ['+0x%x' % x for x in jumps if x != o + 4]))
    out.update(shows=shows, refree=refree, click=click)
    out['quit_click'] = any(QUIT_FALL == int(x[1:], 16) for site, js in click for x in js)
    return out


def decode_blocks(s, info):
    """AFTER by itself: every planned site is an op63 into the appended area; the block's instructions resolved to
    (opcode, operand / member / call name / jump target) - compared with the same resolution of the plan's words"""
    probs, rows = [], []
    for key, b in info['blocks'].items():
        j = s.w(b['site'])
        if j >> 24 != 0x63 or b['site'] + 4 + 4 * s24(j) != b['block']:
            probs.append('%s: +0x%x is %08x, not op63 to +0x%x' % (key, b['site'], j, b['block'])); continue
        lo, hi = b['block'], b['block'] + 4 * b['words']
        res = []
        for o, opc, w, ex in s.instrs(lo, hi):
            if opc in (0x65, 0x66): res.append('op%02x %s' % (opc, s.call_name(ex[0])))
            elif opc == 0x68: res.append('op68 func %s' % s.proto_func(s.it.get(ex[0])))
            elif opc in JUMPS: res.append('op%02x -> +0x%x' % (opc, o + 4 + 4 * s24(w)))
            else: res.append('op%02x %d' % (opc, s24(w) if opc in (0x03, 0x04) else w & 0xffffff))
        rows.append((key, b, res))
    return rows, probs


_SHOW = ['op0f 1716', 'op65 uibitmap f4 (+0xf4)'] + ['op03 1', 'op5c 0'] * 4 + [
    'op0f 1716', 'op65 uibitmap f18 (+0x27c)', 'op0f 1980', 'op68 func 22']
EXPECT_BLOCK = {
    'show': ['op00 M'] + _SHOW + ['op63 -> BACK'],
    'refree': ['op00 M', 'op0f 2704', 'op03 13', 'op21 14', 'op1e 1', 'op04 0', 'op2e 0'] + _SHOW + ['op63 -> BACK'],
    'click': ['op00 M', 'op09 178', 'op09 180', 'op0f 368', 'op65 HIT', 'op09 180', 'op09 0', 'op65 IN', 'op06 178',
              'op0f 2704', 'op03 13', 'op21 14', 'op1b 0', 'op50 0', 'op51 0', 'op64 -> SKIP',
              'op63 -> +0x188f8', 'op63 -> BACK'],
}


def verify(rb, ra, names=('BEFORE', 'AFTER')):
    """rb / ra raw files -> (report dict, problems)"""
    B, A = DW.read(rb, 'le'), DW.read(ra, 'le')
    bad = []
    rep = dict(before=names[0], after=names[1], md5_before=hashlib.md5(rb).hexdigest(),
               md5_after=hashlib.md5(ra).hexdigest(), script=SID)
    for k in ('ver', 'names', 'pad', 'u0', 'u1'):
        if getattr(B, k, None) != getattr(A, k, None): bad.append('file header %s differs' % k)
    if len(B.sections) != len(A.sections): bad.append('section count %d -> %d' % (len(B.sections), len(A.sections)))
    same = 0; k7 = None
    for i, (b, a) in enumerate(zip(B.sections, A.sections)):
        hdr = [k for k in ('type', 'id', 'flags', 'ver', 'spec', 'pad') if getattr(b, k, None) != getattr(a, k, None)]
        if hdr: bad.append('section %d (%d:%d): header %s differs' % (i, b.type, b.id, ', '.join(hdr)))
        elif b.type == 8 and b.id == SID: k7 = i
        elif b.data != a.data or b.reloc != a.reloc:
            bad.append('section %d (%d:%d) differs - unexplained' % (i, b.type, b.id))
        else: same += 1
    rep['sections'] = len(B.sections); rep['sections_identical'] = same
    words = []
    try:
        ed, er, info = plan(B)
    except Refuse as e:
        bad.append('BEFORE: %s' % e); info = None
    if info and k7 is not None:
        db, da = B.sections[k7].data, A.sections[k7].data
        if len(da) != len(ed): bad.append('script 7 size %d -> %d, the plan gives %d' % (len(db), len(da), len(ed)))
        n = max(len(db), len(da))
        for off in range(0, n - n % 4, 4):
            old = struct.unpack_from('<I', db, off)[0] if off + 4 <= len(db) else None
            new = struct.unpack_from('<I', da, off)[0] if off + 4 <= len(da) else None
            if old == new and off not in info['words']: continue
            exp = info['words'].get(off)
            if exp is None:
                bad.append('+0x%x: %s -> %s - unexplained word' % (off, '%08x' % old if old is not None else '-',
                           '%08x' % new if new is not None else '-'))
            elif new != exp[1] or (exp[0] is not None and old != exp[0]):
                bad.append('+0x%x: %s -> %s, the plan says %s -> %08x (%s)' % (off, old, new, exp[0], exp[1], exp[2]))
            elif old != new:
                words.append(dict(offset='0x%x' % off, old='%08x' % old if old is not None else None, new='%08x' % new,
                                  why=exp[2]))
        rb_, ra_ = R.parse(B.sections[k7].reloc, 'le'), R.parse(A.sections[k7].reloc, 'le')
        for k in ('idref_a', 'unk3', 'idref'):
            if getattr(ra_, k) != getattr(rb_, k): bad.append('relocations %s differ - unexplained' % k)
        n0 = len(rb_.internal)
        if ra_.internal[:n0] != rb_.internal: bad.append('existing internal relocations changed')
        if ra_.internal[n0:] != info['int_added']: bad.append('appended internal relocations differ from the plan')
        m0 = len(rb_.external)
        want = [(info['ext_changed'][so][1][0], so, info['ext_changed'][so][1][1]) if so in info['ext_changed']
                else (si, so, do) for si, so, do in rb_.external]
        if ra_.external[:m0] != want: bad.append('existing external relocations differ from the plan')
        if ra_.external[m0:] != info['ext_added']: bad.append('appended external relocations differ from the plan')
        rep['relocations'] = dict(external_retargeted=['+0x%x: (section %d, +0x%x) -> (section %d, +0x%x)' % (
            so, o[0], o[1], nw[0], nw[1]) for so, (o, nw) in sorted(info['ext_changed'].items())],
            external_added=len(info['ext_added']), internal_added=len(info['int_added']))
        # AFTER by itself
        try:
            sa, sb = S7(A), S7(B)
            if sa.W.bad != sb.W.bad: bad.append('walker problems %s -> %s' % (sb.W.bad, sa.W.bad))
            rep['walker_problems'] = [list(x) for x in sa.W.bad]
            st = p14_status(A); rep['status'] = st
            if st['slot7'] != 'f15': bad.append('slot 7 sites: %s, expected f15' % st['slot7'])
            if st['lock14_base'] != 0: bad.append('func 19 stores %s in m0xa90[13], expected 0' % st['lock14_base'])
            if not st['place14_pc']: bad.append('func 29 case 14 still gated')
            if (st['icon14'], st['text14'], st['bg14']) != (D4['new'], D5['new'], D6['new']):
                bad.append('icon / text / background %s' % ((st['icon14'], st['text14'], st['bg14']),))
            if not st['quit_click']: bad.append('no click block to the quit fall-through')
            rows, probs = decode_blocks(sa, info)
            bad += probs
            shape = shape_gate(sb, sa, info)
            bad += shape
            rep['shape_gate'] = dict(blocks=len(info['blocks']), unknown_sequences=len(shape))
            dec = {}
            for key, b, res in rows:
                st_ = next(x for x in SITES if x['key'] == key)
                exp = [x.replace('M', str(st_['marker'])).replace('BACK', '+0x%x' % b['back'])
                       .replace('HIT', 'hit f14').replace('IN', 'in f0') for x in EXPECT_BLOCK[st_['kind']]]
                got = list(res)
                if st_['kind'] == 'click':
                    skip_to = b['block'] + 4 * (b['words'] - 1)
                    exp = [x.replace('SKIP', '+0x%x' % skip_to) for x in exp]
                    hitn, inn = sa.call_name(b['block'] + 4 * 5), sa.call_name(b['block'] + 4 * 9)
                    href, iref = sb.call_name(REF_HIT[0] + 4), sb.call_name(REF_IN[0] + 4)
                    if hitn != href or inn != iref: bad.append('%s: calls %s / %s, slot-7 test %s / %s' % (key, hitn,
                                                               inn, href, iref))
                    got = ['op65 hit f14' if x == 'op65 ' + hitn else 'op65 in f0' if x == 'op65 ' + inn else x
                           for x in res]
                if got != exp: bad.append('%s block +0x%x decodes to %s, expected %s' % (key, b['block'], got, exp))
                dec[key] = dict(site='0x%x' % b['site'], block='0x%x' % b['block'], code=res)
            rep['blocks'] = dec
        except Refuse as e:
            bad.append('AFTER: %s' % e)
    elif k7 is None:
        bad.append('no script 7')
    rep['words'] = words; rep['problems'] = bad; rep['result'] = 'ok' if not bad else 'REFUSED'
    return rep, bad


def print_report(rep):
    for x in rep['words']:
        print('  +%-7s %s -> %s  %s' % (x['offset'], x['old'] or '--------', x['new'], x['why']))
    for k, v in rep.get('relocations', {}).items():
        print('  relocations %s: %s' % (k, v))
    for k, v in rep.get('blocks', {}).items():
        print('  %s site +%s -> block +%s: %s' % (k, v['site'], v['block'], ' | '.join(v['code'])))
    if 'status' in rep: print('  status: %s' % rep['status'])
    for x in rep['problems']: print('  PROBLEM: ' + x)
    print('verify script 7: %d words changed / appended, %d of %d other sections identical, walker problems %s - %s'
          % (len(rep['words']), rep.get('sections_identical', 0), rep.get('sections', 1) - 1,
             rep.get('walker_problems'), rep['result']))


def main(argv):
    report = None
    if '--report' in argv: k = argv.index('--report'); report = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 3 or argv[0] not in ('build', 'verify'): sys.exit(__doc__)
    cmd, a, b = argv
    if cmd == 'build':
        raw_in = open(a, 'rb').read()
        D = DW.read(raw_in, 'le')
        try:
            data, rel, info = plan(D)
        except Refuse as e:
            sys.exit('REFUSED: %s' % e)
        s = D.sections[S7(D).k]
        s.data = data; s.reloc = R.write(rel, 'le')
        raw = D.write('le'); C = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
        infos = [dict(size=len(x.data)) for x in C.sections]
        nbad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in C.sections)
        if nbad: sys.exit('%d sections with relocations out of bounds - %s NOT written' % (nbad, b))
        os.makedirs(os.path.dirname(os.path.abspath(b)), exist_ok=True)
        open(b, 'wb').write(DW.cdrm_encode(raw, 'le'))
        print('built %s: script 7 %d -> %d bytes, slot-7 sites were %s, relocations out of bounds 0' % (
            b, info['old_size'], info['new_size'], '/'.join(info['forms'])))
    rep, bad = verify(open(a, 'rb').read(), open(b, 'rb').read(), (a, b))
    print_report(rep)
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(rep, open(report, 'w', encoding='utf-8'), indent=1)
    if bad:
        if cmd == 'build':
            os.remove(b); print('VERIFY FAILED - %s removed' % b)
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
