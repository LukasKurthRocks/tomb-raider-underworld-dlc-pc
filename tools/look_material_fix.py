"""Shadow-power look (Look finding 2026-11-03): the full-screen material of the doppelganger's look effect.

The TU start event 0x32 of doppelganger_casual (object 857, event list DTP 20172) fires kind 1 sub 0xb {0xe} = record 14
of the model record list (DTP 20134). PC tru+0x135cc0 turns it into an instance effect of type 0x85; tru+0x1469a0 draws
it every frame: record word 7 (effect +0x4c) != 0 -> tru+0x146340 -> tru+0x13ef30(colour 0x80576b79 x fade, material
word 7, flags) = a full-screen quad drawn with MATERIAL 20744 (type 10) through the renderer [0xa1407c]->vtbl[0x58].
On the PC that material has a converter surrogate pixel shader (shader_map: no PC twin of TU lib 2327) and no PS
MaterialParams, so the screen shows the surrogate's output (black centre, white edges) instead of the Xbox look.

Modes (from the repository root; read-only unless an output path is given):
  ../bin/pyt -t 600 tools/look_material_fix.py show XBOX.drm PC.drm MID [--asm]
      material tuple, texture records and MaterialParams on both platforms, CTAB of every Xbox / PC lib of the tuple,
      slot occupancy, and (--asm) the direct Xenos -> ps_3_0 translation of the Xbox pass-2 PS slots
  ../bin/pyt -t 600 tools/look_material_fix.py xtext XBOX.drm LIB [SLOT,SLOT]   Xenos text, vertex fetch, interpolators
  ../bin/pyt -t 900 tools/look_material_fix.py pcvs [NAME,NAME]                 base PC VS libs that pass a colour
  ../bin/pyt -t 1800 tools/look_material_fix.py gpusers TEXT                    Xbox libs whose text names TEXT
  ../bin/pyt -t 600 tools/look_material_fix.py pscalls EXE                      SetPixelShaderConstantF call sites
  ../bin/pyt -t 600 tools/look_material_fix.py vcallidx EXE DISP [MIN]          functions with >= MIN `call [reg+DISP]`
                                                                                 with an immediate index push (0..15)
  ../bin/pyt -t 1200 tools/look_material_fix.py build PC.drm XBOX.drm MID OUTDIR PS_ID VS_ID
      translated pass-2 PS lib + VS lib with the colour pass-through -> OUTDIR/<id>.lib, plan.json, build.txt, asm
  ../bin/pyt -t 1200 tools/look_material_fix.py apply IN.drm XBOX.drm OUT.drm OUTDIR
      new libs after the material's current ones, material -> new libs, PS MaterialParams = Xbox (Xbox layout);
      readback: only the material differs, new libs byte-equal
  ../bin/pyt -t 1200 tools/look_material_fix.py preview OUTDIR PC.drm SCENE.png [G,G]
      SM3-VM preview of the translated PS and the surrogate over a scene picture (see the function)
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
S4 = os.path.join(ROOT, 'work', 'ws', 'shader4')
sys.path.insert(0, S4)
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R
import shaderlib as SL


def sections(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    return D, {(s.type, s.id): s for s in D.sections}


def mat_info(s, e):
    """(libs tuple, texture records, PS MaterialParams) of a material section"""
    f = '>' if e == 'be' else '<'
    d = s.data
    libs = struct.unpack_from(f + '4I', d, 0x28)
    tg = dict(R.parse(bytes(s.reloc), e).internal)
    recs = []
    if 0x54 in tg:
        ntex = d[0x52]
        for k in range(ntex):
            tid, a, ty, fl, slot, filt = struct.unpack_from(f + 'IIIBBH', d, tg[0x54] + 16 * k)
            recs.append(dict(tex=tid, type=ty, u8=fl, slot=slot, filt=filt))
    mp = []
    n = struct.unpack_from(f + 'I', d, 0x58)[0]
    if n and 0x5c in tg:
        v = struct.unpack_from(f + '%df' % (4 * n), d, tg[0x5c])
        mp = [v[4 * i:4 * i + 4] for i in range(n)]
    return libs, recs, mp


def lib_summary(sec, e, plat):
    L = SL.parse(sec.data, e)
    occ = [k for k, o in enumerate(L['slots']) if o != 0xffffffff]
    out = ['  lib %d (%s, kind %d): %d slots, occupied %s, %d unique entries'
           % (sec.id, plat, L['kind'], len(L['slots']), occ if len(occ) <= 16 else '%d' % len(occ), len(L['entries']))]
    seen = set()
    for k in occ[:16]:
        o = L['slots'][k]
        if o in seen: continue
        seen.add(o)
        try: cs = SL.constants(L['entries'][o]['blob'], 'xbox' if e == 'be' else 'pc')
        except Exception as ex: cs = ['(ctab: %s)' % ex]
        out.append('    slot %d entry +%#x: %s' % (k, o, '; '.join(str(c) for c in cs)))
    return L, out


def show(argv):
    xp, pp, mid = argv[0], argv[1], int(argv[2])
    X, XS = sections(xp, 'be'); P, PS = sections(pp, 'le')
    xm, pm = XS[(10, mid)], PS[(10, mid)]
    for nm, s, e, S in (('Xbox', xm, 'be', XS), ('PC', pm, 'le', PS)):
        libs, recs, mp = mat_info(s, e)
        print('%s material %d (%d bytes): libs %s' % (nm, mid, len(s.data), libs))
        for r in recs: print('  texture %(tex)5d type %(type)d u8 %(u8)d sampler s%(slot)d filter %(filt)#06x' % r)
        for j, v in enumerate(mp): print('  PS MP[%d] = (%s)' % (j, ', '.join('%g' % x for x in v)))
        for lid in libs:
            if lid and (9, lid) in S:
                _, lines = lib_summary(S[(9, lid)], e, nm)
                print('\n'.join(lines))
            elif lid:
                print('  lib %d: not in this file' % lid)
    if '--asm' in argv:
        import f9_transplant as F9
        import xenos2sm3
        xl = SL.parse(XS[(9, mat_info(xm, 'be')[0][2])].data, 'be')
        for k in sorted(set(o for o in xl['slots'] if o != 0xffffffff)):
            K = F9.Consts([]); names = {}

            def fn(name, j, count, K=K, names=names):
                r = K.fn(name, j, count); names[(name, j)] = r; return r
            t = xenos2sm3.translate(xl['entries'][k]['blob'], fn, bools=None, samp=lambda n, c: c, opts={})
            print('--- Xbox pass-2 PS entry +%#x, slots %s; constants without a PC register: %s'
                  % (k, [i for i, o in enumerate(xl['slots']) if o == k], sorted(K.extra)))
            print('    constant names -> PC registers: %s' % ', '.join('%s[%d] c%s' % (n, j, r)
                                                                  for (n, j), r in sorted(names.items())))
            print('    Xbox CTAB: %s' % [(c['name'], c['set'], c['reg']) for c in F9.XL.parse(
                xl['entries'][k]['blob']).ctab])
            print(t.text)


def xtext(argv):
    """Xenos container + HLSL-like text (work/ws/xenos/xenos_xlat.py, read-only) of one Xbox lib slot"""
    sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
    import xenos_xlat as XX
    xp, lid = argv[0], int(argv[1]); slots = [int(x) for x in argv[2].split(',')] if len(argv) > 2 else None
    X, XS = sections(xp, 'be')
    L = SL.parse(XS[(9, lid)].data, 'be')
    occ = [k for k, o in enumerate(L['slots']) if o != 0xffffffff]
    print('Xbox lib %d kind %d, occupied slots %s' % (lid, L['kind'], occ))
    for k in (slots if slots is not None else occ[:1]):
        sh = XX.parse(L['entries'][L['slots'][k]]['blob'])
        print('--- slot %d' % k)
        U = XX.USAGE
        if getattr(sh, 'vtx', None):
            print('  vertex fetch: %s' % ['%s%d' % (U[v['usage']], v['index']) for v in sh.vtx])
        print('  interpolators: %s' % ['r%d=%s%d' % (v['reg'], U[v['usage']], v['index']) for v in sh.interp])
        print('  ctab: %s' % [(c['name'], c['set'], c['reg'], c.get('count')) for c in sh.ctab])
        print('  defs: %s' % sh.defs)
        T = XX.text(sh, 'pretty')
        for line in getattr(T, 'lines', getattr(T, 'out', [])): print('  ' + str(line))


def _pc_io(blob):
    """(inputs, outputs) of a PC VS / PS entry as sorted 'usageN.mask' strings (d3d9 dcl tokens)"""
    import sm3asm, sm3dis
    p = sm3asm.decode(blob[:sm3dis.bytecode_len(blob)])
    txt = sm3asm.format_program(p, comments=False).splitlines()
    ins, outs = [], []
    for l in txt:
        l = l.strip()
        if not l.startswith('dcl_') or ' ' not in l: continue
        sem, reg = l.split(None, 1)
        if reg.startswith('o'): outs.append(sem[4:] + ':' + reg)
        elif reg.startswith('v'): ins.append(sem[4:] + ':' + reg)
    return ins, outs


def pcvs(argv):
    """base PC VS libs (work/render/shaderlibs.pkl P) with an entry that outputs a colour: per lib the slot groups and
    their inputs / outputs, and which base Xbox lib maps to it (shader_x2p) - candidates for a screen-quad VS that
    passes the vertex colour like Xbox VS 2328's colour slots"""
    import pickle
    W = os.path.join(ROOT, 'work', 'render')
    L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
    x2p = pickle.load(open(os.path.join(W, 'shader_x2p.pkl'), 'rb'))
    p2x = collections.defaultdict(list)
    for x, p in x2p.items(): p2x[p].append(x)
    want = argv[0].split(',') if argv else ['ScreenMatrix', 'World']
    for pid, lib in sorted(L['P'].items()):
        if lib['kind'] != 0: continue
        groups = collections.OrderedDict()
        for i, o in enumerate(lib['slots']):
            if o != 0xffffffff: groups.setdefault(o, []).append(i)
        rows = []; has_col = False; names_ok = True
        for o, ss in groups.items():
            b = lib['entries'][o]['blob']
            try:
                ins, outs = _pc_io(b)
                cs = SL.constants(b, 'pc')
            except Exception as ex:
                rows.append('    slots %s: (%s)' % (ss, ex)); continue
            names = sorted({c[0] for c in (cs[1] if isinstance(cs, tuple) else cs) if isinstance(c, tuple)})
            if any(s.startswith('color') for s in ins) and any(s.startswith('color') for s in outs): has_col = True
            rows.append('    slots %s: in %s out %s consts %s' % (ss, ins, outs, names))
        if not has_col: continue
        txt = '\n'.join(rows)
        if not all(w in txt for w in want): continue
        print('PC VS lib %d (from base Xbox %s): %d occupied slots' % (pid, p2x.get(pid), sum(len(v) for v in groups.values())))
        print(txt)


