"""Test 50a/50c, second route for the TU lit shaders WITHOUT an equivalent base light block (doppelganger face 2679, body
skin 2682 / 2685, holster 2688): "PC per-light geometry + Xbox BRDF".

Construction (T = PC pixel shader for one PC slot):
  X  = the Xbox shader translated Xenos -> ps_3_0 (f9.translate_x, PC constant registers, lights on, Xbox shadows off).
       Its light block is 7 generic light chunks; chunk 1 (an accumulating chunk) is cut by lane-level taint:
       geometry (reads only this light's position / direction / attenuation constants, the attenuation sampler and
       the world position), BRDF (geometry values x surface values), tail (projection, colour, accumulation).
       Instructions of the block without any light dependence (hoisted set-up) move before the block.
  Pd = a PC donor pixel shader of the same slot: its light chain (`if b0 .. b6`) is kept as structure; in every light
       sub-block the PC geometry (light-pure instructions: visibility incl. PC shadows, radiance = visibility x colour
       [x modulation], L) is kept, the PC BRDF and accumulation are dropped and replaced by: L lanes of X := PC L,
       the Xbox BRDF of chunk 1, and acc_X[lane] += D_or_S x radiance[colour lane] (the lane / scalar pairing of the
       Xbox tail is probed in the VM: one BRDF output and one colour lane at a time).
  The X block's inputs / outputs are wired with f9.assemble (in_moves / out_moves), as in the transplant.
Proof (oracle): the same construction for a BASE Xbox lib Xb with its own PC twin Pb as donor (and with other
donors) must reproduce Pb (VM, real material params, lights off / on / mixed).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_perlight.py xblock D|X XID SLOT OUT.txt
  ../bin/pyt -t 900 tools/tu_perlight.py oracle XB/PB[/PD] [...] [--slots 2,0,4,6,1] [--debug]   base pairs (PD defaults to PB)
  ../bin/pyt -t 3000 tools/tu_perlight.py oracle-random N SEED      N random base lit pairs, slot 2
  ../bin/pyt -t 900 tools/tu_perlight.py ldiag XB PB SLOT BIT       light term of one bool, T vs the PC lib (writes T asm)
  ../bin/pyt -t 1800 tools/tu_perlight.py build PC.drm XBOX.drm OUTDIR --mesh 21730 --libs XID[,XID] [--donor PD] [--mats PM,PM]
      like tu_light_transplant build (same plan.json / .bin layout, usable by its pack / apply / vscheck);
      --mats: only these PC materials of the mesh (one lib per sampler-map / DXN set; refused when the users differ)
"""
import sys, os, json, struct, hashlib, collections, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs
import f9_common



# ---- f9.assemble with FIXED temps: P' temps listed in FIXED keep a given T register (X registers the Xbox BRDF only
# reads; they hold their value through the block because they are reserved as X block inputs). Built from the
# upstream source text with the same liveness patch as tu_light_transplant.
FIXED = {}


def _patch_assemble_fixed():
    src = open(F9.__file__, encoding='utf-8').read()
    a = src.index('def assemble('); b = src.index('\ndef dce(')
    s = src[a:b]
    old_r = ("    for i in BX[i1:]:\n        for o in i.ops:\n"
             "            if not o.isdst and o.rtype == sm3asm.RT_TEMP: reserved.add(o.num)\n")
    old_t = ("    if len(free) < len(ptemps): raise Fail('temp insufficienti: servono %d, liberi %d' % (len(ptemps), len(free)))\n"
             "    tmap = dict(zip(ptemps, free))\n")
    if old_r not in s or old_t not in s: raise SystemExit('f9.assemble changed upstream - patch not applicable')
    s = s.replace(old_r, "    reserved |= _live_after(BX, i1, xprog)\n"
                         "    reserved |= {o.num for i in xslice for o in i.ops if o.rtype == sm3asm.RT_TEMP}\n")
    s = s.replace(old_t, "    ptemps = [p for p in ptemps if p not in FIXED]\n"
                         "    if len(free) < len(ptemps): raise Fail('temp insufficienti: servono %d, liberi %d' % (len(ptemps), len(free)))\n"
                         "    tmap = dict(zip(ptemps, free)); tmap.update(FIXED)\n")
    ns = F9.__dict__
    ns['_live_after'] = TLT._live_after; ns['FIXED'] = FIXED
    exec(compile(s, F9.__file__ + ' (assemble, test50c patch)', 'exec'), ns)


_patch_assemble_fixed()
LSAMP_X = {14, 15} | set(range(16, 23))
PC_LIGHT_NAME = re.compile(r'Light|Shadow|Modulation|PSSM|Parallel|Split')


DEBUG = "--debug" in sys.argv


class Fail(Exception):
    pass


def reads(i, st):
    """[(kind, num, lanes)] read by instruction i; kind 't' temp, 'c' const, 'v' input, 's' sampler, 'b' bool"""
    out = []
    for j, o in enumerate(i.ops):
        if o.isdst: continue
        if o.rtype == sm3asm.RT_TEMP: out.append(('t', o.num, F9.lanes(i, j, st)))
        elif o.rtype == sm3asm.RT_CONST: out.append(('c', o.num, F9.lanes(i, j, st)))
        elif o.rtype == sm3asm.RT_INPUT: out.append(('v', o.num, F9.lanes(i, j, st)))
        elif o.rtype == sm3asm.RT_SAMPLER: out.append(('s', o.num, []))
        elif o.rtype == sm3asm.RT_CONSTBOOL: out.append(('b', o.num, []))
        if o.rel and o.relop is not None and o.relop.rtype == sm3asm.RT_TEMP: out.append(('t', o.relop.num, [0, 1, 2, 3]))
    return out


COMPWISE = {'mov', 'add', 'mul', 'mad', 'max', 'min', 'cmp', 'slt', 'sge', 'frc', 'abs', 'lrp', 'sub', 'mov_sat'}


def lane_reads(i, st):
    """{dst lane: [(kind, num, lanes)]}: componentwise ops read swizzle lane l for dst lane l, others read all"""
    w = [c for c in range(4) if i.ops and i.ops[0].isdst and i.ops[0].wm >> c & 1]
    allr = reads(i, st)
    if i.op not in COMPWISE: return {c: allr for c in w}
    out = {}
    for c in w:
        rd = []
        for o in i.ops:
            if o.isdst: continue
            sl = [(o.swz >> (2 * c)) & 3]
            if o.rtype == sm3asm.RT_TEMP: rd.append(('t', o.num, sl))
            elif o.rtype == sm3asm.RT_CONST: rd.append(('c', o.num, sl))
            elif o.rtype == sm3asm.RT_INPUT: rd.append(('v', o.num, sl))
            if o.rel and o.relop is not None and o.relop.rtype == sm3asm.RT_TEMP: rd.append(('t', o.relop.num, [0, 1, 2, 3]))
        out[c] = rd
    return out


def writes(i):
    if i.ops and i.ops[0].isdst and i.ops[0].rtype == sm3asm.RT_TEMP and i.op not in ('if', 'ifc'):
        return [(i.ops[0].num, c) for c in range(4) if i.ops[0].wm >> c & 1]
    return []


