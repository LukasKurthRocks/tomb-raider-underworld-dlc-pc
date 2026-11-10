"""List the intros (placed object instances) of a unit DRM with object name, unique id, position and the +0x7c word,
for the Xbox DLC original and a PC file side by side (read-only; N15 / package E 2026-11-09: which thralls are placed
in dlc_yggdrasil_end, and does the PC copy differ from the Xbox one).

Intro records and the unit DTP are read by work/endb270_0811/unit_dtp.py (unit(), intros()); object names: PC ids from
work/generic/merged/tr8/pc-w/objectlist.txt ("id,name"). Position = the three floats at intro +0x10 (assumed layout
{rotation vec4 +0x00, position vec4 +0x10}; printed as read).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/unit_intro_names.py REL PC.drm [--match TEXT]
    REL = DLC unit name (e.g. dlc_yggdrasil_end.drm, read from pack11 like unit_dtp 'dlcx'); PC.drm = installed or
    tree copy. Prints per intro: index, PC object id + name, uid, PC position, and 'DIFF' when the Xbox position
    (byte-swapped floats) differs by more than 0.5 units or the +0x7c word differs in value.
    --rec / --data: the 0x90-byte intro record / the intro data block word by word (Xbox, PC, byte-order class).
    --live: also print the live (in-game) position = data position - Level+0x80 (ENGINE.md 4.3; Level+0x80 read from
    section 0 of the PC file; valid when the unit is Lara's own unit, P = 0) - the frame TruMenu / TruFight.log use.
    --near X,Y,Z[,R]: only intros whose live position is within R (default 2000) units of the live point X, Y, Z,
    sorted by distance (implies --live; 2026-11-10 goo drip deaths).
"""
import sys, os, struct
os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'work', 'endb270_0811'))
import unit_dtp as UD

NAMES = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def names():
    out = {}
    for ln in open(NAMES, encoding='utf-8', errors='replace'):
        ln = ln.strip()
        if ',' in ln:
            i, n = ln.split(',', 1)
            if i.isdigit():
                out[int(i)] = n
    return out


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    rel, pcf = a[0], a[1]
    match = a[a.index('--match') + 1].lower() if '--match' in a else None
    nm = names()
    dx, ex = UD.load('dlcx', rel)
    dp = open(pcf, 'rb').read()
    _, ux, px = UD.unit(dx, ex)
    _, up, pp = UD.unit(dp, 'le')
    IX, IP = UD.intros(ux, px, 'be'), UD.intros(up, pp, 'le')
    print('%s: Xbox %d intros, PC %d intros' % (rel, len(IX), len(IP)))
    near = [float(v) for v in a[a.index('--near') + 1].split(',')] if '--near' in a else None
    live = '--live' in a or near is not None
    off = (0.0, 0.0, 0.0)
    if live:
        import drm
        S = drm.sections_with_data(drm.cdrm_decode(dp, 'le'), 'le')[1]
        off = struct.unpack_from('<3f', S[0]['data'], 0x80)
        print('Level+0x80 = %.1f %.1f %.1f -> live = data - Level+0x80' % off)
    rows = []
    for x, p in zip(IX, IP):
        n = nm.get(p['obj'], '?')
        if match and match not in n.lower():
            continue
        posp = struct.unpack_from('<3f', up['data'], p['o'] + 0x10)
        lv = tuple(posp[i] - off[i] for i in range(3))
        dist = None
        if near is not None:
            dist = sum((lv[i] - near[i]) ** 2 for i in range(3)) ** 0.5
            if dist > (near[3] if len(near) > 3 else 2000.0):
                continue
        rows.append((dist if dist is not None else 0.0, x, p, n, posp, lv))
    if near is not None:
        rows.sort(key=lambda r: r[0])
    for dist, x, p, n, posp, lv in rows:
        posx = struct.unpack_from('>3f', ux['data'], x['o'] + 0x10)
        w7p = struct.unpack_from('<I', up['data'], p['o'] + 0x7c)[0]
        w7x = struct.unpack_from('>I', ux['data'], x['o'] + 0x7c)[0]
        d = max(abs(u - v) for u, v in zip(posp, posx))
        flag = ' DIFF' if (d > 0.5 or w7p != w7x or x['uid'] != p['uid']) else ''
        extra = (' live %9.1f %9.1f %9.1f' % lv if live else '') + (' dist %7.1f' % dist if near is not None else '')
        print('%3d obj %5d %-44s uid %6d pos %9.1f %9.1f %9.1f +0x7c %08x%s%s' % (
            p['k'], p['obj'], n[:44], p['uid'], posp[0], posp[1], posp[2], w7p, extra, flag))
        if '--rec' in a:
            # the 0x90-byte intro record itself, word by word
            for w in range(0, 0x90, 4):
                xb = ux['data'][x['o'] + w:x['o'] + w + 4]
                pb = up['data'][p['o'] + w:p['o'] + w + 4]
                c = ('same' if xb == pb else 'u32' if xb[::-1] == pb else
                     'u16x2' if xb[1::-1] + xb[3:1:-1] == pb else 'other')
                print('      rec +%#04x X %s P %s %s%s' % (w, xb.hex(), pb.hex(), c, ' ptr' if (p['o'] + w) in pp else ''))
        if '--data' in a and x['dp'] is not None and p['dp'] is not None:
            # intro data block word by word: Xbox word, PC word, class (same / u32 / u16x2 / raw / other)
            xd = ux['data'][x['dp']:x['dp'] + x['dsz']]
            pd = up['data'][p['dp']:p['dp'] + p['dsz']]
            print('      data Xbox %#x B, PC %#x B' % (len(xd), len(pd)))
            for w in range(0, min(len(xd), len(pd)) - 3, 4):
                xb, pb = xd[w:w + 4], pd[w:w + 4]
                c = ('same' if xb == pb else 'u32' if xb[::-1] == pb else
                     'u16x2' if xb[1::-1] + xb[3:1:-1] == pb else 'raw?' if xb == pb else 'other')
                ptr = ' ptr' if (p['dp'] + w) in pp else ''
                print('      +%#05x X %s P %s %s%s' % (w, xb.hex(), pb.hex(), c, ptr))
    return 0


if __name__ == '__main__':
    sys.exit(main())