def gpusers(argv):
    """Xbox libs (base X and DLC D of work/render/shaderlibs.pkl) whose decoded text names TEXT (e.g. GlobalParams[7]),
    with the decoded lines that hold it"""
    import pickle
    sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
    import xenos_xlat as XX
    text = argv[0]
    L = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shaderlibs.pkl'), 'rb'))
    x2p = pickle.load(open(os.path.join(ROOT, 'work', 'render', 'shader_x2p.pkl'), 'rb'))
    for k in ('X', 'D'):
        n = 0
        for lid, lib in sorted(L[k].items()):
            hits = []
            for o in sorted(set(s for s in lib['slots'] if s != 0xffffffff)):
                try: lines = XX.text(XX.parse(lib['entries'][o]['blob']), 'pretty').lines
                except Exception: continue
                hits += [l.strip() for l in lines if text in l]
            if hits:
                n += 1
                print('%s %d (kind %d%s): %s' % ('base Xbox' if k == 'X' else 'DLC Xbox', lid, lib['kind'],
                                                 ', PC %s' % x2p.get(lid) if k == 'X' else '', sorted(set(hits))[:4]))
        print('%s libs naming %s: %d' % (k, text, n))


def pscalls(argv):
    """every IDirect3DDevice9::SetPixelShaderConstantF call site of tru.exe (`call [reg + 0x1b4]`, also through a
    register loaded from [reg + 0x1b4]) with the function start before it (int3 padding) - where c140.. (GlobalParams)
    is uploaded"""
    import capstone
    import pe_dis as PD, pe_callers as PE
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        loaded = {}
        for ins in md.disasm(exe[rptr:rptr + size], sva):
            if ins.id == 0: loaded.clear(); continue
            ops = ins.operands
            if ins.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG and \
                    ops[1].type == capstone.x86.X86_OP_MEM and ops[1].mem.disp == 0x1b4 and ops[1].mem.base != 0:
                loaded[ops[0].reg] = ins.address
            hit = (ins.mnemonic == 'call' and len(ops) == 1 and ((ops[0].type == capstone.x86.X86_OP_MEM and
                   ops[0].mem.disp == 0x1b4 and ops[0].mem.base != 0) or (ops[0].type == capstone.x86.X86_OP_REG and
                   ops[0].reg in loaded)))
            if hit:
                if ops[0].type == capstone.x86.X86_OP_REG: loaded.pop(ops[0].reg)
                print('0x%08x  in function 0x%08x' % (ins.address, PD.func_start(exe, secs, ins.address)))


