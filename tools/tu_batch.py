"""Test 50m (night 03.11., part 3): batch translation of the remaining title-update / DLC pixel shaders that the PC port
still draws with base-game surrogates. Per material group the same methods and proofs as test 50l:
  * lit pass-2 PS (p_Lights): tools/tu_perlight.py build ("PC per-light geometry + Xbox BRDF", donor = the converter's
    surrogate PC lib), accepted only if every one of the 8 slots matches the Xbox shader lit by one light AND with the
    lights off (tools/tu_shader_night.py xref method, game-like DXN) and passes the build checks (lights-off, f4_lint,
    D3DX9, uninitialised reads, dcl);
  * unlit pass-2 PS: tools/tu_unlit.py direct translation (test 46 / f13), accepted only if every slot == the Xbox
    shader with Xbox registers (VM) and D3DX9 / f4_lint valid;
  * both: every interpolator the new PS reads must be written by at least one occupied slot of the material's PC
    vertex shader (else the group is refused - it needs a VS translation first, like the 50l colour VS);
  * a material id that exists in several DRMs gets the same lib in every copy (the engine keeps the first loaded copy);
    the records (sampler map, DXN registers) must agree in every copy, else the material is refused.
Pass 0 / 1 (depth / alpha passes) are not touched (the 50c / 50l oracles show Nixxes changed them).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/tu_batch.py xdump OUTDIR
      writes every Xbox DLC DRM (ack10 / ack11 of work/generic/dlc_drms.pkl) that has a material whose pass-2 PS is
      untranslated (shader map C1-C3 / D) as OUTDIR/<pack>/<name>.drm (big-endian, as dlc_xbox_dump.py)
  ../bin/pyt -t 3600 tools/tu_batch.py inv XDIR OUT.json TREE [TREE ...]
      effective PC files = installed mods overlaid by the TREEs (later wins); per material: Xbox pass-2 lib, class,
      lit, surrogate, DRMs (effective path), units loading them (objlist.dat of pack10 / pack11; a level DRM counts
      as its own unit), visibility group; ranked list (OUT.json + OUT.txt)
  ../bin/pyt -t 7200 tools/tu_batch.py run INV.json XDIR TREE WORKDIR IDS_FROM [--max N] [--only XLIB,XLIB] [--reuse WD,WD]
      translates the groups in rank order, writes the changed DRMs into TREE/mods (copying the effective file first),
      logs to WORKDIR/run.txt, updates TREE/PROGRESS.md after every group (refused groups are retried on the next run);
      --reuse: a group whose packed lib is byte-identical to a done group of an earlier WORKDIR (same Xbox lib, same
      materials) keeps that lib id, all others get new ids from IDS_FROM
  ../bin/pyt -t 3600 tools/tu_batch.py verify INV.json WORKDIR TREE      independent re-check of every done group in the tree files
  ../bin/pyt -t 3600 tools/tu_batch.py vcheck MODS XDIR [--libs A-B,C] [--no-vm] [--strict]
      binding_check of every translated pass-2 lib in any mods tree (no tu_batch state needed); --strict: exit 1 when a
      copy has a binding problem (pipeline step Shaders)
  ../bin/pyt -t 1800 tools/tu_batch.py selftest      sampler pairing + binding_check + abs-const rewrite regression cases (exit 1 on failure)
  ../bin/pyt -t 3600 tools/tu_batch.py nativefix OUT_MODS LAYER [LAYER ...] [--libs A-B,C]
      17r: rewrite the ABS_CONST form (abs / -abs on a constant, refused by Windows' own D3D9 on AMD) in the effective
      files of an install stack (LAYERs = mods folders, lowest first) into OUT_MODS; constant -> unused temp
      (TLT.fix_abs_native), bit-exact per slot in the VM, f4_lint + D3DX9 valid, lib ids kept, new entry hashes

ABS_CONST (17r, 08.11.): pack_lib runs TLT.fix_abs_native after fix_abs_consts, so new builds carry no abs on a
constant any more (`cmp r8, -|c221.xxxy|, r5.zxyy, |c221.y|` -> `mov rT, c221` + `cmp r8, -|rT.xxxy|, r5.zxyy,
|rT.y|`, rT = a temp the shader never uses); upstream's B269 fold into a def literal (`cmp r5, c217.zzzy, r7.zxyy, c221.y`) reads two constant
registers in one instruction (X5584) and is not used.

Sampler map (08.11., n6b): ALL texture records of a material are paired - the ordinary ones by position, the
per-instance ones (terrain atlases, [+0x52, +0x52 + byte +0x50)) by kind byte (TLT.sampler_map). verify / vcheck
check the translated code without any sampler map: the Xbox reference keeps the Xbox sampler numbers and every VM
texture is keyed by the record role behind its register (binding_check), so the per-instance gap of N6 (3410 read
PC s9 for Xbox s9 = PC s8) now fails.
"""
import sys, os, json, struct, hashlib, collections, pickle, math, time, shutil, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, '..'))
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs
import sm3vm                         # work/ws/shader4 (on the path via tu_light_transplant)
import tu_perlight as TP
import tu_unlit as TU
import tu_shader_night as TN
import perlight_xref as PX
import shaderlib as SL
import drm_write as DW, drm_reloc as R
import fade_slots_translate as FST
import objlists as O

# installed mods folder of the game (env TRUDLC_GAME_MODS, no default: no personal paths in the repo)
GAME_MODS = os.environ.get('TRUDLC_GAME_MODS')
if GAME_MODS and not os.path.isdir(GAME_MODS): GAME_MODS = None


def need_game_mods():
    if not GAME_MODS:
        sys.exit('tu_batch: set TRUDLC_GAME_MODS to the installed "<game>\\mods" folder (missing or not a folder)')
    return GAME_MODS
SMAP = TN.SMAP
UNTR = ('C1', 'C2', 'C3', 'D')
GROUP_W = {'player': 5, 'enemy': 4, 'level': 3, 'object': 2.5, 'effect': 2, 'weapon / pickup': 2}


def group(name, is_unit):
    n = name.lower()
    if any(k in n for k in ('lara', 'doppelganger', 'costume')): return 'player'
    if any(k in n for k in ('thrall', 'yeti', 'viking', 'knight')): return 'enemy'
    if n.startswith(('fx', 'dlc_fx', 'dlc1_fx', 'dlc2_fx')) or '_fx_' in n: return 'effect'
    if n.startswith(('wp_', 'pr_')) or 'health' in n: return 'weapon / pickup'
    return 'level' if is_unit else 'object'


def lit_lib(xid):
    L = libs(); lib = L['D'].get(xid)
    if lib is None or lib['slots'][0] == 0xffffffff: return None
    return any(c['name'] == 'p_Lights' for c in XL.parse(lib['entries'][lib['slots'][0]]['blob']).ctab)


# ---------------------------------------------------------------------------------------------------- xdump
def xbox_names():
    """{(pack, hash): basename} from work/generic/dlc_names.txt - the cache keys the streamgroup DRMs (and other records
    without a filelist name) only by their hash; the PC files carry the resolved name (05.11.: streamgroups were missed)"""
    out = {}
    p = os.path.join(ROOT, 'work', 'generic', 'dlc_names.txt')
    if not os.path.exists(p): return out
    for l in open(p, encoding='utf8', errors='ignore'):
        t = l.split()
        if len(t) >= 3 and t[1] in ('pack10', 'pack11') and t[-1] != '?' and t[-1].lower().endswith('.drm'):
            out[('ack' + t[1][4:] + '.000', int(t[0], 16))] = t[-1].replace('\\', '/').split('/')[-1][:-4].lower()
    return out


def cmd_xdump(outd):
    C = pickle.load(open(os.path.join(ROOT, 'work', 'generic', 'dlc_drms.pkl'), 'rb'))
    XN = xbox_names()
    n = nh = 0; seen = set()
    for key, (h, secs) in C.items():
        pack, path = key[0], key[1]
        if pack not in ('ack10.000', 'ack11.000'): continue
        # hash-only keys ('0x17fc0130', no extension): the streamgroup DRMs - named via dlc_names.txt below
        hv = None
        if path.lower().startswith('0x') and '\\' not in path and '/' not in path:
            try: hv = int(path, 16)
            except ValueError: hv = None
        if hv is None and not path.lower().endswith('.drm'): continue
        if hv is not None and (pack, hv) not in XN: continue      # an unnamed hash record is not a known DRM
        bad = False
        for s in secs:
            if s['type'] != 10 or len(s['data']) < 0x38: continue
            p2 = struct.unpack_from('>I', s['data'], 0x30)[0]
            if SMAP.get(p2, {}).get('cls') in UNTR: bad = True; break
        if not bad: continue
        if hv is not None:
            name = XN[(pack, hv)]; nh += 1; print('  %s %s = %s' % (pack, path, name))
        else: name = os.path.splitext(path.replace('\\', '/').split('/')[-1])[0].lower()
        od = os.path.join(outd, pack.split('.')[0]); os.makedirs(od, exist_ok=True)
        if (pack, name) in seen: print('  %s: %s.drm written twice - last one kept' % (pack, name))
        seen.add((pack, name))
        S = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec']) for s in secs]
        D = DW.Drm(S, b'\0' * h['namesz'], b'\0' * h['padsz'], h['ver'], h['u0'], h['u1'])
        open(os.path.join(od, name + '.drm'), 'wb').write(D.write('be')); n += 1
    print('wrote %d Xbox DRMs with untranslated pass-2 materials to %s (%d named via dlc_names.txt)' % (n, outd, nh))


