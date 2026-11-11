r"""Shader decisions inventory (pipeline step "Shaders", plan A1, 2026-11-11, docs Befund-Shader-Inventur-1111.md):
every ShaderLib (type 9) / Material (type 10) section where the installed game's mods differ from the pipeline output,
which install wrote it, which tool + recorded inputs produced it, the decision behind it and whether a tool can redo
that decision from recorded data. Read-only: reads the game's mods folder, backup\tree_* manifests + their before
copies, the pipeline output and the work records; writes only below --out and the decision file.
(tools/shader_inventory.py is a different, older tool: surrogate materials of a mods tree.)

  scan --out DIR [--pipe work/rebuild/pipeline_check_1111] [--costumes work/rebuild/costumes_0913]
       [--gb work/rebuild/pipeline_check_1011_gb] [--game MODS] [--backup ../backup] [--logs ../logs]
      effective pipeline tree = <pipe>/dlc1/mods, <pipe>/dlc2/mods (later wins), dlc_costume_*.drm of the costume packs,
      <gb>/generalbank_build/k12/mods (as tools/own_tree.py assemble; g_pda.drm dropped). MODS = env TRUDLC_GAME_MODS,
      else ../data/pc/mods. For every installed DRM whose md5 differs from the pipeline file: the type 9 / 10
      sections keyed (type, id, occurrence) whose content (data + normalised relocations, as own_tree) differs, and
      the install events of the file (open Install-TruTree installs + Install-TruModFile installs + hand copies,
      tools/own_tree.file_events). Per section: every event that changed it (chain), the last writer (attribution
      as own_tree: fix_missing / changed_differently / section_missing_in_own / added_file_differs / base_differs),
      data md5 of the installed / pipeline / before section, material shader tuple (+0x28, 4 x u32: PS pass 0 / 1 / 2,
      VS). Any name containing "truguard" is skipped and never printed. Writes DIR/scan.json.
  decide --out DIR [--tsv docs/data/shader_decisions.tsv]
      resolves every scanned section against the recorded data (no game bytes are written, only ids, hashes, names):
        * lib files: md5 of every *.lib below the shader work folders (LIB_ROOTS) -> the folder that built it
          (tu_batch WORKDIR/p/<id>/<id>.lib, vsapply / vs = VS libs, shader50l b<xlib> builds, ...)
        * tu_batch state.json groups (STATES): new lib id + md5 of the packed lib -> Xbox lib, materials, tool run
        * nativefix.json (NATIVEFIX): lib ids rewritten (ABS_CONST) + the layers they were read from; the section of
          the pre-image (effective file of those layers) is resolved again
        * apply logs below the work folders: "material M: pass 2 A -> B", "added ShaderLib L ... from F",
          "material M slot k (+0x..): A -> B", "wrote PATH md5 X"
        * the install sources (SOURCES: tool chain, records, evidence per test tree)
      and writes the decision file (one row per section) + DIR/summary.md (counts per class / source / rerun).

Usage (from the repository root):
  set TRUDLC_GAME_MODS=<game>\mods   (or the ../data/pc link)
  ../bin/pyt -t 5400 tools/shader_decisions.py scan --out work/q13_shaderinv_1111/scan
  ../bin/pyt -t 1800 tools/shader_decisions.py decide --out work/q13_shaderinv_1111/scan --tsv docs/data/shader_decisions.tsv
"""
import sys, os, re, json, struct, hashlib, collections, fnmatch, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import own_tree as OT

SHTYPES = (9, 10)
TN = {9: 'shaderlib', 10: 'material'}


def arg(argv, key, default=None):
    return OT.arg(argv, key, default)


hidden = OT.hidden
md5_file = OT.md5_file


# ---------------------------------------------------------------------------------------------------------- sections
_cache = {}


def shsecs(p):
    """{(type, id, n): dict(h, d, size, tup)} of the type 9 / 10 sections of a DRM. h = data + normalised relocations
    (own_tree.sections), d = md5 of the data alone, tup = material shader tuple (4 x u32 LE at +0x28)."""
    if p is None: return None
    key = md5_file(p)
    if key in _cache: return _cache[key]
    import drm, drm_reloc as R
    try:
        raw = drm.cdrm_decode(open(p, 'rb').read(), 'le')
        h, secs = drm.sections_with_data(raw, 'le')
    except Exception as ex:
        _cache[key] = 'ERR %s: %s' % (type(ex).__name__, ex); return _cache[key]
    t0 = {}
    for x in secs:
        if x['type'] == 0: t0[x['i']] = len(t0)
    out, cnt = {}, collections.Counter()
    for s in secs:
        if s['type'] not in SHTYPES: continue
        try:
            r = R.parse(s['reloc'], 'le')
            ext = [((secs[si]['type'], secs[si]['id'] if secs[si]['type'] != 0 else t0[si]), so, do) for si, so, do in r.external]
            rk = repr((r.internal, ext, r.idref, r.idref_a))
        except Exception:
            rk = s['reloc'].hex()
        k0 = (s['type'], s['id']); n = cnt[k0]; cnt[k0] += 1
        d = s['data']
        tup = list(struct.unpack_from('<4I', d, 0x28)) if s['type'] == 10 and len(d) >= 0x38 else None
        out[(s['type'], s['id'], n)] = dict(h=hashlib.md5(d + b'|' + rk.encode()).hexdigest(), d=hashlib.md5(d).hexdigest(),
                                             size=len(d), tup=tup)
    _cache[key] = out
    return out


def skey(sk): return '%d:%d:%d' % tuple(sk)


def pkey(s): return tuple(int(x) for x in s.split(':'))


