"""Translate the DLC 2 fall-column shaders to PC (finding 43, test 46): material 24691 of dlc_level2_start.drm uses on
the Xbox the DLC's own ShaderLibs 2457 (pass 0) / 2458 (pass 2) / 2459 (vertex shader); the PC port had surrogates
1909 / 1910 / 1911 (PC versions of base Xbox 1065 / 1066 / 1067, the l7 yggdrasil refraction set).

Method (docs: Befund-Wasserfall.md "Test 46"):
* Vertex shader, rule of three. Xbox 2459 = base Xbox 1064 (same text) in every position-only permutation, and =
  base Xbox 1067 + the vertex-wave prelude of 1064 in the permutations that write interpolators. Base Xbox 1064 -> PC
  1908 and 1067 -> PC 1911 are known pairs, so: PC slot k = PC 1908 slot k (verbatim) where Xbox 2459 k == 1064 k,
  else PC 1911 slot k with the wave slice of PC 1908 slot k inserted (the instructions that compute the displaced
  position) and every read of the position input redirected to the displaced position. Checked numerically with the
  SM3 VM: oPos equals PC 1908's, every other output equals PC 1911's run on the displaced position.
* Pixel shaders (no base twin): upstream's Xenos -> ps_3_0 translator (work/ws/shader4/xenos2sm3.py, validated
  upstream against XenosRecomp) with the PC register conventions (one register per constant name on PC, counted over
  all base PC libraries; CameraPosition -> g_CameraPosition, TimeVector -> TimeVectorPS), sampler registers mapped to
  the PC material's texture records (same texture id and same sampler name in the surrogate), DXN normal maps read as
  y = alpha (our DXN -> DXT5 conversion). PC slot k of the surrogate lib <- Xbox slot k & 1 (checked: the PC slots
  that carry MaterialOpacity are the ones whose Xbox slot carries it).

Usage (from the repository root; TRUDLC_PACK_FIRST=pack11 for DLC 2 Xbox sources):
  ../bin/pyt -t 900 tools/column_shader_translate.py build PC_DRM OUT_DIR [--mat 24691]
      writes OUT_DIR/ps0.lib, ps2.lib, vs.lib (ShaderLib section data, PC layout), OUT_DIR/asm/*.asm, OUT_DIR/build.txt
  ../bin/pyt -t 300 tools/column_shader_translate.py apply IN.drm OUT.drm OUT_DIR PS0_ID PS2_ID VS_ID [--mat 24691] [--keep-ps0]
      adds the libs as ShaderLib sections with the given (free) ids and points the material's slots at them
      (--keep-ps0: pass 0 stays on the surrogate)
"""
import sys, os, struct, pickle, hashlib, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
S4 = os.path.join(ROOT, 'work', 'ws', 'shader4')
sys.path.insert(0, HERE); sys.path.insert(0, S4); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
import drm_write as DW, drm_reloc as R, shaderlib as SL
import xenos_xlat as XL, xenos2sm3, sm3asm, sm3dis, sm3vm, sm3opt
from sm3asm import Instr, Operand, Comment, RT_TEMP, RT_INPUT, RT_CONST, RT_RAST, RT_ATTR, RT_TEXOUT, RT_SAMPLER
import shader_disasm as SD, shader_validate as SV

W = os.path.join(ROOT, 'work', 'render')

# Fix for upstream's translator (work/ws/shader4/xenos2sm3.py, not edited): Tr.alu_body runs the vector op only when
# the vector write mask is non-zero, so a vector kill_* whose instruction writes nothing (e.g. 2457 slot 1:
# `clip(any(c255.x > -AlphaThreshold.x))` in an export instruction whose lanes all come from the scalar unit) was
# dropped. Xenos (XenosRecomp / xenos_xlat) executes the kill regardless of the write mask.
_alu_body = xenos2sm3.Tr.alu_body


def _alu_body_kill(self, f, pred):
    v = XL.VOP[f['vopc']]; vm = f['vmask']
    if f['export']: vm &= ~f['smask']
    if v.startswith('kill_') and not vm:
        self.kill_vector(f, v); self.notes.append('vector %s with empty write mask executed (upstream drops it)' % v)
    return _alu_body(self, f, pred)


xenos2sm3.Tr.alu_body = _alu_body_kill
ALIAS = {'CameraPosition': 'g_CameraPosition', 'TimeVector': 'TimeVectorPS'}
DXN_X = 0x31                      # Xenos texture format DXN (low 6 bits of the texture header word +4)
DXT5_PC = 0x35545844
LOG = []
PARAMS = None                     # MaterialParams of the material (set by cmd_build, used by the VM check)


def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.append(s)


def libs():
    L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
    L['x2p'] = pickle.load(open(os.path.join(W, 'shader_x2p.pkl'), 'rb'))
    return L


def trim(b): return b[:sm3dis.bytecode_len(b)]


def occ(lib): return [i for i, s in enumerate(lib['slots']) if s != 0xffffffff]


def blob(lib, k): return lib['entries'][lib['slots'][k]]['blob']


def xtext(b): return XL.text(XL.parse(b), 'pretty').lines


# ------------------------------------------------------------------------------------------------ material data
def mat_info(d, rb, e):
    r = R.parse(rb, 'be' if e == '>' else 'le'); it = dict(r.internal)
    tp, pp = it.get(0x54), it.get(0x5C)
    recs = {}
    for k in range(d[0x52]):
        tid, u1, typ, b0, slot, filt = struct.unpack_from(e + 'IIIBBH', d, tp + 16 * k)
        recs.setdefault(slot, []).append((tid, b0))
    n = struct.unpack_from(e + 'I', d, 0x58)[0]
    params = [struct.unpack_from(e + '4f', d, pp + 16 * i) for i in range(n)]
    return struct.unpack_from(e + '4I', d, 0x28), recs, params