def clone(i, tmap=None):
    j = sm3asm.Instr(i.op, [], i.ctrl, i.pred, list(i.imm), i.usage)
    for o in i.ops:
        o2 = sm3asm.Operand(o.rtype, o.num, o.isdst, o.rel, o.relop, o.wm, o.mod, o.shift, o.swz, o.smod, o.resv)
        if o.rtype == sm3asm.RT_TEMP and tmap is not None: o2.num = tmap[o.num]
        j.ops.append(o2)
    return j


def P(text):
    return sm3asm.parse_text('ps_3_0\n' + text + '\n').instrs()[0]


# ------------------------------------------------------------------------------------------------ Xbox side
def taint_flags(i, rd, LX, flag, lo, hi):
    F = set()
    for t, n, ls in rd:
        if t == 'c' and n in LX:
            rel = LX[n] - lo
            F.add('O' if not 0 <= rel < hi - lo else ('T' if rel == 3 or 5 <= rel <= 8 else 'G'))
        elif t == 's' and n in LSAMP_X: F.add('T' if n >= 16 else 'G')
        elif t == 'v': F.add('S')
        elif t == 't':
            for c in ls: F |= flag.get((n, c), {'S'})
    return F


def xbox_analysis(xblob, K, samp, log, tail_move=False):
    xprog, i0, i1, tr = F9.translate_x(xblob, K.fn, samp, F9.xbools(xblob), opts=dict(TLT.EXTRA_OPTS))
    if i0 is None: raise Fail('no Xbox light block')
    B = F9.body(xprog); st = F9.stypes(xprog)
    if any(i.op in ('if', 'ifc', 'else', 'endif', 'rep', 'loop') for i in B[i0:i1]): raise Fail('control flow in the Xbox block')
    LX = {r: j for (n, j), r in K.extra.items() if n == 'p_Lights'}
    def first_read(j):
        r = next((r_ for r_, j_ in LX.items() if j_ == j), None)
        if r is None: return None
        return next((k for k in range(i0, i1) for o in B[k].ops if not o.isdst and o.rtype == sm3asm.RT_CONST and o.num == r), None)
    c1s, c2s = first_read(13), first_read(26)
    if c1s is None: raise Fail('no light chunk 1')
    c1e = c2s if c2s is not None else i1
    def is_light(rd, lit):
        return any((t == 'c' and n in LX) or (t == 's' and n in LSAMP_X) or (t == 't' and any((n, c) in lit for c in ls)) for t, n, ls in rd)
    lit = set(); hoist = []; lit2 = None; hoist_lanes = {}
    for k in range(i0, i1):
        if k == c1s: lit2 = set(lit)
        i = B[k]; w = writes(i); lr = lane_reads(i, st); clean = False
        for (r_, c_) in w:
            if is_light(lr[c_], lit): lit.add((r_, c_))
            else: lit.discard((r_, c_)); clean = True
        if clean: hoist.append(k); hoist_lanes[k] = {l for l in w if l not in lit}
    # chunk 1 classification
    flag = {l: {'O'} for l in lit2}
    pos = {(n, c) for t, n, ls in reads(B[c1s], st) if t == 't' for c in ls}
    for l in pos: flag[l] = {'G'}
    cls = {}; fl0 = dict(flag)
    for k in range(c1s, c1e):
        i = B[k]; lr = lane_reads(i, st); fl_prev = dict(flag)
        Fl = {l: taint_flags(i, lr[l[1]], LX, fl_prev, 13, 26) for l in writes(i)}
        F = set().union(*Fl.values()) if Fl else taint_flags(i, reads(i, st), LX, fl_prev, 13, 26)
        cls[k] = 'tail' if ('O' in F or 'T' in F) else 'brdf' if ('G' in F and 'S' in F) else 'geo' if 'G' in F else 'hoist'
        flag.update(Fl)
    ft = next((k for k in range(c1s, c1e) if cls[k] == 'tail'), c1e)
    # BRDF = brdf / constant-only instructions before the first tail instruction; tail = everything non-geometry after it
    brdf = [k for k in range(c1s, ft) if cls[k] in ('brdf', 'hoist')]
    tail = [k for k in range(ft, c1e) if cls[k] != 'geo']
    late = [k for k in tail if cls[k] in ('brdf', 'hoist')]
    if late and tail_move:              # only when tail_linear() found the old split non-linear (build)
        # P4.3 (14.11., Xbox 2057): the Xbox compiler interleaves: 2057 chunk 1 has the diffuse colour mad (201) BEFORE
        # the specular math (202-207: log / exp of sat(R.V), x c108.y, x visibility, x the lerp term) and the specular
        # colour mad (208). 'everything after the first tail instruction' put 202-207 in the tail, which the build
        # replaces by acc += output x radiance -> the specular power was lost (Xbox-lit reference 0.000). Now the tail is
        # only the colour / accumulator instructions and what reads their results; a later BRDF instruction moves into
        # the BRDF (before the tail) unless it writes a lane an earlier tail instruction reads or writes (refused).
        # only the backward slice of the true tail instructions (cls 'tail') through late BRDF instructions moves - the
        # other late instructions (scratch movs / maxes the old route ran in the probe only) stay where they were, so
        # builds without such a slice are byte-identical (base proof work/p43_1411/rad_fold_proof.py)
        need = set(); mv = []
        late_all = [k for k in range(ft, c1e) if cls[k] != 'geo']
        for k in reversed(late_all):
            if cls[k] == 'tail':
                for t, n, ls in reads(B[k], st):
                    if t == 't': need |= {(n, c) for c in ls}
                continue
            w_ = set(writes(B[k]))
            if not (w_ & need): continue
            mv.append(k); need -= w_
            for l_ in w_:
                for t, n, ls in lane_reads(B[k], st).get(l_[1], []):
                    if t == 't': need |= {(n, c) for c in ls}
        mv = sorted(mv)
        tl = set(k for k in late_all if k not in mv)
        tru = {k for k in late_all if cls[k] == 'tail'}
        for k in mv:
            for t_ in sorted(tru):                # hazard: an earlier TRUE tail instruction uses a lane the move rewrites
                if t_ > k: break
                rd_t = {(n, c) for t, n, ls in reads(B[t_], st) if t == 't' for c in ls}
                if set(writes(B[k])) & (rd_t | set(writes(B[t_]))):
                    raise Fail('tail reorder hazard: %s writes a lane tail instruction %d uses' % (sm3asm.fmt_instr(B[k], 'ps'), t_))
        if mv:
            brdf = brdf + mv; tail = sorted(tl)
            log.append('P4.3 chunk 1: %d BRDF instructions after the first tail instruction moved into the BRDF (%s)' % (len(mv), mv))
    flag = fl0; wcls = {}; Lx = set(); Lfirst = {}; din = set(); DS = set(); DSat = {}; tail_pure = set(); written_brdf = set()
    bset, tset = set(brdf), set(tail)
    for k in range(c1s, c1e):
        i = B[k]; rd = reads(i, st); lr = lane_reads(i, st); fl_prev = dict(flag)
        F = taint_flags(i, rd, LX, flag, 13, 26)
        c_ = 'brdf' if k in bset else 'tail' if k in tset else 'geo'
        for t, n, ls in rd:
            if t != 't': continue
            for c in ls:
                f = flag.get((n, c), {'S'})
                if c_ == 'brdf':
                    if f == {'G'} and (n, c) not in Lx and (n, c) not in written_brdf: Lx.add((n, c)); Lfirst[(n, c)] = k
                    elif 'S' in f and 'G' not in f and (n, c) not in written_brdf: din.add((n, c))
                if c_ == 'tail':
                    if wcls.get((n, c)) == 'brdf': DS.add((n, c)); DSat.setdefault((n, c), k)
                    elif f == {'G'} and wcls.get((n, c)) != 'tail': tail_pure.add((n, c))
        for l in writes(i):
            flag[l] = taint_flags(i, lr[l[1]], LX, fl_prev, 13, 26); wcls[l] = c_
            if c_ == 'brdf': written_brdf.add(l)
    if not brdf or not DS: raise Fail('chunk 1: brdf %d instr, outputs %s' % (len(brdf), sorted(DS)))
    log.append('X block [%d,%d), chunk 1 [%d,%d): geo %d, brdf %d, tail %d, hoisted (block) %d; L lanes %s, brdf inputs %d, '
               'outputs %s (first read %s), first tail %d, tail pure reads %s' % (i0, i1, c1s, c1e, sum(1 for v in cls.values() if v == 'geo'), len(brdf), len(tail),
                                                   len(hoist), sorted(Lx), len(din), sorted(DS), DSat, ft, sorted(tail_pure)))
    return dict(xprog=xprog, i0=i0, i1=i1, B=B, st=st, LX=LX, c1s=c1s, c1e=c1e, hoist=hoist, hoist_lanes=hoist_lanes, brdf=brdf, tail=tail, Lx=sorted(Lx), Lfirst=Lfirst,
                din=sorted(din), DS=sorted(DS), tail_pure=sorted(tail_pure), lit=lit, cls=cls, late=late)


