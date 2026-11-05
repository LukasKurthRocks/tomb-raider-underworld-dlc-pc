"""Find UTF-16LE (wide) strings in a 32-bit PE (x86) such as tru.exe by substring and list the places that reference
them as a 32-bit immediate / pointer (read-only; TruMenu 0.9 save-folder finding). Wide counterpart of
tools/pe_find_str.py: the string start is found by walking back over wide characters to the previous L'\\0'.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_find_wstr.py EXE TEXT[,TEXT...] [--max N] [--case]
  Without --case the search ignores ASCII case (both the needle and the image are compared lower-cased).
  ../bin/pyt -t 300 tools/pe_find_wstr.py EXE --range FROM TO [--min N]
  lists every wide ASCII string of >= N characters (default 3) in [FROM, TO) (hex VAs) with its references.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def va_of(secs, o):
    for name, sva, rptr, size, _ in secs:
        if rptr <= o < rptr + size: return sva + o - rptr, name
    return None, None


def lower_wide(b):
    """ASCII lower-case of a UTF-16LE byte string (only the low byte of characters with a zero high byte)."""
    out = bytearray(b)
    for i in range(0, len(out) - 1, 2):
        if out[i + 1] == 0 and 0x41 <= out[i] <= 0x5A:
            out[i] += 0x20
    return bytes(out)


def refs(exe, secs, va):
    key = struct.pack('<I', va)
    out, r = [], 0
    while True:
        r = exe.find(key, r)
        if r < 0: break
        rva, rsec = va_of(secs, r)
        if rva is not None: out.append('0x%08x %s' % (rva, rsec))
        r += 1
    return out


def list_range(exe, secs, lo, hi, mn):
    """Every wide string of >= mn printable ASCII characters in [lo, hi) (2-byte aligned)."""
    for name, sva, rptr, size, _ in secs:
        if not (sva <= lo < sva + size): continue
        o = rptr + lo - sva
        end = rptr + min(hi, sva + size) - sva
        while o < end:
            e = o
            while e + 1 < end and 0x20 <= exe[e] < 0x7f and exe[e + 1] == 0: e += 2
            if (e - o) // 2 >= mn and exe[e:e + 2] == b'\0\0':
                va = sva + o - rptr
                print('  0x%08x %r' % (va, exe[o:e].decode('utf-16-le')))
                for r in refs(exe, secs, va): print('      ref ' + r)
                o = e + 2
            else:
                o += 2


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    if argv[1] == '--range':
        base, secs = PE.sections(exe)
        mn = int(argv[argv.index('--min') + 1]) if '--min' in argv else 3
        list_range(exe, secs, int(argv[2], 16), int(argv[3], 16), mn)
        return
    texts = argv[1].split(',')
    mx = 20
    if '--max' in argv: mx = int(argv[argv.index('--max') + 1])
    case = '--case' in argv
    base, secs = PE.sections(exe)
    hay = exe if case else lower_wide(exe)
    for t in texts:
        needle = t.encode('utf-16-le')
        if not case: needle = lower_wide(needle)
        print('== %r (wide)' % t)
        pos, n, seen = 0, 0, set()
        while n < mx:
            i = hay.find(needle, pos)
            if i < 0: break
            pos = i + 1
            s = i
            if s % 2 != i % 2: continue
            while s >= 2 and exe[s - 2:s] != b'\0\0' and i - s < 512: s -= 2
            if s in seen: continue
            seen.add(s)
            e = s
            while e + 1 < len(exe) and exe[e:e + 2] != b'\0\0': e += 2
            va, sec = va_of(secs, s)
            if va is None: continue
            n += 1
            text = exe[s:e].decode('utf-16-le', errors='replace')
            print('  0x%08x %-6s %r' % (va, sec, text[:120]))
            key = struct.pack('<I', va)
            r = 0
            while True:
                r = exe.find(key, r)
                if r < 0: break
                rva, rsec = va_of(secs, r)
                if rva is not None:
                    print('      ref 0x%08x %s' % (rva, rsec))
                r += 1


if __name__ == '__main__':
    main(sys.argv[1:])
