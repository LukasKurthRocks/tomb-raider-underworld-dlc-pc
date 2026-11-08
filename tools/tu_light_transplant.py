"""Test 50a (finding 43, DLC 2 doppelganger 857): translate lit title-update (TU) Xbox pixel-shader libs to PC SM3 with
upstream's light transplant (work/ws/shader4/f9_transplant.py): the Xbox shader X is translated Xenos -> ps_3_0 with
PC registers (f9.Consts: PC CTAB names + aliases, MaterialParams c100+j), and its Xbox light block (the LightEnabled
chain) is replaced by the light block of a PC donor Pd. The bridge is Pd's Xbox twin Xs (base pair Xs -> Pd,
shader_x2p): Pd's block inputs / outputs are matched to Xs's numerically on a real base material, Xs's Xbox block to
X's by fingerprints (the same compiler, the same light model). Proof of the method on base pairs: f9 'oracolo'
(transplant of base Xbox Xb with a donor of ANOTHER pair == the real PC twin Pb, lights on / off / mixed).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tu_light_transplant.py donors XID[,XID] [--want N]
      base pairs (Xs, Pd) whose Xbox light block is equivalent to the DLC lib's (slot 0 and 1)
  ../bin/pyt -t 3600 tools/tu_light_transplant.py build PC.drm XBOX.drm OUTDIR --mesh 21730 --libs XID[,XID]
      per DLC lib: donor, all 8 PC slots (slot k: Xbox slot k & 1, light block of Pd slot k - or k & ~1 when Pd's odd
      slot is empty: the light bits are the same, bit 0 is the fade variant), checks (lights off == direct Xbox
      translation, f4_lint, uninitialised reads, dcl problems, <= 1024 instructions), sampler registers from the
      material's own record pairing (Xbox record k register -> PC record k register), writes OUTDIR/<xid>_s<k>.bin,
      OUTDIR/<xid>_s<k>.asm, OUTDIR/plan.json (lib -> slots, donor, material params read)
      plus 'consensus': slot 0 / 1 built with every other equivalent donor, VM-compared with the chosen one
  ../bin/pyt -t 600 tools/tu_light_transplant.py pack PC.drm PACKDIR BUILDDIR [BUILDDIR ...] --ids NEW,NEW,...
      8-slot PC ShaderLibs (base layout, size word with the dcl_cube mask, word0 0 as upstream's translated libs),
      new entry hashes (blake2b, checked against every known hash and the file's), every unique entry f4_lint +
      D3DX9-reassembled; PACKDIR/<new>.lib + map.json (TU lib -> new id, materials, donor); libs in TU-id order
  ../bin/pyt -t 600 tools/tu_light_transplant.py apply IN.drm XBOX.drm OUT.drm PACKDIR
      new ShaderLib sections (after the material's current pass-2 lib), pass-2 PS of the listed materials -> new id,
      their PS MaterialParams := the Xbox material's (the translated shaders read the Xbox layout; grown in place
      when the PC block is shorter); readback: only those materials differ, new libs byte-equal
  ../bin/pyt -t 600 tools/tu_light_transplant.py vscheck PC.drm BUILDDIR [...]
      input semantics of the translated PS against the outputs of each material's PC vertex shader
  ../bin/pyt -t 600 tools/tu_light_transplant.py oracle-pair XB PB    one base pair with a cross donor (f9 'coppia')
"""
import sys, os, json, struct, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
S4 = os.path.join(ROOT, 'work', 'ws', 'shader4')
sys.path.insert(0, S4)
from f12_build_all import *          # f9 transplant (build, find_donors, ...), f10 lights_off_check, f11 checks
import f9_transplant as F9
import f9_common
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R
import shaderlib as SL


# ---- two local corrections of the upstream transplant (upstream files are not edited):
# 1. f9.assemble reserved EVERY temp that X reads after its light block, so the 9 temps of a PC light chain did not fit
#    next to the unoptimised translation of the bigger TU shaders ("temp insufficienti"). A temp is only taken when it
#    is live at the block end: read after the block before an unconditional (depth 0, unpredicated) full write.
def _live_after(BX, i1, xprog):
    st = F9.stypes(xprog); killed = set(); live = set(); depth = 0
    for i in BX[i1:]:
        if i.op in ('if', 'ifc', 'rep', 'loop'): depth += 1
        elif i.op in ('endif', 'endrep', 'endloop'): depth -= 1
        for j, o in enumerate(i.ops):
            if o.isdst: continue
            if o.rtype == sm3asm.RT_TEMP:
                for c in F9.lanes(i, j, st):
                    if (o.num, c) not in killed: live.add(o.num)
            if o.rel and o.relop is not None and o.relop.rtype == sm3asm.RT_TEMP: live.add(o.relop.num)
        if depth == 0 and i.ops and i.ops[0].isdst and i.ops[0].rtype == sm3asm.RT_TEMP and not i.pred and i.op not in ('if', 'ifc'):
            for c in range(4):
                if i.ops[0].wm >> c & 1: killed.add((i.ops[0].num, c))
    return live


def _patch_assemble():
    import inspect
    src = inspect.getsource(F9.assemble)
    old = ("    for i in BX[i1:]:\n        for o in i.ops:\n"
           "            if not o.isdst and o.rtype == sm3asm.RT_TEMP: reserved.add(o.num)\n")
    if old not in src: raise SystemExit('f9.assemble changed upstream - patch not applicable')
    src = src.replace(old, "    reserved |= _live_after(BX, i1, xprog)\n"
                           "    reserved |= {o.num for i in xslice for o in i.ops if o.rtype == sm3asm.RT_TEMP}\n")
    F9._live_after = _live_after
    exec(compile(src, F9.__file__ + ' (assemble, test50a liveness patch)', 'exec'), F9.__dict__)


_patch_assemble()


# 2. f10.lights_off_check translates X with sampler register = Xbox register, while the build maps the samplers to the
#    material's PC record registers: with a non-identity map the check compared different textures. Same check with
#    the build's sampler map:
EXTRA_OPTS = {}   # translator options of the build (e.g. dxn registers), also used by the lights-off reference


def lights_off(progT, xblob, XP, names, seed=11):
    K = F9.Consts([])
    sh = XL.parse(xblob); bn = F9.bool_names(sh)
    t = xenos2sm3.translate(xblob, K.fn, bools={i: 0 for i in bn}, samp=F9.xsamp(xblob, names), opts=dict(EXTRA_OPTS, noopt=True))
    progX = sm3asm.parse_text(t.text)
    env = F9.Env(seed, XP)
    a = env.run(progT, F9.body(progT), env.state0(progT), {})
    b = env.run(progX, F9.body(progX), env.state0(progX), {})
    ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
    if ca is None or cb is None: return 0.0
    return float((np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])).mean())