def tail_linear(A, seeds=(1, 2)):
    """P4.3: the build replaces the chunk-1 tail by acc += BRDF output x radiance, i.e. it assumes the tail is LINEAR in
    each BRDF output (x_tail_map probes with one output = 1). True when, for random positive outputs (light-pure tail
    reads = 1, colour (1, 2, 4), as x_tail_map), halving one output halves its contribution to every lane the colour /
    accumulator instructions write, for every output. 2057's tail (log / exp of sat(R.V) before the specular colour
    mad) is not -> tail_move."""
    xprog, B = A['xprog'], A['B']; N = 16
    rcol = next(r for r, j in A['LX'].items() if j == 16)
    instrs = [B[k] for k in A['tail']]
    out_l = sorted({l for k in A['tail'] if A['cls'][k] == 'tail' for l in writes(B[k])})
    if not out_l: return True
    tex = lambda s, c, m: np.ones((c.shape[0], 4), np.float32)
    for seed in seeds:
        rng = np.random.RandomState(seed)
        # material / engine constants random (x_tail_map's zeros hide a pow: exp(0 x log x) = 1), lights as x_tail_map
        consts = {r: rng.uniform(0.05, 1.5, 4).astype(np.float32) for r in range(256)}
        for r, j in A['LX'].items(): consts[r] = np.float32([0.5, 0.5, 0.5, 1.0])
        consts[rcol] = np.float32([1, 2, 4, 8])
        base = {}
        regs = {r for r, c in A['DS']} | {r for r, c in A['tail_pure']} | {r for r, c in out_l}
        for r in regs: base[(0, r)] = np.zeros((N, 4), np.float32)
        for (r, c) in A['tail_pure']: base[(0, r)][:, c] = 1.0
        for (r, c) in A['DS']: base[(0, r)][:, c] = rng.uniform(0.2, 1.0, N).astype(np.float32)
        def run(st):
            reg, _ = F9.run_state(xprog, instrs, st, consts, tex, N, F9.ALLB)
            return np.stack([reg[(0, r)][:, c] if (0, r) in reg else np.zeros(N, np.float32) for r, c in out_l], 1)
        for ds in A['DS']:
            outs = []
            for f in (1.0, 0.5, 0.0):
                s2 = {k: v.copy() for k, v in base.items()}; s2[(0, ds[0])][:, ds[1]] *= f
                outs.append(run(s2))
            d1, dh = outs[0] - outs[2], outs[1] - outs[2]
            if not (np.isfinite(d1).all() and np.isfinite(dh).all() and np.allclose(dh, 0.5 * d1, rtol=1e-4, atol=1e-6)):
                return False
    return True


def x_vis_lane(A, r, c, k):
    """P4.3 (14.11., Xbox 2057 DLC 1 dungeon water 20262): is light-pure lane (r, c), first read by the chunk-1 BRDF at
    k, a scalar light visibility (attenuation x cone) and not L? 2057 computes the attenuation into r0.z (`cmp r0.z,
    r16, c223.x, c222.x` cone test, `texld r16, .., s15` falloff, `cmp r0.z, -r0.z_abs, r1.x, c219.x`) and multiplies
    it INSIDE the BRDF (`mul r1.w, sat(N.L), r0.z`, specular `mul r1.w, r0.z, pow`) - other libs multiply it into the
    colour in the tail, where tail_pure lanes are already probed as visibility 1. Proof (VM, Xbox-lit reference light of
    tools/perlight_xref.py, seeds 5 / 11): (a) it is the only light-pure BRDF lane of its register (L takes 3 lanes);
    (b) it is a real light term: non-zero on some samples, finite everywhere; (c) the rest of chunk 1 is LINEAR in it -
    every lane chunk 1 writes from k on changes by exactly half when the lane is halved (out(v/2) - out(0) =
    (out(v) - out(0)) / 2) and at least one changes. Then setting it to 1 and letting the PC radiance (= PC visibility x
    colour) carry it is exact; the build's Xbox-lit reference (>= 0.999) checks the whole shader afterwards."""
    import perlight_xref as PX
    B = A['B']; xprog = A['xprog']
    if sum(1 for (r_, c_) in A['Lx'] if r_ == r) != 1: return False
    LXi = {j: r_ for r_, j in A['LX'].items()}
    span = B[k:A['c1e']]
    wl = sorted({l for i in span for l in writes(i)})
    moved = False
    for seed in (5, 11):
        env = F9.Env(seed); L = PX.light(np.random.RandomState(seed + 100), -100.0)
        cons = dict(env.consts); PX.set_x(cons, LXi, L)
        for j in range(13):                       # the reference light also on Xbox light 1 (= chunk 1, the template)
            if j in LXi and 13 + j in LXi: cons[LXi[13 + j]] = cons[LXi[j]]
        reg, _ = F9.run_state(xprog, B[:k], env.state0(xprog), cons, env.tex, env.N, F9.ALLB)
        v = reg.get((0, r))
        if v is None or not np.isfinite(v[:, c]).all(): return False
        outs = []
        for f in (1.0, 0.5, 0.0):
            s2 = {kk: vv.copy() for kk, vv in reg.items()}; s2[(0, r)][:, c] = v[:, c] * f
            o, _ = F9.run_state(xprog, span, s2, cons, env.tex, env.N, F9.ALLB)
            outs.append(np.stack([o[(0, rr)][:, cc] for rr, cc in wl], 1))
        d1, dh = outs[0] - outs[2], outs[1] - outs[2]
        fin = np.isfinite(d1) & np.isfinite(dh) & np.isfinite(outs[2])          # per lane value (log(0) lanes drop out)
        if fin.mean() < 0.5 or not np.allclose(dh[fin], 0.5 * d1[fin], rtol=1e-4, atol=1e-5): return False
        moved |= bool((np.abs(d1[fin]) > 1e-6).any())
    return moved