# ------------------------------------------------------------------------------------------------ build / apply
NONE = 0xffffffff


def _sm3():
    import sm3asm, sm3dis, f4_lint
    from f11_uninit import uninit_reads, decl_problems
    return sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems


def translate_ps(xblob):
    """direct Xenos -> ps_3_0 translation (upstream xenos2sm3, constants by name -> PC registers, samplers on the same
    register, MaterialParams c100+j read from the material) + static checks"""
    import f9_transplant as F9, xenos2sm3
    sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems = _sm3()
    K = F9.Consts([]); names = {}

    def fn(name, j, count):
        r = K.fn(name, j, count); names[(name, j)] = r; return r
    t = xenos2sm3.translate(xblob, fn, bools=None, samp=lambda n, c: c, opts={})
    if K.extra: raise SystemExit('constants without a PC register: %s' % sorted(K.extra))
    prog = sm3asm.parse_text(t.text)
    bc = sm3asm.encode(prog)
    errs = f4_lint.lint(bc, True)
    if errs or uninit_reads(prog) or decl_problems(prog):
        raise SystemExit('static checks failed: %s %s %s' % (errs[:2], uninit_reads(prog), decl_problems(prog)))
    return bc, names, t.text


def add_colour(blob):
    """PC vs_3_0 entry + vertex colour pass-through (dcl_color vN / dcl_color oM / mov oM, vN) - the part Xbox VS 2328
    adds to its base twin 350 in every slot that fetches Color0"""
    sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems = _sm3()
    p = sm3asm.decode(blob[:sm3dis.bytecode_len(blob)])
    lines = sm3asm.format_program(p, comments=False).splitlines()
    vin = [int(l.split()[1][1:].split('.')[0]) for l in lines if l.strip().startswith('dcl_') and l.split()[1].startswith('v')]
    vout = [int(l.split()[1][1:].split('.')[0]) for l in lines if l.strip().startswith('dcl_') and l.split()[1].startswith('o')]
    if any(l.strip().startswith('dcl_color') for l in lines): raise SystemExit('entry already has a colour')
    vn, on = max(vin) + 1, max(vout) + 1
    out = []; last_dcl = max(i for i, l in enumerate(lines) if l.strip().startswith('dcl'))
    for i, l in enumerate(lines):
        out.append(l)
        if i == last_dcl:
            out += ['    dcl_color v%d' % vn, '    dcl_color o%d' % on]
    out.append('    mov o%d, v%d' % (on, vn))
    prog = sm3asm.parse_text('\n'.join(out))
    return sm3asm.encode(prog), '\n'.join(out)


