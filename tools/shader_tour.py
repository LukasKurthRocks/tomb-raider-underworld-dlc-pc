"""Shader tour (read-only): where in the DLC levels can the translated shader groups of tests 50l / 50m / 50n be seen?
For every material group (built-in table GROUPS, from docs Befund-Shader-Nacht.md / Befund-Look.md and the PROGRESS.md
tables of the 50m / 50n trees) it finds the DRMs of the shader trees that carry the material, then
  * object DRMs: the object id (DLC object list), the units that place an Intro of that object (unit DTP Level+0x74,
    tools/unit_ids.level_info; +0x10 position, +0x50 object id, +0x58 unique id = the intro id `player.goto` takes)
    and the units whose objlist.dat record loads the object;
  * unit DRMs: the terrain geometry drawn with the material (tools/terrain_material_bbox logic), its bounding box and
    the intros nearest to it. Terrain vertices and intro positions are taken to share one frame (every terrain bbox
    encloses its unit's intros; dlc_yggdrasil_end: effect dlc_fx_goo_tube_end 10643 at z 8259 sits at the lower end of
    the material-23164 tube from z 8304) - not proven in game. The TruMenu position overlay seemed offset against it
    in two dlc_level2_start screenshots, so use `player.goto <intro id>`, not `player.teleport` with these numbers.
Nothing is written into the game data; outputs only under work/shader_tour/.

Modes (from the repository root):
  ../bin/pyt -t 600 tools/shader_tour.py tg UNIT.drm
      per TerrainGroup (0x50 B): raw floats +0x00..+0x2c, uniqueID +0x28, the terrain section it points to, that
      section's vertex bbox (local), and the bbox of the unit's intro positions (to test which TG field is the offset)
  ../bin/pyt -t 1800 tools/shader_tour.py index UNITDIR [UNITDIR ...] [--out work/shader_tour/intros.json]
      every unit DRM of the folders (later folders replace a unit of the same name): intros (unit, unique id, object
      id, name, position) -> JSON
  ../bin/pyt -t 1800 tools/shader_tour.py mats TREE [TREE ...] [--out work/shader_tour/mats.json]
      every material of GROUPS -> the tree files (file name -> first tree that has it, trees in the given order =
      later trees win, as in a profile) that contain a type-10 section with that id; unit DRMs: terrain draws of it
  ../bin/pyt -t 600 tools/shader_tour.py report [--intros F] [--mats F] [--near N] [--max N] [--only KEY,KEY]
      per group: files, objects, placing units with intro ids / positions (or of the SPAWNERS), terrain draws
      (largest first, centre + nearest intros)
  ../bin/pyt -t 120 tools/shader_tour.py files                      tree file -> groups it carries
  ../bin/pyt -t 120 tools/shader_tour.py list UNIT [REGEX]          intros of a unit (names matching REGEX)
  ../bin/pyt -t 120 tools/shader_tour.py near UNIT X Y Z [N]        the N intros nearest to a data position
  ../bin/pyt -t 600 tools/shader_tour.py portals UNIT.drm [...]     StreamUnitPortal names (neighbour units)
"""
import sys, os, struct, json, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, unit_ids as U, terrain_convert as TC

OUTDIR = 'work/shader_tour'
OBJLIST = 'work/generic/lists/dlc_pack11_objectlist.txt'
OBJDAT = 'work/generic/lists/dlc_pack11_objlist.dat'

