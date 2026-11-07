"""Test 50o (03.11.): DLC vertex shaders that DEFORM the vertices (TU VS 2474 / 2704, PS groups 2473 / 2703), refused in
50n because the Nixxes depth-pass slots (bit 3 / 4) of the PC twin cannot simply take the Xbox position (Nixxes removed
the Xbox `z *= |w|` there and writes z / w to TEXCOORD6 instead), so `tu_vs.py vsmerge` kept the undeformed twin entry in
those slots while the colour slots got the deformed DLC position -> depth and colour pass disagree.

Idea, proven per slot (no guessing): the DLC VS = the base Xbox VS applied to a deformed object-space position,
  T(x) == Tb(D(x))     T = translated DLC slot, Tb = translated base slot, D = a prefix of T (vertex position := P'),
then the PC slot is the twin applied to the same deformed position:
  M(x) := P(D(x)) (+ the outputs T adds, as vsmerge) .
Checks per slot (VM, shared random inputs / constants, 3 seeds): (1) decomposition T == Tb o D on EVERY output of T and Tb
(exact <= 1e-5 rel.); (2) M == P o D on every twin output (P run with its position input replaced by D's value);
(3) M == T on the outputs added from T; (4) D3DX9 vs_3_0 valid. D is searched, not assumed: the prefix length / register
whose value, put into the base slot as the position, reproduces T exactly (smallest such prefix; must also leave the base
slot's other inputs untouched).

Skinned slots deform the skinned position with the skinned normal; there the D of slot 0 (same family) is used and
proven numerically (check_donor, range-normalised error < 1e-5). Every deformed slot of a family uses that one D, so
depth and colour pass compute the deformed vertex with the same code. Normal decoding follows Nixxes' rule from every
base PC VS (`nsorule`: NormalScaleOffset exactly in the slots with bit 7 clear). The translator's `def` constants
(c218-c223, inside SkinMatrices c85 + 168) are moved out of the relatively addressed range (`remap_defs`).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_vs_deform.py pcinfo PCLIB [SLOT,SLOT]      inputs / outputs / CTAB names per PC VS slot
  ../bin/pyt -t 1200 tools/tu_vs_deform.py nsorule                      NormalScaleOffset use by slot bit 7 (base PC VS)
  ../bin/pyt -t 1200 tools/tu_vs_deform.py deformers                    base VS pairs whose depth slots read the normal
  ../bin/pyt -t 1800 tools/tu_vs_deform.py decomp DLCVS XBASE PCTWIN    per PC slot: does T == Tb o D hold (which D)
  ../bin/pyt -t 900 tools/tu_vs_deform.py decomp1 DLCVS XBASE PCTWIN SLOT [DONORSLOT] [--debug]
  ../bin/pyt -t 900 tools/tu_vs_deform.py dcmp DLCVS XBASE PCTWIN SLOT SLOT ...   D values of several slots compared
  ../bin/pyt -t 7200 tools/tu_vs_deform.py oracle XD/PD[,XD/PD] XBASE PCTWIN [--slots a,b] [--debug]
      the construction on base Xbox VS that deform vs Nixxes' own PC twin PD (every output it writes)
  ../bin/pyt -t 3600 tools/tu_vs_deform.py build DLCVS XBASE PCTWIN OUT.lib   merged PC VS lib, every slot checked
  ../bin/pyt -t 1200 tools/tu_vs_deform.py treecheck TREE VSID:LIBFILE:MAT[+MAT] ...   VS id / bytes / PS inputs in a tree
  ../bin/pyt -t 600 tools/tu_vs_deform.py defscan LIB.lib ...           defs inside the SkinMatrices range per slot
"""
import sys, os, json, struct, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs, xenos2sm3
import shaderlib as SL
import tu_vs as V

TOL = 1e-5
SEEDS = (3, 7, 11)
DEBUG = False
DONOR_TOL = 1e-5


def slot_prog(lib, k):
    o = lib['slots'][k]
    if o == 0xffffffff: return None, None
    import column_shader_translate as CST
    b = CST.trim(lib['entries'][o]['blob'])
    return F9.decode_pc(b), F9.pc_ctab(b)


def cmd_pcinfo(pc, slots):
    L = libs(); Pl = L['P'][pc]
    for k, o in enumerate(Pl['slots']):
        if o == 0xffffffff or (slots and k not in slots): continue
        P, pct = slot_prog(Pl, k)
        ins = sorted(V.dcls(P, sm3asm.RT_INPUT).items()); outs = sorted(V.dcls(P, sm3asm.RT_TEXOUT).items())
        fmt = lambda d: ' '.join('%s%d=%s%d' % (t, n, V.USAGE_NAME.get(s[0], s[0]), s[1]) for n, s in d for t in [''])
        print('slot %3d: in %s | out %s | ctab %s' % (k, fmt(ins), fmt(outs), ' '.join('%s@c%d/%d' % (n, ri, rc) for n, rs, ri, rc in pct if rs == 2)))


# ---------------------------------------------------------------------------------------------------- VM helpers
def rand_inputs(keys, N, seed):
    rng = np.random.RandomState(seed); ins = {}
    for key in sorted(keys):
        a = rng.uniform(0, 1, (N, 4)).astype(np.float32)
        if key == (0, 0): a[:, :3] = rng.uniform(-50, 50, (N, 3)); a[:, 3] = 1
        # bone indices as the engine stores them (UBYTE4N: k / 255), bones 0..41 -> SkinMatrices rows stay inside c0..c255
        if key[0] == 2: a = (np.floor(rng.uniform(0, 42, (N, 4))) / 255.0).astype(np.float32)
        ins[key] = a
    consts = {r: rng.uniform(-1, 1, 4).astype(np.float32) for r in range(256)}
    return ins, consts


def add_defs(consts, *progs):
    for p in progs:
        for i in p.instrs():
            if i.op == 'def': consts[i.ops[0].num] = np.array([struct.unpack('<f', struct.pack('<I', u))[0] for u in i.imm], np.float32)