# -------------------------------------------------------------------------------------------------------------- scan
def pipe_tree(run, costumes, gb):
    """{rel_lower: (rel, path, layer)} - the effective pipeline output (own_tree.layers order, g_pda dropped)"""
    out = {}
    lay = [('dlc1', run + '/dlc1/mods', None), ('dlc2', run + '/dlc2/mods', None)]
    for pk in ('pack1', 'pack2', 'pack20'):
        lay.append(('cost_' + pk, '%s/%s/stage2b/mods' % (costumes, pk), 'dlc_costume_*.drm'))
    lay.append(('generalbank', gb + '/generalbank_build/k12/mods', None))
    for name, d, pat in lay:
        if not os.path.isdir(d): print('pipeline layer missing (skipped): %s %s' % (name, d)); continue
        for k, (rel, p) in OT.walk(d).items():
            if pat and not fnmatch.fnmatch(os.path.basename(rel).lower(), pat): continue
            out[k] = (rel, p, name)
    for rel, why in OT.DROP: out.pop(rel.lower(), None)
    return out, lay


def add_gaps(ev):
    """own_tree.file_events takes an event's 'after' = the next event's before copy. When that copy is not what the
    event installed (its after md5: manifest, else the source file), something else changed the file in between (an
    install that is no longer open, a hand copy): a 'gap' event is put in between, so its changes are not credited to
    the earlier install. The earlier event's after = its source file when that still has the installed md5."""
    out = []
    for i, e in enumerate(ev):
        out.append(e)
        if i + 1 >= len(ev) or not ev[i + 1]['before'] or not e.get('after_md5'): continue
        nb = ev[i + 1]['before']; nm = md5_file(nb)
        if nm == e['after_md5']: continue
        sp = e.get('src_path')
        sp = sp if sp and os.path.isfile(sp) and md5_file(sp) == e['after_md5'] else None
        e['after'] = sp
        out.append(dict(t=ev[i + 1]['t'], name='gap_before_' + ev[i + 1]['name'], source='unrecorded change (file md5 %s)' % nm,
                        before=sp, added=False, after_md5=nm, after=nb, src_path=None))
    return out


def scan(argv):
    outd = arg(argv, '--out')
    run = arg(argv, '--pipe', 'work/rebuild/pipeline_check_1111')
    costumes = arg(argv, '--costumes', 'work/rebuild/costumes_0913')
    gb = arg(argv, '--gb', 'work/rebuild/pipeline_check_1011_gb')
    game_root = arg(argv, '--game', os.environ.get('TRUDLC_GAME_MODS') or '../data/pc/mods')
    backup = arg(argv, '--backup', '../backup')
    logs = arg(argv, '--logs', '../logs')
    if not outd: raise SystemExit('scan: --out DIR missing')
    os.makedirs(outd, exist_ok=True)
    pipe, lay = pipe_tree(run, costumes, gb)
    game = OT.walk(game_root)
    stack = OT.load_stack(backup)
    mods = OT.load_modfile_logs(logs)
    kits = OT.kit_md5s()
    print('pipeline %d files (%s), installed %d files (TruGuard names skipped), open installs %d, single-file installs %d' % (
        len(pipe), run, len(game), len(stack), len(mods)), flush=True)
    files, rows = [], []
    nd = 0
    for k in sorted(game):
        if not k.endswith('.drm'): continue
        rel, gp = game[k]
        pe = pipe.get(k)
        im = md5_file(gp); pm = md5_file(pe[1]) if pe else None
        if im == pm: continue
        sg = shsecs(gp); sp = shsecs(pe[1]) if pe else {}
        if isinstance(sg, str) or isinstance(sp, str):
            files.append(dict(rel=rel, err=sg if isinstance(sg, str) else sp)); continue
        diff = sorted(x for x in set(sg) | set(sp) if (sg.get(x) or {}).get('h') != (sp.get(x) or {}).get('h'))
        if not diff: continue
        nd += 1
        ev = add_gaps(OT.file_events(k, rel, stack, mods, backup, gp, im))
        vers = []
        for e in ev:
            sb = shsecs(e['before']) if e['before'] else ({} if e['added'] else None)
            sa = shsecs(e['after']) if e['after'] else None
            vers.append((e, sb, sa))
        base_path = next((e['before'] for e in ev if e['before']), None) if ev else gp
        base_md5 = md5_file(base_path) if base_path else '-'
        kit = '-'
        if base_path:
            kn = kits.get((k, base_md5)) or kits.get((k, 'raw:' + (OT.raw_md5(base_path) or '-')))
            if kn: kit = '/'.join(sorted(set(kn)))
        files.append(dict(rel=rel, inst_md5=im, pipe_md5=pm or '-', pipe_layer=pe[2] if pe else '-',
                          events=[dict(name=e['name'], source=e['source'], t=e['t'], added=e['added'], after_md5=e.get('after_md5'),
                                       before_md5=md5_file(e['before']) if e['before'] else None) for e in ev],
                          base_md5=base_md5, base_kit=kit, ndiff=len(diff)))
        for sk in diff:
            gi, pi = sg.get(sk), sp.get(sk)
            chain = []
            for e, sb, sa in vers:
                if sa is None or isinstance(sa, str) or sb is None or isinstance(sb, str): continue
                if (sb.get(sk) or {}).get('h') != (sa.get(sk) or {}).get('h'): chain.append(e['name'])
            who, src, state, bef = 'base', '-', 'base_differs', None
            for e, sb, sa in reversed(vers):
                if sa is None or isinstance(sa, str) or isinstance(sb, str): continue
                if sb is None:
                    if (sa.get(sk) or {}).get('h') == (gi or {}).get('h') and e is vers[-1][0]:
                        who, src, state = e['name'], e['source'], 'no_before'
                        break
                    continue
                if (sb.get(sk) or {}).get('h') != (sa.get(sk) or {}).get('h') and (sa.get(sk) or {}).get('h') == (gi or {}).get('h'):
                    who, src = e['name'], e['source']
                    bef = 'added' if e['added'] else sb.get(sk)
                    break
            if who != 'base' and state != 'no_before':
                oh = (pi or {}).get('h')
                if bef == 'added': state = 'added_file_differs'
                elif oh == (bef or {}).get('h'): state = 'fix_missing'
                elif oh is None: state = 'section_missing_in_own'
                else: state = 'changed_differently'
            pres = 'both' if gi and pi else ('inst_only' if gi else 'pipe_only')
            rows.append(dict(rel=rel, sec=skey(sk), type=TN[sk[0]], pres=pres, last=who, last_src=src, state=state,
                             chain=chain, inst=gi, pipe=pi, before=bef if isinstance(bef, dict) else None))
        if nd % 10 == 0: print('  %d files with shader differences, %d sections so far' % (nd, len(rows)), flush=True)
    # pipeline DRMs that are not installed at all (never played): counted only
    notinst = sorted(rel for k, (rel, p, l) in pipe.items() if k.endswith('.drm') and k not in game)
    json.dump(dict(pipe=run, layers=[(n, d) for n, d, _ in lay], game=game_root.replace('\\', '/'), files=files, rows=rows,
                   pipe_not_installed=notinst, open_installs=[s['name'] for s in stack]),
              open(os.path.join(outd, 'scan.json'), 'w', encoding='utf-8'), indent=0)
    c = collections.Counter((r['type'], r['pres'], r['last'], r['state']) for r in rows)
    for kk, n in sorted(c.items(), key=lambda x: -x[1]): print('%5d  %s' % (n, ' '.join(kk)))
    print('%d sections in %d files; pipeline DRMs not installed: %d; wrote %s' % (len(rows), nd, len(notinst), os.path.join(outd, 'scan.json')))