# ---------------------------------------------------------------------------------------------------- inventory
def units_by_object():
    """object name -> set of units (pack10 + pack11 objlist.dat); set of unit names"""
    out = collections.defaultdict(set); units = set()
    for p in ('pack10', 'pack11'):
        base = os.path.join(ROOT, 'work', 'generic', 'lists', 'dlc_%s_' % p)
        objs = O.read_objectlist(open(base + 'objectlist.txt', 'rb').read())
        recs, _ = O.read_objlist(open(base + 'objlist.dat', 'rb').read(), 'be')
        for u, ids in recs:
            units.add(u.lower())
            for i in ids: out[objs.get(i, '?').lower()].add(u.lower())
    return out, units


SUBDIRS = ('', 'streamgroups')     # mods\ and mods\streamgroups\ (area DRMs the game streams in; 05.11.: were missed)


def mods_drms(mods):
    """{name: path} of the DRMs in a mods folder and its streamgroups sub folder; a name in both levels is refused"""
    out = {}
    for sub in SUBDIRS:
        d = os.path.join(mods, sub)
        if not os.path.isdir(d): continue
        for f in os.listdir(d):
            if not f.lower().endswith('.drm'): continue
            if f.lower() in out: raise SystemExit('%s: %s exists in mods\\ and mods\\streamgroups\\ - refused' % (mods, f))
            out[f.lower()] = os.path.join(d, f)
    return out


def tree_dst(tree, pc_path):
    """path of a PC file inside TREE/mods, keeping the streamgroups sub folder"""
    sub = 'streamgroups' if os.path.basename(os.path.dirname(pc_path)).lower() == 'streamgroups' else ''
    return os.path.join(tree, 'mods', sub, os.path.basename(pc_path))


def effective(trees):
    eff = mods_drms(need_game_mods())
    for t in trees:
        eff.update(mods_drms(os.path.join(t, 'mods')))
    return eff


def is_surrogate_lib(pid):
    """the PC pass-2 lib is a base lib (converter surrogate) or one of the 48g fade copies (2494-2526) - not a translation"""
    return pid in libs()['P'] or 2494 <= pid <= 2526      # 48g fade copies 2494-2526; 2491-2493 = test 42-46 waterfall translations (played)


def owned_by_rule():
    """{file name lower: {material ids}} a later fix rule owns (tools/rule_owned.py, N3 2026-11-11): the ring rule puts
    the base lib 1706 on the ring materials ON PURPOSE - for this tool it looks like a surrogate, n6b re-translated
    21164 / 20345 (08.11.) and the installed stack lost the played ring fix. inv / run skip them, nativefix keeps the
    rule's ShaderLibs."""
    import rule_owned as RO
    return RO.owned_materials()


def cmd_inv(xdir, outp, trees):
    eff = effective(trees); ubo, units = units_by_object()
    L = libs(); rows = {}; owned = owned_by_rule(); skipped = []
    xfiles = {}
    for pk in ('ack11', 'ack10'):
        for f in glob.glob(os.path.join(xdir, pk, '*.drm')):
            xfiles.setdefault(os.path.basename(f).lower(), f)
    for name, xf in sorted(xfiles.items()):
        if name not in eff: continue
        try:
            _, P = TLT.load(eff[name], 'le'); _, X = TLT.load(xf, 'be')
        except Exception as e:
            print('%s: not readable %s' % (name, e)); continue
        base = name[:-4]
        sg = os.path.basename(os.path.dirname(eff[name])).lower() == 'streamgroups'
        us = set(ubo.get(base, set())) | ({base} if base in units else set())
        if sg:      # streamgroup '<unit>_<group>': level geometry of that unit
            us |= {u for u in [max((u for u in units if base.startswith(u + '_')), key=len, default=None)] if u}
        for pm, xm, mesh in TN.mats_of(P, X):
            if (10, pm) not in P or (10, xm) not in X: continue
            xt = struct.unpack_from('>4I', X[(10, xm)].data, 0x28); pt = struct.unpack_from('<4I', P[(10, pm)].data, 0x28)
            c = SMAP.get(xt[2], {}).get('cls')
            if c not in UNTR or not is_surrogate_lib(pt[2]): continue
            if pm in owned.get(name, ()):
                skipped.append('%s mat %d (Xbox lib %d, PC pass-2 lib %d): owned by a fix rule (tools/rule_owned.py)' % (name, pm, xt[2], pt[2]))
                continue
            r = rows.setdefault(pm, dict(mat=pm, xmat=xm, xlib=xt[2], cls=c, lit=lit_lib(xt[2]), surrogate=SMAP[xt[2]].get('pc'),
                                         vs=(xt[3], pt[3]), vscls=SMAP.get(xt[3], {}).get('cls', 'base'), files=[], units=set(), groups=set()))
            if r['xlib'] != xt[2]: r.setdefault('conflict', []).append(name); continue
            r['files'].append(dict(name=name, pc=eff[name], xbox=xf, pcl=pt[2], xmat=xm, sg=sg))
            r['units'] |= us; r['groups'].add(group(base, base in units or sg))
    out = []
    for r in rows.values():
        g = max(r['groups'], key=lambda x: GROUP_W[x]); r['group'] = g
        r['sgonly'] = all(f['sg'] for f in r['files'])
        r['score'] = round(GROUP_W[g] * (1 + math.log(1 + len(r['units']))), 3)
        r['units'] = sorted(r['units']); r['groups'] = sorted(r['groups'])
        out.append(r)
    out.sort(key=lambda r: (-r['score'], r['xlib'], r['mat']))
    json.dump(out, open(outp, 'w'), indent=1)
    with open(os.path.splitext(outp)[0] + '.txt', 'w') as t:
        bylib = collections.Counter(r['xlib'] for r in out)
        t.write('%d materials on surrogates (pass 2), %d Xbox libs; lit %d / unlit %d materials\n' % (
            len(out), len(bylib), sum(1 for r in out if r['lit']), sum(1 for r in out if not r['lit'])))
        for g in GROUP_W: t.write('  %-16s %d materials\n' % (g, sum(1 for r in out if r['group'] == g)))
        for r in out:
            t.write('%6.2f %-8s mat %5d xlib %4d %-2s %s VS %s(%s) units %2d files %s%s\n' % (
                r['score'], r['group'], r['mat'], r['xlib'], r['cls'], 'lit  ' if r['lit'] else 'unlit', r['vs'], r['vscls'],
                len(r['units']), ' '.join(('streamgroups/' if f['sg'] else '') + f['name'] for f in r['files']),
                ' [streamgroup-only]' if r['sgonly'] else ''))
        t.write('streamgroup-only materials: %d\n' % sum(1 for r in out if r['sgonly']))
        t.write('skipped, owned by a fix rule (tools/rule_owned.py): %d\n' % len(skipped))
        for s in skipped: t.write('  %s\n' % s)
    print(open(os.path.splitext(outp)[0] + '.txt').read()[:3000])


# ---------------------------------------------------------------------------------------------------- run
def recs_full(Pd, Xd, pm, xm):
    """TLT.sampler_map of the material: ALL records (ordinary by position, per-instance by kind). Before 08.11. only
    the byte(+0x52) ordinary records entered the map, so a translation sampled a per-instance Xbox register under its
    Xbox number (25057: Xbox s9 = per-instance kind 2 sits on PC s8; N6 lib 3410 read PC s9)."""
    return TLT.sampler_map(Pd[(10, pm)], Xd[(10, xm)], Xd)


def recs_of(Pd, Xd, pm, xm):
    """-> (smap {Xbox reg: PC reg}, dxn {PC regs}) or None when the records do not pair (recs_full)"""
    r = recs_full(Pd, Xd, pm, xm)
    return None if r is None else (r['smap'], r['dxn'])


def ps_inputs(prog):
    return {((i.usage & 31), (i.usage >> 16) & 15) for i in prog.instrs() if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_INPUT}


def vs_outputs_any(Pd, vid):
    if (9, vid) in Pd: lib = SL.parse(Pd[(9, vid)].data, 'le')
    elif vid in libs()['P']: lib = libs()['P'][vid]
    else: return None
    outs = set()
    for k, o in enumerate(lib['slots']):
        if o == 0xffffffff: continue
        prog = F9.decode_pc(lib['entries'][o]['blob'])
        outs |= {((i.usage & 31), (i.usage >> 16) & 15) for i in prog.instrs() if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_TEXOUT}
    return outs


def fix_sincos(T):
    """D3DX9 (error X5767): the destination register of sincos must differ from its source register. xenos2sm3 emits
    e.g. `sincos r3.xy, r3.x` for Xenos sin / cos on the same register. Rewrite: `mov rF, r3` + `sincos r3.xy, rF.x`
    (rF = a new temp). Same values; the caller checks the program in the VM against the Xbox reference."""
    items = list(T.items); used = {o.num for i in T.instrs() for o in i.ops if o.rtype == sm3asm.RT_TEMP}
    free = [r for r in range(32) if r not in used]
    if not free: raise TP.Fail('sincos fix: no free temp')
    F = free[0]; out = []; n = 0
    for it in items:
        if isinstance(it, sm3asm.Instr) and it.op == 'sincos' and it.ops[0].rtype == sm3asm.RT_TEMP and \
                it.ops[1].rtype == sm3asm.RT_TEMP and it.ops[1].num == it.ops[0].num:
            s = it.ops[1]
            if s.smod != 0 or s.rel: raise TP.Fail('sincos fix: source modifier')
            c = 'xyzw'[s.swz & 3]          # sincos reads one replicated component
            out.append(TP.P('mov r%d.x, r%d.%s' % (F, s.num, c)))
            j = TP.clone(it); j.ops[1].num = F; j.ops[1].swz = 0x00; out.append(j); n += 1
        else: out.append(it)
    return (sm3asm.Program(T.kind, T.major, T.minor, out), n) if n else (T, 0)