def vs_valid(bc):
    """vs_3_0 entry: d3dcompiler disassembly re-assembled by D3DX9 without error (f4_lint is pixel-shader only)"""
    import shader_disasm as SD, shader_validate as SV
    sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems = _sm3()
    body = bc[:sm3dis.bytecode_len(bc)]
    txt = SD.disasm(body); ok, msg = SV.assemble(txt)
    return bool(ok and 'vs_3_0' in txt and not msg.strip()), txt, msg.strip()[:200]


def pc_blob(e):
    """the bytes of a PC entry: shaderlib.parse reads size bytes from +16, but the PC size word counts from the entry
    start (16 + bytecode, high 16 bits = dcl_cube mask), so its blob carries the next entry's 8 header bytes"""
    return bytes(e['blob'][:(e['size'] & 0xffff) - 16])


def _lib_rebuild_check(FST, lib, kind):
    """the base layout of FST.pc_lib reproduces an existing PC lib byte for byte (own hashes / size words)"""
    sb = []
    for o in lib['slots']:
        if o == NONE: sb.append(None); continue
        e = lib['entries'][o]
        sb.append((e['hash'], pc_blob(e), e['size']))
    return sb


def build(argv):
    """build PC.drm XBOX.drm MID OUTDIR PS_ID VS_ID"""
    import hashlib, json
    import fade_slots_translate as FST
    sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems = _sm3()
    pp, xp, mid, out, psid, vsid = argv[0], argv[1], int(argv[2]), argv[3], int(argv[4]), int(argv[5])
    os.makedirs(out, exist_ok=True)
    X, XS = sections(xp, 'be'); P, PS = sections(pp, 'le')
    if (9, psid) in PS or (9, vsid) in PS: raise SystemExit('new id already in the file')
    xlibs = mat_info(XS[(10, mid)], 'be')[0]; plibs = mat_info(PS[(10, mid)], 'le')[0]
    rep = ['material %d: Xbox libs %s, PC libs %s' % (mid, xlibs, plibs)]
    taken = FST.known_hashes() | {bytes(e['hash']) for s in P.sections if s.type == 9
                                  for e in SL.parse(s.data, 'le')['entries'].values()}
    # PS: Xbox pass-2 lib, slot k of the PC lib <- Xbox slot k & 1 (8 slots as the PC surrogate)
    xl = SL.parse(XS[(9, xlibs[2])].data, 'be'); pl = SL.parse(PS[(9, plibs[2])].data, 'le')
    occ = [k for k, o in enumerate(pl['slots']) if o != NONE]
    bcs = {}
    for xs in (0, 1):
        bc, names, txt = translate_ps(xl['entries'][xl['slots'][xs]]['blob'])
        ok, dis, err = FST.valid(bc)
        if not ok: raise SystemExit('PS slot %d not valid: %s' % (xs, err))
        bcs[xs] = bc
        open(os.path.join(out, 'ps_x%d.asm' % xs), 'w').write(dis)
        rep.append('PS Xbox %d slot %d: %d bytes, f4_lint + D3DX9 valid, constants %s'
                   % (xlibs[2], xs, len(bc), ', '.join('%s[%d]=c%s' % (n, j, r) for (n, j), r in sorted(names.items()))))
    hs = {xs: FST.new_hash(b'TRU-DLC look 20744|' + bcs[xs], taken) for xs in bcs}
    sb = [(hs[k & 1], bcs[k & 1], None) if k in occ else None for k in range(len(pl['slots']))]
    psdata = FST.pc_lib(1, sb, 0)
    chk = SL.parse(psdata, 'le')
    assert [o != NONE for o in chk['slots']] == [k in occ for k in range(len(pl['slots']))]
    open(os.path.join(out, '%d.lib' % psid), 'wb').write(psdata)
    rep.append('new PS lib %d: %d slots %s (slot k = Xbox slot k & 1), %d bytes, md5 %s'
               % (psid, len(sb), occ, len(psdata), hashlib.md5(psdata).hexdigest()))
    # VS: the material's PC VS lib (PC twin of base Xbox 350 = Xbox 2328 without colour) + colour pass-through in the
    # slots where Xbox 2328 fetches Color0: PC bit 6 (vertex colour, as PC 12 / 229 / 484) and the fog group (Xbox
    # 2328 slots 40 / 168 fetch Color0 too; PC fog entry = the one that writes texcoord5)
    vl = SL.parse(PS[(9, plibs[3])].data, 'le')
    rb = FST.pc_lib(0, _lib_rebuild_check(FST, vl, 0), struct.unpack_from('<I', PS[(9, plibs[3])].data, 4 + 8 + 4 * len(vl['slots']))[0])
    orig = PS[(9, plibs[3])].data
    fd = next((i for i, (a, b) in enumerate(zip(rb, orig)) if a != b), None)
    rep.append('layout check: pc_lib rebuilds PC VS %d byte-equal: %s (len %d / %d, first difference %s: %s / %s)'
               % (plibs[3], rb == orig, len(rb), len(orig), fd, rb[fd:fd + 8].hex() if fd is not None else '',
                  orig[fd:fd + 8].hex() if fd is not None else ''))
    newe = {}; sbv = []; colslots = []
    for k, o in enumerate(vl['slots']):
        if o == NONE: sbv.append(None); continue
        e = vl['entries'][o]
        ins, outs = _pc_io(e['blob'])
        fog = any(s.startswith('texcoord5') for s in outs)
        if k & 0x40 or fog:
            if o not in newe:
                bc, txt = add_colour(e['blob'])
                ok, dis, err = vs_valid(bc)
                if not vs_valid(e['blob'])[0]: raise SystemExit('validator rejects the original VS entry +%#x' % o)
                if not ok: raise SystemExit('VS entry +%#x not valid: %s' % (o, err))
                newe[o] = (FST.new_hash(b'TRU-DLC look VS|' + bc, taken), bc)
                open(os.path.join(out, 'vs_e%x.asm' % o), 'w').write(dis)
            sbv.append((newe[o][0], newe[o][1], None)); colslots.append(k)
        else:
            sbv.append((e['hash'], pc_blob(e), e['size']))
    word0 = struct.unpack_from('<I', PS[(9, plibs[3])].data, 4 + 8 + 4 * len(vl['slots']))[0]
    vsdata = FST.pc_lib(0, sbv, word0)
    open(os.path.join(out, '%d.lib' % vsid), 'wb').write(vsdata)
    rep.append('new VS lib %d: colour pass-through in slots %s (%d new entries), other slots = PC %d entries; '
               '%d bytes, md5 %s' % (vsid, colslots, len(newe), plibs[3], len(vsdata), hashlib.md5(vsdata).hexdigest()))
    xmp = mat_info(XS[(10, mid)], 'be')[2]
    json.dump(dict(mid=mid, ps=psid, vs=vsid, old=list(plibs), params=[list(v) for v in xmp]),
              open(os.path.join(out, 'plan.json'), 'w'), indent=1)
    open(os.path.join(out, 'build.txt'), 'w').write('\n'.join(rep) + '\n')
    print('\n'.join(rep))