def x_L_world(A, seed=4):
    """which world component of L = normalize(p_Lights[13].xyz - pos) each X L lane holds (VM).
    -> ({lane: world component}, [visibility lanes]) - P4.3: a light-pure BRDF lane that is no L component and passes
    x_vis_lane is a scalar visibility (set to 1: the PC radiance carries the PC visibility); otherwise refused as before"""
    xprog, B = A['xprog'], A['B']
    env = F9.Env(seed)
    rpos = next(r for r, j in A['LX'].items() if j == 13)
    P_ = np.broadcast_to(env.consts[rpos], (env.N, 4))[:, :3]
    pos = env.vals[(5, 5)][:, :3]
    d = P_ - pos; Lw = d / np.linalg.norm(d, axis=1, keepdims=True)
    out = {}; cache = {}; vis = []
    for (r, c) in A['Lx']:
        k = A['Lfirst'][(r, c)]
        if k not in cache: cache[k] = env.run(xprog, B[:k], env.state0(xprog), F9.ALLB)[0]
        reg = cache[k]
        v = reg.get((0, r)); v = None if v is None else v[:, c]
        hit = [w for w in range(3) if v is not None and np.allclose(v, Lw[:, w], rtol=1e-3, atol=1e-4)]
        if not hit and VIS_RULE and x_vis_lane(A, r, c, k):
            vis.append((r, c)); continue
        if len(hit) != 1:
            dist = np.linalg.norm(d, axis=1)
            raise Fail('X L lane r%d.%s (read at %d) is not one world component of L: mean %.3f, L %s, dist %.3f'
                       % (r, 'xyzw'[c], k, float(np.mean(v)) if v is not None else 0, np.round(Lw.mean(0), 3), float(dist.mean())))
        out[(r, c)] = hit[0]
    return out, vis


VIS_RULE = os.environ.get('TRUDLC_PERLIGHT_VIS', 'on') != 'off'      # P4.3 switches (2026-11-14)
RAD_RULE = os.environ.get('TRUDLC_PERLIGHT_RAD', 'on') != 'off'
TAIL_RULE = os.environ.get('TRUDLC_PERLIGHT_TAIL', 'on') != 'off'


def x_tail_map(A, acc):
    """acc lane -> (BRDF output lane, colour lane): VM on the chunk-1 tail, one output at a time, colour (1, 2, 4)"""
    xprog, B = A['xprog'], A['B']; N = 8
    rcol = next(r for r, j in A['LX'].items() if j == 16)
    instrs = [B[k] for k in A['tail']]
    res = {}
    for ds in A['DS']:
        st = {}
        for (r, c) in set(A['DS']) | set(A['tail_pure']) | set(acc):
            st.setdefault((0, r), np.zeros((N, 4), np.float32))
        for (r, c) in A['tail_pure']: st[(0, r)][:, c] = 1.0
        st[(0, ds[0])][:, ds[1]] = 1.0
        consts = {r: np.zeros(4, np.float32) for r in range(256)}
        for r, j in A['LX'].items(): consts[r] = np.float32([0.5, 0.5, 0.5, 1.0])
        consts[rcol] = np.float32([1, 2, 4, 8])
        tex = lambda s, c, m: np.ones((c.shape[0], 4), np.float32)
        reg, _ = F9.run_state(xprog, instrs, st, consts, tex, N, F9.ALLB)
        for (r, c) in acc:
            v = reg.get((0, r)); v = 0.0 if v is None else float(v[0, c])
            if abs(v) > 1e-6:
                lane = {1.0: 0, 2.0: 1, 4.0: 2}.get(round(v, 4))
                if lane is None or (r, c) in res: raise Fail('tail probe: acc r%d.%s = %g for output %s' % (r, 'xyzw'[c], v, ds))
                res[(r, c)] = (ds, lane)
    missing = [a for a in acc if a not in res]
    if missing: raise Fail('acc lanes without a BRDF output: %s' % missing)
    return res


# ------------------------------------------------------------------------------------------------ PC side + build
def l_norm_track(i, sub):
    """P4a (13.11., Xbox 2195 DLC 1 water, donor 1008): some base PC light sub-blocks normalise the light vector as
    `dp3 rS.w, rV, rV` / `rsq rS.w, rS.w` / `mul rL.xyz, rV, rS.w` instead of `nrm` (1008 b0: rV = c178 - v4 = light
    position - world position) and overwrite rL later (reflection vector). The build only knew `nrm`, so L stayed
    None ('L None radiance'). Records the first such light-pure normalisation of the sub-block as sub['Lc'] =
    (insert index after it, register); emit_insert uses it only when no nrm / sun-direction L was found (existing
    builds unchanged). The sign / lane choice is proved like every L by the Xbox-lit VM reference (>= 0.999)."""
    if not i.ops or not i.ops[0].isdst or i.ops[0].rtype != sm3asm.RT_TEMP: return
    d = i.ops[0]; s = i.ops[1:]; wl = [c for c in range(4) if d.wm >> c & 1]
    T_ = lambda o, mods=(0,): o.rtype == sm3asm.RT_TEMP and o.smod in mods and not o.rel
    sq = sub.setdefault('sq', {}); rs = sub.setdefault('rs', {})
    if i.op == 'dp3' and len(s) == 2 and T_(s[0]) and T_(s[1]) and s[0].num == s[1].num and (s[0].swz & 0x3f) == (s[1].swz & 0x3f):
        for c in wl: sq[(d.num, c)] = (s[0].num, s[0].swz & 0x3f)
    elif i.op == 'rsq' and len(s) == 1 and T_(s[0], (0, 11)) and (s[0].num, s[0].swz & 3) in sq:
        for c in wl: rs[(d.num, c)] = sq[(s[0].num, s[0].swz & 3)]
    elif i.op == 'mul' and len(s) == 2 and wl == [0, 1, 2] and not (d.mod & 1) and sub.get('Lc') is None:
        for a, b in ((s[0], s[1]), (s[1], s[0])):
            if T_(a) and T_(b) and b.swz in (0x00, 0x55, 0xAA, 0xFF) and rs.get((b.num, b.swz & 3)) == (a.num, a.swz & 0x3f):
                sub['Lc'] = (len(sub['body']), d.num); break


