"""Static check of planned code patch sites in a 32-bit PE (tru.exe) - read-only; 2026-11-04, TruMenu 0.10.4 /
TruDlc2Player 0.5 (docs Befund-Menue-Dlc2Player-0411b.md).

A detour that overwrites LEN bytes at SITE with `jmp rel32` (+ nops) is safe only if
  1. the bytes at SITE are the expected instructions (HEX, spaces allowed) and the patch covers whole instructions,
  2. no branch lands strictly inside (SITE, SITE + LEN): the jump would hit the middle of the new jmp / the nops.
Check 2 is done twice: (a) every jmp / jcc / call with a direct target in the function range FROM..TO, decoded with
capstone (short and near forms), (b) every rel32 E8 / E9 / 0F 8x in all executable sections (byte pattern, like
tools/pe_callers.py - may over-report, never under-report for rel32).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_patch_site_check.py EXE SITE:LEN:HEX:FROM:TO [SITE:LEN:HEX:FROM:TO ..]
  all numbers hex; HEX = the expected bytes at SITE (at least LEN bytes, spaces / '_' ignored)
Prints per site the instructions covered, the bytes check, any inner branch target, and ok / FAIL; exit 1 on a FAIL.
Only addresses and instruction text are printed - no game bytes beyond the checked instructions.
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, va):
    for _, sva, rptr, size, _ in secs:
        if sva <= va < sva + size: return rptr + va - sva
    return -1


def rel32_targets(pe, secs, lo, hi):
    """(source, kind, target) for every rel32 E8 / E9 / 0F 80..8F in code sections with lo < target < hi"""
    out = []
    for name, va, rptr, size, chars in secs:
        if not chars & 0x20000000: continue
        blob = pe[rptr:rptr + size]
        for i in range(1, len(blob) - 4):
            b = blob[i - 1]
            if b in (0xe8, 0xe9):
                src, n = va + i - 1, 5
            elif i >= 2 and blob[i - 2] == 0x0f and 0x80 <= b <= 0x8f:
                src, n = va + i - 2, 6
            else:
                continue
            t = (src + n + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff
            if lo < t < hi: out.append((src, 'rel32 %02x' % b, t))
    return out


def main(argv):
    pe = open(argv[0], 'rb').read()
    base, secs = PE.sections(pe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False
    fails = 0
    for spec in argv[1:]:
        site_s, len_s, hex_s, from_s, to_s = spec.split(':')
        site, length = int(site_s, 16), int(len_s, 16)
        fr, to = int(from_s, 16), int(to_s, 16)
        want = bytes.fromhex(hex_s.replace(' ', '').replace('_', ''))
        o = off_of(secs, site)
        have = pe[o:o + len(want)]
        ok = True
        print('== site 0x%08x, %d bytes patched (function range 0x%08x..0x%08x)' % (site, length, fr, to))
        if have != want:
            print('  bytes MISMATCH: expected %s, found %s' % (want.hex(), have.hex())); ok = False
        else:
            print('  bytes ok (%d bytes)' % len(want))
        # instruction boundaries of the patched range
        end, covered = site, []
        for ins in md.disasm(pe[o:o + length + 16], site):
            if ins.address >= site + length: break
            covered.append('%08x  %-16s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
            end = ins.address + ins.size
        for c in covered: print('    ' + c)
        if end != site + length:
            print('  instruction boundary FAIL: the last covered instruction ends at 0x%08x, patch ends at 0x%08x'
                  % (end, site + length)); ok = False
        else:
            print('  instruction boundaries ok (%d instructions)' % len(covered))
        # (a) direct branches of the function range
        fo = off_of(secs, fr)
        inner = []
        for ins in md.disasm(pe[fo:fo + (to - fr)], fr):
            if ins.mnemonic.startswith('j') or ins.mnemonic in ('call', 'loop', 'jecxz'):
                try:
                    t = int(ins.op_str, 16)
                except ValueError:
                    continue
                if site < t < site + length: inner.append((ins.address, ins.mnemonic, t))
        # (b) rel32 anywhere
        inner += rel32_targets(pe, secs, site, site + length)
        if inner:
            for src, kind, t in inner: print('  inner branch target FAIL: 0x%08x %s -> 0x%08x' % (src, kind, t))
            ok = False
        else:
            print('  no branch into (0x%08x, 0x%08x): function range decoded + rel32 scan of all code' %
                  (site, site + length))
        print('  %s' % ('ok' if ok else 'FAIL'))
        fails += 0 if ok else 1
    print('total: %d sites, %d fail' % (len(argv) - 1, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
