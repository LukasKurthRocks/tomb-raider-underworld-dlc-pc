"""Object event lists: kind-1 records of sub type 0x32 carry a 32-bit section id in payload word 1; check that the PC
word is the u32 conversion of the Xbox word and with --out repair it (read-only unless --out; test 50d: player event
0x87 of doppelganger_casual DTP 20172 faulted in tru+0x14df84 with index 0x688c0000 = id 0x688c with swapped u16
halves).

Proof from the PC reader (tru.exe 2008 Steam build): kind-1 handler tru+0x147b40 switches on the u16 at payload +0
(`movzx eax, word [esi]; dec; jmp [eax*4 + 0x54872c]`); case 0x32 (tru+0x1486b2) passes `mov eax, dword [esi + 4]`
(a full u32) to tru+0x135eb0, which calls tru+0x14df80(id) = `[id*4 + 0x00c36f28]` (the section table by id). So the
word is one u32 (an id), not two u16 - the converter's learned rule for key (kind 1, 2 words, word 3) is u16 (from the
base pair, where no sub-0x32 record exists). Record format: tools/obj_eventlist_fix.py.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/eventlist_idword_fix.py XBOX.drm PC.drm [--out OUT.drm] [--subs 0x32[,..]]
Output: every kind-1 record of the listed subs, Xbox word, PC word, expected PC word, whether the id names a section of
the PC file; --out writes the repaired DRM (CDRM kept when the input is CDRM) and reads it back.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import obj_eventlist_fix as OE


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    xp, pp = argv[0], argv[1]
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    subs = {0x32}
    if '--subs' in argv: subs = {int(x, 0) for x in argv[argv.index('--subs') + 1].split(',')}
    DX = DW.read(open(xp, 'rb').read(), 'be')
    DP = DW.read(open(pp, 'rb').read(), 'le')
    ids = {s.id for s in DP.sections}
    xo = {s.id: lst for _, s, lst in OE.objects(DX, 'be')}
    n = nbad = 0
    patched = {}
    for _, s, lst in OE.objects(DP, 'le'):
        xl = xo.get(s.id)
        if lst is None or xl is None: continue
        rp, _ = OE.walk(lst.data, 'le'); rx, _ = OE.walk(xl.data, 'be')
        if len(rp) != len(rx) or any(a[1] != b[1] or a[2] != b[2] for a, b in zip(rp, rx)):
            print('object %d: list %d record layout differs - skipped' % (s.id, lst.id)); continue
        d = bytearray(lst.data)
        for (a, h, sz), (ax, hx, szx) in zip(rp, rx):
            if h & 3 != 1 or sz < 16: continue
            sub_x = struct.unpack_from('>H', xl.data, ax + 8)[0]
            if sub_x not in subs: continue
            wx = struct.unpack_from('>I', xl.data, ax + 12)[0]
            wp = struct.unpack_from('<I', d, a + 12)[0]
            n += 1
            ok = wp == wx
            nbad += not ok
            print('object %d list %d +0x%04x type 0x%02x sub 0x%02x: Xbox u32 0x%08x, PC u32 0x%08x -> %s; id %d %s'
                  % (s.id, lst.id, a, d[a + 4], sub_x, wx, wp, 'ok' if ok else 'WRONG (expected 0x%08x)' % wx, wx,
                     'is a section of the PC file' if wx in ids else 'NOT a section of this file'))
            if not ok: struct.pack_into('<I', d, a + 12, wx)
        if bytes(d) != lst.data: patched[lst.id] = bytes(d)
    print('records %d, wrong %d' % (n, nbad))
    if out:
        for k, s in enumerate(DP.sections):
            if s.type == 7 and s.id in patched:
                DP.sections[k] = DW.Section(s.type, s.id, patched[s.id], s.reloc, s.flags, s.ver, s.spec, s.pad)
        raw = DP.write('le')
        if open(pp, 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(raw)
        DR = DW.read(open(out, 'rb').read(), 'le')
        assert [(a.type, a.id, a.data, a.reloc) for a in DR.sections] == [(b.type, b.id, b.data, b.reloc) for b in DP.sections]
        print('wrote %s (lists changed: %s), readback ok' % (out, sorted(patched)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
