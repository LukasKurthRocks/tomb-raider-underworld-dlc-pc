"""Read-only: where do given 4-byte words (hex, file byte order) occur, word-aligned, in the type-8 sections of a DRM
('pc:<name>' = the PC archive copy)? Evidence that a rebuilt word has the PC form.
Usage (repo root): ../bin/pyt work/crash_gpda_1411/find_words.py SPEC SCRIPT_ID[,ID...] WORD_HEX [...]"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sec_hex import load


def main(argv):
    e, S = load(argv[0])
    want = {int(x) for x in argv[1].split(',')}
    for w in argv[2:]:
        b = bytes.fromhex(w)
        hits = []
        for t, i, d, rl in S:
            if t != 8 or i not in want: continue
            hits += ['%d +0x%x' % (i, o) for o in range(0, len(d) - 3, 4) if d[o:o + 4] == b]
        print('%s: %d hit(s) %s' % (w, len(hits), hits[:8]))


if __name__ == '__main__':
    main(sys.argv[1:])