# ------------------------------------------------------------------------------------------------------------ records
# tu_batch WORKDIRs (state.json: done groups with Xbox lib, materials, new lib id, md5 of the packed lib)
STATES = ['work/n6b_0811/tb', 'work/n6b_0811/tb_layers', 'work/n6shaders_0711/tb', 'work/n5mats_0711/tb', 'work/n5b_0711/tb',
          'work/floor_0811/tb', 'work/q17q_0811/tb', 'work/shader17c_0811/tb', 'work/sg_audit_0511/run51x',
          'work/rebuild/shader50m_work/run', 'work/rebuild/shader50n_work/run', 'work/rebuild/shader50o_work/run',
          'work/rebuild/shader50o_work/retry']
# folders whose *.lib files are built shader libraries (md5 of the file = section data of the lib it became)
LIB_ROOTS = ['work/n6b_0811', 'work/n6shaders_0711', 'work/n5mats_0711', 'work/n5b_0711', 'work/floor_0811', 'work/q17q_0811',
             'work/shader17c_0811', 'work/sg_audit_0511/run51x', 'work/endcolumn_0711', 'work/rebuild/shader50l_work',
             'work/rebuild/shader50m_work', 'work/rebuild/shader50n_work', 'work/rebuild/shader50o_work',
             'work/rebuild/test48g_work', 'work/rebuild/test50a_work', 'work/rebuild/test50c_work',
             'work/rebuild/test46_shader_work', 'work/rebuild/test50l_look_work', 'work/rebuild/test50l_work',
             'work/rebuild/arms_work']
# nativefix records (17r / 17z): lib ids rewritten (ABS_CONST) and the layers the files were read from
NATIVEFIX = ['work/clean17z_0811/n6b', 'work/clean17z_0811/b270cmp', 'work/clean17z_0811/dopp17m', 'work/clean17z_0811/crash17m',
             'work/clean17z_0811/installed_rest', 'work/amd17r_0811/tree', 'work/amd17r_0811/v1_1135/tree']
# text logs with apply lines (material / lib changes, written files)
LOG_ROOTS = LIB_ROOTS + ['work/clean17z_0811', 'work/b270cmp_0811', 'work/amd17r_0811', 'work/rebuild/dlc_test50l_merged',
                         'work/regress_1111']

