"""Streamgroup audit (night 05.11.2026, read-only towards every input): which data of the DLC streamgroup DRMs
(mods\\streamgroups\\, the area geometry the game streams in) the tools that only list the top level of a mods folder
would have looked at, and what those tools' criteria find there.

Background: tools/tu_batch.py inv read only mods\\*.drm (fixed in a1c5a71); the Xbox cache work/generic/dlc_drms.pkl
keys the streamgroup DRMs only by their name hash (names in work/generic/dlc_names.txt). Workspace finding
docs\\Befund-Streamgroups-Shader-0511.md.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/sg_audit.py sections MODS_DIR [MODS_DIR ...]
      per streamgroup DRM (MODS_DIR/streamgroups/*.drm): section counts by type, new DTPs (type 7, id >= 20000),
      state-chart DTPs (tools/statechart_scan.py header 10000 / 12000 / 4000 / 6000), objects (type 11), scripts
      (type 8), materials (type 10), shader libs (type 9), NavPower image at Level+0x60 (tools/navgraph_probe.py)
  ../bin/pyt -t 300 tools/sg_audit.py invsum INV.json [--base INV0.json] [--out OUT.tsv]
      summary of a tools/tu_batch.py inventory: per DLC (Xbox pack of the paired file) materials / streamgroup-only /
      mixed (streamgroup + top-level copies); --base = an inventory of the same Xbox dump without the test trees:
      materials whose top-level copies the trees translated but whose streamgroup copies still use the surrogate.
      OUT.tsv: ranked rows (rank, score, DLC, material, Xbox lib, class, lit, VS, VS class, units, areas, files)
  ../bin/pyt -t 1800 tools/sg_audit.py float SG_DIR OUT_DIR
      the pipeline step `float` (work/ws/cine/float_fix.py, modes s16 and raw, each on the unchanged input) on the
      streamgroup DRMs of SG_DIR with the Xbox source looked up as streamgroups\\<name> (the step itself lists only
      the top folder and looks up the bare name). Writes the would-be fixed copies + float_fix_log.json to
      OUT_DIR/<mode>/ (never back to SG_DIR); prints the word counts per file / DTP.
  ../bin/pyt -t 1800 tools/sg_audit.py where INV.json INTROS.json [--top N]
      per material and file: terrain draws (bbox, vertices), the unit's intro bbox and the 3 nearest intros
      (INTROS.json from tools/shader_tour.py index); positions are a lead for screenshots, the frame is not proven
  ../bin/pyt -t 300 tools/sg_audit.py shots WHERE.tsv STATE.json [--top N] [--out OUT.tsv]
      screenshot list: per material the area with the most terrain vertices, ordered by total terrain vertices,
      with the status of a tools/tu_batch.py run (STATE.json of its WORKDIR)
  ../bin/pyt -t 900 tools/sg_audit.py diff INV.json STATE.json TREE
      every tree DRM against its inventory source: only the done groups' materials changed and their new libs added
  ../bin/pyt -t 300 tools/sg_audit.py mdinv INV.json STATE.json WHERE.tsv
      the ranked inventory as Markdown table rows (finding file) with terrain vertices and the run status
  ../bin/pyt -t 300 tools/sg_audit.py libcmp A.drm:LIB=B.drm:LIB [...]
      slot by slot: byte-identical shader blobs of two PC libs?
  ../bin/pyt -t 900 tools/sg_audit.py origin TARGET_MODS CAND_MODS [CAND_MODS ...]
      md5 of every streamgroup DRM of TARGET_MODS and the candidate mods folders holding a byte-identical copy
  ../bin/pyt -t 900 tools/sg_audit.py natives SG_DIR
      tools/script_missing_native_fix.process (report only, types 'all', reference = original PC generalbank) on
      every streamgroup DRM: script calls into natives the PC exe does not have
"""
import sys, os, struct, json, collections, glob, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, '..'))
import drm_write as DW

