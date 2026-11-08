"""Night 03.11. (test 50l, second part): direct translation of UNLIT title-update / DLC pixel shaders (no light block -
the effect materials of the thralls and the doppelganger: 2249 / 2250, 2317 / 2318, 2323 / 2324, 2326 / 2327, 2368, 2375)
the test-46 way: upstream's Xenos -> ps_3_0 translator (work/ws/shader4/xenos2sm3.py) with the PC register conventions
(f9 Consts: constant names of the PC surrogate + the global PC name table + aliases, MaterialParams c100+j), sampler
registers from the material's own record pairing (Xbox record k register -> PC record k register), DXN textures with
the explicit `dxn` option (y = A, z = 0, w = 1; our DXN -> DXT5 layout). PC slot k <- Xbox slot k & 1 for EVERY slot of
the surrogate's table (odd = the Xbox fade variant, so no empty odd slot is left - test 48e).

Proof of the convention (rule of three): the same direct translation of BASE Xbox unlit libs against Nixxes' real PC
twins (shader_x2p), every PC slot, VM on random inputs / textures / constants with the base material's own params
(`oracle`). Per DLC lib (`build`): every slot f4_lint + D3DX9 valid, and the PC slot == the Xbox shader translated with
Xbox register numbers (VM, game-like DXN textures, Xbox MaterialParams).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tu_unlit.py oracle XB/PB[,XB/PB] | random N SEED     base unlit PS pairs vs the real PC lib
  ../bin/pyt -t 900 tools/tu_unlit.py build PC.drm XBOX.drm OUTDIR --pass 0|2 --mats M[,M]
      one lib for the given materials (must agree on the Xbox lib, sampler map, DXN registers); OUTDIR/plan.json in the
      tu_light_transplant layout (its `pack` makes the .lib); the PC slot table = the surrogate's (current lib of the pass)
  ../bin/pyt -t 600 tools/tu_unlit.py apply IN.drm XBOX.drm OUT.drm PACKDIR --pass 0|2
      new ShaderLib sections (after the material's current lib of that pass), the pass slot of the listed materials ->
      new id, PS MaterialParams := the Xbox material's (grown in place; --pass 3 = VS, params unchanged)
  ../bin/pyt -t 600 tools/tu_unlit.py vsinfo DLCVS XBASEVS PCVS          DLC VS slots vs the base twin (inputs / outputs / extra lines)
  ../bin/pyt -t 600 tools/tu_unlit.py vsbuild DLCVS XBASEVS PCVS PACKDIR NEWID MAT[,MAT]   PC twin + COLOR0 pass-through
"""
import sys, os, json, struct, hashlib, random, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs, xenos2sm3
import f9_common
import shaderlib as SL
import drm_write as DW, drm_reloc as R
import fade_slots_translate as FST
from tu_shader_night import game_dxn_tex

PASS_OFF = {0: 0x28, 1: 0x2c, 2: 0x30, 3: 0x34}   # 3 = vertex shader (no PS MaterialParams change)
LIGHT = re.compile(r'Light|Shadow|PSSM')


def translate(xblob, pct, samp_names, dxn):
    """xenos2sm3 with PC registers: K from the PC ctab pct; samplers by Xbox name -> PC register"""
    K = F9.Consts(pct)
    opts = {'dxn': set(dxn), 'dxn_full': set(dxn)} if dxn else {}
    t = xenos2sm3.translate(xblob, K.fn, bools=None, samp=F9.xsamp(xblob, samp_names), opts=opts)
    if K.extra: raise F9.Fail('constants without a PC register: %s' % sorted({k[0] for k in K.extra}))
    return sm3asm.parse_text(t.text)


def translate_xregs(xblob, samp_names, dxn):
    """reference: the same Xbox shader with XBOX register numbers for the constants (identity), same samplers"""
    opts = {'dxn': set(dxn), 'dxn_full': set(dxn)} if dxn else {}
    sh = XL.parse(xblob); regs = {c['name']: c['reg'] for c in sh.ctab if c['set'] == 2}
    t = xenos2sm3.translate(xblob, lambda n, j, c: regs[n] + j if n in regs else None, bools=None, samp=F9.xsamp(xblob, samp_names), opts=opts)
    return sm3asm.parse_text(t.text), regs


