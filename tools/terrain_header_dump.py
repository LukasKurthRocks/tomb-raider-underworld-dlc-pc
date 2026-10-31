"""Dump the header words of a terrain section (type 12 without 'Mesh') and the layout of its regions, read-only:
H, the known header fields (tools/terrain_convert.py) and the unknown words after them, plus the byte ranges of
each region sorted by offset with the gaps between them - to find structures the converter does not name.
Finding 43, test 44b: the DLC 2 waterfall column follows the pool's material although no pool triangle is vertical.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/terrain_header_dump.py PC.drm SECTION_ID [--words N] [--be]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, terrain_convert as TC


def main(argv):
    n = 40; e = '>' if '--be' in argv else '<'; argv = [a for a in argv if a != '--be']
    if '--words' in argv: k = argv.index('--words'); n = int(argv[k + 1]); del argv[k:k + 2]
    D = DW.read(open(argv[0], 'rb').read(), 'le' if e == '<' else 'be')
    s = next(x for x in D.sections if x.type == 12 and x.id == int(argv[1])); d = s.data
    T = TC.parse(d, e); H = T['H']
    u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    print('section size %d, H = %#x; words before H: %s' % (len(d), H, ' '.join('%08x' % u(o) for o in range(0, min(H, 0x40), 4))))
    for k in range(n):
        o = H + 4 * k
        if o + 4 > len(d): break
        v = u(o); f = struct.unpack_from(e + 'f', d, o)[0]
        print('  H+%#04x  %08x  %12d  %s' % (4 * k, v, v, ('%.3f' % f) if 1e-4 < abs(f) < 1e7 else ''))
    r = R.parse(s.reloc, 'le' if e == '<' else 'be'); ml = dict(r.internal).get(0x0C)
    mats = struct.unpack_from(e + '%dI' % u(ml), d, ml + 4) if ml is not None else ()
    print('material list (+0x0C -> %s): %s' % (hex(ml) if ml is not None else '-', ' '.join('%d:%d' % x for x in enumerate(mats))))
    print('Y records: idx material vb hash u16 u8 u8 i32 x4')
    for k, y in enumerate(T['Y']):
        print('  Y %3d  m%-3d %-6s vb %d  %08x  %5d %3d %3d  %s' % (k, y[0], mats[y[0]] if y[0] < len(mats) else '?',
              y[1], y[2], y[3], y[4], y[5], ' '.join('%d' % v for v in y[6:])))
    regions = [('A', T['offA'], 32 * T['nA']), ('Y', T['offY'], 32 * T['nY']), ('VF', T['offVF'], T['sizeVF']),
               ('VB table', T['offVB'], 16 * T['nVB']), ('Z', T['offZ'], None), ('Idx', T['offIdx'], 2 * T['nIdx'])]
    for k, (vo, _z, nv, vfi) in enumerate(T['vbs']):
        regions.append(('VB %d data' % k, vo, nv * T['vfs'][vfi]['stride']))
    regions.sort(key=lambda x: x[1])
    print('regions (H-relative):')
    for i, (name, off, size) in enumerate(regions):
        end = off + size if size is not None else (regions[i + 1][1] if i + 1 < len(regions) else len(d) - H)
        nxt = regions[i + 1][1] if i + 1 < len(regions) else len(d) - H
        print('  %-12s %#9x .. %#9x  (%d bytes)%s' % (name, off, end, end - off,
                                                   '  gap %d bytes to next' % (nxt - end) if nxt > end else ''))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