# install sources (Install-TruTree / Install-TruModFile) -> how the tree was made (evidence = the folder's PROGRESS /
# logs / docs; read 11.11.). tools = repo tools in build order; pre = mods folders the last tool read; rerun = whether a
# repo tool can redo the tree's decisions from recorded data, with what is missing.
SOURCES = {
    'work/clean17z_0811/n6b/mods': dict(
        tools='tu_batch inv/run (+tu_vs vsapply, n6b rebuild_layers) -> tu_batch nativefix',
        records='work/n6b_0811/tb/state.json; work/n6b_0811/tb_layers/state.json; work/n6b_0811/vs_plan.json; work/n6b_0811/inv.json; '
                'work/n6b_0811/tuples_final.tsv; work/n6b_0811/id_map.txt; work/clean17z_0811/n6b/nativefix.json',
        pre='work/n6b_0811/testtree/mods', evidence='work/n6b_0811/PROGRESS.md; work/clean17z_0811/PROGRESS.md 14:39',
        note='stack: installed -> n5mats_0711/testtree -> n6b; nativefix rewrote 44 libs (ABS_CONST) in 26 of 58 files'),
    'work/clean17z_0811/b270cmp/mods': dict(
        tools='b270cmp_0811 build_tree.py (work one-off: B270 kit comparison, words / sections taken from B270) -> tu_batch nativefix',
        records='work/b270cmp_0811/build_tree.txt; work/b270cmp_0811/final_words.tsv; work/clean17z_0811/b270cmp/nativefix.json',
        pre='work/b270cmp_0811/tree/mods', evidence='work/b270cmp_0811/PROGRESS.md; work/clean17z_0811/PROGRESS.md 14:36',
        note='builder is a work one-off reading the B270 kit (kit-derived)'),
    'work/clean17z_0811/rest10/mods': dict(
        tools='tu_batch nativefix (amd17r step 10, on the installed folder)', records='work/amd17r_0811/tree/nativefix.json',
        pre=None, evidence='work/clean17z_0811/PROGRESS.md 14:42 (rest10 = byte copies of amd17r step 10)',
        note='2 files, libs 2824 / 2827; pre-image = the installed copy of 03.11. / 07.11.'),
    'work/q17q_0811/tree20265/mods': dict(
        tools='q17q build20265.py (work one-off: record fix -> tu_batch build_group -> pack -> tu_unlit apply -> lane fix -> VS 3091)',
        records='work/q17q_0811/tb/state.json; work/q17q_0811/tuples.tsv; work/q17q_0811/build20265.txt; work/q17q_0811/rec20265.txt',
        pre=None, evidence='work/q17q_0811/PROGRESS.md 08:45', note='material 20265 in 9 streamgroups; PS 3534 / VS 3091'),
    'work/endcolumn_0711/testtree/mods': dict(
        tools='tu_unlit / column_shader_translate apply + lib copy (endcolumn_0711 step1)', records='work/endcolumn_0711/build_log.txt',
        pre=None, evidence='work/endcolumn_0711/build_log.txt; lib_vs_report.txt', note='material 23164 (end column) pass 2 / VS'),
    'work/rebuild/dlc_test50l_merged/mods': dict(
        tools='50l / 50m / 50n merge: tu_perlight build, tu_unlit apply, tu_batch run (50m / 50n), look plan (test50l_look_work)',
        records='work/rebuild/shader50l_work/*/plan.json + apply_*.txt; work/rebuild/shader50m_work/run/state.json; '
                'work/rebuild/shader50n_work/run/state.json; work/rebuild/dlc_test50l_merged/md5_50l_merged.txt',
        pre=None, evidence='CHANGELOG 2026-11-03 (test trees 50l / 50m / 50n); docs Befund-Regression-Stapel-1111.md',
        note='merge recipe of the tree itself not recorded (only md5_50l_merged.txt)'),
    'work/rebuild/dlc_test50l_shaders_dlc1/mods': dict(
        tools='tu_perlight build + tu_unlit apply (shader50l_work/enemy)', records='work/rebuild/shader50l_work/enemy/apply_*.txt; build_*.txt',
        pre=None, evidence='work/rebuild/shader50l_work/enemy', note='DLC 1 knight thralls'),
    'work/rebuild/dlc_test46_column_shader/mods': dict(
        tools='column_shader_translate (test 46)', records='work/rebuild/test46_shader_work', pre=None,
        evidence='CHANGELOG 2026-10-31 (test 46, played)', note='waterfall column, dlc_level2_start'),
    'work/rebuild/dlc_test48f/mods/doppelganger_casual.drm': dict(
        tools='ps_odd_slots (slot fill of empty odd fade slots, 33 base-id libs)', records='docs Befund-Felsrinne.md "Test 48e / 48f" (command + md5 e5d1b982)',
        pre='work/rebuild/dlc_test48e/mods', evidence='docs Befund-Felsrinne.md test 48f / 48g',
        note='48g live: the engine keeps the base game copy of a base-id lib -> the patched copy is ignored (no effect)'),
    'work/rebuild/play_20261030b/mods': dict(
        tools='merge of DLC 2 test trees (merge_manifest.json) incl. ring rule 16637 + 1704-1707 (material_copy)',
        records='work/rebuild/play_20261030b/merge_manifest.json', pre=None,
        evidence='docs Befund-Regression-Stapel-1111.md (ring rule, tests 22 / 24 / 26a); tools/rule_owned.py', note=''),
    'copied by hand (no install record)': dict(
        tools='hand copy of the Repair ring files (rule_owned register)', records='tools/rule_owned.py (register, N3 00e326c)', pre=None,
        evidence='docs Befund-Regression-Stapel-1111.md', note='= work/rebuild/b138_fixes ring (Repair)'),
}


# reference trees for libs no build record explains (read only, never assembled): the B138 kit as unpacked, the
# Repair tree (B138 + our fixes), the B270 kit, the B138 shader fix tree
KIT_REFS = [('B138', 'work/rebuild/b138_pristine/mods'), ('Repair', 'work/rebuild/pipeline_check_1011_repair/b138_fixes/mods'),
            ('B270', 'work/b270_kit/mods'), ('b138_shaderfix', 'work/rebuild/b138_shaderfix/out')]
SLOTFILL_SRC = 'work/rebuild/dlc_test48f/mods/doppelganger_casual.drm'


def kit_ref(rel, sk, d):
    """names of the reference trees whose copy of rel has section sk with data md5 d"""
    hits = []
    for name, root in KIT_REFS:
        for q in (os.path.join(root, rel.replace('/', os.sep)), os.path.join(root, os.path.basename(rel))):
            if os.path.isfile(q):
                s = shsecs(q)
                if isinstance(s, dict) and (s.get(sk) or {}).get('d') == d: hits.append(name)
                break
    return hits


_inv_cache = {}


def xbox_inputs_ok(inv, mats):
    """do the Xbox DRMs the tu_batch inventory names for these materials still exist"""
    if inv in ('-', 'rebuild_layers') or not os.path.isfile(inv): return None
    if inv not in _inv_cache:
        _inv_cache[inv] = {e['mat']: [f.get('xbox') for f in e.get('files', [])] for e in json.load(open(inv, encoding='utf-8-sig'))}
    xs = [x for m in mats for x in _inv_cache[inv].get(m, []) if x]
    return bool(xs) and all(os.path.isfile(x) for x in xs)


def tracked(path):
    """is a repo file tracked by git (no git call: reads the index list once)"""
    global _tracked
    if _tracked is None:
        import subprocess
        try: _tracked = set(subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True).stdout.splitlines())
        except Exception: _tracked = set()
    return path in _tracked


_tracked = None
RX = [('mat', re.compile(r'material (\d+): p(?:ass )?2 (\d+) -> (\d+)')),
      ('vs', re.compile(r'VS (\d+) -> (\d+) for materials \[([\d, ]+)\]')),
      ('slot', re.compile(r'material (\d+) slot (\d) \(\+0x[0-9a-f]+\): (\d+) -> (\d+)')),
      ('add', re.compile(r'added ShaderLib (\d+) \((\d+) bytes\) from (\S+)')),
      ('new', re.compile(r'new ShaderLibs \[([\d, ]+)\]')),
      ('wrote', re.compile(r'wrote (\S+) md5 ([0-9a-f]{32})'))]


def walk_files(roots, exts, maxsize=None):
    for r in roots:
        if not os.path.isdir(r): continue
        for dp, dn, fn in os.walk(r):
            dn[:] = sorted(d for d in dn if not hidden(d) and d not in ('__pycache__', 'mods', 'native', 'xbox'))
            for f in sorted(fn):
                if hidden(f) or not f.lower().endswith(exts): continue
                p = os.path.join(dp, f)
                if maxsize and os.path.getsize(p) > maxsize: continue
                yield p.replace('\\', '/')


