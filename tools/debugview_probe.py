"""Read-only probe of a unit DRM for the debug render mode research (2026-11-06 debug render mode,
workspace docs\\Befund-Debug-Rendermodus-0611.md): Level / Terrain / TerrainGroup words with their relocation targets,
plus a generic word walker by section INDEX, so the collision mesh, its face flags and the hidden volumes can be
located from the data.

Known layouts it relies on (tools/unit_ids.level_info, tools/unit_frames.py): section 0 = Level, Level+0 -> Terrain
(24 bytes: +0x02 s16 portal count, +0x04 -> 0x100-byte StreamUnitPortals, +0x08 TerrainGroup count, +0x0c -> 0x50-byte
TerrainGroups, +0x10 -> one more TerrainGroup), Level+0x74 -> unit DTP (intros).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/debugview_probe.py level UNIT.drm [--words N]
      Level words +0..N (default 0x100), Terrain words, every TerrainGroup (0x50 B) with pointer targets
  ../bin/pyt -t 300 tools/debugview_probe.py walk UNIT.drm SECTION_INDEX OFFSET LENGTH
      words of section SECTION_INDEX (index, not id) from OFFSET (hex), LENGTH (hex) bytes, pointers marked
  ../bin/pyt -t 300 tools/debugview_probe.py list UNIT.drm
      section index, type, id, size, relocation counts
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    rel = []
    for s in D.sections:
        r = R.parse(s.reloc, 'le')
        rel.append((dict(r.internal), {so: (si, do) for si, so, do in r.external}))
    return D, rel


def target(D, rel, si, o):
    itn, ext = rel[si]
    if o in itn: return si, itn[o]
    if o in ext: return ext[o]
    return None


def fmtf(x):
    return ('%.3f' % x) if 1e-4 < abs(x) < 1e8 else ''


def words(D, rel, si, off, ln, indent='  '):
    d = D.sections[si].data
    for o in range(off, min(off + ln, len(d) - 3), 4):
        w = struct.unpack_from('<I', d, o)[0]; f = struct.unpack_from('<f', d, o)[0]
        t = target(D, rel, si, o)
        mark = ''
        if t is not None:
            ts = D.sections[t[0]]
            mark = '-> [%d] (type %d id %d, 0x%x B) +0x%x' % (t[0], ts.type, ts.id, len(ts.data), t[1])
        print('%s+%04x  %08x  %6d %6d  %12s  %s' % (indent, o - off, w, w & 0xffff, w >> 16, fmtf(f), mark))


def cmd_level(argv):
    n = 0x100
    if '--words' in argv: k = argv.index('--words'); n = int(argv[k + 1], 0); del argv[k:k + 2]
    D, rel = load(argv[0])
    print('== Level = section [0] type %d id %d size 0x%x' % (D.sections[0].type, D.sections[0].id,
                                                               len(D.sections[0].data)))
    words(D, rel, 0, 0, n)
    t = target(D, rel, 0, 0)
    if t is None: print('Level+0 has no target'); return 0
    ti, to = t
    print('== Terrain = [%d] +0x%x' % (ti, to))
    words(D, rel, ti, to, 0x18)
    td = D.sections[ti].data
    ntg = struct.unpack_from('<i', td, to + 8)[0]
    tg = target(D, rel, ti, to + 0xc)
    if tg is not None:
        for k in range(ntg):
            print('== TerrainGroup %d = [%d] +0x%x' % (k, tg[0], tg[1] + 0x50 * k))
            words(D, rel, tg[0], tg[1] + 0x50 * k, 0x50)
    t2 = target(D, rel, ti, to + 0x10)
    if t2 is not None:
        print('== Terrain+0x10 = [%d] +0x%x' % t2)
        words(D, rel, t2[0], t2[1], 0x50)
    return 0


def cmd_walk(argv):
    D, rel = load(argv[0])
    si = int(argv[1]); off = int(argv[2], 16); ln = int(argv[3], 16)
    s = D.sections[si]
    print('== [%d] type %d id %d size 0x%x, +0x%x .. +0x%x' % (si, s.type, s.id, len(s.data), off, off + ln))
    words(D, rel, si, off, ln)
    return 0


def cmd_list(argv):
    D, rel = load(argv[0])
    for si, s in enumerate(D.sections):
        m = s.data[0x10:0x14] if len(s.data) >= 0x14 else b''
        print('[%3d] type %2d id %6d size 0x%7x  int %5d ext %5d %s' % (si, s.type, s.id, len(s.data), len(rel[si][0]),
              len(rel[si][1]), 'Mesh' if m in (b'Mesh', b'hseM') else ''))
    return 0


def main(argv):
    if not argv: print(__doc__); return 1
    return {'level': cmd_level, 'walk': cmd_walk, 'list': cmd_list}[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
