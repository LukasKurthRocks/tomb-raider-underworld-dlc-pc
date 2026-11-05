"""Scan converted DLC DRMs for wrong particle spawn words (record +0x148) in object data DTPs (read-only; night
analysis N5 04.11.2026, F3 / B24 crash tru+0x42e62, anim 65 of dlc2_uo_goo_drips_spawned).

Engine (tru.exe): the object data DTP D (named at object section +8) holds u16 [D+0x0c] particle records of 0x17c
bytes at [D+0x10]. The emitter build tru+0x1453a5 copies record byte +0x148 -> emitter +0x136 (spawn animation index,
0xff = none), byte +0x149 -> +0x137, and bit fields of the u16 +0x14a -> emitter +0x134 (spawn mode bits); the spawner
tru+0x140b80 copies them to the particle (+0xf0 / +0xf1 / +0xf2) and tru+0x137e90 spawns the object with that anim.
Base pairs (tools/objdata_rec148_base.py): 471 objects, 11 032 records, word +0x148 = {u8, u8, u16} in all 341
informative records (0 other classes).

For every PC DRM given (files / folders) with an Xbox source in work/generic/dlc_drms.pkl (pack11 first, then pack10),
every type-7 section whose id is an object data DTP is paired with the Xbox section of the same id and the same
occurrence number (1st copy with 1st copy ...); each record's +0x148 is compared with the {u8, u8, u16} conversion of
the Xbox bytes. Reports wrong words with the decoded values (anim index / spawn bits PC vs right).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/objdata_rec148_scan.py PATH [PATH ...]
"""
import sys, os, struct, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'):
                    yield os.path.join(p, n)
        else:
            yield p


def objdata_ids(secs, e, key):
    out = set()
    for s in secs:
        t, d, rel = key(s)
        if t != 11 or len(d) < 12:
            continue
        r = R.parse(rel, e) if rel else R.Reloc()
        if dict((o, ty) for ty, o in r.idref).get(8) == 7:
            out.add(struct.unpack_from(('>' if e == 'be' else '<') + 'I', d, 8)[0])
    return out


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    idx = {}
    for k, v in C.items():
        if k[0] in ('ack11.000', 'ack10.000'):
            nm = base(k[1])
            if nm not in idx or k[0] == 'ack11.000':
                idx[nm] = v
    nf = nx = nrec = nbad = 0
    for path in files(a):
        nf += 1
        nm = os.path.splitext(os.path.basename(path))[0].lower()
        if nm not in idx:
            continue
        try:
            pdrm = DW.read(open(path, 'rb').read(), 'le')
        except Exception as ex:
            print('SKIP %s: %s' % (nm, ex))
            continue
        nx += 1
        _, xsecs = idx[nm]
        ids = objdata_ids(pdrm.sections, 'le', lambda s: (s.type, s.data, s.reloc))
        xids = objdata_ids(xsecs, 'be', lambda s: (s['type'], s['data'], s['reloc']))
        for did in sorted(ids & xids):
            pl = [s for s in pdrm.sections if s.type == 7 and s.id == did]
            xl = [s for s in xsecs if s['type'] == 7 and s['id'] == did]
            for copy, (ps, xs) in enumerate(zip(pl, xl)):
                pd, xd = ps.data, xs['data']
                pp = dict(R.parse(ps.reloc, 'le').internal) if ps.reloc else {}
                xp = dict(R.parse(xs['reloc'], 'be').internal) if xs['reloc'] else {}
                if len(pd) < 0x14 or len(xd) < 0x14 or 0x10 not in pp or 0x10 not in xp:
                    continue
                n = struct.unpack_from('>H', xd, 0x0c)[0]
                if n != struct.unpack_from('<H', pd, 0x0c)[0]:
                    print('%s DTP %d copy %d: record counts differ' % (nm, did, copy))
                    continue
                for k in range(n):
                    bx, bp = xp[0x10] + k * 0x17c, pp[0x10] + k * 0x17c
                    if bx + 0x17c > len(xd) or bp + 0x17c > len(pd):
                        break
                    nrec += 1
                    xb = xd[bx + 0x148:bx + 0x14c]
                    want = bytes((xb[0], xb[1], xb[3], xb[2]))
                    got = pd[bp + 0x148:bp + 0x14c]
                    if got != want:
                        nbad += 1
                        print('%s DTP %d copy %d (section index %d) rec %d +0x%x: xbox %s pc %s right %s | '
                              'pc anim %d spawn-bits 0x%04x, right anim %d spawn-bits 0x%04x'
                              % (nm, did, copy, pdrm.sections.index(ps), k, bp + 0x148, xb.hex(), got.hex(),
                                 want.hex(), got[0], struct.unpack('<H', got[2:])[0], want[0],
                                 struct.unpack('<H', want[2:])[0]))
    print('files %d, with Xbox source %d, particle records %d, wrong +0x148 words %d' % (nf, nx, nrec, nbad))


if __name__ == '__main__':
    main()
