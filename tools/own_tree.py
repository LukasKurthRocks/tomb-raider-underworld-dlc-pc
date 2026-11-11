r"""The own mods tree from our pipeline outputs only (no file of the B138 / B270 kit), and its exact comparison with
the installed game (2026-11-11, docs Befund-Eigener-Baum-1111.md).

  assemble OUT_DIR [--run work/rebuild/pipeline_check_1011] [--costumes work/rebuild/costumes_0913]
                   [--generalbank pc|k12] [--no-lang] [--exe FILE] [--credits DIR]
      copies the pipeline outputs, in this order (a later layer wins for a file two layers have; every overlap is
      listed with "same" / "DIFFERENT"):
        dlc1         <run>/dlc1/mods                        step Fixes (-FixesOut <run>), DLC 1 tree (B138 layout)
        dlc2         <run>/dlc2/mods                        step Fixes, DLC 2 tree
        cost_<pack>  <costumes>/<pack>/stage2b/mods         step Costumes; only dlc_costume_*.drm (images / lists of
                                                            the costume trees are the DLC 1 tree's, docs/COSTUMES.md)
        lang         <run>/lang/mods                        step Lang (2026-11-11, R10): the 60 language variants of
                     (else work/rebuild/lang/mods)          the DLC cinematics / DLC 1 radio lines (replaces the
                                                            carry-over list carry_lang.txt); --no-lang leaves it out
        globalsound  <run>/globalsound/mods                 step Globalsound (kit-free: PC original + TU edit)
                     (else work/rebuild/globalsound/mods)
        generalbank  --generalbank pc (default since 2026-11-11): <run>/generalbank_pc/mods (else
                     work/rebuild/generalbank_pc/mods), step Generalbank = PC patch.000 generalbank + recorded
                     knowledge + ring P14 + TU camera DTPs, no kit input;
                     --generalbank k12: <run>_gb/generalbank_build/k12/mods, the old K12 file whose INPUT is B138's
                     generalbank.drm -> marked kit_derived
      and the exe of step Exe (<run>/exe/tru.exe, else work/rebuild/exe/tru.exe; --exe FILE) to OUT_DIR/exe/ (not
      part of mods).
      Credits (2026-11-11, Q42): the end-credits movies credits_DLC1.bik / credits_DLC2.bik of scripts/credits_convert.py
      (--dlc 1 / --dlc 2: the player's own credits_DLC<n>.wmv of the DLC content folder, ffmpeg + RAD Video Tools) from
      --credits DIR (default <run>/credits, else work/rebuild/credits) to OUT_DIR/movies/ (not part of mods; manifest
      rows ../movies/<name>, as the exe). A missing movie is named, not fatal (credits need RAD Video Tools).
      DROP: pipeline outputs a played tree must not have (g_pda.drm, finding 40); ALIAS: byte copies of a pipeline
      output under a name the game asks for and no step writes yet (loading_bg_dlc1/2.raw_004) - both with the
      evidence in the table below, both listed in assemble_overlaps.tsv.
      Refuses any source below a kit / kit-based tree (b138_pristine, b138_fixes, *_repair, b270_kit, release).
      Writes OUT_DIR/mods, OUT_DIR/exe/tru.exe, OUT_DIR/movies/credits_DLC*.bik, OUT_DIR/own_manifest.tsv (rel, size, md5, raw_md5, layer, step,
      kit_derived, source, also_in) and OUT_DIR/assemble_overlaps.tsv. OUT_DIR/mods must not exist yet.

  compare OWN_MODS GAME_MODS --backup ../backup --logs ../logs --out DIR [--manifest OWN_MANIFEST.tsv]
      read-only. Every file of both trees (case-insensitive paths; any name containing "truguard" is skipped and never
      printed) is classified:
        same            md5 equal
        same_content    DRM: same decompressed content (other zlib stream)
        different       the producer of the installed file is looked up: the events that changed it in the game =
                        the open Install-TruTree installs (backup/tree_* manifests, not *.restored) and the single-file
                        installs (logs/Install-TruModFile_*_Install.log + backup/mods/<name>.<previous md5>), oldest
                        first; before = the event's backup copy, after = the next event's before / the current file;
                        a current file no event wrote = a 'manual' event (its md5 is looked up by name in work/);
                        no event = the B138 / B270 kit manifests. Every differing section (type, id) of a DRM - the
                        whole file for the others - is attributed to the event that last changed it ("base" = the
                        first installed state): own section == the event's before = fix_missing, other = changed
                        differently, not in the own file = section_missing_in_own, file added by the event =
                        added_file_differs. String tables also get the differing string indices.
        only_installed  B138 / B270 kit file, test tree, single-file install or unknown
        only_own        only our tree has it
      Writes DIR/compare.tsv (one row per file), DIR/regressions.tsv (one row per (file, install) with sections the
      own tree lacks), DIR/sections.tsv (one row per differing section) and DIR/summary.md.

  report DIR [--out FILE]
      read-only: per event and state the differing section types and files of a compare run, and the counts per
      regression class R1-R13 (Befund-Eigener-Baum-1111.md) -> DIR/breakdown.md (or FILE).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/own_tree.py assemble work/own_1011
  ../bin/pyt -t 900 tools/own_tree.py assemble work/own_1111 --run work/rebuild/pipeline_check_1111b
        (Fixes + Lang + Generalbank + Exe + Globalsound all run with -FixesOut work/rebuild/pipeline_check_1111b)
  ../bin/pyt -t 5400 tools/own_tree.py compare work/own_1011/mods ../data/pc/mods --backup ../backup --logs ../logs
        --out work/own_1011/compare --manifest work/own_1011/own_manifest.tsv
"""
import sys, os, re, json, shutil, hashlib, collections, fnmatch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FORBIDDEN = ('b138_pristine', 'b138_fixes', '_repair', 'b270_kit', '/release/', 'release\\', 'base_b138')
TYPE_NAME = {-1: 'file', 0: 'general', 2: 't2', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
             11: 'obj', 12: 'mesh', 13: 't13'}


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def hidden(name):
    return 'truguard' in name.lower()


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