def checks(T, xblob, XP, names):
    n = len(F9.body(T)); off = lights_off(T, xblob, XP, names)
    bc = sm3asm.encode(T); errs = f4_lint.lint(bc, True); un = uninit_reads(T); dp = decl_problems(T)
    smax = max([i.ops[0].num for i in F9.header(T) if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_SAMPLER] + [0])
    probs = []
    if n > 1024: probs.append('instr %d' % n)
    if off < 0.99: probs.append('lights off %.3f' % off)
    if errs: probs.append('lint %s' % errs[:2])
    if un: probs.append('uninitialised %d' % len(un))
    if dp: probs.append('dcl %s' % dp[:2])
    if smax > 15: probs.append('sampler s%d' % smax)
    return bc, n, off, probs


def tu_lib(xid):
    L = libs()
    if xid not in L['D']: raise SystemExit('DLC Xbox lib %d not in shaderlibs.pkl' % xid)
    return L['D'][xid]


def cmd_donors(ids, want):
    for xid in ids:
        lib = tu_lib(xid)
        for xs_ in (0, 1):
            if lib['slots'][xs_] == 0xffffffff: print('d%d slot %d empty' % (xid, xs_)); continue
            info = F9.xblock_info('D', xid, xs_)
            if info is None: print('d%d slot %d: light block not translatable / not found' % (xid, xs_)); continue
            prog, i0, i1, ins, outs = info
            d = F9.find_donors('D', xid, xs_, want=want)
            print('d%d slot %d: block [%d,%d) in %d out %d -> donors %s' % (xid, xs_, i0, i1, len(ins), len(outs), d), flush=True)


