"""Test 50h (doppelganger arms / gloves): small read-only diagnostics around the per-light translations.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/arms_diag.py twins PCLIB [PCLIB ...]
      base Xbox libs whose PC twin (work/render/shader_x2p.pkl) is PCLIB, and whether a base material pair exists
  ../bin/pyt -t 300 tools/arms_diag.py xconst D:XID|X:XID SLOT
      Xbox constant table of one lib slot and the PC register each float constant gets in f9
  ../bin/pyt -t 900 tools/arms_diag.py clobber PC.drm XBOX.drm MAT [--slots 0,1] [--donor PCLIB]
      rebuild the material's per-light lib with tools/tu_perlight.build: writes inside the new light chain to the
      read-only X registers, and the hoisting hazards (light-free instructions after chunk 1 that write a BRDF input)
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4')); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
from f3_common import x2p
import f9_common


def cmd_twins(pcs):
    m = x2p()
    for p in pcs:
        xs = sorted(x for x, pp in m.items() if pp == p)
        print('PC %d: Xbox twins %s' % (p, ['%d (%d base materials)' % (x, len(f9_common.material_pairs(x, p))) for x in xs]))


def cmd_xconst(spec, slot):
    """Xbox CTAB of one lib slot and the PC register each float constant gets in f9 (Consts([]) = base PC names,
    aliases, MaterialParams c100+j, Xbox-only names -> free registers)"""
    import f9_transplant as F9
    from f3_common import libs
    import xenos_xlat as XL
    k, i = spec.split(':'); lib = libs()[k][int(i)]
    blob = lib['entries'][lib['slots'][slot]]['blob']
    sh = XL.parse(blob); K = F9.Consts([])
    for c in sorted(sh.ctab, key=lambda c: (c['set'], c['reg'])):
        n = max(1, c.get('count', 1) or 1)
        if c['set'] == 2:
            regs = [K.fn(c['name'], j, n) for j in range(n)]
            pcname = F9.ALIAS.get(c['name'], c['name'])
            how = 'PC name' if pcname in K.pfl else 'MaterialParams' if c['name'] == 'MaterialParams' else 'Xbox-only -> free register'
            print('float c%d x%d %s -> PC c%s (%s)' % (c['reg'], n, c['name'], ','.join(str(r) for r in regs[:6]) + (',..' if n > 6 else ''), how))
        else:
            print('set %d reg %d x%d %s' % (c['set'], c['reg'], n, c['name']))
    print('Xbox literal defs: %s' % sorted(sh.defs))


def cmd_clobber(pcf, xf, mat, slots, pdonor=None):
    """rebuild the per-light lib of a material (tu_perlight.build, same inputs as its 'build') and list writes, inside
    the new light chain, to the X registers the cloned Xbox BRDF only reads (FIXED: they must keep their value)"""
    import struct
    import tu_perlight as TP
    import tu_light_transplant as TLT
    from tu_light_transplant import F9, sm3asm
    _, Pd = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    pm, xm = Pd[(10, mat)], Xd[(10, mat)]
    xid = struct.unpack_from('>4I', xm.data, 0x28)[2]
    lib = TLT.tu_lib(xid)
    pr, xr = TLT.records(pm, 'le'), TLT.records(xm, 'be')
    smap = {x[3]: p[3] for p, x in zip(pr, xr)}
    names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
    dxn = {p[3] for p, x in zip(pr, xr) if (5, x[0]) in Xd and struct.unpack_from('>I', Xd[(5, x[0])].data, 4)[0] & 0x3f == 0x31}
    TLT.EXTRA_OPTS.clear(); TLT.EXTRA_OPTS.update({'dxn': dxn, 'dxn_full': dxn} if dxn else {})
    from f3_common import libs
    PL = libs()['P']; pd = pdonor or 1616
    for k in slots:
        slots_pd = PL[pd]['slots']; src = k if slots_pd[k] != 0xffffffff else (k & ~1)
        xblob = lib['entries'][lib['slots'][k & 1]]['blob']
        log = []
        T = TP.build(xblob, PL[pd]['entries'][slots_pd[src]]['blob'], names, log)
        fixed = sorted(set(TP.FIXED.values()))
        B = F9.body(T)
        q0 = next(n for n, i in enumerate(B) if i.op == 'if' and i.ops and i.ops[0].rtype == sm3asm.RT_CONSTBOOL)
        depth = 0; q1 = None
        for n in range(q0, len(B)):
            if B[n].op in ('if', 'ifc'): depth += 1
            elif B[n].op == 'endif':
                depth -= 1
                if depth == 0: q1 = n
        hits = []
        for n in range(q0, (q1 or len(B)) + 1):
            i = B[n]
            if i.ops and i.ops[0].isdst and i.ops[0].rtype == sm3asm.RT_TEMP and i.op not in ('if', 'ifc') and i.ops[0].num in fixed:
                hits.append('%d: %s' % (n, sm3asm.fmt_instr(i, 'ps')))
        print('mat %d Xbox %d slot %d (donor %d slot %d): read-only X registers kept in place %s; light chain [%d,%s]; writes to them inside: %d'
              % (mat, xid, k, pd, src, ['r%d' % r for r in fixed], q0, q1, len(hits)))
        for h in hits[:12]: print('   ' + h)
        # hoisting hazard: a hoisted (light-free) instruction that sits AFTER the start of chunk 1 in the Xbox block and
        # writes a lane the chunk-1 BRDF reads - moved before the block it overwrites the value the BRDF needs
        pprog = F9.decode_pc(PL[pd]['entries'][slots_pd[src]]['blob']); pct = F9.pc_ctab(PL[pd]['entries'][slots_pd[src]]['blob'])
        K = F9.Consts(pct); samp = F9.xsamp(xblob, names)
        A = TP.xbox_analysis(xblob, K, samp, [])
        B, st = A['B'], A['st']
        # BRDF inputs = lanes the BRDF reads before it writes them itself (their value comes from before chunk 1)
        brdf_reads = {}; wr = set(); Lx = set(A['Lx'])
        for kk in A['brdf']:
            for t, n, ls in TP.reads(B[kk], st):
                if t == 't':
                    for c in ls:
                        if (n, c) not in wr and (n, c) not in Lx: brdf_reads.setdefault((n, c), kk)
            wr |= set(TP.writes(B[kk]))
        bad = []
        for kk in A['hoist']:
            if kk <= A['c1s']: continue
            for l in TP.writes(B[kk]):
                if l in brdf_reads: bad.append((kk, l))
        print('   chunk 1 [%d,%d), BRDF reads %d lanes; hoisted instructions after chunk-1 start that write a BRDF-read lane: %d'
              % (A['c1s'], A['c1e'], len(brdf_reads), len(bad)))
        for kk, l in bad[:12]:
            print('      %d: %s   (lane r%d.%s, read by BRDF at %d)' % (kk, sm3asm.fmt_instr(B[kk], 'ps'), l[0], 'xyzw'[l[1]], brdf_reads[l]))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'clobber':
        sl = (0, 1)
        if '--slots' in a: j = a.index('--slots'); sl = tuple(int(x) for x in a[j + 1].split(',')); a = a[:j] + a[j + 2:]
        dn = None
        if '--donor' in a: j = a.index('--donor'); dn = int(a[j + 1]); a = a[:j] + a[j + 2:]
        cmd_clobber(a[1], a[2], int(a[3]), sl, dn); return
    if a[0] == 'twins': cmd_twins([int(x) for x in a[1:]])
    elif a[0] == 'xconst': cmd_xconst(a[1], int(a[2]))
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