_raw_cache = {}


def raw_md5(p):
    """md5 of the decompressed DRM (None for other files)"""
    if not p.lower().endswith('.drm'): return None
    key = (p, os.path.getsize(p), os.path.getmtime(p))
    if key not in _raw_cache:
        from drm import cdrm_decode
        _raw_cache[key] = hashlib.md5(cdrm_decode(open(p, 'rb').read(), 'le')).hexdigest()
    return _raw_cache[key]


def walk(root):
    """{rel_lower: (rel, path)} below root; names containing 'truguard' are skipped (never listed)"""
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not hidden(d)]
        for f in fn:
            if hidden(f): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace('\\', '/')
            out[rel.lower()] = (rel, p)
    return out


# ---------------------------------------------------------------------------------------------------------- assemble

# pipeline outputs that must not go into a played tree (with the evidence)
DROP = [('g_pda.drm', 'docs/WINDOWS_REBUILD.md finding 40: the merged / converted g_pda replaces 12 PC PDA scripts that '
                      'are not ported (vtable one slot short, Xbox init) - a new base game crashed (test 12); every '
                      'played tree keeps the PC g_pda (no file in mods)')]
# files the game asks for that no pipeline step writes yet: byte copies of a pipeline output (the installed copies
# have exactly these bytes)
ALIAS = [('image/loading_bg_dlc1.raw', 'image/loading_bg_dlc1.raw_004',
          'WINDOWS_REBUILD test 11: the TU loading screen asks for mods\\image\\loading_bg_dlc2.raw_004 on a German '
          'game and loops in NtCreateFile when it is missing; installed _004 = plain .raw byte for byte'),
         ('image/loading_bg_dlc2.raw', 'image/loading_bg_dlc2.raw_004', 'as loading_bg_dlc1.raw_004')]


def in_run(run, sub, fallback):
    """a side step's output of this run (-FixesOut <run> puts it below <run>), else the step's usual folder"""
    p = run + '/' + sub
    return p if os.path.exists(p) else fallback


def layers(run, costumes, gb='pc', lang=True):
    L = [('dlc1', 'Fixes (DLC 1, -FixesOut %s)' % run, run + '/dlc1/mods', None, False),
         ('dlc2', 'Fixes (DLC 2, -FixesOut %s)' % run, run + '/dlc2/mods', None, False)]
    for pk in ('pack1', 'pack2', 'pack20'):
        L.append(('cost_' + pk, 'Costumes (%s)' % costumes, '%s/%s/stage2b/mods' % (costumes, pk), 'dlc_costume_*.drm', False))
    if lang:
        L.append(('lang', 'Lang (language variants, R10)', in_run(run, 'lang/mods', 'work/rebuild/lang/mods'), None, False))
    L.append(('globalsound', 'Globalsound', in_run(run, 'globalsound/mods', 'work/rebuild/globalsound/mods'), None, False))
    if gb == 'k12':
        L.append(('generalbank', 'Generalbank (K12; input = B138 generalbank.drm)', run + '_gb/generalbank_build/k12/mods', None, True))
    elif gb == 'pc':
        L.append(('generalbank', 'Generalbank (PC basis: patch.000 + knowledge + ring P14 + TU camera DTPs)',
                  in_run(run, 'generalbank_pc/mods', 'work/rebuild/generalbank_pc/mods'), None, False))
    else:
        raise SystemExit('--generalbank must be pc or k12: %s' % gb)
    return L