def grow_ps_params(s, vals):
    """PS MaterialParams := vals; the PC material has an EMPTY block whose pointer (+0x5c) equals the record pointer
    (+0x54): the vec4 are inserted at the block start, +0x5c keeps it, every later pointer slot / target and id
    reference moves - the Xbox layout (block, then records, then the VS block)"""
    r = R.parse(bytes(s.reloc), 'le')
    tg = dict(r.internal); o = tg[0x5c]; n = struct.unpack_from('<I', s.data, 0x58)[0]
    if n: raise SystemExit('material %d: PS params block not empty (%d)' % (s.id, n))
    add = 16 * len(vals); d = bytearray(s.data)
    d[o:o] = b''.join(struct.pack('<4f', *v) for v in vals)
    r.internal = [(a + add if a >= o else a, b if a == 0x5c else (b + add if b >= o else b)) for a, b in r.internal]
    r.idref = [(t, off + add if off >= o else off) for t, off in r.idref]
    r.idref_a = [(t, off + add if off >= o else off) for t, off in r.idref_a]
    if r.external: raise SystemExit('material %d has external pointers' % s.id)
    struct.pack_into('<I', d, 0x58, len(vals))
    s.data = bytes(d); s.reloc = R.write(r, 'le')
    return '%d vec4 inserted at +%#x (+%d bytes)' % (len(vals), o, add)