def rad_track(i, sub, flag, gconst, lastw, constl=frozenset()):
    """P4.3 (14.11., donor 975 for Xbox 2057 dungeon water): the PC compiler can fold the visibility into the BRDF
    products instead of forming radiance = visibility x colour (975 slot 0 b0: `cmp_pp r0.x, ..` visibility, then
    `mul_pp r0.x, r0.x, r0.y` (x N.L), `mul_pp r0.z, r0.x, r1.w` (x specular), `mul_pp r2.yzw, r0.x, c182.xxyz` (x
    colour); slot 2 adds the shadow factor `lrp_pp r2.y, shadow, c2.z, 1 - c108.w` the same way) -> 'radiance None'.
    Records, for an impure mul / mad: every light-pure SCALAR temp lane multiplied with a non-light value (a visibility
    factor; keyed by its writer, saved where it is first read: sub['Vf'] = {(reg, lane, writer): insert index}) and the
    light-colour constant read as 3 lanes (sub['Cs']). emit_insert builds radiance = product of the factors x colour only
    when no radiance was found, the colour is unique and there are 1..4 factors (else refused as before); proof: the
    Xbox-lit VM reference of the build and, for the shadow sub-blocks, work/p43_1411/rad_fold_proof.py."""
    if i.op not in ('mul', 'mad') or len(i.ops) < 3: return
    dl = [c for c in range(4) if i.ops[0].wm >> c & 1]
    a, b = i.ops[1], i.ops[2]
    for x, y in ((a, b), (b, a)):
        sw = [(x.swz >> (2 * l)) & 3 for l in range(4)]
        if x.rtype == sm3asm.RT_TEMP and x.smod == 0 and not x.rel and len({sw[l] for l in dl}) == 1 and \
                flag.get((x.num, sw[dl[0]]), {'S'}) <= {'G'} and (x.num, sw[dl[0]]) not in constl and y.rtype == sm3asm.RT_TEMP and \
                any(not flag.get((y.num, (y.swz >> (2 * l)) & 3), {'S'}) <= {'G'} for l in dl):
            key = (x.num, sw[dl[0]], lastw.get((x.num, sw[dl[0]])))
            sub.setdefault('Vf', {}).setdefault(key, len(sub['body']))
        if x.rtype == sm3asm.RT_CONST and x.num in gconst and x.smod == 0 and not x.rel and len(dl) == 3 and \
                len({sw[l] for l in dl}) == 3:
            sub.setdefault('Cs', set()).add('c%d.%s' % (x.num, ''.join('xyzw'[sw[l]] for l in dl)))


def narrow_hoisted(i, lanes):
    """P4a (13.11., Xbox 2188 sluice gate): a componentwise instruction of the Xbox block can write light-free AND
    light-dependent lanes at once (2188 `add r9, r8.xwyz, -r3.wxyz`: r9.x = specular constant, r9.yzw = reflection
    vector 2N(N.L) - L from `dp2add r8.y/z/w` just before it). Hoisting the whole instruction before the block read
    r8.yzw before any write (f4_lint 'r8.w / r8.y read, not written', uninitialised 3) - a translation artefact, the
    Xbox code writes r8.yzw first. The hoisted copy keeps only its light-free lanes; the original stays in the block."""
    if set(writes(i)) == set(lanes): return i
    if i.op not in COMPWISE: raise Fail('hoist: mixed light / light-free lanes in a non-componentwise %s' % sm3asm.fmt_instr(i, 'ps'))
    j = clone(i); j.ops[0].wm = sum(1 << c for r_, c in lanes)
    return j


def hoist_select(A):
    """Test 50h fix. The light-free instructions of the Xbox block are executed once before the new block (H). Moving
    ALL of them there (50a-50c) broke the order for those that stand AFTER light chunk 1 in the Xbox code: the Xbox
    compiler reuses temps, so a later light-free write (e.g. 2685 `mov r1.w, ps` after the last light chunk) moved before
    the block overwrote a lane the chunk-1 BRDF reads (r1.w = specular exponent) -> pow(x, wrong exponent) -> inf / 0
    (the black / white arm blotches). Rule now: hoist the light-free instructions up to the end of chunk 1 (their values
    are the ones the BRDF sees on the Xbox) plus, from after chunk 1, only those needed for a non-accumulator output of
    the block (backward slice); refuse if a hoisted instruction would still write a BRDF input lane after its first read."""
    B, st = A['B'], A['st']
    pre = [k for k in A['hoist'] if k < A['c1e']]
    post = [k for k in A['hoist'] if k >= A['c1e']]
    xin, xout = F9.live_in_out(A['xprog'], A['i0'], A['i1'])
    need = {l for l in xout if l not in A['lit']}
    keep = []
    for k in reversed(post):
        w = set(A['hoist_lanes'][k])          # P4a: only the light-free lanes are hoisted (narrow_hoisted)
        if not (w & need): continue
        keep.append(k); need -= w
        lr = lane_reads(B[k], st)
        for l in w:
            for t, n, ls in lr.get(l[1], []):
                if t == 't': need |= {(n, c) for c in ls}
    H = sorted(pre + keep)
    first_read = {}; wr = set(); Lx = set(A['Lx'])
    for k in A['brdf']:
        for t, n, ls in reads(B[k], st):
            if t == 't':
                for c in ls:
                    if (n, c) not in wr and (n, c) not in Lx: first_read.setdefault((n, c), k)
        wr |= set(writes(B[k]))
    for k in H:
        for l in A['hoist_lanes'][k]:
            if l in first_read and k > first_read[l]:
                raise Fail('hoist hazard: %s writes BRDF input r%d.%s after its read at %d' % (sm3asm.fmt_instr(B[k], 'ps'), l[0], 'xyzw'[l[1]], first_read[l]))
    return H, len(post) - len(keep)


