"""Decode one PC stream file (.mul: voice line, music or cinematic) to WAV the way tru.exe decodes it
(tools/f13_sibilants.decode_game), read-only on the input. Prints rate, channels, samples and length.
For listening to a record already extracted to a file (e.g. with tools/bigfile_lang_diff.py --extract);
tools/listen_arch_langs.py does the same straight from a game archive.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/mul_to_wav.py IN.mul OUT.wav
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f13_sibilants as F


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    d = open(argv[0], 'rb').read()
    rate, total, nch, segs = F.channel_blocks(d)
    chans = [F.decode_channel(s, F.decode_game) for s in segs]
    F.write_wav(argv[1], chans, rate)
    print('%s: %d Hz, %d channel(s), %d samples, %.2f s -> %s' % (os.path.basename(argv[0]), rate, nch, total,
                                                                  total / float(rate), argv[1]))


if __name__ == '__main__':
    main(sys.argv[1:])