def build_group(xid, pd, smap, dxn, XP, lit, outd, log, unpaired=()):
    """-> {slot: bytecode} (8 slots) or raises with the reason. unpaired: Xbox registers of records without a PC
    partner (TLT.sampler_map) - a shader that declares such a sampler is refused (it would keep the Xbox number)"""
    L = libs(); lib = TLT.tu_lib(xid); P = L['P']
    if pd not in P: raise TP.Fail('donor / surrogate %s not a base PC lib' % pd)
    xnames = TLT.xbox_sampler_names(lib)
    bad = sorted(r for r in xnames if r in set(unpaired))
    if bad: raise TP.Fail('Xbox samplers %s have a record without a PC partner (per-instance kind differs)' % ['s%d %s' % (r, xnames[r]) for r in bad])
    names = {n: smap[r] for r, n in xnames.items() if r in smap}
    slots = P[pd]['slots']; nsl = 8 if lit else len(slots)
    if lit and len(slots) != 8: raise TP.Fail('lit surrogate %d has %d slots' % (pd, len(slots)))
    TLT.EXTRA_OPTS.clear(); TLT.EXTRA_OPTS.update({'dxn': set(dxn), 'dxn_full': set(dxn)} if dxn else {})
    res = {}; os.makedirs(outd, exist_ok=True)
    for k in range(nsl):
        xs = lib['slots'][k & 1] if lib['slots'][k & 1] != 0xffffffff else lib['slots'][0]
        xblob = lib['entries'][xs]['blob']
        if lit:
            src = k if slots[k] != 0xffffffff else (k & ~1)
            if slots[src] == 0xffffffff: raise TP.Fail('donor slot %d empty' % k)
            lg = []
            T = TP.build(xblob, P[pd]['entries'][slots[src]]['blob'], names, lg)
            # 50o: the lit path needs the same D3DX9 X5767 rewrite as the unlit one (2342: `sincos rN, rN.x`); the
            # checks and the Xbox-lit reference below run on the rewritten program
            T, nsc = fix_sincos(T)
            if nsc: log.append('slot %d: %d sincos with dst == src rewritten (D3DX9 X5767)' % (k, nsc))
            bc, n, off, probs = TLT.checks(T, xblob, XP, names)
            if probs: raise TP.Fail('slot %d: %s' % (k, probs))
            R_, LX = PX.xref_translate(xblob, F9.xsamp(xblob, names), dict(TLT.EXTRA_OPTS))
            sc = []
            for seed, rw in ((5, -100.0), (11, 0.3)):
                o = TN.compare(R_, LX, T, XP, XP, seed, rw, set(dxn), '   %d slot %d seed %d:' % (xid, k, seed))
                sc.append(min(o['off'], o['on']))
            if min(sc) < 0.999: raise TP.Fail('slot %d: Xbox-lit reference %.3f' % (k, min(sc)))
            log.append('slot %d: %d instr, lights-off %.3f, xref %.3f' % (k, n, off, min(sc)))
        else:
            pct = F9.pc_ctab(P[pd]['entries'][next(o for o in slots if o != 0xffffffff)]['blob'])
            T = TU.translate(xblob, pct, names, dxn)
            T, nsc = fix_sincos(T)
            if nsc: log.append('slot %d: %d sincos with dst == src rewritten (D3DX9 X5767)' % (k, nsc))
            bc = sm3asm.encode(T); valid, txt, err = FST.valid(bc)
            if not valid: raise TP.Fail('slot %d invalid: %s' % (k, str(err)[:100]))
            Rx, regs = TU.translate_xregs(xblob, names, dxn)
            ex = F9.Env(5 + k, XP); ep = F9.Env(5 + k, XP); K = F9.Consts(pct)
            for nme, r in regs.items():
                c = next(c for c in XL.parse(xblob).ctab if c['set'] == 2 and c['name'] == nme)
                for j in range(max(1, c['count'])):
                    pr_ = K.fn(nme, j, c['count'])
                    if pr_ is not None: ep.consts[pr_] = ex.consts[r + j]
            for j, v in enumerate(XP): ex.consts[100 + j] = ep.consts[100 + j] = np.array(v, np.float32)
            if 'MaterialParams' in regs:
                for j, v in enumerate(XP): ex.consts[regs['MaterialParams'] + j] = np.array(v, np.float32)
            m = TU.vm_cmp(T, Rx, ep, ex, TN.game_dxn_tex(ex.tex, dxn))
            if m < 0.999: raise TP.Fail('slot %d: PC != Xbox %.3f' % (k, m))
            n = len(F9.body(T))
            log.append('slot %d: %d instr, PC == Xbox %.3f' % (k, n, m))
        res[k] = bc
        open(os.path.join(outd, '%d_s%d.bin' % (xid, k)), 'wb').write(bc)
    return res


def pack_lib(res, nid, taken, nslots):
    sb = []; uniq = {}
    for k in range(nslots):
        bc0 = res[k]; bc, nf = TLT.fix_abs_consts(bc0)
        if nf and TLT.vm_same(bc0, bc) < 1.0: raise TP.Fail('abs fold changed slot %d' % k)
        bc1 = bc
        try: bc, na = TLT.fix_abs_native(bc1)        # 17r: no abs / -abs on a constant (native D3D9 ABS_CONST)
        except ValueError as e: raise TP.Fail('slot %d: %s' % (k, e))
        if na:
            same, why = TLT.vm_exact(bc1, bc)
            if not same: raise TP.Fail('abs-const rewrite changed slot %d (%s)' % (k, why))
        if bc not in uniq:
            ok, txt, err = FST.valid(bc)
            if not ok: raise TP.Fail('packed slot %d invalid' % k)
            uniq[bc] = FST.new_hash(b'test50m|' + bc, taken)
        sb.append((uniq[bc], bc, None))
    return FST.pc_lib(1, sb, 0)


def progress(tree, state):
    p = os.path.join(tree, 'PROGRESS.md')
    lines = ['# PROGRESS %s (updated %s)' % (os.path.basename(os.path.normpath(tree)), time.strftime('%Y-%m-%d %H:%M:%S')), '',
             'Tree = the groups below, each changed file copied from its effective source of the inventory %s first '
             '(stack it after the trees of that inventory). Tool: tools/tu_batch.py run; log %s.' % (state['inv'], state['log']), '',
             '| status | Xbox lib | lit | new lib | materials | files | note |', '|---|---|---|---|---|---|---|']
    for g in state['groups']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (g['status'], g['xlib'], 'lit' if g['lit'] else 'unlit', g.get('new', '-'),
                                                         ' '.join(str(m) for m in g['mats']), ' '.join(sorted(g.get('files', []))), g.get('note', '')))
    lines += ['', 'Next: the remaining groups of the ranked inventory (%s) in order; resume with the same `tu_batch.py run` command (done groups are kept, refused ones retried).' % state['inv'], '']
    open(p, 'w', newline='\r\n').write('\n'.join(lines))


def reuse_table(wds):
    """done groups of earlier runs (WORKDIRs): [{xlib, mats, id, data, wd}] - a group of this run whose packed lib is
    byte-identical to one of them (same Xbox lib, same materials) keeps that lib id (--reuse, n6b 08.11.)"""
    out = []
    for w in wds:
        st = json.load(open(os.path.join(w, 'state.json')))
        for g in st['groups']:
            if g['status'] != 'done': continue
            p = os.path.join(w, 'p', str(g['new']), '%d.lib' % g['new'])
            if os.path.exists(p):
                out.append(dict(xlib=g['xlib'], mats=frozenset(g['mats']), id=g['new'], data=open(p, 'rb').read(), wd=w))
    return out


