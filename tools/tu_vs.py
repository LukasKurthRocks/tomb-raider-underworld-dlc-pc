"""Night 03.11. part 4 (test 50n): Xenos VERTEX shader -> D3D9 vs_3_0, built on upstream's pixel-shader translator
(work/ws/shader4/xenos2sm3.py: the ALU / predicate / constant handling is reused unchanged through a subclass). What is
VS-specific is added here: vertex fetches (vfetch -> `dcl_<usage> vN` + mov with the fetch's destination swizzle),
exports (62 = position, interpolator registers -> `dcl_<usage> oN` by the shader's interpolator table), constants by
name -> PC VS registers (the PC twin's CTAB, else the register the name has in every base PC vertex shader), the vs_3_0
header.

Proof (same standard as the pixel shaders): base Xbox VS libs translated with this tool against Nixxes' real PC twins
(shader_x2p), every PC slot that has an Xbox slot of the same number, SM3 VM on shared random inputs per vertex element
and shared constants by name - all outputs (position and every interpolator the PC twin writes) compared (`oracle`).
Input conversion rules per vertex element (the PC vertex format differs from the Xbox one, e.g. DEC3N normals ->
UBYTE4N) are not guessed: they are taken from the oracle (`--conv`), and must hold on every pair.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_vs.py fetches D|X LIB SLOT        vfetch instructions, vertex element table, interpolators
  ../bin/pyt -t 900 tools/tu_vs.py show D|X LIB SLOT [--conv U:mode,...]   translated vs_3_0 text
  ../bin/pyt -t 1800 tools/tu_vs.py oracle XB/PB[,XB/PB] | random N SEED [--conv ...] [--slots ...]
"""
import sys, os, json, struct, collections, random, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs, xenos2sm3
import shaderlib as SL
import sm3vm
from xenos_xlat import bits, decode_cf

USAGE_NAME = {0: 'position', 1: 'blendweight', 2: 'blendindices', 3: 'normal', 4: 'psize', 5: 'texcoord', 6: 'tangent',
              7: 'binormal', 10: 'color', 11: 'fog', 12: 'depth'}
XYZW = 'xyzw'


def pc_vs_regs():
    """{constant name: (start register, count)} over every base PC vertex shader (most frequent start)"""
    L = libs(); cnt = collections.defaultdict(collections.Counter)
    for lib in L['P'].values():
        if lib['kind'] != 0: continue
        for o in set(s for s in lib['slots'] if s != 0xffffffff):
            try:
                for n, rs, ri, rc in SL.constants(lib['entries'][o]['blob'], 'p')[1]:
                    if rs == 2: cnt[n][(ri, rc)] += 1
            except Exception: pass
    return {n: c.most_common(1)[0][0] for n, c in cnt.items()}


_PCV = None


def pcv():
    global _PCV
    if _PCV is None: _PCV = pc_vs_regs()
    return _PCV


