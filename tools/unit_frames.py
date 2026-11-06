"""Unit coordinate frames (read-only): do the stream units of a level share one coordinate frame, or does the engine
relocate them (cdc RelocateWorld / RelocateUnit, strings in the 2007 prototype SceneLayer.obj)?

Background: the TruMenu position overlay (Instance +0x20, live) and the intro positions read from the unit DRMs
(Intro +0x10, tools/unit_ids.level_info) disagree in dlc_level2_start screenshots by about (+270, +2876, -1236).
A stream unit portal (StreamUnitPortal, 0x100 B, name[128], +0x80 u16 id of the matching portal in the destination
unit, +0x82 u16 own id, +0x84 u16 destination unit) carries the portal geometry; the engine places a neighbour unit so
that its matching portal lies on top of the current unit's portal. Comparing the geometry of the two portal records of
one connection gives the relocation offset between the two unit frames (0 = shared frame).

Modes (from the repository root, nothing is written except with --out):
  ../bin/pyt -t 600 tools/unit_frames.py dump UNIT.drm [...]
      every portal: name, ids, the 30 words after +0x88 as floats (layout check)
  ../bin/pyt -t 900 tools/unit_frames.py pairs DIR [DIR ...]
      every unit DRM of the folders (later folders replace a unit of the same name): portal connections A -> B with
      the matching record in B, centroid of the portal points in A and in B, offset = A - B (B's frame + offset =
      A's frame)
  ../bin/pyt -t 900 tools/unit_frames.py level UNIT.drm
      Level section 0: words +0x00..+0xa0 as hex / float (looking for a stored unit offset)
  ../bin/pyt -t 900 tools/unit_frames.py reloc UNIT.drm [...]
      the RelocateWorld offset of a level load that starts in the unit (PC STREAM_LevelLoadAndInit 0x5d30d0:
      offset = -[Terrain +0x10].xyz), with the raw record
  ../bin/pyt -t 900 tools/unit_frames.py intro UNIT.drm UID[,UID...]|all
      Intro records (0x90 B) as hex / float rows; counts intros whose +0x10 and +0x30 vectors differ
  ../bin/pyt -t 900 tools/unit_frames.py floor UNIT.drm X Y Z [X Y Z ...] [--dz N]
      terrain surfaces (render triangles) in the vertical column through each point: is there a floor at the feet?
  ../bin/pyt -t 900 tools/unit_frames.py origins DIR [DIR ...]
      Level +0x80 of every unit ("origin"; the unit-load step 0x5d1cd0 subtracts it from all intro positions)
  ../bin/pyt -t 900 tools/unit_frames.py live UNIT.drm UID[,UID...] [--up N]
      intro data position -> live position (TruMenu overlay / player.teleport) = data - origin
  ../bin/pyt -t 900 tools/unit_frames.py tolive|todata UNIT.drm X Y Z [...]
      convert free coordinates between the two frames
  ../bin/pyt -t 900 tools/unit_frames.py memdump DUMP.dmp [--intros work/shader_tour/intros.json] [--show N]
      full tru.exe minidump: loaded units (Level +0x80, runtime P = [[Level+0]+0x10]+0) and live - data per unit

Result (03.11.2026, docs Befund-Position-und-Schrotflinte.md): live = data - Level[+0x80] of the unit Lara is in.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, unit_ids as U


def load(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    return D, secs, U.level_info(secs, 'le')


def portals(secs, L):
    out = []
    for si, o in L['portals']:
        d = secs[si]['data']
        name = d[o:o + 128].split(b'\0', 1)[0].decode('latin-1')
        to_id, own, dest = struct.unpack_from('<3H', d, o + 0x80)
        fl = struct.unpack_from('<30f', d, o + 0x88)
        words = struct.unpack_from('<30I', d, o + 0x88)
        out.append(dict(name=name, to=to_id, own=own, dest=dest, f=fl, w=words, sec=si, off=o))
    return out


def fmt(x):
    if x != x or abs(x) > 1e7 or (x != 0 and abs(x) < 1e-6): return '   .'
    return '%.1f' % x


def cmd_dump(argv):
    for p in argv:
        D, secs, L = load(p)
        if L is None: print('%s: not a unit' % p); continue
        print('== %s: %d portals' % (os.path.basename(p), len(L['portals'])))
        for k, q in enumerate(portals(secs, L)):
            print(' [%d] -> %-28s to %d own %d dest %d  (sec %d +0x%x)' % (k, q['name'], q['to'], q['own'], q['dest'],
                                                                         q['sec'], q['off']))
            for r in range(0, 30, 6):
                print('      +%02x %s' % (0x88 + 4 * r, ' '.join('%10s' % fmt(x) for x in q['f'][r:r + 6])))
    return 0


def quad_points(q):
    """the portal points: every vec4 (+0x90 + 16*k, k = 0..6) whose xyz is finite and not all zero.
    Returns [(x, y, z)] - the caller compares like with like (same record layout on both sides).
    2026-11-06: was +0x88 + 16*k (mixed the w of one vec4 with the xy of the next); the engine aligns the vec4 at
    +0x90 (STREAM_ConnectStreamToStream 0x5d13e0, docs Befund-Unit-Streaming-0611.md), q['f'] starts at +0x88."""
    pts = []
    for k in range(7):
        a = q['f'][2 + 4 * k:2 + 4 * k + 3]
        if all(v == v and abs(v) < 1e7 for v in a) and any(a): pts.append(a)
    return pts


def cmd_pairs(argv):
    files = {}
    for dd in argv:
        for n in sorted(os.listdir(dd)):
            if n.lower().endswith('.drm') and not n.lower().endswith('_map.drm'):
                files[n.lower()[:-4]] = os.path.join(dd, n)
    units = {}
    for n, p in sorted(files.items()):
        try:
            D, secs, L = load(p)
        except Exception as ex:
            continue
        if L is None or not L['portals']: continue
        unit_id = struct.unpack_from('<I', secs[0]['data'], 0x4c)[0]
        units[n] = dict(id=unit_id, portals=portals(secs, L))
        del D, secs
    byid = {u['id']: n for n, u in units.items()}
    print('%d units with portals' % len(units))
    for n, u in sorted(units.items()):
        for q in u['portals']:
            tgt = q['name'].split('\\')[-1].lower()
            if tgt not in units:
                print('%-30s -> %-30s own %4d to %4d: destination not in the folders' % (n, tgt, q['own'], q['to']))
                continue
            m = [r for r in units[tgt]['portals'] if r['own'] == q['to']]
            if not m:
                print('%-30s -> %-30s own %4d to %4d: no record with own id %d' % (n, tgt, q['own'], q['to'], q['to']))
                continue
            r = m[0]
            a, b = quad_points(q), quad_points(r)
            if len(a) != len(b) or not a:
                print('%-30s -> %-30s own %4d to %4d: point counts %d / %d' % (n, tgt, q['own'], q['to'], len(a), len(b)))
                continue
            ca = [sum(v[i] for v in a) / len(a) for i in range(3)]
            cb = [sum(v[i] for v in b) / len(b) for i in range(3)]
            off = [ca[i] - cb[i] for i in range(3)]
            # the engine's own relocation: [A portal +0x90] - [B portal +0x90] (STREAM_ConnectStreamToStream 0x5d13e0)
            eng = [q['f'][2 + i] - r['f'][2 + i] for i in range(3)]
            print('%-30s -> %-30s own %4d to %4d: centre A (%.1f %.1f %.1f)  B (%.1f %.1f %.1f)  A-B (%.1f %.1f %.1f)'
                  '  engine +0x90 A-B (%.1f %.1f %.1f)' % (n, tgt, q['own'], q['to'], *ca, *cb, *off, *eng))
    return 0


def cmd_level(argv):
    D, secs, L = load(argv[0])
    d = secs[0]['data']
    rx = R.parse(secs[0]['reloc'], 'le')
    ext = {so: (si, do) for si, so, do in rx.external}; itn = dict(rx.internal)
    for o in range(0, min(len(d), 0xa0), 4):
        w = struct.unpack_from('<I', d, o)[0]; f = struct.unpack_from('<f', d, o)[0]
        mark = ''
        if o in ext: mark = '-> sec %d (%d:%d) +0x%x' % (ext[o][0], D.sections[ext[o][0]].type, D.sections[ext[o][0]].id,
                                                          ext[o][1])
        elif o in itn: mark = '-> +0x%x' % itn[o]
        print('+%02x %08x %12s %s' % (o, w, fmt(f), mark))
    return 0


def start_offset(D, secs, L):
    """The vector STREAM_LevelLoadAndInit (PC 0x5d30d0) hands to RelocateWorld (0x5cbe90) for the unit a level load
    starts with: Terrain = [Level +0]; P = [Terrain +0x10]; offset = (-0.0 - P.x, -0.0 - P.y, -0.0 - P.z, 0)
    (0x5d3180..0x5d31ca; P = NULL -> offset 0). Returns (P section index, P offset, P xyz) or None."""
    ti = L['terrain']
    rt = R.parse(secs[ti]['reloc'], 'le')
    ext = {so: (si, do) for si, so, do in rt.external}; itn = dict(rt.internal)
    if 0x10 in ext: si, do = ext[0x10]
    elif 0x10 in itn: si, do = ti, itn[0x10]
    else: return None
    d = secs[si]['data']
    if do + 12 > len(d): return (si, do, None)
    return (si, do, struct.unpack_from('<3f', d, do))


def cmd_reloc(argv):
    """reloc UNIT.drm [...]: Terrain words, the record [Terrain +0x10] (first 0x40 bytes) and the RelocateWorld offset
    a level load that starts in this unit applies (live = data + offset)."""
    for p in argv:
        D, secs, L = load(p)
        if L is None: print('%s: not a unit' % p); continue
        ti = L['terrain']; td = secs[ti]['data']
        print('== %s: Terrain = section %d (%d:%d), words %s' % (os.path.basename(p), ti, D.sections[ti].type,
              D.sections[ti].id, ' '.join('%08x' % w for w in struct.unpack_from('<6I', td, 0))))
        r = start_offset(D, secs, L)
        if r is None: print('   [Terrain +0x10] = NULL -> RelocateWorld (0, 0, 0)'); continue
        si, do, xyz = r
        d = secs[si]['data']
        n = min(0x40, len(d) - do)
        print('   [Terrain +0x10] -> section %d (%d:%d, %d B) +0x%x' % (si, D.sections[si].type, D.sections[si].id,
                                                                     len(d), do))
        for o in range(0, n - n % 16, 16):
            ws = struct.unpack_from('<4I', d, do + o); fs = struct.unpack_from('<4f', d, do + o)
            print('     +%02x %s   %s' % (o, ' '.join('%08x' % w for w in ws), ' '.join('%10s' % fmt(x) for x in fs)))
        if xyz is not None:
            off = tuple(-v for v in xyz)
            print('   RelocateWorld offset = -P = (%.1f %.1f %.1f)  ->  live = data + offset' % off)
    return 0


def cmd_intro(argv):
    """intro UNIT.drm UID[,UID...]|all: the 0x90-byte Intro records as hex / float rows (+0x10 vs +0x30 check)."""
    D, secs, L = load(argv[0])
    want = None if argv[1] == 'all' else {int(x) for x in argv[1].split(',')}
    diff = 0; total = 0
    for si, o in L['intros']:
        d = secs[si]['data']
        uid = struct.unpack_from('<I', d, o + 0x58)[0]
        a = struct.unpack_from('<3f', d, o + 0x10); b = struct.unpack_from('<3f', d, o + 0x30)
        total += 1; diff += a != b
        if want is not None and uid not in want: continue
        print('intro %d (sec %d +0x%x)  +0x10 %s  +0x30 %s%s' % (uid, si, o, ' '.join('%.1f' % v for v in a),
              ' '.join('%.1f' % v for v in b), '' if a == b else '  DIFFERENT'))
        if want is not None:
            for r in range(0, 0x90, 16):
                ws = struct.unpack_from('<4I', d, o + r); fs = struct.unpack_from('<4f', d, o + r)
                print('   +%02x %s   %s' % (r, ' '.join('%08x' % w for w in ws), ' '.join('%10s' % fmt(x) for x in fs)))
    print('%d intros, %d with +0x10 != +0x30' % (total, diff))
    return 0


def terrain_triangles(D):
    """All render triangles of the unit's terrain sections as an (n, 3, 3) float array + material per triangle.
    Index lists are read as triangle lists (count % 3 == 0 checked per batch; other batches are skipped)."""
    import numpy as np
    import terrain_convert as TC
    tris = []; mats = []; skipped = 0
    for s in D.sections:
        if s.type != 12 or not TC.is_terrain(s.data): continue
        d, e = s.data, '<'
        T = TC.parse(d, e); H = T['H']
        ptr = dict(R.parse(s.reloc, 'le').internal)
        ml = ptr.get(0x0C)
        ml_ids = list(struct.unpack_from(e + '%dI' % struct.unpack_from(e + 'I', d, ml)[0], d, ml + 4)) if ml else []
        idx = np.frombuffer(d, dtype=e + 'u2', count=T['nIdx'], offset=H + T['offIdx'])
        cache = {}
        for slot, seq, lst in TC.draw_lists(d, T, e):
            for yi, cnt, start in lst:
                if cnt % 3: skipped += 1; continue
                y = T['Y'][yi]
                vb = y[1]
                if vb not in cache:
                    vdo, _, nv, vfi = T['vbs'][vb]
                    vf = T['vfs'][vfi]
                    pos = [o for _s, o, t, _ in vf['elems'] if t == 2]
                    if not pos or not nv: cache[vb] = None
                    else:
                        st = vf['stride']
                        buf = np.frombuffer(d, dtype=np.uint8, count=nv * st, offset=H + vdo).reshape(nv, st)
                        cache[vb] = buf[:, pos[0]:pos[0] + 12].copy().view('<f4').reshape(nv, 3)
                P = cache[vb]
                if P is None: continue
                ii = idx[start:start + cnt].astype(np.int64)
                if (ii >= len(P)).any(): skipped += 1; continue
                tris.append(P[ii].reshape(-1, 3, 3))
                m = ml_ids[y[0]] if y[0] < len(ml_ids) else -1
                mats.append(np.full(len(ii) // 3, m))
    if not tris: return None, None, skipped
    return np.concatenate(tris), np.concatenate(mats), skipped


def cmd_floor(argv):
    """floor UNIT.drm X Y Z [X Y Z ...] [--dz N]: terrain surfaces straight above / below each point (z of every
    render triangle whose xy projection contains the point), nearest first - is there a floor under Lara's feet?"""
    import numpy as np
    dz = float(argv[argv.index('--dz') + 1]) if '--dz' in argv else 1500.0
    a = [x for i, x in enumerate(argv) if not x.startswith('--') and (i == 0 or argv[i - 1] != '--dz')]
    D, secs, L = load(a[0])
    tri, mat, skipped = terrain_triangles(D)
    print('%s: %d triangles (%d batches skipped)' % (os.path.basename(a[0]), 0 if tri is None else len(tri), skipped))
    if tri is None: return 1
    A, B, C = tri[:, 0], tri[:, 1], tri[:, 2]
    for k in range(1, len(a) - 2, 3):
        x, y, z = float(a[k]), float(a[k + 1]), float(a[k + 2])
        # barycentric in xy
        v0 = C[:, :2] - A[:, :2]; v1 = B[:, :2] - A[:, :2]; v2 = np.array([x, y]) - A[:, :2]
        d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1e-6
        u = np.where(ok, (d11 * d20 - d01 * d21) / np.where(ok, den, 1), -1)
        v = np.where(ok, (d00 * d21 - d01 * d20) / np.where(ok, den, 1), -1)
        inside = ok & (u >= -1e-4) & (v >= -1e-4) & (u + v <= 1 + 1e-4)
        zs = A[inside, 2] + u[inside] * (C[inside, 2] - A[inside, 2]) + v[inside] * (B[inside, 2] - A[inside, 2])
        ms = mat[inside]
        rows = sorted(set((round(float(q), 0), int(m)) for q, m in zip(zs, ms)), key=lambda r: abs(r[0] - z))
        near = [r for r in rows if abs(r[0] - z) <= dz]
        below = [r for r in rows if r[0] <= z + 5]
        nb = max(below, key=lambda r: r[0]) if below else None
        print('point (%.0f %.0f %.0f): %d surfaces in the column; nearest floor at or below: %s; within %.0f: %s' % (
            x, y, z, len(rows), 'none' if nb is None else '%.0f (mat %d, %.0f below)' % (nb[0], nb[1], z - nb[0]),
            dz, ', '.join('%.0f (mat %d)' % r for r in near[:12]) or '-'))
    return 0


