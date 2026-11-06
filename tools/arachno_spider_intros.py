"""Spider intros per unit (read-only; 2026-11-06 arachnophobia - feasibility of a mode that shows spiders as a flat
picture, docs Befund-Arachnophobie-0611.md).

For every given unit it lists the intros (placed instances, unit DTP Level+0x74 -> 0x90-byte Intro records, layout in
tools/unit_ids.py: +0x10 position, +0x40 scale, +0x50 u16 object id, +0x58 unique id = the intro id TruMenu's
`player.goto` takes, +0x78 data pointer) whose object name matches REGEX (default spider|tarantula), with the object
name taken from the PC object list (work/generic/merged/tr8/pc-w/objectlist.txt = PC base ids + DLC ids appended, the
numbering of pcbig / pcpatch units and of our converted DLC units). For intros that carry a data block (+0x78, e.g.
the generators) the first --words dwords of that block are printed raw (hex and as float) - their meaning is NOT known.
Units are read either from a game archive (patch first, then bigfile: --src pc = pcpatch then pcbig, any other
tools/locals.py source alone) without writing anything, or from DRM files given as paths.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/arachno_spider_intros.py --src pc UNIT [UNIT ...] [--grep REGEX] [--words N]
  ../bin/pyt -t 600 tools/arachno_spider_intros.py PATH.drm [PATH.drm ...] [--grep REGEX] [--words N]
  e.g. ../bin/pyt -t 600 tools/arachno_spider_intros.py --src pc l2_norsehub l4_traprooms
  ../bin/pyt -t 300 tools/arachno_spider_intros.py groups OBJECT.drm [...]   (mesh groups + their draw-group word)
Prints per unit: source, total intro count, matching intros (unique id, object id, name, position, scale, data words)
and a per-object count; at the end a summary table over all units. Exit code 0 = read, 2 = usage error.
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode
import drm_write as DW, drm_reloc as R, unit_ids as U

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OBJLIST = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def objnames(path=OBJLIST):
    d = {}
    for line in open(path, encoding='utf8', errors='ignore'):
        p = line.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


def unit_bytes(archives, unit):
    """(source name, decoded DRM bytes) of the first archive that has pc-w\\<unit>.drm, else (None, None)."""
    for src, A, pre in archives:
        recs = A.find(crc(pre + '\\' + unit + '.drm'))
        if recs: return src, cdrm_decode(A.read(recs[-1]), 'le')
    return None, None


def report(label, data, names, rx, nwords, total):
    D = DW.read(data, 'le')
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, 'le')
    if L is None:
        print('== %s: not a unit DRM' % label); return
    cnt = collections.Counter()
    print('== %s: %d intros' % (label, len(L['intros'])))
    for si, o in L['intros']:
        d = secs[si]['data']
        oid = struct.unpack_from('<H', d, o + 0x50)[0]
        name = names.get(oid, '?')
        if not re.search(rx, name, re.I): continue
        cnt[name] += 1
        uid = struct.unpack_from('<I', d, o + 0x58)[0]
        pos = struct.unpack_from('<3f', d, o + 0x10)
        scale = struct.unpack_from('<3f', d, o + 0x40)
        ri = dict(R.parse(secs[si]['reloc'], 'le').internal)
        extra = ''
        t = ri.get(o + 0x78)
        if t is not None and nwords:
            n = max(0, min(nwords, (len(d) - t) // 4))
            w = struct.unpack_from('<%dI' % n, d, t)
            f = struct.unpack_from('<%df' % n, d, t)
            extra = ' data@0x%x: %s' % (t, ' '.join('%08x(%s)' % (a, ('%.3g' % b) if 1e-4 < abs(b) < 1e7 else '-')
                                                  for a, b in zip(w, f)))
        print('   intro %6d obj %4d %-32s pos (%9.1f %9.1f %9.1f) scale (%.2f %.2f %.2f)%s' % (
            uid, oid, name, pos[0], pos[1], pos[2], scale[0], scale[1], scale[2], extra))
    print('   matching: %s' % (', '.join('%s %d' % kv for kv in sorted(cnt.items())) or 'none'))
    total[label] = cnt


def mesh_groups(paths):
    """groups mode: per Mesh section (type 12) the draw-group word of every group (tools/mesh_tr8.py layout,
    'drawGroup?' = group +0x24) - which bits of the instance's noDrawGroups mask (+0x23c) could hide which part."""
    import mesh_tr8 as MT
    for path in paths:
        D = DW.read(open(path, 'rb').read(), 'le')
        for i, s in enumerate(D.sections):
            if s.type != 12 or s.data[0x10:0x14] not in (b'hseM', b'Mesh'): continue
            M = MT.Mesh(s.data, 'le')
            print('%s mesh sec %d id %d: groups %d, meshes %d, bones %d, materials %s' % (
                os.path.basename(path), i, s.id, M.numGroups, M.numMeshes, M.numBones, M.materials))
            for k, g in enumerate(M.groups):
                print('   group %2d drawGroup %d material index %d tris %d verts %d' % (
                    k, g['drawGroup'], g['material'], g['numTris'], g['numVerts']))
    return 0


def main(argv):
    argv = list(argv)
    if argv[:1] == ['groups']: return mesh_groups(argv[1:])
    rx = opt(argv, '--grep', r'spider|tarantula')
    nwords = int(opt(argv, '--words', '8'))
    src = opt(argv, '--src', None)
    if not argv: print(__doc__); return 2
    names = objnames()
    total = collections.OrderedDict()
    if src:
        order = ['pcpatch', 'pcbig'] if src == 'pc' else [src]
        archives = []
        for s in order:
            path, e, pre = LC.SRC[s]
            if e != 'le': print('only little-endian (PC) sources: %s is %s' % (s, e)); return 2
            if os.path.exists(path): archives.append((s, Archive(path, e), pre))
        for unit in argv:
            s, data = unit_bytes(archives, unit.lower())
            if data is None: print('== %s: not in %s' % (unit, '/'.join(order))); continue
            report('%s [%s]' % (unit, s), data, names, rx, nwords, total)
    else:
        for path in argv:
            if not os.path.isfile(path): print('== %s: no such file' % path); continue
            report(os.path.basename(path), open(path, 'rb').read(), names, rx, nwords, total)
    objs = sorted({k for c in total.values() for k in c})
    print('\nsummary (intros per unit, regex %r):' % rx)
    print('%-40s %s' % ('unit', ' | '.join(objs)))
    for label, c in total.items():
        print('%-40s %s' % (label, ' | '.join('%d' % c.get(k, 0) for k in objs)))
    print('%-40s %s' % ('total', ' | '.join('%d' % sum(c.get(k, 0) for c in total.values()) for k in objs)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
