"""Show Lara's state-machine records for given ids on the Xbox TU, the Xbox retail and the PC (read-only).

Shadow combat translation (docs Befund-Schattenkampf.md): Lara's two state machines (gameTracker +0xf10 / +0xf14)
register three tables each - conditions {id, group, fn}, activities {id, fn}, states {id, fn x 6} - in
TU 0x82473b50 / retail 0x8246e418 / PC tru+0x368b60. The table addresses are read from those functions' code
(lis / addi pairs on the Xbox, push imm32 on the PC), then every record of the asked ids is printed with the
TU -> retail pairing of each function (TU table slot -> retail record with the same id and slot).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/lara_table_ids.py RETAIL_IMAGE TU_IMAGE TRU_EXE ID[,ID...]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

BASE = 0x82000000
TU_REG, RETAIL_REG, PC_REG = 0x82473b50, 0x8246e418, 0x00768b60


def be(d, a):
    return struct.unpack_from(">I", d, a - BASE)[0]


def xbox_tables(d, reg):
    """the six r4 operands (lis rX, hi / addi r4, rX, lo) of the registration function, in code order"""
    out, hi = [], {}
    for a in range(reg, reg + 0x100, 4):
        w = be(d, a)
        op = w >> 26
        if op == 15 and ((w >> 16) & 31) == 0:      # lis rD, imm
            hi[(w >> 21) & 31] = (w & 0xffff) << 16
        elif op == 14 and ((w >> 21) & 31) == 4:     # addi r4, rA, imm
            ra = (w >> 16) & 31
            if ra in hi:
                lo = w & 0xffff
                if lo & 0x8000: lo -= 0x10000
                out.append((hi[ra] + lo) & 0xffffffff)
    return out


def pe_at(pe, va):
    for s in PE.sections(pe)[1]:
        if s[1] <= va < s[1] + s[3]: return s[2] + va - s[1]
    raise ValueError("VA 0x%x not in a section" % va)


def pc_tables(pe):
    o = pe_at(pe, PC_REG); code = pe[o:o + 0xc0]; out = []
    for i in range(len(code) - 7):
        if code[i] == 0x68 and code[i + 5] == 0x8b and code[i + 6] == 0xce:   # push imm32; mov ecx, esi
            out.append(struct.unpack_from("<I", code, i + 1)[0])
    return out


def xbox_recs(d, start, n):
    out, a = {}, start
    while True:
        r = struct.unpack_from(">%dI" % n, d, a - BASE)
        out.setdefault(r[0], []).append((a, r[1:]))
        if r[0] == 0: return out
        a += 4 * n


def pc_recs(pe, start, n):
    out, o, a = {}, pe_at(pe, start), start
    while True:
        r = struct.unpack_from("<%dI" % n, pe, o)
        out.setdefault(r[0], []).append((a, r[1:]))
        if r[0] == 0: return out
        o += 4 * n; a += 4 * n


def main(argv):
    if len(argv) != 4:
        print(__doc__); return 2
    retail, tu = open(argv[0], "rb").read(), open(argv[1], "rb").read()
    pe = open(argv[2], "rb").read()
    ids = [int(x, 0) for x in argv[3].split(",")]
    t_tu, t_rt, t_pc = xbox_tables(tu, TU_REG), xbox_tables(retail, RETAIL_REG), pc_tables(pe)
    print("tables (machine 1 cond / act / state, machine 2 cond / act / state)")
    print("  TU     " + " ".join("0x%08x" % x for x in t_tu))
    print("  retail " + " ".join("0x%08x" % x for x in t_rt))
    print("  PC     " + " ".join("0x%08x" % x for x in t_pc))
    kinds = (("condition", 3, 1), ("activity", 2, 0), ("state", 7, 2))
    for m in range(2):
        for k, (name, n, _) in enumerate(kinds):
            i = 3 * m + k
            a, b, c = xbox_recs(tu, t_tu[i], n), xbox_recs(retail, t_rt[i], n), pc_recs(pe, t_pc[i], n)
            for ident in ids:
                if ident not in a and ident not in b and ident not in c: continue
                print("machine %d %s %d:" % (m + 1, name, ident))
                for tag, tab in (("TU    ", a), ("retail", b), ("PC    ", c)):
                    for addr, words in tab.get(ident, []):
                        print("  %s @0x%08x: %s" % (tag, addr, " ".join("0x%08x" % w for w in words)))
                    if ident not in tab: print("  %s -" % tag)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