def unit_origin(secs):
    """Level +0x80 (vec4): the vector the unit-load step (PC 0x5d1cd0, 0x5d1df3..0x5d1efe) subtracts from every Intro
    +0x10 / +0x30 and the other DTP position records (+0x1c/+0x20, +0x58/+0x5c, +0xac/+0xb0) - live = data - origin."""
    return struct.unpack_from('<3f', secs[0]['data'], 0x80)


def unit_files(dirs):
    files = {}
    for dd in dirs:
        for n in sorted(os.listdir(dd)):
            if n.lower().endswith('.drm') and not n.lower().endswith('_map.drm'):
                files[n.lower()[:-4]] = os.path.join(dd, n)
    return files


def cmd_origins(argv):
    """origins DIR [DIR ...]: Level +0x80 of every unit DRM (later folders replace a unit of the same name)."""
    for n, p in sorted(unit_files(argv).items()):
        try:
            D, secs, L = load(p)
        except Exception:
            continue
        if L is None: continue
        o = unit_origin(secs)
        print('%-34s origin (Level +0x80) %10.1f %10.1f %10.1f   live = data - origin   (%s)' % (n, *o, p))
        del D, secs
    return 0


_NAMES = None


def objname(oid):
    """object name for an object id of a PC unit DRM: ids < 822 are PC base ids (pc_objectlist.txt; the DLC converter
    remaps base objects by name), 822.. are DLC ids (identity, dlc_pack11_objectlist.txt)."""
    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for fn, keep in (('pc_objectlist.txt', lambda k: k < 822), ('dlc_pack11_objectlist.txt', lambda k: k >= 822)):
            p = os.path.join('work', 'generic', 'lists', fn)
            if not os.path.exists(p): continue
            for l in open(p, encoding='utf8', errors='ignore'):
                a = l.strip().split(',', 1)
                if len(a) == 2 and a[0].isdigit() and keep(int(a[0])): _NAMES[int(a[0])] = a[1]
    return _NAMES.get(oid, '?')


