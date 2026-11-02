"""Classify every retail <-> title-update (TU) function pair of the Xbox 360 exe by an instruction-level diff, tag its
area, and check whether the PC tru.exe looks like retail or like the TU (read-only; 2026-11-02,
docs/Plan-TU-Funktionsvergleich.md sections 2.2-2.4).

Input: OUT_DIR/pairs.tsv from tools/tu_func_pair.py, the two Xenia images, the Steam tru.exe and the Xbox retail ->
PC map work/xmap/xbox_pc_map.tsv (tools/xbox_pc_funcmap.py).

Per instruction three tokens (address halves of lis/addi/ori/load/store address pairs and branch offsets always
masked; built addresses become their meaning: string text, float value, mapped function, or "data"; bl targets
become the paired retail function):
  L0 the word itself (registers, immediates, stack offsets kept)
  L1 registers and stack (r1) offsets masked, immediates / field displacements / rotate masks kept
  L2 opcode skeleton only (immediates, displacements, float / string values masked; calls and function pointers kept)
Classes of a pair:
  relink   L0 equal (only address / branch noise)
  regalloc L1 equal (register numbers / stack offsets differ)
  field    L2 equal, every other difference is a structure-field displacement (data layout moved, logic the same)
  const    L2 equal, immediates / float / string constants differ (listed old -> new)
  inline   a 'code' pair whose dropped calls all went to small retail helpers (<= INLINE_MAX bytes or leaf code
           without .pdata, e.g. the unoptimised accessors 0x82168xxx, register save / restore entries) and whose
           added calls are only calls those helpers made: the TU build inlined them (compiler noise)
  code     L2 differ, opcode similarity >= 0.5: inserted / removed / replaced instructions counted, new callees listed
           ('consts' column 'callee a->b' when only call targets differ)
  rewrite  L2 similarity < 0.5
  tu-only / retail-only from the pairing.
Call targets without .pdata are mapped by the b / bl sites of hash-equal pairs, else by the nearest paired function
(same offset, 8 opcode skeletons equal). Hash-equal pairs whose constants were permuted between look-alike functions
are re-paired when another pair gives L1-identical bodies ('swap').
Area: own strings (keyword table AREAS), known ranges (TU player code 0x823dca00..0x823e1220, the TU meter / shadow
block 0x823d7000..0x823da000, Lara's state / condition / activity tables), else the majority area of the tagged
callers + callees (marked '~'). dlc: the function reads gameTracker+0x1244 through the game-tracker pointer
(0x829892b0 TU) = 'gt', or any load with displacement 0x1244 = 'disp'; meter: the same for +0x508.
PC side (code / const / rewrite with a PC partner of the retail function): callees added by the TU whose PC partner
the PC function calls (-> tu) or does not call (-> retail), callees removed by the TU likewise, changed float /
integer / string constants found in the PC function (old -> retail, new -> tu). pc_like = the side with more votes,
else unknown.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/tu_func_classify.py RETAIL.bin TU.bin TRU_EXE OUT_DIR [--pcmap work/xmap/xbox_pc_map.tsv]
       [--show TU_ADDR]     (debug: print the differing tokens of one pair, no output files)
Output: OUT_DIR/classes.tsv, OUT_DIR/summary.txt, OUT_DIR/main_game.tsv (real changes without dlc / meter flag, not
live), OUT_DIR/const_changes.txt (old -> new per const / field pair),
OUT_DIR/pc_cache.pkl (derived PC function table, rebuilt when the exe is newer). Addresses, classes, counts, string
names and constant values only - no game bytes.
"""
import sys, os, struct, difflib, bisect, collections, pickle, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P
import xbox_pc_funcmap as FM
import tu_func_pair as TP
import tu_dlc_mode_users as DM

BASE = 0x82000000
GT = {'tu': 0x829892b0, 'retail': 0x82988f30}
LS = set(range(32, 56))
ARITH = {3, 7, 8, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29}
SPR_XO = {339, 467, 371, 824, 19, 144, 597, 725}
INLINE_MAX = 160                 # bytes: a retail callee this small that the TU stopped calling counts as inlined
# op 31 forms that write no GPR (stores, compares, cache / sync, traps, mtspr / mtcrf)
X31_NOWRITE = {0, 32, 4, 68, 151, 183, 215, 247, 407, 439, 663, 695, 727, 759, 983, 231, 487, 135, 167, 199, 918,
               662, 150, 214, 278, 54, 86, 246, 1014, 470, 598, 854, 467, 144, 149, 181}
