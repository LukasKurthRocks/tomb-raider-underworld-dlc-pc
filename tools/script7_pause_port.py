"""Port the pause signalling and the DLC 1 help refresh of the title update's pause menu (Xbox TU generalbank script 7,
"uipause") into the PC's own script 7 - nothing else of the TU script (2026-11-03, workspace Befund-Pausemenue-TU.md).

What the TU adds to script 7 (tools/tu_script_func_diff.py, work/night_analyses/tu_cosmetic/diff_7_xl_xt_masked.txt):
  (a) the "NEW DOWNLOAD AVAILABLE ON XBOX LIVE" banner: function Symbol 16978, 12 uibitmap members, 12 textures,
      its calls in f0 / f3 and the language switch in f8                           -> NOT ported (Xbox Live advert)
  (b) open  (TU f2, Symbol 519 = PC f1 / 521): `uipopupmgr` f8 replaced by messagechannel(PauseMsgCh).f2("paused", 0)
      close (TU f3, Symbol 520 = PC f2 / 522): messagechannel(PauseMsgCh).f2("unpaused", 0) after the uipopupmgr f1
      receivers: the ported hint box (PC script 9 = TU 10) and the DLC 2 PDA                           -> ported
  (c) TU f8 (523 = PC f8 / 525) and TU f40 (992 = PC f43 / 1019), right before the Help-on-Demand refresh call into
      script 74: unit = corebase.f14(uigamedata.f33()); if corebase.f34(unit, 3) == "dlc":
      messagechannel(HODRefresh).f2("DLC", 1) else the old HOD refresh                                   -> ported
      receiver: DLC 1 `dlc_dispatcher` script 24319 (member 16900 "HODRefresh", installed on PC)
The PC script 7 is Nixxes' own, larger version (mouse / keyboard, save with name); it is kept as it is and only gets:
  * 2 data members appended (TU m343 / m344: messagechannel, init {0, "HODRefresh" / "PauseMsgCh", 0}) at the next
    free instance offsets (3208 / 3228, instance size 3205 -> 3248), entry copied from the PC's own messagechannel
    member (tag / userType / type id) with the name Symbols the converter's map gives (16420 -> 16900, 16924 -> 17404 -
    the same names the installed DLC 1 dispatcher and our ported hint box use);
  * 2 start-function-info entries (script 64 + offset, highest first as in the TU: the engine constructs these objects);
  * 3 string locals appended to PC f8 and to PC f43 (TU added 3 string locals to both functions; frame + 12 bytes,
    stackSize = max(PC, TU));
  * 4 code blocks, translated word by word from the TU blocks, appended to the section; each reached by an `op63` that
    replaces one debug line marker (op00) at the TU's insertion point and jumping back the way the TU code flows.
New arrays (members, sfi, locals) are appended copies; the old arrays stay in place with their relocations (orphaned).
Every word that is replaced is checked first; the tool refuses on any mismatch, an unmapped operand, a script that
inherits from script 7 or an external pointer into the arrays it re-homes. After writing it re-reads OUT and decodes
the 4 blocks again against the TU blocks (opcodes, immediates, strings, native targets by name Symbol, members, locals).

Translation tables (all checked, none guessed):
  natives: Xbox target -> PC script with the same native name, function whose prototype name Symbol equals the
           converter's map of the Xbox one (dlc_generic.DlcIds.sym, TRUDLC_SYM_EXTRA = work/rebuild/sym_base_evidence.json
           as in generalbank_build step 2) - e.g. uigamedata f33 (+0x400) -> PC f34 (+0x41c), as in our ported script 6;
  members: TU 2900 (the uigamedata object) -> the PC's only member of type script 63 (2764); TU 3264 / 3284 -> new;
  locals : the TU's new string locals -> the new PC string locals (ascending offsets).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script7_pause_port.py IN_GENERALBANK OUT_GENERALBANK [--keep-popupmgr]
  --keep-popupmgr: NOT the TU - also keep the PC's uipopupmgr f8 call after "paused" (fallback variant, unused)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC
import script_func_list as FL
import menu_dlc_probe as P

SID = 7
PH = 0xBEEBBEEB                 # pointer placeholder the PC files hold under a relocation
EXTRA = dict(SC.Walk.EXTRA); EXTRA[P.PUSHF] = 1

# TU blocks (Xbox TU script 7 offsets): [lo, hi) = the inserted instructions; hi = where the TU's own flow continues
# PC sites (PC script 7 offsets): the op00 marker that becomes `op63 -> block`, expected marker value, back targets
SITES = [
    dict(key='paused', tu=(0x6be4, 0x6bfc), tu_func=2, pc_func=1, site=0x401c, marker=70, back=0x402c,
         skipped=[(0x4020, 0x0f000ba8)], note='TU f2 (519) / PC f1 (521) OnOpen: replaces the uipopupmgr f8 call'),
    dict(key='unpaused', tu=(0xed34, 0xed4c), tu_func=3, pc_func=2, site=0x8280, marker=151, back=0x8284,
         skipped=[], note='TU f3 (520) / PC f2 (522) OnClose: after the uipopupmgr f1 call'),
    dict(key='hod_f8', tu=(0x1a130, 0x1a1a0), tu_func=8, pc_func=8, site=0x1b374, marker=0x5d1, back=0x1b3a0,
         back_else=0x1b378, tu_else=(0x1a1a4, 0x1a1cc), note='TU f8 (523) / PC f8 (525): DLC unit -> HODRefresh "DLC"'),
    dict(key='hod_f43', tu=(0x113ec, 0x1145c), tu_func=40, pc_func=43, site=0x12978, marker=0x1294, back=0x129a4,
         back_else=0x1297c, tu_else=(0x11460, 0x11488), note='TU f40 (992) / PC f43 (1019): same'),
]
TU_NEW_MEMBERS = (3264, 3284)   # TU m343 HODRefresh, m344 PauseMsgCh (messagechannel)
SFI_ENTRY, MEMBER_ENTRY, LOCAL_ENTRY, FUNC_ENTRY = 8, 20, 20, 28


def op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def sarg(w):
    a = w & 0xffffff
    return a - 0x1000000 if a & 0x800000 else a


class Script:
    """one script section with its walker, relocation lookups and element tables"""
    def __init__(self, data, reloc, e, sections):
        self.d, self.e, self.E = data, e, ('>' if e == 'be' else '<')
        self.rel = R.parse(reloc, e)
        self.it = dict(self.rel.internal)
        self.ext = {so: (si, do) for si, so, do in self.rel.external}
        self.ids = self.rel.id_offsets()
        self.S = sections
        self.W = SC.Walk(data, self.rel, e).run()
        self.arr = {name: (t, n, sz) for name, t, n, sz in self.W.arrays if name in ('members', 'sfi', 'protos', 'funcs', 'deps')}

    def u32(self, o): return struct.unpack_from(self.E + 'I', self.d, o)[0]
    def u16(self, o): return struct.unpack_from(self.E + 'H', self.d, o)[0]

    def func(self, k):
        t, n, sz = self.arr['funcs']; return t + sz * k

    def members(self):
        t, n, sz = self.arr['members']
        for k in range(n):
            a = t + sz * k
            yield a, self.u16(a + 12), self.u16(a + 14), self.u32(a), self.u16(a + 4), self.u32(a + 8)

    def member_at(self, off):
        return next((m for m in self.members() if m[1] == off), None)

    def init_string(self, a):
        """messagechannel init {u32, char*, u32} behind member entry a: (word0, name)"""
        i = self.it.get(a + 16)
        if i is None or i not in self.it: return None
        node = self.it[i]
        return self.u32(node), (P.cstr(self.d, self.it[node + 4]) if node + 4 in self.it else None)

    def locals(self, k):
        f = self.func(k); lt = self.it.get(f + 12)
        n = self.u32(lt - 4) if lt is not None else 0
        return [(lt + LOCAL_ENTRY * j, self.u16(lt + LOCAL_ENTRY * j + 12), self.u16(lt + LOCAL_ENTRY * j + 14),
                 self.u32(lt + LOCAL_ENTRY * j)) for j in range(n)]

    def frame(self, k):
        f = self.func(k); return self.u16(f + 6), self.u16(f + 10)

    def target(self, o):
        """external pointer at o -> (type, id, offset)"""
        si, do = self.ext[o]; return self.S[si][0], self.S[si][1], do

    def instrs(self, lo, hi):
        o = lo
        while o < hi:
            w = self.u32(o); op_ = w >> 24
            ex = [o + 4 * (j + 1) for j in range(EXTRA.get(op_, 0))]
            yield o, op_, w, ex
            o += 4 * (1 + len(ex))
        if o != hi: raise SystemExit('instruction walk overran the block end 0x%x (at 0x%x)' % (hi, o))


def native_index(S, e):
    """{script id: (package, native name)} and per native script {function entry offset: proto name Symbol}"""
    names, funcs = {}, {}
    for ty, sid, d, rl in S:
        if ty != 8 or not d: continue
        info = P.script_info({'data': d, 'reloc': rl}, e)[:2]
        if not info[1]: continue
        names[sid] = info
        sc = Script(d, rl, e, S)
        pt = {}
        if 'protos' in sc.arr:
            t, n, sz = sc.arr['protos']
            pt = {t + sz * k: sc.u16(t + sz * k + 8) for k in range(n)}
        ft = {}
        if 'funcs' in sc.arr:
            t, n, sz = sc.arr['funcs']
            for k in range(n):
                a = t + sz * k
                ft[a] = (k, pt.get(sc.it.get(a)))
        funcs[sid] = ft
    return names, funcs


def main(argv):
    keep_popup = '--keep-popupmgr' in argv
    argv = [a for a in argv if a != '--keep-popupmgr']
    src, out = argv[0], argv[1]
    os.environ.setdefault('TRUDLC_SYM_EXTRA', os.path.join('work', 'rebuild', 'sym_base_evidence.json'))
    import dlc_generic as DG
    ids = DG.DlcIds()

    raw_in = open(src, 'rb').read()
    D = DW.read(raw_in, 'le')
    PS = [(x.type, x.id, x.data, x.reloc) for x in D.sections]
    XS, xe = FL.sections('xt')
    idx = {(x.type, x.id): i for i, x in enumerate(D.sections)}
    s = D.sections[idx[(8, SID)]]
    pc = Script(s.data, s.reloc, 'le', PS)
    xd, xrl = next((q[2], q[3]) for q in XS if q[0] == 8 and q[1] == SID and q[2])
    tu = Script(xd, xrl, xe, XS)
    xnames, xfuncs = native_index(XS, xe)
    pnames, pfuncs = native_index(PS, 'le')
    log = []
    L = lambda *a: log.append(' '.join(str(x) for x in a))

    # ---- preconditions ------------------------------------------------------------------------------------------
    size, align = pc.u16(0x1c), pc.u16(0x1e)
    if (size, align) != (3205, 4): sys.exit('PC script 7 instance size/align %d/%d, expected 3205/4 - nothing written' % (size, align))
    for sid_other, sec in ((x.id, x) for x in D.sections if x.type == 8 and x.data and x.id != SID):
        rr = R.parse(sec.reloc, 'le')
        if 0x18 in rr.id_offsets() and struct.unpack_from('<I', sec.data, 0x18)[0] == SID:
            sys.exit('script %d inherits from script 7 - its members would overlap the new ones; nothing written' % sid_other)
        for si, so, do in rr.external:
            if si != idx[(8, SID)]: continue
            for name in ('members', 'sfi'):
                t, n, sz = pc.arr[name]
                if t - 4 <= do < t + n * sz:
                    sys.exit('script %d +0x%x points into script 7 %s (+0x%x) - nothing written' % (sid_other, so, name, do))
    deps_t, deps_n, _ = pc.arr['deps']
    deps = {pc.u32(deps_t + 4 * k) for k in range(deps_n)}
    for need in (63, 64):           # corebase (230) is never listed (TU / retail / PC script 7 call it without a dependency)
        if need not in deps: sys.exit('script 7 does not depend on script %d - nothing written' % need)
    for st in SITES:
        a = st['site']
        if a in pc.it or a in pc.ext or a in pc.ids or pc.u32(a) != op(0, st['marker']):
            sys.exit('%s: +0x%x expected op00 %d without relocation, found %08x - nothing written' % (st['key'], a, st['marker'], pc.u32(a)))
        for b, v in st.get('skipped', []):
            if pc.u32(b) != v: sys.exit('%s: +0x%x expected %08x, found %08x' % (st['key'], b, v, pc.u32(b)))
    # the skipped popup call: op65 -> uipopupmgr f8
    pt = pc.target(0x4028)
    if pc.u32(0x4024) >> 24 != 0x65 or pnames.get(pt[1], (None, None))[1] != 'uipopupmgr' or pfuncs[pt[1]][pt[2]][0] != 8:
        sys.exit('PC f1 +0x4024 is not the uipopupmgr f8 call - nothing written')
    # the TU removed exactly this call: retail f1 had uipopupmgr f8 where TU f2 sends "paused" (masked diff); the TU
    # word before the block is the debug marker, the next one after it as well
    # PC else blocks (Help-on-Demand refresh) = TU else blocks (opcodes, call targets by native / script name)
    for st in SITES:
        if 'tu_else' not in st: continue
        a = [(o_, w >> 24) for o_, _, w, _ in tu.instrs(*st['tu_else'])]
        b = [(o_, w >> 24) for o_, _, w, _ in pc.instrs(st['back_else'], st['back'])]
        if [x[1] for x in a] != [x[1] for x in b]:
            sys.exit('%s: PC block 0x%x..0x%x is not the TU else block (%s / %s)' % (st['key'], st['back_else'], st['back'], a, b))
        L('%s: PC +0x%x..+0x%x = TU else block +0x%x..+0x%x (%d instructions, same opcodes)' % (
            st['key'], st['back_else'], st['back'], st['tu_else'][0], st['tu_else'][1], len(a)))

    # ---- translation tables -------------------------------------------------------------------------------------
    def ext_map(o):
        ty, xsid, xoff = tu.target(o)
        if ty != 8 or xsid not in xnames: sys.exit('TU +0x%x: call target %s is not a native script' % (o, (ty, xsid, xoff)))
        nat = xnames[xsid]
        psid = [k for k, v in pnames.items() if v == nat]
        if len(psid) != 1: sys.exit('native %s: %d PC scripts' % (nat, len(psid)))
        psid = psid[0]
        xk, xsym = xfuncs[xsid][xoff]
        want = ids.sym(xsym)
        hit = [(a, k) for a, (k, nm) in pfuncs[psid].items() if nm == want]
        if len(hit) != 1: sys.exit('native %s f%d (Symbol %d -> %d): %d PC functions with that name' % (nat[1], xk, xsym, want, len(hit)))
        return psid, hit[0][0], '%s f%d (+0x%x, Symbol %d) -> PC script %d f%d (+0x%x, Symbol %d)%s' % (
            nat[1], xk, xoff, xsym, psid, hit[0][1], hit[0][0], want, '' if hit[0][0] == xoff else '  [other offset]')

    # members: the uigamedata object + the two new channels
    new_off = {}
    nxt = (size + 3) & ~3
    for xo in TU_NEW_MEMBERS:
        m = tu.member_at(xo)
        ini = tu.init_string(m[0])
        if m[5] != 64 or m[4] != 219 or not ini: sys.exit('TU member %d is not a messagechannel with a name' % xo)
        new_off[xo] = dict(pc=nxt, name_x=m[2], name=ids.sym(m[2]), init=ini, tag=m[3])
        nxt += 20                                   # messagechannel object size (PC members 140 -> 160, script 9 60 -> 80)
    new_size = nxt
    mm = {}
    for st in SITES:
        for o_, opc, w, ex in tu.instrs(*st['tu']):
            if opc in (0x0f, 0x0c, 0x10):
                xo = w & 0xffffff
                if xo in new_off: mm[xo] = new_off[xo]['pc']; continue
                m = tu.member_at(xo)
                cand = [p for p in pc.members() if p[5] == m[5]]
                if m[5] != 63 or xnames.get(63, (0, 0))[1] != pnames.get(63, (0, 1))[1] or len(cand) != 1:
                    sys.exit('TU member %d (type script %d): no unique PC counterpart (%d)' % (xo, m[5], len(cand)))
                mm[xo] = cand[0][1]
    for xo, po in sorted(mm.items()): L('member TU %d -> PC %d' % (xo, po))
    # locals per function: TU string locals used by the block -> new PC locals at the end of the frame
    lmaps = {}
    for st in SITES:
        used = []
        for o_, opc, w, ex in tu.instrs(*st['tu']):
            if opc in (0x08, 0x09, 0x0a) and (w & 0xffffff) not in used: used.append(w & 0xffffff)
        if not used: continue
        tl = {off: (nm, tag) for _, off, nm, tag in tu.locals(st['tu_func'])}
        fsz, fstack = pc.frame(st['pc_func'])
        lm = {}
        for k, xo in enumerate(sorted(used)):
            if tl.get(xo, (0, 0))[1] != 0x34: sys.exit('%s: TU local %d is not a string local' % (st['key'], xo))
            lm[xo] = dict(pc=fsz + 4 * k, name_x=tl[xo][0], name=ids.sym(tl[xo][0]))
        lmaps[st['key']] = lm
        L('%s: TU locals %s -> PC f%d frame %d -> %d' % (st['key'], ', '.join('%d->%d (name %d->%d)' % (
            xo, v['pc'], v['name_x'], v['name']) for xo, v in sorted(lm.items())), st['pc_func'], fsz, fsz + 4 * len(lm)))
    # the two name Symbols must be what the installed DLC 1 dispatcher / our hint box use (evidence, not a guess)
    expect_names = {3264: 16900, 3284: 17404}
    for xo, v in new_off.items():
        if v['name'] != expect_names[xo]:
            sys.exit('member %d: map gives name %d, the installed PC scripts use %d' % (xo, v['name'], expect_names[xo]))
        L('new member PC %d: name %d (TU %d), init (%d, %r), TU %d' % (v['pc'], v['name'], v['name_x'], v['init'][0], v['init'][1], xo))

    # ---- build --------------------------------------------------------------------------------------------------
    d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    def pad():
        while len(d) % 4: d.append(0)
    def put(a, v): struct.pack_into('<I', d, a, v)
    def dup(lo, hi, delta):
        r.internal += [(a + delta, t) for a, t in list(r.internal) if lo <= a < hi]
        r.external += [(si, a + delta, dd) for si, a, dd in list(r.external) if lo <= a < hi]
        r.idref += [(t, a + delta) for t, a in list(r.idref) if lo <= a < hi]
        r.idref_a += [(t, a + delta) for t, a in list(r.idref_a) if lo <= a < hi]
    def retarget(a, t):
        n0 = len(r.internal)
        r.internal = [(x, y) for x, y in r.internal if x != a]
        if len(r.internal) != n0 - 1: sys.exit('no internal pointer at +0x%x' % a)
        r.internal.append((a, t))
    def idkind(a):
        for nm in ('idref', 'idref_a'):
            if any(o == a for _, o in getattr(r, nm)): return nm
        sys.exit('no id reference at +0x%x' % a)
    strings = {}
    def string(txt):
        if txt not in strings:
            pad(); strings[txt] = len(d); d.extend(txt.encode('ascii') + b'\0'); pad()
        return strings[txt]
    def init_block(words_ptr):
        """[(word, target or None)] -> offset of the appended block"""
        pad(); a = len(d)
        for k, (w, t) in enumerate(words_ptr):
            d.extend(struct.pack('<I', PH if t is not None else w))
        for k, (w, t) in enumerate(words_ptr):
            if t is not None: r.internal.append((a + 4 * k, t))
        return a

    # members: new array = old entries + 2
    mt, mn, _ = pc.arr['members']
    tmpl = next(m for m in pc.members() if m[5] == 64 and m[4] == 219 and pc.init_string(m[0]))
    pad(); d.extend(struct.pack('<I', mn + 2)); nmt = len(d)
    d.extend(s.data[mt:mt + MEMBER_ENTRY * mn]); dup(mt, mt + MEMBER_ENTRY * mn, nmt - mt)
    newm = []
    for xo in TU_NEW_MEMBERS:
        v = new_off[xo]; a = len(d)
        d.extend(s.data[tmpl[0]:tmpl[0] + MEMBER_ENTRY]); newm.append(a)
        struct.pack_into('<HH', d, a + 12, v['pc'], v['name'])
        getattr(r, idkind(tmpl[0] + 8)).append((8, a + 8))
        put(a + 16, PH)
    for a, xo in zip(newm, TU_NEW_MEMBERS):
        v = new_off[xo]
        txt = string(v['init'][1])
        # init = [-> node][node: word0, -> name, 0] as in the TU and every PC messagechannel init
        pad(); root = len(d); d.extend(struct.pack('<IIII', PH, v['init'][0], PH, 0))
        r.internal += [(root, root + 4), (root + 8, txt), (a + 16, root)]
    retarget(0x2c, nmt)
    struct.pack_into('<H', d, 0x1c, new_size)
    L('members: %d -> %d (new array +0x%x), instance size %d -> %d' % (mn, mn + 2, nmt, size, new_size))
    # start-function-info: the 2 new objects first (highest offset first, as the TU and PC lists are ordered)
    st_t, st_n, _ = pc.arr['sfi']
    stmpl = next(st_t + 8 * k for k in range(st_n) if pc.u32(st_t + 8 * k) == 64)
    pad(); d.extend(struct.pack('<I', st_n + 2)); nst = len(d)
    for xo in reversed(TU_NEW_MEMBERS):
        a = len(d); d.extend(struct.pack('<II', 64, new_off[xo]['pc'])); getattr(r, idkind(stmpl)).append((8, a))
    d.extend(s.data[st_t:st_t + 8 * st_n]); dup(st_t, st_t + 8 * st_n, nst + 16 - st_t)
    retarget(0x30, nst)
    L('sfi: %d -> %d (new array +0x%x): (64, %d), (64, %d) first' % (st_n, st_n + 2, nst, new_off[3284]['pc'], new_off[3264]['pc']))
    # locals of PC f8 / f43
    ltmpl = next(a for a, off, nm, tag in pc.locals(8) if tag == 0x34 and a + 16 in pc.it)
    for st in SITES:
        lm = lmaps.get(st['key'])
        if not lm: continue
        k = st['pc_func']; f = pc.func(k)
        old = pc.locals(k); lt = old[0][0]; n = len(old)
        pad(); d.extend(struct.pack('<I', n + len(lm))); nlt = len(d)
        d.extend(s.data[lt:lt + LOCAL_ENTRY * n]); dup(lt, lt + LOCAL_ENTRY * n, nlt - lt)
        for xo, v in sorted(lm.items(), key=lambda q: q[1]['pc']):
            a = len(d); d.extend(s.data[ltmpl:ltmpl + LOCAL_ENTRY])
            struct.pack_into('<HH', d, a + 12, v['pc'], v['name'])
            v['entry'] = a
        for xo, v in lm.items():
            ib = init_block([(0, None)] * 4)             # string local init = 16 zero bytes (as every PC string local)
            r.internal.append((v['entry'] + 16, ib))
        retarget(f + 12, nlt)
        fsz, fstack = pc.frame(k); tsz, tstack = tu.frame(st['tu_func'])
        struct.pack_into('<H', d, f + 6, fsz + 4 * len(lm)); struct.pack_into('<H', d, f + 10, max(fstack, tstack))
        L('PC f%d: locals %d -> %d (new array +0x%x), frame %d -> %d, stackSize %d -> %d (TU %d)' % (
            k, n, n + len(lm), nlt, fsz, fsz + 4 * len(lm), fstack, max(fstack, tstack), tstack))

    # code blocks
    blocks = {}
    for st in SITES:
        code = []                               # (word, reloc): ('ext', si, off) / ('str', text) / ('jmp', target)
        lm = {xo: v['pc'] for xo, v in lmaps.get(st['key'], {}).items()}
        lo, hi = st['tu']
        for o_, opc, w, ex in tu.instrs(lo, hi):
            if opc == 0x00: code.append((op(0, st['marker']), None))
            elif opc in (0x08, 0x09, 0x0a): code.append((op(opc, lm[w & 0xffffff]), None))
            elif opc in (0x0f, 0x0c, 0x10): code.append((op(opc, mm[w & 0xffffff]), None))
            elif opc in (0x03, 0x04, 0x4f): code.append((w, None))
            elif opc == 0x05:
                code.append((w, None)); code.append((PH, ('str', P.cstr(tu.d, tu.it[ex[0]]))))
            elif opc in (0x65, 0x66):
                psid, poff, txt = ext_map(ex[0]); L('%s +0x%x: %s' % (st['key'], o_, txt))
                code.append((w, None)); code.append((PH, ('ext', idx[(8, psid)], poff)))
            elif opc == 0x64:
                t = o_ + 4 + 4 * sarg(w)
                if not lo < t <= hi: sys.exit('%s: TU op64 at +0x%x leaves the block' % (st['key'], o_))
                code.append((w, None))
            elif opc == 0x63:
                t = o_ + 4 + 4 * sarg(w)
                if t != st['tu_else'][1]: sys.exit('%s: TU op63 at +0x%x does not skip the else block' % (st['key'], o_))
                code.append((None, ('jmp', st['back'])))
            else:
                sys.exit('%s: TU opcode %02x at +0x%x not handled' % (st['key'], opc, o_))
        if 'back_else' in st:
            code.append((op(0, st['marker']), None)); code.append((None, ('jmp', st['back_else'])))
        else:
            if keep_popup and st['key'] == 'paused':
                code.append((None, ('jmp', 0x4020)))
            else:
                code.append((None, ('jmp', st['back'])))
        pad(); a0 = len(d)
        for k, (w, rel) in enumerate(code):
            at = a0 + 4 * k
            if rel and rel[0] == 'jmp': w = op(0x63, (rel[1] - (at + 4)) // 4)
            d.extend(struct.pack('<I', w))
        for k, (w, rel) in enumerate(code):
            at = a0 + 4 * k
            if rel and rel[0] == 'ext': r.external.append((rel[1], at, rel[2]))
            elif rel and rel[0] == 'str': r.internal.append((at, string(rel[1])))
        put(st['site'], op(0x63, (a0 - (st['site'] + 4)) // 4))
        blocks[st['key']] = (a0, len(code))
        L('%s: block +0x%x (%d words) from TU +0x%x..+0x%x; site +0x%x op00 %d -> op63; %s' % (
            st['key'], a0, len(code), lo, hi, st['site'], st['marker'], st['note']))

    before = len(s.data); s.data = bytes(d); s.reloc = R.write(r, 'le')
    raw = D.write('le'); C = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in C.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in C.sections)
    if bad: sys.exit('%d sections with relocations out of bounds - %s NOT written' % (bad, out))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    L('script 7: section %d -> %d bytes; relocations out of bounds: 0 -> %s' % (before, len(d), out))

    # ---- verify: re-read OUT, decode the blocks again against the TU -------------------------------------------
    O = DW.read(open(out, 'rb').read(), 'le')
    I = DW.read(raw_in, 'le')
    diff = [(x.type, x.id) for x, y in zip(O.sections, I.sections) if (x.type, x.id) != (y.type, y.id) or x.data != y.data or x.reloc != y.reloc]
    if len(O.sections) != len(I.sections) or diff != [(8, SID)]:
        sys.exit('VERIFY: sections that differ from IN: %s (expected only script 7)' % diff)
    OS = [(x.type, x.id, x.data, x.reloc) for x in O.sections]
    o7 = next(x for x in O.sections if x.type == 8 and x.id == SID)
    v = Script(o7.data, o7.reloc, 'le', OS)
    probs = []
    if v.u16(0x1c) != new_size: probs.append('instance size')
    for xo, nv in new_off.items():
        m = v.member_at(nv['pc'])
        if not m or m[2] != nv['name'] or m[5] != 64 or v.init_string(m[0]) != nv['init']: probs.append('member %d' % nv['pc'])
    sf = v.arr['sfi']
    if sf[1] != st_n + 2 or [(v.u32(sf[0] + 8 * k), v.u32(sf[0] + 8 * k + 4)) for k in range(2)] != [(64, new_off[3284]['pc']), (64, new_off[3264]['pc'])]:
        probs.append('sfi')
    nchk = 0
    for st in SITES:
        a0, n = blocks[st['key']]
        if v.u32(st['site']) >> 24 != 0x63 or st['site'] + 4 + 4 * sarg(v.u32(st['site'])) != a0: probs.append('%s site' % st['key'])
        lmv = {}
        if st['key'] in lmaps:
            loc = {off: (nm, tag) for _, off, nm, tag in v.locals(st['pc_func'])}
            for xo, lv in lmaps[st['key']].items():
                if loc.get(lv['pc']) != (lv['name'], 0x34): probs.append('%s local %d' % (st['key'], lv['pc']))
                lmv[lv['pc']] = xo
        tw = list(tu.instrs(*st['tu'])); pw = list(v.instrs(a0, a0 + 4 * sum(1 + len(e) for _, _, _, e in tw)))
        for (xo_, xop, xw, xex), (po_, pop, pw_, pex) in zip(tw, pw):
            ok = xop == pop
            if ok and xop in (0x03, 0x04, 0x4f, 0x64): ok = xw == pw_
            if ok and xop == 0x05: ok = P.cstr(tu.d, tu.it[xex[0]]) == P.cstr(v.d, v.it[pex[0]])
            if ok and xop in (0x65, 0x66):
                xt_, xs_, xf_ = tu.target(xex[0]); pt_, ps_, pf_ = v.target(pex[0])
                ok = xnames[xs_] == pnames[ps_] and ids.sym(xfuncs[xs_][xf_][1]) == pfuncs[ps_][pf_][1]
            if ok and xop in (0x0f, 0x0c, 0x10):
                xm = tu.member_at(xw & 0xffffff); pm = v.member_at(pw_ & 0xffffff)
                ok = pm is not None and xm[5] == pm[5] and (xm[5] != 64 or tu.init_string(xm[0]) == v.init_string(pm[0]))
            if ok and xop in (0x08, 0x09, 0x0a): ok = lmv.get(pw_ & 0xffffff) == (xw & 0xffffff)
            if ok and xop == 0x63: ok = po_ + 4 + 4 * sarg(pw_) == st['back']
            if not ok: probs.append('%s: TU +0x%x %08x / PC +0x%x %08x' % (st['key'], xo_, xw, po_, pw_))
            nchk += 1
        tail = a0 + 4 * sum(1 + len(e) for _, _, _, e in tw)
        if 'back_else' in st:
            if v.u32(tail + 4) >> 24 != 0x63 or tail + 8 + 4 * sarg(v.u32(tail + 4)) != st['back_else']: probs.append('%s else jump' % st['key'])
        else:
            want = 0x4020 if (keep_popup and st['key'] == 'paused') else st['back']
            if v.u32(tail) >> 24 != 0x63 or tail + 4 + 4 * sarg(v.u32(tail)) != want: probs.append('%s back jump' % st['key'])
    L('VERIFY: %d sections, only script 7 differs; %d translated instructions re-decoded against the TU, problems: %s' % (
        len(O.sections), nchk, probs or 'none'))
    print('\n'.join(log))
    if probs: sys.exit('VERIFY FAILED - remove %s' % out)


if __name__ == '__main__':
    main(sys.argv[1:])
