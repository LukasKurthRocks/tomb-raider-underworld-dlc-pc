"""Listening copies of every language variant of one PC archive stream (.mul), decoded the way tru.exe decodes
(tools/f13_sibilants.decode_game) - read-only on the archives, writes WAVs only below work/listen/ (git-excluded).
Written for the "mercs speak Spanish" question 06.11.: does the Spanish record of a merc bark really carry Spanish
speech (and not a copy of the English one)?

Usage (from the repository root):
  ../bin/pyt -t 600 tools/listen_arch_langs.py SRC PATH [PATH ...] [--out work/listen/merc_langs]
      SRC = archive key of tools/locals.SRC (pcbig, pcpatch); PATH below the platform root,
      e.g. audio\\streams\\vo\\enemy\\merc\\b_m02_inv_g_01.mul -> <out>/<name>_<lang>.wav (+ a line per record:
      spec, size, samples, seconds, md5 of the record)
"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from vo_refs_scan import LANG
import f13_sibilants as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    out = os.path.join(ROOT, 'work', 'listen', 'merc_langs')
    if '--out' in argv:
        k = argv.index('--out'); out = os.path.join(ROOT, argv[k + 1]); del argv[k:k + 2]
    if not os.path.abspath(out).startswith(os.path.join(ROOT, 'work', 'listen')):
        sys.exit('refused: output must be below work/listen/ (git-excluded)')
    import locals as LC
    path, e, pre = LC.SRC[argv[0]]
    A = Archive(path, e)
    os.makedirs(out, exist_ok=True)
    for rel in argv[1:]:
        name = os.path.splitext(rel.replace('/', '\\').split('\\')[-1])[0]
        recs = A.find(crc(pre + '\\' + rel.replace('/', '\\')))
        if not recs:
            print('%s: not found' % rel); continue
        seen = set()
        for r in recs:
            if r['spec'] in seen: continue
            seen.add(r['spec'])
            d = A.read(r)
            rate, total, nch, segs = F.channel_blocks(d)
            chans = [F.decode_channel(s, F.decode_game) for s in segs]
            lg = LANG.get(r['spec'], '%08x' % r['spec'])
            print('%s %-4s spec %08x size %6d  %d Hz %d ch %7d samples %.2f s  md5 %s' % (
                name, lg, r['spec'], len(d), rate, nch, total, total / float(rate), hashlib.md5(d).hexdigest()[:12]))
            F.write_wav(os.path.join(out, '%s_%s.wav' % (name, lg)), chans, rate)


if __name__ == '__main__':
    main(sys.argv[1:])
