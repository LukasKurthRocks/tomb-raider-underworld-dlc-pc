"""Repair the UI text element records of a title-update script that the generic converter ported into a PC DRM,
using the RETAIL Xbox / PC pair of the same script as the template (finding 43, hint box: TU generalbank script 10 ->
PC script 9). Record = 16 words from `ffffffff, 00000000, colour, colour (alpha 0xff)`. The converter turned colours
into Symbol pairs (ff606060 -> 60600140), small integers into swapped halves (4 -> 0x40000) and the float -1.0 into
garbage; the retail PC script shows how Crystal Dynamics converted the same record: per position the u32 value
(s32), the bytes as they are (a u8 field, 01000000 -> 01 00 00 00), or a PC-only constant (0 -> 0x00010000).

Per TU record (non-relocation words only):
  * a retail Xbox record with the same 16 words  -> the retail PC words (exact template)
  * else, per position: the template's rule when the TU word equals the retail Xbox word there (bytes / PC constant),
    otherwise the u32 value (s32); the string id word (position 4, `id << 16`, DLC index 1284 .. 1406) -> the PC
    string id of the locmap as u32
Prints every changed word. Read-only on the inputs, writes OUT.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_record_template.py TU.drm TU_ID RETAIL_XBOX.drm RX_ID RETAIL_PC.drm RP_ID
      PORTED_PC.drm PC_ID OUT.drm --locmap MAP.json
  (Xbox DRMs decoded, e.g. tools/bigfile_extract.py tu|xbase generalbank.drm; TU_ID / PC_ID must have one layout)
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

N = 16
DLC_FIRST, DLC_LAST = 1284, 1406


def script(path, sid, e):
    return next(s for s in DW.read(open(path, 'rb').read(), e).sections if s.type == 8 and s.id == sid)


def records(d, e):
    """offsets of `ffffffff, 0, colour, colour (alpha ff)`"""
    out = []
    for o in range(0, len(d) - 4 * N + 1, 4):
        a, b, c1, c2 = struct.unpack_from(e + '4I', d, o)
        if a == 0xffffffff and b == 0 and c2 >> 24 == 0xff and (c1 >> 24 == 0xff): out.append(o)
    return out


def main(argv):
    k = argv.index('--locmap'); lm = {int(a): b for a, b in json.load(open(argv[k + 1]))['map'].items()}; del argv[k:k + 2]
    tu, rx, rp = script(argv[0], int(argv[1]), 'be'), script(argv[2], int(argv[3]), 'be'), script(argv[4], int(argv[5]), 'le')
    raw = open(argv[6], 'rb').read(); D = DW.read(raw, 'le')
    pc = next(s for s in D.sections if s.type == 8 and s.id == int(argv[7]))
    if len(tu.data) != len(pc.data): raise SystemExit('TU and ported PC script differ in length - not one layout')
    rel = set(R.parse(tu.reloc, 'be').pointer_offsets()) | set(R.parse(tu.reloc, 'be').id_offsets())
    words = lambda d, o, e: list(struct.unpack_from(e + '%dI' % N, d, o))
    # templates: retail Xbox record -> retail PC words at the same offset (retail layouts agree there: checked by
    # requiring the PC record head `ffffffff 0` at that offset too)
    tpl = []
    for r in records(rx.data, '>'):
        if r + 4 * N <= len(rp.data) and struct.unpack_from('<2I', rp.data, r) == (0xffffffff, 0):
            tpl.append((words(rx.data, r, '>'), words(rp.data, r, '<'), r))
    if not tpl: raise SystemExit('no retail template record')
    rx0, rp0, r0 = tpl[0]
    rule = []
    for xv, pv in zip(rx0, rp0):
        rule.append('s32' if pv == xv else 'bytes' if pv == int.from_bytes(xv.to_bytes(4, 'big'), 'little') else 'pc')
    print('template: retail record at +%#x, rules %s' % (r0, ' '.join(rule)))
    pd = bytearray(pc.data); st = collections.Counter()
    for o in records(tu.data, '>'):
        tw = words(tu.data, o, '>')
        exact = next((p for x, p, r in tpl if x == tw), None)
        for i, v in enumerate(tw):
            q = o + 4 * i
            if q in rel: continue
            if exact is not None: want = exact[i]
            elif i == 4 and not v & 0xffff and DLC_FIRST <= v >> 16 <= DLC_LAST: want = lm.get(v >> 16, v >> 16)
            elif rule[i] == 'bytes': want = int.from_bytes(v.to_bytes(4, 'big'), 'little')
            elif rule[i] == 'pc' and v == rx0[i]: want = rp0[i]
            else: want = v
            cur = struct.unpack_from('<I', pd, q)[0]
            if cur != want:
                struct.pack_into('<I', pd, q, want); st['words changed'] += 1
                print('  record +%#06x word %2d +%#06x: xbox %08x  pc %08x -> %08x%s' % (o, i, q, v, cur, want, '  (exact template)' if exact else ''))
        st['records' + (' (exact template)' if exact else '')] += 1
    pc.data = bytes(pd)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(argv[8])), exist_ok=True); open(argv[8], 'wb').write(o)
    print(dict(st))


if __name__ == '__main__':
    main(sys.argv[1:])
