"""Dump the raw dwords of the companion hit records (extension data type 0x3d, +0x28 / +0x2c) of a thrall extension
DRM, as the PC code reads them when TruShadowCombat 0.6.7 redirects the hit structure s to record+0xc. Read-only;
K-1b 2026-11-09 (light / heavy and knockback inputs).

Per record: type, then s = record+0xc with the fields the PC reads:
  s+0x00..+0x0c  default reaction animation refs (tru+0x245a00), s+0x10 / +0x14 flags, s+0x18 entry count
  (tru+0x24f363), s+0x20 / +0x24 (knockback tru+0x2206f7 / +0x22070d), s+0x30 f32 (knockback speed fallback
  tru+0x22072e), s+0x34 = record+0x40 (TU-inserted f32, knockback force), s+0x3c.. first entry (PC layout).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/thrall_hit_record_dump.py DRM be|le [TYPE]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import thrall_extension_fix as X


def main(a):
    if len(a) not in (2, 3):
        print(__doc__)
        return 2
    want = int(a[2]) if len(a) == 3 else None
    raw = open(a[0], 'rb').read()
    D = DW.read(raw, a[1])
    E = '>' if a[1] == 'be' else '<'
    found = 0
    for S in X.secs_of(D, a[1]):
        if S is None:
            continue
        b = X.ext_root(S)
        if b is None:
            continue
        p, n = S.it.get(b + 0x28), S.u32(b + 0x2c)
        if p is None:
            continue
        cnt = n if n <= 0xffff else (n >> 16)
        for k in range(cnt):
            r = p + k * X.REC
            if r + X.REC > len(S.data):
                break
            typ = S.u32(r)
            if want is not None and typ != want:
                continue
            found += 1
            s = r + X.BSTRUCT_AT
            print('record %2d type %2d (section %d +0x%x, s = +0x%x)' % (k, typ, S.id, r, s))
            for off in range(0, X.REC - X.BSTRUCT_AT, 0x10):
                words = []
                for o in range(off, min(off + 0x10, X.REC - X.BSTRUCT_AT), 4):
                    u = struct.unpack_from(E + 'I', S.data, s + o)[0]
                    f = struct.unpack_from(E + 'f', S.data, s + o)[0]
                    ref = '*' if S.it.get(s + o) is not None else ' '
                    ft = ('%g' % f) if (u and 1e-6 < abs(f) < 1e7) else '-'
                    words.append('%08x%s(%s)' % (u, ref, ft))
                print('  s+0x%02x  %s' % (off, '  '.join(words)))
    if not found:
        print('no hit records found')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
