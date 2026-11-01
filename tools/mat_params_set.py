"""Set one MaterialParams vec4 (pixel-shader block, count +0x58, pointer +0x5C) of a material (type 10) in a PC DRM and
write a new DRM; prints old / new values and re-reads the output (all other sections byte-identical).
Test 48h (2026-11-01): diagnostic build - the doppelganger hair material 25521 draws PC surrogate lib 2, whose
`mad r0.xyz, tex(s2), c101, r0` adds MaterialParams[1] = (0, 1, 1) (copied from the TU material, where it is not a
colour) as flat cyan; MP[1].rgb = 0 must remove the cyan and nothing else.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mat_params_set.py IN.drm OUT.drm MATERIAL_ID INDEX X Y Z W
  a value '=' keeps that lane
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    src, out, mid, idx = argv[0], argv[1], int(argv[2]), int(argv[3])
    vals = argv[4:8]
    if len(vals) != 4: sys.exit(__doc__)
    raw = open(src, 'rb').read()
    D = DW.read(raw, 'le')
    hit = [s for s in D.sections if s.type == 10 and s.id == mid]
    if len(hit) != 1: sys.exit('material %d found %d times' % (mid, len(hit)))
    s = hit[0]
    o = dict(R.parse(s.reloc, 'le').internal).get(0x5C); n = struct.unpack_from('<I', s.data, 0x58)[0]
    if o is None or idx >= n: sys.exit('no params block / index %d >= count %d' % (idx, n))
    old = struct.unpack_from('<4f', s.data, o + 16 * idx)
    new = tuple(old[k] if vals[k] == '=' else float(vals[k]) for k in range(4))
    d = bytearray(s.data); struct.pack_into('<4f', d, o + 16 * idx, *new); s.data = bytes(d)
    print('material %d MP[%d] at +%#x: %s -> %s' % (mid, idx, o + 16 * idx, old, new))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    data = D.write('le')
    if raw[:4] == b'CDRM': data = DW.cdrm_encode(data, 'le')      # keep the container of the input
    open(out, 'wb').write(data)
    # readback: same section list, only this material differs
    A, B = DW.read(raw, 'le'), DW.read(open(out, 'rb').read(), 'le')
    assert len(A.sections) == len(B.sections)
    diff = [(x.type, x.id) for x, y in zip(A.sections, B.sections)
            if (x.type, x.id) != (y.type, y.id) or x.data != y.data or x.reloc != y.reloc]
    print('readback ok: %d sections, differing: %s' % (len(B.sections), diff))
    print('%s  %d bytes  md5 %s' % (out, len(data), hashlib.md5(data).hexdigest()))


if __name__ == '__main__':
    if len(sys.argv) < 9: sys.exit(__doc__)
    main(sys.argv[1:])
