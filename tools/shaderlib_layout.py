"""Raw layout of ShaderLib sections (type 9) of a DRM, read-only: header words, slot offsets, and per entry the
offset, the two header words, the hash, the size field, where the D3D9 END token is, and the gap to the next entry.
Finding 43, test 46: tools/shaderlib.build() did not reproduce PC sections byte for byte - which field differs.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/shaderlib_layout.py FILE.drm be|le ID[,ID]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    path, en, ids = argv[0], argv[1], {int(x) for x in argv[2].split(',')}
    e = '>' if en == 'be' else '<'
    D = DW.read(open(path, 'rb').read(), en)
    for s in D.sections:
        if s.type != 9 or s.id not in ids: continue
        d = s.data
        kind = d[0]; tb, ds = struct.unpack_from(e + 'II', d, 4)
        slots = list(struct.unpack_from(e + '%dI' % (tb // 4), d, 12))
        print('lib %d: %d bytes, kind %d, tableBytes %d, dataSize %d (= len - %d), reloc %d bytes, flags %d ver %d spec %#x pad %d'
              % (s.id, len(d), kind, tb, ds, len(d) - ds, len(s.reloc), s.flags, s.ver, s.spec, s.pad))
        offs = sorted(set(x for x in slots if x != 0xffffffff))
        print('  slots -> offsets: %s' % ' '.join('%d:%x' % (k, x) for k, x in enumerate(slots) if x != 0xffffffff))
        for k, o in enumerate(offs):
            a, size = struct.unpack_from(e + 'II', d, 4 + o); h = d[4 + o + 8:4 + o + 16]
            nxt = offs[k + 1] if k + 1 < len(offs) else len(d) - 4
            code = d[4 + o + 16:4 + nxt]
            end = None
            if en == 'le':
                w = struct.unpack_from('<%dI' % (len(code) // 4), code, 0)
                i = 1
                while i < len(w):
                    t = w[i]
                    if t == 0x0000FFFF: end = 4 * i; break
                    if t & 0xFFFF == 0xFFFE: i += 1 + (t >> 16); continue
                    i += 1 + ((t >> 24) & 0xF)
            print('  entry @%x: word0 %#x size %d hash %s; bytes to next entry %d; END token at +%s of the code (code len %s)'
                  % (o, a, size, h.hex(), nxt - o, end, None if end is None else end + 4))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
