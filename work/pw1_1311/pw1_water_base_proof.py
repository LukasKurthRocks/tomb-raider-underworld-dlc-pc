"""PW.1 (2026-11-13, Q124): byte order of the watervolume intro data words on the base-game pairs.

For every base unit of the PC unit list (pcpatch first, then pcbig) and its Xbox twin (tu, then xbase2, then xbase)
the watervolume intros (object 7) are paired by their rounded position (+0x10; the intro ids of the Xbox and the PC
base builds differ, a pairing by id matched wrong volumes) and every u32 word of the data block (0xc0 B) is
classed: s32 (PC = Xbox u32 swapped), u16p (swapped as two u16 halves), raw, sym (all orders equal), other.
Prints per word offset the class counts and the non-symmetric samples of offsets given with --show (default 4c),
plus a line per volume with the +0x4c word on both sides. Read-only.

Usage (from the repository root):
  ../bin/pyt -t 1800 work/pw1_1311/pw1_water_base_proof.py [--show 4c,50]
Exit code 0.
"""
import sys, os, struct, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode
import drm_write as DW, drm_reloc as R, unit_ids as U


def archives(order):
    out = []
    for s in order:
        path, e, pre = LC.SRC[s]
        p = os.path.join(ROOT, 'tools', path) if not os.path.isabs(path) else path
        if not os.path.exists(p):
            p = path
        if os.path.exists(p): out.append((s, Archive(p, e), pre, e))
    return out


def unit_bytes(arcs, unit):
    for s, A, pre, e in arcs:
        recs = A.find(crc(pre + '\\' + unit + '.drm'))
        if recs: return s, cdrm_decode(A.read(recs[-1]), e), e
    return None, None, None


def volumes(data, e):
    D = DW.read(data, e)
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, e)
    if L is None: return {}
    E = '>' if e == 'be' else '<'
    out = {}
    for si, o in L['intros']:
        d = secs[si]['data']
        if struct.unpack_from(E + 'H', d, o + 0x50)[0] != 7: continue
        uid = struct.unpack_from(E + 'I', d, o + 0x58)[0]
        rp = R.parse(secs[si]['reloc'], e)
        t = dict(rp.internal).get(o + 0x78)
        if t is None or t + 0xc0 > len(d): continue
        ptrs = set(dict(rp.internal))
        pos = tuple(round(v) for v in struct.unpack_from(E + '3f', d, o + 0x10))
        out[pos] = (d[t:t + 0xc0], {q - t for q in ptrs if t <= q < t + 0xc0}, uid)
    return out


def cls(x, p):
    if x == p and x == x[::-1] and x == bytes((x[1], x[0], x[3], x[2])): return 'sym'
    c = []
    if x[::-1] == p: c.append('s32')
    if bytes((x[1], x[0], x[3], x[2])) == p: c.append('u16p')
    if x == p: c.append('raw')
    return '/'.join(c) if c else 'other'


def main(argv):
    show = {0x4c}
    if '--show' in argv:
        show = {int(v, 16) for v in argv[argv.index('--show') + 1].split(',')}
    pc = archives(['pcpatch', 'pcbig'])
    xb = archives(['tu', 'xbase2', 'xbase'])
    units = [l.strip().split('\\')[-1] for l in open(os.path.join(ROOT, 'work', 'generic', 'lists', 'pc_unitlist.txt'))
             if '\\' in l]
    stat = collections.defaultdict(collections.Counter)
    nvol = 0; nunit = 0
    for u in units:
        if u.startswith('dlc') or u.startswith('container'): continue
        ps, pd, pe = unit_bytes(pc, u)
        xs, xd, xe = unit_bytes(xb, u)
        if pd is None or xd is None: continue
        PV = volumes(pd, 'le'); XV = volumes(xd, 'be')
        common = sorted(set(PV) & set(XV))
        if not common: continue
        nunit += 1
        for uid in common:
            nvol += 1
            pb, pptr, puid = PV[uid]; xbk, _, xuid = XV[uid]
            for w in range(0, 0xc0, 4):
                if w in pptr: stat[w]['ptr'] += 1; continue
                c = cls(xbk[w:w + 4], pb[w:w + 4])
                stat[w][c] += 1
                if w in show and c != 'sym':
                    print('  %-26s intro PC %6d / Xbox %6d +%02x Xbox %s PC %s -> %s' % (
                        u, puid, xuid, w, xbk[w:w + 4].hex(), pb[w:w + 4].hex(), c))
    print('\n%d units, %d paired water volumes' % (nunit, nvol))
    for w in sorted(stat):
        c = stat[w]
        if set(c) <= {'sym', 'ptr'}: continue
        print('  +%02x %s' % (w, ', '.join('%s %d' % kv for kv in c.most_common())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
