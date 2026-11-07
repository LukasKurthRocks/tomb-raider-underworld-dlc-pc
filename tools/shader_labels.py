"""Shader-label data for a TruMenu "shader label" layer (2026-11-07, workspace docs Befund-Shader-Etiketten-0711.md),
read-only towards every input.

Question it answers: which material / shader does a piece of DLC geometry draw with, and is that shader the
original (PC twin of the Xbox lib), our title-update translation, or still a surrogate (placeholder chosen by
similarity in the converter)?

Inputs:
  * a mods folder (installed state or a test tree): every DRM, top level and streamgroups\\
  * work/render/shaderlibs.pkl: 'DM' = DLC Xbox materials (big endian, shader slots +0x28 / +0x2c / +0x30 / +0x34),
    'P' = base PC shader libs (ids)
  * work/render/dlc_shader_map.json: per DLC Xbox lib its class (A / B = byte-identical base lib -> PC twin,
    C1..C3 / D = surrogate chosen by similarity) and the PC lib the converter used ("pc")
Slot status (per material and slot 0..3 = PS pass 0, PS pass 1, PS pass 2 (colour), VS):
  O  original     Xbox lib class A / B and the PC copy uses its PC twin
  T  translated   the PC copy uses a lib id that is no base PC lib (a lib our TU translation added, e.g. 2842..2994)
  S  surrogate    Xbox lib class C* / D (no byte-identical base twin) and the PC copy uses a base PC lib (the
                  converter's surrogate, or B138's own donor in DLC 1) or a renumbered copy of the surrogate
  ?  unknown      anything else (PC slot without Xbox slot, other base lib)
  -  empty slot on both platforms
Material status: SURR (slot 2 = colour PS is S), PART (another slot is S, colour PS fine), UNK (a ? slot),
TU (at least one T, no S / ?), ORIG (all O), BASE (no DLC Xbox material: a base-game material id).

Positions: terrain batches are in the DRM's data frame. Live (TruMenu overlay, Instance +0x20) = data - origin,
origin = Level +0x80 of the unit (tools/unit_frames.py; checked again on 07.11.: trigger 12075 of dlc_yggdrasil_end
6060 units from Lara, as TruMenu's label said). Streamgroup DRMs have no Level: the owner unit's origin is used
(name prefix; inferred, not proven).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/shader_labels.py mats DRM [DRM ...]
      per material of the DRMs: PC libs, Xbox libs with class, slot letters, status
  ../bin/pyt -t 900 tools/shader_labels.py near DRM X Y Z [--live] [--r R] [--top N] [--all]
      terrain draws (one draw-list entry each) nearest to the point (horizontal distance to the draw's bbox, then
      vertical), with material and status; --live: X Y Z are live coordinates (converted with the unit origin);
      --all: also ORIG / BASE materials (default: all materials anyway, sorted by distance; --bad = only non-ORIG)
  ../bin/pyt -t 3600 tools/shader_labels.py build MODS_DIR OUT_DIR [--units NAME,NAME] [--reasons FINDING.md]
                                                 [--trees DIR,DIR] [--grid N]
      OUT_DIR/shaderlabel.txt  (the TruMenu data file, format in its header)
      OUT_DIR/shaderlabel_mats.tsv, OUT_DIR/shaderlabel_batches.tsv (same content, spreadsheet form)
      --units: only DRMs whose base name starts with one of the names (default: every DLC DRM = file that holds at
      least one DLC material, plus its streamgroups); --reasons: a finding with the 51x table ("| # | DLC | mat |
      Xbox lib | ... | 51x |") whose last column becomes the material's note; --trees: test-tree mods folders scanned
      for a translated copy of each SURR / PART material (note "fix in <tree> (libs ...)"); --grid: batch clustering
      cell in units (default 4096): draws of one material in one terrain section are merged per grid cell
"""
import sys, os, struct, json, pickle, re, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R, terrain_convert as TC

W = os.path.join(ROOT, 'work', 'render')
_REF = None


