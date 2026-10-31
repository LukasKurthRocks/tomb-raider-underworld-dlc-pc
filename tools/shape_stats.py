"""Which block shapes of a converted DTP still hold suspicious words (read-only; finding 43, rock vein state chart).

Suspicious = the Xbox word looks like two small u16 (both halves 1..0xfff) but the PC word is not their u16-swapped
form (u32-swapped or raw). Grouped by block shape (size, pointer offsets) with the block count and the word offsets.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/shape_stats.py XBOX.drm PC.drm SID [--top N]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shape_proof import load
import bisect


def main(argv):
    top = 25
    if '--top' in argv: k = argv.index('--top'); top = int(argv[k + 1]); del argv[k:k + 2]
    _, _, xd, xi, xp = load(argv[0], 'be', int(argv[2]))
    _, _, pd, _, pp = load(argv[1], 'le', int(argv[2]))
    t = sorted(set(xi.values()) | {0})
    byb = collections.defaultdict(list)
    for o in xi:
        k = bisect.bisect_right(t, o) - 1
        byb[t[k]].append(o - t[k])
    if '--at' in argv:                          # shape of the block that starts at / contains OFFSET
        o = int(argv[argv.index('--at') + 1], 16)
        k = bisect.bisect_right(t, o) - 1; a = t[k]; end = t[k + 1] if k + 1 < len(t) else len(xd)
        print('block +0x%x size 0x%x ptrs %s' % (a, end - a, ','.join('%x' % f for f in sorted(byb.get(a, ())))))
        return
    count = collections.Counter(); sus = collections.Counter(); offs = collections.defaultdict(collections.Counter)
    total = 0; first = {}
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(xd)
        S = (end - a, tuple(sorted(byb.get(a, ()))))
        count[S] += 1
        for o in range(a, end - 3, 4):
            if o in xp or o in pp: continue
            x = xd[o:o + 4]; p = pd[o:o + 4]
            h1, h2 = struct.unpack('>HH', x)
            if 0 < h1 < 0x1000 and 0 < h2 < 0x1000 and p != x[1::-1] + x[3:1:-1]:
                sus[S] += 1; offs[S][o - a] += 1; total += 1; first.setdefault(S, []).append(o)
    print('%d suspicious words in %d shapes' % (total, len(sus)))
    for S, n in sus.most_common(top):
        print('  size 0x%-5x ptrs %-24s blocks %5d  suspicious %5d  at %s' % (S[0], ','.join('%x' % f for f in S[1])[:24],
              count[S], n, ' '.join('+%x:%d' % kv for kv in offs[S].most_common(6))))
        print('      e.g. ' + ' '.join('0x%x' % o for o in first[S][:8]))


if __name__ == '__main__':
    main(sys.argv[1:])