# op 31 forms that write rA (logical, shifts, sign extension, count leading zeros)
X31_WRITES_RA = {28, 60, 124, 284, 316, 412, 444, 476, 24, 536, 792, 824, 954, 922, 26, 58, 986, 27, 539, 794, 413}
# area keywords (lower case, matched as substrings of the function's strings); first match wins per string
AREAS = [
    ('live', ['achievement', 'xcontent', 'content package', 'signin', 'sign in', 'signed', 'profile', 'xlive',
              'xbox live', 'marketplace', 'gamer', 'leaderboard', 'presence', 'xam', 'savegame', 'save game',
              'storage', 'device', 'xuser', 'offer', 'license', 'dlc', 'download', 'xmp', 'friend', 'session',
              'xnet', 'xonline', 'guide', 'trial', 'unlock']),
    ('camera', ['camera', 'cam_', 'cam ']),
    ('ai', ['ai_', ' ai ', 'enemy', 'navmesh', 'nav ', 'path', 'combat', 'attack', 'target', 'squad', 'npc',
            'monster', 'creature', 'thrall', 'spider', 'tiger', 'shark']),
    ('sound', ['sound', 'music', 'audio', 'fmod', 'snd', 'voice', 'dialog', '.mul', 'sfx', 'reverb', 'volume']),
    ('ui', ['menu', 'hud', 'font', 'button', 'screen', 'text', 'pda', 'subtitle', 'locali', 'language', 'ui_',
            'option', 'pause', 'title', 'credits', 'loading']),
    ('render', ['shader', 'texture', 'render', 'draw', 'vertex', 'mesh', 'light', 'shadow', 'material', 'd3d',
                'surface', 'gpu', 'tiling', 'resolve', 'bloom', 'fx', 'particle', 'effect', 'fog', 'sky', 'water',
                'decal', 'terrain', 'occlu', 'lod', 'glow', 'depth', 'blur']),
    ('player', ['lara', 'player', 'doppel', 'costume', 'grapple', 'weapon', 'ledge', 'climb', 'swim', 'jump',
                'pickup', 'inventory', 'health', 'adrenal', 'sonar', 'shadow']),
    ('script', ['script', 'native', 'event', 'statechart', 'chart', 'trigger', 'cine', 'intro', 'object',
                'instance', 'unit', 'level', 'streaming', 'stream', 'drm', 'bigfile', 'load', 'file', 'memory',
                'heap', 'alloc', 'thread', 'debug', 'assert', 'error', 'warning']),
    ('physics', ['physic', 'collision', 'collide', 'havok', 'rigid', 'ragdoll', 'cloth', 'rope', 'phys']),
    ('anim', ['anim', 'pose', 'bone', 'skeleton', 'blend', 'segment']),
]
AREA_ORDER = ['live', 'player', 'camera', 'ai', 'sound', 'ui', 'render', 'physics', 'anim', 'script', 'other']


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


class Img:
    def __init__(self, path, side):
        self.side = side
        self.X = FM.Xbox(path)
        self.d = self.X.d
        self.starts = self.X.starts
        self.sset = set(self.starts)
        self.size = self.X.size
        self.gt = GT[side]
        lo = min(s[1] for s in self.X.secs)
        hi = max(s[1] + s[2] for s in self.X.secs)
        self.range = (lo, hi)

    def word(self, a):
        o = a - BASE
        return struct.unpack_from('>I', self.d, o)[0] if 0 <= o <= len(self.d) - 4 else None

    def meaning(self, v, op, fmap):
        """what a built address stands for"""
        X = self.X
        if v in self.sset:
            return ('P', fmap(v))
        o = v - BASE
        if X.rdata[0] <= v < X.rdata[1]:           # constants only: .data holds run-time values in a memory dump
            if op in (48, 49) and 0 <= o <= len(self.d) - 4:
                f = struct.unpack_from('>f', self.d, o)[0]
                return ('F', '%.7g' % f)
            if op in (50, 51) and 0 <= o <= len(self.d) - 8:
                return ('F', '%.12g' % struct.unpack_from('>d', self.d, o)[0])
            s = FM.cstr(self.d, o)
            if s and op == 14:
                return ('S', s)
        return ('G',)


