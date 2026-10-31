"""List the zero-terminated ASCII strings inside a virtual-address range of a 32-bit PE (x86) such as tru.exe, with
the places that reference each string as a 32-bit immediate / pointer (read-only; weapons / ammo / health research
2026-10-31, used to read the player-weapon log strings around 0x85d300).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_strings_range.py EXE FROM TO [--min N] [--norefs]   N = min length (default 4)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    lo, hi = int(argv[1], 16), int(argv[2], 16)
    mn = int(argv[argv.index('--min') + 1]) if '--min' in argv else 4
    norefs = '--norefs' in argv
    base, secs = PE.sections(exe)
    sec = None
    for s in secs:
        if s[1] <= lo < s[1] + s[3]: sec = s
    if sec is None: sys.exit('range not in a section')
    _, sva, rptr, size, _ = sec
    o, end = rptr + lo - sva, rptr + min(hi, sva + size) - sva
    hits = []
    i = o
    while i < end:
        j = i
        while j < end and 0x20 <= exe[j] < 0x7f or (j < end and exe[j] in (9, 10, 13)): j += 1
        if j - i >= mn and j < len(exe) and exe[j] == 0:
            hits.append((sva + i - rptr, exe[i:j].decode('latin-1')))
            i = j + 1
        else:
            i = max(j, i) + 1
    refs = {}
    if not norefs:
        want = {struct.pack('<I', a): a for a, _ in hits}
        for name, s_va, s_rp, s_sz, _ in secs:
            blob = exe[s_rp:s_rp + s_sz]
            for k in range(0, len(blob) - 3):
                b = blob[k:k + 4]
                if b in want: refs.setdefault(want[b], []).append(s_va + k)
    for a, t in hits:
        r = refs.get(a, [])
        rs = ' '.join('0x%08x' % x for x in r[:6]) + (' ...' if len(r) > 6 else '')
        print('0x%08x %-60r %s' % (a, t[:120], rs))


if __name__ == '__main__':
    main(sys.argv[1:])
