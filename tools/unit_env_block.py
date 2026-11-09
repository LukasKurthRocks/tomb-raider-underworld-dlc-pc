"""Environment block of a unit (Level+0x70 -> DTP, ENGINE.md "Fog / underwater": underwater colour +0x1c.., distances
+0x44 / +0x48 / +0x4c, LUT ids +0x84 / +0x88, ambience +0x68 / +0x6c) word by word: Xbox DLC original vs one or more
PC files (read-only; N15 / package E 2026-11-09, X14 "blue haze" in dlc_yggdrasil_end on the Xbox).

Sections / relocations: tools/drm.py, tools/drm_reloc.py; Xbox DLC raw: convert_dlc.raw_dlc (pack11), as
work/endb270_0811/unit_dtp.py does.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/unit_env_block.py REL PC.drm [PC2.drm ...] [--len 0x200]
    prints per word: offset, Xbox word (BE), Xbox as float, then per PC file the word (LE) as hex / float and a
    class (same value / OTHER); pointer words (internal / external relocation in the block) are marked.
    Exit 0 = all PC files equal the Xbox values, 1 = differences.
"""
import sys, os, struct
os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm, drm_reloc as R
from convert_dlc import raw_dlc


def env(d, e):
    S = drm.sections_with_data(drm.cdrm_decode(d, e), e)[1]
    lv = S[0]
    r = R.parse(lv['reloc'], e)
    hit = [(si, dd) for si, s, dd in r.external if s == 0x70]
    if not hit:
        raise SystemExit('Level+0x70 has no external relocation')
    si, dd = hit[0]
    sec = S[si]
    sr = R.parse(sec['reloc'], e)
    ptrs = set(o for o, t in sr.internal) | set(s for _, s, _ in sr.external)
    return sec, dd, ptrs


def main():
    a = sys.argv[1:]
    n = int(a[a.index('--len') + 1], 16) if '--len' in a else 0x100
    a = [x for i, x in enumerate(a) if x != '--len' and (i == 0 or a[i - 1] != '--len')]
    if len(a) < 2:
        print(__doc__)
        return 2
    rel, pcs = a[0], a[1:]
    sides = []
    if pcs == ['BASE']:
        # base-game pair (Xbox layer1 / layer2 vs PC bigfile) through work/endb270_0811/unit_dtp.load
        sys.path.insert(0, os.path.join(HERE, '..', 'work', 'endb270_0811'))
        import unit_dtp as UD
        xd = UD.load('xbox', rel)[0]
        s, o, p = env(UD.load('pc', rel)[0], 'le')
        sides.append(('pc-base', s, o, p))
    else:
        xd = raw_dlc(rel)[0]
        for f in pcs:
            s, o, p = env(open(f, 'rb').read(), 'le')
            sides.append((os.path.basename(os.path.dirname(os.path.dirname(f))) or f, s, o, p))
    xs, xo, xp = env(xd, 'be')
    print('%s: Xbox env DTP id %s at +%#x (size %#x); PC: %s' % (rel, xs.get('id'), xo, xs['size'],
          ', '.join('%s id %s +%#x' % (t, s.get('id'), o) for t, s, o, p in sides)))
    diff = 0
    for w in range(0, min(n, xs['size'] - xo), 4):
        xw = xs['data'][xo + w:xo + w + 4]
        xv = struct.unpack('>I', xw)[0]
        xf = struct.unpack('>f', xw)[0]
        cols = []
        for t, s, o, p in sides:
            pw = s['data'][o + w:o + w + 4]
            pv = struct.unpack('<I', pw)[0]
            ok = 'same' if pv == xv else 'OTHER'
            if ok != 'same' and (o + w) not in p:
                diff += 1
            cols.append('%08x %s%s' % (pv, ok, ' ptr' if (o + w) in p else ''))
        print('+%#05x X %08x (%11.4g)  %s' % (w, xv, xf, '  |  '.join(cols)))
    print('differing non-pointer words: %d' % diff)
    return 1 if diff else 0


if __name__ == '__main__':
    sys.exit(main())
