r"""Pipeline step "Shaders" (plan A2 stage 1, 2026-11-11, docs Befund-Shader-Schritt-A2-1111.md): re-applies the recorded
shader decisions of docs/data/shader_decisions.tsv (tools/shader_decisions.py, A1) to the pipeline output - from
recorded data only, nothing is translated again.

What a decision becomes (docs/data/shader_step.tsv, one row per decision row, written by `plan`):
  lib   a ShaderLib (type 9) that the decided state has and the pipeline lacks: the RECORDED lib (tu_batch group
        WORKDIR/p/<id>/<id>.lib, 50l / VS / column / look / test-50 lib files - our own translations; md5 = the lib
        bytes) taken from the lib store; "+NF" rows: then the ABS_CONST rewrite of tu_batch nativefix (17r) with a
        STACK-INDEPENDENT entry hash: FST.new_hash over the base-game hashes only (FST.known_hashes, shaderlibs.pkl) and
        the hashes this run gave out - never the hashes found in an install stack (that salted the same code
        differently on another stack, clean17z 14:42). The same rewritten code gets the same hash in every file.
        Added when a material of the output file references the lib, or when the decided file has it unreferenced too
        (refs '-': kept as decided); inserted after the lib the material used before (as tu_unlit apply), else after
        the last ShaderLib.
  mat   a Material (type 10): the decided shader tuple slots (ids at +0x28: PS pass 0 / 1 / 2, VS) and, when a PS slot
        changes, PS MaterialParams := the Xbox material's (tu_unlit apply / grow_params; the Xbox DLC DRM from the
        tu_batch xdump folder). Precondition: the pipeline material's texture records (TLT.records_all: id, type, kind,
        sampler register, per-instance) are the ones the lib was built for (rec_md5); otherwise, when only the pass-2
        PS changes, tu_batch.binding_check of the recorded lib on OUR material must pass (record roles + VM >= 0.999
        against the Xbox shader) - the row is then "applied_differs" (taken, but not word-equal: our records); else
        it is REFUSED (the recorded lib would bind the wrong samplers: needs a tu_batch run on the pipeline material).
  rule  owned by tools/rule_owned.py (ring): the pipeline step runs `rule_owned.py apply` after this tool.
  skip  not re-runnable from recorded data (kit bytes, kit-derived libs, slot fill 48f, files the pipeline does not
        make, one-off builders) - with the reason; counted by `check`.
The lib store (OUR translations, game-derived: never in the repository) is filled by `plan` from the work folders;
a player has no such store yet (later player-path question: knowledge package or own tu_batch run).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_step.py plan [--tsv docs/data/shader_decisions.tsv] [--plan docs/data/shader_step.tsv]
        [--store work/shader_store] [--xbox work/sg_audit_0511/xbox] [--game MODS]
      developer side: per decision row the action + recorded lib (copied into STORE/libs/<md5>.lib) + nativefix flag +
      expected section md5; materials: decided tuple, changed slots, Xbox file / material, records fingerprint.
      Reads the decided (installed) files by their explicit names only (MODS = env TRUDLC_GAME_MODS, else
      ../data/pc/mods); every recorded lib (after the rewrite) must equal the decided section, else the row is skip.
  ../bin/pyt -t 3600 tools/shader_step.py apply --layers L1,L2[,...] --out OUT_MODS [--plan ...] [--store ...]
        [--xbox ...] [--report FILE.json]
      the step: effective file = the last layer that has it; every file with a lib / mat row is written to OUT_MODS
      (sub folder kept, CDRM when the input was); readback: every other section byte-identical, external relocation
      targets unchanged. Exit 1 on an error (store lib missing / wrong md5, rewrite not exact, id clash, ...); refused
      rows (records differ, material missing) are listed, not fatal.
  ../bin/pyt -t 1800 tools/shader_step.py check --layers L1,L2[,...] [--tsv ...] [--plan ...] [--game MODS]
        [--apply-report FILE.json] [--report FILE.json]
      the gate: every decision row's section in the effective tree vs the decided (installed) file, read by explicit
      name, compared as tools/shader_decisions.py scan does (data + normalised relocations): same / differs / missing,
      per class and action. Exit 1 when a lib / mat / rule row is not "same" unless apply refused it or took it as
      "applied_differs" (binding proof on our records; both listed with the reason).
"""
import sys, os, re, json, struct, hashlib, collections, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R