def run_regs(prog, ins, consts, N, upto=None):
    """run prog (or its first `upto` body instructions) -> (outputs by semantic, temp registers)"""
    if upto is not None:
        hdr = [i for i in prog.instrs() if i.op in ('dcl', 'def', 'defi', 'defb')]
        body = [i for i in prog.instrs() if i.op not in ('dcl', 'def', 'defi', 'defb')]
        prog = sm3asm.Program(prog.kind, prog.major, prog.minor, hdr + body[:upto])
    inp = {}
    for n, key in V.dcls(prog, sm3asm.RT_INPUT).items():
        inp[(sm3asm.RT_INPUT, n)] = ins[key]
    # `def` constants are local to a program: overlay this program's own defs (two programs may def one register
    # with different values - a shared table would run one of them with the other's constants)
    consts = dict(consts); add_defs(consts, prog)
    r = V.sm3vm.run(prog, inp, consts, None, N)
    sem = V.dcls(prog, sm3asm.RT_TEXOUT); outs = {}
    for (t, n), v in r['regs'].items():
        if t == sm3asm.RT_TEXOUT and n in sem: outs[sem[n]] = v
    temps = {n: v for (t, n), v in r['regs'].items() if t == sm3asm.RT_TEMP}
    return outs, temps


def relerr(a, b, mask=15):
    m = [c for c in range(4) if mask >> c & 1]
    d = np.abs(a[:, m] - b[:, m]) / (1 + np.abs(b[:, m]))
    return float(np.nanmax(d)) if np.isfinite(d).all() and np.isfinite(a[:, m]).all() else 1e9


def cmp_outs(oa, ob, ma, mb, keys=None):
    """worst rel. error over the common outputs (or `keys`, which must exist in both); missing -> 1e9"""
    worst = 0.0
    for k in (keys if keys is not None else set(oa) & set(ob)):
        if k not in oa or k not in ob: return 1e9
        worst = max(worst, relerr(oa[k], ob[k], ma.get(k, 15) & mb.get(k, 15)))
    return worst


# ---------------------------------------------------------------------------------------------------- decomposition
def find_deform(T, Tb, N=200):
    """smallest prefix length i of T's body and temp register r such that Tb run with position := (r.xyz, v0.w) gives T's
    outputs exactly (all outputs of T and Tb, 3 seeds). -> (i, r, worst) or None. The base slot must read only the
    position plus inputs T also has (same values)."""
    tin = set(V.dcls(T, sm3asm.RT_INPUT).values()); bin_ = set(V.dcls(Tb, sm3asm.RT_INPUT).values())
    if (0, 0) not in bin_ or not bin_ <= tin: return None
    body = [i for i in T.instrs() if i.op not in ('dcl', 'def', 'defi', 'defb')]
    keysT = set(V.dcls(T, sm3asm.RT_TEXOUT).values()) & set(V.dcls(Tb, sm3asm.RT_TEXOUT).values())
    if (0, 0) not in keysT: return None
    mT = V.out_masks(T); mB = V.out_masks(Tb)
    runs = []
    for s in SEEDS:
        ins, consts = rand_inputs(tin | bin_, N, s)
        ot, _ = run_regs(T, ins, consts, N)
        runs.append((ins, consts, ot))
    # candidate (i, r): the value of temp r after the first i body instructions; xyz must differ from v0.xyz somewhere
    for i in range(1, len(body) + 1):
        if not any(o.isdst and o.rtype == sm3asm.RT_TEMP for o in body[i - 1].ops[:1]): continue
        r = body[i - 1].ops[0].num
        # cheap screen (first seed, 32 vertices, position only); the full check below decides
        ins, consts, ot = runs[0]
        ins_s = {k_: v[:32] for k_, v in ins.items()}
        _, temps = run_regs(T, ins_s, consts, 32, upto=i)
        if r not in temps or not np.isfinite(temps[r][:, :3]).all(): continue
        pos = ins_s[(0, 0)].copy(); pos[:, :3] = temps[r][:, :3]
        ins2 = dict(ins_s); ins2[(0, 0)] = pos
        ob, _ = run_regs(Tb, ins2, consts, 32)
        if relerr(ob[(0, 0)], ot[(0, 0)][:32], mT.get((0, 0), 15) & mB.get((0, 0), 15)) > 1e-3: continue
        worst = 0.0
        for ins, consts, ot in runs:
            _, temps = run_regs(T, ins, consts, N, upto=i)
            if r not in temps: worst = 1e9; break
            v = temps[r]
            pos = ins[(0, 0)].copy(); pos[:, :3] = v[:, :3]
            if not np.isfinite(pos).all(): worst = 1e9; break
            ins2 = dict(ins); ins2[(0, 0)] = pos
            ob, _ = run_regs(Tb, ins2, consts, N)
            worst = max(worst, cmp_outs(ot, ob, mT, mB, keysT))
            if DEBUG and cmp_outs(ot, ob, mT, mB, {(0, 0)}) <= TOL:
                print('   debug: prefix %d r%d: position ok, per output %s' % (i, r, {k: round(cmp_outs(ot, ob, mT, mB, {k}), 5) for k in keysT}))
            if worst > TOL: break
        if worst <= TOL:
            ident = all(np.allclose(run_regs(T, ins, consts, N, upto=i)[1][r][:, :3], ins[(0, 0)][:, :3]) for ins, consts, ot in runs)
            return (i, r, worst, ident)
    return None


def check_donor(T, Tb, Td, i, r, N=200):
    """D taken from another slot's translation Td (prefix i, register r): T == Tb o D on every common output of T / Tb
    (3 seeds). Used for the skinned slots, where the DLC deforms the skinned position with the skinned normal (for a
    rigid / blended skin the same as deforming the object-space position first - shown here numerically, not assumed)"""
    keys = set(V.dcls(T, sm3asm.RT_INPUT).values()) | set(V.dcls(Tb, sm3asm.RT_INPUT).values()) | set(V.dcls(Td, sm3asm.RT_INPUT).values())
    common = set(V.dcls(T, sm3asm.RT_TEXOUT).values()) & set(V.dcls(Tb, sm3asm.RT_TEXOUT).values())
    if (0, 0) not in common: return 1e9
    mT = V.out_masks(T); mB = V.out_masks(Tb); worst = 0.0
    for s in SEEDS:
        ins, consts = rand_inputs(keys, N, s)
        ot, _ = run_regs(T, ins, consts, N)
        _, temps = run_regs(Td, ins, consts, N, upto=i)
        pos = ins[(0, 0)].copy(); pos[:, :3] = temps[r][:, :3]
        ins2 = dict(ins); ins2[(0, 0)] = pos
        ob, _ = run_regs(Tb, ins2, consts, N)
        # range-normalised error: max |difference| / (1 + max |value|) per output lane over the batch. The per-vertex
        # (1 + |v|) normalisation of relerr breaks down at the Xbox depth-slot `z *= |w|` when z ~ 0 and |w| ~ 100
        # (float32 rounding of the reordered sum shows as 1e-4 there); a formula difference stays O(1) either way
        for k_ in common:
            m = [c for c in range(4) if (mT.get(k_, 15) & mB.get(k_, 15)) >> c & 1]
            a, b = ot[k_][:, m].astype(np.float64), ob[k_][:, m].astype(np.float64)
            if not (np.isfinite(a).all() and np.isfinite(b).all()): return 1e9
            worst = max(worst, float((np.abs(a - b).max(axis=0) / (1 + np.abs(b).max(axis=0))).max()))
    return worst


