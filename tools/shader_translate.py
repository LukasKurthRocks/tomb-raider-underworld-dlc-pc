r"""Pipeline step "Shaders", part 2 (plan A2 stage 2, 2026-11-11, workspace docs Befund-Shader-Stufe2-1111.md): OUR
pass-2 pixel-shader translation for the materials the recorded decisions cannot serve - built on the PIPELINE material
(our records), never on a kit material.

Scope = the material rows of docs/data/shader_step.tsv that `shader_step.py apply` does not take:
  * action skip with a kit class (K_MAT_*: the installed state is B138 / B270 bytes) or the q17q one-off class
    M_LIB_SAME_TU_VS (20265: was built by work/q17q_0811/build20265.py on B138's material);
  * rows the apply report (--apply-report) lists as "refused" (recorded lib binds wrong on our records).
Per material copy (effective file = last layer that has it, Xbox twin from the tu_batch xdump folder): the Xbox pass-2
lib must be untranslated (shader map class C1 / C2 / C3 / D) and the PC pass-2 lib a surrogate (base PC lib), else the
copy is listed with the reason. Copies are grouped as tools/tu_batch.py run does: (Xbox lib, sampler map, DXN registers,
unpaired) on OUR records (tu_batch.recs_full). Per group, in this order:
  reuse  a RECORDED lib of the lib store (shader_step plan rows, map.json beside the record = same Xbox lib) whose
         tu_batch.binding_check passes on every copy of the group (record roles + VM >= 0.999 against the Xbox shader);
         lib id = the recorded id, bytes = the store bytes after the nativefix rewrite (shader_step.NativeFix) -
         e.g. 20265: the 26584 lib 3533 (Xbox 2065, same record signature as our 20265) instead of the kit-based 3534;
  build  tu_batch.build_group (lit: per-light transplant + Xbox-lit reference, unlit: direct translation; >= 0.999),
         pack_lib (abs-const rewrites, entry hashes over the base-game hashes only = stack-independent), new lib id from
         --ids-from upwards (never an id of the base game, the layers or the lib store), then binding_check on every
         copy as above.
VS rule: every interpolator the new PS reads must be written by the material's PC VS; otherwise a RECORDED VS lib of
the store for the same Xbox VS (map.json) that writes them all is put on pass 3 (e.g. 3091 for Xbox 2066), else the
group is refused ("needs a VS translation").
Lane rule (ENGINE 17.4, 17c): MaterialParams := the Xbox material's (tu_unlit apply); a c100+ lane that the pass-0 / 1
PS of the material read and the new PS does not read keeps its old value; a lane both read with different values
refuses the group.
Output: only the changed DRMs -> OUT_MODS (a layer over the input layers; sub folder kept, CDRM when the input was);
readback: every other section byte-identical, external relocation targets unchanged; a lib id is never used with two
different byte strings anywhere in the layers + output.
--record FILE writes the decisions (group, copies, action, lib id + md5, VS); --expect FILE (pipeline) compares the run
with them and exits 1 on any difference (determinism / input drift gate).

Usage (from the repository root):
  ../bin/pyt -t 7200 tools/shader_translate.py run --layers L1,L2[,...] --out OUT_MODS [--plan docs/data/shader_step.tsv]
        [--apply-report <shaders>/shader_step_apply.json] [--store work/shader_store] [--xbox work/sg_audit_0511/xbox]
        [--work WORKDIR] [--ids-from 3600] [--only XLIB,XLIB] [--record FILE.tsv | --expect FILE.tsv] [--report FILE.json]
Developer data (not in the repository, not on the player path yet): the lib store, the Xbox xdump folder, the base
shader tables work/render/shaderlibs.pkl / shader map.
"""
import sys, os, json, struct, hashlib, collections, shutil, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW

REC_COLS = ['group', 'xlib', 'lit', 'smap', 'dxn', 'copies', 'action', 'lib', 'md5', 'vs', 'vs_md5', 'lanes_kept', 'note']
SCOPE_CLASSES = ('M_LIB_SAME_TU_VS',)
PER_LANE = {'mov', 'add', 'mul', 'mad', 'max', 'min', 'slt', 'sge', 'frc', 'abs', 'cmp', 'lrp', 'dsx', 'dsy', 'mova',
            'exp', 'log', 'rcp', 'rsq', 'pow', 'sincos', 'texkill'}
