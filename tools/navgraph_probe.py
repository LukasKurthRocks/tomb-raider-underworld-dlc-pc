"""Look at the NavPower NavGraph image of a unit DRM (read-only; debug view research 2026-11-05, workspace
docs\\Befund-Debug-Ansicht-0511.md). The image is the block the PC hands to NavPower's AddResource: Level+0x60 ->
first dword 0xffffffff, image = +4 (tru+0x48c42f `cmp dword [eax], -1` ... `add eax, 4; push eax; call 0x42e990`).
The format is BabelFlux NavPower's own binary layout and is NOT known; this tool only shows words and searches for
runs of float triples that lie inside the unit's own bounding box (intro / terrain range), as a lead for decoding.
Nothing it prints is a parsed navmesh.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/navgraph_probe.py UNIT.drm [--words N] [--runs MIN] [--le|--be]
  ../bin/pyt -t 600 tools/navgraph_probe.py --compare PC_UNIT.drm UNITNAME [pack11]
     word-by-word class of the PC image against the Xbox original read from the DLC pack (read-only);
     PC_UNIT.drm may be `pcbig:` (PC side read from the PC archive) and the pack `xbase` / `xbase2` for base pairs
     --words N  print the first N words of the image (default 96) as hex / int / float
     --runs MIN print runs of >= MIN consecutive 12-byte float triples inside the box (default 6)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R
import unit_ids as U


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def image_of(path_or_bytes, e):
    """(sections, (section index, offset)) of the Level+0x60 image of a unit DRM"""
    raw = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, 'rb').read()
    D = DW.read(raw, e)
    r0 = R.parse(bytes(D.sections[0].reloc), e)
    ext = {so: (si, do) for si, so, do in r0.external}
    return D, ext.get(0x60) or ((0, dict(r0.internal)[0x60]) if 0x60 in dict(r0.internal) else None)


def compare(argv):
    """--compare PC.drm UNITNAME [pack]: the PC image against the Xbox original from the DLC pack (tools/locals.SRC)"""
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode
    pc, unit = argv[0], argv[1]
    pack = argv[2] if len(argv) > 2 else 'pack11'
    path, e, pre = LC.SRC[pack]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + unit + '.drm'))
    if not recs:
        print('%s not in %s' % (unit, pack)); return 1
    xraw = cdrm_decode(A.read(recs[-1]), 'be')
    XD, xt = image_of(xraw, 'be')
    if pc.endswith(':'):            # e.g. pcbig: = read the PC side from that archive (base-game pair proof)
        ppath, pe, ppre = LC.SRC[pc[:-1]]
        PA = Archive(ppath, pe)
        precs = PA.find(crc(ppre + '\\' + unit + '.drm'))
        if not precs:
            print('%s not in %s' % (unit, pc)); return 1
        pc = cdrm_decode(PA.read(precs[-1]), 'le')
    PD, pt = image_of(pc, 'le')
    if xt is None or pt is None:
        print('%s: no Level+0x60 image (Xbox %s, PC %s) - not a unit with a NavGraph' % (unit, xt, pt)); return 0
    xd = bytes(XD.sections[xt[0]].data)[xt[1]:]
    pd = bytes(PD.sections[pt[0]].data)[pt[1]:]
    print('Xbox %s/%s image: section %d +0x%x, %d bytes; PC: section %d +0x%x, %d bytes' % (
        pack, unit, xt[0], xt[1], len(xd), pt[0], pt[1], len(pd)))
    n = min(len(xd), len(pd)) // 4
    end = struct.unpack_from('<I', pd, 0x30)[0] if len(pd) >= 0x34 else n * 4
    cls = {}
    sites = {}
    for k in range(n):
        xw = xd[4 * k:4 * k + 4]
        pw = pd[4 * k:4 * k + 4]
        # order: identical first (palindromic words such as ffff7f7f count as identical)
        if pw == xw: c = 'raw (identical)'
        elif pw == xw[::-1]: c = 'u32 swap'
        elif pw == xw[1::-1] + xw[3:1:-1]: c = 'u16-pair swap'
        elif pw == xw[2:4] + xw[0:2]: c = 'halves exchanged, bytes kept'
        else: c = 'other'
        part = 'area block' if 4 * k < end else 'after area block'
        cls[(part, c)] = cls.get((part, c), 0) + 1
        sites.setdefault((part, c), []).append(4 * k)
    for (part, c), v in sorted(cls.items()):
        s = sites.get((part, c), [])
        print('  %-17s %-36s %6d  %s' % (part, c, v, ' '.join('+0x%x:%s>%s' % (
            o, xd[o:o + 4].hex(), pd[o:o + 4].hex()) for o in s[:6])))
    zero = [o for o in sites.get(('area block', 'u16-pair swap'), []) if xd[o + 2:o + 4] == b'\0\0' and xd[o:o + 2] != b'\0\0']
    print('  area block words converted as u16 pairs whose Xbox low half is 0 (a float like 1200.0 = 44960000): %d'
          % len(zero))
    return 0


def main(argv):
    if '--compare' in argv:
        argv.remove('--compare')
        return compare(argv)
    nw = int(opt(argv, '--words', '96'))
    mn = int(opt(argv, '--runs', '6'))
    e = 'be' if '--be' in argv else 'le'
    E = '>' if e == 'be' else '<'
    argv = [a for a in argv if a not in ('--le', '--be')]
    if not argv:
        print(__doc__); return 2
    D = DW.read(open(argv[0], 'rb').read(), e)
    secs = [dict(type=s.type, data=bytes(s.data), reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, e)
    if L is None:
        print('not a unit DRM'); return 1
    r0 = R.parse(bytes(D.sections[0].reloc), e)
    ext = {so: (si, do) for si, so, do in r0.external}
    intl = dict(r0.internal)
    xs = [struct.unpack_from(E + '3f', secs[si]['data'], o + 0x10) for si, o in L['intros']]
    lo = [min(p[i] for p in xs) - 3000 for i in range(3)]
    hi = [max(p[i] for p in xs) + 3000 for i in range(3)]
    print('intro box (data frame, +-3000): %s .. %s' % (' '.join('%.0f' % v for v in lo), ' '.join('%.0f' % v for v in hi)))
    for fld in (0x60, 0x68):
        t = ext.get(fld) or ((0, intl[fld]) if fld in intl else None)
        if t is None:
            print('Level+0x%02x: no pointer' % fld); continue
        si, o = t
        d = secs[si]['data']
        print('Level+0x%02x -> section %d +0x%x (section size %d, relocations %s)' % (
            fld, si, o, len(d), R.parse(bytes(D.sections[si].reloc), e)))
        for k in range(min(nw, (len(d) - o) // 4)):
            w = struct.unpack_from(E + 'I', d, o + 4 * k)[0]
            f = struct.unpack_from(E + 'f', d, o + 4 * k)[0]
            print('  +%05x  %08x  %11d  %s' % (4 * k, w, w if w < 0x80000000 else w - 0x100000000,
                                                ('%.3f' % f) if 1e-3 < abs(f) < 1e6 else ''))
        if fld != 0x60: continue
        runs = []
        for start in range(o, o + 12):
            k = start
            while k + 12 <= len(d):
                n = 0
                while k + 12 * (n + 1) <= len(d):
                    p = struct.unpack_from(E + '3f', d, k + 12 * n)
                    if all(lo[i] <= p[i] <= hi[i] and abs(p[i]) > 1e-3 for i in range(3)): n += 1
                    else: break
                if n >= mn: runs.append((k, n)); k += 12 * n
                else: k += 12
        seen = set()
        for k, n in sorted(runs):
            if any(k <= s < k + 12 * n for s in seen): continue
            seen.add(k)
            ps = [struct.unpack_from(E + '3f', d, k + 12 * i) for i in range(n)]
            print('  float-triple run at image +0x%x (%d): first (%.1f %.1f %.1f) last (%.1f %.1f %.1f)' % (
                k - o, n, *ps[0], *ps[-1]))
        for stride in (16,):
            k = o; best = []
            while k + stride <= len(d):
                n = 0
                while k + stride * (n + 1) <= len(d):
                    p = struct.unpack_from(E + '3f', d, k + stride * n)
                    if all(lo[i] <= p[i] <= hi[i] and abs(p[i]) > 1e-3 for i in range(3)): n += 1
                    else: break
                if n >= mn: best.append((k, n)); k += stride * n
                else: k += 4
            for k, n in best:
                p0 = struct.unpack_from(E + '3f', d, k); p1 = struct.unpack_from(E + '3f', d, k + stride * (n - 1))
                print('  vec4-stride run at image +0x%x (%d): first (%.1f %.1f %.1f) last (%.1f %.1f %.1f)' % (
                    k - o, n, *p0, *p1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