def load_records():
    R = dict(states={}, state_md5=collections.defaultdict(list), state_id=collections.defaultdict(list), libfile=collections.defaultdict(list),
             nf={}, nf_id=collections.defaultdict(list), log=collections.defaultdict(list))
    for wd in STATES:
        sp = os.path.join(wd, 'state.json')
        if not os.path.isfile(sp): continue
        st = json.load(open(sp, encoding='utf-8-sig')); R['states'][wd] = st
        for g in st['groups']:
            if g.get('status') != 'done' or g.get('new') is None: continue
            e = dict(wd=wd, xlib=g['xlib'], mats=g['mats'], new=g['new'], lit=g.get('lit'), inv=st.get('inv', '-'),
                     lib=os.path.join(wd, 'p', str(g['new']), '%d.lib' % g['new']).replace('\\', '/'), old=g.get('old'))
            if g.get('md5'): R['state_md5'][g['md5']].append(e)
            R['state_id'][g['new']].append(e)
    for p in walk_files(LIB_ROOTS, ('.lib',)):
        R['libfile'][md5_file(p)].append(p)
    for d in NATIVEFIX:
        jp = os.path.join(d, 'nativefix.json')
        if not os.path.isfile(jp): continue
        j = json.load(open(jp, encoding='utf-8-sig')); R['nf'][d] = j
        for lid in j.get('libs', {}): R['nf_id'][int(lid)].append(d)
    for p in walk_files(LOG_ROOTS, ('.txt', '.log'), 8 << 20):
        try: txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError: continue
        if not any(w in txt for w in ('-> ', 'ShaderLib', 'wrote ')): continue
        for ln in txt.splitlines():
            for kind, rx in RX:
                for m in rx.finditer(ln):
                    R['log'][kind].append((p, m.groups(), ln.strip()[:160]))
    return R


def log_index(R):
    I = dict(mat=collections.defaultdict(list), vs=collections.defaultdict(list), slot=collections.defaultdict(list),
             add=collections.defaultdict(list), wrote=collections.defaultdict(list))
    for p, g, ln in R['log']['mat']: I['mat'][(int(g[0]), int(g[2]))].append((p, int(g[1])))
    for p, g, ln in R['log']['vs']:
        for m in g[2].replace(' ', '').split(','):
            if m: I['vs'][(int(m), int(g[1]))].append((p, int(g[0])))
    for p, g, ln in R['log']['slot']: I['slot'][(int(g[0]), int(g[3]))].append((p, int(g[1]), int(g[2])))
    for p, g, ln in R['log']['add']: I['add'][int(g[0])].append((p, g[2]))
    for p, g, ln in R['log']['wrote']: I['wrote'][g[1]].append((p, g[0]))
    return I


def eff_file(layers, rel):
    """effective copy of rel in a stack of mods folders (last wins); the game folder of a record is not used (it has
    changed since) -> None for it"""
    hit = None
    for L in layers:
        if os.path.normpath(L).replace('\\', '/').lower().replace(' ', '').endswith('tombraiderunderworld/mods'): continue
        q = os.path.join(L, rel.replace('/', os.sep))
        if os.path.isfile(q): hit = q
    return hit


def roots_of(src):
    """work folders named in a SOURCES entry (the tree's own lineage) - preferred when several records hold the same
    lib bytes"""
    si = SOURCES.get(src) or {}
    txt = ' '.join(str(si.get(k) or '') for k in ('tools', 'records', 'pre', 'evidence')) + ' ' + (src or '')
    return set(re.findall(r'work/(?:rebuild/)?[A-Za-z0-9_\-]+', txt))


def lib_origin(R, d, prefer=()):
    """what built a lib whose section data has md5 d: ('tu_batch', group) / ('libfile', path) / None; with several
    records of the same bytes the one below a preferred root wins, then the alphabetically first"""
    rank = lambda p: (0 if any(p.startswith(r + '/') or p == r for r in prefer) else 1, p)
    if d in R['state_md5']:
        g = sorted(R['state_md5'][d], key=lambda e: rank(e['wd']))[0]
        return 'tu_batch', g
    if d in R['libfile']:
        return 'libfile', sorted(R['libfile'][d], key=rank)[0]
    return None


def libfile_kind(p):
    """class + tool of a built lib file by the folder that holds it (folders read 11.11.: PROGRESS / build logs)"""
    q = p.lower()
    if '/vsapply/' in q or '/vs/' in q or '/apply_vs/' in q or '/pv/' in q or os.path.basename(q).startswith('vs_'):
        return 'L_VS', 'tu_vs vsapply (translated vertex shader lib, %s)' % q.split('/')[1 if q.split('/')[1] != 'rebuild' else 2]
    if 'shader50l_work' in q: return 'L_50L', 'tu_perlight / tu_unlit build (test 50l)'
    if 'test48g_work' in q: return 'L_FADE', 'fade_slots_translate (test 48g)'
    if 'test46_shader_work' in q: return 'L_COLUMN', 'column_shader_translate (test 46)'
    if 'test50l_look_work' in q: return 'L_LOOK', 'look shader plan (test 50l look)'
    if 'n5b_0711/recheck' in q: return 'L_N5B', 'n5b recheck build (tu_batch / tu_vs, work/n5b_0711)'
    if 'test50a_work' in q or 'test50c_work' in q or 'arms_work' in q:
        return 'L_TEST50', 'tests 50a-50h: doppelganger look / rock vein strip (tu_perlight / tu_unlit packs, %s)' % q.split('/rebuild/')[-1].split('/')[0]
    if '/p/' in q: return 'L_TU', 'tu_batch run (packed lib)'
    return 'L_FILE', 'lib file %s' % p


