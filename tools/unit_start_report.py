"""Start position of a unit load (test questions 2026-11-05: 'level.load dlc_yggdrasil_hall02 put Lara into
dlc_yggdrasil_end'), read-only.

For each unit DRM: its stream portals (StreamUnitPortal records, tools/unit_ids.level_info; destination unit name,
the plane through the portal points) and every intro (object name from the DLC object list, unique id, data position,
the raw u16 / u32 words of the 0x90-byte record that are not position floats), with the side of each portal plane the
intro lies on (+ = side of the plane normal). Names matching --grep (default: checkpoint|start|save|trigger|wall|
portal|marker|lara|player|break|spawn) are printed; --all prints every intro.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/unit_start_report.py UNIT.drm [UNIT.drm ...] [--all] [--grep REGEX]
"""
import sys, os, struct, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unit_ids as U
import shader_tour as ST

DEF = r'checkpoint|start|save|trigger|wall|portal|marker|lara|player|break|spawn|stone|door|block'


def portal_planes(secs, L):
    out = []
    for si, o in L['portals']:
        d = secs[si]['data']
        name = d[o:o + 0x80].split(b'\0', 1)[0].decode('latin-1')
        # layout read from `unit_frames.py dump`: 6 points {x, y, z, 0} at +0x90 (stride 0x10), unit normal at +0xf0
        pts = [struct.unpack_from('<3f', d, o + 0x90 + 0x10 * k) for k in range(6)]
        n = struct.unpack_from('<3f', d, o + 0xf0)
        c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        own, dest = struct.unpack_from('<HH', d, o + 0x82)
        out.append(dict(name=name, centre=c, normal=n, pts=pts, own=own, dest=dest))
    return out


def side(p, pl):
    return sum((p[i] - pl['centre'][i]) * pl['normal'][i] for i in range(3))


def main(argv):
    show_all = '--all' in argv; argv = [a for a in argv if a != '--all']
    rx = DEF
    if '--grep' in argv:
        k = argv.index('--grep'); rx = argv[k + 1]; del argv[k:k + 2]
    names = ST.objnames()
    for path in argv:
        D = ST.load(path); secs = ST.secdicts(D); L = U.level_info(secs, 'le')
        if L is None: print(path, 'not a unit'); continue
        pls = portal_planes(secs, L)
        print('== %s: %d portals, %d intros' % (os.path.basename(path), len(pls), len(L['intros'])))
        for pl in pls:
            print('   portal -> %-28s own %d dest-unit %d centre (%.0f %.0f %.0f) normal (%.0f %.0f %.0f)' % (
                pl['name'], pl['own'], pl['dest'], *pl['centre'], *pl['normal']))
        cnt = collections.Counter()
        for (si, o), it in zip(L['intros'], ST.intro_list(secs, L, names)):
            cnt[it['name']] += 1
            if not show_all and not re.search(rx, it['name'], re.I): continue
            d = secs[si]['data']
            sides = ' '.join('%s%s' % ('+' if side(it['pos'], pl) >= 0 else '-', pl['name'].replace('dlc_yggdrasil_', ''))
                             for pl in pls)
            extra = struct.unpack_from('<4H', d, o + 0x50)
            tail = struct.unpack_from('<8I', d, o + 0x70)
            print('   intro %6d obj %4d %-34s pos (%8.1f %8.1f %8.1f) [%s] +0x50 %s +0x70 %s' % (
                it['uid'], it['obj'], it['name'], *it['pos'], sides, extra, ' '.join('%x' % t for t in tail)))
        print('   objects:', ', '.join('%s %d' % kv for kv in sorted(cnt.items())))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