def apply(argv):
    """apply IN.drm XBOX.drm OUT.drm OUTDIR"""
    import hashlib, json
    src, xp, dst, out = argv
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    plan = json.load(open(os.path.join(out, 'plan.json')))
    mid, psid, vsid = plan['mid'], plan['ps'], plan['vs']
    secs = {(s.type, s.id): s for s in D.sections}
    mat_idx = {i for i, s in enumerate(D.sections) if s.type == 10}
    for s in D.sections:
        for si, so, do in R.parse(bytes(s.reloc), 'le').external:
            if si in mat_idx: raise SystemExit('section %d:%d points into a material' % (s.type, s.id))
    m = secs[(10, mid)]
    libs = struct.unpack_from('<4I', m.data, 0x28)
    # the same material id is in several DRMs (doppelganger_casual: surrogate copies 2516 / 2517, the four DLC 2 thrall
    # DRMs: 404 / 405); the engine keeps the first loaded copy, so every copy gets the same libs and params. The copy
    # must be the Xbox material's (same texture records); its own pass-0 lib stays.
    X0, XS0 = sections(xp, 'be')
    xr = [(r['tex'], r['slot']) for r in mat_info(XS0[(10, mid)], 'be')[1]]
    pr = [(r['tex'], r['slot']) for r in mat_info(m, 'le')[1]]
    if xr != pr: raise SystemExit('material %d records %s differ from the Xbox %s' % (mid, pr, xr))
    if libs[1] or libs[3] != plan['old'][3]: raise SystemExit('material %d libs %s: unexpected pass-1 / VS' % (mid, libs))
    refs = set(R.parse(bytes(m.reloc), 'le').idref)
    if not {(9, 0x30), (9, 0x34)} <= refs: raise SystemExit('+0x30 / +0x34 are not ShaderLib references')
    for nid, after in ((psid, libs[2]), (vsid, libs[3])):
        if (9, nid) in secs: raise SystemExit('lib %d already in the file' % nid)
        old = secs[(9, after)]
        data = open(os.path.join(out, '%d.lib' % nid), 'rb').read()
        D.sections.insert(D.sections.index(old) + 1, DW.Section(9, nid, data, b'', flags=old.flags, ver=old.ver,
                                                                  spec=old.spec, pad=old.pad))
    d = bytearray(m.data); struct.pack_into('<I', d, 0x30, psid); struct.pack_into('<I', d, 0x34, vsid); m.data = bytes(d)
    info = grow_ps_params(m, [tuple(v) for v in plan['params']])
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = DW.read(raw, 'le').sections; B = DW.read(o, 'le').sections
    rest = [s for s in B if not (s.type == 9 and s.id in (psid, vsid))]
    assert len(rest) == len(A)
    diff = [(a.type, a.id) for a, b in zip(A, rest) if (a.type, a.id, a.data, a.reloc) != (b.type, b.id, b.data, b.reloc)]
    assert diff == [(10, mid)], diff
    for nid in (psid, vsid):
        assert next(x for x in B if x.type == 9 and x.id == nid).data == open(os.path.join(out, '%d.lib' % nid), 'rb').read()
    nm = next(x for x in B if x.type == 10 and x.id == mid)
    _, recs, mp = mat_info(nm, 'le')
    X, XS = sections(xp, 'be')
    xm = XS[(10, mid)]
    print('material %d: libs %s -> %s; PS params %s' % (mid, libs, struct.unpack_from('<4I', nm.data, 0x28), info))
    print('  layout: size %d (Xbox %d), pointers %s (Xbox %s)' % (len(nm.data), len(xm.data),
          sorted(R.parse(bytes(nm.reloc), 'le').internal), sorted(R.parse(bytes(xm.reloc), 'be').internal)))
    print('  records %s' % [(r['tex'], r['u8'], r['slot']) for r in recs])
    print('  PS params %s' % [tuple(round(c, 6) for c in v) for v in mp])
    print('readback: %d original sections in order, only material %d changed, new libs %d / %d byte-equal'
          % (len(A), mid, psid, vsid))
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True); open(dst, 'wb').write(o)
    print('wrote %s md5 %s, %d bytes' % (dst, hashlib.md5(o).hexdigest(), len(o)))


