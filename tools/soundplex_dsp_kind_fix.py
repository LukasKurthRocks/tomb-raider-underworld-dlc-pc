"""SoundPlex DSP node (type 12) of dlc_caverns_hall DTP 23469: the u16 DSP kind at record +4 (DTP +0x74) is left raw
by the converter (Xbox 00 07 00 00 -> PC 00 07 00 00 = u16 0x0700); the PC engine needs {u16 kind, u16 pad} in
little-endian order (07 00 00 00). Package P4c 2026-11-07, docs Befund-P4c-Caverns-0711.md (workspace docs).

Reader chain (tru.exe 2008 Steam build, tools/pe_dis.py):
  SoundPlex walker 0x5920b0, jump table 0x5923cc, case 12 -> 0x59219f -> node ctor 0x58def0(data = record):
    [record+0] = child node (walked), record+4 passed to 0x58dad0 -> 0x587620: `movzx eax, word [rec+4]; eax-1;
    cmp eax, 0xa; ja default` -> table 0x5876fc picks the DSP type pushed to 0x7b98ea (with the sound system
    [0xcc9f80]); kind 7 -> 5. Out of range (0x0700) -> no DSP is created; 0x582ec0(dsp = 0, ...) returns at once.
  Parameters: 0x582ec0 switches on the same u16; kind 7 (0x583118) sets parameter 0 = [[rec+8]] and 1 = [[rec+8]+4]
    (here 2200.0 and 1.3334 at DTP +0x80).
Base proof: same record layout ({ptr, u16 kind, u16 0, ptr params, 0} behind a {0xc, ptr} node) in base Xbox DTP 12456
  (ar_ani_statue_arms) and its genuine PC twin 19977: Xbox 00 08 00 00 -> PC 08 00 00 00, dtp_audit key rule s16 with
  n = 134, 0 exceptions (kitrest_fp_stats log).

Only the planned word is written; every new word is computed from the Xbox bytes (s16 = both u16 halves swapped).
Before a word is set: Xbox word as expected layout, old PC bytes a raw copy of the Xbox bytes, new u16 kind in 1..11.
Proofs on the written DRM: read back, decompressed bytes differ only in the planned bytes, section headers + relocation
blobs identical, a second plan on the output plans 0 words.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/soundplex_dsp_kind_fix.py SRC_MODS OUT_MODS [--check]
Library (step `dspkind` of tools/dlc_struct_fixes.py, 2026-11-08): fix_drm(raw, rel) -> (new raw or None, changes,
  report lines, Xbox source), proven like main
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW
import tuning_word_audit as TA
from objdata_fx_fix import data_bases

S16 = (1, 0, 3, 2)
# rel -> [(DTP id (Xbox = PC), node offset, record offset)]; kind word = record + 4
PLAN = {'dlc_caverns_hall.drm': [(23469, 0x60, 0x70)]}


def xbox(rel):
    TA.ORDER = ('pack10', 'pack11', 'tu', 'xbase2', 'xbase')
    return TA.load_x(rel.replace('/', chr(92)))


def plan_file(rel, D, xs, lines):
    """{(section index, offset): (old, new)}"""
    ch = {}
    for sid, node, rec in PLAN[rel]:
        xsec = [s for s in xs if s['type'] == 7 and s['id'] == sid]
        ks = [i for i, s in enumerate(D.sections) if s.type == 7 and s.id == sid]
        if len(xsec) != 1 or len(ks) != 1:
            lines.append('  DTP %d: not unique (Xbox %d, PC %d copies) - skipped' % (sid, len(xsec), len(ks))); continue
        xd = xsec[0]['data']; xi = dict(R.parse(xsec[0]['reloc'], 'be').internal)
        pd = D.sections[ks[0]].data
        if len(pd) != len(xd): lines.append('  DTP %d: size differs - skipped' % sid); continue
        # layout check on the Xbox side: node {u32 12, ptr -> rec}, rec {ptr, u16 kind, u16 0, ptr, ...}
        ok = (struct.unpack_from('>I', xd, node)[0] == 12 and xi.get(node + 4) == rec and rec in xi and rec + 8 in xi
              and rec + 4 not in xi and struct.unpack_from('>H', xd, rec + 6)[0] == 0)
        kind = struct.unpack_from('>H', xd, rec + 4)[0]
        if not ok or not 1 <= kind <= 11:
            lines.append('  DTP %d: Xbox layout / kind %d not as expected - skipped' % (sid, kind)); continue
        o = rec + 4
        xw, old = bytes(xd[o:o + 4]), bytes(pd[o:o + 4])
        new = bytes(xw[i] for i in S16)
        if old == new: lines.append('  DTP %d +0x%x: already %s' % (sid, o, new.hex())); continue
        if old != xw:
            lines.append('  DTP %d +0x%x: PC %s is not the raw Xbox word %s - left' % (sid, o, old.hex(), xw.hex())); continue
        assert struct.unpack_from('<H', new, 0)[0] == kind
        ch[(ks[0], o)] = (old, new)
        lines.append('  DTP %d +0x%x: Xbox %s, PC %s (u16 %d) -> %s (u16 kind %d)' % (
            sid, o, xw.hex(), old.hex(), struct.unpack_from('<H', old, 0)[0], new.hex(), kind))
    return ch


def fix_drm(raw, rel):
    """library for the step `dspkind` of tools/dlc_struct_fixes.py (2026-11-08): -> (new raw or None, changes
    [(section index, offset, old, new, section id)], report lines, Xbox source); only the DRMs of PLAN (others:
    (None, [], [], None)). The written bytes are proven as in main (decoded bytes differ only in the planned bytes,
    section headers + relocation blobs identical, re-plan 0): an AssertionError leaves the caller's DRM unchanged."""
    name = os.path.basename(rel.replace(chr(92), '/')).lower()
    if name not in PLAN: return None, [], [], None
    order = TA.ORDER
    try:
        xs, xsrc = xbox(name)
    finally:
        TA.ORDER = order
    D = DW.read(raw, 'le'); lines = []
    ch = plan_file(name, D, xs, lines)
    if not ch: return None, [], lines, xsrc
    ids = {k: D.sections[k].id for k, o in ch}
    for (k, o), (old, new) in ch.items():
        s = D.sections[k]; d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
    out = D.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    D0 = DW.read(raw, 'le'); dec0 = DW.cdrm_decode(raw, 'le'); dec1 = DW.cdrm_decode(out, 'le')
    assert D0.write('le') == bytes(dec0), 'writer not lossless'
    D1 = DW.read(out, 'le')
    assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections), 'decoded size / section count changed'
    for x, y in zip(D0.sections, D1.sections):
        assert (x.type, x.id, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) == \
               (y.type, y.id, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)), 'header / reloc changed'
    bases = data_bases(D0)
    planned = {bases[k] + o + j for (k, o), (old, new) in ch.items() for j in range(4) if old[j] != new[j]}
    diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
    assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
    assert not plan_file(name, D1, xs, []), 're-plan not empty'
    return out, [(k, o, old, new, ids[k]) for (k, o), (old, new) in sorted(ch.items())], lines, xsrc


