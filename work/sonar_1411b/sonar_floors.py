r"""Sonar 1411b: floor masks + portals of the PDA sonar map files (<unit>_map.drm) and a replay of the game's load /
draw rule (0x6e53f0 open -> 0x6e4e80 load -> callback 0x6e4df0 -> 0x6df600 mask -> 0x6e2e60 neighbours; draw 0x6e4130).
Read-only. Usage (from trudlcport):
  ../bin/pyt work/sonar_1411b/sonar_floors.py hdr NAME_map.drm [...]       header: mask, portals (name, ids, position)
  ../bin/pyt work/sonar_1411b/sonar_floors.py chain START [MAXUNITS]        the game's rule from START + AllFloors variants
  ../bin/pyt work/sonar_1411b/sonar_floors.py all                           mask + portal count + faces of every base map
Sources: base maps from the PC bigfile (little endian, the files the game reads); a name the bigfile lacks (DLC) from the
Xbox DLC packs (big endian, same header layout - the converter keeps header words).
"""
import sys, os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'sonar_1411'))
import drm_reloc as R, drm_write as DW          # noqa: E402
import map_mesh_fix as M                        # noqa: E402
import dtp_word_classes as C                    # noqa: E402
import sonar_maps as SM                         # noqa: E402

_cache = {}


def sections(nm):
    """(endian, source, [(type, data, reloc bytes)]) or (None, 'missing', [])"""
    if nm in _cache: return _cache[nm]
    ps = C.find(C.PC, 'le', 'pc-w' + C.BS + nm)
    if ps:
        r = ('le', 'PC bigfile', [(s['type'], s['data'], s['reloc']) for s in ps])
    else:
        from convert_dlc import raw_dlc
        raw, src = raw_dlc(nm)
        if raw is None: r = (None, 'missing', [])
        else: r = ('be', 'Xbox ' + src.split('/')[-1], [(s.type, s.data, s.reloc) for s in DW.read(raw, 'be').sections])
    _cache[nm] = r
    return r


def cstr(d, o):
    e = d.find(b'\0', o)
    return d[o:e if e >= 0 else len(d)].decode('latin1')


def header(nm):
    """dict(mask, raw10, portals=[(name, id4, id8, (x, y, z))], faces, verts, meshes, src) or None (no file)"""
    e, src, secs = sections(nm)
    if e is None: return None
    E = '>' if e == 'be' else '<'
    # the header section = the one whose data starts with the map header (mesh pointers / beebbeeb words, +8 portal count);
    # the game takes it as the DRM's root (section 0)
    t, d, rl = secs[0]
    d = bytes(d or b''); rel = R.parse(bytes(rl or b''), e)
    itn = dict(rel.internal)
    res = dict(src=src, endian=e, size0=len(d), mask=None, raw10=d[0x10:0x14].hex(' ') if len(d) >= 0x14 else '',
               portals=[], faces=0, verts=0, meshes=[])
    if len(d) >= 0x14:
        res['mask'] = d[0x10]
        n, = struct.unpack_from(E + 'H', d, 8)
        po = itn.get(0xc)
        for k in range(n if po is not None else 0):
            o = po + 32 * k
            if o + 32 > len(d): break
            nmo = itn.get(o)
            name = cstr(d, nmo) if nmo is not None else '?'
            i4, i8 = struct.unpack_from(E + '2I', d, o + 4)
            pos = struct.unpack_from(E + '3f', d, o + 16)
            res['portals'].append((name, i4, i8, pos))
    res['skipflag'] = 0
    for t2, d2, rl2 in secs:
        if t2 != 13 or d2 is None: continue
        d2 = bytes(d2); rel2 = R.parse(bytes(rl2 or b''), e)
        mi = SM.mesh_info(d2, rel2, e)
        if mi:
            res['faces'] += mi['faces']; res['verts'] += mi['verts']
            res['meshes'].append((mi['faces'], mi['verts']))
            m = M.find_mesh(d2, rel2, e) or M.find_mesh(d2, rel2, e, strict=False)
            _, _, nf, _, _, fs, (vo, fo, no) = m
            # 0x6e3adf: test byte [face+0xc], 0x40 -> the face is never drawn (and never counted by 0x6dfa60)
            res['skipflag'] += sum(1 for k in range(nf) if d2[fo + fs * k + 0xc] & 0x40)
    res['placeholder'] = any(f == 100 and v == 56 for f, v in res['meshes'])
    return res


