"""Night 03.11. shader work (test 50l): rebuild of the per-light / transplanted TU pixel shaders with the 50h-fixed
tools/tu_perlight.py, and the translation of the thrall / enemy materials with the same method. Read-only helpers;
the builds themselves are done by tools/tu_perlight.py build + tools/tu_light_transplant.py pack / apply.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/tu_shader_night.py inv PC.drm XBOX.drm [--all]
      materials of the pair (paired by every mesh's material list, Xbox order = PC order): ids, Xbox tuple
      (pass 0 / 1 / 2 PS, VS) with the DLC shader-map class of each lib (A / B exact, C1-C3 / D untranslated),
      PC tuple, pass-2 Xbox lib: lit (p_Lights / LightEnabled) or not, Xbox samplers -> PC registers, DXN registers;
      --all also lists materials whose libs are all exact
  ../bin/pyt -t 900 tools/tu_shader_night.py xref PC.drm XBOX.drm MAT [--slots 0,1,..] [--lib ID | --bin DIR]
      [--seed N] [--range R] [--no-game-dxn]
      tools/perlight_xref.py 'tu' with game-like DXN textures: on the PC our converted DXN maps are DXT5 with
      R = x, G = 1, B = 0, A = y (Xbox DXN = (x, y, 0, 1)), so the samplers of DXN textures return (x, 1, 0, y) in the
      VM (both programs). Without this the VM's random G / B make shaders translated with xenos2sm3's name rule
      (`*_Normal_*`: y = A * G) and with the explicit `dxn` option (y = A, z = 0, w = 1) differ where the game cannot.
      The Xbox reference is translated with the explicit DXN option (= the Xbox values (x, y, 0, 1)).
  ../bin/pyt -t 900 tools/tu_shader_night.py vmcmp PC.drm XBOX.drm MAT BUILDDIR [--slots ..]
      the material's current PC lib vs a new build, PC light bools none / b0 / b3 / b6 / mixed / all (old vs new)
  ../bin/pyt -t 900 tools/tu_shader_night.py twins PCID[,PCID]      base Xbox twin of each PC lib (shader_x2p) as XB/PB
  ../bin/pyt -t 900 tools/tu_shader_night.py lit XID[,XID]
      DLC Xbox lib: per slot light block [i0, i1), light chunk count, p_Lights / LightEnabled bools (translatability
      for tu_perlight)
"""
import sys, os, struct, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs
import perlight_xref as PX
import shaderlib as SL

ROOT = os.path.normpath(os.path.join(HERE, '..'))
SMAP = {int(k): v for k, v in json.load(open(os.path.join(ROOT, 'work', 'render', 'dlc_shader_map.json'))).items()}


def cls(lib):
    if lib in (0, 0xffffffff): return '-'
    v = SMAP.get(lib)
    return v['cls'] if v else 'base'


def mats_of(P, X):
    """[(pc mat, xbox mat, mesh)] paired by each mesh's material list (order); first occurrence wins"""
    out = []; seen = set()
    for (t, mid), s in sorted(X.items()):
        if t != 12 or (12, mid) not in P: continue
        try:
            xl = TLT.mesh_mats(X, mid, 'be'); pl = TLT.mesh_mats(P, mid, 'le')
        except Exception:
            continue
        if len(xl) != len(pl): print('mesh %d: %d Xbox / %d PC materials - skipped' % (mid, len(xl), len(pl))); continue
        for pm, xm in zip(pl, xl):
            if (pm, xm) in seen: continue
            seen.add((pm, xm)); out.append((pm, xm, mid))
    # materials no paired mesh lists (other models / effects of the object): paired by id (DLC ids are kept on PC)
    done = {xm for pm, xm, m in out}
    for (t, xid), s in sorted(X.items()):
        if t == 10 and xid not in done and (10, xid) in P: out.append((xid, xid, 0))
    return out