def cmd_run(invp, xdir, tree, wd, ids_from, maxn, only, reuse=()):
    inv = json.load(open(invp)); os.makedirs(wd, exist_ok=True)
    RU = reuse_table(reuse); reuse_ids = {u['id'] for u in RU}
    logf = open(os.path.join(wd, 'run.txt'), 'a')
    def log(s): print(s, flush=True); logf.write(s + '\n'); logf.flush()
    stp = os.path.join(wd, 'state.json')
    state = json.load(open(stp)) if os.path.exists(stp) else dict(groups=[], log=os.path.join(wd, 'run.txt'), inv=invp, next_id=ids_from)
    # refused groups of an earlier run are tried again (tool fixes in between); done ones are kept
    state['groups'] = [g for g in state['groups'] if g['status'] in ('done', 'reverted')]
    done_mats = {m for g in state['groups'] for m in g['mats']}
    # groups: Xbox lib + sampler map + DXN set (+ donor); a material is one group across all its file copies
    groups = collections.OrderedDict()
    cache = {}
    def load(p, e):
        if p not in cache:
            if len(cache) > 24: cache.clear()
            cache[p] = TLT.load(p, e)[1]
        return cache[p]
    owned = owned_by_rule()
    for r in inv:
        if r['mat'] in done_mats or (only and r['xlib'] not in only): continue
        if r.get('conflict'): continue
        # an inventory written before 2026-11-11 may still list rule-owned copies (the ring): never translate those
        keep = [f for f in r['files'] if r['mat'] not in owned.get(f['name'], ())]
        if len(keep) != len(r['files']):
            log('mat %d: %d file copies skipped - owned by a fix rule (tools/rule_owned.py)' % (r['mat'], len(r['files']) - len(keep)))
            if not keep: continue
            r = dict(r); r['files'] = keep
        # 50n: file copies of one material whose records differ (sampler map / DXN) are split into separate groups -
        # every copy gets the lib built for its own records (the engine draws the first loaded copy, each is exact)
        bysig = collections.OrderedDict(); bad = None
        for f in r['files']:
            pcp = tree_dst(tree, f['pc']) if os.path.exists(tree_dst(tree, f['pc'])) else f['pc']
            Pd = load(pcp, 'le'); Xd = load(f['xbox'], 'be')
            rr = recs_full(Pd, Xd, r['mat'], f['xmat'])
            if rr is None: bad = 'records do not pair (%s)' % f['name']; break
            s = (r['xlib'], tuple(sorted(rr['smap'].items())), tuple(sorted(rr['dxn'])), tuple(sorted(rr['unpaired'])))
            bysig.setdefault(s, []).append(f)
        if bad or not bysig:
            g = groups.setdefault(('bad', r['mat']), dict(xlib=r['xlib'], lit=r['lit'], mats=[], rows=[], score=r['score'], bad=bad or 'no files'))
            g['mats'].append(r['mat']); g['rows'].append(r); continue
        for key, fs in bysig.items():
            r2 = dict(r); r2['files'] = fs
            g = groups.setdefault(key, dict(xlib=r['xlib'], lit=r['lit'], mats=[], rows=[], score=r['score'], bad=None))
            g['mats'].append(r['mat']); g['rows'].append(r2)
    todo = sorted(groups.values(), key=lambda g: -g['score'])
    log('== run %s: %d groups to do (%d materials)' % (time.strftime('%H:%M:%S'), len(todo), sum(len(g['mats']) for g in todo)))
    taken = FST.known_hashes()
    used_ids = set()
    # installed mods + the current test trees (50x, 48i: the ones profiles stack) - older trees are never installed together
    for p in [need_game_mods()] + glob.glob(os.path.join(ROOT, 'work', 'rebuild', 'dlc_test5*', 'mods')) + glob.glob(os.path.join(ROOT, 'work', 'rebuild', 'dlc_test48i*', 'mods')):
        for f in glob.glob(os.path.join(p, '*.drm')) + glob.glob(os.path.join(p, 'streamgroups', '*.drm')):
            try: used_ids |= {s.id for s in DW.read(open(f, 'rb').read(), 'le').sections if s.type == 9}
            except Exception: pass
    for idx in ('idx_pc.json', 'idx_dlc.json'):
        try:
            J = json.load(open(os.path.join(ROOT, 'work', idx)))
            used_ids |= {int(k.split(':')[1]) for k in (J.keys() if isinstance(J, dict) else []) if str(k).startswith('9:')}
        except Exception: pass
    used_ids |= set(libs()['P']) | set(libs()['X']) | set(libs()['D']) | {2943, 2944}
    nid = state['next_id']; nd = 0
    for g in todo:
        if maxn and nd >= maxn: break
        ent = dict(xlib=g['xlib'], lit=g['lit'], mats=g['mats'], status='refused')
        t0 = time.time()
        try:
            if g['bad']: raise TP.Fail(g['bad'])
            r0 = g['rows'][0]; f0 = r0['files'][0]
            pcp0 = tree_dst(tree, f0['pc']) if os.path.exists(tree_dst(tree, f0['pc'])) else f0['pc']
            Pd0 = load(pcp0, 'le'); Xd0 = load(f0['xbox'], 'be')
            rf = recs_full(Pd0, Xd0, r0['mat'], f0['xmat']); smap, dxn = rf['smap'], rf['dxn']
            XPs = {tuple(map(tuple, TLT.mparams(load(rr['files'][0]['xbox'], 'be')[(10, rr['files'][0]['xmat'])], 'be'))) for rr in g['rows']}
            XP = TLT.mparams(Xd0[(10, f0['xmat'])], 'be')
            pd = r0['surrogate']
            lg = []
            res = build_group(g['xlib'], pd, smap, dxn, XP, g['lit'], os.path.join(wd, 'b', '%d_%d' % (g['xlib'], r0['mat'])), lg, rf['unpaired'])
            # other MaterialParams of the group's materials: the lit xref / unlit check once more with each
            if len(XPs) > 1: lg.append('%d different MaterialParams sets in the group (shader is params-independent code; checks used the first)' % len(XPs))
            need = set()
            for bc in res.values(): need |= {s for s in ps_inputs(sm3asm.decode(bc)) if s[0] != 10 or True}
            need = {s for s in need if s[0] in (5, 10)}
            for rr in g['rows']:
                for f in rr['files']:
                    pcp = tree_dst(tree, f['pc']) if os.path.exists(tree_dst(tree, f['pc'])) else f['pc']
                    Pd = load(pcp, 'le'); vid = struct.unpack_from('<4I', Pd[(10, rr['mat'])].data, 0x28)[3]
                    outs = vs_outputs_any(Pd, vid)
                    if outs is None: raise TP.Fail('VS %d of material %d not found' % (vid, rr['mat']))
                    miss = need - outs
                    if miss: raise TP.Fail('PS reads %s, PC VS %d (material %d, %s) never writes them - needs a VS translation' % (sorted(miss), vid, rr['mat'], f['name']))
            data = pack_lib(res, nid, taken, len(res))
            run_ids = {g_['new'] for g_ in state['groups'] if g_['status'] == 'done'}
            u = next((u for u in RU if u['xlib'] == g['xlib'] and u['mats'] == frozenset(g['mats']) and u['data'] == data
                      and u['id'] not in run_ids), None)
            if u is not None:
                gid = u['id']; lg.append('lib byte-identical to %s lib %d: id kept' % (u['wd'], gid))
            else:
                while nid in used_ids or nid in reuse_ids: nid += 1
                gid = nid
            used_ids.add(gid)
            # apply per file: all group materials present in that file
            perfile = collections.defaultdict(list)
            for rr in g['rows']:
                for f in rr['files']: perfile[f['name']].append((rr['mat'], f['xmat'], f))
            pk = os.path.join(wd, 'p', str(gid)); os.makedirs(pk, exist_ok=True)
            open(os.path.join(pk, '%d.lib' % gid), 'wb').write(data)
            for fname, ms in perfile.items():
                f = ms[0][2]
                dst = tree_dst(tree, f['pc'])
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(f['pc'], dst)
                json.dump({str(g['xlib']): dict(new=gid, mats=[(m, x) for m, x, _ in ms])}, open(os.path.join(pk, 'map.json'), 'w'))
                tmp = dst + '.tmp50m'
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    TU.cmd_apply(dst, f['xbox'], tmp, pk, 2)
                os.replace(tmp, dst); cache.pop(dst, None)
                lg.append('apply %s: %s' % (fname, buf.getvalue().strip().splitlines()[-1]))
            ent.update(status='done', new=gid, files=list(perfile), md5=hashlib.md5(data).hexdigest(),
                       note='%d slots, %.0f s%s' % (len(res), time.time() - t0, ', id kept (byte-identical)' if u is not None else ''))
            nd += 1
            if u is None: nid += 1
        except (TP.Fail, F9.Fail, Exception) as e:
            ent['note'] = ('%s: %s' % (type(e).__name__, str(e)))[:200].replace('|', '/')
            ent['files'] = sorted({f['name'] for rr in g['rows'] for f in rr['files']})
            lg = locals().get('lg', [])
        log('%s xlib %d (%s) mats %s -> %s %s' % (ent['status'], g['xlib'], 'lit' if g['lit'] else 'unlit', g['mats'], ent.get('new', '-'), ent.get('note', '')))
        for l in lg: log('     ' + l)
        state['groups'].append(ent); state['next_id'] = nid
        json.dump(state, open(stp, 'w'), indent=1); progress(tree, state)
    log('== end %s: %d translated groups this run' % (time.strftime('%H:%M:%S'), nd))


def sampled_regs(prog):
    """sampler registers a program samples (texld / texldl / texldb / texldd operands)"""
    return {o.num for i in prog.instrs() if i.op.startswith('tex') for o in i.ops if o.rtype == sm3asm.RT_SAMPLER}


def record_roles(recs):
    """{sampler register: role} straight from a material's raw records (TLT.records_all), no sampler map: role
    ('ord', position, kind) for the ordinary records, ('inst', kind) for the per-instance ones - the texture that the
    engine binds to that register. Verify keys its VM textures by these roles on either side (n6b 08.11.)."""
    out = {}; j = 0
    for r in recs:
        if r[4]: key = ('inst', r[2])
        else: key = ('ord', j, r[2]); j += 1
        out.setdefault(r[3], key)
    return out


def _role_tex(roles, dxn):
    def key(s): return roles.get(s, ('engine', s))
    return TN.game_dxn_tex(sm3vm.det_tex(key), dxn)


def _cmp_lit(R_, LX, T, XP, PP, seed, rangew, xtex, ptex):
    """TN.compare with one texture function per side (Xbox reference / PC translation)"""
    rng = np.random.RandomState(seed + 100); Lt = PX.light(rng, rangew)
    ex = F9.Env(seed, XP); ep = F9.Env(seed, PP)
    for r in range(224):
        if not 100 <= r < 132: ep.consts[r] = ex.consts[r]
    worst = 1.0
    for on in (False, True):
        cx = dict(ex.consts); cp = dict(ep.consts)
        Lc = Lt if on else (Lt[0], Lt[1], Lt[2], Lt[3], Lt[4], np.float32([0, 0, 0]))
        PX.set_x(cx, LX, Lc); PX.set_pc(cp, Lc)
        a = F9.run_state(R_, F9.body(R_), ex.state0(R_), cx, xtex, ex.N, {})
        b = F9.run_state(T, F9.body(T), ep.state0(T), cp, ptex, ep.N, {3: True} if on else {})
        ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
        if ca is None or cb is None: return 0.0
        worst = min(worst, float((np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])).mean()))
    return worst


