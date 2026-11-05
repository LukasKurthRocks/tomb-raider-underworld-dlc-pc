r"""Costume scope check (owner decision E4, 2026-11-05): the costume slots g / n and pack20's container unit
dlc_costumes4 are left out of the port. Read-only; writes only the optional --report file.

What "left out" means (docs/COSTUMES.md, section "Left out"):
  * no dlc_costume_g.drm / dlc_costume_n.drm in a mods tree. The loading-screen script (generalbank script 6,
    function 26) offers a slot only when dlc_costume_<x>.drm exists (dlcsystem f1 + conditional jump), and the
    costume validator 0x5c54e0 needs the file too - without the file the outfit list shows only real costumes;
  * no unit dlc\dlc_costume_containers\dlc_costumes4 in unitlist.txt and no objlist.dat record of that name
    (pack20's list-only container, no DRM in any pack; it would be unit 8 and move the 112 units after it);
  * kept on purpose (removing them would break things): object ids 20..35 = dlc_costume_a..p in objectlist.txt,
    including 26 = dlc_costume_g and 33 = dlc_costume_n (ids are positions; the PC base list, the Xbox lists and the
    DRMs refer to objects by id), and the outfit images image\dlc_outfit_costume_{g,n}.raw (B138 / pack11 ship them;
    script 6 function 17 loads images only for the offered slots).

  tree DIR [DIR ...] [--report OUT.json]   mods trees (or a game's mods folder - only read)
  profiles [DIR] [--report OUT.json]       every tests/profiles/*.json (default DIR): each tree source (relative to the
                                           workspace = the folder that holds the repository) checked like `tree`,
                                           plus every text mention of the left-out names (reported, not an error)
  script6 DRM [DRM ...]                    generalbank script 6 function 26: every dlc_costume_<x>.drm /
                                           dlc_doppel_costume_<x>.drm name must be followed by the dlcsystem f1
                                           call and a conditional jump (op64) - the offer is gated by the file
  selftest                                 the checks on in-memory variants of the merged PC lists
                                           (work/generic/merged): unchanged -> 0 findings; + dlc_costumes4 unit,
                                           + dlc_costumes4 record, + dlc_costume_g.drm / dlc_costume_n.drm,
                                           id 26 renamed -> each one found; and pack20's Xbox list (work/generic/lists)
                                           -> dlc_costumes4 found

Exit code 1 when a left-out item is in a tree, a kept costume id moved, a script-6 gate is missing or the selftest
fails; else 0.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/costume_scope_check.py tree work/rebuild/dlc_test51g_costumes/mods --report OUT.json
  ../bin/pyt -t 900 tools/costume_scope_check.py profiles
  ../bin/pyt -t 600 tools/costume_scope_check.py script6 work/rebuild/b138_fixes/mods/generalbank.drm
  ../bin/pyt -t 300 tools/costume_scope_check.py selftest
"""
import sys, os, io, re, json, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objlists as O

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..'))
WORKSPACE = os.path.normpath(os.path.join(REPO, '..'))
SLOTS = 'abcdefghijklmnop'
LEFT_OUT_DRMS = ('dlc_costume_g.drm', 'dlc_costume_n.drm')
LEFT_OUT_UNIT = 'dlc\\dlc_costume_containers\\dlc_costumes4'
LEFT_OUT_RECORD = 'dlc_costumes4'
KEPT_IDS = {20 + k: 'dlc_costume_' + s for k, s in enumerate(SLOTS)}      # 26 = g, 33 = n stay in the list
KEPT_IMAGES = ('dlc_outfit_costume_g.raw', 'dlc_outfit_costume_n.raw')
MENTION = re.compile(r'dlc_costume_[gn]\.drm|dlc_costume_[gn]\b|dlc_costumes4', re.I)


def check_lists(objectlist=None, unitlist=None, objlist=None, endian='le'):
    """findings for the three list files (bytes or None when the tree does not carry the file)"""
    found, info = [], []
    if unitlist is not None:
        units = O.read_unitlist(unitlist)
        for u in units:
            if u.lower() == LEFT_OUT_UNIT or u.lower().endswith('\\' + LEFT_OUT_RECORD):
                found.append('unitlist.txt: unit %s (position %d of %d)' % (u, units.index(u) + 1, len(units)))
        info.append('unitlist.txt %d units' % len(units))
    if objlist is not None:
        recs, _ = O.read_objlist(objlist, endian)
        for n, l in recs:
            if n.lower() == LEFT_OUT_RECORD:
                found.append('objlist.dat: record %s (%d objects)' % (n, len(l)))
        info.append('objlist.dat %d records' % len(recs))
    if objectlist is not None:
        ol = O.read_objectlist(objectlist)
        for i, nm in sorted(KEPT_IDS.items()):
            if ol.get(i) != nm:
                found.append('objectlist.txt: id %d is %r, expected %r (kept ids must not move)' % (i, ol.get(i), nm))
        info.append('objectlist.txt %d objects, ids 20..35 = dlc_costume_a..p %s' % (
            len(ol), 'ok' if all(ol.get(i) == nm for i, nm in KEPT_IDS.items()) else 'CHANGED'))
    return found, info