def lib_lit(xid):
    L = libs()
    if xid not in L['D']: return None
    lib = L['D'][xid]
    blob = lib['entries'][lib['slots'][0]]['blob'] if lib['slots'][0] != 0xffffffff else None
    if blob is None: return None
    sh = XL.parse(blob)
    names = {c['name'] for c in sh.ctab}
    return 'p_Lights' in names, sorted(n for n in names if 'Light' in n or 'Shadow' in n)


def cmd_inv(pcf, xf, all_):
    _, P = TLT.load(pcf, 'le'); _, X = TLT.load(xf, 'be')
    rows = mats_of(P, X)
    print('%s: %d material pairs over the meshes' % (os.path.basename(pcf), len(rows)))
    for pm, xm, mesh in rows:
        if (10, xm) not in X or (10, pm) not in P: continue
        xt = struct.unpack_from('>4I', X[(10, xm)].data, 0x28); pt = struct.unpack_from('<4I', P[(10, pm)].data, 0x28)
        cl = [cls(v) for v in xt]
        untr = [c for c in cl if c in ('C1', 'C2', 'C3', 'D')]
        if not untr and not all_: continue
        xr, pr = TLT.records(X[(10, xm)], 'be'), TLT.records(P[(10, pm)], 'le')
        smap = {x[3]: p[3] for p, x in zip(pr, xr)}
        dxn = sorted({p[3] for p, x in zip(pr, xr) if (5, x[0]) in X and struct.unpack_from('>I', X[(5, x[0])].data, 4)[0] & 0x3f == 0x31})
        lit = lib_lit(xt[2])
        np_x = len(TLT.mparams(X[(10, xm)], 'be')); np_p = len(TLT.mparams(P[(10, pm)], 'le'))
        print('mat %5d (Xbox %5d) mesh %5d  Xbox %s  PC %s  p2 lit %s  MP %d/%d  samp %s  DXN %s  tex %s' % (
            pm, xm, mesh, ' '.join('%d%s' % (v, '' if c in ('A', 'B', '-', 'base') else '[%s]' % c) for v, c in zip(xt, cl)),
            ' '.join(str(v) for v in pt), None if lit is None else ('yes' if lit[0] else 'no'), np_x, np_p, smap, dxn,
            [x[0] for x in xr]))


