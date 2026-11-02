"""Test 50h (doppelganger arms / gloves): an Xbox-lit reference for per-light PC shaders.

The per-light builds (tools/tu_perlight.py) were checked only with the lights OFF against the Xbox translation (the light
part was proven on base pairs, not on the TU libs themselves). Here the Xbox shader is translated WITH its own Xbox light
chain (xenos2sm3, p_Lights in free registers, LightEnabled on, p_ShadowEnabled / p_ProjectionEnabled off) and lit by ONE
light; the PC shader is lit by the equivalent PC non-shadow light (bool b3, NonShadowLights[0..4]); both run in the SM3
VM on the same random inputs / constants (f9 Env) and the colour outputs are compared.

Constant correspondence used (Xbox chunk 0 vs PC b3 sub-block, Befund-Felsrinne 50a "Per-light route"):
  p_Lights[0].xyz = NonShadowLights[0].xyz (position)      p_Lights[1].xyz = NonShadowLights[1].xyz (direction)
  p_Lights[2].x / .y = NonShadowLights[2].x / .z (attenuation u = dist * a + b)
  p_Lights[0].w = NonShadowLights[2].w with NonShadowLights[2].y = 0 (attenuation v)
  p_Lights[2].w / .z = NonShadowLights[3].x / .y (cone scale / bias)   p_Lights[1].w = NonShadowLights[3].z (range)
  p_Lights[3] = NonShadowLights[4] (colour); lights 1..6 of the Xbox: colour 0, far away.
It is validated first on a BASE pair (Xbox lib vs its real PC twin): if Nixxes' PC lib reproduces the Xbox one under this
correspondence, the reference is trustworthy for the TU libs.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/perlight_xref.py pair XB PB [--slots 2,0]            base pair: Xbox XB lit vs real PC PB
  ../bin/pyt -t 900 tools/perlight_xref.py tu PC.drm XBOX.drm MAT [--slots 2,0] [--lib PCLIB]
      the material's TU Xbox lib (pass 2 of the Xbox material) lit vs the PC lib the PC material uses (or --lib)
  options: --bin DIR (PC entries from DIR/<xid>_s<slot>.bin of a tu_perlight build instead of the DRM lib), --trace, --seed N (default 5), --range R (p_Lights[1].w, default -100 = always in range), --dump (per-sample rows)
"""
import sys, os, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs
import f9_common
import shaderlib as SL

XBOOLS = {'p_ShadowEnabled': 0, 'p_ProjectionEnabled': 0, 'LightEnabled': 1}
PC_NSL = 193          # NonShadowLights[0] (PC CTAB of the base libs, see ps_swatch consts)
TRACE = False
BINDIR = None


def light(rng, rangew):
    P = np.float32([0.5, 0.5, 0.5]) + rng.uniform(-3, 3, 3).astype(np.float32)
    D = rng.normal(size=3).astype(np.float32); D /= np.linalg.norm(D)
    a, b, v = 0.15, 0.05, 0.5
    w, z = 0.7, 0.4
    col = np.float32([0.9, 0.6, 0.3])
    return P, D, (a, b, v), (w, z), rangew, col


def set_x(consts, LX, L):
    P, D, (a, b, v), (w, z), rw, col = L
    for k in range(7):
        base = 13 * k
        for j in range(13):
            if (base + j) in LX: consts[LX[base + j]] = np.float32([0.3, 0.2, 0.1, 0.5])
        far = np.float32([1e3 * (k + 1), 1e3, 1e3, v])
        if k == 0:
            vals = {0: np.float32([P[0], P[1], P[2], v]), 1: np.float32([D[0], D[1], D[2], rw]), 2: np.float32([a, b, z, w]), 3: np.float32([col[0], col[1], col[2], 0])}
        else:
            vals = {0: far, 1: np.float32([0, 0, 1, rw]), 2: np.float32([a, b, z, w]), 3: np.float32([0, 0, 0, 0])}
        for j, val in vals.items():
            if (base + j) in LX: consts[LX[base + j]] = val