def vcallidx(argv):
    """vcallidx EXE DISP [MIN] - functions of tru.exe with >= MIN (default 5) virtual calls `call [reg + DISP]` (also
    through a register loaded from [reg + DISP]) whose argument pushes include an immediate 0..15 - e.g. the PC twin of
    a TU function that sets GlobalParams[0..6] through (*0x829be0a4)->vtbl[0x84](index, vec4*, 1)"""
    import capstone
    import pe_dis as PD, pe_callers as PE
    exe = open(argv[0], 'rb').read(); disp = int(argv[1], 16); mn = int(argv[2]) if len(argv) > 2 else 5
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    X = capstone.x86
    byf = collections.defaultdict(list)
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        win = collections.deque(maxlen=12); loaded = set()
        for ins in md.disasm(exe[rptr:rptr + size], sva):
            if ins.id == 0: win.clear(); loaded.clear(); continue
            ops = ins.operands
            if ins.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_MEM \
                    and ops[1].mem.disp == disp and ops[1].mem.base != 0:
                loaded.add(ops[0].reg)
            hit = ins.mnemonic == 'call' and len(ops) == 1 and (
                (ops[0].type == X.X86_OP_MEM and ops[0].mem.disp == disp and ops[0].mem.base != 0) or
                (ops[0].type == X.X86_OP_REG and ops[0].reg in loaded))
            if hit:
                imms = [w.operands[0].imm for w in win if w.mnemonic == 'push' and w.operands[0].type == X.X86_OP_IMM
                        and 0 <= w.operands[0].imm < 16]
                if imms:
                    f = PD.func_start(exe, secs, ins.address)
                    byf[f].append((ins.address, imms))
                loaded.clear()
            win.append(ins)
    for f, calls in sorted(byf.items()):
        if len(calls) >= mn:
            print('0x%08x: %d calls %s' % (f, len(calls), ' '.join('%x%s' % (a, i) for a, i in calls[:12])))


