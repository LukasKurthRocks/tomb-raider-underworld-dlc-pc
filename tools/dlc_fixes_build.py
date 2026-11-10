"""Stage 2b of the rebuild (DLC 1; DLC 2 with --pack pack11): apply upstream's data fixes, in order, to a copy of the
stage-2a tree.

Each fix is one function below, in the order of docs/WINDOWS_REBUILD.md finding 20; it reads the current OUT tree and
replaces the files it fixes there. Upstream's own scripts in work/ws/ are called, not copied.

  cine   B44/B45: cutscene command lists and effect DTPs of every cinstream/*.drm (DLC 1: pdlc1_010_intro,
         pdlc1_030_finale)
         (work/ws/cine/build_cine.py; command rules validated 106/106 on the base game, effect rules learned from
         the base pairs)
  float  B46/B47: float words of the new DLC DTPs (id >= 20000) - work/ws/cine/float_fix.py, mode s16 then raw
         (top folder only, as upstream's script)
  tag404 B33: raft/grapple ring records (tag 0x404), word at +4 raw in the new DLC DTPs (learned from B138)
  cloth  (ours, finding 43) cloth iteration counts of the new DLC DTPs back to s32 (DLC 2 `co_dlc_lara*`: 262 144
         instead of 4 passes made the intro run at about one frame per second)
  uipath (ours, finding 43) UI timeline target paths in new DLC scripts = member Symbols in inline u16 arrays:
         PC Symbols in Xbox element order (tools/script_u16array_fix.py; DLC 2 crashed after the intro)
  uitext (ours, finding 43) UI text elements and the hint list of new DLC scripts: string ids (Xbox high u16, taken
         for Symbols by the converter) -> PC string ids, colour s32 (tools/script_uitext_fix.py; empty hint box)
  postfix upstream's tools/dlc1_postfix.py steps 1-2: streamgroup name tables (save hang) and type-0 name strings
  analog upstream's tools/analog_word_fix.py: near-clone DTPs get the base PC bytes (each word checked against B138)
  statechart (ours, finding 43) state charts, record tables and id lists of the new DLC objects: the DLC 2 player
         chart (doppelganger_casual DTP 20212) by the typed five steps of tools/statechart_fix_all.py, then every
         such DTP word by word from the base game's Xbox/PC pairs (tools/statechart_fix_tree.py /
         statechart_twins.py; the rock vein's conditions 607 / 608 were unreachable)
  twins, childids, translist, actlist, condlist, eventlist, reclist, fadeslots, animfx, markup, vmliteral (ours,
         2026-11-01/02, tests 47 / 48 / 48c-48m / 50a) the structure fixes of tools/dlc_struct_fixes.py, one step each:
         base-twin byte-order truth for every same-size section of the DLC 2 player files
         (tools/dlc_structure_audit.py, ~20 min), object child id list by name, player-chart transition lists, state
         records / activity entries and the condition records every transition lists, object event lists, model record list stride 36 -> 40, own fade pixel-shader libraries of the TU-drawn
         player objects, anim event lists, object markup records, VM literals
  objtex, objrec, objid (ours, 2026-11-04, findings 47 / 48) after markup, also tools/dlc_struct_fixes.py: texture group
         counts of the object data DTP as the Xbox u32 (F16 machine_column crash), the 0x17c particle records by the 66
         proven byte classes (F3 / B24 crash tru+0x42e62), the player data breath-sound ids +0x94 / +0x98 as one u32
         (doppelganger_casual 0x68f40000); only words whose PC bytes are another byte order of the Xbox word, each
         written DRM proven (only the planned bytes differ, headers / relocations identical, re-check 0)
  chunkrec, exttuning, thrallext, meleelink, genintro, costumedtp, dspkind (ours, 2026-11-08: the data fixes of
         2026-11-07) after objid, also tools/dlc_struct_fixes.py: chunkdoll piece records (chunkdoll_record_fix), the DLC 2
         player tuning DTP 22497 targeter + K9 pair words (player_ext_tuning_fix), the thrall extension objects of data
         type 0x3d (thrall_extension_fix), melee attack records incl. the link-only combo records (melee_link_record_fix),
         pool generator intro data (generator_intro_fix; DLC 1 too), costume model u16 arrays / list counts
         (costume_dtp_fix; DLC 1 and the costume packs), the SoundPlex DSP kind of dlc_caverns_hall DTP 23469
         (soundplex_dsp_kind_fix); each typed by its proven rule, only words whose PC bytes are another byte order of
         the Xbox word, each written DRM proven; an UNEXPECTED word stops the build
  fadecard, uberanim, fxrec, sgmesh, introtyped, leveltwin, basecopy (ours, 2026-11-08, 17n: the typed families of the
         night 07./08.11.) after dspkind, also tools/dlc_struct_fixes.py with tools/typed_family_fix.py: fade-record DTPs
         of the cine cards, uber play-anim words, FX particle record words, streamgroup mesh lists, unit DTP intro
         data, the Level section of a unit without a same-size base twin (dlc_yggdrasil_end), DTPs whose Xbox payload
         is the base Xbox DTP of the same id (= the PC base copy, e.g. the colour LUT 18577); each rule proven on the
         base pairs once per run, only words whose PC bytes are another byte order of the Xbox word, each written DRM
         proven
  fxrecread (ours, 2026-11-08, 18e) after basecopy, also tools/typed_family_fix.py: the 0x17c particle record words of
         the object data DTP at the 12 offsets objrec does not rule, by the reads of tru.exe 0x543f70 (u8 fields in
         place, +0x58 / +0x5c / +0x160 u16); introtyped takes the unit-DTP pointer-path table of 77 base units since 18e
  seqrepeat (ours, 2026-11-05, finding 49) after objid, also tools/dlc_struct_fixes.py: the word data +0xc of SoundPlex
         Sequence nodes (s8 repeat + 3 bytes) raw = the Xbox bytes (tools/soundplex_sequence_fix.py; the converter
         u32-swapped repeat 1 to 0 = endless, the DLC 2 doppelganger's groan); a word that is no byte order of the
         Xbox word stops the build
  navraw (ours, 2026-11-06, finding 50) after seqrepeat, also tools/dlc_struct_fixes.py: the NavPower NavGraph image of
         every unit (Level+0x60) raw = the Xbox bytes, the count word after resource 1 u32-swapped
         (tools/navgraph_raw_fix.py; base proof once per process, a unit it cannot pair is left alone and fails the
         check; DRMs without an image - e.g. the costume packs - are not touched)
  objevent, idword, animlist, fxnode, statevm, chartid (ours, 2026-11-03, finding 44) the converter fault families
         that the crash dumps of tests 50d-50j uncovered (tools/converter_faults_fix.py, rules proven on x_lara /
         pc_lara): object event list words and their sub-0x32 id word, anim event list words, effect node headers and
         type-1 ids, state-VM code words, state-chart id values of types 3 / 5. Sections paired by position; base-mapped
         sections (renumbered base DTPs) are reported, never changed; any word a rule cannot explain stops the build
  uirecord (ours, finding 43) UI text element records of the new DLC scripts by Crystal's PC conversion rules (w1/w3
         as u32 instead of swapped halves, the PC word 0x00010000, -1.0f) - tools/script_records_dlc.py; after the
         other script fixes, so it sees the final scripts (it only touches type-8 records; test 34, played
         2026-10-30). The merged g_pda.drm of the DLC 2 tree is left out (not installed, finding 40)
  achievement (ours, finding 43, test 40) script calls into the title update's achievement natives f16-f20, which
         the PC exe lacks (16 natives instead of 21): call sequence -> its line marker, relocation dropped
         (tools/script_missing_native_fix.py; DLC 1 treasure room, DLC 2 halls and Yggdrasil end; 1 + 10 calls).
         It only touches script code words and their relocations
  scriptclash (ours, findings 45 / 46, 2026-11-04) DLC script classes re-authored under the id of an always-resident
         PC generalbank script with another instance layout (DLC 2 thrall base 12433: 8 instead of 16 bytes - the
         unload crash tru+0x1976a3) get their own PC id from docs/data/script_clash_ids.json (12433 -> 26884), by
         rule (tools/script_clash_fix.py: resident id, no native, other instance layout, a DLC class derives from
         it); section ids and type-8 id references only. Last: it renumbers ids, so it sees the final sections

Report: <OUT>/../fixes_report.json (per fix: files, log lines).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dlc_fixes_build.py SRC_MODS_DIR OUT_MODS_DIR [--only fix,fix] [--pack pack11]
  e.g. work/rebuild/stage2a/mods work/rebuild/stage2b/mods
  --pack pack11 for a DLC 2 tree: Xbox sources of names that exist in several packs come from pack11 (finding 38)
"""
import sys, os, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(HERE, '..', 'work', 'ws')


