"""0.22.52 (2026-11-14 late): the stubs of a built TruMenu.asi by their byte patterns (read-only), as the source says
(absolute addresses of TruMenu's own variables masked). S5FogStub and W9SendStub as in work/menu51_1411/s5_stub_bytes.py;
S5UnitStub of 0.22.52:
  mov eax,[esp+4]; mov ecx,[g_s5ShowUnit]; test ecx,ecx; je draw; cmp eax,ecx; je draw; lock inc [g_s5AreaSkips]; ret;
  draw: cmp [g_s5Tint],0; je plain; push eax; call S5ColourFor (stdcall, 1 argument: its first ret = ret 4);
  test eax,eax; je plain; mov ecx,[g_s5ColourAt]; push [ecx]; mov [ecx],eax; push [esp+0Ch]; push [esp+0Ch];
  call [g_s5DrawFn]; add esp,8; mov ecx,[g_s5ColourAt]; pop edx; mov [ecx],edx; lock inc [g_s5Tinted]; ret;
  plain: jmp [g_s5DrawFn]
Exit 0 = exactly one match each with the right jump targets; 1 = not so.

Usage (from the repository root):
  ../bin/pyt -t 60 work/menu52_1411/s6_stub_bytes.py work/asi/menu0275/TruMenu.asi
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'menu51_1411'))
import s5_stub_bytes as S5   # noqa: E402

A = b'(.{4})'
UNIT = re.compile(rb'\x8b\x44\x24\x04\x8b\x0d' + A + rb'\x85\xc9\x74(.)\x3b\xc1\x74(.)\xf0\xff\x05' + A + rb'\xc3'
                  rb'\x83\x3d' + A + rb'\x00\x74(.)\x50\xe8' + A + rb'\x85\xc0\x74(.)\x8b\x0d' + A +
                  rb'\xff\x31\x89\x01\xff\x74\x24\x0c\xff\x74\x24\x0c\xff\x15' + A + rb'\x83\xc4\x08\x8b\x0d' + A +
                  rb'\x5a\x89\x11\xf0\xff\x05' + A + rb'\xc3\xff\x25' + A, re.S)


def main(argv):
    data = open(argv[0], 'rb').read()
    ok = True
    hits = list(S5.FOG.finditer(data))
    print('S5FogStub: %d match(es)' % len(hits))
    ok = ok and len(hits) == 1
    for m in hits:
        go, want = S5.rel8(m, 2, data), m.end() - 6
        print('  je go -> 0x%x (want 0x%x)' % (go, want))
        ok = ok and go == want
    hits = list(UNIT.finditer(data))
    print('S5UnitStub (0.22.52): %d match(es)' % len(hits))
    ok = ok and len(hits) == 1
    for m in hits:
        draw = m.start() + data[m.start():].find(b'\x83\x3d')
        plain = m.end() - 6
        # groups: 1 ShowUnit, 2 / 3 je draw, 4 AreaSkips, 5 Tint, 6 je plain, 7 call rel, 8 je plain
        t1, t2, t3, t4 = S5.rel8(m, 2, data), S5.rel8(m, 3, data), S5.rel8(m, 6, data), S5.rel8(m, 8, data)
        call_at = m.start(7) - 1
        callee = call_at + 5 + int.from_bytes(m.group(7), 'little', signed=True)
        ret = S5.first_ret(data, callee)
        print('  file offset 0x%x: %d bytes' % (m.start(), m.end() - m.start()))
        print('  je draw -> 0x%x / 0x%x (want 0x%x), je plain -> 0x%x / 0x%x (want 0x%x); S5ColourFor at 0x%x, first '
              'ret %s (want 4)' % (t1, t2, draw, t3, t4, plain, callee, ret))
        ok = ok and t1 == draw and t2 == draw and t3 == plain and t4 == plain and ret in ('4', '0x4')
    hits = list(S5.W9.finditer(data))
    print('W9SendStub: %d match(es)' % len(hits))
    ok = ok and len(hits) == 1
    for m in hits:
        keep, want = S5.rel8(m, 2, data), m.end() - 8
        callee = m.start() + 3 + 5 + int.from_bytes(m.group(1), 'little', signed=True)
        ret = S5.first_ret(data, callee)
        print('  je keep -> 0x%x (want 0x%x); W9VoiceMuted first ret %s (want 4)' % (keep, want, ret))
        ok = ok and keep == want and ret in ('4', '0x4')
    print('stubs %s' % ('ok' if ok else 'NOT as the source says'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
