"""Weapon / thrall / shadow-combat tuning: Xbox source vs converted PC file, word by word (read-only; test questions
2026-11-05 "pistol feels weak, thralls get up again").

For every type-7 section of XBOX paired with the PC file (same DTP id, else the unique PC section with the same size
and the same internal-pointer offsets), every word that is not a pointer / id slot on the Xbox side is classified by
the byte permutation that turns the Xbox bytes into the PC bytes (u32 | u16pair | raw | u8u8u16 | other) and flagged:
  FLOAT   Xbox BE float plausible (finite, 1e-4 <= |v| <= 1e6, not a small int pattern) but the PC word is not the
          u32-reversed value - the PC float differs (the 'float swapped as u16 pair / left raw' fault class)
  INTGREW Xbox BE u32 in 1..0xffff, PC LE u32 >= 0x10000 (count / index left raw)
  PAIR    Xbox halves both in 1..0x7fff (two small u16) but converted as u32 (halves exchanged on PC)
Words where Xbox == PC as u32 (or both orders give the same bytes) are fine and only counted.

Modes (from the repository root):
  ../bin/pyt -t 600 tools/tuning_word_audit.py audit XBOX_NAME PC.drm [DTP[,DTP..]] [--all] [--range DTP:LO:HI]
        flags per DTP (counts) and every flagged word of the named DTPs (all DTPs with --all); --range dumps every
        word of one DTP range with both values (hex LO / HI)
  ../bin/pyt -t 300 tools/tuning_word_audit.py source PROFILE.json NAME.drm [NAME.drm ..]
        which tree of a test profile supplies NAME last (and its expected md5), md5 of the installed file
  ../bin/pyt -t 600 tools/tuning_word_audit.py xcmp XBOX_A XBOX_B DTP_A:DTP_B[:LO:HI]
        two Xbox sections word by word (e.g. DLC handgun vs base handgun tuning)
XBOX_NAME: DRM name in the Xbox archives (TitleUpdate / DLC packs / layers, tools/locals.py SRC) or a file path.
"""
import sys, os, struct, collections, math, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
from drm import cdrm_decode, sections_with_data

ORDER = ('tu', 'pack11', 'pack10', 'xbase2', 'xbase', 'pack1', 'pack2', 'pack20')


def load_x(spec):
    if os.path.isfile(spec):
        return sections_with_data(cdrm_decode(open(spec, 'rb').read(), 'be'), 'be')[1], spec
    import locals as LC
    from archive import Archive
    from names import crc
    n = spec if spec.endswith('.drm') else spec + '.drm'
    for src in ORDER:
        path, e, pre = LC.SRC[src]
        if e != 'be' or not os.path.exists(path): continue
        A = Archive(path, e)
        r = [x for x in A.find(crc(pre + '\\' + n)) if x['spec'] == 0xffffffff]
        if r:
            return sections_with_data(cdrm_decode(A.read(r[0]), 'be'), 'be')[1], src
    sys.exit('not in the Xbox archives: ' + n)


def load_p(path):
    return sections_with_data(cdrm_decode(open(path, 'rb').read(), 'le'), 'le')[1]


def cls(xw, pw):
    if xw[::-1] == pw: return 'u32'
    if xw[1::-1] + xw[:1:-1] == pw: return 'u16pair'
    if xw == pw: return 'raw'
    if xw[:2] + xw[:1:-1] == pw: return 'u8u8u16'
    return 'other'


def plaus_f(b, e):
    v = struct.unpack(e + 'f', b)[0]
    return math.isfinite(v) and 1e-4 <= abs(v) <= 1e6, v