def fix_cine(out):
    """every cinstream/*.drm of the tree (DLC 1: pdlc1_010_intro, pdlc1_030_finale; DLC 2: pdlc2_000 .. 045).
    build_cine.build reads its Xbox source from PACKS[0] (pack10); for another pack its PACKS is pointed at that pack."""
    sys.path.insert(0, os.path.join(WS, 'cine'))
    import build_cine as BC, fxdtp as F
    from convert_dlc import PACKS
    first = os.environ.get('TRUDLC_PACK_FIRST')
    if first: BC.PACKS = [p for p in PACKS if p.endswith('/%s.000' % first)] or PACKS
    tab = F.learn(F.samples())
    log, files = [], []
    cdir = os.path.join(out, 'cinstream')
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if not f.endswith('.drm'): continue
        nm = f[:-4]; p = os.path.join(cdir, f); tmp = p + '.new'
        log += BC.build(nm, p, tmp, tab)
        os.replace(tmp, p); files.append('cinstream/' + f)
    return {'files': files, 'log': log}


def fix_float(out):
    """B46/B47: work/ws/cine/float_fix.py in its two modes - 's16' (float words whose u16 halves are swapped, certain)
    then 'raw' (floats still in Xbox byte order, probable). It only looks at DRMs in the top folder of the tree and
    writes changed files to a separate folder; they are copied back here."""
    sys.path.insert(0, os.path.join(WS, 'cine'))
    import float_fix as FF
    files, log = [], []
    for mode in ('s16', 'raw'):
        tmp = os.path.join(os.path.dirname(os.path.abspath(out)), 'float_%s' % mode)
        if os.path.isdir(tmp): shutil.rmtree(tmp)
        saved = sys.argv
        try:
            sys.argv = ['float_fix.py', out, tmp, mode]
            FF.main()
        finally:
            sys.argv = saved
        for e in json.load(open(os.path.join(tmp, 'float_fix_log.json'))):
            log.append('%s %s DTP %s %s: %s -> %s (%s)' % (mode, e['file'], e['dtp'], e['off'], e['prima'], e['dopo'], e['valore']))
        for f in sorted(os.listdir(tmp)):
            if f.endswith('.drm'):
                shutil.copyfile(os.path.join(tmp, f), os.path.join(out, f)); files.append(f)
        shutil.rmtree(tmp)
    return {'files': sorted(set(files)), 'log': log}