# (key, label, tree, [material ids]) - tree = the first test tree that has the translation
GROUPS = [
    # part 1 (50l): doppelganger = the DLC 2 player figure
    ('dop_hair', 'doppelganger hair 2308 -> 2810', '50l', [25521]),
    ('dop_cloth', 'doppelganger top / trousers 2603 / 2617 / 2652 -> 2811 / 2812 / 2814', '50l', [26346, 26351, 26359]),
    ('dop_belt', 'doppelganger belt metal 2648 -> 2813', '50l', [26358]),
    ('dop_face', 'doppelganger face 2679 -> 2815', '50l', [26348]),
    ('dop_arms', 'doppelganger arms / gloves 2682 / 2685 / 2688 (50h libs 2582-2584, unchanged)', '50l', [26349, 26350, 26352]),
    ('dop_rest', 'doppelganger 2624 / 2628 / 2636 / 2640 / 2644 (transplant libs kept, exact)', '50l',
     [21686, 21687, 26355, 26356, 26357, 26360]),
    ('dop_50m', 'doppelganger 2607 -> 2840 and fade material 2632 -> 2841', '50m', [26347, 26354]),
    # thrall bodies
    ('viking', 'viking thrall body 2816-2820', '50l', [26186, 26361, 26424, 26422, 26423, 26425, 26426]),
    ('yeti', 'yeti thrall body 2817 / 2818 / 2821-2823', '50l', [26437, 26439, 26440, 26441, 26436, 26435, 26438]),
    ('yeti_arm', 'armoured yeti body 2813 / 2818 / 2824-2826', '50l', [24979, 24980, 24981, 24982, 24983, 24984, 26459]),
    ('natla_thrall', 'natla thrall body 2331 -> 2827', '50l', [26372, 26373, 26378, 26380]),
    # part 2: unlit effect materials (eitr / glow / distortion)
    ('eitr_glow', 'eitr / glow PS 2250 -> 2828', '50l', [24351, 24352, 24353, 24354, 24357, 24358, 24359, 24360, 24361]),
    ('eitr_2318', 'effect PS 2318 -> 2829', '50l', [21531]),
    ('eitr_2324', 'effect PS 2324 -> 2830 + VS 2834 (vertex colour)', '50l', [24356]),
    ('distort_2368', 'distortion PS 2368 -> 2832 + VS 2834 (back buffer, GlobalParams[7])', '50l', [24958]),
    ('refract_2375', 'refraction PS 2375 -> 2833', '50l', [24817, 25059]),
    ('look', 'full-screen look 2327 / 2328 -> 2943 / 2944', '50l', [20744]),
    ('knight_dlc1', 'DLC 1 knight thrall copies -> upstream 2723 / 2724 / 2782 / 2726', '50l_dlc1', [20321, 20322, 20323, 20325]),
    ('vein', 'rock vein 2392 -> 2675 (50c, reference, unchanged)', '50c', [24299, 24690]),
    # part 3 (50m)
    ('m2315', '2315 -> 2842', '50m', [23294]),
    ('m2273', 'costume f 2273 -> 2843', '50m', [23552]),
    ('m2354', 'rune / treadmill blocks 2354 -> 2844', '50m', [26226, 26227]),
    ('m2364', 'punch switch 2364 -> 2845', '50m', [26778]),
    ('m2380', 'goo spout 2380 -> 2846', '50m', [25263]),
    ('m2436', 'corkscrew 2436 -> 2847', '50m', [26331]),
    ('m2591', 'pistons 2591 -> 2848', '50m', [25520]),
    ('m2594', 'column / pistons 2594 -> 2849', '50m', [22657]),
    ('m2311', '2311 -> 2850', '50m', [23156]),
    ('m2455', 'goo converter ball 2455 -> 2851 (unlit)', '50m', [23164]),
    ('m2453', 'natla pod 2453 -> 2852', '50m', [26421]),
    ('m2489', 'natla pod 2489 -> 2853', '50m', [25846, 25921]),
    ('m2596', 'natla pod 2596 -> 2854', '50m', [22997]),
    ('m2375', 'goo 2375 -> 2855 (unlit)', '50m', [26639, 26640]),
    ('m2361', '2361 -> 2856', '50m', [26445]),
    ('m2433', 'hall02 2433 -> 2857', '50m', [20533]),
    ('m2299', 'DLC 1 adren trap 2299 -> 2859', '50m', [21118]),
    ('m2405', 'goo converter 2405 -> 2860', '50m', [26316]),
    ('m2468', 'goo converter 2468 -> 2861', '50m', [25170]),
    ('m2571', 'goo grinder / converter 2571 -> 2862', '50m', [25163]),
    ('m2709', 'crushers 2709 -> 2863', '50m', [25659]),
    ('m2302', 'machine metal 2302 -> 2864', '50m', [23160, 23295, 23304, 26165, 23163]),
    ('m2305', 'machine / wall 2305 -> 2865', '50m', [23152, 23155, 23153, 22567, 20490, 23303]),
    ('m2346', 'dark wall streaks 2346 -> 2866', '50m', [25522, 24736, 25057, 26444]),
    ('m2392', 'column / pistons vein 2392 -> 2867', '50m', [26267]),
    ('m2446a', 'bridges / grinder 2446 -> 2868', '50m', [25529, 25857, 25164]),
    ('m2446b', 'bridges 2446 -> 2869', '50m', [25530, 26696]),
    ('m2700', 'bridges / column 2700 -> 2870', '50m', [26120, 26592, 26695]),
    ('m2370', 'energy / goo glow 2370 -> 2871 (unlit)', '50m', [25169, 25855, 25940, 25941]),
    ('m2410', 'switch glow 2410 -> 2872 (unlit)', '50m', [22670]),
    ('m2712', 'goo 2712 -> 2873 (unlit)', '50m', [26298]),
    ('m2481', 'goo converter 2481 -> 2874 (unlit)', '50m', [26730]),
    # part 4 (50n): translated vertex shaders
    ('n2464', 'grinder / converter VS 2876 + PS 2885', '50n', [25165]),
    ('n2470', 'extending bridges VS 2877 + PS 2881', '50n', [25528]),
    ('n2564', 'rune / treadmill blocks, natla pod VS 2878 + PS 2883', '50n', [26228, 26662]),
    ('n2579', 'runes ceremony VS 2879 + PS 2884', '50n', [26602]),
    ('n2476', 'punch switch VS 2880 + PS 2882', '50n', [22844]),
    ('n2254', 'DLC 1 grapple wall / ceiling / dragon slider PS 2886 / 2887', '50n', [21164, 20345]),
]


