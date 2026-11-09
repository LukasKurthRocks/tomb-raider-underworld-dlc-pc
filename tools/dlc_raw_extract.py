"""Write the Xbox DLC original of one DRM (big-endian, as stored in the pack, via convert_dlc.raw_dlc) to a file, so
tools that take a --be FILE.drm can read it (read-only towards the packs; N15 / package E 2026-11-09).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/dlc_raw_extract.py REL OUT.drm [--pack pack11]
"""
import sys, os, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    os.environ.setdefault('TRUDLC_PACK_FIRST', a[a.index('--pack') + 1] if '--pack' in a else 'pack11')
    from convert_dlc import raw_dlc
    d = raw_dlc(a[0])[0]
    os.makedirs(os.path.dirname(os.path.abspath(a[1])), exist_ok=True)
    with open(a[1], 'wb') as f:
        f.write(d)
    print('%s -> %s (%d bytes, md5 %s)' % (a[0], a[1], len(d), hashlib.md5(d).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
