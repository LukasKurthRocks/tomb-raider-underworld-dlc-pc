"""Find the places where the title update changed one small immediate into another (read-only).

Shadow combat translation (docs Befund-Schattenkampf.md): the TU grew the player's target list from 7 to 10 targeters
(retail `li/cmpwi rX, 7` -> TU `0xa`, the candidate mask 0x71 -> 0x3f1, the array size 0x1c -> 0x28). This tool lists,
for every paired function (work/tu_funcdiff/pairs.tsv of tools/tu_func_pair.py), the TU instructions `li` / `cmpwi` /
`cmplwi` / `addi rX, 0, imm` with immediate NEW whose retail partner has the same opcode with immediate OLD at the
same instruction index (functions of equal length) or, for different lengths, the same count of both immediates.
The PC sites then follow from the PC partner of each function (tools/xbox_pc_candidates.py, pe_dis.py).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_imm_change_sites.py RETAIL_IMAGE TU_IMAGE PAIRS_TSV OLD:NEW[,OLD:NEW..]
  e.g. ... work/tu_funcdiff/pairs.tsv 7:0xa,0x71:0x3f1,0x1c:0x28
"""
import sys, struct

BASE = 0x82000000


def imm_insns(d, start, size):
    out = []
    for k in range(size // 4):
        o = start - BASE + 4 * k
        if o + 4 > len(d): break
        w = struct.unpack_from(">I", d, o)[0]
        op = w >> 26
        ra = (w >> 16) & 31
        imm = w & 0xffff
        if op == 14 and ra == 0: out.append((k, "li", imm, start + 4 * k))      # li = addi rD, 0, imm
        elif op == 11: out.append((k, "cmpwi", imm, start + 4 * k))
        elif op == 10: out.append((k, "cmplwi", imm, start + 4 * k))
    return out


def main(argv):
    if len(argv) != 4:
        print(__doc__); return 2
    retail, tu = open(argv[0], "rb").read(), open(argv[1], "rb").read()
    changes = [tuple(int(x, 0) for x in c.split(":")) for c in argv[3].split(",")]
    rows = [l.rstrip("\n").split("\t") for l in open(argv[2], encoding="utf-8")][1:]
    n = 0
    for r in rows:
        if len(r) < 8 or not r[0] or not r[1]: continue
        ta, ra, ts, rs = int(r[0], 16), int(r[1], 16), int(r[6]), int(r[7])
        ti, ri = imm_insns(tu, ta, ts), imm_insns(retail, ra, rs)
        for old, new in changes:
            tn = [x for x in ti if x[2] == new]
            rn = [x for x in ri if x[2] == old]
            if not tn or not rn: continue
            if ts == rs:
                rk = dict((x[0], x) for x in rn)
                hits = [(x, rk[x[0]]) for x in tn if x[0] in rk and rk[x[0]][1] == x[1]]
            else:
                hits = list(zip(tn, rn)) if len(tn) == len(rn) else []
            for t, rr in hits:
                n += 1
                print("TU 0x%08x (fn 0x%08x) %s 0x%x  <-  retail 0x%08x (fn 0x%08x) %s 0x%x  [%s]" %
                      (t[3], ta, t[1], new, rr[3], ra, rr[1], old, r[8]))
    print("%d sites" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