def remap_defs(T, P):
    """move T's `def` constants that would collide in a merged program to registers nothing reads: a def register is
    moved if P reads / defines it, or if it lies inside a relatively addressed range (SkinMatrices c85 + 0..167 when P or
    T use a0 - a def there would shadow bone matrices for the engine's upload). Targets: unread, undefined, outside the
    relative range, from c255 down. Pure renaming of constants (VM-checked by the callers)."""
    rel_lo, rel_hi = None, None
    for prog in (P, T):
        for x in prog.instrs():
            for o in x.ops:
                if o.rtype == sm3asm.RT_CONST and o.rel:
                    lo = o.num; rel_lo = lo if rel_lo is None else min(rel_lo, lo)
    if rel_lo is not None:
        rel_lo = min(rel_lo, 85); rel_hi = 85 + 168 - 1          # SkinMatrices c85 / 168 (PC CTAB of every skinned slot)
    inrel = lambda n: rel_lo is not None and rel_lo <= n <= rel_hi
    pread = {o.num for x in P.instrs() for o in x.ops if o.rtype == sm3asm.RT_CONST}
    pdef = {x.ops[0].num: tuple(x.imm) for x in P.instrs() if x.op == 'def'}
    tread = {o.num for x in T.instrs() if x.op != 'def' for o in x.ops if o.rtype == sm3asm.RT_CONST}
    tdef = {x.ops[0].num: tuple(x.imm) for x in T.instrs() if x.op == 'def'}
    taken = pread | set(pdef) | tread | set(tdef)
    move = {}
    for n, v in tdef.items():
        if (n in pdef and pdef[n] == v) and not inrel(n): continue          # identical def in both - shared
        if n in pread or n in pdef or inrel(n):
            tgt = next((c for c in range(255, -1, -1) if c not in taken and not inrel(c)), None)
            if tgt is None: raise xenos2sm3.Reject('remap_defs: no free constant')
            taken.add(tgt); move[n] = tgt
    if not move: return T, {}
    items = []
    for it in T.items:
        if not isinstance(it, sm3asm.Instr): items.append(it); continue
        j = sm3asm.Instr(it.op, [], it.ctrl, it.pred, list(it.imm), it.usage)
        for o in it.ops:
            o2 = _clone(o)
            if o.rtype == sm3asm.RT_CONST and not o.rel and o.num in move: o2.num = move[o.num]
            j.ops.append(o2)
        items.append(j)
    return sm3asm.Program(T.kind, T.major, T.minor, items), move


def strip_shared_defs(T, PD):
    """T without the defs PD already has with the same value (merge_slot would see them as collisions)"""
    pdef = {x.ops[0].num: tuple(x.imm) for x in PD.instrs() if x.op == 'def'}
    items = [it for it in T.items if not (isinstance(it, sm3asm.Instr) and it.op == 'def' and pdef.get(it.ops[0].num) == tuple(it.imm))]
    return sm3asm.Program(T.kind, T.major, T.minor, items)


def _clone(o, **kw):
    o2 = sm3asm.Operand(o.rtype, o.num, o.isdst, o.rel, o.relop, o.wm, o.mod, o.shift, o.swz, o.smod, o.resv)
    for k, v in kw.items(): setattr(o2, k, v)
    return o2