def load(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    by = {}
    for s in D.sections: by.setdefault((s.type, s.id), s)
    return D, by


def records(s, e):
    """the byte(+0x52) ORDINARY texture records only: [(tex id, type, kind byte, sampler register)]. Not enough for a
    sampler map - the per-instance records behind them are missing (ENGINE.md 17.4, per-instance sampler gap 08.11.);
    use sampler_map() for that."""
    r = R.parse(s.reloc, e); tp = dict(r.internal).get(0x54)
    f = '>' if e == 'be' else '<'
    out = []
    if tp is None: return out
    for k in range(s.data[0x52]):
        tid, u1, typ = struct.unpack_from(f + 'III', s.data, tp + 16 * k)
        out.append((tid, typ, s.data[tp + 16 * k + 12], s.data[tp + 16 * k + 13]))
    return out


def records_all(s, e):
    """every texture record of a material section: the byte(+0x52) ordinary ones, then the byte(+0x50) per-instance
    ones (terrain atlases, ENGINE.md 17.1) -> [(tex id, type, kind byte, sampler register, per_instance)]"""
    r = R.parse(s.reloc, e); tp = dict(r.internal).get(0x54)
    f = '>' if e == 'be' else '<'
    out = []
    if tp is None: return out
    n_ord, n_inst = s.data[0x52], s.data[0x50]
    for k in range(n_ord + n_inst):
        tid, u1, typ = struct.unpack_from(f + 'III', s.data, tp + 16 * k)
        out.append((tid, typ, s.data[tp + 16 * k + 12], s.data[tp + 16 * k + 13], k >= n_ord))
    return out


def pair_records(pr, xr):
    """pair the PC and Xbox records of one material (records_all tuples). Ordinary records: by position (the
    converter keeps their order; the kind byte must agree - 9 back buffer / 10 depth / 0 texture). Per-instance
    records: by kind byte (1 / 2 / 3 = the terrain instance's texture index; the converter re-slots them, 25057:
    Xbox kind 2 s9 -> PC s8, 25520: kind 1 s2 -> s1 and kind 2 s1 -> s2), same kind several times in order.
    -> (pairs [(xrec, prec)], unpaired_x [xrec without a PC partner], problems [str]); problems = not pairable"""
    po = [r for r in pr if not r[4]]; xo = [r for r in xr if not r[4]]
    pi = [r for r in pr if r[4]]; xi = [r for r in xr if r[4]]
    probs = []; pairs = []; unpaired = []
    if len(po) != len(xo): probs.append('%d PC / %d Xbox ordinary records' % (len(po), len(xo)))
    else:
        for j, (p, x) in enumerate(zip(po, xo)):
            if p[2] != x[2]: probs.append('ordinary record %d: kind PC %d / Xbox %d' % (j, p[2], x[2]))
            pairs.append((x, p))
    byk = collections.defaultdict(list)
    for p in pi: byk[p[2]].append(p)
    for x in xi:
        if byk.get(x[2]): pairs.append((x, byk[x[2]].pop(0)))
        else: unpaired.append(x)
    return pairs, unpaired, probs


def is_dxn(Xd, tid):
    return (5, tid) in Xd and struct.unpack_from('>I', Xd[(5, tid)].data, 4)[0] & 0x3f == 0x31


def sampler_map(ps, xs, Xd):
    """Xbox -> PC sampler map of a material from ALL its records (ordinary + per-instance, pair_records).
    -> None (records do not pair) or dict(smap {Xbox reg: PC reg}, dxn {PC regs whose Xbox texture is DXN},
    unpaired {Xbox regs of records without a PC partner - a shader that samples them cannot be translated},
    type_diff [ordinary pairs whose type word differs - B138 record variants, reported only])"""
    pairs, unpaired, probs = pair_records(records_all(ps, 'le'), records_all(xs, 'be'))
    if probs: return None
    smap = {}
    for x, p in pairs:
        if smap.get(x[3], p[3]) != p[3]: return None          # one Xbox register on two PC registers
        smap[x[3]] = p[3]
    dxn = {p[3] for x, p in pairs if is_dxn(Xd, x[0])}
    return dict(smap=smap, dxn=dxn, unpaired={x[3] for x in unpaired} - set(smap),
                type_diff=[(x, p) for x, p in pairs if x[1] != p[1]])


def mparams(s, e):
    f = '>' if e == 'be' else '<'
    o = dict(R.parse(s.reloc, e).internal).get(0x5C); n = struct.unpack_from(f + 'I', s.data, 0x58)[0]
    return [tuple(struct.unpack_from(f + '4f', s.data, o + 16 * j)) for j in range(n)] if o is not None else []


def mesh_mats(by, mid, e):
    s = by[(12, mid)]
    r = R.parse(s.reloc, e); f = '>' if e == 'be' else '<'
    return [struct.unpack_from(f + 'I', s.data, o)[0] for t, o in sorted(r.idref, key=lambda x: x[1]) if t == 10]


def xbox_sampler_names(lib):
    out = {}
    for s in set(lib['slots']):
        if s == 0xffffffff: continue
        for c in XL.parse(lib['entries'][s]['blob']).ctab:
            if c['set'] == 3:
                for j in range(max(1, c.get('count', 1) or 1)): out.setdefault(c['reg'] + j, c['name'])
    return out


def cmd_build(pcf, xf, out, mesh, ids, prefer):
    os.makedirs(out, exist_ok=True)
    _, P = load(pcf, 'le'); _, X = load(xf, 'be')
    pl, xl = mesh_mats(P, mesh, 'le'), mesh_mats(X, mesh, 'be')
    L = libs(); PL = L['P']
    pp = os.path.join(out, "plan.json"); plan = json.load(open(pp)) if os.path.exists(pp) else {}
    for xid in ids:
        lib = tu_lib(xid)
        mats = [(pm, xm) for pm, xm in zip(pl, xl) if struct.unpack_from('>4I', X[(10, xm)].data, 0x28)[2] == xid]
        if not mats: print('d%d: no material of mesh %d uses it' % (xid, mesh)); continue
        # sampler map from the record pairing (identical for every material of the lib, checked)
        smaps = []
        for pm, xm in mats:
            pr, xr = records(P[(10, pm)], 'le'), records(X[(10, xm)], 'be')
            if len(pr) != len(xr): raise SystemExit('material %d: %d PC / %d Xbox records' % (pm, len(pr), len(xr)))
            m = {}
            for (pt, pty, pfl, psl), (xt, xty, xfl, xsl) in zip(pr, xr):
                if m.get(xsl, psl) != psl: raise SystemExit('material %d: Xbox s%d on two PC registers' % (pm, xsl))
                m[xsl] = psl
            smaps.append(m)
        if any(m != smaps[0] for m in smaps): raise SystemExit('d%d: materials disagree on the sampler map %s' % (xid, smaps))
        xnames = xbox_sampler_names(lib)
        smap = smaps[0]
        XPs = [mparams(X[(10, xm)], 'be') for pm, xm in mats]
        print('== d%d materials %s, Xbox sampler -> PC register %s' % (xid, mats, {('s%d %s' % (k, F9.norm_x(xnames.get(k, '?')))): v for k, v in sorted(smap.items())}), flush=True)
        # donor per Xbox slot (both must agree on one donor pair)
        donors = None
        # first candidates: the given ones, then the base Xbox twin(s) of the PC surrogate the material has now
        sur = {struct.unpack_from('<4I', P[(10, pm)].data, 0x28)[2] for pm, xm in mats}
        pref = list(prefer) + [(x_, p_) for x_, p_ in sorted(x2p().items()) if p_ in sur and (x_, p_) not in prefer]
        print('   PC surrogate(s) now %s, preferred donors %s' % (sorted(sur), pref), flush=True)
        for xs_ in (0, 1):
            d = F9.find_donors('D', xid, xs_, want=6, prefer=pref)
            print('   slot %d donors %s' % (xs_, d), flush=True)
            donors = d if donors is None else [p for p in donors if p in d]
        if not donors: print('   d%d: NO common donor' % xid); plan[str(xid)] = dict(error="no donor"); continue
        res = None
        for xs, pd in donors:
            if pd not in PL: continue
            slots = PL[pd]['slots']
            if len(slots) != 8: print('   donor %d/%d: %d PC slots, skipped' % (xs, pd, len(slots))); continue
            bridge = [(m[2], m[3]) for m in f9_common.material_pairs(xs, pd)]
            if not bridge: print('   donor %d/%d: no bridge material' % (xs, pd)); continue
            # x_samp_names: Xbox name -> PC register (material records), engine samplers by the donor's names
            names = {}
            for xr_, n in xnames.items():
                if xr_ in smap: names[n] = smap[xr_]
            built = {}; ok = True; logs = {}
            for k in range(8):
                src = k if slots[k] != 0xffffffff else (k & ~1)
                if slots[src] == 0xffffffff: built[k] = None; continue
                xblob = lib['entries'][lib['slots'][k & 1]]['blob']
                xsblob = L['X'][xs]['entries'][L['X'][xs]['slots'][k & 1]]['blob']
                pdblob = PL[pd]['entries'][slots[src]]['blob']
                log = []
                try:
                    T, info = F9.build(xblob, pdblob, xsblob, bridge, x_samp_names=names, log=log)
                except F9.Fail as e:
                    print('   donor %d/%d slot %d: FAIL %s' % (xs, pd, k, e)); ok = False; break
                except Exception as e:
                    print('   donor %d/%d slot %d: ERR %r' % (xs, pd, k, e)); ok = False; break
                bc, n, off, probs = checks(T, xblob, XPs[0], names)
                logs[k] = dict(src_pd_slot=src, instr=n, lights_off=off, problems=probs, log=log)
                print('   slot %d (Xbox %d, Pd slot %d): %d instr, lights-off match %.3f %s' % (k, k & 1, src, n, off, probs or 'ok'), flush=True)
                if probs: ok = False; break
                built[k] = (T, bc)
            if ok: res = (xs, pd, built, logs, bridge); break
        if res is None: plan[str(xid)] = dict(error='no donor built'); continue
        xs, pd, built, logs, bridge = res
        # donor consensus: the same TU slot 0 / 1 built with every other equivalent donor, VM-compared (real material
        # params of the first material, lights on / off / mixed). Equal = the choice of donor does not matter.
        consensus = {}
        for xs2, pd2 in donors:
            if (xs2, pd2) == (xs, pd) or pd2 not in PL or len(PL[pd2]['slots']) != 8: continue
            for k in (0, 1):
                s2 = PL[pd2]['slots']; src = k if s2[k] != 0xffffffff else (k & ~1)
                if s2[src] == 0xffffffff or built.get(k) is None: continue
                try:
                    br2 = [(m[2], m[3]) for m in f9_common.material_pairs(xs2, pd2)]
                    T2, _ = F9.build(lib['entries'][lib['slots'][k & 1]]['blob'], PL[pd2]['entries'][s2[src]]['blob'],
                                     L['X'][xs2]['entries'][L['X'][xs2]['slots'][k & 1]]['blob'], br2, x_samp_names=names, log=[])
                    r_ = {lab: F9.compare_pc(built[k][0], T2, XPs[0], bools=bl) for lab, bl in
                          (('on', F9.ALLB), ('off', {}), ('mixed', {0: True, 3: True, 6: True}))}
                except Exception as e:
                    r_ = 'FAIL %s' % str(e)[:100]
                consensus['%d/%d s%d' % (xs2, pd2, k)] = r_
                print('   consensus with donor %d/%d slot %d: %s' % (xs2, pd2, k, r_), flush=True)
        ent = dict(donor_xs=xs, donor_pd=pd, donors=donors, consensus=consensus, mats=mats,
                   sampler_map={str(k): v for k, v in smap.items()}, slots={})
        for k, v in built.items():
            if v is None: ent['slots'][str(k)] = None; continue
            T, bc = v
            fn = os.path.join(out, '%d_s%d' % (xid, k))
            open(fn + '.bin', 'wb').write(bc)
            open(fn + '.asm', 'w').write(sm3asm.format_program(T))
            ent['slots'][str(k)] = dict(file=os.path.basename(fn) + '.bin', md5=hashlib.md5(bc).hexdigest(), **{a: b for a, b in logs[k].items()})
        plan[str(xid)] = ent
        json.dump(plan, open(os.path.join(out, 'plan.json'), 'w'), indent=1, default=str)
    json.dump(plan, open(os.path.join(out, 'plan.json'), 'w'), indent=1, default=str)


# ------------------------------------------------------------------------------------------------ pack / apply
def read_plans(dirs):
    out = {}
    for d in dirs:
        p = os.path.join(d, 'plan.json')
        if not os.path.exists(p): print('no plan in %s' % d); continue
        for k, v in json.load(open(p)).items():
            if 'error' in v: print('lib %s: %s (%s)' % (k, v['error'], d)); continue
            v['dir'] = d; out[int(k)] = v
    return out


def drm_hashes(D):
    hs = set()
    for s in D.sections:
        if s.type != 9: continue
        try:
            for e in SL.parse(s.data, 'le')['entries'].values(): hs.add(bytes(e['hash']))
        except Exception: pass
    return hs


def fix_abs_consts(bc):
    """D3DX9 (and the driver rule set, error X6045): an instruction that reads one constant register several times
    must use _abs on all or none of them. xenos2sm3 emits e.g. `cmp r8, -c221.xxxy_abs, r5.zxy, c221.y` (Xbox cndge
    on a literal). When the register is a def literal, the abs operand is folded into a new def (value = swizzle, abs,
    sign applied) - same value, no modifier. Returns (bytecode, number of operands folded)."""
    prog = sm3asm.decode(bc)
    ins = prog.instrs()
    defs = {i.ops[0].num: [struct.unpack('<f', struct.pack('<I', u))[0] for u in i.imm] for i in ins if i.op == 'def'}
    used = {o.num for i in ins for o in i.ops if o.rtype == sm3asm.RT_CONST}
    free = [r for r in range(223, -1, -1) if r not in used and not 100 <= r < 132]
    newdefs = {}; n = 0
    for i in ins:
        if i.op in ('dcl', 'def', 'defi', 'defb'): continue
        srcs = [o for o in i.ops if not o.isdst and o.rtype == sm3asm.RT_CONST and not o.rel]
        by = collections.defaultdict(list)
        for o in srcs: by[o.num].append(o)
        for num, ops in by.items():
            if len(ops) < 2 or len({o.smod in (11, 12) for o in ops}) < 2: continue
            # preferred (keeps one constant register per instruction, f4_lint): give the plain operands _abs too when
            # the def lanes they select are >= 0 (|x| == x) - plain -> abs, neg -> abs_neg
            plain = [o for o in ops if o.smod not in (11, 12)]
            if num in defs and all(o.smod in (0, 1) and all(defs[num][(o.swz >> (2 * l)) & 3] >= 0 for l in range(4)) for o in plain):
                for o in plain: o.smod = 11 if o.smod == 0 else 12
                n += len(plain); continue
            for o in ops:
                if o.smod not in (11, 12): continue
                if num not in defs: raise SystemExit('abs on a uniform constant c%d read twice - not foldable' % num)
                v = [abs(defs[num][(o.swz >> (2 * l)) & 3]) * (-1 if o.smod == 12 else 1) for l in range(4)]
                key = tuple(v)
                if key not in newdefs: newdefs[key] = free.pop(0)
                o.num, o.swz, o.smod = newdefs[key], 0xE4, 0; n += 1
    if not n: return bc, 0
    head = [sm3asm.parse_text('ps_3_0\ndef c%d, %s\n' % (r, ', '.join('%.9g' % x for x in v))).instrs()[0] for v, r in newdefs.items()]
    hdr = [i for i in ins if i.op in ('dcl', 'def', 'defi', 'defb')]; body = [i for i in ins if i.op not in ('dcl', 'def', 'defi', 'defb')]
    p2 = sm3asm.Program(prog.kind, prog.major, prog.minor, hdr + head + body)
    return sm3asm.encode(p2), n


def vm_same(bc_a, bc_b, N=300, seed=9):
    """the same program before / after a rewrite: random inputs / constants / textures, all light bools on and off"""
    A, B = sm3asm.decode(bc_a), sm3asm.decode(bc_b); worst = 1.0
    for bl in ({}, F9.ALLB):
        env = F9.Env(seed)
        a = env.run(A, F9.body(A), env.state0(A), bl); b = env.run(B, F9.body(B), env.state0(B), bl)
        ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
        ok = (np.isclose(ca, cb, rtol=1e-6, atol=1e-7).all(axis=1) & (a[1] == b[1])) | (a[1] & b[1])
        worst = min(worst, float(ok.mean()))
    return worst


def abs_const_operands(bc):
    """number of source operands with an abs / -abs modifier on a constant register (native_extract's ABS_CONST rule)"""
    return sum(1 for i in sm3asm.decode(bc).instrs() if i.op not in ('dcl', 'def', 'defi', 'defb')
               for o in i.ops if not o.isdst and o.rtype == sm3asm.RT_CONST and o.smod in (11, 12))


def fix_abs_native(bc):
    """Windows' own D3D9 (AMD RX 9070 XT, native test 20.10.2026, form ABS_CONST) refuses an abs / -abs source
    modifier on a constant register, e.g. `cmp r8, -|c221.xxxy|, r5.zxyy, |c221.y|` (what fix_abs_consts leaves for
    an Xbox cndge on a literal; the original PC game never uses the form). Rewrite, bit-equivalent (17r, 08.11.2026):
    per instruction and per constant register that the instruction reads with abs, `mov rT, cN` (all four components,
    no modifier, relative addressing kept) is inserted right before it, and EVERY operand of that instruction that
    reads cN reads rT instead (swizzle and modifier kept) - the abs then acts on a temp, which D3D9 allows.
    rT = a temp register the program never uses (only these movs write it, so a temp already holding cN is reused
    without a new mov until the next flow-control instruction; relative reads are always reloaded). The mov is not
    predicated (it only writes rT). The distinct constants per instruction only go down, so no X5584 form
    (two different constant registers in one instruction) is created - unlike folding -|cN| into a new def literal,
    which leaves `cmp r5, c217.zzzy, r7.zxyy, c221.y` (upstream B269 / B270: 500 such shaders). Bytes after the END
    token are kept.
    Fallback when the program uses all 32 temps: if the instruction reads only def literals (no relative addressing
    in the whole program), all its operands of such a register are folded into ONE new def literal, bit for bit
    (float32 sign-bit operations: neg flips, abs clears, -abs sets the sign bit; at most 4 distinct values, lanes
    picked by swizzle), so the instruction reads one constant without modifier; new registers from c223 down, never
    c100..c131 (MaterialParams) or a register the program reads; the same values share one register.
    Returns (bytecode, rewrites: movs inserted + operands folded); (bc, 0) when there is nothing to do; ValueError when
    neither works."""
    prog = sm3asm.decode(bc); tail = prog.trailing
    def ckey(o): return (o.num, o.rel, o.relop.key() if o.relop is not None else None)
    ins_all = prog.instrs()
    used = {o.num for i in ins_all for o in i.ops if o.rtype == sm3asm.RT_TEMP}
    free = [r for r in range(32) if r not in used]
    defs = {i.ops[0].num: list(i.imm) for i in ins_all if i.op == 'def'}
    anyrel = any(o.rel and o.rtype == sm3asm.RT_CONST for i in ins_all for o in i.ops)
    cused = {o.num for i in ins_all for o in i.ops if o.rtype == sm3asm.RT_CONST}
    cfree = [r for r in range(223, -1, -1) if r not in cused and not 100 <= r < 132]
    newdefs = {}
    def lane_bits(o):
        v = [defs[o.num][(o.swz >> (2 * l)) & 3] for l in range(4)]
        if o.smod == 1: return [u ^ 0x80000000 for u in v]
        if o.smod == 11: return [u & 0x7FFFFFFF for u in v]
        if o.smod == 12: return [u | 0x80000000 for u in v]
        if o.smod == 0: return v
        raise ValueError('abs-const fold: source modifier %d' % o.smod)
    # a temp keeps the constant it was loaded with (only these movs write it): the next instruction that needs the same
    # constant reads it without a new mov, until a flow-control instruction (branch / join point); relative reads
    # (c[aL + n], c[a0.x + n]) are always loaded again
    FLOW = {'if', 'ifc', 'else', 'endif', 'loop', 'endloop', 'rep', 'endrep', 'call', 'callnz', 'label', 'ret',
            'break', 'breakc', 'breakp'}
    loaded = {}
    out = []; nmov = 0
    for it in prog.items:
        if not isinstance(it, sm3asm.Instr) or it.op in ('dcl', 'def', 'defi', 'defb'):
            out.append(it); continue
        if it.op in FLOW: loaded.clear()
        srcs = [o for o in it.ops if not o.isdst and o.rtype == sm3asm.RT_CONST]
        need = []
        for o in srcs:
            if o.smod in (11, 12) and ckey(o) not in need: need.append(ckey(o))
        if not need:
            out.append(it); continue
        if len(free) < len(need):
            if anyrel or any(o.num not in defs for o in srcs):
                raise ValueError('abs-const rewrite: %d free temps, %d needed, constants not all def literals' % (len(free), len(need)))
            bits = [lane_bits(o) for o in srcs]
            vals = []
            for b in bits:
                for u in b:
                    if u not in vals: vals.append(u)
            if len(vals) > 4: raise ValueError('abs-const fold: %d distinct values' % len(vals))
            vals += [vals[0]] * (4 - len(vals)); key = tuple(vals)
            if key not in newdefs:
                if not cfree: raise ValueError('abs-const fold: no free constant register')
                newdefs[key] = cfree.pop(0)
            reg = newdefs[key]; m = iter(srcs); bm = iter(bits); ops = []
            for o in it.ops:
                if not o.isdst and o.rtype == sm3asm.RT_CONST:
                    next(m); b = next(bm)
                    o = sm3asm.Operand(sm3asm.RT_CONST, reg, swz=sum(vals.index(u) << (2 * l) for l, u in enumerate(b)), smod=0)
                    nmov += 1
                ops.append(o)
            out.append(sm3asm.Instr(it.op, ops, ctrl=it.ctrl, pred=it.pred, imm=it.imm, usage=it.usage)); continue
        tmap = {}; in_use = set()
        for key in need:
            t = None if key[1] else next((t for t, k in loaded.items() if k == key and t not in in_use), None)
            if t is None:
                cand = [r for r in free if r not in in_use and r not in loaded] or [r for r in free if r not in in_use]
                t = cand[0]
                src = next(o for o in srcs if ckey(o) == key)
                s2 = sm3asm.Operand(sm3asm.RT_CONST, src.num, rel=src.rel, relop=src.relop, swz=0xE4, smod=0, resv=src.resv)
                d2 = sm3asm.Operand(sm3asm.RT_TEMP, t, isdst=True, wm=15)
                out.append(sm3asm.Instr('mov', [d2, s2])); nmov += 1
                loaded[t] = key
            tmap[key] = t; in_use.add(t)
        ops = []
        for o in it.ops:
            if not o.isdst and o.rtype == sm3asm.RT_CONST and ckey(o) in tmap:
                o = sm3asm.Operand(sm3asm.RT_TEMP, tmap[ckey(o)], swz=o.swz, smod=o.smod)
            ops.append(o)
        out.append(sm3asm.Instr(it.op, ops, ctrl=it.ctrl, pred=it.pred, imm=it.imm, usage=it.usage))
        if it.op in FLOW: loaded.clear()
    if not nmov: return bc, 0
    if newdefs:
        last = max(k for k, it in enumerate(out) if isinstance(it, sm3asm.Instr) and it.op in ('dcl', 'def', 'defi', 'defb'))
        nd = [sm3asm.Instr('def', [sm3asm.Operand(sm3asm.RT_CONST, r, isdst=True, wm=15)], imm=list(v)) for v, r in newdefs.items()]
        out = out[:last + 1] + nd + out[last + 1:]
    return sm3asm.encode(sm3asm.Program(prog.kind, prog.major, prog.minor, out)) + tail, nmov


def vm_exact(bc_a, bc_b, seeds=(9, 23, 41), N=300):
    """bit-exact VM comparison of two programs that must compute the same thing (a rewrite such as fix_abs_native):
    random semantic inputs (F9.Env), every float constant random in [-1.5, 1.5] (the sign matters for abs; a def
    literal keeps its own value), deterministic textures, light bools all off and all on, per seed. Every colour
    output oC0..oC3 and oDepth must be equal BITWISE (float32 bit pattern, -0.0 / NaN included) and the kill masks
    equal. -> (True / False, text of the first difference or '')"""
    A, B = sm3asm.decode(bc_a), sm3asm.decode(bc_b)
    outs = [(sm3asm.RT_COLOROUT, k) for k in range(4)] + [(sm3asm.RT_DEPTHOUT, 0)]
    for seed in seeds:
        env = F9.Env(seed, None, N); rng = np.random.RandomState(seed + 1000)
        consts = {r: rng.uniform(-1.5, 1.5, 4).astype(np.float32) for r in range(224)}
        for bl in ({}, F9.ALLB):
            a = f9_common.run_state(A, F9.body(A), env.state0(A), consts, env.tex, N, bl)
            b = f9_common.run_state(B, F9.body(B), env.state0(B), consts, env.tex, N, bl)
            for k in outs:
                va, vb = a[0].get(k), b[0].get(k)
                if (va is None) != (vb is None): return False, 'seed %d: output %s only on one side' % (seed, k)
                if va is None: continue
                if not np.array_equal(np.ascontiguousarray(va, np.float32).view(np.uint32),
                                      np.ascontiguousarray(vb, np.float32).view(np.uint32)):
                    return False, 'seed %d bools %s: output %s differs' % (seed, 'on' if bl else 'off', k)
            ka = a[1] if a[1] is not None else np.zeros(N, bool); kb = b[1] if b[1] is not None else np.zeros(N, bool)
            if not np.array_equal(ka, kb): return False, 'seed %d: kill masks differ' % seed
    return True, ''


def cmd_pack(dirs, pcf, out, ids_new):
    import fade_slots_translate as FST
    os.makedirs(out, exist_ok=True)
    plans = read_plans(dirs)
    D = DW.read(open(pcf, 'rb').read(), 'le')
    have9 = {s.id for s in D.sections if s.type == 9}
    taken = FST.known_hashes() | drm_hashes(D)
    order = sorted(plans)
    if len(ids_new) < len(order): raise SystemExit('%d libs, %d new ids' % (len(order), len(ids_new)))
    mp = {}; lines = []
    for xid, nid in zip(order, ids_new):
        if nid in have9: raise SystemExit('id %d already in the file' % nid)
        v = plans[xid]; sb = []; uniq = {}; fixes = {}
        for k in range(8):
            s = v['slots'].get(str(k))
            if s is None: sb.append(None); continue
            bc0 = open(os.path.join(v['dir'], s['file']), 'rb').read()
            bc, nf = fix_abs_consts(bc0)
            if nf:
                same = vm_same(bc0, bc)
                if same < 1.0: raise SystemExit('lib %d slot %d: abs fold changed the result (%.3f)' % (xid, k, same))
                fixes[k] = nf
            bc1 = bc; bc, na = fix_abs_native(bc1)          # 17r: no abs on a constant (native D3D9, AMD)
            if na:
                same, why = vm_exact(bc1, bc)
                if not same: raise SystemExit('lib %d slot %d: abs-const rewrite changed the result (%s)' % (xid, k, why))
                fixes[k] = '%s+%d mov' % (fixes.get(k, 0), na)
            if bc not in uniq:
                ok, txt, err = FST.valid(bc)
                if not ok: raise SystemExit('lib %d slot %d not valid: %s' % (xid, k, err))
                uniq[bc] = FST.new_hash(b'test50a|' + bc, taken)
            sb.append((uniq[bc], bc, None))
        data = FST.pc_lib(1, sb, 0)
        lib = SL.parse(data, 'le')
        assert len(lib['slots']) == 8 and all(lib['slots'][k] != 0xffffffff for k in range(8) if sb[k] is not None)
        open(os.path.join(out, '%d.lib' % nid), 'wb').write(data)
        mp[str(xid)] = dict(new=nid, mats=v['mats'], donor='%d/%d' % (v['donor_xs'], v['donor_pd']),
                            slots=[k for k in range(8) if sb[k] is not None], unique=len(uniq), md5=hashlib.md5(data).hexdigest())
        lines.append('TU %d -> new lib %d: %d slots (%d unique, all D3DX9 + f4_lint valid; abs-const folds per slot %s), donor Xs/Pd %d/%d, materials %s, %d bytes'
                     % (xid, nid, len(mp[str(xid)]['slots']), len(uniq), fixes or 'none', v['donor_xs'], v['donor_pd'], [m[0] for m in v['mats']], len(data)))
    json.dump(mp, open(os.path.join(out, 'map.json'), 'w'), indent=1)
    open(os.path.join(out, 'pack.txt'), 'w').write('\n'.join(lines) + '\n'); print('\n'.join(lines))


def grow_params(s, vals):
    """write MaterialParams (PS block) = vals; the block grows in place when the Xbox has more vec4 than the PC
    material (bytes inserted at the block end, internal pointers / targets and id-reference offsets behind it moved)."""
    r = R.parse(s.reloc, 'le')
    o = dict(r.internal).get(0x5C); n = struct.unpack_from('<I', s.data, 0x58)[0]
    if o is None: raise SystemExit('material %d: no params block' % s.id)
    d = bytearray(s.data); info = ''
    if len(vals) > n:
        at = o + 16 * n; add = 16 * (len(vals) - n)
        # nothing of the block may be pointed at from inside [o, at) except the block start
        d[at:at] = bytes(add)
        # 50m fix: with an EMPTY PC block (n == 0, e.g. effect materials 20744 / 24958: Xbox 7, PC 0) the insert point is
        # the block start itself, and the +0x5C pointer (target == at) must stay there - before, it moved with the data
        # behind it and pointed at the texture records (test 50l, Befund-Shader-Nacht part 2). n > 0: unchanged rule.
        r.internal = [(a + add if a >= at else a, b + add if (b > at or (b == at and not (a == 0x5C and n == 0))) else b)
                      for a, b in r.internal]
        r.idref = [(t, off + add if off >= at else off) for t, off in r.idref]
        r.idref_a = [(t, off + add if off >= at else off) for t, off in r.idref_a]
        if r.external: raise SystemExit('material %d has external pointers' % s.id)
        s.reloc = R.write(r, 'le'); info = 'grown %d -> %d vec4 (+%d bytes at +%#x)' % (n, len(vals), add, at)
        n = len(vals)
    struct.pack_into('<I', d, 0x58, max(n, len(vals)))
    old = [struct.unpack_from('<4f', d, o + 16 * j) for j in range(n)]
    for j, v in enumerate(vals): struct.pack_into('<4f', d, o + 16 * j, *v)
    s.data = bytes(d)
    return old, info


def cmd_apply(src, xf, out, packd):
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    _, X = load(xf, 'be')
    mp = json.load(open(os.path.join(packd, 'map.json')))
    have = {s.id for s in D.sections if s.type == 9}
    # every DRM section that points INTO a material with an external pointer would break when it grows: refuse
    mat_idx = {i for i, s in enumerate(D.sections) if s.type == 10}
    for s in D.sections:
        for si, so, do in R.parse(s.reloc, 'le').external:
            if si in mat_idx: raise SystemExit('section %d:%d points into material section %d' % (s.type, s.id, si))
    secs = {(s.type, s.id): s for s in D.sections}
    added = []; changed = {}
    for xid, v in sorted(mp.items(), key=lambda kv: int(kv[0])):
        nid = v['new']
        if nid in have: raise SystemExit('lib %d already in the file' % nid)
        data = open(os.path.join(packd, '%d.lib' % nid), 'rb').read()
        pm0 = v['mats'][0][0]; cur = struct.unpack_from('<4I', secs[(10, pm0)].data, 0x28)[2]
        old = secs[(9, cur)]
        D.sections.insert(D.sections.index(old) + 1, DW.Section(9, nid, data, b'', flags=old.flags, ver=old.ver, spec=old.spec, pad=old.pad))
        added.append(nid)
        for pm, xm in v['mats']:
            s = secs[(10, pm)]
            refs = set(R.parse(s.reloc, 'le').idref)
            if (9, 0x30) not in refs: raise SystemExit('material %d: +0x30 is not a ShaderLib reference' % pm)
            d = bytearray(s.data); was = struct.unpack_from('<I', d, 0x30)[0]
            struct.pack_into('<I', d, 0x30, nid); s.data = bytes(d)
            xv = mparams(X[(10, xm)], 'be')
            oldp, info = grow_params(s, xv)
            diffs = ['MP[%d] %s -> %s' % (j, tuple(round(c, 4) for c in oldp[j]), tuple(round(c, 4) for c in xv[j]))
                     for j in range(min(len(oldp), len(xv))) if any(abs(oldp[j][c] - xv[j][c]) > 1e-6 for c in range(4))]
            changed[pm] = 'p2 %d -> %d; params = Xbox %d vec4 %s; %s' % (was, nid, len(xv), info or '(size kept)', '; '.join(diffs) or 'values already equal')
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    rest = [s for s in B if not (s.type == 9 and s.id in added)]
    assert len(rest) == len(A)
    diff = [(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc) != (b.type, b.id, b.data, b.reloc)]
    assert set(diff) == {(10, m) for m in changed}, diff
    for nid in added:
        s = next(x for x in B if x.type == 9 and x.id == nid)
        assert s.data == open(os.path.join(packd, '%d.lib' % nid), 'rb').read()
    for m in sorted(changed): print('material %d: %s' % (m, changed[m]))
    print('readback: %d original sections in order, %d materials changed, %d new ShaderLibs %s' % (len(A), len(changed), len(added), added))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (out, hashlib.md5(o).hexdigest(), len(o)))


