"""Own fade (odd-slot) pixel-shader libraries for one object (test 48g, Befund-Felsrinne.md "Test 48g").

Background (test 48e / 48f): tru.exe picks the pass pixel shader as slot (b0 | light bits); b0 = 1 for some drawn
instances (the doppelganger ~10 s into DLC 2). PC base libraries of Lara's family have their odd slots empty (retail
never selects them) and +0x1260e0 does not test for 0xFFFFFFFF -> CreatePixelShader on garbage -> the driver box.
Shader libraries are resident ONCE per id (live run 20261031_215609: lib 801 in memory is the base copy, the DLC copy
with patched slots is ignored), so the object needs its own libraries under new ids.

Translation rule (decided on the data, `survey`):
* pass-2 libs (PC 8 slots = Xbox slot k & 1 x light bits): the Xbox slot 1 of the object's own Xbox library (the TU /
  base Xbox counterpart, paired by material position) differs from slot 0 only in the alpha output. Two forms occur:
  - `oC0.w = 0.0` (no MaterialOpacity): PC odd = PC even of the same light bits with oC0.w := 0;
  - luminance form `oC0.w = MaterialParams[i].c * (sum of the lit diffuse rgb) / 3` (e.g. TU 2632): PC odd = PC even
    with oC0.w := (r + g + b of the PC register that holds the same term) * c(100+i).c * 1/3. The PC register is the
    addend of the colour mad that adds the specular term (matched per library, see LUM_TERM) - same construction as
    Nixxes' own odd entries of base libs 25 / 29 (`survey` checks the rule on every base pair that has odd slots).
* pass-0 libs (PC 4 slots: 0 / 1 = Xbox 0 / 1, 2 = PC-only depth-into-colour, 3 = empty everywhere in the base game):
  slot 3 = depth permutation of the bit-0 variant. Xbox / PC slot 0 and 1 differ only in the colour constant written;
  the kill is the same (VM-checked here); slot 2 writes packed depth into all four lanes, so slot 3 == slot 2's entry.
Anything that does not match these forms -> workaround for that lib (odd slot = even entry, as 48f), reported.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/fade_slots_translate.py survey
      rule check on the base pairs (Xbox slot 1 alpha form vs Nixxes' PC odd entries)
  ../bin/pyt -t 900 tools/fade_slots_translate.py build PC.drm XBOX.drm OUT_DIR FIRST_FREE_ID LIB[,LIB...]
      writes OUT_DIR/<newid>.lib per library + OUT_DIR/map.json (old -> new id, method) + OUT_DIR/build.txt + asm
  ../bin/pyt -t 600 tools/fade_slots_translate.py apply IN.drm OUT.drm OUT_DIR [--mats ID,ID | --all-mats]
      adds the new ShaderLib sections (after the old one) and points the materials' PS slots old -> new
"""
import sys, os, re, struct, json, pickle, hashlib, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
S4 = os.path.join(ROOT, 'work', 'ws', 'shader4')
sys.path.insert(0, HERE); sys.path.insert(0, S4); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
import drm_write as DW, drm_reloc as R, shaderlib as SL
import xenos_xlat as XL, sm3asm, sm3dis, sm3vm, f4_lint
from sm3asm import Instr, Operand, RT_TEMP, RT_INPUT, RT_CONST, RT_COLOROUT
import shader_disasm as SD, shader_validate as SV
import ps_odd_slots as POS

LOG = []
NONE = 0xffffffff
FIRST_THIRD = 1.0 / 3.0


def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.append(s)


def trim(b): return bytes(b[:sm3dis.bytecode_len(b)])


def xlines(blob): return XL.text(XL.parse(blob), 'pretty').lines


# ------------------------------------------------------------------------------------------------ alpha forms
def xbox_alpha(blob):
    """Xbox slot alpha form: ('zero',) | ('lum', i, comp) | ('other', line)"""
    L = [l.strip() for l in xlines(blob)]
    w = [k for k, l in enumerate(L) if re.match(r'oC0\.(x?y?z?w) = ', l) and 'w' in l.split('=')[0]]
    if not w: return ('none',)
    k = w[-1]; rhs = L[k].split('=', 1)[1].strip().rstrip(';')
    if rhs in ('0.0', '0'): return ('zero',)
    if rhs == 'ps':
        j = next(j for j in range(k - 1, -1, -1) if L[j].startswith('ps = '))
        m = re.search(r'MaterialParams(?:\[(\d+)\])?\.([xyzw])\b', L[j])
        if m: return ('lum', int(m.group(1) or 0), m.group(2), L[j])
    return ('other', L[k])


def pc_defs(prog):
    return {i.ops[0].num: list(i.imm) for i in prog.instrs() if i.op == 'def'}