def pc_regs(L, kind):
    """{constant name: register} for PC libs of one kind (0 VS, 1 PS): the start register each name has (asserted
    unique over every base PC library)"""
    cnt = collections.defaultdict(collections.Counter)
    for lib in L['P'].values():
        if lib['kind'] != kind: continue
        for o in set(s for s in lib['slots'] if s != 0xffffffff):
            for n, rs, ri, rc in SL.constants(lib['entries'][o]['blob'], 'p')[1]:
                if rs == 2: cnt[n][ri] += 1
    out = {}
    for n, c in cnt.items():
        out[n] = c.most_common(1)[0][0]
        if len(c) > 1: log('  note: PC %s constant %s has several registers %s' % (('VS', 'PS')[kind], n, dict(c)))
    return out


def xbox_tex_formats(name):
    import convert_dlc
    raw, pk = convert_dlc.raw_dlc(name)
    if raw is None: return {}, None
    D = DW.read(raw, 'be')
    return {s.id: struct.unpack_from('>I', s.data, 4)[0] & 0x3f for s in D.sections if s.type == 5}, pk


# ------------------------------------------------------------------------------------------------ pixel shaders
def translate_ps(L, xid, pc_sur, PC, cregs, sampmap, dxn, tag, outd):
    """-> list of PC slot bytecodes (None = empty) in the surrogate's slot layout"""
    X = L['D'][xid]; P = L['P'][pc_sur]
    def cfn(name, j, count):
        r = cregs.get(ALIAS.get(name, name))
        return None if r is None else r + j
    xs = {}
    for k in occ(X):
        b = blob(X, k)
        names = {c['reg']: c['name'] for c in XL.parse(b).ctab if c['set'] == 3}
        def samp(n, c, names=names):
            return sampmap.get(c)
        used_dxn = {sampmap[r] for r in dxn if r in sampmap}
        t = xenos2sm3.translate(b, cfn, bools=None, samp=samp, opts={'dxn': used_dxn} if used_dxn else {})
        prog = t.prog; bc = sm3asm.encode(prog)
        import f4_lint
        errs = f4_lint.lint(bc, True)
        txt = SD.disasm(bc); ok, msg = SV.assemble(txt)
        open(os.path.join(outd, 'asm', '%s_x%d_s%d.asm' % (tag, xid, k)), 'w').write(txt)
        log('  %s Xbox %d slot %d: %d instructions, consts %s, samplers %s, inputs %s, lint %s, D3DX reassembly %s%s'
            % (tag, xid, k, t.ninstr, sorted(t.consts), {r: n[:40] for r, n in sorted(t.samplers.items())},
               sorted(t.inputs), errs or 'ok', 'ok' if ok and not msg.strip() else 'FAILED', (' ' + msg.strip()[:300]) if msg.strip() else ''))
        for n in t.notes: log('     note: %s' % n)
        if errs or not ok: raise SystemExit('%s: translated shader not valid' % tag)
        if PARAMS:   # VM run with the material's own constants: finite colour, alpha range, kill count
            N = 512; rng = np.random.RandomState(7)
            inp = {}
            for i in prog.instrs():
                if i.op == 'dcl' and i.ops[0].rtype == RT_INPUT:
                    a = rng.uniform(-1, 1, (N, 4)).astype(np.float32)
                    if (i.usage & 31) == 10: a = np.abs(a)
                    if (i.usage & 31, (i.usage >> 16) & 15) == (5, 5): a *= 300
                    inp[(RT_INPUT, i.ops[0].num)] = a
            cs = {100 + j: np.array(v, np.float32) for j, v in enumerate(PARAMS)}
            cs.update({98: np.array([0.8, 0.8, 0.8, 0.8], np.float32), 53: np.array([12.5, 0, 0, 0], np.float32),
                       1: np.array([10, 20, 30, 1], np.float32), 2: np.array([0.5, 0, 0, 0], np.float32)})
            r = sm3vm.run(prog, inp, cs, sm3vm.det_tex(lambda s: s), N)
            c = r.get('oC0')
            log('     VM (material constants, random interpolators): oC0 finite %s, rgb %.3f..%.3f, alpha %.3f..%.3f, killed %d / %d'
                % (bool(np.all(np.isfinite(c))), float(c[:, :3].min()), float(c[:, :3].max()), float(c[:, 3].min()), float(c[:, 3].max()),
                   int(np.sum(r['kill'])) if r['kill'] is not None else 0, N))
        xs[k] = (bc, t)
    out = []
    for k, s in enumerate(P['slots']):
        if s == 0xffffffff: out.append(None); continue
        out.append(xs[k & 1][0] if (k & 1) in xs else None)
    return out, xs


def opacity_slot_check(L, xid, pid):
    """PC slot k <- Xbox slot k & 1: the PC slots with MaterialOpacity must be the ones whose Xbox slot has it"""
    X, P = L['X'][xid], L['P'][pid]
    hx = {k: any(n == 'MaterialOpacity' for n, *_ in SL.constants(blob(X, k), 'x')[1]) for k in occ(X)}
    hp = {k: any(n == 'MaterialOpacity' for n, *_ in SL.constants(blob(P, k), 'p')[1]) for k in occ(P)}
    bad = [k for k in hp if hx.get(k & 1) != hp[k]]
    log('  slot rule k -> k&1 on base pair Xbox %d / PC %d: Xbox opacity %s, PC opacity %s, mismatches %s' % (xid, pid, hx, hp, bad or 'none'))
    return not bad