def ref():
    """(DM xbox tuples {mat: (l0, l1, l2, l3)}, shader map {xlib: {cls, pc}}, base PC lib id set)"""
    global _REF
    if _REF is None:
        L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
        dm = {}
        for mid, v in L['DM'].items():
            d = v[0] if isinstance(v, tuple) else v
            dm[mid] = tuple(struct.unpack_from('>4I', d, 0x28)) if len(d) >= 0x38 else (0, 0, 0, 0)
        sm = {int(k): v for k, v in json.load(open(os.path.join(W, 'dlc_shader_map.json'))).items()}
        pm = {}
        for mid, v in L['PM'].items():
            d = v[0] if isinstance(v, tuple) else v
            if len(d) >= 0x38: pm[mid] = tuple(x or None for x in struct.unpack_from('<4I', d, 0x28))
        globals()['_PM'] = pm
        _REF = (dm, sm, set(L['P'].keys()))
    return _REF


def pc_mats(D):
    """{material id: (pc lib or None) x 4} of one PC DRM (first copy per id in the file)"""
    out = {}
    for s in D.sections:
        if s.type != 10 or s.id in out: continue
        refs = set(R.parse(s.reloc, 'le').idref)
        sl = []
        for k in range(4):
            o = 0x28 + 4 * k
            sl.append(struct.unpack_from('<I', s.data, o)[0] if (9, o) in refs and o + 4 <= len(s.data) else None)
        out[s.id] = tuple(sl)
    return out


def pc_libs(D):
    """{lib id: section data} of the ShaderLib sections (type 9) of one PC DRM"""
    out = {}
    for s in D.sections:
        if s.type == 9 and s.id not in out: out[s.id] = s.data
    return out


_SHARE = {}


def surrogate_share(lib_id, data, sur):
    """share of the distinct shader blobs of a non-base lib that are byte-equal to a blob of base PC lib `sur`
    (1.0 = a renumbered copy of the surrogate, e.g. the fade-slot copies 2526 of 801; ~0 = a real translation)"""
    key = (lib_id, sur, len(data))
    if key in _SHARE: return _SHARE[key]
    import shaderlib as SL
    L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb')) if '_P' not in globals() else None
    if L is not None: globals()['_P'] = L['P']
    P = globals()['_P']
    v = 0.0
    try:
        mine = {e['blob'] for e in SL.parse(data, 'le')['entries'].values()}
        theirs = {e['blob'] for e in P[sur]['entries'].values()} if sur in P else set()
        v = len(mine & theirs) / len(mine) if mine else 0.0
    except Exception:
        v = -1.0
    _SHARE[key] = v
    return v


def classify(mid, pc, libs=None):
    """(status, slot letters, xbox tuple, class tuple, surrogate tuple); libs = {lib id: data} of the DRM that holds
    the copy (to recognise a renumbered copy of the surrogate)"""
    dm, sm, base = ref()
    if mid not in dm:
        return 'BASE', ''.join('-' if p is None else 'o' for p in pc), None, None, None
    xt = dm[mid]; letters = []; cls = []; sur = []
    for k in range(4):
        x = xt[k] or None; p = pc[k]
        e = sm.get(x) if x else None
        cls.append(e['cls'] if e else ('-' if x is None else '?'))
        sur.append(e['pc'] if e else None)
        if x is None and p is None: letters.append('-'); continue
        if p is None or e is None: letters.append('?'); continue
        if p not in base:
            if libs and p in libs and e['cls'] not in ('A', 'B') and surrogate_share(p, libs[p], e['pc']) >= 0.5:
                letters.append('S')      # renumbered (fade-slot) copy of the surrogate
            else:
                letters.append('T')
            continue
        if e['cls'] in ('A', 'B'):
            letters.append('O' if p == e['pc'] else '?')
        else:
            # class C* / D: the Xbox lib has no byte-identical base twin, so ANY base PC lib there is a stand-in
            # (our converter's choice e['pc'], or B138 / upstream's own donor for DLC 1)
            letters.append('S')
    lt = ''.join(letters)
    pmt = globals().get('_PM', {}).get(mid)
    if pmt is not None and tuple(pc) == pmt:
        return 'BASE', lt.replace('?', 'o'), xt, tuple(cls), tuple(sur)   # the base PC material of the same id
    if lt[2] == 'S': st = 'SURR'
    elif 'S' in lt: st = 'PART'
    elif '?' in lt: st = 'UNK'
    elif 'T' in lt: st = 'TU'
    else: st = 'ORIG'
    return st, lt, xt, tuple(cls), tuple(sur)