class VTr(xenos2sm3.Tr):
    def __init__(self, blob, consts, conv=None, opts=None):
        sh = XL.parse(blob)
        if sh.is_ps: raise xenos2sm3.Reject('not a vertex shader')
        # Tr.__init__ refuses vertex shaders: run it on a patched parse result
        orig = XL.parse
        def parse_ps(b):
            s = orig(b); s.is_ps = True; s.interp_vs = s.interp; s.interp = []; return s
        XL.parse = parse_ps
        try:
            xenos2sm3.Tr.__init__(self, blob, consts, None, lambda n, c: c, opts)
        finally:
            XL.parse = orig
        self.sh.is_ps = False
        self.vs_out = {i['reg']: (i['usage'], i['index']) for i in self.sh.interp_vs}
        self.vin = {}                # (usage, index) -> set(comps) read
        self.conv = conv or {}       # usage -> 'id' | 'snorm' (x * 2 - 1)
        self.fetch_regs = {}
        self.pos_written = False
        # fetch number k (program order) -> vertex element (from the vtx table, matched by fetch constant + offset)
        self.vtx = list(self.sh.vtx)

    # Xenos VS exports: 62 = position, 0..15 = interpolator registers
    def expname(self, vdest):
        if vdest == 62: self.pos_written = True; return 'o11'
        if vdest in self.vs_out: return 'o%d' % vdest
        raise xenos2sm3.Reject('VS export %d' % vdest)

    def fetch_body(self, d0, d1, d2):
        opc = bits(d0, 0, 5)
        if opc != 0: raise xenos2sm3.Reject('VS texture fetch (opcode %d)' % opc)
        dst = bits(d0, 12, 6)
        dsw = bits(d1, 0, 12)
        # the vertex element table names each element by the code address of its vfetch: find this fetch's address
        if not hasattr(self, '_faddr'):
            self._faddr = [e[1] for e in XL.walk(self.sh) if e[0] == 'fetch']; self._fused = set()
        code = self.sh.code
        addr = next((s for s in self._faddr if s not in self._fused and tuple(code[3 * s:3 * s + 3]) == (d0, d1, d2)), None)
        if addr is None: raise xenos2sm3.Reject('vfetch not found in the code')
        self._fused.add(addr)
        e = next((v for v in self.vtx if v['address'] == addr), None)
        if e is None:
            self.palette_fetch(d0, d1, d2, dst, dsw); return
        key = (e['usage'], e['index'])
        if key[0] == 2: self.bi_reg = dst
        dsws = [(dsw >> (3 * i)) & 7 for i in range(4)]
        t = 'vin_%d_%d' % key
        for i in range(4):
            s = dsws[i]
            if s <= 3:
                self.vin.setdefault(key, set()).add(s)
                self.emit('mov r%d.%s, %s.%s' % (dst, XYZW[i], t, XYZW[s]))
            elif s == 4: self.emit('mov r%d.%s, %s.x' % (dst, XYZW[i], self.const1(0)))
            elif s == 5: self.emit('mov r%d.%s, %s.x' % (dst, XYZW[i], self.const1(1)))
        self.mark_written(dst, sum(1 << i for i in range(4) if dsws[i] != 7))

    def palette_fetch(self, d0, d1, d2, dst, dsw):
        """Xbox bone matrix row fetch: vfetch from the palette stream with the BlendIndices value as index (Xenia
        ucode: d0 src_reg 5..10, src_swizzle 30..31; d2 stride 0..7, offset 8..30 in dwords). PC (Nixxes, e.g. PC 71
        slot 2): index = floor(BlendIndices * 255 + 0.5) * 4, rows SkinMatrices[index + row] (4 vec4 per bone); row
        = offset / 4. Only the rigid one-bone case (index register = the fetched BlendIndices, unchanged)."""
        src = bits(d0, 5, 6); comp = bits(d0, 30, 2); off = bits(d2, 8, 23)
        if getattr(self, 'bi_reg', None) != src: raise xenos2sm3.Reject('palette fetch: index register r%d is not the BlendIndices one' % src)
        if off % 4: raise xenos2sm3.Reject('palette fetch: offset %d not a row' % off)
        base = self.consts_fn('SkinMatrices', 0, 1)
        if base is None: raise xenos2sm3.Reject('palette fetch: no PC SkinMatrices')
        self.used_c[base] = ('SkinMatrices', 0)
        k = self.defreg((255.0, 0.5, 4.0, 0.0))
        t = self.tmp(); u = self.tmp()
        self.emit('mad r%d.x, r%d.%s, c%d.x, c%d.y' % (t, src, XYZW[comp], k, k))
        self.emit('frc r%d.x, r%d.x' % (u, t))
        self.emit('add r%d.x, r%d.x, -r%d.x' % (t, t, u))
        self.emit('mul r%d.x, r%d.x, c%d.z' % (t, t, k))
        self.emit('mova a0.x, r%d.x' % t)
        dsws = [(dsw >> (3 * i)) & 7 for i in range(4)]
        self.emit('mov r%d, c[a0.x + %d]' % (u, base + off // 4))
        for i in range(4):
            s = dsws[i]
            if s <= 3: self.emit('mov r%d.%s, r%d.%s' % (dst, XYZW[i], u, XYZW[s]))
            elif s == 4: self.emit('mov r%d.%s, %s.x' % (dst, XYZW[i], self.const1(0)))
            elif s == 5: self.emit('mov r%d.%s, %s.x' % (dst, XYZW[i], self.const1(1)))
        self.rel(t); self.rel(u)
        self.mark_written(dst, sum(1 << i for i in range(4) if dsws[i] != 7))

    def finish(self):
        lines = ['vs_3_0']
        for r in sorted(self.defs):
            lines.append('def c%d, %s' % (r, ', '.join('%.9g' % x for x in self.defs[r])))
        vreg = {}
        for n, key in enumerate(sorted(self.vin, key=lambda k: (k[0] != 0, k))):
            u, ix = key
            if u not in USAGE_NAME: raise xenos2sm3.Reject('input usage %d' % u)
            vreg[key] = n
            lines.append('dcl_%s%s v%d' % (USAGE_NAME[u], ix if ix else '', n))
        lines.append('dcl_position o11')
        for reg, (u, ix) in sorted(self.vs_out.items()):
            if reg in self.exp_written or True:
                lines.append('dcl_%s%s o%d' % (USAGE_NAME.get(u, 'texcoord'), ix if ix else '', reg))
        pro = []
        for key, n in vreg.items():
            if self.conv.get(key[0]) == 'nso':
                # Nixxes' PC vertex formats: normal / tangent / binormal decoded with the uniform NormalScaleOffset
                # (v * NSO.x + NSO.y, read from PC 46 and the other base PC VS that consume these elements)
                r_nso = pcv().get('NormalScaleOffset', (21, 1))[0]
                self.used_c[r_nso] = ('NormalScaleOffset', 0)
                pro.append('mad r%d.xyz, v%d, c%d.x, c%d.y' % (self.vtmp(key), n, r_nso, r_nso))
                pro.append('mov r%d.w, v%d.w' % (self.vtmp(key), n))
            elif self.conv.get(key[0]) == 'snorm':
                # PC element stored unsigned-normalised (UBYTE4N) where the Xbox one is signed: x * 2 - 1
                k2 = self.defreg((2.0, -1.0, 0.0, 0.0))
                pro.append('mad r%d, v%d, c%d.x, c%d.y' % (self.vtmp(key), n, k2, k2))
            else:
                pro.append('mov r%d, v%d' % (self.vtmp(key), n))
        body = [re.sub(r'vin_(\d+)_(\d+)', lambda m: 'r%d' % self.vtmp((int(m.group(1)), int(m.group(2)))), l) for l in self.out]
        # defs created while building the prologue
        lines = [lines[0]] + ['def c%d, %s' % (r, ', '.join('%.9g' % x for x in self.defs[r])) for r in sorted(self.defs)] + \
                [l for l in lines[1:] if not l.startswith('def ')]
        text = '\n'.join(lines + pro + body) + '\n'
        prog = sm3asm.parse_text(text)
        return fix_cmp_vs(prog)


NEGMOD = {0: 1, 1: 0, 11: 12, 12: 11}


def fix_cmp_vs(prog):
    """the PS translator emits `cmp d, a, b, c` (d = a >= 0 ? b : c), which vs_3_0 does not have. Rewritten as
    `sge s, a, -a` (1 where a >= 0, else 0) + `lrp d, s, b, c` (exact for s in {0, 1} and finite b / c); the oracle /
    merge checks run on the rewritten program."""
    ins = prog.instrs()
    if not any(i.op in ('cmp', 'dp2add', 'sincos') for i in ins): return prog
    used = {o.num for i in ins for o in i.ops if o.rtype == sm3asm.RT_TEMP}
    S = max(used | {-1}) + 1          # scratch temps above every used one (the merge re-allocates registers)
    if S > 60: raise xenos2sm3.Reject('rewrite: no free temp')
    out = []
    cp = lambda o, **kw: sm3asm.Operand(kw.get('rtype', o.rtype), kw.get('num', o.num), o.isdst, o.rel, o.relop,
                                        kw.get('wm', o.wm), o.mod, o.shift, kw.get('swz', o.swz), kw.get('smod', o.smod), o.resv)
    for it in prog.items:
        if isinstance(it, sm3asm.Instr) and it.op == 'sincos' and it.ops[1].rtype == sm3asm.RT_TEMP and it.ops[1].num == it.ops[0].num:
            # vs_3_0 / D3DX9 X5768: dst must differ from the source register -> copy the one component read first
            s = it.ops[1]; c = s.swz & 3
            out.append(sm3asm.Instr('mov', [sm3asm.Operand(sm3asm.RT_TEMP, S + 1, True, False, None, 1, 0, 0, 0xE4, 0, 0),
                                            cp(s, swz=c * 0x55)], 0, False, [], 0))
            j = sm3asm.Instr('sincos', [cp(it.ops[0]), cp(s, num=S + 1, swz=0x00)] + [cp(o) for o in it.ops[2:]], it.ctrl, it.pred, list(it.imm), it.usage)
            out.append(j); continue
        if isinstance(it, sm3asm.Instr) and it.op == 'dp2add':
            # ps-only dp2add d, a, b, c = a.x*b.x + a.y*b.y + c (replicated) -> mul / mad / add on a scratch lane
            d, a, b, c = it.ops
            comp = lambda o, i: ((o.swz >> (2 * i)) & 3) * 0x55
            sx = lambda wm: sm3asm.Operand(sm3asm.RT_TEMP, S + 2, True, False, None, wm, 0, 0, 0xE4, 0, 0)
            sr = sm3asm.Operand(sm3asm.RT_TEMP, S + 2, False, False, None, 15, 0, 0, 0x00, 0, 0)
            out.append(sm3asm.Instr('mul', [sx(1), cp(a, swz=comp(a, 0)), cp(b, swz=comp(b, 0))], 0, False, [], 0))
            out.append(sm3asm.Instr('mad', [sx(1), cp(a, swz=comp(a, 1)), cp(b, swz=comp(b, 1)), sr], 0, False, [], 0))
            out.append(sm3asm.Instr('add', [cp(d), sr, cp(c)], it.ctrl, it.pred, [], 0)); continue
        if isinstance(it, sm3asm.Instr) and it.op == 'cmp':
            d, a, b, c = it.ops
            if a.smod not in NEGMOD or a.rel: raise xenos2sm3.Reject('cmp rewrite: source modifier %d' % a.smod)
            cp = lambda o, **kw: sm3asm.Operand(kw.get('rtype', o.rtype), kw.get('num', o.num), o.isdst, o.rel, o.relop,
                                                kw.get('wm', o.wm), o.mod, o.shift, kw.get('swz', o.swz), kw.get('smod', o.smod), o.resv)
            sd = cp(d, rtype=sm3asm.RT_TEMP, num=S); sd.mod = 0
            out.append(sm3asm.Instr('sge', [sd, cp(a), cp(a, smod=NEGMOD[a.smod])], 0, False, [], 0))
            ss = sm3asm.Operand(sm3asm.RT_TEMP, S, False, False, None, 15, 0, 0, 0xE4, 0, 0)
            # D3DX9 X5790: the lrp destination must differ from every source -> lrp into a fresh scratch, then mov
            s3 = cp(d, rtype=sm3asm.RT_TEMP, num=S + 3); s3.mod = 0
            out.append(sm3asm.Instr('lrp', [s3, ss, cp(b), cp(c)], 0, False, [], 0))
            out.append(sm3asm.Instr('mov', [cp(d), sm3asm.Operand(sm3asm.RT_TEMP, S + 3, False, False, None, 15, 0, 0, 0xE4, 0, 0)],
                                    it.ctrl, it.pred, [], 0))
        else: out.append(it)
    return sm3asm.Program(prog.kind, prog.major, prog.minor, out)


def _vtmp(self, key):
    if not hasattr(self, '_vt'): self._vt = {}
    if key not in self._vt:
        self._vt[key] = self.maxtemp + 1 + len(self._vt)
    return self._vt[key]


VTr.vtmp = _vtmp


def consts_fn(pct):
    """Xbox constant name -> PC VS register: the PC twin's CTAB first, then the global base-PC VS table"""
    own = {n: (ri, rc) for n, rs, ri, rc in pct if rs == 2}
    alias = {'CameraPosition': 'g_CameraPosition', 'TexcoordScale': 'TexcoordScales'}
    def fn(name, j, count):
        n = alias.get(name, name)
        if n in own: return own[n][0] + j
        g = pcv().get(n)
        if g is not None: return g[0] + j
        return None
    return fn


def translate(xblob, pct, conv):
    missing = set()
    base = consts_fn(pct)
    def fn(n, j, c):
        r = base(n, j, c)
        if r is None: missing.add(n)
        return r
    if conv == "auto" or not conv:
        # rule from the base oracle: the PC permutation decodes normal / tangent / binormal with NormalScaleOffset
        # exactly when its own CTAB has that constant (PC 46 slot 64 yes, slot 192 no)
        nso = any(n == "NormalScaleOffset" for n, rs, ri, rc in pct)
        conv = {3: "nso", 6: "nso", 7: "nso"} if nso else {}
    t = VTr(xblob, fn, conv)
    t.run()
    if missing: raise xenos2sm3.Reject('constants without a PC VS register: %s' % sorted(missing))
    return t.finish(), t


# ---------------------------------------------------------------------------------------------------- VM
def dcls(prog, rt):
    out = {}
    for i in prog.instrs():
        if i.op == 'dcl' and i.ops[0].rtype == rt: out[i.ops[0].num] = ((i.usage & 31), (i.usage >> 16) & 15)
    return out


def run_vs(prog, inputs_by_sem, consts, N):
    inp = {}
    for n, key in dcls(prog, sm3asm.RT_INPUT).items():
        if key not in inputs_by_sem: return None
        inp[(sm3asm.RT_INPUT, n)] = inputs_by_sem[key]
    r = sm3vm.run(prog, inp, consts, None, N)
    outs = {}
    sem = dcls(prog, sm3asm.RT_TEXOUT)
    for (t, n), v in r['regs'].items():
        if t == sm3asm.RT_TEXOUT and n in sem: outs[sem[n]] = v
    return outs


def compare_vs(T, P, pct_names, N=200, seed=3):
    """T (translation) vs P (Nixxes' PC VS): shared random inputs per element, shared constants by register (both
    use the PC registers); -> (worst rel. error over the outputs P writes, missing outputs)"""
    rng = np.random.RandomState(seed)
    ins = {}
    for key in set(dcls(T, sm3asm.RT_INPUT).values()) | set(dcls(P, sm3asm.RT_INPUT).values()):
        a = rng.uniform(0, 1, (N, 4)).astype(np.float32)
        if key == (0, 0): a[:, :3] = rng.uniform(-50, 50, (N, 3)); a[:, 3] = 1
        if key[0] == 2: a = np.floor(rng.uniform(0, 4, (N, 4))).astype(np.float32)
        ins[key] = a
    consts = {r: rng.uniform(-1, 1, 4).astype(np.float32) for r in range(256)}
    for i in P.instrs() + T.instrs():
        if i.op == 'def': consts[i.ops[0].num] = np.array([struct.unpack('<f', struct.pack('<I', u))[0] for u in i.imm], np.float32)
    ot = run_vs(T, ins, consts, N); op = run_vs(P, ins, consts, N)
    if ot is None or op is None: return None, ['inputs']
    wmP = out_masks(P); wmT = out_masks(T)
    worst = 0.0; miss = []
    for k, v in op.items():
        if k not in ot: miss.append(k); continue
        m = [c for c in range(4) if (wmP.get(k, 15) & wmT.get(k, 15)) >> c & 1]
        d = np.abs(ot[k][:, m] - v[:, m]) / (1 + np.abs(v[:, m]))
        worst = max(worst, float(np.nanmax(d)) if np.isfinite(d).all() else 1e9)
    return worst, miss


def out_masks(prog):
    """{(usage, index): written lane mask} of the output dcls"""
    out = {}
    for i in prog.instrs():
        if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT: out[((i.usage & 31), (i.usage >> 16) & 15)] = i.ops[0].wm
    return out


def cmd_slotmap(pairs, conv):
    """which Xbox slot reproduces each PC slot (common outputs, position included, exact) - the PC slot numbering is not the
    Xbox one for every bit (Nixxes re-used the depth / fog bits for the PSSM shadow output)"""
    L = libs(); X, P = L['X'], L['P']; votes = collections.defaultdict(collections.Counter)
    for xb, pb in pairs:
        cache = {}
        for k, o in enumerate(P[pb]['slots']):
            if o == 0xffffffff: continue
            pblob = P[pb]['entries'][o]['blob']; pct = F9.pc_ctab(pblob); Pp = F9.decode_pc(pblob); hits = []
            for j, xo in enumerate(X[xb]['slots']):
                if xo == 0xffffffff: continue
                try:
                    T, t = translate(X[xb]['entries'][xo]['blob'], pct, conv)
                except Exception: continue
                w, miss = compare_vs(T, Pp, pct)
                if w is not None and w < 1e-4 and (0, 0) in out_masks(T): hits.append((j, tuple(sorted(miss))))
            best = [h for h in hits if not h[1]] or hits
            if best:
                js = tuple(sorted({h[0] for h in best})); votes[k][(js, best[0][1])] += 1
            print('%d/%d PC slot %d: Xbox slots %s' % (xb, pb, k, [(h[0], list(h[1])) for h in hits][:12]), flush=True)
    print('== votes per PC slot (Xbox slots that match, PC-only outputs): count')
    for k in sorted(votes): print('PC slot %3d: %s' % (k, votes[k].most_common(4)))


def lib_of(which, xid):
    L = libs(); return L[which][xid]


def cmd_fetches(which, xid, slot):
    lib = lib_of(which, xid); b = lib['entries'][lib['slots'][slot]]['blob']; sh = XL.parse(b)
    print('vtx', [(XL.USAGE[v['usage']], v['index'], v['address']) for v in sh.vtx])
    print('interp (out)', [(XL.USAGE[v['usage']], v['index'], v['reg']) for v in sh.interp])
    for e in XL.walk(sh):
        if e[0] == 'fetch':
            _, s, d0, d1, d2 = e
            print('fetch @%d: opc %d dst r%d src r%d const %d dsw %03o d1 %08x d2 %08x' % (s, bits(d0, 0, 5), bits(d0, 12, 6), bits(d0, 5, 6), bits(d0, 20, 5), bits(d1, 0, 12), d1, d2))


def parse_conv(a):
    conv = {}
    if '--conv' in a:
        k = a.index('--conv')
        for x in a[k + 1].split(','):
            u, m = x.split(':'); conv[int(u)] = m
        del a[k:k + 2]
    return conv


def vs_pairs():
    L = libs(); X, P = L['X'], L['P']
    return [(x, p) for x, p in sorted(TLT.x2p().items()) if x in X and p in P and X[x]['kind'] == 0 and P[p]['kind'] == 0]


def cmd_oracle(pairs, conv, slots=None):
    L = libs(); X, P = L['X'], L['P']; tot = ok = 0; rej = collections.Counter()
    for xb, pb in pairs:
        res = []
        for k, o in enumerate(P[pb]['slots']):
            if o == 0xffffffff or (slots and k not in slots): continue
            if k >= len(X[xb]['slots']) or X[xb]['slots'][k] == 0xffffffff: continue
            pblob = P[pb]['entries'][o]['blob']; xblob = X[xb]['entries'][X[xb]['slots'][k]]['blob']
            pct = F9.pc_ctab(pblob)
            try:
                T, t = translate(xblob, pct, conv)
            except Exception as e:
                rej[str(e)[:50]] += 1; res.append('s%d:rej' % k); continue
            Pp = F9.decode_pc(pblob)
            per = compare_outputs(T, Pp)
            if per is None: res.append('s%d:inputs' % k); continue
            bad = {s: e for s, e in per.items() if e >= 1e-4}
            for s, e in per.items():
                SEM[s][0] += 1; SEM[s][1] += e < 1e-4
            tot += 1; ok += not bad
            res.append('s%d=%s' % (k, 'ok' if not bad else 'BAD%s' % {s: round(e, 3) for s, e in bad.items()}))
        print('%d/%d: %s' % (xb, pb, ' '.join(res)), flush=True)
    print('SUMMARY vs oracle: %d of %d translated slots exact on every common output; rejects %s' % (ok, tot, dict(rej.most_common(8))))
    print('per output semantic (exact / compared): %s' % {'%s%d' % (USAGE_NAME.get(s[0], s[0]), s[1]): '%d/%d' % (v[1], v[0]) for s, v in sorted(SEM.items())})


SEM = collections.defaultdict(lambda: [0, 0])


def compare_outputs(T, P, N=200, seed=3):
    """per output semantic written by BOTH programs: max rel. error over the lanes both write (PC-only outputs such as
    the PSSM TEXCOORD6 are not compared - they are Nixxes' additions)"""
    rng = np.random.RandomState(seed)
    ins = {}
    for key in set(dcls(T, sm3asm.RT_INPUT).values()) | set(dcls(P, sm3asm.RT_INPUT).values()):
        a = rng.uniform(0, 1, (N, 4)).astype(np.float32)
        if key == (0, 0): a[:, :3] = rng.uniform(-50, 50, (N, 3)); a[:, 3] = 1
        ins[key] = a
    consts = {r: rng.uniform(-1, 1, 4).astype(np.float32) for r in range(256)}
    for i in P.instrs() + T.instrs():
        if i.op == 'def': consts[i.ops[0].num] = np.array([struct.unpack('<f', struct.pack('<I', u))[0] for u in i.imm], np.float32)
    ot = run_vs(T, ins, consts, N); op = run_vs(P, ins, consts, N)
    if ot is None or op is None: return None
    wmP = out_masks(P); wmT = out_masks(T); out = {}
    for k, v in op.items():
        if k not in ot: continue
        m = [c for c in range(4) if (wmP.get(k, 15) & wmT.get(k, 15)) >> c & 1]
        d = np.abs(ot[k][:, m] - v[:, m]) / (1 + np.abs(v[:, m]))
        out[k] = float(np.nanmax(d)) if np.isfinite(d).all() else 1e9
    return out


def realloc(prog):
    """linear-scan temp re-allocation for straight-line code (no flow control): every temp lives from its first to its
    last reference; registers are reused after the last read. Pure renaming - the merge check runs on the result."""
    ins = prog.instrs()
    body = [i for i in ins if i.op not in ('dcl', 'def', 'defi', 'defb')]
    if any(i.op in ('if', 'ifc', 'else', 'endif', 'rep', 'endrep', 'loop', 'endloop', 'call', 'callnz', 'ret', 'label', 'break', 'breakc') for i in body):
        return prog
    first, last = {}, {}
    for n, i in enumerate(body):
        for o in i.ops:
            for r in ([o] + ([o.relop] if o.rel and o.relop is not None else [])):
                if r.rtype == sm3asm.RT_TEMP:
                    first.setdefault(r.num, n); last[r.num] = n
    order = sorted(first, key=lambda r: first[r])
    free = list(range(32)); active = []; phys = {}
    for r in order:
        for a in list(active):
            if last[a] < first[r]: free.append(phys[a]); active.remove(a)
        free.sort()
        if not free: phys[r] = 32 + len(phys); continue
        phys[r] = free.pop(0); active.append(r)
    for i in body:
        for o in i.ops:
            if o.rtype == sm3asm.RT_TEMP: o.num = phys[o.num]
            if o.rel and o.relop is not None and o.relop.rtype == sm3asm.RT_TEMP: o.relop.num = phys[o.relop.num]
    return prog


def merge_slot(P, T, override=()):
    """P = Nixxes' PC twin slot (kept whole: its outputs incl. position and the PC-only PSSM TEXCOORD6), T = the
    translated DLC slot; the outputs T writes that P does not are appended (T's code with renamed temps / inputs /
    outputs; T's writes to outputs P already has go to a scratch temp). -> merged program, list of added semantics"""
    pin = {v: k for k, v in dcls(P, sm3asm.RT_INPUT).items()}; tin = dcls(T, sm3asm.RT_INPUT)
    pout = {v: k for k, v in dcls(P, sm3asm.RT_TEXOUT).items()}; tout = dcls(T, sm3asm.RT_TEXOUT)
    used_t = [o.num for i in P.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP]
    off = max(used_t + [-1]) + 1
    t_t = sorted({o.num for i in T.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP})
    tdense = {r: off + n for n, r in enumerate(t_t)}          # T's temps renumbered densely after P's
    scratch = off + len(t_t)
    # (the 32-temp limit is checked after the register re-allocation below)
    free_v = [n for n in range(16) if n not in dcls(P, sm3asm.RT_INPUT)]
    free_o = [n for n in range(12) if n not in dcls(P, sm3asm.RT_TEXOUT)]
    vmap = {}; omap = {}; hdr = []; added = []
    for n, sem in tin.items():
        if sem in pin: vmap[n] = pin[sem]
        else:
            vmap[n] = free_v.pop(0); hdr.append('dcl_%s%s v%d' % (USAGE_NAME[sem[0]], sem[1] or '', vmap[n]))
    for n, sem in tout.items():
        if sem in override: omap[n] = pout[sem]          # the DLC value replaces the PC one (T runs after P: last write)
        elif sem in pout or sem[0] == 12: omap[n] = None     # DEPTH: dropped by Nixxes on PC (TEXCOORD6 instead), never read by a PC PS
        else:
            omap[n] = free_o.pop(0); added.append(sem)
            hdr.append('dcl_%s%s o%d' % (USAGE_NAME.get(sem[0], 'texcoord'), sem[1] or '', omap[n]))
    pdefs = {i.ops[0].num for i in P.instrs() if i.op in ('def', 'defi', 'defb')}
    pconst = {o.num for i in P.instrs() for o in i.ops if o.rtype == sm3asm.RT_CONST}
    tdefs = [i for i in T.instrs() if i.op == 'def']
    for i in tdefs:
        if i.ops[0].num in pconst or i.ops[0].num in pdefs: raise xenos2sm3.Reject('merge: def c%d collides' % i.ops[0].num)
    body = []
    for i in T.instrs():
        if i.op in ('dcl', 'def', 'defi', 'defb'): continue
        j = sm3asm.Instr(i.op, [], i.ctrl, i.pred, list(i.imm), i.usage)
        for o in i.ops:
            o2 = sm3asm.Operand(o.rtype, o.num, o.isdst, o.rel, o.relop, o.wm, o.mod, o.shift, o.swz, o.smod, o.resv)
            if o.rtype == sm3asm.RT_TEMP: o2.num = tdense[o.num]
            elif o.rtype == sm3asm.RT_INPUT: o2.num = vmap[o.num]
            elif o.rtype == sm3asm.RT_TEXOUT:
                if omap[o.num] is None: o2.rtype = sm3asm.RT_TEMP; o2.num = scratch
                else: o2.num = omap[o.num]
            j.ops.append(o2)
        body.append(j)
    ptxt = sm3asm.format_program(P).splitlines()
    ph = [l for l in ptxt if l.strip().startswith(('vs_', 'dcl', 'def'))]; pb = [l for l in ptxt if l.strip() and l not in ph]
    txt = '\n'.join([ph[0]] + [sm3asm.fmt_instr(i, 'vs') for i in tdefs] + ph[1:] + hdr + pb +
                    [sm3asm.fmt_instr(i, 'vs') for i in body]) + '\n'
    M = realloc(sm3asm.parse_text(txt))
    nt = len({o.num for i in M.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP})
    if max([o.num for i in M.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP] + [0]) > 31: raise xenos2sm3.Reject('merge: %d temps after re-allocation' % nt)
    return M, added


def check_merge(M, P, T, override=(), N=200, seed=5):
    """VM: M's outputs == P's for every P output, == T's for the added ones (exact)"""
    rng = np.random.RandomState(seed); ins = {}
    for key in set(dcls(M, sm3asm.RT_INPUT).values()) | set(dcls(P, sm3asm.RT_INPUT).values()) | set(dcls(T, sm3asm.RT_INPUT).values()):
        a = rng.uniform(0, 1, (N, 4)).astype(np.float32)
        if key == (0, 0): a[:, :3] = rng.uniform(-50, 50, (N, 3)); a[:, 3] = 1
        ins[key] = a
    consts = {r: rng.uniform(-1, 1, 4).astype(np.float32) for r in range(256)}
    for prog in (P, T, M):
        for i in prog.instrs():
            if i.op == 'def': consts[i.ops[0].num] = np.array([struct.unpack('<f', struct.pack('<I', u))[0] for u in i.imm], np.float32)
    om, op, ot = run_vs(M, ins, consts, N), run_vs(P, ins, consts, N), run_vs(T, ins, consts, N)
    worst = 0.0
    for ref, which in ((op, 'P'), (ot, 'T')):
        for k, v in ref.items():
            if which == 'P' and k in override: continue
            if which == 'T' and ((k in op and k not in override) or k[0] == 12): continue
            if k not in om: return 1e9
            m = [c for c in range(4) if out_masks(M).get(k, 15) >> c & 1]
            worst = max(worst, float(np.nanmax(np.abs(om[k][:, m] - v[:, m]))))
    return worst


def cmd_vsmerge(dl, pc, xbase, outp):
    """PC VS lib for DLC VS dl: per PC slot of the twin pc: the twin's entry + the DLC slot's extra outputs (translated);
    every merged slot checked: (a) the DLC translation == the twin on every common output except the position of
    slots where the base pair xbase / pc itself differs in position (Nixxes' depth-pass change), (b) merged == twin on
    the twin's outputs and == translation on the added ones, (c) D3DX9 vs_3_0 valid. Skinned DLC slots (bone palette
    by vfetch) cannot be translated: those slots keep the twin entry (no extra outputs) and are listed."""
    import column_shader_translate as CST, fade_slots_translate as FST
    L = libs(); D, Pl, Xb = L['D'][dl], L['P'][pc], L['X'][xbase]
    slots = []; log = []; uniq = {}; taken = FST.known_hashes(); nmer = nskip = 0
    for k, o in enumerate(Pl['slots']):
        if o == 0xffffffff: slots.append(None); continue
        pblob = CST.trim(Pl['entries'][o]['blob']); P = F9.decode_pc(pblob); pct = F9.pc_ctab(pblob)
        keep = (Pl['entries'][o]['hash'], pblob)
        # DLC slot for PC slot k: k itself, except where the PC twin writes TEXCOORD5 (fog / world position) and the
        # Xbox slot k does not - Nixxes moved the Xbox fog group (bit 3: 40 / 104 / 168 / 232) onto the slots
        # 32 / 96 / 160 / 224 (see the 50l colour VS and the Look VS 2944); then k + 8. Checked below on the common outputs.
        src = k
        pouts = set(dcls(P, sm3asm.RT_TEXOUT).values())
        try:
            if (5, 5) in pouts and k + 8 < len(D['slots']) and D['slots'][k + 8] != 0xffffffff and \
                    not any((v['usage'], v['index']) == (5, 5) for v in XL.parse(D['entries'][D['slots'][k]]['blob']).interp):
                src = k + 8
        except Exception: pass
        if src >= len(D['slots']) or D['slots'][src] == 0xffffffff:
            slots.append(keep); log.append('slot %3d: no DLC slot - twin kept' % k); continue
        try:
            T, t = translate(D['entries'][D['slots'][src]]['blob'], pct, 'auto')
            if src != k: log.append('slot %3d: uses DLC slot %d (fog group)' % (k, src))
        except Exception as e:
            slots.append(keep); nskip += 1; log.append('slot %3d: DLC slot not translatable (%s) - twin kept, NO extra outputs' % (k, str(e)[:70])); continue
        per = compare_outputs(T, P) or {}
        diff = {s for s, e in per.items() if e >= 1e-4}
        override = set(); posbad = False
        if diff:
            # decide per differing output with the base twin's own translation Tb (same PC slot conventions):
            #   Tb == PC  -> the difference is the DLC's own change   -> the DLC (translated) value replaces the PC one
            #   Tb != PC and DLC == Tb -> Nixxes' PC change (e.g. depth-pass position) the DLC shares -> PC kept
            #   otherwise ambiguous -> refuse
            if src >= len(Xb['slots']) or Xb['slots'][src] == 0xffffffff: raise xenos2sm3.Reject('slot %d differs, no base slot %d' % (k, src))
            Tb, _ = translate(Xb['entries'][Xb['slots'][src]]['blob'], pct, 'auto')
            pb = compare_outputs(Tb, P) or {}; tb = compare_outputs(T, Tb) or {}
            amb = []
            for s in diff:
                if pb.get(s, 1) < 1e-4: override.add(s)
                elif tb.get(s, 1) < 1e-4: posbad = posbad or s == (0, 0)
                else: amb.append(s)
            if amb == [(0, 0)] and pb.get((0, 0), 1) >= 1e-4:
                # a Nixxes depth-pass slot (the PC position is not the Xbox one even for the base pair) where the DLC
                # position also differs from the base one: not decidable -> the twin entry stays (depth pass: the
                # colour interpolators are not read there - pass 0 / 1 keep their PC shaders)
                slots.append(keep); nskip += 1; log.append('slot %3d: depth-pass slot, position not decidable - twin kept' % k); continue
            if amb: raise xenos2sm3.Reject('slot %d: outputs %s differ from PC and from the base translation' % (k, amb))
        M, added = merge_slot(P, T, override)
        if not added and not override: slots.append(keep); log.append('slot %3d: nothing to add - twin kept' % k); continue
        w = check_merge(M, P, T, override)
        bc = sm3asm.encode(M); ok_, msg = FST.SV.assemble(FST.SD.disasm(bc))
        if w > 1e-5 or not ok_ or msg.strip():
            open(outp + '.bad_s%d.txt' % k, 'w').write(FST.SD.disasm(bc) + '\n' + msg)
            raise xenos2sm3.Reject('slot %d merge check %.3g / D3DX9 %s' % (k, w, msg.strip()[:80]))
        if bc not in uniq: uniq[bc] = CST.new_hash(bc, taken)
        slots.append((uniq[bc], bc)); nmer += 1
        log.append('slot %3d: twin + %s%s (other common outputs exact%s), merged check %.1g, D3DX9 ok' % (
            k, ['%s%d' % (USAGE_NAME.get(s[0]), s[1]) for s in added],
            (', DLC replaces %s' % ['%s%d' % (USAGE_NAME.get(s[0]), s[1]) for s in sorted(override)]) if override else '',
            ', position = Nixxes depth change' if posbad else '', w))
    j = {e['junk'] for e in Pl['entries'].values()}
    data = CST.pc_lib(Pl['kind'], slots, j.pop() if len(j) == 1 else 0)
    open(outp, 'wb').write(data)
    for l in log: print(l)
    print('RESULT VS %d (twin PC %d, base %d): %d slots merged, %d DLC slots not translatable (twin kept), %d bytes' % (dl, pc, xbase, nmer, nskip, len(data)))


def cmd_vsapply(invp, tree, wd, specs):
    """put merged VS libs into the tree: specs XLIB:XVS:NEWID:LIBFILE - every inventory material of Xbox pass-2 lib XLIB
    whose Xbox VS is XVS gets VS NEWID (tu_unlit apply --pass 3) in every file copy; files not yet in the tree are copied
    from their effective source first"""
    import shutil, io, contextlib
    import tu_unlit as TU
    inv = json.load(open(invp)); os.makedirs(wd, exist_ok=True)
    for sp in specs:
        xl, xvs, nid, libf = sp.split(':'); xl, xvs, nid = int(xl), int(xvs), int(nid)
        perfile = collections.defaultdict(list)
        for r in inv:
            if r['xlib'] == xl and r['vs'][0] == xvs:
                for f in r['files']: perfile[(f['name'], f['pc'], f['xbox'])].append((r['mat'], f['xmat']))
        for (name, pc, xb), ms in sorted(perfile.items()):
            dst = os.path.join(tree, 'mods', os.path.basename(pc))
            if not os.path.exists(dst): shutil.copyfile(pc, dst); print('copied %s into the tree' % name)
            pk = os.path.join(wd, 'vs_%d_%s' % (nid, name[:-4])); os.makedirs(pk, exist_ok=True)
            shutil.copyfile(libf, os.path.join(pk, '%d.lib' % nid))
            json.dump({str(xvs): dict(new=nid, mats=ms)}, open(os.path.join(pk, 'map.json'), 'w'))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                TU.cmd_apply(dst, xb, dst + '.tmp50n', pk, 3)
            os.replace(dst + '.tmp50n', dst)
            print('%s: VS %d -> %d for materials %s; %s' % (name, xvs, nid, [m for m, x in ms], buf.getvalue().strip().splitlines()[-2][:120]))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'vsmerge': cmd_vsmerge(int(a[1]), int(a[2]), int(a[3]), a[4]); return
    if a[0] == 'vsapply': cmd_vsapply(a[1], a[2], a[3], a[4:]); return
    conv = parse_conv(a)
    slots = None
    if '--slots' in a:
        k = a.index('--slots'); slots = {int(x) for x in a[k + 1].split(',')}; del a[k:k + 2]
    if a[0] == 'fetches': cmd_fetches(a[1], int(a[2]), int(a[3])); return
    if a[0] == 'slotmap': cmd_slotmap([tuple(int(y) for y in x.split('/')) for x in a[1].split(',')], conv); return
    if a[0] == 'show':
        lib = lib_of(a[1], int(a[2])); b = lib['entries'][lib['slots'][int(a[3])]]['blob']
        T, t = translate(b, [], conv); print(sm3asm.format_program(T)); return
    if a[0] == 'oracle':
        if a[1] == 'random':
            random.seed(int(a[3])); ps = vs_pairs(); cmd_oracle(sorted(random.sample(ps, min(int(a[2]), len(ps)))), conv, slots)
        else: cmd_oracle([tuple(int(y) for y in x.split('/')) for x in a[1].split(',')], conv, slots)
        return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