def unit_of(map_name): return map_name[:-len('_map.drm')] if map_name.endswith('_map.drm') else map_name


def show(nm):
    h = header(nm)
    if h is None: print('%s: no file (the load request is never made, +0x88 stays 0)' % nm); return
    print('%s (%s, header %d B): floor mask 0x%02x (bytes +0x10: %s), %d portals, faces %d verts %d meshes %s%s' % (
        nm, h['src'], h['size0'], h['mask'] or 0, h['raw10'], len(h['portals']), h['faces'], h['verts'],
        h['meshes'], ' PLACEHOLDER' if h['placeholder'] else ''))
    for name, i4, i8, pos in h['portals']:
        hn = header(name + '_map.drm')
        tm = 'no map file' if hn is None else 'mask 0x%02x' % (hn['mask'] or 0)
        print('    portal -> %-32s ids %4d / %4d  at (%.0f, %.0f, %.0f)  [%s]' % (name, i4, i8, pos[0], pos[1], pos[2], tm))


def lowbit(m):
    for b in range(8):
        if m & (1 << b): return 1 << b
    return 0


def replay(start, cross_load=False, maxu=200):
    """the game's open path: floor = 0, load START recursively; callback: mask from header +0x10, floor = lowest bit
    (0x6ddb00, only while floor is 0 or the unit is off it - at open floor is 0); 0x6e2e60(u): stop when u's mask misses
    the floor, else every portal neighbour that is neither loaded nor loading and whose mask is unknown (0) or on the
    floor is requested with recursion. cross_load = the patched variant (both floor tests in 0x6e2e60 ignored).
    Returns (floor, loaded [names in load order], missing [names without a map file])."""
    floor = 0
    loaded, missing, queue, seen = [], [], [start], {start}
    while queue and len(loaded) < maxu:
        u = queue.pop(0)
        h = header(u + '_map.drm')
        if h is None: missing.append(u); continue          # 0x6e4f87: +0x88 = 0, no callback, no recursion
        loaded.append(u)
        m = h['mask'] or 0
        if floor == 0 or not (m & floor):
            if floor == 0: floor = lowbit(m)                # 0x6df697 -> 0x6ddb00 (only while floor is 0)
        if not cross_load and not (m & floor): continue     # 0x6e2e7a je
        for name, i4, i8, pos in h['portals']:
            if name in seen: continue                       # loaded / loading (+0x8c / +0xb1)
            seen.add(name); queue.append(name)              # mask still unknown (0) -> requested (0x6e2ecd)
    return floor, loaded, missing