def load(path):
    return DW.read(open(path, 'rb').read(), 'le')


def secdicts(D):
    return [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]


def objnames(path=OBJLIST):
    d = {}
    for l in open(path, encoding='utf8', errors='ignore'):
        p = l.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


def terrain_draws(s, mids):
    """[(material, local bbox lo, hi, vertex count)] of one terrain section for the materials mids."""
    d, e = s.data, '<'
    u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    T = TC.parse(d, e); H = T['H']
    ptr = dict(R.parse(s.reloc, 'le').internal)
    ml = ptr[0x0C]; mats = list(struct.unpack_from(e + '%dI' % u(ml), d, ml + 4))
    idx = np.frombuffer(d, dtype=e + 'u2', count=T['nIdx'], offset=H + T['offIdx'])
    out = []
    for slot, seq, lst in TC.draw_lists(d, T, e):
        for yi, cnt, start in lst:
            y = T['Y'][yi]
            if y[0] >= len(mats) or mats[y[0]] not in mids: continue
            vdo, _, nv, vfi = T['vbs'][y[1]]
            vf = T['vfs'][vfi]
            pos = [o for _s, o, t, _ in vf['elems'] if t == 2]
            if not pos: continue
            ii = idx[start:start + cnt].astype(np.int64); ii = np.unique(ii[ii < nv])
            if not len(ii): continue
            P = np.array([struct.unpack_from(e + '3f', d, H + vdo + k * vf['stride'] + pos[0]) for k in ii])
            out.append((mats[y[0]], P.min(0).tolist(), P.max(0).tolist(), len(P)))
    return out


