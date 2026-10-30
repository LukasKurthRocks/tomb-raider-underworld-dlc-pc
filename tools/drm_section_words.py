"""Print the 32-bit words and relocations of one section of an Xbox DRM from the title update or retail layers (big
endian), read-only. Finding 43, test 36: what the title update's own generalbank sections (UI DTP data, textures)
hold and which sections they point to.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_words.py tu:NAME|retail:NAME TYPE ID [MAX_WORDS]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C
import drm_reloc as R


def main(argv):
    kind, name = argv[0].split(':', 1); typ, sid = int(argv[1]), int(argv[2])
    n = int(argv[3]) if len(argv) > 3 else 64
    secs = C.find(C.BASE if kind == 'tu' else C.BASE[1:], 'be', 'xenon-w' + chr(92) + name)
    s = next(q for q in secs if q['type'] == typ and q['id'] == sid)
    d = s['data']; r = R.parse(s['reloc'], 'be')
    print('type %d id %d: %d bytes' % (typ, sid, len(d)))
    for attr in ('internal', 'external', 'idref_a', 'idref'):
        v = getattr(r, attr, None)
        if v: print('%s relocations (%d): %s' % (attr, len(v), list(v)[:24]))
    for o in range(0, min(len(d), 4 * n), 16):
        print('+0x%04x  %s' % (o, ' '.join('%08x' % struct.unpack_from('>I', d, o + k)[0]
                                           for k in range(0, 16, 4) if o + k + 4 <= len(d))))


if __name__ == '__main__':
    main(sys.argv[1:])
