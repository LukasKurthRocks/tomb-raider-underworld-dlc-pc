"""Bring a script's vtable to the PC layout by inserting the PC's extra slot (finding 43).

Case: generalbank script 6 (loading screen). The PC version has 53 vtable slots, the Xbox (retail and title update)
52: the PC inserts one inherited slot at 31, every slot from 31 on moves up by one, and every prototype with
vtIndex >= 31 has vtIndex + 1 on PC (21 of 21). A converted Xbox script keeps the Xbox layout, so on PC the engine
reads slot 52 beyond the table and calls the wrong function from slot 31 on (crash: jump to address 2).

What it changes in SECTION of IN (a file whose other sections are laid out as in REF, e.g. the output of
drm_put_sections.py on the installed generalbank):
  * a new vtable (count word + SIZE+1 pointers) is APPENDED to the section data (nothing else moves; the old table
    stays, unused): old slots 0..SLOT-1, then the REF section's slot SLOT (its VTE struct appended as well, with REF's
    relocations - they address sections by index, valid because IN keeps REF's section order), then old SLOT..SIZE-1;
  * root 0x3c (vtableSize) +1, root 0x44 -> the new table;
  * every prototype with vtIndex >= SLOT (and != 0xffff): vtIndex + 1.
Checks: the REF section must have exactly SIZE+1 slots; the copied VTE may not contain internal relocations.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_vtable_insert.py IN_DRM REF_DRM OUT_DRM SCRIPT_ID SLOT
  e.g. work/rebuild/dlc2_gb4/generalbank.drm ../data/pc/mods/generalbank.drm work/rebuild/dlc2_gb5/generalbank.drm 6 31
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC


def main(argv):
    src, ref, out, sid, slot = argv[0], argv[1], argv[2], int(argv[3]), int(argv[4])
    D = DW.read(open(src, 'rb').read(), 'le'); P = DW.read(open(ref, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    p = next(x for x in P.sections if x.type == 8 and x.id == sid)
    d = bytearray(s.data); r = R.parse(s.reloc, 'le'); it = dict(r.internal)
    pd = p.data; pr = R.parse(p.reloc, 'le'); pit = dict(pr.internal)
    size = struct.unpack_from('<H', d, 0x3c)[0]; psize = struct.unpack_from('<H', pd, 0x3c)[0]
    if psize != size + 1: sys.exit('reference has %d slots, this section %d - expected exactly one more' % (psize, size))
    old = it[0x44]; pold = pit[0x44]
    # the reference VTE of the extra slot: u32 n + n pointers
    pv = pit[pold + 4 * slot]; n = struct.unpack_from('<I', pd, pv)[0]; vlen = 4 + 4 * n
    if any(pv <= a < pv + vlen for a, _ in pr.internal): sys.exit('reference VTE has internal relocations - not copied')
    pext = [(si, a - pv, dd) for si, a, dd in pr.external if pv <= a < pv + vlen]
    # append: [VTE copy][count][new table]
    while len(d) % 4: d.append(0)
    vte = len(d); d += pd[pv:pv + vlen]
    d += struct.pack('<I', size + 1); table = len(d)
    slots = [it[old + 4 * k] for k in range(size)]
    slots = slots[:slot] + [vte] + slots[slot:]
    d += b'\0' * (4 * (size + 1))
    r.internal = [(a, b) for a, b in r.internal if a != 0x44] + [(0x44, table)] + [(table + 4 * k, t) for k, t in enumerate(slots)]
    for k in range(size + 1): struct.pack_into('<I', d, table + 4 * k, 0xBEEBBEEB)   # pointer slots: the PC files
    struct.pack_into('<I', d, 0x44, 0xBEEBBEEB)                                       # hold this placeholder
    r.external += [(si, vte + o, dd) for si, o, dd in pext]
    struct.pack_into('<H', d, 0x3c, size + 1)
    # prototypes: vtIndex >= slot -> +1 (u16 at prototype + 6)
    shifted = 0
    for a, v, f in SC.elements(bytes(s.data), R.parse(s.reloc, 'le'), 'le').get('protos', []):
        vi = struct.unpack_from('<H', d, a + 6)[0]
        if vi != 0xffff and vi >= slot: struct.pack_into('<H', d, a + 6, vi + 1); shifted += 1
    # the section's own size field (root 0x1c, u16) is the instance size, not the data size - untouched
    before = len(s.data); s.data = bytes(d); s.reloc = R.write(r, 'le')
    raw = D.write('le'); E = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in E.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in E.sections)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: vtable %d -> %d slots (slot %d copied from the reference, VTE n=%d, %d external relocations), '
          '%d prototypes vtIndex+1, section %d -> %d bytes; sections with relocations out of bounds: %d -> %s' % (
              sid, size, size + 1, slot, n, len(pext), shifted, before, len(d), bad, out))


if __name__ == '__main__':
    main(sys.argv[1:])