def resolve_lib(R, I, row, chain_src, scan_rel):
    """decision for a ShaderLib row -> dict(cls, decision, tool, record, xlib)"""
    import rule_owned as RO
    sk = pkey(row['sec']); lid = sk[1]
    inst = row['inst']
    out = dict(cls='', decision='', tool='-', record='-', xlib='-', mats='-', nf='-')
    base = row['last'] == 'base'
    if inst is None:
        out.update(cls='K_PIPE_LIB' if base else 'L_PIPE_ONLY',
                   decision='lib %d only in the pipeline output (installed %s lacks it)' % (lid, 'kit state' if base else 'file')); return out
    bn = os.path.basename(scan_rel).lower()
    if lid in RO.owned_libs().get(bn, set()):
        out.update(cls='RULE_RING', decision='lib %d = base ring lib of %s (rule ring: base material %d + libs %s)' % (
            lid, RO.BASE_RING, RO.BASE_MATERIAL, '-'.join(map(str, (RO.BASE_LIBS[0], RO.BASE_LIBS[-1])))),
            tool='b138_fix_tree step ring / rule_owned apply', record='tools/rule_owned.py RULES')
        return out
    if row['last_src'] == SLOTFILL_SRC:
        o = lib_origin(R, inst['d'])
        out.update(cls='L_SLOTFILL', decision='lib %d (base id): empty odd fade slots point at slot - 1 (ps_odd_slots, 48f)%s' % (
            lid, '; same bytes as %s' % o[1] if o and o[0] == 'libfile' else ''),
            tool='ps_odd_slots', record='docs Befund-Felsrinne.md test 48f')
        return out
    prefer = roots_of(row['last_src'])
    o = lib_origin(R, inst['d'], prefer)
    nfrec = None
    if o is None:
        # rewritten by nativefix? pre-image = the effective file of the record's layers, else the section before the
        # last install (the record read the then installed folder)
        for d in R['nf_id'].get(lid, []):
            j = R['nf'][d]
            pre = eff_file(j['layers'], scan_rel)
            ps = shsecs(pre) if pre else None
            pf = prefer | set(re.findall(r'work/(?:rebuild/)?[A-Za-z0-9_\-]+', ' '.join(j['layers'])))
            if isinstance(ps, dict) and sk in ps and ps[sk]['d'] != inst['d']:
                o2 = lib_origin(R, ps[sk]['d'], pf)
                nfrec = d
                o = o2 if o2 else ('pre', pre.replace('\\', '/'))
                break
            if pre is None and row.get('before') and row['before']['d'] != inst['d']:
                o2 = lib_origin(R, row['before']['d'], pf)
                nfrec = d
                o = o2 if o2 else ('pre', 'the section before %s' % row['last'])
                break
    if o is None:
        refs = kit_ref(scan_rel, sk, inst['d'])
        if refs:
            k = 'K_KIT_LIB' if base else 'L_KIT_LIB'
            kit = 'B138' in refs or 'B270' in refs
            out.update(cls=k, decision='lib %d = %s (same bytes in %s)%s' % (
                lid, 'the kit lib' if kit else 'the B138 lib after shader_const_fix (Repair step shaders, WINDOWS_REBUILD 2026-10-29)',
                ' / '.join(refs), '' if base else '; brought in by %s' % row['last_src']),
                tool='kit (not our tool)' if kit else 'b138_fix_tree step shaders (shader_const_fix) on the B138 lib', record=' / '.join(refs))
            return out
        if lid in I['add']:
            p, src = I['add'][lid][0]
            out.update(cls='L_COPY', decision='lib %d copied from %s' % (lid, src), tool='lib copy (apply log)', record=p); return out
        out.update(cls='K_UNKNOWN_LIB' if base else 'L_UNRESOLVED', decision='lib %d: no recorded build found (data md5 %s)' % (lid, inst['d'][:12]))
        return out
    kind, x = o
    if kind == 'tu_batch':
        cls = 'L_TU' if x['wd'] != 'work/n6b_0811/tb_layers' else 'L_TU_LAYER'
        out.update(cls=cls, decision='lib %d = tu_batch group: Xbox lib %d -> %d (%s, materials %s)' % (
            lid, x['xlib'], x['new'], 'lit' if x['lit'] else 'unlit', ' '.join(str(m) for m in x['mats'])),
            tool='tu_batch run' if cls == 'L_TU' else 'n6b rebuild_layers (tu_batch group on a lower layer)',
            record=x['wd'] + '/state.json', xlib=str(x['xlib']), mats=' '.join(str(m) for m in x['mats']),
            xok=xbox_inputs_ok(x['inv'], x['mats']))
        if x['new'] != lid: out['decision'] += ' [id %d in the record, %d installed]' % (x['new'], lid)
    elif kind == 'libfile':
        cls, tool = libfile_kind(x)
        xl = re.search(r'/b(\d{4})[a-z]?/', x)
        xlib, mats = (xl.group(1) if xl else '-'), '-'
        mp = os.path.join(os.path.dirname(x), 'map.json')       # tu_unlit apply map next to the lib: {xlib: {new, mats, ...}}
        if os.path.isfile(mp):
            try:
                for k, v in json.load(open(mp, encoding='utf-8-sig')).items():
                    if isinstance(v, dict) and (v.get('md5') == (inst['d'] if not nfrec else None) or
                                                os.path.basename(x) == '%s.lib' % v.get('new')):
                        xlib = k; mats = ' '.join(str(m[0] if isinstance(m, list) else m) for m in v.get('mats', []))
                        break
            except (ValueError, OSError):
                pass
        out.update(cls=cls, decision='lib %d = built lib file %s%s' % (lid, x, '' if xlib == '-' else ' (Xbox lib %s, materials %s)' % (xlib, mats)),
                   tool=tool, record=x, xlib=xlib, mats=mats)
    else:
        out.update(cls='L_PRE', decision='lib %d: before nativefix = the section of %s (no build record)' % (lid, x), tool='-', record=x)
    if nfrec:
        out['cls'] += '+NF'; out['nf'] = nfrec + '/nativefix.json'
        out['decision'] += '; ABS_CONST rewritten by tu_batch nativefix (%s)' % nfrec
        out['tool'] += ' -> tu_batch nativefix'
    return out