def lane(swz, k): return (swz >> (2 * k)) & 3


def pc_alpha(prog):
    """PC entry alpha form: ('opacity',) mov oC0.w, c98 | ('zero',) | ('lum', i, comp) | ('other', text)"""
    ins = prog.instrs(); defs = pc_defs(prog)
    ws = [k for k, i in enumerate(ins) if i.ops and i.ops[0].isdst and i.ops[0].rtype == RT_COLOROUT and i.ops[0].num == 0
          and i.ops[0].wm & 8]
    if not ws: return ('none',)
    k = ws[-1]; i = ins[k]
    if i.op == 'mov' and i.ops[1].rtype == RT_CONST:
        c = i.ops[1].num; l = lane(i.ops[1].swz, 3)
        if c == 98: return ('opacity',)
        if c in defs and defs[c][l] == 0.0: return ('zero',)
        return ('other', 'mov const c%d' % c)
    # luminance: walk back over the mul chain feeding oC0.w, collect the MaterialParams register
    for j in range(k, max(k - 6, -1), -1):
        for o in ins[j].ops[1:]:
            if o.rtype == RT_CONST and 100 <= o.num < 132 and o.num not in defs:
                return ('lum', o.num - 100, 'xyzw'[lane(o.swz, 0)])
    return ('other', i.op)


# ------------------------------------------------------------------------------------------------ PC rewrite
def free_const(prog):
    used = set(pc_defs(prog))
    for i in prog.instrs():
        for o in i.ops:
            if o.rtype == RT_CONST: used.add(o.num)
    for it in prog.items:
        pass
    ct = SL.constants(sm3asm.encode(prog), 'p')[1]
    for n, rs, ri, rc in ct:
        if rs == 2: used |= set(range(ri, ri + rc))
    return next(c for c in range(223, 3, -1) if c not in used)


def max_temp(prog):
    return max([o.num for i in prog.instrs() for o in i.ops if o.rtype == RT_TEMP] + [-1])


def insert_def(prog, num, vals):
    items = prog.items
    k = max(n for n, it in enumerate(items) if isinstance(it, Instr) and it.op in ('dcl', 'def', 'defi', 'defb'))
    raw = [struct.unpack('<I', struct.pack('<f', v))[0] for v in vals]       # def immediates are u32 bit patterns
    items.insert(k + 1, Instr('def', [Operand(RT_CONST, num, isdst=True, wm=15)], imm=raw))


def odd_from_even(bc, form, term=None):
    """PC even entry -> odd entry with the alpha of `form`; returns (bytecode, note)"""
    prog = sm3asm.decode(trim(bc)); ins = prog.instrs()
    ws = [i for i in ins if i.ops and i.ops[0].isdst and i.ops[0].rtype == RT_COLOROUT and i.ops[0].num == 0 and i.ops[0].wm & 8]
    if len(ws) != 1: raise ValueError('%d oC0.w writes' % len(ws))
    W = ws[0]
    if W.ops[0].wm != 8 or W.pred:
        raise ValueError('even alpha write is not a single oC0.w instruction (%s, mask %d)' % (W.op, W.ops[0].wm))
    if not any(o.rtype == RT_CONST and o.num == 98 for o in W.ops[1:]):
        raise ValueError('even alpha does not read MaterialOpacity c98 (%s)' % W.op)
    # the odd variant replaces the whole alpha instruction (Xbox slot 1 has no MaterialOpacity); the dead inputs stay
    k = prog.items.index(W)
    W = Instr('mov', [Operand(RT_COLOROUT, 0, isdst=True, wm=8, mod=W.ops[0].mod), Operand(RT_CONST, 98, swz=0)])
    prog.items[k] = W
    pp = W.ops[0].mod
    if form[0] == 'zero':
        defs = pc_defs(prog); z = None
        for c, v in sorted(defs.items()):
            l = next((q for q in range(4) if v[q] == 0.0), None)
            if l is not None: z = (c, l); break
        if z is None:
            c = free_const(prog); insert_def(prog, c, [0.0, 0.0, 0.0, 0.0]); z = (c, 0); note = 'new def c%d = 0' % c
        else: note = 'def c%d.%s = 0' % (z[0], 'xyzw'[z[1]])
        W.ops[1] = Operand(RT_CONST, z[0], swz=z[1] * 0x55)
        return sm3asm.encode(prog), 'oC0.w := 0 (%s)' % note
    if form[0] == 'lum':
        i_, comp = form[1], 'xyzw'.index(form[2])
        ci, mode = term(prog)                   # colour instruction; 'addend' = its ops[3], 'product' = ops[1] * ops[2]
        srcs = [ci.ops[3]] if mode == 'addend' else [ci.ops[1], ci.ops[2]]
        if any(o.smod != 0 or o.rel for o in srcs): raise ValueError('term operand has a source modifier')
        t = max_temp(prog) + 1
        if t > 31: raise ValueError('no free temp')
        k3 = free_const(prog); insert_def(prog, k3, [FIRST_THIRD, FIRST_THIRD, FIRST_THIRD, 0.0])
        idx = prog.items.index(ci)
        cp = lambda o: Operand(o.rtype, o.num, swz=o.swz)
        pre = []
        if mode == 'product':
            pre.append(Instr('mul', [Operand(RT_TEMP, t, isdst=True, wm=7, mod=pp), cp(srcs[0]), cp(srcs[1])]))
            src = Operand(RT_TEMP, t)
        else: src = cp(srcs[0])
        pre.append(Instr('dp3', [Operand(RT_TEMP, t, isdst=True, wm=1, mod=pp), src, Operand(RT_CONST, k3)]))
        pre.append(Instr('mul', [Operand(RT_TEMP, t, isdst=True, wm=1, mod=pp), Operand(RT_TEMP, t, swz=0), Operand(RT_CONST, 100 + i_, swz=comp * 0x55)]))
        prog.items[idx:idx] = pre
        W.ops[1] = Operand(RT_TEMP, t, swz=0)
        return sm3asm.encode(prog), 'oC0.w := sum(%s).rgb / 3 * c%d.%s (r%d, def c%d)' % (
            ' * '.join('%s%d' % ('rcv'[o.rtype] if o.rtype < 3 else '?', o.num) for o in srcs), 100 + i_, form[2], t, k3)
    raise ValueError('form %s' % (form,))