def level_origin(D):
    """Level +0x80 (3 floats) if section 0 is a Level (unit DRM), else None"""
    s = D.sections[0]
    if s.type != 0 or len(s.data) < 0x8c: return None
    r = R.parse(s.reloc, 'le')
    if 0 not in {so for si, so, do in r.external}: return None
    return struct.unpack_from('<3f', s.data, 0x80)


def terrain_draws(D):
    """[(section id, cell slot, draw index, y index, material id, index count, lo xyz, hi xyz)] for every draw-list
    entry of every render terrain section (type 12 without 'Mesh' magic)"""
    out = []
    for s in D.sections:
        if s.type != 12 or not TC.is_terrain(s.data): continue
        d = s.data
        try:
            T = TC.parse(d, '<'); H = T['H']
            ptr = dict(R.parse(s.reloc, 'le').internal)
            ml = ptr[0x0C]; n = struct.unpack_from('<I', d, ml)[0]
            mids = list(struct.unpack_from('<%dI' % n, d, ml + 4))
            idx = np.frombuffer(d, dtype='<u2', count=T['nIdx'], offset=H + T['offIdx'])
            pos_cache = {}
            for slot, seq, lst in TC.draw_lists(d, T, '<'):
                for j, (yi, cnt, start) in enumerate(lst):
                    y = T['Y'][yi]
                    if y[0] >= len(mids): continue
                    vb = y[1]
                    if vb not in pos_cache:
                        vdo, _, nv, vfi = T['vbs'][vb]; vf = T['vfs'][vfi]
                        po = [o for _, o, t, _ in vf['elems'] if t == 2]
                        if not po: pos_cache[vb] = None
                        else:
                            st = vf['stride']
                            raw = np.frombuffer(d, dtype=np.uint8, count=nv * st, offset=H + vdo).reshape(nv, st)
                            pos_cache[vb] = raw[:, po[0]:po[0] + 12].copy().view('<f4').reshape(nv, 3)
                    P = pos_cache[vb]
                    if P is None: continue
                    ii = idx[start:start + cnt].astype(np.int64); ii = ii[ii < len(P)]
                    if not len(ii): continue
                    Q = P[ii]
                    out.append((s.id, slot, j, yi, mids[y[0]], cnt, Q.min(0), Q.max(0)))
        except Exception as ex:
            print('  terrain section %d: %s' % (s.id, ex), file=sys.stderr)
    return out


def read(path):
    return DW.read(open(path, 'rb').read(), 'le')


def fmt_t(t):
    return '/'.join('-' if v is None or v == 0 else str(v) for v in t)


# ------------------------------------------------------------------------------------------------------------ mats
def cmd_mats(argv):
    for p in argv:
        D = read(p); M = pc_mats(D); LB = pc_libs(D)
        print('== %s: %d materials' % (os.path.basename(p), len(M)))
        for mid, pc in sorted(M.items()):
            st, lt, xt, cls, sur = classify(mid, pc, LB)
            x = '' if xt is None else 'xbox %s cls %s' % (fmt_t(xt), '/'.join(cls))
            print('  mat %6d  %-4s %s  pc %-22s %s' % (mid, st, lt, fmt_t(pc), x))