def vm_cmp(A, B, env_a, env_b, tex, bools=None):
    a = F9.run_state(A, F9.body(A), env_a.state0(A), env_a.consts, tex, env_a.N, bools or {})
    b = F9.run_state(B, F9.body(B), env_b.state0(B), env_b.consts, tex, env_b.N, bools or {})
    ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
    if ca is None or cb is None: return 0.0 if (ca is None) != (cb is None) else 1.0
    return float((np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])).mean())


# ---------------------------------------------------------------------------------------------------- oracle
def unlit_pairs():
    """base unlit PS pairs used as a PASS-2 (colour) shader by some base material (pass 0 = depth / alpha pass: Nixxes
    changed those - kill / AlphaThreshold - and they are not translated here)"""
    L = libs(); X, P = L['X'], L['P']; out = []; pos = F9.positions()
    for x, p in sorted(TLT.x2p().items()):
        if x not in X or p not in P or X[x]['kind'] != 1 or P[p]['kind'] != 1: continue
        if 2 not in pos.get(x, set()): continue
        sh = XL.parse(X[x]['entries'][X[x]['slots'][0]]['blob']) if X[x]['slots'][0] != 0xffffffff else None
        if sh is None or any(LIGHT.search(c['name']) for c in sh.ctab): continue
        out.append((x, p))
    return out


def cmd_oracle(pairs):
    L = libs(); X, P = L['X'], L['P']; tot = ok = 0
    for xb, pb in pairs:
        mt = f9_common.material_pairs(xb, pb)
        XP, PP = (mt[0][2], mt[0][3]) if mt else (None, None)
        res = []
        for k, o in enumerate(P[pb]['slots']):
            if o == 0xffffffff: continue
            xs = X[xb]['slots'][k & 1] if len(X[xb]['slots']) > (k & 1) else 0xffffffff
            if xs == 0xffffffff: res.append('s%d:noX' % k); continue
            pblob = P[pb]['entries'][o]['blob']; xblob = X[xb]['entries'][xs]['blob']
            pct = F9.pc_ctab(pblob); preg = {n: ri for n, rs, ri, rc in pct if rs == 3}
            try:
                T = translate(xblob, pct, ('globali', preg), ())
            except Exception as e:
                res.append('s%d:FAIL %s' % (k, str(e)[:60])); continue
            Pb = F9.decode_pc(pblob)
            ex = F9.Env(5, XP); ep = F9.Env(5, PP)
            for r in range(224):
                if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
            v = min(vm_cmp(T, Pb, ex, ep, ex.tex), vm_cmp(T, Pb, ex, ep, ex.tex, F9.ALLB))
            res.append('s%d=%.3f' % (k, v)); tot += 1; ok += v >= 0.999
        print('%d/%d (%s params): %s' % (xb, pb, 'material' if mt else 'random', ' '.join(res)), flush=True)
    print('SUMMARY oracle: %d of %d PC slots reproduced exactly (>= 0.999)' % (ok, tot))


# ---------------------------------------------------------------------------------------------------- build
def mat_recs(Pd, Xd, pm, xm):
    """sampler map + DXN registers from ALL records (TLT.sampler_map; 08.11.: the per-instance records were missing)"""
    r = TLT.sampler_map(Pd[(10, pm)], Xd[(10, xm)], Xd)
    if r is None: raise SystemExit('material %d: PC / Xbox texture records do not pair' % pm)
    return r['smap'], r['dxn']