def compose(P, T, i, r):
    """PD = P applied to the deformed position: T's first i body instructions (D, temps renamed above P's, inputs mapped
    onto P's by semantic, new inputs declared), rQ = (rR.xyz, vPos.w), then P's program with every read of its
    position input replaced by rQ. Pure composition - checked in the VM by the caller."""
    pin = {v: k for k, v in V.dcls(P, sm3asm.RT_INPUT).items()}
    if (0, 0) not in pin: raise xenos2sm3.Reject('compose: twin slot has no position input')
    vpos = pin[(0, 0)]
    tin = V.dcls(T, sm3asm.RT_INPUT)
    ptemps = [o.num for x in P.instrs() for o in x.ops if o.rtype == sm3asm.RT_TEMP]
    off = max(ptemps + [-1]) + 1
    body = [x for x in T.instrs() if x.op not in ('dcl', 'def', 'defi', 'defb')][:i]
    dt = sorted({o.num for x in body for o in x.ops if o.rtype == sm3asm.RT_TEMP} | {r})
    tmap = {t: off + n for n, t in enumerate(dt)}; Q = off + len(dt)
    free_v = [n for n in range(16) if n not in V.dcls(P, sm3asm.RT_INPUT)]
    vmap = {}; hdr = []
    used_in = {o.num for x in body for o in x.ops if o.rtype == sm3asm.RT_INPUT}
    for n in sorted(used_in):
        sem = tin[n]
        if sem in pin: vmap[n] = pin[sem]
        else:
            vmap[n] = free_v.pop(0); hdr.append('dcl_%s%s v%d' % (V.USAGE_NAME[sem[0]], sem[1] or '', vmap[n]))
    # constants: T's defs must not collide with anything P reads / defines, and D must not read a register P defines
    pdefs = {x.ops[0].num for x in P.instrs() if x.op in ('def', 'defi', 'defb')}
    pconst = {o.num for x in P.instrs() for o in x.ops if o.rtype == sm3asm.RT_CONST}
    tdefs = [x for x in T.instrs() if x.op == 'def']
    for x in tdefs:
        if x.ops[0].num in pconst or x.ops[0].num in pdefs: raise xenos2sm3.Reject('compose: def c%d collides' % x.ops[0].num)
    dconst = {o.num for x in body for o in x.ops if o.rtype == sm3asm.RT_CONST}
    if dconst & pdefs: raise xenos2sm3.Reject('compose: D reads c%s that the twin defines' % sorted(dconst & pdefs))
    if any(o.rel for x in body for o in x.ops if o.rtype == sm3asm.RT_INPUT): raise xenos2sm3.Reject('compose: relative input')
    dl = []
    for x in body:
        j = sm3asm.Instr(x.op, [], x.ctrl, x.pred, list(x.imm), x.usage)
        for o in x.ops:
            o2 = _clone(o)
            if o.rtype == sm3asm.RT_TEMP: o2.num = tmap[o.num]
            elif o.rtype == sm3asm.RT_INPUT: o2.num = vmap[o.num]
            elif o.rtype == sm3asm.RT_TEXOUT: raise xenos2sm3.Reject('compose: D writes an output')
            if o.rel and o.relop is not None and o.relop.rtype == sm3asm.RT_TEMP: o2.relop = _clone(o.relop, num=tmap[o.relop.num])
            j.ops.append(o2)
        dl.append(sm3asm.fmt_instr(j, 'vs'))
    dl.append('mov r%d, v%d' % (Q, vpos))
    dl.append('mov r%d.xyz, r%d.xyz' % (Q, tmap[r]))
    ph, pb = [], []
    for it in P.items:
        if isinstance(it, sm3asm.Instr) and it.op in ('dcl', 'def', 'defi', 'defb'):
            ph.append(sm3asm.fmt_instr(it, 'vs')); continue
        if not isinstance(it, sm3asm.Instr): continue          # comments (CTAB) are not carried: the engine binds by register
        j = sm3asm.Instr(it.op, [], it.ctrl, it.pred, list(it.imm), it.usage)
        for n, o in enumerate(it.ops):
            o2 = _clone(o)
            if o.rtype == sm3asm.RT_INPUT and o.num == vpos and not (n == 0 and o.isdst):
                if o.rel: raise xenos2sm3.Reject('compose: relative position read')
                o2.rtype = sm3asm.RT_TEMP; o2.num = Q
            j.ops.append(o2)
        pb.append(sm3asm.fmt_instr(j, 'vs'))
    txt = '\n'.join(['vs_3_0'] + [sm3asm.fmt_instr(x, 'vs') for x in tdefs] + ph + hdr + dl + pb) + '\n'
    M = V.realloc(sm3asm.parse_text(txt))
    if max([o.num for x in M.instrs() for o in x.ops if o.rtype == sm3asm.RT_TEMP] + [0]) > 31: raise xenos2sm3.Reject('compose: too many temps')
    return M


def check_compose(PD, P, T, i, r, N=200):
    """VM: PD == P run with its position input := (D value xyz, w) on every P output (3 seeds) -> worst abs error"""
    keys = set(V.dcls(PD, sm3asm.RT_INPUT).values()) | set(V.dcls(P, sm3asm.RT_INPUT).values()) | set(V.dcls(T, sm3asm.RT_INPUT).values())
    mP = V.out_masks(P); worst = 0.0
    for s in SEEDS:
        ins, consts = rand_inputs(keys, N, s)
        _, temps = run_regs(T, ins, consts, N, upto=i)
        pos = ins[(0, 0)].copy(); pos[:, :3] = temps[r][:, :3]
        ins2 = dict(ins); ins2[(0, 0)] = pos
        op, _ = run_regs(P, ins2, consts, N); om, _ = run_regs(PD, ins, consts, N)
        for k, v in op.items():
            if k not in om: return 1e9
            worst = max(worst, relerr(om[k], v, mP.get(k, 15)))
    return worst


def conv_for(k):
    """Nixxes' rule over every base PC VS slot that reads normal / tangent / binormal (`nsorule`: 5 610 / 5 610 slots each
    way, no exception): slot bit 7 clear -> compressed, decoded with NormalScaleOffset; bit 7 set -> raw"""
    return {} if k & 128 else {3: 'nso', 6: 'nso', 7: 'nso'}


class NoDecomp(xenos2sm3.Reject): pass


def translate_pair(Dl, Xp, Pp, k, src):
    P, pct = slot_prog(Pp, k)
    conv = conv_for(k)
    T, _ = V.translate(Dl['entries'][Dl['slots'][src]]['blob'], pct, conv)
    Tb, _ = V.translate(Xp['entries'][Xp['slots'][src]]['blob'], pct, conv)
    # the translator puts its defs at c218-c223, inside SkinMatrices (c85 + 168) - in a skinned slot a def there
    # shadows the bone rows of bones 33-34 (Xbox fetches bones from a stream, so the original has no such overlap):
    # move them out of the relative range first (renaming only; every later check runs on the moved programs)
    T, _ = remap_defs(T, P); Tb, _ = remap_defs(Tb, P)
    return P, T, Tb