CHART = (struct.pack('>4I', 10000, 12000, 4000, 6000), struct.pack('<4I', 10000, 12000, 4000, 6000))


def sg_files(d):
    sd = d if os.path.basename(os.path.normpath(d)).lower() == 'streamgroups' else os.path.join(d, 'streamgroups')
    return sorted(glob.glob(os.path.join(sd, '*.drm')))


def cmd_sections(dirs):
    import navgraph_probe as NP
    for d in dirs:
        fs = sg_files(d); tot = collections.Counter()
        print('== %s: %d streamgroup DRMs' % (d, len(fs)))
        print('%-52s %5s %5s %5s %5s %5s %5s %5s %5s %s' % ('file', 'secs', 'dtp', 'dtp>=', 'chart', 'obj', 'scr', 'mat', 'lib', 'nav'))
        for p in fs:
            D = DW.read(open(p, 'rb').read(), 'le')
            c = collections.Counter(s.type for s in D.sections)
            new = sum(1 for s in D.sections if s.type == 7 and s.id >= 20000)
            ch = sum(1 for s in D.sections if s.type == 7 and len(s.data) >= 0x1c and bytes(s.data[0xc:0x1c]) in CHART)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    nav = NP.image_of(p, 'le')[1] is not None
            except Exception as e:
                nav = 'err %s' % type(e).__name__
            row = dict(secs=len(D.sections), dtp=c[7], new=new, chart=ch, obj=c[11], scr=c[8], mat=c[10], lib=c[9])
            tot.update(row); tot['nav'] += nav is True
            print('%-52s %5d %5d %5d %5d %5d %5d %5d %5d %s' % (os.path.basename(p), row['secs'], row['dtp'], row['new'], row['chart'],
                                                             row['obj'], row['scr'], row['mat'], row['lib'], nav))
            print('    types %s' % dict(sorted(c.items())))
        print('TOTAL %s: %s' % (d, dict(sorted(tot.items()))))


def dlc_of(f):
    x = f['xbox'].replace('\\', '/').lower()
    return 'DLC1' if '/ack10/' in x else 'DLC2' if '/ack11/' in x else '?'


def area_of(name, units):
    base = name[:-4]
    u = max((u for u in units if base.startswith(u + '_')), key=len, default=None)
    return base[len(u) + 1:] if u else base