def chain(start, maxu=200):
    print('=== start %s' % start)
    show(start + '_map.drm')
    floor, loaded, missing = replay(start, False, maxu)
    drawn = [u for u in loaded if (header(u + '_map.drm')['mask'] or 0) & floor]
    other = [u for u in loaded if u not in drawn]
    def faces(us): return sum(header(u + '_map.drm')['faces'] for u in us)
    print('game (FullMap only): floor bit 0x%02x; loaded %d units, drawn %d (%d faces): %s' % (
        floor, len(loaded), len(drawn), faces(drawn), ', '.join(drawn)))
    print('   loaded but other floor (placed by 0x6e2ef0(u, 0xff), skipped by the draw test 0x6e4295): %s (%d faces)' % (
        ', '.join('%s 0x%02x' % (u, header(u + '_map.drm')['mask'] or 0) for u in other) or '-', faces(other)))
    print('   no map file: %s' % (', '.join(missing) or '-'))
    print('AllFloors draw-only (draw test off, no extra load): drawn %d units, %d faces' % (len(loaded), faces(loaded)))
    f2, l2, m2 = replay(start, True, maxu)
    def nbytes(us): return sum(sum(len(s[1] or b'') for s in sections(u + '_map.drm')[2]) for u in us)
    print('   map data bytes: game %d, extra for draw-only 0' % nbytes(loaded))
    print('AllFloors with cross-floor loading (NOT built): loaded %d units (%d faces, %d map bytes)%s: %s' % (
        len(l2), faces(l2), nbytes(l2), ' (stopped at %d)' % maxu if len(l2) >= maxu else '', ', '.join(l2)))
    print('   extra loads against the game: %d (%s)' % (len(set(l2) - set(loaded)), ', '.join(sorted(set(l2) - set(loaded)))))
    print()


CAP = 0x16d83 + 1          # 0x6dfa69: cmp [0xee03e8], 0x16d83; jbe -> at most 93572 triangles per sonar frame


def cap(start, all_floors=False):
    """where the triangle cap falls with FullMap: the frame 0x6e4130 draws the units in list order (= creation order of
    0x6e2a60: the open's unit, then the portal neighbours as 0x6e2e60 meets them), mesh 0 then mesh 1, faces in file
    order, minus the faces with flag +0xc & 0x40; every triangle after the 93572nd is refused - also the markers / icons
    drawn after the units (0x6e1f30, 0x6e2170, symbols, 0x6e4050). Upper bound: assumes everything is inside the view
    distance (the distance / half-space culls in 0x6dfa60 come before the count)."""
    floor, loaded, missing = replay(start, False)
    total = 0
    print('=== cap %s (floor 0x%02x, %s)' % (start, floor, 'AllFloors 1' if all_floors else 'AllFloors 0'))
    for u in loaded:
        h = header(u + '_map.drm')
        m = h['mask'] or 0
        if not all_floors and not (m & floor):
            print('   %-24s m%02x  not drawn (other floor)' % (u, m)); continue
        n = h['faces'] - h['skipflag']
        before = total; total += n
        state = 'drawn' if total <= CAP else 'refused' if before >= CAP else 'cut: %d drawn, %d refused' % (CAP - before, total - CAP)
        print('   %-24s m%02x  %6d faces (%d flagged 0x40)  cumulative %6d  %s' % (u, m, n, h['skipflag'], total, state))
    print('   total %d, cap %d -> refused %d (%.0f %%) + every marker / icon drawn after the units' % (
        total, CAP, max(0, total - CAP), 100.0 * max(0, total - CAP) / total if total else 0))


def all_maps():
    for nm in M.base_map_names():
        h = header(nm)
        if h is None: print('%-40s missing' % nm); continue
        print('%-40s mask 0x%02x portals %2d faces %6d%s  -> %s' % (nm, h['mask'] or 0, len(h['portals']), h['faces'],
              ' PLACEHOLDER' if h['placeholder'] else '', ', '.join(p[0] for p in h['portals'])))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'hdr':
        for nm in a[1:]: show(nm)
    elif a[0] == 'chain': chain(a[1], int(a[2]) if len(a) > 2 else 200)
    elif a[0] == 'all': all_maps()
    elif a[0] == 'cap':                                 # cap START [all]
        cap(a[1], len(a) > 2 and a[2] == 'all')
    elif a[0] == 'pcfile':                              # installed PC copies (DLC): the bytes the PC game reads
        for p in a[1:]:
            secs = DW.read(open(p, 'rb').read(), 'le').sections
            _cache[os.path.basename(p)] = ('le', 'PC file', [(s.type, s.data, s.reloc) for s in secs])
            show(os.path.basename(p))
    else: raise SystemExit('unknown mode ' + a[0])
