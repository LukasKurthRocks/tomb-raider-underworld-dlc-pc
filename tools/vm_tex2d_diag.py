"""Light-transplant oracle with a 2D-correct VM texture (read-only; test 50c, rock vein strip).

Finding: upstream's deterministic VM texture (work/ws/shader4/sm3vm.det_tex) hashes coords x, y AND z for every
sampler, while the GPU reads only x, y from a 2D texture. PC light chains of different shader builds leave different
garbage in the z lane of their 2D texld coordinates (e.g. the sun modulation map s11: `texld T3, T5, s11` vs
`texld T5, T4.ywzw, s11`), so the oracle reported two "PC light-chain variants" that may be equal on the hardware.
This tool repeats tools/tu_light_transplant.py lightdiag (base Xbox xb transplanted with donor xs/pd against the real
PC twin pb, one PC light bool at a time) twice: with the upstream texture and with z := 0 for every sampler both
programs declare dcl_2d (cube samplers keep x, y, z).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/vm_tex2d_diag.py XB PB XS PD [SLOT]
"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, f9_common, sm3asm, libs


def sampler_kinds(prog):
    """{sampler register: 'cube' | '2d' | other} from the dcl lines of the formatted program"""
    out = {}
    for i in prog.instrs():
        if i.op != 'dcl' or not i.ops or i.ops[0].rtype != sm3asm.RT_SAMPLER: continue
        t = sm3asm.fmt_instr(i, 1)
        out[i.ops[0].num] = 'cube' if 'cube' in t else ('2d' if '2d' in t else t.split()[0])
    return out


def main(a):
    xb, pb, xs, pd = [int(x) for x in a[:4]]; slot = int(a[4]) if len(a) > 4 else 0
    L = libs(); X, PL = L['X'], L['P']
    xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']; xsblob = X[xs]['entries'][X[xs]['slots'][slot & 1]]['blob']
    pdblob = PL[pd]['entries'][PL[pd]['slots'][slot]]['blob']; pbblob = PL[pb]['entries'][PL[pb]['slots'][slot]]['blob']
    mb = f9_common.material_pairs(xs, pd); mt = f9_common.material_pairs(xb, pb)
    xnames = {n: ri for n, rs, ri, rc in F9.pc_ctab(pbblob) if rs == 3}
    T, info = F9.build(xblob, pdblob, xsblob, [(m[2], m[3]) for m in mb], x_samp_names=xnames, log=[])
    Pb = F9.decode_pc(pbblob)
    kT, kP = sampler_kinds(T), sampler_kinds(Pb)
    two_d = {r for r in set(kT) | set(kP) if kT.get(r, '2d') == '2d' and kP.get(r, '2d') == '2d'}
    print('xb %d pb %d donor %d/%d slot %d; samplers T %s, Pb %s; 2D (z ignored): %s' % (xb, pb, xs, pd, slot, kT, kP, sorted(two_d)))
    for lab, fix in (('upstream texture (x, y, z)', False), ('2D samplers x, y only', True)):
        env = F9.Env(5, mt[0][3])
        if fix:
            base = env.tex
            def tex(smp, c, m, base=base):
                if smp in two_d: c = c.copy(); c[:, 2] = 0
                return base(smp, c, m)
            env.tex = tex
        print('-- %s' % lab)
        for name, bl in [('none', {})] + [('b%d' % b, {b: True}) for b in range(7)] + [('all', F9.ALLB)]:
            x = env.run(T, F9.body(T), env.state0(T), bl)[0].get((sm3asm.RT_COLOROUT, 0))
            y = env.run(Pb, F9.body(Pb), env.state0(Pb), bl)[0].get((sm3asm.RT_COLOROUT, 0))
            ok = np.isclose(x, y, **F9.TOL).all(axis=1).mean()
            print('  %-4s match %.3f  max|diff| %s' % (name, ok, np.round(np.nanmax(np.abs(x - y), axis=0), 4)))


if __name__ == '__main__':
    main(sys.argv[1:])