def set_pc(consts, L):
    P, D, (a, b, v), (w, z), rw, col = L
    consts[PC_NSL] = np.float32([P[0], P[1], P[2], 0]); consts[PC_NSL + 1] = np.float32([D[0], D[1], D[2], 0])
    consts[PC_NSL + 2] = np.float32([a, 0, b, v]); consts[PC_NSL + 3] = np.float32([w, z, rw, 0])
    consts[PC_NSL + 4] = np.float32([col[0], col[1], col[2], 0])


def xref_translate(xblob, samp, opts):
    K = F9.Consts([])
    prog, i0, i1, tr = F9.translate_x(xblob, K.fn, samp, XBOOLS, opts=opts)
    LX = {j: r for (n, j), r in K.extra.items() if n == 'p_Lights'}
    return prog, LX


def compare(R, LX, T, XP, PP, seed, rangew, dump=False, tag=''):
    rng = np.random.RandomState(seed + 100)
    L = light(rng, rangew)
    ex = F9.Env(seed, XP); ep = F9.Env(seed, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    # a sane world: position inputs near the origin, unit-ish tangent frame (texcoord2..4 rows), camera away from the surface
    res = {}
    for lab, on in (('off', False), ('on', True)):
        cx = dict(ex.consts); cp = dict(ep.consts)
        if on: set_x(cx, LX, L); set_pc(cp, L)
        else:
            set_x(cx, LX, (L[0], L[1], L[2], L[3], L[4], np.float32([0, 0, 0])))
            set_pc(cp, (L[0], L[1], L[2], L[3], L[4], np.float32([0, 0, 0])))
        a = F9.run_state(R, F9.body(R), ex.state0(R), cx, ex.tex, ex.N, {})
        b = F9.run_state(T, F9.body(T), ep.state0(T), cp, ep.tex, ep.N, {3: True} if on else {})
        res[lab] = (a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0)), a[1], b[1])
    out = {}
    for lab, (ca, cb, ka, kb) in res.items():
        if ca is None or cb is None: out[lab] = None; continue
        ok = np.isclose(ca, cb, **F9.TOL).all(axis=1) & (ka == kb) | (ka & kb)
        out[lab] = float(ok.mean())
    (a0, b0, _, _), (a1, b1, _, _) = res['off'], res['on']
    dx, dp = a1[:, :3] - a0[:, :3], b1[:, :3] - b0[:, :3]
    fin = np.isfinite(dx).all(1) & np.isfinite(dp).all(1)
    corr = [float(np.corrcoef(dx[fin, c], dp[fin, c])[0, 1]) if fin.sum() > 2 and dx[fin, c].std() > 0 and dp[fin, c].std() > 0 else float('nan') for c in range(3)]
    print('%s off=%.3f on=%.3f | light term Xbox mean %s min %s max %s | PC mean %s min %s max %s | corr %s | non-finite Xbox %d PC %d'
          % (tag, out['off'] or 0, out['on'] or 0, np.round(np.nanmean(dx, 0), 4), np.round(np.nanmin(dx, 0), 3), np.round(np.nanmax(dx, 0), 3),
             np.round(np.nanmean(dp, 0), 4), np.round(np.nanmin(dp, 0), 3), np.round(np.nanmax(dp, 0), 3), np.round(corr, 3),
             int((~np.isfinite(a1)).any(1).sum()), int((~np.isfinite(b1)).any(1).sum())), flush=True)
    if dump:
        for k in range(8): print('   sample %d: Xbox light %s  PC light %s' % (k, np.round(dx[k], 4), np.round(dp[k], 4)))
    return out


