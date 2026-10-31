"""Print the 32-bit words (and both u16 halves) of one DRM section in a byte range, marking relocated pointers
(read-only; finding 43, rock vein state chart in doppelganger_casual.drm).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/drm_words_at.py FILE.drm SECTION_ID OFFSET LENGTH [--be] [--type T]
  OFFSET / LENGTH hex; --be for an Xbox (big-endian) DRM; --type when ids repeat across types
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    be = '--be' in argv
    argv = [a for a in argv if a != '--be']
    typ = None
    if '--type' in argv: k = argv.index('--type'); typ = int(argv[k + 1]); del argv[k:k + 2]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    if argv[1] == 'list':                       # section list: index, type, id, size
        for si, s in enumerate(D.sections):
            if typ is None or s.type == typ: print('%3d type %2d id %6d size 0x%x' % (si, s.type, s.id, len(s.data)))
        return
    sid = int(argv[1]); off = int(argv[2], 16); ln = int(argv[3], 16)
    for si, s in enumerate(D.sections):
        if s.id != sid or (typ is not None and s.type != typ): continue
        d = bytes(s.data)
        r = R.parse(bytes(s.reloc), e)
        intern = dict(r.internal)
        ext = {o: (xi, t) for xi, o, t in r.external}
        print('== type %d id %d size 0x%x' % (s.type, s.id, len(d)))
        start = off & ~3
        for o in range(start, min(len(d), off + ln), 4):
            w = struct.unpack_from(f + 'I', d, o)[0]
            lo, hi = struct.unpack_from(f + 'HH', d, o)
            fl = struct.unpack_from(f + 'f', d, o)[0]
            note = ''
            if o in intern: note = '-> +0x%x' % intern[o]
            elif o in ext: note = '-> sec %d (id %d) +0x%x' % (ext[o][0], D.sections[ext[o][0]].id, ext[o][1])
            fs = ('%.5g' % fl) if (w == 0 or 1e-5 < abs(fl) < 1e7) else ''
            print('  +0x%05x  %08x  u16 %5d %5d  %-12s %s' % (o, w, lo, hi, fs, note))


if __name__ == '__main__':
    main(sys.argv[1:])
