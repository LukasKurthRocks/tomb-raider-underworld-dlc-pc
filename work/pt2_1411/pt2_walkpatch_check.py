"""PT.2 (2026-11-14): check the TruQoL 0.1.8 [Fixes] ReleaseWalk patch of the deferred release walk 0x47ab90. Read-only.

Reads tru.exe (path given; the file is only read), compares the bytes at 0x47ab90..0x47abd4 with the expected original
(TruQoL's guard string), disassembles original and patched loop (capstone) and checks the patched branch targets.

Usage (repository root): ../bin/pyt -t 60 work/pt2_1411/pt2_walkpatch_check.py TRU_EXE
"""
import sys, struct
import capstone

BASE = 0x400000
GUARD_VA = 0x47ab90
GUARD = bytes.fromhex('8b81acfd0000 83ec0c 56 8db1acfd0000 57 8bb9b4fd0000 8b4e08 8d1481 3bfa 741d 8b0f 85c9 7408 8b01 8b10'
                      '6a01 ffd2 8b06 8b4e08 83c704 8d1481 3bfa 75e3 c70600000000'.replace(' ', ''))
PATCH_VA = 0x47aba1
PATCH = bytes.fromhex('31ff 3b3e 7327 8b4e08 8b0cb9 47 85c9 74f1 8b01 6a01 ff10 ebe9'.replace(' ', '')) + b'\x90' * 20


def va_to_off(pe, va):
    e = struct.unpack_from('<I', pe, 0x3c)[0]
    nsec = struct.unpack_from('<H', pe, e + 6)[0]
    opt = struct.unpack_from('<H', pe, e + 20)[0]
    s = e + 24 + opt
    for i in range(nsec):
        vs, vaddr, rs, rp = struct.unpack_from('<IIII', pe, s + i * 40 + 8)
        if vaddr <= va - BASE < vaddr + max(vs, rs):
            return va - BASE - vaddr + rp
    raise ValueError('va not in a section')


def dis(code, va, title):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print(title)
    out = []
    for i in md.disasm(code, va):
        print('  %08x  %-22s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        out.append(i)
    return out


def main(a):
    pe = open(a[0], 'rb').read()
    o = va_to_off(pe, GUARD_VA)
    cur = pe[o:o + len(GUARD)]
    ok = cur == GUARD
    print('guard 0x%x (%d bytes): %s' % (GUARD_VA, len(GUARD), 'MATCH' if ok else 'DIFFERENT ' + cur.hex()))
    assert PATCH_VA + len(PATCH) == 0x47abce, 'patch must end at 0x47abce'
    print('patch %d bytes 0x%x..0x%x' % (len(PATCH), PATCH_VA, PATCH_VA + len(PATCH)))
    dis(cur[:0x44], GUARD_VA, 'original:')
    new = cur[:PATCH_VA - GUARD_VA] + PATCH + cur[PATCH_VA - GUARD_VA + len(PATCH):]
    ins = dis(new[:0x44], GUARD_VA, 'patched:')
    tg = {i.address: i for i in ins}
    bad = 0
    for i in ins:
        if i.mnemonic in ('jae', 'je', 'jmp', 'jne') and PATCH_VA <= i.address < 0x47abce:
            t = int(i.op_str, 16)
            good = t in (0x47aba3, 0x47abce) and (t in tg or t == 0x47abce)
            print('  branch %08x -> %08x %s' % (i.address, t, 'ok' if good else 'BAD'))
            bad += not good
    print('result: %s' % ('ok' if ok and not bad else 'FAILED'))
    return 0 if ok and not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