def binding_check(Pd, Xd, m, xm, xlib, data, lit, pct=None, vm=True):
    """sampler-binding check of a translated pass-2 PC lib (bytes `data`) for PC material m / Xbox material xm, built
    WITHOUT any sampler map (n6b 08.11.: the old verify translated its reference with the build's own map and so
    said 1.000 for the per-instance gap). Roles = record_roles of each side's raw records.
      static, per slot: every record role the Xbox shader (Xbox register numbers) samples must be sampled by the PC
        slot and vice versa; an Xbox sampler without a record (engine: s15 attenuation ...) must not land on a PC
        record register;
      VM (vm=True): the Xbox reference keeps the XBOX sampler numbers, every texture is keyed by the role behind the
        register on its own side (DXN by the Xbox texture), so a wrong / missing / swapped sampler register changes the
        fetched values: lit = Xbox-lit reference (2 seeds, lights off / on), unlit = Xbox registers reference.
    -> (worst VM match or None, [problems])"""
    prec, xrec = TLT.records_all(Pd[(10, m)], 'le'), TLT.records_all(Xd[(10, xm)], 'be')
    proles, xroles = record_roles(prec), record_roles(xrec)
    xdxn = {r[3] for r in xrec if TLT.is_dxn(Xd, r[0])}
    pdxn = {p for p, ro in proles.items() if ro in {xroles[r] for r in xdxn if r in xroles}}
    xtex, ptex = _role_tex(xroles, xdxn), _role_tex(proles, pdxn)
    xopts = {'dxn': set(xdxn), 'dxn_full': set(xdxn)} if xdxn else {}
    lib = TLT.tu_lib(xlib); PL = SL.parse(data, 'le')
    XP = TLT.mparams(Xd[(10, xm)], 'be'); PP = TLT.mparams(Pd[(10, m)], 'le')
    probs = []; worst = 1.0 if vm else None
    import io, contextlib
    nsl = len(PL['slots'])
    for k in range(nsl):
        if PL['slots'][k] == 0xffffffff: continue
        T = F9.decode_pc(PL['entries'][PL['slots'][k]]['blob'])
        xs = lib['slots'][k & 1] if lib['slots'][k & 1] != 0xffffffff else lib['slots'][0]
        xblob = lib['entries'][xs]['blob']
        if lit:
            with contextlib.redirect_stdout(io.StringIO()):
                R_, LX = PX.xref_translate(xblob, F9.xsamp(xblob, None), xopts)
        else:
            R_, regs = TU.translate_xregs(xblob, None, xdxn)
        XR, TR = sampled_regs(R_), sampled_regs(T)
        xr_roles = {xroles[r]: r for r in XR if r in xroles}
        pr_roles = {proles[p]: p for p in TR if p in proles}
        exp = {ro: p for p, ro in proles.items()}
        for ro, r in sorted(xr_roles.items(), key=lambda t: t[1]):
            if ro not in pr_roles:
                probs.append('slot %d: Xbox s%d %s not sampled (PC record on %s)' % (k, r, ro, 's%d' % exp[ro] if ro in exp else 'no register'))
        for ro, p in sorted(pr_roles.items(), key=lambda t: t[1]):
            if ro not in xr_roles: probs.append('slot %d: PC s%d %s sampled, the Xbox shader does not sample it' % (k, p, ro))
        for r in sorted(XR):
            if r not in xroles and r in proles: probs.append('slot %d: Xbox engine sampler s%d lands on PC record %s' % (k, r, proles[r]))
        if not vm: continue
        if lit:
            if nsl != 8: probs.append('lit lib with %d slots' % nsl); vm = False; worst = None; continue
            for seed, rw in ((5, -100.0), (11, 0.3)):
                worst = min(worst, _cmp_lit(R_, LX, T, XP, PP, seed, rw, xtex, ptex))
        else:
            if pct is None: worst = None; vm = False; continue
            ex = F9.Env(7 + k, XP); ep = F9.Env(7 + k, PP); K = F9.Consts(pct)
            for nme, r in regs.items():
                c = next(c for c in XL.parse(xblob).ctab if c['set'] == 2 and c['name'] == nme)
                for j in range(max(1, c['count'])):
                    pr_ = K.fn(nme, j, c['count'])
                    if pr_ is not None: ep.consts[pr_] = ex.consts[r + j]
            for j, v in enumerate(PP): ep.consts[100 + j] = np.array(v, np.float32)
            if 'MaterialParams' in regs:
                for j, v in enumerate(XP): ex.consts[regs['MaterialParams'] + j] = np.array(v, np.float32)
            a = F9.run_state(T, F9.body(T), ep.state0(T), ep.consts, ptex, ep.N, {})
            b = F9.run_state(R_, F9.body(R_), ex.state0(R_), ex.consts, xtex, ex.N, {})
            ca, cb = a[0].get((sm3asm.RT_COLOROUT, 0)), b[0].get((sm3asm.RT_COLOROUT, 0))
            if ca is None or cb is None: v_ = 0.0 if (ca is None) != (cb is None) else 1.0
            else: v_ = float((np.isclose(ca, cb, **F9.TOL).all(axis=1) & (a[1] == b[1]) | (a[1] & b[1])).mean())
            worst = min(worst, v_)
    return worst, probs


def cmd_verify(invp, wd, tree):
    """independent re-check on the FINISHED tree files: every material of every done group, in every file copy:
    pass-2 lib == the group's new lib, the lib bytes == the packed lib; unlit: PC MaterialParams start with the Xbox
    ones; then binding_check (no sampler map: static role check + VM with role-keyed textures; lit: Xbox-lit
    reference, 2 seeds, 8 slots; unlit: Xbox registers reference). FAIL on any problem or VM < 0.999."""
    inv = {r['mat']: r for r in json.load(open(invp))}
    state = json.load(open(os.path.join(wd, 'state.json')))
    tot = ok = 0
    for g in state['groups']:
        if g['status'] != 'done': continue
        data = open(os.path.join(wd, 'p', str(g['new']), '%d.lib' % g['new']), 'rb').read()
        for m in g['mats']:
            for f in [f_ for f_ in inv[m]['files'] if not g.get('files') or f_['name'] in g['files']]:
                p = tree_dst(tree, f['pc'])
                _, Pd = TLT.load(p, 'le'); _, Xd = TLT.load(f['xbox'], 'be')
                cur = struct.unpack_from('<4I', Pd[(10, m)].data, 0x28)[2]
                good = cur == g['new'] and Pd[(9, cur)].data == data
                worst = 1.0; probs = []
                if good:
                    pct = None
                    if not g['lit']:
                        XP = TLT.mparams(Xd[(10, f['xmat'])], 'be'); PP = TLT.mparams(Pd[(10, m)], 'le')
                        if [tuple(v) for v in XP] != [tuple(v) for v in PP[:len(XP)]]: probs.append('PC MaterialParams != Xbox')   # PC may keep extra vec4 behind the Xbox ones (unread)
                        pd = inv[m]['surrogate']; P = libs()['P']
                        pct = F9.pc_ctab(P[pd]['entries'][next(o for o in P[pd]['slots'] if o != 0xffffffff)]['blob'])
                    worst, pb = binding_check(Pd, Xd, m, f['xmat'], g['xlib'], data, g['lit'], pct)
                    probs += pb
                    if worst is None: worst = 0.0; probs.append('no VM check')
                passed = good and worst >= 0.999 and not probs
                tot += 1; ok += passed
                print('%s mat %5d %-40s lib %s (%s) %s worst %.3f%s' % ('OK  ' if passed else 'FAIL', m, f['name'], cur,
                      'lit' if g['lit'] else 'unlit', 'bytes ok' if good else 'LIB / BYTES WRONG', worst,
                      (' | ' + '; '.join(probs[:6])) if probs else ''), flush=True)
    print('SUMMARY verify: %d of %d material copies ok' % (ok, tot))


