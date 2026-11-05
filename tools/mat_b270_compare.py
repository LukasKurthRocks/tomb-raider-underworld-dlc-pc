"""Read-only comparison of the materials that upstream's B270 kit re-points to new / other shader libraries (DLC 1 water
20262, treasure room 26584 and the DLC 1 lit materials with new pixel-shader libs) against B138, our installed /
tree files and the Xbox original (2026-11-05, docs Befund-Materialien-B270-0511).

Material words (PC little-endian, Xbox big-endian): +0x28 pass-0 PS, +0x2c pass-1 PS, +0x30 pass-2 PS, +0x34 VS.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/mat_b270_compare.py mats REL:MID [REL:MID ...] [--trees]
      per material copy: shader tuple in the kit (work/b270_kit/mods), B138 (work/rebuild/b138_pristine/mods,
      b138_fixes/mods), the installed game mods (env TRUDLC_GAME_MODS) and - with --trees - every
      work/rebuild/*/mods tree holding that file; the Xbox material (work/render/shaderlibs.pkl DM, same id) with the
      shader-map class of each Xbox lib (work/render/dlc_shader_map.json) and whether the Xbox pass-2 lib is lit
  ../bin/pyt -t 1800 tools/mat_b270_compare.py libs OUTDIR REL:LIB[:OLDLIB] [...]
      one ShaderLib of a kit file: slots, entries, md5 of every shader body against the PC game shaders
      (tools/native_test/pc_shader_md5.txt and the base PC libs of shaderlibs.pkl), CTAB creator / constant names,
      instruction count, light chain (`if b`), samplers; per slot the similarity (difflib ratio of the instruction
      lines) to OLDLIB (a base PC lib = the B138 surrogate); disassembly of every entry to OUTDIR/<lib>/
  ../bin/pyt -t 1800 tools/mat_b270_compare.py xlib XLIB [XLIB ...]
      Xbox DLC lib facts: kind, slots, entries, shader-map class / PC id / surrogate / basis, lit, CTAB names of slot 0
  ../bin/pyt -t 1800 tools/mat_b270_compare.py xdump OUTDIR NAME[,NAME] [PACK]
      Xbox DLC DRMs (work/generic/dlc_drms.pkl, PACK default ack10.000) as raw big-endian files OUTDIR/<name>.drm;
      NAME `matID` = list every cached DRM holding material ID and write the first as OUTDIR/<name>_mID.drm
  ../bin/pyt -t 1800 tools/mat_b270_compare.py vmcmp FILE.drm:LIB FILE.drm:LIB|P:LIB [...]
      per slot SM3-VM equality (tu_light_transplant.vm_same: random inputs, light bools off / on) of the first lib
      against each further lib (P:LIB = base PC lib from shaderlibs.pkl)
  ../bin/pyt -t 3600 tools/mat_b270_compare.py trial OUTDIR PCFILE:XBOXFILE:MAT[:VSLIB,...] [...]
      dry run of OUR translation path for the material's Xbox pass-2 PS (tu_batch.build_group, same checks and the
      Xbox-lit reference >= 0.999); only .bin files under OUTDIR, no DRM written; then the interpolator rule against
      the material's PC VS and the extra VSLIBs (e.g. upstream's PC base VS 164 / 243)
  ../bin/pyt -t 900 tools/mat_b270_compare.py pcinfo PCLIB [PCLIB ...]
      base PC lib facts: slots, CTAB names of the first occupied slot, Xbox base libs whose PC twin it is (shader_x2p)
  ../bin/pyt -t 3600 tools/mat_b270_compare.py idscan TYPE ID[,ID] DIR [DIR ...]
      which DRMs below the DIRs contain section (TYPE, ID) - section headers only (first CDRM blocks)
"""
import sys, os, re, glob, json, pickle, struct, zlib, hashlib, difflib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, '..'))
import drm_write as DW
import shaderlib as SL

