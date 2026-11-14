"""0.22.51 (2026-11-14): find S5FogStub / S5UnitStub in a built TruMenu.asi by their byte patterns (read-only) and check
that the naked functions are what the source says (absolute addresses of TruMenu's own variables masked):
  S5FogStub:  mov eax,[g_s5FogFar]; test eax,eax; je go; mov [esp+14h],eax; mov eax,[g_s5FogNear]; mov [esp+10h],eax;
              lock inc [g_s5FogCalls]; go: jmp [g_s5FogFn]
  S5UnitStub: mov eax,[esp+4]; mov ecx,[g_s5ShowUnit]; test ecx,ecx; je draw; cmp eax,ecx; je draw;
              lock inc [g_s5AreaSkips]; ret; draw: cmp [g_s5Tint],0; je plain; mov ecx,[g_s5AnchorAt]; cmp eax,[ecx];
              je plain; mov ecx,[g_s5ColourAt]; push [ecx]; mov edx,[g_s5TintColour]; mov [ecx],edx; push [esp+0Ch];
              push eax; call [g_s5DrawFn]; add esp,8; mov ecx,[g_s5ColourAt]; pop edx; mov [ecx],edx;
              lock inc [g_s5Tinted]; ret; plain: jmp [g_s5DrawFn]
Also: both jumps 'je' land on the labels (go / draw / plain) of the same stub.
Exit 0 = exactly one match each with the right jump targets; 1 = not so.

Usage (from the repository root):
  ../bin/pyt -t 60 work/menu51_1411/s5_stub_bytes.py work/asi/menu0274/TruMenu.asi
"""
import re
import sys

A = b'(.{4})'
FOG = re.compile(rb'\xa1' + A + rb'\x85\xc0\x74(.)\x89\x44\x24\x14\xa1' + A + rb'\x89\x44\x24\x10\xf0\xff\x05' + A +
                 rb'\xff\x25' + A, re.S)
UNIT = re.compile(rb'\x8b\x44\x24\x04\x8b\x0d' + A + rb'\x85\xc9\x74(.)\x3b\xc1\x74(.)\xf0\xff\x05' + A + rb'\xc3'
                  rb'\x83\x3d' + A + rb'\x00\x74(.)\x8b\x0d' + A + rb'\x3b\x01\x74(.)\x8b\x0d' + A + rb'\xff\x31\x8b\x15' + A +
                  rb'\x89\x11\xff\x74\x24\x0c\x50\xff\x15' + A + rb'\x83\xc4\x08\x8b\x0d' + A + rb'\x5a\x89\x11\xf0\xff\x05' + A +
                  rb'\xc3\xff\x25' + A, re.S)


def rel8(m, group, data):
    """the target file offset of a short jump whose displacement byte is the given group"""
    at = m.start(group)
    return at + 1 + int.from_bytes(data[at:at + 1], 'little', signed=True)


def main(argv):
    data = open(argv[0], 'rb').read()
    ok = True
    hits = list(FOG.finditer(data))
    print('S5FogStub: %d match(es)' % len(hits))
    ok = ok and len(hits) == 1
    for m in hits:
        go = rel8(m, 2, data)
        want = m.end() - 6                           # the jmp [g_s5FogFn]
        print('  file offset 0x%x: %s' % (m.start(), data[m.start():m.end()].hex(' ')))
        print('  je go -> 0x%x (want the jmp at 0x%x)' % (go, want))
        ok = ok and go == want
    hits = list(UNIT.finditer(data))
    print('S5UnitStub: %d match(es)' % len(hits))
    ok = ok and len(hits) == 1
    for m in hits:
        draw = m.start() + data[m.start():].find(b'\x83\x3d')
        plain = m.end() - 6
        # groups: 1 [g_s5ShowUnit], 2 / 3 je draw, 4 [g_s5AreaSkips], 5 [g_s5Tint], 6 je plain, 7 [g_s5AnchorAt], 8 je plain
        t1, t2, t3, t4 = rel8(m, 2, data), rel8(m, 3, data), rel8(m, 6, data), rel8(m, 8, data)
        print('  file offset 0x%x: %d bytes' % (m.start(), m.end() - m.start()))
        print('  je draw -> 0x%x / 0x%x (want 0x%x), je plain -> 0x%x / 0x%x (want 0x%x)' % (t1, t2, draw, t3, t4, plain))
        ok = ok and t1 == draw and t2 == draw and t3 == plain and t4 == plain
    print('stubs %s' % ('ok' if ok else 'NOT as the source says'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
