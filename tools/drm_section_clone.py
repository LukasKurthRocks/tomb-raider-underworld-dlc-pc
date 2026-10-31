"""Append a copy of one section of a PC DRM under a new id (data, relocations, flags and specMask unchanged), e.g.
a copy of a material that another user should keep while the original is changed. Refuses when the new (type, id)
already exists in the file, or when the section has external relocations (they name section indices of this file;
a copy at the end would still be valid, but is not needed so far and is refused to stay simple).
Finding 43, test 44: the DLC 2 pool keeps a copy of material 24920 (new id) while 24920 gets the eitr-fall material.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_clone.py IN.drm OUT.drm TYPE ID NEW_ID
Check the new id with tools/section_id_free.py first (the engine loads every (type, id) once, game-wide).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    src, out, typ, sid, new = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4])
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    s = next((x for x in D.sections if x.type == typ and x.id == sid), None)
    if s is None: raise SystemExit('section %d:%d not in %s' % (typ, sid, src))
    if any(x.type == typ and x.id == new for x in D.sections): raise SystemExit('%d:%d already exists' % (typ, new))
    if R.parse(s.reloc, 'le').external: raise SystemExit('section %d:%d has external relocations' % (typ, sid))
    c = DW.Section(typ, new, s.data, s.reloc, s.flags, s.ver, s.spec, s.pad)
    D.sections.append(c)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(o)
    print('section %d:%d cloned as %d:%d (%d bytes) -> %s' % (typ, sid, typ, new, len(s.data), out))


if __name__ == '__main__':
    if len(sys.argv) != 6: sys.exit(__doc__)
    main(sys.argv[1:])
