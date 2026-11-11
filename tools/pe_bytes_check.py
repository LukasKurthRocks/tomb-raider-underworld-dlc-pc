"""Check expected code bytes at virtual addresses of a PE file (read-only; the byte pre-checks an ASI does at load,
run offline against the installed exe before a test - wall run 2026-11-01, TruRockVein 0.6 / TruShadowPower 0.6).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_bytes_check.py EXE ADDR=HEX [ADDR=HEX ..]      HEX may contain spaces if quoted
  ../bin/pyt -t 120 tools/pe_bytes_check.py EXE --file CHECKS.txt          one `ADDR HEX...` per line, # comments
Prints ok / MISMATCH (with the bytes found) per check and a total.
Exit code (Q75, 2026-11-11; before: always 0): 0 = every check ok, 1 = at least one MISMATCH (an address outside
every section counts as one), 2 = usage error (no exe / no check given).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) < 2 or (argv[1] == '--file' and len(argv) < 3):
        print(__doc__.strip())
        return 2
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)

    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        return None
    checks = []
    if argv[1] == '--file':
        for line in open(argv[2]):
            line = line.split('#')[0].strip()
            if not line: continue
            a, _, h = line.partition(' ')
            checks.append((a, h))
    else:
        for x in argv[1:]:
            a, _, h = x.partition('=')
            checks.append((a, h))
    bad = 0
    for a, h in checks:
        va = int(a, 16)
        want = bytes.fromhex(h.replace(' ', ''))
        o = off(va)
        got = exe[o:o + len(want)] if o is not None else b''
        ok = got == want
        bad += not ok
        print('%s 0x%08x %2d bytes%s' % ('ok      ' if ok else 'MISMATCH', va, len(want), '' if ok else ' found ' + got.hex()))
    print('%d checks, %d mismatches' % (len(checks), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