def fix_tag404(out):
    """B33: raft/grapple ring records (DTP record tag 0x404): the word at +4 keeps the raw Xbox bytes - only in the
    new DLC DTPs (id >= 20000); in the base-game DTP 2154 of the costume DRMs B138 keeps the converted (s32) value.
    Learned from B138 with tools/tag404_check.py (finding 23); upstream FINDINGS.md: 'the enable byte at +4 must stay
    raw'. Every DRM of the tree, sub folders included."""
    import struct
    sys.path.insert(0, HERE)
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    tag = struct.pack('>I', 0x404)
    files, log = [], []
    for rel, path in sorted(DA.overlay([os.path.abspath(out)], None).items()):
        xs = DA.xsecs(rel)
        if xs is None: continue
        D = DW.read(open(path, 'rb').read(), 'le')
        changed = False
        for x, i in DA.section_pairs(xs, D):
            sec = D.sections[i]
            if x['type'] != 7 or sec.id < 20000 or len(sec.data) != len(x['data']): continue
            xd = x['data']; xr = R.parse(x['reloc'], 'be'); sl = set(xr.pointer_offsets()) | set(xr.id_offsets())
            pd = bytearray(sec.data)
            for o in range(0, len(xd) - 8, 4):
                if xd[o:o + 4] != tag or o in sl or o + 4 in sl: continue
                if pd[o + 4:o + 8] != xd[o + 4:o + 8]:
                    log.append('%s DTP %d +%#x: %s -> %s' % (rel, sec.id, o + 4, pd[o + 4:o + 8].hex(), xd[o + 4:o + 8].hex()))
                    pd[o + 4:o + 8] = xd[o + 4:o + 8]; changed = True
            sec.data = bytes(pd)
        if changed:
            open(path, 'wb').write(DW.cdrm_encode(D.write('le'), 'le')); files.append(rel)
    return {'files': files, 'log': log}