def term_specular_mad(prog):
    """the colour sequence of the lit PC pass-2 shaders ends with  ... mul/mad rD.xyz (lit diffuse) ; mad rX.xyz, rS, rT,
    rD (+ specular) ; [mad rX.xyz, emissive...] ; fog. Returns the item index of the first mad after the last fog-free
    lit-diffuse write that adds into the pre-fog colour chain: the mad whose result reaches oC0.xyz through mad/add only and
    whose addend is a product (mul) - the Xbox 2632 structure (lit diffuse = r7 * albedo, then + spec, then + rim)."""
    items = prog.items; ins = [(n, it) for n, it in enumerate(items) if isinstance(it, Instr)]
    # final colour write and its pre-fog register
    fo = [(n, i) for n, i in ins if i.ops and i.ops[0].isdst and i.ops[0].rtype == RT_COLOROUT and i.ops[0].wm & 7]
    n0, F = fo[-1]
    reg = F.ops[3].num if F.op == 'mad' else None
    chain = []
    cur = reg; pos = n0
    while cur is not None:
        prev = [(n, i) for n, i in ins if n < pos and i.ops and i.ops[0].isdst and i.ops[0].rtype == RT_TEMP and i.ops[0].num == cur
                and i.ops[0].wm & 7]
        if not prev: break
        n, i = prev[-1]
        if i.op != 'mad' or i.ops[3].rtype != RT_TEMP: break
        chain.append((n, i)); cur = i.ops[3].num; pos = n
    return chain


# ------------------------------------------------------------------------------------------------ VM check
def vm_compare(bc_a, bc_b, N=256, seed=5):
    """same random interpolators / constants / textures: -> (max |rgb diff|, alpha_b range, kill equal)"""
    A, B = sm3asm.decode(trim(bc_a)), sm3asm.decode(trim(bc_b))
    rng = np.random.RandomState(seed); inp = {}
    for P_ in (A, B):
        for i in P_.instrs():
            if i.op == 'dcl' and i.ops[0].rtype == RT_INPUT and (RT_INPUT, i.ops[0].num) not in inp:
                inp[(RT_INPUT, i.ops[0].num)] = rng.uniform(-1, 1, (N, 4)).astype(np.float32)
    cs = {c: rng.uniform(0.05, 1.0, 4).astype(np.float32) for c in range(224)}
    tex = sm3vm.det_tex(lambda s: s)
    ra = sm3vm.run(A, inp, dict(cs), tex, N); rb = sm3vm.run(B, inp, dict(cs), tex, N)
    ca, cb = ra.get('oC0'), rb.get('oC0')
    ka = ra['kill'] if ra['kill'] is not None else np.zeros(N, bool)
    kb = rb['kill'] if rb['kill'] is not None else np.zeros(N, bool)
    live = ~(ka | kb)
    d = float(np.nanmax(np.abs(ca[live, :3] - cb[live, :3]))) if live.any() else 0.0
    return d, (float(np.nanmin(cb[live, 3])), float(np.nanmax(cb[live, 3]))) if live.any() else (0, 0), bool(np.all(ka == kb)), ca, cb, live


