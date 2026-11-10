"""Find the unknown root folder of an archive's file names (read-only): the archive name hash is CRC-32
(poly 0x04C11DB7, MSB first, lower-cased, tools/names.crc). Given a record hash and the known rest of its path
(e.g. `\\audio\\streams\\vo\\kraken\\x.mul`), the CRC state before that rest is computed backwards, and prefixes of
1..8 characters from [a-z0-9-_.] that reach it are found by meet-in-the-middle (forward half <= 4, backward
half <= 4). Built when a second retail PC build named its files under another root than `pc-w`.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/hash_prefix_probe.py HASH_HEX SUFFIX [HASH_HEX SUFFIX ...] [--max-len N]
      every pair must share the prefix; prints prefixes that fit all pairs (default --max-len 7)
"""
import sys, itertools

POLY = 0x04C11DB7
T = []
for i in range(256):
    h = i << 24
    for _ in range(8):
        h = ((h << 1) ^ POLY) & 0xffffffff if h & 0x80000000 else (h << 1) & 0xffffffff
    T.append(h)
LOW = {t & 0xff: i for i, t in enumerate(T)}      # h' = (h << 8) ^ T[i]: the low byte of h' names i
assert len(LOW) == 256
CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789-_.'


def fwd(h, s):
    for c in s.lower():
        h = ((h << 8) & 0xffffffff) ^ T[((h >> 24) ^ ord(c)) & 0xff]
    return h


def back(h, s):
    for c in reversed(s.lower()):
        i = LOW[h & 0xff]
        h = (((h ^ T[i]) >> 8) & 0xffffff) | ((i ^ ord(c)) << 24)
    return h


FW = {}


def fw_table(a):
    if a not in FW:
        d = {}
        for p in itertools.product(CHARS, repeat=a):
            p = ''.join(p); d.setdefault(fwd(0xffffffff, p), []).append(p)
        FW[a] = d
    return FW[a]


def solve(target_state, max_len):
    out = set()
    for total in range(1, max_len + 1):
        a = min(4, total); b = total - a
        if b > 4: continue
        fw = fw_table(a)
        for q in itertools.product(CHARS, repeat=b):
            q = ''.join(q)
            for p in fw.get(back(target_state, q), []): out.add(p + q)
    return out


def main(argv):
    ml = 7
    if '--max-len' in argv: k = argv.index('--max-len'); ml = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) < 2 or len(argv) % 2: sys.exit(__doc__)
    pairs = [(int(argv[i], 16), argv[i + 1]) for i in range(0, len(argv), 2)]
    common = None
    for h, suf in pairs:
        st = back(~h & 0xffffffff, suf)
        sols = solve(st, ml)
        print('%08x %s: %d prefixes' % (h, suf, len(sols)))
        common = sols if common is None else common & sols
    print('prefixes fitting all pairs: %s' % (', '.join(sorted(common, key=len)[:40]) or '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