def section_bbox(s):
    """bbox of every vertex of a terrain section (all vertex buffers, position element)."""
    d, e = s.data, '<'
    T = TC.parse(d, e); H = T['H']
    lo = np.full(3, np.inf); hi = np.full(3, -np.inf)
    for vdo, _, nv, vfi in T['vbs']:
        vf = T['vfs'][vfi]
        pos = [o for _s, o, t, _ in vf['elems'] if t == 2]
        if not pos or not nv: continue
        st = vf['stride']
        k = np.arange(nv)
        buf = np.frombuffer(d, dtype=np.uint8, count=nv * st, offset=H + vdo).reshape(nv, st)
        P = buf[:, pos[0]:pos[0] + 12].copy().view('<f4').reshape(nv, 3)
        lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0))
    return lo.tolist(), hi.tolist()


def tg_records(D, secs, L):
    """[(index, sec index, offset, floats[12], uniqueID, terrain section index or None)]"""
    out = []
    for k, (si, o) in enumerate(L['tgs']):
        d = secs[si]['data']
        f = struct.unpack_from('<12f', d, o)
        uid = struct.unpack_from('<I', d, o + 0x28)[0]
        ext = {so: (ti, do) for ti, so, do in R.parse(secs[si]['reloc'], 'le').external}
        tsec = None
        for so in range(o, o + 0x50, 4):
            if so in ext and D.sections[ext[so][0]].type == 12 and TC.is_terrain(D.sections[ext[so][0]].data):
                tsec = (ext[so][0], so - o); break
        out.append((k, si, o, f, uid, tsec))
    return out


def intro_list(secs, L, names):
    out = []
    for si, o in L['intros']:
        d = secs[si]['data']
        oid = struct.unpack_from('<H', d, o + 0x50)[0]
        uid = struct.unpack_from('<I', d, o + 0x58)[0]
        p = struct.unpack_from('<3f', d, o + 0x10)
        out.append(dict(uid=uid, obj=oid, name=names.get(oid, '?'), pos=[round(x, 1) for x in p]))
    return out


def cmd_tg(argv):
    D = load(argv[0]); secs = secdicts(D); L = U.level_info(secs, 'le')
    if L is None: print('not a unit DRM'); return 1
    names = objnames()
    ins = intro_list(secs, L, names)
    if ins:
        P = np.array([i['pos'] for i in ins])
        print('%d intros, position bbox (%.0f %.0f %.0f) - (%.0f %.0f %.0f)' % (len(ins), *P.min(0), *P.max(0)))
        print('intro position percentiles 5 / 50 / 95: %s' % ' | '.join(
            '%.0f %.0f %.0f' % tuple(np.percentile(P, q, 0)) for q in (5, 50, 95)))
    for i, s in enumerate(D.sections):
        if s.type == 12 and TC.is_terrain(s.data):
            try:
                lo, hi = section_bbox(s)
                print('terrain section %d (id %d): vertex bbox (%.0f %.0f %.0f) - (%.0f %.0f %.0f)' % (i, s.id, *lo, *hi))
            except Exception as ex:
                print('terrain section %d (id %d): %s' % (i, s.id, ex))
    for k, si, o, f, uid, tsec in tg_records(D, secs, L):
        line = 'TG %2d sec %d +0x%x uid %d  +00 %s  +10 %s  +20 %s' % (
            k, si, o, uid, ' '.join('%.1f' % x for x in f[0:4]), ' '.join('%.1f' % x for x in f[4:8]),
            ' '.join('%.3g' % x for x in f[8:12]))
        print(line)
        d = secs[si]['data']
        if o + 0x50 > len(d): print('       (record ends at the section end)'); continue
        rx = R.parse(secs[si]['reloc'], 'le')
        ext = {so: (ti, do) for ti, so, do in rx.external}; itn = dict(rx.internal)
        marks = []
        for so in range(o, o + 0x50, 4):
            if so in ext:
                t = D.sections[ext[so][0]]
                marks.append('+%02x->X(%d:%d+0x%x)' % (so - o, t.type, t.id, ext[so][1]))
            elif so in itn:
                marks.append('+%02x->P(+0x%x)' % (so - o, itn[so]))
        print('       words +2c..+4c %s  %s' % (' '.join('%08x' % x for x in struct.unpack_from('<9I', d, o + 0x2c)),
                                               ' '.join(marks)))
        if tsec:
            s = D.sections[tsec[0]]
            lo, hi = section_bbox(s)
            print('       terrain section %d (id %d, TG +0x%x): local bbox (%.0f %.0f %.0f) - (%.0f %.0f %.0f)' % (
                tsec[0], s.id, tsec[1], *lo, *hi))
    return 0