COLS = ['rel', 'type', 'sec_id', 'occ', 'decision_class', 'rerun', 'action', 'src_md5', 'nf', 'out_md5', 'tuple', 'slots',
        'params', 'xbox', 'xmat', 'rec_md5', 'refs', 'src_record', 'note']
GAME_DEFAULT = os.environ.get('TRUDLC_GAME_MODS') or '../data/pc/mods'
ONE_OFF_MATS = {'work/q17q_0811/tree20265/mods': 'one-off builder work/q17q_0811/build20265.py on B138\'s material 20265 (record kind '
                                                  'fix 2 -> 1 / default 121, lane fix, PS0 / PS1 240 / 241 = the kit material\'s) - port to a tool '
                                                  'and decide PS0 / PS1 first (Befund-Shader-Inventur-1111 4.3)'}


def arg(argv, key, default=None):
    if key in argv:
        j = argv.index(key); v = argv[j + 1]; del argv[j:j + 2]; return v
    return default


def md5(b): return hashlib.md5(b).hexdigest()


def is_cdrm(raw): return raw[:4] in (b'CDRM', b'MRDC')


def tup(s): return list(struct.unpack_from('<4I', s.data, 0x28)) if s is not None and s.type == 10 and len(s.data) >= 0x38 else None


def rec_fp(s):
    import tu_light_transplant as TLT
    return md5(repr(TLT.records_all(s, 'le')).encode())


def read_tsv(p):
    L = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')]
    return [dict(zip(L[0], r)) for r in L[1:]]


def sec_of(D, typ, sid, occ=0):
    n = 0
    for i, s in enumerate(D.sections):
        if s.type == typ and s.id == sid:
            if n == occ: return i, s
            n += 1
    return None, None


def xbox_file(xdir, rel):
    b = os.path.basename(rel).lower()
    for pk in ('ack11', 'ack10'):                 # as tu_batch inv: pack11 first
        p = os.path.join(xdir, pk, b)
        if os.path.isfile(p): return '%s/%s' % (pk, b)
    return None


# ------------------------------------------------------------------------------------------------------- nativefix
class NativeFix:
    """tu_batch nativefix (17r) on one lib's bytes with a stack-independent hash: taken = base-game hashes only"""
    def __init__(self):
        import fade_slots_translate as FST
        self.taken = FST.known_hashes(); self.memo = {}

    def lib(self, data):
        import tu_batch as TB, tu_light_transplant as TLT, fade_slots_translate as FST
        from tu_light_transplant import sm3asm
        head, tb, offs, ents = TB._lib_parse(data)
        if TB._lib_build(head, tb, offs, ents) != data: raise ValueError('lib rebuild not byte-identical')
        n = 0
        for o, e in ents.items():
            code = e[3]
            if code[2:4] != b'\xff\xff' or not TLT.abs_const_operands(code): continue
            if code not in self.memo:
                new, k = TLT.fix_abs_native(code)
                same, why = TLT.vm_exact(code, new)
                if not same: raise ValueError('rewrite not bit-exact (%s)' % why)
                prog = sm3asm.decode(new)
                ok, txt, err = FST.valid(new[:4 * prog.nend])
                if not ok: raise ValueError('rewritten shader not valid (%s)' % str(err)[:100])
                self.memo[code] = (new, FST.new_hash(b'17r native|' + new, self.taken), k)
            new, h, k = self.memo[code]
            e[3] = new; e[2] = h; n += 1
        return TB._lib_build(head, tb, offs, ents), n


# ------------------------------------------------------------------------------------------------------------ plan
def src_lib(r):
    """recorded lib file of a lib decision row: tu_batch state.json -> WORKDIR/p/<new>/<new>.lib, else the record path"""
    rec = r['record'].split(' ; ')[0].strip()
    if rec.endswith('state.json'):
        m = re.search(r'-> (\d+) \(', r['decision'])
        if not m: return None
        return '%s/p/%s/%s.lib' % (os.path.dirname(rec), m.group(1), m.group(1))
    return rec if rec.endswith('.lib') else None