def cmd_invsum(a):
    def opt(k):
        if k in a:
            j = a.index(k); v = a[j + 1]; del a[j:j + 2]; return v
    basep, outp = opt('--base'), opt('--out')
    inv = json.load(open(a[0]))
    base = {r['mat']: r for r in json.load(open(basep))} if basep else {}
    st = collections.Counter(); rows = []
    for i, r in enumerate(inv, 1):
        dl = sorted({dlc_of(f) for f in r['files']})
        sgf = [f for f in r['files'] if f.get('sg')]; top = [f for f in r['files'] if not f.get('sg')]
        kind = 'sg-only' if sgf and not top else 'mixed' if sgf else 'top-only'
        part = ''
        if base and r['mat'] in base:
            btop = {f['name'] for f in base[r['mat']]['files'] if not f.get('sg')}
            gone = btop - {f['name'] for f in top}
            if gone and sgf: part = 'top-level copies translated by the trees (%s), streamgroup copies not' % ' '.join(sorted(gone))
        for d in dl:
            st[(d, 'materials')] += 1; st[(d, kind)] += 1; st[(d, 'lit' if r['lit'] else 'unlit')] += 1
            if part: st[(d, 'partial')] += 1
        areas = sorted({area_of(f['name'], r['units']) for f in sgf})
        rows.append([i, r['score'], '+'.join(dl), r['mat'], r['xlib'], r['cls'], 'lit' if r['lit'] else 'unlit',
                     '%d/%d' % tuple(r['vs']), r['vscls'], ' '.join(r['units']), ' '.join(areas), kind,
                     ' '.join(('streamgroups/' if f.get('sg') else '') + f['name'] for f in r['files']), part])
    print('%s: %d materials on surrogates' % (a[0], len(inv)))
    for d in ('DLC1', 'DLC2', '?'):
        if st[(d, 'materials')]:
            print('  %s: %d materials (lit %d / unlit %d): streamgroup-only %d, mixed %d, top-level only %d%s' % (
                d, st[(d, 'materials')], st[(d, 'lit')], st[(d, 'unlit')], st[(d, 'sg-only')], st[(d, 'mixed')], st[(d, 'top-only')],
                ', partial (top translated, streamgroup not) %d' % st[(d, 'partial')] if base else ''))
    libs = collections.Counter(r[4] for r in rows)
    print('  Xbox libs: %d; streamgroup-only / mixed Xbox libs: %d' % (len(libs), len({r[4] for r in rows if r[11] != 'top-only'})))
    vsc = collections.Counter(r[8] for r in rows)
    print('  Xbox VS classes of the materials: %s' % dict(sorted(vsc.items())))
    for r in rows:
        print('%3d %6.2f %-9s mat %5d xlib %4d %-2s %-5s VS %-9s %-4s %-8s units [%s] areas [%s]%s' % (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[11], r[9], r[10], ('  ** ' + r[13]) if r[13] else ''))
    if outp:
        with open(outp, 'w', encoding='utf-8', newline='\n') as t:
            t.write('\t'.join(['rank', 'score', 'dlc', 'mat', 'xlib', 'cls', 'lit', 'vs_xbox/pc', 'vs_cls', 'units', 'areas', 'kind', 'files', 'note']) + '\n')
            for r in rows: t.write('\t'.join(str(x) for x in r) + '\n')
        print('wrote %s' % outp)