def build(xblob, pdblob, names, log):
    pprog = F9.decode_pc(pdblob); pct = F9.pc_ctab(pdblob)
    preg = {n: ri for n, rs, ri, rc in pct if rs == 3}
    K = F9.Consts(pct)
    samp = F9.xsamp(xblob, names if names is not None else ('globali', preg))
    lg0 = []
    A = xbox_analysis(xblob, K, samp, lg0)
    if TAIL_RULE and A['late'] and not tail_linear(A):          # P4.3: old tail split not linear -> move the slice
        lg0 = ['P4.3 chunk-1 tail not linear in the BRDF outputs (tail_linear)']
        A = xbox_analysis(xblob, K, samp, lg0, tail_move=True)
    log.extend(lg0)
    B, i0, i1 = A['B'], A['i0'], A['i1']
    Hk, ndrop = hoist_select(A)
    log.append('hoist: %d light-free instructions before the block, %d after chunk 1 dropped (not needed outside the light chain)' % (len(Hk), ndrop))
    H = [narrow_hoisted(B[k], A['hoist_lanes'][k]) for k in Hk]
    nn = sum(1 for k in Hk if set(writes(B[k])) != A['hoist_lanes'][k])
    if nn: log.append('hoist: %d mixed instructions narrowed to their light-free lanes' % nn)
    xprog2 =sm3asm.Program(A['xprog'].kind, A['xprog'].major, A['xprog'].minor, F9.header(A['xprog']) + B[:i0] + H + B[i0:])
    j0, j1 = i0 + len(H), i1 + len(H)
    xin, xout = F9.live_in_out(xprog2, j0, j1)
    acc = sorted(l for l in xout if l in A['lit'])
    log.append('X block outputs: acc %s, hoisted %d' % (acc, len(xout) - len(acc)))
    Lmap, Vis = x_L_world(A)
    if Vis: log.append('P4.3 visibility lanes of the Xbox BRDF set to 1 (PC radiance carries the visibility): %s' % ['r%d.%s' % (r, 'xyzw'[c]) for r, c in Vis])
    tmap_x = x_tail_map(A, acc)
    log.append('X tail: %s' % {('r%d.%s' % (a[0], 'xyzw'[a[1]])): ('r%d.%s' % (d[0], 'xyzw'[d[1]]), 'rgb'[c]) for a, (d, c) in tmap_x.items()})
    BP = F9.body(pprog); p0, p1 = F9.pc_light_block(pprog)
    if p0 is None: raise Fail('donor without light block')
    pst = F9.stypes(pprog)
    pin_sem, pv = TLT.inputs_of(pprog)
    pure_v = {v for s, v in pv.items() if s in ((5, 5), (5, 6))}
    gconst = set()
    for n, rs, ri, rc in pct:
        if rs == 2 and PC_LIGHT_NAME.search(n): gconst |= set(range(ri, ri + rc))
    maxp = max([o.num for i in pprog.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP] + [0])
    pdefs_p = {i.ops[0].num for i in F9.header(pprog) if i.op == 'def'}
    xregs = sorted({n for k in A['brdf'] for t, n, ls in reads(B[k], A['st']) if t == 't'} |
                   {l[0] for k in A['brdf'] for l in writes(B[k])} | {r for r, c in A['Lx']})
    written_x = {l[0] for k in A['brdf'] for l in writes(B[k])}; Lregs = {r for r, c in A['Lx']}
    ro = [r for r in xregs if r not in written_x and r not in Lregs]
    rw = [r for r in xregs if r not in ro]
    xm = {r: maxp + 1 + k for k, r in enumerate(rw)}; xm.update({r: 200 + r for r in ro})
    FIXED.clear(); FIXED.update({200 + r: r for r in ro})
    accregs = sorted({r for r, c in acc})
    am = {r: maxp + 1 + len(rw) + k for k, r in enumerate(accregs)}
    lsave = maxp + 1 + len(rw) + len(accregs)
    used_c = {o.num for i in pprog.instrs() + xprog2.instrs() for o in i.ops if o.rtype == sm3asm.RT_CONST}
    cz = next(r for r in range(6, 100) if r not in used_c)
    newB = []
    for r in accregs:
        m = ''.join('xyzw'[c] for rr, c in acc if rr == r)
        newB.append(P('mov r%d.%s, c%d.x' % (am[r], m, cz)))
    flag = {}; skip_else = None; nsub = 0; stack = []; lastw = {}; constl = set()
    # PC pre-block: lanes computed from def literals only (e.g. mov r3.zw, c2) are light-pure; those instructions are
    # copied to the start of the new block (T does not contain the PC pre-block)
    for i in BP[:p0]:
        lr = lane_reads(i, pst)
        for l in writes(i):
            F_ = set()
            for t, n, ls in lr[l[1]]:
                if t in ('v', 's') or (t == 'c' and (n in gconst or n not in pdefs_p)): F_.add('S')
                elif t == 't':
                    for c in ls: F_ |= flag.get((n, c), {'S'})
            flag[l] = {'G'} if not F_ else {'S'}
        if writes(i) and all(flag[l] == {'G'} for l in writes(i)): newB.append(i)
    def emit_insert(sub):
        if not sub['body'] and sub['rad'] is None: return
        L = sub['L']; rad = sub['rad']
        if L is None and sub.get('Lc'):          # P4a: L normalised as rsq + mul (no nrm), fallback only
            idx, r = sub['Lc']
            sub['body'].insert(idx, P('mov r%d.xyz, r%d.xyz' % (lsave, r))); L = sub['L'] = ['r%d.%s' % (lsave, w) for w in 'xyz']
            sub['Lc_used'] = idx
        if rad is None and L is not None and RAD_RULE and not sub.get('Vf') and len(sub.get('Cs', ())) == 1:
            # P4.3: no visibility factor at all (sun without shadow): radiance = the light colour
            creg, clanes = next(iter(sub['Cs'])).split('.')
            rad = sub['rad'] = ['%s.%s' % (creg, w) for w in clanes]
            log.append('P4.3 PC sub-block b%d: radiance = %s (no visibility factor)' % (sub['b'], next(iter(sub['Cs']))))
        if rad is None and L is not None and RAD_RULE and 1 <= len(sub.get('Vf', {})) <= 4 and len(sub.get('Cs', ())) == 1:
            # P4.3: radiance = product of the folded visibility factors x colour, fallback only (rad_track)
            fs = sorted(sub['Vf'].items(), key=lambda t: t[1]); col_ = next(iter(sub['Cs']))
            for j, ((vr, vc, _), idx) in reversed(list(enumerate(fs))):
                if sub.get('Lc_used') is not None and sub['Lc_used'] <= idx: idx += 1
                sub['body'].insert(idx, P('mov r%d.%s, r%d.%s' % (lsave + 1, 'xyzw'[j], vr, 'xyzw'[vc])))
            sub['body'].append(P('mul r%d.xyz, r%d.x, %s' % (lsave + 2, lsave + 1, col_)))
            for j in range(1, len(fs)): sub['body'].append(P('mul r%d.xyz, r%d.xyz, r%d.%s' % (lsave + 2, lsave + 2, lsave + 1, 'xyzw'[j])))
            rad = sub['rad'] = ['r%d.%s' % (lsave + 2, w) for w in 'xyz']
            log.append('P4.3 PC sub-block b%d: radiance = %s x %s (folded visibility)' % (
                sub['b'], ' x '.join('r%d.%s' % (vr, 'xyzw'[vc]) for (vr, vc, _), _ in fs), col_))
        if L is None or rad is None: raise Fail('PC sub-block b%d: L %s radiance %s' % (sub['b'], L, rad))
        newB.extend(sub['body'])
        for (r, c), w in Lmap.items(): newB.append(P('mov r%d.%s, %s' % (xm[r], 'xyzw'[c], L[w])))
        for (r, c) in Vis: newB.append(P('mov r%d.%s, c%d.w' % (xm[r], 'xyzw'[c], cz)))      # P4.3: visibility := 1
        newB.extend(clone(B[k], xm) for k in A['brdf'])
        for (r, c), (ds, lane) in sorted(tmap_x.items()):
            newB.append(P('mad r%d.%s, r%d.%s, %s, r%d.%s' % (am[r], 'xyzw'[c], xm[ds[0]], 'xyzw'[ds[1]], rad[lane], am[r], 'xyzw'[c])))
        sub['body'] = []
    for k in range(p0, p1):
        i = BP[k]
        if skip_else is not None:
            if i.op in ('if', 'ifc'): skip_else += 1
            elif i.op == 'endif':
                if skip_else == 0: skip_else = None; newB.append(i); stack.pop()
                else: skip_else -= 1
            continue
        if i.op == 'if' and i.ops[0].rtype == sm3asm.RT_CONSTBOOL:
            if stack and not stack[-1]['done']: emit_insert(stack[-1]); stack[-1]['done'] = True
            newB.append(i); stack.append(dict(b=i.ops[0].num, body=[], L=None, rad=None, done=False)); nsub += 1; continue
        if i.op in ('if', 'ifc'): raise Fail('non-bool if in the PC light block')
        if i.op == 'else':
            sub = stack[-1]
            if not sub['done']: emit_insert(sub); sub['done'] = True
            skip_else = 0; continue          # PC else = its accumulators zero: ours are zeroed once before the chain
        if i.op == 'endif':
            sub = stack[-1]
            if not sub['done']: emit_insert(sub); sub['done'] = True
            newB.append(i); stack.pop(); continue
        sub = stack[-1]
        rd = reads(i, pst); F = set()
        for t, n, ls in rd:
            if t == 'c' and n in gconst: F.add('G')
            elif t == 's': F.add('G' if 11 <= n <= 15 else 'S')
            elif t == 'v': F.add('G' if n in pure_v else 'S')
            elif t == 't':
                for c in ls: F |= flag.get((n, c), {'S'})
        pure = F <= {'G'}
        if DEBUG and not pure: print('   PC drop b%d: %s   F=%s' % (sub['b'], sm3asm.fmt_instr(i, 'ps'), sorted(F)))
        def pcF(rd_):
            F_ = set()
            for t, n, ls in rd_:
                if t == 'c' and n in gconst: F_.add('G')
                elif t == 's': F_.add('G' if 11 <= n <= 15 else 'S')
                elif t == 'v': F_.add('G' if n in pure_v else 'S')
                elif t == 't':
                    for c in ls: F_ |= flag.get((n, c), {'S'})
            return F_ if F_ else {'G'}
        newfl = {l: pcF(rdl) for l, rdl in ((w_, lane_reads(i, pst)[w_[1]]) for w_ in writes(i))}
        if pure: flag.update(newfl)
        # P4.3: lanes made of plain constants only (no light constant / input / sampler), e.g. 975 sun `mov r6.x, c2.x`
        for l_ in writes(i):
            if pure and all(t == 'c' and n not in gconst or (t == 't' and all((n, c) in constl for c in ls))
                            for t, n, ls in lane_reads(i, pst)[l_[1]]): constl.add(l_)
            else: constl.discard(l_)
        if pure:
            sub['body'].append(i)
            if i.op == 'nrm':
                sub['body'].append(P('mov r%d.xyz, r%d.xyz' % (lsave, i.ops[0].num))); sub['L'] = ['r%d.%s' % (lsave, w) for w in 'xyz']
            else: l_norm_track(i, sub)
            lastw.update({l: k for l in writes(i)})
            continue
        if i.op in ('mad', 'mul') and len(i.ops) >= 3:
            dl = [c for c in range(4) if i.ops[0].wm >> c & 1]
            for o in i.ops[1:3]:
                if o.rtype != sm3asm.RT_TEMP or len(dl) != 3 or o.smod != 0: continue
                sw = [(o.swz >> (2 * l)) & 3 for l in range(4)]
                if all(flag.get((o.num, sw[l]), {'S'}) <= {'G'} for l in dl):
                    # P4.3: a constants-only operand is no radiance (975 / 1657 sun: `mad r5.xyz, r5, r6.x, c209`
                    # with r6.x = c2.x = 2 was taken for the sun colour c212 -> sun term wrong, unseen by the b3 reference)
                    if RAD_RULE and all((o.num, sw[l]) in constl for l in dl): continue
                    sub['rad'] = ['r%d.%s' % (o.num, 'xyzw'[sw[l]]) for l in dl]
        rad_track(i, sub, flag, gconst, lastw, constl)
        flag.update(newfl); lastw.update({l: k for l in writes(i)})
        if sub["L"] is None and i.op == "dp3":
            for o in i.ops[1:]:
                if o.rtype == sm3asm.RT_CONST and o.num in gconst and o.smod == 1 and o.swz == 0xE4:
                    sub['L'] = ['-c%d.%s' % (o.num, w) for w in 'xyz']
    if stack: raise Fail('unbalanced PC block')
    log.append('PC donor block [%d,%d): %d light sub-blocks -> %d instructions' % (p0, p1, nsub, len(newB)))
    hdr = F9.header(pprog) + [P('def c%d, 0, 0, 0, %d' % (cz, 1 if Vis else 0))]      # w = 1 only for P4.3 builds
    pprog2 = sm3asm.Program(pprog.kind, pprog.major, pprog.minor, hdr + BP[:p0] + newB + BP[p1:])
    q0, q1 = p0, p0 + len(newB)
    in_moves = [((xm[r], c), (r, c)) for (r, c) in A['din'] if r not in ro]
    out_moves = [((r, c), (am[r], c)) for (r, c) in acc]
    F9.ZERO_OUTS[:] = []
    return F9.assemble(xprog2, j0, j1, pprog2, q0, q1, in_moves, {}, out_moves, list(A['din']), list(xout), log, {}, ())


