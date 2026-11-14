"""0.22.48 (2026-11-14): find SoPlaceholderStub in a built TruMenu.asi by its byte pattern (read-only) and print where
it is and the bytes, so the naked function is known to be what the source says:
  mov eax,[ecx+44h] (8b 41 44); cmp eax,100 (83 f8 64); jne (75 xx); cmp dword [ecx+48h],56 (83 79 48 38); jne (75 xx);
  lock inc dword [abs] (f0 ff 05 xx xx xx xx); xor eax,eax (33 c0); test eax,eax (85 c0); ret (c3)
Exit 0 = exactly one match with both jumps landing on the test, 1 = not so.

Usage (from the repository root):
  ../bin/pyt -t 60 work/menu48_1411/stub_bytes.py work/asi/menu0271/TruMenu.asi
"""
import re, sys


def main(argv):
    data = open(argv[0], 'rb').read()
    pat = re.compile(rb'\x8b\x41\x44\x83\xf8\x64\x75(.)\x83\x79\x48\x38\x75(.)\xf0\xff\x05(.{4})\x33\xc0\x85\xc0\xc3', re.S)
    hits = list(pat.finditer(data))
    print('%d match(es) of the stub pattern' % len(hits))
    ok = len(hits) == 1
    for m in hits:
        j1, j2 = m.group(1)[0], m.group(2)[0]
        at1 = m.start() + 8 + j1           # after the first jne (offset 8) -> must be the test (offset 25)
        at2 = m.start() + 14 + j2          # after the second jne (offset 14)
        test = m.start() + 23              # 8b4144 83f864 75xx 83794838 75xx f0ff05+4 33c0 = 23 bytes before 85 c0
        print('file offset 0x%x: %s' % (m.start(), data[m.start():m.end()].hex(' ')))
        print('  jne 1 -> +0x%x, jne 2 -> +0x%x, test eax,eax at +0x%x: %s' % (at1 - m.start(), at2 - m.start(),
                                                                             test - m.start(), 'ok' if at1 == test ==
                                                                             at2 else 'WRONG'))
        ok = ok and at1 == test == at2
    print('stub %s' % ('ok' if ok else 'NOT as the source says'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
