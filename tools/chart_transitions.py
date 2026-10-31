"""List the transitions of a converted (little-endian) player state chart DTP with their condition records
(read-only; finding 43, rock vein: which transitions lead to the title-update states and which test markup 607 / 608).

Transition = 20-byte block {u16 target state, u16, u16 count, u16, ptr conditions, ptr, u32} (layout proven by
tools/shape_proof.py on lara.drm 12647 / 850); its condition list = `count` records {u16 key, u16 id, u16 value, u8
flags, u8} at the first pointer.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_transitions.py PC.drm SID [--target ID[,ID..]] [--value V[,V..]] [--holders]
  --holders  also print the pointer lists / blocks that point at each listed transition (who owns it)
"""
import sys, os, struct, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    holders = '--holders' in argv; argv = [a for a in argv if a != '--holders']
    tg = vals = None
    if '--target' in argv: k = argv.index('--target'); tg = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--value' in argv: k = argv.index('--value'); vals = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    s = [q for q in D.sections if q.id == int(argv[1]) and q.type == 7][0]
    d = bytes(s.data); it = dict(R.parse(bytes(s.reloc), 'le').internal)
    t = sorted(set(it.values()) | {0})
    ptrs_in = collections.defaultdict(list)
    for o, x in it.items(): ptrs_in[x].append(o)
    n = 0
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(d)
        if end - a != 0x14 or (a + 8) not in it or (a + 0xc) not in it: continue
        target, w1, cnt, w3 = struct.unpack_from('<4H', d, a)
        c0 = it[a + 8]
        conds = []
        for j in range(min(cnt, 16)):
            if c0 + 8 * j + 8 > len(d): break
            ky, i, v = struct.unpack_from('<3H', d, c0 + 8 * j); fl = d[c0 + 8 * j + 6]
            conds.append((ky, i, v, fl))
        if tg and target not in tg: continue
        if vals and not any(c[2] in vals and c[1] in (610, 611, 612, 613) for c in conds): continue
        n += 1
        print('+0x%05x -> state %5d  (%d, count %d, %d)  conds @+0x%x: %s' % (a, target, w1, cnt, w3, c0, ' '.join(
            '{%d,%d,%d%s}' % (c[0], c[1], c[2], ',NOT' if c[3] & 1 else '') for c in conds)))
        if holders:
            for p in ptrs_in.get(a, ()):
                kb = bisect.bisect_right(t, p) - 1
                print('      held by +0x%05x (block +0x%x, slot %d)' % (p, t[kb], (p - t[kb]) // 4))
    print('%d transitions listed' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