def is_unit(path):
    D = load(path); secs = secdicts(D)
    return D, secs, U.level_info(secs, 'le')


def cmd_index(argv):
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(OUTDIR, 'intros.json')
    dirs = [a for a in argv if not a.startswith('--') and a != out]
    names = objnames()
    files = {}
    for dd in dirs:
        for n in sorted(os.listdir(dd)):
            if n.lower().endswith('.drm') and not n.lower().endswith('_map.drm'):
                files[n.lower()] = os.path.join(dd, n)
    res = {}
    for n, p in sorted(files.items()):
        try:
            D, secs, L = is_unit(p)
        except Exception as ex:
            print('%s: read error %s' % (n, ex)); continue
        if L is None or not L['intros']: continue
        ins = intro_list(secs, L, names)
        tgs = []
        for k, si, o, f, uid, tsec in tg_records(D, secs, L):
            tgs.append(dict(k=k, f=[round(x, 2) for x in f], uid=uid,
                            tsec=None if not tsec else D.sections[tsec[0]].id))
        res[n[:-4]] = dict(path=p, intros=ins, tgs=tgs)
        print('%-36s %4d intros, %3d terrain groups  (%s)' % (n, len(ins), len(tgs), p))
        del D, secs
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w'), indent=0)
    print('-> %s (%d units)' % (out, len(res)))
    return 0


def cmd_mats(argv):
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(OUTDIR, 'mats.json')
    trees = [a for a in argv if not a.startswith('--') and a != out]
    want = {m for g in GROUPS for m in g[3]}
    files = {}
    for t in trees:
        for n in sorted(os.listdir(t)):
            if n.lower().endswith('.drm'): files[n.lower()] = os.path.join(t, n)
    res = {}
    for n, p in sorted(files.items()):
        D = load(p)
        have = sorted({s.id for s in D.sections if s.type == 10 and s.id in want})
        if not have: continue
        ent = dict(path=p, mats=have, terrain=[])
        secs = secdicts(D); L = U.level_info(secs, 'le')
        if L is not None:
            tgmap = {}
            for k, si, o, f, uid, tsec in tg_records(D, secs, L):
                if tsec: tgmap.setdefault(tsec[0], []).append(k)
            for i, s in enumerate(D.sections):
                if s.type != 12 or not TC.is_terrain(s.data): continue
                try:
                    for m, lo, hi, nv in terrain_draws(s, set(have)):
                        ent['terrain'].append(dict(sec=s.id, tg=tgmap.get(i, []), mat=m, lo=lo, hi=hi, nv=nv))
                except Exception as ex:
                    print('  %s section %d: %s' % (n, s.id, ex))
            ent['unit'] = True
        res[n[:-4]] = ent
        print('%-44s %3d materials%s  (%s)' % (n, len(have), ', unit, %d terrain draws' % len(ent['terrain'])
              if L is not None else '', p))
        del D
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w'), indent=0)
    print('-> %s' % out)
    return 0