def analyse(img, fs, fmap):
    """per instruction (l0, l1, l2, detail); plus flags {'dlc': gt|disp, 'meter': gt|disp}"""
    fe = fs + img.size[fs]
    ws = TP.words(img.d, fs, fe)
    regs, gtr = {}, set()
    toks, flags = [], {}
    for i, w in enumerate(ws):
        a = fs + 4 * i
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
        simm = s16(imm)
        # address constants
        if op == 15 and ra == 0 and 0x8200 <= imm <= 0x8340:
            regs[rd] = (imm << 16) & 0xffffffff
            gtr.discard(rd)
            toks.append((('H', w & 0xffff0000), ('H',), ('H',), None))
            continue
        base = None
        if op == 24 and rd in regs:
            base, v, dst = regs[rd], regs[rd] | imm, ra
        elif ra in regs and (op == 14 or op in LS or op in (58, 62)) and ra != 0:
            base, v, dst = regs[ra], (regs[ra] + (simm if op not in (58, 62) else s16(imm & 0xfffc))) & 0xffffffff, rd
        if base is not None:
            k = img.meaning(v, op, fmap)
            if op == 32 and v == img.gt:
                gtr.add(rd)
            elif op in (14, 24) or op in (32, 33, 34, 35, 40, 41, 42, 43, 48, 49, 50, 51, 58):
                gtr.discard(dst)
            if op in (14, 24):
                regs.pop(dst, None) if dst != ra or op == 24 else regs.pop(ra, None)
            elif op in (32, 33, 34, 35, 40, 41, 42, 43, 58):
                regs.pop(rd, None)
            toks.append((('A', w & 0xffff0000, k), ('A', op, k), ('A', op, k if k[0] == 'P' else k[0]),
                         ('val', k) if k[0] in 'SF' else None))
            continue
        # game tracker flags (+0x1244 doppelganger mode, +0x508 meter)
        if op in (32, 34, 40):
            for disp, name in ((0x1244, 'dlc'), (0x508, 'meter')):
                if simm == disp:
                    if ra in gtr:
                        flags[name] = 'gt'
                    else:
                        flags.setdefault(name, 'disp')
        if op == 31 and ((w >> 1) & 0x3ff) == 444 and rd == ((w >> 11) & 31):     # mr ra, rs
            if rd in gtr:
                gtr.add(ra)
            else:
                gtr.discard(ra)
            regs.pop(ra, None)
            toks.append((w, (31, 444), TP.skel(w), None))
            continue
        # register invalidation (rough, as tools/ppc_xrefs.py)
        if op == 31:
            xo = (w >> 1) & 0x3ff
            tgt = None if xo in X31_NOWRITE else ra if xo in X31_WRITES_RA else rd
            if tgt is not None:
                regs.pop(tgt, None); gtr.discard(tgt)
        elif op in (14, 15, 7, 8, 12, 13, 32, 33, 34, 35, 40, 41, 42, 43, 58) or op in (21, 20, 23, 24, 25, 28, 29, 30):
            tgt = ra if op in (20, 21, 23, 24, 25, 28, 29, 30) else rd
            regs.pop(tgt, None); gtr.discard(tgt)
        if op == 18:
            li = w & 0x03fffffc
            if li & 0x02000000:
                li -= 0x04000000
            t = (a + li) & 0xffffffff
            if (w & 1) or not (fs <= t < fe):
                c = ('C', fmap(t))
                toks.append((c, c, c, ('call', c[1])))
                if w & 1:                                  # a call clobbers r0, r3..r12
                    for q in [0] + list(range(3, 13)):
                        regs.pop(q, None); gtr.discard(q)
            else:
                toks.append((('b', w & 3), ('b',), ('b',), None))
            continue
        if op == 16:
            toks.append((('bc', (w >> 16) & 0x3ff, w & 3), ('bc', rd, ra & 3, w & 3), ('bc',), None))
            continue
        sk = TP.skel(w)
        if op in LS or op in (58, 62):
            disp = s16(imm & 0xfffc) if op in (58, 62) else simm
            if ra == 1:
                toks.append((w, (op, 'stk', w & 3 if op in (58, 62) else 0), sk, None))
            else:
                toks.append((w, (op, disp, w & 3 if op in (58, 62) else 0), sk, ('disp', disp)))
            continue
        if op in ARITH:
            if op == 14 and ra == 1:
                toks.append((w, (op, 'stk'), sk, None))
            else:
                v = imm if op in (24, 25, 26, 27, 28, 29, 10) else simm
                z = (ra == 0) if op in (14, 15) else None
                # addi rD, rA, d with a pointer in rA = the address of a field: a layout offset like a displacement
                kind = 'disp' if op == 14 and ra != 0 else 'imm'
                toks.append((w, (op, v, z), (sk, z), (kind, v)))
            continue
        if op in (20, 21):
            toks.append((w, (op, w & 0xffff), sk, ('rot', w & 0xffff)))
            continue
        if op == 23:
            toks.append((w, (op, w & 0x7ff), sk, ('rot', w & 0x7ff)))
            continue
        if op == 30:
            toks.append((w, (op, w & 0xfffe & ~0x0), sk, ('rot', w & 0xffff)))
            continue
        if op == 31:
            xo = (w >> 1) & 0x3ff
            if xo in SPR_XO:
                toks.append((w, (op, xo, (w >> 11) & 0x3ff), sk, ('spr', (w >> 11) & 0x3ff)))
            else:
                toks.append((w, w & 0xfc0007ff, sk, None))
            continue
        if op in (19, 59, 63):
            toks.append((w, sk, sk, None))
            continue
        if op in (4, 5, 6):
            toks.append((w, sk, sk, None))
            continue
        toks.append((w, w & 0xfc00ffff, sk, None))
    return toks, flags