def vs_outputs(lib):
    """per occupied VS slot: set of output (usage, index)"""
    out = {}
    for k, s in enumerate(lib['slots']):
        if s == 0xffffffff: continue
        b = lib['entries'][s]['blob']; prog = sm3asm.decode(b[:sm3dis.bytecode_len(b)])
        out[k] = {((i.usage & 31), (i.usage >> 16) & 15) for i in prog.instrs() if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT}
    return out


def cmd_vscheck(dirs, pcf):
    """translated PS input semantics against the outputs of the material's PC vertex shader (every VS slot that writes
    texcoords): a PS input no VS slot writes would read garbage"""
    _, P = load(pcf, 'le')
    for xid, v in sorted(read_plans(dirs).items()):
        need = set()
        for k, s in v['slots'].items():
            if s is None: continue
            prog = sm3asm.decode(open(os.path.join(v['dir'], s['file']), 'rb').read())
            ins, vmap = inputs_of(prog); need |= {x for x in ins if x[0] != 'misc'}
        for pm, xm in v['mats']:
            vid = struct.unpack_from('<4I', P[(10, pm)].data, 0x28)[3]
            vl = SL.parse(P[(9, vid)].data, 'le')
            outs = vs_outputs(vl)
            full = [k for k, o in outs.items() if len(o) > 2]
            miss = {k: sorted(need - outs[k]) for k in full if need - outs[k]}
            print('TU %d material %d VS %d: PS reads %s; VS slots with outputs %d, missing in %d slots%s'
                  % (xid, pm, vid, sorted(need), len(full), len(miss), (': %s' % dict(list(miss.items())[:4])) if miss else ''))