def fix_cloth(out):
    """Cloth parameter blocks of the character-model DTPs (finding 43, DLC 2 slow intro): Xbox layout
    {u32, ptr, u32, ptr, f32, f32, u32 iterations, u32, u32, u32, f32, ...}; the engine copies the iteration count to
    the simulation object (+0x30) and repeats its constraint / collision pass that often. The learned type-7 table
    encoded the count of the third block of `co_dlc_lara` / `co_dlc_lara_f` (DTPs 24717 / 25808) as two s16 halves
    (4 -> 0x00040000 = 262 144 passes, about 1 s per frame); every other block of the same DTP and the B138 / base
    blocks use s32. A word is set to s32 only when the whole block matches: pointer slots at -20 and -12, small
    integers (< 0x100) at the count and at +4 / +8 / +12, and the converted word is exactly the s16 encoding.
    New DLC DTPs (id >= 20000) only; every DRM of the tree, sub folders included."""
    import struct
    sys.path.insert(0, HERE)
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    files, log = [], []
    for rel, path in sorted(DA.overlay([os.path.abspath(out)], None).items()):
        xs = DA.xsecs(rel)
        if xs is None: continue
        D = DW.read(open(path, 'rb').read(), 'le')
        changed = False
        for x, i in DA.section_pairs(xs, D):
            sec = D.sections[i]
            if x['type'] != 7 or sec.id < 20000 or len(sec.data) != len(x['data']): continue
            xd = x['data']; xr = R.parse(x['reloc'], 'be'); ptrs = set(xr.pointer_offsets()); sl = ptrs | set(xr.id_offsets())
            pd = bytearray(sec.data)
            for o in range(20, len(xd) - 15, 4):          # the block needs o + 16 <= len
                if o - 20 not in ptrs or o - 12 not in ptrs or any(k in sl for k in (o - 8, o - 4, o, o + 4, o + 8, o + 12)): continue
                v = [struct.unpack_from('>I', xd, o + d)[0] for d in (0, 4, 8, 12)]
                if not all(0 < w < 0x100 for w in v): continue
                want = struct.pack('<I', v[0]); xw = xd[o:o + 4]
                # only the defect itself: the word as two swapped u16 halves (e.g. 00000400) - any other encoding
                # (raw bytes kept on purpose, e.g. by fix tag404) stays
                if pd[o:o + 4] == xw[1::-1] + xw[:1:-1] and pd[o:o + 4] != want:
                    log.append('%s DTP %d +%#x: %s -> %s (cloth iterations %d)' % (rel, sec.id, o, pd[o:o + 4].hex(), want.hex(), v[0]))
                    pd[o:o + 4] = want; changed = True
            sec.data = bytes(pd)
        if changed:
            open(path, 'wb').write(DW.cdrm_encode(D.write('le'), 'le')); files.append(rel)
    return {'files': files, 'log': log}


def _write(out, rel, data):
    q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(data)


def fix_uipath(out, srcs=None):
    """UI timeline target paths of the new DLC scripts (finding 43): inline u16 arrays of member Symbols that the
    converter swapped as s32 with Xbox values; the engine's path lookup then returned a stack address as the target
    (crash one second after the DLC 2 intro). tools/script_u16array_fix.process, every DRM of the tree in place.
    Both DLCs since 2026-10-30 (owner's decision): B138 has the same 25 unmapped paths in 10 DLC 1 level DRMs (the
    never-shown Xbox "update required" message, so no crash seen) - fixed so that they cannot crash either.
    srcs: read from these folders (later wins, e.g. B138 originals + repair tree) and write changed files to out."""
    import collections
    sys.path.insert(0, HERE)
    import dtp_audit as DA, dlc_generic as DG, script_u16array_fix as UF
    ids = DG.DlcIds(); st = collections.Counter(); files, log = [], []
    for rel, path in sorted(DA.overlay([os.path.abspath(s) for s in (srcs or [out])], None).items()):
        new = UF.process(rel, path, ids, st, log)
        if new is not None:
            _write(out, rel, new); files.append(rel)
    log.append('total %s, symbol routes %s' % (dict(st), dict(ids.sym_stats)))
    return {'files': files, 'log': log}