def build_slot(Dl, Xp, Pp, k, src, log, ref=None, donors=(), force_donor=False):
    """one PC slot: T (DLC / deforming Xbox VS) on base Tb (plain Xbox), twin P (plain PC). -> (M, info) or raises.
    D = a prefix of T itself, or the D of a donor slot of the same family (bit 7) of the same lib, proven by
    check_donor (force_donor: the donor D even where the slot has its own - one D program for every slot of a family,
    so depth and colour pass compute the deformed vertex with the same code). ref = Nixxes' own PC slot (oracle only):
    M must equal it on every output it writes."""
    P, T, Tb = translate_pair(Dl, Xp, Pp, k, src)
    f = find_deform(T, Tb); donor = None
    if f is not None and (f[3] or not (force_donor and donors)):
        i, r, w1, ident = f; Td = T
    else:
        for dk, (Tdn, di, dr) in sorted(donors, key=lambda d: abs(d[0] - k)):
            w = check_donor(T, Tb, Tdn, di, dr)
            # the donor D is the same formula; in a skinned slot evaluated in a different order (deform, then skin vs
            # skin, then deform): equal up to float rounding -> range-normalised error < 1e-5
            if w < DONOR_TOL: donor = dk; Td, i, r, w1, ident = Tdn, di, dr, w, False; break
        if donor is None:
            if f is not None: i, r, w1, ident = f; Td = T          # (force_donor only) the slot's own D is proven
            else: raise NoDecomp('no decomposition T == Tb o D')
    # (2) the plain base pair itself on this slot: every common output equal, except the position in the Nixxes
    #     depth-pass slots (bit 3 / 4: Xbox z *= |w| removed on PC)
    pb = V.compare_outputs(Tb, P) or {}
    bad = {s: e for s, e in pb.items() if e >= 1e-4 and not (s == (0, 0) and k & 24)}
    if bad: raise xenos2sm3.Reject('base pair differs on %s' % {('%s%d' % (V.USAGE_NAME.get(s[0]), s[1])): round(e, 4) for s, e in bad.items()})
    moved = {}
    if ident: PD = P; w3 = 0.0
    else:
        Td1, mv = remap_defs(Td, P); moved.update(mv)
        PD = compose(P, Td1, i, r)
        w3 = check_compose(PD, P, Td1, i, r)
    if w3 > TOL: raise xenos2sm3.Reject('composition check %.3g' % w3)
    T2, mv = remap_defs(T, PD); moved.update(mv)
    # 08.11.: merge_slot shares identical defs and moves clashing ones itself (both directions); a T stripped of its
    # shared defs would look like T reading the twin's literal as an engine constant
    M, added = V.merge_slot(PD, T2, ())
    w4 = V.check_merge(M, PD, T2, ()) if added else 0.0
    if w4 > TOL: raise xenos2sm3.Reject('merge check %.3g' % w4)
    w5 = None
    if ref is not None:
        R = ref
        keys = set(V.dcls(M, sm3asm.RT_INPUT).values()) | set(V.dcls(R, sm3asm.RT_INPUT).values())
        w5 = 0.0; mR = V.out_masks(R); mM = V.out_masks(M)
        for s in SEEDS:
            ins, consts = rand_inputs(keys, 200, s)
            om, _ = run_regs(M, ins, consts, 200); orf, _ = run_regs(R, ins, consts, 200)
            for kk, v in orf.items():
                if kk not in om: w5 = 1e9; break
                e = relerr(om[kk], v, mR.get(kk, 15) & mM.get(kk, 15))
                if e >= 1e-4 and DEBUG:
                    m = [c for c in range(4) if (mR.get(kk, 15) & mM.get(kk, 15)) >> c & 1]
                    a, b = om[kk][:, m].astype(np.float64), v[:, m].astype(np.float64)
                    rn = float((np.abs(a - b).max(axis=0) / (1 + np.abs(b).max(axis=0))).max())
                    j = int(np.argmax((np.abs(a - b) / (1 + np.abs(b))).max(axis=1)))
                    print('   debug ref slot %d seed %d output %s: per-vertex rel %.3g, range-normalised %.3g; worst vertex M %s Nixxes %s' % (
                        k, s, kk, e, rn, np.round(a[j], 5), np.round(b[j], 5)))
                w5 = max(w5, e)
    info = dict(prefix=i, reg=r, ident=ident, decomp=w1, base_diff=sorted(s for s, e in pb.items() if e >= 1e-4), comp=w3,
                merge=w4, added=added, ref=w5, donor=donor, moved=moved, own=(None if ident or donor is not None else (k, T, i, r)))
    return M, info


def build_all(Dl, Xp, Pp, slots_of, refs=None):
    """every PC slot k in slots_of (with its DLC slot src): pass 1 with each slot's own D, pass 2 with donor Ds (same
    family bit 7) for the slots without own decomposition. -> {k: (M, info, src) | (None, error, src)}"""
    res = {}; donors = collections.defaultdict(list)
    for k, src in slots_of:
        try:
            M, info = build_slot(Dl, Xp, Pp, k, src, [], ref=(refs or {}).get(k))
            res[k] = (M, info, src)
            if info['own']: donors[k & 128].append((k, info['own'][1], info['own'][2], info['own'][3]))
        except NoDecomp as e: res[k] = (None, 'NODECOMP', src)
        except Exception as e: res[k] = (None, str(e), src)
    # canonical D per family: the own D of the lowest slot of that family; pass 2 puts it on every deformed slot
    canon = {fam: min(ds, key=lambda d: d[0]) for fam, ds in donors.items()}
    for k, src in slots_of:
        if res[k][1] != 'NODECOMP' and not (res[k][0] is not None and not res[k][1]['ident']): continue
        cd = canon.get(k & 128)
        if cd is None and res[k][1] != 'NODECOMP': continue
        try:
            M, info = build_slot(Dl, Xp, Pp, k, src, [], ref=(refs or {}).get(k), donors=[(cd[0], (cd[1], cd[2], cd[3]))] if cd else [],
                                 force_donor=True)
            res[k] = (M, info, src)
        except Exception as e:
            if res[k][0] is not None: continue          # keeps its own proven D
            res[k] = (None, ('no decomposition T == Tb o D (own prefix, canonical D of slot %s)' % (cd[0] if cd else 'none')) if isinstance(e, NoDecomp) else str(e), src)
    return res


def fmt_info(k, src, info):
    s = 'slot %3d%s: ' % (k, ' (DLC %d)' % src if src != k else '')
    s += 'D = identity' if info['ident'] else 'D = %sfirst %d instr (r%d), T == Tb o D %.1g' % (
        'donor slot %d: ' % info['donor'] if info['donor'] is not None else '', info['prefix'], info['reg'], info['decomp'])
    if info['moved']: s += ', defs moved %s' % ' '.join('c%d->c%d' % kv for kv in sorted(info['moved'].items()))
    if info['base_diff']: s += ', base pair: Nixxes depth position'
    if not info['ident']: s += ', twin o D check %.1g' % info['comp']
    if info['added']: s += ', + %s (merge %.1g)' % (['%s%d' % (V.USAGE_NAME.get(a[0]), a[1]) for a in info['added']], info['merge'])
    if info['ref'] is not None: s += ', vs Nixxes PC %s' % ('EXACT' if info['ref'] < 1e-4 else 'DIFF %.3g' % info['ref'])
    return s


STATS = collections.defaultdict(lambda: [0, 0])