def cmd_report(argv):
    fi = argv[argv.index('--intros') + 1] if '--intros' in argv else os.path.join(OUTDIR, 'intros.json')
    fm = argv[argv.index('--mats') + 1] if '--mats' in argv else os.path.join(OUTDIR, 'mats.json')
    near = int(argv[argv.index('--near') + 1]) if '--near' in argv else 3
    maxn = int(argv[argv.index('--max') + 1]) if '--max' in argv else 3
    only = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
    I = json.load(open(fi)); M = json.load(open(fm))
    names = objnames(); byname = {v.lower(): k for k, v in names.items()}
    import objlists as O
    recs, _ = O.read_objlist(open(OBJDAT, 'rb').read(), 'be')
    loaders = collections.defaultdict(list)
    for un, ids in recs:
        for i in ids: loaders[i].append(un.split('\\')[-1])
    for key, label, tree, mats in GROUPS:
        if only and key not in only: continue
        print('\n=== %s: %s [%s] materials %s' % (key, label, tree, mats))
        fl = [(n, e) for n, e in sorted(M.items()) if set(e['mats']) & set(mats)]
        if not fl: print('  no file of the trees has these materials'); continue
        for n, e in fl:
            got = sorted(set(e['mats']) & set(mats))
            if e.get('unit'):
                tr = [t for t in e['terrain'] if t['mat'] in mats]
                print('  unit %s %s: %d terrain draws' % (n, got, len(tr)))
                agg = collections.defaultdict(list)
                for t in tr: agg[(t['sec'], tuple(t['tg']))].append(t)
                for (sec, tg), ts in sorted(agg.items()):
                    lo = np.min([t['lo'] for t in ts], 0); hi = np.max([t['hi'] for t in ts], 0)
                    print('    terrain sec %d mats %s: bbox (%.0f %.0f %.0f) - (%.0f %.0f %.0f), %d verts' % (
                        sec, sorted({t['mat'] for t in ts}), *lo, *hi, sum(t['nv'] for t in ts)))
                    u = I.get(n)
                    # the largest draws: centre (same frame as the intro positions - see the module doc) + the
                    # nearest intros of the unit, so a spot can be reached with player.goto <intro id>
                    for t in sorted(ts, key=lambda t: -t['nv'])[:maxn]:
                        c = (np.array(t['lo']) + np.array(t['hi'])) / 2
                        nb = []
                        if u:
                            nb = sorted(((float(np.linalg.norm(np.array(y['pos']) - c)), y) for y in u['intros']
                                         if any(y['pos'])), key=lambda q: q[0])[:near]
                        print('      draw mat %d %5d verts centre (%.0f %.0f %.0f) size (%.0f %.0f %.0f)  near: %s' % (
                            t['mat'], t['nv'], *c, *(np.array(t['hi']) - np.array(t['lo'])),
                            '; '.join('%s %d (%.0f)' % (y['name'], y['uid'], dd) for dd, y in nb)))
                continue
            oid = byname.get(n.lower())
            print('  object %s id %s: loaded by %s' % (n, oid, ', '.join(sorted(set(loaders.get(oid, [])))) or '-'))
            if oid is None: continue
            shown = 0
            for cand in [n.lower()] + SPAWNERS.get(n.lower(), []):
                cid = byname.get(cand)
                for un, u in sorted(I.items()):
                    hits = [x for x in u['intros'] if x['obj'] == cid]
                    if not hits: continue
                    shown += 1
                    print('    %s: %d intros%s' % (un, len(hits), '' if cand == n.lower() else ' of the spawner ' + cand))
                    for x in hits[:maxn]:
                        p = np.array(x['pos'])
                        nb = sorted(((float(np.linalg.norm(np.array(y['pos']) - p)), y) for y in u['intros']
                                     if y['uid'] != x['uid'] and any(y['pos'])), key=lambda t: t[0])[:near]
                        print('      intro %6d pos %s   near: %s' % (x['uid'], x['pos'], '; '.join(
                            '%s %d (%.0f)' % (y['name'], y['uid'], dd) for dd, y in nb)))
                    if len(hits) > maxn: print('      ... %d more: %s' % (len(hits) - maxn, ' '.join(
                        str(x['uid']) for x in hits[maxn:])))
            if not shown: print('    no intro (of it or a known spawner) in any indexed unit')
    return 0


