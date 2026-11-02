"""Test 50c (rock vein strip, DLC 2): translate the pass-0 pixel shader of the vein materials (Xbox TU / DLC lib 2372,
alpha-tested depth pass of the multi-layer blend; PC surrogate 1984 = PC twin of base Xbox 1144) to PC SM3.

Method (as test 46 pass 0, docs Befund-Wasserfall.md): upstream Xenos -> ps_3_0 translator (work/ws/shader4/xenos2sm3,
with the vector-kill fix of tools/column_shader_translate.py), PC constant registers (one register per name over all
base PC libs), sampler registers from the material's record pairing (Xbox record k register -> PC record k register).
PC pass-0 layout (tools/column_shader_report.py pass0, all base pairs): PC slot 0 / 1 <- Xbox slot 0 / 1, PC slot 2 =
the PC-only depth-into-colour permutation of the family (kept from the surrogate), slot 3 empty.

Proof first (rule of three): `oracle` translates base Xbox libs of pass-0 pairs the same way (sampler map by name)
and compares them in the SM3 VM (random interpolators / constants / textures, colour AND kill mask) with their real
PC twins, slot 0 and 1.

Usage (from the repository root; TRUDLC_PACK_FIRST=pack11):
  ../bin/pyt -t 900 tools/vein_ps0_translate.py oracle XID/PID[,XID/PID ...]
  ../bin/pyt -t 900 tools/vein_ps0_translate.py build PC.drm XBOX.drm OUTDIR --mat 24299 [--xid 2372]
  ../bin/pyt -t 600 tools/vein_ps0_translate.py apply IN.drm OUT.drm OUTDIR NEW_ID --mats 24299,24690
"""
import sys, os, json, struct, hashlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import column_shader_translate as CST                      # applies the upstream kill fix on import
from column_shader_translate import (libs, occ, blob, trim, pc_regs, ALIAS, xenos2sm3, XL, sm3asm, SD, SV,
                                     lib_bytes, known_hashes)
import drm_write as DW, drm_reloc as R, shaderlib as SL
sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4'))
import f9_transplant as F9, f4_lint


def xnames_of(b):
    return {c['reg'] + j: c['name'] for c in XL.parse(b).ctab if c['set'] == 3 for j in range(max(1, c.get('count', 1) or 1))}


def xlate(b, cregs, sampmap):
    def cfn(name, j, count):
        r = cregs.get(ALIAS.get(name, name))
        return None if r is None else r + j
    t = xenos2sm3.translate(b, cfn, bools=None, samp=lambda n, c: sampmap.get(c, c), opts={})
    bc = sm3asm.encode(t.prog)
    errs = f4_lint.lint(bc, True); ok, msg = SV.assemble(SD.disasm(bc))
    return t, bc, errs, (ok and not msg.strip()), msg.strip()


def pc_prog(lib, k):
    return sm3asm.decode(trim(lib['entries'][lib['slots'][k]]['blob']))


def cmd_oracle(pairs):
    L = libs(); cregs = pc_regs(L, 1)
    for xid, pid in pairs:
        X, P = L['X'][xid], L['P'][pid]
        for k in occ(X):
            if k > 1 or P['slots'][k] == 0xffffffff: continue
            b = blob(X, k)
            pn = {n: ri for n, rs, ri, rc in F9.pc_ctab(P['entries'][P['slots'][k]]['blob']) if rs == 3}
            pnn = {F9.norm_x(n): r for n, r in pn.items()}
            smap = {r: pn.get(n, pnn.get(F9.norm_x(n), r)) for r, n in xnames_of(b).items()}
            try:
                t, bc, errs, ok, msg = xlate(b, cregs, smap)
            except Exception as e:
                print('x%d/p%d slot %d: translation failed %r' % (xid, pid, k, e)); continue
            T = sm3asm.decode(bc); Pp = pc_prog(P, k)
            r = [F9.compare_pc(T, Pp, None, seed=s) for s in (5, 6, 7)]
            km = []
            for s in (5, 6, 7):        # kill mask alone (a depth pass writes no colour except the PC-only slot 2)
                env = F9.Env(s)
                ka = env.run(T, F9.body(T), env.state0(T), {})[1]; kb = env.run(Pp, F9.body(Pp), env.state0(Pp), {})[1]
                km.append('%.3f (%d/%d killed)' % (float(np.mean(ka == kb)), int(np.sum(ka)), int(np.sum(kb))))
            print('x%d/p%d slot %d: %d instr (PC %d), samplers %s, lint %s, D3DX %s, VM colour+kill match %s; kill mask match %s'
                  % (xid, pid, k, t.ninstr, len(F9.body(Pp)), smap, errs or 'ok', 'ok' if ok else 'FAILED ' + msg[:120],
                     ' / '.join('%.3f' % x for x in r), ' / '.join(km)), flush=True)


def records(s, e):
    r = R.parse(s.reloc, e); tp = dict(r.internal)[0x54]; f = '>' if e == 'be' else '<'
    return [struct.unpack_from(f + 'I', s.data, tp + 16 * k)[0:1] + (s.data[tp + 16 * k + 13],) for k in range(s.data[0x52])]


def mparams(s, e):
    f = '>' if e == 'be' else '<'
    o = dict(R.parse(s.reloc, e).internal).get(0x5C); n = struct.unpack_from(f + 'I', s.data, 0x58)[0]
    return [struct.unpack_from(f + '4f', s.data, o + 16 * j) for j in range(n)] if o is not None else []


def by_id(path, e):
    return {(s.type, s.id): s for s in DW.read(open(path, 'rb').read(), e).sections}