def cmd_vcheck(mods, xdir, ranges, vm):
    """binding_check for every translated pass-2 lib in a mods tree (top + streamgroups) whose DRM has an Xbox twin in
    XDIR/ack10|ack11: materials whose PC pass-2 lib is in RANGES (a-b,c,...) or, without RANGES, is not a base PC
    lib / fade copy. Unlit libs: constants mapped with the PC CTAB of the shader map's surrogate. Prints one line per
    copy and a FAIL list; identical (lib bytes, records, params) combinations are checked once."""
    want = None
    if ranges:
        want = set()
        for t in ranges.split(','):
            a_, _, b_ = t.partition('-'); want |= set(range(int(a_), int(b_ or a_) + 1))
    names = []
    for sub in SUBDIRS:
        d = os.path.join(mods, sub)
        if os.path.isdir(d): names += [os.path.join(sub, n) if sub else n for n in sorted(os.listdir(d)) if n.lower().endswith('.drm')]
    cache = {}; tot = nfail = 0; fails = []
    for rel in names:
        base = os.path.basename(rel).lower()
        xp = next((os.path.join(xdir, p, base) for p in ('ack11', 'ack10') if os.path.exists(os.path.join(xdir, p, base))), None)
        if xp is None: continue
        _, Pd = TLT.load(os.path.join(mods, rel), 'le'); _, Xd = TLT.load(xp, 'be')
        for (t, mid), ps in sorted(Pd.items()):
            if t != 10 or (10, mid) not in Xd or len(ps.data) < 0x38: continue
            pl = struct.unpack_from('<4I', ps.data, 0x28)[2]; xl = struct.unpack_from('>4I', Xd[(10, mid)].data, 0x28)[2]
            if pl == 0 or (want is not None and pl not in want) or (want is None and is_surrogate_lib(pl)): continue
            if (9, pl) not in Pd or xl not in libs()['D']: continue
            lit = bool(lit_lib(xl)); data = Pd[(9, pl)].data
            key = (hashlib.md5(data).hexdigest(), xl, tuple(TLT.records_all(ps, 'le')), tuple(TLT.records_all(Xd[(10, mid)], 'be')),
                   tuple(map(tuple, TLT.mparams(ps, 'le'))), tuple(map(tuple, TLT.mparams(Xd[(10, mid)], 'be'))))
            if key not in cache:
                pct = None
                sur = SMAP.get(xl, {}).get('pc'); P = libs()['P']
                if not lit and sur in P:
                    pct = F9.pc_ctab(P[sur]['entries'][next(o for o in P[sur]['slots'] if o != 0xffffffff)]['blob'])
                try: cache[key] = binding_check(Pd, Xd, mid, mid, xl, data, lit, pct, vm)
                except Exception as e: cache[key] = (None, ['check error %s: %s' % (type(e).__name__, str(e)[:120])])
            worst, probs = cache[key]
            tot += 1; bad = bool(probs)
            if bad: nfail += 1; fails.append('%s mat %d lib %d' % (rel, mid, pl))
            print('%s mat %5d %-62s lib %4d xlib %4d %-5s VM %s%s' % ('FAIL' if bad else 'ok  ', mid, rel, pl, xl, 'lit' if lit else 'unlit',
                  '-' if worst is None else '%.3f' % worst, (' | ' + '; '.join(probs[:6])) if probs else ''), flush=True)
    print('SUMMARY vcheck %s: %d translated material copies, %d with binding problems' % (mods, tot, nfail))
    for l in fails: print('  FAIL ' + l)
    return nfail


