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
--ref-any: the REF section may have any number of slots above SLOT (test 35: the ported title-update hint-box script
9 has 4 own virtual functions and 35 slots, Crystal's PC script 9 only 2 and 34 - its slot 31 is still the parent's
extra PC slot).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_vtable_insert.py IN_DRM REF_DRM OUT_DRM SCRIPT_ID SLOT [--ref-any]
  e.g. work/rebuild/dlc2_gb4/generalbank.drm ../data/pc/mods/generalbank.drm work/rebuild/dlc2_gb5/generalbank.drm 6 31
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC


def ref_vte(pd, pr, slot):
    """the reference section's VTE of `slot`: (VTE bytes = u32 n + n pointers, [(section index, offset in the VTE,
    target offset)]); refuses a VTE with internal relocations"""
    pit = dict(pr.internal)
    pv = pit[pit[0x44] + 4 * slot]; n = struct.unpack_from('<I', pd, pv)[0]; vlen = 4 + 4 * n
    if any(pv <= a < pv + vlen for a, _ in pr.internal): raise ValueError('reference VTE has internal relocations')
    return bytes(pd[pv:pv + vlen]), [(si, a - pv, dd) for si, a, dd in pr.external if pv <= a < pv + vlen]


def appended(at, slots_old, slot, vte_bytes, pext):
    """the block appended at data offset `at` (4-aligned): [VTE copy][count][new table of placeholders] -> (bytes,
    table offset, internal entries [(0x44, table)] + [(slot pointer, target)], external entries of the VTE copy);
    slots_old = the old table's slot targets. Also used by tools/generalbank_pc_build.py (rule, not recorded bytes)."""
    size = len(slots_old)
    slots = list(slots_old[:slot]) + [at] + list(slots_old[slot:])
    d = bytes(vte_bytes) + struct.pack('<I', size + 1)
    table = at + len(d)
    d += struct.pack('<I', 0xBEEBBEEB) * (size + 1)          # pointer slots: the PC files hold this placeholder
    return d, table, [(0x44, table)] + [(table + 4 * k, t) for k, t in enumerate(slots)], \
        [(si, at + o, dd) for si, o, dd in pext]


def main(argv):
    ref_any = '--ref-any' in argv
    argv = [a for a in argv if a != '--ref-any']
    src, ref, out, sid, slot = argv[0], argv[1], argv[2], int(argv[3]), int(argv[4])
    D = DW.read(open(src, 'rb').read(), 'le'); P = DW.read(open(ref, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    p = next(x for x in P.sections if x.type == 8 and x.id == sid)
    d = bytearray(s.data); r = R.parse(s.reloc, 'le'); it = dict(r.internal)
    pd = p.data; pr = R.parse(p.reloc, 'le'); pit = dict(pr.internal)
    size = struct.unpack_from('<H', d, 0x3c)[0]; psize = struct.unpack_from('<H', pd, 0x3c)[0]
    if ref_any:
        if psize <= slot: sys.exit('reference has %d slots - no slot %d to copy' % (psize, slot))
    elif psize != size + 1: sys.exit('reference has %d slots, this section %d - expected exactly one more' % (psize, size))
    old = it[0x44]
    # the reference VTE of the extra slot: u32 n + n pointers
    try:
        vte_bytes, pext = ref_vte(pd, pr, slot)
    except ValueError as e:
        sys.exit('%s - not copied' % e)
    n = (len(vte_bytes) - 4) // 4
    for si, _, _ in pext:       # REF's section indices are reused: IN must hold the same section at that index
        if si >= len(D.sections) or (D.sections[si].type, D.sections[si].id) != (P.sections[si].type, P.sections[si].id):
            sys.exit('section %d is %s in the reference but %s here - the inputs are not laid out alike' % (
                si, (P.sections[si].type, P.sections[si].id),
                (D.sections[si].type, D.sections[si].id) if si < len(D.sections) else 'missing'))
    missing = [k for k in range(size) if old + 4 * k not in it]
    if missing: sys.exit('vtable slots %s have no internal relocation (null or external) - not handled' % missing)
    # append: [VTE copy][count][new table]
    while len(d) % 4: d.append(0)
    vte = len(d)
    blk, table, ints, exts = appended(vte, [it[old + 4 * k] for k in range(size)], slot, vte_bytes, pext)
    d += blk
    r.internal = [(a, b) for a, b in r.internal if a != 0x44] + ints
    struct.pack_into('<I', d, 0x44, 0xBEEBBEEB)                                       # the PC files hold this placeholder
    r.external += exts
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
    if bad: sys.exit('%d sections with relocations out of bounds - %s NOT written' % (bad, out))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: vtable %d -> %d slots (slot %d copied from the reference, VTE n=%d, %d external relocations), '
          '%d prototypes vtIndex+1, section %d -> %d bytes; sections with relocations out of bounds: %d -> %s' % (
              sid, size, size + 1, slot, n, len(pext), shifted, before, len(d), bad, out))


if __name__ == '__main__':
    main(sys.argv[1:])