# ------------------------------------------------------------------------------------------------ CTAB
def ctab_parse(prog):
    for it in prog.items:
        if isinstance(it, Comment) and it.payload[:4] == b'CTAB':
            d = it.payload[4:]
            size, creator, version, n, cinfo, flags, target = struct.unpack_from('<7I', d, 0)
            ents = []
            for k in range(n):
                no, rs, ri, rc, res, ti, dv = struct.unpack_from('<IHHHHII', d, cinfo + 20 * k)
                name = d[no:d.index(b'\0', no)].decode('latin1')
                tinfo = d[ti:ti + 16]
                ents.append((name, rs, ri, rc, tinfo))
            cr = d[creator:d.index(b'\0', creator)]; tg = d[target:d.index(b'\0', target)]
            return dict(ents=ents, creator=cr, target=tg, version=version, flags=flags)
    return None


def ctab_build(ct):
    """D3DXSHADER_CONSTANTTABLE (type infos without struct members: copied 16-byte records)"""
    ents = sorted(ct['ents'], key=lambda e: e[0])
    n = len(ents); hdr = 28; cinfo = hdr; p = cinfo + 20 * n
    blob = bytearray(); offs = []
    for name, rs, ri, rc, tinfo in ents:
        to = p + len(blob); blob += tinfo
        no = p + len(blob); blob += name.encode('latin1') + b'\0'
        while len(blob) % 4: blob += b'\xab'
        offs.append((no, to))
    cr = p + len(blob); blob += ct['creator'] + b'\0'
    while len(blob) % 4: blob += b'\xab'
    tg = p + len(blob); blob += ct['target'] + b'\0'
    while len(blob) % 4: blob += b'\xab'
    out = bytearray(struct.pack('<7I', hdr, cr, ct['version'], n, cinfo, ct['flags'], tg))
    for (name, rs, ri, rc, tinfo), (no, to) in zip(ents, offs):
        out += struct.pack('<IHHHHII', no, rs, ri, rc, 0, to, 0)
    out += blob
    return Comment(b'CTAB' + bytes(out))


# ------------------------------------------------------------------------------------------------ vertex shader merge
def dcl_map(prog):
    """{(usage, index): input register number} and the position input register"""
    m = {}
    for i in prog.instrs():
        if i.op == 'dcl' and i.ops[0].rtype == RT_INPUT: m[(i.usage & 31, (i.usage >> 16) & 15)] = i.ops[0].num
    return m


def body(prog): return [i for i in prog.instrs() if i.op not in ('dcl', 'def', 'defi', 'defb')]


def wave_slice(B):
    """-> (instructions of PC 1908's slot that compute the displaced position, the final instruction W)"""
    dm = dcl_map(B); vpos = dm[(0, 0)]
    bb = body(B)
    wi = next(k for k, i in enumerate(bb) if i.op == 'mad' and i.ops[0].rtype == RT_TEMP and i.ops[0].wm == 7
              and i.ops[3].rtype == RT_INPUT and i.ops[3].num == vpos)
    need = set()
    W_ = bb[wi]
    for j in (1, 2, 3):
        o = W_.ops[j]
        if o.rtype == RT_TEMP:
            for c in sm3opt.lanes_read(W_, j, W_.ops[0].wm)[0]: need.add((o.num, c))
    keep = []
    for i in reversed(bb[:wi]):
        d = i.ops[0] if i.ops else None
        if d is None or not d.isdst or d.rtype != RT_TEMP: continue
        wr = {(d.num, c) for c in range(4) if d.wm >> c & 1}
        if not (wr & need): continue
        keep.append(i); need -= wr
        for j in range(1, len(i.ops)):
            o = i.ops[j]
            if o.rtype == RT_TEMP:
                for c in sm3opt.lanes_read(i, j, d.wm)[0]: need.add((o.num, c))
    if need: raise SystemExit('wave slice: temps read before written %s' % sorted(need))
    return list(reversed(keep)), W_


def clone_op(o, **kw):
    n = Operand(o.rtype, o.num, o.isdst, o.rel, o.relop, o.wm, o.mod, o.shift, o.swz, o.smod, o.resv)
    for k, v in kw.items(): setattr(n, k, v)
    return n