def _lib_parse(d):
    """ShaderLib section (type 9): u8 kind + 3 pad | u32 tableBytes | u32 dataSize (= len - 4) | u32 slot offset[]
    (relative to byte 4, 0xffffffff = empty) | entries {u32 word0, u32 size word ((16 + code) | cube mask << 16),
    u64 hash, code}. -> (head, tb, offs, {offset: [word0, size word, hash, code]}) - slots may share an entry"""
    tb, ds = struct.unpack_from('<II', d, 4)
    if ds != len(d) - 4: raise ValueError('dataSize %d != section length - 4 (%d)' % (ds, len(d) - 4))
    offs = list(struct.unpack_from('<%dI' % (tb // 4), d, 12)); ents = {}
    for o in offs:
        if o == 0xffffffff or o in ents: continue
        a, sz, h = struct.unpack_from('<II8s', d, 4 + o)
        ents[o] = [a, sz, h, d[4 + o + 16:4 + o + (sz & 0xFFFF)]]
    return d[:4], tb, offs, ents


def _lib_build(head, tb, offs, ents):
    body = bytearray(); moved = {}; pos = 12 + tb
    for o in sorted(ents):
        a, sz, h, code = ents[o]
        moved[o] = pos - 4
        e = struct.pack('<II', a, (sz & 0xFFFF0000) | (16 + len(code))) + bytes(h) + code
        body += e; pos += len(e)
    no = [o if o == 0xffffffff else moved[o] for o in offs]
    return bytes(head) + struct.pack('<II', tb, 8 + tb + len(body)) + struct.pack('<%dI' % len(no), *no) + bytes(body)


def _ranges(txt):
    if not txt: return None
    want = set()
    for t in txt.split(','):
        a_, _, b_ = t.partition('-'); want |= set(range(int(a_), int(b_ or a_) + 1))
    return want


def cmd_nativefix(out, layers, ranges=None):
    """17r (08.11.2026): rewrite the ABS_CONST form (abs / -abs on a constant register, refused by Windows' own D3D9 on
    AMD) in the pixel shaders of an install stack. LAYERS = mods-style folders, lowest first (e.g. the installed mods,
    then the test trees in install order); the effective copy of every DRM (top + streamgroups) is the one of the last
    layer that has it. Every effective file with a ShaderLib (type 9; with --libs only those ids) whose pixel shaders
    carry the form is rewritten into OUT (sub folder kept): per shader TLT.fix_abs_native (constant -> unused temp,
    `mov rT, cN` before the instruction), proven per slot bit-exact in the VM (TLT.vm_exact) and valid (f4_lint +
    D3DX9, FST.valid); lib ids, slot table, word0 and the size word's cube mask are kept, a changed entry gets a new
    hash (the same new code gets the same hash in every file, never a known hash). Readback: every other section byte-
    identical, the changed libs parse to the same slots, no ABS_CONST left, no instruction with two different constant
    registers. Writes OUT/../nativefix.json (per lib: slots, movs, files, source layer) and prints a summary."""
    want = _ranges(ranges)
    import rule_owned as RO
    owned_libs = RO.owned_libs()
    eff = {}; layer_of = {}
    for li, L in enumerate(layers):
        for name, p in mods_drms(L).items(): eff[name] = p; layer_of[name] = li
    taken = FST.known_hashes()
    for p in eff.values():                     # every hash of the effective stack is taken
        try:
            for s in DW.read(open(p, 'rb').read(), 'le').sections:
                if s.type == 9 and len(s.data) >= 12:
                    for e in _lib_parse(s.data)[3].values(): taken.add(bytes(e[2]))
        except Exception: pass
    memo = {}; per_lib = collections.defaultdict(lambda: dict(slots=set(), movs=0, files=set(), layers=set()))
    nfiles = 0; problems = []
    for name in sorted(eff):
        p = eff[name]; raw = open(p, 'rb').read()
        try: D = DW.read(raw, 'le')
        except Exception: continue
        changed = {}
        keep_libs = owned_libs.get(name, set())      # the fix rules' ShaderLibs (base PC libs) stay byte-identical
        for si, s in enumerate(D.sections):
            if s.type != 9 or len(s.data) < 12 or (want is not None and s.id not in want) or s.id in keep_libs: continue
            head, tb, offs, ents = _lib_parse(s.data)
            if _lib_build(head, tb, offs, ents) != s.data: problems.append('%s lib %d: rebuild not byte-identical' % (name, s.id)); continue
            hit = False
            for o, e in ents.items():
                code = e[3]
                if code[2:4] != b'\xff\xff' or not TLT.abs_const_operands(code): continue
                new, n = TLT.fix_abs_native(code)
                if code not in memo:
                    same, why = TLT.vm_exact(code, new)
                    if not same: raise SystemExit('%s lib %d entry +%#x: rewrite not bit-exact (%s)' % (name, s.id, o, why))
                    prog = sm3asm.decode(new); body = new[:4 * prog.nend]
                    ok_, txt, err = FST.valid(body)
                    if not ok_: raise SystemExit('%s lib %d entry +%#x: rewritten shader not valid (%s)' % (name, s.id, o, err))
                    memo[code] = (new, FST.new_hash(b'17r native|' + new, taken), n)
                new, h, n = memo[code]
                e[3] = new; e[2] = h; hit = True
                L_ = per_lib[s.id]; L_['slots'] |= {k for k, oo in enumerate(offs) if oo == o}; L_['movs'] += n
            if hit:
                if s.reloc: raise SystemExit('%s lib %d has relocations - refused' % (name, s.id))
                changed[si] = _lib_build(head, tb, offs, ents)
                per_lib[s.id]['files'].add(name); per_lib[s.id]['layers'].add(layer_of[name])
        if not changed: continue
        old = [bytes(s.data) for s in D.sections]
        for si, d in changed.items(): D.sections[si].data = d
        outb = D.write('le')
        if raw[:4] in (b'CDRM', b'MRDC'): outb = DW.cdrm_encode(outb, 'le')
        sub = 'streamgroups' if os.path.basename(os.path.dirname(p)).lower() == 'streamgroups' else ''
        q = os.path.join(out, sub, os.path.basename(p)); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(outb); nfiles += 1
        # readback
        R_ = DW.read(open(q, 'rb').read(), 'le')
        if len(R_.sections) != len(old): raise SystemExit('%s: section count changed' % q)
        for si, s in enumerate(R_.sections):
            if si not in changed:
                if s.data != old[si]: raise SystemExit('%s: section %d changed unexpectedly' % (q, si))
                continue
            h0, tb0, offs0, e0 = _lib_parse(old[si]); h1, tb1, offs1, e1 = _lib_parse(s.data)
            if h0 != h1 or tb0 != tb1 or [o == 0xffffffff for o in offs0] != [o == 0xffffffff for o in offs1]:
                raise SystemExit('%s lib %d: slot table changed' % (q, s.id))
            for k, (o0, o1) in enumerate(zip(offs0, offs1)):
                if o0 == 0xffffffff: continue
                c0, c1 = e0[o0][3], e1[o1][3]
                if e0[o0][0] != e1[o1][0] or (e0[o0][1] >> 16) != (e1[o1][1] >> 16): raise SystemExit('%s lib %d slot %d: word0 / cube mask changed' % (q, s.id, k))
                if c1[2:4] == b'\xff\xff' and TLT.abs_const_operands(c1): raise SystemExit('%s lib %d slot %d: ABS_CONST left' % (q, s.id, k))
                if c0 == c1: continue
                if memo.get(c0, (None,))[0] != c1: raise SystemExit('%s lib %d slot %d: unexpected code' % (q, s.id, k))
                pr = sm3asm.decode(c1)
                for i in pr.instrs():
                    if i.op in ('dcl', 'def', 'defi', 'defb'): continue
                    if len({o.num for o in i.ops if not o.isdst and o.rtype == sm3asm.RT_CONST and not o.rel}) > 1:
                        raise SystemExit('%s lib %d slot %d: two different constant registers in one instruction' % (q, s.id, k))
    rep = {str(l): dict(slots=sorted(v['slots']), movs=v['movs'], files=sorted(v['files']), layers=sorted(v['layers'])) for l, v in sorted(per_lib.items())}
    json.dump(dict(layers=layers, libs=rep, unique_shaders=len(memo), files=nfiles, problems=problems),
              open(os.path.join(os.path.dirname(os.path.normpath(out)), 'nativefix.json'), 'w'), indent=1)
    for l, v in rep.items():
        print('lib %s: slots %s, %d movs, %d files, layers %s' % (l, v['slots'], v['movs'], len(v['files']), v['layers']))
    for pb in problems: print('PROBLEM ' + pb)
    print('SUMMARY nativefix: %d libs, %d unique pixel shaders rewritten (each bit-exact in the VM, f4_lint + D3DX9 valid), '
          '%d files written to %s, readback ok, %d problems' % (len(rep), len(memo), nfiles, out, len(problems)))


def cmd_selftest():
    """regression self-test of the sampler pairing (TLT.pair_records / sampler_map) and of binding_check (n6b 08.11.).
    Synthetic record lists (always) + real data when the files exist (TRUDLC_GAME_MODS not needed): 25057
    (`dlc_yggdrasil_end`, Xbox per-instance kind 2 s9 -> PC s8), 25520 (swapped kinds), 23303 (identity), 20265
    (per-instance kind differs -> unpaired); binding_check must FAIL the N6 lib 3410 on 25057 and pass the floor proof
    lib 3460. Exit 1 on any failure."""
    fails = []; nok = [0]
    def ok(c, msg):
        print(('  ok   ' if c else '  FAIL ') + msg, flush=True)
        if c: nok[0] += 1
        else: fails.append(msg)
    def rec(tid, typ, kind, reg, inst=False): return (tid, typ, kind, reg, inst)
    # 1 synthetic: 25057-like records (Xbox s8/s2/s3/s4 ordinary + per-instance kinds 1 / 3 / 2 on s0 / s1 / s9)
    X = [rec(7349, 1, 0, 8), rec(7350, 5, 0, 2), rec(7351, 1, 0, 3), rec(7352, 3, 0, 4),
         rec(119, 6, 1, 0, True), rec(147, 6, 3, 1, True), rec(288, 6, 2, 9, True)]
    P = [rec(7349, 1, 0, 9), rec(7350, 5, 0, 3), rec(7351, 1, 0, 4), rec(7352, 3, 0, 2),
         rec(121, 6, 1, 0, True), rec(719, 6, 3, 1, True), rec(255, 6, 2, 8, True)]
    pairs, un, pb = TLT.pair_records(P, X); sm = {x[3]: p[3] for x, p in pairs}
    ok(not pb and not un and sm == {8: 9, 2: 3, 3: 4, 4: 2, 0: 0, 1: 1, 9: 8}, 'synthetic 25057: map %s (Xbox s9 kind 2 -> PC s8)' % sm)
    old = {x[3]: p[3] for p, x in zip([r for r in P if not r[4]], [r for r in X if not r[4]])}
    ok(9 not in old, 'synthetic 25057: the old ordinary-only map has no Xbox s9 (the gap the fix closes)')
    # 2 synthetic: swapped per-instance kinds, stored in different order (25520 / 26120: kind 1 s2 -> s1, kind 2 s1 -> s2)
    X2 = [rec(10, 1, 0, 0), rec(119, 6, 1, 2, True), rec(288, 6, 2, 1, True)]
    P2 = [rec(10, 1, 0, 0), rec(255, 6, 2, 2, True), rec(121, 6, 1, 1, True)]
    pairs, un, pb = TLT.pair_records(P2, X2); sm = {x[3]: p[3] for x, p in pairs}
    ok(not pb and sm == {0: 0, 2: 1, 1: 2}, 'synthetic swapped kinds (other order on PC): paired by kind %s' % sm)
    # 3 synthetic: per-instance kind only on one side (20265: Xbox kind 1, PC kind 2) -> unpaired, no guess
    X3 = [rec(10, 1, 0, 1), rec(119, 6, 1, 0, True)]; P3 = [rec(10, 1, 0, 0), rec(255, 7, 2, 1, True)]
    pairs, un, pb = TLT.pair_records(P3, X3)
    ok(not pb and [u[3] for u in un] == [0] and {x[3]: p[3] for x, p in pairs} == {1: 0}, 'synthetic kind only on one side: Xbox s0 unpaired %s' % un)
    # 4 synthetic: ordinary count / kind differ -> not pairable (old rule kept)
    ok(bool(TLT.pair_records(P3[:1], X3[:1] + [rec(5, 1, 0, 5)])[2]), 'synthetic ordinary count differs -> problem')
    ok(bool(TLT.pair_records([rec(1, 0, 9, 2)], [rec(1, 0, 0, 2)])[2]), 'synthetic ordinary kind differs -> problem')
    # 5 role keys: identical on both sides exactly when the pairing holds
    xr_, pr_ = record_roles(X), record_roles(P)
    ok(xr_[9] == pr_[8] == ('inst', 2) and xr_[8] == pr_[9] == ('ord', 0, 0), 'record_roles: Xbox s9 / PC s8 = inst 2, Xbox s8 / PC s9 = ord 0')
    # 5b abs-const rewrite (17r): TLT.fix_abs_native = constant -> unused temp, bit-exact, no ABS_CONST, no X5584
    def asm(t): return sm3asm.encode(sm3asm.parse_text(t))
    # def literal read twice (the translator's form), a uniform constant (sign random in the VM), abs + plain read of one register
    pa = asm('ps_3_0\ndef c220, 3, 1, 0, -1\ndcl_texcoord v0\ndcl_texcoord1 v1\nmul r1, v0, c5\n'
             'cmp r8, -c220.zzzy_abs, r1.zxyy, c220.y_abs\ncmp r9, -c7_abs, v1, c220.x\n'
             'add r2, r8, -c6.yxzw_abs\nadd r2, r2, c6\nmov oC0, r2\nmov oC1, r9\n')
    na_ = TLT.abs_const_operands(pa)
    pb_, nmv = TLT.fix_abs_native(pa)
    ok(na_ == 4 and TLT.abs_const_operands(pb_) == 0 and nmv == 3, 'abs-const rewrite: %d abs operands -> %d, %d movs inserted (one per instruction and register)' % (na_, TLT.abs_const_operands(pb_), nmv))
    same, why = TLT.vm_exact(pa, pb_)
    ok(same, 'abs-const rewrite: VM bit-exact (oC0 / oC1, bools off / on, 3 seeds) %s' % why)
    prg = sm3asm.decode(pb_)
    two = [sm3asm.fmt_instr(i, 'ps') for i in prg.instrs() if i.op not in ('dcl', 'def') and
           len({o.num for o in i.ops if not o.isdst and o.rtype == sm3asm.RT_CONST and not o.rel}) > 1]
    ok(not two, 'abs-const rewrite: no instruction reads two different constant registers (X5584) %s' % two)
    vt, txt_, err_ = FST.valid(pb_)
    ok(vt, 'abs-const rewrite: f4_lint + D3DX9 valid %s' % (err_ if not vt else ''))
    tl = [sm3asm.fmt_instr(i, 'ps') for i in prg.instrs()]
    ok(any(l.startswith('mov r0, c220') for l in tl) and any(l == 'cmp r8, -r0.zzzy_abs, r1.zxy, r0.y_abs' for l in tl),
       'abs-const rewrite: mov r0, c220 + cmp r8, -r0.zzzy_abs, r1.zxyy, r0.y_abs (both c220 operands moved) %s' % [l for l in tl if l.startswith(('mov r0', 'cmp r8'))])
    ok(TLT.fix_abs_native(pb_) == (pb_, 0) and TLT.fix_abs_native(asm('ps_3_0\nmov oC0, c1\n'))[1] == 0, 'abs-const rewrite: idempotent, no change without the form')
    # temp reuse: three cmps on c220 in a row -> one mov; an `if` in between -> loaded again after it
    pr3 = asm('ps_3_0\ndef c220, 0, 1, 1.5, -1\ndefb b3, true\ndcl_texcoord v0\nmul r2, v0, c9\n'
              'cmp r5, -c220.xxxy_abs, r2.zxyy, c220.y_abs\ncmp r6, -c220.xxxy_abs, r2.xyzz, c220.y_abs\n'
              'if b3\ncmp r7, -c220.xxxy_abs, r2.zyxx, c220.y_abs\nelse\nmov r7, r2\nendif\n'
              'cmp r8, -c220.xxxy_abs, r7, c220.y_abs\nadd r5, r5, r6\nadd r5, r5, r8\nmov oC0, r5\n')
    r3, n3 = TLT.fix_abs_native(pr3); s3, w3 = TLT.vm_exact(pr3, r3); v3 = FST.valid(r3)[0]
    ok(n3 == 3 and s3 and v3 and TLT.abs_const_operands(r3) == 0, 'abs-const rewrite: temp reused (2 cmps in a row -> 1 mov, reloaded inside if and after endif: %d movs), VM bit-exact %s %s, valid %s' % (n3, s3, w3, v3))
    # sensitivity: a wrong rewrite (abs kept, sign dropped) must fail the bit-exact VM check
    bad = sm3asm.decode(pb_)
    for i in bad.instrs():
        if i.op == 'cmp':
            for o in i.ops:
                if not o.isdst and o.smod == 12: o.smod = 11
    ok(not TLT.vm_exact(pa, sm3asm.encode(bad))[0], 'abs-const rewrite: sensitivity - a rewrite with -|x| -> |x| fails vm_exact')
    full = asm('ps_3_0\ndcl_texcoord v0\n' + ''.join('mov r%d, v0\n' % r for r in range(32)) + 'add r0, r31, -c3_abs\nmov oC0, r0\n')
    try: TLT.fix_abs_native(full); raised = False
    except ValueError: raised = True
    ok(raised, 'abs-const rewrite: refused (ValueError) when all 32 temps are used and the constant is a uniform')
    # fallback: all temps used, def literal -> one new def literal, bit for bit (-0.0 kept)
    fd = asm('ps_3_0\ndef c220, -0.0, 1, -2, 3\ndcl_texcoord v0\n' + ''.join('mov r%d, v0\n' % r for r in range(32)) +
             'cmp r0, -c220.xxxy_abs, r31, c220.y_abs\nadd r0, r0, -c220.zwzw_abs\nadd r0, r0, r1\nmov oC0, r0\n')
    fb, nf_ = TLT.fix_abs_native(fd)
    fx, why = TLT.vm_exact(fd, fb); vt, _, err_ = FST.valid(fb)
    dl = [sm3asm.fmt_instr(i, 'ps') for i in sm3asm.decode(fb).instrs() if i.op in ('def', 'cmp')]
    ok(nf_ == 3 and TLT.abs_const_operands(fb) == 0 and fx and vt, 'abs-const fallback (32 temps used): def-literal fold, %d operands, VM bit-exact %s, valid %s %s' % (nf_, fx, vt, dl))
    sm_ = sm3asm.decode(fb).instrs()
    newdef = [i for i in sm_ if i.op == 'def' and i.ops[0].num != 220]
    ok(len(newdef) == 2 and newdef[0].imm[0] == 0x80000000, 'abs-const fallback: two new defs, -|-0.0| keeps the bit pattern 0x80000000 (%s)' % [hex(u) for i in newdef for u in i.imm])
    try: TLT.fix_abs_native(asm('ps_3_0\ndef c220, 1, 2, 3, 4\ndef c221, 5, 6, 7, 8\ndcl_texcoord v0\n' + ''.join('mov r%d, v0\n' % r for r in range(32)) +
                                'mad r0, -c220_abs, r31, c221_abs\nmov oC0, r0\n')); raised = False
    except ValueError: raised = True
    ok(raised, 'abs-const fallback: refused with more than 4 distinct values in one instruction')
    # 6 real data
    xd = os.path.join(ROOT, 'work', 'sg_audit_0511', 'xbox', 'ack11')
    cases = [('floor 3460', os.path.join(ROOT, 'work', 'floor_0811', 'testtree', 'mods', 'dlc_yggdrasil_end.drm'), 25057, 3460, True),
             ('N6 3410', os.path.join(ROOT, 'work', 'n6shaders_0711', 'testtree', 'mods', 'dlc_yggdrasil_end.drm'), 25057, 3410, False)]
    xf = os.path.join(xd, 'dlc_yggdrasil_end.drm')
    if not os.path.exists(xf) or not all(os.path.exists(c[1]) for c in cases):
        print('  skip real-data cases (files missing)')
    else:
        _, Xd = TLT.load(xf, 'be')
        for tag, pf, mat, lid, want in cases:
            _, Pd = TLT.load(pf, 'le')
            r = TLT.sampler_map(Pd[(10, mat)], Xd[(10, mat)], Xd)
            if tag.startswith('floor'):
                ok(r is not None and r['smap'].get(9) == 8 and not r['unpaired'], 'real 25057: sampler_map Xbox s9 -> PC s%s' % (r and r['smap'].get(9)))
                o = TLT.records(Pd[(10, mat)], 'le'), TLT.records(Xd[(10, mat)], 'be')
                ok(9 not in {x[3]: p[3] for p, x in zip(*o)}, 'real 25057: old TLT.records map leaves Xbox s9 out')
                if (10, 23303) in Pd and (10, 23303) in Xd:
                    r2 = TLT.sampler_map(Pd[(10, 23303)], Xd[(10, 23303)], Xd)
                    ok(r2 is not None and all(r2['smap'][x] == x for x in (0, 1, 8) if x in r2['smap']), 'real 23303: per-instance registers identity %s' % (r2 and r2['smap']))
            cur = struct.unpack_from('<4I', Pd[(10, mat)].data, 0x28)[2]
            ok(cur == lid, '%s: material %d pass-2 lib = %d' % (tag, mat, cur))
            w, pb = binding_check(Pd, Xd, mat, mat, 2346, Pd[(9, lid)].data, True)
            passed = w is not None and w >= 0.999 and not pb
            ok(passed == want, '%s on 25057: binding_check %s (VM %.3f, %s)' % (tag, 'passes' if passed else 'fails', w if w is not None else -1, '; '.join(pb[:2]) or 'no static problem'))
        sgx = os.path.join(xd, 'dlc2_uo_piston_a.drm'); sgp = os.path.join(ROOT, 'work', 'n6shaders_0711', 'testtree', 'mods', 'dlc2_uo_piston_a.drm')
        if os.path.exists(sgx) and os.path.exists(sgp):
            _, Xd = TLT.load(sgx, 'be'); _, Pd = TLT.load(sgp, 'le')
            r = TLT.sampler_map(Pd[(10, 25520)], Xd[(10, 25520)], Xd)
            ok(r is not None and r['smap'].get(2) == 1 and r['smap'].get(1) == 2, 'real 25520: per-instance kind 1 Xbox s2 -> PC s1, kind 2 Xbox s1 -> PC s2 (%s)' % (r and r['smap']))
            w, pb = binding_check(Pd, Xd, 25520, 25520, 2591, Pd[(9, 3408)].data, True)
            ok(w is not None and w < 0.999, 'N6 3408 on 25520 (swapped kinds): VM catches it (%.3f; static: %s)' % (w if w is not None else -1, '; '.join(pb[:1]) or 'none - the sets agree'))
        dgx = os.path.join(ROOT, 'work', 'sg_audit_0511', 'xbox', 'ack10', 'dlc_dungeon_dungeon_main.drm')
        dgp = os.path.join(ROOT, 'work', 'n5mats_0711', 'testtree', 'mods', 'streamgroups', 'dlc_dungeon_dungeon_main.drm')
        if os.path.exists(dgx) and os.path.exists(dgp):
            _, Xd = TLT.load(dgx, 'be'); _, Pd = TLT.load(dgp, 'le')
            r = TLT.sampler_map(Pd[(10, 20265)], Xd[(10, 20265)], Xd)
            ok(r is not None and r['unpaired'] == {0}, 'real 20265: per-instance Xbox kind 1 (s0) has no PC partner (PC kind 2) -> unpaired %s' % (r and r['unpaired']))
    print('SELFTEST %s: %d ok, %d failed' % ('PASSED' if not fails else 'FAILED', nok[0], len(fails)))
    if fails: sys.exit(1)


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'verify': cmd_verify(a[1], a[2], a[3]); return
    if a[0] == 'mark':      # mark WORKDIR TREE NEWLIB STATUS NOTE   (e.g. a group reverted by hand)
        stp = os.path.join(a[1], 'state.json'); st = json.load(open(stp))
        for g in st['groups']:
            if g.get('new') == int(a[3]): g['status'] = a[4]; g['note'] = a[5]
        json.dump(st, open(stp, 'w'), indent=1); progress(a[2], st); return
    if a[0] == 'xdump': cmd_xdump(a[1]); return
    if a[0] == 'inv': cmd_inv(a[1], a[2], a[3:]); return
    if a[0] == 'run':
        def opt(k, d=None):
            if k in a:
                j = a.index(k); v = a[j + 1]; del a[j:j + 2]; return v
            return d
        mx = int(opt('--max', 0)); only = opt('--only'); only = {int(x) for x in only.split(',')} if only else None
        reuse = opt('--reuse'); reuse = reuse.split(',') if reuse else ()
        cmd_run(a[1], a[2], a[3], a[4], int(a[5]), mx, only, reuse); return
    if a[0] == 'vcheck':
        novm = '--no-vm' in a; a = [x for x in a if x != '--no-vm']
        strict = '--strict' in a; a = [x for x in a if x != '--strict']     # 2026-11-11 (pipeline step Shaders): exit 1 on a problem
        rg = None
        if '--libs' in a: j = a.index('--libs'); rg = a[j + 1]; a = a[:j] + a[j + 2:]
        nfail = cmd_vcheck(a[1], a[2], rg, not novm)
        if strict and nfail: sys.exit(1)
        return
    if a[0] == 'selftest': cmd_selftest(); return
    if a[0] == 'nativefix':
        rg = None
        if '--libs' in a: j = a.index('--libs'); rg = a[j + 1]; a = a[:j] + a[j + 2:]
        cmd_nativefix(a[1], a[2:], rg); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
