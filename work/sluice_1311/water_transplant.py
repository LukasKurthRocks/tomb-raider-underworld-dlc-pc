"""sluice_1311 (quick workaround test, NOT a pipeline step): replace materials of one PC DRM by the copies of the same
material ids from another PC DRM (data + relocations), and append the ShaderLib / texture sections they reference that
the file lacks. Unlike tools/material_transplant.py an id reference that is in neither file is accepted when the
destination's own material already referenced the same (kind, id) (a global section such as texture 121).
Used to put the old tree's (B138) DLC 1 water material 23171 / 23172 + libs 1465 / 1466 / 2744 / 2745 / 1468 into the
own-tree files for a play test. Writes OUT only; IN / SRC are only read.

usage (from trudlcport): ../bin/pyt -t 600 work/sluice_1311/water_transplant.py IN.drm OUT.drm SRC.drm MAT[,MAT]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R


def refs(sec):
    out = []
    for kind, off in R.parse(sec.reloc, 'le').idref:
        out.append((kind, struct.unpack_from('<I', sec.data, off)[0]))
    return out


def main(a):
    src_in, out, other = a[0], a[1], a[2]
    mats = [int(v) for v in a[3].split(',')]
    raw = open(src_in, 'rb').read()
    D = DW.read(raw, 'le'); B = DW.read(open(other, 'rb').read(), 'le')
    have = {(x.type, x.id) for x in D.sections}
    for mid in mats:
        d = next(s for s in D.sections if s.type == 10 and s.id == mid)
        s = next(x for x in B.sections if x.type == 10 and x.id == mid)
        if R.parse(s.reloc, 'le').external: raise SystemExit('source material %d has external relocations' % mid)
        own_refs = set(refs(d))
        for kind, v in refs(s):
            if (kind, v) in have: continue
            add = next((x for x in B.sections if x.type == kind and x.id == v), None) if kind in (5, 9) else None
            if add is not None and not R.parse(add.reloc, 'le').external:
                D.sections.append(DW.Section(add.type, add.id, add.data, add.reloc, add.flags, add.ver, add.spec, add.pad))
                have.add((kind, v))
                print('  added %s %d (%d bytes)' % ('ShaderLib' if kind == 9 else 'section type %d' % kind, v, len(add.data)))
            elif (kind, v) in own_refs:
                print('  ref %d:%d global (in neither file, our material references it too) - kept' % (kind, v))
            else:
                raise SystemExit('ref %d:%d of material %d is in neither file and not referenced by ours' % (kind, v, mid))
        n0 = len(d.data)
        d.data, d.reloc = s.data, s.reloc
        print('  material %d: %d -> %d bytes (copy of %s)' % (mid, n0, len(s.data), os.path.basename(other)))
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(o)
    print('wrote %s' % out)


if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    main(sys.argv[1:])