def check_names(names):
    """findings / info for the file names (relative, any case) of a tree"""
    low = {n.replace('/', '\\').lower(): n for n in names}
    found = ['file %s (left-out costume slot)' % low[k] for k in sorted(low) if os.path.basename(k) in LEFT_OUT_DRMS]
    slots = sorted(os.path.basename(k)[12] for k in low
                   if re.fullmatch(r'dlc_costume_[a-p]\.drm', os.path.basename(k)))
    imgs = sorted(os.path.basename(k) for k in low if os.path.basename(k) in KEPT_IMAGES)
    return found, slots, imgs


def check_tree(d):
    r = {'tree': d, 'exists': os.path.isdir(d), 'findings': [], 'info': [], 'costume_drms': [], 'kept_images': []}
    if not r['exists']:
        r['info'].append('folder not found')
        return r
    names = []
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            names.append(os.path.relpath(os.path.join(dp, f), d))
    r['files'] = len(names)
    f, slots, imgs = check_names(names)
    r['findings'] += f; r['costume_drms'] = slots; r['kept_images'] = imgs
    lp = os.path.join(d, 'tr8', 'pc-w')
    rd = lambda n: open(os.path.join(lp, n), 'rb').read() if os.path.isfile(os.path.join(lp, n)) else None
    f, info = check_lists(rd('objectlist.txt'), rd('unitlist.txt'), rd('objlist.dat'), 'le')
    r['findings'] += f; r['info'] += info
    return r


def print_tree(r):
    print('== %s' % r['tree'])
    if not r['exists']:
        print('   (folder not found)'); return
    print('   files %d, costume DRMs: %s, kept outfit images g/n: %s' % (
        r['files'], ' '.join(r['costume_drms']) or '-', ' '.join(r['kept_images']) or '-'))
    for i in r['info']: print('   ' + i)
    for f in r['findings']: print('   LEFT-OUT ITEM: ' + f)
    print('   result: %s' % ('%d finding(s)' % len(r['findings']) if r['findings'] else 'ok (nothing left-out present)'))


def cmd_tree(dirs, report=None):
    res = [check_tree(os.path.normpath(d)) for d in dirs]
    for r in res: print_tree(r)
    n = sum(len(r['findings']) for r in res)
    print('TOTAL trees %d, findings %d' % (len(res), n))
    if report: json.dump({'trees': res, 'findings': n}, open(report, 'w'), indent=1)
    return 1 if n else 0


def cmd_profiles(pdir=None, report=None):
    pdir = pdir or os.path.join(REPO, 'tests', 'profiles')
    seen, out, mentions = {}, [], []
    files = sorted(f for f in os.listdir(pdir) if f.lower().endswith('.json'))
    for f in files:
        raw = open(os.path.join(pdir, f), 'rb').read().decode('utf-8-sig')
        for m in sorted(set(x.group(0) for x in MENTION.finditer(raw))):
            mentions.append((f, m))
        p = json.loads(raw)
        for t in p.get('trees') or []:
            src = t.get('source') if isinstance(t, dict) else t
            if not src: continue
            full = os.path.normpath(src if os.path.isabs(src) else os.path.join(WORKSPACE, src))
            if full not in seen:
                seen[full] = check_tree(full); seen[full]['profiles'] = []
            seen[full]['profiles'].append(f[:-5])
    n = 0
    for full, r in sorted(seen.items()):
        if r['findings'] or not r['exists'] or r['costume_drms']:
            print_tree(r); print('   used by %d profile(s): %s' % (len(r['profiles']), ', '.join(r['profiles'])))
        n += len(r['findings'])
    missing = sum(1 for r in seen.values() if not r['exists'])
    withc = sum(1 for r in seen.values() if r['costume_drms'])
    print('mentions of left-out names in the profile texts: %d%s' % (
        len(mentions), ''.join('\n   %s: %s' % m for m in mentions)))
    print('TOTAL profiles %d, distinct trees %d (missing %d, with costume DRMs %d), findings %d' % (
        len(files), len(seen), missing, withc, n))
    if report:
        json.dump({'profiles': len(files), 'trees': list(seen.values()), 'mentions': mentions, 'findings': n},
                  open(report, 'w'), indent=1)
    return 1 if n else 0