def cmd_build(pcf, xf, out, pas, mats):
    os.makedirs(out, exist_ok=True)
    _, Pd = TLT.load(pcf, 'le'); _, Xd = TLT.load(xf, 'be')
    L = libs(); off = PASS_OFF[pas]
    xids = {struct.unpack_from('>4I', Xd[(10, m)].data, 0x28)[pas] for m in mats}
    if len(xids) != 1: raise SystemExit('materials use different Xbox libs in pass %d: %s' % (pas, xids))
    xid = xids.pop(); lib = TLT.tu_lib(xid)
    recs = [mat_recs(Pd, Xd, m, m) for m in mats]
    if any(r != recs[0] for r in recs): raise SystemExit('materials differ in sampler map / DXN: %s' % recs)
    smap, dxn = recs[0]
    sur = {struct.unpack_from('<4I', Pd[(10, m)].data, 0x28)[pas] for m in mats}
    if len(sur) != 1: raise SystemExit('materials have different PC libs in pass %d: %s' % (pas, sur))
    sur = sur.pop()
    PL = SL.parse(Pd[(9, sur)].data, 'le') if (9, sur) in Pd else L['P'][sur]
    xnames = TLT.xbox_sampler_names(lib)
    names = {n: smap[r] for r, n in xnames.items() if r in smap}
    XP = TLT.mparams(Xd[(10, mats[0])], 'be')
    # PC ctab: the surrogate's even slot 0 entry (the names the PC engine binds for this material type)
    pct = F9.pc_ctab(PL['entries'][next(o for o in PL['slots'] if o != 0xffffffff)]['blob'])
    print('== d%d pass %d materials %s: PC surrogate %d (%d slots), samplers %s, DXN %s, Xbox params %d vec4' % (
        xid, pas, mats, sur, len(PL['slots']), {xnames.get(k, '?')[:40]: v for k, v in smap.items()}, sorted(dxn), len(XP)), flush=True)
    ent = dict(donor_xs=0, donor_pd=sur, method='unlit-direct', pas=pas, mats=[(m, m) for m in mats],
               sampler_map={str(k): v for k, v in smap.items()}, slots={})
    ok = True
    for k in range(len(PL['slots'])):
        xs = lib['slots'][k & 1]
        if xs == 0xffffffff: xs = lib['slots'][0]
        xblob = lib['entries'][xs]['blob']
        try:
            T = translate(xblob, pct, names, dxn)
        except Exception as e:
            print('   slot %d: FAIL %s' % (k, e)); ok = False; break
        bc = sm3asm.encode(T)
        valid, txt, err = FST.valid(bc)
        Rx, regs = translate_xregs(xblob, names, dxn)
        ex = F9.Env(5 + k, XP); ep = F9.Env(5 + k, XP)
        # same values under the PC register numbers: copy every Xbox constant to the register the PC translation uses
        K = F9.Consts(pct)
        for n, r in regs.items():
            c = next(c for c in XL.parse(xblob).ctab if c['set'] == 2 and c['name'] == n)
            for j in range(max(1, c['count'])):
                pr_ = K.fn(n, j, c['count'])
                if pr_ is not None: ep.consts[pr_] = ex.consts[r + j]
        for j, v in enumerate(XP): ex.consts[100 + j] = ep.consts[100 + j] = np.array(v, np.float32)
        # the Xbox reference reads MaterialParams at its own Xbox register: put the params there too
        if 'MaterialParams' in regs:
            for j, v in enumerate(XP): ex.consts[regs['MaterialParams'] + j] = np.array(v, np.float32)
        tex = game_dxn_tex(ex.tex, dxn)
        m = vm_cmp(T, Rx, ep, ex, tex)
        n = len(F9.body(T))
        print('   slot %d (Xbox slot %d): %d instr, D3DX9 + f4_lint %s, PC == Xbox (Xbox registers) %.3f' % (k, k & 1, n, 'ok' if valid else 'FAIL ' + str(err)[:120], m), flush=True)
        if not valid or m < 0.999: ok = False; break
        fn = os.path.join(out, '%d_s%d' % (xid, k))
        open(fn + '.bin', 'wb').write(bc); open(fn + '.asm', 'w').write(sm3asm.format_program(T))
        ent['slots'][str(k)] = dict(file=os.path.basename(fn) + '.bin', md5=hashlib.md5(bc).hexdigest(), instr=n, vm_vs_xbox=m)
    pp = os.path.join(out, 'plan.json'); plan = json.load(open(pp)) if os.path.exists(pp) else {}
    plan[str(xid)] = ent if ok else dict(error='unlit build failed')
    json.dump(plan, open(pp, 'w'), indent=1)
    print('RESULT d%d pass %d: %s' % (xid, pas, 'ok' if ok else 'FAILED'))