def cmd_live(argv):
    """live UNIT.drm UID[,UID...] [--up N]: data position of the intros and the live position (overlay / player.teleport
    frame while Lara is in that unit) = data - origin; --up N adds N to the live z (stand above the spot)."""
    up = float(argv[argv.index('--up') + 1]) if '--up' in argv else 0.0
    a = [x for i, x in enumerate(argv) if not x.startswith('--') and (i == 0 or argv[i - 1] != '--up')]
    D, secs, L = load(a[0])
    o = unit_origin(secs)
    want = {int(x) for x in a[1].split(',')}
    print('%s: origin %.1f %.1f %.1f' % (os.path.basename(a[0]), *o))
    for si, off in L['intros']:
        d = secs[si]['data']
        uid = struct.unpack_from('<I', d, off + 0x58)[0]
        if uid not in want: continue
        p = struct.unpack_from('<3f', d, off + 0x10)
        oid = struct.unpack_from('<H', d, off + 0x50)[0]
        sid = struct.unpack_from('<I', d, off + 0x7c)[0]
        lv = (p[0] - o[0], p[1] - o[1], p[2] - o[2] + up)
        print('intro %6d obj %4d %-30s script %5d  data %9.1f %9.1f %9.1f  ->  live %9.1f %9.1f %9.1f' % (
            uid, oid, objname(oid), sid, *p, *lv))
    return 0