def cmd_relaxed(xid, slot, tol):
    """donor search without f9's prefilter on the number of MaterialParams inputs (only: same number of block outputs,
    block length within tol): match_blocks + verify_blocks against every base lit pair, best scores printed"""
    me = F9.xblock_info('D', xid, slot)
    if me is None: print('d%d: no light block' % xid); return
    prog, i0, i1, ins, outs = me
    env = F9.Env(2); res = []
    for xs, pd in F9.lit_pairs():
        o = F9.xblock_info('X', xs, slot)
        if o is None: continue
        pB, b0, b1, inB, outB = o
        if len(outB) != len(outs) or abs((b1 - b0) - (i1 - i0)) > tol * (i1 - i0): continue
        try:
            im, om = F9.match_blocks(prog, i0, i1, ins, outs, pB, b0, b1, inB, outB, env)
            v = F9.verify_blocks(prog, i0, i1, ins, outs, pB, b0, b1, inB, outB, im, om, env)
            res.append((v, xs, pd, b1 - b0, len(inB)))
            print('  x%d/p%d: block %d instr, in %d -> verify %.3f' % (xs, pd, b1 - b0, len(inB), v), flush=True)
        except F9.Fail as e:
            res.append((-1, xs, pd, b1 - b0, len(inB)))
    res.sort(reverse=True)
    print('d%d slot %d (block %d instr, in %d, out %d): %d candidates tried, best %s'
          % (xid, slot, i1 - i0, len(ins), len(outs), len(res), res[:5]))


