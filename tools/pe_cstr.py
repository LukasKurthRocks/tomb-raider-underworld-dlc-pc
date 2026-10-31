"""Print the zero-terminated ASCII strings at one or more virtual addresses of a 32-bit PE (x86) such as tru.exe
(read-only; developer channel finding: name the source-file strings that FMOD's profiler code passes to its
allocator).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/pe_cstr.py EXE VA[,VA...] [MAXLEN]      MAXLEN default 200
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    maxlen = int(argv[2]) if len(argv) > 2 else 200
    base, secs = PE.sections(exe)
    for tok in argv[1].split(','):
        va = int(tok, 16)
        o = off_of(secs, va)
        if o < 0:
            print('0x%08x  <not in a raw section>' % va)
            continue
        end = exe.find(b'\0', o, o + maxlen)
        if end < 0: end = o + maxlen
        print('0x%08x  %r' % (va, exe[o:end].decode('latin-1')))


if __name__ == '__main__':
    main(sys.argv[1:])
