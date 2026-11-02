"""Find cinematic streams (cinstream-style .mul) among the records of a game archive, named or not (read-only).

Reads only the first bytes of every uncompressed record and keeps those whose header looks like a cdc multiplexed
stream (u32 [0] sample rate 8000..48000, [1] 0xffffffff, [3] channels 1..8) and whose first block is a cine block
(type 1) - then prints hash, name from the Yura file list (or '-'), spec, size, duration and the scene name of cine
block 0 (char[64] @0xc). Music / ambience .mul start with an audio block and are listed only with --all.
Question: is there a cinematic stream for the deleted extended ending that the PC file list does not name?

Usage (from the repository root):
  ../bin/pyt -t 900 tools/cine_unnamed_scan.py SOURCE [--all]       SOURCE as in tools/locals.py (pcbig, xbase, ...)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import load, L


def head(A, r, n):
    pos = r['offset'] << 11
    part, off = divmod(pos, A.align) if A.path.endswith('.000') else (0, pos)
    p = '%s.%03d' % (A.base, part) if A.path.endswith('.000') else A.path
    with open(p, 'rb') as f:
        f.seek(off); return f.read(n)


def main(argv):
    allm = '--all' in argv; argv = [a for a in argv if a != '--all']
    src = argv[0]
    path, e, pre = LC.SRC[src]
    E = '>' if e == 'be' else '<'
    A = Archive(path, e)
    xn = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
    n = 0
    for r in A.idx:
        if r['clen'] > 0 or r['size'] < 0x900: continue
        h = head(A, r, 0x800 + 16 + 0x50)
        W = struct.unpack_from(E + '4I', h, 0)
        if not (8000 <= W[0] <= 48000 and W[1] == 0xffffffff and 1 <= W[3] <= 8): continue
        t, sz = struct.unpack_from(E + '2I', h, 0x800)
        if t != 1 and not allm: continue
        scene = h[0x810 + 0xc:0x810 + 0x4c].split(b'\0')[0].decode('latin1', errors='replace') if t == 1 else ''
        name = xn.get(r['hash'], '-')
        n += 1
        print('%08x  %-50s spec %08x size %9d  %7.2f s  first block %d  scene "%s"'
              % (r['hash'], name, r['spec'], r['size'], W[2] / W[0], t, scene))
    print('streams: %d' % n)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