def valid(bc):
    errs = f4_lint.lint(bc, True); txt = SD.disasm(bc); ok, msg = SV.assemble(txt)
    return (not errs) and ok and not msg.strip(), txt, (errs or msg.strip()[:200])


# ------------------------------------------------------------------------------------------------ survey
def cmd_survey():
    L = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shaderlibs.pkl'), 'rb'))
    x2p = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shader_x2p.pkl'), 'rb'))
    tab = collections.Counter(); ex = collections.defaultdict(list); vm = collections.Counter()
    for xid, pid in sorted(x2p.items()):
        X = L['X'].get(xid); P = L['P'].get(pid)
        if not X or not P or X['kind'] != 1 or P['kind'] != 1 or len(X['slots']) != 2 or len(P['slots']) != 8: continue
        if X['slots'][1] == NONE: continue
        xf = xbox_alpha(X['entries'][X['slots'][1]]['blob'])
        for k in (1, 3, 5, 7):
            if P['slots'][k] == NONE or P['slots'][k - 1] == NONE:
                tab[(xf[0], 'pc-empty')] += 1; continue
            ob = P['entries'][P['slots'][k]]['blob']; eb = P['entries'][P['slots'][k - 1]]['blob']
            pf = pc_alpha(sm3asm.decode(trim(ob)))
            key = (xf[0], pf[0]); tab[key] += 1
            same = xf[0] == pf[0] and (xf[0] != 'lum' or (xf[1], xf[2]) == (pf[1], pf[2]))
            if not same and len(ex[key]) < 6: ex[key].append('x%d/p%d s%d %s | %s' % (xid, pid, k, xf[:3], pf))
            if xf[0] == 'zero' and pf[0] == 'zero':
                try:
                    nb, _ = odd_from_even(eb, xf)
                    d, ar, ke, *_ = vm_compare(ob, nb)
                    vm['zero rule: built == Nixxes (rgb diff < 1e-4, alpha 0, same kill)' if d < 1e-4 and ar == (0.0, 0.0) and ke else 'zero rule: differs'] += 1
                    if not (d < 1e-4 and ke) and len(ex['vmdiff']) < 8: ex['vmdiff'].append('x%d/p%d s%d d=%.4g kill %s' % (xid, pid, k, d, ke))
                except Exception as e_:
                    vm['zero rule: not buildable (%s)' % str(e_)[:50]] += 1
            if xf[0] == 'lum':
                ex['lum'].append('x%d/p%d s%d Xbox %s / PC %s' % (xid, pid, k, xf[1:3], pf[1:]))
                vm['lum: Xbox MaterialParams index/lane %s PC odd' % ('==' if pf[0] == 'lum' and (xf[1], xf[2]) == (pf[1], pf[2]) else '!=')] += 1
                if pf[0] == 'lum' and vm['lum checked'] < 240:
                    vm['lum checked'] += 1; hit = []
                    for nm, f in TERM_MODES.items():
                        try:
                            ch = term_specular_mad(sm3asm.decode(trim(eb)))
                            if not ch: continue
                            nb, _ = odd_from_even(eb, ('lum', pf[1], pf[2]), lambda prog, f=f: f(term_specular_mad(prog)))
                            d, ar, ke, ca, cb, live = vm_compare(ob, nb)
                            da = float(np.nanmax(np.abs(ca[live, 3] - cb[live, 3]))) if live.any() else 0.0
                            if d < 1e-4 and da < 2e-3 and ke: hit.append(nm)
                        except Exception:
                            pass
                    vm['lum: built alpha == Nixxes odd with term %s' % ('/'.join(hit) or 'none')] += 1
    log('base pairs Xbox 2-slot / PC 8-slot pass-2 PS (shader_x2p), Xbox slot 1 alpha form vs PC odd entry alpha form:')
    for k, v in sorted(tab.items()): log('  Xbox %-6s PC %-9s %5d odd slots' % (k[0], k[1], v))
    for k, v in sorted(vm.items()): log('  VM: %s: %d' % (k, v))
    for k, v in ex.items():
        for s in v[:12]: log('  e.g. %s: %s' % (k, s))


# ------------------------------------------------------------------------------------------------ build
def known_hashes():
    L = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shaderlibs.pkl'), 'rb'))
    hs = set()
    for k in ('P', 'X', 'D'):
        for lib in L[k].values():
            for e in lib['entries'].values(): hs.add(bytes(e['hash']))
    return hs


def new_hash(bc, taken):
    for salt in range(1000):
        h = hashlib.blake2b(b'TRU-DLC test48g|%d|' % salt + bc, digest_size=8).digest()
        if h not in taken: taken.add(h); return h
    raise RuntimeError('hash')


