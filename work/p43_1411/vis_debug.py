r"""P4.3 debug (14.11.): run tu_perlight.xbox_analysis on one Xbox lib slot (setup as tu_batch.build_group) and show
the x_vis_lane proof step by step for every L lane that is no world component of L.
Usage: ../bin/pyt -t 900 work/p43_1411/vis_debug.py PC.drm XBOX.drm PCMAT XLIB SLOT"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_batch as TB, tu_light_transplant as TLT, tu_perlight as TP, tu_shader_night as TN, perlight_xref as PX
from tu_light_transplant import F9, sm3asm, libs


def main(a):
    pcf, xf, mat, xl, k = a[0], a[1], int(a[2]), int(a[3]), int(a[4])
    P = TLT.load(pcf, 'le')[1]; X = TLT.load(xf, 'be')[1]
    xm = {pm: x for pm, x, _ in TN.mats_of(P, X)}[mat]
    r = TB.recs_full(P, X, mat, xm); smap, dxn = r['smap'], set(r['dxn'])
    pd = TB.SMAP[xl]['pc']; L = libs(); lib = TLT.tu_lib(xl)
    names = {n: smap[r_] for r_, n in TLT.xbox_sampler_names(lib).items() if r_ in smap}
    TLT.EXTRA_OPTS.clear(); TLT.EXTRA_OPTS.update({'dxn': set(dxn), 'dxn_full': set(dxn)} if dxn else {})
    slots = L['P'][pd]['slots']; src = k if slots[k] != 0xffffffff else (k & ~1)
    xblob = lib['entries'][lib['slots'][k & 1]]['blob']; pdblob = L['P'][pd]['entries'][slots[src]]['blob']
    pct = F9.pc_ctab(pdblob); preg = {n: ri for n, rs, ri, rc in pct if rs == 3}
    K = F9.Consts(pct); samp = F9.xsamp(xblob, names)
    log = []; A = TP.xbox_analysis(xblob, K, samp, log)
    print(log[0][:300])
    B = A['B']; xprog = A['xprog']; LXi = {j: r_ for r_, j in A['LX'].items()}
    print('LX (index -> reg):', sorted(LXi.items())[:30])
    for (rr, c) in A['Lx']:
        kk = A['Lfirst'][(rr, c)]
        span = B[kk:A['c1e']]; wl = sorted({l for i in span for l in TP.writes(i)})
        print('lane r%d.%s first read %d, span %d instr, written lanes %d' % (rr, 'xyzw'[c], kk, len(span), len(wl)))
        for seed in (5, 11):
            env = F9.Env(seed); Lr = PX.light(np.random.RandomState(seed + 100), -100.0)
            cons = dict(env.consts); PX.set_x(cons, LXi, Lr)
            for j in range(13):
                if j in LXi and 13 + j in LXi: cons[LXi[13 + j]] = cons[LXi[j]]
            reg, _ = F9.run_state(xprog, B[:kk], env.state0(xprog), cons, env.tex, env.N, F9.ALLB)
            v = reg.get((0, rr))
            if v is None: print('   seed %d: register not set' % seed); continue
            v = v[:, c]
            print('   seed %d: value mean %.4f min %.4f max %.4f nonzero %d / %d finite %s' % (seed, np.nanmean(v), np.nanmin(v), np.nanmax(v), int((np.abs(v) > 1e-6).sum()), len(v), bool(np.isfinite(v).all())))
            outs = []
            for f in (1.0, 0.5, 0.0):
                s2 = {q: w.copy() for q, w in reg.items()}; s2[(0, rr)][:, c] = v * f
                o, _ = F9.run_state(xprog, span, s2, cons, env.tex, env.N, F9.ALLB)
                outs.append(np.stack([o[(0, a_)][:, b_] for a_, b_ in wl], 1))
            d1, dh = outs[0] - outs[2], outs[1] - outs[2]
            fin = np.isfinite(d1) & np.isfinite(dh) & np.isfinite(outs[2])
            bad = fin & ~np.isclose(dh, 0.5 * d1, rtol=1e-4, atol=1e-5)
            print('   finite %.3f, nonlinear values %d, changed values %d' % (fin.mean(), int(bad.sum()), int((fin & (np.abs(d1) > 1e-6)).sum())))
            for j in np.where(bad.any(0))[0][:6]:
                print('     lane r%d.%s nonlinear on %d samples' % (wl[j][0], 'xyzw'[wl[j][1]], int(bad[:, j].sum())))
        print('   x_vis_lane ->', TP.x_vis_lane(A, rr, c, kk))


if __name__ == '__main__':
    main(sys.argv[1:])