def merge_vs(A, B, label):
    """PC 1911 slot program A + wave slice of PC 1908 slot program B -> new program"""
    sl, W_ = wave_slice(B)
    da, db = dcl_map(A), dcl_map(B)
    vposA = da[(0, 0)]
    maxt = max([o.num for i in A.instrs() for o in i.ops if o.rtype == RT_TEMP] + [-1])
    tmap = {}
    def nt(n):
        if n not in tmap: tmap[n] = maxt + 1 + len(tmap)
        return tmap[n]
    defsA = {i.ops[0].num for i in A.instrs() if i.op == 'def'}
    defsB = {i.ops[0].num: i for i in B.instrs() if i.op == 'def'}
    cta, ctb = ctab_parse(A), ctab_parse(B)
    usedA = set(defsA)
    for name, rs, ri, rc, ti in cta['ents']:
        if rs == 2: usedA |= set(range(ri, ri + rc))
    namesA = {e[0]: e for e in cta['ents']}
    cmap = {}; newdefs = []; newdcl = []; vmap = {}
    free = [r for r in range(253, 7, -1) if r not in usedA]
    inv_b = {v: k for k, v in db.items()}
    def cv(o):
        if o.rtype == RT_TEMP: return clone_op(o, num=nt(o.num))
        if o.rtype == RT_INPUT:
            key = inv_b[o.num]
            if key not in da and key not in vmap:
                vmap[key] = max(list(da.values()) + list(vmap.values())) + 1
                newdcl.append(Instr('dcl', [Operand(RT_INPUT, vmap[key], isdst=True, wm=15)], usage=key[0] | (key[1] << 16) | 0))
            return clone_op(o, num=da.get(key, vmap.get(key)))
        if o.rtype == RT_CONST:
            if o.num in defsB:
                if o.num not in cmap:
                    cmap[o.num] = free.pop(0)
                    d = defsB[o.num]; newdefs.append(Instr('def', [clone_op(d.ops[0], num=cmap[o.num])], imm=list(d.imm)))
                return clone_op(o, num=cmap[o.num])
            # a named constant of 1908: same register on PC by convention; must not collide with another name in A
            nb = next((e for e in ctb['ents'] if e[1] == 2 and e[2] <= o.num < e[2] + e[3]), None)
            if nb is None: raise SystemExit('%s: constant c%d of 1908 not in its CTAB' % (label, o.num))
            for e in cta['ents']:
                if e[1] == 2 and e[2] <= o.num < e[2] + e[3] and e[0] != nb[0]:
                    raise SystemExit('%s: c%d is %s in 1911 but %s in 1908' % (label, o.num, e[0], nb[0]))
            return clone_op(o)
        raise SystemExit('%s: operand type %d in the wave slice' % (label, o.rtype))
    ins_new = []
    for i in sl + [W_]:
        ops = [cv(o) for o in i.ops]
        ins_new.append(Instr(i.op, ops, ctrl=i.ctrl, pred=i.pred, imm=list(i.imm), usage=i.usage))
    P_ = ins_new[-1].ops[0].num
    ins_new.append(Instr('mov', [Operand(RT_TEMP, P_, isdst=True, wm=8), Operand(RT_INPUT, vposA, swz=0xFF)]))
    # redirect position reads in A
    nred = 0; items = []
    for it in A.items:
        if isinstance(it, Instr) and it.op not in ('dcl', 'def', 'defi', 'defb'):
            ops = []
            for j, o in enumerate(it.ops):
                if not o.isdst and o.rtype == RT_INPUT and o.num == vposA:
                    ops.append(clone_op(o, rtype=RT_TEMP, num=P_)); nred += 1
                else: ops.append(o)
            it = Instr(it.op, ops, ctrl=it.ctrl, pred=it.pred, imm=list(it.imm), usage=it.usage)
        items.append(it)
    # CTAB: A's entries + the named constants of 1908 the slice reads
    used_b = {o.num for i in sl + [W_] for o in i.ops if o.rtype == RT_CONST and o.num not in defsB}
    ct = dict(cta); ct['ents'] = list(cta['ents'])
    for e in ctb['ents']:
        if e[1] == 2 and any(e[2] <= r < e[2] + e[3] for r in used_b) and e[0] not in namesA: ct['ents'].append(e)
    out = []; placed = False; last_decl = max(k for k, it in enumerate(items) if isinstance(it, Instr) and it.op in ('dcl', 'def', 'defi', 'defb'))
    for k, it in enumerate(items):
        if isinstance(it, Comment) and it.payload[:4] == b'CTAB': out.append(ctab_build(ct)); continue
        out.append(it)
        if k == last_decl:
            out += newdcl + newdefs + ins_new; placed = True
    assert placed
    prog = sm3asm.Program(A.kind, A.major, A.minor, out)
    return prog, dict(slice=len(sl) + 1, redirected=nred, temps=tmap, defs=cmap, newdcl=vmap, ctab_added=[e[0] for e in ct['ents'] if e[0] not in namesA])


def vm_inputs(prog, N, rng, shared):
    """random inputs per (usage, index), shared between programs"""
    inp = {}
    for key, v in dcl_map(prog).items():
        if key not in shared:
            a = rng.uniform(-1, 1, (N, 4)).astype(np.float32)
            if key == (0, 0): a[:, 3] = 1.0; a[:, :3] *= 500
            shared[key] = a
        inp[(RT_INPUT, v)] = shared[key]
    return inp


def outputs_by_sem(prog, regs):
    """{(usage, index): (N,4)} of the written output registers"""
    sem = {}
    for i in prog.instrs():
        if i.op == 'dcl' and i.ops[0].rtype in (RT_TEXOUT, RT_ATTR, RT_RAST) and i.ops[0].isdst:
            sem[i.ops[0].num] = (i.usage & 31, (i.usage >> 16) & 15, i.ops[0].wm)
    out = {}
    for (t, n), v in regs.items():
        if t in (RT_TEXOUT, RT_ATTR, RT_RAST) and n in sem:
            u, ix, wm = sem[n]; out[(u, ix)] = (v, wm)
    return out