def cmd_build(pcf, xf, outd, mid, xid):
    os.makedirs(outd, exist_ok=True)
    L = libs(); cregs = pc_regs(L, 1)
    P, X = by_id(pcf, 'le'), by_id(xf, 'be')
    pm, xm = P[(10, mid)], X[(10, mid)]
    xt = struct.unpack_from('>4I', xm.data, 0x28); pt = struct.unpack_from('<4I', pm.data, 0x28)
    if xt[0] != xid: raise SystemExit('Xbox material %d pass 0 is %d, not %d' % (mid, xt[0], xid))
    pr, xr = records(pm, 'le'), records(xm, 'be')
    if [a[0] for a in pr] != [a[0] for a in xr]: raise SystemExit('record texture ids differ Xbox / PC')
    smap = {}
    for (pt_, ps), (xt_, xs) in zip(pr, xr):
        if smap.get(xs, ps) != ps: raise SystemExit('Xbox s%d on two PC registers' % xs)
        smap[xs] = ps
    sur = L['P'][pt[0]]; XL_ = L['D'][xid]
    xp = mparams(xm, 'be')
    log = ['material %d: Xbox pass-0 lib %d, PC surrogate %d (slots %s), sampler map Xbox -> PC %s' % (
        mid, xid, pt[0], ['-' if s == 0xffffffff else 'x' for s in sur['slots']], dict(sorted(smap.items())))]
    out = [None] * len(sur['slots'])
    for k in occ(XL_):
        b = blob(XL_, k)
        t, bc, errs, ok, msg = xlate(b, cregs, smap)
        T = sm3asm.decode(bc)
        open(os.path.join(outd, 'ps0_x%d_s%d.asm' % (xid, k)), 'w').write(sm3asm.format_program(T))
        kills = sum(1 for i in T.instrs() if i.op == 'texkill')
        # VM with the material's Xbox params: colour finite, kill count over random inputs
        env = F9.Env(7, xp); res = env.run(T, F9.body(T), env.state0(T), {})
        c = res[0].get((sm3asm.RT_COLOROUT, 0)); km = res[1]
        log.append('Xbox slot %d: %d instr, texkill %d, samplers used %s, consts %s, lint %s, D3DX %s; VM (Xbox params, random '
                   'inputs): colour finite %s, killed %d / %d' % (
                       k, t.ninstr, kills, sorted(t.samplers), sorted(t.consts), errs or 'ok', 'ok' if ok else 'FAILED ' + msg[:200],
                       bool(c is not None and np.all(np.isfinite(c))), int(np.sum(km)) if km is not None else 0, env.N))
        for n in t.notes: log.append('   note: %s' % n)
        if errs or not ok: raise SystemExit('slot %d not valid' % k)
        if k < len(out): out[k] = bc
    for k, s in enumerate(sur['slots']):
        if k >= 2 and s != 0xffffffff:
            e = sur['entries'][s]; out[k] = (bytes(e['hash']), trim(e['blob']))
            log.append('PC slot %d: kept from PC %d (hash %s, PC-only depth-into-colour permutation)' % (k, pt[0], bytes(e['hash']).hex()))
    data = lib_bytes(1, out, known_hashes(L))
    lib = SL.parse(data, 'le')
    open(os.path.join(outd, 'ps0.lib'), 'wb').write(data)
    log.append('ps0.lib: %d bytes, slots %s, md5 %s' % (len(data), ['-' if s == 0xffffffff else 'x' for s in lib['slots']], hashlib.md5(data).hexdigest()))
    open(os.path.join(outd, 'build.txt'), 'w').write('\n'.join(log) + '\n')
    print('\n'.join(log))


def cmd_apply(src, out, outd, nid, mats):
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    if any(s.type == 9 and s.id == nid for s in D.sections): raise SystemExit('lib %d already in the file' % nid)
    data = open(os.path.join(outd, 'ps0.lib'), 'rb').read()
    secs = {(s.type, s.id): s for s in D.sections}
    cur = struct.unpack_from('<I', secs[(10, mats[0])].data, 0x28)[0]
    old = secs[(9, cur)]
    D.sections.insert(D.sections.index(old) + 1, DW.Section(9, nid, data, b'', flags=old.flags, ver=old.ver, spec=old.spec, pad=old.pad))
    for m in mats:
        s = secs[(10, m)]
        if (9, 0x28) not in set(R.parse(s.reloc, 'le').idref): raise SystemExit('material %d: +0x28 is not a ShaderLib reference' % m)
        d = bytearray(s.data); was = struct.unpack_from('<I', d, 0x28)[0]
        struct.pack_into('<I', d, 0x28, nid); s.data = bytes(d)
        print('material %d pass 0: %d -> %d' % (m, was, nid))
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    rest = [s for s in B if not (s.type == 9 and s.id == nid)]
    assert len(rest) == len(A)
    diff = [(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc, a.flags, a.ver, a.spec, a.pad) != (b.type, b.id, b.data, b.reloc, b.flags, b.ver, b.spec, b.pad)]
    assert set(diff) == {(10, m) for m in mats}, diff
    assert next(x for x in B if x.type == 9 and x.id == nid).data == data
    print('readback: %d original sections in order, changed only %s; new ShaderLib %d' % (len(A), sorted(diff), nid))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (out, hashlib.md5(o).hexdigest(), len(o)))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'oracle': cmd_oracle([tuple(int(y) for y in x.split('/')) for x in a[1].split(',')])
    elif a[0] == 'build':
        mid = int(a[a.index('--mat') + 1]); xid = int(a[a.index('--xid') + 1]) if '--xid' in a else 2372
        cmd_build(a[1], a[2], a[3], mid, xid)
    elif a[0] == 'apply': cmd_apply(a[1], a[2], a[3], int(a[4]), [int(x) for x in a[a.index('--mats') + 1].split(',')])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