def trace_big(T, XP, PP, seed, rangew, limit=1e6, nshow=12):
    """first instructions of T (lit by the one PC light) that write |value| > limit or non-finite values"""
    import sm3vm
    rng = np.random.RandomState(seed + 100); L = light(rng, rangew)
    ex = F9.Env(seed, XP); ep = F9.Env(seed, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    cp = dict(ep.consts); set_pc(cp, L)
    body = F9.body(T); idx = {id(i): n for n, i in enumerate(body)}; hits = []
    class TV(sm3vm.VM):
        def _alu(self, it, s):
            self._cur = it
            return sm3vm.VM._alu(self, it, s)
        def write(self, o, val, mask):
            v = np.asarray(val)
            bad = ~np.isfinite(v) | (np.abs(v) > limit)
            if bad.any() and len(hits) < nshow:
                it = getattr(self, '_cur', None)
                hits.append('%s: %s  (%d samples)' % (idx.get(id(it), '?'), sm3asm.fmt_instr(it, 'ps') if it is not None else '?', int(bad.any(1).sum()) if v.ndim == 2 else -1))
            return sm3vm.VM.write(self, o, val, mask)
    vm = TV(F9.sub_program(T, body), ep.N, {k: v.copy() for k, v in ep.state0(T).items()}, cp, ep.tex, {3: True})
    vm.exec()
    for h in hits: print('   ' + h)


def cmd_pair(xb, pb, slots, seed, rangew, dump):
    Lb = libs(); X, P = Lb['X'], Lb['P']
    mt = f9_common.material_pairs(xb, pb)
    if not mt: raise SystemExit('no base material pair %d/%d' % (xb, pb))
    for slot in slots:
        xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']; pblob = P[pb]['entries'][P[pb]['slots'][slot]]['blob']
        names = {n: ri for n, rs, ri, rc in F9.pc_ctab(pblob) if rs == 3}
        R, LX = xref_translate(xblob, F9.xsamp(xblob, names), {})
        T = F9.decode_pc(pblob)
        compare(R, LX, T, mt[0][2], mt[0][3], seed, rangew, dump, '%d/%d slot %d:' % (xb, pb, slot))


def cmd_tu(pcf, xf, mat, slots, seed, rangew, dump, lib_override):
    _, Pd = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    pm, xm = Pd[(10, mat)], Xd[(10, mat)]
    xid = struct.unpack_from('>4I', xm.data, 0x28)[2]
    plib = lib_override or struct.unpack_from('<4I', pm.data, 0x28)[2]
    lib = TLT.tu_lib(xid)
    pr, xr = TLT.records(pm, 'le'), TLT.records(xm, 'be')
    smap = {x[3]: p[3] for p, x in zip(pr, xr)}
    names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
    dxn = {p[3] for p, x in zip(pr, xr) if (5, x[0]) in Xd and struct.unpack_from('>I', Xd[(5, x[0])].data, 4)[0] & 0x3f == 0x31}
    opts = {'dxn': dxn, 'dxn_full': dxn} if dxn else {}
    XP = TLT.mparams(xm, 'be'); PP = TLT.mparams(pm, 'le')
    PL = SL.parse(Pd[(9, plib)].data, 'le')
    print('material %d: Xbox lib %d, PC lib %s, sampler map %s, DXN on PC %s' % (mat, xid, plib, smap, sorted(dxn)))
    for slot in slots:
        if BINDIR:
            T = F9.decode_pc(open(os.path.join(BINDIR, "%d_s%d.bin" % (xid, slot)), "rb").read()); plib = "bin"
        else:
            o = PL["slots"][slot]
            if o == 0xffffffff: print("slot %d empty" % slot); continue
            T = F9.decode_pc(PL["entries"][o]["blob"])
        xblob = lib['entries'][lib['slots'][slot & 1]]['blob']
        R, LX = xref_translate(xblob, F9.xsamp(xblob, names), opts)
        compare(R, LX, T, XP, PP, seed, rangew, dump, 'mat %d Xbox %d / PC %s slot %d:' % (mat, xid, plib, slot))
        if TRACE: trace_big(T, XP, PP, seed, rangew)


def main(a):
    if not a: sys.exit(__doc__)
    def opt(k, d, f=int):
        if k in a:
            j = a.index(k); v = f(a[j + 1]); del a[j:j + 2]; return v
        return d
    slots = tuple(int(x) for x in opt('--slots', '2,0', str).split(','))
    global BINDIR
    BINDIR = opt('--bin', None, str)
    seed = opt('--seed', 5); rangew = opt('--range', -100.0, float); lib = opt('--lib', None)
    global TRACE
    TRACE = '--trace' in a
    dump = '--dump' in a; a = [x for x in a if x not in ('--dump', '--trace')]
    if a[0] == 'pair': cmd_pair(int(a[1]), int(a[2]), slots, seed, rangew, dump)
    elif a[0] == 'tu': cmd_tu(a[1], a[2], int(a[3]), slots, seed, rangew, dump, lib)
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