def fix_uitext(out, srcs=None):
    """String ids of UI text elements / hint lists in the new DLC scripts (finding 43, empty DLC 2 hint box): the
    Xbox keeps them in a high u16, the converter mapped them as Symbols; they become the PC string id
    (locmap_xbox_to_pc.json of `tools/locals.py build`: environment TRUDLC_LOCMAP, else work/rebuild/stage1/).
    Both DLCs since 2026-10-30: B138 has 26 such text elements in DLC 1 (24 x the Xbox "update required" warning,
    shown on PC as "Press [Y] to pull on the grapple line", plus "Continue" and "TEST WEAPON").
    srcs: as in fix_uipath (out is read too and wins, so uipath's output is the input here)."""
    import collections, json
    sys.path.insert(0, HERE)
    import dtp_audit as DA, dlc_generic as DG, script_uitext_fix as TF
    lm = os.environ.get('TRUDLC_LOCMAP') or os.path.join(HERE, '..', 'work', 'rebuild', 'stage1', 'locmap_xbox_to_pc.json')
    if not os.path.exists(lm): raise SystemExit('uitext: no string id map %s (run tools/locals.py build first)' % lm)
    ids = DG.DlcIds(); ids._loc = {int(k): v for k, v in json.load(open(lm))['map'].items()}
    st = collections.Counter(); files, log = [], []
    dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
    for rel, path in sorted(DA.overlay(dirs, None).items()):
        new = TF.process(rel, path, ids, st, log)
        if new is not None:
            _write(out, rel, new); files.append(rel)
    log.append('total %s (map %s)' % (dict(st), os.path.relpath(lm, os.path.join(HERE, '..'))))
    return {'files': files, 'log': log}


def fix_postfix(out):
    """upstream's DLC 1 post-step tools/dlc1_postfix.py, steps 1 and 2 per DRM (called directly, so nothing is
    written to its fixed folder work/ws/converge/): streamname_fix (streamgroup name table of unit DRMs; a broken
    name made 'Create new savegame' hang) and the R12 string fixes of refs_scan (name-like strings in type-0
    sections). Step 3 (single words from work/ws/dtpkeys/out/min/log_words.tsv) is skipped: that log is not in the
    repository."""
    import collections
    sys.path.insert(0, HERE)
    import dlc1_postfix as PF
    files, log, tot = [], [], collections.Counter()
    for dp, dn, fn in os.walk(out):
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            path = os.path.join(dp, f); rel = os.path.relpath(path, out).replace(os.sep, '/')
            raw0 = open(path, 'rb').read()
            r1, n1 = PF.step_streamname(rel, raw0)
            r2, nf, nm = PF.step_strings(rel, r1)
            tot.update({'streamname_sections': n1, 'r12_fixed': nf, 'r12_manual': nm})
            if n1 or nf or nm: log.append('%s: streamname sections %d, strings fixed %d, manual %d' % (rel, n1, nf, nm))
            if r2 != raw0:
                open(path, 'wb').write(r2); files.append(rel)
    log.append('total %s' % dict(tot))
    return {'files': files, 'log': log}


REF = os.path.join(HERE, '..', '..', 'data', 'pc', 'mods')   # installed B138 tree, only for the '= B138' notes


def ref_word(rel, sid, off):
    """the 4 bytes of B138 at (DTP sid, off) or None (no reference, e.g. for DLC 2)"""
    import drm_write as DW
    p = os.path.join(REF, rel)
    if not os.path.exists(p): return None
    D = DW.read(open(p, 'rb').read(), 'le')
    s = next((s for s in D.sections if s.type == 7 and s.id == sid), None)
    return bytes(s.data[off:off + 4]) if s is not None else None


def fix_analog(out):
    """upstream's tools/analog_word_fix.py (fix mode as a library): words of DLC DTPs that are near-clones of a base
    Xbox DTP must get the base PC bytes where the Xbox bytes are equal (byte-class errors of the learned table);
    re-authored analogs are skipped. Each changed word is noted with '= B138' / '!= B138' when the reference exists."""
    sys.path.insert(0, HERE)
    import analog_word_fix as AW, dtpid_sweep as DS
    st, ids = DS.ctx(); ids.local = {}
    files, log = [], []
    for rel, path in sorted(DS.load_overlay([out]).items()):
        new, logs = AW.process(rel, path, st, ids)
        for l in logs:
            sid, ax, pid, k, old, pcw, what = l
            ref = ref_word(rel, sid, k) if what == 'fix' else None
            note = '' if ref is None else (' = B138' if ref.hex() == pcw else ' != B138 (%s)' % ref.hex())
            log.append('%s DTP %d +%#x: %s -> %s %s (analog xbox %d / pc %d)%s' % (rel, sid, k, old, pcw, what, ax, pid, note))
        if new is not None:
            open(path, 'wb').write(new); files.append(rel)
    return {'files': files, 'log': log}