def cmd_blockcmp(xid, cands):
    """light block of DLC lib xid slot 0 against base Xbox libs: sizes, inputs / outputs, equivalence score"""
    me = F9.xblock_info('D', xid, 0)
    if me is None: print('d%d: no light block' % xid); return
    prog, i0, i1, ins, outs = me
    print('d%d: block [%d,%d) %d instr, in %d (MP %d) out %d' % (xid, i0, i1, i1 - i0, len(ins), sum(1 for i in ins if len(i) == 3), len(outs)))
    env = F9.Env(2)
    for xs in cands:
        o = F9.xblock_info('X', xs, 0)
        if o is None: print('  x%d: no block' % xs); continue
        pB, b0, b1, inB, outB = o
        line = '  x%d: block %d instr, in %d (MP %d) out %d' % (xs, b1 - b0, len(inB), sum(1 for i in inB if len(i) == 3), len(outB))
        try:
            im, om = F9.match_blocks(prog, i0, i1, ins, outs, pB, b0, b1, inB, outB, env)
            line += ' match ok, verify %.3f' % F9.verify_blocks(prog, i0, i1, ins, outs, pB, b0, b1, inB, outB, im, om, env)
        except F9.Fail as e:
            line += ' FAIL %s' % str(e)[:120]
        print(line, flush=True)


