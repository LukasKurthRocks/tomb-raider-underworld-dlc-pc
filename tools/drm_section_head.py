"""Print size, md5 and the first bytes of one or more DRM sections, read-only.

Finding 43, test 43: compare a texture section (type 5) between the Xbox title update, the retail Xbox layers and a
PC DRM (e.g. whether the hint-box texture 76 differs). For PC textures the PCD9 header '<4sIIIHHBBH' (magic,
format, data size, mips?, width, height, ...) is decoded.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_head.py SRC TYPE:ID[,TYPE:ID...] [--bytes N]
  SRC  a PC DRM file (little endian), or tu:NAME / retail:NAME (Xbox title update / retail layers, big endian)
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_idrefs as IR


def main(argv):
    n = 48
    if '--bytes' in argv:
        k = argv.index('--bytes'); n = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 2: sys.exit(__doc__)
    secs, e = IR.load(argv[0])
    idx = {(t, i): (d, r) for t, i, d, r in secs}
    for item in argv[1].split(','):
        t, i = (int(x) for x in item.split(':'))
        if (t, i) not in idx:
            print('%s %d:%d  MISSING' % (argv[0], t, i)); continue
        d, r = idx[(t, i)]
        print('%s %d:%d  size %d  md5 %s  reloc %d bytes' % (argv[0], t, i, len(d), hashlib.md5(bytes(d)).hexdigest(), len(r)))
        if d[:4] == b'PCD9' and len(d) >= 24:
            magic, fmt, size, x, w, h, b1, b2, s2 = struct.unpack_from('<4sIIIHHBBH', d, 0)
            print('    PCD9 format 0x%x data %d word3 %d %dx%d bytes %d %d %d' % (fmt, size, x, w, h, b1, b2, s2))
        print('    ' + ' '.join('%02x' % b for b in bytes(d[:n])))


if __name__ == '__main__':
    main(sys.argv[1:])
