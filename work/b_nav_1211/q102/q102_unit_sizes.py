"""Q102 (read-only): record size of unit DRMs in the PC archives (pcbig / pcpatch) and whether the stored bytes are a
CDRM (block-compressed) container. Used to estimate how many 512 KB file-system chunks a level load reads.

Usage (from the repository root):
  ../bin/pyt -t 300 work/b_nav_1211/q102/q102_unit_sizes.py UNIT [UNIT ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools'))
import locals as LC
from archive import Archive
from names import crc


def main(argv):
    arcs = {}
    for src in ('pcpatch', 'pcbig'):
        path, e, pre = LC.SRC[src]
        arcs[src] = (Archive(path, e), pre)
    total = 0
    for unit in argv:
        name = unit if unit.endswith('.drm') else unit + '.drm'
        hit = None
        for src in ('pcpatch', 'pcbig'):
            A, pre = arcs[src]
            recs = A.find(crc(pre + '\\' + name))
            if recs:
                hit = (src, A, recs[0]); break
        if not hit:
            print('%-28s not found' % name); continue
        src, A, r = hit
        data = A.read(r)
        magic = data[:4]
        info = ''
        if magic == b'CDRM':
            n = struct.unpack_from('<I', data, 8)[0] if len(data) > 12 else -1
            info = 'CDRM'
        print('%-28s %-8s size %10d clen %10d stored %10d magic %r %s' % (
            name, src, r['size'], r['clen'], len(data), magic, info))
        total += r['size']
    print('total size %d bytes = %.1f MB = %d chunks of 512 KB' % (total, total / 1048576.0, (total + 0x7ffff) // 0x80000))


if __name__ == '__main__':
    main(sys.argv[1:])