def vm_check(new, A, B, label, N=256):
    rng = np.random.RandomState(46); shared = {}
    consts = {r: rng.uniform(-2, 2, 4).astype(np.float32) for r in range(256)}
    rn = sm3vm.run(new, vm_inputs(new, N, rng, shared), consts, None, N)
    rb = sm3vm.run(B, vm_inputs(B, N, rng, shared), consts, None, N)
    on, ob = outputs_by_sem(new, rn['regs']), outputs_by_sem(B, rb['regs'])
    e_pos = float(np.max(np.abs(on[(0, 0)][0] - ob[(0, 0)][0]) / (1 + np.abs(ob[(0, 0)][0]))))
    # A run on the displaced position (taken from the new program's position temp)
    P_ = next(i for i in body(new) if i.op == 'mov' and i.ops[0].wm == 8 and i.ops[1].rtype == RT_INPUT).ops[0].num
    disp = rn['regs'][(RT_TEMP, P_)].copy()
    sharedA = dict(shared); sharedA[(0, 0)] = disp
    ra = sm3vm.run(A, vm_inputs(A, N, rng, sharedA), consts, None, N)
    oa = outputs_by_sem(A, ra['regs'])
    worst = 0.0; miss = []
    for k, (v, wm) in oa.items():
        if k not in on: miss.append(k); continue
        m = [c for c in range(4) if wm >> c & 1]
        worst = max(worst, float(np.max(np.abs(on[k][0][:, m] - v[:, m]) / (1 + np.abs(v[:, m])))))
    moved = float(np.max(np.abs(disp[:, :3] - shared[(0, 0)][:, :3])))
    log('  %s VM: oPos vs PC 1908 rel.err %.2e; other outputs vs PC 1911 on the displaced position rel.err %.2e; '
        'missing %s; max displacement %.3g' % (label, e_pos, worst, miss or 'none', moved))
    return e_pos < 1e-4 and worst < 1e-4 and not miss and moved > 0


def build_vs(L, xid, xbase_same, xbase_out, outd):
    """xid 2459, xbase_same 1064 (-> PC 1908), xbase_out 1067 (-> PC 1911)"""
    X, XS, XO = L['D'][xid], L['X'][xbase_same], L['X'][xbase_out]
    PS_, PO = L['P'][L['x2p'][xbase_same]], L['P'][L['x2p'][xbase_out]]
    log('VS: Xbox %d; base Xbox %d -> PC %d (wave), base Xbox %d -> PC %d (outputs)' % (xid, xbase_same, L['x2p'][xbase_same], xbase_out, L['x2p'][xbase_out]))
    assert occ(X) == occ(XO) == occ(XS), 'Xbox slot sets differ'
    same = {k for k in occ(X) if xtext(blob(X, k)) == xtext(blob(XS, k))}
    log('  Xbox slots equal to %d: %d of %d %s' % (xbase_same, len(same), len(occ(X)), sorted(same)))
    pcs = occ(PO)
    assert pcs == occ(PS_), 'PC slot sets of the two base libs differ'
    slots = [None] * 256; stats = collections.Counter(); ok_all = True; cache = {}
    # Xbox and PC permutation numbers do not mean the same (e.g. Xbox 32 = depth output, PC 32 = fog + PSSM outputs),
    # so the choice is made on the PC programs: position-only on both -> PC 1908 verbatim (wave + transform);
    # otherwise 1911's outputs + 1908's wave (merge); skinned with outputs -> 1911 (no wave)
    def outs(p):
        return {(i.usage & 31, (i.usage >> 16) & 15) for i in p.instrs()
                if i.op == 'dcl' and i.ops[0].isdst and i.ops[0].rtype in (RT_TEXOUT, RT_ATTR, RT_RAST)} - {(0, 0)}
    for k in pcs:
        A = sm3asm.decode(trim(blob(PO, k))); B = sm3asm.decode(trim(blob(PS_, k)))
        key = (PO['slots'][k], PS_['slots'][k])
        if not outs(A) and not outs(B):
            e = PS_['entries'][PS_['slots'][k]]; slots[k] = (bytes(e['hash']), e['blob'])
            stats['position-only: PC %d verbatim' % L['x2p'][xbase_same]] += 1
            continue
        if key in cache: slots[k] = cache[key]; stats['merged (shared)'] += 1; continue
        if (0, 0) not in dcl_map(B) or not any(i.op == 'mad' and i.ops[0].rtype == RT_TEMP and i.ops[0].wm == 7 and i.ops[3].rtype == RT_INPUT
                                               and i.ops[3].num == dcl_map(B)[(0, 0)] for i in body(B)):
            # skinned permutation: PC 1908 adds the wave after skinning; not merged (static terrain never uses it)
            e = PO['entries'][PO['slots'][k]]; slots[k] = (bytes(e['hash']), e['blob']); stats['skinned: PC %d without wave' % L['x2p'][xbase_out]] += 1
            cache[key] = slots[k]
            continue
        prog, info = merge_vs(A, B, 'slot %d' % k)
        bc = sm3asm.encode(prog)
        txt = SD.disasm(bc); ok, msg = SV.assemble(txt)
        open(os.path.join(outd, 'asm', 'vs_s%d.asm' % k), 'w').write(txt)
        good = vm_check(prog, A, B, 'slot %d' % k)
        log('  slot %d merged: %s; D3DX reassembly %s%s' % (k, info, 'ok' if ok and not msg.strip() else 'FAILED', (' ' + msg.strip()[:200]) if msg.strip() else ''))
        if not (ok and good): ok_all = False
        slots[k] = (None, bc); cache[key] = slots[k]; stats['merged'] += 1
    log('  VS slots: %s' % dict(stats))
    return slots, ok_all


# ------------------------------------------------------------------------------------------------ lib bytes
def known_hashes(L):
    hs = set()
    for k in ('P', 'X', 'D'):
        for lib in L[k].values():
            for e in lib['entries'].values(): hs.add(bytes(e['hash']))
    return hs


