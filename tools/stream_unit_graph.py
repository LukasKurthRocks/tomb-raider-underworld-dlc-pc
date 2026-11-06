"""Stream-unit portal graph of a level (read-only; 2026-11-06 unit streaming, docs/Befund-Unit-Streaming-0611.md).

Question behind it: can TruMenu stream in a unit that is NOT a direct portal neighbour of the loaded set (DLC 2:
dlc_level2_start -> dlc_yggdrasil_hall02) without a full level change? The engine (PC tru.exe, 2007 prototype names)
keeps loaded: the unit Lara is in (gameTracker+0xc0) + every unit its portals name whose unit-DTP portal record has
flag byte +0xb bit 0 set (STREAM_LevelLoadAdjacentUnits 0x5d2940); everything else is dumped on the next unit change
(STREAM_DumpAllUnitsNotNeeded 0x5d1a10). A newly streamed unit is placed only against the MAIN unit
(STREAM_ConnectStreamToStream 0x5d13e0: offset = [main portal +0x90] - [new portal +0x90]) unless its Level +0x2c has
bit 0x100000 ("connect to any loaded unit").

For every unit DRM of the given folders (later folders replace a unit of the same name; *_map.drm skipped) this prints
  * unit id (Level +0x4c), origin (Level +0x80), Level +0x2c and its 0x100000 bit,
  * every StreamUnitPortal (0x100 B: +0 name = destination unit, +0x80 u16 id of the matching portal in the destination,
    +0x82 u16 own id, +0x84 u16 destination unit id, +0x90 vec4 = the point the engine aligns), the auto-load flag of
    the matching unit-DTP portal record (+0x98 count / +0x9c -> 0x40-byte records, u16 id @+8, flag byte @+0xb),
    and whether the destination has a portal back with own id = +0x80 (needed for the hook-up),
and with --from A --to B the shortest portal chain A -> B (breadth first), per hop the engine relocation offset
(main portal +0x90 - new portal +0x90) and the loaded set after each move (unit + auto-load neighbours, slot count of
the 32-entry table 0xdbab40, overlay units not counted).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/stream_unit_graph.py DIR [DIR ...] [--prefix dlc_,dlc2_] [--from UNIT --to UNIT] [--quiet]
      --prefix: only unit files whose name starts with one of the prefixes (comma list); --quiet: no per-unit table
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, unit_ids as U


def load_unit(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, 'le')
    if L is None or secs[0]['data'] is None or len(secs[0]['data']) < 0x90: return None
    d0 = secs[0]['data']
    uid = struct.unpack_from('<I', d0, 0x4c)[0]
    flags2c = struct.unpack_from('<I', d0, 0x2c)[0]
    origin = struct.unpack_from('<3f', d0, 0x80)
    dflag = {}
    for si, o in L['dportals']:
        d = secs[si]['data']
        dflag[struct.unpack_from('<H', d, o + 8)[0]] = d[o + 0xb]
    ports = []
    for si, o in L['portals']:
        d = secs[si]['data']
        name = d[o:o + 128].split(b'\0', 1)[0].decode('latin-1')
        to_id, own, dest = struct.unpack_from('<3h', d, o + 0x80)
        v90 = struct.unpack_from('<4f', d, o + 0x90)
        ports.append(dict(name=name, tgt=name.split('\\')[-1].lower(), to=to_id, own=own, dest=dest, v90=v90,
                          flag=dflag.get(own & 0xffff)))
    return dict(id=uid, flags2c=flags2c, origin=origin, portals=ports)


def unit_files(dirs, prefixes):
    files = {}
    for dd in dirs:
        for n in sorted(os.listdir(dd)):
            ln = n.lower()
            if not ln.endswith('.drm') or ln.endswith('_map.drm'): continue
            if prefixes and not any(ln.startswith(p) for p in prefixes): continue
            files[ln[:-4]] = os.path.join(dd, n)
    return files


def adjacent(units, n):
    """the units the engine requests when n becomes the main unit (flag byte +0xb bit 0, names de-duplicated, the
    vehicle-section names comp_entry1 / comp_exit1 skipped like 0x5d2a15..0x5d2a37)."""
    out = []
    for q in units[n]['portals']:
        if q['flag'] is None or not (q['flag'] & 1): continue
        if q['tgt'] in ('comp_entry1', 'comp_exit1') or q['tgt'] in out: continue
        out.append(q['tgt'])
    return out


def main(argv):
    if not argv: sys.exit(__doc__)
    prefixes, a, b, quiet, dirs = [], None, None, False, []
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == '--prefix': prefixes = [p.lower() for p in argv[i + 1].split(',') if p]; i += 2; continue
        if x == '--from': a = argv[i + 1].lower(); i += 2; continue
        if x == '--to': b = argv[i + 1].lower(); i += 2; continue
        if x == '--quiet': quiet = True; i += 1; continue
        dirs.append(x); i += 1
    units = {}
    for n, p in sorted(unit_files(dirs, prefixes).items()):
        try:
            u = load_unit(p)
        except Exception as ex:
            print('%s: not read (%s)' % (n, ex)); continue
        if u is not None: units[n] = u
    byid = {u['id']: n for n, u in units.items()}
    print('%d unit DRMs read' % len(units))
    if not quiet:
        for n, u in sorted(units.items()):
            print('== %s  id %d  origin (%.1f %.1f %.1f)  Level+0x2c 0x%08x%s  %d portal(s), auto-load set %d' % (
                n, u['id'], *u['origin'], u['flags2c'], ' CONNECT-ANY' if u['flags2c'] & 0x100000 else '',
                len(u['portals']), len(adjacent(units, n))))
            for q in u['portals']:
                back = ''
                if q['tgt'] in units:
                    m = [r for r in units[q['tgt']]['portals'] if r['own'] == q['to']]
                    back = ('back ok (-> %s)' % m[0]['tgt']) if m else 'NO BACK PORTAL'
                    if units[q['tgt']]['id'] != q['dest']: back += ', dest id %d != unit id %d' % (q['dest'], units[q['tgt']]['id'])
                else:
                    back = 'destination not in the folders'
                print('   -> %-30s own %4d to %4d dest %4d  flag %s  +0x90 (%.1f %.1f %.1f)  %s' % (
                    q['tgt'], q['own'], q['to'], q['dest'], '-' if q['flag'] is None else '0x%02x' % q['flag'],
                    q['v90'][0], q['v90'][1], q['v90'][2], back))
    if a and b:
        if a not in units or b not in units:
            print('--from / --to: unit not found (%s / %s)' % (a in units, b in units)); return 1
        prev = {a: None}
        dq = collections.deque([a])
        while dq:
            n = dq.popleft()
            for t in adjacent(units, n):
                if t in units and t not in prev:
                    prev[t] = n; dq.append(t)
        if b not in prev:
            print('no auto-load portal chain %s -> %s' % (a, b)); return 0
        path = [b]
        while prev[path[-1]] is not None: path.append(prev[path[-1]])
        path.reverse()
        direct = b in adjacent(units, a)
        print('\nchain %s -> %s: %d hop(s): %s%s' % (a, b, len(path) - 1, ' -> '.join(path),
                                                      '  (DIRECT neighbour)' if direct else ''))
        for k, n in enumerate(path):
            loaded = [n] + [t for t in adjacent(units, n)]
            print('  step %d main %-28s loaded set %2d slot(s): %s' % (k, n, len(loaded), ', '.join(loaded)))
            if k + 1 < len(path):
                nx = path[k + 1]
                q = [r for r in units[n]['portals'] if r['tgt'] == nx][0]
                m = [r for r in units[nx]['portals'] if r['own'] == q['to']]
                if m:
                    off = [q['v90'][i] - m[0]['v90'][i] for i in range(3)]
                    print('         hop %s -> %s via portal own %d / %d: relocation of %s = (%.1f %.1f %.1f)' % (
                        n, nx, q['own'], m[0]['own'], nx, *off))
                else:
                    print('         hop %s -> %s: no matching back portal (engine prints "Can\'t find signal")' % (n, nx))
        if not direct:
            print('\n%s is NOT a direct neighbour of %s: no portal record of %s names it, so a stream request from %s '
                  'has no portal pair to place it (ConnectStreamToStream relocates only against the main unit).' % (
                      b, a, a, a))
            back = [r['tgt'] for r in units[b]['portals']]
            print('%s portals: %s' % (b, ', '.join(back)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