def main(a):
    check = '--check' in a
    a = [x for x in a if x != '--check']
    if len(a) != 2: sys.exit(__doc__)
    src, out = a
    if not check and os.path.realpath(src) == os.path.realpath(out): sys.exit('OUT_MODS is SRC_MODS')
    for rel in PLAN:
        p = os.path.join(src, rel)
        if not os.path.isfile(p): print('%s: not in %s' % (rel, src)); continue
        orig = open(p, 'rb').read(); D = DW.read(orig, 'le')
        xs, xsrc = xbox(rel)
        lines = []
        ch = plan_file(rel, D, xs, lines)
        print('%s (Xbox %s, input md5 %s): %d word(s)' % (rel, xsrc, hashlib.md5(orig).hexdigest(), len(ch)))
        for l in lines: print(l)
        if check or not ch: continue
        for (k, o), (old, new) in ch.items():
            s = D.sections[k]; d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
        raw = D.write('le')
        if orig[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        D0 = DW.read(orig, 'le'); dec0 = DW.cdrm_decode(orig, 'le'); dec1 = DW.cdrm_decode(raw, 'le')
        assert D0.write('le') == bytes(dec0), 'writer not lossless'
        D1 = DW.read(raw, 'le')
        assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections)
        for x, y in zip(D0.sections, D1.sections):
            assert (x.type, x.id, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) == \
                   (y.type, y.id, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)), 'header / reloc changed'
        bases = data_bases(D0)
        planned = {bases[k] + o + j for (k, o), (old, new) in ch.items() for j in range(4) if old[j] != new[j]}
        diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
        assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
        assert not plan_file(rel, DW.read(raw, 'le'), xs, []), 're-plan not empty'
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(raw); assert open(q, 'rb').read() == raw
        print('  proof: readback ok, %d byte(s) differ = planned (%d word), %d sections: headers + relocation blobs '
              'identical, re-plan 0 words; written %s md5 %s' % (len(diff), len(ch), len(D1.sections), q,
                                                                 hashlib.md5(raw).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