def fix_statechart(out, srcs=None):
    """State-chart-like DTPs of the new DLC objects (finding 43, rock vein / state chart conversion): state charts,
    their record tables and id lists (tools/statechart_corpus.family; id >= 20000, PC section of the same size).
    tools/statechart_fix_tree: player charts (DLC 2 doppelganger_casual.drm DTP 20212: condition records of Lara's ids
    in Xbox byte order, the rock vein's markup tests 607 / 608 unreachable) get the five typed steps of
    tools/statechart_fix_all.py; then every such DTP gets the base game's own PC bytes where a base Xbox/PC pair
    proves them (tools/statechart_twins.py, levels exact + value, leave-one-pair-out precision 99.99 %); the proven
    condition-record / transition layouts of player charts are applied last. Needs work/statechart/corpus.pkl (built
    when missing) and the title-update image for player charts (TRUDLC_TU_IMAGE).
    srcs: as in fix_uitext (out is read too and wins)."""
    import collections, tempfile
    sys.path.insert(0, HERE)
    import dtp_audit as DA, statechart_fix_tree as SF
    dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
    tmpdir = os.path.join(HERE, '..', 'work', 'statechart'); os.makedirs(tmpdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='fix_', dir=tmpdir)
    st = collections.Counter(); files, log = [], []
    try:
        F = SF.Fixer(tmp)
        for rel, path in sorted(DA.overlay(dirs, None).items()):
            new = F.process(rel, path, log, st)
            if new is not None:
                _write(out, rel, new); files.append(rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log.append('total %s' % dict(st))
    return {'files': files, 'log': log}


def _struct_fix(step):
    """one step of tools/dlc_struct_fixes.py over the tree (2026-11-01, Befund-Felsrinne.md "Structure audit of the
    DLC 2 player and pipeline steps"); srcs: as in fix_uitext (out is read too and wins)"""
    def fn(out, srcs=None):
        sys.path.insert(0, HERE)
        import dlc_struct_fixes as SX
        dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
        ol = os.path.join(out, 'tr8', 'pc-w', 'objectlist.txt')
        files, log = SX.run_tree(dirs, out, [step], None, ol if os.path.exists(ol) else None)
        return {'files': files, 'log': log}
    fn.__name__ = 'fix_' + step
    return fn


# proven structure fixes after `statechart`: the base-twin pass first (byte-order errors of every same-size section of
# the DLC 2 player files), then the record layouts in the order the test trees 47 / 48c-48m were built in - a proven
# layout always has the last word
# objtex / objrec / objid (2026-11-04, agent N11): the object data DTP fixes of N7 / N8 after markup (no other step
# touches the object data DTP); tools/Invoke-TruPipeline.ps1 checks them afterwards (dlc_struct_fixes.py check)
# seqrepeat (2026-11-05, finding 49): SoundPlex Sequence repeat word +0xc raw, after objid (no other step writes the word);
# Invoke-TruPipeline.ps1 proves the rule first (soundplex_sequence_fix.py proof) and gates every tree afterwards
# (soundplex_sequence_fix.py scan + dlc_struct_fixes.py check)
# navraw (2026-11-06, finding 50): NavPower NavGraph image raw, after seqrepeat (no other step writes the image);
# before, Invoke-TruPipeline.ps1 ran it in place after dlc_fixes_build; the gates stay (navgraph_raw_fix.py scan +
# dlc_struct_fixes.py check)
# chunkrec / exttuning / thrallext / meleelink / genintro / costumedtp / dspkind (2026-11-08, agent P2 / N8): the typed data
# fixes of 2026-11-07 after objid, before seqrepeat (each writes only its own records, which no later structure step
# touches; twins / statechart run before, so the proven rule has the last word); Invoke-TruPipeline.ps1 proves the
# rules first (chunkdoll_record_fix / melee_link_record_fix / generator_intro_fix / thrall_extension_fix proof,
# costume_dtp_fix prove) and gates every tree afterwards (the tools' scans + dlc_struct_fixes.py check)
# fadecard / uberanim / fxrec / sgmesh / introtyped / leveltwin / basecopy (2026-11-08, 17n): the typed families of the
# night 07./08.11. (tools/typed_family_fix.py) after dspkind, before seqrepeat (none writes a word of the earlier data
# fixes, seqrepeat or the NavGraph image; basecopy last - the PC base copy has the last word); Invoke-TruPipeline.ps1
# proves the rules first (typed_family_fix.py proof) and gates every tree afterwards (dlc_struct_fixes.py check)
# fxrecread (2026-11-08, 18e): the 0x17c particle record words objrec does not rule, by the reads of tru.exe 0x543f70,
# after basecopy, before seqrepeat (introtyped takes the unit-DTP path table since 18e as well)
# playerblock (2026-11-10, K-5b): the player data block (DTP +0xc8, PC [0xfad764]) in the byte order of five base player
# pairs (tools/player_block_fix.py; doppelganger_casual +0x294 LT lock time), after dspkind; Invoke-TruPipeline.ps1
# proves the rule first (player_block_fix.py proof) and gates every tree (dlc_struct_fixes.py check)
STRUCT_STEPS = ('twins', 'childids', 'translist', 'actlist', 'condlist', 'eventlist', 'reclist', 'fadeslots', 'animfx',
                'markup', 'objtex', 'objrec', 'objid', 'chunkrec', 'exttuning', 'thrallext', 'meleelink', 'genintro',
                'costumedtp', 'dspkind', 'playerblock', 'fadecard', 'uberanim', 'fxrec', 'sgmesh', 'introtyped',
                'leveltwin', 'basecopy', 'fxrecread', 'seqrepeat', 'navraw', 'vmliteral')
(fix_twins, fix_childids, fix_translist, fix_actlist, fix_condlist, fix_eventlist, fix_reclist, fix_fadeslots, fix_animfx,
 fix_markup, fix_objtex, fix_objrec, fix_objid, fix_chunkrec, fix_exttuning, fix_thrallext, fix_meleelink, fix_genintro,
 fix_costumedtp, fix_dspkind, fix_playerblock, fix_fadecard, fix_uberanim, fix_fxrec, fix_sgmesh, fix_introtyped,
 fix_leveltwin, fix_basecopy, fix_fxrecread, fix_seqrepeat, fix_navraw, fix_vmliteral) = (_struct_fix(s) for s in STRUCT_STEPS)


def _fault_fix(step):
    """one converter fault family of tools/converter_faults_fix.py over the tree (2026-11-03, finding 44: the classes
    the crash dumps of tests 50d-50j found, each rule proven on x_lara / pc_lara); srcs: as in fix_uitext (out is read
    too and wins). Fails (SystemExit) on any word the rule cannot explain - nothing is guessed."""
    def fn(out, srcs=None):
        sys.path.insert(0, HERE)
        import converter_faults_fix as CF
        dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
        logs = []
        r = CF.run_tree(dirs, out, [step], log=logs.append)
        CF.summary(r, log=logs.append)
        if r['unexpected'] or r['files_without_xbox_original']:
            for l in logs: print('  ', l, flush=True)
            raise SystemExit('converter fault step %s: %d unexpected word(s), %d DRM(s) without an Xbox original - see the '
                             'UNEXPECTED / NO XBOX ORIGINAL lines' % (step, len(r['unexpected']), len(r['files_without_xbox_original'])))
        return {'files': r['written'], 'log': logs, 'counts': r['counts'][step], 'changes': r['changes'],
                'kept_base_mapped': r['kept_base_mapped']}
    fn.__name__ = 'fix_' + step
    return fn


# the converter fault families (tools/converter_faults_fix.STEPS), after the structure steps: objevent / animlist re-check
# the event lists eventlist / animfx already set (base-pair rules of x_lara / pc_lara plus the sub-0x32 id word), the
# others are classes no earlier step touches
FAULT_STEPS = ('objevent', 'idword', 'animlist', 'fxnode', 'statevm', 'chartid')
(fix_objevent, fix_idword, fix_animlist, fix_fxnode, fix_statevm, fix_chartid) = (_fault_fix(s) for s in FAULT_STEPS)


UIRECORD_SKIP = {'g_pda.drm'}      # merged g_pda of the DLC 2 tree: not installed (finding 40), left as built


def fix_uirecord(out, srcs=None):
    """UI text element records of the new DLC scripts (type 8, id >= 20000) by the retail Xbox / PC template of
    generalbank script 10 / 9 (finding 43, test 34): words the converter turned into swapped halves or left at the
    Xbox value where every PC record has the PC constant. tools/script_records_dlc.process per DRM; relocation words
    and the string id (uitext) stay. srcs: as in fix_uitext (out is read too and wins). g_pda.drm is skipped."""
    import collections
    sys.path.insert(0, HERE)
    import dtp_audit as DA, script_records_dlc as RD
    tpl = RD.template(); st = collections.Counter(); files, log = [], []
    dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
    for rel, path in sorted(DA.overlay(dirs, None).items()):
        if rel.lower() in UIRECORD_SKIP: continue
        new = RD.process(rel, path, tpl, st, log)
        if new is not None:
            _write(out, rel, new); files.append(rel)
    log.append('total %s (template %s)' % (dict(st), ' '.join(tpl[2])))
    return {'files': files, 'log': log}


ACHIEVEMENT_TYPES = {'achievement'}


def fix_achievement(out, srcs=None):
    """Calls into the title update's `achievement` natives f16-f20 (finding 43, test 40; workspace docs
    Befund-Erfolge.md): the TU binds 21 achievement natives, the PC exe 16, so a DLC script's `op65` into entry 16-20
    lands behind the PC function table (a call through a null native pointer, like `dlc2data` in test 33).
    tools/script_missing_native_fix.process per DRM with the original PC generalbank as the reference of the native
    tables (read-only, the same in every run; the installed / our generalbank give the same 11 calls): each such call
    sequence (object push + call + operand) becomes the preceding line marker and its relocation is dropped;
    sequences with out parameters or other ops are reported and left alone. srcs: as in fix_uitext (out is read
    too and wins)."""
    sys.path.insert(0, HERE)
    import dtp_audit as DA, script_missing_native_fix as MN
    nat = MN.native_types('pc'); files, log = [], []
    dirs = [os.path.abspath(s) for s in (srcs or [])] + [os.path.abspath(out)]
    for rel, path in sorted(DA.overlay(dirs, None).items()):
        new = MN.process(rel, path, nat, ACHIEVEMENT_TYPES, log)
        if new is not None:
            _write(out, rel, new); files.append(rel)
    log.append('total %d call(s) neutralised in %d file(s) (types %s, reference: original PC generalbank)' % (
        sum(l.startswith('FIX') for l in log), len(files), ','.join(sorted(ACHIEVEMENT_TYPES))))
    return {'files': files, 'log': log}


def fix_scriptclash(out, srcs=None):
    """DLC copies of always-resident PC scripts with another instance layout that DLC classes derive from: own PC
    id (findings 45 / 46; tools/script_clash_fix.run_tree, in place over OUT; reference pc:generalbank.drm, the PC
    patch version - read-only). srcs: not used (the rule needs the whole tree, which OUT already is). Ids come from
    docs/data/script_clash_ids.json; a new group is appended there and reported. Fails (SystemExit) when an id is
    taken or a rewritten DRM does not verify (other words changed, old references left)."""
    sys.path.insert(0, HERE)
    import script_clash_fix as SCF
    log = []
    r = SCF.run_tree(out, out, log=log.append)
    return {'files': r['files'], 'log': log, 'mapping': r['mapping'], 'stats': r['stats'], 'vt_only': r['vt_only']}


FIXES = [('cine', fix_cine), ('float', fix_float), ('tag404', fix_tag404), ('cloth', fix_cloth), ('uipath', fix_uipath), ('uitext', fix_uitext), ('postfix', fix_postfix),
         ('analog', fix_analog), ('statechart', fix_statechart),
         ] + [(s, globals()['fix_' + s]) for s in STRUCT_STEPS] + [(s, globals()['fix_' + s]) for s in FAULT_STEPS] + [
         ('uirecord', fix_uirecord), ('achievement', fix_achievement), ('scriptclash', fix_scriptclash)]


def main(argv):
    only = None
    if '--only' in argv:
        k = argv.index('--only'); only = set(argv[k + 1].split(',')); del argv[k:k + 2]
    if '--pack' in argv:     # DLC 2 tree: Xbox sources from pack11 first (convert_dlc.raw_dlc, finding 38)
        k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    src, out = argv[0], argv[1]
    sys.path.insert(0, HERE)
    from build_util import replace_tree
    replace_tree(src, out)
    report = {}
    for name, fn in FIXES:
        if only and name not in only: continue
        print('== fix', name, flush=True)
        r = fn(out)
        for l in r['log']: print('  ', l, flush=True)
        report[name] = r
    json.dump(report, open(os.path.join(os.path.dirname(os.path.abspath(out)), 'fixes_report.json'), 'w'), indent=1)
    print('fixes applied:', ', '.join(report) or '-')


if __name__ == '__main__':
    main(sys.argv[1:])
