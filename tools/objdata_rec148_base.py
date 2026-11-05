"""Base-pair proof for the spawn word of the object data records (read-only; night analysis N5 04.11.2026, F3 / B24).

The object data DTP D (named at object section +8) holds u16 [D+0x0c] records of 0x17c bytes at [D+0x10]. In
dlc2_uo_goo_drips_spawned DTP 24414 record word +0x148 holds Xbox values like ffff0041 / 02ff0041 / 04ff0021 /
ffff0000, and the converter wrote the two copies of the DTP differently (u32 swap in one, two u16 in the other).
This tool reads the base game Xbox / PC pairs (tools/pairs.py: PC bigfile, Xbox layer1/2) for every object name
of the PC objectlist (ids 1..821), pairs the object data DTPs through object section +8 and counts, per record word
offset given (default +0x148), which byte permutation turns the Xbox bytes into the PC bytes:
  s32 = u32 swap, s16 = two u16 swapped, u16u8u8 = {u16, u8, u8}, u8u8u16 = {u8, u8, u16}, raw, amb (several fit).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/objdata_rec148_base.py OBJECTLIST.txt [--off 0x148[,0x14c]] [--max N] [--show K]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pairs as P
import drm_reloc as R

PERMS = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'u16u8u8': (1, 0, 2, 3), 'u8u8u16': (0, 1, 3, 2), 'raw': (0, 1, 2, 3)}


def objdata(drm, endian):
    if drm is None:
        return None
    _, secs = drm
    e = '>' if endian == 'be' else '<'
    by = {(s['type'], s['id']): s for s in secs}
    for s in secs:
        if s['type'] != 11 or len(s['data']) < 12:
            continue
        r = R.parse(s['reloc'], endian) if s['reloc'] else R.Reloc()
        if dict((o, t) for t, o in r.idref).get(8) != 7:
            continue
        d = by.get((7, struct.unpack_from(e + 'I', s['data'], 8)[0]))
        if d is None:
            return None
        dr = R.parse(d['reloc'], endian) if d['reloc'] else R.Reloc()
        return d['data'], dict(dr.internal)
    return None


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    offs = [int(x, 16) for x in (a[a.index('--off') + 1] if '--off' in a else '0x148').split(',')]
    mx = int(a[a.index('--max') + 1]) if '--max' in a else 100000
    show = int(a[a.index('--show') + 1]) if '--show' in a else 12
    names = []
    for ln in open(a[0], encoding='latin-1').read().splitlines()[1:]:
        if ',' in ln:
            i, n = ln.split(',', 1)
            if int(i) <= 821:
                names.append(n.strip())
    stats = {o: collections.Counter() for o in offs}
    samples = {o: collections.defaultdict(list) for o in offs}
    nobj = nrec = 0
    for n in names[:mx]:
        try:
            x = objdata(P.xbox_drm(n + '.drm'), 'be')
            p = objdata(P.pc_drm(n + '.drm'), 'le')
        except Exception as ex:
            print('skip %s: %s' % (n, ex))
            continue
        if not x or not p:
            continue
        xd, xp = x
        pd, pp = p
        if len(xd) < 0x14 or len(pd) < 0x14:
            continue
        cx = struct.unpack_from('>H', xd, 0x0c)[0]
        cp = struct.unpack_from('<H', pd, 0x0c)[0]
        if cx == 0 or cx != cp or 0x10 not in xp or 0x10 not in pp:
            continue
        nobj += 1
        for k in range(cx):
            bx, bp = xp[0x10] + k * 0x17c, pp[0x10] + k * 0x17c
            if bx + 0x17c > len(xd) or bp + 0x17c > len(pd):
                break
            nrec += 1
            for o in offs:
                xb, pb = xd[bx + o:bx + o + 4], pd[bp + o:bp + o + 4]
                fit = [nm for nm, pm in PERMS.items() if bytes(xb[i] for i in pm) == pb]
                key = fit[0] if len(fit) == 1 else ('amb' if fit else 'none')
                stats[o][key] += 1
                if key not in ('amb',) and len(samples[o][key]) < show:
                    samples[o][key].append('%s rec %d xbox %s pc %s' % (n, k, xb.hex(), pb.hex()))
    print('base objects with object data records: %d, records %d' % (nobj, nrec))
    for o in offs:
        print('record +0x%x: %s' % (o, dict(stats[o])))
        for key, lst in samples[o].items():
            for s in lst:
                print('   %-8s %s' % (key, s))


if __name__ == '__main__':
    main()
