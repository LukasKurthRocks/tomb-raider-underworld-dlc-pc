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
  postfix upstream's tools/dlc1_postfix.py steps 1-2: streamgroup name tables (save hang) and type-0 name strings
  analog upstream's tools/analog_word_fix.py: near-clone DTPs get the base PC bytes (each word checked against B138)

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


FIXES = [('cine', fix_cine), ('float', fix_float), ('tag404', fix_tag404), ('postfix', fix_postfix),
         ('analog', fix_analog)]


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
