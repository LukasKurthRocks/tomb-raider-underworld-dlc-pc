"""Which entries of a global pointer array does Xbox code read - per function, TU against retail (read-only).

Shadow combat translation (docs Befund-Schattenkampf.md): the player's target list is a global pointer to an array of
targeter pointers (TU 0x829ca648, retail 0x829ca560, PC [0xfadfac]); the TU grew it from 7 to 10 entries and gave
index 6 other parameters. To see which code reads which index, every `lwz rA, lo(rHi)` of the global (after
`lis rHi, hi`) marks rA as the array base; a later `lwz rD, d(rA)` is "index d / 4", an `lwzx rD, rA, rB` / `add` +
`lwz` is "variable". The mark is dropped when rA is written again or at the next blr / function start (.pdata not
needed - linear scan, conservative). Each hit is reported with its function start (closest preceding `mflr r12`).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_list_index_users.py IMAGE GLOBAL [--tu-retail RETAIL_IMAGE RETAIL_GLOBAL]
  With --tu-retail the first image is the TU and the second the retail image; the functions are not paired here -
  both lists are printed (per index count, then every read) for a side-by-side read.
"""
import sys, struct, collections

BASE = 0x82000000
TEXT_START, TEXT_END = 0x82080000, 0x82700000


def scan(path, glob):
    d = open(path, "rb").read()
    hi_want, lo_want = (glob + 0x8000) >> 16 & 0xffff, glob & 0xffff
    lis = {}             # register -> hi half
    base = set()         # registers holding the array pointer
    func = TEXT_START
    hits = []
    end = min(TEXT_END - BASE, len(d))
    for o in range(TEXT_START - BASE, end, 4):
        w = struct.unpack_from(">I", d, o)[0]
        a = o + BASE
        if w == 0x7d8802a6:                         # mflr r12 = function prologue
            func = a; lis.clear(); base.clear()
        op = w >> 26
        rd, ra = (w >> 21) & 31, (w >> 16) & 31
        imm = w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 15 and ra == 0:                    # lis rd, imm
            lis[rd] = imm; base.discard(rd); continue
        if op == 32:                                # lwz rd, simm(ra)
            if ra in lis and lis[ra] == hi_want and imm == lo_want:
                base.add(rd); lis.pop(rd, None); continue
            if ra in base:
                hits.append((func, a, "index %d" % (simm // 4) if simm % 4 == 0 else "disp 0x%x" % simm))
            base.discard(rd); lis.pop(rd, None); continue
        if op == 31 and ((w >> 1) & 0x3ff) == 23:   # lwzx rd, ra, rb
            rb = (w >> 11) & 31
            if ra in base or rb in base: hits.append((func, a, "variable"))
            base.discard(rd); lis.pop(rd, None); continue
        if op == 31 and ((w >> 1) & 0x3ff) == 266:  # add rd, ra, rb
            rb = (w >> 11) & 31
            if ra in base or rb in base: hits.append((func, a, "variable (add)"))
            base.discard(rd); lis.pop(rd, None); continue
        if w == 0x4e800020:                         # blr
            lis.clear(); base.clear(); continue
        if op in (14, 15, 21, 24, 25, 28, 31, 34, 40, 33, 35, 41):
            base.discard(rd); lis.pop(rd, None)     # rd overwritten (approximate)
    return hits


def report(tag, hits):
    per = collections.Counter(h[2] for h in hits)
    print("%s: %d reads; by index: %s" % (tag, len(hits), ", ".join("%s x%d" % kv for kv in sorted(per.items()))))
    for func, a, what in hits:
        print("  fn 0x%08x  @0x%08x  %s" % (func, a, what))


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    report("image 1 global 0x%x" % int(argv[1], 0), scan(argv[0], int(argv[1], 0)))
    if len(argv) >= 5 and argv[2] == "--tu-retail":
        report("image 2 global 0x%x" % int(argv[4], 0), scan(argv[3], int(argv[4], 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