def fmt_val(x):
    if isinstance(x, tuple):
        if x[0] == 'S':
            return '"%s"' % x[1][:40]
        if x[0] == 'F':
            return x[1] + 'f'
        return str(x)
    if isinstance(x, int):
        return ('0x%x' % x) if abs(x) >= 10 else str(x)
    return str(x)


def classify(rt, tt):
    """class, similarity, changed instruction count, const diffs [(kind, old, new)], new callees, removed callees"""
    r0 = [t[0] for t in rt]; t0 = [t[0] for t in tt]
    rc = set(t[0][1] for t in rt if isinstance(t[0], tuple) and t[0][0] == 'C')
    tc = set(t[0][1] for t in tt if isinstance(t[0], tuple) and t[0][0] == 'C')
    addc, remc = tc - rc, rc - tc
    if r0 == t0:
        return 'relink', 1.0, 0, [], addc, remc
    r1 = [t[1] for t in rt]; t1 = [t[1] for t in tt]
    if r1 == t1:
        return 'regalloc', 1.0, 0, [], addc, remc
    r2 = [t[2] for t in rt]; t2 = [t[2] for t in tt]
    if r2 == t2:
        diffs = []
        for a, b in zip(rt, tt):
            if a[1] != b[1] and a[3] and b[3] and a[3][0] == b[3][0]:
                diffs.append((a[3][0], a[3][1], b[3][1]))
            elif a[1] != b[1]:
                diffs.append(('reg', '', ''))
        real = [x for x in diffs if x[0] != 'reg']
        if real and all(x[0] == 'disp' for x in real):
            return 'field', 1.0, len(real), real, addc, remc
        if real:
            return 'const', 1.0, len(real), real, addc, remc
        return 'regalloc', 1.0, 0, [], addc, remc
    sm = difflib.SequenceMatcher(None, r2, t2, autojunk=False)
    sim = sm.ratio()
    n = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal':
            n += max(i2 - i1, j2 - j1)
    diffs = []
    if len(r2) == len(t2):                         # only call targets / function pointers differ: 'callee' diffs
        dd = [(a, b) for a, b in zip(r2, t2) if a != b]
        ok = lambda z: isinstance(z, tuple) and (z[0] == 'C' or (z[0] == 'A' and isinstance(z[2], tuple)))
        if all(ok(a) and ok(b) and b[0] == a[0] for a, b in dd):
            diffs = [('callee', a[-1] if a[0] == 'C' else a[2][1], b[-1] if b[0] == 'C' else b[2][1]) for a, b in dd]
    return ('rewrite' if sim < 0.5 else 'code'), sim, n, diffs, addc, remc


# ---------------------------------------------------------------- PC side
def pc_load(exe, cache):
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(exe):
        return pickle.load(open(cache, 'rb'))
    Pc = FM.PC(exe)
    Pc.build()
    keep = dict(base=Pc.base, secs=Pc.secs, starts=Pc.starts, size=Pc.size, calls=Pc.calls, strs=Pc.strs)
    pickle.dump(keep, open(cache, 'wb'))
    return keep


class PCInfo:
    def __init__(self, exe, cache):
        self.k = pc_load(exe, cache)
        self.d = open(exe, 'rb').read()
        self.secs = self.k['secs']
        self.rd = self.secs.get('.rdata')

    def read(self, va, n):
        for va0, vs, raw, rs in self.secs.values():
            if va0 <= va < va0 + min(vs, rs) - n + 1:
                return self.d[raw + va - va0: raw + va - va0 + n]
        return None

    def body(self, f):
        return self.read(f, min(self.k['size'].get(f, 0), 0x4000)) or b''

    def consts(self, f):
        """floats (inline and referenced .rdata), dwords, of a PC function"""
        b = self.body(f)
        fl, dw = set(), set()
        for i in range(len(b) - 3):
            v = struct.unpack_from('<I', b, i)[0]
            dw.add(v)
            x = struct.unpack_from('<f', b, i)[0]
            if math.isfinite(x):
                fl.add('%.7g' % x)
            if self.rd and self.rd[0] <= v < self.rd[0] + self.rd[1]:
                r = self.read(v, 8)
                if r:
                    fl.add('%.7g' % struct.unpack('<f', r[:4])[0])
                    fl.add('%.12g' % struct.unpack('<d', r)[0])
        return fl, dw


