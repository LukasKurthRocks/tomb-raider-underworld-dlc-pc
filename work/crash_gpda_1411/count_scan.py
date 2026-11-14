"""Read-only (crash 2 of 2026-11-14, 21:50): list counts {u32 n, internal pointer} of the ported / new g_pda scripts.
For every internal pointer of the pack11 Xbox original whose previous word is no pointer and holds a small count
(1..0xffff, big-endian): does the built PC word hold the same number little-endian? 'byte order kept' = the built
word is the Xbox bytes unchanged (value = the byte swap of the count) - what tru.exe 0x4ca2a0 / 0x5a4ce0 crashed on.
Also a census of words whose built bytes = the Xbox bytes (not 0 / -1, not a byte palindrome).
Usage (repo root): ../bin/pyt -t 1800 work/crash_gpda_1411/count_scan.py BUILT_G_PDA [--show N]"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import gpda_port as GP
import drm_write as DW, drm_reloc as R


def main(argv):
    show = 30
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    K = GP.load_knowledge(); I = GP.ids()
    PK = GP.read_pack(); pk = {(s['type'], s['id']): s for s in PK}
    inv = {(t, I(t, x)): (t, x) for (t, x) in pk}
    sec = {(s.type, s.id): s for s in DW.read(open(argv[0], 'rb').read(), 'le').sections}
    targets = sorted((k for k, r in K['recipes'].items() if r in ('port', 'new93', 'new')), key=lambda q: int(q.split(':')[1]))
    tot = collections.Counter(); shown = 0; small = []
    for key in targets:
        t, sid = map(int, key.split(':'))
        if (t, sid) not in sec: continue
        s = sec[(t, sid)]; xs = pk[inv[(t, sid)]]
        xd, d = xs['data'], s.data
        xr = R.parse(xs['reloc'], 'be'); xptr = set(xr.pointer_offsets())
        br = R.parse(s.reloc, 'le'); bptr = set(br.pointer_offsets())
        per = collections.Counter()
        for o, tg in xr.internal:
            w = o - 4
            if w < 0 or w in xptr or w in bptr or w + 4 > len(d): continue
            xv = struct.unpack_from('>I', xd, w)[0]
            if not 1 <= xv <= 0xffff: continue
            bv = struct.unpack_from('<I', d, w)[0]
            if bv == xv: per['count ok'] += 1; continue
            kind = 'BYTE ORDER KEPT' if d[w:w + 4] == xd[w:w + 4] else 'other value'
            per['count ' + kind] += 1
            if shown < show:
                shown += 1
                print('%s +0x%x: Xbox count %d, built %s (%s), pointer +0x%x -> +0x%x' % (key, w, xv, d[w:w + 4].hex(), kind, o, tg))
        for w in range(0, min(len(xd), len(d)) - 3, 4):
            if w in xptr or w in bptr: continue
            xb = xd[w:w + 4]
            if xb in (b'\0\0\0\0', b'\xff\xff\xff\xff') or xb == xb[::-1]: continue
            if d[w:w + 4] == xb:
                per['words with the Xbox bytes unchanged'] += 1
                if 1 <= struct.unpack('>I', xb)[0] <= 0xffff:     # a small Xbox integer read little-endian = huge
                    per['  of them a small Xbox integer (UNSWAPPED)'] += 1
                    small.append('%s +0x%x Xbox %s' % (key, w, xb.hex()))
        print(key, dict(per))
        tot.update(per)
    for x in small[:show]: print('  unswapped small integer:', x)
    print('total', dict(tot))


if __name__ == '__main__':
    main(sys.argv[1:])
