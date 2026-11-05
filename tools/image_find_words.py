"""Find a sequence of 32-bit words in a binary file (Xenia memory image = big endian, or a PE file = little endian)
and print the words that follow it (read-only; shadow combat night 2026-11-04: the pad button -> input source code
table of the Xbox exe, PC twin tru+0x84bd2: masks [0x844e40] / codes [0x844e78]).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/image_find_words.py FILE be|le BASE W1,W2,..  [--after N]
  BASE = the address of file offset 0 (0x82000000 for the Xenia images; 0 for a plain file offset)
  --after N  print N words after each hit (default 16)
"""
import sys, struct


def main(argv):
    n_after = 16
    if '--after' in argv: k = argv.index('--after'); n_after = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) < 4: sys.exit(__doc__)
    d = open(argv[0], 'rb').read()
    f = '>' if argv[1] == 'be' else '<'
    base = int(argv[2], 16)
    pat = b''.join(struct.pack(f + 'I', int(x, 16)) for x in argv[3].split(','))
    i = d.find(pat); hits = 0
    while i >= 0 and hits < 20:
        if i % 4 == 0:
            hits += 1
            w = [struct.unpack_from(f + 'I', d, i + 4 * k)[0] for k in range(n_after) if i + 4 * k + 4 <= len(d)]
            print('0x%08x: %s' % (base + i, ' '.join('%x' % x for x in w)))
        i = d.find(pat, i + 1)
    if not hits: print('not found')


if __name__ == '__main__':
    main(sys.argv[1:])
