"""List the hit reaction structs of a thrall: the enemy hit switch data D (damage types 0..16 through the selector
table PC 0x6159a0 / retail 0x823042a8) and the TU extension hit records (type 0x3d data, +0x28 / +0x2c, looked up by
damage type in TU 0x82301dc0 when the enemy has a companion). Read-only; K-1 2026-11-09 ("thrall falls at every
hit on PC").

Per struct: flags word +0x14 with the bits the PC reads (0x10000000 tested in 0x623410, 0x20000000 with amount < 1.0,
0x40000000 = selector return value), bytes +0x1c / +0x1d / +0x1e (subtype 2 / 1 / 3 reaction index), and for records
the inserted f32 +0x40.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/thrall_hit_records.py DRM be|le
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import thrall_extension_fix as X

# selector table: damage type -> offset in D (PC 0x6159a0 jump table / retail 0x823042f0); None = no struct
TYPE_OFF = {0: 0x50, 1: 0x104, 2: 0x1b8, 4: 0x6a4, 6: 0x26c, 8: 0x1b8, 10: 0x3d4, 11: 0x488, 13: 0x320, 14: 0x5f0,
            16: 0x1b8}


def show(E, data, at, label):
    fl = struct.unpack_from(E + 'I', data, at + 0x14)[0]
    b1c, b1d, b1e = data[at + 0x1c], data[at + 0x1d], data[at + 0x1e]
    bits = ' '.join(n for m, n in ((0x10000000, 'B28'), (0x20000000, 'B29'), (0x40000000, 'B30')) if fl & m) or '-'
    print('  %-28s flags +14 %08x [%s]  +1c/1d/1e %d/%d/%d' % (label, fl, bits, b1c, b1d, b1e))


def main(a):
    if len(a) != 2:
        print(__doc__)
        return 2
    raw = open(a[0], 'rb').read()
    D = DW.read(raw, a[1])
    E = '>' if a[1] == 'be' else '<'
    found = 0
    for S in X.secs_of(D, a[1]):
        if S is None:
            continue
        d = X.enemy_d(S)
        if d is not None:
            found += 1
            print('enemy hit switch data D at section %d +0x%x' % (S.id, d))
            for t, off in sorted(TYPE_OFF.items()):
                show(E, S.data, d + off, 'type %2d -> D+0x%03x' % (t, off))
            show(E, S.data, d + 0x53c, 'msg+0x6e set -> D+0x53c')
            show(E, S.data, d + 0x758, 'override -> D+0x758')
        b = X.ext_root(S)
        if b is not None:
            found += 1
            p, n = S.it.get(b + 0x28), S.u32(b + 0x2c)
            print('extension data at section %d +0x%x: hit records %s, count %d (raw word %08x)' % (
                S.id, b, 'none' if p is None else '+0x%x' % p, n & 0xffff if n > 0xffff else n, n))
            if p is not None:
                cnt = n if n <= 0xffff else (n >> 16)
                for k in range(cnt):
                    r = p + k * X.REC
                    if r + X.REC > len(S.data):
                        break
                    typ = S.u32(r)
                    f40 = struct.unpack_from(E + 'f', S.data, r + 0x40)[0]
                    show(E, S.data, r + X.BSTRUCT_AT, 'record %2d type %2d (+40 %g)' % (k, typ, f40))
    if not found:
        print('no enemy data / extension data found')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