def pc_like(pc, pcf, pcmap, addc, remc, diffs, rpair):
    """votes tu / retail from callees and constants"""
    tu = rt = 0.0
    ev = []
    calls = set(pc.k['calls'].get(pcf, []))
    for c in addc:
        if isinstance(c, int) and c in pcmap:
            if pcmap[c][0] in calls:
                tu += 1; ev.append('+call yes')
            else:
                rt += 0.5; ev.append('+call no')
    for c in remc:
        if isinstance(c, int) and c in pcmap:
            if pcmap[c][0] in calls:
                rt += 1; ev.append('-call yes')
            else:
                tu += 0.5; ev.append('-call no')
    if diffs:
        fl, dw = pc.consts(pcf)
        strs = pc.k['strs'].get(pcf, set())
        for kind, old, new in diffs:
            if kind == 'val' and old[0] == 'F' and new[0] == 'F':
                o, n = old[1] in fl, new[1] in fl
            elif kind == 'val' and old[0] == 'S' and new[0] == 'S':
                o, n = old[1] in strs, new[1] in strs
            elif kind == 'imm' and isinstance(old, int) and isinstance(new, int) and min(abs(old), abs(new)) >= 0x80:
                o, n = (old & 0xffffffff) in dw, (new & 0xffffffff) in dw
            else:
                continue
            if o and not n:
                rt += 1; ev.append('%s old' % kind)
            elif n and not o:
                tu += 1; ev.append('%s new' % kind)
    like = 'tu' if tu > rt else 'retail' if rt > tu else 'unknown'
    return like, ' '.join(ev[:6])


# ---------------------------------------------------------------- areas
def own_area(strs):
    hits = collections.Counter()
    for s in strs:
        ls = s.lower()
        for name, keys in AREAS:
            if any(k in ls for k in keys):
                hits[name] += 1
                break
    if not hits:
        return None
    for a in AREA_ORDER:          # ties: the more specific area first
        if hits[a] == max(hits.values()):
            return a


def lara_table_funcs(d):
    out = set()
    for r in [r for t in DM.STATES for r in DM.table(d, t, 7)]:
        out |= set(f for f in r[1:] if f)
    for t in DM.CONDS:
        out |= set(r[2] for r in DM.table(d, t, 3))
    for t in DM.ACTS:
        out |= set(r[1] for r in DM.table(d, t, 2))
    return out


def areas_for(T, lara, ranges):
    area, src = {}, {}
    for f in T.starts:
        a = None
        if ranges and (0x823dca00 <= f < 0x823e1220 or 0x823d7000 <= f < 0x823da000) or f in lara:
            a, s = 'player', 'range'
        else:
            a, s = own_area(T.X.strs.get(f, ())), 'strings'
        if a:
            area[f], src[f] = a, s
    for rnd in range(8):
        add = {}
        for f in T.starts:
            if f in area:
                continue
            # callers count double: a helper belongs to the code that uses it more than to what it calls
            c = collections.Counter()
            for g in T.X.callers.get(f, ()):
                if g in area:
                    c[area[g]] += 2
            for g in T.X.calls.get(f, []):
                if g in area:
                    c[area[g]] += 1
            if c:
                best = c.most_common(2)
                if len(best) == 1 or best[0][1] > best[1][1]:
                    add[f] = best[0][0]
        for f, a in add.items():
            area[f], src[f] = a, 'graph'
        if not add:
            break
    return area, src