# ---------------------------------------------------------------------------------------------------- apply
def grow_params(s, vals):
    """tu_light_transplant.grow_params, plus the fix for a PC block of 0 vec4 (effect materials 20744 / 24958: Xbox 7,
    PC 0): there the insert point equals the block start, and the generic rule 'targets >= insert point move' also moved
    the +0x5C MaterialParams pointer itself - it then pointed at the texture records behind the new block (found on the
    first apply, mat_layout_show). The +0x5C target is put back to the block start; the values are written there."""
    r0 = R.parse(s.reloc, 'le'); o = dict(r0.internal).get(0x5C); n = struct.unpack_from('<I', s.data, 0x58)[0]
    oldp, info = TLT.grow_params(s, vals)
    if n == 0 and len(vals) > 0:
        r = R.parse(s.reloc, 'le')
        r.internal = [(a, o) if a == 0x5C else (a, b) for a, b in r.internal]
        s.reloc = R.write(r, 'le'); info += '; +0x5C kept at %#x (empty PC block)' % o
    o2 = dict(R.parse(s.reloc, 'le').internal)[0x5C]
    got = [struct.unpack_from('<4f', s.data, o2 + 16 * j) for j in range(len(vals))]
    assert all(np.allclose(g, v) for g, v in zip(got, vals)), 'params readback'
    return oldp, info


def cmd_apply(src, xf, out, packd, pas):
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le'); _, X = TLT.load(xf, 'be')
    mp = json.load(open(os.path.join(packd, 'map.json'))); off = PASS_OFF[pas]
    have = {s.id for s in D.sections if s.type == 9}
    secs = {(s.type, s.id): s for s in D.sections}
    added = []; changed = {}
    for xid, v in sorted(mp.items(), key=lambda kv: int(kv[0])):
        nid = v['new']
        if nid in have: raise SystemExit('lib %d already in the file' % nid)
        data = open(os.path.join(packd, '%d.lib' % nid), 'rb').read()
        cur = struct.unpack_from('<I', secs[(10, v['mats'][0][0])].data, off)[0]
        old = secs[(9, cur)]
        D.sections.insert(D.sections.index(old) + 1, DW.Section(9, nid, data, b'', flags=old.flags, ver=old.ver, spec=old.spec, pad=old.pad))
        added.append(nid)
        for pm, xm in v['mats']:
            s = secs[(10, pm)]
            if (9, off) not in set(R.parse(s.reloc, 'le').idref): raise SystemExit('material %d: +%#x is not a ShaderLib reference' % (pm, off))
            d = bytearray(s.data); was = struct.unpack_from('<I', d, off)[0]
            struct.pack_into('<I', d, off, nid); s.data = bytes(d)
            xv = TLT.mparams(X[(10, xm)], 'be')
            oldp, info = grow_params(s, xv) if (xv and pas != 3) else ([], 'not changed' if pas == 3 else 'no Xbox params')
            changed[pm] = 'pass %d %d -> %d; params = Xbox %d vec4 %s' % (pas, was, nid, len(xv), info or '(size kept)')
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    rest = [s for s in B if not (s.type == 9 and s.id in added)]
    assert len(rest) == len(A)
    diff = {(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc) != (b.type, b.id, b.data, b.reloc)}
    assert diff <= {(10, m) for m in changed}, diff
    for nid in added:
        assert next(x for x in B if x.type == 9 and x.id == nid).data == open(os.path.join(packd, '%d.lib' % nid), 'rb').read()
    for m in sorted(changed): print('material %d: %s' % (m, changed[m]))
    print('readback: %d original sections in order, %d materials changed (%d differ), %d new ShaderLibs %s' % (len(A), len(changed), len(diff), len(added), added))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (out, hashlib.md5(o).hexdigest(), len(o)))


