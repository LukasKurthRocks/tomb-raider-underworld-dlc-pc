"""Find vtables in a PE whose slots point at functions starting with given bytes (read-only).

Shadow combat translation (docs Befund-Schattenkampf.md): the TU camera class answers vtbl[0x38] with `addi r3, r3,
0x10; blr` and vtbl[0x3c] with `addi r3, r3, 0x50; blr`; this finds the PC camera vtable(s) with the same small
accessors at the same slots (`lea eax, [ecx+0x10]; ret` = 8d4110c3, `lea eax, [ecx+0x50]; ret` = 8d4150c3).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_vtable_slot_find.py EXE SLOT=HEX [SLOT=HEX ..]      e.g. 0x38=8d4110c3 0x3c=8d4150c3
Prints every dword-aligned address A in a data section with [A + SLOT] -> code starting with HEX for all pairs, and
the vtable's first 0x40 slots' targets.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    pe = open(argv[0], "rb").read()
    base, secs = PE.sections(pe)
    want = [(int(a, 0), bytes.fromhex(h)) for a, h in (x.split("=") for x in argv[1:])]

    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        return None
    text = [s for s in secs if s[0].startswith(".text")]
    data = [s for s in secs if not s[0].startswith(".text")]

    def is_code(va):
        return any(s[1] <= va < s[1] + s[3] for s in text)
    hits = 0
    for name, sva, rptr, size, _ in data:
        for o in range(0, size - 0x200, 4):
            ok = True
            for slot, h in want:
                t = struct.unpack_from("<I", pe, rptr + o + slot)[0]
                if not is_code(t):
                    ok = False; break
                to = off(t)
                if to is None or pe[to:to + len(h)] != h:
                    ok = False; break
            if ok:
                hits += 1
                va = sva + o
                slots = [struct.unpack_from("<I", pe, rptr + o + 4 * k)[0] for k in range(0x10)]
                print("vtable? 0x%08x (%s): slots 0..0x3c -> %s" % (va, name, " ".join("0x%x" % s for s in slots)))
    print("%d candidates" % hits)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