def assemble(argv):
    run = arg(argv, '--run', 'work/rebuild/pipeline_check_1011').replace('\\', '/').rstrip('/')
    costumes = arg(argv, '--costumes', 'work/rebuild/costumes_0913')
    gb = arg(argv, '--generalbank', 'pc')
    lang = '--no-lang' not in argv
    if not lang: argv.remove('--no-lang')
    exe = arg(argv, '--exe', in_run(run, 'exe/tru.exe', 'work/rebuild/exe/tru.exe'))
    credits = arg(argv, '--credits', in_run(run, 'credits', 'work/rebuild/credits'))
    outdir = argv[0]
    mods = os.path.join(outdir, 'mods')
    if os.path.exists(mods): raise SystemExit('exists already: %s (remove it first)' % mods)
    lay = layers(run, costumes, gb, lang)
    for name, step, d, pat, kd in lay + [('exe', 'Exe', exe, None, False), ('credits', 'Credits', credits, None, False)]:
        low = d.replace('\\', '/').lower()
        if any(f.replace('\\', '/') in low for f in FORBIDDEN):
            raise SystemExit('refused: layer %s reads a kit / kit-based tree: %s' % (name, d))
        if name == 'credits': continue      # optional (RAD Video Tools); missing movies are named below
        if name == 'exe':
            if not os.path.isfile(d): raise SystemExit('missing exe: %s' % d)
            continue
        if not os.path.isdir(d): raise SystemExit('missing layer %s: %s' % (name, d))
    files = collections.OrderedDict()      # rel_lower -> dict
    overlaps, skipped = [], collections.Counter()
    for name, step, d, pat, kd in lay:
        for k, (rel, p) in sorted(walk(d).items()):
            if pat and not fnmatch.fnmatch(os.path.basename(rel).lower(), pat):
                skipped[name] += 1
                # the skipped costume files must exist with the same content in a layer before (DLC 1 tree)
                prev = files.get(k)
                overlaps.append((rel, name, prev['layer'] if prev else '-', 'skipped:' + (
                    'same' if prev and md5_file(prev['source']) == md5_file(p) else ('DIFFERENT' if prev else 'not_in_earlier_layer'))))
                continue
            m = md5_file(p)
            prev = files.get(k)
            also = []
            if prev:
                verdict = 'same' if prev['md5'] == m else ('same_content' if raw_md5(prev['source']) and raw_md5(prev['source']) == raw_md5(p) else 'DIFFERENT')
                overlaps.append((rel, name, prev['layer'], verdict))
                also = prev['also_in'] + ['%s:%s' % (prev['layer'], verdict)]
            files[k] = dict(rel=rel, source=p, md5=m, size=os.path.getsize(p), layer=name, step=step, kit_derived=kd, also_in=also)
    for rel, why in DROP:
        e = files.pop(rel.lower(), None)
        print('dropped %s (%s): %s' % (rel, e['layer'] if e else 'not present', why))
        overlaps.append((rel, 'drop', e['layer'] if e else '-', 'dropped'))
    for src, dst, why in ALIAS:
        e = files.get(src.lower())
        if not e: raise SystemExit('alias source missing: %s' % src)
        files[dst.lower()] = dict(e, rel=dst, layer='alias', step='assemble alias of %s (%s)' % (src, why), also_in=[])
        overlaps.append((dst, 'alias', e['layer'], 'copy_of:' + src))
    os.makedirs(mods)
    for k, e in files.items():
        q = os.path.join(mods, e['rel'].replace('/', os.sep))
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(e['source'], q)
        if md5_file(q) != e['md5']: raise SystemExit('copy check failed: %s' % q)
        e['raw_md5'] = raw_md5(q) or '-'
    exe_md5 = '-'
    if exe and os.path.isfile(exe):
        os.makedirs(os.path.join(outdir, 'exe'), exist_ok=True)
        q = os.path.join(outdir, 'exe', 'tru.exe'); shutil.copy2(exe, q); exe_md5 = md5_file(q)
    movies = []                            # (name, size, md5, source): end credits of scripts/credits_convert.py
    for n in ('1', '2'):
        name = 'credits_DLC%s.bik' % n
        p = os.path.join(credits, name)
        if not os.path.isfile(p):
            print('credits: %s not built (missing %s) - scripts/credits_convert.py --dlc %s' % (name, p, n)); continue
        os.makedirs(os.path.join(outdir, 'movies'), exist_ok=True)
        q = os.path.join(outdir, 'movies', name); m = md5_file(p)
        shutil.copy2(p, q)
        if md5_file(q) != m: raise SystemExit('copy check failed: %s' % q)
        movies.append((name, os.path.getsize(q), m, p))
        print('credits: %s %d bytes md5 %s <- %s' % (name, os.path.getsize(q), m, p))
    cols =['rel', 'size', 'md5', 'raw_md5', 'layer', 'step', 'kit_derived', 'source', 'also_in']
    with open(os.path.join(outdir, 'own_manifest.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(cols) + '\n')
        for k, e in files.items():
            f.write('\t'.join([e['rel'], str(e['size']), e['md5'], e['raw_md5'], e['layer'], e['step'],
                               'yes' if e['kit_derived'] else 'no', e['source'].replace('\\', '/'),
                               ','.join(e['also_in']) or '-']) + '\n')
        f.write('\t'.join(['../exe/tru.exe', str(os.path.getsize(exe)) if exe_md5 != '-' else '0', exe_md5, '-', 'exe',
                           'Exe (not part of mods)', 'no', exe.replace('\\', '/'), '-']) + '\n')
        for name, size, m, p in movies:
            f.write('\t'.join(['../movies/' + name, str(size), m, '-', 'credits',
                               'Credits (scripts/credits_convert.py, not part of mods)', 'no', p.replace('\\', '/'), '-']) + '\n')
    with open(os.path.join(outdir, 'assemble_overlaps.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('rel\tlayer\toverrides\tverdict\n')
        for r in overlaps: f.write('\t'.join(r) + '\n')
    per = collections.Counter(e['layer'] for e in files.values())
    for name, step, d, pat, kd in lay:
        print('layer %-12s %4d files%s  %s%s' % (name, per[name], (' (%d skipped)' % skipped[name]) if skipped[name] else '',
                                              d, '  [kit_derived input]' if kd else ''))
    ov = collections.Counter(r[3] for r in overlaps)
    print('overlaps:', dict(ov))
    for r in overlaps:
        if 'DIFFERENT' in r[3] or 'not_in' in r[3]: print('  %-60s %-12s over %-8s %s' % r)
    print('own tree: %d files, %d bytes -> %s; exe md5 %s; movies %s' % (len(files), sum(e['size'] for e in files.values()), mods,
                                                                      exe_md5, ', '.join(m[0] for m in movies) or 'none'))


# ----------------------------------------------------------------------------------------------------------- compare

def load_stack(backup):
    """open Install-TruTree installs, oldest first"""
    st = []
    for n in sorted(os.listdir(backup)):
        if not n.startswith('tree_') or n.endswith('.restored') or hidden(n): continue
        mp = os.path.join(backup, n, 'manifest.json')
        if not os.path.isfile(mp): continue
        m = json.load(open(mp, encoding='utf-8-sig'))
        rep = {str(r['path']).replace('\\', '/').lower(): r['md5'] for r in (m.get('replaced') or []) if r}
        add = {str(a).replace('\\', '/').lower() for a in (m.get('added') or []) if a}
        inst = {str(i['path']).replace('\\', '/').lower(): i['md5'] for i in (m.get('installed') or []) if i}
        st.append(dict(name=n, dir=os.path.join(backup, n), time=m.get('time', n[5:]), source=m.get('source', ''),
                       replaced=rep, added=add, installed=inst))
    return st


def short_source(s):
    s = s.replace('\\', '/')
    i = s.find('/work/')
    return s[i + 1:] if i >= 0 else s


def load_modfile_logs(logs):
    """single-file installs (Install-TruModFile.ps1 logs): [(time, rel_lower, md5, source, previous md5)]"""
    out = []
    if not os.path.isdir(logs): return out
    for n in sorted(os.listdir(logs)):
        if not n.startswith('Install-TruModFile_') or not n.endswith('_Install.log') or hidden(n): continue
        src = ''
        for ln in open(os.path.join(logs, n), encoding='utf-8-sig', errors='replace'):
            m = re.search(r'\] source (.+?) md5 ([0-9a-f]{32})', ln)
            if m: src = m.group(1)
            m = re.search(r'Installed mods\\(.+?) \(md5 ([0-9a-f]{32})\)(?:; previous build md5 ([0-9a-f]{32}))?', ln)
            if m: out.append((n[19:34], m.group(1).replace('\\', '/').lower(), m.group(2), src, m.group(3)))
    return out


def file_events(k, rel, stack, mods, backup, gp, inst_md5):
    """what changed mods/<rel> in the game, oldest first: open tree installs and single-file installs, each with the
    file before it (backup copy; None = the install added it) and after it (= the next event's before, the current
    file for the last one). A last state that no recorded install wrote (copied by hand) becomes a 'manual' event."""
    ev = []
    for s in stack:
        if k in s['replaced'] or k in s['added']:
            b = os.path.join(s['dir'], 'files', rel.replace('/', os.sep)) if k in s['replaced'] else None
            after_md5 = s['installed'].get(k)
            if after_md5 is None:
                sp = os.path.join(s['source'], rel.replace('/', os.sep))
                after_md5 = md5_file(sp) if os.path.isfile(sp) else None
            ev.append(dict(t=s['name'][5:], name=s['name'], source=short_source(s['source']), before=b, added=b is None,
                           after_md5=after_md5, src_path=os.path.join(s['source'], rel.replace('/', os.sep))))
    for t, rk, md5, src, prev in mods:
        if rk != k: continue
        b = os.path.join(backup, 'mods', rel.replace('/', os.sep) + '.' + prev) if prev else None
        ev.append(dict(t=t, name='ModFile ' + t, source=short_source(src), before=b if b and os.path.isfile(b) else None,
                       added=False, after_md5=md5, src_path=src))
    ev.sort(key=lambda e: e['t'])
    for i, e in enumerate(ev):
        if e['before'] and not os.path.isfile(e['before']): e['before'] = None
        e['after'] = ev[i + 1]['before'] if i + 1 < len(ev) else gp
    if ev and gp and ev[-1]['after_md5'] and ev[-1]['after_md5'] != inst_md5:
        last = ev[-1]
        sp = last['src_path'] if last['src_path'] and os.path.isfile(last['src_path']) and md5_file(last['src_path']) == last['after_md5'] else None
        last['after'] = sp
        ev.append(dict(t='manual', name='manual', source='copied by hand (no install record)', before=sp, added=False,
                       after_md5=inst_md5, after=gp, src_path=None))
    return ev


def kit_md5s():
    out = {}
    for kname, mp in (('B138', '../release/B138/kit/manifest.json'), ('B270', 'work/b270_kit/kit/manifest.json')):
        if not os.path.isfile(mp): continue
        man = json.load(open(mp, encoding='utf-8'))
        for e in list(man['files']) + list(man.get('extra', [])):
            rel = e['rel'].replace('\\', '/').lower()
            out.setdefault((rel, e['md5']), []).append(kname)
            if e.get('raw_md5'): out.setdefault((rel, 'raw:' + e['raw_md5']), []).append(kname)
    return out


def sections(p):
    """{(type, id, n): (hash, size)} of a DRM; General sections keyed by their order"""
    import drm, drm_reloc as R
    raw = drm.cdrm_decode(open(p, 'rb').read(), 'le')
    h, secs = drm.sections_with_data(raw, 'le')
    t0 = {}
    for x in secs:
        if x['type'] == 0: t0[x['i']] = len(t0)
    out, cnt = {}, collections.Counter()
    for s in secs:
        try:
            r = R.parse(s['reloc'], 'le')
            ext = [((secs[si]['type'], secs[si]['id'] if secs[si]['type'] != 0 else t0[si]), so, do) for si, so, do in r.external]
            rk = repr((r.internal, ext, r.idref, r.idref_a))
        except Exception:
            rk = s['reloc'].hex()
        k0 = (s['type'], s['id'])
        n = cnt[k0]; cnt[k0] += 1
        out[(s['type'], s['id'], n)] = (hashlib.md5(s['data'] + b'|' + rk.encode()).hexdigest(), s['size'])
    return out


_sec_cache = {}


def secs_of(p, is_drm):
    """sections of a DRM; any other file is one pseudo section (-1, 0, 0) = its md5. is_drm comes from the mods
    path (backup copies are named <name>.drm.<md5>)"""
    if p is None: return None
    key = md5_file(p)
    if not is_drm: return {(-1, 0, 0): (key, os.path.getsize(p))}
    if key not in _sec_cache:
        try: _sec_cache[key] = sections(p)
        except Exception as ex: _sec_cache[key] = 'ERR %s: %s' % (type(ex).__name__, ex)
    return _sec_cache[key]


def name_index(root, names):
    """{basename_lower: [paths]} below root for the given basenames (skips TruGuard names)"""
    out = collections.defaultdict(list)
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not hidden(d) and d not in ('.git',)]
        for f in fn:
            fl = f.lower()
            if fl in names and not hidden(f): out[fl].append(os.path.join(dp, f))
    return out


def compare(argv):
    backup = arg(argv, '--backup', '../backup')
    logs = arg(argv, '--logs', '../logs')
    outd = arg(argv, '--out', 'work/own_1011/compare')
    manp = arg(argv, '--manifest')
    own_root, game_root = argv[0], argv[1]
    os.makedirs(outd, exist_ok=True)
    own, game = walk(own_root), walk(game_root)
    layer = {}
    if manp and os.path.isfile(manp):
        for ln in open(manp, encoding='utf-8').read().splitlines()[1:]:
            c = ln.split('\t')
            layer[c[0].lower()] = (c[4], c[5], c[6])
    stack = load_stack(backup)
    mods = load_modfile_logs(logs)
    kits = kit_md5s()
    print('own %d files, installed %d files (TruGuard names skipped), open installs %d, single-file installs %d' % (
        len(own), len(game), len(stack), len(mods)))
    # md5 of every source file referenced by the stack (v1 manifests have no installed md5)
    rows, secrows, regrows = [], [], []
    unresolved = {}
    for k in sorted(set(own) | set(game)):
        o = own.get(k); g = game.get(k)
        rel = (o or g)[0]
        r = dict(rel=rel, cls='', own_md5='-', inst_md5='-', own_layer='-', producer='-', producer_time='-',
                 chain='-', newer='-', secs='-', note='')
        if o: r['own_md5'] = md5_file(o[1]); r['own_layer'] = layer.get(k, ('?',))[0]
        if g: r['inst_md5'] = md5_file(g[1])
        # what changed this file in the game (open tree installs + single-file installs + hand copies), oldest first
        ev = file_events(k, rel, stack, mods, backup, g[1] if g else None, r['inst_md5']) if g else []
        r['chain'] = ','.join(e['name'].replace('tree_', '') for e in ev) or '-'
        if g:
            prod = None
            if ev and ev[-1]['name'] != 'manual':
                last = ev[-1]
                prod = ('tree' if last['name'].startswith('tree_') else 'modfile', last['name'], last['source'], last['t'])
            if prod is None:
                kn = kits.get((k, r['inst_md5'])) or (kits.get((k, 'raw:' + raw_md5(g[1]))) if k.endswith('.drm') else None)
                if kn: prod = ('kit', '/'.join(sorted(set(kn))), 'kit', '-')
            if prod is None:
                unresolved[k] = r
                prod = ('unknown', '-', '-', '-')
            r['producer_kind'], r['producer'], r['producer_src'], r['producer_time'] = prod
        else:
            r['producer_kind'] = r['producer_src'] = '-'
        if o and g:
            if r['own_md5'] == r['inst_md5']: r['cls'] = 'same'
            elif k.endswith('.drm') and raw_md5(o[1]) == raw_md5(g[1]): r['cls'] = 'same_content'
            else: r['cls'] = 'different'
        elif g: r['cls'] = 'only_installed'
        else: r['cls'] = 'only_own'
        r['_paths'] = (o[1] if o else None, g[1] if g else None)
        r['_ev'] = ev
        if ev and ev[-1]['name'] == 'manual': r['note'] = 'installed file copied by hand after the last install'
        rows.append(r)
    # unknown producers: look the md5 up by name in work/ (test trees, fix folders)
    if unresolved:
        idx = name_index('work', {os.path.basename(k) for k in unresolved})
        for k, r in unresolved.items():
            hits = sorted(p.replace('\\', '/') for p in idx.get(os.path.basename(k), [])
                          if os.path.getsize(p) == os.path.getsize(r['_paths'][1]) and md5_file(p) == r['inst_md5'])
            if hits:
                hits.sort(key=lambda p: (0 if '/rebuild/b138_fixes/' in p else 1 if '/rebuild/' in p else 2, p))
                r['producer_kind'], r['producer'] = ('manual' if r['_ev'] else 'by_md5'), 'same md5 in work'
                r['producer_src'] = hits[0] + ('' if len(hits) == 1 else ' (+%d more)' % (len(hits) - 1))
            if r['producer_kind'] == 'unknown': r['note'] = (r['note'] + '; ' if r['note'] else '') + 'producer not found'
    # attribution of every differing section (DRM) / the whole file (others) to the event that last changed it:
    #   base_differs           no recorded event changed it: the installed state is the first one (kit file / the
    #                          state before the oldest open install)
    #   added_file_differs     the event added the whole file (no "before" to compare with)
    #   fix_missing            the own section = the event's "before": the own tree lacks exactly this change
    #   section_missing_in_own the event's section is not in the own file at all
    #   changed_differently   the own section is neither the event's before nor after
    #   no_before              the event's "before" copy is not available (single-file install without backup)
    srcmap = {s['name']: short_source(s['source']) for s in stack}
    for r in rows:
        if r['cls'] != 'different': continue
        op, gp = r['_paths']
        isd = r['rel'].lower().endswith('.drm')
        so, sg = secs_of(op, isd), secs_of(gp, isd)
        if isinstance(so, str) or isinstance(sg, str):
            r['secs'] = so if isinstance(so, str) else sg; r['_attr'] = collections.Counter(); continue
        diff = sorted(k for k in set(so) | set(sg) if so.get(k, (None,))[0] != sg.get(k, (None,))[0])
        vers = []
        for e in r['_ev']:
            sb = secs_of(e['before'], isd) if e['before'] else ({} if e['added'] else None)
            sa = secs_of(e['after'], isd) if e['after'] else None
            vers.append((e, sb, sa))
        attr = collections.Counter()
        for sk in diff:
            who, src, beforeh, state = 'base', '-', None, 'base_differs'
            for e, sb, sa in reversed(vers):
                if sa is None or isinstance(sa, str) or isinstance(sb, str): continue
                if sb is None:             # no before copy: only attributable when the after state is the installed one
                    if sa.get(sk, (None,))[0] == sg.get(sk, (None,))[0] and e is vers[-1][0]:
                        who, src, state = e['name'], e['source'], 'no_before'
                        break
                    continue
                if sb.get(sk, (None,))[0] != sa.get(sk, (None,))[0] and sa.get(sk, (None,))[0] == sg.get(sk, (None,))[0]:
                    who, src = e['name'], e['source']
                    beforeh = 'added' if e['added'] else sb.get(sk, (None,))[0]
                    break
            if who != 'base' and state != 'no_before':
                oh = so.get(sk, (None,))[0]
                if beforeh == 'added': state = 'added_file_differs'
                elif oh == beforeh: state = 'fix_missing'
                elif oh is None: state = 'section_missing_in_own'
                else: state = 'changed_differently'
            tname = TYPE_NAME.get(sk[0], 't%d' % sk[0])
            if sk not in sg: tname = 'ownonly_' + tname
            elif sk not in so: tname = 'instonly_' + tname
            attr[(who, state, tname)] += 1
            secrows.append([r['rel'], '%d:%d:%d' % sk, tname, who, src, state])
        r['secs'] = '; '.join('%s/%s/%s=%d' % (w, st, t, n) for (w, st, t), n in sorted(attr.items()))
        r['_attr'] = attr
        for e in r['_ev']: srcmap.setdefault(e['name'], e['source'])
    # string tables: which strings differ, and the DLC description line breaks (456 / 457, dlc_text_unwrap)
    import locals as LOC
    for r in rows:
        if r['cls'] != 'different' or not r['rel'].lower().startswith('local/locals.bin'): continue
        op, gp = r['_paths']
        _, so_, _ = LOC.parse(open(op, 'rb').read(), 'le')
        _, sg_, _ = LOC.parse(open(gp, 'rb').read(), 'le')
        di = [i for i in range(max(len(so_), len(sg_))) if (so_[i] if i < len(so_) else None) != (sg_[i] if i < len(sg_) else None)]
        nl = lambda s, i: (b'\n' in s[i]) if i < len(s) else None
        r['note'] = (r['note'] + '; ' if r['note'] else '') + 'strings own %d / installed %d, %d differ (index %s); 456/457 line breaks own %s/%s installed %s/%s' % (
            len(so_), len(sg_), len(di), ','.join(str(i) for i in di[:8]), nl(so_, 456), nl(so_, 457), nl(sg_, 456), nl(sg_, 457))
    # which side newer: producer time of the installed file vs the own file's build time
    for r in rows:
        if r['cls'] != 'different': continue
        op, gp = r['_paths']
        ot, gt = os.path.getmtime(op), os.path.getmtime(gp)
        r['newer'] = 'own' if ot > gt else 'installed'
    # regression rows: per (file, install) the sections the own tree lacks
    reg = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        for (who, st, t), n in (r.get('_attr') or {}).items():
            if who != 'base':
                reg[(r['rel'], who)][st] += n
    for (rel, who), c in sorted(reg.items()):
        regrows.append([rel, who, srcmap.get(who, who), str(c['fix_missing']), str(c['changed_differently']),
                        str(c['section_missing_in_own']), str(c['added_file_differs']), str(c['no_before']), str(sum(c.values()))])
    # write
    cols = ['rel', 'cls', 'own_md5', 'inst_md5', 'own_layer', 'producer_kind', 'producer', 'producer_src', 'producer_time',
            'newer', 'chain', 'secs', 'note']
    with open(os.path.join(outd, 'compare.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows: f.write('\t'.join(str(r.get(c, '-')) for c in cols) + '\n')
    with open(os.path.join(outd, 'sections.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('rel\tsection\ttype\tinstalled_by\tinstalled_by_source\tstate\n')
        for x in secrows: f.write('\t'.join(x) + '\n')
    with open(os.path.join(outd, 'regressions.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('rel\tinstall\tsource\tfix_missing\tchanged_differently\tsection_missing_in_own\tadded_file_differs\tno_before\ttotal\n')
        for x in regrows: f.write('\t'.join(x) + '\n')
    # summary
    c = collections.Counter(r['cls'] for r in rows)
    L = ['# Own tree vs installed (tools/own_tree.py compare)', '',
         'own `%s` (%d files), installed `%s` (%d files, TruGuard names skipped), %d open installs' % (
             own_root, len(own), game_root, len(game), len(stack)), '',
         '| class | files |', '|---|---|']
    for k in ('same', 'same_content', 'different', 'only_installed', 'only_own'): L.append('| %s | %d |' % (k, c[k]))
    L += ['', '## different: producer of the installed file', '', '| producer kind | producer | files |', '|---|---|---|']
    g = collections.Counter((r['producer_kind'], r['producer_src'] if r['producer_kind'] != 'kit' else r['producer']) for r in rows if r['cls'] == 'different')
    for (kd, p), n in sorted(g.items(), key=lambda x: -x[1]): L.append('| %s | %s | %d |' % (kd, p, n))
    L += ['', '## only_installed: producer', '', '| producer kind | producer | files |', '|---|---|---|']
    g = collections.Counter((r['producer_kind'], r['producer_src'] if r['producer_kind'] != 'kit' else r['producer']) for r in rows if r['cls'] == 'only_installed')
    for (kd, p), n in sorted(g.items(), key=lambda x: -x[1]): L.append('| %s | %s | %d |' % (kd, p, n))
    for r in rows:
        if r['cls'] == 'only_installed': L.append('- only installed: `%s` (%s %s)' % (r['rel'], r['producer_kind'], r['producer_src'] if r['producer_kind'] != 'kit' else r['producer']))
    L += ['', '## only_own', '']
    for r in rows:
        if r['cls'] == 'only_own': L.append('- `%s` (%s)' % (r['rel'], r['own_layer']))
    L += ['', '## Regressions: installed changes the own tree lacks, per install', '',
          '| install | source | files | fix_missing | changed_differently | section_missing_in_own | added_file_differs | no_before |', '|---|---|---|---|---|---|---|---|']
    per = collections.defaultdict(lambda: [set(), collections.Counter()])
    for (rel, who), cc in reg.items():
        per[who][0].add(rel); per[who][1].update(cc)
    for who in sorted(per):
        fs, cc = per[who]
        L.append('| %s | %s | %d | %d | %d | %d | %d | %d |' % (who, srcmap.get(who, who), len(fs), cc['fix_missing'], cc['changed_differently'],
                                                            cc['section_missing_in_own'], cc['added_file_differs'], cc['no_before']))
    base = collections.Counter()
    for r in rows:
        for (who, st, t), n in (r.get('_attr') or {}).items():
            if who == 'base': base[(who, st, t)] += n
    L += ['', '## Differences in the first installed state (kit file / state before the oldest open install)', '', '| who | state | type | sections / files |', '|---|---|---|---|']
    for (w, st, t), n in sorted(base.items()): L.append('| %s | %s | %s | %d |' % (w, st, t, n))
    open(os.path.join(outd, 'summary.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    print('wrote', outd)


R5_SOURCES = ('dlc_test51i_ids', 'crash17m', 'dopp17m', 'treecer', 'dlc_test51v_fix26_15f', 'meleefix_0711', 'genfix_0711',
              'costumefix_0711', 'moan_0711', 'dlc_test51c_objfx', 'caverns74_0711')


def r_class(rel, typ, who, src, state):
    """regression class of one differing section (sections.tsv row) - the table of Befund-Eigener-Baum-1111.md:
    R1 N6b shaders, R2 other shader trees, R3 grapple ring (DLC 1), R4 B270 data words (b270cmp), R5 data words of other
    test trees, R6 shadow meter HUD (generalbank), R7 ring menu P14, R8 lock-on K-5b, R9 texts, R10 language variants
    (only_installed files, see report), R12 UI records test 34, R13 objlist.dat; 'added' = files a 30.10. play tree
    added (no before state), 'base' = first installed state"""
    r, s = rel.lower(), (src or '').replace('\\', '/').lower()
    if who == 'base': return 'base'
    if r.startswith('dlc1_ei_grapple_'): return 'R3'
    if 'fix_lock_1011' in s: return 'R8'
    if 'dlc_test50l_hud' in s: return 'R6'
    if 'ring_p14' in s: return 'R7'
    if 'dlc_text' in s: return 'R9'
    if 'dlc_test34_records' in s: return 'R12'
    if r.endswith('objlist.dat'): return 'R13'
    if state == 'added_file_differs': return 'added'
    if typ in ('shaderlib', 'material'):
        return 'R1' if ('/n6b' in s or 'tree_n6b' in s) else 'R2'
    if 'b270cmp' in s: return 'R4'
    if any(x in s for x in R5_SOURCES): return 'R5'
    return 'other (%s %s)' % (src, typ)


def report(argv):
    """breakdown of a compare run (DIR/sections.tsv + compare.tsv): per event and state the section types and files;
    writes DIR/breakdown.md (--out FILE: there instead)"""
    outf = arg(argv, '--out')
    d = argv[0]
    rows = [ln.split('\t') for ln in open(os.path.join(d, 'sections.tsv'), encoding='utf-8').read().splitlines()[1:]]
    comp = [ln.split('\t') for ln in open(os.path.join(d, 'compare.tsv'), encoding='utf-8').read().splitlines()]
    hc = comp[0]; comp = [dict(zip(hc, c)) for c in comp[1:]]
    per = collections.defaultdict(collections.Counter)
    files = collections.defaultdict(set)
    src = {}
    for rel, sec, t, who, s, st in rows:
        base_t = t.split('_', 1)[1] if t.startswith(('ownonly_', 'instonly_')) else t
        per[(who, st)][base_t] += 1
        files[(who, st)].add(rel)
        src[who] = s
    L = ['# Breakdown of `%s` (tools/own_tree.py report)' % d, '',
         '| event | source | state | sections by type | files |', '|---|---|---|---|---|']
    for (who, st) in sorted(per, key=lambda k: (k[0] == 'base', k[0], k[1])):
        c = per[(who, st)]
        fs = sorted(files[(who, st)])
        L.append('| %s | %s | %s | %s | %d: %s |' % (who, src.get(who, '-'), st, ', '.join('%s %d' % kv for kv in sorted(c.items())),
                                                  len(fs), ', '.join('`%s`' % f for f in fs[:12]) + (' ...' if len(fs) > 12 else '')))
    # the regression classes R1-R13 of docs Befund-Eigener-Baum-1111.md (N1), so two compare runs can be set side by side
    cls_c = collections.defaultdict(collections.Counter)
    cls_f = collections.defaultdict(set)
    for rel, sec, t, who, s, st in rows:
        base_t = t.split('_', 1)[1] if t.startswith(('ownonly_', 'instonly_')) else t
        rc = r_class(rel, base_t, who, s, st)
        cls_c[rc][st] += 1
        cls_f[rc].add(rel)
    for r in comp:
        if r['cls'] == 'only_installed':
            rc = 'R10' if re.search(r'\.mul_\d+$', r['rel'].lower()) else 'only_installed (%s)' % r.get('producer_src', '-')
            cls_c[rc]['only_installed_file'] += 1
            cls_f[rc].add(r['rel'])
    states = ['fix_missing', 'changed_differently', 'section_missing_in_own', 'added_file_differs', 'no_before',
              'base_differs', 'only_installed_file']
    L += ['', '## Regression classes (R1-R13 of Befund-Eigener-Baum-1111.md)', '',
          '| class | files | ' + ' | '.join(states) + ' |', '|---|---|' + '---|' * len(states)]
    for rc in sorted(cls_c, key=lambda k: (not k.startswith('R'), int(re.sub(r'\D', '', k) or 0) if k.startswith('R') else 0, k)):
        L.append('| %s | %d | %s |' % (rc, len(cls_f[rc]), ' | '.join(str(cls_c[rc][s]) for s in states)))
    L += ['', '## Files per class and own layer', '', '| class | own layer | files |', '|---|---|---|']
    for (cl, ly), n in sorted(collections.Counter((r['cls'], r['own_layer']) for r in comp).items()):
        L.append('| %s | %s | %d |' % (cl, ly, n))
    L += ['', '## Notes (string tables, hand copies, unknown producers)', '']
    for r in comp:
        if r.get('note', '-') not in ('', '-'): L.append('- `%s` (%s): %s' % (r['rel'], r['cls'], r['note']))
    open(outf or os.path.join(d, 'breakdown.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def main(argv):
    if not argv or argv[0] not in ('assemble', 'compare', 'report'): raise SystemExit(__doc__)
    {'assemble': assemble, 'compare': compare, 'report': report}[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
