"""Classify the Xbox -> PC conversion of one DTP section word by word (read-only; finding 43, rock vein: the DLC 2
player state chart in doppelganger_casual.drm DTP 20212).

For every 4-byte word: '16' (two u16 swapped), '32' (u32 swapped), '=' (bytes unchanged), 'amb' (several modes give
the same bytes, e.g. 0 or a palindrome), '?' (changed otherwise: id remap, relocation, re-authored).
Then the same split only for "u16-pair-like" Xbox words (both BE halves non-zero and < 0x1000, the shape of the state
chart's {id, kind} / {id, id} records), and the offsets of the first runs where such words were NOT u16-swapped.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_conv_modes.py XBOX.drm PC.drm SECTION_ID [PC_SECTION_ID] [--list N]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def section(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return bytes(s.data)
    raise SystemExit('DTP %d not in %s' % (sid, path))


def mode(x, p):
    m16 = x[1::-1] + x[3:1:-1]; m32 = x[::-1]
    hits = [n for n, v in (('16', m16), ('32', m32), ('=', x)) if v == p]
    if len(hits) > 1: return 'amb'
    return hits[0] if hits else '?'


def main(argv):
    n_list = 20
    if '--list' in argv: k = argv.index('--list'); n_list = int(argv[k + 1]); del argv[k:k + 2]
    xs = section(argv[0], 'be', int(argv[1 + 1]))
    ps = section(argv[1], 'le', int(argv[3]) if len(argv) > 3 else int(argv[2]))
    print('sizes xbox 0x%x pc 0x%x' % (len(xs), len(ps)))
    n = min(len(xs), len(ps)) // 4
    allc = collections.Counter(); pairc = collections.Counter(); bad = []
    for k in range(n):
        x, p = xs[4 * k:4 * k + 4], ps[4 * k:4 * k + 4]
        m = mode(x, p); allc[m] += 1
        a, b = struct.unpack('>HH', x)
        if 0 < a < 0x1000 and 0 < b < 0x1000:
            pairc[m] += 1
            if m != '16': bad.append((4 * k, a, b, m))
    print('all words  : ' + ', '.join('%s %d' % kv for kv in allc.most_common()))
    print('u16-pair-like words: ' + ', '.join('%s %d' % kv for kv in pairc.most_common()))
    for o, a, b, m in bad[:n_list]:
        print('  +0x%05x  xbox u16 %5d %5d  -> %s' % (o, a, b, m))
    if bad:
        print('  ... %d such words, offsets 0x%x .. 0x%x' % (len(bad), bad[0][0], bad[-1][0]))


if __name__ == '__main__':
    main(sys.argv[1:])