def pair(xs, ps):
    """[(xsec, psec)] type-7 pairs"""
    pid = collections.defaultdict(list)
    for s in ps:
        if s['type'] == 7: pid[s['id']].append(s)
    used = set(); out = []
    lay = collections.defaultdict(list)
    for s in ps:
        if s['type'] == 7:
            lay[len(s['data']), tuple(sorted(o for o, t in R.parse(s['reloc'], 'le').internal))].append(s)
    seen = collections.Counter()
    for s in xs:
        if s['type'] != 7: continue
        c = seen[s['id']]; seen[s['id']] += 1
        cand = pid.get(s['id'], [])
        p = cand[c] if c < len(cand) and len(cand[c]['data']) == len(s['data']) else None
        if p is None:
            key = (len(s['data']), tuple(sorted(o for o, t in R.parse(s['reloc'], 'be').internal)))
            cc = [q for q in lay.get(key, []) if id(q) not in used]
            p = cc[0] if len(cc) == 1 else None
        if p is not None: used.add(id(p))
        out.append((s, p))
    return out


def audit_pair(s, p):
    xd, pd = s['data'], p['data']
    xr = R.parse(s['reloc'], 'be')
    skip = set(xr.pointer_offsets()) | set(xr.id_offsets())
    flags = []; cnt = collections.Counter()
    for o in range(0, min(len(xd), len(pd)) // 4 * 4, 4):
        if o in skip: cnt['slot'] += 1; continue
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        c = cls(xw, pw)
        cnt[c] += 1
        if xw == xw[::-1] or c == 'u32': continue
        okf, xf = plaus_f(xw, '>')
        xi = struct.unpack('>I', xw)[0]
        pi = struct.unpack('<I', pw)[0]
        h1, h2 = struct.unpack('>HH', xw)
        smallpair = 1 <= h1 <= 0x7fff and 1 <= h2 <= 0x7fff
        if okf and not smallpair and xi > 0xffff:
            flags.append(('FLOAT', o, xw, pw, c, '%.6g -> %.6g' % (xf, struct.unpack('<f', pw)[0])))
        elif 1 <= xi <= 0xffff and pi >= 0x10000:
            flags.append(('INTGREW', o, xw, pw, c, '%d -> %d' % (xi, pi)))
    for o in range(0, min(len(xd), len(pd)) // 4 * 4, 4):
        if o in skip: continue
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        h1, h2 = struct.unpack('>HH', xw)
        if 1 <= h1 <= 0x7fff and 1 <= h2 <= 0x7fff and h1 != h2 and cls(xw, pw) == 'u32':
            flags.append(('PAIR', o, xw, pw, 'u32', '(%d, %d) -> (%d, %d)' % (h1, h2, *struct.unpack('<HH', pw))))
    return flags, cnt


def audit(xname, ppath, want, show_all, rng):
    xs, src = load_x(xname); ps = load_p(ppath)
    print('Xbox %s (%s)  PC %s  md5 %s' % (xname, src, ppath, hashlib.md5(open(ppath, 'rb').read()).hexdigest()))
    tot = collections.Counter(); unp = 0
    for s, p in pair(xs, ps):
        if p is None:
            unp += 1
            if want and s['id'] in want: print('DTP %d: no PC twin' % s['id'])
            continue
        if rng and s['id'] == rng[0]:
            xd, pd = s['data'], p['data']
            xr = R.parse(s['reloc'], 'be'); sl = set(xr.pointer_offsets()); il = set(xr.id_offsets())
            for o in range(rng[1], min(rng[2], len(xd), len(pd)), 4):
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                print('  DTP %d +%#06x X %s (u32 %d s16 %d,%d f %.6g)  PC %s (u32 %d f %.6g)  %s%s' % (
                    s['id'], o, xw.hex(), struct.unpack('>I', xw)[0], *struct.unpack('>hh', xw), struct.unpack('>f', xw)[0],
                    pw.hex(), struct.unpack('<I', pw)[0], struct.unpack('<f', pw)[0], cls(xw, pw),
                    ' PTR' if o in sl else ' ID' if o in il else ''))
        fl, cnt = audit_pair(s, p)
        for f in fl: tot[f[0]] += 1
        tot['words'] += sum(cnt.values())
        if fl and (show_all or (want and s['id'] in want) or not want):
            byk = collections.Counter(f[0] for f in fl)
            print('DTP %d (PC %d, %d bytes): %s' % (s['id'], p['id'], len(s['data']), dict(byk)))
            if show_all or (want and s['id'] in want):
                for k, o, xw, pw, c, txt in fl:
                    print('   %-7s +%#06x X %s PC %s (%s) %s' % (k, o, xw.hex(), pw.hex(), c, txt))
    print('total', dict(tot), 'unpaired Xbox DTPs', unp)


def source(prof, names):
    P = json.load(open(prof, encoding='utf-8-sig'))
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    game = os.path.join(root, 'data', 'pc', 'mods')
    for n in names:
        last = None
        for t in P.get('trees', []):
            md = t.get('md5', {})
            if n in md: last = (t['source'], md[n])
        ip = os.path.join(game, n)
        im = hashlib.md5(open(ip, 'rb').read()).hexdigest() if os.path.exists(ip) else None
        print('%-40s last tree %s md5 %s | installed md5 %s %s' % (
            n, last[0] if last else '-', last[1] if last else '-', im, '' if not last else ('SAME' if last[1] == im else 'DIFF')))


def xcmp(a, b, spec):
    xa, _ = load_x(a); xb, _ = load_x(b)
    q = spec.split(':'); ia, ib = int(q[0]), int(q[1])
    lo = int(q[2], 16) if len(q) > 2 else 0; hi = int(q[3], 16) if len(q) > 3 else 1 << 30
    sa = [s for s in xa if s['type'] == 7 and s['id'] == ia][0]; sb = [s for s in xb if s['type'] == 7 and s['id'] == ib][0]
    print('sizes', len(sa['data']), len(sb['data']))
    nd = 0
    for o in range(lo, min(hi, len(sa['data']), len(sb['data'])) // 4 * 4, 4):
        wa, wb = sa['data'][o:o + 4], sb['data'][o:o + 4]
        if wa != wb:
            nd += 1
            print('  +%#06x A %s (u32 %d f %.6g)  B %s (u32 %d f %.6g)' % (o, wa.hex(), struct.unpack('>I', wa)[0],
                  struct.unpack('>f', wa)[0], wb.hex(), struct.unpack('>I', wb)[0], struct.unpack('>f', wb)[0]))
    print('differing words', nd)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'audit':
        rng = None
        if '--range' in a:
            k = a.index('--range'); r = a[k + 1].split(':'); rng = (int(r[0]), int(r[1], 16), int(r[2], 16)); del a[k:k + 2]
        sa = '--all' in a; a = [x for x in a if x != '--all']
        want = set(int(v) for v in a[3].split(',')) if len(a) > 3 else None
        audit(a[1], a[2], want, sa, rng)
    elif a[0] == 'source': source(a[1], a[2:])
    elif a[0] == 'xcmp': xcmp(a[1], a[2], a[3])
    elif a[0] == 'pcmp':
        # pcmp PC_A.drm PC_B.drm DTP: two PC files, one type-7 section, every differing word (LE values)
        sa = [s for s in load_p(a[1]) if s['type'] == 7 and s['id'] == int(a[3])][0]
        sb = [s for s in load_p(a[2]) if s['type'] == 7 and s['id'] == int(a[3])][0]
        for o in range(0, min(len(sa['data']), len(sb['data'])) // 4 * 4, 4):
            wa, wb = sa['data'][o:o + 4], sb['data'][o:o + 4]
            if wa != wb:
                print('  +%#06x A %s (u32 %d f %.6g)  B %s (u32 %d f %.6g)' % (o, wa.hex(), struct.unpack('<I', wa)[0],
                      struct.unpack('<f', wa)[0], wb.hex(), struct.unpack('<I', wb)[0], struct.unpack('<f', wb)[0]))
    else: sys.exit(__doc__)
