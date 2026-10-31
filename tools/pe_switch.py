"""Decode an MSVC two-level switch of a 32-bit PE (x86) such as tru.exe into 'case value -> target' lines
(read-only; developer channel / cheat mode finding: which message id reaches which handler block).

Pattern in the code:
    lea  eax, [edi - LOW]          ; case value minus the lowest case
    cmp  eax, COUNT-1 ; ja default
    movzx eax, byte ptr [eax + BYTETABLE]
    jmp  dword ptr [eax*4 + JUMPTABLE]
A one-level switch (no byte table) is decoded with BYTETABLE = 0.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/pe_switch.py EXE LOW COUNT BYTETABLE JUMPTABLE [--target VA]
      LOW / COUNT decimal or 0x hex; with --target only the case values that reach VA are printed
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def main(argv):
    if len(argv) < 5: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    low, count = int(argv[1], 0), int(argv[2], 0)
    bt, jt = int(argv[3], 16), int(argv[4], 16)
    want = int(argv[argv.index('--target') + 1], 16) if '--target' in argv else None
    base, secs = PE.sections(exe)
    for k in range(count):
        idx = exe[off_of(secs, bt) + k] if bt else k
        tgt = struct.unpack_from('<I', exe, off_of(secs, jt) + 4 * idx)[0]
        if want is None or tgt == want:
            print('case %5d (0x%04x)  index %3d  -> 0x%08x' % (low + k, low + k, idx, tgt))


if __name__ == '__main__':
    main(sys.argv[1:])
