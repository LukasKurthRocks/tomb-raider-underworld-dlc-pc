"""Find runs of 0x5c-byte markup records in the sections of a DRM without relying on a (count, pointer) pair, and
compare the type chars Xbox vs PC (read-only; finding 43, rock vein: are the markup types 22 / 23 in the level data and
do they survive the conversion?).

Record (PC loader tru+0x1ce4f0): +0x28 runtime dword (0 in the file), +0x2e s16 markup id, +0x33 type char,
+0x58 segment pointer (may be null). A run = >= MIN consecutive records with +0x28 == 0, 0 <= id < 0x4000 and a type
char 1..63.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/markup_runs.py XBOX.drm PC.drm [--min N] [--list]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

STRIDE = 0x5c
NEED28 = True                           # --any28: do not require +0x28 == 0


def ok(d, r, f):
    if r + STRIDE > len(d): return False
    if NEED28 and struct.unpack_from(f + "I", d, r + 0x28)[0] != 0: return False
    i = struct.unpack_from(f + 'h', d, r + 0x2e)[0]
    return 0 <= i < 0x4000 and 1 <= d[r + 0x33] <= 63


def runs(d, f, mn):
    out = []
    o = 0
    while o + STRIDE <= len(d):
        n = 0
        while ok(d, o + n * STRIDE, f): n += 1
        if n >= mn:
            out.append((o, n)); o += n * STRIDE
        else:
            o += 4
    return out


def main(argv):
    global NEED28
    mn = 5; lst = '--list' in argv
    if '--any28' in argv: NEED28 = False; argv = [a for a in argv if a != '--any28']
    argv = [a for a in argv if a != '--list']
    if '--min' in argv: k = argv.index('--min'); mn = int(argv[k + 1]); del argv[k:k + 2]
    X = DW.read(open(argv[0], 'rb').read(), 'be'); P = DW.read(open(argv[1], 'rb').read(), 'le')
    for si, (xs, ps) in enumerate(zip(X.sections, P.sections)):
        if xs.type in (5, 6, 9, 10, 12): continue
        xd, pd = bytes(xs.data), bytes(ps.data)
        for o, n in runs(xd, '>', mn):
            xt = collections.Counter(xd[o + k * STRIDE + 0x33] for k in range(n))
            same = sum(1 for k in range(n) if len(pd) >= o + (k + 1) * STRIDE and pd[o + k * STRIDE + 0x33] == xd[o + k * STRIDE + 0x33]
                       and struct.unpack_from('<h', pd, o + k * STRIDE + 0x2e)[0] == struct.unpack_from('>h', xd, o + k * STRIDE + 0x2e)[0])
            print('section %d type %d id %d +0x%x: %d records, types %s; PC same type+id: %d' % (
                si, xs.type, xs.id, o, n, ' '.join('%d:%d' % kv for kv in sorted(xt.items())), same))
            if lst:
                for k in range(n):
                    r = o + k * STRIDE
                    print('    #%d id %d type %d  pc id %d type %d' % (k, struct.unpack_from('>h', xd, r + 0x2e)[0], xd[r + 0x33],
                          struct.unpack_from('<h', pd, r + 0x2e)[0] if len(pd) >= r + STRIDE else -1,
                          pd[r + 0x33] if len(pd) >= r + STRIDE else -1))


if __name__ == '__main__':
    main(sys.argv[1:])