def cmd_oracle(pairs, xp, pp, only=None):
    """base Xbox VS that deform (X') with Nixxes' PC twin P': the construction (X' on plain base xp / twin pp) must give
    Nixxes' P' on every output, every slot (or the slots in `only`)"""
    L = libs(); X, P = L['X'], L['P']; tot = ok = 0; rej = collections.Counter()
    for xd, pd in pairs:
        res = []; sl = []; refs = {}
        for k, o in enumerate(P[pd]['slots']):
            if o == 0xffffffff or k >= len(P[pp]['slots']) or P[pp]['slots'][k] == 0xffffffff: continue
            if only and k not in only: continue
            Pq, _ = slot_prog(P[pp], k)
            src = dlc_src_slot(X[xd], Pq, k)
            if src >= len(X[xd]['slots']) or X[xd]['slots'][src] == 0xffffffff or src >= len(X[xp]['slots']) or X[xp]['slots'][src] == 0xffffffff: continue
            refs[k] = slot_prog(P[pd], k)[0]; sl.append((k, src))
        out = build_all(X[xd], X[xp], P[pp], sl, refs)
        for k, src in sl:
            M, info, _ = out[k]
            if M is None:
                rej[info[:60]] += 1; res.append('s%d:rej(%s)' % (k, info[:40])); continue
            tot += 1; good = info['ref'] < 1e-4; ok += good
            res.append('s%d=%s%s' % (k, 'ok' if good else 'DIFF%.3g' % info['ref'], '' if info['ident'] else '(D%d%s)' % (
                info['prefix'], '' if info['donor'] is None else ' from s%d' % info['donor'])))
            STATS['ident' if info['ident'] else ('donor' if info['donor'] is not None else 'own')][0 if good else 1] += 1
            if not (k & 24) or info['ident']: pass
            else: STATS['depth-pass deformed'][0 if good else 1] += 1
        print('%d/%d: %s' % (xd, pd, ' '.join(res)), flush=True)
    print('per kind (exact / not exact): %s' % {k: tuple(v) for k, v in STATS.items()})
    print('SUMMARY deform oracle (plain base %d / %d): %d of %d constructed slots == Nixxes PC; rejects %s' % (xp, pp, ok, tot, dict(rej.most_common(10))))


def cmd_build(dl, xp, pp, outp):
    import column_shader_translate as CST, fade_slots_translate as FST
    L = libs(); D, Xp, Pp = L['D'][dl], L['X'][xp], L['P'][pp]
    slots = []; uniq = {}; taken = FST.known_hashes(); cnt = collections.Counter(); lines = []
    sl = []
    for k, o in enumerate(Pp['slots']):
        if o == 0xffffffff: continue
        P = F9.decode_pc(CST.trim(Pp['entries'][o]['blob'])); src = dlc_src_slot(D, P, k)
        if src < len(D['slots']) and D['slots'][src] != 0xffffffff: sl.append((k, src))
    out = build_all(D, Xp, Pp, sl)
    for k, o in enumerate(Pp['slots']):
        if o == 0xffffffff: slots.append(None); continue
        pblob = CST.trim(Pp['entries'][o]['blob'])
        keep = (Pp['entries'][o]['hash'], pblob)
        if k not in out:
            slots.append(keep); cnt['no DLC slot, twin kept'] += 1; lines.append('slot %3d: no DLC slot - twin kept' % k); continue
        M, info, src = out[k]
        if M is None:
            msg = info
            if 'palette fetch' in msg or 'VS export' in msg or 'VS texture fetch' in msg:
                # as tu_vs vsmerge: a DLC slot the translator cannot read (multi-bone palette) keeps the twin, listed
                slots.append(keep); cnt['DLC slot not translatable, twin kept'] += 1; lines.append('slot %3d: DLC slot not translatable (%s) - twin kept' % (k, msg[:70])); continue
            if msg.startswith('no decomposition') and (1, 0) in V.dcls(F9.decode_pc(pblob), sm3asm.RT_INPUT).values():
                # multi-bone (BLENDWEIGHT) slot: never selected for one-bone meshes (SKININDICES, no BLENDWEIGHT -
                # checked per object with mesh_render_dump); twin kept, listed - as tu_vs vsmerge kept undecidable slots
                slots.append(keep); cnt['blendweight slot without decomposition, twin kept'] += 1
                lines.append('slot %3d: BLENDWEIGHT slot, %s - twin kept (not drawn for one-bone meshes)' % (k, msg)); continue
            for l in lines: print(l)
            raise SystemExit('REFUSED VS %d slot %d: %s' % (dl, k, msg))
        if info['ident'] and not info['added']:
            slots.append(keep); cnt['nothing to add, twin kept'] += 1; lines.append('slot %3d: D = identity, nothing to add - twin kept' % k); continue
        bc = sm3asm.encode(M); ok_, msg = FST.SV.assemble(FST.SD.disasm(bc))
        if not ok_ or msg.strip():
            open(outp + '.bad_s%d.txt' % k, 'w').write(FST.SD.disasm(bc) + '\n' + msg)
            raise SystemExit('REFUSED VS %d slot %d: D3DX9 %s' % (dl, k, msg.strip()[:100]))
        if bc not in uniq: uniq[bc] = CST.new_hash(bc, taken)
        slots.append((uniq[bc], bc)); cnt['deformed' if not info['ident'] else 'twin + added'] += 1
        lines.append(fmt_info(k, src, info) + ', D3DX9 ok')
    j = {e['junk'] for e in Pp['entries'].values()}
    data = CST.pc_lib(Pp['kind'], slots, j.pop() if len(j) == 1 else 0)
    open(outp, 'wb').write(data)
    for l in lines: print(l)
    import hashlib
    print('RESULT VS %d (plain base %d / twin PC %d): %s; %d unique new entries, %d bytes, md5 %s' % (
        dl, xp, pp, dict(cnt), len(uniq), len(data), hashlib.md5(data).hexdigest()))


def dlc_src_slot(D, P, k):
    """as tu_vs.cmd_vsmerge: the DLC slot for PC slot k (k, or k + 8 for the PC fog slots that take the Xbox fog group)"""
    src = k
    pouts = set(V.dcls(P, sm3asm.RT_TEXOUT).values())
    try:
        if (5, 5) in pouts and k + 8 < len(D['slots']) and D['slots'][k + 8] != 0xffffffff and \
                not any((v['usage'], v['index']) == (5, 5) for v in XL.parse(D['entries'][D['slots'][k]]['blob']).interp):
            src = k + 8
    except Exception: pass
    return src


