"""P1 (2026-11-13): print words of one DTP section of a DRM with internal-pointer marks (read-only).

Usage (from trudlcport): ../bin/pyt -t 120 work/p1_med_1311/p1_dtp_words.py FILE.drm DTP_ID START_HEX COUNT
  Prints COUNT u32 words from START, 4 per line; a word that is an internal pointer is shown as '->+0x...'.
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import drm_write as DW


def main(argv):
    if len(argv) < 4:
        print(__doc__); return 2
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    s = next((x for x in D.sections if x.type == 7 and x.id == int(argv[1])), None)
    if s is None:
        print('DTP %s not found' % argv[1]); return 1
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    o0, n = int(argv[2], 16), int(argv[3])
    for r in range(0, n, 4):
        cells = []
        for k in range(4):
            o = o0 + 4 * (r + k)
            if o + 4 > len(d): break
            cells.append(('->+0x%x' % it[o]) if o in it else '%08x' % struct.unpack_from('<I', d, o)[0])
        print('+0x%04x  %s' % (o0 + 4 * r, '  '.join('%-10s' % c for c in cells)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