SCALAR = {'exp', 'log', 'rcp', 'rsq', 'pow'}


def arg(argv, key, default=None):
    if key in argv:
        j = argv.index(key); v = argv[j + 1]; del argv[j:j + 2]; return v
    return default


def md5(b): return hashlib.md5(b).hexdigest()


def read_tsv(p):
    L = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')]
    return [dict(zip(L[0], r)) for r in L[1:]]


# --------------------------------------------------------------------------------------------------- param lanes
def op_lanes(i, o):
    """lanes (0..3) of source operand o that instruction i reads (work/shader17c_0811/param_lanes.py, 17c)"""
    sw = [(o.swz >> (2 * k)) & 3 for k in range(4)]
    if i.op == 'texkill': return set(sw)
    if i.op in SCALAR: return {sw[0]}
    if i.op in PER_LANE and i.ops and i.ops[0].isdst:
        return {sw[k] for k in range(4) if i.ops[0].wm & (1 << k)}
    return set(sw)


def lib_lanes(lib):
    """{(register, lane)} of c100..c131 a parsed PC lib reads over its occupied slots; ('rel', reg) for relative reads"""
    from tu_light_transplant import F9, sm3asm
    out = set()
    for o in sorted(set(x for x in lib['slots'] if x != 0xffffffff)):
        for i in F9.decode_pc(lib['entries'][o]['blob']).instrs():
            if i.op in ('def', 'defi', 'defb', 'dcl'): continue
            for op in (i.ops[1:] if i.ops and i.ops[0].isdst else i.ops):
                if op.rtype == sm3asm.RT_CONST and 100 <= op.num < 132:
                    if op.rel: out.add(('rel', op.num))
                    else: out |= {(op.num, k) for k in op_lanes(i, op)}
    return out


# --------------------------------------------------------------------------------------------------------- helpers
def lib_of(P, lid):
    """parsed PC lib: the file's ShaderLib section, else the base PC lib; None if neither"""
    import shaderlib as SL
    from tu_light_transplant import libs
    if lid == 0: return None
    if (9, lid) in P: return SL.parse(P[(9, lid)].data, 'le')
    return libs()['P'].get(lid)


def ps_needs(data):
    import shaderlib as SL, tu_batch as TB
    from tu_light_transplant import F9
    L = SL.parse(data, 'le'); need = set()
    for o in set(x for x in L['slots'] if x != 0xffffffff):
        need |= TB.ps_inputs(F9.decode_pc(L['entries'][o]['blob']))
    return {s for s in need if s[0] in (5, 10)}


def vs_writes(data):
    import shaderlib as SL
    from tu_light_transplant import F9, sm3asm
    VL = SL.parse(data, 'le'); outs = set()
    for o in set(x for x in VL['slots'] if x != 0xffffffff):
        outs |= {((i.usage & 31), (i.usage >> 16) & 15) for i in F9.decode_pc(VL['entries'][o]['blob']).instrs()
                 if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT}
    return outs


def pct_of(xl, lit):
    import tu_batch as TB
    from tu_light_transplant import F9, libs
    if lit: return None
    sur = TB.SMAP.get(xl, {}).get('pc'); L = libs()['P']
    if sur not in L: return None
    return F9.pc_ctab(L[sur]['entries'][next(o for o in L[sur]['slots'] if o != 0xffffffff)]['blob'])


def params_off(s):
    import drm_reloc as R
    return dict(R.parse(s.reloc, 'le').internal).get(0x5C), struct.unpack_from('<I', s.data, 0x58)[0]


def new_material(s, X, xm, pass2, vs, keep_lanes):
    """copy of material section s with pass-2 PS / VS ids set, MaterialParams := Xbox (tu_unlit.grow_params) and the
    kept lanes back at their old values -> (section, [(reg, lane, old, xbox)])"""
    import tu_light_transplant as TLT, tu_unlit as TU
    n_ = DW.Section(s.type, s.id, s.data, s.reloc, s.flags, s.ver, s.spec, s.pad)
    old = TLT.mparams(s, 'le')
    d = bytearray(n_.data)
    struct.pack_into('<I', d, 0x30, pass2)
    if vs is not None: struct.pack_into('<I', d, 0x34, vs)
    n_.data = bytes(d)
    xv = TLT.mparams(X[(10, xm)], 'be')
    if xv: TU.grow_params(n_, xv)
    kept = []
    if keep_lanes:
        po, n = params_off(n_)
        d = bytearray(n_.data)
        for reg, k in sorted(keep_lanes):
            j = reg - 100
            if j >= len(old) or j >= n: continue
            was = struct.unpack_from('<f', d, po + 16 * j + 4 * k)[0]
            if was != old[j][k]:
                struct.pack_into('<f', d, po + 16 * j + 4 * k, old[j][k]); kept.append((reg, k, old[j][k], was))
        n_.data = bytes(d)
    return n_, kept


