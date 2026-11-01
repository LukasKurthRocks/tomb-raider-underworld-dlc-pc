"""Re-convert the object markup records of a converted PC DRM from the Xbox original with the proven field layout
(writes only OUT; DLC 2 rock vein, 2026-11-01).

Layout of a 0x5c-byte markup record (PC tru+0x5ce4f0 / +0x5ce569; proven on the base pair
ar_uo_valgrind_column_floor{a,b}_ringa: every Xbox record matches the PC record with this rule):
  +0x00 .. +0x28  dwords / floats (u32 swap), +0x28 runtime flags (0 in the file)
  +0x2c u16, +0x2e u16 markup id (read as a word)
  +0x30 u16, +0x32 byte (1 = skipped by the query tru+0x5ce44a), +0x33 type char (bytes kept)
  +0x34 .. +0x54  floats (u32 swap), +0x58 relocated pointer to the poly line (left as it is)
An object's markup array: count = DTP +0x54, records = DTP +0x58 (tru+0x5d0656), same DTP id on both platforms.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/markup_fix.py PC.drm XBOX.drm OUT.drm
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

STRIDE = 0x5c


def conv(xw, w):
    if w == 0x2c: return xw[0:2][::-1] + xw[2:4][::-1]
    if w == 0x30: return xw[0:2][::-1] + xw[2:4]
    return xw[::-1]


def main(argv):
    src = open(argv[0], 'rb').read()
    P = DW.read(src, 'le')
    X = DW.read(open(argv[1], 'rb').read(), 'be')
    total = 0
    for si, s in enumerate(P.sections):
        d = bytearray(s.data)
        if s.type != 7 or len(d) < 0x5c: continue
        r = R.parse(bytes(s.reloc), 'le')
        relocated = set(o for o, _ in r.internal) | set(o for _, o, _ in r.external)
        intern = dict(r.internal)
        n = struct.unpack_from('<I', d, 0x54)[0]
        ro = intern.get(0x58)
        if ro is None or not 1 <= n <= 1000 or ro + n * STRIDE > len(d): continue
        if not all(struct.unpack_from('<I', d, ro + k * STRIDE + 0x28)[0] == 0 for k in range(n)): continue
        xs = [x for x in X.sections if x.type == 7 and x.id == s.id]
        if len(xs) != 1 or len(xs[0].data) != len(d):
            print('dtp %d: no unique Xbox section of the same size - skipped' % s.id); continue
        xd = bytes(xs[0].data)
        if struct.unpack_from('>I', xd, 0x54)[0] != n:
            print('dtp %d: Xbox count differs - skipped' % s.id); continue
        changed = []
        for k in range(n):
            o = ro + k * STRIDE
            for w in range(0, 0x58, 4):
                if o + w in relocated: continue
                new = conv(xd[o + w:o + w + 4], w)
                if bytes(d[o + w:o + w + 4]) != new:
                    changed.append((k, w, bytes(d[o + w:o + w + 4]).hex(), new.hex()))
                    d[o + w:o + w + 4] = new
        if changed:
            s.data = bytes(d)
            total += len(changed)
            print('dtp %d: %d markup records, %d words re-converted' % (s.id, n, len(changed)))
            for k, w, a, b in changed:
                print('   record %d +0x%02x: %s -> %s' % (k, w, a, b))
        else:
            print('dtp %d: %d markup records, all words already right' % (s.id, n))
    raw = P.write('le')
    out = DW.cdrm_encode(raw, 'le') if src[:4] == b'CDRM' else raw   # same container as the input
    if DW.read(out, 'le').write('le') != raw: raise SystemExit('readback differs')
    os.makedirs(os.path.dirname(os.path.abspath(argv[2])), exist_ok=True)
    open(argv[2], 'wb').write(out)
    print('%d words changed -> %s (%d bytes%s, readback ok)' % (total, argv[2], len(out),
                                                                ', CDRM' if src[:4] == b'CDRM' else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
