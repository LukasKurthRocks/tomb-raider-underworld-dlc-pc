"""List the DTPs (type 7) of one or more DRMs with size, relocation counts and the first words, to find the base-game
counterpart of a DLC DTP by its layout (read-only; finding 43, state-chart scope).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_list_shapes.py be|le FILE.drm [FILE.drm ...] [--min BYTES] [--grep HEX]
  --grep HEX: only DTPs whose first 8 bytes (as stored) contain HEX
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    mn = 0; grep = None
    if '--min' in argv: k = argv.index('--min'); mn = int(argv[k + 1]); del argv[k:k + 2]
    if '--grep' in argv: k = argv.index('--grep'); grep = bytes.fromhex(argv[k + 1]); del argv[k:k + 2]
    e = argv[0]
    for path in argv[1:]:
        D = DW.read(open(path, 'rb').read(), e)
        for s in D.sections:
            if s.type != 7 or len(s.data) < mn: continue
            d = bytes(s.data)
            if grep is not None and grep not in d[:8]: continue
            r = R.parse(bytes(s.reloc), e)
            print('%s DTP %6d  0x%06x bytes  internal %6d  idref %5d  head %s' % (os.path.basename(path), s.id, len(d),
                  len(r.internal), len(set(r.id_offsets())), d[:16].hex()))


if __name__ == '__main__':
    main(sys.argv[1:])
