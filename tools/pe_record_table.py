"""Dump a static table of fixed-size records from a 32-bit PE (x86) such as tru.exe, read-only.

Every record is printed as its dwords; a dword that points at a printable zero-terminated string in a raw section is
shown with that string. Stops after COUNT records or at the first all-zero record (with --stop-zero).
Example: the player type table (records {name, init, f2..f6}, 7 dwords) at 0x8aba28.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/pe_record_table.py EXE VA STRIDE COUNT [--stop-zero]
    VA, STRIDE in hex (0x...) or decimal; STRIDE in bytes (multiple of 4)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size:
            return rptr + a - sva
    return -1


def cstr(exe, secs, va, maxlen=64):
    o = off_of(secs, va)
    if o < 0:
        return None
    end = exe.find(b'\0', o, o + maxlen)
    if end <= o:
        return None
    s = exe[o:end]
    if all(32 <= c < 127 for c in s) and len(s) >= 2:
        return s.decode('ascii')
    return None


def main(argv):
    if len(argv) < 4:
        sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    va, stride, count = int(argv[1], 0), int(argv[2], 0), int(argv[3], 0)
    stop_zero = '--stop-zero' in argv
    base, secs = PE.sections(exe)
    for i in range(count):
        a = va + i * stride
        o = off_of(secs, a)
        if o < 0:
            print('%3d 0x%08x <not in a raw section>' % (i, a))
            break
        words = struct.unpack_from('<%dI' % (stride // 4), exe, o)
        if stop_zero and not any(words):
            print('%3d 0x%08x <zero record>' % (i, a))
            break
        parts = []
        for w in words:
            s = cstr(exe, secs, w) if w else None
            parts.append('0x%08x' % w + (' "%s"' % s if s else ''))
        print('%3d 0x%08x  %s' % (i, a, '  '.join(parts)))


if __name__ == '__main__':
    main(sys.argv[1:])