# ------------------------------------------------------------------------------------------------------------ near
def cmd_near(argv):
    live = '--live' in argv
    if live: argv.remove('--live')
    bad = '--bad' in argv
    if bad: argv.remove('--bad')
    if '--all' in argv: argv.remove('--all')
    r = 6000.0; top = 40
    if '--r' in argv: k = argv.index('--r'); r = float(argv[k + 1]); del argv[k:k + 2]
    if '--top' in argv: k = argv.index('--top'); top = int(argv[k + 1]); del argv[k:k + 2]
    path = argv[0]; X = np.array([float(v) for v in argv[1:4]])
    D = read(path); org = level_origin(D)
    if live:
        if org is None: sys.exit('no Level in %s - give data coordinates' % path)
        X = X + np.array(org)
        print('live -> data: + origin (%.1f %.1f %.1f) = (%.1f %.1f %.1f)' % (*org, *X))
    M = pc_mats(D); LB = pc_libs(D); rows = []
    for sid, slot, j, yi, mid, cnt, lo, hi in terrain_draws(D):
        st = classify(mid, M.get(mid, (None,) * 4), LB)[0]
        if bad and st in ('ORIG', 'BASE'): continue
        dxy = np.maximum(0, np.maximum(lo[:2] - X[:2], X[:2] - hi[:2])); h = float(np.hypot(*dxy))
        dz = float(max(0, lo[2] - X[2], X[2] - hi[2]))
        if h > r: continue
        rows.append((h, dz, sid, slot, j, yi, mid, st, cnt, lo, hi))
    rows.sort(key=lambda t: (t[0], t[1]))
    print('%s: %d draws within %.0f (horizontal) of (%.0f %.0f %.0f), data frame' % (os.path.basename(path), len(rows), r, *X))
    for h, dz, sid, slot, j, yi, mid, st, cnt, lo, hi in rows[:top]:
        sz = hi - lo
        print('  h %6.0f dz %6.0f  sec %d cell %d draw %d Y %d  mat %6d %-4s idx %5d  bbox (%.0f %.0f %.0f)-(%.0f %.0f %.0f) '
              'size (%.0f %.0f %.0f)' % (h, dz, sid, slot, j, yi, mid, st, cnt, *lo, *hi, *sz))


def cmd_intros(argv):
    """intros UNIT.drm X Y Z [--r R]: intros (instances placed by the unit) nearest to a LIVE point, with object name"""
    import unit_frames as UF
    r = 10000.0
    if '--r' in argv: k = argv.index('--r'); r = float(argv[k + 1]); del argv[k:k + 2]
    D, secs, L = UF.load(argv[0]); o = UF.unit_origin(secs)
    X = np.array([float(v) for v in argv[1:4]]); rows = []
    for si, off in L['intros']:
        d = secs[si]['data']
        uid = struct.unpack_from('<I', d, off + 0x58)[0]
        p = np.array(struct.unpack_from('<3f', d, off + 0x10)) - np.array(o)
        oid = struct.unpack_from('<H', d, off + 0x50)[0]
        dist = float(np.linalg.norm(p - X))
        if dist <= r: rows.append((dist, uid, oid, UF.objname(oid), p))
    rows.sort(key=lambda t: t[0])
    print('%s: origin %.1f %.1f %.1f, %d intros within %.0f of live (%.0f %.0f %.0f)' % (
        os.path.basename(argv[0]), *o, len(rows), r, *X))
    for dist, uid, oid, nm, p in rows:
        print('  %6.0f  intro %6d obj %5d %-36s live %8.0f %8.0f %8.0f' % (dist, uid, oid, nm, *p))


# ----------------------------------------------------------------------------------------------------------- build
def reasons_from(path):
    """{material: last column of the 51x table} from a finding (docs/Befund-Streamgroups-Shader-0511.md)"""
    out = {}
    for l in open(path, encoding='utf-8-sig', errors='replace'):
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        if len(c) == 9 and c[0].isdigit() and c[2].isdigit():
            v = c[8].replace('**', '')
            out[int(c[2])] = ('51x lib ' + v) if v.isdigit() else v
    return out


