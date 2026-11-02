"""List the instances of the game's static instance pool in a minidump: head links (+0 next / +4 prev, unlinked by
tru+0x197690), object pointer +0x10, flags +0x14 and the last 16 bytes of each slot, and flag every slot whose +0 / +4
are not 0 or a pointer to another slot start (read-only; test 50i crash tru+0x1976a3 in INSTANCE removal tru+0x1bc70d,
instance 0x00cf1650 with +0 = 0x0000d082, +4 = 0x00cf135f).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/instance_pool_dump.py DUMP START STRIDE COUNT [--all]
  e.g. DUMP 0x00ce74c0 0x2f0 120   (slot stride 0x2f0 = distance of the linked neighbours in the 50i dump)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minidump_read as MR


def main(argv):
    if len(argv) < 4: print(__doc__); return 2
    M = MR.Minidump(argv[0])
    start, stride, n = int(argv[1], 16), int(argv[2], 16), int(argv[3])
    slots = {start + k * stride for k in range(n)}
    bad = 0
    for k in range(n):
        a = start + k * stride
        b = M.read(a, stride)
        if b is None: print('0x%08x not in dump' % a); continue
        nx, pv, w8, wc, obj, fl = struct.unpack_from('<6I', b, 0)
        ok = all(v == 0 or v in slots for v in (nx, pv))
        bad += not ok
        if not ok or '--all' in argv:
            print('%s slot %3d 0x%08x next 0x%08x prev 0x%08x +8 0x%08x +c 0x%08x obj 0x%08x flags 0x%08x tail %s'
                  % ('BAD' if not ok else '   ', k, a, nx, pv, w8, wc, obj, fl, b[-16:].hex()))
    print('slots %d, bad links %d' % (n, bad))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
