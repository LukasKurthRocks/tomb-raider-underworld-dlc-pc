"""Dump the shader slots and texture references of materials (type 10) in PC DRM files, read-only: the 4 ShaderLib
slots at +0x28 / +0x2c / +0x30 / +0x34 (pixel shader of pass 0-2, vertex shader; tools/material_shader_swap.py),
each with '*' when an id reference (kind 9) sits there and '-' when the slot is empty (no reference: the engine
keeps the shader of the previous draw), plus the texture ids (kind 5 references) in offset order.
Finding 43, test 44b: the DLC 2 fall column changes with the pool's material although no column geometry uses it -
which material of the column has empty slots.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/material_slots_dump.py FILE_OR_DIR [...] [--ids ID,ID] [--empty] [--detail]
  --empty: only materials with at least one empty shader slot; --detail: render flags and texture records
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'): yield os.path.join(p, n)
        else:
            yield p


def main(argv):
    ids = None; empty = '--empty' in argv; detail = '--detail' in argv
    argv = [a for a in argv if a not in ('--empty', '--detail')]
    if '--ids' in argv: k = argv.index('--ids'); ids = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    for f in files(argv):
        try: D = DW.read(open(f, 'rb').read(), 'le')
        except Exception as ex: print('%s: not readable (%s)' % (os.path.basename(f), ex)); continue
        for s in D.sections:
            if s.type != 10 or (ids is not None and s.id not in ids): continue
            r = R.parse(s.reloc, 'le'); refs = set(r.idref)
            slots = []
            for k in range(4):
                o = 0x28 + 4 * k
                v = struct.unpack_from('<I', s.data, o)[0] if o + 4 <= len(s.data) else None
                slots.append('%s%s' % (v, '*' if (9, o) in refs else '-'))
            if empty and all(x.endswith('*') for x in slots): continue
            tex = [struct.unpack_from('<I', s.data, o)[0] for t, o in sorted(r.idref, key=lambda x: x[1]) if t == 5]
            print('%-40s 10:%-6d %5d bytes  shaders %s  textures %s'
                  % (os.path.basename(f), s.id, len(s.data), ' '.join(slots), ' '.join(map(str, tex))))
            if detail:      # render flags 0x4C, counts 0x50, texture records (tools/material_convert.py layout)
                d = s.data; tp = dict(r.internal).get(0x54)
                print('    flags 0x4C %s  0x50 %s' % (d[0x4C:0x50].hex(' '), d[0x50:0x54].hex(' ')))
                if tp is not None:
                    for k in range(d[0x52]):
                        tid, u1, typ, b0, slot, filt = struct.unpack_from('<IIIBBH', d, tp + 16 * k)
                        print('    texture %d: id %5d  u32 %#x  type %d  u8 %d  sampler slot %d  filter %#06x'
                              % (k, tid, u1, typ, b0, slot, filt))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