def drm_files(mods):
    for d in (mods, os.path.join(mods, 'streamgroups')):
        if not os.path.isdir(d): continue
        for n in sorted(os.listdir(d)):
            if n.lower().endswith('.drm'):
                yield os.path.join(d, n), ('streamgroups/' if d != mods else '') + n[:-4]


def clean(s):
    return re.sub(r'\s+', '_', s.strip())[:400] if s else '-'


def cmd_build(argv):
    units = None; reasons = {}; trees = []; grid = 4096.0
    if '--units' in argv: k = argv.index('--units'); units = [u.lower() for u in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--reasons' in argv: k = argv.index('--reasons'); reasons = reasons_from(argv[k + 1]); del argv[k:k + 2]
    if '--trees' in argv: k = argv.index('--trees'); trees = argv[k + 1].split(','); del argv[k:k + 2]
    if '--grid' in argv: k = argv.index('--grid'); grid = float(argv[k + 1]); del argv[k:k + 2]
    mods, outd = argv[0], argv[1]; os.makedirs(outd, exist_ok=True)
    dm, sm, base = ref()
    files = []
    for path, name in drm_files(mods):
        b = name.split('/')[-1].lower()
        if units and not any(b.startswith(u) for u in units): continue
        files.append((path, name))
    origins = {}; mats = {}; copies = collections.defaultdict(list); batches = []; groups = {}
    for path, name in files:
        D = read(path); M = pc_mats(D)
        org = level_origin(D)
        b = name.split('/')[-1].lower()
        dlcname = name.startswith('streamgroups/') or b.startswith('dlc') or b.startswith('co_dlc')
        if not units and not dlcname and not any(m in dm for m in M): continue     # base-game file
        if org is not None: origins[name] = org
        elif not name.startswith('streamgroups/'):
            mm = set()                       # object DRM: materials its model meshes reference
            for s in D.sections:
                if s.type == 12 and not TC.is_terrain(s.data):
                    for t, o in R.parse(s.reloc, 'le').idref:
                        if t == 10 and o + 4 <= len(s.data): mm.add(struct.unpack_from('<I', s.data, o)[0])
            if mm: groups[name] = sorted(mm)
        LB = pc_libs(D)
        for mid, pc in M.items():
            st, lt, xt, cls, sur = classify(mid, pc, LB)
            copies[mid].append((st, lt, name, pc, xt, cls, sur))
        # batches: draws merged per (section, material, grid cell of the draw centre)
        acc = {}
        for sid, slot, j, yi, mid, cnt, lo, hi in terrain_draws(D):
            c = (lo + hi) / 2; key = (sid, mid, tuple(np.floor(c / grid).astype(int)))
            a = acc.get(key)
            if a is None: acc[key] = [cnt, 1, lo.copy(), hi.copy(), {yi}]
            else:
                a[0] += cnt; a[1] += 1; a[2] = np.minimum(a[2], lo); a[3] = np.maximum(a[3], hi); a[4].add(yi)
        for (sid, mid, _), (cnt, nd, lo, hi, ys) in acc.items():
            batches.append((name, sid, mid, cnt, nd, lo, hi, sorted(ys)))
        print('  %-60s %4d materials, %5d batches%s' % (name, len(M), len(acc), '' if org is None else ' (unit)'))
    # material status per copy; the label status = worst copy (the engine keeps the first loaded copy of an id)
    order = {'SURR': 0, 'PART': 1, 'UNK': 2, 'TU': 3, 'ORIG': 4, 'BASE': 5}
    for mid, cl in copies.items():
        per = sorted(cl, key=lambda t: order[t[0]])
        st0, lt0, _, pc0, xt, cls, sur = per[0]
        mixed = len({p[0] for p in per}) > 1
        mats[mid] = dict(status=st0, letters=lt0, pc=pc0, xbox=xt, cls=cls, sur=sur, mixed=mixed,
                         copies=[p[:4] for p in per], note=reasons.get(mid, ''))
    # test trees: a translated copy of a SURR / PART material
    if trees:
        need = {m for m, v in mats.items() if v['status'] in ('SURR', 'PART', 'UNK')}
        for t in trees:
            tn = os.path.basename(os.path.dirname(os.path.normpath(t))) if os.path.basename(os.path.normpath(t)) == 'mods' else os.path.basename(os.path.normpath(t))
            for path, name in drm_files(t):
                try: D = read(path)
                except Exception: continue
                LB = pc_libs(D)
                for mid, pc in pc_mats(D).items():
                    if mid not in need: continue
                    st, lt, *_ = classify(mid, pc, LB)
                    if order[st] > order[mats[mid]['status']]:
                        f = 'fix in %s (%s %s)' % (tn, lt, fmt_t(pc))
                        if f not in mats[mid].setdefault('fixes', []): mats[mid]['fixes'].append(f)
    write_out(outd, mats, origins, batches, files, mods, groups)


def owner_unit(name, origins):
    if not name.startswith('streamgroups/'): return name
    b = name.split('/')[-1]
    best = None
    for u in origins:
        if b.startswith(u + '_') and (best is None or len(u) > len(best)): best = u
    return best or '-'


def write_out(outd, mats, origins, batches, files, mods, objects=None):
    stat = collections.Counter(v['status'] for v in mats.values())
    with open(os.path.join(outd, 'shaderlabel.txt'), 'w', encoding='ascii', errors='replace', newline='\r\n') as f:
        f.write('# shaderlabel v1 - TruMenu shader label data (tools/shader_labels.py build), ids and status only, no game data\n')
        f.write('# source: %s (%d DRMs), status counts %s\n' % (os.path.basename(os.path.normpath(mods)), len(files),
                                                                 ' '.join('%s=%d' % kv for kv in sorted(stat.items()))))
        f.write('# lines (space separated, - = empty):\n')
        f.write('#   U <unit> <origin x> <origin y> <origin z>            live = data - origin (Level +0x80)\n')
        f.write('#   M <material> <status> <slots> <pc libs a/b/c/d> <xbox libs> <xbox classes> <surrogate pc libs> <mixed 0|1> <note>\n')
        f.write('#      status SURR / PART / UNK / TU / ORIG / BASE; slots = 4 letters (PS0 PS1 PS2 VS): O original, T translated,\n')
        f.write('#      S surrogate, ? unknown, - empty; mixed 1 = copies in different DRMs differ (load order decides)\n')
        f.write('#   B <drm> <owner unit> <section> <material> <status> <cx> <cy> <cz> <sx> <sy> <sz> <indices> <draws> <y list>\n')
        f.write('#      batch = draws of one material in one render terrain section, merged per grid cell; centre / size in\n')
        f.write('#      the DRM data frame (subtract the owner unit origin for live coordinates)\n')
        f.write('#   G <drm> <owner unit> <cx> <cy> <cz> <sx> <sy> <sz> <batches> <SURR> <PART> <UNK> <TU> <ORIG> <BASE>\n')
        f.write('#      one per DRM with terrain (unit or streamgroup): bbox of all its batches (data frame), batch counts\n')
        f.write('#   O <object drm> <worst status> <material:status,...>   materials the model meshes of an object DRM use\n')
        f.write('#      (instance labels: object name -> this line)\n')
        f.write('#   L firstnewlib <id>    lib ids >= this are no base PC lib: translations (T) unless a renumbered\n')
        f.write('#      copy of the surrogate (checked offline, then S)\n')
        dm, sm, base = ref()
        f.write('L firstnewlib %d\n' % (max(base) + 1))
        for u, o in sorted(origins.items()):
            f.write('U %s %.1f %.1f %.1f\n' % (u, *o))
        grp = {}
        for name, sid, mid, cnt, nd, lo, hi, ys in batches:
            st = mats.get(mid, {}).get('status', 'BASE')
            g = grp.get(name)
            if g is None: g = grp[name] = [lo.copy(), hi.copy(), collections.Counter()]
            g[0] = np.minimum(g[0], lo); g[1] = np.maximum(g[1], hi); g[2][st] += 1
        rank = {'SURR': 0, 'PART': 1, 'UNK': 2, 'TU': 3, 'ORIG': 4, 'BASE': 5}
        for name, mm in sorted((objects or {}).items()):
            sts = [(m, mats.get(m, {}).get('status', 'BASE')) for m in mm]
            worst = min((s for _, s in sts), key=lambda s: rank[s])
            f.write('O %s %s %s\n' % (name, worst, ','.join('%d:%s' % t for t in sts)))
        for name in sorted(grp):
            lo, hi, c = grp[name]
            f.write('G %s %s %.0f %.0f %.0f %.0f %.0f %.0f %d %d %d %d %d %d %d\n' % (
                name, owner_unit(name, origins), *((lo + hi) / 2), *(hi - lo), sum(c.values()),
                *(c[k] for k in ('SURR', 'PART', 'UNK', 'TU', 'ORIG', 'BASE'))))
        for mid in sorted(mats):
            v = mats[mid]
            if v['status'] == 'BASE': continue
            note = v['note']
            if v.get('fixes'): note = (note + '; ' if note else '') + '; '.join(v['fixes'])
            f.write('M %d %s %s %s %s %s %s %d %s\n' % (
                mid, v['status'], v['letters'], fmt_t(v['pc']), fmt_t(v['xbox'] or ()), '/'.join(v['cls'] or ()) or '-',
                fmt_t(v['sur'] or ()), 1 if v['mixed'] else 0, clean(note)))
        for name, sid, mid, cnt, nd, lo, hi, ys in sorted(batches, key=lambda b: (b[0], b[1], b[2], tuple(b[5]))):
            st = mats.get(mid, {}).get('status', 'BASE')
            c = (lo + hi) / 2; sz = hi - lo
            f.write('B %s %s %d %d %s %.0f %.0f %.0f %.0f %.0f %.0f %d %d %s\n' % (
                name, owner_unit(name, origins), sid, mid, st, *c, *sz, cnt, nd, ','.join(map(str, ys))))
    with open(os.path.join(outd, 'shaderlabel_mats.tsv'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('material\tstatus\tslots\tpc\txbox\tclasses\tsurrogate\tmixed\tcopies\tnote\n')
        for mid in sorted(mats):
            v = mats[mid]
            cp = ' '.join('%s:%s:%s' % (n, s, l) for s, l, n, _ in v['copies'])
            note = v['note'] + ('; ' + '; '.join(v['fixes']) if v.get('fixes') else '')
            f.write('%d\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n' % (
                mid, v['status'], v['letters'], fmt_t(v['pc']), fmt_t(v['xbox'] or ()), '/'.join(v['cls'] or ()) or '-',
                fmt_t(v['sur'] or ()), v['mixed'], cp, note))
    with open(os.path.join(outd, 'shaderlabel_batches.tsv'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('drm\towner\tsection\tmaterial\tstatus\tcx\tcy\tcz\tsx\tsy\tsz\tindices\tdraws\ty\n')
        for name, sid, mid, cnt, nd, lo, hi, ys in batches:
            st = mats.get(mid, {}).get('status', 'BASE'); c = (lo + hi) / 2; sz = hi - lo
            f.write('%s\t%s\t%d\t%d\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%d\t%d\t%s\n' % (
                name, owner_unit(name, origins), sid, mid, st, *c, *sz, cnt, nd, ','.join(map(str, ys))))
    print('materials %d (%s), batches %d, units with origin %d -> %s' % (
        len(mats), ' '.join('%s=%d' % kv for kv in sorted(stat.items())), len(batches), len(origins), outd))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    cmd, a = sys.argv[1], sys.argv[2:]
    {'mats': cmd_mats, 'near': cmd_near, 'intros': cmd_intros, 'build': cmd_build}.get(cmd, lambda a: sys.exit(__doc__))(a)