def cmd_vsinfo(dl, xb, pc):
    """per occupied slot of the DLC VS dl: Xbox vertex inputs / output interpolators, same text as base Xbox xb's slot
    (after register renaming) or not, and the extra lines; the PC twin pc's slot outputs"""
    L = libs(); D, X, P = L['D'][dl], L['X'][xb], L['P'][pc]
    def norm(lines):
        out = []
        for l in lines:
            m = {}
            def rn(mo):
                k = mo.group(0)
                if k not in m: m[k] = 'R%d' % len(m)
                return m[k]
            out.append(re.sub(r'\br\d+\b', rn, l))
        return out
    import difflib
    for k, o in enumerate(D['slots']):
        if o == 0xffffffff: continue
        sd = XL.parse(D['entries'][o]['blob']); td = XL.text(sd, 'pretty').lines
        line = 'slot %3d: in %s out %s' % (k, [(XL.USAGE[v['usage']], v['index']) for v in sd.vtx], [(XL.USAGE[v['usage']], v['index'], v['reg']) for v in sd.interp])
        if k < len(X['slots']) and X['slots'][k] != 0xffffffff:
            sx = XL.parse(X['entries'][X['slots'][k]]['blob']); tx = XL.text(sx, 'pretty').lines
            same = norm(td) == norm(tx)
            extra = [l.strip() for l in difflib.ndiff(norm(tx), norm(td)) if l.startswith('+ ')]
            line += ' | base %d: in %s out %s, %s%s' % (xb, [(XL.USAGE[v['usage']], v['index']) for v in sx.vtx], [(XL.USAGE[v['usage']], v['index'], v['reg']) for v in sx.interp],
                                                    'SAME' if same else 'differs', '' if same else ' extra %s' % extra[:4])
        else: line += ' | base %d: slot empty' % xb
        if k < len(P['slots']) and P['slots'][k] != 0xffffffff:
            prog = F9.decode_pc(P['entries'][P['slots'][k]]['blob'])
            outs = [(i.usage & 31, (i.usage >> 16) & 15) for i in prog.instrs() if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT]
            line += ' | PC %d out %s' % (pc, outs)
        else: line += ' | PC %d slot empty' % pc
        print(line)


def cmd_vsbuild(dl, xb, pc, packd, nid, mats, extra=()):
    """PC VS lib for the DLC VS dl whose slots are base Xbox xb's + a COLOR0 pass-through (vsinfo): PC twin pc slot k
    verbatim, plus `dcl_color v; dcl_color o; mov o, v` in every slot where the DLC slot reads the Color input. Slots
    the PC twin leaves empty stay empty (base PC convention). Writes PACKDIR/<nid>.lib + map.json for `apply --pass 3`.
    extra: PC slots that get the pass-through although the DLC slot of the same number does not fetch colour - PC 406
    slots 32 / 160 are the only PC slots with the TexCoord5 output of the Xbox fog group 40 / 168 (which fetch Color0
    and are empty on the PC); the same rule as the Look fix VS 2944 (Befund-Look.md), so both VS libs agree."""
    import column_shader_translate as CST
    L = libs(); D, P = L['D'][dl], L['P'][pc]
    taken = FST.known_hashes()
    slots = []; uniq = {}; log = []
    for k, o in enumerate(P['slots']):
        if o == 0xffffffff: slots.append(None); continue
        pblob = CST.trim(P['entries'][o]['blob']); prog = sm3asm.decode(pblob)
        dcol = k in extra or k < len(D['slots']) and D['slots'][k] != 0xffffffff and any(
            XL.USAGE[v['usage']] == 'Color' for v in XL.parse(D['entries'][D['slots'][k]]['blob']).vtx)
        if not dcol: slots.append((P['entries'][o]['hash'], pblob)); continue
        ins = prog.instrs()
        vin = {i.ops[0].num for i in ins if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_INPUT}
        vout = {i.ops[0].num for i in ins if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT}
        if any(i.op == 'dcl' and (i.usage & 31) == 10 for i in ins): raise SystemExit('slot %d already has a colour dcl' % k)
        v = next(n for n in range(16) if n not in vin); oo = next(n for n in range(12) if n not in vout)
        txt = sm3asm.format_program(prog).splitlines()
        hdr = [l for l in txt if l.strip().startswith(('vs_', 'dcl', 'def'))]
        body = [l for l in txt if l not in hdr]
        new = hdr + ['dcl_color v%d' % v, 'dcl_color o%d' % oo] + body
        endi = max(i for i, l in enumerate(new) if l.strip() == 'end') if any(l.strip() == 'end' for l in new) else len(new)
        new = new[:endi] + ['mov o%d, v%d' % (oo, v)] + new[endi:]
        p2 = sm3asm.parse_text('\n'.join(new) + '\n'); bc = sm3asm.encode(p2)
        _ok, _msg = FST.SV.assemble(FST.SD.disasm(bc)); valid = _ok and not _msg.strip(); err = _msg   # D3DX9 vs_3_0 (f4_lint is PS-only)
        # structural proof: the PC twin's instructions in order, plus exactly the 2 dcl + 1 mov
        a_ = [sm3asm.fmt_instr(i, 'vs') for i in prog.instrs()]; b_ = [sm3asm.fmt_instr(i, 'vs') for i in p2.instrs()]
        added = list(b_)
        for l in a_: added.remove(l)
        log.append('slot %3d: PC %d + colour v%d -> o%d (%d -> %d instructions), D3DX9 %s, added %s' % (
            k, pc, v, oo, len(a_), len(b_), 'ok' if valid else 'FAIL %s' % str(err)[:100], added))
        if not valid or len(added) != 3: raise SystemExit(log[-1])
        if bc not in uniq: uniq[bc] = CST.new_hash(bc, taken)
        slots.append((uniq[bc], bc))
    j = {e['junk'] for e in P['entries'].values()}
    data = CST.pc_lib(P['kind'], slots, j.pop() if len(j) == 1 else 0)
    chk = SL.parse(data, 'le')
    assert len(chk['slots']) == len(P['slots']) and all((a == 0xffffffff) == (b == 0xffffffff) for a, b in zip(chk['slots'], P['slots']))
    os.makedirs(packd, exist_ok=True)
    open(os.path.join(packd, '%d.lib' % nid), 'wb').write(data)
    json.dump({str(dl): dict(new=nid, mats=[(m, m) for m in mats], donor='0/%d' % pc, md5=hashlib.md5(data).hexdigest())}, open(os.path.join(packd, 'map.json'), 'w'), indent=1)
    for l in log: print(l)
    print('VS lib %d: DLC %d = base %d + colour; PC %d %d slots (%d with the colour pass-through), %d bytes, md5 %s' % (
        nid, dl, xb, pc, sum(1 for s in slots if s), len(log), len(data), hashlib.md5(data).hexdigest()))