def plan(argv):
    tsv = arg(argv, '--tsv', 'docs/data/shader_decisions.tsv')
    outp = arg(argv, '--plan', 'docs/data/shader_step.tsv')
    store = arg(argv, '--store', 'work/shader_store')
    xdir = arg(argv, '--xbox', 'work/sg_audit_0511/xbox')
    game = arg(argv, '--game', GAME_DEFAULT)
    import tu_light_transplant as TLT, tu_shader_night as TN
    rows = read_tsv(tsv)
    os.makedirs(os.path.join(store, 'libs'), exist_ok=True)
    NF = NativeFix()
    cache = {}

    def inst(rel):
        if rel not in cache:
            p = os.path.join(game, rel.replace('/', os.sep))      # explicit name from the decision table, never a listing
            cache[rel] = DW.read(open(p, 'rb').read(), 'le') if os.path.isfile(p) else None
        return cache[rel]
    xcache = {}
    out = []; stat = collections.Counter()
    for r in rows:
        e = {c: '-' for c in COLS}
        for c in ('rel', 'type', 'sec_id', 'occ', 'decision_class', 'rerun'): e[c] = r[c]
        cls, rr = r['decision_class'], r['rerun']
        sid, occ = int(r['sec_id']), int(r['occ'])
        def skip(why): e.update(action='skip', note=why)
        if cls == 'RULE_RING':
            e.update(action='rule', note='tools/rule_owned.py apply (ring), after this tool')
        elif cls == 'L_SLOTFILL':
            skip('not taken over: 48f slot fill of base-id libs, no game effect (48g live)')
        elif cls == 'F_NOT_IN_PIPE':
            skip('file not made by the pipeline (%s)' % r['install_source'])
        elif rr not in ('yes', 'partial'):
            skip('rerun %s: %s' % (rr, r['missing']))
        elif r['type'] == 'shaderlib':
            p = src_lib(r)
            D = inst(r['rel'])
            _, s = sec_of(D, 9, sid, occ) if D else (None, None)
            if not p or not os.path.isfile(p): skip('recorded lib not found (%s)' % p)
            elif s is None: skip('decided file / section not readable')
            else:
                data = open(p, 'rb').read(); nf = '+NF' in cls
                res = NF.lib(data)[0] if nf else data
                if md5(res) != md5(s.data): skip('recorded lib%s != decided section (%s)' % (' + nativefix' if nf else '', p))
                else:
                    q = os.path.join(store, 'libs', md5(data) + '.lib')
                    if not os.path.isfile(q): shutil.copyfile(p, q)
                    if md5(open(q, 'rb').read()) != md5(data): raise SystemExit('store copy check failed: %s' % q)
                    refs = ['%d:%d' % (m.id, k) for m in D.sections if m.type == 10 and tup(m) for k, x in enumerate(tup(m)) if x == sid]
                    e.update(action='lib', src_md5=md5(data), nf='1' if nf else '0', out_md5=md5(s.data), refs=','.join(refs) or '-',
                             src_record=p, note='orphan in the decided file (no material references it)' if not refs else '-')
        elif r['type'] == 'material':
            D = inst(r['rel'])
            _, s = sec_of(D, 10, sid, occ) if D else (None, None)
            if r['install_source'] in ONE_OFF_MATS: skip(ONE_OFF_MATS[r['install_source']])
            elif s is None: skip('decided file / section not readable')
            elif r['pipe_tuple'] == '-': skip('material not in the pipeline output')
            else:
                it = tup(s); pt = [int(x) for x in r['pipe_tuple'].split('/')]
                if '/'.join(map(str, it)) != r['inst_tuple']: skip('decided tuple drifted since the inventory (%s, table %s)' % (it, r['inst_tuple']))
                else:
                    slots = [k for k in range(4) if it[k] != pt[k]]
                    xf = xbox_file(xdir, r['rel']); xm = None
                    if xf:
                        if xf not in xcache: xcache[xf] = TLT.load(os.path.join(xdir, xf), 'be')[1]
                        by = {}
                        for x in D.sections: by.setdefault((x.type, x.id), x)       # as TLT.load: first copy of an id
                        xm = {pm: x for pm, x, _ in TN.mats_of(by, xcache[xf])}.get(sid)
                    ps = any(k < 3 for k in slots)
                    if ps and xm is None: skip('no Xbox material for the MaterialParams (%s)' % xf)
                    else:
                        e.update(action='mat', out_md5=md5(s.data), tuple='/'.join(map(str, it)), slots=','.join(map(str, slots)) or '-',
                                 params='xbox' if ps else 'keep', xbox=xf or '-', xmat=str(xm) if xm is not None else '-', rec_md5=rec_fp(s),
                                 src_record=r['record'], note='-')
        else:
            skip('type %s' % r['type'])
        stat[(r['type'], e['action'])] += 1
        out.append(e)
    with open(outp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(COLS) + '\n')
        for e in out: f.write('\t'.join(str(e[c]).replace('\t', ' ') for c in COLS) + '\n')
    for k, n in sorted(stat.items()): print('%5d  %s %s' % (n, k[0], k[1]))
    print('nativefix: %d distinct rewritten shaders' % len(NF.memo))
    print('wrote %s (%d rows), lib store %s' % (outp, len(out), store))


