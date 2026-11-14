"""TruMenu 0.22.51 research helper (read only): where a dword value is stored in the PC exe image (any section).

Usage (from trudlcport):
  ../bin/pyt work/menu51_1411/m51_find.py EXE VALUE [VALUE ...]   every aligned / unaligned position whose u32 = VALUE (VA)
Output goes to stdout; nothing is written.
"""
import os
import sys
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'work', 'ledge18a_0811'))
import qol_pe as P  # noqa: E402


def main(a):
    d, base, secs, pe = P.load(a[0])
    for s in a[1:]:
        v = int(s, 16)
        pat = struct.pack('<I', v)
        i = d.find(pat)
        while i >= 0:
            va = P.off2va(secs, i)
            if va is not None:
                print('%08x  at %08x' % (v, va))
            i = d.find(pat, i + 1)


if __name__ == '__main__':
    main(sys.argv[1:])
