"""Water volumes and sea creatures per unit (read-only; 2026-11-06 thalassophobia - feasibility of an accessibility
option against fear of deep water, docs Befund-Thalassophobie-0611.md).

For every unit: each `watervolume` intro (object 7; intro layout as tools/arachno_spider_intros.py: +0x10 position,
+0x50 u16 object id, +0x58 intro id, +0x78 data pointer) with its position and the type-11 data block fields that
look like the box: data +0x54 / +0x58 / +0x5c (three floats, extents in game units, 100 = 1 m - meaning INFERRED,
`Befund-Debug-Rendermodus-0611.md` calls them extents too), data +0x48 (640.0 in every volume seen) and the u16 at
data +0x4c; plus a count of the sea-creature intros (shark / jellyfish / fish / kraken / diver objects) of the unit.
Units are read from the PC archives (patch first, then bigfile) or from DRM files; nothing is written.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/thalasso_water_volumes.py --src pc UNIT [UNIT ...]
  ../bin/pyt -t 900 tools/thalasso_water_volumes.py PATH.drm [PATH.drm ...]
Prints one line per water volume and one summary line per unit (volumes, largest extent, creatures).
Exit code 0 = read, 2 = usage error.
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
import drm_write as DW, drm_reloc as R, unit_ids as U
import arachno_spider_intros as A

CREATURES = r'shark|jellyfish|fish_medsea|kraken_body|kraken_tentacle|kraken_floor|kraken_death|co_diver'


def report(label, data, names, rows):
    D = DW.read(data, 'le')
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, 'le')
    if L is None:
        print('== %s: not a unit DRM' % label); return
    vols = []; crea = collections.Counter()
    for si, o in L['intros']:
        d = secs[si]['data']
        oid = struct.unpack_from('<H', d, o + 0x50)[0]
        name = names.get(oid, '?')
        if re.search(CREATURES, name): crea[name] += 1
        if name != 'watervolume': continue
        uid = struct.unpack_from('<I', d, o + 0x58)[0]
        pos = struct.unpack_from('<3f', d, o + 0x10)
        t = dict(R.parse(secs[si]['reloc'], 'le').internal).get(o + 0x78)
        if t is None or t + 0x60 > len(d):
            vols.append((uid, pos, None)); continue
        typ = struct.unpack_from('<I', d, t)[0]
        ext = struct.unpack_from('<3f', d, t + 0x54)
        f48 = struct.unpack_from('<f', d, t + 0x48)[0]
        u4c = struct.unpack_from('<H', d, t + 0x4e)[0]
        vols.append((uid, pos, (typ, ext, f48, u4c)))
    print('== %s: %d water volumes, creatures: %s' % (
        label, len(vols), ', '.join('%s %d' % kv for kv in sorted(crea.items())) or 'none'))
    big = 0.0
    for uid, pos, info in vols:
        if info is None:
            print('   intro %6d pos (%8.0f %8.0f %8.0f) no data block' % ((uid,) + pos)); continue
        typ, ext, f48, u4c = info
        big = max(big, max(ext))
        print('   intro %6d pos (%8.0f %8.0f %8.0f) type %d extents %8.0f x %8.0f x %8.0f  +48 %.0f  +4e %d' % (
            (uid,) + pos + (typ,) + ext + (f48, u4c)))
    rows.append((label, len(vols), big, dict(crea)))


def main(argv):
    argv = list(argv)
    src = None
    if '--src' in argv:
        i = argv.index('--src'); src = argv[i + 1]; del argv[i:i + 2]
    if not argv: print(__doc__); return 2
    names = A.objnames()
    rows = []
    if src:
        order = ['pcpatch', 'pcbig'] if src == 'pc' else [src]
        archives = []
        for s in order:
            path, e, pre = LC.SRC[s]
            if e != 'le': print('only little-endian (PC) sources'); return 2
            if os.path.exists(path): archives.append((s, Archive(path, e), pre))
        for unit in argv:
            s, data = A.unit_bytes(archives, unit.lower())
            if data is None: print('== %s: not found' % unit); continue
            report(unit, data, names, rows)
    else:
        for path in argv:
            if not os.path.isfile(path): print('== %s: no such file' % path); continue
            report(os.path.basename(path)[:-4], open(path, 'rb').read(), names, rows)
    print('\nsummary: unit | water volumes | largest extent (units) | sea creatures')
    for label, n, big, crea in rows:
        if n or crea:
            print('%-32s %3d %9.0f  %s' % (label, n, big, ', '.join('%s %d' % kv for kv in sorted(crea.items()))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