# ------------------------------------------------------------------------------------------------ commands
def cmd_xblock(which, xid, slot, outp):
    L = libs(); lib = L[which][xid]
    blob = lib['entries'][lib['slots'][slot]]['blob']
    K = F9.Consts([])
    prog, i0, i1, tr = F9.translate_x(blob, K.fn, lambda n, c: c, F9.xbools(blob))
    inv = {}
    for n, (ri, rc) in K.pfl.items():
        for j in range(rc): inv.setdefault(ri + j, '%s[%d]' % (n, j))
    for (n, j), r in K.extra.items(): inv[r] = '%s[%d]' % (n, j)
    for j in range(32): inv[100 + j] = 'MP[%d]' % j
    sh = XL.parse(blob); bn = F9.bool_names(sh)
    out = ['; light block [%d,%d), bools %s' % (i0, i1, sorted(bn.items()))]
    for k, i in enumerate(F9.body(prog)):
        names = sorted({inv.get(o.num, '?') for o in i.ops if o.rtype == sm3asm.RT_CONST and not o.isdst})
        out.append('%4d %s %s   %s' % (k, '|' if i0 is not None and i0 <= k < i1 else ' ', sm3asm.fmt_instr(i, 'ps'),
                                        ('; ' + ' '.join(names)) if names else ''))
    open(outp, 'w').write('\n'.join(out) + '\n'); print('wrote %s (%d instr, block [%s,%s))' % (outp, len(out) - 1, i0, i1))


def compare2(T, Pb, XP, PP, bools, seed=5):
    """T with the Xbox material params, Pb with the PC ones (the base pair may pack MaterialParams differently);
    same interpolators, textures and all other constants"""
    ex = F9.Env(seed, XP); ep = F9.Env(seed, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    d = np.array(ex.consts[209], np.float32); d[:3] = d[:3] / np.linalg.norm(d[:3]); ex.consts[209] = d; ep.consts[209] = d   # SunLight[1] = unit direction
    a = ex.run(T, F9.body(T), ex.state0(T), bools); b = ep.run(Pb, F9.body(Pb), ep.state0(Pb), bools)
    ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
    if ca is None or cb is None: return 0.0
    ok = np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])
    return float(ok.mean())