def resolve_mat(R, I, row, libres):
    """decision for a Material row; libres = {(file_lower, lib id): lib decision} of the scan"""
    import rule_owned as RO
    sk = pkey(row['sec']); mid = sk[1]
    gi, pi = row['inst'], row['pipe']
    out = dict(cls='', decision='', tool='-', record='-', xlib='-', mats=str(mid), nf='-')
    base = row['last'] == 'base'
    if gi is None:
        out.update(cls='M_PIPE_ONLY', decision='material %d only in the pipeline output' % mid); return out
    if pi is None:
        out.update(cls='K_INST_MAT' if base else 'M_INST_ONLY', decision='material %d only in the installed file (tuple %s)' % (
            mid, '/'.join(map(str, gi['tup'] or [])))); return out
    if mid in RO.owned_materials().get(os.path.basename(row['rel']).lower(), set()):
        out.update(cls='RULE_RING', decision='material %d = base ring material %d of %s with libs %s (rule ring); pipeline tuple %s' % (
            mid, RO.BASE_MATERIAL, RO.BASE_RING, '/'.join(map(str, gi['tup'] or [])), '/'.join(map(str, pi['tup'] or []))),
            tool='b138_fix_tree step ring / rule_owned apply', record='tools/rule_owned.py RULES')
        return out
    I_, P_ = gi['tup'] or [0] * 4, pi['tup'] or [0] * 4
    ch = [k for k in range(4) if I_[k] != P_[k]]
    names = ('PS0', 'PS1', 'PS2', 'VS')
    if not ch:
        sz = '' if gi['size'] == pi['size'] else ' (size %d -> %d)' % (pi['size'], gi['size'])
        hit = I['mat'].get((mid, I_[2]))
        out.update(cls='K_MAT_PARAMS' if base else 'M_PARAMS', decision='material %d: same shader tuple %s, other bytes differ%s (params / sampler records)' % (
            mid, '/'.join(map(str, I_)), sz))
        if hit: out.update(tool='tu_unlit apply (params = Xbox)', record=hit[0][0])
        return out
    parts, classes, tools, recs, xl = [], [], [], [], []
    for k in ch:
        L = I_[k]
        lr = libres.get((row['rel'].lower(), L))
        how = lr['cls'] if lr else 'lib not differing in the file (same in both, or a base-game lib)'
        if lr and lr['xlib'] != '-': xl.append(lr['xlib'])
        parts.append('%s %d -> %d (%s)' % (names[k], P_[k], L, how))
        classes.append(how.split('+')[0] if lr else 'L_SAME')
        if lr: tools.append(lr['tool']); recs.append(lr['record'])
        lg = I['mat'].get((mid, L)) if k == 2 else (I['vs'].get((mid, L)) if k == 3 else None)
        lg = lg or I['slot'].get((mid, L))
        if lg: recs.append(lg[0][0])
    sz = '' if gi['size'] == pi['size'] else '; size %d -> %d' % (pi['size'], gi['size'])
    cl = ('K_MAT_LIB_' if base else 'M_LIB_') + '_'.join(sorted(set(c.split('_', 1)[1] for c in classes)))
    out.update(cls=cl, decision='material %d: %s%s' % (mid, '; '.join(parts), sz),
               tool=' / '.join(sorted(set(tools))) or '-', record=' ; '.join(sorted(set(recs))) or '-', xlib=' '.join(sorted(set(xl))) or '-')
    return out


def rerun_of(row, res, src_info, R):
    """yes / partial / no + what is missing for redoing the decision from recorded data with repo tools"""
    cls = res['cls']
    if cls == 'F_NOT_IN_PIPE':
        return 'n/a', 'file not in the pipeline at all (%s)' % row['file_not_in_pipe']
    if cls.startswith('K_'):
        if cls == 'K_PIPE_LIB': return 'n/a', 'our pipeline lib, the kit state has none (A2 decides: keep ours or translate)'
        return 'no', 'kit state (B138 / B270 bytes), not made by our tools - kit-free only by an own translation'
    if cls.startswith(('L_PIPE_ONLY', 'M_PIPE_ONLY')):
        return 'n/a', 'pipeline-only section: the installed stack removed / never had it'
    miss = []
    tool_ok = True
    t = res['tool'] + ' ' + (src_info or {}).get('tools', '')
    for name in ('tu_batch', 'tu_unlit', 'tu_perlight', 'tu_vs', 'column_shader_translate', 'ps_odd_slots', 'fade_slots_translate', 'rule_owned'):
        if name in t and not tracked('tools/%s.py' % name): tool_ok = False; miss.append('tools/%s.py not tracked' % name)
    if 'one-off' in (src_info or {}).get('tools', ''): miss.append('builder is a work one-off script, not a repo tool')
    if cls.startswith(('L_UNRESOLVED', 'L_PRE')) or 'UNRESOLVED' in cls: miss.append('no build record for the lib bytes')
    if cls.startswith('L_KIT_LIB') or 'KIT_LIB' in cls: miss.append('kit-derived lib (B138 bytes + Repair step shaders) - needs an own translation')
    if '+NF' in cls or res['nf'] != '-':
        miss.append('nativefix entry hashes are salted against the hashes taken in the stack (clean17z 14:42): same code, other hashes on another stack')
    if cls.startswith('M_PARAMS') and res['record'] == '-': miss.append('no log line for the parameter / record change')
    if cls.startswith('M_INST_ONLY'): miss.append('material only in a test-tree file')
    if cls.startswith('L_TU') and res.get('xok') is False: miss.append('Xbox input DRM of the tu_batch inventory is gone')
    recs = [r.strip().split(' ')[0] for r in res['record'].split(';') if r.strip()]
    if res['record'] != '-' and not all(os.path.exists(r) for r in recs if r.startswith('work/') or r.startswith('tools/')):
        miss.append('a record file is gone')
    if src_info is None: miss.append('install source not in the SOURCES table')
    if row['last_src'] == SLOTFILL_SRC:
        miss.append('decision has no game effect (48g live: a base-id lib, the engine keeps the base game copy)')
    if row.get('file_not_in_pipe'): miss.append('file not in the pipeline at all (%s)' % row['file_not_in_pipe'])
    soft = ('nativefix', 'decision has no', 'file not in the pipeline')
    hardfail = ('no build record', 'install source', 'a record file', 'kit-derived', 'Xbox input')
    if not tool_ok or any(m.startswith(hardfail) for m in miss):
        return 'no', '; '.join(miss)
    if miss: return 'partial', '; '.join(miss)
    return 'yes', '-'


