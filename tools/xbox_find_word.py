"""Find big-endian 32-bit words (e.g. function pointers in vtables / tables) in an Xbox 360 memory image (read-only).

Finding 43 follow-up (DLC 2 DoppelgangerInit): functions without `bl` callers are reached through data (vtables,
state tables); this lists every 4-byte-aligned occurrence of the given values with its section and neighbours.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/xbox_find_word.py DUMP VALUE[,VALUE..] [--ctx N]
  DUMP: memory image with guest base 0x82000000 (work/xenia_dump/*.bin)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS

BASE = 0x82000000


def main(argv):
    ctx = 4
    if '--ctx' in argv:
        k = argv.index('--ctx'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    path = argv[0]; vals = [int(x, 0) for x in argv[1].split(',')]
    d = open(path, 'rb').read()
    secs = XS.sections(d, BASE)
    def sec_of(a):
        for s in secs:
            if s[1] <= a < s[2]: return s[0]
        return '?'
    for v in vals:
        pat = struct.pack('>I', v)
        i = d.find(pat); hits = 0
        while i >= 0:
            if i % 4 == 0:
                a = BASE + i; hits += 1
                lo = max(0, i - 4 * ctx); words = struct.unpack_from('>%dI' % (ctx * 2 + 1), d, lo) if lo + 4 * (ctx * 2 + 1) <= len(d) else ()
                print('0x%08x in %s: ...%s' % (a, sec_of(a), ' '.join('%08x' % w for w in words)))
            i = d.find(pat, i + 1)
        print('value 0x%08x: %d aligned hits' % (v, hits))


if __name__ == '__main__':
    main(sys.argv[1:])