def cube_mask(bc):
    m = 0
    for i in sm3asm.decode(bc).instrs():
        if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_SAMPLER and (i.usage >> 27) & 15 == 3: m |= 1 << i.ops[0].num
    return m


def pc_lib(kind, sb, word0):
    """same layout as column_shader_translate.pc_lib (base PC convention, size word with the dcl_cube mask)"""
    n = len(sb); tb = 4 * n; body = bytearray(); offs = {}; slots = []
    for s in sb:
        if s is None: slots.append(NONE); continue
        h, bc, sz = bytes(s[0]), bytes(s[1]), s[2]
        if (h, bc) not in offs:
            offs[(h, bc)] = 8 + tb + len(body)
            body += struct.pack('<II', word0, sz if sz is not None else (16 + len(bc)) | (cube_mask(bc) << 16)) + h + bc
        slots.append(offs[(h, bc)])
    out = bytearray(bytes([kind, 0, 0, 0]) + struct.pack('<II', tb, 0) + struct.pack('<%dI' % n, *slots) + bytes(body))
    struct.pack_into('<I', out, 8, len(out) - 4)
    return bytes(out)


def xbox_counterparts(P, X, lid):
    pm = POS.mats(P, 'le'); xm = POS.mats(X, 'be'); out = collections.defaultdict(set)
    for i, (mid, sl) in enumerate(pm):
        for k in range(3):
            if sl[k] == lid and i < len(xm) and xm[i][1][k] is not None: out[xm[i][1][k]].add(mid)
    return out


def cmd_build(pc_drm, x_drm, outd, first, ids):
    os.makedirs(os.path.join(outd, 'asm'), exist_ok=True)
    P = DW.read(open(pc_drm, 'rb').read(), 'le'); X = DW.read(open(x_drm, 'rb').read(), 'be')
    pl = {s.id: s for s in P.sections if s.type == 9}; xl = {s.id: SL.parse(s.data, 'be') for s in X.sections if s.type == 9}
    taken = known_hashes(); nid = first; mp = {}; stats = collections.Counter()
    for lid in ids:
        sec = pl[lid]; lib = SL.parse(sec.data, 'le'); n = len(lib['slots'])
        words = {e['junk'] for e in lib['entries'].values()}; word0 = words.pop() if len(words) == 1 else 0
        sb = [None if s == NONE else (lib['entries'][s]['hash'], trim(lib['entries'][s]['blob']), lib['entries'][s]['size'])
              for s in lib['slots']]
        # keep the even entries byte for byte (hash, size word); check the rebuild of the unchanged lib first
        rt = pc_lib(lib['kind'], sb, word0)
        xc = xbox_counterparts(P, X, lid)
        forms = {}
        for xid in sorted(xc):
            xb = xl.get(xid)
            if xb and len(xb['slots']) > 1 and xb['slots'][1] != NONE: forms[xid] = xbox_alpha(xb['entries'][xb['slots'][1]]['blob'])
        log('lib %d (%d slots, word0 %#x, rebuild of the unchanged lib %s): Xbox counterparts %s, slot-1 alpha forms %s'
            % (lid, n, word0, 'identical' if rt == bytes(sec.data) else 'DIFFERS', {x: sorted(m) for x, m in xc.items()},
               {x: f[:3] for x, f in forms.items()}))
        method = None; notes = []
        holes = [k for k in range(1, n, 2) if lib['slots'][k] == NONE and lib['slots'][k - 1] != NONE]
        if n == 4:
            # pass 0: slot 3 = slot 2's entry; proof: slot 0 / 1 kill identical
            d, ar, ke, *_ = vm_compare(sb[0][1], sb[1][1])
            notes.append('VM slot 0 vs 1: kill identical %s' % ke)
            if holes == [3] and ke and sb[2] is not None:
                sb[3] = sb[2]; method = 'pass0: slot 3 = depth entry of slot 2 (bit 0 changes only the colour constant, kill identical)'
            else:
                sb[3] = sb[2]; method = 'WORKAROUND pass0: slot 3 = slot 2 (kill of slot 0 / 1 differ or layout unexpected)'
        else:
            fs = {f[:3] if f[0] == 'lum' else f[:1] for f in forms.values()}
            if len(fs) != 1:
                method = 'WORKAROUND: Xbox counterparts disagree / missing (%s)' % sorted(fs)
            else:
                form = next(iter(fs)); built = {}
                try:
                    for k in holes:
                        eb = sb[k - 1][1]
                        term = None
                        if form[0] == 'lum':
                            term = lambda prog: lum_term(lid, prog)
                        nb, note = odd_from_even(eb, form, term)
                        ok, txt, err = valid(nb)
                        if not ok: raise ValueError('not valid: %s' % err)
                        d, ar, ke, ca, cb, live = vm_compare(eb, nb)
                        if d > 1e-5 or not ke: raise ValueError('VM: rgb differs %.3g / kill %s' % (d, ke))
                        if form[0] == 'zero' and ar != (0.0, 0.0): raise ValueError('VM alpha %s' % (ar,))
                        open(os.path.join(outd, 'asm', '%d_s%d.asm' % (lid, k)), 'w').write(txt)
                        built[k] = nb; notes.append('slot %d: %s; D3DX ok; VM rgb == slot %d, alpha %.3f..%.3f, kill same' % (k, note, k - 1, ar[0], ar[1]))
                    for k, nb in built.items(): sb[k] = (new_hash(nb, taken), nb, None)
                    method = 'TRANSLATED from Xbox slot 1 (%s)' % ('alpha 0' if form[0] == 'zero' else 'luminance x MaterialParams[%d].%s / 3' % form[1:3])
                except Exception as e_:
                    notes.append('translation failed: %s' % e_)
                    method = 'WORKAROUND: %s' % str(e_)[:80]
            if method.startswith('WORKAROUND'):
                for k in holes: sb[k] = sb[k - 1]
        data = pc_lib(lib['kind'], sb, word0)
        chk = SL.parse(data, 'le')
        assert all(chk['slots'][k] != NONE for k in range(n) if lib['slots'][k] != NONE or k in holes)
        for k in range(0, n, 2):
            if lib['slots'][k] != NONE:
                e0 = lib['entries'][lib['slots'][k]]; e1 = chk['entries'][chk['slots'][k]]
                assert (e0['hash'], trim(e0['blob']), e0['size']) == (e1['hash'], trim(e1['blob']), e1['size'])
        open(os.path.join(outd, '%d.lib' % nid), 'wb').write(data)
        mp[lid] = dict(new=nid, method=method, notes=notes, md5=hashlib.md5(data).hexdigest(), bytes=len(data))
        stats['translated' if method.startswith(('TRANSLATED', 'pass0')) else 'workaround'] += 1
        log('  -> new lib %d: %s' % (nid, method))
        for s in notes: log('     %s' % s)
        nid += 1
    json.dump({str(k): v for k, v in mp.items()}, open(os.path.join(outd, 'map.json'), 'w'), indent=1)
    log('libraries: %s' % dict(stats))
    open(os.path.join(outd, 'build.txt'), 'w').write('\n'.join(LOG) + '\n')