def ext_targets(D):
    import shader_step as SS
    return SS.ext_targets(D)


# ------------------------------------------------------------------------------------------------------------- run
def scope_rows(planp, arep):
    """[(rel, mat, occ, class, why)] - the plan's material rows the recorded step does not take"""
    P = read_tsv(planp)
    st = json.load(open(arep, encoding='utf-8'))['status'] if arep and os.path.isfile(arep) else {}
    out = []
    for p in P:
        if p['type'] != 'material': continue
        k = '%s|%s|%s' % (p['rel'], p['type'], p['sec_id'])
        if p['action'] == 'skip' and (p['decision_class'].startswith('K_MAT') or p['decision_class'] in SCOPE_CLASSES):
            out.append((p['rel'], int(p['sec_id']), int(p['occ']), p['decision_class'], 'kit / one-off: ' + p['note'][:80]))
        elif p['action'] == 'mat' and st.get(k, {}).get('state') == 'refused':
            out.append((p['rel'], int(p['sec_id']), int(p['occ']), p['decision_class'], 'refused by shader_step apply'))
    return out


def recorded_libs(planp, store, want_ps, want_vs):
    """recorded libs of the store with their Xbox lib (map.json beside the record) among WANT_PS (Xbox pass-2 libs) /
    WANT_VS (Xbox VS): [(xlib, id, data, src, kind)] - kind 'ps' for pass-2 rows (L_TU*, L_50L*, L_COLUMN, ...), 'vs'
    for L_VS rows; data after the nativefix rewrite (+NF rows), checked against the plan's out md5"""
    import shader_step as SS
    NF = None; out = {}; seen = set()
    for p in read_tsv(planp):
        if p['type'] != 'shaderlib' or p['action'] != 'lib': continue
        key = (p['sec_id'], p['src_md5'], p['nf'])
        if key in seen: continue
        seen.add(key)
        mp = os.path.join(os.path.dirname(p['src_record']), 'map.json')
        if not os.path.isfile(mp): continue
        kind = 'vs' if p['decision_class'].startswith('L_VS') else 'ps'
        xks = [int(xk) for xk, v in json.load(open(mp)).items() if int(v.get('new', -1)) == int(p['sec_id'])]
        xks = [x for x in xks if x in (want_vs if kind == 'vs' else want_ps)]
        if not xks: continue
        q = os.path.join(store, 'libs', p['src_md5'] + '.lib')
        if not os.path.isfile(q): continue
        data = open(q, 'rb').read()
        if md5(data) != p['src_md5']: continue
        if p['nf'] == '1':
            NF = NF or SS.NativeFix(); data = NF.lib(data)[0]
        if md5(data) != p['out_md5']: continue
        for xk in xks:
            out[(kind, xk, int(p['sec_id']), md5(data))] = (xk, int(p['sec_id']), data, p['src_record'], kind)
    return sorted(out.values(), key=lambda t: (t[4], t[0], t[1]))