# ----------------------------------------------------------------------------------------------------------- apply
def ext_targets(D):
    """per section index: [(type, id, occurrence) of every external relocation target] - the readback key"""
    occ = {}; key = []
    cnt = collections.Counter()
    for s in D.sections:
        key.append((s.type, s.id, cnt[(s.type, s.id)])); cnt[(s.type, s.id)] += 1
    out = []
    for s in D.sections:
        try: ex = R.parse(s.reloc, 'le').external
        except Exception: ex = []
        out.append([(key[si] if si < len(key) else ('bad', si), so, do) for si, so, do in ex])
    return out


def bind_proof(D, mat, X, xmat, data):
    """tu_batch.binding_check of the pass-2 lib bytes DATA on material section MAT (already changed, in memory) of DRM D
    against Xbox material XMAT of X -> (ok, text). ok = no static problem and VM >= 0.999 (lit: Xbox-lit reference,
    unlit: Xbox registers with the surrogate's PC CTAB, as vcheck)"""
    import tu_batch as TB
    from tu_light_transplant import F9, libs
    if data is None: return False, 'no recorded pass-2 lib for this file'
    Pd = {}
    for s in D.sections: Pd.setdefault((s.type, s.id), s)
    Pd[(10, mat.id)] = mat
    xl = struct.unpack_from('>4I', X[(10, xmat)].data, 0x28)[2]
    lit = bool(TB.lit_lib(xl)); pct = None
    sur = TB.SMAP.get(xl, {}).get('pc'); L = libs()['P']
    if not lit and sur in L: pct = F9.pc_ctab(L[sur]['entries'][next(o for o in L[sur]['slots'] if o != 0xffffffff)]['blob'])
    try: worst, probs = TB.binding_check(Pd, X, mat.id, xmat, xl, data, lit, pct)
    except Exception as e: return False, 'check error %s: %s' % (type(e).__name__, str(e)[:100])
    ok = not probs and worst is not None and worst >= 0.999
    return ok, '%s VM %s, %d problems%s' % ('lit' if lit else 'unlit', '-' if worst is None else '%.3f' % worst, len(probs),
                                           (' ' + '; '.join(probs[:2])) if probs else '')