def cmd_decomp(dl, xb, pc):
    L = libs(); D, Pl, Xb = L['D'][dl], L['P'][pc], L['X'][xb]
    cnt = collections.Counter()
    for k, o in enumerate(Pl['slots']):
        if o == 0xffffffff: continue
        P, pct = slot_prog(Pl, k)
        src = dlc_src_slot(D, P, k)
        if src >= len(D['slots']) or D['slots'][src] == 0xffffffff: print('slot %3d: no DLC slot' % k); cnt['no DLC slot'] += 1; continue
        if src >= len(Xb['slots']) or Xb['slots'][src] == 0xffffffff: print('slot %3d: no base slot %d' % (k, src)); cnt['no base slot'] += 1; continue
        try:
            T, _ = V.translate(D['entries'][D['slots'][src]]['blob'], pct, 'auto')
            Tb, _ = V.translate(Xb['entries'][Xb['slots'][src]]['blob'], pct, 'auto')
        except Exception as e:
            print('slot %3d: not translatable (%s)' % (k, str(e)[:80])); cnt['not translatable'] += 1; continue
        f = find_deform(T, Tb)
        if f is None: print('slot %3d (DLC %d): NO decomposition T == Tb o D' % (k, src)); cnt['no decomposition'] += 1; continue
        i, r, w, ident = f
        print('slot %3d (DLC %d): T == Tb o D, D = first %d instr, position := r%d.xyz, worst %.1g%s' % (k, src, i, r, w, ' (D = identity)' if ident else ''))
        cnt['identity' if ident else 'deform'] += 1
    print('SUMMARY decomp %d / %d / %d: %s' % (dl, xb, pc, dict(cnt)))


def cmd_deformers(maxn=0):
    """base Xbox VS libs (with a PC twin) whose depth-pass slots (bit 3 / 4) read the normal: vertex deformation in the
    depth pass. Lists how Nixxes' PC twin slot reads it (inputs, NormalScaleOffset in its CTAB)."""
    L = libs(); X, P = L['X'], L['P']; n = 0
    for xb, pb in V.vs_pairs():
        hits = []
        for k, o in enumerate(X[xb]['slots']):
            if o == 0xffffffff or not (k & 24) or k >= len(P[pb]['slots']) or P[pb]['slots'][k] == 0xffffffff: continue
            sh = XL.parse(X[xb]['entries'][o]['blob'])
            if not any(v['usage'] == 3 for v in sh.vtx): continue
            Pp, pct = slot_prog(P[pb], k)
            pin = sorted(V.dcls(Pp, sm3asm.RT_INPUT).values())
            hits.append('s%d[pc in %s%s]' % (k, ','.join('%s%d' % (V.USAGE_NAME.get(u, u), i) for u, i in pin),
                                              ' NSO' if any(c[0] == 'NormalScaleOffset' for c in pct) else ''))
        if hits:
            n += 1
            print('%d/%d: %s' % (xb, pb, ' '.join(hits)), flush=True)
            if maxn and n >= maxn: break
    print('SUMMARY deformers: %d base VS pairs read the normal in a depth-pass slot' % n)


def cmd_nsorule():
    """every base PC VS slot that declares a normal / tangent / binormal input: does its CTAB have NormalScaleOffset,
    by slot bit 7 (counts per (bit 7, NSO yes / no)); and does the code actually use c21 (NSO register) then"""
    L = libs(); cnt = collections.Counter(); ex = {}
    for pid, lib in L['P'].items():
        if lib['kind'] != 0: continue
        for k, o in enumerate(lib['slots']):
            if o == 0xffffffff: continue
            P, pct = slot_prog(lib, k)
            ins = set(V.dcls(P, sm3asm.RT_INPUT).values())
            if not any(u in (3, 6, 7) for u, i in ins): continue
            nso = any(c[0] == 'NormalScaleOffset' for c in pct)
            reg = next((c[2] for c in pct if c[0] == 'NormalScaleOffset'), None)
            used = reg is not None and any(op.rtype == sm3asm.RT_CONST and op.num == reg for i in P.instrs() for op in i.ops)
            key = ('bit7=%d' % (k >> 7 & 1), 'NSO' if nso else 'no NSO', 'c%s used' % reg if used else ('-' if reg is None else 'c%s unused' % reg))
            cnt[key] += 1; ex.setdefault(key, (pid, k))
    for key, n in sorted(cnt.items()): print('%-40s %6d slots   e.g. PC %d slot %d' % (' / '.join(key), n, ex[key][0], ex[key][1]))


def cmd_treecheck(tree, specs):
    """specs VSID:LIBFILE:MAT[+MAT]: in every DRM of TREE/mods that has one of the materials: the material's VS id ==
    VSID, the section (9, VSID) == LIBFILE byte for byte (as packed), and every interpolator its pass-2 PS reads is
    written by an occupied slot of the VS"""
    import drm_write as DW
    import shaderlib as SL_
    tot = ok = 0
    for sp in specs:
        vid, libf, mats = sp.split(':'); vid = int(vid); mats = {int(m) for m in mats.split('+')}
        data = open(libf, 'rb').read()
        md = os.path.join(tree, 'mods')       # 05.11.: mods\streamgroups\ too (area DRMs carry material copies)
        fl = sorted(os.listdir(md)) + (['streamgroups/' + x for x in sorted(os.listdir(os.path.join(md, 'streamgroups')))]
                                       if os.path.isdir(os.path.join(md, 'streamgroups')) else [])
        for f in fl:
            if not f.lower().endswith('.drm'): continue
            D = DW.read(open(os.path.join(tree, 'mods', f), 'rb').read(), 'le')
            sec = {(s.type, s.id): s for s in D.sections}
            for m in sorted(mats):
                if (10, m) not in sec: continue
                tot += 1
                t = struct.unpack_from('<4I', sec[(10, m)].data, 0x28)
                good = t[3] == vid and (9, vid) in sec and sec[(9, vid)].data == data
                outs = set()
                L_ = SL_.parse(sec[(9, vid)].data, 'le') if (9, vid) in sec else None
                if L_:
                    for o in set(x for x in L_['slots'] if x != 0xffffffff):
                        outs |= set(V.dcls(F9.decode_pc(L_['entries'][o]['blob']), sm3asm.RT_TEXOUT).values())
                need = set()
                if (9, t[2]) in sec:
                    PL = SL_.parse(sec[(9, t[2])].data, 'le')
                    for o in set(x for x in PL['slots'] if x != 0xffffffff):
                        need |= {s for s in V.dcls(F9.decode_pc(PL['entries'][o]['blob']), sm3asm.RT_INPUT).values() if s[0] in (5, 10)}
                miss = need - outs
                good = good and not miss
                ok += good
                print('%s %-42s mat %d: VS %d (want %d), lib bytes %s, PS %d reads %s, VS writes them: %s' % (
                    'OK  ' if good else 'FAIL', f, m, t[3], vid, 'equal' if (9, vid) in sec and sec[(9, vid)].data == data else 'DIFFERENT',
                    t[2], sorted(need), 'yes' if not miss else 'missing %s' % sorted(miss)))
    print('SUMMARY treecheck: %d of %d material copies ok' % (ok, tot))