def main(argv):
    pcmap_path, show = 'work/xmap/xbox_pc_map.tsv', None
    if '--show' in argv:
        k = argv.index('--show'); show = int(argv[k + 1], 16); del argv[k:k + 2]
    if '--pcmap' in argv:
        k = argv.index('--pcmap'); pcmap_path = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 4:
        sys.exit(__doc__)
    retail, tu, exe, out = argv
    log = []
    say = lambda s: (print(s, flush=True), log.append(s))
    rows = TP.read_pairs(os.path.join(out, 'pairs.tsv'))
    R, T = Img(retail, 'retail'), Img(tu, 'tu')
    t2r = dict((r['tu'], r['retail']) for r in rows if r['tu'] is not None and r['retail'] is not None)
    # call targets without a .pdata entry (library code such as memset): map them by the bl sites of the
    # hash-equal pairs (same instruction index on both sides), majority vote
    votes = collections.defaultdict(collections.Counter)
    for r in rows:
        if r['status'] == 'moved-equal' and r['tu'] is not None and r['retail'] is not None:
            wr = TP.words(R.d, r['retail'], r['retail'] + R.size[r['retail']])
            wt = TP.words(T.d, r['tu'], r['tu'] + T.size[r['tu']])
            for i, (a, b) in enumerate(zip(wr, wt)):
                if a >> 26 == 18 and b >> 26 == 18 and (a & 3) == (b & 3):     # bl, and b out of the function
                    la, lb = a & 0x03fffffc, b & 0x03fffffc
                    la -= 0x04000000 if la & 0x02000000 else 0
                    lb -= 0x04000000 if lb & 0x02000000 else 0
                    ta, tb = (r['retail'] + 4 * i + la) & 0xffffffff, (r['tu'] + 4 * i + lb) & 0xffffffff
                    if tb not in t2r:
                        votes[tb][ta] += 1
    extra = dict((tb, c.most_common(1)[0][0]) for tb, c in votes.items())
    say("call targets without .pdata (library code, register save / restore entries) mapped by b / bl sites of hash-equal pairs: %d" % len(extra))
    t2r.update(extra)
    fmap_r = lambda a: a
    tstarts = sorted(s for s in t2r if s in T.sset)

    def fmap_t(a):
        """TU target -> retail; targets without .pdata (leaf code) through the nearest paired TU function before /
        after them (same offset), accepted when 8 opcode skeletons agree (as tools/tu_to_retail.py)"""
        if a in t2r:
            return t2r[a]
        i = bisect.bisect_right(tstarts, a) - 1
        for j in (i, i + 1):
            if 0 <= j < len(tstarts):
                c = a - tstarts[j] + t2r[tstarts[j]]
                sa = [TP.skel(w) for w in TP.words(T.d, a, a + 32)]
                sc = [TP.skel(w) for w in TP.words(R.d, c, c + 32)]
                if sa == sc and (a not in T.sset) == (c not in R.sset):
                    t2r[a] = c
                    return c
        t2r[a] = 'tu:0x%08x' % a
        return t2r[a]
    if show is not None:                           # debug: the differing L1 / L2 tokens of one pair
        x = t2r[show]
        rt, _f = analyse(R, x, fmap_r)
        tt, fl = analyse(T, show, fmap_t)
        print('TU 0x%08x retail 0x%08x: %s, flags %s' % (show, x, classify(rt, tt)[:3], fl))
        sm = difflib.SequenceMatcher(None, [t[2] for t in rt], [t[2] for t in tt], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                print('  %s retail +0x%x..+0x%x  TU +0x%x..+0x%x' % (tag, 4 * i1, 4 * i2, 4 * j1, 4 * j2))
                for i in range(i1, min(i2, i1 + 4)):
                    print('     r %s %s' % (rt[i][2], rt[i][3]))
                for j in range(j1, min(j2, j1 + 4)):
                    print('     t %s %s' % (tt[j][2], tt[j][3]))
            else:
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    if rt[i][1] != tt[j][1]:
                        print('  L1 +0x%x / +0x%x: %s -> %s' % (4 * i, 4 * j, rt[i][3], tt[j][3]))
        return
    pcmap = {}
    with open(pcmap_path, encoding='utf-8') as f:
        f.readline()
        for line in f:
            v = line.rstrip('\n').split('\t')
            pcmap[int(v[0], 16)] = (int(v[1], 16), v[8], v[2], v[3])
    say('PC map %s: %d retail functions with a PC partner' % (pcmap_path, len(pcmap)))
    pc = PCInfo(exe, os.path.join(out, 'pc_cache.pkl'))
    say('PC %s: %d derived functions' % (exe, len(pc.k['starts'])))
    lara = lara_table_funcs(T.d)
    area, asrc = areas_for(T, lara, True)
    rarea, _rs = areas_for(R, set(), False)        # retail-only functions: strings + call graph only
    say('areas: %d of %d TU functions tagged (%s)' % (len(area), len(T.starts),
                                                     dict(collections.Counter(asrc.values()))))
    # refinement: equal-hash functions whose constants were permuted (e.g. three getters of different offsets)
    # are paired by position; swap partners when another pair gives L1-identical bodies on both sides
    sig_r, sig_t, cur = {}, {}, {}
    for r in rows:
        t, x = r['tu'], r['retail']
        if t is not None and x is not None and r['status'] == 'moved-equal':
            sig_r[x] = hash(tuple(z[1] for z in analyse(R, x, fmap_r)[0]))
            sig_t[t] = hash(tuple(z[1] for z in analyse(T, t, fmap_t)[0]))
            cur[t] = x
    by_sig = collections.defaultdict(list)
    for t, s in sig_t.items():
        by_sig[s].append(t)
    swaps = 0
    t_of = dict((x, t) for t, x in cur.items())
    for t, x in list(cur.items()):
        if sig_r[x] == sig_t[t]:
            continue
        cand = [u for u in by_sig.get(sig_r[x], []) if u != t and sig_r[cur[u]] != sig_t[u]]
        if len(cand) == 1:
            u = cand[0]
            y = cur[u]                            # (y, u) -> (x, u), (y, t)
            cur[u], cur[t] = x, y
            t_of[x], t_of[y] = u, t
            swaps += 1
    for r in rows:
        if r['tu'] in cur and r['retail'] != cur[r['tu']]:
            r['retail'] = cur[r['tu']]
            r['method'] = 'swap'
            r['retail_size'] = str(R.size[r['retail']])
    t2r.update(cur)
    say('equal-hash pairs re-paired by identical L1 bodies (permuted constants): %d swaps' % swaps)

    out_rows = []
    constf = open(os.path.join(out, 'const_changes.txt'), 'w', encoding='utf-8', newline='\n')
    for r in rows:
        t, x = r['tu'], r['retail']
        cls, sim, nchg, diffs, addc, remc = r['status'], 0.0, 0, [], set(), set()
        flags = {}
        if t is not None and x is not None:
            rt, _f = analyse(R, x, fmap_r)
            tt, flags = analyse(T, t, fmap_t)
            cls, sim, nchg, diffs, addc, remc = classify(rt, tt)
        elif t is not None:
            _t, flags = analyse(T, t, fmap_t)
        a = area.get(t) if t is not None else rarea.get(x)
        s = asrc.get(t, '') if t is not None else 'retail'
        ar = (a or 'other') if s in ('range', 'strings', '') or a is None else '~' + a
        pcp = pcmap.get(x) if x is not None else None
        like, ev = '', ''
        if pcp and cls in ('code', 'const', 'rewrite'):
            like, ev = pc_like(pc, pcp[0], pcmap, addc, remc, diffs, x)
        if cls == 'code' and remc and all(isinstance(c, int) and R.size.get(c, 0) <= INLINE_MAX for c in remc):
            # every call the TU dropped went to a small retail helper and every added call is one the helpers made:
            # the TU build inlined them (compiler change, e.g. the unoptimised accessors 0x82168xxx)
            inner = set()
            for c in remc:
                inner |= set(R.X.calls.get(c, []))
            if all(isinstance(c, int) and c in inner for c in addc):
                cls = 'inline'
        newc = sorted(('0x%08x' % c) if isinstance(c, int) else c for c in addc)
        cd = ['%s %s->%s' % (k, fmt_val(o), fmt_val(n)) for k, o, n in diffs]
        if cls in ('const', 'field'):
            constf.write('TU 0x%08x retail 0x%08x %s: %s\n' % (t, x, cls, '; '.join(cd)))
        out_rows.append(dict(
            tu=('0x%08x' % t) if t is not None else '', retail=('0x%08x' % x) if x is not None else '',
            pc=('0x%08x' % pcp[0]) if pcp else '', pc_tier=pcp[1] if pcp else '', cls=cls, area=ar,
            tu_size=r['tu_size'], retail_size=r['retail_size'],
            delta=str(int(r['tu_size']) - int(r['retail_size'])) if t is not None and x is not None else '',
            changed=str(nchg), sim='%.2f' % sim if cls in ('code', 'rewrite') else '',
            dlc=flags.get('dlc', ''), meter=flags.get('meter', ''), pc_like=like, pc_evidence=ev,
            new_callees=' '.join(newc[:8]), consts='; '.join(cd[:6]), pair_method=r['method'],
            removed_callees=' '.join(sorted(('0x%08x' % c) if isinstance(c, int) else c for c in remc)[:8]),
            pair_conf=r['confidence'], diff_class=r['diff_class'], retail_class=r['retail_class']))
    constf.close()
    cols = ['tu', 'retail', 'pc', 'pc_tier', 'cls', 'area', 'tu_size', 'retail_size', 'delta', 'changed', 'sim', 'dlc',
            'meter', 'pc_like', 'pc_evidence', 'new_callees', 'removed_callees', 'consts', 'pair_method', 'pair_conf',
            'diff_class',
            'retail_class']
    with open(os.path.join(out, 'classes.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(c if c != 'cls' else 'class' for c in cols) + '\n')
        for o in out_rows:
            f.write('\t'.join(o[c] for c in cols) + '\n')
    # ---------------- summary
    classes = ['relink', 'regalloc', 'field', 'inline', 'const', 'code', 'rewrite', 'tu-only', 'retail-only']
    noise = {'relink', 'regalloc', 'field', 'inline'}
    say('')
    say('class x area (all functions; area "~x" = by call graph, counted with x):')
    tab = collections.Counter()
    for o in out_rows:
        tab[(o['cls'], o['area'].lstrip('~'))] += 1
    say('%-12s' % 'class' + ''.join('%8s' % a for a in AREA_ORDER) + '%8s' % 'total')
    for c in classes:
        say('%-12s' % c + ''.join('%8d' % tab[(c, a)] for a in AREA_ORDER) +
            '%8d' % sum(tab[(c, a)] for a in AREA_ORDER))
    for oc, key in (('changed', 'diff_class'), ('new', 'diff_class'), ('removed', 'retail_class'),
                    ('equal', 'diff_class')):
        sel = [o for o in out_rows if o[key] == oc]
        c = collections.Counter(o['cls'] for o in sel)
        nz = sum(n for k, n in c.items() if k in noise)
        say('xbox_func_diff "%s" (%d): %s - noise %d, real %d' % (oc, len(sel), dict(sorted(c.items())), nz,
                                                                   len(sel) - nz))
    real = [o for o in out_rows if o['cls'] in ('const', 'code', 'rewrite')]
    say('')
    co = [o for o in out_rows if o['cls'] == 'code']
    cal = [o for o in co if o['consts'].startswith('callee')]
    unp = [o for o in cal if 'tu:' in o['consts']]
    say('code: %d, of them only call targets differ: %d (%d with a TU callee that has no retail partner; the rest '
        'call a differently paired retail function - pairing doubt or a real retarget)' % (len(co), len(cal), len(unp)))
    dropped = collections.Counter()
    for o in out_rows:
        if o['cls'] in ('code', 'inline', 'rewrite'):
            for c in o['removed_callees'].split():
                dropped[c] += 1
    say('retail callees most often dropped by the TU (code / inline / rewrite pairs): %s' % ', '.join(
        '%s x%d (%d B)' % (c, n, R.size.get(int(c, 16), 0)) for c, n in dropped.most_common(12) if c.startswith('0x')))
    say('real changes (const / code / rewrite pairs): %d; by area: %s' % (
        len(real), dict(collections.Counter(o['area'].lstrip('~') for o in real))))
    say('  with dlc flag (gt / disp): %d / %d; meter: %d' % (
        sum(1 for o in real if o['dlc'] == 'gt'), sum(1 for o in real if o['dlc'] == 'disp'),
        sum(1 for o in real if o['meter'])))
    main_game = [o for o in real if not o['dlc'] and not o['meter'] and o['area'].lstrip('~') != 'live']
    with open(os.path.join(out, 'main_game.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(c if c != 'cls' else 'class' for c in cols) + '\n')
        for o in sorted(main_game, key=lambda o: (o['pc'] == '', o['tu'])):
            f.write('\t'.join(o[c] for c in cols) + '\n')
    say('  main-game candidates (no dlc / meter flag, not live): %d; class %s' % (
        len(main_game), dict(collections.Counter(o['cls'] for o in main_game))))
    say('  ... with PC partner: %d; pc_like %s' % (
        sum(1 for o in main_game if o['pc']), dict(collections.Counter(o['pc_like'] for o in main_game if o['pc']))))
    say('  ... with PC partner tier verified / anchor: %d; pc_like %s' % (
        sum(1 for o in main_game if o['pc_tier'] in ('verified', 'anchor')),
        dict(collections.Counter(o['pc_like'] for o in main_game if o['pc_tier'] in ('verified', 'anchor')))))
    tuo = [o for o in out_rows if o['cls'] == 'tu-only']
    say('tu-only %d: dlc flag %d, area %s' % (len(tuo), sum(1 for o in tuo if o['dlc']),
                                               dict(collections.Counter(o['area'].lstrip('~') for o in tuo))))
    open(os.path.join(out, 'summary.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(log) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