def cmd_diag(pcf, xf, mesh, xid, slot, donors):
    """one TU lib / PC slot built with several donors: transplant log (input / output / MaterialParams matching) and
    the VM difference per output lane against the first donor (lights on)"""
    _, P = load(pcf, 'le'); _, X = load(xf, 'be')
    pl, xl = mesh_mats(P, mesh, 'le'), mesh_mats(X, mesh, 'be')
    L = libs(); PL = L['P']; lib = tu_lib(xid)
    pm, xm = next((p, x) for p, x in zip(pl, xl) if struct.unpack_from('>4I', X[(10, x)].data, 0x28)[2] == xid)
    pr, xr = records(P[(10, pm)], 'le'), records(X[(10, xm)], 'be')
    smap = {x[3]: p[3] for p, x in zip(pr, xr)}
    names = {n: smap[r] for r, n in xbox_sampler_names(lib).items() if r in smap}
    XP = mparams(X[(10, xm)], 'be'); print('material %d Xbox MP %s' % (pm, [tuple(round(c, 3) for c in v) for v in XP]))
    progs = []
    for xs, pd in donors:
        s2 = PL[pd]['slots']; src = slot if s2[slot] != 0xffffffff else (slot & ~1)
        br = [(m[2], m[3]) for m in f9_common.material_pairs(xs, pd)]
        log = []
        T, _ = F9.build(lib['entries'][lib['slots'][slot & 1]]['blob'], PL[pd]['entries'][s2[src]]['blob'],
                        L['X'][xs]['entries'][L['X'][xs]['slots'][slot & 1]]['blob'], br, x_samp_names=names, log=log)
        print('--- donor %d/%d (Pd slot %d), %d bridge materials' % (xs, pd, src, len(br)))
        for l in log: print('   ' + l)
        progs.append(T)
    env = F9.Env(5, XP)
    outs = [env.run(T, F9.body(T), env.state0(T), F9.ALLB)[0].get((sm3asm.RT_COLOROUT, 0)) for T in progs]
    for (xs, pd), o in zip(donors[1:], outs[1:]):
        d = np.abs(o - outs[0])
        print('donor %d/%d vs %d/%d: max |diff| per lane %s, mean ratio new/first per lane %s'
              % (xs, pd, donors[0][0], donors[0][1], np.round(np.nanmax(d, axis=0), 4),
                 np.round(np.nanmean(o / (outs[0] + 1e-6), axis=0), 3)))