# objects that no unit places as an Intro: the objects that spawn them (names from the DLC object list)
SPAWNERS = {
    'viking_thrall_dlc2_': ['viking_thrall_pool_generator_dlc2_'],
    'viking_thrall_tutorial_dlc2_': ['viking_thrall_tutorial_pool_generator_dlc2_'],
    'yeti_thrall_dlc2_': ['yeti_thrall_pool_generator_arc_dlc2_'],
    'yeti_thrall_armored_chunkdoll_dlc_2_': ['yeti_thrall_armored_dlc2_'],
    'dlc2_uo_treadmill_block_spawned': ['dlc2_uo_treadmill_block_spawner'],
    'dlc2_uo_treadmill_block_spawned_faulty_a': ['dlc2_uo_treadmill_block_spawner'],
    'dlc2_uo_treadmill_block_spawned_faulty_b': ['dlc2_uo_treadmill_block_spawner'],
    'dlc2_uo_energy_ball': ['dlc2_uo_energy_pillar', 'dlc2_uo_energy_pillar_machine'],
    'dlc2_uo_goo_converter_ball': ['dlc2_uo_gooconverter'],
    'dlc2_uo_goo_upcolumn': ['dlc_fx_goo_upcolumn_pit'],
}


def cmd_near(argv):
    """near UNIT X Y Z [N] [--intros F]: the N intros of UNIT nearest to a position (e.g. a TruMenu overlay value)."""
    fi = argv[argv.index('--intros') + 1] if '--intros' in argv else os.path.join(OUTDIR, 'intros.json')
    a = [x for x in argv if not x.startswith('--') and x != fi]
    I = json.load(open(fi)); u = I[a[0]]; p = np.array([float(x) for x in a[1:4]]); n = int(a[4]) if len(a) > 4 else 10
    for dd, y in sorted(((float(np.linalg.norm(np.array(y['pos']) - p)), y) for y in u['intros']), key=lambda q: q[0])[:n]:
        print('%8.0f  intro %6d %-40s pos %s' % (dd, y['uid'], y['name'], y['pos']))
    return 0


def cmd_portals(argv):
    """portals UNIT.drm [...]: the StreamUnitPortal names of each unit (= its neighbour units; play order hints)."""
    for p in argv:
        D = load(p); secs = secdicts(D); L = U.level_info(secs, 'le')
        if L is None: print('%s: not a unit' % p); continue
        names = []
        for si, o in L['portals']:
            raw = secs[si]['data'][o:o + 128]
            names.append(raw.split(b'\0', 1)[0].decode('latin-1'))
        print('%-34s -> %s' % (os.path.basename(p)[:-4], ', '.join(names)))
    return 0


def cmd_files(argv):
    """files [--mats F]: per tree file the shader groups (keys of GROUPS) whose materials it carries."""
    fm = argv[argv.index('--mats') + 1] if '--mats' in argv else os.path.join(OUTDIR, 'mats.json')
    M = json.load(open(fm))
    for n, e in sorted(M.items()):
        ks = [g[0] for g in GROUPS if set(g[3]) & set(e['mats'])]
        if e.get('unit'):
            tm = {t['mat'] for t in e['terrain']}
            kt = [g[0] for g in GROUPS if set(g[3]) & tm]
            print('%-44s %s | terrain draws: %s' % (n, ' '.join(ks), ' '.join(kt)))
        else:
            print('%-44s %s' % (n, ' '.join(ks)))
    return 0


def cmd_list(argv):
    """list UNIT [REGEX] [--intros F]: every intro of a unit (optionally names matching REGEX)."""
    import re
    fi = argv[argv.index('--intros') + 1] if '--intros' in argv else os.path.join(OUTDIR, 'intros.json')
    a = [x for x in argv if not x.startswith('--') and x != fi]
    I = json.load(open(fi)); rx = re.compile(a[1]) if len(a) > 1 else None
    for y in I[a[0]]['intros']:
        if rx is None or rx.search(y['name']):
            print('intro %6d obj %4d %-44s pos %s' % (y['uid'], y['obj'], y['name'], y['pos']))
    return 0


def main(argv):
    if not argv: print(__doc__); return 2
    return {'tg': cmd_tg, 'index': cmd_index, 'mats': cmd_mats, 'report': cmd_report, 'near': cmd_near,
            'list': cmd_list, 'files': cmd_files, 'portals': cmd_portals}[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
