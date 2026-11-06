"""Find u32 values in the sections of DRMs read straight from a game archive (read-only).

Like tools/drm_find_u32.py, but the DRM comes from an archive (Xbox packs are big-endian), so no extracted copy is
needed. Prints section index / type / id, the offset and the neighbour words of every aligned hit. Written for the
voice-line question 06.11.: which section of a DLC 2 unit refers to the dialogue DTP of a doppelganger line and which
string ids sit next to it.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/arch_drm_find_u32.py SRC NAME.drm[,NAME.drm..] VALUE[,VALUE..] [--ctx N] [--u16]
      SRC = archive key of tools/locals.SRC; VALUE decimal or 0x-hex; --u16 also searches 2-byte aligned u16 values
  ../bin/pyt -t 600 tools/arch_drm_find_u32.py SRC NAME.drm --dump SECID:FROM:TO[:STRIDE]
      words of section SECID from offset FROM to TO, STRIDE bytes per line (default 0x18)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from drm import cdrm_decode, sections_with_data
from drm import SECTION_TYPES


def main(argv):
    ctx, u16 = 2, False
    if '--ctx' in argv:
        k = argv.index('--ctx'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    if '--u16' in argv:
        argv.remove('--u16'); u16 = True
    dump = None
    if '--dump' in argv:                      # --dump SECID:FROM:TO  print the words of one section instead
        k = argv.index('--dump'); dump = [int(x, 0) for x in argv[k + 1].split(':')]; del argv[k:k + 2]
        argv = argv + ['0']
    src, names, vals = argv[0], argv[1].split(','), [int(v, 0) for v in argv[2].split(',')]
    import locals as LC
    path, e, pre = LC.SRC[src]
    E = '>' if e == 'be' else '<'
    A = Archive(path, e)
    for name in names:
        recs = A.find(crc(pre + '\\' + name))
        if not recs:
            print('%s: not in %s' % (name, src)); continue
        raw = cdrm_decode(A.read(recs[-1]), e)
        h, secs = sections_with_data(raw, e)
        if dump:
            for s in secs:
                if s['id'] != dump[0] or s['type'] in (2, 5, 6, 9): continue
                d = s['data']
                for o in range(dump[1] & ~3, min(dump[2], len(d) - 3), 0x18 if len(dump) < 4 else dump[3]):
                    n = min(6 if len(dump) < 4 else dump[3] // 4, (len(d) - o) // 4)
                    print('%s sec type %d id %d +0x%05x: %s' % (name, s['type'], s['id'], o,
                          ' '.join('%08x' % x for x in struct.unpack(E + '%dI' % n, d[o:o + 4 * n]))))
            continue
        hits = 0
        for s in secs:
            d = s['data']
            n = len(d) // 4
            if not n: continue
            w = struct.unpack(E + '%dI' % n, d[:4 * n])
            for i, x in enumerate(w):
                if x in vals:
                    hits += 1
                    near = ' '.join(('*' if j == i else '') + '%08x' % w[j] for j in range(max(0, i - ctx), min(n, i + ctx + 1)))
                    print('%s sec %d type %d(%s) id %d +0x%x: %s' % (name, s['i'], s['type'], SECTION_TYPES.get(s['type'], '?'),
                                                                   s['id'], 4 * i, near))
            if u16:
                m = len(d) // 2
                hw = struct.unpack(E + '%dH' % m, d[:2 * m])
                for i, x in enumerate(hw):
                    if x in vals and i % 2:
                        hits += 1
                        print('%s sec %d type %d id %d +0x%x: u16 %d (odd half)' % (name, s['i'], s['type'], s['id'], 2 * i, x))
        print('%s: %d sections, %d hits' % (name, len(secs), hits))


if __name__ == '__main__':
    main(sys.argv[1:])