# per-library location of the term the Xbox luminance alpha sums (filled after reading the PC epilogue)
LUM_TERMS = {
    # PC 801 (surrogate of TU 2632): colour = rim mad (chain[0]) <- mad lighting * albedo + specular (chain[-1]); the Xbox
    # 2632 slot 1 sums `r7 * albedo` (lighting x albedo, before + specular and + rim) -> the product of the innermost mad
    801: lambda prog, chain: (chain[-1][1], 'product'),
}
TERM_MODES = {'a0': lambda chain: (chain[0][1], 'addend'), 'p-1': lambda chain: (chain[-1][1], 'product'),
              'a-1': lambda chain: (chain[-1][1], 'addend'), 'p0': lambda chain: (chain[0][1], 'product')}


def lum_term(lid, prog):
    chain = term_specular_mad(prog)
    rule = LUM_TERMS.get(lid)
    if rule is None: raise ValueError('luminance form: no PC term rule for lib %d (chain %d mads)' % (lid, len(chain)))
    return rule(prog, chain)


# ------------------------------------------------------------------------------------------------ apply
def cmd_apply(src, out, outd, mats):
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    mp = {int(k): v for k, v in json.load(open(os.path.join(outd, 'map.json'))).items()}
    have = {s.id for s in D.sections if s.type == 9}
    for o, v in mp.items():
        if v['new'] in have: raise SystemExit('lib %d already in the file' % v['new'])
    # new sections right after the old lib of the same id (the lib must be in the file)
    added = []
    for o, v in sorted(mp.items()):
        old = next((s for s in D.sections if s.type == 9 and s.id == o), None)
        if old is None: continue
        data = open(os.path.join(outd, '%d.lib' % v['new']), 'rb').read()
        D.sections.insert(D.sections.index(old) + 1, DW.Section(9, v['new'], data, b'', flags=old.flags, ver=old.ver, spec=old.spec, pad=old.pad))
        added.append(v['new'])
    changed = []
    for s in D.sections:
        if s.type != 10 or (mats is not None and s.id not in mats): continue
        refs = set(R.parse(s.reloc, 'le').idref); d = bytearray(s.data); ch = []
        for k in range(3):
            off = 0x28 + 4 * k
            if (9, off) not in refs: continue
            v = struct.unpack_from('<I', d, off)[0]
            if v in mp and mp[v]['new'] in added:
                struct.pack_into('<I', d, off, mp[v]['new']); ch.append('p%d %d->%d' % (k, v, mp[v]['new']))
        if ch: s.data = bytes(d); changed.append((s.id, ch))
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    rest = [s for s in B if not (s.type == 9 and s.id in added)]
    assert len(rest) == len(A)
    diff = [(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc) != (b.type, b.id, b.data, b.reloc)]
    assert set(diff) == {(10, m) for m, _ in changed}, diff
    for lid in added:
        s = next(x for x in B if x.type == 9 and x.id == lid)
        assert s.data == open(os.path.join(outd, '%d.lib' % lid), 'rb').read()
    import section_id_free as SIF
    base10 = SIF.used_from_index(os.path.join(ROOT, 'work', 'idx_pc.json'), 10)
    for m, ch in changed: print('material %d%s: %s' % (m, ' (id also in the PC base index)' if m in base10 else '', ', '.join(ch)))
    print('materials changed whose id is also a base PC material id: %s' % (sorted(m for m, _ in changed if m in base10) or 'none'))
    print('readback: %d original sections in order, changed %d materials; %d new ShaderLibs %s' % (len(A), len(changed), len(added), added))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (out, hashlib.md5(o).hexdigest(), len(o)))