def preview(argv):
    """preview OUTDIR PC.drm SCENE.png [G,G,..] - the translated PS (OUTDIR/<ps>.lib slot 0) and the PC surrogate (the
    material's current pass-2 lib, slot 0) in the SM3 VM over SCENE (both back-buffer samplers s0 / s2) with the
    material's texture (s1 = record texture, decoded from PC.drm), vertex colour 0x80576b79 at full fade (alpha 0x80),
    MaterialOpacity 1, ScreenExtents (0, 0, 1/W, 1/H), the Xbox MaterialParams, GlobalParams[7] = (0, G, 0, 0);
    composite = rgb * a + scene * (1 - a) (alpha blend assumed). Writes OUTDIR/preview_*.png + preview.txt.
    A stated neutral environment, not game values (GlobalParams[7] is TU-only, see Befund-Look.md)."""
    import json
    import numpy as np
    from PIL import Image
    import sm3vm
    import tex_convert as T
    sm3asm, sm3dis, f4_lint, uninit_reads, decl_problems = _sm3()
    out, pp, scene_p = argv[0], argv[1], argv[2]
    gs = [float(x) for x in argv[3].split(',')] if len(argv) > 3 else [0.0, 0.5, 1.0]
    plan = json.load(open(os.path.join(out, 'plan.json')))
    P, PS = sections(pp, 'le')
    W, H = 320, 180
    sc = np.asarray(Image.open(scene_p).convert('RGB').resize((W, H)), np.float32) / 255.0
    libs, recs, _ = mat_info(PS[(10, plan['mid'])], 'le')
    tex1 = next(r['tex'] for r in recs if r['slot'] == 1)
    m = T.pc_image(PS[(5, tex1)].data).astype(np.float32) / 255.0
    if m.ndim == 2: m = m[:, :, None]
    if m.shape[2] < 4: m = np.concatenate([m[:, :, :3] if m.shape[2] >= 3 else np.repeat(m, 3, 2), np.ones(m.shape[:2] + (1,), np.float32)], 2)

    def samp(img):
        h, w = img.shape[:2]

        def f(c):
            u = np.clip((c[:, 0] * w).astype(int), 0, w - 1); v = np.clip((c[:, 1] * h).astype(int), 0, h - 1)
            px = img[v, u]
            return px if px.shape[1] == 4 else np.concatenate([px, np.ones((len(px), 1), np.float32)], 1)
        return f
    sc4 = np.concatenate([sc, np.ones((H, W, 1), np.float32)], 2)
    S = {0: samp(sc4), 2: samp(sc4), 1: samp(m)}
    tex = lambda smp, coords, mode: S[smp](coords)
    ys, xs = np.mgrid[0:H, 0:W]
    N = W * H
    vpos = np.stack([xs.ravel(), ys.ravel(), np.zeros(N), np.zeros(N)], 1).astype(np.float32)
    col = np.tile(np.array([0x57, 0x6b, 0x79, 0x80], np.float32) / 255.0, (N, 1))
    lines = []
    progs = {'translated': SL.parse(open(os.path.join(out, '%d.lib' % plan['ps']), 'rb').read(), 'le'),
             'surrogate': SL.parse(PS[(9, libs[2])].data, 'le')}
    Image.fromarray((sc * 255).astype(np.uint8)).save(os.path.join(out, 'preview_scene.png'))
    for nm, L in progs.items():
        blob = pc_blob(L['entries'][L['slots'][0]])
        prog = sm3asm.decode(blob[:sm3dis.bytecode_len(blob)])
        for g in (gs if nm == 'translated' else [0.0]):
            consts = {51: [0, 0, 1.0 / W, 1.0 / H], 98: [1, 1, 1, 1], 147: [0, g, 0, 0]}
            for j, v in enumerate(plan['params']): consts[100 + j] = v
            inputs = {(sm3asm.RT_INPUT, 0): col, (17, 0): vpos}
            r = sm3vm.run(prog, inputs, consts, tex, N)
            o = np.nan_to_num(np.asarray(r['oC0'], np.float32))
            a = np.clip(o[:, 3:4], 0, 1); rgb = np.clip(o[:, :3], 0, 1)
            comp = (rgb * a + sc.reshape(N, 3) * (1 - a)).reshape(H, W, 3)
            tag = '%s_g%.2f' % (nm, g)
            Image.fromarray((comp * 255).astype(np.uint8)).save(os.path.join(out, 'preview_%s.png' % tag))
            Image.fromarray((a.reshape(H, W) * 255).astype(np.uint8)).save(os.path.join(out, 'preview_%s_alpha.png' % tag))
            cen = a.reshape(H, W)[H // 3:2 * H // 3, W // 3:2 * W // 3].mean(); edge = a.reshape(H, W)[:, :W // 8].mean()
            lines.append('%s: rgb mean %s, alpha mean %.3f (centre %.3f, left edge %.3f), composite mean %.3f vs scene %.3f'
                         % (tag, np.round(rgb.mean(0), 3).tolist(), float(a.mean()), float(cen), float(edge),
                            float(comp.mean()), float(sc.mean())))
    open(os.path.join(out, 'preview.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    if sys.argv[1] == 'preview': preview(sys.argv[2:]); sys.exit(0)
    {'show': show, 'xtext': xtext, 'pcvs': pcvs, 'gpusers': gpusers, 'pscalls': pscalls, 'build': build, 'vcallidx': vcallidx,
     'apply': apply}[sys.argv[1]](sys.argv[2:])