def cmd_ldiag(xb, pb, slot, bit):
    L = libs(); X, PL = L['X'], L['P']
    xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']; pbblob = PL[pb]['entries'][PL[pb]['slots'][slot]]['blob']
    mt = f9_common.material_pairs(xb, pb); XP, PP = mt[0][2], mt[0][3]
    T = build(xblob, pbblob, {n: ri for n, rs, ri, rc in F9.pc_ctab(pbblob) if rs == 3}, [])
    Pb = F9.decode_pc(pbblob); open('work/rebuild/test50a_work/pl/T_%d_%d_s%d.asm' % (xb, pb, slot), 'w').write(sm3asm.format_program(T))
    ex = F9.Env(5, XP); ep = F9.Env(5, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    d = np.array(ex.consts[209], np.float32); d[:3] /= np.linalg.norm(d[:3]); ex.consts[209] = d; ep.consts[209] = d
    for bl in ({}, {bit: True}):
        a = ex.run(T, F9.body(T), ex.state0(T), bl)[0][(sm3asm.RT_COLOROUT, 0)]
        b = ep.run(Pb, F9.body(Pb), ep.state0(Pb), bl)[0][(sm3asm.RT_COLOROUT, 0)]
        if not bl: a0, b0 = a, b; continue
        da, db = a - a0, b - b0
        bad = ~np.isclose(a, b, **F9.TOL).all(axis=1)
        print('bit %d: light term T mean %s  Pb mean %s; bad %d / %d; on bad samples T %s Pb %s'
              % (bit, np.round(da.mean(0), 4), np.round(db.mean(0), 4), bad.sum(), len(bad), np.round(da[bad][:3], 3).tolist(), np.round(db[bad][:3], 3).tolist()))


def cmd_oracle(specs, slots):
    L = libs(); X, PL = L['X'], L['P']
    for spec in specs:
        ids = [int(x) for x in spec.split('/')]
        xb, pb = ids[0], ids[1]; pd = ids[2] if len(ids) > 2 else pb
        mt = f9_common.material_pairs(xb, pb)
        if not mt: print('%d/%d: no base material' % (xb, pb)); continue
        for slot in slots:
            if PL[pb]['slots'][slot] == 0xffffffff or PL[pd]['slots'][slot] == 0xffffffff: continue
            xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']
            pbblob = PL[pb]['entries'][PL[pb]['slots'][slot]]['blob']; pdblob = PL[pd]['entries'][PL[pd]['slots'][slot]]['blob']
            xnames = {n: ri for n, rs, ri, rc in F9.pc_ctab(pbblob) if rs == 3}
            log = []
            try:
                T = build(xblob, pdblob, xnames, log)
                Pb = F9.decode_pc(pbblob)
                res = {lab: compare2(T, Pb, mt[0][2], mt[0][3], bl) for lab, bl in
                       (('off', {}), ('on', F9.ALLB), ('mixed', {0: True, 3: True, 6: True}))}
                res.update({'b%d' % b: compare2(T, Pb, mt[0][2], mt[0][3], {b: True}) for b in (0, 3, 6)})
                res['offX'] = TLT.lights_off(T, xblob, mt[0][2], xnames)
                print('%d/%d donor %d slot %d: %s  (%d instr)' % (xb, pb, pd, slot, ' '.join('%s=%.3f' % kv for kv in res.items()), len(F9.body(T))), flush=True)
            except (Fail, F9.Fail) as e:
                print('%d/%d donor %d slot %d: FAIL %s' % (xb, pb, pd, slot, e), flush=True)
            for l in log: print('     ' + l[:300])


def cmd_build(pcf, xf, out, mesh, ids, donor, only_mats=None):
    os.makedirs(out, exist_ok=True)
    _, Pd_ = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    pl, xl = TLT.mesh_mats(Pd_, mesh, 'le'), TLT.mesh_mats(Xd, mesh, 'be')
    L = libs(); PL = L['P']
    pp = os.path.join(out, 'plan.json'); plan = json.load(open(pp)) if os.path.exists(pp) else {}
    for xid in ids:
        lib = TLT.tu_lib(xid)
        mats = [(pm, xm) for pm, xm in zip(pl, xl) if struct.unpack_from('>4I', Xd[(10, xm)].data, 0x28)[2] == xid]
        # 50l: --mats restricts the build (and so the material that apply re-points) to the given PC materials - the users
        # of one Xbox lib can differ in which textures are DXN (2644: 26357 has DXN on PC s1 / s2, 26360 only on s1), and
        # the DXN handling is compiled into the shader, so they need one lib each
        if only_mats: mats = [m for m in mats if m[0] in only_mats]
        if not mats: raise SystemExit('d%d: no material of mesh %d uses it%s' % (xid, mesh, ' (--mats %s)' % sorted(only_mats) if only_mats else ''))
        # the materials of one build must agree on the sampler map and the DXN registers (both are compiled in)
        def recs(pm, xm):
            # ALL records, per-instance ones paired by kind (TLT.sampler_map; 08.11.: they were missing)
            r_ = TLT.sampler_map(Pd_[(10, pm)], Xd[(10, xm)], Xd)
            if r_ is None: raise SystemExit('d%d: material %d: PC / Xbox texture records do not pair' % (xid, pm))
            return r_['smap'], r_['dxn']
        r0 = recs(*mats[0])
        for m in mats[1:]:
            if recs(*m) != r0: raise SystemExit('d%d: materials %s and %s differ in sampler map / DXN registers %s vs %s - build them separately (--mats)' % (xid, mats[0][0], m[0], r0, recs(*m)))
        pm0, xm0 = mats[0]
        smap, dxn = r0
        names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
        XP = TLT.mparams(Xd[(10, xm0)], 'be')
        TLT.EXTRA_OPTS.clear(); TLT.EXTRA_OPTS.update({'dxn': dxn, 'dxn_full': dxn} if dxn else {})
        print('   Xbox DXN textures on PC registers %s (translator: y from alpha, z = 0, w = 1)' % sorted(dxn), flush=True)
        pd = donor or struct.unpack_from('<4I', Pd_[(10, pm0)].data, 0x28)[2]
        slots = PL[pd]['slots']
        print('== d%d materials %s donor PC %d, samplers %s' % (xid, mats, pd, smap), flush=True)
        ent = dict(donor_xs=0, donor_pd=pd, method='perlight', mats=mats, sampler_map={str(k): v for k, v in smap.items()}, slots={})
        ok = True
        for k in range(8):
            src = k if slots[k] != 0xffffffff else (k & ~1)
            xblob = lib['entries'][lib['slots'][k & 1]]['blob']
            log = []
            try:
                T = build(xblob, PL[pd]['entries'][slots[src]]['blob'], names, log)
            except (Fail, F9.Fail) as e:
                print('   slot %d: FAIL %s' % (k, e)); ok = False; break
            bc, n, off, probs = TLT.checks(T, xblob, XP, names)
            print('   slot %d (Xbox %d, Pd slot %d): %d instr, lights-off %.3f %s' % (k, k & 1, src, n, off, probs or 'ok'), flush=True)
            for l in log: print('      ' + l[:250])
            if probs: ok = False; break
            fn = os.path.join(out, '%d_s%d' % (xid, k))
            open(fn + '.bin', 'wb').write(bc); open(fn + '.asm', 'w').write(sm3asm.format_program(T))
            ent['slots'][str(k)] = dict(file=os.path.basename(fn) + '.bin', md5=hashlib.md5(bc).hexdigest(), src_pd_slot=src, instr=n, lights_off=off, log=log)
        plan[str(xid)] = ent if ok else dict(error='perlight build failed')
        json.dump(plan, open(pp, 'w'), indent=1, default=str)


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'xblock': cmd_xblock(a[1], int(a[2]), int(a[3]), a[4]); return
    a = [x for x in a if x != '--debug']
    if a[0] == 'ldiag': cmd_ldiag(*[int(x) for x in a[1:5]]); return
    if a[0] == 'oracle-random':
        import random; random.seed(int(a[2])); pairs = F9.lit_pairs(); smp = random.sample(pairs, int(a[1]))
        cmd_oracle(['%d/%d' % p for p in smp], (2,)); return
    if a[0] == 'oracle':
        sl = (2, 0, 4, 6, 1)
        if '--slots' in a: k = a.index('--slots'); sl = tuple(int(x) for x in a[k + 1].split(',')); a = a[:k] + a[k + 2:]
        cmd_oracle(a[1:], sl); return
    if a[0] == 'build':
        mesh = int(a[a.index('--mesh') + 1]); ids = [int(x) for x in a[a.index('--libs') + 1].split(',')]
        donor = int(a[a.index('--donor') + 1]) if '--donor' in a else None
        only = {int(x) for x in a[a.index('--mats') + 1].split(',')} if '--mats' in a else None
        cmd_build(a[1], a[2], a[3], mesh, ids, donor, only); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
