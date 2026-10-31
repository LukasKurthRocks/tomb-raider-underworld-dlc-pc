"""List every x86 instruction of a 32-bit PE (tru.exe) that names one of the given absolute addresses (memory operand
`[0xADDR]` / `[reg + 0xADDR]` or immediate), read-only. Weapons / ammo / health research 2026-10-31: who sets and
tests the player flag word 0xfada74 (bit 0x20000 = no damage) and the playerstate pointer 0xfadb58.

Linear sweep of the executable sections with capstone (like tools/pe_disp_scan.py, which only matches base +
displacement operands); read the hits in context with tools/pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_abs_uses.py EXE ADDR[,ADDR..] [--grep TEXT]   TEXT = only lines whose text contains it
"""
import sys, os
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    want = [int(x, 16) for x in argv[1].split(',')]
    keys = ['0x%x' % a for a in want]
    g = argv[argv.index('--grep') + 1] if '--grep' in argv else None
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.skipdata = True
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        for ins in md.disasm(exe[rptr:rptr + size], sva):
            s = ins.op_str
            if any(k in s for k in keys):
                t = '0x%08x  %s %s' % (ins.address, ins.mnemonic, s)
                if g is None or g in t: print(t)


if __name__ == '__main__':
    main(sys.argv[1:])
