"""Find a raw little-endian u32 value in the sections of PC DRM files, read-only (no relocation needed - catches ids
stored without an id reference). Finding 43, test 44: where else could material 24920 be named.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/drm_raw_u32_find.py VALUE FILE_OR_DIR [...] [--type T] [--aligned]
  --type T   only sections of type T; --aligned  only 4-byte aligned positions
Output per hit: file, section type:id, offset, and whether the position is an id reference / pointer in the relocs.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    typ = None; aligned = '--aligned' in argv; argv = [a for a in argv if a != '--aligned']
    if '--type' in argv: k = argv.index('--type'); typ = int(argv[k + 1]); del argv[k:k + 2]
    val = struct.pack('<I', int(argv[0], 0)); hits = 0
    paths = []
    for a in argv[1:]:
        if os.path.isdir(a):
            for root, _ds, fs in os.walk(a):
                paths += [os.path.join(root, n) for n in sorted(fs) if n.lower().endswith('.drm')]
        else:
            paths.append(a)
    for path in paths:
        try:
            D = DW.read(open(path, 'rb').read(), 'le')
        except Exception:
            continue
        for s in D.sections:
            if typ is not None and s.type != typ: continue
            o = s.data.find(val)
            if o < 0: continue
            r = R.parse(s.reloc, 'le'); ids = r.id_offsets(); ptrs = set(r.pointer_offsets())
            while o >= 0:
                if not aligned or o % 4 == 0:
                    hits += 1
                    tag = 'idref type %d' % ids[o] if o in ids else ('pointer' if o in ptrs else 'raw')
                    print('%s  %d:%d  +%#x  %s' % (os.path.basename(path), s.type, s.id, o, tag))
                o = s.data.find(val, o + 1)
    print('%d hits' % hits)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