def cmd_copylib(src, packd, specs):
    """pack dir for `apply` from libs that already exist in another PC DRM (DLC 1: upstream's B138 translations of
    knight_thrall.drm for the co_dlc_knight_thrall copies of the same materials): specs LIBID:MAT[+MAT]"""
    _, S = TLT.load(src, 'le'); os.makedirs(packd, exist_ok=True); mp = {}
    for k, sp in enumerate(specs):
        lid, mats = sp.split(':'); lid = int(lid); mats = [int(m) for m in mats.split('+')]
        data = S[(9, lid)].data
        for m in mats:
            cur = struct.unpack_from('<I', S[(10, m)].data, 0x30)[0]
            if cur != lid: raise SystemExit('material %d uses %d in %s, not %d' % (m, cur, src, lid))
        open(os.path.join(packd, '%d.lib' % lid), 'wb').write(data)
        mp[str(k + 1)] = dict(new=lid, mats=[(m, m) for m in mats], donor='copy of %s' % os.path.basename(src), md5=hashlib.md5(data).hexdigest())
        print('lib %d (%d bytes, md5 %s) for materials %s' % (lid, len(data), hashlib.md5(data).hexdigest(), mats))
    json.dump(mp, open(os.path.join(packd, 'map.json'), 'w'), indent=1)


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'copylib': cmd_copylib(a[1], a[2], a[3:]); return
    if a[0] == 'vsinfo': cmd_vsinfo(int(a[1]), int(a[2]), int(a[3])); return
    if a[0] == 'vsbuild':
        ex = [int(x) for x in a[a.index('--extra') + 1].split(',')] if '--extra' in a else []
        cmd_vsbuild(int(a[1]), int(a[2]), int(a[3]), a[4], int(a[5]), [int(x) for x in a[6].split(',')], ex); return
    def opt(k, d=None):
        if k in a:
            j = a.index(k); v = a[j + 1]; del a[j:j + 2]; return v
        return d
    if a[0] == 'oracle':
        if a[1] == 'random':
            random.seed(int(a[3])); ps = unlit_pairs(); cmd_oracle(sorted(random.sample(ps, min(int(a[2]), len(ps)))))
        else: cmd_oracle([tuple(int(y) for y in x.split('/')) for x in a[1].split(',')])
        return
    if a[0] == 'build':
        pas = int(opt('--pass')); mats = [int(x) for x in opt('--mats').split(',')]
        cmd_build(a[1], a[2], a[3], pas, mats); return
    if a[0] == 'apply':
        pas = int(opt('--pass')); cmd_apply(a[1], a[2], a[3], a[4], pas); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