def cmd_lightdiag(xb, pb, xs, pd, slot):
    """base oracle case: transplant of Xbox xb with donor xs/pd against the real PC twin pb, one PC light bool at a time
    (b0-b2 shadow lights, b3-b5 non-shadow lights, b6), per lane max |diff|; plus Pd against Pb directly"""
    L = libs(); X, PL = L['X'], L['P']
    xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']; xsblob = X[xs]['entries'][X[xs]['slots'][slot & 1]]['blob']
    pdblob = PL[pd]['entries'][PL[pd]['slots'][slot]]['blob']; pbblob = PL[pb]['entries'][PL[pb]['slots'][slot]]['blob']
    mb = f9_common.material_pairs(xs, pd); mt = f9_common.material_pairs(xb, pb)
    xnames = {n: ri for n, rs, ri, rc in F9.pc_ctab(pbblob) if rs == 3}
    log = []
    T, info = F9.build(xblob, pdblob, xsblob, [(m[2], m[3]) for m in mb], x_samp_names=xnames, log=log)
    Pb = F9.decode_pc(pbblob)
    for l in log: print('   ' + l)
    env = F9.Env(5, mt[0][3])
    for lab, bl in [('none', {})] + [('b%d' % b, {b: True}) for b in range(7)] + [('all', F9.ALLB)]:
        a = env.run(T, F9.body(T), env.state0(T), bl)[0].get((sm3asm.RT_COLOROUT, 0))
        b = env.run(Pb, F9.body(Pb), env.state0(Pb), bl)[0].get((sm3asm.RT_COLOROUT, 0))
        ok = np.isclose(a, b, **F9.TOL).all(axis=1).mean()
        print('  %-4s match %.3f  max|diff| %s  mean T/Pb %s' % (lab, ok, np.round(np.nanmax(np.abs(a - b), axis=0), 4),
                                                                 np.round(np.nanmean(a / (b + 1e-6), axis=0), 3)))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == "relaxed": cmd_relaxed(int(a[1]), int(a[2]), float(a[3])); return
    if a[0] == "lightdiag":
        cmd_lightdiag(*[int(x) for x in a[1:6]]); return
    if a[0] == 'diag':
        cmd_diag(a[1], a[2], int(a[3]), int(a[4]), int(a[5]), [tuple(int(y) for y in x.split('/')) for x in a[6].split(',')]); return
    if a[0] == "oracle":
        sys.argv = ["f9", "oracolo"] + a[1:3]; F9.main(); return
    if a[0] == "blockcmp": cmd_blockcmp(int(a[1]), [int(x) for x in a[2].split(',')]); return
    if a[0] == 'pack':
        k = a.index('--ids'); ids = [int(x) for x in a[k + 1].split(',')]; rest = a[1:k] + a[k + 2:]
        cmd_pack(rest[2:], rest[0], rest[1], ids); return
    if a[0] == 'apply': cmd_apply(a[1], a[2], a[3], a[4]); return
    if a[0] == 'vscheck': cmd_vscheck(a[2:], a[1]); return
    if a[0] == 'donors':
        want = int(a[a.index('--want') + 1]) if '--want' in a else 3
        cmd_donors([int(x) for x in a[1].split(',')], want)
    elif a[0] == 'build':
        mesh = int(a[a.index('--mesh') + 1]); ids = [int(x) for x in a[a.index('--libs') + 1].split(',')]
        prefer = []
        if '--prefer' in a: prefer = [tuple(int(y) for y in x.split('/')) for x in a[a.index('--prefer') + 1].split(',')]
        cmd_build(a[1], a[2], a[3], mesh, ids, prefer)
    elif a[0] == 'oracle-pair':
        sys.argv = ['f9', 'coppia', a[1], a[2], '0']; F9.main()
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