W = os.path.join(ROOT, 'work', 'render')
KIT = os.path.join(ROOT, 'work', 'b270_kit', 'mods')
B138P = os.path.join(ROOT, 'work', 'rebuild', 'b138_pristine', 'mods')
B138F = os.path.join(ROOT, 'work', 'rebuild', 'b138_fixes', 'mods')
GAME = os.environ.get('TRUDLC_GAME_MODS')
_L = None
_SMAP = None


def libs():
    global _L
    if _L is None: _L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
    return _L


def smap():
    global _SMAP
    if _SMAP is None: _SMAP = {int(k): v for k, v in json.load(open(os.path.join(W, 'dlc_shader_map.json'))).items()}
    return _SMAP


def load(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    return {(s.type, s.id): s for s in D.sections}


def tup(s, e='<'): return struct.unpack_from(e + '4I', s.data, 0x28)


def fmt_t(t): return 'PS0 %s PS1 %s PS2 %s VS %s' % tuple(t)


def ctab_info(blob):
    i = blob.find(b'CTAB')
    if i < 0: return None, []
    o = i + 4
    try:
        size, creator, version, n, cinfo, flags, target = struct.unpack_from('<7I', blob, o)
        end = blob.find(b'\0', o + creator)
        cr = blob[o + creator:end].decode('latin1')
    except Exception:
        return '?', []
    _, names = SL._ctab(blob, o, '<')
    return cr, names


def lit(xid):
    lib = libs()['D'].get(xid)
    if lib is None: return None
    occ = [o for o in lib['slots'] if o != 0xffffffff]
    if not occ: return None
    v, names = SL.constants(lib['entries'][occ[0]]['blob'], 'x')
    return any(n[0] == 'p_Lights' for n in names)


# ------------------------------------------------------------------------------------------------ mats
def cmd_mats(args, trees):
    L = libs(); SM = smap()
    for a in args:
        rel, mid = a.rsplit(':', 1); mid = int(mid)
        print('=== material %d in %s' % (mid, rel))
        srcs = [('kit B270', KIT), ('b138_pristine', B138P), ('b138_fixes', B138F)]
        if GAME: srcs.append(('installed', GAME))
        if trees:
            for t in sorted(glob.glob(os.path.join(ROOT, 'work', 'rebuild', '*', 'mods'))):
                srcs.append(('tree ' + os.path.basename(os.path.dirname(t)), t))
        for name, base in srcs:
            p = os.path.join(base, rel)
            if not os.path.isfile(p):
                if not name.startswith('tree'): print('  %-34s (file missing)' % name)
                continue
            try: S = load(p)
            except Exception as e: print('  %-34s not readable: %s' % (name, e)); continue
            s = S.get((10, mid))
            if s is None: print('  %-34s material missing' % name); continue
            t = tup(s)
            here = [x for x in t if x and (9, x) in S]
            print('  %-34s %s  size %d  md5 %s  libs in file: %s' % (name, fmt_t(t), len(s.data),
                                                                      hashlib.md5(s.data).hexdigest()[:12], here))
        xm = L['DM'].get(mid)
        if xm is None: print('  Xbox: material %d not in shaderlibs.pkl DM' % mid); continue
        xt = struct.unpack_from('>4I', xm[0], 0x28)
        print('  %-34s %s  size %d' % ('Xbox (DM)', fmt_t(xt), len(xm[0])))
        for k, x in zip(('PS0', 'PS1', 'PS2', 'VS'), xt):
            if not x: continue
            m = SM.get(x)
            if m is None: print('    Xbox %s %d: base lib (not a DLC lib), in X: %s' % (k, x, x in L['X'])); continue
            print('    Xbox %s %d: class %s pc %s surrogate %s basis %s%s' % (k, x, m.get('cls'), m.get('pc'),
                  m.get('surrogate'), m.get('basis'), ('  lit %s' % lit(x)) if k != 'VS' else ''))


# ------------------------------------------------------------------------------------------------ libs
def body_of(blob):
    w = struct.unpack('<%dI' % (len(blob) // 4), blob[:len(blob) // 4 * 4]); i = 1
    while i < len(w):
        t = w[i]; op = t & 0xFFFF
        if op == 0xFFFF: return blob[:4 * (i + 1)]
        if op == 0xFFFE: i += 1 + ((t >> 16) & 0x7FFF); continue
        i += 1 + ((t >> 24) & 0xF)
    return blob


def ins_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith(('//', 'ps_', 'vs_'))]


def pc_index():
    L = libs(); idx = {}
    for lid, lib in L['P'].items():
        for o, e in lib['entries'].items():
            idx.setdefault(hashlib.md5(body_of(e['blob'])).hexdigest(), set()).add(lid)
    return idx


def cmd_libs(outd, args):
    import shader_disasm as SD
    L = libs(); idx = pc_index()
    pcmd5 = set(l.strip() for l in open(os.path.join(HERE, 'native_test', 'pc_shader_md5.txt')) if l.strip())
    for a in args:
        parts = a.split(':'); rel, lid = parts[0], int(parts[1]); old = int(parts[2]) if len(parts) > 2 else None
        S = load(os.path.join(KIT, rel)); s = S[(9, lid)]
        lib = SL.parse(s.data, 'le')
        occ = [o for o in lib['slots'] if o != 0xffffffff]
        junk = collections.Counter('%08x' % e['junk'] for e in lib['entries'].values())
        print('=== lib %d (%s) kind %d  section %d B md5 %s  slots %d (occupied %d)  entries %d  junk words %s' % (
            lid, rel, lib['kind'], len(s.data), hashlib.md5(s.data).hexdigest(), len(lib['slots']), len(occ),
            len(lib['entries']), dict(junk)))
        if lid in L['P']:
            P = L['P'][lid]
            same = [k for k, (a1, b1) in enumerate(zip(lib['slots'], P['slots']))
                    if (a1 == 0xffffffff) == (b1 == 0xffffffff) and (a1 == 0xffffffff or
                        lib['entries'][a1]['blob'] == P['entries'][b1]['blob'])]
            print('  base PC lib %d exists: slots %d vs %d, slots with identical shader %d / %d' % (
                lid, len(lib['slots']), len(P['slots']), len(same), len(lib['slots'])))
        O = L['P'].get(old) if old else None
        if old: print('  compared with base PC lib %d (B138 surrogate): %s' % (old, 'present' if O else 'NOT in shaderlibs.pkl P'))
        od = os.path.join(outd, str(lid)); os.makedirs(od, exist_ok=True)
        texts = {}
        for o in sorted(lib['entries']):
            e = lib['entries'][o]; b = body_of(e['blob']); md = hashlib.md5(b).hexdigest()
            t = SD.disasm(b); texts[o] = t
            open(os.path.join(od, 'entry_%05x.asm' % o), 'w').write(t)
            il = ins_lines(t)
            cr, names = ctab_info(e['blob'])
            ops = collections.Counter(l.split()[0] for l in il)
            slots = [k for k, x in enumerate(lib['slots']) if x == o]
            print('  entry +%05x slots %s %s md5 %s  pc_shader_md5 %s  in base PC libs %s  instr %d (tex %d, if_b %d, '
                  'loop/rep %d, def %d)' % (o, slots, t.split()[0] if t else '?', md[:12], md in pcmd5,
                  sorted(idx.get(md, []))[:6], sum(1 for l in il if not l.startswith(('dcl', 'def'))),
                  sum(v for k, v in ops.items() if k.startswith('texld')), sum(1 for l in il if re.match(r'if b\d', l)),
                  ops['loop'] + ops['rep'], ops['def']))
            print('      CTAB creator %r, %d constants: %s' % (cr, len(names), ' '.join(
                '%s@%s%d' % (SL.norm_name(n), 'bic s'[rs] if rs < 5 else '?', ri) for n, rs, ri, rc in names[:14])))
        if O:
            for k, (a1, b1) in enumerate(zip(lib['slots'], O['slots'])):
                if a1 == 0xffffffff or b1 == 0xffffffff:
                    print('  slot %d: new %s / old %s' % (k, 'empty' if a1 == 0xffffffff else 'set', 'empty' if b1 == 0xffffffff else 'set'))
                    continue
                ob = body_of(O['entries'][b1]['blob'])
                ot = SD.disasm(ob); nl, ol = ins_lines(texts[a1]), ins_lines(ot)
                r = difflib.SequenceMatcher(None, ol, nl, autojunk=False).ratio()
                ro = difflib.SequenceMatcher(None, [x.split()[0] for x in ol], [x.split()[0] for x in nl], autojunk=False).ratio()
                print('  slot %d vs %d slot %d: identical %s  line ratio %.3f  opcode ratio %.3f  instr new %d / old %d' % (
                    k, old, k, body_of(lib['entries'][a1]['blob']) == ob, r, ro, len(nl), len(ol)))


# ------------------------------------------------------------------------------------------------ xlib
def cmd_xlib(ids):
    L = libs(); SM = smap()
    for x in ids:
        lib = L['D'].get(x)
        m = SM.get(x, {})
        if lib is None: print('Xbox lib %d: not a DLC lib in shaderlibs.pkl (base X: %s)' % (x, x in L['X'])); continue
        occ = [o for o in lib['slots'] if o != 0xffffffff]
        v, names = SL.constants(lib['entries'][occ[0]]['blob'], 'x') if occ else (None, [])
        print('Xbox lib %d: kind %s slots %d (occupied %d) entries %d  class %s pc %s surrogate %s basis %r lit %s' % (
            x, lib['kind'], len(lib['slots']), len(occ), len(lib['entries']), m.get('cls'), m.get('pc'),
            m.get('surrogate'), m.get('basis'), lit(x)))
        print('   slot-0 CTAB: %s' % ' '.join(sorted(set(SL.norm_name(n[0]) for n in names))))
        for k in ('sim', 'similarity', 'score'):
            if k in m: print('   %s %s' % (k, m[k]))


def cmd_xdump(outd, names, pack):
    """Xbox DRMs from work/generic/dlc_drms.pkl as raw big-endian files (as tools/dlc_xbox_dump.py, one cache load)"""
    C = pickle.load(open(os.path.join(ROOT, 'work', 'generic', 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    os.makedirs(outd, exist_ok=True)
    for name in names:
        if name.startswith('mat'):          # matID: every cached DRM of the pack holding material ID; the first is written
            mid = int(name[3:])
            hits = sorted(((k, v) for k, v in C.items() if k[0] == pack and any(s['type'] == 10 and s['id'] == mid for s in v[1])),
                          key=lambda kv: kv[0][1])
            print('material %d in %d cached DRMs: %s' % (mid, len(hits), '; '.join(k[1] for k, v in hits)))
            if not hits: continue
            name = '%s_m%d' % (base(hits[0][0][1]), mid)
        else:
            hits = [(k, v) for k, v in C.items() if k[0] == pack and base(k[1]) == name.lower()]
        if not hits: print('no %s in %s' % (name, pack)); continue
        h, secs = hits[0][1]
        S = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec']) for s in secs]
        D = DW.Drm(S, b'\0' * h['namesz'], b'\0' * h['padsz'], h['ver'], h['u0'], h['u1'])
        raw = D.write('be'); p = os.path.join(outd, name.lower() + '.drm')
        open(p, 'wb').write(raw)
        print('wrote %s (%s, %d sections, md5 %s)' % (p, hits[0][0][1], len(S), hashlib.md5(raw).hexdigest()))


def lib_from(spec):
    """FILE.drm:LIB (a lib section of that PC file) or P:LIB (base PC lib of shaderlibs.pkl) -> parsed lib"""
    f, lid = spec.rsplit(':', 1); lid = int(lid)
    if f == 'P': return libs()['P'][lid]
    return SL.parse(load(f)[(9, lid)].data, 'le')


def cmd_vmcmp(a_spec, b_specs):
    """per slot: tools/tu_light_transplant.vm_same (SM3 VM, random inputs / constants / textures, all light bools off
    and on; 1.000 = same colour output on every sample) of lib A against each lib B"""
    import tu_light_transplant as TLT
    A = lib_from(a_spec)
    for b in b_specs:
        B = lib_from(b); res = []
        for k, (oa, ob) in enumerate(zip(A['slots'], B['slots'])):
            if oa == 0xffffffff or ob == 0xffffffff: res.append('%d:-' % k); continue
            res.append('%d:%.3f' % (k, TLT.vm_same(A['entries'][oa]['blob'], B['entries'][ob]['blob'])))
        print('%s vs %s: %s' % (a_spec, b, ' '.join(res)))


def cmd_trial(outd, specs):
    """dry translation with OUR lit / unlit path (tools/tu_batch.build_group: tu_perlight build + D3DX9 / f4_lint checks +
    Xbox-lit reference >= 0.999 with 2 seeds; unlit: tu_unlit + VM PC == Xbox) for PCFILE:XBOXFILE:MAT[:VSLIB,...];
    writes only OUTDIR/<xlib>_<mat>/<xlib>_s<k>.bin, changes no DRM. Then the tu_batch interpolator rule: every
    TEXCOORD / COLOR the new PS reads must be written by the material's PC VS (and by each extra VSLIB listed)."""
    import time
    import tu_batch as TB, tu_perlight as TP
    import sm3asm
    SM = smap()
    for spec in specs:
        parts = spec.split(':'); pcf, xf, mat = parts[0], parts[1], int(parts[2])
        extra_vs = [int(v) for v in parts[3].split(',')] if len(parts) > 3 else []
        t0 = time.time()
        Pd = load(pcf); Xd = {(s.type, s.id): s for s in DW.read(open(xf, 'rb').read(), 'be').sections}
        xt = struct.unpack_from('>4I', Xd[(10, mat)].data, 0x28); pt = struct.unpack_from('<4I', Pd[(10, mat)].data, 0x28)
        xid = xt[2]; m = SM.get(xid, {}); pd = m.get('pc'); lit_ = lit(xid)
        head = 'trial mat %d: Xbox PS2 %d (%s, %s), donor / surrogate PC %s, PC file PS2 %d VS %d' % (
            mat, xid, m.get('cls'), 'lit' if lit_ else 'unlit', pd, pt[2], pt[3])
        rr = TB.recs_of(Pd, Xd, mat, mat)
        if rr is None: print(head + ' -> REFUSED: records do not pair'); continue
        smap_, dxn = rr
        XP = TB.TLT.mparams(Xd[(10, mat)], 'be'); lg = []
        try:
            res = TB.build_group(xid, pd, smap_, dxn, XP, lit_, os.path.join(outd, '%d_%d' % (xid, mat)), lg)
        except Exception as e:
            print(head + ' -> REFUSED (%.0f s): %s: %s' % (time.time() - t0, type(e).__name__, str(e)[:240]))
            for l in lg: print('     ' + l)
            continue
        need = set()
        for bc in res.values(): need |= {s for s in TB.ps_inputs(sm3asm.decode(bc)) if s[0] in (5, 10)}
        vsr = []
        for vid in [pt[3]] + extra_vs:
            outs = TB.vs_outputs_any(Pd, vid)
            vsr.append('VS %d: %s' % (vid, 'not found' if outs is None else ('ok' if not (need - outs) else 'MISSING %s' % sorted(need - outs))))
        print(head + ' -> BUILT %d slots (%.0f s); PS reads %s; %s' % (len(res), time.time() - t0, sorted(need), '; '.join(vsr)))
        for l in lg: print('     ' + l)


def cmd_pcinfo(ids):
    """base PC lib: occupied slots, CTAB names of the first occupied slot, Xbox base libs whose PC twin it is"""
    L = libs(); x2p = pickle.load(open(os.path.join(W, 'shader_x2p.pkl'), 'rb'))
    for p in ids:
        lib = L['P'].get(p)
        if lib is None: print('PC lib %d: not a base PC lib' % p); continue
        occ = [o for o in lib['slots'] if o != 0xffffffff]
        _, names = SL.constants(lib['entries'][occ[0]]['blob'], 'p') if occ else (None, [])
        tw = sorted(x for x, q in x2p.items() if q == p)
        print('PC lib %d: kind %s slots %d (occupied %d) entries %d; Xbox base twins %s' % (
            p, lib['kind'], len(lib['slots']), len(occ), len(lib['entries']), tw[:10]))
        print('   first-slot CTAB: %s' % ' '.join(sorted(set(SL.norm_name(n[0]) for n in names))))


# ------------------------------------------------------------------------------------------------ idscan
def header_sections(path):
    d = open(path, 'rb').read()
    if d[:4] == b'CDRM':
        n, = struct.unpack_from('<I', d, 8)
        ents = [struct.unpack_from('<II', d, 16 + 8 * i) for i in range(n)]
        pos = (16 + 8 * n + 15) & ~15; out = bytearray()
        for u, c in ents:
            blk = d[pos:pos + c]
            out += zlib.decompress(blk) if (u & 0xff) == 2 else blk
            pos = (pos + c + 15) & ~15
            if len(out) >= 24:
                k, = struct.unpack_from('<i', out, 20)
                if len(out) >= 24 + 20 * k: break
        d = bytes(out)
    n, = struct.unpack_from('<i', d, 20)
    return [struct.unpack_from('<iBBHIII', d, 24 + 20 * i) for i in range(n)]


def cmd_idscan(typ, ids, dirs):
    hits = collections.defaultdict(list); nf = 0
    for base in dirs:
        for dp, dn, fn in os.walk(base):
            for f in fn:
                if not f.lower().endswith('.drm'): continue
                p = os.path.join(dp, f); nf += 1
                try: secs = header_sections(p)
                except Exception: continue
                for size, t, pad, ver, packed, sid, spec in secs:
                    if t == typ and sid in ids: hits[sid].append(os.path.relpath(p, ROOT).replace(os.sep, '/'))
    print('scanned %d DRMs in %d dirs' % (nf, len(dirs)))
    for i in sorted(ids):
        h = hits.get(i, [])
        print('%d:%d in %d DRMs%s' % (typ, i, len(h), (': ' + '; '.join(h[:40]) + (' ...' if len(h) > 40 else '')) if h else ''))


def main(a):
    if not a: sys.exit(__doc__)
    c = a[0]
    if c == 'mats': cmd_mats([x for x in a[1:] if x != '--trees'], '--trees' in a)
    elif c == 'libs': cmd_libs(a[1], a[2:])
    elif c == 'xlib': cmd_xlib([int(x) for x in a[1:]])
    elif c == 'pcinfo': cmd_pcinfo([int(x) for x in a[1:]])
    elif c == 'vmcmp': cmd_vmcmp(a[1], a[2:])
    elif c == 'trial': cmd_trial(a[1], a[2:])
    elif c == 'xdump': cmd_xdump(a[1], a[2].split(','), a[3] if len(a) > 3 else 'ack10.000')
    elif c == 'idscan': cmd_idscan(int(a[1]), {int(x) for x in a[2].split(',')}, a[3:])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