def decide(argv):
    outd = arg(argv, '--out')
    tsv = arg(argv, '--tsv', 'docs/data/shader_decisions.tsv')
    S = json.load(open(os.path.join(outd, 'scan.json'), encoding='utf-8'))
    R = load_records(); I = log_index(R)
    print('records: %d tu_batch states (%d done groups), %d lib files, %d nativefix records, log lines %s' % (
        len(R['states']), sum(len(v) for v in R['state_id'].values()), sum(len(v) for v in R['libfile'].values()), len(R['nf']),
        dict((k, len(v)) for k, v in R['log'].items())), flush=True)
    libres = {}
    out = []
    rows = S['rows']
    notpipe = {f['rel'] for f in S['files'] if f.get('pipe_md5') == '-'}
    gaps = collections.Counter()
    for r in rows:
        if r['rel'] in notpipe: r['file_not_in_pipe'] = 'only installed: ' + (r['last_src'] if r['last'] != 'base' else 'kit')
        if r['last'].startswith('gap_'):
            m = re.search(r'[0-9a-f]{32}', r['last_src'])
            hit = sorted(I['wrote'].get(m.group(0), [])) if m else []
            if hit:
                r['gap_src'] = dict(tools='unrecorded install of %s (apply log %s)' % (hit[0][1], hit[0][0]), records=hit[0][0])
                r['last_src'] = 'unrecorded: ' + hit[0][1]
            gaps[(r['last'], r['last_src'])] += 1
    for (g, s), n in sorted(gaps.items()): print('gap event %s: %s (%d sections)' % (g, s, n))
    for r in rows:
        if r['type'] != 'shaderlib': continue
        res = resolve_lib(R, I, r, r['last_src'], r['rel'])
        libres[(r['rel'].lower(), pkey(r['sec'])[1])] = res
        out.append((r, res))
    for r in rows:
        if r['type'] != 'material': continue
        out.append((r, resolve_mat(R, I, r, libres)))
    for r, res in out:
        if r.get('file_not_in_pipe'):
            res.update(cls='F_NOT_IN_PIPE', decision='%s - the whole file is not a pipeline output (%s); %s' % (
                res['cls'], r['file_not_in_pipe'], res['decision']))
    out.sort(key=lambda x: (x[0]['rel'].lower(), pkey(x[0]['sec'])))
    cols = ['rel', 'type', 'sec_id', 'occ', 'presence', 'last_install', 'install_source', 'chain', 'attribution', 'decision_class',
            'decision', 'xbox_lib', 'tool', 'record', 'nativefix', 'rerun', 'missing', 'inst_md5', 'pipe_md5', 'before_md5',
            'inst_tuple', 'pipe_tuple']
    lines = ['\t'.join(cols)]
    stat = collections.Counter(); by_src = collections.Counter(); by_rerun = collections.Counter()
    files = set()
    for r, res in out:
        sk = pkey(r['sec'])
        si = (r.get('gap_src') or SOURCES.get(r['last_src'])) if r['last'] != 'base' else None
        rr, miss = rerun_of(r, res, si, R)
        tup = lambda x: '/'.join(map(str, x['tup'])) if x and x.get('tup') else '-'
        vals = [r['rel'], r['type'], str(sk[1]), str(sk[2]), r['pres'], r['last'], r['last_src'], ','.join(c.replace('tree_', '') for c in r['chain']) or '-',
                r['state'], res['cls'], res['decision'], res['xlib'], res['tool'], res['record'], res['nf'], rr, miss,
                (r['inst'] or {}).get('d', '-'), (r['pipe'] or {}).get('d', '-'), (r['before'] or {}).get('d', '-'), tup(r['inst']), tup(r['pipe'])]
        lines.append('\t'.join(v.replace('\t', ' ') for v in vals))
        stat[(r['type'], res['cls'])] += 1; by_src[(r['last'], r['last_src'], r['type'])] += 1; by_rerun[(rr, res['cls'])] += 1
        files.add(r['rel'])
    os.makedirs(os.path.dirname(tsv) or '.', exist_ok=True)
    open(tsv, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    L = ['# Shader decisions (tools/shader_decisions.py decide)', '',
         'pipeline `%s`, installed `%s`; %d sections in %d files; pipeline DRMs not installed: %d' % (
             S['pipe'], S['game'], len(out), len(files), len(S['pipe_not_installed'])), '',
         '## Per decision class', '', '| type | class | sections |', '|---|---|---|']
    for (t, c), n in sorted(stat.items()): L.append('| %s | %s | %d |' % (t, c, n))
    L += ['', '## Per last install', '', '| install | source | type | sections |', '|---|---|---|---|']
    for (w, s, t), n in sorted(by_src.items()): L.append('| %s | %s | %s | %d |' % (w, s, t, n))
    L += ['', '## Re-runnable', '', '| rerun | class | sections |', '|---|---|---|']
    for (rr, c), n in sorted(by_rerun.items()): L.append('| %s | %s | %d |' % (rr, c, n))
    L += ['', '## Missing (distinct texts)', '']
    mc = collections.Counter()
    for ln in lines[1:]:
        c = ln.split('\t')
        for m in c[16].split('; '):
            if m and m != '-': mc[m] += 1
    for m, n in mc.most_common(): L.append('- %d x %s' % (n, m))
    open(os.path.join(outd, 'summary.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    print('wrote %s (%d rows)' % (tsv, len(out)))


def main(argv):
    if not argv or argv[0] not in ('scan', 'decide'): raise SystemExit(__doc__)
    {'scan': scan, 'decide': decide}[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