def new_hash(bc, taken):
    for salt in range(1000):
        h = hashlib.blake2b(b'TRU-DLC test46|%d|' % salt + bc, digest_size=8).digest()
        if h not in taken: taken.add(h); return h
    raise RuntimeError('hash')


def cube_mask(bc):
    m = 0
    for i in sm3asm.decode(bc).instrs():
        if i.op == 'dcl' and i.ops[0].rtype == RT_SAMPLER and (i.usage >> 27) & 15 == 3: m |= 1 << i.ops[0].num
    return m


def pc_lib(kind, sb, word0=0):
    """PC ShaderLib section data (layout read from the base PC sections, tools/shaderlib_layout.py): u8 kind, 3 pad,
    u32 tableBytes, u32 dataSize = section length - 4, u32 slot offsets (relative to +4); entry = u32 word0 (one
    value per library), u32 size = (16 + code bytes) | (bit mask of dcl_cube samplers << 16) (6139 / 6139 base PS
    entries, tools/column_shader_report.py flags), u64 hash, D3D9 code up to and including END. Identical
    (hash, code) entries are shared."""
    n = len(sb); tb = 4 * n; body = bytearray(); offs = {}; slots = []
    for s in sb:
        if s is None: slots.append(0xffffffff); continue
        h, bc = bytes(s[0]), bytes(s[1])
        if (h, bc) not in offs:
            offs[(h, bc)] = 8 + tb + len(body)
            body += struct.pack('<II', word0, (16 + len(bc)) | (cube_mask(bc) << 16)) + h + bc
        slots.append(offs[(h, bc)])
    out = bytearray(bytes([kind, 0, 0, 0]) + struct.pack('<II', tb, 0) + struct.pack('<%dI' % n, *slots) + bytes(body))
    struct.pack_into('<I', out, 8, len(out) - 4)
    return bytes(out)


def lib_bytes(kind, slots, taken, word0=0):
    """slots: list of None | bytecode | (hash or None, bytecode)"""
    sb = []; hmap = {}
    for s in slots:
        if s is None: sb.append(None); continue
        h, bc = s if isinstance(s, tuple) else (None, s)
        bc = trim(bc)
        if h is None:
            if bc not in hmap: hmap[bc] = new_hash(bc, taken)
            h = hmap[bc]
        sb.append((h, bc))
    return pc_lib(kind, sb, word0)


def roundtrip_check(sec_data):
    lib = SL.parse(sec_data, 'le')
    sb = [None if s == 0xffffffff else (lib['entries'][s]['hash'], trim(lib['entries'][s]['blob'])) for s in lib['slots']]
    j = {e['junk'] for e in lib['entries'].values()}
    b = pc_lib(lib['kind'], sb, j.pop() if len(j) == 1 else 0)
    if b == sec_data: return 'yes'
    d = next((i for i in range(min(len(b), len(sec_data))) if b[i] != sec_data[i]), None)
    return 'NO: sizes %d / %d, first difference at %s (%s / %s), junk values %s, header %s / %s' % (
        len(sec_data), len(b), d, sec_data[d:d + 8].hex() if d is not None else '-', b[d:d + 8].hex() if d is not None else '-',
        sorted('%x' % e['junk'] for e in lib['entries'].values()), sec_data[:12].hex(), b[:12].hex())