def cmd_float(sgd, outd):
    sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'cine'))
    import float_fix as FF
    from wave_swap import raw_dlc
    FF.raw_dlc = lambda f: raw_dlc('streamgroups\\' + f)       # the step looks up the bare name (top folder only)
    sgd = sgd if os.path.basename(os.path.normpath(sgd)).lower() == 'streamgroups' else os.path.join(sgd, 'streamgroups')
    # coverage first (float_fix skips silently): Xbox source found, same DTP count, new DTPs of the same size
    import drm
    cov = collections.Counter()
    for p in sg_files(sgd):
        f = os.path.basename(p); xr, _ = FF.raw_dlc(f)
        if xr is None: cov['no Xbox source'] += 1; print('   %s: no Xbox source' % f); continue
        X = [s for s in drm.sections_with_data(drm.cdrm_decode(xr, 'be'), 'be')[1] if s['type'] == 7]
        P = [s for s in DW.read(open(p, 'rb').read(), 'le').sections if s.type == 7]
        if len(X) != len(P): cov['DTP count differs (skipped by the step)'] += 1; continue
        cov['files checked'] += 1
        cov['new DTPs, same size'] += sum(1 for x, q in zip(X, P) if x['id'] >= 20000 and len(x['data']) == len(q.data))
        cov['DTP words checked'] += sum(len(x['data']) // 4 for x, q in zip(X, P) if x['id'] >= 20000 and len(x['data']) == len(q.data))
    print('%s coverage: %s' % (sgd, dict(cov)))
    for mode in ('s16', 'raw'):
        od = os.path.join(outd, mode)
        if os.path.realpath(od).startswith(os.path.realpath(sgd)): sys.exit('OUT_DIR inside the input - refused')
        saved = sys.argv
        try:
            sys.argv = ['float_fix.py', sgd, od, mode]
            with contextlib.redirect_stdout(io.StringIO()):
                FF.main()
        finally:
            sys.argv = saved
        log = json.load(open(os.path.join(od, 'float_fix_log.json')))
        byf = collections.Counter(l['file'] for l in log)
        byd = collections.Counter((l['file'], l['dtp']) for l in log)
        print('%s mode %s: %d words in %d files / %d DTPs' % (sgd, mode, len(log), len(byf), len(byd)))
        for (f, dtp), n in sorted(byd.items()):
            ex = [l for l in log if l['file'] == f and l['dtp'] == dtp][:3]
            print('   %-52s DTP %6d: %3d words, e.g. %s' % (f, dtp, n, '; '.join('%s %s->%s (%s)' % (l['off'], l['prima'], l['dopo'], l['valore']) for l in ex)))


def cmd_natives(sgd):
    import script_missing_native_fix as MN
    nat = MN.native_types('pc'); tot = 0
    for p in sg_files(sgd):
        rep = []
        new = MN.process('streamgroups/' + os.path.basename(p), p, nat, 'all', rep)
        n = sum(1 for l in rep if l.startswith('FIX'))
        tot += n
        print('%-52s calls into missing natives: %d%s' % (os.path.basename(p), n, '' if new is None else ' (would change the file)'))
        for l in rep: print('    ' + l)
    print('TOTAL %s: %d' % (sgd, tot))


def cmd_where(a):
    """where INV.json INTROS.json [--top N] [--labels]: per material of the inventory (rank order) and per streamgroup
    file: the terrain draws with that material (type-12 terrain sections, tools/shader_tour.terrain_draws: local bbox,
    vertex count), the bbox of the unit's intros (same frame? - a hint, not a proof) and the 3 intros nearest to the
    draw centre (`player.goto <intro id>`)."""
    import numpy as np, shader_tour as ST, terrain_convert as TC
    top = 1000; outp = None
    if '--top' in a: j = a.index('--top'); top = int(a[j + 1]); del a[j:j + 2]
    if '--out' in a: j = a.index('--out'); outp = a[j + 1]; del a[j:j + 2]
    inv = json.load(open(a[0])); I = json.load(open(a[1]))
    tsv = []; vsum = collections.Counter()
    labels = {}
    for key, lab, tree, mats in ST.GROUPS:
        for m in mats: labels.setdefault(m, '%s (%s)' % (lab, tree))
    cache = {}
    for i, r in enumerate(inv[:top], 1):
        print('%3d mat %5d xlib %4d %s %s  label: %s' % (i, r['mat'], r['xlib'], r['cls'], 'lit' if r['lit'] else 'unlit',
                                                         labels.get(r['mat'], '-')))
        for f in r['files']:
            p = f['pc']
            if p not in cache:
                if len(cache) > 6: cache.clear()
                cache[p] = ST.load(p)
            D = cache[p]; draws = []
            for s in D.sections:
                if s.type != 12 or not TC.is_terrain(s.data): continue
                try: draws += [(s.id,) + tuple(d) for d in ST.terrain_draws(s, {r['mat']})]
                except Exception as ex: print('     %s section %d: %s' % (f['name'], s.id, ex))
            base = f['name'][:-4]
            unit = max((u for u in I if base == u or base.startswith(u + '_')), key=len, default=None)
            if not draws:
                print('   %-50s no terrain draw (object / mesh use)' % (('streamgroups/' if f.get('sg') else '') + f['name'])); continue
            lo = np.min([d[2] for d in draws], 0); hi = np.max([d[3] for d in draws], 0); nv = sum(d[4] for d in draws)
            c = (lo + hi) / 2; near = []
            line ='   %-50s %d draws, %d vertices, bbox (%.0f %.0f %.0f)-(%.0f %.0f %.0f)' % (
                ('streamgroups/' if f.get('sg') else '') + f['name'], len(draws), nv, *lo, *hi)
            if unit:
                ip = np.array([y['pos'] for y in I[unit]['intros']])
                ilo, ihi = ip.min(0), ip.max(0)
                inside = bool(np.all(c >= ilo - 2000) and np.all(c <= ihi + 2000))
                near = sorted(((float(np.linalg.norm(np.array(y['pos']) - c)), y) for y in I[unit]['intros']), key=lambda q: q[0])[:3]
                line += '\n      unit %s intro bbox (%.0f %.0f %.0f)-(%.0f %.0f %.0f), draw centre %s it; nearest: %s' % (
                    unit, *ilo, *ihi, 'inside' if inside else 'OUTSIDE',
                    ', '.join('%d %s (%.0f)' % (y['uid'], y['name'], dd) for dd, y in near))
            print(line)
            vsum[r['mat']] += nv
            tsv.append([i, r['mat'], r['xlib'], labels.get(r['mat'], ''), ('streamgroups/' if f.get('sg') else '') + f['name'],
                        unit or '', len(draws), nv, '%.0f %.0f %.0f' % tuple(c),
                        ' '.join('%d:%s' % (y['uid'], y['name']) for dd, y in near)])
    print('terrain vertices per material (most first):')
    for m, n in vsum.most_common(): print('   mat %5d %7d' % (m, n))
    if outp:
        with open(outp, 'w', encoding='utf-8', newline='\n') as t:
            t.write('rank\tmat\txlib\tlabel\tfile\tunit\tdraws\tvertices\tcentre\tnearest_intros\n')
            for row in tsv: t.write('\t'.join(str(x) for x in row) + '\n')
        print('wrote %s' % outp)


def cmd_shots(a):
    """shots WHERE.tsv STATE.json [--top N] [--out OUT.tsv]: screenshot list for the Xenia / PC comparison - per material
    the area file with the most terrain vertices (the biggest visible surface), its unit and nearest intros, ordered by
    the material's total terrain vertices; status from a tools/tu_batch.py run state (new lib or refusal reason)"""
    top = 25; outp = None
    if '--top' in a: j = a.index('--top'); top = int(a[j + 1]); del a[j:j + 2]
    if '--out' in a: j = a.index('--out'); outp = a[j + 1]; del a[j:j + 2]
    rows = [l.rstrip('\n').split('\t') for l in open(a[0], encoding='utf-8')][1:]
    st = json.load(open(a[1]))
    status = {}
    for g in st['groups']:
        for m in g['mats']:
            status[m] = ('lib %d' % g['new']) if g['status'] == 'done' else 'refused: %s' % g.get('note', '')[:90]
    tot = collections.Counter(); best = {}; nfiles = collections.Counter()
    for r in rows:
        m = int(r[1]); v = int(r[7]); tot[m] += v; nfiles[m] += 1
        if m not in best or v > int(best[m][7]): best[m] = r
    out = []
    for k, (m, v) in enumerate(tot.most_common(top), 1):
        r = best[m]
        out.append([k, m, r[2], r[3], v, nfiles[m], r[4], r[5], r[7], r[8], r[9], status.get(m, 'not in run')])
        print('%2d mat %5d xlib %s %-30s total %7d vertices in %d files; best %s (unit %s, %s vertices, centre %s) nearest %s | %s' % (
            k, m, r[2], r[3][:30], v, nfiles[m], r[4], r[5], r[7], r[8], r[9], status.get(m, 'not in run')))
    if outp:
        with open(outp, 'w', encoding='utf-8', newline='\n') as t:
            t.write('rank\tmat\txlib\tlabel\tvertices_total\tfiles\tbest_file\tunit\tbest_vertices\tcentre\tnearest_intros\tstatus_51x\n')
            for row in out: t.write('\t'.join(str(x) for x in row) + '\n')
        print('wrote %s' % outp)


def cmd_diff(a):
    """diff INV.json STATE.json TREE: every DRM of TREE/mods against its source (the effective file of the inventory)
    section by section: the changed sections must be exactly the type-10 materials of the done groups in that file,
    the added sections exactly their new type-9 libs; everything else byte-identical (data + relocations)"""
    import tu_batch as TB
    inv = json.load(open(a[0])); st = json.load(open(a[1])); tree = a[2]
    src = {}
    for r in inv:
        for f in r['files']: src[os.path.normcase(os.path.abspath(TB.tree_dst(tree, f['pc'])))] = f['pc']
    want_mat = collections.defaultdict(set); want_lib = collections.defaultdict(set)
    for g in st['groups']:
        if g['status'] != 'done': continue
        for fn in g['files']:
            want_lib[fn].add(g['new'])
            for m in g['mats']: want_mat[fn].add(m)
    tot = collections.Counter()
    for dp, dn, fs in os.walk(os.path.join(tree, 'mods')):
        for fn in sorted(fs):
            if not fn.lower().endswith('.drm'): continue
            p = os.path.join(dp, fn); s = src.get(os.path.normcase(os.path.abspath(p)))
            if s is None: print('%s: no source in the inventory' % fn); tot['no source'] += 1; continue
            A = DW.read(open(s, 'rb').read(), 'le'); B = DW.read(open(p, 'rb').read(), 'le')
            ka = {(x.type, x.id): x for x in A.sections}; kb = {(x.type, x.id): x for x in B.sections}
            changed = sorted(k for k in set(ka) & set(kb) if (ka[k].data, ka[k].reloc) != (kb[k].data, kb[k].reloc))
            added = sorted(set(kb) - set(ka)); removed = sorted(set(ka) - set(kb))
            # materials of done groups whose copy in this file was a surrogate (the group's files list names it)
            mats_ok = {k for k in changed if k[0] == 10 and k[1] in want_mat[fn.lower()]}
            libs_ok = {k for k in added if k[0] == 9 and k[1] in want_lib[fn.lower()]}
            bad = [k for k in changed if k not in mats_ok] + [k for k in added if k not in libs_ok] + removed
            same_order = [(x.type, x.id) for x in A.sections] == [(x.type, x.id) for x in B.sections if (x.type, x.id) not in libs_ok]
            tot['files'] += 1; tot['materials changed'] += len(mats_ok); tot['libs added'] += len(libs_ok); tot['unexpected'] += len(bad)
            tot['section order kept'] += same_order
            print('%-52s src %s: %d materials %s, %d libs %s, unexpected %s, other order kept %s' % (
                ('streamgroups/' if os.path.basename(dp).lower() == 'streamgroups' else '') + fn, os.path.relpath(s, ROOT),
                len(mats_ok), sorted(k[1] for k in mats_ok), len(libs_ok), sorted(k[1] for k in libs_ok), bad or 0, same_order))
    print('TOTAL %s' % dict(tot))


def cmd_mdinv(a):
    """mdinv INV.json STATE.json WHERE.tsv: the ranked inventory as Markdown table rows (for the finding file): rank,
    DLC, material, Xbox lib / class / lit, streamgroup-only, units / areas, terrain vertices, status of the run"""
    inv = json.load(open(a[0])); st = json.load(open(a[1]))
    vs = collections.Counter()
    for l in list(open(a[2], encoding='utf-8'))[1:]:
        t = l.rstrip('\n').split('\t'); vs[int(t[1])] += int(t[7])
    status = {}
    for g in st['groups']:
        for m in g['mats']:
            status[m] = ('**%d**' % g['new']) if g['status'] == 'done' else 'refused: %s' % g.get('note', '').split(': ', 1)[-1][:70]
    print('| # | DLC | mat | Xbox lib | lit | where | units / areas | terrain vertices | 51x |')
    print('|---|---|---|---|---|---|---|---|---|')
    for i, r in enumerate(inv, 1):
        dl = '+'.join(sorted({dlc_of(f) for f in r['files']}))
        sgf = [f for f in r['files'] if f.get('sg')]; top = [f for f in r['files'] if not f.get('sg')]
        kind = 'SG only' if sgf and not top else 'SG + top' if sgf else 'top'
        areas = sorted({area_of(f['name'], r['units']) for f in sgf})
        units = sorted({u for u in r['units'] if any(f['name'].startswith(u + '_') for f in sgf)}) if sgf else []
        topn = ' '.join(f['name'][:-4] for f in top)
        where = '; '.join(x for x in ('%s: %s' % (' '.join(units), ' '.join(areas)) if sgf else '', topn) if x)
        print('| %d | %s | %d | %d %s | %s | %s | %s | %d | %s |' % (i, dl, r['mat'], r['xlib'], r['cls'], 'lit' if r['lit'] else 'unlit',
                                                                kind, where, vs.get(r['mat'], 0), status.get(r['mat'], '-')))


def cmd_libcmp(pairs):
    """libcmp A.drm:LIB B.drm:LIB [...]: slot by slot, are the shader blobs of two PC libs byte-identical? (a new lib of
    this run against the 50m / 50n lib that the same Xbox lib got in the top-level copies)"""
    import shaderlib as SL
    for pr in pairs:
        (fa, la), (fb, lb) = [(x.rsplit(':', 1)[0], int(x.rsplit(':', 1)[1])) for x in pr.split('=')]
        A = {(s.type, s.id): s for s in DW.read(open(fa, 'rb').read(), 'le').sections}
        B = {(s.type, s.id): s for s in DW.read(open(fb, 'rb').read(), 'le').sections}
        if (9, la) not in A or (9, lb) not in B: print('%s: lib missing' % pr); continue
        LA, LB = SL.parse(A[(9, la)].data, 'le'), SL.parse(B[(9, lb)].data, 'le')
        res = []
        for k in range(max(len(LA['slots']), len(LB['slots']))):
            oa = LA['slots'][k] if k < len(LA['slots']) else None; ob = LB['slots'][k] if k < len(LB['slots']) else None
            if oa in (None, 0xffffffff) or ob in (None, 0xffffffff): res.append('%d:%s' % (k, 'both empty' if oa == ob else 'one empty')); continue
            res.append('%d:%s' % (k, 'same' if LA['entries'][oa]['blob'] == LB['entries'][ob]['blob'] else 'DIFF'))
        print('%s lib %d vs %s lib %d: %d slots, identical blobs %d - %s' % (os.path.basename(fa), la, os.path.basename(fb), lb,
              len(res), sum(r.endswith('same') for r in res), ' '.join(res)))


def cmd_origin(target, cands):
    """which candidate trees hold a byte-identical copy of each streamgroup DRM of TARGET (md5)"""
    import hashlib
    md = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    cm = {}
    for c in cands:
        for p in sg_files(c): cm.setdefault((os.path.basename(p).lower(), md(p)), []).append(c)
    st = collections.Counter()
    for p in sg_files(target):
        h = md(p); hit = cm.get((os.path.basename(p).lower(), h), [])
        st['identical in a candidate' if hit else 'no identical candidate'] += 1
        print('%-52s %s  %s' % (os.path.basename(p), h, ' '.join(hit) or '-'))
    print('TOTAL %s: %s' % (target, dict(st)))


def main(a):
    if not a: sys.exit(__doc__)
    if a[0] == 'origin': cmd_origin(a[1], a[2:])
    elif a[0] == 'where': cmd_where(a[1:])
    elif a[0] == 'shots': cmd_shots(a[1:])
    elif a[0] == 'diff': cmd_diff(a[1:])
    elif a[0] == 'mdinv': cmd_mdinv(a[1:])
    elif a[0] == 'libcmp': cmd_libcmp(a[1:])
    elif a[0] == 'sections': cmd_sections(a[1:])
    elif a[0] == 'invsum': cmd_invsum(a[1:])
    elif a[0] == 'float': cmd_float(a[1], a[2])
    elif a[0] == 'natives': cmd_natives(a[1])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
