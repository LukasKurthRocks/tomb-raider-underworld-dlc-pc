r"""P4a probe (13.11.): build one lit group slot like tu_batch.build_group and dump the program around the lint /
uninitialised findings, plus the Xbox translated program (xprog) and the build log.
Usage: ../bin/pyt -t 900 work/p4a_shader_1311/probe_build.py PC.drm XBOX.drm PCMAT XLIB SLOT OUT.txt"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_batch as TB, tu_light_transplant as TLT, tu_perlight as TP, tu_shader_night as TN
from tu_light_transplant import F9, sm3asm, libs
import f4_lint
from f11_uninit import uninit_reads


def main(a):
    pcf, xf, mat, xl, k, outp = a[0], a[1], int(a[2]), int(a[3]), int(a[4]), a[5]
    P = TLT.load(pcf, 'le')[1]; X = TLT.load(xf, 'be')[1]
    xm = {pm: x for pm, x, _ in TN.mats_of(P, X)}[mat]
    r = TB.recs_full(P, X, mat, xm)
    smap, dxn = r['smap'], set(r['dxn'])
    XP = TLT.mparams(X[(10, xm)], 'be')
    pd = TB.SMAP[xl]['pc']; L = libs(); lib = TLT.tu_lib(xl)
    xnames = TLT.xbox_sampler_names(lib)
    names = {n: smap[r_] for r_, n in xnames.items() if r_ in smap}
    TLT.EXTRA_OPTS.clear(); TLT.EXTRA_OPTS.update({'dxn': set(dxn), 'dxn_full': set(dxn)} if dxn else {})
    out = open(outp, 'w', encoding='utf-8', newline='\n')
    w = lambda s='': out.write(s + '\n')
    w('xlib %d slot %d donor %s mat %d xmat %d smap %s dxn %s names %s' % (xl, k, pd, mat, xm, smap, sorted(dxn), names))
    w('xbox lib slots %s, donor slots %s' % (lib['slots'], L['P'][pd]['slots']))
    slots = L['P'][pd]['slots']
    xs = lib['slots'][k & 1] if lib['slots'][k & 1] != 0xffffffff else lib['slots'][0]
    xblob = lib['entries'][xs]['blob']
    src = k if slots[k] != 0xffffffff else (k & ~1)
    lg = []
    try:
        T = TP.build(xblob, L['P'][pd]['entries'][slots[src]]['blob'], names, lg)
    except Exception as ex:
        w('BUILD FAIL %s %s' % (type(ex).__name__, ex))
        for x in lg: w('log ' + str(x))
        T = None
    if T is not None:
        T, nsc = TB.fix_sincos(T)
        for x in lg: w('log ' + str(x))
        bc = sm3asm.encode(T); errs = f4_lint.lint(bc, True); un = uninit_reads(T)
        w('lint %s' % errs); w('uninit %s' % un)
        bad = {int(e.split()[0]) for e in errs if e.split()[0].isdigit()}
        ins = sm3asm.decode(bc).instrs()
        w('---- T (lint index = instrs() index)')
        for i, x in enumerate(ins):
            w('%s%4d  %s' % ('>>' if i in bad else '  ', i, sm3asm.fmt_instr(x, 'ps')))
    # Xbox side
    K = F9.Consts(F9.pc_ctab(L['P'][pd]['entries'][slots[src]]['blob']))
    samp = F9.xsamp(xblob, names)
    xprog, i0, i1, tr = F9.translate_x(xblob, K.fn, samp, F9.xbools(xblob), opts=dict(TLT.EXTRA_OPTS))
    w('---- Xbox translated (light block [%s,%s))' % (i0, i1))
    xun = uninit_reads(xprog)
    w('xbox uninit %s' % xun)
    for i, x in enumerate(F9.body(xprog)):
        w('%s%4d  %s' % ('[]' if i0 is not None and i0 <= i < i1 else '  ', i, sm3asm.fmt_instr(x, 'ps')))
    out.close()
    print('wrote %s' % outp)


if __name__ == '__main__':
    main(sys.argv[1:])