def cmd_lit(ids):
    L = libs()
    for xid in ids:
        lib = L['D'].get(xid)
        if lib is None: print('d%d: not a DLC lib' % xid); continue
        for k in (0, 1):
            if lib['slots'][k] == 0xffffffff: print('d%d slot %d empty' % (xid, k)); continue
            blob = lib['entries'][lib['slots'][k]]['blob']
            K = F9.Consts([])
            try:
                prog, i0, i1, tr = F9.translate_x(blob, K.fn, lambda n, c: c, F9.xbools(blob))
            except Exception as e:
                print('d%d slot %d: translate failed %s' % (xid, k, str(e)[:120])); continue
            LX = sorted(j for (n, j), r in K.extra.items() if n == 'p_Lights')
            print('d%d slot %d: %d instr, light block %s, p_Lights entries %d (chunks %s), bools %s' % (
                xid, k, len(F9.body(prog)), (i0, i1), len(LX), sorted({j // 13 for j in LX}), sorted(F9.xbools(blob).items())))


# ---------------------------------------------------------------------------------------------------- xref
def game_dxn_tex(tex, dxn):
    def f(smp, coords, mode):
        out = tex(smp, coords, mode)
        if smp in dxn:
            out = out.copy(); out[:, 1] = 1.0; out[:, 2] = 0.0
        return out
    return f


def compare(R, LX, T, XP, PP, seed, rangew, dxn, tag):
    rng = np.random.RandomState(seed + 100)
    Lt = PX.light(rng, rangew)
    ex = F9.Env(seed, XP); ep = F9.Env(seed, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    tx, tp = game_dxn_tex(ex.tex, dxn), game_dxn_tex(ep.tex, dxn)
    res = {}
    for lab, on in (('off', False), ('on', True)):
        cx = dict(ex.consts); cp = dict(ep.consts)
        Lc = Lt if on else (Lt[0], Lt[1], Lt[2], Lt[3], Lt[4], np.float32([0, 0, 0]))
        PX.set_x(cx, LX, Lc); PX.set_pc(cp, Lc)
        a = F9.run_state(R, F9.body(R), ex.state0(R), cx, tx, ex.N, {})
        b = F9.run_state(T, F9.body(T), ep.state0(T), cp, tp, ep.N, {3: True} if on else {})
        res[lab] = (a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0)), a[1], b[1])
    out = {}
    for lab, (ca, cb, ka, kb) in res.items():
        if ca is None or cb is None: out[lab] = 0.0; continue
        ok = np.isclose(ca, cb, **F9.TOL).all(axis=1) & (ka == kb) | (ka & kb)
        out[lab] = float(ok.mean())
    (a0, b0, _, _), (a1, b1, _, _) = res['off'], res['on']
    dx, dp = a1[:, :3] - a0[:, :3], b1[:, :3] - b0[:, :3]
    fin = np.isfinite(dx).all(1) & np.isfinite(dp).all(1)
    corr = [float(np.corrcoef(dx[fin, c], dp[fin, c])[0, 1]) if fin.sum() > 2 and dx[fin, c].std() > 0 and dp[fin, c].std() > 0 else float('nan') for c in range(3)]
    print('%s off=%.3f on=%.3f | light corr %s | colour mean Xbox %s PC %s | non-finite Xbox %d PC %d' % (
        tag, out['off'], out['on'], np.round(corr, 3), np.round(np.nanmean(a1[:, :3], 0), 3), np.round(np.nanmean(b1[:, :3], 0), 3),
        int((~np.isfinite(a1)).any(1).sum()), int((~np.isfinite(b1)).any(1).sum())), flush=True)
    return out


def cmd_xref(pcf, xf, mat, slots, seed, rangew, lib_override, bindir, gamedxn):
    _, Pd = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    pm, xm = Pd[(10, mat)], Xd[(10, mat)]
    xid = struct.unpack_from('>4I', xm.data, 0x28)[2]
    plib = lib_override or struct.unpack_from('<4I', pm.data, 0x28)[2]
    lib = TLT.tu_lib(xid)
    rm = TLT.sampler_map(pm, xm, Xd)      # ALL records (08.11.: per-instance ones were missing)
    if rm is None: raise SystemExit('material %d: PC / Xbox texture records do not pair' % mat)
    smap, dxn = rm['smap'], rm['dxn']
    names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
    opts = {'dxn': dxn, 'dxn_full': dxn} if dxn else {}
    XP = TLT.mparams(xm, 'be'); PP = TLT.mparams(pm, 'le')
    if bindir: PP = XP   # a new build is applied with the PC MaterialParams := the Xbox ones (tu_light_transplant apply)
    PLb = None if bindir else SL.parse(Pd[(9, plib)].data, 'le')
    print('material %d: Xbox lib %d, PC lib %s, sampler map %s, DXN on PC %s, game-like DXN textures %s' % (
        mat, xid, 'bin ' + bindir if bindir else plib, smap, sorted(dxn), gamedxn))
    res = {}
    for slot in slots:
        if bindir:
            p = os.path.join(bindir, '%d_s%d.bin' % (xid, slot))
            if not os.path.exists(p): print('slot %d: no %s' % (slot, p)); continue
            T = F9.decode_pc(open(p, 'rb').read())
        else:
            o = PLb['slots'][slot]
            if o == 0xffffffff: print('slot %d empty' % slot); continue
            T = F9.decode_pc(PLb['entries'][o]['blob'])
        xblob = lib['entries'][lib['slots'][slot & 1]]['blob']
        R, LX = PX.xref_translate(xblob, F9.xsamp(xblob, names), opts)
        res[slot] = compare(R, LX, T, XP, PP, seed, rangew, dxn if gamedxn else set(), 'mat %d Xbox %d / PC %s slot %d:' % (mat, xid, 'bin' if bindir else plib, slot))
    if res:
        print('SUMMARY mat %d PC %s: off min %.3f, on min %.3f over %d slots' % (
            mat, 'bin' if bindir else plib, min(v['off'] for v in res.values()), min(v['on'] for v in res.values()), len(res)))


def cmd_vmcmp(pcf, xf, mat, bindir, slots, seed):
    """the material's current PC lib against a new build (DIR/<xid>_s<k>.bin) with every PC light bool combination
    used by the oracles: none, b0 (shadow light), b3 (non-shadow light), b6 (sun), mixed, all; same random inputs /
    constants / textures (game-like DXN), the PC material's params for both"""
    _, Pd = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    pm, xm = Pd[(10, mat)], Xd[(10, mat)]
    xid = struct.unpack_from('>4I', xm.data, 0x28)[2]; plib = struct.unpack_from('<4I', pm.data, 0x28)[2]
    pr, xr = TLT.records(pm, 'le'), TLT.records(xm, 'be')
    dxn = {p[3] for p, x in zip(pr, xr) if (5, x[0]) in Xd and struct.unpack_from('>I', Xd[(5, x[0])].data, 4)[0] & 0x3f == 0x31}
    PP = TLT.mparams(pm, 'le'); PLb = SL.parse(Pd[(9, plib)].data, 'le')
    worst = 1.0
    for slot in slots:
        o = PLb['slots'][slot]
        if o == 0xffffffff: continue
        A = F9.decode_pc(PLb['entries'][o]['blob']); B = F9.decode_pc(open(os.path.join(bindir, '%d_s%d.bin' % (xid, slot)), 'rb').read())
        env = F9.Env(seed, PP)
        d = np.array(env.consts[209], np.float32); d[:3] /= np.linalg.norm(d[:3]); env.consts[209] = d
        tx = game_dxn_tex(env.tex, dxn); line = []
        for lab, bl in (('none', {}), ('b0', {0: True}), ('b3', {3: True}), ('b6', {6: True}), ('mixed', {0: True, 3: True, 6: True}), ('all', F9.ALLB)):
            a = F9.run_state(A, F9.body(A), env.state0(A), env.consts, tx, env.N, bl); b = F9.run_state(B, F9.body(B), env.state0(B), env.consts, tx, env.N, bl)
            ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
            v = 0.0 if ca is None or cb is None else float((np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])).mean())
            worst = min(worst, v); line.append('%s=%.3f' % (lab, v))
        print('mat %d slot %d: PC %d vs new %s  %s  (instr %d -> %d)' % (mat, slot, plib, bindir, ' '.join(line), len(F9.body(A)), len(F9.body(B))), flush=True)
    print('SUMMARY vmcmp mat %d PC %d vs new: worst %.3f' % (mat, plib, worst))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'vmcmp':
        sl = (0, 1, 2, 3, 4, 5, 6, 7)
        if '--slots' in a: k = a.index('--slots'); sl = tuple(int(x) for x in a[k + 1].split(',')); a = a[:k] + a[k + 2:]
        cmd_vmcmp(a[1], a[2], int(a[3]), a[4], sl, 5); return
    def opt(k, d, f=str):
        if k in a:
            j = a.index(k); v = f(a[j + 1]); del a[j:j + 2]; return v
        return d
    if a[0] == 'inv':
        all_ = '--all' in a; a = [x for x in a if x != '--all']; cmd_inv(a[1], a[2], all_); return
    if a[0] == 'lit': cmd_lit([int(x) for x in a[1].split(',')]); return
    if a[0] == 'twins':
        inv = collections.defaultdict(list)
        for x_, p_ in TLT.x2p().items(): inv[p_].append(x_)
        print(' '.join('%d/%d' % (min(inv[int(p)]), int(p)) if inv.get(int(p)) else 'none/%s' % p for p in a[1].split(','))); return
    if a[0] == 'xref':
        slots = tuple(int(x) for x in opt('--slots', '0,1,2,3,4,5,6,7').split(','))
        lib = opt('--lib', None, int); bindir = opt('--bin', None); seed = opt('--seed', 5, int); rw = opt('--range', -100.0, float)
        gd = '--no-game-dxn' not in a; a = [x for x in a if x != '--no-game-dxn']
        cmd_xref(a[1], a[2], int(a[3]), slots, seed, rw, lib, bindir, gd); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