# ------------------------------------------------------------------------------------------------ commands
def cmd_build(pc_drm, outd, mid, xbox_slots=False):
    os.makedirs(os.path.join(outd, 'asm'), exist_ok=True)
    L = libs()
    xd, xr = L['DM'][mid]
    xt, xrec, xpar = mat_info(xd, xr, '>')
    D = DW.read(open(pc_drm, 'rb').read(), 'le')
    pm = next(s for s in D.sections if s.type == 10 and s.id == mid)
    pt, prec, ppar = mat_info(pm.data, pm.reloc, '<')
    global PARAMS; PARAMS = ppar
    log('material %d: Xbox tuple %s, PC tuple %s' % (mid, xt, pt))
    log('  header +0x38..+0x53 Xbox %s' % ' '.join('%08x' % w for w in struct.unpack_from('>7I', xd, 0x38)))
    log('  header +0x38..+0x53 PC   %s' % ' '.join('%08x' % w for w in struct.unpack_from('<7I', pm.data, 0x38)))
    log('  Xbox records %s' % dict(sorted(xrec.items())))
    log('  PC records   %s' % dict(sorted(prec.items())))
    for j in range(max(len(xpar), len(ppar))):
        a = xpar[j] if j < len(xpar) else None; b = ppar[j] if j < len(ppar) else None
        log('  c%d Xbox %s PC %s%s' % (100 + j, a, b, '' if a == b or a is None else '  DIFFERENT'))
    if any(xpar[j] != ppar[j] for j in range(len(xpar))): raise SystemExit('MaterialParams differ Xbox / PC')
    # PC ShaderLib section format check: rebuilding the surrogate libs from their entries gives the same bytes
    for s in D.sections:
        if s.type == 9 and s.id in pt: log('  PC ShaderLib %d rebuild from entries identical: %s' % (s.id, roundtrip_check(s.data)))
    w0 = collections.Counter(); per = collections.Counter()
    for lib in L['P'].values():
        ws = {e['junk'] for e in lib['entries'].values()}
        per[len(ws)] += 1; w0.update(ws)
    log('  PC entry word0: %d libraries, distinct values per library %s, distinct values overall %d, zero used by %d'
        % (len(L['P']), dict(per), len(w0), w0.get(0, 0)))
    # samplers of the pass-2 PS: Xbox register -> PC register (texture id of the records + sampler name of the surrogate)
    xps2, xps0, xvs = xt[2], xt[0], xt[3]
    pc_names = {}
    for o in set(x for x in L['P'][pt[2]]['slots'] if x != 0xffffffff):
        for n, rs, ri, rc in SL.constants(L['P'][pt[2]]['entries'][o]['blob'], 'p')[1]:
            if rs == 3: pc_names[n] = ri
    xnames = {}
    for o in set(x for x in L['D'][xps2]['slots'] if x != 0xffffffff):
        for n, rs, ri, rc in SL.constants(L['D'][xps2]['entries'][o]['blob'], 'x')[1]:
            if rs == 3: xnames[ri] = n
    xfmt, pk = xbox_tex_formats('dlc_level2_start.drm')
    pfmt = {s.id: struct.unpack_from('<I', s.data, 4)[0] for s in D.sections if s.type == 5}
    log('  Xbox source %s, %d textures' % (pk, len(xfmt)))
    sampmap = {}; dxn = set()
    for xr_, n in sorted(xnames.items()):
        tid = xrec.get(xr_, [(None, 0)])[0][0]
        by_tid = sorted(s for s, v in prec.items() if any(t == tid for t, b in v))
        by_name = pc_names.get(n)
        pick = by_name if by_name in by_tid else (by_tid[0] if len(by_tid) == 1 else None)
        log('  sampler Xbox s%d %s: texture %s (Xbox fmt %#x, PC fmt %#x) -> PC by texture %s, by name %s -> s%s'
            % (xr_, n, tid, xfmt.get(tid, -1), pfmt.get(tid, -1), by_tid, by_name, pick))
        if pick is None: raise SystemExit('no PC sampler for Xbox s%d' % xr_)
        sampmap[xr_] = pick
        if xfmt.get(tid) == DXN_X and pfmt.get(tid) == DXT5_PC: dxn.add(xr_)
    log('  DXN normal maps (Xbox registers): %s' % sorted(dxn))
    cps = pc_regs(L, 1)
    log('  PC PS registers used: %s' % {n: cps.get(ALIAS.get(n, n)) for n in ('MaterialParams', 'MaterialOpacity', 'TimeVector', 'CameraPosition', 'AlphaThreshold')})
    ok_rule = opacity_slot_check(L, 1066, 1910)
    if not ok_rule: raise SystemExit('slot rule does not hold')
    if xbox_slots:
        # keep the Xbox sampler registers (base pairs keep the register of a sampler name, tools/material_reslot.py);
        # apply moves the PC material's records back to the Xbox slots (reslot.json: PC slot -> Xbox slot)
        inv = {p: x for x, p in sampmap.items()}
        if len(inv) != len(sampmap) or set(inv) != set(prec): raise SystemExit('PC records do not map 1:1 to Xbox samplers')
        import json
        json.dump({str(p): x for p, x in inv.items()}, open(os.path.join(outd, 'reslot.json'), 'w'))
        log('  --xbox-slots: PS keeps the Xbox registers; material records PC slot -> Xbox slot %s' % dict(sorted(inv.items())))
        sampmap = {x: x for x in sampmap}
    ps2, x2 = translate_ps(L, xps2, pt[2], None, cps, sampmap, dxn, 'ps2', outd)
    ps0, x0 = translate_ps(L, xps0, pt[0], None, cps, {}, set(), 'ps0', outd)
    # pass 0: PC slot 2 of the surrogate family (depth into a colour target, a PC-only permutation) stays as it is
    P0 = L['P'][pt[0]]
    for k in occ(P0):
        if k >= 2:
            e = P0['entries'][P0['slots'][k]]; ps0[k] = (bytes(e['hash']), e['blob'])
            log('  ps0 PC slot %d: kept from PC %d (hash %s, PC-only permutation)' % (k, pt[0], e['hash'].hex()))
    vs, ok_vs = build_vs(L, xvs, 1064, 1067, outd)
    if not ok_vs: raise SystemExit('VS checks failed')
    taken = known_hashes(L)
    for nm, kind, sl in (('ps0', 1, ps0), ('ps2', 1, ps2), ('vs', 0, vs)):
        data = lib_bytes(kind, sl, taken)
        assert SL.parse(data, 'le')['slots'] == SL.parse(data, 'le')['slots']
        open(os.path.join(outd, nm + '.lib'), 'wb').write(data)
        log('wrote %s.lib: %d bytes, %d slots, md5 %s' % (nm, len(data), len(sl), hashlib.md5(data).hexdigest()))
    open(os.path.join(outd, 'build.txt'), 'w').write('\n'.join(LOG) + '\n')


