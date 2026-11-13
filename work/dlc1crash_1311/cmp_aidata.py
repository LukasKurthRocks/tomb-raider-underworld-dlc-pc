"""Compare the AI combat-data record of DTP 20872 (+0x5530) in installed dlc_caverns.drm copies; run aidata_fix on each
(what fix() would still change). Usage: pyt cmp_aidata.py <drm> [<drm>...]  (read only)"""
import sys, os, struct, collections
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools')
sys.path.insert(0, T)
import drm_write as DW, drm_reloc as R, aidata_fix as A
from drm import cdrm_decode, sections_with_data
from convert_dlc import raw_dlc
DTP, REC = 20872, 0x5530
raw, _ = raw_dlc('dlc_caverns.drm')
_, xs = sections_with_data(cdrm_decode(raw, 'be'), 'be')
ids = A._ids()
xbox_id = [s['id'] for s in xs if s['type'] == 7 and ids(7, s['id']) == DTP]
print('xbox ids mapping to PC 20872:', xbox_id)
xsec = [s for s in xs if s['type'] == 7 and s['id'] in xbox_id][0]
xrel = R.parse(xsec['reloc'], 'be')
print('xbox DTP %d size 0x%x, aidata records at %s' % (xsec['id'], len(xsec['data']), [hex(t) for t in A.detect(xsec['data'], xrel)]))
xd = xsec['data']
for k in range(0, 33):
    o = REC + 0x8c + 0x18 * k
    print('  xbox +0x%03x: %s %s' % (0x8c + 0x18 * k, xd[o:o + 4].hex(), xd[o + 4:o + 8].hex()), end='\n' if k % 4 == 3 else '')
print()
for path in sys.argv[1:]:
    d = DW.read(open(path, 'rb').read(), 'le')
    secs = [s for s in d.sections if s.type == 7 and s.id == DTP]
    print('==', path, 'sections type7 id20872:', len(secs))
    for s in secs:
        b = s.data
        print('  size 0x%x sig@0x%x = %d' % (len(b), REC, struct.unpack_from('<I', b, REC)[0]))
        for k in (15, 16, 17, 18):
            o = REC + 0x8c + 0x18 * k
            print('   +0x%03x: %08x %08x' % (0x8c + 0x18 * k, *struct.unpack_from('<II', b, o)))
        bad = []
        for k in range(33):
            o = REC + 0x8c + 0x18 * k
            v = struct.unpack_from('<I', b, o)[0]
            if v >= 0x8000 and v != 0xffffffff: bad.append((hex(0x8c + 0x18 * k), hex(v)))
        print('   id words >= 0x8000 in record:', len(bad), bad[:12])
        buf = bytearray(b)
        n = A.fix(xd, xrel, buf, ids) if len(b) == len(xd) else 'size differs'
        print('   aidata_fix would change words:', n)
        if isinstance(n, int) and n:
            ch = [o for o in range(0, len(buf) // 4 * 4, 4) if buf[o:o + 4] != b[o:o + 4]]
            print('   changed offsets (first 20):', [(hex(o), b[o:o + 4].hex(), buf[o:o + 4].hex()) for o in ch[:20]])
print(dict(A.FIX_STATS))