def cmd_script6(drms):
    import script_dis as SD
    bad = 0
    for drm in drms:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            SD.main([drm, '6', '26'])
        lines = buf.getvalue().splitlines()
        rows = []
        for i, l in enumerate(lines):
            m = re.search(r"'((?:dlc_costume|dlc_doppel_costume)_[a-z]\.drm)'", l)
            if not m: continue
            f1 = next((j for j in range(i + 1, min(i + 4, len(lines))) if 'ext (8,90)' in lines[j] and ' f1' in lines[j]), None)
            jmp = next((j for j in range(f1 + 1, min(f1 + 4, len(lines))) if ' op64 ' in lines[j]), None) if f1 else None
            rows.append((m.group(1), f1 is not None, jmp is not None))
        gated = sum(1 for _n, a, b in rows if a and b)
        print('== %s: script 6 function 26, %d names, %d gated by dlcsystem f1 + conditional jump' % (drm, len(rows), gated))
        for n, a, b in rows:
            print('   %-26s f1 %s  jump %s%s' % (n, 'yes' if a else 'NO', 'yes' if b else 'NO',
                                              '   <- left out (no file -> no entry)' if n in LEFT_OUT_DRMS else ''))
        if len(rows) != 20 or gated != len(rows): bad += 1
    print('TOTAL files %d, not fully gated %d' % (len(drms), bad))
    return 1 if bad else 0


def cmd_selftest():
    mp = os.path.join(REPO, 'work', 'generic', 'merged', 'tr8', 'pc-w')
    ob, ub, db = (open(os.path.join(mp, n), 'rb').read() for n in ('objectlist.txt', 'unitlist.txt', 'objlist.dat'))
    units = O.read_unitlist(ub); recs, first = O.read_objlist(db, 'le'); ol = O.read_objectlist(ob)
    c4 = next(l for n, l in recs if n == 'dlc_costumes2')                 # same shape as pack20's record
    ol26 = dict(ol); ol26[26] = 'dlc_costume_x'
    cases = [
        ('unchanged merged lists', (ob, ub, db), [], 0),
        ('+ unit dlc_costumes4', (ob, O.write_unitlist(sorted(units + [LEFT_OUT_UNIT])), db), [], 1),
        ('+ record dlc_costumes4', (ob, ub, O.write_objlist(recs + [(LEFT_OUT_RECORD, c4)], 'le', first)), [], 1),
        ('+ dlc_costume_g.drm, dlc_costume_n.drm', (ob, ub, db), ['dlc_costume_g.drm', 'dlc_costume_n.drm',
                                                                   'dlc_costume_k.drm', 'image\\dlc_outfit_costume_g.raw'], 2),
        ('id 26 renamed', (O.write_objectlist(ol26), ub, db), [], 1),
    ]
    bad = 0
    for name, (a, b, c), files, want in cases:
        f, _ = check_lists(a, b, c, 'le'); g, _s, _i = check_names(files); got = len(f) + len(g)
        ok = got == want; bad += not ok
        print('   %-40s findings %d (expected %d) %s' % (name, got, want, 'ok' if ok else 'FAIL'))
        for x in f + g: print('      ' + x)
    lp = os.path.join(REPO, 'work', 'generic', 'lists', 'dlc_pack20_')
    if os.path.isfile(lp + 'unitlist.txt'):
        f, _ = check_lists(None, open(lp + 'unitlist.txt', 'rb').read(), open(lp + 'objlist.dat', 'rb').read(), 'be')
        ok = len(f) == 2; bad += not ok
        print('   %-40s findings %d (expected 2) %s' % ("pack20's Xbox lists", len(f), 'ok' if ok else 'FAIL'))
        for x in f: print('      ' + x)
    print('SELFTEST %s (%d case(s) failed)' % ('ok' if not bad else 'FAILED', bad))
    return 1 if bad else 0


def main(argv):
    rep = None
    if '--report' in argv:
        k = argv.index('--report'); rep = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    if not argv: print(__doc__); return 2
    c, a = argv[0], argv[1:]
    if c == 'tree' and a: return cmd_tree(a, rep)
    if c == 'profiles': return cmd_profiles(a[0] if a else None, rep)
    if c == 'script6' and a: return cmd_script6(a)
    if c == 'selftest': return cmd_selftest()
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
