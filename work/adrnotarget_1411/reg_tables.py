"""Read-only: print the {id, group, fn} records of registration tables in a 32-bit PE (ends at id 0 or a bad record)
and mark the ids asked for.

Usage (from the repository root):
  ../bin/pyt -t 120 work/adrnotarget_1411/reg_tables.py EXE TABLE_VA[,TABLE_VA..] [ID,ID..]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size:
            return rptr + a - sva
    return -1


def main(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    want = set(int(x) for x in argv[2].split(',')) if len(argv) > 2 else set()
    for t in argv[1].split(','):
        va = int(t, 16)
        o = off_of(secs, va)
        n = 0
        print('; table 0x%08x' % va)
        while n < 2000:
            i, g, f = struct.unpack_from('<III', exe, o + 12 * n)
            if i == 0 and g == 0:
                print('  end at record %d (0x%08x): %u %u 0x%08x' % (n, va + 12 * n, i, g, f))
                break
            if i in want or not want:
                print('  #%-4d 0x%08x  id %5u  group %5u  fn 0x%08x' % (n, va + 12 * n, i, g, f))
            n += 1
        print('  records:', n)


if __name__ == '__main__':
    main(sys.argv[1:])