def cmd_defscan(paths):
    """VS lib files (PC): per lib the slots whose `def` constants lie inside a relatively addressed range they read
    (c[a0 + base] .. base + 167, SkinMatrices) - a def there shadows the bone rows of the engine upload"""
    import shaderlib as SL_
    for pth in paths:
        L_ = SL_.parse(open(pth, 'rb').read(), 'le'); hits = []; n = 0
        for k, o in enumerate(L_['slots']):
            if o == 0xffffffff: continue
            prog = F9.decode_pc(L_['entries'][o]['blob']); n += 1
            rel = [op.num for x in prog.instrs() for op in x.ops if op.rtype == sm3asm.RT_CONST and op.rel]
            if not rel: continue
            lo, hi = min(rel + [85]), 85 + 167
            bad = sorted(x.ops[0].num for x in prog.instrs() if x.op == 'def' and lo <= x.ops[0].num <= hi)
            if bad: hits.append('s%d:c%s' % (k, ','.join(map(str, bad))))
        print('%s: %d slots, %d with defs inside the SkinMatrices range: %s' % (os.path.basename(pth), n, len(hits), ' '.join(hits[:12]) + (' ...' if len(hits) > 12 else '')))


def main(a):
    global DEBUG
    if a and a[0] == 'treecheck': cmd_treecheck(a[1], a[2:]); return
    if a and a[0] == 'defscan': cmd_defscan(a[1:]); return
    if not a: sys.exit(__doc__)
    if '--debug' in a: a.remove('--debug'); DEBUG = True
    if a[0] == 'dcmp':              # dcmp DLCVS XBASE PCTWIN SLOT SLOT...: the D values of several slots on the same vertices
        L = libs(); D, Xb, Pl = L['D'][int(a[1])], L['X'][int(a[2])], L['P'][int(a[3])]; vals = {}
        for k in [int(x) for x in a[4:]]:
            P, T, Tb = translate_pair(D, Xb, Pl, k, dlc_src_slot(D, slot_prog(Pl, k)[0], k)); f = find_deform(T, Tb)
            keys = set(V.dcls(T, sm3asm.RT_INPUT).values()) | {(0, 0), (3, 0), (5, 0), (5, 1), (10, 0), (6, 0), (7, 0), (2, 0), (1, 0)}
            ins, consts = rand_inputs(keys, 200, 3)
            vals[k] = run_regs(T, ins, consts, 200, upto=f[0])[1][f[1]][:, :3].astype(np.float64)
            print('slot %d: D = first %d instr, r%d' % (k, f[0], f[1]))
        ks = list(vals)
        for k in ks[1:]:
            d = np.abs(vals[k] - vals[ks[0]]); print('D(slot %d) vs D(slot %d): max abs %.3g, max rel %.3g, bit-identical %s' % (
                k, ks[0], d.max(), (d / (1 + np.abs(vals[ks[0]]))).max(), bool((vals[k] == vals[ks[0]]).all())))
        return
    if a[0] == 'decomp1':           # decomp1 DLCVS XBASE PCTWIN SLOT: one slot, debug output
        L = libs(); D, Xb, Pl = L['D'][int(a[1])], L['X'][int(a[2])], L['P'][int(a[3])]; k = int(a[4])
        P, pct = slot_prog(Pl, k); src = dlc_src_slot(D, P, k)
        P, T, Tb = translate_pair(D, Xb, Pl, k, src)
        print('T outputs', V.dcls(T, sm3asm.RT_TEXOUT), 'Tb outputs', V.dcls(Tb, sm3asm.RT_TEXOUT))
        print('T inputs', V.dcls(T, sm3asm.RT_INPUT), 'Tb inputs', V.dcls(Tb, sm3asm.RT_INPUT))
        print(find_deform(T, Tb))
        if len(a) > 5:              # donor slot: its own D, then the donor check on this slot
            dk = int(a[5]); Pd_, Td, Tbd = translate_pair(D, Xb, Pl, dk, dlc_src_slot(D, slot_prog(Pl, dk)[0], dk))
            fd = find_deform(Td, Tbd); print('donor', dk, fd)
            if fd: print('donor check worst', check_donor(T, Tb, Td, fd[0], fd[1]))
            print(sm3asm.format_program(T))
        return
    if a[0] == 'nsorule': cmd_nsorule(); return
    if a[0] == 'deformers': cmd_deformers(int(a[1]) if len(a) > 1 else 0); return
    if a[0] == 'pcinfo': cmd_pcinfo(int(a[1]), {int(x) for x in a[2].split(',')} if len(a) > 2 else None); return
    if a[0] == 'decomp': cmd_decomp(int(a[1]), int(a[2]), int(a[3])); return
    if a[0] == 'oracle':
        only = None
        if '--slots' in a: j = a.index('--slots'); only = {int(x) for x in a[j + 1].split(',')}; del a[j:j + 2]
        cmd_oracle([tuple(int(y) for y in x.split('/')) for x in a[1].split(',')], int(a[2]), int(a[3]), only); return
    if a[0] == 'build': cmd_build(int(a[1]), int(a[2]), int(a[3]), a[4]); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