def cmd_tolive(argv):
    """tolive UNIT.drm X Y Z [X Y Z ...]: data -> live for free coordinates; todata UNIT.drm X Y Z: live -> data."""
    D, secs, L = load(argv[0])
    o = unit_origin(secs)
    for k in range(1, len(argv) - 2, 3):
        x, y, z = float(argv[k]), float(argv[k + 1]), float(argv[k + 2])
        print('data %.1f %.1f %.1f -> live %.1f %.1f %.1f' % (x, y, z, x - o[0], y - o[1], z - o[2]))
    return 0


def cmd_todata(argv):
    D, secs, L = load(argv[0])
    o = unit_origin(secs)
    for k in range(1, len(argv) - 2, 3):
        x, y, z = float(argv[k]), float(argv[k + 1]), float(argv[k + 2])
        print('live %.1f %.1f %.1f -> data %.1f %.1f %.1f' % (x, y, z, x + o[0], y + o[1], z + o[2]))
    return 0


def cmd_memdump(argv):
    """memdump DUMP.dmp [--intros work/shader_tour/intros.json] [--show N]: a full minidump of tru.exe -> the loaded
    stream units (table 0xdbab40, 0xd8 per entry: +0 id, +4 state (2 = loaded), +8 Level*, +0xc name) with Level +0x80
    in memory, and every instance of the active list ([0xd98d54], next +8) with intro id +0x58, position +0x20 and
    stream unit +0xe0, compared with the intro data position: live - data per unit (expect -origin)."""
    import json, collections
    import minidump_read as MR
    fi = argv[argv.index('--intros') + 1] if '--intros' in argv else os.path.join('work', 'shader_tour', 'intros.json')
    show = int(argv[argv.index('--show') + 1]) if '--show' in argv else 6
    M = MR.Minidump(argv[0])
    I = json.load(open(fi))
    f3 = lambda va: struct.unpack('<3f', M.read(va, 12))
    units = {}
    for k in range(32):
        e = 0xdbab40 + 0xd8 * k
        raw = M.read(e, 0x50)
        if raw is None: continue
        uid, = struct.unpack_from('<I', raw, 0); st = raw[4]; lev, = struct.unpack_from('<I', raw, 8)
        name = raw[0xc:0x4c].split(b'\0', 1)[0].decode('latin-1')
        if st == 0 or not name: continue
        o = f3(lev + 0x80) if lev and M.read(lev + 0x80, 12) else None
        # [[Level +0] +0x10] = the record STREAM_LevelLoadAndInit reads (P); RelocateWorld(-P) re-centres on it
        sig = None
        if lev and M.read(lev, 4):
            ter = M.u32(lev)
            if ter and M.read(ter + 0x10, 4):
                sp = M.u32(ter + 0x10)
                if sp and M.read(sp, 12): sig = f3(sp)
        units[uid] = name
        print('unit table [%2d] id %4d state %d Level 0x%08x %-26s Level+0x80 %s   [Terrain+0x10]+0 (P) %s' % (
            k, uid, st, lev, name, 'n/a' if o is None else '%.1f %.1f %.1f' % o,
            'n/a' if sig is None else '%.1f %.1f %.1f' % sig))
    inst = M.u32(0xd98d54); n = 0
    per = collections.defaultdict(list)
    while inst and n < 4096:
        raw = M.read(inst, 0x100)
        if raw is None: break
        intro, = struct.unpack_from('<I', raw, 0x58); unit, = struct.unpack_from('<I', raw, 0xe0)
        pos = struct.unpack_from('<3f', raw, 0x20)
        un = units.get(unit, '?%d' % unit)
        u = I.get(un)
        if u:
            for x in u['intros']:
                if x['uid'] == intro:
                    per[un].append((intro, x['name'], x['pos'], pos)); break
        n += 1
        inst, = struct.unpack_from('<I', raw, 8)
    print('%d instances walked' % n)
    for un, rows in sorted(per.items()):
        diffs = collections.Counter(tuple(round(l[i] - d[i], 1) for i in range(3)) for _, _, d, l in rows)
        print('== %s: %d instances with a data intro; live - data (count): %s' % (
            un, len(rows), '; '.join('(%.1f %.1f %.1f) x%d' % (*k, c) for k, c in diffs.most_common(4))))
        for intro, nm, d, l in rows[:show]:
            print('   intro %6d %-34s data %9.1f %9.1f %9.1f   live %9.1f %9.1f %9.1f' % (intro, nm, *d, *l))
    return 0


def main(argv):
    modes = {'dump': cmd_dump, 'pairs': cmd_pairs, 'level': cmd_level, 'reloc': cmd_reloc, 'intro': cmd_intro,
             'floor': cmd_floor, 'origins': cmd_origins, 'live': cmd_live, 'tolive': cmd_tolive, 'todata': cmd_todata,
             'memdump': cmd_memdump}
    if not argv or argv[0] not in modes:
        print(__doc__); return 2
    return modes[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
