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
  ../bin/pyt -t 7200 tools/tu_batch.py run INV.json XDIR TREE WORKDIR IDS_FROM [--max N] [--only XLIB,XLIB]
      translates the groups in rank order, writes the changed DRMs into TREE/mods (copying the effective file first),
      logs to WORKDIR/run.txt, updates TREE/PROGRESS.md after every group (refused groups are retried on the next run)
  ../bin/pyt -t 3600 tools/tu_batch.py verify INV.json WORKDIR TREE      independent re-check of every done group in the tree files
"""
import sys, os, json, struct, hashlib, collections, pickle, math, time, shutil, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, '..'))
import tu_light_transplant as TLT
from tu_light_transplant import F9, sm3asm, XL, libs
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


def cmd_inv(xdir, outp, trees):
    eff = effective(trees); ubo, units = units_by_object()
    L = libs(); rows = {}
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
    print(open(os.path.splitext(outp)[0] + '.txt').read()[:3000])


# ---------------------------------------------------------------------------------------------------- run
def recs_of(Pd, Xd, pm, xm):
    pr, xr = TLT.records(Pd[(10, pm)], 'le'), TLT.records(Xd[(10, xm)], 'be')
    if len(pr) != len(xr): return None
    smap = {}
    for p, x in zip(pr, xr):
        if smap.get(x[3], p[3]) != p[3]: return None
        smap[x[3]] = p[3]
    dxn = {p[3] for p, x in zip(pr, xr) if (5, x[0]) in Xd and struct.unpack_from('>I', Xd[(5, x[0])].data, 4)[0] & 0x3f == 0x31}
    return smap, dxn


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


def build_group(xid, pd, smap, dxn, XP, lit, outd, log):
    """-> {slot: bytecode} (8 slots) or raises with the reason"""
    L = libs(); lib = TLT.tu_lib(xid); P = L['P']
    if pd not in P: raise TP.Fail('donor / surrogate %s not a base PC lib' % pd)
    xnames = TLT.xbox_sampler_names(lib)
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


def cmd_run(invp, xdir, tree, wd, ids_from, maxn, only):
    inv = json.load(open(invp)); os.makedirs(wd, exist_ok=True)
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
    for r in inv:
        if r['mat'] in done_mats or (only and r['xlib'] not in only): continue
        if r.get('conflict'): continue
        # 50n: file copies of one material whose records differ (sampler map / DXN) are split into separate groups -
        # every copy gets the lib built for its own records (the engine draws the first loaded copy, each is exact)
        bysig = collections.OrderedDict(); bad = None
        for f in r['files']:
            pcp = tree_dst(tree, f['pc']) if os.path.exists(tree_dst(tree, f['pc'])) else f['pc']
            Pd = load(pcp, 'le'); Xd = load(f['xbox'], 'be')
            rr = recs_of(Pd, Xd, r['mat'], f['xmat'])
            if rr is None: bad = 'records do not pair (%s)' % f['name']; break
            s = (r['xlib'], tuple(sorted(rr[0].items())), tuple(sorted(rr[1])))
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
            smap, dxn = recs_of(Pd0, Xd0, r0['mat'], f0['xmat'])
            XPs = {tuple(map(tuple, TLT.mparams(load(rr['files'][0]['xbox'], 'be')[(10, rr['files'][0]['xmat'])], 'be'))) for rr in g['rows']}
            XP = TLT.mparams(Xd0[(10, f0['xmat'])], 'be')
            pd = r0['surrogate']
            lg = []
            res = build_group(g['xlib'], pd, smap, dxn, XP, g['lit'], os.path.join(wd, 'b', '%d_%d' % (g['xlib'], r0['mat'])), lg)
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
            while nid in used_ids: nid += 1
            data = pack_lib(res, nid, taken, len(res))
            used_ids.add(nid)
            # apply per file: all group materials present in that file
            perfile = collections.defaultdict(list)
            for rr in g['rows']:
                for f in rr['files']: perfile[f['name']].append((rr['mat'], f['xmat'], f))
            pk = os.path.join(wd, 'p', str(nid)); os.makedirs(pk, exist_ok=True)
            open(os.path.join(pk, '%d.lib' % nid), 'wb').write(data)
            for fname, ms in perfile.items():
                f = ms[0][2]
                dst = tree_dst(tree, f['pc'])
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(f['pc'], dst)
                json.dump({str(g['xlib']): dict(new=nid, mats=[(m, x) for m, x, _ in ms])}, open(os.path.join(pk, 'map.json'), 'w'))
                tmp = dst + '.tmp50m'
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    TU.cmd_apply(dst, f['xbox'], tmp, pk, 2)
                os.replace(tmp, dst); cache.pop(dst, None)
                lg.append('apply %s: %s' % (fname, buf.getvalue().strip().splitlines()[-1]))
            ent.update(status='done', new=nid, files=list(perfile), md5=hashlib.md5(data).hexdigest(),
                       note='%d slots, %.0f s' % (len(res), time.time() - t0)); nd += 1; nid += 1
        except (TP.Fail, F9.Fail, Exception) as e:
            ent['note'] = ('%s: %s' % (type(e).__name__, str(e)))[:200].replace('|', '/')
            ent['files'] = sorted({f['name'] for rr in g['rows'] for f in rr['files']})
            lg = locals().get('lg', [])
        log('%s xlib %d (%s) mats %s -> %s %s' % (ent['status'], g['xlib'], 'lit' if g['lit'] else 'unlit', g['mats'], ent.get('new', '-'), ent.get('note', '')))
        for l in lg: log('     ' + l)
        state['groups'].append(ent); state['next_id'] = nid
        json.dump(state, open(stp, 'w'), indent=1); progress(tree, state)
    log('== end %s: %d translated groups this run' % (time.strftime('%H:%M:%S'), nd))


def cmd_verify(invp, wd, tree):
    """independent re-check on the FINISHED tree files: every material of every done group, in every file copy:
    pass-2 lib == the group's new lib, the lib bytes == the packed lib; lit: Xbox-lit reference (2 seeds, 8 slots);
    unlit: each slot == the Xbox shader with Xbox registers (VM)"""
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
                worst = 1.0
                if good and g['lit']:
                    smap, dxn = recs_of(Pd, Xd, m, f['xmat'])
                    lib = TLT.tu_lib(g['xlib']); names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
                    XP = TLT.mparams(Xd[(10, f['xmat'])], 'be'); PP = TLT.mparams(Pd[(10, m)], 'le')
                    PL = SL.parse(data, 'le'); opts = {'dxn': dxn, 'dxn_full': dxn} if dxn else {}
                    import io, contextlib
                    for k in range(8):
                        T = F9.decode_pc(PL['entries'][PL['slots'][k]]['blob'])
                        xblob = lib['entries'][lib['slots'][k & 1] if lib['slots'][k & 1] != 0xffffffff else lib['slots'][0]]['blob']
                        R_, LX = PX.xref_translate(xblob, F9.xsamp(xblob, names), opts)
                        for seed, rw in ((5, -100.0), (11, 0.3)):
                            with contextlib.redirect_stdout(io.StringIO()):
                                o = TN.compare(R_, LX, T, XP, PP, seed, rw, set(dxn), '')
                            worst = min(worst, o['off'], o['on'])
                elif good:
                    smap, dxn = recs_of(Pd, Xd, m, f['xmat'])
                    lib = TLT.tu_lib(g['xlib']); names = {n: smap[r] for r, n in TLT.xbox_sampler_names(lib).items() if r in smap}
                    XP = TLT.mparams(Xd[(10, f['xmat'])], 'be'); PP = TLT.mparams(Pd[(10, m)], 'le')
                    if [tuple(v) for v in XP] != [tuple(v) for v in PP[:len(XP)]]: worst = 0.0   # PC may keep extra vec4 behind the Xbox ones (unread)
                    PL = SL.parse(data, 'le'); pd = inv[m]['surrogate']; P = libs()['P']
                    pct = F9.pc_ctab(P[pd]['entries'][next(o for o in P[pd]['slots'] if o != 0xffffffff)]['blob'])
                    for k in range(len(PL['slots'])):
                        T = F9.decode_pc(PL['entries'][PL['slots'][k]]['blob'])
                        xblob = lib['entries'][lib['slots'][k & 1] if lib['slots'][k & 1] != 0xffffffff else lib['slots'][0]]['blob']
                        Rx, regs = TU.translate_xregs(xblob, names, dxn)
                        ex = F9.Env(7 + k, XP); ep = F9.Env(7 + k, PP); K = F9.Consts(pct)
                        for nme, r in regs.items():
                            c = next(c for c in XL.parse(xblob).ctab if c['set'] == 2 and c['name'] == nme)
                            for j in range(max(1, c['count'])):
                                pr_ = K.fn(nme, j, c['count'])
                                if pr_ is not None: ep.consts[pr_] = ex.consts[r + j]
                        for j, v in enumerate(PP): ep.consts[100 + j] = np.array(v, np.float32)
                        if 'MaterialParams' in regs:
                            for j, v in enumerate(XP): ex.consts[regs['MaterialParams'] + j] = np.array(v, np.float32)
                        worst = min(worst, TU.vm_cmp(T, Rx, ep, ex, TN.game_dxn_tex(ex.tex, dxn)))
                tot += 1; ok += good and worst >= 0.999
                print('%s mat %5d %-40s lib %s (%s) %s worst %.3f' % ('OK  ' if good and worst >= 0.999 else 'FAIL', m, f['name'], cur,
                      'lit' if g['lit'] else 'unlit', 'bytes ok' if good else 'LIB / BYTES WRONG', worst), flush=True)
    print('SUMMARY verify: %d of %d material copies ok' % (ok, tot))


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
        cmd_run(a[1], a[2], a[3], a[4], int(a[5]), mx, only); return
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
