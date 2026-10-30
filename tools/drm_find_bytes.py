"""Find a byte pattern in the sections of DRM files (CDRM is decoded; read-only). Used to trace a value seen in the
running game back to the data that carries it (finding 43: the cloth iteration count 0x00040000 of a DLC 2
simulation object). Reports file, section index / type / id, offset in the section and the bytes around it.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/drm_find_bytes.py HEX DIR [DIR ...] [--endian le|be] [--context N]
  HEX: bytes as written in the file, e.g. 17d986c0cdcccc3d00000400 (spaces allowed if quoted)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    endian = 'le'; ctx = 16
    if '--endian' in argv: k = argv.index('--endian'); endian = argv[k + 1]; del argv[k:k + 2]
    if '--context' in argv: k = argv.index('--context'); ctx = int(argv[k + 1]); del argv[k:k + 2]
    pat = bytes.fromhex(argv[0].replace(' ', ''))
    files = hits = 0
    for top in argv[1:]:
        for dp, dn, fn in os.walk(top):
            for f in sorted(fn):
                if not f.lower().endswith('.drm'): continue
                p = os.path.join(dp, f); files += 1
                try: D = DW.read(open(p, 'rb').read(), endian)
                except Exception as e: print('  skipped %s: %s' % (p, e)); continue
                for si, s in enumerate(D.sections):
                    o = s.data.find(pat)
                    while o >= 0:
                        hits += 1
                        a = max(0, o - ctx)
                        print('HIT %s sec %d type %d id %d off 0x%x: %s' % (
                            p, si, s.type, s.id, o, s.data[a:o + len(pat) + ctx].hex()))
                        o = s.data.find(pat, o + 1)
    print('files: %d, hits: %d' % (files, hits))


if __name__ == '__main__':
    main(sys.argv[1:])
