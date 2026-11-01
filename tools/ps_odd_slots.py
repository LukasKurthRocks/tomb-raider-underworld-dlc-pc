"""Pixel-shader libraries with empty odd permutation slots, and the materials that draw with them (read-only unless
--out). Test 48e (2026-10-31): tru.exe +0x106a7a..+0x106b00 picks the pass pixel shader as slot (b0 | lightbits):
b0 = 1 when the drawn instance fades (alpha < 1.0 at [+0x10], object flag [+0x40] bit 0, < 4 at [+0x38]), the light
bits from [ctx+0x11484]; +0x1260e0 then takes `base + 4 + slot[i]` WITHOUT checking for 0xFFFFFFFF, so an empty slot
gives "entry" = base + 3 and IDirect3DDevice9::CreatePixelShader gets garbage (D3DERR_INVALIDCALL -> status -4 ->
the display-driver box). Lib 801 (doppelganger material 26354, pass 2) has slots 0 / 2 / 4 / 6 only; its Xbox
original 2632 has slot 1 (the fade variant).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ps_odd_slots.py PC.drm [XBOX.drm] [--out OUT.drm --libs ID,ID]
  lists every kind-1 library with an even table whose odd slots are empty while the even neighbour is filled, its
  material users (material id / pass) and, with XBOX.drm, the Xbox library of the same material slot and its slot count;
  --out: point every empty odd slot of the given libraries at the entry of slot - 1 (only the slot table changes;
  the fade variant then draws like the opaque one - no translated shader)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from shaderlib import parse


def mats(D, en):
    e = '>' if en == 'be' else '<'
    out = []
    for s in D.sections:
        if s.type != 10: continue
        refs = set(R.parse(s.reloc, en).idref)
        sl = []
        for k in range(4):
            o = 0x28 + 4 * k
            v = struct.unpack_from(e + 'I', s.data, o)[0] if o + 4 <= len(s.data) else None
            sl.append(v if (9, o) in refs else None)
        out.append((s.id, sl))
    return out


def main(argv):
    out = libs = None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--libs' in argv: k = argv.index('--libs'); libs = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    raw = open(argv[0], 'rb').read(); P = DW.read(raw, 'le')
    X = DW.read(open(argv[1], 'rb').read(), 'be') if len(argv) > 1 else None
    pm = mats(P, 'le'); xm = mats(X, 'be') if X else None
    xl = {s.id: parse(s.data, 'be') for s in X.sections if s.type == 9} if X else {}
    users = collections.defaultdict(list)
    for i, (mid, sl) in enumerate(pm):
        for k in range(3):
            if sl[k] is not None:
                xa = xm[i][1][k] if xm and i < len(xm) else None
                users[sl[k]].append((mid, k, xa))
    holes = {}
    for s in P.sections:
        if s.type != 9: continue
        lib = parse(s.data, 'le')
        if lib['kind'] != 1: continue
        sl = lib['slots']
        odd = [i for i in range(1, len(sl), 2) if sl[i] == 0xffffffff and sl[i - 1] != 0xffffffff]
        if not odd: continue
        holes[s.id] = odd
        us = users.get(s.id, [])
        xs = sorted(set('%s(%s slots, occ %s)' % (xa, len(xl[xa]['slots']), [j for j, o in enumerate(xl[xa]['slots']) if o != 0xffffffff])
                        if xa in xl else str(xa) for _, _, xa in us))
        print('lib %5d: %d slots, empty odd %s; users %s; Xbox %s'
              % (s.id, len(sl), odd, ' '.join('%d/p%d' % (m, k) for m, k, _ in us) or '-', ', '.join(xs) or '-'))
    print('%d pixel-shader libraries with empty odd slots' % len(holes))
    if out:
        n = 0
        for s in P.sections:
            if s.type != 9 or s.id not in (libs or set()): continue
            d = bytearray(s.data); tb = struct.unpack_from('<I', d, 4)[0]
            for i in holes.get(s.id, []):
                src = struct.unpack_from('<I', d, 12 + 4 * (i - 1))[0]
                struct.pack_into('<I', d, 12 + 4 * i, src); n += 1
            s.data = bytes(d)
        open(out, 'wb').write(DW.cdrm_encode(P.write('le'), 'le'))
        B = DW.read(open(out, 'rb').read(), 'le')
        left = [s.id for s in B.sections if s.type == 9 and s.id in (libs or set()) and parse(s.data, 'le')['kind'] == 1
                and any(o == 0xffffffff for o in parse(s.data, 'le')['slots'][1::2])]
        print('filled %d odd slots in libs %s; read back ok, libs with an empty odd slot left among them: %s'
              % (n, sorted(libs or []), left or 'none'))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