def run(argv):
    import tu_batch as TB, tu_light_transplant as TLT, tu_shader_night as TN, fade_slots_translate as FST
    from tu_light_transplant import libs
    layers = (arg(argv, '--layers') or '').split(',')
    outm = arg(argv, '--out'); planp = arg(argv, '--plan', 'docs/data/shader_step.tsv')
    arep = arg(argv, '--apply-report'); store = arg(argv, '--store', 'work/shader_store')
    xdir = arg(argv, '--xbox', 'work/sg_audit_0511/xbox'); wd = arg(argv, '--work')
    ids_from = int(arg(argv, '--ids-from', '3600')); only = arg(argv, '--only')
    recp = arg(argv, '--record'); expp = arg(argv, '--expect'); rep = arg(argv, '--report')
    only = {int(x) for x in only.split(',')} if only else None
    if not outm or not layers[0]: raise SystemExit('run: --layers and --out are needed')
    for L in layers:
        if not os.path.isdir(L): raise SystemExit('layer not found: %s' % L)
        a, b = os.path.realpath(outm), os.path.realpath(L)
        if a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep): raise SystemExit('OUT must not be a layer or inside one: %s' % outm)
    if os.path.isdir(outm):
        print('replacing previous output %s' % outm); shutil.rmtree(outm)
    wd = wd or os.path.join(os.path.dirname(os.path.abspath(outm)), 'translate_work')
    os.makedirs(wd, exist_ok=True)
    t0 = time.time()
    # effective files of every layer DRM (ids in use: id -> md5 set)
    eff = {}
    for L in layers:
        for dp, dn, fn in os.walk(L):
            dn[:] = [d for d in dn if 'truguard' not in d.lower()]
            for f in fn:
                if f.lower().endswith('.drm') and 'truguard' not in f.lower():
                    rel = os.path.relpath(os.path.join(dp, f), L).replace('\\', '/')
                    eff[rel.lower()] = (rel, os.path.join(dp, f))
    idmd5 = collections.defaultdict(set)
    for k, (rel, p) in sorted(eff.items()):
        try:
            for s in DW.read(open(p, 'rb').read(), 'le').sections:
                if s.type == 9: idmd5[s.id].add(md5(s.data))
        except Exception as ex:
            print('not readable (ids not scanned): %s %s' % (rel, ex))
    print('layers: %d DRMs, %d ShaderLib ids in use (%.0f s)' % (len(eff), len(idmd5), time.time() - t0))
    for p in read_tsv(planp):                         # every recorded lib id of the plan (store) is taken too
        if p['type'] == 'shaderlib' and p['action'] == 'lib': idmd5[int(p['sec_id'])].add(p['out_md5'])
    used_ids = set(idmd5) | set(libs()['P']) | set(libs()['X']) | set(libs()['D'])
    cache = {}
    def load(p, e):
        if p not in cache:
            if len(cache) > 12: cache.clear()
            cache[p] = TLT.load(p, e)[1]
        return cache[p]
    def xfile(rel):
        b = os.path.basename(rel).lower()
        for pk in ('ack11', 'ack10'):
            q = os.path.join(xdir, pk, b)
            if os.path.isfile(q): return q
        return None
    # ---- copies
    copies = []; listed = []
    for rel, mat, occ, cls, why in scope_rows(planp, arep):
        e = dict(rel=rel, mat=mat, cls=cls, scope=why)
        f = eff.get(rel.lower()); xf = xfile(rel)
        if f is None: listed.append(dict(e, why='file not in the layers')); continue
        if xf is None: listed.append(dict(e, why='no Xbox twin in %s' % xdir)); continue
        P = load(f[1], 'le'); X = load(xf, 'be')
        if (10, mat) not in P: listed.append(dict(e, why='material not in the effective file')); continue
        xm = {pm: x for pm, x, _ in TN.mats_of(P, X)}.get(mat)
        if xm is None or (10, xm) not in X: listed.append(dict(e, why='no Xbox material')); continue
        pt = struct.unpack_from('<4I', P[(10, mat)].data, 0x28); xt = struct.unpack_from('>4I', X[(10, xm)].data, 0x28)
        cl = TB.SMAP.get(xt[2], {}).get('cls', 'base')
        e.update(path=f[1], xbox=xf, xmat=xm, pt=pt, xt=xt, xcls=cl)
        if only is not None and xt[2] not in only: continue
        if cl not in TB.UNTR:
            listed.append(dict(e, why='Xbox pass-2 lib %d class %s (byte-identical base twin): no translation; the kit differs only in '
                                      'MaterialParams / other bytes' % (xt[2], cl))); continue
        if not TB.is_surrogate_lib(pt[2]):
            listed.append(dict(e, why='PC pass-2 lib %d is not a surrogate (already a translation in the layers)' % pt[2])); continue
        r = TB.recs_full(P, X, mat, xm)
        if r is None: listed.append(dict(e, why='records do not pair (tu_batch.recs_full)')); continue
        e.update(smap=tuple(sorted(r['smap'].items())), dxn=tuple(sorted(r['dxn'])), unpaired=tuple(sorted(r['unpaired'])))
        copies.append(e)
    groups = collections.OrderedDict()
    for e in sorted(copies, key=lambda e: (e['xt'][2], e['smap'], e['dxn'], e['unpaired'], e['mat'], e['rel'])):
        groups.setdefault((e['xt'][2], e['smap'], e['dxn'], e['unpaired']), []).append(e)
    print('scope: %d copies in %d groups, %d listed without translation (%.0f s)' % (len(copies), len(groups), len(listed), time.time() - t0))
    REC = recorded_libs(planp, store, {k[0] for k in groups}, {c['xt'][3] for c in copies})
    print('recorded libs for these Xbox libs (map.json): %d PS / %d VS (%.0f s)' % (
        sum(1 for r in REC if r[4] == 'ps'), sum(1 for r in REC if r[4] == 'vs'), time.time() - t0))
    # ---- per group: reuse / build, VS rule, lane rule, binding proof on every copy
    taken = FST.known_hashes(); nid = ids_from
    plans = []                       # (group entry, {copy index: (new section, kept)}, ps (id, data), vs (id, data) or None)
    gres = []
    for gi, (key, cs) in enumerate(groups.items()):
        xl, smap, dxn, unp = key
        lit = bool(TB.lit_lib(xl)); pct = pct_of(xl, lit)
        g = dict(group=gi, xlib=xl, lit=lit, smap=dict(smap), dxn=list(dxn), copies=['%s:%d' % (c['rel'], c['mat']) for c in cs],
                 action='refused', lib='-', md5='-', vs='-', vs_md5='-', lanes_kept='-', note='-')
        tg = time.time(); lg = []
        def prove(data):
            """-> (per copy (new section, kept, vs) or None, reason) - VS rule, lane rule, binding check on every copy"""
            need = ps_needs(data); newl = lib_lanes(__import__('shaderlib').parse(data, 'le')); res = {}
            for ci, c in enumerate(cs):
                P = load(c['path'], 'le'); X = load(c['xbox'], 'be')
                pv = c['pt'][3]; outs = TB.vs_outputs_any(P, pv); vs = None
                if outs is None or not need <= outs:
                    cand = [r_ for r_ in REC if r_[4] == 'vs' and r_[0] == c['xt'][3] and need <= vs_writes(r_[2])]
                    if not cand:
                        return None, 'PS reads %s, PC VS %d of %s:%d does not write them and no recorded VS for Xbox VS %d does - needs a VS translation' % (
                            sorted(need - (outs or set())), pv, c['rel'], c['mat'], c['xt'][3])
                    vs = (cand[0][1], cand[0][2])
                old01 = set()
                for k in (0, 1):
                    lb = lib_of(P, c['pt'][k])
                    if lb is not None: old01 |= lib_lanes(lb)
                if any(t[0] == 'rel' for t in old01) or any(t[0] == 'rel' for t in newl):
                    return None, 'relative c100+ read in pass 0 / 1 or the new PS (%s:%d) - lane rule not decidable' % (c['rel'], c['mat'])
                keep = old01 - newl
                both = old01 & newl
                old = TLT.mparams(P[(10, c['mat'])], 'le'); xv = TLT.mparams(X[(10, c['xmat'])], 'be')
                clash = [(r_, k) for r_, k in sorted(both) if r_ - 100 < len(old) and r_ - 100 < len(xv) and old[r_ - 100][k] != xv[r_ - 100][k]]
                if clash:
                    return None, 'lane clash: pass 0 / 1 and the new PS both read %s with different values (PC %s / Xbox %s) on %s:%d' % (
                        ['c%d.%s' % (r_, 'xyzw'[k]) for r_, k in clash[:3]], [old[r_ - 100][k] for r_, k in clash[:3]],
                        [xv[r_ - 100][k] for r_, k in clash[:3]], c['rel'], c['mat'])
                ns, kept = new_material(P[(10, c['mat'])], X, c['xmat'], 0, vs[0] if vs else None, keep)
                Pd = dict(P); Pd[(10, c['mat'])] = ns
                try: worst, probs = TB.binding_check(Pd, X, c['mat'], c['xmat'], xl, data, lit, pct)
                except Exception as ex: return None, 'binding check error on %s:%d: %s %s' % (c['rel'], c['mat'], type(ex).__name__, str(ex)[:100])
                if probs or worst is None or worst < 0.999:
                    return None, 'binding check on %s:%d: VM %s, %d problems %s' % (c['rel'], c['mat'], '-' if worst is None else '%.3f' % worst,
                                                                                len(probs), '; '.join(probs[:2]))
                res[ci] = (kept, vs, worst)
            return res, 'ok'
        chosen = None; why = []
        # 1 reuse a recorded lib for the same Xbox lib
        for xk, lid, data, src, kind in REC:
            if kind != 'ps' or xk != xl: continue
            res, w = prove(data)
            if res is None: why.append('recorded %d (%s): %s' % (lid, src, w)); continue
            chosen = ('reuse', lid, data, res, src); break
        # 2 our translation on our records
        if chosen is None:
            c0 = cs[0]; X0 = load(c0['xbox'], 'be')
            XP = TLT.mparams(X0[(10, c0['xmat'])], 'be'); pd = TB.SMAP.get(xl, {}).get('pc')
            try:
                built = TB.build_group(xl, pd, dict(smap), set(dxn), XP, lit, os.path.join(wd, 'b', '%d_%d' % (xl, c0['mat'])), lg, list(unp))
                while nid in used_ids: nid += 1
                data = TB.pack_lib(built, nid, taken, len(built))
                res, w = prove(data)
                if res is None: why.append('build: %s' % w)
                else:
                    chosen = ('build', nid, data, res, 'tu_batch.build_group donor %s' % pd); used_ids.add(nid); nid += 1
            except Exception as ex:
                why.append('build refused: %s %s' % (type(ex).__name__, str(ex)[:160]))
        if chosen is None:
            g['note'] = ' | '.join(why)[:600] or 'no candidate'
        else:
            act, lid, data, res, src = chosen
            if idmd5.get(lid) and md5(data) not in idmd5[lid] and act == 'build':
                raise SystemExit('lib id %d already used with other bytes' % lid)
            idmd5[lid].add(md5(data))
            vss = {r_[1] for r_ in res.values() if r_[1]}
            g.update(action=act, lib=lid, md5=md5(data), note='%s; worst VM %.3f over %d copies; %.0f s' % (
                src, min(r_[2] for r_ in res.values()), len(res), time.time() - tg))
            if vss:
                g['vs'] = ','.join(str(v[0]) for v in sorted(vss)); g['vs_md5'] = ','.join(md5(v[1]) for v in sorted(vss))
            kl = sorted({'%s:%d c%d.%s %g->%g' % (cs[ci]['rel'].split('/')[-1], cs[ci]['mat'], r_, 'xyzw'[k], o_, x_)
                         for ci, (kept, _, _) in res.items() for r_, k, o_, x_ in kept})
            g['lanes_kept'] = '; '.join(kl[:6]) + (' (+%d)' % (len(kl) - 6) if len(kl) > 6 else '') if kl else '-'
            plans.append((cs, res, (lid, data)))
        g['log'] = lg
        gres.append(g)
        print('group %2d xlib %4d %-5s %2d copies -> %-7s %s %s' % (gi, xl, 'lit' if lit else 'unlit', len(cs), g['action'], g['lib'], g['note'][:200]), flush=True)
    # ---- apply per file
    byfile = collections.OrderedDict()
    for cs, res, ps in plans:
        for ci, (kept, vs, worst) in res.items():
            c = cs[ci]; byfile.setdefault(c['rel'], []).append((c, kept, vs, ps))
    errors = []; nfiles = 0
    for rel, items in byfile.items():
        src = eff[rel.lower()][1]; raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
        X = load(items[0][0]['xbox'], 'be')
        before = [(s.type, s.id, s.data, s.reloc) for s in D.sections]; ext0 = ext_targets(D)
        have = {s.id: s for s in D.sections if s.type == 9}
        changed = set(); added = set(); ins = []
        for c, kept, vs, (lid, data) in items:
            i, s = next((j, x) for j, x in enumerate(D.sections) if x.type == 10 and x.id == c['mat'])
            ns, kept2 = new_material(s, X, c['xmat'], lid, vs[0] if vs else None, {(r_, k) for r_, k, _, _ in kept})
            s.data, s.reloc = ns.data, ns.reloc; changed.add(i)
            for nid_, nd, anchor in ((lid, data, c['pt'][2]),) + (((vs[0], vs[1], c['pt'][3]),) if vs else ()):
                if nid_ in have:
                    if have[nid_].data != nd: errors.append('%s: lib %d in the file with other bytes' % (rel, nid_))
                    continue
                if any(x[0] == nid_ for x in ins): continue
                ins.append((nid_, nd, anchor))
        for nid_, nd, anchor in ins:
            idx = next((j for j, s in enumerate(D.sections) if s.type == 9 and s.id == anchor and id(s) not in added), None)
            if idx is None:
                t9 = [j for j, s in enumerate(D.sections) if s.type == 9]
                idx = t9[-1] if t9 else next(j for j, s in enumerate(D.sections) if s.type == 10) - 1
            while idx + 1 < len(D.sections) and id(D.sections[idx + 1]) in added: idx += 1
            ref = D.sections[idx] if idx >= 0 and D.sections[idx].type == 9 else next((s for s in D.sections if s.type == 9), D.sections[0])
            n_ = DW.Section(9, nid_, nd, b'', flags=ref.flags, ver=ref.ver, spec=ref.spec, pad=ref.pad)
            D.sections.insert(idx + 1, n_); added.add(id(n_))
        olds = [s for s in D.sections if id(s) not in added]
        for j, (a, s) in enumerate(zip(before, olds)):
            if j not in changed and a != (s.type, s.id, s.data, s.reloc): errors.append('%s: section %d changed unexpectedly' % (rel, j))
        if [x for s, x in zip(D.sections, ext_targets(D)) if id(s) not in added] != ext0:
            errors.append('%s: an external relocation target moved with the inserted libs' % rel)
        o = D.write('le')
        if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
        dst = os.path.join(outm, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(o); nfiles += 1
        B = DW.read(open(dst, 'rb').read(), 'le')
        if [(s.type, s.id, s.data, s.reloc) for s in B.sections] != [(s.type, s.id, s.data, s.reloc) for s in D.sections]:
            errors.append('%s: readback of the written file differs' % dst)
    # ---- record / expect
    rows = []
    for g in gres:
        rows.append({c: (json.dumps(g[c], sort_keys=True) if c in ('smap', 'dxn', 'copies') else str(g[c])) for c in REC_COLS})
    if recp:
        with open(recp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(REC_COLS) + '\n')
            for r_ in rows: f.write('\t'.join(r_[c].replace('\t', ' ') if c != 'note' else r_[c].split(';')[0].replace('\t', ' ')[:300] for c in REC_COLS) + '\n')
        print('recorded %d groups -> %s' % (len(rows), recp))
    if expp:
        E = {(r_['xlib'], r_['smap'], r_['dxn'], r_['copies']): r_ for r_ in read_tsv(expp)}
        for r_ in rows:
            e_ = E.pop((r_['xlib'], r_['smap'], r_['dxn'], r_['copies']), None)
            if e_ is None: errors.append('expect: group xlib %s %s not recorded' % (r_['xlib'], r_['copies'][:80])); continue
            for c in ('action', 'lib', 'md5', 'vs', 'vs_md5', 'lanes_kept'):
                if e_[c] != r_[c]: errors.append('expect: group xlib %s %s: %s %s != recorded %s' % (r_['xlib'], r_['copies'][:60], c, r_[c], e_[c]))
        for k in E: errors.append('expect: recorded group xlib %s %s not in this run' % (k[0], k[3][:80]))
    cnt = collections.Counter(g['action'] for g in gres)
    ncop = collections.Counter()
    for g in gres: ncop[g['action']] += len(g['copies'])
    for x in errors: print('ERROR ' + x)
    for x in listed: print('listed %s:%d (%s): %s' % (x['rel'], x['mat'], x['cls'], x['why'][:160]))
    print('SUMMARY shader_translate: %d groups (%s), copies %s, %d listed without translation, %d files written to %s, %d errors, %.0f s' % (
        len(gres), dict(cnt), dict(ncop), len(listed), nfiles, outm, len(errors), time.time() - t0))
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(dict(layers=layers, out=outm, plan=planp, groups=gres, listed=[{k: v for k, v in x.items() if k in ('rel', 'mat', 'cls', 'scope', 'why')} for x in listed],
                       files=nfiles, errors=errors), open(rep, 'w', encoding='utf-8'), indent=1, default=str)
    return 1 if errors else 0


def main(argv):
    if not argv or argv[0] not in ('run',): raise SystemExit(__doc__)
    return {'run': run}[argv[0]](list(argv[1:])) or 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