def apply(argv):
    layers = (arg(argv, '--layers') or '').split(',')
    outm = arg(argv, '--out'); planp = arg(argv, '--plan', 'docs/data/shader_step.tsv')
    store = arg(argv, '--store', 'work/shader_store'); xdir = arg(argv, '--xbox', 'work/sg_audit_0511/xbox')
    rep = arg(argv, '--report')
    if not outm or not layers[0]: raise SystemExit('apply: --layers and --out are needed')
    for L in layers:
        if not os.path.isdir(L): raise SystemExit('layer not found: %s' % L)
        a, b = os.path.realpath(outm), os.path.realpath(L)
        if a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep): raise SystemExit('OUT must not be a layer or inside one: %s' % outm)
    if os.path.isdir(outm):
        print('replacing previous output %s' % outm); shutil.rmtree(outm)
    import tu_light_transplant as TLT, tu_unlit as TU
    P = read_tsv(planp)
    byfile = collections.OrderedDict()
    for p in P:
        if p['action'] in ('lib', 'mat'): byfile.setdefault(p['rel'], []).append(p)
    NF = NativeFix(); xcache = {}
    status = {}; errors = []; nfiles = 0; nadd = nmat = 0
    def key(p): return '%s|%s|%s' % (p['rel'], p['type'], p['sec_id'])
    for rel, rows in byfile.items():
        src = None
        for L in layers:
            q = os.path.join(L, rel.replace('/', os.sep))
            if os.path.isfile(q): src = q
        if src is None:
            for p in rows: status[key(p)] = dict(state='refused', why='file not in the layers')
            continue
        raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
        before = [(s.type, s.id, s.data, s.reloc) for s in D.sections]; ext0 = ext_targets(D)
        changed = set(); anchors = {}
        # the recorded libs of this file first (bytes after nativefix, checked against the decided md5)
        libdata = {}
        for p in [x for x in rows if x['action'] == 'lib']:
            sid = int(p['sec_id'])
            q = os.path.join(store, 'libs', p['src_md5'] + '.lib')
            if not os.path.isfile(q): errors.append('%s lib %d: store lib %s missing (shader_step.py plan)' % (rel, sid, q)); continue
            data = open(q, 'rb').read()
            if md5(data) != p['src_md5']: errors.append('%s lib %d: store lib md5 differs' % (rel, sid)); continue
            if p['nf'] == '1':
                try: data, n = NF.lib(data)
                except ValueError as ex: errors.append('%s lib %d: nativefix %s' % (rel, sid, ex)); continue
            if md5(data) != p['out_md5']: errors.append('%s lib %d: rebuilt lib md5 %s != decided %s' % (rel, sid, md5(data), p['out_md5'])); continue
            libdata[sid] = data
        # materials (the libs are added for the materials that took their decision)
        for p in [x for x in rows if x['action'] == 'mat']:
            sid = int(p['sec_id']); i, s = sec_of(D, 10, sid, int(p['occ']))
            if s is None: status[key(p)] = dict(state='refused', why='material not in the pipeline file'); continue
            want = [int(x) for x in p['tuple'].split('/')]; cur = tup(s)
            slots = [int(k) for k in p['slots'].split(',')] if p['slots'] != '-' else []
            if md5(s.data) == p['out_md5']: status[key(p)] = dict(state='already'); continue
            fp_ok = rec_fp(s) == p['rec_md5']
            if not fp_ok and slots != [2]:
                status[key(p)] = dict(state='refused', why='texture records differ from the material the libs were built for and '
                                                           'more than the pass-2 PS changes (no binding proof) - needs a tu_batch run')
                continue
            n_ = DW.Section(s.type, s.id, s.data, s.reloc, s.flags, s.ver, s.spec, s.pad)
            d = bytearray(n_.data)
            for k in slots: struct.pack_into('<I', d, 0x28 + 4 * k, want[k])
            n_.data = bytes(d)
            X = None
            if p['params'] == 'xbox' or not fp_ok:
                xf = os.path.join(xdir, p['xbox'])
                if not os.path.isfile(xf): errors.append('%s material %d: Xbox file %s missing (tu_batch.py xdump)' % (rel, sid, xf)); continue
                if xf not in xcache: xcache[xf] = TLT.load(xf, 'be')[1]
                X = xcache[xf]
            if p['params'] == 'xbox':
                xv = TLT.mparams(X[(10, int(p['xmat']))], 'be')
                if xv: TU.grow_params(n_, xv)
            proof = '-'
            if not fp_ok:
                # records differ from the decided (installed) material: the recorded pass-2 lib is taken only when the
                # binding check (tu_batch.binding_check: record roles + VM vs the Xbox shader) passes on OUR material
                ok, proof = bind_proof(D, n_, X, int(p['xmat']), libdata.get(want[2]))
                if not ok:
                    status[key(p)] = dict(state='refused', why='texture records differ from the material the lib was built for and the '
                                                               'binding check fails on the pipeline material (%s) - needs a tu_batch run' % proof)
                    continue
            s.data, s.reloc = n_.data, n_.reloc
            for k in slots: anchors.setdefault(want[k], cur[k])
            changed.add(i); nmat += 1
            same = md5(s.data) == p['out_md5']
            status[key(p)] = dict(state='applied' if same else 'applied_differs',
                                  why='-' if same else ('texture records of the pipeline material differ from the decided one; binding '
                                                         'check on the pipeline material: %s' % proof if not fp_ok else
                                                         'other bytes of the pipeline material differ from the decided one'))
        # libs: only those a material of the output file references
        used = {x for s in D.sections if s.type == 10 and tup(s) for x in tup(s)}
        have = {s.id: s for s in D.sections if s.type == 9}
        new = []
        for p in sorted([x for x in rows if x['action'] == 'lib'], key=lambda x: int(x['sec_id'])):
            sid = int(p['sec_id'])
            if sid not in libdata: continue                 # error listed above
            if sid not in used and p['refs'] != '-':
                # a lib that the decided file has unreferenced too (refs '-') is added as decided (the engine keeps lib
                # ids across DRMs); a lib whose own material did not take its decision here is not
                status[key(p)] = dict(state='refused', why='orphan: no material of the output file references it (its material was refused / not taken over)'); continue
            data = libdata[sid]
            if sid in have:
                if have[sid].data == data: status[key(p)] = dict(state='already'); continue
                errors.append('%s lib %d: id taken by another lib in the pipeline file' % (rel, sid)); continue
            new.append((sid, data, p))
        added = set()                       # id() of the inserted Section objects (Section has __slots__)
        for sid, data, p in new:
            anc = anchors.get(sid)
            idx = next((j for j, s in enumerate(D.sections) if s.type == 9 and s.id == anc and id(s) not in added), None)
            if idx is None:
                t9 = [j for j, s in enumerate(D.sections) if s.type == 9]
                idx = t9[-1] if t9 else next(j for j, s in enumerate(D.sections) if s.type == 10) - 1
            while idx + 1 < len(D.sections) and id(D.sections[idx + 1]) in added: idx += 1     # after libs inserted there before
            ref = D.sections[idx] if idx >= 0 and D.sections[idx].type == 9 else next((s for s in D.sections if s.type == 9), D.sections[0])
            ns = DW.Section(9, sid, data, b'', flags=ref.flags, ver=ref.ver, spec=ref.spec, pad=ref.pad)
            D.sections.insert(idx + 1, ns); added.add(id(ns)); nadd += 1
            status[key(p)] = dict(state='applied', why='-')
        if not changed and not new: continue
        # readback: every old section unchanged except the changed materials, external targets unchanged
        olds = [s for s in D.sections if id(s) not in added]
        for j, (a, s) in enumerate(zip(before, olds)):
            if j in changed: continue
            if a != (s.type, s.id, s.data, s.reloc): errors.append('%s: section %d changed unexpectedly' % (rel, j))
        e1 = [x for s, x in zip(D.sections, ext_targets(D)) if id(s) not in added]
        if e1 != ext0: errors.append('%s: an external relocation target moved with the inserted libs' % rel)
        o = D.write('le')
        if is_cdrm(raw): o = DW.cdrm_encode(o, 'le')
        dst = os.path.join(outm, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(o); nfiles += 1
        B = DW.read(open(dst, 'rb').read(), 'le')
        if [(s.type, s.id, s.data, s.reloc) for s in B.sections] != [(s.type, s.id, s.data, s.reloc) for s in D.sections]:
            errors.append('%s: readback of the written file differs' % dst)
    st = collections.Counter()
    for p in P:
        if p['action'] in ('lib', 'mat'):
            x = status.get(key(p), dict(state='error'))
            st[(p['type'], p['action'], x['state'], x.get('why', '-'))] += 1
    for k, n in sorted(st.items()): print('%5d  %s %s %s  %s' % (n, k[0], k[1], k[2], k[3][:140]))
    for x in errors: print('ERROR ' + x)
    print('nativefix: %d distinct rewritten shaders (stack-independent hashes)' % len(NF.memo))
    print('SUMMARY shader_step apply: %d files written to %s, %d libs added, %d materials changed, %d errors' % (nfiles, outm, nadd, nmat, len(errors)))
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(dict(layers=layers, out=outm, plan=planp, store=store, xbox=xdir, files=nfiles, libs_added=nadd, materials=nmat,
                       errors=errors, status=status), open(rep, 'w', encoding='utf-8'), indent=1)
    return 1 if errors else 0


# ----------------------------------------------------------------------------------------------------------- check
def check(argv):
    layers = (arg(argv, '--layers') or '').split(',')
    tsv = arg(argv, '--tsv', 'docs/data/shader_decisions.tsv'); planp = arg(argv, '--plan', 'docs/data/shader_step.tsv')
    game = arg(argv, '--game', GAME_DEFAULT); arep = arg(argv, '--apply-report'); rep = arg(argv, '--report')
    import shader_decisions as SD
    rows = read_tsv(tsv); P = {(p['rel'], p['type'], p['sec_id'], p['occ']): p for p in read_tsv(planp)}
    ast = json.load(open(arep, encoding='utf-8'))['status'] if arep else {}
    TN = {'shaderlib': 9, 'material': 10}
    res = []; cnt = collections.Counter(); bad = []
    for r in rows:
        p = P.get((r['rel'], r['type'], r['sec_id'], r['occ'])) or {'action': '?', 'note': 'not in the plan'}
        eff = None
        for L in layers:
            q = os.path.join(L, r['rel'].replace('/', os.sep))
            if os.path.isfile(q): eff = q
        gp = os.path.join(game, r['rel'].replace('/', os.sep))          # explicit name from the decision table
        sk = (TN[r['type']], int(r['sec_id']), int(r['occ']))
        so = SD.shsecs(eff) if eff else None; sg = SD.shsecs(gp) if os.path.isfile(gp) else None
        a = (so or {}).get(sk) if isinstance(so, dict) else None
        b = (sg or {}).get(sk) if isinstance(sg, dict) else None
        if b is None: state = 'missing_decided'
        elif a is None: state = 'missing_out'
        else: state = 'same' if a['h'] == b['h'] else 'differs'
        drift = b is not None and b['d'] != r['inst_md5']
        k = '%s|%s|%s' % (r['rel'], r['type'], r['sec_id'])
        ap = ast.get(k, {}).get('state', '-')
        cnt[(r['rerun'], p['action'], r['decision_class'], state)] += 1
        row = dict(rel=r['rel'], type=r['type'], id=int(r['sec_id']), cls=r['decision_class'], rerun=r['rerun'], action=p['action'],
                   apply=ap, why=ast.get(k, {}).get('why', p.get('note', '-')), state=state, drift=drift)
        res.append(row)
        if p['action'] in ('lib', 'mat', 'rule') and state != 'same' and ap not in ('refused', 'applied_differs'):
            bad.append(row)
    print('| rerun | action | class | state | sections |')
    print('|---|---|---|---|---|')
    for (rr, ac, cl, stt), n in sorted(cnt.items()): print('| %s | %s | %s | %s | %d |' % (rr, ac, cl, stt, n))
    agg = collections.Counter((x['action'], x['state']) for x in res)
    print('per action: ' + ', '.join('%s %s %d' % (a, s, n) for (a, s), n in sorted(agg.items())))
    print('installed section drifted since the inventory: %d' % sum(1 for x in res if x['drift']))
    for x in res:
        if x['action'] in ('lib', 'mat') and x['state'] != 'same':
            print('apply %-15s %-8s %s %s %d (%s): %s' % (x['apply'], x['state'], x['rel'], x['type'], x['id'], x['cls'], x['why'][:150]))
    for x in bad[:40]: print('NOT SAME %s %s %d (%s, apply %s): %s' % (x['rel'], x['type'], x['id'], x['cls'], x['apply'], x['state']))
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(dict(layers=layers, game=game, rows=res, not_same=len(bad)), open(rep, 'w', encoding='utf-8'), indent=1)
    print('shader step gate: %s (%d lib / mat / rule sections not equal to the decided state)' % ('PASS' if not bad else 'FAIL', len(bad)))
    return 1 if bad else 0


def main(argv):
    if not argv or argv[0] not in ('plan', 'apply', 'check'): raise SystemExit(__doc__)
    r = {'plan': plan, 'apply': apply, 'check': check}[argv[0]](list(argv[1:]))
    return r or 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