def cmd_reid(src, out, free):
    """Materials of the file that point at one of the new libs (2494-2531) and whose id is also a base PC material id get
    a new id (in file order, from FREE); every type-10 id reference (both relocation lists) in every section is moved.
    Reason: the engine keeps each (type, id) once - a resident base copy of material 851 would keep base lib 17."""
    import section_id_free as SIF
    base10 = SIF.used_from_index(os.path.join(ROOT, 'work', 'idx_pc.json'), 10)
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    mats = [s for s in D.sections if s.type == 10 and s.id in base10
            and any(2494 <= struct.unpack_from('<I', s.data, 0x28 + 4 * k)[0] <= 2531 for k in (0, 2))]
    have = {s.id for s in D.sections if s.type == 10}
    free = [f for f in free if f not in have]
    if len(free) < len(mats): raise SystemExit('need %d free ids, got %d' % (len(mats), len(free)))
    mp = {s.id: free[k] for k, s in enumerate(mats)}
    nref = collections.Counter()
    for s in D.sections:
        if not s.reloc: continue
        r = R.parse(s.reloc, 'le'); d = bytearray(s.data); ch = 0
        for t, off in list(r.idref_a) + list(r.idref):
            if t != 10 or off + 4 > len(d): continue
            v = struct.unpack_from('<I', d, off)[0]
            if v in mp: struct.pack_into('<I', d, off, mp[v]); ch += 1
        if ch: s.data = bytes(d); nref['%d:%d' % (s.type, s.id)] += ch
    for s in mats: s.id = mp[s.id]
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    B = DW.read(o, 'le')
    left = []
    for s in B.sections:
        if not s.reloc: continue
        r = R.parse(s.reloc, 'le')
        for t, off in list(r.idref_a) + list(r.idref):
            if t == 10 and off + 4 <= len(s.data) and struct.unpack_from('<I', s.data, off)[0] in mp: left.append((s.type, s.id, off))
    print('materials re-id\'d: %d (%s)' % (len(mp), ', '.join('%d->%d' % kv for kv in sorted(mp.items()))))
    print('id references moved: %d in %s; references to an old id left: %s' % (sum(nref.values()), dict(nref), left or 'none'))
    wd = os.path.join(ROOT, 'work', 'rebuild', 'test48g_work'); os.makedirs(wd, exist_ok=True)
    json.dump({str(k): v for k, v in mp.items()}, open(os.path.join(wd, os.path.basename(out) + '.reid.json'), 'w'), indent=1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (out, hashlib.md5(o).hexdigest(), len(o)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'survey': cmd_survey()
    elif a[0] == 'build': cmd_build(a[1], a[2], a[3], int(a[4]), [int(x) for x in a[5].split(',')])
    elif a[0] == 'scan':        # scan MODS_DIR [NAME_FILTER]: per DRM the PS libs with empty odd slots that materials use
        import convert_dlc, section_id_free as SIF
        base9 = SIF.used_from_index(os.path.join(ROOT, 'work', 'idx_pc.json'), 9)
        flt = a[2] if len(a) > 2 else ''
        for n in sorted(os.listdir(a[1])):
            if not n.lower().endswith('.drm') or flt not in n.lower(): continue
            try:
                P = DW.read(open(os.path.join(a[1], n), 'rb').read(), 'le')
            except Exception as e_:
                print('%s: not readable (%s)' % (n, e_)); continue
            holes = {}
            for s in P.sections:
                if s.type != 9: continue
                lib = SL.parse(s.data, 'le')
                if lib['kind'] != 1: continue
                if any(lib['slots'][k] == NONE and lib['slots'][k - 1] != NONE for k in range(1, len(lib['slots']), 2)): holes[s.id] = lib
            pm = POS.mats(P, 'le')
            try:
                raw, pk = convert_dlc.raw_dlc(n); X = DW.read(raw, 'be') if raw else None
            except Exception:
                X = None
            xm = POS.mats(X, 'be') if X else []
            xl = {s.id: SL.parse(s.data, 'be') for s in X.sections if s.type == 9} if X else {}
            rows = []
            for i, (mid, sl) in enumerate(pm):
                for k in (0, 2):
                    if sl[k] in holes:
                        f = '-'
                        if i < len(xm) and xm[i][1][k] in xl:
                            xb = xl[xm[i][1][k]]
                            f = 'x%d:%s' % (xm[i][1][k], xbox_alpha(xb['entries'][xb['slots'][1]]['blob'])[0] if len(xb['slots']) > 1 and xb['slots'][1] != NONE else 'no-slot1')
                        rows.append((mid, k, sl[k], sl[k] in base9, f))
            if not rows: continue
            libs_ = sorted({r[2] for r in rows}); fades = collections.Counter(r[4].split(':')[-1] for r in rows)
            print('%s: %d materials, %d libs with empty odd slots used (%d with a base id): %s; Xbox slot-1 forms %s; lum users %s'
                  % (n, len({r[0] for r in rows}), len(libs_), sum(1 for l in libs_ if l in base9), libs_, dict(fades),
                     sorted({'%d/p%d->%d' % (r[0], r[1], r[2]) for r in rows if r[4].endswith('lum') or r[4].endswith('other')})[:12]))
    elif a[0] == 'params':      # params PC.drm XBOX.drm MAT: PS MaterialParams (+0x58 count / +0x5C pointer) on both
        for path, en in ((a[1], '<'), (a[2], '>')):
            D = DW.read(open(path, 'rb').read(), 'le' if en == '<' else 'be')
            s = next(x for x in D.sections if x.type == 10 and x.id == int(a[3]))
            it = dict(R.parse(s.reloc, 'le' if en == '<' else 'be').internal); n = struct.unpack_from(en + 'I', s.data, 0x58)[0]
            print(os.path.basename(path), 'tuple', struct.unpack_from(en + '4I', s.data, 0x28))
            for i in range(n): print('  MP[%d] = %s' % (i, ' '.join('%.4g' % v for v in struct.unpack_from(en + '4f', s.data, it[0x5C] + 16 * i))))
    elif a[0] == 'apply':
        mats = None
        if '--mats' in a: mats = {int(x) for x in a[a.index('--mats') + 1].split(',')}
        cmd_apply(a[1], a[2], a[3], mats)
    elif a[0] == 'verify':      # verify DRM...: PS libs of every material: empty odd slot in the file copy or in the base PC copy
        L = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shaderlibs.pkl'), 'rb'))
        def holes_of(lib): return [k for k in range(1, len(lib['slots']), 2) if lib['slots'][k] == NONE and lib['slots'][k - 1] != NONE]
        for path in a[1:]:
            D = DW.read(open(path, 'rb').read(), 'le'); fl = {s.id: SL.parse(s.data, 'le') for s in D.sections if s.type == 9}
            used = collections.defaultdict(set)
            for mid, sl in POS.mats(D, 'le'):
                for k in (0, 2):
                    if sl[k] is not None: used[sl[k]].add(mid)
            bad_file = sorted(l for l in used if l in fl and fl[l]['kind'] == 1 and holes_of(fl[l]))
            missing = sorted(l for l in used if l not in fl)
            bad_base = sorted(l for l in used if l in L['P'] and L['P'][l]['kind'] == 1 and holes_of(L['P'][l]))
            print('%s: %d PS libs used by %d materials; empty odd slot in the file copy: %s; not in the file: %s; '
                  'id also a base PC lib whose base copy has empty odd slots: %s'
                  % (os.path.basename(path), len(used), len({m for v in used.values() for m in v}), bad_file or 'none',
                     missing or 'none', bad_base or 'none'))
    elif a[0] == 'reid':        # reid IN.drm OUT.drm NEWID,NEWID,... : own ids for the materials whose id is a base PC id
        cmd_reid(a[1], a[2], [int(x) for x in a[3].split(',')])
    else: sys.exit(__doc__)
