"""Byte pre-checks for a read-only SweepAndPrune (SAP) usage display in TruMenu (read-only on tru.exe).

2026-11-06 SweepAndPrune: docs/Befund-SweepAndPrune-0611.md plans a TruMenu line "SAP used / capacity" for the
MarkupManager's SweepAndPrune (owner [0xdb94cc], ctor tru+0x1be3a0). Before a plugin reads the pointer chain it
must make sure the exe is the expected build; this tool checks the code / data bytes the plan relies on and prints
the expected runtime values (capacity, memory counter) derived from the constants in the file.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/sap_precheck.py EXE
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

# (VA, expected bytes hex, meaning)
CHECKS = [
    (0x5be390, 'a1cc94db00c3', 'getter: mov eax,[0xdb94cc]; ret (owner = MarkupManager)'),
    (0x5be3a7, '68c800000068e8030000', 'owner ctor: push 200; push 1000 (SAP create arguments)'),
    (0x5be3bd, 'c74618e8030000c74620c8000000', 'owner ctor: [this+0x18]=1000 proxies, [this+0x20]=200'),
    (0x5be3cb, 'e8b0edeaff894604', 'owner ctor: call SAP create 0x46d180; [this+4] = SAP core'),
    (0x5d9ea9, '6a006a24', 'owner allocation: 0x24 bytes'),
    (0x5d9ebc, 'c70614528500', 'derived vtable 0x855214'),
    (0x5d9ec6, '893560f0e7008935cc94db00', 'owner stored to [0xe7f060] and [0xdb94cc]'),
    (0x46c880, '897e2489462c', 'SAP core ctor: [core+0x24]=boxes cap, [core+0x2c]=pair-link param'),
    (0x46c8cb, '8d7850897828', 'SAP core ctor: box stride 0x50, free chain via box+0x28'),
    (0x4633db, '8b410c85c07422', 'AddPair: link = [core+0xc] (free list); none -> warning'),
    (0x4633f0, '83413001', 'AddPair: [core+0x30] += 1 (links used)'),
    (0x463404, '68143e8400e8f2ad0200', 'AddPair: push "Out of space for pairs"; call warning 0x48e200'),
    (0x46344c, '834130ff', 'RemovePair: [core+0x30] -= 1'),
    (0x4635f3, '837b040057', 'AddBox: cmp [core+4], 0 (free box list empty?); push edi'),
    (0x4635fd, '68483e8400e8f9ab0200', 'AddBox: push "Out of space for boxes"; call warning; return 0'),
    (0x46395e, '8343280183433402', 'AddBox: [core+0x28] += 1 (boxes used), [core+0x34] += 2 (endpoints)'),
    (0x463ba4, '834634fe83cdff016e28', 'RemoveBox: [core+0x34] -= 2; ebp = -1; [core+0x28] += ebp'),
    (0x5be5b9, '895024', 'CreateProxy: [box+0x24] = index (box == 0 after overflow -> write to 0x24)'),
    (0x48e20a, '68f035a000', 'warning: vsprintf into 0xa035f0'),
    (0x48e217, 'c705fc37a00001000000', 'warning: [0xa037fc] = 1 (display timer)'),
]
STRINGS = [0x843e14, 0x843e48]


def main(argv):
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)

    def raw(va, n):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size:
                return exe[rptr + va - sva: rptr + va - sva + n]
        return b''

    bad = 0
    for va, hexs, what in CHECKS:
        want = bytes.fromhex(hexs)
        got = raw(va, len(want))
        ok = got == want
        bad += not ok
        print('%s 0x%06x (tru+0x%06x) %-30s %s' % ('OK ' if ok else 'BAD', va, va - base, hexs, what))
        if not ok:
            print('    got %s' % got.hex())
    for va in STRINGS:
        s = raw(va, 80).split(b'\0')[0].decode('ascii', 'replace')
        print('STR 0x%06x (tru+0x%06x) %r' % (va, va - base, s))
    # expected runtime values from the constants
    n, m = 1000, 200
    mem = 1 + n * 0x50 + m * 16 + n * 4 + 3 * n * 40
    print('expected: core+0x24 = %d boxes, core+0x2c = %d -> %d pair links (core+0x08 pool, 8 B each),'
          ' core+0x20 = %d (0x%x) bytes allocated, owner+0x18 = %d proxies' % (n, m, 2 * m, mem, mem, 1000))
    n, m = 3000, 500
    mem = 1 + n * 0x50 + m * 16 + n * 4 + 3 * n * 40
    print('with TU constants (3000, 500): %d pair links, core+0x20 = %d (0x%x) bytes' % (2 * m, mem, mem))
    print('%d of %d byte checks differ' % (bad, len(CHECKS)))


if __name__ == '__main__':
    main(sys.argv[1:])
