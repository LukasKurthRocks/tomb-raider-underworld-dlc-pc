"""Give a PC material the engine texture records (back buffer / depth buffer) its pixel shaders' samplers need.

Rule (tools/refraction_inputs_report.py stats, all 2248 base material pairs, Xbox and PC identical, 0 exceptions):
  every sampler named *BackBufferTexture / *DepthBufferTexture of a material's pixel-shader libraries is fed by a
  texture record {u32 id 2 (with a kind-5 id reference), u32 0, u32 type 0, u8 9 = back buffer / 10 = depth buffer,
  u8 sampler slot, u16 filter 2}; the engine records are stored after the ordinary records; byte +0x51 = number of
  ordinary records, +0x52 = all records; byte +0x4F - (highest sampler slot + 1) is 0 / 1 / 2, never negative;
  word +0x44 bit 1 (0x2) is set in 153 / 153 materials with a back-buffer record (others: 5 / 2095) - most likely
  the flag that makes the renderer copy the back buffer before the draw (inferred from the data, code not traced).
Finding 43, test 45: DLC 2 fall column 24691 uses the PC tuple 1909 / - / 1910 / 1911 (surrogates); the only base
material with that tuple, PC 18575 (= Xbox 10992), has 6 ordinary records + s3 = {2, u8 10} + s2 = {2, u8 9},
+0x4F 8, +0x51 6, +0x52 8. 24691 (converted from the Xbox DLC, whose own shader has no such samplers) has none.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/material_engine_samplers.py IN.drm OUT.drm MATID SLOT:KIND [SLOT:KIND ...]
  KIND 9 = back buffer, 10 = depth buffer; records are appended in the given order. Refuses when the sampler name
  of the material's PC pixel-shader libraries (in IN.drm) at SLOT does not match KIND, or when SLOT already has a
  record. +0x52 += n; +0x4F is raised to highest slot + 1 when it is below (the base invariant); with a back-buffer
  record +0x44 |= 2 unless --no-flag.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from shaderlib import parse, constants

KIND_NAME = {9: 'BackBufferTexture', 10: 'DepthBufferTexture'}


def sampler_names(D, lids):
    out = {}
    for lid in lids:
        s = next((x for x in D.sections if x.type == 9 and x.id == lid), None)
        if s is None: continue
        lib = parse(s.data, 'le')
        for o in set(x for x in lib['slots'] if x != 0xffffffff):
            for n, rs, ri, rc in constants(lib['entries'][o]['blob'], 'p')[1]:
                if rs == 3: out.setdefault(ri, set()).add(n)
    return out


def main(argv):
    noflag = '--no-flag' in argv; argv = [a for a in argv if a != '--no-flag']
    src, out, mid = argv[0], argv[1], int(argv[2])
    add = [tuple(map(int, a.split(':'))) for a in argv[3:]]
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    idx = next(i for i, x in enumerate(D.sections) if x.type == 10 and x.id == mid)
    s = D.sections[idx]; d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    lids = [v for v in struct.unpack_from('<3I', d, 0x28) if v]
    names = sampler_names(D, lids)
    tp = dict(r.internal)[0x54]; n = d[0x52]
    recs = [struct.unpack_from('<IIIBBH', d, tp + 16 * k) for k in range(n)]
    have = {x[4] for x in recs}
    for slot, kind in add:
        nm = names.get(slot, set())
        if kind not in KIND_NAME or not any(KIND_NAME[kind] in x for x in nm):
            raise SystemExit('slot s%d: sampler name(s) %s do not match kind %d' % (slot, sorted(nm), kind))
        if slot in have: raise SystemExit('slot s%d already has a record' % slot)
    # other sections must not point into this material (external relocations would need the same shift)
    for j, x in enumerate(D.sections):
        if x.reloc and any(e[0] == idx for e in R.parse(x.reloc, 'le').external):
            raise SystemExit('section %d (type %d id %d) has an external relocation into the material' % (j, x.type, x.id))
    ins = tp + 16 * n; k = 16 * len(add)
    blk = b''.join(struct.pack('<IIIBBH', 2, 0, 0, kind, slot, 2) for slot, kind in add)
    sh = lambda o: o + k if o >= ins else o
    # stored pointer values (the loader adds the section base; in the file they hold the target offset)
    for o, t in r.internal:
        if struct.unpack_from('<I', d, o)[0] == t and t >= ins: struct.pack_into('<I', d, o, t + k)
    d = d[:ins] + bytearray(blk) + d[ins:]
    r.internal = [(sh(o), sh(t)) for o, t in r.internal]
    r.external = [(si, sh(so), do) for si, so, do in r.external]
    r.idref = [(t, sh(o)) for t, o in r.idref] + [(5, ins + 16 * i) for i in range(len(add))]
    r.idref_a = [(t, sh(o)) for t, o in r.idref_a]
    d[0x52] = n + len(add)
    old44 = struct.unpack_from('<I', d, 0x44)[0]
    if any(kind == 9 for slot, kind in add) and not noflag: struct.pack_into('<I', d, 0x44, old44 | 2)
    top = max([x[4] for x in recs] + [a[0] for a in add]) + 1
    old4f = d[0x4F]
    if d[0x4F] < top: d[0x4F] = top
    s.data, s.reloc = bytes(d), R.write(r, 'le')
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
    print('material %d: %d engine record(s) %s appended at +%#x (after %d ordinary); +0x51 %d, +0x52 %d -> %d, +0x4F %d -> %d, '
          '+0x44 %08x -> %08x; %d -> %d bytes'
          % (mid, len(add), ' '.join('s%d=%s' % (a, KIND_NAME[b]) for a, b in add), ins, n, d[0x51], n, d[0x52], old4f, d[0x4F],
             old44, struct.unpack_from('<I', d, 0x44)[0], len(d) - k, len(d)))


if __name__ == '__main__':
    if len(sys.argv) < 5: sys.exit(__doc__)
    main(sys.argv[1:])
