"""0.22.50 (2026-11-14): find W8PlayStub / W8EmitStub in a built TruMenu.asi by their byte patterns (read-only) and check
that the naked functions are what the source says, and that the two callbacks they call are __stdcall with two arguments
(their first return is ret 8):
  W8PlayStub: push [esp+4]; call [g_w8PlayFn]; pushad; pushfd; push esi; push eax; call W8OnPlay; popfd; popad; ret 4
  W8EmitStub: mov eax,[esp+0x1c]; pushad; pushfd; push [ebp+0xc]; push eax; call W8OnEmit; popfd; popad;
              test eax,eax; ret
Stack (W8EmitStub): it is called from 0x5b99fc (the 6 bytes after the game's untouched create call), so the game's
[esp+0x18] (the handle the create wrote) is [esp+0x1c] one return address deeper; it returns to the nop at 0x5b9a01.
Exit 0 = exactly one match each and both callbacks end their first path with ret 8; 1 = not so.

Usage (from the repository root):
  ../bin/pyt -t 60 work/menu50_1411/stub_bytes.py work/asi/menu0273/TruMenu.asi
"""
import re, sys
import capstone

PLAY = re.compile(rb'\xff\x74\x24\x04\xff\x15(.{4})\x60\x9c\x56\x50\xe8(.{4})\x9d\x61\xc2\x04\x00', re.S)
EMIT = re.compile(rb'\x8b\x44\x24\x1c()\x60\x9c\xff\x75\x0c\x50\xe8(.{4})\x9d\x61\x85\xc0\xc3', re.S)


def first_ret(data, off):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for ins in md.disasm(data[off:off + 0x600], off):
        if ins.mnemonic == 'ret':
            return ins.op_str or '0'
    return None


def check(data, pat, name, call_at):
    hits = list(pat.finditer(data))
    print('%s: %d match(es)' % (name, len(hits)))
    ok = len(hits) == 1
    for m in hits:
        rel = int.from_bytes(m.group(2), 'little', signed=True)
        target = m.start() + call_at + 5 + rel      # same section (.text): file offsets keep the distance
        ret = first_ret(data, target)
        print('  file offset 0x%x: %s' % (m.start(), data[m.start():m.end()].hex(' ')))
        print('  callback at file offset 0x%x, first ret: %s (want 8 = __stdcall, 2 arguments)' % (target, ret))
        ok = ok and ret in ('8', '0x8')
    return ok


def main(argv):
    data = open(argv[0], 'rb').read()
    ok = check(data, PLAY, 'W8PlayStub', 4 + 6 + 4)          # the e8 after ff742404 ff15xxxx 60 9c 56 50
    ok = check(data, EMIT, 'W8EmitStub', 4 + 2 + 3 + 1) and ok   # the e8 after 8b44241c 60 9c ff750c 50
    print('stubs %s' % ('ok' if ok else 'NOT as the source says'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