def cmd_apply(src, out, outd, ids, mid, keep0):
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    have9 = {s.id for s in D.sections if s.type == 9}
    m = next(s for s in D.sections if s.type == 10 and s.id == mid)
    old = struct.unpack_from('<4I', m.data, 0x28)
    tmpl = next(s for s in D.sections if s.type == 9 and s.id == old[2])
    idx = D.sections.index(tmpl)
    plan = [('ps0', 0, ids[0]), ('ps2', 2, ids[1]), ('vs', 3, ids[2])]
    if keep0: plan = plan[1:]
    rr = R.parse(m.reloc, 'le')
    d = bytearray(m.data)
    for nm, slot, lid in plan:
        if lid in have9: raise SystemExit('ShaderLib id %d already in the file' % lid)
        data = open(os.path.join(outd, nm + '.lib'), 'rb').read()
        idx += 1
        D.sections.insert(idx, DW.Section(9, lid, data, b'', flags=tmpl.flags, ver=tmpl.ver, spec=tmpl.spec, pad=tmpl.pad))
        off = 0x28 + 4 * slot
        if (9, off) not in rr.idref: raise SystemExit('no shader id reference at +%#x' % off)
        struct.pack_into('<I', d, off, lid)
        print('material %d slot %d: %d -> %d (%s.lib, %d bytes)' % (mid, slot, old[slot], lid, nm, len(data)))
    rs = os.path.join(outd, 'reslot.json')
    if os.path.exists(rs):
        import json
        inv = {int(k): v for k, v in json.load(open(rs)).items()}
        tp = dict(rr.internal)[0x54]; mx = 0
        for k in range(d[0x52]):
            o_ = tp + 16 * k + 13; p = d[o_]
            d[o_] = inv[p]; mx = max(mx, inv[p] + 1)
            print('  texture record %d (id %d): sampler slot %d -> %d' % (k, struct.unpack_from('<I', d, tp + 16 * k)[0], p, inv[p]))
        print('  byte +0x4F %d (highest slot + 1 = %d)' % (d[0x4F], mx))
    m.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    # readback: the original sections in order, unchanged except the material; the new ones exactly the libs
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    new = [s for s in B if s.type == 9 and s.id in {p[2] for p in plan}]
    rest = [s for s in B if not (s.type == 9 and s.id in {p[2] for p in plan})]
    assert len(rest) == len(A), (len(rest), len(A))
    changed = [(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc, a.flags, a.ver, a.spec, a.pad) != (b.type, b.id, b.data, b.reloc, b.flags, b.ver, b.spec, b.pad)]
    assert changed == [(10, mid)], changed
    for nm, slot, lid in plan:
        s = next(x for x in new if x.id == lid)
        assert s.data == open(os.path.join(outd, nm + '.lib'), 'rb').read()
    print('readback: %d original sections in order, changed only %s; %d new ShaderLibs %s' % (len(A), changed, len(new), [s.id for s in new]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s' % (out, hashlib.md5(o).hexdigest()))


def vs_block(d, rb, e):
    """material +0x58 / +0x5C = PS MaterialParams (count, pointer; uploaded to PS c100 at 0x505acf), +0x68 /
    +0x6C = VS MaterialParams (u32; the engine reads the low u16, uploaded to VS c25 at 0x505c2e), +0x70..+0x73 = per-instance PS / VS ranges"""
    it = dict(R.parse(rb, 'be' if e == '>' else 'le').internal)
    n_ps = struct.unpack_from(e + 'I', d, 0x58)[0]; n_vs = struct.unpack_from(e + 'I', d, 0x68)[0]
    p = it.get(0x6C)
    vs = [struct.unpack_from(e + '4f', d, p + 16 * i) for i in range(n_vs)] if p is not None else None
    return dict(n_ps=n_ps, n_vs=n_vs, raw60=d[0x60:0x74].hex(' '), vs=vs, ptr6c=p, ptr5c=it.get(0x5C), ptr64=it.get(0x64))


def cmd_mat(mid, pc_drm=None, pcid=None):
    L = libs()
    for k in ('DM', 'XM'):
        if mid in L[k]:
            d, r = L[k][mid]; print('Xbox %s %d: tuple %s %s' % (k, mid, struct.unpack_from('>4I', d, 0x28), vs_block(d, r, '>')))
    if pc_drm:
        D = DW.read(open(pc_drm, 'rb').read(), 'le')
        s = next(x for x in D.sections if x.type == 10 and x.id == (pcid or mid))
        print('PC %s %d: %s' % (os.path.basename(pc_drm), pcid or mid, vs_block(s.data, s.reloc, '<')))
    elif pcid and pcid in L['PM']:
        d, r = L['PM'][pcid]; print('PC PM %d: %s' % (pcid, vs_block(d, r, '<')))


def cmd_show(xid, slot):
    """translate one DLC Xbox PS entry without optimisation (registers: PC conventions, samplers unchanged), print text"""
    L = libs(); cregs = pc_regs(L, 1)
    def cfn(name, j, count):
        r = cregs.get(ALIAS.get(name, name))
        return None if r is None else r + j
    b = blob(L['D'][xid], slot)
    print('\n'.join(xtext(b)))
    t = xenos2sm3.translate(b, cfn, bools=None, samp=lambda n, c: c, opts={'noopt': True})
    print(t.text)


def main(argv):
    mid = 24691
    if argv and argv[0] == 'show': return cmd_show(int(argv[1]), int(argv[2]))
    if argv and argv[0] == 'mat': return cmd_mat(int(argv[1]), argv[2] if len(argv) > 2 and not argv[2].isdigit() else None, int(argv[-1]) if len(argv) > 2 and argv[-1].isdigit() else None)
    if '--mat' in argv: k = argv.index('--mat'); mid = int(argv[k + 1]); del argv[k:k + 2]
    keep0 = '--keep-ps0' in argv; argv = [a for a in argv if a != '--keep-ps0']
    xs = "--xbox-slots" in argv; argv = [a for a in argv if a != "--xbox-slots"]
    if argv[0] == 'build': cmd_build(argv[1], argv[2], mid, xs)
    elif argv[0] == 'apply': cmd_apply(argv[1], argv[2], argv[3], [int(x) for x in argv[4:7]], mid, keep0)
    else: sys.exit(__doc__)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
